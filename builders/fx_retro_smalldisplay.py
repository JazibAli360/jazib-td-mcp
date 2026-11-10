# fx_retro_smalldisplay - FX_retro module 'smalldisplay' (FX2 AV-40 small displays; FX0 row 78).
# Module file = pages / presets + shader_texts + build(m, H, Lg) (template: docs/builds/fx_glitch.md; rack:
# builders/fx_retro.py). Six displays, all from one `state` compute pass (rgba32float, in place, one texel per dot or
# character cell; T-110 (5)) and one `fx` render pass at the input size:
#   lcd       - dot-matrix LCD: Levels grey (or RGB stripes), asymmetric response (Rise / Fall s: the Game Boy smear),
#               pixel gap and the reflective drop shadow;
#   vfd       - vacuum fluorescent dots: cyan-green glow into the neighbours, faint unlit dots, fine grid mesh, flicker;
#   nixie     - orange neon numerals (stroke SDFs) in glass tubes, unlit cathode stack, hex anode mesh, crossfade;
#   flipdot   - bistable discs that rotate over Fliptime (scan all / columns / rows / random over Sweep s);
#   splitflap - character cards flapping through the alphabet one card per Flapstep s until they reach the target;
#   eink      - grey levels with ghosting partial updates (Updatehz, Ghost) and a full refresh flash (Refresh pulse /
#               Refreshperiod): inverted -> black -> white -> new picture.
# Content: image (dot displays) / text / 12-hour clock / value (Format) -> `codes` Script CHOP (texture buffer).
# State restarts after a stall > 0.25 s (per-texel last-update time, buffer 1) or a Display / size change.
# Amount 0 = exact passthrough. ASCII only.

MODULE = 'smalldisplay'


def pages(Lg):
    return [
        ('Display', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Display', 'Menu', 'lcd', {'names': Lg['DISPLAYS'], 'labels': Lg['DISPLAY_LABELS']}),
            ('Content', 'Menu', 'image', {'names': Lg['CONTENTS'],
                                          'labels': ['Image (dot displays)', 'Text', 'Clock (12 h)', 'Value']}),
            ('Dotsize', 'Float', 12.0, {'min': 2, 'max': 64, 'label': 'Dot pitch (px)'}),
            ('Columns', 'Int', 4, {'min': 1, 'max': 40, 'label': 'Character columns'}),
            ('Rows', 'Int', 1, {'min': 1, 'max': 20, 'label': 'Character rows'}),
            ('Cellaspect', 'Float', 1.8, {'min': 0.5, 'max': 4, 'label': 'Cell aspect (h / w)'}),
            ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Threshold (1-bit)'}),
            ('Levels', 'Int', 4, {'min': 2, 'max': 16, 'label': 'Grey levels'}),
            ('Invert', 'Toggle', False, {'label': 'Invert'}),
            ('Contrast', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Contrast'}),
            ('Brightness', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Brightness'}),
            ('Lcdcolour', 'Toggle', False, {'label': 'LCD RGB stripes'}),
        ]),
        ('Look', [
            ('Gap', 'Float', 0.12, {'min': 0, 'max': 0.9, 'label': 'Gap'}),
            ('Glow', 'Float', 0.35, {'min': 0, 'max': 2, 'label': 'Glow'}),
            ('Mesh', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Mesh / grid'}),
            ('Meshpitch', 'Int', 4, {'min': 2, 'max': 32, 'label': 'Mesh pitch (px)'}),
            ('Shadow', 'Float', 3.0, {'min': 0, 'max': 16, 'label': 'LCD shadow (px)'}),
            ('Shadowamt', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'LCD shadow amount'}),
            ('Cathodes', 'Float', 0.12, {'min': 0, 'max': 1, 'label': 'Nixie unlit cathodes'}),
            ('Stroke', 'Float', 0.06, {'min': 0.01, 'max': 0.2, 'label': 'Nixie stroke'}),
            ('Flicker', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Flicker'}),
            ('Smooth', 'Toggle', True, {'label': 'Smooth glyphs'}),
        ]),
        ('Motion', [
            ('Rise', 'Float', 0.08, {'min': 0, 'max': 2, 'label': 'LCD rise s'}),
            ('Fall', 'Float', 0.25, {'min': 0, 'max': 2, 'label': 'LCD fall s'}),
            ('Fliptime', 'Float', 0.12, {'min': 0.01, 'max': 2, 'label': 'Flip time s'}),
            ('Flipscan', 'Menu', 'columns', {'names': ['all', 'columns', 'rows', 'random'],
                                             'labels': ['All at once', 'Columns', 'Rows', 'Random']}),
            ('Sweep', 'Float', 0.6, {'min': 0, 'max': 5, 'label': 'Scan sweep s'}),
            ('Flapstep', 'Float', 0.06, {'min': 0.01, 'max': 1, 'label': 'Flap step s'}),
            ('Fade', 'Float', 0.15, {'min': 0, 'max': 2, 'label': 'Nixie fade s'}),
            ('Updatehz', 'Float', 4.0, {'min': 0, 'max': 30, 'label': 'E-ink partial updates Hz'}),
            ('Ghost', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'E-ink ghost'}),
            ('Flashtime', 'Float', 1.2, {'min': 0.1, 'max': 5, 'label': 'E-ink refresh flash s'}),
            ('Refreshperiod', 'Float', 0.0, {'min': 0, 'max': 120, 'label': 'E-ink auto refresh s (0 off)'}),
            ('Refresh', 'Pulse', None, {'label': 'E-ink full refresh'}),
            ('Refreshtime', 'Float', -100.0, {'min': -100, 'max': 0, 'label': 'Last refresh (absTime s)'}),
            ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ]),
        ('Colours', [
            ('Oncolour', 'RGB', (0.06, 0.22, 0.06), {'label': 'On (lit / ink / dark pixel)'}),
            ('Offcolour', 'RGB', (0.55, 0.67, 0.06), {'label': 'Off (panel / paper / card)'}),
            ('Bgcolour', 'RGB', (0.6, 0.72, 0.1), {'label': 'Background / gap'}),
        ]),
        ('Content', [
            ('Text', 'Str', 'RETRO', {'label': 'Text (| = new line)'}),
            ('Textdat', 'DAT', '', {'label': 'Text DAT (rows = lines)'}),
            ('Value', 'Float', 0.0, {'min': 0, 'max': 100, 'label': 'Value'}),
            ('Format', 'Str', '{:.1f}', {'label': 'Value format (Python)'}),
            ('Align', 'Menu', 'right', {'names': ['left', 'centre', 'right'], 'labels': ['Left', 'Centre', 'Right']}),
        ]),
    ]


PANEL_PAGES = ['Display', 'Look', 'Motion', 'Colours']


def presets(Lg):
    D = Lg['DISPLAYS']
    C = Lg['CONTENTS']
    base = {'Amount': 1.0, 'Invert': 0, 'Contrast': 1.0, 'Brightness': 0.0, 'Lcdcolour': 0, 'Flicker': 0.05,
            'Smooth': 1, 'Seed': 1}

    def look(disp, content, on, off, bg, **kw):
        d = dict(base, Display=D.index(disp), Content=C.index(content), **kw)
        for n, c in (('Oncolour', on), ('Offcolour', off), ('Bgcolour', bg)):
            d.update({n + 'r': c[0], n + 'g': c[1], n + 'b': c[2]})
        return d
    return [
        (1, 'game boy lcd', look('lcd', 'image', (0.06, 0.22, 0.06), (0.55, 0.67, 0.06), (0.6, 0.72, 0.1),
                                 Dotsize=8.0, Levels=4, Gap=0.12, Shadow=3.0, Shadowamt=0.25, Rise=0.08, Fall=0.25)),
        (2, 'vfd', look('vfd', 'image', (0.25, 1.0, 0.85), (0.03, 0.08, 0.07), (0.01, 0.02, 0.02),
                        Dotsize=10.0, Levels=2, Threshold=0.45, Gap=0.25, Glow=0.4, Mesh=0.3, Meshpitch=4)),
        (3, 'nixie clock', look('nixie', 'clock', (1.0, 0.42, 0.08), (0.08, 0.06, 0.05), (0.0, 0.0, 0.0),
                                Columns=8, Rows=1, Cellaspect=1.9, Gap=0.1, Glow=0.5, Mesh=0.2, Meshpitch=6,
                                Cathodes=0.12, Stroke=0.06, Fade=0.15)),
        (4, 'flip-dot', look('flipdot', 'image', (1.0, 0.9, 0.1), (0.05, 0.05, 0.05), (0.0, 0.0, 0.0),
                             Dotsize=18.0, Threshold=0.5, Gap=0.08, Fliptime=0.12, Flipscan=1, Sweep=0.6)),
        (5, 'split-flap', look('splitflap', 'text', (0.95, 0.95, 0.9), (0.1, 0.1, 0.11), (0.02, 0.02, 0.02),
                               Columns=8, Rows=6, Cellaspect=1.4, Gap=0.08, Flapstep=0.06)),
        (6, 'e-ink', look('eink', 'image', (0.12, 0.12, 0.14), (0.86, 0.85, 0.8), (0.86, 0.85, 0.8),
                          Dotsize=3.0, Levels=16, Gap=0.0, Updatehz=4.0, Ghost=0.3, Flashtime=1.2,
                          Refreshperiod=0.0)),
    ]


STATE = """// FX_retro smalldisplay state: one texel per dot / character cell, rgba32float in place (T-110 (5)), 2 buffers:
// buffer 0 = the display state (w = display id + 1; anything else = re-init), buffer 1 x = this texel's last update
// time, so a second cook in the same frame (readbacks, T-116 (4)) is a no-op (dt 0) and a gap > 0.25 s re-inits.
// in0 = picture.
layout (local_size_x = 8, local_size_y = 8) in;
%LIB%
uniform samplerBuffer uCodes;
uniform vec4 uA;   // display (0 lcd 1 vfd 2 nixie 3 flipdot 4 splitflap 5 eink), image content, threshold, levels
uniform vec4 uB;   // GW, GH, dot size px, text cols (dot displays: GW / 8)
uniform vec4 uC;   // rise, fall, flip time, flip scan (0 all 1 columns 2 rows 3 random)
uniform vec4 uD;   // sweep, flap step, -, seed
uniform vec4 uE;   // refresh time, flash time, update Hz, ghost
uniform vec4 uF;   // contrast, brightness, invert, lcd rgb
uniform vec4 uT;   // now (absTime.seconds)
int codeAt(int i) { return i < textureSize(uCodes) ? int(texelFetch(uCodes, i).r + 0.5) : 0; }
void main() {
    ivec2 g = ivec2(gl_GlobalInvocationID.xy);               // g.y counted from the TOP
    ivec2 gs = ivec2(uB.xy + 0.5);
    if (g.x >= gs.x || g.y >= gs.y) return;
    ivec2 res = textureSize(sTD2DInputs[0], 0);
    float now = uT.x;
    int disp = int(uA.x + 0.5);
    float id = float(disp + 1);
    vec4 s = TDImageLoadOutput(0, ivec3(g, 0));
    float gap = now - TDImageLoadOutput(1, ivec3(g, 0)).x;
    bool init = s.w != id || gap > 0.25 || gap < 0.0;
    float dt = clamp(gap, 0.0, 0.25);
    vec3 tgt = vec3(0.0);
    int code = 0;
    if (disp == 2 || disp == 4) {
        code = codeAt(g.y * gs.x + g.x);                     // cell displays: one code per cell
    } else if (uA.y > 0.5) {                                 // dot displays, image: box of the dot (2x2 bilinear)
        float ds = max(uB.z, 1.0);
        vec3 acc = vec3(0.0);
        for (int k = 0; k < 4; k++) {
            vec2 o = vec2(float(k & 1) + 0.5, float(k >> 1) + 0.5) * 0.5 * ds;
            vec2 p = vec2(float(g.x) * ds + o.x, float(res.y) - (float(g.y) * ds + o.y));
            acc += straight(textureLod(sTD2DInputs[0], clamp(p, vec2(0.5), vec2(res) - 0.5) / vec2(res), 0.0));
        }
        tgt = clamp((acc * 0.25 - 0.5) * uF.x + 0.5 + uF.y, 0.0, 1.0);
        if (uF.z > 0.5) tgt = 1.0 - tgt;
    } else {                                                 // dot displays, text: 8x8 font per character
        int tc = max(int(uB.w + 0.5), 1);
        int gi = codeAt((g.y / 8) * tc + g.x / 8) - 1;
        bool on = (g.x / 8) < tc && fontBit(gi, g.x % 8, g.y % 8);
        tgt = vec3(on ? 1.0 : 0.0);
        if (uF.z > 0.5) tgt = 1.0 - tgt;
    }
    float lum = luma(tgt);
    vec4 o = s;
    if (disp == 0) {                                         // LCD: levels + asymmetric response per channel
        vec3 q = uF.w > 0.5 ? vec3(quantL(tgt.r, uA.w, 0.5), quantL(tgt.g, uA.w, 0.5), quantL(tgt.b, uA.w, 0.5))
                            : vec3(quantL(lum, uA.w, 0.5));
        if (init) o = vec4(q, id);
        else {
            vec3 c = s.rgb;
            for (int k = 0; k < 3; k++) {
                float tau = q[k] > c[k] ? uC.x : uC.y;
                c[k] = tau <= 0.0 ? q[k] : c[k] + (q[k] - c[k]) * (1.0 - exp(-dt / tau));
            }
            o = vec4(c, id);
        }
    } else if (disp == 1) {                                  // VFD: 1-bit by Threshold or levels
        float v = uA.w <= 2.0 ? (lum > uA.z ? 1.0 : 0.0) : quantL(lum, uA.w, 0.5);
        o = vec4(v, 0.0, 0.0, id);
    } else if (disp == 3) {                                  // flip-dot: x side, y flip start (-1 idle), z new side
        float t = lum > uA.z ? 1.0 : 0.0;
        if (init) o = vec4(t, -1.0, t, id);
        else {
            o = s;
            if (o.y >= 0.0 && now >= o.y + uC.z) { o.x = o.z; o.y = -1.0; }
            if (o.y < 0.0 && t != o.x) {
                int sc = int(uC.w + 0.5);
                float d = sc == 1 ? uD.x * float(g.x) / float(max(gs.x, 1))
                        : sc == 2 ? uD.x * float(g.y) / float(max(gs.y, 1))
                        : sc == 3 ? uD.x * hsh(g, uint(uD.w)) : 0.0;
                o.y = now + d;
                o.z = t;
            }
        }
    } else if (disp == 5) {                                  // e-ink: x displayed, y target, z last update time
        float t = quantL(lum, uA.w, 0.5);
        if (init) o = vec4(t, t, now, id);
        else {
            o = vec4(s.x, t, s.z, id);
            float tr = uE.x, fl = uE.y;
            bool inflash = tr >= 0.0 && now >= tr && now < tr + fl;
            if (!inflash) {
                if (tr >= 0.0 && now >= tr + fl && s.z < tr + fl) { o.x = t; o.z = now; }
                else if (uE.z > 0.0 && floor(now * uE.z) > floor(s.z * uE.z)) {
                    o.x = t + (s.x - t) * uE.w;
                    o.z = now;
                }
            }
        }
    } else if (disp == 2) {                                  // nixie: x digit (-1 blank), y previous, z change time
        float t = float(code - 1);
        if (init) o = vec4(t, t, -1000.0, id);
        else if (t != s.x) o = vec4(t, s.x, now, id);
    } else {                                                 // split-flap: x index, y flap start (-1 idle)
        int n = NFLAP;
        int t = clamp(code - 1, 0, n - 1);
        if (init) o = vec4(float(t), -1.0, 0.0, id);
        else {
            int cur = int(s.x + 0.5);
            float y = s.y;
            if (y >= 0.0 && now - y >= uD.y) { cur = (cur + 1) % n; y = -1.0; }
            if (y < 0.0 && cur != t) y = now;
            o = vec4(float(cur), y, 0.0, id);
        }
    }
    TDImageStoreOutput(0, ivec3(g, 0), o);
    TDImageStoreOutput(1, ivec3(g, 0), vec4(now, 0.0, 0.0, 1.0));
}
"""

FX = """// FX_retro smalldisplay render: per output pixel, reads the state texel(s). in0 = picture, in1 = state.
layout (local_size_x = 8, local_size_y = 8) in;
%LIB%
uniform vec4 uA;   // amount, display, dot size px, glow
uniform vec4 uB;   // GW, GH, gap, mesh
uniform vec4 uC;   // on rgb, flicker
uniform vec4 uD;   // off rgb, cathodes
uniform vec4 uE;   // bg rgb, shadow px
uniform vec4 uF;   // now, flip time, flap step, fade
uniform vec4 uG;   // cell w, cell h, x0, y0 (top)
uniform vec4 uH;   // refresh time, flash time, mesh pitch, smooth
uniform vec4 uI;   // cols, rows, lcd rgb, shadow amount
uniform vec4 uJ;   // stroke, seed, -, -
vec4 stAt(ivec2 g) { ivec2 gs = ivec2(uB.xy + 0.5); return texelFetch(sTD2DInputs[1], clamp(g, ivec2(0), gs - 1), 0); }
float segD(vec2 p, vec4 s) { vec2 a = s.xy, b = s.zw, v = b - a, w = p - a;
    float t = clamp(dot(w, v) / max(dot(v, v), 1e-12), 0.0, 1.0); return length(w - v * t); }
float digitD(int d, vec2 p, vec2 box) {                      // distance in px to numeral d (0-9), box = digit size px
    if (d < 0 || d > 9) return 1e9;
    ivec2 r = NIXRANGE[d];
    float m = 1e9;
    for (int i = r.x; i < r.x + r.y; i++) {
        vec4 s = NIXSEG[i];
        m = min(m, segD(p, vec4(s.xy * box, s.zw * box)));
    }
    return m;
}
float symD(int d, vec2 p, vec2 box) {                        // 0-9 numerals, 10 ':', 11 '.'
    if (d == 10) return min(length(p - vec2(0.5, 0.3) * box), length(p - vec2(0.5, 0.7) * box)) - 0.04 * box.x;
    if (d == 11) return length(p - vec2(0.85, 0.04) * box) - 0.05 * box.x;
    return digitD(d, p, box);
}
bool flapGlyph(int idx, vec2 cuv, bool sm) {             // card uv (v down) -> glyph pixel, 12 % margin
    vec2 q = (cuv - 0.12) / 0.76;
    if (q.x < 0.0 || q.x >= 1.0 || q.y < 0.0 || q.y >= 1.0) return false;
    return glyphAt(FLAPG[clamp(idx, 0, NFLAP - 1)], q, sm);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 res = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= res.x || p.y >= res.y) return;
    int disp = int(uA.y + 0.5);
    float now = uF.x;
    int pyt = res.y - 1 - p.y;                               // row from the top
    vec3 on = uC.rgb, off = uD.rgb, bg = uE.rgb;
    float gap = uB.z;
    vec3 col = bg;
    if (disp == 0 || disp == 1 || disp == 3 || disp == 5) {
        int ds = max(int(uA.z + 0.5), 1);
        ivec2 g = ivec2(p.x / ds, pyt / ds);
        vec2 uv = vec2((float(p.x - g.x * ds) + 0.5) / float(ds), (float(pyt - g.y * ds) + 0.5) / float(ds));
        vec4 s = stAt(g);
        bool inside = uv.x < 1.0 - gap && uv.y < 1.0 - gap;
        if (disp == 0) {                                     // LCD
            if (uI.z > 0.5) {
                int k = int(uv.x * 3.0);
                vec3 prim = k == 0 ? vec3(1.0, 0.0, 0.0) : (k == 1 ? vec3(0.0, 1.0, 0.0) : vec3(0.0, 0.0, 1.0));
                col = inside ? prim * s[min(k, 2)] : bg * 0.15;
            } else {
                col = inside ? mix(on, off, s.x) : bg;
                int sh = int(uE.w + 0.5);
                if (sh > 0) {                                // drop shadow of the dot up-left of here
                    ivec2 q = ivec2(p.x - sh, pyt - sh);
                    if (q.x >= 0 && q.y >= 0) {
                        ivec2 g2 = ivec2(q.x / ds, q.y / ds);
                        vec2 uv2 = vec2((float(q.x - g2.x * ds) + 0.5) / float(ds), (float(q.y - g2.y * ds) + 0.5) / float(ds));
                        if (uv2.x < 1.0 - gap && uv2.y < 1.0 - gap) col *= 1.0 - uI.w * (1.0 - stAt(g2).x);
                    }
                }
            }
        } else if (disp == 1) {                              // VFD
            float I = s.x;
            vec2 d = abs(uv - (1.0 - gap) * 0.5) / max((1.0 - gap) * 0.5, 1e-3);
            float core = I * (1.0 - smoothstep(0.75, 1.0, max(d.x, d.y)));
            float glow = 0.0;
            if (uA.w > 0.0) {
                for (int dy = -1; dy <= 1; dy++) for (int dx = -1; dx <= 1; dx++) {
                    float In = stAt(g + ivec2(dx, dy)).x;
                    vec2 c = vec2(float(dx), float(dy)) + (1.0 - gap) * 0.5;
                    glow += In * exp(-length(uv - c) / max(uA.w, 1e-3));
                }
            }
            float fl = 1.0 + uC.w * (hsh(g, uint(now * 60.0)) - 0.5);
            col = bg + off * (1.0 - core) * (inside ? 1.0 : 0.0) + on * (core + 0.25 * glow) * fl;
            int mp = max(int(uH.z + 0.5), 2);
            if (p.x % mp == 0 || pyt % mp == 0) col *= 1.0 - uB.w;
        } else if (disp == 3) {                              // flip-dot
            float side = s.x, sc = 1.0;
            if (s.y >= 0.0 && now >= s.y) {
                float pr = clamp((now - s.y) / max(uF.y, 1e-3), 0.0, 1.0);
                side = pr < 0.5 ? s.x : s.z;
                sc = abs(cos(3.14159265 * pr));
            }
            vec2 c = uv - 0.5;
            float r = 0.5 * (1.0 - gap);
            float e = c.x * c.x + (c.y / max(sc, 0.02)) * (c.y / max(sc, 0.02));
            col = e < r * r ? (side > 0.5 ? on : off) * (0.55 + 0.45 * sc) : bg;
        } else {                                             // e-ink
            float gr = s.x;
            float ts = now - uH.x;
            if (uH.x >= 0.0 && ts >= 0.0 && ts < uH.y) {
                float q = ts / uH.y * 4.0;
                gr = q < 1.0 ? 1.0 - s.x : (q < 2.0 ? 0.0 : (q < 3.0 ? 1.0 : mix(1.0, s.y, fract(q))));
            }
            col = mix(on, off, gr) * (1.0 - 0.05 * hsh(p, 7u));
            if (!inside) col = off;
        }
    } else {                                                 // character cells: nixie / split-flap
        vec2 cw = uG.xy;
        vec2 lp = vec2(float(p.x) + 0.5 - uG.z, float(pyt) + 0.5 - uG.w);
        ivec2 cell = ivec2(floor(lp / cw));
        ivec2 cr = ivec2(uI.xy + 0.5);
        if (lp.x >= 0.0 && lp.y >= 0.0 && cell.x < cr.x && cell.y < cr.y) {
            vec2 uv = lp / cw - vec2(cell);                  // v down
            vec4 s = stAt(cell);
            if (disp == 2) {                                 // nixie tube
                vec2 tq = abs(uv - 0.5) * 2.0;
                bool tube = max(tq.x, tq.y) < 1.0 - gap;
                if (tube) {
                    col = off;
                    vec2 box = cw * vec2(0.6, 0.66);
                    vec2 dp = (vec2(uv.x, 1.0 - uv.y) - vec2(0.2, 0.17)) * cw;      // y up inside the digit box
                    float lw = uJ.x * box.x;
                    bool inBox = all(greaterThan(dp, vec2(-lw))) && all(lessThan(dp, box + lw));
                    if (uD.w > 0.0 && inBox) {                       // unlit cathode stack: only inside the digit box
                        float dm = 1e9;
                        for (int k = 0; k < 10; k++) dm = min(dm, digitD(k, dp, box));
                        col += vec3(0.35, 0.33, 0.3) * uD.w * (1.0 - smoothstep(lw * 0.3, lw * 0.6, dm));
                    }
                    float pf = clamp((now - s.z) / max(uF.w, 1e-3), 0.0, 1.0);
                    float fl = 1.0 + uC.w * (hsh(cell, uint(now * 60.0)) - 0.5);
                    float gr = max(uA.w, 1e-3) * box.x * 0.25;
                    for (int k = 0; k < 2; k++) {
                        int d = int(k == 0 ? s.x : s.y);
                        float I = k == 0 ? pf : 1.0 - pf;
                        if (d < 0 || I <= 0.0) continue;
                        float dd = symD(d, dp, box);
                        float core = 1.0 - smoothstep(lw * 0.4, lw, dd);
                        col += on * (core * 1.6 + exp(-max(dd, 0.0) / gr) * 0.7) * I * fl;
                    }
                    vec2 hp = vec2(p.x, pyt) / max(uH.z, 2.0);                       // hex anode mesh
                    float hx = min(min(abs(fract(hp.x) - 0.5), abs(fract(0.5 * hp.x + 0.866 * hp.y) - 0.5)),
                                   abs(fract(-0.5 * hp.x + 0.866 * hp.y) - 0.5));
                    col *= 1.0 - uB.w * (1.0 - smoothstep(0.0, 0.08, hx));
                    float edge = max(tq.x, tq.y) / (1.0 - gap);
                    col += vec3(0.25) * smoothstep(0.9, 1.0, edge) * 0.5;                 // glass rim
                }
            } else {                                         // split-flap card
                vec2 q = (uv - gap * 0.5) / (1.0 - gap);
                if (q.x >= 0.0 && q.x < 1.0 && q.y >= 0.0 && q.y < 1.0) {
                    int cur = int(s.x + 0.5), nx = (cur + 1) % NFLAP;
                    bool moving = s.y >= 0.0 && now >= s.y;
                    float pr = moving ? clamp((now - s.y) / max(uF.z, 1e-3), 0.0, 1.0) : 0.0;
                    float cs_ = cos(3.14159265 * pr);
                    bool sm = uH.w > 0.5;
                    bool lit;
                    float shade = 1.0;
                    if (q.y < 0.5) {
                        lit = flapGlyph(moving ? nx : cur, q, sm);
                        if (moving && pr < 0.5) {
                            float top = 0.5 - 0.5 * cs_;
                            if (q.y >= top) { lit = flapGlyph(cur, vec2(q.x, 0.5 - (0.5 - q.y) / max(cs_, 1e-3)), sm); shade = 0.6 + 0.4 * cs_; }
                        }
                    } else {
                        lit = flapGlyph(cur, q, sm);
                        if (moving && pr >= 0.5) {
                            float bot = 0.5 + 0.5 * abs(cs_);
                            if (q.y <= bot) { lit = flapGlyph(nx, vec2(q.x, 0.5 + (q.y - 0.5) / max(abs(cs_), 1e-3)), sm); shade = 0.6 + 0.4 * abs(cs_); }
                        }
                    }
                    col = (lit ? on : off) * shade;
                    if (abs(q.y - 0.5) * cw.y < 1.5) col *= 0.2;                       // hinge line
                }
            }
        }
    }
    vec4 src = texelFetch(sTD2DInputs[0], p, 0);
    vec4 r = mix(vec4(straight(src), src.a), vec4(col, 1.0), uA.x);
    TDImageStoreOutput(0, ivec3(p, 0), TDOutputSwizzle(vec4(r.rgb * r.a, r.a)));
}
"""


def shader_texts(lib):
    return {'state': STATE.replace('%LIB%', lib(font=1, flap=True)),
            'fx': FX.replace('%LIB%', lib(font=2, nixie=True, flap=True))}


def build(m, H, Lg):
    """in1 + codes -> state (grid res, in place, 2 buffers) -> fx (input res) -> out_sel -> out1; Refresh pulse."""
    mk, expr, compute, P, LX = H['mk'], H['expr'], H['compute'], H['P'], H['LX']
    in1 = mk(m, inTOP, 'in1')
    codes = H['codes_chop'](m, 'display_codes_td', 'Display codes (fx_retro_logic.display_codes), top row first.')
    H['pulse_exec'](m, {'Refresh': 'Refreshtime'})
    W, Hh = 'me.inputs[0].width', 'me.inputs[0].height'
    disp = "parent().par.Display.eval()"
    size = "%s.state_size(%s, %s, %s, %s, %s, %s)" % (LX, disp, W, Hh, P.format('Dotsize'), P.format('Columns'),
                                                       P.format('Rows'))
    lay = "%s.cell_layout(%s, %s, %s, %s, %s)" % (LX, W, Hh, P.format('Columns'), P.format('Rows'),
                                                  P.format('Cellaspect'))
    tref = ("max(%s, (math.floor(absTime.seconds / %s) * %s) if %s > 0 else -1.0)" % (
        P.format('Refreshtime'), P.format('Refreshperiod'), P.format('Refreshperiod'), P.format('Refreshperiod')))
    rgb = lambda n, w: [P.format(n + 'r'), P.format(n + 'g'), P.format(n + 'b'), w]     # noqa: E731
    sh = shader_texts(lambda **k: H['glsl_lib'](Lg, **k))
    font = H['select'](m, 'font', '../font_top')
    st = compute(m, 'state', sh['state'], [in1, font], size + '[0]', size + '[1]', fmt='rgba32float', readwrite=True, bufs=2,
                 uniforms=[
                     ('uA', ['parent().par.Display.menuIndex', "1 if parent().par.Content.eval() == 'image' else 0",
                             P.format('Threshold'), P.format('Levels')]),
                     ('uB', [size + '[0]', size + '[1]', P.format('Dotsize'), 'max(1, %s[0] // 8)' % size]),
                     ('uC', [P.format('Rise'), P.format('Fall'), P.format('Fliptime'),
                             'parent().par.Flipscan.menuIndex']),
                     ('uD', [P.format('Sweep'), P.format('Flapstep'), '0', P.format('Seed')]),
                     ('uE', [tref, P.format('Flashtime'), P.format('Updatehz'), P.format('Ghost')]),
                     ('uF', [P.format('Contrast'), P.format('Brightness'), '1 if %s else 0' % P.format('Invert'),
                             '1 if %s else 0' % P.format('Lcdcolour')]),
                     ('uT', ['absTime.seconds', '0', '0', '0']),
                 ], arrays=[('uCodes', codes)])
    st.comment = 'smalldisplay state: one rgba32float texel per dot / cell, in place (T-110 (5)); restarts on stalls.'
    fx = compute(m, 'fx', sh['fx'], [in1, st, font], W, Hh, uniforms=[
        ('uA', [P.format('Amount'), 'parent().par.Display.menuIndex', P.format('Dotsize'), P.format('Glow')]),
        ('uB', [size + '[0]', size + '[1]', P.format('Gap'), P.format('Mesh')]),
        ('uC', rgb('Oncolour', P.format('Flicker'))),
        ('uD', rgb('Offcolour', P.format('Cathodes'))),
        ('uE', rgb('Bgcolour', P.format('Shadow'))),
        ('uF', ['absTime.seconds', P.format('Fliptime'), P.format('Flapstep'), P.format('Fade')]),
        ('uG', [lay + '[0]', lay + '[1]', lay + '[2]', lay + '[3]']),
        ('uH', [tref, P.format('Flashtime'), P.format('Meshpitch'), '1 if %s else 0' % P.format('Smooth')]),
        ('uI', [P.format('Columns'), P.format('Rows'), '1 if %s else 0' % P.format('Lcdcolour'),
                P.format('Shadowamt')]),
        ('uJ', [P.format('Stroke'), P.format('Seed'), '0', '0']),
    ])
    fx.comment = 'smalldisplay render: LCD / VFD / Nixie / flip-dot / split-flap / e-ink from the state texels.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, "0 if parent().par.Amount.eval() <= 0 else 1")
    sel.comment = 'Amount 0 = in1 exactly (state / fx / codes not pulled).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'font', 'codes', 'codes_callbacks', 'pulse_exec'],
         'body': 'Picture, text codes, Refresh pulse.'},
        {'title': '2 Display', 'role': 'process', 'ops': ['state', 'state_compute', 'fx', 'fx_compute'],
         'body': 'state: per dot / cell memory (in place). fx: render.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:
    PAGES, PRESETS = None, None
