# fx_synth_colorize - FX_synth module 'colorize' (FX2 AV-22 Sandin / Paik-Abe colouriser + FX1 DG-22 overflow:
# wrap / fold / solarize). Template: docs/builds/fx_glitch.md "Module template" (rack = builders/fx_synth.py); doc +
# LIVE CHECKS: docs/builds/fx_synth.md. ONE compute pass (builders/glsl/fx_synth_colorize.glsl):
#   source (luma, or R/G/B each into its own channel like Paik-Abe's three cameras) -> per channel
#   f(Gain * x + Phase + Drift * t) with f = sine / triangle / saw / ramp, or Hue mode (luma -> hue at Sat)
#   -> x Drive + Bias -> overflow clip / wrap / fold / solarize (the overdriven video amp).
# Amount 0 = out_sel passes in1 (pass not cooked); the shader's own Amount 0 path is a texelFetch (exact).
# Maths = builders/fx_synth_logic.py colorize(). ASCII only.
import os

MODULE = 'colorize'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
SHADERS = {'fx': 'colorize'}

PAGES = [
    ('Colorize', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'channels', {'names': ['channels', 'hue'], 'labels': ['Per channel (Paik-Abe)',
                                                                               'Hue cycle']}),
        ('Source', 'Menu', 'luma', {'names': ['luma', 'rgb', 'red', 'green', 'blue'],
                                    'labels': ['Luma', 'RGB (each its own)', 'Red', 'Green', 'Blue']}),
        ('Function', 'Menu', 'sine', {'names': ['sine', 'triangle', 'saw', 'ramp'],
                                      'labels': ['Sine', 'Triangle', 'Saw', 'Ramp (linear)']}),
        ('Overflow', 'Menu', 'clip', {'names': ['clip', 'wrap', 'fold', 'solarize'],
                                      'labels': ['Clip', 'Wrap', 'Fold', 'Solarize']}),
        ('Drive', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Drive (amp gain)'}),
        ('Bias', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Bias'}),
        ('Solar', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Solarize threshold'}),
        ('Invert', 'Toggle', False, {'label': 'Invert source'}),
        ('Drift', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Drift (cycles/s)'}),
    ]),
    ('Channels', [
        ('Gainr', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Gain R'}),
        ('Gaing', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Gain G'}),
        ('Gainb', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Gain B'}),
        ('Phaser', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Phase R'}),
        ('Phaseg', 'Float', 0.33, {'min': 0, 'max': 1, 'label': 'Phase G'}),
        ('Phaseb', 'Float', 0.67, {'min': 0, 'max': 1, 'label': 'Phase B'}),
        ('Huegain', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Hue cycles per luma'}),
        ('Huephase', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Hue phase'}),
        ('Sat', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Hue saturation'}),
        ('Valuefollow', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Hue value follows luma'}),
    ]),
]
PANEL_PAGES = ['Colorize', 'Channels']

_Z = {'Mode': 0, 'Source': 0, 'Function': 0, 'Overflow': 0, 'Drive': 1.0, 'Bias': 0.0, 'Solar': 0.5, 'Invert': 0,
      'Drift': 0.0, 'Gainr': 1.0, 'Gaing': 1.0, 'Gainb': 1.0, 'Phaser': 0.0, 'Phaseg': 0.33, 'Phaseb': 0.67,
      'Huegain': 1.0, 'Huephase': 0.0, 'Sat': 1.0, 'Valuefollow': 0.0}
PRESETS = [
    (1, 'paik phase', dict(_Z, Amount=1.0, Gainr=1.5, Gaing=1.5, Gainb=1.5)),
    (2, 'sandin sunset', dict(_Z, Amount=1.0, Function=3, Gainr=2.2, Gaing=1.3, Gainb=0.6, Phaser=0.0,
                              Phaseg=-0.25, Phaseb=-0.1)),
    (3, 'solarize', dict(_Z, Amount=1.0, Source=1, Function=3, Overflow=3, Drive=1.4, Phaseg=0.0, Phaseb=0.0,
                         Solar=0.55)),
    (4, 'neon fold', dict(_Z, Amount=1.0, Function=3, Overflow=2, Gainr=3.0, Gaing=4.0, Gainb=5.0, Phaseg=0.0,
                          Phaseb=0.0)),
    (5, 'acid wrap', dict(_Z, Amount=1.0, Mode=1, Overflow=1, Huegain=3.0, Drift=0.2, Valuefollow=0.3, Drive=1.2)),
]

P = 'parent().par.{}.eval()'
MI = 'parent().par.{}.menuIndex'
TOG = '1 if parent().par.{}.eval() else 0'


def _glsl(stem):
    with open(os.path.join(_HERE, 'glsl', 'fx_synth_%s.glsl' % stem)) as fh:
        return fh.read()


def uniforms(name='fx'):
    """[(uniform, [x, y, z, w expressions])] of the fx pass (names = the shader's declarations; tested offline)."""
    return [
        ('uA', [P.format('Amount'), MI.format('Mode'), MI.format('Source'), MI.format('Function')]),
        ('uB', [MI.format('Overflow'), P.format('Drive'), P.format('Bias'), P.format('Solar')]),
        ('uG', [P.format('Gainr'), P.format('Gaing'), P.format('Gainb'), TOG.format('Invert')]),
        ('uP', [P.format('Phaser'), P.format('Phaseg'), P.format('Phaseb'), P.format('Drift')]),
        ('uH', [P.format('Huegain'), P.format('Huephase'), P.format('Sat'), P.format('Valuefollow')]),
        ('uT', ['absTime.seconds if %s != 0 else 0' % P.format('Drift'), '0', '0', '0']),
    ]


def build(m, H):
    """in1 -> fx (one compute pass, input format) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    g = H['compute'](m, 'fx', _glsl('colorize'), [in1])
    H['uniforms'](g, uniforms())
    g.comment = 'colorize: luma/RGB -> f(gain x + phase) per channel or hue cycle -> drive -> overflow.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(g)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exactly (fx not cooked).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Colorize', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One compute pass: phase colour / hue cycle -> drive -> overflow (clip wrap fold solarize).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
