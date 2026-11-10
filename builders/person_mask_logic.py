"""person_mask logic: pure Python (no td), copied into CV_person_mask/person_mask_logic as a Text DAT module.

Matte model (our own): Apple Vision gives a soft person mask (alpha only, LEARNINGS T-99). We blur it by R px at mask
resolution and remap the blurred value linearly from [lo, hi] to [0, 1]:
- Feather f widens the ramp (soft edge), Grow g moves the edge outward (g > 0) or inward (choke, g < 0).
- R = f + |g|. A straight edge blurred over R px reads ~0.5 on the edge and ~0.5 -/+ d / (2R) at d px inside/outside
  (linear-ish ramp), so the 0.5-level moves by g px when the centre goes to 0.5 - g / (2R); the ramp half-width
  f / (2R) gives an edge about f px soft.
- f = g = 0: no blur, lo 0 / hi 1 = the raw Vision mask.
Temporal smooth s: m = mix(new, last, s) (s 0 = live). Invert flips m. Cut-out is premultiplied (overlay-alpha rule).
Pure ASCII.
"""

PLUGIN = ('~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/bgremoval/build/'
          'AppleVisionMask.plugin')
QUALITY = (('Fast', 'Fast (2 frames late)'), ('Balanced', 'Balanced (3 frames)'), ('Accurate', 'Accurate (7 frames)'))
INPUTSCALE = (('full', 'Full source size'), ('half', 'Half (960x540 from 1080p, fast path)'),
              ('quarter', 'Quarter'), ('fixed', 'Fixed 960 px long side'))
SCALE = {'full': 1.0, 'half': 0.5, 'quarter': 0.25}
PERSON = (('source', 'Source colour'), ('fill', 'Fill colour (silhouette)'))
BACKGROUND = (('none', 'Transparent (premultiplied)'), ('color', 'Background colour'), ('input', 'Background TOP (in2)'))
RGBDELAY = (('match', 'Full res, delayed to the mask'), ('plugin', 'Plugin delayed RGB (mask res)'),
            ('none', 'Live (no delay)'))
CACHE_SIZE = 12


def menu_index(menu, name, default=0):
    for k, (n, _label) in enumerate(menu):
        if n == name:
            return k
    return default


def vision_size(w, h, scale='half'):
    """Vision input size for a source size; even, at least 16 px. 'fixed' = long side 960."""
    w, h = max(1, int(w)), max(1, int(h))
    if scale == 'fixed':
        s = 960.0 / max(w, h)
    else:
        s = SCALE.get(scale, 0.5)

    def ev(v):
        return max(16, int(round(v * s / 2.0)) * 2)
    return ev(w), ev(h)


def edge_params(feather=0.0, grow=0.0):
    """-> (blur_size_px, lo, hi): blur the mask by blur_size, then m = clamp((b - lo) / (hi - lo)).
    feather >= 0 (px, mask res), grow in px (+ grows the person, - chokes)."""
    f = max(0.0, float(feather))
    g = float(grow)
    r = f + abs(g)
    if r < 0.25:
        return 0.0, 0.0, 1.0
    c = 0.5 - g / (2.0 * r)
    hw = max(f / (2.0 * r), 0.01)
    c = min(max(c, 0.01), 0.99)
    return 2.0 * r, c - hw, c + hw


def remap(b, lo, hi):
    """The shader's edge remap (reference)."""
    d = max(hi - lo, 1e-6)
    return min(max((b - lo) / d, 0.0), 1.0)


def temporal(new, last, smooth):
    s = min(max(float(smooth), 0.0), 0.99)
    return new * (1.0 - s) + last * s


def cache_index(latency, cachesize=CACHE_SIZE):
    """Cache TOP outputindex to delay the full-res RGB by the plugin's latency (0 = this frame, -1 = previous)."""
    try:
        n = int(round(float(latency)))
    except (TypeError, ValueError):
        n = 0
    return -min(max(n, 0), cachesize - 1)


def composite(rgb, m, person='source', fill=(1.0, 1.0, 1.0), background='none', bg=(0.0, 0.0, 0.0, 0.0),
              bgcolor=(0.0, 0.0, 0.0, 1.0)):
    """Reference of the composite shader for one pixel. rgb = source colour, m = matte 0..1.
    Returns premultiplied (r, g, b, a): person over background."""
    pc = tuple(fill) if person == 'fill' else tuple(rgb[:3])
    if background == 'color':
        b = (bgcolor[0] * bgcolor[3], bgcolor[1] * bgcolor[3], bgcolor[2] * bgcolor[3], bgcolor[3])
    elif background == 'input':
        b = tuple(bg)
    else:
        b = (0.0, 0.0, 0.0, 0.0)
    return (pc[0] * m + b[0] * (1 - m), pc[1] * m + b[1] * (1 - m), pc[2] * m + b[2] * (1 - m), m + b[3] * (1 - m))


def coverage(values, thresh=0.5):
    """Fraction of matte values above thresh (verification helper)."""
    vals = list(values)
    if not vals:
        return 0.0
    return sum(1 for v in vals if v > thresh) / float(len(vals))


# ---- light wrap + despill (FX7c 7C-08, lane F, 27 Oct 2026): one compute pass `wrap` after `comp`
WRAPSRC = (('background', 'Background (in2, or Bg colour)'), ('source', 'Source surroundings (blurred source)'))
WRAP_TAPS = 16                    # ring taps: 8 at Wrapwidth, 8 at Wrapwidth / 2 (offset 22.5 deg)


def wrap_taps(width):
    """(dx, dy) px of the edge-band taps (== the shader's loop)."""
    import math
    out = []
    for k in range(WRAP_TAPS):
        r = width if k < 8 else 0.5 * width
        a = (k % 8) * math.pi / 4.0 + (0.0 if k < 8 else math.pi / 8.0)
        out.append((r * math.cos(a), r * math.sin(a)))
    return out


def wrap_ref(comp, matte_g, light, pars):
    """= the wrap pass. comp (H, W, 4) premultiplied person over background, matte_g (H, W) the matte (g), light
    (H, W, 3) the blurred wrap light (or a colour broadcast), pars {Lightwrap, Wrapwidth, Wrapgamma, Despill}.
    band = m x (1 - mean of m at the ring taps) ^ Wrapgamma (0 inside the body, ~0.5 x m on the edge);
    person rgb (premultiplied, alpha m): despill g -> min(g, max(r, b)) mixed by Despill x m, then screen with
    Lightwrap x band x light, scaled by m so rgb <= alpha holds."""
    import numpy as np
    comp = np.asarray(comp, np.float64)
    m = np.clip(np.asarray(matte_g, np.float64), 0, 1)
    H, W = m.shape
    py, px = np.mgrid[0:H, 0:W].astype(np.float64)
    acc = np.zeros((H, W))
    for dx, dy in wrap_taps(max(float(pars['Wrapwidth']), 0.0)):
        acc += _bilin(m, px + 0.5 + dx, py + 0.5 + dy)
    out = comp.copy()
    band = m * np.power(np.clip(1.0 - acc / WRAP_TAPS, 0, 1), max(float(pars['Wrapgamma']), 1e-3))
    rgb = comp[..., :3]
    g2 = np.minimum(rgb[..., 1], np.maximum(rgb[..., 0], rgb[..., 2]))
    d = float(pars['Despill'])
    rgb = rgb.copy()
    rgb[..., 1] = rgb[..., 1] + (g2 - rgb[..., 1]) * np.clip(d, 0, 1) * m
    lw = np.clip(float(pars['Lightwrap']) * band[..., None] * np.asarray(light, np.float64), 0, 1)
    rgb = rgb + (m[..., None] - rgb) * lw
    out[..., :3] = rgb
    return out


def _bilin(img, x, y):
    """texture() of a 1-channel image at pixel coords (texel centres + 0.5), extend hold."""
    import numpy as np
    H, W = img.shape
    x = np.clip(x - 0.5, 0, W - 1)
    y = np.clip(y - 0.5, 0, H - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, W - 1), np.minimum(y0 + 1, H - 1)
    fx, fy = x - x0, y - y0
    return (img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy) + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy
