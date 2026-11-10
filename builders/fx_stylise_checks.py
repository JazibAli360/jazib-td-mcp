"""fx_stylise_checks: live checks for /project1/lab/FX_stylise and /project1/lab/FX_glass (docs/builds/fx_stylise.md,
fx_glass.md LIVE CHECKS). Runs INSIDE TD via td_exec, always in TWO execs: one that changes things (setup / schedule),
one later that reads pixels (T-74 / T-111 (4): never read pixels in the exec that changed them):
    K = dict(globals()); exec(open('<repo>/builders/fx_stylise_checks.py').read(), K); K['solo'](c, 'outline1')
Generic: solo, still (test clip paused on a real frame, T-157 (3)), diff (out1 vs img_src), cost / cost_result
(T-157 (2) frame filter, In TOPs excluded), fps / fps_result (real frames over wall time, T-124 (4)), presets_check.
Module: outline_jfa (JFA vs numpy mirror + brute force on sampled texels), outline_parity. ASCII only."""
import sys

import numpy as np

REPO_B = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
if REPO_B not in sys.path:
    sys.path.insert(0, REPO_B)


def solo(c, name, enabled=1, mix=1):
    """Only slot `name` enabled (others 0), mix as given; Panic off."""
    t = c.op('slots')
    for i in range(1, t.numRows):
        t[i, 'enabled'] = enabled if t[i, 'name'].val == name else 0
        if t[i, 'name'].val == name:
            t[i, 'mix'] = mix
    c.par.Panic = False
    return {'solo': name}


def rest(c):
    """Rest state: every slot enabled 0, mix 1, Panic off."""
    t = c.op('slots')
    for i in range(1, t.numRows):
        t[i, 'enabled'] = 0
        t[i, 'mix'] = 1
    c.par.Panic = False
    return {'rest': [t[i, 'name'].val for i in range(1, t.numRows)]}


def still(c):
    """Test clip paused where it is (play it first for a second so it shows a real frame; check img_src mean > 0 in
    the next exec, T-157 (3))."""
    c.par.Input = 'test'
    c.op('test_clip').par.play = False
    return {'still': True}


def play(c, on=True):
    c.par.Input = 'test'
    c.op('test_clip').par.play = bool(on)
    return {'play': bool(on)}


def img(o):
    return o.numpyArray(delayed=False).astype(np.float64)


def diff(c, a='img_src', b='out1'):
    A, B = img(c.op(a)), img(c.op(b))
    d = np.abs(A - B)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'src_mean': float(A[..., :3].mean()),
            'src_std': float(A[..., :3].std()), 'changed': float((d.max(-1) > 1.0 / 255).mean())}


def mod_pars(m, names=None):
    """Module par values (menus as index, toggles as int) for the numpy mirrors."""
    out = {}
    for p in m.customPars:
        if names and p.name not in names:
            continue
        if p.isMenu:
            out[p.name] = p.menuIndex
        elif p.isToggle:
            out[p.name] = int(p.eval())
        elif p.isNumber:
            out[p.name] = float(p.eval())
    return out


def set_pars(m, vals):
    for k, v in vals.items():
        p = getattr(m.par, k)
        if p.isMenu and isinstance(v, int):
            p.menuIndex = v
        else:
            p.val = v


def defaults(m, module_ns):
    """Reset a module's pars to its page defaults (full state)."""
    for _pg, pl in module_ns['PAGES']:
        for n, s, d, o in pl:
            if s == 'Pulse':
                continue
            getattr(m.par, n).val = d


# ------------------------------------------------------------------ cost + fps
def cost(c, name, frames=120):
    """Schedule a per-frame pull of module `name`'s out1: sum cpu + gpu ms of its TOPs that cooked in the newest
    cook frame among them (T-157 (2)), In TOPs excluded. Exec 2: cost_result(c)."""
    c.storage['fxs_cost'] = {'name': name, 'ms': [], 'gpu': []}
    code = ("c = op(%r); m = c.op(%r); o = m.op('out1'); o.cook(force=True); "
            "L = [x for x in m.findChildren(depth=1) if x.family == 'TOP' and x.OPType != 'inTOP']; "
            "f = max(x.cookAbsFrame for x in L); "
            "c.storage['fxs_cost']['ms'].append(sum(x.cpuCookTime + getattr(x, 'gpuCookTime', 0) for x in L "
            "if x.cookAbsFrame == f)); "
            "c.storage['fxs_cost']['gpu'].append(dict((x.name, round(getattr(x, 'gpuCookTime', 0), 3)) for x in L "
            "if x.cookAbsFrame == f))") % (c.path, name)
    for k in range(frames):
        run(code, delayFrames=k + 1)                                          # noqa: F821
    return {'module': name, 'frames': frames}


def cost_result(c):
    st = c.storage.get('fxs_cost', {})
    ms = sorted(st.get('ms', [])[10:])
    if not ms:
        return {'ms': None}
    g = st.get('gpu', [])[10:]
    per = {}
    for row in g:
        for k, v in row.items():
            per.setdefault(k, []).append(v)
    per = dict((k, sorted(v)[len(v) // 2]) for k, v in per.items())
    return {'median_ms': round(ms[len(ms) // 2], 3), 'p90_ms': round(ms[int(len(ms) * 0.9)], 3), 'n': len(ms),
            'gpu_median_per_op': per}


def fps(c, frames=300):
    """Real frames over wall time: two runs `frames` frames apart store time.time(). Exec 2: fps_result(c)."""
    c.storage['fxs_fps'] = {'t': []}
    code = "import time; op(%r).storage['fxs_fps']['t'].append(time.time())" % c.path
    run(code, delayFrames=1)                                                  # noqa: F821
    run(code, delayFrames=frames + 1)                                         # noqa: F821
    c.storage['fxs_fps']['frames'] = frames
    return {'frames': frames}


def fps_result(c):
    st = c.storage.get('fxs_fps', {})
    t = st.get('t', [])
    if len(t) < 2:
        return {'fps': None}
    return {'fps': round(st['frames'] / (t[1] - t[0]), 2), 'cookRate': project.cookRate}  # noqa: F821


# ------------------------------------------------------------------ presets (zkit, full state)
def presets_check(m, module_ns, slot):
    """Exec 1: recall preset `slot` (twice: T-157 (1)); exec 2: presets_read(m, module_ns, slot)."""
    rt = m.op('controls/zk_rt').module
    rt.Recall(slot)
    rt.Recall(slot)
    return {'recalled': slot}


def presets_read(m, module_ns, slot):
    want = next(v for s, _n, v in module_ns['PRESETS'] if s == slot)
    bad = {}
    for k, v in want.items():
        p = getattr(m.par, k)
        got = p.menuIndex if p.isMenu else (int(p.eval()) if p.isToggle else p.eval())
        if (isinstance(v, float) and abs(float(got) - v) > 1e-6) or (not isinstance(v, float) and got != v):
            bad[k] = [got, v]
    return {'slot': slot, 'n': len(want), 'mismatch': bad}


# ------------------------------------------------------------------ outline
def _outline_logic():
    import importlib
    import fx_stylise_outline_logic as L
    importlib.reload(L)
    return L


def outline_jfa(m, samples=20000, seed=1):
    """GPU seed map -> numpy JFA mirror (same algorithm) vs the GPU jfa: share of identical picks; GPU JFA distance
    vs brute force at `samples` random texels: max / p99 error (texels)."""
    L = _outline_logic()
    S = m.op('seed').numpyArray(delayed=False).astype(np.float32)
    J = m.op('jfa').numpyArray(delayed=False).astype(np.float32)
    extra = int(m.par.Extra.eval())
    Pm = int(round(m.op('jfa').par.vec0valuez.eval()))
    reach = 2 ** Pm - 1                                                       # texels the steps can reach
    ref = L.jfa_pm(S, Pm, extra)
    same = float((np.abs(ref[..., :3] - J[..., :3]).max(-1) < 1e-3).mean())
    pts = S[S[..., 2] > 0][:, :2].astype(np.float64)
    H, W = S.shape[:2]
    rng = np.random.default_rng(seed)
    ys, xs = rng.integers(0, H, samples), rng.integers(0, W, samples)
    q = np.stack([xs + 0.5, ys + 0.5], -1)
    best = np.full(samples, np.inf)
    for i in range(0, len(pts), 512):
        P = pts[i:i + 512]
        best = np.minimum(best, ((q[:, None, :] - P[None, :, :]) ** 2).sum(-1).min(1))
    bf = np.sqrt(best)
    jd = L.jfa_dist(J)[ys, xs]
    e = np.abs(jd - bf)
    e = e[np.isfinite(e) & (bf <= reach)]
    return {'seeds': int(len(pts)), 'jfa_size': [W, H], 'npasses': int(m.op('jfa').par.npasses.eval()), 'Pm': Pm,
            'in_reach_samples': int(len(e)),
            'same_as_mirror': same, 'bf_max_err_texels': float(e.max()) if len(e) else None,
            'bf_p99_err': float(np.percentile(e, 99)) if len(e) else None}


def outline_parity(m):
    """out1 vs the numpy mirror fed with in1 (Colsrc solid, Wobble 0, Speed 0 + Phase -> _phase)."""
    L = _outline_logic()
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    P['_phase'] = P.get('Phase', 0.0)
    ref, sd, _j = L.reference(I, P, int(P.get('Extra', 1)))
    if not P.get('Hdr'):
        ref = np.clip(ref, 0, 1)                                              # 8-bit out (format useinput)
    r = L.compare(O, ref)
    r['lit'] = float((np.abs(O - I).max(-1) > 2.0 / 255).mean())
    return r


# ------------------------------------------------------------------ boil
def _logic(name):
    import importlib
    mod = importlib.import_module(name)
    importlib.reload(mod)
    return mod


def boil_parity(m):
    """out1 vs fx_stylise_boil_logic.look(held, in1, pars, seed from the fx uniform) (Fill palette excluded).
    Read with the clip paused and Holdfps low so the tick (seed) does not change between cook and read."""
    L = _logic('fx_stylise_boil_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    Hd = m.op('hsrc').numpyArray(delayed=False).astype(np.float32)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    k = m.op('fx').par.vec1valuez.eval()
    ref = np.clip(L.look(Hd, I, P, int(k)), 0, 1)
    r = L.X.compare(O, ref)
    r['seed'] = k
    r['ink_share'] = L.edge_share(O, I)
    return r


def boil_hold(c, m, frames=120):
    """Exec 1: record stamp.y (time of the last tick) every frame; exec 2 (>= frames later): boil_hold_result."""
    c.storage['fxs_hold'] = []
    code = ("m = op(%r); s = m.op('stamp').numpyArray(delayed=False)[0, 0]; "
            "m.parent().storage['fxs_hold'].append(float(s[1]))") % m.path
    for k in range(frames):
        run(code, delayFrames=k + 1)                                          # noqa: F821
    return {'frames': frames, 'holdfps': m.par.Holdfps.eval()}


def boil_hold_result(c):
    ys = c.storage.get('fxs_hold', [])
    return {'samples': len(ys), 'distinct_ticks': len(set(ys))}


# ------------------------------------------------------------------ ink
def ink_parity(m):
    """(a) GPU blurv vs fx_stylise_ink_logic.blur2(in1) (16F store); (b) out1 vs look(in1, GPU blurv) (palette fills
    excluded)."""
    L = _logic('fx_stylise_ink_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    G = m.op('blurv').numpyArray(delayed=False).astype(np.float64)[..., :2]
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    ref_g = L.blur2(I, P['Sigma'], P['K'])
    r = {'blur_max': float(np.abs(ref_g - G).max())}
    ref = np.clip(L.look(I, G, P), 0, 1)
    r.update(L.X.compare(O, ref))
    r['ink_share'] = float((L.X.luma(O) < 0.2).mean())
    return r


# ------------------------------------------------------------------ saber
def saber_parity(m):
    """out1 vs fx_stylise_saber_logic (Distort 0, Flicker 0, Colsrc solid): path from the segs CHOP, masks from the
    mirror's own seed + JFA of in1 / mfit."""
    L = _logic('fx_stylise_saber_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    H, W = I.shape[:2]
    s = m.op('segs')
    n = int(m.op('segs_callbacks').module.count(m))
    pts = [[s['x'][i], s['y'][i], s['u'][i], s['pen'][i]] for i in range(n)]
    tipd = np.full((H, W), 1e6)
    if P['Source'] == 0:
        d, u, tipd = L.path_distance(W, H, pts, P['Start'], P['End'], P['Pathunits'] == 1)
    else:
        src = I if P['Source'] == 1 else m.op('mfit').numpyArray(delayed=False).astype(np.float32)
        Pm = int(round(m.op('jfa').par.vec0valuez.eval()))
        d, u = L.mask_distance(src, P, Pm)
    ref = L.look(I, d, u, tipd, P)
    if not P.get('Hdr'):
        ref = np.clip(ref, 0, 1)
    r = L.X.compare(O, ref)
    r['lit'] = float((np.abs(O - I).max(-1) > 2.0 / 255).mean())
    r['npts'] = n
    return r


# ------------------------------------------------------------------ clean
def clean_parity(m):
    """out1 vs fx_stylise_clean_logic.clean(in1) (16F intermediate not modelled) + the noise drop vs in1."""
    L = _logic('fx_stylise_clean_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float64)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    ref = np.clip(L.clean(I, P), 0, 1)
    r = L.X.compare(O, ref)
    hp = lambda a: a[1:-1, 1:-1, :3] - 0.25 * (a[:-2, 1:-1, :3] + a[2:, 1:-1, :3] + a[1:-1, :-2, :3] + a[1:-1, 2:, :3])
    r['hf_in'] = float(hp(I).std())
    r['hf_out'] = float(hp(O).std())
    return r


# ------------------------------------------------------------------ watercolour
def watercolour_parity(m):
    """(a) GPU wash vs fx_stylise_watercolour_logic.wash(in1) (16F); (b) out1 vs look(in1, GPU wash) (palette off)."""
    L = _logic('fx_stylise_watercolour_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    Wg = m.op('wash').numpyArray(delayed=False).astype(np.float64)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    wref = L.wash(I, P)
    r = {'wash_max': float(np.abs(wref - Wg).max()), 'wash_over': float((np.abs(wref - Wg).max(-1) > 2.0 / 255).mean())}
    ref = np.clip(L.look(I, Wg, P), 0, 1)
    r.update(L.X.compare(O, ref))
    return r


# ------------------------------------------------------------------ engrave
def engrave_parity(m):
    """out1 vs fx_stylise_engrave_logic.look(in1) (Speed 0, palette fill excluded)."""
    L = _logic('fx_stylise_engrave_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    ref = np.clip(L.look(I, P, m.op('fx').par.vec3valuex.eval()), 0, 1)
    return L.X.compare(O, ref)


# ------------------------------------------------------------------ kuwahara
def kuwahara_parity(m, win=(200, 400, 48, 48)):
    """(a) GPU tblur vs mirror tblur(tensor(in1)) (16F); (b) GPU kuw on a texel window vs the mirror fed with the GPU
    tblur (a crop: the full mirror would block TD for minutes); (c) out1 vs up(in1, GPU kuw)."""
    L = _logic('fx_stylise_kuwahara_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    TB = m.op('tblur').numpyArray(delayed=False).astype(np.float64)
    KW = m.op('kuw').numpyArray(delayed=False).astype(np.float64)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    tref = L.tblur(L.tensor(I, L.div(P)))
    r = {'tensor_max_rel': float(np.abs(tref[..., :3] - TB[..., :3]).max() / max(float(np.abs(tref[..., :3]).max()), 1e-9))}
    x0, y0, w, h = win
    kref = L.kuwahara(I, TB, P, win)
    d = np.abs(kref[..., :3] - KW[y0:y0 + h, x0:x0 + w, :3])
    r['kuw_max'] = float(d.max())
    r['kuw_over'] = float((d.max(-1) > 2.0 / 255).mean())
    ref = np.clip(L.up(I, KW, P['Amount']), 0, 1)
    r.update(L.X.compare(O, ref))
    return r


# ------------------------------------------------------------------ FX_glass liquid
def liquid_parity(m):
    """out1 vs fx_glass_liquid_logic.look(in1, GPU backdrop bd, shapes table) (Source shapes, Drift 0, solid tint)."""
    L = _logic('fx_glass_liquid_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    BD = m.op('bd').numpyArray(delayed=False).astype(np.float64)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    t = m.op('shapes')
    shapes = L.shapes_from_rows([[c.val for c in t.row(i)] for i in range(t.numRows)])
    ref = np.clip(L.look(I, BD, shapes, P, m.op('fx').par.vec5valuey.eval()), 0, 1)
    r = L.X.compare(O, ref)
    r['glass_px'] = float((np.abs(O - I).max(-1) > 2.0 / 255).mean())
    return r


def foil_parity(m):
    """out1 vs fx_glass_foil_logic.look(in1) with the phase / noise time read from the fx uniforms (Speed 0,
    Noisespeed 0 for a stable read; palette mode excluded)."""
    L = _logic('fx_glass_foil_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    fx = m.op('fx')
    ref = np.clip(L.look(I, P, fx.par.vec0valuew.eval(), fx.par.vec2valuew.eval()), 0, 1)
    return L.X.compare(O, ref)


def rain_parity(m):
    """out1 vs fx_glass_rain_logic.look(in1, GPU backdrop, t from the fx uniform) (Speed 0 for a stable read)."""
    L = _logic('fx_glass_rain_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    BD = m.op('bd').numpyArray(delayed=False).astype(np.float64)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    ref = np.clip(L.look(I, BD, P, m.op('fx').par.vec1valuex.eval()), 0, 1)
    r = L.X.compare(O, ref)
    r['changed'] = float((np.abs(O - I).max(-1) > 2.0 / 255).mean())
    return r


def frost_parity(m):
    """out1 vs fx_glass_frost_logic.look(in1, GPU backdrop, tick from the fx uniform) (Animate 0)."""
    L = _logic('fx_glass_frost_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    BD = m.op('bd').numpyArray(delayed=False).astype(np.float64)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    ref = np.clip(L.look(I, BD, P, int(m.op('fx').par.vec0valuew.eval())), 0, 1)
    return L.X.compare(O, ref)


def floor_parity(m):
    """out1 vs fx_glass_floor_logic.look(in1, GPU backdrop, ripple time from the fx uniform) (Ripplespeed 0,
    Tilesrc solid)."""
    L = _logic('fx_glass_floor_logic')
    I = m.op('in1').numpyArray(delayed=False).astype(np.float32)
    BD = m.op('bd').numpyArray(delayed=False).astype(np.float64)
    O = m.op('out1').numpyArray(delayed=False).astype(np.float64)
    P = mod_pars(m)
    ref = np.clip(L.look(I, BD, P, m.op('fx').par.vec2valuez.eval()), 0, 1)
    return L.X.compare(O, ref)
