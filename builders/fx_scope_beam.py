# fx_scope_beam - the FX_scope beam engine shared by the three line modules that use it today: xy, vector,
# lissajous (no-bloat rule: shared because 3 real modules draw beams). Exec'd by each module file (in TD and offline).
# Chain inside a module instance (all compute GLSL, T-46/T-47):
#   [module CHOPs] -> path (1024x17 rgba32f: points in beam px + chunk bboxes + count; module source shader)
#   -> beam (state, in place: Gaussian beam splat binned per 32 px tile + phosphor decay; 2 colour buffers)
#   -> glow (1/8, only while Glow > 0) -> look (input size: tone map, graticule, background, Amount) -> out_sel -> out1
# Maths + references: builders/fx_scope_logic.py. Shaders: builders/glsl/fx_scope_*.glsl. ASCII only.
import os

_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
GLSL_DIR = os.path.join(_HERE, 'glsl')
LG = {}
with open(os.path.join(_HERE, 'fx_scope_logic.py')) as _fh:
    exec(_fh.read(), LG)

# LIVE CHECK switches (docs/builds/fx_scope.md): flip only on evidence, then rebuild.
BUFFERS = 'packed'   # 'split' = one float texture buffer per channel if vec2/vec3 buffers do not map chans -> xyz (X0)
ATOMICS = True       # False = scan / gather fallbacks if shared-memory atomicAdd miscounts on 31550 (S0)

P = "parent().par.{}.eval()"
MI = "parent().par.{}.menuIndex"


def glsl(name):
    with open(os.path.join(GLSL_DIR, 'fx_scope_%s.glsl' % name)) as fh:
        return fh.read()


def defines():
    return '' if ATOMICS else '#define SCOPE_NO_ATOMICS\n'


def buf_header(rgb=False):
    """GLSL for the CHOP texture buffers: BUF_N(), BUF_XY(i) (+ BUF_RGB(i))."""
    if BUFFERS == 'packed':
        t = ("uniform samplerBuffer uXY;\n#define BUF_N() textureSize(uXY)\n"
             "#define BUF_XY(i) texelFetch(uXY, (i)).xy\n")
        if rgb:
            t += "uniform samplerBuffer uRGB;\n#define BUF_RGB(i) texelFetch(uRGB, (i)).rgb\n"
        return t
    t = ("uniform samplerBuffer uBx;\nuniform samplerBuffer uBy;\n#define BUF_N() textureSize(uBx)\n"
         "#define BUF_XY(i) vec2(texelFetch(uBx, (i)).x, texelFetch(uBy, (i)).x)\n")
    if rgb:
        t += ("uniform samplerBuffer uBr;\nuniform samplerBuffer uBg;\nuniform samplerBuffer uBb;\n"
              "#define BUF_RGB(i) vec3(texelFetch(uBr, (i)).x, texelFetch(uBg, (i)).x, texelFetch(uBb, (i)).x)\n")
    return t


def array_specs(rgb=False):
    """(uniform, CHOP op name, type) for the GLSL Arrays page (texturebuffer)."""
    if BUFFERS == 'packed':
        s = [('uXY', 'src_xy', 'vec2')]
        return s + [('uRGB', 'src_rgb', 'vec3')] if rgb else s
    s = [('uBx', 'sel_x', 'float'), ('uBy', 'sel_y', 'float')]
    return s + [('uBr', 'sel_r', 'float'), ('uBg', 'sel_g', 'float'), ('uBb', 'sel_b', 'float')] if rgb else s


def path_text(source, rgb=False, audio=False):
    t = glsl('path')
    t = t.replace('//@LIB', glsl('lib')).replace('//@BUF', buf_header(rgb))
    t = t.replace('//@AUDIO', glsl('audio') if audio else '').replace('//@SOURCE', glsl(source))
    return t


def engine_texts():
    return {'beam': defines() + glsl('beam').replace('//@LIB', glsl('lib')), 'glow': glsl('glow'),
            'look': glsl('look')}


# ------------------------------------------------------------------ pars shared by the beam modules
_PH = LG['PHOSPHORS']
BEAM_PAGES = [
    ('Beam', [
        ('Intensity', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Intensity (1 = a Lref-long line once per frame peaks at 1)'}),
        ('Beamwidth', 'Float', 1.5, {'min': 0.5, 'max': 6, 'label': 'Beam width (sigma, output px)'}),
        ('Dwell', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Dwell (1 = slow beam bright, 0 = even line)'}),
        ('Quality', 'Menu', 'half', {'names': LG['QUALITIES'], 'labels': ['Full res beam', 'Half res beam',
                                                                             'Quarter res beam'], 'label': 'Quality'}),
        ('Noise', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Trace noise (x 2 px jitter)'}),
        ('Budget', 'Int', 1024, {'min': 256, 'max': 16384, 'label': 'Hit budget per 32 px tile (segments)'}),
    ]),
    ('Phosphor', [
        ('Phosphor', 'Menu', 'p1', {'names': LG['PHOSPHOR_NAMES'], 'labels': LG['PHOSPHOR_LABELS'], 'label': 'Phosphor'}),
        ('Persist', 'Float', 0.08, {'min': 0, 'max': 3, 'label': 'Persistence tau (s, 0 = none)'}),
        ('Afterglow', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Afterglow'}),
        ('Flash', 'Float', 0.5, {'min': 0, 'max': 3, 'label': 'Flash (current beam, flash tint)'}),
        ('Tintr', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Custom tint R'}),
        ('Tintg', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Custom tint G'}),
        ('Tintb', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Custom tint B'}),
    ]),
    ('Display', [
        ('Size', 'Float', 0.9, {'min': 0.1, 'max': 1.5, 'label': 'Size (of the short side / canvas)'}),
        ('Aspect', 'Menu', 'square', {'names': ['square', 'fill'], 'labels': ['Square scope', 'Fill canvas'],
                                      'label': 'Aspect'}),
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre X'}),
        ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre Y'}),
        ('Rotate', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate (deg)'}),
        ('Exposure', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Exposure'}),
        ('Glow', 'Float', 0.5, {'min': 0, 'max': 3, 'label': 'Glow'}),
        ('Glowradius', 'Float', 1.0, {'min': 0.25, 'max': 4, 'label': 'Glow radius'}),
        ('Graticule', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Graticule'}),
        ('Gratstyle', 'Menu', 'scope', {'names': ['none', 'scope', 'polar', 'cross'],
                                        'labels': ['None', 'Scope grid + ticks', 'Polar rings', 'Cross only'],
                                        'label': 'Graticule style'}),
        ('Divisions', 'Int', 8, {'min': 2, 'max': 20, 'label': 'Divisions (short side)'}),
        ('Background', 'Menu', 'add', {'names': ['add', 'dim', 'black', 'screen'],
                                       'labels': ['Add over picture', 'Dim picture', 'Black', 'Scope screen'],
                                       'label': 'Background'}),
        ('Bgdim', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Picture dim (Dim)'}),
    ]),
]
BEAM_PANEL = ['Beam', 'Phosphor', 'Display']


def ph_list(i, field):
    """Expression: component i of a phosphor field ('A' afterglow, 'F' flash, 'M' tau mult, 'mono') by menu."""
    vals = []
    for _k, _l, A, F, M, mono in _PH:
        if field == 'mono':
            vals.append(repr(float(mono)))
        elif A is None:                                      # custom: from the Tint pars
            tint = P.format(('Tintr', 'Tintg', 'Tintb')[i])
            vals.append(tint if field == 'A' else ('(0.5 + 0.5 * %s)' % tint if field == 'F' else '1.0'))
        else:
            vals.append(repr(float({'A': A, 'F': F, 'M': M}[field][i])))
    return '[%s][%s]' % (', '.join(vals), MI.format('Phosphor'))


def panel_expr(k, src="op('in1')"):
    return LG['PANEL_LAMBDA'] + "(%s.width, %s.height, %s, %s, %s, %s)[%d]" % (
        src, src, P.format('Size'), MI.format('Aspect'), P.format('Centerx'), P.format('Centery'), k)


def beam_wh_expr(k, src="op('in1')"):
    return LG['BEAMWH_LAMBDA'] + "(%s, %s, %s)[%d]" % (panel_expr(2, src), panel_expr(3, src), LG['Q_EXPR'], k)


BW = "op('beam').par.resolutionw.eval()"
BH = "op('beam').par.resolutionh.eval()"
SIGMA = "max(0.35, %s * %s)" % (P.format('Beamwidth'), LG['Q_EXPR'])
DIV_EXPR = ("(lambda pw, ph, d, a: (d, d) if a == 0 else ((d, max(1, int(round(d * ph / pw)))) if pw <= ph else "
            "(max(1, int(round(d * pw / ph))), d)))(%s, %s, %s, %s)[%%d]" % (
                panel_expr(2, 'me.inputs[0]'), panel_expr(3, 'me.inputs[0]'), P.format('Divisions'), MI.format('Aspect')))


def path_uniforms():
    lref = "min(%s, %s)" % (BW, BH)
    return [
        ('uG', [BW, BH, "(%s if %s == 1 else %s) / 2.0" % (BW, MI.format('Aspect'), lref),
                "(%s if %s == 1 else %s) / 2.0" % (BH, MI.format('Aspect'), lref)]),
        ('uR', ["math.cos(math.radians(%s))" % P.format('Rotate'), "math.sin(math.radians(%s))" % P.format('Rotate'),
                "%s * 2.0 * %s" % (P.format('Noise'), LG['Q_EXPR']), 'absTime.frame']),
    ]


def beam_uniforms():
    w, h = "me.par.resolutionw.eval()", "me.par.resolutionh.eval()"       # own size: no me.width (T-117 (2))
    lref = "min(%s, %s)" % (w, h)
    return [
        ('uB', [SIGMA, "%s * %r * %s" % (lref, LG['SQ2PI'], SIGMA), P.format('Dwell'), lref]),
        ('uI', [P.format('Intensity'), ph_list(0, 'mono'), P.format('Budget'), '0']),
        ('uA', ["%s * %s" % (ph_list(i, 'A'), P.format('Afterglow')) for i in range(3)] + ['0']),
        ('uP', ["%s * %s" % (ph_list(i, 'M'), P.format('Persist')) for i in range(3)] + ['1.0 / project.cookRate']),
        ('uT', ['absTime.frame', 'max(2.0, round(0.25 * project.cookRate))', '0', '0']),
    ]


def look_uniforms(over=None):
    U = [
        ('uPn', [panel_expr(k, 'me.inputs[0]') for k in range(4)]),
        ('uE', [P.format('Exposure'), P.format('Glow'), P.format('Flash'), P.format('Amount')]),
        ('uF', [ph_list(i, 'F') for i in range(3)] + [MI.format('Background')]),
        ('uC', [ph_list(i, 'A') for i in range(3)] + [P.format('Bgdim')]),
        ('uGr', [P.format('Graticule'), MI.format('Gratstyle'), DIV_EXPR % 0, DIV_EXPR % 1]),
        ('uO', ['0', '0', '0', '0']), ('uO1', ['1', '1', '1', '0']), ('uO2', ['1', '1', '1', '0']),
    ]
    over = over or {}
    return [(n, over.get(n, e)) for n, e in U]


# ------------------------------------------------------------------ TD side
def setp(o, H, **kw):
    """Set pars that may differ by build; '=expr' sets an expression. Returns the missing par names."""
    missing = []
    for k, v in kw.items():
        p = getattr(o.par, k, None)
        if p is None:
            missing.append('%s.%s' % (o.name, k))
        elif isinstance(v, str) and v.startswith('='):
            H['expr'](p, v[1:])
        else:
            p.val = v
    return missing


def tidy(g, H):
    """A new GLSL TOP docks its own template DATs (T-115 (5)); keep only our `<name>_compute`."""
    for t in list(getattr(g, 'docked', None) or []):
        if t.name != g.name + '_compute':
            H['sd'](t)


def bind_arrays(g, specs):
    g.seq.array.numBlocks = max(int(g.seq.array.numBlocks), len(specs))
    for k, (un, chop, typ) in enumerate(specs):
        getattr(g.par, 'array%dname' % k).val = un
        getattr(g.par, 'array%dtype' % k).val = typ
        getattr(g.par, 'array%dchop' % k).val = chop
        getattr(g.par, 'array%darraytype' % k).val = 'texturebuffer'


def chan_chops(m, H, names, source_expr):
    """Fallback Constant `src_none` (channels named by the module's Chan pars, 0), one Select per channel (`sel_<k>`
    from source_expr, the channel named by its par) and Merges `src_xy` (+ `src_rgb`): channel order = merge order,
    whatever order the source CHOP has. names = [(key, select channel expr, fallback channel name expr)], key in
    x y r g b."""
    mk = H['mk']
    miss = []
    none = mk(m, constantCHOP, 'src_none')                      # noqa: F821 (TD global)
    none.seq.const.numBlocks = len(names)
    for k, (_key, _sexpr, nexpr) in enumerate(names):
        miss += setp(none, H, **{'const%dname' % k: '=' + nexpr, 'const%dvalue' % k: 0.0})
    none.comment = 'Fallback source (0, channels named like the Chan pars) when no CHOP is set.'
    sels = {}
    for key, sexpr, _nexpr in names:
        s = mk(m, selectCHOP, 'sel_' + key)                       # noqa: F821
        miss += setp(s, H, chops='=' + source_expr, channames='=' + sexpr)
        sels[key] = s
    groups = [('src_xy', ['x', 'y'])] + ([('src_rgb', ['r', 'g', 'b'])] if 'r' in sels else [])
    for nm, keys in groups:
        mg = mk(m, mergeCHOP, nm)                                 # noqa: F821
        for i, key in enumerate(keys):
            cn = mg.inputConnectors[i].connections
            if not cn or cn[0].owner != sels[key]:
                mg.inputConnectors[i].connect(sels[key])
        mg.comment = '%s in fixed order -> GLSL texture buffer (Arrays page).' % ' '.join(keys)
    return miss


def build_engine(m, H, source, rgb, audio, src_uniforms, look_over=None, chop_ops=()):
    """Path -> beam -> glow -> look -> out_sel -> out1 inside module instance m. Returns (stages, missing)."""
    mk, expr = H['mk'], H['expr']
    T = engine_texts()
    miss = []
    in1 = mk(m, inTOP, 'in1')                                     # noqa: F821
    path = H['compute'](m, 'path', path_text(source, rgb, audio), [], res=LG['PATH_WH'], fmt='rgba32float')
    bind_arrays(path, array_specs(rgb))
    H['uniforms'](path, path_uniforms() + src_uniforms)
    path.comment = ('Source -> up to %d points in beam px (x y weight rgb), chunk bboxes + count in row %d.'
                    % (LG['CAP'], LG['CAPROW']))
    beam = H['compute'](m, 'beam', T['beam'], [path], res=(64, 64), fmt='rgba32float')
    expr(beam.par.resolutionw, beam_wh_expr(0))
    expr(beam.par.resolutionh, beam_wh_expr(1))
    miss += setp(beam, H, outputaccess='readwrite', clearoutputs=False, numcolorbufs=2, autodispatchsize=False,
                 dispatchsizex='=(int(me.par.resolutionw.eval()) + 31) // 32',
                 dispatchsizey='=(int(me.par.resolutionh.eval()) + 31) // 32', dispatchsizez=1)
    H['uniforms'](beam, beam_uniforms())
    beam.comment = ('Beam + phosphor state in place (rgb afterglow, a flash); buffer 1 = per-texel frame stamp '
                    '(repeat cooks keep, gaps reset). Size = panel x Quality.')
    glow = H['compute'](m, 'glow', T['glow'], [beam], res=(8, 8), fmt='rgba16float')
    expr(glow.par.resolutionw, "(int(%s) + 7) // 8" % BW)
    expr(glow.par.resolutionh, "(int(%s) + 7) // 8" % BH)
    miss += setp(glow, H, inputfiltertype='mipmap', inputextenduv='hold')
    H['uniforms'](glow, [('uF', [ph_list(i, 'F') for i in range(3)] + [P.format('Flash')]),
                         ('uGl', [P.format('Glowradius'), '3', '0', '0'])])
    glow.comment = 'Glow: 1/8 of the beam buffer from mip lod 3, near + wide 7x7 Gaussians. Pulled only while Glow > 0.'
    gn = mk(m, constantTOP, 'glow_none')                          # noqa: F821
    gn.par.outputresolution = 'custom'
    gn.par.resolutionw, gn.par.resolutionh = 1, 1
    gn.par.colorr = gn.par.colorg = gn.par.colorb = 0
    gn.par.alpha = 0
    gs = mk(m, switchTOP, 'glow_src')                             # noqa: F821
    gs.inputConnectors[0].connect(gn)
    gs.inputConnectors[1].connect(glow)
    expr(gs.par.index, '1 if %s > 0 else 0' % P.format('Glow'))
    for g in (path, beam, glow):
        tidy(g, H)
    look = H['compute'](m, 'look', T['look'], [in1, beam, gs])
    tidy(look, H)
    miss += setp(look, H, inputfiltertype='linear', inputextenduv='hold')
    H['uniforms'](look, look_uniforms(look_over))
    look.comment = 'Tone map 1 - exp(-x), graticule, background mode, Amount. Outside the panel = in1 exact.'
    sel = mk(m, switchTOP, 'out_sel')                             # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(look)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact (path / beam / glow / look not pulled).'
    out1 = mk(m, outTOP, 'out1')                                  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    stages = [
        {'title': '1 In + source', 'role': 'input', 'ops': ['in1'] + list(chop_ops),
         'body': 'Picture in; the CHOPs that feed the path pass (texture buffers).'},
        {'title': '2 Path', 'role': 'process', 'ops': ['path', 'path_compute'],
         'body': 'Module source -> points in beam px + chunk bboxes.'},
        {'title': '3 Beam + phosphor', 'role': 'process', 'ops': ['beam', 'beam_compute'],
         'body': 'Tile-binned Gaussian beam (erf), dwell, phosphor decay in place.'},
        {'title': '4 Glow', 'role': 'process', 'ops': ['glow', 'glow_compute', 'glow_none', 'glow_src']},
        {'title': '5 Look', 'role': 'process', 'ops': ['look', 'look_compute'],
         'body': 'Tone map, graticule, background, Amount.'},
        {'title': '6 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
    return stages, miss
