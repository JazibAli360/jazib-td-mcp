# gen_pattern_opart - GEN_pattern module 'opart' (FX5 G17): up to 3 analytic-antialiased grating layers (lines,
# circles, dots, checker, rays) combined by xor / multiply / difference / add / max -> moire; warps: Riley sine waves,
# Vasarely bulge, twist. No flash / frequency limiter (user rule: no built-in limits). Audio -> warp amount, beat
# pulse -> phase kick, Beatinvert flips polarity every step. Mirror: gen_pattern_logic.gen_opart. ASCII only.
MODULE = 'opart'
KIND = 'gen'
BLURB = 'Op-art gratings: 1-3 layers combined -> moire; Riley / bulge / twist warp; beat inverts.'
TYPES = ['lines', 'circles', 'dots', 'checker', 'rays']
TYPE_LABELS = ['Lines', 'Circles', 'Dots', 'Checker', 'Rays']
COMBINES = ['xor', 'multiply', 'difference', 'add', 'max']
WARPS = ['none', 'riley', 'bulge', 'twist']


def _layer(i, typ, freq, ang, speed):
    return [('Type%d' % i, 'Menu', typ, {'names': TYPES, 'labels': TYPE_LABELS}),
            ('Freq%d' % i, 'Float', freq, {'min': 1, 'max': 400, 'label': 'Freq %d (per screen height)' % i}),
            ('Angle%d' % i, 'Float', ang, {'min': -180, 'max': 180, 'label': 'Angle %d deg' % i}),
            ('Speed%d' % i, 'Float', speed, {'min': -4, 'max': 4, 'label': 'Phase speed %d /s' % i}),
            ('Duty%d' % i, 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Duty %d' % i})]


PAGES = [('Opart', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Layers', 'Int', 2, {'min': 1, 'max': 3, 'label': 'Layers'}),
    ('Combine', 'Menu', 'xor', {'names': COMBINES, 'labels': ['XOR', 'Multiply', 'Difference', 'Add', 'Max']}),
    ('Warp', 'Menu', 'none', {'names': WARPS, 'labels': ['None', 'Riley waves', 'Bulge (Vasarely)', 'Twist']}),
    ('Warpamt', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Warp amount'}),
    ('Warpfreq', 'Float', 3.0, {'min': 0, 'max': 20, 'label': 'Riley wave freq'}),
    ('Beatinvert', 'Toggle', False, {'label': 'Invert every step'}),
]), ('Layers', _layer(1, 'lines', 60.0, 0.0, 0.2) + _layer(2, 'lines', 62.0, 3.0, -0.1)
     + _layer(3, 'circles', 40.0, 0.0, 0.0))]
DEFAULTS = {'Scale': 1.0, 'Palette': 0, 'Colorar': 0.94, 'Colorag': 0.93, 'Colorab': 0.9,
            'Colorbr': 0.94, 'Colorbg': 0.93, 'Colorbb': 0.9, 'Bgcolorr': 0.08, 'Bgcolorg': 0.08, 'Bgcolorb': 0.09}
PANEL_PAGES = ['Opart', 'Layers', 'Drive', 'Space', 'Colour']
PRESETS = [
    (1, 'riley waves', {'Amount': 1.0, 'Layers': 1, 'Type1': 0, 'Freq1': 40.0, 'Angle1': 90.0, 'Speed1': 0.0,
                        'Duty1': 0.5, 'Warp': 1, 'Warpamt': 1.0, 'Warpfreq': 2.5, 'Scale': 1.0}),
    (2, 'vasarely', {'Amount': 1.0, 'Layers': 1, 'Type1': 3, 'Freq1': 16.0, 'Angle1': 0.0, 'Warp': 2,
                     'Warpamt': 0.6, 'Scale': 1.0}),
    (3, 'circle moire', {'Amount': 1.0, 'Layers': 2, 'Type1': 1, 'Freq1': 60.0, 'Speed1': 0.3, 'Type2': 1,
                         'Freq2': 63.0, 'Speed2': -0.2, 'Combine': 0, 'Warp': 0}),
    (4, 'line pair', {'Amount': 1.0, 'Layers': 2, 'Type1': 0, 'Freq1': 80.0, 'Angle1': 0.0, 'Speed1': 0.1,
                      'Type2': 0, 'Freq2': 80.0, 'Angle2': 4.0, 'Speed2': 0.0, 'Combine': 1, 'Warp': 0}),
    (5, 'dots beat', {'Amount': 1.0, 'Layers': 2, 'Type1': 2, 'Freq1': 30.0, 'Duty1': 0.6, 'Type2': 2,
                      'Freq2': 31.0, 'Angle2': 5.0, 'Duty2': 0.6, 'Combine': 0, 'Beatinvert': True,
                      'Beatevery': 1.0, 'Beatgain': 0.5}),
]
UNIFORMS = [('uM0', ['{Layers}', '{Combine#}', '{Warp#}', '{Warpamt}']),
            ('uM1', ['{Warpfreq}', 'float({Beatinvert})', '0', '0'])]
UNIFORMS += [('uM%d' % (1 + i), ['{Type%d#}' % i, '{Freq%d}' % i, 'math.radians({Angle%d})' % i, '{Speed%d}' % i])
             for i in (1, 2, 3)]
UNIFORMS += [('uM5', ['{Duty1}', '{Duty2}', '{Duty3}', '0'])]

GLSL = """
float olayer(int typ, float freq, float ang, float ph, float duty, vec2 q) {
    float aa = freq * PX;
    if (typ == 0) return band(dot(q, vec2(cos(ang), sin(ang))) * freq + ph, duty, aa);
    if (typ == 1) return band(length(q) * freq + ph, duty, aa);
    vec2 r = rot2(q, -ang);
    if (typ == 2) {
        vec2 g = vec2(fract(r.x * freq + ph), fract(r.y * freq)) - 0.5;
        return clamp(0.5 + (duty * 0.5 - length(g)) / max(aa, 1e-9), 0.0, 1.0);
    }
    if (typ == 3) { float a = band(r.x * freq + ph, 0.5, aa), b = band(r.y * freq, 0.5, aa); return a + b - 2.0 * a * b; }
    float n = max(floor(freq + 0.5), 1.0);
    float rr = max(length(q), 1e-4);
    float u = (atan(q.y, q.x) / TAU + ang / TAU) * n + ph;
    return band(u, duty, n / (TAU * rr) * PX);
}
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int layers = int(uM0.x + 0.5), comb = int(uM0.y + 0.5), warp = int(uM0.z + 0.5);
    float A = uM0.w * (1.0 + LEVEL);
    if (warp == 1) q.x += A * 0.05 * sin(TAU * (uM1.x * q.y + 0.25 * T));
    else if (warp == 2) q *= 1.0 - A * exp(-dot(q, q) / 0.09);
    else if (warp == 3) q = rot2(q, A * PI * exp(-dot(q, q) / 0.09));
    vec4 L[3] = vec4[3](uM2, uM3, uM4);
    int nl = clamp(layers, 1, 3);
    v = 0.0;
    for (int i = 0; i < 3; i++) {
        if (i >= nl) break;
        float li = olayer(int(L[i].x + 0.5), L[i].y, L[i].z, L[i].w * T + ENV, uM5[i], q);
        if (i == 0) v = li;
        else if (comb == 0) v = v + li - 2.0 * v * li;
        else if (comb == 1) v = v * li;
        else if (comb == 2) v = abs(v - li);
        else if (comb == 3) v = v + li;
        else v = max(v, li);
    }
    if (uM1.y > 0.5 && (int(STEP) & 1) == 1) v = 1.0 - v;
    k = v;
}
"""
