"""Offline tests for PX phase C (28 Oct): auto quality (hold60 controller, the px_auto layer, render-size expressions,
sort-key map), LOD by distance, sort only on change, external camera (Usecam). docs/builds/px.md "28 Oct: phase C".
No TD needed. Run: python3 -I -m unittest discover -s test -p 'test_px_phaseC.py'"""
import math
import os
import random
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
sys.path.insert(0, BUILDERS)
import px_logic as L  # noqa: E402


def _rd(*p):
    with open(os.path.join(BUILDERS, *p)) as fh:
        return fh.read()


def _spec(page, name):
    for pg, pars in L.CORE_PAGES:
        if pg == page:
            for s in pars:
                if s[0] == name:
                    return s
    return None


def _items(*mods):
    """[(type, values, drives)] with schema defaults + overrides."""
    out = []
    for m in mods:
        t, over = (m, {}) if isinstance(m, str) else m
        st, uid = L.add_module([], t)
        v = L.instance_values(st[0], {})
        v.update(over.get('v', {}))
        out.append((t, v, over.get('d', [])))
    return out


# ---- a fake TD parent for evaluating the size expressions ---------------------------------------------------------
class _Par(object):
    def __init__(self, v):
        self.v = v

    def eval(self):
        return self.v


class _Chop(object):
    def __init__(self, **ch):
        self.ch = ch

    def __getitem__(self, k):
        return self.ch[k]


class _Comp(object):
    def __init__(self, auto, **pars):
        self.par = type('P', (), dict((k, _Par(v)) for k, v in pars.items()))()
        self._auto = auto

    def op(self, name):
        return self._auto if name == 'px_auto' else None


class _Me(object):
    def __init__(self, comp):
        self._c = comp

    def parent(self):
        return self._c


def ev(expr, resf=1.0, **pars):
    return eval(expr, {'me': _Me(_Comp(_Chop(resf=resf), **pars)), 'max': max, 'min': min, 'int': int})


class Pars(unittest.TestCase):
    def test_perf_page(self):
        for n, st, d in (('Autoquality', 'Menu', 'off'), ('Aqfps', 'Float', 57.0), ('Aqframes', 'Int', 45),
                         ('Aqheadroom', 'Float', 10.0), ('Aqstate', 'Str', 'off'), ('Sortstill', 'Toggle', True),
                         ('Lod', 'Toggle', False), ('Loddist', 'Float', 6.0), ('Lodkeep', 'Float', 0.35)):
            s = _spec('Perf', n)
            self.assertIsNotNone(s, n)
            self.assertEqual((s[1], s[2]), (st, d), n)
        self.assertTrue(_spec('Perf', 'Aqstate')[3].get('readonly'))
        self.assertEqual(_spec('Perf', 'Autoquality')[3]['names'], ['off', 'hold60', 'governor'])
        self.assertIn('Perf', L.PANEL_CORE_PAGES)

    def test_camera_source(self):
        cam = dict(L.CORE_PAGES)['Camera']
        self.assertEqual([s[0] for s in cam[:2]], ['Camsource', 'Camcomp'])     # first on the Camera page
        self.assertEqual(cam[0][2], 'internal')                                  # default = the old camera
        self.assertTrue(cam[1][3].get('menu'))                                   # a live dropdown
        self.assertEqual(L.menu_specs(cam)[:1], ['Camcomp'])

    def test_never_in_a_look(self):
        for n in ('Autoquality', 'Aqstate', 'Sortstill', 'Lod', 'Loddist', 'Lodkeep', 'Camsource', 'Camcomp'):
            self.assertIn(n, L.NOSNAP)
        ld = L.look_defaults()
        for n in ('Camsource', 'Camcomp', 'Autoquality', 'Lod'):
            self.assertNotIn(n, ld)                    # a built-in look never switches the camera / auto quality


class Rows(unittest.TestCase):
    def test_lod_rows_default_off(self):
        r = L.render_rows({}, 10, 100)
        self.assertEqual(len(r), L.R_ROWS)
        self.assertEqual(r[9][0], 0.0)
        vec, sp = L.splat_rows({}, 100)
        self.assertEqual(len(sp), L.SP_ROWS)
        self.assertEqual(sp[4][0], 0.0)
        on = L.lod_row({'Lod': True, 'Loddist': 4.0, 'Lodkeep': 0.25})
        self.assertEqual(on, [1.0, 4.0, 0.25, 0.0])
        self.assertEqual(L.lod_row({'Lod': 1, 'Lodkeep': 5.0})[2], 1.0)          # clamped share
        self.assertEqual(L.lod_row({'Lod': 1, 'Lodkeep': 0.0})[2], 0.01)

    def test_shader_arrays_match_rows(self):
        self.assertIn('uniform vec4 uR[%d];' % L.R_ROWS, _rd('glsl', 'px_vert.glsl'))
        self.assertIn('uniform vec4 uR[%d];' % L.R_ROWS, _rd('glsl', 'px_pixel.glsl'))
        self.assertIn('uniform vec4 uSp[%d];' % L.SP_ROWS, _rd('glsl', 'px_splat_adapter.glsl'))
        self.assertIn('uniform vec4 uSp[%d];' % L.SP_ROWS, _rd('glsl', 'px_sortkey.glsl'))


class Lod(unittest.TestCase):
    def test_keep_curve(self):
        self.assertEqual(L.lod_keep(1.0, 6.0, 0.3), 1.0)
        self.assertEqual(L.lod_keep(6.0, 6.0, 0.3), 1.0)
        self.assertAlmostEqual(L.lod_keep(9.0, 6.0, 0.3), 0.65)
        self.assertAlmostEqual(L.lod_keep(12.0, 6.0, 0.3), 0.3)
        self.assertAlmostEqual(L.lod_keep(50.0, 6.0, 0.3), 0.3)

    def test_hash_share(self):
        n = 20000
        h = [L.id_hash01(i) for i in range(n)]
        self.assertTrue(all(0.0 <= x < 1.0 for x in h))
        for k in (0.25, 0.5, 0.75):
            share = sum(1 for x in h if x < k) / float(n)
            self.assertAlmostEqual(share, k, delta=0.02)

    def test_area_kept(self):
        # kept splats grow by 1 / sqrt(share): kept count x radius^2 stays the same on average
        k = 0.35
        self.assertAlmostEqual(k * (1.0 / math.sqrt(k)) ** 2, 1.0)

    def test_glsl_twins(self):
        for fn, row in (('px_vert.glsl', 'uR[9]'), ('px_splat_adapter.glsl', 'uSp[4]')):
            t = _rd('glsl', fn)
            self.assertIn(row + '.x > 0.5' if fn == 'px_vert.glsl' else row + '.x < 0.5', t)
            self.assertIn('2654435761u', t)            # the same id hash as px_logic.id_hash01
            self.assertIn('inversesqrt', t)            # kept ones grow
        self.assertIn('s * pxsLodScale', _rd('glsl', 'px_splat_adapter.glsl'))
        self.assertIn('* lodk;', _rd('glsl', 'px_vert.glsl'))


class AutoQuality(unittest.TestCase):
    def test_steps(self):
        st = L.aq_steps({'Splataa': 'aa1'}, True)
        self.assertEqual(st[0], (False, 1.0, 1.0))
        self.assertEqual(len(st), 5)                   # no AA step at 1x
        self.assertEqual(st[1], (False, 0.75, 1.0))
        self.assertEqual(st[-1], (False, 0.5, 0.5))
        st4 = L.aq_steps({'Splataa': 'aa4'}, True)
        self.assertEqual(st4[1], (True, 1.0, 1.0))     # AA first, then points, then resolution
        self.assertEqual(len(st4), 6)
        self.assertTrue(all(s[0] for s in st4[1:]))
        self.assertEqual(len(L.aq_steps({'Splataa': 'aa4'}, False)), 5)   # sprites: no splat MSAA step
        self.assertEqual(L.aq_effect(st4, 99), st4[-1])
        self.assertEqual(L.aq_effect(st4, -3), st4[0])

    def test_governor_plan(self):
        import fps_gov_logic as G
        for i in range(0, 101):
            q = i / 100.0
            self.assertEqual(tuple(L.gov_plan(q)), tuple(G.px_plan(q)), q)
        self.assertEqual(tuple(L.gov_plan(1.0)), (False, 1.0, 1.0))      # full = no change
        self.assertEqual(_spec('Perf', 'Govop')[2], '/project1/lab/FG_fps_governor/out1')
        self.assertIn('governor', _spec('Perf', 'Autoquality')[3]['names'])
        self.assertEqual(_spec('Perf', 'Autoquality')[2], 'off')
        self.assertIn('Govop', L.NOSNAP)

    def test_labels(self):
        st = L.aq_steps({'Splataa': 'aa4'}, True)
        self.assertTrue(L.aq_label(st, 0).startswith('full quality (0/5)'))
        self.assertEqual(L.aq_label(st, 2, fps=51.6), 'step 2/5: splat AA 1x, points 75% (fps 52)')
        self.assertIn('res 50% = 540x960', L.aq_label(st, 5, res=(540, 960)))

    def test_res(self):
        self.assertEqual(L.aq_res(1080, 1920), L.eff_res(1080, 1920))
        self.assertEqual(L.aq_res(1080, 1920, 0.5), (540, 960))
        self.assertEqual(L.aq_res(1080, 1920, 0.75), (810, 1440))
        self.assertEqual(L.aq_res(20000, 12000), L.eff_res(20000, 12000))

    def test_raw(self):
        raw = {'Resx': 1080, 'Resy': 1920, 'Size': 0.02, 'Minpx': 1.0, 'Maxpx': 32.0}
        self.assertIs(L.aq_raw(raw), raw)
        r = L.aq_raw(raw, 1.0, 0.5)
        self.assertEqual((r['Resx'], r['Resy'], r['Minpx'], r['Maxpx']), (540, 960, 0.5, 16.0))
        self.assertEqual(raw['Resx'], 1080)            # the user's values are untouched
        r = L.aq_raw(raw, 0.5)
        g = 1.0 / math.sqrt(0.5)
        self.assertAlmostEqual(r['Size'], 0.02 * g)
        self.assertAlmostEqual(r['Splatscalemult'], g)
        self.assertEqual(r['Resx'], 1080)

    def test_key_map(self):
        end = 228287
        for cf in (0.75, 0.5):
            side = L.aq_key_side(end, cf)
            keys = int(math.ceil(end * cf))
            self.assertGreaterEqual(side * side, keys)
            ids = L.aq_key_ids(end, cf, side * side)
            kept = [i for i in ids if i >= 0]
            self.assertEqual(len(kept), keys)          # exactly ceil(end x f) splats drawn
            self.assertEqual(len(set(kept)), len(kept))
            self.assertTrue(all(0 <= i < end for i in kept))
            self.assertEqual(kept, sorted(kept))       # stable map: the same ids every sort
        self.assertEqual(L.aq_key_side(end, 1.0), L.side_for(end))
        self.assertEqual(L.aq_key_ids(10, 1.0, 12), list(range(10)) + [-1, -1])

    def test_controller_down_up(self):
        st, n, t = L.aq_new(), 5, 0.0
        for k in range(44):
            st, d = L.aq_step(st, 40.0, 25.0, t, n, 57.0, 45, 10.0)
            self.assertEqual(d, 0)
        st, d = L.aq_step(st, 40.0, 25.0, t, n, 57.0, 45, 10.0)
        self.assertEqual((d, st['level']), (1, 1))     # 45 frames under the threshold -> one step down
        for k in range(L.AQ_SETTLE):                   # settle frames: nothing counts
            st, d = L.aq_step(st, 40.0, 25.0, t, n, 57.0, 45, 10.0)
            self.assertEqual(d, 0)
        # headroom: fps fine and frame ms low for 3 x 45 frames -> one step up
        ups = []
        for k in range(200):
            st, d = L.aq_step(st, 60.0, 6.0, 100.0, n, 57.0, 45, 10.0)
            ups.append(d)
        k = ups.index(-1)                              # the average first climbs back from the settle frames
        self.assertTrue(3 * 45 - 1 <= k < 3 * 45 + 30, k)
        self.assertEqual(ups.count(-1), 1)
        self.assertEqual(st['level'], 0)

    def test_controller_holds_at_60_without_headroom(self):
        st = dict(L.aq_new(), level=2)
        for k in range(1000):
            st, d = L.aq_step(st, 60.0, 14.0, k / 60.0, 5, 57.0, 45, 10.0)   # 60 fps but no headroom
            self.assertEqual(d, 0)
        self.assertEqual(st['level'], 2)

    def test_controller_backoff(self):
        st = dict(L.aq_new(), level=1, last_up=5.0)
        for k in range(45):
            st, d = L.aq_step(st, 30.0, 30.0, 8.0, 5, 57.0, 45, 10.0)     # down 3 s after an up: ping-pong
        self.assertEqual((d, st['level'], st['upwait']), (1, 2, 2.0))
        st = dict(L.aq_new(), level=4)
        for k in range(100):
            st, d = L.aq_step(st, 10.0, 90.0, 0.0, 5, 57.0, 45, 10.0)
        self.assertEqual(st['level'], 4)               # never past the last step

    def test_res_expressions(self):
        old = L.clamp_expr('parent().par.Resx')
        new = L.aq_res_expr(old)
        self.assertNotEqual(new, old)
        self.assertIn("op('px_auto')['resf']", new)
        self.assertEqual(L.aq_res_expr(new), new)      # idempotent
        self.assertEqual(L.aq_res_expr('parent().par.Fov'), 'parent().par.Fov')
        for w, h in ((1080, 1920), (3840, 2160), (20000, 12000)):
            for rf in (1.0, 0.75, 0.5):
                ex, ey = L.aq_res(w, h, rf)
                self.assertEqual(ev(new, rf, Resx=w, Resy=h), ex)
                self.assertEqual(ev(L.aq_res_expr(L.clamp_expr('parent().par.Resy')), rf, Resx=w, Resy=h), ey)
            self.assertEqual(ev(new, 1.0, Resx=w, Resy=h), ev(old, 1.0, Resx=w, Resy=h))   # full = phase B value
        hz = L.aq_res_expr(L.clamp_expr('max(1, int(parent().par.Resx) // 4)'))
        self.assertEqual(ev(hz, 0.5, Resx=1080, Resy=1920), 135)
        self.assertIn('post', L.AQ_RES_SKIP)           # out1 keeps Resx x Resy

    def test_post_samples_by_uv(self):
        t = _rd('glsl', 'px_post.glsl')
        self.assertIn('bool same = sz == os;', t)
        self.assertIn('same ? texelFetch(sTD2DInputs[0], g, 0) : texture(sTD2DInputs[0], uv)', t)

    def test_sortkey_map_glsl(self):
        t = _rd('glsl', 'px_sortkey.glsl')
        self.assertIn('uniform vec4 uKs;', t)
        self.assertIn('int(floor(float(k) / kf))', t)
        self.assertIn('(uKs.x > 0.0 && uKs.x < 1.0) ? uKs.x : 1.0', t)    # no uniform = the full map


class SortOnChange(unittest.TestCase):
    def test_default_stack_moves(self):
        it = _items(('prox_push', {'v': {'strength': 0.4}}), ('curl', {'v': {'strength': 0.6}}), 'prox_colour',
                    ('dissolve_noise', {'v': {'progress': 0.0}}))
        self.assertTrue(L.stack_motion(it, 1 / 60.0))  # curl flows: the default keeps re-sorting

    def test_still_stacks(self):
        self.assertFalse(L.stack_motion(_items('prox_push', 'prox_colour'), 1 / 60.0))
        self.assertFalse(L.stack_motion(_items(('curl', {'v': {'mode': 'displace', 'speed': 0.0}})), 1 / 60.0))
        self.assertFalse(L.stack_motion(_items(('dissolve_noise', {'v': {'progress': 0.0}})), 1 / 60.0))
        self.assertFalse(L.stack_motion(_items('prox_colour', 'colour_ramp'), 1 / 60.0))   # colour only
        self.assertFalse(L.stack_motion(_items(('explode', {'v': {'progress': 0.4}})), 1 / 60.0))
        self.assertFalse(L.stack_motion(_items(('twist', {'v': {'wobble': 0.0}})), 1 / 60.0))
        self.assertFalse(L.stack_motion(_items(('jitter', {'v': {'mode': 'static'}})), 1 / 60.0))
        self.assertFalse(L.stack_motion(_items(('curl', {'v': {'strength': 0.0}})), 1 / 60.0))   # amount-like 0

    def test_moving_stacks(self):
        self.assertTrue(L.stack_motion(_items(('curl', {'v': {'mode': 'displace'}})), 1 / 60.0))   # speed 0.3
        self.assertTrue(L.stack_motion(_items(('explode', {'v': {'auto': 'loop'}})), 1 / 60.0))
        self.assertTrue(L.stack_motion(_items(('twist', {'v': {'wobble': 0.5}})), 1 / 60.0))
        self.assertTrue(L.stack_motion(_items('jitter'), 1 / 60.0))
        self.assertTrue(L.stack_motion(_items('prox_burn'), 1 / 60.0))
        self.assertTrue(L.stack_motion(_items('lifetime'), 1 / 60.0))
        self.assertTrue(L.stack_motion(_items(('prox_push', {'v': {'mode': 'force'}})), 1 / 60.0))
        self.assertTrue(L.stack_motion(_items(('orbit', {'v': {'speed': 0.5}})), 1 / 60.0))

    def test_drives_effectors_pause(self):
        drv = [('strength', None, 'bass', 1.0, 0.0)]
        self.assertTrue(L.stack_motion(_items(('prox_push', {'d': drv})), 1 / 60.0))
        self.assertTrue(L.stack_motion(_items(('prox_push', {'d': drv})), 0.0))     # a drive moves even paused
        self.assertTrue(L.stack_motion(_items('prox_push'), 1 / 60.0, eff_moving=True))
        self.assertTrue(L.stack_motion(_items('prox_push'), 0.0, eff_moving=True))   # a hand-moved effector
        self.assertFalse(L.stack_motion(_items('jitter', 'curl'), 0.0))            # Play off: frozen
        self.assertTrue(L.stack_motion(_items('prox_push'), 1 / 60.0, src_moving=True))
        self.assertFalse(L.stack_motion(_items('prox_colour'), 1 / 60.0, eff_moving=True))   # colour only

    def test_unknown_module_moves(self):
        self.assertFalse(L.module_still('not_a_module', {}))
        self.assertTrue(L.module_still('mask_region', {}))

    def test_settle(self):
        self.assertAlmostEqual(L.settle_s({}), 7.8 / 1.7)
        self.assertEqual(L.settle_s({'Damping': 100.0}), 1.0)
        self.assertEqual(L.settle_s({'Damping': 0.0, 'Drag': 0.0}), 8.0)


class Usecam(unittest.TestCase):
    def test_round_trip(self):
        rnd = random.Random(7)
        for _ in range(200):
            row = [rnd.uniform(-5, 5), rnd.uniform(-5, 5), rnd.uniform(-5, 5), rnd.uniform(-85, 85),
                   rnd.uniform(-179, 179), rnd.uniform(-179, 179)]
            pos, rt, up, fw = L.cam_basis(row)
            back = [-x for x in fw]
            r2 = L.basis_row(pos, rt, up, back)
            p2, rt2, up2, fw2 = L.cam_basis(r2)
            for a, b in zip(list(rt) + list(up) + list(fw), list(rt2) + list(up2) + list(fw2)):
                self.assertAlmostEqual(a, b, places=9)
            self.assertEqual(r2[:3], [float(x) for x in pos])

    def test_gimbal_and_scale(self):
        for ry in (90.0, -90.0):
            row = [0.0, 1.0, 2.0, ry, 30.0, 0.0]
            pos, rt, up, fw = L.cam_basis(row)
            r2 = L.basis_row(pos, [2 * x for x in rt], [3 * x for x in up], [-0.5 * x for x in fw])   # scaled axes
            _p, rt2, up2, fw2 = L.cam_basis(r2)
            for a, b in zip(list(rt) + list(up) + list(fw), list(rt2) + list(up2) + list(fw2)):
                self.assertAlmostEqual(a, b, places=6)

    def test_orbit_row(self):
        row = [math.sin(0.5) * 4, 0.3, math.cos(0.5) * 4, math.degrees(0.5), 0.0, 0.0]
        pos, rt, up, fw = L.cam_basis(row)
        r2 = L.basis_row(pos, rt, up, [-x for x in fw])
        self.assertAlmostEqual(r2[3], row[3])
        self.assertAlmostEqual(r2[4], 0.0)
        self.assertAlmostEqual(r2[5], 0.0)
        vp1 = L.cam_viewproj_row(row, 45.0, 1080, 1920)
        vp2 = L.cam_viewproj_row(r2, 45.0, 1080, 1920)
        for a, b in zip(sum(vp1, []), sum(vp2, [])):
            self.assertAlmostEqual(a, b, places=9)

    def test_fov(self):
        self.assertAlmostEqual(L.hfov_from_proj(1.0 / math.tan(math.radians(22.5))), 45.0)

    def test_menu_items(self):
        got = L.cam_menu_items(['/project1/lab/PX_pointfx/pcam', '/project1/lab/CS_cam_sequencer/cam_out',
                                '/project1/cam1', '/project1/lab/PX_pointfx1/pcam'], '/project1/lab/PX_pointfx')
        self.assertEqual(got, ['/project1/cam1', '/project1/lab/CS_cam_sequencer/cam_out',
                               '/project1/lab/PX_pointfx1/pcam'])


class Upgrade(unittest.TestCase):
    def test_staged_ui_safe(self):
        src = _rd('px.py')
        self.assertIn("UPGC_STEPS = ('b_texts', 'b_menus', 'b_tables', 'c_texts', 'c_pars', 'c_ops', 'c_exprs', 'done')", src)
        body = src[src.index('def phaseC_upgrade('):src.index('def phaseC_result(')]
        self.assertIn('_ui_safe(c)', body)             # T-249: off the screen first
        self.assertIn('_upgC_later(', body)            # the work runs in deferred steps
        self.assertNotIn('_phaseC_texts(c)', body)
        self.assertIn('delayFrames=delay', src[src.index('def _upgC_later('):])
        self.assertGreaterEqual(int(re.search(r'^UPG_GAP = (\d+)', src, re.M).group(1)), 3)

    def test_build_has_phase_c(self):
        src = _rd('px.py')
        b = src[src.index('def build('):src.index('def _post_clock(')]
        self.assertIn('_phaseC_ops(c)', b)
        self.assertIn('_phaseC_exprs(c)', b)
        self.assertIn("'px_perf', 'px_auto'", src)   # placed in the Controls stage

    def test_expression_forms(self):
        src = _rd('px.py')
        self.assertIn("AQ_AA_E = \"'aa1' if op('px_auto')['aa'] > 0.5 else \" + PP + \"Splataa.eval()\"", src)
        self.assertIn("op('eng_cam')['fov']", src)
        rt = _rd('px_rt.py')
        self.assertIn("CAM_CHANS = ('tx', 'ty', 'tz', 'ry', 'rx', 'rz', 'fov')", rt)
        self.assertIn("'Aqstate')", rt)                # Aqstate writes never mark the caches dirty


if __name__ == '__main__':
    unittest.main()
