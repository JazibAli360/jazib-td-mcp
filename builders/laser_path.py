# laser_path builder - LP_laser_path: any source -> laser sample stream + beam preview + stats
# (spec docs/research/BM_lasers.md section 4, clean-room). Run inside TD (TD 2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/laser_path.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts/pars/wires re-set, custom par values kept, zkit panel refreshed in place.
# ASCII only. No Python functions in op storage (T-67). T-70 safe: nothing destroyed directly (_sd = safe_destroy),
# controls_window closed before a rebuild, panel container kept, network pane never moved here.
# T-74: the builder never reads TOP pixels; no force-cook of TOPs.
import os

NAME = 'LP_laser_path'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(HERE, 'laser_path_logic.py')
RT_FILE = os.path.join(HERE, 'laser_path_rt.py')
CLIP = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4'

P = "parent().par.{}"

SCRIPT_CB = """# {name}: {what} (lp_rt.{fn}).
# Frame (clock) par: an expression that changes only while this op must cook every frame (0 = cook on change).
def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = {clock!r}
        p.mode = ParMode.EXPRESSION
    return

def onCook(scriptOp):
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    op('lp_rt').module.{fn}(scriptOp)
    return
"""

STATS_CB = """# stats: points_total, points_draw, points_blank, frames_per_image, shapes, corners, blank_travel, est_flicker_hz,
# overflow ... (lp_rt.cook_stats; Own engine = its own numbers, Native = counted from the laser stream).
def onCook(scriptOp):
    _dep = op('laser').numSamples
    op('lp_rt').module.cook_stats(scriptOp)
    return
"""

PEXEC = """# Opencontrols -> controls window (zkit also listens); Savesnap -> output/laser/<COMP>.json.
def onPulse(par):
    if par.name == 'Opencontrols':
        w = parent().op('controls_window')
        if w is not None and not w.isOpen:
            w.par.winopen.pulse()
    elif par.name == 'Savesnap':
        f = op('lp_rt').module.savesnap()
        print('LP_laser_path snapshot:', f)
    elif par.name == 'Exportilda':
        r = op('lp_rt').module.export_ilda()
        print('LP_laser_path ILDA:', r.get('file'), 'ok' if r.get('ok') else 'CHECK FAILED')
    return
"""

SPRITE_FILE = os.path.join(HERE, 'glsl', 'laser_path_sprite.glsl')   # single pass, no inputs (T-46 n/a)
PERSIST_FILE = os.path.join(HERE, 'glsl', 'laser_path_persist.glsl')   # one pixel pass
LOOK_FILE = os.path.join(HERE, 'glsl', 'laser_path_look.glsl')         # compute (T-47)

# Clock expressions for the Frame par of each Script CHOP (0 = cook only when an input/par it reads changes).
CLOCK = {
    'rows': ("absTime.frame if (parent().par.Source.eval() in ('audio', 'toptrace') or (parent().par.Source.eval() "
             "== 'pattern' and parent().par.Pattern.eval() == 'calib')) else 0"),
    'drive': "absTime.frame if op('lp_rt').module.drive_animated() else 0",
    'preview_pts': "absTime.frame if op('lp_rt').module.preview_animated() else 0",
}

PAGES = [
    ('Source', [
        ('Source', 'Menu', 'pattern', {'names': ['pattern', 'sop', 'chop', 'pop', 'toptrace', 'text', 'audio'],
                                       'labels': ['Test pattern', 'SOP', 'CHOP', 'POP', 'TOP trace', 'Text',
                                                  'Audio scope']}),
        ('Pattern', 'Menu', 'square', {'names': ['circle', 'square', 'triangle', 'star', 'grid', 'dashed', 'spiral',
                                                 'calib'],
                                       'labels': ['Circle', 'Square', 'Triangle', 'Star', '3x3 dots', 'Dashed',
                                                  'Spiral', 'Delay calibration']}),
        ('Count', 'Int', 5, {'min': 1, 'max': 300, 'label': 'Count'}),
        ('Size', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Size'}),
        ('Sop', 'SOP', '', {'label': 'SOP (empty = in1)'}),
        ('Chop', 'CHOP', '', {'label': 'CHOP (empty = in2)'}),
        ('Pop', 'POP', '', {'label': 'POP (empty = in4)'}),
        ('Fitsource', 'Toggle', True, {'label': 'Fit SOP/POP to -1..1'}),
        ('Text', 'Str', 'LASER', {'label': 'Text'}),
        ('Font', 'Str', 'Helvetica', {'label': 'Font'}),
        ('Tracesrc', 'Menu', 'clip', {'names': ['in3', 'clip'], 'labels': ['In3 TOP', 'Stored clip']}),
        ('Tracelevel', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Trace threshold'}),
        ('Traceblur', 'Float', 4.0, {'min': 0, 'max': 32, 'label': 'Trace blur px'}),
        ('Tracesteps', 'Int', 3, {'min': 1, 'max': 12, 'label': 'Trace res /'}),
        ('Audiochop', 'CHOP', '', {'label': 'Audio CHOP (L/R)'}),
    ]),
    ('Path', [
        ('Engine', 'Menu', 'native', {'names': ['native', 'own'], 'labels': ['Native (Laser CHOP)', 'Own (numpy)']}),
        ('Pps', 'Float', 30000.0, {'min': 1000, 'max': 100000, 'label': 'Points/s'}),
        ('Fps', 'Float', 60.0, {'min': 1, 'max': 240, 'label': 'Frame rate'}),
        ('Stepsize', 'Float', 0.02, {'min': 0.001, 'max': 0.2, 'label': 'Step'}),
        ('Bstepsize', 'Float', 0.1, {'min': 0.001, 'max': 1, 'label': 'Blank step'}),
        ('Minhold', 'Float', 0.1, {'min': 0, 'max': 2, 'label': 'Min corner hold ms'}),
        ('Maxhold', 'Float', 0.3, {'min': 0, 'max': 2, 'label': 'Max corner hold ms'}),
        ('Holdadd', 'Int', 0, {'min': 0, 'max': 20, 'label': 'Hold add'}),
        ('Cornertol', 'Float', 25.0, {'min': 0, 'max': 90, 'label': 'Corner above deg'}),
        ('Closedoverlap', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Closed overlap ms'}),
        ('Order', 'Menu', 'twoopt', {'names': ['none', 'nearest', 'twoopt'], 'labels': ['None', 'Nearest', 'TwoOpt']}),
        ('Orderms', 'Float', 3.0, {'min': 0, 'max': 20, 'label': 'Order budget'}),
        ('Startpoint', 'Menu', 'centre', {'names': ['centre', 'first'], 'labels': ['Nearest to centre', 'First']}),
        ('Preblankon', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Pre-blank on ms'}),
        ('Postblankon', 'Float', 0.1, {'min': 0, 'max': 2, 'label': 'Post-blank on ms'}),
        ('Preblankoff', 'Float', 0.1, {'min': 0, 'max': 2, 'label': 'Pre-blank off ms'}),
        ('Postblankoff', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Post-blank off ms'}),
        ('Colordelay', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Colour delay ms'}),
        ('Interpcolors', 'Toggle', True, {'label': 'Interp colours'}),
        ('Overflow', 'Menu', 'frames', {'names': ['frames', 'thin', 'drop'],
                                        'labels': ['Draw over frames', 'Thin the steps', 'Drop farthest']}),
    ]),
    ('Shape', [
        ('Scalex', 'Float', 1.0, {'min': -2, 'max': 2, 'label': 'Scale X'}),
        ('Scaley', 'Float', 1.0, {'min': -2, 'max': 2, 'label': 'Scale Y'}),
        ('Rotate', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate'}),
        ('Offsetx', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Offset X'}),
        ('Offsety', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Offset Y'}),
        ('Flipx', 'Toggle', False, {'label': 'Flip X'}),
        ('Flipy', 'Toggle', False, {'label': 'Flip Y'}),
        ('Swap', 'Toggle', False, {'label': 'Swap XY'}),
        ('Warp', 'Toggle', False, {'label': 'Warp (warptable)'}),
        ('Intensity', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Intensity'}),
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Gain'}),
        ('Rgb', 'RGB', (0.1, 1.0, 0.25), {'label': 'Colour'}),
    ]),
    ('Drive', [
        ('Intensitysrc', 'Menu', 'manual', {'names': ['manual', 'bpm', 'audio', 'chop'],
                                            'labels': ['Manual', 'BPM LFO', 'Audio', 'CHOP']}),
        ('Bpm', 'Float', 120.0, {'min': 20, 'max': 300, 'label': 'BPM'}),
        ('Beatdiv', 'Float', 1.0, {'min': 0.125, 'max': 8, 'label': 'Beat mult'}),
        ('Audioch', 'CHOP', '', {'label': 'Audio CHOP (level)'}),
        ('Audioamt', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Audio amount'}),
        ('Drivechop', 'CHOP', '', {'label': 'Drive CHOP (chan 0)'}),
        ('Strobe', 'Menu', 'off', {'names': ['off', 'manual', 'bpm', 'audio'],
                                   'labels': ['Off', 'Manual', 'BPM', 'Audio gate']}),
        ('Strobeon', 'Momentary', False, {'label': 'Strobe button'}),
        ('Blackout', 'Toggle', False, {'label': 'Blackout'}),
        ('Hold', 'Toggle', False, {'label': 'Hold image'}),
    ]),
    ('Preview', [
        ('Previewon', 'Toggle', True, {'label': 'Preview on'}),
        ('Previewres', 'Int', 1080, {'min': 128, 'max': 2160, 'label': 'Preview px'}),
        ('Galvobw', 'Float', 6000.0, {'min': 200, 'max': 20000, 'label': 'Galvo bandwidth Hz'}),
        ('Galvozeta', 'Float', 0.7, {'min': 0.1, 'max': 2, 'label': 'Galvo damping'}),
        ('Showlag', 'Toggle', False, {'label': 'Show galvo lag'}),
        ('Showblank', 'Toggle', False, {'label': 'Show blanked travel'}),
        ('Persist', 'Float', 60.0, {'min': 0, 'max': 1000, 'label': 'Persistence ms'}),
        ('Glow', 'Float', 6.0, {'min': 0, 'max': 64, 'label': 'Glow px'}),
        ('Spotgain', 'Float', 0.35, {'min': 0, 'max': 4, 'label': 'Spot gain'}),
        ('Spotsize', 'Float', 10.0, {'min': 1, 'max': 64, 'label': 'Spot px'}),
        ('Bg', 'RGB', (0.0, 0.0, 0.0), {'label': 'Background'}),
    ]),
    ('Controls', [
        ('Opencontrols', 'Pulse', None, {'label': 'Open controls'}),
        ('Savesnap', 'Pulse', None, {'label': 'Save snapshot'}),
        ('Exportilda', 'Pulse', None, {'label': 'Export ILDA'}),
    ]),
]
KIT_PAGES = ['Source', 'Path', 'Shape', 'Drive', 'Preview']


def _pars(c):
    """Create the custom pages/pars once; keep existing values."""
    for page_name, pars in PAGES:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None or (style == 'RGB' and getattr(c.par, name + 'r', None) is not None):
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
            elif style == 'Momentary':
                page.appendMomentary(name, label=label)
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style == 'RGB':
                for p, v in zip(page.appendRGB(name, label=label), default):
                    p.default = v
                    p.val = v
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
                p.default = default
                p.val = default
            elif style in ('SOP', 'CHOP', 'POP', 'TOP'):
                getattr(page, 'append' + style)(name, label=label)


def _sd(o):
    """T-70: destroy through safe_destroy (td_exec namespace, else the MCP handlers module)."""
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


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


def _set(o, name, val=None, expr=None, missing=None):
    """Set a par if this build has it (newer/older builds differ); record misses."""
    p = getattr(o.par, name, None)
    if p is None:
        if missing is not None:
            missing.append('%s.%s' % (o.name, name))
        return False
    if expr is not None:
        _expr(p, expr)
    else:
        if p.isMenu and isinstance(val, str) and val not in p.menuNames:
            hit = [m for m in p.menuNames if val in m]
            if not hit:
                if missing is not None:
                    missing.append('%s.%s=%s (menu %s)' % (o.name, name, val, list(p.menuNames)[:12]))
                return False
            val = hit[0]
        p.mode = ParMode.CONSTANT
        p.val = val
    return True


def _script(c, cls, name, fn, what):
    s = _mk(c, cls, name)
    cb = s.par.callbacks.eval()
    if cb is None:
        cb = _mk(c, textDAT, name + '_callbacks')
        s.par.callbacks = cb
    cb.text = SCRIPT_CB.format(name=name, what=what, fn=fn, clock=CLOCK.get(name, '0'))
    s.par.setuppars.pulse()
    _clock(s, CLOCK.get(name, '0'))         # rebuild: the par exists already, re-set its expression
    return s


def _clock(s, expr):
    p = getattr(s.par, 'Frame', None)
    if p is not None:
        _expr(p, expr)
        return True
    return False                            # first build: onSetupParameters sets it (SCRIPT_CB)


def _compute(c, name, path, ins, vec, exprs, pixel=False):
    """A one-pass GLSL TOP at the preview size, rgba16f: compute (T-47) or pixel mode, shader in its docked
    `<name>_compute` / `<name>_pixel` DAT."""
    t = _mk(c, glslTOP, name)
    t.par.mode = 'vertexpixel' if pixel else 'compute'
    dn = name + ('_pixel' if pixel else '_compute')
    d = c.op(dn)
    if d is None:
        d = _mk(c, textDAT, dn)
        d.dock = t
    d.text = open(path).read()
    if pixel:
        t.par.pixeldat = d
    else:
        t.par.computedat = d
    t.par.outputresolution = 'custom'
    _expr(t.par.resolutionw, "parent().par.Previewres.eval()")
    _expr(t.par.resolutionh, "parent().par.Previewres.eval()")
    t.par.format = 'rgba16float'
    for k, o in enumerate(ins):
        t.inputConnectors[k].connect(o)
    t.seq.vec.numBlocks = 1
    t.par.vec0name = vec
    for a, e in zip('xyz', exprs):
        _expr(getattr(t.par, 'vec0value' + a), e)
    return t


def build(parent_path='/project1/lab'):
    missing = []
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True                    # house rule: builders re-enable their own COMP each step
    c.comment = ('LP_laser_path: any source (pattern/SOP/CHOP/POP/TOP trace/text/audio) -> laser sample stream '
                 '(Native Laser CHOP or Own numpy engine) + beam preview + stats. Out: out1 CHOP laser, out2 TOP '
                 'preview, out3 DAT stats. No device output here (LO_laser_out). Safety: interlock, shutter and '
                 'e-stop are the operator\'s; nothing here limits values.')
    _close_window(c)
    _pars(c)
    if c.par.Fps.mode == ParMode.CONSTANT and c.fetch('lp_fps_bound', False, search=False) is False:
        _expr(c.par.Fps, 'project.cookRate')   # read-out follows the project; editable (set a value to override)
        c.store('lp_fps_bound', True)

    # code
    lg = _mk(c, textDAT, 'lp_logic')
    lg.text = open(LOGIC_FILE).read()
    lg.comment = 'Pure logic = builders/laser_path_logic.py (tests: test/test_laser_path.py).'
    rt = _mk(c, textDAT, 'lp_rt')
    rt.text = open(RT_FILE).read()
    rt.comment = 'TD runtime = builders/laser_path_rt.py (rows, engines, drive, preview, stats, snapshot).'
    wt = _mk(c, tableDAT, 'warptable')
    if wt.numRows != 10 or wt[0, 0] is None or wt[0, 0].val != 'gx':
        wt.clear()
        wt.appendRow(['gx', 'gy', 'x', 'y'])
        for gy in (-1, 0, 1):
            for gx in (-1, 0, 1):
                wt.appendRow([gx, gy, gx, gy])
    wt.comment = '3x3 warp grid (Warp toggle): x y = where grid point gx gy lands. Edit to calibrate.'

    # 1 Sources
    in1 = _mk(c, inSOP, 'in1')
    in2 = _mk(c, inCHOP, 'in2')
    in3 = _mk(c, inTOP, 'in3')
    try:
        in4 = _mk(c, inPOP, 'in4')
    except Exception:
        in4 = None
        missing.append('inPOP')
    clip = _mk(c, moviefileinTOP, 'trace_clip')
    clip.par.file = CLIP
    _expr(clip.par.play, "parent().par.Source.eval() == 'toptrace' and parent().par.Tracesrc.eval() == 'clip'")
    tsw = _mk(c, switchTOP, 'trace_src')
    tsw.inputConnectors[0].connect(in3)
    tsw.inputConnectors[1].connect(clip)
    _expr(tsw.par.index, "parent().par.Tracesrc.menuIndex")
    tres = _mk(c, resolutionTOP, 'trace_res')
    tres.inputConnectors[0].connect(tsw)
    tres.par.outputresolution = 'custom'
    _expr(tres.par.resolutionw, "max(16, int(160 / max(1, parent().par.Tracesteps.eval()) * 3))")
    _expr(tres.par.resolutionh, "max(16, int(90 / max(1, parent().par.Tracesteps.eval()) * 3))")
    tblur = _mk(c, blurTOP, 'trace_blur')
    tblur.inputConnectors[0].connect(tres)
    _expr(tblur.par.size, "parent().par.Traceblur.eval()")
    tmono = _mk(c, monochromeTOP, 'trace_mono')
    tmono.inputConnectors[0].connect(tblur)
    trace = _mk(c, traceSOP, 'trace')
    _set(trace, 'top', 'trace_mono', missing=missing)
    _set(trace, 'thresh', expr="parent().par.Tracelevel.eval()", missing=missing)   # LIVE CHECK: par names
    _set(trace, 'step', 4.0, missing=missing)
    txt = _mk(c, textSOP, 'text_sop')
    _expr(txt.par.text, "parent().par.Text.eval()")
    om = list(txt.par.output.menuNames) if getattr(txt.par, 'output', None) is not None else []
    pick = (next((m for m in om if 'outline' in m.lower()), None) or next((m for m in om if 'line' in m.lower()), None)
            or ('closedpolys' if 'closedpolys' in om else None))   # 31550: triangles/closedpolys/openpolys (live 26 Oct)
    if pick:
        txt.par.output = pick
    else:
        missing.append('text_sop.output outline (menu %s)' % om)
    try:
        _expr(txt.par.font, "parent().par.Font.eval()")
    except Exception as e:
        missing.append('text_sop.font expr: %s' % e)
    pchop = None
    try:
        pchop = _mk(c, poptoCHOP, 'pop_chop')
        _expr(pchop.par.pop, "parent().par.Pop.eval() or op('in4')")
        if getattr(pchop.par, 'attribscope', None) is not None:   # string par with a '*' suggestion menu (31550)
            pchop.par.attribscope.mode = ParMode.CONSTANT
            pchop.par.attribscope.val = 'P Color'
        else:
            missing.append('pop_chop.attribscope')
    except Exception as e:
        missing.append('poptoCHOP: %s' % e)
    rows = _script(c, scriptCHOP, 'rows', 'cook_rows', 'source -> point rows x y r g b id lascorner')

    # 2 Native engine
    nin = _script(c, scriptCHOP, 'native_in', 'cook_native_in', 'rows -> transform, tint, draw order -> Laser CHOP input')
    nin.inputConnectors[0].connect(rows)
    las = None
    try:
        las = _mk(c, laserCHOP, 'laser_native')
    except Exception as e:
        missing.append('laserCHOP: %s' % e)
    if las is not None:
        _set(las, 'source', 'chop', missing=missing)
        _set(las, 'chop', 'native_in', missing=missing)       # by name: survives a COMP rename
        for dbg in ('debug', 'debugchan'):                    # LIVE CHECK: which par adds the debug/flag channel
            if getattr(las.par, dbg, None) is not None and getattr(las.par, dbg).style == 'Toggle':
                _set(las, dbg, True, missing=missing)
        for tdn, ours in (('outputrate', 'Pps'), ('stepsize', 'Stepsize'), ('bstepsize', 'Bstepsize'),
                          ('mincornerhold', 'Minhold'), ('maxcornerhold', 'Maxhold'),
                          ('closedoverlap', 'Closedoverlap'), ('preblankon', 'Preblankon'),
                          ('postblankon', 'Postblankon'), ('preblankoff', 'Preblankoff'),
                          ('postblankoff', 'Postblankoff'), ('colordelay', 'Colordelay'),
                          ('interpcolors', 'Interpcolors')):
            _set(las, tdn, expr=P.format(ours) + '.eval()', missing=missing)
        nfix = _script(c, scriptCHOP, 'native_fix', 'cook_native_fix', 'Laser CHOP stream -> x y r g b i flag')
        nfix.inputConnectors[0].connect(las)
    else:
        nfix = _script(c, scriptCHOP, 'native_fix', 'cook_native_fix', 'Laser CHOP unavailable: empty stream')

    # 3 Own engine
    own = _script(c, scriptCHOP, 'own', 'cook_own', 'Own engine: order, resample, dwell, blanks, colour delay, budget')
    own.inputConnectors[0].connect(rows)
    eng = _mk(c, switchCHOP, 'engine')
    eng.inputConnectors[0].connect(nfix)
    eng.inputConnectors[1].connect(own)
    _expr(eng.par.index, "parent().par.Engine.menuIndex")

    # 4 Drive + output
    drv = _script(c, scriptCHOP, 'drive', 'cook_drive', 'intensity source, strobe, blackout, hold')
    drv.inputConnectors[0].connect(eng)
    laser = _mk(c, nullCHOP, 'laser')
    laser.inputConnectors[0].connect(drv)
    out1 = _mk(c, outCHOP, 'out1')
    out1.inputConnectors[0].connect(laser)
    st = _mk(c, scriptDAT, 'stats')
    scb = st.par.callbacks.eval()
    if scb is None:
        scb = _mk(c, textDAT, 'stats_callbacks')
        st.par.callbacks = 'stats_callbacks'
    scb.text = STATS_CB
    out3 = _mk(c, outDAT, 'out3')
    out3.inputConnectors[0].connect(st)

    # 5 Preview (beam simulation): instance points -> additive sprites -> persistence -> glow
    pp = _script(c, scriptCHOP, 'preview_pts', 'cook_preview_pts', 'galvo lag + dwell brightness -> instances')
    pp.inputConnectors[0].connect(laser)
    spr = _mk(c, glslTOP, 'sprite')
    sglsl = c.op('sprite_pixel')             # the GLSL TOP's own docked pixel DAT holds the shader (strobe pattern)
    if sglsl is None:
        sglsl = _mk(c, textDAT, 'sprite_pixel')
        sglsl.dock = spr
    sglsl.text = open(SPRITE_FILE).read()
    spr.par.pixeldat = sglsl
    if c.op('sprite_glsl') is not None:      # an earlier draft used a separate DAT
        _sd(c.op('sprite_glsl'))
    spr.par.outputresolution = 'custom'
    spr.par.resolutionw, spr.par.resolutionh = 64, 64
    _set(spr, 'format', 'rgba16float', missing=missing)
    mat = _mk(c, constantMAT, 'beam_mat')
    mat.par.colormap = spr
    mat.par.blending = True
    _set(mat, 'srcblend', 'one', missing=missing)
    _set(mat, 'destblend', 'one', missing=missing)
    _set(mat, 'depthtest', False, missing=missing)
    _set(mat, 'depthwriting', False, missing=missing)
    _set(mat, 'postmultalpha', False, missing=missing)
    geo = _mk(c, geometryCOMP, 'beam_geo')
    for ch_ in list(geo.children):
        if ch_.valid and ch_.name != 'spot':
            _sd(ch_)
    spot = geo.op('spot') or geo.create(rectangleSOP, 'spot')
    _expr(spot.par.sizex, "parent(2).par.Spotsize.eval() * 2.0 / max(16, parent(2).par.Previewres.eval())")
    _expr(spot.par.sizey, "parent(2).par.Spotsize.eval() * 2.0 / max(16, parent(2).par.Previewres.eval())")
    spot.render = True
    spot.display = True
    geo.par.material = mat
    geo.par.instancing = True
    geo.par.instanceop = pp
    for k, v in (('instancetx', 'tx'), ('instancety', 'ty'), ('instancer', 'r'), ('instanceg', 'g'), ('instanceb', 'b')):
        _set(geo, k, v, missing=missing)
    _set(geo, 'instancecolorop', pp, missing=missing)
    _set(geo, 'instancecolormode', 'replace', missing=missing)
    cam = _mk(c, cameraCOMP, 'beam_cam')
    cam.par.projection = 'ortho'
    cam.par.orthowidth = 2.0
    cam.par.tz = 5
    ren = _mk(c, renderTOP, 'beam_render')
    ren.par.camera = cam
    ren.par.geometry = geo
    ren.par.lights = ''
    ren.par.outputresolution = 'custom'
    _expr(ren.par.resolutionw, "parent().par.Previewres.eval()")
    _expr(ren.par.resolutionh, "parent().par.Previewres.eval()")
    _set(ren, 'format', 'rgba16float', missing=missing)
    ren.par.bgcolora = 0
    _expr(ren.par.render, "parent().par.Previewon.eval()")
    _set(ren, 'antialias', 'aa1', missing=missing)
    # persistence + look as two one-pass GLSL TOPs (perf wave 3, 27 Oct): persist_add (pixel) =
    # beam_render + persist_fb x decay (was persist_decay Level + persist_add Composite), preview_comp = persist +
    # glow + background (was a 3-input Composite + the bg Constant)
    for gone in ('persist_decay', 'bg', 'persist_add_compute'):
        if c.op(gone) is not None:
            _sd(c.op(gone))
    fb = _mk(c, feedbackTOP, 'persist_fb')
    fb.inputConnectors[0].connect(ren)
    add = _compute(c, 'persist_add', PERSIST_FILE, (ren, fb), 'uDecay', ["op('lp_rt').module.decay_factor()"],
                   pixel=True)   # pixel: the Blur reading a compute output cost ~2x (T-222)
    fb.par.top = add
    glow = _mk(c, blurTOP, 'glow_blur')
    glow.inputConnectors[0].connect(add)
    _expr(glow.par.size, "parent().par.Glow.eval()")
    look = _compute(c, 'preview_comp', LOOK_FILE, (add, glow), 'uBg',
                    ['parent().par.Bgr.eval()', 'parent().par.Bgg.eval()', 'parent().par.Bgb.eval()'])
    prev = _mk(c, nullTOP, 'preview')
    prev.inputConnectors[0].connect(look)
    out2 = _mk(c, outTOP, 'out2')
    out2.inputConnectors[0].connect(prev)

    # Controls
    pe = _mk(c, parameterexecuteDAT, 'controls_open')
    pe.text = PEXEC
    pe.par.op = c
    pe.par.pars = 'Opencontrols Savesnap Exportilda'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = False
    pe.par.onpulse = True
    ns_ = dict(globals())
    exec(open(os.path.join(HERE, 'zkit.py')).read(), ns_)
    kit = ns_['build_controls'](c.path, pages=KIT_PAGES, d=52, cols=8)

    c.par.opviewer.expr = "me.op('preview')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'controls_open'],
         'body': 'zkit panel (Source, Path, Shape, Drive, Preview pages) + window. Pulse Opencontrols. Savesnap writes '
                 'output/laser/LP_laser_path.json; Exportilda writes LP_laser_path.ild (ILDA 5) + _ilda.json checks.'},
        {'title': '0 Code', 'role': 'process', 'ops': ['lp_logic', 'lp_rt', 'warptable'],
         'body': 'lp_logic = builders/laser_path_logic.py (49 offline tests), lp_rt = builders/laser_path_rt.py. '
                 'warptable = 3x3 calibration grid.'},
        {'title': '1 Source', 'role': 'input',
         'ops': ['in1', 'in2', 'in3', 'in4', 'trace_clip', 'trace_src', 'trace_res', 'trace_blur', 'trace_mono',
                 'trace', 'text_sop', 'pop_chop', 'rows', 'rows_callbacks'],
         'body': 'Source picks pattern / SOP / CHOP / POP / TOP trace (In3 or the stored webcam clip) / Text / audio '
                 'scope -> rows (x y r g b id lascorner, one sample per vertex).'},
        {'title': '2 Native engine', 'role': 'process',
         'ops': ['native_in', 'native_in_callbacks', 'laser_native', 'native_fix', 'native_fix_callbacks'],
         'body': 'Transform + tint + draw order (Order) -> built-in Laser CHOP (rate, steps, holds, blanking from the '
                 'COMP pars) -> x y r g b i flag.'},
        {'title': '3 Own engine', 'role': 'process', 'ops': ['own', 'own_callbacks', 'engine'],
         'body': 'numpy: shapes, transform, nearest + 2-opt order, resample, corner dwell, 5-phase blanking, colour '
                 'delay, frame budget / overflow. Engine switch picks Native or Own.'},
        {'title': '4 Drive + out', 'role': 'output',
         'ops': ['drive', 'drive_callbacks', 'laser', 'out1', 'stats', 'stats_callbacks', 'out3'],
         'body': 'Intensity (manual / BPM / audio / CHOP), strobe, blackout, hold. out1 = laser (x y r g b i flag at '
                 'Pps), out3 = stats. No limits: the operator decides.'},
        {'title': '5 Beam preview', 'role': 'output',
         'ops': ['preview_pts', 'preview_pts_callbacks', 'sprite_pixel', 'sprite', 'beam_mat', 'beam_geo', 'beam_cam',
                 'beam_render', 'persist_fb', 'persist_add', 'persist_add_pixel', 'glow_blur', 'preview_comp',
                 'preview_comp_compute',
                 'preview', 'out2'],
         'body': 'Galvo lag model (Showlag) + dwell brightness -> instanced additive spots -> persistence (half life '
                 'Persist ms) -> glow. Image longer than a frame: only this frame\'s window is drawn.'},
    ]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    return {'comp': c.path, 'missing': missing, 'kit': str(kit)[:200], 'layout': str(lay)[:300],
            'laser_pars': [p.name for p in las.pars() if p.page is not None][:80] if las is not None else None}
