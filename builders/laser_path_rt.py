# laser_path_rt - TD runtime for LP_laser_path (copied into the COMP's `lp_rt` Text DAT; logic in `lp_logic`).
# Called by the Script ops: rows (source -> point rows), native_in (ordered rows for the Laser CHOP), own (Own
# engine stream), native_fix (Laser CHOP stream -> x y r g b i flag), drive (intensity / strobe / blackout / hold),
# preview_pts (galvo lag + dwell brightness -> instance channels), stats (Script DAT); and the Parameter Execute
# (Savesnap). T-74: no TOP pixel readback anywhere. T-67: state lives in this module's dict S, never op storage.
# ASCII only.
import json
import os
import time

import numpy as np

S = {'rows': [], 'own': None, 'own_ms': 0.0, 'rows_ms': 0.0, 'preview_ms': 0.0, 'drive_hold': None,
     'native_in_n': 0, 'err': ''}
SNAP_DIR = '~/Documents/StageLab_PrismFest/jazib-td-mcp/output/laser'


def C():
    return me.parent()


def L():
    return C().op('lp_logic').module


def pv(name, d=None):
    p = getattr(C().par, name, None)
    return d if p is None else p.eval()


def params():
    """COMP pars -> logic params dict (reading them inside a cook makes the cook depend on them)."""
    c = C()
    warp = None
    if pv('Warp', False):
        t = c.op('warptable')
        try:
            warp = [(float(t[r, 'x']), float(t[r, 'y'])) for r in range(1, 10)]
        except Exception:
            warp = None
    return L().params(
        pps=float(pv('Pps', 30000)), fps=float(pv('Fps', 60)), stepsize=float(pv('Stepsize', 0.02)),
        bstepsize=float(pv('Bstepsize', 0.1)), minhold=float(pv('Minhold', 0.1)), maxhold=float(pv('Maxhold', 0.3)),
        holdadd=int(pv('Holdadd', 0)), closedoverlap=float(pv('Closedoverlap', 0)), order=pv('Order', 'none'),
        startpoint=pv('Startpoint', 'centre'), preblankon=float(pv('Preblankon', 0)),
        postblankon=float(pv('Postblankon', 0.1)), preblankoff=float(pv('Preblankoff', 0.1)),
        postblankoff=float(pv('Postblankoff', 0)), colordelay=float(pv('Colordelay', 0)),
        interpcolors=bool(pv('Interpcolors', True)), overflow=pv('Overflow', 'frames'),
        cornertol=float(pv('Cornertol', 25)), orderms=float(pv('Orderms', 3)), scalex=float(pv('Scalex', 1)),
        scaley=float(pv('Scaley', 1)), rotate=float(pv('Rotate', 0)), offx=float(pv('Offsetx', 0)),
        offy=float(pv('Offsety', 0)), flipx=bool(pv('Flipx', False)), flipy=bool(pv('Flipy', False)),
        swap=bool(pv('Swap', False)), warp=warp,
        rgb=(float(pv('Rgbr', 1)), float(pv('Rgbg', 1)), float(pv('Rgbb', 1))), intensity=float(pv('Intensity', 1)),
        gain=float(pv('Gain', 1)))


# ---------------------------------------------------------------- sources -> rows (x y r g b id corner)
def _sop_rows(sop, closed_hint=True):
    rows = []
    if sop is None:
        return rows
    sid = 0
    for pr in sop.prims:
        vs = [v.point for v in pr]
        if not vs:
            continue
        col = (1.0, 1.0, 1.0)
        for v in vs:
            try:
                cd = v.Cd
                c3 = (float(cd[0]), float(cd[1]), float(cd[2]))
            except Exception:
                c3 = col
            rows.append((float(v.P[0]), float(v.P[1]), c3[0], c3[1], c3[2], sid, -1.0))
        cl = getattr(pr, 'closed', None)
        closed = bool(cl() if callable(cl) else (cl if cl is not None else closed_hint))
        if closed and len(vs) > 2:
            rows.append(rows[-len(vs)])
        sid += 1
    return rows


def _chop_rows(ch):
    if ch is None or ch.numSamples == 0 or ch['x'] is None or ch['y'] is None:
        return []
    n = ch.numSamples
    get = lambda nm, d: ch[nm].vals if ch[nm] is not None else [d] * n
    x, y = ch['x'].vals, ch['y'].vals
    r, g, b = get('r', 1.0), get('g', 1.0), get('b', 1.0)
    sid = get('id', None)
    cor = get('lascorner', -1.0)
    if ch['id'] is None:
        sid = list(range(n))               # Laser CHOP rule: no id = every point separate
    return [(x[k], y[k], r[k], g[k], b[k], sid[k], cor[k]) for k in range(n)]


def _first(ch, names):
    for nm in names:
        if ch[nm] is not None:
            return ch[nm].vals
    return None


def _pop_rows(ch):
    """POP to CHOP output (one sample per point): P -> x y, Color -> r g b; points form one open path in order."""
    if ch is None or ch.numSamples == 0:
        return []
    x = _first(ch, ('P(0)', 'P0', 'Px', 'P_x', 'tx', 'x'))
    y = _first(ch, ('P(1)', 'P1', 'Py', 'P_y', 'ty', 'y'))
    if x is None or y is None:
        return []
    n = ch.numSamples
    r = _first(ch, ('Color(0)', 'Color0', 'Colorr', 'r')) or [1.0] * n
    g = _first(ch, ('Color(1)', 'Color1', 'Colorg', 'g')) or [1.0] * n
    b = _first(ch, ('Color(2)', 'Color2', 'Colorb', 'b')) or [1.0] * n
    return [(x[k], y[k], r[k], g[k], b[k], 0, -1.0) for k in range(n)]


def _audio_rows(ch):
    """Audio scope: first channel = x, second = y (mono: x = time sweep), one open shape."""
    if ch is None or ch.numChans == 0 or ch.numSamples < 2:
        return []
    a = np.asarray(ch[0].vals, float)
    bb = np.asarray(ch[1].vals, float) if ch.numChans > 1 else None
    if bb is None:
        x = np.linspace(-1, 1, len(a))
        y = a
    else:
        x, y = a, bb
    step = max(1, len(x) // 400)
    return [(float(x[k]), float(y[k]), 1.0, 1.0, 1.0, 0, 0.0) for k in range(0, len(x), step)]


def _norm_rows(rows, fit):
    """Fit SOP/trace coordinates into [-1, 1] (aspect kept) when the source is not already laser space."""
    if not rows or not fit:
        return rows
    a = np.asarray([r[:2] for r in rows], float)
    lo, hi = a.min(0), a.max(0)
    c = (lo + hi) / 2
    s = max(float((hi - lo).max()) / 2, 1e-9)
    return [((r[0] - c[0]) / s, (r[1] - c[1]) / s) + tuple(r[2:]) for r in rows]


def source_rows():
    c = C()
    src = pv('Source', 'pattern')
    Lg = L()
    if src == 'pattern':
        pat = pv('Pattern', 'square')               # read absTime only for the animated pattern: reading it makes
        t = absTime.seconds if pat == 'calib' else 0.0   # the Script CHOP time-dependent (cooks every frame, live 26 Oct)
        return Lg.pattern_rows(pat, int(pv('Count', 8)), float(pv('Size', 0.8)), t=t)
    if src == 'sop':
        s = pv('Sop') or c.op('in1')
        return _norm_rows(_sop_rows(s), bool(pv('Fitsource', True)))
    if src == 'chop':
        return _chop_rows(pv('Chop') or c.op('in2'))
    if src == 'pop':
        return _norm_rows(_pop_rows(c.op('pop_chop')), bool(pv('Fitsource', True)))
    if src == 'toptrace':
        return _norm_rows(_sop_rows(c.op('trace')), True)
    if src == 'text':
        return _norm_rows(_sop_rows(c.op('text_sop')), True)
    if src == 'audio':
        return _audio_rows(pv('Audiochop'))
    return []


def _out(scriptOp, chans, rate):
    scriptOp.clear()
    scriptOp.isTimeSlice = False            # one whole image per cook, not a per-frame slice
    n = len(next(iter(chans.values()))) if chans else 0
    scriptOp.numSamples = max(1, n)
    scriptOp.rate = rate
    for nm, v in chans.items():
        ch = scriptOp.appendChan(nm)
        if n:                               # float64 -> float32 once (CHOP samples are float32): same as .vals = list
            ch.copyNumpyArray(np.asarray(v, dtype=np.float64).astype(np.float32))


def _arr(ch, nm, d, n):
    """Channel nm of CHOP ch as float64 numpy (perf lane 2: the channel array, not a .vals list), or n x d if absent."""
    c = ch[nm]
    return np.asarray(c.numpyArray(), dtype=np.float64) if c is not None else np.full(n, d, dtype=np.float64)


def cook_rows(scriptOp):
    t0 = time.perf_counter()
    try:
        rows = source_rows()
        S['err'] = ''
    except Exception as e:                  # a broken source shows in stats, the stream stays empty
        rows = []
        S['err'] = 'source: %s' % e
    S['rows'] = rows
    if not rows:
        scriptOp.clear()                    # no channels = no rows (downstream reads i['x'] is None)
    else:
        _out(scriptOp, dict(zip(['x', 'y', 'r', 'g', 'b', 'id', 'lascorner'], list(zip(*rows)))), 60)
    S['rows_ms'] = (time.perf_counter() - t0) * 1000


def _rows_from_input(scriptOp):
    """Rows from the wired `rows` CHOP's channels (a module reload never loses them). No x channel = no rows."""
    i = scriptOp.inputs[0] if scriptOp.inputs else None
    if i is None or i['x'] is None or i.numSamples < 1:
        return []
    cols = [i[nm].vals if i[nm] is not None else [d] * i.numSamples
            for nm, d in (('x', 0.0), ('y', 0.0), ('r', 1.0), ('g', 1.0), ('b', 1.0), ('id', 0.0), ('lascorner', -1.0))]
    return list(zip(*cols))


# ---------------------------------------------------------------- engines
def cook_native_in(scriptOp):
    """Rows -> shapes -> transform + tint -> draw order -> rows for the Laser CHOP (ids renumbered in draw order,
    lascorner 1 on corner vertices, closed shapes repeat their first point)."""
    Lg = L()
    rows = _rows_from_input(scriptOp)
    p = params()
    sh = Lg.build_shapes(rows, p['cornertol'])
    sh = Lg.apply_xform(sh, p['scalex'], p['scaley'], p['rotate'], p['offx'], p['offy'], p['flipx'], p['flipy'],
                        p['swap'], p['warp'])
    tint = np.asarray(p['rgb']) * p['gain'] * p['intensity']
    start = (0.0, 0.0) if p['startpoint'] == 'centre' else (tuple(Lg.shape_entry(sh[0])) if sh else (0.0, 0.0))
    sh, _, _ = Lg.order_shapes(sh, p['order'], start, p['orderms'])
    out = {k: [] for k in ('x', 'y', 'r', 'g', 'b', 'id', 'lascorner')}
    for k, s in enumerate(sh):
        idx = list(range(len(s['pts']))) + ([0] if s['closed'] else [])
        for j in idx:
            out['x'].append(s['pts'][j][0])
            out['y'].append(s['pts'][j][1])
            for ci, cn in enumerate('rgb'):
                out[cn].append(s['col'][j][ci] * tint[ci])
            out['id'].append(k)
            out['lascorner'].append(1.0 if s['corner'][j] else 0.0)
    S['native_in_n'] = len(out['x'])
    _out(scriptOp, out, 60)


def cook_own(scriptOp):
    t0 = time.perf_counter()
    p = params()
    r = L().run_engine(_rows_from_input(scriptOp), p)
    S['own'] = r
    _out(scriptOp, {k: r[k] for k in ('x', 'y', 'r', 'g', 'b', 'i', 'flag')}, p['pps'])
    S['own_ms'] = (time.perf_counter() - t0) * 1000


def cook_native_fix(scriptOp):
    """Laser CHOP output -> x y r g b i flag (flag = its debug channel when present)."""
    i = scriptOp.inputs[0] if scriptOp.inputs else None
    chans = {}
    if i is not None and i.numSamples:
        n = i.numSamples
        for nm in ('x', 'y', 'r', 'g', 'b'):
            chans[nm] = _arr(i, nm, 0.0, n)
        chans['i'] = _arr(i, 'i', 0.0, n) if i['i'] is not None else (
            ((chans['r'] + chans['g']) + chans['b']) > 1e-6).astype(np.float64)
        dbg = None
        for nm in ('debug', 'flag', 'debugchan'):
            if i[nm] is not None:
                dbg = _arr(i, nm, 0.0, n)
        chans['flag'] = dbg if dbg is not None else np.zeros(n)
    _out(scriptOp, chans, float(pv('Pps', 30000)))


# ---------------------------------------------------------------- drive
def drive_animated():
    return (pv('Intensitysrc', 'manual') != 'manual' or pv('Strobe', 'off') in ('bpm', 'audio')
            or (pv('Source', 'pattern') == 'pattern' and pv('Pattern', '') == 'calib'))


def _audio_level():
    a = pv('Audioch')
    if a is None or a.numChans == 0:
        return 0.0
    v = np.abs(np.asarray(a[0].vals, float))
    return float(v.max()) if len(v) else 0.0


def cook_drive(scriptOp):
    i = scriptOp.inputs[0] if scriptOp.inputs else None
    if i is None or i.numSamples == 0:
        scriptOp.clear()
        return
    if pv('Hold', False) and S['drive_hold'] is not None:
        _out(scriptOp, S['drive_hold'], float(pv('Pps', 30000)))
        return
    Lg = L()
    t = absTime.seconds if drive_animated() else 0.0   # static drive must not depend on time (cook every frame)
    src = pv('Intensitysrc', 'manual')
    aud = _audio_level() if (src == 'audio' or pv('Strobe', 'off') == 'audio') else 0.0
    dc = pv('Drivechop')
    chopv = float(dc[0][0]) if (dc is not None and dc.numChans) else 1.0
    lvl = Lg.drive_level(src, t, 1.0, float(pv('Bpm', 120)), float(pv('Beatdiv', 1)), aud,
                         float(pv('Audioamt', 1)), chopv)
    st = pv('Strobe', 'off')
    gate = (1.0 if pv('Strobeon', False) else 0.0) if st == 'manual' else Lg.strobe_gate(
        st, t, float(pv('Bpm', 120)), float(pv('Beatdiv', 1)), aud)
    k = lvl * gate * (0.0 if pv('Blackout', False) else 1.0)
    chans = {}
    n = i.numSamples
    for nm in ('x', 'y', 'flag'):
        chans[nm] = _arr(i, nm, 0.0, n)
    for nm in ('r', 'g', 'b', 'i'):
        v = _arr(i, nm, 1.0, n)
        chans[nm] = v * k if k != 1.0 else v
    order = {nm: chans[nm] for nm in ('x', 'y', 'r', 'g', 'b', 'i', 'flag')}
    S['drive_hold'] = order
    S['drive_level'] = k
    _out(scriptOp, order, float(pv('Pps', 30000)))


# ---------------------------------------------------------------- preview
def cook_preview_pts(scriptOp):
    """Laser stream -> instance channels tx ty r g b (colour x dwell weight x Spotgain). Showlag: xy through the
    galvo model, colour unfiltered (tails / overshoot appear). Image longer than one frame: only this frame's
    window is drawn (flicker visible). Showblank: blanked travel drawn dim grey."""
    t0 = time.perf_counter()
    i = scriptOp.inputs[0] if scriptOp.inputs else None
    Lg = L()
    if i is None or i.numSamples < 1 or i['x'] is None:
        _out(scriptOp, {'tx': [9.0], 'ty': [9.0], 'r': [0.0], 'g': [0.0], 'b': [0.0]}, 60)
        return
    n = i.numSamples
    x = _arr(i, 'x', 0.0, n)
    y = _arr(i, 'y', 0.0, n)
    rgb = np.stack([_arr(i, c, 1.0, n) for c in 'rgb'], 1)
    pps, fps = float(pv('Pps', 30000)), float(pv('Fps', 60))
    if pv('Showlag', False):
        x, y = Lg.galvo_filter(x, y, pps, float(pv('Galvobw', 6000)), float(pv('Galvozeta', 0.7)))
    w = Lg.dwell_weights(x, y, float(pv('Stepsize', 0.02)))
    col = rgb * (w * float(pv('Spotgain', 1)))[:, None]
    if pv('Showblank', False):
        dark = rgb.sum(1) < 1e-6
        col[dark] = 0.06
    n = len(x)
    budget = Lg.frame_budget(pps, fps)
    if n > budget:                                     # several frames per image: this frame's samples only
        idx = Lg.frame_window(n, budget, absTime.frame)
        x, y, col = x[idx], y[idx], col[idx]
    S['preview_ms'] = (time.perf_counter() - t0) * 1000
    _out(scriptOp, {'tx': x, 'ty': y, 'r': col[:, 0], 'g': col[:, 1], 'b': col[:, 2]}, 60)


def preview_animated():
    """The preview must cook every frame when the image needs more than one frame (window moves)."""
    try:
        n = C().op('laser').numSamples
        return n > L().frame_budget(float(pv('Pps', 30000)), float(pv('Fps', 60)))
    except Exception:
        return False


def decay_factor():
    """Per-frame persistence multiplier from the half life in ms and the frame time."""
    hl = float(pv('Persist', 60))
    if hl <= 0:
        return 0.0
    return 0.5 ** ((1000.0 / max(float(pv('Fps', 60)), 1.0)) / hl)


# ---------------------------------------------------------------- stats
def cook_stats(dat):
    Lg = L()
    eng = pv('Engine', 'native')
    lz = C().op('laser')
    pps, fps = float(pv('Pps', 30000)), float(pv('Fps', 60))
    if eng == 'own' and S['own'] is not None:
        st = dict(S['own']['stats'])
    else:
        st = {}
        if lz is not None and lz.numSamples and lz['x'] is not None:
            f = lz['flag'].vals if lz['flag'] is not None else None
            st = Lg.stream_stats(lz['x'].vals, lz['y'].vals, lz['r'].vals, lz['g'].vals, lz['b'].vals, f, pps, fps)
            st['native_in_points'] = S['native_in_n']
            st.pop('flag_counts', None)
            if f is not None:
                st['corner_runs'] = Lg.count_runs(f, 1)
                st['blank_runs'] = Lg.count_runs(f, 5)
    st['engine'] = eng
    st['laser_samples'] = lz.numSamples if lz is not None else 0
    st['own_ms'] = round(S['own_ms'], 3)
    st['rows_ms'] = round(S['rows_ms'], 3)
    st['preview_ms'] = round(S['preview_ms'], 3)
    st['drive_level'] = round(S.get('drive_level', 1.0), 3)
    if S['err']:
        st['error'] = S['err']
    dat.clear()
    dat.appendRows(Lg.stats_rows(st))


# ---------------------------------------------------------------- pulses
def export_ilda():
    """Exportilda pulse: the current `laser` image -> output/laser/<COMP>.ild (ILDA format 5) + <COMP>_ilda.json
    (read-back and DAC-less packer checks, lp_logic.export_check). No device output. Returns the report."""
    c = C()
    L_ = c.op('laser')
    ch = dict((n, [float(v) for v in L_[n].vals]) if L_[n] is not None else (n, None) for n in 'xyrgbi')
    data, rep = L().export_check(ch['x'], ch['y'], ch['r'], ch['g'], ch['b'], ch['i'], name=c.name[:8])
    os.makedirs(SNAP_DIR, exist_ok=True)
    f = os.path.join(SNAP_DIR, '%s.ild' % c.name)
    with open(f, 'wb') as fh:
        fh.write(data)
    rep.update(file=f, engine=pv('Engine'), source=pv('Source'), pps=pv('Pps'), build=app.build,
               time=time.strftime('%Y-%m-%d %H:%M:%S'))
    with open(os.path.join(SNAP_DIR, '%s_ilda.json' % c.name), 'w') as fh:
        json.dump(rep, fh, indent=1, default=str)
    return rep


def savesnap():
    c = C()
    pars = {}
    for p in c.customPars:
        if p.style in ('Pulse', 'Momentary'):
            continue
        v = p.eval()
        pars[p.name] = v.path if hasattr(v, 'path') else v
    snap = {'comp': c.path, 'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'build': app.build, 'pars': pars,
            'rows': [list(r) for r in S['rows']]}
    os.makedirs(SNAP_DIR, exist_ok=True)
    f = os.path.join(SNAP_DIR, '%s.json' % c.name)
    with open(f, 'w') as fh:
        json.dump(snap, fh, indent=1, default=str)
    return f
