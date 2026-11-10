"""Offline tests for Blender -> TD: tools/blender_td_logic.py (pure maths), the fixture export
(test/fixtures/blender/tiny_stage.*, made headless by tools/blender_export.py --make-test-scene) and
td/handlers.py cmd_import_blender on a fake TD. A Blender re-export check runs only when Blender is installed.

Run from jazib-td-mcp/:  python3 -I -m unittest discover -s test -p 'test_*.py'
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, HERE)
import blender_td_logic as L  # noqa: E402
import test_handlers as TH  # noqa: E402  (installs the td stub, imports handlers)

handlers = TH.handlers
FIX = os.path.join(HERE, 'fixtures', 'blender')
BLENDER = os.environ.get('BLENDER_PATH', '/Applications/Blender.app/Contents/MacOS/Blender')


def close(a, b, eps=1e-4):
    return all(abs(x - y) < eps for x, y in zip(a, b))


class Logic(unittest.TestCase):
    def test_point_map(self):
        self.assertEqual(L.point_to_td((1, 2, 3)), (1.0, 3.0, -2.0))

    def test_object_identity_and_camera_frame(self):
        I = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        d = L.decompose(L.mat4_to_td(I, 'object'))
        self.assertEqual((d['t'], d['r'], d['s']), ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]))
        # Blender camera with identity rotation looks down Blender -Z (straight down); in TD that is -Y:
        # TD camera rotated rx = -90 (its -Z goes to -Y).
        c = L.decompose(L.mat4_to_td(I, 'camera'))
        self.assertTrue(close(c['r'], [-90.0, 0.0, 0.0]), c)

    def test_blender_front_camera_is_td_level(self):
        # Blender camera rotated X +90 looks along +Y (into the scene) -> TD looks along -Z: no rotation.
        a = math.radians(90)
        M = [[1, 0, 0, 0], [0, math.cos(a), -math.sin(a), -10], [0, math.sin(a), math.cos(a), 2], [0, 0, 0, 1]]
        c = L.decompose(L.mat4_to_td(M, 'camera'))
        self.assertTrue(close(c['r'], [0, 0, 0]), c)
        self.assertTrue(close(c['t'], [0, 2, 10]), c)

    def test_compose_roundtrip(self):
        for t, r, s in (([1, 2, 3], [10, 20, 30], [1, 2, 3]), ([0, 0, 0], [-45, 80, 170], [1, 1, 1])):
            d = L.decompose(L.compose(t, r, s))
            self.assertTrue(close(d['t'], t) and close(d['r'], r, 1e-3) and close(d['s'], s), (d, t, r, s))

    def test_units(self):
        M = [[1, 0, 0, 1], [0, 1, 0, 2], [0, 0, 1, 3], [0, 0, 0, 1]]
        self.assertTrue(close(L.decompose(L.mat4_to_td(M), unit=0.3048)['t'], [0.3048, 0.9144, -0.6096]))
        with self.assertRaises(ValueError):
            L.unit_scale(0)

    def test_camera_view(self):
        v = L.camera_view(35, 36, 24, 'AUTO', 1920, 1080, shift_x=0.1, shift_y=0.05)
        self.assertAlmostEqual(v['hfov'], 2 * math.degrees(math.atan(18 / 35.0)), 4)
        self.assertAlmostEqual(math.tan(math.radians(v['vfov'] / 2)), math.tan(math.radians(v['hfov'] / 2)) / (16 / 9.), 5)
        self.assertEqual((v['winx'], v['winy']), (0.1, round(0.05 * 16 / 9., 6)))
        p = L.camera_view(35, 36, 24, 'AUTO', 1080, 1920, shift_x=0.1, shift_y=0.05)  # portrait: fit = height
        self.assertEqual(p['fit'], 'vertical')
        self.assertAlmostEqual(p['vfov'], 2 * math.degrees(math.atan(18 / 35.0)), 4)
        self.assertEqual((p['winx'], p['winy']), (round(0.1 / (1080 / 1920.), 6), 0.05))
        vv = L.camera_view(50, 36, 24, 'VERTICAL', 1920, 1080)
        self.assertAlmostEqual(vv['vfov'], 2 * math.degrees(math.atan(12 / 50.0)), 4)
        o = L.camera_view(50, 36, 24, 'AUTO', 1000, 2000, ortho=True, ortho_scale=10, unit=2)
        self.assertEqual((o['projection'], o['orthowidth']), ('ortho', 10.0))
        with self.assertRaises(ValueError):
            L.camera_view(50, 36, 24, 'DIAG', 10, 10)

    def test_lights_and_projector(self):
        s = L.light_values('SPOT', (1, 0.5, 0), 1000, math.radians(40), 0.2)
        self.assertEqual((s['lighttype'], s['coneangle'], s['conedelta'], s['dimmer']), ('cone', 40.0, 4.0, 1.0))
        self.assertEqual(L.light_values('SUN', (1, 1, 1), 5)['lighttype'], 'distant')
        self.assertEqual(L.light_values('POINT', (1, 1, 1), 1e9)['dimmer'], L.DIMMER_MAX)
        with self.assertRaises(ValueError):
            L.light_values('LASER', (1, 1, 1), 1)
        self.assertIsNone(L.projector_values({}, 40))
        p = L.projector_values({'projector': '/x.png', 'projector_throw': 1.5, 'projector_res': '1920x1080'}, 40)
        self.assertEqual((p['texture'], p['res']), ('/x.png', (1920, 1080)))
        self.assertAlmostEqual(p['hfov'], 36.8699, 3)
        q = L.projector_values({'projector': True}, 30)
        self.assertEqual((q['texture'], q['hfov']), ('', 30.0))
        self.assertAlmostEqual(L.hfov_from_throw(q['throw']), 30.0, 3)
        with self.assertRaises(ValueError):
            L.parse_res('1920')


class Fixture(unittest.TestCase):
    """The tiny stage exported by Blender 5.2.2: deck 8x4x1 m, FOH camera (0,-12,3) aimed at (0,0,1), projector
    spot (0,-8,4) aimed at (0,0,1)."""

    def setUp(self):
        with open(os.path.join(FIX, 'tiny_stage.json')) as fh:
            self.s = json.load(fh)

    def test_sidecar(self):
        s = self.s
        self.assertEqual(s['schema'], L.SCHEMA)
        self.assertEqual(s['geometry']['usd'], 'tiny_stage.usdc')
        cam = s['cameras'][0]
        self.assertTrue(close(cam['xform']['t'], [0, 3, 12]))
        self.assertTrue(close(cam['xform']['r'], [-math.degrees(math.atan(2 / 12.)), 0, 0], 1e-3))
        self.assertEqual(cam['view']['winx'], 0.1)
        pj = s['lights'][0]
        self.assertTrue(close(pj['xform']['t'], [0, 4, 8]))
        self.assertTrue(close(pj['xform']['r'], [-math.degrees(math.atan(3 / 8.)), 0, 0], 1e-3))
        self.assertEqual(pj['projector']['res'], [1920, 1080])
        self.assertEqual(s['objects'][0]['dims_m'], [8.0, 1.0, 4.0])

    @unittest.skipUnless(os.path.exists(BLENDER), 'Blender not installed')
    def test_reexport_matches_fixture(self):
        out = tempfile.mkdtemp()
        try:
            r = subprocess.run([BLENDER, '-b', '--factory-startup', '--disable-autoexec',
                                os.path.join(FIX, 'tiny_stage.blend'), '--python',
                                os.path.join(ROOT, 'tools', 'blender_export.py'), '--', '--out', out, '--name', 't',
                                '--format', 'usd'], capture_output=True, text=True, timeout=180)
            self.assertIn('JZB_EXPORT', r.stdout, r.stdout[-2000:] + r.stderr[-2000:])
            with open(os.path.join(out, 't.json')) as fh:
                n = json.load(fh)
            for k in ('cameras', 'lights', 'objects', 'units', 'scene', 'world'):
                self.assertEqual(n[k], self.s[k], k)
            self.assertTrue(os.path.getsize(os.path.join(out, 't.usdc')) > 0)
        finally:
            shutil.rmtree(out, ignore_errors=True)


class AnyOp(TH.RecOp):
    """RecOp whose .par makes any par on first use (camera / light / USD pars)."""

    def __init__(self, comp, name, optype):
        TH.RecOp.__init__(self, comp, name, optype)
        base = vars(self.par)
        me = self

        class Pars(object):
            def __getattr__(self, k):
                if k.startswith('__'):
                    raise AttributeError(k)
                p = base.get(k) or TH.FakePar(me, k)
                base[k] = p
                setattr(self, k, p)
                return p
        self.par = Pars()


class AnyComp(TH.RecComp):
    def create(self, cls, name=None):
        if cls == 'baseCOMP':
            o = AnyComp(self.path.rstrip('/') + '/' + name, self)
        else:
            o = AnyOp(self, name, cls)
        self.children.append(o)
        TH.OPS[o.path] = o
        return o


TYPES = handlers.BLENDER_OP_TYPES + ('baseCOMP', 'textDAT')


class ImportCommand(unittest.TestCase):
    def setUp(self):
        for n in TYPES:
            setattr(handlers, n, n)
        self.comp = AnyComp('/p')
        TH.OPS['/p'] = self.comp
        self.ops = [
            {'name': 'geo', 'type': 'usdCOMP', 'pars': {'file': '/x/tiny.usdc', 'cameras': False}, 'pulse': ['imp']},
            {'name': 'cam_FOH', 'type': 'cameraCOMP', 'pars': {'tx': 0, 'ty': 3, 'tz': 12, 'fov': 54.43, 'winx': 0.1}},
            {'name': 'map_P', 'type': 'rampTOP', 'pars': {'resolutionw': 1920}},
            {'name': 'light_P', 'type': 'lightCOMP', 'pars': {'projmap': 'map_P', 'projangle': 36.87},
             'exprs': {'dimmer': 'parent().par.Lightdimmer * 0.8'}, 'comment': 'projector'},
            {'name': 'render', 'type': 'renderTOP', 'exprs': {'camera': 'parent().par.Camera.eval()'}},
            {'name': 'out', 'type': 'nullTOP'}]

    def tearDown(self):
        for n in TYPES:
            if n in vars(handlers) and getattr(handlers, n) == n:
                delattr(handlers, n)
        TH.OPS.clear()

    def test_builds_comp(self):
        r = handlers.cmd_import_blender('/p', 'bl_tiny', self.ops, wires=[['render', 'out']], sidecar='{}',
                                        report='rep', arrange=False)
        c = self.comp.op('bl_tiny')
        self.assertEqual(sorted(o.name for o in c.children),
                         ['cam_FOH', 'geo', 'light_P', 'map_P', 'out', 'render', 'report', 'sidecar'])
        self.assertEqual(c.op('geo').par.file.val, '/x/tiny.usdc')
        self.assertEqual(c.op('geo').par.imp.pulsed, 1)
        self.assertEqual(r['pulsed'], ['geo.imp'])
        self.assertEqual(c.op('cam_FOH').par.fov.val, 54.43)
        lp = c.op('light_P').par
        self.assertEqual((lp.projmap.val, lp.dimmer.expr), ('map_P', 'parent().par.Lightdimmer * 0.8'))
        self.assertEqual(c.op('light_P').comment, 'projector')
        self.assertIs(c.op('out').inputConnectors[0].connections[0].owner, c.op('render'))
        self.assertEqual((c.op('report').text, r['out']), ('rep', '/p/bl_tiny/out'))
        self.assertTrue(c.op('render').viewer)

    def test_refusals_build_nothing(self):
        bad = [dict(self.ops[0], type='scriptDAT')]
        with self.assertRaises(ValueError):
            handlers.cmd_import_blender('/p', 'bl_x', bad, arrange=False)
        with self.assertRaises(ValueError):
            handlers.cmd_import_blender('/p', 'bl_x', self.ops + [dict(self.ops[0])], arrange=False)  # duplicate
        with self.assertRaises(ValueError):
            handlers.cmd_import_blender('/p', 'bl_x', self.ops, wires=[['render', 'nope']], arrange=False)
        with self.assertRaises(ValueError):
            handlers.cmd_import_blender('/p', 'bl x', self.ops, arrange=False)
        self.assertIsNone(self.comp.op('bl_x'))
        handlers.cmd_import_blender('/p', 'bl_x', self.ops, arrange=False)
        with self.assertRaises(ValueError):  # exists
            handlers.cmd_import_blender('/p', 'bl_x', self.ops, arrange=False)

    def test_registered(self):
        self.assertIs(handlers.COMMANDS['import_blender'], handlers.cmd_import_blender)
        self.assertIn('import_blender', handlers.MUTATING)
        self.assertIn('import_blender', handlers.PRESAVE_CMDS)


if __name__ == '__main__':
    unittest.main()
