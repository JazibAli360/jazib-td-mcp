# dmx_patch_rt - TD runtime for BK_dmx_patch (copied into the COMP's `patch_rt` Text DAT).
# Logic: `patch_logic` (= builders/dmx_patch_logic.py) and `dmx_logic` (= builders/dmx_logic.py, BK_dmx_out's).
# Called by: state / pix_pos / pix_col / owner / aim (Script CHOPs), src_watch + stage_watch (DAT Execute),
# settings + dmx_pars (Parameter Execute), status_tick (Execute, every 30 frames), camera/uniform expressions.
# Reads BK_dmx_out (Dmxcomp): its patch / pixels / profiles_json tables and its out3 universes CHOP. Never writes it.
# T-74: no TOP pixel readback anywhere (DMX values come from a CHOP). T-67: state is a module dict, never op storage.
# Tables are written only from callbacks / pulses, never inside a cook (a plan built inside a cook writes 1 frame later).
# ASCII only.
import os
import time

S = {'plan': None, 'dec': None, 'sel': None, 'pixpos': None, 'owner': None, 'labels': [], 'conflicts': 0,
     'pairs_key': None, 'pairs': [], 'flat': None, 'flat_key': None, 'prev': {}, 'missed': [], 'err': '',
     'state_ms': 0.0, 'pix_ms': 0.0, 'pending': False, 'nfix': 0, 'npix': 0}
REPLAN_PARS = ('Dmxcomp', 'Univchop', 'Chanfmt', 'Pixmax', 'Wallx', 'Wally', 'Wallz', 'Wallw', 'Wallh')
PULSES = ('Syncpatch', 'Prune', 'Applyarrange', 'Fit', 'Calibrate', 'Exportsheet', 'Checkpatch', 'Resetdefaults')


def C():
    return me.parent()


def L():
    return C().op('patch_logic').module


def D():
    return C().op('dmx_logic').module


def _pv(name, d=None):
    p = getattr(C().par, name, None)
    return d if p is None else p.eval()


def _rows(dat):
    if dat is None:
        return []
    return [[c.val for c in r] for r in dat.rows()]


def dmx():
    """The BK_dmx_out this helper reads (Dmxcomp par), or None."""
    o = _pv('Dmxcomp', None)
    return o if (o is not None and getattr(o, 'isCOMP', False)) else None


def _dmx_par(name, d):
    o = dmx()
    p = getattr(o.par, name, None) if o is not None else None
    return d if p is None else p.eval()


def univ_src():
    """Path for the univ_in Select CHOP: Univchop if set, else <Dmxcomp>/out3."""
    u = _pv('Univchop', None)
    if u is not None:
        return u.path
    o = dmx()
    if o is not None and o.op('out3') is not None:
        return o.op('out3').path
    return ''


def source_dats():
    """Space-separated DAT paths src_watch listens to (the BK_dmx_out tables)."""
    o = dmx()
    if o is None:
        return ''
    return ' '.join(o.op(n).path for n in ('patch', 'pixels', 'profiles_json') if o.op(n) is not None)


# ---------------------------------------------------------------- plan (static data)
def _src_tables():
    Dm, o = D(), dmx()
    if o is None:
        return [], Dm.builtin_profiles(), []
    profiles = Dm.profiles_from_text(o.op('profiles_json').text if o.op('profiles_json') is not None else '')
    patch = Dm.rows_to_dicts(_rows(o.op('patch')), Dm.PATCH_COLS)
    pixels = Dm.rows_to_dicts(_rows(o.op('pixels')), Dm.PIXEL_COLS)
    return patch, profiles, pixels


def stage_rows():
    return L().rows_to_dicts(_rows(C().op('stage')), L().STAGE_COLS)


def replan(write=True):
    Dm, Lg = D(), L()
    patch, profiles, pixels = _src_tables()
    try:
        filt = Dm.parse_univfilter(_dmx_par('Univfilter', ''))
    except ValueError:
        filt = None
    order = _dmx_par('Colororder', 'rgb')
    try:
        pl = Dm.build_plan(patch, profiles, pixels, order, filt)
        S['err'] = ''
    except Exception as e:                   # a bad row in the source tables: keep the helper alive, show why
        S['err'] = 'plan: %s' % str(e)[:200]
        pl = Dm.build_plan([], profiles, [], order, None)
    st = stage_rows()
    S['plan'] = pl
    S['dec'] = Lg.build_decode(Dm, pl, st)
    wall = (_pv('Wallx', 0.0), _pv('Wally', 3.0), _pv('Wallz', -1.0), _pv('Wallw', 8.0), _pv('Wallh', 4.5))
    S['sel'], S['pixpos'] = Lg.pixel_layout(pixels, wall, int(_pv('Pixmax', 4096)))
    try:
        S['owner'], S['labels'], S['conflicts'] = Lg.owner_grid(Dm, pl, patch, profiles, pixels)
    except Exception as e:
        S['owner'], S['labels'], S['conflicts'] = None, [], 0
        S['err'] = 'owner: %s' % str(e)[:200]
    S['pairs_key'] = None
    S['flat_key'] = None
    S['nfix'], S['npix'] = S['dec']['n'], len(S['sel'])
    if write:
        write_static(patch, profiles, st)
    else:
        S['pending'] = True
    return pl


def plan():
    if S['plan'] is None:
        replan(write=False)
    return S['plan']


def write_static(patch=None, profiles=None, st=None):
    """Sheet table + re-cook the static CHOPs (pix_pos, owner). Callbacks / delayed runs only, never in a cook."""
    S['pending'] = False
    c, Dm, Lg = C(), D(), L()
    if patch is None:
        patch, profiles, _ = _src_tables()
        st = stage_rows()
    rows = Lg.patch_sheet(Dm, patch, profiles, st, int(_dmx_par('Firstuniv', 0)))
    tab = Lg.dicts_to_rows(rows, Lg.SHEET_COLS)
    sh = c.op('sheet')
    if sh is not None:
        txt = '\n'.join('\t'.join(r) for r in tab)
        if sh.text.strip() != txt.strip():
            sh.clear()
            sh.appendRows(tab)
    for n in ('pix_pos', 'owner'):
        o = c.op(n)
        if o is not None:
            o.cook(force=True)               # CHOPs: no GPU readback involved (T-74 is about TOPs)


def _later(call):
    run("op(%r).module.%s" % (me.path, call), delayFrames=1, delayRef=op.TDResources)


# ---------------------------------------------------------------- DMX values (per frame)
def get_flat(chop):
    """Slot values in plan row order from the universes CHOP (names fmt.format(u=flat + Firstuniv)); cached per
    cook of that CHOP, so state and pix_col share one assemble."""
    import numpy as np
    pl, Lg = plan(), L()
    key = (chop.path, chop.totalCooks) if chop is not None else None
    if key is not None and key == S['flat_key'] and S['flat'] is not None:
        return S['flat']
    if S['flat'] is None or len(S['flat']) != pl['nrows'] * 512:
        S['flat'] = np.zeros(pl['nrows'] * 512)
    if chop is None or not chop.numChans:
        S['flat'][:] = 0.0
        S['flat_key'] = key
        return S['flat']
    names = tuple(c_.name for c_ in chop.chans())
    pk = (names, int(_dmx_par('Firstuniv', 0)), _pv('Chanfmt', 'u{u}'), id(pl))
    if pk != S['pairs_key']:
        S['pairs'] = Lg.chan_rows(pl, names, pk[1], pk[2])
        S['pairs_key'] = pk
    Lg.assemble(pl, chop.numpyArray(), S['pairs'], S['flat'])
    S['flat_key'] = key
    return S['flat']


def _put(scriptOp, n, chans):
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = int(n)
    import numpy as np
    for name, arr in chans.items():
        scriptOp.appendChan(name).vals = np.asarray(arr, dtype=np.float64).tolist()


def cook_state(scriptOp):
    """Per fixture (one sample each): body + beam instance channels."""
    t0 = time.perf_counter()
    plan()
    dec, Lg = S['dec'], L()
    ins = scriptOp.inputs
    flat = get_flat(ins[0] if len(ins) else None)
    st = Lg.decode(dec, flat)
    hl = Lg.highlight_index(dec['names'], _pv('Highlight', ''))
    inst = Lg.fixture_instances(dec, st, _pv('Bodysize', 0.25), _pv('Beamlen', 8.0), _pv('Beamangle', 15.0),
                                _pv('Beamgain', 0.5), _pv('Mingrey', 0.12), bool(_pv('Beams', True)), hl)
    ch = dict(inst['body'])
    ch.update(inst['beam'])
    _put(scriptOp, dec['n'], ch)
    S['state_ms'] = (time.perf_counter() - t0) * 1000.0
    if S['pending']:
        _later('write_static()')
        S['pending'] = False


def cook_pix_pos(scriptOp):
    """Static: one sample per shown pixel (tx ty tz s). Re-cooked by write_static after a plan change."""
    plan()
    p = S['pixpos']
    s = _pv('Pixsize', 0.06)
    _put(scriptOp, len(p), {'tx': p[:, 0], 'ty': p[:, 1], 'tz': p[:, 2], 's': [s] * len(p)})


def cook_pix_col(scriptOp):
    t0 = time.perf_counter()
    pl, Lg = plan(), L()
    ins = scriptOp.inputs
    flat = get_flat(ins[0] if len(ins) else None)
    rgb = Lg.pixel_colours(pl, S['sel'], flat, pl['order'])
    g = _pv('Pixgain', 1.0)
    _put(scriptOp, len(rgb), {'r': rgb[:, 0] * g, 'g': rgb[:, 1] * g, 'b': rgb[:, 2] * g})
    S['pix_ms'] = (time.perf_counter() - t0) * 1000.0


def cook_owner(scriptOp):
    """Static: one 512-sample channel per sent universe (BK_dmx_out out3 order), value = owner id."""
    pl = plan()
    g = S['owner']
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 512
    first = int(_dmx_par('Firstuniv', 0))
    if g is None or not len(g):
        scriptOp.appendChan('o_none')
        return
    for u, row in zip(pl['send_univs'], g):
        scriptOp.appendChan('o%d' % (u + first)).vals = [float(x) for x in row]


def target():
    t = _pv('Targetchop', None)
    if t is not None and getattr(t, 'isCHOP', False):
        vals = []
        for k, n in enumerate(('tx', 'ty', 'tz')):
            ch = t[n] if t[n] is not None else (t[k] if k < t.numChans else None)
            vals.append(float(ch.eval()) if ch is not None else 0.0)
        return tuple(vals)
    return (_pv('Targetx', 0.0), _pv('Targety', 0.0), _pv('Targetz', 4.0))


def cook_aim(scriptOp):
    """'<fixture>.pan' / '<fixture>.tilt' 0..1 for BK_dmx_out in2, while Aimon is on."""
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    if not _pv('Aimon', False):
        S['missed'] = []
        return
    plan()
    names, vals, S['prev'], S['missed'] = L().aim_all(D(), S['dec'], target(), _pv('Aimset', '*'), S['prev'])
    for n, v in zip(names, vals):
        scriptOp.appendChan(n)[0] = float(v)


# ---------------------------------------------------------------- expressions (camera, uniforms)
def cam():
    return L().camera(_pv('View', 'front'), (_pv('Centerx', 0.0), _pv('Centery', 3.0), _pv('Centerz', 0.0)),
                      _pv('Viewsize', 16.0), _pv('Fov', 40.0), _pv('Orbit', 30.0), _pv('Elev', 20.0))


def sel_owner():
    """Owner id (1-based) of the first fixture matching Highlight, 0 = none (address map outline)."""
    if S['dec'] is None:
        return 0
    hl = L().highlight_index(S['dec']['names'], _pv('Highlight', ''))
    return (hl[0] + 1) if hl else 0


def map_layout():
    return D().monitor_layout(_pv('Mapw', 1024), _pv('Maph', 768), _pv('Mapcell', 6), _pv('Mapcount', 16))


def nfix():
    return S['nfix'] if S['dec'] is not None else len(plan()['fixtures'])


# ---------------------------------------------------------------- callbacks
def report(text):
    r = C().op('report')
    if r is not None:
        r.text = text


def _write_stage(rows):
    Lg = L()
    tab = Lg.dicts_to_rows(rows, Lg.STAGE_COLS)
    d = C().op('stage')
    txt = '\n'.join('\t'.join(r) for r in tab)
    if d.text.strip() != txt.strip():
        d.clear()
        d.appendRows(tab)                    # stage_watch replans
        return True
    return False


def _arr():
    return {'layout': _pv('Arrange', 'line'), 'span': _pv('Spanx', 12.0), 'height': _pv('Height', 6.0),
            'depth': _pv('Depth', 0.0), 'curve': _pv('Curve', 60.0), 'cols': int(_pv('Cols', 8)),
            'rowgap': _pv('Rowgap', 1.0), 'hang': bool(_pv('Hang', True))}


def sync(prune=False):
    pl = replan(write=False)
    rows, added, stale = L().sync_stage(stage_rows(), pl['fixtures'], prune, **_arr())
    changed = _write_stage(rows)
    if not changed:
        replan(write=True)
    msg = 'sync: %d fixtures, added %d%s' % (len(pl['fixtures']), len(added), (': ' + ' '.join(added[:20])) if added else '')
    if stale:
        msg += '\nstale (not in the patch, pulse Prune): ' + ' '.join(stale[:40])
    report(msg)


def on_source_change():
    """BK_dmx_out's patch / pixels / profiles changed."""
    if _pv('Autosync', True):
        sync(False)
    else:
        replan(write=True)


def on_stage_change():
    replan(write=True)


def check():
    Dm, Lg = D(), L()
    patch, profiles, pixels = _src_tables()
    pl = plan()
    issues = [tuple(i) for i in Dm.check_patch(patch, profiles, pixels)]
    issues += Lg.stage_issues(pl['fixtures'], stage_rows())
    if S['missed']:
        issues.append(('aim_out_of_range', ' '.join(S['missed'][:20]), 'clamped'))
    if S['err']:
        issues.append(('error', 'plan', S['err']))
    report(Lg.issue_text(issues))
    return issues


def export_sheet():
    Dm, Lg = D(), L()
    patch, profiles, pixels = _src_tables()
    st = stage_rows()
    rows = Lg.patch_sheet(Dm, patch, profiles, st, int(_dmx_par('Firstuniv', 0)))
    issues = check()
    folder = _pv('Sheetdir', '') or os.path.join(os.path.dirname(project.folder), 'output', 'dmx')
    name = (_pv('Sheetname', '') or 'dmx_patch').strip()
    os.makedirs(folder, exist_ok=True)
    pcsv, pmd = os.path.join(folder, name + '.csv'), os.path.join(folder, name + '.md')
    with open(pcsv, 'w', encoding='utf-8') as f:
        f.write(Lg.sheet_csv(rows))
    with open(pmd, 'w', encoding='utf-8') as f:
        f.write(Lg.sheet_md(rows, issues, 'DMX patch: ' + name, _dmx_par('Protocol', 'artnet'), len(pixels)))
    report('sheet: %d fixtures -> %s, %s' % (len(rows), pcsv, pmd))


def fit():
    import numpy as np
    plan()
    pts = [S['dec']['pos']] + ([S['pixpos']] if len(S['pixpos']) else [])
    P = np.vstack(pts) if sum(len(p) for p in pts) else np.zeros((0, 3))
    rw, rh = max(1, _pv('Resw', 1080)), max(1, _pv('Resh', 1920))
    ctr, size = L().fit_view(P, _pv('View', 'front'), rw / float(rh), 1.15, _pv('Orbit', 30.0), _pv('Elev', 20.0))
    c = C()
    c.par.Centerx, c.par.Centery, c.par.Centerz = [round(v, 3) for v in ctr]
    c.par.Viewsize = round(size, 3)


def calibrate():
    Dm, Lg = D(), L()
    plan()
    name = (_pv('Calfixture', '') or '').strip()
    dec = S['dec']
    if name not in dec['names']:
        report('calibrate: no fixture %r' % name)
        return
    k = dec['names'].index(name)
    if not dec['has_pt'][k]:
        report('calibrate: %s has no pan/tilt' % name)
        return
    pz0 = dec['cal'][k][0]
    pz, to = Lg.calibrate(Dm, tuple(dec['pos'][k]), tuple(dec['rot'][k]), target(), _pv('Calpan', 0.5),
                          _pv('Caltilt', 0.5), dec['range']['pan'][k], dec['range']['tilt'][k], dec['cal'][k][2],
                          dec['cal'][k][3], pz0)
    rows = stage_rows()
    for r in rows:
        if r['name'] == name:
            r['pan_zero'], r['tilt_off'] = round(pz, 6), round(to, 4)
    _write_stage(rows)
    report('calibrate %s: pan_zero %.6f (was %.6f), tilt_off %.4f deg' % (name, pz, pz0, to))


def on_pulse(par):
    n = par.name
    if n == 'Syncpatch':
        sync(False)
    elif n == 'Prune':
        sync(True)
    elif n == 'Applyarrange':
        rows, k = L().apply_arrange(stage_rows(), _pv('Arrangeset', '*'), **_arr())
        _write_stage(rows)
        report('arranged %d (%s)' % (k, _pv('Arrange', 'line')))
    elif n == 'Fit':
        fit()
    elif n == 'Calibrate':
        calibrate()
    elif n == 'Exportsheet':
        export_sheet()
    elif n == 'Checkpatch':
        check()
    elif n == 'Resetdefaults':
        for p in C().customPars:
            if p.page.name == 'Zkit' or p.readOnly or p.isPulse or p.isMomentary:
                continue
            try:
                p.val = p.default
            except Exception:
                pass


def on_value(par):
    if par.name in REPLAN_PARS:
        replan(write=True)


def on_dmx_value(par):
    """Colororder / Univfilter / Firstuniv changed on BK_dmx_out."""
    replan(write=True)


def status():
    """Read-only status pars (Execute DAT, every 30 frames; never inside a cook)."""
    c = C()
    if S['plan'] is None:
        return
    for name, v in (('Fixtures', S['nfix']), ('Pixelsshown', S['npix']), ('Conflicts', S['conflicts']),
                    ('Statems', round(S['state_ms'] + S['pix_ms'], 3)), ('Aimmissed', len(S['missed']))):
        p = getattr(c.par, name, None)
        if p is not None and p.eval() != v:
            p.readOnly = False
            p.val = v
            p.readOnly = True
