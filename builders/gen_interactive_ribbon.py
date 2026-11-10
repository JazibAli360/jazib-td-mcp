# gen_interactive_ribbon - GEN_interactive module 'ribbon': gesture ribbons / multi-line brush strokes that follow
# the rack's tracked points (face landmarks, hands as effectors, the mouse, a Null) - a technique emulation of Zach
# Lieberman's sketches (FX5 E8; neutral par names, credit in docs/builds/gen_interactive.md).
# Network: pts (rack points) -> hist (history ring, self-clocked, Feedback hist_fb) -> segs (Catmull-Rom sub-segments,
# width by speed, fade, strands, wobble, colour) -> cbox (a box per chunk of 256 segments) -> fx (16x16 tile lists of segments, tapered capsules, glow, over
# the slot input) -> out_sel (Amount 0 = in1) -> out1. Shaders builders/glsl/gen_interactive_ribbon_*.glsl; numpy
# references builders/gen_interactive_ribbon_logic.py; LIVE CHECKS docs/builds/gen_interactive.md. ASCII only.

MODULE = 'ribbon'
WIDTHLAWS = ['constant', 'speed', 'calligraphy']
STYLES = ['solid', 'light', 'outline']
COLORMODES = ['ribbon', 'direction', 'age', 'speed', 'source']

PAGES = [
    ('Ribbon', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Ribbons', 'Int', 8, {'min': 1, 'max': 64, 'label': 'Ribbons (one per point)'}),
        ('Pointstart', 'Int', 0, {'min': 0, 'max': 255, 'label': 'First point'}),
        ('Length', 'Int', 96, {'min': 4, 'max': 1024, 'label': 'History samples'}),
        ('Sampleevery', 'Float', 0.0, {'min': 0, 'max': 0.5, 'label': 'Sample every s (0 = each frame)'}),
        ('Subdiv', 'Int', 3, {'min': 1, 'max': 8, 'label': 'Smooth (curve steps per sample)'}),
        ('Strands', 'Int', 1, {'min': 1, 'max': 16, 'label': 'Strands per ribbon'}),
        ('Spread', 'Float', 6.0, {'min': 0, 'max': 100, 'label': 'Strand spread px'}),
        ('Fade', 'Float', 2.5, {'min': 0, 'max': 30, 'label': 'Fade s (0 = never)'}),
        ('Fadecurve', 'Float', 1.0, {'min': 0.1, 'max': 4, 'label': 'Fade curve'}),
    ]),
    ('Width', [
        ('Width', 'Float', 18.0, {'min': 0.5, 'max': 200, 'label': 'Width px'}),
        ('Widthlaw', 'Menu', 'speed', {'names': WIDTHLAWS, 'labels': ['Constant', 'Grows with speed',
                                                                      'Calligraphy (thin when fast)']}),
        ('Speedref', 'Float', 600.0, {'min': 10, 'max': 5000, 'label': 'Reference speed px/s'}),
        ('Taper', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Taper with age'}),
        ('Widthmin', 'Float', 0.5, {'min': 0, 'max': 50, 'label': 'Width min px'}),
        ('Widthmax', 'Float', 400.0, {'min': 1, 'max': 2000, 'label': 'Width max px'}),
        ('Wobble', 'Float', 0.0, {'min': 0, 'max': 100, 'label': 'Wobble px'}),
        ('Wobblefreq', 'Float', 2.0, {'min': 0, 'max': 20, 'label': 'Wobble per s of stroke'}),
        ('Wobblespeed', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Wobble crawl'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Style', [
        ('Style', 'Menu', 'solid', {'names': STYLES, 'labels': ['Solid (clean joins)', 'Light (additive)',
                                                                 'Outline']}),
        ('Glow', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Glow'}),
        ('Glowwidth', 'Float', 12.0, {'min': 1, 'max': 100, 'label': 'Glow width px'}),
        ('Edge', 'Float', 2.0, {'min': 0, 'max': 40, 'label': 'Outline width px'}),
        ('Colormode', 'Menu', 'ribbon', {'names': COLORMODES, 'labels': ['Per ribbon', 'Direction (hue)',
                                                                         'Age', 'Speed', 'Source picture']}),
        ('Colourspread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Colour spread'}),
    ]),
    drive_page(),
    STATE_PAGE_GI,
    colour_page('rainbow', 'over', (0.95, 0.3, 0.2), (0.2, 0.6, 1.0)),
]
PANEL_PAGES = ['Ribbon', 'Width', 'Style', 'Drive', 'Colour']
RESEED = []

PRESETS = full_presets(PAGES, [
    (1, 'light brush', {'Ribbons': 4, 'Style': 1, 'Glow': 0.6, 'Glowwidth': 14.0, 'Width': 14.0, 'Widthlaw': 1,
                        'Fade': 2.0, 'Colormode': 1, 'Palette': 4, 'Blend': 2}),
    (2, 'calligraphy', {'Ribbons': 2, 'Widthlaw': 2, 'Width': 46.0, 'Taper': 1.0, 'Fade': 4.0, 'Subdiv': 4,
                        'Style': 0, 'Colormode': 2, 'Palette': 0, 'Colora': (1.0, 0.85, 0.4),
                        'Colorb': (0.6, 0.1, 0.05), 'Blend': 1}),
    (3, 'multi line', {'Ribbons': 4, 'Subdiv': 2, 'Strands': 7, 'Spread': 7.0, 'Width': 3.0, 'Widthlaw': 0, 'Taper': 0.2,
                       'Fade': 3.0, 'Style': 0, 'Colormode': 0, 'Palette': 3, 'Blend': 1}),
    (4, 'wobble neon', {'Ribbons': 8, 'Style': 2, 'Edge': 3.0, 'Width': 22.0, 'Widthlaw': 0, 'Wobble': 12.0,
                        'Wobblefreq': 3.0, 'Wobblespeed': 1.0, 'Glow': 0.8, 'Glowwidth': 10.0, 'Colormode': 0,
                        'Palette': 3, 'Blend': 1}),
    (5, 'source paint', {'Ribbons': 8, 'Colormode': 4, 'Width': 30.0, 'Widthlaw': 1, 'Fade': 6.0, 'Taper': 0.3,
                         'Length': 240, 'Style': 0, 'Blend': 1}),
    (6, 'beat burst', {'Ribbons': 8, 'Style': 1, 'Width': 10.0, 'Widthlaw': 0, 'Beatgain': 1.5, 'Beatdecay': 0.2,
                       'Glow': 0.5, 'Colormode': 1, 'Palette': 4, 'Blend': 2}),
])

R_ = P.format('Ribbons')
L_ = P.format('Length')
SUB_ = P.format('Subdiv')
S_ = P.format('Strands')
HIST_W = "max(4, int(%s))" % L_
HIST_H = "max(1, int(%s)) + 1" % R_
SEGS_W = "3 * (max(4, int(%s)) - 1) * max(1, int(%s))" % (L_, SUB_)
SEGS_H = "max(1, int(%s)) * max(1, int(%s))" % (R_, S_)
CBOX_W = "max(1, ((%s) // 3 * (%s) + 255) // 256)" % (SEGS_W, SEGS_H)


def hist_uniforms():
    return [('uTime', [TIME_EXPR, P.format('Speed'), EPOCH, P.format('Sampleevery')]),
            ('uRib', [R_, HIST_W, P.format('Pointstart'), '0']),
            ('uSz', [IN_W, IN_H, '0', '0'])]


def segs_uniforms():
    return [('uRib', [R_, HIST_W, SUB_, S_]),
            ('uW', [P.format('Width'), PI.format('Widthlaw'), P.format('Speedref'), P.format('Taper')]),
            ('uW2', [P.format('Widthmin'), P.format('Widthmax'), P.format('Spread'), P.format('Wobble')]),
            ('uF', [P.format('Fade'), P.format('Fadecurve'), P.format('Wobblefreq'), P.format('Wobblespeed')]),
            ('uC', [PI.format('Colormode'), P.format('Seed'), P.format('Colourspread'), '0'])] \
        + DRIVE_UNIFORMS + LOOK_UNIFORMS


def draw_uniforms():
    return [('uD', [PI.format('Style'), P.format('Glow'), P.format('Glowwidth'), P.format('Edge')])] + LOOK_UNIFORMS



def shader_texts():
    return {'hist': glsl_text('gen_interactive_ribbon_hist'), 'segs': glsl_text('gen_interactive_ribbon_segs'),
            'cbox': glsl_text('gen_interactive_ribbon_cbox'), 'fx': glsl_text('gen_interactive_ribbon_draw')}


def build(m, H):
    mk = H['mk']
    tx = shader_texts()
    in1 = mk(m, inTOP, 'in1')
    pts = H['pts_in'](m)
    fb = H['state'](m, 'hist_fb', 'hist', HIST_W, HIST_H)
    hist = H['pas'](m, 'hist', tx['hist'], [fb, pts], HIST_W, HIST_H, 'rgba32float', hist_uniforms())
    hist.comment = 'History ring: row i = ribbon i (x y px, t, valid), last row = meta (head, T, last time, epoch).'
    segs = H['pas'](m, 'segs', tx['segs'], [hist, in1], SEGS_W, SEGS_H, 'rgba32float', segs_uniforms())
    segs.comment = 'Segments: 3 texels each (p0 p1 / widths alphas / colour valid), Catmull-Rom x Subdiv, strands.'
    cbox = H['pas'](m, 'cbox', tx['cbox'], [segs], CBOX_W, '1', 'rgba32float', [], dispatch=(CBOX_W, '1'))
    cbox.comment = 'One box per chunk of 256 segments (min xy, max xy px): the draw skips chunks far from its tile.'
    fx = H['pas'](m, 'fx', tx['fx'], [in1, segs, cbox], IN_W, IN_H, 'useinput', draw_uniforms())
    fx.comment = 'Ribbons: 16x16 tile lists of segments (chunks of 256), tapered capsules + glow over the slot input.'
    H['out_sel'](m, fx)
    H['pulses'](m, RESEED)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pts', 'pulses']},
        {'title': '2 History', 'role': 'process', 'ops': ['hist_fb_blank', 'hist_fb', 'hist', 'hist_compute'],
         'body': 'Self-clocked ring of point samples (Speed 0 = frozen). Reset / size change = cleared.'},
        {'title': '3 Segments', 'role': 'process', 'ops': ['segs', 'segs_compute', 'cbox', 'cbox_compute']},
        {'title': '4 Draw', 'role': 'process', 'ops': ['fx', 'fx_compute']},
        {'title': '5 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
