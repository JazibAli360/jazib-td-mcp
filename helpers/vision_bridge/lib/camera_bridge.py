"""jazib-td-mcp copy of td-port/lib/camera_bridge.py (sha1 2ce47b178659, 2026-10-26), plus KIND_LANDMARKS = 5 for
helpers/vision_bridge (jzb_vision_bridge). td-port is a separate project: never edited from here.

Client side of td-port's camera-model helper (camera_bridge/, jzb_camera_bridge): protocol, one-in-flight pipeline
and a non-blocking Unix-socket client that TD's Python (x86_64 3.11 under Rosetta) can run inside a frame script.

Stdlib only (struct, socket, subprocess); numpy is used only by the optional pixel helpers when the caller passes numpy
arrays (TD has numpy 2.1.2). Embedded into each camera effect's frame_exec text, so it must not import other td-port
modules. Keep the wire format in step with camera_bridge/src/jzb_camera_bridge.mm and camera_bridge/README.md.

Policy (EXECUTION_GUIDE "Shared camera backend feasibility gate"): at most ONE request in flight per client; a new
frame is sent only after the previous answer (or a timeout) -- so the newest frame is always the one sent and nothing
queues. Every request carries the TD frame number and time; every answer echoes them, so a result is matched to the
exact picture it was computed from. A request without an answer after `timeout_s` drops the connection (the helper
may be stuck or dead) and the client reconnects/respawns; no unbounded latency.
"""
import math
import os
import socket
import struct
import subprocess
import tempfile
import time

PROTOCOL = 1
KIND_DEPTH, KIND_SEG_FAST, KIND_SEG_BALANCED, KIND_FACES, KIND_INFO = 1, 2, 3, 4, 9  # faces: tracker/BRIDGE_REQUEST.md
KIND_LANDMARKS = 5  # jazib-td-mcp: face landmarks (helpers/vision_bridge/README.md)
KIND_NAMES = {KIND_DEPTH: 'depth', KIND_SEG_FAST: 'seg_fast', KIND_SEG_BALANCED: 'seg_balanced', KIND_FACES: 'faces',
              KIND_LANDMARKS: 'landmarks', KIND_INFO: 'info'}
ST_OK, ST_ERROR, ST_NOT_READY, ST_DROPPED, ST_BAD_REQUEST = 0, 1, 2, 3, 4
STATUS_NAMES = {ST_OK: 'ok', ST_ERROR: 'error', ST_NOT_READY: 'not_ready', ST_DROPPED: 'dropped',
                ST_BAD_REQUEST: 'bad_request'}
FL_BOTTOM_UP, FL_INSTANCES = 1, 2
FMT_NONE, FMT_F32, FMT_U8 = 0, 1, 2
REQ = struct.Struct('<4sHBBQdIIIIII')            # 48 bytes
RESP = struct.Struct('<4sHBBQdIIB3xffffIIIII')     # 72 bytes
MAX_SIDE = 2048
DEPTH_READ = (518, 392)                          # DepthFX reads the model's own input size (DepthFX.cpp MODEL_W/H)
assert REQ.size == 48 and RESP.size == 72


def pack_request(kind, frame_id, stamp, width=0, height=0, payload=b'', flags=FL_BOTTOM_UP, delay_ms=0):
    """Header + payload bytes for one request. payload: w*h*4 BGRA bytes (tightly packed), b'' for info."""
    if kind != KIND_INFO:
        if not (0 < width <= MAX_SIDE and 0 < height <= MAX_SIDE):
            raise ValueError('frame size {}x{} outside 1..{}'.format(width, height, MAX_SIDE))
        if len(payload) != width * height * 4:
            raise ValueError('payload {} bytes, expected {}'.format(len(payload), width * height * 4))
    return REQ.pack(b'JZBQ', PROTOCOL, kind, flags, int(frame_id), float(stamp), int(width), int(height),
                    int(delay_ms), len(payload), 0, 0) + bytes(payload)


class Result(object):
    """One answer. data: raw bytes (float32 LE depth or uint8 mask), rows bottom-up (GL / TD numpy order)."""
    __slots__ = ('kind', 'status', 'frame_id', 'stamp', 'width', 'height', 'fmt', 'compute_ms', 'wait_ms', 'p_lo',
                 'p_hi', 'inst_w', 'inst_h', 'data', 'inst', 'text', 'received')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    @property
    def ok(self):
        return self.status == ST_OK

    def status_name(self):
        return STATUS_NAMES.get(self.status, str(self.status))

    def summary(self):
        return {'kind': KIND_NAMES.get(self.kind, self.kind), 'status': self.status_name(), 'frame_id': self.frame_id,
                'stamp': self.stamp, 'size': [self.width, self.height], 'compute_ms': self.compute_ms,
                'wait_ms': self.wait_ms, 'text': self.text}


def parse_response(buf, offset=0):
    """(Result, bytes consumed) for a complete answer at buf[offset:], or (None, 0) if incomplete.
    Raises ValueError on a bad magic/version (framing lost: the caller must drop the connection)."""
    if len(buf) - offset < RESP.size:
        return None, 0
    (magic, version, kind, status, frame_id, stamp, w, h, fmt, compute_ms, wait_ms, p_lo, p_hi, iw, ih, plen, ilen,
     tlen) = RESP.unpack_from(buf, offset)
    if magic != b'JZBR' or version != PROTOCOL:
        raise ValueError('bad response header {!r} v{}'.format(magic, version))
    total = RESP.size + plen + ilen + tlen
    if len(buf) - offset < total:
        return None, 0
    a = offset + RESP.size
    data = bytes(buf[a:a + plen])
    inst = bytes(buf[a + plen:a + plen + ilen])
    text = bytes(buf[a + plen + ilen:a + total - RESP.size]).decode('utf-8', 'replace')
    expect = {FMT_F32: 4 * w * h, FMT_U8: w * h, FMT_NONE: 0}.get(fmt)
    if expect is None or plen != expect or ilen != iw * ih:
        raise ValueError('inconsistent payload: fmt {} {}x{} {} bytes, inst {}x{} {} bytes'.format(
            fmt, w, h, plen, iw, ih, ilen))
    return Result(kind=kind, status=status, frame_id=frame_id, stamp=stamp, width=w, height=h, fmt=fmt,
                  compute_ms=compute_ms, wait_ms=wait_ms, p_lo=p_lo, p_hi=p_hi, inst_w=iw, inst_h=ih, data=data,
                  inst=inst, text=text, received=None), total


def seg_read_size(aspect):
    """PersonKeyLogic.h SegReadSize: long side 512, aspect kept, short side >= 128, multiples of 4."""
    a = aspect if (isinstance(aspect, (int, float)) and math.isfinite(aspect) and aspect > 0) else 16.0 / 9.0
    w = h = 512
    if a >= 1.0:
        h = int(_lround(512.0 / a))
    else:
        w = int(_lround(512.0 * a))
    return max(128, w) // 4 * 4, max(128, h) // 4 * 4


def _lround(x):
    """C lround: halves away from zero (Python round() is banker's)."""
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def bgra_bytes(rgba):
    """TD numpyArray() (float32 h x w x 4, 0..1, rows bottom-up) -> BGRA8 bytes, rows bottom-up. Needs numpy."""
    import numpy  # only inside TD / tools
    a = numpy.clip(rgba[:, :, (2, 1, 0, 3)] * 255.0 + 0.5, 0, 255).astype(numpy.uint8)
    return numpy.ascontiguousarray(a).tobytes()


class Pipeline(object):
    """The one-in-flight rule with frame IDs, independent of sockets (tested in tests/test_camera_bridge.py)."""

    def __init__(self, timeout_s=2.0):
        self.timeout_s = timeout_s
        self.inflight = None          # (frame_id, sent_time)
        self.sent = self.answered = self.timeouts = self.stale = 0
        self.last_frame = None        # frame id of the newest result accepted

    def can_submit(self):
        return self.inflight is None

    def submitted(self, frame_id, now):
        if self.inflight is not None:
            raise RuntimeError('a request is already in flight')
        self.inflight = (frame_id, now)
        self.sent += 1

    def answered_for(self, frame_id, now):
        """True if this answer is the one in flight (it frees the pipeline). Older/unknown answers are stale."""
        if self.inflight is not None and self.inflight[0] == frame_id:
            self.inflight = None
            self.answered += 1
            return True
        self.stale += 1
        return False

    def accept(self, frame_id):
        """Results apply only in frame order: an answer older than the newest applied one is ignored."""
        if self.last_frame is not None and frame_id <= self.last_frame:
            return False
        self.last_frame = frame_id
        return True

    def expired(self, now):
        if self.inflight is not None and now - self.inflight[1] > self.timeout_s:
            self.inflight = None
            self.timeouts += 1
            return True
        return False

    def reset(self):
        """Source change / reconnect: forget what is in flight and which frame was last applied."""
        self.inflight = None
        self.last_frame = None


def default_socket_path(name):
    """A per-user, per-effect socket path short enough for sun_path (104 bytes on macOS)."""
    base = tempfile.gettempdir()
    p = os.path.join(base, 'jzbcb_{}_{}.sock'.format(os.getuid(), name))
    if len(p.encode()) >= 100:
        p = '/tmp/jzbcb_{}_{}.sock'.format(os.getuid(), name)
    return p


class BridgeClient(object):
    """Non-blocking client. Call pump() once per frame; it never waits on the helper.

    helper: path to jzb_camera_bridge (spawned on demand when nothing serves the socket), args: extra serve flags.
    The spawned helper gets --parent-pid (exits with this process) and --idle-exit (exits when unused)."""

    def __init__(self, socket_path, helper=None, args=(), timeout_s=2.0, retry_s=1.0, idle_exit_s=20.0,
                 log_path=None):
        self.socket_path, self.helper, self.args = socket_path, helper, list(args)
        self.retry_s, self.idle_exit_s, self.log_path = retry_s, idle_exit_s, log_path
        self.pipe = Pipeline(timeout_s)
        self.sock = None
        self.proc = None
        self.out = bytearray()
        self.inbuf = bytearray()
        self.next_try = 0.0
        self.last_error = ''
        self.spawns = self.connects = self.disconnects = 0
        self.counts = {}

    # -- connection
    def connected(self):
        return self.sock is not None

    def _connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)
        except OSError:
            pass
        try:
            s.connect(self.socket_path)
        except OSError as e:
            s.close()
            self.last_error = 'connect: {}'.format(e)
            return False
        s.setblocking(False)
        self.sock = s
        self.connects += 1
        return True

    def _spawn(self):
        if not self.helper:
            return False
        if self.proc is not None and self.proc.poll() is None:
            return True  # still starting up
        if not os.path.isfile(self.helper):
            self.last_error = 'helper missing: {}'.format(self.helper)
            return False
        cmd = [self.helper, 'serve', '--socket', self.socket_path, '--parent-pid', str(os.getpid()),
               '--idle-exit', str(self.idle_exit_s)] + self.args
        log = open(self.log_path, 'ab') if self.log_path else subprocess.DEVNULL
        try:
            self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True)
        except OSError as e:
            self.last_error = 'spawn: {}'.format(e)
            return False
        finally:
            if self.log_path:
                log.close()
        self.spawns += 1
        return True

    def ensure(self, now):
        """Connect (spawning the helper if nothing serves the socket); at most one attempt per retry_s."""
        if self.sock is not None:
            return True
        if now < self.next_try:
            return False
        self.next_try = now + self.retry_s
        if self._connect():
            return True
        self._spawn()
        return False

    def drop(self, why):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.disconnects += 1
        self.sock = None
        self.out = bytearray()
        self.inbuf = bytearray()
        self.pipe.reset()
        self.last_error = why

    def close(self, stop_helper=True):
        self.drop('closed')
        if stop_helper and self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    # -- traffic
    def can_submit(self):
        return self.sock is not None and self.pipe.can_submit()

    def submit(self, kind, frame_id, stamp, width=0, height=0, payload=b'', flags=FL_BOTTOM_UP, delay_ms=0, now=None):
        """Queue one request; False (nothing sent) if not connected or one is already in flight."""
        if not self.can_submit():
            return False
        self.out += pack_request(kind, frame_id, stamp, width, height, payload, flags, delay_ms)
        self.pipe.submitted(frame_id, time.monotonic() if now is None else now)
        self._flush()
        return True

    def _flush(self):
        while self.out and self.sock is not None:
            try:
                n = self.sock.send(self.out)
            except (BlockingIOError, InterruptedError):
                return
            except OSError as e:
                self.drop('send: {}'.format(e))
                return
            del self.out[:n]

    def pump(self, now=None, connect=True):
        """Send what is queued, read what has arrived. Returns the complete answers (oldest first).
        connect=False: only service an existing connection (never connect or spawn) -- used while bypassed."""
        now = time.monotonic() if now is None else now
        if not (self.ensure(now) if connect else self.sock is not None):
            return []
        self._flush()
        while self.sock is not None:
            try:
                chunk = self.sock.recv(1 << 20)
            except (BlockingIOError, InterruptedError):
                break
            except OSError as e:
                self.drop('recv: {}'.format(e))
                break
            if not chunk:
                self.drop('helper closed the connection')
                break
            self.inbuf += chunk
        results = []
        while self.sock is not None:
            try:
                r, used = parse_response(self.inbuf)
            except ValueError as e:
                self.drop(str(e))
                break
            if r is None:
                break
            del self.inbuf[:used]
            r.received = now
            self.pipe.answered_for(r.frame_id, now)
            name = r.status_name()
            self.counts[name] = self.counts.get(name, 0) + 1
            results.append(r)
        if self.pipe.expired(now):
            self.drop('no answer within {} s'.format(self.pipe.timeout_s))
        return results

    def stats(self):
        p = self.pipe
        return {'connected': self.sock is not None, 'in_flight': 0 if p.inflight is None else 1, 'sent': p.sent,
                'answered': p.answered, 'timeouts': p.timeouts, 'stale': p.stale, 'counts': dict(self.counts),
                'spawns': self.spawns, 'connects': self.connects, 'disconnects': self.disconnects,
                'out_bytes': len(self.out), 'in_bytes': len(self.inbuf), 'last_error': self.last_error,
                'helper_pid': self.proc.pid if self.proc is not None else None}
