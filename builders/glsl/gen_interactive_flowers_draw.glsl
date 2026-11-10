// gen_interactive_flowers_draw: flowers + flying petals + water streaks over the slot input (compute, slot input
// size, 16x16 groups). in0 = slot input, in1 = flower state (`state`), in2 = drops (`water`). Items = Count flowers
// then Drops drops; each workgroup walks them in chunks of 256 (one per thread): a thread keeps its item if its box
// (+ 2 px) touches the 16x16 tile, an ordered prefix sum packs the kept ones into shared memory, every pixel shades
// that list (painter's order, evaluated front to back: chunks and lists in reverse, acc += Tr v col, Tr *= 1 - v; a
// pixel stops at Tr < 1/1024 and the tile stops when all 256 pixels have: dense meadows cost what is visible), then
// the next chunk (any count works). Per-item geometry + colour are computed once per tile into shared memory.
// Flower: open = smooth01(age / Bloomtime); petal length Lp = size (0.15 + 0.85 open) (1 + 0.5 (beat + level)),
// width Wp = Lp Petalwidth SPW (0.4 + 0.6 open); n petals at rot + j TAU / n, half-width profile
// Wp max(sin(pi t^a), 0)^b (species table SPN SPA SPB SPW), distance max(|v| - hw, -u, u - Lp), 1 px AA; centre
// disc Lp x Centresize (resting only). Wilt (last Wilttime s of life) greys the petals x Wilt. Scatter (or life over:
// x 0.15 speed) = petals fly: v_j = dir(theta_j + (h_j - 0.5) 1.2) Scatterspeed (0.5 + h_j) + (0, 0.3 Scatterspeed),
// pos = Lp / 2 dir(theta_j) + v_j ts + (Wind ts, -Petalgravity ts^2 / 2), spin (2 h_j - 1) Spin ts, alpha 1 - ts /
// Falltime. Drop: streak A.xy -> A.xy - v Streak, width Dropwidth (1 + splash), colour water + splash x Splash.
// == builders/gen_interactive_flowers_logic.py flower_pose / shade_grid.
// uD = Count Drops Mode Petalwidth; uD2 = Scatterspeed Petalgravity Spin Wind; uD3 = Wilt Colorvar Dropwidth Streak;
// uD4 = water rgb Wateralpha; uD5 = centre rgb Centresize; uD6 = Bloomtime Falltime Wilttime Splash.
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uD;
uniform vec4 uD2;
uniform vec4 uD3;
uniform vec4 uD4;
uniform vec4 uD5;
uniform vec4 uD6;
uniform vec4 uDrv;
uniform vec4 uDg;

const float SPN[6] = float[6](9.0, 5.0, 6.0, 8.0, 5.0, 6.0);
const float SPA[6] = float[6](1.0, 0.7, 1.4, 1.2, 0.5, 0.8);
const float SPB[6] = float[6](0.5, 0.6, 0.8, 1.2, 1.5, 0.3);
const float SPW[6] = float[6](0.18, 0.45, 0.40, 0.35, 0.30, 0.55);

shared vec4 sA[256];
shared vec4 sB[256];
shared vec4 sC[256];
shared vec4 sDd[256];
shared float sK[256];
shared uint scn[2 * 256];
shared uint nlist;
shared uint ndone;

float gT, gBoost;

// flower geometry: c centre, Lp Wp, rot, ts (< 0 = resting), spd, alpha, wilt, n, species, open
void flower(vec4 A, vec4 B, out vec2 c, out vec4 g, out vec4 h, out int n, out int sp)
{
	float age = gT - A.z;
	float open = smoothstep(0.0, 1.0, clamp(age / max(uD6.x, 1e-3), 0.0, 1.0));
	sp = clamp(int(B.w + 0.5), 0, 5);
	n = int(SPN[sp]);
	float Lp = B.y * (0.15 + 0.85 * open) * gBoost;
	float Wp = Lp * uD.w * SPW[sp] * (0.4 + 0.6 * open);
	float ts = -1.0, spd = 0.0;
	if (B.z >= 0.0) { ts = gT - B.z; spd = uD2.x; }
	else if (age >= A.w) { ts = age - A.w; spd = uD2.x * 0.15; }
	float alpha = ts >= 0.0 ? clamp(1.0 - ts / max(uD6.y, 1e-3), 0.0, 1.0) : 1.0;
	float wilt = clamp((min(age, A.w) - (A.w - uD6.z)) / max(uD6.z, 1e-3), 0.0, 1.0);
	c = A.xy;
	g = vec4(Lp, Wp, B.x * GI_TAU, ts);
	h = vec4(spd, alpha, wilt, open);
}

void petalPose(vec4 g, vec4 h, float seed, int j, int n, out vec2 b, out float phi)
{
	float th = g.z + float(j) * GI_TAU / float(n);
	if (g.w < 0.0) { b = vec2(0.0); phi = th; return; }
	float hj = gs_hash3(int(seed * 65536.0), j, 7);
	float dv = th + (hj - 0.5) * 1.2;
	vec2 v = vec2(cos(dv), sin(dv)) * h.x * (0.5 + hj) + vec2(0.0, h.x * 0.3);
	float ts = g.w;
	vec2 pos = 0.5 * g.x * vec2(cos(th), sin(th)) + v * ts + vec2(uD2.w * ts, -0.5 * uD2.y * ts * ts);
	phi = th + uD2.z * (2.0 * hj - 1.0) * ts;
	b = pos - vec2(cos(phi), sin(phi)) * g.x * 0.5;
}

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	ivec2 fsz = textureSize(sTD2DInputs[1], 0), wsz = textureSize(sTD2DInputs[2], 0);
	int mode = int(uD.z + 0.5);
	int NF = (mode == 1) ? 0 : min(max(int(uD.x + 0.5), 0), (fsz.y - 1) * 64);
	int ND = (mode == 0) ? 0 : min(max(int(uD.y + 0.5), 0), (wsz.y - 1) * 64);
	int total = NF + ND;
	gT = texelFetch(sTD2DInputs[1], ivec2(0, fsz.y - 1), 0).y;
	float lvl = gi_level(uDrv, uDg);
	gBoost = 1.0 + 0.5 * (gi_env(uDrv, uDg) + lvl);
	uint li = gl_LocalInvocationIndex;
	vec2 lo = vec2(gl_WorkGroupID.xy * 16u), hi = lo + 16.0;
	bool inside = p.x < osz.x && p.y < osz.y;
	vec2 x = vec2(p) + 0.5;
	vec3 acc = vec3(0.0);          // front to back: acc += Tr x v x col, Tr *= 1 - v (== painter's order over)
	float Tr = 1.0;
	bool done = !inside;
	int nch = (total + 255) / 256;
	for (int ci = nch - 1; ci >= 0; ci--) {          // last chunk = frontmost items first
		int it = ci * 256 + int(li);
		uint mine = 0u;
		vec4 A = vec4(0.0), Bv = vec4(0.0), Cs = vec4(0.0), Ds = vec4(0.0);
		float kind = 0.0;
		if (it < total) {
			vec2 bmin, bmax;
			if (it < NF) {
				ivec2 t0 = ivec2(2 * (it % 64), it / 64);
				vec4 Ar = texelFetch(sTD2DInputs[1], t0, 0);
				vec4 Br = texelFetch(sTD2DInputs[1], t0 + ivec2(1, 0), 0);
				if (Ar.w > 0.0) {
					vec2 c; vec4 g, h; int n, sp;
					flower(Ar, Br, c, g, h, n, sp);
					if (h.y > 0.0) {
						bmin = c - g.x - 2.0; bmax = c + g.x + 2.0;
						if (g.w >= 0.0) {
							for (int j = 0; j < 9; j++) {
								if (j >= n) break;
								vec2 b; float phi;
								petalPose(g, h, Br.x, j, n, b, phi);
								vec2 e = b + vec2(cos(phi), sin(phi)) * g.x;
								bmin = min(bmin, min(c + b, c + e) - g.y - 2.0);
								bmax = max(bmax, max(c + b, c + e) + g.y + 2.0);
							}
						} else {
							float rr = max(length(g.xy), g.x * uD5.w) + 2.0;
							bmin = min(bmin, c - rr); bmax = max(bmax, c + rr);
						}
						if (bmax.x >= lo.x && bmin.x <= hi.x && bmax.y >= lo.y && bmin.y <= hi.y) {
							mine = 1u;
							vec3 pc = gs_pal(float(sp) / 6.0 + (Br.x - 0.5) * uD3.y);
							pc = mix(pc, vec3(gs_luma(pc)) * 0.55 + vec3(0.08, 0.05, 0.0), h.z * uD3.x);
							A = vec4(c, g.x, g.y);                 // per-item geometry once per tile, not per pixel
							Bv = vec4(g.z, g.w, h.x, h.y);
							Cs = vec4(pc, float(n) + 16.0 * float(sp));
							Ds = vec4(Br.x, 0.0, 0.0, 0.0);
						}
					}
				}
			} else {
				int d = it - NF;
				ivec2 t0 = ivec2(2 * (d % 64), d / 64);
				A = texelFetch(sTD2DInputs[2], t0, 0);
				Bv = texelFetch(sTD2DInputs[2], t0 + ivec2(1, 0), 0);
				kind = 1.0;
				if (Bv.z > 0.5) {
					vec2 tail = A.xy - A.zw * uD3.w;
					float r = 0.5 * uD3.z * (1.0 + Bv.x) + 2.0;
					bmin = min(A.xy, tail) - r; bmax = max(A.xy, tail) + r;
					if (bmax.x >= lo.x && bmin.x <= hi.x && bmax.y >= lo.y && bmin.y <= hi.y) mine = 1u;
				}
			}
		}
		scn[li] = mine;
		uint src = 0u;
		for (uint off = 1u; off < 256u; off <<= 1u) {
			barrier();
			uint v = scn[src * 256u + li];
			if (li >= off) v += scn[src * 256u + li - off];
			scn[(1u - src) * 256u + li] = v;
			src = 1u - src;
		}
		barrier();
		uint start = scn[src * 256u + li] - mine;
		if (mine == 1u) { sA[start] = A; sB[start] = Bv; sC[start] = Cs; sDd[start] = Ds; sK[start] = kind; }
		if (li == 255u) nlist = scn[src * 256u + li];
		if (li == 0u) ndone = 0u;
		barrier();
		if (!done) {
			uint nl = nlist;
			for (uint kk = nl; kk > 0u; kk--) {           // front to back inside the chunk too
				uint k = kk - 1u;
				vec4 a = sA[k], b = sB[k];
				vec3 col;
				float v;
				if (sK[k] < 0.5) {
					vec2 c = a.xy;
					vec4 g = vec4(a.z, a.w, b.x, b.y), h = vec4(b.z, b.w, 0.0, 0.0);
					vec4 cc = sC[k];
					int n = int(mod(cc.w, 16.0) + 0.5), sp = int(cc.w / 16.0);
					float seed = sDd[k].x;
					vec3 pc = cc.rgb;
					float fv = 0.0;
					col = pc;
					vec2 xc = x - c;
					bool resting = g.w < 0.0;
					// exact skips: a resting flower out of reach, and petals whose box (|l.y| <= Wp, 0 <= l.x <= Lp,
					// + 0.5 px AA) misses the pixel, add 0 coverage anyway
					if (resting && dot(xc, xc) > pow(max(length(g.xy), g.x * uD5.w) + 1.0, 2.0)) continue;
					float step_ = GI_TAU / float(n);
					float cs0 = cos(g.z), sn0 = sin(g.z), cst = cos(step_), snt = sin(step_);
					for (int j = 0; j < 9; j++) {
						if (j >= n) break;
						vec2 pb; float phi, cs, sn;
						if (resting) {
							pb = vec2(0.0); cs = cs0; sn = sn0;
							float c2 = cs0 * cst - sn0 * snt;
							sn0 = sn0 * cst + cs0 * snt; cs0 = c2;
						} else {
							petalPose(g, h, seed, j, n, pb, phi);
							cs = cos(phi); sn = sin(phi);
						}
						vec2 q = xc - pb;
						vec2 l = vec2(cs * q.x + sn * q.y, -sn * q.x + cs * q.y);
						if (l.x < -0.5 || l.x > g.x + 0.5 || abs(l.y) > g.y + 0.5) continue;
						float t = clamp(l.x / max(g.x, 1e-3), 0.0, 1.0);
						float hw = g.y * pow(max(sin(3.14159265 * pow(t, SPA[sp])), 0.0), SPB[sp]);
						float dd = max(abs(l.y) - hw, max(-l.x, l.x - g.x));
						float cv = clamp(0.5 - dd, 0.0, 1.0);
						if (cv > fv) { fv = cv; col = pc * (0.65 + 0.35 * t); }
					}
					if (resting) {
						float cv = clamp(0.5 - (length(xc) - g.x * uD5.w), 0.0, 1.0);
						col = mix(col, uD5.rgb, cv);
						fv = max(fv, cv);
					}
					v = fv * h.y;
				} else {
					float hh;
					float dd = gi_segdist(x, a.xy, a.xy - a.zw * uD3.w, hh) - 0.5 * uD3.z * (1.0 + b.x);
					v = clamp(clamp(0.5 - dd, 0.0, 1.0) * uD4.w * (1.0 + b.x), 0.0, 1.0);
					col = uD4.rgb + vec3(b.x * uD6.w);
				}
				acc += Tr * v * col;
				Tr *= 1.0 - v;
				if (Tr < 1.0 / 1024.0) { done = true; break; }
			}
		}
		if (done) atomicAdd(ndone, 1u);
		barrier();
		if (ndone == 256u) break;                       // the whole tile is opaque: nothing behind can show
	}
	if (!inside) return;
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, acc, 1.0 - Tr));
}
