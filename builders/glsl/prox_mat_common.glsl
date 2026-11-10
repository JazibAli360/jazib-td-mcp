// MX_prox_material shared block (vertex + pixel stage of the GLSL MAT). Included after the generated header
// (prox_mat_logic.glsl_header: uMX[], MX_* rows, uMXT, uE = uMX, uG) and builders/glsl/px_common.glsl (PX's
// effector / falloff / point-set maths, shared, not copied). numpy twin: prox_mat_logic.ref_weight / ref_push / drive.

#ifdef MX_VC_PASS
#define sPts sTD2DInputs[1]   // vertex cache pass (compute): the same textures arrive as wired inputs (vc_s0 / vc_s1)
#define sField sTD2DInputs[2]
#else
uniform sampler2D sPts;     // points texture (pts pass) or blank4
uniform sampler2D sField;   // point field atlas (field pass) or blank4
#endif

int mxI(float x) { return int(floor(x + 0.5)); }

// PX lib reads the effector count from uG[1].z.
void mxInit() { uG[1] = vec4(0.0, 0.0, MX_G0.x, 0.0); }

// Drive row (near, far, curve, -): far at w = 0, near at w = 1, shaped by w^curve.
float mxDrive(float w, vec4 d) { return mix(d.y, d.x, pow(clamp(w, 0.0, 1.0), max(d.z, 1e-3))); }

float mxComb(float a, float b, int comb)
{
	if (comb == 1) return a + b;
	if (comb == 2) return a * b;
	if (comb == 3) return a + b - a * b;
	return max(a, b);
}

struct MXProx {
	float w;      // proximity weight (after combine, gain, flip)
	float d;      // signed distance to the strongest source (effector surface / point radius)
	vec3 dir;     // outward unit direction from that source (only when asked: costs SDF / field samples)
	vec3 axis;    // up axis of the strongest object effector (world y otherwise)
	vec3 vel;     // velocity of the nearest effector point (units/s), 0 without a point set
};

float mxFieldDist(vec3 p)
{
	return pxFieldSample(sField, p, MX_GRID.xyz, MX_GRID2.xyz, mxI(MX_GRID.w), mxI(MX_GRID2.w), 0).x;
}

MXProx mxProx(vec3 p, bool wantDir)
{
	MXProx r;
	r.w = 0.0;
	r.d = 1e9;
	r.dir = vec3(0.0, 1.0, 0.0);
	r.axis = vec3(0.0, 1.0, 0.0);
	r.vel = vec3(0.0);
	float R = MX_PROX.x, k = MX_PROX.y;
	int shape = mxI(MX_PROX.z), comb = mxI(MX_PROX.w);
	float nedge = MX_RAG.x, nfreq = MX_RAG.y;
	int neff = mxI(MX_G0.x), path = mxI(MX_G0.y), m = mxI(MX_G0.z);
	bool list = uEffSel.z > 0.5;           // Effsource 'list': the shared /project1/effectors list (packed buffer)
	bool he = list ? pxeCount() > 0 : neff > 0, hp = path > 0 && m > 0;
	float we = 0.0, wp = 0.0;
	if (he && list) {
		int best;
		we = pxeW(p, uEffSel, uEffIds, uEffMix, uEffFall, best);
		if (best >= 0) {
			r.d = pxeSd(best, p, pxeRadius(best, uEffMix, uEffFall));
			r.axis = pxeAxis(best);
			if (wantDir) r.dir = pxeGrad(best, p);
			r.vel = pxeVelAt(best, p);
		}
		he = best >= 0;
	} else if (he) {
		int best;
		we = pxW(p, (1 << neff) - 1, R, k, shape, comb, nedge, nfreq, best);
		if (best >= 0) {
			r.d = pxESd(best, p);
			r.axis = pxEAxis(best);
			if (wantDir) r.dir = pxEGrad(best, p);
		}
	}
	if (hp) {
		float prad = MX_PTS.w;
		int mode = mxI(MX_PTS2.x);
		float dist, dens = 0.0;
		vec3 vel = vec3(0.0), pdir = vec3(0.0, 1.0, 0.0);
		if (path == 1) {
			int bi;
			int pw = mxI(MX_PTS.y), ph = mxI(MX_PTS.z);
			dist = pxPtsNearest(sPts, p, m, pw, ph, bi);
			if (mode == 1) dens = pxPtsDensity(sPts, p, m, pw, ph, max(prad, 1e-4));
			if (bi >= 0) {
				pdir = pxSafeN(p - pxPtsTexel(sPts, bi, pw, ph, 0).xyz, vec3(0.0, 1.0, 0.0));
				vel = pxPtsTexel(sPts, bi, pw, ph, 1).xyz;
			}
		} else {
			int G = mxI(MX_GRID.w), T = mxI(MX_GRID2.w);
			vec4 f = pxFieldSample(sField, p, MX_GRID.xyz, MX_GRID2.xyz, G, T, 0);
			dist = f.x;
			dens = f.y;
			vel = pxFieldSample(sField, p, MX_GRID.xyz, MX_GRID2.xyz, G, T, 1).xyz;
			if (wantDir) {
				vec3 h = MX_GRID2.xyz / float(max(G, 1));
				float e = max(min(h.x, min(h.y, h.z)), 1e-4);
				vec3 g = vec3(mxFieldDist(p + vec3(e, 0.0, 0.0)) - mxFieldDist(p - vec3(e, 0.0, 0.0)),
				              mxFieldDist(p + vec3(0.0, e, 0.0)) - mxFieldDist(p - vec3(0.0, e, 0.0)),
				              mxFieldDist(p + vec3(0.0, 0.0, e)) - mxFieldDist(p - vec3(0.0, 0.0, e)));
				pdir = pxSafeN(g, vec3(0.0, 1.0, 0.0));
			}
		}
		float dp = pxPtsEqDist(mode, dist, dens, prad, R, MX_PTS2.y);
		if (nedge != 0.0) dp += (pxNoise(p * nfreq, 7u) - 0.5) * nedge * R;
		wp = pxFall(dp, R, k, shape) * MX_RAG.w;
		if (!he || wp > we) {
			r.d = dp;
			r.dir = pdir;
		}
		r.vel = vel;
	}
	float w = (he && hp) ? mxComb(we, wp, comb) : (he ? we : wp);
	w *= MX_RAG.z;
	if (MX_G0.w > 0.5) w = 1.0 - w;
	r.w = w;
	return r;
}

// World-space vertex offset at rest position p with normal n (Dispmode, prox_mat_logic.DISPMODES).
vec3 mxDisplace(vec3 p, vec3 n, float t)
{
	int mode = mxI(MX_DSP.w);
	if (mode == 0) return vec3(0.0);
	int dsel = mxI(MX_DSP2.x);
	MXProx r = mxProx(p, dsel == 1 || mode == 2);
	float a = mxDrive(r.w, MX_DSP);
	vec3 dir = n;
	if (dsel == 1) dir = r.dir;
	else if (dsel == 2) dir = r.axis;
	else if (dsel == 3) dir = vec3(0.0, 1.0, 0.0);
	if (mode == 1) return dir * a;                                           // push / pull
	if (mode == 2) return -r.dir * (a >= 0.0 ? min(a, max(r.d, 0.0)) : a);   // attract, never past the surface
	if (mode == 3) {                                                         // swell ring, peak at w = 0.5
		float x = clamp(r.w, 0.0, 1.0);
		return dir * mix(MX_DSP.y, MX_DSP.x, 4.0 * x * (1.0 - x));
	}
	if (mode == 4) return dir * a * sin(r.d * MX_DSP2.y - t * MX_DSP2.z);  // ripple from the surface
	if (mode == 5) return dir * a * (pxFbm(p * MX_DSP2.w + vec3(0.0, 0.3 * t, 0.0), 3, 11u) * 2.0 - 1.0);
	if (mode == 6) return r.vel * MX_DSP3.x * clamp(r.w, 0.0, 1.0) + dir * a;  // wake of moving points
	return vec3(0.0);
}

// Vertex displacement of a rest point (world) with unit normal wn: returns the offset; with Normalfix, wn becomes
// the normal of the displaced surface, rebuilt from two displaced neighbours along the tangent plane. One mxDisplace
// call site in a loop (centre + 2 neighbours): three inlined copies of the proximity code cost ~1.4x per evaluation
// in the vertex stage (perf-b2-w4). Used by the vertex shader (fallback path) and the vertex cache pass (vc_cache),
// so both give the same numbers.
vec3 mxVertDisp(vec3 rest, inout vec3 wn)
{
	float t = uMXT.x;
	bool nf = MX_DSP3.y > 0.5;
	float e = max(MX_DSP3.z, 1e-5);
	vec3 a = abs(wn.y) < 0.99 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
	vec3 t1 = normalize(cross(wn, a));
	vec3 t2 = cross(wn, t1);
	vec3 d0 = vec3(0.0), q1 = vec3(0.0), q2 = vec3(0.0);
	int nk = nf ? 3 : 1;
	for (int k = 0; k < 3; k++) {
		if (k >= nk) break;
		vec3 o = k == 0 ? rest : (k == 1 ? rest + t1 * e : rest + t2 * e);
		vec3 r = mxDisplace(o, wn, t);
		if (k == 0) d0 = r;
		else if (k == 1) q1 = r;
		else q2 = r;
	}
	if (nf) {
		vec3 p1 = t1 * e + q1 - d0;
		vec3 p2 = t2 * e + q2 - d0;
		vec3 nn = cross(p1, p2);
		if (dot(nn, wn) < 0.0) nn = -nn;
		if (dot(nn, nn) > 1e-20) wn = normalize(nn);
	}
	return d0;
}
