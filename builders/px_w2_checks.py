"""px_w2_checks: live checks for PX_pointfx wave 2 (docs/builds/px.md "Wave 2", LIVE CHECKS W2-*). Runs INSIDE TD:
    ns = dict(globals()); exec(open('<repo>/builders/px_w2_checks.py').read(), ns); ns['snap'](c, 'base_splat')
Reads happen only in run() callbacks frames after the exec that changed things (T-74 / T-76 / T-91: the read is
repeated and the second kept). Captures: numpy arrays of out1 (or any op) in output/px_w2/<name>.npy (+ .jpg).
Perf: px_checks.ab_start / ab_report (same-minute A/B, T-143 (9) / T-145). ASCII; no TD state in module globals.
"""
import os

REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
OUT = os.path.join(REPO, 'output', 'px_w2')
FILE = os.path.join(REPO, 'builders', 'px_w2_checks.py')


def setp(c, vals):
    """Set COMP pars once, only when they differ (T-164: never reset-then-set on a zkit COMP)."""
    out = []
    for k, v in vals.items():
        p = getattr(c.par, k, None)
        if p is None:
            out.append(k)
            continue
        if p.mode != ParMode.CONSTANT:
            p.mode = ParMode.CONSTANT
        try:
            if p.eval() != v:
                p.val = v
        except Exception:
            out.append(k)
    return out


def _pump_tick(path, top, k, n, name, sub):
    c = op(path)
    if c is None:
        return
    rt = c.op('px_rt')
    if rt is not None:
        try:
            rt.module.tick(c)
        except Exception:
            pass
    o = c.op(top) if top else c.op('out1')
    o.cook(force=True)
    if k >= n:
        if name:
            _save(o, name, sub)
        return
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_pump_tick'](%r, %r, %d, %d, %r, %r)"
        % (FILE, path, top, k + 1, n, name, sub), delayFrames=1, delayRef=op.TDResources)


def _save(o, name, sub=''):
    import numpy as np
    d = os.path.join(OUT, sub) if sub else OUT
    os.makedirs(d, exist_ok=True)
    a = o.numpyArray(delayed=False)
    np.save(os.path.join(d, name + '.npy'), np.array(a, dtype=np.float32))
    try:
        o.save(os.path.join(d, name + '.jpg'))
    except Exception:
        pass


def snap(c, name, frames=40, top='out1', sub=''):
    """Pull `top` once per frame for `frames` frames, then save it (numpy + jpg). Returns the npy path."""
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_pump_tick'](%r, %r, 0, %d, %r, %r)"
        % (FILE, c.path, top, int(frames), name, sub), delayFrames=1, delayRef=op.TDResources)
    return os.path.join(OUT, sub, name + '.npy')


def pump(c, frames=60, top='out1'):
    return snap(c, '', frames, top)


def diff(a, b, sub=''):
    """Max abs diff / count of differing values between two saved captures."""
    import numpy as np
    d = os.path.join(OUT, sub) if sub else OUT
    x = np.load(os.path.join(d, a + '.npy'))
    y = np.load(os.path.join(d, b + '.npy'))
    if x.shape != y.shape:
        return {'shape': [list(x.shape), list(y.shape)]}
    e = np.abs(x.astype(np.float64) - y.astype(np.float64))
    return {'max': float(e.max()), 'n_diff': int((e > 0).sum()), 'mean_a': float(x.mean()), 'mean_b': float(y.mean()),
            'shape': list(x.shape)}


def stats(name, sub=''):
    import numpy as np
    d = os.path.join(OUT, sub) if sub else OUT
    x = np.load(os.path.join(d, name + '.npy')).astype(np.float64)
    return {'mean': [round(float(v), 5) for v in x.reshape(-1, x.shape[-1]).mean(0)], 'max': float(x.max()),
            'nan': int(np.isnan(x).sum())}


def errors(c):
    """Ops with errors (COMP level + children, sorter included)."""
    out = {}
    for o in [c] + c.findChildren(maxDepth=2):
        try:
            e = o.errors()
        except Exception:
            e = ''
        if e:
            out[o.path.replace(c.path + '/', '')] = e[:160]
    return out


def tex(c, top, sub='tex'):
    """Save a texture (state / look / haze) for a reference check, frames later (run)."""
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_save'](op(%r), %r, %r)"
        % (FILE, c.op(top).path, top.replace('/', '_'), sub), delayFrames=3, delayRef=op.TDResources)
    return os.path.join(OUT, sub, top.replace('/', '_') + '.npy')


# ---- W2-1: modules on the shared list (/project1/effectors) -----------------------------------------------------------
PXC = os.path.join(REPO, 'builders', 'px_checks.py')


def _pxc():
    ns = dict(globals())
    exec(open(PXC).read(), ns)
    return ns


def eff_texels():
    o = op('/project1/effectors/eff_rows')
    cols = [list(o[n].vals) for n in ('x', 'y', 'z', 'w')]
    return [(cols[0][i], cols[1][i], cols[2][i], cols[3][i]) for i in range(len(cols[0]))]


def shared_setup(c, sel='box1', R=0.3, k=1.0, shape='linear', move=None):
    """Plane of points (px_checks.v2_setup 'box' scene) + ONE prox_push (displace, outward, rest, strength 0.2)
    whose effectors text is a SHARED selection; the own E1 stays unlinked. move = {effector: {tx..}} on the list."""
    X = _pxc()
    r = X['v2_setup'](c, 'box', R=R, k=k, shape=shape)
    c.par.M1effectors = sel
    for nm, xf in (move or {}).items():
        o = op('/project1/effectors/' + nm)
        for kk, v in xf.items():
            getattr(o.par, kk).val = v
    X['pump'](c, 40)
    return r


def shared_check(c, sel='box1', R=0.3, k=1.0, shape=1):
    """GPU weight |P - p0| / 0.2 vs the float64 reference: module falloff (R, k, shape) on each selected shared row's
    signed distance (effectors_logic.read_row + px_logic.ref_sd_shape), x the row gain, max-combined."""
    import numpy as np
    X = _pxc()
    Lg = c.op('px_logic').module
    el = op('/project1/effectors/eff_rt').module.L()
    rows_ = op('/project1/effectors/eff_rt').module.rows()
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    src = X['unpack'](c.op('source').numpyArray(delayed=False), 4, side, n)
    st = X['unpack'](c.op('update').numpyArray(delayed=False), 5, side, n)
    p0 = src[:, 0, :3]
    wg = np.linalg.norm(st[:, 0, :3] - p0, axis=1) / 0.2
    tex = eff_texels()
    idx = el.selected(rows_, sel)
    wr = np.zeros(n)
    for i in idx:
        r = el.read_row(tex, i)
        if r[6][3] < 0.5:
            continue
        M = np.array([r[0], r[1], r[2]], dtype=np.float64)
        q = p0 @ M[:, :3].T + M[:, 3]
        sd = Lg.ref_sd_shape(int(round(r[3][0])), q, np.asarray(r[3][1:], dtype=np.float64)) * r[4][3]
        wr = np.maximum(wr, Lg.ref_fall(sd, R, k, shape) * r[7][3])
    e = np.abs(wg - wr)
    m1 = c.op('eng_m')
    return {'sel': sel, 'rows': idx, 'n': n, 'n_w': int((wr > 1e-3).sum()), 'w_gpu_mean': round(float(wg.mean()), 6),
            'w_ref_mean': round(float(wr.mean()), 6), 'maxerr': float(e.max()), 'p99': float(np.percentile(e, 99)),
            'hdr': [[round(float(m1[ch][j]), 3) for ch in 'xyzw'] for j in range(3)], 'nan': int(np.isnan(st).sum())}


# ---- W2-2: light module (relight by the light effectors) -------------------------------------------------------------
def light_setup(c, values=None, lights=None, splat=False):
    """Plane of points (or the SmileyPinata splat scene with splat=True) + ONE light module; lights = [(name, type,
    pos, colour, intensity, extra light values)] made in /project1/effectors (tag pxchk; earlier pxchk lights removed)."""
    X = _pxc()
    ert = op('/project1/effectors/eff_rt').module
    for r in list(ert.rows()):
        if 'pxchk' in str(r.get('tags', '')).split():
            ert.remove(r['name'])
    if splat:
        X['splat_core'](c)
    else:
        X['reset_pages'](c)
        core = dict(X['CORE_DEFAULTS'])
        core.update({'Agen': 'plane', 'Agenp': 1.0, 'Acolmode': 'solid', 'Bright': 1.0})
        X['set_core'](c, core)
    for nm, ty, pos, col, it, extra in (lights or [('pxl1', 'point', (0.0, 1.0, 0.0), (1.0, 0.8, 0.6), 2.0, {})]):
        v = {'type': ty, 'colour': col, 'intensity': it}
        v.update(extra)
        name = ert.add('light', nm, tags='pxchk', **v)
        o = op('/project1/effectors/' + name)
        for kk, x in zip(('tx', 'ty', 'tz'), pos):
            getattr(o.par, kk).val = x
        for kk, x in extra.get('xf', {}).items():
            getattr(o.par, kk).val = x
    Lg = c.op('px_logic').module
    vals = dict(Lg.instance_defaults(Lg.new_instance('light', 1)))      # full state (T-124 (1): a reused uid keeps values)
    vals.pop('drive', None)
    vals['effectors'] = '#pxchk'
    vals.update(values or {})
    st = X['set_stack'](c, [('light', vals, None)])
    c.op('px_rt').module.load(c)
    X['reset'](c)
    X['pump'](c, 40)
    return {'stack': st, 'lights': [r['name'] for r in ert.rows() if 'pxchk' in str(r.get('tags', ''))]}


def light_check(c, nprobe=4096, seed=1):
    """Look rgb vs px_logic.ref_light_module at nprobe random points (float64; light blocks read back from eff_rows,
    the same data the GPU used). Points without splat scale: model per the module (auto = glow by distance); splats:
    normal = effectors_logic.splat_normal(state q, rest scale, view)."""
    import numpy as np
    X = _pxc()
    Lg = c.op('px_logic').module
    ert = op('/project1/effectors/eff_rt').module
    el = ert.L()
    rt = c.op('px_rt').module
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    src = X['unpack'](c.op('source').numpyArray(delayed=False), 4, side, n)
    st = X['unpack'](c.op('update').numpyArray(delayed=False), 5, side, n)
    lk = X['unpack'](c.op('look').numpyArray(delayed=False), 3, side, n)
    tex = eff_texels()
    sel_rows = set(el.selected(ert.rows(), '#pxchk'))
    blocks = [el.read_light(tex, k) for k in range(el.light_count(tex))]
    blocks = [b for b in blocks if int(round(b[2][3])) in sel_rows]
    inst = rt.stack(c)[0]
    flat = rt.flat_module_values(c, [inst])
    vals = Lg.instance_values(inst, flat)
    g = [[float(c.op('eng_g')[ch][i]) for ch in 'xyzw'] for i in range(24)]
    campos = g[8][:3]
    bright = g[10][3]
    rng = np.random.default_rng(seed)
    ids = rng.choice(n, size=min(nprobe, n), replace=False)
    pm = c.op('px_palmap').module
    pal = (pm.colsrc_eval, rt.S(c).get('pal_rows'), [float(c.op('eng_palc')[ch][0]) for ch in 'xyzw'])
    err = []
    nm = vals.get('normal', 'auto')
    for i in ids:
        P = st[i, 0, :3]
        col = src[i, 1, :3]
        sc = src[i, 2, :3]
        v = np.asarray(campos) - P
        v = v / max(np.linalg.norm(v), 1e-12)
        has_s = sc.max() > 0
        if nm == 'up':
            nrm = [0.0, 1.0, 0.0]
        elif nm == 'view':
            nrm = list(v)
        elif (nm == 'auto' and has_s) or nm == 'splat':
            nrm = list(el.splat_normal(st[i, 4, :4], sc, v)) if has_s else list(v)
        else:
            nrm = None
        ref = np.asarray(Lg.ref_light_module(col, P, nrm, campos, blocks, vals, pal)) * bright
        err.append(np.abs(lk[i, 0, :3] - np.maximum(ref, 0)).max())
    err = np.asarray(err)
    return {'n_lights': len(blocks), 'probes': len(ids), 'maxerr': float(err.max()), 'p99': float(np.percentile(err, 99)),
            'look_mean': [round(float(x), 4) for x in lk[:, 0, :3].mean(0)], 'nan': int(np.isnan(lk).sum())}


# ---- W2-3: shared palette (Palette page) ------------------------------------------------------------------------------
def pal_setup(c, mods, core=None):
    """Plane of points (position colours) + mods = [(type, values)] (full module defaults first)."""
    X = _pxc()
    Lg = c.op('px_logic').module
    X['reset_pages'](c, ('Source', 'Sim', 'Look', 'Grade', 'Palette'))
    cc = dict(X['CORE_DEFAULTS'])
    cc.update({'Agen': 'plane', 'Agenp': 1.0, 'Acolmode': 'position', 'Bright': 1.0})
    cc.update(core or {})
    X['set_core'](c, cc)
    st = []
    for t, v in mods:
        d = dict(Lg.instance_defaults(Lg.new_instance(t, 1)))
        d.pop('drive', None)
        d.update(v)
        st.append((t, d, None))
    r = X['set_stack'](c, st)
    c.op('px_rt').module.load(c)
    X['reset'](c)
    X['pump'](c, 40)
    return r


def pal_check_ramp(c, attr='height', lo=-1.0, hi=1.0, nprobe=4096):
    """colour_ramp ramp=palette (replace, G 1): look rgb = pal_eval(uPal rows, uPalCtl, x) x Bright, x = (a - lo) / (hi -
    lo) clamped; a = P.y (height) or the luma of the source colour (luma)."""
    import numpy as np
    X = _pxc()
    rt = c.op('px_rt').module
    pm = c.op('px_palmap').module
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    src = X['unpack'](c.op('source').numpyArray(delayed=False), 4, side, n)
    st = X['unpack'](c.op('update').numpyArray(delayed=False), 5, side, n)
    lk = X['unpack'](c.op('look').numpyArray(delayed=False), 3, side, n)
    rows = [[float(c.op('eng_pal')[ch][i]) for ch in 'xyzw'] for i in range(16)]
    ctl = [float(c.op('eng_palc')[ch][0]) for ch in 'xyzw']
    bright = float(c.op('eng_g')['w'][10])
    ids = np.random.default_rng(3).choice(n, size=min(nprobe, n), replace=False)
    err = []
    for i in ids:
        a = st[i, 0, 1] if attr == 'height' else float(src[i, 1, :3] @ np.array([0.2126, 0.7152, 0.0722]))
        x = min(max((a - lo) / (hi - lo), 0.0), 1.0)
        ref = np.asarray(pm.pal_eval(rows, ctl, x)) * bright
        err.append(np.abs(lk[i, 0, :3] - ref).max())
    err = np.asarray(err)
    return {'attr': attr, 'ctl': ctl, 'stops': int(ctl[0]), 'maxerr': float(err.max()), 'p99': float(np.percentile(err, 99)),
            'look_mean': [round(float(v), 4) for v in lk[:, 0, :3].mean(0)]}


# ---- W2-4: volumetric haze inside PX ----------------------------------------------------------------------------------
def haze_dump(c, tag='hz'):
    """Save the haze TOP, its input (haze_src) and the uniform rows the GPU used (eng_h, eng_hl, palette, uHt.x, cs)
    for the offline px_haze_logic.ref_haze comparison (run frames after the setup)."""
    import json
    rows = lambda n: [[float(c.op(n)[ch][i]) for ch in 'xyzw'] for i in range(c.op(n).numSamples)]
    hz = c.op('haze')
    k = next(i for i in range(int(hz.seq.vec.numBlocks)) if getattr(hz.par, 'vec%dname' % i).eval() == 'uHt')
    kc = next(i for i in range(int(hz.seq.vec.numBlocks)) if getattr(hz.par, 'vec%dname' % i).eval() == 'uHazeCs')
    meta = {'U': rows('eng_h'), 'L': rows('eng_hl'), 'pal': rows('eng_pal'), 'ctl': rows('eng_palc')[0],
            'time': float(getattr(hz.par, 'vec%dvaluex' % k).eval()),
            'cs': [float(getattr(hz.par, 'vec%dvalue%s' % (kc, a)).eval()) for a in 'xyzw']}
    os.makedirs(os.path.join(OUT, tag), exist_ok=True)
    with open(os.path.join(OUT, tag, 'meta.json'), 'w') as fh:
        json.dump(meta, fh)
    _save(c.op('haze'), 'haze', tag)
    _save(c.op('haze_src'), 'haze_src', tag)
    return meta['U'][10]


# ---- per-op cost inside a sub-COMP (PX_lines) while PX's out1 is pulled ------------------------------------------------
def _sub_tick(path, sub, k, n):
    c = op(path)
    s = c.op(sub)
    rt = c.op('px_rt')
    if rt is not None:
        rt.module.tick(c)
    c.op('out1').cook(force=True)
    rec = c.fetch('w2_sub', {}, search=False)
    last = rec.setdefault('tc', {})
    ops = rec.setdefault('ops', {})
    tot = 0.0
    for x in s.findChildren(maxDepth=1):
        try:
            tc = int(x.totalCooks)
            cooked = x.name in last and tc > last[x.name]
            last[x.name] = tc
            if not cooked:
                continue
            cpu, gpu = float(x.cpuCookTime), float(getattr(x, 'gpuCookTime', 0.0) or 0.0)
        except Exception:
            continue
        d = ops.setdefault(x.name, [[], []])
        d[0].append(cpu)
        d[1].append(gpu)
        tot += cpu + gpu
    if k > 5:
        rec.setdefault('tot', []).append(tot)
    c.store('w2_sub', rec)
    if k + 1 < n:
        run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_sub_tick'](%r, %r, %d, %d)" % (FILE, path, sub, k + 1, n),
            delayFrames=1, delayRef=op.TDResources)


def sub_perf(c, sub='PX_lines', n=120):
    c.store('w2_sub', {})
    _sub_tick(c.path, sub, 0, n)
    return n


def sub_report(c):
    rec = c.fetch('w2_sub', {}, search=False)
    med = lambda v: round(sorted(v)[len(v) // 2], 3) if v else None
    out = {'tot_ms_median': med(rec.get('tot', [])), 'frames': len(rec.get('tot', []))}
    for k, (a, b) in rec.get('ops', {}).items():
        if len(a) > 10:
            out[k] = [med(a), med(b), len(a)]
    return out


# ---- W2-7: the wave-2 looks -------------------------------------------------------------------------------------------
def look_cap(c, name, frames=150):
    """Recall a preset (Play on), then capture out1 `frames` frames later in output/px_w2/looks/."""
    setp(c, {'Play': True})
    c.op('px_rt').module.recall(c, name)
    slug = ''.join(ch if ch.isalnum() else '_' for ch in name)
    return snap(c, 'look_' + slug, frames, sub='looks')


def look_info(c):
    i = c.op('eng_info')
    return {'status': c.par.Status.eval(), 'info': dict((ch.name, float(ch[0])) for ch in i.chans()),
            'lights': c.par.Lightinfo.eval(), 'geo': c.par.Geocomps.eval(), 'lines': bool(c.par.Lineson.eval()),
            'haze': bool(c.par.Vhon.eval()), 'errors': errors(c)}


# ---- same-minute A/B of two PX COMPs (v2 vs wave 2 with everything new off): alternate which one cooks --------------
def _pair_tick(paths, k, n, rounds, settle):
    seg = k // n
    a = op(paths[0])
    rec = a.fetch('w2_pair', None, search=False)
    if rec is None:
        return
    if seg >= 2 * rounds:
        rec['done'] = True
        a.store('w2_pair', rec)
        return
    m = seg % 2
    c = op(paths[m])
    if k % n == 0:
        op(paths[1 - m]).allowCooking = False
        c.allowCooking = True
    rt = c.op('px_rt')
    if rt is not None:
        rt.module.tick(c)
    c.op('out1').cook(force=True)
    last = rec['tc'].setdefault(str(m), {})
    tot = 0.0
    ops = rec['ops'][m]
    for x in c.findChildren(maxDepth=1):
        try:
            tc = int(x.totalCooks)
            cooked = x.name in last and tc > last[x.name]
            last[x.name] = tc
            if not cooked or k % n < settle or x.isCOMP:
                continue
            cpu, gpu = float(x.cpuCookTime), float(getattr(x, 'gpuCookTime', 0.0) or 0.0)
        except Exception:
            continue
        d = ops.setdefault(x.name, [[], []])
        d[0].append(cpu)
        d[1].append(gpu)
        tot += cpu + gpu
    if k % n >= settle:
        rec['tot'][m].append(tot)
    a.store('w2_pair', rec)
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_pair_tick'](%r, %d, %d, %d, %d)"
        % (FILE, list(paths), k + 1, n, rounds, settle), delayFrames=1, delayRef=op.TDResources)


def pair_ab(path_a, path_b, n=40, rounds=3, settle=8):
    op(path_a).store('w2_pair', {'tc': {}, 'ops': [{}, {}], 'tot': [[], []], 'done': False})
    _pair_tick([path_a, path_b], 0, n, rounds, settle)
    return 2 * n * rounds


def pair_report(path_a, names=('update', 'look', 'srender', 'post', 'bloom', 'glow_in', 'eng_g', 'source', 'sort_keys')):
    rec = op(path_a).fetch('w2_pair', {}, search=False)
    med = lambda v: round(sorted(v)[len(v) // 2], 3) if v else None
    out = {'done': rec.get('done'), 'tot_ms': [med(rec['tot'][0]), med(rec['tot'][1])]}
    for nm in names:
        a, b = rec['ops'][0].get(nm), rec['ops'][1].get(nm)
        out[nm] = [[med(a[0]), med(a[1])] if a else None, [med(b[0]), med(b[1])] if b else None]
    return out


# ---- W3: packet glitch rigidity (SA18) --------------------------------------------------------------------------------
def packet_check(c, block=0.25):
    """Every point of a cell keeps its distance to the cell's first point (rigid packets); report moved cells and the
    max rotation seen in state q (splats rotate with the packet)."""
    import numpy as np
    X = _pxc()
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    src = X['unpack'](c.op('source').numpyArray(delayed=False), 4, side, n)
    st = X['unpack'](c.op('update').numpyArray(delayed=False), 5, side, n)
    p0 = src[:, 0, :3]
    P = st[:, 0, :3]
    cell = np.floor(p0.astype(np.float32) / np.float32(block)).astype(np.int64)     # float32 like the GPU
    _u, key = np.unique(cell, axis=0, return_inverse=True)                         # exact cell ids (a hash collided)
    key = key.reshape(-1)
    order = np.argsort(key, kind='stable')
    k = key[order]
    first = np.r_[0, np.nonzero(np.diff(k))[0] + 1]
    ref = np.repeat(order[first], np.diff(np.r_[first, len(k)]))
    d0 = np.linalg.norm(p0[order] - p0[ref], axis=1)
    d1 = np.linalg.norm(P[order] - P[ref], axis=1)
    moved = np.linalg.norm(P - p0, axis=1) > 1e-4
    qw = np.clip(np.abs(st[:, 4, 0]), 0, 1)
    e = np.abs(d1 - d0)
    return {'cells': int(len(first)), 'points_moved': int(moved.sum()), 'rigid_maxerr': float(e.max()),
            'n_err_gt_1e4': int((e > 1e-4).sum()), 'rigid_p999': float(np.percentile(e, 99.9)),
            'max_rot_deg': float(np.degrees(2 * np.arccos(qw.min()))), 'nan': int(np.isnan(st).sum())}


# ---- W3: dissolve fronts (SA19 / SA20) --------------------------------------------------------------------------------
def front_check(c, mode, rng, progress, soft, pitch=0.5):
    import numpy as np
    X = _pxc()
    Lg = c.op('px_logic').module
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    src = X['unpack'](c.op('source').numpyArray(delayed=False), 4, side, n)
    st = X['unpack'](c.op('update').numpyArray(delayed=False), 5, side, n)
    g = [[float(c.op('eng_g')[ch][i]) for ch in 'xyzw'] for i in range(24)]
    ref = Lg.ref_dissolve_front(src[:, 0, :3], g[7][:3], g[8][:3], mode, rng, progress, soft, pitch)
    e = np.abs(st[:, 3, 3] - ref)
    return {'mode': mode, 'dis_mean': round(float(st[:, 3, 3].mean()), 5), 'ref_mean': round(float(ref.mean()), 5),
            'maxerr': float(e.max()), 'n_gt_1e3': int((e > 1e-3).sum())}


# ---- W3: splat attributes (SA15) --------------------------------------------------------------------------------------
def attr_check(c, by='splatsize', lo=0.0, hi=1.0, soft=0.001):
    """mask_attr by a splat attribute -> m0 (state texel 3 .x) vs the numpy band of the rest scale / alpha."""
    import numpy as np
    X = _pxc()
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    src = X['unpack'](c.op('source').numpyArray(delayed=False), 4, side, n)
    st = X['unpack'](c.op('update').numpyArray(delayed=False), 5, side, n)
    sc = np.abs(src[:, 2, :3].astype(np.float64))
    if by == 'splatsize':
        a = np.cbrt(np.prod(sc, axis=1))
    elif by == 'flatness':
        mx = sc.max(1)
        a = np.where(mx > 0, sc.min(1) / np.maximum(mx, 1e-30), 1.0)
    else:
        a = src[:, 1, 3].astype(np.float64)
    ss = lambda e0, e1, x: (lambda t: t * t * (3 - 2 * t))(np.clip((x - e0) / (e1 - e0), 0, 1))
    w = ss(lo - soft, lo, a) * (1 - ss(hi, hi + soft, a))
    e = np.abs(st[:, 3, 0] - w)
    return {'by': by, 'attr_quartiles': [float(x) for x in np.percentile(a, [25, 50, 75])], 'm0_mean': float(st[:, 3, 0].mean()),
            'ref_mean': float(w.mean()), 'maxerr': float(e.max()), 'n_gt_1e3': int((e > 1e-3).sum())}


# ---- W3: actor echoes (SA31 / TC-37) ----------------------------------------------------------------------------------
def echo_check(c):
    """Static actor: echo copy k = actor P + (k + 1) x Echooffset (after enough shifts); report errors + counts."""
    import numpy as np
    X = _pxc()
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    g = [[float(c.op('eng_g')[ch][i]) for ch in 'xyzw'] for i in range(24)]
    ns, na, npool, ne = [int(round(x)) for x in g[21]]
    st = X['unpack'](c.op('update').numpyArray(delayed=False), 5, side, n)
    lk = X['unpack'](c.op('look').numpyArray(delayed=False), 3, side, n)
    off = np.array(g[23][:3])
    K = ne // max(na, 1)
    A = st[ns:ns + na, 0, :3]
    errs, alphas = [], []
    for k in range(K):
        E = st[ns + na + npool + k * na: ns + na + npool + (k + 1) * na, 0, :3]
        errs.append(float(np.abs(E - (A + (k + 1) * off)).max()))
        alphas.append(round(float(lk[ns + na + npool + k * na: ns + na + npool + (k + 1) * na, 0, 3].mean()), 4))
    return {'layers': [ns, na, npool, ne], 'K': K, 'max_err_per_copy': errs, 'alpha_mean_per_copy': alphas,
            'actor_alpha': round(float(lk[ns:ns + na, 0, 3].mean()), 4)}


# ---- W3: camera motion blur (K25) -------------------------------------------------------------------------------------
def blur_check(c, gain, maxlen=20.0):
    """velocity_streak source camera: look stretch = min(|vrel| gain, maxlen), sdir = vrel / |vrel| with vrel =
    -(CAMVEL + CAMOMEGA x (P - CAMPOS)) from the uG rows the GPU used (same frame: Play off after a move)."""
    import numpy as np
    X = _pxc()
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    g = np.array([[float(c.op('eng_g')[ch][i]) for ch in 'xyzw'] for i in range(c.op('eng_g').numSamples)])
    st = X['unpack'](c.op('update').numpyArray(delayed=False), 5, side, n)
    lk = X['unpack'](c.op('look').numpyArray(delayed=False), 3, side, n)
    P = st[:, 0, :3].astype(np.float64)
    vrel = -(g[24, :3] + np.cross(g[25, :3], P - g[8, :3]))
    sp = np.linalg.norm(vrel, axis=1)
    ref_st = np.minimum(sp * gain, maxlen)
    e1 = np.abs(lk[:, 1, 1] - ref_st)
    m = sp > 1e-3
    e2 = np.abs(lk[m, 2, :3] - vrel[m] / sp[m, None]).max() if m.any() else 0.0
    return {'camvel': g[24, :3].round(4).tolist(), 'omega': g[25, :3].round(4).tolist(), 'stretch_mean': float(lk[:, 1, 1].mean()),
            'ref_mean': float(ref_st.mean()), 'stretch_maxerr': float(e1.max()), 'dir_maxerr': float(e2)}


# ---- W3: heat spread (SA21) through the shared grid --------------------------------------------------------------------
def heat_stats(c, thr=0.3):
    import numpy as np
    X = _pxc()
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    st = X['unpack'](c.op('update').numpyArray(delayed=False), 5, side, n)
    h = st[:, 2, 3]
    P = st[:, 0, :3]
    hot = h > thr
    r = np.linalg.norm(P[hot] - np.array([0.0, 0.0, 0.0]), axis=1) if hot.any() else np.zeros(1)
    return {'hot': int(hot.sum()), 'max_r_hot': round(float(r.max()), 4), 'heat_max': round(float(h.max()), 3),
            'grid_on': bool(op('/project1/effectors').par.Gridon.eval())}


# ---- wave 4 K36: proximity from a > 4096-point cloud through the shared grid ------------------------------------------
K36_PIX = '''// w4 K36 check cloud: a sphere surface of radius 0.4 at the origin, one point per pixel (alpha 1)
out vec4 fragColor;
void main()
{
	vec2 uv = vUV.st;
	float th = uv.x * 6.28318530718, z = uv.y * 2.0 - 1.0, s = sqrt(max(0.0, 1.0 - z * z));
	fragColor = TDOutputSwizzle(vec4(0.4 * vec3(s * cos(th), z, s * sin(th)), 1.0));
}
'''


def k36_setup(c, n=128, R=0.3):
    """A 128 x 128 (16 384 points) sphere cloud TOP (/project1/lab/w4px_cloud) as the `cloud` row w4cloud of the
    shared list + the grid on around the origin; plane scene + one prox_push selecting it (shared_setup)."""
    lab = op('/project1/lab')
    g = lab.op('w4px_cloud') or lab.create(glslTOP, 'w4px_cloud')
    d = lab.op('w4px_cloud_pixel') or lab.create(textDAT, 'w4px_cloud_pixel')
    d.text = K36_PIX
    g.par.pixeldat = d.name
    g.par.outputresolution = 'custom'
    g.par.resolutionw = g.par.resolutionh = n
    g.par.format = 'rgba32float'
    ert = op('/project1/effectors/eff_rt').module
    if not any(r['name'] == 'w4cloud' for r in ert.rows()):
        ert.add('cloud', 'w4cloud', tags='w4', ref=g.path)
    e = op('/project1/effectors')
    e.par.Gridon = True
    for k in 'xyz':
        getattr(e.par, 'Gridcentre' + k).val = 0.0
    e.par.Gridsize = 2.0
    return shared_setup(c, sel='w4cloud', R=R)


def k36_check(c, R=0.3, r0=0.4):
    """GPU weight |P - p0| / 0.2 vs the analytic distance to the sphere surface (| |p0| - r0 |, the cloud is dense),
    linear falloff. The grid field answers within one cell (seed = voxel centroid)."""
    import numpy as np
    X = _pxc()
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    src = X['unpack'](c.op('source').numpyArray(delayed=False), 4, side, n)
    st = X['unpack'](c.op('update').numpyArray(delayed=False), 5, side, n)
    p0 = src[:, 0, :3]
    wg = np.linalg.norm(st[:, 0, :3] - p0, axis=1) / 0.2
    d = np.abs(np.linalg.norm(p0, axis=1) - r0)
    wr = np.clip(1.0 - d / R, 0.0, 1.0)
    cell = 2.0 / float(op('/project1/effectors').par.Gridres.eval())
    near = d < R - cell
    far = d > R + cell
    e = np.abs(wg - wr)
    return {'grid': '#define PXE_GRID' in c.op('update_compute').text, 'aux': int(c.op('aux_src').par.index.eval()),
            'weighted': int((wg > 1e-4).sum()), 'ref_weighted': int((wr > 0).sum()),
            'near_hit': round(float((wg[near] > 1e-4).mean()), 4) if near.any() else None,
            'far_zero': round(float((wg[far] < 1e-4).mean()), 4) if far.any() else None,
            'err_median': round(float(np.median(e[wr > 0])), 4), 'err_max_in_cell': round(float(e.max() * R / cell), 3),
            'cell': cell, 'status': c.par.Status.eval()}
