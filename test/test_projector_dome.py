# Offline tests for builders/projector_dome_logic.py (no TD):
#   python3 -I -m unittest discover -s test -p 'test_projector_dome.py'
import math
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
L = {}
exec(open(os.path.join(HERE, '..', 'builders', 'projector_dome_logic.py'), encoding='utf-8').read(), L)


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


class Optics(unittest.TestCase):
    def test_throw_angle_round_trip(self):
        for T in (0.5, 1.0, 1.258, 2.0):
            self.assertTrue(close(L['throw_from_angle'](L['hfov'](T)), T))
        # the old LK_projection_room default (Throw 43.4 deg) is a 1.256:1 lens
        self.assertAlmostEqual(L['throw_from_angle'](43.4), 1.2564, places=3)

    def test_image_size(self):
        W, H, D = L['image_size'](6.0, 1.5, 1920, 1080)
        self.assertTrue(close(W, 4.0) and close(H, 2.25) and close(D, math.hypot(4, 2.25)))

    def test_vfov(self):
        self.assertTrue(close(L['vfov'](1.0, 1920, 1080), 2 * math.degrees(math.atan(1080 / 3840.))))

    def test_density_perpendicular_wall_is_uniform(self):
        # wall at depth 5, pixels uniform: ppm = T*resx/z at the centre and at an off-axis point
        T, rx = 1.5, 1920
        self.assertTrue(close(L['px_per_m'](T, rx, 5.0), T * rx / 5.0))
        a = math.atan(0.3)
        d = 5.0 / math.cos(a)
        self.assertTrue(close(L['px_per_m'](T, rx, d, math.cos(a), math.cos(a)), T * rx / 5.0))
        # check 3 of AT 6.5: ppi = Resx / W / 39.37
        W = 5.0 / T
        self.assertTrue(close(L['ppi'](L['px_per_m'](T, rx, 5.0)), rx / W / 39.37007874))

    def test_density_drops_with_cos(self):
        base = L['px_per_m'](1.5, 1920, 5.0)
        self.assertTrue(close(L['px_per_m'](1.5, 1920, 5.0, 0.5), base * 0.5))   # AT check 4 (wall at 60 deg)

    def test_lux_nits(self):
        E = L['lux'](6000, 1.5, 1920, 1080, 6.0)
        W, H, _ = L['image_size'](6.0, 1.5, 1920, 1080)
        self.assertTrue(close(E, 6000 / (W * H)))
        self.assertTrue(close(L['nits'](E, 1.0), E / math.pi))
        self.assertTrue(close(L['foot_lamberts'](342.6), 100.0))
        a = math.atan(0.25)
        self.assertTrue(close(L['lux'](6000, 1.5, 1920, 1080, 6.0 / math.cos(a), math.cos(a), math.cos(a)), E))

    def test_resolution_presets(self):
        self.assertEqual(L['resolution']('wuxga', 1, 1), (1920, 1200))
        self.assertEqual(L['resolution']('custom', 1024, 768), (1024, 768))


class Shift(unittest.TestCase):
    def test_canvas_no_shift(self):
        c = L['canvas'](1.5, 0, 0, 1920, 1080, 1024)
        self.assertTrue(close(c['projangle'], L['hfov'](1.5)))
        self.assertEqual((c['w'], c['h']), (1024, 576))
        self.assertEqual(tuple(round(x, 6) for x in c['rect']), (0, 0, 1, 1))

    def test_canvas_shift_matches_offaxis_frustum(self):
        T, sh, sv = 1.5, 0.25, 0.5
        c = L['canvas'](T, sh, sv, 1920, 1080, 1000)
        half = math.tan(math.radians(c['projangle'] / 2))        # tan half-width of the padded symmetric map
        u0, v0, u1, v1 = c['rect']
        # image left/right edges in tan space = (-0.5+sh)/T, (0.5+sh)/T
        self.assertTrue(close((2 * u0 - 1) * half, (-0.5 + sh) / T))
        self.assertTrue(close((2 * u1 - 1) * half, (0.5 + sh) / T))
        # vertical: the map aspect sets the tan half-height
        hh = half * c['h'] / float(c['w'])
        ar = 1920 / 1080.
        self.assertTrue(abs((2 * v0 - 1) * hh - (-0.5 + sv) / (T * ar)) < 2e-3)
        self.assertTrue(abs((2 * v1 - 1) * hh - (0.5 + sv) / (T * ar)) < 2e-3)

    def test_project_shift_edge_on_axis(self):
        # AT check 2: shift V +50 % puts the image bottom edge on the lens axis
        pj = L['projector'](True, (0, 0, 0), 0, 0, 1.5, 1920, 1080, 6000, 0.0, 0.5)
        u, v, z, d = L['project'](pj, (0, 0, -5))
        self.assertTrue(close(u, 0.5) and close(v, 0.0))
        pj = L['projector'](True, (0, 0, 0), 0, 0, 1.5, 1920, 1080, 6000, 0.5, 0.0)
        u, v, _, _ = L['project'](pj, (0, 0, -5))
        self.assertTrue(close(u, 0.0))


class Rig(unittest.TestCase):
    def test_basis_matches_td_order(self):
        R, U, F = L['basis'](0, 0)
        self.assertEqual(tuple(round(x, 9) for x in F), (0, 0, -1))
        R, U, F = L['basis'](30, 0)          # tilt up 30
        self.assertTrue(close(F[1], math.sin(math.radians(30))))
        R, U, F = L['basis'](0, 90)          # pan 90 -> looks along -X
        self.assertTrue(close(F[0], -1.0))
        rx, ry = L['look_angles']((-1, 0.5, -2))
        _, _, F = L['basis'](rx, ry)
        n = math.sqrt(1 + 0.25 + 4)
        for a, b in zip(F, (-1 / n, 0.5 / n, -2 / n)):
            self.assertTrue(close(a, b))

    def test_probe_point_wall(self):
        pj = L['projector'](True, (0, 2, 6), 0, 0, 1.5, 1920, 1080, 6000, 0, 0)
        cov, ppm, lx = L['probe_point'](pj, (0, 2, -3), (0, 0, 1))
        self.assertEqual(cov, 1.0)
        self.assertTrue(close(ppm, 1.5 * 1920 / 9.0))
        self.assertTrue(close(lx, L['lux'](6000, 1.5, 1920, 1080, 9.0)))
        self.assertEqual(L['probe_point'](pj, (0, 2, -3), (0, 0, -1))[0], 0.0)   # facing away
        self.assertEqual(L['probe_point'](pj, (10, 2, -3), (0, 0, 1))[0], 0.0)   # outside the image

    def test_overlap_strip(self):
        # AT check 5: two projectors side by side overlapping by 20 % of the image width
        T, z = 1.5, 6.0
        W = z / T
        A = L['projector'](True, (0, 0, 0), 0, 0, T, 1920, 1080, 6000, 0, 0)
        B = L['projector'](True, (0.8 * W, 0, 0), 0, 0, T, 1920, 1080, 6000, 0, 0)
        xs = [i * 0.001 * 2 * W - 0.5 * W for i in range(1001)]
        two = [x for x in xs if L['probe_point'](A, (x, 0, -z), (0, 0, 1))[0] + L['probe_point'](B, (x, 0, -z), (0, 0, 1))[0] == 2]
        self.assertAlmostEqual((max(two) - min(two)) / W, 0.2, places=2)

    def test_uniform_rows(self):
        A = L['projector'](True, (1, 2, 3), 0, 0, 1.5, 1920, 1080, 6000, 0.1, 0.2, 1.3)
        rows = L['uniforms']([A, A])
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[0], (1, 2, 3, 1.0))
        self.assertEqual(rows[4], (1.5, 1920.0, 1080.0, 6000.0))
        self.assertEqual(rows[5], (0.1, 0.2, 1.3, 0.0))

    def test_orbit_matches_original_formula(self):
        p = {'Campreset': 'orbit', 'Camdist': 10.469, 'Orbit': -59.2, 'Height': 5.34, 'Lookheight': 0.808625,
             'Camfov': 45}
        c = L['rig'](p)['cam']
        a = math.radians(36 - 59.2)
        self.assertTrue(close(c['tx'], 10.469 * math.sin(a)) and close(c['tz'], 10.469 * math.cos(a)))
        self.assertTrue(close(c['rx'], -math.degrees(math.atan2(5.34 - 0.808625, 10.469))))
        self.assertTrue(close(c['ry'], 36 - 59.2))

    def test_through_projector_preset(self):
        p = {'Campreset': 'proja', 'Projx': 1, 'Projy': 2, 'Projz': 3, 'Projtilt': -10, 'Projpan': 5,
             'Throwratio': 1.2, 'Shifth': 10, 'Shiftv': -20}
        c = L['rig'](p)['cam']
        self.assertEqual((c['tx'], c['ty'], c['tz'], c['rx'], c['ry']), (1, 2, 3, -10, 5))
        self.assertTrue(close(c['fov'], L['hfov'](1.2)))
        self.assertTrue(close(c['winx'], 0.1) and close(c['winy'], -0.2))

    def test_legacy_angle_input(self):
        st = L['rig']({'Lensinput': 'angle', 'Throw': 43.4})
        self.assertTrue(close(st['chans']['pa_projangle'], 43.4))

    def test_frustum(self):
        pj = L['projector'](True, (0, 0, 0), 0, 0, 2.0, 1920, 1080, 6000, 0, 0)
        segs = L['frustum_segments'](pj, 4.0)
        self.assertEqual(len(segs), 8)
        xs = [s[1][0] for s in segs[:4]]
        self.assertTrue(close(max(xs) - min(xs), 2.0))   # W = D/T

    def test_readouts_and_hud(self):
        p = {'Throwratio': 1.5, 'Respreset': 'hd', 'Lumens': 6000, 'Gain': 1.0}
        ppm = 1.5 * 1920 / 9.0
        r = L['readouts'](p, {'a_d': 9.0, 'a_ppm': ppm, 'a_avgppm': ppm * 0.5, 'a_avgcov': 0.5, 'a_maxmm': 1000.0 / ppm})
        self.assertTrue(close(r['imgw'], 6.0) and close(r['ppi'], ppm / 39.37007874))
        self.assertTrue(close(r['lux'], L['lux'](6000, 1.5, 1920, 1080, 9.0)))
        self.assertTrue(close(r['avgppi'], r['ppi']) and close(r['minppi'], r['ppi']))
        t = L['hud_text'](dict(p, Unit='ft'), r)
        self.assertIn('19.69 ft', t)                     # 6 m image width in feet
        self.assertIn('throw 1.50:1', t)
        miss = L['readouts'](p, {})
        self.assertIn('no surface', L['hud_text'](p, miss))


class Dome(unittest.TestCase):
    def test_round_trip(self):
        for fov in (180.0, 220.0):
            for u, v in ((0.5, 0.5), (0.3, 0.7), (0.9, 0.5), (0.5, 0.05)):
                d = L['dome_dir'](u, v, fov)
                uu, vv = L['dome_uv'](d, fov)
                self.assertTrue(close(uu, u) and close(vv, v))

    def test_conventions(self):
        self.assertEqual(tuple(round(x, 9) for x in L['dome_dir'](0.5, 0.5)), (0, 1, 0))   # zenith at centre
        f = L['dome_dir'](0.5, 0.0)                     # bottom edge = front horizon (-Z)
        self.assertTrue(close(f[2], -1.0) and abs(f[1]) < 1e-9)
        r = L['dome_dir'](1.0, 0.5)                     # right edge = +X
        self.assertTrue(close(r[0], 1.0))
        self.assertIsNone(L['dome_dir'](0.0, 0.0))      # corner outside the circle
        self.assertIsNone(L['dome_uv']((0, -1, 0), 180))

    def test_tilt(self):
        z = L['tilt_dir']((0, 1, 0), 30)
        self.assertTrue(close(z[1], math.cos(math.radians(30))) and close(z[2], -math.sin(math.radians(30))))

    def test_window_and_equirect(self):
        self.assertEqual(L['window_uv']((0, 0, -1), 0, 0, 60, 30), (0.5, 0.5))
        self.assertIsNone(L['window_uv']((0, 0, 1), 0, 0, 60, 30))
        u, v = L['equirect_uv']((0, 0, -1))
        self.assertTrue(close(u, 0.5) and close(v, 0.5))
        self.assertTrue(close(L['equirect_uv']((0, 1, 0))[1], 1.0))


if __name__ == '__main__':
    unittest.main()
