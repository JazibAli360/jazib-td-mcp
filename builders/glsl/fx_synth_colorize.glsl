// FX_synth colorize (compute, T-47; FX2 AV-22 + FX1 DG-22). Paik/Abe phase colour and Sandin colour encoder: grey
// levels become colour through three offset functions, then the overflow stage (clip / wrap / fold / solarize) is
// the overdriven amplifier. = builders/fx_synth_logic.py colorize(). in0 = picture. Amount 0 = texelFetch (exact).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, mode (0 channels 1 hue), source (luma rgb red green blue), function (sine tri saw ramp)
uniform vec4 uB;   // overflow (clip wrap fold solarize), drive, bias, solar threshold
uniform vec4 uG;   // gain r g b, invert
uniform vec4 uP;   // phase r g b, drift (cycles/s)
uniform vec4 uH;   // hue gain, hue phase, saturation, value follow
uniform vec4 uT;   // time s
const float TAU = 6.28318530718;
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
vec3 hsv2rgb(float h, float s, float v) {
    vec3 k = clamp(abs(fract(h + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    return v * mix(vec3(1.0), k, s);
}
vec3 func(vec3 v, int f) {
    if (f == 0) return 0.5 - 0.5 * cos(TAU * v);
    if (f == 1) return 1.0 - abs(1.0 - 2.0 * fract(v));
    if (f == 2) return fract(v);
    return v;
}
vec3 overflow(vec3 y, int o, float T) {
    if (o == 0) return clamp(y, 0.0, 1.0);
    if (o == 1) return mix(y, fract(y), vec3(lessThan(y, vec3(0.0))) + vec3(greaterThan(y, vec3(1.0))));
    if (o == 2) return 1.0 - abs(1.0 - mod(y, 2.0));
    vec3 s = mix(y, 2.0 * T - y, vec3(greaterThan(y, vec3(T))));
    return clamp(s, 0.0, 1.0);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= sz.x || p.y >= sz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }
    int src = int(uA.z + 0.5);
    vec3 x;
    if (src == 0) x = vec3(lum(c.rgb));
    else if (src == 1) x = c.rgb;
    else x = vec3(c[src - 2]);
    if (uG.w > 0.5) x = 1.0 - x;
    vec3 y;
    if (uA.y < 0.5) {
        y = func(x * uG.xyz + uP.xyz + uP.w * uT.x, int(uA.w + 0.5));
    } else {
        float xs = src == 1 ? lum(x) : x.r;
        y = hsv2rgb(uH.x * xs + uH.y + uP.w * uT.x, uH.z, mix(1.0, xs, uH.w));
    }
    y = overflow(y * uB.y + uB.z, int(uB.x + 0.5), uB.w);
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(y, c.a), uA.x));
}
