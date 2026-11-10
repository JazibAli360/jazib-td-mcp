// FX_scope HUD (compute, one pass, input size, useinput): camera viewfinder over the picture. Picture tools first
// (mono for peaking, false colour, zebra, focus peaking, clip / crush), then overlays (frame guides + dim, safe
// areas, centre cross, corner brackets, REC / STBY + blinking dot, timecode, battery, label; 8x8 font with a
// 1-px dark outline so text reads on any picture). Amount mixes the whole HUD over the input.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uZ;    // zebra on, low, high, opacity
uniform vec4 uZ2;   // stripe width px, angle rad, shift px (time x speed), colour (0 white 1 black 2 red)
uniform vec4 uK;    // peaking on, threshold, colour (0 red 1 yellow 2 blue 3 white 4 green), mono picture
uniform vec4 uFc;   // false colour on, mode (0 exposure 1 spectrum 2 zones 3 clip), mix, clip warning on
uniform vec4 uCl;   // clip level, crush level, absTime s, amount
uniform vec4 uOv;   // rec (0 off 1 standby 2 rec), blink Hz, timecode on, battery level (< 0 = off)
uniform vec4 uOv2;  // safe areas on, action, title, centre cross on
uniform vec4 uGd;   // guide aspect (0 none), guide dim, brackets on, hud colour (0 white 1 yellow 2 green 3 cyan)
uniform vec4 uTx;   // glyph px, margin px, label length, 0
uniform vec4 uTc;   // timecode h m s f
uniform vec4 uLb0;  // label chars 0-3 (ASCII codes)
uniform vec4 uLb1;
uniform vec4 uLb2;
uniform vec4 uLb3;
//@FONT
const vec3 LUM = vec3(0.2126, 0.7152, 0.0722);
float Y(vec3 c) { return dot(c, LUM); }
vec3 fcol(float y, int mode) {
    y = clamp(y, 0.0, 1.0);
    if (mode == 0) {
        if (y < 0.025) return vec3(0.5, 0.0, 0.6);
        if (y < 0.04) return vec3(0.0, 0.2, 1.0);
        if (y >= 0.38 && y < 0.42) return vec3(0.1, 0.85, 0.2);
        if (y >= 0.52 && y < 0.56) return vec3(1.0, 0.55, 0.7);
        if (y >= 0.97 && y < 0.99) return vec3(1.0, 0.9, 0.0);
        if (y >= 0.99) return vec3(1.0, 0.0, 0.0);
        return vec3(y);
    }
    if (mode == 1) {
        vec3 k = mod(vec3(5.0, 3.0, 1.0) + 0.66 * (1.0 - y) * 6.0, 6.0);
        return 1.0 - clamp(min(k, 4.0 - k), 0.0, 1.0);
    }
    if (mode == 2) return vec3(floor(y * 10.0 + 0.5) / 10.0);
    if (y >= 0.99) return vec3(1.0, 0.0, 0.0);
    if (y <= 0.02) return vec3(0.0, 0.2, 1.0);
    return vec3(y);
}
int glyphBit(int code, int row, int col) {
    int g = code - 32;
    if (g < 0 || g > 94 || row < 0 || row > 7 || col < 0 || col > 7) return 0;
    return int((FONT[2 * g + row / 4] >> uint(8 * (row % 4) + col)) & 1u);
}
// No per-thread arrays here (perf lane 3, 27 Oct: the per-pixel TC_ fill + local char / colour tables cost ~0.3 ms
// GPU at 1080 x 1920; dynamic indexing of a private array goes to memory, T-145). Same characters as before.
int charOf(int kind, int i) {
    if (kind == 0) { int m = i % 3; return m == 0 ? 82 : (m == 1 ? 69 : 67); }                          // REC
    if (kind == 1) { int m = i % 4; return m == 0 ? 83 : (m == 1 ? 84 : (m == 2 ? 66 : 89)); }         // STBY
    if (kind == 2) {                                                                                   // hh:mm:ss:ff
        int k = i % 11, f = k / 3, r = k % 3;
        if (r == 2) return 58;
        int d = int((f == 0 ? uTc.x : (f == 1 ? uTc.y : (f == 2 ? uTc.z : uTc.w))) + 0.5);
        return 48 + (r == 0 ? (d / 10) % 10 : d % 10);
    }
    vec4 v = i < 4 ? uLb0 : (i < 8 ? uLb1 : (i < 12 ? uLb2 : uLb3));
    return int(v[i % 4] + 0.5);
}
bool bitAt(int kind, int len, ivec2 gp) {
    if (gp.x < 0 || gp.y < 0 || gp.y > 7 || gp.x >= len * 8) return false;
    return glyphBit(charOf(kind, gp.x / 8), gp.y, gp.x % 8) == 1;
}
// 2 = glyph pixel, 1 = outline, 0 = none. pd = y-down px, org = top-left, s = px per glyph pixel
int textAt(vec2 pd, vec2 org, float s, int kind, int len) {
    vec2 r = (pd - org) / s;
    if (r.x < -1.0 || r.y < -1.0 || r.x >= float(len * 8 + 1) || r.y >= 9.0) return 0;
    ivec2 gp = ivec2(floor(r));
    if (bitAt(kind, len, gp)) return 2;
    for (int j = -1; j <= 1; j++)
        for (int i = -1; i <= 1; i++)
            if (bitAt(kind, len, gp + ivec2(i, j))) return 1;
    return 0;
}
float rectLine(vec2 p, vec4 r, float t) {            // outline of rect (x0 y0 w h), thickness t px
    vec2 a = p - r.xy, b = r.xy + r.zw - p;
    float inside = step(0.0, min(min(a.x, a.y), min(b.x, b.y)));
    return inside * step(min(min(a.x, a.y), min(b.x, b.y)), t);
}
void main() {
    ivec2 P = ivec2(gl_GlobalInvocationID.xy);
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    if (P.x >= R.x || P.y >= R.y) return;
    vec4 src = texelFetch(sTD2DInputs[0], P, 0);
    vec2 W = vec2(R);
    vec2 p = vec2(P) + 0.5;                            // y up
    vec2 pd = vec2(p.x, W.y - p.y);                    // y down (overlay layout)
    float t = uCl.z;
    vec3 c = src.rgb;
    float y = Y(c);
    if (uK.x > 0.5 && uK.w > 0.5) c = vec3(y);
    if (uFc.x > 0.5) c = mix(c, fcol(y, int(uFc.y + 0.5)), uFc.z);
    if (uZ.x > 0.5 && y >= uZ.y && y <= uZ.z) {
        float d = (p.x * cos(uZ2.y) + p.y * sin(uZ2.y) + uZ2.z) / (2.0 * max(uZ2.x, 1e-3));
        if (fract(d) < 0.5) {
            int zc = int(uZ2.w + 0.5);
            c = mix(c, zc == 0 ? vec3(1.0) : (zc == 1 ? vec3(0.0) : vec3(1.0, 0.1, 0.1)), uZ.w);
        }
    }
    if (uK.x > 0.5) {
        float m[9];
        for (int j = 0; j < 3; j++)
            for (int i = 0; i < 3; i++)
                m[j * 3 + i] = Y(texelFetch(sTD2DInputs[0], clamp(P + ivec2(i - 1, j - 1), ivec2(0), R - 1), 0).rgb);
        float gx = (m[2] + 2.0 * m[5] + m[8]) - (m[0] + 2.0 * m[3] + m[6]);
        float gy = (m[6] + 2.0 * m[7] + m[8]) - (m[0] + 2.0 * m[1] + m[2]);
        if (sqrt(gx * gx + gy * gy) * 0.25 > uK.y) {
            int k = clamp(int(uK.z + 0.5), 0, 4);
            c = k == 0 ? vec3(1.0, 0.1, 0.1) : (k == 1 ? vec3(1.0, 0.9, 0.1) : (k == 2 ? vec3(0.2, 0.5, 1.0)
              : (k == 3 ? vec3(1.0) : vec3(0.2, 1.0, 0.3))));
        }
    }
    if (uFc.w > 0.5) {
        bool blink = fract(t * 2.0) < 0.5;
        if (max(max(src.r, src.g), src.b) >= uCl.x && blink) c = vec3(1.0, 0.0, 0.85);
        else if (y <= uCl.y && blink) c = vec3(0.0, 0.25, 1.0);
    }
    // ---- overlays
    int hk = clamp(int(uGd.w + 0.5), 0, 3);
    vec3 H = hk == 0 ? vec3(1.0) : (hk == 1 ? vec3(1.0, 0.9, 0.25) : (hk == 2 ? vec3(0.35, 1.0, 0.45) : vec3(0.35, 0.9, 1.0)));
    float s = max(uTx.x, 1.0), M = uTx.y;
    vec4 fr = vec4(0.0, 0.0, W);
    if (uGd.x > 0.0) {
        float a = uGd.x;
        if (W.x / W.y > a) fr = vec4((W.x - W.y * a) * 0.5, 0.0, W.y * a, W.y);
        else fr = vec4(0.0, (W.y - W.x / a) * 0.5, W.x, W.x / a);
        vec2 q = pd - fr.xy;
        if (q.x < 0.0 || q.y < 0.0 || q.x >= fr.z || q.y >= fr.w) c *= 1.0 - uGd.y;
        if (rectLine(pd, fr, 2.0) > 0.0) c = mix(c, H, 0.8);
    }
    if (uOv2.x > 0.5) {
        for (int k = 0; k < 2; k++) {
            float f = k == 0 ? uOv2.y : uOv2.z;
            vec4 r = vec4(fr.xy + fr.zw * (1.0 - f) * 0.5, fr.zw * f);
            if (rectLine(pd, r, 2.0) > 0.0) c = mix(c, H, 0.55);
        }
    }
    if (uOv2.w > 0.5) {
        vec2 d = abs(pd - (fr.xy + fr.zw * 0.5));
        if ((d.x < 1.0 && d.y < 5.0 * s) || (d.y < 1.0 && d.x < 5.0 * s)) c = H;
    }
    if (uGd.z > 0.5) {
        float L = 12.0 * s, th = max(2.0, 0.5 * s);
        vec4 r = vec4(fr.xy + M, fr.zw - 2.0 * M);
        vec2 a = pd - r.xy, b = r.xy + r.zw - pd;
        vec2 nr = min(a, b);
        bool inb = a.x >= 0.0 && a.y >= 0.0 && b.x >= 0.0 && b.y >= 0.0;
        if (inb && ((nr.x < th && nr.y < L) || (nr.y < th && nr.x < L))) c = H;
    }
    int rec = int(uOv.x + 0.5);
    if (rec == 2) {
        vec2 dc = pd - vec2(M + 4.0 * s, M + 4.0 * s);
        if (dot(dc, dc) < 10.0 * s * s && fract(t * max(uOv.y, 0.0)) < 0.5) c = vec3(1.0, 0.08, 0.08);
        int k = textAt(pd, vec2(M + 9.0 * s, M), s, 0, 3);
        if (k > 0) c = k == 2 ? vec3(1.0, 0.15, 0.15) : vec3(0.0);
    } else if (rec == 1) {
        int k = textAt(pd, vec2(M, M), s, 1, 4);
        if (k > 0) c = k == 2 ? H : vec3(0.0);
    }
    if (uOv.z > 0.5) {
        int k = textAt(pd, vec2(W.x - M - 88.0 * s, M), s, 2, 11);
        if (k > 0) c = k == 2 ? H : vec3(0.0);
    }
    if (uOv.w >= 0.0) {
        vec4 bx = vec4(W.x - M - 15.0 * s, M + 11.0 * s, 13.0 * s, 6.0 * s);
        float th = max(1.0, 0.75 * s);
        if (rectLine(pd, bx, th) > 0.0) c = H;
        vec4 nub = vec4(bx.x + bx.z, bx.y + 1.5 * s, s, 3.0 * s);
        vec2 qn = pd - nub.xy;
        if (qn.x >= 0.0 && qn.y >= 0.0 && qn.x < nub.z && qn.y < nub.w) c = H;
        vec2 qf = pd - (bx.xy + 2.0 * th);
        vec2 fsz = vec2((bx.z - 4.0 * th) * clamp(uOv.w, 0.0, 1.0), bx.w - 4.0 * th);
        if (qf.x >= 0.0 && qf.y >= 0.0 && qf.x < fsz.x && qf.y < fsz.y)
            c = uOv.w < 0.2 ? vec3(1.0, 0.15, 0.1) : H;
    }
    int ln = int(uTx.z + 0.5);
    if (ln > 0) {
        int k = textAt(pd, vec2(M, W.y - M - 8.0 * s), s, 3, min(ln, 16));
        if (k > 0) c = k == 2 ? H : vec3(0.0);
    }
    vec4 o = vec4(clamp(c, 0.0, 1.0), src.a);
    TDImageStoreOutput(0, ivec3(P, 0), mix(src, o, uCl.w));
}
