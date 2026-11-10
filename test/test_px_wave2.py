"""Offline tests for PX_pointfx wave 2 (27 Oct 2026; docs/builds/px.md "Wave 2"): shared effectors (K37), light module
(L1 / L2), shared palette + colour sources (CO2-CO5), haze / bloom v2 / geo / lines wiring. No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_px_wave2.py'"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
GLSL = os.path.join(BUILDERS, 'glsl')
sys.path.insert(0, BUILDERS)
sys.path.insert(0, HERE)
import px_logic as L  # noqa: E402
import palette_map_logic as PM  # noqa: E402
import effectors_logic as EL  # noqa: E402
import px_haze_logic as HZ  # noqa: E402

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None


def rd(n):
    with open(os.path.join(GLSL, n)) as fh:
        return fh.read()


LIB, TU, TC, MODS, PAL = rd('px_common.glsl'), rd('px_update.glsl'), rd('px_colour.glsl'), rd('px_modules.glsl'), \
    rd('px_palette.glsl')


class Menus(unittest.TestCase):
    def test_palette_menus_match_w1b(self):
        self.assertEqual(L.COLSRC_MODES, PM.COLSRC_MODES)
        self.assertEqual(L.PAL_MODES, PM.PAL_MODES)
        self.assertEqual(L.PAL_INTERP, PM.PAL_INTERP)
        self.assertEqual(L.PAL_DRIVES, PM.PAL_DRIVES)
        self.assertEqual(L.names(L.PAL_SOURCES), [m[0] for m in PM.PAL_SOURCES if m[0] != 'image'])

    def test_light_menus_match_w1a(self):
        self.assertEqual(L.names(L.LIGHT_MODELS), ['halflambert', 'lambert', 'wrap', 'glow'])
        self.assertEqual(L.names(L.LTYPES), [m[0] for m in EL.LTYPES])

    def test_new_pages_and_par_names(self):
        names = [p[0] for pg, pars in L.CORE_PAGES for p in pars]
        self.assertEqual(len(names), len(set(names)))                         # no clash across pages
        for pg in L.NEW_PAGES:
            self.assertIn(pg, L.CORE_PAGE_NAMES)
            self.assertIn(pg, L.PANEL_CORE_PAGES)
        for n in names:                                                        # TD custom par rule
            self.assertTrue(n[0].isupper() and (n[1:] == '' or n[1:].islower() or n[1:].isalnum()), n)
        for pre in ('Edge', 'Haze', 'Flare', 'Glow', 'Bloom', 'Vh'):
            self.assertIn(pre + 'colsrc', names)
        self.assertIn('Geoon', names)                                          # = splat_render.geo_pars names
        self.assertIn('Lineson', names)

    def test_haze_params_cover_w1d(self):
        p = L.haze_params({})
        self.assertEqual(set(p), set(HZ.HAZE_DEFAULTS))
        rows = HZ.haze_rows(p, HZ.camera_from_px([0, 0, 4, 0], 45, 1080, 1920), 2)
        self.assertEqual(len(rows), HZ.HZ_ROWS)


class SharedEffectors(unittest.TestCase):
    def test_split_and_selection(self):
        own, rest = L.split_effectors('E1 box1, #demo all E9', ['E1', 'E2'])
        self.assertEqual(own, ['E1'])
        self.assertEqual(rest, ['box1', '#demo', 'all', 'E9'])
        own, rest = L.split_effectors('E1 all', ['E1'], shared_only=True)     # light: everything to the list
        self.assertEqual(own, [])
        rows = EL.parse_table([EL.COLS] + [['sphere1', 'sphere', 'demo', '1'], ['box1', 'box', 'demo', '1']])
        f = lambda t: EL.sel_vec(t, rows)[0]
        self.assertEqual(L.shared_sel(['box1'], f), ([0.0, 0.0, 1.0], [2.0, 0.0, 0.0, 0.0]))
        self.assertEqual(L.shared_sel(['#demo'], f)[0], [1.0, 0.0, 1.0])
        self.assertEqual(L.shared_sel(['all'], f)[0], [0.0, 1.0, 1.0])
        self.assertEqual(L.shared_sel(['E9'], f), ([0.0, 0.0, 0.0], [0.0] * 4))  # unknown: off (old path)
        self.assertEqual(L.shared_sel(['box1'], None), ([0.0, 0.0, 0.0], [0.0] * 4))

    def test_header_rows(self):
        st, u = L.add_module([], 'prox_push')
        st, w = L.add_module(st, 'light')
        lay, n = L.layout(st)
        self.assertEqual([il['hdr'] for il in lay], [3, 3])
        rows_ = EL.parse_table([EL.COLS] + [['box1', 'box', '', '1']])
        f = lambda t: EL.sel_vec(t, rows_)[0]
        vals = {u: dict(L.instance_defaults(st[0]), effectors='E1 box1'), w: L.instance_defaults(st[1])}
        R = L.pack_module_rows(lay, n, vals, ['E1'], shared=f)
        self.assertEqual(R[0][1], 1.0)                                         # own E1 bit
        self.assertEqual(R[1][1:], [0.0, 0.0, 1.0])                            # shared on
        self.assertEqual(R[2], [1.0, 0.0, 0.0, 0.0])                           # box1 = row 0 -> id 1
        b = lay[1]['base']
        self.assertEqual(R[b][1], 0.0)                                         # light: no own bits
        self.assertEqual(R[b + 1][1:], [0.0, 1.0, 1.0])                        # default 'all'
        # without the list: identical to v2 rows (on 0)
        R0 = L.pack_module_rows(lay, n, vals, ['E1'])
        self.assertEqual(R0[1], [0.0, 0.0, 0.0, 0.0])

    def test_old_layout_in_flight(self):
        st, u = L.add_module([], 'prox_push')
        lay, n = L.layout(st)
        old = [dict(il, hdr=2) for il in lay]
        R = L.pack_module_rows(old, n, {u: dict(L.instance_defaults(st[0]), effectors='E1')}, ['E1'])
        self.assertEqual(R[0][1], 1.0)
        self.assertEqual(R[1], [0.0, 0.0, 0.0, 0.0])

    def test_block_sets_selection_globals(self):
        st, _ = L.add_module([], 'prox_push')
        cg = L.codegen(st, LIB, TU, TC, MODS, PAL)
        self.assertIn('pxShSel = vec4(uM[1].yzw, 1.0);', cg['update'])
        self.assertIn('pxShIds = uM[2];', cg['update'])
        self.assertIn('#define PX_SHARED_EFF 1', cg['update'])
        self.assertNotIn('#define PX_SHARED_EFF', L.source_text(LIB, rd('px_source.glsl')))

    def test_own_functions_untouched(self):
        """W2-0 (live b5): PX's own-effector accessors keep the v2 text; dispatch only in pxX* / pxW / pxFirst /
        pxDirOf (branching inside them changed the driver codegen)."""
        for f in ('vec3 pxECentre(int i) { return uE[i * PX_EP + 4].xyz; }',
                  'int pxEType(int i) { return pxI(uE[i * PX_EP + 3].x); }',
                  '\treturn pxSdShape(ty, pxELocal(i, p), t.yzw) * uE[i * PX_EP + 4].w;'):
            self.assertIn(f, LIB)
        for m in ('pxECentre(bi)', 'pxEAxis(bi)', 'pxESd(bi', 'pxEGrad(bi', 'pxESample(e'):
            self.assertNotIn(m, MODS)


@unittest.skipIf(np is None, 'numpy')
class LightModule(unittest.TestCase):
    def _blocks(self):
        rows = EL.parse_table([EL.COLS] + [['l1', 'light', 'light', '1'], ['l2', 'light', 'light', '1']])
        w1 = [[1, 0, 0, 0.3], [0, 1, 0, 1.0], [0, 0, 1, 0.2]]
        w2 = [[1, 0, 0, -0.5], [0, 0, 1, 1.5], [0, -1, 0, 0.1]]          # pointing down (-z local -> -y world)
        effs = [EL.effector(rows[0], w1, light=EL.light_values({'type': 'point', 'colour': (1, 0.5, 0.2),
                                                                 'intensity': 2.0, 'att_on': True, 'att_end': 4.0})),
                EL.effector(rows[1], w2, light=EL.light_values({'type': 'spot', 'colour': (0.2, 0.6, 1.0),
                                                                 'intensity': 3.0, 'cone_angle': 50.0}))]
        tex = EL.pack_buffer(effs)
        return tex, [EL.read_light(tex, k) for k in range(EL.light_count(tex))]

    def test_matches_w1a_lights(self):
        tex, blocks = self._blocks()
        P, cam = [0.1, 0.0, 0.05], [0.0, 0.5, 3.0]
        v = np.asarray(cam) - P
        v = v / np.linalg.norm(v)
        n = [0.0, 1.0, 0.0]
        sel = EL.sel_vec('all', EL.parse_table([EL.COLS] + [['l1', 'light', 'light', '1'], ['l2', 'light', 'light', '1']]))[0]
        Ls = np.asarray(EL.ref_lights(tex, np.asarray([P]), np.asarray([n]), np.asarray([v]), sel,
                                      (0, 0.5, 0.0, 0.5))).reshape(-1)
        col = [0.4, 0.5, 0.6]
        vals = dict(L.instance_defaults(L.new_instance('light', 1)))
        out = L.ref_light_module(col, P, n, cam, blocks, vals)
        want = [c + (c * (0.15 + l) - c) * 1.0 for c, l in zip(col, Ls)]
        self.assertTrue(np.allclose(out, want, atol=1e-9), (out, want))

    def test_relight_zero_is_baked(self):
        _t, blocks = self._blocks()
        vals = dict(L.instance_defaults(L.new_instance('light', 1)), relight=0.0)
        self.assertEqual(L.ref_light_module([0.3, 0.2, 0.1], [0, 0, 0], None, [0, 0, 3], blocks, vals), [0.3, 0.2, 0.1])

    def test_palette_index_colours(self):
        _t, blocks = self._blocks()
        st = PM.palette_stops({'source': 'neon_trio', 'mode': 'steps'})
        rows, ctl = PM.pal_rows(st), PM.pal_ctl(st, 'steps', 'rgb', 0.0)
        vals = dict(L.instance_defaults(L.new_instance('light', 1)), colsrc='index', ambient=0.0, relight=0.0, add=1.0)
        out = L.ref_light_module([0, 0, 0], [0.3, 0.0, 0.2], None, [0, 0, 3], blocks[:1], vals,
                                 (PM.colsrc_eval, rows, ctl))
        self.assertAlmostEqual(out[0] / max(out[1], 1e-9), st[0][0] / st[0][1], 6)   # light 0 = stop 0 (green)


class Palette(unittest.TestCase):
    def test_spec_and_drive(self):
        spec, rows = L.palette_spec({'Palsource': 'custom', 'Palstops': '#ff0000 0, #00ff00 1', 'Palmode': 'steps'})
        self.assertEqual(spec['mode'], 'steps')
        self.assertEqual(rows, [['#ff0000', '0'], ['#00ff00', '1']])
        st = PM.palette_stops(spec, rows)
        self.assertEqual(len(st), 2)
        d = L.pal_drive({'Paldrive': 'bpm_step', 'Palevery': 2.0})
        self.assertEqual(PM.pal_shift(d, 4, 0.0, beats=4.5), 0.5)

    def test_scalar_colours_solid_is_identity(self):
        raw = {'Edgecolr': 0.3, 'Edgecolg': 0.2, 'Edgecolb': 0.1}
        cols = L.scalar_colours(raw, PM.colsrc_eval, PM.pal_rows([]), [0, 0, 0, 0])
        self.assertEqual(cols['Edgecol'], (0.3, 0.2, 0.1))
        self.assertEqual(cols['Flaretint'], (1.0, 0.75, 0.55))
        self.assertIsNone(L.glow_recolour({}, PM.colsrc_eval, None, None))
        g = [[0.0] * 4 for _ in range(24)]
        q = L.post_rows({})
        L.apply_scalar_colours(g, q, cols)
        self.assertEqual(g[10][:3], [0.3, 0.2, 0.1])

    def test_scalar_colours_palette(self):
        st = PM.palette_stops({'source': 'neon_trio'})
        rows, ctl = PM.pal_rows(st), PM.pal_ctl(st)
        cols = L.scalar_colours({'Edgecolsrc': 'palette', 'Edgepalpos': 0.5}, PM.colsrc_eval, rows, ctl)
        self.assertEqual(cols['Edgecol'], tuple(PM.pal_eval(rows, ctl, 0.5)))
        rc = L.glow_recolour({'Glowcolsrc': 'index'}, PM.colsrc_eval, rows, ctl)
        self.assertEqual(rc(1, (1, 1, 1)), tuple(PM.pal_step(rows, ctl, 1)))
        g, n = L.glow_rows([{'kind': 'sphere', 'world': [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]],
                             'settings': {'Glow': True, 'Glowintensity': 1.0}}], rc)
        self.assertEqual(n, 1)
        self.assertEqual(g[3][:3], list(PM.pal_step(rows, ctl, 0)))

    def test_look_defaults_reset_new_pages(self):
        d = L.look_defaults()
        for k in ('Palsource', 'Vhon', 'Geoon', 'Lineson', 'Bloomtight', 'Edgecolsrc'):
            self.assertIn(k, d)
        self.assertNotIn('Addlight', d)


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, what):
        import test_px as T
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.comp')
            with open(p, 'w') as fh:
                fh.write(T.STUB_COMPUTE + text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:2000]))

    def test_light_and_palette_modules(self):
        st = []
        for t, v in (('light', {}), ('colour_ramp', {}), ('prox_colour', {}), ('prox_burn', {})):
            st, _ = L.add_module(st, t)
        cg = L.codegen(st, LIB, TU, TC, MODS, PAL)
        self._ok(cg['colour'], 'colour')
        self._ok(cg['update'], 'update')

    def test_post_bloom_haze(self):
        self._ok(rd('px_post.glsl'), 'post (3 inputs, uQh)')
        self._ok(PAL + rd('px_bloom.glsl'), 'bloom v2')
        self._ok(PAL + rd('px_haze.glsl'), 'haze')

    def test_wave2_presets_compile(self):
        for name in L.BUILTIN:
            cg = L.codegen(L.builtin_preset(name)['stack'], LIB, TU, TC, MODS, PAL)
            self._ok(cg['colour'], 'colour ' + name)
            self._ok(cg['update'], 'update ' + name)


class Looks(unittest.TestCase):
    W2 = ('Green line sweep', 'Neon rings', 'Haze shafts', 'Light sweep', 'Lit splats + geometry', 'Palette beat cycle',
          'Acid palette', 'Fire clouds')

    def test_eight_wave2_looks(self):
        import px_lines_logic as PLL
        lines_pars = set(n for _pg, pars in PLL.PAGES for n, *_r in pars)
        core = set(L.flat_core_defaults())
        for nm in self.W2:
            self.assertIn(nm, L.BUILTIN)
            s = L.preset_loads(L.preset_dumps(L.builtin_preset(nm)))
            for k in s['values']:
                self.assertTrue(k in core or k.startswith('M'), (nm, k))
            for k in (s.get('lines') or {}):
                self.assertIn(k, lines_pars, (nm, k))
            for l in s.get('lights', []):
                self.assertIn(l[1], L.names(L.LTYPES))
                self.assertTrue(set(l[6]) <= set(EL.LIGHT_DEFAULTS) | {'expr'}, (nm, l[6]))
            for g in s.get('geo', []):
                self.assertIn(g[1], L.names(L.GEO_KINDS))
            self.assertEqual(s['values'].get('Render'), 'splats')       # whole scenes, splat files
        self.assertTrue(L.builtin_preset('Haze shafts')['values']['Vhon'])
        self.assertTrue(L.builtin_preset('Lit splats + geometry')['values']['Geoon'])
        self.assertFalse(L.builtin_preset('KANDA swipe')['values']['Lineson'])      # older looks reset the new pages


@unittest.skipIf(np is None, 'numpy')
class Wave3(unittest.TestCase):
    """Wave 3 (27 Oct): camera rigs, camera blur, echoes, grid modules, fronts, attributes, sprites, source top."""

    def test_camera_rows_match_cam_rig(self):
        import cam_rig_logic as CR
        for p in (CR.crane((0, 0.5, 0), 30, 25, 4, 10, (0, 0, 0), 50), CR.orbit((0, 0, 0), 3, 1, 70, fov=60),
                  CR.dolly((0, 1, 6), (1, 0.5, 2), 0.3, (0, 0, 0), fov=40)):
            r = L.cam_row(p, CR)
            pos, rt, up, fw = L.cam_basis(r)
            x, y, z = CR.axes(p)
            self.assertTrue(np.allclose(fw, [-v for v in z], atol=1e-9) and np.allclose(rt, x, atol=1e-9))
            self.assertTrue(np.allclose(L.cam_viewproj_row(r, p['fov'], 1080, 1920), CR.viewproj(p, 1080, 1920),
                                        atol=1e-9))
        r = [1.0, 0.2, 3.0, 30.0, 0.0, 0.0]                                       # level: the v2 maths exactly
        self.assertEqual(L.cam_viewproj_row(r, 45, 1080, 1920), L.cam_viewproj(r, 45, 1080, 1920))

    def test_cam_pose_modes_and_director(self):
        import cam_rig_logic as CR
        raw = dict((n, d) for _pg, pars in L.CORE_PAGES for n, st, d, _o in pars if st not in ('Pulse',))
        for k in ('Camtarget', 'Camdollya', 'Camdollyb', 'Camoffset'):
            for a, v in zip('xyz', raw.pop(k)):
                raw[k + a] = v
        for mode in ('crane', 'dolly', 'path', 'follow', 'director'):
            raw['Cammode'] = mode
            p = L.cam_pose(raw, CR, 3.0, 6.0, {}, (0.0, 0.0, 0.0), 1.0 / 60)
            self.assertEqual(len(L.cam_row(p, CR)), 6, mode)
        st = {}
        raw.update(Cammode='director', Camquant=4.0)
        cuts = set()
        for b in range(0, 200):
            L.cam_pose(raw, CR, b * 0.5, float(b), st)
            cuts.add(st['dir_info']['start'])
        self.assertTrue(all(abs(c / 4.0 - round(c / 4.0)) < 1e-9 for c in cuts) and len(cuts) > 3)
        self.assertFalse(L.cam_rig_active({'Cammode': 'orbit'}))

    def test_cam_motion(self):
        a = 0.3
        r0 = [np.sin(a) * 4, 0, np.cos(a) * 4, np.degrees(a), 0, 0]
        r1 = [np.sin(a + 0.01) * 4, 0, np.cos(a + 0.01) * 4, np.degrees(a + 0.01), 0, 0]
        v, w = L.cam_motion(r0, r1, 0.01)
        self.assertAlmostEqual(w[1], 1.0, 3)
        self.assertEqual(L.cam_motion(r0, r1, 0.0), ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))

    def test_fronts(self):
        p0 = np.random.default_rng(1).uniform(-1, 1, (500, 3))
        d = L.ref_dissolve_front(p0, (0, 0, 0), (0, 0, 3), 'camera', 4.0, 0.6, 0.1)
        self.assertTrue(((d >= 0) & (d <= 1)).all())
        near = np.linalg.norm(p0 - [0, 0, 3], axis=1) < 2.6
        self.assertTrue(d[near].mean() > d[~near].mean())
        sp = L.ref_dissolve_front(p0, (0, 0, 0), (0, 0, 3), 'spiral', 1.0, 0.5, 0.05)
        self.assertTrue(0.2 < sp.mean() < 0.8)

    def test_layers_with_echoes(self):
        raw = {'Quality': 'custom', 'Count': 10000, 'Actormode': 'gen', 'Actorcount': 1000, 'Pool': 10.0, 'Echoes': 3}
        ns, na, npool = L.layers(raw)
        self.assertEqual((na, npool, 10000 - ns - na - npool), (1000, 1000, 3000))
        self.assertEqual(L.sprite_range('splats', ns, na, npool, 3000), (ns + na, 4000))
        self.assertEqual(L.layers({'Quality': 'custom', 'Count': 10000}), (10000, 0, 0))

    def test_echo_and_grid_codegen(self):
        st, _ = L.add_module([], 'prox_push')
        off = L.codegen(st, LIB, TU, TC, MODS, PAL)
        on = L.codegen(st, LIB, TU, TC, MODS, PAL, echo=True)
        self.assertNotIn('actor echoes (SA31)', off['update'])
        self.assertIn('actor echoes (SA31)', on['update'])
        self.assertNotEqual(off['hash'], on['hash'])
        g = L.grid_section(open(os.path.join(GLSL, 'eff_consumer.glsl')).read())
        self.assertIn('float pxgFieldNearest(', g)
        self.assertNotIn('uEffSel', g)
        st2, _ = L.add_module([], 'heat_spread')
        cg = L.codegen(st2, LIB, TU, TC, MODS, PAL, grid_text=g)
        self.assertTrue(cg['grid'])
        self.assertIn('#define PXE_GRID sTD2DInputs[2]', cg['update'])
        st3, _ = L.add_module(st2, 'mask_image')
        self.assertFalse(L.codegen(st3, LIB, TU, TC, MODS, PAL, grid_text=g)['grid'])     # the mask input wins

    def test_wave3_looks(self):
        W3 = ('Packet glitch', 'Crane director', 'Fire spreads', 'Echo dancer', 'Glyph city', 'Pointillist',
              'Spiral reveal', 'kNN lace sweep')
        for nm in W3:
            s = L.builtin_preset(nm)
            self.assertEqual(s['values'].get('Echoes'), 0 if nm != 'Echo dancer' else 6, nm)
        self.assertEqual(L.builtin_preset('KANDA swipe')['values']['Cammode'], 'orbit')    # whole looks reset the rig


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Wave3Compile(Compile):
    def test_all_modules_echo_grid(self):
        g = L.grid_section(open(os.path.join(GLSL, 'eff_consumer.glsl')).read())
        st = []
        for t in L.module_types():
            if t != 'mask_image':
                st, _ = L.add_module(st, t)
        cg = L.codegen(st, LIB, TU, TC, MODS, PAL, echo=True, grid_text=g)
        self._ok(cg['update'], 'update echo grid')
        self._ok(cg['colour'], 'colour echo grid')
        self._ok(cg['update_inplace'], 'update inplace echo grid')
        self._ok(L.source_text(LIB, rd('px_source.glsl')), 'source (top mode)')


class Builder(unittest.TestCase):
    def test_wave2_builder_pieces(self):
        with open(os.path.join(BUILDERS, 'px.py')) as fh:
            src = fh.read()
        for k in ("'uEffRows', 'eff_in', 'texturebuffer'", 'def wave2_upgrade', "'px_bloom.glsl'", "'px_haze.glsl'",
                  'geo_stage', "'PX_lines'", "'sw_lines'", "'sw_haze'", "'Geoon'"):
            self.assertIn(k, src)
        self.assertIn('cleardepth', src)
        src.encode('ascii')


if __name__ == '__main__':
    unittest.main()
