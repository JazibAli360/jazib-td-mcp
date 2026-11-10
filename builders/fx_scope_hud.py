# fx_scope_hud - FX_scope module 'hud': camera viewfinder / monitoring overlay (FX3 C6, FX0 row 58). One compute pass
# over the picture: zebra (level band, moving diagonal stripes), focus peaking (|Sobel| / 4 > threshold, optional mono
# picture), false colour (exposure bands / spectrum / 11 zones / clip), clip + crush warning (blinks 2 Hz), frame
# guides with outside dim (16:9, 2.39, 1.85, 4:3, 4:5, 1:1, 9:16), safe areas, centre cross, corner brackets, REC /
# STBY with a blinking dot, timecode (run time with Tcreset, or time of day), battery, a 16-character label. 8x8
# public-domain font (fx_scope_logic.FONT_HEX) with a dark outline so text reads on any picture. ASCII only.
import os

MODULE = 'hud'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
BE = dict(globals())
with open(os.path.join(_HERE, 'fx_scope_beam.py')) as _fh:
    exec(_fh.read(), BE)
LG = BE['LG']
P, MI = BE['P'], BE['MI']

PAGES = [
    ('HUD', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Hudcolour', 'Menu', 'white', {'names': ['white', 'yellow', 'green', 'cyan'],
                                        'labels': ['White', 'Yellow', 'Green', 'Cyan'], 'label': 'HUD colour'}),
        ('Hudscale', 'Float', 4.0, {'min': 1, 'max': 12, 'label': 'Text size (px per font pixel)'}),
        ('Margin', 'Float', 0.035, {'min': 0, 'max': 0.2, 'label': 'Margin (of the short side)'}),
    ]),
    ('Exposure', [
        ('Zebra', 'Toggle', True, {'label': 'Zebra'}),
        ('Zebralevel', 'Float', 0.95, {'min': 0, 'max': 1, 'label': 'Zebra from (luma)'}),
        ('Zebraupper', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Zebra to (luma; < 1 = a band, e.g. skin 0.7)'}),
        ('Zebraopacity', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Zebra opacity'}),
        ('Zebrawidth', 'Float', 8.0, {'min': 1, 'max': 64, 'label': 'Zebra stripe width (px)'}),
        ('Zebraangle', 'Float', 45.0, {'min': -90, 'max': 90, 'label': 'Zebra angle (deg)'}),
        ('Zebraspeed', 'Float', 20.0, {'min': -200, 'max': 200, 'label': 'Zebra speed (px / s)'}),
        ('Zebracolour', 'Menu', 'white', {'names': ['white', 'black', 'red'], 'labels': ['White', 'Black', 'Red'],
                                          'label': 'Zebra colour'}),
        ('Falsecolour', 'Toggle', False, {'label': 'False colour'}),
        ('Fcmode', 'Menu', 'exposure', {'names': LG['FALSECOLOURS'],
                                        'labels': ['Exposure bands', 'Spectrum (heat)', '11 zones', 'Clip / crush only'],
                                        'label': 'False colour mode'}),
        ('Fcmix', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'False colour mix'}),
        ('Clip', 'Toggle', False, {'label': 'Clip / crush warning (blinks)'}),
        ('Cliplevel', 'Float', 0.99, {'min': 0.5, 'max': 1, 'label': 'Clip at (any channel)'}),
        ('Crushlevel', 'Float', 0.02, {'min': 0, 'max': 0.5, 'label': 'Crush at (luma)'}),
    ]),
    ('Focus', [
        ('Peaking', 'Toggle', False, {'label': 'Focus peaking'}),
        ('Peakthresh', 'Float', 0.15, {'min': 0.01, 'max': 1, 'label': 'Peaking threshold (|Sobel| / 4)'}),
        ('Peakcolour', 'Menu', 'red', {'names': ['red', 'yellow', 'blue', 'white', 'green'],
                                       'labels': ['Red', 'Yellow', 'Blue', 'White', 'Green'], 'label': 'Peaking colour'}),
        ('Peakmono', 'Toggle', False, {'label': 'Mono picture under peaking'}),
    ]),
    ('Overlay', [
        ('Rec', 'Menu', 'rec', {'names': ['off', 'standby', 'rec'], 'labels': ['Off', 'STBY', 'REC'], 'label': 'Rec'}),
        ('Recblink', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'REC dot blink (Hz, 0 = steady off)'}),
        ('Timecode', 'Toggle', True, {'label': 'Timecode'}),
        ('Tcsource', 'Menu', 'run', {'names': ['run', 'timeofday'], 'labels': ['Run time (Tcreset)', 'Time of day'],
                                     'label': 'Timecode source'}),
        ('Tcfps', 'Int', 25, {'min': 1, 'max': 60, 'label': 'Timecode frames per second'}),
        ('Tcoffset', 'Float', 0.0, {'min': 0, 'max': 86400, 'label': 'Timecode offset (s)'}),
        ('Tcreset', 'Pulse', None, {'label': 'Timecode reset'}),
        ('Battery', 'Toggle', True, {'label': 'Battery'}),
        ('Batterylevel', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Battery level (< 0.2 = red)'}),
        ('Label', 'Str', 'ISO 800  1/50  F2.8', {'label': 'Label (16 chars, bottom left)'}),
        ('Safe', 'Toggle', False, {'label': 'Safe areas'}),
        ('Safeaction', 'Float', 0.93, {'min': 0.5, 'max': 1, 'label': 'Action safe'}),
        ('Safetitle', 'Float', 0.9, {'min': 0.5, 'max': 1, 'label': 'Title safe'}),
        ('Centre', 'Toggle', True, {'label': 'Centre cross'}),
        ('Guides', 'Menu', 'none', {'names': LG['GUIDES'], 'labels': ['None', '16:9', '2.39:1', '1.85:1', '4:3', '4:5',
                                                                       '1:1', '9:16'], 'label': 'Frame guide'}),
        ('Guidedim', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Dim outside the guide'}),
        ('Brackets', 'Toggle', True, {'label': 'Corner brackets'}),
    ]),
    ('State', [
        ('Tcstart', 'Float', 0.0, {'min': 0, 'max': 1e6, 'label': 'Timecode start (absTime s; Tcreset)'}),
    ]),
]
PANEL_PAGES = ['HUD', 'Exposure', 'Focus', 'Overlay']
MENUS = dict((n, o['names']) for _pg, pars in PAGES for n, s, _d, o in pars if s == 'Menu')


def _v(d):
    return dict((k, MENUS[k].index(v) if k in MENUS else v) for k, v in d.items())


PRESETS = [
    (1, 'camera REC', _v({'Rec': 'rec', 'Timecode': 1, 'Battery': 1, 'Brackets': 1, 'Centre': 1, 'Zebra': 1,
                          'Zebralevel': 0.95, 'Falsecolour': 0, 'Peaking': 0, 'Guides': 'none', 'Safe': 0})),
    (2, 'exposure check', _v({'Falsecolour': 1, 'Fcmode': 'exposure', 'Zebra': 0, 'Rec': 'standby', 'Peaking': 0,
                              'Brackets': 0})),
    (3, 'focus check', _v({'Peaking': 1, 'Peakmono': 1, 'Peakcolour': 'red', 'Peakthresh': 0.12, 'Zebra': 0,
                           'Falsecolour': 0, 'Rec': 'standby'})),
    (4, 'cinema 2.39 guides', _v({'Guides': '2.39:1', 'Guidedim': 0.6, 'Safe': 1, 'Centre': 1, 'Rec': 'rec',
                                  'Zebra': 0, 'Brackets': 0})),
    (5, 'LED clip check', _v({'Clip': 1, 'Cliplevel': 0.98, 'Zebra': 1, 'Zebralevel': 0.9, 'Zebracolour': 'red',
                              'Falsecolour': 1, 'Fcmode': 'clip', 'Rec': 'off', 'Timecode': 0, 'Battery': 0,
                              'Brackets': 0})),
]

PULSES = """# Tcreset -> Tcstart = absTime.seconds (the HUD timecode counts from there). ASCII only.
def onPulse(par):
\tif par.name == 'Tcreset':
\t\tpar.owner.par.Tcstart.val = absTime.seconds
\treturn
"""


def font_glsl():
    w = LG['font_words']()
    return 'const uint FONT[%d] = uint[%d](%s);' % (len(w), len(w), ', '.join('%du' % v for v in w))


def shader_texts():
    return {'fx': BE['glsl']('hud').replace('//@FONT', font_glsl())}


MIN = "min(me.inputs[0].width, me.inputs[0].height)"


def uniforms():
    tc = LG['TC_EXPR']
    lab = [LG['label_expr'](k) for k in range(LG['LABEL_CHARS'])]
    return [
        ('uZ', ['1 if %s else 0' % P.format('Zebra'), P.format('Zebralevel'), P.format('Zebraupper'),
                P.format('Zebraopacity')]),
        ('uZ2', [P.format('Zebrawidth'), 'math.radians(%s)' % P.format('Zebraangle'),
                 '(absTime.seconds * %s) %% 100000.0' % P.format('Zebraspeed'), MI.format('Zebracolour')]),
        ('uK', ['1 if %s else 0' % P.format('Peaking'), P.format('Peakthresh'), MI.format('Peakcolour'),
                '1 if %s else 0' % P.format('Peakmono')]),
        ('uFc', ['1 if %s else 0' % P.format('Falsecolour'), MI.format('Fcmode'), P.format('Fcmix'),
                 '1 if %s else 0' % P.format('Clip')]),
        ('uCl', [P.format('Cliplevel'), P.format('Crushlevel'), 'absTime.seconds % 3600.0', P.format('Amount')]),
        ('uOv', [MI.format('Rec'), P.format('Recblink'), '1 if %s else 0' % P.format('Timecode'),
                 '%s if %s else -1.0' % (P.format('Batterylevel'), P.format('Battery'))]),
        ('uOv2', ['1 if %s else 0' % P.format('Safe'), P.format('Safeaction'), P.format('Safetitle'),
                  '1 if %s else 0' % P.format('Centre')]),
        ('uGd', ['%r[%s]' % (LG['GUIDE_ASPECT'], MI.format('Guides')), P.format('Guidedim'),
                 '1 if %s else 0' % P.format('Brackets'), MI.format('Hudcolour')]),
        ('uTx', [P.format('Hudscale'), '%s * %s' % (P.format('Margin'), MIN),
                 'min(len(%s.rstrip()), 16)' % P.format('Label'), '0']),
        ('uTc', [tc + '[%d]' % k for k in range(4)]),
        ('uLb0', lab[0:4]), ('uLb1', lab[4:8]), ('uLb2', lab[8:12]), ('uLb3', lab[12:16]),
    ]


def build(m, H):
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')                                      # noqa: F821 (TD global)
    pe = mk(m, parameterexecuteDAT, 'pulses')                      # noqa: F821
    if pe.text != PULSES:
        pe.text = PULSES
        pe.par.active = False                                      # T-97: toggle after a text rewrite
    miss = BE['setp'](pe, H, op='..', pars='Tcreset', valuechange=False, onpulse=True, active=True)
    pe.comment = 'Tcreset -> Tcstart (State page).'
    fx = H['compute'](m, 'fx', shader_texts()['fx'], [in1])
    H['uniforms'](fx, uniforms())
    BE['tidy'](fx, H)
    fx.comment = 'HUD: zebra, peaking, false colour, clip, guides, safe, REC, timecode, battery, label. One pass.'
    sel = mk(m, switchTOP, 'out_sel')                              # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact (fx not pulled).'
    out1 = mk(m, outTOP, 'out1')                                   # noqa: F821
    out1.inputConnectors[0].connect(sel)
    m.store('fx_scope_missing', ' '.join(miss))
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulses'], 'body': 'Tcreset -> Tcstart.'},
        {'title': '2 HUD', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'One compute pass.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
