// FSR 1 RCAS (robust contrast-adaptive sharpening), compute GLSL TOP, shared file (no COMP). Port of AMD
// FidelityFX FSR 1 `FsrRcasF` (ffx_fsr1.h, MIT, (c) Advanced Micro Devices; via libretro slang-shaders), float
// path, with the optional FSR_RCAS_DENOISE term, written for TD 2025.31550 compute. Mirror: builders/fsr_logic.py
// (rcas). Research: FX7a SX-10. Runs at the input's own size (EASU output), input 0 only.
// 5 taps (b / d e f / h), one negative lobe for all channels, limited so a [0, 1] picture stays in [0, 1]
// (FSR_RCAS_LIMIT 0.25 - 1/16); values above 1 (HDR glow) get no sharpening. The lobe is applied to rgba alike
// (premultiplied stays consistent; alpha joins the limit). uRcas: x = sharpness in stops (0 = strongest, +1 = half), y = denoise 0 / 1,
// z = on (0 = exact texelFetch passthrough). No loops.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uRcas;
#define FSR_RCAS_LIMIT (0.25 - (1.0 / 16.0))
float rluma(vec4 c) { return c.b * 0.5 + (c.r * 0.5 + c.g); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 e = texelFetch(sTD2DInputs[0], p, 0);
    if (uRcas.z <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), e); return; }
    ivec2 hi = isz - 1;
    vec4 b = texelFetch(sTD2DInputs[0], clamp(p + ivec2(0, -1), ivec2(0), hi), 0);
    vec4 d = texelFetch(sTD2DInputs[0], clamp(p + ivec2(-1, 0), ivec2(0), hi), 0);
    vec4 f = texelFetch(sTD2DInputs[0], clamp(p + ivec2(1, 0), ivec2(0), hi), 0);
    vec4 h = texelFetch(sTD2DInputs[0], clamp(p + ivec2(0, 1), ivec2(0), hi), 0);
    float bL = rluma(b), dL = rluma(d), eL = rluma(e), fL = rluma(f), hL = rluma(h);
    float nz = 0.25 * bL + 0.25 * dL + 0.25 * fL + 0.25 * hL - eL;
    float rng = max(max(max(bL, dL), max(eL, fL)), hL) - min(min(min(bL, dL), min(eL, fL)), hL);
    nz = rng > 0.0 ? clamp(abs(nz) / rng, 0.0, 1.0) : 0.0;
    nz = -0.5 * nz + 1.0;
    vec4 mn4 = min(min(b, d), min(f, h));
    vec4 mx4 = max(max(b, d), max(f, h));
    vec4 hitMin = min(mn4, e) / max(4.0 * mx4, vec4(1e-20));
    vec4 hitMax = (1.0 - max(mx4, e)) / min(4.0 * mn4 - 4.0, vec4(-1e-20));
    vec4 lobeC = max(-hitMin, hitMax);              // alpha joins the limit, so it also stays in [0, 1] ...
    if (max(mx4.a, e.a) <= min(mn4.a, e.a)) lobeC.a = -FSR_RCAS_LIMIT;   // ... unless it is flat (opaque areas)
    float lobe = max(-FSR_RCAS_LIMIT, min(max(max(lobeC.r, lobeC.g), max(lobeC.b, lobeC.a)), 0.0)) * exp2(-uRcas.x);
    if (uRcas.y > 0.5) lobe *= nz;
    float rcpL = 1.0 / (4.0 * lobe + 1.0);
    TDImageStoreOutput(0, ivec3(p, 0), (lobe * (b + d + f + h) + e) * rcpL);
}
