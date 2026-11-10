# review_tour runtime (copied into /project1/review_tour/tour_rt by builders/review_tour.py). TD 2025.31550.
# Called by tour_pars (Parameter Execute), tour_tick (Execute, frame start: window open/close edges + 0.5 s list
# refresh while open), list_click / view_click (Panel Execute) and tour_keys (Keyboard In, panels = the tour).
# Cook rule: only the shown COMP is woken; what the tour woke is parked when the tour leaves it; what was cooking
# when the tour started, a live lane's COMP (logs/active_lanes.json) and top-level COMPs are never parked.
# No functions in storage (T-67); no TOP readback (T-74/T-76); the window is never rebuilt from here (T-70).
import json
import os

LANES = '%(lanes)s'
LAB = '%(lab)s'
_C = {'mt': None, 'lanes': [], 'open': False, 'lines': [], 'sig': {}, 'n': 0}


def L():
    return op('tour_logic').module


def C():
    return parent()


def _set(p, v):
    if p is not None and p.eval() != v:
        p.val = v


def lanes():
    try:
        mt = os.path.getmtime(LANES)
        if mt != _C['mt']:
            _C['lanes'] = sorted(json.load(open(LANES)).keys())
            _C['mt'] = mt
    except Exception:
        pass
    return _C['lanes']


def win(c=None):
    return (c or C()).op('controls_window')


def is_open(c=None):
    w = win(c)
    return bool(w is not None and w.isOpen)


def _source_top(o):
    h = op('/jazib_mcp/handlers')
    if h is not None:
        try:
            return h.module._source_top(o)
        except Exception:
            pass
    for nm in ('out1', 'out', 'null_out'):
        k = o.op(nm)
        if k is not None and k.isTOP:
            return k.path
    return None


# ---------------------------------------------------------------- items
def scan(c=None):
    """items table <- lab children COMPs (no annotate boxes) grouped like the lab's stage boxes."""
    c = c or C()
    lab = op(c.par.Lab.eval()) if c.par.Lab.eval() else op(LAB)
    if lab is None:
        return 0
    plan = lab.fetch('jz_stages', None, search=False)
    stages = plan.get('stages', []) if isinstance(plan, dict) else (plan or [])
    kids = [ch.name for ch in lab.children if ch.isCOMP and ch.OPType != 'annotateCOMP']
    items = L().build_items(stages, kids)
    t = c.op('items')
    rows = [['index', 'group', 'name', 'path', 'top', 'ctl']]
    for i, it in enumerate(items):
        o = lab.op(it['name'])
        top = _source_top(o) or ''
        ctl = 'pulse' if getattr(o.par, 'Opencontrols', None) is not None else (
            'window' if o.op('controls_window') is not None else '')
        rows.append([i, it['group'], it['name'], o.path, top, ctl])
    old = [[x.val for x in t.row(r)] for r in range(t.numRows)]
    if [[str(x) for x in r] for r in rows] != old:
        t.clear()
        t.appendRows(rows)
    n = len(items)
    p = c.par.Index
    p.normMax = max(1, n - 1)
    p.max = max(0, n - 1)
    _C['n'] = n
    return n


def items(c=None):
    t = (c or C()).op('items')
    hd = [x.val for x in t.row(0)] if t.numRows else []
    return [dict(zip(hd, [x.val for x in t.row(r)])) for r in range(1, t.numRows)]


def cur(c=None):
    c = c or C()
    its = items(c)
    if not its:
        return None, its
    i = L().clamp_index(c.par.Index.eval(), len(its))
    return its[i], its


# ---------------------------------------------------------------- cook guard
def _session(c):
    return dict(c.fetch('rt_session', {}, search=False) or {})


def _cands(its):
    out = {}
    for it in its:
        o = op(it['path'])
        if o is not None:
            out[o.path] = bool(o.allowCooking)
    return out


def start(c=None):
    """Window opened: remember what was cooking (never parked by the tour), then show the current COMP."""
    c = c or C()
    scan(c)
    _, its = cur(c)
    if _session(c):                                       # still running (e.g. reopened after a rebuild): keep it
        return show(c)
    cooking = _cands(its)
    c.store('rt_session', {'before': sorted(p for p, on in cooking.items() if on), 'owned': [], 'shown': ''})
    _set(c.par.Tourstatus, 'tour started: %%d COMPs, %%d cooking before' %% (len(its), sum(cooking.values())))
    return show(c)


def show(c=None):
    """Point the view at the current COMP and apply the cook plan (wake it, park what the tour woke before)."""
    c = c or C()
    it, its = cur(c)
    s = _session(c)
    if not s:
        _point(c, it)
        render(c, force=True)
        return {'shown': it['path'] if it else None, 'session': False}
    guard = bool(c.par.Cookguard.eval())
    prot = set(lanes() if c.par.Protectlanes.eval() else [])
    cooking = _cands(its)
    shown = it['path'] if it else None
    wake, park, owned = L().cook_plan(shown if guard else None, cooking, s.get('before', []), s.get('owned', []), prot)
    if not guard:
        wake, park = [], []
    for p in wake:
        op(p).allowCooking = True
    for p in park:
        op(p).allowCooking = False
    s['owned'] = owned
    s['shown'] = shown or ''
    c.store('rt_session', s)
    _point(c, it)
    _set(c.par.Tourstatus, 'show %%s: woke %%s, parked %%s' %% (it['name'] if it else '-',
                                                          ','.join(x.rsplit('/', 1)[-1] for x in wake) or '-',
                                                          ','.join(x.rsplit('/', 1)[-1] for x in park) or '-'))
    render(c, force=True)
    return {'shown': shown, 'wake': wake, 'park': park, 'owned': owned}


def leave(c=None):
    """Window closed: park everything the tour woke (never what was cooking before / lanes), end the session."""
    c = c or C()
    s = _session(c)
    if not s:
        return {'park': []}
    _, its = cur(c)
    prot = set(lanes() if c.par.Protectlanes.eval() else [])
    wake, park, owned = L().cook_plan(None, _cands(its), s.get('before', []), s.get('owned', []), prot)
    for p in park:
        op(p).allowCooking = False
    c.unstore('rt_session')
    c.op('view_src').par.top = ''                       # nothing is pulled while closed
    _set(c.par.Tourstatus, 'tour closed: parked %%s' %% (','.join(x.rsplit('/', 1)[-1] for x in park) or '-'))
    _update_status(c)
    return {'park': park}


def _point(c, it):
    top = it['top'] if it else ''
    src = c.op('view_src')
    if src.par.top.eval() is None or (src.par.top.eval().path if src.par.top.eval() else '') != top:
        src.par.top = top
    _set(c.par.Shown, it['path'] if it else '')
    _update_status(c)


def _update_status(c):
    _, its = cur(c)
    on = [it['name'] for it in its if op(it['path']) is not None and op(it['path']).allowCooking]
    _set(c.par.Cooking, ' '.join(on))


# ---------------------------------------------------------------- actions
def go(c, d):
    c = c or C()
    n = _C['n'] or len(items(c))
    c.par.Index = L().step(c.par.Index.eval(), n, d)    # Index change -> on_value -> show


def open_ctl(c=None):
    c = c or C()
    it, _ = cur(c)
    o = op(it['path']) if it else None
    if o is None:
        return 'none'
    if not o.allowCooking:                               # its scripts need it cooking (T-100 / T-105)
        show(c)
    p = getattr(o.par, 'Opencontrols', None)
    if p is not None:
        p.pulse()
        _set(c.par.Tourstatus, 'opened %%s controls' %% it['name'])
        return 'pulse'
    w = o.op('controls_window')
    if w is not None:
        w.par.winopen.pulse()
        return 'window'
    _set(c.par.Tourstatus, '%%s has no controls panel' %% it['name'])
    return 'none'


def open_tour(c=None):
    c = c or C()
    w = win(c)
    if w is not None:
        w.par.winopen.pulse()                            # tick sees the open edge -> start()


def close_tour(c=None):
    c = c or C()
    w = win(c)
    if w is not None and w.isOpen:
        w.par.winclose.pulse()                           # tick sees the close edge -> leave()


def on_pulse(c, par):
    n = par.name
    if n == 'Prev':
        go(c, -1)
    elif n == 'Next':
        go(c, 1)
    elif n == 'Openctl':
        open_ctl(c)
    elif n == 'Opentour':
        open_tour(c)
    elif n == 'Closetour':
        close_tour(c)
    elif n == 'Rescan':
        scan(c)
        show(c)


def on_value(c, par, prev):
    if par.name == 'Index':
        show(c)
    elif par.name in ('Cookguard', 'Protectlanes'):
        show(c)


def click(c, v):
    it = L().item_at(_C['lines'], v)
    if it is not None:
        c.par.Index = int(it)
    return it


def key(c, info):
    if not getattr(info, 'state', True):
        return None
    a = L().key_action(getattr(info, 'key', ''), getattr(info, 'character', ''))
    if a == 'prev':
        go(c, -1)
    elif a == 'next':
        go(c, 1)
    elif a == 'ctl':
        open_ctl(c)
    elif a == 'close':
        close_tour(c)
    return a


# ---------------------------------------------------------------- drawing (only while open, only what changed)
def _write(c, name, rows):
    if _C['sig'].get(name) == rows:
        return False
    t = c.op(name)
    t.clear()
    t.appendRow(['x', 'y', 'text'])
    if rows:
        t.appendRows(rows)
    _C['sig'][name] = rows
    return True


def render(c=None, force=False):
    c = c or C()
    if not is_open(c) and not force:
        return 0
    lg = L()
    it, its = cur(c)
    idx = lg.clamp_index(c.par.Index.eval(), len(its))
    cooking = set(x['name'] for x in its if op(x['path']) is not None and op(x['path']).allowCooking)
    has_top = dict((x['name'], bool(x['top'])) for x in its)
    lines = lg.list_lines(its, idx, cooking, has_top)
    _C['lines'] = lines
    n = 0
    for kind in ('head', 'dim', 'group', 'body', 'sel'):
        n += _write(c, 'sp_' + kind, lg.spec_rows(lines, kind))
    bar = lg.sel_bar(lines)
    r = c.op('list_bar')
    if bar is not None:
        x, y, w, h = bar
        cx, cy = lg.bar_center(bar)                     # Rectangle TOP centre is measured from the image centre
        vals = {'centerx': cx, 'centery': cy, 'sizex': w, 'sizey': h, 'fillalpha': 1}
    else:
        vals = {'fillalpha': 0}
    for k, v in vals.items():
        _set(getattr(r.par, k), v)
    a, b = lg.view_title(it, idx, len(its), bool(it and it['name'] in cooking), bool(it and it['top']),
                         bool(it and it['ctl']))
    n += _write(c, 'sp_title', [[14, lg.VIEW_H - 30, a], [14, lg.VIEW_H - 52, b]] if it else [[14, lg.VIEW_H - 30, a]])
    _update_status(c)
    return n


def tick(c=None):
    c = c or C()
    o = is_open(c)
    if o != bool(c.fetch('rt_open', False, search=False)):  # in storage: survives a runtime text rewrite
        c.store('rt_open', o)
        if o:
            start(c)
        else:
            leave(c)
        return
    if o and absTime.frame %% 30 == 0:
        render(c)
