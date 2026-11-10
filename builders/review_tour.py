# review_tour builder - /project1/review_tour: the LAB REVIEW window. Lists every lab COMP (children of
# /project1/lab, grouped like the lab's stage boxes), shows the selected COMP's Out TOP large + a controls button,
# Prev/Next (zkit knobs + arrow keys + click a row), and cooks ONLY the shown COMP: un-parks it on show, re-parks it
# on leave; a COMP that was cooking before the tour started, a live lane's COMP or a top-level COMP is never parked.
# Logic: builders/review_tour_logic.py (offline tests test/test_review_tour.py); runtime builders/review_tour_rt.py.
# Doc: docs/builds/review_tour.md. Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/review_tour.py').read(), ns); ns['build']()
# Open: pulse /project1/review_tour Opentour (window title 'Lab review').
# Idempotent, T-70 safe: the window is closed before the rebuild and reopened 5 frames after; no panel is destroyed;
# texts/tables/pars updated in place. No functions in storage (T-67). No TOP readback (T-74/T-76). ASCII only.
import os

NAME = 'review_tour'
PARENT = '/project1'
LAB = '/project1/lab'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = REPO + '/builders'
LOGIC_FILE = os.path.join(HERE, 'review_tour_logic.py')
RT_FILE = os.path.join(HERE, 'review_tour_rt.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
TITLE = 'Lab review'
FONT = 'Menlo'

PARS_CB = '''# review_tour: custom par change / pulse -> tour_rt. Written by builders/review_tour.py.
def onValueChange(par, prev):
    parent().op('tour_rt').module.on_value(parent(), par, prev)


def onPulse(par):
    parent().op('tour_rt').module.on_pulse(parent(), par)
'''

TICK_CB = '''# review_tour: per frame -> tour_rt.tick (window open/close edges start/end the tour; list refresh while open).
def onFrameStart(frame):
    parent().op('tour_rt').module.tick(parent())
'''

CLICK_CB = '''# review_tour: a left click on the list selects that COMP.
def onOffToOn(panelValue):
    parent().op('tour_rt').module.click(parent(), float(panelValue.owner.panel.v))
    return
'''

VIEW_CB = '''# review_tour: a click on the title bar of the big view opens the shown COMP's controls.
def onOffToOn(panelValue):
    if float(panelValue.owner.panel.v) > 0.93:
        parent().op('tour_rt').module.open_ctl(parent())
    return
'''

KEYS_CB = '''# review_tour: keys while the tour panel has focus: left/up/[ prev, right/down/]/space next, Enter/c controls,
# Esc close.
def onKey(dat, keyInfo):
    parent().op('tour_rt').module.key(parent(), keyInfo)
    return


def onShortcut(dat, shortcutName, time):
    return
'''

COLS = {'head': (1.0, 1.0, 1.0), 'dim': (0.52, 0.55, 0.6), 'group': (0.98, 0.72, 0.26), 'body': (0.84, 0.86, 0.88),
        'sel': (1.0, 1.0, 1.0), 'title': (1.0, 1.0, 1.0)}
BG = (0.065, 0.07, 0.085)
ACCENT = (0.16, 0.42, 0.95)


def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _mk(c, cls, name, viewer=True):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = viewer
    return o


def _setp(o, **kw):
    for k, v in kw.items():
        p = getattr(o.par, k)
        if p.mode != ParMode.CONSTANT:
            p.mode = ParMode.CONSTANT
        cur = p.eval()
        cur = cur.path if hasattr(cur, 'path') else cur
        if cur != v:
            p.val = v


def _inputs(comp, srcs):
    """Multi-input TOP: inputs = srcs in order (input 0 on top for 'over'); rewired only when they differ."""
    if [x.name for x in comp.inputs] == [x.name for x in srcs]:
        return
    for cn in list(comp.inputConnectors):
        cn.disconnect()
    for s_ in srcs:
        s_.outputConnectors[0].connect(comp)


def _logic():
    ns = {}
    exec(open(LOGIC_FILE).read(), ns)
    return ns


PAGES = [
    ('Tour', [
        ('Prev', 'Pulse', None, {'label': 'Prev'}),
        ('Next', 'Pulse', None, {'label': 'Next'}),
        ('Index', 'Int', 0, {'label': 'COMP #', 'min': 0, 'max': 64}),
        ('Openctl', 'Pulse', None, {'label': 'Controls'}),
        ('Rescan', 'Pulse', None, {'label': 'Rescan lab'}),
        ('Closetour', 'Pulse', None, {'label': 'Close tour'}),
        ('Shown', 'Str', '', {'label': 'Shown', 'ro': True}),
        ('Cooking', 'Str', '', {'label': 'Lab COMPs cooking', 'ro': True}),
        ('Tourstatus', 'Str', '', {'label': 'Last action', 'ro': True}),
    ]),
    ('Setup', [
        ('Opentour', 'Pulse', None, {'label': 'Open tour'}),
        ('Lab', 'COMP', LAB, {'label': 'Lab COMP'}),
        ('Cookguard', 'Toggle', True, {'label': 'Cook only the shown COMP'}),
        ('Protectlanes', 'Toggle', True, {'label': 'Never park a live lane COMP'}),
    ]),
]


def _pars(c):
    for page_name, pars in PAGES:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None:
                continue
            label = o.get('label', name)
            if style == 'Pulse':
                page.appendPulse(name, label=label)
                continue
            p = getattr(page, 'append' + style)(name, label=label)[0]
            if 'min' in o:
                p.normMin = p.min = o['min']
                p.clampMin = True
            if 'max' in o:
                p.normMax = p.max = o['max']
                p.clampMax = True
            if default is not None:
                p.default = default
                p.val = default
            if o.get('ro'):
                p.readOnly = True


def _text(c, name, spec, w, h, col, size):
    t = _mk(c, textTOP, name, viewer=False)
    _setp(t, specdat=spec.path, text='', font=FONT, fontsizexunit='pixels', fontsizex=size, alignx='left',
          aligny='bottom', positionunit='pixels', outputresolution='custom', resolutionw=w, resolutionh=h, bgalpha=0,
          fontcolorr=col[0], fontcolorg=col[1], fontcolorb=col[2], fontalpha=1)
    return t


def _table(c, name):
    t = _mk(c, tableDAT, name)
    if t.numRows == 0 or [x.val for x in t.row(0)] != ['x', 'y', 'text']:   # a new Table DAT is not empty
        t.clear()
        t.appendRow(['x', 'y', 'text'])
    return t


def build(panel=True, open_window=None):
    Lg = _logic()
    LW, VW, VH = Lg['LIST_W'], Lg['VIEW_W'], Lg['VIEW_H']
    H = op('/jazib_mcp/handlers').module
    par_ = op(PARENT)
    c = par_.op(NAME)
    was_open = False
    if c is None:
        c = par_.create(baseCOMP, NAME)
        lab = op(LAB)
        c.nodeX, c.nodeY = (lab.nodeX, lab.nodeY - 300) if lab is not None else (0, -300)
    c.allowCooking = True
    w = c.op('controls_window')
    if w is not None and w.isOpen:                       # T-70: never rebuild under an open window
        was_open = True
        w.par.winclose.pulse()
    _pars(c)
    # code
    lg = _mk(c, textDAT, 'tour_logic')
    lg.text = open(LOGIC_FILE).read()
    lg.comment = 'Pure logic (copy of builders/review_tour_logic.py; tests in test/test_review_tour.py).'
    rt = _mk(c, textDAT, 'tour_rt')
    rt.text = open(RT_FILE).read() % {'lanes': REPO + '/logs/active_lanes.json', 'lab': LAB}
    rt.comment = 'Runtime (copy of builders/review_tour_rt.py): scan, show + cook guard, keys, clicks, drawing.'
    it = _mk(c, tableDAT, 'items')
    it.comment = 'Lab COMPs in stage-box order: index group name path top (Out TOP) ctl (pulse/window/"").'
    pe = _mk(c, parameterexecuteDAT, 'tour_pars')
    pe.text = PARS_CB
    _setp(pe, op=c.path, pars='Prev Next Index Openctl Rescan Closetour Opentour Cookguard Protectlanes',
          custom=True, builtin=False, valuechange=True, onpulse=True)
    tk = _mk(c, executeDAT, 'tour_tick')
    tk.text = TICK_CB
    tk.par.framestart = True
    tk.par.active = False                                # T-97: toggle after writing the text
    tk.par.active = True
    # list view: spec tables -> Text TOPs (one colour per kind) over a highlight bar + background
    texts = []
    for kind, size in (('sel', 13), ('head', 14), ('dim', 11), ('group', 12), ('body', 13)):
        sp = _table(c, 'sp_' + kind)
        texts.append(_text(c, 'tx_' + kind, sp, LW, VH, COLS[kind], size))
    bar = _mk(c, rectangleTOP, 'list_bar', viewer=False)
    _setp(bar, outputresolution='custom', resolutionw=LW, resolutionh=VH, sizeunit='pixels', centerunit='pixels',
          fillcolorr=ACCENT[0], fillcolorg=ACCENT[1], fillcolorb=ACCENT[2], borderalpha=0, bgalpha=0, cornerradius=3,
          cornerradiusunit='pixels')
    lbg = _mk(c, constantTOP, 'list_bg', viewer=False)
    _setp(lbg, outputresolution='custom', resolutionw=LW, resolutionh=VH, colorr=BG[0], colorg=BG[1], colorb=BG[2],
          alpha=1)
    lcomp = _mk(c, compositeTOP, 'list_comp', viewer=False)
    _setp(lcomp, operand='over')
    _inputs(lcomp, texts + [bar, lbg])
    lout = _mk(c, nullTOP, 'list_out')
    lout.inputConnectors[0].connect(lcomp)
    # big view: Select TOP of the shown COMP's Out TOP -> fit 450x800 -> title over -> background
    src = _mk(c, selectTOP, 'view_src', viewer=False)
    src.comment = 'Points at the shown COMP\'s Out TOP (set by tour_rt); empty while the tour is closed.'
    fit = _mk(c, fitTOP, 'view_fit', viewer=False)
    _setp(fit, fit='fitbest', outputresolution='custom', resolutionw=VW, resolutionh=VH, bgcolora=0)
    fit.inputConnectors[0].connect(src)
    spt = _table(c, 'sp_title')
    ttl = _text(c, 'tx_title', spt, VW, VH, COLS['title'], 14)
    vbg = _mk(c, constantTOP, 'view_bg', viewer=False)
    _setp(vbg, outputresolution='custom', resolutionw=VW, resolutionh=VH, colorr=0.02, colorg=0.02, colorb=0.025,
          alpha=1)
    hdr = _mk(c, rectangleTOP, 'view_hdr', viewer=False)
    _setp(hdr, outputresolution='custom', resolutionw=VW, resolutionh=VH, sizeunit='pixels', centerunit='pixels',
          sizex=VW, sizey=62, centerx=0, centery=VH / 2.0 - 31, fillcolorr=0, fillcolorg=0, fillcolorb=0,
          fillalpha=0.62, borderalpha=0, bgalpha=0)
    vcomp = _mk(c, compositeTOP, 'view_comp', viewer=False)
    _setp(vcomp, operand='over')
    _inputs(vcomp, [ttl, hdr, fit, vbg])
    vout = _mk(c, nullTOP, 'view_out')
    vout.inputConnectors[0].connect(vcomp)
    # panel: tour (window op) = list | view, zkit knobs under them
    tour = _mk(c, containerCOMP, 'tour')
    _setp(tour, bgalpha=1, bgcolorr=BG[0], bgcolorg=BG[1], bgcolorb=BG[2])
    lst = _mk(tour, containerCOMP, 'list')
    vw = _mk(tour, containerCOMP, 'view')
    for o_, x in ((lst, 0), (vw, LW)):
        _setp(o_, x=x, w=(LW if o_ is lst else VW), h=VH)
    lst.par.top = lout.path
    vw.par.top = vout.path
    lc = _mk(c, panelexecuteDAT, 'list_click')
    lc.text = CLICK_CB
    _setp(lc, panels=lst.path, panelvalue='lselect', offtoon=True, ontooff=False, whileon=False, whileoff=False,
          valuechange=False)
    vc = _mk(c, panelexecuteDAT, 'view_click')
    vc.text = VIEW_CB
    _setp(vc, panels=vw.path, panelvalue='lselect', offtoon=True, ontooff=False, whileon=False, whileoff=False,
          valuechange=False)
    kcb = _mk(c, textDAT, 'tour_keys_cb')
    kcb.text = KEYS_CB
    keys = _mk(c, keyboardinDAT, 'tour_keys')
    _setp(keys, callbacks=kcb.path, panels=' '.join([tour.path, lst.path, vw.path]), active=True)
    for lo_ in ('tour_keys_callbacks',):
        if c.op(lo_) is not None:
            _sd(c.op(lo_))
    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=['Tour'], d=52, cols=8,
                                    panel_name='tour/zk', winop='tour')
    zk = tour.op('zk')
    if zk is not None:
        zk.par.x = 0
        zk.par.y = 0
        for o_ in (lst, vw):
            o_.par.y.expr = "int(parent().op('zk').par.h)"
            o_.par.y.mode = ParMode.EXPRESSION
        tour.par.h.expr = "%d + int(me.op('zk').par.h)" % VH
        tour.par.w.expr = "max(%d, int(me.op('zk').par.w))" % (LW + VW)
        tour.par.h.mode = tour.par.w.mode = ParMode.EXPRESSION
    else:
        tour.par.w, tour.par.h = LW + VW, VH
    win = c.op('controls_window')
    if win is not None:
        _setp(win, title=TITLE, winop=tour.path)
    c.par.opviewer.expr = "me.op('view_out')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    c.comment = ('LAB REVIEW (builders/review_tour.py): pulse Opentour -> window "%s": every lab COMP grouped like the '
                 'lab boxes, the shown one large, Prev/Next (knobs, arrow keys, click a row), Enter/click title = its '
                 'controls. Cooks ONLY the shown COMP; never parks one that was cooking before the tour.' % TITLE)
    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['tour', 'controls_window', 'tour_pars', 'list_click',
                                                         'view_click', 'tour_keys', 'tour_keys_cb'],
         'body': 'tour panel (list | view, zkit knobs) in the "Lab review" window; pars, clicks, keys -> tour_rt'},
        {'title': '1 Engine', 'role': 'process', 'ops': ['tour_logic', 'tour_rt', 'tour_tick', 'items'],
         'body': 'scan lab (stage-box groups) -> items; show = wake shown, park what the tour woke; tick = open/close'},
        {'title': '2 List view', 'role': 'process', 'ops': ['sp_sel', 'sp_head', 'sp_dim', 'sp_group', 'sp_body',
                                                           'tx_sel', 'tx_head', 'tx_dim', 'tx_group', 'tx_body',
                                                           'list_bar', 'list_bg', 'list_comp', 'list_out'],
         'body': 'spec tables (fixed line slots, rewritten only on change) -> Text TOPs -> over bar + bg'},
        {'title': '3 Big view', 'role': 'output', 'ops': ['view_src', 'view_fit', 'sp_title', 'tx_title', 'view_hdr',
                                                         'view_bg', 'view_comp', 'view_out'],
         'body': 'Select TOP = the shown COMP\'s Out TOP (empty while closed) -> fit 450x800 -> title over'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = H.layout_stages(c, stages, True, arrange='mixed')
    n = rt.module.scan(c)
    if open_window is None:
        open_window = was_open
    if open_window and win is not None:
        run("args[0].par.winopen.pulse()", win, delayFrames=5)
    return {'comp': c.path, 'items': n, 'was_open': was_open, 'reopen': bool(open_window),
            'panel': str(info)[:200], 'layout': str(lay)[:300]}
