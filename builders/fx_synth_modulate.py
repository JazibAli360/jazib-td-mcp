# fx_synth_modulate - FX_synth module 'modulate' (FX7a SX-12: the Hydra modulate bank, 9 modes; maths re-written,
# hydra-synth is AGPL and was read for its function list only). Template: docs/builds/fx_glitch.md "Module template"
# (rack = builders/fx_synth.py); doc + LIVE CHECKS: docs/builds/fx_synth.md. ONE compute pass
# (builders/glsl/fx_synth_modulate.glsl): B (the modulator) is read at the same uv and bends where A is read:
# modulate (displace), scale, rotate, hue, pixelate, repeat, kaleid, scroll x / y. B = A itself (Hydra's
# src(o0).modulate(o0)), any TOP (Btop), or the built-in moving noise. Chain it before / after vfeedback in the rack
# for the feedback tunnels. Amount 0 = out_sel passes in1 (pass not cooked). Maths = fx_synth_logic.modulate(). ASCII.
import os

MODULE = 'modulate'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
SHADERS = {'fx': 'modulate'}
MODES = ['modulate', 'scale', 'rotate', 'hue', 'pixelate', 'repeat', 'kaleid', 'scrollx', 'scrolly']
MODE_LABELS = ['Modulate (displace by B.rg)', 'Scale (zoom by B.r)', 'Rotate (twist by B.r)', 'Hue (shift by B chroma)',
               'Pixelate (cells by B.rg)', 'Repeat (tiles shifted by B)', 'Kaleid (fold, radius by B.r)',
               'Scroll x (slide by B.r)', 'Scroll y (lift by B.r)']
WRAPS = ['repeat', 'mirror', 'hold', 'transparent']
BSOURCES = ['self', 'top', 'noise']

PAGES = [
    ('Modulate', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'modulate', {'names': MODES, 'labels': MODE_LABELS}),
        ('Multiple', 'Float', 0.1, {'min': -2, 'max': 2, 'label': 'Multiple (how much B moves it)'}),
        ('Offset', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Offset (B centre / base scale, angle, cells)'}),
        ('Repeatx', 'Float', 3.0, {'min': 1, 'max': 20, 'label': 'Repeat x (repeat)'}),
        ('Repeaty', 'Float', 3.0, {'min': 1, 'max': 20, 'label': 'Repeat y (repeat)'}),
        ('Sides', 'Float', 4.0, {'min': 1, 'max': 16, 'label': 'Sides (kaleid)'}),
        ('Speed', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Scroll speed /s (scroll)'}),
        ('Wrap', 'Menu', 'repeat', {'names': WRAPS, 'labels': ['Repeat (Hydra)', 'Mirror', 'Hold edge',
                                                              'Transparent']}),
    ]),
    ('Modulator', [
        ('Bsource', 'Menu', 'self', {'names': BSOURCES, 'labels': ['A itself (in1)', 'TOP (Btop)', 'Noise (built-in)']}),
        ('Btop', 'TOP', '', {'label': 'B TOP'}),
        ('Noisescale', 'Float', 1.0, {'min': 0.05, 'max': 8, 'label': 'Noise period'}),
        ('Noisespeed', 'Float', 0.2, {'min': -4, 'max': 4, 'label': 'Noise speed /s'}),
    ]),
]
PANEL_PAGES = ['Modulate', 'Modulator']

_Z = {'Mode': 0, 'Multiple': 0.1, 'Offset': 0.0, 'Repeatx': 3.0, 'Repeaty': 3.0, 'Sides': 4.0, 'Speed': 0.0, 'Wrap': 0,
      'Bsource': 0, 'Noisescale': 1.0, 'Noisespeed': 0.2}
PRESETS = [
    (1, 'self warp', dict(_Z, Amount=1.0, Mode=0, Multiple=0.08, Offset=0.5, Wrap=1)),
    (2, 'noise ripple', dict(_Z, Amount=1.0, Mode=0, Multiple=0.06, Offset=0.5, Bsource=2, Noisescale=0.6,
                             Noisespeed=0.3, Wrap=1)),
    (3, 'luma twist', dict(_Z, Amount=1.0, Mode=2, Multiple=1.2, Offset=-0.6, Wrap=1)),
    (4, 'pixel bloom', dict(_Z, Amount=1.0, Mode=4, Multiple=60.0, Offset=8.0, Bsource=2, Noisescale=1.5)),
    (5, 'kaleid breath', dict(_Z, Amount=1.0, Mode=6, Multiple=0.5, Sides=6.0, Bsource=2, Noisespeed=0.5, Wrap=1)),
]

P = 'parent().par.{}.eval()'
MI = 'parent().par.{}.menuIndex'


def _glsl(stem):
    with open(os.path.join(_HERE, 'glsl', 'fx_synth_%s.glsl' % stem)) as fh:
        return fh.read()


def uniforms(name='fx'):
    """[(uniform, [x, y, z, w expressions])] of the fx pass (names = the shader's declarations; tested offline)."""
    return [
        ('uA', [P.format('Amount'), MI.format('Mode'), P.format('Multiple'), P.format('Offset')]),
        ('uB', [P.format('Repeatx'), P.format('Repeaty'), P.format('Sides'), P.format('Speed')]),
        ('uC', [MI.format('Wrap'), 'absTime.seconds if %s != 0 else 0' % P.format('Speed'), '0', '0']),
    ]


def build(m, H):
    """in1 (A) + b_src (A / Btop / b_noise) -> fx (one pass) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    bs = mk(m, selectTOP, 'b_sel')
    expr(bs.par.top, "parent().par.Btop.eval() or 'in1'")
    bs.comment = 'B = any TOP path (Btop); empty = A itself. Read only while Bsource = top (sampled by uv, any size).'
    nz = mk(m, noiseTOP, 'b_noise')
    nz.par.outputresolution = 'custom'
    expr(nz.par.resolutionw, "max(16, op('in1').width // 4)")
    expr(nz.par.resolutionh, "max(16, op('in1').height // 4)")
    nz.par.mono = False
    expr(nz.par.period, P.format('Noisescale'))
    expr(nz.par.tz, 'absTime.seconds * %s' % P.format('Noisespeed'))
    nz.comment = 'Built-in modulator: colour noise at 1/4 res, moving at Noisespeed (cooks only while Bsource = noise).'
    b = mk(m, switchTOP, 'b_src')
    for i, s in enumerate((in1, bs, nz)):
        b.inputConnectors[i].connect(s)
    expr(b.par.index, MI.format('Bsource'))
    b.comment = 'B: 0 A itself, 1 Btop, 2 noise. Only the picked one cooks.'
    g = H['compute'](m, 'fx', _glsl('modulate'), [in1, b])
    H['uniforms'](g, uniforms())
    g.par.inputextenduv = 'hold'          # live: zero extend blended the frame edge (uv ~1 read half transparent)
    g.par.inputfiltertype = 'linear'
    g.comment = 'modulate: B read at uv bends where A is read (9 Hydra modes), then wrap.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(g)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exactly (fx not cooked).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 A + B', 'role': 'input', 'ops': ['in1', 'b_sel', 'b_noise', 'b_src'],
         'body': 'A = in1 (rack chain); B = A, Btop or the built-in noise.'},
        {'title': '2 Modulate', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One compute pass: B bends the uv of A (modulate / scale / rotate / hue / pixelate / repeat / '
                 'kaleid / scroll).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
