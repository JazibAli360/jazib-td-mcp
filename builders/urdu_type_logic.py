"""urdu_type pure logic (no td): bidi-lite at word level, layout, animation, pixel-free measuring (font tables +
hb-shape extents; no TOP readback, no evalTextSize: T-74 + crash 4), alpha bbox (offline only), hb-shape check.

Spec: docs/research/BJ_urdu_arabic_text_shaping.md section 5 (clean-room, our own). Copied into the COMP as the
Text DAT `urdu_type_logic`; mirrored here for the offline tests (test/test_urdu_type.py). Pure ASCII source:
non-ASCII characters are written as escapes.

Coordinates: layout works in output pixels, x right, y DOWN from the top edge. Ink boxes of a word tile are given
relative to the tile centre, x right, y UP (numpyArray row 0 = bottom, T-58). The runtime converts for the shader.
"""
import json
import math
import os
import subprocess

DIRECTION = [('auto', 'Auto (first strong word)'), ('rtl', 'Right to left'), ('ltr', 'Left to right')]
ALIGN = [('center', 'Center'), ('start', 'Start (right for RTL)'), ('end', 'End (left for RTL)')]
MODE = [('none', 'None'), ('fade', 'Fade'), ('slide', 'Slide'), ('scale', 'Scale'), ('wipe', 'Wipe'),
        ('blur', 'Blur'), ('pulse', 'Pulse')]
ORDER = [('reading', 'Reading order'), ('reverse', 'Reverse'), ('random', 'Random'), ('centerout', 'Center out')]
TIMING = [('manual', 'Manual (Progress)'), ('seconds', 'Seconds'), ('bpm', 'BPM (beats)'), ('audio', 'Audio level')]
EASE = [('linear', 'Linear'), ('ease', 'Ease in-out'), ('expo', 'Expo out')]
MEASURE = [('hbshape', 'HarfBuzz extents (hb-shape)'), ('estimate', 'Estimate (no shaper)')]
BACKGROUND = [('none', 'None (transparent)'), ('color', 'Colour'), ('input', 'In TOP (in1)')]
TYPEFACE = [('Regular', 'Regular'), ('Bold', 'Bold')]

# per-word fields sent to the shader (one CHOP channel = one row of the params texture, one sample = one word)
FIELDS = ['cx', 'cy', 'tx', 'ty', 'sx', 'sy', 'rot', 'alpha', 'reveal', 'blur',
          'bx0', 'by0', 'bx1', 'by1', 'rtl', 'live', 'progress', 'ax', 'ay', 'tw', 'th']

HB_SHAPE = '/opt/homebrew/bin/hb-shape'
NASTALIQ_TTC = '/System/Library/Fonts/NotoNastaliq.ttc'

ARABIC_PUNCT = set('\u060c\u061b\u061f\u06d4\u066a\u066b\u066c\u06dd')   # comma, semicolon, ?, full stop, % etc.


def menu_index(menu, name):
    for i, m in enumerate(menu):
        if m[0] == name:
            return i
    return 0


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


# ---------------------------------------------------------------- bidi-lite (UAX #9 at word granularity)

def char_class(ch):
    """Simplified bidi class of one character: AL, R, L, EN, AN, NSM or N."""
    o = ord(ch)
    if 0x06F0 <= o <= 0x06F9 or 0x0660 <= o <= 0x0669:
        return 'AN' if o <= 0x0669 else 'EN'      # Extended Arabic-Indic (Urdu) digits are EN in UAX #9
    if 0x0610 <= o <= 0x061A or 0x064B <= o <= 0x065F or o == 0x0670 or 0x06D6 <= o <= 0x06ED:
        return 'NSM'
    if (0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0x08A0 <= o <= 0x08FF or 0xFB50 <= o <= 0xFDFF or
            0xFE70 <= o <= 0xFEFF):
        if o == 0x060C:                           # Arabic comma is CS (neutral here); 061B/061F/06D4 are AL
            return 'N'
        if o in (0x066B, 0x066C):
            return 'AN'
        return 'AL'
    if 0x0590 <= o <= 0x05FF or 0xFB1D <= o <= 0xFB4F:
        return 'R'
    if '0' <= ch <= '9':
        return 'EN'
    if ch.isalpha():
        return 'L'
    return 'N'


def token_info(tok):
    """(class, script, mixed) of a whole token. class = first strong (AL/R/L), else EN/AN, else N."""
    strong = [char_class(c) for c in tok]
    first = None
    has_r = has_l = has_n = False
    for k in strong:
        if k in ('AL', 'R'):
            has_r = True
            first = first or k
        elif k == 'L':
            has_l = True
            first = first or k
        elif k in ('EN', 'AN'):
            has_n = True
    if first is None:
        if 'AN' in strong:
            cls = 'AN'
        elif 'EN' in strong:
            cls = 'EN'
        else:
            cls = 'N'
    else:
        cls = first
    if cls in ('AL', 'R'):
        script = 'arabic' if cls == 'AL' else 'hebrew'
    elif cls == 'L':
        script = 'latin'
    elif cls in ('EN', 'AN'):
        script = 'digits_ar' if any(0x0660 <= ord(c) <= 0x06F9 for c in tok) else 'digits'
    else:
        script = 'arabic' if any(c in ARABIC_PUNCT for c in tok) else 'neutral'
    mixed = (has_r and has_l) or (has_n and (has_r or has_l))
    return cls, script, mixed


def tokenize(text):
    """Paragraphs (split on newlines) of whitespace-separated tokens. Punctuation stays glued to its word."""
    text = (text or '').replace('\r\n', '\n').replace('\r', '\n').replace('\u2028', '\n').replace('\u2029', '\n')
    return [p.split() for p in text.split('\n')]


def base_level(classes, direction):
    if direction == 'rtl':
        return 1
    if direction == 'ltr':
        return 0
    for k in classes:
        if k in ('AL', 'R'):
            return 1
        if k == 'L':
            return 0
    return 0


def resolve_levels(classes, base):
    """Embedding level per token (W1-W7, N1-N2, I1-I2 on token classes; no explicit embeddings)."""
    n = len(classes)
    t = list(classes)
    sos = 'R' if base % 2 else 'L'
    # W2: EN after AL -> AN; W3: AL -> R
    last = sos
    for i in range(n):
        if t[i] in ('AL', 'R', 'L'):
            last = t[i]
        elif t[i] == 'EN' and last == 'AL':
            t[i] = 'AN'
    t = ['R' if k == 'AL' else k for k in t]
    # W7: EN -> L when the last strong is L
    last = sos
    for i in range(n):
        if t[i] in ('R', 'L'):
            last = t[i]
        elif t[i] == 'EN' and last == 'L':
            t[i] = 'L'
    # N1/N2: neutrals take the surrounding direction (EN/AN count as R) or the base
    def strong_dir(k):
        return 'L' if k == 'L' else 'R' if k in ('R', 'EN', 'AN') else None
    i = 0
    while i < n:
        if t[i] == 'N':
            j = i
            while j < n and t[j] == 'N':
                j += 1
            before = strong_dir(t[i - 1]) if i > 0 else sos
            after = strong_dir(t[j]) if j < n else sos
            d = before if before == after else sos
            for k in range(i, j):
                t[k] = d
            i = j
        else:
            i += 1
    out = []
    for k in t:
        if base % 2 == 0:
            out.append(base + (1 if k == 'R' else 2 if k in ('AN', 'EN') else 0))
        else:
            out.append(base + (1 if k in ('L', 'EN', 'AN') else 0))
    return out


def reorder(levels):
    """L2: visual order (left to right) of indices for one line."""
    idx = list(range(len(levels)))
    if not levels:
        return idx
    hi = max(levels)
    odd = [l for l in levels if l % 2]
    lo = min(odd) if odd else hi + 1
    for lev in range(hi, lo - 1, -1):
        i = 0
        while i < len(idx):
            if levels[idx[i]] >= lev:
                j = i
                while j < len(idx) and levels[idx[j]] >= lev:
                    j += 1
                idx[i:j] = idx[i:j][::-1]
                i = j
            else:
                i += 1
    return idx


def parse(text, direction='auto'):
    """Logical rows: idx, text, cls, script, mixed, level, dir ('rtl'/'ltr'), para, base."""
    rows = []
    for pi, toks in enumerate(tokenize(text)):
        if not toks:
            continue
        info = [token_info(tk) for tk in toks]
        classes = [x[0] for x in info]
        base = base_level(classes, direction)
        levels = resolve_levels(classes, base)
        for tk, (cls, script, mixed), lev in zip(toks, info, levels):
            rows.append({'idx': len(rows), 'text': tk, 'cls': cls, 'script': script, 'mixed': mixed,
                         'level': lev, 'dir': 'rtl' if lev % 2 else 'ltr', 'para': pi, 'base': base})
    return rows


def font_role(row):
    """Which font a token uses: 'rtl' (Urdu/Arabic font), 'ltr' (Latin font) or 'digits'."""
    s = row['script']
    if s in ('arabic', 'hebrew', 'digits_ar'):
        return 'rtl'
    if s == 'digits':
        return 'digits'
    if s == 'neutral':
        return 'rtl' if row['dir'] == 'rtl' else 'ltr'
    return 'ltr'


def select_text(text, dat_rows, line):
    """Text source: line `line` of a DAT (list of strings) when given, else the Text par."""
    if dat_rows:
        return dat_rows[int(line) % len(dat_rows)]
    return text or ''


# ---------------------------------------------------------------- measuring

def tile_size(text_w, text_h, size, padx=0.55, pady=0.4):
    """Tile resolution for one word from the Text TOP's evalTextSize, padded for Nastaliq overhang (U-03)."""
    w = int(math.ceil((text_w + 2.0 * padx * size) / 4.0) * 4)
    h = int(math.ceil((text_h + 2.0 * pady * size) / 4.0) * 4)
    return max(w, 8), max(h, 8)


def bbox_from_alpha(alpha, thr=0.02, edge=2):
    """Ink bbox of a 2D alpha array (row 0 = bottom). Returns dict x0,y0,x1,y1 (pixel edges, relative to the tile
    centre, y up), w, h, edge (non-zero pixels on the outer `edge` px = clipped tails) or None when empty."""
    import numpy as np
    a = np.asarray(alpha)
    m = a > thr
    if not m.any():
        return None
    rows = np.nonzero(m.any(axis=1))[0]
    cols = np.nonzero(m.any(axis=0))[0]
    H, W = a.shape
    cxp, cyp = W / 2.0, H / 2.0
    e = int(m[:edge, :].sum() + m[-edge:, :].sum() + m[:, :edge].sum() + m[:, -edge:].sum()) if edge else 0
    x0, x1 = float(cols[0]) - cxp, float(cols[-1] + 1) - cxp
    y0, y1 = float(rows[0]) - cyp, float(rows[-1] + 1) - cyp
    return {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'w': x1 - x0, 'h': y1 - y0, 'edge': e}


def hb_font_for(fontname, fontfile):
    """(path, face index) for hb-shape, or None. Explicit file wins; Noto Nastaliq maps to the system .ttc."""
    if fontfile and os.path.isfile(fontfile):
        return fontfile, 0
    if fontname and 'nastaliq' in fontname.lower() and os.path.isfile(NASTALIQ_TTC):
        return NASTALIQ_TTC, (1 if fontname.strip().lower().endswith(' ui') else 0)
    return find_font(fontname)


# ---------------------------------------------------------------- pixel-free measuring (T-74 + crash 4)
# The TD runtime never calls a TOP method to measure (no numpyArray, no evalTextSize, no cook(force)): ink boxes come
# from the font file (hhea metrics) and HarfBuzz glyph extents (hb-shape --show-extents, one process per font per
# rebuild), else from a per-character estimate. Pure Python, no deps.

FONT_DIRS = ('/System/Library/Fonts', '/System/Library/Fonts/Supplemental', '/Library/Fonts',
             os.path.expanduser('~/Library/Fonts'))
_FONT_INDEX = {}       # lower family name -> (path, face); filled lazily by font_index()


def _sfnt_offsets(data):
    """Table directory offsets of every face in a .ttf/.otf/.ttc byte string."""
    if data[:4] == b'ttcf':
        n = int.from_bytes(data[8:12], 'big')
        return [int.from_bytes(data[12 + 4 * i:16 + 4 * i], 'big') for i in range(n)]
    return [0]


def _tables(data, off):
    num = int.from_bytes(data[off + 4:off + 6], 'big')
    t = {}
    for i in range(num):
        rec = off + 12 + 16 * i
        t[data[rec:rec + 4].decode('latin-1')] = (int.from_bytes(data[rec + 8:rec + 12], 'big'),
                                                  int.from_bytes(data[rec + 12:rec + 16], 'big'))
    return t


def font_metrics(fontfile, face=0):
    """dict upem, ascent, descent (positive), linegap from head + hhea; None when unreadable."""
    try:
        with open(fontfile, 'rb') as f:
            data = f.read()
        offs = _sfnt_offsets(data)
        t = _tables(data, offs[min(face, len(offs) - 1)])
        h = t['head'][0]
        upem = int.from_bytes(data[h + 18:h + 20], 'big')
        hh = t['hhea'][0]
        asc = int.from_bytes(data[hh + 4:hh + 6], 'big', signed=True)
        desc = int.from_bytes(data[hh + 6:hh + 8], 'big', signed=True)
        gap = int.from_bytes(data[hh + 8:hh + 10], 'big', signed=True)
        return {'upem': upem, 'ascent': asc, 'descent': abs(desc), 'linegap': gap}
    except Exception:
        return None


_FILE_INDEX = {}       # lower file stem (no spaces) -> real path


def _read_face_names(f, size):
    """Family names of every face in an open font file, reading only the headers + name tables (seek, no full read)."""
    def rd(off, n):
        f.seek(off)
        return f.read(n)
    head = rd(0, 12)
    offs = [0]
    if head[:4] == b'ttcf':
        n = min(int.from_bytes(head[8:12], 'big'), 64)
        raw = rd(12, 4 * n)
        offs = [int.from_bytes(raw[4 * i:4 * i + 4], 'big') for i in range(n)]
    out = []
    for fi, off in enumerate(offs):
        num = int.from_bytes(rd(off + 4, 2), 'big')
        dirb = rd(off + 12, 16 * num)
        for i in range(num):
            r = dirb[16 * i:16 * i + 16]
            if r[:4] == b'name':
                to, tl = int.from_bytes(r[8:12], 'big'), int.from_bytes(r[12:16], 'big')
                if 0 < tl < 1 << 20 and to + tl <= size:
                    out += [(fi, nm) for nm in _names_from_blob(rd(to, tl))]
                break
    return out


def _names_from_blob(blob):
    """Family names (ids 1, 4, 16) from a raw name table."""
    out = []
    try:
        count = int.from_bytes(blob[2:4], 'big')
        sto = int.from_bytes(blob[4:6], 'big')
        for i in range(count):
            r = 6 + 12 * i
            pid = int.from_bytes(blob[r:r + 2], 'big')
            nid = int.from_bytes(blob[r + 6:r + 8], 'big')
            ln = int.from_bytes(blob[r + 8:r + 10], 'big')
            o = int.from_bytes(blob[r + 10:r + 12], 'big')
            if nid not in (1, 4, 16):
                continue
            raw = blob[sto + o:sto + o + ln]
            s = raw.decode('utf-16-be', 'ignore') if pid in (0, 3) else raw.decode('latin-1', 'ignore')
            if s and s not in out:
                out.append(s)
    except Exception:
        pass
    return out


def font_index(dirs=FONT_DIRS):
    """lower family name -> (path, face) over the font folders (headers only, cached). Slow-ish once (~0.1-0.5 s):
    the runtime only calls it for a font name that neither the Nastaliq map nor the file-name guess resolves."""
    if _FONT_INDEX:
        return _FONT_INDEX
    for d in dirs:
        try:
            names = sorted(os.listdir(d))
        except Exception:
            continue
        for fn in names:
            if not fn.lower().endswith(('.ttf', '.otf', '.ttc')):
                continue
            p = os.path.join(d, fn)
            try:
                with open(p, 'rb') as f:
                    for fi, nm in _read_face_names(f, os.path.getsize(p)):
                        _FONT_INDEX.setdefault(nm.strip().lower(), (p, fi))
            except Exception:
                continue
    return _FONT_INDEX


def find_font(fontname, dirs=FONT_DIRS):
    """(path, face) of a font family by name: file-name guess first (fast), then the name-table index."""
    if not fontname:
        return None
    key = fontname.strip().lower()
    if not _FILE_INDEX:
        for d in dirs:
            try:
                for fn in os.listdir(d):
                    stem, ext = os.path.splitext(fn)
                    if ext.lower() in ('.ttf', '.otf', '.ttc'):
                        _FILE_INDEX.setdefault(stem.lower().replace(' ', ''), os.path.join(d, fn))
            except Exception:
                continue
    p = _FILE_INDEX.get(key.replace(' ', ''))
    if p:
        return p, 0
    return font_index(dirs).get(key)


def hb_extents_batch(texts, fontfile, face=0, language='ur', exe=HB_SHAPE, timeout=4.0, tmpdir=None):
    """One hb-shape process for many words. Returns a list (same order) of dicts in font units:
    advance, x0, x1 (ink, from the pen start, x right), y0, y1 (ink, from the baseline, y up), glyphs, notdef;
    None for every entry when hb-shape is missing or fails."""
    if not texts:
        return []
    if not os.path.isfile(exe) or not fontfile or any('\n' in t for t in texts):
        return [None] * len(texts)
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.txt', dir=tmpdir)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write('\n'.join(texts) + '\n')
        cmd = [exe, '--output-format=json', '--show-extents', '--language=' + language,
               '--face-index={}'.format(face), '--font-file=' + fontfile, '--text-file=' + path]
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        lines = [ln for ln in r.stdout.decode('utf-8').splitlines() if ln.strip()]
        if len(lines) != len(texts):
            return [None] * len(texts)
        return [hb_ink(json.loads(ln)) for ln in lines]
    except Exception:
        return [None] * len(texts)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def hb_ink(glyphs):
    """Ink box + advance of one hb-shape --show-extents JSON line (font units)."""
    pen = 0
    x0 = y0 = float('inf')
    x1 = y1 = float('-inf')
    notdef = False
    for g in glyphs:
        if g.get('g') in ('.notdef', 0, '0'):
            notdef = True
        w, h = g.get('w', 0), g.get('h', 0)
        if w or h:
            gx = pen + g.get('dx', 0) + g.get('xb', 0)
            gy = g.get('dy', 0) + g.get('yb', 0)            # top of the ink (y up)
            x0, x1 = min(x0, gx, gx + w), max(x1, gx, gx + w)
            y0, y1 = min(y0, gy, gy + h), max(y1, gy, gy + h)
        pen += g.get('ax', 0)
    if x0 == float('inf'):
        x0 = x1 = y0 = y1 = 0
    return {'advance': pen, 'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1, 'glyphs': len(glyphs), 'notdef': notdef}


def line_box(metrics, size):
    """(line box height px, baseline y px from the box centre, y up) for a Text TOP centring the hhea line box."""
    if not metrics or not metrics.get('upem'):
        return 1.2 * size, -0.3 * size
    s = size / float(metrics['upem'])
    asc, desc = metrics['ascent'] * s, metrics['descent'] * s
    h = asc + desc
    return h, h / 2.0 - asc


def ink_from_hb(ext, metrics, size):
    """Ink box relative to the tile centre (x right, y up) from hb extents, assuming the Text TOP centres the advance
    box horizontally (alignx center) and the hhea line box vertically (aligny center). Returns the measure dict."""
    s = size / float(metrics['upem'])
    lh, base = line_box(metrics, size)
    adv = ext['advance'] * s
    x0 = ext['x0'] * s - adv / 2.0
    x1 = ext['x1'] * s - adv / 2.0
    y0 = base + ext['y0'] * s
    y1 = base + ext['y1'] * s
    return {'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1, 'w': x1 - x0, 'h': y1 - y0, 'adv': adv, 'lineh': lh,
            'src': 'hb'}


def estimate_ink(text, size, metrics=None, role='ltr'):
    """Fallback ink box with no shaper: advance ~ 0.55 em per Latin/digit char, 0.42 em per Arabic-script letter
    (marks count 0), ink = advance box, cap height to descender."""
    adv = 0.0
    for ch in text:
        k = char_class(ch)
        if k == 'NSM':
            continue
        adv += (0.42 if k in ('AL', 'R', 'AN') or 0x0600 <= ord(ch) <= 0x06FF else 0.55) * size
    lh, base = line_box(metrics, size)
    up = (1.0 if role == 'rtl' else 0.72) * size
    down = (0.45 if role == 'rtl' else 0.22) * size
    return {'x0': -adv / 2.0, 'x1': adv / 2.0, 'y0': base - down, 'y1': base + up, 'w': adv, 'h': up + down,
            'adv': adv, 'lineh': lh, 'src': 'est'}


def measure_words(items, size, hb_exe=HB_SHAPE, tmpdir=None):
    """items: list of (text, fontfile_or_None, face, role). Groups by font, one hb-shape call per font.
    Returns a list of measure dicts (x0 x1 y0 y1 w h adv lineh src, hbglyphs)."""
    out = [None] * len(items)
    groups = {}
    for i, (txt, ff, face, role) in enumerate(items):
        groups.setdefault((ff, face), []).append(i)
    for (ff, face), idxs in groups.items():
        met = font_metrics(ff, face) if ff else None
        exts = hb_extents_batch([items[i][0] for i in idxs], ff, face, exe=hb_exe, tmpdir=tmpdir) if ff and met \
            else [None] * len(idxs)
        for i, e in zip(idxs, exts):
            if e is not None and not e['notdef'] and e['advance'] > 0:
                m = ink_from_hb(e, met, size)
                m['hbglyphs'] = e['glyphs']
            else:
                m = estimate_ink(items[i][0], size, met, items[i][3])
                m['hbglyphs'] = 0
            out[i] = m
    return out


def tile_for(m, size, padx=0.55, pady=0.4):
    """Tile resolution that holds the centred advance box, the line box and the ink, plus pad (em)."""
    half_w = max(abs(m['x0']), abs(m['x1']), m['adv'] / 2.0) + padx * size
    half_h = max(abs(m['y0']), abs(m['y1']), m['lineh'] / 2.0) + pady * size
    return int(math.ceil(2 * half_w / 4.0) * 4), int(math.ceil(2 * half_h / 4.0) * 4)


def hb_advance(text, fontfile, face=0, features=None, language='ur', exe=HB_SHAPE, timeout=3.0):
    """(advance sum in font units, glyph count, upem-free) from hb-shape --output-format=json; None on any failure."""
    if not os.path.isfile(exe) or not fontfile:
        return None
    cmd = [exe, '--output-format=json', '--language=' + language, '--face-index={}'.format(face)]
    if features:
        cmd.append('--features=' + features)
    cmd += [fontfile, text]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        data = json.loads(r.stdout.decode('utf-8'))
    except Exception:
        return None
    return {'advance': sum(g.get('ax', 0) for g in data), 'glyphs': len(data)}


def hb_upem(fontfile, face=0):
    """units per em from the head table (pure Python, no deps); 1000 for Noto Nastaliq."""
    try:
        with open(fontfile, 'rb') as f:
            data = f.read()
        off = 0
        if data[:4] == b'ttcf':
            off = int.from_bytes(data[12 + 4 * face:16 + 4 * face], 'big')
        num = int.from_bytes(data[off + 4:off + 6], 'big')
        for i in range(num):
            rec = off + 12 + 16 * i
            if data[rec:rec + 4] == b'head':
                t = int.from_bytes(data[rec + 8:rec + 12], 'big')
                return int.from_bytes(data[t + 18:t + 20], 'big')
    except Exception:
        return None
    return None


# ---------------------------------------------------------------- pre-shaped atlas route (urdu_render.py, outside TD)
# T-76: the COMP never makes a Text TOP with an Urdu font and never calls a TOP method. Words are shaped + rasterised
# by HarfBuzz (hb-view) in a child process into one atlas PNG + metrics JSON; TD loads the PNG (Movie File In).

def render_key(item, margin_em, version=1):
    """Content hash of a word raster: text, font name/file, typeface, weight, size, language, direction, margin."""
    s = json.dumps([item.get('text', ''), item.get('font', ''), item.get('fontfile', ''), item.get('typeface', ''),
                    int(item.get('weight') or 0), round(float(item.get('size', 0)), 2), item.get('lang', ''),
                    item.get('dir', ''), round(float(margin_em), 3), int(version)], ensure_ascii=True)
    import hashlib
    return hashlib.sha1(s.encode('ascii')).hexdigest()[:16]


def atlas_key(word_keys):
    import hashlib
    return hashlib.sha1('|'.join(word_keys).encode('ascii')).hexdigest()[:16]


def render_items(rows, fonts, size, weight=0, typeface='Regular'):
    """Render job items (logical order) from parse() rows. fonts: role -> (font name, font file)."""
    items = []
    for r in rows:
        role = font_role(r)
        font, ffile = fonts.get(role) or fonts.get('ltr') or ('', '')
        rtl = r['script'] in ('arabic', 'hebrew') or (r['script'] == 'neutral' and r['dir'] == 'rtl')
        items.append({'text': r['text'], 'font': font, 'fontfile': ffile or '',
                      'typeface': typeface if role == 'rtl' else 'Regular',
                      'weight': int(weight) if role == 'rtl' else 0, 'size': float(size),
                      'lang': 'ur' if role == 'rtl' else ('en' if r['script'] == 'latin' else ''),
                      'dir': 'rtl' if rtl else 'ltr', 'role': role})
    return items


def tex_rect(x, ytop, w, h, atlas_h):
    """Atlas rect from PNG coords (top-left origin) to TD texture coords (bottom-left origin, y up)."""
    return (x, atlas_h - ytop - h, w, h)


def clusters_from_hb(glyphs):
    """hb-shape JSON glyphs -> per-cluster list (cluster = first code point index, visual order as HarfBuzz gives it):
    cl, n glyphs, ax (advance px), x0 x1 y0 y1 ink from that cluster's pen start / baseline (y up)."""
    out = []
    by = {}
    pen = 0
    for g in glyphs:
        cl = g.get('cl', 0)
        c = by.get(cl)
        if c is None:
            c = by[cl] = {'cl': cl, 'n': 0, 'ax': 0, 'pen': pen, 'x0': None, 'x1': None, 'y0': None, 'y1': None}
            out.append(c)
        c['n'] += 1
        c['ax'] += g.get('ax', 0)
        w, h = g.get('w', 0), g.get('h', 0)
        if w or h:
            gx = pen + g.get('dx', 0) + g.get('xb', 0) - c['pen']
            gy = g.get('dy', 0) + g.get('yb', 0)
            xs, ys = (gx, gx + w), (gy, gy + h)
            c['x0'] = min(xs) if c['x0'] is None else min(c['x0'], min(xs))
            c['x1'] = max(xs) if c['x1'] is None else max(c['x1'], max(xs))
            c['y0'] = min(ys) if c['y0'] is None else min(c['y0'], min(ys))
            c['y1'] = max(ys) if c['y1'] is None else max(c['y1'], max(ys))
        pen += g.get('ax', 0)
    for c in out:
        for k in ('x0', 'x1', 'y0', 'y1'):
            if c[k] is None:
                c[k] = 0
    return out


def words_from_atlas(rows, atlas):
    """Join parse() rows with the atlas JSON words (same order) into layout() input dicts. Words that failed to
    render keep a zero box (they take no space and draw nothing)."""
    ws = []
    aw = atlas.get('words', []) if atlas else []
    for r, a in zip(rows, aw):
        ok = bool(a.get('ok'))
        rect = a.get('rect') or [0, 0, 0, 0]
        ws.append({'idx': r['idx'], 'text': r['text'], 'para': r['para'], 'level': r['level'], 'base': r['base'],
                   'dir': r['dir'], 'script': r['script'], 'mixed': int(r['mixed']),
                   'rtl': 1 if r['dir'] == 'rtl' else 0,
                   'x0': float(a.get('x0', 0.0)) if ok else 0.0, 'x1': float(a.get('x1', 0.0)) if ok else 0.0,
                   'y0': float(a.get('y0', 0.0)) if ok else 0.0, 'y1': float(a.get('y1', 0.0)) if ok else 0.0,
                   'w': float(a.get('x1', 0.0)) - float(a.get('x0', 0.0)) if ok else 0.0,
                   'adv': float(a.get('adv', 0.0)), 'lineh': float(a.get('lineh', 0.0)),
                   'ax': float(rect[0]), 'ay': float(rect[1]), 'tw': float(rect[2]), 'th': float(rect[3]),
                   'glyphs': int(a.get('glyphs', 0)), 'notdef': int(a.get('notdef', 0)), 'ok': ok,
                   'edge': int(a.get('edge', 0)), 'key': a.get('key', '')})
        if ok and 'baseline_top' in a:           # baseline relative to the tile centre, y up
            ws[-1]['basey'] = float(a.get('h', 0)) / 2.0 - float(a['baseline_top'])
    return ws


# ---------------------------------------------------------------- layout

def _line_breaks(words, size, wordgap, maxwidth):
    """Logical-order lines per paragraph. A word wider than maxwidth sits on its own line."""
    lines = []
    cur, cur_w, cur_para = [], 0.0, None
    gap = wordgap * size
    for w in words:
        ww = w['w']
        if cur and (w['para'] != cur_para or (maxwidth > 0 and cur_w + gap + ww > maxwidth)):
            lines.append(cur)
            cur, cur_w = [], 0.0
        if not cur:
            cur_para = w['para']
            cur, cur_w = [w], ww
        else:
            cur.append(w)
            cur_w += gap + ww
    if cur:
        lines.append(cur)
    return lines


def layout(words, size=160.0, wordgap=0.30, linegap=1.0, lineh=2.5, maxwidth=0.0, align='center',
           anchorx=0.5, anchory=0.5, outw=1080, outh=1920):
    """words: logical list of dicts with idx, para, level, base, w, x0, x1, y0, y1 (ink, tile-centre relative, y up).
    Returns dict idx -> placement (cx, cy tile centre in output px, y down; left, right, top, bottom of the ink box;
    line; vis = left-to-right position in the line), plus 'lines' and 'block' (left, top, right, bottom)."""
    gap = wordgap * size
    pitch = linegap * lineh * size
    lines = _line_breaks(words, size, wordgap, maxwidth)
    nl = len(lines)
    ax, ay = anchorx * outw, anchory * outh
    top_line_y = ay - (nl - 1) * pitch / 2.0
    place = {}
    bl = bt = float('inf')
    br = bb = float('-inf')
    for li, line in enumerate(lines):
        base = line[0]['base']
        order = reorder([w['level'] for w in line])
        vis = [line[k] for k in order]
        width = sum(w['w'] for w in vis) + gap * (len(vis) - 1)
        rtl = base % 2 == 1
        if align == 'center':
            left = ax - width / 2.0
        elif (align == 'start') == rtl:      # start of RTL / end of LTR: right edge at the anchor
            left = ax - width
        else:
            left = ax
        y0 = top_line_y + li * pitch
        bys = [w['basey'] for w in vis if 'basey' in w]
        ref = min(bys) if bys else 0.0           # lowest baseline of the line (tile-centre relative, y up)
        x = left
        for vi, w in enumerate(vis):
            cx = x - w['x0']
            y = y0 + (w['basey'] - ref if 'basey' in w else 0.0)     # shared baseline across fonts (y down)
            place[w['idx']] = {'cx': cx, 'cy': y, 'left': x, 'right': x + w['w'], 'top': y - w['y1'],
                               'bottom': y - w['y0'], 'line': li, 'vis': vi, 'w': w['w'], 'h': w['y1'] - w['y0']}
            bl, br = min(bl, x), max(br, x + w['w'])
            bt, bb = min(bt, y - w['y1']), max(bb, y - w['y0'])
            x += w['w'] + gap
    return {'place': place, 'lines': nl, 'block': (bl, bt, br, bb) if place else (ax, ay, ax, ay)}


def ranks(place, n_idx, order='reading', seed=0):
    """Animation rank per logical idx (0 = first)."""
    idx = list(range(n_idx))
    if order == 'reverse':
        seq = idx[::-1]
    elif order == 'random':
        seq = idx[:]
        s = (int(seed) * 2654435761 + 12345) & 0xFFFFFFFF
        for i in range(len(seq) - 1, 0, -1):          # Fisher-Yates with an LCG (deterministic, no random module)
            s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
            j = s % (i + 1)
            seq[i], seq[j] = seq[j], seq[i]
    elif order == 'centerout' and place:
        xs = [(place[i]['left'] + place[i]['right']) / 2.0 for i in idx]
        ys = [place[i]['cy'] for i in idx]
        mx = (min(p['left'] for p in place.values()) + max(p['right'] for p in place.values())) / 2.0
        my = (min(ys) + max(ys)) / 2.0
        seq = sorted(idx, key=lambda i: (math.hypot(xs[i] - mx, ys[i] - my), i))
    else:
        seq = idx
    r = [0] * n_idx
    for k, i in enumerate(seq):
        r[i] = k
    return r


# ---------------------------------------------------------------- animation

def ease(t, kind='linear'):
    t = clamp(t)
    if kind == 'ease':
        return t * t * (3.0 - 2.0 * t)
    if kind == 'expo':
        return 1.0 if t >= 1.0 else 1.0 - 2.0 ** (-10.0 * t)
    return t


def local_progress(p, rank, n, stagger):
    if n <= 1 or stagger <= 0:
        return clamp(p)
    s = clamp(stagger)
    span = 1.0 - s * (n - 1) / float(n)
    return clamp((p - rank * s / float(n)) / max(span, 1e-6))


def progress(timing, manual=0.0, elapsed=0.0, seconds=2.0, bpm=120.0, beats=4.0, level=0.0, gain=1.0, loop=False,
             chan_progress=None, chan_beat=None):
    """Global progress 0..1 from the Timing mode. CHOP channels (in2) override when present."""
    if timing == 'audio':
        return clamp(level * gain)
    if timing == 'manual':
        p = chan_progress if chan_progress is not None else manual
        return clamp(p)
    if timing == 'bpm':
        if chan_beat is not None:
            p = chan_beat / max(beats, 1e-6)
        else:
            p = elapsed * bpm / 60.0 / max(beats, 1e-6)
    else:
        p = elapsed / max(seconds, 1e-6)
    if loop:
        p = p - math.floor(p)
    return clamp(p)


def anim(rank, n, p, mode='fade', stagger=0.5, ease_kind='ease', slidex=0.0, slidey=-80.0, scalefrom=0.6,
         blurmax=24.0, pulseamt=0.25):
    """Per-word transform at global progress p. Returns tx, ty (px, y up), sx, sy, rot, alpha, reveal, blur."""
    lp = ease(local_progress(p, rank, n, stagger), ease_kind)
    r = {'tx': 0.0, 'ty': 0.0, 'sx': 1.0, 'sy': 1.0, 'rot': 0.0, 'alpha': 1.0, 'reveal': 1.0, 'blur': 0.0}
    if mode == 'fade':
        r['alpha'] = lp
    elif mode == 'slide':
        r['tx'], r['ty'], r['alpha'] = slidex * (1.0 - lp), slidey * (1.0 - lp), lp
    elif mode == 'scale':
        s = scalefrom + (1.0 - scalefrom) * lp
        r['sx'] = r['sy'] = s
        r['alpha'] = lp
    elif mode == 'wipe':
        r['reveal'] = lp
    elif mode == 'blur':
        r['blur'], r['alpha'] = blurmax * (1.0 - lp), lp
    elif mode == 'pulse':
        s = 1.0 + pulseamt * math.sin(math.pi * lp)
        r['sx'] = r['sy'] = s
    return r


def smooth(prev, x, k):
    """One-pole smoothing, k 0 = none .. 0.99 = slow."""
    k = clamp(k, 0.0, 0.999)
    return x if prev is None else prev * k + x * (1.0 - k)
