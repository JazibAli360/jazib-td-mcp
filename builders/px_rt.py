# px_rt - PX_pointfx TD runtime (copied into the Text DAT `px_rt` by builders/px.py). TD 2025.31550.
# Pure maths lives in px_logic (Text DAT `px_logic`); this file only talks to TD: reads pars / tables / effector
# objects once per frame (guarded by absTime.frame), fills the uniform Script CHOPs, uploads rest textures on load,
# recompiles the stage shaders when the module STACK changes (never per frame), keeps module pages, effector objects,
# gizmos and presets in sync.
# Rules kept: T-67 only plain data in storage; T-74/T-76 no TOP pixel reads anywhere; T-70 no destroy of a panel an
# open window shows (pages are custom pars, effectors live outside the panel; destroys go through safe_destroy);
# T-89 module globals can vanish (STATE self-heals, layout + rest cache are rebuilt on demand); T-81 per-channel
# appendChan(nm).copyNumpyArray; T-64 never touches cookRate. ASCII only.
import json
import math

STATE = {}        # comp path -> dict (frame cache, phases, trigger times, effector history, rest images)


def C():
    return me.parent()


_LC = {'f': None, 'm': None}


def L():
    """px_logic's module, looked up once per frame (perf, T-143). This module is the px_rt DAT of ONE COMP, so the
    cache is per COMP; a rewritten px_logic text is picked up the next frame."""
    f = absTime.frame
    if _LC['f'] != f or _LC['m'] is None:
        _LC['m'] = C().op('px_logic').module
        _LC['f'] = f
    return _LC['m']


def S(c=None):
    c = c or C()
    s = STATE.get(c.path)
    if s is None:
        s = {'frame': None, 'rows': None, 'simt': 0.0, 'tlast': None, 'phases': {}, 'trig_t': [-1e9] * 4,
             'eff_prev': {}, 'reset': 2, 'rest': {}, 'bounds': None, 'orbit': 0.0, 'spin': [0.0, 0.0, 0.0],
             'morph': None, 'gizmo': {}, 'err': '', 'trail': {}, 'pts_prev': {}, 'mpos': {}, 'mt0': 0.0,
             'splat': False, 'actor_frames': [], 'actor_idx': -1, 'actor_prev': None, 'sort_last': None,
             'sort_fwd': None, 'sort_pos': (0.0, 0.0, 0.0), 'sort_dirty': True, 'sortnow': False, 'sorts': 0,
             'sorter_on': False}
        STATE[c.path] = s
    return s


def status(c, text):
    S(c)['err'] = text
    p = getattr(c.par, 'Status', None)
    if p is not None and p.eval() != text:
        p.val = text[:250]


def _sd(o):
    if o is None or not o.valid:
        return
    h = op('/jazib_mcp/handlers')                  # the MCP's safe destroy when it is installed; plain destroy in any
    f = getattr(h.module, 'safe_destroy', None) if h is not None else None   # other project (drop-in, 28 Oct)
    if f is not None:
        f(o)
    else:
        nomcp = o                                   # T-70 exception: no MCP here, so no safe_destroy to call
        nomcp.destroy()


# ------------------------------------------------------------------------------------------------- reading

def raw_core(c):
    out = {}
    s = S(c)
    key = len(c.customPars)
    cache = s.get('core_pars')
    if cache is None or cache[0] != key:          # par list cached (perf: ~0.3 ms/frame with ~250 custom pars)
        pages = set(L().CORE_PAGE_NAMES)
        cache = (key, [p for p in c.customPars if p.page.name in pages and p.style != 'Pulse'])
        s['core_pars'] = cache
    for p in cache[1]:
        if p.valid:
            v = p.eval()
            if hasattr(v, 'path'):
                v = v.path
            out[p.name] = v
    return out


def stack(c):
    t = c.op('px_stack')
    if t is None:
        return []
    rows = [[cell.val for cell in t.row(r)] for r in range(t.numRows)]
    return L().stack_from_rows(rows)


def write_stack(c, st):
    t = c.op('px_stack')
    rows = L().stack_rows(st)
    t.clear()
    t.appendRows(rows)
    mark_all(c)
    # Compile now: the stack_watch DAT Execute did not fire reliably for edits made from Python (live, 31550: an add
    # stayed 'compiling' until the next edit). The watch still catches hand edits; a second call for the same stack
    # returns at once (pending/live hash check in stack_changed).
    stack_changed(c)


def flat_module_values(c, st):
    flat = {}
    s = S(c)
    key = (len(c.customPars), tuple((i['uid'], i['type']) for i in st))
    cache = s.get('mod_pars')
    if cache is None or cache[0] != key:          # par objects per stack cached (perf)
        Lg = L()
        cache = (key, [(n, getattr(c.par, n, None)) for inst in st for n in Lg.flat_par_names(inst)])
        s['mod_pars'] = cache
    for n, p in cache[1]:
        if p is not None and p.valid:
            flat[n] = p.eval()
    return flat


def eff_table(c):
    t = c.op('px_eff')
    out = []
    if t is None:
        return out
    for r in range(1, t.numRows):
        row = dict((t[0, k].val, t[r, k].val) for k in range(t.numCols))
        if row.get('name'):
            out.append(row)
    return out[:8]


def _pos(m, x, y, z):
    p = m * tdu.Position(x, y, z)
    return (p.x, p.y, p.z)


def _world(o):
    m = o.worldTransform
    return L().affine_from_points(_pos(m, 0, 0, 0), _pos(m, 1, 0, 0), _pos(m, 0, 1, 0), _pos(m, 0, 0, 1))


def _find(c, path):
    if not path:
        return None
    return c.op(path) or op(path)


def eff_raw(o):
    """Effector page values of an object ({} for objects without the page: defaults apply)."""
    out = {}
    if o is None:
        return out
    for name, style, _d, _o in L().EFF_PARS:
        if style == 'Pulse':
            continue
        keys = [name + s_ for s_ in ('xyz' if style == 'XYZ' else 'rgb')] if style in ('XYZ', 'RGB') else [name]
        for k in keys:
            p = getattr(o.par, k, None)
            if p is not None:
                v = p.eval()
                out[k] = v.path if hasattr(v, 'path') else v
    return out


def _chop_chans(ch, maxn=None):
    d = {}
    for cc in ch.chans():
        vals = cc.vals if maxn is None else cc.vals[:maxn]
        d[cc.name] = list(vals)
    return d


def _pts_source(c, path, nmax, obj=None):
    """Point set of a pts effector, local to its Null: a CHOP (samples = points: tx ty tz, or one sample of
    <prefix>tx/ty/tz triples) or a SOP (its points, stride subsampled to nmax). No TOP pixel reads (T-74): a TOP goes
    through a TOP to CHOP the user wires, a POP through a POP to SOP / CHOP."""
    Lg = L()
    o = None
    if obj is not None and path:                     # relative to the effector object first (what the user sees)
        try:
            o = obj.op(path)
        except Exception:
            o = None
    o = o or _find(c, path)
    if o is None:
        return []
    pts = []
    try:
        if o.family == 'CHOP':
            if o.numSamples > nmax:                  # samples = points: stride-subsample the channels first (a
                idx = Lg.pts_subsample(range(o.numSamples), nmax)   # 16k-sample TOP to CHOP of a particle state)
                d = {}
                for ch in o.chans():
                    v = ch.vals
                    d[ch.name] = [v[k] for k in idx]
                pts = Lg.pts_from_chans(d)
            else:
                pts = Lg.pts_from_chans(_chop_chans(o))
        elif o.family == 'SOP':
            P = o.points
            idx = Lg.pts_subsample(range(len(P)), nmax)
            pts = [(P[k].x, P[k].y, P[k].z) for k in idx]
    except Exception:
        pts = []
    return [pts[k] for k in Lg.pts_subsample(pts, nmax)]


def _move(c, row, o, st, t, dt):
    """A2: write the motion path position into the effector object's translate (constant pars only)."""
    Lg = L()
    s = S(c)
    kind = st.get('Motion', 'none')
    if kind == 'none' or o is None or not Lg._truthy(st.get('Mplay', True)):
        return
    chop_pts = None
    if kind == 'chop':
        ch = _find(c, st.get('Mchop', ''))
        if ch is not None and ch.family == 'CHOP':
            chop_pts = Lg.pts_from_chans(_chop_chans(ch))
    follow = None
    if kind == 'follow':
        f = _find(c, st.get('Mfollow', ''))
        if f is not None and hasattr(f, 'worldTransform'):
            follow = _pos(f.worldTransform, 0, 0, 0)
    pos = Lg.motion_pos(kind, t - s['mt0'], st, chop_pts, follow, s['mpos'].get(row['name']), dt,
                        seed=sum(ord(ch_) for ch_ in row['name']))
    if pos is None:
        return
    s['mpos'][row['name']] = pos
    for k, v in zip(('tx', 'ty', 'tz'), pos):
        p = getattr(o.par, k)
        if p.mode == ParMode.CONSTANT and abs(p.eval() - v) > 1e-7:
            p.val = v


def effectors(c, dt, t=0.0, actor_off=(0.0, 0.0, 0.0), actor_samples=256):
    """-> list of {'name','kind','world','speed','vel','axis','pts','trail','settings'} in px_eff order (index =
    effector id). Motion paths are applied first (they move the object), then transforms are read. Also fills
    S['pts_rows'/'ptsv_rows'/'trail_rows'/'glow_rows'/'glow_n'] for the texture buffers and the glow MAT."""
    Lg = L()
    s = S(c)
    out = []
    sets = []
    bufs = []
    now = absTime.seconds
    s.setdefault('eff_prev_t', {})
    for row in eff_table(c):
        kind = row.get('kind', 'null')
        world = None
        o = None
        axis = None
        if kind == 'chop':
            ch = _find(c, row.get('path', ''))
            pre = row.get('prefix', '')
            if ch is not None:
                g = lambda n, d=0.0: float(ch[pre + n].eval()) if ch[pre + n] is not None else d
                world = Lg.chop_affine((g('tx'), g('ty'), g('tz')), g('sx', 1.0))
        elif kind == 'actor':
            world = Lg.chop_affine(actor_off, 1.0)
        else:
            o = _find(c, row.get('path', ''))
        # Effector page values: cached, re-read when eff_watch saw a page edit (dirty_effset) or for a new object
        ec = s.setdefault('effset', {})
        st = ec.get(row['name'])
        if st is None or s.get('effset_stale', True) or (o is not None and st[0] != o.path):
            st = (o.path if o is not None else '', Lg.eff_settings(eff_raw(o)))
            ec[row['name']] = st
        st = st[1]
        if kind == 'camera':                               # camera: its forward (-Z) is the axis (radial blast, bend)
            pos, axis = _cam_pose(s.get('cam'))            # from the orbit numbers (last frame), never pcam (cook loop)
            world = Lg.chop_affine(pos, 1.0)
        elif o is not None:
            _move(c, row, o, st, t, dt)
            if hasattr(o, 'worldTransform'):
                world = _world(o)
        if world is None:
            world = Lg.chop_affine((0.0, 0.0, 0.0), 1.0)
        ctr = (world[0][3], world[1][3], world[2][3])
        prev = s['eff_prev'].get(row['name'])
        vel = (0.0, 0.0, 0.0)
        # velocity over the time since this effector was last read (the engine skips static effectors, T-143: a
        # frame dt after a long skip would turn a hand edit into a huge velocity spike)
        tp = s['eff_prev_t'].get(row['name'])
        dtv = (now - tp) if tp is not None else dt
        if prev is not None and dt > 0 and dtv > 0:
            vel = tuple((a - b) / max(dtv, dt) for a, b in zip(ctr, prev))
        sp = math.sqrt(sum(x * x for x in vel))
        s['eff_prev'][row['name']] = ctr
        s['eff_prev_t'][row['name']] = now
        e = {'name': row['name'], 'kind': kind, 'world': world, 'speed': sp, 'vel': vel, 'settings': st}
        if axis is not None:
            e['axis'] = axis
        if kind == 'pts':
            loc = _pts_source(c, st.get('Ptssource', ''), int(st.get('Ptsmax', 512)), o)
            wp = Lg.xform_pts(world, loc)
            pv = Lg.pts_velocity(wp, s['pts_prev'].get(row['name']), dt)
            s['pts_prev'][row['name']] = wp
            sets.append((wp, pv))
            e['pts'] = len(sets) - 1
            e['size'] = (float(st.get('Ptsradius', 0.02)), 0.0, 0.0)
        elif kind == 'actor':
            e['pts_actor'] = int(actor_samples)
            e['size'] = (float(st.get('Ptsradius', 0.02)) if o is not None else 0.05, 0.0, 0.0)
        s['trail'][row['name']] = Lg.trail_push(s['trail'].get(row['name'], []), ctr, t, int(st.get('Trail', 0)),
                                                float(st.get('Traildt', 0.05)))
        bufs.append(s['trail'][row['name']])
        e['trail_buf'] = s['trail'][row['name']]
        out.append(e)
    prow, pvrow, spans = Lg.pack_pts(sets)
    trows, tspans = Lg.trail_rows(bufs, t)
    for k, e in enumerate(out):
        if 'pts' in e:
            st_, cnt = spans[e['pts']]
            e['pts'] = (st_, cnt, Lg.menu_index(Lg.PTSMODES, e['settings'].get('Ptsmode', 'nearest')))
        elif 'pts_actor' in e:
            e['pts'] = (0, e.pop('pts_actor'), Lg.menu_index(Lg.PTSMODES, e['settings'].get('Ptsmode', 'nearest')))
        e['trail'] = tspans[k]
    grows, gn = Lg.glow_rows([{'kind': e['kind'], 'world': e['world'], 'settings': e['settings'],
                               'trail': e['trail_buf']} for e in out], s.get('pal_recol'))
    s['effset_stale'] = False
    s['pts_rows'], s['ptsv_rows'], s['trail_rows'] = prow, pvrow, trows
    s['glow_rows'], s['glow_n'] = grows, gn
    return out


def _chop_vals(c, raw):
    o = c.op(raw.get('Audiochop') or '') if raw.get('Audiochop') else None
    if o is None:
        i = c.op('in_ctl')
        o = i if (i is not None and i.numChans) else None
    vals = {}
    if o is not None:
        for ch in o.chans():
            try:
                vals[ch.name] = float(ch.eval())
            except Exception:
                pass
    d = c.op(raw.get('Drivechop') or '') if raw.get('Drivechop') else None   # wave 4 K33: OSC / MIDI / any CHOP
    if d is not None:
        Lg = L()
        for ch in d.chans():
            try:
                nm = Lg.drive_name(ch.name) if hasattr(Lg, 'drive_name') else ch.name
                if nm and nm not in vals:
                    vals[nm] = float(ch.eval())
            except Exception:
                pass
    return vals


AUDIO_NOTES = {'off': 'audio: Audiosrc empty (off): audio drive sources read 0',
               'missing': 'audio: %s not found: audio drive sources read 0',
               'parked': 'audio: %s is parked (turn it on): audio drive sources read 0',
               'quiet': 'audio: %s Analysison off: bass / mid / high / level only; beat / onset / tempo read 0',
               'live': 'audio: beat sync from %s'}


def _audio_chans(c):
    '''Beat sync (28 Oct): AUDIO_CHANS of <Audiosrc>/out_features -> ({channel: value} or None, state). Never cooks
    a parked COMP; missing channels are simply absent (read as 0).'''
    p = getattr(c.par, 'Audiosrc', None)
    if p is None or (p.mode == ParMode.CONSTANT and not str(p.val or '').strip()):
        return None, 'off', ''
    a = p.eval()
    if a is None:
        return None, 'missing', str(p.val)
    if not a.allowCooking:
        return None, 'parked', a.name
    o = a.op('out_features') or a.op('out1')
    if o is None or o.family != 'CHOP':
        return None, 'missing', a.name + '/out_features'
    vals = {}
    for k in L().AUDIO_CHANS:
        ch = o[k]
        if ch is not None:
            vals[k] = float(ch[0])
    return vals, ('live' if vals.get('live', 0.0) >= 0.5 else 'quiet'), a.name


def _beat_sync(c, s, raw, t, bpm):
    '''Phase A (28 Oct): audio drive sources (onset beat bass mid high level tempo) + beat / onset triggers. Reads the
    audio COMP only while something uses it (Beatsync, Trigsource onset, a drive word in AUDIO_NEED); a Status note
    on every state change (parked / missing / no analysis: the sources read 0, nothing errors). -> src dict.'''
    Lg = L()
    ts = str(raw.get('Trigsource', 'manual') or 'manual')
    sync = bool(raw.get('Beatsync'))
    need = sync or ts == 'onset' or bool(s.get('m_audio'))
    if need:
        ch, state, who = _audio_chans(c)
    else:
        ch, state, who = None, 'unused', ''
    src, s['au'], ev, s['au_bpm'], bidx = Lg.audio_tick(s.get('au'), ch, absTime.seconds,
                                                        float(raw.get('Beatdecay', 6.0)))
    note = (state, who)
    if note != s.get('au_note'):
        s['au_note'] = note
        if state in AUDIO_NOTES:
            txt = AUDIO_NOTES[state]
            status(c, txt % who if '%s' in txt else txt)
    if ts != 'manual':
        if sync:
            bev, bi = ev['beat'], bidx
        else:
            bev, s['clk_beat'] = Lg.clock_beat(t, bpm, s.get('clk_beat'))
            bi = s['clk_beat']
        if Lg.trig_fire(ts, raw.get('Trigbeats', 4), bev, bi, ev['onset']):
            for k in Lg.trig_which(raw.get('Trigautowhich', 'all')):
                s['trig_t'][k] = t
    return src


def _tempo(c, raw):
    if raw.get('Tempo') == 'project':
        try:
            return float(c.time.tempo)
        except Exception:
            pass
    return float(raw.get('Bpm', 120.0))


# ------------------------------------------------------------------------------------------------- per frame
# v2 perf (T-143): the engine is event-driven. Pars, module values and effector settings are cached and patched by
# Parameter Execute callbacks (mark / mark_eff: one dict write per changed par, expressions included); the tables
# (stack, effectors) and a compiled layout swap set 'dirty_all'. Each frame only the time-dependent parts are
# recomputed (clock, drives, moving effectors, rate phases, orbit, spins), and only the engine CHOPs whose rows really
# changed are made to cook (their constant `Frame` par is bumped: _push). eng_g alone cooks every frame (Frame =
# absTime.frame). The px_tick Execute DAT runs frame() at frame start, so every CHOP sees the same frame.

ENG = (('g', 'eng_g'), ('gs', 'eng_gs'), ('e', 'eng_e'), ('m', 'eng_m'), ('r', 'eng_r'), ('q', 'eng_q'),
       ('src', 'eng_src'), ('cam', 'eng_cam'), ('pts', 'eng_pts'), ('ptsv', 'eng_ptsv'), ('trail', 'eng_trail'),
       ('glow', 'eng_glow'), ('s', 'eng_s'), ('sp', 'eng_sp'), ('info', 'eng_info'), ('ez', 'eng_ez'),
       ('pal', 'eng_pal'), ('palc', 'eng_palc'), ('h', 'eng_h'), ('hl', 'eng_hl'))
SKIP_DIRTY = ('Status', 'Sel', 'Effname', 'Presetname', 'Newname', 'Addtype', 'Effkind', 'Lightinfo', 'Current', 'Cue',
              'Cueindex', 'Addafter', 'Aqstate')
EFF_RT = '/project1/effectors/eff_rt'


def _eff_rt():
    """The shared list's runtime module (/project1/effectors/eff_rt), or None when the list is missing."""
    o = op(EFF_RT)
    try:
        return o.module if o is not None else None
    except Exception:
        return None


def _listver():
    o = op('/project1/effectors')
    p = getattr(o.par, 'Listver', None) if o is not None else None
    return p.eval() if p is not None else None


_PM = {'f': None, 'm': None}


def PM(c):
    """palette_map_logic (W1-B) = the Text DAT px_palmap, looked up once per frame."""
    f = absTime.frame
    if _PM['f'] != f or _PM['m'] is None:
        d = c.op('px_palmap')
        _PM['m'] = d.module if d is not None else None
        _PM['f'] = f
    return _PM['m']


def _lines_stops(c, rows):
    """One palette: PX's custom stops (Palstops) into PX_lines' own pal_stops table (its Palsource etc. are linked by
    expression; the table is data, so it is copied when it differs)."""
    t = c.op('PX_lines/pal_stops')
    if t is None or rows is None:
        return
    want = [[str(x) for x in r[:2]] for r in rows]
    have = [[cell.val for cell in t.row(i)][:2] for i in range(t.numRows)]
    if have != want:
        t.clear()
        for r in want:
            t.appendRow(r)


def _palette(c, s, raw, core, t, bpm, level):
    """Palette page -> (16 uPal rows, uPalCtl row); stops re-read on core edits, the shift every frame while a drive
    moves it. Also the scalar colour sources (Edge / Haze / Flare) and the glow recolour function."""
    Lg = L()
    pm = PM(c)
    if pm is None:
        return [[0.0] * 4] * 16, [0.0, 0.0, 0.0, 0.0], None, None
    if core or s.get('pal_stops') is None:
        spec, rows = Lg.palette_spec(raw)
        fhex = None
        if spec['source'] == 'file':
            try:
                path = raw.get('Palfile', '')
                data = open(path, 'rb').read() if path else b''
                fhex = pm.parse_file(path, data) if data else []
                if isinstance(fhex, tuple):
                    fhex = fhex[0]
            except Exception:
                fhex = []
        try:
            st = pm.palette_stops(spec, rows if spec['source'] == 'custom' else None, fhex)
        except Exception:
            st = []
        s['pal_stops'] = st
        s['pal_rows'] = pm.pal_rows(st)
        _lines_stops(c, rows if spec['source'] == 'custom' else None)
    st = s['pal_stops']
    drive = Lg.pal_drive(raw)
    beats = t * bpm / 60.0
    shift = pm.pal_shift(drive, max(len(st), 1), float(raw.get('Palshift', 0.0)), beats, level, beats)
    ctl = pm.pal_ctl(st, raw.get('Palmode', 'gradient'), raw.get('Palinterp', 'oklab'), shift)
    key = (id(s['pal_rows']), tuple(ctl))
    if core or s.get('pal_key') != key:
        s['pal_key'] = key
        s['pal_cols'] = Lg.scalar_colours(raw, pm.colsrc_eval, s['pal_rows'], ctl)
        s['pal_recol'] = Lg.glow_recolour(raw, pm.colsrc_eval, s['pal_rows'], ctl)
        s['pal_changed'] = True
    return s['pal_rows'], ctl, s['pal_cols'], s['pal_recol']
EFF_DYN_KINDS = ('chop', 'pts', 'actor', 'camera')


def mark(par):
    """px_dirty (Parameter Execute, every custom par of the COMP, value change): patch the cached value."""
    c = par.owner
    s = S(c)
    nm = par.name
    if nm in SKIP_DIRTY:
        return
    v = par.eval()
    if hasattr(v, 'path'):
        v = v.path
    raw = s.get('raw')
    flat = s.get('flat')
    if raw is not None and nm in raw:
        raw[nm] = v
        s['dirty_core'] = True
    elif flat is not None and nm in flat:
        flat[nm] = v
        s['dirty_mod'] = True
    else:
        s['dirty_all'] = True                     # a par the caches do not know (new page / module): re-read all


def mark_eff(par=None):
    """eff_watch (Parameter Execute on effectors/*): an effector object moved or its Effector page changed. Two
    frames of recompute: the move, then the velocity going back to 0."""
    try:
        c = par.owner.parent(2) if par is not None else C()
    except Exception:
        c = C()
    s = S(c)
    s['dirty_eff'] = 2
    if par is not None and par.page is not None and par.page.name == 'Effector':
        s['dirty_effset'] = True
        s['effset_stale'] = True


def mark_all(c=None):
    S(c or C())['dirty_all'] = True


def _refresh(c, s):
    """Full re-read (first frame, tables / layout changed, un-parked): pars, stack, layout, module values, effectors."""
    Lg = L()
    s['raw'] = raw_core(c)
    lay = [dict(il, slots=dict((k, tuple(v)) for k, v in il['slots'].items())) for il in c.fetch('px_layout', [], search=False)]
    s['lay'] = lay
    s['nrows'] = int(c.fetch('px_rows', 1, search=False))
    st = stack(c)
    s['st'] = st
    by_uid = dict((i['uid'], i) for i in st)
    s['lay_inst'] = [(il, by_uid.get(il['uid']) or Lg.new_instance(il['type'], il['uid'])) for il in lay]
    s['flat'] = flat_module_values(c, [by_uid[il['uid']] for il in lay if il['uid'] in by_uid])
    s['efft'] = eff_table(c)
    s['dirty_all'] = False
    s['dirty_core'] = s['dirty_mod'] = s['dirty_effset'] = True
    s['effset_stale'] = True
    s['dirty_eff'] = 2


def _module_vals(c, s, src, dt):
    """Module values with drives applied; the static part (values, parsed drives) is cached per module edit."""
    Lg = L()
    if s['dirty_mod'] or s.get('mcache') is None:
        mc = []
        dyn = False
        aud = False
        for il, inst in s['lay_inst']:
            v = Lg.instance_values(inst, s['flat'])
            drives, _bad = Lg.parse_drives(v.get('drive', ''))
            v = Lg.auto_vals(il['type'], v, drives)      # a drive on progress turns auto progress off (28 Oct)
            rate = any(Lg.rate_live(il['type'], v, p) for p in Lg.MODULES[il['type']]['params'])
            dyn = dyn or bool(drives) or rate
            aud = aud or (hasattr(Lg, 'drives_need_audio') and Lg.drives_need_audio(drives))
            mc.append((il, v, drives))
        s['mcache'] = mc
        s['m_dyn'] = dyn
        s['m_audio'] = aud
    vals = {}
    for il, v, drives in s['mcache']:
        vals[il['uid']] = Lg.apply_drives(v, il['type'], drives, src) if drives else v
    return vals


def frame(c=None):
    """Everything the shaders need this frame (computed once per frame, cached); bumps the engine CHOPs whose rows
    changed (_push)."""
    c = c or C()
    s = S(c)
    f = absTime.frame
    if s['frame'] == f and s['rows'] is not None:
        return s['rows']
    Lg = L()
    prev = s['rows']
    if prev is None or s.get('raw') is None or s.get('dirty_all') or f - (s.get('fprev') or f) > 3:
        _refresh(c, s)                            # > 3 frames since the last run: parked / unpulled -> re-read
    s['fprev'] = f
    s['tick_n'] = s.get('tick_n', 0) + 1            # engine frames (cooks): the sort gate counts these (T-143)
    core = s['dirty_core']
    raw = s['raw']
    now = absTime.seconds
    wall_dt = 0.0 if s['tlast'] is None else max(0.0, min(now - s['tlast'], 0.1))
    s['tlast'] = now
    dt = wall_dt * float(raw.get('Speed', 1.0)) if raw.get('Play', True) else 0.0
    s['simt'] += dt
    t = s['simt']
    if (core or s.get('static') is None) and hasattr(Lg, 'size_notes'):
        _size_check(c, s, raw)
    if core or s.get('static') is None:
        n = Lg.quality_count(raw)
        ns, na, npool = Lg.layers(raw, n)
        ne = n - ns - na - npool                       # actor echoes (wave 3, SA31)
        mode = Lg.render_mode(raw, s['splat'])
        first, drawn = Lg.sprite_range(mode, ns, na, npool, ne)
        s['static'] = {'n': n, 'side': Lg.side_for(n), 'ns': ns, 'na': na, 'npool': npool, 'mode': mode,
                       'first': first, 'drawn': drawn, 'bpm_proj': raw.get('Tempo') == 'project',
                       'spin': any(float(raw.get(k, 0.0)) != 0.0 for k in ('Aspin', 'Bspin', 'Actorspin')),
                       'depth': 'depth' in (raw.get('Amode'), raw.get('Bmode'), raw.get('Actormode')),
                       'grain': float(raw.get('Grain', 0.0)) > 0.0}
    sv = s['static']
    n, side, ns, na, npool, mode = sv['n'], sv['side'], sv['ns'], sv['na'], sv['npool'], sv['mode']
    reset = 1.0 if s['reset'] > 0 else 0.0
    if s['reset'] > 0:
        s['reset'] -= 1
    # drive sources (per frame)
    chv = _chop_vals(c, raw)
    bpm = _tempo(c, raw) if sv['bpm_proj'] else float(raw.get('Bpm', 120.0))
    env, ph, bar = Lg.beat_state(t, bpm, float(raw.get('Beatdecay', 6.0)))
    if raw.get('Trigauto'):                        # auto trigger (28 Oct): fires Trig 1-4 every N s while > 0
        fire, s['trig_auto'] = Lg.trig_auto(t, s.get('trig_auto'), raw.get('Trigauto'), raw.get('Trigautowhich', 'all'))
        for k in fire:
            s['trig_t'][k] = t
    elif s.get('trig_auto') is not None:
        s['trig_auto'] = None
    aud = _beat_sync(c, s, raw, t, bpm) if hasattr(Lg, 'audio_tick') else None   # 28 Oct phase A
    if aud is not None and raw.get('Beatsync'):
        env, ph = aud['beat'], aud['tempo']        # the beat and its phase follow the audio (0 while it is off)
    tages = [max(t - tt, 0.0) if tt > -1e8 else 1e6 for tt in s['trig_t']]
    tenv = [Lg.trig_env(a, float(raw.get('Trigdecay', 2.0))) for a in tages]
    l1 = Lg.lfo(t, float(raw.get('Lfo1rate', 0.25)), raw.get('Lfoshape', 'sine'))
    l2 = Lg.lfo(t, float(raw.get('Lfo2rate', 1.0)), raw.get('Lfoshape', 'sine'))
    # actor layer offset (+ the followed effector's centre, last frame's: it moves in effectors() below)
    aoff = [float(raw.get('Actoroffset' + k, 0.0)) for k in 'xyz']
    fol = str(raw.get('Actorfollow', '') or '')
    if fol and fol in s['eff_prev']:
        aoff = [a + b for a, b in zip(aoff, s['eff_prev'][fol])]
    avel = (0.0, 0.0, 0.0)
    if s['actor_prev'] is not None and wall_dt > 0:
        avel = tuple((a - b) / wall_dt for a, b in zip(aoff, s['actor_prev']))
    s['actor_prev'] = tuple(aoff)
    # camera + source spin (integrated: speed changes never jump). Camera position from these numbers, never from
    # pcam.worldTransform: pcam's translate reads eng_cam, so reading pcam here was a cook loop (live, 31550).
    orb = float(raw.get('Orbit', 0.0))
    s['orbit'] += math.radians(orb) * dt
    s['spin'][0] += float(raw.get('Aspin', 0.0)) * dt
    s['spin'][1] += float(raw.get('Bspin', 0.0)) * dt
    s['spin'][2] += float(raw.get('Actorspin', 0.0)) * dt
    # wave 2: the shared palette (+ its drive) and the shared effector list version
    prow, pctl, pcols, _recol = _palette(c, s, raw, core, t, bpm, chv.get('level', 0.0))
    pal_changed = s.pop('pal_changed', False)
    lv = _listver()
    list_new = lv != s.get('listver')
    if list_new:
        s['listver'] = lv
        _light_info(c)
    if pal_changed and raw.get('Glowcolsrc', 'solid') != 'solid':
        s['dirty_eff'] = max(s['dirty_eff'], 1)
    rig = hasattr(Lg, 'cam_rig_active') and Lg.cam_rig_active(raw) and c.op('cam_rig') is not None
    cam_new = core or orb != 0.0 or s.get('cam') is None or rig
    ext = _ext_cam(c, s, raw) if raw.get('Camsource', 'internal') == 'external' else None   # phase C Usecam
    if ext is None and s.get('ext_msg') and raw.get('Camsource', 'internal') != 'external':
        s['ext_msg'] = None
        status(c, 'camera: internal (orbit / Camera rig)')
    if ext is not None:                               # the external Camera COMP's pose; recomputed only when it moved
        cam_new = core or prev is None or ext[0] != s.get('cam') or ext[1] != s.get('fov_eff')
        if cam_new:
            cam = [ext[0]]
            s['cam'] = ext[0]
            s['fov_eff'] = ext[1]
            s['vp'] = Lg.cam_viewproj_row(ext[0], ext[1], raw.get('Resx', 1080), raw.get('Resy', 1920))
            s['camfwd'] = _cam_pose(ext[0])[1]
        else:
            cam = prev['cam']
    elif cam_new and rig:                               # wave 3 Camera page (cam_rig_logic): crane / dolly / path /
        CR = c.op('cam_rig').module                   # follow / director cuts on the beat, + roll / shake
        cs_ = s.setdefault('camstate', {})
        cs_['orbit_deg'] = math.degrees(s['orbit'])
        fol_ = str(raw.get('Camfollow', '') or '')
        fp = s['eff_prev'].get(fol_) if fol_ else None
        try:
            pose_ = Lg.cam_pose(raw, CR, t, t * bpm / 60.0, cs_, fp, wall_dt)
            cam = [Lg.cam_row(pose_, CR)]
        except Exception as e:                         # a bad rig value never stops the engine
            status(c, 'camera rig: %s' % e)
            cam = [list(s.get('cam') or [0.0, 0.0, 4.0, 0.0, 0.0, 0.0])]
        s['cam'] = cam[0]
        s['fov_eff'] = float(raw.get('Fov', 45.0))
        s['vp'] = Lg.cam_viewproj_row(cam[0], raw.get('Fov', 45.0), raw.get('Resx', 1080), raw.get('Resy', 1920))
        s['camfwd'] = _cam_pose(cam[0])[1]
    elif cam_new:
        d = float(raw.get('Camdist', 4.0))
        cam = [[math.sin(s['orbit']) * d, float(raw.get('Camheight', 0.0)), math.cos(s['orbit']) * d,
                math.degrees(s['orbit']), 0.0, 0.0]]
        s['cam'] = cam[0]
        s['fov_eff'] = float(raw.get('Fov', 45.0))
        s['vp'] = Lg.cam_viewproj(cam[0], raw.get('Fov', 45.0), raw.get('Resx', 1080), raw.get('Resy', 1920))
        s['camfwd'] = _cam_pose(cam[0])[1]
    else:
        cam = prev['cam']
    # camera motion for velocity_streak source camera (K25): this frame's row vs the last one over the sim dt
    if cam_new and prev is not None and prev.get('cam') and hasattr(Lg, 'cam_motion'):
        s['camvel'], s['camomega'] = Lg.cam_motion(prev['cam'][0], cam[0], dt)
    elif not cam_new:
        s['camvel'] = s['camomega'] = (0.0, 0.0, 0.0)
    # effectors: recomputed only when something can move them (motion paths, CHOP / point-set / actor / camera kinds,
    # trails, a watched object edit, actor follow); else last frame's rows stand
    efft = s['efft']
    if s['dirty_effset'] or s.get('eff_dyn') is None:
        dyn = False
        for row in efft:
            kind = row.get('kind', 'null')
            if kind in EFF_DYN_KINDS:
                dyn = True
                break
            o = _find(c, row.get('path', ''))
            st_ = Lg.eff_settings(eff_raw(o))
            if st_.get('Motion', 'none') != 'none' or int(st_.get('Trail', 0)) > 0:
                dyn = True
                break
            if o is not None and any(getattr(o.par, k).mode != ParMode.CONSTANT for k in XF if hasattr(o.par, k)):
                dyn = True                         # transform from an expression / export: watched by value anyway
                break
        s['eff_dyn'] = dyn
        s['dirty_effset'] = False
    eff_new = s['eff_dyn'] or s['dirty_eff'] > 0 or s.get('effs') is None or (fol and na > 0)
    if eff_new:
        effs = effectors(c, wall_dt, t, tuple(aoff), int(raw.get('Actorsamples', 256)))
        s['effs'] = effs
        s['dirty_eff'] = max(s['dirty_eff'] - 1, 0)
        if any(e['speed'] > 0.0 for e in effs):
            s['dirty_eff'] = max(s['dirty_eff'], 1)   # one more frame so the velocity returns to 0
    effs = s['effs']
    eff_names = [e['name'] for e in effs]
    src = dict(chv)
    src.update({'low': chv.get('low', 0.0), 'mid': chv.get('mid', 0.0), 'high': chv.get('high', 0.0),
                'level': chv.get('level', 0.0), 'beat': env, 'bar': bar, 'lfo1': l1, 'lfo2': l2, 'tempo': ph})
    if aud is not None:                            # audio sources: an Audiochop / in_ctl channel of the same name wins
        for k in ('onset', 'bass', 'mid', 'high', 'level'):
            if k not in chv:
                src[k] = aud[k]
    for k in range(4):
        src['trig%d' % (k + 1)] = tenv[k]
    for k, e in enumerate(effs):
        src['espd%d' % (k + 1)] = e['speed']
    # modules (the COMPILED layout, so rows always match the running shader)
    lay = s['lay']
    edit = bool(reset > 0.0 or prev is None or list_new)   # phase C: restarts the settle (sort only on change)
    if core or s['dirty_mod']:                         # a real value change, not a re-read after a pause / park
        sig = (dict((k, v) for k, v in raw.items() if k not in SKIP_DIRTY), dict(s.get('flat') or {}))
        if sig != s.get('motion_sig'):
            s['motion_sig'] = sig
            edit = True
    names_new = eff_names != s.get('eff_names')
    s['eff_names'] = eff_names
    mod_new = s['dirty_mod'] or s.get('m_dyn') is None or s['m_dyn'] or names_new or prev is None or list_new
    cloud_chk = s['dirty_mod'] or names_new or list_new or prev is None
    if mod_new:
        vals = _module_vals(c, s, src, dt)
        if cloud_chk and hasattr(Lg, 'stack_cloud'):  # K36: a selection reaching a cloud row needs PXE_GRID compiled
            ert_ = _eff_rt()
            items = [{'type': il['type'], 'uid': il['uid'], 'enabled': True, 'values': vals.get(il['uid']) or {}}
                     for il in lay]
            cl = bool(ert_ is not None and Lg.stack_cloud(items, eff_names, ert_.rows(), hot_name(c)))
            s['eff_pub'] = _wants_pub(ert_, items, eff_names)
            if cl != bool(s.get('cloud')):
                s['cloud'] = cl
                run("op(%r).module.stack_changed(op(%r))" % (me.path, c.path), delayFrames=1, delayRef=op.TDResources)
        s['phases'] = Lg.integrate_phases(s['phases'], lay, vals, dt)
        ert = _eff_rt()
        mrows = Lg.pack_module_rows(lay, s['nrows'], vals, eff_names, s['phases'],
                                    ert.sel_vec if ert is not None else None)
        _eff_use(c, s, lay, mrows)
    else:
        mrows = prev['m']
    s['dirty_mod'] = False
    # globals
    if raw.get('Amode') == 'file' and raw.get('Afile') and s['bounds'] is None and not s.get('load_sched'):
        s['load_sched'] = True                    # T-89: module state reset (text rewrite / reopen) -> reload once
        run("op(%r).module.load(op(%r))" % (me.path, c.path), delayFrames=2, delayRef=op.TDResources)
    if core or s.get('bb') is None or s.get('bb_src') is not s['bounds']:
        bb = s['bounds'] or Lg.gen_bounds(raw.get('Agen', 'sphere'), float(raw.get('Agenp', 1.0)), float(raw.get('Agenp2', 0.3)))
        s['bb'] = Lg.place_bounds(bb, raw.get('Ascale', 1.0), raw.get('Arot', 0.0),
                                  (raw.get('Aoffsetx', 0.0), raw.get('Aoffsety', 0.0), raw.get('Aoffsetz', 0.0)))
        s['bb_src'] = s['bounds']
        _lines_box(c, s['bb'])
    bb = s['bb']
    spec = [chv.get('s%d' % k, 0.0) for k in range(16)]
    g = {'dt': dt, 't': t, 'frame': f, 'side': side, 'count': n, 'reset': reset, 'ecount': len(effs),
         'seed': raw.get('Seed', 1), 'low': src['low'], 'mid': src['mid'], 'high': src['high'], 'level': src['level'],
         'beat': env, 'beatph': ph, 'bpm': bpm, 'bar': bar, 'trig': tenv, 'trigage': tages,
         'spring': raw.get('Spring', 4.0), 'damp': raw.get('Damping', 1.5), 'drag': raw.get('Drag', 0.2),
         'maxspeed': raw.get('Maxspeed', 0.0), 'bbc': bb[0], 'bbr': bb[1], 'campos': tuple(s['cam'][:3]),
         'heatdecay': raw.get('Heatdecay', 0.5), 'disrecover': raw.get('Disrecover', 0.0),
         'disfade': raw.get('Disfade', 1.0), 'dissize': raw.get('Dissize', 0.3), 'edgegain': raw.get('Edgegain', 2.0),
         'edgecol': (raw.get('Edgecolr', 1.0), raw.get('Edgecolg', 0.5), raw.get('Edgecolb', 0.15)),
         'bright': raw.get('Bright', 1.0), 'lfo1': l1, 'lfo2': l2, 'spec': spec,
         'viewproj': s['vp'], 'camfwd': s['camfwd'], 'nscene': ns, 'nactor': na, 'npool': npool, 'actorvel': avel,
         'necho': n - ns - na - npool, 'echoevery': raw.get('Echoevery', 6), 'echofade': raw.get('Echofade', 1.5),
         'echooff': (raw.get('Echooffsetx', 0.0), raw.get('Echooffsety', 0.0), raw.get('Echooffsetz', 0.0)),
         'camvel': s.get('camvel', (0.0, 0.0, 0.0)), 'camomega': s.get('camomega', (0.0, 0.0, 0.0))}
    grows = Lg.global_rows(g)
    gs = [[0.0] * 4 for _ in range(Lg.G_ROWS)]   # the source pass's uG: static rows only (bounds, layers), so
    gs[0][3] = float(side)                        # source cooks only when a source input changes, not per frame
    gs[1] = [float(n), 0.0, 0.0, float(raw.get('Seed', 1))]
    gs[7] = list(grows[7])
    gs[21] = list(grows[21])                          # (w = echo count: the source pass copies actor rest)
    if sv['depth'] or core or prev is None:
        dep = c.op('in_depth_pack')
        s['asp'] = (dep.width / max(dep.height, 1)) if dep is not None else 1.0   # size only, never pixels (T-74)
        if 'image' in (raw.get('Amode'), raw.get('Bmode')) and c.op('pts_sel') is not None:   # wave 4 K27: the
            im_ = c.op('pts_sel')                                                          # picture's aspect
            s['asp'] = im_.width / max(im_.height, 1)
    _motion(c, s, raw, dt, effs, sv, na, edit or names_new)
    sorts = _sort_gate(c, raw, mode, f, s['st'], side * side)
    _actor_tick(c, raw, t)
    if core or prev is None:
        aqv = s.get('aqv') or AQ_FULL                  # phase C auto quality: the rows see the step, the pars stay
        rx = Lg.aq_raw(raw, aqv[1], aqv[2]) if hasattr(Lg, 'aq_raw') else raw
        prx, pry = Lg.proj_res(rx) if hasattr(Lg, 'proj_res') else (None, None)   # wave 4 K26: cube faces
        svec, ssp = Lg.splat_rows(rx, n, prx, pry, ns=ns, na=na, sortoff=raw.get('Sortmode', 'auto') == 'off')
        nse, nae, npe = Lg.layers(raw, n)
        echo_ = (nse + nae + npe, nae) if Lg.echo_count(raw, nae) > 0 and nae > 0 else None
        try:
            rrows = Lg.render_rows(rx, side, n, prx, pry, first=sv['first'], end=sv['first'] + sv['drawn'], echo=echo_)
        except TypeError:                             # an older px_logic text (no echo row)
            rrows = Lg.render_rows(rx, side, n, first=sv['first'], end=sv['first'] + sv['drawn'])
        _aq_write(c, s, ns + na)
    else:
        svec, ssp, rrows = prev['s'], prev['sp'], prev['r']
    qrows = Lg.post_rows(raw, 0) if (core or prev is None or pal_changed) else prev['q']   # grain: uQf expression
    if pcols is not None:                             # Edge / Haze / Flare colour sources (solid = the pars)
        Lg.apply_scalar_colours(grows, qrows, pcols)
    if core or sv['spin'] or sv['depth'] or fol or prev is None:
        srows = Lg.source_rows(raw, side, n, s['spin'][0], s['spin'][1], s['asp'], s['spin'][2], aoff)
    else:
        srows = prev['src']
    rows = {'g': grows, 'gs': gs, 'e': Lg.effector_rows(effs) if eff_new else prev['e'], 'm': mrows, 'r': rrows,
            'q': qrows, 'src': srows, 'cam': [list(cam[0][:6]) + [float(s.get('fov_eff', raw.get('Fov', 45.0)))]],
            'pts': s['pts_rows'], 'ptsv': s['ptsv_rows'], 'trail': s['trail_rows'], 'glow': s['glow_rows'],
            's': svec, 'sp': ssp, 'ez': EZ_ROWS,
            'pal': prow, 'palc': [pctl],
            'h': _haze_rows(c, s, raw if ext is None else dict(raw, Fov=ext[1]), core or cam_new or prev is None, prev),
            'hl': s.get('hl_rows', HL_ZERO),
            'info': [[float(n), float(side), float(len(lay)), float(len(effs)), float(_aq_drawn(s, sv['drawn'])),
                      1.0 if mode == 'splats' else 0.0, float(s['glow_n']), float(_sorts_shown(s, sorts))]]}
    s['dirty_core'] = False
    s['rows'] = rows
    s['frame'] = f
    if eff_new:
        _gizmos(c, effs)
    if s.get('morph'):
        _morph_tick(c)
    _push(c, s, rows, prev)
    return rows


def _size_check(c, s, raw):
    """Phase B hard limits: a size par past its limit runs clamped (px_logic.size_notes); Status says so once per
    change ('Count 80M -> clamped to 2.68M (8192 px state texture)'), the user's value stays as typed."""
    pl = c.op('PX_lines')
    ms = getattr(pl.par, 'Maxseg', None) if pl is not None else None
    try:
        notes = L().size_notes(raw, int(ms.eval()) if ms is not None else None)
    except Exception:
        return
    if notes != s.get('size_notes'):
        had = s.get('size_notes')
        s['size_notes'] = notes
        if notes:
            status(c, 'size: ' + '; '.join(notes))
            note(c, 'size', '; '.join(notes))
        elif had:
            status(c, 'size: every size inside its limit again')


def _eff_texels():
    """The shared packed buffer as a list of 4-float texels (eff_rows CHOP values; no TOP reads, T-74)."""
    o = op('/project1/effectors/eff_rows')
    if o is None or o.numChans < 4:
        return []
    try:
        cols = [o[n].vals for n in ('x', 'y', 'z', 'w')]
    except Exception:
        return []
    return [(cols[0][i], cols[1][i], cols[2][i], cols[3][i]) for i in range(len(cols[0]))]


def _haze_lights(raw):
    """Light blocks (W1-A, 7 texels each) of the lights Vhlights selects, in list order (max 8 in the haze)."""
    ert = _eff_rt()
    if ert is None:
        return []
    tex = _eff_texels()
    try:
        el = ert.L()
        k = el.light_count(tex)
        rows_sel = set(el.selected(ert.rows(), raw.get('Vhlights', 'all') or 'all'))
        out = []
        for i in range(k):
            b = el.read_light(tex, i)
            if int(round(b[2][3])) in rows_sel:
                out.append(b)
        return out
    except Exception:
        return []


HZ_ZERO = [[0.0] * 4] * 13
HL_ZERO = [[0.0] * 4] * 40


def _haze_rows(c, s, raw, recompute, prev):
    """uH[13] + uHL[40] (W1-D px_haze_logic) from the Haze page, PX's camera and the light effectors. Only while Vhon;
    lights re-read every frame while it is on (a moved light shows next frame), rows pushed only when they change."""
    if not L()._truthy(raw.get('Vhon', False)):
        s['hl_rows'] = HL_ZERO
        return prev['h'] if (prev is not None and 'h' in prev) else HZ_ZERO
    d = c.op('px_hazelogic')
    if d is None:
        return HZ_ZERO
    hz = d.module
    blocks = _haze_lights(raw)
    lr, n = hz.light_rows(hz.lights_from_block(blocks))
    s['hl_rows'] = lr if (prev is None or prev.get('hl') != lr) else prev['hl']
    if recompute or n != s.get('hl_n') or prev is None or 'h' not in prev:
        s['hl_n'] = n
        row_ = s['cam']
        if len(row_) > 5 and (row_[4] or row_[5]):     # wave 3 rigs: the full camera basis
            pos_, rt_, up_, fw_ = L().cam_basis(row_)
            asp = float(raw.get('Resx', 1080)) / max(float(raw.get('Resy', 1920)), 1.0)
            fy = math.degrees(2.0 * math.atan(math.tan(math.radians(float(raw.get('Fov', 45.0))) * 0.5) / asp))
            cam = hz.camera(list(pos_), list(rt_), list(up_), list(fw_), fy, asp)
        else:
            cam = hz.camera_from_px(row_, raw.get('Fov', 45.0), raw.get('Resx', 1080), raw.get('Resy', 1920))
        return hz.haze_rows(L().haze_params(raw), cam, n)
    return prev['h']


def _light_info(c):
    ert = _eff_rt()
    txt = 'no /project1/effectors'
    if ert is not None:
        try:
            ls = [r['name'] for r in ert.rows() if r.get('kind') == 'light' and str(r.get('enabled', '1')) not in ('0', '')]
            txt = '%d lights on: %s' % (len(ls), ' '.join(ls)[:180]) if ls else '0 lights (Addlight)'
        except Exception:
            pass
    p = getattr(c.par, 'Lightinfo', None)
    if p is not None and p.eval() != txt:
        p.val = txt


def add_light(c, name=None, ltype=None, colour=None, intensity=None, pos=None, tags='px'):
    """Lights page Addlight: a light effector in /project1/effectors (kind light, tag px) at Addlpos; adds a `light`
    module to the stack when there is none, so the light shows on the points / splats at once."""
    ert = _eff_rt()
    if ert is None:
        status(c, 'Addlight: /project1/effectors is missing')
        return None
    r = c.par
    nm = ert.add('light', name, tags=tags, type=ltype or r.Addltype.eval(),
                 colour=tuple(colour or (r.Addlcolourr.eval(), r.Addlcolourg.eval(), r.Addlcolourb.eval())),
                 intensity=float(intensity if intensity is not None else r.Addlintensity.eval()))
    o = op('/project1/effectors/' + nm)
    if o is not None:
        for k, v in zip(('tx', 'ty', 'tz'), pos or (r.Addlposx.eval(), r.Addlposy.eval(), r.Addlposz.eval())):
            getattr(o.par, k).val = float(v)
    if not any(i['type'] == 'light' and i['enabled'] for i in stack(c)):
        add(c, 'light')
    _light_info(c)
    return nm


GEO_SOPS = {'box': boxSOP, 'sphere': sphereSOP, 'torus': torusSOP, 'plane': gridSOP, 'tube': tubeSOP}


def add_geo(c, name=None, kind=None, colour=None, metal=None, rough=None, emit=None, xform=None):
    """Geo page Geoadd: a Geometry COMP in PX's geo/ (shape + PBR MAT), appended to Geocomps, Geoon on. It renders
    in the same frame as the splats / sprites (occlusion both ways), lit by Geolights (the light effectors)."""
    r = c.par
    holder = c.op('geo') or c.create(baseCOMP, 'geo')
    holder.comment = 'Geometry objects in the PX scene (Geo page): move / rotate / scale them.'
    k = 1
    while name is None or holder.op(name) is not None:
        name = 'G%d' % k
        k += 1
    kind = kind or r.Geoaddkind.eval()
    g = holder.create(geometryCOMP, name)
    for ch in list(g.children):
        _sd(ch)
    sop = g.create(GEO_SOPS.get(kind, sphereSOP), 'shape')
    if kind == 'plane':
        sop.par.sizex, sop.par.sizey = 4, 4
        sop.par.orient = 'zx'
    elif kind == 'sphere':
        sop.par.radx = sop.par.rady = sop.par.radz = 0.3
    elif kind == 'box':
        sop.par.sizex = sop.par.sizey = sop.par.sizez = 0.4
    elif kind == 'torus':
        sop.par.radx, sop.par.rady = 0.35, 0.08
    elif kind == 'tube':
        sop.par.rad1 = sop.par.rad2 = 0.08
        sop.par.height = 2.0
    sop.render = sop.display = True
    m = holder.create(pbrMAT, name + '_mat')
    col = colour or (r.Geoaddcolourr.eval(), r.Geoaddcolourg.eval(), r.Geoaddcolourb.eval())
    for nm, v in (('basecolorr', col[0]), ('basecolorg', col[1]), ('basecolorb', col[2]),
                  ('metallic', metal if metal is not None else r.Geoaddmetal.eval()),
                  ('roughness', rough if rough is not None else r.Geoaddrough.eval())):
        p = getattr(m.par, nm, None)
        if p is not None:
            p.val = float(v)
    e = float(emit if emit is not None else r.Geoaddemit.eval())
    for nm, v in (('emitr', col[0] * e), ('emitg', col[1] * e), ('emitb', col[2] * e)):
        p = getattr(m.par, nm, None)
        if p is not None:
            p.val = v
    g.par.material = m.path
    for kk, v in (xform or {}).items():
        getattr(g.par, kk).val = v
    g.viewer = True
    toks = str(r.Geocomps.eval() or '').split()
    if g.path not in toks:
        r.Geocomps = ' '.join(toks + [g.path])
    if not r.Geoon.eval():
        r.Geoon = True
    geo_sync(c)
    return g.path


def geo_lights(c, root='/project1/effectors', env=None):
    """geo_render's `lights` (W1-E recipe, PX names): Geolights resolved (#light = the light effectors) + geo_key."""
    cands = []
    eff = op(root)
    if eff is not None:
        for o in eff.findChildren(type=lightCOMP, maxDepth=2):
            cands.append((o.path, list(o.tags)))
    sl = c.op('splat_logic')
    if sl is None:
        return ''
    out = sl.module.resolve_lights(c.par.Geolights.eval(), cands).split()
    if c.par.Geokey.eval() and c.op('geo_key') is not None:
        out.append(c.op('geo_key').path)
    if getattr(c.par, 'Geoenv', None) is not None and c.par.Geoenv.eval() and c.op('geo_env_light') is not None:
        out.append(c.op('geo_env_light').path)      # wave 4 GE3: scene reflections on the PBR objects
    return ' '.join(out)


def geo_sync(c):
    """Geo adapter text in front of PX's splat shader (Geoon) or out of it (off = the exact old text) + the MAT's uGeo
    block (W1-E geo_sync with PX's op names; uGeo = (0 relight: PX relights with its light module, 0, 0, depth bias))."""
    sl = c.op('splat_logic')
    ad = c.op('splat_geo_adapter')
    dat = c.op('smat_glsl')
    m = c.op('smat')
    if sl is None or ad is None or dat is None or m is None or getattr(c.par, 'Geoon', None) is None:
        return 'geo: not built'
    on = bool(c.par.Geoon.eval())
    t = sl.module.geo_patch(dat.text, ad.text, on)
    if dat.text != t:
        dat.text = t
    k = None
    for i in range(int(m.seq.vec.numBlocks)):
        if getattr(m.par, 'vec%dname' % i).eval() == 'uGeo':
            k = i
    if on and k is None:
        m.seq.vec.numBlocks = int(m.seq.vec.numBlocks) + 1
        k = int(m.seq.vec.numBlocks) - 1
    if k is not None:
        getattr(m.par, 'vec%dname' % k).val = 'uGeo' if on else ''
        for ax in 'xyz':
            q = getattr(m.par, 'vec%dvalue%s' % (k, ax))
            q.mode = ParMode.CONSTANT
            q.val = 0.0
        q = getattr(m.par, 'vec%dvaluew' % k)
        if on:
            q.expr = 'parent().par.Geodepthbias'
            q.mode = ParMode.EXPRESSION
        else:
            q.mode = ParMode.CONSTANT
            q.val = 0.0
    return ''


def _sorts_shown(s, sorts):
    """eng_info's sorts readout, refreshed every 30 engine frames: eng_info drives the render / switch expressions,
    so a per-sort change made all of them re-evaluate every other frame (T-143)."""
    if s.get('sorts_shown') is None or s.get('tick_n', 0) % 30 == 0:
        s['sorts_shown'] = sorts
    return s['sorts_shown']


EZ_ROWS = [[0.0, 0.0, 0.0, 0.0]] * 88             # zero uE / texture buffers for the source pass (it reads none)


def _push(c, s, rows, prev):
    """Make the engine CHOPs whose rows changed cook (constant Frame par bumped); eng_g cooks every frame anyway."""
    ver = s.setdefault('ver', {})
    for key, nm in ENG:
        if key == 'g':
            continue
        if prev is not None and key in prev and prev[key] is rows[key]:
            continue                               # not recomputed this frame
        if prev is not None and key in prev and prev[key] == rows[key]:
            continue
        o = c.op(nm)
        if o is None:
            continue
        p = getattr(o.par, 'Frame', None)
        if p is None or p.mode != ParMode.CONSTANT:
            continue                               # an older build (Frame = absTime.frame): cooks every frame
        ver[key] = ver.get(key, 0) + 1
        p.val = ver[key] % 1000000


def tick(c=None):
    """px_tick (Execute DAT, onFrameStart): run frame() before any cook while the COMP is being pulled (update
    cooked since the last tick), so every engine CHOP reads the same frame. Idle COMPs cost one compare."""
    c = c or C()
    s = S(c)
    u = c.op('update')
    tc = u.totalCooks if u is not None else 0
    if tc != s.get('tick_tc') or s['rows'] is None:
        s['tick_tc'] = tc
        if not s.get('inst_checked'):               # phase B: a pasted copy fixes itself up on its first cook
            s['inst_checked'] = True
            try:
                instance_check(c)
            except Exception as e:
                status(c, 'instance check: %s' % e)
            try:
                _hot_sync(c, hot_want(c))       # 29 Oct: a loaded / pasted PX: its hot row on only if its grid is
            except Exception as e:              # (once per session, no per-frame work)
                status(c, 'hot row: %s' % e)
        _cooking(c, s)
        import time as _t
        t0 = _t.perf_counter()
        frame(c)
        _aq_tick(c, s)
        ms = (_t.perf_counter() - t0) * 1000.0
        h = s.setdefault('tick_ms', [])
        h.append(ms)
        if len(h) > 240:
            del h[:120]


# ------------------------------------------------------------------------------------------------- PX instances (phase B)
# Several PX COMPs in one project (a copy-paste, PX_pointfx1 in main): each keeps its own row names in the shared list
# and its own references; a warning when two cook at once (each costs its full frame budget).

def _registry():
    """{PX path: last engine frame}, shared by every PX's px_rt (a module in sys.modules: per-PX modules have their
    own globals; plain data only)."""
    import sys
    import types
    m = sys.modules.get('_jz_px_cooking')
    if m is None:
        m = types.ModuleType('_jz_px_cooking')
        m.d = {}
        sys.modules['_jz_px_cooking'] = m
    return m.d


def _cooking(c, s):
    reg = _registry()
    f = absTime.frame
    reg[c.path] = f
    if f - s.get('reg_f', -10 ** 9) < 60:
        return
    s['reg_f'] = f
    live = []
    for p_, fr in list(reg.items()):
        if f - fr > 600:
            reg.pop(p_, None)
        elif f - fr <= 5:
            o = op(p_)
            if o is not None and o.allowCooking:
                live.append(p_)
    live = sorted(live)
    if len(live) > 1 and live != s.get('multi'):
        s['multi'] = live
        txt = '%d PX cooking: %dx cost (%s)' % (len(live), len(live), ', '.join(x.split('/')[-1] for x in live))
        status(c, txt)
        note(c, 'cost', txt)
    elif len(live) <= 1 and s.get('multi'):
        s['multi'] = None


def px_instances(root='/'):
    """Every PX COMP in the project (a COMP holding px_rt + px_stack + px_presets)."""
    out = []
    r = op(root)
    if r is None:
        return out
    for d in r.findChildren(name='px_rt', type=textDAT):
        p_ = d.parent()
        if p_ is not None and p_.op('px_stack') is not None and p_.op('px_presets') is not None:
            out.append(p_)
    return out


STRUCT_PARS = ('winop', 'Geocomps')


def _swap_refs(c, old, generic):
    """References into `old` (another PX path) -> this PX. generic (a pasted copy: everything was copied verbatim):
    every constant string par of PX and its children (3 levels) that names old/...; else only what a copy always
    carries (controls_window winop, Geocomps, PX_lines' pars) and only when the same child exists here.
    -> ['<op>:<par>' changed]."""
    Lg = L()
    done = []
    pl = c.op('PX_lines')
    if generic:
        ops_ = [c] + list(c.findChildren(maxDepth=3))
    else:
        ops_ = [o for o in (c, c.op('controls_window'), pl) if o is not None]
    for o in ops_:
        top = o.path == c.path or (pl is not None and o.path == pl.path)
        for p in (o.customPars if top else o.pars()):
            try:
                if p.mode != ParMode.CONSTANT or p.readOnly or getattr(p, 'isPulse', False):
                    continue
                v = p.val
                if not isinstance(v, str) or old not in v:
                    continue
                if not generic and o.path == c.path and p.name not in STRUCT_PARS:
                    continue
                nv, ch = Lg.path_swap(v, old, c.path)
                if not ch:
                    continue
                if not generic:
                    tails = [t[len(c.path) + 1:] for t in nv.split() if t.startswith(c.path + '/')]
                    if not tails or any(c.op(t) is None for t in tails):
                        continue
                p.val = nv
                done.append('%s:%s' % (o.path[len(c.path):] or '.', p.name))
            except Exception:
                continue
    # table cells: a copied zkit panel's zk_cfg 'target' (its knobs drove the ORIGINAL) and, for a pasted copy, any
    # other table that names the original's children. The looks (px_presets), notes and setlist are never touched.
    tabs = [t for t in c.findChildren(type=tableDAT, maxDepth=3)
            if t.name not in ('px_presets', 'px_notes', 'px_setlist') and (generic or t.name == 'zk_cfg')]
    for t in tabs:
        try:
            for r in range(t.numRows):
                for k in range(t.numCols):
                    v = t[r, k].val
                    if old not in v:
                        continue
                    if not generic and not (k == 1 and t[r, 0].val == 'target'):
                        continue
                    nv, ch = Lg.path_swap(v, old, c.path)
                    if ch:
                        t[r, k] = nv
                        done.append('%s[%d,%d]' % (t.path[len(c.path):], r, k))
        except Exception:
            continue
    return done


def instance_check(c):
    """Phase B, once per PX (first cook, and phaseB_upgrade). Storage 'px_inst' = {key, path}:
    - no record (a PX from before phase B): key = px_hot_<name>; the legacy 'px_hot' row is renamed to it when its ref
      is this PX's hot_pts; references to another PX's controls / geo / lines objects (an earlier copy-paste) come home;
    - record path = another live PX holding the same key: this is a pasted COPY -> a new key, and every reference to
      the original's children points here;
    - record path gone (the COMP was renamed / moved): key kept, the hot row's ref follows.
    -> {key, was, refs, renamed}."""
    Lg = L()
    rec = c.fetch('px_inst', None, search=False)
    out = {'key': None, 'was': None, 'refs': [], 'renamed': None}
    if isinstance(rec, dict) and rec.get('path') == c.path and rec.get('key'):
        out['key'] = rec['key']
        return out
    others = [o for o in px_instances() if o.path != c.path]
    keys = [(o.fetch('px_inst', None, search=False) or {}).get('key') for o in others]
    ert = _eff_rt()
    rows_ = list(ert.rows()) if ert is not None else []
    mine_ref = c.path + '/hot_pts'
    if isinstance(rec, dict) and rec.get('path') and rec.get('key'):
        orig = op(rec['path'])
        is_copy = (orig is not None and orig.path != c.path and orig.op('px_rt') is not None
                   and (orig.fetch('px_inst', None, search=False) or {}).get('key') == rec['key'])
        is_copy = is_copy or rec['key'] in keys        # 29 Oct: two loads of one tox (the original's path gone here)
        out['was'] = rec['path']
        out['refs'] = _swap_refs(c, rec['path'], True)
        if is_copy:
            key = Lg.hot_key(c.name, [k for k in keys if k] + [r['name'] for r in rows_])
        else:
            key = rec['key']
            if ert is not None and any(r['name'] == key for r in rows_):
                try:
                    ert.set_value(key, 'ref', mine_ref)
                except Exception:
                    pass
    else:
        taken = [k for k in keys if k] + [r['name'] for r in rows_ if r.get('ref') != mine_ref]
        key = Lg.hot_key(c.name, taken)
        legacy = [r for r in rows_ if r['name'] == HOT_ROW and r.get('ref') == mine_ref]
        if legacy and ert is not None:
            try:
                ert.rename(HOT_ROW, key)
                out['renamed'] = '%s -> %s' % (HOT_ROW, key)
            except Exception as e:
                out['renamed'] = 'rename failed: %s' % e
        for o in others:
            out['refs'] += _swap_refs(c, o.path, False)
    c.store('px_inst', {'key': key, 'path': c.path})
    out['key'] = key
    if out['refs'] or out['renamed'] or out['was']:
        note(c, 'instance', json.dumps(out, sort_keys=True))
    S(c)['dirty_all'] = True
    return out


# ------------------------------------------------------------------------------------------------- phase C (28 Oct)
# Usecam, sort only on change, auto quality. Manual wins: nothing here writes a user par (Aqstate / Status only).

AQ_FULL = (False, 1.0, 1.0)                          # (force splat AA 1x, point fraction, resolution fraction)


def _ext_cam(c, s, raw):
    """Camsource external: (engine camera row, horizontal fov) of the Camcomp Camera COMP, from its world transform
    and its projection at PX's Resx x Resy; None (internal camera, one Status note) when it is not a Camera COMP."""
    path = str(raw.get('Camcomp', '') or '').strip()
    o = None
    if path:
        o = op(path) if path.startswith('/') else c.op(path)
    if o is None or getattr(o, 'OPType', '') != 'cameraCOMP':
        msg = 'camera: Camcomp %s is not a Camera COMP: internal camera' % (path or '(empty)')
        if s.get('ext_msg') != msg:
            s['ext_msg'] = msg
            status(c, msg)
        return None
    try:
        m = o.worldTransform
        p0 = m * tdu.Position(0.0, 0.0, 0.0)
        ax = [m * tdu.Vector(1.0, 0.0, 0.0), m * tdu.Vector(0.0, 1.0, 0.0), m * tdu.Vector(0.0, 0.0, 1.0)]
        row = L().basis_row((p0.x, p0.y, p0.z), *[(v.x, v.y, v.z) for v in ax])
        rx, ry = L().aq_res(raw.get('Resx', 1080), raw.get('Resy', 1920))
        try:
            fov = L().hfov_from_proj(o.projection(rx, ry)[0, 0])
        except Exception:
            fov = float(o.par.fov.eval())
    except Exception as e:                           # never stops the engine
        msg = 'camera: %s: %s' % (path, e)
        if s.get('ext_msg') != msg:
            s['ext_msg'] = msg
            status(c, msg)
        return None
    if s.get('ext_msg') != 'ok ' + path:
        s['ext_msg'] = 'ok ' + path
        status(c, 'camera: following %s' % path)
    return row, fov


def _motion(c, s, raw, dt, effs, sv, na, edit):
    """Sort only on change (Sortstill, Sortmode auto): s['moving'] = can the centres move now, or did anything change
    within the settle time (px_logic.settle_s)? The camera has its own gate (Sortmovedeg) in _sort_gate."""
    Lg = L()
    if not hasattr(Lg, 'stack_motion') or not Lg._truthy(raw.get('Sortstill', False)):   # no par yet = old rule
        s['moving'] = None                           # the old rule: every N frames while a module CAN move centres
        return
    items = [(il['type'], v, d) for il, v, d in (s.get('mcache') or [])]
    effmv = any(e.get('speed', 0.0) > 0.0 for e in effs)
    srcmv = bool(sv.get('spin') or sv.get('depth') or na > 0)
    now = absTime.seconds
    mv = Lg.stack_motion(items, dt, effmv, srcmv)
    if edit and dt <= 0.0 and not mv:
        s['sort_dirty'] = True                       # paused: an edit moves points once (no settling): one re-sort
    elif mv or edit:
        s['motion_t'] = now
    s['moving'] = (now - s.get('motion_t', -1e9)) < Lg.settle_s(raw)


def _aq_drawn(s, drawn):
    """Sprite instances at the auto-quality point fraction (px_vert strides by 1 / fraction)."""
    cf = (s.get('aqv') or AQ_FULL)[1]
    return int(math.ceil(drawn * cf - 1e-9)) if (cf < 1.0 and drawn > 0) else drawn


def _aq_write(c, s, end):
    """px_auto (Constant CHOP) = the active step: aa (1 = splat MSAA forced to 1x), countf, resf, kside (sort-key
    texture side at countf). Written only when a value changes (its readers re-evaluate then, never per frame)."""
    a = c.op('px_auto')
    if a is None:
        return
    aa, cf, rf = s.get('aqv') or AQ_FULL
    want = {'aa': 1.0 if aa else 0.0, 'countf': float(cf), 'resf': float(rf),
            'kside': float(L().aq_key_side(end, cf)) if hasattr(L(), 'aq_key_side') else 1.0}
    if s.get('aq_written') == want:
        return
    for i in range(int(a.seq.const.numBlocks)):
        nm = getattr(a.par, 'const%dname' % i).eval()
        if nm in want:
            p = getattr(a.par, 'const%dvalue' % i)
            if p.eval() != want[nm]:
                p.val = want[nm]
    s['aq_written'] = want


def _aqstate(c, txt):
    p = getattr(c.par, 'Aqstate', None)
    if p is not None and p.eval() != txt:
        ro = p.readOnly
        p.readOnly = False
        p.val = txt[:200]
        p.readOnly = ro


def _aq_apply(c, s, raw, eff, label):
    s['aqv'] = tuple(eff)
    st_ = s.get('static') or {}
    _aq_write(c, s, int(st_.get('ns', 0)) + int(st_.get('na', 0)))
    s['dirty_core'] = True                           # render / splat rows at the new step next frame
    s['sort_dirty'] = True                           # a new key texture size: re-sort once
    _aqstate(c, label)
    if label != 'off':
        status(c, 'auto quality: ' + label)


def _aq_governor(c, s, raw):
    """Autoquality governor: the step comes from FG_fps_governor's quality channel (Govop); missing, parked or Active
    off = quality 1 (full), one Status note per state. A channel read per frame; px_auto changes only on a new step."""
    Lg = L()
    path = str(raw.get('Govop', '') or '').strip()
    g = op(path) if path.startswith('/') else (c.op(path) if path else None)
    q, why = 1.0, ''
    try:
        if g is None:
            why = 'governor %s missing: full quality' % (path or '(empty)')
        elif not g.parent().allowCooking or (getattr(g.parent().par, 'Active', None) is not None
                                             and not g.parent().par.Active.eval()):
            why = 'governor %s parked / Active off: full quality' % g.parent().name
        else:
            ch = g['quality']
            q = float(ch[0]) if ch is not None else 1.0
    except Exception as e:
        q, why = 1.0, 'governor: %s' % e
    s['aq'] = None
    eff = Lg.gov_plan(q)
    key = (eff, why)
    if key != s.get('gov_key'):
        s['gov_key'] = key
        txt = Lg.aq_label([AQ_FULL, eff], 1).split(': ', 1)[-1] if tuple(eff) != AQ_FULL else 'full quality'
        label = why or ('governor quality %.2f: %s' % (q, txt))
        s['aq_label'] = label
        _aq_apply(c, s, raw, eff, label)


def _aq_tick(c, s):
    """Autoquality hold60: one controller step per engine frame from the Perform CHOP px_perf (fps, msec; read only
    while auto is on, so it cooks only then). px_logic.aq_step decides; a step changes px_auto + the rows, never a par."""
    Lg = L()
    raw = s.get('raw')
    if raw is None or not hasattr(Lg, 'aq_step'):
        return
    if raw.get('Autoquality', 'off') == 'governor' and hasattr(Lg, 'gov_plan'):
        _aq_governor(c, s, raw)
        return
    if raw.get('Autoquality', 'off') != 'hold60':
        if s.get('aq') is not None or (s.get('aqv') or AQ_FULL) != AQ_FULL:
            s['aq'] = None
            _aq_apply(c, s, raw, AQ_FULL, 'off')
        elif s.get('aq_label') != 'off':
            _aqstate(c, 'off')
        s['aq_label'] = 'off'
        s['gov_key'] = None
        return
    s['gov_key'] = None
    pf = c.op('px_perf')
    if pf is None:
        return
    try:
        fps, ms = float(pf['fps'].eval()), float(pf['msec'].eval())
    except Exception:
        return
    steps = Lg.aq_steps(raw, (s.get('static') or {}).get('mode') == 'splats')
    st, d = Lg.aq_step(s.get('aq'), fps, ms, absTime.seconds, len(steps), float(raw.get('Aqfps', 57.0)),
                       int(raw.get('Aqframes', 45)), float(raw.get('Aqheadroom', 10.0)))
    if st['level'] > len(steps) - 1:
        st['level'] = len(steps) - 1
    s['aq'] = st
    eff = Lg.aq_effect(steps, st['level'])
    if d != 0 or tuple(eff) != (s.get('aqv') or AQ_FULL) or s.get('aq_label') in (None, 'off'):
        res = Lg.aq_res(raw.get('Resx', 1080), raw.get('Resy', 1920), eff[2]) if eff[2] < 1.0 else None
        label = Lg.aq_label(steps, st['level'], res, fps)
        s['aq_label'] = label
        _aq_apply(c, s, raw, eff, label)


def _cam_pose(row):
    """(position, forward) of the output camera from its orbit numbers (tx ty tz ry deg), pure maths: pcam reads
    eng_cam, so reading pcam.worldTransform from the engine cook was a cook loop (live 31550, T-113)."""
    if not row:
        return (0.0, 0.0, 5.0), (0.0, 0.0, -1.0)
    if len(row) > 5 and (float(row[4]) != 0.0 or float(row[5]) != 0.0):
        b = L().cam_basis(row)                         # wave 3 rigs: pitch / roll
        return b[0], b[3]
    a = math.radians(float(row[3]))
    return (float(row[0]), float(row[1]), float(row[2])), (-math.sin(a), 0.0, -math.cos(a))


def _sort_prime(c, so):
    """29 Oct: in sprites mode the sorter never cooked in a fresh session (TD does not save POP data), so sgeo's
    instancing warned "instance attribute 'pid(0)' could not be found in sorter/sorted". Cook the sorter ONCE (un-park,
    pull `sorted`, park the next frame through sorter_on): the order is valid from the first frame a splat render
    needs it. No POP data is read back."""
    s = S(c)
    s['sort_primed'] = True
    fin = so.op('sorted')
    if fin is None:
        return
    so.allowCooking = True
    s['sorter_on'] = True
    try:
        fin.cook(force=True)
    except Exception as e:
        status(c, 'sort prime: %s' % e)


def _sort_gate(c, raw, mode, f, st, slots):
    """S1: un-park the sorter COMP (sort_keys -> TOP to POP -> Sort POP) on frames the splat order must be rebuilt
    (px_logic.sort_due with the BL camera gate splat_logic.need_sort); park it again the next frame, so the last
    sorted POP keeps feeding the splat instancing. Sprites mode: parked. Returns the number of sorts so far."""
    s = S(c)
    so = c.op('sorter')
    if so is None:
        return s['sorts']
    if mode != 'splats':
        if s['sorter_on']:
            so.allowCooking = False
            s['sorter_on'] = False
        elif not s.get('sort_primed'):
            _sort_prime(c, so)                     # once per session: sorter/sorted holds pid (no sgeo warning)
        return s['sorts']
    Lg = L()
    sm = raw.get('Sortmode', 'auto')
    pos, fwd = _cam_pose(s.get('cam'))
    srl = _logic_dat(c, 'splat_logic')
    rad = (s['bounds'] or ((0, 0, 0), 1.0))[1]
    cam_due = srl.need_sort('sortpop', f, s['sort_last'] if s['sort_last'] is not None else -1, 0, fwd,
                            s['sort_fwd'], pos, s['sort_pos'], float(raw.get('Sortmovedeg', 1.0)), rad) \
        if srl is not None else True
    now = absTime.seconds
    st_t = s.get('sort_t')
    moving = s['moving'] if s.get('moving') is not None else Lg.stack_moves(st)   # phase C: sort only on change
    due = Lg.sort_due(sm, s.get('tick_n', f), s['sort_last'], int(raw.get('Sorteveryn', 6)), moving, cam_due,
                      pulse=s['sortnow'], data_changed=s['sort_dirty'], since_s=None if st_t is None else now - st_t,
                      max_hz=float(raw.get('Sortmaxhz', 20.0)))
    if due:
        s['sort_primed'] = True
        sc = so.op('sort_cam')
        row = s.get('cam')
        if sc is not None and row:                 # pcam's pose from the engine's numbers (pcam.par reads eng_cam)
            rx_, rz_ = (row[4], row[5]) if len(row) > 5 else (0.0, 0.0)
            for k, v in zip(('tx', 'ty', 'tz', 'rx', 'ry', 'rz'), (row[0], row[1], row[2], rx_, row[3], rz_)):
                getattr(sc.par, k).val = float(v)
        so.allowCooking = True
        s['sorter_on'] = True
        s['sort_last'], s['sort_fwd'], s['sort_pos'] = s.get('tick_n', f), fwd, pos
        s['sort_t'] = now
        s['sortnow'] = False
        s['sort_dirty'] = False
        s['sorts'] += 1
    elif s['sorter_on'] and sm != 'always':
        so.allowCooking = False                    # keeps the last sorted order (LIVE CHECK P9)
        s['sorter_on'] = False
    return s['sorts']


def _actor_tick(c, raw, t):
    """A4 sequences: when the frame index changes, re-upload rest_actor next frame (run(), never inside a cook)."""
    s = S(c)
    fr = s['actor_frames']
    if raw.get('Actormode') != 'file' or len(fr) < 2:
        return
    k = L().actor_frame(t, float(raw.get('Actorfps', 24.0)), len(fr))
    if k != s['actor_idx']:
        s['actor_idx'] = k
        ra = c.op('rest_actor')
        if ra is not None:
            run("op(%r).cook(force=True)" % ra.path, delayFrames=1, delayRef=op.TDResources)


INFO_CHANS = ('count', 'side', 'modules', 'effectors', 'drawn', 'splat', 'glows', 'sorts')
CAM_CHANS = ('tx', 'ty', 'tz', 'ry', 'rx', 'rz', 'fov')   # phase C: + fov (pcam follows an external camera's)


def rows_cook(scriptOp, key):
    """Script CHOP callback body: one sample per uniform row, channels x y z w (cam: tx ty tz ry). One numpy copy
    per channel (T-81: copyNumpyArray per appended channel keeps the names)."""
    import numpy as np
    c = scriptOp.parent()
    s = S(c)
    # Only the clock CHOP (eng_g) calls frame(): frame() reads absTime, and ANY absTime read inside a Script CHOP
    # cook makes that CHOP cook every frame from then on (T-125 (2); live T-143: eng_q kept cooking at 0.25 ms per
    # frame after it once carried frame()). The others copy the rows the engine already made this frame.
    rows = (frame(c) if (key == 'g' or s['rows'] is None) else s['rows'])[key]
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    nm = (CAM_CHANS[:len(rows[0])] if rows else CAM_CHANS) if key == 'cam' else (INFO_CHANS if key == 'info' else ('x', 'y', 'z', 'w'))
    a = np.asarray(rows if rows else [[0.0] * len(nm)], dtype=np.float32).reshape(-1, len(nm))
    scriptOp.numSamples = a.shape[0]
    for k, n in enumerate(nm):                   # a fresh copy per channel: stride 4 even for 1 sample (TD checks it;
        scriptOp.appendChan(n).copyNumpyArray(np.array(a[:, k], dtype=np.float32, copy=True))   # a column view: 16)


# ------------------------------------------------------------------------------------------------- rest upload

def _logic_dat(c, name):
    d = c.op(name)
    return d.module if d is not None else None


def _load_file(c, path, up, n, seed):
    """-> (P, C, S, Q) numpy arrays of length n (resampled), or raises."""
    Lg = L()
    import numpy as np
    low = path.lower()
    srl = _logic_dat(c, 'splat_logic')
    pcl = _logic_dat(c, 'pointcloud_logic')
    S_ = Q = None
    if srl is not None and (low.endswith('.splat') or low.endswith('.spz') or (low.endswith('.ply') and _ply_is_splat(path))):
        fmt, raw = srl.load_any(path)               # (format, raw dict); 'auto' coordfix already makes splats y-up
        prep = srl.prepare(raw, fmt, coordfix='auto', shdegree=0)
        P, Cc, S_, Q = prep['P'], prep['C'], prep['S'], prep['Q']
    else:
        cl = pcl.load_cloud(path)
        P, Cc = cl['P'], cl.get('C')
        if Cc is None:
            Cc = np.ones((len(P), 4), np.float32)
    P = Lg.up_fix(P, up)
    raw = raw_core(c)
    kp = Lg.load_keep(P, Cc, float(raw.get('Clip', 0.0)), float(raw.get('Opacitymin', 0.0)))
    if len(kp) < len(P):
        P, Cc = P[kp], np.asarray(Cc)[kp]
        if S_ is not None:
            S_, Q = S_[kp], Q[kp]
    idx = Lg.resample_to(P, n, seed)
    P, Cc = P[idx], np.asarray(Cc)[idx]
    if S_ is not None:
        S_, Q = S_[idx], Q[idx]
    return P, Cc, S_, Q


def _ply_is_splat(path):
    try:
        with open(path, 'rb') as fh:
            head = fh.read(4096)
        return b'scale_0' in head and b'f_dc_0' in head
    except Exception:
        return False


ACTOR_EXT = ('.ply', '.xyz', '.obj', '.csv', '.splat', '.spz', '.pts', '.txt')
ACTOR_MAX_FRAMES = 300


def _actor_files(raw):
    """Actor file list: the sequence folder's frames (sorted), else the single file."""
    import os
    d = str(raw.get('Actorseq', '') or '')
    if d and os.path.isdir(d):
        fs = sorted(f for f in os.listdir(d) if f.lower().endswith(ACTOR_EXT))
        return [os.path.join(d, f) for f in fs[:ACTOR_MAX_FRAMES]]
    f = str(raw.get('Actorfile', '') or '')
    return [f] if f else []


def load(c=None, recook=True):
    """Load file sources (A, B, actor file / sequence) -> rest images in STATE (numpy) + bounds; recook = force the
    rest Script TOPs. A and B go into ONE image (rest_files: A rows, then B rows); the actor into rest_actor."""
    c = c or C()
    Lg = L()
    s = S(c)
    raw = raw_core(c)
    n = Lg.quality_count(raw)
    side = Lg.side_for(n)
    ns, na, _np_ = Lg.layers(raw, n)
    s['rest'] = {}
    s['bounds'] = None
    s['load_sched'] = False
    s['splat'] = False
    s['actor_frames'] = []
    s['actor_idx'] = -1
    msg = []
    try:
        import numpy as np
        loaded = {}
        for k in ('A', 'B'):
            if raw.get(k + 'mode') == 'file' and raw.get(k + 'file'):
                loaded[k] = _load_file(c, raw[k + 'file'], raw.get(k + 'up', 'y'), ns, int(raw.get('Seed', 1)))
                msg.append('%s %d pts' % (k, len(loaded[k][0])))
                if k == 'A' and loaded[k][2] is not None:
                    s['splat'] = True
        if 'A' in loaded and 'B' in loaded and raw.get('Match', 'morton') != 'index':
            for k in ('A', 'B'):
                o = Lg.morton_order(loaded[k][0])
                loaded[k] = tuple(None if x is None else x[o] for x in loaded[k])
        imgs = {}
        for k, (P, Cc, S_, Q) in loaded.items():
            imgs[k] = Lg.pack_rest(P, Cc, S_, Q, side, ns)
            if k == 'A':
                s['bounds'] = Lg.bounds(P)
        if imgs:
            s['rest']['files'] = Lg.stack_files(imgs.get('A'), imgs.get('B'), side)
        if raw.get('Actormode') == 'file' and na > 0:
            sa = Lg.side_for(na)
            for fp in _actor_files(raw):
                P, Cc, S_, Q = _load_file(c, fp, raw.get('Actorup', 'y'), na, int(raw.get('Seed', 1)))
                s['actor_frames'].append(Lg.pack_rest(P, Cc, S_, Q, sa, na))
            msg.append('actor %d frame(s) x %d pts' % (len(s['actor_frames']), na))
        if mode_warn(raw, s['splat'], n):
            msg.append(mode_warn(raw, s['splat'], n))
        if hasattr(Lg, 'size_notes') and Lg.size_notes(raw):     # phase B: say the clamp here too (load wins Status)
            msg.append('size: ' + '; '.join(Lg.size_notes(raw)))
        status(c, 'loaded ' + (', '.join(msg) or 'generators only') + ' | %d points (scene %d), side %d' % (n, ns, side))
    except Exception as e:
        status(c, 'load failed: %s' % e)
    s['reset'] = 2
    s['sort_dirty'] = True
    s['dirty_all'] = True                          # splat flag / bounds / layers changed
    for nm in (('rest_files', 'rest_actor') if recook else ()):
        t = c.op(nm)
        if t is not None:
            t.cook(force=True)


def mode_warn(raw, is_splat, n):
    if L().render_mode(raw, is_splat) == 'splats' and n > 524288:
        return 'WARN splats at %d points: keep splat scenes <= 524288 (Quality high)' % n
    return ''


def rest_cook(scriptOp, key):
    """Script TOP callback: upload the rest image ('files' = A|B stacked, 'actor' = the actor's current frame) or a
    4x1 empty one. Self-heals after a reopen (T-89)."""
    c = scriptOp.parent()
    s = S(c)
    import numpy as np
    raw = raw_core(c)
    if key == 'files':
        want = any(raw.get(k + 'mode') == 'file' and raw.get(k + 'file') for k in ('A', 'B'))
    else:
        want = raw.get('Actormode') == 'file' and bool(_actor_files(raw))
    have = ('files' in s['rest']) if key == 'files' else bool(s['actor_frames'])
    if want and not have and not s.get('loading'):
        s['loading'] = True
        try:
            load(c, recook=False)
        finally:
            s['loading'] = False
    img = None
    if want and key == 'files':
        img = s['rest'].get('files')
    elif want and s['actor_frames']:
        img = s['actor_frames'][max(s['actor_idx'], 0) % len(s['actor_frames'])]
    if img is None:
        img = np.zeros((1, 4, 4), np.float32)
    scriptOp.copyNumpyArray(np.ascontiguousarray(img, dtype=np.float32))


# ------------------------------------------------------------------------------------------------- stack -> shaders

def _texts(c):
    rd = lambda n: c.op(n).text
    pal = c.op('px_palette')
    return rd('px_lib'), rd('px_tmpl_update'), rd('px_tmpl_colour'), rd('px_modules'), (pal.text if pal else '')


def stack_changed(c=None):
    """Called by the px_stack DAT Execute (and after any stack edit): codegen; a changed structure is compiled on the
    probe TOPs first, and goes live only when they compile clean (check_probe, 3 frames later)."""
    c = c or C()
    Lg = L()
    mark_all(c)
    st = stack(c)
    sync_pages(c, st)
    lib, tu, tc, mods, pal = _texts(c)
    echo = (int(getattr(c.par, 'Echoes', None) or 0) > 0 if getattr(c.par, 'Echoes', None) is not None else False) \
        and c.par.Actormode.eval() != 'off'
    gsec = c.op('px_gridsec')
    try:
        kw = {'cloud': bool(S(c).get('cloud'))} if hasattr(Lg, 'stack_cloud') else {}
        cg = Lg.codegen(st, lib, tu, tc, mods, pal, echo=echo,
                        grid_text=gsec.text if (gsec is not None and hasattr(Lg, 'stack_grid')) else '', **kw)
    except Exception as e:
        status(c, 'codegen error: %s' % e)
        return
    if cg['hash'] == c.fetch('px_hash', '', search=False):
        c.unstore('px_pending')
        _grid_wire(c, cg.get('grid', False), cg.get('hot', cg.get('grid', False)))   # hot row follows the stack
        status(c, 'live: %d modules, %d uniform rows%s' % (len(cg['layout']), cg['rows'], _solo_tail(c)))
        return
    pend = c.fetch('px_pending', None, search=False)
    if pend and pend.get('hash') == cg['hash'] and absTime.frame - pend.get('frame', -1e9) < 30:
        return                                        # this exact stack is already compiling on the probes
    c.op('update_next').text = cg['update']
    c.op('colour_next').text = cg['colour']
    _grid_wire(c, cg.get('grid', False), cg.get('hot', cg.get('grid', False)))   # input 2 = the grid field (SA5 / SA21 / K36)
    S(c)['grid_on'] = bool(cg.get('grid', False))
    c.store('px_pending', {'hash': cg['hash'], 'rows': cg['rows'], 'inplace': cg['update_inplace'], 'frame': absTime.frame,
                           'layout': [dict(il, slots=dict((k, list(v)) for k, v in il['slots'].items()))
                                      for il in cg['layout']]})
    for nm in ('update_probe', 'colour_probe'):
        p = c.op(nm)
        if p is not None:
            p.cook(force=True)
    status(c, 'compiling %d modules ...' % len(cg['layout']))
    run("op(%r).module.check_probe(op(%r))" % (me.path, c.path), delayFrames=3, delayRef=op.TDResources)


def _eff_use(c, s, lay, mrows):
    """Wave 4: eff_in follows /project1/effectors/eff_rows only while PX reads it (a module's shared selection is on:
    header row 1 w, or the stages compiled the shared grid); else eff_none (no per-frame buffer upload)."""
    hdr = getattr(L(), 'HEADER_ROWS', 0)
    if s.get('grid_on') is None:                      # a reloaded px_rt: read it once from the running shader
        uc = c.op('update_compute')
        s['grid_on'] = uc is not None and '#define PXE_GRID' in uc.text
    use = bool(s.get('grid_on')) or (hdr >= 2 and any(
        il.get('hdr', 0) >= 2 and len(mrows) > il['base'] + 1 and mrows[il['base'] + 1][3] > 0.5 for il in lay))
    e = c.op('eff_use')
    want = (2 if s.get('eff_pub') else 1) if use else 0      # 2 = read eff_rows_pub (a module names a #pub row)
    if e is not None and int(round(float(e.par.value0.eval()))) != want:
        e.par.value0 = want


def _wants_pub(ert, items, eff_names):
    """29 Oct: does an enabled module's shared selection name a published (#pub) row? Then eff_in reads the full
    buffer eff_rows_pub; else eff_rows, where #pub rows are inert (no reference to the publishing COMP)."""
    if ert is None or not hasattr(ert.L(), 'wants_pub'):
        return False
    Lg = L()
    rs = ert.rows()
    for i in items:
        if not i.get('enabled', True) or not Lg.MODULES.get(i['type'], {}).get('eff'):
            continue
        _own, rest = Lg.split_effectors((i.get('values') or {}).get('effectors', ''), eff_names,
                                        shared_only=i['type'] == 'light')
        if rest and ert.L().wants_pub(' '.join(rest), rs):
            return True
    return False


HOT_ROW = 'px_hot'                                   # legacy name (before phase B every PX used this one row)


def hot_name(c):
    """This PX's hot-points row in /project1/effectors (phase B: one per instance, px_logic.hot_key; kept in storage
    'px_inst' by instance_check)."""
    rec = c.fetch('px_inst', None, search=False)
    return rec.get('key', HOT_ROW) if isinstance(rec, dict) else HOT_ROW


def _grid_wire(c, on, hot=True):
    """SA5 / SA21: input 2 of update / look (+ probes) = the shared grid field (aux_src 1) while a module reads it,
    else the mask (aux_src 0, the v2 wiring). The hot row follows (_hot_sync); on: the shared grid is on (fitted
    around the scene when PX is the only cloud)."""
    a = c.op('aux_src')
    if a is not None and int(a.par.index.eval()) != (1 if on else 0):
        a.par.index = 1 if on else 0
    ert = _hot_sync(c, bool(on and hot))
    if not on:
        return
    if ert is None:
        status(c, 'grid modules need /project1/effectors (shared voxel grid): off here')
        return
    e = ert.C()
    if getattr(e.par, 'Gridon', None) is not None and not e.par.Gridon.eval():
        e.par.Gridon = True
        clouds = [r for r in ert.rows() if r.get('kind') == 'cloud']
        if len(clouds) <= 1 and getattr(c.par, 'Gridfit', None) is not None and c.par.Gridfit.eval():
            bb = S(c).get('bb') or ((0.0, 0.0, 0.0), 2.0)
            for k, v in zip('xyz', bb[0]):
                getattr(e.par, 'Gridcentre' + k).val = float(v)
            e.par.Gridsize = float(2.2 * bb[1])


HOT_TAGS = 'pxhot pub'                               # 29 Oct: published (#pub): never part of anyone's 'all'


def _hot_sync(c, want):
    """29 Oct (drop-in): this PX's hot-points row in the shared list is ON only while a compiled module reads the grid
    (heat_spread, light bounce: px_logic.stack_grid with PXE_GRID compiled), OFF otherwise; tagged #pub, so no consumer
    reads it unless it names it. Called on stack events and once on the first cook, never per frame. No shared list
    (another project, a fresh scene): nothing happens, no error. -> the shared eff_rt module or None."""
    ert = _eff_rt()
    if ert is None:
        return None
    try:
        hn = hot_name(c)
        row = next((r for r in ert.rows() if r['name'] == hn), None)
        if want:
            ref = c.path + '/hot_pts'
            if row is None:
                ert.add('cloud', hn, tags=HOT_TAGS, ref=ref)
                return ert
            tg = str(row.get('tags', '')).replace(',', ' ').split()
            miss = [t for t in HOT_TAGS.split() if t not in tg]
            if miss:
                ert.set_value(hn, 'tags', ' '.join(tg + miss))
            if row.get('ref') != ref:
                ert.set_value(hn, 'ref', ref)
            if str(row.get('enabled', '1')).strip() in ('0', 'False', 'false', ''):
                ert.enable(hn, True)
        elif row is not None and str(row.get('enabled', '1')).strip() not in ('0', 'False', 'false', ''):
            ert.enable(hn, False)
    except Exception as e:
        status(c, 'hot row: %s' % e)
    return ert


def hot_want(c):
    """The compiled stack reads the grid through the hot row (heat_spread / light bounce, PXE_GRID compiled)."""
    uc = c.op('update_compute')
    if uc is None or '#define PXE_GRID' not in uc.text:
        return False
    Lg = L()
    return bool(hasattr(Lg, 'stack_grid') and Lg.stack_grid(stack(c)))


def check_probe(c):
    pend = c.fetch('px_pending', None, search=False)
    if not pend:
        return
    errs = []
    for nm in ('update_probe', 'colour_probe'):
        p = c.op(nm)
        if p is not None:
            e = (p.errors() or '') + (p.warnings() or '')
            if 'rror' in e:
                errs.append('%s: %s' % (nm, e[:300]))
    if errs:
        status(c, 'compile FAILED, old shader kept: ' + ' | '.join(errs))
        c.unstore('px_pending')
        return
    # rows first (engine packs to the new layout) then texts: both land before the next frame's cook
    c.store('px_layout', pend['layout'])
    c.store('px_rows', pend['rows'])
    c.op('update_compute').text = c.op('update_next').text
    c.op('update_inplace').text = pend['inplace']
    c.op('colour_compute').text = c.op('colour_next').text
    c.store('px_hash', pend['hash'])
    c.unstore('px_pending')
    S(c)['frame'] = None
    S(c)['dirty_all'] = True                       # new layout: re-read (T-143 engine caches)
    status(c, 'live: %d modules, %d uniform rows%s' % (len(pend['layout']), pend['rows'], _solo_tail(c)))


# ------------------------------------------------------------------------------------------------- module pages

def _add_par(page, name, style, default, o):
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
        p.default = bool(default)
        p.val = bool(default)
    elif style in ('XYZ', 'RGB'):
        ps = page.appendXYZ(name, label=label) if style == 'XYZ' else page.appendRGB(name, label=label)
        for p, v in zip(ps, default):
            if style == 'XYZ':
                p.normMin, p.normMax = o['min'], o['max']
            p.default = v
            p.val = v
    elif style == 'Str' and o.get('menu'):          # live dropdown, free text kept (T-233)
        p = page.appendStrMenu(name, label=label)[0]
        p.menuSource = L().menu_source(name)
        p.default = default
        p.val = default
    elif style == 'Str':
        p = page.appendStr(name, label=label)[0]
        p.default = default
        p.val = default


def _watchers(c, on, names=('px_dirty', 'eff_watch')):
    """Pause / resume the par watchers around custom-par creation (T-143: with px_dirty watching '*', adding a
    module page took 4.6 s instead of 0.4 s; the engine re-reads everything afterwards, mark_all)."""
    was = {}
    for nm in names:
        d = c.op(nm)
        if d is not None:
            was[nm] = bool(d.par.active.eval())
            if on is not None:
                d.par.active = on if not isinstance(on, dict) else on.get(nm, True)
    if on is not False:
        mark_all(c)
    return was


def sync_pages(c, st, values=None):
    """(watchers paused while pages / pars are made, T-143)"""
    was = _watchers(c, False)
    try:
        return _sync_pages(c, st, values)
    finally:
        _watchers(c, was)


def _sync_pages(c, st, values=None):
    """One custom page per instance in the stack (enabled or not, so a disabled module keeps its values); pages of
    removed instances are destroyed (custom pars only, never ops: T-70 safe). values = {TD name: value} to set
    (duplicate / preset recall)."""
    Lg = L()
    want = dict((Lg.page_name(i), i) for i in st)
    changed = False
    for pg in list(c.customPages):
        if pg.name.startswith('M') and '_' in pg.name and pg.name[1:pg.name.index('_')].isdigit() and pg.name not in want:
            pg.destroy()
            changed = True
    for pname, inst in want.items():
        page = next((pg for pg in c.customPages if pg.name == pname), None)
        if page is None:
            page = c.appendCustomPage(pname)
            changed = True
        for name, style, default, o in Lg.instance_par_specs(inst):
            probe = name + ('x' if style == 'XYZ' else ('r' if style == 'RGB' else ''))
            if getattr(c.par, probe, None) is None:
                _add_par(page, name, style, default, o)
                if name.endswith('progress'):
                    _own(c, {name: default})     # its creation event is PX's own write too (auto_guard)
    _own(c, values or {})
    for k, v in (values or {}).items():
        p = getattr(c.par, k, None)
        if p is not None:
            try:
                p.val = v
            except Exception:
                pass
    if changed:
        # zkit panel rebuild costs ~0.5-0.7 s with ~200 knobs (live, 31550): only while the controls window is open;
        # otherwise it is marked dirty and rebuilt when Opencontrols opens the window.
        w = c.op('controls_window')
        if w is not None and w.isOpen:
            run("op(%r).module.rebuild_ui(op(%r))" % (me.path, c.path), delayFrames=2, delayRef=op.TDResources)
        else:
            c.store('px_ui_dirty', True)
    return changed


def rebuild_ui(c):
    """zkit panel: core pages + one page per instance (stack order)."""
    zk = c.fetch('px_zkit_file', '', search=False)
    if not zk or c.op('controls') is None:
        return
    Lg = L()
    pages = list(Lg.PANEL_CORE_PAGES) + [Lg.page_name(i) for i in stack(c)]
    try:
        g = dict(globals())
        exec(open(zk).read(), g)
        g['build_controls'](c.path, pages=pages, d=56, cols=8)
        c.unstore('px_ui_dirty')
    except Exception as e:
        status(c, 'panel rebuild failed: %s' % e)


# ------------------------------------------------------------------------------------------------- stack edits

def add(c, mtype, values=None, at=None):
    """Stack page Add: a new module; explode / dissolves start with auto progress on (ping-pong, 28 Oct). mtype = a
    type name or a browser label (phase B); an unknown type goes to Status, nothing is added (-> None)."""
    Lg = L()
    t = Lg.addtype_of(mtype) if hasattr(Lg, 'addtype_of') else mtype
    if t is None:
        status(c, 'add: unknown module type %r (pick one in Addtype)' % (mtype,))
        return None
    mtype = t
    st, uid = Lg.add_module(stack(c), mtype, at)
    vals = Lg.new_module_values(mtype, uid) if hasattr(Lg, 'new_module_values') else {}
    vals.update(values or {})
    write_stack(c, st)
    sync_pages(c, st, vals)
    c.par.Sel = uid
    return uid


def remove(c, uid):
    write_stack(c, L().remove_module(stack(c), uid))


def duplicate(c, uid):
    Lg = L()
    st0 = stack(c)
    st, new = Lg.duplicate_module(st0, uid)
    if new is None:
        return None
    flat = flat_module_values(c, [i for i in st0 if i['uid'] == int(uid)])
    sync_pages(c, st, Lg.copy_values(flat, uid, new))
    write_stack(c, st)
    c.par.Sel = new
    return new


def move(c, uid, delta):
    write_stack(c, L().move_module(stack(c), uid, delta))


def toggle(c, uid):
    """Enable / disable = bypass. While soloed, the module's flag in the saved set follows the click too (your hand
    wins: Unsolo keeps what you set)."""
    st = stack(c)
    k = L().find(st, uid)
    if k >= 0:
        on = not st[k]['enabled']
        so = c.fetch('px_solo', None, search=False)
        if so and str(int(uid)) in so.get('saved', {}):
            so = dict(so, saved=dict(so['saved']))
            so['saved'][str(int(uid))] = on
            c.store('px_solo', so)
        write_stack(c, L().set_enabled(st, uid, on))


# ------------------------------------------------------------------------------------------------- solo (phase B)
# Solo (Stack page, on Sel): only that module runs (one recompile); Unsolo puts back the enabled set saved at the
# first Solo, exactly (one recompile). The saved set is in storage 'px_solo' (plain dict); presets never see it: Store
# writes the saved set, recall / morph / a setlist scene end solo.

def _solo_tail(c):
    so = c.fetch('px_solo', None, search=False)
    tail = (' | solo M%d (Unsolo restores the set)' % int(so['uid'])) if so else ''
    k = S(c).get('src_kept_frame')                 # a look applied in the last 2 s kept the source (Presetsource)
    if k is not None and absTime.frame - int(k) <= 120 and hasattr(L(), 'SOURCE_KEPT_NOTE'):
        tail += ' | ' + L().SOURCE_KEPT_NOTE
    return tail


def solo_uid(c):
    so = c.fetch('px_solo', None, search=False)
    return int(so['uid']) if so else None


def solo(c, uid):
    Lg = L()
    st = stack(c)
    if Lg.find(st, uid) < 0:
        status(c, 'solo: no module %s in the stack (pick Sel)' % uid)
        return False
    so = c.fetch('px_solo', None, search=False)
    st2, saved = Lg.solo_stack(st, uid, so['saved'] if so else None)
    c.store('px_solo', {'uid': int(uid), 'saved': saved})
    if [i['enabled'] for i in st2] != [i['enabled'] for i in st]:
        write_stack(c, st2)
    i = st[Lg.find(st, uid)]
    status(c, 'solo: %s (Unsolo restores %d module%s)' % (Lg.sel_label(i, uid), sum(1 for v in saved.values() if v),
                                                           '' if sum(1 for v in saved.values() if v) == 1 else 's'))
    return True


def unsolo(c, quiet=False):
    so = c.fetch('px_solo', None, search=False)
    if not so:
        if not quiet:
            status(c, 'unsolo: nothing is soloed')
        return False
    c.unstore('px_solo')
    st = stack(c)
    st2 = L().unsolo_stack(st, so.get('saved'))
    if [i['enabled'] for i in st2] != [i['enabled'] for i in st]:
        write_stack(c, st2)
    if not quiet:
        status(c, 'unsolo: %d of %d modules on again' % (sum(1 for i in st2 if i['enabled']), len(st2)))
    return True


def _end_solo(c):
    """A new look (recall / morph / scene) brings its own enabled set: solo ends without writing the old set back."""
    if c.fetch('px_solo', None, search=False) is not None:
        c.unstore('px_solo')


# ------------------------------------------------------------------------------------------------- effectors

_SOPS = {'box': boxSOP, 'sphere': sphereSOP, 'plane': gridSOP, 'capsule': tubeSOP, 'torus': torusSOP}


def add_effector(c, kind, name=None, xform=None):
    """Create a visible effector object in `effectors` (Geometry COMP + wire shape, or a Null COMP) and a px_eff row.
    Returns the name. 8 max (the shader's bound)."""
    Lg = L()
    t = c.op('px_eff')
    have = [r['name'] for r in eff_table(c)]
    if len(have) >= Lg.MAX_EFF:
        status(c, 'effector limit 8 reached (shader bound)')
        return None
    k = 1
    while name is None or name in have:
        name = 'E%d' % k
        k += 1
    holder = c.op('effectors')
    if kind == 'chop':
        t.appendRow([name, 'chop', 'in_eff', name.lower()])
        mark_all(c)
        return name
    if kind == 'actor':                            # the actor layer's points (Source page Actor*): no object
        t.appendRow([name, 'actor', '', ''])
        mark_all(c)
        return name
    if kind == 'camera':                           # the output camera itself (position + forward)
        t.appendRow([name, 'camera', 'pcam', ''])
        mark_all(c)
        return name
    if kind in ('null', 'pts'):                    # pts: the Null places / scales the point set (Ptssource)
        o = holder.op(name) or holder.create(nullCOMP, name)
    else:
        o = holder.op(name) or holder.create(geometryCOMP, name)
        for ch in list(o.children):
            if ch.name != 'shape':
                _sd(ch)
        s_ = o.op('shape') or o.create(_SOPS.get(kind, boxSOP), 'shape')
        if kind == 'plane':
            s_.par.orient = 'zx'
            s_.par.sizex, s_.par.sizey = 1, 1
        if kind == 'capsule':
            s_.par.rad1, s_.par.rad2 = 0.25, 0.25
            s_.par.height = 1.0
        if kind == 'torus':
            s_.par.radx, s_.par.rady = 0.5, 0.15
        if kind == 'sphere':
            s_.par.radx, s_.par.rady, s_.par.radz = 0.5, 0.5, 0.5
        s_.render = True
        s_.display = True
        o.par.material = 'giz_mat'                 # sibling in `effectors` (COMP OP pars resolve beside it, T-81)
    o.viewer = True
    eff_page(o)
    for k_, v in (xform or {}).items():
        getattr(o.par, k_).val = v
    t.appendRow([name, kind, 'effectors/' + name, ''])
    _preview_geometry(c)
    mark_all(c)
    return name


def eff_page(o, values=None):
    """The 'Effector' custom page on an effector object (motion path, trail, glow, point set): added once, values
    kept; values = {par name or component name: value} to set (presets)."""
    comp = o.parent(2) if o.parent() is not None and o.parent().name == 'effectors' else None
    was = _watchers(comp, False, ('eff_watch',)) if comp is not None else None
    try:
        _eff_page(o, values)
    finally:
        if comp is not None:
            _watchers(comp, was, ('eff_watch',))


def _eff_page(o, values=None):
    page = next((pg for pg in o.customPages if pg.name == 'Effector'), None) or o.appendCustomPage('Effector')
    for name, style, default, opt in L().EFF_PARS:
        probe = name + ('x' if style == 'XYZ' else ('r' if style == 'RGB' else ''))
        if getattr(o.par, probe, None) is None:
            _add_par(page, name, style, default, opt)
    for k, v in (values or {}).items():
        if isinstance(v, (tuple, list)):
            st = next((s_ for n_, s_, _d, _o in L().EFF_PARS if n_ == k), 'XYZ')
            for suf, x in zip('xyz' if st == 'XYZ' else 'rgb', v):
                p = getattr(o.par, k + suf, None)
                if p is not None:
                    p.val = x
        else:
            p = getattr(o.par, k, None)
            if p is not None:
                try:
                    p.val = v
                except Exception:
                    pass


def remove_effector(c, name):
    t = c.op('px_eff')
    for r in range(t.numRows - 1, 0, -1):
        if t[r, 'name'].val == name:
            t.deleteRow(r)
    o = c.op('effectors/' + name)
    if o is not None:
        _sd(o)
    S(c)['trail'].pop(name, None)
    g = c.op('gizmos/g_' + name)
    if g is not None:
        _sd(g)
    _preview_geometry(c)
    mark_all(c)


def _preview_geometry(c):
    r = c.op('render_preview')
    if r is None:
        return
    geo = ['pgeo_prev']
    for row in eff_table(c):
        if row.get('kind') in GIZMO_KINDS:
            geo.append('gizmos/g_' + row['name'])
        elif row.get('path') and c.op(row['path']) is not None and c.op(row['path']).OPType == 'geometryCOMP':
            geo.append(row['path'])
    r.par.geometry = ' '.join(geo)


GIZMO_KINDS = ('null', 'chop', 'pts', 'actor')


def _gizmos(c, effs):
    """Axes gizmos for Null / CHOP / point-set / actor effectors (they render nothing themselves): set only when a
    value changed."""
    s = S(c)
    holder = c.op('gizmos')
    if holder is None:
        return
    for e in effs:
        if e['kind'] not in GIZMO_KINDS:
            continue
        g = holder.op('g_' + e['name'])
        if g is None:
            g = holder.create(geometryCOMP, 'g_' + e['name'])
            for ch in list(g.children):
                _sd(ch)
            ax = g.create(boxSOP, 'axes')
            ax.par.sizex, ax.par.sizey, ax.par.sizez = 0.2, 0.2, 0.2
            ax.render = True
            ax.display = True
            g.par.material = 'giz_mat'
            _preview_geometry(c)
        w = e['world']
        key = (round(w[0][3], 5), round(w[1][3], 5), round(w[2][3], 5))
        if s['gizmo'].get(e['name']) != key:
            g.par.tx, g.par.ty, g.par.tz = key
            s['gizmo'][e['name']] = key


# ------------------------------------------------------------------------------------------------- presets

def _eff_xforms(c):
    out = {}
    for row in eff_table(c):
        o = c.op(row['path']) if row.get('path') else None
        if o is not None and row.get('kind') not in ('chop', 'actor', 'camera'):
            out[row['name']] = [float(getattr(o.par, k).eval()) for k in XF]
    return out


def _nosnap():
    '''Core pars a preset never stores: Status, the preset fields, the rig-level Audiosrc / Beatsync, the setlist.'''
    return getattr(L(), 'NOSNAP', ('Status', 'Presetname', 'Newname'))


def _flat_all(c, st):
    flat = flat_module_values(c, st)
    for p in c.customPars:
        if p.page.name in L().CORE_PAGE_NAMES and p.style not in ('Pulse',) and p.name not in _nosnap():
            v = p.eval()
            flat[p.name] = v.path if hasattr(v, 'path') else v
    return flat


def _eff_pars_all(c):
    """{effector name: its Effector page values} (objects only)."""
    out = {}
    for row in eff_table(c):
        o = c.op(row.get('path', '')) if row.get('path') else None
        if o is not None and row.get('kind') not in ('chop', 'camera'):
            out[row['name']] = eff_raw(o)
    return out


def _make_effectors(c, snap, drop_prev=False):
    """Create the effectors a preset needs (snap['make'] = [name, kind]) when missing, then set their settings.
    drop_prev (recall): effectors an earlier recall CREATED and this preset does not need are removed first (only 8
    slots; they piled up across looks, b4 lane 27 Oct). Effectors the user made are never removed. 'px_made' = plain
    list of names (T-67)."""
    want = [m[0] for m in snap.get('make', [])]
    prev = list(c.fetch('px_made', [], search=False) or [])
    if drop_prev:
        for name in prev:
            if name not in want and any(r['name'] == name for r in eff_table(c)):
                remove_effector(c, name)
    have = [r['name'] for r in eff_table(c)]
    made = [n for n in prev if n in want] if drop_prev else [n for n in prev if n in have]
    for name, kind in snap.get('make', []):
        if name not in have:
            add_effector(c, kind, name)
            made.append(name)
    c.store('px_made', made)
    for name, vals in snap.get('effpars', {}).items():
        o = c.op('effectors/' + name)
        if o is not None and vals:
            eff_page(o, vals)


def install_builtins(c):
    """D: the built-in looks (px_logic.BUILTIN) in px_presets: added when missing, refreshed when a build brings a newer
    version (built-in names are reserved; store an edited look under its own name). Other presets are never touched."""
    Lg = L()
    t = c.op('px_presets')
    rows = dict((t[r, 'name'].val, r) for r in range(1, t.numRows))
    items = [(name, Lg.builtin_preset(name)) for name in Lg.BUILTIN]
    if hasattr(Lg, 'splat_presets'):              # splat versions + splat_showcase (27 Oct)
        items += Lg.splat_presets(lambda nm: _get_preset(c, nm))
    for name, snap in items:
        txt = Lg.preset_dumps(snap)
        if name not in rows:
            t.appendRow([name, txt])
            rows[name] = t.numRows - 1
        elif t[rows[name], 1].val != txt:
            t[rows[name], 1] = txt


def store(c, name):
    Lg = L()
    st = stack(c)
    so = c.fetch('px_solo', None, search=False)
    if so and hasattr(Lg, 'real_stack'):
        st = Lg.real_stack(st, so.get('saved'))        # solo is never stored (phase B)
    make = [[r['name'], r.get('kind', 'null')] for r in eff_table(c)]
    snap = Lg.snapshot(st, _flat_all(c, st), _eff_xforms(c), name, _eff_pars_all(c), make,
                       lines=_lines_values(c) if c.op('PX_lines') is not None else None)
    t = c.op('px_presets')
    for r in range(1, t.numRows):
        if t[r, 'name'].val == name:
            t[r, 'json'] = Lg.preset_dumps(snap)
            return
    t.appendRow([name, Lg.preset_dumps(snap)])


def _get_preset(c, name):
    t = c.op('px_presets')
    for r in range(1, t.numRows):
        if t[r, 'name'].val == name:
            return L().preset_loads(t[r, 'json'].val)
    return None


def _own(c, flat):
    """Remember the progress values PX itself writes (recall / morph / page sync): their late par events are echoes
    for auto_guard, not the user's hand (T-236)."""
    own = S(c).setdefault('own_prog', {})
    for k, v in flat.items():
        if k.endswith('progress') and k[:1] == 'M':
            own[k] = v


def auto_guard(par):
    """px_autoguard (Parameter Execute on M*progress / M*drive: value, expression, export, mode): the user took
    progress (by hand, expression, export, CHOP, or a progress drive) -> that module's auto progress goes Off. Echoes
    of PX's own writes are ignored. Events only, never per frame."""
    try:
        c = par.owner
        Lg = L()
        m = Lg.AUTO_GUARD_RE.match(par.name)
        if not m:
            return
        ap = getattr(c.par, 'M%sauto' % m.group(1), None)
        if ap is None or ap.mode != ParMode.CONSTANT:
            return
        const = par.mode == ParMode.CONSTANT
        uid = Lg.auto_guard_off(par.name, par.eval(), ap.eval(), const,
                                S(c).get('own_prog', {}).get(par.name) if const else None)
        if uid is not None:
            ap.val = 'off'
            status(c, 'M%d progress is yours: auto progress off' % uid)
    except Exception:
        pass


def _apply_values(c, flat):
    """Set the constant pars of flat (a par driven by an expression / export stays the user's). -> names that exist
    but could not be set (bad menu item, read only ...)."""
    _own(c, flat)
    failed = []
    for k, v in flat.items():
        p = getattr(c.par, k, None)
        if p is not None and p.mode == ParMode.CONSTANT:
            try:
                if p.eval() != v:
                    p.val = v
            except Exception:
                failed.append(k)
    return failed


# ------------------------------------------------------------------------------------------------- preset checks
# Phase B: a recall / morph never fails silently and never raises. What could not be applied (pars this PX does not
# have, module types it does not know, effectors / files that are missing) goes to Status ("recalled X: 2 pars skipped
# (Foo, Bar)") and to the px_notes table (frame, kind, text; newest last, NOTES_MAX rows).
NOTES_MAX = 200


def note(c, kind, text):
    t = c.op('px_notes')
    if t is None:
        return
    try:
        if t.numRows == 0:
            t.appendRow(['frame', 'kind', 'text'])
        t.appendRow([str(absTime.frame), str(kind), str(text)[:4000]])
        while t.numRows > NOTES_MAX + 1:
            t.deleteRow(1)
    except Exception:
        pass


def _keeps_source(c):
    """Presetsource off (or absent): looks keep the user's source (28 Oct)."""
    Lg = L()
    if not hasattr(Lg, 'keep_source'):
        return False
    p = getattr(c.par, 'Presetsource', None)
    return Lg.keep_source(None if p is None else p.eval())


def _source_names(c):
    """Source-page pars of this PX (live page + px_logic's list + LOAD_PARS)."""
    page = [p.name for p in c.customPars if p.page is not None and p.page.name == 'Source']
    return L().source_par_names(page) | set(LOAD_PARS)


def _load_checked(c, name):
    """-> (snapshot or None, notes): a missing row, bad JSON or a row that is not a preset is notes['error']; module
    types this PX does not have are notes['types'] (preset_loads drops them)."""
    Lg = L()
    t = c.op('px_presets')
    txt = None
    for r in range(1, t.numRows if t is not None else 0):
        if t[r, 0].val == name:
            txt = t[r, 1].val
            break
    if txt is None:
        return None, {'error': 'no preset %r' % (name,)}
    notes = {}
    try:
        d = json.loads(txt)
        if isinstance(d, dict) and hasattr(Lg, 'preset_unknown_types'):
            notes['types'] = Lg.preset_unknown_types(d)
        snap = Lg.preset_loads(txt)
        if _keeps_source(c) and isinstance(snap, dict) and isinstance(snap.get('values'), dict):
            snap['values'], gone = Lg.strip_source(snap['values'], _source_names(c))
            if gone:
                notes['source_kept'] = gone
                S(c)['src_kept_frame'] = absTime.frame
        return snap, notes
    except Exception as e:
        notes['error'] = 'not a PX preset (%s: %s)' % (type(e).__name__, e)
        return None, notes


def _check_applied(c, snap, notes):
    """After a look was applied: its pars this PX does not have, effectors and files that are missing."""
    import os
    Lg = L()
    vals = snap.get('values', {})
    notes['pars'] = sorted(k for k in vals if getattr(c.par, k, None) is None)
    own = [r['name'] for r in eff_table(c)]
    miss = [n for n in snap.get('effectors', {}) if n not in own]
    ert = _eff_rt()
    shared = [r['name'] for r in ert.rows()] if ert is not None else []
    if hasattr(Lg, 'preset_eff_missing'):
        miss += [n for n in Lg.preset_eff_missing(snap.get('stack', []), vals, own, shared) if n not in miss]
        notes['files'] = Lg.preset_files(vals, os.path.exists)
    notes['effectors'] = miss
    return notes


def _report(c, name, notes, verb='recalled'):
    """Status line + a px_notes row when something was skipped; -> the issues text ('' when clean)."""
    Lg = L()
    if hasattr(Lg, 'preset_summary'):
        txt = Lg.preset_summary(name, notes, verb)
    else:
        txt = '%s %s' % (verb, name)
    status(c, txt)
    issues = dict((k, v) for k, v in (notes or {}).items() if v and k != 'source_kept')   # a kept source is no issue
    if issues:
        note(c, verb.split()[0], '%s: %s' % (name, json.dumps(issues, sort_keys=True, default=str)))
        return txt
    return ''


XF = ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz')


def _apply_effectors(c, xf, frac=1.0, start=None):
    """Effector object transforms; with start, lerp start -> xf by frac (preset morph)."""
    for name, vals in xf.items():
        o = c.op('effectors/' + name)
        if o is None:
            continue
        a = (start or {}).get(name)
        for k, v in enumerate(vals):
            getattr(o.par, XF[k]).val = v if a is None else a[k] + (v - a[k]) * frac


def _lines_values(c):
    """PX_lines' own values that differ from their defaults (constant pars only; linked pars are expressions)."""
    pl = c.op('PX_lines')
    out = {}
    if pl is None:
        return out
    for p in pl.customPars:
        if p.style == 'Pulse' or p.mode != ParMode.CONSTANT or p.readOnly:
            continue
        try:
            v = p.eval()
            v = v.path if hasattr(v, 'path') else v
            if v != p.default:
                out[p.name] = v
        except Exception:
            pass
    return out


LINES_BOX = ('Cngridcentrex', 'Cngridcentrey', 'Cngridcentrez', 'Cngridsize')


def _lines_box(c, bb):
    """Wave 4: PX_lines' connect grid index box = the scene bounds (centre, 2.2 x radius); constants, set only when the
    bounds change (an expression here would re-evaluate per frame and re-index)."""
    pl = c.op('PX_lines')
    if pl is None or getattr(pl.par, 'Cngridsize', None) is None:
        return
    for nm, v in zip(LINES_BOX, list(bb[0]) + [2.2 * float(bb[1])]):
        p = getattr(pl.par, nm)
        if p.mode == ParMode.CONSTANT and abs(float(p.eval()) - float(v)) > 1e-6:
            p.val = float(v)


def _apply_lines(c, vals):
    """Whole PX_lines look: constant pars back to their defaults, then vals (xyz / rgb tuples to components)."""
    pl = c.op('PX_lines')
    if pl is None or vals is None:
        return
    flat = {}
    for k, v in vals.items():
        if isinstance(v, (list, tuple)):
            sfx = 'rgb' if getattr(pl.par, k + 'r', None) is not None else 'xyz'
            for a, x in zip(sfx, v):
                flat[k + a] = x
        else:
            flat[k] = v
    for p in pl.customPars:
        if p.style == 'Pulse' or p.mode != ParMode.CONSTANT or p.readOnly or p.name in ('Resetn', 'Status'):
            continue
        if p.name in LINES_BOX and p.name not in flat:
            continue                                  # the index box follows the scene bounds (_lines_box)
        want = flat.get(p.name, p.default)
        if p.style == 'COMP' and isinstance(want, str) and want and c.op(want) is not None:
            want = c.op(want).path                    # a look names PX's own objects relative to PX
        try:
            cur = p.eval()
            cur = cur.path if hasattr(cur, 'path') else cur
            if cur != want:
                p.val = want
        except Exception:
            pass


def _apply_w2(c, snap):
    """Wave 2 parts of a look: light effectors (in /project1/effectors, tag pxpreset; the previous look's removed),
    geometry objects (PX geo/, Geocomps), PX_lines values. Runs after the core values (Geocomps / Geoon set)."""
    ert = _eff_rt()
    lights = snap.get('lights') or []
    if ert is not None:
        want = [l[0] for l in lights]
        have = [r['name'] for r in ert.rows()]
        others = None
        for nm in c.fetch('px_made_lights', []) or []:
            if nm not in want and nm in have:
                if others is None:                     # phase B: a light another PX's look also made stays
                    others = [o for o in px_instances() if o.path != c.path]
                if any(nm in (o.fetch('px_made_lights', []) or []) for o in others):
                    continue
                ert.remove(nm)
        made = []
        for nm, ty, pos, rot, col, it, extra in lights:
            lv = dict((k, v) for k, v in extra.items() if k != 'expr')
            o = op('/project1/effectors/' + nm)
            if o is None:
                nm = ert.add('light', nm, tags='pxpreset', type=ty, colour=tuple(col), intensity=float(it), **lv)
                o = op('/project1/effectors/' + nm)
            else:
                ert.set_light(o, type=ty, colour=tuple(col), intensity=float(it), **lv)
            if o is not None:
                for k, v in zip(('tx', 'ty', 'tz', 'rx', 'ry', 'rz'), tuple(pos) + tuple(rot)):
                    p = getattr(o.par, k)
                    p.mode = ParMode.CONSTANT
                    p.val = float(v)
                for k, e in extra.get('expr', {}).items():
                    p = getattr(o.par, k)
                    p.expr = e
                    p.mode = ParMode.EXPRESSION
            made.append(nm)
        c.store('px_made_lights', made)
        _light_info(c)
    geo = snap.get('geo') or []
    holder = c.op('geo')
    want = [g[0] for g in geo]
    toks = str(c.par.Geocomps.eval() or '').split() if getattr(c.par, 'Geocomps', None) is not None else []
    for nm in c.fetch('px_made_geo', []) or []:
        if nm not in want and holder is not None:
            for o in (holder.op(nm), holder.op(nm + '_mat')):
                _sd(o)
            toks = [t for t in toks if not t.endswith('/geo/' + nm)]
    if getattr(c.par, 'Geocomps', None) is not None:
        c.par.Geocomps = ' '.join(toks)
    for nm, kind, xf, col, metal, rough, emit in geo:
        g = holder.op(nm) if holder is not None else None
        if g is None:
            add_geo(c, nm, kind, tuple(col), metal, rough, emit, xf)
        else:
            for k, v in xf.items():
                getattr(g.par, k).val = v
            if g.path not in toks:
                c.par.Geocomps = ' '.join(toks + [g.path])
    c.store('px_made_geo', want)
    if snap.get('lines') is not None:
        _apply_lines(c, snap['lines'])


def recall(c, name):
    """Recall a look. Never raises: whatever could not be applied is reported (_report), the rest is applied.
    -> the issues text ('' when the look applied clean)."""
    snap, notes = _load_checked(c, name)
    if snap is None:
        return _report(c, name, notes, 'recall failed:')
    failed = []
    try:
        _end_solo(c)
        _make_effectors(c, snap, drop_prev=True)
        sync_pages(c, snap['stack'], snap['values'])
        write_stack(c, snap['stack'])
        failed = _apply_values(c, snap['values'])
        _apply_effectors(c, snap['effectors'])
        _apply_w2(c, snap)
        if getattr(c.par, 'Geoon', None) is not None:
            geo_sync(c)
        S(c)['mt0'] = S(c)['simt']                 # motion paths start from their beginning
    except Exception as e:
        notes['error'] = '%s: %s' % (type(e).__name__, e)
    try:
        _check_applied(c, snap, notes)
    except Exception as e:
        notes['error'] = (notes.get('error', '') + ' check: %s' % e).strip()
    notes['failed'] = failed
    return _report(c, name, notes)


def morph_to(c, name, dur=None, curve=None):
    """Morph to a look over dur s. Never raises; what could not be applied is reported like a recall. -> issues text."""
    Lg = L()
    b, notes = _load_checked(c, name)
    if b is None:
        return _report(c, name, notes, 'morph failed:')
    try:
        return _morph_start(c, Lg, b, name, notes, dur, curve)
    except Exception as e:
        notes['error'] = '%s: %s' % (type(e).__name__, e)
        S(c)['morph'] = None
        return _report(c, name, notes, 'morph failed:')


def _morph_start(c, Lg, b, name, notes, dur, curve):
    _end_solo(c)
    st = stack(c)
    a = Lg.snapshot(st, _flat_all(c, st), _eff_xforms(c), 'now')
    if 'source_kept' in notes or _keeps_source(c):  # the morph never writes the source (not even its own start)
        a['values'] = Lg.strip_source(a['values'], _source_names(c))[0]
    _make_effectors(c, b)                          # settings (motion, glow...) switch at the start
    _apply_w2(c, b)                                # lights / geometry / lines switch at the start too
    if Lg.morph_plan(a, b) == 'switch':
        sync_pages(c, b['stack'], dict((k, v) for k, v in b['values'].items() if k not in a['values']))
        write_stack(c, b['stack'])
    # source pars (file, count, Clip, Opacitymin...) switch at the START, once: lerping Clip / Opacitymin re-loaded the
    # scene on every morph frame (28 Oct sweep, b3: KANDA swipe -> Green line sweep froze ~50 s, T-237)
    ld = dict((k, v) for k, v in b['values'].items() if k in LOAD_PARS)
    _apply_values(c, ld)
    av = dict(a['values'])
    av.update(ld)
    S(c)['morph'] = {'a': av, 'b': b['values'], 'ea': a['effectors'], 'eb': b['effectors'],
                     't0': absTime.seconds,
                     'dur': max(float(c.par.Morphtime.eval() if dur is None else dur), 1e-3),
                     'curve': c.par.Morphcurve.eval() if curve is None else curve,
                     'disc': sorted(Lg.discrete_keys(b['stack'])), 'name': name, 'own': {}, 'hold': []}
    _check_applied(c, b, notes)
    # pars this PX does not have are never written by the morph (they would only fail each frame)
    S(c)['morph']['b'] = dict((k, v) for k, v in b['values'].items() if k not in set(notes.get('pars') or []))
    return _report(c, name, notes, 'morphing to')


def _morph_tick(c):
    Lg = L()
    m = S(c)['morph']
    t = (absTime.seconds - m['t0']) / m['dur']
    vals = Lg.morph_flat(m['a'], m['b'], t, m['curve'], set(m['disc']))
    # the user's hand wins (28 Oct): a par whose value is no longer what the morph wrote last frame was moved by
    # someone else (knob, typing, a script) and stays theirs for the rest of the morph. Checked here, not in a par
    # callback: those events arrive after the next morph write (T-238 / T-245).
    own, hold = m.setdefault('own', {}), m.setdefault('hold', [])
    for k in list(own):
        p = getattr(c.par, k, None)
        if k not in hold and p is not None and p.mode == ParMode.CONSTANT and Lg.hand_moved(p.eval(), own[k]):
            hold.append(k)
    if hold:
        vals = dict((k, v) for k, v in vals.items() if k not in hold)
    _apply_values(c, vals)
    m['own'] = dict(vals)
    _apply_effectors(c, m['eb'], Lg.curve(t, m['curve']), m['ea'])
    if t >= 1.0:
        S(c)['morph'] = None
        status(c, 'morph done: %s' % m['name'])


def delete_preset(c, name):
    t = c.op('px_presets')
    for r in range(t.numRows - 1, 0, -1):
        if t[r, 'name'].val == name:
            t.deleteRow(r)


def _preset_rows(c):
    t = c.op('px_presets')
    return t, [(t[r, 0].val, t[r, 1].val) for r in range(1, t.numRows)]


def _write_order(c, t, rows, names):
    """Rewrite px_presets' cells in the order `names` (a permutation of the row names). Same rows, same count:
    nothing is deleted or appended; refused (False) unless it is exactly a permutation (duplicates included)."""
    if sorted(names) != sorted(n for n, _j in rows):
        return False
    pool = {}
    for n, j in rows:
        pool.setdefault(n, []).append(j)
    new = [(n, pool[n].pop(0)) for n in names]
    for r, (n, j) in enumerate(new, start=1):
        if t[r, 0].val != n:
            t[r, 0] = n
        if t[r, 1].val != j:
            t[r, 1] = j
    return True


def move_preset(c, name, delta):
    """Presetup / Presetdown: move the selected preset one row; the Presetname dropdown lists px_presets' order."""
    t, rows = _preset_rows(c)
    names = [n for n, _j in rows]
    if name not in names:
        status(c, 'no preset %r' % name)
        return False
    ok = _write_order(c, t, rows, L().preset_move(names, name, delta))
    status(c, 'moved %s to #%d' % (name, [r[0] for r in _preset_rows(c)[1]].index(name) + 1) if ok else 'move refused')
    return ok


def sort_presets(c):
    """Presetsort: A-Z, built-in looks first."""
    t, rows = _preset_rows(c)
    ok = _write_order(c, t, rows, L().preset_sort([n for n, _j in rows]))
    status(c, 'presets sorted A-Z (built-ins first)' if ok else 'sort refused')
    return ok


def rename_preset(c, old, new):
    """Presetrename: Presetname -> Newname (row and order kept; the snapshot's own name follows). A renamed built-in
    becomes your own look; the next PX build adds the built-in again under its own name."""
    t, rows = _preset_rows(c)
    new = str(new or '').strip()
    why = L().preset_rename_check([n for n, _j in rows], old, new)
    if why:
        status(c, 'rename: ' + why)
        return False
    for r in range(1, t.numRows):
        if t[r, 0].val == old:
            try:
                d = json.loads(t[r, 1].val)
                d['name'] = new
                t[r, 1] = L().preset_dumps(d)
            except Exception:
                pass
            t[r, 0] = new
            break
    if c.par.Presetname.eval() == old:
        c.par.Presetname = new
    if getattr(c.par, 'Newname', None) is not None:
        c.par.Newname = ''
    status(c, 'renamed %s -> %s' % (old, new))
    return True


# ------------------------------------------------------------------------------------------------- setlist (28 Oct)
# Presets as scenes in show order (phase A). The setlist only references preset names: px_setlist (or the DAT in
# Setlist), one column `name`; empty = px_presets' order. Next / Prev wrap and skip missing names; Go jumps to Cue;
# CQ_cuelist / TL_timeline set Cueindex (a number, 1-based) or call setlist_go(comp, 'name'). The transition is the
# preset Morph (load-safe, T-237) over Transition s (beats with Beatsync), 0 = Recall. Nothing changes a preset.

def setlist(c):
    '''-> (scene names in show order, preset names).'''
    _t, rows = _preset_rows(c)
    pres = [n for n, _j in rows]
    d = c.par.Setlist.eval() if getattr(c.par, 'Setlist', None) is not None else None
    names = []
    if d is not None and getattr(d, 'isDAT', False) and d.isTable and d.numRows > 1:
        col = 0
        if d[0, 'name'] is not None:
            col = d[0, 'name'].col
        names = [d[r, col].val for r in range(1, d.numRows)]
    return L().setlist_names(names, pres), pres


def _set_current(c, names, pos):
    S(c)['cue_pos'] = pos
    c.store('px_cue_pos', pos if pos is not None else -1)
    p = getattr(c.par, 'Current', None)
    if p is not None:
        txt = L().current_text(names, pos)
        if p.eval() != txt:
            ro = p.readOnly
            p.readOnly = False
            p.val = txt
            p.readOnly = ro
    # Cueindex is NOT mirrored: it is the CQ / TL input. A timeline lane writes it every frame; mirroring Next / Prev
    # into it would make the lane's next write undo the hand's Next (manual control wins).


def _cue_pos(c):
    s = S(c)
    if s.get('cue_pos') is None:
        k = int(c.fetch('px_cue_pos', -1, search=False))
        s['cue_pos'] = k if k >= 0 else None
    return s['cue_pos']


def setlist_go(c, cue):
    '''Go to a setlist scene: cue = a name, a '3 name' label, a 1-based number text, or an int index (0-based).
    Missing names are refused ("(missing)" in Status). -> the scene name or None. CQ / TL / any script:
    op('<PX>/px_rt').module.setlist_go(op('<PX>'), 'KANDA swipe').'''
    Lg = L()
    names, pres = setlist(c)
    k = cue if isinstance(cue, int) else Lg.cue_index(names, cue)
    if k is None and str(cue or '').strip() == '' and _cue_pos(c) is not None:
        k = _cue_pos(c)                                # Go with no Cue = replay the current scene
    if k is None or not (0 <= k < len(names)):
        status(c, 'setlist: no scene %r' % (cue,))
        return None
    nm = names[k]
    if nm not in pres:
        status(c, 'setlist: %s (missing) skipped' % nm)
        return None
    raw = S(c).get('raw') or {}
    beat = bool(c.par.Beatsync.eval()) if getattr(c.par, 'Beatsync', None) is not None else False
    bpm = S(c).get('au_bpm') or _tempo(c, raw if raw else {'Tempo': c.par.Tempo.eval(), 'Bpm': c.par.Bpm.eval()})
    dur = Lg.transition_seconds(c.par.Transition.eval(), beat, bpm)
    _set_current(c, names, k)
    if dur <= 0.0:
        iss = recall(c, nm)
    else:
        iss = morph_to(c, nm, dur, Lg.trans_curve(c.par.Transcurve.eval()))
    miss = Lg.setlist_missing(names, pres)
    kept = ('; ' + Lg.SOURCE_KEPT_NOTE) if hasattr(Lg, 'SOURCE_KEPT_NOTE') and _keeps_source(c) else ''
    status(c, 'scene %s%s%s%s%s' % (Lg.current_text(names, k), ' (cut)' if dur <= 0.0 else ' (%.2f s)' % dur,
                                   ('; missing: ' + ', '.join(miss)) if miss else '', kept,
                                   (' | ' + iss.split(': ', 1)[-1]) if iss else ''))
    return nm


def setlist_step(c, delta):
    '''Next (+1) / Prev (-1): wrap, skip "(missing)" names.'''
    Lg = L()
    names, pres = setlist(c)
    k, skipped = Lg.setlist_step(names, pres, _cue_pos(c), delta)
    if k is None:
        status(c, 'setlist: nothing to play' + (' (missing: %s)' % ', '.join(skipped) if skipped else ''))
        return None
    nm = setlist_go(c, k)
    if skipped and nm:
        status(c, '%s; skipped (missing): %s' % (c.par.Status.eval(), ', '.join(skipped)))
    return nm


def setlist_fill(c):
    '''Setlistfill: px_setlist <- the presets order (to edit by hand). The presets are never touched.'''
    d = c.par.Setlist.eval()
    if d is None or not getattr(d, 'isTable', False):
        status(c, 'setlist: Setlist is not a table DAT')
        return 0
    _t, rows = _preset_rows(c)
    d.clear()
    d.appendRow(['name'])
    for n, _j in rows:
        d.appendRow([n])
    status(c, 'setlist: %d scenes (presets order)' % len(rows))
    return len(rows)


# ------------------------------------------------------------------------------------------------- dropdowns

def _ml(c):
    return c.op('menu_logic').module


def menu(c, name):
    """Items of PX's live dropdowns (menuSource = px_logic.menu_source(name), T-233): built on each menu read (menu
    open, panel build), never per frame. Presetname = stored presets; Sel = the stack ('4 Dissolve: noise (off)');
    Effname / Actorfollow / Camfollow = PX's effector objects; M<uid>effectors / Vhlights / Geolights = helper items
    that add / remove a name or #tag (the text stays free)."""
    ML = _ml(c)
    try:
        if name == 'Presetname':
            t = c.op('px_presets')
            return ML.name_menu([t[r, 0].val for r in range(1, t.numRows)] if t is not None else [])
        if name == 'Cue':                          # setlist scenes, '3 KANDA swipe' / '(missing)'
            nm, pr = setlist(c)
            lab = L().setlist_labels(nm, pr)       # item = '3 name': unique even when a look is in the show twice
            return ML.name_menu(lab, lab)
        if name == 'Sel':
            st = stack(c)
            so = solo_uid(c)
            return ML.name_menu([str(i['uid']) for i in st], [L().sel_label(i, so) for i in st])
        if name == 'Addtype':                      # phase B module browser: 'Motion > Explode / reassemble - ...'
            nm, lab = L().module_browser()
            return ML.name_menu(nm, lab)
        if name == 'Camcomp':                      # phase C Usecam: Camera COMPs under /project1 (PX's own left out)
            root = op('/project1')
            cams = [o.path for o in root.findChildren(type=cameraCOMP)
                    if o.OPType == 'cameraCOMP'] if root is not None else []          # T-241: OPType, not subclasses
            items = L().cam_menu_items(cams, c.path)
            return ML.name_menu(items, items, none=True)
        if name in ('Effname', 'Actorfollow', 'Camfollow'):
            effs = eff_table(c)
            return ML.name_menu([e['name'] for e in effs], ['%s (%s)' % (e['name'], e.get('kind', '')) for e in effs],
                                none=(name != 'Effname'))
        cur = getattr(c.par, name).eval()
        ert = _eff_rt()
        rows = list(ert.rows()) if ert is not None else []
        if name == 'Vhlights':
            lit = [r for r in rows if r.get('kind') == 'light']
            return ML.select_menu(cur, [r['name'] for r in lit], _tags(lit))
        if name == 'Geolights':
            eff = op('/project1/effectors')
            cands = [(o.path, list(o.tags)) for o in eff.findChildren(type=lightCOMP, maxDepth=2)] if eff is not None else []
            tags = ['light'] + sorted(set(t for _p, ts in cands for t in ts) - {'light'})
            return ML.select_menu(cur, [p for p, _t in cands], tags, all_word=None)
        if name.startswith('M') and name.endswith('effectors'):
            uid = L().sel_uid(name[1:-len('effectors')], -1)
            inst = next((i for i in stack(c) if i['uid'] == uid), None)
            shared_only = inst is not None and L().MODULES[inst['type']].get('shared_only', False)
            own = [] if shared_only else [e['name'] for e in eff_table(c)]
            kinds = dict((e['name'], e.get('kind', '')) for e in eff_table(c) if e['name'] in own)
            shared = [r for r in rows if r['name'] not in own]          # own names win (split_effectors)
            kinds.update((r['name'], 'shared ' + r.get('kind', '')) for r in shared)
            return ML.select_menu(cur, own + [r['name'] for r in shared], _tags(rows), kinds=kinds)
    except Exception:                                  # a menu never raises: the field stays free text
        return ML.Menu()
    return ML.Menu()


def _resolution(c, name):
    """Resolution picked -> Resx / Resy (custom: left as typed); Resx / Resy typed to a size the picked item does not
    have -> custom. px_values delivers the Resx / Resy events of a pick a frame LATE, together with the next pick
    (live b3, T-236): a Resx / Resy event whose size is the one the last pick wrote is that echo and is ignored.
    Only constant pars are written (an expression / bind on Resx stays in charge)."""
    Lg = L()
    s = S(c)
    r, x, y = c.par.Resolution, c.par.Resx, c.par.Resy
    cur = (int(x.eval()), int(y.eval()))
    if name == 'Resolution':
        wh = Lg.res_size(r.eval())
        s['res_set'] = wh if wh is not None else cur
        if wh is not None:
            for p, v in zip((x, y), wh):
                if p.mode == ParMode.CONSTANT and int(p.eval()) != v:
                    p.val = v
        return
    if tuple(s.get('res_set') or ()) == cur:
        return
    s['res_set'] = cur
    if r.mode == ParMode.CONSTANT and r.eval() != 'custom' and Lg.res_size(r.eval()) != cur:
        r.val = 'custom'


def _tags(rows):
    return sorted(set(t for r in rows for t in str(r.get('tags', '')).replace(',', ' ').split()))


# ------------------------------------------------------------------------------------------------- callbacks

def on_pulse(par):
    c = par.owner
    n = par.name
    sel = L().sel_uid(c.par.Sel.eval())          # Sel = StrMenu text since T-233 (Int in older COMPs)
    if n == 'Reset':
        S(c)['reset'] = 2
        S(c)['mt0'] = S(c)['simt']                 # motion paths restart
        S(c)['trail'] = {}
        S(c)['sort_dirty'] = True
    elif n == 'Sortnow':
        S(c)['sortnow'] = True
    elif n == 'Reload':
        load(c)
    elif n.startswith('Trig') and n[4:].isdigit():
        S(c)['trig_t'][int(n[4:]) - 1] = S(c)['simt']
    elif n == 'Add':
        after = bool(c.par.Addafter.eval()) if getattr(c.par, 'Addafter', None) is not None else False
        at = L().add_index(stack(c), sel, after) if hasattr(L(), 'add_index') else None
        add(c, c.par.Addtype.eval(), at=at)
    elif n == 'Solo':
        solo(c, sel)
    elif n == 'Unsolo':
        unsolo(c)
    elif n == 'Remove':
        remove(c, sel)
    elif n == 'Duplicate':
        duplicate(c, sel)
    elif n == 'Moveup':
        move(c, sel, -1)
    elif n == 'Movedown':
        move(c, sel, 1)
    elif n == 'Toggleon':
        toggle(c, sel)
    elif n == 'Addeffector':
        add_effector(c, c.par.Effkind.eval())
    elif n == 'Removeeffector':
        remove_effector(c, c.par.Effname.eval())
    elif n == 'Store':
        store(c, c.par.Presetname.eval())
    elif n == 'Recall':
        recall(c, c.par.Presetname.eval())
    elif n == 'Deletepreset':
        delete_preset(c, c.par.Presetname.eval())
    elif n == 'Morphto':
        morph_to(c, c.par.Presetname.eval())
    elif n in ('Presetup', 'Presetdown'):
        move_preset(c, c.par.Presetname.eval(), -1 if n == 'Presetup' else 1)
    elif n == 'Presetrename':
        rename_preset(c, c.par.Presetname.eval(), c.par.Newname.eval())
    elif n == 'Presetsort':
        sort_presets(c)
    elif n == 'Stopmorph':
        S(c)['morph'] = None
    elif n in ('Next', 'Prev'):                       # setlist (28 Oct phase A)
        setlist_step(c, 1 if n == 'Next' else -1)
    elif n == 'Go':
        setlist_go(c, c.par.Cue.eval())
    elif n == 'Setlistfill':
        setlist_fill(c)
    elif n == 'Addlight':
        add_light(c)
    elif n == 'Geoadd':
        add_geo(c)
    elif n == 'Opencontrols':
        w = c.op('controls_window')
        if c.fetch('px_ui_dirty', False, search=False):
            rebuild_ui(c)                         # pages changed while the window was closed
        if w is not None:
            w.par.winopen.pulse()


LOAD_PARS = ('Afile', 'Bfile', 'Amode', 'Bmode', 'Aup', 'Bup', 'Quality', 'Count', 'Match', 'Actormode', 'Actorfile',
             'Actorseq', 'Actorcount', 'Actorup', 'Pool', 'Clip', 'Opacitymin')


def on_value(par):
    c = par.owner
    if par.name in ('Resolution', 'Resx', 'Resy'):  # render resolution menu (28 Oct): Resx / Resy follow it
        _resolution(c, par.name)
        return
    if par.name == 'Cueindex':                       # setlist hook (CQ / TL set a number): go to scene #n when it
                                                     # changes (not when that scene is already the current one)
        k = int(par.eval())
        if k > 0 and k - 1 != S(c).get('cue_pos'):
            setlist_go(c, k - 1)
        return
    if par.name == 'Geoon':                          # W1-E: the splat shader text follows Geoon (geo adapter in / out)
        geo_sync(c)
        return
    if par.name == 'Soundon' and c.op('sound') is not None:   # wave 4 K34: the sound COMP cooks only while on
        c.op('sound').allowCooking = bool(par.eval())
    if par.name in ('Echoes', 'Actormode'):           # wave 3: echo code is in the stage shaders only while on
        stack_changed(c)
    if par.name in LOAD_PARS:                       # debounced: ONE load 6 frames after the last source change (T-237)
        s = S(c)
        stale = absTime.frame - int(s.get('load_req', -10 ** 9)) > 120    # a lost schedule never blocks loads
        s['load_req'] = absTime.frame
        if not s.get('load_sched') or stale:
            s['load_sched'] = True
            run("op(%r).module.load_due(op(%r))" % (me.path, c.path), delayFrames=6, delayRef=op.TDResources)


LOAD_QUIET = 6                                     # frames with no source-par change before the load runs


def load_due(c):
    """The debounced load: waits until no source par changed for LOAD_QUIET frames (a recall sets ~10 of them in one
    frame; each used to schedule its own full reload), then loads once."""
    s = S(c)
    wait = LOAD_QUIET - (absTime.frame - int(s.get('load_req', -10 ** 9)))
    if wait > 0:
        run("op(%r).module.load_due(op(%r))" % (me.path, c.path), delayFrames=wait, delayRef=op.TDResources)
        return
    load(c)
