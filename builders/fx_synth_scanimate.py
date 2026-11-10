# fx_synth_scanimate - FX_synth module 'scanimate' (FX2 AV-27 Scanimate flying-logo / slit-raster look). Template:
# docs/builds/fx_glitch.md "Module template" (rack = builders/fx_synth.py); doc + LIVE CHECKS: docs/builds/fx_synth.md.
# A high-contrast source (in1, or the logo_text Text TOP) is keyed, drawn through the Scanimate deflection raster
# (fly-in zoom + spin, perspective taper, a horizontal sine bend travelling along the lines), smeared into
# long-tail streamers by a feedback trail (zoom / drift / blur / Decay) and coloured by the trail's AGE through a
# 4-stop ramp (Bands = banded streamers), with raster scanlines and mip glow. Settle 0 = flying, 1 = the clean,
# whole source (warps and trails x 0): keyframe Settle to land the title readable.
# Use it on titles typed in Text (whole words, never split) or on art that allows distortion; keep brand logos clean.
# Network: in1 + logo_text -> src (Switch) -> warp (compute) -> fb (Feedback of trail) -> stamp (1x1 clock)
#   -> trail (compute, 16f state) -> look (compute, in1 + trail: colour, lines, glow, background, Amount)
#   -> out_sel (Amount 0 = in1, nothing cooks) -> out1. Maths = builders/fx_synth_logic.py sc_*. ASCII only.
import os

MODULE = 'scanimate'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
SHADERS = {'stamp': 'stamp', 'warp': 'scan_warp', 'trail': 'scan_trail', 'look': 'scan_look'}
PALETTES = ['gold', 'sunset', 'electric', 'chrome', 'mono']

PAGES = [
    ('Scanimate', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Source', 'Menu', 'text', {'names': ['input', 'text'], 'labels': ['Input (in1)', 'Text (logo_text)']}),
        ('Text', 'Str', 'SCANIMATE', {'label': 'Text'}),
        ('Textsize', 'Float', 0.16, {'min': 0.02, 'max': 0.5, 'label': 'Text size (x width)'}),
        ('Key', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Key (luma above)'}),
        ('Keysoft', 'Float', 0.1, {'min': 0, 'max': 0.5, 'label': 'Key softness'}),
        ('Settle', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Settle (1 = clean source)'}),
        ('Colour', 'Menu', 'ramp', {'names': ['ramp', 'logo'], 'labels': ['Age ramp', 'Source colour + ramp']}),
        ('Palette', 'Menu', 'sunset', {'names': PALETTES, 'labels': ['Gold pink orchid plum', 'Sunset',
                                                                   'Electric', 'Chrome', 'Mono']}),
        ('Background', 'Menu', 'black', {'names': ['black', 'input', 'transparent'],
                                         'labels': ['Black', 'Input', 'Transparent']}),
        ('Reset', 'Toggle', False, {'label': 'Reset (clear trails)'}),
    ]),
    ('Warp', [
        ('Bend', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Bend (widths)'}),
        ('Bendfreq', 'Float', 1.5, {'min': 0, 'max': 8, 'label': 'Bend cycles per height'}),
        ('Bendspeed', 'Float', 0.5, {'min': -4, 'max': 4, 'label': 'Bend speed (cycles/s)'}),
        ('Taper', 'Float', 0.3, {'min': -1, 'max': 1, 'label': 'Perspective taper'}),
        ('Zoom', 'Float', 1.0, {'min': 0.1, 'max': 4, 'label': 'Zoom'}),
        ('Fly', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Fly (zoom swing)'}),
        ('Flyspeed', 'Float', 0.25, {'min': 0, 'max': 4, 'label': 'Fly speed Hz'}),
        ('Rotate', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate deg'}),
        ('Spin', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Spin deg/s'}),
    ]),
    ('Trails', [
        ('Decay', 'Float', 0.93, {'min': 0, 'max': 0.995, 'label': 'Trail decay per cook'}),
        ('Trailzoom', 'Float', 1.01, {'min': 0.9, 'max': 1.1, 'label': 'Trail zoom per cook'}),
        ('Trailx', 'Float', 0.0, {'min': -8, 'max': 8, 'label': 'Trail drift x px'}),
        ('Traily', 'Float', 0.0, {'min': -8, 'max': 8, 'label': 'Trail drift y px'}),
        ('Trailblur', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Trail blur'}),
        ('Bands', 'Int', 0, {'min': 0, 'max': 12, 'label': 'Age bands (0 = smooth)'}),
        ('Lines', 'Int', 0, {'min': 0, 'max': 480, 'label': 'Raster lines (0 = off)'}),
        ('Linegap', 'Float', 0.4, {'min': 0, 'max': 0.9, 'label': 'Line gap'}),
        ('Glow', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Glow'}),
    ]),
]
PANEL_PAGES = ['Scanimate', 'Warp', 'Trails']

_Z = {'Source': 1, 'Text': 'SCANIMATE', 'Textsize': 0.16, 'Key': 0.5, 'Keysoft': 0.1, 'Settle': 0.0, 'Colour': 0,
      'Palette': 1, 'Background': 0, 'Reset': 0, 'Bend': 0.15, 'Bendfreq': 1.5, 'Bendspeed': 0.5, 'Taper': 0.3,
      'Zoom': 1.0, 'Fly': 0.2, 'Flyspeed': 0.25, 'Rotate': 0.0, 'Spin': 0.0, 'Decay': 0.93, 'Trailzoom': 1.01,
      'Trailx': 0.0, 'Traily': 0.0, 'Trailblur': 0.3, 'Bands': 0, 'Lines': 0, 'Linegap': 0.4, 'Glow': 0.5}
PRESETS = [
    (1, 'flying logo', dict(_Z, Amount=1.0)),
    (2, 'banded streamers', dict(_Z, Amount=1.0, Bands=6, Decay=0.96, Trailzoom=1.02, Bend=0.25, Palette=0,
                                 Lines=240, Linegap=0.35)),
    (3, 'title settle', dict(_Z, Amount=1.0, Settle=1.0, Colour=1, Glow=0.8, Lines=320, Linegap=0.3)),
    (4, 'spin tunnel', dict(_Z, Amount=1.0, Spin=40.0, Fly=0.5, Flyspeed=0.5, Decay=0.97, Trailzoom=0.98,
                            Palette=2, Bend=0.05)),
    (5, 'rising slit', dict(_Z, Amount=1.0, Traily=3.0, Trailzoom=1.0, Decay=0.95, Taper=0.6, Bend=0.1,
                            Bands=4, Palette=3, Lines=180)),
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
    if name == 'warp':
        return [
            ('uA', [P.format('Key'), P.format('Keysoft'), P.format('Settle'), 'absTime.seconds']),
            ('uB', [P.format('Bend'), P.format('Bendfreq'), P.format('Bendspeed'), P.format('Taper')]),
            ('uC', [P.format('Zoom'), P.format('Fly'), P.format('Flyspeed'), P.format('Rotate')]),
            ('uD', [P.format('Spin'), '0', '0', '0']),
        ]
    if name == 'trail':
        return [
            ('uA', [P.format('Decay'), P.format('Trailzoom'), P.format('Trailx'), P.format('Traily')]),
            ('uB', [P.format('Trailblur'), TOG.format('Reset'), P.format('Settle'), '0']),
        ]
    return [
        ('uA', [P.format('Amount'), MI.format('Colour'), MI.format('Palette'), P.format('Bands')]),
        ('uB', [P.format('Lines'), P.format('Linegap'), P.format('Glow'), MI.format('Background')]),
    ]


def build(m, H):
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    tx = mk(m, textTOP, 'logo_text')
    expr(tx.par.text, P.format('Text'))
    tx.par.outputresolution = 'custom'
    expr(tx.par.resolutionw, "op('in1').width")
    expr(tx.par.resolutionh, "op('in1').height")
    if getattr(tx.par, 'fontsizex', None) is not None:
        expr(tx.par.fontsizex, "op('in1').width * %s" % P.format('Textsize'))
    tx.comment = 'Logo / title text (white on black, the input size). Cooks only while Source = text.'
    src = mk(m, switchTOP, 'src')
    src.inputConnectors[0].connect(in1)
    src.inputConnectors[1].connect(tx)
    expr(src.par.index, MI.format('Source'))
    src.comment = 'Source: in1 or logo_text.'
    w = H['compute'](m, 'warp', _glsl('scan_warp'), [src], fmt='rgba16float')
    H['uniforms'](w, uniforms('warp'))
    w.comment = 'Scanimate raster: zoom/spin, taper, travelling bend; keyed source (premultiplied, alpha = key).'
    fb = mk(m, feedbackTOP, 'fb')
    fb.inputConnectors[0].connect(w)
    st = H['compute'](m, 'stamp', _glsl('stamp'), [fb], res=(1, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    st.par.autodispatchsize = False
    st.par.dispatchsizex, st.par.dispatchsizey, st.par.dispatchsizez = 1, 1, 1
    H['uniforms'](st, uniforms('stamp'))
    st.comment = 'Cook clock: gap > 0.25 s (slot bypassed) -> trails restart, no stale trail pops in.'
    tr = H['compute'](m, 'trail', _glsl('scan_trail'), [w, fb, st], fmt='rgba16float')
    tr.par.inputextenduv = 'zero'
    H['uniforms'](tr, uniforms('trail'))
    tr.comment = 'Streamers: warp OVER (previous x Decay, zoomed / drifted / blurred). alpha = trail age.'
    fb.par.top = 'trail'
    fb.comment = 'Previous trail state.'
    lk = H['compute'](m, 'look', _glsl('scan_look'), [in1, tr])
    lk.par.inputfiltertype = 'mipmap'
    H['uniforms'](lk, uniforms('look'))
    lk.comment = 'Age -> palette (bands), logo colour, raster lines, mip glow, background, Amount.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(lk)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exactly (nothing cooks).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 Source', 'role': 'input', 'ops': ['in1', 'logo_text', 'src']},
        {'title': '2 Raster + trails', 'role': 'process',
         'ops': ['warp', 'warp_compute', 'fb', 'stamp', 'stamp_compute', 'trail', 'trail_compute'],
         'body': 'warp (deflection raster) -> trail (feedback streamers, 16f; stamp restarts after a bypass).'},
        {'title': '3 Look', 'role': 'output', 'ops': ['look', 'look_compute', 'out_sel', 'out1'],
         'body': 'Age ramp, raster lines, glow, background, Amount.'},
    ]
