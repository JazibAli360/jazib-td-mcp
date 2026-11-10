// FX_scope video-scope bins (compute, T-47): counts of the sampled input (every `step` px) as a bins texture
// (rgba32float, r = count, g = row max for histogram). One workgroup = one tile of <= 1024 bins in shared memory,
// filled with shared atomicAdd (no image atomics: unverified on MoltenVK). Layout (logic.hist_ref):
//   0 waveform  (Sx x levels): column = sample column, row = luma level      tile = cpt columns x levels
//   1 parade    (3 Sx x levels): R | G | B panels                             tile = cpt columns of one channel
//   2 vector    (B x B): column = Cb bin, row = Cr bin over -0.5..0.5          tile = 32 x 32 bins, all samples
//   3 histogram (levels x 4): rows R G B luma                                 tile = one row, all samples
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uH0;   // mode, step, Sx, Sy
uniform vec4 uH1;   // levels, bins B, matrix (0 Rec.709, 1 Rec.601), sample columns per tile (cpt)
shared uint sH[1024];
shared uint sM[256];
int lvBin(float v, int n) { return clamp(int(floor(v * float(n))), 0, n - 1); }
int MODE, ST, SX, SY, LV, BB, CH_, C0, NC, TW;
ivec2 T0;
vec3 K;
ivec2 ISZ;
int binOf(int i) {                                  // local bin of sample i of this tile's domain, -1 = elsewhere
    int sx = C0 + i % NC, sy = i / NC;
    ivec2 px = min(ivec2(sx, sy) * ST + ST / 2, ISZ - 1);
    vec3 c = clamp(texelFetch(sTD2DInputs[0], px, 0).rgb, 0.0, 1.0);
    if (MODE == 0) return (sx - C0) + lvBin(dot(c, K), LV) * TW;
    if (MODE == 1) return (sx - C0) + lvBin(c[CH_], LV) * TW;
    if (MODE == 2) {
        float y = dot(c, K);
        ivec2 q = ivec2(lvBin((c.b - y) / (2.0 * (1.0 - K.b)) + 0.5, BB), lvBin((c.r - y) / (2.0 * (1.0 - K.r)) + 0.5, BB)) - T0;
        return (q.x >= 0 && q.y >= 0 && q.x < 32 && q.y < 32) ? q.x + q.y * 32 : -1;
    }
    return lvBin(CH_ < 3 ? c[CH_] : dot(c, K), LV);
}
void main() {
    uint lid = gl_LocalInvocationIndex;
    ivec2 wg = ivec2(gl_WorkGroupID.xy);
    MODE = int(uH0.x + 0.5); ST = max(int(uH0.y + 0.5), 1); SX = int(uH0.z + 0.5); SY = int(uH0.w + 0.5);
    LV = clamp(int(uH1.x + 0.5), 2, 1024); BB = clamp(int(uH1.y + 0.5), 32, 4096);
    int cpt = max(int(uH1.w + 0.5), 1);
    K = uH1.z < 0.5 ? vec3(0.2126, 0.7152, 0.0722) : vec3(0.299, 0.587, 0.114);
    ISZ = textureSize(sTD2DInputs[0], 0);
    int th;
    CH_ = 0;
    if (MODE == 0) { C0 = wg.x * cpt; T0 = ivec2(C0, 0); TW = cpt; th = LV; }
    else if (MODE == 1) {
        int tpp = (SX + cpt - 1) / cpt;
        CH_ = min(wg.x / tpp, 2); C0 = (wg.x % tpp) * cpt; T0 = ivec2(CH_ * SX + C0, 0); TW = cpt; th = LV;
    } else if (MODE == 2) { C0 = 0; T0 = wg * 32; TW = 32; th = 32; }
    else { C0 = 0; CH_ = min(wg.y, 3); T0 = ivec2(0, CH_); TW = LV; th = 1; }
    NC = MODE < 2 ? clamp(SX - C0, 0, cpt) : SX;
    int nb = min(TW * th, 1024);
    int total = NC * SY;
#ifdef SCOPE_NO_ATOMICS
    int gs = MODE >= 2 ? 16 : 1;                        // whole-frame domains: every 16th sample x 16 (bounded)
    for (int k = int(lid); k < nb; k += 256) {          // gather fallback: each thread counts its own bins
        uint n = 0u;
        for (int i = 0; i < total; i += gs) if (binOf(i) == k) n += uint(gs);
        sH[k] = n;
    }
    barrier();
#else
    for (int k = int(lid); k < 1024; k += 256) sH[k] = 0u;
    barrier();
    for (int i = int(lid); i < total; i += 256) {
        int b = binOf(i);
        if (b >= 0) atomicAdd(sH[b], 1u);
    }
    barrier();
#endif
    float mx = 0.0;
    if (MODE == 3) {                                    // row max for the histogram bar scale (uniform branch)
        uint m = 0u;
        for (int k = int(lid); k < nb; k += 256) m = max(m, sH[k]);
        sM[lid] = m;
        barrier();
        for (uint s = 128u; s > 0u; s >>= 1) {
            if (lid < s) sM[lid] = max(sM[lid], sM[lid + s]);
            barrier();
        }
        mx = float(sM[0]);
    }
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    for (int k = int(lid); k < nb; k += 256) {
        if (MODE < 2 && k % TW >= NC) continue;          // partial last tile: never spill into the next panel
        ivec2 q = T0 + ivec2(k % TW, k / TW);
        if (q.x < R.x && q.y < R.y) TDImageStoreOutput(0, ivec3(q, 0), vec4(float(sH[k]), mx, 0.0, 1.0));
    }
}
