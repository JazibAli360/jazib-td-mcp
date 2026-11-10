# cs_rt - CS_cam_sequencer v2 TD runtime (copied into the Camera COMP as the Text DAT `cs_rt` by builders/cam_seq.py).
# Pure logic lives in cs_logic (builders/cam_seq_logic.py) + cam_rig_logic. TD 2025.31550. ASCII only.
#
# Drop-in rules: every reference is relative to the COMP `c` (the Camera COMP itself): c.op('x'), c.par.*; the
# optional hooks (Auop, Tlop, Effop, Targetop, Customease, in1) are empty by default and a missing one never raises;
# state is this module's dict keyed by the COMP's id (each copy has its own cs_rt DAT, so its own dict).
#
# Bind (documented choice, docs/builds/cs_cam_sequencer.md "How Bind works"): WRITE ON CHANGE. The solve Script CHOP
# computes one state per cook; when it differs from the last one, the counter channel cs_ver steps and the CHOP
# Execute `cs_bind` writes the values into the camera's own CONSTANT pars (and the Look At op's). Nothing writes
# while the output stands still, so with Bind on the camera viewer can still be tumbled between Select moves (then
# Append / Replace capture it), and the sequencer owns the pars whenever it moves. Bind off = no writes at all.
# Values are written from the module's float64 copy, not the float32 CHOP (T-247).
#
# Also: the solve never reads absTime itself (T-143): its Frame / Secs pars do, only while its Tick par is on, so an
# idle manual sequencer cooks 0 times; the cook never writes pars (Tick and Select are set by run() a frame later);
# TD names by plain name (T-240); pulses go through the Parameter Execute DAT `cs_pexec`, one event each (T-238).

import numpy as np

STATE = {}


def S(c):
    st = STATE.get(c.id)
    if st is None:
        st = STATE[c.id] = {'E': None, 'events': [], 'ok': False, 'cam': [], 'look': [], 'edges': {}, 'tick': None,
                            'last_preset_chan': None, 'cooks': 0, 'P': None, 'out': None, 'ver': 0, 'writes': 0,
                            'L': None, 'written': None, 'params': 0}
    return st


def L(c):
    st = S(c)
    m = st.get('L')
    if m is None:                                            # cached: a DAT's .module costs ~8 us a call
        m = c.op('cs_logic').module
        rig = c.op('cam_rig_logic').module
        if getattr(m, 'R', None) is not rig:
            m.bind_rig(rig)
        st['L'] = m
    return m


def engine(c):
    st = S(c)
    if st['E'] is None:
        st['E'] = L(c).Engine()
    return st['E']


def note(c, msg):
    p = getattr(c.par, 'Status', None)
    if p is not None:
        run("o = op(args[0])\nif o is not None: o.par.Status = args[1]", c.path, str(msg)[:200], delayFrames=1)


# ------------------------------------------------------------------------------------------------ preset tables

def _rows(t):
    return [[x.val for x in t.row(r)] for r in range(t.numRows)] if t is not None else []


def tables(c):
    """(cam presets, look presets), parsed only after a table changed (cam_watch / look_watch -> tables_dirty)."""
    st = S(c)
    if not st['ok']:
        Lg = L(c)
        st['cam'] = Lg.presets_from_rows(_rows(c.op('cam_presets')), Lg.CAM_PARS)
        st['look'] = Lg.presets_from_rows(_rows(c.op('lookat_presets')), Lg.LOOK_PARS)
        st['ok'] = True
    return st['cam'], st['look']


def tables_dirty(c):
    S(c)['ok'] = False
    poke(c)


def _fill(t, rows):
    t.clear()
    t.appendRows(rows)


def write_tables(c, cam, look, sel=None):
    Lg = L(c)
    _fill(c.op('cam_presets'), Lg.preset_rows(cam, Lg.CAM_PARS))
    _fill(c.op('lookat_presets'), Lg.preset_rows(look, Lg.LOOK_PARS))
    S(c)['ok'] = False
    c.par.Select.normMax = max(len(cam), 1)
    if sel is not None and c.par.Select.mode == ParMode.CONSTANT:
        c.par.Select = float(sel)                            # the camera stays where it was captured
    poke(c)


# ------------------------------------------------------------------------------------------------ capture

def look_op(c):
    """The camera's own Xform Look At op (any object COMP), or None."""
    try:
        o = c.par.lookat.eval()
    except Exception:
        return None
    return o if (o is not None and getattr(o.par, 'tx', None) is not None) else None


def _vals(o, names):
    return tuple(float(getattr(o.par, n).eval()) if getattr(o.par, n, None) is not None else 0.0 for n in names)


def capture_cam(c):
    return _vals(c, L(c).CAM_PARS)


def capture_look(c):
    o = look_op(c)
    return _vals(o, L(c).LOOK_PARS) if o is not None else None


def do_edit(c, kind):
    """Seq page Init / Append / Insert (before the selected) / Replace / Remove: the camera's current pars (and its
    Look At op's) into both tables at the same row; EASE = the current Easing."""
    Lg = L(c)
    cam, look = tables(c)
    n = len(cam)
    sel = Lg.selected(float(c.par.Select.eval()), n, c.par.Loopmode.eval()) if n else None
    if kind in ('replace', 'remove') and sel is None:
        note(c, '%s: no presets yet (Init or Append first)' % kind)
        return None
    c2, l2, s2 = Lg.edit_pair(cam, look, kind, sel, capture_cam(c), capture_look(c), c.par.Easing.eval())
    write_tables(c, c2, l2, s2)
    note(c, '%s -> preset %s of %d%s' % (kind, s2, len(c2), (' (+ Look At %s)' % look_op(c).name)
                                         if look_op(c) is not None else ''))
    return s2


# ------------------------------------------------------------------------------------------------ pop-up editor

def _ui(c):
    return c.op('presets_ui')


def open_presets(c, which):
    """Presets page pulses: the pop-up table editor (#, EASE, a column per par) for 'cam' or 'look'."""
    ui = _ui(c)
    w = c.op('presets_window')
    if ui is None or w is None:
        return False
    tname = 'cam_presets' if which == 'cam' else 'lookat_presets'
    ui.par.Table = tname
    ov = ui.op('table_view')
    if ov is not None:
        ov.par.opviewer = '../' + tname                     # relative: the table is a child of the camera
    w.par.title = '%s  %s presets' % (c.name, 'Cam' if which == 'cam' else 'Look At')
    _ui_label(c)
    w.par.winopen.pulse()
    return True


def _ui_rows(c):
    ui = _ui(c)
    t = c.op(ui.par.Table.eval()) if ui is not None else None
    return t


def _ui_label(c):
    ui = _ui(c)
    t = _ui_rows(c)
    if ui is None or t is None:
        return
    n = max(t.numRows - 1, 0)
    r = int(ui.par.Row.eval())
    if n and r > n - 1:
        ui.par.Row = n - 1
        r = n - 1
    lab = ui.op('lbl')
    if lab is not None and getattr(lab.par, 'text', None) is not None:
        lab.par.text = '%s   row #%d of %d' % ('Cam' if t.name == 'cam_presets' else 'Look At', r, n)


def ui_click(c, name):
    """Pop-up buttons: Row - / + pick the row, Up / Down move it, Add appends the current values, Dup, Delete,
    Sort # reorders by the # cells (type 1.5 to put a row between 1 and 2). Moves act on THIS table only (the two
    tables are separate, as the original's)."""
    Lg = L(c)
    ui = _ui(c)
    t = _ui_rows(c)
    if ui is None or t is None:
        return None
    pars = Lg.CAM_PARS if t.name == 'cam_presets' else Lg.LOOK_PARS
    pre = Lg.presets_from_rows(_rows(t), pars)
    r = int(ui.par.Row.eval())
    n = len(pre)
    if name == 'b_close':
        w = c.op('presets_window')
        if w is not None:
            w.par.winclose.pulse()
        return None
    if name in ('b_rowm', 'b_rowp'):
        ui.par.Row = max(0, min(n - 1, r + (1 if name == 'b_rowp' else -1)))
        _ui_label(c)
        return None
    if name == 'b_sort':
        _fill(t, Lg.sort_rows_by_number(_rows(t)))
        tables_dirty(c)
        return None
    if name == 'b_add':
        v = capture_cam(c) if t.name == 'cam_presets' else (capture_look(c) or
                                                            (pre[-1]['v'] if pre else Lg.default_vec(pars)))
        new, sel = Lg.edit(pre, 'append', None, v, c.par.Easing.eval())
    else:
        kind = {'b_up': 'moveup', 'b_down': 'movedown', 'b_del': 'remove', 'b_dup': 'duplicate'}.get(name)
        if kind is None or not n:
            return None
        new, sel = Lg.edit(pre, kind, min(r, n - 1))
    _fill(t, Lg.preset_rows(new, pars))
    ui.par.Row = sel if sel is not None else 0
    tables_dirty(c)
    _ui_label(c)
    return sel


# ------------------------------------------------------------------------------------------------ menus (T-233)

def menu(c, name):
    """Live dropdown items (menuSource = me.op('cs_rt').module.menu(me, name)); read on menu open, never per frame."""
    M = c.op('menu_logic').module
    try:
        if name == 'Gotopreset':
            cam, _look = tables(c)
            return M.name_menu([str(k) for k in range(len(cam))],
                               ['#%d  %s' % (k, p['ease'] or '(Easing)') for k, p in enumerate(cam)])
        if name == 'Targeteff':
            rows = _eff_rows(c)
            return M.name_menu([r['name'] for r in rows], ['%s (%s)' % (r['name'], r.get('kind', '')) for r in rows],
                               none=True)
    except Exception:
        return M.Menu()
    return M.Menu()


def _eff_rt(c):
    try:
        e = c.par.Effop.eval()
    except Exception:
        return None
    d = e.op('eff_rt') if e is not None else None
    return d.module if d is not None else None


def _eff_rows(c):
    rt = _eff_rt(c)
    try:
        return list(rt.rows()) if rt is not None else []
    except Exception:
        return []


# ------------------------------------------------------------------------------------------------ targets + clock

def _point(o):
    m = o.worldTransform
    return (m[0, 3], m[1, 3], m[2, 3])


def target_point(c, mode):
    try:
        if mode == 'op':
            o = c.par.Targetop.eval()
            return _point(o) if (o is not None and hasattr(o, 'worldTransform')) else None
        if mode == 'effector':
            nm = str(c.par.Targeteff.eval()).strip()
            rt = _eff_rt(c)
            if nm and rt is not None:
                for r in rt.rows():
                    if r['name'] == nm:
                        o = rt.source_of(r)
                        if o is not None and hasattr(o, 'worldTransform'):
                            return _point(o)
    except Exception:
        return None
    return None


def clock(c, P, secs):
    """(beats, bpm) of Clockmode; falls back to the internal clock when the source is empty or missing."""
    m = P['clockmode']
    bpm = float(P['bpm'])
    try:
        if m == 'au':
            a = c.par.Auop.eval()
            o = (a.op('out1') or a.op('out_features')) if a is not None else None
            if o is not None and o['beat_count'] is not None:
                b = float(o['bpm'][0]) if o['bpm'] is not None else 0.0
                ph = float(o['beat_phase'][0]) if o['beat_phase'] is not None else 0.0
                return float(o['beat_count'][0]) + min(max(ph, 0.0), 0.999), (b if b > 1.0 else bpm)
        elif m == 'tl':
            t = c.par.Tlop.eval()
            o = t.op('tl_out') if t is not None else None
            if o is not None and o['tl_beat'] is not None:
                return float(o['tl_beat'][0]), bpm
        elif m == 'chop':
            i = c.op('in1')
            if i is not None and i['beats'] is not None:
                return float(i['beats'][0]), bpm
        elif m == 'manual':
            return float(P['seek']), bpm
    except Exception:
        pass
    return secs * bpm / 60.0, bpm


# ------------------------------------------------------------------------------------------------ cook

PARS = ('Bind', 'Playmode', 'Loopmode', 'Override', 'Easing', 'Trans', 'Splineinterp', 'Splinetension', 'Shortrot',
        'Defaulthold', 'Tdur', 'Quant', 'Gotoblend', 'Gototime', 'Gotoease', 'Seed', 'Minhold', 'Maxhold',
        'Shakeprofile', 'Shakeamount', 'Shakepos', 'Shakerot', 'Shakespeed', 'Shakeseed', 'Shakebeat', 'Shakeperlens',
        'Fovoffset', 'Roll', 'Targetmode', 'Lookdamp', 'Frame', 'Framepad', 'Frameradius', 'Resx', 'Resy', 'Lag',
        'Bpm', 'Clockmode', 'Seek', 'Beatsperbar')
KEYMAP = {'Splinetension': 'tension'}
BOOLS = ('bind', 'override', 'splineinterp', 'shortrot', 'shakeperlens', 'frame')


def params(c):
    S(c)['params'] += 1
    P = {}
    for n in PARS:
        p = getattr(c.par, n, None)
        if p is not None:
            P[KEYMAP.get(n, n.lower())] = p.eval()
    for k in BOOLS:
        P[k] = bool(P.get(k))
    P['rord'] = c.par.rord.eval()
    return P


def _edge(st, key, v):
    prev = st['edges'].get(key, 0.0)
    st['edges'][key] = v
    return v > 0.5 >= prev


def _custom(c, cam, P):
    if P['easing'] != 'custom' and not any(p.get('ease') == 'custom' for p in cam):
        return None
    try:
        ch = c.par.Customease.eval()
    except Exception:
        return None
    if ch is None or not ch.numChans:
        return None
    return list(ch[0].vals)


def cook(c, s):
    st = S(c)
    st['cooks'] += 1
    Lg = L(c)
    cam, look = tables(c)
    if st['P'] is None:                                      # par values cached; cs_pexec marks them dirty
        st['P'] = params(c)
    P = dict(st['P'])
    P['select'] = float(s.par.Sel.eval()) if getattr(s.par, 'Sel', None) is not None else float(c.par.Select.eval())
    lo = look_op(c)                                          # read live: Look At set / cleared
    P['haslook'] = lo is not None
    secs = float(s.par.Secs.eval())
    ev = st['events']
    st['events'] = []
    i1 = c.op('in1')
    if i1 is not None and i1.numChans:                       # optional CHOP drives (CHOP / OSC / kick)
        if i1['select'] is not None:
            P['select'] = float(i1['select'][0])
        for k in ('next', 'prev', 'random'):
            if i1[k] is not None and _edge(st, k, float(i1[k][0])):
                ev.append((k,))
        if i1['kick'] is not None and _edge(st, 'kick', float(i1['kick'][0])):
            ev.append(('next',))
        if i1['preset'] is not None:
            v = int(round(float(i1['preset'][0])))
            if v != st['last_preset_chan']:
                if st['last_preset_chan'] is not None:
                    ev.append(('goto', v))
                st['last_preset_chan'] = v
    timed = P['playmode'] != 'manual' or float(P['shakebeat']) > 0 or P['shakeprofile'] == 'quake'
    if timed:
        beats, bpm = clock(c, P, secs)
        P['bpm'] = bpm
    else:
        beats = float(P['bpm']) * secs / 60.0
    if P['targetmode'] in ('op', 'effector'):
        P['targetpoint'] = target_point(c, P['targetmode'])
    E = engine(c)
    camv, lookv, info = E.step(cam, look, P, beats, secs, ev, _custom(c, cam, P))
    if camv is not None:
        out = (tuple(camv), tuple(lookv) if (lookv is not None and P['haslook']) else None)
        if out != st['out']:
            st['out'] = out
            st['ver'] = (st['ver'] + 1) % 1000000
    else:
        st['out'] = None
    vals = Lg.out_values(camv if camv is not None else capture_cam(c), lookv, info, P['haslook'], st['ver'])
    s.clear()
    s.copyNumpyArray(np.array(vals, dtype=np.float32).reshape(-1, 1))   # one call for all channels (T-199)
    need = (info['needs_tick'] or bool(st['events']) or E.pending is not None or E.goto is not None)
    want = 1 if need else 0
    if want != st['tick']:                                   # poke() resets st['tick'] when it sets Tick itself
        st['tick'] = want
        run("o = op(args[0])\nif o is not None and o.par.Tick.eval() != args[1]: o.par.Tick = args[1]", s.path, want,
            delayFrames=1)


def poke(c):
    """Make the solve cook now and keep ticking until it decides it is idle (and re-read the pars)."""
    st = S(c)
    st['P'] = None
    s = c.op('solve')
    if s is not None and not s.par.Tick.eval():
        s.par.Tick = 1
    st['tick'] = None


# ------------------------------------------------------------------------------------------------ Bind

def _write(o, names, vals, prev=None):
    """Set the CONSTANT pars whose value changed since the last write (prev = what was written then; None = compare
    with the par itself). Par reads cost ~2 us each, so the steady state compares Python floats only."""
    k = 0
    for q, (n, v) in enumerate(zip(names, vals)):
        if prev is not None and prev[q] == v:
            continue
        p = getattr(o.par, n, None)
        if p is None or p.mode != ParMode.CONSTANT:
            continue
        if prev is not None or abs(float(p.val) - v) > 1e-9:
            p.val = v
            k += 1
    return k


def on_out(c):
    """cs_bind (CHOP Execute on cs_ver): the new state into the camera's pars and the Look At op's (Bind on).
    Only the values that changed since the last write are set (Bind on / a new Look At op = a full write)."""
    st = S(c)
    if st['out'] is None or not bool(c.par.Bind.eval()):
        st['written'] = None
        return 0
    Lg = L(c)
    camv, lookv = st['out']
    lo = look_op(c) if lookv is not None else None
    w = st['written']
    lp = lo.path if lo is not None else None
    if w is not None and w[2] != lp:
        w = None
    k = _write(c, Lg.CAM_PARS, camv, w[0] if w is not None else None)
    if lo is not None:
        k += _write(lo, Lg.LOOK_PARS, lookv, w[1] if (w is not None and w[1] is not None) else None)
    st['written'] = (camv, lookv if lo is not None else None, lp)
    st['writes'] += k
    return k


def _constant(o, names):
    for n in names:
        p = getattr(o.par, n, None)
        if p is not None and p.mode != ParMode.CONSTANT:
            v = p.eval()
            p.mode = ParMode.CONSTANT
            p.val = v


def bind(c, on=True):
    """Bind on: the sequencer owns the camera's pars (and the Look At op's): expressions / exports on them are
    turned to constants, then the current state is written. Off: nothing is written; the pars keep their values,
    free for the viewer / hand; Append / Replace and re-bind."""
    Lg = L(c)
    if on:
        _constant(c, Lg.CAM_PARS)
        lo = look_op(c)
        if lo is not None:
            _constant(lo, Lg.LOOK_PARS)
        S(c)['out'] = None                                   # the next cook re-sends (cs_ver steps)
    S(c)['written'] = None
    poke(c)
    note(c, 'Bind %s' % ('on: the sequencer owns the camera pars' if on else 'off: edit freely, then Append / '
                         'Replace and re-bind'))


# ------------------------------------------------------------------------------------------------ events

EDITS = {'Init': 'init', 'Append': 'append', 'Insert': 'insert', 'Replace': 'replace', 'Remove': 'remove'}
TRIGS = {'Trignext': ('next',), 'Trigprev': ('prev',), 'Trigrandom': ('random',)}


def goto(c, key=None):
    """Any-to-any jump to a preset (index): blends from the current output straight to it. Manual mode: a constant
    Select is set to the target, so the fader agrees when the jump lands; a later hand move wins."""
    cam, _look = tables(c)
    k = c.par.Gotopreset.eval() if key is None else key
    try:
        i = int(float(str(k).strip()))
    except (TypeError, ValueError):
        i = None
    if i is None or not 0 <= i < len(cam):
        note(c, 'go to: no preset %r' % (k,))
        return None
    if c.par.Playmode.eval() == 'manual' and c.par.Select.mode == ParMode.CONSTANT:
        c.par.Select = float(i)
    S(c)['events'].append(('goto', i))
    poke(c)
    return i


def open_controls(c):
    """Optional zkit panel: open it if it exists; build it once when this repo's zkit builder is reachable; else a
    note (the sequencer never needs it)."""
    w = c.op('controls_window')
    if w is not None:
        w.par.winopen.pulse()
        return True
    import os
    path = c.op('cs_cfg')[1, 1].val if (c.op('cs_cfg') is not None and c.op('cs_cfg').numRows > 1) else ''
    if not path or not os.path.isfile(path) or op('/jazib_mcp/handlers') is None:
        note(c, 'zkit panel not available here (needs the jazib-td-mcp repo); every control is on these pages')
        return False
    run("ns = {'op': op}\nns.update(globals())\nexec(open(args[1]).read(), ns)\n"
        "ns['build_controls'](args[0], pages=args[2], d=56, cols=8, open_window=True)",
        c.path, path, ['Seq', 'Play', 'Clock', 'Shake', 'Look'], delayFrames=1)
    note(c, 'building the zkit panel (first open is slow: fonts, T-248)')
    return True


def on_pulse(c, name):
    if name in EDITS:
        return do_edit(c, EDITS[name])
    if name == 'Opencampresets':
        return open_presets(c, 'cam')
    if name == 'Openlookatpresets':
        return open_presets(c, 'look')
    if name in TRIGS:
        S(c)['events'].append(TRIGS[name])
        return poke(c)
    if name == 'Trigcut':
        cam, _l = tables(c)
        S(c)['events'].append(('cut', L(c).selected(float(c.par.Select.eval()), len(cam))))
        return poke(c)
    if name == 'Go':
        return goto(c)
    if name == 'Reset':
        engine(c).reset()
        return poke(c)
    if name == 'Opencontrols':
        return open_controls(c)
    return None


def on_value(c, name):
    S(c)['P'] = None
    if name == 'Gotopreset':
        return goto(c)
    if name == 'Bind':
        return bind(c, bool(c.par.Bind.eval()))
    if name in ('Playmode', 'Clockmode'):
        engine(c).seg = None
    if not name.startswith('Zk'):
        poke(c)
    return None
