# px_lines.py - builder of PX_lines: the lines pass for point / splat scenes (lane W1-C, 27 Oct 2026; doc
# docs/builds/px_lines.md; logic + numpy references: builders/px_lines_logic.py; tests: test/test_px_lines.py).
# Standalone over any TOP (in1 = scene, in_points = any xyz TOP, in_depth = linear eye depth) or as the PX lines layer
# (wave-2 PX owner: build it inside PX_pointfx with Outmode lines, in_points = PX update, Ptstride 5, Camera = pcam).
# Network (left to right; every multi-pass stage is a compute GLSL TOP, T-46/T-47; GLSL TOPs get <= 3 inputs, T-84):
#   rows (Script CHOP: uL[] rows, cooks on par edits; per frame only while following objects / an outside camera)
#   pal (Script CHOP: W1-B palette uPal[16]) + pal_stops (Table: custom stops)
#   in_points -> hist (compute, Feedback hist_fb; Trails only) -> hist_sw
#   Polychop (a SOP: through your SOP to CHOP) -> poly_top (CHOP to TOP) -> poly_sw
#   in_points + hist_sw + poly_sw -> seg (compute: segment texture) -> lmat (GLSL MAT) on lgeo (1 quad, instanced
#   = segments) + cam -> render (16f, additive / max) -> render_sw
#   in1 + depth_sw -> edges (compute, Edres; Edges only) -> edges_sw
#   in1 + render_sw + edges_sw -> comp (compute) -> out_sel (Amount 0 = in1) -> out1
# T-70: destroys only through safe_destroy. T-74: no TOP readback. T-64: never touches the project rate. ASCII.
import os

NAME = 'PX_lines'
HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(HERE, 'px_lines_logic.py')
PALMAP_FILE = os.path.join(HERE, 'palette_map_logic.py')
PALETTE_GLSL = os.path.join(HERE, 'glsl', 'px_palette.glsl')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
STAGES = {'seg': 'px_lines_seg', 'hist': 'px_lines_hist', 'edges': 'px_lines_edges', 'comp': 'px_lines_comp',
          'vert': 'px_lines_vert', 'pixel': 'px_lines_pixel'}
P = 'parent().par.{}.eval()'
SOURCES_ON = '(%s)' % ' or '.join(P.format(t) for t in ('Rings', 'Contour', 'Trails', 'Connect', 'Polyline'))
# per-frame rows only while something moves the rows: followed objects, or an outside camera AND a feature that reads
# the camera in a compute (the line MAT itself uses the render camera: no rows needed). Live 31550: a rows cook is
# ~1.7 ms of Python, so it must not run every frame just because Camera is set.
CAM_USERS = ("parent().par.Ringface.eval() == 'camera'", "parent().par.Ctaxis.eval() == 'view'",
             "parent().par.Cttangent.eval() == 'view'", P.format('Trvcam'),
             "'depth' in (parent().par.Ringattr.eval(), parent().par.Ctattr.eval(), parent().par.Trattr.eval(), "
             "parent().par.Cnattr.eval(), parent().par.Poattr.eval())",
             "(%s and %s and parent().par.Maskmode.eval() != 'off')" % (P.format('Edges'), P.format('Usedepth')))
FOLLOW = '(%s or (%s and (%s)))' % (' or '.join(P.format(t) for t in ('Ringops', 'Polyop', 'Maskop')),
                                     P.format('Camera'), ' or '.join(CAM_USERS))
UT = ['absTime.seconds * ' + P.format('Speed'), 'absTime.frame', 'absTime.stepSeconds * ' + P.format('Speed'),
      P.format('Resetn')]
PAL_CTL_EXPR = ["parent().par.Palshift.eval()", "parent().par.Palmode.menuIndex", "parent().par.Palinterp.menuIndex"]

# rows: every par -> px_lines_logic.rows -> one sample per uL row, channels x y z w. Runs only when a par it reads
# changes (T-115) or, while following objects / an outside camera, once per frame through the Frame par.
ROWS_CB = '''# rows: uL[] uniform rows of PX_lines (px_lines_logic.rows). Built by builders/px_lines.py.
def onSetupParameters(scriptOp):
\tpg = next((p for p in scriptOp.customPages if p.name == 'Clock'), None) or scriptOp.appendCustomPage('Clock')
\tif getattr(scriptOp.par, 'Frame', None) is None:
\t\tpg.appendFloat('Frame', label='Frame (follow clock)')

def _vals(c, Lg):
\tout = {}
\tfor n, (st, d, o) in Lg.par_specs().items():
\t\tif st == 'Pulse':
\t\t\tcontinue
\t\tif st in ('XYZ', 'RGB'):
\t\t\tsx = 'xyz' if st == 'XYZ' else 'rgb'
\t\t\tout[n] = tuple(float(getattr(c.par, n + k).eval()) for k in sx)
\t\telif st == 'Toggle':
\t\t\tout[n] = bool(getattr(c.par, n).eval())
\t\telse:
\t\t\tout[n] = getattr(c.par, n).eval()
\treturn out

def _world(o):
\tm = o.worldTransform
\treturn [[m[r, 0], m[r, 1], m[r, 2], m[r, 3]] for r in range(4)]

def _find(c, path):
\tif not path:
\t\treturn None
\tif not isinstance(path, str):
\t\treturn path
\treturn c.op(path) or op(path)

ID4 = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]

def ctx_of(c, Lg, v, static=False):
\t# static (wave 4): no world transform is read (reading one makes this CHOP cook every frame); rows_follow patches
\t# the rows that use them in the `rows` CHOP
\tW = (lambda o: ID4) if static else _world
\tctx = {}
\tcam = v['Camera'] or c.op('cam')
\ttry:
\t\tfov = float(cam.par.fov.eval())
\t\thor = str(getattr(cam.par, 'viewanglemethod', None) and cam.par.viewanglemethod.eval()) != 'vertical'
\t\tproj = Lg.perspective(fov, v['Resx'], v['Resy'], float(cam.par.near.eval()), float(cam.par.far.eval()), hor)
\t\tctx['cam'] = Lg.camera(W(cam), proj)
\texcept Exception:
\t\tctx['cam'] = Lg.default_camera(v['Resx'], v['Resy'])
\tcents = []
\tfor p in str(v['Ringops'] or '').split()[:Lg.MAX_CENTRES]:
\t\to = _find(c, p)
\t\tif o is not None and hasattr(type(o), 'worldTransform'):
\t\t\tcents.append(Lg.frame_from_world(W(o)))
\tctx['centres'] = cents
\tch = v['Polychop']
\tctx['poly_n'] = int(ch.numSamples) if ch is not None else 0
\tif v['Polyop'] is not None and not static:
\t\tctx['poly_world'] = _world(v['Polyop'])[:3]
\tif v['Maskop'] is not None and not static:
\t\tctx['mask_world'] = _world(v['Maskop'])[:3]
\treturn ctx

def onCook(scriptOp):
\tc = scriptOp.parent()
\tLg = c.op('pl_logic').module
\tv = _vals(c, Lg)
\tctx = ctx_of(c, Lg, v, static=bool(getattr(Lg, 'follows', None) and Lg.follows(v)))
\trows = Lg.rows(v, ctx)
\tpl = Lg.plan(v, ctx)
\tst = 'segments %d of %d%s' % (pl['total'], pl['maxseg'], ('; clamped: ' + ' '.join(pl['clamped'])) if pl['clamped'] else '')
\tif c.par.Status.eval() != st:
\t\tc.par.Status = st
\tscriptOp.store('v', dict((k, (x.path if hasattr(x, 'path') else x)) for k, x in v.items()))   # for rows (follow)
\tscriptOp.clear()
\tscriptOp.isTimeSlice = False
\tscriptOp.numSamples = len(rows)
\tfor k, n in enumerate('xyzw'):
\t\tch = scriptOp.appendChan(n)
\t\tfor i, r in enumerate(rows):
\t\t\tch[i] = r[k]
'''

# rows (wave 4, PX owner): rows_static (the par-driven rows above, event cooks) copied + ONLY the object / camera rows
# patched per frame while following (px_lines_logic.rows_follow): was the whole rows() + 148 par reads per frame.
ROWS_FOLLOW_CB = '''# rows: rows_static + the rows that follow objects / the camera (px_lines_logic.rows_follow). Built by px_lines.py.
def onSetupParameters(scriptOp):
\tpg = next((p for p in scriptOp.customPages if p.name == 'Clock'), None) or scriptOp.appendCustomPage('Clock')
\tif getattr(scriptOp.par, 'Frame', None) is None:
\t\tpg.appendFloat('Frame', label='Frame (follow clock)')

def onCook(scriptOp):
\tc = scriptOp.parent()
\tsrc = scriptOp.inputs[0] if scriptOp.inputs else None
\tscriptOp.clear()
\tif src is None:
\t\treturn
\tscriptOp.copy(src)
\tif not scriptOp.par.Frame.eval():
\t\treturn
\tv = src.fetch('v', None, search=False)
\tif not v:
\t\treturn
\tLg = c.op('pl_logic').module
\tcb = c.op('rows_static_callbacks').module
\tvv = dict(v)
\tfor k in ('Camera', 'Maskop', 'Polyop', 'Polychop'):
\t\tvv[k] = (c.op(v[k]) or op(v[k])) if v.get(k) else None
\tf = Lg.rows_follow(vv, cb.ctx_of(c, Lg, vv))
\tfor name, row in f.items():
\t\ti = Lg.R[name]
\t\tfor k, n in enumerate('xyzw'):
\t\t\tscriptOp[n][i] = row[k]
'''

# pal: W1-B palette (palette_map_logic in pl_palmap) -> 16 samples r g b pos; binds uPal + uPalCtl on seg / edges
PAL_CB = '''# pal: W1-B shared palette of PX_lines (palette_map_logic.palette_stops -> pal_rows), uPal[16] + uPalCtl.
def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tc = scriptOp.parent()
\tPm = c.op('pl_palmap').module
\tsrc = c.par.Palsource.eval()
\tspec = {'source': src, 'mode': c.par.Palmode.eval(), 'reverse': bool(c.par.Palreverse.eval())}
\trows, fhex = None, None
\tif src == 'custom':
\t\tt = c.op('pal_stops')
\t\trows = [[cell.val for cell in t.row(i)] for i in range(t.numRows)] if t is not None else []
\telif src == 'file':
\t\tpath = c.par.Palfile.eval()
\t\ttry:
\t\t\tdata = open(path, 'rb').read() if path else b''
\t\t\tfhex = Pm.parse_file(path, data) if data else []
\t\texcept Exception:
\t\t\tfhex = []
\t\tif isinstance(fhex, tuple):
\t\t\tfhex = fhex[0]
\tstops = Pm.palette_stops(spec, rows, fhex)
\tPm.cook_chop(scriptOp, Pm.pal_rows(stops))
\tctl = [float(min(len(stops), Pm.PAL_MAX))] + %r
\tfor n in ('seg', 'edges'):
\t\to = c.op(n)
\t\tif o is not None and int(o.par.vec0valuex.eval() if False else 0) == 0:
\t\t\tPm.bind_glsl(o, 'pal', ctl, ParMode)
''' % (PAL_CTL_EXPR,)

PEXEC = '''# pl_pulse: Reset -> Resetn + 1 (the trail history restarts on the next cook)
def onPulse(par):
\tif par.name == 'Reset':
\t\tc = par.owner
\t\tc.par.Resetn = int(c.par.Resetn.eval()) + 1
'''


def _read(p):
    with open(p) as fh:
        return fh.read()


def _logic():
    ns = {}
    exec(compile(_read(LOGIC_FILE), LOGIC_FILE, 'exec'), ns)
    return ns


def _sd(o):
    """T-70: destroy through safe_destroy (td_exec namespace, else the MCP handlers module)."""
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _mk(c, cls, name):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = True
    return o


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


def _set(o, name, val, missing=None):
    p = getattr(o.par, name, None)
    if p is None:
        if missing is not None:
            missing.append('%s.%s' % (o.name, name))
        return False
    try:
        p.val = val
    except Exception:
        if missing is not None:
            missing.append('%s.%s=%s' % (o.name, name, val))
        return False
    return True


def _close_window(c):
    w = c.op('controls_window')
    if w is not None and w.OPType == 'windowCOMP' and w.isOpen:
        w.par.winclose.pulse()


def _pars(c, Lg):
    """Custom pages / pars once; existing values kept."""
    for page_name, pars in Lg['PAGES'] + [('Info', [('Status', 'Str', '', {'label': 'Status'})])]:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            probe = name + ('x' if style == 'XYZ' else ('r' if style == 'RGB' else ''))
            if getattr(c.par, probe, None) is not None:
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
                p.default = default
                p.val = default
            elif style in ('Float', 'Int'):
                p = (page.appendFloat if style == 'Float' else page.appendInt)(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
                p.default = default
                p.val = default
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style in ('XYZ', 'RGB'):
                for p, v in zip((page.appendXYZ if style == 'XYZ' else page.appendRGB)(name, label=label), default):
                    p.default = v
                    p.val = v
            elif style in ('Str', 'File'):
                p = (page.appendStr if style == 'Str' else page.appendFile)(name, label=label)[0]
                p.default = default
                p.val = default
            elif style in ('COMP', 'CHOP', 'SOP', 'TOP'):
                getattr(page, 'append' + style)(name, label=label)
    c.par.Resetn.readOnly = True
    c.par.Status.readOnly = True


def _uniforms(o, missing):
    """uL[] from rows (Arrays block 0) + uT (Vectors block 0)."""
    o.seq.array.numBlocks = max(int(o.seq.array.numBlocks), 1)
    o.par.array0name = 'uL'
    o.par.array0type = 'vec4'
    o.par.array0chop = 'rows'
    o.par.array0arraytype = 'uniformarray'
    o.seq.vec.numBlocks = max(int(o.seq.vec.numBlocks), 1)
    o.par.vec0name = 'uT'
    for comp, e in zip('xyzw', UT):
        _expr(getattr(o.par, 'vec0value' + comp), e)


def _cs(o, name, prefix):
    """W1-B colour source vec4 (mode index, pos, spread, keep) as Vectors block 1."""
    o.seq.vec.numBlocks = max(int(o.seq.vec.numBlocks), 2)
    o.par.vec1name = name
    for comp, e in zip('xyzw', ['parent().par.%scolsrc.menuIndex' % prefix, P.format(prefix + 'palpos'),
                                P.format(prefix + 'palspread'), P.format(prefix + 'keep')]):
        _expr(getattr(o.par, 'vec1value' + comp), e)


def _bind_palette(c, o):
    """uPal (Arrays, from pal) + uPalCtl (Vectors) on o; count from the current pars (the pal CHOP keeps it
    current after palette edits: PAL_CB re-binds)."""
    ns = {}
    exec(compile(_read(PALMAP_FILE), PALMAP_FILE, 'exec'), ns)
    src = c.par.Palsource.eval()
    spec = {'source': src, 'mode': c.par.Palmode.eval(), 'reverse': bool(c.par.Palreverse.eval())}
    rows = None
    if src == 'custom':
        t = c.op('pal_stops')
        rows = [[cell.val for cell in t.row(i)] for i in range(t.numRows)]
    n = len(ns['palette_stops'](spec, rows, []))
    ns['bind_glsl'](o, 'pal', [float(min(n, ns['PAL_MAX']))] + PAL_CTL_EXPR, ParMode)


def _compute(c, name, text, ins, w_expr, h_expr, fmt, filt, comment):
    g = _mk(c, glslTOP, name)
    g.par.mode = 'compute'
    d = _mk(c, textDAT, name + '_compute')
    d.text = text
    d.dock = g
    g.par.computedat = d.name
    for dn in ('_info', '_pixel'):
        x = c.op(name + dn)
        if x is not None and x.dock == g:
            _sd(x)
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, w_expr)
    _expr(g.par.resolutionh, h_expr)
    g.par.format = fmt
    g.par.autodispatchsize = True
    g.par.inputfiltertype = filt
    for k, s in enumerate(ins):                  # <= 3 wired inputs (T-84 / T-88)
        g.inputConnectors[k].connect(s)
    g.comment = comment
    return g


def _switch(c, name, a, b, index_expr, comment):
    s = _mk(c, switchTOP, name)
    s.inputConnectors[0].connect(a)
    s.inputConnectors[1].connect(b)
    _expr(s.par.index, index_expr)
    s.comment = comment
    return s


GRID_ON = "1 if (%s and parent().par.Cnindex.eval() == 'grid') else 0" % P.format('Connect')
_NEXPR = 'min(128, max(8, (int(%s) + 7) // 8 * 8))' % P.format('Cngrid')


def _cn_index(c, Lg, inp, black, missing):
    """Wave 4 (SA33 whole cloud): cn_src (Cnindextop or in_points) -> cn_index (compute, one workgroup per 8^3
    brick, uniforms from par expressions only: a static index TOP is indexed once) -> cn_idx_sw / cn_rest_sw
    (black unless Connect + Cnindex grid) = seg inputs 3 / 4 through seg's `tops` par."""
    src = _mk(c, selectTOP, 'cn_src')
    _expr(src.par.top, "parent().par.Cnindextop.eval() or parent().op('in_points')")
    src.comment = 'Index points: Cnindextop (e.g. PX rest = static: indexed once) or in_points.'
    body = _read(os.path.join(HERE, 'glsl', 'px_lines_index.glsl'))
    g = _mk(c, glslTOP, 'cn_index')
    g.par.mode = 'compute'
    d = _mk(c, textDAT, 'cn_index_compute')
    d.text = Lg['glsl_header']() + body
    d.dock = g
    g.par.computedat = d.name
    for dn in ('_info', '_pixel'):
        x = c.op('cn_index' + dn)
        if x is not None and x.dock == g:
            _sd(x)
    tx = 'int(math.ceil(math.sqrt(%s)))' % _NEXPR
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, '%s * %s' % (_NEXPR, tx))
    _expr(g.par.resolutionh, '%s * ((%s + %s - 1) // %s)' % (_NEXPR, _NEXPR, tx, tx))
    g.par.format = 'rgba32float'
    g.par.inputfiltertype = 'nearest'
    g.par.autodispatchsize = False
    for ax in ('x', 'y', 'z'):
        _expr(getattr(g.par, 'dispatchsize' + ax), '%s // 8' % _NEXPR)
    g.inputConnectors[0].connect(src)
    g.seq.vec.numBlocks = max(int(g.seq.vec.numBlocks), 3)
    size = P.format('Cngridsize')
    vecs = [('uCnG', ['%s - 0.5 * %s' % (P.format('Cngridcentre' + k), size) for k in 'xyz'] + ['%s / %s' % (size, _NEXPR)]),
            ('uCnN', [_NEXPR, tx, 'int(%s) or int(%s)' % (P.format('Cnistride'), P.format('Ptstride')),
                      'int(%s)' % P.format('Ptcount')]),
            ('uCnP', ["parent().par.Cnpick.menuIndex", '0', '0', '0'])]
    for k, (nm, ex) in enumerate(vecs):
        getattr(g.par, 'vec%dname' % k).val = nm
        for comp, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec%dvalue%s' % (k, comp)), e)
    g.comment = 'Connect grid index: one representative point per voxel (id + 1 in w), N^3 atlas.'
    isw = _switch(c, 'cn_idx_sw', black, g, GRID_ON, 'Index only while Connect uses the voxel index.')
    rsw = _switch(c, 'cn_rest_sw', black, src, GRID_ON, 'Index points (rest) for the grid search.')
    return src, isw, rsw


def build(parent_path='/project1/lab', name=NAME):
    missing = []
    Lg = _logic()
    par_ = op(parent_path)
    c = par_.op(name) or par_.create(baseCOMP, name)
    c.allowCooking = True                        # house rule: builders re-enable their own COMP each step
    c.comment = ('PX_lines: thin bright lines over point / splat scenes (rings, contour, trails / vortex, connect / '
                 'lightning, polyline / logo, edges). Width in px, halo, HDR, reveal / dash / flicker, world mask, '
                 'depth occlusion, W1-B palette. Doc: docs/builds/px_lines.md.')
    _close_window(c)
    _pars(c, Lg)
    common = _read(os.path.join(HERE, 'glsl', 'px_lines_common.glsl'))
    pal = _read(PALETTE_GLSL)
    txt = lambda st: Lg['stage_text'](st, common, pal, _read(os.path.join(HERE, 'glsl', STAGES[st] + '.glsl')))

    lg = _mk(c, textDAT, 'pl_logic')
    lg.text = _read(LOGIC_FILE)
    lg.comment = 'Pure logic = builders/px_lines_logic.py (rows, plan, palette spec, references).'
    pm = _mk(c, textDAT, 'pl_palmap')
    pm.text = _read(PALMAP_FILE)
    pm.comment = 'W1-B shared palette = builders/palette_map_logic.py (read-only copy).'
    stops = _mk(c, tableDAT, 'pal_stops')
    if stops.numRows == 0:
        for h, pos in (('39FF14', 0.0), ('00F0FF', 0.5), ('FF00E6', 1.0)):
            stops.appendRow([h, pos])
    stops.comment = 'Custom palette stops (Palsource custom): hex [pos] per row.'
    pe = _mk(c, parameterexecuteDAT, 'pl_pulse')
    pe.text = PEXEC
    pe.par.op = c
    pe.par.pars = 'Reset'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = False
    pe.par.onpulse = True

    rst = _mk(c, scriptCHOP, 'rows_static')
    scb = _mk(c, textDAT, 'rows_static_callbacks')
    scb.text = ROWS_CB
    scb.dock = rst
    rst.par.callbacks = scb.name
    rst.par.setuppars.pulse()
    rst.comment = 'uL[] rows (px_lines_logic.rows): cooks only when a par it reads changes.'
    rows = _mk(c, scriptCHOP, 'rows')
    rcb = _mk(c, textDAT, 'rows_callbacks')
    rcb.text = ROWS_FOLLOW_CB
    rcb.dock = rows
    rows.par.callbacks = rcb.name
    rows.inputConnectors[0].connect(rst)
    rows.par.setuppars.pulse()
    if getattr(rows.par, 'Frame', None) is not None:
        _expr(rows.par.Frame, 'absTime.frame if %s else 0' % FOLLOW)
    rows.comment = 'rows_static + object / camera rows per frame while following (px_lines_logic.rows_follow).'
    palc = _mk(c, scriptCHOP, 'pal')
    pcb = _mk(c, textDAT, 'pal_callbacks')
    pcb.text = PAL_CB
    pcb.dock = palc
    palc.par.callbacks = pcb.name
    palc.comment = 'W1-B palette uPal[16] (r g b pos); binds uPal + uPalCtl on seg and edges.'

    in1 = _mk(c, inTOP, 'in1')
    inp = _mk(c, inTOP, 'in_points')
    ind = _mk(c, inTOP, 'in_depth')
    for k, o in enumerate((in1, inp, ind)):     # COMP input k (live 31550: default order follows node position)
        _set(o, 'connectorder', k, missing)
    black = _mk(c, constantTOP, 'black')
    black.par.outputresolution = 'custom'
    black.par.resolutionw, black.par.resolutionh = 8, 8
    _set(black, 'format', 'rgba32float', missing)
    black.par.colorr = black.par.colorg = black.par.colorb = 0
    black.par.alpha = 0
    black.comment = 'Stand-in input for parts that are off (they do not cook).'

    hist_fb = _mk(c, feedbackTOP, 'hist_fb')
    hist = _compute(c, 'hist', txt('hist'), [inp, hist_fb],
                    'max(2, int(%s)) + 2' % P.format('Trsamples'), 'max(1, int(%s))' % P.format('Trtracks'),
                    'rgba32float', 'nearest', 'Trail history: col 0 head, col 1 life, cols 2.. ring of samples.')
    hist_fb.inputConnectors[0].connect(black)      # reset source; the loop goes through par.top (no wire loop)
    hist_fb.par.top = 'hist'
    _uniforms(hist, missing)
    hist_sw = _switch(c, 'hist_sw', black, hist, '1 if %s else 0' % P.format('Trails'), 'History only while Trails.')

    ptop = _mk(c, choptoTOP, 'poly_top')
    _expr(ptop.par.chop, "%s or ''" % P.format('Polychop'))
    _set(ptop, 'format', 'rgba32float', missing)
    if getattr(ptop.par, 'dataformat', None) is not None:   # live 31550: rgba with 3 channels = all zeros
        _expr(ptop.par.dataformat, "'rgba' if (%s and %s.numChans >= 4) else 'rgb'" % (P.format('Polychop'),
                                                                                    P.format('Polychop')))
    else:
        missing.append('poly_top.dataformat')
    ptop.comment = 'Path: one row, texel i = tx ty tz (w < 0 = pen up). LIVE CHECK the channel -> rgba mapping.'
    poly_sw = _switch(c, 'poly_sw', black, ptop, '1 if (%s and %s) else 0' % (
        P.format('Polyline'), P.format('Polychop')), 'Path only while Polyline has a CHOP.')

    cn_src, cn_idx_sw, cn_rest_sw = _cn_index(c, Lg, inp, black, missing)
    seg = _compute(c, 'seg', txt('seg'), [inp, hist_sw, poly_sw], str(4 * Lg['SEG_W']),
                   'max(1, (int(%s) + %d) // %d)' % (P.format('Maxseg'), Lg['SEG_W'] - 1, Lg['SEG_W']),
                   'rgba32float', 'nearest', 'Segments: 4 texels each (A u, B u, colour alpha, width caps id src).')
    _uniforms(seg, missing)
    if not _set(seg, 'tops', 'cn_idx_sw cn_rest_sw', missing):   # inputs 3, 4 by name (T-88: 3 wired max)
        missing.append('seg.tops (connect grid index needs it)')
    _cs(seg, 'uLineCs', 'Line')
    _bind_palette(c, seg)

    depth_sw = _switch(c, 'depth_sw', black, ind, '1 if %s else 0' % P.format('Usedepth'),
                       'Scene depth (linear eye depth in R) only when Usedepth.')
    mat = _mk(c, glslMAT, 'lmat')
    vd = _mk(c, textDAT, 'lmat_vertex')
    vd.text = txt('vert')
    vd.dock = mat
    pd = _mk(c, textDAT, 'lmat_pixel')
    pd.text = txt('pixel')
    pd.dock = mat
    for dn in ('lmat_info', 'lmat_compute'):
        x = c.op(dn)
        if x is not None and x.dock == mat:
            _sd(x)
    mat.par.vdat = vd.name
    mat.par.pdat = pd.name
    _uniforms(mat, missing)
    mat.seq.sampler.numBlocks = max(int(mat.seq.sampler.numBlocks), 3)
    for k, (sn, top) in enumerate((('sSeg', 'seg'), ('sDepth', 'depth_sw'), ('sScene', 'in1'))):
        getattr(mat.par, 'sampler%dname' % k).val = sn
        getattr(mat.par, 'sampler%dtop' % k).val = top
        _set(mat, 'sampler%dfilter' % k, 'nearest' if k == 0 else 'linear', missing)
    mat.par.blending = True
    for pn in ('srcblend', 'destblend', 'srcblenda', 'destblenda'):
        _set(mat, pn, 'one', missing)
    if getattr(mat.par, 'blendop', None) is not None:
        _expr(mat.par.blendop, "'maximum' if parent().par.Blend.eval() == 'max' else 'add'")
    else:
        missing.append('lmat.blendop (Blend max falls back to add)')
    mat.par.depthtest = False
    mat.par.depthwriting = False
    _set(mat, 'postmultalpha', False, missing)
    mat.comment = 'One instance = one segment; quad built in screen px; premultiplied HDR, add or max.'

    geo = _mk(c, geometryCOMP, 'lgeo')
    for ch in list(geo.children):
        if ch.name != 'quad':
            _sd(ch)
    q = geo.op('quad') or geo.create(rectangleSOP, 'quad')
    q.par.orient = 'xy'
    q.par.sizex, q.par.sizey = 1, 1
    _set(q, 'normals', False, missing)
    q.render = True
    q.display = True
    geo.par.instancing = True
    geo.par.instancecountmode = 'manual'
    _expr(geo.par.numinstances, "max(1, int(parent().op('rows')['z'][0]))")
    geo.par.material = 'lmat'                    # sibling name (T-81)
    geo.comment = '1x1 quad, instanced = segments (rows G0.z).'
    cam = _mk(c, cameraCOMP, 'cam')
    cam.par.tz = 5
    cam.par.fov = 45
    cam.comment = 'Own camera when Camera is empty (0, 0, 5) looking down -z, fov 45.'
    ren = _mk(c, renderTOP, 'render')
    _expr(ren.par.camera, "%s or op('cam')" % P.format('Camera'))
    ren.par.geometry = 'lgeo'
    ren.par.lights = ''
    ren.par.outputresolution = 'custom'
    _expr(ren.par.resolutionw, P.format('Resx'))
    _expr(ren.par.resolutionh, P.format('Resy'))
    ren.par.format = 'rgba16float'
    names = list(ren.par.antialias.menuNames)
    ren.par.antialias = 'aa1x' if 'aa1x' in names else names[0]
    ren.par.bgcolorr = ren.par.bgcolorg = ren.par.bgcolorb = 0
    _set(ren, 'bgcolora', 0, missing)
    _set(ren, 'cullface', 'neither', missing)
    ren.comment = 'Lines, 16f, Resx x Resy (the AA is in the pixel shader).'
    render_sw = _switch(c, 'render_sw', black, ren, "1 if (%s and int(op('rows')['z'][0]) > 0) else 0" % SOURCES_ON,
                        'Line render only while a source draws.')

    edges = _compute(c, 'edges', txt('edges'), [in1, depth_sw],
                     "max(1, %s // {'full': 1, 'half': 2}.get(parent().par.Edres.eval(), 4))" % P.format('Resx'),
                     "max(1, %s // {'full': 1, 'half': 2}.get(parent().par.Edres.eval(), 4))" % P.format('Resy'),
                     'rgba16float', 'linear', 'Edge / outline lines (Sobel of luma, alpha, depth), Edres.')
    _uniforms(edges, missing)
    _cs(edges, 'uEdgeCs', 'Edge')
    _bind_palette(c, edges)
    edges_sw = _switch(c, 'edges_sw', black, edges, '1 if %s else 0' % P.format('Edges'), 'Edges only while on.')

    comp = _compute(c, 'comp', txt('comp'), [in1, render_sw, edges_sw], P.format('Resx'), P.format('Resy'),
                    'rgba16float', 'linear', 'Composite (Outmode composite / lines only), Amount, Bgdim.')
    _uniforms(comp, missing)
    sel = _switch(c, 'out_sel', in1, comp, '1 if %s > 0 else 0' % P.format('Amount'), 'Amount 0 = in1 exactly.')
    out1 = _mk(c, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    stages = [
        {'title': '0 Code + rows', 'role': 'control',
         'ops': ['pl_logic', 'pl_palmap', 'pl_pulse', 'pal_stops', 'rows_static', 'rows_static_callbacks', 'rows',
                 'rows_callbacks', 'pal', 'pal_callbacks'],
         'body': 'rows = uL[] (px_lines_logic.rows), pal = W1-B palette uPal[16]; pl_pulse: Reset trails.'},
        {'title': '1 Inputs', 'role': 'input', 'ops': ['in1', 'in_points', 'in_depth', 'black', 'depth_sw'],
         'body': 'in1 scene, in_points any xyz TOP (PX state: Ptstride 5), in_depth linear eye depth (Usedepth).'},
        {'title': '2 Trails + path', 'role': 'process',
         'ops': ['hist_fb', 'hist', 'hist_compute', 'hist_sw', 'poly_top', 'poly_sw'],
         'body': 'Trail history (points or own flow particles); polyline path from a CHOP (a SOP: SOP to CHOP first).'},
        {'title': '3 Segments + render', 'role': 'process',
         'ops': ['cn_src', 'cn_index', 'cn_index_compute', 'cn_idx_sw', 'cn_rest_sw',
                 'seg', 'seg_compute', 'lmat', 'lmat_vertex', 'lmat_pixel', 'lgeo', 'cam', 'render', 'render_sw'],
         'body': 'seg: rings / contour / trails / connect / polyline -> segment texture; lmat draws each as a px-wide '
                 'quad with core + halo, reveal / dash / occlusion.'},
        {'title': '4 Edges + out', 'role': 'output',
         'ops': ['edges', 'edges_compute', 'edges_sw', 'comp', 'comp_compute', 'out_sel', 'out1'],
         'body': 'Edge lines (Sobel, Edres), composite over in1 or lines only, Amount 0 = in1.'},
    ]
    lay = None
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:                       # layout is cosmetic; the network works without it
        lay = 'layout skipped: %s' % e
    return {'comp': c.path, 'missing': missing, 'layout': str(lay)[:200]}


def panel(parent_path='/project1/lab', name=NAME, open_window=False):
    """zkit panel: separate exec, >= 5 frames after build()."""
    c = op(parent_path).op(name)
    ns = dict(globals())
    exec(_read(ZKIT_FILE), ns)
    return str(ns['build_controls'](c.path, pages=_logic()['PANEL_PAGES'], d=56, cols=8,
                                    open_window=open_window))[:300]


def park(parent_path='/project1/lab', name=NAME):
    """Park only this COMP (house rule, after saving)."""
    c = op(parent_path).op(name)
    if c is not None:
        _close_window(c)
        c.allowCooking = False
    return {'comp': name, 'allowCooking': False if c is not None else None}
