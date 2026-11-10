// gen_sim_dla_grow: GEN_sim 'dla' stochastic growth, dielectric breakdown model (compute, npasses = growth steps
// this frame). An empty cell touching the cluster (4 neighbours) attaches with p = clamp(Growth * (phi / Ref)^Eta)
// where phi = the Laplace field (bilinear, float weights) and Ref = phimax x Phiref (phimax = the largest frontier phi
// of the last frame, from the touch pass via the field's texel 0 g); Eta = 1 ~ DLA statistics, high Eta =
// lightning, low = dense coral / Eden. in0 = cluster (Feedback of this pass / previous pass), in1 = field
// (r = phi, field size), in2 = slot input (Seed shape input). == gen_sim_logic.dla_init / dla_grow.
// State texel: r = occupied, g = step stamp when it attached (0 = seed), b = 0, a = E (the effective epoch, read
// from the field's texel 0: a = E, g = phimax, b = Jacobi iterations since its restart (no growth until Warmup of
// them; phi starts at 1) + 2e6 while touched (no growth)).
// uD = W H 0 shape; uG = growth eta nsteps frame; uD2 = seed threshold 0 phiref; uFs = FW FH warmup 0.
// (8-neighbour growth was tried offline: diagonal cells sit off the 4-neighbour frontier phimax is taken on, so
// p clamps to 1 and the cluster floods; not offered.)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uD;
uniform vec4 uG;
uniform vec4 uD2;
uniform vec4 uFs;

float occ(ivec2 c, ivec2 sz)
{
	if (c.x < 0 || c.y < 0 || c.x >= sz.x || c.y >= sz.y) return 0.0;
	return texelFetch(sTD2DInputs[0], c, 0).r;
}

float initOcc(ivec2 c, ivec2 sz)
{
	int shape = int(uD.w + 0.5);     // 0 centre point, 1 bottom line, 2 top point, 3 ring, 4 input, 5 scatter
	if (shape == 0) return (c == sz / 2) ? 1.0 : 0.0;
	if (shape == 1) return c.y == 0 ? 1.0 : 0.0;
	if (shape == 2) return (c.x == sz.x / 2 && c.y == sz.y - 1) ? 1.0 : 0.0;
	if (shape == 3) return abs(length(vec2(c) + 0.5 - 0.5 * vec2(sz)) - 0.45 * float(min(sz.x, sz.y))) < 0.75 ? 1.0 : 0.0;
	if (shape == 4) {
		ivec2 isz = textureSize(sTD2DInputs[2], 0);
		ivec2 q = clamp(ivec2((vec2(c) + 0.5) * vec2(isz) / vec2(sz)), ivec2(0), isz - 1);
		return gs_luma(texelFetch(sTD2DInputs[2], q, 0).rgb) > uD2.y ? 1.0 : 0.0;
	}
	return gs_hash3(c.x, c.y, int(uD2.x)) < 0.0004 ? 1.0 : 0.0;
}

float phiAt(ivec2 c, ivec2 sz)
{
	ivec2 fsz = ivec2(uFs.xy);
	vec2 f = (vec2(c) + 0.5) * uFs.xy / vec2(sz) - 0.5;
	f = clamp(f, vec2(0.0), vec2(fsz - 1));
	ivec2 i0 = ivec2(floor(f));
	vec2 w = f - vec2(i0);
	ivec2 i1 = min(i0 + 1, fsz - 1);
	float a = texelFetch(sTD2DInputs[1], i0, 0).r, b = texelFetch(sTD2DInputs[1], ivec2(i1.x, i0.y), 0).r;
	float cc = texelFetch(sTD2DInputs[1], ivec2(i0.x, i1.y), 0).r, d = texelFetch(sTD2DInputs[1], i1, 0).r;
	return mix(mix(a, b, w.x), mix(cc, d, w.x), w.y);
}

void main()
{
	ivec2 sz = ivec2(uD.xy);
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	if (c.x >= sz.x || c.y >= sz.y) return;
	vec4 f0 = texelFetch(sTD2DInputs[1], ivec2(0), 0);
	float E = f0.a;
	bool init = textureSize(sTD2DInputs[0], 0) != sz || texelFetch(sTD2DInputs[0], ivec2(0), 0).a != E;
	if (init) { TDImageStoreOutput(0, ivec3(c, 0), vec4(initOcc(c, sz), 0.0, 0.0, E)); return; }
	vec4 me = texelFetch(sTD2DInputs[0], c, 0);
	if (float(uTDPass) >= uG.z || me.r > 0.5) { TDImageStoreOutput(0, ivec3(c, 0), me); return; }
	float n = occ(c + ivec2(1, 0), sz) + occ(c - ivec2(1, 0), sz) + occ(c + ivec2(0, 1), sz) + occ(c - ivec2(0, 1), sz);
	if (n < 0.5 || f0.b < uFs.z || f0.b >= 2e6) { TDImageStoreOutput(0, ivec3(c, 0), me); return; }
	uint su = uint(uG.w) * 8u + uint(uTDPass);
	float phi = max(phiAt(c, sz), 0.0) / max(f0.g * uD2.w, 1e-6);
	float p = clamp(uG.x * pow(phi, uG.y), 0.0, 1.0);
	if (gs_hash3(c.x, c.y, int(su * 7919u + uint(int(uD2.x)))) < p) me = vec4(1.0, float(su), 0.0, E);
	TDImageStoreOutput(0, ivec3(c, 0), me);
}
