// FX_scope shared constants + helpers (path + beam passes; mirrors builders/fx_scope_logic.py). ASCII only.
#define CAP 16384
#define ROWW 1024
#define CAPROW 16
#define CH 256
const float SQ2PI = 2.5066282746310002;
const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);
float erfA(float x) {                         // Abramowitz-Stegun 7.1.26, |error| < 1.5e-7 (logic.erf_as)
    float s = sign(x);
    float a = abs(x);
    float t = 1.0 / (1.0 + 0.3275911 * a);
    float p = ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t;
    return s * (1.0 - p * exp(-a * a));
}
uint hashU(uint x) {
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
    return x;
}
float hash01(uint x) { return float(hashU(x) >> 8) * (1.0 / 16777216.0); }
float packRGB(vec3 c) {
    uvec3 q = uvec3(clamp(c, 0.0, 1.0) * 255.0 + 0.5);
    return float((q.r << 16) | (q.g << 8) | q.b);
}
vec3 unpackRGB(float f) {
    uint u = uint(round(f));                  // not f + 0.5: 16777215.5 rounds to 2^24 in float32 (white -> black)
    return vec3(float((u >> 16) & 255u), float((u >> 8) & 255u), float(u & 255u)) / 255.0;
}
vec3 hsv2rgb(float h) {
    vec3 k = mod(vec3(5.0, 3.0, 1.0) + fract(h) * 6.0, 6.0);
    return 1.0 - clamp(min(k, 4.0 - k), 0.0, 1.0);
}
