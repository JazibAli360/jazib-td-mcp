"""gen_interactive_parallax_logic - float64 reference of GEN_interactive 'parallax' (FX7a SX-30 / 7C-31 / TC-05; lane
F, 27 Oct 2026). == builders/glsl/gen_interactive_parallax.glsl. Pure (numpy inside functions). ASCII only.
Images (H, W, C) with row 0 = bottom (TD order); uv 0..1 with texel centres at (i + 0.5) / size."""
import math


def bilinear(img, u, v):
    """texture() with extend hold (GLSL TOP inputextenduv hold) at uv -> (C,)."""
    import numpy as np
    img = np.asarray(img, np.float64)
    H, W = img.shape[:2]
    x = min(max(u * W - 0.5, 0.0), W - 1.0)
    y = min(max(v * H - 0.5, 0.0), H - 1.0)
    x0, y0 = int(math.floor(x)), int(math.floor(y))
    x1, y1 = min(x0 + 1, W - 1), min(y0 + 1, H - 1)
    fx, fy = x - x0, y - y0
    return (img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy) + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy


def depth_at(depth, u, v, lo, hi, inv):
    r = float(bilinear(depth, u, v)[0])
    d = min(max((r - lo) / max(hi - lo, 1e-6), 0.0), 1.0)
    return 1.0 - d if inv else d


def march(uv, O, dolly, steps, refine, depth, lo, hi, inv):
    """-> (q uv sampled, hit layer t). == the shader's relief march."""
    D = (O[0] + (uv[0] - 0.5) * dolly, O[1] + (uv[1] - 0.5) * dolly)
    n = min(max(int(round(steps)), 1), 256)
    tp, th, hit = 1.0, 0.0, False
    for i in range(n + 1):
        t = 1.0 - i / float(n)
        if depth_at(depth, uv[0] - D[0] * t, uv[1] - D[1] * t, lo, hi, inv) >= t:
            th, hit = t, True
            break
        tp = t
    if not hit:
        th = 0.0
    elif th < tp:
        a, b = th, tp
        for _j in range(min(max(int(round(refine)), 0), 16)):
            m = 0.5 * (a + b)
            if depth_at(depth, uv[0] - D[0] * m, uv[1] - D[1] * m, lo, hi, inv) >= m:
                a = m
            else:
                b = m
        th = a
    return (uv[0] - D[0] * th, uv[1] - D[1] * th), th


def pixel(px, py, base, colour, depth, P, O, palette, blend):
    """Output at pixel (px, py): base / colour / depth images, P module pars (menus as index), O = (ox, oy) offset uv
    the uniform got; palette / blend = gen_sim_logic.palette / blend."""
    import numpy as np
    H, W = base.shape[:2]
    uv = ((px + 0.5) / W, (py + 0.5) / H)
    lo, hi, inv = P['Depthlo'], P['Depthhi'], bool(P['Depthinvert'])
    if O == (0.0, 0.0) and P['Dolly'] == 0.0:
        col = np.asarray(colour[py, px], np.float64) if colour.shape[:2] == base.shape[:2] else bilinear(colour, *uv)
        dep = depth_at(depth, uv[0], uv[1], lo, hi, inv)
    else:
        q, _t = march(uv, O, P['Dolly'], P['Steps'], P['Refine'], depth, lo, hi, inv)
        col = bilinear(colour, *q)
        dep = depth_at(depth, q[0], q[1], lo, hi, inv)
    col = np.array(col, np.float64)
    nb = int(round(P['Bands']))
    if nb > 0 and P['Bandmix'] > 0:
        bi = min(math.floor(dep * nb), nb - 1)
        L = float(col[:3] @ np.array([0.2126, 0.7152, 0.0722]))
        bc = palette(np.array(bi / float(nb - 1) if nb > 1 else 0.0), int(P['Palette']),
                     (P['Colorar'], P['Colorag'], P['Colorab']), (P['Colorbr'], P['Colorbg'], P['Colorbb']),
                     P['Palshift']) * (0.4 + 0.8 * L)
        col[:3] = col[:3] + (bc - col[:3]) * P['Bandmix']
    f = min(max((1.0 - dep) * P['Fog'], 0.0), 1.0)
    col[:3] = col[:3] + (np.array([P['Colorar'], P['Colorag'], P['Colorab']]) - col[:3]) * f
    return blend(np.asarray(base[py, px], np.float64), col[:3] * col[3], np.array(col[3]), int(P['Blend']), P['Amount'])
