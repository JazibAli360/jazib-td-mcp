"""Offline drop-in checks of the builders (28 Oct 2026, docs/builds/DROPIN_AUDIT_28OCT.md): what a builder writes into
a COMP must stay relative, so rebuilds and new copies stay drop-ins. No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_dropin*.py'"""
import glob
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
B = os.path.join(REPO, 'builders')
sys.path.insert(0, os.path.join(REPO, 'tools'))
sys.path.insert(0, B)
import dropin_audit as D  # noqa: E402
import zkit_logic as ZL  # noqa: E402

SKIP = ('fx_venue_logic.py', 'review_tour.py', 'review_tour_rt.py')      # untracked / the review tool (MCP-only)
# OP-par defaults and menu roots that name a scene or shared system ON PURPOSE (missing-safe, overridable)
ALLOWED = {
    ('effectors_rt.py', '/project1'), ('px_rt.py', '/project1'), ('show_rig_logic.py', '/project1/show_rig'),
    ('fx_film_dof_logic.py', '/project1/lab/DC_depth_cam/depth'), ('particles_logic.py', '/project1/lab/AC_audio/out_ctl'),
    ('px_logic.py', '/project1/lab/FG_fps_governor/out1'), ('px_logic.py', '/project1/lab/AU_features'),
    ('show_rig_logic.py', '/project1/lab/FX_palette_map'), ('show_rig_logic.py', '/project1/lab/FX_motion_trail'),
    ('show_rig_logic.py', '/project1/lab/FX_strobe'), ('zctl_ext.py', '/project1/show/tools/autoUI'),
}


def _files(pat='*.py'):
    return [f for f in sorted(glob.glob(os.path.join(B, pat))) if os.path.basename(f) not in SKIP]


def _rd(f):
    with open(f) as fh:
        return fh.read()


class OpParsRelative(unittest.TestCase):
    def test_no_op_par_set_from_a_path_string(self):
        """`x.par.op = c.path` stores an ABSOLUTE path (a dropped copy then watches the original); `= c` (an OP) or
        `= '..'` stores a relative one (seen in the expanded library .tox files)."""
        bad = []
        pat = re.compile(r"\.par\.(op|ops|winop|chop|chops|top|sop|dat|panels|array\dchop)\s*=\s*[A-Za-z_]+\.path\b"
                         r"|\bop\s*=\s*[A-Za-z_]+\.path\b")
        for f in _files():
            for i, line in enumerate(_rd(f).splitlines(), 1):
                if pat.search(line) and not line.lstrip().startswith('#') and '# dropin: scene ref' not in line:
                    bad.append('%s:%d %s' % (os.path.basename(f), i, line.strip()))
        self.assertEqual(bad, [])

    def test_mx_vertex_cache_paths_are_relative(self):
        src = _rd(os.path.join(B, 'prox_mat.py'))
        self.assertIn("_try(ch, 'sop', _relc(c, s)", src)
        self.assertIn("rows.append([str(k), _relc(c, geo)", src)


class RuntimeTexts(unittest.TestCase):
    def test_no_new_absolute_lab_paths(self):
        """Runtime / logic texts copied into COMPs name no /project1 op in code, except the allowed defaults."""
        bad = []
        for f in _files('*_rt.py') + _files('*_logic.py') + _files('*_ext.py'):
            t = _rd(f)
            for h in D.find_paths(t):
                if h['ctx'] != 'code' or not h['path'].startswith('/project1'):
                    continue
                if h['path'].startswith('/project1/effectors'):
                    continue                                   # the shared list's contract path (missing-safe)
                if (os.path.basename(f), h['path']) not in ALLOWED:
                    bad.append('%s:%d %s' % (os.path.basename(f), h['line'], h['path']))
        self.assertEqual(bad, [])

    def test_mcp_handlers_fallbacks_are_guarded(self):
        """op('/jazib_mcp/handlers') exists only in a TD with the MCP: runtime code checks it before use."""
        bad = []
        for f in _files('*_rt.py') + _files('*_ext.py') + [os.path.join(B, 'timeline_record.py')]:
            for i, line in enumerate(_rd(f).splitlines(), 1):
                if re.search(r"op\('/jazib_mcp/handlers'\)\.module", line):
                    bad.append('%s:%d' % (os.path.basename(f), i))
        self.assertEqual(bad, [])

    def test_fx_film_depth_through_an_op_par(self):
        dof = _rd(os.path.join(B, 'fx_film_dof.py'))
        self.assertIn("('Depthop', 'COMP', ''", dof)
        self.assertIn("getattr(parent().par, 'Depthop', None)", dof)
        ns = {}
        src = dof[dof.index('DCP = ('):dof.index('BROKEN_DCP')]
        exec(src, ns)
        class Par(object):                       # an EMPTY TD Par is falsy (bool = its value): the trap of the 1st form
            def __init__(self, v):
                self.v = v

            def eval(self):
                return self.v

            def __bool__(self):
                return bool(self.v)
        class Cam(object):
            def op(self, n):
                return 'cam/' + n
        for depthop, want in ((None, 'lab'), (Par(None), 'lab'), (Par(Cam()), 'cam/depth')):
            pars = type('P', (), {})()
            if depthop is not None:
                pars.Depthop = depthop
            par_ = type('C', (), {'par': pars})()
            got = eval(ns['DCP'], {'parent': lambda: par_, 'op': lambda p: 'lab'})
            self.assertEqual(got, want)


class StaleTimes(unittest.TestCase):
    def test_reset_now_ignores_a_future_clear(self):
        import motion_trail_logic as ML
        self.assertEqual(ML.reset_now(10, 9, source='live'), 1)
        self.assertEqual(ML.reset_now(10, 500000, source='live'), 0)   # stored by another session

    def test_builders_guard_stored_frames(self):
        for f in ('pop_collide_logic.py', 'pop_collide.py', 'person_mask.py', 'motion_trail.py'):
            t = _rd(os.path.join(B, f))
            self.assertNotRegex(t, r"(?<!\)\()parent\(\)\.fetch\('jz_\w+', -99, search=False\)(?!, absTime)", f)
            self.assertIsNone(D.guard_stale_frames(t), f)

    def test_urdu_reanchors_a_future_start(self):
        self.assertIn("if elapsed < 0.0:", _rd(os.path.join(B, 'urdu_type_rt.py')))


class FluidIdle(unittest.TestCase):
    def test_idle_note(self):
        import fluid2d_logic as FL
        p = dict(FL.ENGINE_DEFAULTS)
        self.assertEqual(FL.idle_note(p, {}), FL.IDLE_NOTE)
        self.assertEqual(FL.idle_note(p, {'srcwired': 1}), '')
        self.assertEqual(FL.idle_note(p, {}, effon=True), '')
        self.assertEqual(FL.idle_note(dict(p, bpmmode='internal'), {}), '')
        self.assertEqual(FL.idle_note(p, {'points': [(0, 0, 0)]}), '')

    def test_builder_adds_status(self):
        t = _rd(os.path.join(B, 'fluid2d.py'))
        self.assertIn('status_par(c)', t)
        self.assertIn("L.idle_note(p, inp,", t)


class Zkit(unittest.TestCase):
    def test_target_rel(self):
        self.assertEqual(ZL.target_rel('/p/lab/X/controls', '/p/lab/X'), '..')
        self.assertEqual(ZL.target_rel('/p/lab/X/controls/params', '/p/lab/X'), '../..')
        self.assertEqual(ZL.target_rel('/elsewhere/controls', '/p/lab/X'), '/p/lab/X')

    def test_winop_rel(self):
        self.assertEqual(ZL.winop_rel('/p/X/controls_window', '/p/X/controls'), 'controls')
        self.assertEqual(ZL.winop_rel('/p/X/controls_window', '/p/X/controls/params'), 'controls/params')
        self.assertTrue(ZL.is_abs('/p/X') and not ZL.is_abs('..'))

    def test_builder_writes_relative_and_reads_both(self):
        zk = _rd(os.path.join(B, 'zkit.py'))
        rt = _rd(os.path.join(B, 'zkit_rt.py'))
        self.assertIn("('target', zl['target_rel'](panel.path, c.path))", zk)
        self.assertIn("zl['winop_rel'](win.path, wop.path)", zk)
        self.assertNotIn("('target', c.path)", zk)
        self.assertIn('_cfg_target(t).path == c.path', zk)            # refresh compares the resolved op
        self.assertIn('_zk_owner(t.parent()).path == c.path', zk)     # a copy's stale absolute target: owner wins
        self.assertIn("op(v) if v.startswith('/') else P.op(v)", rt)  # old absolute panels keep working
        self.assertIn('P.op(v)', rt)                                  # dropin_fix keys on this marker


if __name__ == '__main__':
    unittest.main()
