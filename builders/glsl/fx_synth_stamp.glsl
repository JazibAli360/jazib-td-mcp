// FX_synth stamp + meter (T-111, as FX_glitch feedbackkill): 1x1 rgba32float in place (outputaccess readwrite,
// clearoutputs off), ONE 16x16 workgroup (manual dispatch 1x1x1). x = now, y = previous cook, z = cooks since fresh
// (a gap > 0.25 s = the slot was bypassed -> the loop restarts from live), w = mean luma of in0 (the previous state)
// on a 64x64 texel grid (= builders/fx_synth_logic.py mean_grid / vf_mean). A second cook in the same frame (a
// readback, T-116 (4) / T-117 (4)) keeps the stored values. Used by scanimate (trail) and vfeedback (loop).
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uT;   // now (absTime.seconds)
shared float sm[256];
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
void main() {
    uint t = gl_LocalInvocationIndex;
    ivec2 sz = textureSize(sTD2DInputs[0], 0);
    ivec2 l = ivec2(gl_LocalInvocationID.xy);
    float acc = 0.0;
    for (int j = 0; j < 4; j++) {
        for (int i = 0; i < 4; i++) {
            ivec2 gp = l * 4 + ivec2(i, j);
            ivec2 q = clamp(ivec2((vec2(gp) + 0.5) / 64.0 * vec2(sz)), ivec2(0), sz - 1);
            acc += lum(texelFetch(sTD2DInputs[0], q, 0).rgb);
        }
    }
    sm[t] = acc / 16.0;
    barrier();
    for (uint s = 128u; s > 0u; s >>= 1u) {
        if (t < s) sm[t] += sm[t + s];
        barrier();
    }
    if (t == 0u) {
        vec4 o = TDImageLoadOutput(0, ivec3(0));
        if (uT.x == o.x) return;
        bool fresh = uT.x - o.x > 0.25 || uT.x < o.x;
        TDImageStoreOutput(0, ivec3(0), vec4(uT.x, o.x, fresh ? 0.0 : o.z + 1.0, sm[0] / 256.0));
    }
}
