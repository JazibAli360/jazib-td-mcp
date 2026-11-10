# particles_checks - live checks of BO_particles lane G (27 Oct 2026; doc docs/builds/particles.md "Lane G").
# Run inside TD through td_exec, reads in their OWN exec >= 2 frames after any change (T-74 / T-91: read twice, keep
# the second). Never in the builder (its static test forbids readbacks there).
#   ns = dict(globals()); exec(open('<repo>/builders/particles_checks.py').read(), ns)
#   ns['state'](C, 'V12', frames)  ns['lines'](C)  ns['preset_state'](C, name)  ns['passthrough'](C)
#   ns['cost_start'](C, 120) ... ns['cost_read'](C)
# ASCII only. T-70: nothing destroyed. T-64: never touches cookRate.

REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'


def _L(c):
    return c.op('particles_logic').module


def _arr(o):
    import numpy
    return numpy.array(o.numpyArray(delayed=True), dtype=numpy.float64)


def _raw(c):
    return {p.name: p.eval() for p in c.customPars if p.style != 'Pulse' and p.page.name != 'Zkit'
            and isinstance(p.eval(), (bool, int, float, str))}


def state(comp, which='V12', frames=None):
    """compare_state of the state texture vs the float64 reference. Run with Play off, >= 2 frames after.
    which: 'V1' / 'V12' (the par set the reset ran with); frames = cooked frames since the reset incl. the reset
    frame (default info frame + 1)."""
    c = op(comp)
    L = _L(c)
    arr = _arr(c.op('state'))
    raw = dict(_raw(c))
    raw.update(getattr(L, which + '_PARS'))
    F = int(c.op('info')['frame'].eval()) + 1 if frames is None else int(frames)
    w = L.compare_state(arr.tolist(), raw, F)
    w['frames'] = F
    return w


def preset_state(comp, name):
    """Every par of preset `name` (full state) equals the COMP's par now: returns the mismatches."""
    c = op(comp)
    L = _L(c)
    bad = {}
    for k, v in L.preset_pars(name).items():
        p = getattr(c.par, k, None)
        if p is None:
            bad[k] = 'missing'
            continue
        got = p.eval()
        if isinstance(v, float) or isinstance(got, float):
            if abs(float(got) - float(v)) > 1e-6:
                bad[k] = (got, v)
        elif got != v:
            bad[k] = (got, v)
    return {'preset': name, 'pars': len(L.preset_pars(name)), 'mismatch': bad}


def lines(comp):
    """PX_lines trails on the state texture: hist head of track k == P of particle floor(k * Count / tracks)
    (Trails points mode, Ptstride 3); valid history slots; rows Status (segments)."""
    import numpy
    c = op(comp)
    L = _L(c)
    lx = c.op('PX_lines')
    H = _arr(lx.op('hist'))
    S = _arr(c.op('state'))
    count = int(c.par.Count.eval())
    tracks = H.shape[0]
    side = L.side(count)
    err = 0.0
    for k in range(tracks):
        i = int(k * count // tracks)
        x, y = 3 * (i % side), i // side
        err = max(err, float(numpy.abs(H[k, 0, :3] - S[y, x, :3]).max()))
    slots = H[:, 2:, 3]
    return {'tracks': tracks, 'samples': H.shape[1] - 2, 'head_vs_state_max_err': err,
            'slots_written': float((slots > 0).mean()), 'status': str(lx.par.Status.eval()),
            'finite': bool(numpy.isfinite(H).all())}


def passthrough(comp):
    """Lineson off: sw_lines == sw_trail exactly (max diff). Call with Lineson off, >= 2 frames after."""
    import numpy
    c = op(comp)
    a, b = _arr(c.op('sw_lines')), _arr(c.op('sw_trail'))
    return {'max_diff': float(numpy.abs(a - b).max()) if a.shape == b.shape else 'shape %s vs %s' % (a.shape, b.shape)}


def palette(comp):
    """pmat's palette binding: uPalCtl (count, shift, mode, interp) and the pal CHOP rows."""
    c = op(comp)
    m = c.op('pmat')
    out = {}
    for k in range(int(m.seq.vec.numBlocks)):
        if getattr(m.par, 'vec%dname' % k).eval() == 'uPalCtl':
            out['uPalCtl'] = [float(getattr(m.par, 'vec%dvalue%s' % (k, a)).eval()) for a in 'xyzw']
    p = c.op('pal')
    out['pal'] = [[round(float(p[ch][i]), 4) for ch in ('r', 'g', 'b', 'pos')] for i in range(min(p.numSamples, 4))]
    return out


COST_CB = """def bo_cost_tick(path, k):
    m = op(path)
    o = m.op('out1')
    o.cook(force=True)
    f = o.cookAbsFrame
    cpu = gpu = 0.0
    names = {}
    for c in m.findChildren(depth=None):
        if c.family in ('TOP', 'CHOP', 'POP', 'SOP') and c.cookAbsFrame == f:
            cpu += float(getattr(c, 'cpuCookTime', 0.0) or 0.0)
            gpu += float(getattr(c, 'gpuCookTime', 0.0) or 0.0)
            names[c.path[len(path) + 1:]] = [round(float(getattr(c, 'cpuCookTime', 0.0) or 0.0), 3),
                             round(float(getattr(c, 'gpuCookTime', 0.0) or 0.0), 3)]
    st = m.fetch('bo_cost', {}, search=False)
    st.setdefault('rows', []).append([cpu, gpu, names])
    m.store('bo_cost', st)
"""


def cost_start(comp, n=120):
    """T-102: pull out1 once a frame for n frames (one queued sampler, never overlapping, T-124 (3)); read with
    cost_read() > n frames later. Sums cpu + gpu of the COMP's ops cooked in that frame (PX_lines children too)."""
    m = op(comp)
    m.store('bo_cost', {'rows': []})
    script = COST_CB + 'bo_cost_tick(args[0], args[1])\n'
    for k in range(n):
        run(script, comp, k, delayFrames=k + 1)
    return {'cost_started': comp, 'frames': n}


def cost_read(comp):
    m = op(comp)
    rows = (m.fetch('bo_cost', {}, search=False) or {}).get('rows', [])
    if not rows:
        return {'rows': 0}
    med = lambda v: sorted(v)[len(v) // 2]
    tot = [r[0] + r[1] for r in rows]
    per = {}
    for r in rows:
        for k, v in r[2].items():
            per.setdefault(k, []).append(v)
    ops = sorted(((k, round(sum(a + b for a, b in v) / len(rows), 3), round(med([a for a, _b in v]), 3),
                   round(med([b for _a, b in v]), 3), len(v)) for k, v in per.items()), key=lambda r: -r[1])
    m.unstore('bo_cost')
    return {'rows': len(rows), 'median_ms': round(med(tot), 3), 'p90_ms': round(sorted(tot)[int(0.9 * (len(tot) - 1))], 3),
            'cpu_median_ms': round(med([r[0] for r in rows]), 3), 'gpu_median_ms': round(med([r[1] for r in rows]), 3),
            'per_op': dict((k, {'mean_ms': t, 'cpu_med': a, 'gpu_med': b, 'cooks': n}) for k, t, a, b, n in ops[:10])}
