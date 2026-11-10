# gen_sim_sand - GEN_sim module 'sand' (FX7a SX-27 + FX7c 7C-15 falling sand; Margolus block CA, clean-room from the
# "falling turnip" block-rule idea; BUILD_PLAN_27OCT lane A). Sand, water and walls on a grid of Cell px cells:
# sand falls and piles (topples diagonally), water falls and spreads sideways, walls never move. Inside a 2x2 block
# cells only swap, so sand / water counts are conserved exactly (sources excepted). Sources: Pour (a band at the top,
# Pourx +- Pourw, Rate per cell per step, Pourmat), hits (Hit pulse or the rising edge of Hitchop / Hitchan, e.g.
# AC_audio/out_ctl kick: a disc of Hitmat drops in at a random x), walls from the slot input (Walls: luma above
# Threshold = a moving funnel: feed a person mask), Drain (the bottom row empties). Seeds: empty, pile, input (bright
# = sand, its luma = the grain colour), layers (sand over water). Colours: sand = palette at the grain shade (the shade
# moves with the grain), water = Colour B, wall grey; Gap = pixel-grain borders.
# Network: in1 -> state_fb (rgba8) -> step (npasses = Steps; + in1) -> look (+ in1) -> out_sel -> out1; hits,
# pulses, pal (shared palette). Shaders builders/glsl/gen_sim_sand_step.glsl + gen_sim_sand_look.glsl; numpy
# reference gen_sim_logic.sand_step; LIVE CHECKS docs/builds/gen_sim.md. ASCII only.
MODULE = 'sand'

PAGES0 = [
    ('Sand', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Cell', 'Float', 2.0, {'min': 1, 'max': 16, 'label': 'Cell px'}),
        ('Steps', 'Int', 2, {'min': 0, 'max': 8, 'label': 'Steps / frame'}),
        ('Fall', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Fall probability'}),
        ('Topple', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Topple probability (pile slope)'}),
        ('Flow', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Water flow probability'}),
        ('Seedmode', 'Menu', 'pile', {'names': ['empty', 'pile', 'input', 'layers'],
                                      'labels': ['Empty', 'Sand cloud (top half)', 'Slot input (bright = sand)',
                                                 'Sand over water']}),
        ('Density', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Seed density'}),
        ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Input threshold (seed / walls)'}),
        ('Walls', 'Toggle', False, {'label': 'Walls from the slot input'}),
        ('Rate', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Pour rate (per top cell per step)'}),
        ('Pourx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Pour x'}),
        ('Pourw', 'Float', 0.05, {'min': 0, 'max': 0.5, 'label': 'Pour half width'}),
        ('Pourmat', 'Menu', 'sand', {'names': ['sand', 'water'], 'labels': ['Sand', 'Water']}),
        ('Drain', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Drain (bottom row empties)'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (re-seed)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Hits', [
        ('Hit', 'Pulse', None, {'label': 'Hit (drop a disc now)'}),
        ('Hitchop', 'CHOP', '/project1/lab/AC_audio/out_ctl', {'label': 'Hit CHOP (rising edge = a disc)'}),
        ('Hitchan', 'Str', 'kick', {'label': 'Hit channel'}),
        ('Hitsize', 'Float', 12.0, {'min': 1, 'max': 200, 'label': 'Hit disc radius (cells)'}),
        ('Hitmat', 'Menu', 'sand', {'names': ['sand', 'water'], 'labels': ['Sand', 'Water']}),
    ]),
    ('Look', [
        ('Gap', 'Float', 0.0, {'min': 0, 'max': 0.9, 'label': 'Grain gap'}),
        ('Spread', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Palette spread (grain shade)'}),
        ('Wateralpha', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Water opacity'}),
    ]),
]
PAGES = PAGES0 + [colour_page_pal('shared', 'over', (0.2, 0.12, 0.05), (0.1, 0.4, 1.0)), palette_page('fire'),
                  ('State', [('Resetcount', 'Int', 0, {'min': 0, 'max': 100, 'label': 'Reset count (Reset pulse +1)'}),
                             ('Hitn', 'Int', 0, {'min': 0, 'max': 1000000, 'label': 'Hits so far (Hit +1)'})])]
PANEL_PAGES = ['Sand', 'Hits', 'Look', 'Colour', 'Palette']
RESEED = ['Seedmode', 'Seed', 'Density']

PRESETS = full_presets(PAGES, [
    (1, 'sand cloud', {'Seedmode': 'pile', 'Palsource': 'fire'}),
    (2, 'hourglass pour', {'Seedmode': 'empty', 'Rate': 0.6, 'Pourw': 0.02, 'Drain': 0.0, 'Palsource': 'px_ramp'}),
    (3, 'beach', {'Seedmode': 'layers', 'Density': 0.5, 'Palsource': 'fire', 'Wateralpha': 0.6}),
    (4, 'person funnel', {'Seedmode': 'empty', 'Walls': True, 'Rate': 0.4, 'Pourw': 0.3, 'Drain': 0.3,
                          'Palsource': 'neon_trio', 'Palmode': 'steps'}),
    (5, 'pixel kicks', {'Seedmode': 'empty', 'Cell': 6.0, 'Gap': 0.15, 'Hitsize': 6.0, 'Drain': 0.05,
                        'Palette': 'rainbow', 'Spread': 1.0}),
])

SIMW = "max(1, int(op('in1').width / max(1.0, parent().par.Cell.eval())))"
SIMH = "max(1, int(op('in1').height / max(1.0, parent().par.Cell.eval())))"
SAND_EPOCH = "float(int(parent().par.Resetcount.eval()) % 255 + 1)"     # rgba8 state alpha: 1..255


def step_uniforms():
    return [('uSim', [SIMW, SIMH, PI.format('Seedmode'), SAND_EPOCH]),
            ('uRule', [P.format('Fall'), P.format('Topple'), P.format('Flow'), P.format('Drain')]),
            ('uSrc', [P.format('Rate'), P.format('Pourx'), P.format('Pourw'), '%s + 1' % PI.format('Pourmat')]),
            ('uHit', [P.format('Hitn'), P.format('Hitsize'), '%s + 1' % PI.format('Hitmat'), P.format('Seed')]),
            ('uIn', ["1 if parent().par.Walls.eval() else 0", P.format('Threshold'), P.format('Density'),
                     P.format('Steps')]),
            ('uRun', ['absTime.frame', '0', '0', '0'])]


def look_uniforms():
    return [('uSl', [P.format('Cell'), P.format('Gap'), P.format('Spread'), P.format('Wateralpha')]),
            ('uPalCtl', list(PAL_CTL))] + LOOK_UNIFORMS


def shader_texts():
    return {'step': glsl_text('gen_sim_sand_step'), 'look': pal_glsl(glsl_text('gen_sim_sand_look'))}


def build(m, H):
    mk = H['mk']
    in1 = mk(m, inTOP, 'in1')
    T = shader_texts()
    fb = H['state'](m, 'state_fb', 'step', SIMW, SIMH, fmt='rgba8fixed')
    step = H['pas'](m, 'step', T['step'], [fb, in1], SIMW, SIMH, 'rgba8fixed', step_uniforms(),
                    npasses="max(1, parent().par.Steps.eval())")
    step.comment = 'Sand: r material/3, g grain shade, b hits applied, a epoch; Margolus blocks, npasses = Steps.'
    look = H['pas'](m, 'look', T['look'], [in1, step], IN_W, IN_H, 'useinput', look_uniforms(), filt='nearest')
    look.comment = 'Cells -> sand palette / water / walls, over the slot input.'
    pal = H['palette'](m, look)
    H['out_sel'](m, look)
    H['pulses'](m, RESEED)
    hits = H['hits'](m)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulses'] + hits},
        {'title': '2 Sand', 'role': 'process', 'ops': ['state_fb_blank', 'state_fb', 'step', 'step_compute'],
         'body': 'state_fb <- step: walls / pour / hits / drain, then fall, topple, flow in 2x2 blocks.'},
        {'title': '3 Look', 'role': 'process', 'ops': ['look', 'look_compute'] + pal},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
