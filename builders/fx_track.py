# fx_track builder - FX_track: tracking looks over a picture (lane F, 27 Oct 2026; doc docs/builds/fx_track.md;
# plan docs/builds/BUILD_PLAN_27OCT.md s2 "FX_track YES, small"). The FX_glitch rack (builders/fx_glitch.py: slots
# table, Cross + Switch per slot, Panic, add/remove/rewire) reused as is (like fx_stylise.py), plus ONE shared tracker
# at rack level, because every module reads the same points (no-bloat rule: plexus TC-01, hud TC-02, analytics TC-04):
#   img_src (picture) / Tracktop (any TOP: person matte, mask) -> trk_src -> det (key at Detw x Deth: bright / dark /
#   motion / bright x motion / alpha / red; det_fb = last frame for motion) ->
#   cells (GPU grid: per cell the key-weighted centroid of pixels over Threshold + their bounds)    } Detector
#   bt (Blob Track TOP, OpenCV, CPU) -> bt_info (Info DAT) -> bt_pack (Script TOP: rows -> texels)  }
#   -> trk_pts (compute: points texture, 4 texels per point, smoothing + velocity against trk_pts_fb).
# Layout of trk_pts: builders/fx_track_lib.py. Modules read it through a Select TOP of '../trk_pts'.
# Module files builders/fx_track_<X>.py (template: docs/builds/fx_glitch.md "Module template").
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fx_track.py').read(), ns)
#   ns['build']('/project1/lab')                          # rack + tracker + 'plexus1' (enabled 1) on first build
#   ns['add']('/project1/lab/FX_track', 'hud', enabled=1)
# Blob Track TOP (T-186): created once, Download type 'nextframe', only cooks while Detector = blobs. ASCII only.
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
with open(os.path.join(HERE, 'fx_glitch.py')) as _fh:
    exec(_fh.read(), globals())                          # the rack functions; they look NAME / _module up at call time
_LIB = {'HERE': HERE}
with open(os.path.join(HERE, 'fx_track_lib.py')) as _fh:
    exec(compile(_fh.read(), os.path.join(HERE, 'fx_track_lib.py'), 'exec'), _LIB)

NAME = 'FX_track'
PREFIX = 'fx_track'
FIRST = ('plexus1', 'plexus')
LABEL = ('FX_track: tracking looks (plexus / hud / analytics) over in1. One shared tracker (cells on the GPU or the '
         'Blob Track TOP) -> trk_pts. In: in1 TOP. Out: out1 TOP. Slots from `slots`; Panic = instant passthrough. '
         'Doc docs/builds/fx_track.md.')
_rack_build = build
_rack_add = add
_rack_layout = _layout

TRACK_PAGES = [
    ('Track', [
        ('Tracksrc', 'Menu', 'picture', {'names': ['picture', 'top'], 'labels': ['The picture (img_src)',
                                                                                 'Track TOP (mask / matte)']}),
        ('Tracktop', 'TOP', '', {'label': 'Track TOP (e.g. CV_person_mask/out2)'}),
        ('Key', 'Menu', 'bright', {'names': [k for k, _l in _LIB['KEYS']], 'labels': [lb for _k, lb in _LIB['KEYS']]}),
        ('Keygain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Key gain'}),
        ('Motiongain', 'Float', 6.0, {'min': 0, 'max': 40, 'label': 'Motion gain'}),
        ('Threshold', 'Float', 0.55, {'min': 0, 'max': 1, 'label': 'Threshold (key)'}),
        ('Detector', 'Menu', 'cells', {'names': [k for k, _l in _LIB['DETECTORS']],
                                       'labels': [lb for _k, lb in _LIB['DETECTORS']]}),
        ('Cellsx', 'Int', 18, {'min': 1, 'max': 64, 'label': 'Cells across'}),
        ('Cellsy', 'Int', 32, {'min': 1, 'max': 64, 'label': 'Cells down'}),
        ('Cellpick', 'Menu', 'peak', {'names': ['peak', 'centroid'], 'labels': [
            'Peak (brightest pixel, hashed ties: organic)', 'Centroid (key-weighted: grid-like on flat areas)']}),
        ('Minfill', 'Float', 0.03, {'min': 0, 'max': 1, 'label': 'Min share of a cell over threshold'}),
        ('Smooth', 'Float', 0.5, {'min': 0, 'max': 0.98, 'label': 'Smooth (kept share per frame)'}),
        ('Maxblobs', 'Int', 32, {'min': 1, 'max': 256, 'label': 'Max blobs'}),
        ('Blobmin', 'Float', 0.02, {'min': 0, 'max': 1, 'label': 'Blob min size'}),
        ('Blobmax', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Blob max size'}),
        ('Blobmove', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Blob max move'}),
        ('Detw', 'Int', 270, {'min': 16, 'max': 1080, 'label': 'Detect width px'}),
        ('Deth', 'Int', 480, {'min': 16, 'max': 1920, 'label': 'Detect height px'}),
        ('Resw', 'Int', 1080, {'min': 64, 'max': 8192, 'label': 'Picture width (plexus lines)'}),
        ('Resh', 'Int', 1920, {'min': 64, 'max': 8192, 'label': 'Picture height (plexus lines)'}),
        ('Outpts', 'Int', 64, {'min': 1, 'max': 4096, 'label': 'Points out (out_pts CHOP, strongest kept)'}),
    ]),
]

T = "parent().par.{}.eval()"
N_EXPR = ("(int(parent().par.Cellsx.eval()) * int(parent().par.Cellsy.eval()) if parent().par.Detector.eval() == "
          "'cells' else int(parent().par.Maxblobs.eval()))")


def n_expr(up=''):
    """N (point count) as an expression from a COMP `up` levels below the rack ('' = the rack, '2' = a module op...).
    Pars only, never a TOP size (T-169 (5): a TOP read would re-cook PX_lines' rows every frame)."""
    return N_EXPR.replace('parent()', 'parent(%s)' % up if up else 'parent()')


DET = """// FX_track det: key at Detw x Deth. in0 track source (bilinear, hold), in1 last det (motion). Out r key, g luma,
// b motion, a 1.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uK;   // key mode, key gain, motion gain, -
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= sz.x || p.y >= sz.y) return;
    vec4 c = texture(sTD2DInputs[0], (vec2(p) + 0.5) / vec2(sz));
    float L = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
    float pl = textureSize(sTD2DInputs[1], 0) == sz ? texelFetch(sTD2DInputs[1], p, 0).g : 0.0;
    float m = abs(L - pl) * uK.z;
    int km = int(uK.x + 0.5);
    float k = km == 0 ? L : km == 1 ? 1.0 - L : km == 2 ? m : km == 3 ? L * m : km == 4 ? c.a : c.r;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(k * uK.y, L, m, 1.0));
}
"""

CELLS = """// FX_track cells: (2 Cx) x Cy. Thread (x, y) = cell (x / 2, y), texel x %% 2: T0 centroid u v (key-weighted, pixels
// with key >= Threshold), fill share, mean key; T1 bounds u0 v0 u1 v1 (no pixel over: cell centre / cell box).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uC;   // threshold, cells x, cells y, pick (0 peak, 1 centroid)
uint lb(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= osz.x || p.y >= osz.y) return;
    ivec2 d = textureSize(sTD2DInputs[0], 0);
    int cxn = max(int(uC.y + 0.5), 1), cyn = max(int(uC.z + 0.5), 1), cx = p.x / 2, cy = p.y;
    int x0 = (cx * d.x) / cxn, x1 = min(((cx + 1) * d.x) / cxn, x0 + %d);
    int y0 = (cy * d.y) / cyn, y1 = min(((cy + 1) * d.y) / cyn, y0 + %d);
    float tot = 0.0, sk = 0.0, n = 0.0, sw = 0.0, sx = 0.0, sy = 0.0;
    ivec2 lo = ivec2(1 << 30), hi = ivec2(-1);
    float bs = -1e30;
    vec2 bp = vec2(0.0);
    for (int j = 0; j < %d; j++) {
        int y = y0 + j;
        if (y >= y1) break;
        for (int i = 0; i < %d; i++) {
            int x = x0 + i;
            if (x >= x1) break;
            float k = texelFetch(sTD2DInputs[0], ivec2(x, y), 0).r;
            tot += 1.0; sk += k;
            if (k >= uC.x) {
                n += 1.0; sw += k; sx += k * (float(x) + 0.5); sy += k * (float(y) + 0.5);
                lo = min(lo, ivec2(x, y)); hi = max(hi, ivec2(x, y));
                float sc = k + 0.02 * float(lb(uint(x) * 73856093u ^ uint(y) * 19349663u)) / 4294967296.0;
                if (sc > bs) { bs = sc; bp = vec2(x, y) + 0.5; }
            }
        }
    }
    vec2 dv = vec2(d);
    vec4 o;
    if ((p.x & 1) == 0)
        o = n > 0.0 ? vec4(uC.w < 0.5 ? bp / dv : vec2(sx, sy) / max(sw, 1e-9) / dv, n / max(tot, 1.0), sk / max(tot, 1.0))
                    : vec4(0.5 * float(x0 + x1) / dv.x, 0.5 * float(y0 + y1) / dv.y, 0.0, sk / max(tot, 1.0));
    else
        o = n > 0.0 ? vec4(vec2(lo) / dv, vec2(hi + 1) / dv) : vec4(float(x0) / dv.x, float(y0) / dv.y,
                                                                    float(x1) / dv.x, float(y1) / dv.y);
    TDImageStoreOutput(0, ivec3(p, 0), o);
}
""" % ((_LIB['CELL_MAX'],) * 4)

PTS = """// FX_track pts: the points texture (layout builders/fx_track_lib.py). in0 cells, in1 bt_pack (row 0 u v w h, row 1
// id age active), in2 last pts (smoothing + velocity when the same id holds the slot).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uG;   // detector, cells x, cells y, N
uniform vec4 uW;   // world half width, half height, now s, smooth
uniform vec4 uP;   // min fill, -, -, -
@FONT@void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= osz.x || p.y >= osz.y) return;
    if (p.y == osz.y - 1) {                               // the font row (fx_track_lib.font_bytes)
        int b = p.x * 4;
        vec4 f = vec4(0.0);
        for (int c = 0; c < 4; c++) if (b + c < 768) f[c] = FT_FONTB[b + c];
        if (p.x == osz.x - 1) f = vec4(uW.z, 0.0, 0.0, 0.0);      // clock: time of this cook
        TDImageStoreOutput(0, ivec3(p, 0), f);
        return;
    }
    int i = p.y * %d + p.x / 4, k = p.x %% 4;
    vec4 o0 = vec4(1e4 + 10.0 * float(i), 1e4, 0.0, 0.0), o1 = vec4(0.0), o2 = vec4(0.0), o3 = vec4(0.0);
    if (i < int(uG.w + 0.5)) {
        bool valid;
        vec2 cen;
        float age = 0.0, idv;
        if (uG.x < 0.5) {
            int cxn = max(int(uG.y + 0.5), 1);
            ivec2 c = ivec2(2 * (i %% cxn), i / cxn);
            vec4 c0 = texelFetch(sTD2DInputs[0], c, 0), c1 = texelFetch(sTD2DInputs[0], c + ivec2(1, 0), 0);
            valid = c0.z >= uP.x && c0.z > 0.0;
            cen = c0.xy; o1 = vec4(c0.xy, c0.w, c0.z); o2 = c1; idv = float(i);
        } else {
            vec4 b0 = texelFetch(sTD2DInputs[1], ivec2(i, 0), 0), b1 = texelFetch(sTD2DInputs[1], ivec2(i, 1), 0);
            valid = b1.z > 0.5;
            cen = b0.xy; o1 = vec4(b0.xy, 1.0, 1.0); o2 = vec4(b0.xy - 0.5 * b0.zw, b0.xy + 0.5 * b0.zw);
            idv = b1.x; age = b1.y;
        }
        vec2 vel = vec2(0.0);
        // self-clocked (the last cook's time in the clock texel): dt 0 = same frame again (keep), > 0.25 s = stale
        bool hp = textureSize(sTD2DInputs[2], 0) == osz;
        float last = hp ? texelFetch(sTD2DInputs[2], osz - 1, 0).x : -1.0;
        float dt = last > 0.0 ? uW.z - last : -1.0;
        if (valid && hp && dt >= 0.0 && dt <= 0.25) {
            ivec2 q = ivec2((i %% %d) * 4, i / %d);
            vec4 p0 = texelFetch(sTD2DInputs[2], q, 0), p1 = texelFetch(sTD2DInputs[2], q + ivec2(1, 0), 0);
            vec4 p3 = texelFetch(sTD2DInputs[2], q + ivec2(3, 0), 0);
            if (p0.w > 0.5 && p3.x == idv) {
                vec2 nc = mix(cen, p1.xy, uW.w);
                vel = dt > 0.0 ? (nc - p1.xy) / dt : p3.zw;
                cen = nc;
                if (uG.x < 0.5) age = p3.y + dt;
            }
        }
        o1.xy = cen;
        if (valid) {
            o0 = vec4((cen - 0.5) * 2.0 * uW.xy, 0.0, 1.0);
            o3 = vec4(idv, age, vel);
        } else o3 = vec4(idv, 0.0, 0.0, 0.0);
    }
    TDImageStoreOutput(0, ivec3(p, 0), k == 0 ? o0 : k == 1 ? o1 : k == 2 ? o2 : o3);
}
""" % (_LIB['FT_SIDE'], _LIB['FT_SIDE'], _LIB['FT_SIDE'])
PTS = PTS.replace('@FONT@', _LIB['FONT_GLSL'])

TRACK_SHADERS = {'det': DET, 'cells': CELLS, 'trk_pts': PTS}
TRACK_NIN = {'det': 2, 'cells': 1, 'trk_pts': 3}

BT_PACK_CB = '''# bt_pack: Blob Track Info DAT rows -> (2, Maxblobs, 4) float32: row 0 u v width height, row 1 id age active 0
# (builders/fx_track.py; mirror fx_track_lib.blob_rows). Cooks only while Detector = blobs pulls it.
import numpy as np

def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tc = scriptOp.parent()
\tn = max(1, int(c.par.Maxblobs.eval()))
\ta = np.zeros((2, n, 4), np.float32)
\td = c.op('bt_info')
\tif d is not None and d.numRows > 1:
\t\th = [x.val for x in d.row(0)]
\t\tix = dict((k, h.index(k)) for k in ('id', 'u', 'v', 'width', 'height', 'age', 'active') if k in h)
\t\tfor i in range(1, min(d.numRows, n + 1)):
\t\t\tr = d.row(i)
\t\t\tv = dict((k, float(r[j].val)) for k, j in ix.items())
\t\t\ta[0, i - 1] = (v.get('u', 0.0), v.get('v', 0.0), v.get('width', 0.0), v.get('height', 0.0))
\t\t\ta[1, i - 1] = (v.get('id', 0.0), v.get('age', 0.0), 1.0 if v.get('active', 1.0) > 0.5 else 0.0, 0.0)
\tscriptOp.copyNumpyArray(a)
'''

# out_pts: the tracked points as a CHOP for anything outside the rack (an effector `pts` row in /project1/effectors,
# FX_glitch misc `arcs` Pointchop via out_uv, any CHOP user). trk_chop (TOP to CHOP of trk_pts, downloadtype nextframe:
# one frame late, no GPU stall; crop full = every row, channels r0 g0 b0 a0 r1 ...) -> this Script CHOP. Cooks only
# while something pulls it. Pure parts (unpack / points) are tested offline (test_fx_track Outputs).
OUT_PTS_CB = '''# out_pts (builders/fx_track.py OUT_PTS_CB): valid tracker points -> samples, channels tx ty tz (T0 world on
# PX_lines' camera plane = TD's default camera view at z 0) u v (centre uv, v up) id strength. Index order; over
# Outpts the strongest Outpts are kept (still in index order: ids / velocities stay put).
import numpy as np

CHANS = ('tx', 'ty', 'tz', 'u', 'v', 'id', 'strength')
SIDE = 64

def unpack(names, vals):
\t"""TOP to CHOP channels (crop full: r0 g0 b0 a0 r1 ..., row 0 = bottom; bare r g b a = one row) + their values
\t(chans x samples: the CHOP's numpy read, not a TOP readback) -> (rows, w, 4)."""
\tvals = np.asarray(vals, dtype=np.float64).reshape(len(names), -1) if len(names) else np.zeros((0, 0))
\tkey = [(int(nm[1:]) if nm[1:].isdigit() else 0, 'rgba'.index(nm[0])) if nm and nm[0] in 'rgba' else None
\t       for nm in names]
\tys = [k[0] for k in key if k is not None]
\ttex = np.zeros(((max(ys) + 1) if ys else 0, vals.shape[1], 4))
\tfor j, k in enumerate(key):
\t\tif k is not None:
\t\t\ttex[k[0], :, k[1]] = vals[j]
\treturn tex

def points(tex, n, cap):
\t"""(rows, w, 4) points texture -> dict channel -> float array (valid points). The last row is the font row."""
\tm = max(0, min(int(n), (tex.shape[0] - 1) * SIDE)) if tex.ndim == 3 and tex.shape[1] >= SIDE * 4 else 0
\ti = np.arange(m)
\ty, x = i // SIDE, (i % SIDE) * 4
\tt0, t1, t3 = tex[y, x], tex[y, x + 1], tex[y, x + 3]
\tok = t0[:, 3] > 0.5
\tidx = np.nonzero(ok)[0]
\tcap = int(cap)
\tif cap > 0 and len(idx) > cap:
\t\tidx = np.sort(idx[np.argsort(-t1[idx, 2], kind='stable')[:cap]])
\treturn {'tx': t0[idx, 0], 'ty': t0[idx, 1], 'tz': t0[idx, 2], 'u': t1[idx, 0], 'v': t1[idx, 1],
\t        'id': t3[idx, 0], 'strength': t1[idx, 2]}

def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tc = scriptOp.parent()
\tsrc = scriptOp.inputs[0] if scriptOp.inputs else None
\tP = None
\tif src is not None and src.numChans:
\t\tchs = src.chans()
\t\ttex = unpack([ch.name for ch in chs], src.numpyArray())
\t\tn = (int(c.par.Cellsx.eval()) * int(c.par.Cellsy.eval()) if c.par.Detector.eval() == 'cells'
\t\t     else int(c.par.Maxblobs.eval()))
\t\tP = points(tex, n, c.par.Outpts.eval())
\tk = len(P['tx']) if P else 0
\tscriptOp.clear()
\tif not k:                                 # no points: NO channels (a CHOP keeps >= 1 sample, live 31550: zeros
\t\treturn                                 # would read as a point at the origin); effectors / arcs then read none
\tscriptOp.numSamples = k
\tfor nm in CHANS:
\t\tscriptOp.appendChan(nm).vals = [float(v) for v in P[nm]]
'''


def track_uniforms():
    return {
        'det': [('uK', ['parent().par.Key.menuIndex', T.format('Keygain'), T.format('Motiongain'), '0'])],
        'cells': [('uC', [T.format('Threshold'), T.format('Cellsx'), T.format('Cellsy'), 'parent().par.Cellpick.menuIndex'])],
        'trk_pts': [('uG', ['parent().par.Detector.menuIndex', T.format('Cellsx'), T.format('Cellsy'), n_expr()]),
                    ('uW', [repr(_LIB['WX']), '%r * %s / max(1, %s)' % (_LIB['WX'], T.format('Resh'), T.format('Resw')),
                            'absTime.seconds', T.format('Smooth')]),
                    ('uP', [T.format('Minfill'), '0', '0', '0'])],
    }


def glsl_text(name):
    with open(os.path.join(HERE, 'glsl', name + '.glsl')) as fh:
        return fh.read()


def _pas(m, name, text, ins, w, h, fmt='rgba32float', extend='hold', filt=None):
    """Compute GLSL TOP with size expressions w / h. <= 3 inputs (T-88)."""
    g = _compute(m, name, text, ins, None, fmt)
    for t in list(g.docked):                              # a new GLSL op docks its own templates (T-115 (5))
        if t.name != name + '_compute' and t.name.startswith(name + '_'):
            _sd(t)
    _expr(g.par.resolutionw, w)
    _expr(g.par.resolutionh, h)
    g.par.inputextenduv = extend
    if filt:
        g.par.inputfiltertype = filt
    return g


H = dict(H, pas=_pas, glsl=glsl_text, lib=_LIB, n_expr=n_expr)


def _comment(c, name, module):
    m = c.op(name)
    if m is not None:
        m.comment = '%s module %s (%s). Pars on its custom pages; pulse Opencontrols for the zkit panel.' % (
            NAME, name, module)


def module_file(module):
    return os.path.join(HERE, '%s_%s.py' % (PREFIX, module))


def _module(module):
    ns = dict(globals())
    with open(module_file(module)) as fh:
        exec(fh.read(), ns)
    return ns


def _logic_dat(c):
    d = c.op('palette_map_logic')
    if d is None:
        d = _mk(c, textDAT, 'palette_map_logic')
    with open(os.path.join(HERE, 'palette_map_logic.py')) as fh:
        t = fh.read()
    if d.text != t:
        d.text = t
    d.comment = 'W1-B palette logic (copy of builders/palette_map_logic.py), read by the modules\' pal Script CHOPs.'
    return d


def _set_menu(par, want):
    names = list(par.menuNames)
    if want in names:
        par.val = want
    return want in names


def tracker(c):
    """The shared tracker stage (idempotent). Returns notes (par names TD did not have)."""
    notes = []
    _pars(c, TRACK_PAGES)
    U = track_uniforms()
    img = _mk(c, switchTOP, 'img_src')                     # the rack (re)wires it; made here so trk_src can point at it
    tt = _mk(c, selectTOP, 'trk_top')
    _expr(tt.par.top, "parent().par.Tracktop.eval() or 'img_src'")
    tt.comment = 'Track TOP (Tracktop), or img_src while empty.'
    ts = _mk(c, switchTOP, 'trk_src')
    ts.inputConnectors[0].connect(img)
    ts.inputConnectors[1].connect(tt)
    _expr(ts.par.index, "1 if parent().par.Tracksrc.eval() == 'top' and parent().par.Tracktop.eval() else 0")
    ts.comment = 'What the tracker looks at: the picture or the Track TOP.'
    blk = _mk(c, constantTOP, 'trk_black')
    blk.par.outputresolution = 'custom'
    blk.par.resolutionw, blk.par.resolutionh = 8, 8
    blk.par.format = 'rgba32float'
    blk.par.colorr = blk.par.colorg = blk.par.colorb = 0
    blk.par.alpha = 0
    blk.comment = 'Reset source of the feedbacks + stand-in for the blob path while Detector = cells.'
    dfb = _mk(c, feedbackTOP, 'det_fb')
    det = _pas(c, 'det', DET, [ts, dfb], T.format('Detw'), T.format('Deth'), 'rgba16float')
    dfb.inputConnectors[0].connect(blk)                   # reset source; the loop goes through par.top (T-168 (4))
    dfb.par.top = 'det'
    _uniforms(det, U['det'])
    det.comment = 'Key at Detw x Deth: r key, g luma, b motion (vs det_fb).'
    cells = _pas(c, 'cells', CELLS, [det], '2 * int(%s)' % T.format('Cellsx'), T.format('Cellsy'), 'rgba32float',
                 'hold', 'nearest')
    _uniforms(cells, U['cells'])
    cells.comment = 'Per cell: key-weighted centroid of pixels over Threshold + their bounds (GPU).'
    bt = c.op('bt')
    if bt is None:                                        # T-186: one create, nothing else on it in this step
        bt = c.create(blobtrackTOP, 'bt')
        bt.viewer = False
    bt.inputConnectors[0].connect(det)
    for pn, val in (('downloadtype', 'nextframe'), ('drawblobs', False), ('reviveblobs', True)):
        p = getattr(bt.par, pn, None)
        if p is None:
            notes.append('bt.' + pn)
        elif pn == 'downloadtype':
            _set_menu(p, val) or notes.append('bt.downloadtype=' + val)
        else:
            p.val = val
    p = getattr(bt.par, 'monosource', None)
    if p is not None and not _set_menu(p, 'red'):
        notes.append('bt.monosource red: %s' % list(p.menuNames))
    for pn, e in (('threshold', 'Threshold'), ('minblobsize', 'Blobmin'), ('maxblobsize', 'Blobmax'),
                  ('maxmovedistance', 'Blobmove')):
        if getattr(bt.par, pn, None) is not None:
            _expr(getattr(bt.par, pn), T.format(e))
        else:
            notes.append('bt.' + pn)
    bt.comment = 'Blob Track TOP (OpenCV, CPU, ids). Cooks only while Detector = blobs (bt_sel pulls bt_pack).'
    bi = _mk(c, infoDAT, 'bt_info')
    bi.par.op = 'bt'
    bi.comment = 'Blob Track rows: id u v width height ... age.'
    bp = _mk(c, scriptTOP, 'bt_pack')
    bcb = c.op('bt_pack_callbacks') or _mk(c, textDAT, 'bt_pack_callbacks')
    if bcb.text != BT_PACK_CB:
        bcb.text = BT_PACK_CB
    bcb.dock = bp
    bp.par.callbacks = bcb.name
    if getattr(bp.par, 'format', None) is not None:
        bp.par.format = 'rgba32float'
    bp.comment = 'Blob rows -> texels: row 0 u v w h, row 1 id age active.'
    bs = _mk(c, switchTOP, 'bt_sel')
    bs.inputConnectors[0].connect(blk)
    bs.inputConnectors[1].connect(bp)
    _expr(bs.par.index, "1 if parent().par.Detector.eval() == 'blobs' else 0")
    bs.comment = 'Blob path only while Detector = blobs (else nothing of it cooks).'
    pfb = _mk(c, feedbackTOP, 'trk_pts_fb')
    pts = _pas(c, 'trk_pts', PTS, [cells, bs, pfb], str(_LIB['FT_SIDE'] * _LIB['FT_STRIDE']),
               'max(1, (%s + %d) // %d) + 1' % (n_expr(), _LIB['FT_SIDE'] - 1, _LIB['FT_SIDE']), 'rgba32float', 'hold',
               'nearest')
    pfb.inputConnectors[0].connect(blk)
    pfb.par.top = 'trk_pts'
    _uniforms(pts, U['trk_pts'])
    pts.comment = 'Points: 4 texels each (world xyz valid / centre strength fill / box / id age velocity); last row = font.'
    notes += outputs(c)
    return notes


def outputs(c):
    """trk_chop -> out_pts (+ out_uv): the tracked points as CHOPs for effectors / arcs / any CHOP user (idempotent).
    Cook only while pulled. Returns notes (par names TD did not have)."""
    notes = []
    pts = c.op('trk_pts')
    tc = _mk(c, toptoCHOP, 'trk_chop')
    tc.par.top = 'trk_pts'
    for pn, val in (('downloadtype', 'nextframe'), ('crop', 'full'), ('outputcolorspace', 'passthrough')):
        p = getattr(tc.par, pn, None)
        if p is None or not _set_menu(p, val):
            notes.append('trk_chop.%s=%s' % (pn, val))
    tc.comment = 'trk_pts as channels (r0 g0 b0 a0 r1 ...), one frame late (nextframe: no GPU stall). Cooks when pulled.'
    op_ = _mk(c, scriptCHOP, 'out_pts')
    cb = c.op('out_pts_callbacks') or _mk(c, textDAT, 'out_pts_callbacks')
    if cb.text != OUT_PTS_CB:
        cb.text = OUT_PTS_CB
    cb.dock = op_
    op_.par.callbacks = cb.name
    op_.inputConnectors[0].connect(tc)
    op_.comment = ('Tracked points out: samples = valid points (<= Outpts, strongest kept), channels tx ty tz (world, '
                   'PX_lines plane) u v id strength. Effector: add(\'pts\', ref=<this>). Doc fx_track.md "Outputs".')
    uv = _mk(c, selectCHOP, 'out_uv')
    uv.par.chops = 'out_pts'
    uv.par.channames = 'u v'
    uv.comment = 'u v only (0..1, v up): FX_glitch misc arcs Pointchop (Pointspace uv).'
    if pts is None:
        notes.append('no trk_pts')
    return notes


EFF_BUILDER = os.path.join(HERE, 'effectors.py')
MISC_FILE = os.path.join(HERE, 'fx_glitch_misc.py')
ARCS_PRESET = 'tracked arcs'
# The 'tracked arcs' look for FX_glitch misc (full state = misc's page defaults _D + these; zkit's 8 preset slots are
# all taken by misc's own looks, so link_fx applies it): plasma arcs between tracked people / blobs (pairs within
# Reach, closer = brighter). Pointchop (op par) is set by link_fx, not stored here.
ARCS_LOOK = dict(Type=8, Rate=16.0, Jag=0.25, Width=2.0, Glow=2.5, Colr=0.45, Colg=0.8, Colb=1.0, Pointspace=0,
                 Arcmode=1, Reach=0.22, Arcfalloff=1.2, Maxarcs=24)


def link_fx(comp_path='/project1/lab/FX_track', effector='track', tags='track', eff_enabled=True,
            glitch='/project1/lab/FX_glitch', misc='misc1', look=True, enable_slot=None):
    """One click: FX_track's points -> (1) a `pts` effector row `effector` in /project1/effectors (ref = out_pts; any
    consumer with Effon + Effselect `all` / `#track` / the name is pushed by the tracked points) and (2) FX_glitch
    misc slot `misc` Pointchop = out_uv (Pointspace uv); look True also applies the full-state look ARCS_LOOK
    'tracked arcs' (Type arcs, pairs).
    enable_slot 1 / 0 sets the misc slot's enabled cell (None = leave). Pass effector=None / glitch=None to skip a part.
    Idempotent (an existing row of that name keeps its values; only ref is re-pointed). Returns what it did."""
    c = op(comp_path)
    if c is None:
        return {'error': 'no %s' % comp_path}
    res = {'notes': outputs(c), 'out_pts': c.op('out_pts').path, 'out_uv': c.op('out_uv').path}
    if effector:
        ns = dict(globals())
        with open(EFF_BUILDER) as fh:
            exec(fh.read(), ns)
        R = ns['_rt']()
        have = [r for r in R.rows() if r['name'] == effector]
        if have:
            if have[0].get('ref') != res['out_pts']:
                R.set_value(effector, 'ref', res['out_pts'])
            res['effector'] = effector
        else:
            res['effector'] = R.add('pts', effector, tags, res['out_pts'])
        R.enable(res['effector'], bool(eff_enabled))
    if glitch:
        g = op(glitch)
        m = g.op(misc) if g is not None else None
        if m is None or getattr(m.par, 'Pointchop', None) is None:
            res['arcs'] = 'no misc slot %s/%s with Pointchop (FX_glitch upgrade first)' % (glitch, misc)
        else:
            m.par.Pointchop = res['out_uv']
            if look:
                ns = dict(globals())
                with open(MISC_FILE) as fh:
                    exec(fh.read(), ns)
                vals = dict(ns['_D'], **ARCS_LOOK)
                bad = []
                for k, v in vals.items():
                    p = getattr(m.par, k, None)
                    if p is None:
                        bad.append(k)
                    elif p.isMenu:
                        p.menuIndex = int(v)
                    else:
                        p.val = v
                res['look'] = ARCS_PRESET
                if bad:
                    res['look_missing'] = bad
            m.par.Pointspace = 'uv'
            t = g.op('slots')
            if enable_slot is not None and t is not None and t.row(misc) is not None:
                t[misc, 'enabled'] = int(bool(enable_slot))
            res['arcs'] = m.path
    return res


def build(parent_path='/project1/lab', panel=True):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    if c.op('slots') is None:                             # first row = the pilot, on
        t = _mk(c, tableDAT, 'slots')
        t.clear()
        t.appendRow(COLS)
        t.appendRow([FIRST[0], FIRST[1], 1, 1, 1])
    _logic_dat(c)
    notes = tracker(c)
    res = _rack_build(parent_path, panel)
    c.comment = LABEL
    for r in _rows(c):
        _comment(c, r['name'], r['module'])
    res['notes'] = notes
    return res


def _layout(c):
    """The rack layout plus the tracker stage."""
    names = plan_chain(_rows(c))
    chain = []
    for n in names:
        chain += [n, n + '_mix', n + '_slot']
    stages = [
        {'title': 'Rack', 'role': 'control', 'ops': ['slots', 'palette_map_logic'],
         'body': 'slots: name module enabled order mix (enabled/mix live). palette_map_logic: W1-B palette for modules.'},
        {'title': '1 Input', 'role': 'input', 'ops': ['in1', 'test_clip', 'img_src'],
         'body': 'in1 TOP or the stored webcam clip (Input: auto = in1 when wired).'},
        {'title': '2 Tracker', 'role': 'process',
         'ops': ['trk_top', 'trk_src', 'trk_black', 'det_fb', 'det', 'det_compute', 'cells', 'cells_compute', 'bt',
                 'bt_info', 'bt_pack', 'bt_pack_callbacks', 'bt_sel', 'trk_pts_fb', 'trk_pts', 'trk_pts_compute'],
         'body': 'Key (det) -> cells (GPU) or Blob Track TOP -> trk_pts (4 texels per point). Modules read trk_pts.'},
        {'title': '2b Points out', 'role': 'output', 'ops': ['trk_chop', 'out_pts', 'out_pts_callbacks', 'out_uv'],
         'body': 'trk_pts -> CHOP (nextframe) -> out_pts (tx ty tz u v id strength) / out_uv: effector pts row, misc arcs.'},
        {'title': '3 Slots', 'role': 'process', 'ops': [n for n in chain if c.op(n) is not None],
         'body': 'Per slot: module COMP -> _mix (Cross) -> _slot (Switch 0 bypass / 1 module / 2 mix).'},
        {'title': '4 Out', 'role': 'output', 'ops': ['panic', 'out1'], 'body': 'Panic = instant passthrough of the rack.'},
    ]
    for s in stages:
        s['ops'] = [n for n in s['ops'] if c.op(n) is not None]
    stages = [s for s in stages if s['ops']]
    return op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='rows')


def add(comp_path, module, name=None, order=None, enabled=0, mix=1, panel=True):
    c = op(comp_path)
    _logic_dat(c)
    res = _rack_add(comp_path, module, name=name, order=order, enabled=enabled, mix=mix, panel=panel)
    _comment(c, res['added'], module)
    return res
