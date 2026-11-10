"""urdu_render: shape + rasterise Urdu / Arabic / Latin words OUTSIDE TouchDesigner (HarfBuzz hb-view + hb-shape),
then pack them into one atlas PNG with alpha + a metrics JSON. The urdu_type COMP (/project1/lab/BJ_urdu_type) only
loads the atlas (Movie File In TOP) and lays the words out from the JSON: no Text TOP with an Urdu font, no
evalTextSize, no numpyArray in TD (T-74, T-76: both crashed TD 2025.31550 on this Mac).

Run (system Python, stdlib only; the TD runtime starts it as a child process, never in TD's own interpreter):
    python3 -I builders/urdu_render.py <job.json>
job.json = {"cache": dir, "atlas": key, "margin_em": 0.6, "items": [{"text", "font", "fontfile", "typeface",
            "weight", "size", "lang", "dir", "key"}...]}
Writes <cache>/w_<key>.png + w_<key>.json per word (cached across jobs) and <cache>/a_<atlas>.png + a_<atlas>.json
(written last, atomically: the TD side polls for that JSON). Pure ASCII source.

Geometry (probed 26 Oct with HarfBuzz 14.6.0): `hb-view --logical --margin=M` draws the logical box (advance x
ascent+descent) M px inside the canvas and does NOT clip ink outside it (Nastaliq tails land in the margin), so the
canvas centre = the advance-box centre horizontally and the line-box centre vertically, and the baseline sits at
M + ascent*size/upem from the top. A word whose ink touches the outer 2 px is re-rendered with twice the margin.
"""
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import urdu_type_logic as L  # noqa: E402

HB_VIEW = '/opt/homebrew/bin/hb-view'
HB_SHAPE = L.HB_SHAPE
RENDER_VERSION = 2
ATLAS_MAXW = 4096
GUTTER = 4


# ---------------------------------------------------------------- PNG (stdlib only)

def png_read(path):
    """(w, h, channels, rows) for an 8-bit non-interlaced PNG; rows = list of bytes, top row first."""
    with open(path, 'rb') as f:
        data = f.read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG')
    pos, idat, hdr = 8, [], None
    while pos < len(data):
        ln, typ = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        if typ == b'IHDR':
            hdr = struct.unpack('>IIBBBBB', body)
        elif typ == b'IDAT':
            idat.append(body)
        elif typ == b'IEND':
            break
        pos += 12 + ln
    w, h, depth, ctype, _, _, inter = hdr
    if depth != 8 or inter != 0:
        raise ValueError('only 8-bit non-interlaced PNG')
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b''.join(idat))
    stride = w * ch
    rows, prev = [], bytearray(stride)
    p = 0
    for _ in range(h):
        ft = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        if ft == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        rows.append(bytes(line))
        prev = line
    return w, h, ch, rows


def alpha_rows(w, h, ch, rows):
    """Alpha plane (list of bytes rows, top first)."""
    if ch == 4:
        return [r[3::4] for r in rows]
    if ch == 2:
        return [r[1::2] for r in rows]
    return [r for r in rows] if ch == 1 else [bytes(w) for _ in rows]


def png_write_alpha(path, w, h, alpha):
    """RGBA PNG, white RGB + the given alpha plane (rows top first). Straight alpha (TD premultiplies on load)."""
    raw = bytearray()
    for r in alpha:
        raw.append(0)
        line = bytearray(w * 4)
        line[0::4] = b'\xff' * w
        line[1::4] = b'\xff' * w
        line[2::4] = b'\xff' * w
        line[3::4] = r
        raw += line

    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    out = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + \
        chunk(b'IDAT', zlib.compress(bytes(raw), 3)) + chunk(b'IEND', b'')
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(out)
    os.replace(tmp, path)


def ink_box_px(alpha, w, h, thr=5, edge=2):
    """Ink bbox in image pixels (x0, y0top, x1, y1top exclusive) + count of ink pixels on the outer `edge` px; None if
    empty."""
    x0, x1, y0, y1 = w, -1, h, -1
    e = 0
    for y, r in enumerate(alpha):
        hit = [i for i, v in enumerate(r) if v > thr]
        if not hit:
            continue
        y0, y1 = min(y0, y), max(y1, y)
        x0, x1 = min(x0, hit[0]), max(x1, hit[-1])
        if y < edge or y >= h - edge:
            e += len(hit)
        else:
            e += sum(1 for i in hit if i < edge or i >= w - edge)
    if x1 < 0:
        return None, 0
    return (x0, y0, x1 + 1, y1 + 1), e


# ---------------------------------------------------------------- keys + fonts

def word_key(item, margin_em):
    """Content hash of everything that changes a word raster (the TD side computes the same key)."""
    return L.render_key(item, margin_em, RENDER_VERSION)


def resolve_font(item):
    """(path, face) for an item: explicit file, Nastaliq system .ttc (Bold = face + 2), or a name lookup."""
    ff = L.hb_font_for(item.get('font', ''), item.get('fontfile', ''))
    if ff is None:
        return None
    path, face = ff
    if item.get('typeface') == 'Bold' and path == L.NASTALIQ_TTC and face < 2:
        face += 2
    return path, face


def _base_cmd(exe, item, path, face):
    cmd = [exe, '--font-file=' + path, '--face-index={}'.format(face), '--font-size={}'.format(int(round(item['size']))),
           '--direction=' + ('rtl' if item.get('dir') == 'rtl' else 'ltr')]
    if item.get('lang'):
        cmd.append('--language=' + item['lang'])
    wt = int(item.get('weight') or 0)
    if wt > 0:
        cmd.append('--variations=wght={}'.format(wt))
    return cmd


def render_word(item, cache, margin_em=0.6, hb_view=HB_VIEW, hb_shape=HB_SHAPE, tries=3):
    """Render one word to <cache>/w_<key>.png + .json (skipped when both exist). Returns the metrics dict."""
    key = item.get('key') or word_key(item, margin_em)
    jp = os.path.join(cache, 'w_%s.json' % key)
    pp = os.path.join(cache, 'w_%s.png' % key)
    if os.path.isfile(jp) and os.path.isfile(pp):
        with open(jp, encoding='utf-8') as f:
            return json.load(f)
    size = float(item['size'])
    met = None
    ff = resolve_font(item)
    res = {'key': key, 'text': item['text'], 'size': size, 'dir': item.get('dir', 'ltr'), 'png': pp, 'ok': False}
    if ff is None or not os.path.isfile(hb_view):
        res['error'] = 'no font file' if ff is None else 'hb-view missing'
        return res
    path, face = ff
    met = L.font_metrics(path, face)
    res['font_file'], res['face'] = path, face
    m = int(round(margin_em * size))
    for _ in range(tries):
        cmd = _base_cmd(hb_view, item, path, face) + ['--logical', '--margin={}'.format(m), '--background=none',
                                                       '--foreground=FFFFFF', '-o', pp, '--text=' + item['text']]
        r = subprocess.run(cmd, capture_output=True, timeout=20)
        if r.returncode != 0 or not os.path.isfile(pp):
            res['error'] = 'hb-view failed: ' + r.stderr.decode('utf-8', 'replace')[:200]
            return res
        w, h, ch, rows = png_read(pp)
        al = alpha_rows(w, h, ch, rows)
        box, edge = ink_box_px(al, w, h)
        if edge == 0:
            break
        m *= 2
    res.update({'w': w, 'h': h, 'margin': m, 'edge': edge})
    s = size / float(met['upem']) if met else size / 1000.0
    asc = met['ascent'] * s if met else 0.8 * size
    res['adv'] = float(w - 2 * m)
    res['lineh'] = float(h - 2 * m)
    res['baseline_top'] = m + asc            # baseline, px from the PNG's top edge
    cx, cy = w / 2.0, h / 2.0
    if box is None:
        res.update({'x0': 0.0, 'x1': 0.0, 'y0': 0.0, 'y1': 0.0})
    else:                                     # ink box relative to the tile centre, x right, y UP
        res.update({'x0': box[0] - cx, 'x1': box[2] - cx, 'y0': cy - box[3], 'y1': cy - box[1]})
    res['iw'] = res['x1'] - res['x0']
    res['ih'] = res['y1'] - res['y0']
    # HarfBuzz glyph clusters (glyph ids, advances, offsets, extents in px at this size; visual order)
    glyphs = []
    if os.path.isfile(hb_shape):
        cmd = _base_cmd(hb_shape, item, path, face) + ['--output-format=json', '--show-extents', '--no-glyph-names',
                                                        '--text=' + item['text']]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=10)
            glyphs = json.loads(r.stdout.decode('utf-8'))
        except Exception:
            glyphs = []
    res['glyphs'] = len(glyphs)
    res['notdef'] = sum(1 for g in glyphs if g.get('g') in (0, '0'))
    res['hb_adv'] = float(sum(g.get('ax', 0) for g in glyphs))
    res['clusters'] = L.clusters_from_hb(glyphs)
    res['ok'] = True
    tmp = jp + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=True)
    os.replace(tmp, jp)
    return res


# ---------------------------------------------------------------- atlas

def pack(sizes, maxw=ATLAS_MAXW, gutter=GUTTER):
    """Shelf packing: list of (w, h) -> list of (x, ytop) + atlas (W, H). Deterministic, order kept."""
    x = y = shelf = 0
    pos = []
    W = 0
    for w, h in sizes:
        if x > 0 and x + w > maxw:
            y += shelf + gutter
            x = shelf = 0
        pos.append((x, y))
        x += w + gutter
        W = max(W, x - gutter)
        shelf = max(shelf, h)
    H = y + shelf
    return pos, (max(W, 8), max(H, 8))


def build_atlas(words, cache, akey):
    """Paste every word PNG (alpha) into one atlas. Rects in the JSON: x, y bottom-left (TD texture, y up), w, h."""
    uniq = {}
    for w in words:                           # a repeated word is packed once
        if w.get('ok') and w['key'] not in uniq:
            uniq[w['key']] = w
    ok = list(uniq.values())
    pos, (W, H) = pack([(w['w'], w['h']) for w in ok])
    plane = [bytearray(W) for _ in range(H)]
    rects = {}
    for wd, (x, yt) in zip(ok, pos):
        ww, hh, ch, rows = png_read(wd['png'])
        for r, line in enumerate(alpha_rows(ww, hh, ch, rows)):
            plane[yt + r][x:x + ww] = line
        rects[wd['key']] = list(L.tex_rect(x, yt, ww, hh, H))
    for w in words:
        if w.get('ok'):
            w['rect'] = rects[w['key']]
    ap = os.path.join(cache, 'a_%s.png' % akey)
    png_write_alpha(ap, W, H, [bytes(r) for r in plane])
    return ap, W, H


def run_job(job):
    t0 = time.perf_counter()
    cache = job['cache']
    os.makedirs(cache, exist_ok=True)
    me = float(job.get('margin_em', 0.6))
    words = [render_word(it, cache, me) for it in job['items']]
    akey = job['atlas']
    ap, W, H = build_atlas(words, cache, akey)
    out = {'atlas': ap, 'w': W, 'h': H, 'words': words, 'version': RENDER_VERSION,
           'ms': round((time.perf_counter() - t0) * 1000.0, 1)}
    jp = os.path.join(cache, 'a_%s.json' % akey)
    tmp = jp + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=True)
    os.replace(tmp, jp)                      # last write: the TD side waits for this file
    return out


def main(argv):
    with open(argv[1], encoding='utf-8') as f:
        job = json.load(f)
    try:
        out = run_job(job)
        print(json.dumps({'ok': True, 'words': len(out['words']), 'ms': out['ms']}))
    except Exception as e:                   # the TD side reads the error file and keeps the old atlas
        ep = os.path.join(job['cache'], 'a_%s.err' % job['atlas'])
        with open(ep, 'w', encoding='utf-8') as f:
            f.write(repr(e))
        print(json.dumps({'ok': False, 'error': repr(e)}))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
