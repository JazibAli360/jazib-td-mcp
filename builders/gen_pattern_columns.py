# gen_pattern_columns - GEN_pattern module 'columns' (FX5 E5 / G35, light-column / LED-array look): Count columns
# whose heights follow Height + a travelling sine (Wave, Wavespeed, Phasestep per column) + per-step Jitter + audio
# (per-column weight) + beat pulse; drawn as vertical light beams (exp halo, soft top, haze noise), an LED VU meter
# (round LEDs, Unlit level) or a dot field. Mirror: gen_pattern_logic.gen_columns. ASCII only.
MODULE = 'columns'
KIND = 'gen'
BLURB = 'Light columns / LED meter / dot field; heights = wave + jitter per step + audio + beat.'

PAGES = [('Columns', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Mode', 'Menu', 'beams', {'names': ['beams', 'meter', 'dots'], 'labels': ['Light beams', 'LED meter',
                                                                               'Dot field']}),
    ('Count', 'Int', 24, {'min': 1, 'max': 128, 'label': 'Columns'}),
    ('Height', 'Float', 0.6, {'min': 0, 'max': 1.5, 'label': 'Base height'}),
    ('Wave', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Wave'}),
    ('Wavespeed', 'Float', 0.3, {'min': -4, 'max': 4, 'label': 'Wave speed /s'}),
    ('Phasestep', 'Float', 0.07, {'min': -1, 'max': 1, 'label': 'Phase per column'}),
    ('Jitter', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Jitter per step'}),
    ('Width', 'Float', 6.0, {'min': 0, 'max': 100, 'label': 'Beam core px'}),
    ('Falloff', 'Float', 18.0, {'min': 0.1, 'max': 200, 'label': 'Beam halo px'}),
    ('Softtop', 'Float', 80.0, {'min': 1, 'max': 600, 'label': 'Soft top px'}),
    ('Haze', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Haze'}),
    ('Rows', 'Int', 48, {'min': 1, 'max': 256, 'label': 'LED rows'}),
    ('Ledsize', 'Float', 0.75, {'min': 0, 'max': 1.5, 'label': 'LED size'}),
    ('Unlit', 'Float', 0.06, {'min': 0, 'max': 1, 'label': 'Unlit LED level'}),
])]
DEFAULTS = {'Palette': 0, 'Colorar': 1.0, 'Colorag': 0.95, 'Colorab': 0.85, 'Colorbr': 0.3, 'Colorbg': 0.6,
            'Colorbb': 1.0}
PANEL_PAGES = ['Columns', 'Drive', 'Colour']
PRESETS = [
    (1, 'light columns', {'Amount': 1.0, 'Mode': 0, 'Count': 24, 'Height': 0.6, 'Wave': 0.25, 'Wavespeed': 0.3,
                          'Haze': 0.3}),
    (2, 'vu meter', {'Amount': 1.0, 'Mode': 1, 'Count': 16, 'Rows': 40, 'Height': 0.3, 'Wave': 0.2, 'Jitter': 0.3,
                     'Audiogain': 1.0, 'Palette': 0, 'Colorar': 0.1, 'Colorag': 1.0, 'Colorab': 0.3,
                     'Colorbr': 1.0, 'Colorbg': 0.1, 'Colorbb': 0.1}),
    (3, 'dot field', {'Amount': 1.0, 'Mode': 2, 'Count': 27, 'Rows': 48, 'Wavespeed': 0.5, 'Phasestep': 0.05,
                      'Palette': 2}),
    (4, 'beat beams', {'Amount': 1.0, 'Mode': 0, 'Count': 12, 'Jitter': 0.6, 'Wave': 0.1, 'Beatevery': 1.0,
                       'Beatgain': 1.0, 'Width': 10.0, 'Falloff': 30.0}),
    (5, 'haze wall', {'Amount': 1.0, 'Mode': 0, 'Count': 48, 'Width': 2.0, 'Falloff': 8.0, 'Haze': 0.8,
                      'Height': 0.9, 'Wave': 0.08, 'Palette': 4}),
]
UNIFORMS = [('uM0', ['{Mode#}', '{Height}', '{Wave}', '{Phasestep}']),
            ('uM1', ['{Wavespeed}', '{Jitter}', '0', '0']),
            ('uM2', ['{Width}', '{Falloff}', '{Softtop}', '{Haze}']),
            ('uM3', ['{Count}', '{Rows}', '{Ledsize}', '{Unlit}'])]

GLSL = """
float colh(int i) {
    return uM0.y + uM0.z * sin(TAU * (float(i) * uM0.w + T * uM1.x))
         + uM1.y * (h2(ivec2(i, int(STEP)), SEED ^ 0xC0u) - 0.5)
         + LEVEL * (0.5 + 0.5 * h2(ivec2(i, 9), SEED)) + ENV * 0.3;
}
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int mode = int(uM0.x + 0.5), cnt = max(int(uM3.x + 0.5), 1), rows = max(int(uM3.y + 0.5), 1);
    float cw = RES.x / float(cnt);
    int i = int(floor(P.x / cw));
    if (mode == 0) {
        float s = 0.0;
        for (int j = i - 2; j <= i + 2; j++) {
            float dx = abs(P.x - (float(j) + 0.5) * cw);
            float core = exp(-max(dx - uM2.x * 0.5, 0.0) / max(uM2.y, 1e-3));
            s += core * clamp((colh(j) * RES.y - P.y) / max(uM2.z, 1.0) + 0.5, 0.0, 1.0);
        }
        if (uM2.w > 0.0) s *= 1.0 - uM2.w + uM2.w * vnoise(vec2(P.x / 80.0, P.y / 120.0 - T * 0.5), SEED);
        v = s; k = (float(i) + 0.5) / float(cnt);
        return;
    }
    float rh = RES.y / float(rows);
    int r = int(floor(P.y / rh));
    vec2 l = P - vec2((float(i) + 0.5) * cw, (float(r) + 0.5) * rh);
    float vd = clamp(0.5 + (uM3.z * 0.5 * min(cw, rh) - length(l)), 0.0, 1.0);
    if (mode == 1) {
        v = vd * ((float(r) + 0.5) / float(rows) < colh(i) ? 1.0 : uM3.w);
        k = (float(r) + 0.5) / float(rows);
        return;
    }
    v = vd * (0.5 + 0.5 * sin(TAU * (float(i) * uM0.w + float(r) * uM0.w * 0.5 + T * uM1.x)));
    k = (float(i) + 0.5) / float(cnt);
}
"""
