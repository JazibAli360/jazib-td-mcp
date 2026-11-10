# gen_clone builder - GEN_clone (G-CLONE, FX0 row 70): a MoGraph / Notch style cloner COMP.
#   Clones of a shape (card with a TOP on it, box, sphere, torus, any SOP) laid out in grid / radial / linear / path /
#   points / random modes; per-clone modifiers by index (step), hash (random) and noise; per-clone time offset (cards
#   show older frames from a Texture 3D ring; modifier animation runs late per clone); the shared effectors
#   (/project1/effectors, builders/effectors.py helpers) push / rotate / scale / tint / delay / hide clones by
#   falloff weight; an optional map TOP tints or scales clones by where they sit.
#   GPU path: `clones` compute TOP (5 texels per clone) -> Geometry COMP instancing (manual count, no instance OPs,
#   no POP buffers, T-124) -> GLSL MAT reads the clone texture by TDInstanceID() -> Render TOP -> out1.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/gen_clone.py').read(), ns)
#   ns['build']('/project1/lab')            # idempotent; panel=False skips the zkit panel
# T-70 safe (effectors.py _mk / _sd = safe_destroy; pane never moved). Pure logic + mirror: builders/gen_clone_logic.py.
# Doc: docs/builds/gen_clone.md. ASCII only.
import os
import sys

NAME = 'GEN_clone'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
GLSL = os.path.join(HERE, 'glsl')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
EFF_FILE = os.path.join(HERE, 'effectors.py')
TEST_TEX = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4'
PP = 'parent().par.'


def load_logic():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    ns = {'__name__': 'gen_clone_logic_build'}
    path = os.path.join(HERE, 'gen_clone_logic.py')
    with open(path) as fh:
        exec(compile(fh.read(), path, 'exec'), ns)
    return ns


def _read(p):
    with open(p) as fh:
        return fh.read()


def _m(names, labels, label):
    return {'names': names, 'labels': labels, 'label': label}


def pages(Lg):
    D = Lg['DEFAULTS']
    F = lambda n, lo, hi, label: (n, 'Float', D[n], {'min': lo, 'max': hi, 'label': label})      # noqa: E731
    X = lambda n, lo, hi, label: (n, 'XYZ', (D[n + 'x'], D[n + 'y'], D[n + 'z']),                 # noqa: E731
                                  {'min': lo, 'max': hi, 'label': label})
    return [
        ('Clone', [
            ('Mode', 'Menu', D['Mode'], _m(Lg['MODES'], ['Grid', 'Radial', 'Linear', 'Along a path', 'On points',
                                                         'Random (box)'], 'Mode')),
            ('Count', 'Int', D['Count'], {'min': 1, 'max': 400, 'label': 'Count (radial / linear / path / random)'}),
            ('Countx', 'Int', D['Countx'], {'min': 1, 'max': 40, 'label': 'Grid count x'}),
            ('County', 'Int', D['County'], {'min': 1, 'max': 40, 'label': 'Grid count y'}),
            ('Countz', 'Int', D['Countz'], {'min': 1, 'max': 40, 'label': 'Grid count z'}),
            X('Space', 0, 2, 'Grid spacing'),
            F('Radius', 0, 4, 'Radial radius'),
            F('Arcstart', -360, 360, 'Arc start deg'),
            F('Arcend', -360, 720, 'Arc end deg (360 = full ring)'),
            ('Plane', 'Menu', D['Plane'], _m(Lg['PLANES'], ['XY (facing camera)', 'XZ (floor)', 'YZ'], 'Plane')),
            X('Lin', -2, 2, 'Linear step offset'),
            ('Centre', 'Toggle', bool(D['Centre']), {'label': 'Linear: centred on the origin'}),
            ('Pathshape', 'Menu', D['Pathshape'], _m(Lg['PATHS'], ['Circle', 'Line', 'Lissajous 3:2', 'Spiral',
                                                                   'Helix', 'Points (SOP / CHOP / TOP)'],
                                                     'Path shape')),
            F('Pathsize', 0, 4, 'Path size (radius / half length)'),
            F('Pathturns', 0, 12, 'Spiral / helix turns'),
            F('Pathstart', 0, 1, 'Path start'),
            F('Pathend', 0, 1, 'Path end'),
            F('Pathspeed', -2, 2, 'Path travel (per s)'),
            F('Helixheight', 0, 8, 'Helix height'),
            ('Pointsource', 'Menu', 'sop', _m(Lg['PTSOURCES'], ['SOP points', 'CHOP (tx ty tz / x y z)',
                                                                'TOP (rgb = xyz, GPU)'], 'Points from')),
            ('Pointsop', 'Str', '', {'label': 'Points SOP path'}),
            ('Pointchop', 'Str', '', {'label': 'Points CHOP path'}),
            ('Pointtop', 'Str', '', {'label': 'Points TOP path'}),
            ('Pointstep', 'Int', D['Pointstep'], {'min': 1, 'max': 64, 'label': 'Every Nth point'}),
            ('Pathsamples', 'Int', 256, {'min': 2, 'max': 4096, 'label': 'Path resample (points path)'}),
            X('Box', 0, 8, 'Random box size'),
            ('Seed', 'Int', D['Seed'], {'min': 0, 'max': 999, 'label': 'Seed'}),
            ('Align', 'Toggle', bool(D['Align']), {'label': 'Align to layout (outward / tangent)'}),
            ('Alignaxis', 'Menu', D['Alignaxis'], _m(Lg['AXES'], ['X', 'Y (card up)', 'Z'], 'Axis that aligns')),
        ]),
        ('Look', [
            ('Source', 'Menu', 'card', _m(Lg['SOURCES'], ['Card (TOP)', 'Box', 'Sphere', 'Torus', 'Any SOP'],
                                          'Clone shape')),
            ('Sourcesop', 'Str', '', {'label': 'SOP path (Source = sop)'}),
            ('Texsource', 'Menu', 'auto', _m(Lg['TEXSOURCES'], ['Auto (in1 if wired)', 'Test clip', 'TOP path'],
                                             'Card picture')),
            ('Textop', 'Str', '', {'label': 'Card TOP path'}),
            F('Size', 0, 2, 'Size (uniform)'),
            X('Scale', 0, 4, 'Scale per axis'),
            ('Colour', 'RGB', (D['Colourr'], D['Colourg'], D['Colourb']), {'label': 'Colour'}),
            F('Alpha', 0, 1, 'Alpha'),
            ('Shading', 'Menu', 'lambert', _m(Lg['SHADINGS'], ['Flat', 'Headlight'], 'Shading')),
            ('Ambient', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Ambient (headlight)'}),
            ('Alphacut', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Discard alpha below'}),
            ('Blend', 'Menu', 'over', _m(['over', 'add', 'opaque'], ['Over (premultiplied)', 'Add', 'Opaque (depth)'],
                                         'Blend')),
            ('Mapmode', 'Menu', D['Mapmode'], _m(Lg['MAPMODES'], ['Off', 'Tint by map', 'Scale by map luma',
                                                                  'Both'], 'Map TOP')),
            ('Maptop', 'Str', '', {'label': 'Map TOP path'}),
            F('Mapamount', 0, 2, 'Map amount'),
            F('Mapsize', 0.1, 8, 'Map size (world units across)'),
        ]),
        ('Modifiers', [
            X('Stepr', -45, 45, 'Step rotate deg per clone'),
            F('Stepscale', -0.1, 0.1, 'Step scale per clone'),
            F('Stephue', -0.1, 0.1, 'Step hue (turns per clone)'),
            X('Randp', 0, 2, 'Random position'),
            X('Randr', 0, 180, 'Random rotation deg'),
            F('Randscale', 0, 1, 'Random scale'),
            F('Randhue', 0, 1, 'Random hue (turns)'),
            F('Noisepos', 0, 2, 'Noise position'),
            F('Noiserot', 0, 180, 'Noise rotation deg'),
            F('Noisescale', 0, 1, 'Noise scale'),
            F('Noisefreq', 0, 8, 'Noise frequency (per unit)'),
            F('Noisespeed', -4, 4, 'Noise speed'),
            F('Timeoffset', 0, 8, 'Time offset (frames per step)'),
            ('Timemode', 'Menu', D['Timemode'], _m(Lg['TIMEMODES'], ['By index', 'Random', 'By distance'],
                                                   'Time offset by')),
            ('Timedepth', 'Int', 30, {'min': 2, 'max': 120, 'label': 'Card frame ring (frames)'}),
            ('Ringorder', 'Menu', 'newestlast', _m(Lg['RINGORDER'], ['Newest = last slice', 'Newest = first slice'],
                                                   'Ring slice order (LIVE CHECK C9)')),
        ]),
        ('Render', [
            ('Resw', 'Int', 1080, {'min': 16, 'max': 3840, 'label': 'Width'}),
            ('Resh', 'Int', 1920, {'min': 16, 'max': 3840, 'label': 'Height'}),
            ('Camdist', 'Float', 6.0, {'min': 0.5, 'max': 30, 'label': 'Camera distance'}),
            ('Fov', 'Float', 45.0, {'min': 5, 'max': 120, 'label': 'Vertical FOV deg'}),
            ('Camrx', 'Float', 0.0, {'min': -89, 'max': 89, 'label': 'Camera tilt deg'}),
            ('Camry', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Camera orbit deg'}),
            ('Camspin', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Orbit speed deg/s'}),
            ('Ortho', 'Toggle', False, {'label': 'Orthographic'}),
            ('Orthowidth', 'Float', 3.0, {'min': 0.1, 'max': 20, 'label': 'Ortho width'}),
            ('Bg', 'RGB', (0.0, 0.0, 0.0), {'label': 'Background'}),
            ('Bgalpha', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Background alpha (0 = transparent out)'}),
            ('Antialias', 'Toggle', True, {'label': 'Antialias (4x)'}),
        ]),
    ]


def eff_page(E):
    L = E['_logic']()
    return L['CONSUMER_PAGE'] + [
        ('Effoff', 'XYZ', (0.0, 0.0, 0.0), {'min': -2, 'max': 2, 'label': 'Offset x weight'}),
        ('Effpush', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Push (away from the effector)'}),
        ('Effrot', 'XYZ', (0.0, 0.0, 0.0), {'min': -180, 'max': 180, 'label': 'Rotate deg x weight'}),
        ('Effscale', 'Float', 1.0, {'min': -1, 'max': 4, 'label': 'Scale (x 1 + s w; -1 = vanish)'}),
        ('Effcolour', 'RGB', (1.0, 0.3, 0.1), {'label': 'Tint colour'}),
        ('Effcolourmix', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Tint x weight'}),
        ('Efftime', 'Float', 0.0, {'min': -30, 'max': 30, 'label': 'Time offset frames x weight'}),
        ('Effhide', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Hide at weight (0 = off)'}),
    ]


PANEL_PAGES = ['Clone', 'Look', 'Modifiers', 'Effectors']


def presets(Lg):
    """Full states (T-124 (1)): DEFAULTS (menus as indices) + the preset's own values."""
    D = Lg['DEFAULTS']

    def st(**kw):
        v = {}
        for k, x in list(D.items()) + list(kw.items()):
            if k in Lg['MENUS']:
                v[k] = Lg['MENUS'][k].index(x) if isinstance(x, str) else x
            else:
                v[k] = float(x)
        return v
    return [
        (1, 'card wall', st()),
        (2, 'ring of cards', st(Mode='radial', Count=16, Radius=1.3, Align=1, Size=0.4, Timeoffset=2.0)),
        (3, 'helix boxes', st(Mode='path', Pathshape='helix', Count=120, Pathturns=4.0, Pathsize=0.9,
                              Helixheight=4.0, Size=0.12, Align=1, Alignaxis='x', Stephue=0.008, Noiserot=40.0)),
        (4, 'noise field', st(Countx=9, County=16, Spacex=0.27, Spacey=0.27, Size=0.22, Noisepos=0.15,
                              Noiserot=60.0, Noisescale=0.6, Noisefreq=1.2, Noisespeed=0.4)),
        (5, 'scatter', st(Mode='random', Count=200, Size=0.12, Randrx=90.0, Randry=90.0, Randrz=90.0, Randscale=0.6, Randhue=0.3, Seed=7)),
        (6, 'stagger line', st(Mode='linear', Count=24, Liny=0.15, Steprz=7.5, Stepscale=-0.02, Timeoffset=1.0)),
    ]


# ------------------------------------------------------------------ TD side
def _eff_ns():
    ns = dict(globals())
    exec(_read(EFF_FILE), ns)
    return ns


def _menu_val(par, *names):
    have = list(getattr(par, 'menuNames', []) or [])
    for n in names:
        if not have or n in have:
            par.val = n
            return n
    return None


SCRIPT_PTS = """# pts_chop: clone points (x y z w) from the Points SOP / CHOP (gen_clone_logic.pts_resample for a points path).
# Cooks when its source changes. Big SOPs (> ~20k points) are Python-heavy: use Pointsource top (GPU) for those.
def onSetupParameters(scriptOp):
    return

def onCook(scriptOp):
    L = op('clone_logic').module
    c = parent()
    src = c.par.Pointsource.eval()
    pts = []
    if src == 'sop':
        s = op(c.par.Pointsop.eval()) if c.par.Pointsop.eval() else None
        if s is not None and s.family == 'SOP':
            pts = [(p.P[0], p.P[1], p.P[2]) for p in s.points]
    elif src == 'chop':
        ch = op(c.par.Pointchop.eval()) if c.par.Pointchop.eval() else None
        if ch is not None and ch.family == 'CHOP':
            for names in (('tx', 'ty', 'tz'), ('x', 'y', 'z'), ('P0', 'P1', 'P2')):
                if all(ch[n] is not None for n in names):
                    xs, ys, zs = (ch[n].vals for n in names)
                    pts = list(zip(xs, ys, zs))
                    break
    if c.par.Mode.eval() == 'path' and c.par.Pathshape.eval() == 'points' and len(pts) > 1:
        pts = L.pts_resample(pts, int(c.par.Pathsamples.eval()))
    if not pts:
        pts = [(0.0, 0.0, 0.0)]
    scriptOp.clear()
    scriptOp.numSamples = len(pts)
    for k, n in enumerate('xyz'):
        scriptOp.appendChan(n).vals = [p[k] for p in pts]
    scriptOp.appendChan('w').vals = [1.0] * len(pts)
    return
"""


def _script(E, c, name, text):
    s = E['_mk'](c, scriptCHOP, name)
    cb = c.op(name + '_callbacks')
    if cb is None or cb.OPType != 'textDAT':
        cb = E['_mk'](c, textDAT, name + '_callbacks', viewer=False)
    if cb.text != text:
        cb.text = text
    cb.dock = s
    s.par.callbacks = cb.name
    return s


def _const_top(E, c, name, rgba, fmt='rgba32float'):
    k = E['_mk'](c, constantTOP, name)
    k.par.outputresolution = 'custom'
    k.par.resolutionw, k.par.resolutionh = 1, 1
    k.par.colorr, k.par.colorg, k.par.colorb = rgba[:3]
    k.par.alpha = rgba[3]
    k.par.format = fmt
    return k


def _inputs(E, c):
    mk, ex, wire = E['_mk'], E['_expr'], E['_wire']
    in1 = mk(c, inTOP, 'in1')
    tt = mk(c, moviefileinTOP, 'tex_test')
    tt.par.file = TEST_TEX
    ex(tt.par.play, "parent().op('tex_src').par.index.eval() == 0 and parent().par.Source.eval() == 'card'")
    tt.comment = 'Card test picture: stored 5 s webcam clip (plays only while used).'
    ts = mk(c, selectTOP, 'tex_sel')
    ex(ts.par.top, "parent().par.Textop.eval() or 'tex_test'")
    tsrc = mk(c, switchTOP, 'tex_src')
    for i, s in enumerate((tt, in1, ts)):
        wire(s, tsrc, i)
    ex(tsrc.par.index, "{'test': 0, 'top': 2}.get(parent().par.Texsource.eval(), 1 if any(len(cn.connections) for cn "
                       "in parent().inputConnectors if cn.inOP is not None and cn.inOP.name == 'in1') else 0)")
    tsrc.comment = 'Card picture: in1 (auto when wired), the test clip or any TOP path.'
    ring = mk(c, texture3dTOP, 'ring')
    wire(tsrc, ring, 0)
    ring.par.type = 'texture3d'
    on = ("(parent().par.Source.eval() == 'card' and (parent().par.Timeoffset.eval() != 0 or "
          "parent().par.Efftime.eval() != 0))")
    ex(ring.par.cachesize, "max(2, int(parent().par.Timedepth.eval())) if %s else 1" % on)
    ring.par.outputresolution = 'custom'
    ex(ring.par.resolutionw, "op('tex_src').width if %s else 8" % on)
    ex(ring.par.resolutionh, "op('tex_src').height if %s else 8" % on)
    ring.comment = 'Card frame ring (Timedepth slices) while a time offset is on; else 1 slice of 8x8 (costs ~0).'
    pts = _script(E, c, 'pts_chop', SCRIPT_PTS)
    pts.comment = 'Clone points / path from the Points SOP or CHOP (x y z w per sample).'
    ptop = mk(c, choptoTOP, 'pts_ctop')
    ptop.par.chop = pts.name
    ptop.par.dataformat = 'rgba'
    ptop.par.format = 'rgba32float'
    pnone = _const_top(E, c, 'pts_none', (0.0, 0.0, 0.0, 1.0))
    psel = mk(c, selectTOP, 'pts_tsel')
    ex(psel.par.top, "parent().par.Pointtop.eval() or 'pts_none'")
    psrc = mk(c, switchTOP, 'pts_src')
    for i, s in enumerate((pnone, ptop, psel)):
        wire(s, psrc, i)
    ex(psrc.par.index, "0 if not (parent().par.Mode.eval() == 'points' or (parent().par.Mode.eval() == 'path' and "
                       "parent().par.Pathshape.eval() == 'points')) else (2 if parent().par.Pointsource.eval() == "
                       "'top' else 1)")
    psrc.comment = 'Point texture for points / points-path modes (else 1x1: the Script CHOP is not pulled).'
    mnone = _const_top(E, c, 'map_none', (1.0, 1.0, 1.0, 1.0), fmt='rgba8fixed')
    msel = mk(c, selectTOP, 'map_sel')
    ex(msel.par.top, "parent().par.Maptop.eval() or 'map_none'")
    msrc = mk(c, switchTOP, 'map_src')
    wire(mnone, msrc, 0)
    wire(msel, msrc, 1)
    ex(msrc.par.index, "1 if parent().par.Mapmode.eval() != 'off' and parent().par.Maptop.eval() else 0")
    return tsrc, ring, psrc, msrc


def _clones(E, c, Lg, psrc, msrc):
    mk, ex, wire = E['_mk'], E['_expr'], E['_wire']
    EL = E['_logic']()
    code = mk(c, textDAT, 'clones_compute', viewer=False)
    txt = EL['with_prefix'](_read(os.path.join(GLSL, 'gen_clone_layout.glsl')), E['_prefix'](EL))
    if code.text != txt:
        code.text = txt
    code.comment = 'gen_clone_layout.glsl + the shared effectors block (effectors_logic.consumer_prefix).'
    g = mk(c, glslTOP, 'clones')
    code.dock = g
    for extra in ('clones_pixel', 'clones_info', 'clones_vertex', 'clones_compute1'):
        if c.op(extra) is not None:
            E['_sd'](c.op(extra))
    g.par.mode = 'compute'
    g.par.computedat = code.name
    g.par.outputresolution = 'custom'
    L = "op('clone_logic').module"
    ex(g.par.resolutionw, '%s.tex_size(%s.count_of(parent()))[0]' % (L, L))
    ex(g.par.resolutionh, '%s.tex_size(%s.count_of(parent()))[1]' % (L, L))
    g.par.format = 'rgba32float'
    g.par.inputextenduv = 'hold'
    wire(psrc, g, 0)
    wire(msrc, g, 1)
    E['_vecs'](g, Lg['uniform_exprs']())
    E['_eff_in'](c)
    E['_buffer'](g)
    E['_vecs'](g, EL['consumer_vecs']())
    g.comment = 'Clone data, 5 texels per clone (pos+size, quaternion, colour, scale+time offset, weight/index/hidden).'
    return g


def _geo(E, c):
    mk, ex = E['_mk'], E['_expr']
    geo = mk(c, geometryCOMP, 'geo')
    keep = ('s_card', 's_box', 's_sphere', 's_torus', 's_sop', 's_sw', 's_norm', 's_out')
    for ch in list(geo.children):
        if ch.name not in keep:
            E['_sd'](ch)

    def sop(cls, name):
        o = geo.op(name)
        if o is None or o.OPType != cls.__name__:
            if o is not None:
                E['_sd'](o)
            o = geo.create(cls, name)
        return o
    card = sop(gridSOP, 's_card')
    card.par.rows, card.par.cols = 2, 2
    card.par.sizex, card.par.sizey = 1.0, 1.0
    card.par.orient = 'xy'
    card.par.texture = 'rowcol'
    shapes = [card, sop(boxSOP, 's_box'), sop(sphereSOP, 's_sphere'), sop(torusSOP, 's_torus'), sop(selectSOP, 's_sop')]
    ex(shapes[4].par.sop, "parent(2).par.Sourcesop.eval() or 's_box'")
    sw = sop(switchSOP, 's_sw')
    for i, s in enumerate(shapes):
        sw.inputConnectors[i].connect(s)
    ex(sw.par.input, "parent(2).par.Source.menuIndex")      # Switch SOP: `input` (live 31550; not `index`)
    nm = sop(transformSOP, 's_norm')
    nm.inputConnectors[0].connect(sw)
    ex(nm.par.scale, "{'sphere': 0.5, 'torus': 1.0 / 3.0}.get(parent(2).par.Source.eval(), 1.0)")
    out = sop(nullSOP, 's_out')
    out.inputConnectors[0].connect(nm)
    out.render = True
    out.display = True
    geo.par.instancing = True
    _menu_val(geo.par.instancecountmode, 'manual')
    ex(geo.par.numinstances, "op('clone_logic').module.count_of(parent())")
    geo.par.material = 'clonemat'                      # T-81: resolves from the Geometry COMP's parent
    geo.comment = ('One shape (card / box / sphere / torus / any SOP, unit size); N instances, transforms read by '
                   'the GLSL MAT from `clones` (no instance OPs).')
    return geo


CAM = {'tx': "{d} * math.cos(math.radians({rx})) * math.sin(math.radians({ry}))",
       'ty': "{d} * math.sin(math.radians({rx}))",
       'tz': "{d} * math.cos(math.radians({rx})) * math.cos(math.radians({ry}))"}


def _cam_expr(k):
    return CAM[k].format(d=PP + 'Camdist.eval()', rx=PP + 'Camrx.eval()',
                         ry='(%sCamry.eval() + %sCamspin.eval() * absTime.seconds)' % (PP, PP))


def _render(E, c, geo, clones, tsrc, ring):
    mk, ex, wire = E['_mk'], E['_expr'], E['_wire']
    vd = mk(c, textDAT, 'clone_vert', viewer=False)
    pd = mk(c, textDAT, 'clone_pixel', viewer=False)
    for d, f in ((vd, 'gen_clone_vert.glsl'), (pd, 'gen_clone_pixel.glsl')):
        t = _read(os.path.join(GLSL, f))
        if d.text != t:
            d.text = t
    mat = mk(c, glslMAT, 'clonemat')
    mat.par.vdat = vd.name
    mat.par.pdat = pd.name
    for dn in ('_vertex', '_pixel', '_info'):
        d = c.op('clonemat' + dn)
        if d is not None and d.name not in (vd.name, pd.name):
            E['_sd'](d)
    vd.dock = mat
    pd.dock = mat
    S = [('sClones', clones.name, 'nearest'), ('sTex', tsrc.name, 'linear'), ('sRing', ring.name, 'linear')]
    mat.seq.sampler.numBlocks = max(int(mat.seq.sampler.numBlocks), len(S))
    for k, (sn, top, flt) in enumerate(S):
        getattr(mat.par, 'sampler%dname' % k).val = sn
        getattr(mat.par, 'sampler%dtop' % k).val = top
        _menu_val(getattr(mat.par, 'sampler%dfilter' % k), flt)
        _menu_val(getattr(mat.par, 'sampler%dextendu' % k), 'hold')
        _menu_val(getattr(mat.par, 'sampler%dextendv' % k), 'hold')
    L = "op('clone_logic').module"
    card = "(1 if parent().par.Source.eval() == 'card' else 0)"
    ring_on = ("(1 if parent().par.Source.eval() == 'card' and (parent().par.Timeoffset.eval() != 0 or "
               "parent().par.Efftime.eval() != 0) else 0)")
    E['_vecs'](mat, [
        ('uR', ['%s.cw(%s.count_of(parent()))' % (L, L), '%s.count_of(parent())' % L, card,
                "op('tex_src').width / max(1, op('tex_src').height)"]),
        ('uL', ["parent().par.Shading.menuIndex if parent().par.Source.eval() != 'card' else 0", card,
                PP + 'Ambient.eval()', PP + 'Alphacut.eval()']),
        ('uRing', [ring_on, "max(1, op('ring').par.cachesize.eval())", 'parent().par.Ringorder.menuIndex', 0]),
        ('uCam', [_cam_expr('tx'), _cam_expr('ty'), _cam_expr('tz'), 0])])
    mat.par.blending = True
    _menu_val(mat.par.srcblend, 'one')
    _menu_val(mat.par.srcblenda, 'one')
    blend = 'parent().par.Blend.eval()'
    ex(mat.par.destblend, "{{'add': 'one', 'over': 'omsa'}}.get({}, 'zero')".format(blend))
    ex(mat.par.destblenda, "{{'add': 'one', 'over': 'omsa'}}.get({}, 'zero')".format(blend))
    ex(mat.par.depthtest, "{} == 'opaque'".format(blend))
    ex(mat.par.depthwriting, "{} == 'opaque'".format(blend))
    mat.par.postmultalpha = False
    _menu_val(mat.par.cullface, 'neither')
    mat.comment = 'Instance transform from `clones` (TDInstanceID), card picture / ring slice, own shading.'
    tgt = mk(c, nullCOMP, 'target')
    tgt.comment = 'Camera look-at (origin).'
    cam = mk(c, cameraCOMP, 'cam')
    for k in ('tx', 'ty', 'tz'):
        ex(getattr(cam.par, k), _cam_expr(k))
    cam.par.lookat = 'target'
    ex(cam.par.projection, "'ortho' if parent().par.Ortho.eval() else 'perspective'")
    ex(cam.par.orthowidth, PP + 'Orthowidth.eval()')
    _menu_val(cam.par.viewanglemethod, 'vertfov')
    ex(cam.par.fov, PP + 'Fov.eval()')
    cam.par.near = 0.01
    cam.par.far = 1000
    ren = mk(c, renderTOP, 'render')
    ren.par.camera = cam.name
    ren.par.geometry = geo.name
    ren.par.lights = ''
    ren.par.outputresolution = 'custom'
    ex(ren.par.resolutionw, PP + 'Resw.eval()')
    ex(ren.par.resolutionh, PP + 'Resh.eval()')
    _menu_val(ren.par.format, 'rgba16float')
    for ch in 'rgb':
        ex(getattr(ren.par, 'bgcolor' + ch), '%sBg%s.eval() * %sBgalpha.eval()' % (PP, ch, PP))
    ex(ren.par.bgcolora, PP + 'Bgalpha.eval()')
    ex(ren.par.antialias, "'aa4' if parent().par.Antialias.eval() else 'aa1x'")
    ren.comment = 'Render Resw x Resh, premultiplied (Bgalpha 0 = transparent background for layering).'
    o1 = mk(c, outTOP, 'out1')
    wire(ren, o1, 0)
    return mat, cam, ren


def build(parent_path='/project1/lab', panel=True):
    Lg = load_logic()
    E = _eff_ns()
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('GEN_clone (G-CLONE): cloner. Modes grid / radial / linear / path / points / random; modifiers step '
                 '/ random / noise / time offset; shared effectors; card (TOP), box, sphere, torus or any SOP. In: '
                 'in1 = card picture. Out: out1. builders/gen_clone.py.')
    for page_name, pars in pages(Lg):
        E['_pars'](c, page_name, pars)
    E['_pars'](c, 'Effectors', eff_page(E))
    d = E['_mk'](c, textDAT, 'clone_logic', viewer=False)
    t = _read(os.path.join(HERE, 'gen_clone_logic.py'))
    if d.text != t:
        d.text = t
    d.comment = 'Module DAT = builders/gen_clone_logic.py (same text; edit the file and rebuild).'
    tsrc, ring, psrc, msrc = _inputs(E, c)
    clones = _clones(E, c, Lg, psrc, msrc)
    geo = _geo(E, c)
    _render(E, c, geo, clones, tsrc, ring)
    stages = [
        {'title': 'Logic', 'role': 'control', 'ops': ['clone_logic', 'eff_none', 'eff_in'],
         'body': 'clone_logic (counts, mirror), shared effector list (eff_in = /project1/effectors/eff_rows).'},
        {'title': '1 Inputs', 'role': 'input', 'ops': ['in1', 'tex_test', 'tex_sel', 'tex_src', 'ring', 'pts_chop',
                                                       'pts_chop_callbacks', 'pts_ctop', 'pts_none', 'pts_tsel',
                                                       'pts_src', 'map_none', 'map_sel', 'map_src'],
         'body': 'Card picture (+ frame ring for time offsets), points / path points, map TOP.'},
        {'title': '2 Clones', 'role': 'process', 'ops': ['clones', 'clones_compute'],
         'body': 'One compute pass: layout -> modifiers -> effectors -> map; 5 texels per clone.'},
        {'title': '3 Render', 'role': 'process', 'ops': ['geo', 'clonemat', 'clone_vert', 'clone_pixel', 'target',
                                                         'cam', 'render'],
         'body': 'Instanced shape, GLSL MAT reads the clone texture, Render TOP.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out1']},
    ]
    info = None
    if panel:
        ns = dict(globals())
        exec(_read(ZKIT_FILE), ns)
        info = ns['build_controls'](c.path, pages=PANEL_PAGES, d=56, cols=6)
        pt = c.op('controls/zk_presets')
        if pt is not None and pt.numRows <= 1:              # seed once (the user's own kept)
            Lz = c.op('controls/zk_logic').module
            for slot, pname, vals in presets(Lg):
                pt.appendRow([slot, pname, Lz.DEFAULT_COLOR, Lz.preset_dump(vals)])
        stages = [{'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window']}] + stages
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, [s_ for s_ in stages if s_['ops']], True, arrange='mixed')
    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    return {'comp': c.path, 'panel': bool(info), 'layout': str(lay)[:200]}
