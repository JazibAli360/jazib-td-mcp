// gen_sim_lava_step: GEN_sim 'lavalamp' fluid step (compute, npasses = steps this frame; pass n+1 reads pass n as
// input 0, T-91 (3)). Clean-room Rayleigh-Taylor / Boussinesq step after the lygia description (FX7a SX-25): one pass,
// semi-Lagrangian advection, ONE warm-started Jacobi pressure iteration, buoyancy. in0 = state (sim res, linear
// filter), in1 = slot input (seed / Relax source), in2 = mass of the last frame (1x1: x target mean density = the
// seeded mean, y mean density, a epoch; an epoch it has not seen = seed now). State texel: xy velocity (sim px / step), z density (0 light .. 1 heavy), w pressure.
// Walls: a closed tank (normal velocity 0 at the border, neighbours clamped). Heat: the bottom Heatzone turns the
// fluid light, the top Heatzone heavy (Heatnoise breaks it into plumes), so a lava lamp convects forever. Relax pulls
// density toward the slot input luma. Conserve (pass 0): every texel += target - mean, so the total density stays
// the seeded total (semi-Lagrangian advection alone drifts +-10 %, numpy).
// == builders/gen_sim_logic.py lava_step (numpy, test/test_gen_sim_lavalamp.py).
// uSim = W H seedmode epoch; uFl = buoyancy viscosity heat heatzone; uSd = fill seed relax conserve;
// uRun = nsteps frame heatnoise t.
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uSim;
uniform vec4 uFl;
uniform vec4 uSd;
uniform vec4 uRun;

vec4 at(ivec2 c, ivec2 sz) { return texelFetch(sTD2DInputs[0], clamp(c, ivec2(0), sz - 1), 0); }

float inLuma(vec2 p, ivec2 sz)
{
	ivec2 isz = textureSize(sTD2DInputs[1], 0);
	ivec2 q = clamp(ivec2(p * vec2(isz) / vec2(sz)), ivec2(0), isz - 1);
	return gs_luma(texelFetch(sTD2DInputs[1], q, 0).rgb);
}

float seedRho(ivec2 c, ivec2 sz)
{
	int mode = int(uSim.z + 0.5), sd = int(uSd.y);
	vec2 p = vec2(c) + 0.5;
	if (mode == 2) return inLuma(p, sz);
	if (mode == 1) {                                         // heavy blobs on a light bath
		float r = 0.0;
		for (int i = 0; i < 12; i++) {
			vec2 ctr = vec2(gs_hash3(i, 1, sd), gs_hash3(i, 2, sd)) * vec2(sz);
			float rad = (0.04 + 0.08 * gs_hash3(i, 3, sd)) * float(sz.y);
			r = max(r, length(p - ctr) < rad ? 1.0 : 0.0);
		}
		return r;
	}
	float y = float(sz.y) * (1.0 - uSd.x) + 0.02 * float(sz.y) * sin(p.x * 0.11 + float(sd)) + 2.0 * (gs_hash3(c.x, c.y, sd) - 0.5);
	return p.y > y ? 1.0 : 0.0;                              // layers: heavy fluid on top of light (unstable)
}

void main()
{
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(int(uSim.x + 0.5), int(uSim.y + 0.5));
	if (c.x >= sz.x || c.y >= sz.y) return;
	vec4 s = texelFetch(sTD2DInputs[0], c, 0);
	ivec2 isz = textureSize(sTD2DInputs[0], 0);
	vec4 mass = texelFetch(sTD2DInputs[2], ivec2(0), 0);
	if (isz != sz || abs(mass.a - uSim.w) > 0.5) {         // first frame, Reset, size change: seed (mass learns the
		// new epoch + target this frame, so the next frame steps)
		TDImageStoreOutput(0, ivec3(c, 0), vec4(0.0, 0.0, seedRho(c, sz), 0.0));
		return;
	}
	if (float(uTDPass) >= uRun.x) { TDImageStoreOutput(0, ivec3(c, 0), s); return; }
	vec2 p = vec2(c) + 0.5;
	vec4 adv = texture(sTD2DInputs[0], (p - s.xy) / vec2(sz));
	vec4 l = at(c - ivec2(1, 0), sz), r = at(c + ivec2(1, 0), sz), d = at(c - ivec2(0, 1), sz), u = at(c + ivec2(0, 1), sz);
	float div = 0.5 * ((r.x - l.x) + (u.y - d.y));
	float pn = 0.25 * (l.w + r.w + u.w + d.w - div);
	vec2 v = adv.xy - 0.5 * vec2(r.w - l.w, u.w - d.w);
	float rho = adv.z;
	v.y -= uFl.x * (rho - mass.x);
	v *= 1.0 - uFl.y;
	if (c.x == 0 || c.x == sz.x - 1) v.x = 0.0;
	if (c.y == 0 || c.y == sz.y - 1) v.y = 0.0;
	if (uFl.z > 0.0) {
		float hz = uFl.w * float(sz.y);
		float k = uFl.z * (1.0 + uRun.z * (gs_vnoise(vec2(p.x / max(0.08 * float(sz.x), 1.0), uRun.w * 0.3), int(uSd.y)) - 0.5) * 2.0);
		k = clamp(k, 0.0, 1.0);
		if (p.y < hz) rho += (0.0 - rho) * k;
		else if (p.y > float(sz.y) - hz) rho += (1.0 - rho) * k;
	}
	if (uSd.z > 0.0) rho += (inLuma(p, sz) - rho) * uSd.z;
	if (uTDPass == 0 && uSd.w > 0.5) rho += mass.x - mass.y;
	TDImageStoreOutput(0, ivec3(c, 0), vec4(v, rho, pn));
}
