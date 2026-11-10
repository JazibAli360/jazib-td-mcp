"""Offline tests for builders/palette_map_logic.py (FX_palette_map). Run:
python3 -I -m unittest discover -s test -p 'test_palette_map.py'"""
import json
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'builders'))
import palette_map_logic as L  # noqa: E402


def ase_bytes(swatches):
    """Build a minimal ASE file: swatches = [(name, model, floats)]."""
    blocks = b''
    for name, model, vals in swatches:
        nm = (name + '\0').encode('utf-16-be')
        body = struct.pack('>H', len(nm) // 2) + nm + model + struct.pack('>' + 'f' * len(vals), *vals) + struct.pack('>H', 2)
        blocks += struct.pack('>HI', 0x0001, len(body)) + body
    grp = struct.pack('>HI', 0xC001, 0)
    return b'ASEF' + struct.pack('>HHI', 1, 0, len(swatches) + 1) + grp + blocks


class Hex(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(L.norm_hex('#ca47e9'), 'CA47E9')
        self.assertEqual(L.norm_hex('0xCA47E9'), 'CA47E9')
        self.assertEqual(L.norm_hex('c4e'), 'CC44EE')
        self.assertEqual(L.norm_hex('#CA47E9FF'), 'CA47E9')
        self.assertEqual(L.norm_hex('FFCA47E9', argb=True), 'CA47E9')
        for bad in ('', 'xyz', '#12345', 'red'):
            self.assertIsNone(L.norm_hex(bad))

    def test_roundtrip(self):
        self.assertEqual(L.rgb_to_hex(L.hex_to_rgb('1D2B53')), '1D2B53')

    def test_table_rows(self):
        good, bad = L.parse_hex_list([['hex'], ['#ff0000'], ['bogus'], [''], ['00ff00']])
        self.assertEqual(good, ['FF0000', '00FF00'])
        self.assertEqual(bad, ['bogus'])


class Presets(unittest.TestCase):
    def test_counts(self):
        n = {k: len(c) for k, _l, _a, _s, c in L.PRESETS}
        self.assertEqual(n['pico8'], 16)
        self.assertEqual(n['sweetie16'], 16)
        self.assertEqual(n['endesga32'], 32)
        self.assertEqual(n['resurrect64'], 64)
        self.assertEqual(n['aap64'], 64)
        self.assertEqual(n['apollo'], 46)
        self.assertEqual(n['gameboy'], 4)
        self.assertEqual(n['solarized'], 16)

    def test_all_valid_unique_keys(self):
        self.assertEqual(len(set(L.PRESET_KEYS)), len(L.PRESET_KEYS))
        for k, _l, _a, _s, cols in L.PRESETS:
            for h in cols:
                self.assertEqual(L.norm_hex(h), h, k)

    def test_pico8_values(self):
        self.assertEqual(L.preset('pico8')[:4], ['000000', '1D2B53', '7E2553', '008751'])

    def test_menu(self):
        self.assertEqual(L.PALETTE_MENU[0][0], 'custom')
        self.assertEqual(L.menu_index(L.PALETTE_MENU, 'pico8'), 2)
        self.assertEqual(L.menu_index(L.DITHER, 'nope'), 0)

    def test_resolve(self):
        self.assertEqual(L.resolve('custom', [['#000'], ['fff']]), ['000000', 'FFFFFF'])
        self.assertEqual(L.resolve('file', [], ['ABCDEF']), ['ABCDEF'])
        self.assertEqual(len(L.resolve('db32', [])), 32)
        self.assertEqual(L.resolve('missing', []), [])


class Files(unittest.TestCase):
    def test_hex_and_txt(self):
        self.assertEqual(L.parse_file('a.hex', b'ff004d\n29adff\n'), ['FF004D', '29ADFF'])
        txt = b';paint.net Palette File\n;Colors: 2\nFFFF004D\nFF29ADFF\n'
        self.assertEqual(L.parse_file('a.txt', txt), ['FF004D', '29ADFF'])
        self.assertEqual(L.parse_file('a.txt', b'#FF004D80\n'), ['FF004D'])

    def test_json(self):
        self.assertEqual(L.parse_file('a.json', json.dumps(['#112233', 'aabbcc']).encode()), ['112233', 'AABBCC'])
        lospec = {'name': 'x', 'author': '', 'colors': ['000000', 'ffffff']}
        self.assertEqual(L.parse_file('a.json', json.dumps(lospec).encode()), ['000000', 'FFFFFF'])
        self.assertEqual(L.parse_file('a.json', json.dumps({'bg': '#010203', 'fg': '#040506'}).encode()),
                         ['010203', '040506'])

    def test_gpl(self):
        g = b'GIMP Palette\nName: t\nColumns: 4\n#\n  0   0   0\tBlack\n255 241 232 White\n'
        self.assertEqual(L.parse_file('a.gpl', g), ['000000', 'FFF1E8'])

    def test_jasc(self):
        self.assertEqual(L.parse_file('a.pal', b'JASC-PAL\r\n0100\r\n2\r\n255 0 77\r\n41 173 255\r\n'),
                         ['FF004D', '29ADFF'])

    def test_ase(self):
        data = ase_bytes([('red', b'RGB ', (1.0, 0.0, 0.0)), ('k', b'CMYK', (0, 0, 0, 1)),
                          ('blue', b'RGB ', (0.0, 0.0, 1.0)), ('g', b'Gray', (0.5,))])
        self.assertEqual(L.parse_file('a.ase', data), ['FF0000', '0000FF'])
        self.assertEqual(L.parse_ase(b'nope'), [])


class Colour(unittest.TestCase):
    def test_oklab_reference(self):
        # Ottosson's published OKLab values: white (1, 0, 0), sRGB red (0.62796, 0.22486, 0.12585)
        w = L.srgb_to_oklab((1.0, 1.0, 1.0))
        self.assertAlmostEqual(w[0], 1.0, places=4)
        self.assertAlmostEqual(w[1], 0.0, places=4)
        r = L.srgb_to_oklab((1.0, 0.0, 0.0))
        for a, b in zip(r, (0.62796, 0.22486, 0.12585)):
            self.assertAlmostEqual(a, b, places=4)

    def test_inverse(self):
        for rgb in ((0.2, 0.5, 0.9), (0.0, 0.0, 0.0), (1.0, 0.3, 0.0)):
            for a, b in zip(L.oklab_to_srgb(L.srgb_to_oklab(rgb)), rgb):
                self.assertAlmostEqual(a, b, places=5)

    def test_table(self):
        rows = L.palette_table(['FFFFFF'])
        self.assertEqual(rows[0], ['hex', 'r', 'g', 'b', 'L', 'A', 'B'])
        self.assertEqual(rows[1][:4], ['FFFFFF', '1.000000', '1.000000', '1.000000'])
        self.assertEqual(L.palette_table([])[1][:4], ['none', '0.000000', '0.000000', '0.000000'])   # empty -> black
        self.assertEqual(L.count('none', 2), 0)
        self.assertEqual(L.count('FFFFFF', 17), 16)


class Shader(unittest.TestCase):
    def test_bayer(self):
        m = L.bayer8()
        self.assertEqual(sorted(v for r in m for v in r), list(range(64)))
        self.assertEqual(m[0][:4], [0, 32, 8, 40])
        self.assertIn('float[64](0.0, 32.0', L.bayer_glsl())

    def test_nearest(self):
        pal = [L.hex_to_rgb(h) for h in ('000000', 'FFFFFF', 'FF0000')]
        self.assertEqual(L.pick((0.9, 0.1, 0.1), pal), 2)
        self.assertEqual(L.pick((0.1, 0.1, 0.1), pal), 0)
        self.assertEqual(L.pick((0.9, 0.9, 0.9), pal, space='srgb'), 1)

    def test_dither_mix(self):
        # mid grey between black and white: OKLab L 0.5 is equidistant -> about half the Bayer cells pick white
        pal = [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)]
        g = L.oklab_to_srgb((0.5, 0.0, 0.0))
        picks = [L.pick(g, pal, threshold=(v + 0.5) / 64.0) for r in L.bayer8() for v in r]
        self.assertTrue(25 <= picks.count(1) <= 39, picks.count(1))
        self.assertEqual(len(set(L.pick(g, pal, threshold=(v + 0.5) / 64.0, amount=0.0)
                                 for r in L.bayer8() for v in r)), 1)   # amount 0 = hard quantise

    def test_lightness_weight(self):
        pal = [L.hex_to_rgb(h) for h in ('202020', 'C02020')]
        src = (0.55, 0.3, 0.3)
        self.assertNotEqual(L.pick(src, pal, wl=4.0), L.pick(src, pal, wl=0.0))


if __name__ == '__main__':
    unittest.main()
