# pop_common - shared builder helpers for lane H (POP-structural tail of BUILD_PLAN_27OCT s5; doc
# docs/builds/pop_lane_h.md). Shared because every lane-H builder uses the same small kit (11 users today): idempotent
# op creation, custom pars, compute GLSL TOP passes (T-46/T-47: every multi-pass is compute), a STATIC Grid POP drawn
# by a GLSL MAT (the lab's known-good POP class: physarum, GEN_points, T-112), Render TOP, out switch, layout + zkit.
# Rules baked in: no POP compute, no attribute layouts, no Sort / TOP-to-POP configs (T-124); the only POP is a
# Grid POP whose pars are set once at build time. Vertex shaders read TDPos() (raw P reads garbage on POP points,
# T-112). Nothing destroyed directly (T-70: _sd = safe_destroy). No pixel readback here (T-74/T-182).
# Load inside a builder:  exec(open(<repo>/builders/pop_common.py).read(), globals())
# ASCII only.
import os

REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = REPO + '/builders'
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
NOTES = []
PP = "parent().par.{}"
RESW = "parent().par.Resw.eval()"
RESH = "parent().par.Resh.eval()"


def _read(p):
    with open(p) as f:
        return f.read()


def _sd(o):
    if o is None or not getattr(o, 'valid', False):
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
    ins = getattr(dst, 'inputs', [])
    if len(ins) > i and ins[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _expr(par, e):
    par.expr = str(e)
    par.mode = ParMode.EXPRESSION


def _try(o, name, value=None, expr=None):
    """Set a par not confirmed live on 31550 yet: misses go to NOTES, never fail (LIVE CHECK reads NOTES)."""
    p = getattr(o.par, name, None)
    if p is None:
        NOTES.append('%s.%s: no such par' % (o.name, name))
        return None
    try:
        if expr is not None:
            _expr(p, expr)
        else:
            p.val = value
    except Exception as e:
        NOTES.append('%s.%s: %s' % (o.name, name, e))
    return p


def _pars(c, pages):
    """Custom pars from PAGES [(page, [(Name, style, default, opts)])]. Existing pars keep the user's values."""
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None and getattr(getattr(c.par, name), 'val', None) is not None:
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
            elif style in ('Float', 'Int'):
                p = (page.appendFloat if style == 'Float' else page.appendInt)(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']     # slider range only: no clamps (no limits)
                if 'clampmin' in o:                            # sizes / counts only
                    p.min, p.clampMin = o['clampmin'], True
                if 'clampmax' in o:                            # hard caps for GPU safety (T-124 / T-193)
                    p.max, p.clampMax = o['clampmax'], True
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
                continue
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
            elif style == 'TOP':
                p = page.appendTOP(name, label=label)[0]
            else:
                continue
            p.default = default
            p.val = default


def _apply_first(c, values):
    """build(..., first=True): set the item's FIRST dict (small counts / low res, docs/builds/pop_lane_h.md "First-frame
    safe settings") right after _pars and BEFORE any render op exists, so the very first cook is the small one."""
    for k, v in (values or {}).items():
        p = getattr(c.par, k, None)
        if p is None:
            NOTES.append('first: no par %s' % k)
            continue
        p.val = v


def _code(c, name, text):
    d = _mk(c, textDAT, name)
    if d.text != text:
        d.text = text
    return d


def _blank(c, name, w, h, fmt='rgba32float'):
    b = _mk(c, constantTOP, name)
    b.par.outputresolution = 'custom'
    _expr(b.par.resolutionw, w)
    _expr(b.par.resolutionh, h)
    b.par.format = fmt
    b.par.colorr = b.par.colorg = b.par.colorb = 0
    b.par.alpha = 0
    return b


def _vecs(o, spec):
    """spec = [(uniform name, (x, y, z, w) python expressions)] -> the op's Vectors sequence."""
    if not spec:
        return
    o.seq.vec.numBlocks = max(int(o.seq.vec.numBlocks), len(spec))
    for k, (un, ex) in enumerate(spec):
        getattr(o.par, 'vec%dname' % k).val = un
        for ax, e in zip('xyzw', ex):
            _expr(getattr(o.par, 'vec%dvalue%s' % (k, ax)), e)


def _compute(c, name, text, inputs, w, h, fmt='rgba32float', spec=(), bufs=1, inplace=False, filt='nearest'):
    """Compute-mode GLSL TOP (T-47) with its code DAT docked. inplace = FX6 probe 5a state pattern (readwrite, no
    clear, TDImageLoadOutput in place, no Feedback TOP)."""
    code = _code(c, name + '_compute', text)
    g = _mk(c, glslTOP, name)
    g.par.mode = 'compute'
    g.par.computedat = code.name
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, w)
    _expr(g.par.resolutionh, h)
    g.par.format = fmt
    g.par.autodispatchsize = True
    _try(g, 'inputfiltertype', filt)
    if bufs > 1:
        _try(g, 'numcolorbufs', bufs)
    if inplace:
        _try(g, 'outputaccess', 'readwrite')
        _try(g, 'clearoutputs', False)
    for i, s in enumerate(inputs):
        if s is not None:
            _wire(s, g, i)
    _vecs(g, list(spec))
    code.dock = g
    return g


def _feedback(c, name, target, blank):
    fb = _mk(c, feedbackTOP, name)
    _wire(blank, fb)
    fb.par.top = target
    return fb


def _clock(c, name='clock', rate="parent().par.Speed.eval()"):
    """Module time: Constant CHOP rate -> Speed CHOP (Speed 0 = hold, no jump when Speed changes)."""
    k = _mk(c, constantCHOP, name + '_rate')
    k.par.name0 = 'rate'
    _expr(k.par.value0, rate)
    s = _mk(c, speedCHOP, name)
    _wire(k, s)
    s.comment = 'Module time (s) = integral of the rate; read by the shader uniforms as op(%r)[0].' % name
    return s


def _grid(c, name, cols_e, rows_e, surftype='quads', sizex=1.0, sizey=1.0):
    """The ONE POP: a static Grid POP (pars set once at build; nothing POP-side changes live)."""
    g = _mk(c, gridPOP, name)
    g.par.surftype = surftype
    _expr(g.par.cols, cols_e)
    _expr(g.par.rows, rows_e)
    g.par.sizex, g.par.sizey = sizex, sizey
    _try(g, 'texture', 'point')        # Tex exists on Grid POP in 31550 (dump); silences "MAT uses texture coords"
    return g


def _mat(c, name, vert, pixel, samplers=(), spec=(), blend='over', depth=True, cull='neither'):
    """GLSL MAT with docked vertex / pixel DATs. samplers = [(uniform, top name, filter)]; blend 'add' = one/one
    (exact sums, T-112), 'over' = premultiplied over, 'none' = opaque."""
    m = _mk(c, glslMAT, name)
    for suf, text in (('_vertex', vert), ('_pixel', pixel)):
        d = _code(c, name + suf, text)
        d.dock = m
    m.par.vdat = name + '_vertex'
    m.par.pdat = name + '_pixel'
    if samplers:
        m.seq.sampler.numBlocks = max(int(m.seq.sampler.numBlocks), len(samplers))
        for k, (un, top, filt) in enumerate(samplers):
            getattr(m.par, 'sampler%dname' % k).val = un
            getattr(m.par, 'sampler%dtop' % k).val = top
            _try(m, 'sampler%dfilter' % k, filt)
    _vecs(m, list(spec))
    if blend == 'none':
        m.par.blending = False
    else:
        m.par.blending = True
        dst = 'one' if blend == 'add' else 'omsa'
        m.par.srcblend, m.par.destblend = 'one', dst
        _try(m, 'srcblenda', 'one')
        _try(m, 'destblenda', dst)
    _try(m, 'postmultalpha', False)
    m.par.depthtest = bool(depth)
    m.par.depthwriting = bool(depth)
    _try(m, 'cullface', cull)
    return m


def _geo(c, name, pop_name, mat_name):
    geo = _mk(c, geometryCOMP, name)
    for ch in list(geo.children):
        if ch.name != 'sel':
            _sd(ch)                                       # the default torus (prox_mat.py note)
    s = geo.op('sel') or geo.create(selectPOP, 'sel')
    s.par.pop = '../' + pop_name
    s.render = True
    s.display = True
    geo.par.material = mat_name
    return geo


def _cam(c, name, pars):
    """Camera COMP; pars = {par: python expression (str) or constant}. Used with TDWorldToProj in mesh MATs.
    Menu values are passed as ('menu', 'name') so they are not taken for expressions."""
    cam = _mk(c, cameraCOMP, name)
    for k, e in pars.items():
        p = getattr(cam.par, k, None)
        if p is None:
            NOTES.append('%s.%s: no such par' % (name, k))
            continue
        if isinstance(e, tuple):
            p.val = e[1]
        elif isinstance(e, str):
            _expr(p, e)
        else:
            p.val = e
    return cam


def _render(c, name, cam, geo, w=RESW, h=RESH, fmt='rgba16float', aa='aa4'):
    r = _mk(c, renderTOP, name)
    r.par.camera = cam
    r.par.geometry = geo
    r.par.lights = ''
    r.par.outputresolution = 'custom'
    _expr(r.par.resolutionw, w)
    _expr(r.par.resolutionh, h)
    r.par.format = fmt
    r.par.antialias = aa
    r.par.bgcolorr = r.par.bgcolorg = r.par.bgcolorb = r.par.bgcolora = 0
    return r


def _out_switch(c, in1, look, name='out_sel', extra=()):
    """Amount 0 = in1 untouched (nothing upstream cooks); else the look."""
    s = _mk(c, switchTOP, name)
    _wire(in1, s, 0)
    _wire(look, s, 1)
    for i, e in enumerate(extra):
        _wire(e, s, 2 + i)
    _expr(s.par.index, "0 if parent().par.Amount.eval() <= 0 else 1")
    o = _mk(c, outTOP, 'out1')
    _wire(s, o)
    return s, o


def _comp(parent_path, name, comment):
    pc = op(parent_path)
    c = pc.op(name) or pc.create(baseCOMP, name)
    c.allowCooking = True
    c.comment = comment
    return c


def _finish(c, stages, panel_pages=None, was_open=False, panel=True, viewer='out1'):
    """Layout (handlers.layout_stages) + zkit panel. Both optional: failures land in the reply, never raise."""
    try:
        c.par.opviewer = viewer
        c.viewer = True
    except Exception:
        pass
    info = None
    if panel and panel_pages:
        try:
            ns = dict(globals())
            exec(_read(ZKIT_FILE), ns)
            info = ns['build_controls'](c.path, pages=panel_pages, d=56, cols=8, open_window=was_open)
        except Exception as e:
            info = 'panel failed: %s' % e
    stages = [s for s in stages if s['ops']]
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: %s' % e
    return {'comp': c.path, 'ops': len(c.children), 'notes': list(NOTES), 'panel': str(info)[:300],
            'layout': str(lay)[:300]}


# Common pars every lane-H COMP has (first page of each builder appends its own).
OUT_PAGE = ('Output', [
    ('Resw', 'Int', 1080, {'min': 64, 'max': 4096, 'clampmin': 16, 'label': 'Output width'}),
    ('Resh', 'Int', 1920, {'min': 64, 'max': 4096, 'clampmin': 16, 'label': 'Output height'}),
])

# GLSL MAT stand-ins used by the offline tests (glslc) live in test/pop_testkit.py, not here.
