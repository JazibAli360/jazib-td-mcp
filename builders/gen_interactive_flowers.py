# gen_interactive_flowers - GEN_interactive module 'flowers': flowers that bloom where people stand still and scatter
# their petals when people move, plus a waterfall that parts around people - a technique emulation of teamLab's
# interactive flower / waterfall rooms (FX5 E4; neutral par names, credit in docs/builds/gen_interactive.md).
# Network: mask + pts (rack) -> state (flower slots, self-clocked, Feedback state_fb) and water (drops, self-clocked,
# Feedback water_fb) -> fx (16x16 tile lists of flowers / petals / streaks, procedural SDF petals, over the slot
# input) -> out_sel (Amount 0 = in1) -> out1. Shaders builders/glsl/gen_interactive_flowers_*.glsl; numpy references
# builders/gen_interactive_flowers_logic.py; LIVE CHECKS docs/builds/gen_interactive.md. ASCII only.

MODULE = 'flowers'
MODES = ['flowers', 'waterfall', 'both']
SPECIES = ['mix', 'daisy', 'sakura', 'tulip', 'lotus', 'star', 'poppy']

PAGES = [
    ('Flowers', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'flowers', {'names': MODES, 'labels': ['Flowers', 'Waterfall', 'Flowers + waterfall']}),
        ('Count', 'Int', 400, {'min': 1, 'max': 8192, 'label': 'Flower slots'}),
        ('Spawnrate', 'Float', 0.5, {'min': 0, 'max': 20, 'label': 'Births / s per empty slot'}),
        ('Stillness', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Stillness gain (bloom where still)'}),
        ('Scatterthresh', 'Float', 0.15, {'min': 0.001, 'max': 2, 'label': 'Motion that scatters'}),
        ('Nearshare', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Share born near points'}),
        ('Spawnnear', 'Float', 120.0, {'min': 0, 'max': 1000, 'label': 'Near-point radius px'}),
        ('Species', 'Menu', 'mix', {'names': SPECIES, 'labels': ['Mix', 'Daisy', 'Blossom', 'Tulip', 'Lotus',
                                                                  'Star', 'Poppy']}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Life', [
        ('Bloomtime', 'Float', 4.0, {'min': 0.05, 'max': 120, 'label': 'Bloom s'}),
        ('Life', 'Float', 20.0, {'min': 0.1, 'max': 600, 'label': 'Life s'}),
        ('Lifevar', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Life variation'}),
        ('Wilttime', 'Float', 4.0, {'min': 0, 'max': 120, 'label': 'Wilt s (end of life)'}),
        ('Falltime', 'Float', 3.0, {'min': 0.05, 'max': 30, 'label': 'Petal fall s'}),
        ('Size', 'Float', 70.0, {'min': 2, 'max': 600, 'label': 'Flower size px'}),
        ('Sizevar', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Size variation'}),
    ]),
    ('Petals', [
        ('Petalwidth', 'Float', 1.0, {'min': 0.1, 'max': 4, 'label': 'Petal width x'}),
        ('Scatterspeed', 'Float', 220.0, {'min': 0, 'max': 3000, 'label': 'Scatter speed px/s'}),
        ('Petalgravity', 'Float', 260.0, {'min': -2000, 'max': 2000, 'label': 'Petal gravity px/s2'}),
        ('Spin', 'Float', 3.0, {'min': 0, 'max': 30, 'label': 'Petal spin rad/s'}),
        ('Wind', 'Float', 0.0, {'min': -1000, 'max': 1000, 'label': 'Wind (petals px/s, water px/s2)'}),
        ('Wilt', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Wilt grey'}),
        ('Colorvar', 'Float', 0.3, {'min': 0, 'max': 2, 'label': 'Colour variation'}),
        ('Centrecolor', 'RGB', (1.0, 0.85, 0.3), {'label': 'Centre colour'}),
        ('Centresize', 'Float', 0.18, {'min': 0, 'max': 1, 'label': 'Centre size x'}),
    ]),
    ('Water', [
        ('Drops', 'Int', 1200, {'min': 1, 'max': 16384, 'label': 'Drops'}),
        ('Fallspeed', 'Float', 700.0, {'min': 0, 'max': 5000, 'label': 'Start speed px/s'}),
        ('Gravity', 'Float', 900.0, {'min': -5000, 'max': 5000, 'label': 'Gravity px/s2'}),
        ('Part', 'Float', 3000.0, {'min': 0, 'max': 20000, 'label': 'Part around people px/s2'}),
        ('Topspread', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Start band (x height above)'}),
        ('Dropvar', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Speed variation'}),
        ('Streak', 'Float', 0.025, {'min': 0, 'max': 0.5, 'label': 'Streak s'}),
        ('Dropwidth', 'Float', 2.5, {'min': 0.5, 'max': 40, 'label': 'Streak width px'}),
        ('Watercolor', 'RGB', (0.7, 0.85, 1.0), {'label': 'Water colour'}),
        ('Wateralpha', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Water opacity'}),
        ('Splash', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Splash brightness'}),
    ]),
    drive_page(),
    STATE_PAGE_GI,
    colour_page('rainbow', 'over', (1.0, 0.45, 0.6), (1.0, 0.95, 0.8)),
]
PANEL_PAGES = ['Flowers', 'Life', 'Petals', 'Water', 'Drive', 'Colour']
RESEED = []

PRESETS = full_presets(PAGES, [
    (1, 'meadow', {}),
    (2, 'blossom wind', {'Species': 2, 'Palette': 0, 'Colora': (1.0, 0.72, 0.84), 'Colorb': (1.0, 0.95, 0.97),
                         'Scatterspeed': 160.0, 'Petalgravity': 120.0, 'Wind': 40.0, 'Life': 14.0, 'Size': 55.0}),
    (3, 'night lotus', {'Species': 4, 'Palette': 2, 'Size': 110.0, 'Count': 150, 'Bloomtime': 8.0, 'Life': 40.0,
                        'Blend': 2}),
    (4, 'waterfall', {'Mode': 1, 'Drops': 2000, 'Streak': 0.03}),
    (5, 'falls + blossoms', {'Mode': 2, 'Count': 250, 'Drops': 1200, 'Species': 2}),
    (6, 'beat bloom', {'Spawnrate': 0.2, 'Beatgain': 3.0, 'Beatdecay': 0.3, 'Bloomtime': 1.5, 'Life': 8.0,
                       'Palette': 3}),
    (7, 'touch scatter', {'Scatterthresh': 0.05, 'Stillness': 2.0, 'Nearshare': 0.5, 'Spawnnear': 80.0}),
])

CNT = "max(1, int(%s))" % P.format('Count')
DRP = "max(1, int(%s))" % P.format('Drops')
STATE_W = '128'
STATE_H = "(%s + 63) // 64 + 1" % CNT
WATER_H = "(%s + 63) // 64 + 1" % DRP


def _sz():
    return ('uSz', [IN_W, IN_H, P.format('Seed'), PI.format('Mode')])


def state_uniforms():
    return [('uTime', [TIME_EXPR, P.format('Speed'), EPOCH, CNT]), _sz(),
            ('uLife', [P.format('Bloomtime'), P.format('Life'), P.format('Lifevar'), P.format('Wilttime')]),
            ('uSp', [P.format('Spawnrate'), P.format('Stillness'), P.format('Scatterthresh'), P.format('Falltime')]),
            ('uSp2', [P.format('Nearshare'), P.format('Spawnnear'), P.format('Size'), P.format('Sizevar')]),
            ('uSp3', [PI.format('Species'), '0', '0', '0'])] + DRIVE_UNIFORMS


def water_uniforms():
    return [('uTime', [TIME_EXPR, P.format('Speed'), EPOCH, DRP]), _sz(),
            ('uW1', [P.format('Fallspeed'), P.format('Gravity'), P.format('Part'), P.format('Wind')]),
            ('uW2', [P.format('Topspread'), P.format('Dropvar'), P.format('Streak'), '0'])]


def draw_uniforms():
    return [('uD', [CNT, DRP, PI.format('Mode'), P.format('Petalwidth')]),
            ('uD2', [P.format('Scatterspeed'), P.format('Petalgravity'), P.format('Spin'), P.format('Wind')]),
            ('uD3', [P.format('Wilt'), P.format('Colorvar'), P.format('Dropwidth'), P.format('Streak')]),
            ('uD4', [P.format('Watercolorr'), P.format('Watercolorg'), P.format('Watercolorb'),
                     P.format('Wateralpha')]),
            ('uD5', [P.format('Centrecolorr'), P.format('Centrecolorg'), P.format('Centrecolorb'),
                     P.format('Centresize')]),
            ('uD6', [P.format('Bloomtime'), P.format('Falltime'), P.format('Wilttime'), P.format('Splash')])] \
        + DRIVE_UNIFORMS + LOOK_UNIFORMS


def shader_texts():
    return {'state': glsl_text('gen_interactive_flowers_state'), 'water': glsl_text('gen_interactive_flowers_water'),
            'fx': glsl_text('gen_interactive_flowers_draw')}


def build(m, H):
    mk = H['mk']
    tx = shader_texts()
    in1 = mk(m, inTOP, 'in1')
    pts = H['pts_in'](m)
    mask = H['mask_in'](m)
    sfb = H['state'](m, 'state_fb', 'state', STATE_W, STATE_H)
    st = H['pas'](m, 'state', tx['state'], [sfb, mask, pts], STATE_W, STATE_H, 'rgba32float', state_uniforms())
    st.comment = 'Flower slots: 2 texels each (x y birth life / seed size scatterT species), last row = meta.'
    wfb = H['state'](m, 'water_fb', 'water', STATE_W, WATER_H)
    wa = H['pas'](m, 'water', tx['water'], [wfb, mask], STATE_W, WATER_H, 'rgba32float', water_uniforms())
    wa.comment = 'Waterfall drops: 2 texels each (x y vx vy / splash seed alive), part around presence.'
    fx = H['pas'](m, 'fx', tx['fx'], [in1, st, wa], IN_W, IN_H, 'useinput', draw_uniforms())
    fx.comment = 'Flowers / flying petals / water streaks: 16x16 tile lists (chunks of 256), over the slot input.'
    H['out_sel'](m, fx)
    H['pulses'](m, RESEED)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pts', 'mask', 'pulses']},
        {'title': '2 Flowers', 'role': 'process', 'ops': ['state_fb_blank', 'state_fb', 'state', 'state_compute'],
         'body': 'Self-clocked flower slots: born where still + present, scatter on motion (Speed 0 = frozen).'},
        {'title': '3 Water', 'role': 'process', 'ops': ['water_fb_blank', 'water_fb', 'water', 'water_compute'],
         'body': 'Falling drops that part around people (Mode waterfall / both).'},
        {'title': '4 Draw', 'role': 'process', 'ops': ['fx', 'fx_compute']},
        {'title': '5 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
