# gen_sim_dla - GEN_sim module 'dla': Laplacian growth by the dielectric breakdown model (FX5 G09): DLA frost,
# lightning, coral, ring, input crystallise. GPU form (no random walkers): the Laplace field phi around the cluster is
# relaxed by Jacobi (8 iterations per pass, temporal blocking in shared memory), then every empty cell touching the
# cluster attaches with p = Growth x (phi / (phimax x Phiref))^Eta (phimax = largest frontier phi, last frame).
# Network: in1 -> touch (1 workgroup: strike detect + phimax + regrow) -> field (npasses = ceil(Iters / 8), state
# field_fb) -> grow (npasses = Steps, state cluster_fb) -> look (age / solid / field bands + mip glow, over the slot
# input) -> out_sel (Amount 0 = in1) -> out1. A strike that reaches the electrode stops the growth; Autoregrow starts
# a new one Hold s later (GPU side: the regrow count is part of the state epoch).
# Shaders builders/glsl/gen_sim_dla_*.glsl; maths + numpy reference builders/gen_sim_logic.py (jacobi, dla_fixed,
# dla_grow, dla_touched, dla_phimax, dla_run); LIVE CHECKS docs/builds/gen_sim.md. ASCII only.

MODULE = 'dla'
LG = logic()
SHAPE_LABELS = ['Centre point (frost / DLA)', 'Bottom line (coral)', 'Top point (lightning)', 'Ring (inward)',
                'Input (threshold)', 'Scatter points']

PAGES = [
    ('Dla', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Shape', 'Menu', 'centre', {'names': LG['DLA_SHAPES'], 'labels': SHAPE_LABELS}),
        ('Cell', 'Float', 4.0, {'min': 1, 'max': 16, 'label': 'Cell px'}),
        ('Steps', 'Int', 2, {'min': 0, 'max': 16, 'label': 'Growth steps / frame'}),
        ('Run', 'Toggle', True, {'label': 'Run'}),
        ('Growth', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Growth'}),
        ('Eta', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Eta (branching)'}),
        ('Phiref', 'Float', 1.0, {'min': 0.05, 'max': 2, 'label': 'Phi reference (x phimax)'}),
        ('Iters', 'Int', 32, {'min': 8, 'max': 128, 'label': 'Field iterations / frame'}),
        ('Fieldscale', 'Float', 1.0, {'min': 0.25, 'max': 1, 'label': 'Field res (x cells)'}),
        ('Warmup', 'Int', 256, {'min': 0, 'max': 2000, 'label': 'Warmup iterations'}),
        ('Autoregrow', 'Toggle', True, {'label': 'Regrow after a strike'}),
        ('Hold', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Strike hold s'}),
        ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Input threshold'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (regrow)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Look', [
        ('Viewmode', 'Menu', 'age', {'names': ['age', 'solid', 'field'], 'labels': ['Age', 'Solid', 'Field bands']}),
        ('Fade', 'Float', 400.0, {'min': 1, 'max': 4000, 'label': 'Age fade (steps x 8)'}),
        ('Glow', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Glow'}),
        ('Glowlod', 'Float', 2.5, {'min': 0, 'max': 6, 'label': 'Glow size (mip)'}),
        ('Bands', 'Float', 12.0, {'min': 1, 'max': 64, 'label': 'Field bands'}),
    ]),
    colour_page('ice', 'replace', (0.02, 0.05, 0.2), (0.85, 0.95, 1.0)),
    STATE_PAGE,
]
PANEL_PAGES = ['Dla', 'Look', 'Colour']
RESEED = ['Shape', 'Seed']

PRESETS = [
    (1, 'frost', {'Shape': 0, 'Growth': 0.3, 'Eta': 1.0, 'Steps': 2, 'Hold': 1.5, 'Viewmode': 0,
                  'Glow': 0.6, 'Palette': 2}),
    (2, 'lightning', {'Shape': 2, 'Growth': 0.2, 'Eta': 4.0, 'Steps': 4, 'Hold': 0.5, 'Viewmode': 1,
                      'Glow': 1.5, 'Glowlod': 3.0, 'Palette': 2}),
    (3, 'coral', {'Shape': 1, 'Growth': 0.3, 'Eta': 1.5, 'Steps': 2, 'Hold': 2.0, 'Viewmode': 0,
                  'Glow': 0.4, 'Palette': 3}),
    (4, 'ring', {'Shape': 3, 'Growth': 0.3, 'Eta': 1.2, 'Steps': 2, 'Viewmode': 0, 'Glow': 0.5, 'Palette': 4}),
    (5, 'field bands', {'Shape': 0, 'Growth': 0.3, 'Eta': 1.0, 'Steps': 2, 'Viewmode': 2, 'Bands': 16.0,
                        'Glow': 0.0, 'Palette': 3}),
    (6, 'crystallise', {'Shape': 4, 'Growth': 0.3, 'Eta': 1.0, 'Steps': 2, 'Threshold': 0.5, 'Viewmode': 0,
                        'Glow': 0.6, 'Palette': 2}),
]

SIMW = "max(1, int(op('in1').width / max(1.0, parent().par.Cell.eval())))"
SIMH = "max(1, int(op('in1').height / max(1.0, parent().par.Cell.eval())))"
FW = "max(1, int(%s * parent().par.Fieldscale.eval() + 0.5))" % SIMW
FH = "max(1, int(%s * parent().par.Fieldscale.eval() + 0.5))" % SIMH
SHAPE = "parent().par.Shape.menuIndex"
NSTEPS = "(max(0, int(parent().par.Steps.eval())) if parent().par.Run.eval() else 0)"
EL_R = "(max(2.0, 0.03 * min(%s, %s)) if %s == 3 else 0.0)" % (FW, FH, SHAPE)
BC = [('uBC', [LG['dla_bc_expr'](i, SHAPE) for i in range(4)])]


def uniforms():
    return {
        'touch': [('uT', [SIMW, SIMH, EPOCH, 'absTime.seconds']),
                  ('uT2', [P.format('Hold'), "1 if parent().par.Autoregrow.eval() else 0", FW, FH])] + BC +
                 [('uTe', ["%s * 0.5" % SIMW, "%s * 0.5" % SIMH, "%s * %s / %s" % (EL_R, SIMW, FW), '0'])],
        'field': [('uF', [FW, FH, EPOCH, '0'])] + BC +
                 [('uEl', ["%s * 0.5" % FW, "%s * 0.5" % FH, EL_R, '0']), ('uFs', [SIMW, SIMH, '0', '0'])],
        'grow': [('uD', [SIMW, SIMH, '0', SHAPE]),
                 ('uG', [P.format('Growth'), P.format('Eta'), NSTEPS, 'absTime.frame']),
                 ('uD2', [P.format('Seed'), P.format('Threshold'), '0', P.format('Phiref')]),
                 ('uFs', [FW, FH, P.format('Warmup'), '0'])],
        'look': [('uDl', [PI.format('Viewmode'), P.format('Fade'), P.format('Glow'), 'absTime.frame * 8']),
                 ('uDl2', [SIMW, SIMH, P.format('Glowlod'), P.format('Bands')])] + LOOK_UNIFORMS,
    }


def shader_texts():
    return dict((k, glsl_text('gen_sim_dla_' + k)) for k in ('touch', 'field', 'grow', 'look'))


def build(m, H):
    mk = H['mk']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')
    cfb = H['state'](m, 'cluster_fb', 'grow', SIMW, SIMH)
    ffb = H['state'](m, 'field_fb', 'field', FW, FH)
    touch = H['pas'](m, 'touch', H['glsl']('gen_sim_dla_touch'), [cfb, ffb], '2', '1', 'rgba32float', U['touch'],
                     dispatch=('1', '1'), readwrite=True)
    touch.comment = ('Strike detector + phimax (one 32x32 workgroup, in place): texel 0 touched / time / regrows / '
                     'epoch, texel 1 phimax.')
    field = H['pas'](m, 'field', H['glsl']('gen_sim_dla_field'), [ffb, cfb, touch], FW, FH, 'rgba32float',
                     U['field'], npasses="max(1, int(math.ceil(parent().par.Iters.eval() / 8.0)))",
                     dispatch=("int(math.ceil(%s / 16.0))" % FW, "int(math.ceil(%s / 16.0))" % FH))
    field.comment = 'Laplace field: 8 Jacobi iterations per pass (32x32 tiles, 16x16 cores); phi 0 on the cluster.'
    grow = H['pas'](m, 'grow', H['glsl']('gen_sim_dla_grow'), [cfb, field, in1], SIMW, SIMH, 'rgba32float',
                    U['grow'], npasses="max(1, %s)" % NSTEPS)
    grow.comment = 'Growth: npasses = Steps; frontier cells attach with p = Growth (phi / (phimax Phiref))^Eta.'
    look = H['pas'](m, 'look', H['glsl']('gen_sim_dla_look'), [in1, grow, field], IN_W, IN_H, 'useinput',
                    U['look'], filt='mipmap')
    look.comment = 'Cluster by age / solid / field bands + mip glow, over the slot input.'
    H['out_sel'](m, look)
    H['pulses'](m, RESEED)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulses']},
        {'title': '2 Field', 'role': 'process',
         'ops': ['cluster_fb_blank', 'cluster_fb', 'field_fb_blank', 'field_fb', 'touch', 'touch_compute', 'field',
                 'field_compute'],
         'body': 'touch: strike + phimax + regrow. field: Jacobi x Iters (temporal blocking).'},
        {'title': '3 Growth', 'role': 'process', 'ops': ['grow', 'grow_compute']},
        {'title': '4 Look', 'role': 'process', 'ops': ['look', 'look_compute']},
        {'title': '5 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
