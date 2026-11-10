"""fx_track_checks: live checks for /project1/lab/FX_track (docs/builds/fx_track.md LIVE CHECKS). Runs INSIDE TD via
td_exec, in TWO execs: one that changes things, a later one that reads pixels (T-74 / T-111 (4)):
    K = dict(globals()); exec(open('<repo>/builders/fx_track_checks.py').read(), K); K['tracker_parity'](c)
Generic helpers (solo, rest, still, play, diff, cost / cost_result, fps / fps_result, presets_check / presets_read,
mod_pars) come from builders/fx_stylise_checks.py (read-only reuse: same rack). ASCII only."""
import importlib
import sys

import numpy as np

REPO_B = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
if REPO_B not in sys.path:
    sys.path.insert(0, REPO_B)
exec(open(REPO_B + '/fx_stylise_checks.py').read(), globals())


def _libs():
    import fx_track_lib as FL
    import fx_track_logic as FG
    import palette_map_logic as PM
    importlib.reload(FL)
    importlib.reload(FG)
    return FL, FG, PM


def rack_vals(c):
    det = c.par.Detector.menuIndex
    cx, cy = int(c.par.Cellsx.eval()), int(c.par.Cellsy.eval())
    n = cx * cy if det == 0 else int(c.par.Maxblobs.eval())
    return {'Detector': det, 'Cellsx': cx, 'Cellsy': cy, 'N': n, 'Threshold': float(c.par.Threshold.eval()),
            'Resw': float(c.par.Resw.eval()), 'Resh': float(c.par.Resh.eval())}


def arr(o):
    return o.numpyArray(delayed=False).astype(np.float64)


def freeze(c, on=True):
    """Exec 1 of every parity read: the clip paused (play off) so det_fb = det (motion 0 next frames)."""
    c.par.Input = 'test'
    c.op('test_clip').par.play = not on
    return {'frozen': on}


def tracker_parity(c):
    """det vs det_ref(trk_src, det_fb), cells vs cells_ref(det), trk_pts vs pts_ref(cells, bt_pack, trk_pts_fb).
    Read with the picture still (freeze) >= 3 frames after the last change."""
    FL, _FG, _PM = _libs()
    rk = rack_vals(c)
    src = arr(c.op('trk_src'))
    det_fb = arr(c.op('det_fb'))
    det = arr(c.op('det'))
    cells = arr(c.op('cells'))
    pts = arr(c.op('trk_pts'))
    pfb = arr(c.op('trk_pts_fb'))
    H, W = det.shape[:2]
    dref = FL.det_ref(src, det_fb, W, H, c.par.Key.menuIndex, float(c.par.Keygain.eval()),
                      float(c.par.Motiongain.eval()))
    r = {'det_max': float(np.abs(dref[..., :3] - det[..., :3]).max())}
    cref = FL.cells_ref(det, rk['Cellsx'], rk['Cellsy'], rk['Threshold'], c.par.Cellpick.menuIndex)
    if rk['Detector'] == 0:
        dc = np.abs(cref - cells)
        r['cells_max'] = float(dc.max())
        r['cells_valid_mismatch'] = int(((cref[:, 0::2, 2] > 0) != (cells[:, 0::2, 2] > 0)).sum())
    blobs = arr(c.op('bt_sel')) if rk['Detector'] == 1 else None
    now = float(pts[-1, -1, 0])                                # the clock texel of this cook
    pref = FL.pts_ref(rk['Detector'], cells, blobs, pfb, rk['N'], rk['Cellsx'], FL.WX,
                      FL.WX * rk['Resh'] / max(1, rk['Resw']), now, float(c.par.Smooth.eval()),
                      float(c.par.Minfill.eval()))
    r['pts_shape'] = list(pts.shape)
    r['pts_max'] = float(np.abs(pref - pts).max()) if pref.shape == pts.shape else 'shape %s' % (pref.shape,)
    valid = [i for i in range(rk['N']) if FL.pt(pts, i, 0)[3] > 0.5]
    r['valid'] = len(valid)
    r['valid_ref'] = sum(1 for i in range(rk['N']) if FL.pt(pref, i, 0)[3] > 0.5)
    if rk['Detector'] == 1:
        r['bt_rows'] = int(c.op('bt_info').numRows) - 1
    return r


def _pal(m, PM):
    ch = m.op('pal')
    rows = [[ch['r'][i], ch['g'][i], ch['b'][i], ch['pos'][i]] for i in range(ch.numSamples)]
    fx = m.op('fx')
    ctl = None
    for k in range(int(fx.seq.vec.numBlocks)):
        if getattr(fx.par, 'vec%dname' % k).eval() == 'uPalCtl':
            ctl = [float(getattr(fx.par, 'vec%dvalue%s' % (k, a)).eval()) for a in 'xyzw']
    return lambda t: PM.pal_eval(rows, ctl, t)


def module_parity(c, name, samples=400, seed=1, near=0.7):
    """Module fx vs its fx_track_logic pixel reference at `samples` pixels (share `near` taken next to valid points
    so the drawn parts are tested, the rest random). Over-tol share at 2/255 + max."""
    FL, FG, PM = _libs()
    m = c.op(name)
    mod = c.op('slots')[name, 'module'].val
    rk = rack_vals(c)
    P = mod_pars(m)
    I = arr(m.op('in1'))
    O = arr(m.op('fx'))
    pts = arr(m.op('pts'))
    H, W = O.shape[:2]
    res = (float(W), float(H))
    pal = _pal(m, PM)
    t = float(m.op('fx').par.vec6valuex.eval()) if mod == 'hud' else 0.0
    rng = np.random.default_rng(seed)
    valid = [i for i in range(rk['N']) if FL.pt(pts, i, 0)[3] > 0.5]
    px = []
    for k in range(samples):
        if valid and rng.random() < near:
            T1 = FL.pt(pts, valid[int(rng.integers(len(valid)))], 1)
            x = int(np.clip(T1[0] * W + rng.normal() * 30, 0, W - 1))
            y = int(np.clip(T1[1] * H + rng.normal() * 30, 0, H - 1))
        else:
            x, y = int(rng.integers(W)), int(rng.integers(H))
        px.append((x, y))
    if mod == 'plexus':
        B = arr(m.op('lines/out1'))
        ref = [FG.plexus_pixel(p, B[p[1], p[0]], I[p[1], p[0]], pts, P, rk, res, pal) for p in px]
    elif mod == 'hud':
        ref = [FG.hud_pixel(p, I[p[1], p[0]], pts, P, rk, res, pal, t) for p in px]
    else:
        hs = arr(m.op('hs'))
        ta = float(m.op('fx').par.vec6valuew.eval())
        ref = [FG.analytics_pixel(p, I, pts, hs, P, rk, res, pal, ta) for p in px]
    got = np.array([O[p[1], p[0]] for p in px])
    ref = np.array(ref)
    d = np.abs(got - ref).max(-1)
    lit = float((np.abs(got - np.array([I[p[1], p[0]] for p in px])).max(-1) > 2.0 / 255).mean())
    worst = int(np.argmax(d))
    return {'module': mod, 'n': len(px), 'valid_pts': len(valid), 'over_tol': float((d > 2.0 / 255).mean()),
            'max': float(d.max()), 'lit_share': lit, 'worst_px': px[worst], 'worst_got': got[worst].round(4).tolist(),
            'worst_ref': ref[worst].round(4).tolist()}


def hs_parity(c, name):
    """analytics hs vs hs_step(det, pts, hs_fb, now = stats texel w)."""
    FL, FG, _PM = _libs()
    m = c.op(name)
    rk = rack_vals(c)
    hs, fb = arr(m.op('hs')), arr(m.op('hs_fb'))
    det, pts = arr(m.op('det')), arr(m.op('pts'))
    now = float(hs[-1, 0, 3])
    ref = FG.hs_step(det, pts, fb, mod_pars(m), rk, now)
    d = np.abs(ref - hs)
    return {'heat_max': float(d[:-1, :, :2].max()), 'stats_max': float(d[-1].max()), 'count': float(hs[-1, 0, 0]),
            'movers': float(hs[-1, 0, 1]), 'count_ref': float(ref[-1, 0, 0]), 'heat_mean': float(hs[:-1, :, 0].mean())}


def lines_segments(c, name):
    """PX_lines seg texture of the plexus: valid connect segments vs the pairs within radius (each point's Cnk
    nearest, as px_lines_logic connect)."""
    FL, _FG, _PM = _libs()
    m = c.op(name)
    rk = rack_vals(c)
    seg = arr(m.op('lines/seg'))
    pts = arr(m.op('pts'))
    R = float(m.op('lines').par.Cnradius.eval())
    K = int(m.par.Neighbours.eval())
    sub = int(m.par.Pieces.eval())
    P = np.array([FL.pt(pts, i, 0)[:3] for i in range(rk['N'])])
    want = 0
    for i in range(rk['N']):
        d = np.linalg.norm(P - P[i], axis=1)
        d[i] = np.inf
        want += min(K, int((d < R).sum()))
    srcs = seg[:, 3::4, 3].ravel()
    got = int((srcs > 3.5).sum())
    return {'segments_valid': got, 'expected': want * sub, 'radius_world': R}


def cost_all(c, frames=120):
    """Per-frame pull of the rack out1: sum cpu + gpu of EVERY TOP inside the rack (tracker + modules + PX_lines) that
    cooked in that frame (test clip and In TOPs excluded) + per-op medians. Exec 2: cost_all_result(c). Pane off the
    COMP (viewers would pull extra ops, T-111 (5))."""
    c.storage['ft_cost'] = {'ms': [], 'per': []}
    code = ("c = op(%r); c.op('out1').cook(force=True); "
            "L = [x for x in c.findChildren(type=TOP) if x.OPType not in ('inTOP', 'moviefileinTOP')]; "
            "f = max(x.cookAbsFrame for x in L); A = [x for x in L if x.cookAbsFrame == f]; "
            "c.storage['ft_cost']['ms'].append(sum(x.cpuCookTime + x.gpuCookTime for x in A)); "
            "c.storage['ft_cost']['per'].append(dict((x.path[len(c.path) + 1:], round(x.cpuCookTime + x.gpuCookTime, 3)) "
            "for x in A))") % c.path
    for k in range(frames):
        run(code, delayFrames=k + 1)                                          # noqa: F821
    return {'frames': frames}


def cost_all_result(c, top=8):
    st = c.storage.get('ft_cost', {})
    ms = sorted(st.get('ms', [])[10:])
    if not ms:
        return {'ms': None}
    per = {}
    for row in st.get('per', [])[10:]:
        for k, v in row.items():
            per.setdefault(k, []).append(v)
    per = sorted(((sorted(v)[len(v) // 2], k) for k, v in per.items()), reverse=True)[:top]
    return {'median_ms': round(ms[len(ms) // 2], 3), 'p90_ms': round(ms[int(len(ms) * 0.9)], 3), 'n': len(ms),
            'top_ops': [(k, v) for v, k in per]}


# ------------------------------------------------------------------ GEN_interactive strings (lane F)
def strings_parity(m):
    """One-cook parity: state_fb (prev) + pts + mask read in the same exec as step; step vs
    gen_interactive_strings_logic.step(prev, ...) with now / epoch from the step's own meta row and the rack beats
    of that cook (meta texel 1)."""
    ns = {}
    exec(open(REPO_B + '/gen_interactive_strings_logic.py').read(), ns)
    prev = arr(m.op('state_fb'))
    st = arr(m.op('step'))
    pts = arr(m.op('pts'))[0]
    msk = arr(m.op('mask'))
    P = mod_pars(m)
    S = int(P['Strings'])
    in1 = m.op('in1')
    W, H = float(in1.width), float(in1.height)
    drv = m.parent().op('drive')
    U = {'now': float(st[S, 0, 2]), 'epoch': float(st[S, 0, 3]), 'beats': float(st[S, 1, 0]),
         'level': float(drv['level']) if drv is not None else 0.0}
    ref = ns['step'](prev, pts, msk, P, U, W, H)
    d = np.abs(ref - st)
    off = np.abs(st[:S, :, :2])
    return {'pos_max': float(d[:S, :, :2].max()), 'vel_max': float(d[:S, :, 2:].max()), 'meta_max': float(d[S].max()),
            'max_offset_px': float(off.max()), 'dt': float(st[S, 0, 2] - prev[S, 0, 2]) if prev.shape == st.shape else None}


def strings_draw_parity(m, samples=600, seed=1):
    """draw vs pixel() + look() at sampled pixels (half of them on string rest columns)."""
    ns = {}
    exec(open(REPO_B + '/gen_interactive_strings_logic.py').read(), ns)
    import gen_sim_logic as GL
    importlib.reload(GL)
    st = arr(m.op('step'))
    I = arr(m.op('in1'))
    O = arr(m.op('draw'))
    P = mod_pars(m)
    for n in ('Colora', 'Colorb'):
        for ch in 'rgb':
            P[n + ch] = float(getattr(m.par, n + ch).eval())
    H, W = O.shape[:2]
    S, K = int(P['Strings']), int(P['Nodes'])
    T = float(st[S, 0, 1])
    eight = 'fixed' in str(m.op('in1').pixelFormat) or float(O.max()) <= 1.0
    rng = np.random.default_rng(seed)
    bad, mx, lit = 0, 0.0, 0
    for i in range(samples):
        if i % 2 == 0:
            s, k = int(rng.integers(S)), int(rng.integers(K))
            x, y = ns['rest'](s, k, S, K, P, W, H)
            x, y = int(np.clip(x + st[s, k, 0] + rng.normal() * 2, 0, W - 1)), int(np.clip(y + st[s, k, 1], 0, H - 1))
        else:
            x, y = int(rng.integers(W)), int(rng.integers(H))
        core, glow, t = ns['pixel'](x, y, st, P, W, H)
        ref = ns['look'](I[y, x], core, glow, t, T, P, GL.palette, GL.blend)
        if eight:
            ref = np.clip(ref, 0.0, 1.0)                                      # 8-bit draw (format useinput)
        d = float(np.abs(ref - O[y, x]).max())
        mx = max(mx, d)
        bad += d > 2.0 / 255
        lit += (core + glow) > 0.05
    return {'n': samples, 'over_tol': bad / float(samples), 'max': mx, 'lit': lit}


# ------------------------------------------------------------------ GEN_interactive parallax (lane F)
def parallax_parity(m, samples=600, seed=1):
    """fx vs gen_interactive_parallax_logic.pixel at sampled pixels, with the offset the uniform got this cook."""
    ns = {}
    exec(open(REPO_B + '/gen_interactive_parallax_logic.py').read(), ns)
    import gen_sim_logic as GL
    importlib.reload(GL)
    fx = m.op('fx')
    base, col, dep, O = arr(m.op('in1')), arr(m.op('colsel')), arr(m.op('depsel')), arr(fx)
    P = mod_pars(m)
    for n in ('Colora', 'Colorb'):
        for ch in 'rgb':
            P[n + ch] = float(getattr(m.par, n + ch).eval())
    P['Dolly'] = float(fx.par.vec0valuez.eval())                              # the dolly the uniform got
    off = (float(fx.par.vec0valuex.eval()), float(fx.par.vec0valuey.eval()))
    eight = float(O.max()) <= 1.0
    H, W = O.shape[:2]
    rng = np.random.default_rng(seed)
    bad, mx = 0, 0.0
    for _ in range(samples):
        x, y = int(rng.integers(W)), int(rng.integers(H))
        r = ns['pixel'](x, y, base, col, dep, P, off, GL.palette, GL.blend)
        if eight:
            r = np.clip(r, 0, 1)
        d = float(np.abs(r - O[y, x]).max())
        mx = max(mx, d)
        bad += d > 2.0 / 255
    return {'n': samples, 'over_tol': bad / float(samples), 'max': mx, 'offset': off, 'dolly': P['Dolly'],
            'changed': float((np.abs(O - col).max(-1) > 2.0 / 255).mean())}


# ------------------------------------------------------------------ GEN_interactive skinner (lane F)
def skinner_parity(m, samples=600, seed=1):
    """slots one-cook parity (slots_fb + mask + slots read together), tris vs tris(slots), draw vs pixel() + look()."""
    ns = {'HERE': REPO_B}
    exec(open(REPO_B + '/gen_interactive_skinner_logic.py').read(), ns)
    import gen_sim_logic as GL
    importlib.reload(GL)
    prev, msk, sl = arr(m.op('slots_fb')), arr(m.op('mask')), arr(m.op('slots'))
    tr, I, O = arr(m.op('tris')), arr(m.op('in1')), arr(m.op('draw'))
    P = mod_pars(m)
    for n in ('Colora', 'Colorb'):
        for ch in 'rgb':
            P[n + ch] = float(getattr(m.par, n + ch).eval())
    H, W = O.shape[:2]
    R = sl.shape[0] - 1
    U = {'now': float(sl[R, 0, 2]), 'epoch': float(sl[R, 0, 3])}
    sref = ns['slots_step'](prev, msk, P, U, float(W), float(H))
    d = np.abs(sref - sl)
    vg, vr = sl[:R, :, 2] > 0.5, sref[:R, :, 2] > 0.5
    r = {'slots_max': float(d[:R].max()), 'valid': int(vg.sum()), 'valid_mismatch': int((vg != vr).sum()),
         'pos_max_both_valid': float(d[:R][vg & vr][:, :2].max()) if (vg & vr).any() else None}
    tref = ns['tris'](sl, P)
    r['tris_max'] = float(np.abs(tref - tr).max())
    r['shown'] = int((tr[:, 1::2, 2] > 0).sum())
    eight = float(O.max()) <= 1.0
    rng = np.random.default_rng(seed)
    bad, mx = 0, 0.0
    for _ in range(samples):
        x, y = int(rng.integers(W)), int(rng.integers(H))
        tot, t = ns['pixel'](x, y, tr, P)
        ref = ns['look'](I[y, x], tot, t, P, GL.palette, GL.blend)
        if eight:
            ref = np.clip(ref, 0, 1)
        e = float(np.abs(ref - O[y, x]).max())
        mx = max(mx, e)
        bad += e > 2.0 / 255
    r.update(draw_over_tol=bad / float(samples), draw_max=mx)
    return r
