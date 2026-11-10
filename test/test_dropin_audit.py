"""Offline tests for tools/dropin_audit.py (28 Oct 2026, drop-in COMPs): path finding, classes, contexts, the
self-reference rewrite (relative, idempotent), OP-par relative paths, escapes. No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_dropin*.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'tools'))
import dropin_audit as D  # noqa: E402

C = '/project1/lab/PX_pointfx'


class Classes(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(D.classify(C + '/eng', C), 'self')
        self.assertEqual(D.classify(C, C), 'self')
        self.assertEqual(D.classify('/project1/lab/PX_pointfx1/eng', C), 'scene')       # not a prefix match
        self.assertEqual(D.classify('/project1/effectors/eff_rows', C), 'shared')
        self.assertEqual(D.classify('/project1/lab/AU_features/out1', C), 'shared')
        self.assertEqual(D.classify('/project1/hotkeys', C), 'shared')
        self.assertEqual(D.classify('/project1/lab/FX_palette_map', C), 'shared')
        self.assertEqual(D.classify('/project1/lab/GEN_points/out1', C), 'scene')
        self.assertEqual(D.classify('/sys/drag', C), 'builtin')
        self.assertEqual(D.classify('/local/time', C), 'builtin')
        self.assertEqual(D.classify('/jazib_mcp/handlers', C), 'unknown')

    def test_source_path_is_self(self):
        drop = '/project1/dropin/host_3/PX_pointfx_drop'
        self.assertEqual(D.classify(C + '/eng', drop, (C,)), 'self')
        self.assertEqual(D.self_root(C + '/eng', drop, (C,)), C)

    def test_clean_path_and_fs(self):
        self.assertEqual(D.clean_path('/project1/lab/%s/x'), '/project1/lab')
        self.assertEqual(D.clean_path('/project1/lab/'), '/project1/lab')
        self.assertTrue(D.is_fs_path('~/x'))
        self.assertTrue(D.is_fs_path('/Applications/TouchDesigner 2.app'))
        self.assertFalse(D.is_fs_path('/project1/lab/X'))


class Finding(unittest.TestCase):
    def test_contexts(self):
        txt = ("a = op('%s/eng')\n"
               "# see op('%s/eng')\n"
               "p.expr = \"op('%s/x')['tx']\"\n"
               "def f():\n    '''docs: '%s' '''\n    return '/Users/me/file.ply'\n") % (C, C, C, C)
        hits = D.find_paths(txt)
        self.assertEqual([h['ctx'] for h in hits], ['code', 'comment', 'embedded', 'embedded'])
        self.assertEqual(hits[0]['path'], C + '/eng')

    def test_suffix_is_not_a_path(self):
        self.assertEqual(D.find_paths("op(c.path + '/hot_pts')\nx = me.parent().path + '/geo/'"), [])

    def test_glsl_text(self):
        hits = D.find_paths('// op("/project1/x")\nvec4 a;\n', python=False)
        self.assertEqual([h['ctx'] for h in hits], ['comment'])

    def test_escapes(self):
        self.assertEqual(D.escapes("parent(2).par.x", 1), ['parent(2)'])
        self.assertEqual(D.escapes("me.parent(1).par.x", 1), [])
        self.assertEqual(D.escapes("op('../../effectors')", 1), ["op('../../"])
        self.assertEqual(D.escapes("op('../x')", 1), [])


class Rewrite(unittest.TestCase):
    def test_op_call(self):
        new, done = D.rewrite_self("op('%s/eng')['tx']" % C, C, (), 1)
        self.assertEqual(new, "me.parent().op('eng')['tx']")
        self.assertEqual(len(done), 1)

    def test_comp_itself(self):
        self.assertEqual(D.rewrite_self("op('%s').par.Size" % C, C, (), 2)[0], 'me.parent(2).par.Size')
        self.assertEqual(D.rewrite_self("op('%s').par.Size" % C, C, (), 0)[0], 'me.par.Size')

    def test_bare_string(self):
        new, _ = D.rewrite_self("P = '%s/geo'\nx = op(P)" % C, C, (), 1)
        self.assertEqual(new, "P = (me.parent().path + '/geo')\nx = op(P)")

    def test_method_op_and_placeholders(self):
        self.assertEqual(D.rewrite_self("root.op('%s/a')" % C, C, (), 1)[0], "root.op((me.parent().path + '/a'))")
        self.assertEqual(D.rewrite_self("'%s/%%s' %% n" % C, C, (), 1)[0], "(me.parent().path + '/%s') % n")

    def test_leaves_others(self):
        src = "op('/project1/effectors/eff_rows')  # op('%s/x')\ns = \"op('%s/y')\"" % (C, C)
        new, done = D.rewrite_self(src, C, (), 1)
        self.assertEqual(new, src)
        self.assertEqual(done, [])

    def test_source_root(self):
        drop = '/project1/dropin/host_2/PX_drop'
        self.assertEqual(D.rewrite_self("op('%s/eng')" % C, drop, (C,), 1)[0], "me.parent().op('eng')")

    def test_idempotent(self):
        once = D.rewrite_self("op('%s/eng')['tx'] + op('%s').par.A" % (C, C), C, (), 3)[0]
        again, done = D.rewrite_self(once, C, (), 3)
        self.assertEqual(again, once)
        self.assertEqual(done, [])
        self.assertFalse([h for h in D.find_paths(once) if D.self_root(h['path'], C) and h['ctx'] == 'code'])


class OpPar(unittest.TestCase):
    def test_rel_op_path(self):
        self.assertEqual(D.rel_op_path(C + '/controls', C), './controls')
        self.assertEqual(D.rel_op_path(C + '/controls', C + '/controls_window'), '../controls')
        self.assertEqual(D.rel_op_path(C, C + '/a/b'), '../..')
        self.assertEqual(D.rel_op_path(C + '/a/b/c', C + '/a/b/c'), '.')
        self.assertEqual(D.rel_op_path(C + '/x/y', C + '/a/b'), '../../x/y')

    def test_candidates(self):
        self.assertEqual(D.op_par_candidates([C + '/x/controls'], C + '/x/controls_window'), ['controls', '../controls'])
        self.assertEqual(D.op_par_candidates([C + '/x'], C + '/x/pulses'), ['..'])
        self.assertEqual(D.op_par_candidates([C + '/a', C + '/b'], C + '/w'), ['a b', '../a ../b'])

    def test_links_par_name(self):
        self.assertEqual(D.links_par_name('effectors'), 'Linkeffectors')
        self.assertEqual(D.links_par_name('AU_features'), 'Linkaufeatures')


class InGuard(unittest.TestCase):
    def test_guard(self):
        g = D.guard_in_chan("op('audio_in')['low']", ['audio_in'], 0.5)
        self.assertEqual(g, "(lambda ch: ch.eval() if ch is not None else 0.5)(op('audio_in')['low'])")
        ch = type('Ch', (), {'eval': lambda self: 0.25})()
        self.assertEqual(eval(g, {'op': lambda n: {'low': ch}}), 0.25)
        empty = type('In', (), {'__getitem__': lambda self, k: None})()       # an unwired In CHOP: no channel
        self.assertEqual(eval(g, {'op': lambda n: empty}), 0.5)

    def test_not_guarded(self):
        self.assertIsNone(D.guard_in_chan("op('audio_in')['low'] * 2", ['audio_in'], 0))
        self.assertIsNone(D.guard_in_chan("op('noise1')['chan1']", ['audio_in'], 0))
        self.assertIsNone(D.guard_in_chan("parent().par.X", ['audio_in'], 0))


class StaleFrames(unittest.TestCase):
    E = "1.0 if absTime.frame - parent().fetch('jz_reset', -99, search=False) < 3 else 0.0"

    def test_guard(self):
        g = D.guard_stale_frames(self.E)
        self.assertEqual(g, "1.0 if absTime.frame - (lambda k, f: k if k <= f else -99)(parent().fetch('jz_reset', -99, "
                            "search=False), absTime.frame) < 3 else 0.0")
        self.assertIsNone(D.guard_stale_frames(g))                    # idempotent

    def test_semantics(self):
        g = D.guard_stale_frames(self.E)
        class P(object):
            def __init__(self, k):
                self.k = k

            def fetch(self, *a, **kw):
                return self.k
        T = type('T', (), {})
        for frame, stored, want in ((100, 99, 1.0), (100, 50, 0.0), (100, 900000, 0.0), (100, -99, 0.0)):
            T.frame = frame
            self.assertEqual(eval(g, {'absTime': T, 'parent': lambda: P(stored)}), want, (frame, stored))

    def test_untouched(self):
        self.assertIsNone(D.guard_stale_frames("parent().par.Size"))
        self.assertIsNone(D.guard_stale_frames("absTime.frame % 2048"))


class Summary(unittest.TestCase):
    def test_summarize(self):
        s = D.summarize([{'cls': 'self', 'ctx': 'code'}, {'cls': 'shared', 'ctx': 'code'},
                         {'cls': 'self', 'ctx': 'comment'}, {'cls': 'scene', 'ctx': 'embedded'}])
        self.assertEqual((s['self'], s['shared'], s['scene'], s['comment'], s['embedded']), (1, 1, 0, 1, 1))


if __name__ == '__main__':
    unittest.main()
