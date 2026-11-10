"""face_track TD runtime (runs inside TouchDesigner; copied into the COMP's `runtime` Text DAT by face_track.py).
Called by the COMP's `frame_exec` (onFrameStart / onFrameEnd), `par_exec` (Active / Calibrate) and the Script CHOPs'
onCook. State lives in this module's STATE dict (plain Python objects in a DAT module, never in op storage, T-67).
Every call gets the COMP, so the module never relies on TD globals.

Frame flow (helpers/vision_bridge/README.md): Frame Start pumps the non-blocking client (one request in flight,
newest frame wins, frame id echoed), feeds answers to the tracker and cooks the CHOPs; Frame End reads the small
detect TOP and sends it if nothing is in flight. Helper missing / crashed: outputs stay valid (no faces = video
pass-through, black masks), status says why, the helper is respawned with backoff 0.5, 1, 2, 4, 8 s.
"""
import collections
import time

STATE = {}


def _st(comp):
    s = STATE.get(comp.id)
    if s is None:
        s = STATE[comp.id] = {'client': None, 'tracker': None, 'slots': [], 'status': 'off', 'sent': {},
                              'lat': collections.deque(maxlen=60), 'comp': collections.deque(maxlen=60),
                              'ans_t': collections.deque(maxlen=120), 'restarts': 0, 'ok_since': None,
                              'counts': None, 'answers': 0, 'faces_seen': 0, 'active': False, 'error': '',
                              'last_ans_t': None, 'aspect': 16 / 9.0, 'raw_eyes': None,
                              'py_ms': collections.deque(maxlen=120)}
    return s


def _L(comp):
    return comp.op('face_track_logic').module


def _CB(comp):
    return comp.op('vision_client').module


def _tracker(comp, s):
    L = _L(comp)
    p = comp.par
    if s['tracker'] is None:
        s['tracker'] = L.Tracker()
    t = s['tracker']
    t.maxfaces = int(p.Maxfaces.eval())
    t.hold = int(p.Holdframes.eval())
    return t


def _client(comp, s):
    cb = _CB(comp)
    helper = comp.par.Helper.eval()
    c = s['client']
    if c is not None and c.helper != helper:
        c.close()
        c = None
    if c is None:
        sock = cb.default_socket_path('ft{}'.format(comp.id))
        c = cb.BridgeClient(sock, helper=helper, args=['--no-depth', '--no-seg', '--no-faces'], timeout_s=2.0,
                            retry_s=0.5, idle_exit_s=20.0)
        s['client'] = c
    return c


def stop(comp):
    """Active off / rebuild: close the socket and stop the helper this COMP started (terminate, then kill)."""
    s = _st(comp)
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
    s['sent'] = {}
    if s['tracker'] is not None:
        s['tracker'].reset()
    s['slots'] = []
    s['status'] = 'off'
    s['active'] = False
    _cook_outputs(comp)
    _report(comp, s)


def helper_pid(comp):
    c = _st(comp)['client']
    return c.proc.pid if (c is not None and c.proc is not None and c.proc.poll() is None) else None


def frame_start(comp):
    t0 = time.perf_counter()
    try:
        _frame_start(comp)
    finally:
        _st(comp)['py_start'] = (time.perf_counter() - t0) * 1000.0


def frame_end(comp):
    t0 = time.perf_counter()
    try:
        _frame_end(comp)
    finally:
        s = _st(comp)
        if s['active']:
            s['py_ms'].append(s.get('py_start', 0.0) + (time.perf_counter() - t0) * 1000.0)


def _frame_start(comp):
    s = _st(comp)
    p = comp.par
    if not p.Active.eval():
        if s['active'] or s['client'] is not None:
            stop(comp)
        return
    s['active'] = True
    L = _L(comp)
    cb = _CB(comp)
    tr = _tracker(comp, s)
    now = time.perf_counter()
    src = comp.op('src')
    s['aspect'] = src.width / float(max(1, src.height))
    smooth, minconf = float(p.Smooth.eval()), float(p.Minconf.eval())
    if p.Fakeface.eval():
        if s['client'] is not None:
            stop(comp)
            s['active'] = True
        f = L.fake_face(now, 0.5, 0.45, 0.35, s['aspect'])
        s['slots'] = tr.update([f], now, smooth, minconf)
        s['status'] = 'fake face (helper off)'
        _cook_outputs(comp)
        _report(comp, s)
        _log(comp, s, [f])
        return
    c = _client(comp, s)
    # crash watch: a helper we started that exited -> count it, back off, respawn on the next ensure()
    if c.proc is not None and c.proc.poll() is not None:
        code = c.proc.returncode
        c.proc = None
        c.drop('helper exited (code {})'.format(code))
        s['restarts'] += 1
        c.retry_s = min(8.0, 0.5 * (2 ** min(s['restarts'] - 1, 4)))
        c.next_try = time.monotonic() + c.retry_s
        s['ok_since'] = None
    new = None
    for r in c.pump():
        if r.kind != cb.KIND_LANDMARKS:
            continue
        sent = s['sent'].pop(r.frame_id, None)
        if r.status == cb.ST_NOT_READY:
            s['status'] = 'warming up'
            continue
        if r.status != cb.ST_OK:
            if r.status != cb.ST_DROPPED:
                s['status'] = 'error: ' + (r.text or r.status_name())
            continue
        if not c.pipe.accept(r.frame_id):
            continue
        try:
            faces = L.parse_landmarks(r.data, r.width, r.height, r.text)
        except ValueError as e:
            s['status'] = 'error: ' + str(e)
            continue
        if faces and s['counts'] is None:
            s['counts'] = L.counts_of(faces)
        new = faces
        s['answers'] += 1
        s['ans_t'].append(now)
        s['last_ans_t'] = now
        if sent is not None:
            s['lat'].append((now - sent) * 1000.0)
        s['comp'].append(r.compute_ms)
        if s['ok_since'] is None:
            s['ok_since'] = now
        elif now - s['ok_since'] > 5.0:
            c.retry_s = 0.5
        s['status'] = 'tracking' if faces else 'no face'
    if len(s['sent']) > 8:
        s['sent'] = {}
    if not c.connected():
        err = c.last_error or ''
        if 'missing' in err:
            s['status'] = err
        elif s['restarts'] and c.proc is None:
            s['status'] = 'helper exited, restart #{} (backoff {:.1f} s)'.format(s['restarts'], c.retry_s)
        else:
            s['status'] = 'starting helper'
    if new is None and L.stale(s['last_ans_t'], now):
        new = []  # answers stopped (helper gone/stalled): age the slots so present ramps to 0 after Holdframes
    s['slots'] = tr.update(new, now, smooth, minconf)
    _cook_outputs(comp)
    _report(comp, s)
    _log(comp, s, new)


def _log(comp, s, new):
    """Verification hook: when STATE[comp.id]['log'] is a list (set from td_exec), append one plain record per frame."""
    lg = s.get('log')
    if not isinstance(lg, list) or len(lg) > 2000:
        return
    ctl = comp.op('ctl')
    rec = {'t': time.perf_counter(), 'status': s['status'], 'raw': None if new is None else len(new)}
    if ctl is not None:
        for ch in ctl.chans():
            rec[ch.name] = round(float(ch[0]), 4)
    lg.append(rec)


def _frame_end(comp):
    s = _st(comp)
    p = comp.par
    if not p.Active.eval() or p.Fakeface.eval():
        return
    c = s['client']
    if c is None or not c.can_submit():
        return
    cb = _CB(comp)
    t = comp.op('detect')
    t.cook(force=True)
    a = t.numpyArray(delayed=False)
    if a is None:
        return
    h, w = int(a.shape[0]), int(a.shape[1])
    import td
    fid = int(td.absTime.frame)
    if c.submit(cb.KIND_LANDMARKS, fid, time.monotonic(), w, h, cb.bgra_bytes(a), cb.FL_BOTTOM_UP):
        s['sent'][fid] = time.perf_counter()


def _cook_outputs(comp):
    for n in ('pts', 'ctl', 'polys', 'segs', 'fbox', 'frange'):
        o = comp.op(n)
        if o is not None:
            o.cook(force=True)


def _report(comp, s):
    p = comp.par
    lat = sorted(s['lat'])
    cms = sorted(s['comp'])
    now = time.perf_counter()
    rate = len([t for t in s['ans_t'] if now - t <= 2.0]) / 2.0
    n = sum(1 for sl in s['slots'] if sl and sl['present'] > 0)
    med = lat[len(lat) // 2] if lat else 0.0
    rows = [('key', 'value'), ('status', s['status']), ('backend', 'apple vision (jzb_vision_bridge, kind 5)'),
            ('helper_pid', helper_pid(comp) or ''), ('facecount', n),
            ('latency_ms_median', round(med, 1)), ('latency_ms_p95', round(lat[int(len(lat) * 0.95)], 1) if lat else ''),
            ('compute_ms_median', round(cms[len(cms) // 2], 1) if cms else ''), ('answers_per_s', rate),
            ('answers', s['answers']), ('restarts', s['restarts']),
            ('python_ms_per_frame_median', round(sorted(s['py_ms'])[len(s['py_ms']) // 2], 2) if s['py_ms'] else ''),
            ('last_error', (s['client'].last_error if (s['client'] is not None and not s['client'].connected()) else ''))]
    info = comp.op('info')
    if info is not None:
        info.clear()
        for r in rows:
            info.appendRow([str(v) for v in r])
    for name, v in (('Facecount', n), ('Latency', round(med, 1)), ('Status', s['status'])):
        par = getattr(p, name, None)
        if par is not None and par.eval() != v:
            par.val = v


def calibrate(comp):
    """Rest pose (eyes open, mouth closed): Eyeopen = mean raw eye ratio of face 1, Eyeclosed = 40 % of it."""
    s = _st(comp)
    sl = s['slots'][0] if s['slots'] else None
    if not sl:
        return False
    m = _L(comp).measures(sl['face'], s['aspect'])
    e = (m['eye_l_raw'] + m['eye_r_raw']) / 2.0
    if e <= 0:
        return False
    comp.par.Eyeopen = round(e, 4)
    comp.par.Eyeclosed = round(0.4 * e, 4)
    comp.par.Mouthrest = round(m['mouth_raw'], 4)
    return True


# ------------------------------------------------------------------------------------------------ Script CHOPs
def _slots(comp):
    s = _st(comp)
    n = int(comp.par.Maxfaces.eval())
    sl = list(s['slots'] or [])
    return (sl + [None] * n)[:n], n, s


def cook_pts(comp, sop):
    L = _L(comp)
    slots, n, s = _slots(comp)
    counts = s['counts'] or L.DEFAULT_COUNTS
    vals = L.point_values(slots, n, counts)
    sop.clear()
    sop.numSamples = 1
    for name in L.point_channels(n, counts):
        sop.appendChan(name)[0] = vals[name]


def cook_ctl(comp, sop):
    L = _L(comp)
    slots, n, s = _slots(comp)
    p = comp.par
    vals = L.control_values(slots, n, s['aspect'], p.Rollunit.eval(), eyeclosed=float(p.Eyeclosed.eval()),
                            eyeopen=float(p.Eyeopen.eval()), mouthmax=float(p.Mouthmax.eval()),
                            mouthrest=float(p.Mouthrest.eval()))
    sop.clear()
    sop.numSamples = 1
    sop.appendChan('facecount')[0] = vals['facecount']
    for i in range(n):
        for c in L.CTL_NAMES:
            k = 'f{}_{}'.format(i + 1, c)
            sop.appendChan(k)[0] = vals[k]


def _fill(sop, names, cols):
    sop.clear()
    sop.numSamples = len(cols[0])
    for name, col in zip(names, cols):
        sop.appendChan(name).vals = col


def cook_polys(comp, sop):
    L = _L(comp)
    slots, n, s = _slots(comp)
    p = comp.par
    grow_amt = float(p.Maskgrow.eval()) / 1000.0
    polys = L.mask_polygons(slots, s['aspect'], grow_amt, float(p.Eyeexpand.eval()), float(p.Mouthexpand.eval()),
                            float(p.Forehead.eval()))
    _fill(sop, ('x', 'v', 'id', 'kind'), L.poly_samples(polys))


def _wire(comp):
    L = _L(comp)
    slots, n, s = _slots(comp)
    p = comp.par
    return L.wire_segments(slots, bool(p.Showwire.eval()), bool(p.Showboxes.eval()))


def cook_segs(comp, sop):
    segs, _f = _wire(comp)
    _fill(sop, ('x0', 'v0', 'x1', 'v1'), [list(c) for c in zip(*segs)])


def cook_fbox(comp, sop):
    _s, faces = _wire(comp)
    _fill(sop, ('minx', 'minv', 'maxx', 'maxv'), [[f[k] for f in faces] for k in (2, 3, 4, 5)])


def cook_frange(comp, sop):
    _s, faces = _wire(comp)
    _fill(sop, ('start', 'count', 'present', 'pad'), [[f[0] for f in faces], [f[1] for f in faces],
                                                       [f[6] for f in faces], [0.0 for f in faces]])
