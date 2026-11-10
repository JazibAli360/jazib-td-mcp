"""depth_cam TD runtime (runs inside TouchDesigner; copied into the COMP's `runtime` Text DAT by depth_cam.py).
Called by the COMP's `frame_exec` (onFrameStart / onFrameEnd), `par_exec` (Active off) and the `depth_field` Script
TOP's onCook. State lives in this module's STATE dict (plain Python objects in a DAT module, never in op storage,
T-67). Every call gets the COMP, so the module never relies on TD globals.

Frame flow (helpers/vision_bridge/README.md, kind 1): Frame Start pumps the non-blocking client (one request in
flight, newest frame wins, frame id echoed), eases each good answer into the depth field (numpy) and force-cooks the
Script TOP that uploads it. Frame End reads the 518x392 `detect_bgra` TOP with numpyArray(delayed=True) (T-74: never
a synchronous readback, never right after creating/resizing the TOP; the first 3 frames after a start are skipped)
and sends it when nothing is in flight. Helper or model missing / crashed: Havedepth = 0, the effect passes the video
through, status says why, the helper is respawned with backoff 0.5, 1, 2, 4, 8 s.
"""
import collections
import time

STATE = {}
SKIP_START_FRAMES = 3


def _st(comp):
    s = STATE.get(comp.id)
    if s is None:
        s = STATE[comp.id] = {'client': None, 'ctl': None, 'field': None, 'status': 'off', 'active': False,
                              'lat': collections.deque(maxlen=60), 'comp': collections.deque(maxlen=60),
                              'ans_t': collections.deque(maxlen=120), 'py_ms': collections.deque(maxlen=120),
                              'py_ans_ms': collections.deque(maxlen=60), 'answers': 0, 'restarts': 0,
                              'ok_since': None, 'skip': SKIP_START_FRAMES, 'upload4': False, 'report_t': 0.0,
                              'report_key': None, 'answered_now': False, 'map_size': ''}
    return s


def _L(comp):
    return comp.op('depth_cam_logic').module


def _CB(comp):
    return comp.op('vision_client').module


def _ctl(comp, s):
    if s['ctl'] is None:
        s['ctl'] = _L(comp).Controller()
    return s['ctl']


def _client(comp, s):
    cb = _CB(comp)
    helper = comp.par.Helper.eval()
    model = comp.par.Model.eval()
    c = s['client']
    if c is not None and (c.helper != helper or s.get('model') != model):
        _stop_client(s)
        c = None
    if c is None:
        sock = cb.default_socket_path('dc{}'.format(comp.id))
        c = cb.BridgeClient(sock, helper=helper, args=_L(comp).helper_args(model), timeout_s=2.0, retry_s=0.5,
                            idle_exit_s=20.0)
        s['client'] = c
        s['model'] = model
        _ctl(comp, s).reset('starting helper')
    return c


def _stop_client(s):
    c = s['client']
    if c is not None:
        c.drop('stopped')
        pr = c.proc
        if pr is not None and pr.poll() is None:
            pr.terminate()
            try:
                pr.wait(timeout=1.0)
            except Exception:
                pr.kill()
        c.proc = None
    s['client'] = None


def stop(comp):
    """Active off / rebuild: close the socket, stop the helper this COMP started (terminate, then kill), drop depth."""
    s = _st(comp)
    _stop_client(s)
    if s['ctl'] is not None:
        s['ctl'].reset('off')
    s['field'] = None
    s['have'] = False
    s['status'] = 'off'
    s['active'] = False
    s['skip'] = SKIP_START_FRAMES
    _cook_field(comp)
    _report(comp, s, force=True)


def helper_pid(comp):
    c = _st(comp)['client']
    return c.proc.pid if (c is not None and c.proc is not None and c.proc.poll() is None) else None


def frame_start(comp):
    t0 = time.perf_counter()
    s = _st(comp)
    s['answered_now'] = False
    try:
        _frame_start(comp, s)
    finally:
        s['py_start'] = (time.perf_counter() - t0) * 1000.0


def frame_end(comp):
    t0 = time.perf_counter()
    s = _st(comp)
    try:
        _frame_end(comp, s)
    finally:
        if s['active']:
            ms = s.get('py_start', 0.0) + (time.perf_counter() - t0) * 1000.0
            s['py_ms'].append(ms)
            if s['answered_now']:
                s['py_ans_ms'].append(ms)


def _fake(comp, s, now):
    import numpy as np
    L = _L(comp)
    w, h = L.FAKE_SIZE
    g = s.get('fake_grid')
    if g is None or g[0].shape != (h, w):
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        g = s['fake_grid'] = ((xs + 0.5) / w, (ys + 0.5) / h)  # row 0 = bottom (y up), as TD numpy
    s['field'] = np.clip(L.fake_depth(g[0], g[1], now, np.exp, np.cos, np.sin), 0.0, 1.0).astype(np.float32)
    s['map_size'] = '{}x{} (fake)'.format(w, h)
    s['status'] = 'fake depth (helper off)'
    s['have'] = True
    _cook_field(comp)


def _frame_start(comp, s):
    p = comp.par
    if not p.Active.eval():
        if s['active'] or s['client'] is not None:
            stop(comp)
        return
    if not s['active']:
        s['active'] = True
        s['skip'] = SKIP_START_FRAMES
    L = _L(comp)
    now = time.monotonic()
    ctl = _ctl(comp, s)
    if p.Fakedepth.eval():
        if s['client'] is not None:
            _stop_client(s)
        _fake(comp, s, now)
        _report(comp, s)
        return
    problem = L.model_problem(p.Model.eval())
    if problem:  # never spawn a helper that cannot answer: pass-through with the reason as status
        if s['client'] is not None:
            _stop_client(s)
        s['status'] = problem
        _drop_depth(comp, s, problem)
        _report(comp, s)
        return
    cb = _CB(comp)
    c = _client(comp, s)
    if c.proc is not None and c.proc.poll() is not None:  # a helper we started exited: back off, respawn
        code = c.proc.returncode
        c.proc = None
        c.drop('helper exited (code {})'.format(code))
        s['restarts'] += 1
        c.retry_s = min(8.0, 0.5 * (2 ** min(s['restarts'] - 1, 4)))
        c.next_try = now + c.retry_s
        s['ok_since'] = None
        ctl.reset('helper exited')
    was_connected = c.connected()
    for r in c.pump(now):
        if r.kind != cb.KIND_DEPTH:
            continue
        if r.status == cb.ST_NOT_READY:
            ctl.not_ready(now, r.frame_id)
            continue
        if r.status != cb.ST_OK:
            if r.status != cb.ST_DROPPED:
                ctl.error(now, r.frame_id, r.text or r.status_name())
            continue
        try:
            L.check_answer(r.data, r.width, r.height)
        except ValueError as e:
            ctl.error(now, r.frame_id, str(e))
            continue
        e = ctl.result(now, r.frame_id, r.p_lo, r.p_hi, r.width, r.height, float(p.Smooth.eval()))
        if e is None:
            continue
        import numpy as np
        raw = np.frombuffer(r.data, dtype=np.float32).reshape(r.height, r.width)
        s['field'] = L.field_step_np(np, None if e['first'] else s['field'], raw, e['lo'], e['span'], e['k'])
        s['map_size'] = '{}x{}'.format(r.width, r.height)
        s['answers'] += 1
        s['answered_now'] = True
        s['ans_t'].append(now)
        s['lat'].append((now - e['sent_t']) * 1000.0)
        s['comp'].append(r.compute_ms)
        if s['ok_since'] is None:
            s['ok_since'] = now
        elif now - s['ok_since'] > 5.0:
            c.retry_s = 0.5
    if was_connected and not c.connected():
        ctl.reset('connection lost')
    have = ctl.showing(now, float(p.Hold.eval()))
    if not have and s['field'] is not None:
        s['field'] = None
    status = ctl.status
    if not c.connected():
        err = c.last_error or ''
        if 'missing' in err:
            status = err
        elif s['restarts'] and c.proc is None:
            status = 'helper exited, restart #{} (backoff {:.1f} s)'.format(s['restarts'], c.retry_s)
        else:
            status = 'starting helper'
    s['status'] = status
    s['have'] = have
    if s['answered_now'] or (not have and s.get('uploaded_have', False)):
        _cook_field(comp)
    _report(comp, s)


def _drop_depth(comp, s, why):
    if s['ctl'] is not None and s['ctl'].has_depth:
        s['ctl'].reset(why)
    if s['field'] is not None or s.get('uploaded_have', False):
        s['field'] = None
        _cook_field(comp)
    s['have'] = False


def _frame_end(comp, s):
    p = comp.par
    if not p.Active.eval() or p.Fakedepth.eval():
        return
    c = s['client']
    if c is None or not c.connected():
        return
    if s['skip'] > 0:  # T-74: no readback in the first frames after a start / rebuild
        s['skip'] -= 1
        return
    ctl = _ctl(comp, s)
    now = time.monotonic()
    if not ctl.want_request(now, c.can_submit()):
        return
    t = comp.op('detect_bgra')
    if t is None:
        return
    a = t.numpyArray(delayed=True)  # previous frame's download: no GPU stall, no sync readback (T-74)
    if a is None or a.ndim != 3 or a.shape[2] != 4:
        return
    h, w = int(a.shape[0]), int(a.shape[1])
    L = _L(comp)
    if (w, h) != L.MODEL_IN:
        return
    cb = _CB(comp)
    import numpy as np
    import td
    fid = int(td.absTime.frame)
    if c.submit(cb.KIND_DEPTH, fid, now, w, h, L.bytes_from_bgra_float(np, a), cb.FL_BOTTOM_UP, now=now):
        ctl.sent_frame(now, fid)


def _cook_field(comp):
    o = comp.op('depth_field')
    if o is not None:
        o.cook(force=True)


def cook_depth(comp, sop):
    """depth_field Script TOP onCook: upload the field (mono 32-bit float, 1 = near, rows bottom-up). No field ->
    a 2x2 black map (Havedepth 0 makes the effect pass the video through anyway)."""
    import numpy as np
    s = _st(comp)
    f = s['field'] if s.get('have') else None
    s['uploaded_have'] = f is not None
    a = (f if f is not None else np.zeros((2, 2), dtype=np.float32))[:, :, None]
    if not s['upload4']:
        try:
            sop.copyNumpyArray(np.ascontiguousarray(a))
            return
        except Exception:
            s['upload4'] = True  # 1-channel upload refused on this build: send RGBA (same value in every channel)
    sop.copyNumpyArray(np.ascontiguousarray(np.repeat(a, 4, axis=2)))


def _report(comp, s, force=False):
    """Info table + Output pars, at most 4 times a second and only when something changed (T-72: no per-frame DAT
    churn)."""
    hv = getattr(comp.par, 'Havedepth', None)  # the shader's pass-through switch: never rate-limited
    if hv is not None and int(hv.eval()) != (1 if s.get('have') else 0):
        hv.val = 1 if s.get('have') else 0
    now = time.monotonic()
    if not force and now - s['report_t'] < 0.25:
        return
    s['report_t'] = now
    L = _L(comp)
    p = comp.par
    rate = len([t for t in s['ans_t'] if now - t <= 2.0]) / 2.0
    ctl = s['ctl']
    lo = ctl.easer.lo if (ctl is not None and ctl.has_depth) else None
    hi = ctl.easer.hi if (ctl is not None and ctl.has_depth) else None
    med = L.median(s['lat'])
    c = s['client']
    d = {'status': s['status'], 'backend': 'core ml depth anything v2 small (jzb_vision_bridge, kind 1)',
         'helper_pid': helper_pid(comp), 'have_depth': int(bool(s.get('have'))), 'map_size': s['map_size'],
         'range_lo': lo, 'range_hi': hi, 'latency_ms_median': med, 'latency_ms_p95': L.pct(s['lat'], 0.95),
         'compute_ms_median': L.median(s['comp']), 'answers_per_s': rate, 'answers': s['answers'],
         'ignored': ctl.ignored if ctl is not None else 0, 'restarts': s['restarts'],
         'python_ms_per_frame_median': L.median(s['py_ms']),
         'python_ms_answer_frame_median': L.median(s['py_ans_ms']),
         'last_error': c.last_error if (c is not None and not c.connected()) else ''}
    rows = L.info_rows(d)
    key = tuple(rows)
    if key != s['report_key']:
        s['report_key'] = key
        info = comp.op('info')
        if info is not None:
            info.clear()
            for r in rows:
                info.appendRow(list(r))
    for name, v in (('Status', s['status']), ('Latency', round(med or 0.0, 1)), ('Rate', rate)):
        par = getattr(p, name, None)
        if par is not None and par.eval() != v:
            par.val = v
