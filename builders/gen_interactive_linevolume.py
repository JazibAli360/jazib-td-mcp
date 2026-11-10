# gen_interactive_linevolume - GEN_interactive module 'linevolume': line-volume light sculptures as hairlines of
# light - wire Platonic solids (nested), a tonal hatch sphere, a relief grid raised by the person mask / picture /
# noise (nearer lines hide farther ones), moire planes - a technique emulation of Joanie Lemercier's projected light
# sculptures (FX5 E3; neutral par names, credit in docs/builds/gen_interactive.md). Stateless: ONE compute pass.
# Network: in1 + pts (rack points: follow) + mask (rack mask: relief height / reveal) -> fx -> out_sel (Amount 0 =
# in1) -> out1; module time = clock (Constant CHOP rate = Speed) -> clock_int (Speed CHOP), GEN_pattern's clock, read
# by the uniform expressions (no clock texture input: 3 inputs, T-88). Shader builders/glsl/
# gen_interactive_linevolume.glsl (its `// %SOLIDS%` line = the solid tables of the logic file); float64 twin
# builders/gen_interactive_linevolume_logic.py; LIVE CHECKS docs/builds/gen_interactive.md. ASCII only.

MODULE = 'linevolume'
LV = module_logic('linevolume')

PAGES = [
    ('Scene', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Scene', 'Menu', 'wire', {'names': LV['SCENES'], 'labels': ['Wire solids', 'Hatch sphere', 'Relief grid',
                                                                     'Moire planes']}),
        ('Solid', 'Menu', 'icosa', {'names': LV['SOLIDS'], 'labels': ['Tetrahedron', 'Cube', 'Octahedron',
                                                                      'Icosahedron', 'Dodecahedron']}),
        ('Nest', 'Int', 1, {'min': 1, 'max': 8, 'label': 'Nested copies'}),
        ('Nestscale', 'Float', 0.6, {'min': 0.1, 'max': 1.5, 'label': 'Nest scale'}),
        ('Size', 'Float', 0.6, {'min': 0.05, 'max': 3, 'label': 'Size (world units)'}),
        ('Dist', 'Float', 3.0, {'min': 0.5, 'max': 20, 'label': 'Camera distance'}),
        ('Fov', 'Float', 40.0, {'min': 5, 'max': 120, 'label': 'Field of view deg'}),
        ('Rotx', 'Float', 20.0, {'min': -180, 'max': 180, 'label': 'Rotate x deg'}),
        ('Roty', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate y deg'}),
        ('Rotz', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate z deg'}),
        ('Spinx', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Spin x deg/s'}),
        ('Spiny', 'Float', 20.0, {'min': -180, 'max': 180, 'label': 'Spin y deg/s'}),
        ('Spinz', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Spin z deg/s'}),
        ('Kick', 'Float', 30.0, {'min': -180, 'max': 180, 'label': 'Beat kick deg (x pulse)'}),
        ('Phase', 'Float', 0.0, {'min': -10, 'max': 10, 'label': 'Phase s (added to the clock)'}),
        ('Posx', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Offset x (screen heights)'}),
        ('Posy', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Offset y (screen heights)'}),
        ('Follow', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Follow points (position)'}),
        ('Followrot', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Follow points (rotation)'}),
        ('Followmode', 'Menu', 'first', {'names': LV['FOLLOWMODES'], 'labels': ['First present point',
                                                                              'Centroid of the points']}),
    ]),
    ('Lines', [
        ('Linewidth', 'Float', 1.5, {'min': 0.25, 'max': 20, 'label': 'Line width px'}),
        ('Glow', 'Float', 0.4, {'min': 0, 'max': 4, 'label': 'Glow'}),
        ('Glowwidth', 'Float', 6.0, {'min': 0.5, 'max': 60, 'label': 'Glow width px'}),
        ('Depthfade', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Depth fade'}),
        ('Hatchdensity', 'Float', 40.0, {'min': 2, 'max': 300, 'label': 'Hatch lines per diameter'}),
        ('Hatchangle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Hatch angle deg'}),
        ('Crosshatch', 'Toggle', False, {'label': 'Cross hatch (lit side)'}),
        ('Hatchcontrast', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Hatch contrast (light -> duty)'}),
        ('Lightaz', 'Float', 45.0, {'min': -180, 'max': 180, 'label': 'Light azimuth deg'}),
        ('Lightel', 'Float', 30.0, {'min': -90, 'max': 90, 'label': 'Light elevation deg'}),
        ('Rim', 'Toggle', True, {'label': 'Sphere rim line'}),
        ('Reveal', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Reveal by mask'}),
        ('Revealinvert', 'Toggle', False, {'label': 'Reveal outside the person'}),
        ('Colourspread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Colour spread'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Relief', [
        ('Rows', 'Int', 48, {'min': 1, 'max': 512, 'label': 'Rows'}),
        ('Gridwidth', 'Float', 1.2, {'min': 0.1, 'max': 6, 'label': 'Grid half width (x Size)'}),
        ('Tilt', 'Float', 60.0, {'min': -90, 'max': 90, 'label': 'Plane tilt deg'}),
        ('Height', 'Float', 0.25, {'min': -2, 'max': 2, 'label': 'Relief height (world)'}),
        ('Heightsource', 'Menu', 'noise', {'names': LV['HEIGHTSOURCES'], 'labels': ['Mask presence', 'Picture luma',
                                                                                  'Value noise']}),
        ('Noisescale', 'Float', 3.0, {'min': 0.1, 'max': 40, 'label': 'Noise scale'}),
        ('Noisespeed', 'Float', 0.3, {'min': -4, 'max': 4, 'label': 'Noise flow /s'}),
        ('Occlude', 'Toggle', True, {'label': 'Nearer lines hide farther ones'}),
    ]),
    ('Moire', [
        ('Spacing', 'Float', 10.0, {'min': 2, 'max': 200, 'label': 'Line spacing px'}),
        ('Moireangle', 'Float', 2.0, {'min': -45, 'max': 45, 'label': 'Second set angle deg'}),
        ('Moirescale', 'Float', 0.02, {'min': -0.5, 'max': 0.5, 'label': 'Second set spacing +'}),
        ('Drift', 'Float', 5.0, {'min': -200, 'max': 200, 'label': 'Drift px/s (opposite ways)'}),
    ]),
    drive_page(),
    STATE_PAGE_GI,
    colour_page('ab', 'add', (0.75, 0.9, 1.0), (1.0, 1.0, 1.0)),
]
PANEL_PAGES = ['Scene', 'Lines', 'Relief', 'Moire', 'Drive', 'Colour']
RESEED = []

PRESETS = full_presets(PAGES, [
    (1, 'wire icosa', {'Scene': 0, 'Solid': 3, 'Rotx': 20.0, 'Spiny': 20.0, 'Glow': 0.4, 'Linewidth': 1.5}),
    (2, 'nested cubes', {'Scene': 0, 'Solid': 1, 'Nest': 4, 'Nestscale': 0.62, 'Spinx': 7.0, 'Spiny': 13.0,
                         'Depthfade': 0.8, 'Glow': 0.3, 'Palette': 2}),
    (3, 'hatch sphere', {'Scene': 1, 'Size': 0.7, 'Hatchdensity': 48.0, 'Crosshatch': True, 'Spiny': 10.0,
                         'Lightaz': 60.0, 'Lightel': 35.0, 'Glow': 0.2}),
    (4, 'relief grid', {'Scene': 2, 'Rows': 56, 'Heightsource': 2, 'Height': 0.25, 'Noisespeed': 0.4, 'Tilt': 62.0,
                        'Size': 0.9, 'Depthfade': 0.5, 'Glow': 0.3, 'Palette': 5}),
    (5, 'person relief', {'Scene': 2, 'Rows': 64, 'Heightsource': 0, 'Height': 0.35, 'Tilt': 55.0, 'Size': 0.9,
                          'Gridwidth': 1.0, 'Glow': 0.3}),
    (6, 'moire planes', {'Scene': 3, 'Spacing': 9.0, 'Moireangle': 1.5, 'Drift': 6.0, 'Linewidth': 2.0,
                         'Glow': 0.0}),
    (7, 'follow solid', {'Scene': 0, 'Solid': 4, 'Follow': 0.8, 'Followrot': 0.6, 'Kick': 25.0, 'Beatgain': 1.0,
                         'Glow': 0.6}),
])

T_ = "(float(op('clock_int')[0]) + parent().par.Phase.eval())"
TOG = "(1.0 if parent().par.{}.eval() else 0.0)"
_LAZ, _LEL = "math.radians(parent().par.Lightaz.eval())", "math.radians(parent().par.Lightel.eval())"


def _rot(axis):
    return "math.radians(parent().par.Rot%s.eval() + parent().par.Spin%s.eval() * %s)" % (axis, axis, T_)


def uniforms():
    return [('uA', [PI.format('Scene'), PI.format('Solid'), P.format('Nest'), P.format('Nestscale')]),
            ('uB', [P.format('Size'), P.format('Dist'), "0.5 / math.tan(math.radians(%s) * 0.5)" % P.format('Fov'),
                    P.format('Follow')]),
            ('uRot', [_rot('x'), _rot('y'), _rot('z'), "math.radians(%s)" % P.format('Kick')]),
            ('uPos', [P.format('Posx'), P.format('Posy'), P.format('Followrot'), PI.format('Followmode')]),
            ('uLn', [P.format('Linewidth'), P.format('Glow'), P.format('Glowwidth'), P.format('Depthfade')]),
            ('uHt', [P.format('Hatchdensity'), "math.radians(%s)" % P.format('Hatchangle'), TOG.format('Crosshatch'),
                     P.format('Hatchcontrast')]),
            ('uLt', ["math.cos(%s) * math.sin(%s)" % (_LEL, _LAZ), "math.sin(%s)" % _LEL,
                     "math.cos(%s) * math.cos(%s)" % (_LEL, _LAZ), TOG.format('Rim')]),
            ('uRl', [P.format('Rows'), P.format('Gridwidth'), "math.radians(%s)" % P.format('Tilt'),
                     P.format('Height')]),
            ('uRl2', [PI.format('Heightsource'), P.format('Noisescale'), "%s * %s" % (P.format('Noisespeed'), T_),
                      TOG.format('Occlude')]),
            ('uMo', [P.format('Spacing'), "math.radians(%s)" % P.format('Moireangle'), P.format('Moirescale'),
                     "%s * %s" % (P.format('Drift'), T_)]),
            ('uMisc', [P.format('Reveal'), TOG.format('Revealinvert'), P.format('Colourspread'), P.format('Seed')])] \
        + DRIVE_UNIFORMS + LOOK_UNIFORMS


def shader_texts():
    return {'fx': glsl_text('gen_interactive_linevolume').replace('// %SOLIDS%', LV['glsl_solids']())}


def build(m, H):
    mk = H['mk']
    in1 = mk(m, inTOP, 'in1')
    pts = H['pts_in'](m)
    msk = H['mask_in'](m)
    clk = _GP['_const_chop'](m, 'clock', [('rate', P.format('Speed'))])
    clk.comment = 'Module clock rate = Speed (integrated by clock_int; Speed 0 = frozen).'
    ci = mk(m, speedCHOP, 'clock_int')
    ci.inputConnectors[0].connect(clk)
    ci.comment = 'Module time s (no jump when Speed changes); uniforms read clock_int + Phase.'
    fx = H['pas'](m, 'fx', shader_texts()['fx'], [in1, pts, msk], IN_W, IN_H, 'useinput', uniforms())
    fx.comment = 'Line volume: wire solids / hatch sphere / relief grid / moire planes, one pass over the slot input.'
    H['out_sel'](m, fx)
    H['pulses'](m, RESEED)
    return [
        {'title': '1 In + clock', 'role': 'input', 'ops': ['in1', 'pts', 'mask', 'clock', 'clock_int', 'pulses']},
        {'title': '2 Line volume', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One analytic pass (no state): Scene menu; points follow, mask raises / reveals, beat kicks.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


def freeze(inst_path, t=1.0):
    """Deterministic picture for a pixel check: module time = t (Speed 0, clock reset, Phase t). Pars only (no TOP
    reads, T-74); read the frozen out1 >= 3 frames later in another exec. unfreeze() puts Speed / Phase back."""
    m = op(inst_path)
    m.store('lv_frozen', {'Speed': m.par.Speed.eval(), 'Phase': m.par.Phase.eval()})
    m.par.Speed = 0
    m.par.Phase = t
    m.op('clock_int').par.resetpulse.pulse()
    return {'frozen': inst_path, 't': t}


def unfreeze(inst_path):
    m = op(inst_path)
    st = m.fetch('lv_frozen', None, search=False) or {}
    for k in ('Speed', 'Phase'):
        if k in st:
            setattr(m.par, k, st[k])
    return {'unfrozen': inst_path}
