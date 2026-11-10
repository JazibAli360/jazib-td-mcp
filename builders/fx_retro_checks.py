"""fx_retro_checks: live checks for /project1/lab/FX_retro (docs/builds/fx_retro.md LIVE CHECKS). Runs INSIDE TD via
td_exec, always in TWO execs (T-74 / T-111 (4) / T-116 (4): never read pixels in the exec that changed them):
    ns = dict(globals()); exec(open('<repo>/builders/fx_retro_checks.py').read(), ns); ns['setup'](c, 'P1')   # exec 1
    ns = dict(globals()); exec(open('<repo>/builders/fx_retro_checks.py').read(), ns); ns['check'](c, 'P1')   # exec 2
c = op('/project1/lab/FX_retro'). setup() solos the check's slot (others enabled 0), resets that module's pars to
their defaults, applies the check's pars, sets the rack Input (test clip paused / ramp) and, for timed checks,
schedules delayed reads (run(delayFrames)) that store plain numbers in c.storage['fx_retro_check'] (T-67: plain data
only). check() runs >= 3 frames later (timed checks: after the `wait` seconds the doc lists) and returns
{'pass': bool, ...numbers}. The numpy references mirror fx_retro_logic (the rack DAT module, so this also exercises
the runtime import of palette_map_logic). Offline, test/test_fx_retro.py runs the pure numpy parts on synthetic data.
ASCII only.
"""
import math

try:
    import numpy as np
except ImportError:                                      # pragma: no cover
    np = None


# ------------------------------------------------------------------ numpy references (pure; tested offline)
M1 = [[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
      [0.0883024619, 0.2817188376, 0.6299787005]]
M2 = [[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
      [0.0259040371, 0.7827717662, -0.8086757660]]


def np_oklab(c):
    c = np.asarray(c, dtype=np.float64)
    lin = np.where(c <= 0.04045, c / 12.92, ((np.clip(c, 0, None) + 0.055) / 1.055) ** 2.4)
    lms = np.cbrt(lin @ np.array(M1).T)
    return lms @ np.array(M2).T


def np_pick(rgb, pal_rgb, thr=None, amount=1.0, space='oklab', wl=1.0):
    """Vectorised fx_retro_logic.pick / palette_map_logic.pick: rgb (N, 3), pal (K, 3) -> index (N,)."""
    q = np_oklab(rgb) if space == 'oklab' else np.asarray(rgb, np.float64)
    P = np_oklab(pal_rgb) if space == 'oklab' else np.asarray(pal_rgb, np.float64)
    w = np.array([wl, 1.0, 1.0]) if space == 'oklab' else np.ones(3)
    d = (((q[:, None, :] - P[None, :, :]) * w) ** 2).sum(-1)
    order = np.argsort(d, axis=1, kind='stable')
    i1 = order[:, 0]
    if thr is None or P.shape[0] < 2:
        return i1
    i2 = order[:, 1]
    e1 = np.sqrt(np.take_along_axis(d, i1[:, None], 1)[:, 0])
    e2 = np.sqrt(np.take_along_axis(d, i2[:, None], 1)[:, 0])
    t = np.where(e1 + e2 > 0, e1 / np.maximum(e1 + e2, 1e-30), 0.0)
    return np.where(t * amount > thr, i2, i1)


def np_bayer(h, w, n, ox=0, oy=0):
    """Bayer thresholds (h, w) for rows y = 0.. (bottom first), the GLSL bayerT((x + ox) & k, (y + oy) & k)."""
    k = (1 << n) - 1
    y, x = np.mgrid[0:h, 0:w]
    x, y = (x + ox) & k, (y + oy) & k
    v = np.zeros((h, w), np.int64)
    for i in range(n):
        bx, by, s = (x >> i) & 1, (y >> i) & 1, 2 * (n - 1 - i)
        v |= ((bx ^ by) << (s + 1)) | (by << s)
    return (v + 0.5) / float(1 << (2 * n))


def block_means(a, psx, psy):
    """(H, W, C) bottom-first -> (VH, VW, C) means of whole psx x psy blocks (crops a partial edge)."""
    H, W = a.shape[0] // psy * psy, a.shape[1] // psx * psx
    b = a[:H, :W].reshape(H // psy, psy, W // psx, psx, a.shape[2])
    return b.mean(axis=(1, 3))


def block_uniform(a8, psx, psy):
    """Number of whole blocks whose 8-bit pixels are not all equal."""
    H, W = a8.shape[0] // psy * psy, a8.shape[1] // psx * psx
    b = a8[:H, :W, :3].reshape(H // psy, psy, W // psx, psx, 3)
    return int((b.max(axis=(1, 3)) != b.min(axis=(1, 3))).any(-1).sum())


def colours8(a8):
    return set(map(tuple, a8[..., :3].reshape(-1, 3).tolist()))


def hex8(h):
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def bilinear(img, px, py):
    """TD texture() at pixel coords (px, py) (texel centres at +0.5, clamp): img (H, W, C) bottom-first."""
    H, W = img.shape[:2]
    x = np.clip(px - 0.5, 0, W - 1)
    y = np.clip(py - 0.5, 0, H - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, W - 1), np.minimum(y0 + 1, H - 1)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    return ((img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy) + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy)


def glyph_cell_means(img, cw, ch, cols, rows):
    """Cell mean luma of the glyph shader's 8x8 sample grid (cells from the top)."""
    H = img.shape[0]
    t = (np.arange(8) + 0.5) / 8.0
    cx = np.arange(cols)[:, None] * cw + t[None, :] * cw                     # (cols, 8)
    cy = np.arange(rows)[:, None] * ch + t[None, :] * ch                     # (rows, 8) from the top
    PX = np.broadcast_to(cx[None, None, :, :], (rows, 8, cols, 8))
    PY = H - np.broadcast_to(cy[:, :, None, None], (rows, 8, cols, 8))
    s = bilinear(img[..., :3], PX, PY)
    lum = s @ np.array([0.2126, 0.7152, 0.0722])
    return lum.mean(axis=(1, 3))                                             # (rows, cols)


def cell_bounds(n, size):
    return np.ceil(np.arange(n + 1) * size).astype(int)


def luma_quant(L, levels):
    """quant(rgb) for fx_retro_logic.diffuse: grey levels of the luma (the fxd shader's Colour = luma)."""
    def q(c):
        v = L.quant_levels(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2], levels, 0.5)
        return [v, v, v]
    return q


def ham_violations(row8, base8):
    """Pixels of a HAM row (8-bit, left to right) that are neither a base entry nor a one-channel modify."""
    bad, prev = 0, base8[0]
    for c in row8:
        c = tuple(c)
        if c not in base8 and sum(1 for k in range(3) if c[k] != prev[k]) > 1:
            bad += 1
        prev = c
    return bad


# ------------------------------------------------------------------ TD side
CHECKS = {
    # id: (module, input, {par: value}, wait s)
    'P0': ('palette', 'test', {'Amount': 0.0}, 0.1),
    'P1': ('palette', 'test', {'Machine': 'dmg', 'Pixelsize': 4.0, 'Dither': 'none', 'Sampling': 'box'}, 0.1),
    'P2': ('palette', 'test', {'Machine': 'nes', 'Pixelsize': 4.0, 'Pixelaspect': 8.0 / 7.0, 'Dither': 'none'}, 0.1),
    'P3': ('palette', 'test', {'Machine': 'spectrum', 'Constraint': 'auto', 'Pixelsize': 4.0, 'Dither': 'none'}, 0.1),
    'P4': ('palette', 'test', {'Machine': 'amiga12', 'Pixelsize': 2.0, 'Dither': 'none'}, 0.1),
    'P5': ('palette', 'test', {'Machine': 'amigaham', 'Constraint': 'auto', 'Pixelsize': 3.0}, 0.1),
    'P6': ('palette', 'ramp', {'Machine': 'pico8', 'Pixelsize': 1.0, 'Dither': 'bayer8', 'Ditheramt': 1.0}, 0.1),
    'D0': ('dither', 'test', {'Amount': 0.0}, 0.1),
    'D1': ('dither', 'ramp', {'Method': 'bayer8', 'Colour': 'luma', 'Levels': 2, 'Pixelsize': 1.0}, 0.1),
    'D2': ('dither', 'ramp', {'Method': 'blue', 'Colour': 'rgb', 'Levels': 4, 'Pixelsize': 1.0}, 0.1),
    'D3': ('dither', 'ramp', {'Method': 'fs', 'Colour': 'luma', 'Levels': 2, 'Pixelsize': 1.0, 'Tile': 32,
                              'Serpentine': True}, 0.1),
    'D4': ('dither', 'test', {'Method': 'gbcam', 'Colour': 'palette', 'Machine': 'dmg', 'Pixelsize': 8.0}, 0.1),
    'G0': ('glyph', 'test', {'Amount': 0.0}, 0.1),
    'G1': ('glyph', 'test', {'Mode': 'ascii', 'Charset': 'ascii', 'Colour': 'mono', 'Bgmode': 'black', 'Cellw': 12,
                             'Cellh': 12, 'Fgr': 1.0, 'Fgg': 1.0, 'Fgb': 1.0, 'Smooth': False}, 0.1),
    'G2': ('glyph', 'test', {'Mode': 'textmode', 'Shapeset': 'basic+blocks', 'Colour': 'palette', 'Machine': 'cga16',
                             'Cellw': 8, 'Cellh': 16}, 0.1),
    'G3': ('glyph', 'test', {'Mode': 'matrix', 'Charset': 'hiragana', 'Colour': 'mono', 'Bgmode': 'black'}, 0.1),
    'T0': ('teletext', 'test', {'Amount': 0.0}, 0.1),
    'T1': ('teletext', 'test', {'Mode': 'image', 'Columns': 40, 'Rows': 0, 'Separated': False}, 0.1),
    'T2': ('teletext', 'test', {'Mode': 'page', 'Columns': 40, 'Rows': 25, 'Loadtime': 0.0, 'Flashhz': 0.0}, 0.2),
    'S0': ('smalldisplay', 'test', {'Amount': 0.0}, 0.1),
    'S1': ('smalldisplay', 'test', {'Display': 'lcd', 'Content': 'image', 'Dotsize': 8.0, 'Levels': 4}, 1.0),
    'S2': ('smalldisplay', 'test', {'Display': 'flipdot', 'Content': 'image', 'Dotsize': 18.0, 'Threshold': 0.5}, 1.5),
    'S3': ('smalldisplay', 'test', {'Display': 'nixie', 'Content': 'clock', 'Columns': 8, 'Rows': 1}, 0.5),
    'S4': ('smalldisplay', 'test', {'Display': 'splitflap', 'Content': 'text', 'Text': ' ', 'Columns': 8,
                                    'Rows': 6, 'Align': 'left', 'Flapstep': 0.03}, 0.5),    # then settext()
    'S5': ('smalldisplay', 'test', {'Display': 'eink', 'Content': 'image', 'Dotsize': 3.0, 'Levels': 16,
                                    'Updatehz': 4.0, 'Flashtime': 1.2, 'Refreshperiod': 0.0}, 1.0),
    'S6': ('smalldisplay', 'test', {'Display': 'vfd', 'Content': 'image', 'Dotsize': 10.0, 'Levels': 2,
                                    'Threshold': 0.45}, 0.2),
}


def _lg(c):
    return c.op('fx_retro_logic').module


def _inst(c, module):
    t = c.op('slots')
    for i in range(1, t.numRows):
        if t[i, 'module'].val == module:
            return t[i, 'name'].val
    return None


def _defaults(m):
    for p in m.customPars:
        if p.page.name in ('Zkit',) or p.style in ('Pulse',) or p.readOnly:
            continue
        if p.mode != ParMode.CONSTANT:                                       # noqa: F821
            continue
        try:
            p.val = p.default
        except Exception:                                                    # noqa: BLE001
            pass


def setup(c, cid):
    module, inp, pars, wait = CHECKS[cid]
    name = _inst(c, module)
    c.allowCooking = True
    t = c.op('slots')
    for i in range(1, t.numRows):
        t[i, 'enabled'] = 1 if t[i, 'name'].val == name else 0
        t[i, 'mix'] = 1
    c.par.Panic = False
    c.par.Input = inp
    c.op('test_clip').par.play = False
    m = c.op(name)
    _defaults(m)
    for k, v in pars.items():
        getattr(m.par, k).val = v
    c.storage.pop('fx_retro_check', None)
    return {'check': cid, 'instance': m.path, 'read_after_s': wait}


def _rd(o):
    return o.numpyArray(delayed=False).astype(np.float64)


def _8(a):
    return np.round(a * 255.0).astype(np.int64)


def check(c, cid):
    module, inp, pars, wait = CHECKS[cid]
    m = c.op(_inst(c, module))
    L = _lg(c)
    I = _rd(m.op('in1'))
    O = _rd(m.op('out1'))
    O8 = _8(O)
    r = {'check': cid}
    if pars.get('Amount') == 0.0:
        r['max_diff'] = float(np.abs(O - I).max())
        r['pass'] = r['max_diff'] == 0.0
        return r
    return globals()['_check_' + cid[0]](c, m, L, cid, I, O, O8, r)


def _check_P(c, m, L, cid, I, O, O8, r):
    mach = m.par.Machine.eval()
    pal_hex = L.machine_hex(mach)
    pal8 = set(hex8(h) for h in pal_hex)
    cols = colours8(O8)
    psx, psy, VW, VH = L.vgrid(I.shape[1], I.shape[0], m.par.Pixelsize.eval(), m.par.Pixelaspect.eval())
    r['unique'] = len(cols)
    r['blocks_not_uniform'] = block_uniform(O8, psx, psy)
    if cid == 'P4':
        r['not_mult_17'] = int((O8[..., :3] % 17 != 0).sum())
        r['pass'] = r['not_mult_17'] == 0 and r['blocks_not_uniform'] == 0
        return r
    r['outside_palette'] = len(cols - pal8)
    ok = r['outside_palette'] == 0 and r['blocks_not_uniform'] == 0
    means = block_means(I[..., :3], psx, psy)
    outb = O8[psy // 2::psy, psx // 2::psx, :3][:means.shape[0], :means.shape[1]]
    pal_rgb = [L.PM.hex_to_rgb(h) for h in pal_hex]
    if cid in ('P1', 'P2'):
        idx = np_pick(means.reshape(-1, 3), pal_rgb)
        ref = np.array([hex8(pal_hex[i]) for i in idx]).reshape(outb.shape)
        r['agree'] = float((ref == outb).all(-1).mean())
        ok = ok and r['agree'] >= 0.995 and (cid != 'P2' or r['unique'] <= 55)
    elif cid == 'P3':
        bad = 0
        H8, W8 = outb.shape[0] // 8, outb.shape[1] // 8
        for cy in range(H8):
            for cx in range(W8):
                cell = set(map(tuple, outb[cy * 8:(cy + 1) * 8, cx * 8:(cx + 1) * 8].reshape(-1, 3).tolist()))
                idxs = [pal_hex.index('%02X%02X%02X' % p) for p in cell]
                if len(cell) > 2 or len(set(i < 8 for i in idxs)) > 1:
                    bad += 1
        r['cells_bad'] = bad
        rng = np.random.default_rng(1)
        agree = 0
        for _k in range(50):
            cy, cx = int(rng.integers(H8)), int(rng.integers(W8))
            px = [tuple(v) for v in means[cy * 8:(cy + 1) * 8, cx * 8:(cx + 1) * 8].reshape(-1, 3)]
            i, j, _cost = L.cell_pair(px, pal_rgb, halves_rule=1)
            got = set(map(tuple, outb[cy * 8:(cy + 1) * 8, cx * 8:(cx + 1) * 8].reshape(-1, 3).tolist()))
            agree += got <= {hex8(pal_hex[i]), hex8(pal_hex[j])}
        r['ref_cells_agree_of_50'] = agree
        ok = ok and bad == 0 and agree >= 48
    elif cid == 'P5':
        base8 = [hex8(h) for h in pal_hex]
        r['ham_violations'] = sum(ham_violations(outb[y].tolist(), base8) for y in range(outb.shape[0]))
        r.pop('outside_palette')
        rng = np.random.default_rng(2)
        same, tot = 0, 0
        for y in rng.integers(0, outb.shape[0], 6):
            ref = L.ham_row([tuple(v) for v in means[y]], pal_rgb)
            refb = np.round(np.array([v for v, _c in ref]) * 255).astype(int)
            same += int((refb == outb[y]).all(-1).sum())
            tot += refb.shape[0]
        r['ham_ref_agree'] = same / float(tot)
        ok = r['ham_violations'] == 0 and r['blocks_not_uniform'] == 0 and r['ham_ref_agree'] >= 0.98
    elif cid == 'P6':
        thr = np_bayer(means.shape[0], means.shape[1], 3)
        idx = np_pick(means.reshape(-1, 3), pal_rgb, thr=thr.reshape(-1), amount=m.par.Ditheramt.eval())
        ref = np.array([hex8(pal_hex[i]) for i in idx]).reshape(outb.shape)
        r['agree'] = float((ref == outb).all(-1).mean())
        ok = ok and r['agree'] >= 0.99
    r['pass'] = bool(ok)
    return r


def _check_D(c, m, L, cid, I, O, O8, r):
    lum = I[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
    vals = sorted(set(O8[..., :3].reshape(-1).tolist()))
    r['values'] = vals[:8]
    if cid == 'D1':
        ref = np.clip(np.floor(lum + np_bayer(lum.shape[0], lum.shape[1], 3)), 0, 1) * 255
        r['agree'] = float((ref == O8[..., 0]).mean())
        r['pass'] = vals == [0, 255] and r['agree'] >= 0.999
    elif cid == 'D2':
        T = 64
        H, W = O.shape[0] // T * T, O.shape[1] // T * T
        mo = O[:H, :W, :3].reshape(H // T, T, W // T, T, 3).mean(axis=(1, 3))
        mi = I[:H, :W, :3].reshape(H // T, T, W // T, T, 3).mean(axis=(1, 3))
        r['tile_mean_err_max'] = float(np.abs(mo - mi).max())
        r['pass'] = set(vals) <= {0, 85, 170, 255} and r['tile_mean_err_max'] <= 0.02
    elif cid == 'D3':
        T = 32
        H, W = O.shape[0] // T * T, O.shape[1] // T * T
        mo = O[:H, :W, 0].reshape(H // T, T, W // T, T).mean(axis=(1, 3))
        mi = lum[:H, :W].reshape(H // T, T, W // T, T).mean(axis=(1, 3))
        r['tile_mean_err_max'] = float(np.abs(mo - mi).max())
        top = I[::-1][:T, :T, :3]                                            # the top-left tile, rows top-first
        img = [[tuple(v) for v in row] for row in top]
        ref = L.diffuse(img, 'fs', luma_quant(L, 2), serpentine=True)
        refa = np.array([[p[0] for p in row] for row in ref]) * 255
        r['tile0_agree'] = float((refa == O8[::-1][:T, :T, 0]).mean())
        r['pass'] = vals == [0, 255] and r['tile_mean_err_max'] <= 0.03 and r['tile0_agree'] >= 0.9
    elif cid == 'D4':
        pal8 = set(hex8(h) for h in L.machine_hex('dmg'))
        r['outside_palette'] = len(colours8(O8) - pal8)
        r['blocks_not_uniform'] = block_uniform(O8, 8, 8)
        r['pass'] = r['outside_palette'] == 0 and r['blocks_not_uniform'] == 0
    return r


def _check_G(c, m, L, cid, I, O, O8, r):
    H, W = I.shape[:2]
    cw, ch = int(m.par.Cellw.eval()), int(m.par.Cellh.eval())
    cols, rows = -(-W // cw), -(-H // ch)
    T8 = O8[::-1]                                                            # top-first
    if cid == 'G1':
        vals = colours8(O8)
        r['colours'] = len(vals)
        means = glyph_cell_means(I, cw, ch, cols, rows)
        ramp = L.ramp('ascii')
        n = len(ramp)
        good = 0
        tot = 0
        for cy in range(rows):
            for cx in range(cols):
                if (cx + 1) * cw > W or (cy + 1) * ch > H:
                    continue
                g = ramp[max(0, min(n - 1, int(math.floor(means[cy, cx] * n))))]
                ys, xs = np.mgrid[0:ch, 0:cw]
                exp = np.vectorize(lambda yy, xx: L.font_bit(g, int((xx + 0.5) / cw * 8), int((yy + 0.5) / ch * 8)))(
                    ys, xs)
                got = T8[cy * ch:(cy + 1) * ch, cx * cw:(cx + 1) * cw, 0] > 127
                good += bool((exp == got).all())
                tot += 1
        r['cells_match'] = good / float(max(tot, 1))
        r['pass'] = vals <= {(0, 0, 0), (255, 255, 255)} and r['cells_match'] >= 0.98
    elif cid == 'G2':
        pal8 = set(hex8(h) for h in L.machine_hex('cga16'))
        r['outside_palette'] = len(colours8(O8) - pal8)
        bad = 0
        for cy in range(H // ch):
            for cx in range(W // cw):
                if len(colours8(T8[cy * ch:(cy + 1) * ch, cx * cw:(cx + 1) * cw])) > 2:
                    bad += 1
        r['cells_over_2_colours'] = bad
        r['pass'] = r['outside_palette'] == 0 and bad == 0
    elif cid == 'G3':
        st = c.storage.get('fx_retro_check')
        if st is None:                                                       # first call: remember, ask again
            c.storage['fx_retro_check'] = {'sum': float(O[..., :3].sum()), 'lit': float((O8[..., 1] > 0).mean()),
                                           'g': O8[..., 1].copy()}
            r['again_after_s'] = 0.5
            r['pass'] = None
            return r
        r['lit_share'] = float((O8[..., 1] > 0).mean())
        r['sum_changed'] = abs(float(O[..., :3].sum()) - st['sum']) / max(st['sum'], 1.0)   # rgb: alpha 1 swamped it
        r['px_changed'] = float((O8[..., 1] != st['g']).mean())    # live 31550: the rgb sum barely moves (0.002-0.03)
        r['pass'] = 0.005 <= r['lit_share'] <= 0.6 and r['px_changed'] > 0.005  # defaults: lit ~0.016, moved ~0.03
    return r


TT8 = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)]


def _check_T(c, m, L, cid, I, O, O8, r):
    H, W = I.shape[:2]
    cols, rows, cw, ch = L.tt_grid(W, H, m.par.Columns.eval(), m.par.Rows.eval(), m.par.Cellaspect.eval())
    T8 = O8[::-1]
    xb, yb = cell_bounds(cols, cw), cell_bounds(rows, ch)
    r['outside_8'] = len(colours8(O8) - set(TT8))
    bad = 0
    for cy in range(rows):
        for cx in range(cols):
            if len(colours8(T8[yb[cy]:yb[cy + 1], xb[cx]:xb[cx + 1]])) > 2:
                bad += 1
    r['cells_over_2_colours'] = bad
    ok = r['outside_8'] == 0 and bad == 0
    if cid == 'T2':
        codes = m.op('codes').chan('c').vals
        r['codes'] = len(codes)
        tm = __import__('time').localtime()
        T = (tm.tm_year, tm.tm_mon, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec, tm.tm_wday)
        hdr = ''.join(chr(L.tt_unpack(v)['ch']) for v in codes[:cols])
        want = ''.join(chr(L.tt_unpack(v)['ch']) for v in L.tt_row(L.header_text(m.par.Header.eval(), T,
                                                                                m.par.Pagenum.eval()), cols))
        r['header'] = hdr
        r['header_ok'] = hdr[:20] == want[:20]                               # the clock part may be 1 s apart
        ok = ok and r['codes'] == cols * rows and r['header_ok']
    r['pass'] = bool(ok)
    return r


def _check_S(c, m, L, cid, I, O, O8, r):
    S = m.op('state').numpyArray(delayed=False).astype(np.float64)           # S[gy, gx]: gy is already top-based
    disp = m.par.Display.eval()
    r['state_size'] = [S.shape[1], S.shape[0]]
    if cid == 'S1':
        vals = np.round(S[..., 0] * 3.0, 4)
        r['state_levels_ok'] = float((np.abs(vals - np.round(vals)) < 1e-3).mean())
        r['pass'] = r['state_levels_ok'] >= 0.999 and r['state_size'] == list(L.dot_grid(I.shape[1], I.shape[0],
                                                                                          8)[1:])
    elif cid in ('S2', 'S6'):
        ds = int(round(m.par.Dotsize.eval()))
        gw, gh = S.shape[1], S.shape[0]
        acc = 0
        for k in range(4):
            ox, oy = (k & 1) + 0.5, (k >> 1) + 0.5
            gx = np.arange(gw) * ds + ox * 0.5 * ds
            gy = np.arange(gh) * ds + oy * 0.5 * ds
            PX = np.broadcast_to(gx[None, :], (gh, gw))
            PY = I.shape[0] - np.broadcast_to(gy[:, None], (gh, gw))
            acc = acc + bilinear(I[..., :3], PX, PY)
        lum = (acc / 4.0) @ np.array([0.2126, 0.7152, 0.0722])
        tgt = (lum > m.par.Threshold.eval()).astype(float)
        r['state_agree'] = float((S[..., 0] == tgt).mean())
        r['flipping'] = int((S[..., 1] >= 0).sum()) if cid == 'S2' else 0
        r['pass'] = r['state_agree'] >= 0.995 and r['flipping'] == 0
    elif cid == 'S3':
        codes = list(m.op('codes').chan('c').vals)
        r['codes'] = codes
        r['digits'] = [int(v) for v in S[0, :, 0]]
        r['pass'] = r['digits'] == [int(v) - 1 for v in codes][:len(r['digits'])]
    elif cid == 'S4':
        codes = list(m.op('codes').chan('c').vals)
        want = [max(0, int(v) - 1) for v in codes]
        got = [int(round(v)) for v in S[..., 0].reshape(-1)]
        r['cells_on_target'] = sum(1 for a, b in zip(got, want) if a == b) / float(len(want))
        r['moving'] = int((S[..., 1] >= 0).sum())
        r['pass'] = r['cells_on_target'] == 1.0 and r['moving'] == 0
    elif cid == 'S5':
        r['displayed_eq_target'] = float((np.abs(S[..., 0] - S[..., 1]) < 1e-6).mean())
        r['pass'] = r['displayed_eq_target'] >= 0.95
    r['display'] = disp
    return r


# ------------------------------------------------------------------ timed: split-flap text, e-ink flash, cost
def settext(c, text='HELLO|WORLD'):
    """After S4 settled on a blank board: new text; check(c, 'S4') at ~0.25 s shows cells moving, at >= 1.5 s all on
    target (WORLD needs 23 flaps of 2 frames at Flapstep 0.03 = ~0.77 s)."""
    m = c.op(_inst(c, 'smalldisplay'))
    m.par.Text = text
    return {'text': text, 'at': absTime.seconds}                             # noqa: F821



def eink_flash(c):
    """exec 1 after S5 has settled: pulse Refresh and schedule out1 mean reads at 0.15 / 0.45 / 0.75 / 1.5 s;
    exec 2 (>= 2 s later): c.storage['fx_retro_check'] -> [(t, mean luma)], phases by fx_retro_logic.eink_phase."""
    m = c.op(_inst(c, 'smalldisplay'))
    m.par.Refresh.pulse()
    t0 = absTime.seconds                                                     # noqa: F821
    c.storage['fx_retro_check'] = {'t0': t0, 'reads': []}
    fps = 60
    for t in (0.15, 0.45, 0.75, 1.5):
        run("o = op(%r); a = o.op('out1').numpyArray(delayed=False); st = o.parent().storage['fx_retro_check']; "
            "st['reads'].append([absTime.seconds - st['t0'], float(a[..., :3].mean())])" % m.path,
            delayFrames=int(t * fps))                                        # noqa: F821
    return {'scheduled': [0.15, 0.45, 0.75, 1.5]}


def cost(c, frames=120):
    """Schedule a per-frame pull of the soloed module's out1 (T-102): sum cpu + gpu cook ms of its ops that cooked in
    that frame; exec 2 reads c.storage['fx_retro_cost'] -> median / p90 ms. Pane elsewhere (T-111 (5))."""
    t = c.op('slots')
    name = next(t[i, 'name'].val for i in range(1, t.numRows) if t[i, 'enabled'].val == '1')
    c.storage['fx_retro_cost'] = {'name': name, 'ms': []}
    c.par.Input = 'test'                               # live 31550: a still input (paused clip, ramp) leaves the
    c.op('test_clip').par.play = True                  # passes uncooked, so only out1 / out_sel were counted
    code = ("c = op(%r); m = c.op(%r); o = m.op('out1'); o.cook(force=True); f = o.cookAbsFrame; "
            "c.storage['fx_retro_cost']['ms'].append(sum(x.cpuCookTime + getattr(x, 'gpuCookTime', 0) "
            "for x in m.findChildren(depth=1) if x.cookAbsFrame == f and x.family == 'TOP'))") % (c.path, name)
    for k in range(frames):
        run(code, delayFrames=k + 1)                                         # noqa: F821
    return {'module': name, 'frames': frames}


def cost_result(c):
    ms = sorted(c.storage.get('fx_retro_cost', {}).get('ms', []))[10:]
    if not ms:
        return {'ms': None}
    return {'median_ms': ms[len(ms) // 2], 'p90_ms': ms[int(len(ms) * 0.9)], 'n': len(ms)}
