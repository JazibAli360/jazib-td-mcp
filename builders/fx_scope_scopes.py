# fx_scope_scopes - FX_scope module 'scopes': video scopes of the input picture (FX2 AV-33, FX0 row 58): waveform,
# RGB parade, vectorscope (75 / 100 % bar targets, skin line), histogram (R G B luma, auto scale). Two compute passes:
# `hist` counts the sampled input (every Step px) into a bins texture with shared-memory atomics per tile (no image
# atomics, FX2 note; gather fallback when ATOMICS is off), `fx` draws it with a broadcast graticule over the dimmed
# picture (overlay panel or full frame). Exact counts = logic.hist_ref (LIVE CHECK S1-S4). Also an engineering aid:
# clipped / crushed LED-wall levels show at the waveform's top / bottom line. ASCII only.
import os

MODULE = 'scopes'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
BE = dict(globals())
with open(os.path.join(_HERE, 'fx_scope_beam.py')) as _fh:
    exec(_fh.read(), BE)
LG = BE['LG']
P, MI = BE['P'], BE['MI']

PAGES = [
    ('Scope', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Scope', 'Menu', 'waveform', {'names': LG['SCOPES'], 'labels': ['Waveform (luma)', 'RGB parade',
                                                                         'Vectorscope', 'Histogram'],
                                       'label': 'Scope'}),
        ('Matrix', 'Menu', '709', {'names': ['709', '601'], 'labels': ['Rec.709 (HD)', 'Rec.601 (SD)'],
                                   'label': 'Matrix'}),
        ('Step', 'Int', 4, {'min': 1, 'max': 16, 'label': 'Sample every N px'}),
        ('Levels', 'Menu', '256', {'names': [str(v) for v in LG['LEVELS']], 'labels': ['128', '256', '512'],
                                   'label': 'Levels (waveform / parade / histogram)'}),
        ('Bins', 'Menu', '256', {'names': [str(v) for v in LG['BINS']], 'labels': ['128', '256', '512'],
                                 'label': 'Vectorscope bins'}),
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Trace gain'}),
        ('Colour', 'Menu', 'colour', {'names': ['green', 'white', 'colour'],
                                      'labels': ['Green', 'White', 'Colour (parade / vectorscope)'],
                                      'label': 'Trace colour'}),
        ('Logscale', 'Toggle', False, {'label': 'Histogram log scale'}),
        ('Zoom', 'Float', 1.0, {'min': 0.5, 'max': 4, 'label': 'Vectorscope zoom'}),
        ('Bars', 'Menu', '75', {'names': ['75', '100'], 'labels': ['75 % bars', '100 % bars'], 'label': 'Targets'}),
        ('Skinline', 'Toggle', True, {'label': 'Skin-tone line'}),
        ('Legal', 'Toggle', True, {'label': 'Legal 16 / 235 lines'}),
    ]),
    ('Panel', [
        ('Layout', 'Menu', 'overlay', {'names': ['overlay', 'full'], 'labels': ['Overlay panel', 'Full frame'],
                                       'label': 'Layout'}),
        ('Size', 'Float', 0.6, {'min': 0.1, 'max': 1, 'label': 'Panel width (of the canvas width)'}),
        ('Panelratio', 'Float', 0.6, {'min': 0.2, 'max': 2, 'label': 'Panel height / width (not vectorscope)'}),
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre X'}),
        ('Centery', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Centre Y'}),
        ('Graticule', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Graticule'}),
        ('Bgdim', 'Float', 0.75, {'min': 0, 'max': 1, 'label': 'Picture dim behind the panel'}),
    ]),
]
PANEL_PAGES = ['Scope', 'Panel']
MENUS = dict((n, o['names']) for _pg, pars in PAGES for n, s, _d, o in pars if s == 'Menu')


def _v(d):
    return dict((k, MENUS[k].index(v) if k in MENUS else v) for k, v in d.items())


PRESETS = [
    (1, 'waveform', _v({'Scope': 'waveform', 'Layout': 'overlay', 'Colour': 'green', 'Gain': 1.0, 'Size': 0.6})),
    (2, 'RGB parade', _v({'Scope': 'parade', 'Layout': 'overlay', 'Colour': 'colour', 'Gain': 1.2, 'Size': 0.8})),
    (3, 'vectorscope', _v({'Scope': 'vectorscope', 'Layout': 'overlay', 'Colour': 'colour', 'Gain': 1.5,
                           'Size': 0.55, 'Zoom': 1.0, 'Skinline': 1})),
    (4, 'histogram', _v({'Scope': 'histogram', 'Layout': 'overlay', 'Logscale': 0, 'Size': 0.7, 'Panelratio': 0.4})),
    (5, 'scope wall', _v({'Scope': 'parade', 'Layout': 'full', 'Colour': 'colour', 'Gain': 2.0, 'Bgdim': 1.0,
                          'Graticule': 0.4, 'Step': 2})),
]

LV_EXPR = "[128, 256, 512][%s]" % MI.format('Levels')
B_EXPR = "[128, 256, 512][%s]" % MI.format('Bins')
# panel: full = whole frame (vectorscope: centred square); overlay = Size x W wide, Panelratio high (vector: square)
PANEL_LAMBDA = ("(lambda W, H, full, vec, s, r, cx, cy: ((0.0, 0.0, W, H) if not vec else "
                "((W - min(W, H)) / 2.0, (H - min(W, H)) / 2.0, min(W, H), min(W, H))) if full else "
                "(lambda pw, ph: (cx * W - pw / 2.0, cy * H - ph / 2.0, pw, ph))(s * W, s * W * (1.0 if vec else r)))")


def panel(W, H, full, vec, s, r, cx, cy):
    return eval(PANEL_LAMBDA)(W, H, full, vec, s, r, cx, cy)


def panel_expr(k):
    return PANEL_LAMBDA + "(me.inputs[0].width, me.inputs[0].height, %s == 1, %s == 2, %s, %s, %s, %s)[%d]" % (
        MI.format('Layout'), MI.format('Scope'), P.format('Size'), P.format('Panelratio'), P.format('Centerx'),
        P.format('Centery'), k)


def geom_expr(key, src="me.inputs[0]"):
    return LG['GEOM_LAMBDA'] + "(%s, %s.width, %s.height, %s, %s, %s)[%d]" % (
        MI.format('Scope'), src, src, P.format('Step'), LV_EXPR, B_EXPR, LG['GEOM_KEYS'].index(key))


def shader_texts():
    return {'hist': BE['defines']() + BE['glsl']('hist'), 'fx': BE['glsl']('scopes')}


def build(m, H):
    mk, expr = H['mk'], H['expr']
    T = shader_texts()
    miss = []
    in1 = mk(m, inTOP, 'in1')                                      # noqa: F821 (TD global)
    hist = H['compute'](m, 'hist', T['hist'], [in1], res=(256, 256), fmt='rgba32float')
    expr(hist.par.resolutionw, geom_expr('w'))
    expr(hist.par.resolutionh, geom_expr('h'))
    miss += BE['setp'](hist, H, autodispatchsize=False, dispatchsizex='=' + geom_expr('gx'),
                       dispatchsizey='=' + geom_expr('gy'), dispatchsizez=1)
    H['uniforms'](hist, [
        ('uH0', [MI.format('Scope'), P.format('Step'), geom_expr('Sx'), geom_expr('Sy')]),
        ('uH1', [LV_EXPR, B_EXPR, MI.format('Matrix'), geom_expr('cpt')]),
    ])
    hist.comment = 'Bins texture: counts per tile in shared memory (atomics), r = count, g = histogram row max.'
    fx = H['compute'](m, 'fx', T['fx'], [in1, hist])
    H['uniforms'](fx, [
        ('uPn', [panel_expr(k) for k in range(4)]),
        ('uD', [MI.format('Scope'), geom_expr('Sx'), geom_expr('Sy'), LV_EXPR]),
        ('uD2', [B_EXPR, P.format('Gain'), MI.format('Colour'), '1 if %s else 0' % P.format('Logscale')]),
        ('uD3', [P.format('Graticule'), MI.format('Matrix'), '[0.75, 1.0][%s]' % MI.format('Bars'),
                 '1 if %s else 0' % P.format('Skinline')]),
        ('uD4', [P.format('Bgdim'), P.format('Amount'), P.format('Zoom'), '1 if %s else 0' % P.format('Legal')]),
    ])
    fx.comment = 'Scope display + graticule in the panel over the dimmed picture; outside = in1 exact.'
    for g in (hist, fx):
        BE['tidy'](g, H)
    sel = mk(m, switchTOP, 'out_sel')                              # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact (hist / fx not pulled).'
    out1 = mk(m, outTOP, 'out1')                                   # noqa: F821
    out1.inputConnectors[0].connect(sel)
    m.store('fx_scope_missing', ' '.join(miss))
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Bins', 'role': 'process', 'ops': ['hist', 'hist_compute'],
         'body': 'Sampled input -> counts (waveform / parade / vectorscope / histogram).'},
        {'title': '3 Scope', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'Trace + graticule + panel.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
