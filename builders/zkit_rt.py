"""zkit runtime: TD side of a zkit controls panel (copied as text into <comp>/controls/zk_rt; runs without the MCP).

The panel is one Container COMP. Its look is one GLSL TOP (zk_face) drawing every knob from an instance table (+ a
per-tile instance list, zk_tiles) and reading the Text TOPs (zk_text0..7 by font size, zk_hot0/1 for the value text of
a knob being dragged or changing every frame); drawing is incremental (docs/builds/zkit_perf.md). Mouse comes in through
a Panel Execute DAT (zk_mouse) and keys through a
Keyboard In DAT (zk_keys, active only while typing). Values live in the host COMP's custom parameters (two-way: the
knobs follow changes made anywhere, zk_sync). Pure value logic is in zk_logic (= builders/zkit_logic.py, tested
offline). Persistent state = tables inside the panel (zk_cfg, zk_props, zk_presets); module globals hold only the
transient mouse/typing state (lost on a text refresh, which is fine). Pure ASCII. Clean-room, spec BE 6 + 7.0.
"""
import json
import random

P = me.parent()                      # the panel container
L = P.op('zk_logic').module

SLOTS = 8
NTEXT = 8                            # Text TOPs, one per font size (spec rows carry no size)
NHOT = 2                             # hot Text TOPs: the value text of a knob being dragged / a par moving each frame
MIN_FONT = 9.0                       # live 31550: evalTextSize at fontsizex 3..9.6 px = the same width as 9 px
S = {'press': None, 'hover': None, 'edit': None, 'popup': None, 'last': (-1.0, None), 'items': {}, 'order': [],
     'lay': None, 'groups': [], 'pending': {}, 'tw': {}, 'flush': False, 'rng': random.Random(), 'menu': None,
     'gpu_last': None, 'txt_last': None, 'uni_last': None, 'dirty': False,
     # perf (docs/builds/zkit_perf.md): per-knob draw segments cached by a signature, the hit-test grid, the par ->
     # item map, hot text slots, last-written tile/text/size state; all rebuilt lazily (lost on a DAT recompile)
     'gen': 0, 'segs': {}, 'seglist': None, 'pmap': {}, 'hgrid': None, 'mgeom': None, 'stored': None,
     'hot': [None] * NHOT, 'hot_t': [0] * NHOT, 'hot_ver': 0, 'clock': 0, 'sync_names': set(), 'ui_last': None,
     'G_last': None, 'asm_last': None, 'bkey': None, 'bkeep': [], 'bmap': {}, 'fs_last': None, 'hs_last': None,
     'hotsize_last': None, 'tiles_last': None, 'cull_last': None, 'stats': {'segs': 0},
     # pages + scroll (28 Oct, T-231): the panel is a viewport; S['draw'] = this tab's knobs, S['scroll'] = px
     'gl': [], 'draw': [], 'scroll': 0, 'scrolls': {}, 'vis_key': None, 'vis': [], 'visset': set(),
     'scroll_last': None, 'win': None, 'win_gen': None, 'win_last': None, 'stage': None, 'ctiles': None,
     'uview_last': None,
     # dropdowns (28 Oct): the open pop-up list {id, names, labels, off} (names read when it opens, never at build)
     'drop': None}


# ---------------------------------------------------------------- tables
def _cfg(key, default=''):
    t = P.op('zk_cfg')
    c = t[key, 1] if t is not None else None
    return c.val if c is not None else default


def _setcfg(key, val):
    t = P.op('zk_cfg')
    if t[key, 1] is None:
        t.appendRow([key, val])
    else:
        t[key, 1] = val


def host():
    h = S.get('host')
    if h is None or not h.valid:
        v = _cfg('target')                           # '..' from the panel (drop-in, 28 Oct); absolute = older panels
        h = (op(v) if v.startswith('/') else P.op(v)) if v else None
        S['host'] = h
    return h


def _hdr(t, cols):
    """Make sure a table starts with its header row (a new Table DAT is not empty: it holds one blank cell)."""
    if t.numRows == 0 or t[0, 0].val != cols[0]:
        t.clear()
        t.appendRow(cols)
    return t


PROP_COLS = ['id', 'recall', 'sens', 'min', 'max', 'filter', 'clampmin', 'clampmax', 'label', 'size', 'color',
             'showvalue', 'ktype', 'default', 'hidden']


def props(iid):
    d = L.default_props()
    t = P.op('zk_props')
    if t is not None and t.row(iid) is not None:
        for c in PROP_COLS[1:]:
            cell = t[iid, c]
            if cell is None or cell.val == '':
                continue
            v = cell.val
            if c in ('label', 'ktype'):
                d[c] = v
            elif c == 'default':
                try:
                    d[c] = json.loads(v)
                except ValueError:
                    pass
            elif c in ('recall', 'clampmin', 'clampmax', 'showvalue', 'color', 'hidden'):
                d[c] = int(float(v))
            else:
                d[c] = float(v)
    return d


def setprop(iid, key, val):
    t = _hdr(P.op('zk_props'), PROP_COLS)
    if t.row(iid) is None:
        t.appendRow([iid] + [''] * (len(PROP_COLS) - 1))
    if key == 'default':
        val = json.dumps(val)
    elif val is None:
        val = ''
    t[iid, key] = val


# ---------------------------------------------------------------- items from the host's custom pars
def _theme():
    h = host()
    p = getattr(h.par, 'Zktheme', None) if h else None
    return 'day' if (p is not None and p.eval() == 'day') else 'night'


def _hostnum(name, default):
    h = host()
    p = getattr(h.par, name, None) if h else None
    try:
        return p.eval() if p is not None else default
    except Exception:
        return default


def _pages():
    h = host()
    want = [s for s in _cfg('pages', '').split() if s]
    skip = set(['Zkit'] + [s for s in _cfg('exclude', '').split() if s])
    out = []
    for pg in h.customPages:
        if pg.name in skip or (want and pg.name not in want):
            continue
        out.append(pg)
    return out


def _item_from_tuplet(tup, page):
    p0 = tup[0]
    if p0.name in ('Opencontrols',) or p0.readOnly or p0.style == 'Header':
        return []
    kind = L.kind_for_style(p0.style, len(p0.menuNames) if p0.style == 'Menu' else 0)   # StrMenu: no read here
    if kind is None:
        return []
    if kind == 'swatch':
        return [{'id': p0.tupletName, 'base': 'swatch', 'pars': [q.name for q in tup[:3]], 'page': page,
                 'label': p0.label, 'tup': p0.tupletName}]
    if kind in ('knob', 'int') and len(tup) > 1:
        return [{'id': q.name, 'base': kind, 'pars': [q.name], 'page': page, 'label': p0.label + ' ' + q.name[-1],
                 'tup': p0.tupletName} for q in tup]
    return [{'id': p0.name, 'base': kind, 'pars': [p0.name], 'page': page, 'label': p0.label, 'tup': p0.tupletName}]


def _stack_rows():
    t = host().op('px_stack')
    if t is None or t.numRows < 2:
        return []
    try:
        cols = [t[0, c].val for c in range(t.numCols)]
        return [dict((cols[c], t[r, c].val) for c in range(t.numCols)) for r in range(1, t.numRows)]
    except Exception:
        return []


def _inactive_pages():
    """Pages of modules that are off (PX_pointfx: px_stack rows with enabled 0). No reliable signal = none."""
    return L.stack_inactive(_stack_rows())


def _uid_ok():
    """-> f(par name): False for an M<uid> par whose uid no longer holds the type the essentials assumed
    (zk_cfg 'uidtypes' = PX's DEFAULT_STACK)."""
    exp = {}
    for part in _cfg('uidtypes', '').split():
        if ':' in part:
            k, t = part.split(':', 1)
            if k.isdigit():
                exp[int(k)] = t
    cur = L.stack_types(_stack_rows()) if exp else {}
    return lambda n: L.uid_par_ok(n, exp, cur)


def _note(key, notes):
    """Runtime notes into zk_cfg (written only when they change)."""
    v = '; '.join(sorted(set(notes)))
    if _cfg(key, '') != v and P.op('zk_cfg') is not None:
        _setcfg(key, v)


def _macros():
    """zk_cfg 'macros' (json, written by the builder from builders/zk_essentials.json) -> [{name, label, drives}]."""
    if S.get('macros') is None:
        try:
            m = json.loads(_cfg('macros', '') or '[]')
        except ValueError:
            m = []
        h = host()
        S['macros'] = [x for x in m if isinstance(x, dict) and getattr(h.par, str(x.get('name')), None) is not None]
    return S['macros']


def _drive(par):
    """A macro par changed: set each driven par linearly from -> to (only on the macro's own change, so a driven
    par moved by hand is not fought). A change the kit itself made while applying a preset / random / morph is
    skipped (those carry the driven pars' own values)."""
    q = S.setdefault('mq', {})
    n = par.name
    if n in q:
        v = q.pop(n)
        try:
            if abs(float(par.eval()) - float(v)) < 1e-9:
                return
        except (TypeError, ValueError):
            pass
    mc = next((x for x in _macros() if x['name'] == n), None)
    if mc is None:
        return
    u = float(par.eval())
    h = host()
    ok = S.get('uid_ok') or _uid_ok()
    for d in mc['drives']:
        p = getattr(h.par, d['par'], None)
        if p is None or p.readOnly or not ok(d['par']):   # missing / module changed: skipped (noted at Rebuild)
            continue
        v = L.macro_value(u, d, p.style)
        if p.style == 'Menu':
            v = max(0, min(len(p.menuNames) - 1, int(v)))
        _write_par(d['par'], v)


def _collect():
    h = host()
    items, groups = {}, []
    off = _inactive_pages()
    S['switches'] = set()
    for pg in _pages():
        if pg.name in off:                       # a module that is off: its page is not shown (comes back when on)
            continue
        ids = []
        tups = list(pg.parTuplets)
        if tups and L.is_page_switch(tups[0][0].style, tups[0][0].name):
            S['switches'].add(tups[0][0].name)   # a page's feature switch: while off, only the switch shows
            if not tups[0][0].eval():
                tups = tups[:1]
        for tup in tups:
            for it in _item_from_tuplet(tup, pg.name):
                pr = props(it['id'])
                if pr['hidden']:
                    continue
                par = getattr(h.par, it['pars'][0])
                it['kind'] = pr['ktype'] if pr['ktype'] in L.ktype_choices(it['base']) else it['base']
                # a static Menu keeps its items for the knob; a StrMenu (dropdown) reads them only when its list
                # opens (a menuSource is evaluated on every read, and items cached here went stale)
                it['menu'] = list(par.menuNames) if it['base'] == 'menu' else []
                it['menul'] = list(par.menuLabels) if it['base'] == 'menu' else []
                lo, hi = (par.normMin, par.normMax) if it['base'] in ('knob', 'int') else (0.0, 1.0)
                it['lo'] = pr['min'] if pr['min'] is not None else lo
                it['hi'] = pr['max'] if pr['max'] is not None else hi
                it['pr'] = pr
                items[it['id']] = it
                ids.append(it['id'])
        if ids:
            groups.append((pg.name, ids))
    # Main tab: the COMP's essentials (zk_cfg 'main', from builders/zk_essentials.json) + its macros; no entry =
    # the first controls of the first page
    S['macros'] = None
    ok = _uid_ok()
    allnames = [x for x in _cfg('main', '').split() if x]
    names = [x for x in allnames if ok(x)]
    notes = ['main: %s skipped (its module is not the one the essentials assume)' % x for x in allnames
             if x not in names]
    for mc in _macros():
        notes += ['macro %s: %s skipped (module changed)' % (mc['name'], d['par']) for d in mc['drives']
                  if not ok(d['par'])]
    _note('rt_notes', notes)
    S['uid_ok'] = ok
    main = L.resolve_main(names, [(i, items[i]['pars'], items[i].get('tup')) for _g, ids in groups for i in ids]) \
        if names else L.main_fallback(groups)
    for mc in _macros():
        p = getattr(h.par, mc['name'])
        pr = props(mc['name'])
        if pr['hidden']:
            continue
        items[mc['name']] = {'id': mc['name'], 'base': 'knob', 'kind': 'knob', 'pars': [mc['name']], 'page': 'Zkit',
                             'label': mc.get('label') or p.label, 'tup': mc['name'], 'menu': [], 'menul': [],
                             'lo': 0.0, 'hi': 1.0, 'pr': pr}
        main.append(mc['name'])
    allids = [i for _g, ids in groups for i in ids]
    S['main'] = main if (main and (set(main) != set(allids) or len(groups) > 1)) else []
    return items, groups


def Rebuild():
    """Re-read the host's pars, lay the panel out, draw. Safe any time (changes only table/par values)."""
    h = host()
    if h is None:
        return 'no target'
    items, groups = _collect()
    S['items'] = items
    S['groups'] = groups
    S['gl'] = [('_g:' + gname, gname, [(i, items[i]['pr']['size'], 2 if items[i]['kind'] in WIDE else 1)
                                       for i in ids]) for gname, ids in groups]
    S['popup'] = S['popup'] if (S['popup'] and S['popup'] in items) else None
    if S['drop'] is not None and S['drop']['id'] not in items:
        _close_drop()
    S['has_hot'] = all(P.op('zk_hot%d' % k) is not None and P.op('zk_hs%d' % k) is not None for k in range(NHOT))
    return _relayout()


WIDE = ('string', 'dropdown')       # two cells wide (text fields)
BAR = [('_plus', 'plus')] + [('_p%d' % k, 'slot') for k in range(1, SLOTS + 1)] + [('_gap', 'gap'), ('_rand', 'rand'),
                                                                                    ('_theme', 'theme')]


def _screen():
    """Screen size in panel px (points): zk_cfg 'screen' (the builder writes it), else the primary monitor."""
    s = _cfg('screen', '').split()
    if len(s) == 2:
        try:
            return (int(float(s[0])), int(float(s[1])))
        except ValueError:
            pass
    try:
        mo = [x for x in monitors if x.isPrimary] or list(monitors)
        return (int(mo[0].scaledWidth), int(mo[0].scaledHeight))
    except Exception:
        return None


def _relayout():
    """Lay out the current tab inside the viewport cap (no re-read of the host's pars: a tab switch comes here)."""
    items = S['items']
    d = int(_hostnum('Zkd', int(_cfg('d', '56') or 56)))
    cols = int(_hostnum('Zkcols', int(_cfg('cols', '8') or 8)))
    collapsed = [s for s in _cfg('collapsed', '').split(',') if s]
    cap = L.viewport_cap(int(_hostnum('Zkmaxh', 0) or 0), _screen())
    main = None
    if S.get('main'):
        main = ('_g:Main', 'Main', [(i, items[i]['pr']['size'], 2 if items[i]['kind'] in WIDE else 1)
                                    for i in S['main']])
    lay = L.layout_view(S['gl'], d=d, cols_max=cols, collapsed=collapsed, bar_items=BAR, tab=_cfg('tab', '') or None,
                        cap=cap, measure=_tw, tabs=_cfg('tabs', '1') != '0', main=main)
    S['lay'] = lay
    v = lay['view']
    allitems = lay['all']['items']
    S['order'] = [i for _g, ids in S['groups'] for i in ids if i in allitems]     # presets / random: every page
    S['order'] += [i for i in S.get('main') or [] if i not in S['order']]         # + the macros
    if v['tab'] == L.MAIN_TAB:
        S['draw'] = [i for i in S['main'] if i in lay['items']]
    else:
        S['draw'] = [i for _g, ids in S['groups'] for i in ids if i in lay['items']]  # this tab
    S['scrolls'] = L.scroll_cfg_load(_cfg('scroll', ''))
    S['scroll'] = L.clamp_scroll(S['scrolls'].get(v['tab'], 0), v['smax'])
    S['gen'] += 1                    # every cached draw segment / menu geometry is stale now
    S['segs'], S['seglist'], S['mgeom'], S['stored'] = {}, None, None, None
    S['hgrid'] = L.hit_grid(lay['items'])
    S['pmap'] = dict((n, items[i]) for i in S['order'] for n in items[i]['pars'])
    S['hot'] = [i if i in lay['items'] else None for i in S['hot']]
    S['vis_key'] = None
    Render()
    return '%d knobs, %dx%d view of %dx%d (tab %s)' % (len(S['order']), v['W'], v['H'], lay['w'], lay['h'], v['tab'])


def SetTab(name):
    """Show one page (or 'All'); remembered in zk_cfg 'tab'."""
    if S['lay'] is None:
        Rebuild()
    _setcfg('tab', name)
    S['popup'] = None
    _close_drop()
    _relayout()


def ScrollTo(px):
    """Scroll the current tab to px (clamped); kept per tab in zk_cfg 'scroll'."""
    lay = S['lay']
    if lay is None:
        Rebuild()
        lay = S['lay']
    v = lay['view']
    s = L.clamp_scroll(px, v['smax'])
    if s == S.get('scroll', 0):
        return s
    S['scroll'] = s
    had_popup = S['popup'] is not None or S['drop'] is not None
    S['popup'] = None                # the properties menu / a dropdown list sits at its knob: close, not float
    _close_drop()
    S['mgeom'] = None
    S['scrolls'][v['tab']] = s
    _setcfg('scroll', L.scroll_cfg_dump(S['scrolls']))
    Gl = S['G_last']
    if not had_popup and S['seglist'] is not None and S.get('win') is not None and Gl is not None and \
            Gl[0] == S['gen'] and Gl[2] == v['H'] and L.in_window(S['win'], v, s):
        # inside the stage band: only the scroll uniform and the thumb change (no knob, text or tile rewrite)
        if _scroll_fast(lay, v, s):
            return s
        th = L.THEMES[Gl[3]]
        _seg_head(Gl, lay, lay['m'], th, S['hover'])
        _assemble(S['seglist'], None, Gl[1], Gl[2], th, Gl[3])
        return s
    Render()
    return s


def _window():
    """The stage band (L.stage_window): kept while the viewport stays inside it; new one when it leaves."""
    lay = S['lay']
    v = lay['view']
    w = S.get('win')
    if w is not None and S.get('win_gen') == S['gen'] and L.in_window(w, v, S['scroll']):
        return w
    items, draw = lay['items'], S['draw']

    def n_in(lo, hi):
        return sum(1 for i in draw if items[i][1] + items[i][3] > lo and items[i][1] < hi)
    w = L.stage_window(v, S['scroll'], lay['h'], n_in, L.MAX_INST - 120)
    S['win'], S['win_gen'] = w, S['gen']
    return w


def _visible():
    """Knob ids of this tab inside the stage band (= the viewport plus a margin; cached per band)."""
    w = _window()
    key = (S['gen'], w)
    if S.get('vis_key') != key:
        S['vis_key'] = key
        lay = S['lay']
        if lay['view']['overflow']:
            items = lay['items']
            S['vis'] = [i for i in S['draw'] if items[i][1] + items[i][3] > w[1] and items[i][1] < w[2]]
        else:
            S['vis'] = [i for i in S['draw'] if i in lay['items']]
        S['visset'] = set(S['vis'])
    return S['vis']


# ---------------------------------------------------------------- values
def _par(name):
    return getattr(host().par, name)


def raw_of(it):
    """Current raw value(s) of an item: float/int/bool/menu index/str or a 3-list for swatches."""
    if it['base'] == 'swatch':
        return [_par(n).eval() for n in it['pars']]
    p = _par(it['pars'][0])
    if it['base'] == 'menu':
        return p.menuIndex
    if it['base'] in ('toggle', 'momentary'):
        return bool(p.eval())
    if it['base'] == 'pulse':
        return False
    return p.eval()


def u_of(it, raw=None):
    raw = raw_of(it) if raw is None else raw
    k = it['kind']
    if it['base'] == 'swatch':
        return max(raw) if raw else 0.0
    if it['base'] == 'menu':
        return L.from_par(raw, 'menu', 0, 0, len(it['menu']))
    if it['base'] in ('toggle', 'momentary', 'pulse'):
        return 1.0 if raw else 0.0
    if it['base'] in WIDE:
        return 0.0
    if k in ('toggle', 'momentary'):                # float/int knob shown as a toggle (knob type row)
        return 1.0 if L.norm(raw, it['lo'], it['hi']) >= 0.5 else 0.0
    return L.norm(raw, it['lo'], it['hi'])


def _write_par(name, v):
    p = _par(name)
    if p.mode != ParMode.CONSTANT:                  # expression/export/bind: do not fight it (two-way bind stays)
        if p.mode == ParMode.BIND:
            p.val = v
        return
    if p.isMenu and isinstance(v, int) and not isinstance(v, bool):
        p.menuIndex = v
    else:
        p.val = v


def write_raw(it, raw, smooth=True):
    """Write a raw value to the item's par(s); with the item's filter > 0 numeric writes glide (zk_tick)."""
    tau = it['pr']['filter']
    if smooth and tau > 0 and it['base'] in ('knob', 'int', 'swatch'):
        vals = raw if isinstance(raw, (list, tuple)) else [raw]
        for n, v in zip(it['pars'], vals):
            S['pending'][n] = (float(v), tau, it['base'] == 'int')
        P.op('zk_tick').par.active = True
        return
    if it['base'] == 'swatch':
        for n, v in zip(it['pars'], raw):
            _write_par(n, float(v))
        return
    _write_par(it['pars'][0], raw)


def write_u(it, u):
    k = it['kind']
    if k in ('toggle', 'momentary') and it['base'] in ('knob', 'int'):
        write_raw(it, it['hi'] if u >= 0.5 else it['lo'], smooth=False)
        return
    if it['base'] == 'menu':
        write_raw(it, L.to_par(u, 'menu', 0, 0, len(it['menu'])), smooth=False)
        return
    write_raw(it, L.to_par(u, it['base'], it['lo'], it['hi']))


def Tick():
    """zk_tick onFrameStart while filtered writes are pending."""
    dt = 1.0 / max(1.0, float(project.cookRate))
    done = []
    for n, (tgt, tau, isint) in list(S['pending'].items()):
        p = _par(n)
        cur = float(p.eval())
        nv = L.filter_step(cur, tgt, dt, tau)
        if abs(nv - tgt) < 1e-4 * max(1.0, abs(tgt)):
            nv = tgt
            done.append(n)
        _write_par(n, int(round(nv)) if isint else nv)
    ids = set(S['pmap'][n]['id'] for n in S['pending'] if n in S['pmap'])
    for n in done:
        S['pending'].pop(n, None)
    if not S['pending']:
        P.op('zk_tick').par.active = False
    if len(ids) <= NHOT:
        for iid in ids:
            _hot(iid)
    Render(only=ids)


# ---------------------------------------------------------------- snapshots / presets / randomise
def _ensure():
    """Right after a panel build the deferred Rebuild has not run yet (items / pmap empty): a Recall / Store then did
    nothing (T-157). Build the map now when it is empty."""
    if not S['pmap'] and host() is not None:
        Rebuild()


def snapshot(recall_only=False):
    _ensure()
    vals, kinds, specs = {}, {}, {}
    for iid in S['order']:
        it = S['items'][iid]
        if it['base'] in ('pulse', 'momentary'):
            continue
        if recall_only and not it['pr']['recall']:
            continue
        raw = raw_of(it)
        if it['base'] == 'swatch':
            for n, v in zip(it['pars'], raw):
                vals[n], kinds[n], specs[n] = v, 'knob', ('knob', 0.0, 1.0, 0)
            continue
        n = it['pars'][0]
        vals[n] = raw
        kinds[n] = {'knob': 'knob', 'int': 'int', 'menu': 'menu', 'toggle': 'toggle'}.get(it['base'], 'string')
        if it['base'] in ('knob', 'int', 'menu', 'toggle'):
            specs[n] = (kinds[n], it['lo'], it['hi'], len(it['menu']))
    return vals, kinds, specs


def _par_item():
    """par name -> item, for the drawn items (cached at Rebuild; built on first use if still empty, T-157)."""
    _ensure()
    return S['pmap']


def apply_values(vals, recall_only=True):
    pm = _par_item()
    q = S.setdefault('mq', {})
    for n, v in vals.items():
        it = pm.get(n)
        if it is None or (recall_only and not it['pr']['recall']):
            continue
        if n.startswith('Zkm') and abs(float(_par(n).eval()) - float(v)) > 1e-9:
            q[n] = float(v)          # a macro set by a preset / random / morph: its driven pars come from vals too
        if it['base'] == 'menu':
            _write_par(n, int(v))
        elif it['base'] == 'dropdown':
            if isinstance(v, str):   # presets store the text; an index from an older preset is not applied
                _write_par(n, v)
        elif it['base'] == 'int':
            _write_par(n, int(round(float(v))))
        elif it['base'] == 'toggle':
            _write_par(n, bool(v))
        elif it['base'] in ('knob', 'swatch'):
            _write_par(n, float(v))
        else:
            _write_par(n, v)


def _ptable():
    return _hdr(P.op('zk_presets'), ['slot', 'name', 'color', 'data'])


def preset(slot):
    t = _ptable()
    r = t.row(str(slot))
    return L.preset_load(t[str(slot), 'data'].val) if r is not None else None


def stored_slots():
    t = _ptable()
    return set(int(t[i, 0].val) for i in range(1, t.numRows) if t[i, 'data'].val)


def Store(slot=None):
    if slot is None:
        slot = L.next_free_slot(stored_slots(), SLOTS)
        if slot is None:
            return None
    vals, _k, _s = snapshot(recall_only=True)
    t = _ptable()
    if t.row(str(slot)) is None:
        t.appendRow([slot, 'p%d' % slot, L.DEFAULT_COLOR, ''])
    t[str(slot), 'data'] = L.preset_dump(vals)
    S['stored'] = None
    Render()
    return slot


def Recall(slot):
    v = preset(slot)
    if v:
        apply_values(v)
    Render()
    return bool(v)


def DeletePreset(slot):
    t = _ptable()
    if t.row(str(slot)) is not None:
        t.deleteRow(str(slot))
    S['stored'] = None
    Render()


def Randomize(amount=None):
    a = _hostnum('Zkrandamount', 0.5) if amount is None else amount
    vals, kinds, specs = snapshot()
    locks = [n for n, it in _par_item().items() if not it['pr']['recall']]
    apply_values(L.randomise(vals, specs, a, S['rng'], locks), recall_only=True)
    Render()


# ---------------------------------------------------------------- properties menu
def _menu_geom():
    """Properties menu / dropdown list geometry (cached per popup + layout generation: _hit runs on every mouse
    move)."""
    dr = S['drop']
    key = (S['popup'], (dr['id'], dr['off'], len(dr['names'])) if dr else None, S['gen'], S['scroll'])
    mg = S['mgeom']
    if mg is not None and mg[0] == key:
        return mg[1]
    g = _menu_geom_calc()
    S['mgeom'] = (key, g)
    return g


def _menu_geom_calc():
    iid = S['popup']
    if iid is None and S['drop'] is not None:
        return _drop_geom_calc()
    if iid is None or iid not in S['lay']['items']:
        return None
    it = S['items'][iid]
    d = S['lay']['m']['d']
    rh = max(16, int(round(d * 0.30)))
    w = max(210, int(round(d * 3.9)))
    rows = L.menu_rows(it['kind'] if it['base'] in ('knob', 'int') else it['base'])
    v = S['lay']['view']
    pw, ph = v['W'], min(L.TEX_CAP, max(v['H'], (len(rows) + 1) * rh + 8))
    ax, ay, aw, ah = S['lay']['items'][iid]
    box = L.popup_rect((ax, ay - S['scroll'], aw, ah), len(rows), rh, w, pw, ph)   # view px: beside the knob
    return {'box': box, 'rh': rh, 'rows': rows, 'it': it, 'ph': ph, 'type': 'props'}


# ---------------------------------------------------------------- dropdown fields (StrMenu, 28 Oct)
# A StrMenu (a name field, often with a live menuSource: presets, module Sel, effectors, '+ name / - word' helpers)
# is a text field with a pop-up list. The list's items are read from the par when it opens (menuNames /
# menuLabels evaluate the menuSource then), never at panel build; a pick writes the item's NAME (the helper items'
# names already hold the whole new text). Alt+click (or the list's header row) types a value instead.
def _drop_font(rh):
    return max(7.0, rh * 0.55)


def _drop_geom_calc():
    dr = S['drop']
    iid = dr['id']
    lay = S['lay']
    if iid not in lay['items']:
        return None
    it = S['items'][iid]
    d = lay['m']['d']
    rh = max(16, int(round(d * 0.30)))
    f = _drop_font(rh)
    labs = dr['labels'] or ['(no items)']
    want = max(_tw(x, f) for x in labs[:400]) + 44          # widest label (cached widths) + pads + scrollbar
    v = lay['view']
    ax, ay, aw, ah = lay['items'][iid]
    top = v['hdr']                   # never over the presets bar / tabs
    g = L.drop_geom((ax, ay - S['scroll'], aw, ah), len(dr['names']), rh, want, v['W'] - v['gutter'], v['H'], top)
    g.update({'it': it, 'ph': v['H'], 'type': 'drop', 'f': f})
    return g


def _open_drop(it):
    """Read the CURRENT items (menuSource evaluated now) and open the list under the field."""
    p = _par(it['pars'][0])
    try:
        names = [str(x) for x in p.menuNames]
        labels = [str(x) for x in p.menuLabels]
    except Exception:
        names, labels = [], []
    labels = [labels[k] if k < len(labels) and labels[k].strip() else names[k] for k in range(len(names))]
    S['popup'] = None
    S['drop'] = {'id': it['id'], 'names': names, 'labels': labels, 'off': 0}
    S['mgeom'] = None
    g = _menu_geom()
    cur = str(p.eval())
    ci = names.index(cur) if cur in names else None
    if g is not None:
        S['drop']['off'] = L.drop_start(ci, len(names), g['nvis'])
    P.op('zk_keys').par.active = True           # Esc closes the list
    S['mgeom'] = None


def _close_drop():
    if S['drop'] is None:
        return False
    S['drop'] = None
    S['mgeom'] = None
    if S['edit'] is None and P.op('zk_keys') is not None:
        P.op('zk_keys').par.active = False
    return True


def _start_typing(it):
    """Type a value into a text / dropdown field (starts from the current text; Enter commits, Esc cancels)."""
    _close_drop()
    raw = raw_of(it)
    S['edit'] = {'id': it['id'], 'row': None, 'buf': str(raw).strip() if it['base'] == 'dropdown' else ''}
    P.op('zk_keys').par.active = True


def _drop_pick(i):
    dr = S['drop']
    it = S['items'].get(dr['id'])
    if it is not None and 0 <= i < len(dr['names']):
        _write_par(it['pars'][0], dr['names'][i])
    _close_drop()


def _overlay():
    """What is open over the knobs (properties menu id, or the dropdown marker), for the render fast path."""
    if S['popup'] is not None:
        return S['popup']
    dr = S['drop']
    return ('_d', dr['id'], dr['off']) if dr is not None else None


def _row_value(it, key):
    pr = it['pr']
    if key == 'ktype':
        return it['kind'] if it['kind'] != 'knob' else 'float'
    if key in ('sens', 'size', 'filter'):
        return L.fmt4(pr[key])
    if key in ('min', 'max'):
        return L.fmt4(it['lo'] if key == 'min' else it['hi'])
    if key == 'label':
        return pr['label'] or it['label'].lower()
    if key == 'chan':
        return ' '.join(it['pars'])
    if key == 'midi':
        return 'td_midi_learn'
    if key == 'savelayout':
        return ''
    return ''


def _menu_click(key, sub=None):
    g = _menu_geom()
    it = g['it']
    iid = it['id']
    pr = it['pr']
    if key == 'ktype':
        ch = L.ktype_choices(it['base'])
        setprop(iid, 'ktype', ch[(ch.index(it['kind']) + 1) % len(ch)] if it['kind'] in ch else ch[0])
    elif key in ('recall', 'clampmin', 'clampmax', 'showvalue'):
        setprop(iid, key, 0 if pr[key] else 1)
    elif key == 'color' and sub is not None:
        setprop(iid, 'color', int(sub))
    elif key in ('sens', 'min', 'max', 'filter', 'size', 'label'):
        S['edit'] = {'id': iid, 'row': key, 'buf': ''}
        P.op('zk_keys').par.active = True
    elif key == 'showop':
        try:
            host().openParameters()
        except Exception:
            pass
    elif key == 'setdefault':
        setprop(iid, 'default', raw_of(it))
    elif key == 'delete':
        setprop(iid, 'hidden', 1)
        S['popup'] = None
    Rebuild()


# ---------------------------------------------------------------- typing
def _commit_edit():
    e = S['edit']
    S['edit'] = None
    P.op('zk_keys').par.active = False
    if e is None:
        return
    it = S['items'].get(e['id'])
    if it is None:
        return
    buf = e['buf']
    if e['row'] is None:
        if it['base'] in WIDE:
            write_raw(it, buf, smooth=False)
            return
        v = L.parse_typed(buf, it['base'] if it['base'] != 'knob' else 'knob', it['menu'])
        if v is None:
            return
        if it['base'] in ('knob', 'int'):
            v = L.clamp_typed(v, it['lo'], it['hi'], it['pr']['clampmin'], it['pr']['clampmax'])
            v = int(round(v)) if it['base'] == 'int' else v
        write_raw(it, v, smooth=False)
        return
    key = e['row']
    if key == 'label':
        setprop(it['id'], 'label', buf)
        return
    v = L.parse_typed(buf)
    if v is None:
        return
    if key in L.NUM_LIMITS:
        lo, hi = L.NUM_LIMITS[key]
        v = max(lo, min(hi, v))
    setprop(it['id'], key, v)


def Key(info):
    """zk_keys callback (only active while typing or while a dropdown list is open: Esc closes it)."""
    if S['edit'] is None and S['drop'] is not None:
        if info.state and str(info.key).lower() in ('esc', 'escape'):
            _close_drop()
            Render()
        return
    if S['edit'] is None or not info.state:
        return
    k = info.key
    code = {'enter': 13, 'return': 13, 'esc': 27, 'escape': 27, 'backspace': 8, 'delete': 127}.get(k)
    if code is None:
        ch = info.character or ''
        if len(ch) != 1:
            return
        code = ord(ch)
    e = S['edit']
    it = S['items'].get(e['id'])
    free = e['row'] == 'label' or (e['row'] is None and it is not None and it['base'] in WIDE)
    buf, act = L.type_key(e['buf'], code, free=free)      # text / name fields take spaces, '#', '*', '/' too
    if act == 'commit':
        _commit_edit()
        Rebuild()
        return
    if act == 'cancel':
        S['edit'] = None
        P.op('zk_keys').par.active = False
    else:
        S['edit']['buf'] = buf
    Render(only=())                  # the edited knob comes from the UI state; a properties-menu row: full


# ---------------------------------------------------------------- mouse
def _pos():
    pn = P.panel
    w, h = float(P.par.w.eval()), float(P.par.h.eval())
    return float(pn.u) * w, (1.0 - float(pn.v)) * h


def _mods():
    pn = P.panel
    return bool(pn.shift), bool(pn.ctrl or pn.cmd), bool(pn.alt)


def _hit(x, y):
    g = _menu_geom()
    if g is not None and g['type'] == 'drop':
        k = L.drop_hit(g, x, y, S['drop']['off'])
        if k is not None:
            return ('_d', k, None)
    elif g is not None:
        bx, by, bw, bh = g['box']
        if bx <= x < bx + bw and by <= y < by + bh:
            k = int((y - by) // g['rh']) - 1
            if k < 0:
                return ('_m', None, None)
            key = g['rows'][k][0]
            if key == 'color':
                vx = bx + bw * 0.47
                if x >= vx:
                    i = int((x - vx) // (g['rh'] * 1.0))
                    return ('_m', key, i if 0 <= i < len(L.PALETTE) else None)
            return ('_m', key, None)
    lay = S['lay']
    zone, x, y = L.where(lay['view'], x, y, S['scroll'])     # view px -> content px (header items do not scroll)
    if zone == 'sbar':
        return ('item', '_sb', None)
    if S['hgrid'] is None:
        S['hgrid'] = L.hit_grid(lay['items'])
    iid = L.hit_fast(S['hgrid'], lay['items'], x, y)
    if iid is not None:
        return ('item', iid, None)
    if zone == 'content':
        for gid, (gx, gy, gw, gh, _c) in lay['groups'].items():
            if gx <= x < gx + gw and gy <= y < gy + lay['m']['head']:
                return ('group', gid, None)
    return (None, None, None)


def _bar_kind(iid):
    return 'plus' if iid == '_plus' else 'rand' if iid == '_rand' else 'theme' if iid == '_theme' else \
        'slot' if iid.startswith('_p') else 'tab' if iid.startswith('_t:') else 'sbar' if iid == '_sb' else None


def OnPanel(name, val, prev):
    if S['lay'] is None:
        Rebuild()
    elif S['dirty']:                 # values changed while the window was closed
        S['dirty'] = False
        Render()
    x, y = _pos()
    if name == 'lselect':
        if val and not prev:
            _press(x, y)
        elif not val and prev:
            _release(x, y)
    elif name == 'rselect' and val and not prev:
        _rpress(x, y)
    elif name == 'mselect' and val and not prev:
        _mpress(x, y)
    elif name in ('u', 'v'):
        if S['press'] is not None:
            _drag(x, y)
        else:
            h = _hit(x, y)
            hv = h[1] if h[0] in ('item', 'group') else ('_m:' + str(h[1]) if h[0] == '_m' else
                                                         ('_d:' + str(h[1]) if h[0] == '_d' else None))
            if hv != S['hover']:
                S['hover'] = hv
                Render(only=())          # old + new hover redraw (picked up from the UI state)
    elif name == 'wheel' and val:
        _wheel(x, y, 1 if float(val) > float(prev or 0) else -1)
    elif name == 'rollover' and not val:
        if _close_drop():            # leaving the panel = clicking outside the list
            Render()
        if S['edit'] is not None:    # leaving the panel = clicking away: commit the typed value
            _commit_edit()
            Rebuild()
        if S['hover'] is not None:
            S['hover'] = None
            Render()


def _press(x, y):
    kind, iid, sub = _hit(x, y)
    if S['edit'] is not None and not (kind == 'item' and S['edit']['id'] == iid and S['edit']['row'] is None):
        _commit_edit()
    if kind == '_m':
        if iid is not None:
            _menu_click(iid, sub)
        return
    if kind == '_d':                 # a row of the open dropdown list
        if iid == 'head':
            it = S['items'].get(S['drop']['id'])
            if it is not None:
                _start_typing(it)
        elif iid != 'pad':
            _drop_pick(iid)
        else:
            return
        Render()
        return
    if S['drop'] is not None:        # a click outside the list closes it (and does nothing else)
        _close_drop()
        Render()
        return
    if S['popup'] is not None:
        S['popup'] = None
        Render()
        if kind is None:
            return
    if kind == 'group':
        col = [s for s in _cfg('collapsed', '').split(',') if s]
        col = [s for s in col if s != iid] if iid in col else col + [iid]
        _setcfg('collapsed', ','.join(col))
        Rebuild()
        return
    if kind is None:
        return
    pr = {'id': iid, 'x0': x, 'y0': y, 't': absTime.seconds, 'moved': False}
    bk = _bar_kind(iid)
    if bk == 'sbar':
        v = S['lay']['view']
        t = L.thumb(v, S['scroll'], S['lay']['h'])
        if t is None:
            return
        if not (t[0] <= y < t[0] + t[1]):          # on the track: a page up / down toward the click
            page = max(1, v['H'] - v['hdr'] - S['lay']['m']['cellh'] // 2)
            ScrollTo(S['scroll'] + (page if y >= t[0] + t[1] else -page))
            return
        pr['s0'] = S['scroll']
    if bk is None:
        it = S['items'][iid]
        pr['u0'] = u_of(it)
        pr['raw0'] = raw_of(it)
        _hot(iid)
        if it['kind'] == 'momentary':
            write_u(it, 1.0)
        elif it['kind'] == 'pulse':
            _par(it['pars'][0]).pulse()
    elif bk == 'slot':
        slot = int(iid[2:])
        tgt = preset(slot)
        if tgt:
            pr['cap'] = snapshot()
            pr['tgt'] = tgt
    elif bk == 'rand':
        vals, kinds, specs = snapshot()
        locks = [n for n, it in _par_item().items() if not it['pr']['recall']]
        pr['cap'] = (vals, kinds, specs)
        pr['tgt'] = L.randomise(vals, specs, _hostnum('Zkrandamount', 0.5), S['rng'], locks)
    S['press'] = pr
    Render(only=())                  # press/edit/popup changes are picked up from the UI state (bar items: full)


def _drag(x, y):
    """Incremental drag: each move adds (pixels since the last move) x the modifier scale, so pressing Shift mid-drag
    slows from that point on instead of jumping."""
    pr = S['press']
    dx, dy = x - pr['x0'], y - pr['y0']
    if 's0' in pr:                   # scrollbar thumb: absolute, follows the pointer
        pr['moved'] = True
        ScrollTo(L.thumb_drag(S['lay']['view'], pr['s0'], dy, S['lay']['h']))
        return
    if not pr['moved'] and L.is_click(dx, dy):
        return
    if not pr['moved']:
        pr['moved'] = True
        pr['ylast'] = pr['y0']
    step_up = pr['ylast'] - y
    pr['ylast'] = y
    if step_up == 0:                 # a mouse move fires u and v separately: the u-only half changes nothing
        return
    iid = pr['id']
    bk = _bar_kind(iid)
    sh, ct, al = _mods()
    if bk is None:
        it = S['items'][iid]
        sens = 200.0 / max(0.01, it['pr']['sens'])
        if it['kind'] in ('knob', 'int', 'menu'):
            pr['ucur'] = L.drag_value(pr.get('ucur', pr['u0']), step_up, sens, sh, ct, al)
            u = pr['ucur']
            if it['kind'] != 'knob':
                u = L.quantize_u(u, it['kind'], it['lo'], it['hi'], len(it['menu']))
            write_u(it, u)
        elif it['base'] == 'swatch':
            pr['rgb'] = L.brightness_scale(pr.get('rgb', pr['raw0']), step_up * L.drag_scale(sh, ct, al), sens)
            write_raw(it, list(pr['rgb']))
        Render(only=(iid,))
    elif bk in ('slot', 'rand') and pr.get('tgt'):
        pr['tm'] = L.drag_value(max(0.0, pr.get('tm', 0.0)), step_up, 200.0, sh, ct, al)
        cap = pr['cap']
        apply_values(L.morph_values(cap[0], pr['tgt'], pr['tm'], cap[1]))
        Render()


def _release(x, y):
    pr = S['press']
    S['press'] = None
    if pr is None:
        return
    iid = pr['id']
    bk = _bar_kind(iid)
    click = not pr['moved']
    now = absTime.seconds
    if bk is None:
        it = S['items'].get(iid)
        if it is None:
            Render()
            return
        if it['kind'] == 'momentary':
            write_u(it, 0.0)
        elif click:
            dbl = L.is_double(S['last'][0], S['last'][1], now, iid)
            if dbl and it['kind'] in ('knob', 'int', 'menu', 'swatch', 'toggle'):
                # double click (vendor): toggle "recallable"; undo the first click's action
                S['edit'] = None
                P.op('zk_keys').par.active = False
                if it['kind'] == 'toggle':
                    write_u(it, 1.0 - u_of(it))
                elif it['kind'] == 'menu':
                    write_raw(it, pr['raw0'], smooth=False)
                setprop(iid, 'recall', 0 if it['pr']['recall'] else 1)
                S['last'] = (-1.0, None)
                Rebuild()
                return
            if it['kind'] == 'dropdown':
                if _mods()[2]:
                    _start_typing(it)          # Alt+click: type a value (any text: a new name, a pattern, a path)
                else:
                    _open_drop(it)
                S['last'] = (-1.0, None)
                Render()
                return
            if it['kind'] == 'toggle':
                write_u(it, 0.0 if u_of(it) >= 0.5 else 1.0)
            elif it['kind'] == 'menu':
                sh = _mods()[0]
                p = _par(it['pars'][0])
                if getattr(p, 'menuSource', ''):   # a Menu with a live source: its items as they are now
                    it['menu'], it['menul'] = list(p.menuNames), list(p.menuLabels)
                n = max(1, len(it['menu']))
                write_raw(it, (raw_of(it) + (-1 if sh else 1)) % n, smooth=False)
            elif it['kind'] in ('knob', 'int', 'string', 'swatch') and it['base'] != 'swatch':
                S['edit'] = {'id': iid, 'row': None, 'buf': ''}
                P.op('zk_keys').par.active = True
        S['last'] = (now, iid) if click else (-1.0, None)
    elif bk == 'plus':
        tgt = _hit(x, y)
        if not click and tgt[0] == 'item' and _bar_kind(tgt[1]) == 'slot':
            Store(int(tgt[1][2:]))                 # drag "+" onto a slot = store there
        elif click:
            Store()
    elif bk == 'slot':
        slot = int(iid[2:])
        if click:
            if _mods()[0] or not pr.get('tgt'):
                Store(slot)                        # empty slot or Shift+click = (over)write
            else:
                Recall(slot)                       # classic: instant recall
    elif bk == 'rand' and click and pr.get('tgt'):
        apply_values(pr['tgt'])
    elif bk == 'theme' and click:
        h = host()
        if getattr(h.par, 'Zktheme', None) is not None:
            h.par.Zktheme = 'night' if _theme() == 'day' else 'day'
    elif bk == 'tab' and click:
        SetTab(iid[3:])
        return
    Render(only=())                  # the released knob comes from the UI state; bar items (presets, rand): full


def _rpress(x, y):
    if _close_drop():
        Render()
        return
    kind, iid, _s = _hit(x, y)
    if kind == 'item' and _bar_kind(iid) == 'slot':
        DeletePreset(int(iid[2:]))
        return
    if kind == 'item' and _bar_kind(iid) is None:
        S['popup'] = None if S['popup'] == iid else iid
    else:
        S['popup'] = None
    Render()


def _mpress(x, y):
    kind, iid, _s = _hit(x, y)
    if kind != 'item' or _bar_kind(iid) is not None:
        return
    it = S['items'][iid]
    dv = it['pr']['default']
    if dv is None:
        if it['base'] == 'swatch':
            dv = [_par(n).default for n in it['pars']]
        else:
            p = _par(it['pars'][0])
            dv = p.menuNames.index(p.default) if (p.style == 'Menu' and p.default in p.menuNames) else p.default
    write_raw(it, dv, smooth=False)
    _hot(iid)
    Render(only=(iid,))


def _wheel(x, y, notch):
    """Over a knob: value step (Ctrl/Cmd = fine). Shift+wheel anywhere, or the wheel over anything else (empty space,
    group titles, the scrollbar, the header): scroll half a knob row per notch."""
    kind, iid, _s = _hit(x, y)
    if kind == '_m':
        return
    if kind == '_d':                 # over the open list: scroll its rows (never the value)
        dr = S['drop']
        g = _menu_geom()
        off = L.drop_off(dr['off'] - notch, len(dr['names']), g['nvis'])
        if off != dr['off']:
            dr['off'] = off
            Render()
        return
    if _close_drop():                # the wheel elsewhere: the list closes, the panel scrolls as usual
        Render()
    sh, ct, _al = _mods()
    it = S['items'].get(iid) if (kind == 'item' and _bar_kind(iid) is None) else None
    if sh or it is None or it['kind'] not in ('knob', 'int', 'menu'):
        v = S['lay']['view']
        if v['smax'] > 0:
            ScrollTo(L.wheel_scroll(S['scroll'], notch, v, max(12, S['lay']['m']['cellh'] // 2)))
        return
    u = L.wheel_value(u_of(it), notch, it['kind'], it['lo'], it['hi'], len(it['menu']), fine=ct)
    write_u(it, u)
    _hot(iid)
    Render(only=(iid,))


# ---------------------------------------------------------------- sync (host par changed anywhere)
def Sync(par):
    n = par.name
    if par.owner != host():
        return
    if n in ('Zkd', 'Zkcols', 'Zkmaxh'):
        Rebuild()
        return
    if n == 'Opencontrols':
        return
    if n.startswith('Zkm'):          # a macro: drive its pars (also while the window is closed)
        _drive(par)
    if n in S.get('switches', ()):   # a page's feature switch: that page shows more / less
        if _shown():
            Rebuild()
        else:
            S['lay'] = None          # rebuilt on the next open / mouse event
        return
    if not _shown():                 # nobody sees the panel: draw on open / the next mouse event, not every change
        S['dirty'] = True            # (a par that moves every frame, e.g. a playhead, cost ~1.4 ms Python per frame)
        return
    S['sync_names'].add(n)           # Flush redraws only these pars' knobs (and skips the kit's own echoes)
    if not S['flush']:
        S['flush'] = True
        run("args[0].module.Flush()", me, delayFrames=1, delayRef=op.TDResources)


def _shown():
    """False only when the COMP's controls_window exists and is closed (the panel then is not on screen)."""
    h = host()
    w = h.op('controls_window') if h is not None else None
    return w is None or w.OPType != 'windowCOMP' or bool(w.isOpen)


def Flush():
    S['flush'] = False
    names, S['sync_names'] = S['sync_names'], set()
    if S['dirty'] or 'Zktheme' in names:
        S['dirty'] = False
        Render()
        return
    pm = S['pmap']
    ids = set(pm[n]['id'] for n in names if n in pm)     # pars not on the panel draw nothing
    if len(ids) <= NHOT:
        for iid in ids:
            _hot(iid)
    Render(only=ids)                 # a knob whose value is already drawn (the kit's own write) is skipped by its sig


def StackChanged():
    """zk_watch (DAT Execute on the host's px_stack): a module turned on / off shows / hides its page."""
    if S['lay'] is None:
        return
    if _shown():
        Rebuild()
    else:
        S['lay'] = None


def Pulse(par):
    if par.owner != host():
        return
    if par.name == 'Opencontrols':
        w = host().op('controls_window')
        if w is not None:
            w.par.winopen.pulse()
        if S['dirty'] and not S['flush']:
            S['flush'] = True
            run("args[0].module.Flush()", me, delayFrames=1, delayRef=op.TDResources)
    elif par.name == 'Zkshowall':
        t = P.op('zk_props')
        for i in range(1, t.numRows):
            t[i, 'hidden'] = ''
        Rebuild()
    elif par.name == 'Zkrandomize':
        Randomize()
    elif par.name == 'Zkrebuild':
        Rebuild()


# ---------------------------------------------------------------- drawing
# Perf (docs/builds/zkit_perf.md): the panel is drawn from SEGMENTS (groups, presets bar, one per knob, properties
# menu). A knob's segment is rebuilt only when its signature changes (value, flags, typing buffer); mouse events and
# synced pars name the knobs they touched (Render(only=...)), the rest is reused as is. Tables get only changed cells;
# a knob being dragged / a par moving every frame draws its value text in a hot Text TOP (zk_hot0/1), so the big label
# buckets do not re-render; the face shader loops only over its 64 px tile's instances (zk_tiles).
def _tw(text, size):
    """Text width at a font size (cached; Text TOP measures at its own size 20)."""
    key = text
    w = S['tw'].get(key)
    if w is None:
        w = float(P.op('zk_measure').evalTextSize(text)[0]) if text else 0.0
        S['tw'][key] = w
    return w * max(float(size), MIN_FONT) / 20.0     # 31550: a Text TOP under ~9.6 px still draws ~9 px wide


def _hot(iid):
    """Give a knob's value text a hot Text TOP slot (least recently used one is reused)."""
    if not S.get('has_hot'):
        return
    S['clock'] += 1
    _k, changed = L.hot_take(S['hot'], S['hot_t'], iid, S['clock'])
    if changed:
        S['hot_ver'] += 1


class _Seg(object):
    """One draw segment: face instances (+ their cull boxes for the tile lists) and text rows."""
    __slots__ = ('sig', 'inst', 'cull', 'txt', 'cell', 'H', 'fixed', 'vc')

    def __init__(self, sig, H, cell=None, fixed=False):
        """fixed = drawn in view px (presets bar, tabs, scrollbar, menu); else content px, moved by the scroll."""
        self.sig, self.H, self.cell, self.fixed = sig, H, cell, fixed
        self.inst, self.cull, self.txt = [], [], []
        self.vc = None               # view copy at one scroll: (key, inst, cull, {j: local index})

    def _c(self, box):
        self.cull.append(tuple(box) if self.cell is None else L.union_box(box, self.cell))

    def add(self, box, c, r, u, kind, flags, rgb, zu=0.0, a1=0.0, a2=0.0):
        self.inst.append(tuple(round(float(v), 3) for v in (box[0], box[1], box[2], box[3], c[0], c[1], r, u,
                                                            L.RK[kind], flags, rgb[0], rgb[1], rgb[2], zu, a1, a2)))
        self._c(box)

    def text(self, x, y_base, s, size, rgb, alpha=1.0, layer=0, dyn=None):
        """dyn = the knob id when this is its value text (can move to a hot Text TOP)."""
        sz = round(size * 2.0) / 2.0
        tw = _tw(s, sz)
        box = (x - 1, y_base - sz * 1.15, tw * 1.12 + 4, sz * 1.55)
        li = len(self.inst)
        # field u of a tcol instance = which text input holds its pixels (bucket 0..7, hot 8..9), set at assembly
        self.inst.append(tuple(round(float(v), 3) for v in (box[0], box[1], box[2], box[3], x, y_base, 0, 0,
                                                            L.RK['tcol'], 0, rgb[0], rgb[1], rgb[2], 0, alpha, 0)))
        self._c(box)
        self.txt.append((round(x, 1), round(self.H - y_base, 1), s, sz, layer, y_base, dyn, li))

    def ctext(self, cx, y_base, s, size, rgb, alpha=1.0, dyn=None):
        self.text(L.text_x(cx, _tw(s, size)), y_base, s, size, rgb, alpha, dyn=dyn)


def _seg_groups(G, lay, m, hov):
    sig = (G, hov if hov in lay['groups'] else None)
    sg = S['segs'].get('_groups')
    if sg is not None and sg.sig == sig:
        return sg, False
    sg = _Seg(sig, G[2])
    for gid, (gx, gy, gw, gh, col) in lay['groups'].items():           # group frames + titles (surface blue, 7.3)
        fl = L.F_HOVER if hov == gid else 0
        sg.add((gx, gy, gw, gh), (gx, gy), m['head'] * 0.5, 0.0, 'group', fl, L.SURFACE_BLUE, a1=1.0 if col else 0.0)
        sg.text(gx + m['inset'], gy + m['head'] * 0.70, gid[3:].upper(), m['tfont'] * 0.92, L.SURFACE_BLUE)
    S['segs']['_groups'] = sg
    return sg, True


def _stored():
    if S['stored'] is None:
        stored = {}
        t = _ptable()
        for i in range(1, t.numRows):
            if t[i, 'data'].val:
                stored[int(t[i, 0].val)] = int(float(t[i, 'color'].val or L.DEFAULT_COLOR))
        S['stored'] = stored
    return S['stored']


def _seg_bar(G, lay, m, th, ui):
    hov, press = ui[0], S['press']
    stored = _stored()
    BK = ('plus', 'slot', 'rand', 'theme')
    pid = press['id'] if press is not None and _bar_kind(press['id']) in BK else None
    sig = (G, tuple(sorted(stored.items())), hov if (hov and _bar_kind(hov) in BK) else None, pid,
           press.get('tm', -1.0) if pid else None)
    sg = S['segs'].get('_bar')
    if sg is not None and sg.sig == sig:
        return sg, False
    sg = _Seg(sig, G[2], fixed=True)
    for iid, box in lay['items'].items():
        bk = _bar_kind(iid)
        if bk is None:
            continue
        x, y, w, h = box
        r = m['d'] * 0.36
        c = (x + w / 2.0, y + r + m['d'] * 0.08)
        act = press is not None and press['id'] == iid
        fl = (L.F_HOVER if hov == iid else 0) | (L.F_ACTIVE if act and bk != 'slot' else 0)
        lab_y = y + h - m['d'] * 0.12
        if bk == 'plus':
            sg.add(box, c, r, 0, 'plus', fl, L.PALETTE[L.DEFAULT_COLOR][1])
        elif bk == 'slot':
            k = int(iid[2:])
            st = k in stored
            rgb = L.PALETTE[stored.get(k, L.DEFAULT_COLOR)][1]
            tm = press.get('tm', -1.0) if (act and press) else -1.0
            sg.add(box, c, r, 0, 'slot', fl, rgb, a1=1.0 if st else 0.0, a2=tm)
            sg.ctext(c[0], lab_y, 'p%d' % k, m['font'] * 0.9, th['label'], 1.0 if st else 0.45)
        elif bk == 'rand':
            tm = press.get('tm', -1.0) if (act and press) else -1.0
            sg.add(box, c, r, 0, 'rand', fl, L.PALETTE[L.DEFAULT_COLOR][1], a2=tm)
            sg.ctext(c[0], lab_y, 'rand', m['font'] * 0.9, th['label'])
        elif bk == 'theme':
            day = G[3] == 'day'
            sg.add(box, c, r, 1.0 if day else 0.0, 'theme', fl, (1, 1, 1))
            sg.ctext(c[0], lab_y, 'day' if day else 'night', m['font'] * 0.9, th['label'])
    S['segs']['_bar'] = sg
    return sg, True


def _seg_knob(iid, G, lay, m, th, ui):
    """One knob: face instance + value text (dyn) + label. Rebuilt only when its signature changes."""
    hov, press, edit, popup = ui[0], S['press'], S['edit'], S['popup']
    it = S['items'][iid]
    raw = raw_of(it)
    u = u_of(it, raw)
    pr = it['pr']
    act = press is not None and press['id'] == iid
    fl = (L.F_HOVER if hov == iid else 0) | (L.F_ACTIVE if act else 0)
    dopen = S['drop'] is not None and S['drop']['id'] == iid
    fl |= L.F_SELECT if (popup == iid or (edit and edit['id'] == iid)) else 0
    fl |= 0 if pr['recall'] else L.F_LOCK
    k = it['kind']
    if it['base'] != 'swatch' and k in ('toggle', 'momentary') and u >= 0.5:
        fl |= L.F_ON
    ebuf = edit['buf'] if (edit and edit['id'] == iid and edit['row'] is None) else None
    sig = (G, tuple(raw) if isinstance(raw, list) else raw, fl, act, ebuf, dopen)
    sg = S['segs'].get(iid)
    if sg is not None and sg.sig == sig:
        return sg, False
    S['stats']['segs'] = S['stats'].get('segs', 0) + 1
    box = lay['items'][iid]
    s = lay['sizes'].get(iid, 1.0)
    x, y, w, h = box
    sg = _Seg(sig, G[2], cell=box)
    d = m['d'] * s
    r = d / 2.0
    c = (x + w / 2.0, y + m['top'] * s + r)
    rgb = L.PALETTE[max(0, min(len(L.PALETTE) - 1, pr['color']))][1]
    kd = k
    if it['base'] == 'swatch':
        kd = 'swatch'
        rgb = tuple(float(v) for v in raw)
    a1 = a2 = 0.0
    if k == 'menu':
        a1, a2 = L.menu_arc(raw, len(it['menu']))
    zu = L.zero_u(it['lo'], it['hi']) if k in ('knob', 'int') else 0.0
    if k == 'dropdown':
        kd = 'drop'
        a1 = 1.0 if dopen else 0.0
    if ebuf is not None:
        kd = 'field' if k in WIDE else kd
    sg.add(box, c, r, u, kd, fl, rgb, zu=zu, a1=a1, a2=a2)
    # value text inside the body (7.2), label below; label red when out of range (6.2)
    vf = max(7.0, m['d'] * 0.22 * s)
    lf = m['d'] * 0.205 * (1.0 + 0.15 * (s - 1.0))
    lit = (fl & L.F_ON) or (act and k in ('momentary', 'pulse'))
    vcol = (1.0, 1.0, 1.0) if (lit or act) else th['value']
    vs = None
    vx = c[0]
    if ebuf is not None:
        vs = ebuf + '_'
        if it['base'] in WIDE:       # long typed text: show its end (where the cursor is)
            vs = vs[-max(3, int(w * 0.85 / (vf * 0.52))):]
    elif it['base'] == 'dropdown':   # the current text, whole when it fits; room left for the triangle
        vs = str(raw).strip()
        vx = c[0] - r * 0.25
    elif pr['showvalue']:
        if it['base'] == 'menu':
            vs = str(it['menu'][raw]) if 0 <= raw < len(it['menu']) else str(raw)
        elif it['base'] in ('toggle', 'momentary'):
            vs = L.fmt4(raw, 'toggle')
        elif it['base'] == 'string':
            sv = str(raw)
            if _par(it['pars'][0]).style in ('File', 'Folder', 'FileSave') and '/' in sv.rstrip('/'):
                sv = sv.rstrip('/').rsplit('/', 1)[-1]     # a path: its file name says more than its start
            vs = sv[:max(3, int(w * 0.85 / (vf * 0.52)))]
        elif it['base'] in ('knob', 'int'):
            vs = L.fmt4(raw, 'int' if it['base'] == 'int' else 'knob')
    if vs:
        vf_ = vf
        if it['base'] == 'menu' and k == 'menu':       # item name whole when a smaller size holds it
            vs, vf_ = L.fit_label_size(vs, 2 * r * 0.84, vf, measure=_tw)
        elif it['base'] == 'dropdown' and ebuf is None:   # the value as it is (case, the op name whole)
            vs, vf_ = L.fit_value(vs, w * 0.80 - r * 0.9, vf, _tw)
        sg.ctext(vx, c[1] + vf_ * 0.48, vs, vf_, vcol, dyn=iid)
    lab, lf = L.fit_label_size(pr['label'] or it['label'], w, lf, measure=_tw)
    oor = it['base'] in ('knob', 'int') and L.out_of_range(raw, it['lo'], it['hi'])
    sg.ctext(c[0], y + h - m['d'] * 0.10 * s, lab, lf, L.RED if oor else th['label'])
    S['segs'][iid] = sg
    return sg, True


TAB_TEXT_ON = (0.07, 0.07, 0.08)     # label on the selected (blue) tab pill


def _seg_head(G, lay, m, th, hov):
    """Fixed header extras: the page tabs (zerror-style pills, selected = surface blue) and the scrollbar (track +
    thumb). None when there is nothing."""
    v = lay['view']
    tb = [(nm, lay['items'].get('_t:' + nm)) for nm in v['tabs']]
    th_ = L.thumb(v, S['scroll'], lay['h'])
    if not tb and not v['overflow']:
        S['segs'].pop('_head', None)
        return None, False
    press = S['press']
    pid = press['id'] if (press is not None and press['id'] == '_sb') else None
    hv = hov if (hov == '_sb' or (hov and str(hov).startswith('_t:'))) else None
    sig = (G, v['tab'], hv, pid, th_)
    sg = S['segs'].get('_head')
    if sg is not None and sg.sig == sig:
        return sg, False
    sg = _Seg(sig, G[2], fixed=True)
    tm = L.tab_metrics(m['d'])        # (the shader clips scrolled content under the header: no cover strip)
    for nm, b in tb:
        if b is None:
            continue
        on = nm == v['tab']
        fl = (L.F_ON if on else 0) | (L.F_HOVER if hov == '_t:' + nm else 0)
        x, y, w, h = b
        sg.add(b, (x + w / 2.0, y + h / 2.0), h / 2.0, 0, 'tab', fl, L.SURFACE_BLUE)
        sg.ctext(x + w / 2.0, y + h * 0.5 + tm['font'] * 0.42, nm.lower(), tm['font'], TAB_TEXT_ON if on else
                 th['label'])
    if th_ is not None:
        tr = v['track']
        fl = (L.F_HOVER if hov == '_sb' else 0) | (L.F_ACTIVE if pid else 0)
        sg.add(tr, (tr[0] + tr[2] / 2.0, th_[0]), th_[1], 0, 'sbar', fl, L.SURFACE_BLUE, a1=th_[0], a2=th_[1])
    S['segs']['_head'] = sg
    return sg, True


def _seg_popup(G, g, th, hov, edit):
    """Properties menu (7.0 #8): black header with the knob name, zebra rows, value column at 47 %. Not cached."""
    sg = _Seg(None, G[2], fixed=True)
    bx, by, bw, bh = g['box']
    rh = g['rh']
    it = g['it']
    f = max(7.0, rh * 0.55)
    sg.add((bx, by, bw, rh), (bx, by), 0, 0, 'row', 0, th['head'])
    sg.text(bx + 8, by + rh * 0.72, (it['pr']['label'] or it['label']).lower(), f, (0.92, 0.92, 0.92), layer=1)
    for k, (key, label, tint, rk) in enumerate(g['rows']):
        ry = by + (k + 1) * rh
        rcol = th['row0'] if k % 2 == 0 else th['row1']
        fl = L.F_HOVER if hov == '_m:' + key else 0
        if edit and edit['row'] == key:
            fl |= L.F_SELECT
        sg.add((bx, ry, bw, rh), (bx, ry), 0, 0, 'row', fl, rcol)
        lc = L.TINTS[tint] if tint else th['label']
        sg.text(bx + 8, ry + rh * 0.72, label, f, lc, layer=1)
        vx = bx + bw * 0.47
        cy = ry + rh / 2.0
        if rk == 'radio':
            on = it['pr'][key]
            sg.add((vx, ry, rh, rh), (vx + rh / 2.0, cy), rh * 0.5, 0, 'radio', L.F_ON if on else 0,
                   lc if tint else (0.85, 0.85, 0.85))
        elif rk == 'dots':
            for ci, (_nm, prgb) in enumerate(L.PALETTE):
                sg.add((vx + ci * rh, ry, rh, rh), (vx + ci * rh + rh / 2.0, cy), rh * 0.5, 0, 'dot',
                       L.F_ON if it['pr']['color'] == ci else 0, prgb)
        elif rk == 'layouts':
            for ci, lrgb in enumerate(((0.40, 0.78, 0.35), (0.33, 0.53, 0.90), (0.88, 0.25, 0.17))):
                sg.add((vx + ci * rh, ry, rh, rh), (vx + ci * rh + rh / 2.0, cy), rh * 0.5, 0, 'radio', 0,
                       tuple(v * 0.6 for v in lrgb))
        elif rk == 'action' and key == 'delete':
            sg.add((vx, ry, rh, rh), (vx + rh / 2.0, cy), rh * 0.5, 0, 'radio', 0, L.RED)
        vs = edit['buf'] + '_' if (edit and edit['row'] == key) else _row_value(it, key)
        if vs:
            sg.text(vx + (rh * 1.2 if rk in ('radio',) else 0), ry + rh * 0.72, vs, f,
                    th['value'] if th is L.THEMES['night'] else th['label'], layer=1)
    return sg


def _seg_drop(G, g, th, hov):
    """Dropdown pop-up list: header row (the par name, 'type...' = click to type), then the visible item rows
    (zebra, hover, the current value marked blue), a slim scrollbar when the list is longer than the room."""
    sg = _Seg(None, G[2], fixed=True)
    dr = S['drop']
    bx, by, bw, bh = g['box']
    rh, f = g['rh'], g['f']
    it = g['it']
    cur = str(_par(it['pars'][0]).eval())
    fl = L.F_HOVER if hov == '_d:head' else 0
    sg.add((bx, by, bw, rh), (bx, by), 0, 0, 'row', fl, th['head'])
    sg.text(bx + 8, by + rh * 0.72, (it['pr']['label'] or it['label']).lower(), f, (0.92, 0.92, 0.92), layer=1)
    hint = 'type...'
    sg.text(bx + bw - _tw(hint, f) - 10, by + rh * 0.72, hint, f, L.SURFACE_BLUE, layer=1)
    names, labels = dr['names'], dr['labels']
    tb = L.drop_thumb(g, dr['off'])
    tw_ = bw - 16 - (tb[2] + 4 if tb else 0)
    if not names:
        sg.add((bx, by + rh, bw, rh), (bx, by + rh), 0, 0, 'row', 0, th['row0'])
        sg.text(bx + 8, by + rh * 1.72, '(no items: alt+click to type)', f, th['label'], alpha=0.6, layer=1)
    for k in range(g['nvis']):
        i = dr['off'] + k
        if i >= len(names):
            break
        ry = by + (k + 1) * rh
        on = names[i] == cur
        rcol = L.SURFACE_DIM if on else (th['row0'] if i % 2 == 0 else th['row1'])
        sg.add((bx, ry, bw, rh), (bx, ry), 0, 0, 'row', L.F_HOVER if hov == '_d:%d' % i else 0, rcol)
        lab, lf = L.fit_value(labels[i], tw_, f, _tw)
        sg.text(bx + 8, ry + rh * 0.72, lab, lf, (1.0, 1.0, 1.0) if on else th['label'], layer=1)
    if tb is not None:
        tx, ty, tw, tht, yy, hh = tb
        sg.add((tx, ty, tw, tht), (tx + tw / 2.0, yy), hh, 0, 'sbar', 0, L.SURFACE_BLUE, a1=yy, a2=hh)
    return sg


def Render(only=None):
    """Draw the panel. only = ids of knobs whose VALUE changed (the caller knows); hover/press/typing/popup changes
    are found from the UI state. None = full pass (every segment checked by its signature, rebuilt if changed)."""
    lay = S['lay']
    if lay is None:                  # module state is lost whenever the DAT recompiles (project load, text refresh)
        if host() is not None and P.op('zk_gpu') is not None:
            Rebuild()
        return
    S['dirty'] = False
    theme = _theme()
    th = L.THEMES[theme]
    g = _menu_geom()
    v = lay['view']
    H = int(v['H'])                  # the VIEWPORT (T-231): never the content height
    if g is not None:
        H = max(H, int(g['ph']))
    H = min(H, L.TEX_CAP)
    W = min(int(v['W']), L.TEX_CAP)
    m = lay['m']
    G = (S['gen'], W, H, theme)
    press, edit, popup = S['press'], S['edit'], S['popup']
    ui = (S['hover'], press['id'] if press else None, edit['id'] if edit else None, _overlay())
    last = S['ui_last']
    S['ui_last'] = ui
    items = S['items']
    vis = _visible()
    changed = False
    if only is not None and last is not None and S['seglist'] is not None and G == S['G_last'] and \
            ui[3] is None and last[3] is None and S['win_last'] == S.get('win'):
        ids = set(only)
        for v_ in (ui[0], ui[1], ui[2], last[0], last[1], last[2]):
            if v_ is not None:
                ids.add(v_)
        if all(i in items for i in ids):
            for iid in ids:
                if iid in S['visset']:               # off-screen / other-tab / collapsed knobs are not drawn
                    changed = _seg_knob(iid, G, lay, m, th, ui)[1] or changed
            if not changed and S['asm_last'] == S['hot_ver']:
                return                               # nothing visible changed (e.g. the kit's own write echoing)
            _assemble(S['seglist'], g, W, H, th, theme)
            return
    seglist = []
    sg, c_ = _seg_groups(G, lay, m, ui[0])
    seglist.append('_groups')
    changed = changed or c_
    sg, c_ = _seg_bar(G, lay, m, th, ui)
    bar_at = len(seglist)
    seglist.append('_bar')
    changed = changed or c_
    for iid in vis:                  # cull by viewport: only knobs on screen get a segment / instances
        sg, c_ = _seg_knob(iid, G, lay, m, th, ui)
        seglist.append(iid)
        changed = changed or c_
    sg, c_ = _seg_head(G, lay, m, th, ui[0])
    changed = changed or c_
    if sg is not None:
        if v['overflow']:            # scrolling: every fixed segment after the content ones (tile lists append)
            seglist.pop(bar_at)
            seglist += ['_head', '_bar']
        else:
            seglist.append('_head')
    if g is not None:
        S['segs']['_popup'] = _seg_drop(G, g, th, ui[0]) if g['type'] == 'drop' else _seg_popup(G, g, th, ui[0], edit)
        seglist.append('_popup')
        changed = True
    if not changed and seglist == S['seglist'] and G == S['G_last'] and S['asm_last'] == S['hot_ver'] and \
            S['gpu_last'] is not None and S['scroll_last'] == S['scroll'] and S['win_last'] == S.get('win'):
        return
    S['seglist'] = seglist
    S['G_last'] = G
    _assemble(seglist, g, W, H, th, theme)


def _assemble(seglist, g, W, H, th, theme):
    """Segments -> instances / cull boxes / text rows. No overflow: everything in view px, as before. Overflow:
    content segments go in STAGE px (content y - o, flagged L.F_SCROLL; the shader moves them by the scroll uniform
    and clips them under the header), only those inside the stage band; fixed ones (bar, tabs, scrollbar, menu) in
    view px. Text TOPs hold the stage (header rows at view y, content rows at stage y), so a scroll inside the band
    rewrites nothing but the uniform and the thumb. At most L.MAX_INST instances (texture cap)."""
    segs = S['segs']
    v = S['lay']['view']
    sc = S['scroll']
    ov = bool(v['overflow'])
    win = S.get('win') if ov else None
    if ov and win is None:
        win = _window()
    S['scroll_last'] = sc
    S['win_last'] = S.get('win')
    o = win[0] if ov else 0
    hdr = v['hdr']
    sh = sc - o                       # stage y of a content-area pixel = view y + sh
    TH = int(min(L.TEX_CAP, max(H, hdr + win[2] - win[1]))) if ov else H
    budget = L.MAX_INST - sum(len(segs[k].inst) for k in seglist if segs[k].fixed)
    inst, cull, rows = [], [], []
    ccull_n = 0
    dropped = 0
    S['seg_base'] = sb = {}
    for key in seglist:
        sg = segs[key]
        base = len(inst)
        sb[key] = base
        if not ov or sg.fixed:
            if not sg.fixed:
                if budget < len(sg.inst):
                    dropped += len(sg.inst)
                    continue
                budget -= len(sg.inst)
            inst.extend(sg.inst)
            if ov:                    # fixed things in the content area: tiles at their stage position (moves);
                gx = v['W'] - v['gutter']             # the scrollbar gutter keeps view px (its tiles never move)
                for cb in sg.cull:
                    y0, y1 = cb[1], cb[1] + cb[3]
                    if y0 < hdr or cb[0] >= gx:
                        cull.append(cb)
                    else:
                        cull.append((cb[0], y0 + sh, cb[2], cb[3]))
                for r in sg.txt:
                    rows.append((r, base + r[7], sg, (o - sc) if r[5] >= hdr else 0, 0))
            else:
                cull.extend(sg.cull)
                for r in sg.txt:
                    rows.append((r, base + r[7], sg, 0, 0))
            continue
        vk = win
        if sg.vc is None or sg.vc[0] != vk:      # stage copy, reused while the band stays
            vi, vcu, loc = [], [], {}
            lo, hi = win[1], win[2]
            for j, t in enumerate(sg.inst):
                if t[1] + t[3] < lo - 2 or t[1] > hi + 2:
                    continue
                loc[j] = len(vi)
                vi.append((t[0], round(t[1] - o, 3), t[2], t[3], t[4], round(t[5] - o, 3), t[6], t[7], t[8],
                           float(int(t[9]) | L.F_SCROLL)) + t[10:])
                cb = sg.cull[j]
                vcu.append((cb[0], cb[1] - o, cb[2], cb[3]))
            sg.vc = (vk, vi, vcu, loc)
        _k, vi, vcu, loc = sg.vc
        if len(vi) > budget:
            dropped += len(vi)
            continue
        budget -= len(vi)
        inst.extend(vi)
        cull.extend(vcu)
        ccull_n = len(cull)
        for r in sg.txt:
            if r[7] in loc:
                rows.append((r, base + loc[r[7]], sg, o, sc))
    S['stats']['inst_dropped'] = dropped
    S['stage'] = (sh, hdr if ov else -1, TH, ccull_n)
    if g is not None:                # the menu sits over the knobs: drop knob text that would show through it
        bx, by, bw, bh = g['box']
        keep = []
        for e in rows:
            r = e[0]
            if r[4] == 0:
                tw = _tw(r[2], r[3])
                yb = r[5] - e[4]
                if r[0] < bx + bw and r[0] + tw > bx and yb - r[3] < by + bh and yb + r[3] * 0.3 > by:
                    continue
            keep.append(e)
        rows = keep
    hotslot = dict((iid, k) for k, iid in enumerate(S['hot']) if iid is not None) if S.get('has_hot') else {}
    bkey = tuple(sorted(set(e[0][3] for e in rows if not (e[0][6] is not None and e[0][6] in hotslot))))
    if bkey != S['bkey']:
        S['bkey'] = bkey
        S['bkeep'], S['bmap'] = L.size_buckets(list(bkey), NTEXT)
    bmap = S['bmap']
    bk = [[] for _k in range(NTEXT)]
    hb = [[] for _k in range(NHOT)]
    hsz = [None] * NHOT
    for r, gi, sg, off, _vo in rows:
        dyn = r[6]
        ty = round(TH - (r[5] - off), 1)         # Text TOP y is up from the bottom of the stage
        if dyn is not None and dyn in hotslot:
            k = hotslot[dyn]
            hb[k].append((r[0], ty, r[2]))
            hsz[k] = r[3]
            b = float(NTEXT + k)
        else:
            b = float(bmap[r[3]])
            bk[int(b)].append((r[0], ty, r[2]))
        t = inst[gi]
        if t[7] != b:                # which text input this tcol instance reads (cached back into its segment)
            inst[gi] = t[:7] + (b,) + t[8:]
            t0 = sg.inst[r[7]]
            sg.inst[r[7]] = t0[:7] + (b,) + t0[8:]
            vc = sg.vc               # keep the scrolled copy in step (it is reused while the scroll stays)
            if not sg.fixed and vc is not None and r[7] in vc[3]:
                li = vc[3][r[7]]
                vc[1][li] = vc[1][li][:7] + (b,) + vc[1][li][8:]
    S['asm_last'] = S['hot_ver']
    _flush_tables(inst, cull, [tuple(b) for b in bk], [tuple(b) for b in hb], hsz, W, H, th, theme, TH)


def _uview(uv):
    """uView: scroll shift, header bottom (-1 = nothing scrolls), stage height, scrollbar gutter x."""
    fp = P.op('zk_face').par
    if getattr(fp, 'vec8valuex', None) is None or S.get('uview_last') == uv:
        return
    S['uview_last'] = uv
    for comp, x in zip('xyzw', uv):
        if getattr(fp, 'vec8value' + comp).eval() != x:
            setattr(fp, 'vec8value' + comp, x)


def _scroll_fast(lay, v, s):
    """A scroll inside the stage band: move the thumb (its cells only) and the scroll uniform. False = full draw."""
    hs = S['segs'].get('_head')
    base = (S.get('seg_base') or {}).get('_head')
    gl = S['gpu_last']
    st = S.get('stage')
    if hs is None or base is None or gl is None or st is None or S.get('win') is None:
        return False
    k = L.RK['sbar']
    j = next((j for j, t in enumerate(hs.inst) if int(t[8]) == k), None)
    t = L.thumb(v, s, lay['h'])
    if j is None or t is None or base + j >= len(gl):
        return False
    old = hs.inst[j]
    new = old[:5] + (round(t[0], 3), round(t[1], 3)) + old[7:14] + (round(t[0], 3), round(t[1], 3))
    tab = P.op('zk_gpu')
    for f, (a, b) in enumerate(zip(new, old)):
        if a != b:
            tab[f, base + j + 1] = a
    hs.inst[j] = new
    hs.sig = hs.sig[:-1] + (t,)
    gl = list(gl)
    gl[base + j] = new
    S['gpu_last'] = gl
    w = S['win']
    S['stage'] = (s - w[0],) + tuple(st[1:])
    S['scroll_last'] = s
    _uview((float(s - w[0]), float(st[1]), float(st[2]), float(v['W'] - v['gutter'])))
    return True


def _write_spec(ts, old, rows):
    """Text TOP spec table (x y text): only changed cells, or a rewrite when the row count changed."""
    if old is not None and len(old) == len(rows) and ts.numRows == len(old) + 1:
        for i, (ra, rb) in enumerate(zip(rows, old)):
            if ra != rb:
                for j in range(3):
                    if ra[j] != rb[j]:
                        ts[i + 1, j] = ra[j]
    else:
        ts.clear()
        ts.appendRow(['x', 'y', 'text'])
        ts.appendRows([list(r) for r in rows])


def _flush_tables(inst, cull, buckets, hot, hsz, W, H, th, theme, TH=None):
    TH = H if TH is None else TH
    if int(P.par.w.eval()) != W:
        P.par.w = W
    if int(P.par.h.eval()) != H:
        P.par.h = H
    # instances: only changed cells (88 knobs: a full rewrite cost ~13 ms per change, cells ~1 ms)
    n = len(inst)
    t = P.op('zk_gpu')
    nf = len(L.FIELDS)
    diff = L.diff_columns(S['gpu_last'], inst)
    if diff is None or t.numCols != n + 1 or t.numRows != nf:
        t.clear()
        cols = list(zip(*inst)) if inst else [()] * nf
        t.appendRows([[f] + list(cols[k]) for k, f in enumerate(L.FIELDS)])
    else:
        for k, i, v in diff:
            t[k, i + 1] = v
    S['gpu_last'] = inst
    # tile lists for the face shader: rewritten only when an instance's cull box (= its knob cell) changes
    tt = P.op('zk_tiles')
    if tt is not None and (cull != S['cull_last'] or S['tiles_last'] is None or S['tiles_last'][0] != (W, TH)):
        S['cull_last'] = cull
        cn = S.get('stage', (0, -1, TH, 0))[3]
        cc = cull[:cn]
        if cn and S.get('ctiles') is not None and S['ctiles'][0] == (W, TH, cc):
            lists = [list(x) for x in S['ctiles'][1]]   # content part unchanged (scroll inside the band)
        else:
            lists = L.tile_lists(cc, W, TH, L.TILE)
            S['ctiles'] = ((W, TH, cc), [tuple(x) for x in lists])
        if len(cull) > cn:                               # + the fixed things, after (= draw order)
            more = L.tile_lists(cull[cn:], W, TH, L.TILE)
            for a_, b_ in zip(lists, more):
                a_.extend(cn + k for k in b_)
        rows = [tuple(r) for r in L.tile_rows(lists)]
        old = S['tiles_last'][1] if S['tiles_last'] is not None else None
        d_ = L.diff_rows(old, rows)
        if d_ is None or tt.numRows != len(rows) or tt.numCols != len(rows[0]):
            tt.clear()
            tt.appendRows([list(r) for r in rows])
        else:
            for r, c, v in d_:
                tt[r, c] = v
        S['tiles_last'] = ((W, TH), rows)
    # text buckets (one Text TOP per font size); only changed rows/cells
    keep = S['bkeep']
    fs = S['fs_last'] or [None] * NTEXT
    last = S['txt_last'] or [None] * NTEXT
    for k in range(NTEXT):
        tx = P.op('zk_text%d' % k)
        if k < len(keep) and fs[k] != keep[k]:
            if tx.par.fontsizex.eval() != keep[k]:
                tx.par.fontsizex = keep[k]
            fs[k] = keep[k]
        if buckets[k] != last[k]:
            _write_spec(P.op('zk_ts%d' % k), last[k], buckets[k])
    S['fs_last'] = fs
    S['txt_last'] = buckets
    if S.get('has_hot'):
        hl = S['hs_last'] or [None] * NHOT
        hf = S['hotsize_last'] or [None] * NHOT
        for k in range(NHOT):
            if hsz[k] is not None and hf[k] != hsz[k]:
                hp = P.op('zk_hot%d' % k).par
                if hp.fontsizex.eval() != hsz[k]:
                    hp.fontsizex = hsz[k]
                hf[k] = hsz[k]
            if hot[k] != hl[k]:
                _write_spec(P.op('zk_hs%d' % k), hl[k], hot[k])
        S['hs_last'] = hot
        S['hotsize_last'] = hf
    tiles_on = 1 if tt is not None else 0
    st = S.get('stage', (0, -1, TH, 0))
    fp = P.op('zk_face').par
    _uview((float(st[0]), float(st[1]), float(TH), float(W - S['lay']['view']['gutter'])))
    ukey = (n, W, H, theme, tiles_on, TH)
    if ukey != S['uni_last']:
        S['uni_last'] = ukey
        gpar = P.op('zk_face').par
        # uInfo.w = tile size (0 = no tile table: the shader loops over every instance, as before)
        vals = [(n, W, H, L.TILE if tiles_on else 0), th['bg'] + (1,), th['body'] + (1,), th['track'] + (1,),
                L.SURFACE_BLUE + (1,), L.SURFACE_DIM + (1,), L.RED + (1,), (1, 1, 1, 1.0 if theme == 'day' else 0.0)]
        for k, v in enumerate(vals):
            for comp, x in zip('xyzw', v):
                setattr(gpar, 'vec%dvalue%s' % (k, comp), x)
        names = ['zk_face', 'zk_comp'] + ['zk_text%d' % k for k in range(NTEXT)] + ['zk_hot%d' % k for k in range(NHOT)]
        for o in names:
            o_ = P.op(o)
            if o_ is None:
                continue
            p = o_.par
            h_ = H if o in ('zk_face', 'zk_comp') else TH   # the face = the view; text = the stage (<= TEX_CAP)
            if p.resolutionw.eval() != W or p.resolutionh.eval() != h_:
                p.resolutionw, p.resolutionh = W, h_
