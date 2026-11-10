// PX_pointfx shared GLSL library (clean-room, 26 Oct 2026). Every function here has a numpy twin in
// builders/px_logic.py (ref_* / np_*), checked by test/test_px.py. Included ONCE by the generated stage shaders,
// after the uniform declarations (uG[PX_G_ROWS], uE[88], uPts / uPtsV / uTrail texture buffers; px_logic.decl()).
// Effector rows (PX_EP = 11 per effector, max 8): 0..2 inverse world matrix rows (world -> local, affine), 3 = (sdf
// type, local size xyz), 4 = (world centre xyz, world scale), 5 = (up axis xyz (camera: forward), speed units/s),
// 6 = (velocity xyz, point-set start), 7 = (point count, point mode, trail start, trail count), 8..10 = world matrix.
// Sdf types: 0 point, 1 sphere (r = x), 2 box (half extents xyz), 3 plane (local y = 0, +y outside), 4 capsule
// (radius x, half height y), 5 torus (R x, r y), 6 point set (uPts, radius x), 7 actor layer points (state texture,
// radius x). Distances are local * world scale (exact for uniform scale).
// Each stage template #defines PX_STATE_TEX(t) / PX_STATE_SIZE (its state texture) before //@DECL (pxStateT).
// T-35: every texelFetch is bounds-checked, every loop is bounded (<= 8 effectors, <= 6 octaves, <= 4096 points,
// <= 64 trail samples).

const float PX_PI = 3.141592653589793;
const float PX_TAU = 6.283185307179586;

int pxI(float x) { return int(floor(x + 0.5)); }

uint pxHash(uint x)
{
	x ^= x >> 16u;
	x *= 0x7feb352du;
	x ^= x >> 15u;
	x *= 0x846ca68bu;
	x ^= x >> 16u;
	return x;
}

float pxRnd(uint id, uint salt) { return float(pxHash(id * 2654435761u + salt) >> 8u) * (1.0 / 16777216.0); }

vec3 pxRnd3(uint id, uint salt) { return vec3(pxRnd(id, salt), pxRnd(id, salt + 1u), pxRnd(id, salt + 2u)); }

// Chunk cell id (header chunk): one id per rest cell, so every point of a cell shares its random values.
uint pxCellId(vec3 c)
{
	ivec3 k = ivec3(c);
	return pxHash(uint(k.x) * 73856093u ^ uint(k.y) * 19349663u ^ uint(k.z) * 83492791u) | 1u;
}

// Weyl sequence in fixed point: exact on GPU and in numpy (no float precision loss at 4M points).
float pxWeyl(uint id, uint k) { return float((id * k) >> 8u) * (1.0 / 16777216.0); }

float pxLattice(ivec3 c, uint seed)
{
	uint h = uint(c.x) * 73856093u ^ uint(c.y) * 19349663u ^ uint(c.z) * 83492791u ^ (seed * 2654435761u);
	return float(pxHash(h) >> 8u) * (1.0 / 16777216.0);
}

// Value noise 0..1, smoothstep-interpolated lattice.
float pxNoise(vec3 p, uint seed)
{
	vec3 i = floor(p);
	vec3 f = p - i;
	vec3 u = f * f * (3.0 - 2.0 * f);
	ivec3 c = ivec3(i);
	float n000 = pxLattice(c, seed);
	float n100 = pxLattice(c + ivec3(1, 0, 0), seed);
	float n010 = pxLattice(c + ivec3(0, 1, 0), seed);
	float n110 = pxLattice(c + ivec3(1, 1, 0), seed);
	float n001 = pxLattice(c + ivec3(0, 0, 1), seed);
	float n101 = pxLattice(c + ivec3(1, 0, 1), seed);
	float n011 = pxLattice(c + ivec3(0, 1, 1), seed);
	float n111 = pxLattice(c + ivec3(1, 1, 1), seed);
	return mix(mix(mix(n000, n100, u.x), mix(n010, n110, u.x), u.y),
	           mix(mix(n001, n101, u.x), mix(n011, n111, u.x), u.y), u.z);
}

// Fractal value noise 0..1 (normalised by the amplitude sum).
float pxFbm(vec3 p, int oct, uint seed)
{
	float a = 0.5, s = 0.0, n = 0.0;
	for (int o = 0; o < 6; o++) {
		if (o >= oct) break;
		s += a * pxNoise(p, seed + uint(o) * 101u);
		n += a;
		p = p * 2.0 + vec3(17.1, 3.7, 9.3);
		a *= 0.5;
	}
	return n > 0.0 ? s / n : 0.5;
}

// Curl noise: psi_c = sum_k sin(K.p + W t + j) (3 waves per component), curl taken analytically, so the field is
// exactly divergence-free (no clumping). Octave o samples (curl psi)(p * 2^o), which is curl(psi(p 2^o) / 2^o).
const vec3 PXK[9] = vec3[9](vec3(1.31, 1.73, -0.67), vec3(-1.11, 0.53, 1.97), vec3(0.79, -1.63, 1.21),
                            vec3(1.89, -0.41, 0.93), vec3(-0.57, 1.37, -1.49), vec3(1.07, 1.19, 1.51),
                            vec3(-1.71, -0.83, 0.47), vec3(0.61, 1.91, -1.03), vec3(1.43, -1.27, -0.89));
const float PXW[9] = float[9](0.31, -0.47, 0.23, 0.53, -0.29, 0.41, -0.37, 0.19, 0.44);

vec3 pxCurl1(vec3 p, float t)
{
	vec3 g0 = vec3(0.0), g1 = vec3(0.0), g2 = vec3(0.0);
	for (int k = 0; k < 3; k++) {
		g0 += PXK[k] * cos(dot(PXK[k], p) + PXW[k] * t + float(k));
		g1 += PXK[3 + k] * cos(dot(PXK[3 + k], p) + PXW[3 + k] * t + float(3 + k));
		g2 += PXK[6 + k] * cos(dot(PXK[6 + k], p) + PXW[6 + k] * t + float(6 + k));
	}
	return 0.25 * vec3(g2.y - g1.z, g0.z - g2.x, g1.x - g0.y);
}

vec3 pxCurl(vec3 p, float t, int oct)
{
	vec3 s = vec3(0.0);
	float a = 1.0, sc = 1.0, n = 0.0;
	for (int o = 0; o < 4; o++) {
		if (o >= oct) break;
		s += a * pxCurl1(p * sc + float(o) * vec3(5.3, 1.7, 3.1), t);
		n += a;
		a *= 0.5;
		sc *= 2.0;
	}
	return n > 0.0 ? s / n : vec3(0.0);
}

vec3 pxSafeN(vec3 v, vec3 fb) { float l = length(v); return l > 1e-8 ? v / l : fb; }

vec3 pxRot(vec3 v, vec3 ax, float a)
{
	float c = cos(a), s = sin(a);
	return v * c + cross(ax, v) * s + ax * dot(ax, v) * (1.0 - c);
}

// ---- quaternions (w, x, y, z), the splat convention of splat_render.glsl / splat_render_logic.quat_to_mat3

vec4 pxQMul(vec4 a, vec4 b)
{
	return vec4(a.x * b.x - dot(a.yzw, b.yzw), a.x * b.yzw + b.x * a.yzw + cross(a.yzw, b.yzw));
}

vec4 pxQAxis(vec3 ax, float ang) { return vec4(cos(0.5 * ang), pxSafeN(ax, vec3(0.0, 1.0, 0.0)) * sin(0.5 * ang)); }

vec4 pxQNorm(vec4 q) { float l = length(q); return l > 1e-8 ? q / l : vec4(1.0, 0.0, 0.0, 0.0); }

// nlerp toward identity by t (lattice snap: S4 "snap = identity rotation")
vec4 pxQToId(vec4 q, float t)
{
	vec4 id = vec4(1.0, 0.0, 0.0, 0.0);
	if (q.x < 0.0) q = -q;
	return pxQNorm(mix(q, id, clamp(t, 0.0, 1.0)));
}

mat3 pxQMat(vec4 q)
{
	q = pxQNorm(q);
	float w = q.x, x = q.y, y = q.z, z = q.w;
	// columns of R (R rows as in splat_render.glsl r0 r1 r2, transposed into column-major)
	return mat3(vec3(1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y + w * z), 2.0 * (x * z - w * y)),
	            vec3(2.0 * (x * y - w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z + w * x)),
	            vec3(2.0 * (x * z + w * y), 2.0 * (y * z - w * x), 1.0 - 2.0 * (x * x + y * y)));
}

// ---- bend (twist mode bend): a = long axis, bd = the direction it curves toward, n = a x bd (rotation axis)

void pxBendFrame(vec3 a, out vec3 bd, out vec3 n)
{
	vec3 up = vec3(0.0, 1.0, 0.0);
	bd = up - a * dot(up, a);
	if (length(bd) < 1e-3) bd = vec3(1.0, 0.0, 0.0) - a * a.x;
	bd = pxSafeN(bd, vec3(1.0, 0.0, 0.0));
	n = cross(a, bd);
}

// Arc-length-keeping bend with curvature k (rad per unit) about the centre; q = the local rotation (S4).
vec3 pxBend(vec3 r, vec3 a, vec3 bd, vec3 n, float k, out vec4 q)
{
	q = vec4(1.0, 0.0, 0.0, 0.0);
	if (abs(k) < 1e-6) return r;
	float s = dot(r, a);
	float y = dot(r, bd);
	float th = k * s;
	float rho = 1.0 / k - y;
	q = pxQAxis(n, th);
	return r - a * s - bd * y + a * (rho * sin(th)) + bd * (1.0 / k - rho * cos(th));
}

// Unit direction inside a cone of half angle cone (rad) around ax (uniform in solid angle); mirrors ref_cone_dirs.
vec3 pxCone(vec3 ax, float cone, uint id, uint fr)
{
	ax = pxSafeN(ax, vec3(0.0, 1.0, 0.0));
	float u1 = pxRnd(id, fr * 19u + 131u);
	float u2 = pxRnd(id, fr * 23u + 137u);
	float ct = 1.0 - u1 * (1.0 - cos(clamp(cone, 0.0, PX_PI)));
	float st = sqrt(max(1.0 - ct * ct, 0.0));
	float ph = PX_TAU * u2;
	vec3 t = abs(ax.x) < 0.9 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0);
	vec3 e1 = normalize(cross(ax, t));
	vec3 e2 = cross(ax, e1);
	return ax * ct + e1 * (st * cos(ph)) + e2 * (st * sin(ph));
}

float pxLum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

// SA15 splat attributes from the rest scale texel (0 for plain points): k 0 size (geometric mean of the scales),
// 1 flatness (smallest / largest scale: 0 = a flat disc, 1 = round).
float pxSplatAttr(vec3 sc, int k)
{
	vec3 a = abs(sc);
	if (k == 0) return pow(max(a.x * a.y * a.z, 0.0), 1.0 / 3.0);
	float mx = max(a.x, max(a.y, a.z));
	return mx > 0.0 ? min(a.x, min(a.y, a.z)) / mx : 1.0;
}

vec3 pxHue(vec3 c, float turns)
{
	// YIQ rotation (hue shift in turns)
	float a = turns * PX_TAU;
	float y = dot(c, vec3(0.299, 0.587, 0.114));
	float i = dot(c, vec3(0.596, -0.274, -0.322));
	float q = dot(c, vec3(0.211, -0.523, 0.312));
	float ca = cos(a), sa = sin(a);
	float i2 = i * ca - q * sa, q2 = i * sa + q * ca;
	return vec3(y + 0.956 * i2 + 0.621 * q2, y - 0.272 * i2 - 0.647 * q2, y - 1.106 * i2 + 1.703 * q2);
}

vec3 pxFire(float x)
{
	x = clamp(x, 0.0, 1.0);
	vec3 a = vec3(0.0), b = vec3(0.6, 0.02, 0.0), c = vec3(1.0, 0.35, 0.02), d = vec3(1.0, 0.8, 0.25), e = vec3(1.0, 1.0, 0.9);
	if (x < 0.25) return mix(a, b, x * 4.0);
	if (x < 0.5) return mix(b, c, (x - 0.25) * 4.0);
	if (x < 0.75) return mix(c, d, (x - 0.5) * 4.0);
	return mix(d, e, (x - 0.75) * 4.0);
}

// ---- effectors

float pxSdBox(vec3 q, vec3 h)
{
	vec3 d = abs(q) - h;
	return length(max(d, 0.0)) + min(max(d.x, max(d.y, d.z)), 0.0);
}

float pxSdShape(int ty, vec3 q, vec3 s)
{
	if (ty == 1) return length(q) - s.x;
	if (ty == 2) return pxSdBox(q, s);
	if (ty == 3) return q.y;
	if (ty == 4) { q.y -= clamp(q.y, -s.y, s.y); return length(q) - s.x; }
	if (ty == 5) { vec2 d = vec2(length(q.xz) - s.x, q.y); return length(d) - s.y; }
	return length(q);
}

// Legacy uniform path (uE[48], max 8; PX v1 and MX's Effsource 'objects'). Kept working until PX v2 / MX move to
// the packed list below; consumers that only use the packed list define PX_PACKED_ONLY (no uG / uE needed).
#ifndef PX_PACKED_ONLY
int pxECount() { return clamp(pxI(uG[1].z), 0, 8); }

// Shared effectors in PX (wave 2, RUBENFRO K37; docs/builds/px.md "Wave 2"). With PX_SHARED_EFF (PX's update / colour
// stages: px_logic.decl) an effector index i >= PX_SH0 is row i - PX_SH0 of the shared packed list /project1/effectors
// (PXE_ROWS = uEffRows). A module's shared selection (tags / all / up to 4 names) = its header rows 1.yzw + 2
// (px_logic.pack_module_rows), set into pxShSel / pxShIds by its block header. Weights: pxW's second loop (pxEWsh);
// module-facing accessors pxX* (centre, axis, sd, gradient, velocity, sample) dispatch own / shared. PX's own-effector
// functions below are the v2 text untouched: branching inside them changed the driver's codegen (live W2-0, b5:
// P moved by up to 5e-6 with no shared effector in use), so the dispatch sits only at the module-facing calls.
#ifdef PX_SHARED_EFF
const int PX_SH0 = 8;
vec4 pxShSel = vec4(0.0);
vec4 pxShIds = vec4(0.0);
int pxeCount();
vec4 pxeT(int i, int t);
bool pxeSel(int i, vec4 sel, vec4 ids);
int pxeLoopN(vec4 sel, int n);
int pxeLoopI(vec4 sel, vec4 ids, int k, int n);
int pxeNth(vec4 sel, vec4 ids, int k);
float pxeSd(int i, vec3 p, float R);
vec3 pxeGrad(int i, vec3 p);
vec3 pxeVelAt(int i, vec3 p);
vec3 pxeLocal(int i, vec3 p);
float pxePtsNearest(int i, vec3 p, out int bj, out vec3 bv);
vec3 pxePtsPoint(int i, int j);
#endif

// MX_prox_material (a GLSL MAT, PX_NO_TEX_INPUTS) shares this library but has no PX state texture, point-set / trail
// buffers or layer globals: their accessors compile to empty ones there (point-set kinds 6/7 then find no points;
// MX has its own point-set path, pxPtsNearest below). PX_EP = px_logic.E_PER when the includer did not define it.
#ifdef PX_NO_TEX_INPUTS
#ifndef PX_EP
#define PX_EP 11
#endif
#define PX_NO_PX_BUFFERS
#ifndef CAMPOS
#define CAMPOS uG[8].xyz
#endif
#ifndef CAMFWD
#define CAMFWD uG[20].xyz
#endif
#endif
#ifdef PX_NO_PX_BUFFERS
int pxPtsTot() { return 0; }
vec3 pxPtsP(int j) { return vec3(0.0); }
vec3 pxPtsVel(int j) { return vec3(0.0); }
int pxTrailTot() { return 0; }
vec4 pxTrailT(int j) { return vec4(0.0); }
#define PX_NSCENE_ 0.0
#define PX_NACTOR_ 0.0
#define PX_ACTORVEL_ vec3(0.0)
#else
int pxPtsTot() { return textureSize(uPts); }
vec3 pxPtsP(int j) { return texelFetch(uPts, j).xyz; }
vec3 pxPtsVel(int j) { return texelFetch(uPtsV, j).xyz; }
int pxTrailTot() { return textureSize(uTrail); }
vec4 pxTrailT(int j) { return texelFetch(uTrail, j); }
#define PX_NSCENE_ NSCENE
#define PX_NACTOR_ NACTOR
#define PX_ACTORVEL_ ACTORVEL
#endif

// Texel k of point id in this stage's state texture (PX_STATE_TEX / PX_STATE_SIZE: defined by each stage template
// before //@DECL; the source stage has no state: zeros). Out of range -> 0.
vec4 pxStateT(int id, int k)
{
#ifdef PX_NO_PX_BUFFERS
	return vec4(0.0);
#else
	int side = max(pxI(SIDE), 1);
	if (id < 0) return vec4(0.0);
	ivec2 t = ivec2((id % side) * PX_ST + k, id / side);
	ivec2 sz = PX_STATE_SIZE;
	if (t.x >= sz.x || t.y >= sz.y) return vec4(0.0);
	return PX_STATE_TEX(t);
#endif
}

vec3 pxELocal(int i, vec3 p)
{
	int b = i * PX_EP;
	vec4 h = vec4(p, 1.0);
	return vec3(dot(uE[b], h), dot(uE[b + 1], h), dot(uE[b + 2], h));
}

vec3 pxEWorld(int i, vec3 q)
{
	int b = i * PX_EP;
	vec4 h = vec4(q, 1.0);
	return vec3(dot(uE[b + 8], h), dot(uE[b + 9], h), dot(uE[b + 10], h));
}

int pxEType(int i) { return pxI(uE[i * PX_EP + 3].x); }

vec3 pxECentre(int i) { return uE[i * PX_EP + 4].xyz; }

vec3 pxEAxis(int i) { return pxSafeN(uE[i * PX_EP + 5].xyz, vec3(0.0, 1.0, 0.0)); }

float pxESpeed(int i) { return uE[i * PX_EP + 5].w; }

vec3 pxEVelocity(int i) { return uE[i * PX_EP + 6].xyz; }

// Motion direction: unit velocity, else the up axis (a still plane's front = its normal). Mirrors ref_move_dir.
vec3 pxEMoveDir(int i)
{
	vec3 v = pxEVelocity(i);
	return length(v) > 1e-4 ? normalize(v) : pxEAxis(i);
}

// Point sets (types 6 / 7, A1): nearest distance (minus the point radius) or a soft density distance
// (-r ln sum exp(-d^2 / 2r^2)); nearp / nvel = the nearest point and its velocity (per-point frame difference for
// CHOP / SOP sets; the actor layer's own motion for actor points). Brute force over <= 4096 points (row 7 x);
// the actor layer is sampled with a stride (Actorsamples). Mirrors ref_pts_nearest.
float pxPtsNear(int i, vec3 p, out vec3 nearp, out vec3 nvel)
{
	int b = i * PX_EP;
	int ty = pxI(uE[b + 3].x);
	float rr = max(uE[b + 3].y, 1e-4);
	int st = pxI(uE[b + 6].w);
	int cnt = pxI(uE[b + 7].x);
	int md = pxI(uE[b + 7].y);
	nearp = pxECentre(i);
	nvel = pxEVelocity(i);
	if (cnt <= 0) return 1e10;
	int tot = ty == 7 ? 0 : pxPtsTot();
	int na = max(pxI(PX_NACTOR_), 1);
	int stride = ty == 7 ? max(na / max(cnt, 1), 1) : 1;
	float best = 1e30;
	float dens = 0.0;
	for (int k = 0; k < 4096; k++) {
		if (k >= cnt) break;
		vec3 q;
		vec3 vq;
		if (ty == 7) {
			int aid = pxI(PX_NSCENE_) + k * stride;
			if (k * stride >= na) break;
			q = pxStateT(aid, 0).xyz;
			vq = PX_ACTORVEL_;
		} else {
			int j = st + k;
			if (j >= tot) break;
			q = pxPtsP(j);
			vq = pxPtsVel(j);
		}
		vec3 dv = p - q;
		float d2 = dot(dv, dv);
		if (md == 1) dens += exp(-d2 / (2.0 * rr * rr));
		if (d2 < best) { best = d2; nearp = q; nvel = vq; }
	}
	if (best > 1e29) return 1e10;
	return md == 1 ? -rr * log(max(dens, 1e-8)) : sqrt(best) - rr;
}

float pxESd(int i, vec3 p)
{
	vec4 t = uE[i * PX_EP + 3];
	int ty = pxI(t.x);
	if (ty >= 6) { vec3 np_, nv; return pxPtsNear(i, p, np_, nv); }
	return pxSdShape(ty, pxELocal(i, p), t.yzw) * uE[i * PX_EP + 4].w;
}

// Outward unit direction at p (gradient of the effector's distance; centre direction as the fallback; point sets:
// away from the nearest point).
vec3 pxEGrad(int i, vec3 p)
{
	if (pxEType(i) >= 6) {
		vec3 np_, nv;
		pxPtsNear(i, p, np_, nv);
		return pxSafeN(p - np_, pxSafeN(p - pxECentre(i), vec3(0.0, 1.0, 0.0)));
	}
	const float e = 1e-3;
	vec3 g = vec3(pxESd(i, p + vec3(e, 0.0, 0.0)) - pxESd(i, p - vec3(e, 0.0, 0.0)),
	              pxESd(i, p + vec3(0.0, e, 0.0)) - pxESd(i, p - vec3(0.0, e, 0.0)),
	              pxESd(i, p + vec3(0.0, 0.0, e)) - pxESd(i, p - vec3(0.0, 0.0, e)));
	return pxSafeN(g, pxSafeN(p - pxECentre(i), vec3(0.0, 1.0, 0.0)));
}

// Effector velocity at p (units/s): the object's velocity, or the nearest point's for point sets (stirring).
vec3 pxEVel(int i, vec3 p)
{
	if (pxEType(i) >= 6) { vec3 np_, nv; pxPtsNear(i, p, np_, nv); return nv; }
	return pxEVelocity(i);
}

// Random point of effector i (ember spawn, prox_burn source volume / surface): local unit shape -> world matrix.
// nrm = outward world normal (surface) or the up axis.
vec3 pxESample(int i, uint id, uint fr, bool surface, out vec3 nrm)
{
	int b = i * PX_EP;
	int ty = pxI(uE[b + 3].x);
	vec3 s = uE[b + 3].yzw;
	vec3 r3 = pxRnd3(id, fr * 29u + 301u);
	vec3 dir = pxSafeN(r3 * 2.0 - 1.0, vec3(0.0, 1.0, 0.0));
	nrm = pxEAxis(i);
	vec3 q = vec3(0.0);
	if (ty == 6 || ty == 7) {
		int cnt = pxI(uE[b + 7].x);
		int k = int(pxRnd(id, fr * 31u + 307u) * float(max(cnt, 1)));
		if (ty == 7) {
			int na = max(pxI(PX_NACTOR_), 1);
			return pxStateT(pxI(PX_NSCENE_) + min(k * max(na / max(cnt, 1), 1), na - 1), 0).xyz + dir * s.x;
		}
		int j = min(pxI(uE[b + 6].w) + k, max(pxPtsTot() - 1, 0));
		return pxPtsP(j) + dir * s.x;
	}
	if (ty == 1 || ty == 4 || ty == 5) {                 // sphere (capsule / torus approximated by their radius x)
		float rad = max(s.x, 1e-4);
		q = dir * rad * (surface ? 1.0 : pow(pxRnd(id, fr * 37u + 311u), 1.0 / 3.0));
		nrm = dir;
	} else if (ty == 2) {                                // box
		q = (r3 * 2.0 - 1.0) * s;
		if (surface) {
			int f = int(pxRnd(id, fr * 41u + 313u) * 6.0) % 6;
			int ax = f / 2;
			float sg = (f % 2 == 0) ? 1.0 : -1.0;
			q[ax] = sg * s[ax];
			nrm = vec3(0.0);
			nrm[ax] = sg;
		}
	} else if (ty == 3) {                                // plane: unit grid in local xz
		q = vec3(r3.x - 0.5, 0.0, r3.z - 0.5);
		nrm = vec3(0.0, 1.0, 0.0);
	}
	vec3 wn = pxEWorld(i, nrm) - pxEWorld(i, vec3(0.0));
	nrm = pxSafeN(wn, pxEAxis(i));
	return pxEWorld(i, q);
}

// Front shapes 6 behind / 7 ahead (A3): a front through the effector centre, perpendicular to its motion
// (pxEMoveDir). behind: everything the front passed is weighted ((1 + s/R)^k over R behind it), ahead of the front
// the weight drops to 0 within edge x R (a sharp leading edge); ahead mirrors it. Mirrors ref_front.
float pxFront(int i, vec3 p, float R, float k, int shape, float edge, float noise)
{
	float s = dot(p - pxECentre(i), pxEMoveDir(i)) + noise;
	if (shape == 7) s = -s;
	R = max(R, 1e-5);
	if (s > 0.0) return 1.0 - smoothstep(0.0, max(edge * R, 1e-5), s);
	return pow(clamp(1.0 + s / R, 0.0, 1.0), max(k, 1e-3));
}

// Wake shape 8 (A3): tube of radius R around centre -> trail ring buffer (uTrail rows: xyz, age s; row 7 zw =
// start, count), weight fading with age^k; no trail: a tube of length 4R behind the motion. Mirrors ref_wake.
float pxWake(int i, vec3 p, float R, float k, float noise)
{
	int b = i * PX_EP;
	int ts = pxI(uE[b + 7].z);
	int tc = pxI(uE[b + 7].w);
	int tot = pxTrailTot();
	R = max(R, 1e-5);
	float rs = pxEType(i) == 1 ? uE[b + 3].y * uE[b + 4].w : 0.0;
	vec3 a = pxECentre(i);
	float aa = 0.0;
	float amax = 1e-6;
	for (int j = 0; j < 64; j++) {
		if (j >= tc || ts + j >= tot) break;
		amax = max(amax, pxTrailT(ts + j).w);
	}
	float w = 0.0;
	if (tc <= 0) {
		vec3 bpt = a - pxEMoveDir(i) * (4.0 * R);
		vec3 ab = bpt - a;
		float u = clamp(dot(p - a, ab) / max(dot(ab, ab), 1e-12), 0.0, 1.0);
		float d = length(p - (a + ab * u)) + noise;
		return (1.0 - smoothstep(0.0, R, d - rs)) * pow(clamp(1.0 - u, 0.0, 1.0), max(k, 1e-3));
	}
	for (int j = 0; j < 64; j++) {
		if (j >= tc || ts + j >= tot) break;
		vec4 t = pxTrailT(ts + j);
		vec3 ab = t.xyz - a;
		float u = clamp(dot(p - a, ab) / max(dot(ab, ab), 1e-12), 0.0, 1.0);
		float d = length(p - (a + ab * u)) + noise;
		float age = mix(aa, t.w, u) / amax;
		w = max(w, (1.0 - smoothstep(0.0, R, d - rs)) * pow(clamp(1.0 - age, 0.0, 1.0), max(k, 1e-3)));
		a = t.xyz;
		aa = t.w;
	}
	return w;
}
#endif

// Falloff of a signed distance d: 1 at/inside the surface, 0 beyond R (shapes 0..5 of px_logic.FALLOFFS).
float pxFall(float d, float R, float k, int shape)
{
	R = max(R, 1e-5);
	k = max(k, 1e-3);
	if (shape == 1) return pow(clamp(1.0 - max(d, 0.0) / R, 0.0, 1.0), k);
	if (shape == 2) { float x = max(d, 0.0) / R; return exp(-4.0 * k * x * x); }
	if (shape == 3) return d < R ? 1.0 : 0.0;
	if (shape == 4) return pow(1.0 - smoothstep(0.0, R, abs(d)), k);
	if (shape == 5) return pow(smoothstep(0.0, R, -d), k);
	return pow(1.0 - smoothstep(0.0, R, max(d, 0.0)), k);
}

float pxComb(float w, float wi, int comb)
{
	if (comb == 1) return w + wi;
	if (comb == 2) return w * wi;
	if (comb == 3) return w + wi - w * wi;
	return max(w, wi);
}

#ifndef PX_PACKED_ONLY
#ifdef PX_SHARED_EFF
// Shared row s: motion direction (unit velocity, else its up axis), and its weight with the MODULE's falloff (radius,
// exponent, shape, ragged edge) x the row's gain. Fronts (6 behind / 7 ahead) as pxFront; wake (8): shared rows carry
// no trail, so the tube of length 4R behind the motion (pxWake's no-trail case). Point sets: nearest / density.
vec3 pxSMoveDir(int s)
{
	vec3 v = pxeT(s, 6).xyz;
	return length(v) > 1e-4 ? normalize(v) : pxSafeN(pxeT(s, 5).xyz, vec3(0.0, 1.0, 0.0));
}

float pxEWsh(int s, vec3 p, float R, float k, int shape, float nedge, float nfreq, float edge)
{
	float n = nedge != 0.0 ? (pxNoise(p * nfreq, 7u) - 0.5) * nedge * R : 0.0;
	R = max(R, 1e-5);
	vec3 c = pxeT(s, 4).xyz;
	if (shape == 8) {
		vec3 ab = -pxSMoveDir(s) * (4.0 * R);
		float u = clamp(dot(p - c, ab) / max(dot(ab, ab), 1e-12), 0.0, 1.0);
		float d = length(p - (c + ab * u)) + n;
		return (1.0 - smoothstep(0.0, R, d)) * pow(clamp(1.0 - u, 0.0, 1.0), max(k, 1e-3));
	}
	if (shape >= 6) {
		float sd = dot(p - c, pxSMoveDir(s)) + n;
		if (shape == 7) sd = -sd;
		if (sd > 0.0) return 1.0 - smoothstep(0.0, max(edge * R, 1e-5), sd);
		return pow(clamp(1.0 + sd / R, 0.0, 1.0), max(k, 1e-3));
	}
	return pxFall(pxeSd(s, p, pxeT(s, 7).y) + n, R, k, shape);
}
#endif

// Weight of ONE effector (shapes: px_logic.FALLOFFS; 6..8 need the effector, not only a distance).
float pxEW(int i, vec3 p, float R, float k, int shape, float nedge, float nfreq, float edge)
{
	float n = nedge != 0.0 ? (pxNoise(p * nfreq, 7u) - 0.5) * nedge * R : 0.0;
	if (shape == 8) return pxWake(i, p, R, k, n);
	if (shape >= 6) return pxFront(i, p, R, k, shape, edge, n);
	return pxFall(pxESd(i, p) + n, R, k, shape);
}

// Proximity weight of p to the effectors in bit mask em (combine: 0 max, 1 sum, 2 product, 3 screen).
// best = index of the strongest effector (-1 when none is linked; then w = 0).
float pxW(vec3 p, int em, float R, float k, int shape, int comb, float nedge, float nfreq, float edge, out int best)
{
	float w = (comb == 2) ? 1.0 : 0.0;
	float bw = -1.0;
	best = -1;
	int n = pxECount();
	for (int i = 0; i < 8; i++) {
		if (i >= n) break;
		if (((em >> i) & 1) == 0) continue;
		float wi = pxEW(i, p, R, k, shape, nedge, nfreq, edge);
		if (comb == 1) w += wi;
		else if (comb == 2) w *= wi;
		else if (comb == 3) w = w + wi - w * wi;
		else w = max(w, wi);
		if (wi > bw) { bw = wi; best = i; }
	}
#ifdef PX_SHARED_EFF
	if (pxShSel.z > 0.5) {                              // the module's shared selection (/project1/effectors)
		int sn = pxeCount();
		int sm = pxeLoopN(pxShSel, sn);
		for (int q = 0; q < 65536; q++) {
			if (q >= sm) break;
			int si = pxeLoopI(pxShSel, pxShIds, q, sn);
			if (si < 0 || !pxeSel(si, pxShSel, pxShIds)) continue;
			float wi = pxEWsh(si, p, R, k, shape, nedge, nfreq, edge) * pxeT(si, 7).w;
			w = pxComb(w, wi, comb);
			if (wi > bw) { bw = wi; best = PX_SH0 + si; }
		}
	}
#endif
	return best < 0 ? 0.0 : w;
}

// v1 signature (MX_prox_material calls it): edge only matters for the front shapes 6 / 7 (px_logic default 0.02).
float pxW(vec3 p, int em, float R, float k, int shape, int comb, float nedge, float nfreq, out int best)
{
	return pxW(p, em, R, k, shape, comb, nedge, nfreq, 0.02, best);
}

float pxFlip(float w, float f) { return f > 0.5 ? 1.0 - w : w; }

// First linked effector (or -1).
int pxFirst(int em)
{
	int n = pxECount();
	for (int i = 0; i < 8; i++) {
		if (i >= n) break;
		if (((em >> i) & 1) != 0) return i;
	}
#ifdef PX_SHARED_EFF
	if (pxShSel.z > 0.5) { int si = pxeNth(pxShSel, pxShIds, 0); if (si >= 0) return PX_SH0 + si; }
#endif
	return -1;
}

// Module-facing accessors (own index 0..7 or shared PX_SH0 + row): what modules call with `bi` / pxFirst(EM).
vec3 pxXCentre(int i)
{
#ifdef PX_SHARED_EFF
	if (i >= PX_SH0) return pxeT(i - PX_SH0, 4).xyz;
#endif
	return pxECentre(i);
}

vec3 pxXAxis(int i)
{
#ifdef PX_SHARED_EFF
	if (i >= PX_SH0) return pxSafeN(pxeT(i - PX_SH0, 5).xyz, vec3(0.0, 1.0, 0.0));
#endif
	return pxEAxis(i);
}

float pxXSd(int i, vec3 p)
{
#ifdef PX_SHARED_EFF
	if (i >= PX_SH0) return pxeSd(i - PX_SH0, p, pxeT(i - PX_SH0, 7).y);
#endif
	return pxESd(i, p);
}

vec3 pxXGrad(int i, vec3 p)
{
#ifdef PX_SHARED_EFF
	if (i >= PX_SH0) return pxeGrad(i - PX_SH0, p);
#endif
	return pxEGrad(i, p);
}

vec3 pxXVel(int i, vec3 p)
{
#ifdef PX_SHARED_EFF
	if (i >= PX_SH0) return pxeVelAt(i - PX_SH0, p);
#endif
	return pxEVel(i, p);
}

// Ember spawn point (prox_burn source volume / surface) on a shared row: a random point of its set, or of its unit
// shape mapped by the inverse of its inverse matrix (object kinds; nrm = the up axis).
vec3 pxXSample(int i, uint id, uint fr, bool surface, out vec3 nrm)
{
#ifdef PX_SHARED_EFF
	if (i >= PX_SH0) {
		int s = i - PX_SH0;
		nrm = pxSafeN(pxeT(s, 5).xyz, vec3(0.0, 1.0, 0.0));
		vec3 r3 = pxRnd3(id, fr * 29u + 301u);
		vec3 dir = pxSafeN(r3 * 2.0 - 1.0, vec3(0.0, 1.0, 0.0));
		vec4 t3 = pxeT(s, 3);
		if (pxI(t3.x) == 6) {
			int cnt = pxI(pxeT(s, 8).w);
			if (cnt <= 0) return pxeT(s, 4).xyz;
			int k = min(int(pxRnd(id, fr * 31u + 307u) * float(cnt)), cnt - 1);
			return pxePtsPoint(s, k) + dir * pxeT(s, 9).x;
		}
		vec3 q = (r3 * 2.0 - 1.0) * max(t3.yzw, vec3(0.05));
		if (surface) { q = dir * max(t3.y, 0.05); nrm = dir; }
		vec4 r0 = pxeT(s, 0), r1 = pxeT(s, 1), r2 = pxeT(s, 2);
		mat3 A = inverse(transpose(mat3(r0.xyz, r1.xyz, r2.xyz)));
		vec3 wp = A * (q - vec3(r0.w, r1.w, r2.w));
		if (surface) nrm = pxSafeN(A * nrm, nrm);
		return wp;
	}
#endif
	return pxESample(i, id, fr, surface, nrm);
}

// Centre: the first linked effector, else the source's bounding-box centre (uG[7].xyz).
vec3 pxCentreOf(int em) { int i = pxFirst(em); return i >= 0 ? pxXCentre(i) : uG[7].xyz; }

// Axis menu (px_logic.AXES): 0 x, 1 y, 2 z, 3 first effector's up axis (y when none), 4 view (camera forward).
vec3 pxAxisOf(int em, int sel)
{
	if (sel == 0) return vec3(1.0, 0.0, 0.0);
	if (sel == 2) return vec3(0.0, 0.0, 1.0);
	if (sel == 3) { int i = pxFirst(em); return i >= 0 ? pxXAxis(i) : vec3(0.0, 1.0, 0.0); }
	if (sel == 4) return pxSafeN(CAMFWD, vec3(0.0, 0.0, -1.0));
	return vec3(0.0, 1.0, 0.0);
}

// Stretch axis menu (px_logic.STRETCH_AXES): 0 velocity (vec3(0): the sprite keeps its screen-velocity streak), 1 view,
// 2..4 world x y z, 5 effector up axis, 6 radial from the effector (or the bounds centre), 7 radial from the camera.
vec3 pxStretchAxis(int sel, int bi, vec3 p)
{
	if (sel == 1) return pxSafeN(CAMFWD, vec3(0.0, 0.0, -1.0));
	if (sel == 2) return vec3(1.0, 0.0, 0.0);
	if (sel == 3) return vec3(0.0, 1.0, 0.0);
	if (sel == 4) return vec3(0.0, 0.0, 1.0);
	if (sel == 5) return bi >= 0 ? pxXAxis(bi) : vec3(0.0, 1.0, 0.0);
	if (sel == 6) return pxSafeN(p - (bi >= 0 ? pxXCentre(bi) : uG[7].xyz), vec3(0.0, 1.0, 0.0));
	if (sel == 7) return pxSafeN(p - CAMPOS, vec3(0.0, 0.0, -1.0));
	return vec3(0.0);
}

// Direction menu for proximity forces: 0 outward (sdf gradient), 1 from centre, 2 effector axis, 3 tangent (axis x r),
// 4 effector velocity (not normalised: a faster hand stirs harder; per point for point sets).
vec3 pxDirOf(int sel, int i, vec3 q)
{
	if (i < 0) return vec3(0.0);
#ifdef PX_SHARED_EFF
	if (i >= PX_SH0) {
		if (sel == 1) return pxSafeN(q - pxXCentre(i), vec3(0.0, 1.0, 0.0));
		if (sel == 2) return pxXAxis(i);
		if (sel == 3) return pxSafeN(cross(pxXAxis(i), q - pxXCentre(i)), vec3(1.0, 0.0, 0.0));
		if (sel == 4) return pxXVel(i, q);
		return pxXGrad(i, q);
	}
#endif
	if (sel == 1) return pxSafeN(q - pxECentre(i), vec3(0.0, 1.0, 0.0));
	if (sel == 2) return pxEAxis(i);
	if (sel == 3) return pxSafeN(cross(pxEAxis(i), q - pxECentre(i)), vec3(1.0, 0.0, 0.0));
	if (sel == 4) return pxEVel(i, q);
	return pxEGrad(i, q);
}
#endif

// Mask input menu (px_logic.MASKSEL): 0 none, 1..3 mask registers, 4 visible, 5 dissolved, 6 heat, 7 scene layer,
// 8 actor layer, 9 pool. lay = the point's layer (0 scene, 1 actor, 2 pool; LAYER in the stage templates).
float pxMaskSel(int sel, vec3 mk, float dis, float heat, int lay)
{
	if (sel == 1) return mk.x;
	if (sel == 2) return mk.y;
	if (sel == 3) return mk.z;
	if (sel == 4) return 1.0 - clamp(dis, 0.0, 1.0);
	if (sel == 5) return clamp(dis, 0.0, 1.0);
	if (sel == 6) return clamp(heat, 0.0, 1.0);
	if (sel == 7) return lay == 0 ? 1.0 : 0.0;
	if (sel == 8) return lay == 1 ? 1.0 : 0.0;
	if (sel == 9) return lay == 2 ? 1.0 : 0.0;
	return 1.0;
}

// Write w into mask register slot (1..3; 0 = none) with op (px_logic.MASKOPS: set max min multiply add subtract).
void pxPublish(inout vec3 mk, int slot, int op, float w)
{
	if (slot < 1 || slot > 3) return;
	float m = mk[slot - 1];
	if (op == 1) m = max(m, w);
	else if (op == 2) m = min(m, w);
	else if (op == 3) m *= w;
	else if (op == 4) m += w;
	else if (op == 5) m -= w;
	else m = w;
	mk[slot - 1] = clamp(m, 0.0, 1.0);
}

#ifndef PX_PACKED_ONLY
// 16-band spectrum (uG[12..15]) sampled at x in 0..1 (linear between bands).
float pxSpec(float x)
{
	float f = clamp(x, 0.0, 1.0) * 15.0;
	int i0 = int(floor(f));
	int i1 = min(i0 + 1, 15);
	float a = uG[12 + i0 / 4][i0 % 4];
	float b = uG[12 + i1 / 4][i1 % 4];
	return mix(a, b, f - float(i0));
}
#endif

// Mask TOP lookup (input 2 of the stage). proj: 0 screen (output camera view-proj in uG[16..19]), 1 planar xy,
// 2 planar xz (centre c, size sz). chan: 0 luminance, 1 alpha, 2 red. Returns 0 outside the image / behind.
// GLSL MATs have no sTD2DInputs: MX_prox_material defines PX_NO_TEX_INPUTS before including this file.
#if !defined(PX_NO_TEX_INPUTS) && !defined(PX_PACKED_ONLY)
float pxMaskTex(vec3 p, int proj, vec3 c, float sz, int chan, int mirror)
{
	vec2 uv;
	if (proj == 0) {
		vec4 h = vec4(p, 1.0);
		vec4 clip = vec4(dot(uG[16], h), dot(uG[17], h), dot(uG[18], h), dot(uG[19], h));
		if (clip.w <= 1e-5) return 0.0;
		uv = clip.xy / clip.w * 0.5 + 0.5;
	} else if (proj == 1) {
		uv = (p.xy - c.xy) / max(sz, 1e-5) + 0.5;
	} else {
		uv = (p.xz - c.xz) / max(sz, 1e-5) + 0.5;
	}
	if (mirror != 0) uv.x = 1.0 - uv.x;
	if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) return 0.0;
	vec4 t = texture(sTD2DInputs[2], uv);
	if (chan == 1) return t.a;
	if (chan == 2) return t.r;
	return pxLum(t.rgb);
}
#endif

// ---- point-set effectors (px_requirements item 8; used by MX_prox_material, numpy twins in prox_mat_logic.py).
// Points texture (rgba32f) W x 2H: texel (i % W, i / W) = world xyz + valid (a > 0.5); texel (i % W, H + i / W) =
// velocity xyz (units/s) + speed. Loops are bounded (T-35): at most PX_PTS_MAX points brute force.
const int PX_PTS_MAX = 4096;

vec4 pxPtsTexel(sampler2D s, int i, int w, int h, int row)
{
	return texelFetch(s, ivec2(i % w, (i / w) + row * h), 0);
}

// Nearest point: centre distance (1e9 when none), best = its index (-1 when none).
float pxPtsNearest(sampler2D s, vec3 p, int n, int w, int h, out int best)
{
	float bd = 1e18;
	best = -1;
	for (int i = 0; i < PX_PTS_MAX; i++) {
		if (i >= n) break;
		vec4 t = pxPtsTexel(s, i, w, h, 0);
		if (t.a < 0.5) continue;
		vec3 d = p - t.xyz;
		float q = dot(d, d);
		if (q < bd) { bd = q; best = i; }
	}
	return best < 0 ? 1e9 : sqrt(bd);
}

// Soft density: sum over points of exp(-4 (d / r)^2) (1 at a point, ~0.02 at d = r).
float pxPtsDensity(sampler2D s, vec3 p, int n, int w, int h, float r)
{
	float k = 4.0 / max(r * r, 1e-10), D = 0.0;
	for (int i = 0; i < PX_PTS_MAX; i++) {
		if (i >= n) break;
		vec4 t = pxPtsTexel(s, i, w, h, 0);
		if (t.a < 0.5) continue;
		vec3 d = p - t.xyz;
		D += exp(-k * dot(d, d));
	}
	return D;
}

// Distance / density field atlas of a point set: R^3 cells over the box lo..lo+size, slice z in tile
// (z % T, z / T) of R x R texels; rows 0..R*T-1 = (nearest distance, density, 0, 1), rows R*T.. = velocity of the
// nearest point (xyz, speed). Built by prox_mat_field.glsl.
vec4 pxFieldFetch(sampler2D s, ivec3 c, int R, int T, int row)
{
	c = clamp(c, ivec3(0), ivec3(R - 1));
	return texelFetch(s, ivec2((c.z % T) * R + c.x, (c.z / T) * R + c.y + row * R * T), 0);
}

// Trilinear sample at world p. Outside the box the clamped value is used and, for row 0, the distance to the box
// is added to the nearest distance (a lower bound of the true distance, exact along the box normal).
vec4 pxFieldSample(sampler2D s, vec3 p, vec3 lo, vec3 size, int R, int T, int row)
{
	vec3 sz = max(size, vec3(1e-6));
	vec3 q = clamp(p, lo, lo + sz);
	vec3 g = (q - lo) / sz * float(R) - 0.5;
	vec3 i = floor(g);
	vec3 f = g - i;
	ivec3 c = ivec3(i);
	vec4 a = mix(mix(pxFieldFetch(s, c, R, T, row), pxFieldFetch(s, c + ivec3(1, 0, 0), R, T, row), f.x),
	             mix(pxFieldFetch(s, c + ivec3(0, 1, 0), R, T, row), pxFieldFetch(s, c + ivec3(1, 1, 0), R, T, row), f.x), f.y);
	vec4 b = mix(mix(pxFieldFetch(s, c + ivec3(0, 0, 1), R, T, row), pxFieldFetch(s, c + ivec3(1, 0, 1), R, T, row), f.x),
	             mix(pxFieldFetch(s, c + ivec3(0, 1, 1), R, T, row), pxFieldFetch(s, c + ivec3(1, 1, 1), R, T, row), f.x), f.y);
	vec4 v = mix(a, b, f.z);
	if (row == 0) v.x += length(p - q);
	return v;
}

// Point-set distance for the falloffs: nearest mode = centre distance - point radius; density mode = an equivalent
// distance R (1 - min(D / full, 1)) so every falloff shape works (D >= full -> 0 = inside).
float pxPtsEqDist(int mode, float dist, float dens, float prad, float R, float full)
{
	if (mode == 1) return R * (1.0 - clamp(dens / max(full, 1e-6), 0.0, 1.0));
	return dist - prad;
}

// Strange attractor velocity fields (type: 0 lorenz, 1 aizawa, 2 thomas, 3 halvorsen, 4 dadras, 5 chen).
// k = (a, b, c, d); custom = 0 uses the canonical constants.
vec3 pxAttractor(int ty, vec3 q, vec4 k, bool custom)
{
	float x = q.x, y = q.y, z = q.z;
	if (ty == 1) {
		vec4 c = custom ? k : vec4(0.95, 0.7, 0.6, 3.5);
		return vec3((z - c.y) * x - c.w * y, c.w * x + (z - c.y) * y,
		            c.z + c.x * z - z * z * z / 3.0 - (x * x + y * y) * (1.0 + 0.25 * z) + 0.1 * z * x * x * x);
	}
	if (ty == 2) {
		float b = custom ? k.x : 0.208186;
		return vec3(sin(y) - b * x, sin(z) - b * y, sin(x) - b * z);
	}
	if (ty == 3) {
		float a = custom ? k.x : 1.89;
		return vec3(-a * x - 4.0 * y - 4.0 * z - y * y, -a * y - 4.0 * z - 4.0 * x - z * z, -a * z - 4.0 * x - 4.0 * y - x * x);
	}
	if (ty == 4) {
		vec4 c = custom ? k : vec4(3.0, 2.7, 1.7, 2.0);
		return vec3(y - c.x * x + c.y * y * z, c.z * y - x * z + z, c.w * x * y - 9.0 * z);
	}
	if (ty == 5) {
		vec4 c = custom ? k : vec4(5.0, -10.0, -0.38, 0.0);
		return vec3(c.x * x - y * z, c.y * y + x * z, c.z * z + x * y / 3.0);
	}
	vec4 c = custom ? k : vec4(10.0, 28.0, 2.6666667, 0.0);
	return vec3(c.x * (y - x), x * (c.y - z) - y, x * y - c.z * z);
}

// ---- packed effector list (/project1/effectors; px_requirements items 11 + 12; layout + CPU twins:
// builders/effectors_logic.py, tests test/test_effectors.py, doc docs/builds/effectors.md).
// One vec4 texture buffer (Script CHOP eff_rows, one sample per texel): texel 0 = (count N, row width W, points
// start, version); row i = texels 1 + i*W .. : 0..2 inverse world rows, 3 (sdf type, local size), 4 (centre, scale),
// 5 (up axis, speed) [= the uE rows above], 6 (velocity, enabled), 7 (falloff shape, radius, exponent, gain),
// 8 (tag bits, kind, points start, point count), 9 (point radius, point mode, density full, id). Points: 2 texels
// each (xyz, valid) (velocity, speed). Sdf type 6 = point set. A consumer defines PXE_ROWS (its samplerBuffer)
// before this file. No cap: loops run to the header count (PXE_MAX / PXE_PTS_MAX only bound them, T-35).
// Selection: sel = (tag mask, all, on, gain), ids = 4 effector ids (row + 1); mixv = (combine, radius scale, ragged,
// ragged freq); fall = (override, radius, exponent, shape) replaces every row's falloff when fall.x > 0.5.
#ifdef PXE_ROWS
const int PXE_W = 10;
const int PXE_MAX = 65536;
const int PXE_PTS_MAX = 4096;
const int PXE_SD_PTS = 6;
const int PXE_SD_GRID = 7;      // kind `cloud`: a point TOP through the shared grid's distance field (lane E)
#ifdef PXE_GRID
float pxgFieldNearest(vec3 p, out vec3 seed);   // eff_grid_common.glsl (the adapter prefix appends it)
#endif

int pxeCount()
{
	int sz = textureSize(PXE_ROWS);
	if (sz < 1) return 0;
	return clamp(pxI(texelFetch(PXE_ROWS, 0).x), 0, min(PXE_MAX, (sz - 1) / PXE_W));
}

vec4 pxeT(int i, int t) { return texelFetch(PXE_ROWS, 1 + i * PXE_W + t); }

bool pxeSel(int i, vec4 sel, vec4 ids)
{
	if (pxeT(i, 6).w < 0.5) {
#ifdef PXE_GRID
		vec4 t3 = pxeT(i, 3);           // a cloud row carries its own on flag (texel 6.w = 0 hides it from older readers)
		if (pxI(t3.x) != PXE_SD_GRID || t3.y < 0.5) return false;
#else
		return false;
#endif
	}
	if (sel.y > 0.5) return true;
	if ((pxI(pxeT(i, 8).x) & pxI(sel.x)) != 0) return true;
	return any(equal(ids, vec4(float(i + 1))));
}

// Loop helpers: a names-only selection (no tag mask, not 'all') visits only its <= 4 ids, so its cost does not grow
// with the list (live: 109k splats x 105 rows = +3.4 ms render GPU for one named effector). Tags / 'all' walk the list.
bool pxeIdsOnly(vec4 sel) { return sel.y < 0.5 && pxI(sel.x) == 0; }
int pxeLoopN(vec4 sel, int n) { return pxeIdsOnly(sel) ? 4 : n; }
int pxeLoopI(vec4 sel, vec4 ids, int k, int n)
{
	if (!pxeIdsOnly(sel)) return k;
	int i = pxI(ids[k]) - 1;
	return (i >= 0 && i < n) ? i : -1;
}

bool pxeIsPts(int i) { return pxI(pxeT(i, 3).x) == PXE_SD_PTS; }
vec3 pxeCentre(int i) { return pxeT(i, 4).xyz; }
vec3 pxeAxis(int i) { return pxSafeN(pxeT(i, 5).xyz, vec3(0.0, 1.0, 0.0)); }
float pxeSpeed(int i) { return pxeT(i, 5).w; }
vec3 pxeVel(int i) { return pxeT(i, 6).xyz; }

vec3 pxeLocal(int i, vec3 p)
{
	vec4 h = vec4(p, 1.0);
	return vec3(dot(pxeT(i, 0), h), dot(pxeT(i, 1), h), dot(pxeT(i, 2), h));
}

float pxeSdObj(int i, vec3 p)
{
	vec4 t = pxeT(i, 3);
	return pxSdShape(pxI(t.x), pxeLocal(i, p), t.yzw) * pxeT(i, 4).w;
}

// Nearest point of set i: centre distance (1e9 when empty), bj = its point index, bv = its velocity.
float pxePtsNearest(int i, vec3 p, out int bj, out vec3 bv)
{
	vec4 h = pxeT(i, 8);
	int o = pxI(h.z), m = min(pxI(h.w), PXE_PTS_MAX);
	float bd = 1e18;
	bj = -1;
	bv = vec3(0.0);
	for (int j = 0; j < PXE_PTS_MAX; j++) {
		if (j >= m) break;
		vec4 q = texelFetch(PXE_ROWS, o + 2 * j);
		if (q.w < 0.5) continue;
		vec3 d = p - q.xyz;
		float e = dot(d, d);
		if (e < bd) { bd = e; bj = j; }
	}
	if (bj >= 0) bv = texelFetch(PXE_ROWS, o + 2 * bj + 1).xyz;
	return bj < 0 ? 1e9 : sqrt(bd);
}

float pxePtsDensity(int i, vec3 p, float r)
{
	vec4 h = pxeT(i, 8);
	int o = pxI(h.z), m = min(pxI(h.w), PXE_PTS_MAX);
	float k = 4.0 / max(r * r, 1e-10), D = 0.0;
	for (int j = 0; j < PXE_PTS_MAX; j++) {
		if (j >= m) break;
		vec4 q = texelFetch(PXE_ROWS, o + 2 * j);
		if (q.w < 0.5) continue;
		vec3 d = p - q.xyz;
		D += exp(-k * dot(d, d));
	}
	return D;
}

vec3 pxePtsPoint(int i, int j) { return texelFetch(PXE_ROWS, pxI(pxeT(i, 8).z) + 2 * j).xyz; }

// Signed distance of p to effector i (point sets: nearest point - point radius, or the density equivalent of
// pxPtsEqDist with the row's radius R).
float pxeSd(int i, vec3 p, float R)
{
#ifdef PXE_GRID
	if (pxI(pxeT(i, 3).x) == PXE_SD_GRID) { vec3 sd; return pxgFieldNearest(p, sd) - pxeT(i, 9).x; }
#endif
	if (!pxeIsPts(i)) return pxeSdObj(i, p);
	vec4 t9 = pxeT(i, 9);
	if (pxI(t9.y) == 1) return pxPtsEqDist(1, 0.0, pxePtsDensity(i, p, max(R, 1e-4)), t9.x, R, t9.z);
	int bj;
	vec3 bv;
	return pxePtsNearest(i, p, bj, bv) - t9.x;
}

// Outward unit direction at p (object: gradient of the SDF; point set: away from the nearest point).
vec3 pxeGrad(int i, vec3 p)
{
#ifdef PXE_GRID
	if (pxI(pxeT(i, 3).x) == PXE_SD_GRID) {
		vec3 sd;
		return pxgFieldNearest(p, sd) > 1e8 ? vec3(0.0, 1.0, 0.0) : pxSafeN(p - sd, vec3(0.0, 1.0, 0.0));
	}
#endif
	if (pxeIsPts(i)) {
		int bj;
		vec3 bv;
		pxePtsNearest(i, p, bj, bv);
		return bj < 0 ? vec3(0.0, 1.0, 0.0) : pxSafeN(p - pxePtsPoint(i, bj), vec3(0.0, 1.0, 0.0));
	}
	const float e = 1e-3;
	vec3 g = vec3(pxeSdObj(i, p + vec3(e, 0.0, 0.0)) - pxeSdObj(i, p - vec3(e, 0.0, 0.0)),
	              pxeSdObj(i, p + vec3(0.0, e, 0.0)) - pxeSdObj(i, p - vec3(0.0, e, 0.0)),
	              pxeSdObj(i, p + vec3(0.0, 0.0, e)) - pxeSdObj(i, p - vec3(0.0, 0.0, e)));
	return pxSafeN(g, pxSafeN(p - pxeCentre(i), vec3(0.0, 1.0, 0.0)));
}

// Velocity seen at p: the nearest point's for a point set, else the effector's.
vec3 pxeVelAt(int i, vec3 p)
{
	if (!pxeIsPts(i)) return pxeVel(i);
	int bj;
	vec3 bv;
	pxePtsNearest(i, p, bj, bv);
	return bv;
}

// Falloff of effector i at distance d (row falloff, or the consumer's when fall.x > 0.5) x row gain.
float pxeFallOf(int i, float d, vec4 mixv, vec4 fall)
{
	vec4 f = pxeT(i, 7);
	bool o = fall.x > 0.5;
	float R = (o ? fall.y : f.y) * mixv.y;
	return pxFall(d, R, o ? fall.z : f.z, o ? pxI(fall.w) : pxI(f.x)) * f.w;
}

float pxeRadius(int i, vec4 mixv, vec4 fall) { return (fall.x > 0.5 ? fall.y : pxeT(i, 7).y) * mixv.y; }

// Proximity weight of p to the selected effectors (combine mixv.x), x sel.w. best = strongest (-1: none -> 0).
float pxeW(vec3 p, vec4 sel, vec4 ids, vec4 mixv, vec4 fall, out int best)
{
	int comb = pxI(mixv.x);
	float w = (comb == 2) ? 1.0 : 0.0;
	float bw = -1.0;
	best = -1;
	if (sel.z < 0.5) return 0.0;
	int n = pxeCount();
	int m = pxeLoopN(sel, n);
	for (int q = 0; q < PXE_MAX; q++) {
		if (q >= m) break;
		int i = pxeLoopI(sel, ids, q, n);
		if (i < 0 || !pxeSel(i, sel, ids)) continue;
		float R = pxeRadius(i, mixv, fall);
		float d = pxeSd(i, p, R);
		if (mixv.z != 0.0) d += (pxNoise(p * mixv.w, 7u) - 0.5) * mixv.z * R;
		float wi = pxeFallOf(i, d, mixv, fall);
		w = pxComb(w, wi, comb);
		if (wi > bw) { bw = wi; best = i; }
	}
	return best < 0 ? 0.0 : w * sel.w;
}

// k-th selected effector (k = 0.. ; -1 when fewer are selected): spawn / centre picks.
int pxeNth(vec4 sel, vec4 ids, int k)
{
	int n = pxeCount(), c = 0;
	if (sel.z < 0.5) return -1;
	int m = pxeLoopN(sel, n);
	for (int q = 0; q < PXE_MAX; q++) {
		if (q >= m) break;
		int i = pxeLoopI(sel, ids, q, n);
		if (i < 0 || !pxeSel(i, sel, ids)) continue;
		if (c == k) return i;
		c++;
	}
	return -1;
}

int pxeNumSel(vec4 sel, vec4 ids)
{
	int n = pxeCount(), c = 0;
	if (sel.z < 0.5) return 0;
	int m = pxeLoopN(sel, n);
	for (int q = 0; q < PXE_MAX; q++) {
		if (q >= m) break;
		int i = pxeLoopI(sel, ids, q, n);
		if (i >= 0 && pxeSel(i, sel, ids)) c++;
	}
	return c;
}

// ---- lights (effector kind `light` = a TD Light COMP; header version >= 2; CPU twins effectors_logic.light_block /
// ref_light_factor / ref_light / ref_lights / splat_normal). Light region at L0 = 1 + N * W (W from the header):
// texel L0 = (light count K, block stride, 0, 0), then K blocks (enabled lights, table order), texels:
// 0 (r, g, b, intensity)  1 (position, type 0 point 1 spot 2 area 3 directional)  2 (forward = shine direction, row)
// 3 (att start, att end, att exp, att on)  4 (cos inner, cos outer, cone roll, 0)
// 5 (area half-U xyz, 0)  6 (area half-V xyz, 0). Light rows are never proximity effectors (row texel 6.w = 0).
// Selection: the usual (sel, ids) pair; 'all' = every enabled light; tags / names = the light rows'.
// Colour: texel 0 is already the palette-resolved colour (the effectors COMP's Lights page, palette_convention.md);
// a consumer that recolours per pixel uses pxColSrc(cs, solid, pxeLightColB(...), attrT) from px_palette.glsl.
const int PXE_LIGHT_MAX = 256;

// Texel of the light region header, -1 when there is none (v1 buffer / empty list).
int pxeLightBase()
{
	vec4 h = texelFetch(PXE_ROWS, 0);
	if (h.w < 1.5) return -1;
	int b = 1 + pxI(h.x) * pxI(h.y);
	return b < textureSize(PXE_ROWS) ? b : -1;
}

int pxeLightCountB(int b)
{
	if (b < 0) return 0;
	vec4 lh = texelFetch(PXE_ROWS, b);
	int lw = max(pxI(lh.y), 7);
	return clamp(pxI(lh.x), 0, min(PXE_LIGHT_MAX, (textureSize(PXE_ROWS) - b - 1) / lw));
}

int pxeLightCount() { return pxeLightCountB(pxeLightBase()); }

// Texel t of light k (b = pxeLightBase()).
vec4 pxeLTb(int b, int k, int t) { return texelFetch(PXE_ROWS, b + 1 + k * max(pxI(texelFetch(PXE_ROWS, b).y), 7) + t); }
vec4 pxeLT(int k, int t) { return pxeLTb(pxeLightBase(), k, t); }

int pxeLightRow(int k) { return pxI(pxeLT(k, 2).w); }
int pxeLightType(int k) { return pxI(pxeLT(k, 1).w); }
vec3 pxeLightPos(int k) { return pxeLT(k, 1).xyz; }
vec3 pxeLightDir(int k) { return pxeLT(k, 2).xyz; }

bool pxeLightSelB(int b, int k, vec4 sel, vec4 ids)
{
	if (sel.z < 0.5) return false;
	if (sel.y > 0.5) return true;
	int i = pxI(pxeLTb(b, k, 2).w);
	if ((pxI(pxeT(i, 8).x) & pxI(sel.x)) != 0) return true;
	return any(equal(ids, vec4(float(i + 1))));
}

// Light colour x intensity.
vec3 pxeLightColB(int b, int k) { vec4 c = pxeLTb(b, k, 0); return c.rgb * c.w; }
vec3 pxeLightCol(int k) { return pxeLightColB(pxeLightBase(), k); }

// Attenuation x spot cone of light k at p (0..1); L = unit vector from p to the light (area: to the nearest point of
// its rectangle; directional: -forward). Attenuation as TD's lights: sin(clamp((end - d) / (end - start)) pi/2)^exp;
// spot = smoothstep(outer, inner, angle)^roll (angles from texel 4's cosines).
float pxeLightFactorB(int b, int k, vec3 p, out vec3 L)
{
	vec4 t1 = pxeLTb(b, k, 1);
	vec3 F = pxeLTb(b, k, 2).xyz;
	int ty = pxI(t1.w);
	if (ty == 3) { L = -F; return 1.0; }
	vec3 q = t1.xyz;
	if (ty == 2) {
		vec3 U = pxeLTb(b, k, 5).xyz, V = pxeLTb(b, k, 6).xyz;
		vec3 r = p - q;
		q += U * clamp(dot(r, U) / max(dot(U, U), 1e-12), -1.0, 1.0) + V * clamp(dot(r, V) / max(dot(V, V), 1e-12), -1.0, 1.0);
	}
	vec3 dv = q - p;
	float d = length(dv);
	L = d > 1e-9 ? dv / d : -F;
	float a = 1.0;
	vec4 t3 = pxeLTb(b, k, 3);
	if (t3.w > 0.5) a = pow(sin(clamp((t3.y - d) / max(t3.y - t3.x, 1e-6), 0.0, 1.0) * 1.5707963267948966), t3.z);
	if (ty == 1) {
		vec4 t4 = pxeLTb(b, k, 4);
		float ai = acos(clamp(t4.x, -1.0, 1.0)), ao = acos(clamp(t4.y, -1.0, 1.0));
		float x = clamp((ao - acos(clamp(dot(-L, F), -1.0, 1.0))) / max(ao - ai, 1e-6), 0.0, 1.0);
		a *= pow(x * x * (3.0 - 2.0 * x), max(t4.z, 1e-3));   // smoothstep in angle: TD's cone (live b4, 31550)
	}
	return a;
}

float pxeLightFactor(int k, vec3 p, out vec3 L) { return pxeLightFactorB(pxeLightBase(), k, p, L); }

// rgb light k adds at p: n = unit normal, v = unit vector p -> eye; mode = (model 0 half-Lambert / 1 Lambert / 2 wrap /
// 3 no normal (glow by distance), wrap, spec amount (Blinn), roughness).
// Scalar part of light k at p (attenuation x cone x (diffuse + spec)); pxeLightB = colour x this. PX's `light` module
// recolours per light (palette) with it.
float pxeLightShadeB(int b, int k, vec3 p, vec3 n, vec3 v, vec4 mode)
{
	vec3 L;
	float a = pxeLightFactorB(b, k, p, L);
	if (a <= 0.0) return 0.0;
	int m = pxI(mode.x);
	float dif = 1.0, sp = 0.0;
	if (m != 3) {
		float ndl = dot(n, L);
		if (m == 1) dif = max(ndl, 0.0);
		else if (m == 2) dif = max((ndl + mode.y) / (1.0 + mode.y), 0.0);
		else { float h = ndl * 0.5 + 0.5; dif = h * h; }
		if (mode.z > 0.0 && ndl > 0.0) {
			float r = clamp(mode.w, 0.02, 1.0);
			sp = mode.z * pow(max(dot(n, pxSafeN(L + v, n)), 0.0), 2.0 / (r * r * r * r) - 2.0);
		}
	}
	return a * (dif + sp);
}

vec3 pxeLightB(int b, int k, vec3 p, vec3 n, vec3 v, vec4 mode)
{
	return pxeLightColB(b, k) * pxeLightShadeB(b, k, p, n, v, mode);
}

vec3 pxeLight(int k, vec3 p, vec3 n, vec3 v, vec4 mode) { return pxeLightB(pxeLightBase(), k, p, n, v, mode); }

// Sum of the selected lights at p (0 when the list has no lights).
vec3 pxeLights(vec3 p, vec3 n, vec3 v, vec4 sel, vec4 ids, vec4 mode)
{
	int b = pxeLightBase();
	int K = pxeLightCountB(b);
	vec3 s = vec3(0.0);
	for (int k = 0; k < PXE_LIGHT_MAX; k++) {
		if (k >= K) break;
		if (pxeLightSelB(b, k, sel, ids)) s += pxeLightB(b, k, p, n, v, mode);
	}
	return s;
}

// Splat normal: rotation q (w, x, y, z) applied to the axis of its smallest scale, flipped to face v (p -> eye).
vec3 pxeSplatNormal(vec4 q, vec3 scale, vec3 v)
{
	int a = (scale.x <= scale.y && scale.x <= scale.z) ? 0 : (scale.y <= scale.z ? 1 : 2);
	vec3 n = pxQMat(q)[a];
	return dot(n, v) < 0.0 ? -n : n;
}

// ---- env lights (kind `env`, SA6 screen-as-light; header version >= 3; CPU twins effectors_logic.env_coeffs /
// ref_env / ref_envs; doc docs/builds/effectors.md "Env light"). The light header texel (pxeLightBase) carries
// z = env region texel E and w = grid region texel G (0 = none; v2 readers never read them). Env region: texel E =
// (count M, stride EW, 0, 0), then M blocks: 0 (gain, row index, map 0 screen / 1 equirect / 2 ambient, 0),
// 1..9 SH coefficients (rgb, 0) pre-convolved with the clamped cosine: a white Lambert surface with normal n gets
// gain x max(0, sum_k c_k Y_k(n)) (uniform white sky of radiance 1 -> 1). Selection: the usual (sel, ids) pair.
const int PXE_EW = 10;
const int PXE_ENV_MAX = 64;

int pxeExtBase(int c)
{
	if (texelFetch(PXE_ROWS, 0).w < 2.5) return -1;
	int lb = pxeLightBase();
	if (lb < 0) return -1;
	int e = pxI(texelFetch(PXE_ROWS, lb)[c]);
	return (e > 0 && e < textureSize(PXE_ROWS)) ? e : -1;
}

int pxeEnvBase() { return pxeExtBase(2); }

int pxeEnvCountB(int e)
{
	if (e < 0) return 0;
	vec4 h = texelFetch(PXE_ROWS, e);
	int st = max(pxI(h.y), PXE_EW);
	return clamp(pxI(h.x), 0, min(PXE_ENV_MAX, (textureSize(PXE_ROWS) - e - 1) / st));
}

int pxeEnvCount() { return pxeEnvCountB(pxeEnvBase()); }

vec4 pxeETb(int e, int m, int t) { return texelFetch(PXE_ROWS, e + 1 + m * max(pxI(texelFetch(PXE_ROWS, e).y), PXE_EW) + t); }

int pxeEnvRow(int m) { return pxI(pxeETb(pxeEnvBase(), m, 0).y); }

// Diffuse light of env m at unit normal n (SH9 irradiance / pi x gain), clamped >= 0.
vec3 pxeEnvIrrB(int e, int m, vec3 n)
{
	float x = n.x, y = n.y, z = n.z;
	vec3 s = pxeETb(e, m, 1).rgb * 0.28209479177387814
	       + (pxeETb(e, m, 2).rgb * y + pxeETb(e, m, 3).rgb * z + pxeETb(e, m, 4).rgb * x) * 0.4886025119029199
	       + (pxeETb(e, m, 5).rgb * (x * y) + pxeETb(e, m, 6).rgb * (y * z) + pxeETb(e, m, 8).rgb * (x * z)) * 1.0925484305920792
	       + pxeETb(e, m, 7).rgb * ((3.0 * z * z - 1.0) * 0.31539156525252005)
	       + pxeETb(e, m, 9).rgb * ((x * x - y * y) * 0.5462742152960396);
	return max(s, vec3(0.0)) * pxeETb(e, m, 0).x;
}

vec3 pxeEnvIrr(int m, vec3 n) { return pxeEnvIrrB(pxeEnvBase(), m, n); }

bool pxeEnvSelB(int e, int m, vec4 sel, vec4 ids)
{
	if (sel.z < 0.5) return false;
	if (sel.y > 0.5) return true;
	int i = pxI(pxeETb(e, m, 0).y);
	if ((pxI(pxeT(i, 8).x) & pxI(sel.x)) != 0) return true;
	return any(equal(ids, vec4(float(i + 1))));
}

// Sum of the selected envs at normal n (0 without envs / before version 3). Plain points without normals: pass the
// view vector or vec3(0, 1, 0), or use pxeEnvIrr(m, n) per env.
vec3 pxeEnvs(vec3 n, vec4 sel, vec4 ids)
{
	int e = pxeEnvBase();
	int M = pxeEnvCountB(e);
	vec3 s = vec3(0.0);
	for (int m = 0; m < PXE_ENV_MAX; m++) {
		if (m >= M) break;
		if (pxeEnvSelB(e, m, sel, ids)) s += pxeEnvIrrB(e, m, n);
	}
	return s;
}
#endif
