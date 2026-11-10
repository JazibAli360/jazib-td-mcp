// gen_sim_ca_step: GEN_sim 'ca' state step (compute, npasses = steps this frame; pass n+1 reads pass n as input 0,
// T-91 (3)). in0 = state (Feedback TOP of this pass, sim res), in1 = slot input (seed / inject source).
// State texel: r = cell state (life: 0 dead, 1 alive, 2.. dying; wireworld: 0 empty, 1 head, 2 tail, 3 wire;
// cyclic: 0..N-1; ltl: 0/1; lenia: 0..1), g = glow (1 on a live cell, then x Decay per step), b = age (steps alive),
// a = epoch (Resetcount + 1): a state whose epoch or size differs is re-seeded (first frame, Reset, seed change).
// == builders/gen_sim_logic.py ca_step / ca_init (numpy, test/test_gen_sim_ca.py).
// uSim = W H family epoch; uRule = Bmask Smask C R; uLtl = b1 b2 s1 s2; uCyc = N threshold 0 0;
// uLen = mu sigma dt norm; uSeed = mode density threshold seed; uRun = nsteps frame mutate inject;
// uMisc = wrap decay wirespacing sparks.
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uSim;
uniform vec4 uRule;
uniform vec4 uLtl;
uniform vec4 uCyc;
uniform vec4 uLen;
uniform vec4 uSeed;
uniform vec4 uRun;
uniform vec4 uMisc;

#define TS 16
#define HMAX 16
#define TW 48
#define KW 33
#define F_LIFE 0
#define F_WIRE 1
#define F_CYC 2
#define F_LTL 3
#define F_LENIA 4
shared float tileS[TW * TW];
shared float kern[KW * KW];

float cellAt(ivec2 c, ivec2 sz)
{
	if (uMisc.x > 0.5) c = ivec2(c.x - sz.x * int(floor(float(c.x) / float(sz.x))), c.y - sz.y * int(floor(float(c.y) / float(sz.y))));
	else if (c.x < 0 || c.y < 0 || c.x >= sz.x || c.y >= sz.y) return 0.0;
	return texelFetch(sTD2DInputs[0], c, 0).r;
}

// slot input luma at the cell centre (texelFetch of the input pixel under it: exact for the parity check)
float inLuma(ivec2 c, ivec2 sz)
{
	ivec2 isz = textureSize(sTD2DInputs[1], 0);
	ivec2 q = clamp(ivec2((vec2(c) + 0.5) * vec2(isz) / vec2(sz)), ivec2(0), isz - 1);
	return gs_luma(texelFetch(sTD2DInputs[1], q, 0).rgb);
}

float initCell(ivec2 c, ivec2 sz, int fam)
{
	int mode = int(uSeed.x + 0.5);          // 0 noise, 1 blob, 2 input, 3 wires, 4 empty
	int sd = int(uSeed.w);
	float dens = uSeed.y;
	float h = gs_hash3(c.x, c.y, sd);
	float N = max(uCyc.x, 2.0);
	if (mode == 4) return 0.0;
	if (mode == 2) {
		float l = inLuma(c, sz);
		if (fam == F_LENIA) return l;
		if (fam == F_CYC) return min(floor(l * N), N - 1.0);
		if (fam == F_WIRE) return l > uSeed.z ? (gs_hash3(c.x, c.y, sd + 7) < uMisc.w ? 1.0 : 3.0) : 0.0;
		return l > uSeed.z ? 1.0 : 0.0;
	}
	if (mode == 3 || (fam == F_WIRE && mode == 0)) {   // wire lattice with gaps + sparks (any family: alive = wire)
		int sp = max(int(uMisc.z + 0.5), 2);
		bool wire = (c.x % sp == 0 || c.y % sp == 0) && gs_hash3(c.x / sp, c.y / sp, sd + 3) > dens * 0.5;
		if (!wire) return 0.0;
		if (fam != F_WIRE) return 1.0;
		return gs_hash3(c.x, c.y, sd + 7) < uMisc.w ? 1.0 : 3.0;
	}
	if (mode == 1) {                                   // a disc of noise in the middle (r = 0.2 of the short side)
		vec2 d = vec2(c) + 0.5 - 0.5 * vec2(sz);
		if (length(d) > 0.2 * float(min(sz.x, sz.y))) return 0.0;
	}
	if (fam == F_CYC) return min(floor(h * N), N - 1.0);
	if (fam == F_LENIA) {                              // patches (value noise at 2R cells) of uniform random
		float R = clamp(uRule.w, 1.0, float(HMAX));
		return gs_vnoise(vec2(c) / (2.0 * R), sd + 1) < dens ? h : 0.0;
	}
	if (fam == F_WIRE) return h < dens ? (gs_hash3(c.x, c.y, sd + 7) < uMisc.w ? 1.0 : 3.0) : 0.0;
	return h < dens ? 1.0 : 0.0;
}

void main()
{
	ivec2 sz = ivec2(uSim.xy);
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	bool inside = c.x < sz.x && c.y < sz.y;
	int fam = int(uSim.z + 0.5);
	// the whole dispatch takes the same branch (cell (0,0) decides), so the early returns keep barrier() uniform
	bool init = textureSize(sTD2DInputs[0], 0) != sz || texelFetch(sTD2DInputs[0], ivec2(0), 0).a != uSim.w;
	if (init) {
		if (inside) TDImageStoreOutput(0, ivec3(c, 0), vec4(initCell(c, sz, fam), 0.0, 0.0, uSim.w));
		return;
	}
	if (float(uTDPass) >= uRun.x) {                    // no step this pass (Steps < 1 per frame, Run off): copy
		if (inside) TDImageStoreOutput(0, ivec3(c, 0), texelFetch(sTD2DInputs[0], c, 0));
		return;
	}
	int R = (fam == F_LIFE || fam == F_WIRE) ? 1 : clamp(int(uRule.w + 0.5), 1, HMAX);
	ivec2 org = ivec2(gl_WorkGroupID.xy) * TS - R;
	int tw = TS + 2 * R;
	for (int i = int(gl_LocalInvocationIndex); i < tw * tw; i += TS * TS)
		tileS[(i / tw) * TW + (i % tw)] = cellAt(org + ivec2(i % tw, i / tw), sz);
	if (fam == F_LENIA) {                              // kernel shell: exp(4 - 1 / (r (1 - r))), r = |d| / R in (0, 1)
		int kw = 2 * R + 1;
		for (int i = int(gl_LocalInvocationIndex); i < kw * kw; i += TS * TS) {
			float r = length(vec2(i % kw - R, i / kw - R)) / float(R);
			kern[(i / kw) * KW + (i % kw)] = (r > 0.0 && r < 1.0) ? exp(4.0 - 1.0 / (r * (1.0 - r))) : 0.0;
		}
	}
	barrier();
	if (!inside) return;
	vec4 me = texelFetch(sTD2DInputs[0], c, 0);
	ivec2 l = ivec2(gl_LocalInvocationID.xy) + R;
	float s = me.r;
	int si = int(s + 0.5);
	float ns = s;
	float live = 0.0;
	if (fam == F_LIFE || fam == F_WIRE) {
		int n = 0;
		for (int dy = -1; dy <= 1; dy++)
			for (int dx = -1; dx <= 1; dx++)
				if ((dx != 0 || dy != 0) && int(tileS[(l.y + dy) * TW + l.x + dx] + 0.5) == 1) n++;
		if (fam == F_LIFE) {
			int C = max(int(uRule.z + 0.5), 2);
			if (si == 0) ns = ((int(uRule.x + 0.5) >> n) & 1) == 1 ? 1.0 : 0.0;
			else if (si == 1) ns = ((int(uRule.y + 0.5) >> n) & 1) == 1 ? 1.0 : (C > 2 ? 2.0 : 0.0);
			else ns = (si + 1 >= C) ? 0.0 : float(si + 1);
		} else {
			if (si == 1) ns = 2.0;
			else if (si == 2) ns = 3.0;
			else if (si == 3) ns = (n == 1 || n == 2) ? 1.0 : 3.0;
		}
	} else if (fam == F_CYC || fam == F_LTL) {
		int N = max(int(uCyc.x + 0.5), 2);
		int want = (fam == F_CYC) ? (si + 1) % N : 1;
		int n = 0;
		for (int dy = -R; dy <= R; dy++)
			for (int dx = -R; dx <= R; dx++)
				if ((dx != 0 || dy != 0) && int(tileS[(l.y + dy) * TW + l.x + dx] + 0.5) == want) n++;
		if (fam == F_CYC) {
			ns = (float(n) >= uCyc.y) ? float(want) : s;
		} else {
			if (si == 0) ns = (float(n) >= uLtl.x && float(n) <= uLtl.y) ? 1.0 : 0.0;
			else ns = (float(n) >= uLtl.z && float(n) <= uLtl.w) ? 1.0 : 0.0;
		}
	} else {                                           // lenia: A += dt * (2 exp(-(U - mu)^2 / (2 sigma^2)) - 1)
		float U = 0.0;
		for (int dy = -R; dy <= R; dy++)
			for (int dx = -R; dx <= R; dx++)
				U += kern[(dy + R) * KW + dx + R] * tileS[(l.y + dy) * TW + l.x + dx];
		U /= max(uLen.w, 1e-9);
		float d = (U - uLen.x) / max(uLen.y, 1e-6);
		ns = clamp(s + uLen.z * (2.0 * exp(-0.5 * d * d) - 1.0), 0.0, 1.0);
	}
	// per-step random stream: frame * 8 + pass (uint maths: wraps the same way as gen_sim_logic.step_seed)
	int rs = int((uint(uRun.y) * 8u + uint(uTDPass)) * 7919u + uint(int(uSeed.w)));
	if (uRun.z > 0.0 && gs_hash3(c.x, c.y, rs) < uRun.z) {                       // Mutate
		float h2 = gs_hash3(c.x, c.y, rs + 11);
		if (fam == F_LENIA) ns = max(ns, h2);
		else if (fam == F_CYC) ns = min(floor(h2 * max(uCyc.x, 2.0)), max(uCyc.x, 2.0) - 1.0);
		else if (fam == F_WIRE) { if (ns == 3.0) ns = 1.0; }
		else ns = 1.0;
	}
	if (uRun.w > 0.5) {                                // Inject: the slot input draws cells every step
		float li = inLuma(c, sz);
		if (li > uSeed.z) {
			if (fam == F_LENIA) ns = max(ns, li);
			else if (fam == F_WIRE) { if (ns == 0.0) ns = 3.0; }
			else if (fam != F_CYC) ns = 1.0;
		}
	}
	if (fam == F_CYC) live = ns != s ? 1.0 : 0.0;
	else if (fam == F_LENIA) live = ns;
	else live = ns == 1.0 ? 1.0 : 0.0;
	float glow = max(live, me.g * uMisc.y);
	float age = live > 0.5 ? me.b + 1.0 : 0.0;
	TDImageStoreOutput(0, ivec3(c, 0), vec4(ns, glow, age, uSim.w));
}
