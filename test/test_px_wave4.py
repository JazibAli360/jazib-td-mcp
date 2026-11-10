"""Offline tests for PX_pointfx wave 4 (27 Oct 2026; docs/builds/px.md "Wave 4"): K36 proximity from big point sets
through the shared grid, and the other wave-4 items. No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_px_wave4.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
GLSL = os.path.join(BUILDERS, 'glsl')
sys.path.insert(0, BUILDERS)
sys.path.insert(0, HERE)
import px_logic as L  # noqa: E402
import test_px_wave2 as W  # noqa: E402
from test_px_wave2 import LIB, TU, TC, MODS, PAL, rd  # noqa: E402

GRID = L.grid_section(rd('eff_consumer.glsl'))
ROWS = [{'name': 'sphere1', 'kind': 'sphere', 'tags': 'demo', 'enabled': '1'},
        {'name': 'body', 'kind': 'cloud', 'tags': 'people', 'enabled': '1'},
        {'name': 'px_hot', 'kind': 'cloud', 'tags': 'pxhot', 'enabled': '1'}]


def _items(sel, t='prox_push'):
    return [{'type': t, 'uid': 1, 'enabled': True, 'values': {'effectors': sel}}]


class K36Cloud(unittest.TestCase):
    def test_selection_reaches_cloud(self):
        own = ['eff1']
        self.assertTrue(L.stack_cloud(_items('body'), own, ROWS))
        self.assertTrue(L.stack_cloud(_items('#people'), own, ROWS))
        self.assertTrue(L.stack_cloud(_items('all'), own, ROWS))
        self.assertFalse(L.stack_cloud(_items('eff1'), own, ROWS))          # own effector only
        self.assertFalse(L.stack_cloud(_items('sphere1'), own, ROWS))       # not a cloud
        self.assertFalse(L.stack_cloud(_items('px_hot'), own, ROWS))        # PX's own hot row never counts
        self.assertFalse(L.stack_cloud(_items('body', 'colour_adjust'), own, ROWS))   # no effectors
        off = [dict(r, enabled='0') if r['name'] == 'body' else r for r in ROWS]
        self.assertFalse(L.stack_cloud(_items('body'), own, off))

    def test_codegen_grid_for_cloud(self):
        st, _ = L.add_module([], 'prox_push')
        a = L.codegen(st, LIB, TU, TC, MODS, PAL, grid_text=GRID)
        b = L.codegen(st, LIB, TU, TC, MODS, PAL, grid_text=GRID, cloud=True)
        self.assertFalse(a['grid'])
        self.assertNotIn('#define PXE_GRID', a['update'])
        self.assertTrue(b['grid'])
        self.assertFalse(b['hot'])                     # no heat_spread: no hot row
        self.assertIn('#define PXE_GRID', b['update'])
        self.assertNotEqual(a['hash'], b['hash'])
        m, _ = L.add_module(st, 'mask_image')
        self.assertFalse(L.codegen(m, LIB, TU, TC, MODS, PAL, grid_text=GRID, cloud=True)['grid'])   # input 2 taken


class K36Compile(unittest.TestCase):
    _ok = W.Compile._ok

    def test_prox_modules_with_grid(self):
        st = []
        for t in ('prox_push', 'prox_colour', 'prox_burn', 'prox_stretch', 'dissolve_prox'):
            if t in L.MODULES:
                st, _ = L.add_module(st, t)
        cg = L.codegen(st, LIB, TU, TC, MODS, PAL, grid_text=GRID, cloud=True)
        self._ok(cg['update'], 'update cloud grid')
        self._ok(cg['colour'], 'colour cloud grid')


import px_lines_logic as PL  # noqa: E402
import test_px_lines as TL  # noqa: E402
try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None


def _cloud(n, seed=3):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, 3))
    v = v / np.linalg.norm(v, axis=1, keepdims=True) * (1.0 + 0.05 * rng.normal(size=(n, 1)))
    side = int(np.ceil(np.sqrt(n)))
    tex = np.zeros((side, side, 4))
    tex.reshape(-1, 4)[:n, :3] = v
    tex.reshape(-1, 4)[:n, 3] = 1.0
    return v, tex


@unittest.skipIf(np is None, 'numpy')
class SA33Index(unittest.TestCase):
    def test_index_one_rep_per_voxel(self):
        v, tex = _cloud(20000)
        p = TL.P(Connect=True, Cnindex='grid', Cngrid=16, Cngridsize=2.6, Ptcount=20000)
        lay = PL.index_layout(p)
        self.assertEqual((lay['N'], lay['TX'], lay['atlas']), (16, 4, (64, 64)))
        for pick in ('random', 'centre'):
            A = PL.ref_index(tex, 1, 20000, lay, pick)
            vox = np.floor((v - np.array(lay['origin'])) / lay['cell']).astype(int)
            occ = set(map(tuple, vox))
            got = {}
            N, tx = lay['N'], lay['TX']
            for z in range(N):
                for y in range(N):
                    for x in range(N):
                        e = A[y + (z // tx) * N, x + (z % tx) * N]
                        if e[3] > 0.5:
                            got[(x, y, z)] = int(e[3] + 0.5) - 1
            self.assertEqual(set(got), occ)                          # every occupied voxel, no other
            for k, i in list(got.items())[:200]:
                self.assertEqual(tuple(vox[i]), k)                   # the rep lies in its voxel
            if pick == 'random':
                ids = np.arange(20000)
                pr = PL.pcg(ids) >> 22
                for k, i in list(got.items())[:200]:
                    inv = ids[np.all(vox == k, axis=1)]
                    best = min(inv, key=lambda j: (int(pr[j]) << 22) | int(j))
                    self.assertEqual(i, best)

    def test_grid_connect_links_nearest_reps(self):
        v, tex = _cloud(20000)
        p = TL.P(Rings=False, Connect=True, Cnindex='grid', Cngrid=16, Cngridsize=2.6, Ptcount=20000, Cnpoints=2000,
                 Cnk=3, Cnradius=0.3, Cnsub=1, Maxseg=65536)
        r = PL.rows(p)
        self.assertEqual(r[PL.R['CN0']][0], 2000)                    # no 4096 clamp in grid mode
        lay = PL.index_layout(p)
        A = PL.ref_index(tex, 1, 20000, lay)
        S = PL.ref_segments(r, [0.5, 30, 0, 0], points=tex, index=A, index_points=tex)
        reps = [(int(e[3] + 0.5) - 1) for e in A.reshape(-1, 4) if e[3] > 0.5]
        valid = S[:6000, 3, 3] == 4
        self.assertGreater(valid.sum(), 3000)
        for pi in (0, 7, 999, 1999):
            i = int(np.floor(pi * 20000 / 2000))
            vi = np.floor((v[i] - np.array(lay['origin'])) / lay['cell']).astype(int)
            near = [q for q in reps if q != i and np.all(np.abs(np.floor((v[q] - np.array(lay['origin'])) / lay['cell'])
                                                                 .astype(int) - vi) <= 1)]
            d = sorted((np.linalg.norm(v[q] - v[i]), q) for q in near)
            want = [q for dd, q in d[:3] if dd < 0.3]
            ends = [set(map(tuple, np.round(S[pi * 3 + m, :2, :3], 9))) for m in range(3) if S[pi * 3 + m, 3, 3] == 4]
            self.assertEqual(len(ends), len(want))
            for m, q in enumerate(want):
                self.assertEqual(ends[m], {tuple(np.round(v[i], 9)), tuple(np.round(v[q], 9))})

    def test_brute_clamped(self):
        p = TL.P(Rings=False, Connect=True, Cnpoints=60000)
        self.assertEqual(PL.rows(p)[PL.R['CN0']][0], 4096)
        self.assertEqual(PL.plan(p)['connect_points'], 4096)


class LinesFollow(unittest.TestCase):
    def test_rows_follow_equals_rows(self):
        for kw in ({}, {'Ringface': 'camera', 'Trvcam': True, 'Ctaxis': 'view', 'Maskmode': 'front'}):
            p = TL.P(**kw)
            ctx = {'centres': [([1, 2, 3], [0, 1, 0], 1.0), ([0, 0, 1], [1, 0, 0], 2.0)],
                   'mask_world': [[1, 0, 0, 0.5], [0, 1, 0, 0.2], [0, 0, 1, 0.1]],
                   'poly_world': [[2, 0, 0, 1], [0, 1, 0, 0], [0, 0, 1, 0]]}
            r, f = PL.rows(p, ctx), PL.rows_follow(p, ctx)
            self.assertEqual(sorted(f), sorted(PL.FOLLOW_ROWS))
            for k, v in f.items():
                self.assertEqual(r[PL.R[k]], v, k)
        src = open(os.path.join(BUILDERS, 'px_lines.py')).read()
        self.assertIn("rows.inputConnectors[0].connect(rst)", src)
        self.assertIn('Lg.rows_follow(vv', src)


class K26Proj(unittest.TestCase):
    def test_proj_res_and_page(self):
        self.assertEqual(L.proj_res({'Resx': 1080, 'Resy': 1920}), (1080.0, 1920.0))
        self.assertEqual(L.proj_res({'Proj': 'equirect', 'Projface': 768, 'Resx': 2048, 'Resy': 1024}), (768.0, 768.0))
        self.assertIn('Output', L.NEW_PAGES)                                   # looks reset it to perspective
        r = L.render_rows({'Proj': 'fisheye', 'Projface': 512}, 10, 100, *L.proj_res({'Proj': 'fisheye', 'Projface': 512}))
        self.assertEqual(r[4][:2], [512.0, 512.0])
        src = open(os.path.join(BUILDERS, 'px.py')).read()
        self.assertIn("'cubemap' if %s else 'render2d'", src)
        self.assertIn("_proj(c)", src)


class GE3Env(unittest.TestCase):
    def test_env_pars_and_builder(self):
        d = dict((n, dv) for pg, ps in L.CORE_PAGES for n, _s, dv, _o in ps)
        self.assertFalse(d['Geoenv'])                                          # off by default
        self.assertEqual(d['Geoenvres'], 128)
        src = open(os.path.join(BUILDERS, 'px.py')).read()
        self.assertIn("'pgeo_prev' if", src)                                   # the decimated preview, not every splat
        self.assertIn("env_capture'](c, 'geo_env'", src)
        self.assertIn('Geoenv', L.BUILTIN['Lit splats + geometry']['core'])


class SA33Compile(unittest.TestCase):
    def test_index_and_seg_with_five_inputs(self):
        stub = TL.STUB_COMPUTE.replace('uniform sampler2D sTD2DInputs[3];',
                                       '#define TD_NUM_2D_INPUTS 5\nuniform sampler2D sTD2DInputs[5];')
        ok, err = TL.glslc(stub + TL.text('seg'), 'comp')
        self.assertTrue(ok, err)
        idx = PL.glsl_header() + rd('px_lines_index.glsl')
        ok, err = TL.glslc(TL.STUB_COMPUTE + idx, 'comp')
        self.assertTrue(ok, err)


class EchoCost(unittest.TestCase):
    def test_render_row8(self):
        raw = {'Echoes': 6, 'Actormode': 'gen', 'Actorcount': 100}
        r = L.render_rows(raw, 10, 1000, echo=(400, 100))
        self.assertEqual(len(r), L.R_ROWS)
        self.assertEqual(r[8], [400.0, 100.0, 0.8, 0.25])
        self.assertEqual(L.render_rows({}, 10, 1000)[8][0], -1.0)             # no echoes: the vertex branch is off
        v = rd('px_vert.glsl')
        self.assertIn('uniform vec4 uR[%d];' % L.R_ROWS, v)          # phase C: + row 9 (LOD)
        self.assertIn('if (ok && uR[8].x >= 0.0', v)
        self.assertIn('uniform vec4 uR[%d];' % L.R_ROWS, rd('px_pixel.glsl'))
        fill = sum((0.75 * 0.8 ** 2) ** k for k in range(1, 7))
        self.assertLess(fill, 1.0)                                              # 6 echoes < one copy of fill


class StrandsImageSound(unittest.TestCase):
    _ok = W.Compile._ok

    def test_strands_ref(self):
        st, v = L.ref_strands([0, 1, 2], 6.0, 0.5, (0.0, 2.0, 0.0))
        self.assertEqual(list(v), [0.0, 1.0, 0.0])
        self.assertTrue(all(3.0 <= x <= 6.0 for x in st))
        self.assertIn('//@module strands colour', MODS)

    def test_image_mode_rows(self):
        self.assertEqual(L.menu_index(L.SOURCEMODES, 'image'), 5)
        self.assertIn('image', [a for a, _b in L.AMODES])
        r = L.source_rows({'Amode': 'image', 'Imagerelief': 0.7, 'Imagesrc': 'hue', 'Imagecut': 0.1}, 64, 4096)
        self.assertEqual(len(r), L.SRC_ROWS)
        self.assertEqual(r[0][0], 5.0)
        self.assertEqual(r[17], [0.7, 1.0, 0.1, 0.0])
        self.assertIn('uniform vec4 uSrc[18];', rd('px_source.glsl'))
        self._ok(L.source_text(LIB, rd('px_source.glsl')), 'source (image mode)')

    def test_sound(self):
        P = np.array([[0.0, 1.0, 0.0], [0.0, 3.0, 0.0]]) if np is not None else None
        if np is None:
            return
        V = np.array([[3.0, 4.0, 0.0], [0.0, 0.0, 1.0]])
        sp, dis, h = L.ref_sound(P, V, [0.0, 1.0], 2, 2, 1.0, 2.0)
        self.assertEqual((sp, dis, h), (3.0, 0.5, 0.5))
        f = L.sound_freqs(1.0, 0.25, 0.0, full=2.0)
        self.assertEqual(f['drone'], (110.0, 0.375))
        self.assertEqual(f['shimmer'], (220.0 * 2.5, 0.075))
        self._ok(rd('px_sound.glsl'), 'px_sound')
        names = [n for pg, ps in L.CORE_PAGES if pg == 'Sound' for n, *_r in ps]
        self.assertIn('Soundon', names)
        self.assertFalse(dict((n, d) for pg, ps in L.CORE_PAGES for n, _s, d, _o in ps)['Soundon'])   # off by default
        self.assertIn('Sound', L.NEW_PAGES)                                    # looks reset it to off
        src = open(os.path.join(BUILDERS, 'px.py')).read()
        self.assertIn("dev.par.cookalways = False", src)
        self.assertNotIn('audiodeviceinCHOP', src)                             # never an input device


class K33DriveChop(unittest.TestCase):
    def test_names_and_drive(self):
        self.assertEqual(L.drive_name('/1/fader1'), '1_fader1')
        self.assertEqual(L.drive_name('ch1'), 'ch1')
        d, bad = L.parse_drives('strength:1_fader1*2 radius:note60*-0.5+0.1')
        self.assertEqual(bad, [])
        self.assertEqual(d[0], ('strength', None, '1_fader1', 2.0, 0.0))
        v = L.apply_drives({'strength': 0.2}, 'prox_push', d[:1], {'1_fader1': 0.25})
        self.assertAlmostEqual(v['strength'], 0.7)


if __name__ == '__main__':
    unittest.main()
