# fx_synth_keyer - FX_synth module 'keyer' (FX2 AV-24: luma / chroma keys, shape key generator, video logic and
# blend ops). Template: docs/builds/fx_glitch.md "Module template" (rack = builders/fx_synth.py); doc + LIVE CHECKS:
# docs/builds/fx_synth.md. A = in1 (the rack chain), B = a colour or any TOP (Btop, fitted to A). ONE compute pass
# (builders/glsl/fx_synth_keyer.glsl): key A (luma window / chroma CbCr distance / shape: wipe, iris, diamond, box,
# clock with a Position fader / B luma / A alpha / one) optionally combined with key B by logic (and, or, xor,
# a-not-b, multiply, a>b) -> invert -> Op: key (A over B), matte, alpha (A premultiplied by the key), or a blend of A
# and B (add, multiply, min, max, difference, bitwise xor / and / or on 8-bit levels) applied where the key is 1.
# Spill pulls the key colour's chroma out of A. Amount 0 = out_sel passes in1. Maths = fx_synth_logic.keyer(). ASCII.
import os

MODULE = 'keyer'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
SHADERS = {'fx': 'keyer'}
KEYS = ['luma', 'chroma', 'shape', 'bluma', 'alpha', 'one']
KEY_LABELS = ['Luma window', 'Chroma', 'Shape (key generator)', 'B luma', 'A alpha', 'One (whole frame)']
OPS = ['key', 'matte', 'alpha', 'add', 'multiply', 'min', 'max', 'difference', 'xor_bits', 'and_bits', 'or_bits']

PAGES = [
    ('Keyer', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Keya', 'Menu', 'luma', {'names': KEYS, 'labels': KEY_LABELS, 'label': 'Key A'}),
        ('Keyb', 'Menu', 'none', {'names': ['none'] + KEYS, 'labels': ['None'] + KEY_LABELS, 'label': 'Key B'}),
        ('Logic', 'Menu', 'and', {'names': ['a', 'and', 'or', 'xor', 'a_not_b', 'multiply', 'a_gt_b'],
                                  'labels': ['A only', 'A AND B (min)', 'A OR B (max)', 'A XOR B', 'A AND NOT B',
                                             'A x B', 'A > B']}),
        ('Invert', 'Toggle', False, {'label': 'Invert key'}),
        ('Op', 'Menu', 'key', {'names': OPS, 'labels': ['Key (A over B)', 'Matte (show key)', 'Alpha (A x key)',
                                                       'Add', 'Multiply', 'Min', 'Max', 'Difference', 'XOR bits',
                                                       'AND bits', 'OR bits']}),
        ('Bsource', 'Menu', 'colour', {'names': ['colour', 'top'], 'labels': ['Colour', 'TOP (Btop)']}),
        ('Btop', 'Str', '', {'label': 'B TOP path'}),
        ('Br', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'B colour R'}),
        ('Bg', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'B colour G'}),
        ('Bb', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'B colour B'}),
    ]),
    ('Luma', [
        ('Low', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Luma low'}),
        ('High', 'Float', 1.01, {'min': 0, 'max': 1.01, 'label': 'Luma high (> 1 = none)'}),
        ('Soft', 'Float', 0.05, {'min': 0, 'max': 0.5, 'label': 'Softness'}),
    ]),
    ('Chroma', [
        ('Chromar', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Key colour R'}),
        ('Chromag', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Key colour G'}),
        ('Chromab', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Key colour B'}),
        ('Tolerance', 'Float', 0.15, {'min': 0, 'max': 0.6, 'label': 'Tolerance (CbCr)'}),
        ('Chromasoft', 'Float', 0.1, {'min': 0, 'max': 0.5, 'label': 'Chroma softness'}),
        ('Spill', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Spill suppress'}),
    ]),
    ('Shape', [
        ('Shape', 'Menu', 'circle', {'names': ['hwipe', 'vwipe', 'circle', 'diamond', 'rect', 'clock'],
                                     'labels': ['H wipe', 'V wipe', 'Iris (circle)', 'Diamond', 'Box', 'Clock']}),
        ('Position', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Position (fader)'}),
        ('Shapesoft', 'Float', 0.05, {'min': 0, 'max': 0.5, 'label': 'Edge softness'}),
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre x'}),
        ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre y'}),
        ('Angle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Angle deg'}),
    ]),
]
PANEL_PAGES = ['Keyer', 'Luma', 'Chroma', 'Shape']

_Z = {'Keya': 0, 'Keyb': 0, 'Logic': 1, 'Invert': 0, 'Op': 0, 'Bsource': 0, 'Br': 0.0, 'Bg': 0.0, 'Bb': 0.0,
      'Low': 0.5, 'High': 1.01, 'Soft': 0.05, 'Chromar': 0.0, 'Chromag': 1.0, 'Chromab': 0.0, 'Tolerance': 0.15,
      'Chromasoft': 0.1, 'Spill': 0.0, 'Shape': 2, 'Position': 0.5, 'Shapesoft': 0.05, 'Centerx': 0.5,
      'Centery': 0.5, 'Angle': 0.0}
PRESETS = [
    (1, 'luma over colour', dict(_Z, Amount=1.0, Low=0.45, Soft=0.1, Br=0.23, Bg=0.07, Bb=0.18)),
    (2, 'green screen', dict(_Z, Amount=1.0, Keya=1, Tolerance=0.12, Chromasoft=0.08, Spill=0.6)),
    (3, 'iris', dict(_Z, Amount=1.0, Keya=2, Shape=2, Position=0.45, Shapesoft=0.02)),
    (4, 'xor logic', dict(_Z, Amount=1.0, Keya=5, Op=8, Br=0.5, Bg=0.25, Bb=0.75)),
    (5, 'window x diamond', dict(_Z, Amount=1.0, Keya=0, Keyb=3, Logic=3, Low=0.3, High=0.7, Shape=3,
                                 Position=0.6, Op=7, Br=1.0, Bg=0.72, Bb=0.0)),
]

P = 'parent().par.{}.eval()'
MI = 'parent().par.{}.menuIndex'
TOG = '1 if parent().par.{}.eval() else 0'


def _glsl(stem):
    with open(os.path.join(_HERE, 'glsl', 'fx_synth_%s.glsl' % stem)) as fh:
        return fh.read()


def uniforms(name='fx'):
    return [
        ('uA', [P.format('Amount'), MI.format('Keya'), MI.format('Keyb'), MI.format('Logic')]),
        ('uB', [TOG.format('Invert'), MI.format('Op'), MI.format('Bsource'), P.format('Spill')]),
        ('uC', [P.format('Low'), P.format('High'), P.format('Soft'), '0']),
        ('uD', [P.format('Chromar'), P.format('Chromag'), P.format('Chromab'), P.format('Tolerance')]),
        ('uE', [P.format('Chromasoft'), MI.format('Shape'), P.format('Position'), P.format('Shapesoft')]),
        ('uF', [P.format('Centerx'), P.format('Centery'), P.format('Angle'), '0']),
        ('uG', [P.format('Br'), P.format('Bg'), P.format('Bb'), '0']),
    ]


def build(m, H):
    """in1 (A) + b_sel (Btop or A) -> b_fit (to A's size) -> fx (one pass) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    bs = mk(m, selectTOP, 'b_sel')
    expr(bs.par.top, "parent().par.Btop.eval() or 'in1'")
    bs.comment = 'B = any TOP path (Btop); empty = A itself. Only read while Bsource = TOP.'
    # Transform TOP, not Fit TOP: the Fit TOP blends its frame edge with bgcolor (live 31550: a 540x960 ramp fitted to
    # 1080x1920 had its border rows/columns at 0.75 x); Transform extend hold + fill outside is exact to 1/2 texel.
    bf = mk(m, transformTOP, 'b_fit')
    bf.inputConnectors[0].connect(bs)
    bf.par.outputresolution = 'custom'
    expr(bf.par.resolutionw, "op('in1').width")
    expr(bf.par.resolutionh, "op('in1').height")
    bf.par.outputaspect = 'resolution'
    bf.par.fillmode = 'outside'
    bf.par.extend = 'hold'
    bf.comment = 'B filled to A (in1) size (fill outside, edge held): one pixel grid.'
    g = H['compute'](m, 'fx', _glsl('keyer'), [in1, bf])
    H['uniforms'](g, uniforms())
    g.comment = 'keyer: keys (luma, chroma, shape, B luma, alpha) -> logic -> key / matte / alpha / blend op.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(g)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exactly (fx not cooked).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 A + B', 'role': 'input', 'ops': ['in1', 'b_sel', 'b_fit'],
         'body': 'A = in1 (rack chain), B = Btop (or A) fitted to A; B colour lives in the shader.'},
        {'title': '2 Keyer', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One compute pass: keys -> logic -> op.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
