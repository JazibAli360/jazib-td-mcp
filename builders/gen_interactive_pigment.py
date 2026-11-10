# gen_interactive_pigment - GEN_interactive module 'pigment': luminous colour-carrying particles ("data pigment")
# flowing in a curl-noise field, pushed / pulled / swirled by the rack's tracked points, attracted to or repelled by
# the person mask, or carried by an external fluid (BN_fluid2d out2) - a technique emulation of Refik Anadol's data
# paintings (FX5 E1; the AI part is offline in his work and not attempted here; neutral par names, credit in
# docs/builds/gen_interactive.md). Colour per particle from the slot picture at its anchor, from an image atlas
# (cells cross-faded over time = the 'latent morph'), or a palette by speed / age / seed.
# Network: pts + field -> state (self-clocked particles, Feedback state_fb) -> splat (one thread per particle, square
# dots, last write wins, Quality res) -> trail (decay / add / paint, Feedback trail_fb) -> fx (glow + exposure over
# the slot input) -> out_sel (Amount 0 = in1) -> out1. Shaders builders/glsl/gen_interactive_pigment_*.glsl; numpy
# references builders/gen_interactive_pigment_logic.py; LIVE CHECKS docs/builds/gen_interactive.md. ASCII only.

MODULE = 'pigment'
SPAWNMODES = ['frame', 'points', 'mask', 'bottom']
EDGES = ['respawn', 'wrap']
FIELDSOURCES = ['mask', 'flowtop', 'none']
POINTMODES = ['push', 'attract', 'swirl']
COLORMODES = ['source', 'atlas', 'speed', 'age', 'seed']
TRAILMODES = ['max', 'add', 'paint']

PAGES = [
    ('Pigment', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Side', 'Int', 256, {'min': 8, 'max': 512, 'label': 'Particles per side (count = side^2)'}),
        ('Life', 'Float', 4.0, {'min': 0.1, 'max': 60, 'label': 'Life s'}),
        ('Lifevar', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Life variation'}),
        ('Spawnmode', 'Menu', 'frame', {'names': SPAWNMODES, 'labels': ['Anywhere', 'Around the points',
                                                                       'Inside the mask', 'Bottom edge']}),
        ('Edge', 'Menu', 'respawn', {'names': EDGES, 'labels': ['Respawn when out', 'Wrap around']}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Flow', [
        ('Flowscale', 'Float', 300.0, {'min': 10, 'max': 3000, 'label': 'Flow scale px'}),
        ('Flowstrength', 'Float', 120.0, {'min': 0, 'max': 2000, 'label': 'Flow strength px/s'}),
        ('Evolve', 'Float', 0.15, {'min': 0, 'max': 4, 'label': 'Evolve (field drift /s)'}),
        ('Octaves', 'Int', 3, {'min': 1, 'max': 6, 'label': 'Octaves'}),
        ('Fieldsource', 'Menu', 'none', {'names': FIELDSOURCES, 'labels': ['Rack mask (attract / repel)',
                                                                          'Flow TOP (fluid velocity)', 'None']}),
        ('Maskforce', 'Float', 0.0, {'min': -2000, 'max': 2000, 'label': 'Mask force (+ attract, - repel)'}),
        ('Flowtop', 'TOP', '', {'label': 'Flow TOP (e.g. BN_fluid2d/out2, cells/s)'}),
        ('Flowgain', 'Float', 1.0, {'min': -10, 'max': 10, 'label': 'Flow TOP gain'}),
    ]),
    ('Points', [
        ('Radius', 'Float', 220.0, {'min': 1, 'max': 2000, 'label': 'Point radius px'}),
        ('Pointforce', 'Float', 250.0, {'min': -4000, 'max': 4000, 'label': 'Point force px/s'}),
        ('Pointmode', 'Menu', 'push', {'names': POINTMODES, 'labels': ['Push', 'Attract', 'Swirl']}),
        ('Pointvel', 'Float', 0.5, {'min': 0, 'max': 4, 'label': 'Drag along with the point'}),
    ]),
    ('Look', [
        ('Colormode', 'Menu', 'source', {'names': COLORMODES, 'labels': ['Source picture', 'Image atlas',
                                                                         'Speed', 'Age', 'Seed']}),
        ('Atlastop', 'TOP', '', {'label': 'Atlas TOP (N x N images)'}),
        ('Atlascells', 'Int', 4, {'min': 1, 'max': 16, 'label': 'Atlas cells per side'}),
        ('Atlasrate', 'Float', 0.1, {'min': 0, 'max': 8, 'label': 'Atlas morph cells/s'}),
        ('Morph', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Colour follow /s (re-sample)'}),
        ('Speedref', 'Float', 300.0, {'min': 1, 'max': 5000, 'label': 'Reference speed px/s'}),
        ('Size', 'Float', 2.0, {'min': 1, 'max': 16, 'label': 'Dot size px'}),
        ('Opacity', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Opacity'}),
        ('Agefade', 'Float', 0.2, {'min': 0, 'max': 0.5, 'label': 'Fade in / out (share of life)'}),
        ('Quality', 'Float', 0.5, {'min': 0.1, 'max': 1, 'label': 'Quality (trail res x)'}),
        ('Trail', 'Float', 1.5, {'min': 0, 'max': 30, 'label': 'Trail s (0 = none)'}),
        ('Trailmode', 'Menu', 'max', {'names': TRAILMODES, 'labels': ['Max (luminous)', 'Add (builds up)',
                                                                      'Paint (dots replace)']}),
        ('Exposure', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Exposure'}),
        ('Glow', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Glow'}),
        ('Glowwidth', 'Float', 6.0, {'min': 0.5, 'max': 60, 'label': 'Glow width px'}),
    ]),
    drive_page(),
    STATE_PAGE_GI,
    colour_page('neon', 'replace', (0.1, 0.3, 1.0), (1.0, 0.4, 0.8)),
]
PANEL_PAGES = ['Pigment', 'Flow', 'Points', 'Look', 'Drive', 'Colour']
RESEED = ['Side', 'Seed']

PRESETS = full_presets(PAGES, [
    (1, 'pigment flow', {'Colormode': 0, 'Flowstrength': 120.0, 'Trail': 1.5, 'Size': 2.0, 'Glow': 0.4,
                         'Blend': 0}),
    (2, 'data atlas', {'Colormode': 1, 'Atlascells': 4, 'Atlasrate': 0.2, 'Morph': 0.5, 'Flowscale': 500.0,
                       'Flowstrength': 90.0, 'Trail': 2.0, 'Glow': 0.5, 'Blend': 0}),
    (3, 'ember swirl', {'Colormode': 2, 'Palette': 1, 'Pointmode': 2, 'Pointforce': 400.0, 'Radius': 300.0,
                        'Trail': 2.5, 'Trailmode': 1, 'Exposure': 0.6, 'Flowstrength': 60.0, 'Blend': 0}),
    (4, 'person bloom', {'Fieldsource': 0, 'Maskforce': 300.0, 'Spawnmode': 2, 'Colormode': 3, 'Palette': 3,
                         'Life': 3.0, 'Trail': 1.0, 'Glow': 0.6, 'Blend': 2}),
    (5, 'fluid ink', {'Fieldsource': 1, 'Flowgain': 1.0, 'Flowstrength': 30.0, 'Colormode': 0, 'Trail': 4.0,
                      'Trailmode': 2, 'Size': 3.0, 'Glow': 0.0, 'Blend': 0}),
    (6, 'beat burst', {'Beatgain': 2.0, 'Beatdecay': 0.3, 'Flowstrength': 80.0, 'Pointmode': 0,
                       'Pointforce': 600.0, 'Colormode': 4, 'Palette': 4, 'Trail': 1.2, 'Blend': 0}),
])

SIDE_ = "max(8, int(%s))" % P.format('Side')
STATE_W = "2 * %s" % SIDE_
STATE_H = "%s + 1" % SIDE_
TRAIL_W = "max(1, int(%s * %s + 0.5))" % (IN_W, P.format('Quality'))
TRAIL_H = "max(1, int(%s * %s + 0.5))" % (IN_H, P.format('Quality'))
DISPATCH = "max(1, (%s + 7) // 8)" % SIDE_
FIELD_SRC = ("(lambda f, t: t if f == 'flowtop' and t is not None else (op('mask') if f == 'mask' else op('pts')))"
             "(parent().par.Fieldsource.eval(), parent().par.Flowtop.eval())")
COL_SRC = ("(lambda t: t if parent().par.Colormode.eval() == 'atlas' and t is not None else op('in1'))"
           "(parent().par.Atlastop.eval())")


def state_uniforms():
    return [('uTime', [TIME_EXPR, P.format('Speed'), EPOCH, SIDE_]),
            ('uFlow', [P.format('Flowscale'), P.format('Flowstrength'), P.format('Evolve'), P.format('Octaves')]),
            ('uLife', [P.format('Life'), P.format('Lifevar'), PI.format('Spawnmode'), P.format('Seed')]),
            ('uPt', [P.format('Radius'), P.format('Pointforce'), PI.format('Pointmode'), P.format('Pointvel')]),
            ('uExt', [PI.format('Fieldsource'), P.format('Maskforce'), P.format('Flowgain'), PI.format('Edge')]),
            ('uMisc', [P.format('Morph'), IN_W, IN_H, '0'])] + DRIVE_UNIFORMS


def splat_uniforms():
    return [('uS', [SIDE_, P.format('Size'), P.format('Opacity'), P.format('Agefade')]),
            ('uC', [PI.format('Colormode'), P.format('Atlascells'), P.format('Atlasrate'), P.format('Speedref')]),
            ('uQ', [P.format('Quality'), IN_W, IN_H, '0'])] + LOOK_UNIFORMS


def trail_uniforms():
    return [('uT', [P.format('Trail'), PI.format('Trailmode'), SIDE_, '0'])]


def look_uniforms():
    return [('uL', [P.format('Exposure'), P.format('Glow'), P.format('Glowwidth'), '0'])] + LOOK_UNIFORMS


def shader_texts():
    return {'state': glsl_text('gen_interactive_pigment_state'), 'splat': glsl_text('gen_interactive_pigment_splat'),
            'trail': glsl_text('gen_interactive_pigment_trail'), 'fx': glsl_text('gen_interactive_pigment_look')}


def build(m, H):
    mk = H['mk']
    tx = shader_texts()
    in1 = mk(m, inTOP, 'in1')
    pts = H['pts_in'](m)
    H['mask_in'](m)
    field = mk(m, selectTOP, 'field')
    H['expr'](field.par.top, FIELD_SRC)
    field.comment = 'Field: rack mask (Fieldsource mask), the Flow TOP (flowtop), else pts (unused, nothing heavy cooks).'
    col = mk(m, selectTOP, 'colsrc')
    H['expr'](col.par.top, COL_SRC)
    col.comment = 'Colour source: the Atlas TOP in Colormode atlas (when set), else the slot input.'
    fb = H['state'](m, 'state_fb', 'state', STATE_W, STATE_H)
    st = H['pas'](m, 'state', tx['state'], [fb, pts, field], STATE_W, STATE_H, 'rgba32float', state_uniforms(),
                  filt='linear')
    st.comment = 'Particles: texel 2i = x y age life, 2i+1 = anchor seed speed; last row = meta (T, time, epoch, dts).'
    sp = H['pas'](m, 'splat', tx['splat'], [st, col], TRAIL_W, TRAIL_H, 'rgba16float', splat_uniforms(),
                  dispatch=(DISPATCH, DISPATCH), filt='linear')
    sp.par.clearoutputs = True                         # untouched texels = 0 (scatter, T-138)
    sp.comment = 'Pigment dots: one thread per particle stores a Size px square (last write wins), Quality res.'
    tfb = H['state'](m, 'trail_fb', 'trail', TRAIL_W, TRAIL_H, 'rgba16float')
    tr = H['pas'](m, 'trail', tx['trail'], [sp, tfb, st], TRAIL_W, TRAIL_H, 'rgba16float', trail_uniforms())
    tr.comment = 'Trail: max / add / paint of the dots over the last trail x exp(-dts / Trail).'
    fx = H['pas'](m, 'fx', tx['fx'], [in1, tr], IN_W, IN_H, 'useinput', look_uniforms(), filt='linear')
    fx.comment = 'Look: trail upsampled + ring glow, Exposure, over the slot input (Colour page Blend).'
    H['out_sel'](m, fx)
    H['pulses'](m, RESEED)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pts', 'mask', 'field', 'colsrc', 'pulses']},
        {'title': '2 Particles', 'role': 'process', 'ops': ['state_fb_blank', 'state_fb', 'state', 'state_compute'],
         'body': 'Self-clocked particles (Speed 0 = frozen). Reset / Side / Seed change = re-seeded.'},
        {'title': '3 Dots + trail', 'role': 'process', 'ops': ['splat', 'splat_compute', 'trail_fb_blank',
                                                               'trail_fb', 'trail', 'trail_compute']},
        {'title': '4 Look', 'role': 'process', 'ops': ['fx', 'fx_compute']},
        {'title': '5 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
