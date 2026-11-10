# gen_interactive_skinner - GEN_interactive module 'skinner' (FX7c 7C-25 "Skinner shards on a performer": the
# silhouette becomes long thin random triangles that re-roll and glitch, more of them where the body moves; technique
# from the README of Keijiro Takahashi's Skinner (Unity, ideas ported, no code copied). Lane F, 27 Oct 2026.
# Network: rack mask (presence + motion) -> slots (N points kept inside the mask, re-spawned when they leave it or by
# Respawn / s; self-clocked, Feedback slots_fb) -> tris (M shards: 3 hashed slots per life, longest edge in Minlen..
# Maxlen, shown by Density + Motiongain x motion, fade in / out per life) -> draw (8x8 tile lists, fill + edges +
# glow, palette) over the slot input -> out_sel (Amount 0 = in1) -> out1. Set the rack Masksource to the person mask
# (CV_person_mask/out2) or luma; with Masksource none the shards fill the frame. Shaders builders/glsl/
# gen_interactive_skinner_*.glsl; references builders/gen_interactive_skinner_logic.py. No limits. ASCII only.

MODULE = 'skinner'

PAGES = [
    ('Shards', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Slots', 'Int', 512, {'min': 3, 'max': 16384, 'label': 'Points on the body'}),
        ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Mask presence threshold'}),
        ('Respawn', 'Float', 0.5, {'min': 0, 'max': 60, 'label': 'Point respawn / s'}),
        ('Shards', 'Int', 256, {'min': 1, 'max': 16384, 'label': 'Shards'}),
        ('Rerollhz', 'Float', 2.0, {'min': 0, 'max': 30, 'label': 'Shard lives / s'}),
        ('Minlen', 'Float', 120.0, {'min': 0, 'max': 2000, 'label': 'Longest edge min px'}),
        ('Maxlen', 'Float', 700.0, {'min': 1, 'max': 4000, 'label': 'Longest edge max px'}),
        ('Density', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Shown share (still)'}),
        ('Motiongain', 'Float', 4.0, {'min': 0, 'max': 40, 'label': 'Shown share x motion'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 999, 'label': 'Seed'}),
    ]),
    ('Look', [
        ('Fill', 'Float', 0.25, {'min': 0, 'max': 2, 'label': 'Fill'}),
        ('Edgewidth', 'Float', 1.2, {'min': 0.05, 'max': 20, 'label': 'Edge width px'}),
        ('Glow', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Edge glow'}),
        ('Glowwidth', 'Float', 4.0, {'min': 0.1, 'max': 60, 'label': 'Glow width px'}),
    ]),
    drive_page(),
    STATE_PAGE_GI,
    colour_page('neon', 'add', (0.2, 0.9, 1.0), (1.0, 0.2, 0.6)),
]
PANEL_PAGES = ['Shards', 'Look', 'Drive', 'Colour']
RESEED = ['Slots', 'Seed']

PRESETS = full_presets(PAGES, [
    (1, 'glass shards', {}),
    (2, 'needles', {'Minlen': 300.0, 'Maxlen': 1600.0, 'Fill': 0.0, 'Edgewidth': 1.0, 'Glow': 0.6,
                    'Rerollhz': 6.0, 'Shards': 512, 'Palette': 3}),
    (3, 'solid facets', {'Minlen': 40.0, 'Maxlen': 260.0, 'Fill': 0.8, 'Edgewidth': 0.6, 'Glow': 0.0,
                         'Shards': 1024, 'Slots': 1024, 'Density': 0.8, 'Palette': 4, 'Blend': 1}),
    (4, 'motion burst', {'Density': 0.02, 'Motiongain': 20.0, 'Rerollhz': 8.0, 'Glow': 0.8, 'Palette': 1}),
    (5, 'slow crystal', {'Rerollhz': 0.3, 'Respawn': 0.05, 'Fill': 0.4, 'Glow': 0.4, 'Glowwidth': 8.0,
                         'Palette': 0}),
])

N_ = "max(1, int(%s))" % P.format('Slots')
M_ = "max(1, int(%s))" % P.format('Shards')
SLOTS_H = "(%s + 63) // 64 + 1" % N_
TRIS_H = "(%s + 63) // 64" % M_


def slots_uniforms():
    return [('uTime', [TIME_EXPR, P.format('Speed'), EPOCH, P.format('Respawn')]),
            ('uK', [P.format('Slots'), P.format('Threshold'), P.format('Seed'), '0']),
            ('uSz', [IN_W, IN_H, '0', '0'])]


def tris_uniforms():
    return [('uR', [P.format('Shards'), P.format('Rerollhz'), P.format('Minlen'), P.format('Maxlen')]),
            ('uD', ["%s * (1.0 + %s * float(%s['level']) + %s)" % (P.format('Density'), P.format('Audiogain'),
                                                                     D_OP, P.format('Manual')),
                    P.format('Motiongain'), P.format('Seed'), P.format('Slots')])]


def draw_uniforms():
    return [('uR', [P.format('Shards'), P.format('Edgewidth'), P.format('Glow'), P.format('Glowwidth')]),
            ('uF', [P.format('Fill'), '0', '0', '0'])] + LOOK_UNIFORMS


def shader_texts():
    return dict((k, glsl_text('gen_interactive_skinner_' + k)) for k in ('slots', 'tris', 'draw'))


def build(m, H):
    mk = H['mk']
    tx = shader_texts()
    in1 = mk(m, inTOP, 'in1')
    msk = H['mask_in'](m)
    fb = H['state'](m, 'slots_fb', 'slots', '64', SLOTS_H)
    sl = H['pas'](m, 'slots', tx['slots'], [fb, msk], '64', SLOTS_H, 'rgba32float', slots_uniforms())
    sl.comment = 'Points kept inside the rack mask (respawn when they leave it); last row = meta (count, T, time, epoch).'
    tr = H['pas'](m, 'tris', tx['tris'], [sl], '128', TRIS_H, 'rgba32float', tris_uniforms())
    tr.comment = 'Shards: 3 slots per life (longest edge Minlen..Maxlen), shown by density + motion, fade per life.'
    dr = H['pas'](m, 'draw', tx['draw'], [in1, tr], IN_W, IN_H, 'useinput', draw_uniforms())
    dr.comment = 'Shards: 8x8 tile lists, fill + edges + glow, palette per shard, over the slot input.'
    H['out_sel'](m, dr)
    H['pulses'](m, RESEED)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'mask', 'pulses']},
        {'title': '2 Points + shards', 'role': 'process',
         'ops': ['slots_fb_blank', 'slots_fb', 'slots', 'slots_compute', 'tris', 'tris_compute'],
         'body': 'Points live inside the mask; shards pick 3 of them per life (long thin triangles).'},
        {'title': '3 Draw', 'role': 'process', 'ops': ['draw', 'draw_compute']},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
