# px_lines_checks.py - live checks of PX_lines inside TD (lane W1-C; doc docs/builds/px_lines.md LIVE CHECKS).
# exec'd by td_exec on the assigned TD: harness() makes a disposable /project1/lab/PL_harness (test TOPs / CHOP) and
# wires it into PX_lines; case(name) sets the pars of one check; check(name) reads the textures (numpyArray delayed,
# call it in a SEPARATE exec >= 2 frames after case(), twice, keep the second: T-74 / T-91) and compares them with
# px_lines_logic's references. drop_harness() removes the harness (safe_destroy). Pure ASCII.
import math

LAB = '/project1/lab'
COMP = LAB + '/PX_lines'
H = LAB + '/PL_harness'

SPHERE = '''// 4096 Fibonacci-sphere points, 64 x 64, xyz + 1
layout (local_size_x = 8, local_size_y = 8) in;
void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	if (g.x >= 64 || g.y >= 64) return;
	float i = float(g.y * 64 + g.x);
	float y = 1.0 - 2.0 * (i + 0.5) / 4096.0;
	float r = sqrt(max(1.0 - y * y, 0.0));
	float a = i * 2.39996322973;
	TDImageStoreOutput(0, ivec3(g, 0), vec4(r * cos(a), y, r * sin(a), 1.0));
}
'''
MOVER = '''// 16 points on a row: x = 0.1 * frame, y = index
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uF;
void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	if (g.x >= 16 || g.y >= 1) return;
	float x = 0.1 * uF.x + (g.x == 5 ? uF.y : 0.0);
	TDImageStoreOutput(0, ivec3(g, 0), vec4(x, float(g.x), 0.0, 1.0));
}
'''
CHART = '''// white half-size square (alpha 1) on transparent black, 216 x 384
layout (local_size_x = 8, local_size_y = 8) in;
void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	if (g.x >= 216 || g.y >= 384) return;
	bool in_ = g.x >= 54 && g.x < 162 && g.y >= 96 && g.y < 288;
	TDImageStoreOutput(0, ivec3(g, 0), in_ ? vec4(1.0) : vec4(0.0));
}
'''
PATH_CB = '''# 4-sample square path tx ty tz (LC10)
def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tscriptOp.clear()
\tscriptOp.numSamples = 4
\tfor n, v in (('tx', (0, 1, 1, 0)), ('ty', (0, 0, 1, 1)), ('tz', (0, 0, 0, 0))):
\t\tc = scriptOp.appendChan(n)
\t\tfor i, x in enumerate(v):
\t\t\tc[i] = x
'''


def _sd(o):
    if o is not None and o.valid:
        (globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy)(o)


def _compute(h, name, code, w, hh):
    g = h.op(name) or h.create(glslTOP, name)
    g.par.mode = 'compute'
    d = h.op(name + '_compute') or h.create(textDAT, name + '_compute')
    d.text = code
    g.par.computedat = d.name
    g.par.outputresolution = 'custom'
    g.par.resolutionw, g.par.resolutionh = w, hh
    g.par.format = 'rgba32float'
    g.par.autodispatchsize = True
    return g


def harness():
    lab = op(LAB)
    h = lab.op('PL_harness') or lab.create(baseCOMP, 'PL_harness')
    h.nodeX, h.nodeY = op(COMP).nodeX - 400, op(COMP).nodeY
    sph = _compute(h, 'sphere', SPHERE, 64, 64)
    mov = _compute(h, 'mover', MOVER, 16, 1)
    mov.seq.vec.numBlocks = 1
    mov.par.vec0name = 'uF'
    mov.par.vec0valuex = 0
    mov.par.vec0valuey = 0
    ch = _compute(h, 'chart', CHART, 216, 384)
    for n in ('pts_sw', 'scene_sw'):
        s = h.op(n) or h.create(switchTOP, n)
    h.op('pts_sw').inputConnectors[0].connect(sph)
    h.op('pts_sw').inputConnectors[1].connect(mov)
    h.op('pts_sw').par.index = 0
    blank = h.op('blank') or h.create(constantTOP, 'blank')
    blank.par.outputresolution = 'custom'
    blank.par.resolutionw, blank.par.resolutionh = 270, 480
    blank.par.format = 'rgba16float'
    blank.par.colorr = blank.par.colorg = blank.par.colorb = 0
    blank.par.alpha = 0
    h.op('scene_sw').inputConnectors[0].connect(blank)
    h.op('scene_sw').inputConnectors[1].connect(ch)
    h.op('scene_sw').par.index = 0
    dep = h.op('depth') or h.create(constantTOP, 'depth')
    dep.par.outputresolution = 'custom'
    dep.par.resolutionw, dep.par.resolutionh = 270, 480
    dep.par.format = 'rgba32float'
    dep.par.colorr = 4.0
    dep.par.alpha = 1
    path = h.op('path') or h.create(scriptCHOP, 'path')
    cb = h.op('path_callbacks') or h.create(textDAT, 'path_callbacks')
    cb.text = PATH_CB
    path.par.callbacks = cb.name
    outs = []
    for k, src in enumerate(('scene_sw', 'pts_sw', 'depth')):
        o = h.op('out%d' % (k + 1)) or h.create(outTOP, 'out%d' % (k + 1))
        o.inputConnectors[0].connect(h.op(src))
        o.par.connectorder = k
        outs.append(o)
    c = op(COMP)
    for k in range(3):
        c.inputConnectors[k].connect(h.outputConnectors[k])
    return {'harness': h.path, 'in_points': [c.op('in_points').width, c.op('in_points').height],
            'in1': [c.op('in1').width, c.op('in1').height], 'in_depth': [c.op('in_depth').width]}


BASE = {'Resx': 270, 'Resy': 480, 'Maxseg': 65536, 'Rings': True, 'Contour': False, 'Trails': False,
        'Connect': False, 'Polyline': False, 'Edges': False, 'Usedepth': False, 'Occlusion': 'over', 'Reveal': 1.0,
        'Cut': 0.0, 'Ringcount': 4, 'Ringsegs': 128, 'Ringradius': 0.5, 'Ringspacing': 0.15, 'Width': 2.0,
        'Halo': 6.0, 'Blend': 'max', 'Linecolsrc': 'solid', 'Ringattr': 'along', 'Palsource': 'neon_green',
        'Palmode': 'cycle', 'Polychop': '', 'Ringcentre': (0.0, 0.0, 0.0), 'Ringnormal': (0.0, 0.0, 1.0),
        'Occbias': 0.02, 'Occsoft': 0.05, 'Ringexpand': 0.0, 'Ringtilt': 0.0, 'Ringspin': 0.0, 'Ptstride': 1, 'Ptcount': 0, 'Outmode': 'composite', 'Amount': 1.0}

CASES = {
    'rings': {},
    'radius': {'Ringcount': 1, 'Ringsegs': 256, 'Ringradius': 1.0, 'Halo': 0.0},
    'contour': {'Rings': False, 'Contour': True, 'Ctmax': 4096, 'Ctaxis': 'y', 'Ctspacing': 0.1, 'Ctband': 0.02,
                'Ctlen': 0.04, 'Cttangent': 'around', 'Ctsnap': 1.0, 'Ctspeed': 0.0, 'Ctwave': 0.0},
    'width': {'Ringcount': 1, 'Ringsegs': 256, 'Ringradius': 0.3, 'Width': 3.0, 'Halo': 0.0},
    'edges': {'Rings': False, 'Edges': True, 'Resx': 216, 'Resy': 384, 'Edwidth': 2.0, 'Edres': 'half',
              'Edthr': 0.15, 'Edsoft': 0.1, 'Edluma': 1.0, 'Edalpha': 1.0, 'Eddepth': 0.0, 'Edwipe': 0.0},
    'trails_pts': {'Rings': False, 'Trails': True, 'Trtracks': 16, 'Trsamples': 8, 'Trmotion': 'points',
                   'Trtaper': 0.0, 'Trfade': 0.0, 'Trevery': 1, 'Trmaxjump': 0.5, 'Trjitter': 0.0},
    'trails_flow': {'Rings': False, 'Trails': True, 'Trtracks': 32, 'Trsamples': 4, 'Trmotion': 'flow',
                    'Trlife': 0.1, 'Trdir': (0.0, 0.0, 0.0), 'Trcurl': 1.0, 'Trcount': 0, 'Ptcount': 0},
    'connect': {'Rings': False, 'Connect': True, 'Cnpoints': 256, 'Cnk': 3, 'Cnradius': 0.4, 'Cnsub': 3,
                'Cnjitter': 0.05, 'Cnjitterhz': 0.0},
    'polyline': {'Rings': False, 'Polyline': True, 'Poclose': True, 'Pomaxgap': 0.0},
    'occl': {'Ringcount': 1, 'Usedepth': True, 'Occlusion': 'depth', 'Occbias': 0.02, 'Occsoft': 0.05},
    'palette': {'Ringcount': 4, 'Ringsegs': 16, 'Linecolsrc': 'index', 'Ringattr': 'index', 'Palsource': 'neon_trio',
                'Palmode': 'steps'},
}


def _setp(c, k, v):
    p = getattr(c.par, k, None)
    if p is None:                                     # XYZ / RGB
        for s, x in zip('xyz', v):
            getattr(c.par, k + s).val = x
        return
    if p.mode != ParMode.CONSTANT:
        p.mode = ParMode.CONSTANT
    p.val = v


def case(name, extra=None):
    c = op(COMP)
    h = op(H)
    vals = dict(BASE)
    vals.update(CASES[name])
    vals.update(extra or {})
    for k, v in vals.items():
        _setp(c, k, v)
    h.op('pts_sw').par.index = 1 if name == 'trails_pts' else 0
    h.op('scene_sw').par.index = 1 if name == 'edges' else 0
    if name == 'polyline':
        c.par.Polychop = h.op('path')
    return {'case': name, 'status': c.par.Status.eval()}


def _vals(c, L):
    out = {}
    for n, (st, d, o) in L.par_specs().items():
        if st == 'Pulse':
            continue
        if st in ('XYZ', 'RGB'):
            out[n] = tuple(float(getattr(c.par, n + k).eval()) for k in ('xyz' if st == 'XYZ' else 'rgb'))
        elif st == 'Toggle':
            out[n] = bool(getattr(c.par, n).eval())
        else:
            out[n] = getattr(c.par, n).eval()
    return out


def _rows_chop(c):
    import numpy as np
    r = c.op('rows')
    return np.stack([np.array(r[k].vals) for k in 'xyzw'], -1)


def _seg(c):
    import numpy as np
    a = c.op('seg').numpyArray(delayed=True)
    if a is None:
        return None
    n = a.shape[0] * 256
    return a.reshape(a.shape[0], 256, 4, 4).reshape(n, 4, 4)


def _uT(c):
    g = c.op('seg')
    return [float(getattr(g.par, 'vec0value' + k).eval()) for k in 'xyzw']


def _colfn(c, L, Pm, v):
    import numpy as np
    stops = Pm.palette_stops(L.pal_spec(v))
    rows = Pm.pal_rows(stops)
    ctl = Pm.pal_ctl(stops, v['Palmode'], v['Palinterp'], v['Palshift'])
    cs = L.cs_vec(v, 'Line')
    return lambda t, m: np.array([Pm.colsrc_eval(cs, v['Linecol'], v['Linecol'], float(x), rows, ctl) for x in t])


def check(name):
    import numpy as np
    c = op(COMP)
    L = c.op('pl_logic').module
    Pm = c.op('pl_palmap').module
    v = _vals(c, L)
    R = _rows_chop(c)
    S = _seg(c)
    if S is None:
        return {'case': name, 'note': 'first delayed read: run again'}
    out = {'case': name, 'status': c.par.Status.eval(), 'total': int(R[0, 2])}
    pts = c.op('in_points').numpyArray(delayed=True)
    uT = _uT(c)
    if name in ('rings', 'radius', 'width', 'palette', 'occl'):
        ref = L.ref_segments(R, uT, colfn=_colfn(c, L, Pm, v))
        n = out['total']
        out['seg_max_err'] = float(np.abs(S[:n] - ref[:n]).max())
    if name == 'radius':
        img = c.op('render').numpyArray(delayed=True)
        if img is not None:
            g = img[..., 1]
            ys, xs = np.nonzero(g > 0.5 * g.max())
            rr = np.hypot(xs + 0.5 - 135.0, ys + 0.5 - 240.0)
            out['radius_px_median'] = float(np.median(rr))
            out['radius_px_expected'] = 1.0 / math.tan(math.radians(22.5)) * 0.5 * 270 / 5.0
    if name == 'width':
        img = c.op('render').numpyArray(delayed=True)
        if img is not None:
            row = img[240, :, 1]
            ring = row[135:]
            on = np.nonzero(ring > 0.5 * ring.max())[0]
            out['fwhm_px'] = int(len(on))
            out['row_profile'] = [round(float(x), 3) for x in ring[max(on.min() - 3, 0): on.max() + 4]]
    if name == 'contour' and pts is not None:
        ref = L.ref_segments(R, uT, points=pts, colfn=_colfn(c, L, Pm, v))
        n = out['total']
        ok = S[:n, 3, 3] == 2
        out['valid_frac'] = float(ok.mean())
        out['band_ids'] = sorted(set(int(x) for x in S[:n, 3, 2][ok]))
        both = ok & (ref[:n, 3, 3] == 2)
        out['valid_mismatch'] = int((ok != (ref[:n, 3, 3] == 2)).sum())
        out['seg_max_err'] = float(np.abs(S[:n][both] - ref[:n][both]).max())
    if name == 'connect' and pts is not None:
        ref = L.ref_segments(R, uT, points=pts, colfn=_colfn(c, L, Pm, v))
        n = out['total']
        out['valid_gpu'] = int((S[:n, 3, 3] == 4).sum())
        out['valid_ref'] = int((ref[:n, 3, 3] == 4).sum())
        same = (S[:n, 3, 3] == ref[:n, 3, 3])
        out['slot_mismatch'] = int((~same).sum())
        out['seg_max_err'] = float(np.abs(S[:n][same] - ref[:n][same]).max())
    if name == 'polyline':
        ref = L.ref_segments(R, uT, path=c.op('poly_top').numpyArray(delayed=True), colfn=_colfn(c, L, Pm, v))
        out['poly_top'] = [round(float(x), 3) for x in c.op('poly_top').numpyArray(delayed=True)[0, :4].ravel()]
        out['seg_max_err'] = float(np.abs(S[:4] - ref[:4]).max())
        out['valid'] = [int(x) for x in S[:5, 3, 3]]
    if name in ('trails_pts', 'trails_flow'):
        hist = c.op('hist').numpyArray(delayed=True)
        out['hist_shape'] = list(hist.shape) if hist is not None else None
        out['life_ids'] = sorted(set(float(x) for x in hist[:, 1, 0]))[:10] if hist is not None else None
        n = out['total']
        out['valid'] = int((S[:n, 3, 3] == 3).sum())
        if name == 'trails_pts':
            tr = S[:n].reshape(16, 8, 4, 4)
            out['dx'] = [round(float(x), 4) for x in (tr[3, 1:, 1, 0] - tr[3, 1:, 0, 0])]
            ref = L.ref_segments(R, uT, points=pts, hist=hist, colfn=_colfn(c, L, Pm, v))
            out['seg_max_err_vs_gpu_hist'] = float(np.abs(S[:n] - ref[:n]).max())
    if name == 'edges':
        e = c.op('edges').numpyArray(delayed=True)
        scene = c.op('in1').numpyArray(delayed=True)
        if e is not None and scene is not None:
            ref = L.ref_edges(R, scene, (e.shape[1], e.shape[0]))
            out['edges_max_err'] = float(np.abs(e - ref).max())
            out['row96_on'] = int((e[96, :, 3] > 0.5).sum())
            out['e_inside_outside_border'] = [float(e[96, 54, 3]), float(e[10, 10, 3]), float(e[96, 27, 3])]
    if name == 'occl':
        img = c.op('render').numpyArray(delayed=True)
        out['render_max'] = float(img[..., 1].max()) if img is not None else None
    return out


def drop_harness():
    c = op(COMP)
    for k in range(3):
        try:
            c.inputConnectors[k].disconnect()
        except Exception:
            pass
    _sd(op(H))
    if c is not None:
        c.par.Polychop = ''
    return {'dropped': op(H) is None}


# ---- pulling + perf (px_checks pattern, T-100 / T-143): nothing views out1 in a check run, so a run() chain pulls it
# once per frame; per-op cpu + gpu ms of the ops that cooked for that pull; real fps from the wall clock ----------
CHECKS_FILE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/px_lines_checks.py'


def _tick(k, n):
    import time
    c = op(COMP)
    c.op('out1').cook()
    rec = c.fetch('pl_perf', {}, search=False)
    rec.setdefault('wall', []).append(time.perf_counter())
    per, last = rec.setdefault('ops', {}), rec.setdefault('tc', {})
    tot = 0.0
    for x in c.findChildren(maxDepth=1):
        try:
            tc = int(x.totalCooks)
            cooked = x.name in last and tc > last[x.name]
            last[x.name] = tc
            if not cooked:
                continue
            cpu, gpu = float(x.cpuCookTime), float(getattr(x, 'gpuCookTime', 0.0) or 0.0)
            ms = cpu + gpu
        except Exception:
            continue
        per.setdefault(x.name, []).append(ms)
        sp = rec.setdefault('split', {}).setdefault(x.name, [[], []])
        sp[0].append(cpu)
        sp[1].append(gpu)
        tot += ms
    rec.setdefault('tot', []).append(tot)
    c.store('pl_perf', rec)
    if k + 1 < n:
        run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_tick'](%d, %d)" % (CHECKS_FILE, k + 1, n),
            delayFrames=1, delayRef=op.TDResources)


def pump(n=120):
    op(COMP).store('pl_perf', {})
    _tick(0, n)
    return n


def perf_report():
    rec = op(COMP).fetch('pl_perf', {}, search=False)
    w = rec.get('wall', [])
    med = lambda v: sorted(v)[len(v) // 2] if v else 0.0
    top = sorted(((round(med(v), 3), k) for k, v in rec.get('ops', {}).items()), reverse=True)[:10]
    return {'frames': len(w), 'real_fps': round((len(w) - 1) / max(w[-1] - w[0], 1e-9), 1) if len(w) > 1 else 0.0,
            'comp_ms_median': round(med(rec.get('tot', [])), 3), 'top_ops_ms': [(k, v) for v, k in top],
            'cpu_gpu_median': dict((k, (round(med(v[0]), 3), round(med(v[1]), 3), len(v[0])))
                                   for k, v in rec.get('split', {}).items() if med(v[0]) + med(v[1]) > 0.05)}
