# effectors_grid - the shared voxel grid of /project1/effectors (lane E, 27 Oct 2026, TD 2025.31550): COMP
# /project1/effectors/grid with the K36 / GE2 distance field (kind `cloud`: one scatter pass per enabled cloud row ->
# seed -> 8 JFA passes -> grid_field) and the SA23 paint volume (paint_init -> paint_fb (Feedback) -> paint_step ->
# paint_out). Copied into the Text DAT `eff_grid` by builders/effectors.py; pure logic in eff_grid_logic
# (builders/effectors_grid_logic.py); shaders builders/glsl/eff_grid_*.glsl (copied into Text DATs by build()).
# Off by default and cheap: the grid COMP is parked (allowCooking False) unless Gridon or Painton is on, and nothing
# in it cooks unless a consumer pulls grid_field / paint_out. Rules kept: T-70 safe_destroy only; T-47 multi-pass =
# compute; T-85 Feedback reset held 3 frames (resetpulse did not clear); T-124 no POP / Texture3D; T-74 the only
# pixel read is the user's Save pulse (TOP.save, never per frame). ASCII only.
GRID = 'grid'
SCAT = 'scat_'
SRC = 'src_'
JFA = 'jfa'


def C():
    return me.parent()


def GL():
    return C().op('eff_grid_logic').module


def RT():
    return C().op('eff_rt').module


def g():
    return C().op(GRID)


def vals():
    """Grid page values (effectors_grid_logic.grid_values)."""
    P = C().par
    pv = lambda n, d: getattr(P, n).eval() if getattr(P, n, None) is not None else d
    return GL().grid_values({
        'on': pv('Gridon', False), 'centre': (pv('Gridcentrex', 0.0), pv('Gridcentrey', 1.0), pv('Gridcentrez', 0.0)),
        'size': pv('Gridsize', 4.0), 'res': pv('Gridres', '32'), 'alpha': pv('Gridalpha', 0.5),
        'paint_on': pv('Painton', False), 'paint_res': pv('Paintres', '64'), 'paint_sel': pv('Paintselect', '#paint'),
        'erase_sel': pv('Eraseselect', '#erase'), 'rate': pv('Paintrate', 2.0), 'decay': pv('Paintdecay', 0.0)})


def texels():
    """Grid region texels for eff_rows (eff_rt.grid_texels)."""
    return GL().grid_texels(vals())


def geo(layer):
    v = vals()
    return GL().geometry(v['centre'], v['size'], v['res'] if layer == 'field' else v['paint_res'])


def u(layer, name, k):
    """Uniform component expressions (inside the grid COMP): uGrid (origin, cell), uGridN (N, TX, -, -), atlas size."""
    G_ = geo(layer)
    if name == 'uGrid':
        return (list(G_['origin']) + [G_['cell']])[k]
    if name == 'uGridN':
        return [float(G_['N']), float(G_['TX']), 0.0, 0.0][k]
    if name == 'atlas':
        return G_['atlas'][k]
    if name == 'dispatch':
        return G_['N'] // GL().BRICK
    if name == 'jfa':
        return float(GL().jfa_steps(G_['N'])[k])
    return 0.0


# ------------------------------------------------------------------------------------------------ small TD helpers

def _sd(o):
    return RT()._sd(o)


def _mk(parent, cls, name):
    o = parent.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = parent.create(cls, name)
    o.viewer = True
    return o


def _expr(par, e):
    if par.mode != ParMode.EXPRESSION or par.expr != e:
        par.expr = e
        par.mode = ParMode.EXPRESSION


def _wire(src, dst, i=0):
    cur = dst.inputConnectors[i].connections if i < len(dst.inputConnectors) else []
    if cur and cur[0].owner is src:
        return
    src.outputConnectors[0].connect(dst.inputConnectors[i])


def _slot(o, seq, name):
    s = getattr(o.seq, seq)
    n = int(s.numBlocks)
    for k in range(n):
        if getattr(o.par, '%s%dname' % (seq, k)).eval() == name:
            return k
    for k in range(n):
        if not getattr(o.par, '%s%dname' % (seq, k)).eval():
            return k
    s.numBlocks = n + 1
    return n


def _vecs(o, specs):
    for name, ex in specs:
        k = _slot(o, 'vec', name)
        getattr(o.par, 'vec%dname' % k).val = name
        for ax, e in zip('xyzw', ex):
            p = getattr(o.par, 'vec%dvalue%s' % (k, ax))
            if isinstance(e, (int, float)):
                p.mode = ParMode.CONSTANT
                p.val = e
            else:
                _expr(p, e)


def _buffer(o):
    k = _slot(o, 'array', 'uEffRows')
    getattr(o.par, 'array%dname' % k).val = 'uEffRows'
    getattr(o.par, 'array%dtype' % k).val = 'vec4'
    full = C().op('eff_rows_pub') or C().op('eff_rows')   # 29 Oct: the grid reads the #pub rows live (PX hot points)
    p = getattr(o.par, 'array%dchop' % k)
    if p.eval() != full:
        p.val = '../' + full.name                          # relative (drop-in: the effectors COMP may live anywhere)
        if p.eval() != full:                               # checked with the par's own eval (T-263)
            p.val = full.path
    getattr(o.par, 'array%darraytype' % k).val = 'texturebuffer'


M = "parent(2).op('eff_grid').module"


def _compute(gc, name, dat, layer, auto=True):
    """Compute GLSL TOP at the layer's atlas size, rgba32f; auto dispatch, or N/8 workgroups per axis (scatter)."""
    o = _mk(gc, glslTOP, name)
    for d in list(getattr(o, 'docked', []) or []):
        if d.valid and d.name != dat:
            _sd(d)
    o.par.mode = 'compute'
    o.par.computedat = dat
    o.par.outputresolution = 'custom'
    _expr(o.par.resolutionw, "%s.u('%s', 'atlas', 0)" % (M, layer))
    _expr(o.par.resolutionh, "%s.u('%s', 'atlas', 1)" % (M, layer))
    o.par.format = 'rgba32float'
    if auto:
        o.par.autodispatchsize = True
    else:
        o.par.autodispatchsize = False
        for ax in ('x', 'y', 'z'):
            _expr(getattr(o.par, 'dispatchsize' + ax), "%s.u('%s', 'dispatch', 0)" % (M, layer))
    _vecs(o, [('uGrid', tuple("%s.u('%s', 'uGrid', %d)" % (M, layer, k) for k in range(4))),
              ('uGridN', ("%s.u('%s', 'uGridN', 0)" % (M, layer), "%s.u('%s', 'uGridN', 1)" % (M, layer), 0.0,
                          0.0))])
    return o


# ------------------------------------------------------------------------------------------------ build + sync

def build(texts):
    """The grid COMP (idempotent). texts = {'scatter', 'seed', 'jfa', 'paint'} shader texts (paint already prefixed
    with the effectors consumer block). Returns the COMP."""
    c = C()
    gc = c.op(GRID)
    if gc is None:
        gc = c.create(baseCOMP, GRID)
    gc.nodeX, gc.nodeY = 0, -800
    for k, t in texts.items():
        d = _mk(gc, textDAT, 'cs_' + k)
        d.viewer = False
        if d.text != t:
            d.text = t
    none = _mk(gc, constantTOP, 'none')
    none.par.outputresolution = 'custom'
    none.par.resolutionw, none.par.resolutionh = 8, 8
    none.par.format = 'rgba32float'
    for n in ('colorr', 'colorg', 'colorb', 'alpha'):
        p = getattr(none.par, n, None)
        if p is not None:
            p.val = 0.0
    none.comment = 'Empty grid (first scatter input; seed input while no cloud is on).'
    seed = _compute(gc, 'seed', 'cs_seed', 'field')
    prev = seed
    for j in range(GL().JFA_PASSES):
        o = _compute(gc, '%s%d' % (JFA, j + 1), 'cs_jfa', 'field')
        _wire(prev, o, 0)
        _vecs(o, [('uJfa', ("%s.u('field', 'jfa', %d)" % (M, j), 0.0, 0.0, 0.0))])
        prev = o
    fld = _mk(gc, nullTOP, 'grid_field')
    _wire(prev, fld, 0)
    fld.comment = ('THE distance field atlas (nearest cloud point per voxel: world xyz, has). Consumers: #define '
                   'PXE_GRID <sampler> (docs/builds/effectors.md "Voxel grid").')
    # paint volume
    blank = _mk(gc, constantTOP, 'paint_blank')
    blank.par.outputresolution = 'custom'
    _expr(blank.par.resolutionw, "%s.u('paint', 'atlas', 0)" % M)
    _expr(blank.par.resolutionh, "%s.u('paint', 'atlas', 1)" % M)
    blank.par.format = 'rgba32float'
    for n in ('colorr', 'colorg', 'colorb', 'alpha'):
        p = getattr(blank.par, n, None)
        if p is not None:
            p.val = 0.0
    pf = _mk(gc, moviefileinTOP, 'paint_file')
    pf.par.file = ''
    pinit = _mk(gc, switchTOP, 'paint_init')
    _wire(blank, pinit, 0)
    _wire(pf, pinit, 1)
    pinit.par.index = 0
    fb = _mk(gc, feedbackTOP, 'paint_fb')
    _wire(pinit, fb, 0)
    ps = _compute(gc, 'paint_step', 'cs_paint', 'paint')
    _wire(fb, ps, 0)
    fb.par.top = ps.name
    _buffer(ps)
    sv = "parent(2).op('eff_rt').module.sel_vec(parent(2).par.%s.eval())[%d]"
    _vecs(ps, [('uPaint', ("parent(2).par.Paintrate.eval() * absTime.stepSeconds",
                           "parent(2).par.Paintdecay.eval() * absTime.stepSeconds", 0.0, 0.0)),
               ('uPaintSel', (sv % ('Paintselect', 0), sv % ('Paintselect', 1), 1.0, 1.0)),
               ('uPaintIds', tuple(sv % ('Paintselect', k) for k in range(2, 6))),
               ('uEraseSel', (sv % ('Eraseselect', 0), sv % ('Eraseselect', 1), 1.0, 1.0)),
               ('uEraseIds', tuple(sv % ('Eraseselect', k) for k in range(2, 6))),
               # the adapter header's own selection uniforms (unused here; unassigned = a warning, live b2)
               ('uEffSel', (0.0, 0.0, 0.0, 0.0)), ('uEffIds', (0.0, 0.0, 0.0, 0.0)),
               ('uEffMix', (0.0, 1.0, 0.0, 4.0)), ('uEffFall', (0.0, 0.5, 1.0, 0.0))])
    po = _mk(gc, nullTOP, 'paint_out')
    _wire(ps, po, 0)
    po.comment = ('THE paint volume atlas (r = paint 0..1, g = paint brush weight, b = erase weight). Consumers: '
                  '#define PXE_PAINT <sampler>, pxePaint(p).')
    for k, o in enumerate([none, seed] + [gc.op('%s%d' % (JFA, j + 1)) for j in range(GL().JFA_PASSES)] + [fld]):
        o.nodeX, o.nodeY = 200 * (k + 1), 0
    for k, o in enumerate((blank, pf, pinit, fb, ps, po)):
        o.nodeX, o.nodeY = 200 * (k + 1), -400
    gc.comment = ('Shared voxel grid (lane E): distance field of the cloud effectors (scat_* -> seed -> jfa1..8 -> '
                  'grid_field) + paint volume (paint_fb -> paint_step -> paint_out). Parked unless Gridon / Painton.')
    sync()
    park()
    return gc


def sync():
    """Scatter passes = the enabled `cloud` rows (table order): src_<name> (Select TOP of the cloud's cloud_src) ->
    scat_<name> (input 0 = the previous pass or `none`); seed reads the last one. Stale passes go (safe_destroy)."""
    gc = g()
    if gc is None:
        return []
    Lg = RT().L()
    rs = RT().rows()
    clouds = [(i, r) for i, r in enumerate(rs) if r['kind'] == Lg.CLOUD_KIND and Lg._on(r['enabled'])]
    keep, prev = set(), gc.op('none')
    for k, (i, r) in enumerate(clouds):
        nm = r['name']
        src = _mk(gc, selectTOP, SRC + nm)
        src.par.top = C().path + '/' + nm + '/cloud_src'
        sc = _compute(gc, SCAT + nm, 'cs_scatter', 'field', auto=False)
        _wire(prev, sc, 0)
        _wire(src, sc, 1)
        _buffer(sc)
        _vecs(sc, [('uGridN', ("%s.u('field', 'uGridN', 0)" % M, "%s.u('field', 'uGridN', 1)" % M,
                               1.0 if k > 0 else 0.0, "parent(2).par.Gridalpha.eval()")),
                   ('uCloud', ("parent(2).op('eff_rt').module.row_index(%r)" % nm, 0.0, 0.0, 0.0))])
        src.nodeX, src.nodeY = 200 * (k + 1), 300
        sc.nodeX, sc.nodeY = 200 * (k + 1), 150
        keep.update((SRC + nm, SCAT + nm))
        prev = sc
    seed = gc.op('seed')
    if seed is not None:
        _wire(prev, seed, 0)
    for o in list(gc.children):
        if o.name.startswith((SCAT, SRC)) and o.name not in keep:
            _sd(o)
    return sorted(keep)


def park():
    """The grid cooks only while Gridon or Painton is on (else parked: allowCooking False)."""
    gc = g()
    if gc is None:
        return False
    v = vals()
    on = bool(v['on'] or v['paint_on'])
    if gc.allowCooking != on:
        gc.allowCooking = on
    return on


def _hold_reset(fb):
    """T-85: hold the Feedback TOP's reset for 3 frames (resetpulse did not clear live)."""
    fb.par.reset = True
    run("o = op(args[0])\nif o is not None: o.par.reset = False", fb.path, delayFrames=3)


def on_pulse(name):
    """Grid page pulses: Paintclear / Paintsave / Paintload."""
    gc = g()
    if gc is None:
        return 'no grid'
    P = C().par
    path = P.Paintfile.eval().strip() or 'paint/effectors_paint.exr'
    if name == 'Paintclear':
        gc.op('paint_init').par.index = 0
        _hold_reset(gc.op('paint_fb'))
        return 'cleared'
    if name == 'Paintsave':
        import os
        full = path if os.path.isabs(path) else os.path.join(project.folder, path)
        d = os.path.dirname(full)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        gc.op('paint_out').save(full)
        return 'saved ' + full
    if name == 'Paintload':
        gc.op('paint_file').par.file = path
        gc.op('paint_init').par.index = 1
        _hold_reset(gc.op('paint_fb'))
        return 'loaded ' + path
    return 'unknown pulse ' + name
