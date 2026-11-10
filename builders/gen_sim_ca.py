# gen_sim_ca - GEN_sim module 'ca': cellular automata lab (FX5 G08 + G26). Families: Life-like / Generations (any
# Golly B/S/C rule: Life, HighLife, Seeds, Day & Night, Coral, Maze, Brian's Brain, Star Wars, custom), Wireworld,
# Cyclic CA, Larger than Life (radius <= 16 box), Lenia (continuous, ring kernel, radius <= 16).
# Network: in1 -> step (compute, npasses = steps this frame, state in place of the Feedback state_fb) -> look
# (palette / glow / age, cells square / round / smooth, over the slot input) -> out_sel (Amount 0 = in1) -> out1.
# Shaders builders/glsl/gen_sim_ca_step.glsl + gen_sim_ca_look.glsl; maths + numpy reference
# builders/gen_sim_logic.py (ca_init / ca_step / ca_value); LIVE CHECKS docs/builds/gen_sim.md. ASCII only.
# Module file contract: docs/builds/fx_glitch.md "Module template" (exec'd in builders/gen_sim.py's namespace).

MODULE = 'ca'
LG = logic()
FAMILY_LABELS = ['Life-like / Generations', 'Wireworld', 'Cyclic', 'Larger than Life', 'Lenia']
RULESETS = LG['RULESETS']

PAGES = [
    ('Ca', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Family', 'Menu', 'life', {'names': LG['FAMILIES'], 'labels': FAMILY_LABELS}),
        ('Ruleset', 'Menu', 'life', {'names': [r[0] for r in RULESETS], 'labels': [r[1] for r in RULESETS]}),
        ('Rule', 'Str', 'B3/S23', {'label': 'Custom rule (B/S/C)'}),
        ('Cell', 'Float', 4.0, {'min': 1, 'max': 16, 'label': 'Cell px'}),
        ('Steps', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Steps / frame'}),
        ('Run', 'Toggle', True, {'label': 'Run'}),
        ('Wrap', 'Toggle', True, {'label': 'Wrap edges'}),
        ('Seedmode', 'Menu', 'noise', {'names': LG['CA_SEEDS'], 'labels': ['Noise', 'Blob', 'Input (threshold)',
                                                                            'Wire lattice', 'Empty']}),
        ('Density', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Density'}),
        ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Input threshold'}),
        ('Inject', 'Toggle', False, {'label': 'Inject input every step'}),
        ('Mutate', 'Float', 0.0, {'min': 0, 'max': 0.01, 'label': 'Mutate / cell / step'}),
        ('Decay', 'Float', 0.85, {'min': 0, 'max': 1, 'label': 'Glow decay / step'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (re-seed)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Rules', [
        ('States', 'Int', 12, {'min': 2, 'max': 24, 'label': 'Cyclic states'}),
        ('Cycthresh', 'Int', 3, {'min': 1, 'max': 12, 'label': 'Cyclic threshold'}),
        ('Cycrange', 'Int', 1, {'min': 1, 'max': 5, 'label': 'Cyclic range'}),
        ('Ltlr', 'Int', 5, {'min': 1, 'max': 16, 'label': 'LtL radius'}),
        ('Ltlb1', 'Int', 34, {'min': 0, 'max': 300, 'label': 'LtL birth min'}),
        ('Ltlb2', 'Int', 45, {'min': 0, 'max': 300, 'label': 'LtL birth max'}),
        ('Ltls1', 'Int', 34, {'min': 0, 'max': 300, 'label': 'LtL survive min'}),
        ('Ltls2', 'Int', 58, {'min': 0, 'max': 300, 'label': 'LtL survive max'}),
        ('Leniar', 'Int', 10, {'min': 1, 'max': 16, 'label': 'Lenia radius'}),
        ('Leniamu', 'Float', 0.15, {'min': 0, 'max': 0.5, 'label': 'Lenia mu'}),
        ('Leniasigma', 'Float', 0.015, {'min': 0.001, 'max': 0.1, 'label': 'Lenia sigma'}),
        ('Leniadt', 'Float', 0.1, {'min': 0.01, 'max': 0.5, 'label': 'Lenia dt'}),
        ('Wirespacing', 'Int', 12, {'min': 2, 'max': 64, 'label': 'Wire spacing'}),
        ('Sparks', 'Float', 0.02, {'min': 0, 'max': 0.2, 'label': 'Wire sparks'}),
    ]),
    ('Look', [
        ('Colormode', 'Menu', 'glow', {'names': ['state', 'glow', 'age'], 'labels': ['State', 'Glow trail', 'Age']}),
        ('Shape', 'Menu', 'square', {'names': ['square', 'round', 'smooth'], 'labels': ['Square', 'Round', 'Smooth']}),
        ('Gap', 'Float', 0.1, {'min': 0, 'max': 0.9, 'label': 'Cell gap'}),
        ('Agescale', 'Float', 30.0, {'min': 1, 'max': 300, 'label': 'Age scale (steps)'}),
    ]),
    colour_page('ab', 'replace', (0.05, 0.1, 0.35), (1.0, 0.85, 0.4)),
    STATE_PAGE,
]
PANEL_PAGES = ['Ca', 'Rules', 'Look', 'Colour']
RESEED = ['Family', 'Ruleset', 'Rule', 'Seedmode', 'Seed', 'Density', 'Wirespacing', 'Sparks']

# zkit preset slots: (slot, name, values); menus as their index
PRESETS = [
    (1, 'life glow', {'Family': 0, 'Ruleset': 0, 'Cell': 4.0, 'Steps': 1.0, 'Seedmode': 0, 'Density': 0.3,
                      'Mutate': 0.0002, 'Colormode': 1, 'Shape': 0, 'Gap': 0.1, 'Decay': 0.85, 'Palette': 0}),
    (2, 'brians brain', {'Family': 0, 'Ruleset': 6, 'Cell': 3.0, 'Steps': 1.0, 'Seedmode': 1, 'Density': 0.4,
                         'Colormode': 0, 'Shape': 1, 'Gap': 0.15, 'Palette': 3}),
    (3, 'coral', {'Family': 0, 'Ruleset': 4, 'Cell': 2.0, 'Steps': 2.0, 'Seedmode': 1, 'Density': 0.5,
                  'Colormode': 2, 'Shape': 2, 'Agescale': 60.0, 'Palette': 2}),
    (4, 'cyclic spirals', {'Family': 2, 'States': 14, 'Cycthresh': 3, 'Cycrange': 2, 'Cell': 3.0, 'Steps': 1.0,
                           'Seedmode': 0, 'Colormode': 0, 'Shape': 2, 'Palette': 4}),
    (5, 'wireworld', {'Family': 1, 'Cell': 4.0, 'Steps': 1.0, 'Seedmode': 3, 'Wirespacing': 10, 'Sparks': 0.03,
                      'Density': 0.4, 'Colormode': 0, 'Shape': 0, 'Gap': 0.2, 'Palette': 1}),
    (6, 'bosco ltl', {'Family': 3, 'Ltlr': 5, 'Ltlb1': 34, 'Ltlb2': 45, 'Ltls1': 34, 'Ltls2': 58, 'Cell': 3.0,
                      'Steps': 1.0, 'Seedmode': 0, 'Density': 0.5, 'Colormode': 1, 'Shape': 2, 'Palette': 3}),
    (7, 'lenia worms', {'Family': 4, 'Leniar': 10, 'Leniamu': 0.15, 'Leniasigma': 0.015, 'Leniadt': 0.1,
                        'Cell': 4.0, 'Steps': 1.0, 'Seedmode': 0, 'Density': 0.5, 'Colormode': 0, 'Shape': 2,
                        'Palette': 2}),
]

RULE_SRC = ("(%r[parent().par.Ruleset.menuIndex] if parent().par.Ruleset.menuIndex < %d else parent().par.Rule.eval())"
            % ([r[2] for r in RULESETS[:-1]], len(RULESETS) - 1))
FAM = "parent().par.Family.menuIndex"
SIMW = "max(1, int(op('in1').width / max(1.0, parent().par.Cell.eval())))"
SIMH = "max(1, int(op('in1').height / max(1.0, parent().par.Cell.eval())))"
NSTEPS = ("(lambda s, f: int(f * s) - int((f - 1) * s))(max(0.0, parent().par.Steps.eval()) if "
          "parent().par.Run.eval() else 0.0, absTime.frame)")
RADIUS = ("[1, 1, parent().par.Cycrange.eval(), parent().par.Ltlr.eval(), parent().par.Leniar.eval()][%s]" % FAM)
C_OR_N = ("(%s) if %s == 0 else (parent().par.States.eval() if %s == 2 else 2)"
          % (LG['rule_expr']('c', RULE_SRC), FAM, FAM))


def step_uniforms():
    return [
        ('uSim', [SIMW, SIMH, FAM, EPOCH]),
        ('uRule', [LG['rule_expr']('b', RULE_SRC), LG['rule_expr']('s', RULE_SRC), LG['rule_expr']('c', RULE_SRC),
                   RADIUS]),
        ('uLtl', [P.format('Ltlb1'), P.format('Ltlb2'), P.format('Ltls1'), P.format('Ltls2')]),
        ('uCyc', [P.format('States'), P.format('Cycthresh'), '0', '0']),
        ('uLen', [P.format('Leniamu'), P.format('Leniasigma'), P.format('Leniadt'), LG['lenia_norm_expr']()]),
        ('uSeed', [PI.format('Seedmode'), P.format('Density'), P.format('Threshold'), P.format('Seed')]),
        ('uRun', [NSTEPS, 'absTime.frame', P.format('Mutate'), "1 if parent().par.Inject.eval() else 0"]),
        ('uMisc', ["1 if parent().par.Wrap.eval() else 0", P.format('Decay'), P.format('Wirespacing'),
                   P.format('Sparks')]),
    ]


def look_uniforms():
    return [('uSim', [SIMW, SIMH, FAM, C_OR_N]),
            ('uCv', [PI.format('Colormode'), PI.format('Shape'), P.format('Gap'), P.format('Agescale')])] \
        + LOOK_UNIFORMS



def shader_texts():
    return {'step': glsl_text('gen_sim_ca_step'), 'look': glsl_text('gen_sim_ca_look')}


def build(m, H):
    mk = H['mk']
    in1 = mk(m, inTOP, 'in1')
    fb = H['state'](m, 'state_fb', 'step', SIMW, SIMH)
    step = H['pas'](m, 'step', H['glsl']('gen_sim_ca_step'), [fb, in1], SIMW, SIMH, 'rgba32float',
                    step_uniforms(), npasses="max(1, %s)" % NSTEPS)
    step.comment = 'CA state: npasses = steps this frame (Steps x Run); r state, g glow, b age, a epoch.'
    look = H['pas'](m, 'look', H['glsl']('gen_sim_ca_look'), [in1, step], IN_W, IN_H, 'useinput',
                    look_uniforms())
    look.comment = 'Cells -> palette (state / glow / age), square / round / smooth, over the slot input.'
    H['out_sel'](m, look)
    H['pulses'](m, RESEED)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulses']},
        {'title': '2 State', 'role': 'process', 'ops': ['state_fb_blank', 'state_fb', 'step', 'step_compute'],
         'body': 'state_fb <- step: npasses = steps this frame. Reset / seed changes -> Resetcount = new epoch.'},
        {'title': '3 Look', 'role': 'process', 'ops': ['look', 'look_compute']},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
