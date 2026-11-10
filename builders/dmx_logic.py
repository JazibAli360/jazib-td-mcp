# dmx_logic - pure logic for BK_dmx_out (Art-Net / sACN out from TD). No `td` import: offline-testable.
# Spec: docs/research/BK_dmx_artnet_sacn.md section 3 (clean-room, our own code). numpy + stdlib only. ASCII only.
# Tests: python3 -I -m unittest discover -s test -p 'test_dmx.py'
# Units: a universe buffer is (U, 512) uint8, one row per used universe (rows sorted by flat universe index).
# "flat" universe = Art-Net 15-bit Port-Address (net*256 + subnet*16 + universe); for sACN the same number is
# the E1.31 universe (1-based; 0 is reserved).
import fnmatch
import json
import math
import struct

import numpy as np

SLOTS = 512
PROTOCOLS = ['artnet', 'sacn']
TARGETMODES = ['unicast', 'broadcast', 'multicast']
SENDERS = ['tddmx', 'python']
ORDERS = ['rgb', 'rbg', 'grb', 'gbr', 'brg', 'bgr', 'rgbw', 'grbw']
WHITEMODES = ['none', 'extract-min', 'zero-w']
INTERPS = ['nearest', 'bilinear']
BLACKOUTMODES = ['intensity', 'all']
MASTERFROM = ['manual', 'bpm', 'audio', 'bpm-x-audio']
BEATSHAPES = ['pulse', 'saw', 'sine', 'square']
PATTERNS = ['live', 'zero', 'full', 'ramp', 'channelid', 'chase', 'rgbcycle', 'walkpixel', 'fixtureid', 'strobe']
PATTERNMIX = ['replace', 'add', 'max']
MONMODES = ['heat', 'grey', 'nonzero']
QUANTIZE = ['off', 'fixture']
PIXLAYOUTS = ['strip', 'grid', 'ring']
DIM_KINDS = ('intensity', 'colour')          # kinds Master / Blackout(intensity) act on; pixels count as colour
LETTER_ATTR = {'r': 'red', 'g': 'green', 'b': 'blue', 'w': 'white'}
PATCH_COLS = ['name', 'profile', 'mode', 'univ', 'addr', 'count', 'gapslots', 'node', 'kind']
PIXEL_COLS = ['id', 'u', 'v', 'univ', 'addr', 'group']
ROUTING_COLS = ['channel', 'net', 'subnet', 'universe', 'netaddress']   # 31550 DMX Out wants a channel column


# ---------------------------------------------------------------- addressing
def port_address(u):
    """Flat Art-Net Port-Address -> (net, subnet, universe)."""
    u = int(u)
    return (u >> 8) & 0x7F, (u >> 4) & 0xF, u & 0xF


def flat_universe(net, subnet, universe):
    return ((int(net) & 0x7F) << 8) | ((int(subnet) & 0xF) << 4) | (int(universe) & 0xF)


def split16(v01):
    """0..1 -> (coarse, fine) bytes; clamped because a slot is 16 bits."""
    n = int(round(min(max(float(v01), 0.0), 1.0) * 65535))
    return n >> 8, n & 255


def join16(coarse, fine):
    return ((int(coarse) << 8) | int(fine)) / 65535.0


def place(buf, univ0, addr, data):
    """Write data into buf (U,512) at row univ0 (row index), 1-based addr; spills into the next rows."""
    flat = int(univ0) * SLOTS + int(addr) - 1
    view = buf.reshape(-1)
    data = np.asarray(data)
    view[flat:flat + len(data)] = data[:max(0, len(view) - flat)]


def abs_slot(univ, addr):
    return int(univ) * SLOTS + int(addr) - 1


def parse_univfilter(s):
    """'0-3 7 10-12' -> set of flat universes; blank -> None (= all)."""
    s = (s or '').replace(',', ' ').strip()
    if not s:
        return None
    out = set()
    for tok in s.split():
        if '-' in tok[1:]:
            a, b = tok.split('-', 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(tok))
    return out


# ---------------------------------------------------------------- pixels
def layout_pixels(n, per_univ=170, univ0=0, addr0=1, chans=3, span=False):
    """-> list of (univ, addr) per pixel. span=False: a pixel never straddles a universe (max per_univ per universe);
    span=True: continuous slots, a pixel may straddle (then per_univ is ignored)."""
    out = []
    if span:
        a = abs_slot(univ0, addr0)
        for i in range(int(n)):
            s = a + i * chans
            out.append((s // SLOTS, s % SLOTS + 1))
        return out
    per_univ = max(1, min(int(per_univ), SLOTS // chans))
    u, addr, k = int(univ0), int(addr0), 0
    for _ in range(int(n)):
        if k >= per_univ or addr + chans - 1 > SLOTS:
            u, addr, k = u + 1, 1, 0
        out.append((u, addr))
        addr += chans
        k += 1
    return out


def order_chans(order):
    return len(order)


def pixel_slots(rgb01, order='rgb', white='none', gamma=1.0, scale=255.0):
    """(N,3|4) floats 0..1 (rgb[a]) -> (N,len(order)) uint8 in wire order. white: none (w=0 / ignored), extract-min
    (w = min(r,g,b), rgb reduced by w), zero-w (w=0). Gamma on 0..1 before scale; result clamped to bytes."""
    a = np.asarray(rgb01, dtype=np.float64)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    rgb = np.clip(a[:, :3], 0.0, 1.0)
    if len(order) == 4:
        if white == 'extract-min':
            w = rgb.min(axis=1, keepdims=True)
            rgb = rgb - w
        else:
            w = np.zeros((rgb.shape[0], 1))
        cols = {'r': rgb[:, 0:1], 'g': rgb[:, 1:2], 'b': rgb[:, 2:3], 'w': w}
    else:
        cols = {'r': rgb[:, 0:1], 'g': rgb[:, 1:2], 'b': rgb[:, 2:3]}
    m = np.concatenate([cols[ch] for ch in order], axis=1)
    if gamma != 1.0:
        m = np.power(m, float(gamma))
    return np.clip(np.rint(m * float(scale)), 0, 255).astype(np.uint8)


def gen_pixels(layout, w, h=1, serpentine=True, per_univ=170, univ0=0, addr0=1, chans=3, span=False, group='px'):
    """Pixel map rows [id, u, v, univ, addr, group] for a strip (w px, left to right), grid (w x h, rows bottom to top,
    serpentine flips every other row) or ring (w px, counter-clockwise from the right, radius 0.45)."""
    pts = []
    if layout == 'strip':
        for i in range(int(w)):
            pts.append(((i + 0.5) / w, 0.5))
    elif layout == 'grid':
        for y in range(int(h)):
            xs = range(int(w))
            if serpentine and y % 2 == 1:
                xs = reversed(list(xs))
            for x in xs:
                pts.append(((x + 0.5) / w, (y + 0.5) / h))
    elif layout == 'ring':
        for i in range(int(w)):
            a = 2 * math.pi * i / w
            pts.append((0.5 + 0.45 * math.cos(a), 0.5 + 0.45 * math.sin(a)))
    else:
        raise ValueError('layout ' + str(layout))
    addrs = layout_pixels(len(pts), per_univ, univ0, addr0, chans, span)
    return [[i, round(u, 6), round(v, 6), ua[0], ua[1], group] for i, ((u, v), ua) in enumerate(zip(pts, addrs))]


def parse_pixel_csv(text, per_univ=170, univ0=0, addr0=1, chans=3, span=False, group='csv'):
    """CSV with a header: x,y[,z][,univ,addr]. x,y are normalised to 0..1 over their bounds (z ignored for sampling).
    Without univ/addr the pixels are laid out in file order."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith('#')]
    head = [h.strip().lower() for h in lines[0].split(',')]
    rows = [[c.strip() for c in ln.split(',')] for ln in lines[1:]]
    ix, iy = head.index('x'), head.index('y')
    xs = [float(r[ix]) for r in rows]
    ys = [float(r[iy]) for r in rows]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sx = (x1 - x0) or 1.0
    sy = (y1 - y0) or 1.0
    if 'univ' in head and 'addr' in head:
        iu, ia = head.index('univ'), head.index('addr')
        addrs = [(int(r[iu]), int(r[ia])) for r in rows]
    else:
        addrs = layout_pixels(len(rows), per_univ, univ0, addr0, chans, span)
    return [[i, round((x - x0) / sx, 6), round((y - y0) / sy, 6), a[0], a[1], group]
            for i, (x, y, a) in enumerate(zip(xs, ys, addrs))]


# ---------------------------------------------------------------- moving heads
def _rot(rot_deg):
    rx, ry, rz = [math.radians(float(a)) for a in rot_deg]
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx                       # x first, then y, then z (TD's default rotate order xyz)


def beam_dir(pan_deg, theta_deg):
    """Forward kinematics in the fixture's own frame: up = +y (mount axis), pan 0 = toward -z, pan about +y,
    theta = polar angle from up. -> unit vector."""
    p, t = math.radians(pan_deg), math.radians(theta_deg)
    return np.array([math.sin(t) * math.sin(p), math.cos(t), -math.sin(t) * math.cos(p)])


def aim(pos, target, rot_deg=(0, 0, 0), pan_range=540.0, tilt_range=270.0, pan_zero=0.5, tilt_off=0.0,
        pan_dir=1, tilt_dir=1, prev_pan=None):
    """Pan/tilt for a fixture at pos (world), rotated by rot_deg (hanging = roll 180), to hit target.
    DMX: pan01 = pan_zero + pan_dir * pan / pan_range; tilt01 = 0.5 + (tilt_dir * theta + tilt_off) / tilt_range
    (tilt 0.5 = beam along the mount axis). Candidates (pan, theta), (pan + 180, -theta) and +-360 pan turns; the one
    inside the mechanical range closest to prev_pan (or to pan centre) wins. -> dict pan, theta, pan01, tilt01, ok."""
    R = _rot(rot_deg)
    d = np.asarray(target, dtype=float) - np.asarray(pos, dtype=float)
    lv = R.T @ d
    horiz = math.hypot(lv[0], lv[2])
    theta = math.degrees(math.atan2(horiz, lv[1]))
    if horiz < 1e-12:
        pan = float(prev_pan) if prev_pan is not None else 0.0
    else:
        pan = math.degrees(math.atan2(lv[0], -lv[2]))
    cands = []
    for p0, t0 in ((pan, theta), (pan + 180.0, -theta)):
        for k in (-2, -1, 0, 1, 2):
            p = p0 + 360.0 * k
            p01 = pan_zero + pan_dir * p / pan_range
            t01 = 0.5 + (tilt_dir * t0 + tilt_off) / tilt_range
            inside = (-1e-9 <= p01 <= 1 + 1e-9) and (-1e-9 <= t01 <= 1 + 1e-9)
            ref = float(prev_pan) if prev_pan is not None else (0.5 - pan_zero) * pan_range * pan_dir
            cands.append((0 if inside else 1, abs(p - ref), abs(t0), p, t0, p01, t01, inside))
    cands.sort(key=lambda c: c[:3])
    _, _, _, p, t0, p01, t01, inside = cands[0]
    return {'pan': p, 'theta': t0, 'pan01': min(max(p01, 0.0), 1.0), 'tilt01': min(max(t01, 0.0), 1.0),
            'ok': bool(inside)}


def aim_world_dir(res, rot_deg=(0, 0, 0)):
    return _rot(rot_deg) @ beam_dir(res['pan'], res['theta'])


# ---------------------------------------------------------------- packets
ARTNET_ID = b'Art-Net\x00'
ACN_ID = b'ASC-E1.17\x00\x00\x00'


def encode_artdmx(seq, univ, data, physical=0):
    """ArtDmx (opcode 0x5000): 18-byte header + data; length even, 2..512 (padded with 0)."""
    data = bytes(bytearray(int(v) & 255 for v in data))[:SLOTS]
    if len(data) % 2:
        data += b'\x00'
    if len(data) < 2:
        data = data + b'\x00' * (2 - len(data))
    u = int(univ)
    return (ARTNET_ID + struct.pack('<H', 0x5000) + bytes([0, 14, int(seq) & 255, int(physical) & 255,
                                                          u & 0xFF, (u >> 8) & 0x7F])
            + struct.pack('>H', len(data)) + data)


def parse_artdmx(pkt):
    if len(pkt) < 18 or pkt[:8] != ARTNET_ID:
        return None
    op_ = struct.unpack('<H', pkt[8:10])[0]
    if op_ != 0x5000:
        return {'opcode': op_}
    n = struct.unpack('>H', pkt[16:18])[0]
    return {'opcode': op_, 'version': (pkt[10] << 8) | pkt[11], 'seq': pkt[12], 'physical': pkt[13],
            'univ': pkt[14] | (pkt[15] << 8), 'length': n, 'data': bytes(pkt[18:18 + n])}


def encode_sacn(seq, univ, data, prio=100, name='BK_dmx_out', cid=b'BK_dmx_out_cid__', sync=0, options=0):
    """E1.31 data packet: root (38 B) + framing (77 B) + DMP (10 B + 1 start code + n slots); 638 B for 512."""
    data = bytes(bytearray(int(v) & 255 for v in data))[:SLOTS]
    n = len(data)
    cid = (bytes(cid) + b'\x00' * 16)[:16]
    nm = (name.encode('ascii', 'replace') + b'\x00' * 64)[:63] + b'\x00'
    dmp = (struct.pack('>H', 0x7000 | (10 + 1 + n)) + bytes([0x02, 0xA1]) + struct.pack('>HHH', 0, 1, 1 + n)
           + b'\x00' + data)
    framing = (struct.pack('>HI', 0x7000 | (77 + len(dmp)), 0x00000002) + nm + bytes([int(prio) & 255])
               + struct.pack('>H', sync) + bytes([int(seq) & 255, options]) + struct.pack('>H', int(univ)))
    root = (struct.pack('>HH', 0x0010, 0) + ACN_ID + struct.pack('>HI', 0x7000 | (22 + len(framing) + len(dmp)), 4)
            + cid)
    return root + framing + dmp


def parse_sacn(pkt):
    if len(pkt) < 126 or pkt[4:16] != ACN_ID:
        return None
    vec = struct.unpack('>I', pkt[18:22])[0]
    if vec != 4:
        return {'vector': vec}
    fvec = struct.unpack('>I', pkt[40:44])[0]
    if fvec != 2:
        return {'vector': vec, 'framing_vector': fvec}
    name = pkt[44:108].split(b'\x00', 1)[0].decode('ascii', 'replace')
    cnt = struct.unpack('>H', pkt[123:125])[0]
    return {'vector': vec, 'cid': bytes(pkt[22:38]), 'name': name, 'priority': pkt[108],
            'sync': struct.unpack('>H', pkt[109:111])[0], 'seq': pkt[111], 'options': pkt[112],
            'univ': struct.unpack('>H', pkt[113:115])[0], 'startcode': pkt[125], 'length': cnt - 1,
            'data': bytes(pkt[126:126 + cnt - 1]), 'size': len(pkt)}


# ---------------------------------------------------------------- profiles (jzfix)
def _ch(off, name, attr, kind, bits=8, default=0.0, fine=None, range_deg=0.0):
    return {'off': off, 'name': name, 'attr': attr, 'bits': bits, 'fine': fine, 'kind': kind,
            'default': default, 'range_deg': range_deg}


def builtin_profiles():
    rgb = [_ch(0, 'Red', 'red', 'colour'), _ch(1, 'Green', 'green', 'colour'), _ch(2, 'Blue', 'blue', 'colour')]
    mh = [_ch(0, 'Pan', 'pan', 'position', 16, 0.5, 1, 540.0), _ch(2, 'Tilt', 'tilt', 'position', 16, 0.5, 3, 270.0),
          _ch(4, 'Speed', 'speed', 'other'), _ch(5, 'Dimmer', 'dimmer', 'intensity', 16, 0.0, 6),
          _ch(7, 'Shutter', 'shutter', 'other', default=1.0), _ch(8, 'Red', 'red', 'colour'),
          _ch(9, 'Green', 'green', 'colour'), _ch(10, 'Blue', 'blue', 'colour'), _ch(11, 'White', 'white', 'colour'),
          _ch(12, 'Zoom', 'zoom', 'other'), _ch(13, 'Focus', 'focus', 'other'), _ch(14, 'Gobo', 'gobo', 'other'),
          _ch(15, 'Control', 'raw', 'other')]
    return [
        {'id': 'generic_dimmer_1ch', 'name': 'Dimmer', 'maker': 'generic', 'source': 'builtin',
         'modes': [{'name': '1ch', 'channels': [_ch(0, 'Dimmer', 'dimmer', 'intensity')]}]},
        {'id': 'generic_rgb_3ch', 'name': 'RGB par', 'maker': 'generic', 'source': 'builtin',
         'modes': [{'name': '3ch', 'channels': rgb}]},
        {'id': 'generic_rgbw_4ch', 'name': 'RGBW par', 'maker': 'generic', 'source': 'builtin',
         'modes': [{'name': '4ch', 'channels': rgb + [_ch(3, 'White', 'white', 'colour')]}]},
        {'id': 'generic_rgbaw_uv_6ch', 'name': 'RGBAW+UV par', 'maker': 'generic', 'source': 'builtin',
         'modes': [{'name': '6ch', 'channels': rgb + [_ch(3, 'Amber', 'amber', 'colour'),
                                                     _ch(4, 'White', 'white', 'colour'), _ch(5, 'UV', 'uv', 'colour')]}]},
        {'id': 'generic_mh_16bit_16ch', 'name': 'Moving head 16 bit', 'maker': 'generic', 'source': 'builtin',
         'pan_range': 540.0, 'tilt_range': 270.0, 'modes': [{'name': '16ch', 'channels': mh}]},
    ]


def profile_index(profiles):
    return {p['id']: p for p in profiles}


def find_mode(profile, mode):
    ms = profile.get('modes') or []
    if not ms:
        return None
    if not mode:
        return ms[0]
    for m in ms:
        if m['name'] == mode:
            return m
    return None


def footprint(mode):
    n = 0
    for c in mode['channels']:
        n = max(n, c['off'] + 1, (c['fine'] + 1) if c.get('fine') is not None else 0)
    return n


_OFL_COLOURS = {'red': 'red', 'green': 'green', 'blue': 'blue', 'white': 'white', 'amber': 'amber', 'uv': 'uv',
                'cyan': 'cyan', 'magenta': 'magenta', 'yellow': 'yellow', 'lime': 'lime', 'indigo': 'indigo',
                'warm white': 'warmwhite', 'cold white': 'coldwhite'}


def _deg(s):
    try:
        return float(str(s).lower().replace('deg', '').strip())
    except ValueError:
        return None


def _ofl_kind(chdef):
    caps = chdef.get('capabilities') or ([chdef['capability']] if chdef.get('capability') else [])
    cap = caps[0] if caps else {}
    t = cap.get('type', '')
    rng = 0.0
    a0, a1 = _deg(cap.get('angleStart')), _deg(cap.get('angleEnd'))
    if a0 is not None and a1 is not None:
        rng = abs(a1 - a0)
    if t == 'Pan':
        return 'pan', 'position', rng
    if t == 'Tilt':
        return 'tilt', 'position', rng
    if t == 'Intensity':
        return 'dimmer', 'intensity', 0.0
    if t == 'ColorIntensity':
        return _OFL_COLOURS.get(str(cap.get('color', '')).lower(), 'colour'), 'colour', 0.0
    if t in ('ShutterStrobe', 'StrobeSpeed'):
        return 'shutter', 'other', 0.0
    if t in ('PanTiltSpeed', 'Speed', 'EffectSpeed'):
        return 'speed', 'other', 0.0
    if t in ('Zoom', 'Focus'):
        return t.lower(), 'other', 0.0
    return 'raw', 'other', 0.0


def ofl_to_profile(d, pid=None):
    """Open Fixture Library JSON -> jzfix profile. Fine channels (fineChannelAliases) pair with their coarse channel
    (bits 16); null mode entries are reserved slots; wheels / matrix channels come in as raw 8-bit slots."""
    avail = d.get('availableChannels') or {}
    fine_of = {}
    for cname, cd in avail.items():
        for k, alias in enumerate(cd.get('fineChannelAliases') or []):
            fine_of[alias] = (cname, k + 1)
    modes = []
    for m in d.get('modes') or []:
        chans, by_name = [], {}
        for off, cname in enumerate(m.get('channels') or []):
            if cname is None:
                chans.append(_ch(off, 'unused', 'raw', 'other'))
                continue
            if cname in fine_of:
                coarse, level = fine_of[cname]
                if coarse in by_name and level == 1:
                    by_name[coarse]['bits'] = 16
                    by_name[coarse]['fine'] = off
                    continue
                chans.append(_ch(off, cname, 'raw', 'other'))
                continue
            cd = avail.get(cname, {})
            attr, kind, rng = _ofl_kind(cd)
            dflt = cd.get('defaultValue', 0)
            try:
                dflt = float(dflt) / 255.0
            except (TypeError, ValueError):
                dflt = 0.0
            c = _ch(off, cname, attr, kind, 8, dflt, None, rng)
            chans.append(c)
            by_name[cname] = c
        modes.append({'name': m.get('shortName') or m.get('name') or 'mode', 'channels': chans})
    phys = d.get('physical') or {}
    focus = phys.get('focus') or {}
    pid = pid or ('ofl_' + ''.join(ch if ch.isalnum() else '_' for ch in d.get('name', 'fixture').lower()))
    return {'id': pid, 'name': d.get('name', pid), 'maker': d.get('manufacturerKey', ''), 'source': 'ofl',
            'pan_range': float(focus.get('panMax', 0) or 0), 'tilt_range': float(focus.get('tiltMax', 0) or 0),
            'modes': modes}


def profiles_from_text(text):
    try:
        v = json.loads(text) if text and text.strip() else []
    except ValueError:
        v = []
    have = {p['id'] for p in v}
    return v + [p for p in builtin_profiles() if p['id'] not in have]


# ---------------------------------------------------------------- patch helper
def _int(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def rows_to_dicts(rows, cols):
    """Table rows (list of lists, first row = header) -> list of dicts (missing columns blank)."""
    if not rows:
        return []
    head = [str(h).strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        dd = {c: '' for c in cols}
        for k, h in enumerate(head):
            if k < len(r):
                dd[h] = str(r[k]).strip()
        out.append(dd)
    return out


def expand_patch(patch, profiles):
    """patch dicts -> fixture list [{name, profile, mode(dict), univ, addr, size, node}] (count expands with gaps)."""
    P = profile_index(profiles)
    out = []
    for row in patch:
        if row.get('kind', 'fixture') not in ('', 'fixture'):
            continue
        prof = P.get(row.get('profile'))
        mode = find_mode(prof, row.get('mode')) if prof else None
        if mode is None:
            continue
        size = footprint(mode)
        cnt = max(1, _int(row.get('count'), 1))
        gap = _int(row.get('gapslots'), 0)
        a = abs_slot(_int(row.get('univ')), max(1, _int(row.get('addr'), 1)))
        for i in range(cnt):
            nm = row['name'] if cnt == 1 else '{}{}'.format(row['name'], i + 1)
            out.append({'name': nm, 'profile': prof, 'mode': mode, 'univ': a // SLOTS, 'addr': a % SLOTS + 1,
                        'size': size, 'node': row.get('node', '')})
            a += size + gap
    return out


def next_free(patch, profiles, pixels=()):
    """First absolute slot after everything patched (fixtures + pixels)."""
    end = 0
    for f in expand_patch(patch, profiles):
        end = max(end, abs_slot(f['univ'], f['addr']) + f['size'])
    for p in pixels:
        end = max(end, abs_slot(_int(p.get('univ')), _int(p.get('addr'), 1)) + 3)
    return end


def add_fixtures(patch, profiles, profile, mode='', count=1, name='fx', univ=0, addr=1, autonext=True,
                 quantize='fixture', gap=0, node='', pixels=()):
    """-> new patch rows (one per fixture, count 1). autonext: start at the next free slot (after gap). quantize
    'fixture': a fixture that would straddle a universe starts at the next universe instead."""
    P = profile_index(profiles)
    prof = P.get(profile)
    if prof is None:
        raise ValueError('unknown profile ' + str(profile))
    m = find_mode(prof, mode)
    if m is None:
        raise ValueError('unknown mode {} of {}'.format(mode, profile))
    size = footprint(m)
    if autonext and (patch or pixels):
        a = next_free(patch, profiles, pixels)
        a += int(gap) if a else 0
    else:
        a = abs_slot(univ, addr)
    taken = {r['name'] for r in patch}
    rows = []
    k = 1
    for _ in range(int(count)):
        if quantize == 'fixture' and size <= SLOTS and (a % SLOTS) + size > SLOTS:
            a = (a // SLOTS + 1) * SLOTS
        while '{}{}'.format(name, k) in taken:
            k += 1
        nm = '{}{}'.format(name, k)
        taken.add(nm)
        rows.append({'name': nm, 'profile': profile, 'mode': m['name'], 'univ': str(a // SLOTS),
                     'addr': str(a % SLOTS + 1), 'count': '1', 'gapslots': '0', 'node': node, 'kind': 'fixture'})
        a += size + int(gap)
    return rows


def check_patch(patch, profiles, pixels=()):
    """Report (never blocks): unknown profile/mode, overlaps (same slot twice), straddles, empty universe holes."""
    P = profile_index(profiles)
    issues = []
    for row in patch:
        if row.get('kind', 'fixture') not in ('', 'fixture'):
            continue
        prof = P.get(row.get('profile'))
        if prof is None:
            issues.append(('unknown_profile', row.get('name'), row.get('profile')))
        elif find_mode(prof, row.get('mode')) is None:
            issues.append(('unknown_mode', row.get('name'), row.get('mode')))
    owner = {}
    used_u = set()
    items = [(f['name'], abs_slot(f['univ'], f['addr']), f['size']) for f in expand_patch(patch, profiles)]
    for p in pixels:
        items.append(('px' + str(p.get('id')), abs_slot(_int(p.get('univ')), _int(p.get('addr'), 1)), 3))
    for nm, a, size in items:
        if a // SLOTS != (a + size - 1) // SLOTS:
            issues.append(('straddle', nm, '{}.{}'.format(a // SLOTS, a % SLOTS + 1)))
        for s in range(a, a + size):
            used_u.add(s // SLOTS)
            if s in owner and owner[s] != nm:
                issues.append(('overlap', nm, '{} at {}.{}'.format(owner[s], s // SLOTS, s % SLOTS + 1)))
                break
            owner[s] = nm
    if used_u:
        holes = sorted(set(range(min(used_u), max(used_u) + 1)) - used_u)
        if holes:
            issues.append(('holes', 'universes', ' '.join(str(h) for h in holes)))
    return issues


def report_text(issues):
    if not issues:
        return 'patch ok'
    return '\n'.join('{}\t{}\t{}'.format(*i) for i in issues)


# ---------------------------------------------------------------- plan
def build_plan(patch, profiles, pixels, order='rgb', univfilter=None, targetip='127.0.0.1'):
    """Index arrays for compose: rows = used flat universes (sorted); every logical channel and pixel slot as a
    global index row*512 + slot. Rebuilt only when a table or a plan par changes."""
    fx = expand_patch(patch, profiles)
    k = len(order)
    used = set()
    for f in fx:
        a = abs_slot(f['univ'], f['addr'])
        used.update({a // SLOTS, (a + f['size'] - 1) // SLOTS})
    pix = []
    for p in pixels:
        a = abs_slot(_int(p.get('univ')), max(1, _int(p.get('addr'), 1)))
        pix.append(a)
        used.update({a // SLOTS, (a + k - 1) // SLOTS})
    univs = sorted(used)
    row = {u: i for i, u in enumerate(univs)}

    def g(abs_):
        return row[abs_ // SLOTS] * SLOTS + abs_ % SLOTS

    names, coarse, fine, dflt, kinds, rng, attrs, owner = [], [], [], [], [], [], [], []
    groups, gnames, node_of = [], [], {}
    for fi, f in enumerate(fx):
        a = abs_slot(f['univ'], f['addr'])
        seen = {}
        gidx = []
        for c in f['mode']['channels']:
            at = c['attr']
            seen[at] = seen.get(at, 0) + 1
            nm = '{}.{}'.format(f['name'], at if seen[at] == 1 else at + str(seen[at]))
            names.append(nm)
            coarse.append(g(a + c['off']))
            fine.append(g(a + c['fine']) if c.get('bits') == 16 and c.get('fine') is not None else -1)
            dflt.append(float(c.get('default', 0.0)))
            kinds.append(c['kind'])
            r = float(c.get('range_deg') or 0.0)
            if not r and at in ('pan', 'tilt'):
                r = float(f['profile'].get(at + '_range') or (540.0 if at == 'pan' else 270.0))
            rng.append(r)
            attrs.append(at)
            owner.append(fi)
            if c['kind'] in DIM_KINDS:
                gidx.append(coarse[-1])
                if fine[-1] >= 0:
                    gidx.append(fine[-1])
        groups.append(np.array(gidx, dtype=np.int64))
        gnames.append(f['name'])
        if f.get('node'):
            for u in range(a // SLOTS, (a + f['size'] - 1) // SLOTS + 1):
                node_of.setdefault(u, f['node'])
    pix_idx = np.array([[g(a + j) for j in range(k)] for a in pix], dtype=np.int64).reshape(-1, k)
    kinds_a = np.array(kinds) if kinds else np.zeros(0, dtype='<U9')
    coarse_a = np.array(coarse, dtype=np.int64)
    fine_a = np.array(fine, dtype=np.int64)
    dim = np.isin(kinds_a, DIM_KINDS) if len(kinds_a) else np.zeros(0, dtype=bool)
    d8 = coarse_a[dim & (fine_a < 0)] if len(coarse_a) else coarse_a
    attr_idx = {}
    for at, ci, fi_, kd in zip(attrs, coarse, fine, kinds):
        if kd in DIM_KINDS:
            attr_idx.setdefault(at, []).append(ci)
    for j, letter in enumerate(order):
        attr_idx.setdefault(LETTER_ATTR[letter], []).extend(pix_idx[:, j].tolist())
    filt = univfilter if univfilter is None else set(univfilter)
    send_rows = [i for i, u in enumerate(univs) if filt is None or u in filt]
    return {
        'univs': univs, 'row': row, 'nrows': len(univs), 'names': names, 'name_ix': {n: i for i, n in enumerate(names)},
        'coarse': coarse_a, 'fine': fine_a, 'default': np.array(dflt, dtype=np.float64),
        'kinds': kinds_a, 'range': np.array(rng, dtype=np.float64), 'attrs': attrs, 'owner': owner,
        'dim8': np.concatenate([d8, pix_idx.reshape(-1)]).astype(np.int64),
        'dim16': (coarse_a[dim & (fine_a >= 0)], fine_a[dim & (fine_a >= 0)]),
        'pix_idx': pix_idx, 'npix': len(pix), 'order': order,
        'groups': groups, 'gnames': gnames,
        'attr_idx': {a_: np.array(v, dtype=np.int64) for a_, v in attr_idx.items()},
        'fixtures': [f['name'] for f in fx], 'send_rows': send_rows, 'send_univs': [univs[i] for i in send_rows],
        'node_of': node_of, 'slots_used': int(len(set(coarse) | set(x for x in fine if x >= 0)) + pix_idx.size),
    }


def routing_rows(plan, protocol='artnet', targetmode='unicast', targetip='127.0.0.1', loopback=False, first=0):
    """Routing table rows for the DMX Out CHOP (one per sent universe, in channel order). first = Firstuniv, added
    to every patch universe on the wire (patch universe 0 + Firstuniv 1 = sACN universe 1)."""
    rows = [ROUTING_COLS[:]]
    for u in plan['send_univs']:
        net, sub, uni = port_address(u + int(first))
        if loopback:
            ip = '127.0.0.1'
        elif targetmode == 'broadcast':
            ip = '255.255.255.255'
        elif targetmode == 'multicast' and protocol == 'sacn':
            ip = ''
        else:
            ip = plan['node_of'].get(u) or targetip
        rows.append(['u%d' % (u + int(first)), str(net), str(sub), str(uni), ip])
    return rows


def resolve_inputs(plan, chans):
    """{chan name: value} -> (idx array, value01 array) of logical channels. '<fx>.<attr>' 0..1; '<fx>.<attr>_deg'
    degrees (0 = centre of range); fnmatch patterns in the fixture part ('par*.red') hit every match.
    TD CHOPs (Script, Constant; 31550) turn '.' in channel names into '_', so '<fx>_<attr>' matches too (T-90)."""
    ix, vals = [], []
    nix = plan['name_ix']
    us = plan.get('_name_ix_us')
    if us is None:
        us = plan['_name_ix_us'] = {n.replace('.', '_'): i for n, i in nix.items()}
    for name, v in chans.items():
        deg = name.endswith('_deg')
        base = name[:-4] if deg else name
        if any(ch in base for ch in '*?['):
            hits = [nix[n] for n in fnmatch.filter(plan['names'], base)]
            if not hits:
                hits = [us[n] for n in fnmatch.filter(list(us), base)]
        else:
            hits = [nix[base]] if base in nix else ([us[base]] if base in us else [])
        for i in hits:
            if deg:
                r = plan['range'][i] or 360.0
                vals.append(0.5 + float(v) / r)
            else:
                vals.append(float(v))
            ix.append(i)
    return np.array(ix, dtype=np.int64), np.array(vals, dtype=np.float64)


# ---------------------------------------------------------------- master / tempo
def beat_shape(shape, phase):
    f = phase % 1.0
    if shape == 'pulse':
        return max(0.0, 1.0 - 4.0 * f)
    if shape == 'saw':
        return 1.0 - f
    if shape == 'sine':
        return 0.5 + 0.5 * math.cos(2 * math.pi * f)
    return 1.0 if f < 0.5 else 0.0


def master_value(src, t, master=1.0, bpm=120.0, shape='pulse', depth=1.0, audio=0.0, audioamt=1.0, phase0=0.0):
    """Effective master. bpm: 1 - depth * (1 - shape(beat phase)); audio: level * audioamt (clamped 0..1)."""
    b = 1.0 - float(depth) * (1.0 - beat_shape(shape, (t - phase0) * float(bpm) / 60.0))
    a = min(max(float(audio) * float(audioamt), 0.0), 1.0)
    if src == 'bpm':
        m = b
    elif src == 'audio':
        m = a
    elif src == 'bpm-x-audio':
        m = b * a
    else:
        m = 1.0
    return float(master) * m


def tap_bpm(taps, now, keep=8, gap=2.0):
    """Tap tempo: taps more than `gap` s apart restart. -> (taps, bpm or None)."""
    taps = [t for t in taps if now - t <= gap * keep]
    if taps and now - taps[-1] > gap:
        taps = []
    taps = (taps + [now])[-keep:]
    if len(taps) < 2:
        return taps, None
    d = (taps[-1] - taps[0]) / (len(taps) - 1)
    return taps, (60.0 / d if d > 0 else None)


# ---------------------------------------------------------------- patterns
def pattern(kind, t, plan, level=1.0, speed=1.0):
    """Test pattern as (U,512) float 0..255, or None for 'live'. Deterministic in t."""
    U = plan['nrows']
    if kind == 'live' or U == 0:
        return None
    full = 255.0 * float(level)
    out = np.zeros((U, SLOTS), dtype=np.float64)
    flat = out.reshape(-1)
    step = int(math.floor(t * float(speed)))
    if kind == 'zero':
        return out
    if kind == 'full':
        out[:] = full
    elif kind == 'ramp':
        out[:] = np.arange(SLOTS) * 255.0 / (SLOTS - 1) * float(level)
    elif kind == 'channelid':                 # address + flat universe, mod 256 (distinct per universe)
        u = np.array(plan['univs'], dtype=np.int64).reshape(-1, 1)
        out[:] = ((np.arange(1, SLOTS + 1).reshape(1, -1) + u) % 256) * float(level)
    elif kind in ('chase', 'fixtureid', 'walkpixel'):
        fg = [x for x in plan['groups'] if len(x)] if kind in ('chase', 'fixtureid') else []
        npx = plan['npix'] if kind in ('chase', 'walkpixel') else 0
        n = len(fg) + npx
        if n == 0:
            i = (step % (U * SLOTS // 8)) * 8
            flat[i:i + 8] = full
        else:
            i = step % n
            flat[fg[i] if i < len(fg) else plan['pix_idx'][i - len(fg)]] = full
    elif kind == 'rgbcycle':
        seq = [a for a in ('red', 'green', 'blue', 'white') if a in plan['attr_idx']][:3] or ['red']
        a = seq[step % len(seq)]
        if a in plan['attr_idx']:
            flat[plan['attr_idx'][a]] = full
    elif kind == 'strobe':
        if (t * float(speed)) % 1.0 < 0.5:
            flat[plan['dim8']] = full
            c16, f16 = plan['dim16']
            flat[c16] = full
            flat[f16] = full
    return out


# ---------------------------------------------------------------- compose
def _apply_dim(flat, plan, m, all_slots=False):
    if all_slots:
        flat *= m
        return
    flat[plan['dim8']] *= m
    c16, f16 = plan['dim16']
    if len(c16):
        v = (np.rint(flat[c16]) * 256 + np.rint(flat[f16])) * m
        v = np.clip(np.rint(v), 0, 65535)
        flat[c16] = np.floor(v / 256)
        flat[f16] = v % 256


def compose(plan, fix=None, pix=None, t=0.0, prm=None, prev=None):
    """One frame. fix: {chan: value}; pix: (N,3|4) 0..1 sampled colours (or None); prm: dict of par values.
    Steps: zero -> fixtures (defaults + inputs) -> pixels -> pattern (Patternmix) -> master/blackout -> solo ->
    round + clip. Freeze returns prev. -> (U,512) uint8 (all plan rows; send rows are plan['send_rows'])."""
    p = dict(prm or {})
    U = plan['nrows']
    if p.get('freeze') and prev is not None and prev.shape == (U, SLOTS):
        return prev
    buf = np.zeros((U, SLOTS), dtype=np.float64)
    flat = buf.reshape(-1)
    n = len(plan['names'])
    if n:
        v01 = plan['default'].copy()
        if fix:
            ix, vals = resolve_inputs(plan, fix)
            if len(ix):
                v01[ix] = vals
        v01 = np.clip(v01, 0.0, 1.0)
        is16 = plan['fine'] >= 0
        n16 = np.rint(v01 * 65535)
        flat[plan['coarse'][~is16]] = np.rint(v01[~is16] * 255)
        flat[plan['coarse'][is16]] = np.floor(n16[is16] / 256)
        flat[plan['fine'][is16]] = n16[is16] % 256
    if pix is not None and plan['npix']:
        a = np.asarray(pix, dtype=np.float64)[:plan['npix']]
        if len(a):
            sl = pixel_slots(a, plan['order'], p.get('whitemode', 'none'), float(p.get('gamma', 1.0)),
                             float(p.get('pixelscale', 255.0)))
            flat[plan['pix_idx'][:len(sl)].reshape(-1)] = sl.reshape(-1)
    pat = pattern(p.get('pattern', 'live'), t, plan, float(p.get('level', 1.0)), float(p.get('speed', 1.0)))
    if pat is not None:
        mix = p.get('patternmix', 'replace')
        if mix == 'add':
            buf += pat
        elif mix == 'max':
            np.maximum(buf, pat, out=buf)
        else:
            buf[:] = pat
    np.clip(buf, 0, 255, out=buf)
    allmode = p.get('blackoutmode', 'intensity') == 'all'
    m = float(p.get('master_eff', 1.0))
    if p.get('blackout'):
        m = 0.0
    if m != 1.0:
        _apply_dim(flat, plan, max(m, 0.0), allmode)
    solo = (p.get('solofixture') or '').strip()
    if solo:
        keep = np.zeros(U * SLOTS, dtype=bool)
        for nm, gi in zip(plan['fixtures'], range(len(plan['fixtures']))):
            if fnmatch.fnmatch(nm, solo):
                for i, o in enumerate(plan['owner']):
                    if o == gi:
                        keep[plan['coarse'][i]] = True
                        if plan['fine'][i] >= 0:
                            keep[plan['fine'][i]] = True
        if fnmatch.fnmatch('pixels', solo):
            keep[plan['pix_idx'].reshape(-1)] = True
        flat[~keep] = 0
    sc = int(p.get('solochan', 0) or 0)
    if 0 < sc <= SLOTS:
        keep_col = buf[:, sc - 1].copy()
        buf[:] = 0
        buf[:, sc - 1] = keep_col
    return np.clip(np.rint(buf), 0, 255).astype(np.uint8)


def wire_names(plan, first=0):
    """Output channel names u<flat on the wire>, one per sent universe."""
    return ['u%d' % (u + int(first)) for u in plan['send_univs']]


def stats_of(buf):
    return {'nonzero': int(np.count_nonzero(buf)), 'max': int(buf.max()) if buf.size else 0}


def pixchop_to_pixels(a, n, k4=False):
    """TOP to CHOP of the (w x h) sample texture -> (n, 3|4) pixel colours in pixel-list order.
    31550 TOP to CHOP on an h-row image gives channels r0 g0 b0 a0 r1 ... (4 per row, row 0 = first texture row)
    with w samples each; pixel i lives at row i // w, column i % w (same order cook_uvmap writes)."""
    a = np.asarray(a)
    if a.ndim != 2 or not a.shape[0] or n <= 0:
        return None
    rows = a.shape[0] // 4
    w = a.shape[1]
    px = a[:rows * 4].reshape(rows, 4, w).transpose(0, 2, 1).reshape(-1, 4)
    return px[:n, :4 if k4 else 3]


def loop_diff(sent, received):
    """Max abs difference sent vs received (both (U,512)-like); rows compared up to the shorter count; -1 if nothing."""
    if sent is None or received is None or not len(sent) or not len(received):
        return -1.0
    n = min(len(sent), len(received))
    w = min(np.asarray(sent).shape[1], np.asarray(received).shape[1])
    return float(np.max(np.abs(np.asarray(sent, dtype=np.float64)[:n, :w] -
                               np.asarray(received, dtype=np.float64)[:n, :w])))


# ---------------------------------------------------------------- monitor
def monitor_layout(width, height, cell, count):
    """Tiles of 32x16 slots (cell px each, 4 px gutter): -> (tiles_x, tiles_y, shown)."""
    tw, th = 32 * int(cell) + 4, 16 * int(cell) + 4
    tx, ty = max(1, int(width) // tw), max(1, int(height) // th)
    return tx, ty, min(int(count), tx * ty)
