"""Offline tests for FX_retro (builders/fx_retro.py rack, fx_retro_logic.py, fx_retro_<module>.py). No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_fx_retro.py'
GLSL: every compute shader is compiled with glslc (OpenGL target) against stubs of the TD functions it uses: a
syntax / type check, NOT a TD compile (that is LIVE CHECK R1 in docs/builds/fx_retro.md). numpy parts are skipped
when numpy is missing."""
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
sys.path.insert(0, BUILDERS)
import fx_retro_logic as L  # noqa: E402
import palette_map_logic as PM  # noqa: E402

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None

RACK = {'__name__': 'fx_retro_rack'}
with open(os.path.join(BUILDERS, 'fx_retro.py')) as _fh:
    exec(_fh.read(), RACK)
LG = RACK['load_logic']()
MODS = list(RACK['MODULES'])


def _read(path):
    with open(path) as fh:
        return fh.read()


def module(name):
    ns = dict(RACK)
    exec(_read(os.path.join(BUILDERS, 'fx_retro_%s.py' % name)), ns)
    return ns


def lib(**k):
    return RACK['glsl_lib'](LG, **k)


STUB = """#version 460
uniform sampler2D sTD2DInputs[3];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[2];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""


# ==================================================================================================== rack
class Rack(unittest.TestCase):
    def test_chain(self):
        rows = [{'name': 'a', 'order': '2'}, {'name': 'b', 'order': '1'}, {'name': 'c', 'order': '2'}]
        self.assertEqual(RACK['plan_chain'](rows), ['b', 'a', 'c'])
        a = set(RACK['chain_edges'](['s1']))
        b = set(RACK['chain_edges'](['s1', 's2']))
        self.assertEqual(len(b - a), 7)
        self.assertEqual(RACK['next_name']('glyph', {'glyph1'}), 'glyph2')

    def test_pars_refresh_menus(self):                   # T-175 / T-190: grown menus reach older instances
        import types as _t
        ns = dict(RACK)
        ns['ParMode'] = _t.SimpleNamespace(EXPRESSION='e', CONSTANT='c')
        exec(_read(os.path.join(BUILDERS, 'fx_retro.py')), ns)

        class P:
            def __init__(s): s.menuNames, s.menuLabels, s.val = ['a', 'b'], ['A', 'B'], 'b'
            def eval(s): return s.val
        p = P()
        c = _t.SimpleNamespace(par=_t.SimpleNamespace(Mode=p), customPages=[_t.SimpleNamespace(name='Pg')])
        ns['_pars'](c, [('Pg', [('Mode', 'Menu', 'a', {'names': ['a', 'b', 'c'], 'labels': ['A', 'B', 'C']})])])
        self.assertEqual(p.menuNames, ['a', 'b', 'c'])
        self.assertEqual(p.val, 'b')

    def test_default_rows_cover_modules(self):
        self.assertEqual([r[1] for r in RACK['DEFAULT_ROWS']], MODS)
        self.assertEqual([r[2] for r in RACK['DEFAULT_ROWS']], [1] + [0] * (len(MODS) - 1))

    def test_files_ascii(self):
        names = ['fx_retro.py', 'fx_retro_logic.py', 'fx_retro_font8x8.py', 'fx_retro_checks.py'] + \
            ['fx_retro_%s.py' % m for m in MODS]
        for f in names:
            with open(os.path.join(BUILDERS, f), 'rb') as fh:
                self.assertTrue(all(b < 128 for b in fh.read()), f)


class Specs(unittest.TestCase):
    """PAGES / PRESETS of every module: names unique, presets only set existing pars, menus in range."""

    def test_specs(self):
        for name in MODS:
            M = module(name)
            self.assertEqual(M['MODULE'], name)
            pars, menus = {}, {}
            for _page, plist in M['PAGES']:
                for pn, style, default, o in plist:
                    self.assertNotIn(pn, pars, (name, pn))
                    self.assertEqual(pn[0].upper() + pn[1:].lower(), pn, (name, pn))      # TD custom par naming
                    pars[pn] = style
                    if style == 'Menu':
                        menus[pn] = o['names']
                        self.assertEqual(len(o['names']), len(o['labels']), (name, pn))
                        self.assertIn(default, o['names'], (name, pn))
                    if style == 'RGB':
                        for s in 'rgb':
                            pars[pn + s] = 'Float'
            self.assertEqual(M['PAGES'][0][1][0][0], 'Amount', name)
            for pg in M['PANEL_PAGES']:
                self.assertIn(pg, [p[0] for p in M['PAGES']], name)
            self.assertTrue(3 <= len(M['PRESETS']) <= 8, name)
            for slot, pname, vals in M['PRESETS']:
                for k, v in vals.items():
                    self.assertIn(k, pars, (name, pname, k))
                    if k in menus:
                        self.assertTrue(0 <= v < len(menus[k]), (name, pname, k, v))


# ==================================================================================================== logic
class Palettes(unittest.TestCase):
    def test_reuse_palette_map(self):
        self.assertIs(L.PM, PM)
        self.assertEqual(L.machine_hex('pico8'), PM.preset('pico8'))
        self.assertEqual(L.machine_hex('gbbgb'), PM.preset('gameboy'))

    def test_counts(self):
        self.assertEqual(len(L.machine_hex('nes')), 55)          # 64 minus 9 duplicate blacks
        self.assertEqual(len(L.machine_hex('c64')), 16)
        self.assertEqual(len(L.machine_hex('spectrum')), 16)      # black twice on purpose: the halves rule needs 8 + 8
        self.assertEqual(len(set(L.machine_hex('ega64'))), 64)
        self.assertEqual(len(L.machine_hex('amigaham')), 16)
        self.assertEqual(L.machine_hex('amiga12'), [])

    def test_spectrum_halves_kept(self):
        # machine_hex drops duplicates: Spectrum's second black must survive -> handled by listing D7 first
        h = L.machine_hex('spectrum')
        self.assertEqual(h[:8], L.SPECTRUM[:8])

    def test_bank(self):
        lay, fixed = L.bank_layout()
        rows = L.bank_rows(['FF0000'])
        self.assertEqual(len(rows), 1 + fixed + 1)
        self.assertEqual(rows[0], ['hex', 'r', 'g', 'b', 'L', 'A', 'B'])
        off, n, kind, _c = L.bank_slot('c64', len(rows))
        self.assertEqual(rows[1 + off][0], '000000')
        self.assertEqual(rows[1 + off + 1][0], 'FFFFFF')
        self.assertEqual(n, 16)
        self.assertEqual(kind, 0)
        self.assertEqual(L.bank_slot('custom', len(rows))[:2], (fixed, 1))
        self.assertEqual(rows[1 + fixed][0], 'FF0000')
        self.assertEqual(L.bank_slot('custom', len(L.bank_rows([])))[:2], (fixed, 1))   # 'none' fallback row
        self.assertEqual(L.bank_slot('amiga12')[2], 1)
        self.assertEqual(L.machine_bits('amiga12'), (4, 4, 4))
        for k, _l in L.MACHINE_MENU:
            o, n, kind, _c = L.bank_slot(k, len(rows))
            self.assertTrue(o + n <= len(rows) - 1, k)

    def test_constraints(self):
        self.assertEqual(L.constraint_index('auto', 'spectrum'), 1)
        self.assertEqual(L.constraint_index('auto', 'amigaham'), 2)
        self.assertEqual(L.constraint_index('auto', 'nes'), 0)
        self.assertEqual(L.constraint_index('cell', 'nes'), 1)
        self.assertEqual(L.halves('spectrum'), 1)

    def test_vgrid(self):
        self.assertEqual(L.vgrid(1080, 1920, 4), (4, 4, 270, 480))
        self.assertEqual(L.vgrid(1080, 1920, 4, 8.0 / 7.0), (5, 4, 216, 480))
        self.assertEqual(L.vgrid(1080, 1920, 7), (7, 7, 155, 275))
        self.assertEqual(L.groups(270, 8), 34)


class Dither(unittest.TestCase):
    def test_bayer_matches_palette_map(self):
        B = PM.bayer8()
        for y in range(8):
            for x in range(8):
                self.assertAlmostEqual(L.bayer(x, y, 3), (B[y][x] + 0.5) / 64.0)

    def test_bayer_sizes_are_permutations(self):
        for n in (1, 2, 3, 4):
            s = 1 << n
            v = sorted(int(L.bayer(x, y, n) * s * s) for y in range(s) for x in range(s))
            self.assertEqual(v, list(range(s * s)))

    def test_bayer2(self):
        self.assertEqual([[int(L.bayer(x, y, 1) * 4) for x in range(2)] for y in range(2)], [[0, 2], [3, 1]])

    def test_quant(self):
        self.assertEqual(L.quant_levels(0.5, 2, 0.5), 1.0)
        self.assertEqual(L.quant_levels(0.49, 2, 0.5), 0.0)
        self.assertEqual(L.quant_levels(0.2, 4, 0.0), 0.0)
        self.assertAlmostEqual(L.quant_levels(0.4, 4, 0.5), 1.0 / 3.0)

    def test_ordered_mean_on_ramp(self):
        # 2 levels + Bayer 8x8 on an ideal ramp: per 8-column block the white share = the ramp value within 1/64
        for x0 in range(0, 256, 8):
            on = 0
            for y in range(8):
                for x in range(x0, x0 + 8):
                    v = (x + 0.5) / 256.0
                    on += L.quant_levels(v, 2, L.bayer(x & 7, y & 7, 3))
            mean = sum((x + 0.5) / 256.0 for x in range(x0, x0 + 8)) / 8.0
            self.assertLess(abs(on / 64.0 - mean), 1.0 / 64.0 + 1e-9)

    def test_ign_and_white_range(self):
        for x in range(0, 300, 7):
            for y in range(0, 300, 11):
                self.assertTrue(0.0 <= L.ign(x, y) < 1.0)
                self.assertTrue(0.0 <= L.hsh(x, y, 5) < 1.0)

    def test_blue_noise(self):
        r = L.void_and_cluster(16)
        self.assertEqual(sorted(r), list(range(256)))
        rows = L.bn_table_rows(r, 16)
        self.assertEqual(len(rows), 17)
        # texel (x, y) = row x + 1, column y = rank[y * n + x]
        self.assertAlmostEqual(float(rows[1 + 3][5]), (r[5 * 16 + 3] + 0.5) / 256.0, places=7)

    @unittest.skipUnless(np is not None, 'numpy')
    def test_blue_noise_spectrum(self):
        r = np.array(L.void_and_cluster(64)).reshape(64, 64) / 4096.0
        F = np.abs(np.fft.fft2(r - r.mean())) ** 2
        f = np.fft.fftfreq(64)
        R = np.sqrt(f[:, None] ** 2 + f[None, :] ** 2)
        low = F[(R > 0) & (R < 0.12)].sum() / F[R > 0].sum()
        self.assertLess(low, 1e-3)                               # white noise: ~0.05

    def test_kernels_sum(self):
        for k in L.DIFFUSION:
            self.assertEqual(sum(w for _dx, _dy, w in L.KERNELS[k]), L.KERNEL_DIV[k] if k != 'atkinson' else 6)
        self.assertIn('KRANGE[6]', L.kernels_glsl())

    def test_diffuse_mean(self):
        img = [[(0.3, 0.3, 0.3)] * 16 for _ in range(16)]
        q = L.diffuse(img, 'fs', lambda c: [L.quant_levels(v, 2, 0.5) for v in c])
        mean = sum(p[0] for row in q for p in row) / 256.0
        self.assertLess(abs(mean - 0.3), 0.03)
        q2 = L.diffuse(img, 'fs', lambda c: [L.quant_levels(v, 2, 0.5) for v in c], serpentine=True)
        self.assertNotEqual(q, q2)

    def test_gbcam(self):
        self.assertEqual(L.gbcam_level(0.0, 1.0, 0.0, 0.5), 0)
        self.assertEqual(L.gbcam_level(1.0, 1.0, 0.0, 0.5), 3)
        self.assertEqual(L.rank_by_l(['9BBC0F', '0F380F', '8BAC0F', '306230']), [1, 3, 2, 0])


class CellAndHam(unittest.TestCase):
    def test_pair_index_roundtrip(self):
        n = 9
        p = 0
        for i in range(n):
            for j in range(i + 1, n):
                self.assertEqual(L.pair_index(i, j, n), p)
                self.assertEqual(L.pair_decode(p, n), (i, j))
                p += 1

    def test_cell_pair_two_colours(self):
        pal = [PM.hex_to_rgb(h) for h in L.machine_hex('spectrum')]
        red, blue = PM.hex_to_rgb('D70000'), PM.hex_to_rgb('0000D7')
        pix = [red] * 40 + [blue] * 24
        i, j, cost = L.cell_pair(pix, pal, halves_rule=1)
        self.assertEqual((L.SPECTRUM[i], L.SPECTRUM[j]), ('0000D7', 'D70000'))
        self.assertAlmostEqual(cost, 0.0, places=9)

    def test_cell_pair_halves(self):
        pal = [PM.hex_to_rgb(h) for h in L.machine_hex('spectrum')]
        pix = [PM.hex_to_rgb('FF0000')] * 32 + [PM.hex_to_rgb('0000D7')] * 32       # bright red + dim blue
        i, j, _c = L.cell_pair(pix, pal, halves_rule=1)
        self.assertEqual(i < 8, j < 8)
        i2, j2, _c2 = L.cell_pair(pix, pal, halves_rule=0)
        self.assertEqual({L.SPECTRUM[i2], L.SPECTRUM[j2]}, {'FF0000', '0000D7'})

    def test_ham_rule(self):
        base = [PM.hex_to_rgb(h) for h in L.HAM_BASE]
        row = [(0.9, 0.1, 0.1), (0.9, 0.5, 0.1), (0.2, 0.2, 0.2), (0.25, 0.8, 0.9)]
        out = L.ham_row(row, base)
        prev = base[0]
        for rgb, code in out:
            if code < 16:
                self.assertEqual(rgb, base[code])
            else:
                k = code - 16
                self.assertEqual([a for t, (a, b) in enumerate(zip(rgb, prev)) if t != k],
                                 [b for t, (a, b) in enumerate(zip(rgb, prev)) if t != k])
                self.assertAlmostEqual(rgb[k] * 15.0, round(rgb[k] * 15.0))
            prev = rgb
        self.assertEqual(out[2][1], 3)                                          # 0.2 grey = base 3 (0x333)


class Font(unittest.TestCase):
    def test_basic_contiguous(self):
        for k in range(94):
            self.assertEqual(L.GLYPH_INDEX[0x21 + k], k)                         # GLSL: glyph = ch - 33
        self.assertEqual(L.glyph_index(' '), -1)
        self.assertEqual(L.GLYPH_RANGES['blocks'], (94, 126))

    def test_A(self):
        g = L.glyph_index('A')
        rows = [''.join('X' if L.font_bit(g, x, y) else '.' for x in range(8)) for y in range(8)]
        self.assertEqual(rows[0], '..XX....')
        self.assertEqual(rows[4], 'XXXXXX..')

    def test_words(self):
        g = L.glyph_index('A')
        lo, hi = L.glyph_words(g)
        self.assertEqual(lo & 0xff, 0x0C)
        self.assertEqual(hi >> 24, 0x00)
        self.assertNotIn('const uint FONT[', L.font_glsl())          # live 31550: big const arrays cost ~3 ms
        rows = L.font_table_rows()                                      # font texture: lo / hi 16 bits per word
        self.assertEqual(rows[0], ['lo', 'hi'])
        self.assertEqual(len(rows), 1 + 2 * L.NGLYPH)
        self.assertEqual(int(rows[1 + 2 * g][0]) | (int(rows[1 + 2 * g][1]) << 16), lo)
        self.assertEqual(int(rows[2 + 2 * g][0]) | (int(rows[2 + 2 * g][1]) << 16), hi)

    def test_smooth_fills_diagonal_only(self):
        g = L.glyph_index('&')                                                  # 1-px diagonals (font8x8 is mostly 2 px)
        n0 = sum(L.font_bit(g, x >> 1, y >> 1) for x in range(16) for y in range(16))
        n1 = sum(L.font_bit_smooth(g, x, y) for x in range(16) for y in range(16))
        self.assertGreater(n1, n0)
        g = L.glyph_index('H')                                                  # no diagonals: unchanged
        self.assertEqual(sum(L.font_bit(g, x >> 1, y >> 1) for x in range(16) for y in range(16)),
                         sum(L.font_bit_smooth(g, x, y) for x in range(16) for y in range(16)))

    def test_ramps(self):
        self.assertEqual(L.ramp('ascii')[0], -1)
        self.assertEqual(L.ramp('ascii')[-1], L.glyph_index('@'))
        self.assertEqual(len(L.ramp('dense')), L.RAMP_MAX)
        c = L.ramp('custom', '#. ')
        self.assertEqual(c, [-1, L.glyph_index('.'), L.glyph_index('#')])
        for cs in L.CHARSETS:
            g = L.ramp(cs, 'abc')
            self.assertEqual(L.ramp_unpack(L.ramp_packed(cs, 'abc')), g)
            self.assertTrue(all(v < 2 ** 24 for v in L.ramp_packed(cs, 'abc')))

    def test_shape_match(self):
        g = L.glyph_index('X')
        lo, hi = L.glyph_words(g)
        self.assertEqual(L.shape_match(lo, hi, 0, L.NGLYPH), (g, False, 0))
        inv_lo, inv_hi = (~lo) & 0xffffffff, (~hi) & 0xffffffff
        self.assertEqual(L.shape_match(inv_lo, inv_hi, 0, L.NGLYPH), (g, True, 0))
        self.assertEqual(L.shape_match(0, 0, 0, L.NGLYPH)[:2], (-1, False))


class Teletext(unittest.TestCase):
    def test_pack(self):
        v = L.tt_pack(65, 3, 4, flash=1, dht=1, img=1)
        self.assertLess(v, 2 ** 24)
        d = L.tt_unpack(v)
        self.assertEqual((d['ch'], d['fg'], d['bg'], d['flash'], d['dht'], d['img']), (65, 3, 4, 1, 1, 1))

    def test_mosaic(self):
        self.assertEqual(L.mosaic_mask(0x20), 0)
        self.assertEqual(L.mosaic_mask(0x7F), 63)
        self.assertEqual(L.mosaic_mask(0x21), 1)
        self.assertEqual(L.mosaic_mask(0x60), 32)
        self.assertEqual(L.mosaic_mask(0x41), -1)

    def test_row_attributes_take_a_cell(self):
        row = [L.tt_unpack(v) for v in L.tt_row('{red}AB{gyellow}\x7f', 8)]
        self.assertEqual([r['ch'] for r in row[:5]], [32, 65, 66, 32, 0x7F])
        self.assertEqual(row[1]['fg'], 1)
        self.assertEqual((row[4]['fg'], row[4]['mosaic']), (3, 1))
        self.assertEqual(len(row), 8)

    def test_bg_and_literal(self):
        row = [L.tt_unpack(v) for v in L.tt_row('{blue}{bg}{white}x{nope}', 12)]
        self.assertEqual(row[3]['bg'], 4)
        self.assertEqual(row[3]['fg'], 7)
        self.assertEqual(''.join(chr(r['ch']) for r in row[4:10]), '{nope}')

    def test_page_double_height(self):
        cells = L.tt_page(['{dh}BIG', 'next'], 10, 6, image_body=True)
        rows = [[L.tt_unpack(v) for v in cells[r * 10:(r + 1) * 10]] for r in range(6)]
        self.assertEqual(rows[0][1]['dht'], 1)
        self.assertEqual(rows[1][1]['dhb'], 1)
        self.assertEqual(rows[1][1]['ch'], ord('B'))
        self.assertEqual(chr(rows[2][0]['ch']), 'n')                              # moved down one row
        self.assertEqual(rows[5][0]['img'], 1)

    def test_subtitle(self):
        cells = L.tt_subtitle('Hello|world', 20, 10, 'yellow', double=True, row_from_bottom=1)
        rows = [[L.tt_unpack(v) for v in cells[r * 20:(r + 1) * 20]] for r in range(10)]
        text = [''.join(chr(c['ch']) for c in r if not c['img']).strip() for r in rows]
        self.assertIn('Hello', text)
        self.assertIn('world', text)
        self.assertEqual(rows[0][0]['img'], 1)

    def test_header_12h(self):
        tm = (2026, 10, 26, 18, 30, 45, 0)
        self.assertEqual(L.header_text('%a %d %b %l:%M/%S %p', tm), 'Mon 26 Oct  6:30/45 PM')
        self.assertEqual(L.clock12(0, 5), '12:05 AM')
        self.assertLessEqual(len(L.header_text(L.DEFAULT_HEADER.replace('{yellow}', ' '), tm, '100')), 40)

    def test_sixel_choose(self):
        pal = [PM.hex_to_rgb(h) for h in L.TELETEXT]
        six = [pal[1], pal[1], pal[4], pal[4], pal[1], pal[4]]
        f, b, mask = L.sixel_choose(six)
        self.assertEqual({f, b}, {1, 4})
        self.assertEqual(mask if f == 1 else (~mask) & 63, 0b010011)
        self.assertEqual(L.sixel_of(0.2, 0.1), 0)
        self.assertEqual(L.sixel_of(0.7, 0.5), 3)
        self.assertEqual(L.sixel_of(0.7, 0.95), 5)

    def test_grid(self):
        self.assertEqual(L.tt_grid(1080, 1920, 40, 25)[:2], (40, 25))
        cols, rows, cw, ch = L.tt_grid(1080, 1920, 40, 0, 1.2)
        self.assertEqual(rows, 59)


class Displays(unittest.TestCase):
    def test_grids(self):
        self.assertEqual(L.dot_grid(1080, 1920, 12), (12, 90, 160))
        cw, ch, x0, y0 = L.cell_layout(1080, 1920, 4, 1, 1.8)
        self.assertEqual((cw, ch, x0), (270.0, 486.0, 0.0))
        self.assertAlmostEqual(y0, (1920 - 486) / 2.0)
        cw, ch, x0, y0 = L.cell_layout(1080, 1920, 2, 8, 1.4)
        self.assertAlmostEqual(ch * 8, 1920.0)
        self.assertEqual(L.state_size('splitflap', 1080, 1920, 12, 10, 4), (10, 4))
        self.assertEqual(L.state_size('lcd', 1080, 1920, 12, 10, 4), (90, 160))

    def test_codes(self):
        tm = (2026, 10, 26, 18, 30, 45, 0)
        c = L.display_codes('nixie', 'clock', '', 0, '', tm, 8, 1)
        self.assertEqual(c, [0, 7, 11, 4, 1, 11, 5, 6])                          # ' 6:30:45' -> digit + 1, ':' = 11
        c = L.display_codes('nixie', 'clock', '', 0, '', (2026, 10, 26, 22, 0, 30, 0), 8, 1)
        self.assertEqual(c, [2, 1, 11, 1, 1, 11, 4, 1])                          # '10:00:30': all 8 tubes
        c = L.display_codes('splitflap', 'text', 'HI', 0, '', tm, 4, 1, 'right')
        self.assertEqual(c, [1, 1, L.FLAP_ALPHABET.index('H') + 1, L.FLAP_ALPHABET.index('I') + 1])
        c = L.display_codes('lcd', 'value', '', 3.14159, '{:.2f}', tm, 4, 1)
        self.assertEqual(c, [L.glyph_index(ch) + 1 for ch in '3.14'])
        self.assertEqual(L.display_codes('lcd', 'image', '', 0, '', tm, 4, 1), [])
        self.assertEqual(L.content_text('clock', '', 0, '', tm, 'splitflap'), '6:30 PM')

    def test_flap(self):
        n = len(L.FLAP_ALPHABET)
        cur, st, t, flips = 0, -1.0, 0.0, 0
        target = L.FLAP_ALPHABET.index('C')
        while cur != target and t < 10:
            c2, st2 = L.flap_step(cur, st, target, t, 0.05, n)
            if c2 != cur:
                flips += 1
            cur, st = c2, st2
            t += 1.0 / 60.0
        self.assertEqual(cur, target)
        self.assertEqual(flips, L.flaps_needed(0, target))
        self.assertAlmostEqual(t, 3 * 0.05 + 3 * (1.0 / 60.0), delta=4.0 / 60.0)
        self.assertEqual(len(L.flap_glyphs()), n)
        self.assertEqual(L.flap_glyphs()[0], -1)

    def test_flip_lcd_eink(self):
        self.assertAlmostEqual(L.flip_scale(0.5), 0.0, places=9)
        self.assertEqual(L.flip_delay('columns', 45, 0, 90, 160, 1.0), 0.5)
        self.assertAlmostEqual(L.lcd_step(0.0, 1.0, 0.1, 0.1, 0.3), 1 - 2.718281828 ** -1, places=6)
        self.assertEqual(L.lcd_step(0.0, 1.0, 0.1, 0.0, 0.3), 1.0)
        self.assertEqual([L.eink_phase(t, 1.0) for t in (0.1, 0.3, 0.6, 0.9, 1.2)],
                         ['inverted', 'black', 'white', 'fadein', 'done'])
        self.assertAlmostEqual(L.eink_partial(1.0, 0.0, 0.25), 0.25)

    def test_nixie(self):
        segs, rng = L.nixie_segments()
        self.assertEqual(len(rng), 10)
        self.assertLess(L.nixie_dist(1, 0.5, 0.5), 1e-9)
        self.assertGreater(L.nixie_dist(1, 0.1, 0.5), 0.3)
        self.assertLess(L.nixie_dist(0, 0.08, 0.5), 1e-6)
        for x0, y0, x1, y1 in segs:
            for v in (x0, y0, x1, y1):
                self.assertTrue(-0.05 <= v <= 1.05)
        self.assertIn('NIXRANGE[10]', L.nixie_glsl())


# ==================================================================================================== GLSL
@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, what):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.comp')
            with open(p, 'w') as fh:
                fh.write(STUB + text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:3000]))

    def test_modules(self):
        for name in MODS:
            M = module(name)
            for opn, text in M['shader_texts'](lib).items():
                self._ok(text, '%s.%s' % (name, opn))


# ==================================================================================================== dry build
class _Par:
    def __init__(self):
        self.val, self.expr, self.mode = None, '', 'c'

    def eval(self):
        return self.val


class _Pars:
    def __getattr__(self, k):
        if k.startswith('__'):
            raise AttributeError(k)
        p = _Par()
        object.__setattr__(self, k, p)
        return p

    def __setattr__(self, k, v):
        getattr(self, k).val = v


class _Conn:
    def __init__(self):
        self.connections = []

    def connect(self, src):
        self.connections = [types.SimpleNamespace(owner=src)]


class _Op:
    def __init__(self, cls, name):
        self.OPType, self.name, self.par, self.text, self.comment = cls, name, _Pars(), '', ''
        self.inputConnectors = [_Conn() for _ in range(3)]
        self.seq = types.SimpleNamespace(vec=types.SimpleNamespace(numBlocks=1),
                                         array=types.SimpleNamespace(numBlocks=0))
        self.children = {}
        self.customPages = []
        self.path = '/fake/' + name
        self.dock = None

    def op(self, n):
        return self.children.get(n)

    # Table DAT bits (T-107: a new table holds one empty cell)
    rows_ = None

    @property
    def numRows(self):
        return 1 if self.rows_ is None else len(self.rows_)

    def __getitem__(self, rc):
        if self.rows_ is None:
            return types.SimpleNamespace(val='')
        return types.SimpleNamespace(val=self.rows_[rc[0]][rc[1]])

    def clear(self):
        self.rows_ = []

    def appendRow(self, r):
        self.rows_.append(list(r))

    def create(self, cls, n):
        o = _Op(cls.__name__, n)
        self.children[n] = o
        return o

    def appendCustomPage(self, n):
        pg = types.SimpleNamespace(name=n, appendFloat=lambda nm, label='': [getattr(self.par, nm)])
        self.customPages.append(pg)
        return pg


class DryBuild(unittest.TestCase):
    """build(m, H, Lg) of every module against a fake TD with the rack's real helpers: every op, par, uniform and
    wire the module makes; catches name typos, >3 wired GLSL inputs and uniform expressions that do not compile."""

    def run_build(self, name):
        cls = dict((c, type(c, (), {})) for c in ('inTOP', 'outTOP', 'glslTOP', 'textDAT', 'switchTOP', 'selectTOP',
                                                    'scriptCHOP', 'parameterexecuteDAT', 'constantTOP', 'tableDAT'))
        ns = dict(RACK)
        ns.update(cls)
        ns['ParMode'] = types.SimpleNamespace(EXPRESSION='e', CONSTANT='c')
        ns['safe_destroy'] = lambda o: None
        exec(_read(os.path.join(BUILDERS, 'fx_retro.py')), ns)                # helpers bound to the fake classes
        exec(_read(os.path.join(BUILDERS, 'fx_retro_%s.py' % name)), ns)
        m = _Op('baseCOMP', name + '1')
        stages = ns['build'](m, ns['H'], LG)
        for s in stages:
            for n in s['ops']:
                self.assertIn(n, m.children, (name, n))
        self.assertEqual(m.op('out1').inputConnectors[0].connections[0].owner.name, 'out_sel')
        for o in m.children.values():
            if o.OPType == 'glslTOP':
                for k in range(8):
                    nm = getattr(o.par, 'vec%dname' % k).val
                    if nm:
                        self.assertIn('uniform vec4 %s;' % nm, m.op(o.name + '_compute').text, (name, o.name, nm))
                        for c in 'xyzw':
                            compile(getattr(o.par, 'vec%dvalue%s' % (k, c)).expr, '<expr>', 'eval')
                for k in range(2):
                    an = getattr(o.par, 'array%dname' % k).val
                    if an:
                        self.assertIn('uniform samplerBuffer %s;' % an, m.op(o.name + '_compute').text)
            for pn in ('index',):
                e = getattr(o.par, pn).expr
                if e:
                    compile(e, '<expr>', 'eval')
        return m

    def test_all(self):
        for name in MODS:
            self.run_build(name)


# ==================================================================================================== checks + adapters
def _checks():
    ns = {'__name__': 'fx_retro_checks'}
    exec(_read(os.path.join(BUILDERS, 'fx_retro_checks.py')), ns)
    return ns


@unittest.skipUnless(np is not None, 'numpy')
class ChecksNumpy(unittest.TestCase):
    def setUp(self):
        self.C = _checks()

    def test_np_pick_matches_logic(self):
        rng = np.random.default_rng(3)
        pal = [PM.hex_to_rgb(h) for h in L.machine_hex('pico8')]
        rgb = rng.random((300, 3))
        thr = rng.random(300)
        got = self.C['np_pick'](rgb, pal, thr=thr, amount=0.8)
        want = [L.pick(tuple(c), pal, t, 0.8) for c, t in zip(rgb, thr)]
        self.assertEqual(got.tolist(), want)
        self.assertEqual(self.C['np_pick'](rgb, pal).tolist(), [L.pick(tuple(c), pal) for c in rgb])

    def test_np_bayer(self):
        b = self.C['np_bayer'](16, 16, 3)
        for y in range(16):
            for x in range(16):
                self.assertAlmostEqual(b[y, x], L.bayer(x & 7, y & 7, 3))

    def test_blocks(self):
        a = np.zeros((8, 12, 4))
        a[:4, :6, 0] = 1.0
        m = self.C['block_means'](a, 6, 4)
        self.assertEqual(m.shape, (2, 2, 4))
        self.assertEqual(m[0, 0, 0], 1.0)
        a8 = np.round(a * 255).astype(int)
        self.assertEqual(self.C['block_uniform'](a8, 6, 4), 0)
        self.assertEqual(self.C['block_uniform'](a8, 4, 4), 1)

    def test_bilinear_centre(self):
        img = np.arange(12, dtype=float).reshape(3, 4, 1)
        self.assertEqual(self.C['bilinear'](img, np.array(1.5), np.array(0.5))[0], 1.0)
        self.assertEqual(self.C['bilinear'](img, np.array(2.0), np.array(0.5))[0], 1.5)

    def test_ham_violations(self):
        base = [PM.hex_to_rgb(h) for h in L.HAM_BASE]
        row = [(0.9, 0.2, 0.1), (0.9, 0.6, 0.1), (0.1, 0.1, 0.8), (0.5, 0.5, 0.5)]
        out = [tuple(int(round(v * 255)) for v in rgb) for rgb, _c in L.ham_row(row, base)]
        b8 = [self.C['hex8'](h) for h in L.HAM_BASE]
        self.assertEqual(self.C['ham_violations'](out, b8), 0)
        self.assertEqual(self.C['ham_violations']([(255, 0, 0), (0, 255, 255)], b8), 1)   # R alone ok, then 3 ch

    def test_cell_bounds(self):
        b = self.C['cell_bounds'](40, 1080 / 40.0)
        self.assertEqual(b[0], 0)
        self.assertEqual(b[-1], 1080)

    def test_luma_quant(self):
        q = self.C['luma_quant'](L, 2)
        self.assertEqual(q((0.6, 0.6, 0.6)), [1.0, 1.0, 1.0])

    def test_check_table(self):
        for cid, (mod, inp, pars, wait) in self.C['CHECKS'].items():
            self.assertIn(mod, MODS, cid)
            self.assertIn(inp, RACK['INPUTS'], cid)
            M = module(mod)
            names = set()
            for _pg, plist in M['PAGES']:
                for pn, style, _d, o in plist:
                    names.add(pn)
                    if style == 'RGB':
                        names.update(pn + c for c in 'rgb')
                    if style == 'Menu' and pn in pars:
                        self.assertIn(pars[pn], o['names'], (cid, pn))
            for k in pars:
                self.assertIn(k, names, (cid, k))


class _FakeDat:
    def __init__(self, lines):
        self.lines = lines

    def rows(self):
        return [[types.SimpleNamespace(val=l)] for l in self.lines]


def _fake_module(module_name, **vals):
    M = module(module_name)
    pars = types.SimpleNamespace()
    for _pg, plist in M['PAGES']:
        for pn, style, default, _o in plist:
            v = vals.get(pn, default)
            setattr(pars, pn, types.SimpleNamespace(eval=(lambda v=v: v)))
    page = _FakeDat(L.DEFAULT_PAGE)
    return types.SimpleNamespace(par=pars, op=lambda n: page if n == 'page' else None)


class Adapters(unittest.TestCase):
    T = (2026, 10, 26, 18, 30, 45, 0)

    def test_teletext(self):
        m = _fake_module('teletext', Mode='image')
        self.assertEqual(len(L.teletext_codes_td(m, self.T, 1080, 1920)), 40 * 59)
        m = _fake_module('teletext', Mode='page', Rows=25, Pagedat='')
        c = L.teletext_codes_td(m, self.T, 1080, 1920)
        self.assertEqual(len(c), 1000)
        hdr = ''.join(chr(L.tt_unpack(v)['ch']) for v in c[:40])
        self.assertIn('Mon 26 Oct', hdr)
        self.assertIn('6:30/45 PM', hdr)
        m = _fake_module('teletext', Mode='subtitle', Rows=25, Subtitle='Hi there')
        c = L.teletext_codes_td(m, self.T, 1080, 1920)
        self.assertTrue(any(L.tt_unpack(v)['ch'] == ord('H') and not L.tt_unpack(v)['img'] for v in c))

    def test_display(self):
        m = _fake_module('smalldisplay', Display='nixie', Content='clock', Columns=8, Rows=1)
        self.assertEqual(L.display_codes_td(m, self.T, 1080, 1920), [0, 7, 11, 4, 1, 11, 5, 6])
        m = _fake_module('smalldisplay', Display='lcd', Content='text', Text='HI', Dotsize=12.0, Align='left')
        c = L.display_codes_td(m, self.T, 1080, 1920)
        self.assertEqual(len(c), (90 // 8) * (160 // 8))
        self.assertEqual(c[:3], [L.glyph_index('H') + 1, L.glyph_index('I') + 1, 0])
        m = _fake_module('smalldisplay', Display='lcd', Content='image')
        self.assertEqual(L.display_codes_td(m, self.T, 1080, 1920), [])



# ---- slot_gate (T-201): same checks as test_fx_glitch SlotGate, on this rack's copy of the gate
_GATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'builders', 'fx_retro.py')
with open(_GATE_FILE) as _fh:
    GATE_SRC = _fh.read()
GATE_NS = {}
exec(GATE_SRC, GATE_NS)

class _GCell(object):
    def __init__(self, v):
        self.val = v


class _GTable(object):
    def __init__(self, rows):
        self.rows = rows                                  # {name: {col: val}}

    def __getitem__(self, k):
        r = self.rows.get(k[0])
        return None if r is None or k[1] not in r else _GCell(r[k[1]])


class _GRack(object):
    def __init__(self, rows):
        self.t = None if rows is None else _GTable(rows)

    def op(self, n):
        return self.t if n == 'slots' else None


def _Ggate_index(rows, name='m1'):
    """Evaluate SLOT_GATE_E the way TD does, with parent() = the module, parent(2) = the rack."""
    from types import SimpleNamespace as S
    mod, rack = S(name=name), _GRack(rows)
    return eval(GATE_NS['SLOT_GATE_E'], {'parent': lambda n=1: mod if n == 1 else rack, 'getattr': getattr,
                                     'float': float, 'int': int})


class _GConn(object):
    def __init__(self, owner, inp=False):
        self.owner, self.inp, self.connections = owner, inp, []

    def connect(self, src):
        src = src if isinstance(src, _GConn) else src.outputConnectors[0]
        self.connections = [src]


class _GPar(object):
    def __init__(self):
        self.expr, self.mode = '', None


class _GOp(object):
    def __init__(self, name, typ, parent_=None):
        from types import SimpleNamespace as S
        self.name, self.OPType, self.valid, self.isCOMP, self.viewer, self.comment = name, typ, True, False, False, ''
        self.inputConnectors = [_GConn(self, True) for _ in range(3)]
        self.outputConnectors = [_GConn(self)]
        self.par = S(index=_GPar())
        self.parent_ = parent_


class _GMod(object):
    def __init__(self, src_name='fx', src_expr=''):
        self.kids = {}
        for n, t in (('in1', 'inTOP'), ('out1', 'outTOP'), (src_name, 'switchTOP')):
            self.kids[n] = _GOp(n, t, self)
        self.kids[src_name].par.index.expr = src_expr
        self.kids[src_name].inputConnectors[0].connect(self.kids['in1'])
        self.kids['out1'].inputConnectors[0].connect(self.kids[src_name])

    def op(self, n):
        return self.kids.get(n)

    def create(self, cls, n):
        self.kids[n] = _GOp(n, cls.__name__, self)
        return self.kids[n]


class _GswitchTOP(object):  # noqa: N801  (TD's class name, only __name__ is read)
    pass


class _GParMode(object):
    EXPRESSION = 'expr'


def _Gsrc_of(o, i=0):
    c = o.inputConnectors[i].connections
    return c[0].owner.name if c else None


class SlotGate(unittest.TestCase):
    """T-198 for every rack: a slot that is off (enabled 0 / mix <= 0) passes in1 inside the module, so a visible
    <name>_mix viewer no longer pulls the module; on = the module's own output, unchanged."""

    def test_slot_off_matches_slot_switch(self):
        so = GATE_NS['slot_off']
        for en, mx, off in (('1', '1', False), ('1', '0.5', False), ('0', '1', True), ('1', '0', True),
                            ('', '1', True), ('1', '', True), ('1', '-1', True), ('1.0', '1', False),
                            (None, None, False)):
            self.assertEqual(so(en, mx), off, (en, mx))
            sw = 0 if not int(float(en or 0)) or float(mx or 0) <= 0 else 1   # the rack's <name>_slot index test
            if en is not None:
                self.assertEqual(off, sw == 0)

    def test_gate_expression(self):
        self.assertEqual(_Ggate_index({'m1': {'enabled': '1', 'mix': '1'}}), 1)
        self.assertEqual(_Ggate_index({'m1': {'enabled': '1', 'mix': '0.3'}}), 1)
        self.assertEqual(_Ggate_index({'m1': {'enabled': '0', 'mix': '1'}}), 0)
        self.assertEqual(_Ggate_index({'m1': {'enabled': '1', 'mix': '0'}}), 0)
        self.assertEqual(_Ggate_index({}), 1)                       # no row = on
        self.assertEqual(_Ggate_index(None), 1)                     # no slots table = on

    def test_gate_needed(self):
        self.assertTrue(GATE_NS['gate_needed']('out_sel', '0 if parent().par.Amount.eval() <= 0 else 1'))
        self.assertTrue(GATE_NS['gate_needed']('fx', ''))
        self.assertFalse(GATE_NS['gate_needed']('out_sel', "0 if parent(2).op('slots') is not None else 1"))

    def test_stages(self):
        st = GATE_NS['gate_stages']([{'ops': ['in1']}, {'ops': ['out_sel', 'out1']}])
        self.assertEqual(st[1]['ops'], ['out_sel', 'slot_gate', 'out1'])
        self.assertEqual(GATE_NS['gate_stages'](st)[1]['ops'], ['out_sel', 'slot_gate', 'out1'])   # idempotent
        self.assertEqual(GATE_NS['gate_stages']([{'ops': ['fx']}])[0]['ops'], ['fx', 'slot_gate'])

    def _ns(self):
        ns = {'switchTOP': _GswitchTOP, 'ParMode': _GParMode}
        exec(GATE_SRC, ns)                                        # rack functions bound to the fake TD globals
        ns['_sd'] = lambda o: None
        return ns

    def test_wiring_idempotent(self):
        ns = self._ns()
        m = _GMod()
        st = ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])
        g = m.op('slot_gate')
        self.assertEqual((_Gsrc_of(g, 0), _Gsrc_of(g, 1), _Gsrc_of(m.op('out1'))), ('in1', 'fx', 'slot_gate'))
        self.assertEqual(g.par.index.expr, GATE_NS['SLOT_GATE_E'])
        self.assertEqual(st[0]['ops'], ['fx', 'slot_gate', 'out1'])
        m.op('out1').inputConnectors[0].connect(m.op('fx'))      # a module rebuild re-wires out1 to its source
        ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])
        self.assertEqual((_Gsrc_of(g, 0), _Gsrc_of(g, 1), _Gsrc_of(m.op('out1'))), ('in1', 'fx', 'slot_gate'))
        ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])           # already gated: unchanged
        self.assertEqual(_Gsrc_of(m.op('out1')), 'slot_gate')

    def test_slot_aware_out_sel_left_alone(self):              # GEN_points OUT_SEL_E
        ns = self._ns()
        m = _GMod('out_sel', "0 if parent().par.Amount.eval() <= 0 or (parent(2).op('slots') is not None) else 1")
        ns['_slot_gate'](m, [{'ops': ['out_sel', 'out1']}])
        self.assertIsNone(m.op('slot_gate'))
        self.assertEqual(_Gsrc_of(m.op('out1')), 'out_sel')


def _Gfamily_src(name):
    with open(os.path.join(BDIR, name + '.py')) as fh:
        return fh.read()


def _Ginstance_body(src):
    i = src.find('\ndef _instance(')
    if i < 0:
        return None
    j = src.find('\ndef ', i + 1)
    return src[i:j if j > 0 else len(src)]



class GateInInstance(unittest.TestCase):
    def test_instance_gates(self):
        i = GATE_SRC.index('\ndef _instance(')
        self.assertIn("stages = _slot_gate(m, M['build'](m, H, Lg))", GATE_SRC[i:GATE_SRC.index('\ndef ', i + 1)])
        self.assertIn('def gate_upgrade(', GATE_SRC)


if __name__ == '__main__':
    unittest.main()
