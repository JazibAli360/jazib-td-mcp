"""Offline tests for the shared palette convention (lane W1-B): palette_map_logic's palette_stops / pal_rows /
pal_ctl / pal_eval / pal_step / colsrc_eval / pal_shift / stops_from_pixels / bind_glsl / cook_chop, a vectorised
numpy reference written independently of pal_eval, and a glslc compile of builders/glsl/px_palette.glsl (a syntax /
type check, NOT a TD compile; the GPU parity check is the first consumer's live check, docs/builds/palette_convention.md).
Run: python3 -I -m unittest discover -s test -p 'test_palette_conv.py'"""
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'builders'))
import palette_map_logic as L  # noqa: E402

try:
    import numpy as np
except ImportError:                                 # pragma: no cover
    np = None

GLSL_PATH = os.path.join(REPO, 'builders', 'glsl', 'px_palette.glsl')


def glsl_text():
    with open(GLSL_PATH) as fh:
        return fh.read()


# ---------------------------------------------------------------------------------------------- numpy reference
def _np_lin(c):
    c = np.maximum(c, 0.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _np_enc(c):
    c = np.maximum(c, 0.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1.0 / 2.4) - 0.055)


M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
               [0.0883024619, 0.2817188376, 0.6299787005]]) if np else None
M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
               [0.0259040371, 0.7827717662, -0.8086757660]]) if np else None


def np_to_lab(c):
    return np.cbrt(_np_lin(c) @ M1.T) @ M2.T


N2 = np.array([[1.0, 0.3963377774, 0.2158037573], [1.0, -0.1055613458, -0.0638541728],
               [1.0, -0.0894841775, -1.2914855480]]) if np else None
N1 = np.array([[4.0767416621, -3.3077115913, 0.2309699292], [-1.2684380046, 2.6097574011, -0.3413193965],
               [-0.0041960863, -0.7034186147, 1.7076147010]]) if np else None


def np_from_lab(q):
    # Ottosson's published inverse constants (as the shader); they invert M1 / M2 to ~3e-6 only, so a round trip
    # through OKLab is good to ~1e-5, far below 1/255.
    return _np_enc(((q @ N2.T) ** 3) @ N1.T)


def np_pal(rows, ctl, t):
    """Vectorised pxPal over an array t (independent of L.pal_eval: searchsorted, no loop)."""
    t = np.asarray(t, dtype=np.float64)
    n = min(max(int(math.floor(ctl[0] + 0.5)), 0), 16)
    R = np.asarray(rows, dtype=np.float64)
    if n == 0:
        return np.zeros(t.shape + (3,))
    if n == 1:
        return np.broadcast_to(R[0, :3], t.shape + (3,)).copy()
    col, pos = R[:n, :3], R[:n, 3]
    mode, shift, lab = int(round(ctl[2])), ctl[1], ctl[3] > 0.5
    if mode == 2:
        u = np.mod(t + shift, 1.0)
    else:
        u = np.clip(t, 0.0, 1.0)
        if shift != 0.0:
            u = np.mod(u + shift, 1.0)
    if mode == 1:
        return col[np.minimum((u * n).astype(int), n - 1)]

    def mix(a, b, f):
        f = f[..., None]
        if lab:
            return np_from_lab(np_to_lab(a) + (np_to_lab(b) - np_to_lab(a)) * f)
        return a + (b - a) * f

    j = np.clip(np.searchsorted(pos, u, side='right') - 1, 0, n - 2)    # last stop with pos <= u
    a, b = pos[j], pos[j + 1]
    out = mix(col[j], col[j + 1], np.clip((u - a) / np.maximum(b - a, 1e-6), 0.0, 1.0))
    out = np.where((u <= pos[0])[..., None], col[0], out)
    out = np.where((u >= pos[-1])[..., None], col[n - 1], out)
    if mode == 2:
        wrap = (u < pos[0]) | (u >= pos[-1])
        x = np.where(u < pos[0], u + 1.0, u)
        f = np.clip((x - pos[-1]) / max(pos[0] + 1.0 - pos[-1], 1e-6), 0.0, 1.0)
        out = np.where(wrap[..., None], mix(np.broadcast_to(col[n - 1], u.shape + (3,)),
                                            np.broadcast_to(col[0], u.shape + (3,)), f), out)
    return out


# ---------------------------------------------------------------------------------------------- fakes for TD
class FPar(object):
    def __init__(self, v=''):
        self.val, self.expr, self.mode = v, '', 'c'

    def eval(self):
        return self.val


class FPars(object):
    def __getattr__(self, name):
        p = FPar()
        object.__setattr__(self, name, p)
        return p


class FSeq(object):
    def __init__(self, n=0):
        self.numBlocks = n


class FSeqs(object):
    def __init__(self):
        self.array, self.vec = FSeq(1), FSeq(1)


class FOp(object):
    def __init__(self):
        self.par, self.seq = FPars(), FSeqs()


class FChan(dict):
    pass


class FScript(object):
    def __init__(self):
        self.chans, self.numSamples = {}, 0

    def clear(self):
        self.chans = {}

    def appendChan(self, n):
        self.chans[n] = FChan()
        return self.chans[n]


# ---------------------------------------------------------------------------------------------- tests
class Sources(unittest.TestCase):
    def test_stop_presets(self):
        for key in L.STOP_PRESET_KEYS:
            for mode in ('gradient', 'steps', 'cycle'):
                st = L.palette_stops({'source': key, 'mode': mode})
                self.assertTrue(2 <= len(st) <= L.PAL_MAX, key)
                pos = [s[3] for s in st]
                self.assertEqual(pos, sorted(pos), key)
                self.assertTrue(0.0 <= pos[0] and pos[-1] <= 1.0, key)
                if mode == 'cycle':
                    self.assertLess(pos[-1] - pos[0], 1.0, key + ': cycle needs a wrap segment')
        self.assertEqual(L.palette_stops({'source': 'neon_trio'})[1][:3], L.hex_to_rgb('00F0FF'))

    def test_px_ramp_matches_colour_ramp_defaults(self):
        want = [(0.05, 0.25, 0.30), (0.1, 0.55, 0.6), (1.0, 0.55, 0.2), (1.0, 0.95, 0.8)]
        for s, w in zip(L.palette_stops({'source': 'px_ramp'}), want):
            for a, b in zip(s[:3], w):
                self.assertAlmostEqual(a, b, delta=0.5 / 255)

    def test_lospec_presets_even_and_downsampled(self):
        st = L.palette_stops({'source': 'pico8'})
        self.assertEqual(len(st), 16)
        self.assertEqual([s[3] for s in st], [i / 15.0 for i in range(16)])
        big = L.palette_stops({'source': 'resurrect64'})
        self.assertEqual(len(big), 16)
        self.assertEqual(big[0][:3], L.hex_to_rgb(L.preset('resurrect64')[0]))
        self.assertEqual(big[-1][:3], L.hex_to_rgb(L.preset('resurrect64')[-1]))
        cyc = L.palette_stops({'source': 'gameboy', 'mode': 'cycle'})
        self.assertEqual([s[3] for s in cyc], [0.0, 0.25, 0.5, 0.75])

    def test_custom_rows_positions(self):
        st = L.palette_stops({}, custom_rows=[['hex', 'pos'], ['#ff0000', '0.2'], ['00ff00', ''], ['0000ff', '0.6'],
                                              ['bogus'], ['#fff']])
        self.assertEqual(len(st), 4)
        self.assertEqual([round(s[3], 9) for s in st], [0.2, 0.4, 0.6, 1.0])
        st = L.palette_stops({'stops': [['#000', 0.5], '#fff']})
        self.assertEqual([s[3] for s in st], [0.5, 1.0])
        st = L.palette_stops({'stops': ['#fff', ['#000', 0.5]]})
        self.assertEqual([s[3] for s in st], [0.0, 0.5])
        st = L.palette_stops({'stops': [['#000', 0.8], ['#fff', 0.3]]})       # never descending
        self.assertEqual([s[3] for s in st], [0.8, 0.8])
        st = L.palette_stops({'stops': [[2.0, 0.5, 0.0, 0.0], [0.0, 0.0, 4.0, 1.0]]})   # HDR rgb rows
        self.assertEqual(st[1], (0.0, 0.0, 4.0, 1.0))
        good, bad = L.parse_stop_rows([['#c4e', 'x'], ['nope']])
        self.assertEqual(good, [('CC44EE', None)])
        self.assertEqual(bad, ['nope'])

    def test_file_and_reverse(self):
        gpl = b'GIMP Palette\nName: t\n#\n255 0 0 red\n0 255 0\n0 0 255\n'
        fh = L.parse_file('x.gpl', gpl)
        st = L.palette_stops({'source': 'file'}, file_hex=fh)
        self.assertEqual([s[:3] for s in st], [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)])
        rv = L.palette_stops({'source': 'file', 'reverse': True}, file_hex=fh)
        self.assertEqual([s[:3] for s in rv], [(0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)])
        self.assertEqual([s[3] for s in rv], [0.0, 0.5, 1.0])

    def test_empty(self):
        st = L.palette_stops({'source': 'file'})
        self.assertEqual(st, [])
        rows, ctl = L.pal_rows(st), L.pal_ctl(st)
        self.assertEqual(len(rows), 16)
        self.assertEqual(ctl[0], 0.0)
        self.assertEqual(L.pal_eval(rows, ctl, 0.3), (0.0, 0.0, 0.0))
        self.assertEqual(L.pal_step(rows, ctl, 3), (0.0, 0.0, 0.0))

    def test_menus(self):
        keys = [k for k, _l in L.PAL_SOURCES]
        self.assertEqual(len(keys), len(set(keys)), 'stop presets must not reuse a Lospec key')
        self.assertEqual([m[0] for m in L.PAL_MODES], ['gradient', 'steps', 'cycle'])
        self.assertEqual([m[0] for m in L.PAL_INTERP], ['rgb', 'oklab'])
        self.assertEqual([m[0] for m in L.COLSRC_MODES], ['solid', 'palette', 'attr', 'source', 'index'])


class Uniforms(unittest.TestCase):
    def test_rows_ctl_channels(self):
        st = L.palette_stops({'source': 'acid', 'mode': 'steps'})
        rows = L.pal_rows(st)
        self.assertEqual(len(rows), 16)
        self.assertTrue(all(len(r) == 4 for r in rows))
        self.assertEqual(rows[15], rows[2])                              # padding repeats the last stop
        self.assertEqual(L.pal_ctl(st, 'steps', 'oklab', 2.25), [3.0, 0.25, 1.0, 1.0])
        ch = L.pal_chop_channels(rows)
        self.assertEqual(list(ch), ['r', 'g', 'b', 'pos'])
        self.assertEqual(ch['pos'][:3], [0.0, 0.5, 1.0])

    def test_cook_chop(self):
        so = FScript()
        rows = L.pal_rows(L.palette_stops({'source': 'neon_green'}))
        L.cook_chop(so, rows)
        self.assertEqual(so.numSamples, 16)
        self.assertEqual(list(so.chans), ['r', 'g', 'b', 'pos'])
        self.assertEqual(so.chans['g'][2], 1.0)
        self.assertEqual(so.chans['pos'][1], 0.35)

    def test_bind_glsl(self):
        o = FOp()
        o.par.array0name.val = 'uPts'                                    # an existing block is kept
        k, v = L.bind_glsl(o, 'pal_chop', [4, "op('drv')['shift']", 0, 1])
        self.assertEqual((k, v), (1, 1))
        self.assertEqual(o.seq.array.numBlocks, 2)
        self.assertEqual(o.par.array1name.val, 'uPal')
        self.assertEqual(o.par.array1type.val, 'vec4')
        self.assertEqual(o.par.array1chop.val, 'pal_chop')
        self.assertEqual(o.par.array1arraytype.val, 'uniformarray')
        self.assertEqual(o.par.vec1name.val, 'uPalCtl')
        self.assertEqual(o.par.vec1valuex.val, 4.0)
        self.assertEqual(o.par.vec1valuey.expr, "op('drv')['shift']")
        self.assertEqual((o.par.array0name.val, o.par.vec0name.val), ('uPts', ''))
        self.assertEqual(L.bind_glsl(o, 'pal_chop', [3, 0, 0, 0]), (1, 1))   # idempotent: same blocks reused
        self.assertEqual(o.seq.array.numBlocks, 2)
        self.assertEqual(o.par.vec1valuex.val, 3.0)


@unittest.skipUnless(np, 'numpy missing')
class Reference(unittest.TestCase):
    """pal_eval (scalar, mirrors the GLSL line by line) == np_pal (vectorised, written separately) at 1 k positions."""

    def test_parity_all_modes(self):
        t = np.linspace(-0.25, 1.25, 1000)
        rng = np.random.RandomState(7)
        t = np.concatenate([t, rng.uniform(-2, 3, 1000)])
        specs = [{'source': k} for k in ('neon_green', 'fire', 'rainbow', 'pico8', 'gameboy', 'acid')]
        specs.append({'stops': [['#000', 0.0], ['#f00', 0.4], ['#0f0', 0.4], ['#00f', 0.9]]})    # hard edge
        specs.append({'stops': [[3.0, 0.2, 0.0, 0.1], [0.0, 0.5, 2.0, 0.7]]})                   # HDR, inset ends
        worst = 0.0
        for sp in specs:
            for mode in ('gradient', 'steps', 'cycle'):
                st = L.palette_stops(dict(sp, mode=mode))
                rows = L.pal_rows(st)
                for interp in ('rgb', 'oklab'):
                    for shift in (0.0, 0.3, 0.875):
                        ctl = L.pal_ctl(st, mode, interp, shift)
                        ref = np_pal(rows, ctl, t)
                        got = np.array([L.pal_eval(rows, ctl, float(x)) for x in t])
                        worst = max(worst, float(np.abs(ref - got).max()))
        self.assertLess(worst, 1e-6)

    def test_oklab_roundtrip_hdr(self):
        for c in [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (0.2, 0.9, 0.4), (3.0, 0.5, 0.1), (0.0, 0.0, 6.0)]:
            back = L.pal_from_lab(L.pal_to_lab(c))
            for a, b in zip(back, c):
                self.assertAlmostEqual(a, b, delta=1e-5 * max(1.0, b))


class Behaviour(unittest.TestCase):
    def rc(self, spec, mode='gradient', interp='rgb', shift=0.0):
        st = L.palette_stops(dict(spec, mode=mode))
        return L.pal_rows(st), L.pal_ctl(st, mode, interp, shift)

    def close(self, a, b, d=1e-9):
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, delta=d)

    def test_gradient_ends_and_mid(self):
        rows, ctl = self.rc({'stops': ['#000000', '#ffffff']})
        self.close(L.pal_eval(rows, ctl, -1.0), (0, 0, 0))
        self.close(L.pal_eval(rows, ctl, 2.0), (1, 1, 1))
        self.close(L.pal_eval(rows, ctl, 0.25), (0.25, 0.25, 0.25))
        rows, ctl = self.rc({'stops': ['#000000', '#ffffff']}, interp='oklab')
        mid = L.pal_eval(rows, ctl, 0.5)
        self.assertAlmostEqual(L.pal_to_lab(mid)[0], 0.5, delta=1e-7)        # OKLab: perceptual mid-grey

    def test_hard_edge(self):
        rows, ctl = self.rc({'stops': [['#ff0000', 0.0], ['#ff0000', 0.5], ['#0000ff', 0.5], ['#0000ff', 1.0]]})
        self.close(L.pal_eval(rows, ctl, 0.4999), (1, 0, 0))
        self.close(L.pal_eval(rows, ctl, 0.5), (0, 0, 1))

    def test_steps_equal_bands(self):
        rows, ctl = self.rc({'source': 'cga0hi'}, mode='steps')
        hexes = L.preset('cga0hi')
        for k, t in enumerate((0.1, 0.3, 0.6, 0.99)):
            self.assertEqual(L.rgb_to_hex(L.pal_eval(rows, ctl, t)), hexes[k])
        self.assertEqual(L.rgb_to_hex(L.pal_eval(rows, ctl, 1.0)), hexes[3])

    def test_shift_one_stop(self):
        st = L.palette_stops({'source': 'neon_trio', 'mode': 'steps'})
        rows = L.pal_rows(st)
        c0, c1 = L.pal_ctl(st, 'steps'), L.pal_ctl(st, 'steps', shift=1.0 / 3)
        for i in range(-4, 7):
            self.assertEqual(L.pal_step(rows, c1, i), L.pal_step(rows, c0, i + 1))
        for t in (0.1, 0.5, 0.8):
            self.assertEqual(L.pal_eval(rows, c1, t), L.pal_eval(rows, c0, (t + 1.0 / 3) % 1.0))

    def test_cycle_is_seamless(self):
        for key in ('rainbow', 'neon_green', 'fire'):
            rows, ctl = self.rc({'source': key}, mode='cycle')
            a, b = L.pal_eval(rows, ctl, 1.0 - 1e-7), L.pal_eval(rows, ctl, 1e-7)
            self.close(a, b, 1e-4)
            self.close(L.pal_eval(rows, ctl, 0.3), L.pal_eval(rows, ctl, 2.3), 1e-9)

    def test_colsrc(self):
        rows, ctl = self.rc({'stops': ['#000000', '#ffffff', '#ff0000']})
        solid, src = (0.1, 0.2, 0.3), (0.9, 0.8, 0.7)
        self.assertEqual(L.colsrc_eval(L.colsrc_vec('solid'), solid, src, 0.0, rows, ctl), solid)
        self.close(L.colsrc_eval(L.colsrc_vec('palette', 0.5), solid, src, 9.0, rows, ctl), (1, 1, 1))
        self.close(L.colsrc_eval(L.colsrc_vec('attr', 0.0, 0.5), solid, src, 0.5, rows, ctl), (0.5, 0.5, 0.5))
        self.assertEqual(L.colsrc_eval(L.colsrc_vec('source'), solid, src, 0.0, rows, ctl), src)
        self.close(L.colsrc_eval(L.colsrc_vec('index', 0.0, 1.0), solid, src, 2.0, rows, ctl), (1, 0, 0))
        self.close(L.colsrc_eval(L.colsrc_vec('index', 0.0, 1.0), solid, src, 3.0, rows, ctl), (0, 0, 0))
        self.close(L.colsrc_eval(L.colsrc_vec('solid', keep=0.5), solid, src, 0.0, rows, ctl), (0.5, 0.5, 0.5))
        pars = L.colsrc_pars('line')
        self.assertEqual([p[0] for p in pars], ['Linecol', 'Linecolsrc', 'Linepalpos', 'Linepalspread', 'Linekeep'])


class Drives(unittest.TestCase):
    def test_bpm_step(self):
        d = {'kind': 'bpm_step', 'every': 2}
        self.assertEqual(L.pal_shift(d, 4, beats=0.0), 0.0)
        self.assertEqual(L.pal_shift(d, 4, beats=1.99), 0.0)
        self.assertEqual(L.pal_shift(d, 4, beats=2.0), 0.25)
        self.assertEqual(L.pal_shift(d, 4, beats=9.0), 0.0)               # 4 steps = a full turn
        self.assertEqual(L.pal_shift(d, 4, base=0.5, beats=2.0), 0.75)

    def test_cycle_audio_onsets_manual(self):
        self.assertAlmostEqual(L.pal_shift({'kind': 'bpm_cycle', 'every': 4}, 5, beats=6.0), 0.5)
        self.assertAlmostEqual(L.pal_shift({'kind': 'audio', 'gain': 0.5}, 5, level=0.8), 0.4)
        self.assertAlmostEqual(L.pal_shift({'kind': 'onset_step'}, 5, onsets=7), 0.4)
        self.assertAlmostEqual(L.pal_shift(None, 5, base=1.3), 0.3)
        self.assertAlmostEqual(L.beats_from(30.0, 128.0), 64.0)


class Image(unittest.TestCase):
    def test_two_colours(self):
        px = [(1.0, 0.0, 0.5)] * 300 + [(0.0, 0.2, 1.0)] * 100 + [(0.5, 0.5, 0.5, 0.0)] * 50   # last = transparent
        cols = L.stops_from_pixels(px, n=4)
        self.assertEqual(len(cols), 2)
        want = [(0.0, 0.2, 1.0), (1.0, 0.0, 0.5)]                  # sorted dark -> light (OKLab L)
        for c, w in zip(cols, want):
            for a, b in zip(c, w):
                self.assertAlmostEqual(a, b, delta=1e-4)
        self.assertEqual(L.stops_from_pixels(px, n=4), cols)                                   # deterministic

    @unittest.skipUnless(np, 'numpy missing')
    def test_numpy_image_and_spec(self):
        img = np.zeros((8, 16, 4), dtype=np.float32)
        img[..., 3] = 1.0
        img[:, :8, 0] = 1.0                                   # left red, right black
        st = L.palette_stops({'source': 'image', 'n': 3}, pixels=img)
        self.assertEqual([L.rgb_to_hex(s[:3]) for s in st], ['000000', 'FF0000'])
        self.assertEqual([s[3] for s in st], [0.0, 1.0])


class GlslContract(unittest.TestCase):
    def test_names_and_sizes(self):
        g = glsl_text()
        self.assertIn('#define PX_PAL_MAX %d' % L.PAL_MAX, g)
        self.assertIn('uniform vec4 uPal[PX_PAL_MAX];', g)
        self.assertIn('uniform vec4 uPalCtl;', g)
        for fn in ('vec3 pxPal(float t)', 'vec3 pxPalStep(int i)', 'vec3 pxColSrc(vec4 cs, vec3 solid, vec3 src, float attrT)'):
            self.assertIn(fn, g)
        self.assertTrue(all(ord(ch) < 128 for ch in g), 'ASCII only')
        self.assertEqual(re.findall(r'm == (\d)', g), ['0', '1', '2', '4'])   # 3 = source is the else branch


STUB_COMPUTE = """#version 460
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
layout(local_size_x = 8, local_size_y = 8) in;
"""
KERNEL = """
void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	float t = float(p.x) / 64.0;
	vec3 c = pxPal(t) + pxPalStep(p.y) + pxColSrc(vec4(2.0, 0.1, 1.0, 0.2), vec3(1.0), vec3(0.5), t);
	imageStore(mTDComputeOutputs[0], ivec3(p, 0), vec4(c, 1.0));
}
"""
STUB_FRAG = """#version 460
layout(location = 0) out vec4 fragColor[1];
in vec2 vUV;
"""
FRAG = """
void main() { fragColor[0] = vec4(palette(vUV.x) + palette_step(int(vUV.y * 8.0)), 1.0); }
"""


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, ext):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.' + ext)
            with open(p, 'w') as fh:
                fh.write(text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            return r.returncode == 0, r.stderr[:3000]

    def test_compute(self):
        ok, err = self._ok(STUB_COMPUTE + glsl_text() + glsl_text() + KERNEL, 'comp')   # twice: include guard
        self.assertTrue(ok, err)

    def test_fragment_short_names(self):
        ok, err = self._ok(STUB_FRAG + '#define PX_PAL_SHORT_NAMES\n' + glsl_text() + FRAG, 'frag')
        self.assertTrue(ok, err)

    def test_short_names_off_by_default(self):
        ok, _err = self._ok(STUB_FRAG + glsl_text() + FRAG, 'frag')
        self.assertFalse(ok, 'palette() must not exist unless PX_PAL_SHORT_NAMES (ph_look / rd_look define their own)')


if __name__ == '__main__':
    unittest.main()
