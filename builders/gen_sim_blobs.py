# gen_sim_blobs - GEN_sim module 'blobs': 2D metaballs / SDF smooth-min blobs (FX5 G12): lava lamp, mercury, neon
# outline, contour bands, glass (refracts the slot input). One compute pass; blobs move analytically from the module
# clock, so there is no state to reset. Each 16x16 workgroup lists the blobs that reach its tile (ordered prefix-sum
# compaction, no atomics), so cost follows the blobs near a pixel, not Count.
# Network: in1 + clock -> fx -> out_sel (Amount 0 = in1) -> out1. Shader builders/glsl/gen_sim_blobs.glsl; maths +
# numpy reference builders/gen_sim_logic.py (blob_params, blob_field); LIVE CHECKS docs/builds/gen_sim.md. ASCII only.

MODULE = 'blobs'
LG = logic()

PAGES = [
    ('Blobs', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Count', 'Int', 24, {'min': 1, 'max': 1024, 'label': 'Blobs'}),
        ('Radius', 'Float', 90.0, {'min': 4, 'max': 600, 'label': 'Radius px'}),
        ('Rvar', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Radius variation'}),
        ('Field', 'Menu', 'metaball', {'names': LG['BLOB_FIELDS'], 'labels': ['Metaball (Wyvill)',
                                                                             'SDF smooth-min']}),
        ('Threshold', 'Float', 0.5, {'min': 0.01, 'max': 0.99, 'label': 'Metaball iso (merge)'}),
        ('Softness', 'Float', 40.0, {'min': 0, 'max': 300, 'label': 'SDF softness px'}),
        ('Motion', 'Menu', 'wander', {'names': LG['BLOB_MOTIONS'], 'labels': ['Wander', 'Lava (rise / fall)',
                                                                             'Orbit', 'Drift (noise)']}),
        ('Speed', 'Float', 0.4, {'min': 0, 'max': 4, 'label': 'Speed'}),
        ('Pulse', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Radius pulse'}),
        ('Pulserate', 'Float', 0.5, {'min': 0, 'max': 4, 'label': 'Pulse Hz (module time)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Style', [
        ('Style', 'Menu', 'flat', {'names': LG['BLOB_STYLES'], 'labels': ['Flat (per blob)', 'Mercury', 'Neon outline',
                                                                         'Contour bands', 'Glass (refract input)']}),
        ('Edgewidth', 'Float', 3.0, {'min': 0, 'max': 40, 'label': 'Edge / line px'}),
        ('Bands', 'Float', 18.0, {'min': 2, 'max': 200, 'label': 'Band spacing px'}),
        ('Refract', 'Float', 30.0, {'min': 0, 'max': 200, 'label': 'Refraction px'}),
        ('Height', 'Float', 40.0, {'min': 1, 'max': 300, 'label': 'Dome height px'}),
        ('Spec', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Specular'}),
    ]),
    colour_page('fire', 'replace', (0.1, 0.1, 0.12), (0.95, 0.95, 1.0)),
]
PANEL_PAGES = ['Blobs', 'Style', 'Colour']

PRESETS = [
    (1, 'lava', {'Count': 18, 'Radius': 110.0, 'Rvar': 0.5, 'Field': 0, 'Threshold': 0.45, 'Motion': 1, 'Speed': 0.3,
                 'Style': 0, 'Palette': 1, 'Blend': 0}),
    (2, 'mercury', {'Count': 14, 'Radius': 120.0, 'Rvar': 0.4, 'Field': 0, 'Threshold': 0.5, 'Motion': 0,
                    'Speed': 0.35, 'Style': 1, 'Height': 60.0, 'Spec': 1.5, 'Palette': 0, 'Blend': 0}),
    (3, 'neon', {'Count': 30, 'Radius': 70.0, 'Rvar': 0.5, 'Field': 1, 'Softness': 60.0, 'Motion': 2, 'Speed': 0.4,
                 'Style': 2, 'Edgewidth': 4.0, 'Palette': 4, 'Blend': 0}),
    (4, 'bands', {'Count': 20, 'Radius': 100.0, 'Field': 1, 'Softness': 80.0, 'Motion': 3, 'Speed': 0.5, 'Style': 3,
                  'Bands': 16.0, 'Edgewidth': 3.0, 'Palette': 3, 'Blend': 0}),
    (5, 'glass', {'Count': 12, 'Radius': 140.0, 'Field': 0, 'Threshold': 0.5, 'Motion': 0, 'Speed': 0.25, 'Style': 4,
                  'Refract': 40.0, 'Height': 80.0, 'Spec': 1.0, 'Blend': 1}),
    (6, 'pulse cells', {'Count': 200, 'Radius': 28.0, 'Rvar': 0.6, 'Field': 1, 'Softness': 20.0, 'Motion': 3,
                        'Pulse': 0.4, 'Pulserate': 0.6, 'Style': 0, 'Palette': 4, 'Blend': 0}),
]


def uniforms():
    return [('uB1', [P.format('Count'), P.format('Radius'), P.format('Rvar'), P.format('Pulse')]),
            ('uB2', [PI.format('Field'), P.format('Threshold'), P.format('Softness'), PI.format('Motion')]),
            ('uB3', [PI.format('Style'), P.format('Edgewidth'), P.format('Bands'), P.format('Refract')]),
            ('uB4', [P.format('Seed'), P.format('Pulserate'), P.format('Height'), P.format('Spec')])] + LOOK_UNIFORMS


def shader_texts():
    return {'fx': glsl_text('gen_sim_blobs')}


def build(m, H):
    mk = H['mk']
    in1 = mk(m, inTOP, 'in1')
    clk = H['clock'](m)
    fx = H['pas'](m, 'fx', H['glsl']('gen_sim_blobs'), [in1, clk], IN_W, IN_H, 'useinput', uniforms())
    fx.comment = 'Blobs: per-tile blob lists (16x16), field / SDF, style, over the slot input.'
    H['out_sel'](m, fx)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'clock', 'clock_compute']},
        {'title': '2 Blobs', 'role': 'process', 'ops': ['fx', 'fx_compute']},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
