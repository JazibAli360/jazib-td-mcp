// gen_sim_ripple_step: GEN_sim 'ripple' wave-equation step (compute, npasses = steps this frame; pass n+1 reads pass
// n as input 0, T-91 (3)). in0 = state (Feedback TOP of this pass, sim res), in1 = slot input (Inject source).
// State texel: r = height now, g = height one step ago, b = hits applied (count), a = epoch (Resetcount + 1).
// h' = Damp x (2 h - h_prev + c2 x (sum of 4 neighbours - 4 h)), c2 = 0.5 Wavespeed^2 (<= 0.5 = the CFL limit;
// c2 0.5 is the classic Hugo Elias water). Then drops: Rain (up to 4 candidates per step, hashed from the frame and
// pass), hits (every hit from b + 1 to Hitn: random place by hit index, centre or Hitu / Hitv) and Inject (slot input
// luma above Threshold pushes the water down). Edges: 0 wrap, 1 reflect (closed tank), 2 absorb (open sea).
// == builders/gen_sim_logic.py ripple_step (numpy, test/test_gen_sim_ripple.py).
// uSim = W H edges epoch; uWave = c2 damp nsteps frame; uRain = drops/step amp size(sim px) seed;
// uHit = hitn amp posmode size; uHitp = u v threshold injectamt.
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uSim;
uniform vec4 uWave;
uniform vec4 uRain;
uniform vec4 uHit;
uniform vec4 uHitp;

vec2 hAt(ivec2 c, ivec2 sz)
{
	int e = int(uSim.z + 0.5);
	if (e == 0) c = ivec2(c.x - sz.x * int(floor(float(c.x) / float(sz.x))), c.y - sz.y * int(floor(float(c.y) / float(sz.y))));
	else if (e == 1) c = clamp(c, ivec2(0), sz - 1);
	else if (c.x < 0 || c.y < 0 || c.x >= sz.x || c.y >= sz.y) return vec2(0.0);
	return texelFetch(sTD2DInputs[0], c, 0).rg;
}

float bump(vec2 p, vec2 ctr, float r)
{
	float d = length(p - ctr);
	if (d >= r) return 0.0;
	float k = cos(0.5 * GS_PI * d / r);
	return k * k;
}

void main()
{
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(int(uSim.x + 0.5), int(uSim.y + 0.5));
	if (c.x >= sz.x || c.y >= sz.y) return;
	vec4 s = texelFetch(sTD2DInputs[0], c, 0);
	ivec2 isz = textureSize(sTD2DInputs[0], 0);
	if (abs(s.a - uSim.w) > 0.5 || isz != sz) {           // first frame, Reset, size change: flat water
		TDImageStoreOutput(0, ivec3(c, 0), vec4(0.0, 0.0, uHit.x, uSim.w));
		return;
	}
	if (float(uTDPass) >= uWave.z) { TDImageStoreOutput(0, ivec3(c, 0), s); return; }   // no step this pass
	float h = s.r, hp = s.g;
	float nb = hAt(c + ivec2(1, 0), sz).r + hAt(c - ivec2(1, 0), sz).r + hAt(c + ivec2(0, 1), sz).r + hAt(c - ivec2(0, 1), sz).r;
	float hn = uWave.y * (2.0 * h - hp + uWave.x * (nb - 4.0 * h));
	vec2 p = vec2(c) + 0.5;
	int st = int(uWave.w) * 8 + uTDPass;
	for (int j = 0; j < 4; j++) {                          // rain: candidate j of this step falls with p = drops/step
		if (gs_hash3(st, j, int(uRain.w)) >= uRain.x - float(j)) continue;
		vec2 ctr = vec2(gs_hash3(st, j + 4, int(uRain.w)), gs_hash3(st, j + 8, int(uRain.w))) * vec2(sz);
		hn -= uRain.y * bump(p, ctr, uRain.z);
	}
	float done = s.b;
	if (uTDPass == 0 && uHit.x > done) {                    // hits not applied yet (at most 8 per frame)
		for (int k = 1; k <= 8; k++) {
			float n = done + float(k);
			if (n > uHit.x) break;
			int pm = int(uHit.z + 0.5);
			vec2 ctr = pm == 1 ? 0.5 * vec2(sz) : (pm == 2 ? uHitp.xy * vec2(sz)
				: vec2(gs_hash3(int(n), 1, int(uRain.w)), gs_hash3(int(n), 2, int(uRain.w))) * vec2(sz));
			hn -= uHit.y * bump(p, ctr, uHit.w);
		}
		done = uHit.x;
	}
	if (uHitp.w > 0.0) {                                    // inject: bright input pushes the water down
		ivec2 q = clamp(ivec2(p * vec2(textureSize(sTD2DInputs[1], 0)) / vec2(sz)), ivec2(0), textureSize(sTD2DInputs[1], 0) - 1);
		float l = gs_luma(texelFetch(sTD2DInputs[1], q, 0).rgb);
		hn -= uHitp.w * max(l - uHitp.z, 0.0);
	}
	TDImageStoreOutput(0, ivec3(c, 0), vec4(hn, h, done, uSim.w));
}
