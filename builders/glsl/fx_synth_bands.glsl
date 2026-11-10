// FX_synth bands (compute, T-47; FX2 AV-23 amplitude classifier + FX5 G24 contour lines). The signal is cut into
// Bands iso-level bands (Sandin amplitude classifier), each filled with a colour; the band edges are drawn as
// constant-width contour lines (distance to the threshold / |gradient|, central differences). Offset / Speed /
// Wobble move every threshold, so contours flow over the picture. = builders/fx_synth_logic.py bands().
// in0 = picture. Amount 0 = texelFetch (exact).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, source (luma red green blue), bands, curve (gamma before banding)
uniform vec4 uB;   // offset (bands), speed (bands/s), wobble (bands), wobble rate (Hz)
uniform vec4 uC;   // softness (band units), fill (source grey rainbow duotone), fill amount, background (source black)
uniform vec4 uD;   // line width px (0 off), line opacity, major every N (0 off), major width x
uniform vec4 uE;   // line colour rgb, hue span
uniform vec4 uF;   // colour A rgb, hue offset
uniform vec4 uG;   // colour B rgb, time s
const float TAU = 6.28318530718;
ivec2 SZ;
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
vec3 hsv2rgb(float h, float s, float v) {
    vec3 k = clamp(abs(fract(h + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    return v * mix(vec3(1.0), k, s);
}
float sig(ivec2 q) {
    vec4 c = texelFetch(sTD2DInputs[0], clamp(q, ivec2(0), SZ - 1), 0);
    int s = int(uA.y + 0.5);
    float v = s == 0 ? lum(c.rgb) : c[s - 1];
    return pow(max(v, 0.0), uA.w);
}
vec3 fillc(float k, float ph, float N, vec3 c, float x0) {
    float kk = k - N * floor(k / N);
    float q = clamp((k + 0.5 - ph) / N, 0.0, 1.0);
    int f = int(uC.y + 0.5);
    if (f == 0) return clamp(c * (q / max(x0, 1e-4)), 0.0, 1.0);
    if (f == 1) return vec3(q);
    if (f == 2) return hsv2rgb(uF.w + uE.w * kk / N, 1.0, 1.0);
    return mix(uF.xyz, uG.xyz, q);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    SZ = textureSize(sTD2DInputs[0], 0);
    if (p.x >= SZ.x || p.y >= SZ.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }
    float N = max(floor(uA.z + 0.5), 1.0);
    float t = uG.w;
    float ph = uB.x + uB.y * t + uB.z * sin(TAU * uB.w * t);
    float x0 = sig(p);
    float f0 = x0 * N + ph;
    float k = floor(f0);
    float tt = f0 - k;
    vec3 col = fillc(k, ph, N, c.rgb, x0);
    float s = uC.x;
    if (s > 0.0) {
        if (tt < 0.5) col = mix(fillc(k - 1.0, ph, N, c.rgb, x0), col, smoothstep(-s * 0.5, s * 0.5, tt));
        else col = mix(col, fillc(k + 1.0, ph, N, c.rgb, x0), smoothstep(1.0 - s * 0.5, 1.0 + s * 0.5, tt));
    }
    vec3 base = uC.w > 0.5 ? vec3(0.0) : c.rgb;
    vec3 o = mix(base, col, uC.z);
    if (uD.x > 0.0) {
        float gx = (sig(p + ivec2(1, 0)) - sig(p - ivec2(1, 0))) * N * 0.5;
        float gy = (sig(p + ivec2(0, 1)) - sig(p - ivec2(0, 1))) * N * 0.5;
        float dpx = min(tt, 1.0 - tt) / max(length(vec2(gx, gy)), 1e-6);
        float n = floor(f0 + 0.5);
        float mj = floor(uD.z + 0.5);
        float w = uD.x;
        if (mj > 0.0 && n - mj * floor(n / mj) == 0.0) w *= uD.w;
        float cov = clamp(w * 0.5 + 0.5 - dpx, 0.0, 1.0);
        o = mix(o, uE.xyz, cov * uD.y);
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(o, c.a), uA.x));
}
