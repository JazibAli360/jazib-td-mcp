"""Offline tests for GEN_points (builders/gen_points.py + gen_points_<module>.py + gen_points_logic.py). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_points.py'
Checks: module specs (pages / presets / uniforms / GLSL hooks), every uniform declared in the shader that receives it
and every TD expression compiles, glslc (OpenGL target, TD-like stubs, NOT a TD compile) of every shader incl. the
effector-prefixed state and the probe, a fake-TD build of each module network (wiring, <= 3 GLSL inputs, MAT samplers,
blend, sizes), and the numpy mirror: seeds, maps, RK4 vs a fine reference, Form grid, projection + additive count,
tone / compose, and that every preset renders a non-degenerate point picture offline."""
import math
import os
import re
import shutil
import subprocess
import tempfile
import types
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
NS = {}
exec(open(os.path.join(B, 'gen_points.py')).read(), NS)
L = {'__file__': os.path.join(B, 'gen_points_logic.py')}
exec(open(os.path.join(B, 'gen_points_logic.py')).read(), L)
MODS = dict((m, NS['module_ns'](m)) for m in NS['MODULES'])
W0, H0 = 108, 192


def pars_for(module, preset=None, extra=None):
    M = MODS[module]
    vals = next(v for s, _n, v in M['PRESETS'] if s == preset) if preset else None
    p = NS['module_pars'](M, vals)
    if extra:
        p.update(extra)
    return p


def U_for(module, preset=None, t=1.0, beats=0.0, W=W0, H=H0, extra=None):
    M = MODS[module]
    p = pars_for(module, preset, extra)
    spec = NS['uniform_spec'](M)
    return L['uniforms'](spec, p, W=W, H=H, t=t, beats=beats), p


def aux_for(module, pars):
    if module == 'polytope4d':
        return L['p4_table'](L['P4_SHAPES'][int(pars.get('Shape', 1))])
    if module != 'lsystem':
        return None
    r = L['ls_resolve'](L['LS_NAMES'][int(pars.get('System', 6))], 'F', ['F=F[+F]F[-F]F'], pars.get('Angle', 0.0),
                        pars.get('Iterations', 0), 'F', pars.get('Heading', -1.0))
    S, D, used = L['ls_segments'](*r, decay=pars.get('Lengthdecay', 1.0), jitter=pars.get('Turnjitter', 0.0),
                                  seed=pars.get('Lseed', 1))
    return L['ls_table'](S, D, used)


def simulate(module, U, n, frames, dt=1.0 / 60.0, img=None, aux=None):
    g = L['Glob'](U, asp=U['uSt2'][1], fr=0, npts=n)
    i = np.arange(n)
    S = L['seed'](module, i, U, g, img, aux)
    for f in range(frames):
        g.FR = f + 1
        S = L['step'](module, i, S, U, g, dt, img, aux, S)
    return S


# --------------------------------------------------------------------------------------------- specs
class Specs(unittest.TestCase):
    def test_modules_complete(self):
        for m, M in MODS.items():
            for k in ('MODULE', 'KIND', 'PAGES', 'PANEL_PAGES', 'PRESETS', 'UNIFORMS', 'STEP', 'PLACE', 'EPOCH'):
                self.assertIn(k, M, '%s: %s' % (m, k))
            self.assertEqual(M['MODULE'], m)
            self.assertIn(M['KIND'], ('2d', '3d'))
            self.assertIn(M.get('EFFECTORS'), (None, 'particles', 'points'))
            self.assertEqual(L['KIND'][m], M['KIND'])
            self.assertGreaterEqual(len(M['PRESETS']), 4)
            names = set()
            for _pg, ps in M['PAGES'] + NS['shared_pages'](M['KIND']):
                for p in ps:
                    self.assertNotIn(p[0], names, '%s: duplicate par %s' % (m, p[0]))
                    names.add(p[0])
            self.assertIn('Amount', names)
            pages = [pg for pg, _ps in M['PAGES'] + NS['shared_pages'](M['KIND'])]
            for pg in M['PANEL_PAGES']:
                self.assertIn(pg, pages)
            allp = NS['module_pars'](M)
            for slot, _nm, vals in M['PRESETS']:
                for k in vals:
                    self.assertIn(k, allp, '%s preset %d: unknown par %s' % (m, slot, k))

    def test_uniforms_declared_and_expressions_compile(self):
        for m, M in MODS.items():
            for spec, text in ((NS['state_spec'](M), NS['state_text'](M)), (NS['mat_spec'](M), NS['vertex_text'](M)),
                               (NS['LOOK_SPEC'], NS['look_text']()), (NS['LOOK_SPEC'], NS['look_text'](True))):
                decl = re.findall(r'^uniform vec4 (\w+);', text, re.M)
                self.assertEqual(sorted(decl), sorted(n for n, _e in spec), m)
                for n, ex in spec:
                    self.assertEqual(len(ex), 4)
                    for e in ex:
                        compile(NS['td_expr'](e), '<expr>', 'eval')
            body = NS['state_text'](M)
            for n, _e in M['UNIFORMS']:
                self.assertTrue(re.search(r'\b%s\.' % n, M.get('COMMON', '') + M['STEP'] + M['PLACE']),
                                '%s: %s unused' % (m, n))
            self.assertIn('pt_seed', body)
            self.assertIn('pt_step', body)
            self.assertIn('pt_place', NS['vertex_text'](M))
            if M.get('EFFECTORS') == 'particles':
                self.assertIn('pxeParticleForce', M['STEP'])
            if M.get('EFFECTORS') == 'points':
                self.assertIn('pxePointFx', M['STEP'])

    def test_tokens_and_sizes(self):
        self.assertIn('Count', NS['SIDE_E'])
        for k in ('W', 'H', 'RW', 'RH', 'side'):
            self.assertIn(k, NS['TOKENS'])
        self.assertNotIn('me.width', ''.join(NS['TOKENS'].values()))          # T-117 (2)
        for c in (1, 3, 65535, 65536, 262144, 1048576):
            s = L['side_of'](c)
            self.assertGreaterEqual(s * s - 1, c)
            self.assertLess((s - 1) * (s - 1) - 1, c)
            self.assertEqual(s, eval(NS['SIDE_E'].replace('parent().par.Count.eval()', str(c)), {'math': math}))

    def test_ascii(self):
        for f in ['gen_points.py', 'gen_points_logic.py'] + ['gen_points_%s.py' % m for m in MODS]:
            with open(os.path.join(B, f), encoding='ascii') as fh:
                fh.read()

    def test_bounded_loops(self):
        for m, M in MODS.items():
            for loop in re.findall(r'for \(int \w+ = 0; \w+ < (\w+);', M.get('COMMON', '') + M['STEP'] + M['PLACE']):
                self.assertTrue(loop.isdigit(), '%s: unbounded loop %s (T-35)' % (m, loop))


# --------------------------------------------------------------------------------------------- glslc
STUB_COMPUTE = """#version 460
uniform sampler2D sTD2DInputs[3];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[2];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""
STUB_VERT = "#version 460\nin vec3 P;\nvec3 TDPos() { return P; }\n"


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, ext, what):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.' + ext)
            with open(p, 'w') as fh:
                fh.write(text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:3000]))

    def test_every_shader(self):
        E = NS['_eff']()
        for m, M in MODS.items():
            self._ok(STUB_COMPUTE + NS['state_text'](M), 'comp', m + ' state')
            self._ok(STUB_COMPUTE + NS['state_text'](M, probe_dt=1 / 60.0), 'comp', m + ' probe')
            pre = NS['effector_prefix'](M)
            if M.get('EFFECTORS'):
                self.assertTrue(pre)
                Lg = E['_logic']()
                self._ok(STUB_COMPUTE + Lg['with_prefix'](NS['state_text'](M), pre), 'comp', m + ' state + eff')
                t = Lg['with_prefix'](NS['state_text'](M, probe_dt=0.01), pre)
                self.assertTrue(t.startswith('#define GP_PROBE_DT'))
                self._ok(STUB_COMPUTE + t, 'comp', m + ' probe + eff')
            self._ok(STUB_VERT + NS['vertex_text'](M), 'vert', m + ' vertex')
        self._ok('#version 460\n' + NS['PIXEL'], 'frag', 'pixel')
        self._ok(STUB_COMPUTE + NS['look_text'](), 'comp', 'look')
        self._ok(STUB_COMPUTE + NS['look_text'](True), 'comp', 'look_acc')
        self.assertIn('TDImageLoadOutput(1', NS['look_text'](True))
        self.assertNotIn('#define GP_ACC', NS['look_text']())

    def test_vertex_contract(self):
        for m, M in MODS.items():
            v = NS['vertex_text'](M)
            self.assertIn('TDPos()', v)                          # raw P reads garbage on POP points (T-112)
            self.assertNotIn('#version', v)
            self.assertIn('gl_PointSize', v)


# --------------------------------------------------------------------------------------------- fake TD build
class FakePar(object):
    def __init__(self):
        self.val, self.expr, self.mode = None, None, None

    def eval(self):
        return self.val


class FakePars(object):
    def __init__(self):
        object.__setattr__(self, '_d', {})

    def __getattr__(self, k):
        d = object.__getattribute__(self, '_d')
        if k not in d:
            d[k] = FakePar()
        return d[k]

    def __setattr__(self, k, v):
        getattr(self, k).val = v


class FakeConn(object):
    def __init__(self):
        self.src = None

    def connect(self, s):
        self.src = s


class Seq(object):
    def __init__(self):
        self.numBlocks = 0


class FakeOp(object):
    def __init__(self, cls, name):
        self.OPType, self.name = cls, name
        self.path = '/fake/' + name
        self.par = FakePars()
        self.inputConnectors = [FakeConn() for _ in range(8)]
        self.seq = types.SimpleNamespace(vec=Seq(), sampler=Seq(), const=Seq(), array=Seq())
        self.text, self.comment, self.dock, self.docked = '', '', None, []
        self.valid, self.viewer, self.render, self.display = True, False, False, False
        self.ops, self.children = {}, []

    def op(self, n):
        return self.ops.get(n)

    def create(self, cls, name):
        o = FakeOp(cls.__name__, name)
        self.ops[name] = o
        self.children.append(o)
        return o


TD_CLASSES = ['inTOP', 'outTOP', 'glslTOP', 'textDAT', 'switchTOP', 'constantTOP', 'feedbackTOP', 'constantCHOP',
              'speedCHOP', 'parameterexecuteDAT', 'gridPOP', 'glslMAT', 'geometryCOMP', 'selectPOP', 'cameraCOMP',
              'renderTOP', 'scriptTOP']


def fake_build(module):
    ns = dict(NS)
    for c in TD_CLASSES:
        ns[c] = type(c, (), {})
    ns['ParMode'] = types.SimpleNamespace(EXPRESSION='expr', CONSTANT='const')
    ns['_EFF'] = {}
    ns['EFFECTORS_FILE'] = '/nonexistent'
    ns['safe_destroy'] = lambda o: None
    with open(os.path.join(B, 'gen_points.py')) as fh:
        exec(compile(fh.read(), 'gen_points.py', 'exec'), ns)   # rack + builder functions bound to the fakes
    ns['_EFF'] = {}
    ns['EFFECTORS_FILE'] = '/nonexistent'
    m = FakeOp('baseCOMP', module + '1')
    stages = ns['_module_network'](m, MODS[module])
    return m, stages


class FakeBuild(unittest.TestCase):
    def test_networks(self):
        for module, M in MODS.items():
            m, stages = fake_build(module)
            o = m.ops
            for n in ('in1', 'clock', 'clock_int', 'pulses', 'state_fb', 'state', 'state_compute', 'pts', 'mat',
                      'mat_vertex', 'mat_pixel', 'geo', 'cam', 'render', 'look', 'out_sel', 'out1'):
                self.assertIn(n, o, '%s: %s missing' % (module, n))
            src = lambda op_, k: op_.inputConnectors[k].src.name if op_.inputConnectors[k].src else None
            self.assertEqual([src(o['state'], 0), src(o['state'], 1)], ['state_fb', 'in1'])
            self.assertEqual(o['state_fb'].par.top.val, 'state')
            self.assertEqual([src(o['look'], 0), src(o['look'], 1)], ['render', 'in1'])
            self.assertEqual([src(o['look_acc'], 0), src(o['look_acc'], 1)], ['render', 'in1'])
            self.assertEqual([src(o['out_sel'], k) for k in range(3)], ['in1', 'look', 'look_acc'])
            for n in ('acc', 'acc_fb', 'acc_sel'):                                    # v1 trail pass merged into look
                self.assertNotIn(n, o)
            self.assertEqual((o['look_acc'].par.numcolorbufs.val, o['look_acc'].par.outputaccess.val,
                              o['look_acc'].par.clearoutputs.val), (2, 'readwrite', False))
            self.assertIsNone(o['look'].par.numcolorbufs.val)
            self.assertIn('Glow', o['look'].par.inputfiltertype.expr)               # mips only when glowing
            self.assertIn('Precision', o['render'].par.format.expr)
            self.assertEqual(o['state_fb_blank'].par.resolutionw.val, 2)            # constant blank, no size expr
            for g in ('state', 'look', 'look_acc'):
                self.assertIsNone(o[g].inputConnectors[3].src)                       # T-88
                self.assertEqual(o[g].par.mode.val, 'compute')
            self.assertEqual(o['state'].par.format.val, 'rgba32float')
            self.assertEqual(o['pts'].par.surftype.val, 'points')
            self.assertEqual(o['pts'].par.cols.expr, NS['SIDE_E'])
            mat = o['mat']
            self.assertEqual((mat.par.sampler0name.val, mat.par.sampler0top.val), ('sSt', 'state'))
            self.assertEqual((mat.par.sampler1name.val, mat.par.sampler1top.val), ('sIn', 'in1'))
            for n in ('srcblend', 'destblend', 'srcblenda', 'destblenda'):
                self.assertEqual(getattr(mat.par, n).val, 'one')
            self.assertFalse(mat.par.depthtest.val)
            self.assertEqual(o['geo'].ops['sel'].par.pop.val, '../pts')
            self.assertEqual(o['render'].par.resolutionw.expr, NS['RW_E'])
            self.assertEqual(o['state_compute'].dock, o['state'])
            names = [getattr(mat.par, 'vec%dname' % k).val for k in range(mat.seq.vec.numBlocks)]
            self.assertEqual(names, [n for n, _e in NS['mat_spec'](M)])
            for g in (o['state'], mat, o['look'], o['look_acc']):
                for k in range(g.seq.vec.numBlocks):
                    for ax in 'xyzw':
                        compile(getattr(g.par, 'vec%dvalue%s' % (k, ax)).expr, '<u>', 'eval')
            if M.get('AUX_SCRIPT'):
                self.assertEqual(src(o['state'], 2), 'aux')
                self.assertEqual(o['aux'].par.callbacks.val, o['aux_callbacks'])
                self.assertIn('def onCook', o['aux_callbacks'].text)
                compile(o['aux_callbacks'].text, 'aux', 'exec')
            else:
                self.assertIsNone(o['state'].inputConnectors[2].src)
            for s in stages:
                for n in s['ops']:
                    self.assertTrue(n in o or n.startswith('eff_') or n.startswith('aux'), '%s stage op %s' % (module, n))


# --------------------------------------------------------------------------------------------- mirror maths
class Mirror(unittest.TestCase):
    def test_rnd_matches_px(self):
        U, _p = U_for('density2d')
        g = L['Glob'](U)
        X = L['px']()
        i = np.arange(10)
        self.assertTrue(np.allclose(L['rnd'](i, 5, g), X['np_rnd'](i, (5 + g.SEED * 7919) & 0xFFFFFFFF)))
        r = L['rnd'](np.arange(20000), 3, g)
        self.assertTrue(0 <= r.min() and r.max() < 1 and abs(r.mean() - 0.5) < 0.01)

    def test_pack_roundtrip(self):
        k = np.array([0.0, 0.25, 0.5, 0.999, 1.37])
        a = np.array([0.0, 0.5, 1.0, 0.3, 2.0])
        kk, aa = L['unpack'](L['pack_ka'](k, a))
        self.assertTrue(np.allclose(kk, k - np.floor(k), atol=1e-6))
        self.assertTrue(np.allclose(aa, np.round(np.clip(a, 0, 1) * 1023) / 1023))

    def test_density_map_and_seed(self):
        U, _p = U_for('density2d', 1)
        g = L['Glob'](U, asp=U['uSt2'][1])
        i = np.arange(500)
        S0 = L['density2d_seed'](i, U, g)
        self.assertTrue(np.all(np.isfinite(S0)))
        g.FR = 1
        S1 = L['density2d_step'](i, S0, U, g, 1 / 60.0)
        p = L['d2_params'](U, g)
        x, y = S0[:, 0], S0[:, 1]
        for _k in range(int(U['uM1'][3] + 0.5)):
            x, y = L['d2_map'](0, x, y, p)
        self.assertTrue(np.allclose(S1[:, :2], np.stack([x, y], -1)))
        self.assertTrue(np.array_equal(L['density2d_step'](i, S0, U, g, 0.0), S0))      # dt 0 = hold
        e = L['d2_ext'](0, p)
        self.assertTrue(np.abs(S1[:, :2]).max() <= e + 1e-9)          # Clifford: |x| <= 1 + |c|

    def test_attractor_rk4_vs_fine(self):
        for sys_ in range(len(L['A3_SYSTEMS'])):
            U, _p = U_for('attractor3d', extra={'System': sys_, 'Respawn': 0.0})
            g = L['Glob'](U, asp=U['uSt2'][1])
            S = L['attractor3d_seed'](np.arange(64), U, g)
            for f in range(30):                               # settle onto the attractor
                g.FR = f + 1
                S = L['attractor3d_step'](np.arange(64), S, U, g, 1 / 30.0)
            g.FR = 99
            one = L['attractor3d_step'](np.arange(64), S, U, g, 1 / 60.0)
            k = L['a3_par'](sys_, U, g)
            Hh = (1 / 60.0) * L['A3_RATE'][sys_] * U['uM1'][0]
            x, y, z = S[:, 0].copy(), S[:, 1].copy(), S[:, 2].copy()
            n = 400
            h = Hh / n
            for _j in range(n):                              # fine Euler-midpoint reference
                f1 = L['a3_f'](sys_, x, y, z, k)
                f2 = L['a3_f'](sys_, x + 0.5 * h * f1[0], y + 0.5 * h * f1[1], z + 0.5 * h * f1[2], k)
                x, y, z = x + h * f2[0], y + h * f2[1], z + h * f2[2]
            ref = np.stack([x, y, z], -1)
            err = np.abs(one[:, :3] - ref).max() / L['A3_EXT'][sys_]
            self.assertLess(err, 1e-4, L['A3_SYSTEMS'][sys_])
            P, _k, a, ok = L['attractor3d_place'](np.arange(64), one, U, g)
            self.assertTrue(ok.all())
            self.assertLess(np.abs(P).max(), 3.0 * U['uM2'][1], L['A3_SYSTEMS'][sys_])   # normalised to ~1

    def test_streamlines_respawn_and_bounds(self):
        U, _p = U_for('streamlines', 1)
        S = simulate('streamlines', U, 2000, 120)
        g = L['Glob'](U, asp=U['uSt2'][1])
        self.assertTrue(np.all(np.abs(S[:, 0]) <= g.ASP + 1e-9))
        self.assertTrue(np.all(np.abs(S[:, 1]) <= 1.0 + 1e-9))
        self.assertTrue(np.all((S[:, 2] >= 0) & (S[:, 2] < 1.0)))
        U5, _p = U_for('streamlines', 5)                       # rain: mostly downward motion
        g5 = L['Glob'](U5, asp=U5['uSt2'][1])
        v = L['sl_field'](np.zeros((100, 2)) + np.array([0.1, 0.2]), U5, g5)
        self.assertTrue(np.all(v[:, 1] < 0))

    def test_form_grid(self):
        U, _p = U_for('form', 1, extra={'Fractal': 0.0, 'Disperse': 0.0, 'Twist': 0.0})
        N = 4096
        g = L['Glob'](U, asp=U['uSt2'][1], npts=N)
        S = L['form_eval'](np.arange(N), U, g)
        P = S[:, :3]
        self.assertLessEqual(np.abs(P[:, 0]).max(), 0.5 * U['uM0'][2] + 1e-9)
        self.assertLessEqual(np.abs(P[:, 1]).max(), 0.5 * U['uM0'][3] + 1e-9)
        self.assertEqual(len(np.unique(np.round(P[:, 2], 6))), int(U['uM0'][1] + 0.5))     # Layers planes
        Us, _p = U_for('form', 2, extra={'Fractal': 0.0, 'Layers': 1})
        Ss = L['form_eval'](np.arange(N), Us, L['Glob'](Us, npts=N))
        r = np.sqrt((Ss[:, :3] ** 2).sum(-1))
        self.assertTrue(np.allclose(r, 0.5 * Us['uM0'][2]))

    def test_project_and_count(self):
        U, _p = U_for('density2d', 1)
        g = L['Glob'](U, asp=U['uV2'][0] / U['uV2'][1])
        P = np.array([[0.0, 0.0, 0.0], [0.5, -0.5, 0.0], [3.0, 0.0, 0.0]])
        ndc, fade, vis = L['project']('2d', np.arange(3), P, U, g)
        self.assertTrue(np.allclose(ndc[0], [0, 0]))
        self.assertTrue(np.allclose(ndc[1], [0.5 / g.ASP, -0.5]))
        img, ok = L['count_image'](ndc, np.ones(3), W0, H0)
        self.assertEqual(int(img.sum()), 2)
        self.assertEqual(list(ok), [True, True, False])
        U3, _p = U_for('form', 1, extra={'Orbit': 0.0, 'Yaw': 0.0, 'Pitch': 0.0})
        g3 = L['Glob'](U3, asp=U3['uV2'][0] / U3['uV2'][1])
        ndc, fade, vis = L['project']('3d', np.arange(2), np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 5.0]]), U3, g3)
        self.assertTrue(np.allclose(ndc[0], [0, 0]) and vis[0] and not vis[1])
        self.assertAlmostEqual(fade[0], 1.0)

    def test_tone_and_compose(self):
        U, _p = U_for('density2d', 1, extra={'Exposure': 0.0, 'Gamma': 1.0, 'Persist': 0.0, 'Blend': 0})
        n = U['uLk2'][2] / U['uLk3'][2]
        v = np.array([[0.0, 0.0, 0.0, 0.0], [1.0 / n, 0.0, 0.0, 1.0 / n]])
        for mode, expect in ((0, 1.0 - math.exp(-1.0)), (1, 1.0)):
            U['uLk'] = (mode,) + U['uLk'][1:]
            col = L['tone'](v, U)
            self.assertAlmostEqual(col[1, 0], expect, places=9)
            self.assertEqual(col[0].sum(), 0.0)
        U['uLk'] = (2, 0.0, 1.0, 1.0)
        col = L['tone'](np.array([[2.0 / n, 4.0 / n, 0.0, 4.0 / n]]), U)
        self.assertAlmostEqual(col[0, 1] / col[0, 0], 2.0)                     # vibrancy 1 keeps the hue
        g = L['Glob'](U)
        c = np.array([[0.2, 0.3, 0.4, 1.0]])
        pts = np.array([[0.5, 0.5, 0.5]])
        for blend, exp_ in ((0, [0.5, 0.5, 0.5, 1.0]), (1, [0.7, 0.8, 0.9, 1.0]), (3, [0.5, 0.5, 0.5, 1.0]),
                            (4, [0.5, 0.5, 0.5, 0.5])):
            U['uLk2'] = U['uLk2'][:3] + (blend,)
            self.assertTrue(np.allclose(L['compose'](c, pts, U, g), exp_), blend)
        U['uLk3'] = (0.0,) + U['uLk3'][1:]
        self.assertTrue(np.allclose(L['compose'](c, pts, U, g), c))              # Amount 0 = input


class Presets(unittest.TestCase):
    def test_every_preset_renders_points(self):
        for m, M in MODS.items():
            for slot, name, _v in M['PRESETS']:
                U, p = U_for(m, slot, extra={'Count': 3000, 'Growspeed': 0.0} if m == 'lsystem' else {'Count': 3000})
                n = 3000
                img = np.random.RandomState(1).rand(48, 27, 4) if m in L['USES_IMG'] else None
                S = simulate(m, U, n, 40, img=img, aux=aux_for(m, p))
                self.assertTrue(np.all(np.isfinite(S)), '%s %s' % (m, name))
                R, nvis = L['points_render'](m, S, U, W0, H0, img=img)
                mv = M.get('MIN_VISIBLE', {}).get(slot, 0.25)
                self.assertGreater(nvis, mv * n, '%s %s: %d of %d visible' % (m, name, nvis, n))
                lit = (R[..., 3] > 0).mean()
                self.assertGreater(lit, 0.002, '%s %s: lit %.4f' % (m, name, lit))
                col = L['tone'](R, U)
                self.assertGreater(col.max(), 0.05, '%s %s' % (m, name))


if __name__ == '__main__':
    unittest.main()


class Wave2(unittest.TestCase):
    def test_flame_genomes_bounded_and_spread(self):
        for gi, name in enumerate(L['FL_NAMES']):
            U, _p = U_for('flame', extra={'Genome': gi, 'Genomeb': gi, 'Xrotate': 0.0, 'Count': 4000})
            S = simulate('flame', U, 4000, 20)
            g = L['Glob'](U, asp=U['uSt2'][1], npts=4000)
            P, k, a, ok = L['flame_place'](np.arange(4000), S, U, g)
            self.assertGreater(ok.mean(), 0.99, name)
            inside = (np.abs(P[:, 0]) <= g.ASP) & (np.abs(P[:, 1]) <= 1.0)
            self.assertGreater(inside.mean(), 0.9, name)              # the measured fit frames the flame
            self.assertGreater(P[:, :2].std(0).min(), 0.05, name)     # not collapsed to a point
            self.assertTrue(((S[:, 2] >= 0) & (S[:, 2] <= 1)).all())

    def test_flame_variations_and_rotation(self):
        x, y, rw = np.array([0.3, -0.7]), np.array([0.5, 0.2]), np.array([0.2, 0.8])
        r2 = x * x + y * y
        self.assertTrue(np.allclose(L['fl_var'](2, x, y, rw)[0], x / r2))
        jx, jy = L['fl_var'](13, x, y, rw)
        self.assertTrue(np.allclose(np.hypot(jx, jy), np.sqrt(np.sqrt(r2))))
        bx, by = L['fl_var'](14, x, y, rw)
        self.assertTrue(np.allclose(bx, [0.3, -1.4]) and np.allclose(by, y))
        U, _p = U_for('flame', extra={'Xrotate': 90.0}, t=1.0)
        g = L['Glob'](U)
        X0 = L['fl_coefs'](dict(U, uM1=(U['uM1'][0], 0.0) + U['uM1'][2:]), g)
        X1 = L['fl_coefs'](U, g)
        self.assertTrue(np.allclose(X1[0, 3], -X0[0, 6]) and np.allclose(X1[0, 6], X0[0, 3]))   # 90 deg turn
        self.assertTrue(np.allclose(X1[1, 3:9], X0[1, 3:9]))                                       # unflagged

    def test_lsystem_rule_counts(self):
        want = {'koch': (3, 125), 'dragon': (10, 1024), 'hilbert': (4, 255), 'gosper': (3, 343),
                'sierpinski': (6, 729), 'plant': (5, 1488)}
        for name, (it, n) in want.items():
            r = L['ls_resolve'](name, iters=it)
            S, D, used = L['ls_segments'](*r)
            self.assertEqual(len(S), n, name)
            self.assertEqual(used, it)
        S, D, used = L['ls_segments'](*L['ls_resolve']('hilbert', iters=4))
        pts = set((round(a, 6), round(b, 6)) for a, b in np.concatenate([S[:, :2], S[:, 2:]]))
        self.assertEqual(len(pts), 256)                                                 # space filling 16 x 16
        self.assertEqual(L['ls_parse_rules'](['F = FF', 'X->F[X]', 'bad']), {'F': 'FF', 'X': 'F[X]'})

    def test_lsystem_table_and_even_spread(self):
        S, D, used = L['ls_segments'](*L['ls_resolve']('koch', iters=3))
        T = L['ls_table'](S, D, used)
        self.assertEqual(T.shape[1], L['LS_W'])
        self.assertEqual(int(T[0, 0, 0]), 125)
        U, _p = U_for('lsystem', extra={'System': 0, 'Iterations': 3, 'Jitter': 0.0, 'Progress': 1.0,
                                        'Growspeed': 0.0, 'Count': 5000})
        g = L['Glob'](U, asp=U['uSt2'][1], npts=5000, fr=1)
        out = L['lsystem_eval'](np.arange(5000), U, g, T)
        k, a = L['unpack'](out[:, 3])
        self.assertTrue((a == 1).all())
        d = np.hypot(np.diff(out[:, 0]), np.diff(out[:, 1]))
        self.assertLess(d.max() / d.mean(), 2.2)              # even spacing along the path (+ 0..1 step offset)
        U2 = dict(U, uM0=(0.5,) + U['uM0'][1:])
        out2 = L['lsystem_eval'](np.arange(5000), U2, g, T)
        w = out[:, 0].max() - out[:, 0].min()
        self.assertLess(out2[:, 0].max() - out[:, 0].min(), 0.6 * w)                # half grown = left half
        U3 = dict(U, uM0=(0.0,) + U['uM0'][1:])
        self.assertTrue((L['unpack'](L['lsystem_eval'](np.arange(50), U3, g, T)[:, 3])[1] == 0).all())

    def test_graph_forces(self):
        U, _p = U_for('graph', extra={'Nodes': 64, 'Count': 20000, 'Kick': 0.0})
        g = L['Glob'](U, asp=U['uSt2'][1], npts=20000)
        i = np.arange(20000)
        S = L['graph_seed'](i, U, g)
        self.assertTrue((S[64:] == 0).all())
        for f in range(300):
            g.FR = f + 1
            S = L['graph_step'](i[:64], S[:64], U, g, 1 / 30.0, full=S[:64])
        par = L['gr_parent'](np.arange(1, 64), g)
        el = np.hypot(*(S[1:64, :2] - S[par, :2]).T)
        dd = np.hypot(*(S[:64, None, :2] - S[None, :64, :2]).transpose(2, 0, 1))
        self.assertLess(np.median(el), np.median(dd[np.triu_indices(64, 1)]))      # linked nodes sit closer
        self.assertGreater(dd[np.triu_indices(64, 1)].min(), 0.005)                 # repulsion keeps them apart
        Sf = np.zeros((20000, 4))
        Sf[:64] = S
        P, k, a, ok = L['graph_place'](i, Sf, U, g)
        self.assertTrue(ok[:64].all())
        self.assertGreater(ok[64 + 64 * 24:].mean(), 0.3)                           # edge dust drawn

    def test_sparkle_cycle(self):
        U, _p = U_for('sparkle', t=3.0, extra={'Count': 2000})
        g = L['Glob'](U, asp=U['uSt2'][1], npts=2000)
        S = L['sparkle_eval'](np.arange(2000), U, g)
        k, b = L['unpack'](S[:, 2])
        self.assertTrue(((b >= 0) & (b <= 1)).all())
        self.assertLess(np.median(b), 0.3)                                          # mostly dark, few glints
        self.assertGreater(b.max(), 0.9)
        U2, _p = U_for('sparkle', t=3.0, extra={'Count': 2000, 'Placement': 2, 'Threshold': 0.5})
        img = np.zeros((64, 36, 4))
        img[40:50, 10:20] = 1.0
        S2 = L['sparkle_eval'](np.arange(2000), U2, g, img)
        k2, b2 = L['unpack'](S2[:, 2])
        lit = b2 > 0
        u = S2[lit, 0] / (2 * g.ASP) + 0.5
        v = S2[lit, 1] * 0.5 + 0.5 - U2['uM1'][1] * 0.0
        self.assertTrue(((u > 9 / 36.) & (u < 21 / 36.)).all())                     # only on the bright patch


class LaneG(unittest.TestCase):
    """Lane G (27 Oct): polytope4d (TC-17) maths."""

    def _U(self, **kw):
        U, p = U_for('polytope4d', 1, extra=dict({'Count': 4096}, **kw))
        g = L['Glob'](U, asp=U['uSt2'][1], fr=0, npts=4096)
        return U, p, g

    def test_six_planes_vs_matrix_product(self):
        ang = dict(Rxy=11.0, Rxz=-23.0, Rxw=37.0, Ryz=5.0, Ryw=-71.0, Rzw=95.0, Sxy=3.0, Sxz=-7.0, Sxw=13.0,
                   Syz=17.0, Syw=-19.0, Szw=29.0, Kick=0.0)
        U, p, g = self._U(**ang)
        M = np.eye(4)
        planes = [((0, 1), 'xy'), ((0, 2), 'xz'), ((0, 3), 'xw'), ((1, 2), 'yz'), ((1, 3), 'yw'), ((2, 3), 'zw')]
        for (a, b), nm in planes:                                       # independent: product of Givens matrices
            d = math.radians(p['R' + nm] + p['S' + nm] * g.T)
            G = np.eye(4)
            G[a, a] = G[b, b] = math.cos(d)
            G[a, b], G[b, a] = -math.sin(d), math.sin(d)
            M = G @ M
        R = L['p4_rotation_matrix'](U, g)
        self.assertLess(np.abs(R - M).max(), 1e-12)
        self.assertLess(np.abs(R @ R.T - np.eye(4)).max(), 1e-12)
        self.assertAlmostEqual(np.linalg.det(R), 1.0, places=12)
        for (a, b), nm in planes:                                       # each plane alone moves only its two axes
            U1, p1, g1 = self._U(**dict({k: 0.0 for k in ang}, **{'R' + nm: 30.0}))
            R1 = L['p4_rotation_matrix'](U1, g1)
            other = [k for k in range(4) if k not in (a, b)]
            for k in other:
                self.assertTrue(np.allclose(R1[:, k], np.eye(4)[:, k]))
            self.assertAlmostEqual(R1[a, a], math.cos(math.radians(30)), places=12)

    def test_polytopes(self):
        for sh, (nv, ne) in zip(L['P4_SHAPES'][:6], [(5, 10), (16, 32), (8, 24), (24, 96), (120, 720), (600, 1200)]):
            V = L['p4_vertices'](sh)
            E = L['p4_edges'](V)
            self.assertEqual((len(V), len(E)), (nv, ne), sh)
            self.assertLess(np.abs(np.sqrt((V * V).sum(-1)) - 1.0).max(), 1e-9, sh)
            le = np.sqrt(((V[E[:, 0]] - V[E[:, 1]]) ** 2).sum(-1))
            self.assertLess(le.max() - le.min(), 1e-9, sh)
            deg = np.bincount(E.ravel(), minlength=nv)
            self.assertEqual(deg.min(), deg.max(), sh)                  # vertex-transitive: same degree
            T = L['p4_table'](sh)
            self.assertEqual(int(T[0, 0, 0]), ne)
            self.assertEqual(T.dtype, np.float32)

    def test_projections_and_surfaces(self):
        q = np.array([[0.3, -0.2, 0.1, 0.0], [0.0, 0.0, 0.0, -1.0], [0.5, 0.5, 0.5, 0.5]])
        U, p, g = self._U(Projection=0, Wdist=2.5, Worldsize=1.0)
        P, vis = L['p4_project'](q, U)
        self.assertTrue(np.allclose(P[0], q[0, :3]))                   # w = 0: scale 1
        self.assertTrue(np.allclose(P[2], q[2, :3] * 2.5 / 2.0))
        U, p, g = self._U(Projection=1)
        P, vis = L['p4_project'](q, U)
        self.assertTrue(np.allclose(P[1], 0.0))                        # south pole -> origin
        U, p, g = self._U(Projection=3, Wslice=0.5, Slicewidth=0.1)
        P, vis = L['p4_project'](q, U)
        self.assertEqual(list(vis), [0.0, 0.0, 1.0])
        for sh in (6, 7, 8):                                           # torus, hopf, glome lie on the unit S3
            U, p, g = self._U(Shape=sh, Fibers=12, Hopfrings=3)
            P, el, al = L['p4_base'](np.arange(4096), U, g)
            self.assertLess(np.abs(np.sqrt((P * P).sum(-1)) - 1.0).max(), 1e-9, sh)
        U, p, g = self._U(Shape=7, Fibers=12, Hopfrings=3, Flow=0.0, Edgejitter=0.0)
        P, el, al = L['p4_base'](np.arange(4096), U, g)
        f0 = P[el == el[0]]                                            # one fiber = a great circle (rank 2 plane)
        self.assertEqual(np.linalg.matrix_rank(f0, tol=1e-9), 2)


class LaneG2(unittest.TestCase):
    """Lane G (27 Oct): hyperspace (FX7c 18) + mirrorball (FX7c 19) maths."""

    def _g(self, module, U, n):
        return L['Glob'](U, asp=U['uSt2'][1], fr=3, npts=n)

    def test_hyperspace_streaks(self):
        n = 64 * 16
        U, p = U_for('hyperspace', 1, t=2.0, extra={'Count': n, 'Jitter': 0.0, 'Fadein': 0.0})
        S = L['hyperspace_eval'](np.arange(n), U, self._g('hyperspace', U, n))
        P = S[:, :2].reshape(64, 16, 2)
        for s in range(64):                                     # one star's samples lie on a ray from the centre
            d = P[s] / np.maximum(np.linalg.norm(P[s], axis=-1, keepdims=True), 1e-12)
            self.assertLess(np.abs(d - d[0]).max(), 1e-9)
            r = np.linalg.norm(P[s], axis=-1)
            self.assertTrue(np.all(np.diff(r) <= 1e-12))        # head (k = 0) outermost, tail toward the centre
            st = np.diff(r)
            self.assertLess(np.abs(st - st[0]).max(), 1e-9)     # evenly spaced on screen
        U0, _ = U_for('hyperspace', 1, t=2.0, extra={'Count': n, 'Stretch': 0.0, 'Jitter': 0.0})
        S0 = L['hyperspace_eval'](np.arange(n), U0, self._g('hyperspace', U0, n))
        P0 = S0[:, :2].reshape(64, 16, 2)
        self.assertLess(np.abs(P0 - P0[:, :1]).max(), 1e-12)   # Stretch 0 = dots
        U1, _ = U_for('hyperspace', 1, t=2.0 + 1.0 / 60.0, extra={'Count': n, 'Jitter': 0.0, 'Fadein': 0.0})
        S1 = L['hyperspace_eval'](np.arange(n), U1, self._g('hyperspace', U1, n))
        r0 = np.linalg.norm(S[::16, :2], axis=-1)
        r1 = np.linalg.norm(S1[::16, :2], axis=-1)
        self.assertGreater((r1 > r0).mean(), 0.9)               # heads move outward (toward the camera)

    def test_mirrorball_reflection(self):
        n = 2048
        U, p = U_for('mirrorball', 1, t=1.3, extra={'Count': n, 'Twinkle': 0.0, 'Edgefade': 0.0})
        g = self._g('mirrorball', U, n)
        S = L['mirrorball_eval'](np.arange(n), U, g)
        k, a = L['unpack'](S[:, 3])
        vis = a > 0
        self.assertGreater(vis.mean(), 0.1)
        nl, nf = 2, n // 2
        for i in np.where(vis)[0][:200]:
            j, f = i // nf, i % nf
            z = 1.0 - 2.0 * (f + 0.5) / nf
            rr = math.sqrt(max(0.0, 1.0 - z * z))
            ph = f * 2.39996323
            nv = np.array([rr * math.cos(ph), z, rr * math.sin(ph)])
            c, s = math.cos(math.radians(p['Spin'] * g.T)), math.sin(math.radians(p['Spin'] * g.T))
            nv = np.array([c * nv[0] - s * nv[2], nv[1], s * nv[0] + c * nv[2]])
            c, s = math.cos(math.radians(p['Tilt'])), math.sin(math.radians(p['Tilt']))
            nv = np.array([nv[0], c * nv[1] - s * nv[2], s * nv[1] + c * nv[2]])
            Ld = L['mb_light'](np.array([j]), nl, U)[0]
            w = S[i, :2] / p['Wallscale']
            hit = np.array([w[0], w[1], -p['Walldist']])         # the spot on the wall plane
            r = hit / np.linalg.norm(hit)
            self.assertAlmostEqual(float(r @ nv), float(Ld @ nv), places=9)              # angle in = angle out
            self.assertLess(np.linalg.norm(np.cross(np.cross(Ld, nv), np.cross(r, nv))), 1e-9)  # same plane
        Ug, _ = U_for('mirrorball', 1, t=1.3, extra={'Count': n, 'Elevation': 89.0, 'Azimuth': 180.0})
        Sg = L['mirrorball_eval'](np.arange(n), Ug, self._g('mirrorball', Ug, n))
        self.assertTrue(np.all(np.isfinite(Sg)))


class LaneG3(unittest.TestCase):
    """Lane G (27 Oct): form Shape clip + Rise (TC-20 video to particles)."""

    def test_clip_rise(self):
        n = 4096
        img = np.zeros((48, 27, 4))
        img[:, 14:, :3] = 1.0                                    # right half white, left half black
        U, p = U_for('form', 6, t=1.7, extra={'Count': n, 'Mapdisp': 0.0})
        g = L['Glob'](U, asp=U['uSt2'][1], fr=0, npts=n)
        S = L['form_eval'](np.arange(n), U, g, img)
        B, N, uvw = L['fm_base'](np.arange(n), U, g)
        self.assertAlmostEqual(B[:, 0].max() - B[:, 0].min(), p['Sizey'] * g.ASP, delta=0.05)   # input aspect
        dark = uvw[:, 0] < 0.45
        bright = uvw[:, 0] > 0.6
        self.assertLess(np.abs(S[dark, 2]).max(), 1e-12)          # dark pixels stay on the plane
        self.assertGreater(S[bright, 2].mean(), 0.3)              # bright ones rise toward the camera
        self.assertLessEqual(S[bright, 2].max(), p['Rise'] + 3.0 * p['Risecurl'])
        k, a = L['unpack'](S[:, 3])
        self.assertTrue(np.all(a[dark] > 0.99))
        self.assertLess(a[bright].min(), 0.9)                      # fading at the top of the rise
        U0, _ = U_for('form', 6, t=1.7, extra={'Count': n, 'Rise': 0.0, 'Mapdisp': 0.0})
        S0 = L['form_eval'](np.arange(n), U0, g, img)
        self.assertLess(np.abs(S0[:, 2]).max(), 1e-12)            # Rise 0 = the plain plane


class LaneGNbody(unittest.TestCase):
    """Lane G (27 Oct): nbody (FX7c card 12)."""

    def test_momentum_and_orbits(self):
        n = 600
        U, p = U_for('nbody', 1, extra={'Count': n, 'Bodies': 512})
        g = L['Glob'](U, asp=U['uSt2'][1], fr=0, npts=n)
        i = np.arange(n)
        S = L['nbody_seed'](i, U, g)
        N = L['nb_n'](U, g)
        m = L['nb_mass'](np.arange(N), U, g)
        p0 = (S[:N, 2:] * m[:, None]).sum(0)
        for _ in range(30):
            S = L['nbody_step'](i, S, U, g, 1.0 / 60.0, S)
        p1 = (S[:N, 2:] * m[:, None]).sum(0)
        self.assertLess(np.abs(p1 - p0).max(), 1e-9)                     # pair forces cancel: momentum kept
        self.assertTrue(np.all(S[N:] == 0.0))                            # stars are not simulated
        U1, _ = U_for('nbody', 3, extra={'Count': n, 'Bodies': 512, 'Discmass': 0.0})
        g1 = L['Glob'](U1, asp=U1['uSt2'][1], fr=0, npts=n)
        S = L['nbody_seed'](i, U1, g1)
        r0 = np.sqrt((S[1:512, :2] ** 2).sum(-1))
        for _ in range(60):
            S = L['nbody_step'](i, S, U1, g1, 1.0 / 60.0, S)
        r1 = np.sqrt((S[1:512, :2] ** 2).sum(-1))
        far = r0 > 0.1
        self.assertLess(np.median(np.abs(r1[far] / r0[far] - 1.0)), 0.05)  # circular orbits around the core

    def test_tiled_main_text(self):
        M = MODS['nbody']
        t = NS['state_text'](M)
        self.assertIn('shared vec4 nbT[64];', t)
        self.assertEqual(t.count('barrier();'), 2)
        self.assertNotIn('return;\n    int N', t)                         # no early return before the barriers
        head = t.split('for (int t = 0; t < 64; t++)')[0].split('void main()')[1]
        self.assertNotIn('return', head)
