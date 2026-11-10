# fx_synth_vfeedback - FX_synth module 'vfeedback' (FX2 AV-28: camera pointed at its own monitor; Crutchfield,
# "Space-time dynamics in video feedback"). Template: docs/builds/fx_glitch.md "Module template" (rack =
# builders/fx_synth.py); doc + LIVE CHECKS: docs/builds/fx_synth.md. Different from FX_glitch feedbackkill (generation
# LOSS): this is the studio loop look - lens (zoom / rotate / shift / barrel, in-loop mirror), camera (blur, gain,
# gamma, contrast, hue step, saturation), monitor (RGB stripe mask in the loop = moire), autogain, live picture keyed
# in (mix / luma above / luma below, Inject + Kick for beats), 0-3 cooks of camera-monitor delay.
# Network: in1 -> fb (Feedback of loop, or of the delay Cache TOP when Delay > 0) -> stamp (1x1 clock + mean luma)
#   -> loop (compute, 16f state) -> [delay (Cache TOP)] ; mix (compute: Amount, input format) -> out_sel -> out1.
# Amount 0 = out_sel passes in1 (nothing cooks). Maths = builders/fx_synth_logic.py vf_*. ASCII only.
import os

MODULE = 'vfeedback'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
SHADERS = {'stamp': 'stamp', 'loop': 'vf_loop', 'mix': 'mix'}

PAGES = [
    ('Loop', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Inject', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Inject (live into the loop)'}),
        ('Keymode', 'Menu', 'mix', {'names': ['mix', 'luma_above', 'luma_below'],
                                    'labels': ['Mix (whole picture)', 'Luma above Key', 'Luma below Key']}),
        ('Key', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Key'}),
        ('Keysoft', 'Float', 0.1, {'min': 0, 'max': 0.5, 'label': 'Key softness'}),
        ('Kick', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Kick (bind a beat: extra inject)'}),
        ('Gain', 'Float', 1.0, {'min': 0.8, 'max': 1.3, 'label': 'Camera gain per generation'}),
        ('Delay', 'Int', 0, {'min': 0, 'max': 3, 'label': 'Loop delay (cooks)'}),
        ('Reset', 'Toggle', False, {'label': 'Reset (loop = live)'}),
    ]),
    ('Lens', [
        ('Zoom', 'Float', 1.03, {'min': 0.9, 'max': 1.1, 'label': 'Zoom per generation'}),
        ('Rotate', 'Float', 2.0, {'min': -10, 'max': 10, 'label': 'Rotate deg per generation'}),
        ('Shiftx', 'Float', 0.0, {'min': -8, 'max': 8, 'label': 'Shift x px'}),
        ('Shifty', 'Float', 0.0, {'min': -8, 'max': 8, 'label': 'Shift y px'}),
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre x'}),
        ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre y'}),
        ('Barrel', 'Float', 0.0, {'min': -0.2, 'max': 0.2, 'label': 'Lens barrel K'}),
        ('Mirror', 'Menu', 'none', {'names': ['none', 'x', 'y', 'quad'],
                                    'labels': ['None', 'Mirror X', 'Mirror Y', 'Quad']}),
        ('Edge', 'Menu', 'black', {'names': ['black', 'mirror', 'repeat', 'clamp'],
                                   'labels': ['Black (monitor border)', 'Mirror', 'Repeat', 'Clamp']}),
    ]),
    ('Camera', [
        ('Blur', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Camera blur'}),
        ('Radius', 'Float', 1.5, {'min': 0.5, 'max': 6, 'label': 'Blur radius px'}),
        ('Gamma', 'Float', 1.0, {'min': 0.5, 'max': 2, 'label': 'Gamma per generation'}),
        ('Contrast', 'Float', 1.05, {'min': 0.8, 'max': 1.3, 'label': 'Contrast per generation'}),
        ('Huestep', 'Float', 3.0, {'min': -30, 'max': 30, 'label': 'Hue deg per generation'}),
        ('Saturation', 'Float', 1.0, {'min': 0, 'max': 1.5, 'label': 'Saturation per generation'}),
        ('Mask', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Monitor RGB mask in loop'}),
        ('Maskpitch', 'Float', 3.0, {'min': 1, 'max': 12, 'label': 'Mask stripe px'}),
        ('Noise', 'Float', 0.0, {'min': 0, 'max': 0.1, 'label': 'Noise'}),
        ('Autogain', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Autogain (stabiliser)'}),
        ('Target', 'Float', 0.4, {'min': 0.05, 'max': 0.95, 'label': 'Autogain target mean'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 99, 'label': 'Seed'}),
    ]),
]
PANEL_PAGES = ['Loop', 'Lens', 'Camera']

_Z = {'Inject': 0.15, 'Keymode': 0, 'Key': 0.5, 'Keysoft': 0.1, 'Kick': 0.0, 'Gain': 1.0, 'Delay': 0, 'Reset': 0,
      'Zoom': 1.03, 'Rotate': 2.0, 'Shiftx': 0.0, 'Shifty': 0.0, 'Centerx': 0.5, 'Centery': 0.5, 'Barrel': 0.0,
      'Mirror': 0, 'Edge': 0, 'Blur': 0.3, 'Radius': 1.5, 'Gamma': 1.0, 'Contrast': 1.05, 'Huestep': 3.0,
      'Saturation': 1.0, 'Mask': 0.0, 'Maskpitch': 3.0, 'Noise': 0.0, 'Autogain': 0.4, 'Target': 0.4, 'Seed': 1}
PRESETS = [
    (1, 'crutchfield spiral', dict(_Z, Amount=1.0, Zoom=1.04, Rotate=3.0, Huestep=4.0, Inject=0.1, Autogain=0.5,
                                   Contrast=1.08)),
    (2, 'infinite hall', dict(_Z, Amount=1.0, Zoom=0.96, Rotate=0.0, Keymode=1, Key=0.4, Inject=0.8, Huestep=1.0,
                              Blur=0.15, Autogain=0.2)),
    (3, 'cells', dict(_Z, Amount=1.0, Zoom=1.0, Rotate=0.0, Contrast=1.25, Blur=0.7, Gamma=1.1, Barrel=0.08,
                      Mirror=3, Noise=0.01, Inject=0.05, Huestep=1.5, Edge=1)),
    (4, 'flame', dict(_Z, Amount=1.0, Zoom=1.01, Rotate=0.0, Shifty=3.0, Huestep=-2.0, Blur=0.5, Gain=1.02,
                      Keymode=1, Key=0.55, Inject=0.9, Autogain=0.3)),
    (5, 'kaleido moire', dict(_Z, Amount=1.0, Mirror=3, Rotate=5.0, Zoom=1.02, Huestep=6.0, Mask=0.5,
                              Maskpitch=3.0, Inject=0.12)),
]

P = 'parent().par.{}.eval()'
MI = 'parent().par.{}.menuIndex'
TOG = '1 if parent().par.{}.eval() else 0'


def _glsl(stem):
    with open(os.path.join(_HERE, 'glsl', 'fx_synth_%s.glsl' % stem)) as fh:
        return fh.read()


def uniforms(name):
    if name == 'stamp':
        return [('uT', ['absTime.seconds', '0', '0', '0'])]
    if name == 'mix':
        return [('uA', [P.format('Amount'), '0', '0', '0'])]
    return [
        ('uA', [P.format('Inject'), MI.format('Keymode'), P.format('Key'), P.format('Keysoft')]),
        ('uB', [P.format('Kick'), P.format('Gain'), TOG.format('Reset'), P.format('Seed')]),
        ('uC', [P.format('Zoom'), P.format('Rotate'), P.format('Shiftx'), P.format('Shifty')]),
        ('uD', [P.format('Centerx'), P.format('Centery'), P.format('Barrel'), MI.format('Mirror')]),
        ('uE', [MI.format('Edge'), P.format('Blur'), P.format('Radius'), P.format('Gamma')]),
        ('uF', [P.format('Contrast'), P.format('Huestep'), P.format('Saturation'), P.format('Mask')]),
        ('uG', [P.format('Maskpitch'), P.format('Noise'), P.format('Autogain'), P.format('Target')]),
        ('uH', ['absTime.frame', '0', '0', '0']),
    ]


def build(m, H):
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    fb = mk(m, feedbackTOP, 'fb')
    fb.inputConnectors[0].connect(in1)
    st = H['compute'](m, 'stamp', _glsl('stamp'), [fb], res=(1, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    st.par.autodispatchsize = False
    st.par.dispatchsizex, st.par.dispatchsizey, st.par.dispatchsizez = 1, 1, 1
    H['uniforms'](st, uniforms('stamp'))
    st.comment = 'Cook clock + mean luma of the previous state (Autogain); gap > 0.25 s = restart from live.'
    lp = H['compute'](m, 'loop', _glsl('vf_loop'), [in1, fb, st], fmt='rgba16float')
    lp.par.inputextenduv = 'hold'
    H['uniforms'](lp, uniforms('loop'))
    lp.comment = 'One camera-at-monitor generation per cook: lens, camera, monitor mask, autogain, key in live.'
    dl = mk(m, cacheTOP, 'delay')
    dl.inputConnectors[0].connect(lp)
    if getattr(dl.par, 'cachesize', None) is not None:
        dl.par.cachesize = 4
    if getattr(dl.par, 'outputindex', None) is not None:
        expr(dl.par.outputindex, '-int(%s)' % P.format('Delay'))
    if getattr(dl.par, 'active', None) is not None:
        expr(dl.par.active, '%s > 0' % P.format('Delay'))
    dl.comment = 'Camera -> monitor latency: the loop reads Delay cooks back (only active while Delay > 0).'
    expr(fb.par.top, "'delay' if %s > 0 else 'loop'" % P.format('Delay'))
    fb.comment = 'Previous state (loop, or delay when Delay > 0).'
    mx = H['compute'](m, 'mix', _glsl('mix'), [in1, lp])
    H['uniforms'](mx, uniforms('mix'))
    mx.comment = 'Amount mix in the input format (Amount 0 = exact in1); the loop keeps running.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(mx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exactly (nothing cooks).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Loop', 'role': 'process',
         'ops': ['fb', 'stamp', 'stamp_compute', 'loop', 'loop_compute', 'delay'],
         'body': 'fb -> stamp (clock + mean) -> loop (one generation, 16f) -> delay (Cache, optional) -> fb.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['mix', 'mix_compute', 'out_sel', 'out1']},
    ]
