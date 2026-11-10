// FX_synth vfeedback loop (compute, T-47; FX2 AV-28 camera at its own monitor, Crutchfield). One generation per
// cook: mirror (in-loop fold) -> lens (rotate / zoom about the centre, shift, barrel K) -> sample the previous state
// (edge black = the monitor's border, or mirror / repeat / clamp) -> camera blur -> gain, gamma, contrast, hue step
// (about the grey axis), saturation -> monitor RGB stripe mask in the loop (moire) -> autogain toward Target (stamp
// mean) -> live picture keyed in (mix / luma above / luma below, Inject + Kick) -> noise -> clamp 0..1. 16-bit float.
// = builders/fx_synth_logic.py vf_coords / vf_tap / vf_colour / vf_step. in0 = live, in1 = previous state (Feedback
// TOP, or the delay Cache TOP), in2 = stamp (z = 0 fresh -> restart from live; w = mean luma of the previous state).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // inject, key mode (mix above below), key, key softness
uniform vec4 uB;   // kick, gain, reset, seed
uniform vec4 uC;   // zoom, rotate deg, shift x px, shift y px
uniform vec4 uD;   // centre x, centre y, barrel, mirror (none x y quad)
uniform vec4 uE;   // edge (black mirror repeat clamp), blur 0..1, radius px, gamma
uniform vec4 uF;   // contrast, hue step deg, saturation, mask 0..1
uniform vec4 uG;   // mask pitch px, noise, autogain, target
uniform vec4 uH;   // frame, 0, 0, 0
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
float rise(float x, float e, float s) { return s > 0.0 ? clamp((x - e) / s + 0.5, 0.0, 1.0) : (x >= e ? 1.0 : 0.0); }
uint pcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                   return (w >> 22u) ^ w; }
float h(uvec4 k) { return float(pcg(k.x ^ pcg(k.y ^ pcg(k.z ^ pcg(k.w)))) >> 8) / 16777215.0; }
vec2 edgep(vec2 q, vec2 sz, int e) {
    if (e == 1) { vec2 t = mod(q, 2.0 * sz); return min(t, 2.0 * sz - t); }
    if (e == 2) return mod(q, sz);
    return clamp(q, vec2(0.5), sz - 0.5);
}
// Bilinear by hand from 4 texelFetches in float32: the sampler's fixed-point weights drifted the identity loop
// (live 31550: Zoom 1, Rotate 0 changed 9.5 % of texels by up to 0.005 over 11 generations); exact at whole-pixel
// offsets now. Neighbours are clamped like the sampler's hold (= fx_synth_logic.bilinear).
vec3 tap(vec2 q, vec2 sz, int e) {
    if (e == 0 && (any(lessThan(q, vec2(0.0))) || any(greaterThan(q, sz)))) return vec3(0.0);
    vec2 u = edgep(q, sz, e) - 0.5;
    vec2 i0 = floor(u);
    vec2 f = u - i0;
    ivec2 isz = ivec2(sz);
    ivec2 a = clamp(ivec2(i0), ivec2(0), isz - 1), b = clamp(ivec2(i0) + 1, ivec2(0), isz - 1);
    vec3 c00 = texelFetch(sTD2DInputs[1], a, 0).rgb, c10 = texelFetch(sTD2DInputs[1], ivec2(b.x, a.y), 0).rgb;
    vec3 c01 = texelFetch(sTD2DInputs[1], ivec2(a.x, b.y), 0).rgb, c11 = texelFetch(sTD2DInputs[1], b, 0).rgb;
    return mix(mix(c00, c10, f.x), mix(c01, c11, f.x), f.y);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec2 sz = vec2(isz);
    vec4 live = texelFetch(sTD2DInputs[0], p, 0);
    vec4 st = texelFetch(sTD2DInputs[2], ivec2(0), 0);
    if (st.z < 0.5 || uB.z > 0.5) { TDImageStoreOutput(0, ivec3(p, 0), live); return; }
    vec2 C = uD.xy * sz;
    vec2 x = vec2(p) + 0.5;
    int mi = int(uD.w + 0.5);
    if (mi == 1 || mi == 3) x.x = C.x - abs(x.x - C.x);
    if (mi == 2 || mi == 3) x.y = C.y - abs(x.y - C.y);
    float a = radians(uC.y);
    vec2 d = x - C;
    vec2 q = C + vec2(cos(a) * d.x + sin(a) * d.y, -sin(a) * d.x + cos(a) * d.y) / max(uC.x, 1e-4) - uC.zw;
    if (uD.z != 0.0) {
        vec2 n = (q - C) / (0.5 * sz.y);
        q = C + (q - C) * (1.0 + uD.z * dot(n, n));
    }
    int e = int(uE.x + 0.5);
    vec3 c = tap(q, sz, e);
    if (uE.y > 0.0) {
        float r = uE.z;
        vec3 acc = c + tap(q - vec2(r, 0.0), sz, e) + tap(q + vec2(r, 0.0), sz, e)
                     + tap(q - vec2(0.0, r), sz, e) + tap(q + vec2(0.0, r), sz, e);
        c = mix(c, acc * 0.2, uE.y);
    }
    c *= uB.y;
    c = pow(max(c, 0.0), vec3(uE.w));
    c = (c - 0.5) * uF.x + 0.5;
    if (uF.y != 0.0) {
        float ha = radians(uF.y);
        vec3 k = vec3(0.57735026919);
        c = c * cos(ha) + cross(k, c) * sin(ha) + k * dot(k, c) * (1.0 - cos(ha));
    }
    float y = lum(c);
    c = y + (c - y) * uF.z;
    if (uF.w > 0.0) {
        int sp = int(mod(floor(float(p.x) / max(uG.x, 1.0)), 3.0));
        vec3 m = vec3(sp == 0 ? 3.0 : 0.0, sp == 1 ? 3.0 : 0.0, sp == 2 ? 3.0 : 0.0);
        c *= mix(vec3(1.0), m, uF.w);
    }
    if (uG.z > 0.0) {
        float mean = st.w;
        float g = uG.w / max(mean, 0.02);
        c = c * (1.0 + (g - 1.0) * 0.2 * uG.z) + (uG.w - mean) * 0.05 * uG.z;
    }
    float ll = lum(live.rgb);
    int km = int(uA.y + 0.5);
    float kk = km == 0 ? 1.0 : (km == 1 ? rise(ll, uA.z, uA.w) : 1.0 - rise(ll, uA.z, uA.w));
    c = mix(c, live.rgb, clamp(uA.x * kk + uB.x, 0.0, 1.0));
    if (uG.y > 0.0) {
        uvec4 key = uvec4(uvec2(p), uint(uH.x), uint(uB.w) * 7919u);
        c += (vec3(h(key), h(key ^ uvec4(0u, 0u, 0u, 1u)), h(key ^ uvec4(0u, 0u, 0u, 2u))) - 0.5) * uG.y;
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(clamp(c, 0.0, 1.0), live.a));
}
