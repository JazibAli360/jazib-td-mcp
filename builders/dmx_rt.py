# dmx_rt - TD runtime for BK_dmx_out (copied into the COMP's `dmx_rt` Text DAT; logic in `dmx_logic`).
# Called by: compose (Script CHOP), stats (Script CHOP), uvmap (Script TOP), plan_watch (DAT Execute on the tables),
# settings (Parameter Execute: plan pars + pulses), status_tick (Execute, every 30 frames).
# T-74: no TOP pixel readback anywhere (pixels arrive as a CHOP via TOP to CHOP); T-67: state is a module dict, never
# op storage. Tables are written only from callbacks, never inside a cook (first plan: written one frame later).
# ASCII only.
import time

S = {'plan': None, 'buf': None, 'compose_ms': 0.0, 'ms_avg': 0.0, 'frame': 0, 'taps': [], 'err': '',
     'npix_seen': 0, 'loopdiff': -1.0, 'pending_write': False}
PLAN_PARS = ('Colororder', 'Univfilter', 'Protocol', 'Targetmode', 'Targetip', 'Loopback', 'Firstuniv')
PULSES = ('Addfixture', 'Checkpatch', 'Importpulse', 'Clearpatch', 'Genpixels', 'Tapbpm', 'Resetdefaults')


def C():
    return me.parent()


def L():
    return C().op('dmx_logic').module


def _rows(dat):
    if dat is None:
        return []
    return [[c.val for c in r] for r in dat.rows()]


def _pv(name, d=None):
    p = getattr(C().par, name, None)
    return d if p is None else p.eval()


# ---------------------------------------------------------------- plan + tables
def replan(write=True):
    c, Lg = C(), L()
    profiles = Lg.profiles_from_text(c.op('profiles_json').text)
    patch = Lg.rows_to_dicts(_rows(c.op('patch')), Lg.PATCH_COLS)
    pixels = Lg.rows_to_dicts(_rows(c.op('pixels')), Lg.PIXEL_COLS)
    try:
        filt = Lg.parse_univfilter(_pv('Univfilter', ''))
    except ValueError:
        filt = None
    order = _pv('Colororder', 'rgb')
    S['plan'] = Lg.build_plan(patch, profiles, pixels, order, filt, _pv('Targetip', '127.0.0.1'))
    S['buf'] = None
    S['err'] = ''
    if write:
        write_tables()
    else:
        S['pending_write'] = True
    return S['plan']


def plan():
    return S['plan'] if S['plan'] is not None else replan(write=False)


def _set_table(dat, rows):
    if dat is None:
        return
    txt = '\n'.join('\t'.join(str(x) for x in r) for r in rows)
    if dat.text.strip() != txt.strip():
        dat.clear()
        dat.appendRows(rows)


def write_tables():
    c, Lg, pl = C(), L(), plan()
    S['pending_write'] = False
    first = int(_pv('Firstuniv', 0))
    rows = Lg.routing_rows(pl, _pv('Protocol', 'artnet'), _pv('Targetmode', 'unicast'), _pv('Targetip', '127.0.0.1'),
                           bool(_pv('Loopback', False)), first)
    if len(rows) == 1:                       # nothing patched: one row so the DMX Out has a valid table
        rows.append(['u_none', '0', '0', '0', '127.0.0.1'])
    _set_table(c.op('routing'), rows)
    _set_table(c.op('loop_filter'), [r[1:4] for r in rows])
    uv = c.op('uvmap')
    if uv is not None:
        uv.cook(force=True)                  # writes a texture; nothing reads pixels back here (T-74)


def on_table_change():
    replan(write=True)


# ---------------------------------------------------------------- pixel map texture
def pix_wh():
    n = plan()['npix'] if S['plan'] is not None else 0
    if n <= 0:
        return 1, 1
    w = min(n, 2048)
    return w, (n + w - 1) // w


def cook_uvmap(scriptOp):
    import numpy as np
    pl = plan()
    w, h = pix_wh()
    a = np.zeros((h, w, 4), dtype=np.float32)
    n = pl['npix']
    if n:
        rows = _rows(C().op('pixels'))[1:]
        u = np.array([float(r[1]) for r in rows[:n]], dtype=np.float32)
        v = np.array([float(r[2]) for r in rows[:n]], dtype=np.float32)
        flat = a.reshape(-1, 4)
        flat[:n, 0] = u
        flat[:n, 1] = v
        flat[:n, 3] = 1.0
    scriptOp.copyNumpyArray(a)


# ---------------------------------------------------------------- compose
def _fixture_inputs(ch):
    if ch is None or not ch.numChans:
        return None
    return {c_.name: float(c_.eval()) for c_ in ch.chans()}


def _pixels_in(ch, n, k4):
    if ch is None or not ch.numChans or n <= 0:
        return None
    a = ch.numpyArray()                      # CHOP data (CPU): (chans, samples); r g b a
    return L().pixchop_to_pixels(a, n, k4)


def master_eff(audio):
    Lg = L()
    return Lg.master_value(_pv('Masterfrom', 'manual'), absTime.seconds, _pv('Master', 1.0), _pv('Bpm', 120.0),
                           _pv('Beatshape', 'pulse'), _pv('Beatdepth', 1.0), audio, _pv('Audioamt', 1.0))


def cook_compose(scriptOp):
    t0 = time.perf_counter()
    Lg, pl = L(), plan()
    ins = scriptOp.inputs
    fix = _fixture_inputs(ins[0] if len(ins) > 0 else None)
    order = _pv('Colororder', 'rgb')
    pix = _pixels_in(ins[1] if len(ins) > 1 else None, pl['npix'], len(order) == 4)
    audio = 0.0
    if len(ins) > 2 and ins[2].numChans:
        audio = float(ins[2][0].eval())
    prm = {'whitemode': _pv('Whitemode', 'none'), 'gamma': _pv('Gamma', 1.0), 'pixelscale': _pv('Pixelscale', 255.0),
           'pattern': _pv('Pattern', 'live'), 'patternmix': _pv('Patternmix', 'replace'), 'level': _pv('Level', 1.0),
           'speed': _pv('Speed', 1.0), 'master_eff': master_eff(audio), 'blackout': bool(_pv('Blackout', False)),
           'blackoutmode': _pv('Blackoutmode', 'intensity'), 'freeze': bool(_pv('Freeze', False)),
           'solofixture': _pv('Solofixture', ''), 'solochan': int(_pv('Solochan', 0))}
    if prm['pattern'] != 'live' and _pv('Masterfrom', 'manual') == 'bpm':
        prm['speed'] = prm['speed'] * _pv('Bpm', 120.0) / 60.0      # Speed counts beats when Master follows BPM
    try:
        buf = Lg.compose(pl, fix, pix, absTime.seconds, prm, S['buf'])
        S['err'] = ''
    except Exception as e:                   # a bad table row must not kill the output: keep the last frame
        S['err'] = str(e)[:200]
        buf = S['buf'] if S['buf'] is not None else Lg.np.zeros((pl['nrows'], Lg.SLOTS), dtype=Lg.np.uint8)
    S['buf'] = buf
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = Lg.SLOTS
    names = Lg.wire_names(pl, int(_pv('Firstuniv', 0)))
    if not names:
        scriptOp.appendChan('u_none')
    fb = buf.astype(Lg.np.float32)
    for nm, r in zip(names, pl['send_rows']):
        scriptOp.appendChan(nm).copyNumpyArray(fb[r])    # 170 univ: 0.6 ms vs 3.1 ms with .vals = list (T-82)
    ms = (time.perf_counter() - t0) * 1000.0
    S['compose_ms'] = ms
    S['ms_avg'] = ms if not S['ms_avg'] else S['ms_avg'] * 0.95 + ms * 0.05
    S['frame'] = absTime.frame
    S['npix_seen'] = 0 if pix is None else len(pix)
    if S['pending_write']:
        run("op(%r).module.write_tables()" % me.path, delayFrames=1, delayRef=op.TDResources)
        S['pending_write'] = False
    return


# ---------------------------------------------------------------- stats
def packets_rate():
    pl = plan()
    if not _pv('Active', False) or _pv('Bypass', False):
        return 0.0
    # one packet per universe per compose cook; compose ticks at Rate, at most once per frame (cookRate)
    return min(float(_pv('Rate', 40.0)), float(project.cookRate)) * len(pl['send_rows'])


def cook_stats(scriptOp):
    Lg, pl = L(), plan()
    ld = -1.0
    if _pv('Loopback', False) and _pv('Protocol', 'artnet') != 'artnet':
        ld = -2.0                            # n/a: 31550's DMX In never receives sACN unicast on 127.0.0.1 (T-82)
    elif _pv('Loopback', False):
        din = C().op('dmxin')
        if din is not None and din.numChans and S['buf'] is not None:
            rec = din.numpyArray()
            ld = Lg.loop_diff(S['buf'][pl['send_rows']], rec)
    S['loopdiff'] = ld
    vals = {'packets_s': packets_rate(), 'universes': len(pl['send_rows']), 'slots_used': pl['slots_used'],
            'frame': S['frame'], 'compose_ms': S['compose_ms'], 'compose_ms_avg': S['ms_avg'], 'loopdiff': ld,
            'seq': -1.0, 'pixels': S['npix_seen'], 'error': 1.0 if S['err'] else 0.0}
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for k, v in vals.items():
        scriptOp.appendChan(k)[0] = float(v)
    return


def status():
    """Read-only status pars (Execute DAT, every 30 frames; never inside a cook)."""
    c, pl = C(), plan()
    sync_blur()
    for name, v in (('Universes', len(pl['send_rows'])), ('Slotsused', pl['slots_used']),
                    ('Packetsrate', round(packets_rate(), 1)), ('Mapok', 0 if S['err'] else 1)):
        p = getattr(c.par, name, None)
        if p is not None and p.eval() != v:
            p.readOnly = False
            p.val = v
            p.readOnly = True


# ---------------------------------------------------------------- patch helper + pulses
def _append_rows(dat, cols, dict_rows):
    if dat.numRows == 0:
        dat.appendRow(cols)
    for r in dict_rows:
        dat.appendRow([r.get(k, '') for k in cols])


def refresh_profile_menu():
    c, Lg = C(), L()
    profs = Lg.profiles_from_text(c.op('profiles_json').text)
    p = c.par.Profile
    p.menuNames = [x['id'] for x in profs]
    p.menuLabels = [x['name'] for x in profs]


def report(lines):
    C().op('patch_report').text = lines


def on_pulse(par):
    c, Lg = C(), L()
    n = par.name
    profiles = Lg.profiles_from_text(c.op('profiles_json').text)
    patch_dat, pix_dat = c.op('patch'), c.op('pixels')
    patch = Lg.rows_to_dicts(_rows(patch_dat), Lg.PATCH_COLS)
    pixels = Lg.rows_to_dicts(_rows(pix_dat), Lg.PIXEL_COLS)
    if n == 'Addfixture':
        try:
            rows = Lg.add_fixtures(patch, profiles, c.par.Profile.eval(), c.par.Mode.eval(), int(c.par.Count.eval()),
                                   c.par.Fixname.eval() or 'fx', int(c.par.Univ.eval()), int(c.par.Addr.eval()),
                                   bool(c.par.Autonext.eval()), c.par.Quantize.eval(), int(c.par.Gap.eval()),
                                   '', pixels)
            _append_rows(patch_dat, Lg.PATCH_COLS, rows)
            report('added %d: %s' % (len(rows), ' '.join('%s@%s.%s' % (r['name'], r['univ'], r['addr']) for r in rows)))
        except ValueError as e:
            report('add failed: %s' % e)
    elif n == 'Checkpatch':
        report(Lg.report_text(Lg.check_patch(patch, profiles, pixels)))
    elif n == 'Clearpatch':
        patch_dat.clear()
        patch_dat.appendRow(Lg.PATCH_COLS)
        pix_dat.clear()
        pix_dat.appendRow(Lg.PIXEL_COLS)
        report('patch cleared')
    elif n == 'Genpixels':
        order = c.par.Colororder.eval()
        u0, a0 = int(c.par.Univ.eval()), int(c.par.Addr.eval())
        if c.par.Autonext.eval() and patch:  # after the fixtures, from the next whole universe
            nf = Lg.next_free(patch, profiles)
            u0, a0 = nf // Lg.SLOTS + (1 if nf % Lg.SLOTS else 0), 1
        rows = Lg.gen_pixels(c.par.Pixlayout.eval(), int(c.par.Pixw.eval()), int(c.par.Pixh.eval()),
                             bool(c.par.Serpentine.eval()), int(c.par.Pixperuniv.eval()), u0, a0, len(order),
                             bool(c.par.Spanuniv.eval()))
        pix_dat.clear()
        pix_dat.appendRow(Lg.PIXEL_COLS)
        pix_dat.appendRows([[str(x) for x in r] for r in rows])
        report('pixels: %d (%s), universes %d..%d' % (len(rows), c.par.Pixlayout.eval(), rows[0][3], rows[-1][3])
               if rows else 'pixels: 0')
    elif n == 'Importpulse':
        path = c.par.Importfile.eval()
        try:
            text = open(path, encoding='utf-8').read()
        except OSError as e:
            report('import failed: %s' % e)
            return
        if path.lower().endswith('.json'):
            import json
            prof = Lg.ofl_to_profile(json.loads(text))
            dat = c.op('profiles_json')
            try:
                cur = json.loads(dat.text) if dat.text.strip() else []
            except ValueError:
                cur = []
            cur = [p for p in cur if p.get('id') != prof['id']] + [prof]
            dat.text = json.dumps(cur, indent=1)
            refresh_profile_menu()
            report('profile %s: modes %s' % (prof['id'], ', '.join('%s (%d ch)' % (m['name'], Lg.footprint(m))
                                                                     for m in prof['modes'])))
        else:
            rows = Lg.parse_pixel_csv(text, int(c.par.Pixperuniv.eval()), int(c.par.Univ.eval()),
                                      int(c.par.Addr.eval()), len(c.par.Colororder.eval()),
                                      bool(c.par.Spanuniv.eval()))
            pix_dat.clear()
            pix_dat.appendRow(Lg.PIXEL_COLS)
            pix_dat.appendRows([[str(x) for x in r] for r in rows])
            report('pixels from csv: %d' % len(rows))
    elif n == 'Tapbpm':
        S['taps'], bpm = Lg.tap_bpm(S['taps'], absTime.seconds)
        if bpm is not None:
            c.par.Bpm = round(bpm, 2)
    elif n == 'Resetdefaults':
        for p in c.customPars:
            if p.page.name in ('Zkit',) or p.readOnly or p.isPulse or p.isMomentary:
                continue
            try:
                p.val = p.default
            except Exception:
                pass
    return


def sync_blur():
    """pixblur is bypassed while Pixelblur <= 0 (intended: no blur, no cook). The bypass flag has no par to bind, so
    on_value sets it, and status() re-syncs it: a Parameter Execute DAT does not fire while the COMP is parked
    (perf pass 26 Oct), so a change made then would leave the flag stale."""
    c = C()
    b = c.op('pixblur')
    want = c.par.Pixelblur.eval() <= 0
    if b is not None and b.bypass != want:
        b.bypass = want


def on_value(par):
    if par.name == 'Pixelblur':              # Blur TOP bypass is an op flag (no par to bind)
        sync_blur()
    if par.name in PLAN_PARS:
        replan(write=True)
