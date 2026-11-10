// gen_interactive_pigment_state: GEN_interactive 'pigment' particle state (compute, 2 x Side wide, Side + 1 high,
// rgba32float). in0 = last state (Feedback TOP `state_fb`), in1 = rack points (`pts`), in2 = `field` (Fieldsource:
// mask = rack gi_mask r presence, flowtop = an external velocity TOP e.g. BN_fluid2d out2, none = pts, unused).
// Particle (i, j), i, j < Side: texel (2i, j) = (x px, y px, age s, life s), (2i + 1, j) = (anchor x px, anchor y px,
// seed 0..1 (24 bits), speed px/s). The anchor is where the particle's colour is sampled (its birth point, pulled
// toward the particle at Morph per s). Row Side = meta: texel 0 = (0, T module time, last absTime, epoch), texel 1 =
// (dts = sim step of this cook, cooks, 0, 0). Self-clocked: a new frame steps by dts = dt x Speed (Speed 0 = frozen);
// a second cook in the same frame holds; a new epoch (Reset) or a size change re-seeds (ages staggered).
// Velocity (px/s, first order, no inertia): Flowstrength x boost x curl of an fbm potential (Flowscale px per noise
// unit, Octaves, Evolve = drift of the potential per s) + mask: Maskforce x grad(presence) x 100 px + flowtop:
// Flowgain x field.xy x (H / field height) (cells/s -> px/s) + points within Radius px: w = (1 - r/R)^2 x
// (Pointforce push / attract / swirl + Pointvel x the point's velocity).  boost = 1 + beat pulse + audio / manual.
// == builders/gen_interactive_pigment_logic.py state_step.
// uTime = now, Speed, epoch, Side; uFlow = Flowscale, Flowstrength, Evolve, Octaves; uLife = Life, Lifevar,
// Spawnmode, Seed; uPt = Radius, Pointforce, Pointmode, Pointvel; uExt = Fieldsource, Maskforce, Flowgain, Edge;
// uMisc = Morph, W, H, 0; uDrv / uDg = rack drive, module Drive page.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uTime;
uniform vec4 uFlow;
uniform vec4 uLife;
uniform vec4 uPt;
uniform vec4 uExt;
uniform vec4 uMisc;
uniform vec4 uDrv;
uniform vec4 uDg;

#define MAXPTS 256
#define SB 16777216.0

float pg_h(int sb, int k) { return gs_hash3(sb, k, int(uLife.w)); }

float pg_fbm(vec2 q, float z)
{
	float v = 0.0, a = 0.5;
	int oc = clamp(int(uFlow.w + 0.5), 1, 6);
	for (int o = 0; o < 6; o++) {
		if (o >= oc) break;
		v += a * gs_vnoise(q + vec2(z, 0.61 * z) + vec2(float(o) * 5.3, float(o) * 9.1), int(uLife.w) + 31 + o);
		q *= 2.0;
		a *= 0.5;
	}
	return v;
}

// curl of the potential at p px (central differences, 0.01 noise units), in noise units per noise unit
vec2 pg_curl(vec2 p, float T)
{
	vec2 q = p / max(uFlow.x, 1e-3);
	float z = T * uFlow.z;
	float e = 0.01;
	float dx = pg_fbm(q + vec2(e, 0.0), z) - pg_fbm(q - vec2(e, 0.0), z);
	float dy = pg_fbm(q + vec2(0.0, e), z) - pg_fbm(q - vec2(0.0, e), z);
	return vec2(dy, -dx) / (2.0 * e);
}

float pg_pres(vec2 p, vec2 sz)
{
	return texture(sTD2DInputs[2], p / sz).r;
}

vec2 pg_vel(vec2 p, float T, vec2 sz)
{
	float boost = 1.0 + gi_env(uDrv, uDg) + gi_level(uDrv, uDg);
	vec2 v = uFlow.y * boost * pg_curl(p, T);
	int fs = int(uExt.x + 0.5);
	ivec2 fsz = textureSize(sTD2DInputs[2], 0);
	if (fs == 0 && uExt.y != 0.0) {
		vec2 e = sz / vec2(fsz);
		vec2 g = vec2(pg_pres(p + vec2(e.x, 0.0), sz) - pg_pres(p - vec2(e.x, 0.0), sz),
		              pg_pres(p + vec2(0.0, e.y), sz) - pg_pres(p - vec2(0.0, e.y), sz)) / (2.0 * e);
		v += uExt.y * g * 100.0;
	} else if (fs == 1) {
		v += uExt.z * texture(sTD2DInputs[2], p / sz).xy * (sz.y / float(fsz.y));
	}
	ivec2 psz = textureSize(sTD2DInputs[1], 0);
	int np = min(psz.x, MAXPTS);
	float R = max(uPt.x, 1e-3);
	int pm = int(uPt.z + 0.5);
	for (int k = 0; k < MAXPTS; k++) {
		if (k >= np) break;
		vec4 q = texelFetch(sTD2DInputs[1], ivec2(k, 0), 0);
		if (!gi_present(q)) continue;
		vec2 d = p - q.xy * sz;
		float r = length(d);
		if (r >= R) continue;
		float w = (1.0 - r / R) * (1.0 - r / R);
		vec2 dn = r > 1e-6 ? d / r : vec2(0.0);
		vec2 f = pm == 1 ? -dn : (pm == 2 ? gi_perp(dn) : dn);
		v += w * (uPt.y * f + uPt.w * q.zw * sz);
	}
	return v;
}

// a new life for seed s: position (Spawnmode), life
vec4 pg_spawn(float s, vec2 sz, out float life)
{
	int sb = int(s * SB);
	float h1 = pg_h(sb, 1), h2 = pg_h(sb, 2), h3 = pg_h(sb, 3), h4 = pg_h(sb, 4);
	vec2 p = vec2(h1, h2) * sz;
	int mode = int(uLife.z + 0.5);
	if (mode == 1) {
		ivec2 psz = textureSize(sTD2DInputs[1], 0);
		int k = min(int(h3 * float(psz.x)), psz.x - 1);
		vec4 q = texelFetch(sTD2DInputs[1], ivec2(k, 0), 0);
		if (gi_present(q)) {
			float a = GI_TAU * pg_h(sb, 5);
			p = q.xy * sz + uPt.x * sqrt(h4) * vec2(cos(a), sin(a));
		}
	} else if (mode == 2 && int(uExt.x + 0.5) == 0) {
		for (int t = 0; t < 4; t++) {
			p = vec2(pg_h(sb, 10 + 2 * t), pg_h(sb, 11 + 2 * t)) * sz;
			if (pg_pres(p, sz) > 0.5) break;
		}
	} else if (mode == 3) p = vec2(h1 * sz.x, h2 * 0.02 * sz.y);
	life = max(uLife.x * (1.0 + uLife.y * (2.0 * h3 - 1.0)), 0.05);
	return vec4(p, 0.0, life);
}

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	int S = int(uTime.w + 0.5);
	if (g.x >= 2 * S || g.y > S) return;
	ivec2 ssz = textureSize(sTD2DInputs[0], 0);
	bool fresh = ssz.x != 2 * S || ssz.y != S + 1;
	vec4 m0 = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], ivec2(0, S), 0);
	vec4 m1 = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], ivec2(1, S), 0);
	fresh = fresh || m0.w != uTime.z;
	if (!fresh && m0.z == uTime.x) { TDImageStoreOutput(0, ivec3(g, 0), texelFetch(sTD2DInputs[0], g, 0)); return; }
	float dt = fresh ? 0.0 : clamp(uTime.x - m0.z, 0.0, 0.1);
	float dts = dt * uTime.y;
	float T = (fresh ? 0.0 : m0.y) + dts;
	if (g.y == S) {
		vec4 o = vec4(0.0);
		if (g.x == 0) o = vec4(0.0, T, uTime.x, uTime.z);
		else if (g.x == 1) o = vec4(dts, (fresh ? 0.0 : m1.y) + 1.0, 0.0, 0.0);
		TDImageStoreOutput(0, ivec3(g, 0), o);
		return;
	}
	int i = g.x / 2, j = g.y, half_ = g.x % 2;
	vec2 sz = uMisc.yz;
	vec4 A, Bv;
	float life;
	if (fresh) {
		float s = gs_hash3(i, j, int(uLife.w));
		A = pg_spawn(s, sz, life);
		A.z = pg_h(int(s * SB), 6) * life;                 // staggered ages: they never all die together
		Bv = vec4(A.xy, s, 0.0);
	} else {
		A = texelFetch(sTD2DInputs[0], ivec2(2 * i, j), 0);
		Bv = texelFetch(sTD2DInputs[0], ivec2(2 * i + 1, j), 0);
		if (dts != 0.0) {
			vec2 v = pg_vel(A.xy, T, sz);
			A.xy += v * dts;
			A.z += abs(dts);
			Bv.w = length(v);
			Bv.xy += (A.xy - Bv.xy) * clamp(uMisc.x * abs(dts), 0.0, 1.0);
			float m = 0.05 * sz.y;
			bool out_ = A.x < -m || A.y < -m || A.x > sz.x + m || A.y > sz.y + m;
			if (out_ && int(uExt.w + 0.5) == 1) {
				vec2 w = mod(A.xy, sz);
				Bv.xy += w - A.xy;
				A.xy = w;
				out_ = false;
			}
			if (A.z >= A.w || out_) {
				float s = pg_h(int(Bv.z * SB), 7);
				A = pg_spawn(s, sz, life);
				Bv = vec4(A.xy, s, 0.0);
			}
		}
	}
	TDImageStoreOutput(0, ivec3(g, 0), half_ == 0 ? A : Bv);
}
