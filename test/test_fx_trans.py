"""Offline tests for FX_trans (G-TRANS): builders/fx_trans_logic.py, builders/fx_trans.py, builders/glsl/fx_trans/.
Run: python3 -I -m unittest discover -s test -p 'test_fx_trans.py'
GLSL: the generated compute shader (whole bank + every single type) is compiled with glslc (OpenGL target) against
stubs of the TD functions: a syntax / type check, NOT a TD compile (LIVE CHECK T1 in docs/builds/fx_trans.md)."""
import ast
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
GLDIR = os.path.join(BUILDERS, 'glsl', 'fx_trans')
sys.path.insert(0, BUILDERS)
import fx_trans_logic as L  # noqa: E402
import fx_analog_crt_logic as CRT  # noqa: E402

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None

STUB = """#version 460
uniform sampler2D sTD2DInputs[3];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
"""


def rd(p):
    with open(p) as fh:
        return fh.read()


class Files(unittest.TestCase):
    def test_ascii(self):
        files = [os.path.join(BUILDERS, f) for f in ('fx_trans.py', 'fx_trans_logic.py')] + \
            [os.path.join(GLDIR, f) for f in os.listdir(GLDIR)]
        for f in files:
            with open(f, 'rb') as fh:
                self.assertTrue(all(b < 128 for b in fh.read()), f)

    def test_vendored_set_and_licences(self):
        stems = sorted(f[:-5] for f in os.listdir(GLDIR) if f.endswith('.glsl'))
        self.assertEqual(stems, sorted(s for _t, s in L.GL_ALL))
        src = rd(os.path.join(GLDIR, 'SOURCES.md'))
        for t, stem in L.GL_ALL:
            info = L.parse_gl(L.gl_text(stem))
            self.assertIn(info['license'], ('MIT', 'BSD 3 Clause'), stem)
            if info['license'] != 'MIT':                                 # BSD: the notice stays in the file
                self.assertIn('Redistributions of source code must retain', L.gl_text(stem), stem)
            self.assertTrue(info['author'], stem)
            self.assertIn('`%s.glsl`' % stem, src)
            self.assertIn(info['author'].split('<')[0].strip(), src, stem)
        self.assertIn('0efa1651dfdbc0cdbd57f4cda55f12d8b3dbc0c5', src)

    def test_counts(self):
        self.assertEqual(len(L.GL), 25)
        self.assertEqual(len(L.GL_MORE), 14)
        self.assertEqual(len(L.GL_W3), 9)
        self.assertEqual(len(L.TYPES), 53)
        self.assertEqual(L.TYPES[29:43], [g[0] for g in L.GL_MORE])        # wave 2 indices fixed
        self.assertEqual(L.TYPES[-1], 'jigsaw')
        self.assertEqual(L.TYPES[26:29], ['tvoff', 'mosh', 'beatripple'])  # earlier indices fixed (presets)     # new types append (preset menu indices)
        self.assertEqual(len(set(L.TYPES)), len(L.TYPES))
        self.assertNotIn('mosh', L.SHADER_TYPES)


class Parse(unittest.TestCase):
    def test_defaults(self):
        B = L.bank()
        self.assertEqual(B['fadecolor']['params'][0][:3], ('color', 'vec4', [0.0, 0.0, 0.0, 1.0]))
        self.assertEqual(B['fadecolor']['params'][1][2], [0.4])
        self.assertEqual(B['pixelize']['params'][0][:3], ('squaresMin', 'ivec2', [20.0, 20.0]))
        self.assertEqual(B['circleopen']['params'][1][:3], ('opening', 'bool', [1.0]))
        self.assertEqual(B['cube']['params'][2][3:], (0.0, 1.0))              # @range(0, 1)
        self.assertEqual(B['displace']['samplers'], ['displacementMap'])
        self.assertEqual(len(B['stripmosh']['params']), 9)

    def test_comment_forms(self):
        i = L.parse_gl('uniform vec3 color /* = vec3(0.9, 0.4, 0.2) */;\nuniform float a; //=1.5\n'
                       'uniform float b; // = 2 ; // note\nuniform bool r; // = false\n')
        self.assertEqual([p[2] for p in i['params']], [[0.9, 0.4, 0.2], [1.5], [2.0], [0.0]])

    def test_knobs_fit(self):
        for t in L.TYPES:
            rows = L.knob_table(t)
            self.assertLessEqual(len(rows), L.NKNOBS, t)
            L.knob_slots(L.bank()[t]['params'])
        self.assertEqual(L.knob_table('wipe')[0][0], 'direction x')
        self.assertEqual(L.knob_table('burn')[2][0], 'burnColor b')
        self.assertEqual(L.kref(9), 'uK2.y')


class Wrap(unittest.TestCase):
    def test_prefix_and_init(self):
        B = L.bank()
        t = L.wrap_gl('cube', L.gl_text('Cube'), B['cube']['params'])
        self.assertIn('vec4 tcube_transition(vec2 op)', t)
        self.assertIn('tcube_persp = uK0.x;', t)
        self.assertNotRegex(t, r'(?<![\w.])persp\b')
        self.assertNotIn('uniform', t)

    def test_macros_undefined(self):
        B = L.bank()
        t = L.wrap_gl('filmburn', L.gl_text('FilmBurn'), B['filmburn']['params'])
        for m in ('pi', 'clamps', 'repeats'):
            self.assertIn('#define tfilmburn_%s' % m, t)
            self.assertIn('#undef tfilmburn_%s' % m, t)

    def test_sampler_to_matte(self):
        B = L.bank()
        t = L.wrap_gl('displace', L.gl_text('DisplacementMap'), B['displace']['params'], B['displace']['samplers'])
        self.assertIn('#define tdisplace_displacementMap sMatte', t)
        self.assertNotIn('texture2D', t)

    def test_shader_cases(self):
        s = L.shader_text()
        for t in L.SHADER_TYPES:
            self.assertIn('case %d: ' % L.type_index(t), s)
            self.assertIn('t%s_transition(uv)' % t, s)
        one = L.shader_text(['cube'])
        self.assertIn('case %d: tcube_init(); c = tcube_transition(uv);' % L.type_index('cube'), one)
        self.assertNotIn('tswirl_', one)
        self.assertIn('vec4(c.rgb * c.a, c.a)', s)              # premultiplied out

    def test_loops_bounded(self):
        """Every loop in the vendored sources runs to a compile-time constant (T-35 / T-124 rule)."""
        for _t, stem in L.GL_ALL:
            for m in re.finditer(r'for\s*\(([^;]*);([^;]*);', L.gl_text(stem)):
                cond = m.group(2)
                if re.search(r'>=\s*0\.?\s*$', cond):                # count-down loop from a const (LissajousTiles grid)
                    self.assertRegex(m.group(1), r'=\s*grid\.[xy]\s*-\s*1\.', (stem, m.group(1)))
                    self.assertIn('const vec2 grid', L.gl_text(stem))
                    continue
                self.assertRegex(cond, r'(<|<=)\s*([0-9.]+|[A-Z_]+|repeats|passes)\s*$', (stem, cond))


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, what):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.comp')
            with open(p, 'w') as fh:
                fh.write(STUB + text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:3000]))

    def test_bank(self):
        self._ok(L.shader_text(), 'whole bank')

    def test_each_type(self):
        for t in L.SHADER_TYPES:
            self._ok(L.shader_text([t]), t)


class Progress(unittest.TestCase):
    def test_eases(self):
        for e in L.EASES:
            self.assertAlmostEqual(L.ease(e, 0.0), 0.0, 9)
            self.assertAlmostEqual(L.ease(e, 1.0), 1.0, 9)
            v = [L.ease(e, i / 50.0) for i in range(51)]
            self.assertTrue(all(b >= a - 1e-12 for a, b in zip(v, v[1:])), e)
        self.assertAlmostEqual(L.ease('smooth', 0.5), 0.5)
        self.assertEqual(L.ease('linear', 0.49, steps=4), 0.25)
        self.assertEqual(L.ease('linear', 1.0, steps=4), 1.0)

    def test_run_seconds(self):
        self.assertAlmostEqual(L.run_seconds('beats', 2.0, 4.0, 120.0), 2.0)
        self.assertAlmostEqual(L.run_seconds('beats', 2.0, 8.0, 128.0), 3.75)
        self.assertAlmostEqual(L.run_seconds('seconds', 1.5, 4.0, 120.0), 1.5)
        self.assertEqual(L.run_seconds('manual', 1.5, 4.0, 120.0), 0.0)

    def test_quantize(self):
        self.assertEqual(L.quantize_start(10.2, 'off', 120), 10.2)
        self.assertAlmostEqual(L.quantize_start(10.2, 'beat', 120), 10.5)           # beat = 0.5 s
        self.assertAlmostEqual(L.quantize_start(10.2, 'bar', 120), 12.0)            # bar = 2 s
        self.assertAlmostEqual(L.quantize_start(10.0, 'beat', 120), 10.0)           # on the beat: now
        self.assertAlmostEqual(L.quantize_start(5.0, 'beat', 120, phase=0.75), 5.125)
        self.assertAlmostEqual(L.quantize_start(5.0, 'bar', 120, phase=3.0), 5.5)

    def test_go_toggles_and_runs(self):
        st = L.go_state(0.0, 100.0, 2.0, 100.0)
        self.assertEqual((st['Gofrom'], st['Goto'], st['Goswap']), (0.0, 1.0, 0.0))
        self.assertAlmostEqual(L.progress_raw('seconds', 0, st, 101.0), 0.5)
        self.assertEqual(L.progress_raw('seconds', 0, st, 99.0), 0.0)
        self.assertEqual(L.progress_raw('seconds', 0, st, 103.0), 1.0)
        back = L.go_state(1.0, 103.0, 2.0, 103.0, 'forward')
        self.assertEqual((back['Goto'], back['Goswap']), (0.0, 1.0))
        raw = L.progress_raw('seconds', 0, back, 103.5)
        self.assertAlmostEqual(raw, 0.75)
        p, sw = L.shader_progress(raw, back['Goswap'], 'linear')
        self.assertAlmostEqual(p, 0.25)                                  # B -> A plays forward
        self.assertEqual(sw, 1.0)
        mid = L.go_state(0.3, 0.0, 1.0, 0.0)                              # reversal mid-run: from where it is
        self.assertEqual((mid['Gofrom'], mid['Goto']), (0.3, 1.0))
        self.assertEqual(L.progress_raw('manual', 0.4, st, 101.0), 0.4)
        cut = L.go_state(0.0, 5.0, 0.0, 5.0)
        self.assertEqual(L.progress_raw('seconds', 0, cut, 5.0), 1.0)

    def test_out_index(self):
        self.assertEqual([L.out_index(x, False) for x in (0.0, 0.5, 1.0)], [0, 2, 1])
        self.assertEqual(L.out_index(0.5, True), 3)
        self.assertEqual(L.type_index('mosh'), -1)

    def test_pick_random(self):
        for s in range(20):
            self.assertIn(L.pick_random('wipe cube nonsense', 'wipe', seed=s), ['cube'])
        self.assertIn(L.pick_random('all', 'fade', seed=3), L.TYPES)
        self.assertEqual(L.pick_random('', 'fade'), 'fade')


class FakePar:
    def __init__(self, v=None):
        self.val, self.expr, self.mode, self.label, self.enable = v, '', 'c', '', True
        self.normMin = self.normMax = self.default = 0

    def eval(self):
        return self.val


class FakeC:
    def __init__(self, **v):
        self.par = types.SimpleNamespace(**dict((k, FakePar(x)) for k, x in v.items()))
        self._ops = {}

    def op(self, n):
        return self._ops.get(n)


class Runtime(unittest.TestCase):
    def comp(self, **kw):
        base = dict(Type='wipe', Drive='manual', Progress=0.0, Ease='linear', Steps=0, Duration=2.0, Beats=4.0,
                    Bpm=120.0, Bpmchop='', Bpmchan='bpm', Phasechan='', Quantize='off', Backstyle='rewind',
                    Randompool='', Gofrom=0.0, Goto=1.0, Gotime=-1.0, Godur=0.0, Goswap=0.0, Keepknobs=False,
                    Compile='selected')
        base.update(kw)
        c = FakeC(**base)
        for k in range(L.NKNOBS):
            setattr(c.par, 'K%d' % (k + 1), FakePar(0.0))
        return c

    def test_values_manual(self):
        c = self.comp(Progress=0.25, Ease='smooth')
        raw, p, sw, out, ti = L.values(c, 10.0)
        self.assertEqual((raw, sw, out, ti), (0.25, 0.0, 2.0, float(L.type_index('wipe'))))
        self.assertAlmostEqual(p, L.ease('smooth', 0.25))

    def test_chan_one_call_per_cook(self):
        c = self.comp(Progress=0.25)
        c.path = '/t/FX_trans'
        n = [0]
        real = L.values

        def counting(c_, now):
            n[0] += 1
            return real(c_, now)
        L.values = counting
        try:
            got = [L.chan(c, 10.0, k) for k in range(5)]
            self.assertEqual(n[0], 1)
            self.assertEqual(got, real(c, 10.0))
            c.par.Progress.val = 0.5                       # a new cook (channel 0) recomputes
            self.assertEqual(L.chan(c, 10.0, 0), 0.5)
            self.assertEqual(n[0], 2)
        finally:
            L.values = real

    def test_patches_apply(self):
        for tid, pairs in L.PATCHES.items():
            saved = L.PATCHES[tid]
            L.PATCHES[tid] = []
            try:
                unpatched = L.shader_text([tid])
            finally:
                L.PATCHES[tid] = saved
            for old, new in pairs:
                self.assertIn(old, unpatched, tid)
                self.assertNotIn(old, L.shader_text([tid]), tid)
        self.assertNotIn('p.x+p.y', L.shader_text(['filmburn']))
        main = L.shader_text(['fade'])
        self.assertNotIn(') return;', main.split('void main()')[1])     # no early return (barrier-safe)

    def test_go_from_manual(self):
        c = self.comp()
        L.on_go(c, 50.0)
        self.assertEqual(c.par.Drive.val, 'seconds')
        self.assertAlmostEqual(L.values(c, 51.0)[0], 0.5)
        L.on_go(c, 53.0)                                     # at B -> goes back
        self.assertAlmostEqual(L.values(c, 54.0)[0], 0.5)
        self.assertEqual(L.values(c, 56.0)[3], 0.0)          # back at A exactly

    def test_apply_type_labels(self):
        c = self.comp(Type='cube')

        class D:
            text = ''
        c._ops['trans_compute'] = D()
        rows = L.apply_type(c)
        self.assertEqual(len(rows), 4)
        self.assertEqual(c.par.K1.label, 'K1 persp')
        self.assertAlmostEqual(c.par.K1.val, 0.7)
        self.assertFalse(c.par.K5.enable)
        self.assertIn('tcube_transition', c._ops['trans_compute'].text)
        self.assertNotIn('tswirl_', c._ops['trans_compute'].text)
        c.par.Compile.val = 'bank'
        L.apply_type(c, keep=True)
        self.assertIn('tswirl_', c._ops['trans_compute'].text)

    def test_load_sources(self):
        s = json.dumps({'Fade': 'X'})
        old = dict(L.SRC)
        try:
            L.SRC.clear()
            self.assertEqual(L.load_sources(s), 1)
            self.assertEqual(L.gl_text('Fade'), 'X')
        finally:
            L.SRC.clear()
            L.SRC.update(old)


@unittest.skipIf(np is None, 'numpy missing')
class References(unittest.TestCase):
    def test_wipe_ends_and_middle(self):
        k = [1.0, 0.0, 0.0]                                   # direction +x, hard edge
        self.assertEqual(float(L.ref_mask('wipe', 0.0, knobs=k).max()), 0.0)
        self.assertEqual(float(L.ref_mask('wipe', 1.0, knobs=k).min()), 1.0)
        m = L.ref_mask('wipe', 0.5, w=100, h=10, knobs=k)
        self.assertAlmostEqual(float(m.mean()), 0.5, 2)      # left half = B (x < progress)
        self.assertEqual(float(m[0, 10]), 1.0)
        self.assertEqual(float(m[0, 90]), 0.0)

    def test_circle(self):
        m = L.ref_mask('circleopen', 0.5, w=101, h=101, knobs=[0.0, 1.0])
        self.assertEqual(float(m[50, 50]), 1.0)              # centre opened first
        self.assertEqual(float(m[0, 0]), 0.0)
        self.assertEqual(float(L.ref_mask('circleopen', 1.0, knobs=[0.3, 1.0]).min()), 1.0)

    def test_matte(self):
        m = L.ref_mask('matte', 0.5, w=100, h=4, knobs=[0.0, 0.0, 0.0, 1.0])
        self.assertAlmostEqual(float(m.mean()), 0.5, 2)
        self.assertEqual(float(L.ref_mask('matte', 1.0, knobs=[0.1, 0.0, 0.0, 1.0]).min()), 1.0)
        self.assertEqual(float(L.ref_mask('matte', 0.0, knobs=[0.1, 0.0, 0.0, 1.0]).max()), 0.0)
        inv = L.ref_mask('matte', 0.25, w=100, h=4, knobs=[0.0, 1.0, 0.0, 1.0])
        self.assertEqual(float(inv[0, 95]), 1.0)             # inverted: bright side (right) goes first

    def test_fadecolor(self):
        a, b = (1.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0, 1.0)
        self.assertEqual(L.ref_fadecolor(0.0, a, b), list(a))
        self.assertEqual(L.ref_fadecolor(1.0, a, b), list(b))
        mid = L.ref_fadecolor(0.5, a, b)
        self.assertAlmostEqual(mid[0], 1.0 / 27.0, 6)        # phase 0.4: near black at the middle
        self.assertAlmostEqual(mid[2], 1.0 / 27.0, 6)
        self.assertEqual(mid[3], 1.0)

    def test_tvoff_matches_crtfault(self):
        for on in (False, True):
            for i in range(0, 121):
                s = i / 100.0
                self.assertEqual(L.power_mirror(on, s, CRT.LINE_H, 4.0), CRT.power_shape(on, s, 1.0), (on, s))
        self.assertEqual(L.ref_tvoff(0.0)[0], 'A')
        self.assertEqual(L.ref_tvoff(0.5)[0], 'black')
        self.assertEqual(L.ref_tvoff(1.0)[:4], ('B', 1.0, 1.0, 1.0))
        w, sy, sx, g, dot = L.ref_tvoff(0.45 * 0.35 * 0.5)    # A squeezing (gap 0.1: off over 0..0.45)
        self.assertEqual(w, 'A')
        self.assertLess(sy, 1.0)

    def test_jigsaw(self):
        import numpy as np
        kn = [r[1] for r in L.knob_table('jigsaw')]
        self.assertEqual([r[0] for r in L.knob_table('jigsaw')][:3], ['cols', 'rows', 'knob'])
        w0 = L.ref_jigsaw(0.0, 108, 192, kn)[0]
        w1 = L.ref_jigsaw(1.0, 108, 192, kn)[0]
        self.assertTrue(bool((w0 == 0).all()) and bool((w1 == 1).all()))  # ends: all A / all B, no gaps
        last = -1.0
        for p in (0.1, 0.3, 0.5, 0.7, 0.9):                             # B share grows with progress
            w = L.ref_jigsaw(p, 108, 192, kn)[0]
            b = float((w == 1).mean())
            self.assertGreaterEqual(b, last)
            last = b
        # knobs interlock: every piece id is a real cell, pieces own area outside their cell (knobs), and the piece
        # map is the same whichever neighbour asks (the edge hash is shared)
        U, V = L.ref_uv(216, 384)
        px, py = L.jg_piece(U * 6, V * 10, (6, 10), 0.18, 1)
        cx, cy = np.floor(U * 6).astype(int), np.floor(V * 10).astype(int)
        out = (px != cx) | (py != cy)
        self.assertTrue(0.01 < float(out.mean()) < 0.15)
        self.assertTrue(bool((np.abs(px - cx) + np.abs(py - cy) <= 1).all()))
        self.assertEqual(L.TYPES.index('jigsaw'), 52)
        self.assertIn('tjigsaw_transition', L.shader_text(['jigsaw']))
        m = L.ref_mask('jigsaw', 0.5, 54, 96, kn)
        self.assertTrue(0.0 < float(m.mean()) < 1.0)

    def test_beatripple(self):
        import numpy as np
        kn = [r[1] for r in L.knob_table('beatripple')]
        self.assertEqual(L.knob_table('beatripple')[0][0], 'drops')
        m0, ox0, oy0 = L.ref_beatripple(0.0, 54, 96, kn)
        self.assertEqual(float(m0.max()), 0.0)                    # nothing born at 0
        self.assertEqual(float(np.abs(ox0).max() + np.abs(oy0).max()), 0.0)
        m1, ox1, oy1 = L.ref_beatripple(1.0, 54, 96, kn)
        self.assertEqual(float(m1.min()), 1.0)                    # all B at the end, no bend left
        self.assertEqual(float(np.abs(ox1).max() + np.abs(oy1).max()), 0.0)
        last = -1.0
        for p in (0.2, 0.4, 0.6, 0.7, 0.8, 0.95):                 # B share grows with progress (default grow 2)
            f = float(L.ref_beatripple(p, 54, 96, kn)[0].mean())
            self.assertGreaterEqual(f, last)
            last = f
        self.assertLess(float(L.ref_beatripple(0.4, 54, 96, kn)[0].mean()), 0.2)
        # drops 4: only drop 0 exists before progress 0.25 -> the B region is one disc around spot 0
        sx, sy = L.br_spot(0, int(kn[5]))
        self.assertTrue(0.0 <= sx < 1.0 and 0.0 <= sy < 1.0)
        m, _x, _y = L.ref_beatripple(0.2, 540, 960, kn[:4] + [0.0] + kn[5:7] + [1.0])
        ratio = 540.0 / 960.0
        far = np.hypot(max(sx * ratio, ratio - sx * ratio), max(sy, 1.0 - sy))
        r = 0.2 * far
        U, V = L.ref_uv(540, 960)
        d = np.hypot(U * ratio - sx * ratio, V - sy)
        self.assertTrue(bool((m[d < r - 2.0 / 960] == 1.0).all()))          # one disc of radius r around spot 0
        self.assertTrue(bool((m[d > r + 2.0 / 960] == 0.0).all()))
        self.assertGreater(int((m == 1.0).sum()), 1000)
        # the mask type reference = the ripple mask
        self.assertEqual(float(np.abs(L.ref_mask('beatripple', 0.5, 54, 96, kn) -
                                      L.ref_beatripple(0.5, 54, 96, kn)[0]).max()), 0.0)
        self.assertIn('tbeatripple_transition', L.shader_text(['beatripple']))
        self.assertIn('for (int k = 0; k < 16; k++)', L.BEATRIPPLE)


# ------------------------------------------------------------------------------------------------ dry build
class _Par(FakePar):
    pass


class _Pars:
    def __getattr__(self, k):
        if k.startswith('__') or k[:1].isupper():          # custom pars exist only once a page made them
            raise AttributeError(k)
        p = _Par()
        object.__setattr__(self, k, p)
        return p

    def __setattr__(self, k, v):
        getattr(self, k).val = v


class _Conn:
    def __init__(self, owner):
        self.connections, self.inOP = [], None

    def connect(self, src):
        self.connections = [types.SimpleNamespace(owner=getattr(src, 'owner', src))]


class _Out:
    def __init__(self, owner):
        self.owner = owner


class _Page:
    def __init__(self, comp, name):
        self.comp, self.name = comp, name

    def _p(self, nm, label=''):
        p = _Par()
        object.__setattr__(self.comp.par, nm, p)
        p.label = label
        self.comp.custom.append(nm)
        return [p]

    def appendFloat(self, nm, label=''):
        return self._p(nm, label)
    appendInt = appendToggle = appendStr = appendPulse = appendFloat

    def appendMenu(self, nm, label=''):
        return self._p(nm, label)


class _Op:
    def __init__(self, cls, name, parent=None):
        self.OPType, self.name, self.par, self.text, self.comment = cls, name, _Pars(), '', ''
        self.inputConnectors = [_Conn(self) for _ in range(4 if cls != 'glslTOP' else 3)]
        self.outputConnectors = [_Out(self)]
        self.seq = types.SimpleNamespace(vec=types.SimpleNamespace(numBlocks=1))
        self.children, self.customPages, self.custom, self.storage = {}, [], [], {}
        self.path = (parent.path if parent else '') + '/' + name
        self.dock, self.valid, self.viewer, self.allowCooking = None, True, False, True
        self.isCOMP = cls.endswith('COMP')

    def op(self, n):
        return self.children.get(n)

    def create(self, cls, n):
        o = _Op(cls.__name__, n, self)
        self.children[n] = o
        return o

    def appendCustomPage(self, n):
        pg = _Page(self, n)
        self.customPages.append(pg)
        return pg

    def fetch(self, k, d=None, search=False):
        return self.storage.get(k, d)

    def store(self, k, v):
        self.storage[k] = v


CLASSES = ('inTOP', 'outTOP', 'glslTOP', 'textDAT', 'switchTOP', 'selectTOP', 'fitTOP', 'moviefileinTOP', 'rampTOP',
           'noiseTOP', 'constantCHOP', 'parameterexecuteDAT', 'baseCOMP', 'cacheTOP', 'feedbackTOP', 'constantTOP')


class DryBuild(unittest.TestCase):
    """build() against a fake TD: every op, par, uniform, wire and expression the builder (and the reused moshcut
    module through FX_glitch's helpers) makes; <= 3 wired GLSL inputs; uniforms declared in the shader text."""

    def build(self):
        root = _Op('baseCOMP', 'lab')
        lay = types.SimpleNamespace(module=types.SimpleNamespace(layout_stages=lambda *a, **k: 'ok',
                                                                 safe_destroy=lambda o: None))
        ns = dict((c, type(c, (), {})) for c in CLASSES)
        ns['ParMode'] = types.SimpleNamespace(EXPRESSION='e', CONSTANT='c')
        ns['safe_destroy'] = lambda o: None
        ns['op'] = lambda p: lay if p == '/jazib_mcp/handlers' else root
        ns['__name__'] = 'fx_trans_dry'
        exec(rd(os.path.join(BUILDERS, 'fx_trans.py')), ns)
        res = ns['build']('/project1/lab', panel=False)
        return root.op('FX_trans'), res

    def test_build(self):
        c, res = self.build()
        self.assertEqual(res['types'], 53)
        for n in ('in1', 'in2', 'in3', 'a_fit', 'b_fit', 'm_fit', 'prog', 'trans', 'trans_compute', 'mosh', 'out_sel',
                  'out1', 'pexec', 'fx_trans_logic', 'fx_trans_src'):
            self.assertIn(n, c.children, n)
        g = c.op('trans')
        self.assertEqual([cn.connections[0].owner.name for cn in g.inputConnectors], ['a_fit', 'b_fit', 'm_fit'])
        txt = c.op('trans_compute').text
        for k in range(4):
            un = getattr(g.par, 'vec%dname' % k).val
            self.assertIn('uniform vec4 %s;' % un, txt)
            for comp in 'xyzw':
                compile(getattr(g.par, 'vec%dvalue%s' % (k, comp)).expr, '<expr>', 'eval')
        sel = c.op('out_sel')
        self.assertEqual([cn.connections[0].owner.name for cn in sel.inputConnectors],
                         ['a_fit', 'b_fit', 'trans', 'mosh'])
        self.assertEqual(c.op('out1').inputConnectors[0].connections[0].owner.name, 'out_sel')
        self.assertEqual(len(json.loads(c.op('fx_trans_src').text)), 48)
        self.assertEqual(c.par.K1.label, 'K1 -')                     # Type fade has no knobs
        self.assertFalse(c.par.K1.enable)

    def test_mosh_reuse(self):
        c, _ = self.build()
        m = c.op('mosh')
        for n in ('in1', 'b_fit', 'upd', 'mv', 'out_sel', 'out1'):
            self.assertIn(n, m.children, n)                          # FX_glitch moshcut engine ops
        self.assertEqual(m.inputConnectors[0].connections[0].owner.name, 'mosh_a')
        self.assertEqual(m.par.Bsource.val, 'top')
        for pn in ('Melt', 'Order', 'Cutmode', 'Progress', 'Btop', 'Seed'):
            compile(getattr(m.par, pn).expr, '<expr>', 'eval')
        for o in list(c.children.values()) + list(m.children.values()):
            if o.OPType == 'glslTOP':
                self.assertLessEqual(sum(1 for cn in o.inputConnectors if cn.connections), 3, o.name)
            e = getattr(o.par, 'index').expr
            if e:
                compile(e, '<expr>', 'eval')

    def test_pexec_parses(self):
        tree = ast.parse(rd(os.path.join(BUILDERS, 'fx_trans.py')))
        pe = [n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'PEXEC']
        ast.parse(pe[0].value.value)

    def test_presets_full_state(self):
        ns = {'__name__': 'x'}
        exec(rd(os.path.join(BUILDERS, 'fx_trans.py')), ns)
        Lg = ns['load_logic']()
        names = [n for _p, pars in ns['pages'](Lg) for n, *_ in pars]
        self.assertEqual(len(names), len(set(names)))
        for n in names:
            self.assertRegex(n, r'^[A-Z][a-z0-9]*$')
        for _s, _n, vals in ns['presets'](Lg):
            for k in vals:
                self.assertIn(k, names)
            for k in range(L.NKNOBS):
                self.assertIn('K%d' % (k + 1), vals)


if __name__ == '__main__':
    unittest.main()
