// gen_interactive_strings_draw: GEN_interactive 'strings' look (compute, frame size). in0 = slot input (in1), in1 =
// string state (K x (S + 1): offset, velocity; meta row S texel 0 .y = module time T).
// in2 = cbox (one bounding box per chunk of 8 segments). Tile list (T-187 / GEN_interactive pattern): each 8x8
// workgroup tests every chunk box (S x ceil((K - 1) / 8), split over its 64 threads) grown by the draw extent (core +
// glow cut at 6 Glowwidth) against the tile and keeps the hits in shared memory (<= 512 chunks per tile); each pixel
// then takes the capsule distance to the 8 segments of those chunks only:
// core (Linewidth, 1 px AA) + glow (Glow x exp(-d / Glowwidth), 0 beyond 6 Glowwidth); colour gs_pal(t + Flow x T)
// of the nearest segment (ties: lower segment index), t = along / bend / string index / speed. Strings bent far
// from their rest place still draw whole. == builders/gen_interactive_strings_logic.py pixel.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS;      // strings S, nodes K, orient, margin
uniform vec4 uD;      // line width px, glow, glow width px, colour mode (0 along, 1 bend, 2 index, 3 speed)
uniform vec4 uD2;     // flow (palette cycles / s), -, -, bend ref px
uniform vec4 uSz;     // frame W, H, speed ref px/s, -

#define ST_LIST 512
shared int sL[ST_LIST];
shared uint sN;

vec2 st_rest(int s, int k, int S, int K)
{
	float c = uS.w + (float(s) + 0.5) / float(S) * (1.0 - 2.0 * uS.w);
	float a = float(k) / float(K - 1);
	return uS.z < 0.5 ? vec2(c * uSz.x, a * uSz.y) : vec2(a * uSz.x, c * uSz.y);
}

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	bool inb = p.x < sz.x && p.y < sz.y;
	int S = max(int(uS.x + 0.5), 1), K = clamp(int(uS.y + 0.5), 2, 256);
	ivec2 ssz = textureSize(sTD2DInputs[1], 0);
	bool ok = ssz.x == K && ssz.y == S + 1;
	float w = max(uD.x, 0.05), gw = max(uD.z, 1e-3);
	float ext = max(0.5 * w + 1.0, uD.y > 0.0 ? 6.0 * gw : 0.0);
	uint lid = gl_LocalInvocationIndex;
	if (lid == 0u) sN = 0u;
	barrier();
	vec2 t0 = vec2(gl_WorkGroupID.xy * 8u) - ext, t1 = vec2(gl_WorkGroupID.xy * 8u + 8u) + ext;
	int C = (K - 1 + 7) / 8;
	int nch = ok ? S * C : 0;
	for (int j = int(lid); j < min(nch, 131072); j += 64) {
		vec4 bx = texelFetch(sTD2DInputs[2], ivec2(j % C, j / C), 0);
		if (bx.z < t0.x || bx.x > t1.x || bx.w < t0.y || bx.y > t1.y) continue;
		uint q = atomicAdd(sN, 1u);
		if (q < uint(ST_LIST)) sL[q] = j;
	}
	barrier();
	if (!inb) return;                                          // after the barrier (T-154)
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	if (!ok) { TDImageStoreOutput(0, ivec3(p, 0), base); return; }
	float T = texelFetch(sTD2DInputs[1], ivec2(0, S), 0).y;
	vec2 pc = vec2(p) + 0.5;
	float best = 1e30, core = 0.0, glow = 0.0, tcol = 0.0;
	int bj = 1 << 30;
	int n = int(min(sN, uint(ST_LIST)));
	for (int i = 0; i < ST_LIST * 8; i++) {
		if (i >= n * 8) break;
		int ch = sL[i / 8];
		int s = ch / C, k = (ch % C) * 8 + (i % 8);
		if (k >= K - 1) continue;
		int j = s * (K - 1) + k;
		vec4 A = texelFetch(sTD2DInputs[1], ivec2(k, s), 0), B = texelFetch(sTD2DInputs[1], ivec2(k + 1, s), 0);
		vec2 a = st_rest(s, k, S, K) + A.xy, b = st_rest(s, k + 1, S, K) + B.xy;
		float hh;
		float d = gi_segdist(pc, a, b, hh);
		core = max(core, clamp(0.5 * w - d + 0.5, 0.0, 1.0));
		if (d < 6.0 * gw) glow = max(glow, uD.y * exp(-d / gw));
		if (d < best || (d == best && j < bj)) {
			best = d;
			bj = j;
			int cm = int(uD.w + 0.5);
			vec4 M = mix(A, B, hh);
			if (cm == 0) tcol = (float(k) + hh) / float(K - 1);
			else if (cm == 1) tcol = length(M.xy) / max(uD2.w, 1e-3);
			else if (cm == 2) tcol = float(s) / float(max(S - 1, 1));
			else tcol = length(M.zw) / max(uSz.z, 1e-3);
		}
	}
	float al = clamp(core + glow, 0.0, 1.0);
	vec3 col = gs_pal(tcol + uD2.x * T) * (core + glow);
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col, al));
}
