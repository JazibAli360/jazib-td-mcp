# fx_track_plexus - FX_track module 'plexus' (FX7b TC-01 blob plexus: tracked blobs become points joined by thin
# proximity lines, with dots and a quantised finish). Template: docs/builds/fx_glitch.md "Module template" (rack =
# builders/fx_track.py). Doc: docs/builds/fx_track.md. Mirror: fx_track_plexus_ref in builders/fx_track_logic.py.
# The lines are NOT re-implemented: PX_lines (builders/px_lines.py, W1-C) is built inside the module from its own
# builder (instance, not a copy) in `connect` mode, fed with the rack's trk_pts (Ptstride 4, Ptcount = N); its pars are
# bound to this module's pars by expressions (radius in px -> PX_lines world units on its own camera plane).
#   in1 -> lines (PX_lines: in1 = picture, in_points = pts) -> fx (dots at the points + posterise, Amount mix with in1)
#   -> out_sel (Amount 0 = in1, nothing cooks) -> out1.
# <= 3 GLSL TOP inputs (T-88). ASCII only.
import os

MODULE = 'plexus'
DOTSTYLES = ['off', 'filled', 'ring', 'cross']
LINECOLSRC = [('solid', 'Solid colour'), ('palette', 'Palette at position'), ('attr', 'Palette by attribute'),
              ('source', 'Keep source colour'), ('index', 'Palette stop by index')]
LINEATTR = [('along', 'Along the link'), ('index', 'Point index'), ('depth', 'Depth'), ('random', 'Random per link')]

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
_L = {'HERE': HERE}  # noqa: F821
exec(compile(open(os.path.join(HERE, 'fx_track_lib.py')).read(), 'fx_track_lib.py', 'exec'), _L)  # noqa: F821

PAGES = [
    ('Plexus', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Radius', 'Float', 170.0, {'min': 1, 'max': 1000, 'label': 'Link radius px'}),
        ('Neighbours', 'Int', 3, {'min': 1, 'max': 4, 'label': 'Links per point'}),
        ('Pieces', 'Int', 1, {'min': 1, 'max': 8, 'label': 'Pieces per link (lightning)'}),
        ('Jitter', 'Float', 0.0, {'min': 0, 'max': 60, 'label': 'Jitter px (lightning)'}),
        ('Jitterhz', 'Float', 12.0, {'min': 0, 'max': 60, 'label': 'Jitter rate Hz'}),
        ('Linewidth', 'Float', 1.5, {'min': 0.25, 'max': 16, 'label': 'Line width px'}),
        ('Halo', 'Float', 3.0, {'min': 0, 'max': 32, 'label': 'Halo px'}),
        ('Halogain', 'Float', 0.35, {'min': 0, 'max': 2, 'label': 'Halo gain'}),
        ('Intensity', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Intensity (HDR)'}),
        ('Blend', 'Menu', 'max', {'names': ['add', 'max'], 'labels': ['Add (crossings brighten)', 'Max (clean)']}),
        ('Bgdim', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Dim the picture'}),
        ('Reveal', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Reveal (draw-on)'}),
        ('Flicker', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Flicker per link'}),
        ('Flickerhz', 'Float', 12.0, {'min': 0, 'max': 60, 'label': 'Flicker Hz'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 999, 'label': 'Seed'}),
    ]),
    ('Dots', [
        ('Dotstyle', 'Menu', 'ring', {'names': DOTSTYLES, 'labels': ['Off', 'Filled', 'Ring', 'Cross']}),
        ('Dotradius', 'Float', 6.0, {'min': 0, 'max': 60, 'label': 'Dot radius px'}),
        ('Dotwidth', 'Float', 1.5, {'min': 0.25, 'max': 16, 'label': 'Ring / cross width px'}),
        ('Dotcolsrc', 'Menu', 'solid', {'names': [k for k, _l in _L['COLSRC']], 'labels': [b for _k, b in _L['COLSRC']]}),
        ('Dotr', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Dot R'}),
        ('Dotg', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Dot G'}),
        ('Dotb', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Dot B'}),
        ('Dotgain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Dot gain'}),
        ('Speedref', 'Float', 400.0, {'min': 1, 'max': 4000, 'label': 'Speed for palette end px/s'}),
        ('Levels', 'Int', 0, {'min': 0, 'max': 16, 'label': 'Posterise levels (0 off)'}),
    ]),
    ('Linecolour', [
        ('Linecolsrc', 'Menu', 'solid', {'names': [k for k, _l in LINECOLSRC], 'labels': [b for _k, b in LINECOLSRC]}),
        ('Linecolr', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Line R'}),
        ('Linecolg', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Line G'}),
        ('Linecolb', 'Float', 0.55, {'min': 0, 'max': 1, 'label': 'Line B'}),
        ('Linepalpos', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Palette position'}),
        ('Linepalspread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Palette spread'}),
        ('Lineattr', 'Menu', 'along', {'names': [k for k, _l in LINEATTR], 'labels': [b for _k, b in LINEATTR]}),
    ]),
    pal_page('neon_trio', 'gradient'),  # noqa: F821
]
PANEL_PAGES = ['Plexus', 'Dots', 'Linecolour', 'Palette']

_SKIP = ('Palstops', 'Palfile')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
_D['Palreverse'] = int(_D['Palreverse'])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'web', _p()),
    (2, 'lightning', _p(Pieces=4, Jitter=10.0, Jitterhz=18.0, Linewidth=1.2, Halo=5.0, Intensity=2.2,
                        Linecolr=0.55, Linecolg=0.75, Linecolb=1.0, Dotstyle=2, Dotradius=4.0, Flicker=0.4, Seed=2)),
    (3, 'dense lace', _p(Radius=240.0, Neighbours=4, Linewidth=1.0, Halo=0.0, Blend=0, Intensity=1.0,
                         Linecolsrc=2, Lineattr=1, Dotstyle=1, Dotradius=2.5, Dotcolsrc=1, Bgdim=0.5, Seed=3)),
    (4, 'posterised', _p(Levels=4, Dotstyle=1, Dotradius=9.0, Dotcolsrc=2, Linewidth=2.5, Halo=6.0, Halogain=0.6,
                         Linecolsrc=1, Linepalpos=0.3, Palsource=PAL_SOURCE_NAMES.index('fire'), Seed=4)),  # noqa: F821
    (5, 'cross hairs', _p(Radius=120.0, Neighbours=2, Dotstyle=3, Dotradius=10.0, Dotwidth=1.0, Dotcolsrc=3,
                          Linecolsrc=4, Lineattr=1, Palsource=PAL_SOURCE_NAMES.index('cyan_magenta'),  # noqa: F821
                          Bgdim=0.3, Seed=5)),
]

FX = """// plexus fx (compute). in0 lines (PX_lines out1, composite over in1), in1 trk_pts, in2 in1 (Amount mix).
// Dots at the valid points (filled / ring / cross, 1 px AA, colour source), posterise (Levels > 0).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, dot radius px, dot style, dot width px
uniform vec4 uB;   // levels, dot colour source, dot gain, speed ref px/s
uniform vec4 uC;   // dot r g b, -
uniform vec4 uG;   // detector, cells x, cells y, N
#define FT_PTS sTD2DInputs[1]
""" + PAL_GLSL + _L['GLSL_LIB'] + _L['GLSL_COL'] + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= sz.x || p.y >= sz.y) return;
    vec2 res = vec2(sz), pc = vec2(p) + 0.5, uv = pc / res;
    vec4 src = texelFetch(sTD2DInputs[2], p, 0);
    vec4 base = texture(sTD2DInputs[0], uv);
    vec3 col = base.rgb;
    if (uB.x > 0.5) col = floor(col * uB.x + 0.5) / uB.x;
    float da = 0.0;
    vec3 dc = vec3(0.0);
    int st = int(uA.z + 0.5);
    if (st > 0) {
        float R = max(uA.y, 0.0), w = max(uA.w, 0.25);
        vec2 reach = vec2(R + w + 1.0) / res;
""" + _L['LOOP_OPEN'] + """
            vec2 q = pc - T1.xy * res;
            float d = length(q), a;
            if (st == 1) a = clamp(R - d + 0.5, 0.0, 1.0);
            else if (st == 2) a = clamp(0.5 * w - abs(d - R) + 0.5, 0.0, 1.0);
            else {
                vec2 aq = abs(q);
                a = max(aq.x, aq.y) <= R + 0.5 ? clamp(0.5 * w - min(aq.x, aq.y) + 0.5, 0.0, 1.0) : 0.0;
            }
            if (a > da) { da = a; dc = ftCol(int(uB.y + 0.5), uC.rgb, T1, T3, res, uB.w) * uB.z; }
""" + _L['LOOP_CLOSE'] + """
    }
    col = mix(col, dc, da);
    vec4 o = vec4(col, max(base.a, da));
    TDImageStoreOutput(0, ivec3(p, 0), mix(src, o, uA.x));
}
"""

SHADERS = {'fx': FX}
NIN = {'fx': 3}

P = "parent().par.{}.eval()"
G = ['parent(2).par.Detector.menuIndex', 'parent(2).par.Cellsx.eval()', 'parent(2).par.Cellsy.eval()']


def uniforms():
    return {'fx': [
        ('uA', [P.format('Amount'), P.format('Dotradius'), 'parent().par.Dotstyle.menuIndex', P.format('Dotwidth')]),
        ('uB', [P.format('Levels'), 'parent().par.Dotcolsrc.menuIndex', P.format('Dotgain'), P.format('Speedref')]),
        ('uC', [P.format('Dotr'), P.format('Dotg'), P.format('Dotb'), '0']),
        ('uG', G + [H_N('2')]),
    ]}


def H_N(up):
    """Point count expression from a module op (rack = parent(2)); pars only (no TOP size)."""
    return ("(int(parent(%s).par.Cellsx.eval()) * int(parent(%s).par.Cellsy.eval()) if parent(%s).par.Detector.eval() "
            "== 'cells' else int(parent(%s).par.Maxblobs.eval()))") % (up, up, up, up)


WX = _L['WX']


def line_bindings():
    """PX_lines par -> expression on the lines COMP (parent() = this module, parent(2) = the rack)."""
    px = 'parent().par.{}.eval() * 2 * %r / max(1, parent(2).par.Resw.eval())' % WX
    b = {
        'Ptcount': H_N('2'), 'Cnpoints': H_N('2'), 'Cnk': P.format('Neighbours'), 'Cnradius': px.format('Radius'),
        'Cnsub': P.format('Pieces'), 'Cnjitter': px.format('Jitter'), 'Cnjitterhz': P.format('Jitterhz'),
        'Cnattr': P.format('Lineattr'), 'Width': P.format('Linewidth'), 'Halo': P.format('Halo'),
        'Halogain': P.format('Halogain'), 'Intensity': P.format('Intensity'), 'Blend': P.format('Blend'),
        'Bgdim': P.format('Bgdim'), 'Reveal': P.format('Reveal'), 'Flicker': P.format('Flicker'),
        'Flickerhz': P.format('Flickerhz'), 'Seed': P.format('Seed'), 'Linecolsrc': P.format('Linecolsrc'),
        'Linecolr': P.format('Linecolr'), 'Linecolg': P.format('Linecolg'), 'Linecolb': P.format('Linecolb'),
        'Linepalpos': P.format('Linepalpos'), 'Linepalspread': P.format('Linepalspread'),
        'Palsource': ("parent().par.Palsource.eval() if parent().par.Palsource.eval() in me.par.Palsource.menuNames "
                      "else 'neon_trio'"),
        'Palmode': P.format('Palmode'), 'Palinterp': P.format('Palinterp'), 'Palreverse': P.format('Palreverse'),
        'Palshift': P.format('Palshift'), 'Resx': 'parent(2).par.Resw.eval()', 'Resy': 'parent(2).par.Resh.eval()',
    }
    const = {'Rings': False, 'Contour': False, 'Trails': False, 'Polyline': False, 'Edges': False, 'Connect': True,
             'Ptstride': 4, 'Amount': 1.0, 'Outmode': 'composite', 'Cnfirst': 0, 'Cncount': 0, 'Cngain': 1.0}
    return b, const


def build(m, H):
    """in1 -> lines (PX_lines instance, connect) + pts -> fx -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    pts = mk(m, selectTOP, 'pts')  # noqa: F821
    pts.par.top = '../trk_pts'
    pts.comment = "The rack's points (trk_pts)."
    ns = dict(globals())
    exec(open(os.path.join(HERE, 'px_lines.py')).read(), ns)  # noqa: F821  (PX_lines' own builder: an instance)
    info = ns['build'](m.path, 'lines')
    lines = m.op('lines')
    lines.inputConnectors[0].connect(in1)
    lines.inputConnectors[1].connect(pts)
    b, const = line_bindings()
    for k, v in const.items():
        getattr(lines.par, k).val = v
    for k, e in b.items():
        expr(getattr(lines.par, k), e)
    lines.comment = 'PX_lines (builders/px_lines.py) in connect mode; pars bound to the module (Plexus / Linecolour).'
    fx = H['pas'](m, 'fx', FX, [lines.outputConnectors[0], pts, in1],     # a COMP source: its connector
                  'me.inputs[2].width', 'me.inputs[2].height', 'rgba16float', 'hold')
    H['uniforms'](fx, U['fx'])
    fx.comment = 'Dots at the tracked points + posterise; Amount mix with in1.'
    pal_bind(m, H, [fx])  # noqa: F821
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact (lines / fx not pulled).'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    m.store('plexus_lines_missing', list(info.get('missing', [])))
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pts']},
        {'title': '2 Lines', 'role': 'process', 'ops': ['lines'],
         'body': 'PX_lines connect: each point to its Neighbours nearest within Radius px.'},
        {'title': '3 Dots', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'fx', 'fx_compute'],
         'body': 'Dots at the points + posterise.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
