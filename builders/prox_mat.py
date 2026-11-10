# prox_mat builder - MX_prox_material: proximity-driven lit PBR GLSL MAT for any mesh (effector objects + point sets).
# Logic + numpy reference: builders/prox_mat_logic.py; shaders builders/glsl/prox_mat_*.glsl + PX's px_common.glsl
# (shared effector / falloff / point-set maths); doc docs/builds/prox_mat.md; tests test/test_prox_mat.py.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/prox_mat.py').read(), ns); ns['build']('/project1/lab')
#   ns['apply_prox_material']('/project1/lab/X/geo', effectors=['/project1/lab/MX_prox_material/eff_sphere'])
#   ns['revert_prox_material']('/project1/lab/X/geo')
# build(parent_path, panel=True): demo COMP (scene + material unit), idempotent (ops reused by name, texts / pars /
# wires re-set, custom par values kept, effector objects created only when missing).
# build_unit(comp, demo=False): the material ops + pars inside any baseCOMP (what apply_prox_material makes).
# T-70 safe: nothing destroyed directly (_sd = safe_destroy), own controls_window closed first, pane never moved.
# T-74/T-76: no TOP pixel readback, no text measuring. No functions in storage (T-67). ASCII only.
import os

NAME = 'MX_prox_material'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = REPO + '/builders'
GLSL_DIR = HERE + '/glsl'
LOGIC_FILE = os.path.join(HERE, 'prox_mat_logic.py')
EFF_LOGIC_FILE = os.path.join(HERE, 'effectors_logic.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
NOTES = []

ROWS_CB = """# mx_rows: packs uMX = material rows (prox_mat_logic.pack_mat). Reads pars (+ effector names, point counts) only, so
# TD recooks it when a par changes. Effector transforms are mx_eff's job (EFF_CB).
def _find(P, path):
    if not path:
        return None
    for base in (P, P.parent()):
        try:
            o = base.op(path)
        except Exception:
            o = None
        if o is not None:
            return o
    try:
        return op(path)
    except Exception:
        return None

def _effs(P):
    out = []
    es = getattr(P.par, 'Effsource', None)
    if es is not None and es.eval() == 'list':
        return out                         # shared list: the packed buffer (eff_in), no per-object rows here
    for tok in P.par.Effectors.eval().split():
        cands = []
        for base in (P, P.parent()):
            try:
                cands = list(base.ops(tok))
            except Exception:
                cands = []
            if cands:
                break
        if not cands and tok.startswith('/'):
            o = _find(P, tok)
            cands = [o] if o is not None else []
        for o in cands:
            # class-level check: hasattr(o, 'worldTransform') evaluates the transform = a dependency on motion (T-115)
            if o is not None and o.isCOMP and hasattr(type(o), 'worldTransform') and o not in out and o is not P:
                out.append(o)
    return out[:8]

def _pos(m, x, y, z):
    v = m * tdu.Position(x, y, z)
    return (v.x, v.y, v.z)

def _world(o, L):
    for n in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'px', 'py', 'pz', 'scale'):
        p = getattr(o.par, n, None)
        if p is not None:
            p.eval()                       # dependency: recook when the object moves
    m = o.worldTransform
    return L.PXL.affine_from_points(_pos(m, 0, 0, 0), _pos(m, 1, 0, 0), _pos(m, 0, 1, 0), _pos(m, 0, 0, 1))

def _shape(o):
    if o.OPType != 'geometryCOMP':
        return None
    for c in o.children:
        if c.family in ('SOP', 'POP') and getattr(c, 'render', False):
            return c
    return None

def _eff(o, L):
    world = _world(o, L)
    s = _shape(o)
    kind = L.kind_of(s.OPType if s is not None else '', o.OPType if s is not None else 'nullCOMP')
    k = getattr(o.par, 'Mxkind', None)
    if k is not None and k.eval() not in ('', 'auto'):
        kind = k.eval()
    bmin = bsize = None
    if s is not None:
        try:
            b = s.bounds()
            bmin, bsize = (b.min.x, b.min.y, b.min.z), (b.size.x, b.size.y, b.size.z)
        except Exception:
            pass
    w, size = L.effector_world(world, kind, bmin, bsize)
    e = {'kind': kind, 'world': w}
    if size is not None:
        e['size'] = size
    return e

def src_chop(P, src):
    if src == 'chop':
        o = _find(P, P.par.Pointop.eval())
        return o if o is not None and o.family == 'CHOP' else None
    if src in ('sop', 'pop'):
        return op('pts_' + src)
    return None

def _points(P, L):
    src = P.par.Pointsource.eval()
    if src == 'top':
        t = _find(P, P.par.Pointop.eval())
        if t is None or t.family != 'TOP':
            return 0, 1, 1
        return (L.count_points('top', top_w=t.width, top_h=t.height, stride=P.par.Topstride.eval(),
                               offset=P.par.Topoffset.eval()), t.width, t.height)
    ch = src_chop(P, src)
    if ch is None or not ch.numChans:
        return 0, 1, 1
    n = L.count_chop_points([c.name for c in ch.chans()], ch.numSamples, P.par.Pointlayout.eval())
    w, h = L.tex_dims(n)
    return n, w, h

def _get(P, n):
    p = getattr(P.par, n)
    return p.eval()

def write(scriptOp, rows):
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = len(rows)
    for c, nm in enumerate('xyzw'):
        scriptOp.appendChan(nm).vals = [r[c] for r in rows]

def onCook(scriptOp):
    P = parent()
    L = op('mx_logic').module
    n, w, h = _points(P, L)
    sp = _find(P, P.par.Pointspace.eval()) if P.par.Pointspace.eval() else None
    sw = _world(sp, L) if (sp is not None and hasattr(type(sp), 'worldTransform')) else None
    write(scriptOp, L.pack_mat(lambda k: _get(P, k), len(_effs(P)), n, w, h, sw))
    return
"""

EFF_CB = """# mx_eff: packs uE = 48 effector rows (PX layout, prox_mat_logic.pack_eff). Reads effector transform pars, so TD
# recooks it when an effector moves (Track = frame: every frame). Helpers live in mx_rows_callbacks.
def onCook(scriptOp):
    P = parent()
    L = op('mx_logic').module
    M = op('mx_rows_callbacks').module
    if P.par.Track.eval() == 'frame':
        absTime.frame
    M.write(scriptOp, L.pack_eff([M._eff(o, L) for o in M._effs(P)]))
    return
"""

PTS_CB = """# pts_tex: CHOP / SOP / POP points -> rgba32float rows (xyz, a = 1) for the pts pass. Cooks when the source changes.
def onCook(scriptOp):
    P = parent()
    L = op('mx_logic').module
    src = P.par.Pointsource.eval()
    ch = op('mx_rows_callbacks').module.src_chop(P, src) if src in ('chop', 'sop', 'pop') else None
    pts = []
    if ch is not None and ch.numChans:
        chans = [(c.name, c.numpyArray()) for c in ch.chans()]
        pts = L.points_from_chans(chans, P.par.Pointlayout.eval(), tuple(P.par.Pointchans.eval().split()), 0.0)
    scriptOp.copyNumpyArray(L.points_image(pts))
    return
"""

PEXEC = """# mx_pexec: Applypreset (preset values onto constant pars) and the demo's Animate toggle.
def onPulse(par):
    if par.name == 'Applypreset':
        P = par.owner
        L = op('mx_logic').module
        for k, v in L.preset_values(P.par.Preset.eval()).items():
            p = getattr(P.par, k, None)
            if p is not None and p.mode == ParMode.CONSTANT:
                p.val = v
        sync_src(P)
    return

def sync_src(P):
    # pts_sop / pts_pop cook only for their source (unused = bypassed: no 'Invalid Input' error)
    src = P.par.Pointsource.eval()
    for k in ('sop', 'pop'):
        o = P.op('pts_' + k)
        if o is not None:
            o.bypass = (src != k)

def onValueChange(par, prev):
    if par.name == 'Pointsource':
        sync_src(par.owner)
        return
    if par.name != 'Animate':
        return
    P = par.owner
    L = op('mx_logic').module
    for name, pars in L.DEMO_ANIM.items():
        o = P.op(name)
        if o is None:
            continue
        for k, e in pars.items():
            p = getattr(o.par, k)
            if par.eval():
                p.expr = e
                p.mode = ParMode.EXPRESSION
            elif p.mode == ParMode.EXPRESSION:
                v = p.eval()
                p.mode = ParMode.CONSTANT
                p.val = v
    return
"""

PP = "parent().par.{}"


def _read(path):
    with open(path) as f:
        return f.read()


def _logic():
    ns = {'__name__': 'prox_mat_logic'}
    exec(compile(_read(LOGIC_FILE), LOGIC_FILE, 'exec'), ns)
    return ns


def _eff_logic():
    ns = {'__name__': 'effectors_logic'}
    exec(compile(_read(EFF_LOGIC_FILE), EFF_LOGIC_FILE, 'exec'), ns)
    return ns


def shader_texts():
    """Assembled stage texts (pure; used offline by the tests and by build_unit): header + px_common + common + stage.
    The MAT stages also get the shared effector list block (effectors_logic.consumer_header: uEffRows + selection)."""
    Lg = _logic()
    hdr = Lg['glsl_header']()
    effh = _eff_logic()['consumer_header']()
    lib = _read(os.path.join(GLSL_DIR, 'px_common.glsl'))
    com = _read(os.path.join(GLSL_DIR, 'prox_mat_common.glsl'))
    g = lambda n: _read(os.path.join(GLSL_DIR, 'prox_mat_%s.glsl' % n))
    return {'vert': hdr + effh + lib + '\n' + com + '\n' + g('vert'),
            'pixel': hdr + effh + lib + '\n' + com + '\n' + g('pixel'),
            'pixel_solid': '#define MX_NO_DISSOLVE\n' + hdr + effh + lib + '\n' + com + '\n' + g('pixel'),
            'pts': hdr + g('pts'), 'field': hdr + lib + '\n' + g('field'),
            'vcache': hdr + effh + lib + '\n#define MX_VC_PASS\n' + com + '\n' + g('vcache')}


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


def _mk(c, cls, name, viewer=True):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = viewer
    return o


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _expr(par, e):
    par.expr = str(e)
    par.mode = ParMode.EXPRESSION


def _try(o, name, value=None, expr=None, menu_like=None):
    """Set a par not confirmed on 31550 yet (LIVE CHECK): record misses in NOTES, never fail."""
    p = getattr(o.par, name, None)
    if p is None:
        NOTES.append('%s.%s: no such par' % (o.name, name))
        return None
    try:
        if menu_like is not None:
            names = list(p.menuNames)
            hit = next((m for m in names if any(k in m.lower() for k in menu_like)), None)
            if hit is None:
                NOTES.append('%s.%s: no menu entry like %s in %s' % (o.name, name, menu_like, names))
                return None
            p.val = hit
            return hit
        if expr is not None:
            _expr(p, expr)
        else:
            p.val = value
    except Exception as e:
        NOTES.append('%s.%s: %s' % (o.name, name, e))
    return p


def _menu_src(name, kind):
    """menuSource of a dropdown par (spec option 'menu': kind): /project1/effectors/eff_rt.menu builds the items on
    each menu read (menu_logic.shared_source; empty menu, free text, while the list is missing)."""
    ns = {}
    exec(open(os.path.join(HERE, 'menu_logic.py')).read(), ns)
    return ns['shared_source'](name, kind)


def _pars(c, pages, skip=()):
    for page_name, pars in pages:
        pars = [p for p in pars if p[0] not in skip]
        if not pars:
            continue
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None or (style in ('RGB', 'XYZ') and getattr(
                    c.par, name + ('r' if style == 'RGB' else 'x'), None) is not None):
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
                p.default = default
                p.val = default
            elif style in ('Float', 'Int'):
                p = (page.appendFloat if style == 'Float' else page.appendInt)(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']     # slider range only: no clamps (no limits)
                if 'clampmin' in o:
                    p.min, p.clampMin = o['clampmin'], True
                p.default = default
                p.val = default
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style == 'Str' and o.get('menu'):     # live dropdown through the shared list runtime (T-233)
                p = page.appendStrMenu(name, label=label)[0]
                p.menuSource = _menu_src(name, o['menu'])
                p.default = default
                p.val = default
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
                p.default = default
                p.val = default
            elif style in ('RGB', 'XYZ'):
                ps = page.appendRGB(name, label=label) if style == 'RGB' else page.appendXYZ(name, label=label)
                for p, v in zip(ps, default):
                    if style == 'XYZ':
                        p.normMin, p.normMax = o['min'], o['max']
                    p.default = v
                    p.val = v


def _code(c, name, text):
    d = _mk(c, textDAT, name, viewer=False)
    if d.text != text:
        d.text = text
    return d


def _arrays(o, specs):
    o.seq.array.numBlocks = max(int(o.seq.array.numBlocks), len(specs))
    for k, (nm, ch) in enumerate(specs):
        getattr(o.par, 'array%dname' % k).val = nm
        getattr(o.par, 'array%dtype' % k).val = 'vec4'
        getattr(o.par, 'array%dchop' % k).val = ch
        getattr(o.par, 'array%darraytype' % k).val = 'uniformarray'


def _vecs(o, specs):
    o.seq.vec.numBlocks = max(int(o.seq.vec.numBlocks), len(specs))
    for k, (un, ex) in enumerate(specs):
        getattr(o.par, 'vec{}name'.format(k)).val = un
        for ax, e in zip('xyzw', ex):
            _expr(getattr(o.par, 'vec{}value{}'.format(k, ax)), e)


MXT = ('absTime.seconds', '1.0 / max(project.cookRate, 1)', '0', '0')


def _drop_default_dats(o, keep):
    """A new GLSL TOP / MAT docks its own template DATs (<name>_pixel, _info, _compute1, _vertex): unused here."""
    for d in list(getattr(o, 'docked', []) or []):
        if d.valid and d.name not in keep:
            _sd(d)


def _compute(c, name, code_dat, w_expr, h_expr, inputs):
    g = _mk(c, glslTOP, name)
    _drop_default_dats(g, (code_dat.name,))
    g.par.mode = 'compute'
    g.par.computedat = code_dat.name
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, w_expr)
    _expr(g.par.resolutionh, h_expr)
    g.par.format = 'rgba32float'
    g.par.autodispatchsize = True
    _try(g, 'inputfiltertype', 'nearest')
    _arrays(g, [('uE', 'mx_eff'), ('uMX', 'mx_rows')])
    _vecs(g, [('uMXT', MXT)])
    for i, src in enumerate(inputs):
        _wire(src, g, i)
    return g


EFF_ROWS = '/project1/effectors/eff_rows'


def _eff_buffer(c, mat, slot):
    """Shared effector list -> `uniform samplerBuffer uEffRows` (array slot, texturebuffer) through eff_in (Select
    CHOP of /project1/effectors/eff_rows; eff_none = an empty list when that COMP is missing)."""
    none = _mk(c, constantCHOP, 'eff_none')
    for k, nm in enumerate('xyzw'):
        getattr(none.par, 'name%d' % k).val = nm             # name0 / value0 (as cuelist / db_meter, live)
        getattr(none.par, 'value%d' % k).val = 0
    none.comment = 'Empty effector list (header count 0): used when /project1/effectors is missing.'
    sel = _mk(c, selectCHOP, 'eff_in')
    _expr(sel.par.chops, "'%s' if op('%s') is not None else me.parent().op('eff_none').path" % (EFF_ROWS, EFF_ROWS))
    sel.comment = 'Shared effector list (packed rows, docs/builds/effectors.md) -> uEffRows (Effsource list).'
    mat.seq.array.numBlocks = max(int(mat.seq.array.numBlocks), slot + 1)
    getattr(mat.par, 'array%dname' % slot).val = 'uEffRows'
    getattr(mat.par, 'array%dtype' % slot).val = 'vec4'
    getattr(mat.par, 'array%dchop' % slot).val = 'eff_in'
    getattr(mat.par, 'array%darraytype' % slot).val = 'texturebuffer'


def _script_chop(c, name, text):
    s = _mk(c, scriptCHOP, name)
    want = name + '_callbacks'
    cb = c.op(want)
    if cb is None or cb.OPType != 'textDAT':
        cb = s.par.callbacks.eval()
        if cb is None:
            cb = _mk(c, textDAT, want, viewer=False)
        elif cb.name != want and c.op(want) is None:
            cb.name = want
    if cb.text != text:
        cb.text = text
    s.par.callbacks = cb.name
    return s


def _script_top(c, name, text):
    s = _mk(c, scriptTOP, name)
    want = name + '_callbacks'
    cb = c.op(want)
    if cb is None or cb.OPType != 'textDAT':
        cb = s.par.callbacks.eval()
        if cb is None:
            cb = _mk(c, textDAT, want, viewer=False)
        elif cb.name != want and c.op(want) is None:
            cb.name = want
    if cb.text != text:
        cb.text = text
    s.par.callbacks = cb.name
    _try(s, 'format', 'rgba32float')
    return s


def _row(chan, idx, default, fmt):
    """Expression reading mx_rows[chan][idx]; `default` while mx_rows has not cooked (parked COMP: the channel is None,
    T-163/T-165). The channel is read on every evaluation (lambda argument), so TD keeps the dependency (T-159)."""
    return "(lambda c: %s)(op('mx_rows')['%s'])" % (fmt.format(v='(%s if c is None else c[%d])' % (default, idx)), chan)


def row_exprs(Lg=None):
    """-> (pts_init w, pts_init h, mx_mat sampler0top, sampler1top) expressions, guarded for a parked COMP."""
    Lg = Lg or _logic()
    pi, g0 = Lg['mat_index']('PTS'), Lg['mat_index']('G0')
    return (_row('y', pi, 1, 'max(1, int({v}))'), _row('z', pi, 1, '2 * max(1, int({v}))'),
            _row('y', g0, 0, "'pts' if {v} > 0.5 else 'blank4'"), _row('y', g0, 0, "'field' if {v} > 1.5 else 'blank4'"))


def guard_rows(c):
    """Re-set the mx_rows expressions of an existing unit c to the guarded form (T-165). -> pars set."""
    pw, ph, s0, s1 = row_exprs()
    done = []
    for path, par, e in (('pts_init', 'resolutionw', pw), ('pts_init', 'resolutionh', ph), ('pts', 'resolutionw', pw),
                         ('pts', 'resolutionh', ph), ('mx_mat', 'sampler0top', s0), ('mx_mat', 'sampler1top', s1)):
        o = c.op(path)
        p = getattr(o.par, par, None) if o is not None else None
        if p is not None and p.mode == ParMode.EXPRESSION and 'mx_rows' in p.expr and p.expr != e:
            _expr(p, e)
            done.append('%s.%s' % (path, par))
    return done


def build_unit(c, demo=False):
    """Material ops + pars inside baseCOMP c. Returns the GLSL MAT."""
    Lg = _logic()
    _pars(c, Lg['PAGES'], skip=() if demo else Lg['DEMO_ONLY'])
    lg = _code(c, 'mx_logic', _read(LOGIC_FILE))
    lg.comment = 'Pure logic (copy of builders/prox_mat_logic.py; imports builders/px_logic.py for effector rows).'
    tx = shader_texts()

    # uniforms
    rows = _script_chop(c, 'mx_rows', ROWS_CB)
    rows.comment = 'uMX: material rows (cooks only when a par changes).'
    effc = _script_chop(c, 'mx_eff', EFF_CB)
    effc.comment = 'uE: effector rows, PX layout (cooks when an effector moves; Track = frame: every frame).'
    pex = _mk(c, parameterexecuteDAT, 'mx_pexec', viewer=False)
    if pex.text != PEXEC:
        pex.text = PEXEC
    pex.par.op = c
    pex.par.pars = 'Applypreset Animate Pointsource'
    pex.par.custom = True
    pex.par.builtin = False
    pex.par.valuechange = True
    pex.par.onpulse = True

    # point set
    blank = _mk(c, constantTOP, 'blank4')
    blank.par.outputresolution = 'custom'
    blank.par.resolutionw, blank.par.resolutionh = 2, 2
    blank.par.format = 'rgba32float'
    blank.par.colorr = blank.par.colorg = blank.par.colorb = 0
    blank.par.alpha = 0
    blank.comment = 'Zero 2x2 32F: stand-in sampler when no point set / field is used.'
    psop = _mk(c, soptoCHOP, 'pts_sop')
    _try(psop, 'sop', expr="parent().par.Pointop.eval() if parent().par.Pointsource.eval() == 'sop' else ''")
    psop.comment = 'SOP points (Pointsource sop): tx ty tz per point.'
    ppop = _mk(c, poptoCHOP, 'pts_pop')
    _try(ppop, 'pop', expr="parent().par.Pointop.eval() if parent().par.Pointsource.eval() == 'pop' else ''")
    ppop.comment = 'POP points (Pointsource pop). LIVE CHECK channel names (P0..2 / P(0).. / tx..).'
    ptex = _script_top(c, 'pts_tex', PTS_CB)
    ptex.comment = 'CHOP / SOP / POP -> point rows (rgba32f, a = 1).'
    psrc = _mk(c, selectTOP, 'pts_src')
    _expr(psrc.par.top, "op('pts_tex') if parent().par.Pointsource.eval() in ('chop', 'sop', 'pop') else "
                        "((op('mx_rows_callbacks').module._find(parent(), parent().par.Pointop.eval()) or op('blank4'))"
                        " if parent().par.Pointsource.eval() == 'top' else op('blank4'))")
    psrc.comment = 'Point source texture: pts_tex, the Pointop TOP (rgb = xyz, Topstride texels per point) or blank.'
    PW, PH2, _s0, _s1 = row_exprs(Lg)
    pinit = _mk(c, constantTOP, 'pts_init')
    pinit.par.outputresolution = 'custom'
    _expr(pinit.par.resolutionw, PW)
    _expr(pinit.par.resolutionh, PH2)
    pinit.par.format = 'rgba32float'
    pinit.par.colorr = pinit.par.colorg = pinit.par.colorb = 0
    pinit.par.alpha = 0
    pfb = _mk(c, feedbackTOP, 'pts_fb')
    _wire(pinit, pfb)
    pts = _compute(c, 'pts', _code(c, 'pts_compute', tx['pts']), PW, PH2, [psrc, pfb])
    pts.comment = 'Point set pass (compute): world xyz + velocity rows, stride-decimated to Pointmax.'
    pfb.par.top = 'pts'
    FS = "op('mx_logic').module.field_size(parent().par.Gridres.eval())[{}]"
    fld = _compute(c, 'field', _code(c, 'field_compute', tx['field']), FS.format(0), FS.format(1), [pts])
    fld.comment = 'Point field (compute): Gridres^3 nearest distance / density / velocity atlas (Pointpath field).'

    # material
    vd = _code(c, 'mx_vert', tx['vert'])
    pd = _code(c, 'mx_pixel', tx['pixel'])
    pd.comment = 'Pixel shader with dissolve (picked while Dissolvemode is not off).'
    ps = _code(c, 'mx_pixel_solid', tx['pixel_solid'])
    ps.comment = 'Pixel shader without the dissolve discard (Dissolvemode off): early depth works (perf-b2-w4).'
    mat = _material(c, 'mx_mat', Lg, vd, pd)
    src = c.par.Pointsource.eval()
    psop.bypass, ppop.bypass = src != 'sop', src != 'pop'
    mat.comment = ('Proximity PBR GLSL MAT (TD PBR lighting + proximity drives). Put it on any Geometry COMP '
                   '(apply_prox_material), instancing-safe (TDDeform).')
    return mat


MAT_VECS_EFF = dict(
    on="parent().par.Effsource.eval() == 'list'", gain='1', comb='parent().par.Combine.menuIndex', rscale='1',
    rag='parent().par.Ragged.eval()', ragf='parent().par.Raggedfreq.eval()',
    ovr="parent().par.Listfalloff.eval() == 'material'", rad='parent().par.Radius.eval()',
    exp_='parent().par.Falloffexp.eval()', shape='parent().par.Shape.menuIndex')
VC_ON = "parent().par.Dispcache.eval() and parent().par.Dispmode.eval() != 'off'"
# uMXT.x (seconds) only where a shader uses it: ripple / noise displacement, dissolve noise speed, detail normal speed.
# Otherwise 0 (same pixels: t only multiplies those speeds), so the MATs / vc_cache carry no time dependency and
# recook only when something they read changes (a still scene renders once; perf-b2-w4).
T_DISP = "parent().par.Dispmode.eval() in ('ripple', 'noise')"
T_MAT = ("%s or (parent().par.Dissolvemode.eval() != 'off' and parent().par.Noisespeed.eval() != 0) "
         "or parent().par.Nrmspeed.eval() != 0" % T_DISP)


def _mxt(cond):
    return ('absTime.seconds if (%s) else 0.0' % cond,) + MXT[1:]


def _uniforms(o, Lg, mxt):
    """Arrays + vectors shared by every MAT of the unit and the vc_cache pass: uE, uMX, uEffRows, uVG, uMXT +
    the shared-list selection vectors. Returns the number of vec blocks used."""
    _arrays(o, [('uE', 'mx_eff'), ('uMX', 'mx_rows')])
    _eff_buffer(o.parent(), o, 2)
    o.seq.array.numBlocks = max(int(o.seq.array.numBlocks), 4)
    o.par.array3name = 'uVG'
    o.par.array3type = 'vec4'
    o.par.array3chop = 'vc_rows'
    o.par.array3arraytype = 'texturebuffer'
    specs = [('uMXT', mxt)] + _eff_logic()['consumer_vecs'](**MAT_VECS_EFF)
    _vecs(o, specs)
    return len(specs)


def _material(c, name, Lg, vd, pd, slot=-1):
    """One GLSL MAT of the unit (all share mx_vert / mx_pixel). slot = its geometry's vertex cache slot (uVC.x)."""
    _s0, _s1 = row_exprs(Lg)[2:]
    mat = _mk(c, glslMAT, name)
    _drop_default_dats(mat, (vd.name, pd.name, pd.name + '_solid'))
    mat.par.vdat = vd.name
    _expr(mat.par.pdat, "'%s' if parent().par.Dissolvemode.eval() != 'off' else '%s_solid'" % (pd.name, pd.name))
    nv = _uniforms(mat, Lg, _mxt(T_MAT))
    mat.seq.vec.numBlocks = max(int(mat.seq.vec.numBlocks), nv + 1)
    getattr(mat.par, 'vec%dname' % nv).val = 'uVC'
    for ax, v in zip('xyzw', (slot, 0, 0, 0)):
        getattr(mat.par, 'vec%dvalue%s' % (nv, ax)).val = v
    mat.seq.sampler.numBlocks = max(int(mat.seq.sampler.numBlocks), 3)
    mat.par.sampler0name = 'sPts'
    _expr(mat.par.sampler0top, _s0)
    mat.par.sampler1name = 'sField'
    _expr(mat.par.sampler1top, _s1)
    mat.par.sampler2name = 'sVC'
    _expr(mat.par.sampler2top, "'vc_cache' if (%s) else 'blank4'" % VC_ON)
    for k in (0, 1, 2):
        _try(mat, 'sampler%dfilter' % k, 'nearest')
    _try(mat, 'cullface', expr="'neither' if parent().par.Dissolvemode.eval() != 'off' else 'userender'")
    _try(mat, 'blending', expr="1 if (parent().par.Opacityon.eval() or parent().par.Basealpha.eval() < 1) else 0")
    mat.comment = ('Proximity PBR GLSL MAT (TD PBR lighting + proximity drives). Put it on any Geometry COMP '
                   '(apply_prox_material), instancing-safe (TDDeform). Vertex cache slot %d.' % slot)
    return mat


VC_ROWS_CB = """# vc_rows: vertex cache slot table (uVG) = prox_mat_logic.vc_rows of vc_slots (slot, geo, chop). Reads each geo's
# transform pars + worldTransform and its SOP point count, so TD recooks it when one moves or changes.
def onCook(scriptOp):
    P = parent()
    L = op('mx_logic').module
    M = op('mx_rows_callbacks').module
    t = op('vc_slots')
    slots = []
    for r in range(1, t.numRows if t is not None else 0):
        g = op(t[r, 'geo'].val)
        ch = op(t[r, 'chop'].val)
        if g is None or ch is None:
            slots.append(([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]], 0))
            continue
        for n in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'px', 'py', 'pz', 'scale'):
            p = getattr(g.par, n, None)
            if p is not None:
                p.eval()
        m = g.worldTransform
        inst = getattr(g.par, 'instancing', None)
        n = ch.numSamples if (ch.numChans >= 6 and not (inst is not None and inst.eval())) else 0
        slots.append(([[m[i, j] for j in range(4)] for i in range(3)], n))
    on = bool(P.par.Dispcache.eval()) and P.par.Dispmode.eval() != 'off'
    M.write(scriptOp, L.vc_rows(slots, on))
    return
"""

VC_SRC_CB = """# vc_src: SOP-space points of every vertex cache slot (vc_slots chop: tx ty tz nx ny nz) -> rgba32float, P rows then
# N rows (prox_mat_logic.vc_image). Cooks only when a slot's SOP changes.
def onCook(scriptOp):
    L = op('mx_logic').module
    t = op('vc_slots')
    chunks = []
    for r in range(1, t.numRows if t is not None else 0):
        ch = op(t[r, 'chop'].val)
        if ch is None or ch.numChans < 6:
            chunks.append(([], []))
            continue
        a = [ch[n].numpyArray() for n in ('tx', 'ty', 'tz', 'nx', 'ny', 'nz')]
        P = list(zip(a[0], a[1], a[2]))
        N = list(zip(a[3], a[4], a[5]))
        chunks.append((P, N))
    scriptOp.copyNumpyArray(L.vc_image(chunks))
    return
"""


def _relc(c, o):
    """Path of o as the COMP's own ops read it (op() from a DAT directly in c, a sibling OP par): relative when o is
    inside c (a dropped copy uses its own ops), absolute when it is the scene's (drop-in, 28 Oct)."""
    return o.path[len(c.path) + 1:] if o.path.startswith(c.path + '/') else o.path


def _render_sop(geo):
    for ch in geo.children:
        if ch.family == 'SOP' and getattr(ch, 'render', False):
            return ch
    return None


def vcache(c, pairs):
    """Vertex cache for the unit c: pairs = [(GLSL MAT, Geometry COMP)], slot k = pairs[k]. Each MAT gets uVC.x = k.
    Ops: vc_slots (table), vc_sop<k> (SOP to CHOP: P + N of the geo's render SOP), vc_src (Script TOP), vc_rows
    (Script CHOP -> uVG), vc_s0 / vc_s1 (the MAT's sPts / sField textures as inputs), vc_compute + vc_cache (compute,
    W x 3H). A geo without a SOP or with instancing gets an empty slot (its vertices run the displacement themselves)."""
    Lg = _logic()
    tx = shader_texts()
    tab = _mk(c, tableDAT, 'vc_slots', viewer=False)
    rows = [['slot', 'geo', 'chop']]
    for k, (mat, geo) in enumerate(pairs):
        ch = _mk(c, soptoCHOP, 'vc_sop%d' % k)
        s = _render_sop(geo) if geo is not None else None
        _try(ch, 'sop', _relc(c, s) if s is not None else '')
        _try(ch, 'position', True)
        _try(ch, 'normal', True)
        ch.comment = 'Vertex cache slot %d: P + N of %s (SOP space).' % (k, s.path if s is not None else '-')
        rows.append([str(k), _relc(c, geo) if geo is not None else '', _relc(c, ch)])
        getattr(mat.par, 'vec%dvaluex' % _vc_vec(mat)).val = k
    for k in range(len(pairs), 64):                    # slots that are gone
        o = c.op('vc_sop%d' % k)
        if o is None:
            break
        _sd(o)
    tab.clear()
    for r in rows:
        tab.appendRow(r)
    tab.comment = 'Vertex cache slots: slot, geometry, its point CHOP (vcache()).'
    vr = _script_chop(c, 'vc_rows', VC_ROWS_CB)
    vr.comment = 'uVG: vertex cache slot table (on, W, H, n; per slot world / normal rows, offset, count).'
    vs = _script_top(c, 'vc_src', VC_SRC_CB)
    vs.comment = 'Vertex cache points: SOP-space P rows then N rows of every slot (cooks when a SOP changes).'
    s0, s1 = row_exprs(Lg)[2:]
    sel = []
    for k, e in ((0, s0), (1, s1)):
        st = _mk(c, selectTOP, 'vc_s%d' % k)
        _expr(st.par.top, e)
        st.comment = 'Vertex cache input %d = the MAT\'s %s texture.' % (k + 1, ('sPts', 'sField')[k])
        sel.append(st)
    vd = _code(c, 'vc_compute', tx['vcache'])
    g = _mk(c, glslTOP, 'vc_cache')
    _drop_default_dats(g, (vd.name,))
    g.par.mode = 'compute'
    g.par.computedat = vd.name
    g.par.outputresolution = 'custom'
    g.par.resolutionw = Lg['VC_W']
    _expr(g.par.resolutionh, "(lambda c: 3 * max(1, int(1 if c is None else c[0])))(op('vc_rows')['z'])")
    g.par.format = 'rgba32float'
    g.par.autodispatchsize = True
    _try(g, 'inputfiltertype', 'nearest')
    _uniforms(g, Lg, _mxt(T_DISP))
    for i, src in enumerate([vs] + sel):
        _wire(src, g, i)
    g.comment = ('Vertex cache (compute): the vertex displacement once per point of each slot (offset, normal, rest '
                 'rows). Pulled by the MATs only while Dispcache is on and Dispmode is not off.')
    return {'slots': len(pairs), 'cache': g.path}


def _vc_vec(mat):
    for k in range(int(mat.seq.vec.numBlocks)):
        if getattr(mat.par, 'vec%dname' % k).eval() == 'uVC':
            return k
    raise ValueError('no uVC on %s' % mat.path)


def _sop(geo, cls, name):
    s = _mk(geo, cls, name)
    return s


def _drop_default(g, keep=()):
    """A new Geometry COMP holds a default torus1: a torusPOP on 31550 (a torusSOP before). Delete every child not
    in `keep` by name, whatever its family (T-163)."""
    for ch in list(g.children):
        if ch.valid and ch.name not in keep:
            _sd(ch)


def _mesh(c, name, kind, xf, comment, mat='mx_mat'):
    g = _mk(c, geometryCOMP, name)
    _drop_default(g, ('shape', 'normals'))
    if kind == 'sphere':
        s = _mk(g, sphereSOP, 'shape')
        _try(s, 'type', menu_like=('mesh',))       # 31550: poly uses freq, mesh uses rows / cols
        _try(s, 'rows', 80)
        _try(s, 'cols', 80)
        for p in ('radx', 'rady', 'radz'):
            _try(s, p, 0.55)
    elif kind == 'torus':
        s = _mk(g, torusSOP, 'shape')
        _try(s, 'radx', 0.6)
        _try(s, 'rady', 0.22)
        _try(s, 'rows', 60)
        _try(s, 'cols', 120)
    else:
        s = _mk(g, gridSOP, 'shape')
        _try(s, 'orient', menu_like=('zx',))
        _try(s, 'sizex', 2.4)
        _try(s, 'sizey', 2.4)
        _try(s, 'rows', 200)
        _try(s, 'cols', 200)
    an = _mk(g, attributecreateSOP, 'normals')
    _wire(s, an)
    _try(an, 'compnml', True)
    an.render = an.display = True
    s.render = s.display = False
    g.par.tx, g.par.ty, g.par.tz, g.par.rx = xf
    g.par.material = mat
    g.comment = comment + ' Material %s.' % mat
    return g


def _effector_objects(c, Lg):
    made = []
    wire = _mk(c, wireframeMAT, 'giz_mat')
    _try(wire, 'colorr', 0.2)
    _try(wire, 'colorg', 1.0)
    _try(wire, 'colorb', 0.6)
    wire.comment = 'Gizmo wire material (effector objects in the preview only).'
    for name, kind in (('eff_box', 'box'), ('eff_sphere', 'sphere')):
        o = c.op(name)
        if o is None:
            o = c.create(geometryCOMP, name)
            o.viewer = True
            _drop_default(o)
            s = o.create(boxSOP if kind == 'box' else sphereSOP, 'shape')
            if kind == 'sphere':
                for p in ('radx', 'rady', 'radz'):
                    _try(s, p, 0.5)
            s.render = s.display = True
            o.par.material = 'giz_mat'
            sc = 0.55 if kind == 'box' else 0.6
            o.par.sx = o.par.sy = o.par.sz = sc
            made.append(name)
        o.comment = ('Effector %s: move / rotate / scale it; the material sees the exact SDF (box = bounds of its SOP). '
                     'Only in the preview render.' % kind)
    n = c.op('eff_null')
    if n is None:
        n = c.create(nullCOMP, 'eff_null')
        n.viewer = True
        made.append('eff_null')
    n.comment = 'Effector Null = point effector. giz_null (child box) shows it in the preview.'
    gz = c.op('giz_null')
    if gz is None:
        gz = c.create(geometryCOMP, 'giz_null')
        gz.viewer = True
        _drop_default(gz)
        b = gz.create(boxSOP, 'shape')
        _try(b, 'sizex', 0.12)
        _try(b, 'sizey', 0.12)
        _try(b, 'sizez', 0.12)
        b.render = b.display = True
        gz.par.material = 'giz_mat'
    if not gz.inputCOMPConnectors[0].connections:
        gz.inputCOMPConnectors[0].connect(n)
    for name, pars in Lg['DEMO_ANIM'].items():
        o = c.op(name)
        if o is None:
            continue
        for k, e in pars.items():
            p = getattr(o.par, k)
            if c.par.Animate.eval():
                if p.mode != ParMode.EXPRESSION or p.expr != e:
                    _expr(p, e)
            elif name in made:
                p.val = Lg['DEMO_HOME'][name].get(k, 0.0)
    return made


ENV_PULL = '''# %s_pull: the Environment Light COMP does not pull its map TOP (live main 27 Oct: the hold chain never cooked
# with no viewer on it), so this cooks the hold each frame while the capture is in use (cheap off capture frames).
def onFrameStart(frame):
\tp = parent()
\tif %s:
\t\tp.op('%s_hold').cook()
\treturn
'''


def env_capture(c, prefix, geo_expr, centre_exprs, res_expr, everyn_expr, dimmer_expr=None, make_light=True,
                lights='', use_cond='True'):
    """Scene environment for reflective (chrome) objects (GE3, W1-E, docs/builds/px_geo.md): `<prefix>_cam` (90 deg
    camera at the object's centre), `<prefix>_cube` (cube-map Render TOP of geo_expr, res_expr px) -> `<prefix>_equi`
    (Projection TOP, equirect 2 res x res) -> `<prefix>_hold` (Cache TOP, size 1, active only every N-th frame: it
    holds the last map and pulls the cube only on those frames; live b3 27 Oct: the Render TOP's own `render` toggle
    gives black when off, it does not hold) -> `<prefix>_light` (Environment Light COMP on the hold). Put
    `<prefix>_light` in the lights of the Render TOP that draws the chrome object. Expressions run in `c`. Shared by
    MX_prox_material (Envmode scene; make_light False: env1 switches to the hold) and BL_splat_render (Geoenv).
    lights = the cube render's Light COMPs (lit meshes in the capture need them; live b3: without them MX meshes
    render black into the cube). Returns the light (or the hold TOP without one)."""
    cam = _mk(c, cameraCOMP, prefix + '_cam')
    for par, e in zip((cam.par.tx, cam.par.ty, cam.par.tz), centre_exprs):
        _expr(par, e)
    _try(cam, 'fov', 90.0)
    _try(cam, 'near', 0.01)
    _try(cam, 'far', 1000.0)
    cam.comment = 'Env capture camera: sits at the reflective object (centre pars); the cube render turns it 6 ways.'
    r = _mk(c, renderTOP, prefix + '_cube')
    r.par.camera = cam.name
    _expr(r.par.geometry, geo_expr)
    r.par.lights = lights
    _try(r, 'rendermode', menu_like=('cubemap',))
    r.par.outputresolution = 'custom'
    _expr(r.par.resolutionw, res_expr)
    _expr(r.par.resolutionh, res_expr)
    _try(r, 'format', 'rgba16float')
    _try(r, 'bgcolora', 1.0)
    rp = getattr(r.par, 'render', None)
    if rp is not None and rp.mode == ParMode.EXPRESSION:      # an earlier build gated it here: black when off
        rp.expr = ''
        rp.mode = ParMode.CONSTANT
        rp.val = True
    r.comment = 'Env capture: low-res cube map of the scene for chrome / reflective objects.'
    eq = _mk(c, projectionTOP, prefix + '_equi')
    _wire(r, eq)
    _try(eq, 'input', menu_like=('cubemap',))
    _try(eq, 'output', menu_like=('equirect',))
    eq.par.outputresolution = 'custom'
    _expr(eq.par.resolutionw, '2 * (%s)' % res_expr)
    _expr(eq.par.resolutionh, res_expr)
    _try(eq, 'format', 'rgba16float')
    eq.comment = 'Env capture: cube -> equirect (2D, so the Cache TOP can hold it).'
    # every N frames (twin = splat_render_logic.env_render_now). A Cache TOP alone still pulls its input every
    # frame (live b3: cube cooks = render cooks), so a Switch TOP in front picks a 1 px constant on the other frames
    # (a Switch cooks only its selected input) and the Cache stores only on the capture frames.
    now = 'absTime.frame %% max(1, int(%s)) == 0' % everyn_expr
    idle = _mk(c, constantTOP, prefix + '_idle')
    idle.par.outputresolution = 'custom'
    idle.par.resolutionw, idle.par.resolutionh = 1, 1
    gate = _mk(c, switchTOP, prefix + '_gate')
    _wire(idle, gate, 0)
    _wire(eq, gate, 1)
    _expr(gate.par.index, '1 if (%s) else 0' % now)
    gate.comment = 'Env capture: pulls the cube only on capture frames (else the 1 px idle input).'
    hold = _mk(c, cacheTOP, prefix + '_hold')
    _wire(gate, hold)
    _try(hold, 'cachesize', 1)
    _try(hold, 'outputindex', 0)
    _try(hold, 'active', expr=now)
    hold.comment = 'Env capture: holds the last map (stores only on capture frames).'
    pull = _mk(c, executeDAT, prefix + '_pull', viewer=False)
    pull.text = ENV_PULL % (prefix, use_cond, prefix)
    pull.par.framestart = True
    pull.par.active = True
    pull.comment = 'Env capture: cooks the hold each frame while in use (the env light does not pull it).'
    if not make_light:
        return hold
    env = _mk(c, environmentlightCOMP, prefix + '_light')
    _try(env, 'envlightmap', hold.name)
    if dimmer_expr:
        _try(env, 'dimmer', expr=dimmer_expr)
    env.comment = 'Env light on the scene map: reflective MX / PBR materials show the scene.'
    return env


DEMO_MATS = {'geo_plane': 'mx_mat', 'geo_torus': 'mx_mat_torus', 'geo_sphere': 'mx_mat_sphere'}


def _scene(c, Lg):
    vd, pd = c.op('mx_vert'), c.op('mx_pixel')
    pairs = []
    for m in Lg['DEMO_MESHES']:
        mname = DEMO_MATS.get(m[0], 'mx_mat')
        mat = c.op(mname) if mname == 'mx_mat' else _material(c, mname, Lg, vd, pd)
        pairs.append((mat, _mesh(c, *m, mat=mname)))
    vcache(c, pairs)
    made = _effector_objects(c, Lg)
    env_map = _mk(c, rampTOP, 'env_map')
    env_map.par.outputresolution = 'custom'
    env_map.par.resolutionw, env_map.par.resolutionh = 512, 256
    _try(env_map, 'type', menu_like=('vert',))
    env_map.comment = 'Environment map (equirect gradient; edit the ramp keys or point env1 at an HDRI TOP).'
    env = _mk(c, environmentlightCOMP, 'env1')
    # Envmode (Environment page, W1-E GE3): gradient = env_map (the v1 default), top = Envtop (HDRI / any TOP),
    # scene = env_cube (a cube of Envgeo seen from Envcentre, every Enveveryn frames)
    env_capture(c, 'env', "parent().par.Envgeo.eval() if parent().par.Envmode.eval() == 'scene' else ''",
                ('parent().par.Envcentrex', 'parent().par.Envcentrey', 'parent().par.Envcentrez'),
                "max(16, int(parent().par.Envres))", 'parent().par.Enveveryn', make_light=False, lights='light1',
                use_cond="p.par.Envmode.eval() == 'scene'")
    _try(env, 'envlightmap', expr="{'top': parent().par.Envtop.eval() or 'env_map', 'scene': 'env_hold'}"
                                  ".get(parent().par.Envmode.eval(), 'env_map')")
    _try(env, 'dimmer', expr='parent().par.Envdimmer')
    l1 = _mk(c, lightCOMP, 'light1')
    l1.par.tx, l1.par.ty, l1.par.tz = 2.5, 4.0, 5.0
    _try(l1, 'dimmer', 1.2)
    cam = _mk(c, cameraCOMP, 'cam')
    cam.par.tx, cam.par.ty, cam.par.tz = 0.0, 0.2, 3.9
    _try(cam, 'fov', 50.0)
    ref = _mk(c, pbrMAT, 'ref_pbr')
    for a, b in zip(('basecolorr', 'basecolorg', 'basecolorb'), ('Basecolourr', 'Basecolourg', 'Basecolourb')):
        _try(ref, a, expr=PP.format(b))
    _try(ref, 'roughness', expr=PP.format('Roughfar'))
    _try(ref, 'metallic', expr=PP.format('Metalfar'))
    _try(ref, 'specularlevel', expr=PP.format('Specular'))
    _try(ref, 'ambientocclusion', expr=PP.format('Ao'))
    for a, b in zip(('emitr', 'emitg', 'emitb'), ('Emitbaser', 'Emitbaseg', 'Emitbaseb')):
        _try(ref, a, expr=PP.format(b))
    _try(ref, 'shadowstrength', expr=PP.format('Shadowstrength'))
    ref.comment = 'Plain PBR MAT with the far-field values: reference for the far = plain PBR check (M3) + shader export.'

    def render(name, geo, w, h):
        r = _mk(c, renderTOP, name)
        r.par.camera = 'cam'
        r.par.geometry = geo
        r.par.lights = 'light1 env1'
        r.par.outputresolution = 'custom'
        _expr(r.par.resolutionw, w)
        _expr(r.par.resolutionh, h)
        _try(r, 'format', 'rgba16float')
        _try(r, 'antialias', expr="parent().par.Antialias.eval()")
        _try(r, 'bgcolora', 1.0)
        return r
    ro = render('render_out', 'geo_*', "max(1, int(parent().par.Resx.eval()))", "max(1, int(parent().par.Resy.eval()))")
    ro.comment = 'Clean output: meshes only (Resx x Resy, 16F).'
    rp = render('render_preview', 'geo_* eff_box eff_sphere giz_null',
                "max(1, int(parent().par.Resx.eval()) // 2)", "max(1, int(parent().par.Resy.eval()) // 2)")
    rp.comment = 'Preview: meshes + effector gizmos (half res, not an output).'
    out1 = _mk(c, outTOP, 'out1')
    _wire(ro, out1)
    pv = _mk(c, nullTOP, 'preview')
    _wire(rp, pv)
    dp = _mk(c, noiseCHOP, 'demo_pts')
    _try(dp, 'channelname', 'tx ty tz')
    _try(dp, 'timeslice', False)
    _try(dp, 'startunit', 'samples')
    _try(dp, 'endunit', 'samples')
    _try(dp, 'start', 0)
    _try(dp, 'end', 63)
    _try(dp, 'amp', 1.2)
    _try(dp, 'period', 0.25)                     # seconds at rate 60: 64 samples span ~4 periods
    _try(dp, 'tx', expr='absTime.seconds * 0.02')
    dp.comment = 'Demo point set (64 noise points, tx ty tz per sample): Pointsource chop + Pointop demo_pts.'
    return made


def build(parent_path='/project1/lab', panel=True):
    del NOTES[:]
    Lg = _logic()
    pc = op(parent_path)
    c = pc.op(NAME) or pc.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('MX_prox_material: proximity-driven PBR material for any mesh. Effectors (eff_box / eff_sphere / '
                 'eff_null or any objects named in Effectors) and point sets (Points page) drive colour, roughness, '
                 'metallic, emission, rim, dissolve, opacity, detail normal and vertex displacement. out1 = clean '
                 'render, preview = with gizmos. apply_prox_material(geo) puts it on any Geometry COMP.')
    was_open = _close_window(c)
    build_unit(c, demo=True)
    made = _scene(c, Lg)
    c.par.opviewer.expr = "me.op('preview') if me.par.Showeff.eval() else me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    info = None
    if panel:
        ns = dict(globals())
        exec(_read(ZKIT_FILE), ns)
        info = ns['build_controls'](c.path, pages=Lg['PANEL_PAGES'], d=56, cols=8, open_window=was_open)
    lay = _layout(c, Lg)
    return {'comp': c.path, 'ops': len(c.children), 'notes': list(NOTES), 'effectors_made': made,
            'panel': str(info)[:300], 'layout': str(lay)[:400]}


def _layout(c, Lg):
    def with_docked(names):
        out = []
        for n in names:
            o = c.op(n)
            if o is None:
                continue
            out.append(n)
            for d in list(getattr(o, 'docked', []) or []):
                if d.valid and d.name not in out:
                    out.append(d.name)
        return out
    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': with_docked(['controls', 'controls_window', 'mx_pexec', 'mx_logic']),
         'body': 'zkit panel (pulse Opencontrols). mx_pexec: Applypreset, Animate. mx_logic = prox_mat_logic.py.'},
        {'title': 'Effectors', 'role': 'input', 'ops': with_docked(['eff_box', 'eff_sphere', 'eff_null', 'giz_null',
                                                                    'giz_mat']),
         'body': 'Effector objects (Effectors par). Box / sphere = exact SDF of their SOP bounds, Null = point.'},
        {'title': 'Point set', 'role': 'input', 'ops': with_docked(['demo_pts', 'pts_sop', 'pts_pop', 'pts_tex',
                                                                    'pts_tex_callbacks', 'pts_src', 'pts_init', 'pts_fb',
                                                                    'pts', 'pts_compute', 'field', 'field_compute',
                                                                    'blank4'])},
        {'title': 'Uniforms', 'role': 'process', 'ops': with_docked(['mx_rows', 'mx_rows_callbacks', 'mx_eff',
                                                                     'mx_eff_callbacks']),
         'body': 'mx_rows -> uMX[] material rows (par changes), mx_eff -> uE[] effector rows (motion).'},
        {'title': 'Material', 'role': 'process', 'ops': with_docked(['mx_vert', 'mx_pixel', 'mx_pixel_solid', 'mx_mat', 'mx_mat_torus',
                                                                     'mx_mat_sphere', 'ref_pbr']),
         'body': 'GLSL MATs (one per mesh: its vertex cache slot; TD PBR lighting + proximity). ref_pbr = plain PBR '
                 'with the far values (checks).'},
        {'title': 'Vertex cache', 'role': 'process', 'ops': with_docked(['vc_slots', 'vc_sop0', 'vc_sop1', 'vc_sop2',
                                                                         'vc_src', 'vc_src_callbacks', 'vc_rows',
                                                                         'vc_rows_callbacks', 'vc_s0', 'vc_s1',
                                                                         'vc_compute', 'vc_cache']),
         'body': 'Displacement once per point (Dispcache): vc_cache compute -> each MAT reads its slot.'},
        {'title': 'Scene', 'role': 'process', 'ops': with_docked(['geo_sphere', 'geo_torus', 'geo_plane', 'env_map',
                                                                  'env1', 'env_cam', 'env_cube', 'env_equi',
                                                                  'env_idle', 'env_gate', 'env_hold', 'env_pull',
                                                                  'light1', 'cam'])},
        {'title': 'Render + out', 'role': 'output', 'ops': with_docked(['render_out', 'out1', 'render_preview',
                                                                        'preview'])},
    ]
    for s in stages:
        s.setdefault('body', '')
    stages = [s_ for s_ in stages if s_['ops']]
    try:
        return op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:
        return 'layout failed: {}'.format(e)


def apply_prox_material(geo_comp_path, effectors=(), like=None, name=None, panel=False, unit_parent=None):
    """Put a proximity material on any Geometry COMP: builds a material unit (baseCOMP `<geo>_proxmat`, sibling of
    the geo), copies values from `like` (default: the lab's MX_prox_material if present), sets Effectors (paths or
    names), and points the geo's material at it. The previous material path is kept in the geo's storage (plain str)
    for revert_prox_material(). unit_parent = put the unit in another (cooking) COMP instead, e.g. when the geo's
    own COMP is parked (a parked COMP's Script CHOPs never cook, T-105)."""
    del NOTES[:]
    Lg = _logic()
    geo = op(geo_comp_path)
    if geo is None or geo.OPType != 'geometryCOMP':
        raise ValueError('not a Geometry COMP: %s' % geo_comp_path)
    holder = op(unit_parent) if unit_parent else geo.parent()
    uname = name or (geo.name + '_proxmat')
    u = holder.op(uname) or holder.create(baseCOMP, uname)
    u.allowCooking = True
    mat = build_unit(u, demo=False)
    vcache(u, [(mat, geo)])
    src = op(like) if like else op('/project1/lab/' + NAME)
    copied = 0
    if src is not None and src is not u:
        for pg in u.customPages:
            for p in pg.pars:
                q = getattr(src.par, p.name, None)
                if q is None or p.isPulse or p.name in ('Effectors', 'Pointop', 'Pointspace'):
                    continue
                try:
                    p.val = q.eval()
                    copied += 1
                except Exception:
                    pass
    u.par.Effectors = ' '.join(effectors)
    if effectors:
        u.par.Effsource = 'objects'            # explicit objects = the v1 path; no objects = the shared list
    if geo.fetch('mx_prev_material', None, search=False) is None:
        prev = geo.par.material.eval()
        geo.store('mx_prev_material', prev.path if prev is not None else '')
    geo.store('mx_unit', u.path)
    geo.par.material = mat.path
    u.comment = 'Proximity material for %s (apply_prox_material). Effectors: %s' % (geo.path, ' '.join(effectors))
    info = None
    if panel:
        ns = dict(globals())
        exec(_read(ZKIT_FILE), ns)
        info = ns['build_controls'](u.path, pages=[p for p in Lg['PANEL_PAGES']], d=56, cols=8)
    return {'unit': u.path, 'material': mat.path, 'geo': geo.path, 'copied_pars': copied, 'notes': list(NOTES),
            'panel': str(info)[:200]}


def revert_prox_material(geo_comp_path, name=None):
    geo = op(geo_comp_path)
    if geo is None:
        raise ValueError('no op %s' % geo_comp_path)
    prev = geo.fetch('mx_prev_material', None, search=False)
    if prev is not None:
        geo.par.material = prev
        geo.unstore('mx_prev_material')
    upath = geo.fetch('mx_unit', None, search=False)
    if upath is not None:
        geo.unstore('mx_unit')
    u = op(upath) if upath else geo.parent().op(name or (geo.name + '_proxmat'))
    if u is not None:
        _sd(u)
    return {'geo': geo.path, 'material': geo.par.material.eval().path if geo.par.material.eval() else '',
            'removed': u is not None}


def env_upgrade(comp_path='/project1/lab/' + NAME):
    """W1-E on an existing MX_prox_material demo without a full rebuild: mx_logic text, Environment page,
    env capture ops + env1 following Envmode, Preset menu (Chrome mirror), layout. No effectors re-attach, no panel
    (run panel_only() in its own exec)."""
    del NOTES[:]
    Lg = _logic()
    c = op(comp_path)
    c.allowCooking = True
    _code(c, 'mx_logic', _read(LOGIC_FILE))
    _pars(c, [pg for pg in Lg['PAGES'] if pg[0] == 'Environment'])
    p = c.par.Preset
    p.menuNames, p.menuLabels = Lg['PRESET_NAMES'], Lg['PRESET_LABELS']
    env = c.op('env1')
    env_capture(c, 'env', "parent().par.Envgeo.eval() if parent().par.Envmode.eval() == 'scene' else ''",
                ('parent().par.Envcentrex', 'parent().par.Envcentrey', 'parent().par.Envcentrez'),
                "max(16, int(parent().par.Envres))", 'parent().par.Enveveryn', make_light=False, lights='light1',
                use_cond="p.par.Envmode.eval() == 'scene'")
    _try(env, 'envlightmap', expr="{'top': parent().par.Envtop.eval() or 'env_map', 'scene': 'env_hold'}"
                                  ".get(parent().par.Envmode.eval(), 'env_map')")
    _try(env, 'dimmer', expr='parent().par.Envdimmer')
    for o in c.children:
        if o.family == 'TOP':
            o.viewer = True
    lay = _layout(c, Lg)
    return {'comp': c.path, 'ops': len(c.children), 'notes': list(NOTES), 'layout': str(lay)[:200]}


def panel_only(comp_path='/project1/lab/' + NAME):
    """zkit panel with the Environment page (own exec after env_upgrade, T-76 / T-98)."""
    Lg = _logic()
    ns = dict(globals())
    exec(_read(ZKIT_FILE), ns)
    return str(ns['build_controls'](comp_path, pages=Lg['PANEL_PAGES'], d=56, cols=8))[:300]


def park(comp_path='/project1/lab/' + NAME):
    c = op(comp_path)
    if c is not None:
        _close_window(c)
        c.allowCooking = False
    return {'parked': comp_path}
