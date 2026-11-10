"""Offline tests for builders/zkit_logic.py (no TD).
Run: cd <repo> && python3 -I -m unittest discover -s test -p 'test_zkit.py'
"""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'builders'))
import zkit_logic as L  # noqa: E402


class Values(unittest.TestCase):
    def test_angle_roundtrip(self):
        self.assertAlmostEqual(L.value_to_angle(0), -135)
        self.assertAlmostEqual(L.value_to_angle(1), 135)
        self.assertAlmostEqual(L.value_to_angle(0.5), 0)
        for u in (0, 0.1, 0.33, 0.9, 1):
            self.assertAlmostEqual(L.angle_to_value(L.value_to_angle(u)), u)
        self.assertEqual(L.value_to_angle(2), 135)

    def test_norm(self):
        self.assertAlmostEqual(L.norm(5, 0, 10), 0.5)
        self.assertEqual(L.norm(20, 0, 10), 1.0)
        self.assertEqual(L.norm(1, 1, 1), 0.0)
        self.assertAlmostEqual(L.norm_free(20, 0, 10), 2.0)
        self.assertAlmostEqual(L.denorm(0.25, -1, 1), -0.5)

    def test_zero_tick(self):
        self.assertAlmostEqual(L.zero_u(-1, 1), 0.5)
        self.assertEqual(L.zero_u(0, 1), 0.0)
        self.assertEqual(L.zero_u(2, 5), 0.0)

    def test_drag(self):
        self.assertAlmostEqual(L.drag_value(0.0, 200), 1.0)
        self.assertAlmostEqual(L.drag_value(0.5, 100), 1.0)
        self.assertAlmostEqual(L.drag_value(0.5, -50), 0.25)
        self.assertAlmostEqual(L.drag_value(0.5, 100, shift=True), 0.55)
        self.assertAlmostEqual(L.drag_value(0.5, 100, shift=True, ctrl=True), 0.51)
        self.assertAlmostEqual(L.drag_value(0.1, 10, alt=True), 0.3)
        self.assertEqual(L.drag_value(0.9, 1000), 1.0)
        self.assertAlmostEqual(L.drag_value(0, 50, sens_px=100), 0.5)

    def test_quantize_wheel(self):
        self.assertAlmostEqual(L.quantize_u(0.26, 'int', 0, 4), 0.25)
        self.assertAlmostEqual(L.quantize_u(0.6, 'menu', 0, 0, 3), 0.5)
        self.assertAlmostEqual(L.wheel_value(0.5, 1, 'knob', 0, 1), 0.51)
        self.assertAlmostEqual(L.wheel_value(0.5, -1, 'knob', 0, 1, fine=True), 0.499)
        self.assertAlmostEqual(L.wheel_value(0.0, 1, 'int', 0, 4), 0.25)
        self.assertAlmostEqual(L.wheel_value(0.5, -1, 'menu', 0, 0, 5), 0.25)

    def test_par_mapping(self):
        self.assertEqual(L.to_par(0.5, 'int', 0, 10), 5)
        self.assertEqual(L.to_par(1.0, 'menu', 0, 0, 4), 3)
        self.assertIs(L.to_par(0.7, 'toggle', 0, 1), True)
        self.assertAlmostEqual(L.to_par(0.5, 'knob', -2, 2), 0.0)
        self.assertAlmostEqual(L.from_par(2, 'menu', 0, 0, 5), 0.5)
        self.assertEqual(L.from_par(True, 'toggle', 0, 1), 1.0)

    def test_format(self):
        self.assertEqual(L.fmt_value(0.3221), '0.322')
        self.assertEqual(L.fmt_value(19.7), '19.70')
        self.assertEqual(L.fmt_value(4030.2), '4030')
        self.assertEqual(L.fmt_value(123.45), '123.5')
        self.assertEqual(L.fmt_value(3, 'int'), '3')
        self.assertEqual(L.fmt_value(1, 'menu', ['a', 'perlin']), 'perlin')
        self.assertEqual(L.fmt_value(True, 'toggle'), 'on')
        self.assertEqual(L.short_label('Noise Period', 9), 'noise per')

    def test_label_kept_whole(self):
        # d=56: cell 77 px, label font 11.48 px -> 11 chars at 1x; 'spectrum gain' (13) fits at 0.85x
        lab, f = L.fit_label_size('Spectrum gain', 77, 11.48)
        self.assertEqual(lab, 'spectrum gain')
        self.assertAlmostEqual(f, 11.48 * 0.85, 3)
        self.assertEqual(L.fit_label_size('Trim', 77, 11.48), ('trim', 11.48))
        lab, f = L.fit_label_size('a very long parameter label', 77, 11.48)
        self.assertTrue(len(lab) < 27 and f < 11.48)
        m = lambda s, f: len(s) * f * 0.45            # a narrower real font: 17 chars fit at 0.85x
        self.assertEqual(L.fit_label_size('Kick glow (flash)', 77, 11.48, measure=m)[0], 'kick glow (flash)')
        lab, f = L.fit_label_size('x' * 40, 77, 11.48, measure=m)
        self.assertTrue(m(lab, f) <= 77 * 0.88 and len(lab) >= 3)
        m2 = lambda s, f: len(s) * f * 0.75           # too long even at 0.72x: whole trailing words go
        self.assertEqual(L.fit_label_size('Kick glow (flash-safe)', 77, 11.48, measure=m2)[0], 'kick glow')
        self.assertEqual(L.fit_label_size('Active (write pars)', 77, 11.48, measure=m2)[0], 'active')
        self.assertEqual(L.fit_label_size('Store (slot; 0 = active)', 77, 11.48, measure=m2)[0], 'store')


class Layout(unittest.TestCase):
    def groups(self, n1=14, n2=3):
        return [('g1', 'Look', [('a%d' % i, 1) for i in range(n1)]),
                ('g2', 'Text', [('s1', 2)] + [('b%d' % i, 1) for i in range(n2)])]

    def test_grid(self):
        lay = L.layout(self.groups(), d=50, cols_max=12)
        m = lay['m']
        self.assertEqual(lay['cols'], 12)
        a0, a12 = lay['items']['a0'], lay['items']['a12']
        self.assertEqual(a12[0], a0[0])                   # wrapped to column 0
        self.assertEqual(a12[1] - a0[1], m['cellh'])       # next row
        self.assertEqual(lay['items']['s1'][2], 2 * m['cellw'])
        g1, g2 = lay['groups']['g1'], lay['groups']['g2']
        self.assertEqual(g2[1], g1[1] + g1[3] + m['ggap'])
        self.assertEqual(lay['w'], 12 * m['cellw'] + 2 * m['inset'] + 2 * m['pad'])
        self.assertEqual(lay['h'], g2[1] + g2[3] + m['pad'])

    def test_few_items_narrow(self):
        lay = L.layout([('g', 't', [('a', 1), ('b', 1), ('c', 1)])], d=50, cols_max=12)
        self.assertEqual(lay['cols'], 3)

    def test_collapsed(self):
        lay = L.layout(self.groups(), d=50, collapsed={'g1'})
        self.assertNotIn('a0', lay['items'])
        self.assertTrue(lay['groups']['g1'][4])
        self.assertEqual(lay['groups']['g1'][3], lay['m']['head'])

    def test_bar_and_hit(self):
        bar = [('plus', 'plus'), ('p1', 'slot'), ('p2', 'slot'), ('g', 'gap'), ('rand', 'rand')]
        lay = L.layout(self.groups(3, 0), d=50, bar_items=bar)
        self.assertIsNotNone(lay['bar'])
        x, y, w, h = lay['items']['p1']
        self.assertEqual(L.hit(lay['items'], x + 1, y + 1), 'p1')
        a = lay['items']['a0']
        self.assertGreater(a[1], y + h)
        self.assertEqual(L.hit(lay['items'], a[0] + a[2] / 2, a[1] + a[3] / 2), 'a0')
        self.assertIsNone(L.hit(lay['items'], -5, -5))
        self.assertTrue(L.is_click(1, 2))
        self.assertFalse(L.is_click(0, 5))


class Typing(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(L.parse_typed('1.5'), 1.5)
        self.assertEqual(L.parse_typed('2.6', 'int'), 3)
        self.assertIsNone(L.parse_typed('abc'))
        self.assertIsNone(L.parse_typed(''))
        self.assertEqual(L.parse_typed('per', 'menu', ['simplex', 'perlin']), 1)
        self.assertEqual(L.parse_typed('0', 'menu', ['a', 'b']), 0)
        self.assertIsNone(L.parse_typed('5', 'menu', ['a', 'b']))
        self.assertIs(L.parse_typed('on', 'toggle'), True)

    def test_keys(self):
        b, a = '', None
        for k in (ord('1'), ord('.'), ord('2'), ord('x')):
            b, a = L.type_key(b, k)
        self.assertEqual(b, '1.2x')
        b, a = L.type_key(b, 127)
        self.assertEqual(b, '1.2')
        self.assertEqual(L.type_key(b, 13)[1], 'commit')
        self.assertEqual(L.type_key(b, 27)[1], 'cancel')


class Presets(unittest.TestCase):
    kinds = {'f': 'knob', 'i': 'int', 'm': 'menu', 't': 'toggle'}

    def test_morph_ends_and_middle(self):
        a = {'f': 0.0, 'i': 0, 'm': 0, 't': False}
        b = {'f': 10.0, 'i': 5, 'm': 2, 't': True}
        self.assertEqual(L.morph_values(a, b, 0, self.kinds), {'f': 0.0, 'i': 0, 'm': 0, 't': False})
        self.assertEqual(L.morph_values(a, b, 1, self.kinds), {'f': 10.0, 'i': 5, 'm': 2, 't': True})
        mid = L.morph_values(a, b, 0.5, self.kinds)
        self.assertAlmostEqual(mid['f'], 5.0)
        self.assertEqual(mid['i'], 2)       # round(2.5) banker's -> 2
        self.assertEqual(mid['m'], 2)
        self.assertIs(mid['t'], True)
        self.assertEqual(L.morph_values(a, b, 0.49, self.kinds)['m'], 0)

    def test_morph_partial_keys(self):
        out = L.morph_values({'f': 1.0, 'x': 3}, {'f': 3.0}, 0.5, {})
        self.assertEqual(out, {'f': 2.0, 'x': 3})

    def test_randomise(self):
        vals = {'f': 0.5, 'i': 2, 'm': 1, 't': True}
        specs = {'f': ('knob', 0, 1, 0), 'i': ('int', 0, 10, 0), 'm': ('menu', 0, 0, 4), 't': ('toggle', 0, 1, 0)}
        self.assertEqual(L.randomise(vals, specs, 0, random.Random(1)), vals)
        r = L.randomise(vals, specs, 1, random.Random(2))
        self.assertTrue(0 <= r['f'] <= 1 and 0 <= r['i'] <= 10 and 0 <= r['m'] < 4)
        locked = L.randomise(vals, specs, 1, random.Random(2), locks={'f'})
        self.assertEqual(locked['f'], 0.5)
        self.assertEqual(locked['i'], r['i'])   # a lock does not shift the others' draws
        small = L.randomise(vals, specs, 0.1, random.Random(3))
        self.assertLessEqual(abs(small['f'] - 0.5), 0.1 + 1e-9)

    def test_slots_and_swatch(self):
        self.assertEqual(L.next_free_slot({1, 2, 4}, 8), 3)
        self.assertIsNone(L.next_free_slot({1, 2}, 2))
        r, g, b = L.brightness_scale((0.5, 0.25, 0.0), 100)
        self.assertAlmostEqual(r, 1.0)
        self.assertAlmostEqual(g, 0.5)
        self.assertEqual(L.brightness_scale((0, 0, 0), 50), (0.25, 0.25, 0.25))


class V2(unittest.TestCase):
    """26 Oct resume: sized flow layout, v5 value text, properties menu order, presets json, filter, text buckets."""

    def test_kinds(self):
        self.assertEqual(L.kind_for_style('Float'), 'knob')
        self.assertEqual(L.kind_for_style('XY'), 'knob')
        self.assertEqual(L.kind_for_style('Int'), 'int')
        self.assertEqual(L.kind_for_style('StrMenu', 0), 'dropdown')   # a field + live pop-up list (28 Oct)
        self.assertEqual(L.kind_for_style('StrMenu', 3), 'dropdown')
        self.assertEqual(L.kind_for_style('Menu', 3), 'menu')
        self.assertEqual(L.kind_for_style('RGB'), 'swatch')
        self.assertEqual(L.kind_for_style('Momentary'), 'momentary')
        self.assertIsNone(L.kind_for_style('Header'))
        self.assertEqual(L.ktype_choices('knob'), ['knob', 'toggle', 'momentary'])
        self.assertEqual(L.ktype_choices('menu'), ['menu'])

    def test_fmt4(self):
        self.assertEqual(L.fmt4(0.93041), '0.9304')
        self.assertEqual(L.fmt4(1.9481), '1.948')
        self.assertEqual(L.fmt4(16.451), '16.45')
        self.assertEqual(L.fmt4(4030.2), '4030')
        self.assertEqual(L.fmt4(True, 'toggle'), '1.0000')
        self.assertEqual(L.fmt4(False, 'momentary'), '0.0000')
        self.assertEqual(L.fmt4(2, 'menu', ['a', 'b', 'perlin3d']), 'perlin3d')

    def test_range(self):
        self.assertTrue(L.out_of_range(9.5, 0.1, 8))
        self.assertFalse(L.out_of_range(8, 0.1, 8))
        self.assertEqual(L.clamp_typed(9.5, 0, 8, False, True), 8)
        self.assertEqual(L.clamp_typed(-3, 0, 8, True, False), 0)
        self.assertEqual(L.clamp_typed(9.5, 0, 8, False, False), 9.5)

    def test_menu_arc(self):
        self.assertEqual(L.menu_arc(0, 4), (0.0, 0.25))     # first item = short arc at 7 o'clock (7.0 #7)
        self.assertEqual(L.menu_arc(3, 4), (0.75, 1.0))
        self.assertEqual(L.menu_arc(9, 4), (0.75, 1.0))

    def test_double_and_filter(self):
        self.assertTrue(L.is_double(1.0, 'a', 1.2, 'a'))
        self.assertFalse(L.is_double(1.0, 'a', 1.5, 'a'))
        self.assertFalse(L.is_double(1.0, 'b', 1.1, 'a'))
        self.assertEqual(L.filter_step(0, 1, 0.1, 0), 1.0)
        v = L.filter_step(0, 1, 0.5, 0.5)
        self.assertAlmostEqual(v, 1 - math.exp(-1))

    def test_preset_json(self):
        vals = {'a': 1.5, 'b': True, 'c': 3, 'd': (0.1, 0.2, 0.3), 's': 'x'}
        back = L.preset_load(L.preset_dump(vals))
        self.assertEqual(back['d'], [0.1, 0.2, 0.3])
        self.assertIs(back['b'], True)
        self.assertEqual(back['c'], 3)
        self.assertEqual(L.preset_load('not json'), {})
        self.assertEqual(L.preset_load(''), {})

    def test_props_menu_order(self):
        keys = [r[0] for r in L.menu_rows('knob')]
        want = ['ktype', 'recall', 'sens', 'min', 'max', 'filter', 'clampmin', 'clampmax', 'label', 'size', 'color',
                'showvalue', 'chan', 'midi', 'showop', 'savelayout', 'setdefault', 'delete']
        self.assertEqual(keys, want)                          # 7.0 #8 order
        self.assertNotIn('min', [r[0] for r in L.menu_rows('toggle')])
        self.assertNotIn('sens', [r[0] for r in L.menu_rows('string')])
        tints = {r[0]: r[2] for r in L.menu_rows('knob')}
        self.assertEqual(tints['midi'], 'blue')
        self.assertEqual(tints['delete'], 'red')

    def test_popup_rect(self):
        x, y, w, h = L.popup_rect((10, 50, 77, 87), 18, 17, 218, 666, 365)
        self.assertEqual((x, w, h), (93, 218, 19 * 17))
        self.assertLessEqual(y + h, 365)
        x2, _y, _w, _h = L.popup_rect((560, 50, 77, 87), 5, 17, 218, 666, 365)
        self.assertEqual(x2, 560 - 6 - 218)                   # no room on the right -> left side

    def test_flow_layout(self):
        g = [('g', 't', [('a', 1, 1), ('b', 2.0, 1), ('s', 1, 2), ('c', 0.5, 1)])]
        lay = L.layout_flow(g, 56, 4)
        m = lay['m']
        a, b, s, c = (lay['items'][k] for k in 'absc')
        self.assertEqual(b[2], 2 * m['cellw'])                # continuous size (7.0 #5)
        self.assertEqual(b[3], 2 * m['cellh'])
        self.assertEqual(s[0], a[0])                          # wrapped: a+b+s exceed 4 cells
        self.assertEqual(s[1], a[1] + b[3])                   # row as tall as its tallest cell
        self.assertEqual(c[1], s[1])
        self.assertEqual(lay['sizes']['b'], 2.0)
        gx, gy, gw, gh, col = lay['groups']['g']
        self.assertEqual(gy + gh, s[1] + s[3] + m['inset'])
        lay2 = L.layout_flow(g, 56, 4, collapsed={'g'})
        self.assertNotIn('a', lay2['items'])
        bar = [('_plus', 'plus'), ('_p1', 'slot'), ('_gap', 'gap'), ('_rand', 'rand')]
        lay3 = L.layout_flow(g, 56, 4, bar_items=bar)
        self.assertNotIn('_gap', lay3['items'])
        self.assertGreater(lay3['items']['a'][1], lay3['items']['_p1'][1] + lay3['items']['_p1'][3])

    def test_size_buckets(self):
        keep, m = L.size_buckets([10, 10.2, 11, 20, 9.5])
        self.assertEqual(keep, [9.5, 10.0, 11.0, 20.0])
        self.assertEqual(m[10.2], 1)
        keep, m = L.size_buckets([float(s) for s in range(8, 30)], n_max=4)
        self.assertEqual(len(keep), 4)
        self.assertTrue(all(0 <= v < 4 for v in m.values()))

    def test_palette_tokens(self):
        self.assertEqual([n for n, _ in L.PALETTE], ['pink', 'orange', 'lime', 'cyan', 'blue', 'white'])
        self.assertEqual(L.SURFACE_BLUE, (0.357, 0.561, 0.816))
        self.assertEqual(len(L.FIELDS), 16)
        self.assertEqual(len(set(L.RK.values()) - {0}), len(L.RK) - 2)   # knob/int share 0, rest unique


class Perf(unittest.TestCase):
    """26 Oct perf pass (docs/builds/zkit_perf.md): tile culling, hit grid, cell diffs, hot text slots."""

    def boxes(self, n=300, W=666, H=805, seed=3):
        rng = random.Random(seed)
        out = []
        for _ in range(n):
            w, h = rng.uniform(4, 140), rng.uniform(4, 120)
            out.append((rng.uniform(-10, W - 5), rng.uniform(-10, H - 5), w, h))
        out.append((0, 0, W, H))                              # a group frame as big as the panel
        return out

    def test_tiles_conservative_and_ordered(self):
        W, H = 666, 805
        bx = self.boxes(W=W, H=H)
        lists = L.tile_lists(bx, W, H, 64)
        ntx, nty = L.tile_grid(W, H, 64)
        self.assertEqual((ntx, nty), (11, 13))
        self.assertEqual(len(lists), ntx * nty)
        rng = random.Random(5)
        for _ in range(3000):
            px, py = rng.randrange(W) + 0.5, rng.randrange(H) + 0.5     # pixel centres, y down (as the shader)
            tile = int(px) // 64 + (int(py) // 64) * ntx                 # = the shader's tile index formula
            want = [i for i, (x, y, w, h) in enumerate(bx)
                    if not (px < x - 2 or px > x + w + 2 or py < y - 2 or py > y + h + 2)]
            got = [i for i in lists[tile] if i in set(want)]
            self.assertEqual(got, want)                                  # every drawer is listed, in draw order
            self.assertEqual(lists[tile], sorted(lists[tile]))
        rows = L.tile_rows(lists)
        self.assertEqual(rows[0][0], 'count')
        self.assertEqual(len(rows[0]), ntx * nty + 1)
        self.assertEqual(len(rows), 1 + max(len(l) for l in lists))
        t = 7
        self.assertEqual([rows[1 + k][1 + t] for k in range(rows[0][1 + t])], lists[t])

    def test_tiles_cut_the_loop(self):
        # a 32-knob panel (AU_db_meter-like, ~120 instances): the average pixel loops over a few, not all
        W, H, n = 666, 805, 0
        bx = []
        for r in range(8):
            for c in range(8):
                x, y = 20 + c * 77, 120 + r * 87
                bx += [(x, y, 77, 87), (x + 20, y + 18, 36, 18), (x + 10, y + 70, 56, 16)]
        bx.append((14, 100, 640, 700))
        lists = L.tile_lists(bx, W, H, 64)
        avg = sum(len(l) for l in lists) / float(len(lists))
        self.assertLess(avg, 0.12 * len(bx))

    def test_hit_grid_matches_hit(self):
        bar = [('_plus', 'plus')] + [('_p%d' % k, 'slot') for k in range(1, 9)] + [('_gap', 'gap'), ('_rand', 'rand')]
        g = [('g1', 't', [('a%d' % i, 1.0 + 0.3 * (i % 3), 2 if i == 4 else 1) for i in range(30)]),
             ('g2', 't', [('b%d' % i, 1, 1) for i in range(12)])]
        lay = L.layout_flow(g, 56, 8, bar_items=bar)
        grid = L.hit_grid(lay['items'])
        rng = random.Random(9)
        for _ in range(4000):
            x, y = rng.uniform(-5, lay['w'] + 5), rng.uniform(-5, lay['h'] + 5)
            self.assertEqual(L.hit_fast(grid, lay['items'], x, y), L.hit(lay['items'], x, y))

    def test_diffs(self):
        a = [(1, 2, 3), (4, 5, 6)]
        self.assertEqual(L.diff_columns(a, [(1, 2, 3), (4, 9, 6)]), [(1, 1, 9)])
        self.assertEqual(L.diff_columns(a, list(a)), [])
        self.assertIsNone(L.diff_columns(a, a + [(7, 8, 9)]))
        self.assertIsNone(L.diff_columns(None, a))
        self.assertEqual(L.diff_rows([('x', 1, 2)], [('x', 1, 3)]), [(0, 2, 3)])
        self.assertIsNone(L.diff_rows([('x', 1)], [('x', 1), ('y', 2)]))
        self.assertIsNone(L.diff_rows([('x', 1)], [('x', 1, 2)]))

    def test_hot_slots(self):
        slots, st = [None, None], [0, 0]
        self.assertEqual(L.hot_take(slots, st, 'a', 1), (0, True))
        self.assertEqual(L.hot_take(slots, st, 'b', 2), (1, True))
        self.assertEqual(L.hot_take(slots, st, 'a', 3), (0, False))     # in use: no move, no rewrite
        self.assertEqual(L.hot_take(slots, st, 'c', 4), (1, True))      # b was least recently used
        self.assertEqual(slots, ['a', 'c'])

    def test_boxes(self):
        self.assertEqual(L.union_box((0, 0, 10, 10), (5, -5, 10, 10)), (0, -5, 15, 15))
        self.assertEqual(L.grow_box((10, 10, 4, 4), 2), (8, 8, 8, 8))


class FaceWiring(unittest.TestCase):
    """T-84: a GLSL TOP has 3 connectors from Python on 31550; the face's 12 textures go 3 wired + 9 via `tops`."""

    class _Src:
        def __init__(self, name):
            self.name, self.path = name, '/p/' + name

    class _Conn:
        def __init__(self, face, i):
            self.face, self.i = face, i

        @property
        def connections(self):
            return [1] if self.face.wired[self.i] is not None else []

        def connect(self, s):
            self.face.wired[self.i] = s

        def disconnect(self):
            self.face.wired[self.i] = None

    class _Par:
        def __init__(self):
            self.val = ''

    class _Face:
        def __init__(self, pre=()):
            self.wired = [None, None, None]
            for i, s in enumerate(pre):
                self.wired[i] = s
            self.inputConnectors = [FaceWiring._Conn(self, i) for i in range(3)]   # IndexError past 3, like TD
            self.par = FaceWiring._Pars()

        @property
        def inputs(self):
            return [s for s in self.wired if s is not None]

    class _Pars:
        def __init__(self):
            object.__setattr__(self, 'tops', FaceWiring._Par())

        def __setattr__(self, k, v):                                    # par = 'x' sets the value, like TD
            getattr(self, k).val = v

    def _zkit(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('zkit_b', os.path.join(os.path.dirname(L.__file__), 'zkit.py'))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_at_most_three_wired(self):
        Z = self._zkit()
        self.assertLessEqual(Z.MAX_WIRED, 3)
        srcs = [self._Src(n) for n in ['zk_gpu_tex', 'zk_tiles_tex'] + ['zk_text%d' % k for k in range(Z.NTEXT)] +
                ['zk_hot%d' % k for k in range(Z.NHOT)]]
        f = self._Face()
        f.par.tops.val = ''
        Z.wire_face(f, srcs)
        self.assertLessEqual(len(f.inputs), 3)
        order = [s.name for s in f.inputs] + f.par.tops.val.split()
        self.assertEqual(order, [s.name for s in srcs])                 # sTD2DInputs order the shader expects
        glsl = open(Z.GLSL_FILE).read()
        import re
        hi = max(int(x) for x in re.findall(r'sTD2DInputs\[(\d+)\]', glsl))
        self.assertEqual(hi + 1, len(srcs))                              # every index the shader reads is fed

    def test_rewire_idempotent_and_shrinks(self):
        Z = self._zkit()
        a, b, c, d = (self._Src(n) for n in 'abcd')
        f = self._Face(pre=(d, d, d))
        Z.wire_face(f, [a, b, c, d])
        self.assertEqual([s.name for s in f.inputs], ['a', 'b', 'c'])
        self.assertEqual(f.par.tops.val, 'd')
        Z.wire_face(f, [a, b])
        self.assertEqual([s.name for s in f.inputs], ['a', 'b'])
        self.assertEqual(f.par.tops.val, '')

    def test_no_connector_index_past_three_in_builder(self):
        import re
        src = open(os.path.join(os.path.dirname(L.__file__), 'zkit.py')).read()
        self.assertNotRegex(src, r'face\.inputConnectors\[\s*\d+\s*\+')
        self.assertNotIn('glslmultiTOP', src)



class PackedInstances(unittest.TestCase):
    """Perf pass 26 Oct: zk_gpu_sel order + Shuffle seqn(4) give texel k*n + i = fields 4k..4k+3 (shader G(i, k))."""

    def test_pack_order_groups(self):
        src = open(os.path.join(os.path.dirname(L.__file__), 'zkit.py')).read()
        ns = {'__name__': 'zkit_t'}
        exec(compile(src.split('\nMAX_WIRED')[0], 'zkit.py', 'exec'), ns)
        order = ns['PACK_ORDER']
        F = L.FIELDS
        # Shuffle seqn N=4 joins consecutive channels j*4..j*4+3 into output channel j (= r, g, b, a)
        chans = [order[4 * j:4 * j + 4] for j in range(4)]
        for k in range(4):
            self.assertEqual([chans[j][k] for j in range(4)], F[4 * k:4 * k + 4])
        glsl = open(os.path.join(os.path.dirname(L.__file__), 'zkit_face.glsl')).read()
        self.assertIn('ivec2(k * gN + i, 0)', glsl)
        self.assertNotIn('F(i,', glsl)


class Dropdowns(unittest.TestCase):
    """StrMenu dropdown fields + pop-up list (28 Oct): pure geometry, typing, presets, randomise."""

    def test_geom_below_above_scroll(self):
        g = L.drop_geom((10, 100, 120, 60), 5, 20, 150, 600, 800, top=40)
        self.assertEqual(g['nvis'], 5)
        self.assertEqual(g['box'], (10, 162, 180, 120))               # below the field, min width 180
        g = L.drop_geom((10, 700, 120, 60), 5, 20, 150, 600, 800, top=40)
        self.assertEqual(g['box'][1], 700 - 2 - 120)                   # no room below: above
        g = L.drop_geom((10, 100, 120, 60), 500, 20, 150, 600, 800, top=40)
        self.assertEqual(g['nvis'], (800 - 2 - 162) // 20 - 1)         # long list: rows that fit below, scrolls
        x, y, w, h = g['box']
        self.assertTrue(y >= 40 and y + h <= 800)                      # inside the viewport, under the header
        g = L.drop_geom((500, 100, 120, 60), 3, 20, 150, 600, 800)
        self.assertTrue(g['box'][0] + g['box'][2] <= 600)              # kept inside the panel width
        g = L.drop_geom((0, 0, 100, 50), 0, 20, 100, 600, 800)
        self.assertEqual((g['nvis'], g['n']), (1, 0))                  # empty: one '(no items)' row
        # the effectors panel case (live b2): field at y 240..300 of a 439 px view, header 125, 7 items
        g = L.drop_geom((108, 240, 140, 60), 7, 17, 180, 666, 439, top=125)
        x, y, w, h = g['box']
        self.assertTrue(y >= 125 and y + h <= 439)
        self.assertTrue(y >= 300 or y + h <= 240)                      # never over the field
        self.assertLess(g['nvis'], 7)                                  # the rest scrolls

    def test_hit_and_offsets(self):
        g = L.drop_geom((0, 0, 200, 40), 30, 20, 100, 400, 300)
        bx, by, bw, bh = g['box']
        self.assertEqual(L.drop_hit(g, bx + 5, by + 5, 0), 'head')
        self.assertEqual(L.drop_hit(g, bx + 5, by + 25, 0), 0)
        self.assertEqual(L.drop_hit(g, bx + 5, by + 45, 7), 8)
        self.assertIsNone(L.drop_hit(g, bx - 1, by + 25, 0))
        self.assertEqual(L.drop_off(-3, 30, g['nvis']), 0)
        self.assertEqual(L.drop_off(99, 30, g['nvis']), 30 - g['nvis'])
        self.assertEqual(L.drop_start(None, 30, 10), 0)
        self.assertEqual(L.drop_start(3, 30, 10), 0)
        self.assertEqual(L.drop_start(20, 30, 10), 15)
        self.assertIsNotNone(L.drop_thumb(g, 0))
        self.assertIsNone(L.drop_thumb(L.drop_geom((0, 0, 200, 40), 3, 20, 100, 400, 300), 0))
        e = L.drop_geom((0, 0, 200, 40), 0, 20, 100, 400, 300)
        self.assertEqual(L.drop_hit(e, e['box'][0] + 3, e['box'][1] + 25, 0), 'pad')

    def test_fit_value_keeps_case_and_op_name(self):
        m = lambda t, f: len(t) * f * 0.5
        self.assertEqual(L.fit_value('Hand_L', 200, 10, m), ('Hand_L', 10.0))     # case kept
        t, f = L.fit_value('/project1/zkm_rig/hand_r', 80, 10, m)
        self.assertTrue(t.endswith('hand_r') and t.startswith('../'))           # leading folders go, name whole
        self.assertLessEqual(m(t, f), 80)
        t, f = L.fit_value('averyveryverylongname', 40, 10, m)
        self.assertLessEqual(m(t, f), 40)                                      # one long word: end cut

    def test_free_typing(self):
        b = ''
        for ch in 'sphere1 #demo':
            b, _a = L.type_key(b, ord(ch), free=True)
        self.assertEqual(b, 'sphere1 #demo')
        b, _a = L.type_key('', ord('#'))
        self.assertEqual(b, '')                                        # numbers keep the strict set

    def test_rows_and_randomise_skip_names(self):
        keys = [r[0] for r in L.menu_rows('dropdown')]
        self.assertNotIn('ktype', keys)
        self.assertIn('recall', keys)
        out = L.randomise({'Sel': 'sphere1', 'Gain': 0.5}, {'Gain': ('knob', 0.0, 1.0, 0)}, 1.0, random.Random(3))
        self.assertEqual(out['Sel'], 'sphere1')                        # text (no spec) never randomised
        self.assertEqual(L.morph_values({'Sel': 'a'}, {'Sel': 'b'}, 0.6, {'Sel': 'string'})['Sel'], 'b')
        self.assertIn('kind == 19', open(os.path.join(os.path.dirname(L.__file__), 'zkit_face.glsl')).read())
        self.assertEqual(L.RK['drop'], 19)


class PagesScroll(unittest.TestCase):
    """Pages + scroll pass (28 Oct, T-231): the panel is a viewport, never sized to its content."""
    BAR = [('_plus', 'plus')] + [('_p%d' % k, 'slot') for k in range(1, 9)] + [('_gap', 'gap'), ('_rand', 'rand'),
                                                                               ('_theme', 'theme')]

    def groups(self, pages=12, per=36):
        return [('_g:P%d' % g, 'P%d' % g, [('k%d_%d' % (g, i), 1.0, 1) for i in range(per)]) for g in range(pages)]

    def test_viewport_cap(self):
        self.assertEqual(L.viewport_cap(0, (2056, 1329)), (2056 - L.SCREEN_MARGIN_W, 1329 - L.SCREEN_MARGIN_H))
        self.assertEqual(L.viewport_cap(500, (2056, 1329))[1], 500)            # Zkmaxh wins
        self.assertEqual(L.viewport_cap(20000, (2056, 1329))[1], L.TEX_CAP)    # never past the texture cap
        self.assertEqual(L.viewport_cap(0, None), (L.FALLBACK_SCREEN[0] - L.SCREEN_MARGIN_W,
                                                   L.FALLBACK_SCREEN[1] - L.SCREEN_MARGIN_H))
        self.assertEqual(L.viewport_cap(0, (30000, 30000)), (L.TEX_CAP, L.TEX_CAP))
        self.assertEqual(L.viewport_cap(10, (2056, 1329))[1], L.MIN_VIEW_H)
        self.assertLessEqual(4 * L.MAX_INST, L.TEX_CAP)

    def test_big_panel_is_capped(self):
        # PX_pointfx-sized: 432 knobs was a 666 x 6935 px panel
        cap = L.viewport_cap(0, (2056, 1329))
        for d in (24, 56, 160):
            lay = L.layout_view(self.groups(), d, 8, (), self.BAR, cap=cap)
            v = lay['view']
            self.assertLessEqual(v['H'], cap[1])
            self.assertLessEqual(v['W'], cap[0])
            self.assertTrue(v['overflow'])
            self.assertGreater(lay['all']['h'], v['H'])
            self.assertEqual(v['smax'], lay['h'] - v['H'])
            self.assertIsNotNone(v['track'])
            self.assertLessEqual(v['track'][0] + v['track'][2], v['W'])
        lay = L.layout_view(self.groups(), 56, 8, (), self.BAR, cap=(4000, 600))
        self.assertEqual(lay['view']['H'], 600)

    def test_columns_capped_by_screen_width(self):
        cap = (700, 900)
        lay = L.layout_view(self.groups(2, 30), 56, 12, (), None, cap=cap)
        self.assertLessEqual(lay['view']['W'], 700)
        self.assertEqual(lay['cols'], L.cols_that_fit(56, 700))
        lay2 = L.layout_view(self.groups(2, 30), 56, 12, (), None, cap=(4000, 900))
        self.assertEqual(lay2['cols'], 12)

    def test_tab_filter(self):
        g = self.groups(3, 10)
        lay = L.layout_view(g, 56, 8, (), self.BAR, tab='P1', cap=(2000, 1200))
        v = lay['view']
        self.assertEqual(v['tab'], 'P1')
        self.assertEqual(v['tabs'], ['P0', 'P1', 'P2', 'All'])
        knobs = [i for i in lay['items'] if not i.startswith('_')]
        self.assertEqual(sorted(knobs), sorted('k1_%d' % i for i in range(10)))
        self.assertEqual(list(lay['groups']), ['_g:P1'])
        for t in v['tabs']:
            self.assertIn('_t:' + t, lay['items'])
        lay_all = L.layout_view(g, 56, 8, (), self.BAR, tab='All', cap=(2000, 1200))
        self.assertEqual(lay_all['view']['W'], v['W'])                     # a tab keeps the All width + height
        self.assertEqual(lay_all['view']['H'], v['H'])
        self.assertEqual(len([i for i in lay['all']['items'] if not i.startswith('_')]), 30)
        self.assertEqual(L.layout_view(g, 56, 8, (), self.BAR, tab='nope', cap=(2000, 1200))['view']['tab'], 'All')
        one = L.layout_view(g[:1], 56, 8, (), self.BAR, cap=(2000, 1200))
        self.assertEqual(one['view']['tabs'], [])                           # one page: nothing to switch
        self.assertFalse(any(i.startswith('_t:') for i in one['items']))
        # tabs sit between the bar and the first group, inside the header
        tb = lay['items']['_t:P2']
        self.assertGreater(tb[1], lay['items']['_p1'][1] + lay['items']['_p1'][3])
        self.assertLessEqual(tb[1] + tb[3], v['hdr'])
        self.assertGreaterEqual(min(b[1] for i, b in lay['items'].items() if not i.startswith('_')), v['hdr'])

    def test_tabs_wrap(self):
        names = ['page%d' % i for i in range(30)]
        tb, h = L.tab_boxes(names, 10, 5, 300, 56)
        for b in tb.values():
            self.assertLessEqual(b[0] + b[2], 310)
        self.assertGreater(h, L.tab_metrics(56)['h'])

    def test_scroll_clamp_and_thumb(self):
        lay = L.layout_view(self.groups(), 56, 8, (), self.BAR, cap=(2000, 900))
        v = lay['view']
        smax = v['smax']
        self.assertEqual(L.clamp_scroll(-50, smax), 0)
        self.assertEqual(L.clamp_scroll(smax + 999, smax), smax)
        self.assertEqual(L.clamp_scroll(12.4, smax), 12)
        tr = v['track']
        t0 = L.thumb(v, 0, lay['h'])
        t1 = L.thumb(v, smax, lay['h'])
        self.assertAlmostEqual(t0[0], tr[1])
        self.assertAlmostEqual(t1[0] + t1[1], tr[1] + tr[3])
        self.assertAlmostEqual(t0[1], t1[1])
        self.assertGreaterEqual(t0[1], 20)
        self.assertEqual(L.thumb_drag(v, 0, tr[3] - t0[1], lay['h']), smax)   # thumb to the bottom = the end
        self.assertEqual(L.thumb_drag(v, smax, -10000, lay['h']), 0)
        self.assertEqual(L.wheel_scroll(100, 1, v, 40), 60)                      # wheel up shows what is above
        self.assertEqual(L.wheel_scroll(0, 1, v, 40), 0)
        small = L.layout_view(self.groups(1, 4), 56, 8, (), self.BAR, cap=(2000, 900))
        self.assertEqual(small['view']['smax'], 0)
        self.assertIsNone(L.thumb(small['view'], 0, small['h']))
        self.assertEqual(L.scroll_cfg_load(L.scroll_cfg_dump({'All': 120, 'P1': 0})), {'All': 120, 'P1': 0})
        self.assertEqual(L.scroll_cfg_load('junk,All:x,P2:30'), {'P2': 30})

    def test_hit_with_offset(self):
        lay = L.layout_view(self.groups(), 56, 8, (), self.BAR, cap=(2000, 900))
        v = lay['view']
        grid = L.hit_grid(lay['items'])
        b = lay['items']['k5_10']
        sc = L.clamp_scroll(b[1] - v['hdr'] - 10, v['smax'])
        vx, vy = b[0] + b[2] / 2.0, b[1] - sc + b[3] / 2.0                       # where it shows in the view
        zone, x, y = L.where(v, vx, vy, sc)
        self.assertEqual(zone, 'content')
        self.assertEqual(L.hit_fast(grid, lay['items'], x, y), 'k5_10')
        p1 = lay['items']['_p1']                                                # header: never moved by the scroll
        zone, x, y = L.where(v, p1[0] + 3, p1[1] + 3, sc)
        self.assertEqual(zone, 'head')
        self.assertEqual(L.hit_fast(grid, lay['items'], x, y), '_p1')
        self.assertEqual(L.where(v, v['W'] - 2, v['hdr'] + 50, sc)[0], 'sbar')
        # a knob scrolled under the header cannot be hit through it
        top = lay['items']['k0_0']
        zone, x, y = L.where(v, top[0] + 5, v['hdr'] - 3, 200)
        self.assertNotEqual(L.hit_fast(grid, lay['items'], x, y), 'k0_0')

    def test_culling(self):
        lay = L.layout_view(self.groups(), 56, 8, (), self.BAR, cap=(2000, 900))
        v = lay['view']
        ids = [i for i in lay['items'] if not i.startswith('_')]
        self.assertEqual(len(ids), 432)
        for sc in (0, v['smax'] // 2, v['smax']):
            vis = L.visible(lay['items'], ids, v, sc)
            self.assertGreater(len(vis), 0)
            self.assertLess(len(vis), 80)
            for i in ids:
                b = lay['items'][i]
                on = b[1] - sc + b[3] > v['hdr'] and b[1] - sc < v['H']
                self.assertEqual(i in vis, on)

    def test_even_rows(self):
        cw = L.metrics(56)['cellw']
        for n, want in ((9, [5, 4]), (17, [6, 6, 5]), (16, [8, 8]), (8, [8]), (1, [1]), (10, [5, 5])):
            g = [('g', 't', [('i%d' % k, 1.0, 1) for k in range(n)])]
            lay = L.layout_flow(g, 56, 8, balance=True)
            rows = {}
            for k in range(n):
                rows.setdefault(lay['items']['i%d' % k][1], []).append(k)
            self.assertEqual([len(r) for _y, r in sorted(rows.items())], want, n)
            self.assertEqual(lay['w'], L.layout_flow(g, 56, 8)['w'])            # frame width unchanged
        rng = random.Random(3)
        for _ in range(200):                                                   # mixed sizes: never more rows
            ws = [int(round(cw * rng.choice((0.5, 1.0, 1.0, 1.0, 1.6, 2.0)))) for _k in range(rng.randint(1, 30))]
            inner = 8 * cw
            ww = L.balanced_wrap(ws, inner)
            self.assertLessEqual(ww, inner)
            self.assertEqual(L._wrap_rows(ws, ww), L._wrap_rows(ws, inner))

    def test_label_rules_kept(self):
        self.assertEqual(L.fit_label_size('kick glow (flash-safe)', 60, 12, measure=lambda s, f: len(s) * f * 0.5)[0],
                         'kick glow')


class Essentials(unittest.TestCase):
    """Main tab + macros + hidden pages (28 Oct; user: skim down, keep and add functionality)."""

    def test_validate(self):
        styles = {'Speed': 'Float', 'Count': 'Int', 'Mode': 'Menu', 'Caption': 'Str', 'Tint': 'RGB'}
        entry = {'main': ['Speed', 'Nope', 'Tint', 'Speed'],
                 'macros': [{'name': 'Zkm1', 'label': 'Energy', 'drives': [{'par': 'Speed', 'from': 0.2, 'to': 3},
                                                                          {'par': 'Ghost', 'from': 0, 'to': 1},
                                                                          {'par': 'Caption', 'from': 0, 'to': 1}]},
                            {'name': 'zkm2', 'drives': [{'par': 'Ghost', 'from': 0, 'to': 1}]},
                            {'name': 'Speed', 'drives': [{'par': 'Speed', 'from': 0, 'to': 1}]},
                            {'name': 'Zkm3', 'drives': [{'par': 'Count', 'to': 1}]}]}
        main, macros, notes = L.validate_essentials(entry, styles.get)
        self.assertEqual(main, ['Speed', 'Tint'])
        self.assertEqual([m['name'] for m in macros], ['Zkm1'])
        self.assertEqual(macros[0]['label'], 'Energy')
        self.assertEqual([d['par'] for d in macros[0]['drives']], ['Speed'])
        self.assertTrue(any('Nope' in n for n in notes))
        self.assertTrue(any('Ghost' in n for n in notes))
        self.assertTrue(any('not numeric' in n for n in notes))
        self.assertTrue(any('Zkm<n>' in n for n in notes))
        self.assertEqual(L.validate_essentials(None, styles.get), ([], [], []))

    def test_macro_mapping(self):
        d = {'par': 'Speed', 'from': 0.2, 'to': 3.0}
        self.assertAlmostEqual(L.macro_value(0, d), 0.2)
        self.assertAlmostEqual(L.macro_value(1, d), 3.0)
        self.assertAlmostEqual(L.macro_value(0.5, d), 1.6)
        self.assertAlmostEqual(L.macro_value(2, d), 3.0)                       # u clamped
        self.assertEqual(L.macro_value(0.5, {'from': 8, 'to': 2}, 'Int'), 5)   # reversed range, int
        self.assertIs(L.macro_value(0.7, {'from': 0, 'to': 1}, 'Toggle'), True)
        self.assertAlmostEqual(L.macro_init(1.6, d), 0.5)
        self.assertEqual(L.macro_init(9, d), 1.0)
        self.assertEqual(L.macro_init(1, {'from': 1, 'to': 1}), 0.0)

    def test_main_resolve_and_fallback(self):
        items = [('Gain', ['Gain'], 'Gain'), ('Offset1', ['Offset1'], 'Offset'), ('Offset2', ['Offset2'], 'Offset'),
                 ('Tint', ['Tintr', 'Tintg', 'Tintb'], 'Tint'), ('Mode', ['Mode'], 'Mode')]
        self.assertEqual(L.resolve_main(['Mode', 'Offset', 'Tintg', 'Nope'], items),
                         ['Mode', 'Offset1', 'Offset2', 'Tint'])
        groups = [('Look', ['a%d' % i for i in range(20)]), ('More', ['b0'])]
        self.assertEqual(L.main_fallback(groups), ['a%d' % i for i in range(12)])
        self.assertEqual(L.main_fallback([]), [])

    def test_main_tab_layout(self):
        g = [('_g:P%d' % k, 'P%d' % k, [('k%d_%d' % (k, i), 1.0, 1) for i in range(30)]) for k in range(4)]
        main = ('_g:Main', 'Main', [('k0_1', 1.0, 1), ('k3_4', 1.0, 1), ('Zkm1', 1.0, 1)])
        lay = L.layout_view(g, 56, 8, (), None, cap=(2000, 900), main=main)
        v = lay['view']
        self.assertEqual(v['tab'], 'Main')                                     # the default tab
        self.assertEqual(v['tabs'], ['Main', 'P0', 'P1', 'P2', 'P3', 'All'])
        self.assertEqual(sorted(i for i in lay['items'] if not i.startswith('_')), ['Zkm1', 'k0_1', 'k3_4'])
        self.assertNotIn('Zkm1', lay['all']['items'])                          # All = every page, as before
        self.assertEqual(len([i for i in lay['all']['items'] if not i.startswith('_')]), 120)
        self.assertEqual(v['smax'], 0)
        lay_a = L.layout_view(g, 56, 8, (), None, tab='All', cap=(2000, 900), main=main)
        self.assertEqual((lay_a['view']['W'], lay_a['view']['H']), (v['W'], v['H']))
        one = L.layout_view(g[:1], 56, 8, (), None, cap=(2000, 900), main=main)
        self.assertEqual(one['view']['tabs'], ['Main', 'P0'])                  # one page: no separate All

    def test_hidden_page_rules(self):
        self.assertTrue(L.is_page_switch('Toggle', 'Vhon'))
        self.assertTrue(L.is_page_switch('Toggle', 'Lineson'))
        self.assertFalse(L.is_page_switch('Float', 'Geoon'))
        self.assertFalse(L.is_page_switch('Toggle', 'Mono'))
        self.assertFalse(L.is_page_switch('Toggle', 'Motion'))                 # "...ion" is a word, not a switch
        self.assertFalse(L.is_page_switch('Toggle', 'On'))
        rows = [{'uid': '1', 'type': 'prox_push', 'enabled': '1'}, {'uid': '4', 'type': 'curl', 'enabled': '0'},
                {'uid': 'x'}]
        self.assertEqual(L.stack_inactive(rows), {'M4_curl'})

    def test_uid_pars(self):
        exp = {1: 'prox_push', 2: 'curl', 4: 'dissolve_noise'}
        cur = {1: 'prox_push', 2: 'prox_colour', 4: 'dissolve_noise'}
        self.assertTrue(L.uid_par_ok('M1strength', exp, cur))
        self.assertFalse(L.uid_par_ok('M2strength', exp, cur))                # uid 2 is not curl any more
        self.assertFalse(L.uid_par_ok('M7amount', exp, cur))                  # not a default-stack uid
        self.assertTrue(L.uid_par_ok('Mono', exp, cur))                       # not uid-named
        self.assertTrue(L.uid_par_ok('Speed', exp, cur))
        self.assertTrue(L.uid_par_ok('M2strength', {}, {}))                   # no expectation: no check
        self.assertEqual(L.stack_types([{'uid': '2', 'type': 'curl'}, {'x': 1}]), {2: 'curl'})
        m, mc, notes = L.validate_essentials({'macros': [{'name': 'Zkm1', 'default': 0.33,
                                                          'drives': [{'par': 'A', 'from': 0, 'to': 1}]}]},
                                             {'A': 'Float'}.get)
        self.assertAlmostEqual(mc[0]['default'], 0.33)

if __name__ == '__main__':
    unittest.main()
