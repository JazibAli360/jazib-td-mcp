# dmx_patch_logic - pure logic for BK_dmx_patch (fixture patch sheet + stage plot + previs + aim helper for
# BK_dmx_out). No `td` import: offline-testable. numpy + stdlib only. ASCII only.
# Spec: docs/research/BK_dmx_artnet_sacn.md sections 2.8, 3.4-3.6, 7 ("Previz of fixtures") - clean-room, our own code.
# Tests: python3 -I -m unittest discover -s test -p 'test_dmx_patch.py'
# The DMX maths (plan, profiles, aim) live in dmx_logic (BK_dmx_out); every function here that needs them takes that
# module as `D`, so the COMP can carry its own copy and the tests can load the file.
#
# Conventions (same as dmx_logic): metres, degrees, y up, audience toward +z, upstage toward -z. A fixture's own frame:
# mount axis +y, pan 0 toward -z; rot (rx, ry, rz) applied x first, then y, then z (TD rotate order xyz).
# Hanging fixture = rx 180. A fixture without pan/tilt shines along its mount axis.
import fnmatch
import math
import re

import numpy as np

SLOTS = 512
STAGE_COLS = ['name', 'x', 'y', 'z', 'rx', 'ry', 'rz', 'group', 'pan_zero', 'tilt_off', 'pan_dir', 'tilt_dir']
SHEET_COLS = ['name', 'profile', 'mode', 'chans', 'univ', 'wire', 'net', 'subnet', 'universe', 'addr', 'end', 'dmx',
              'node', 'group', 'x', 'y', 'z']
LAYOUTS = ['line', 'arc', 'grid', 'ring']
VIEWS = ['front', 'top', 'side', 'persp']
MAPMODES = ['ownervalue', 'owner', 'value']
COLOUR_ATTRS = ('red', 'green', 'blue', 'white', 'amber', 'uv', 'cyan', 'magenta', 'yellow', 'lime', 'warmwhite',
                'coldwhite')
# additive light colour of each emitter (r, g, b); cyan/magenta/yellow are subtractive filters (handled apart)
EMIT_RGB = {'red': (1, 0, 0), 'green': (0, 1, 0), 'blue': (0, 0, 1), 'white': (1, 1, 1), 'amber': (1, 0.75, 0),
            'uv': (0.35, 0.0, 1.0), 'lime': (0.75, 1, 0), 'warmwhite': (1, 0.85, 0.65), 'coldwhite': (0.85, 0.92, 1)}
DIMMER_ONLY_RGB = (1.0, 0.9, 0.75)      # a dimmer-only fixture shows as warm white
CONFLICT = -1                           # owner grid: a slot claimed twice


# ---------------------------------------------------------------- small helpers
def _f(v, d=0.0):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return d
    return x if math.isfinite(x) else d


def default_group(name):
    """'par12' -> 'par', 'mh_L3' -> 'mh_L'; a name without trailing digits is its own group."""
    g = re.sub(r'\d+$', '', str(name))
    return g or str(name)


def rows_to_dicts(rows, cols):
    """Table rows (first row = header) -> list of dicts; missing cells blank."""
    if not rows:
        return []
    head = [str(h).strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        d = {c: '' for c in cols}
        for k, h in enumerate(head):
            if k < len(r):
                d[h] = str(r[k]).strip()
        out.append(d)
    return out


def dicts_to_rows(dicts, cols):
    return [list(cols)] + [[_cell(d.get(c, '')) for c in cols] for d in dicts]


def _cell(v):
    if isinstance(v, float):
        s = ('%.6f' % v).rstrip('0').rstrip('.')
        return '0' if s in ('-0', '') else s
    return str(v)


# ---------------------------------------------------------------- rotations
def rot_matrix(rx, ry, rz):
    """Same as dmx_logic._rot: R = Rz @ Ry @ Rx (x applied first)."""
    a, b, c = math.radians(rx), math.radians(ry), math.radians(rz)
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    Rx = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]])
    Ry = np.array([[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]])
    Rz = np.array([[cc, -sc, 0], [sc, cc, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def rot_matrices(rot):
    """(N,3) degrees -> (N,3,3), vectorised rot_matrix."""
    r = np.radians(np.asarray(rot, dtype=np.float64).reshape(-1, 3))
    ca, sa = np.cos(r[:, 0]), np.sin(r[:, 0])
    cb, sb = np.cos(r[:, 1]), np.sin(r[:, 1])
    cc, sc = np.cos(r[:, 2]), np.sin(r[:, 2])
    n = len(r)
    o, z = np.ones(n), np.zeros(n)
    Rx = np.stack([np.stack([o, z, z], -1), np.stack([z, ca, -sa], -1), np.stack([z, sa, ca], -1)], 1)
    Ry = np.stack([np.stack([cb, z, sb], -1), np.stack([z, o, z], -1), np.stack([-sb, z, cb], -1)], 1)
    Rz = np.stack([np.stack([cc, -sc, z], -1), np.stack([sc, cc, z], -1), np.stack([z, z, o], -1)], 1)
    return Rz @ Ry @ Rx


def dirs_to_euler(d):
    """(N,3) directions -> (N,2) (rx, ry) degrees with Ry(ry) @ Rx(rx) @ (0,1,0) = d (rz = 0, rotate order xyz).
    Used to turn a +y beam cone (instanced) onto the beam direction."""
    d = np.asarray(d, dtype=np.float64).reshape(-1, 3)
    n = np.linalg.norm(d, axis=1, keepdims=True)
    n[n == 0] = 1.0
    d = d / n
    rx = np.degrees(np.arccos(np.clip(d[:, 1], -1.0, 1.0)))
    ry = np.degrees(np.arctan2(d[:, 0], d[:, 2]))
    return np.stack([rx, ry], 1)


def beam_dirs_local(pan_deg, theta_deg):
    """Vectorised dmx_logic.beam_dir: (N,) pan, theta -> (N,3) in the fixture frame."""
    p, t = np.radians(pan_deg), np.radians(theta_deg)
    return np.stack([np.sin(t) * np.sin(p), np.cos(t), -np.sin(t) * np.cos(p)], 1)


# ---------------------------------------------------------------- stage plot (positions)
def arrange(names, layout='line', span=12.0, height=6.0, depth=0.0, curve=60.0, cols=8, rowgap=1.0, hang=True):
    """Default positions for fixtures -> {name: (x, y, z, rx, ry, rz)}.
    line: evenly across `span` (centred on x 0) at (height, depth). arc: on an arc of `curve` degrees whose chord is
    `span`, bulging toward the audience (+z); ry follows the arc angle. grid: `cols` per row (same spacing on every
    row), rows `rowgap` apart going down from height. ring: circle of diameter `span` in the xz plane at height,
    centre (0, depth); ry follows the ring angle. hang: rx 180 (mount axis down)."""
    names = list(names)
    n = len(names)
    rx = 180.0 if hang else 0.0
    out = {}
    if n == 0:
        return out
    span = float(span)
    if layout == 'line':
        for i, nm in enumerate(names):
            x = 0.0 if n == 1 else -span / 2 + span * i / (n - 1)
            out[nm] = (x, height, depth, rx, 0.0, 0.0)
    elif layout == 'arc':
        a = math.radians(max(1e-3, min(float(curve), 359.0)))
        r = (span / 2) / math.sin(a / 2)
        cz = depth - r * math.cos(a / 2)              # centre behind the line so the arc bulges toward +z
        for i, nm in enumerate(names):
            f = 0.5 if n == 1 else i / (n - 1)
            th = -a / 2 + a * f
            x, z = r * math.sin(th), cz + r * math.cos(th)
            out[nm] = (x, height, z, rx, -math.degrees(th) if hang else math.degrees(th), 0.0)
    elif layout == 'grid':
        c = max(1, min(int(cols), n))
        for i, nm in enumerate(names):
            row, col = divmod(i, c)
            x = 0.0 if c == 1 else -span / 2 + span * col / (c - 1)     # same column spacing on every row
            out[nm] = (x, height - row * float(rowgap), depth, rx, 0.0, 0.0)
    elif layout == 'ring':
        r = span / 2
        for i, nm in enumerate(names):
            th = 2 * math.pi * i / n
            x, z = r * math.sin(th), depth - r * math.cos(th)
            out[nm] = (x, height, z, rx, -math.degrees(th), 0.0)
    else:
        raise ValueError('layout ' + str(layout))
    return out


def stage_row(name, pos, group=None):
    x, y, z, rx, ry, rz = pos
    return {'name': name, 'x': float(x), 'y': float(y), 'z': float(z), 'rx': float(rx), 'ry': float(ry),
            'rz': float(rz), 'group': group or default_group(name), 'pan_zero': 0.5, 'tilt_off': 0.0, 'pan_dir': 1,
            'tilt_dir': 1}


def sync_stage(stage, fixture_names, prune=False, **arr):
    """Keep the stage plot in step with the patch. stage: list of dicts (STAGE_COLS). Rows of fixtures still patched
    keep their positions and calibration; new fixtures are arranged (`arr` = arrange() kwargs) and appended; rows of
    fixtures no longer patched stay (reported as stale) unless prune. -> (rows, added names, stale names)."""
    have = {r['name']: r for r in stage}
    names = list(fixture_names)
    new = [n for n in names if n not in have]
    stale = [r['name'] for r in stage if r['name'] not in set(names)]
    rows = [r for r in stage if not (prune and r['name'] in stale)]
    if new:
        pos = arrange(new, **arr)
        if arr.get('layout', 'line') == 'line' and len(new) != len(names) and stage:
            # append to an existing line: continue to the right of the last patched x at the same spacing
            xs = [_f(r.get('x')) for r in stage if r['name'] in set(names)]
            step = (float(arr.get('span', 12.0)) / max(1, len(names) - 1))
            x0 = (max(xs) + step) if xs else 0.0
            for i, nm in enumerate(new):
                x, y, z, rx, ry, rz = pos[nm]
                pos[nm] = (x0 + i * step, y, z, rx, ry, rz)
        rows += [stage_row(n, pos[n]) for n in new]
    order = {n: i for i, n in enumerate(names)}
    rows.sort(key=lambda r: order.get(r['name'], len(order)))
    return rows, new, (stale if not prune else [])


def apply_arrange(stage, pattern='*', **arr):
    """Re-place the rows whose name matches pattern (fnmatch), in table order; calibration columns kept."""
    pat = (pattern or '*').strip() or '*'
    hit = [r['name'] for r in stage if fnmatch.fnmatch(r['name'], pat)]
    pos = arrange(hit, **arr)
    out = []
    for r in stage:
        if r['name'] in pos:
            r = dict(r)
            r['x'], r['y'], r['z'], r['rx'], r['ry'], r['rz'] = [float(v) for v in pos[r['name']]]
        out.append(r)
    return out, len(hit)


def stage_index(stage):
    """name -> dict of floats (positions, rotation, calibration)."""
    out = {}
    for r in stage:
        out[r['name']] = {'pos': (_f(r.get('x')), _f(r.get('y')), _f(r.get('z'))),
                          'rot': (_f(r.get('rx')), _f(r.get('ry')), _f(r.get('rz'))),
                          'pan_zero': _f(r.get('pan_zero'), 0.5), 'tilt_off': _f(r.get('tilt_off'), 0.0),
                          'pan_dir': -1.0 if _f(r.get('pan_dir'), 1.0) < 0 else 1.0,
                          'tilt_dir': -1.0 if _f(r.get('tilt_dir'), 1.0) < 0 else 1.0,
                          'group': r.get('group') or default_group(r['name'])}
    return out


def stage_issues(fixture_names, stage):
    """Reports only: fixtures without a stage row (drawn at the origin), stale rows, duplicate names."""
    issues = []
    names = list(fixture_names)
    seen = {}
    for r in stage:
        seen[r['name']] = seen.get(r['name'], 0) + 1
    for n, k in seen.items():
        if k > 1:
            issues.append(('duplicate_stage_row', n, str(k)))
    for n in names:
        if n not in seen:
            issues.append(('no_position', n, 'drawn at 0,0,0 - pulse Syncpatch'))
    fs = set(names)
    for n in seen:
        if n not in fs:
            issues.append(('stale_stage_row', n, 'not in the patch - pulse Prune'))
    return issues


# ---------------------------------------------------------------- decode (DMX bytes -> what the fixture does)
def build_decode(D, plan, stage):
    """Static index arrays for decode(): one entry per patched fixture (plan['fixtures'] order). D = dmx_logic."""
    fx = list(plan['fixtures'])
    n = len(fx)
    S = stage_index(stage)
    first = {}
    for i, (o, at) in enumerate(zip(plan['owner'], plan['attrs'])):
        first.setdefault((o, at), i)
    attrs = ('dimmer', 'pan', 'tilt', 'shutter') + COLOUR_ATTRS
    co = {a: np.full(n, -1, dtype=np.int64) for a in attrs}
    fi_ = {a: np.full(n, -1, dtype=np.int64) for a in attrs}
    rng = {a: np.zeros(n) for a in ('pan', 'tilt')}
    for (o, at), i in first.items():
        if at in co:
            co[at][o] = plan['coarse'][i]
            fi_[at][o] = plan['fine'][i]
            if at in rng:
                rng[at][o] = plan['range'][i] or (540.0 if at == 'pan' else 270.0)
    pos = np.zeros((n, 3))
    rot = np.zeros((n, 3))
    cal = np.zeros((n, 4))
    cal[:, 0] = 0.5
    cal[:, 2:] = 1.0
    placed = np.zeros(n, dtype=bool)
    for k, nm in enumerate(fx):
        s = S.get(nm)
        if s is None:
            continue
        placed[k] = True
        pos[k] = s['pos']
        rot[k] = s['rot']
        cal[k] = (s['pan_zero'], s['tilt_off'], s['pan_dir'], s['tilt_dir'])
    has_col = np.zeros(n, dtype=bool)
    for a in COLOUR_ATTRS:
        has_col |= co[a] >= 0
    return {'names': fx, 'n': n, 'coarse': co, 'fine': fi_, 'range': rng, 'pos': pos, 'rot': rot,
            'R': rot_matrices(rot) if n else np.zeros((0, 3, 3)), 'cal': cal, 'placed': placed, 'has_col': has_col,
            'has_pt': (co['pan'] >= 0) & (co['tilt'] >= 0), 'has_dim': co['dimmer'] >= 0,
            'size': plan['nrows'] * SLOTS}


def _val(flat, c, f, default=0.0):
    """Gather 0..1 values: coarse index c (-1 = missing -> default), fine f (-1 = 8 bit)."""
    c = np.asarray(c)
    f = np.asarray(f)
    out = np.full(c.shape, float(default))
    m8 = (c >= 0) & (f < 0)
    m16 = (c >= 0) & (f >= 0)
    if m8.any():
        out[m8] = flat[c[m8]] / 255.0
    if m16.any():
        out[m16] = (np.rint(flat[c[m16]]) * 256.0 + np.rint(flat[f[m16]])) / 65535.0
    return out


def decode(dec, flat):
    """flat = (nrows*512,) slot values 0..255 in plan row order. -> dict: rgb (N,3) 0..1 colour at full, inten (N,)
    0..1, light (N,3) = rgb * inten, pan/theta (N,) degrees, pan01/tilt01, dir (N,3) world beam direction."""
    n = dec['n']
    flat = np.asarray(flat, dtype=np.float64)
    co, fi = dec['coarse'], dec['fine']
    if n == 0:
        z = np.zeros((0, 3))
        return {'rgb': z, 'inten': np.zeros(0), 'light': z, 'pan': np.zeros(0), 'theta': np.zeros(0),
                'pan01': np.zeros(0), 'tilt01': np.zeros(0), 'dir': z}
    rgb = np.zeros((n, 3))
    for a, e in EMIT_RGB.items():
        if (co[a] >= 0).any():
            rgb += _val(flat, co[a], fi[a])[:, None] * np.asarray(e, dtype=np.float64)[None, :]
    cmy = [co[a] >= 0 for a in ('cyan', 'magenta', 'yellow')]
    if any(m.any() for m in cmy):
        has_add = np.zeros(n, dtype=bool)
        for a in EMIT_RGB:
            has_add |= co[a] >= 0
        base = np.where(has_add[:, None], rgb, 1.0)       # CMY filters a white lamp unless emitters exist
        for j, a in enumerate(('cyan', 'magenta', 'yellow')):
            base[:, j] *= 1.0 - _val(flat, co[a], fi[a], 0.0)
        rgb = base
    rgb = np.where(dec['has_col'][:, None], rgb, np.asarray(DIMMER_ONLY_RGB)[None, :])
    rgb = np.clip(rgb, 0.0, 1.0)
    inten = np.where(dec['has_dim'], _val(flat, co['dimmer'], fi['dimmer'], 1.0), 1.0)
    inten = np.where(dec['has_col'] | dec['has_dim'], inten, 0.0)
    pan01 = _val(flat, co['pan'], fi['pan'], 0.5)
    tilt01 = _val(flat, co['tilt'], fi['tilt'], 0.5)
    cal = dec['cal']
    pr, tr = dec['range']['pan'], dec['range']['tilt']
    pan = np.where(dec['has_pt'], (pan01 - cal[:, 0]) * pr * cal[:, 2], 0.0)
    theta = np.where(dec['has_pt'], ((tilt01 - 0.5) * tr - cal[:, 1]) * cal[:, 3], 0.0)
    local = beam_dirs_local(pan, theta)
    world = np.einsum('nij,nj->ni', dec['R'], local)
    return {'rgb': rgb, 'inten': inten, 'light': rgb * inten[:, None], 'pan': pan, 'theta': theta, 'pan01': pan01,
            'tilt01': tilt01, 'dir': world}


def chan_rows(plan, chan_names, first=0, fmt='u{u}'):
    """Map CHOP channel names to plan rows: channel fmt.format(u=flat + first) carries plan row of `flat`.
    -> list of (channel index, plan row) for the channels that match."""
    want = {}
    for r, u in enumerate(plan['univs']):
        try:
            want[fmt.format(u=u + int(first))] = r
        except (KeyError, IndexError, ValueError):
            return []
    return [(i, want[nm]) for i, nm in enumerate(chan_names) if nm in want]


def assemble(plan, data, pairs, out=None):
    """data (C, S) CHOP samples; pairs from chan_rows. -> flat (nrows*512,) float, missing universes 0."""
    flat = out if out is not None else np.zeros(plan['nrows'] * SLOTS)
    flat[:] = 0.0
    if data is None or not len(pairs):
        return flat
    a = np.asarray(data, dtype=np.float64)
    w = min(SLOTS, a.shape[1] if a.ndim == 2 else 0)
    for ci, r in pairs:
        flat[r * SLOTS:r * SLOTS + w] = a[ci, :w]
    return flat


# ---------------------------------------------------------------- instances for the render
def fixture_instances(dec, st, size=0.25, beamlen=8.0, beamangle=15.0, beamgain=0.5, mingrey=0.12, beams=True,
                      highlight=None):
    """Instance channels. Bodies: tx ty tz s cr cg cb (colour = light, at least mingrey so dark units stay visible;
    highlighted ones white). Beams: tx ty tz rx ry rz sr sl br bg bb (cone along +y from the fixture, sl = length,
    sr = end radius; colour = light * beamgain; a dark fixture gets sl = sr = 0)."""
    n = dec['n']
    pos = dec['pos']
    light = st['light']
    body = np.maximum(light, mingrey)
    if highlight is not None and len(highlight):
        body[np.asarray(highlight, dtype=np.int64)] = 1.0
    lum = light.max(axis=1) if n else np.zeros(0)
    on = (lum > 1e-4) & bool(beams)
    e = dirs_to_euler(st['dir']) if n else np.zeros((0, 2))
    sl = np.where(on, float(beamlen), 0.0)
    sr = np.where(on, float(beamlen) * math.tan(math.radians(max(0.0, float(beamangle)) * 0.5)), 0.0)
    bc = light * float(beamgain)
    return {
        'body': {'tx': pos[:, 0], 'ty': pos[:, 1], 'tz': pos[:, 2], 's': np.full(n, float(size)),
                 'cr': body[:, 0], 'cg': body[:, 1], 'cb': body[:, 2]},
        'beam': {'tx': pos[:, 0], 'ty': pos[:, 1], 'tz': pos[:, 2], 'rx': e[:, 0], 'ry': e[:, 1], 'rz': np.zeros(n),
                 'sr': sr, 'sl': sl, 'br': bc[:, 0], 'bg': bc[:, 1], 'bb': bc[:, 2]},
    }


def pixel_layout(pixels, wall=(0.0, 3.0, -1.0, 8.0, 4.5), pixmax=4096):
    """pixels: dicts (id u v univ addr group). The pixel map lies on a wall plane: centre (x, y, z), size (w, h)
    metres, u -> x, v -> y. Above pixmax, every k-th pixel is shown (stride). -> (sel (M,) int, pos (M,3))."""
    n = len(pixels)
    if n == 0:
        return np.zeros(0, dtype=np.int64), np.zeros((0, 3))
    k = max(1, int(math.ceil(n / float(max(1, int(pixmax))))))
    sel = np.arange(0, n, k, dtype=np.int64)
    x, y, z, w, h = [float(v) for v in wall]
    u = np.array([_f(pixels[i].get('u'), 0.5) for i in sel])
    v = np.array([_f(pixels[i].get('v'), 0.5) for i in sel])
    pos = np.stack([x + (u - 0.5) * w, y + (v - 0.5) * h, np.full(len(sel), z)], 1)
    return sel, pos


def pixel_colours(plan, sel, flat, order='rgb'):
    """Colours (M,3) 0..1 of the selected pixels from the slot values (wire order -> rgb; w adds white)."""
    if not len(sel) or not plan['npix']:
        return np.zeros((len(sel), 3))
    sel = np.asarray(sel)[np.asarray(sel) < plan['npix']]
    idx = plan['pix_idx'][sel]                            # (M, k)
    v = np.asarray(flat, dtype=np.float64)[idx] / 255.0
    rgb = np.zeros((len(sel), 3))
    for j, letter in enumerate(order):
        if letter == 'w':
            rgb += v[:, j:j + 1]
        else:
            rgb[:, 'rgb'.index(letter)] += v[:, j]
    return np.clip(rgb, 0.0, 1.0)


# ---------------------------------------------------------------- aim helper (feeds BK_dmx_out in2)
def aim_all(D, dec, target, pattern='*', prev=None):
    """Aim every pan/tilt fixture whose name matches pattern at target (world). -> (names, values, prev, missed)
    channel names '<fixture>.pan' / '<fixture>.tilt', values 0..1 (BK_dmx_out in2 convention), prev = {name: pan deg}
    for hysteresis between frames, missed = fixtures whose target is outside the mechanical range (clamped)."""
    prev = dict(prev or {})
    names, vals, missed = [], [], []
    pat = (pattern or '*').strip() or '*'
    for k, nm in enumerate(dec['names']):
        if not dec['has_pt'][k] or not fnmatch.fnmatch(nm, pat):
            continue
        pz, to, pd, td = dec['cal'][k]
        res = D.aim(tuple(dec['pos'][k]), tuple(target), tuple(dec['rot'][k]), dec['range']['pan'][k],
                    dec['range']['tilt'][k], pz, to, pd, td, prev.get(nm))
        prev[nm] = res['pan']
        names += [nm + '.pan', nm + '.tilt']
        vals += [res['pan01'], res['tilt01']]
        if not res['ok']:
            missed.append(nm)
    return names, vals, prev, missed


def calibrate(D, pos, rot, target, pan01, tilt01, pan_range=540.0, tilt_range=270.0, pan_dir=1, tilt_dir=1,
              pan_zero_hint=0.5):
    """Measured: the fixture hits `target` at DMX (pan01, tilt01). Solve pan_zero and tilt_off so aim() reproduces
    that. Of the equivalent solutions (flip, +-360 pan) the one with pan_zero closest to the hint wins.
    -> (pan_zero, tilt_off)."""
    res = D.aim(tuple(pos), tuple(target), tuple(rot), pan_range, tilt_range, 0.5, 0.0, pan_dir, tilt_dir)
    best = None
    for p0, t0 in ((res['pan'], res['theta']), (res['pan'] + 180.0, -res['theta'])):
        for kk in (-2, -1, 0, 1, 2):
            p = p0 + 360.0 * kk
            pz = float(pan01) - pan_dir * p / float(pan_range)
            to = (float(tilt01) - 0.5) * float(tilt_range) - tilt_dir * t0
            key = (abs(pz - pan_zero_hint), abs(to))
            if best is None or key < best[0]:
                best = (key, pz, to)
    return best[1], best[2]


# ---------------------------------------------------------------- camera
def camera(view, centre=(0.0, 3.0, 0.0), size=16.0, fov=40.0, orbit=30.0, elev=20.0):
    """Camera COMP values for a view. TD cameras look along their -z; rotate order xyz.
    front: from +z; top: from +y (upstage at the top of the image); side: from +x; persp: orbit/elev around centre
    at the distance where `size` metres fill the width. -> dict tx ty tz rx ry rz projection orthowidth fov."""
    cx, cy, cz = [float(v) for v in centre]
    size = max(1e-3, float(size))
    d = size / (2.0 * math.tan(math.radians(max(1.0, float(fov))) * 0.5))
    far = max(50.0, d * 4.0)
    if view == 'front':
        o = dict(tx=cx, ty=cy, tz=cz + far * 0.5, rx=0.0, ry=0.0, rz=0.0, projection='ortho')
    elif view == 'top':
        o = dict(tx=cx, ty=cy + far * 0.5, tz=cz, rx=-90.0, ry=0.0, rz=0.0, projection='ortho')
    elif view == 'side':
        o = dict(tx=cx + far * 0.5, ty=cy, tz=cz, rx=0.0, ry=90.0, rz=0.0, projection='ortho')
    elif view == 'persp':
        az, el = math.radians(float(orbit)), math.radians(float(elev))
        o = dict(tx=cx + d * math.sin(az) * math.cos(el), ty=cy + d * math.sin(el),
                 tz=cz + d * math.cos(az) * math.cos(el), rx=-float(elev), ry=float(orbit), rz=0.0,
                 projection='perspective')
    else:
        raise ValueError('view ' + str(view))
    o.update(orthowidth=size, fov=float(fov), far=far * 2.0)
    return o


def view_axes(view, orbit=30.0, elev=20.0):
    """Screen right / up unit vectors (world) of a view, for fit_view."""
    c = camera(view, (0, 0, 0), 1.0, 40.0, orbit, elev)
    R = rot_matrix(c['rx'], c['ry'], c['rz'])
    return R @ np.array([1.0, 0, 0]), R @ np.array([0, 1.0, 0])


def fit_view(points, view, aspect=1080.0 / 1920.0, margin=1.15, orbit=30.0, elev=20.0):
    """Centre + size (orthowidth, metres across) so all points fit. aspect = width / height of the output."""
    p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    if not len(p):
        return (0.0, 3.0, 0.0), 16.0
    rgt, up = view_axes(view, orbit, elev)
    a, b = p @ rgt, p @ up
    w, h = float(a.max() - a.min()), float(b.max() - b.min())
    lo, hi = p.min(0), p.max(0)
    centre = tuple(float(v) for v in (lo + hi) / 2)
    size = max(w, h * float(aspect), 1.0) * float(margin)
    return centre, size


# ---------------------------------------------------------------- address map (owner grid)
def owner_grid(D, plan, patch, profiles, pixels, rows=None):
    """Per slot owner, rows in `rows` order (flat patch universes; default plan['send_univs'] = BK_dmx_out out3 order).
    Value: 0 free, fixture index + 1 (plan['fixtures'] order), pixel groups after the fixtures (nfix + 1 + group
    index), CONFLICT (-1) where two owners claim a slot. -> (grid (R,512) int32, labels list, conflicts count)."""
    rows = list(plan['send_univs'] if rows is None else rows)
    rix = {u: i for i, u in enumerate(rows)}
    grid = np.zeros((len(rows), SLOTS), dtype=np.int32)
    labels = list(plan['fixtures'])
    items = []
    for k, f in enumerate(D.expand_patch(patch, profiles)):
        items.append((k + 1, D.abs_slot(f['univ'], f['addr']), f['size']))
    groups = []
    k4 = len(plan.get('order', 'rgb'))
    for p in pixels:
        g = p.get('group', '') or 'px'
        if g not in groups:
            groups.append(g)
        a = D.abs_slot(int(_f(p.get('univ'))), max(1, int(_f(p.get('addr'), 1))))
        items.append((len(labels) + 1 + groups.index(g), a, k4))
    labels += ['pixels:' + g for g in groups]
    conflicts = 0
    for owner, a, size in items:
        for s in range(a, a + size):
            u, sl = divmod(s, SLOTS)
            r = rix.get(u)
            if r is None:
                continue
            cur = grid[r, sl]
            if cur == 0:
                grid[r, sl] = owner
            elif cur != owner:
                if cur != CONFLICT:
                    conflicts += 1
                grid[r, sl] = CONFLICT
    return grid, labels, conflicts


def highlight_index(names, pattern):
    """Fixture indices whose names match pattern (blank -> none)."""
    pat = (pattern or '').strip()
    if not pat:
        return []
    return [i for i, n in enumerate(names) if fnmatch.fnmatch(n, pat)]


# ---------------------------------------------------------------- patch sheet
def patch_sheet(D, patch, profiles, stage, first=0):
    """One row per fixture (count expanded) in address order: SHEET_COLS. univ = flat patch universe, wire = on the
    wire (univ + Firstuniv), net/subnet/universe of the wire number, addr..end 1-based, dmx = 'wire.addr'."""
    S = stage_index(stage)
    out = []
    for f in D.expand_patch(patch, profiles):
        w = f['univ'] + int(first)
        net, sub, uni = D.port_address(w)
        s = S.get(f['name'])
        x, y, z = s['pos'] if s else ('', '', '')
        out.append({'name': f['name'], 'profile': f['profile']['id'], 'mode': f['mode']['name'], 'chans': f['size'],
                    'univ': f['univ'], 'wire': w, 'net': net, 'subnet': sub, 'universe': uni, 'addr': f['addr'],
                    'end': f['addr'] + f['size'] - 1, 'dmx': '%d.%03d' % (w, f['addr']), 'node': f.get('node', ''),
                    'group': s['group'] if s else default_group(f['name']), 'x': x, 'y': y, 'z': z})
    out.sort(key=lambda r: (r['univ'], r['addr'], r['name']))
    return out


def sheet_csv(rows):
    def q(v):
        s = _cell(v)
        return '"%s"' % s.replace('"', '""') if (',' in s or '"' in s) else s
    lines = [','.join(SHEET_COLS)] + [','.join(q(r.get(c, '')) for c in SHEET_COLS) for r in rows]
    return '\n'.join(lines) + '\n'


def sheet_md(rows, issues=(), title='DMX patch', protocol='artnet', pixels=0):
    """Printable patch sheet (Markdown): summary, per-universe table, issues."""
    unis = sorted({r['wire'] for r in rows})
    used = {}
    for r in rows:
        used[r['wire']] = used.get(r['wire'], 0) + int(r['chans'])
    out = ['# %s' % title, '',
           '%d fixtures, %d universes (%s), %d pixels in the pixel map.' % (len(rows), len(unis), protocol, pixels), '']
    for u in unis:
        rr = [r for r in rows if r['wire'] == u]
        net, sub, uni = rr[0]['net'], rr[0]['subnet'], rr[0]['universe']
        out += ['## Universe %d (net %d, subnet %d, universe %d) - %d / 512 slots' % (u, net, sub, uni, used[u]), '',
                '| Fixture | Profile | Mode | Address | Ch | Group | Position (m) |', '|---|---|---|---|---|---|---|']
        for r in rr:
            p = '' if r['x'] == '' else '%s, %s, %s' % (_cell(r['x']), _cell(r['y']), _cell(r['z']))
            out.append('| %s | %s | %s | %d-%d | %d | %s | %s |' % (r['name'], r['profile'], r['mode'], r['addr'],
                                                                     r['end'], r['chans'], r['group'], p))
        out.append('')
    out += ['## Issues', '']
    out += ['- %s: %s (%s)' % tuple(i) for i in issues] if issues else ['- none']
    return '\n'.join(out) + '\n'


def issue_text(issues):
    if not issues:
        return 'patch + stage ok'
    return '\n'.join('{}\t{}\t{}'.format(*i) for i in issues)
