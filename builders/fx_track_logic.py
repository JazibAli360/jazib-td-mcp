"""fx_track_logic - float64 per-pixel references of the FX_track module passes (lane F; doc docs/builds/fx_track.md).
The tracker mirrors (det / cells / pts), font and candidates live in fx_track_lib.py (shared with the shaders).
Each *_pixel(p, ...) = the module's fx pass at output pixel p = (x, y) (y up, TD order); images (H, W, 4) row 0 =
bottom. pars = module par values (menus as index), rk = rack values {Detector, Cellsx, Cellsy, N, Threshold, Resw,
Resh}, pal(t) -> rgb (palette_map_logic.pal_eval on the live uPal rows). Pure: no td. ASCII only."""
import math
import os
import sys

import numpy as np

_HERE = globals().get('HERE') or os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import fx_track_lib as FL  # noqa: E402

LUMA = np.array([0.2126, 0.7152, 0.0722])


def _cl(x, a=0.0, b=1.0):
    return min(max(x, a), b)


def _cands(uv, reach, rk):
    return FL.candidates(uv, reach, rk['Detector'], int(rk['Cellsx']), int(rk['Cellsy']), int(rk['N']))


def plexus_pixel(p, base, src, pts, P, rk, res, pal):
    """= plexus fx: base = lines out1 sampled at the pixel (same size), src = in1 pixel."""
    pc = (p[0] + 0.5, p[1] + 0.5)
    uv = (pc[0] / res[0], pc[1] / res[1])
    col = np.array(base[:3], np.float64)
    if P['Levels'] > 0.5:
        col = np.floor(col * P['Levels'] + 0.5) / P['Levels']
    da, dc = 0.0, np.zeros(3)
    st = int(P['Dotstyle'])
    if st > 0:
        R, w = max(P['Dotradius'], 0.0), max(P['Dotwidth'], 0.25)
        for i in _cands(uv, ((R + w + 1) / res[0], (R + w + 1) / res[1]), rk):
            T0, T1, T3 = FL.pt(pts, i, 0), FL.pt(pts, i, 1), FL.pt(pts, i, 3)
            if T0[3] < 0.5:
                continue
            q = (pc[0] - T1[0] * res[0], pc[1] - T1[1] * res[1])
            d = math.hypot(*q)
            if st == 1:
                a = _cl(R - d + 0.5)
            elif st == 2:
                a = _cl(0.5 * w - abs(d - R) + 0.5)
            else:
                aq = (abs(q[0]), abs(q[1]))
                a = _cl(0.5 * w - min(aq) + 0.5) if max(aq) <= R + 0.5 else 0.0
            if a > da:
                da = a
                dc = FL.col_ref(int(P['Dotcolsrc']), (P['Dotr'], P['Dotg'], P['Dotb']), T1, T3, res, P['Speedref'],
                                pal) * P['Dotgain']
    col = col * (1 - da) + dc * da
    o = np.array([col[0], col[1], col[2], max(base[3], da)])
    return np.asarray(src, np.float64) * (1 - P['Amount']) + o * P['Amount']


def tile_candidates(p, res, rneg, rpos, rk):
    """= the hud's ftTile range for pixel p's 8x8 tile, ascending point index (the list order does not matter on the
    GPU: ties go to the lower index)."""
    tx, ty = (p[0] // 8) * 8, (p[1] // 8) * 8
    lo = ((tx + 0.5) / res[0], (ty + 0.5) / res[1])
    hi = ((tx + 7.5) / res[0], (ty + 7.5) / res[1])
    if int(rk['Detector']) != 0:
        return list(range(min(int(rk['N']), 256)))
    cx_n, cy_n = int(rk['Cellsx']), int(rk['Cellsy'])
    cl = lambda v, n: min(max(int(math.floor(v * n)), 0), n - 1)
    rn = [min(int(math.ceil(rneg[0] * cx_n)), FL.FT_REACH), min(int(math.ceil(rneg[1] * cy_n)), FL.FT_REACH)]
    rp = [min(int(math.ceil(rpos[0] * cx_n)), FL.FT_REACH), min(int(math.ceil(rpos[1] * cy_n)), FL.FT_REACH)]
    x0, x1 = max(cl(lo[0], cx_n) - rn[0], 0), min(cl(hi[0], cx_n) + rp[0], cx_n - 1)
    y0, y1 = max(cl(lo[1], cy_n) - rn[1], 0), min(cl(hi[1], cy_n) + rp[1], cy_n - 1)
    return [y * cx_n + x for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]


def hud_pixel(p, src, pts, P, rk, res, pal, t):
    pc = (p[0] + 0.5, p[1] + 0.5)
    uv = (pc[0] / res[0], pc[1] / res[1])
    col = np.asarray(src[:3], np.float64) * (1 - P['Bgdim'])
    l0, l1 = FL.LABEL_LINES[min(max(int(P['Labels']), 0), 7)]
    nl = (l0 > 0) + (l1 > 0)
    sc, w = max(P['Labelscale'], 1e-3), max(P['Boxwidth'], 0.25)
    lw = max(FL.LINE_LEN[l0], FL.LINE_LEN[l1]) * 8.0 * sc
    ex = abs(P['Boxpad']) + P['Boxmin'] + P['Cross'] + w + 2.0
    rneg = ((lw + 2 * sc + ex) / res[0], (nl * 9.0 * sc + abs(P['Labelgap']) + 2 * sc + ex) / res[1])
    rpos = (ex / res[0] + 1.0 / max(rk['Cellsx'], 1), ex / res[1] + 1.0 / max(rk['Cellsy'], 1))
    bs = int(P['Boxstyle'])
    ha, ba, hc = 0.0, 0.0, np.zeros(3)
    for i in tile_candidates(p, res, rneg, rpos, rk):
        T0, T1, T2, T3 = (FL.pt(pts, i, k) for k in range(4))
        if T0[3] < 0.5:
            continue
        if T1[2] < P['Minstrength'] or FL.fthash(T3[0], int(P['Seed']) + 1) > P['Share']:
            continue
        c = (T1[0] * res[0], T1[1] * res[1])
        b0 = (T2[0] * res[0] - P['Boxpad'], T2[1] * res[1] - P['Boxpad'])
        b1 = (T2[2] * res[0] + P['Boxpad'], T2[3] * res[1] + P['Boxpad'])
        bc = (0.5 * (b0[0] + b1[0]), 0.5 * (b0[1] + b1[1]))
        hf = (max(0.5 * (b1[0] - b0[0]), 0.5 * P['Boxmin']), max(0.5 * (b1[1] - b0[1]), 0.5 * P['Boxmin']))
        b0 = (bc[0] - hf[0], bc[1] - hf[1])
        b1 = (bc[0] + hf[0], bc[1] + hf[1])
        a = 0.0
        if bs in (1, 2):
            q = (abs(pc[0] - bc[0]) - hf[0], abs(pc[1] - bc[1]) - hf[1])
            sd = math.hypot(max(q[0], 0), max(q[1], 0)) + min(max(q[0], q[1]), 0)
            a = _cl(0.5 * w - abs(sd) + 0.5)
            if bs == 2:
                Lc = P['Cornerlen'] * 2 * min(hf)
                d = (abs(pc[0] - bc[0]), abs(pc[1] - bc[1]))
                if not (d[0] >= hf[0] - Lc and d[1] >= hf[1] - Lc):
                    a = 0.0
        elif bs == 3:
            a = _cl(0.5 * w - abs(math.hypot(pc[0] - bc[0], pc[1] - bc[1]) - max(hf)) + 0.5)
        if P['Cross'] > 0:
            aq = (abs(pc[0] - c[0]), abs(pc[1] - c[1]))
            m = max(aq)
            if P['Crossgap'] <= m <= P['Cross']:
                a = max(a, _cl(0.5 * w - min(aq) + 0.5))
        if nl > 0 and FL.fthash(T3[0] * 7.0 + math.floor(t * P['Flickerhz']), int(P['Seed']) + 3) >= P['Flicker']:
            y0 = b1[1] + P['Labelgap']
            if b0[0] - sc <= pc[0] < b0[0] + lw + sc and y0 - sc <= pc[1] < y0 + nl * 9.0 * sc:
                ba = max(ba, P['Labelbg'])
            v = (T3[0], math.floor(c[0] + 0.5), math.floor(c[1] + 0.5), math.hypot(T3[2] * res[0], T3[3] * res[1]))
            tt = 0.0
            if l0 > 0:
                tt = FL.text_at(pc, (b0[0], y0 + (nl - 1) * 9.0 * sc), sc, l0, v[:3] + (T3[1],) if l0 == 4 else v)
            if l1 > 0:
                tt = max(tt, FL.text_at(pc, (b0[0], y0), sc, l1, v[:3] + (T3[1],) if l1 == 4 else v))
            a = max(a, tt)
        if a > ha:
            ha = a
            hc = FL.col_ref(int(P['Colsrc']), (P['Colr'], P['Colg'], P['Colb']), T1, T3, res, P['Speedref'],
                            pal) * P['Gain']
    col = col * (1 - ba)
    col = col * (1 - ha) + hc * ha
    o = np.array([col[0], col[1], col[2], max(src[3], ha, ba)])
    return np.asarray(src, np.float64) * (1 - P['Amount']) + o * P['Amount']


def hs_step(det, pts, fb, P, rk, now):
    """= analytics hs: det (Deth, Detw, 4) key in r, fb = last hs or None -> (Deth + 1, Detw, 4)."""
    dh, dw = det.shape[:2]
    out = np.zeros((dh + 1, dw, 4))
    same = fb is not None and fb.shape == out.shape
    last = fb[dh, 0, 3] if same else -1.0
    dt = _cl(now - last, 0.0, 0.1) if last > 0 else 0.0
    py, px = np.mgrid[0:dh, 0:dw].astype(np.float64)
    k = FL.bilinear(det, (px + 0.5) / dw, (py + 0.5) / dh)[..., 0]
    h = fb[:dh, :, 0] if same else np.zeros((dh, dw))
    out[:dh, :, 0] = h * math.exp(-dt / max(P['Heatdecay'], 1e-3)) + np.maximum(k - rk['Threshold'], 0) * P['Heatgain'] * dt
    out[:dh, :, 1] = k
    out[:dh, :, 3] = 1
    zx, zy = max(int(P['Zonesx']), 1), max(int(P['Zonesy']), 1)
    cnt = mov = ss = 0.0
    zc, zm = np.zeros(zx * zy), np.zeros(zx * zy)
    for i in range(int(rk['N'])):
        T0, T1, T3 = FL.pt(pts, i, 0), FL.pt(pts, i, 1), FL.pt(pts, i, 3)
        if T0[3] < 0.5:
            continue
        mv = math.hypot(T3[2] * rk['Resw'], T3[3] * rk['Resh']) > P['Moverthr']
        cnt += 1
        ss += T1[2]
        mov += mv
        zi = min(max(int(math.floor(T1[1] * zy)), 0), zy - 1) * zx + min(max(int(math.floor(T1[0] * zx)), 0), zx - 1)
        zc[zi] += 1
        zm[zi] += mv
    out[dh, 0] = [cnt, mov, ss / max(cnt, 1.0), now]
    for z in range(min(zx * zy, dw - 1)):
        out[dh, 1 + z] = [zc[z] / max(cnt, 1.0), zm[z], 0, 0]
    return out


def analytics_pixel(p, src_img, pts, hs, P, rk, res, pal, t):
    """= analytics fx at pixel p; src_img = in1 (for the mosaic); hs = the hs texture."""
    pc = (p[0] + 0.5, p[1] + 0.5)
    uv = (pc[0] / res[0], pc[1] / res[1])
    src = np.asarray(src_img[p[1], p[0]], np.float64)
    dh = hs.shape[0] - 1
    L = float(src[:3] @ LUMA)
    col = src[:3] * (1 - P['Mono']) + L * P['Mono']
    hv = float(FL.bilinear(hs, np.array(uv[0]), np.array(min(uv[1] * dh, dh - 0.5) / hs.shape[0]))[..., 0])
    hn = hv / max(P['Heatmax'], 1e-4)
    hm = int(P['Heat'])
    if hm == 1:
        s = _cl((hn - 0.02) / 0.28)
        f = P['Heatmix'] * s * s * (3 - 2 * s)
        col = col * (1 - f) + np.array(pal(_cl(hn))) * f
    elif hm == 2:
        col = col * (1 - P['Heatmix']) + np.array(pal(_cl(0.35 * L + hn))) * P['Heatmix']
    rm = int(P['Redact'])
    if rm > 0:
        hit = False
        for i in _cands(uv, ((abs(P['Redactpad']) + 2) / res[0], (abs(P['Redactpad']) + 2) / res[1]), rk):
            T0, T2, T3 = FL.pt(pts, i, 0), FL.pt(pts, i, 2), FL.pt(pts, i, 3)
            if T0[3] < 0.5:
                continue
            if int(P['Redacton']) == 1 and math.hypot(T3[2] * res[0], T3[3] * res[1]) <= P['Moverthr']:
                continue
            b0 = (T2[0] * res[0] - P['Redactpad'], T2[1] * res[1] - P['Redactpad'])
            b1 = (T2[2] * res[0] + P['Redactpad'], T2[3] * res[1] + P['Redactpad'])
            if b0[0] <= pc[0] < b1[0] and b0[1] <= pc[1] < b1[1]:
                hit = True
        if hit:
            if rm == 1:
                col = np.array([P['Barr'], P['Barg'], P['Barb']])
            else:
                m = max(P['Mosaic'], 1.0)
                s = FL.bilinear(src_img, np.array((math.floor(pc[0] / m) + 0.5) * m / res[0]),
                                np.array((math.floor(pc[1] / m) + 0.5) * m / res[1]))
                col = s[:3] * (1 - P['Mono']) + float(s[:3] @ LUMA) * P['Mono']
    zx, zy = max(int(P['Zonesx']), 1), max(int(P['Zonesy']), 1)
    zs = (res[0] / zx, res[1] / zy)
    zc = (min(max(int(math.floor(pc[0] / zs[0])), 0), zx - 1), min(max(int(math.floor(pc[1] / zs[1])), 0), zy - 1))
    z = zc[1] * zx + zc[0]
    st = hs[dh, 1 + z]
    a = 0.0
    hot = st[0] >= P['Zonethr'] and P['Zonethr'] >= 0 and st[0] > 0
    tc = np.array([P['Colr'], P['Colg'], P['Colb']])
    if hot:
        col = col * (1 - P['Zonefill']) + tc * P['Zonefill']
    if P['Zonewidth'] > 0:
        fz = (pc[0] - zc[0] * zs[0], pc[1] - zc[1] * zs[1])
        d = min(fz[0], zs[0] - fz[0], fz[1], zs[1] - fz[1])
        a = max(a, _cl(0.5 * P['Zonewidth'] - d + 0.5))
    sc = max(P['Textscale'], 1e-3)
    if P['Zonelabels'] > 0.5 and hot:
        org = (zc[0] * zs[0] + 6.0, zc[1] * zs[1] + zs[1] - 6.0 - 8.0 * sc * 0.67)
        a = max(a, FL.text_at(pc, org, sc * 0.67, 10, (z + 1, math.floor(st[0] * 100 + 0.5), 0, 0)))
    ra = 0.0
    if P['Overlay'] > 0.5:
        s0 = hs[dh, 0]
        m = P['Margin']
        top = res[1] - m - 8.0 * sc
        a = max(a, FL.text_at(pc, (m, top), sc, 9, (P['Cam'], 0, 0, 0)))
        a = max(a, FL.text_at(pc, (m, top - 10 * sc), sc, 8, (math.floor(t), 0, 0, 0)))
        dc = (m + 13 * 8 * sc + 4 * sc, top - 10 * sc + 4 * sc)
        if t - math.floor(t) < 0.5:
            ra = _cl(3 * sc - math.hypot(pc[0] - dc[0], pc[1] - dc[1]) + 0.5)
        a = max(a, FL.text_at(pc, (m, m + 10 * sc), sc, 6, (s0[0], 0, 0, 0)))
        a = max(a, FL.text_at(pc, (m, m), sc, 7, (s0[1], 0, 0, 0)))
    col = col * (1 - a) + tc * a
    col = col * (1 - ra) + np.array([P['Recr'], 0.05, 0.05]) * ra
    o = np.array([col[0], col[1], col[2], max(src[3], a, ra)])
    return src * (1 - P['Amount']) + o * P['Amount']
