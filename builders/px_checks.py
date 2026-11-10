"""px_checks: live checks for /project1/lab/PX_pointfx (docs/builds/px.md LIVE CHECK list). Runs INSIDE TD via td_exec:
    ns = dict(globals()); exec(open('<repo>/builders/px_checks.py').read(), ns); ns['setup'](c, 'push')    # exec 1
    ns = dict(globals()); exec(open('<repo>/builders/px_checks.py').read(), ns); ns['check'](c, 'push')    # exec 2, frames >= 12
setup() writes the stack / core pars / effector transforms of one check and resets the sim; check() reads the GPU
textures (T-74/T-91: never in the exec that changed them; >= 2 frames later, delayed reads twice on the main TD) and
compares them with the float64 reference maths in px_logic (ref_*). Effector rows for the reference come from the
running eng_e CHOP, so the CPU side uses exactly the uniforms the GPU saw. ASCII; no TD state kept in module globals.
"""
import math

CORE_DEFAULTS = {'Amode': 'gen', 'Agen': 'sphere', 'Agenp': 1.0, 'Agenp2': 0.3, 'Agenp3': 0.0, 'Aspin': 0.0,
                 'Ascale': 1.0, 'Arot': 0.0, 'Bmode': 'off', 'Morph': 0.0, 'Stagger': 0.0, 'Quality': 'std',
                 'Play': True, 'Speed': 1.0, 'Spring': 4.0, 'Damping': 1.5, 'Drag': 0.2, 'Maxspeed': 0.0,
                 'Disrecover': 0.0, 'Statemode': 'feedback', 'Seed': 1}


def _rt(c):
    return c.op('px_rt').module


def _lg(c):
    return c.op('px_logic').module


def set_core(c, vals):
    for k, v in vals.items():
        p = getattr(c.par, k)
        if p.mode != ParMode.CONSTANT:
            p.mode = ParMode.CONSTANT
        p.val = v


def set_stack(c, mods):
    """mods = [(type, {param: value}, 'E1 E2' or None)] -> stack written (one recompile), values set."""
    Lg = _lg(c)
    st = []
    vals = {}
    for t, v, effs in mods:
        st, uid = Lg.add_module(st, t)
        for k, x in v.items():
            vals[Lg.par_name(uid, k)] = x
        if effs is not None:
            vals[Lg.par_name(uid, 'effectors')] = effs
    rt = _rt(c)
    rt.sync_pages(c, st, vals)
    rt.write_stack(c, st)
    rt.stack_changed(c)
    rt.sync_pages(c, st, vals)
    return [(i['uid'], i['type']) for i in st]


def set_eff(c, name, kind, xf):
    rt = _rt(c)
    if not any(r['name'] == name for r in rt.eff_table(c)):
        rt.add_effector(c, kind, name, {})
    o = c.op('effectors/' + name)
    base = {'tx': 0, 'ty': 0, 'tz': 0, 'rx': 0, 'ry': 0, 'rz': 0, 'sx': 1, 'sy': 1, 'sz': 1}
    base.update(xf)
    for k, v in base.items():
        getattr(o.par, k).val = v


def reset(c):
    _rt(c).S(c)['reset'] = 2


def grab(top, scratch):
    """rgba float array [row, col, ch] (row 0 = bottom). Scratch: synchronous; main: the delayed read (call twice)."""
    return top.numpyArray(delayed=not scratch)


def eff_rows(c):
    e = c.op('eng_e')
    return [[float(e[ch][i]) for ch in ('x', 'y', 'z', 'w')] for i in range(e.numSamples)]


def glob_rows(c):
    g = c.op('eng_g')
    return [[float(g[ch][i]) for ch in ('x', 'y', 'z', 'w')] for i in range(g.numSamples)]


def unpack(img, texels, side, n):
    import numpy as np
    a = np.asarray(img, dtype=np.float64)[:side, :side * texels].reshape(side * side, texels, 4)
    return a[:n]


SETUPS = {
    # X3/X4: generator sphere -> source texture
    'sphere': dict(core={}, stack=[], eff={}),
    # X5: torus morph
    'torus': dict(core={'Bmode': 'gen', 'Bgen': 'torus', 'Bgenp': 1.0, 'Bgenp2': 0.3, 'Morph': 1.0, 'Stagger': 0.0}, stack=[], eff={}),
    # X6: push displace, sphere effector at origin (r 0.5) over a plane
    'push': dict(core={'Agen': 'plane', 'Agenp': 1.0},
                 stack=[('prox_push', {'strength': 0.4, 'radius': 1.0, 'falloff': 1.0, 'shape': 'smooth', 'space': 'rest',
                                       'mode': 'displace', 'dir': 'outward'}, 'S1')],
                 eff={'S1': ('sphere', {})}),
    # X9: dissolve noise at progress 0.5
    'dissolve': dict(core={}, stack=[('dissolve_noise', {'progress': 0.5, 'release': 0.0, 'curl': 0.0, 'up': 0.0}, '')], eff={}),
    # X10: explode
    'explode': dict(core={}, stack=[('explode', {'progress': 1.0, 'distance': 3.0, 'random': 0.5, 'power': 1.0,
                                                 'mode': 'radial', 'swirl': 0.0}, '')], eff={}),
    # 3 moving Null effectors pushing a plane (positions animated by expressions; freeze() before the exact compare)
    'nulls': dict(core={'Agen': 'plane', 'Agenp': 1.2},
                  stack=[('prox_push', {'strength': 0.35, 'radius': 0.6, 'falloff': 1.0, 'shape': 'smooth', 'space': 'rest',
                                        'mode': 'displace', 'dir': 'outward', 'combine': 'max'}, 'N1 N2 N3')],
                  eff={'N1': ('null', {}), 'N2': ('null', {}), 'N3': ('null', {})}),
    # X11: twist + wave
    'twist': dict(core={}, stack=[('twist', {'twist': 1.3, 'axis': 'y', 'wobble': 0.0}, ''),
                                  ('wave', {'type': 'sine', 'amp': 0.1, 'freq': 3.0, 'speed': 0.0, 'dirx': 1.0, 'diry': 0.0,
                                            'dirz': 0.0, 'axis': 'y'}, '')], eff={}),
}


def pump(c, frames=30, top='out1'):
    """Pull `top` once per frame for `frames` frames (an unviewed COMP does not cook, T-87/T-91)."""
    for k in range(1, int(frames) + 1):
        run("o = op(%r)\nif o is not None: o.cook()" % (c.op(top).path,), delayFrames=k, delayRef=op.TDResources)
    return frames


NULL_PATHS = {'N1': ('0.7 * math.sin(absTime.seconds * 0.9)', '0.6 * math.cos(absTime.seconds * 0.7)', '0.15'),
              'N2': ('0.8 * math.cos(absTime.seconds * 0.5 + 2.0)', '0.5 * math.sin(absTime.seconds * 1.1 + 1.0)', '0.1'),
              'N3': ('0.5 * math.sin(absTime.seconds * 1.3 + 4.0)', '0.7 * math.sin(absTime.seconds * 0.6)', '-0.1')}


def animate_nulls(c, on=True):
    """on: N1..N3 follow Lissajous paths (expressions); off: frozen at their current values (constants)."""
    for nm, ex in NULL_PATHS.items():
        o = c.op('effectors/' + nm)
        for k, e in zip(('tx', 'ty', 'tz'), ex):
            p = getattr(o.par, k)
            if on:
                p.expr = e
                p.mode = ParMode.EXPRESSION
            else:
                v = p.eval()
                p.mode = ParMode.CONSTANT
                p.val = v
    return [[round(getattr(c.op('effectors/' + nm).par, k).eval(), 4) for k in ('tx', 'ty', 'tz')] for nm in NULL_PATHS]


def setup(c, name):
    s = SETUPS[name]
    c.allowCooking = True
    core = dict(CORE_DEFAULTS)
    core.update(s['core'])
    set_core(c, core)
    for en, (kind, xf) in s['eff'].items():
        set_eff(c, en, kind, xf)
    if name == 'nulls':
        animate_nulls(c, True)
    st = set_stack(c, s['stack'])
    _rt(c).load(c)
    reset(c)
    pump(c, 40)
    return {'setup': name, 'stack': st}


def _pull(c):
    for n in ('source', 'update', 'look'):
        c.op(n).cook()


def check(c, name, scratch=True):
    import numpy as np
    Lg = _lg(c)
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    src = unpack(grab(c.op('source'), scratch), 4, side, n)
    st = unpack(grab(c.op('update'), scratch), 5, side, n)
    p0 = src[:, 0, :3]
    valid = src[:, 0, 3]
    P = st[:, 0, :3]
    out = {'check': name, 'n': n, 'side': side, 'valid': int((valid > 0.5).sum()), 'status': c.par.Status.eval()}
    ids = np.arange(n)
    if name == 'sphere':
        ref = Lg.ref_gen('sphere', ids, n, 1.0)
        out['max_r'] = float(np.linalg.norm(p0, axis=1).max())
        out['sum_p0'] = [round(float(x), 5) for x in p0.sum(0)]
        out['maxerr_vs_ref'] = float(np.abs(p0 - ref).max())
        flip = unpack(grab(c.op('source'), scratch)[::-1], 4, side, n)[:, 0, :3]
        out['maxerr_if_rows_flipped'] = float(np.abs(flip - ref).max())
    elif name == 'torus':
        r = np.sqrt((np.linalg.norm(p0[:, [0, 2]], axis=1) - 1.0) ** 2 + p0[:, 1] ** 2)
        out['tube_r_min_max'] = [float(r.min()), float(r.max())]
        refb = Lg.ref_gen('torus', ids, n, 1.0, 0.3)
        out['maxerr_vs_ref'] = float(np.abs(p0 - refb).max())
    elif name == 'push':
        E = eff_rows(c)
        ix = [r['name'] for r in _rt(c).eff_table(c)].index('S1')
        ref = Lg.ref_push_displace(p0, E, 1 << ix, int(info['effectors'][0]), 1.0, 1.0, 0.4, 0)
        d = np.linalg.norm(P - p0, axis=1)
        k = int(np.argmin(np.linalg.norm(p0 - np.array([1.0, 0.0, 0.0]), axis=1)))
        out['eff_rows_S1'] = [[round(x, 4) for x in r] for r in E[ix * 6:ix * 6 + 6]]
        out['near_1_0_0'] = [round(float(x), 5) for x in P[k]]
        out['max_disp'] = float(d.max())
        out['mean_w'] = float((d / 0.4).mean())
        out['maxerr_vs_ref'] = float(np.abs(P - ref).max())
        out['rmserr_vs_ref'] = float(np.sqrt(((P - ref) ** 2).sum(1).mean()))
    elif name == 'nulls':
        E = np.asarray(eff_rows(c), dtype=np.float64)
        names = [r['name'] for r in _rt(c).eff_table(c)]
        ne = int(info['effectors'][0])
        idx = [names.index(k) for k in ('N1', 'N2', 'N3')]
        ws = np.stack([Lg.ref_fall(Lg.ref_effector_sd(E, i, p0), 0.6, 1.0, 0) for i in idx], 1)
        best = np.argmax(ws, 1)
        w = ws.max(1)
        ctr = E[[i * 6 + 4 for i in idx], :3][best]
        dv = p0 - ctr
        dn = dv / np.maximum(np.linalg.norm(dv, axis=1, keepdims=True), 1e-12)
        ref = p0 + dn * (0.35 * w)[:, None]
        d = np.linalg.norm(P - p0, axis=1)
        out['centres'] = [[round(float(x), 4) for x in E[i * 6 + 4, :3]] for i in idx]
        out['speeds'] = [round(float(E[i * 6 + 5, 3]), 4) for i in idx]
        out['moved_pts'] = int((d > 1e-4).sum())
        out['max_disp'] = float(d.max())
        out['maxerr_vs_ref'] = float(np.abs(P - ref).max())
        out['rmserr_vs_ref'] = float(np.sqrt(((P - ref) ** 2).sum(1).mean()))
        out['frac_err_gt_1e-3'] = float((np.abs(P - ref).max(1) > 1e-3).mean())
    elif name == 'dissolve':
        dis = st[:, 3, 3]
        G = glob_rows(c)
        ref = Lg.ref_dissolve_noise(p0, 0.5, 2.0, 3, 0.1, (0.0, 0.0, 0.0), tuple(G[7][:3]))
        out['mean_dis'] = float(dis.mean())
        out['mean_ref_frame'] = float(ref.mean())
        out['frac_dis_ge_ref'] = float((dis >= ref - 1e-4).mean())   # dis = max over frames (monotone at progress fixed)
        out['maxerr_vs_ref'] = float(np.abs(dis - np.clip(ref, 0, 1)).max())
    elif name == 'explode':
        r = np.linalg.norm(P, axis=1)
        seed = Lg.np_rnd(ids, 1)
        out['P_norm_mean_min_max'] = [float(r.mean()), float(r.min()), float(r.max())]
        ref = Lg.ref_explode(p0, (0.0, 0.0, 0.0), ids, seed, 1.0, 3.0, 1.0, 0.5)
        out['maxerr_vs_ref'] = float(np.abs(P - ref).max())
    elif name == 'twist':
        tw = Lg.ref_twist(p0, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 1.3)
        ref = Lg.ref_wave_sine(p0, (1.0, 0.0, 0.0), 3.0, 0.0, 0.1) - p0 + tw
        out['radius_err'] = float(np.abs(np.linalg.norm(P[:, [0, 2]], axis=1) - np.linalg.norm(p0[:, [0, 2]], axis=1)).max())
        out['dy_err'] = float(np.abs((P[:, 1] - p0[:, 1]) - 0.1 * np.sin(3.0 * p0[:, 0])).max())
        out['maxerr_vs_ref'] = float(np.abs(P - ref).max())
    out['nan'] = int(np.isnan(st).sum())
    return out


# ---- sweep: every module alone (linked to E1 when it takes effectors), compile + finite + measurable effect -------
SWEEP_VALUES = {'prox_dissolve': {'threshold': 0.2}, 'dissolve_noise': {'progress': 0.5}, 'dissolve_gradient': {'progress': 0.5},
                'explode': {'progress': 0.5}, 'prox_burn': {'consume': 0.0}, 'prox_stretch': {'snap': 0.5, 'tintamt': 1.0},
                'shockwave': {'trigger': 'beat', 'amp': 0.5}, 'audio_displace': {'band': 'spec_id', 'beatkick': 1.0},
                'mask_region': {}, 'mask_attr': {'lo': -0.2, 'hi': 0.4}, 'velocity_streak': {'gain': 3.0},
                'lifetime': {'life': 0.5, 'fadeout': 0.4}, 'density': {'density': 0.3},
                'colour_adjust': {'exposure': 1.0, 'hue': 0.3}, 'jitter': {'amp': 0.05}, 'glitch': {'prob': 0.5}}


def _sweep_measure(c, mtype):
    import numpy as np
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    src = unpack(c.op('source').numpyArray(delayed=False), 4, side, n)
    st = unpack(c.op('update').numpyArray(delayed=False), 5, side, n)
    lk = unpack(c.op('look').numpyArray(delayed=False), 3, side, n)
    d = np.linalg.norm(st[:, 0, :3] - src[:, 0, :3], axis=1)
    base_rgb = src[:, 1, :3]
    return {'type': mtype, 'status': c.par.Status.eval()[:40], 'nan': int(np.isnan(st).sum() + np.isnan(lk).sum()),
            'disp_mean': round(float(d.mean()), 5), 'disp_max': round(float(d.max()), 4),
            'rgb_change': round(float(np.abs(lk[:, 0, :3] - base_rgb).mean()), 4),
            'alpha_mean': round(float(lk[:, 0, 3].mean()), 4), 'size_mean': round(float(lk[:, 1, 0].mean()), 4),
            'stretch_mean': round(float(lk[:, 1, 1].mean()), 4), 'dis_mean': round(float(st[:, 3, 3].mean()), 4),
            'mask_max': [round(float(x), 3) for x in st[:, 3, :3].max(0)], 'heat_max': round(float(st[:, 2, 3].max()), 3)}


def sweep_step(path, k):
    """Chain: module k alone -> 24 frames later measure, then k + 1. Results in COMP storage px_sweep."""
    c = op(path)
    Lg = _lg(c)
    types = list(Lg.MODULES.keys())
    res = c.fetch('px_sweep', [], search=False)
    if k > 0:
        try:
            res.append(_sweep_measure(c, types[k - 1]))
        except Exception as e:
            res.append({'type': types[k - 1], 'error': str(e)[:200]})
        c.store('px_sweep', res)
    if k >= len(types):
        c.store('px_sweep_done', True)
        return
    t = types[k]
    effs = 'E1' if Lg.MODULES[t].get('eff') else ''
    set_stack(c, [(t, dict(SWEEP_VALUES.get(t, {})), effs)])
    reset(c)
    pump(c, 26)
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['sweep_step'](%r, %d)" % (CHECKS_FILE, path, k + 1),
        delayFrames=24, delayRef=op.TDResources)


CHECKS_FILE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/px_checks.py'


def sweep(c):
    c.store('px_sweep', [])
    c.store('px_sweep_done', False)
    set_core(c, dict(CORE_DEFAULTS))
    set_eff(c, 'E1', 'box', {'tx': 0.6, 'sx': 0.8, 'sy': 0.8, 'sz': 0.8})
    sweep_step(c.path, 0)
    return len(_lg(c).MODULES)


# ---- stack edits: each edit must swap the live shader text exactly once (probe -> live), relinks never -----------
STACK_OPS = [('relink', None), ('add', 'curl'), ('add', 'prox_colour'), ('duplicate', None), ('moveup', None),
             ('toggle', None), ('toggle', None), ('remove', None), ('badcode', None), ('fixcode', None)]


def _sample(path):
    c = op(path)
    log = c.fetch('px_ops_log', [], search=False)
    t = c.op('update_compute').text + c.op('colour_compute').text
    log[-1]['texts'].append(hash(t) & 0xffffffff)
    import time
    log[-1].setdefault('t', []).append(time.perf_counter())
    c.store('px_ops_log', log)


def _do_op(path, k):
    c = op(path)
    rt = _rt(c)
    st = rt.stack(c)
    kind, arg = STACK_OPS[k]
    last = st[-1]['uid'] if st else 0
    if kind == 'relink':
        p = getattr(c.par, 'M%deffectors' % st[0]['uid'])
        p.val = 'N2' if p.eval() != 'N2' else 'N1 N2 N3'
    elif kind == 'add':
        c.par.Addtype = arg
        rt.add(c, arg)
    elif kind == 'duplicate':
        rt.duplicate(c, last)
    elif kind == 'moveup':
        rt.move(c, last, -1)
    elif kind == 'toggle':
        rt.toggle(c, st[0]['uid'])
    elif kind == 'remove':
        rt.remove(c, last)
    elif kind == 'badcode':
        m = c.op('px_modules')
        c.store('px_mod_backup', m.text)
        m.text = m.text.replace('//@module curl update\n', '//@module curl update\nthis is not glsl;\n', 1)
        rt.add(c, 'curl')
    elif kind == 'fixcode':
        c.op('px_modules').text = c.fetch('px_mod_backup', c.op('px_modules').text, search=False)
        rt.stack_changed(c)


def stack_ops_step(path, k):
    c = op(path)
    log = c.fetch('px_ops_log', [], search=False)
    if k > 0:
        log[-1]['after_hash'] = c.fetch('px_hash', '', search=False)[:10]
        log[-1]['status'] = c.par.Status.eval()[:90]
        log[-1]['stack'] = [(i['uid'], i['type'], int(i['enabled'])) for i in _rt(c).stack(c)]
        log[-1]['pages'] = [p.name for p in c.customPages if p.name.startswith('M')]
        tx = log[-1]['texts']
        log[-1]['swaps'] = sum(1 for a, b in zip(tx, tx[1:]) if a != b)
        del log[-1]['texts']
        ts = log[-1].pop('t', [])
        log[-1]['max_frame_ms'] = round(max([(b - a) * 1000.0 for a, b in zip(ts, ts[1:])] or [0.0]), 1)
        c.store('px_ops_log', log)
    if k >= len(STACK_OPS):
        c.store('px_ops_done', True)
        return
    log.append({'op': STACK_OPS[k][0] + ('' if STACK_OPS[k][1] is None else ' ' + STACK_OPS[k][1]),
                'before_hash': c.fetch('px_hash', '', search=False)[:10], 'texts': []})
    c.store('px_ops_log', log)
    _sample(path)
    _do_op(path, k)
    for f in range(1, 12):
        run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_sample'](%r)" % (CHECKS_FILE, path),
            delayFrames=f, delayRef=op.TDResources)
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['stack_ops_step'](%r, %d)" % (CHECKS_FILE, path, k + 1),
        delayFrames=12, delayRef=op.TDResources)


def stack_ops(c):
    c.store('px_ops_log', [])
    c.store('px_ops_done', False)
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['stack_ops_step'](%r, 0)" % (CHECKS_FILE, c.path),
        delayFrames=30, delayRef=op.TDResources)
    return len(STACK_OPS)


# ---- preset morph: sample values every few frames vs px_logic.curve; count shader swaps ---------------------------
def _morph_sample(path, keys):
    import time
    c = op(path)
    log = c.fetch('px_morph_log', [], search=False)
    m = _rt(c).S(c).get('morph')
    t = c.op('update_compute').text + c.op('colour_compute').text
    log.append({'t': time.perf_counter(), 'abs': absTime.seconds, 'active': m is not None, 't0': m['t0'] if m else None,
                'vals': [float(getattr(c.par, k).eval()) for k in keys], 'h': hash(t) & 0xffffffff,
                'stack': len(_rt(c).stack(c))})
    c.store('px_morph_log', log)


def morph_test(c, a, b, keys, seconds=4.0, curve='smooth'):
    """Recall a, then Morph to b over `seconds`; samples every 6 frames for seconds + 1 s (results: px_morph_log)."""
    rt = _rt(c)
    rt.recall(c, a)
    c.par.Morphtime = seconds
    c.par.Morphcurve = curve
    c.store('px_morph_log', [])
    c.store('px_morph_keys', list(keys))
    run("op(%r).op('px_rt').module.morph_to(op(%r), %r)" % (c.path, c.path, b), delayFrames=30, delayRef=op.TDResources)
    for f in range(30, 30 + int((seconds + 1.0) * 60), 6):
        run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_morph_sample'](%r, %r)" % (CHECKS_FILE, c.path, list(keys)),
            delayFrames=f, delayRef=op.TDResources)
    pump(c, 30 + int((seconds + 1.5) * 60))
    return {'a': a, 'b': b, 'keys': keys}


def morph_report(c, a_vals, b_vals, seconds=4.0, curve='smooth'):
    Lg = _lg(c)
    log = c.fetch('px_morph_log', [], search=False)
    act = [r for r in log if r['active']]
    if not act:
        return {'error': 'morph never active', 'n': len(log)}
    errs = []
    rows = []
    for r in log:
        if not r['active']:
            continue
        # morph clock: the tick that wrote these values ran this frame; u from the sample's own time
        u = None
        for k, (va, vb, v) in enumerate(zip(a_vals, b_vals, r['vals'])):
            if abs(vb - va) > 1e-9:
                u = (v - va) / (vb - va)
                break
        rows.append((round(r['abs'] - r['t0'], 3), None if u is None else round(u, 4)))
    # implied u must be monotone and follow curve(t/seconds) within one frame of clock skew
    for (ts, u) in rows:
        if u is None:
            continue
        lo = Lg.curve(max(ts - 1.0 / 30.0, 0.0) / seconds, curve) - 1e-3
        hi = Lg.curve((ts + 1.0 / 30.0) / seconds, curve) + 1e-3
        errs.append(0.0 if lo <= u <= hi else min(abs(u - lo), abs(u - hi)))
    hs = [r['h'] for r in log]
    swaps = sum(1 for x, y in zip(hs, hs[1:]) if x != y)
    return {'samples': len(log), 'active_samples': len(act), 'u_vs_t': rows[::4], 'max_curve_err': max(errs or [0.0]),
            'final_vals': log[-1]['vals'], 'shader_swaps_during': swaps,
            'stack_sizes': sorted(set(r['stack'] for r in log))}


# ---- perf (T-100/T-102): pull out1 once per frame; sum cpu+gpu ms of ops that cooked for that pull; real fps from
# the wall clock in a separate pull-only run (the measuring Python itself costs fps) ---------------------------------
def _perf_tick(path, k, n, mode):
    import time
    c = op(path)
    o = c.op('out1')
    _tick_first(c)
    o.cook()
    rec = c.fetch('px_perf', {}, search=False)
    rec.setdefault('wall', []).append(time.perf_counter())
    if mode == 'ops':
        per = rec.setdefault('ops', {})
        last = rec.setdefault('tc', {})
        tot = 0.0
        so = c.op('sorter')
        kids = c.findChildren(maxDepth=1) + (so.findChildren(maxDepth=1) if so is not None else [])
        split = rec.setdefault('split', {})
        for x in kids:
            nm = x.name if x.parent() == c else 'sorter/' + x.name
            try:
                tc = int(x.totalCooks)
                cooked = nm in last and tc > last[nm]
                last[nm] = tc
                if not cooked:
                    continue
                cpu = float(x.cpuCookTime)
                gpu = float(getattr(x, 'gpuCookTime', 0.0) or 0.0)
                ms = cpu + gpu
            except Exception:
                continue
            per.setdefault(nm, []).append(ms)
            sp = split.setdefault(nm, [[], []])
            sp[0].append(cpu)
            sp[1].append(gpu)
            if nm != 'sorter':                       # the COMP's own time would double its children
                tot += ms
        rec.setdefault('tot', []).append(tot)
    c.store('px_perf', rec)
    if k + 1 < n:
        run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_perf_tick'](%r, %d, %d, %r)" % (CHECKS_FILE, path, k + 1, n, mode),
            delayFrames=1, delayRef=op.TDResources)


def _tick_first(c):
    """A run() pull can come before the px_tick Execute DAT in a frame; a viewer pull never does (cooks follow the
    frame-start callbacks). Run the engine tick first, as a viewer pull would see it (T-143)."""
    try:
        c.op('px_rt').module.tick(c)
    except Exception:
        pass


def perf_start(c, n=180, mode='ops'):
    c.store('px_perf', {})
    _perf_tick(c.path, 0, n, mode)
    return n


def perf_report(c):
    rec = c.fetch('px_perf', {}, search=False)
    w = rec.get('wall', [])
    dts = sorted((b - a) * 1000.0 for a, b in zip(w, w[1:]))
    med = lambda v: sorted(v)[len(v) // 2] if v else 0.0
    out = {'frames': len(w), 'real_fps': round((len(w) - 1) / max(w[-1] - w[0], 1e-9), 1) if len(w) > 1 else 0.0,
           'frame_ms_median': round(med(dts), 2), 'frame_ms_p95': round(dts[int(len(dts) * 0.95)] if dts else 0.0, 2)}
    if 'tot' in rec:
        out['comp_ms_median'] = round(med(rec['tot']), 2)
        top = sorted(((round(med(v), 3), k) for k, v in rec['ops'].items()), reverse=True)[:8]
        out['top_ops_ms'] = [(k, v) for v, k in top]
        eng = [k for k in rec['ops'] if k.startswith('eng_')]
        n = len(rec['tot'])
        out['engine_ms_mean'] = round(sum(sum(rec['ops'][k]) for k in eng) / max(n, 1), 3)
        sp = rec.get('split', {})
        out['detail'] = sorted(((k, round(med(v[0]), 3), round(med(v[1]), 3), len(v[0]),
                                 round(max(a + b for a, b in zip(v[0], v[1])), 2)) for k, v in sp.items()),
                               key=lambda r: -(r[1] + r[2]))[:24]
    return out


def perf_tiers(c, tiers=('draft', 'std', 'high', 'ultra'), n=120, settle=90):
    """Chain: per tier set Quality, settle frames (reload + realloc), then n ops-mode frames; results px_perf_tiers."""
    c.store('px_perf_tiers', {})
    _tier_step(c.path, list(tiers), 0, n, settle)
    return list(tiers)


def _tier_step(path, tiers, k, n, settle):
    c = op(path)
    res = c.fetch('px_perf_tiers', {}, search=False)
    if k > 0:
        res[tiers[k - 1]] = perf_report(c)
        res[tiers[k - 1]]['count'] = int(c.op('eng_info')['count'][0])
        c.store('px_perf_tiers', res)
    if k >= len(tiers):
        return
    c.par.Quality = tiers[k]
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['perf_start'](op(%r), %d, 'ops')" % (CHECKS_FILE, path, n),
        delayFrames=settle, delayRef=op.TDResources)
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_tier_step'](%r, %r, %d, %d, %d)" % (CHECKS_FILE, path, tiers, k + 1, n, settle),
        delayFrames=settle + int(n * 1.6) + 20, delayRef=op.TDResources)


# ---- v2 checks (docs/builds/px.md "v2 checks"): one prox_push (displace, outward, rest space) of strength S, so the
# GPU weight is w = |P - p0| / S, compared with px_logic's float64 reference (ref_pts_nearest / ref_front / ref_wake)
# fed with the uniforms the GPU saw (eng_e, eng_pts, eng_trail). Helper ops live inside the COMP as chk_* and are
# removed by v2_clean().

V2_S = 0.2


def _chk_pts_chop(c, pts, exprs=None):
    """chk_pts: Constant-like CHOP with samples = points (tx ty tz), from a Table DAT -> DAT to CHOP."""
    t = c.op('chk_pts_tab') or c.create(tableDAT, 'chk_pts_tab')
    t.clear()
    t.appendRow(['tx', 'ty', 'tz'])
    for p in pts:
        t.appendRow([repr(float(x)) for x in p])
    d = c.op('chk_pts')
    if d is not None and d.type != 'datto':
        d.destroy()
        d = None
    d = d or c.create(dattoCHOP, 'chk_pts')
    d.par.dat = t.name
    d.par.firstrow = 'names'
    d.par.firstcolumn = 'values'
    d.par.output = 'chanpercol'
    return d


def reset_pages(c, pages=('Source', 'Sim')):
    """Every par of these core pages back to its default (looks leave offsets / scales behind)."""
    for p in c.customPars:
        if p.page.name in pages and p.style not in ('Pulse', 'Momentary') and not p.readOnly:
            if p.mode != ParMode.CONSTANT:
                p.mode = ParMode.CONSTANT
            try:
                p.val = p.default
            except Exception:
                pass


def v2_setup(c, name, **kw):
    """splat=True keeps / sets the splat scene (SPLAT_SCENE, Render splats) instead of the generated plane."""
    c.allowCooking = True
    rt = _rt(c)
    for r in list(rt.eff_table(c)):
        rt.remove_effector(c, r['name'])
    if kw.get('splat'):
        splat_core(c, kw.get('core'))
    else:
        reset_pages(c)
        core = dict(CORE_DEFAULTS)
        core.update({'Agen': 'plane', 'Agenp': 1.0})
        core.update(kw.get('core', {}))
        set_core(c, core)
    eff = ''
    if name in OBJ_CASES:                           # objects (+ a motion path) on any scene
        kind, xf, ep = OBJ_CASES[name]
        rt.add_effector(c, kind, 'E1', dict(xf))
        if ep:
            rt.eff_page(c.op('effectors/E1'), dict(ep))
        eff = 'E1'
    shape = kw.get('shape', 'linear')
    R = kw.get('R', 0.3)
    k = kw.get('k', 1.0)
    if name == 'ptsvel':                            # A1b: point k moves along x at k units/s (sawtooth, 4 s)
        sc = c.op('chk_pts')
        if sc is not None and sc.type != 'script':
            sc.destroy()
            sc = None
        sc = sc or c.create(scriptCHOP, 'chk_pts')
        cb = c.op('chk_pts_cb') or c.create(textDAT, 'chk_pts_cb')
        cb.text = ("def onSetupParameters(scriptOp):\n    return\n\ndef onCook(scriptOp):\n    scriptOp.clear()\n"
                   "    scriptOp.numSamples = 3\n    u = absTime.seconds % 4.0\n"
                   "    for nm in ('tx', 'ty', 'tz'):\n        ch = scriptOp.appendChan(nm)\n"
                   "        for k in range(3):\n            ch[k] = k * u if nm == 'tx' else 0.0\n    return\n")
        sc.par.callbacks = cb.name
        if getattr(sc.par, 'Frame', None) is None:
            sc.appendCustomPage('Clock').appendFloat('Frame')
        sc.par.Frame.expr = 'absTime.frame'
    if name == 'ptsrc':                             # A1c: a real point source (landmark CHOP, particle TOP, mesh)
        rt.add_effector(c, 'pts', 'E3', kw.get('xform', {}))
        rt.eff_page(c.op('effectors/E3'), {'Ptssource': kw['src'], 'Ptsmode': 'nearest',
                                          'Ptsradius': kw.get('prad', 0.02), 'Ptsmax': kw.get('ptsmax', 512)})
        eff = 'E3'
    elif name in ('pts', 'density', 'ptsvel'):
        if name != 'ptsvel':
            _chk_pts_chop(c, kw.get('pts', [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.2, 0.0, 0.0)]))
        rt.add_effector(c, 'pts', 'E3', {})
        o = c.op('effectors/E3')
        rt.eff_page(o, {'Ptssource': 'chk_pts', 'Ptsmode': 'density' if name == 'density' else 'nearest',
                        'Ptsradius': kw.get('prad', 0.02), 'Ptsmax': 512})
        eff = 'E3'
    elif name in ('behind', 'ahead'):
        rt.add_effector(c, 'plane', 'Esw', {'rz': -90.0, 'sx': 6.0, 'sz': 6.0})
        rt.eff_page(c.op('effectors/Esw'), {'Motion': 'line', 'Ma': (-3.0, 0.0, 0.0), 'Mb': (3.0, 0.0, 0.0),
                                            'Mperiod': kw.get('period', 18.0), 'Mloop': 'pingpong', 'Mease': 'linear'})
        eff = 'Esw'
    elif name == 'wake':
        rt.add_effector(c, 'null', 'Ew', {})
        rt.eff_page(c.op('effectors/Ew'), {'Motion': 'line', 'Ma': (1.5, 0.0, 0.0), 'Mb': (-1.5, 0.0, 0.0),
                                           'Mperiod': 6.0, 'Mloop': 'pingpong', 'Mease': 'linear', 'Trail': 8,
                                           'Traildt': 0.1})
        eff = 'Ew'
    st = set_stack(c, [('prox_push', {'strength': V2_S, 'radius': R, 'falloff': k, 'shape': shape, 'space': 'rest',
                                      'mode': 'displace', 'dir': kw.get('dir', 'outward'), 'noiseedge': 0.0,
                                      'edge': kw.get('edge', 0.02)}, eff)])
    rt.load(c)
    reset(c)
    pump(c, 40)
    return {'setup': name, 'stack': st, 'eff': [r['name'] + ':' + r['kind'] for r in rt.eff_table(c)]}


def _chop_rows(ch):
    return [[float(ch[n][i]) for n in ('x', 'y', 'z', 'w')] for i in range(ch.numSamples)]


def v2_check(c, name, scratch=True, R=0.3, k=1.0, shape=1, prad=0.02, edge=0.02):
    import numpy as np
    Lg = _lg(c)
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    src = unpack(grab(c.op('source'), scratch), 4, side, n)
    st = unpack(grab(c.op('update'), scratch), 5, side, n)
    E = eff_rows(c)
    p0 = src[:, 0, :3]
    P = st[:, 0, :3]
    wg = np.linalg.norm(P - p0, axis=1) / V2_S
    out = {'check': name, 'n': n, 'status': c.par.Status.eval(), 'nan': int(np.isnan(st).sum())}
    if name in ('pts', 'density', 'ptsvel', 'ptsrc'):
        b = 0 * Lg.E_PER
        s0, cnt = int(round(E[b + 6][3])), int(round(E[b + 7][0]))
        pts = np.asarray(_chop_rows(c.op('eng_pts')))[s0:s0 + cnt, :3]
        vel = np.asarray(_chop_rows(c.op('eng_ptsv')))[s0:s0 + cnt, :3]
        d, nv = Lg.ref_pts_nearest(p0, pts, vel, prad, 1 if name == 'density' else 0)
        wr = Lg.ref_fall(d, R, k, shape)
        out.update({'pts_count_uE': cnt, 'pts': pts.round(4).tolist()[:4], 'ptsv': vel.round(3).tolist()[:4],
                    'uE_type': E[b + 3][0]})
        if name == 'density':
            dd, _v = Lg.ref_pts_nearest(np.zeros((1, 3)), [(0, 0, 0), (1, 0, 0)], None, 1.0, 1)
            out['density_probe_origin_ref'] = round(float(dd[0]), 4)
    elif name in OBJ_CASES:
        wr = Lg.ref_prox_w(p0, E, 1, 1, R, k, shape)
        out.update({'centre': [round(x, 4) for x in E[4][:3]], 'vel': [round(x, 4) for x in E[6][:3]],
                    'speed': round(float(np.linalg.norm(E[6][:3])), 4), 'sdf_type': E[3][0]})
    elif name in ('behind', 'ahead'):
        wr = Lg.ref_front(p0, E, 0, R, k, 6 if name == 'behind' else 7, edge)
        out.update({'centre': [round(x, 4) for x in E[4][:3]], 'vel': [round(x, 4) for x in E[6][:3]]})
    elif name == 'wake':
        ts, tc = int(round(E[7][2])), int(round(E[7][3]))
        tr = _chop_rows(c.op('eng_trail'))[ts:ts + tc]
        wr = Lg.ref_wake(p0, E[4][:3], [(r[:3], r[3]) for r in tr], R, k)
        out.update({'trail_n': tc, 'trail_ages': [round(r[3], 3) for r in tr], 'centre': [round(x, 4) for x in E[4][:3]]})
    err = np.abs(wg - wr)
    out.update({'w_gpu_mean': round(float(wg.mean()), 5), 'w_ref_mean': round(float(wr.mean()), 5),
                'n_w_pos': int((wr > 1e-3).sum()), 'maxerr': float(err.max()), 'rmserr': float(np.sqrt((err ** 2).mean())),
                'p99err': float(np.percentile(err, 99))})
    return out


def v2_clean(c):
    for nm in ('chk_pts', 'chk_pts_tab', 'chk_pts_cb'):
        o = c.op(nm)
        if o is not None:
            o.destroy()


LOOKS_DIR = '~/Documents/StageLab_PrismFest/jazib-td-mcp/output/px_looks/v2'


def capture(c, name, top='out1', delay=30, pump_frames=None):
    """Save `top` as LOOKS_DIR/<name>.jpg `delay` frames later (T-74: never in the exec that changed things); pulls
    out1 every frame until then (an unviewed COMP does not cook). jpg = premultiplied colour on black."""
    import os
    os.makedirs(LOOKS_DIR, exist_ok=True)
    pump(c, pump_frames or delay + 2)
    path = os.path.join(LOOKS_DIR, name + '.jpg')
    run("op(%r).save(%r)" % (c.op(top).path, path), delayFrames=delay, delayRef=op.TDResources)
    return path


# ---- v2 looks on a street-like scan (media/demo/splats/truck.splat, SOURCES.md): base scene + one built-in look
TRUCK = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/demo/splats/truck.splat'
LOOK_BASE = {'Amode': 'file', 'Afile': TRUCK, 'Quality': 'high', 'Render': 'sprites', 'Aoffsetx': 0.0, 'Aoffsety': 1.2,
             'Aoffsetz': 0.0, 'Size': 0.011, 'Aperture': 0.2, 'Focus': 3.4, 'Alpha': 1.0, 'Bright': 2.0, 'Orbit': 0.0,
             'Camdist': 4.4, 'Camheight': 0.6, 'Exposure': 0.3, 'Minpx': 1.6, 'Haze': 0.02, 'Blend': 'alpha',
             'Bloom': 0.5, 'Softness': 0.35, 'Saturation': 1.3, 'Ptopacity': 0.0, 'Ptcut': 0.08, 'Sprite': 'soft',
             'Flare': 0.0, 'Trails': False, 'Pool': 0.0, 'Actormode': 'off', 'Tealorange': 0.3, 'Streakmax': 64.0,
             'Clip': 6.0, 'Opacitymin': 0.06}


def look_base(c, extra=None, load=True):
    reset_pages(c, ('Source', 'Sim', 'Look', 'Grade'))
    v = dict(LOOK_BASE)
    v.update(extra or {})
    set_core(c, v)
    if load:
        _rt(c).load(c)
    reset(c)


def look(c, name, base_extra=None, delay=150, tag=''):
    """Base scene, then recall the built-in look `name` (its effectors are created), capture out1 `delay` frames later
    to LOOKS_DIR/<name>[tag].jpg."""
    rt = _rt(c)
    for r in list(rt.eff_table(c)):
        rt.remove_effector(c, r['name'])
    look_base(c, base_extra)
    rt.recall(c, name)
    fn = name.lower().replace(' ', '_') + tag
    return capture(c, fn, 'out1', delay)


def look_seq(c, name, frames=(120,), trig_at=None, settle=60):
    """Base scene + built-in look, then captures at each frame offset after `settle` (pulse Trig1 at settle + trig_at
    when given). Files LOOKS_DIR/<name>_<offset>.jpg. Returns the last frame used."""
    rt = _rt(c)
    for r in list(rt.eff_table(c)):
        rt.remove_effector(c, r['name'])
    look_base(c)
    rt.recall(c, name)
    last = settle + max(frames) + 2
    pump(c, last)
    if trig_at is not None:
        run("op(%r).par.Trig1.pulse()" % c.path, delayFrames=settle + trig_at, delayRef=op.TDResources)
    fn = name.lower().replace(' ', '_')
    for f in frames:
        run("op(%r).save(%r)" % (c.op('out1').path, '%s/%s_%03d.jpg' % (LOOKS_DIR, fn, f)), delayFrames=settle + f,
            delayRef=op.TDResources)
    return last


def sheet(names, out, w=360, h=640, cols=4):
    """Contact sheet of LOOKS_DIR jpgs (offline helper, PIL; run outside TD)."""
    from PIL import Image, ImageDraw
    rows = (len(names) + cols - 1) // cols
    sh = Image.new('RGB', (w * cols, h * rows))
    for i, n in enumerate(names):
        im = Image.open('%s/%s.jpg' % (LOOKS_DIR, n)).convert('RGB').resize((w, h))
        ImageDraw.Draw(im).text((8, 8), n, fill=(255, 255, 0))
        sh.paste(im, ((i % cols) * w, (i // cols) * h))
    sh.save('%s/%s.jpg' % (LOOKS_DIR, out), quality=90)


# ---- A/B perf (PX perf lane, T-143): under 6 TDs single runs swing 2x (T-133 (8)); alternate two setups every n
# frames for several rounds in ONE chain and compare medians per op. Setups are code strings exec'd with c bound (plain
# data in storage, T-67). Frames right after a switch are skipped (settle).
def _ab_tick(path, k):
    import time
    c = op(path)
    ab = c.fetch('px_ab', None, search=False)
    if ab is None:
        return
    seg = k // ab['n']
    if seg >= 2 * ab['rounds']:
        ab['done'] = True
        exec(ab['code'][0], {'c': c, 'op': op})
        c.store('px_ab', ab)
        return
    m = seg % 2
    if k % ab['n'] == 0:
        exec(ab['code'][m], {'c': c, 'op': op})
    _tick_first(c)
    c.op('out1').cook()
    ab['wall'][m].append(time.perf_counter())
    if k % ab['n'] >= ab['settle']:
        last = ab['tc']
        so = c.op('sorter')
        kids = c.findChildren(maxDepth=1) + (so.findChildren(maxDepth=1) if so is not None else [])
        tot = 0.0
        eng = 0.0
        for x in kids:
            nm = x.name if x.parent() == c else 'sorter/' + x.name
            try:
                tc = int(x.totalCooks)
                cooked = nm in last and tc > last[nm]
                last[nm] = tc
                if not cooked or nm == 'sorter':
                    continue
                cpu = float(x.cpuCookTime)
                gpu = float(getattr(x, 'gpuCookTime', 0.0) or 0.0)
            except Exception:
                continue
            d = ab['ops'][m].setdefault(nm, [[], []])
            d[0].append(cpu)
            d[1].append(gpu)
            tot += cpu + gpu
            if nm.startswith('eng_'):
                eng += cpu
        ab['tot'][m].append(tot)
        ab['eng'][m].append(eng)
    else:
        so = c.op('sorter')
        for x in c.findChildren(maxDepth=1) + (so.findChildren(maxDepth=1) if so is not None else []):
            try:
                ab['tc'][x.name if x.parent() == c else 'sorter/' + x.name] = int(x.totalCooks)
            except Exception:
                pass
    c.store('px_ab', ab)
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_ab_tick'](%r, %d)" % (CHECKS_FILE, path, k + 1),
        delayFrames=1, delayRef=op.TDResources)


def ab_start(c, code_a, code_b, n=40, rounds=3, settle=8):
    c.store('px_ab', {'code': [code_a, code_b], 'n': n, 'rounds': rounds, 'settle': settle, 'tc': {},
                      'ops': [{}, {}], 'tot': [[], []], 'eng': [[], []], 'wall': [[], []], 'done': False})
    _ab_tick(c.path, 0)
    return 2 * n * rounds


def ab_report(c, names=('render', 'srender', 'sorter/sort', 'eng_info', 'update', 'look', 'source', 'post')):
    ab = c.fetch('px_ab', {}, search=False)
    med = lambda v: round(sorted(v)[len(v) // 2], 3) if v else None
    out = {'done': ab.get('done'), 'tot_ms': [med(ab['tot'][0]), med(ab['tot'][1])],
           'engine_cpu_ms': [med(ab['eng'][0]), med(ab['eng'][1])], 'frames': [len(ab['tot'][0]), len(ab['tot'][1])]}
    for nm in names:
        a, b = ab['ops'][0].get(nm), ab['ops'][1].get(nm)
        out[nm] = [[med(a[0]), med(a[1])] if a else None, [med(b[0]), med(b[1])] if b else None]
    return out


# ---- splats (27 Oct, splat lane): every module / effector / look on a Gaussian splat scene, Render splats. The same
# textures as points (so the v2 references apply unchanged) + what the splat render shows: srender vs the no-module
# baseline (mean abs rgb / alpha change, 1/8 grid) and the splat-only attributes (rotation, peel, covariance size).
SMILEY = '/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/PointClouds/SmileyPinata.spz'
SPLAT_SCENE = {'Amode': 'file', 'Afile': SMILEY, 'Quality': 'custom', 'Count': 228287, 'Render': 'splats',
               'Camdist': 1.3, 'Camheight': 0.15, 'Orbit': 0.0, 'Fov': 55.0, 'Bright': 1.0, 'Pool': 0.0,
               'Actormode': 'off', 'Bmode': 'off', 'Trails': False, 'Bloom': 0.0, 'Flare': 0.0, 'Ascale': 1.0,
               'Arot': 0.0, 'Aoffsetx': 0.0, 'Aoffsety': 0.0, 'Aoffsetz': 0.0, 'Aperture': 0.0, 'Play': True,
               'Speed': 1.0, 'Disrecover': 0.0, 'Statemode': 'feedback', 'Clip': 0.0, 'Opacitymin': 0.0}
# object effectors for v2_setup / v2_check (kind, transform, Effector page); 'path' = a Null on a line path (A2)
OBJ_CASES = {'box': ('box', {'tx': 0.25, 'sx': 0.5, 'sy': 0.5, 'sz': 0.5}, {}),
             'sphere': ('sphere', {'tx': 0.25, 'sx': 0.5, 'sy': 0.5, 'sz': 0.5}, {}),
             'plane': ('plane', {'rz': -90.0, 'sx': 2.0, 'sz': 2.0}, {}),
             'null': ('null', {'tx': 0.25}, {}),
             'path': ('null', {}, {'Motion': 'line', 'Ma': (-0.5, 0.0, 0.0), 'Mb': (0.5, 0.0, 0.0), 'Mperiod': 6.0,
                                   'Mloop': 'pingpong', 'Mease': 'linear'})}
SPLAT_SWEEP_VALUES = dict(SWEEP_VALUES)
SPLAT_SWEEP_VALUES.update({'prox_stretch': {'stretch': 4.0, 'thin': 0.5}, 'twist': {'twist': 1.3},
                           'prox_vortex': {'mode': 'twist', 'strength': 3.0}, 'prox_scale': {'sizegain': 1.5},
                           'prox_colour': {'mode': 'replace', 'colour': (1.0, 0.1, 0.05)},
                           'orbit': {'speed': 1.0}})
SPLAT_DIR = '~/Documents/StageLab_PrismFest/jazib-td-mcp/output/px_looks/splats'


def splat_core(c, extra=None):
    """Splat scene pars, each set ONCE and only when it differs (a reset-then-set of the same par replays through the
    zkit two-way sync after the exec and can leave the reset value: Quality came back 'draft', T-164)."""
    v = dict(SPLAT_SCENE)
    v.update(extra or {})
    for k, x in v.items():
        p = getattr(c.par, k)
        if p.mode != ParMode.CONSTANT:
            p.mode = ParMode.CONSTANT
        if p.eval() != x:
            p.val = x


def _grid(top):
    import numpy as np
    return np.asarray(top.numpyArray(delayed=False), dtype=np.float64)[::8, ::8, :]


def splat_base(c):
    """Store the no-module srender (1/8 grid) as the baseline (plain numpy data in storage)."""
    c.store('pxs_base', _grid(c.op('srender')))
    return float(c.fetch('pxs_base', None, search=False)[..., 3].mean())


def _splat_measure(c, mtype):
    import numpy as np
    out = _sweep_measure(c, mtype)
    info = c.op('eng_info')
    n = int(info['count'][0])
    side = int(info['side'][0])
    src = unpack(c.op('source').numpyArray(delayed=False), 4, side, n)
    st = unpack(c.op('update').numpyArray(delayed=False), 5, side, n)
    dq = np.abs((src[:, 3, :] * st[:, 4, :]).sum(1)).clip(0.0, 1.0)
    out['rot_deg_mean'] = round(float(np.degrees(2.0 * np.arccos(dq)).mean()), 3)
    out['splat'] = int(info['splat'][0])
    out['sw_render'] = int(c.op('sw_render').par.index.eval())
    base = c.fetch('pxs_base', None, search=False)
    cur = _grid(c.op('srender'))
    if base is not None and base.shape == cur.shape:
        out['img_rgb_diff'] = round(float(np.abs(cur[..., :3] - base[..., :3]).mean()), 5)
        out['img_alpha'] = [round(float(base[..., 3].mean()), 4), round(float(cur[..., 3].mean()), 4)]
    return out


def splat_sweep_step(path, k):
    """Chain: module k alone on the splat scene -> 30 frames later measure + capture out1, then k + 1 (px_sweep)."""
    c = op(path)
    Lg = _lg(c)
    types = list(Lg.MODULES.keys())
    res = c.fetch('px_sweep', [], search=False)
    if k > 0:
        t0 = types[k - 1]
        try:
            res.append(_splat_measure(c, t0))
            c.op('out1').save('%s/mod_%02d_%s.jpg' % (SPLAT_DIR, k - 1, t0))
        except Exception as e:
            res.append({'type': t0, 'error': str(e)[:200]})
        c.store('px_sweep', res)
    if k >= len(types):
        c.store('px_sweep_done', True)
        return
    t = types[k]
    effs = 'E1' if Lg.MODULES[t].get('eff') else ''
    set_stack(c, [(t, dict(SPLAT_SWEEP_VALUES.get(t, {})), effs)])
    reset(c)
    pump(c, 32)
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['splat_sweep_step'](%r, %d)" % (CHECKS_FILE, path, k + 1),
        delayFrames=30, delayRef=op.TDResources)


def splat_sweep(c):
    """Every module alone on the splat scene (E1 box beside the centre). Needs splat_base() stored first."""
    import os
    os.makedirs(SPLAT_DIR, exist_ok=True)
    c.store('px_sweep', [])
    c.store('px_sweep_done', False)
    if not any(r['name'] == 'E1' for r in _rt(c).eff_table(c)):
        set_eff(c, 'E1', 'box', {'tx': 0.25, 'sx': 0.5, 'sy': 0.5, 'sz': 0.5})
    splat_sweep_step(c.path, 0)
    return len(_lg(c).MODULES)


def a6_camera(c):
    """A6: camera effector rows = the output camera (centre = eng_cam position, axis = its forward)."""
    import math
    E = eff_rows(c)
    rt = _rt(c)
    i = next(k for k, r in enumerate(rt.eff_table(c)) if r.get('kind') == 'camera')
    b = i * _lg(c).E_PER
    cam = c.op('eng_cam')
    pos = [float(cam[k][0]) for k in ('tx', 'ty', 'tz')]
    ry = math.radians(float(cam['ry'][0]))
    fwd = [-math.sin(ry), 0.0, -math.cos(ry)]
    ax = E[b + 5][:3]
    return {'uE_centre': [round(x, 5) for x in E[b + 4][:3]], 'cam_pos': [round(x, 5) for x in pos],
            'uE_axis': [round(x, 5) for x in ax], 'cam_fwd': [round(x, 5) for x in fwd],
            'centre_err': max(abs(a - b_) for a, b_ in zip(E[b + 4][:3], pos)),
            'axis_err': max(abs(a - b_) for a, b_ in zip(ax, fwd)), 'sdf_type': E[b + 3][0]}


def a5_glow(c):
    """A5: glow rows of the glowing effector + what the splat output shows (layers vs srender)."""
    import numpy as np
    g = _chop_rows(c.op('eng_glow'))
    lay = _grid(c.op('layers'))
    srd = _grid(c.op('srender'))
    return {'glows': int(c.op('eng_info')['glows'][0]), 'sw_render': int(c.op('sw_render').par.index.eval()),
            'rows': [[round(x, 4) for x in r] for r in g[:4]],
            'layers_rgb_mean': round(float(lay[..., :3].mean()), 4), 'srender_rgb_mean': round(float(srd[..., :3].mean()), 4)}
