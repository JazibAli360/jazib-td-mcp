// gen_interactive_skinner_draw: GEN_interactive 'skinner' look (compute, frame size). in0 = slot input, in1 = shards.
// 8x8 tile lists (T-187 pattern) of the shards whose box (+ edge / glow extent) touches the tile; per pixel per shard:
// fill = Fill x clamp(inside distance + 0.5) x alpha, edge = clamp(Edgewidth / 2 - d + 0.5) x alpha (d = distance to
// the 3 edges), glow = Glow x exp(-d / Glowwidth) x alpha (0 beyond 6 Glowwidth); the shard with the largest sum
// colours the pixel (ties: lower index): gs_pal(t + shift) x (fill + edge + glow), blended over the slot input.
// == builders/gen_interactive_skinner_logic.py pixel.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uR;      // shards M, edge width px, glow, glow width px
uniform vec4 uF;      // fill, -, -, -

#define SK_LIST 512
shared int sL[SK_LIST];
shared uint sN;

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	bool inb = p.x < sz.x && p.y < sz.y;
	int M = max(int(uR.x + 0.5), 1);
	ivec2 tsz = textureSize(sTD2DInputs[1], 0);
	bool ok = tsz.x == 128 && tsz.y == (M + 63) / 64;
	float w = max(uR.y, 0.05), gw = max(uR.w, 1e-3);
	float ext = max(0.5 * w + 1.0, uR.z > 0.0 ? 6.0 * gw : 0.0);
	uint lid = gl_LocalInvocationIndex;
	if (lid == 0u) sN = 0u;
	barrier();
	vec2 t0 = vec2(gl_WorkGroupID.xy * 8u) - ext, t1 = vec2(gl_WorkGroupID.xy * 8u + 8u) + ext;
	for (int j = int(lid); j < (ok ? min(M, 65536) : 0); j += 64) {
		vec4 a = texelFetch(sTD2DInputs[1], ivec2(2 * (j % 64), j / 64), 0);
		vec4 b = texelFetch(sTD2DInputs[1], ivec2(2 * (j % 64) + 1, j / 64), 0);
		if (b.z <= 0.0) continue;
		vec2 lo = min(min(a.xy, a.zw), b.xy), hi = max(max(a.xy, a.zw), b.xy);
		if (hi.x < t0.x || lo.x > t1.x || hi.y < t0.y || lo.y > t1.y) continue;
		uint q = atomicAdd(sN, 1u);
		if (q < uint(SK_LIST)) sL[q] = j;
	}
	barrier();
	if (!inb) return;                                          // after the barrier (T-154)
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	vec2 pc = vec2(p) + 0.5;
	float best = 0.0, bf = 0.0, be = 0.0, bg = 0.0, bt = 0.0;
	int bj = 1 << 30;
	int n = int(min(sN, uint(SK_LIST)));
	for (int i = 0; i < SK_LIST; i++) {
		if (i >= n) break;
		int j = sL[i];
		vec4 a = texelFetch(sTD2DInputs[1], ivec2(2 * (j % 64), j / 64), 0);
		vec4 b = texelFetch(sTD2DInputs[1], ivec2(2 * (j % 64) + 1, j / 64), 0);
		vec2 A = a.xy, B = a.zw, C = b.xy;
		float ar = (B.x - A.x) * (C.y - A.y) - (B.y - A.y) * (C.x - A.x);
		if (abs(ar) < 1.0) continue;
		float s = sign(ar), h;
		float e0 = s * ((B.x - A.x) * (pc.y - A.y) - (B.y - A.y) * (pc.x - A.x)) / max(length(B - A), 1e-6);
		float e1 = s * ((C.x - B.x) * (pc.y - B.y) - (C.y - B.y) * (pc.x - B.x)) / max(length(C - B), 1e-6);
		float e2 = s * ((A.x - C.x) * (pc.y - C.y) - (A.y - C.y) * (pc.x - C.x)) / max(length(A - C), 1e-6);
		float sdi = min(min(e0, e1), e2);
		float d = min(min(gi_segdist(pc, A, B, h), gi_segdist(pc, B, C, h)), gi_segdist(pc, C, A, h));
		float fl = uF.x * clamp(sdi + 0.5, 0.0, 1.0) * b.z;
		float ed = clamp(0.5 * w - d + 0.5, 0.0, 1.0) * b.z;
		float gl = d < 6.0 * gw ? uR.z * exp(-d / gw) * b.z : 0.0;
		float tot = fl + ed + gl;
		if (tot > best || (tot == best && tot > 0.0 && j < bj)) { best = tot; bj = j; bf = fl; be = ed; bg = gl; bt = b.w; }
	}
	vec3 col = gs_pal(bt) * best;
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col, clamp(best, 0.0, 1.0)));
}
