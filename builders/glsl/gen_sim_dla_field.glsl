// gen_sim_dla_field: GEN_sim 'dla' Laplace field phi around the cluster (compute, npasses = ceil(Iters / 8)).
// 8 Jacobi iterations per pass with temporal blocking: a 32x32 workgroup loads a 32x32 tile, iterates 8 times in
// shared memory (the valid area shrinks 1 cell per iteration) and writes its 16x16 core; manual dispatch
// ceil(FW / 16) x ceil(FH / 16). Same numbers as 8 plain Jacobi sweeps (== gen_sim_logic.jacobi).
// in0 = phi (Feedback of this pass, field size), in1 = cluster state (sim size; r = occupied, a = epoch),
// in2 = touch (2x1: texel 0 r touched, b regrow count -> effective epoch E = Epoch + 4096 * (b mod 4096); texel 1
// r = phimax of the last frame's frontier).
// Fixed cells: grounded (any of 4x4 samples of the cluster under the field cell occupied) = 0, electrode disc = 1.
// Frame sides: uBC = left right bottom top, < 0 = Neumann (mirror), else that Dirichlet value.
// uF = FW FH epoch 0; uEl = cx cy radius 0 (field px; radius 0 = none); uFs = simW simH 0 0.
// Texel: r = phi, g = phimax (copied from the touch pass), b = Jacobi iterations since the (re)start (growth waits
// for Warmup of them) + 2e6 while touched (growth stops), a = E (phi re-initialises to 1 on a new E or size; the
// growth pass reads g / b / a at texel 0).
layout (local_size_x = 32, local_size_y = 32) in;
uniform vec4 uF;
uniform vec4 uBC;
uniform vec4 uEl;
uniform vec4 uFs;

#define LS 32
#define KB 8
#define CORE 16
shared float ph[2 * LS * LS];
shared float fx[LS * LS];

float fixedAt(ivec2 g, float E)
{
	vec2 sx = uFs.xy / uF.xy;                           // sim cells per field cell
	ivec2 ssz = ivec2(uFs.xy);
	vec2 lo = floor((vec2(g) + (vec2(0.0) + 0.5) * 0.25) * sx), hi = floor((vec2(g) + (vec2(3.0) + 0.5) * 0.25) * sx);
	if (lo == hi) {                                     // all 16 samples land in one sim cell (Cell field = sim): 1 fetch
		vec4 cs = texelFetch(sTD2DInputs[1], clamp(ivec2(lo), ivec2(0), ssz - 1), 0);
		if (cs.r > 0.5 && cs.a == E) return 0.0;
	} else
	for (int b = 0; b < 4; b++)
		for (int a = 0; a < 4; a++) {
			ivec2 s = clamp(ivec2(floor((vec2(g) + (vec2(a, b) + 0.5) * 0.25) * sx)), ivec2(0), ssz - 1);
			vec4 cs = texelFetch(sTD2DInputs[1], s, 0);
			if (cs.r > 0.5 && cs.a == E) return 0.0;
		}
	if (uEl.z > 0.0 && length(vec2(g) + 0.5 - uEl.xy) <= uEl.z) return 1.0;
	return -1.0;
}

void main()
{
	ivec2 fsz = ivec2(uF.xy);
	ivec2 l = ivec2(gl_LocalInvocationID.xy);
	ivec2 g = ivec2(gl_WorkGroupID.xy) * CORE - KB + l;
	bool inImg = g.x >= 0 && g.y >= 0 && g.x < fsz.x && g.y < fsz.y;
	vec4 tch = texelFetch(sTD2DInputs[2], ivec2(0), 0);
	float E = uF.z + 4096.0 * mod(tch.b, 4096.0);
	bool init = textureSize(sTD2DInputs[0], 0) != fsz || texelFetch(sTD2DInputs[0], ivec2(0), 0).a != E;
	int li = l.y * LS + l.x;
	float f = inImg ? fixedAt(g, E) : -1.0;
	fx[li] = f;
	float v = init ? 1.0 : texelFetch(sTD2DInputs[0], clamp(g, ivec2(0), fsz - 1), 0).r;
	ph[li] = f >= 0.0 ? f : v;
	int cur = 0;
	if (!init) {
		for (int it = 0; it < KB; it++) {
			barrier();
			float o = ph[cur * LS * LS + li];
			float nv = o;
			if (inImg && f < 0.0 && l.x > 0 && l.y > 0 && l.x < LS - 1 && l.y < LS - 1) {
				float L = g.x - 1 < 0 ? (uBC.x < 0.0 ? o : uBC.x) : ph[cur * LS * LS + li - 1];
				float R = g.x + 1 >= fsz.x ? (uBC.y < 0.0 ? o : uBC.y) : ph[cur * LS * LS + li + 1];
				float B = g.y - 1 < 0 ? (uBC.z < 0.0 ? o : uBC.z) : ph[cur * LS * LS + li - LS];
				float T = g.y + 1 >= fsz.y ? (uBC.w < 0.0 ? o : uBC.w) : ph[cur * LS * LS + li + LS];
				nv = 0.25 * (L + R + B + T);
			}
			ph[(1 - cur) * LS * LS + li] = nv;
			cur = 1 - cur;
		}
	}
	barrier();
	if (!inImg || l.x < KB || l.y < KB || l.x >= KB + CORE || l.y >= KB + CORE) return;
	float its = init ? 0.0 : min(mod(texelFetch(sTD2DInputs[0], ivec2(0), 0).b, 2e6) + float(KB), 1e6);
	float pm = texelFetch(sTD2DInputs[2], ivec2(1, 0), 0).r;
	TDImageStoreOutput(0, ivec3(g, 0), vec4(ph[cur * LS * LS + li], pm, its + (tch.r > 0.5 ? 2e6 : 0.0), E));
}
