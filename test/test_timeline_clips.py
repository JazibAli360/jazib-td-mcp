"""Offline tests for TL_timeline phase 2 (clips track): builders/timeline_clips_logic.py, the generated TD code
(compiles; phase-1 hook present) and tools/timeline_media.py (ffprobe/ffmpeg run only when installed). No TD needed.

Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_timeline_clips.py'
"""
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'builders'))
import timeline_clips_logic as L  # noqa: E402

HEAD = L.CLIP_HEAD


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def clip(cid, track, start, dur, src='a.mp4', in_=0.0, speed=1.0, fade=0.0, proxy='', enabled=True, row=0):
    return {'id': cid, 'track': track, 'start': start, 'dur': dur, 'src': src, 'in': in_, 'speed': speed,
            'fade': fade, 'proxy': proxy, 'enabled': enabled, 'row': row}


class Table(unittest.TestCase):
    def test_parse_and_skip(self):
        rows = [HEAD,
                ['a', '0', '0', '4', 'x.mp4', '1', '1', '0.5', '', '1'],
                ['', '0', '0', '4', 'x.mp4', '', '', '', '', ''],        # no id
                ['b', '1', '2', '0', 'y.mp4', '', '', '', '', ''],       # dur 0
                ['c', '-3', '2', '2', 'y.mp4', '', '', '', '', 'off'],   # track clamps, disabled
                ['a', '0', '9', '1', 'z.mp4', '', '', '', '', '']]       # duplicate id
        cl = L.parse_clips(rows)
        self.assertEqual([c['id'] for c in cl], ['a', 'c'])
        self.assertEqual(cl[0]['in'], 1.0)
        self.assertEqual(cl[0]['fade'], 0.5)
        self.assertEqual(cl[1]['track'], 0)
        self.assertEqual(cl[1]['speed'], 1.0)      # empty speed = 1
        self.assertFalse(cl[1]['enabled'])
        self.assertEqual(L.parse_clips([]), [])
        self.assertEqual(L.parse_clips([['name', 'x']]), [])

    def test_any_column_order_and_roundtrip(self):
        rows = [['src', 'id', 'dur', 'start'], ['m.mp4', 'k', '3', '1.5']]
        c = L.parse_clips(rows)[0]
        self.assertEqual((c['id'], c['start'], c['dur'], c['speed']), ('k', 1.5, 3.0, 1.0))
        back = L.parse_clips(L.clips_to_rows([c]))
        self.assertEqual({k: v for k, v in back[0].items() if k != 'row'},
                         {k: v for k, v in c.items() if k != 'row'})

    def test_speed_zero_kept(self):
        c = L.parse_clips([HEAD, ['f', '0', '0', '2', 'x', '3', '0', '0', '', '1']])[0]
        self.assertEqual(c['speed'], 0.0)
        self.assertEqual(L.source_index(c, 1.5, 30), 90)   # freeze frame at in


class Weights(unittest.TestCase):
    def test_hard_cut_and_edges(self):
        a = clip('a', 0, 0, 4)
        cl = [a]
        self.assertEqual(L.clip_weight(a, -0.1, cl), 0.0)
        self.assertEqual(L.clip_weight(a, 0.0, cl), 1.0)
        self.assertEqual(L.clip_weight(a, 3.99, cl), 1.0)
        self.assertEqual(L.clip_weight(a, 4.0, cl), 0.0)   # end is exclusive

    def test_fade_in_out(self):
        a = clip('a', 0, 0, 4, fade=1.0)
        self.assertAlmostEqual(L.clip_weight(a, 0.25, [a]), 0.25)
        self.assertAlmostEqual(L.clip_weight(a, 2.0, [a]), 1.0)
        self.assertAlmostEqual(L.clip_weight(a, 3.5, [a]), 0.5)

    def test_auto_crossfade_midpoint_is_mean(self):
        a, b = clip('a', 0, 0, 6, fade=0.5), clip('b', 0, 5, 5, fade=0.25)
        cl = [a, b]
        self.assertEqual(L.fade_lengths(a, cl), (0.5, 0.0))      # covered by b: no fade-out
        self.assertEqual(L.fade_lengths(b, cl), (1.0, 0.25))     # overlap 1 s wins over its own fade
        act = L.active_clips(cl, 5.5)
        self.assertEqual([(c['id'], round(w, 6)) for c, w in act], [('a', 1.0), ('b', 0.5)])
        A, B = (0.8, 0.2, 0.1, 1.0), (0.1, 0.3, 0.9, 1.0)
        px = L.composite_pixel([(A, act[0][1]), (B, act[1][1])], 'over')
        for i in range(4):
            self.assertAlmostEqual(px[i], (A[i] + B[i]) / 2)

    def test_other_track_does_not_crossfade(self):
        a, b = clip('a', 0, 0, 6), clip('b', 1, 5, 5)
        self.assertEqual(L.fade_lengths(a, [a, b]), (0.0, 0.0))
        self.assertEqual([c['id'] for c, _ in L.active_clips([b, a], 5.5)], ['a', 'b'])   # track 0 below

    def test_disabled_invisible(self):
        a = clip('a', 0, 0, 4, enabled=False)
        self.assertEqual(L.active_clips([a], 1), [])
        self.assertEqual(L.upcoming_clips([a], -0.2, 1), [])

    def test_upcoming(self):
        cl = [clip('a', 0, 2, 1), clip('b', 1, 1.2, 1), clip('c', 0, 9, 1)]
        self.assertEqual([c['id'] for c in L.upcoming_clips(cl, 1.0, 1.5)], ['b', 'a'])
        self.assertEqual(L.upcoming_clips(cl, 1.0, 0), [])


class SourceFrames(unittest.TestCase):
    def test_index(self):
        c = clip('a', 0, 10, 5, in_=2.0)
        self.assertEqual(L.source_index(c, 10.0, 30), 60)
        self.assertEqual(L.source_index(c, 11.0, 30), 90)
        self.assertEqual(L.source_index(c, 10 + 1 / 30.0, 30), 61)       # float noise lands on the frame
        self.assertEqual(L.source_index(c, 30.0, 30, frames=300), 299)    # clamped (holds last frame)
        self.assertEqual(L.source_index(c, 0.0, 30), 0)                   # never negative
        self.assertEqual(L.source_index(c, 11.0, 0), 0)

    def test_speed_and_reverse(self):
        c = clip('a', 0, 0, 4, in_=1.0, speed=2.0)
        self.assertAlmostEqual(L.source_time(c, 1.5), 4.0)
        r = clip('r', 0, 0, 4, in_=4.0, speed=-1.0)
        self.assertEqual(L.source_index(r, 1.0, 25), 75)

    def test_span(self):
        c = clip('a', 0, 0, 5, in_=6.0)
        self.assertFalse(L.source_span_ok(c, {'dur': 10.0}))
        self.assertTrue(L.source_span_ok(clip('b', 0, 0, 4, in_=6.0), {'dur': 10.0}))
        self.assertTrue(L.source_span_ok(c, {}))


class Players(unittest.TestCase):
    def test_stable(self):
        a = L.assign_players(['x', 'y'], {}, 2)
        self.assertEqual(a, {'x': 0, 'y': 1})
        b = L.assign_players(['z', 'y'], a, 2)       # y keeps its player (no reload), z takes the free one
        self.assertEqual(b, {'y': 1, 'z': 0})
        c = L.assign_players(['y', 'z', 'q'], b, 2)  # q dropped (lowest priority)
        self.assertEqual(c, {'y': 1, 'z': 0})
        self.assertEqual(L.assign_players(['a', 'a', 'b'], {}, 9), {'a': 0, 'b': 1})   # capped at 4 + dedup
        self.assertEqual(L.assign_players(['a'], {'a': 3}, 2), {'a': 0})                # slot out of range

    def test_plan_crossfade_and_preload(self):
        root = '/r'
        cl = [clip('a', 0, 0, 6, src='a.mp4', in_=2.0), clip('b', 0, 5, 5, src='b.mp4'),
              clip('c', 0, 10, 2, src='c.mp4')]
        media = {'/r/a.mp4': {'fps': 30, 'frames': 300}, '/r/b.mp4': {'fps': 25, 'frames': 200},
                 '/r/c.mp4': {'fps': 30, 'frames': 60, 'proxy': '/p/c_proxy.mp4'}}
        p = L.plan(cl, 5.5, 2, {}, media, preroll=0.5, root=root)
        s = dict((d['id'], d) for d in p['slots'] if d)
        self.assertEqual(p['active'], ['a', 'b'])
        self.assertEqual((s['a']['rank'], s['b']['rank']), (0, 1))
        self.assertEqual(s['a']['index'], 225)        # (2 + 5.5) * 30
        self.assertEqual(s['b']['index'], 12)         # 0.5 * 25 = 12.5 -> 12
        self.assertAlmostEqual(s['b']['weight'], 0.5)
        self.assertEqual(s['a']['file'], '/r/a.mp4')
        # 9.7: only b visible, c preloads in the free player at its in point, weight 0
        p2 = L.plan(cl, 9.7, 2, p['assign'], media, preroll=0.5, root=root)
        s2 = dict((d['id'], d) for d in p2['slots'] if d)
        self.assertEqual(p2['assign']['b'], p['assign']['b'])
        self.assertEqual((s2['c']['weight'], s2['c']['rank'], s2['c']['index']), (0.0, -1, 0))
        self.assertEqual(p2['dropped'], [])

    def test_plan_drops_bottom_when_short(self):
        cl = [clip('a', 0, 0, 4), clip('b', 1, 0, 4), clip('c', 2, 0, 4)]
        p = L.plan(cl, 1.0, 2, {}, {})
        self.assertEqual(sorted(p['assign']), ['b', 'c'])   # the top two keep players
        self.assertEqual(p['dropped'], ['a'])
        ranks = dict((d['id'], d['rank']) for d in p['slots'])
        self.assertEqual(ranks, {'b': 0, 'c': 1})

    def test_plan_fps_fallback_and_empty(self):
        p = L.plan([clip('a', 0, 0, 4)], 1.0, 1, {}, {}, fps_default=60)
        self.assertEqual(p['slots'][0]['index'], 60)
        self.assertEqual(L.plan([], 1.0, 2, {}, {})['slots'], [None, None])

    def test_proxy_modes(self):
        self.assertFalse(L.use_proxy('proxy', False, True))
        self.assertTrue(L.use_proxy('proxy', True, False))
        self.assertTrue(L.use_proxy('auto', True, True))
        self.assertFalse(L.use_proxy('auto', True, False))
        self.assertFalse(L.use_proxy('full', True, True))
        media = {'/r/c.mp4': {'fps': 30, 'frames': 60, 'proxy': '/p/c_proxy.mp4'}}
        c = clip('c', 0, 0, 2, src='c.mp4')
        p = L.plan([c], 1.0, 1, {}, media, sourcemode='auto', scrubbing=True, root='/r')
        self.assertEqual((p['slots'][0]['file'], p['slots'][0]['proxy']), ('/p/c_proxy.mp4', True))
        self.assertEqual(L.proxy_for(dict(c, proxy='none'), '/r', media), '')
        self.assertEqual(L.proxy_for(dict(c, proxy='px/c.mp4'), '/r', media), '/r/px/c.mp4')


class Paths(unittest.TestCase):
    def test_paths(self):
        self.assertEqual(L.resolve_path('media/a.mp4', '/repo'), '/repo/media/a.mp4')
        self.assertEqual(L.resolve_path('/abs/a.mp4', '/repo'), '/abs/a.mp4')
        k = L.media_key('/repo/media/a.mp4')
        self.assertEqual(len(k), 16)
        self.assertEqual(L.media_info_path('/repo/media/a.mp4', '/c'), '/c/%s.json' % k)
        self.assertEqual(L.proxy_path('/repo/media/a.mp4', '/p'), '/p/%s/a_proxy.mp4' % k)
        self.assertNotEqual(L.media_key('/x/a.mp4'), k)

    def test_proxy_cmd_all_intra(self):
        cmd = L.proxy_cmd('in.mov', 'out.mp4', 'ffmpeg', 0.5, 20)
        s = ' '.join(cmd)
        for part in ('-g 1', '-bf 0', '-c:v libx264', '-an', 'scale=trunc(iw*0.5/2)*2:trunc(ih*0.5/2)*2'):
            self.assertIn(part, s)
        self.assertNotIn('-r', cmd)        # same fps as the source
        self.assertEqual(cmd[-1], 'out.mp4')

    def test_parse_probe(self):
        j = json.dumps({'streams': [{'width': 540, 'height': 960, 'r_frame_rate': '30/1',
                                     'avg_frame_rate': '30000/1001', 'nb_frames': '300', 'duration': '10.01'}]})
        d = L.parse_probe(j)
        self.assertAlmostEqual(d['fps'], 29.97, places=2)
        self.assertEqual((d['frames'], d['w'], d['h']), (300, 540, 960))
        d2 = L.parse_probe(json.dumps({'streams': [{'r_frame_rate': '25/1', 'nb_read_packets': '50'}]}))
        self.assertEqual((d2['frames'], d2['dur']), (50, 2.0))
        d3 = L.parse_probe(json.dumps({'streams': [{'r_frame_rate': '25/1'}], 'format': {'duration': '4'}}))
        self.assertEqual(d3['frames'], 100)
        self.assertEqual(L.parse_probe('not json'), {})


class FitBlend(unittest.TestCase):
    def test_fit(self):
        self.assertEqual(L.fit_scale(540, 960, 1080, 1920, 'fit'), (1.0, 1.0))      # same aspect
        sx, sy = L.fit_scale(1920, 1080, 1080, 1920, 'fit')                        # landscape in portrait
        self.assertAlmostEqual(sx, 1.0)
        self.assertAlmostEqual(sy, (1920 / 1080.0) ** 2)                            # bars top/bottom
        sx, sy = L.fit_scale(1920, 1080, 1080, 1920, 'fill')
        self.assertAlmostEqual(sy, 1.0)
        self.assertAlmostEqual(sx, (1080 / 1920.0) ** 2)                            # cropped sides
        self.assertEqual(L.fit_scale(1920, 1080, 1080, 1920, 'stretch'), (1.0, 1.0))
        self.assertEqual(L.fit_scale(0, 0, 1080, 1920, 'fit'), (1.0, 1.0))

    def test_blend_modes(self):
        A, B = (0.5, 0.5, 0.5, 1.0), (0.2, 0.4, 0.6, 1.0)
        self.assertEqual(L.composite_pixel([], 'over'), (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(L.composite_pixel([(A, 1.0), (B, 1.0)], 'over'), B)
        add = L.composite_pixel([(A, 1.0), (B, 0.5)], 'add')
        for got, want in zip(add, (0.6, 0.7, 0.8, 1.0)):
            self.assertAlmostEqual(got, want)
        scr = L.composite_pixel([(A, 1.0), (B, 1.0)], 'screen')
        for i in range(3):
            self.assertAlmostEqual(scr[i], 1 - (1 - A[i]) * (1 - B[i]))
        half = L.composite_pixel([((1.0, 0.0, 0.0, 0.5), 1.0)], 'over', premult_inputs=True)
        self.assertEqual(half, (0.5, 0.0, 0.0, 0.5))
        same = L.composite_pixel([((0.5, 0.0, 0.0, 0.5), 1.0)], 'over', premult_inputs=False)
        self.assertEqual(same, (0.5, 0.0, 0.0, 0.5))
        self.assertEqual(L.menu_index(L.BLENDMODES, 'screen'), 2)
        self.assertEqual(L.menu_index(L.BLENDMODES, 'bogus'), 0)


class Strip(unittest.TestCase):
    CL = [clip('a', 0, 0, 4, row=1), clip('b', 0, 3, 4, row=2), clip('c', 1, 8, 2, row=3)]

    def test_geometry(self):
        self.assertEqual(L.strip_tracks(self.CL), 3)
        self.assertEqual(L.strip_tracks([]), 1)
        u0, u1, v0, v1 = L.clip_rect(self.CL[2], 16, 3)
        self.assertEqual((u0, u1), (0.5, 0.625))
        self.assertTrue(1 / 3.0 < v0 < v1 < 2 / 3.0)
        self.assertEqual(L.track_at(0.9, 3), 2)
        self.assertEqual(L.track_at(-1, 3), 0)

    def test_hit(self):
        v = 1 / 6.0                                         # middle of track 0 of 3
        self.assertEqual(L.clip_at(self.CL, 3.5 / 16, v, 16, 3, 1024), (1, 'body'))   # b on top of a
        self.assertEqual(L.clip_at(self.CL, 1.0 / 16, v, 16, 3, 1024), (0, 'body'))
        self.assertEqual(L.clip_at(self.CL, 7.0 / 16 + 2 / 1024.0, v, 16, 3, 1024), (1, 'out'))
        self.assertEqual(L.clip_at(self.CL, 8.0 / 16 + 3 / 1024.0, 0.5, 16, 3, 1024), (2, 'in'))
        self.assertEqual(L.clip_at(self.CL, 0.9, v, 16, 3, 1024), (-1, ''))

    def test_move_trim(self):
        a = clip('a', 0, 2, 4, in_=1.0)
        m = L.move_clip(a, -1.0, 2)
        self.assertEqual((m['start'], m['track'], a['start']), (0.0, 2, 2))   # copy, clamped at 0
        t = L.trim_clip(a, 'in', 2.5)
        self.assertEqual((t['start'], t['dur'], t['in']), (2.5, 3.5, 1.5))   # out edge stays at 6
        t = L.trim_clip(a, 'in', 0.0)                                       # source time 0 limits: start 1
        self.assertEqual((t['start'], t['in'], L.clip_end(t)), (1.0, 0.0, 6.0))
        t = L.trim_clip(a, 'in', 9.0)                                       # never past the out edge
        self.assertAlmostEqual(t['dur'], L.MIN_DUR)
        t = L.trim_clip(a, 'out', 20.0, src_dur=8.0)                        # source end limits: 2 + 7
        self.assertEqual(t['dur'], 7.0)
        t = L.trim_clip(a, 'out', 1.0)
        self.assertAlmostEqual(t['dur'], L.MIN_DUR)
        fz = L.trim_clip(clip('f', 0, 0, 2, in_=3, speed=0.0), 'out', 50.0, src_dur=4.0)
        self.assertEqual(fz['dur'], 50.0)                                   # freeze frame: no source limit

    def test_rows_labels(self):
        cl = [dict(self.CL[0], enabled=False), self.CL[1], self.CL[2]]
        d = L.strip_rows(cl, 16, 'b')
        self.assertEqual(d['u0'], [0.0, 3 / 16.0, 0.5])
        self.assertEqual(d['tr'], [0.5, 0.0, 1.0])
        self.assertEqual(d['flag'], [0.0, 1.0, 0.0])
        lb = L.strip_labels(cl, 16, 3, 1024, 96)
        self.assertEqual(lb[0], ['text', 'x', 'y'])
        self.assertEqual([r[0] for r in lb[1:]], ['a', 'b', 'c'])
        self.assertEqual(L.strip_labels([clip('tiny', 0, 0, 0.1)], 16, 1, 1024, 96), [['text', 'x', 'y']])


class GeneratedCode(unittest.TestCase):
    """The TD-side code (strings in the builders) compiles, the logic is ASCII, and the phase-1 hook is there."""

    @classmethod
    def setUpClass(cls):
        cls.tl_src = _read(os.path.join(REPO, 'builders', 'timeline.py'))
        cls.cl_src = _read(os.path.join(REPO, 'builders', 'timeline_clips.py'))

    def _strings(self, src, names):
        ns = {'TL_ROOT': '/repo/builders', 'VIEW_W': 1024, 'VIEW_H': 360}
        tree = ast.parse(src)
        out = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
                out[node.targets[0].id] = eval(compile(ast.Expression(node.value), 'x', 'eval'), ns)   # noqa: S307
            elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                try:
                    ns[node.targets[0].id] = eval(compile(ast.Expression(node.value), 'x', 'eval'), ns)  # noqa: S307
                except Exception:  # noqa: BLE001
                    pass
        return out

    def test_python_strings_compile(self):
        s = self._strings(self.cl_src, ('CLIPS_RT', 'CLIPVIEW_CB', 'CLIP_IN', 'CLIP_PARS_CB'))
        self.assertEqual(len(s), 4)
        for name, code in s.items():
            compile(code, name, 'exec')
            self.assertTrue(all(ord(ch) < 128 for ch in code), name)
        self.assertNotIn('@REPO@', s['CLIPS_RT'])
        self.assertIn("REPO = '/repo'", s['CLIPS_RT'])
        a = self._strings(self.tl_src, ('ACTIONS',))['ACTIONS']
        compile(a, 'ACTIONS', 'exec')
        self.assertIn("comp.op('tl_clips')", a)
        self.assertIn('ck.module.tick(comp, nt, jumped or held)', a)

    def test_builders_parse_ascii(self):
        for f in ('timeline.py', 'timeline_clips.py', 'timeline_clips_logic.py'):
            src = _read(os.path.join(REPO, 'builders', f))
            ast.parse(src)
            self.assertTrue(all(ord(ch) < 128 for ch in src), f)

    def test_shaders_guarded(self):
        s = self._strings(self.cl_src, ('COMPOSITE_GLSL', 'STRIP_GLSL'))
        comp = s['COMPOSITE_GLSL']
        self.assertIn('local_size_x = 8', comp)
        self.assertIn('TDImageStoreOutput', comp)
        self.assertNotIn('texture(', comp)               # compute: no implicit-lod sampling
        for i in range(4):                                # every input access behind its TD_NUM_2D_INPUTS guard
            self.assertIn('#if TD_NUM_2D_INPUTS > %d' % i, comp)
        self.assertNotIn('#version', comp + s['STRIP_GLSL'])
        self.assertIn('ts.y < 4', s['STRIP_GLSL'])       # no texelFetch past the data texture

    def test_default_clips_parse(self):
        rows = self._strings(self.cl_src, ('DEFAULT_CLIPS',))['DEFAULT_CLIPS']
        cl = L.parse_clips(rows)
        self.assertEqual([c['id'] for c in cl], ['ramp', 'test', 'red', 'blue'])
        # demo crossfades: ramp -> test at 5..6 s, red -> blue at 13..14 s; midpoint weights 1 / 0.5
        self.assertEqual([round(w, 6) for _, w in L.active_clips(cl, 5.5)], [1.0, 0.5])
        self.assertEqual([round(w, 6) for _, w in L.active_clips(cl, 13.5)], [1.0, 0.5])
        self.assertAlmostEqual(L.active_clips(cl, 15.75)[0][1], 0.5)          # blue fades out 15.5..16
        self.assertTrue(max(len(L.active_clips(cl, t / 10.0)) for t in range(160)) <= 2)   # Maxplayers 2 is enough


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg not installed')
class MediaTool(unittest.TestCase):
    def test_probe_and_proxy(self):
        tmp = tempfile.mkdtemp()
        try:
            src = os.path.join(tmp, 'ramp.mp4')
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i',
                            "color=c=black:s=64x96:r=30:d=1,format=gray,geq=lum='N*8'", '-c:v', 'libx264',
                            '-pix_fmt', 'yuv420p', '-g', '30', src], check=True)
            sys.path.insert(0, os.path.join(REPO, 'tools'))
            import timeline_media as TM
            TM.CACHE, TM.PROXIES = os.path.join(tmp, 'cache'), os.path.join(tmp, 'proxies')
            self.assertEqual(TM.main(['--proxies', src]), 0)
            info = json.loads(_read(L.media_info_path(src, TM.CACHE)))
            self.assertEqual((info['frames'], info['fps'], info['w']), (30, 30.0, 64))
            self.assertTrue(os.path.isfile(info['proxy']))
            self.assertEqual(info['proxy_w'], 32)
            flags = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                    'packet=flags', '-of', 'csv=p=0', info['proxy']], capture_output=True,
                                   text=True, check=True).stdout.split()
            self.assertEqual(len(flags), 30)
            self.assertTrue(all(f.startswith('K') for f in flags))       # All-Intra
            self.assertEqual(TM.main([os.path.join(tmp, 'missing.mp4')]), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
