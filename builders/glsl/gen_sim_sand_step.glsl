// gen_sim_sand_step: GEN_sim 'sand' falling-sand step (compute, npasses = steps this frame; pass n+1 reads pass n as
// input 0, T-91 (3)). Margolus neighbourhood: the grid is cut into 2x2 blocks, the cut shifts by (1, 1) every step;
// every thread computes its whole block's move (the same in all 4 threads: hashes of the block + step) and writes its
// own cell. Inside a block cells only swap places, so material counts are conserved exactly (sources excepted).
// Materials: 0 empty, 1 sand (heavy), 2 water (light, flows sideways), 3 wall (never moves; outside = wall).
// Per step: walls from the slot input (Walls: luma > Threshold), pour (top band at Pourx +- Pourw, Rate per cell per
// step), hits (pass 0: a disc of Hitmat for every hit not applied yet, at a random x), drain (bottom row empties);
// then rules: 1 fall (column swap when the top is heavier), 2 topple (a supported top grain slides diagonally down),
// 3 flow (water swaps sideways with empty). State rgba8: r = material / 3, g = grain shade (moves with the grain),
// b = hits applied (mod 256) / 255, a = epoch (1..255) / 255. == builders/gen_sim_logic.py sand_step.
// uSim = W H seedmode epoch; uRule = fall topple flow drain; uSrc = rate pourx pourw pourmat;
// uHit = hitn hitsize hitmat seed; uIn = walls threshold density nsteps; uRun = frame 0 0 0.
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uSim;
uniform vec4 uRule;
uniform vec4 uSrc;
uniform vec4 uHit;
uniform vec4 uIn;
uniform vec4 uRun;

int matOf(vec4 s) { return int(floor(s.r * 3.0 + 0.5)); }
float wOf(int m) { return m == 1 ? 2.0 : (m == 2 ? 1.0 : 0.0); }
bool mov(int m) { return m == 1 || m == 2; }

float inLuma(ivec2 c, ivec2 sz)
{
	ivec2 isz = textureSize(sTD2DInputs[1], 0);
	ivec2 q = clamp(ivec2((vec2(c) + 0.5) * vec2(isz) / vec2(sz)), ivec2(0), isz - 1);
	return gs_luma(texelFetch(sTD2DInputs[1], q, 0).rgb);
}

// cell c after this step's sources (walls, pour, hits, drain); m = material, g = shade
void cellPre(ivec2 c, ivec2 sz, int sid, int pass, float done, out int m, out float g)
{
	if (c.x < 0 || c.y < 0 || c.x >= sz.x || c.y >= sz.y) { m = 3; g = 0.0; return; }
	vec4 s = texelFetch(sTD2DInputs[0], c, 0);
	m = matOf(s); g = s.g;
	int sd = int(uHit.w);
	if (uIn.x > 0.5) {
		bool wall = inLuma(c, sz) > uIn.y;
		if (wall && m == 0) { m = 3; g = 0.5; }
		else if (!wall && m == 3) m = 0;
	}
	if (m == 0 && uSrc.x > 0.0 && c.y >= sz.y - 2 && abs((float(c.x) + 0.5) / float(sz.x) - uSrc.y) <= uSrc.z
		&& gs_hash3(c.x, c.y, sid * 3 + 1 + sd) < uSrc.x) {
		m = int(uSrc.w + 0.5); g = gs_hash3(c.x, c.y, sid * 3 + 2 + sd);
	}
	if (pass == 0 && m == 0) {                               // hits not applied yet (at most 8 per frame)
		float pend = mod(uHit.x - done, 256.0);
		for (int k = 1; k <= 8; k++) {
			if (float(k) > pend) break;
			int N = int(uHit.x - pend) + k;
			vec2 ctr = vec2(gs_hash3(N, 7, sd) * float(sz.x), float(sz.y) - uHit.y - 2.0);
			if (length(vec2(c) + 0.5 - ctr) < uHit.y) { m = int(uHit.z + 0.5); g = gs_hash3(c.x, c.y, N + 4096 * sd); }
		}
	}
	if (c.y == 0 && mov(m) && uRule.w > 0.0 && gs_hash3(c.x, sid, 99 + sd) < uRule.w) m = 0;
}

void main()
{
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(int(uSim.x + 0.5), int(uSim.y + 0.5));
	if (c.x >= sz.x || c.y >= sz.y) return;
	vec4 s = texelFetch(sTD2DInputs[0], c, 0);
	ivec2 isz = textureSize(sTD2DInputs[0], 0);
	float ep = uSim.w / 255.0;
	if (isz != sz || abs(s.a - ep) > 0.5 / 255.0) {        // first frame, Reset, size change: seed
		int mode = int(uSim.z + 0.5), sd = int(uHit.w);
		float h = gs_hash3(c.x, c.y, sd), m = 0.0, g = gs_hash3(c.x, c.y, sd + 1);
		if (mode == 1 && float(c.y) > 0.45 * float(sz.y) && h < uIn.z) m = 1.0;            // pile: sand cloud
		else if (mode == 2) { float l = inLuma(c, sz); if (l > uIn.y) { m = 1.0; g = l; } }   // input: bright = sand
		else if (mode == 3 && h < uIn.z) m = float(c.y) > 0.5 * float(sz.y) ? 1.0 : 2.0;     // sand over water
		TDImageStoreOutput(0, ivec3(c, 0), vec4(m / 3.0, g, mod(uHit.x, 256.0) / 255.0, ep));
		return;
	}
	if (float(uTDPass) >= uIn.w) { TDImageStoreOutput(0, ivec3(c, 0), s); return; }
	int sid = int(uRun.x) * 8 + uTDPass;
	int o = (int(uRun.x) * int(uIn.w + 0.5) + uTDPass) & 1;
	ivec2 b0 = ivec2(floor(vec2(c - o) * 0.5)) * 2 + o;
	float done = floor(s.b * 255.0 + 0.5);
	int mA, mB, mC, mD; float gA, gB, gC, gD;
	cellPre(b0 + ivec2(0, 1), sz, sid, uTDPass, done, mA, gA);
	cellPre(b0 + ivec2(1, 1), sz, sid, uTDPass, done, mB, gB);
	cellPre(b0, sz, sid, uTDPass, done, mC, gC);
	cellPre(b0 + ivec2(1, 0), sz, sid, uTDPass, done, mD, gD);
	int sd = int(uHit.w);
	float r0 = gs_hash3(b0.x, b0.y, sid * 5 + sd), r1 = gs_hash3(b0.x, b0.y, sid * 5 + 1 + sd);
	float r2 = gs_hash3(b0.x, b0.y, sid * 5 + 2 + sd), r3 = gs_hash3(b0.x, b0.y, sid * 5 + 3 + sd);
	int tm; float tg;
	// 1 fall
	if (r0 < uRule.x) {
		if (mov(mA) && mC != 3 && wOf(mA) > wOf(mC)) { tm = mA; mA = mC; mC = tm; tg = gA; gA = gC; gC = tg; }
		if (mov(mB) && mD != 3 && wOf(mB) > wOf(mD)) { tm = mB; mB = mD; mD = tm; tg = gB; gB = gD; gD = tg; }
	}
	// 2 topple
	bool ad = mov(mA) && mD != 3 && wOf(mA) > wOf(mD) && (mC == 3 || wOf(mC) >= wOf(mA));
	bool bc = mov(mB) && mC != 3 && wOf(mB) > wOf(mC) && (mD == 3 || wOf(mD) >= wOf(mB));
	if (r2 < uRule.y) {
		if (ad && (!bc || r1 < 0.5)) { tm = mA; mA = mD; mD = tm; tg = gA; gA = gD; gD = tg; }
		else if (bc) { tm = mB; mB = mC; mC = tm; tg = gB; gB = gC; gC = tg; }
	}
	// 3 flow (water sideways)
	if (r3 < uRule.z) {
		if ((mC == 2 && mD == 0) || (mD == 2 && mC == 0)) { tm = mC; mC = mD; mD = tm; tg = gC; gC = gD; gD = tg; }
		if ((mA == 2 && mB == 0) || (mB == 2 && mA == 0)) { tm = mA; mA = mB; mB = tm; tg = gA; gA = gB; gB = tg; }
	}
	ivec2 l = c - b0;
	int m = l.y == 1 ? (l.x == 0 ? mA : mB) : (l.x == 0 ? mC : mD);
	float g = l.y == 1 ? (l.x == 0 ? gA : gB) : (l.x == 0 ? gC : gD);
	float nd = uTDPass == 0 ? mod(uHit.x, 256.0) : done;
	TDImageStoreOutput(0, ivec3(c, 0), vec4(float(m) / 3.0, g, nd / 255.0, ep));
}
