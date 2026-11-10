# gen_interactive_parallax - GEN_interactive module 'parallax' (FX7a SX-30 depth-parallax "3D photo" / relief mapping,
# FX7c 7C-31 2.5D photo animator, FX7b TC-05 depth-banded colour layers; plan: "depth precomputed per still"). Lane F,
# 27 Oct 2026. A still (or the slot input) + its depth map -> a camera sway (circle / line / figure 8, or following the
# rack's points, a dolly) with correct occlusion (relief march, nearer layers first), fog by depth, depth bands.
# Depth of a still: precomputed once outside TD with the Depth Anything helper (helpers/vision_bridge kind 1,
# depth_socket_test.py; the demo pair is media/demo/parallax/, SOURCES.md there) or any depth TOP (DC_depth_cam).
# Network: in1, still (Movie File In, filled to in1) -> colsel; depth file / Depthtop -> depsel; clock -> clock_int
# (module time); fx (in1, colsel, depsel) -> out_sel (Amount 0 = in1) -> out1. Shader builders/glsl/
# gen_interactive_parallax.glsl; reference builders/gen_interactive_parallax_logic.py. No limits. ASCII only.

MODULE = 'parallax'
SWAYS = ['off', 'circle', 'horizontal', 'vertical', 'figure8']
DEMO = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/demo/parallax/'

PAGES = [
    ('Parallax', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Colorsource', 'Menu', 'still', {'names': ['still', 'input'], 'labels': ['Still file', 'Slot input (in1)']}),
        ('Still', 'Str', DEMO + 'webcam_f0.png', {'label': 'Still file'}),
        ('Depthsource', 'Menu', 'file', {'names': ['file', 'top'], 'labels': ['Depth file', 'Depth TOP']}),
        ('Depthfile', 'Str', DEMO + 'webcam_f0_depth.png', {'label': 'Depth file (white = near)'}),
        ('Depthtop', 'TOP', '', {'label': 'Depth TOP (r, e.g. DC_depth_cam/out1)'}),
        ('Depthlo', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Depth black point'}),
        ('Depthhi', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Depth white point'}),
        ('Depthinvert', 'Toggle', False, {'label': 'Invert depth (white = far)'}),
    ]),
    ('Camera', [
        ('Strength', 'Float', 0.035, {'min': 0, 'max': 0.3, 'label': 'Parallax strength (frame share)'}),
        ('Swaymode', 'Menu', 'circle', {'names': SWAYS, 'labels': ['Off', 'Circle', 'Side to side', 'Up and down',
                                                                  'Figure 8']}),
        ('Swayhz', 'Float', 0.08, {'min': 0, 'max': 2, 'label': 'Sway cycles / s'}),
        ('Swayx', 'Float', 1.0, {'min': -2, 'max': 2, 'label': 'Sway x'}),
        ('Swayy', 'Float', 0.6, {'min': -2, 'max': 2, 'label': 'Sway y'}),
        ('Follow', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Follow the first rack point'}),
        ('Dolly', 'Float', 0.0, {'min': -0.5, 'max': 0.5, 'label': 'Dolly (zoom by depth)'}),
        ('Dollyamp', 'Float', 0.0, {'min': 0, 'max': 0.5, 'label': 'Dolly sway'}),
        ('Phase', 'Float', 0.0, {'min': 0, 'max': 100, 'label': 'Time offset s'}),
        ('Steps', 'Int', 32, {'min': 1, 'max': 256, 'label': 'March steps (quality)'}),
        ('Refine', 'Int', 5, {'min': 0, 'max': 16, 'label': 'Refine steps'}),
    ]),
    ('Look', [
        ('Bands', 'Int', 0, {'min': 0, 'max': 32, 'label': 'Depth bands (0 off)'}),
        ('Bandmix', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Band colour mix'}),
        ('Fog', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Fog by depth (to Colour A)'}),
    ]),
    drive_page(),
    STATE_PAGE_GI,
    colour_page('neon', 'replace', (0.02, 0.03, 0.08), (1.0, 0.85, 0.4)),
]
PANEL_PAGES = ['Parallax', 'Camera', 'Look', 'Drive', 'Colour']
RESEED = []

PRESETS = full_presets(PAGES, [
    (1, 'slow orbit', {}),
    (2, 'side drift', {'Swaymode': 2, 'Swayhz': 0.05, 'Strength': 0.05, 'Fog': 0.35}),
    (3, 'dolly breathe', {'Swaymode': 0, 'Dollyamp': 0.08, 'Swayhz': 0.1, 'Strength': 0.0, 'Fog': 0.2}),
    (4, 'depth bands', {'Bands': 6, 'Bandmix': 0.8, 'Palette': 4, 'Swaymode': 4, 'Swayhz': 0.06}),
    (5, 'follow person', {'Swaymode': 0, 'Follow': 1.0, 'Strength': 0.05}),
    (6, 'stained glass', {'Bands': 10, 'Bandmix': 0.55, 'Palette': 3, 'Fog': 0.5, 'Strength': 0.025}),
])

T_ = "(float(op('clock_int')[0]) + parent().par.Phase.eval())"
W_ = "2 * math.pi * parent().par.Swayhz.eval() * %s" % T_
SX = "[0.0, math.sin(%s), math.sin(%s), 0.0, math.sin(%s)][parent().par.Swaymode.menuIndex]" % (W_, W_, W_)
SY = "[0.0, math.cos(%s), 0.0, math.sin(%s), 0.5 * math.sin(2 * %s)][parent().par.Swaymode.menuIndex]" % (W_, W_, W_)
FOL = "(lambda v: (v - 0.5) * 2 if v > -1 else 0.0)(float(%s['%s'][0]) if %s is not None else -10.0)"
PTS_OP = "parent(2).op('pts')"
GAIN = "(%s * (1.0 + parent().par.Audiogain.eval() * float(%s['level'])))" % (P.format('Strength'), D_OP)


def offset_exprs():
    """(ox, oy) uv offset expressions: Strength x (1 + Audiogain level) x (sway + Follow x first point + Manual)."""
    fx = FOL % (PTS_OP, 'x', PTS_OP)
    fy = FOL % (PTS_OP, 'y', PTS_OP)
    ox = "%s * (parent().par.Swayx.eval() * %s + parent().par.Follow.eval() * %s + parent().par.Manual.eval())" % (
        GAIN, SX, fx)
    oy = "%s * (parent().par.Swayy.eval() * %s + parent().par.Follow.eval() * %s)" % (GAIN, SY, fy)
    return ox, oy


def uniforms():
    ox, oy = offset_exprs()
    dolly = "parent().par.Dolly.eval() + parent().par.Dollyamp.eval() * math.sin(%s)" % W_
    return [('uO', [ox, oy, dolly, P.format('Steps')]),
            ('uQ', [P.format('Refine'), P.format('Depthlo'), P.format('Depthhi'),
                    "(1.0 if parent().par.Depthinvert.eval() else 0.0)"]),
            ('uB', [P.format('Bands'), P.format('Bandmix'), P.format('Fog'), '0'])] + LOOK_UNIFORMS


def shader_texts():
    return {'fx': glsl_text('gen_interactive_parallax')}


def _fit(m, H, name, file_par, comment):
    mk = H['mk']
    f = mk(m, moviefileinTOP, name)
    H['expr'](f.par.file, "parent().par.%s.eval()" % file_par)
    f.par.outputresolution = 'custom'
    H['expr'](f.par.resolutionw, IN_W)
    H['expr'](f.par.resolutionh, IN_H)
    f.par.outputaspect = 'resolution'
    f.par.fillmode = 'fill'
    f.comment = comment
    return f


def build(m, H):
    mk = H['mk']
    in1 = mk(m, inTOP, 'in1')
    st = _fit(m, H, 'still', 'Still', 'The still, filled to the slot size (cooks only while Colorsource = still).')
    cs = mk(m, switchTOP, 'colsel')
    cs.inputConnectors[0].connect(st)
    cs.inputConnectors[1].connect(in1)
    H['expr'](cs.par.index, "0 if parent().par.Colorsource.eval() == 'still' else 1")
    cs.comment = 'Colour: the still or the slot input.'
    df = _fit(m, H, 'depthfile', 'Depthfile', 'Depth of the still (white = near), filled like the still.')
    dt = mk(m, selectTOP, 'depthtop')
    H['expr'](dt.par.top, "parent().par.Depthtop.eval() or 'depthfile'")
    dt.comment = 'Depth TOP (Depthtop), or the depth file while empty.'
    ds = mk(m, switchTOP, 'depsel')
    ds.inputConnectors[0].connect(df)
    ds.inputConnectors[1].connect(dt)
    H['expr'](ds.par.index, "0 if parent().par.Depthsource.eval() == 'file' else 1")
    ds.comment = 'Depth: file or TOP.'
    clk = _GP['_const_chop'](m, 'clock', [('rate', P.format('Speed'))])
    clk.comment = 'Module clock rate = Speed (integrated by clock_int; Speed 0 = frozen).'
    ci = mk(m, speedCHOP, 'clock_int')
    ci.inputConnectors[0].connect(clk)
    ci.comment = 'Module time s; the sway reads clock_int + Phase.'
    fx = H['pas'](m, 'fx', shader_texts()['fx'], [in1, cs, ds], IN_W, IN_H, 'useinput', uniforms())
    fx.comment = 'Relief march (nearer layers first), fog, depth bands; offset from sway / points / Manual.'
    H['out_sel'](m, fx)
    H['pulses'](m, RESEED)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'still', 'colsel', 'depthfile', 'depthtop', 'depsel',
                                                    'clock', 'clock_int', 'pulses']},
        {'title': '2 Parallax', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One pass: relief march over the depth (2.5D photo), fog, depth bands.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


def freeze(inst_path, t=1.0):
    """Module time = t (Speed 0, clock reset, Phase t). Pars only; read >= 3 frames later in another exec."""
    m = op(inst_path)
    m.store('px_frozen', {'Speed': m.par.Speed.eval(), 'Phase': m.par.Phase.eval()})
    m.par.Speed = 0
    m.par.Phase = t
    m.op('clock_int').par.resetpulse.pulse()
    return {'frozen': inst_path, 't': t}
