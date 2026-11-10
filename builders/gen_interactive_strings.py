# gen_interactive_strings - GEN_interactive module 'strings' (FX7b TC-28 "repelling strings": a curtain / harp of
# strings that bends away from the tracked points, the person mask or a beat kick and springs back, colour running
# along the strings; technique emulation of g3n0m4's TOP-only system, clean-room). Lane F, 27 Oct 2026.
# Network: in1 + pts (rack points) + mask (rack mask) -> step (string physics, ONE workgroup per string with
# shared-memory substeps, self-clocked, Feedback state_fb) -> draw (capsules + glow over the slot input) -> out_sel
# (Amount 0 = in1) -> out1. Shaders builders/glsl/gen_interactive_strings_*.glsl; float64 references
# builders/gen_interactive_strings_logic.py; LIVE CHECKS docs/builds/gen_interactive.md "strings". No limits. ASCII.

MODULE = 'strings'
ORIENTS = ['vertical', 'horizontal']
PINS = ['top', 'both', 'none']
FMODES = ['push', 'pull', 'swirl']
CMODES = ['along', 'bend', 'index', 'speed']

PAGES = [
    ('Strings', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Strings', 'Int', 40, {'min': 1, 'max': 512, 'label': 'Strings'}),
        ('Nodes', 'Int', 64, {'min': 2, 'max': 256, 'label': 'Nodes per string'}),
        ('Orient', 'Menu', 'vertical', {'names': ORIENTS, 'labels': ['Vertical (curtain / harp)', 'Horizontal']}),
        ('Margin', 'Float', 0.03, {'min': 0, 'max': 0.45, 'label': 'Side margin (share of the frame)'}),
        ('Pin', 'Menu', 'both', {'names': PINS, 'labels': ['Top / left end (hangs)', 'Both ends (harp)', 'None']}),
    ]),
    ('Physics', [
        ('Stiffness', 'Float', 12.0, {'min': 0, 'max': 200, 'label': 'Spring back (1/s2)'}),
        ('Tension', 'Float', 2500.0, {'min': 0, 'max': 20000, 'label': 'Tension (neighbour pull)'}),
        ('Damping', 'Float', 3.0, {'min': 0, 'max': 40, 'label': 'Damping (1/s)'}),
        ('Gravity', 'Float', 0.0, {'min': -2000, 'max': 2000, 'label': 'Gravity px/s2'}),
        ('Wind', 'Float', 0.0, {'min': 0, 'max': 5000, 'label': 'Wind px/s2'}),
        ('Substep', 'Float', 0.004, {'min': 0.0005, 'max': 0.05, 'label': 'Max substep s'}),
    ]),
    ('Force', [
        ('Force', 'Float', 20000.0, {'min': 0, 'max': 400000, 'label': 'Point force px/s2'}),
        ('Radius', 'Float', 220.0, {'min': 1, 'max': 2000, 'label': 'Point radius px'}),
        ('Mode', 'Menu', 'push', {'names': FMODES, 'labels': ['Push away (repel)', 'Pull in', 'Swirl']}),
        ('Pointsused', 'Int', 16, {'min': 0, 'max': 64, 'label': 'Points used'}),
        ('Maskforce', 'Float', 0.0, {'min': -2000000, 'max': 2000000, 'label': 'Mask push (x presence gradient)'}),
        ('Kick', 'Float', 0.0, {'min': 0, 'max': 5000, 'label': 'Beat kick px/s'}),
    ]),
    ('Look', [
        ('Linewidth', 'Float', 1.5, {'min': 0.05, 'max': 40, 'label': 'Line width px'}),
        ('Glow', 'Float', 0.25, {'min': 0, 'max': 4, 'label': 'Glow'}),
        ('Glowwidth', 'Float', 5.0, {'min': 0.1, 'max': 100, 'label': 'Glow width px'}),
        ('Colourmode', 'Menu', 'along', {'names': CMODES, 'labels': ['Along the string', 'Bend (offset)',
                                                                    'String index', 'Speed']}),
        ('Flow', 'Float', 0.1, {'min': -4, 'max': 4, 'label': 'Colour flow (cycles / s)'}),
        ('Bendref', 'Float', 120.0, {'min': 1, 'max': 2000, 'label': 'Bend for palette end px'}),
        ('Speedref', 'Float', 1500.0, {'min': 1, 'max': 20000, 'label': 'Speed for palette end px/s'}),
    ]),
    drive_page(),
    STATE_PAGE_GI,
    colour_page('rainbow', 'over', (0.3, 1.0, 0.6), (1.0, 0.2, 0.8)),
]
PANEL_PAGES = ['Strings', 'Physics', 'Force', 'Look', 'Drive', 'Colour']
RESEED = ['Strings', 'Nodes', 'Orient']

PRESETS = full_presets(PAGES, [
    (1, 'harp', {}),
    (2, 'curtain', {'Strings': 64, 'Nodes': 96, 'Pin': 0, 'Gravity': 300.0, 'Wind': 400.0, 'Stiffness': 2.0,
                    'Damping': 1.5, 'Colourmode': 1, 'Palette': 3, 'Glow': 0.4}),
    (3, 'beat strum', {'Strings': 24, 'Kick': 900.0, 'Damping': 1.2, 'Tension': 4000.0, 'Colourmode': 3,
                       'Palette': 1, 'Linewidth': 2.5, 'Glow': 0.6, 'Glowwidth': 8.0, 'Beatgain': 1.0}),
    (4, 'swirl threads', {'Orient': 1, 'Strings': 48, 'Mode': 2, 'Force': 60000.0, 'Radius': 320.0,
                          'Colourmode': 2, 'Palette': 4, 'Flow': 0.3}),
    (5, 'person repel', {'Strings': 72, 'Nodes': 128, 'Maskforce': 400000.0, 'Force': 0.0, 'Colourmode': 1,
                         'Bendref': 80.0, 'Palette': 3}),
    (6, 'neon flow', {'Strings': 32, 'Linewidth': 3.0, 'Glow': 0.9, 'Glowwidth': 10.0, 'Colourmode': 0,
                      'Flow': 0.6, 'Palette': 4, 'Blend': 2}),
])

S_ = "max(1, int(%s))" % P.format('Strings')
K_ = "min(256, max(2, int(%s)))" % P.format('Nodes')
STATE_W = K_
STATE_H = "%s + 1" % S_


def step_uniforms():
    return [('uTime', [TIME_EXPR, P.format('Speed'), EPOCH, P.format('Substep')]),
            ('uS', [P.format('Strings'), P.format('Nodes'), PI.format('Orient'), P.format('Margin')]),
            ('uPh', [P.format('Stiffness'), P.format('Tension'), P.format('Damping'), P.format('Gravity')]),
            ('uF', [P.format('Force'), P.format('Radius'), PI.format('Mode'), P.format('Maskforce')]),
            ('uX', [P.format('Kick'), P.format('Wind'), PI.format('Pin'), P.format('Pointsused')]),
            ('uSz', [IN_W, IN_H, '0', '0'])] + DRIVE_UNIFORMS


def draw_uniforms():
    return [('uS', [P.format('Strings'), P.format('Nodes'), PI.format('Orient'), P.format('Margin')]),
            ('uD', [P.format('Linewidth'), P.format('Glow'), P.format('Glowwidth'), PI.format('Colourmode')]),
            ('uD2', [P.format('Flow'), '0', '0', P.format('Bendref')]),
            ('uSz', [IN_W, IN_H, P.format('Speedref'), '0'])] + LOOK_UNIFORMS


CBOX_W = "(%s - 1 + 7) // 8" % K_


def cbox_uniforms():
    return [('uS', [P.format('Strings'), P.format('Nodes'), PI.format('Orient'), P.format('Margin')]),
            ('uSz', [IN_W, IN_H, '0', '0'])]


def shader_texts():
    return {'step': glsl_text('gen_interactive_strings_step'), 'cbox': glsl_text('gen_interactive_strings_cbox'),
            'draw': glsl_text('gen_interactive_strings_draw')}


def build(m, H):
    mk = H['mk']
    tx = shader_texts()
    in1 = mk(m, inTOP, 'in1')
    pts = H['pts_in'](m)
    msk = H['mask_in'](m)
    fb = H['state'](m, 'state_fb', 'step', STATE_W, STATE_H)
    st = H['pas'](m, 'step', tx['step'], [fb, pts, msk], STATE_W, STATE_H, 'rgba32float', step_uniforms())
    st.comment = ('String physics: one workgroup per string (256 threads = nodes), shared-memory substeps; row s = '
                  'node offset + velocity px, last row = meta (T, last time, epoch, beat).')
    cb = H['pas'](m, 'cbox', tx['cbox'], [st], CBOX_W, S_, 'rgba32float', cbox_uniforms())
    cb.comment = 'One bounding box per chunk of 8 segments (the draw tiles test these, not every segment).'
    dr = H['pas'](m, 'draw', tx['draw'], [in1, st, cb], IN_W, IN_H, 'useinput', draw_uniforms())
    dr.comment = 'Strings: 8x8 tile lists of every segment that can reach the tile, capsules + glow, palette flow.'
    H['out_sel'](m, dr)
    H['pulses'](m, RESEED)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pts', 'mask', 'pulses']},
        {'title': '2 Physics', 'role': 'process', 'ops': ['state_fb_blank', 'state_fb', 'step', 'step_compute'],
         'body': 'Spring + tension + damping, points push / pull / swirl, mask gradient, beat kick; self-clocked.'},
        {'title': '3 Draw', 'role': 'process', 'ops': ['cbox', 'cbox_compute', 'draw', 'draw_compute']},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
