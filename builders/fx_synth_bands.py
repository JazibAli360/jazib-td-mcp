# fx_synth_bands - FX_synth module 'bands' (FX2 AV-23 amplitude classifier + FX5 G24 contour / topographic lines).
# Template: docs/builds/fx_glitch.md "Module template" (rack = builders/fx_synth.py); doc + LIVE CHECKS:
# docs/builds/fx_synth.md. ONE compute pass (builders/glsl/fx_synth_bands.glsl): signal (luma / R / G / B, ^ Curve)
# x Bands + phase (Offset + Speed t + Wobble sin) -> band index -> fill (source posterised / grey / rainbow /
# duotone, Softness blends across edges) over source or black -> contour lines of constant pixel width at every
# threshold (distance / |gradient|), every Major-th line Majorwidth x wider. Amount 0 = out_sel passes in1.
# Maths = builders/fx_synth_logic.py bands(). ASCII only.
import os

MODULE = 'bands'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
SHADERS = {'fx': 'bands'}

PAGES = [
    ('Bands', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Source', 'Menu', 'luma', {'names': ['luma', 'red', 'green', 'blue'],
                                    'labels': ['Luma', 'Red', 'Green', 'Blue']}),
        ('Bands', 'Int', 8, {'min': 2, 'max': 32, 'label': 'Bands'}),
        ('Curve', 'Float', 1.0, {'min': 0.25, 'max': 4, 'label': 'Curve (gamma before banding)'}),
        ('Offset', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Offset (bands)'}),
        ('Speed', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Flow (bands/s)'}),
        ('Wobble', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Wobble (bands)'}),
        ('Wobblerate', 'Float', 0.5, {'min': 0, 'max': 4, 'label': 'Wobble rate Hz'}),
        ('Softness', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Band edge softness'}),
        ('Fill', 'Menu', 'rainbow', {'names': ['source', 'grey', 'rainbow', 'duotone'],
                                     'labels': ['Source (posterise)', 'Grey levels', 'Rainbow', 'Duotone A -> B']}),
        ('Fillamt', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Fill amount'}),
        ('Background', 'Menu', 'source', {'names': ['source', 'black'], 'labels': ['Source', 'Black']}),
    ]),
    ('Lines', [
        ('Linewidth', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Contour width px (0 = off)'}),
        ('Lineopacity', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Contour opacity'}),
        ('Major', 'Int', 0, {'min': 0, 'max': 10, 'label': 'Major line every N (0 = off)'}),
        ('Majorwidth', 'Float', 2.0, {'min': 1, 'max': 4, 'label': 'Major width x'}),
        ('Liner', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Line R'}),
        ('Lineg', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Line G'}),
        ('Lineb', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Line B'}),
    ]),
    ('Colours', [
        ('Huespan', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Rainbow hue span'}),
        ('Hueoffset', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Rainbow hue offset'}),
        ('Colorar', 'Float', 0.1, {'min': 0, 'max': 1, 'label': 'Duotone A R'}),
        ('Colorag', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Duotone A G'}),
        ('Colorab', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Duotone A B'}),
        ('Colorbr', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Duotone B R'}),
        ('Colorbg', 'Float', 0.75, {'min': 0, 'max': 1, 'label': 'Duotone B G'}),
        ('Colorbb', 'Float', 0.1, {'min': 0, 'max': 1, 'label': 'Duotone B B'}),
    ]),
]
PANEL_PAGES = ['Bands', 'Lines', 'Colours']

_Z = {'Source': 0, 'Bands': 8, 'Curve': 1.0, 'Offset': 0.0, 'Speed': 0.0, 'Wobble': 0.0, 'Wobblerate': 0.5,
      'Softness': 0.0, 'Fill': 2, 'Fillamt': 1.0, 'Background': 0, 'Linewidth': 0.0, 'Lineopacity': 1.0, 'Major': 0,
      'Majorwidth': 2.0, 'Liner': 1.0, 'Lineg': 1.0, 'Lineb': 1.0, 'Huespan': 1.0, 'Hueoffset': 0.0}
PRESETS = [
    (1, 'classifier', dict(_Z, Amount=1.0, Bands=8, Fill=2, Huespan=0.8)),
    (2, 'topo', dict(_Z, Amount=1.0, Bands=16, Fill=0, Fillamt=0.0, Linewidth=1.2, Major=5, Majorwidth=2.5,
                     Speed=0.2, Lineopacity=0.85)),
    (3, 'posterise', dict(_Z, Amount=1.0, Bands=6, Fill=0, Softness=0.15)),
    (4, 'neon contour', dict(_Z, Amount=1.0, Bands=24, Fillamt=0.0, Background=1, Linewidth=1.5, Speed=0.5,
                             Liner=0.1, Lineg=1.0, Lineb=0.9)),
    (5, 'duotone flow', dict(_Z, Amount=1.0, Bands=10, Fill=3, Softness=0.3, Speed=-0.3, Wobble=0.5)),
]

P = 'parent().par.{}.eval()'
MI = 'parent().par.{}.menuIndex'


def _glsl(stem):
    with open(os.path.join(_HERE, 'glsl', 'fx_synth_%s.glsl' % stem)) as fh:
        return fh.read()


def uniforms(name='fx'):
    moving = '({} != 0 or {} != 0)'.format(P.format('Speed'), P.format('Wobble'))
    return [
        ('uA', [P.format('Amount'), MI.format('Source'), P.format('Bands'), P.format('Curve')]),
        ('uB', [P.format('Offset'), P.format('Speed'), P.format('Wobble'), P.format('Wobblerate')]),
        ('uC', [P.format('Softness'), MI.format('Fill'), P.format('Fillamt'), MI.format('Background')]),
        ('uD', [P.format('Linewidth'), P.format('Lineopacity'), P.format('Major'), P.format('Majorwidth')]),
        ('uE', [P.format('Liner'), P.format('Lineg'), P.format('Lineb'), P.format('Huespan')]),
        ('uF', [P.format('Colorar'), P.format('Colorag'), P.format('Colorab'), P.format('Hueoffset')]),
        ('uG', [P.format('Colorbr'), P.format('Colorbg'), P.format('Colorbb'),
                'absTime.seconds if %s else 0' % moving]),
    ]


def build(m, H):
    """in1 -> fx (one compute pass, input format) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    g = H['compute'](m, 'fx', _glsl('bands'), [in1])
    H['uniforms'](g, uniforms())
    g.comment = 'bands: amplitude classifier (iso-level bands + fill) + constant-width contour lines.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(g)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exactly (fx not cooked).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Bands', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One compute pass: bands x fill, softness, flowing thresholds, contour lines.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
