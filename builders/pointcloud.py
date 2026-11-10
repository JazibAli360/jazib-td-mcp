"""pointcloud builder: /project1/lab/BL_cloud_morph (TD 2025.31550) - point-cloud viewer + A/B morph.

Spec: docs/research/BL_gaussian_splats_pointclouds.md section 7.2 (our clean-room design). Build doc + live checks:
docs/builds/pointcloud.md. Run inside TD via td_exec:
    ns = dict(globals()); exec(open('<repo>/builders/pointcloud.py').read(), ns); ns['build']('/project1/lab')
build(parent_path='/project1/lab', name=NAME, panel=True) is idempotent: ops reused by name, texts/pars/wires re-set,
custom par values kept, zkit panel refreshed in place.
Network: Script CHOP `cloud_data` (numpy: files / generators / depth images, resampled to one Count, matched A<->B by
k-d / Morton / sliced OT) -> Geometry COMP instancing one quad per point (CHOP instancing; Datapath = pop routes the same
channels through CHOP to POP -> Null POP to de-risk POP instancing) -> GLSL MAT (pc_vertex/pc_pixel: per-point eased
morph with stagger + arc noise, live depth-TOP unprojection, size by depth, DOF, shapes) -> Render TOP 16F -> ONE
compute GLSL pass (gain, tone map, background, alpha) -> out1. Per-frame clock: Script CHOP `engine` (manual / BPM /
LFO / audio morph, orbit camera). Pure logic: builders/pointcloud_logic.py; runtime: builders/pointcloud_rt.py (both
copied into Text DATs). T-70 safe: own controls_window closed first, destroys only through safe_destroy, the panel
container is never destroyed (zkit updates it in place), the network pane is never moved. No functions in storage
(T-67). Never reads TOP pixels (T-74). Only single-pass / compute GLSL (T-46/T-47). ASCII only.
"""
import os

REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = os.path.join(REPO, 'builders')
NAME = 'BL_cloud_morph'
LOGIC_FILE = os.path.join(HERE, 'pointcloud_logic.py')
RT_FILE = os.path.join(HERE, 'pointcloud_rt.py')
VERT_FILE = os.path.join(HERE, 'glsl', 'pointcloud_vertex.glsl')
PIX_FILE = os.path.join(HERE, 'glsl', 'pointcloud_pixel.glsl')
POST_FILE = os.path.join(HERE, 'glsl', 'pointcloud_post.glsl')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
TD_SAMPLES = '/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/PointClouds/'
DEFAULT_A = TD_SAMPLES + 'banana.ply'

DATA_SCRIPT = '''# cloud_data: matched A/B point arrays -> one sample per point (pc_rt.data_cook)
def onSetupParameters(scriptOp):
\treturn

def onPulse(par):
\treturn

def onCook(scriptOp):
\tscriptOp.parent().op('pc_rt').module.data_cook(scriptOp)
\treturn
'''
INFO_SCRIPT = DATA_SCRIPT.replace('cloud_data: matched A/B point arrays -> one sample per point (pc_rt.data_cook)',
                                  'info: points count_a count_b travel load_ms ok gen (pc_rt.info_cook)').replace(
    'data_cook', 'info_cook')
ENGINE_SCRIPT = '''# engine: morph clock + orbit camera once per frame (pc_rt.engine_cook; maths in pointcloud_logic.engine_step)
def onSetupParameters(scriptOp):
\tif getattr(scriptOp.par, 'Frame', None) is None:
\t\tp = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
\t\tp.expr = 'absTime.frame'
\t\tp.mode = ParMode.EXPRESSION
\treturn

def onPulse(par):
\treturn

def onCook(scriptOp):
\t_clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
\tscriptOp.parent().op('pc_rt').module.engine_cook(scriptOp)
\treturn
'''
FRAME_EXEC = '''# frame_exec: debounced reload outside any cook (pc_rt.frame)
def onFrameStart(frame):
\tc = parent()
\ttry:
\t\tc.op('pc_rt').module.frame(c)
\texcept Exception as e:
\t\tc.par.Status.val = ('frame: %s: %s' % (type(e).__name__, e))[:200]
\treturn
'''
PAR_EXEC = '''# par_exec: load pars -> debounced reload; pulses Reload / Frame / Reset (pc_rt)
def onValueChange(par, prev):
\tparent().op('pc_rt').module.on_value(parent(), par)
\treturn

def onPulse(par):
\tparent().op('pc_rt').module.on_pulse(parent(), par)
\treturn
'''

E = "op('engine')['{}']"
P = 'parent().par.{}'
# GLSL MAT uniforms: (name, x, y, z, w); None = constant written by pc_rt.write_tex_uniforms after each load
MAT_VECS = [
    ('uMorph', E.format('morph'), P.format('Stagger'), P.format('Arc'), E.format('t')),
    ('uEase', P.format('Ease') + '.menuIndex', P.format('Noiseamp'), P.format('Noisefreq'), P.format('Noisespeed')),
    ('uSize', P.format('Size'), P.format('Sizebydepth'), P.format('Orbitdist'), P.format('Opacity')),
    ('uDof', P.format('Dof'), P.format('Focusdist'), P.format('Streak'), P.format('Shape') + '.menuIndex'),
    ('uCol', P.format('Colourmix'), P.format('Tintamount'), P.format('Brightness'), P.format('Blend') + '.menuIndex'),
    ('uTint', P.format('Tintr'), P.format('Tintg'), P.format('Tintb'), '0'),
    ('uRes', P.format('Resolution1'), P.format('Resolution2'), '0', '0'),
    ('uTexA', None), ('uTexB', None), ('uFitA', None), ('uOffA', None), ('uFitB', None), ('uOffB', None),
    ('uKind', None), ('uLoHi', None),
]
SAMPLERS = [('sDepthA', 'Deptha'), ('sColA', 'Colora'), ('sDepthB', 'Depthb'), ('sColB', 'Colorb')]

STAGES = [
    {'title': 'Controls', 'role': 'control',
     'ops': ['controls', 'controls_window', 'par_exec', 'frame_exec', 'pointcloud_logic', 'pc_rt'],
     'body': 'zkit panel (Morph, Look, Camera); pulse Opencontrols. par_exec: load pars -> debounced reload (frame_exec). '
             'pointcloud_logic: loaders, matching, morph maths (offline tested); pc_rt: TD runtime (numpy cache).'},
    {'title': '1 Load + match', 'role': 'input', 'ops': ['cloud_data', 'cloud_data_callbacks', 'to_pop', 'cloud_pop'],
     'body': 'A and B (file ply/xyz/obj/csv/pts/splat/spz, generator, depth image file, live depth TOP grid) -> '
             'up axis, outlier crop, unit fit -> resampled to Count -> k-d / Morton / sliced-OT pairing -> one sample per '
             'point: A xyz + delay, B xyz + seed, A rgba, B rgba, uv A/B. Datapath pop: CHOP to POP -> cloud_pop.'},
    {'title': '2 Clock', 'role': 'process', 'ops': ['engine', 'engine_callbacks'],
     'body': 'Per frame: morph (manual / BPM ping-pong / LFO / audio level), orbit camera position, time.'},
    {'title': '3 Draw + render', 'role': 'process', 'ops': ['draw', 'pcmat', 'pc_vertex', 'pc_pixel', 'blank', 'target',
                                                           'cam', 'render'],
     'body': 'Geometry COMP: one quad per point (instancing). GLSL MAT: eased per-point morph with stagger + arc, '
             'depth-TOP unprojection, size by depth, DOF, disc/soft/square/ring/streak; add / over / opaque. Render 16F.'},
    {'title': '4 Output', 'role': 'output', 'ops': ['post', 'post_compute', 'out1', 'info', 'info_callbacks',
                                                    'info_merge', 'out_info'],
     'body': 'post = ONE compute pass: gain, tone map, background, alpha. out1 = image only. out_info: morph beat level '
             '+ points count_a count_b travel load_ms ok.'},
]


def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _close_window(c):
    w = c.op('controls_window')
    if w is not None and w.OPType == 'windowCOMP' and w.isOpen:
        w.par.winclose.pulse()
        return True
    return False


def _mk(c, cls, name):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = True
    return o


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _expr(par, e):
    if par.expr != e or par.mode != ParMode.EXPRESSION:
        par.expr = e
        par.mode = ParMode.EXPRESSION


def _menu_val(par, want):
    names = par.menuNames
    par.val = want if want in names else names[0]


def _page(c, name):
    for p in c.customPages:
        if p.name == name:
            return p
    return c.appendCustomPage(name)


def _par(c, page, style, name, label, default=None, rng=None, menu=None, size=1):
    """Idempotent custom par (any style; slider range only, no clamps: no limits)."""
    if getattr(c.parGroup, name, None) is not None:
        g = getattr(c.parGroup, name)
        if g.label != label:
            g.label = label
        return g
    pg = _page(c, page)
    if style == 'Menu':
        g = pg.appendMenu(name, label=label)
        g[0].menuNames = [m[0] for m in menu]
        g[0].menuLabels = [m[1] for m in menu]
    elif style in ('Int', 'Float') and size > 1:
        g = getattr(pg, 'append' + style)(name, label=label, size=size)
    else:
        g = getattr(pg, 'append' + style)(name, label=label)
    pars = list(g)
    if rng is not None:
        for p in pars:
            p.normMin, p.normMax = rng
    if default is not None:
        vals = default if isinstance(default, (tuple, list)) else [default]
        for p, v in zip(pars, vals):
            p.default = v
            p.val = v
    return g


def _pars(c, L):
    for k, src, gen, f in (('a', 'file', 'sphere', DEFAULT_A), ('b', 'gen', 'sphere', '')):
        pg = 'Source ' + k.upper()
        K = k.upper()
        _par(c, pg, 'Menu', 'Source' + k, 'Source ' + K, src, menu=L.SOURCES)
        _par(c, pg, 'File', 'File' + k, 'File ' + K, f)
        _par(c, pg, 'Menu', 'Gen' + k, 'Generator ' + K, gen, menu=L.GENERATORS)
        _par(c, pg, 'File', 'Depthfile' + k, 'Depth image file ' + K, '')
        _par(c, pg, 'File', 'Colourfile' + k, 'Colour image file ' + K, '')
        _par(c, pg, 'TOP', 'Depth' + k, 'Depth TOP ' + K + ' (live)', '')
        _par(c, pg, 'TOP', 'Color' + k, 'Colour TOP ' + K + ' (live)', '')
        _par(c, pg, 'Menu', 'Up' + k, 'Up axis ' + K + ' (files)', 'y', menu=L.UPAXES)
        _par(c, pg, 'Float', 'Scale' + k, 'Scale ' + K, 1.0, (0, 3))
        _par(c, pg, 'XYZ', 'Offset' + k, 'Offset ' + K, (0.0, 0.0, 0.0), (-3, 3))
    M = 'Match'
    _par(c, M, 'Int', 'Count', 'Count (0 = auto)', 0, (0, 1000000))
    _par(c, M, 'Menu', 'Match', 'Match', 'kd', menu=L.MATCHES)
    _par(c, M, 'Int', 'Slices', 'Sliced OT rounds', 8, (0, 64))
    _par(c, M, 'Int', 'Seed', 'Seed', 0, (0, 100))
    _par(c, M, 'Menu', 'Staggermode', 'Stagger order', 'radial', menu=L.STAGGERS)
    _par(c, M, 'Menu', 'Resample', 'Resample', 'even', menu=[('even', 'Even'), ('random', 'Random')])
    _par(c, M, 'Float', 'Outlier', 'Keep percentile', 100.0, (50, 100))
    _par(c, M, 'Toggle', 'Fit', 'Fit to unit radius', True)
    _par(c, M, 'Pulse', 'Reload', 'Reload')
    _par(c, M, 'Str', 'Status', 'Status', '')
    c.par.Status.readOnly = True
    D = 'Depth'
    _par(c, D, 'Menu', 'Depthkind', 'Depth kind', 'inverse', menu=L.DEPTHKINDS)
    _par(c, D, 'Float', 'Dfov', 'Depth camera FOV (vert deg)', 60.0, (10, 120))
    _par(c, D, 'Float', 'Znear', 'Near', 1.0, (0.01, 10))
    _par(c, D, 'Float', 'Zfar', 'Far', 10.0, (1, 100))
    _par(c, D, 'Float', 'Depthlo', 'Depth lo (raw)', 0.0, (0, 1))
    _par(c, D, 'Float', 'Depthhi', 'Depth hi (raw)', 1.0, (0, 1))
    _par(c, D, 'Toggle', 'Depthauto', 'Auto lo/hi (files: 2-98 %)', True)
    _par(c, D, 'Int', 'Depthstep', 'Depth file pixel step', 4, (1, 16))
    MO = 'Morph'
    _par(c, MO, 'Menu', 'Morphmode', 'Morph mode', 'manual', menu=L.MORPHMODES)
    _par(c, MO, 'Float', 'Morph', 'Morph A -> B', 0.0, (0, 1))
    _par(c, MO, 'Menu', 'Ease', 'Ease', 'inout', menu=L.EASES)
    _par(c, MO, 'Float', 'Stagger', 'Stagger', 0.5, (0, 3))
    _par(c, MO, 'Float', 'Arc', 'Arc (noise path)', 0.3, (-2, 2))
    _par(c, MO, 'Float', 'Colourmix', 'Colour follows', 1.0, (0, 1))
    _par(c, MO, 'Menu', 'Tempo', 'Tempo', 'project', menu=L.TEMPOS)
    _par(c, MO, 'Float', 'Bpm', 'BPM', 120.0, (60, 200))
    _par(c, MO, 'Float', 'Beatsperswap', 'Beats per swap', 8.0, (1, 64))
    _par(c, MO, 'Float', 'Morphbeats', 'Morph beats', 2.0, (0, 16))
    _par(c, MO, 'Float', 'Rate', 'LFO Hz', 0.1, (0, 2))
    _par(c, MO, 'CHOP', 'Audiochop', 'Audio CHOP', '')
    _par(c, MO, 'Str', 'Audiochan', 'Audio channel', 'low')
    _par(c, MO, 'Float', 'Audiogain', 'Audio gain', 1.0, (0, 4))
    _par(c, MO, 'Float', 'Attack', 'Attack s', 0.05, (0, 1))
    _par(c, MO, 'Float', 'Release', 'Release s', 0.3, (0, 2))
    LO = 'Look'
    _par(c, LO, 'Menu', 'Shape', 'Shape', 'disc', menu=L.SHAPES)
    _par(c, LO, 'Menu', 'Blend', 'Blend', 'add', menu=L.BLENDS)
    _par(c, LO, 'Float', 'Size', 'Size px', 2.0, (0.5, 20))
    _par(c, LO, 'Float', 'Sizebydepth', 'Size by depth', 0.0, (0, 1))
    _par(c, LO, 'Float', 'Opacity', 'Opacity', 1.0, (0, 1))
    _par(c, LO, 'Float', 'Brightness', 'Brightness', 1.0, (0, 3))
    _par(c, LO, 'RGB', 'Tint', 'Tint', (1.0, 1.0, 1.0))
    _par(c, LO, 'Float', 'Tintamount', 'Tint amount', 0.0, (0, 1))
    _par(c, LO, 'Float', 'Noiseamp', 'Drift', 0.0, (0, 0.2))
    _par(c, LO, 'Float', 'Noisefreq', 'Noise freq', 2.0, (0, 10))
    _par(c, LO, 'Float', 'Noisespeed', 'Noise speed', 0.3, (0, 3))
    _par(c, LO, 'Float', 'Dof', 'DOF px per unit', 0.0, (0, 20))
    _par(c, LO, 'Float', 'Focusdist', 'Focus distance', 3.0, (0, 20))
    _par(c, LO, 'Float', 'Streak', 'Streak (path fraction)', 0.0, (0, 1))
    CA = 'Camera'
    _par(c, CA, 'Menu', 'Cammode', 'Camera', 'orbit', menu=L.CAMMODES)
    _par(c, CA, 'COMP', 'Camcomp', 'External camera', '')
    _par(c, CA, 'Float', 'Orbitaz', 'Azimuth', 0.0, (-180, 180))
    _par(c, CA, 'Float', 'Orbitel', 'Elevation', 10.0, (-89, 89))
    _par(c, CA, 'Float', 'Orbitdist', 'Distance', 3.0, (0.1, 20))
    _par(c, CA, 'XYZ', 'Target', 'Target', (0.0, 0.0, 0.0), (-5, 5))
    _par(c, CA, 'Float', 'Fov', 'FOV (vert deg)', 45.0, (10, 120))
    _par(c, CA, 'Float', 'Autorbit', 'Orbit deg/s', 6.0, (-90, 90))
    _par(c, CA, 'Pulse', 'Frame', 'Frame both clouds')
    _par(c, CA, 'Pulse', 'Reset', 'Reset look')
    OU = 'Output'
    _par(c, OU, 'Int', 'Resolution', 'Resolution', (1080, 1920), (1, 4096), size=2)
    _par(c, OU, 'RGBA', 'Bgcolor', 'Background', (0.0, 0.0, 0.0, 0.0))
    _par(c, OU, 'Float', 'Gain', 'Gain', 1.0, (0, 4))
    _par(c, OU, 'Toggle', 'Tonemap', 'Tone map (additive)', False)
    _par(c, OU, 'Toggle', 'Outputalpha', 'Output alpha', True)
    _par(c, OU, 'Toggle', 'Premult', 'Premultiplied out', True)
    _par(c, OU, 'Menu', 'Datapath', 'Instance data', 'chop', menu=L.DATAPATHS)


def _attrs_from_chop(tp, L):
    """CHOP to POP: P = A xyz (bounds / viewer), plus the 5 instance slots as custom attributes (Pa Pb Ca Cb Uv)."""
    _menu_val(tp.par.surftype, 'points')
    tp.par.chanscope = 'ax ay az'
    tp.par.attrscope = 'P'
    tp.seq.attr.numBlocks = len(L.SLOTS)
    for i, (nm, chans) in enumerate(L.SLOTS):
        g = lambda s: getattr(tp.par, 'attr{}{}'.format(i, s))  # noqa: E731
        g('chanscope').val = ' '.join(chans)
        _menu_val(g('name'), 'custom')
        g('customname').val = nm
        _menu_val(g('type'), 'float')
        _menu_val(g('numcomps'), str(len(chans)))


def _geo(c, geo, mat, L):
    for ch in list(geo.children):
        if ch.name != 'quad':
            _sd(ch)
    q = geo.op('quad')
    if q is None or q.OPType != 'rectangleSOP':
        if q is not None:
            _sd(q)
        q = geo.create(rectangleSOP, 'quad')
    q.par.sizex = 2
    q.par.sizey = 2
    q.render = True
    q.display = True
    geo.par.instancing = True
    _expr(geo.par.instanceop, "'cloud_pop' if parent().par.Datapath.eval() == 'pop' else 'cloud_data'")
    _menu_val(geo.par.instancecountmode, 'oplength')
    pop = "parent().par.Datapath.eval() == 'pop'"
    for ax, ch, k in (('tx', 'ax', 0), ('ty', 'ay', 1), ('tz', 'az', 2)):
        _expr(getattr(geo.par, 'instance' + ax), "'P({})' if {} else '{}'".format(k, pop, ch))
    geo.seq.instance.numBlocks = max(int(geo.seq.instance.numBlocks), len(L.SLOTS))
    for i, (nm, chans) in enumerate(L.SLOTS):
        cop = getattr(geo.par, 'instance{}customop'.format(i), None)
        if cop is not None:
            _expr(cop, "'cloud_pop' if parent().par.Datapath.eval() == 'pop' else 'cloud_data'")
        for k, ax in enumerate('xyzw'):
            par = getattr(geo.par, 'instance{}custom{}'.format(i, ax))
            _expr(par, "'{}({})' if {} else '{}'".format(nm, k, pop, chans[k]))
    geo.par.material = mat.name                   # T-81: Geometry COMP OP pars resolve from its parent


def _mat(c, mat, vd, pd):
    mat.par.vdat = vd.name
    mat.par.pdat = pd.name
    mat.seq.vec.numBlocks = max(int(mat.seq.vec.numBlocks), len(MAT_VECS))
    for i, row in enumerate(MAT_VECS):
        getattr(mat.par, 'vec{}name'.format(i)).val = row[0]
        if row[1] is None:
            continue                              # constants: pc_rt.write_tex_uniforms
        for ax, e in zip('xyzw', row[1:]):
            par = getattr(mat.par, 'vec{}value{}'.format(i, ax))
            try:
                v = float(e)
                par.mode = ParMode.CONSTANT
                par.val = v
            except ValueError:
                _expr(par, e)
    mat.seq.sampler.numBlocks = max(int(mat.seq.sampler.numBlocks), len(SAMPLERS))
    for i, (un, pn) in enumerate(SAMPLERS):
        getattr(mat.par, 'sampler{}name'.format(i)).val = un
        _expr(getattr(mat.par, 'sampler{}top'.format(i)),
              "parent().par.{0}.eval() if parent().par.{0}.eval() is not None else op('blank')".format(pn))
        _menu_val(getattr(mat.par, 'sampler{}filter'.format(i)), 'linear')
        _menu_val(getattr(mat.par, 'sampler{}extendu'.format(i)), 'hold')
        _menu_val(getattr(mat.par, 'sampler{}extendv'.format(i)), 'hold')
    mat.par.blending = True
    _menu_val(mat.par.srcblend, 'one')
    _menu_val(mat.par.srcblenda, 'one')
    blend = "parent().par.Blend.eval()"
    _expr(mat.par.destblend, "{{'add': 'one', 'over': 'omsa'}}.get({}, 'zero')".format(blend))
    _expr(mat.par.destblenda, "{{'add': 'one', 'over': 'omsa'}}.get({}, 'zero')".format(blend))
    _expr(mat.par.depthtest, "{} == 'opaque'".format(blend))
    _expr(mat.par.depthwriting, "{} == 'opaque'".format(blend))
    mat.par.postmultalpha = False


def _eff_hook(c):
    """Shared effectors adapter (builders/effectors.py attach, docs/builds/effectors.md): Effectors page + a few ops,
    idempotent, run after every build; a failure is reported, never a broken build."""
    try:
        ns = dict(globals())
        exec(open(REPO + '/builders/effectors.py').read(), ns)
        return ns['attach'](c.path)
    except Exception as e:
        return 'effectors adapter skipped: %s' % e


def build(parent_path='/project1/lab', name=NAME, panel=True):
    pc = op(parent_path)
    c = pc.op(name) or pc.create(baseCOMP, name)
    c.allowCooking = True
    _close_window(c)
    lg = _mk(c, textDAT, 'pointcloud_logic')
    lg.text = open(LOGIC_FILE).read()
    lg.comment = 'Pure logic (copy of builders/pointcloud_logic.py; tests in test/test_pointcloud.py).'
    L = lg.module
    rt = _mk(c, textDAT, 'pc_rt')
    rt.text = open(RT_FILE).read()
    rt.comment = 'TD runtime (copy of builders/pointcloud_rt.py).'
    _pars(c, L)
    c.comment = ('BL_cloud_morph: point-cloud viewer + A/B morph. Sources: files (ply xyz obj csv pts splat spz), '
                 'generators, depth image files, live depth TOPs. Out: out1 TOP (Resolution, premultiplied 16F), '
                 'out_info CHOP. No limits. Pulse Opencontrols.')

    # 1 Load + match
    data = _mk(c, scriptCHOP, 'cloud_data')
    cb = c.op('cloud_data_callbacks') or c.create(textDAT, 'cloud_data_callbacks')
    cb.text = DATA_SCRIPT
    data.par.callbacks = cb.name
    tp = _mk(c, choptoPOP, 'to_pop')
    tp.par.chop = data.name
    _attrs_from_chop(tp, L)
    cpop = _mk(c, nullPOP, 'cloud_pop')
    _wire(tp, cpop)

    # 2 Clock
    eng = _mk(c, scriptCHOP, 'engine')
    ecb = c.op('engine_callbacks') or c.create(textDAT, 'engine_callbacks')
    ecb.text = ENGINE_SCRIPT
    eng.par.callbacks = ecb.name
    eng.par.setuppars.pulse()

    # 3 Draw + render
    blank = _mk(c, constantTOP, 'blank')
    blank.par.outputresolution = 'custom'
    blank.par.resolutionw = 2
    blank.par.resolutionh = 2
    blank.par.colorr = blank.par.colorg = blank.par.colorb = 0.5
    blank.par.alpha = 1
    vd = _mk(c, textDAT, 'pc_vertex')
    vd.text = open(VERT_FILE).read()
    pd = _mk(c, textDAT, 'pc_pixel')
    pd.text = open(PIX_FILE).read()
    mat = _mk(c, glslMAT, 'pcmat')
    _mat(c, mat, vd, pd)
    geo = _mk(c, geometryCOMP, 'draw')
    _geo(c, geo, mat, L)
    tgt = _mk(c, nullCOMP, 'target')
    for ax in 'xyz':
        _expr(getattr(tgt.par, 't' + ax), 'parent().par.Target' + ax)
    cam = _mk(c, cameraCOMP, 'cam')
    for ax, ch in (('x', 'camx'), ('y', 'camy'), ('z', 'camz')):
        _expr(getattr(cam.par, 't' + ax), E.format(ch))
    cam.par.lookat = 'target'
    _menu_val(cam.par.viewanglemethod, 'vertfov')
    _expr(cam.par.fov, 'parent().par.Fov')
    cam.par.near = 0.01
    cam.par.far = 1000
    ren = _mk(c, renderTOP, 'render')
    _expr(ren.par.camera, "(parent().par.Camcomp.eval().path if parent().par.Cammode.eval() == 'external' and "
                          "parent().par.Camcomp.eval() is not None else 'cam')")
    ren.par.geometry = geo.name
    ren.par.lights = ''
    ren.par.outputresolution = 'custom'
    _expr(ren.par.resolutionw, 'parent().par.Resolution1')
    _expr(ren.par.resolutionh, 'parent().par.Resolution2')
    _menu_val(ren.par.format, 'rgba16float')
    ren.par.bgcolorr = ren.par.bgcolorg = ren.par.bgcolorb = 0
    ren.par.bgcolora = 0
    _menu_val(ren.par.antialias, 'aa1x')

    # 4 Output
    post = _mk(c, glslTOP, 'post')
    pcd = _mk(c, textDAT, 'post_compute')
    pcd.text = open(POST_FILE).read()
    _menu_val(post.par.mode, 'compute')
    post.par.computedat = pcd.name
    post.par.outputresolution = 'custom'
    _expr(post.par.resolutionw, 'parent().par.Resolution1')
    _expr(post.par.resolutionh, 'parent().par.Resolution2')
    _menu_val(post.par.format, 'rgba16float')
    post.par.autodispatchsize = True
    post.seq.vec.numBlocks = max(int(post.seq.vec.numBlocks), 2)
    post.par.vec0name = 'uPost'
    _expr(post.par.vec0valuex, 'parent().par.Gain')
    _expr(post.par.vec0valuey, '1 if parent().par.Tonemap else 0')
    _expr(post.par.vec0valuez, '1 if parent().par.Outputalpha else 0')
    _expr(post.par.vec0valuew, '1 if parent().par.Premult else 0')
    post.par.vec1name = 'uBg'
    for ax, ch in zip('xyzw', 'rgba'):
        _expr(getattr(post.par, 'vec1value' + ax), 'parent().par.Bgcolor' + ch)
    _wire(ren, post, 0)
    out = _mk(c, outTOP, 'out1')
    _wire(post, out)
    info = _mk(c, scriptCHOP, 'info')
    icb = c.op('info_callbacks') or c.create(textDAT, 'info_callbacks')
    icb.text = INFO_SCRIPT
    info.par.callbacks = icb.name
    im = _mk(c, mergeCHOP, 'info_merge')
    _wire(eng, im, 0)
    _wire(info, im, 1)
    oi = _mk(c, outCHOP, 'out_info')
    _wire(im, oi)

    # Control
    fe = _mk(c, executeDAT, 'frame_exec')
    fe.text = FRAME_EXEC
    fe.par.framestart = True
    fe.par.active = True
    pe = _mk(c, parameterexecuteDAT, 'par_exec')
    pe.text = PAR_EXEC
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = ' '.join([n + '*' if n.startswith('Offset') else n for n in rt.module.LOAD_PARS] +
                           list(rt.module.PULSES))
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = True
    pe.par.onpulse = True
    pe.par.active = True

    rt.module.load(c)                       # synchronous first load (Status shows the result)
    rt.module.frame_camera(c)

    ui = 'skipped'
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        ui = ns['build_controls'](c.path, pages=['Morph', 'Look', 'Camera'], d=56, cols=8)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    for o in c.children:
        if o.family in ('TOP', 'CHOP', 'POP'):
            o.viewer = True
    stages = []
    for s_ in STAGES:
        s2 = dict(s_)
        s2['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
        if s2['ops']:
            stages.append(s2)
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:  # noqa: BLE001
        lay = 'layout failed: {}'.format(e)
    eff = _eff_hook(c)
    return {'effectors': str(eff)[:300],
            'comp': c.path, 'ops': len(c.children), 'status': c.par.Status.eval(), 'ui': str(ui)[:200],
            'layout': str(lay)[:300]}
