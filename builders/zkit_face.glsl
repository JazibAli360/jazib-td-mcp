// zkit face shader: draws every knob / preset / pill / group frame / menu row of one panel in ONE pass (T-46 safe:
// single pass, input = instance texture from a CHOP to TOP, not a GLSL chain). Clean-room, spec BE 6 + 7.0.
// Input 0: instance texture, packed RGBA32F, one row of 4 n texels: texel k*n + i = fields 4k..4k+3 of instance i
//          (zkit_logic.FIELDS; zk_gpu_sel + zk_gpu_pack, perf pass 26 Oct).
// Input 1: tile texture (zkit_logic.tile_rows): column = 64 px tile (row-major), row 0 = count, row 1+k = k-th
//          instance index; a pixel loops over its tile's instances only (perf, docs/builds/zkit_perf.md).
// Inputs 2..9: text buckets zk_text0..7, inputs 10..11: hot text zk_hot0..1 (white on transparent Text TOPs);
// a kind 16 instance colours the text pixels inside its box from input 2 + u, in draw order, so a menu drawn later
// covers the knob text under it.
// Pixel coords: instances are in panel pixels, y DOWN; gl_FragCoord is y up. Scrolling panels: content instances
// (flag 256) are in STAGE px and move by uView.x; they never draw above the header (uView.y). Text TOPs and the tile
// grid are stage-sized (uView.z tall): header rows at view y, content rows at stage y.
uniform vec4 uInfo;    // n instances, panel w, panel h, tile size px (0 = no tiles: loop over all instances)
uniform vec4 uBg;
uniform vec4 uBody;
uniform vec4 uTrack;
uniform vec4 uBlue;    // surface blue (frames, titles, dots)
uniform vec4 uBlueDim;
uniform vec4 uRed;
uniform vec4 uWhite;   // plus sign, rand arc, toggle-on text side (rgb), a = day theme flag
uniform vec4 uView;    // pages + scroll (28 Oct): x = scroll shift (stage y = view y + x below the header),
                       // y = header bottom px (-1 = nothing scrolls), z = stage height (text TOPs + tile grid),
                       // w = scrollbar gutter x (content lives left of it)
out vec4 fragColor;

const float PI = 3.14159265;
const float A0 = -2.35619449;   // -135 deg (7 o'clock), clockwise from 12
const float SW = 4.71238898;    // 270 deg sweep

int gN = 1;                                                  // instance stride (texture width / 4), set in main
vec4 G(int i, int k) { return texelFetch(sTD2DInputs[0], ivec2(k * gN + i, 0), 0); }
float T(int t, int r) { return texelFetch(sTD2DInputs[1], ivec2(t, r), 0).r; }
// alpha of text input b at this pixel (constant sampler indices only: no dynamic sampler-array indexing on MoltenVK)
float textA(int b, ivec2 q) {
    if (b == 0) return texelFetch(sTD2DInputs[2], q, 0).a;
    if (b == 1) return texelFetch(sTD2DInputs[3], q, 0).a;
    if (b == 2) return texelFetch(sTD2DInputs[4], q, 0).a;
    if (b == 3) return texelFetch(sTD2DInputs[5], q, 0).a;
    if (b == 4) return texelFetch(sTD2DInputs[6], q, 0).a;
    if (b == 5) return texelFetch(sTD2DInputs[7], q, 0).a;
    if (b == 6) return texelFetch(sTD2DInputs[8], q, 0).a;
    if (b == 7) return texelFetch(sTD2DInputs[9], q, 0).a;
    if (b == 8) return texelFetch(sTD2DInputs[10], q, 0).a;
    if (b == 9) return texelFetch(sTD2DInputs[11], q, 0).a;
    return 0.0;
}

// coverage helpers (1 px AA)
float disc(float d, float r) { return clamp(r - d + 0.5, 0.0, 1.0); }
float ring(float d, float r0, float r1) { return clamp(min(d - r0, r1 - d) + 0.5, 0.0, 1.0); }
float boxc(vec2 p, vec2 a, vec2 b) {
    vec2 q = min(p - a, b - p);
    return clamp(min(q.x, q.y) + 0.5, 0.0, 1.0);
}
float rbox(vec2 p, vec2 c, vec2 hs, float rad) {           // signed distance of a rounded box
    vec2 q = abs(p - c) - hs + rad;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - rad;
}
// angle of p around c: 0 at 12 o'clock, clockwise positive, -PI..PI (y down coords)
float ang(vec2 d) { return atan(d.x, -d.y); }
// butt-capped arc coverage between angles a0..a1 (radians from 12 o'clock), radius band r0..r1
float arc(vec2 d, float r0, float r1, float a0, float a1) {
    float L = length(d);
    float a = ang(d);
    float cov = ring(L, r0, r1);
    float e0 = (a - a0) * L, e1 = (a1 - a) * L;            // px distance to the caps along the arc
    return cov * clamp(min(e0, e1) + 0.5, 0.0, 1.0);
}
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
vec3 over(vec3 dst, vec3 src, float a) { return mix(dst, src, clamp(a, 0.0, 1.0)); }
float diamond(vec2 p, vec2 c, float s) { vec2 q = abs(p - c); return clamp(s - (q.x + q.y) + 0.5, 0.0, 1.0); }
vec2 polar(vec2 c, float R, float a) { return c + R * vec2(sin(a), -cos(a)); }
// L-shaped corner brackets around a box (selection look, 7.0 #9)
float brackets(vec2 p, vec2 a, vec2 b, float len, float t) {
    float cov = 0.0;
    vec2 cs[4] = vec2[4](a, vec2(b.x, a.y), vec2(a.x, b.y), b);
    for (int k = 0; k < 4; k++) {
        vec2 c = cs[k];
        vec2 dir = vec2(c.x == a.x ? 1.0 : -1.0, c.y == a.y ? 1.0 : -1.0);
        vec2 q = (p - c) * dir;                              // into the box = positive
        float h = (q.x >= -0.5 && q.x <= len && q.y >= -0.5 && q.y <= t) ? 1.0 : 0.0;
        float v = (q.y >= -0.5 && q.y <= len && q.x >= -0.5 && q.x <= t) ? 1.0 : 0.0;
        cov = max(cov, max(h, v));
    }
    return cov;
}

void main() {
    vec2 res = uTDOutputInfo.res.zw;
    vec2 p = vec2(gl_FragCoord.x, res.y - gl_FragCoord.y);  // y down, pixel centres
    vec3 col = uBg.rgb;
    int n = int(uInfo.x + 0.5);
    gN = max(1, textureSize(sTD2DInputs[0], 0).x / 4);
    bool day = uWhite.a > 0.5;
    int ts = int(uInfo.w + 0.5);
    bool scrolls = uView.y >= 0.0;
    bool inContent = scrolls && p.y >= uView.y && p.x < uView.w;   // the scrollbar gutter keeps view px
    float sh = scrolls ? uView.x : 0.0;
    float sty = inContent ? p.y + sh : p.y;               // this pixel in stage px (tiles + text)
    float stH = (scrolls && uView.z > 0.0) ? uView.z : res.y;
    int tile = 0, cnt = n;
    if (ts > 0) {
        int ntx = (int(uInfo.y + 0.5) + ts - 1) / ts;
        tile = int(p.x) / ts + (int(sty) / ts) * ntx;
        cnt = int(T(tile, 0) + 0.5);
    }
    ivec2 tq = ivec2(int(gl_FragCoord.x), int(stH - sty));  // text texel (Text TOPs are y up)
    for (int j = 0; j < cnt; j++) {
        int i = ts > 0 ? int(T(tile, 1 + j) + 0.5) : j;
        vec4 g0 = G(i, 0);
        vec4 g2 = G(i, 2);
        int fl = int(g2.y + 0.5);
        bool scr = (fl & 256) != 0;
        if (scr && !inContent) continue;                    // content never draws over the header
        float sy = scr ? sh : 0.0;
        float bx = g0.x, by = g0.y - sy, bw = g0.z, bh = g0.w;
        if (p.x < bx - 2.0 || p.x > bx + bw + 2.0 || p.y < by - 2.0 || p.y > by + bh + 2.0) continue;
        vec4 g1 = G(i, 1), g3 = G(i, 3);
        vec2 c = g1.xy - vec2(0.0, sy);
        float R = g1.z, u = g1.w;
        int kind = int(g2.x + 0.5);
        vec3 acc = vec3(g2.z, g2.w, g3.x);
        float zu = g3.y, a1 = g3.z, a2 = g3.w;
        bool hov = (fl & 1) != 0, act = (fl & 2) != 0, sel = (fl & 4) != 0, lock = (fl & 16) != 0, on = (fl & 32) != 0;
        vec2 d = p - c;
        float L = length(d);
        // knob geometry (7.0 #2): arc outer = R, arc 0.14 R (0.07 D), gap 0.10 R, body ring 0.06 R (0.03 D)
        float arcT = max(1.5, 0.14 * R), gap = max(1.0, 0.10 * R);
        float rb = R - arcT - gap;                         // body radius
        float ringT = max(1.0, 0.06 * R);
        vec3 body = uBody.rgb * (hov ? 1.08 : 1.0) + (hov ? vec3(0.02) : vec3(0.0));
        vec3 dim = acc * 0.38 + uBody.rgb * 0.30;          // dim tag ring (~#5f271e for orange)
        if (kind == 0 || kind == 4 || kind == 5) {
            // parameter knob / menu knob / swatch
            col = over(col, act ? acc : (kind == 5 ? acc * max(u, 0.0) : body), disc(L, rb));
            vec3 rc = lock ? uTrack.rgb * 1.6 : dim;       // not recallable: grey ring (ours; 7.5 unverified)
            if (kind == 5) rc = acc * 0.6 + 0.15;
            col = over(col, rc, ring(L, rb - ringT, rb));
            col = over(col, uTrack.rgb, arc(d, R - arcT, R, A0, A0 + SW));
            if (kind == 4) {
                float s0 = A0 + SW * a1, s1 = A0 + SW * a2;  // short arc of the current item
                col = over(col, acc, arc(d, R - arcT, R, s0, s1));
            } else if (kind == 0) {
                float az = A0 + SW * zu, av = A0 + SW * u;
                float lo = min(az, av), hi = max(az, av);
                if (hi - lo < 0.06) { lo = az - 0.03; hi = az + 0.03; }  // tiny stub at the zero point
                col = over(col, acc, arc(d, R - arcT, R, lo, hi));
            } else {
                col = over(col, uWhite.rgb * 0.85, arc(d, R - arcT, R, A0, A0 + SW * u)); // swatch: brightness
            }
        } else if (kind == 1 || kind == 2) {
            // toggle / momentary (7.0 #7): off = dim tint body + bright ring, no arc; on = full accent
            bool lit = on || act;
            vec3 fillc = lit ? acc : (acc * 0.28 + uBody.rgb * 0.55);
            col = over(col, fillc, disc(L, rb));
            col = over(col, acc, ring(L, rb - ringT * 1.4, rb));
            if (hov && !lit) col = over(col, acc, 0.10 * disc(L, rb));
        } else if (kind == 3) {
            // pulse: dark body, dim dot 0.45 D, bright while pressed
            col = over(col, body, disc(L, rb));
            col = over(col, dim, ring(L, rb - ringT, rb));
            col = over(col, act ? acc : acc * 0.55, disc(L, 0.45 * R));
        } else if (kind == 6 || kind == 15) {
            // string pill / type-in field
            float sd = rbox(p, c, vec2(bw * 0.46, R * 0.42), R * 0.42);
            col = over(col, act ? acc * 0.5 : body, clamp(0.5 - sd, 0.0, 1.0));
            col = over(col, kind == 15 ? acc : dim, clamp(1.0 - abs(sd + 0.75), 0.0, 1.0));
        } else if (kind == 19) {
            // dropdown field (28 Oct): string pill + a small down triangle at its right end; a1 = 1 while open
            float sd = rbox(p, c, vec2(bw * 0.46, R * 0.42), R * 0.42);
            bool opn = a1 > 0.5;
            col = over(col, act ? acc * 0.5 : body, clamp(0.5 - sd, 0.0, 1.0));
            col = over(col, (opn || hov) ? acc : dim, clamp(1.0 - abs(sd + 0.75), 0.0, 1.0));
            float tsz = max(3.0, R * 0.17);
            vec2 q = p - vec2(c.x + bw * 0.46 - R * 0.50, c.y);
            float e1 = q.y + tsz * 0.55;                        // below the flat top edge
            float e2 = tsz * (0.55 * tsz - q.y) / (1.1 * tsz) - abs(q.x);   // inside the slanted sides
            col = over(col, (opn || hov) ? acc : uWhite.rgb * 0.75, clamp(min(e1, e2 * 0.9) + 0.5, 0.0, 1.0));
        } else if (kind == 7) {
            // preset slot (7.0 #3, #4): a1 = stored, a2 = morph t (-1 idle)
            bool stored = a1 > 0.5;
            vec3 pc = stored ? acc : uTrack.rgb * 1.5;
            col = over(col, body, disc(L, rb));
            col = over(col, stored ? uTrack.rgb : uTrack.rgb * 0.8, arc(d, R - arcT, R, A0, A0 + SW));
            float head = A0;
            if (stored && a2 >= 0.0) {
                head = A0 + SW * a2;
                col = over(col, acc, arc(d, R - arcT, R, A0, max(head, A0 + 0.02)));
            } else if (stored && hov) {
                col = over(col, uRed.rgb, 0.85 * arc(d, R - arcT, R, A0 + 0.12, A0 + SW - 0.12));
                // arrow heads at both ends of the hovered arc
                for (int e = 0; e < 2; e++) {
                    float ae = e == 0 ? A0 + 0.12 : A0 + SW - 0.12;
                    vec2 tip = polar(c, R - arcT * 0.5, ae);
                    col = over(col, uRed.rgb, diamond(p, tip, arcT * 1.3));
                }
                col = over(col, uRed.rgb, 0.10 * ring(L, R, R + 4.0));
            }
            if (stored) col = over(col, acc, disc(L, 0.30 * R));       // classic: solid dot ~0.3 D
            col = over(col, pc, diamond(p, polar(c, R - arcT * 0.5, head), arcT * 1.25));
            if (act) col = over(col, acc, 0.85 * disc(L, rb));
        } else if (kind == 8) {
            // "+" (store preset): dark disc ~1.1 D, white plus
            col = over(col, act ? acc : uBody.rgb * (hov ? 1.25 : 0.9), disc(L, R * 0.92));
            float t = max(1.0, R * 0.07), s = R * 0.42;
            float plus = max(boxc(p, c - vec2(s, t), c + vec2(s, t)), boxc(p, c - vec2(t, s), c + vec2(t, s)));
            col = over(col, vec3(0.92), plus);
        } else if (kind == 9) {
            // group frame = MIDI-surface look (7.3): 1.5 px blue rounded rect, dot top-right (a1 = collapsed)
            float sd = rbox(p, vec2(bx + bw * 0.5, by + bh * 0.5), vec2(bw * 0.5 - 1.0, bh * 0.5 - 1.0), 6.0);
            col = over(col, uBlue.rgb, clamp(1.25 - abs(sd + 0.75), 0.0, 1.0));
            vec2 dc = vec2(bx + bw - R * 1.2, by + R * 1.1);
            float dl = length(p - dc);
            col = over(col, a1 > 0.5 ? uBlueDim.rgb : uBlue.rgb, disc(dl, R * 0.42));
            if (hov) col = over(col, uBlue.rgb, 0.08 * boxc(p, vec2(bx, by), vec2(bx + bw, by + R * 2.2)));
        } else if (kind == 10) {
            // rand pill (7.0 #4): coarse pixel-noise disc; white arc while dragged (a2 = t)
            float cell = max(2.0, floor(R * 0.16));
            vec2 g = floor((p - c) / cell);
            float h = hash(g);
            vec3 nz = mix(uBody.rgb, acc, step(0.55, h)) * (0.6 + 0.4 * hash(g + 7.0));
            col = over(col, nz, disc(L, rb));
            col = over(col, dim, ring(L, rb - ringT, rb));
            if (a2 >= 0.0) col = over(col, vec3(0.95), arc(d, R - arcT, R, A0, A0 + SW * max(a2, 0.01)));
            if (hov) col = over(col, acc, 0.15 * disc(L, rb));
        } else if (kind == 11) {
            // theme switch: small circle, half filled (u = 1 day)
            col = over(col, uTrack.rgb * 1.3, ring(L, R * 0.55, R * 0.62));
            float hf = (u > 0.5) ? step(0.0, -d.x) : step(0.0, d.x);
            col = over(col, vec3(0.86), hf * disc(L, R * 0.50));
        } else if (kind == 12) {
            // properties menu row: flat fill
            col = over(col, acc, boxc(p, vec2(bx, by), vec2(bx + bw, by + bh)));
            if (hov) col = over(col, vec3(1.0), 0.06 * boxc(p, vec2(bx, by), vec2(bx + bw, by + bh)));
        } else if (kind == 13) {
            // colour dot (selected = outer ring)
            col = over(col, acc, disc(L, R * 0.62));
            if (on) col = over(col, vec3(0.92), ring(L, R * 0.78, R * 0.92));
        } else if (kind == 16) {
            // text colour box: a1 = alpha
            float ta = textA(int(u + 0.5), tq);
            col = over(col, acc, ta * a1 * boxc(p, vec2(bx, by), vec2(bx + bw, by + bh)));
            continue;
        } else if (kind == 14) {
            // radio: ring, inner dot when on (7.0 #8)
            col = over(col, acc, ring(L, R * 0.62, R * 0.80));
            if (on) col = over(col, acc, disc(L, R * 0.38));
        } else if (kind == 17) {
            // page tab pill (pages pass, 28 Oct): selected = surface blue fill; else body + dim outline (hover: blue)
            float sd = rbox(p, c, vec2(bw * 0.5 - 0.5, bh * 0.5 - 0.5), bh * 0.5 - 0.5);
            float inside = clamp(0.5 - sd, 0.0, 1.0);
            if (on) {
                col = over(col, acc * (hov ? 1.12 : 1.0), inside);
            } else {
                col = over(col, body, inside);
                col = over(col, hov ? acc : uBlueDim.rgb, clamp(1.0 - abs(sd + 0.75), 0.0, 1.0));
            }
        } else if (kind == 18) {
            // scrollbar: slim rounded track + thumb (a1 = thumb top, a2 = thumb height, view px)
            float rr = bw * 0.5;
            float st = rbox(p, vec2(bx + rr, by + bh * 0.5), vec2(rr, bh * 0.5), rr);
            col = over(col, uTrack.rgb * (day ? 0.85 : 1.25), clamp(0.5 - st, 0.0, 1.0));
            float sth = rbox(p, vec2(bx + rr, a1 + a2 * 0.5), vec2(rr, a2 * 0.5), rr);
            col = over(col, act ? acc * 1.15 : (hov ? acc : acc * 0.72), clamp(0.5 - sth, 0.0, 1.0));
        }
        if (sel) {
            float len = max(4.0, min(bw, bh) * 0.16);
            col = over(col, uRed.rgb, brackets(p, vec2(bx + 1.0, by + 1.0), vec2(bx + bw - 1.0, by + bh - 1.0), len, 1.5));
        }
        if ((fl & 64) != 0) col = over(col, uBlue.rgb, disc(length(p - vec2(c.x + R * 0.82, c.y - R * 0.82)), R * 0.12));
    }
    fragColor = TDOutputSwizzle(vec4(col, 1.0));
}
