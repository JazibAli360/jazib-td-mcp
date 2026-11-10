// gen_interactive_flowers_state: GEN_interactive 'flowers' flower slots (compute, 128 x (ceil(Count / 64) + 1),
// rgba32float). in0 = last state (Feedback `state_fb`), in1 = rack mask (`mask`: r presence, g motion), in2 = rack
// points (`pts`). Flower f = texels (2 (f % 64), f / 64): A = (x px, y px, birth T, life s; life 0 = empty slot),
// B = (seed 0..1, size px, scatter T (-1 = none), species 0..5). Meta row (last): texel 0 = (cooks, T module time,
// last absTime, epoch).
// Life: bloom (0..Bloomtime) -> hold -> wilt (last Wilttime s of Life) -> petals fall (Falltime) -> empty -> respawn.
// Motion at a living flower above Scatterthresh / (1 + level) = scatter now (petals fly, empty after Falltime).
// An empty slot tries one candidate per cook: with chance Nearshare near a present point (+- Spawnnear px, any
// presence), else a hashed spot accepted with chance Spawnrate x dt x (1 + beat pulse) x presence x still^Stillness,
// still = clamp(1 - motion / Scatterthresh). Speed 0 = frozen (dt 0: no births, ages hold); a second cook in the same
// frame holds; new epoch / size = all empty.  == builders/gen_interactive_flowers_logic.py state_step.
// uTime = now Speed epoch Count; uSz = frame W H Seed Mode; uLife = Bloomtime Life Lifevar Wilttime;
// uSp = Spawnrate Stillness Scatterthresh Falltime; uSp2 = Nearshare Spawnnear Size Sizevar; uSp3 = Species 0 0 0.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uTime;
uniform vec4 uSz;
uniform vec4 uLife;
uniform vec4 uSp;
uniform vec4 uSp2;
uniform vec4 uSp3;
uniform vec4 uDrv;
uniform vec4 uDg;

vec2 maskAt(vec2 pos)
{
	ivec2 ms = textureSize(sTD2DInputs[1], 0);
	ivec2 q = clamp(ivec2(pos / uSz.xy * vec2(ms)), ivec2(0), ms - 1);
	return texelFetch(sTD2DInputs[1], q, 0).rg;
}

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	int N = max(int(uTime.w + 0.5), 1);
	int rows = (N + 63) / 64;
	if (p.x >= 128 || p.y > rows) return;
	ivec2 ssz = textureSize(sTD2DInputs[0], 0);
	bool fresh = ssz.x != 128 || ssz.y != rows + 1;
	vec4 m0 = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], ivec2(0, rows), 0);
	fresh = fresh || m0.w != uTime.z;
	if (fresh) m0 = vec4(0.0, 0.0, uTime.x, uTime.z);
	if (!fresh && m0.z == uTime.x) { TDImageStoreOutput(0, ivec3(p, 0), texelFetch(sTD2DInputs[0], p, 0)); return; }
	float dt = gi_dt(m0, uTime.x, fresh) * uTime.y;
	float T = m0.y + dt;
	int cook = int(m0.x + 0.5);
	if (p.y == rows) {
		TDImageStoreOutput(0, ivec3(p, 0), p.x == 0 ? vec4(float(cook + 1), T, uTime.x, uTime.z) : vec4(0.0));
		return;
	}
	int f = p.y * 64 + p.x / 2;
	int part = p.x % 2;
	ivec2 base = ivec2(2 * (p.x / 2), p.y);
	vec4 A = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], base, 0);
	vec4 B = fresh ? vec4(0.0, 0.0, -1.0, 0.0) : texelFetch(sTD2DInputs[0], base + ivec2(1, 0), 0);
	int mode = int(uSz.w + 0.5);
	float level = gi_level(uDrv, uDg);
	if (f >= N || mode == 1) { A = vec4(0.0); B = vec4(0.0, 0.0, -1.0, 0.0); }
	else if (A.w > 0.0) {                                       // living / falling flower
		float age = T - A.z;
		if (B.z < 0.0 && age >= 0.0 && age < A.w) {
			float thr = uSp.z / (1.0 + max(level, 0.0));
			if (maskAt(A.xy).g > thr) B.z = T;
		}
		bool dead = B.z >= 0.0 ? (T - B.z >= uSp.w) : (age >= A.w + uSp.w);
		if (dead) { A = vec4(0.0); B = vec4(0.0, 0.0, -1.0, 0.0); }
	} else if (dt > 0.0) {                                      // empty: one candidate this cook
		int sd = int(uSz.z);
		float h0 = gs_hash3(f, cook * 8 + 1, sd), h1 = gs_hash3(f, cook * 8 + 2, sd);
		float h2 = gs_hash3(f, cook * 8 + 3, sd), h3 = gs_hash3(f, cook * 8 + 4, sd);
		float h4 = gs_hash3(f, cook * 8 + 5, sd), h5 = gs_hash3(f, cook * 8 + 6, sd);
		float h6 = gs_hash3(f, cook * 8 + 7, sd), h7 = gs_hash3(f, cook * 8, sd);
		vec2 pos = vec2(h1, h2) * uSz.xy;
		bool ok = false;
		float rate = uSp.x * dt * (1.0 + gi_env(uDrv, uDg) + max(level, 0.0));
		if (h3 < uSp2.x) {                                      // near a point
			ivec2 psz = textureSize(sTD2DInputs[2], 0);
			int k = min(int(h4 * float(psz.x)), psz.x - 1);
			vec4 q = texelFetch(sTD2DInputs[2], ivec2(k, 0), 0);
			if (gi_present(q)) {
				pos = q.xy * uSz.xy + (vec2(h1, h2) * 2.0 - 1.0) * uSp2.y;
				ok = h0 < rate;
			}
		} else {
			vec2 mk = maskAt(pos);
			float still = clamp(1.0 - mk.g / max(uSp.z, 1e-6), 0.0, 1.0);
			ok = h0 < rate * clamp(mk.r, 0.0, 1.0) * pow(still, max(uSp.y, 0.0));
		}
		if (ok) {
			float life = max(uLife.y * (1.0 + uLife.z * (2.0 * h5 - 1.0)), 1e-3);
			float size = uSp2.z * (1.0 + uSp2.w * (2.0 * h4 - 1.0));
			int sp = int(uSp3.x + 0.5);
			float species = sp > 0 ? float(sp - 1) : min(floor(h7 * 6.0), 5.0);
			A = vec4(pos, T, life);
			B = vec4(h6, size, -1.0, species);
		}
	}
	TDImageStoreOutput(0, ivec3(p, 0), part == 0 ? A : B);
}
