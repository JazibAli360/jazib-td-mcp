# palette_map_logic: pure logic for FX_palette_map (no td import; copied into the COMP as Text DAT palette_map_logic).
# Spec: docs/research/AZ_closest_color_palette.md section 4 (our own clean-room design).
# Presets: hex values fetched from Lospec's JSON endpoint (https://lospec.com/palette-list/<slug>.json) on 26 Oct 2026;
# Lospec palettes are shared by their authors for free use (credit the author, listed per preset). Solarized: Ethan
# Schoonover, MIT licence, values from github.com/altercation/solarized README. Black & white: trivial, no source.
# ASCII only.
import json
import struct

# (key, label, author, source, hex list)
PRESETS = [
    ('pico8', 'PICO-8', '', 'https://lospec.com/palette-list/pico-8', [
        '000000', '1D2B53', '7E2553', '008751', 'AB5236', '5F574F', 'C2C3C7', 'FFF1E8',
        'FF004D', 'FFA300', 'FFEC27', '00E436', '29ADFF', '83769C', 'FF77A8', 'FFCCAA',]),
    ('sweetie16', 'Sweetie 16', '', 'https://lospec.com/palette-list/sweetie-16', [
        '1A1C2C', '5D275D', 'B13E53', 'EF7D57', 'FFCD75', 'A7F070', '38B764', '257179',
        '29366F', '3B5DC9', '41A6F6', '73EFF7', 'F4F4F4', '94B0C2', '566C86', '333C57',]),
    ('endesga32', 'Endesga 32', 'ENDESGA', 'https://lospec.com/palette-list/endesga-32', [
        'BE4A2F', 'D77643', 'EAD4AA', 'E4A672', 'B86F50', '733E39', '3E2731', 'A22633',
        'E43B44', 'F77622', 'FEAE34', 'FEE761', '63C74D', '3E8948', '265C42', '193C3E',
        '124E89', '0099DB', '2CE8F5', 'FFFFFF', 'C0CBDC', '8B9BB4', '5A6988', '3A4466',
        '262B44', '181425', 'FF0044', '68386C', 'B55088', 'F6757A', 'E8B796', 'C28569',]),
    ('resurrect64', 'Resurrect 64', 'Kerrie Lake', 'https://lospec.com/palette-list/resurrect-64', [
        '2E222F', '3E3546', '625565', '966C6C', 'AB947A', '694F62', '7F708A', '9BABB2',
        'C7DCD0', 'FFFFFF', '6E2727', 'B33831', 'EA4F36', 'F57D4A', 'AE2334', 'E83B3B',
        'FB6B1D', 'F79617', 'F9C22B', '7A3045', '9E4539', 'CD683D', 'E6904E', 'FBB954',
        '4C3E24', '676633', 'A2A947', 'D5E04B', 'FBFF86', '165A4C', '239063', '1EBC73',
        '91DB69', 'CDDF6C', '313638', '374E4A', '547E64', '92A984', 'B2BA90', '0B5E65',
        '0B8A8F', '0EAF9B', '30E1B9', '8FF8E2', '323353', '484A77', '4D65B4', '4D9BE6',
        '8FD3FF', '45293F', '6B3E75', '905EA9', 'A884F3', 'EAADED', '753C54', 'A24B6F',
        'CF657F', 'ED8099', '831C5D', 'C32454', 'F04F78', 'F68181', 'FCA790', 'FDCBB0',]),
    ('apollo', 'Apollo', 'AdamCYounis', 'https://lospec.com/palette-list/apollo', [
        '172038', '253A5E', '3C5E8B', '4F8FBA', '73BED3', 'A4DDDB', '19332D', '25562E',
        '468232', '75A743', 'A8CA58', 'D0DA91', '4D2B32', '7A4841', 'AD7757', 'C09473',
        'D7B594', 'E7D5B3', '341C27', '602C2C', '884B2B', 'BE772B', 'DE9E41', 'E8C170',
        '241527', '411D31', '752438', 'A53030', 'CF573C', 'DA863E', '1E1D39', '402751',
        '7A367B', 'A23E8C', 'C65197', 'DF84A5', '090A14', '10141F', '151D28', '202E37',
        '394A50', '577277', '819796', 'A8B5B2', 'C7CFCC', 'EBEDE9',]),
    ('aap64', 'AAP-64', 'Adigun A. Polack', 'https://lospec.com/palette-list/aap-64', [
        '060608', '141013', '3B1725', '73172D', 'B4202A', 'DF3E23', 'FA6A0A', 'F9A31B',
        'FFD541', 'FFFC40', 'D6F264', '9CDB43', '59C135', '14A02E', '1A7A3E', '24523B',
        '122020', '143464', '285CC4', '249FDE', '20D6C7', 'A6FCDB', 'FFFFFF', 'FEF3C0',
        'FAD6B8', 'F5A097', 'E86A73', 'BC4A9B', '793A80', '403353', '242234', '221C1A',
        '322B28', '71413B', 'BB7547', 'DBA463', 'F4D29C', 'DAE0EA', 'B3B9D1', '8B93AF',
        '6D758D', '4A5462', '333941', '422433', '5B3138', '8E5252', 'BA756A', 'E9B5A3',
        'E3E6FF', 'B9BFFB', '849BE4', '588DBE', '477D85', '23674E', '328464', '5DAF8D',
        '92DCBA', 'CDF7E2', 'E4D2AA', 'C7B08B', 'A08662', '796755', '5A4E44', '423934',]),
    ('db16', 'DawnBringer 16', '', 'https://lospec.com/palette-list/dawnbringer-16', [
        '140C1C', '442434', '30346D', '4E4A4E', '854C30', '346524', 'D04648', '757161',
        '597DCE', 'D27D2C', '8595A1', '6DAA2C', 'D2AA99', '6DC2CA', 'DAD45E', 'DEEED6',]),
    ('db32', 'DawnBringer 32', '', 'https://lospec.com/palette-list/dawnbringer-32', [
        '000000', '222034', '45283C', '663931', '8F563B', 'DF7126', 'D9A066', 'EEC39A',
        'FBF236', '99E550', '6ABE30', '37946E', '4B692F', '524B24', '323C39', '3F3F74',
        '306082', '5B6EE1', '639BFF', '5FCDE4', 'CBDBFC', 'FFFFFF', '9BADB7', '847E87',
        '696A6A', '595652', '76428A', 'AC3232', 'D95763', 'D77BBA', '8F974A', '8A6F30',]),
    ('slso8', 'SLSO8', 'Luis Miguel Maldonado', 'https://lospec.com/palette-list/slso8', [
        '0D2B45', '203C56', '544E68', '8D697A', 'D08159', 'FFAA5E', 'FFD4A3', 'FFECD6',]),
    ('oil6', 'Oil 6', '', 'https://lospec.com/palette-list/oil-6', [
        'FBF5EF', 'F2D3AB', 'C69FA5', '8B6D9C', '494D7E', '272744',]),
    ('twilight5', 'Twilight 5', 'Star', 'https://lospec.com/palette-list/twilight-5', [
        'FBBBAD', 'EE8695', '4A7A96', '333F58', '292831',]),
    ('nyx8', 'Nyx8', '', 'https://lospec.com/palette-list/nyx8', [
        '08141E', '0F2A3F', '20394F', 'F6D6BD', 'C3A38A', '997577', '816271', '4E495F',]),
    ('lostcentury', 'Lost Century', 'SurrealEmber', 'https://lospec.com/palette-list/lost-century', [
        'D1B187', 'C77B58', 'AE5D40', '79444A', '4B3D44', 'BA9158', '927441', '4D4539',
        '77743B', 'B3A555', 'D2C9A5', '8CABA1', '4B726E', '574852', '847875', 'AB9B8E',]),
    ('gameboy', 'Game Boy (bgb)', '', 'https://lospec.com/palette-list/nintendo-gameboy-bgb', [
        '081820', '346856', '88C070', 'E0F8D0',]),
    ('demichrome', '2bit Demichrome', 'Space Sandwich', 'https://lospec.com/palette-list/2bit-demichrome', [
        '211E20', '555568', 'A0A08B', 'E9EFEC',]),
    ('cga0hi', 'CGA 0 (high)', '', 'https://lospec.com/palette-list/cga-palette-0-high', [
        '000000', '55FF55', 'FF5555', 'FFFF55',]),
    ('monitorglow', '1bit Monitor Glow', 'Polyducks', 'https://lospec.com/palette-list/1bit-monitor-glow', [
        '222323', 'F0F6F0',]),
    ('grey16', 'Grayscale 16', 'SZIEBERTH Adam', 'https://lospec.com/palette-list/grayscale-16', [
        '000000', '181818', '282828', '383838', '474747', '565656', '646464', '717171',
        '7E7E7E', '8C8C8C', '9B9B9B', 'ABABAB', 'BDBDBD', 'D1D1D1', 'E7E7E7', 'FFFFFF',]),
    ('solarized', 'Solarized', 'Ethan Schoonover', 'https://github.com/altercation/solarized', [
        '002B36', '073642', '586E75', '657B83', '839496', '93A1A1', 'EEE8D5', 'FDF6E3',
        'B58900', 'CB4B16', 'DC322F', 'D33682', '6C71C4', '268BD2', '2AA198', '859900',]),
    ('bw', 'Black & white', '', '', ['000000', 'FFFFFF']),
]

PRESET_KEYS = [p[0] for p in PRESETS]

# Palette menu: custom table, from file, then every preset.
PALETTE_MENU = [('custom', 'Custom (table)'), ('file', 'From file')] + [(p[0], p[1]) for p in PRESETS]
COLOURSPACE = [('oklab', 'OKLab'), ('srgb', 'sRGB')]
DITHER = [('off', 'Off'), ('bayer', 'Bayer 8x8'), ('ign', 'Noise (IGN)'), ('input', 'Noise input (in2)')]
SOURCE = [('auto', 'Auto (in1 if wired, else clip)'), ('input', 'In TOP (in1)'), ('clip', 'Stored clip'),
          ('ramp', 'Test ramp')]
FALLBACK = ['000000']          # what the shader gets when the palette is empty (Count still says 0)
HEXDIGITS = set('0123456789abcdefABCDEF')


def menu_index(menu, key):
    for i, (k, _l) in enumerate(menu):
        if k == key:
            return i
    return 0


def preset(key):
    for k, _l, _a, _s, cols in PRESETS:
        if k == key:
            return list(cols)
    return None


# ---- hex ----------------------------------------------------------------------------------------------------------
def norm_hex(tok, argb=False):
    """'#ca47e9' / 'CA47E9' / '0xCA47E9' / '#C4E' / 'RRGGBBAA' (or AARRGGBB when argb) -> 'CA47E9', else None."""
    t = str(tok).strip().strip(',;"\'')
    if t[:2].lower() == '0x':
        t = t[2:]
    elif t[:1] == '#':
        t = t[1:]
    if not t or any(ch not in HEXDIGITS for ch in t):
        return None
    if len(t) == 3:
        t = ''.join(ch * 2 for ch in t)
    elif len(t) == 8:
        t = t[2:] if argb else t[:6]
    elif len(t) != 6:
        return None
    return t.upper()


def hex_to_rgb(h):
    h = norm_hex(h)
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def rgb_to_hex(rgb):
    return ''.join('%02X' % max(0, min(255, int(round(v * 255.0)))) for v in rgb)


def parse_hex_list(rows):
    """Table rows (lists of cell strings) or lines -> hex list; bad cells are skipped (returned second)."""
    good, bad = [], []
    for r in rows:
        cells = r if isinstance(r, (list, tuple)) else [r]
        for cell in cells:
            s = str(cell).strip()
            if not s or s.startswith(';') or s.startswith('//') or s.lower() in ('hex', 'colour', 'color'):
                continue
            h = norm_hex(s)
            (good if h else bad).append(h or s)
    return good, bad


# ---- file formats (local read only) --------------------------------------------------------------------------------
def parse_text(text, ext=''):
    """.txt / .hex: one colour per line ('#' optional). Lospec / Paint.NET .txt = AARRGGBB (8 digits, no '#')."""
    ext = ext.lower()
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(';') or s.startswith('//'):
            continue
        tok = s.split()[0]
        argb = ext == '.txt' and len(tok) == 8 and not tok.startswith('#')
        h = norm_hex(tok, argb=argb)
        if h:
            out.append(h)
    return out


def parse_json(text):
    d = json.loads(text)
    if isinstance(d, dict):
        d = d.get('colors', d.get('colours', d.get('palette', list(d.values()))))
    out = []
    for v in d if isinstance(d, list) else []:
        if isinstance(v, dict):
            v = v.get('hex', v.get('color', v.get('colour', '')))
        h = norm_hex(v) if isinstance(v, str) else None
        if h:
            out.append(h)
    return out


def parse_gpl(text):
    """GIMP palette: header 'GIMP Palette', 'Name:'/'Columns:' lines, '#' comments, then 'R G B [name]'."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('GIMP') or ':' in s.split()[0]:
            continue
        parts = s.split()
        try:
            r, g, b = (int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            continue
        out.append(rgb_to_hex((r / 255.0, g / 255.0, b / 255.0)))
    return out


def parse_jasc(text):
    """JASC-PAL (.pal): 'JASC-PAL', '0100', count, then 'R G B' lines."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines or lines[0] != 'JASC-PAL':
        return []
    out = []
    for s in lines[3:]:
        parts = s.split()
        try:
            out.append(rgb_to_hex(tuple(int(p) / 255.0 for p in parts[:3])))
        except ValueError:
            continue
    return out


def parse_ase(data):
    """Adobe Swatch Exchange (binary, big-endian). RGB swatches only; CMYK / LAB / Gray skipped."""
    if len(data) < 12 or data[:4] != b'ASEF':
        return []
    n = struct.unpack('>I', data[8:12])[0]
    pos, out = 12, []
    for _ in range(n):
        if pos + 6 > len(data):
            break
        btype, blen = struct.unpack('>HI', data[pos:pos + 6])
        body = data[pos + 6:pos + 6 + blen]
        pos += 6 + blen
        if btype != 0x0001 or len(body) < 2:
            continue
        nl = struct.unpack('>H', body[:2])[0]
        q = 2 + nl * 2
        model = body[q:q + 4]
        if model == b'RGB ' and len(body) >= q + 16:
            r, g, b = struct.unpack('>fff', body[q + 4:q + 16])
            out.append(rgb_to_hex((r, g, b)))
    return out


def parse_file(path, data):
    """bytes + path -> hex list, by extension (.txt .hex .json .gpl .pal .ase); unknown = try text."""
    ext = ('.' + path.rsplit('.', 1)[-1].lower()) if '.' in path else ''
    if ext == '.ase':
        return parse_ase(data)
    text = data.decode('utf-8', 'replace')
    if ext == '.json':
        return parse_json(text)
    if ext == '.gpl' or text.startswith('GIMP Palette'):
        return parse_gpl(text)
    if ext == '.pal' or text.startswith('JASC-PAL'):
        return parse_jasc(text)
    return parse_text(text, ext)


def resolve(mode, custom_rows, file_hex=None):
    """Palette menu key -> active hex list."""
    if mode == 'custom':
        return parse_hex_list(custom_rows)[0]
    if mode == 'file':
        return list(file_hex or [])
    return preset(mode) or []


# ---- colour maths (same as the shader) ----------------------------------------------------------------------------
def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def _cbrt(x):
    return x ** (1.0 / 3.0) if x >= 0 else -((-x) ** (1.0 / 3.0))


def srgb_to_oklab(rgb):
    r, g, b = (srgb_to_linear(v) for v in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = _cbrt(l), _cbrt(m), _cbrt(s)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklab_to_srgb(lab):
    L, a, b = lab
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return tuple(linear_to_srgb(max(0.0, min(1.0, v))) for v in (r, g, bb))


def palette_table(hexes):
    """-> rows for the palette_active Script DAT: header + (hex, r, g, b, L, A, B) per colour.
    Empty palette -> one black row with hex 'none' (the shader needs one entry; Count says 0)."""
    rows = [['hex', 'r', 'g', 'b', 'L', 'A', 'B']]
    for h in (hexes or FALLBACK):
        rgb = hex_to_rgb(h)
        lab = srgb_to_oklab(rgb)
        rows.append([h if hexes else 'none'] + ['%.6f' % v for v in rgb] + ['%.6f' % v for v in lab])
    return rows


# ---- reference model of the shader (offline tests) ----------------------------------------------------------------
def bayer8():
    """8x8 Bayer threshold matrix, values 0..63 (row-major, [y][x])."""
    m = [[0]]
    while len(m) < 8:
        n = len(m)
        m = [[4 * m[y % n][x % n] + [0, 2, 3, 1][(y // n) * 2 + (x // n)] for x in range(2 * n)] for y in range(2 * n)]
    return m


def bayer_glsl():
    flat = [v for row in bayer8() for v in row]
    return 'const float BAYER[64] = float[64](' + ', '.join('%.1f' % v for v in flat) + ');'


def nearest2(src_rgb, pal_rgb, space='oklab', wl=1.0):
    """-> (best index, best dist, second index, second dist); dist = Euclidean (L weighted by wl in OKLab)."""
    if space == 'oklab':
        s = srgb_to_oklab(src_rgb)
        pts = [srgb_to_oklab(p) for p in pal_rgb]
    else:
        s, pts = src_rgb, pal_rgb
    best = (1e30, 0)
    sec = (1e30, 0)
    for i, p in enumerate(pts):
        d0 = (s[0] - p[0]) * (wl if space == 'oklab' else 1.0)
        d = d0 * d0 + (s[1] - p[1]) ** 2 + (s[2] - p[2]) ** 2
        if d < best[0]:
            sec, best = best, (d, i)
        elif d < sec[0]:
            sec = (d, i)
    return best[1], best[0] ** 0.5, sec[1], sec[0] ** 0.5


def pick(src_rgb, pal_rgb, threshold=None, amount=1.0, space='oklab', wl=1.0):
    """Index the shader picks. threshold in [0,1) (None = no dither): second colour wins when t * amount > threshold,
    t = d1 / (d1 + d2) (0 on the best colour, 0.5 midway)."""
    i1, d1, i2, d2 = nearest2(src_rgb, pal_rgb, space, wl)
    if threshold is None or len(pal_rgb) < 2:
        return i1
    t = d1 / (d1 + d2) if (d1 + d2) > 0 else 0.0
    return i2 if t * amount > threshold else i1


def count(first_hex, rows):
    """Count par: real entries in palette_active (0 when it only holds the 'none' fallback row)."""
    return 0 if first_hex in (None, 'none') else max(0, rows - 1)


# ==================================================================================================================
# Shared palette convention (lane W1-B, 27 Oct 2026; doc docs/builds/palette_convention.md; GLSL builders/glsl/
# px_palette.glsl). Everything above is FX_palette_map's and unchanged. A palette SPEC (JSON-able dict) ->
# uPal[16] rows (r g b pos) + uPalCtl (count, shift, mode, interp). pal_eval / pal_step / colsrc_eval mirror the GLSL.
# ==================================================================================================================
import math

PAL_MAX = 16
PAL_MODES = [('gradient', 'Gradient (positioned stops)'), ('steps', 'Steps (equal bands)'),
             ('cycle', 'Cycle (wraps, last -> first)')]
PAL_INTERP = [('rgb', 'RGB'), ('oklab', 'OKLab')]
PAL_CHANNELS = ('r', 'g', 'b', 'pos')          # CHOP channel order = vec4 x y z w of uPal[i]
COLSRC_MODES = [('solid', 'Solid colour'), ('palette', 'Palette at position'), ('attr', 'Palette by attribute'),
                ('source', 'Keep source colour'), ('index', 'Palette stop by index')]
PAL_DRIVES = [('manual', 'Manual (Palshift)'), ('bpm_step', 'BPM step (one stop every N beats)'),
              ('bpm_cycle', 'BPM cycle (full turn every N beats)'), ('audio', 'Audio level (continuous)'),
              ('onset_step', 'Audio onsets (one stop per onset)')]

# Stop presets: (key, label, note, [(hex, pos), ...]). Our own picks by eye from the Ruben Fro looks named in
# docs/research/BR_rubenfro_pointcloud_fx.md (NOT his values, which are unpublished); 'px_ramp' = PX colour_ramp's
# default col0..col3, so a palette-mode ramp can reproduce the old default look.
STOP_PRESETS = [
    ('neon_green', 'Neon green lines', 'TFM 320-370 s, BA2 84 s green lines',
     [('000000', 0.0), ('003B1A', 0.35), ('00FF66', 0.75), ('D8FFE8', 1.0)]),
    ('cyan_magenta', 'Cyan / magenta', 'DR1 cyan beam, TFM magenta heads',
     [('00E5FF', 0.0), ('7A00FF', 0.5), ('FF00C8', 1.0)]),
    ('neon_trio', 'Neon green / cyan / magenta', 'one-stop-per-beat set',
     [('39FF14', 0.0), ('00F0FF', 0.5), ('FF00E6', 1.0)]),
    ('acid', 'Acid remap', 'TFM 420-430 s acid yellow / magenta / cyan',
     [('FFF200', 0.0), ('FF00A8', 0.5), ('00E0FF', 1.0)]),
    ('magenta_inv', 'Magenta inversion', 'AVA 8-12 s',
     [('12001A', 0.0), ('7A1FA2', 0.4), ('FF4FD8', 0.8), ('FFE6FA', 1.0)]),
    ('fire', 'Fire ramp', 'H4 fire clouds, prox_burn embers',
     [('000000', 0.0), ('5A0A00', 0.25), ('E03A00', 0.5), ('FFA000', 0.75), ('FFF4C0', 1.0)]),
    ('px_ramp', 'PX ramp default (teal / orange)', 'colour_ramp col0..col3 defaults',
     [('0D404D', 0.0), ('1A8C99', 1.0 / 3.0), ('FF8C33', 2.0 / 3.0), ('FFF2CC', 1.0)]),
    ('rainbow', 'Rainbow (use mode cycle)', 'OSC 119 s chromatic ring',
     [('FF0000', 0.0), ('FFFF00', 1.0 / 6.0), ('00FF00', 2.0 / 6.0), ('00FFFF', 3.0 / 6.0), ('0000FF', 4.0 / 6.0),
      ('FF00FF', 5.0 / 6.0)]),
]
STOP_PRESET_KEYS = [p[0] for p in STOP_PRESETS]

# Palette source menu for consumers: manual stops table, file, image, then stop presets, then FX_palette_map's.
PAL_SOURCES = ([('custom', 'Custom stops (table: hex [pos])'), ('file', 'From file'), ('image', 'Sampled from image')]
               + [(p[0], p[1]) for p in STOP_PRESETS] + [(p[0], p[1]) for p in PRESETS])


def stop_preset(key):
    for k, _l, _n, stops in STOP_PRESETS:
        if k == key:
            return [(h, float(p)) for h, p in stops]
    return None


def _num(s):
    try:
        v = float(str(s).strip())
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def parse_stop_rows(rows):
    """Table rows -> ([(hex, pos or None)], bad cells). Row = [hex] or [hex, pos]; a header row 'hex' / 'colour' and
    ';' / '//' comments are skipped. Plain strings count as one-cell rows."""
    good, bad = [], []
    for r in rows:
        cells = list(r) if isinstance(r, (list, tuple)) else [r]
        if not cells:
            continue
        s = str(cells[0]).strip()
        if not s or s.startswith(';') or s.startswith('//') or s.lower() in ('hex', 'colour', 'color'):
            continue
        h = norm_hex(s)
        if not h:
            bad.append(s)
            continue
        good.append((h, _num(cells[1]) if len(cells) > 1 and str(cells[1]).strip() else None))
    return good, bad


def _even(n, mode):
    if n <= 1:
        return [0.0] * n
    return [i / float(n) if mode == 'cycle' else i / float(n - 1) for i in range(n)]


def _fill_positions(pos, mode):
    """None positions -> even (none given) or linear between known neighbours (a missing first stop = 0, a missing
    last stop = 1). Clamped 0..1 and made ascending."""
    n = len(pos)
    if all(p is None for p in pos):
        return _even(n, mode)
    known = dict((i, _clamp01(float(p))) for i, p in enumerate(pos) if p is not None)
    known.setdefault(0, 0.0)
    known.setdefault(n - 1, 1.0)
    idx = sorted(known)
    out = []
    for i in range(n):
        if i in known:
            out.append(known[i])
            continue
        a = max(k for k in idx if k < i)
        b = min(k for k in idx if k > i)
        out.append(known[a] + (known[b] - known[a]) * (i - a) / float(b - a))
    for i in range(1, n):                       # ascending: a stop never sits before the previous one
        out[i] = max(out[i], out[i - 1])
    return out


def _downsample(items, n=PAL_MAX):
    """More than n entries -> n evenly picked (first and last kept)."""
    if len(items) <= n:
        return list(items)
    return [items[int(round(i * (len(items) - 1) / float(n - 1)))] for i in range(n)]


def palette_stops(spec, custom_rows=None, file_hex=None, pixels=None):
    """spec -> [(r, g, b, pos)] (0..16 stops, positions ascending 0..1). spec keys (all optional):
      source  'custom' | 'file' | 'image' | a STOP_PRESETS key | a PRESETS key (Lospec); default 'custom'
      stops   inline stops for 'custom' when no table rows: ['#hex', ...] or [['#hex', pos], ...] or [[r, g, b, pos]]
      mode    'gradient' | 'steps' | 'cycle' (default positions: gradient i/(n-1), cycle i/n; steps ignores them)
      reverse True flips the palette; n = colours sampled for 'image' (default 5)
    custom_rows = Table DAT rows (hex [pos]); file_hex = hex list already read with parse_file; pixels = image pixels
    (see stops_from_pixels). Over 16 colours: 16 picked evenly (first + last kept)."""
    spec = spec or {}
    src = spec.get('source', 'custom')
    mode = spec.get('mode', 'gradient')
    if src == 'custom':
        rows = custom_rows if custom_rows is not None else spec.get('stops', [])
        if rows and isinstance(rows[0], (list, tuple)) and len(rows[0]) == 4 and not isinstance(rows[0][0], str):
            items = [(tuple(float(v) for v in r[:3]), float(r[3])) for r in rows]
        else:
            items = [(hex_to_rgb(h), p) for h, p in parse_stop_rows(rows)[0]]
    elif src == 'file':
        items = [(hex_to_rgb(h), None) for h in (file_hex or [])]
    elif src == 'image':
        items = [(c, None) for c in stops_from_pixels(pixels if pixels is not None else [], int(spec.get('n', 5)))]
    elif src in STOP_PRESET_KEYS:
        items = [(hex_to_rgb(h), p) for h, p in stop_preset(src)]
    else:
        items = [(hex_to_rgb(h), None) for h in (preset(src) or [])]
    items = _downsample(items)
    cols = [c for c, _p in items]
    pos = _fill_positions([p for _c, p in items], mode)
    if src in STOP_PRESET_KEYS and mode == 'cycle' and len(cols) > 1 and pos[-1] - pos[0] >= 1.0:
        pos = [p * (len(cols) - 1) / float(len(cols)) for p in pos]   # keep spacing, give the wrap segment 1/n
    if spec.get('reverse'):
        cols, pos = cols[::-1], [1.0 - p for p in pos[::-1]]
    return [(c[0], c[1], c[2], p) for c, p in zip(cols, pos)]


def pal_rows(stops):
    """stops (palette_stops) -> exactly PAL_MAX rows [r, g, b, pos] for the uPal CHOP (padding repeats the last stop;
    the shader never reads past count). Empty -> black rows."""
    rows = [[float(v) for v in s] for s in stops[:PAL_MAX]] or [[0.0, 0.0, 0.0, 0.0]]
    return rows + [list(rows[-1]) for _ in range(PAL_MAX - len(rows))]


def pal_ctl(stops, mode='gradient', interp='rgb', shift=0.0):
    """-> uPalCtl [count, shift (wrapped 0..1), mode index, interp index]."""
    s = float(shift)
    return [float(min(len(stops), PAL_MAX)), s - math.floor(s), float(menu_index(PAL_MODES, mode)),
            float(menu_index(PAL_INTERP, interp))]


def pal_chop_channels(rows):
    """pal_rows -> {channel: 16 values} in PAL_CHANNELS order (r g b pos), for a Script CHOP."""
    return dict((ch, [float(r[k]) for r in rows]) for k, ch in enumerate(PAL_CHANNELS))


def cook_chop(scriptOp, rows):
    """Script CHOP onCook body: write pal_rows as 16 samples x channels r g b pos (TD API by duck typing)."""
    scriptOp.clear()
    scriptOp.numSamples = PAL_MAX
    for ch, vals in pal_chop_channels(rows).items():
        c = scriptOp.appendChan(ch)
        for i, v in enumerate(vals):
            c[i] = v


def _block(seq, par, field, name):
    """Index of the block whose <field> is name, else a new block at the end."""
    n = int(seq.numBlocks)
    for k in range(n):
        if str(getattr(par, '%s%d%s' % (field[0], k, field[1])).eval()) == name:
            return k
    seq.numBlocks = n + 1
    return n


def bind_glsl(o, chop, ctl, parmode=None, arr='uPal', vec='uPalCtl'):
    """Point a GLSL TOP / MAT at a palette: Arrays block `arr` = vec4 uniformarray from `chop` (path or op name),
    Vectors block `vec` = ctl (4 numbers or TD expression strings, e.g. a drive). Reuses blocks already named
    arr / vec (idempotent). parmode = TD's ParMode (pass it from TD so constants leave expression mode)."""
    k = _block(o.seq.array, o.par, ('array', 'name'), arr)
    getattr(o.par, 'array%dname' % k).val = arr
    getattr(o.par, 'array%dtype' % k).val = 'vec4'
    getattr(o.par, 'array%dchop' % k).val = chop
    getattr(o.par, 'array%darraytype' % k).val = 'uniformarray'
    v = _block(o.seq.vec, o.par, ('vec', 'name'), vec)
    getattr(o.par, 'vec%dname' % v).val = vec
    for comp, x in zip('xyzw', ctl):
        p = getattr(o.par, 'vec%dvalue%s' % (v, comp))
        if isinstance(x, str):
            p.expr = x
        else:
            if parmode is not None:
                p.mode = parmode.CONSTANT
            p.val = float(x)
    return k, v


# ---- drives: what moves uPalCtl.y (shift) -------------------------------------------------------------------------
def pal_shift(drive, count, base=0.0, beats=0.0, level=0.0, onsets=0.0):
    """Shift (wrapped 0..1) for a drive dict {'kind': PAL_DRIVES key, 'every': beats per step / cycle (default 1 /
    4), 'gain': audio gain (1), 'step': stops per step (1)} + base (the Palshift par).
    beats = continuous beat count (au_features beat_count, or seconds * bpm / 60); level 0..1; onsets = onset count.
    Steps move whole stops: shift = k / count, so pxPalStep / steps mode jump exactly one colour."""
    d = drive or {}
    kind = d.get('kind', 'manual')
    n = max(int(count), 1)
    step = float(d.get('step', 1.0))
    if kind == 'bpm_step':
        s = math.floor(float(beats) / max(float(d.get('every', 1.0)), 1e-6)) * step / n
    elif kind == 'bpm_cycle':
        s = float(beats) / max(float(d.get('every', 4.0)), 1e-6)
    elif kind == 'audio':
        s = float(d.get('gain', 1.0)) * float(level)
    elif kind == 'onset_step':
        s = math.floor(float(onsets)) * step / n
    else:
        s = 0.0
    s += float(base)
    return s - math.floor(s)


def beats_from(seconds, bpm):
    return float(seconds) * float(bpm) / 60.0


# ---- colour source (one vec4 per coloured element) ----------------------------------------------------------------
def colsrc_vec(mode='solid', pos=0.0, spread=1.0, keep=0.0):
    """-> cs vec4 [mode index, pos, spread, keep] for pxColSrc."""
    return [float(menu_index(COLSRC_MODES, mode)), float(pos), float(spread), float(keep)]


def colsrc_pars(prefix, default_mode='solid', default_rgb=(1.0, 1.0, 1.0)):
    """Standard par set for one coloured element, in the (name, style, default, opts) form the builders use:
    <Prefix>col (RGB, the solid colour), <Prefix>colsrc (menu), <Prefix>palpos, <Prefix>palspread, <Prefix>keep.
    The vec4 uniform = (menu index, palpos, palspread, keep)."""
    p = prefix[:1].upper() + prefix[1:].lower()
    return [
        (p + 'col', 'RGB', tuple(default_rgb), {}),
        (p + 'colsrc', 'Menu', default_mode, {'names': [m[0] for m in COLSRC_MODES],
                                              'labels': [m[1] for m in COLSRC_MODES]}),
        (p + 'palpos', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Palette position'}),
        (p + 'palspread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Palette spread (x attribute)'}),
        (p + 'keep', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Keep source colour'}),
    ]


# ---- reference model of px_palette.glsl (float64; the GPU is float32) ---------------------------------------------
def _lin(c):
    c = max(c, 0.0)
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _enc(c):
    c = max(c, 0.0)
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def pal_to_lab(c):
    """sRGB -> OKLab without the 0..1 clamp (HDR stops), negatives -> 0 (= pxPalToLab)."""
    r, g, b = (_lin(v) for v in c)
    l = _cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = _cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = _cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def pal_from_lab(q):
    """= pxPalFromLab."""
    L_, a, b = q
    l = (L_ + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L_ - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L_ - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (_enc(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
            _enc(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
            _enc(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s))


def _mix(a, b, f, ctl):
    if ctl[3] > 0.5:
        qa, qb = pal_to_lab(a), pal_to_lab(b)
        return pal_from_lab(tuple(x + (y - x) * f for x, y in zip(qa, qb)))
    return tuple(x + (y - x) * f for x, y in zip(a, b))


def _count(ctl):
    return min(max(int(math.floor(ctl[0] + 0.5)), 0), PAL_MAX)


def _clamp01(x):
    return min(max(x, 0.0), 1.0)


def _fract(x):
    return x - math.floor(x)


def pal_step(rows, ctl, i):
    """= pxPalStep(i)."""
    n = _count(ctl)
    if n == 0:
        return (0.0, 0.0, 0.0)
    k = int(math.floor(ctl[1] * n + 0.5))
    return tuple(rows[(int(i) + k) % n][:3])


def pal_eval(rows, ctl, t):
    """= pxPal(t): rows = pal_rows, ctl = pal_ctl."""
    n = _count(ctl)
    if n == 0:
        return (0.0, 0.0, 0.0)
    if n == 1:
        return tuple(rows[0][:3])
    mode = int(math.floor(ctl[2] + 0.5))
    if mode == 2:
        u = _fract(t + ctl[1])
    else:
        u = _clamp01(t)
        if ctl[1] != 0.0:
            u = _fract(u + ctl[1])
    if mode == 1:
        return tuple(rows[min(int(u * n), n - 1)][:3])
    p0, pl = rows[0][3], rows[n - 1][3]
    if mode == 2 and (u < p0 or u >= pl):
        x = u + 1.0 if u < p0 else u
        return _mix(rows[n - 1][:3], rows[0][:3], _clamp01((x - pl) / max(p0 + 1.0 - pl, 1e-6)), ctl)
    if u <= p0:
        return tuple(rows[0][:3])
    if u >= pl:
        return tuple(rows[n - 1][:3])
    for i in range(n - 1):
        a, b = rows[i][3], rows[i + 1][3]
        if u < b:
            return _mix(rows[i][:3], rows[i + 1][:3], _clamp01((u - a) / max(b - a, 1e-6)), ctl)
    return tuple(rows[n - 1][:3])


def colsrc_eval(cs, solid, src, attr_t, rows, ctl):
    """= pxColSrc(cs, solid, src, attrT)."""
    m = int(math.floor(cs[0] + 0.5))
    if m == 0:
        c = tuple(solid)
    elif m == 1:
        c = pal_eval(rows, ctl, cs[1])
    elif m == 2:
        c = pal_eval(rows, ctl, cs[1] + cs[2] * attr_t)
    elif m == 4:
        c = pal_step(rows, ctl, int(math.floor(cs[1] + cs[2] * attr_t + 0.5)))
    else:
        c = tuple(src)
    k = _clamp01(cs[3])
    return tuple(x + (y - x) * k for x, y in zip(c, src))


# ---- image-sampled palettes ----------------------------------------------------------------------------------------
def stops_from_pixels(pixels, n=5, iters=12, max_samples=4096):
    """Pixels -> n representative colours (k-means in OKLab, deterministic: farthest-point init from the darkest
    sample), sorted dark -> light. pixels = rows of r g b [a] floats 0..1 (a list, or a numpy array of any shape
    with 3 / 4 channels last, e.g. TOP.numpyArray()); alpha < 0.5 is skipped; at most max_samples are used
    (even stride). Fewer distinct colours than n -> fewer stops."""
    if hasattr(pixels, 'reshape'):
        pixels = pixels.reshape(-1, pixels.shape[-1]).tolist()
    px = [p for p in pixels if len(p) < 4 or p[3] >= 0.5]
    if not px or n < 1:
        return []
    stride = max(1, len(px) // max_samples)
    labs = [pal_to_lab(tuple(float(v) for v in p[:3])) for p in px[::stride]]
    d2 = lambda a, b: (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
    cents = [min(labs, key=lambda q: q[0])]
    while len(cents) < n:
        far = max(labs, key=lambda q: min(d2(q, c) for c in cents))
        if min(d2(far, c) for c in cents) < 1e-10:
            break
        cents.append(far)
    for _ in range(iters):
        acc = [[0.0, 0.0, 0.0, 0] for _c in cents]
        for q in labs:
            j = min(range(len(cents)), key=lambda k: d2(q, cents[k]))
            a = acc[j]
            a[0] += q[0]
            a[1] += q[1]
            a[2] += q[2]
            a[3] += 1
        new = [(a[0] / a[3], a[1] / a[3], a[2] / a[3]) if a[3] else c for a, c in zip(acc, cents)]
        if all(d2(a, b) < 1e-14 for a, b in zip(new, cents)):
            cents = new
            break
        cents = new
    cents.sort(key=lambda q: q[0])
    return [pal_from_lab(c) for c in cents]
