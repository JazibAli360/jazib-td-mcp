// Shared effector adapters (builders/effectors.py attach): small helpers over px_common's packed list (pxe*), used
// by the consumer shaders that define PXE_HOOK. Prepended after effectors_logic.consumer_header() + px_common.glsl.
// Every helper returns "no effect" when uEffSel.z (Effon) is 0, so a COMP with the adapter off looks unchanged.

// ---- shared voxel grid accessors (lane E; effectors_grid_logic.py, passes eff_grid_*.glsl, doc docs/builds/
// effectors.md "Voxel grid"). Kept here (not in px_common) so px_common only carries the three cloud hooks; a shader
// that includes px_common without this file and defines PXE_GRID must paste this section after px_common.
// Grid region at G = the light header's w (version >= 3): texel G = (layer count, 2, 0, 0), then per layer (origin xyz,
// cell), (N, tiles across TX, kind 1 field / 2 paint, on). Voxel (x, y, z) = atlas texel (x + (z % TX) N,
// y + (z / TX) N); centre = origin + (v + 0.5) cell. Consumers that read the grid define PXE_GRID (sampler of
// /project1/effectors/grid/grid_field) and / or PXE_PAINT (grid/paint_out) BEFORE px_common, e.g. `#define PXE_GRID
// sEffGrid` + a Samplers-page sampler on a GLSL MAT, or `sTD2DInputs[k]` on a GLSL TOP (effectors_grid_logic.
// consumer_defines). With PXE_GRID, `cloud` rows (point sets > 4096 from a TOP) take part in pxeSel / pxeSd / pxeGrad.
const int PXG_FIELD = 1;
const int PXG_PAINT = 2;

// First texel of the grid layer of `kind` (-1: none / grid off / older buffer).
int pxgLayer(int kind)
{
	int g = pxeExtBase(3);
	if (g < 0) return -1;
	vec4 h = texelFetch(PXE_ROWS, g);
	int n = pxI(h.x), st = max(pxI(h.y), 2);
	for (int j = 0; j < 8; j++) {
		if (j >= n) break;
		vec4 b = texelFetch(PXE_ROWS, g + 2 + j * st);
		if (pxI(b.z) == kind && b.w > 0.5) return g + 1 + j * st;
	}
	return -1;
}

ivec2 pxgAtlas(ivec3 v, int N, int tx) { return ivec2(v.x + (v.z % tx) * N, v.y + (v.z / tx) * N); }

// Voxel v of layer L (texel from pxgLayer) in its atlas s, clamped into the grid.
vec4 pxgFetch(sampler2D s, int L, ivec3 v)
{
	vec4 b = texelFetch(PXE_ROWS, L + 1);
	int N = pxI(b.x);
	return texelFetch(s, pxgAtlas(clamp(v, ivec3(0), ivec3(N - 1)), N, pxI(b.y)), 0);
}

// Trilinear sample between voxel centres (clamped at the edges): CPU twin effectors_grid_logic.sample_ref.
vec4 pxgSample(sampler2D s, int L, vec3 p)
{
	vec4 a = texelFetch(PXE_ROWS, L);
	int N = pxI(texelFetch(PXE_ROWS, L + 1).x);
	vec3 g = clamp((p - a.xyz) / a.w - 0.5, vec3(0.0), vec3(float(N - 1)));
	ivec3 b = min(ivec3(floor(g)), ivec3(max(N - 2, 0)));
	vec3 f = g - vec3(b);
	vec4 x00 = mix(pxgFetch(s, L, b), pxgFetch(s, L, b + ivec3(1, 0, 0)), f.x);
	vec4 x10 = mix(pxgFetch(s, L, b + ivec3(0, 1, 0)), pxgFetch(s, L, b + ivec3(1, 1, 0)), f.x);
	vec4 x01 = mix(pxgFetch(s, L, b + ivec3(0, 0, 1)), pxgFetch(s, L, b + ivec3(1, 0, 1)), f.x);
	vec4 x11 = mix(pxgFetch(s, L, b + ivec3(0, 1, 1)), pxgFetch(s, L, b + ivec3(1, 1, 1)), f.x);
	return mix(mix(x00, x10, f.y), mix(x01, x11, f.y), f.z);
}

#ifdef PXE_GRID
// Distance from p to the nearest cloud point (seed) among the 8 voxels around p; 1e9 when the field is off / empty.
// CPU twin effectors_grid_logic.query_ref (error vs brute force < 1 cell).
float pxgFieldNearest(vec3 p, out vec3 seed)
{
	seed = vec3(0.0);
	int L = pxgLayer(PXG_FIELD);
	if (L < 0) return 1e9;
	vec4 a = texelFetch(PXE_ROWS, L);
	ivec3 b = ivec3(floor((p - a.xyz) / a.w - 0.5));
	float bd = 3.4e38;
	for (int c = 0; c < 8; c++) {
		vec4 s = pxgFetch(PXE_GRID, L, b + ivec3(c & 1, (c >> 1) & 1, (c >> 2) & 1));
		if (s.w < 0.5) continue;
		float d = dot(p - s.xyz, p - s.xyz);
		if (d < bd) { bd = d; seed = s.xyz; }
	}
	return bd > 3.0e38 ? 1e9 : sqrt(bd);
}

float pxgFieldSd(vec3 p) { vec3 s; return pxgFieldNearest(p, s); }
#endif

#ifdef PXE_PAINT
// Painted mask (0..1) at p, trilinear; 0 when the paint volume is off.
float pxePaint(vec3 p)
{
	int L = pxgLayer(PXG_PAINT);
	return L < 0 ? 0.0 : pxgSample(PXE_PAINT, L, p).r;
}
#endif

// Weight + strongest effector at p with the consumer's selection uniforms.
float pxeConsumerW(vec3 p, out int best) { return pxeW(p, uEffSel, uEffIds, uEffMix, uEffFall, best); }

#ifdef PXE_PARTICLES
uniform vec4 uEffP;    // push (outward), attract (to the surface), vortex (around the up axis), wake (effector velocity)
uniform vec4 uEffP2;   // kill weight (0 = off), spawn fraction 0..1, spawn radius, drag near effectors

// BO_particles: extra acceleration near the selected effectors.
vec3 pxeParticleForce(vec3 P, vec3 V)
{
	if (uEffSel.z < 0.5) return vec3(0.0);
	int b;
	float w = pxeConsumerW(P, b);
	if (b < 0 || w <= 0.0) return vec3(0.0);
	vec3 dir = pxeGrad(b, P);
	vec3 tng = pxSafeN(cross(pxeAxis(b), P - pxeCentre(b)), vec3(0.0));
	return w * (dir * (uEffP.x - uEffP.y) + tng * uEffP.z + pxeVelAt(b, P) * uEffP.w - V * uEffP2.w);
}

// Particle dies where the weight reaches the kill level.
bool pxeKill(vec3 P)
{
	if (uEffSel.z < 0.5 || uEffP2.x <= 0.0) return false;
	int b;
	return pxeConsumerW(P, b) >= uEffP2.x;
}

// Spawn position: with probability uEffP2.y a random selected effector's centre (point sets: a random point) + a
// random offset in a ball of radius uEffP2.z; else P unchanged. r0..r3 = uniform randoms.
vec3 pxeSpawnAt(vec3 P, float r0, float r1, float r2, float r3)
{
	if (uEffSel.z < 0.5 || uEffP2.y <= 0.0 || r0 >= uEffP2.y) return P;
	int ns = pxeNumSel(uEffSel, uEffIds);
	if (ns < 1) return P;
	int i = pxeNth(uEffSel, uEffIds, min(int(r1 * float(ns)), ns - 1));
	if (i < 0) return P;
	vec3 c = pxeCentre(i);
	if (pxeIsPts(i)) {
		int m = pxI(pxeT(i, 8).w);
		if (m > 0) c = pxePtsPoint(i, min(int(r2 * float(m)), m - 1));
	}
	float z = 2.0 * r2 - 1.0, ph = PX_TAU * r3, s = sqrt(max(0.0, 1.0 - z * z));
	return c + vec3(s * cos(ph), s * sin(ph), z) * (uEffP2.z * pow(fract(r3 * 7.13 + r1), 1.0 / 3.0));
}
#endif

#ifdef PXE_POINTS
uniform vec4 uEffFx;   // push (units, outward), dissolve (-1..1: + near fades, - far fades = reveal near), scale gain, dust
uniform vec4 uEffFx2;  // direction (0 outward, 1 up axis, 2 effector velocity), 0, 0, 0

struct PXEFx { vec3 off; float alpha; float scale; float w; };

// BL_splat_render / BL_cloud_morph: per point / splat offset, alpha and scale factors. seed = a stable per-point id.
PXEFx pxePointFx(vec3 p, float seed)
{
	PXEFx r;
	r.off = vec3(0.0);
	r.alpha = 1.0;
	r.scale = 1.0;
	r.w = 0.0;
	if (uEffSel.z < 0.5) return r;
	int b;
	float w = pxeConsumerW(p, b);
	r.w = w;
	if (b < 0) return r;
	int dm = pxI(uEffFx2.x);
	vec3 dir = dm == 1 ? pxeAxis(b) : (dm == 2 ? pxeVelAt(b, p) : pxeGrad(b, p));
	r.off = dir * (uEffFx.x * w);
	float a = uEffFx.y >= 0.0 ? uEffFx.y * clamp(w, 0.0, 1.0) : -uEffFx.y * (1.0 - clamp(w, 0.0, 1.0));
	if (uEffFx.w > 0.5) {
		float h = float(pxHash(uint(abs(seed)) * 747796405u + 2891336453u) >> 8u) * (1.0 / 16777216.0);
		r.alpha = clamp((h - a) * 20.0 + 1.0, 0.0, 1.0);       // dust: each point drops at its own threshold
	} else {
		r.alpha = clamp(1.0 - a, 0.0, 1.0);
	}
	r.scale = max(1.0 + uEffFx.z * w, 0.0);
	return r;
}
#endif
