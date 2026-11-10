// FX_scope scopes display (compute, input size, useinput): the bins texture drawn as waveform / RGB parade /
// vectorscope / histogram inside the panel, broadcast graticule (levels at 0 25 50 75 100 %, legal 16/235 dashed,
// 75 / 100 % bar targets, skin line, histogram quarters), over the dimmed picture. Outside the panel: in0 exact.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uPn;   // panel x0 y0 w h (output px)
uniform vec4 uD;    // mode, Sx, Sy, levels
uniform vec4 uD2;   // bins B, gain, colour (0 green, 1 white, 2 colour), log scale
uniform vec4 uD3;   // graticule opacity, matrix, bar amplitude, skin line on
uniform vec4 uD4;   // bg dim, amount, vectorscope zoom, legal lines on
float gl1(float q, float div, float px) { return clamp(1.0 - abs(fract(q * div + 0.5) - 0.5) * px / max(div, 1.0), 0.0, 1.0); }
vec3 tint(int cm) { return cm == 1 ? vec3(0.95) : vec3(0.35, 1.0, 0.45); }
float inten(float n, float ref) { return 1.0 - exp(-uD2.y * n / max(ref, 1.0)); }
vec2 cbcr(vec3 c, vec3 K) { float y = dot(c, K); return vec2((c.b - y) / (2.0 * (1.0 - K.b)), (c.r - y) / (2.0 * (1.0 - K.r))); }
float boxLine(vec2 p, vec2 c, float h, float px) {   // outline of a square of half-size h at c, px per unit
    vec2 d = abs(p - c);
    float m = max(d.x, d.y);
    return (abs(m - h) * px < 1.0) ? 1.0 : 0.0;
}
void main() {
    ivec2 P = ivec2(gl_GlobalInvocationID.xy);
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    if (P.x >= R.x || P.y >= R.y) return;
    vec4 src = texelFetch(sTD2DInputs[0], P, 0);
    vec2 q = (vec2(P) + 0.5 - uPn.xy) / uPn.zw;
    if (q.x < 0.0 || q.y < 0.0 || q.x >= 1.0 || q.y >= 1.0) { TDImageStoreOutput(0, ivec3(P, 0), src); return; }
    int mode = int(uD.x + 0.5), Sx = int(uD.y + 0.5), Sy = int(uD.z + 0.5), lv = int(uD.w + 0.5);
    int B = int(uD2.x + 0.5), cm = int(uD2.z + 0.5);
    vec3 K = uD3.y < 0.5 ? vec3(0.2126, 0.7152, 0.0722) : vec3(0.299, 0.587, 0.114);
    vec3 tr = vec3(0.0);
    float g = 0.0;
    vec2 S = uPn.zw;
    if (mode == 0 || mode == 1) {
        int pan = mode == 1 ? min(int(q.x * 3.0), 2) : 0;
        float u = mode == 1 ? fract(q.x * 3.0) : q.x;
        ivec2 b = ivec2(min(int(u * float(Sx)), Sx - 1) + pan * Sx, min(int(q.y * float(lv)), lv - 1));
        float n = texelFetch(sTD2DInputs[1], b, 0).r;
        vec3 c = tint(cm);
        if (mode == 1 && cm == 2) c = pan == 0 ? vec3(1.0, 0.25, 0.2) : (pan == 1 ? vec3(0.25, 1.0, 0.3) : vec3(0.3, 0.45, 1.0));
        tr = c * inten(n, float(Sy) / 64.0);
        g = gl1(q.y, 4.0, S.y);
        if (uD4.w > 0.5) {
            float dl = min(abs(q.y - 16.0 / 255.0), abs(q.y - 235.0 / 255.0)) * S.y;
            if (dl < 0.75 && fract(q.x * S.x / 8.0) < 0.5) g = 1.0;
        }
        if (mode == 1) g = max(g, max(clamp(1.0 - abs(q.x - 1.0 / 3.0) * S.x, 0.0, 1.0), clamp(1.0 - abs(q.x - 2.0 / 3.0) * S.x, 0.0, 1.0)));
    } else if (mode == 2) {
        float z = max(uD4.z, 0.01);
        vec2 v = (q - 0.5) / z;                            // Cb, Cr
        float px = min(S.x, S.y) * z;                      // panel px per unit
        if (abs(v.x) <= 0.5 && abs(v.y) <= 0.5) {
            ivec2 b = clamp(ivec2(floor((v + 0.5) * float(B))), ivec2(0), ivec2(B - 1));
            float n = texelFetch(sTD2DInputs[1], b, 0).r;
            vec3 c = tint(cm);
            if (cm == 2) {                                 // the colour that sits at this Cb / Cr (luma 0.6)
                float y = 0.6;
                vec3 rgb = vec3(y + 2.0 * (1.0 - K.r) * v.y, 0.0, y + 2.0 * (1.0 - K.b) * v.x);
                rgb.g = (y - K.r * rgb.r - K.b * rgb.b) / K.g;
                c = clamp(rgb, 0.0, 1.0) * 0.8 + 0.2;
            }
            tr = c * inten(n, float(Sx * Sy) / 16384.0);
        }
        float r = length(v);
        g = clamp(1.0 - abs(r - 0.5) * px, 0.0, 1.0);
        g = max(g, max(clamp(1.0 - abs(q.x - 0.5) * S.x, 0.0, 1.0) * step(abs(v.y), 0.03),
                       clamp(1.0 - abs(q.y - 0.5) * S.y, 0.0, 1.0) * step(abs(v.x), 0.03)));
        vec3 cols[6] = vec3[6](vec3(1, 0, 0), vec3(1, 1, 0), vec3(0, 1, 0), vec3(0, 1, 1), vec3(0, 0, 1), vec3(1, 0, 1));
        for (int i = 0; i < 6; i++) g = max(g, boxLine(v, cbcr(cols[i] * uD3.z, K), 0.025, px));
        if (uD3.w > 0.5) {                                 // skin-tone line, 123 deg from +Cb
            vec2 dir = vec2(cos(radians(123.0)), sin(radians(123.0)));
            float t = dot(v, dir);
            if (t > 0.0 && t < 0.5 && abs(v.x * dir.y - v.y * dir.x) * px < 0.75) g = max(g, 0.8);
        }
    } else {
        int b = min(int(q.x * float(lv)), lv - 1);
        vec3 cc[4] = vec3[4](vec3(1.0, 0.2, 0.2), vec3(0.2, 1.0, 0.3), vec3(0.3, 0.45, 1.0), vec3(0.8));
        for (int k = 0; k < 4; k++) {
            vec2 t = texelFetch(sTD2DInputs[1], ivec2(b, k), 0).rg;
            float h = uD2.w > 0.5 ? log(1.0 + t.x) / max(log(1.0 + t.y), 1e-6) : t.x / max(t.y, 1.0);
            if (q.y < h) tr += cc[k] * (k == 3 ? 0.35 : 0.55);
        }
        g = gl1(q.x, 4.0, S.x);
    }
    vec3 base = src.rgb * (1.0 - uD4.x);
    vec4 o = vec4(base + tr + uD3.x * g * vec3(0.75, 0.7, 0.55), max(src.a, uD4.x));
    o = clamp(mix(src, o, uD4.y), 0.0, 1.0);
    TDImageStoreOutput(0, ivec3(P, 0), o);
}
