"""Offline tests for GEN_pattern (builders/gen_pattern.py + gen_pattern_<module>.py + gen_pattern_logic.py). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_pattern.py'
Checks: rack chain maths, every module's spec (pages / presets / uniforms / GLSL use), every shader compiles with
glslc (skipped when glslc is missing), the pure mirror (hash, Amount 0 passthrough, blends, warps) and that every
preset renders a non-degenerate picture offline."""
import math
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
NS = {}
exec(open(os.path.join(B, 'gen_pattern.py')).read(), NS)
L = {}
exec(open(os.path.join(B, 'gen_pattern_logic.py')).read(), L)
MODS = dict((m, NS['module_ns'](m)) for m in NS['MODULES'])

PRELUDE = """#version 450
layout(binding = 0) uniform sampler2D sTD2DInputs[1];
layout(binding = 1, rgba8) uniform writeonly image2D mTDOut[1];
void TDImageStoreOutput(int i, ivec3 c, vec4 v) { imageStore(mTDOut[0], c.xy, v); }
"""


def U_for(module, preset=None, t=1.0, beats=0.0, level=0.0, W=1080, H=1920, extra=None, bpm=120.0):
    M = MODS[module]
    vals = dict(next(v for s, _n, v in M['PRESETS'] if s == preset)) if preset else {}
    vals.update(extra or {})
    pars = NS['module_pars'](M, vals)
    return L['uniforms'](NS['uniform_spec'](M), pars, W=W, H=H, t=t, beats=beats, level=level, bpm=bpm,
                         pal_src=NS['PAL_SRC'] if M.get('PAL') else None)


def synth(W, H):
    """Test picture: smooth colour ramps + a soft checker (rows bottom first, [y][x] rgba)."""
    return [[(x / (W - 1.0), y / (H - 1.0), 0.5 + 0.5 * math.sin(x * 0.2) * math.sin(y * 0.2), 1.0)
             for x in range(W)] for y in range(H)]


class LazySynth(object):
    """synth() for big frames without building it: src[y][x] computed on demand."""

    def __init__(self, W, H):
        self.W, self.H = W, H

    def __getitem__(self, y):
        return _Row(y, self.W, self.H)


class _Row(object):
    def __init__(self, y, W, H):
        self.y, self.W, self.H = y, W, H

    def __getitem__(self, x):
        return (x / (self.W - 1.0), self.y / (self.H - 1.0), 0.5 + 0.5 * math.sin(x * 0.2) * math.sin(self.y * 0.2), 1.0)


class Rack(unittest.TestCase):
    def test_chain(self):
        rows = [{'name': 'a', 'order': '2'}, {'name': 'b', 'order': '1'}]
        self.assertEqual(NS['plan_chain'](rows), ['b', 'a'])
        e = NS['chain_edges'](['g1', 'k1'])
        self.assertIn(('k1', 0, 'g1_slot'), e)
        self.assertIn(('panic', 0, 'k1_slot'), e)
        self.assertEqual(NS['next_name']('truchet', {'truchet1'}), 'truchet2')

    def test_td_expr_tokens(self):
        e = NS['td_expr']('{Centerx} * $W')
        self.assertEqual(e, 'float(parent().par.Centerx.eval()) * me.par.resolutionw.eval()')
        self.assertIn('menuIndex', NS['td_expr']('{Blend#}'))
        self.assertIn("op('clock_int')", NS['td_expr']('$t'))


class Specs(unittest.TestCase):
    def test_modules_complete(self):
        self.assertEqual(len(MODS), 17)
        for m, M in MODS.items():
            self.assertEqual(M['MODULE'], m)
            self.assertIn(M['KIND'], ('gen', 'warp'))
            self.assertEqual(M['PAGES'][0][1][0][0], 'Amount', m)
            pages = NS['m_pages'](M)
            names = [p[0] for _pg, ps in pages for p in ps]
            self.assertEqual(len(names), len(set(names)), m)           # no par defined twice
            allpars = NS['module_pars'](M)
            for pg in M['PANEL_PAGES']:
                self.assertIn(pg, [p for p, _ in pages], m)
            self.assertTrue(3 <= len(M['PRESETS']) <= 5, m)
            menus = dict((p[0], p[3]['names']) for _pg, ps in pages for p in ps if p[1] == 'Menu')
            for slot, _n, vals in M['PRESETS']:
                for k, v in vals.items():
                    self.assertIn(k, allpars, '%s preset %s: %s' % (m, slot, k))
                    if k in menus:
                        self.assertTrue(v in menus[k] if isinstance(v, str) else 0 <= v < len(menus[k]),
                                        '%s %s %s' % (m, k, v))
            for k in M.get('DEFAULTS', {}):
                self.assertIn(k, allpars, '%s default %s' % (m, k))

    def test_uniforms_declared_and_used(self):
        for m, M in MODS.items():
            spec = NS['uniform_spec'](M)
            self.assertEqual(len(set(n for n, _e in spec)), len(spec), m)
            src = NS['shader'](M)
            for n, ex in spec:
                self.assertEqual(len(ex), 4, (m, n))
                self.assertGreaterEqual(src.count(n), 2, '%s: uniform %s declared but unused' % (m, n))
            U = U_for(m)                                               # every expression evaluates offline
            self.assertEqual(set(U) - {'uPal'}, set(n for n, _e in spec))

    def test_ascii(self):
        for f in ['gen_pattern.py', 'gen_pattern_logic.py', 'glsl/px_palette.glsl'] + [
                'gen_pattern_%s.py' % m for m in NS['MODULES']]:
            with open(os.path.join(B, f), encoding='ascii') as fh:
                fh.read()


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_shader_compiles(self):
        d = tempfile.mkdtemp()
        for m, M in MODS.items():
            p = os.path.join(d, m + '.comp')
            open(p, 'w').write(PRELUDE + NS['shader'](M))
            r = subprocess.run(['glslc', '-fshader-stage=compute', '--target-env=opengl', '-fauto-bind-uniforms',
                                '-fauto-map-locations', '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s: %s' % (m, r.stderr[:800]))


class Mirror(unittest.TestCase):
    def test_hash_known_values(self):
        self.assertEqual(L['lb32'](0), 0)
        h = [L['h2'](x, y, 1) for x in range(-3, 3) for y in range(-3, 3)]
        self.assertTrue(all(0.0 <= v < 1.0 for v in h))
        self.assertGreater(len(set(h)), 30)
        self.assertEqual(L['h2'](-1, 2, 5), L['h2']((-1) & 0xffffffff, 2, 5))   # GLSL uint(int) wrap

    def test_amount_zero_is_passthrough(self):
        src = synth(16, 16)
        for m in NS['MODULES']:
            U = U_for(m, extra={'Amount': 0.0}, W=16, H=16)
            for x, y in ((0, 0), (7, 9), (15, 15)):
                self.assertEqual(L['expect'](m, U, x, y, 16, 16, src), list(src[y][x]), m)

    def test_blend_modes(self):
        U = U_for('truchet', extra={'Palette': 1})
        C = L['Ctx'](U, 1080, 1920)
        src = [0.25, 0.5, 0.75, 1.0]
        for blend, want in ((0, [1.0, 1.0, 1.0, 1.0]), (1, [1.25, 1.5, 1.75, 1.0]), (3, [0.25, 0.5, 0.75, 1.0]),
                            (4, [0.75, 0.5, 0.25, 1.0]), (5, [1.0, 1.0, 1.0, 1.0])):
            U2 = dict(U, uAmt=(1.0, blend, 1.0, 1.0))
            got = L['compose'](U2, C, 1.0, 0.0, src)
            for a, b in zip(got, want):
                self.assertAlmostEqual(a, b, 6, (blend, got))

    def test_truchet_arc_distance(self):
        # Scale 1, centre at pixel 0: q = P / H. A pixel on the arc around corner (0,0) of radius 0.5 is lit.
        U = U_for('truchet', extra={'Scale': 1.0, 'Centerx': 0.0, 'Centery': 0.0, 'Linewidth': 0.1})
        C = L['Ctx'](U, 1080, 1920)
        o = 1 if L['h3'](0, 0, 0, C.SEED) < 0.5 else 0
        cx = 0.0 if o else 1.0                                  # o = 1: arcs around (0,0)/(1,1), else (1,0)/(0,1)
        q = (cx + (0.5 * math.cos(0.6) if o else -0.5 * math.cos(0.6)), 0.5 * math.sin(0.6))
        v, _k = L['gen_truchet'](U, C, q, (0, 0), (0, 0, 0, 1), None)
        self.assertEqual(v, 1.0)
        v2, _k = L['gen_truchet'](U, C, (0.5, 0.5), (0, 0), (0, 0, 0, 1), None)   # cell centre: off the arcs
        self.assertEqual(v2, 0.0)

    def test_quasicrystal_symmetry(self):
        # N waves at pi/N angles: the field is symmetric under rotation by pi/N about the centre (phase 0).
        U = U_for('wallpaper', extra={'Mode': 0, 'Waves': 7, 'Phasespeed': 0.0, 'Scale': 10.0}, t=0.0)
        C = L['Ctx'](U, 1080, 1920)
        q = (0.31, -0.17)
        a = math.pi / 7
        q2 = (math.cos(a) * q[0] - math.sin(a) * q[1], math.sin(a) * q[0] + math.cos(a) * q[1])
        v1 = L['gen_wallpaper'](U, C, q, None, None, None)[0]
        v2 = L['gen_wallpaper'](U, C, q2, None, None, None)[0]
        self.assertAlmostEqual(v1, v2, 9)

    def test_chladni_nodal_line(self):
        # square plate f = cos(n pi x) cos(m pi y) - cos(m pi x) cos(n pi y) is 0 on the diagonal x = y.
        U = U_for('cymatics', extra={'Grain': 0.0})
        C = L['Ctx'](U, 1080, 1920)
        v, _k = L['gen_cymatics'](U, C, (0.3, 0.3), (0.5, 0.5), None, None)
        self.assertAlmostEqual(v, 1.0, 9)

    def test_split_leaves_tile_the_frame(self):
        # fully grown: every sampled pixel lands in a leaf; leaves are disjoint rects (gap 0 -> v = 1 inside).
        U = U_for('split', 3, W=1080, H=1920)
        C = L['Ctx'](U, 1080, 1920)
        lit = sum(L['gen_split'](U, C, None, (x + 0.5, y + 0.5), None, None)[0] > 0
                  for x in range(5, 1080, 97) for y in range(5, 1920, 97))
        self.assertGreater(lit, 100)

    def test_kaleido_wedge_mirror(self):
        # wedge mode: a point and its mirror image across a wedge edge sample the same source uv.
        U = U_for('kaleido2', extra={'Mode': 0, 'Segments': 6.0, 'Rotspeed': 0.0}, W=1080, H=1920)
        C = L['Ctx'](U, 1080, 1920)
        cx, cy = 540.0, 960.0
        r, a = 300.0, math.radians(10.0)
        p1 = (cx + r * math.cos(a), cy + r * math.sin(a))
        p2 = (cx + r * math.cos(-a), cy + r * math.sin(-a))
        u1 = L['kaleido2_src'](U, C, p1)[0][0]
        u2 = L['kaleido2_src'](U, C, p2)[0][0]
        self.assertAlmostEqual(u1[0], u2[0], 9)
        self.assertAlmostEqual(u1[1], u2[1], 9)

    def test_droste_self_similar(self):
        # Twist 0: radius r and r * Ratio map to the same source point (one copy apart).
        U = U_for('droste', extra={'Twist': 0.0, 'Zoomspeed': 0.0, 'Ratio': 4.0})
        C = L['Ctx'](U, 1080, 1920)
        p1 = (540.0 + 0.05 * 1920, 960.0 + 0.02 * 1920)
        p2 = (540.0 + 0.2 * 1920, 960.0 + 0.08 * 1920)
        u1 = L['droste_src'](U, C, p1)[0][0]
        u2 = L['droste_src'](U, C, p2)[0][0]
        self.assertAlmostEqual(u1[0], u2[0], 6)
        self.assertAlmostEqual(u1[1], u2[1], 6)

    def test_droste_no_seam_at_branch_cut(self):
        # Twist 1 (escher 1 strand, double 2 strands): just above and just below the atan2 cut (left of the centre)
        # map to (almost) the same source point; the cos(alpha) scale left a straight seam there (live, 26 Oct).
        for strands, ratio in ((1.0, 4.0), (2.0, 6.0)):
            U = U_for('droste', 1, extra={'Strands': strands, 'Ratio': ratio, 'Zoomspeed': 0.0})
            C = L['Ctx'](U, 1080, 1920)
            for dx in (0.07, 0.19, 0.31):
                a = L['droste_src'](U, C, (540.0 - dx * 1920, 960.0 + 1e-4))[0][0]
                b = L['droste_src'](U, C, (540.0 - dx * 1920, 960.0 - 1e-4))[0][0]
                self.assertLess(abs(a[0] - b[0]) + abs(a[1] - b[1]), 1e-3, (strands, dx, a, b))

    def test_infzoom_weights_and_period(self):
        # one layer of zoom later (t + 1 / Zoomspeed) the picture is the same (seamless loop).
        U1 = U_for('infzoom', 1, t=0.3)
        U2 = U_for('infzoom', 1, t=0.3 + 1.0 / 0.2)
        src = synth(36, 64)
        for x, y in ((3, 5), (18, 32), (30, 60)):
            a = L['expect']('infzoom', U1, x, y, 36, 64, src)
            b = L['expect']('infzoom', U2, x, y, 36, 64, src)
            for i in range(4):
                self.assertAlmostEqual(a[i], b[i], 6)


class Presets(unittest.TestCase):
    def test_every_preset_renders_a_picture(self):
        src = synth(54, 96)
        for m, M in MODS.items():
            for slot, name, _v in M['PRESETS']:
                if M['KIND'] == 'gen':
                    t, beats = NS['check_state'](m)
                    U = U_for(m, slot, t=t, beats=beats, extra=NS['check_pars'](m))
                    big = LazySynth(1080, 1920) if m == 'barcode' else None     # barcode 'scan' reads its input
                    px = [L['expect'](m, U, x, y, 1080, 1920, big) for x, y in L['sample_points'](1080, 1920, 600)]
                else:
                    U = U_for(m, slot, W=54, H=96)
                    px = [L['expect'](m, U, i, j, 54, 96, src) for i in range(0, 54, 2) for j in range(0, 96, 2)]
                lum = [L['luma'](p) for p in px]
                spread = max(lum) - min(lum)
                floor = 0.2 if M['KIND'] == 'gen' else 0.05            # warps: only 'not constant' on the ramp
                self.assertGreater(spread, floor, '%s preset %d %s is flat (%.3f)' % (m, slot, name, spread))
                self.assertTrue(all(0.0 <= c <= 1.0 for p in px for c in p))


class _P(object):
    def __init__(self, v):
        self.val = v

    def eval(self):
        return self.val


class _Pars(object):
    def __init__(self, d):
        for k, v in d.items():
            setattr(self, k, _P(v))


class Fireworks(unittest.TestCase):
    """SX-15 pilot: burst count per hit, void stamps, Auto off by default, beat launches, palette stops."""

    def C(self, U):
        return L['Ctx'](U, 1080, 1920)

    def test_no_shell_without_a_launch(self):
        U = U_for('fireworks', 1, t=5.0)                          # Auto off, no hits (user rule U7)
        self.assertEqual(U['uM4'][3], 0.0)
        self.assertEqual(L['fw_shells'](U, self.C(U)), [])

    def test_one_burst_per_hit(self):
        hits = {}
        for n in range(1, 6):
            hits['Hit%d' % (n - 1)] = 0.2 * n
            U = U_for('fireworks', 1, t=1.2, extra=hits)
            self.assertEqual(len(L['fw_shells'](U, self.C(U))), n)

    def test_hit_ring_code(self):
        # the TD hit DAT code (HIT_PEXEC): ring of Shells, stamps = module time, stale stamps voided (T-162)
        ns = {}
        exec(NS['HIT_PEXEC'] % 8, ns)
        d = dict(('Hit%d' % i, -1000.0) for i in range(8))
        d.update({'Hitnext': 0, 'Shells': 3, 'Phase': 0.0})
        clock = [1.0]

        class Comp(object):
            par = _Pars(d)

            def op(self, name):
                return [clock[0]]
        c = Comp()
        c.par.Hit5.val = 99.0                                    # from another clock
        for k in range(4):
            clock[0] = 1.0 + k
            ns['_fire'](c)
        self.assertEqual([c.par.Hit0.val, c.par.Hit1.val, c.par.Hit2.val], [4.0, 2.0, 3.0])
        self.assertEqual(c.par.Hit5.val, -1000.0)
        self.assertEqual(c.par.Hitnext.val, 1)
        ns['_clear'](c)
        self.assertEqual(c.par.Hit0.val, -1000.0)

    def test_stale_stamp_is_void(self):
        U = U_for('fireworks', 1, t=1.0, extra={'Hit0': 50.0, 'Hit1': 0.5})
        self.assertEqual(U['uH0'][:2], (-1000.0, 0.5))

    def test_auto_and_beat_launch(self):
        U = U_for('fireworks', 1, t=10.0, extra={'Auto': True, 'Rate': 2.0, 'Shells': 4, 'Life': 1.0, 'Rise': 0.5})
        sh = L['fw_shells'](U, self.C(U))
        self.assertEqual(len(sh), 3)                              # launched 0.0, 0.5, 1.0 s ago; 1.5 s = over
        U = U_for('fireworks', 5, t=1.0, beats=3.0, bpm=120.0)    # beat barrage: Beatevery 1, beats 3 -> step 3
        self.assertAlmostEqual(U['uM5'][0], 0.5)
        sh = sorted((s, round(a, 6)) for s, a, _i, _t in L['fw_shells'](U, self.C(U)))
        self.assertEqual(sh, [(0, 1.5), (1, 1.0), (2, 0.5), (3, 0.0)])

    def test_palette_stops_visible(self):
        # neon rings: steps palette, no per-spark spread: saturated pixels show exactly one of the 3 stops
        PM = L['palmap']()
        stops = [tuple(s[:3]) for s in PM['palette_stops']({'source': 'neon_trio', 'mode': 'steps'})]
        U = U_for('fireworks', 3, t=2.0, extra=NS['check_pars']('fireworks'))
        C = self.C(U)
        seen = set()
        for x, y in L['sample_points'](1080, 1920, 3000, 11):
            q = L['space'](U, C, x + 0.5, y + 0.5)
            v, k = L['gen_fireworks'](U, C, q, (x + 0.5, y + 0.5), None, None)
            if v >= 0.05:                                         # Add over black: out = stop x min(v, 1)
                o = L['expect']('fireworks', U, x, y, 1080, 1920)
                o = [o[c] / min(v, 1.0) for c in range(3)]
                hit = [i for i, st in enumerate(stops) if max(abs(o[c] - st[c]) for c in range(3)) < 1e-6]
                self.assertEqual(len(hit), 1, (x, y, o))
                seen.add(hit[0])
        self.assertGreaterEqual(len(seen), 2)

    def test_window_is_conservative(self):
        # every spark that reaches a pixel (d^2 <= 256 w^2) lies in the shader's angle window (fw_window)
        import random
        rnd = random.Random(3)
        bad = 0
        for trial in range(300):
            typ = rnd.choice([1, 2, 3])
            M = rnd.choice([8, 33, 64, 128])
            rt, jo, jz = rnd.random() * 6.283, rnd.random(), rnd.random()
            ct, orient, var = 0.25 + 0.75 * rnd.random(), rnd.random() * 3.1416, rnd.random()
            R, f0, fb, w = 200 + 400 * rnd.random(), 0.5 * rnd.random(), 0.5 + 0.5 * rnd.random(), 0.5 + 4 * rnd.random()
            gy, gy0 = -150 * rnd.random(), -150 * rnd.random()
            cut = 16.0 * w + abs(gy - gy0)
            for _k in range(20):
                ex, ey = (rnd.random() - 0.5) * 2 * R, (rnd.random() - 0.5) * 2 * R
                j0, n = L['fw_window'](typ, M, rt, ct, orient, ex, ey, cut)
                win = set((j0 + i) % M for i in range(n))
                for j in range(M):
                    dx, dy = L['fw_dir'](typ, j, M, rt, jo, jz, ct, orient, var)
                    d2 = L['_fw_seg'](ex, ey, dx * R * f0, dy * R * f0 + gy0 - gy, dx * R * fb, dy * R * fb)
                    if d2 <= 256.0 * w * w and j not in win:
                        bad += 1
        self.assertEqual(bad, 0)

    def test_shell_types(self):
        for typ in range(1, 5):
            U = U_for('fireworks', 1, t=2.0, extra=dict(NS['check_pars']('fireworks'), Type=typ))
            sh = L['fw_shells'](U, self.C(U))
            self.assertTrue(sh and all(t == typ for _s, _a, _i, t in sh), typ)
        U = U_for('fireworks', 1, t=2.0, extra=NS['check_pars']('fireworks'))
        self.assertGreater(len(set(t for _s, _a, _i, t in L['fw_shells'](U, self.C(U)))), 1)   # mixed


class Bokeh(unittest.TestCase):
    def test_layer_drifts_at_drift_speed(self):
        # one layer (z = 1), drift up 0.05 screen heights/s, no sway / twinkle / gradient: the picture at t + dt is the
        # picture at t moved up by Drift x H x dt px (parallax speed of the near layer)
        ex = {'Layers': 1, 'Drift': 0.05, 'Direction': 90.0, 'Sway': 0.0, 'Twinkle': 0.0, 'Gradient': 0.0}
        U1, U2 = U_for('bokeh', 1, t=1.0, extra=ex), U_for('bokeh', 1, t=3.0, extra=ex)
        shift = 0.05 * 1920 * 2.0                                    # 192 px
        n = 0
        for x, y in L['sample_points'](1080, 1600, 400, 5):
            a = L['expect']('bokeh', U1, x, y, 1080, 1920)
            b = L['expect']('bokeh', U2, x, int(y + shift), 1080, 1920)
            n += a[0] > 0.01
            for c in range(3):
                self.assertAlmostEqual(a[c], b[c], 5)
        self.assertGreater(n, 40)

    def test_far_layers_smaller_and_dimmer(self):
        U = U_for('bokeh', 1)
        self.assertLess(U['uM0'][2], 1.0)
        self.assertGreater(U['uM1'][1], 0.0)


class MoltenChrome(unittest.TestCase):
    def test_flat_metal_reflects_the_viewer(self):
        # Bump 0: normal = view axis, the reflected ray goes straight back (r = 0 0 1): every pixel sees the same
        # environment value mix(Floor, Sky, 0.5) + strips at height 0 + spec + 0 Fresnel
        U = U_for('moltenchrome', 1, extra={'Bump': 0.0, 'Lights': 0, 'Spec': 0.0})
        C = L['Ctx'](U, 1080, 1920)
        vals = set()
        for x, y in ((10, 10), (540, 960), (1000, 1800)):
            v, k = L['gen_moltenchrome'](U, C, L['space'](U, C, x + 0.5, y + 0.5), (x + 0.5, y + 0.5), None, None)
            vals.add(round(v, 9))
            self.assertAlmostEqual(k, 0.5, 9)
        self.assertEqual(vals, {round(0.5 * (0.08 + 0.55), 9)})

    def test_bump_tilts_reflection(self):
        U = U_for('moltenchrome', 1)
        C = L['Ctx'](U, 1080, 1920)
        ks = [L['gen_moltenchrome'](U, C, L['space'](U, C, x + 0.5, y + 0.5), None, None, None)[1]
              for x, y in L['sample_points'](1080, 1920, 200, 3)]
        self.assertGreater(max(ks) - min(ks), 0.5)


class Caustic(unittest.TestCase):
    def test_tileable(self):
        # one tile = 1 pattern unit: q and q + (1, 0) / (0, 1) give the same light, both modes
        for mode in (0, 1):
            U = U_for('caustic', 1, extra={'Mode': mode}, t=1.7)
            C = L['Ctx'](U, 1080, 1920)
            for qx, qy in ((0.13, 0.27), (0.61, 0.9), (0.95, 0.05)):
                a = L['gen_caustic'](U, C, (qx, qy), None, None, None)[0]
                for dq in ((1.0, 0.0), (0.0, 1.0), (-2.0, 3.0)):
                    b = L['gen_caustic'](U, C, (qx + dq[0], qy + dq[1]), None, None, None)[0]
                    self.assertAlmostEqual(a, b, 6, (mode, qx, qy, dq))

    def test_flat_water_no_caustic(self):
        # Depth 0: the map is the identity, det 1 everywhere: light = 1 / (1 + Soft) - Base, constant
        U = U_for('caustic', 1, extra={'Depth': 0.0})
        C = L['Ctx'](U, 1080, 1920)
        want = (1.0 / (1.0 + 0.08) - 0.65) * 0.35
        for qx, qy in ((0.1, 0.2), (0.7, 0.4)):
            self.assertAlmostEqual(L['gen_caustic'](U, C, (qx, qy), None, None, None)[0], want, 9)


class ModuleArrange(unittest.TestCase):  # T-163: feedback modules lay out in rows
    def test_feedback_module_rows(self):
        from types import SimpleNamespace as S
        fb = S(children=[S(OPType='glslTOP'), S(OPType='feedbackTOP'), S(OPType='nullTOP')])
        plain = S(children=[S(OPType='glslTOP'), S(OPType='nullTOP')])
        self.assertEqual(NS['module_arrange'](fb), 'rows')
        self.assertEqual(NS['module_arrange'](plain), 'mixed')
        self.assertEqual(NS['module_arrange'](S(children=[])), 'mixed')

    def test_module_layout_uses_it(self):
        self.assertIn('arrange=module_arrange(m)', SRC_GP)


class _FakeMenuPar(object):
    def __init__(self, names, labels, val):
        self.menuNames, self.menuLabels, self.val = list(names), list(labels), val

    def eval(self):
        return self.val


class _FakePars(object):
    pass


class _FakePage(object):
    name = 'Pattern'


class MenuRefresh(unittest.TestCase):
    """T-190: an idempotent rebuild (existing pars skipped) must still extend a menu that grew."""

    def _comp(self, par):
        c = _FakePars()
        c.par = _FakePars()
        c.par.Shape = par
        c.customPages = [_FakePage()]
        return c

    def test_grown_menu_reaches_old_instance(self):
        p = _FakeMenuPar(['a', 'b'], ['A', 'B'], 'b')
        spec = ('Shape', 'Menu', 0, {'names': ['a', 'b', 'clip'], 'labels': ['A', 'B', 'Clip']})
        NS['_pars'](self._comp(p), [('Pattern', [spec])])
        self.assertEqual(p.menuNames, ['a', 'b', 'clip'])
        self.assertEqual(p.menuLabels, ['A', 'B', 'Clip'])
        self.assertEqual(p.val, 'b')                       # value kept

    def test_same_menu_untouched_and_relabel(self):
        p = _FakeMenuPar(['a', 'b'], ['A', 'B'], 'a')
        self.assertFalse(NS['_refresh_menu'](p, {'names': ['a', 'b'], 'labels': ['A', 'B']}))
        self.assertTrue(NS['_refresh_menu'](p, {'names': ['a', 'b'], 'labels': ['Alpha', 'B']}))
        self.assertEqual(p.menuLabels, ['Alpha', 'B'])
        self.assertFalse(NS['_refresh_menu'](None, {'names': [], 'labels': []}))


with open(os.path.join(B, 'gen_pattern.py')) as _fh:
    SRC_GP = _fh.read()


class _Cell(object):
    def __init__(self, v):
        self.val = v


class _Table(object):
    def __init__(self, rows):
        self.rows = rows                                  # {name: {col: val}}

    def __getitem__(self, k):
        r = self.rows.get(k[0])
        return None if r is None or k[1] not in r else _Cell(r[k[1]])


class _Rack(object):
    def __init__(self, rows):
        self.t = None if rows is None else _Table(rows)

    def op(self, n):
        return self.t if n == 'slots' else None


def _gate_index(rows, name='m1'):
    """Evaluate SLOT_GATE_E the way TD does, with parent() = the module, parent(2) = the rack."""
    from types import SimpleNamespace as S
    mod, rack = S(name=name), _Rack(rows)
    return eval(NS['SLOT_GATE_E'], {'parent': lambda n=1: mod if n == 1 else rack, 'getattr': getattr,
                                     'float': float, 'int': int})


class _Conn(object):
    def __init__(self, owner, inp=False):
        self.owner, self.inp, self.connections = owner, inp, []

    def connect(self, src):
        src = src if isinstance(src, _Conn) else src.outputConnectors[0]
        self.connections = [src]


class _Par(object):
    def __init__(self):
        self.expr, self.mode = '', None


class _Op(object):
    def __init__(self, name, typ, parent_=None):
        from types import SimpleNamespace as S
        self.name, self.OPType, self.valid, self.isCOMP, self.viewer, self.comment = name, typ, True, False, False, ''
        self.inputConnectors = [_Conn(self, True) for _ in range(3)]
        self.outputConnectors = [_Conn(self)]
        self.par = S(index=_Par())
        self.parent_ = parent_


class _Mod(object):
    def __init__(self, src_name='fx', src_expr=''):
        self.kids = {}
        for n, t in (('in1', 'inTOP'), ('out1', 'outTOP'), (src_name, 'switchTOP')):
            self.kids[n] = _Op(n, t, self)
        self.kids[src_name].par.index.expr = src_expr
        self.kids[src_name].inputConnectors[0].connect(self.kids['in1'])
        self.kids['out1'].inputConnectors[0].connect(self.kids[src_name])

    def op(self, n):
        return self.kids.get(n)

    def create(self, cls, n):
        self.kids[n] = _Op(n, cls.__name__, self)
        return self.kids[n]


class switchTOP(object):  # noqa: N801  (TD's class name, only __name__ is read)
    pass


class ParMode(object):
    EXPRESSION = 'expr'


def _src_of(o, i=0):
    c = o.inputConnectors[i].connections
    return c[0].owner.name if c else None


class SlotGate(unittest.TestCase):
    """T-198 for every rack: a slot that is off (enabled 0 / mix <= 0) passes in1 inside the module, so a visible
    <name>_mix viewer no longer pulls the module; on = the module's own output, unchanged."""

    def test_slot_off_matches_slot_switch(self):
        so = NS['slot_off']
        for en, mx, off in (('1', '1', False), ('1', '0.5', False), ('0', '1', True), ('1', '0', True),
                            ('', '1', True), ('1', '', True), ('1', '-1', True), ('1.0', '1', False),
                            (None, None, False)):
            self.assertEqual(so(en, mx), off, (en, mx))
            sw = 0 if not int(float(en or 0)) or float(mx or 0) <= 0 else 1   # the rack's <name>_slot index test
            if en is not None:
                self.assertEqual(off, sw == 0)

    def test_gate_expression(self):
        self.assertEqual(_gate_index({'m1': {'enabled': '1', 'mix': '1'}}), 1)
        self.assertEqual(_gate_index({'m1': {'enabled': '1', 'mix': '0.3'}}), 1)
        self.assertEqual(_gate_index({'m1': {'enabled': '0', 'mix': '1'}}), 0)
        self.assertEqual(_gate_index({'m1': {'enabled': '1', 'mix': '0'}}), 0)
        self.assertEqual(_gate_index({}), 1)                       # no row = on
        self.assertEqual(_gate_index(None), 1)                     # no slots table = on

    def test_gate_needed(self):
        self.assertTrue(NS['gate_needed']('out_sel', '0 if parent().par.Amount.eval() <= 0 else 1'))
        self.assertTrue(NS['gate_needed']('fx', ''))
        self.assertFalse(NS['gate_needed']('out_sel', "0 if parent(2).op('slots') is not None else 1"))

    def test_stages(self):
        st = NS['gate_stages']([{'ops': ['in1']}, {'ops': ['out_sel', 'out1']}])
        self.assertEqual(st[1]['ops'], ['out_sel', 'slot_gate', 'out1'])
        self.assertEqual(NS['gate_stages'](st)[1]['ops'], ['out_sel', 'slot_gate', 'out1'])   # idempotent
        self.assertEqual(NS['gate_stages']([{'ops': ['fx']}])[0]['ops'], ['fx', 'slot_gate'])

    def _ns(self):
        ns = {'switchTOP': switchTOP, 'ParMode': ParMode}
        exec(RACK_SRC, ns)                                        # rack functions bound to the fake TD globals
        ns['_sd'] = lambda o: None
        return ns

    def test_wiring_idempotent(self):
        ns = self._ns()
        m = _Mod()
        st = ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])
        g = m.op('slot_gate')
        self.assertEqual((_src_of(g, 0), _src_of(g, 1), _src_of(m.op('out1'))), ('in1', 'fx', 'slot_gate'))
        self.assertEqual(g.par.index.expr, NS['SLOT_GATE_E'])
        self.assertEqual(st[0]['ops'], ['fx', 'slot_gate', 'out1'])
        m.op('out1').inputConnectors[0].connect(m.op('fx'))      # a module rebuild re-wires out1 to its source
        ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])
        self.assertEqual((_src_of(g, 0), _src_of(g, 1), _src_of(m.op('out1'))), ('in1', 'fx', 'slot_gate'))
        ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])           # already gated: unchanged
        self.assertEqual(_src_of(m.op('out1')), 'slot_gate')

    def test_slot_aware_out_sel_left_alone(self):              # GEN_points OUT_SEL_E
        ns = self._ns()
        m = _Mod('out_sel', "0 if parent().par.Amount.eval() <= 0 or (parent(2).op('slots') is not None) else 1")
        ns['_slot_gate'](m, [{'ops': ['out_sel', 'out1']}])
        self.assertIsNone(m.op('slot_gate'))
        self.assertEqual(_src_of(m.op('out1')), 'out_sel')


def _family_src(name):
    with open(os.path.join(BDIR, name + '.py')) as fh:
        return fh.read()


def _instance_body(src):
    i = src.find('\ndef _instance(')
    if i < 0:
        return None
    j = src.find('\ndef ', i + 1)
    return src[i:j if j > 0 else len(src)]


class Families(unittest.TestCase):
    """GEN_sdf (own _instance) calls the gate; GEN_points keeps its slot-aware out_sel (OUT_SEL_E: no gate)."""

    def test_gen_sdf_gates(self):
        src = _family_src('gen_sdf')
        self.assertIn('gen_pattern.py', src)
        self.assertIn('_slot_gate(m, _module_network(m, M))', _instance_body(src))

    def test_gen_points_out_sel_is_slot_aware(self):
        P = {}
        exec(_family_src('gen_points'), P)
        self.assertFalse(P['gate_needed']('out_sel', P['OUT_SEL_E']))
        self.assertIn('_rack_instance(', _instance_body(_family_src('gen_points')))

    def test_rack_instance_gates(self):
        self.assertIn('stages = _slot_gate(m, _module_network(m, M))', _instance_body(RACK_SRC))


BDIR = B
with open(os.path.join(B, 'gen_pattern.py')) as _fh:
    RACK_SRC = _fh.read()

if __name__ == '__main__':
    unittest.main()
