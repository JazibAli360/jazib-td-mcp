# show_rig_logic - pure logic for /project1/show_rig (master show rig). No TD imports; tested offline in
# test/test_show_rig.py and copied into the rig's `rig_logic` Text DAT by builders/show_rig.py. ASCII only.
#
# The rig = td_layer_mixer (N layers over a bank of look COMPs) + master FX inserts by reference (lab FX COMPs) +
# look presets + CQ_cuelist / MIDI_mapper / BP_io_router hooks. This module decides:
#   - effective layer opacity (opacity x mute x solo), which sources are shown
#   - the cook plan: which COMPs to wake / park (only what the rig woke, never a lane's COMP, never the roots)
#   - preset rows <-> layer state (sources stored by NAME so a changed bank keeps presets valid)
#   - preset fades (opacity / master lerp, discrete values switched at the start)
#   - demo cue rows and MIDI bind rows

FX_ORDER = ('palette', 'trail', 'strobe')          # palette first, trail second, strobe last (flashes not trailed)
FX_DEFAULT = {'palette': '/project1/lab/FX_palette_map', 'trail': '/project1/lab/FX_motion_trail',
              'strobe': '/project1/lab/FX_strobe'}
FX_PAR = {'palette': 'Fxpalette', 'trail': 'Fxtrail', 'strobe': 'Fxstrobe'}
# what the FX COMP's own source par is set to while its insert is on (None = its 'auto' sees the wire)
FX_SOURCE = {'palette': ('Source', 'input'), 'trail': ('Source', 'input'), 'strobe': ('Input', 'live')}
GUARD_MODES = ('owned', 'strict', 'off')
LAYER_FIELDS = ('source', 'opacity', 'blend', 'mute', 'solo')
CURVES = ('linear', 'ease', 'smooth', 'cut')


def _b(v):
    if isinstance(v, str):
        return v.strip().lower() in ('1', 'true', 'on', 'yes')
    return bool(v)


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def effective(layers):
    """layers = [{'opacity', 'mute', 'solo'}...] -> [effective opacity]. Any solo hides every non-solo layer."""
    solo_any = any(_b(l.get('solo')) for l in layers)
    out = []
    for l in layers:
        if _b(l.get('mute')) or (solo_any and not _b(l.get('solo'))):
            out.append(0.0)
        else:
            out.append(max(0.0, min(1.0, _f(l.get('opacity')))))
    return out


def shown_sources(layers, master=1.0):
    """Source indices a visible layer shows (eff > 0 and master > 0). layers carry 'source' = int index."""
    if _f(master) <= 0:
        return []
    eff = effective(layers)
    return sorted(set(int(l['source']) for l, e in zip(layers, eff) if e > 0 and int(l.get('source', -1)) >= 0))


def fx_live(masterfx, enabled):
    """enabled = {fx: bool} -> fx names whose insert is in the chain (in FX_ORDER)."""
    if not _b(masterfx):
        return []
    return [k for k in FX_ORDER if _b(enabled.get(k))]


def cook_plan(candidates, wanted, owned, protected=(), mode='owned'):
    """candidates = {path: cooking_now (bool)} (COMP sources + FX COMPs the rig may drive);
    wanted = paths that must cook (shown sources, live FX inserts); owned = paths the rig woke before.
    Returns (wake, park, owned_after).
    owned  : wake what is wanted and parked; park only what the rig woke and is no longer wanted.
    strict : also park every other unwanted candidate (one live source per layer, research AU).
    off    : touch nothing (owned list kept so switching back can tidy).
    Never parks a protected path (a live lane's COMP) or a top-level path (/project1...)."""
    wanted = set(wanted)
    owned = set(owned)
    prot = set(protected)
    wake, park = [], []
    if mode == 'off':
        return wake, park, sorted(owned & set(candidates))
    for p in sorted(candidates):
        on = bool(candidates[p])
        if p in wanted:
            if not on:
                wake.append(p)
                owned.add(p)
            continue
        if p in prot or p.rstrip('/').count('/') <= 1:
            owned.discard(p)
            continue
        if on and (p in owned or mode == 'strict'):
            park.append(p)
        owned.discard(p)
    return wake, park, sorted(owned)


# ------------------------------------------------------------------ presets
def preset_header(n_layers):
    h = ['name']
    for n in range(1, n_layers + 1):
        h += ['L%d%s' % (n, f) for f in LAYER_FIELDS]
    return h + ['Master', 'Masterfx'] + [FX_PAR[k] for k in FX_ORDER]


def state_to_row(name, state, labels):
    """state = {'layers': [{source:int, opacity, blend, mute, solo}], 'Master', 'Masterfx', 'fx': {k: bool}};
    labels = source index -> label. Sources are stored by label."""
    row = [name]
    for l in state['layers']:
        k = int(l['source'])
        row += [labels[k] if 0 <= k < len(labels) else '', '%g' % _f(l['opacity']), str(l['blend']),
                '1' if _b(l['mute']) else '0', '1' if _b(l['solo']) else '0']
    row += ['%g' % _f(state.get('Master', 1.0)), '1' if _b(state.get('Masterfx')) else '0']
    row += ['1' if _b(state.get('fx', {}).get(k)) else '0' for k in FX_ORDER]
    return row


def row_to_state(header, row, labels, n_layers):
    """-> (state, errors). Missing columns keep None (= leave that value as it is). Unknown source label = error
    and that layer's source is left as it is."""
    d = dict(zip(header, list(row) + [''] * (len(header) - len(row))))
    errs = []
    layers = []
    for n in range(1, n_layers + 1):
        l = {}
        src = d.get('L%dsource' % n, '')
        if src != '':
            if src in labels:
                l['source'] = labels.index(src)
            elif src.isdigit() and int(src) < len(labels):
                l['source'] = int(src)
            else:
                errs.append('L%d source %r not in the bank' % (n, src))
        for f, conv in (('opacity', _f), ('blend', str), ('mute', _b), ('solo', _b)):
            v = d.get('L%d%s' % (n, f), '')
            if v != '':
                l[f] = conv(v)
        layers.append(l)
    st = {'layers': layers, 'fx': {}}
    if d.get('Master', '') != '':
        st['Master'] = _f(d['Master'], 1.0)
    if d.get('Masterfx', '') != '':
        st['Masterfx'] = _b(d['Masterfx'])
    for k in FX_ORDER:
        if d.get(FX_PAR[k], '') != '':
            st['fx'][k] = _b(d[FX_PAR[k]])
    return st, errs


def curve(u, name='linear'):
    u = 0.0 if u < 0 else 1.0 if u > 1 else u
    if name == 'cut':
        return 1.0 if u > 0 else 0.0
    if name == 'ease':
        return u * u * (3 - 2 * u)
    if name == 'smooth':
        return u * u * u * (u * (6 * u - 15) + 10)
    return u


def fade_plan(cur, target, n_layers):
    """cur / target = states. -> (discrete {parname: value} set at the start, faded {parname: (a, b)}).
    A layer whose source changes while it is visible cuts its source at the start (documented)."""
    disc, fade = {}, {}
    for n in range(1, n_layers + 1):
        c = cur['layers'][n - 1]
        t = target['layers'][n - 1] if n - 1 < len(target['layers']) else {}
        for f in ('source', 'blend', 'mute', 'solo'):
            if f in t and t[f] != c.get(f):
                disc['L%d%s' % (n, f)] = t[f]
        if 'opacity' in t and abs(_f(t['opacity']) - _f(c.get('opacity'))) > 1e-9:
            fade['L%dopacity' % n] = (_f(c.get('opacity')), _f(t['opacity']))
    if 'Master' in target and abs(_f(target['Master']) - _f(cur.get('Master', 1.0))) > 1e-9:
        fade['Master'] = (_f(cur.get('Master', 1.0)), _f(target['Master']))
    if 'Masterfx' in target and _b(target['Masterfx']) != _b(cur.get('Masterfx')):
        disc['Masterfx'] = _b(target['Masterfx'])
    for k, v in target.get('fx', {}).items():
        if _b(v) != _b(cur.get('fx', {}).get(k)):
            disc[FX_PAR[k]] = _b(v)
    return disc, fade


def fade_values(fade, t, dur, cv='linear'):
    """Values of a fade_plan's faded pars at t seconds into a dur-second fade. dur <= 0 = the targets."""
    u = 1.0 if dur <= 0 else curve(t / dur, cv)
    return dict((k, a + (b - a) * u) for k, (a, b) in fade.items())


def default_presets(labels, n_layers):
    """A few starting looks over the lab bank (only those whose sources exist)."""
    def L(name):
        return name if name in labels else ''
    rows = []
    blank = [{'source': 0, 'opacity': 0.0, 'blend': 'over', 'mute': False, 'solo': False} for _ in range(n_layers)]

    def mk(name, spec, master=1.0, fx=None):
        lay = [dict(x) for x in blank]
        for i, (src, opv, bl) in enumerate(spec):
            if not L(src):
                return None
            lay[i] = {'source': labels.index(src), 'opacity': opv, 'blend': bl, 'mute': False, 'solo': False}
        return state_to_row(name, {'layers': lay, 'Master': master, 'Masterfx': bool(fx), 'fx': fx or {}}, labels)
    for r in (mk('blackout', [], 0.0),
              mk('test', [('TP_test_pattern', 1.0, 'over')]),
              mk('glass', [('LK_spectrum_glass', 1.0, 'over')]),
              mk('glass_particles', [('LK_spectrum_glass', 1.0, 'over'), ('BO_particles', 0.8, 'add')]),
              mk('fluid_cloud', [('BN_fluid2d', 1.0, 'over'), ('BL_cloud_morph', 0.7, 'screen')]),
              mk('room_palette', [('LK_projection_room', 1.0, 'over')], 1.0, {'palette': True})):
        if r is not None:
            rows.append(r)
    return rows


def demo_cues(labels, rig='/project1/show_rig'):
    """CQ_cuelist rows (its COLUMNS) driving the rig: sources by bank index (resolved here by name), opacities
    faded by CQ, a preset recall (Preset = row number), a blackout. Missing sources -> those rows are skipped."""
    def ix(name):
        return labels.index(name) if name in labels else None
    rows = [['id', 'num', 'name', 'trigger', 'at', 'pre', 'fade', 'curve', 'kind', 'target', 'value', 'follow',
             'delay', 'note', 'enabled', 'color']]
    k = [0]

    def add(num, name, fade, cv, target, value, note=''):
        k[0] += 1
        rows.append([str(k[0]), str(num), name, 'manual', '', '', '%g' % fade, cv, 'par', rig + ':' + target,
                     str(value), '', '', note, '1', ''])
    tp, gl, pa = ix('TP_test_pattern'), ix('LK_spectrum_glass'), ix('BO_particles')
    if tp is not None:
        add(1, 'Test card', 0, 'cut', 'L1source', tp, 'layer 1 = test pattern')
        add(1, 'Test card', 0, 'cut', 'L1opacity', 1)
        add(1, 'Test card', 0, 'cut', 'L2opacity', 0)
        add(1, 'Test card', 0, 'cut', 'Master', 1)
    if gl is not None:
        add(2, 'Glass in', 0, 'cut', 'L2source', gl, 'layer 2 = spectrum glass')
        add(2, 'Glass in', 2, 'linear', 'L2opacity', 1, '2 s crossfade')
        add(2, 'Glass in', 2, 'linear', 'L1opacity', 0)
    if pa is not None:
        add(3, 'Particles add', 0, 'cut', 'L3source', pa)
        add(3, 'Particles add', 1.5, 'ease', 'L3opacity', 0.8)
    add(4, 'Preset glass_particles', 0, 'cut', 'Preset', 4, 'recall preset row 4 (Presetfade)')
    add(5, 'Blackout', 1, 'linear', 'Master', 0)
    return rows


def midi_binds(n_layers, rig='/project1/show_rig', bank=1, channel=1, cc0=1, note0=36):
    """Default bindable controls for MIDI_mapper (midi_core FIELDS): layer opacity faders CC cc0.., Master CC
    cc0+n, layer mutes as toggles on notes note0.., solos note0+8.., Masterfx note0+16, preset step note0+17."""
    out = []
    for n in range(1, n_layers + 1):
        out.append({'id': 'sr_l%d_op' % n, 'label': 'Rig L%d opacity' % n, 'kind': 'cc', 'number': cc0 + n - 1,
                    'par': 'L%dopacity' % n, 'mode': 'absolute', 'takeover': 'pickup'})
        out.append({'id': 'sr_l%d_mute' % n, 'label': 'Rig L%d mute' % n, 'kind': 'note', 'number': note0 + n - 1,
                    'par': 'L%dmute' % n, 'mode': 'toggle'})
        out.append({'id': 'sr_l%d_solo' % n, 'label': 'Rig L%d solo' % n, 'kind': 'note',
                    'number': note0 + 8 + n - 1, 'par': 'L%dsolo' % n, 'mode': 'toggle'})
    out.append({'id': 'sr_master', 'label': 'Rig master', 'kind': 'cc', 'number': cc0 + n_layers, 'par': 'Master',
                'mode': 'absolute', 'takeover': 'pickup'})
    out.append({'id': 'sr_masterfx', 'label': 'Rig master FX', 'kind': 'note', 'number': note0 + 16,
                'par': 'Masterfx', 'mode': 'toggle'})
    out.append({'id': 'sr_recall', 'label': 'Rig recall preset', 'kind': 'note', 'number': note0 + 17,
                'par': 'Recall', 'mode': 'trigger'})
    for m in out:
        m.update({'target': rig, 'bank': int(bank), 'channel': int(channel)})
    return out
