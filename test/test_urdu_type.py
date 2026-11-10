"""Offline tests for builders/urdu_type_logic.py (no TD).
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_urdu_type.py'
Oracles: /opt/homebrew/bin/fribidi (bidi levels) and hb-shape (advances); those tests skip when the tool is missing.
"""
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import urdu_type_logic as L  # noqa: E402
import urdu_render as R  # noqa: E402
import tempfile  # noqa: E402

FRIBIDI = shutil.which('fribidi') or '/opt/homebrew/bin/fribidi'

U_URDU = '\u0627\u0631\u062f\u0648'                  # urdu
U_ZABAN = '\u0632\u0628\u0627\u0646'                 # zaban
U_HELLO = '\u06c1\u06cc\u0644\u0648'                 # hello (Urdu)
U_PRISM = '\u067e\u0631\u0632\u0645'
U_ALI = '\u0639\u0644\u06cc \u0638\u0641\u0631'
U_HASAN = '\u062d\u0633\u0646 \u0631\u062d\u06cc\u0645'
U_STOP = '\u06d4'
U_COMMA = '\u060c'

CORPUS = [
    U_URDU + ' ' + U_ZABAN,
    U_HELLO + ' hello ' + U_URDU,
    U_HELLO + ' hello ' + U_URDU + ' 2026 world',
    'hello ' + U_URDU + ' 2026 world',
    'hello world',
    U_PRISM,
    U_ALI,
    U_HASAN,
    U_URDU + ' 2026',
    '2026 ' + U_URDU,
    U_URDU + ' \u06f2\u06f0\u06f2\u06f6 ' + U_ZABAN,
    U_URDU + ' \u0662\u0660\u0662\u0666 ' + U_ZABAN,
    'PRISM ' + U_PRISM + ' FEST',
    U_PRISM + ' PRISM FEST ' + U_ZABAN,
    U_URDU + U_COMMA + ' ' + U_ZABAN + U_STOP,
    'hello, ' + U_URDU + ' world.',
    '(' + U_URDU + ') hello',
    'hello (' + U_URDU + ')',
    U_URDU + ' (hello) ' + U_ZABAN,
    U_URDU + ' - ' + U_ZABAN,
    'a - b ' + U_URDU,
    U_URDU + ' www.example.com ' + U_ZABAN,
    U_URDU + ' 12 34 ' + U_ZABAN,
    'version 2 ' + U_URDU + ' 3',
    U_ALI + ' & ' + U_HASAN,
    U_URDU + ' TD 2025 ' + U_ZABAN,
    'one two three',
    U_URDU + ' ' + U_ZABAN + ' ' + U_PRISM + ' ' + U_ALI,
    '1 2 3 ' + U_URDU,
    U_URDU + ' ! ' + U_ZABAN,
    'Hi ' + U_HELLO + ' 7 ' + U_URDU + ' ok',
    U_ZABAN + ' 100% ' + U_URDU,
]


def fribidi_levels(line, direction):
    args = [FRIBIDI, '--nopad', '--nobreak', '--levels', '--charset', 'UTF-8']
    if direction == 'rtl':
        args.append('--rtl')
    elif direction == 'ltr':
        args.append('--ltr')
    r = subprocess.run(args, input=(line + '\n').encode('utf-8'), capture_output=True, timeout=5)
    out = r.stdout.decode('utf-8').strip().split('\n')
    return [int(x) for x in out[-1].split()]


def token_char_index(line, tok_i):
    """Index of the token's first strong char (else its first char) in the logical string."""
    pos, k = 0, 0
    for tk in line.split(' '):
        if not tk:
            pos += 1
            continue
        if k == tok_i:
            for j, ch in enumerate(tk):
                if L.char_class(ch) in ('AL', 'R', 'L'):
                    return pos + j
            return pos
        k += 1
        pos += len(tk) + 1
    raise IndexError(tok_i)


@unittest.skipUnless(os.path.isfile(FRIBIDI), 'fribidi not installed')
class TestBidiVsFribidi(unittest.TestCase):
    def test_corpus_levels(self):
        self.assertGreaterEqual(len(CORPUS), 30)
        checked = 0
        for d in ('auto', 'rtl', 'ltr'):
            for line in CORPUS:
                rows = L.parse(line, d)
                fl = fribidi_levels(line, d)
                for r in rows:
                    ci = token_char_index(line, r['idx'])
                    with self.subTest(line=line, d=d, tok=r['text']):
                        self.assertEqual(r['level'], fl[ci])
                    checked += 1
        self.assertGreater(checked, 250)

    def test_visual_order_mixed(self):
        line = U_HELLO + ' hello ' + U_URDU
        rows = L.parse(line, 'auto')
        order = L.reorder([r['level'] for r in rows])        # left to right
        self.assertEqual([rows[i]['text'] for i in order], [U_URDU, 'hello', U_HELLO])   # right-to-left reads 0,1,2


class TestParse(unittest.TestCase):
    def test_tokens_and_dirs(self):
        rows = L.parse(U_URDU + ' ' + U_ZABAN + U_STOP + '\nhello 2026', 'auto')
        self.assertEqual([r['text'] for r in rows], [U_URDU, U_ZABAN + U_STOP, 'hello', '2026'])
        self.assertEqual([r['para'] for r in rows], [0, 0, 1, 1])
        self.assertEqual([r['dir'] for r in rows], ['rtl', 'rtl', 'ltr', 'ltr'])
        self.assertEqual(rows[0]['base'], 1)
        self.assertEqual(rows[2]['base'], 0)

    def test_mixed_flag_and_roles(self):
        r = L.parse('2026\u0621 ' + U_URDU + ' hi 12', 'rtl')
        self.assertTrue(r[0]['mixed'])
        self.assertEqual([L.font_role(x) for x in r], ['rtl', 'rtl', 'ltr', 'digits'])
        self.assertEqual(L.font_role(L.parse('\u06f2\u06f0', 'rtl')[0]), 'rtl')

    def test_empty(self):
        self.assertEqual(L.parse('', 'auto'), [])
        self.assertEqual(L.parse('  \n \n', 'auto'), [])

    def test_select_text(self):
        self.assertEqual(L.select_text('a', ['x', 'y'], 3), 'y')
        self.assertEqual(L.select_text('a', [], 3), 'a')


def _words(widths, levels, base, paras=None):
    out = []
    for i, (w, lv) in enumerate(zip(widths, levels)):
        out.append({'idx': i, 'para': (paras or [0] * len(widths))[i], 'level': lv, 'base': base, 'w': float(w),
                    'x0': -w / 2.0 + 3.0, 'x1': w / 2.0 + 3.0, 'y0': -60.0, 'y1': 90.0})
    return out


class TestLayout(unittest.TestCase):
    def test_rtl_start_edge_and_order(self):
        ws = _words([200, 150, 300], [1, 1, 1], 1)
        lay = L.layout(ws, size=100, wordgap=0.3, align='start', anchorx=0.8, outw=1000, outh=1000)
        P = lay['place']
        self.assertAlmostEqual(P[0]['right'], 800.0)              # line 1 start edge (right, RTL) at the anchor
        self.assertGreater(P[0]['left'], P[1]['right'])          # word 0 right-most
        self.assertAlmostEqual(P[0]['left'] - P[1]['right'], 30.0)
        self.assertAlmostEqual(P[0]['cx'] - P[0]['left'], 100.0 - 3.0)

    def test_center_and_ltr(self):
        ws = _words([100, 100], [0, 0], 0)
        lay = L.layout(ws, size=100, wordgap=0.5, align='center', anchorx=0.5, outw=1000)
        P = lay['place']
        self.assertAlmostEqual(P[0]['left'], 500 - 125)
        self.assertLess(P[0]['left'], P[1]['left'])
        lay = L.layout(ws, size=100, wordgap=0.5, align='start', anchorx=0.1, outw=1000)
        self.assertAlmostEqual(lay['place'][0]['left'], 100.0)

    def test_wrap_no_overlap_deterministic(self):
        ws = _words([180, 220, 90, 300, 140, 260, 120], [1, 1, 2, 1, 1, 2, 1], 1)
        a = L.layout(ws, size=100, wordgap=0.3, maxwidth=500, outw=1080, outh=1920)
        b = L.layout(ws, size=100, wordgap=0.3, maxwidth=500, outw=1080, outh=1920)
        self.assertEqual(a, b)
        self.assertGreater(a['lines'], 1)
        P = a['place']
        for li in range(a['lines']):
            boxes = sorted([(p['left'], p['right']) for p in P.values() if p['line'] == li])
            self.assertLessEqual(boxes[-1][1] - boxes[0][0], 500.0 + 1e-6)
            for (l0, r0), (l1, r1) in zip(boxes, boxes[1:]):
                self.assertLessEqual(r0, l1 + 1e-6)
        ys = sorted(set(round(p['cy'], 3) for p in P.values()))
        self.assertAlmostEqual(ys[1] - ys[0], 250.0)            # Linegap 1 x 2.5 em x 100 px

    def test_wide_word_alone(self):
        ws = _words([900, 100], [1, 1], 1)
        a = L.layout(ws, size=100, maxwidth=500)
        self.assertEqual(a['lines'], 2)

    def test_paragraph_breaks(self):
        ws = _words([100, 100, 100], [1, 1, 0], 1, paras=[0, 0, 1])
        a = L.layout(ws, size=100)
        self.assertEqual([a['place'][i]['line'] for i in range(3)], [0, 0, 1])


class TestRanks(unittest.TestCase):
    def test_orders(self):
        P = L.layout(_words([100, 100, 100, 100, 100], [1] * 5, 1), size=100)['place']
        self.assertEqual(L.ranks(P, 5, 'reading'), [0, 1, 2, 3, 4])
        self.assertEqual(L.ranks(P, 5, 'reverse'), [4, 3, 2, 1, 0])
        self.assertEqual(L.ranks(P, 5, 'centerout')[2], 0)
        r = L.ranks(P, 5, 'random', seed=3)
        self.assertEqual(sorted(r), [0, 1, 2, 3, 4])
        self.assertEqual(r, L.ranks(P, 5, 'random', seed=3))


GOLDEN = {   # (mode, word rank) -> alpha / main value at p = 0, 0.25, 0.5, 1 (n = 3, stagger 0.5, linear)
    'fade': [[0, 0.375, 0.75, 1], [0, 0.125, 0.5, 1], [0, 0, 0.25, 1]],
}


class TestAnim(unittest.TestCase):
    def test_golden_fade(self):
        for rank in range(3):
            got = [round(L.anim(rank, 3, p, 'fade', 0.5, 'linear')['alpha'], 4) for p in (0, 0.25, 0.5, 1)]
            self.assertEqual(got, GOLDEN['fade'][rank])

    def test_modes_end_states(self):
        for m, _ in L.MODE:
            a0 = L.anim(0, 3, 0.0, m, 0.5, 'linear', slidex=10, slidey=-80, scalefrom=0.5, blurmax=20, pulseamt=0.3)
            a1 = L.anim(0, 3, 1.0, m, 0.5, 'linear', slidex=10, slidey=-80, scalefrom=0.5, blurmax=20, pulseamt=0.3)
            with self.subTest(mode=m):
                self.assertEqual((a1['tx'], a1['ty'], round(a1['sx'], 6), a1['alpha'], a1['reveal'], a1['blur']),
                                 (0.0, 0.0, 1.0, 1.0, 1.0, 0.0))
        self.assertEqual(L.anim(0, 3, 0, 'slide', slidey=-80)['ty'], -80.0)
        self.assertEqual(L.anim(0, 3, 0, 'scale', scalefrom=0.5)['sx'], 0.5)
        self.assertEqual(L.anim(0, 3, 0, 'wipe')['reveal'], 0.0)
        self.assertEqual(L.anim(0, 3, 0, 'blur', blurmax=20)['blur'], 20.0)
        self.assertAlmostEqual(L.anim(0, 1, 0.5, 'pulse', pulseamt=0.3, ease_kind='linear')['sx'], 1.3)

    def test_word0_first(self):
        a = [L.anim(r, 3, 0.3, 'fade', 0.6, 'linear')['alpha'] for r in range(3)]
        self.assertTrue(a[0] > a[1] >= a[2])

    def test_progress(self):
        self.assertEqual(L.progress('manual', manual=0.4), 0.4)
        self.assertEqual(L.progress('manual', manual=0.4, chan_progress=0.9), 0.9)
        self.assertAlmostEqual(L.progress('seconds', elapsed=1.0, seconds=4.0), 0.25)
        self.assertAlmostEqual(L.progress('bpm', elapsed=1.0, bpm=120, beats=4), 0.5)
        self.assertAlmostEqual(L.progress('bpm', chan_beat=1.0, beats=4), 0.25)
        self.assertAlmostEqual(L.progress('seconds', elapsed=5.0, seconds=4.0, loop=True), 0.25)
        self.assertEqual(L.progress('seconds', elapsed=5.0, seconds=4.0), 1.0)
        self.assertAlmostEqual(L.progress('audio', level=0.2, gain=3), 0.6)
        self.assertAlmostEqual(L.ease(0.5, 'ease'), 0.5)
        self.assertAlmostEqual(L.ease(1.0, 'expo'), 1.0)
        self.assertAlmostEqual(L.smooth(None, 1.0, 0.5), 1.0)
        self.assertAlmostEqual(L.smooth(0.0, 1.0, 0.5), 0.5)


class TestBbox(unittest.TestCase):
    def test_bbox(self):
        import numpy as np
        a = np.zeros((10, 20), dtype='float32')
        self.assertIsNone(L.bbox_from_alpha(a))
        a[3, 5] = 1.0
        b = L.bbox_from_alpha(a)
        self.assertEqual((b['x0'], b['x1'], b['y0'], b['y1']), (-5.0, -4.0, -2.0, -1.0))
        self.assertEqual(b['edge'], 0)
        a[0, 19] = 0.5
        b = L.bbox_from_alpha(a)
        self.assertEqual((b['x1'], b['y0']), (10.0, -5.0))
        self.assertGreater(b['edge'], 0)

    def test_tile_size(self):
        self.assertEqual(L.tile_size(233.3, 400, 160), (412, 528))


@unittest.skipUnless(os.path.isfile(L.HB_SHAPE) and os.path.isfile(L.NASTALIQ_TTC), 'hb-shape / Noto Nastaliq missing')
class TestHarfBuzz(unittest.TestCase):
    def test_oracle_advances(self):
        want = {U_PRISM: (1617, 7), U_ALI: (2515, 11), U_HASAN: (3605, 12), U_URDU + ' ' + U_ZABAN: (3393, 13)}
        for w, (adv, gl) in want.items():
            r = L.hb_advance(w, L.NASTALIQ_TTC, 0)
            self.assertEqual((r['advance'], r['glyphs']), (adv, gl))
        self.assertEqual(L.hb_upem(L.NASTALIQ_TTC, 0), 1000)

    def test_negative_control_isolated(self):
        off = '-init,-medi,-fina,-calt,-rlig,-liga,-ccmp'
        for w in (U_PRISM, U_ALI, U_HASAN):
            r = L.hb_advance(w, L.NASTALIQ_TTC, 0, features=off)
            self.assertEqual(r['glyphs'], len(w.replace(' ', '')) + w.count(' '))

    def test_font_lookup(self):
        self.assertEqual(L.hb_font_for('Noto Nastaliq Urdu', ''), (L.NASTALIQ_TTC, 0))
        f = L.hb_font_for('Helvetica', '')
        self.assertTrue(f is None or f[0].endswith('Helvetica.ttc'))
        self.assertIsNone(L.hb_font_for('No Such Font 123', ''))


class TestPixelFree(unittest.TestCase):
    """Measuring without TD (crash 4 / T-74): font tables + hb-shape extents. Live references (26 Oct, 31550, from
    docs/builds/urdu_type.md, measured before the crashes): evalTextSize(urdu) at 160 px Noto Nastaliq = (233.3, 400.0);
    ink of urdu = 214 x 150 px, below the tile centre."""

    def test_hb_ink_synthetic(self):
        g = [{'g': 'a', 'dx': 0, 'dy': 0, 'ax': 100, 'xb': 10, 'yb': 50, 'w': 80, 'h': -60},
             {'g': 'mark', 'dx': -30, 'dy': -100, 'ax': 0, 'xb': 0, 'yb': 20, 'w': 20, 'h': -20},
             {'g': 'b', 'dx': 0, 'dy': 0, 'ax': 50, 'xb': -5, 'yb': 40, 'w': 40, 'h': -40}]
        e = L.hb_ink(g)
        self.assertEqual((e['advance'], e['x0'], e['x1'], e['y0'], e['y1']), (150, 10, 135, -100, 50))
        self.assertFalse(e['notdef'])
        self.assertTrue(L.hb_ink([{'g': '.notdef', 'ax': 900, 'w': 1, 'h': -1}])['notdef'])
        self.assertEqual(L.hb_ink([])['advance'], 0)

    def test_estimate_and_tile(self):
        m = L.estimate_ink('hello', 100.0, None, 'ltr')
        self.assertAlmostEqual(m['w'], 275.0)
        self.assertEqual(m['src'], 'est')
        tw, th = L.tile_for(m, 100.0, 0.55, 0.4)
        self.assertGreaterEqual(tw / 2.0, max(abs(m['x0']), abs(m['x1'])) + 55)
        self.assertGreaterEqual(th / 2.0, max(abs(m['y0']), abs(m['y1']), m['lineh'] / 2.0) + 40)
        self.assertEqual((tw % 4, th % 4), (0, 0))
        self.assertEqual(L.estimate_ink('\u0627\u064e', 100.0)['adv'], 42.0)    # the mark adds no width

    def test_runtime_calls_no_top_methods(self):
        import re
        root = os.path.join(os.path.dirname(HERE), 'builders')
        for fn in ('urdu_type_rt.py', 'urdu_type.py', 'urdu_type_logic.py', 'urdu_render.py'):
            with open(os.path.join(root, fn)) as f:
                src = f.read()
            code = '\n'.join(ln.split('#')[0] for ln in src.splitlines() if not ln.strip().startswith(('"', "'")))
            for bad in (r'\.numpyArray\(', r'\.evalTextSize\(', r'\.sample\('):
                self.assertIsNone(re.search(bad, code), (fn, bad))


@unittest.skipUnless(os.path.isfile(L.NASTALIQ_TTC), 'Noto Nastaliq missing')
class TestFontTables(unittest.TestCase):
    def test_nastaliq_metrics(self):
        m = L.font_metrics(L.NASTALIQ_TTC, 0)
        self.assertEqual((m['upem'], m['ascent'], m['descent']), (1000, 1904, 596))
        lh, base = L.line_box(m, 160.0)
        self.assertAlmostEqual(lh, 400.0)                   # = live evalTextSize height (2.5 em)
        self.assertAlmostEqual(base, 200.0 - 304.64, places=2)

    def test_find_font(self):
        self.assertEqual(L.find_font('Noto Nastaliq Urdu'), (L.NASTALIQ_TTC, 0))
        f = L.find_font('Helvetica Neue')
        self.assertTrue(f is None or f[0].lower().endswith('helveticaneue.ttc'))
        self.assertIsNone(L.find_font(''))
        self.assertIsNone(L.font_metrics('/no/such/file.ttf'))


@unittest.skipUnless(os.path.isfile(L.HB_SHAPE) and os.path.isfile(L.NASTALIQ_TTC), 'hb-shape / Noto Nastaliq missing')
class TestHbMeasure(unittest.TestCase):
    def test_matches_live_probe(self):
        ms = L.measure_words([(U_URDU, L.NASTALIQ_TTC, 0, 'rtl')], 160.0)
        m = ms[0]
        self.assertEqual(m['src'], 'hb')
        self.assertAlmostEqual(m['adv'], 233.3, delta=0.5)            # live evalTextSize width
        self.assertAlmostEqual(m['lineh'], 400.0, delta=0.5)          # live evalTextSize height
        self.assertAlmostEqual(m['w'], 214.0, delta=3.0)              # live ink width (alpha, before the crashes)
        self.assertAlmostEqual(m['h'], 150.0, delta=3.0)              # live ink height
        self.assertLess((m['y0'] + m['y1']) / 2.0, 0.0)               # below the tile centre, like the live probe

    def test_batch_order_cache_and_fallback(self):
        items = [(U_ZABAN, L.NASTALIQ_TTC, 0, 'rtl'), ('hello', L.NASTALIQ_TTC, 0, 'ltr'),
                 (U_URDU, L.NASTALIQ_TTC, 0, 'rtl'), ('x', None, 0, 'ltr')]
        ms = L.measure_words(items, 160.0)
        self.assertEqual([m['src'] for m in ms], ['hb', 'est', 'hb', 'est'])   # Latin in Nastaliq = .notdef
        one = L.measure_words([(U_URDU, L.NASTALIQ_TTC, 0, 'rtl')], 160.0)[0]
        self.assertAlmostEqual(ms[2]['w'], one['w'])
        two = L.hb_extents_batch([U_URDU + ' ' + U_ZABAN], L.NASTALIQ_TTC, 0)[0]
        self.assertEqual((two['advance'], two['glyphs']), (3393, 13))           # oracle from BJ 1.5
        self.assertEqual(L.hb_extents_batch(['a\nb'], L.NASTALIQ_TTC, 0), [None])
        self.assertEqual(L.hb_extents_batch(['a'], L.NASTALIQ_TTC, 0, exe='/no/hb'), [None])


class TestAtlasPure(unittest.TestCase):
    def test_render_key(self):
        it = {'text': U_URDU, 'font': 'Noto Nastaliq Urdu', 'fontfile': '', 'typeface': 'Regular', 'weight': 0,
              'size': 160.0, 'lang': 'ur', 'dir': 'rtl'}
        k = L.render_key(it, 0.6, 2)
        self.assertEqual(k, L.render_key(dict(it), 0.6, 2))
        for ch in ({'size': 161.0}, {'weight': 700}, {'dir': 'ltr'}, {'text': U_ZABAN}, {'typeface': 'Bold'}):
            self.assertNotEqual(k, L.render_key(dict(it, **ch), 0.6, 2), ch)
        self.assertNotEqual(k, L.render_key(it, 0.7, 2))
        self.assertTrue(all(ord(c) < 128 for c in k))

    def test_render_items_roles(self):
        rows = L.parse(U_HELLO + ' hello ' + U_URDU + ' 2026', 'auto')
        f = {'rtl': ('Noto Nastaliq Urdu', ''), 'ltr': ('Helvetica Neue', ''), 'digits': ('Menlo', '')}
        it = L.render_items(rows, f, 120, weight=700, typeface='Bold')
        self.assertEqual([i['font'] for i in it], ['Noto Nastaliq Urdu', 'Helvetica Neue', 'Noto Nastaliq Urdu',
                                                   'Menlo'])
        self.assertEqual([i['dir'] for i in it], ['rtl', 'ltr', 'rtl', 'ltr'])
        self.assertEqual([i['weight'] for i in it], [700, 0, 700, 0])
        self.assertEqual(it[0]['lang'], 'ur')

    def test_png_roundtrip_and_ink(self):
        d = tempfile.mkdtemp()
        w, h = 13, 7
        al = [bytes(w) for _ in range(h)]
        al[2] = bytes([0] * 4 + [200, 255] + [0] * 7)
        al[4] = bytes([0] * 5 + [9] + [0] * 7)
        p = os.path.join(d, 'a.png')
        R.png_write_alpha(p, w, h, al)
        W, H, ch, rows = R.png_read(p)
        self.assertEqual((W, H, ch), (w, h, 4))
        self.assertEqual(R.alpha_rows(W, H, ch, rows), al)
        box, edge = R.ink_box_px(al, w, h)
        self.assertEqual((box, edge), ((4, 2, 6, 5), 0))
        al[0] = bytes([0, 99] + [0] * 11)
        self.assertGreater(R.ink_box_px(al, w, h)[1], 0)              # ink on the outer 2 px = clipped
        self.assertEqual(R.ink_box_px([bytes(w)] * h, w, h), (None, 0))

    def test_pack_and_rect(self):
        sizes = [(400, 300), (500, 200), (3900, 100), (10, 10)]
        pos, (W, H) = R.pack(sizes, maxw=4096, gutter=4)
        boxes = [(x, y, x + w, y + h) for (x, y), (w, h) in zip(pos, sizes)]
        for i in range(len(boxes)):
            self.assertLessEqual(boxes[i][2], W)
            self.assertLessEqual(boxes[i][3], H)
            for j in range(i):
                a, b = boxes[i], boxes[j]
                self.assertFalse(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3], (i, j))
        self.assertEqual(L.tex_rect(10, 0, 50, 40, 100), (10, 60, 50, 40))      # top row -> top of the texture

    def test_clusters(self):
        g = [{'g': 5, 'cl': 3, 'ax': 68, 'dx': 0, 'dy': 0, 'xb': 3, 'yb': 71, 'w': 53, 'h': -81},
             {'g': 6, 'cl': 1, 'ax': 0, 'dx': 10, 'dy': -20, 'xb': 0, 'yb': 5, 'w': 4, 'h': -5},
             {'g': 7, 'cl': 1, 'ax': 50, 'dx': 0, 'dy': 0, 'xb': 0, 'yb': 40, 'w': 50, 'h': -40}]
        c = L.clusters_from_hb(g)
        self.assertEqual([(x['cl'], x['n'], x['ax']) for x in c], [(3, 1, 68), (1, 2, 50)])
        self.assertEqual((c[0]['x0'], c[0]['x1'], c[0]['y0'], c[0]['y1']), (3, 56, -10, 71))
        self.assertEqual((c[1]['x0'], c[1]['y0'], c[1]['y1']), (0, -20, 40))

    def test_baseline_alignment(self):
        rows = L.parse(U_URDU + ' hello', 'rtl')
        atlas = {'words': [
            {'ok': True, 'x0': -100, 'x1': 100, 'y0': -116, 'y1': 35, 'h': 592, 'baseline_top': 400.6,
             'rect': [0, 0, 425, 592]},
            {'ok': True, 'x0': -159, 'x1': 164, 'y0': -60.5, 'y1': 55.5, 'h': 379, 'baseline_top': 248.0,
             'rect': [429, 213, 530, 379]}]}
        ws = L.words_from_atlas(rows, atlas)
        lay = L.layout(ws, size=160)
        base = [lay['place'][w['idx']]['cy'] - w['basey'] for w in ws]   # screen baseline (y down)
        self.assertAlmostEqual(base[0], base[1], places=6)
        self.assertEqual(ws[1]['tw'], 530.0)


@unittest.skipUnless(os.path.isfile(R.HB_VIEW) and os.path.isfile(L.HB_SHAPE) and os.path.isfile(L.NASTALIQ_TTC),
                     'hb-view / hb-shape / Noto Nastaliq missing')
class TestRenderOutsideTD(unittest.TestCase):
    """The renderer the COMP runs as a child process: real HarfBuzz rasters + metrics."""
    @classmethod
    def setUpClass(cls):
        cls.cache = tempfile.mkdtemp()
        rows = L.parse(U_URDU + ' ' + U_ZABAN + ' hello ' + U_URDU + '\n' + U_ALI, 'auto')
        f = {'rtl': ('Noto Nastaliq Urdu', ''), 'ltr': ('Helvetica Neue', '')}
        cls.rows = rows
        cls.items = L.render_items(rows, f, 160)
        for it in cls.items:
            it['key'] = L.render_key(it, 0.6, R.RENDER_VERSION)
        cls.job = {'cache': cls.cache, 'atlas': L.atlas_key([i['key'] for i in cls.items]), 'margin_em': 0.6,
                   'items': cls.items}
        cls.out = R.run_job(cls.job)

    def test_words_ok_and_unclipped(self):
        ws = self.out['words']
        self.assertEqual(len(ws), 6)
        self.assertTrue(all(w['ok'] for w in ws))
        self.assertTrue(all(w['edge'] == 0 for w in ws))                # no tail on the outer 2 px
        self.assertTrue(all(w['notdef'] == 0 for w in ws))

    def test_oracle_numbers(self):
        u = self.out['words'][0]                                       # U_URDU at 160 px
        z = self.out['words'][1]
        self.assertAlmostEqual(u['adv'], u['hb_adv'], delta=1.5)        # raster logical box = HarfBuzz advance
        self.assertAlmostEqual(u['iw'], 214.0, delta=3.0)               # = the live pre-crash ink width
        self.assertAlmostEqual(u['ih'], 150.0, delta=3.0)
        self.assertAlmostEqual(u['lineh'], 400.0, delta=1.0)            # 2.5 em Nastaliq line box
        self.assertAlmostEqual(u['hb_adv'] + z['hb_adv'], (3393 - 132) * 0.16, delta=3.0)    # BJ 1.5 minus the space (132)
        self.assertEqual([w['glyphs'] for w in self.out['words'][:2]], [4, 8])   # 4 + 8 + space = 13 (BJ 1.5)

    def test_cache_and_dedupe(self):
        ws = self.out['words']
        self.assertEqual(ws[0]['rect'], ws[3]['rect'])                  # repeated word packed once
        again = R.run_job(dict(self.job))
        self.assertEqual([w['key'] for w in again['words']], [w['key'] for w in ws])
        self.assertTrue(os.path.isfile(os.path.join(self.cache, 'a_%s.json' % self.job['atlas'])))

    def test_atlas_pixels_match_rects(self):
        W, H, ch, rows = R.png_read(self.out['atlas'])
        self.assertEqual((W, H), (self.out['w'], self.out['h']))
        al = R.alpha_rows(W, H, ch, rows)
        for w in self.out['words']:
            x, yb, tw, th = w['rect']
            yt = H - yb - th
            sub = [r[x:x + tw] for r in al[yt:yt + th]]
            box, edge = R.ink_box_px(sub, tw, th)
            self.assertEqual(edge, 0)
            self.assertAlmostEqual(box[2] - box[0], w['iw'], delta=0.01)

    def test_layout_from_atlas(self):
        ws = L.words_from_atlas(self.rows, self.out)
        lay = L.layout(ws, size=160, maxwidth=0)
        self.assertEqual(lay['lines'], 2)
        line0 = sorted([w for w in ws if lay['place'][w['idx']]['line'] == 0],
                       key=lambda w: lay['place'][w['idx']]['left'])
        self.assertEqual(line0[-1]['text'], U_URDU)                     # first word read = right-most (RTL)
        bases = {round(lay['place'][w['idx']]['cy'] - w['basey'], 3) for w in line0}
        self.assertEqual(len(bases), 1)                                 # Urdu + Latin share one baseline


if __name__ == '__main__':
    unittest.main()
