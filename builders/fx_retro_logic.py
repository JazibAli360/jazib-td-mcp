# fx_retro_logic - pure logic of FX_retro (palettes, dither, glyph, teletext, smalldisplay); no TD, no numpy.
# Offline: imported by test/test_fx_retro.py and builders/fx_retro_checks.py. In TD: the rack's Text DAT
# `fx_retro_logic` (same text), next to Text DATs `palette_map_logic` and `fx_retro_font8x8` (same files), so the
# imports below resolve to those DATs. The GLSL in builders/fx_retro*.py mirrors the reference functions here line for
# line; the LIVE CHECKS in docs/builds/fx_retro.md predict pixel numbers from them. ASCII only.
#
# Reuse, not copy: hex parsing, OKLab, Bayer 8x8, nearest-two + dither pick and the Lospec presets come from
# builders/palette_map_logic.py (FX_palette_map). This file only adds the fixed hardware palettes, the bank layout,
# cell / HAM / diffusion references and the text / display logic.
import math

try:
    import palette_map_logic as PM
except ImportError:                                   # inside TD, if the DAT import hook is not active for this DAT
    PM = op('palette_map_logic').module               # noqa: F821 (TD global)
try:
    import fx_retro_font8x8 as FONTDATA
except ImportError:
    FONTDATA = op('fx_retro_font8x8').module          # noqa: F821

U32 = 0xffffffff


# ==================================================================================================== palettes
def _ega64():
    lv = ['00', '55', 'AA', 'FF']
    out = []
    for i in range(64):           # EGA 6-bit rgbRGB: bit0 B, bit1 G, bit2 R (2/3 level), bit3 b, bit4 g, bit5 r (1/3)
        r = ((i >> 2) & 1) * 2 + ((i >> 5) & 1)
        g = ((i >> 1) & 1) * 2 + ((i >> 4) & 1)
        b = (i & 1) * 2 + ((i >> 3) & 1)
        out.append(lv[r] + lv[g] + lv[b])
    return out


CGA16 = ['000000', '0000AA', '00AA00', '00AAAA', 'AA0000', 'AA00AA', 'AA5500', 'AAAAAA',
         '555555', '5555FF', '55FF55', '55FFFF', 'FF5555', 'FF55FF', 'FFFF55', 'FFFFFF']
NES = ['7C7C7C', '0000FC', '0000BC', '4428BC', '940084', 'A80020', 'A81000', '881400',
       '503000', '007800', '006800', '005800', '004058', '000000', '000000', '000000',
       'BCBCBC', '0078F8', '0058F8', '6844FC', 'D800CC', 'E40058', 'F83800', 'E45C10',
       'AC7C00', '00B800', '00A800', '00A844', '008888', '000000', '000000', '000000',
       'F8F8F8', '3CBCFC', '6888FC', '9878F8', 'F878F8', 'F85898', 'F87858', 'FCA044',
       'F8B800', 'B8F818', '58D854', '58F898', '00E8D8', '787878', '000000', '000000',
       'FCFCFC', 'A4E4FC', 'B8B8F8', 'D8B8F8', 'F8B8F8', 'F8A4C0', 'F0D0B0', 'FCE0A8',
       'F8D878', 'D8F878', 'B8F8B8', 'B8F8D8', '00FCFC', 'F8D8F8', '000000', '000000']
SPECTRUM = ['000000', '0000D7', 'D70000', 'D700D7', '00D700', '00D7D7', 'D7D700', 'D7D7D7',      # bright 0
            '000000', '0000FF', 'FF0000', 'FF00FF', '00FF00', '00FFFF', 'FFFF00', 'FFFFFF']      # bright 1
TELETEXT = ['000000', 'FF0000', '00FF00', 'FFFF00', '0000FF', 'FF00FF', '00FFFF', 'FFFFFF']
TT_NAMES = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
HAM_BASE = [('%01X' % k) * 6 for k in range(16)]                  # 16-step 12-bit grey ramp 000, 111 .. FFF

# (key, label, kind, data, constraint default, halves, pixel aspect default, source / note)
# kind 'list' = nearest entry of `data` (hex list); 'bits' = per-channel quantise to `data` = (bits r, g, b).
# Values marked [M] are common emulator tables from memory, not re-checked against hardware (FX2 AV-34).
MACHINES = [
    ('dmg', 'Game Boy (DMG green)', 'list', ['0F380F', '306230', '8BAC0F', '9BBC0F'], 'none', 0, 1.0,
     'FX2 AV-34 common DMG set [M]'),
    ('gbbgb', 'Game Boy (bgb)', 'list', PM.preset('gameboy'), 'none', 0, 1.0, 'palette_map_logic preset (Lospec)'),
    ('gbpocket', 'Game Boy Pocket (grey)', 'list', ['000000', '545454', 'A9A9A9', 'FFFFFF'], 'none', 0, 1.0, '[M]'),
    ('nes', 'NES (2C02)', 'list', NES, 'none', 0, 8.0 / 7.0, 'common 2C02 table [M]; duplicates dropped'),
    ('c64', 'C64 (Pepto)', 'list', ['000000', 'FFFFFF', '68372B', '70A4B2', '6F3D86', '588D43', '352879', 'B8C76F',
                                    '6F4F25', '433900', '9A6759', '444444', '6C6C6C', '9AD284', '6C5EB5', '959595'],
     'none', 0, 0.936, 'Pepto PAL palette [M]'),
    ('cga0lo', 'CGA mode 4 pal 0 low', 'list', ['000000', '00AA00', 'AA0000', 'AA5500'], 'none', 0, 1.0, ''),
    ('cga0hi', 'CGA mode 4 pal 0 high', 'list', PM.preset('cga0hi'), 'none', 0, 1.0, 'palette_map_logic preset'),
    ('cga1lo', 'CGA mode 4 pal 1 low', 'list', ['000000', '00AAAA', 'AA00AA', 'AAAAAA'], 'none', 0, 1.0, ''),
    ('cga1hi', 'CGA mode 4 pal 1 high', 'list', ['000000', '55FFFF', 'FF55FF', 'FFFFFF'], 'none', 0, 1.0, ''),
    ('cga16', 'CGA / EGA 16 (RGBI)', 'list', CGA16, 'none', 0, 1.0, 'RGBI with brown fix'),
    ('ega64', 'EGA 64 (rgbRGB)', 'list', _ega64(), 'none', 0, 1.0, 'all 64 EGA colours'),
    ('spectrum', 'ZX Spectrum (clash)', 'list', SPECTRUM, 'cell', 1, 1.0, '8 colours x bright [M]; clash 8x8'),
    ('amiga12', 'Amiga OCS 12-bit (4096)', 'bits', (4, 4, 4), 'none', 0, 1.0, '4 bits per channel'),
    ('amigaham', 'Amiga HAM6', 'list', HAM_BASE, 'ham', 0, 1.0, 'HAM6: 16 base greys + hold-and-modify'),
    ('pico8', 'PICO-8', 'list', PM.preset('pico8'), 'none', 0, 1.0, 'palette_map_logic preset (Lospec)'),
    ('teletext', 'Teletext (8)', 'list', TELETEXT, 'none', 0, 1.0, 'EN 300 706 level 1'),
    ('mac1', '1-bit (black / white)', 'list', PM.preset('bw'), 'none', 0, 1.0, 'palette_map_logic preset'),
]
CONSTRAINTS = ['auto', 'none', 'cell', 'ham']
MACHINE_KEYS = [m[0] for m in MACHINES]
# every FX_palette_map preset is offered as well (no copy: read from palette_map_logic at import)
PM_KEYS = ['pm_' + p[0] for p in PM.PRESETS if p[0] not in ('pico8', 'gameboy', 'cga0hi', 'bw')]
MACHINE_MENU = ([(m[0], m[1]) for m in MACHINES] +
                [('pm_' + p[0], p[1] + ' (Lospec)') for p in PM.PRESETS if 'pm_' + p[0] in PM_KEYS] +
                [('custom', 'Custom (rack pal_custom)')])


def machine(key):
    for m in MACHINES:
        if m[0] == key:
            return m
    return None


def machine_hex(key):
    """Hex list of a list machine (duplicates dropped, first kept), PM preset, or [] for bits / custom."""
    m = machine(key)
    if m is not None:
        if m[2] != 'list':
            return []
        src = m[3]
    elif key.startswith('pm_'):
        src = PM.preset(key[3:]) or []
    else:
        return []
    keep_dups = m is not None and m[5]                   # halves rule (Spectrum): 8 + 8 entries, black twice
    out = []
    for h in src:
        h = PM.norm_hex(h)
        if h and (keep_dups or h not in out):
            out.append(h)
    return out


BANK_ORDER = [k for k, _l in MACHINE_MENU if k != 'custom']


def bank_layout():
    """{key: (offset, count)} of every fixed palette in the bank texture (custom comes after them)."""
    lay, off = {}, 0
    for k in BANK_ORDER:
        n = len(machine_hex(k))
        lay[k] = (off, n)
        off += n
    return lay, off


_LAYOUT = bank_layout()


def bank_rows(custom_hex):
    """Rows for the rack's pal_bank Script DAT: header + (hex r g b L A B) per entry, fixed palettes first, then the
    custom table (or one black 'none' row when it is empty, so the custom slot still has an entry)."""
    rows = [['hex', 'r', 'g', 'b', 'L', 'A', 'B']]
    for k in BANK_ORDER:
        h = machine_hex(k)
        if h:
            rows += PM.palette_table(h)[1:]
    rows += PM.palette_table(list(custom_hex or []))[1:]
    return rows


def bank_slot(key, bank_numrows=None):
    """(offset, count, kind, constraint_default) for a Machine key. kind 0 = list, 1 = bits. Custom: the rows after
    the fixed ones (count >= 1: the 'none' fallback row)."""
    lay, fixed = _LAYOUT
    if key == 'custom':
        n = max(1, int(bank_numrows or 0) - 1 - fixed)
        return fixed, n, 0, 'none'
    m = machine(key)
    if m is not None and m[2] == 'bits':
        return 0, 0, 1, m[4]
    off, n = lay.get(key, (0, 1))
    return off, max(n, 1), 0, (m[4] if m is not None else 'none')


def machine_bits(key):
    m = machine(key)
    return tuple(m[3]) if (m is not None and m[2] == 'bits') else (8, 8, 8)


def constraint_index(constraint, key):
    """Constraint menu value -> shader code 0 none / 1 cell / 2 ham ('auto' = the machine's default)."""
    c = constraint
    if c == 'auto':
        m = machine(key)
        c = m[4] if m is not None else 'none'
    return {'none': 0, 'cell': 1, 'ham': 2}.get(c, 0)


def halves(key):
    m = machine(key)
    return int(m[5]) if m is not None else 0


# ==================================================================================================== grid
def vgrid(w, h, pixelsize, aspect=1.0):
    """Virtual pixel grid: (psx, psy, VW, VH); whole px per virtual pixel, anchored at the bottom-left (TD y up)."""
    psy = max(1, int(round(pixelsize)))
    psx = max(1, int(round(pixelsize * aspect)))
    return psx, psy, (w + psx - 1) // psx, (h + psy - 1) // psy


def groups(n, size):
    return max(1, (int(n) + size - 1) // size)


# ==================================================================================================== dither
def hsh(x, y, s):
    """GLSL hsh(ivec2(x, y), s) of the rack lib: lowbias32 cell hash in [0, 1) (fx_destroy's, T-108)."""
    def lb32(v):
        v &= U32
        v ^= v >> 16
        v = (v * 0x7feb352d) & U32
        v ^= v >> 15
        v = (v * 0x846ca68b) & U32
        v ^= v >> 16
        return v
    a = (x * 1597334677) & U32
    b = lb32((y & U32) ^ ((s * 2654435761) & U32))
    return (lb32(a ^ b) >> 8) * (1.0 / 16777216.0)


def bayer(x, y, n):
    """Ordered Bayer threshold in (0, 1) for a 2^n x 2^n matrix (n 1..4); GLSL bayerT (the FX_glitch bits formula)."""
    v = 0
    for i in range(n):
        bx, by, s = (x >> i) & 1, (y >> i) & 1, 2 * (n - 1 - i)
        v |= ((bx ^ by) << (s + 1)) | (by << s)
    return (v + 0.5) / float(1 << (2 * n))


def ign(x, y):
    """Interleaved gradient noise (Jimenez 2014), as palette_map's shader."""
    f = 0.06711056 * x + 0.00583715 * y
    v = 52.9829189 * (f - math.floor(f))
    return v - math.floor(v)


DITHER_METHODS = ['none', 'bayer2', 'bayer4', 'bayer8', 'bayer16', 'ign', 'white', 'blue']
DITHER_LABELS = ['None (round)', 'Bayer 2x2', 'Bayer 4x4', 'Bayer 8x8', 'Bayer 16x16', 'IGN noise', 'White noise',
                 'Blue noise 64x64']
DIFFUSION = ['fs', 'atkinson', 'sierralite', 'jarvis', 'stucki', 'burkes']
DIFFUSION_LABELS = ['Floyd-Steinberg', 'Atkinson', 'Sierra Lite', 'Jarvis-Judice-Ninke', 'Stucki', 'Burkes']
DITHER_ALL = DITHER_METHODS + ['gbcam'] + DIFFUSION
DITHER_ALL_LABELS = DITHER_LABELS + ['Game Boy Camera (4 grey)'] + DIFFUSION_LABELS
# (dx, dy, weight) with dy down; weights already divided
KERNELS = {
    'fs': [(1, 0, 7), (-1, 1, 3), (0, 1, 5), (1, 1, 1)],
    'atkinson': [(1, 0, 1), (2, 0, 1), (-1, 1, 1), (0, 1, 1), (1, 1, 1), (0, 2, 1)],
    'sierralite': [(1, 0, 2), (-1, 1, 1), (0, 1, 1)],
    'jarvis': [(1, 0, 7), (2, 0, 5), (-2, 1, 3), (-1, 1, 5), (0, 1, 7), (1, 1, 5), (2, 1, 3),
               (-2, 2, 1), (-1, 2, 3), (0, 2, 5), (1, 2, 3), (2, 2, 1)],
    'stucki': [(1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4), (2, 1, 2),
               (-2, 2, 1), (-1, 2, 2), (0, 2, 4), (1, 2, 2), (2, 2, 1)],
    'burkes': [(1, 0, 8), (2, 0, 4), (-2, 1, 2), (-1, 1, 4), (0, 1, 8), (1, 1, 4), (2, 1, 2)],
}
KERNEL_DIV = {'fs': 16, 'atkinson': 8, 'sierralite': 4, 'jarvis': 48, 'stucki': 42, 'burkes': 32}


def kernels_glsl():
    """const vec3 KTAB[n] (dx, dy, w) + const ivec2 KRANGE[6] (start, count), kernel order = DIFFUSION."""
    tab, rng = [], []
    for k in DIFFUSION:
        rng.append((len(tab), len(KERNELS[k])))
        for dx, dy, w in KERNELS[k]:
            tab.append('vec3(%d.0, %d.0, %.9f)' % (dx, dy, w / float(KERNEL_DIV[k])))
    return ('const vec3 KTAB[%d] = vec3[%d](%s);\nconst ivec2 KRANGE[%d] = ivec2[%d](%s);\n' %
            (len(tab), len(tab), ', '.join(tab), len(rng), len(rng), ', '.join('ivec2(%d, %d)' % r for r in rng)))


def void_and_cluster(n=64, sigma=1.5, seed=1):
    """Blue-noise rank matrix (Ulichney void-and-cluster, toroidal Gaussian sigma 1.5). Returns n*n ranks 0..n*n-1,
    row-major [y * n + x]. Deterministic (LCG seed). ~0.8 s for 64 in CPython; the rack builds it once at build."""
    N = n * n
    r = min(n // 2 - 1, int(math.ceil(3 * sigma)) + 1)
    K = [(dx, dy, math.exp(-(dx * dx + dy * dy) / (2.0 * sigma * sigma)))
         for dy in range(-r, r + 1) for dx in range(-r, r + 1)]
    E = [0.0] * N
    on = [False] * N

    def splat(i, s):
        x, y = i % n, i // n
        for dx, dy, w in K:
            E[((y + dy) % n) * n + (x + dx) % n] += s * w

    st = [seed & U32]

    def rnd():
        st[0] = (st[0] * 1664525 + 1013904223) & U32
        return st[0]

    def tightest():
        best, bi = -1e30, -1
        for i in range(N):
            if on[i] and E[i] > best:
                best, bi = E[i], i
        return bi

    def voidest():
        best, bi = 1e30, -1
        for i in range(N):
            if not on[i] and E[i] < best:
                best, bi = E[i], i
        return bi

    m = max(1, N // 10)
    cnt = 0
    while cnt < m:
        i = rnd() % N
        if not on[i]:
            on[i] = True
            splat(i, 1.0)
            cnt += 1
    while True:
        c = tightest()
        on[c] = False
        splat(c, -1.0)
        v = voidest()
        if v == c:
            on[c] = True
            splat(c, 1.0)
            break
        on[v] = True
        splat(v, 1.0)
    proto, Ep = list(on), list(E)
    rank = [0] * N
    k = m
    while k > 0:
        c = tightest()
        on[c] = False
        splat(c, -1.0)
        k -= 1
        rank[c] = k
    on[:], E[:] = proto, Ep
    k = m
    while k < N:
        v = voidest()
        on[v] = True
        splat(v, 1.0)
        rank[v] = k
        k += 1
    return rank


def bn_table_rows(rank, n=64):
    """Table DAT rows for the rack's blue-noise texture: header b0..b(n-1) (one CHOP channel per column = texture row
    y), then one row per sample x: cell [x + 1][y] = (rank[y * n + x] + 0.5) / n^2. CHOP to TOP: texel (x, y)."""
    rows = [['b%d' % y for y in range(n)]]
    for x in range(n):
        rows.append(['%.8f' % ((rank[y * n + x] + 0.5) / float(n * n)) for y in range(n)])
    return rows


def blue(rank, x, y, n=64):
    return (rank[(y % n) * n + (x % n)] + 0.5) / float(n * n)


def threshold(method, x, y, seed=1, tick=0, rank=None):
    """Dither threshold in [0, 1) at virtual pixel (x, y): mirrors GLSL ditherT (0.5 = no dither)."""
    if method == 'none':
        return 0.5
    ox, oy = x + tick * 37, y + tick * 23
    if method.startswith('bayer'):
        n = {'bayer2': 1, 'bayer4': 2, 'bayer8': 3, 'bayer16': 4}[method]
        return bayer(ox & ((1 << n) - 1), oy & ((1 << n) - 1), n)
    if method == 'ign':
        return ign(ox, oy)
    if method == 'white':
        return hsh(x, y, (seed * 7919 + tick * 131) & U32)
    if method == 'blue':
        return blue(rank, ox, oy)
    raise ValueError(method)


def quant_levels(v, levels, thr):
    """floor(v (L-1) + thr) / (L-1), clamped (thr = 0.5 rounds). Same in GLSL quantL."""
    L = max(2.0, float(levels)) - 1.0
    return min(1.0, max(0.0, math.floor(v * L + thr) / L))


def strength(thr, s):
    return 0.5 + (thr - 0.5) * s


def pick(rgb, pal_rgb, thr=None, amount=1.0, space='oklab', wl=1.0):
    """Index the palette shader picks (reuses palette_map_logic.pick: t = d1/(d1+d2), 2nd wins when t*amt > thr)."""
    return PM.pick(rgb, pal_rgb, threshold=thr, amount=amount, space=space, wl=wl)


def dist2(a, b, space='oklab', wl=1.0):
    if space == 'oklab':
        a, b = PM.srgb_to_oklab(a), PM.srgb_to_oklab(b)
        d0 = (a[0] - b[0]) * wl
    else:
        d0 = a[0] - b[0]
    return d0 * d0 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def cell_pair(pix, pal, space='oklab', wl=1.0, halves_rule=0):
    """Attribute clash reference (Spectrum): pix = up to 64 rgb tuples of one 8x8 cell; returns (i, j, cost) of the
    best pair i < j (cost = sum of per-pixel min distance^2); halves_rule 1 = both from the same half of the palette
    (the bright bit). Ties: the first pair in (i, j) order wins, as the GLSL reduction (lowest pair index)."""
    n = len(pal)
    if n < 2:
        return 0, 0, sum(dist2(p, pal[0], space, wl) for p in pix)
    D = [[dist2(p, c, space, wl) for c in pal] for p in pix]
    best = (1e30, 0, 0)
    h = n // 2
    for i in range(n):
        for j in range(i + 1, n):
            if halves_rule and ((i < h) != (j < h)):
                continue
            cost = sum(min(d[i], d[j]) for d in D)
            if cost < best[0]:
                best = (cost, i, j)
    return best[1], best[2], best[0]


def pair_index(i, j, n):
    """Linear index of pair (i < j) in row order, the GLSL decode's inverse."""
    return i * n - i * (i + 1) // 2 + (j - i - 1)


def pair_decode(p, n):
    i = 0
    while p >= n - 1 - i:
        p -= n - 1 - i
        i += 1
    return i, i + 1 + p


def q4(v):
    return math.floor(v * 15.0 + 0.5) / 15.0


def ham_row(row, base, space='oklab', wl=1.0, border=None):
    """HAM6 reference for one row of virtual pixels (rgb in 0..1): each pixel is either a base entry (16) or the
    previous pixel with ONE channel replaced by the 4-bit target value. Candidate order (ties: first wins): base 0..15,
    modify R, modify G, modify B. Returns [(rgb, code)] with code 0..15 base, 16 R, 17 G, 18 B."""
    prev = border if border is not None else base[0]
    out = []
    for c in row:
        best = (1e30, None, -1)
        for i, b in enumerate(base):
            d = dist2(c, b, space, wl)
            if d < best[0]:
                best = (d, b, i)
        for k in range(3):
            m = list(prev)
            m[k] = q4(c[k])
            m = tuple(m)
            d = dist2(c, m, space, wl)
            if d < best[0]:
                best = (d, m, 16 + k)
        prev = best[1]
        out.append((best[1], best[2]))
    return out


def diffuse(img, kernel, quant, serpentine=False):
    """Error diffusion reference on one tile: img = rows TOP-FIRST of rgb tuples; quant(rgb) -> rgb. Errors leaving
    the tile are dropped (the GLSL tile-parallel approximation). Returns the quantised rows (top first)."""
    H, W = len(img), len(img[0])
    err = [[[0.0, 0.0, 0.0] for _ in range(W)] for _ in range(H)]
    out = [[None] * W for _ in range(H)]
    K = [(dx, dy, w / float(KERNEL_DIV[kernel])) for dx, dy, w in KERNELS[kernel]]
    for y in range(H):
        rev = serpentine and (y & 1) == 1
        xs = range(W - 1, -1, -1) if rev else range(W)
        for x in xs:
            c = [img[y][x][k] + err[y][x][k] for k in range(3)]
            q = quant(c)
            out[y][x] = tuple(q)
            e = [c[k] - q[k] for k in range(3)]
            for dx, dy, w in K:
                xx, yy = x + (-dx if rev else dx), y + dy
                if 0 <= xx < W and 0 <= yy < H:
                    for k in range(3):
                        err[yy][xx][k] += e[k] * w
    return out


def gbcam_level(y, contrast, edge_term, thr, levels=4):
    """Game Boy Camera style: luma -> contrast around 0.5 -> + edge term -> `levels` grey steps (Bayer 4x4 thr);
    the step is shown as the palette entry of that rank in OKLab L (darkest = 0)."""
    v = (y - 0.5) * contrast + 0.5 + edge_term
    return int(quant_levels(v, levels, thr) * (levels - 1) + 0.5)


def rank_by_l(hexes):
    """Palette indices sorted dark -> light by OKLab L (ties: lower index first), the GLSL rank loop."""
    L = [PM.srgb_to_oklab(PM.hex_to_rgb(h))[0] for h in hexes]
    return sorted(range(len(hexes)), key=lambda i: (L[i], i))


# ==================================================================================================== font
GLYPHS = [(cp, bytes.fromhex(hx)) for cp, hx in FONTDATA.GLYPHS]
GLYPH_INDEX = dict((cp, i) for i, (cp, _b) in enumerate(GLYPHS))
NGLYPH = len(GLYPHS)


def glyph_index(ch):
    """Glyph index of a character / codepoint, -1 = blank (space, unknown)."""
    cp = ord(ch) if isinstance(ch, str) else int(ch)
    return GLYPH_INDEX.get(cp, -1)


def font_bit(g, x, y):
    """Pixel (x, y) of glyph g, x left -> right, y top -> bottom (0..7)."""
    if g < 0 or g >= NGLYPH or not (0 <= x < 8 and 0 <= y < 8):
        return False
    return bool((GLYPHS[g][1][y] >> x) & 1)


def font_bit_smooth(g, x2, y2):
    """Half-pixel grid (0..15): SAA5050-style rounding (fill the inner corner where two orthogonal neighbours towards
    this quadrant are lit and the diagonal is not). Mirrors GLSL fontBitS."""
    x, y = x2 >> 1, y2 >> 1
    if font_bit(g, x, y):
        return True
    dx = 1 if (x2 & 1) else -1
    dy = 1 if (y2 & 1) else -1
    return font_bit(g, x + dx, y) and font_bit(g, x, y + dy) and not font_bit(g, x + dx, y + dy)


def glyph_words(g):
    """(lo, hi) uint32 words of glyph g: lo = rows 0-3, hi = rows 4-7, byte k = row k (bit x = column x)."""
    b = GLYPHS[g][1]
    lo = b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)
    hi = b[4] | (b[5] << 8) | (b[6] << 16) | (b[7] << 24)
    return lo, hi


def coverage(g):
    if g < 0:
        return 0
    return sum(bin(v).count('1') for v in GLYPHS[g][1])


def font_table_rows():
    """Table DAT rows for the rack's font texture (font_top, r32float, width 2 * NGLYPH, 2 rows): header lo hi, then
    one row per uint32 word (glyph g = words 2g, 2g + 1): lo / hi 16 bits, exact in float32."""
    rows = [['lo', 'hi']]
    for g in range(NGLYPH):
        for w in glyph_words(g):
            rows.append([str(w & 0xFFFF), str(w >> 16)])
    return rows


def font_glsl():
    """fontWord / fontBit / fontBitS read the font texture on input FONT_IN (T-35: every index guarded). Live 31550:
    a dynamically indexed `const uint FONT[428]` costs ~3 ms per pass (glyph ascii 3.5 ms -> 0.5 ms without it):
    big const arrays are copied per thread, so tables live in textures."""
    return 'const int NGLYPH = %d;\n' % NGLYPH + FONT_FUNCS


FONT_FUNCS = """uint fontWord(int i) {                       // word i of the font texture (lo 16 bits row 0, hi row 1)
    i = clamp(i, 0, 2 * NGLYPH - 1);
    return uint(texelFetch(sTD2DInputs[FONT_IN], ivec2(i, 0), 0).r + 0.5)
         | (uint(texelFetch(sTD2DInputs[FONT_IN], ivec2(i, 1), 0).r + 0.5) << 16);
}
bool fontBit(int g, int x, int y) {          // x left->right, y top->bottom, 0..7; g < 0 = blank
    if (g < 0 || g >= NGLYPH || x < 0 || x > 7 || y < 0 || y > 7) return false;
    uint w = fontWord(2 * g + (y >> 2));
    return ((w >> uint(8 * (y & 3) + x)) & 1u) != 0u;
}
bool fontBitS(int g, int x2, int y2) {        // half-pixel grid 0..15, SAA5050-style corner rounding
    int x = x2 >> 1, y = y2 >> 1;
    if (fontBit(g, x, y)) return true;
    int dx = (x2 & 1) == 1 ? 1 : -1, dy = (y2 & 1) == 1 ? 1 : -1;
    return fontBit(g, x + dx, y) && fontBit(g, x, y + dy) && !fontBit(g, x + dx, y + dy);
}
bool glyphAt(int g, vec2 uv, bool sm) {  // uv in the glyph box, v from the top
    if (sm) return fontBitS(g, int(floor(uv.x * 16.0)), int(floor(uv.y * 16.0)));
    return fontBit(g, int(floor(uv.x * 8.0)), int(floor(uv.y * 8.0)));
}
"""

GLYPH_RANGES = {}                                     # contiguous index ranges in GLYPHS (file order)


def _ranges():
    def rng(lo, hi):
        idx = [i for i, (cp, _b) in enumerate(GLYPHS) if lo <= cp <= hi]
        return (min(idx), max(idx) + 1) if idx else (0, 0)
    GLYPH_RANGES['basic'] = rng(0x21, 0x7E)
    GLYPH_RANGES['blocks'] = rng(0x2580, 0x259F)
    GLYPH_RANGES['hiragana'] = rng(0x3040, 0x309F)
    GLYPH_RANGES['basic+blocks'] = (GLYPH_RANGES['basic'][0], GLYPH_RANGES['blocks'][1])
    GLYPH_RANGES['all'] = (0, NGLYPH)


_ranges()
SHAPESETS = ['basic', 'blocks', 'basic+blocks', 'all']

# brightness ramps (dark -> bright); custom = the Chars string sorted by ink coverage
CHARSETS = ['ascii', 'dense', 'blocks', 'digits', 'binary', 'hex', 'hiragana', 'custom']
CHARSET_LABELS = ['ASCII ramp', 'ASCII dense', 'Blocks', 'Digits', 'Binary', 'Hex', 'Hiragana', 'Custom (Chars)']
RAMP_TEXT = {
    'ascii': ' .:-=+*#%@',
    'dense': " .'`^,:;Il!i><~+_-?][}{1)(|tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    'blocks': ' ' + ''.join(chr(c) for c in (0x2591, 0x2592, 0x2593, 0x2588)),
    'digits': '0123456789',
    'binary': '01',
    'hex': '0123456789ABCDEF',
}
RAMP_MAX = 33                                         # 11 floats x 3 glyphs (uniforms uR0..uR2)
_RAMP_CACHE = {}


def ramp(charset, chars=''):
    """Glyph indices (dark -> bright; -1 = blank). Fixed ramps keep their order; 'custom' sorts the Chars by ink
    coverage (stable). Digits/binary/hex/hiragana are sets (matrix rain / random picks), kept in order.
    Longer than RAMP_MAX: resampled evenly (first and last kept)."""
    key = (charset, chars)
    if key in _RAMP_CACHE:
        return _RAMP_CACHE[key]
    if charset == 'hiragana':
        a, b = GLYPH_RANGES['hiragana']
        g = list(range(a, b))
    elif charset == 'custom':
        cs = [c for c in (chars or ' ') if c != '\n']
        g = sorted([glyph_index(c) for c in cs], key=coverage)
    else:
        g = [glyph_index(c) for c in RAMP_TEXT[charset]]
    if len(g) > RAMP_MAX:
        n = len(g)
        g = [g[int(round(k * (n - 1) / float(RAMP_MAX - 1)))] for k in range(RAMP_MAX)]
    g = g or [-1]
    _RAMP_CACHE[key] = g
    return g


def ramp_packed(charset, chars=''):
    """12 floats for uR0..uR2: 3 glyphs per float as (g + 1) bytes (exact in float32), then the count in uR2.w."""
    g = ramp(charset, chars)
    vals = []
    for k in range(11):
        v = 0
        for j in range(3):
            i = k * 3 + j
            v += (g[i] + 1 if i < len(g) else 0) << (8 * j)
        vals.append(float(v))
    return vals + [float(len(g))]


def ramp_unpack(vals):
    n = int(vals[11])
    out = []
    for i in range(n):
        v = int(vals[i // 3])
        out.append(((v >> (8 * (i % 3))) & 255) - 1)
    return out


def ramp_pick(lum, n):
    """Ramp slot for a cell luma (0..1): floor(lum * n) clamped (GLSL rampSlot)."""
    return max(0, min(n - 1, int(math.floor(lum * n))))


def shape_match(pattern_lo, pattern_hi, lo_glyph, hi_glyph, allow_space=True):
    """Text-mode best glyph for a 64-bit cell pattern (bit y*8+x = pixel brighter than the cell mean). Score =
    popcount(pattern ^ glyph), inverted glyphs allowed (swaps fg / bg). Returns (glyph, inverted, score); space
    (all off) is glyph -1. Ties: lower glyph index, non-inverted first (GLSL order)."""
    best = (65, -2, False)
    pc = bin(pattern_lo).count('1') + bin(pattern_hi).count('1')
    if allow_space:
        best = min(best, (pc, -1, False), (64 - pc, -1, True), key=lambda t: t[0])
    for g in range(lo_glyph, hi_glyph):
        lo, hi = glyph_words(g)
        s = bin(pattern_lo ^ lo).count('1') + bin(pattern_hi ^ hi).count('1')
        if s < best[0]:
            best = (s, g, False)
        if 64 - s < best[0]:
            best = (64 - s, g, True)
    return best[1], best[2], best[0]


# ==================================================================================================== teletext
# packed cell (float32-exact int < 2^24): bits 0-6 char, 7-9 fg, 10-12 bg, 13 mosaic, 14 separated, 15 flash,
# 16 conceal, 17 double-height top, 18 double-height bottom, 19 image cell (show the picture mosaic here)
B_MOS, B_SEP, B_FLASH, B_CONCEAL, B_DHT, B_DHB, B_IMG = 13, 14, 15, 16, 17, 18, 19


def tt_pack(ch, fg=7, bg=0, mosaic=0, sep=0, flash=0, conceal=0, dht=0, dhb=0, img=0):
    return ((ch & 127) | ((fg & 7) << 7) | ((bg & 7) << 10) | (mosaic << B_MOS) | (sep << B_SEP) |
            (flash << B_FLASH) | (conceal << B_CONCEAL) | (dht << B_DHT) | (dhb << B_DHB) | (img << B_IMG))


def tt_unpack(v):
    v = int(v)
    return {'ch': v & 127, 'fg': (v >> 7) & 7, 'bg': (v >> 10) & 7, 'mosaic': (v >> B_MOS) & 1,
            'sep': (v >> B_SEP) & 1, 'flash': (v >> B_FLASH) & 1, 'conceal': (v >> B_CONCEAL) & 1,
            'dht': (v >> B_DHT) & 1, 'dhb': (v >> B_DHB) & 1, 'img': (v >> B_IMG) & 1}


def mosaic_mask(ch):
    """Teletext graphics character -> 6-bit sixel mask (bit 0 top-left, 1 top-right, 2 mid-left, 3 mid-right,
    4 bottom-left, 5 bottom-right): bits 0-4 = char bits 0-4, bit 5 = char bit 6. Chars 0x40-0x5F are letters
    ('blast-through'), -1."""
    if 0x40 <= ch <= 0x5F or ch < 0x20:
        return -1
    return (ch & 0x1F) | ((ch & 0x40) >> 1)


def _tokens(line):
    """Split '{red}News {{x}}' into [('attr', 'red'), ('text', 'News '), ('text', '{x}')]."""
    out, i = [], 0
    while i < len(line):
        if line.startswith('{{', i):
            out.append(('text', '{'))
            i += 2
        elif line.startswith('}}', i):
            out.append(('text', '}'))
            i += 2
        elif line[i] == '{' and '}' in line[i:]:
            j = line.index('}', i)
            out.append(('attr', line[i + 1:j].strip().lower()))
            i = j + 1
        else:
            out.append(('text', line[i]))
            i += 1
    return out


ATTRS = (['dh', 'nh', 'flash', 'steady', 'conceal', 'sep', 'cont', 'bg', 'black', 'hold'] +
         TT_NAMES + ['g' + c for c in TT_NAMES])


def tt_row(line, cols, img_rest=False):
    """One page row: markup -> list of `cols` packed cells. Spacing attributes (as level 1 teletext): every {attr}
    takes one cell, drawn as a space in the current background. {red}.. alpha colour, {gred}.. graphics (mosaic)
    colour, {bg} new background = current fg, {black} black background, {dh}/{nh} double / normal height, {flash}
    {steady} {conceal} {sep} {cont}. Unknown {x} is printed literally. img_rest: cells after the text show the image."""
    fg, bg, mos, sep, flash, conceal, dh = 7, 0, 0, 0, 0, 0, 0
    cells = []
    for kind, v in _tokens(line):
        if len(cells) >= cols:
            break
        if kind == 'attr':
            if v in TT_NAMES:
                fg, mos = TT_NAMES.index(v), 0
            elif v.startswith('g') and v[1:] in TT_NAMES:
                fg, mos = TT_NAMES.index(v[1:]), 1
            elif v == 'bg':
                bg = fg
            elif v == 'black':
                bg = 0
            elif v == 'dh':
                dh = 1
            elif v == 'nh':
                dh = 0
            elif v == 'flash':
                flash = 1
            elif v == 'steady':
                flash = 0
            elif v == 'conceal':
                conceal = 1
            elif v == 'sep':
                sep = 1
            elif v == 'cont':
                sep = 0
            elif v == 'hold':
                pass
            else:
                for c in '{' + v + '}':
                    if len(cells) < cols:
                        cells.append(tt_pack(ord(c) & 127, fg, bg, 0, 0, flash, conceal, dh))
                continue
            cells.append(tt_pack(32, fg, bg, 0, 0, 0, 0, dh))
        else:
            c = ord(v) if ord(v) < 128 else ord('?')
            m = mos and mosaic_mask(c) >= 0
            cells.append(tt_pack(c, fg, bg, 1 if m else 0, sep if m else 0, flash, conceal, dh))
    while len(cells) < cols:
        cells.append(tt_pack(32, fg, bg, 0, 0, 0, 0, 0, 0, 1 if img_rest else 0))
    return cells


def tt_page(lines, cols, rows, image_body=True, header=None):
    """Page mode: row 0 = header (if given), then the page lines; rows after the last line AND empty lines ('')
    show the image when image_body, else black (a line of one space = a black row). Double height: a row with {dh} cells puts its bottom halves into the next screen row and
    the following lines move down one row. Returns cols*rows packed cells, top row first."""
    src = ([header] if header is not None else []) + list(lines)
    out, i = [], 0
    while len(out) < rows:
        if i < len(src) and not (image_body and src[i] == '' and (header is None or i > 0)):
            row = tt_row(src[i], cols)
            i += 1
            out.append(row)
            if any((v >> B_DHT) & 1 for v in row) and len(out) < rows:
                out.append([((v & ~(1 << B_DHT)) | (1 << B_DHB)) if (v >> B_DHT) & 1 else
                            tt_pack(32, 7, (v >> 10) & 7) for v in row])
        else:
            i += 1
            out.append([tt_pack(32, 7, 0, img=1 if image_body else 0)] * cols)
    return [v for row in out[:rows] for v in row]


def wrap(text, width):
    """Word wrap at width (long words are cut)."""
    lines = []
    for para in str(text).replace('\r', '').split('\n'):
        words, cur = para.split(' '), ''
        for w in words:
            while len(w) > width:
                if cur:
                    lines.append(cur)
                    cur = ''
                lines.append(w[:width])
                w = w[width:]
            if not cur:
                cur = w
            elif len(cur) + 1 + len(w) <= width:
                cur += ' ' + w
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return [l for l in lines if l.strip()] or ['']


def tt_subtitle(text, cols, rows, colour='white', double=True, row_from_bottom=2, image_body=True):
    """Subtitle mode (Ceefax style): lines boxed in black, centred, start on a colour attribute, double height by
    default; the rest of the screen shows the image (or black). Lines split at '|' or newlines, wrapped to cols - 4."""
    ci = TT_NAMES.index(colour) if colour in TT_NAMES else 7
    lines = []
    for part in str(text).replace('|', '\n').split('\n'):
        if part.strip():
            lines += wrap(part.strip(), max(1, cols - 4))
    grid = [[tt_pack(32, 7, 0, img=1 if image_body else 0)] * cols for _ in range(rows)]
    step = 2 if double else 1
    top = rows - row_from_bottom - step * len(lines)
    for k, l in enumerate(lines):
        r = top + k * step
        if r < 0 or r >= rows:
            continue
        w = len(l) + 2                                   # colour attribute + text + one trailing box cell
        x0 = max(0, (cols - w) // 2)
        for i in range(w):
            x = x0 + i
            if x >= cols:
                break
            c = 32 if i == 0 or i == w - 1 else ord(l[i - 1]) & 127
            grid[r][x] = tt_pack(c, ci, 0, dht=1 if double else 0)
            if double and r + 1 < rows:
                grid[r + 1][x] = tt_pack(c, ci, 0, dhb=1)
    return [v for row in grid for v in row]


def tt_image(cols, rows):
    return [tt_pack(32, 7, 0, img=1)] * (cols * rows)


WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def clock12(hour, minute, second=None, ampm=True, pad=True):
    """12-hour clock text (user rule): ' 6:30' / '12:05:09 PM'; pad = leading space for 1-digit hours."""
    h = hour % 12 or 12
    s = ('%2d' if pad else '%d') % h + ':%02d' % minute
    if second is not None:
        s += ':%02d' % second
    if ampm:
        s += ' AM' if hour < 12 else ' PM'
    return s


def header_text(template, tm, page='100'):
    """Expand a teletext header: %a weekday, %d day, %b month, %l hour (12 h, space padded), %M minute, %S second,
    %p AM/PM, %P page. tm = (year, month, day, hour, minute, second, weekday 0 = Monday)."""
    y, mo, d, hh, mi, ss, wd = tm[:7]
    rep = {'%a': WEEKDAYS[wd % 7], '%d': '%02d' % d, '%b': MONTHS[(mo - 1) % 12], '%l': '%2d' % (hh % 12 or 12),
           '%M': '%02d' % mi, '%S': '%02d' % ss, '%p': 'AM' if hh < 12 else 'PM', '%P': str(page)}
    out = template
    for k, v in rep.items():
        out = out.replace(k, v)
    return out


DEFAULT_HEADER = 'P%P TELETEXT %P %a %d %b{yellow}%l:%M/%S %p'
DEFAULT_PAGE = ['{blue}{bg}{dh}{white}  FX_retro  teletext  ',
                ' ',
                '{cyan}Edit the rack page table:',
                '{white}one row per line, {{red}} etc.',
                '{gyellow}\x7f\x7f\x7f\x7f{green} mosaic chars after {{gyellow}}']
FASTEXT = '{red}Red {green}Green {yellow}Yellow {cyan}Cyan'
PAGE_GAP = 17                                         # empty lines (picture rows 7-23) so Fastext lands on row 24


def tt_grid(w, h, cols, rows, cell_aspect=1.2):
    """(cols, rows, cw, ch): rows 0 = auto (cells cell_aspect times taller than wide)."""
    cols = max(1, int(cols))
    cw = w / float(cols)
    if int(rows) <= 0:
        rows = max(1, int(round(h / (cw * cell_aspect))))
    rows = int(rows)
    return cols, rows, cw, h / float(rows)


def sixel_choose(six, pal_rgb=None, space='oklab'):
    """Best (fg, bg, mask) for 6 sixel colours with 2 of the 8 teletext colours: each sixel takes the nearer colour
    (fg on ties), cost = sum of distance^2. Candidate order fg 0..7 x bg 0..7 (row-major index fg*8+bg); ties keep
    the first (GLSL reduction: lowest index). Mask bit k = sixel k shows fg."""
    pal = pal_rgb or [PM.hex_to_rgb(h) for h in TELETEXT]
    D = [[dist2(s, c, space) for c in pal] for s in six]
    best = (1e30, 0, 0, 0)
    for f in range(8):
        for b in range(8):
            cost, mask = 0.0, 0
            for k in range(6):
                if D[k][f] <= D[k][b]:
                    cost += D[k][f]
                    mask |= 1 << k
                else:
                    cost += D[k][b]
            if cost < best[0]:
                best = (cost, f, b, mask)
    return best[1], best[2], best[3]


# sixel row boundaries in the cell (from the top), SAA5050: 10 lines -> 3 / 4 / 3
SIXEL_ROWS = (0.0, 0.3, 0.7, 1.0)


def sixel_of(u, v):
    """Sixel index of a cell position (u left->right, v top->bottom, 0..1)."""
    col = 1 if u >= 0.5 else 0
    row = 0 if v < SIXEL_ROWS[1] else (1 if v < SIXEL_ROWS[2] else 2)
    return row * 2 + col


# ==================================================================================================== small displays
DISPLAYS = ['lcd', 'vfd', 'nixie', 'flipdot', 'splitflap', 'eink']
DISPLAY_LABELS = ['LCD dot matrix (ghosting)', 'VFD (vacuum fluorescent)', 'Nixie tubes', 'Flip-dot board',
                  'Split-flap board', 'E-ink (refresh flash)']
DOT_DISPLAYS = ('lcd', 'vfd', 'flipdot', 'eink')
CONTENTS = ['image', 'text', 'clock', 'value']
FLAP_ALPHABET = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,:-!?/&'"
NIXIE_CHARS = '0123456789:.'


def dot_grid(w, h, dotsize):
    """(ds, GW, GH) of a dot display; dot (gx, gyT) with gyT counted from the top."""
    ds = max(1, int(round(dotsize)))
    return ds, (w + ds - 1) // ds, (h + ds - 1) // ds


def cell_layout(w, h, cols, rows, aspect):
    """Character cells (nixie / split-flap): width = w / cols, height = width * aspect; if the block is taller than
    the frame it shrinks to fit. Returns (cw, ch, x0, y0top) of a centred block."""
    cols, rows = max(1, int(cols)), max(1, int(rows))
    cw = w / float(cols)
    ch = cw * aspect
    if ch * rows > h:
        ch = h / float(rows)
        cw = ch / aspect
    return cw, ch, (w - cw * cols) / 2.0, (h - ch * rows) / 2.0


def state_size(display, w, h, dotsize, cols, rows):
    if display in DOT_DISPLAYS:
        _ds, gw, gh = dot_grid(w, h, dotsize)
        return gw, gh
    return max(1, int(cols)), max(1, int(rows))


def text_lines(text):
    return str(text).replace('\r', '').replace('|', '\n').split('\n')


def layout_text(lines, cols, rows, align='left'):
    """Lines -> rows x cols chars (cut, padded with spaces); align left / centre / right."""
    out = []
    for r in range(rows):
        l = lines[r] if r < len(lines) else ''
        l = l[:cols]
        pad = cols - len(l)
        if align == 'right':
            l = ' ' * pad + l
        elif align == 'centre':
            l = ' ' * (pad // 2) + l + ' ' * (pad - pad // 2)
        else:
            l = l + ' ' * pad
        out.append(l)
    return out


def content_text(content, text, value, fmt, tm, display):
    """The string a display shows: text / clock (12 h; nixie: digits and colons only) / value (Format)."""
    if content == 'clock':
        if display == 'nixie':                         # padded: 8 tubes ' 6:30:45' / '10:00:30' (live: 7 cut 10-12 h)
            return clock12(tm[3], tm[4], tm[5], ampm=False, pad=True)
        return clock12(tm[3], tm[4], None if display == 'splitflap' else tm[5], ampm=True, pad=False)
    if content == 'value':
        try:
            return fmt.format(value)
        except (ValueError, IndexError, KeyError):
            return '%g' % value
    return str(text)


def char_code(display, ch):
    """Per-cell code (stored + 1, 0 = blank): nixie 0-9 digits, 10 ':', 11 '.'; split-flap alphabet index (unknown ->
    space 0); dot displays glyph index."""
    if display == 'nixie':
        k = NIXIE_CHARS.find(ch)
        return k + 1 if k >= 0 else 0
    if display == 'splitflap':
        k = FLAP_ALPHABET.find(ch.upper())
        return (k if k >= 0 else 0) + 1
    return glyph_index(ch) + 1


def display_codes(display, content, text, value, fmt, tm, cols, rows, align='left'):
    """Codes for the `codes` Script CHOP (row-major, top row first). Image content -> []."""
    if content == 'image' and display in DOT_DISPLAYS:
        return []
    s = content_text(content, text, value, fmt, tm, display)
    grid = layout_text(text_lines(s), cols, rows, align)
    return [char_code(display, c) for row in grid for c in row]


def flap_glyphs():
    return [glyph_index(c) for c in FLAP_ALPHABET]


def flap_step(cur, start, target, now, step, n=len(FLAP_ALPHABET)):
    """Split-flap state update (GLSL state pass): (cur index, flap start time or -1). A flap that has run `step`
    seconds lands (cur + 1); an idle cell that is not on target starts the next flap now."""
    if start >= 0.0 and now - start >= step:
        cur, start = (cur + 1) % n, -1.0
    if start < 0.0 and cur != target:
        start = now
    return cur, start


def flaps_needed(cur, target, n=len(FLAP_ALPHABET)):
    return (target - cur) % n


def flip_delay(scan, gx, gy, gw, gh, sweep, seed=1):
    """Flip-dot start delay (s): all 0 / columns left->right / rows top->bottom / random, spread over `sweep` s."""
    if scan == 'columns':
        return sweep * gx / float(max(1, gw))
    if scan == 'rows':
        return sweep * gy / float(max(1, gh))
    if scan == 'random':
        return sweep * hsh(gx, gy, seed)
    return 0.0


def flip_scale(p):
    """Apparent disc height during a flip (rotation about the horizontal axis), p 0..1; side shown: old < 0.5."""
    return abs(math.cos(math.pi * min(1.0, max(0.0, p))))


def lcd_step(cur, target, dt, rise, fall):
    """LCD response (per channel): exponential approach, `rise` s when the value goes up, `fall` s when down."""
    tau = rise if target > cur else fall
    if tau <= 0.0:
        return target
    return cur + (target - cur) * (1.0 - math.exp(-dt / tau))


def eink_phase(t_since, flash):
    """E-ink full refresh phase at t_since s after the trigger: 'inverted' (old picture inverted), 'black', 'white',
    'fadein' (new picture), 'done'. Quarters of `flash` seconds."""
    if t_since < 0.0 or flash <= 0.0:
        return 'done'
    p = t_since / flash
    if p >= 1.0:
        return 'done'
    return ['inverted', 'black', 'white', 'fadein'][int(p * 4.0)]


def eink_partial(displayed, target, ghost):
    """Partial update: the new picture with `ghost` of the old one left over (cleared only by a full refresh)."""
    return target + (displayed - target) * ghost


# Nixie numerals as polylines in a 0..1 box (x right, y up), one stroke list per digit 0-9 (IN-14 style shapes).
def _arc(cx, cy, rx, ry, a0, a1, n):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * k / float(n))),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * k / float(n)))) for k in range(n + 1)]


def nixie_strokes():
    d = {}
    d[0] = [_arc(0.5, 0.5, 0.42, 0.5, 0, 360, 20)]
    d[1] = [[(0.5, 0.0), (0.5, 1.0), (0.3, 0.82)]]
    d[2] = [_arc(0.5, 0.72, 0.4, 0.28, 160, -20, 9) + [(0.08, 0.0), (0.92, 0.0)]]
    d[3] = [[(0.1, 1.0), (0.9, 1.0), (0.45, 0.6)] + _arc(0.5, 0.3, 0.42, 0.3, 90, -150, 10)]
    d[4] = [[(0.72, 0.0), (0.72, 1.0), (0.05, 0.32), (0.95, 0.32)]]
    d[5] = [[(0.88, 1.0), (0.18, 1.0), (0.12, 0.56)] + _arc(0.5, 0.32, 0.42, 0.32, 140, -150, 11)]
    d[6] = [_arc(0.62, 0.55, 0.52, 0.45, 60, 180, 6) + _arc(0.5, 0.3, 0.4, 0.3, 180, 540, 16)]
    d[7] = [[(0.06, 1.0), (0.94, 1.0), (0.35, 0.0)]]
    d[8] = [_arc(0.5, 0.76, 0.3, 0.24, -90, 270, 14), _arc(0.5, 0.28, 0.4, 0.28, 90, 450, 16)]
    d[9] = [[(1.0 - x, 1.0 - y) for x, y in s] for s in d[6]]
    return d


def nixie_segments():
    """Flat segment list (x0, y0, x1, y1) + (start, count) per digit."""
    segs, rng = [], []
    for k in range(10):
        st = len(segs)
        for stroke in nixie_strokes()[k]:
            for a, b in zip(stroke[:-1], stroke[1:]):
                segs.append((a[0], a[1], b[0], b[1]))
        rng.append((st, len(segs) - st))
    return segs, rng


def nixie_glsl():
    segs, rng = nixie_segments()
    return ('const vec4 NIXSEG[%d] = vec4[%d](%s);\nconst ivec2 NIXRANGE[10] = ivec2[10](%s);\n' %
            (len(segs), len(segs), ', '.join('vec4(%.5f, %.5f, %.5f, %.5f)' % s for s in segs),
             ', '.join('ivec2(%d, %d)' % r for r in rng)))


def seg_dist(px, py, s):
    ax, ay, bx, by = s
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    L = vx * vx + vy * vy
    t = 0.0 if L <= 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / L))
    dx, dy = wx - vx * t, wy - vy * t
    return math.sqrt(dx * dx + dy * dy)


def nixie_dist(digit, x, y):
    segs, rng = nixie_segments()
    st, n = rng[digit]
    return min(seg_dist(x, y, segs[i]) for i in range(st, st + n))


def flap_glsl():
    g = flap_glyphs()
    return 'const int NFLAP = %d;\nconst int FLAPG[%d] = int[%d](%s);\n' % (len(g), len(g), len(g),
                                                                            ', '.join(str(v) for v in g))


def menu_index(names, key, default=0):
    return names.index(key) if key in names else default


# ==================================================================================================== TD adapters
# Called from the modules' `codes` Script CHOP callbacks (rack builders/fx_retro.py CODES_CB) with the module COMP,
# a local-time tuple (year, month, day, hour, minute, second, weekday) and the input size. Duck-typed: only
# m.par.<Name>.eval(), m.op(name) and a DAT's rows() / [r, 0].val are used, so the offline tests pass fakes.
def _dat_lines(dat):
    if dat is None or not hasattr(dat, 'rows'):        # an empty DAT par evaluates to None (fakes: '')
        return None
    out = []
    for r in dat.rows():
        out.append(' '.join(c.val for c in r))
    return out


def teletext_codes_td(m, T, w, h):
    p = m.par
    cols, rows, _cw, _ch = tt_grid(w, h, p.Columns.eval(), p.Rows.eval(), p.Cellaspect.eval())
    mode = p.Mode.eval()
    img = bool(p.Imagebody.eval())
    if mode == 'page':
        lines = _dat_lines(p.Pagedat.eval() or m.op('page')) or []
        hdr = header_text(p.Header.eval(), T, p.Pagenum.eval())
        return tt_page(lines, cols, rows, img, hdr)
    if mode == 'subtitle':
        dl = _dat_lines(p.Subtitledat.eval())
        txt = '|'.join(dl) if dl else p.Subtitle.eval()
        return tt_subtitle(txt, cols, rows, p.Subcolour.eval(), bool(p.Subdouble.eval()), int(p.Subrow.eval()), img)
    return tt_image(cols, rows)


def display_codes_td(m, T, w, h):
    p = m.par
    disp = p.Display.eval()
    if disp in DOT_DISPLAYS:
        _ds, gw, gh = dot_grid(w, h, p.Dotsize.eval())
        cols, rows = max(1, gw // 8), max(1, gh // 8)
    else:
        cols, rows = max(1, int(p.Columns.eval())), max(1, int(p.Rows.eval()))
    dl = _dat_lines(p.Textdat.eval())
    text = '\n'.join(dl) if dl else p.Text.eval()
    return display_codes(disp, p.Content.eval(), text, p.Value.eval(), p.Format.eval(), T, cols, rows,
                         p.Align.eval())
