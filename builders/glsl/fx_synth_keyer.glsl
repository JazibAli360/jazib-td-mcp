// FX_synth keyer (compute, T-47; FX2 AV-24 keyers + blend matrix + video logic). Keys: luma window, chroma
// (CbCr distance, BT.709), shape key generator (wipes / iris / diamond / box / clock, Cadet-style fader), B luma,
// A alpha, one. Two keys combine by logic (and/or/xor/a-not-b/multiply/a>b), then the op uses the key: key = A over
// B, matte, alpha, or a blend (add/multiply/min/max/difference/bitwise xor-and-or on 8-bit levels) applied where the
// key is 1. = builders/fx_synth_logic.py keyer(). in0 = A (picture), in1 = B (b_fit). Amount 0 = texelFetch (exact).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, key a (luma chroma shape bluma alpha one), key b (none + same), logic
uniform vec4 uB;   // invert, op, b source (colour top), spill
uniform vec4 uC;   // luma low, luma high, softness, 0
uniform vec4 uD;   // chroma key colour rgb, tolerance
uniform vec4 uE;   // chroma softness, shape, position, shape softness
uniform vec4 uF;   // centre x y, angle deg, 0
uniform vec4 uG;   // B colour rgb, 0
const float TAU = 6.28318530718;
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
float rise(float x, float e, float s) { return s > 0.0 ? clamp((x - e) / s + 0.5, 0.0, 1.0) : (x >= e ? 1.0 : 0.0); }
vec2 cbcr(vec3 c) { float y = lum(c); return vec2((c.b - y) / 1.8556, (c.r - y) / 1.5748); }
vec2 rot(vec2 d, float ca, float sa) { return vec2(d.x * ca + d.y * sa, -d.x * sa + d.y * ca); }
float metric(vec2 d, int sh) { return sh == 3 ? abs(d.x) + abs(d.y) : max(abs(d.x), abs(d.y)); }
float shapeField(vec2 P, vec2 S) {
    vec2 C = uF.xy * S;
    float a = radians(uF.z), ca = cos(a), sa = sin(a);
    int sh = int(uE.y + 0.5);
    vec2 n = P / S - 0.5;
    if (sh == 0) return n.x * ca + n.y * sa + 0.5;
    if (sh == 1) return -n.x * sa + n.y * ca + 0.5;
    vec2 d = P - C;
    vec2 k[4] = vec2[4](-C, vec2(S.x, 0.0) - C, vec2(0.0, S.y) - C, S - C);
    if (sh == 2) {
        float R = max(max(length(k[0]), length(k[1])), max(length(k[2]), length(k[3])));
        return length(d) / max(R, 1e-6);
    }
    vec2 r = rot(d, ca, sa);
    if (sh == 3 || sh == 4) {
        float R = 0.0;
        for (int i = 0; i < 4; i++) R = max(R, metric(rot(k[i], ca, sa), sh));
        return metric(r, sh) / max(R, 1e-6);
    }
    return fract(atan(r.x, r.y) / TAU + 1.0);
}
float logic(float a, float b, int lg) {
    if (lg == 0) return a;
    if (lg == 1) return min(a, b);
    if (lg == 2) return max(a, b);
    if (lg == 3) return abs(a - b);
    if (lg == 4) return min(a, 1.0 - b);
    if (lg == 5) return a * b;
    return a > b ? 1.0 : 0.0;
}
vec3 bits(vec3 a, vec3 b, int op) {
    uvec3 ua = uvec3(floor(clamp(a, 0.0, 1.0) * 255.0 + 0.5));
    uvec3 ub = uvec3(floor(clamp(b, 0.0, 1.0) * 255.0 + 0.5));
    uvec3 r = op == 8 ? (ua ^ ub) : (op == 9 ? (ua & ub) : (ua | ub));
    return vec3(r) / 255.0;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= sz.x || p.y >= sz.y) return;
    vec4 A0 = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), A0); return; }
    vec4 B = uB.z > 0.5 ? texelFetch(sTD2DInputs[1], p, 0) : vec4(uG.xyz, 1.0);
    float lA = lum(A0.rgb);
    float keys[6];
    keys[0] = rise(lA, uC.x, uC.z) * (1.0 - rise(lA, uC.y, uC.z));
    keys[1] = rise(length(cbcr(A0.rgb) - cbcr(uD.xyz)), uD.w, uE.x);
    keys[2] = 1.0 - rise(shapeField(vec2(p) + 0.5, vec2(sz)), uE.z, uE.w);
    keys[3] = rise(lum(B.rgb), uC.x, uC.z);
    keys[4] = A0.a;
    keys[5] = 1.0;
    float k = keys[clamp(int(uA.y + 0.5), 0, 5)];
    int kb = int(uA.z + 0.5);
    if (kb > 0) k = logic(k, keys[clamp(kb - 1, 0, 5)], int(uA.w + 0.5));
    if (uB.x > 0.5) k = 1.0 - k;
    vec4 A = A0;
    vec2 kd = cbcr(uD.xyz);
    if (uB.w > 0.0 && length(kd) > 1e-6) {
        kd = normalize(kd);
        vec2 v = cbcr(A.rgb);
        v -= uB.w * max(dot(v, kd), 0.0) * kd;
        float y = lum(A.rgb);
        float r = y + 1.5748 * v.y, b = y + 1.8556 * v.x;
        A.rgb = vec3(r, (y - 0.2126 * r - 0.0722 * b) / 0.7152, b);
    }
    int op = int(uB.y + 0.5);
    vec4 o;
    if (op == 0) o = mix(B, A, k);
    else if (op == 1) o = vec4(vec3(k), 1.0);
    else if (op == 2) o = vec4(A.rgb * k, k);
    else {
        vec3 C;
        if (op == 3) C = A.rgb + B.rgb;
        else if (op == 4) C = A.rgb * B.rgb;
        else if (op == 5) C = min(A.rgb, B.rgb);
        else if (op == 6) C = max(A.rgb, B.rgb);
        else if (op == 7) C = abs(A.rgb - B.rgb);
        else C = bits(A.rgb, B.rgb, op);
        o = vec4(mix(A.rgb, C, k), A.a);
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(A0, o, uA.x));
}
