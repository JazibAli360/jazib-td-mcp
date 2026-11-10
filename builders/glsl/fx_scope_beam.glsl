// FX_scope beam pass (compute, T-47): tile-binned Gaussian beam + phosphor state, in place (outputaccess readwrite,
// clearoutputs off, 2 colour buffers). in0 = path (1024 x 17). Workgroup 16x16 = one 32x32 px tile (2x2 px per
// thread). Per chunk of 256 segments: skip it when its bbox (grown by the cut radius) misses the tile (uniform, no
// barrier); else every thread tests one segment and appends the hits to shared memory, then each pixel sums the
// hits: E += Kn I w [Dwell dt G/L + (1 - Dwell) G / Lref], G = 2D Gaussian integrated along the segment (erf).
// Buffer 0 = (afterglow S rgb, flash = luma of this frame's E); buffer 1 = (last absTime.frame, 1, w, h) per texel:
// a repeat cook in the same frame (readback, T-116/T-117) leaves the texel alone; a gap > uT.y frames or a size
// change restarts from 0 (no stale trails after a bypass). Budget: a tile stops after `uI.z` hit segments
// (white-noise audio crosses every tile; the rest of that frame's segments are dropped there, not the frame).
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uB;   // sigma (buffer px), Kn, Dwell, Lref (buffer px)
uniform vec4 uI;   // Intensity, mono (1 = phosphor luma), hit budget per tile (segments), 0
uniform vec4 uA;   // afterglow tint r g b (x Afterglow), 0
uniform vec4 uP;   // tau r g b (s, <= 0 = no persistence), seconds per frame
uniform vec4 uT;   // absTime.frame, reset gap (frames), 0, 0
//@LIB
shared vec4 sS[CH];
shared vec4 sX[CH];
#ifdef SCOPE_NO_ATOMICS
shared uint sC[2][CH];
#else
shared uint sN;
#endif
void main() {
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    uint lid = gl_LocalInvocationIndex;
    ivec2 l = ivec2(gl_LocalInvocationID.xy);
    vec2 T0 = vec2(gl_WorkGroupID.xy) * 32.0;
    float sg = max(uB.x, 0.05);
    float Rc = 5.0 * sg, Rc2 = Rc * Rc;
    float i2s2 = 0.5 / (sg * sg), is2 = 1.0 / (1.4142135623730951 * sg), iq = 1.0 / (SQ2PI * sg);
    float i2p = 1.0 / (6.283185307179586 * sg * sg);
    vec2 P[4];
    vec3 acc[4];
    for (int k = 0; k < 4; k++) {
        P[k] = T0 + vec2(l) + vec2(float(16 * (k & 1)), float(16 * (k >> 1))) + 0.5;
        acc[k] = vec3(0.0);
    }
    int np = min(int(texelFetch(sTD2DInputs[0], ivec2(ROWW - 1, CAPROW), 0).x + 0.5), CAP);
    float dt = np > 1 ? 1.0 / float(np - 1) : 0.0;
    float wd = uI.x * uB.y * uB.z * dt;
    float wu = uI.x * uB.y * (1.0 - uB.z) / max(uB.w, 1.0);
    vec2 lo = T0 - Rc, hi = T0 + 32.0 + Rc;
    int nch = np > 1 ? (np - 1 + CH - 1) / CH : 0;
    int budget = max(int(uI.z + 0.5), CH), used = 0;      // bounds the per-pixel work (noise-like paths)
    for (int c = 0; c < nch; c++) {
        vec4 bb = texelFetch(sTD2DInputs[0], ivec2(c, CAPROW), 0);
        if (bb.x > hi.x || bb.y > hi.y || bb.z < lo.x || bb.w < lo.y) continue;    // whole chunk misses the tile
        int j = c * CH + int(lid);
        bool hit = false;
        vec4 seg = vec4(0.0), aux = vec4(0.0);
        if (j + 1 < np) {
            vec4 A = texelFetch(sTD2DInputs[0], ivec2(j % ROWW, j / ROWW), 0);
            if (A.z > 0.0) {
                int j1 = j + 1;
                vec2 b = texelFetch(sTD2DInputs[0], ivec2(j1 % ROWW, j1 / ROWW), 0).xy;
                vec2 mn = min(A.xy, b), mx = max(A.xy, b);
                hit = !(mn.x > hi.x || mn.y > hi.y || mx.x < lo.x || mx.y < lo.y);
                seg = vec4(A.xy, b);
                aux = vec4(A.z * wd, A.z * wu, A.w, length(b - A.xy));
            }
        }
#ifdef SCOPE_NO_ATOMICS
        sC[0][lid] = hit ? 1u : 0u;                 // Hillis-Steele inclusive scan, ping-pong (8 barriers)
        barrier();
        int src = 0;
        for (uint o = 1u; o < uint(CH); o <<= 1) {
            uint v = sC[src][lid];
            if (lid >= o) v += sC[src][lid - o];
            sC[1 - src][lid] = v;
            src = 1 - src;
            barrier();
        }
        if (hit) {
            uint k = sC[src][lid] - 1u;
            sS[k] = seg;
            sX[k] = aux;
        }
        barrier();
        uint n = sC[src][CH - 1];
#else
        if (lid == 0u) sN = 0u;
        barrier();
        if (hit) {
            uint k = atomicAdd(sN, 1u);
            sS[k] = seg;
            sX[k] = aux;
        }
        barrier();
        uint n = sN;
#endif
        for (uint k = 0u; k < n; k++) {
            vec4 s = sS[k];
            vec4 x = sX[k];
            vec2 a = s.xy;
            float L = x.w;
            vec2 u = L > 0.0 ? (s.zw - a) / L : vec2(1.0, 0.0);
            vec3 col = unpackRGB(x.z);
            if (uI.y > 0.5) col = vec3(dot(col, LUMA));
            for (int q = 0; q < 4; q++) {
                vec2 d = P[q] - a;
                float t = dot(d, u);
                vec2 r = d - u * clamp(t, 0.0, L);
                if (dot(r, r) > Rc2) continue;
                float pp = d.x * u.y - d.y * u.x;
                float v;
                if (L < 0.02) {                                         // point form about the midpoint
                    float tm = t - 0.5 * L;
                    float g2 = exp(-(pp * pp + tm * tm) * i2s2) * i2p;
                    v = x.x * g2 + x.y * L * g2;
                } else {
                    float G = exp(-pp * pp * i2s2) * iq * 0.5 * (erfA((L - t) * is2) + erfA(t * is2));
                    v = x.x * G / L + x.y * G;
                }
                acc[q] += v * col;
            }
        }
        barrier();
        used += int(n);                                        // n is shared: the break is uniform
        if (used >= budget) break;
    }
    for (int q = 0; q < 4; q++) {
        ivec2 p = ivec2(P[q]);
        if (p.x >= R.x || p.y >= R.y) continue;
        vec4 s1 = TDImageLoadOutput(1, ivec3(p, 0));
        bool valid = s1.y == 1.0 && s1.z == float(R.x) && s1.w == float(R.y);
        if (valid && s1.x == uT.x) continue;                        // repeat cook in this frame: keep
        float df = uT.x - s1.x;
        vec3 S = vec3(0.0);
        if (valid && df > 0.0 && df <= uT.y) {
            vec3 S0 = TDImageLoadOutput(0, ivec3(p, 0)).rgb;
            float ts = df * uP.w;
            S = S0 * vec3(uP.x > 0.0 ? exp(-ts / uP.x) : 0.0, uP.y > 0.0 ? exp(-ts / uP.y) : 0.0,
                          uP.z > 0.0 ? exp(-ts / uP.z) : 0.0);
        }
        S += acc[q] * uA.rgb;
        TDImageStoreOutput(0, ivec3(p, 0), vec4(S, dot(acc[q], LUMA)));
        TDImageStoreOutput(1, ivec3(p, 0), vec4(uT.x, 1.0, float(R.x), float(R.y)));
    }
}
