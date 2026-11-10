# gen_sim_voronoi - GEN_sim module 'voronoi': Jump Flood Voronoi / Delaunay (Gabriel) / analytic Worley (FX5 G10).
# Network: in1 + clock -> seed (scatter Count seeds, manual dispatch, JFA size = Res x input) -> jfa (npasses =
# ceil(log2(max size)) + Extra, T-91 (3)) -> look (cells / stained glass / edges / distance / delaunay, over the
# slot input); worley (one analytic pass, no JFA) for the Worley modes; out_sel picks (Amount 0 = in1). Stateless:
# seeds move analytically from the module clock (Speed), so nothing to reset.
# Shaders builders/glsl/gen_sim_vor_*.glsl; maths + numpy reference builders/gen_sim_logic.py (seed_positions,
# scatter, jfa, voronoi_brute, gabriel_edges, worley); LIVE CHECKS docs/builds/gen_sim.md. ASCII only.

MODULE = 'voronoi'
LG = logic()
MODE_LABELS = ['Cells', 'Stained glass (input at the seed)', 'Edges', 'Distance (F1)', 'Delaunay (Gabriel)',
               'Worley F1', 'Worley F2', 'Worley edges (F2 - F1)', 'Worley cells']
WORLEY0 = LG['VOR_MODES'].index('worleyf1')

PAGES = [
    ('Voronoi', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'cells', {'names': LG['VOR_MODES'], 'labels': MODE_LABELS}),
        ('Count', 'Int', 400, {'min': 8, 'max': 4096, 'label': 'Seeds'}),
        ('Source', 'Menu', 'random', {'names': LG['VOR_SOURCES'], 'labels': ['Random', 'Grid (hex rows)',
                                                                               'Input luma']}),
        ('Wander', 'Float', 0.3, {'min': 0, 'max': 2, 'label': 'Wander (cells)'}),
        ('Speed', 'Float', 0.4, {'min': 0, 'max': 4, 'label': 'Speed'}),
        ('Jitter', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Jitter'}),
        ('Bias', 'Float', 1.5, {'min': 0, 'max': 6, 'label': 'Input bias (luma^)'}),
        ('Edgewidth', 'Float', 2.0, {'min': 0, 'max': 20, 'label': 'Edge width px'}),
        ('Glow', 'Float', 0.0, {'min': 0, 'max': 30, 'label': 'Edge glow px'}),
        ('Outline', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Outline dark (cells)'}),
        ('Cellpx', 'Float', 80.0, {'min': 4, 'max': 400, 'label': 'Worley cell px'}),
        ('Res', 'Float', 0.5, {'min': 0.125, 'max': 1, 'label': 'JFA res'}),
        ('Extra', 'Int', 1, {'min': 0, 'max': 2, 'label': 'JFA extra passes'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    colour_page('neon', 'replace', (0.08, 0.1, 0.25), (1.0, 0.9, 0.6)),
]
PANEL_PAGES = ['Voronoi', 'Colour']

PRESETS = [
    (1, 'stained glass', {'Mode': 1, 'Count': 300, 'Source': 0, 'Wander': 0.2, 'Speed': 0.3, 'Edgewidth': 3.0,
                          'Glow': 0.0, 'Outline': 1.0}),
    (2, 'cracked', {'Mode': 2, 'Count': 700, 'Source': 0, 'Wander': 0.1, 'Speed': 0.2, 'Edgewidth': 1.5, 'Glow': 4.0,
                    'Palette': 1}),
    (3, 'honeycomb', {'Mode': 0, 'Count': 220, 'Source': 1, 'Jitter': 0.12, 'Wander': 0.05, 'Edgewidth': 5.0,
                      'Outline': 1.0, 'Palette': 3}),
    (4, 'delaunay net', {'Mode': 4, 'Count': 250, 'Source': 0, 'Wander': 0.4, 'Speed': 0.3, 'Edgewidth': 1.5,
                         'Glow': 3.0, 'Palette': 5}),
    (5, 'membrane', {'Mode': 7, 'Cellpx': 90.0, 'Wander': 0.7, 'Speed': 0.8, 'Edgewidth': 2.0, 'Glow': 8.0,
                     'Palette': 2}),
    (6, 'portrait cells', {'Mode': 1, 'Count': 1500, 'Source': 2, 'Bias': 2.0, 'Wander': 0.05, 'Edgewidth': 1.0,
                           'Outline': 0.6}),
]

JW = "max(1, int(op('in1').width * parent().par.Res.eval() + 0.5))"
JH = "max(1, int(op('in1').height * parent().par.Res.eval() + 0.5))"
PM = "max(1, int(math.ceil(math.log2(max(%s, %s, 2)))))" % (JW, JH)
MODE = "parent().par.Mode.menuIndex"


def uniforms():
    return {
        'seed': [('uVs', [P.format('Count'), PI.format('Source'), P.format('Wander'), P.format('Seed')]),
                 ('uVs2', [JW, JH, P.format('Jitter'), P.format('Bias')])],
        'jfa': [('uJ', [JW, JH, PM, '0'])],
        'look': [('uVl', [MODE, P.format('Edgewidth'), P.format('Glow'), P.format('Count')]),
                 ('uVl2', [JW, JH, P.format('Seed'), P.format('Outline')])] + LOOK_UNIFORMS,
        'worley': [('uW', ["max(0, %s - %d)" % (MODE, WORLEY0), P.format('Cellpx'), P.format('Jitter'),
                           P.format('Seed')]),
                   ('uW2', [P.format('Wander'), P.format('Edgewidth'), P.format('Glow'), '0'])] + LOOK_UNIFORMS,
    }


def shader_texts():
    return {'seed': glsl_text('gen_sim_vor_seed'), 'jfa': glsl_text('gen_sim_vor_jfa'),
            'look': glsl_text('gen_sim_vor_look'), 'worley': glsl_text('gen_sim_vor_worley')}


def build(m, H):
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')
    clk = H['clock'](m)
    seed = H['pas'](m, 'seed', H['glsl']('gen_sim_vor_seed'), [in1, clk], JW, JH, 'rgba32float', U['seed'],
                    dispatch=("max(1, int(math.ceil(max(1, parent().par.Count.eval()) / 64.0)))", '1'))
    seed.comment = 'Seed scatter: one invocation per seed writes (px, id + 1) at its texel; the rest is cleared to 0.'
    jfa = H['pas'](m, 'jfa', H['glsl']('gen_sim_vor_jfa'), [seed], JW, JH, 'rgba32float', U['jfa'],
                   npasses="%s + max(0, int(parent().par.Extra.eval()))" % PM)
    jfa.comment = 'Jump flood: npasses = ceil(log2(max size)) + Extra; every texel = its nearest seed.'
    look = H['pas'](m, 'look', H['glsl']('gen_sim_vor_look'), [in1, jfa], IN_W, IN_H, 'useinput', U['look'])
    look.comment = 'Cells / stained / edges / distance / delaunay from the JFA map, over the slot input.'
    wor = H['pas'](m, 'worley', H['glsl']('gen_sim_vor_worley'), [in1, clk], IN_W, IN_H, 'useinput', U['worley'])
    wor.comment = 'Analytic Worley (F1 / F2 / edges / cells), one pass, no JFA (Worley modes).'
    sel = mk(m, switchTOP, 'out_sel')
    for i, src in enumerate((in1, look, wor)):
        sel.inputConnectors[i].connect(src)
    expr(sel.par.index, "0 if parent().par.Amount.eval() <= 0 else (2 if %s >= %d else 1)" % (MODE, WORLEY0))
    sel.comment = 'Amount 0 = the slot input untouched; JFA modes = look, Worley modes = worley (the other one idles).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'clock', 'clock_compute']},
        {'title': '2 Seeds + JFA', 'role': 'process', 'ops': ['seed', 'seed_compute', 'jfa', 'jfa_compute'],
         'body': 'Count seeds scattered at JFA res (Res), jump flood npasses = log2 + Extra.'},
        {'title': '3 Look', 'role': 'process', 'ops': ['look', 'look_compute', 'worley', 'worley_compute']},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
