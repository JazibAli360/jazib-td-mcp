"""Offline tests for builders/depth_cam_logic.py + static checks of the builder / runtime (no TD, no helper).
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_depth_cam.py'
numpy-backed tests are skipped when numpy is missing (TD has numpy 2.1.2)."""
import ast
import math
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
sys.path.insert(0, B)
import depth_cam_logic as L  # noqa: E402
import depth_cam as BLD  # noqa: E402  (top level defines constants and functions only; TD names used inside build)

def _src(name):
    with open(os.path.join(B, name)) as f:
        return f.read()


try:
    import numpy as np
except ImportError:
    np = None


class Easing(unittest.TestCase):
    def test_ease_step(self):
        self.assertEqual(L.ease_step(0.1, 0.0), 1.0)
        self.assertAlmostEqual(L.ease_step(0.3, 0.3), 1 - math.exp(-1), places=6)
        self.assertEqual(L.ease_step(-1.0, 0.3), 0.0)

    def test_tau(self):
        self.assertAlmostEqual(L.depth_tau(1.0), 0.6, places=6)
        self.assertAlmostEqual(L.depth_tau(2.0), 0.6, places=6)
        self.assertEqual(L.depth_tau(-1.0), 0.0)

    def test_percentiles_ramp(self):
        lo, hi = L.percentiles([i / 999.0 for i in range(1000)])
        self.assertAlmostEqual(lo, 0.02, delta=0.003)
        self.assertAlmostEqual(hi, 0.98, delta=0.003)

    def test_percentiles_flat_and_empty(self):
        self.assertEqual(L.percentiles([]), (0.0, 1.0))
        lo, hi = L.percentiles([0.5] * 10)
        self.assertAlmostEqual(hi - lo, 1e-3, places=6)

    def test_range_easer(self):
        e = L.RangeEaser()
        a = e.add(1.0, 3.0, 4, 2, 0.0, 0.5)
        self.assertTrue(a['first'])
        self.assertEqual((a['lo'], a['span'], a['k']), (1.0, 2.0, 1.0))
        b = e.add(2.0, 4.0, 4, 2, 0.1, 0.5)
        self.assertFalse(b['first'])
        self.assertTrue(1.0 < b['lo'] < 2.0)
        self.assertTrue(0.0 < b['k'] < 1.0)
        c = e.add(5.0, 6.0, 8, 2, 0.1, 0.5)  # size change = first again
        self.assertTrue(c['first'])
        self.assertEqual(c['lo'], 5.0)

    def test_smoothing_zero_takes_result(self):
        e = L.RangeEaser()
        e.add(0.0, 1.0, 2, 2, 0.0, 0.0)
        self.assertEqual(e.add(0.0, 1.0, 2, 2, 0.05, 0.0)['k'], 1.0)

    def test_field_step(self):
        out = L.field_step([0.0, 0.0, 1.0], [0.5, 2.0, -1.0], 0.0, 1.0, 0.5)
        self.assertEqual(out, [0.25, 0.5, 0.5])


@unittest.skipIf(np is None, 'numpy missing')
class Numpy(unittest.TestCase):
    def test_field_step_np_matches_reference(self):
        raw = np.array([[0.1, 0.4], [0.9, 1.3]], dtype=np.float32)
        ref0 = L.field_step([0.0] * 4, raw.ravel().tolist(), 0.1, 0.8, 1.0)
        f = L.field_step_np(np, None, raw, 0.1, 0.8, 1.0)
        self.assertEqual(f.dtype, np.float32)
        self.assertTrue(np.allclose(f.ravel(), ref0, atol=1e-6))
        raw2 = raw[::-1].copy()
        ref1 = L.field_step(ref0, raw2.ravel().tolist(), 0.1, 0.8, 0.3)
        f = L.field_step_np(np, f, raw2, 0.1, 0.8, 0.3)
        self.assertTrue(np.allclose(f.ravel(), ref1, atol=1e-6))

    def test_field_step_np_shape_change_restarts(self):
        f = L.field_step_np(np, np.zeros((2, 2), np.float32), np.ones((3, 3), np.float32), 0.0, 1.0, 0.1)
        self.assertEqual(f.shape, (3, 3))
        self.assertTrue(np.all(f == 1.0))

    def test_bgra_bytes_exact(self):
        v = np.arange(256, dtype=np.float32) / np.float32(255.0)
        a = np.stack([v, v[::-1], v, np.ones_like(v)], axis=1).reshape(16, 16, 4)
        b = np.frombuffer(L.bytes_from_bgra_float(np, a), np.uint8).reshape(16, 16, 4)
        self.assertTrue(np.array_equal(b[..., 0].ravel(), np.arange(256)))
        self.assertTrue(np.all(b[..., 3] == 255))

    def test_fake_depth_numpy(self):
        ys, xs = np.mgrid[0:98, 0:130].astype(np.float32)
        f = L.fake_depth((xs + 0.5) / 130, (ys + 0.5) / 98, 1.0, np.exp, np.cos, np.sin)
        self.assertEqual(f.shape, (98, 130))
        self.assertTrue(f.min() >= 0.0 and f.max() <= 1.0)


class Helpers(unittest.TestCase):
    def test_check_answer(self):
        self.assertEqual(L.check_answer(b'\0' * 32, 4, 2), 8)
        with self.assertRaises(ValueError):
            L.check_answer(b'\0' * 31, 4, 2)
        with self.assertRaises(ValueError):
            L.check_answer(b'', 0, 2)

    def test_model_problem(self):
        self.assertIn('empty', L.model_problem(''))
        self.assertIn('missing', L.model_problem('/nonexistent/x.mlmodelc'))
        with tempfile.TemporaryDirectory() as d:
            self.assertIn('not a compiled', L.model_problem(d))
            open(os.path.join(d, 'coremldata.bin'), 'wb').close()
            self.assertEqual(L.model_problem(d), '')

    def test_helper_args(self):
        a = L.helper_args('/m')
        self.assertNotIn('--no-depth', a)
        self.assertEqual(a[-2:], ['--model', '/m'])
        for f in ('--no-seg', '--no-faces', '--no-landmarks'):
            self.assertIn(f, a)

    def test_slice_center(self):
        self.assertEqual(L.slice_center(12.3, 0.4, 0), 0.4)
        self.assertEqual(L.slice_center(0, 1.7, 0), 1.0)
        self.assertAlmostEqual(L.slice_center(0.0, 0.4, 0.5), 0.4)
        self.assertGreater(L.slice_center(0.1, 0.4, 0.5), 0.4)  # sweeps nearer first
        for k in range(200):
            v = L.slice_center(k * 0.037, 0.3, 1.3)
            self.assertTrue(0.0 <= v <= 1.0)

    def test_tri(self):
        self.assertEqual(L.tri(0.0), 0.0)
        self.assertEqual(L.tri(0.5), 1.0)
        self.assertAlmostEqual(L.tri(1.25), 0.5)

    def test_modes(self):
        self.assertEqual(L.mode_index('outline'), 3)
        self.assertEqual(L.mode_index('nope'), 0)

    def test_fake_depth_scalar(self):
        bottom = sum(L.fake_depth(x / 10.0, 0.05, 0.0) for x in range(11))
        top = sum(L.fake_depth(x / 10.0, 0.95, 0.0) for x in range(11))
        self.assertGreater(bottom, top)
        self.assertGreater(L.fake_depth(0.75, 0.45, 0.0), 0.8)  # the blob at t = 0 is near

    def test_info_rows(self):
        rows = L.info_rows({'status': 'ok', 'range_lo': 0.123456, 'helper_pid': None})
        d = dict(rows[1:])
        self.assertEqual(rows[0], ('key', 'value'))
        self.assertEqual(d['status'], 'ok')
        self.assertEqual(d['range_lo'], '0.123')
        self.assertEqual(d['helper_pid'], '')
        self.assertEqual(d['answers'], '')


class ControllerTests(unittest.TestCase):
    def test_flow(self):
        c = L.Controller()
        self.assertTrue(c.want_request(0.0, True))
        self.assertFalse(c.want_request(0.0, False))
        c.sent_frame(0.0, 10)
        self.assertFalse(c.want_request(0.01, True))  # MIN_INTERVAL
        e = c.result(0.06, 10, 0.1, 0.9, 518, 392, 0.5)
        self.assertTrue(e['first'])
        self.assertEqual(e['sent_t'], 0.0)
        self.assertTrue(c.has_depth)
        self.assertEqual(c.status, 'ok')

    def test_stale_after_reset(self):
        c = L.Controller()
        c.sent_frame(0.0, 1)
        c.reset('source changed')
        self.assertIsNone(c.result(0.1, 1, 0, 1, 2, 2, 0.5))
        self.assertEqual(c.ignored, 1)
        self.assertIsNone(c.result(0.1, 99, 0, 1, 2, 2, 0.5))  # never sent
        self.assertEqual(c.ignored, 2)

    def test_not_ready_and_error_back_off(self):
        c = L.Controller()
        c.sent_frame(1.0, 5)
        c.not_ready(1.0, 5)
        self.assertEqual(c.status, 'loading model')
        self.assertFalse(c.want_request(1.4, True))
        self.assertTrue(c.want_request(1.51, True))
        c.sent_frame(2.0, 6)
        c.error(2.0, 6, 'model load failed: x')
        self.assertTrue(c.status.startswith('error: model load failed'))
        self.assertFalse(c.want_request(2.9, True))
        self.assertTrue(c.want_request(3.01, True))

    def test_bounded_bookkeeping(self):
        c = L.Controller()
        for i in range(30):
            c.sent_frame(i, i)
        self.assertEqual(len(c.sent), 8)
        self.assertEqual(min(c.sent), 22)

    def test_hold_then_pass_through(self):
        c = L.Controller()
        c.sent_frame(0.0, 1)
        c.result(0.05, 1, 0, 1, 2, 2, 0.5)
        self.assertTrue(c.showing(0.5, 1.0))
        self.assertFalse(c.showing(1.2, 1.0))
        self.assertIn('pass-through', c.status)
        self.assertFalse(c.has_depth)

    def test_dt_feeds_easing(self):
        c = L.Controller()
        c.sent_frame(0.0, 1)
        c.result(0.05, 1, 0.0, 1.0, 2, 2, 0.5)
        c.sent_frame(0.1, 2)
        e = c.result(0.15, 2, 1.0, 2.0, 2, 2, 0.5)
        self.assertFalse(e['first'])
        self.assertAlmostEqual(e['k'], L.ease_step(0.1, L.depth_tau(0.5)), places=6)


class Static(unittest.TestCase):
    FILES = ('depth_cam.py', 'depth_cam_logic.py', 'depth_cam_runtime.py')

    def test_ascii_and_compiles(self):
        for n in self.FILES:
            with open(os.path.join(B, n), 'rb') as f:
                src = f.read()
            src.decode('ascii')  # T-00a: TD reads these
            ast.parse(src, n)

    def test_par_names(self):
        names = []
        for page, pars in BLD._pages():
            for name, style, default, o in pars:
                self.assertRegex(name, r'^[A-Z][a-z0-9]+$', name)  # TD custom par naming
                names.append(name)
                if style == 'Menu':
                    self.assertIn(default, o['names'])
                    self.assertEqual(len(o['names']), len(o['labels']))
        self.assertEqual(len(names), len(set(names)))
        pages = [p for p, _ in BLD._pages()]
        for p in BLD.PANEL_PAGES:
            self.assertIn(p, pages)
        mode = [o for p, pars in BLD._pages() for n, s, d, o in pars if n == 'Mode'][0]
        self.assertEqual(tuple(mode['names']), L.MODES)

    def test_runtime_reads_pars_that_exist(self):
        names = {n for _, pars in BLD._pages() for n, s, d, o in pars}
        src = _src('depth_cam_runtime.py')
        used = set(re.findall(r"\bp\.([A-Z][a-z0-9]+)\b", src)) | set(re.findall(r"comp\.par\.([A-Z][a-z0-9]+)", src))
        used |= set(re.findall(r"\('(Status|Latency|Rate|Havedepth)'", src))
        self.assertTrue(used)
        self.assertTrue(used <= names, used - names)

    def test_shader_uniforms_match_builder(self):
        decl = re.findall(r'uniform vec4 (u\w+);', BLD.SHADER)
        self.assertEqual(len(decl), 6)
        src = _src('depth_cam.py')
        bound = re.findall(r"\('(u[A-Z]\w*)', \[", src)
        self.assertEqual(sorted(decl), sorted(bound))
        self.assertNotIn('#version', BLD.SHADER)       # TD adds its own header
        self.assertEqual(BLD.SHADER.count('void main'), 1)  # single pass (T-46)

    def test_builder_expressions_name_existing_pars(self):
        names = {n for _, pars in BLD._pages() for n, s, d, o in pars}
        rgb = {n for _, pars in BLD._pages() for n, s, d, o in pars if s == 'RGB'}
        src = _src('depth_cam.py')
        for ref in set(re.findall(r"P\.format\('([A-Za-z0-9]+)'\)", src)) | set(re.findall(r"parent\(\)\.par\.([A-Za-z0-9]+)", src)):
            base = ref[:-1] if ref[:-1] in rgb else ref
            self.assertIn(base, names, ref)

    def test_readback_is_delayed(self):
        src = _src('depth_cam_runtime.py')
        calls = re.findall(r'numpyArray\(([^)]*)\)', src)
        self.assertTrue(calls)
        for a in calls:
            self.assertIn('delayed=True', a)  # T-74
        self.assertNotIn('cook(force=True)\n    a = ', src)


if __name__ == '__main__':
    unittest.main()


# ------------------------------------------------------------------ runtime against a fake TD (no TD, no helper)
class _Par(object):
    def __init__(self, v):
        self.val = v

    def eval(self):
        return self.val


class _Pars(object):
    pass


class _Mod(object):
    def __init__(self, module):
        self.module = module


class _ScriptTop(object):
    def __init__(self, comp):
        self.comp, self.uploads = comp, []

    def cook(self, force=False):
        self.comp.op('runtime').module.cook_depth(self.comp, self)

    def copyNumpyArray(self, a):
        self.uploads.append(a.copy())


class _Table(object):
    def __init__(self):
        self.rows = []

    def clear(self):
        self.rows = []

    def appendRow(self, r):
        self.rows.append(r)


class FakeComp(object):
    """Just enough of a TD COMP for depth_cam_runtime: pars, op() lookups, id."""
    _ids = [1000]

    def __init__(self, runtime, client_mod, **pars):
        FakeComp._ids[0] += 1
        self.id = FakeComp._ids[0]
        self.par = _Pars()
        defaults = {n: d for _, ps in BLD._pages() for n, s, d, o in ps if s not in ('RGB', 'Pulse')}
        defaults.update(pars)
        for k, v in defaults.items():
            setattr(self.par, k, _Par(v))
        self.ops = {'depth_cam_logic': _Mod(L), 'runtime': _Mod(runtime), 'vision_client': _Mod(client_mod),
                    'depth_field': _ScriptTop(self), 'info': _Table()}

    def op(self, name):
        return self.ops.get(name)


def _load_runtime():
    import importlib.util
    spec = importlib.util.spec_from_file_location('depth_cam_runtime_t', os.path.join(B, 'depth_cam_runtime.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    cspec = importlib.util.spec_from_file_location(
        'camera_bridge_t', os.path.join(os.path.dirname(HERE), 'helpers', 'vision_bridge', 'lib', 'camera_bridge.py'))
    cb = importlib.util.module_from_spec(cspec)
    cspec.loader.exec_module(cb)
    return m, cb


@unittest.skipIf(np is None, 'numpy missing')
class RuntimeFakeTD(unittest.TestCase):
    def setUp(self):
        self.rt, self.cb = _load_runtime()

    def test_inactive_does_nothing(self):
        c = FakeComp(self.rt, self.cb)
        self.rt.frame_start(c)
        self.rt.frame_end(c)
        self.assertIsNone(self.rt.STATE[c.id]['client'])
        self.assertEqual(c.par.Havedepth.val, 0)

    def test_fake_depth_uploads_and_sets_have(self):
        c = FakeComp(self.rt, self.cb, Active=True, Fakedepth=True)
        for _ in range(3):
            self.rt.frame_start(c)
            self.rt.frame_end(c)
        up = c.ops['depth_field'].uploads
        self.assertEqual(len(up), 3)
        self.assertEqual(up[-1].shape, (L.FAKE_SIZE[1], L.FAKE_SIZE[0], 1))
        self.assertEqual(up[-1].dtype, np.float32)
        self.assertEqual(c.par.Havedepth.val, 1)
        self.assertIn('fake', c.par.Status.val)
        self.assertIsNone(self.rt.STATE[c.id]['client'])  # no helper spawned
        c.par.Active.val = False
        self.rt.frame_start(c)
        self.assertEqual(c.par.Havedepth.val, 0)
        self.assertEqual(up[-1].shape, (2, 2, 1))  # black map after stop
        self.assertTrue(float(up[-1].max()) == 0.0)

    def test_model_missing_is_pass_through_without_spawn(self):
        c = FakeComp(self.rt, self.cb, Active=True, Model='/nonexistent/m.mlmodelc', Helper='/nonexistent/helper')
        self.rt.frame_start(c)
        self.rt.frame_end(c)
        self.assertIn('model missing', c.par.Status.val)
        self.assertEqual(c.par.Havedepth.val, 0)
        self.assertIsNone(self.rt.STATE[c.id]['client'])

    def test_helper_missing_status(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, 'coremldata.bin'), 'wb').close()
            c = FakeComp(self.rt, self.cb, Active=True, Model=d, Helper=os.path.join(d, 'no_helper'))
            self.rt.frame_start(c)
            self.rt._st(c)['report_t'] = 0.0
            self.rt.frame_start(c)
            self.assertIn('helper missing', c.par.Status.val)
            self.assertEqual(c.par.Havedepth.val, 0)
            self.rt.stop(c)

    def test_upload_falls_back_to_rgba(self):
        c = FakeComp(self.rt, self.cb)
        st = c.ops['depth_field']
        calls = []

        def picky(a):
            calls.append(a.shape)
            if a.shape[2] != 4:
                raise ValueError('1 channel refused')
        st.copyNumpyArray = picky
        st.cook()
        st.cook()
        self.assertEqual(calls, [(2, 2, 1), (2, 2, 4), (2, 2, 4)])
