// fluid2d pass fx_press, blocked mode (perf lane 2, 27 Oct; builder press_mode 'blocked', the default): up to KB = 8
// weighted-Jacobi iterations per dispatch instead of one. A 16x16 group loads its tile + a KB-cell halo (32 x 32) of
// pressure, divergence and solid flags into shared memory and iterates there; a cell's result is exact after k
// iterations when it is >= k cells from the region border, so the tile (KB from the border) is exact after KB.
// Same per-cell maths as fluid2d_press.glsl (p' = (1-w) pc + w (sum pn - div) * INV_BETA, Neumann at solids, 0
// outside in open mode, wrap = the wrapped cells' values, wall = outside is solid); npasses = ceil(N / KB).
// uPress.x scales the incoming pressure on the first iteration only (Warmstart). Paused: copy. Out (p, 0, 0, 0).
// in0 = press_fb, in1 = fx_div (div, solid).
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uStep;   // dt, run, edge, aspect
uniform vec4 uPress;  // scale of in0 (first iteration), Jacobi weight w, total iterations N, 0
#define KB 8
#define RW 32
#define RN 1024

shared float sP[2 * RN];
shared float sDv[RN];
shared float sSo[RN];

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	ivec2 isz = textureSize(sTD2DInputs[0], 0), dsz = textureSize(sTD2DInputs[1], 0);
	bool own = T.x < sz.x && T.y < sz.y;
	if (uStep.y < 0.5) {                                          // paused (uniform): pressure frozen
		if (own) TDImageStoreOutput(0, ivec3(T, 0), vec4(texelFetch(sTD2DInputs[0], clamp(T, ivec2(0), isz - 1), 0).r, 0.0, 0.0, 0.0));
		return;
	}
	int e = int(uStep.z + 0.5);
	bool wrap = presMode(e) == M_WRAP;
	ivec2 H0 = ivec2(gl_WorkGroupID.xy) * 16 - KB;
	int li = int(gl_LocalInvocationIndex);
	for (int idx = li; idx < RN; idx += 256) {                   // load: real cells, wrapped cells, or outside
		ivec2 g = H0 + ivec2(idx % RW, idx / RW);
		bool in_ = g.x >= 0 && g.y >= 0 && g.x < sz.x && g.y < sz.y;
		float p = 0.0, dv = 0.0, so = solidConst(e);
		if (in_ || wrap) {
			ivec2 q = in_ ? g : ivec2(wrapi(g.x, sz.x), wrapi(g.y, sz.y));
			p = texelFetch(sTD2DInputs[0], clamp(q, ivec2(0), isz - 1), 0).r;
			vec4 d = texelFetch(sTD2DInputs[1], clamp(q, ivec2(0), dsz - 1), 0);
			dv = d.r;
			so = d.g;
		}
		sP[idx] = p;
		sP[RN + idx] = p;
		sDv[idx] = dv;
		sSo[idx] = so;
	}
	barrier();
	int N = max(int(uPress.z + 0.5), 1);
	int done = int(uTDPass) * KB;
	int nit = clamp(N - done, 0, KB);
	float w = uPress.y;
	int cur = 0;
	for (int it = 0; it < KB; it++) {
		if (it >= nit) break;                                      // uniform
		float s = (done + it == 0) ? uPress.x : 1.0;
		for (int idx = li; idx < RN; idx += 256) {
			int x = idx % RW, y = idx / RW;
			int r = min(min(x, y), min(RW - 1 - x, RW - 1 - y));
			if (r < it + 1) continue;                              // shrinking region: only cells exact so far
			ivec2 g = H0 + ivec2(x, y);
			if (!wrap && !(g.x >= 0 && g.y >= 0 && g.x < sz.x && g.y < sz.y)) continue;   // outside: never updated
			float pn;
			if (sSo[idx] > 0.5) pn = 0.0;
			else {
				float pc = s * sP[cur * RN + idx];
				float acc = 0.0;
				int nb[4] = int[4](idx + 1, idx - 1, idx + RW, idx - RW);
				for (int k = 0; k < 4; k++) {
					int q = nb[k];
					acc += sSo[q] > 0.5 ? pc : s * sP[cur * RN + q];
				}
				pn = (1.0 - w) * pc + w * (acc - sDv[idx]) * INV_BETA;
			}
			sP[(1 - cur) * RN + idx] = pn;
		}
		barrier();
		cur = 1 - cur;
	}
	if (!own) return;
	ivec2 l = T - H0;
	TDImageStoreOutput(0, ivec3(T, 0), vec4(sP[cur * RN + l.y * RW + l.x], 0.0, 0.0, 0.0));
}
