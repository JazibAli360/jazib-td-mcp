# gen_pattern_barcode - GEN_pattern module 'barcode' (FX5 G20 / E2, data-barcode look): Channels stacked bands of
# run-length bars (Barmin px units, runs up to Maxrun per 16-unit segment), a square bit grid, or a scan of the slot's
# input (a bit = input luma > Threshold at the bar's cell). Bands scroll opposite ways at Scroll px/s (+ per-band
# Speedvar); bits re-roll Rate times/s and on every step; Beatinvert flips polarity per step. No flicker cap (user
# rule: no built-in limits). Audio -> scroll speed, beat pulse -> density. Mirror: gen_pattern_logic.gen_barcode.
MODULE = 'barcode'
KIND = 'gen'
BLURB = 'Data barcode: run-length bars / bit grid / input scan; bands scroll; re-roll per Rate and step.'

PAGES = [('Barcode', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Mode', 'Menu', 'bars', {'names': ['bars', 'grid', 'scan'], 'labels': ['Bars (run length)', 'Bit grid',
                                                                           'Scan input (luma)']}),
    ('Channels', 'Int', 8, {'min': 1, 'max': 64, 'label': 'Bands'}),
    ('Barmin', 'Float', 3.0, {'min': 1, 'max': 32, 'label': 'Bar unit px'}),
    ('Maxrun', 'Float', 8.0, {'min': 1, 'max': 32, 'label': 'Max run (units)'}),
    ('Density', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Density'}),
    ('Rate', 'Float', 12.0, {'min': 0, 'max': 60, 'label': 'Re-roll Hz'}),
    ('Scroll', 'Float', 300.0, {'min': -3000, 'max': 3000, 'label': 'Scroll px/s'}),
    ('Speedvar', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Speed per band'}),
    ('Bandgap', 'Float', 4.0, {'min': 0, 'max': 40, 'label': 'Band gap px'}),
    ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Scan threshold'}),
    ('Beatinvert', 'Toggle', False, {'label': 'Invert every step'}),
    ('Vertical', 'Toggle', False, {'label': 'Vertical bars'}),
    ('Cell', 'Float', 24.0, {'min': 2, 'max': 200, 'label': 'Grid cell px'}),
    ('Colorvar', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Colour per band'}),
])]
DEFAULTS = {'Palette': 1}
PANEL_PAGES = ['Barcode', 'Drive', 'Colour']
PRESETS = [
    (1, 'barcode wall', {'Amount': 1.0, 'Mode': 0, 'Channels': 8, 'Barmin': 3.0, 'Maxrun': 8.0, 'Rate': 12.0,
                         'Scroll': 300.0, 'Vertical': False}),
    (2, 'bit grid', {'Amount': 1.0, 'Mode': 1, 'Cell': 24.0, 'Rate': 8.0, 'Scroll': 120.0, 'Density': 0.45}),
    (3, 'scan', {'Amount': 1.0, 'Mode': 2, 'Channels': 48, 'Barmin': 4.0, 'Rate': 0.0, 'Scroll': 0.0,
                 'Bandgap': 2.0, 'Threshold': 0.45}),
    (4, 'binary rain', {'Amount': 1.0, 'Mode': 0, 'Vertical': True, 'Channels': 24, 'Barmin': 4.0, 'Scroll': 900.0,
                        'Rate': 4.0, 'Density': 0.35, 'Palette': 6, 'Colorvar': 0.3}),
    (5, 'beat flip', {'Amount': 1.0, 'Mode': 0, 'Channels': 4, 'Beatinvert': True, 'Beatevery': 1.0, 'Rate': 0.0,
                      'Scroll': 200.0, 'Beatgain': 0.5}),
]
UNIFORMS = [('uM0', ['{Mode#}', '{Channels}', '{Barmin}', '{Maxrun}']),
            ('uM1', ['{Density}', '{Rate}', '{Scroll}', '{Speedvar}']),
            ('uM2', ['{Bandgap}', '{Threshold}', 'float({Beatinvert})', 'float({Vertical})']),
            ('uM3', ['{Cell}', '{Colorvar}', '0', '0'])]

GLSL = """
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int mode = int(uM0.x + 0.5), chans = max(int(uM0.y + 0.5), 1);
    float bmin = max(uM0.z, 1.0), maxrun = max(uM0.w, 1.0);
    float dens = uM1.x + ENV * 0.3, scroll = uM1.z * (1.0 + LEVEL);
    bool vert = uM2.w > 0.5;
    float cellpx = max(uM3.x, 1.0);
    float A = vert ? P.y : P.x, B = vert ? P.x : P.y;
    float WA = vert ? RES.y : RES.x, WB = vert ? RES.x : RES.y;
    uint roll = uint(int(floor(T * uM1.y))) + uint(int(STEP)) * 0x45D9F3Bu;
    float bh = mode == 1 ? cellpx : WB / float(chans);
    int bi = int(floor(B / bh));
    float bpos = B - float(bi) * bh;
    float inband = clamp(0.5 + (min(bpos, bh - bpos) - uM2.x * 0.5), 0.0, 1.0);
    float dirn = (bi & 1) == 1 ? -1.0 : 1.0;
    float sp = scroll * (1.0 + uM1.w * (2.0 * h2(ivec2(bi, 0), SEED ^ 0xB1u) - 1.0));
    float a = A + sp * T * dirn;
    bool bit;
    if (mode == 1) {
        bit = h3(ivec3(int(floor(a / cellpx)), bi, 0), SEED ^ lb32(roll)) < dens;
    } else if (mode == 2) {
        int xs = int(mod(floor(a / bmin) * bmin + bmin * 0.5, WA));
        int yc = int(clamp(floor((float(bi) + 0.5) * bh), 0.0, WB - 1.0));
        vec4 sc = texelFetch(sTD2DInputs[0], vert ? ivec2(yc, xs) : ivec2(xs, yc), 0);
        bit = dot(sc.rgb, vec3(0.2126, 0.7152, 0.0722)) > uM2.y;
    } else {
        int u = int(floor(a / bmin));
        int seg = int(floor(float(u) / 16.0));
        int run = 1 + int(h3(ivec3(seg, bi, 7), SEED ^ lb32(roll)) * maxrun);
        int cid = int(floor(float(u) / float(run)));
        bit = h3(ivec3(cid, bi, seg), SEED ^ lb32(roll + 1u)) < dens;
    }
    if (uM2.z > 0.5 && (int(STEP) & 1) == 1) bit = !bit;
    v = (bit ? 1.0 : 0.0) * inband;
    k = uM3.y * h2(ivec2(bi, 3), SEED);
}
"""
