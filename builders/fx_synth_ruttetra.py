# fx_synth_ruttetra - FX_synth module 'ruttetra' (FX2 AV-26 Rutt/Etra scan processor). Template:
# docs/builds/fx_glitch.md "Module template" (rack = builders/fx_synth.py); doc + LIVE CHECKS: docs/builds/fx_synth.md.
# The picture's voltages are added to the deflection of a raster of Lines scan lines (x' = x + Defx * s1,
# y' = y + Defy * s2, wave + per-line jitter generators), the beam brightness stays the picture (Blank = beam off
# below a luma); the raster is scaled / sheared / rotated, and Yaw / Pitch / Persp with Z = relief give the
# td-port JZBN_RuttLines 3D look (read-only idea source; that one is a per-pixel ribbon search, this one is real
# geometry: GPU vertex displacement, the derivative forum / v002 route, no TOP -> CHOP).
# Network: in1 -> mat (GLSL MAT: builders/glsl/fx_synth_rutt_vert.glsl + _pixel.glsl, sampler sSrc = in1) on geo
# (Grid SOP 2 x Samples ribbon, instanced Lines times) -> render (Render TOP, additive, 16f, input res) -> post
# (compute: mip glow + phosphor persistence via fb) -> outc (compute: background black / input / transparent,
# Amount) -> out_sel (Amount 0 = in1, nothing renders) -> out1. Maths = builders/fx_synth_logic.py rt_place(). ASCII.
import os

MODULE = 'ruttetra'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
SHADERS = {'mat': 'rutt_vert', 'mat_pixel': 'rutt_pixel', 'post': 'rutt_post', 'outc': 'rutt_outc'}
SIGNALS = ['luma', 'red', 'green', 'blue', 'inverse_luma']
SIGNAL_LABELS = ['Luma', 'Red', 'Green', 'Blue', 'Inverse luma']

PAGES = [
    ('Rutt', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Lines', 'Int', 96, {'min': 16, 'max': 512, 'label': 'Scan lines'}),
        ('Samples', 'Int', 256, {'min': 64, 'max': 1024, 'label': 'Samples per line'}),
        ('Width', 'Float', 1.5, {'min': 0.5, 'max': 8, 'label': 'Beam width px'}),
        ('Intensity', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Beam intensity'}),
        ('Blank', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Blank below luma'}),
        ('Scan', 'Menu', 'horizontal', {'names': ['horizontal', 'vertical'], 'labels': ['Horizontal', 'Vertical']}),
        ('Colour', 'Menu', 'video', {'names': ['video', 'mono', 'heat', 'line'],
                                     'labels': ['Video', 'Mono phosphor', 'Heat (by luma)', 'Rainbow by line']}),
        ('Monor', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Mono R'}),
        ('Monog', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Mono G'}),
        ('Monob', 'Float', 0.45, {'min': 0, 'max': 1, 'label': 'Mono B'}),
    ]),
    ('Deflect', [
        ('Defxsrc', 'Menu', 'luma', {'names': SIGNALS, 'labels': SIGNAL_LABELS, 'label': 'Deflect X source'}),
        ('Defx', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Deflect X (heights)'}),
        ('Defysrc', 'Menu', 'luma', {'names': SIGNALS, 'labels': SIGNAL_LABELS, 'label': 'Deflect Y source'}),
        ('Defy', 'Float', 0.12, {'min': -2, 'max': 2, 'label': 'Deflect Y (heights)'}),
        ('Z', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Z relief (luma)'}),
        ('Wave', 'Float', 0.0, {'min': 0, 'max': 0.2, 'label': 'Wave amp (heights)'}),
        ('Wavefreq', 'Float', 4.0, {'min': 0, 'max': 40, 'label': 'Wave cycles per line'}),
        ('Wavespeed', 'Float', 0.5, {'min': -4, 'max': 4, 'label': 'Wave speed (cycles/s)'}),
        ('Jitter', 'Float', 0.0, {'min': 0, 'max': 0.05, 'label': 'Line jitter (heights)'}),
        ('Jitterrate', 'Float', 0.0, {'min': 0, 'max': 30, 'label': 'Jitter rate Hz (0 = fixed)'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 99, 'label': 'Seed'}),
    ]),
    ('Raster', [
        ('Rotate', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Raster rotate deg'}),
        ('Scalex', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Raster scale X'}),
        ('Scaley', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Raster scale Y'}),
        ('Shear', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Raster shear'}),
        ('Offsetx', 'Float', 0.0, {'min': -0.5, 'max': 0.5, 'label': 'Offset X (heights)'}),
        ('Offsety', 'Float', 0.0, {'min': -0.5, 'max': 0.5, 'label': 'Offset Y (heights)'}),
        ('Yaw', 'Float', 0.0, {'min': -60, 'max': 60, 'label': 'Camera yaw deg'}),
        ('Pitch', 'Float', 0.0, {'min': -60, 'max': 60, 'label': 'Camera pitch deg'}),
        ('Persp', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Perspective'}),
    ]),
    ('Glow', [
        ('Glow', 'Float', 0.6, {'min': 0, 'max': 2, 'label': 'Glow'}),
        ('Persist', 'Float', 0.0, {'min': 0, 'max': 0.98, 'label': 'Phosphor persistence'}),
        ('Background', 'Menu', 'black', {'names': ['black', 'input', 'transparent'],
                                         'labels': ['Black', 'Input (dimmed)', 'Transparent']}),
        ('Bgdim', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Input under the lines'}),
    ]),
]
PANEL_PAGES = ['Rutt', 'Deflect', 'Raster', 'Glow']

_Z = {'Lines': 96, 'Samples': 256, 'Width': 1.5, 'Intensity': 1.0, 'Blank': 0.0, 'Scan': 0, 'Colour': 0,
      'Defxsrc': 0, 'Defx': 0.0, 'Defysrc': 0, 'Defy': 0.12, 'Z': 0.0, 'Wave': 0.0, 'Wavefreq': 4.0,
      'Wavespeed': 0.5, 'Jitter': 0.0, 'Jitterrate': 0.0, 'Seed': 1, 'Rotate': 0.0, 'Scalex': 1.0, 'Scaley': 1.0,
      'Shear': 0.0, 'Offsetx': 0.0, 'Offsety': 0.0, 'Yaw': 0.0, 'Pitch': 0.0, 'Persp': 0.0, 'Glow': 0.6,
      'Persist': 0.0, 'Background': 0, 'Bgdim': 0.25}
PRESETS = [
    (1, 'classic relief', dict(_Z, Amount=1.0, Lines=120, Defy=0.08, Z=0.25, Pitch=35.0, Persp=0.4,
                               Colour=1, Glow=0.8)),
    (2, 'sideways scan', dict(_Z, Amount=1.0, Scan=1, Lines=90, Defy=0.0, Defx=0.1, Width=1.2, Glow=0.6)),
    (3, 'face wire', dict(_Z, Amount=1.0, Lines=160, Samples=384, Width=1.0, Defy=0.05, Blank=0.08,
                          Intensity=1.4, Glow=0.5, Persist=0.6)),
    (4, 'wave raster', dict(_Z, Amount=1.0, Lines=64, Defy=0.06, Wave=0.012, Wavefreq=6.0, Wavespeed=1.0,
                            Jitter=0.004, Jitterrate=12.0, Colour=3, Glow=0.9)),
    (5, 'rotating raster', dict(_Z, Amount=1.0, Lines=100, Defy=0.1, Defx=0.05, Defxsrc=1, Rotate=25.0,
                                Shear=0.2, Scalex=0.9, Scaley=0.9, Colour=2, Glow=0.7, Persist=0.4)),
]

P = 'parent().par.{}.eval()'
MI = 'parent().par.{}.menuIndex'


def _glsl(stem):
    with open(os.path.join(_HERE, 'glsl', 'fx_synth_%s.glsl' % stem)) as fh:
        return fh.read()


def uniforms(name='mat'):
    """Uniform rows per pass: 'mat' (GLSL MAT, vertex + pixel), 'post', 'outc'. Names = the shader declarations."""
    if name == 'post':
        return [('uA', [P.format('Glow'), P.format('Persist'), '0', '0'])]
    if name == 'outc':
        return [('uA', [P.format('Amount'), MI.format('Background'), P.format('Bgdim'), '0'])]
    moving = '({} != 0 or ({} != 0 and {} > 0))'.format(P.format('Wave'), P.format('Jitter'), P.format('Jitterrate'))
    return [
        ('uA', [P.format('Lines'), P.format('Samples'), P.format('Width'), P.format('Intensity')]),
        ('uB', [P.format('Blank'), MI.format('Scan'), MI.format('Colour'), '0']),
        ('uC', [MI.format('Defxsrc'), P.format('Defx'), MI.format('Defysrc'), P.format('Defy')]),
        ('uD', [P.format('Z'), P.format('Wave'), P.format('Wavefreq'), P.format('Wavespeed')]),
        ('uE', [P.format('Jitter'), P.format('Jitterrate'), P.format('Seed'),
                'absTime.seconds if %s else 0' % moving]),
        ('uF', [P.format('Rotate'), P.format('Scalex'), P.format('Scaley'), P.format('Shear')]),
        ('uG', [P.format('Offsetx'), P.format('Offsety'), P.format('Yaw'), P.format('Pitch')]),
        ('uH', [P.format('Persp'), P.format('Monor'), P.format('Monog'), P.format('Monob')]),
        ('uR', ["op('in1').width", "op('in1').height", '0', '0']),
    ]


def _set(par_owner, name, value):
    p = getattr(par_owner.par, name, None)
    if p is not None:
        try:
            p.val = value
        except Exception:
            pass
    return p is not None


def _material(m, H):
    mk, expr, sd = H['mk'], H['expr'], H['sd']
    mat = mk(m, glslMAT, 'mat')                       # MAT first: its auto-docked DATs are reused / removed
    vd = mk(m, textDAT, 'mat_vertex')
    vd.text = _glsl('rutt_vert')
    vd.dock = mat
    pd = mk(m, textDAT, 'mat_pixel')
    pd.text = _glsl('rutt_pixel')
    pd.dock = mat
    for dn in ('mat_info', 'mat_compute'):
        if m.op(dn) is not None and m.op(dn).dock == mat:
            sd(m.op(dn))
    mat.par.vdat = vd.name
    mat.par.pdat = pd.name
    U = uniforms('mat')
    mat.seq.vec.numBlocks = max(int(mat.seq.vec.numBlocks), len(U))
    for k, (un, ex) in enumerate(U):
        getattr(mat.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            expr(getattr(mat.par, 'vec{}value{}'.format(k, comp)), e)
    mat.seq.sampler.numBlocks = max(int(mat.seq.sampler.numBlocks), 1)
    mat.par.sampler0name = 'sSrc'
    mat.par.sampler0top = 'in1'
    for pn, v in (('sampler0filter', 'linear'), ('sampler0extendu', 'hold'), ('sampler0extendv', 'hold')):
        _set(mat, pn, v)
    mat.par.blending = True
    _set(mat, 'srcblend', 'one')
    _set(mat, 'destblend', 'one')
    _set(mat, 'srcblenda', 'one')
    _set(mat, 'destblenda', 'one')
    mat.par.depthtest = False
    mat.par.depthwriting = False
    _set(mat, 'postmultalpha', False)
    mat.comment = 'Rutt/Etra beam: deflects every ribbon vertex by the picture (sSrc = in1), additive.'
    return mat


def _geometry(m, H):
    mk, expr, sd = H['mk'], H['expr'], H['sd']
    geo = mk(m, geometryCOMP, 'geo')
    for ch in list(geo.children):
        if ch.name != 'ribbon':
            sd(ch)
    g = geo.op('ribbon')
    if g is None or g.OPType != 'gridSOP':
        if g is not None:
            sd(g)
        g = geo.create(gridSOP, 'ribbon')
    _set(g, 'orient', 'xy')
    g.par.sizex, g.par.sizey = 1, 1
    g.par.rows = 2
    expr(g.par.cols, 'max(2, int(parent(2).par.Samples.eval()))')
    g.render = True
    g.display = True
    geo.par.instancing = True
    _set(geo, 'instancecountmode', 'manual')
    expr(geo.par.numinstances, 'max(1, int(%s))' % P.format('Lines'))
    geo.par.material = 'mat'                         # T-81: Geometry COMP OP pars resolve from its parent
    geo.comment = 'One 2 x Samples ribbon (Grid SOP), instanced Lines times; mat places every vertex.'
    return geo


def build(m, H):
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    _material(m, H)
    _geometry(m, H)
    cam = mk(m, cameraCOMP, 'cam')
    cam.comment = 'Required by the Render TOP; unused (the vertex shader writes clip space itself).'
    r = mk(m, renderTOP, 'render')
    r.par.camera = 'cam'
    r.par.geometry = 'geo'
    r.par.lights = ''
    r.par.outputresolution = 'custom'
    expr(r.par.resolutionw, "op('in1').width")
    expr(r.par.resolutionh, "op('in1').height")
    r.par.format = 'rgba16float'
    names = list(r.par.antialias.menuNames)
    r.par.antialias = 'aa1x' if 'aa1x' in names else names[0]
    r.par.bgcolorr = r.par.bgcolorg = r.par.bgcolorb = 0
    r.par.bgcolora = 0
    _set(r, 'cullface', 'neither')
    r.comment = 'Scan lines, additive, 16f, the input resolution.'
    fb = mk(m, feedbackTOP, 'fb')
    fb.inputConnectors[0].connect(r)
    post = H['compute'](m, 'post', _glsl('rutt_post'), [r, fb], fmt='rgba16float')
    post.par.inputfiltertype = 'mipmap'
    H['uniforms'](post, uniforms('post'))
    post.comment = 'Glow (render mips 1-5) + phosphor persistence (max with fb x Persist).'
    fb.par.top = 'post'
    fb.comment = 'Previous post (phosphor). Restarts from the render after a reset.'
    oc = H['compute'](m, 'outc', _glsl('rutt_outc'), [in1, post])
    H['uniforms'](oc, uniforms('outc'))
    oc.comment = 'Background (black / dimmed input / transparent) + beams, Amount, input format.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(oc)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exactly (nothing renders).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Scan raster', 'role': 'process', 'ops': ['mat', 'mat_vertex', 'mat_pixel', 'geo', 'cam',
                                                              'render'],
         'body': 'GLSL MAT deflects Lines x Samples ribbon vertices by the picture; Render TOP adds the beams.'},
        {'title': '3 Glow', 'role': 'process', 'ops': ['fb', 'post', 'post_compute'],
         'body': 'Mip glow + phosphor persistence (16f state).'},
        {'title': '4 Out', 'role': 'output', 'ops': ['outc', 'outc_compute', 'out_sel', 'out1']},
    ]
