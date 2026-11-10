// BO_particles state update: ONE compute pass per frame (T-46/T-47 safe). Clean-room; mirrors
// particles_logic.update() line by line (tests: test/test_particles.py). Design credit: Tim Gerritsen's Compute
// Particle System (CC BY 4.0) for the state-texture + instanced-fetch idea; curl noise per Bridson et al. 2007.
// State texture rgba32float, width 3*side, height side. Particle id = y*side + x (x < side), texels:
//   (3x, y) = P.xyz, age    (3x+1, y) = V.xyz, life    (3x+2, y) = colour.rgb, r
// Inputs: 0 = last state (Feedback TOP; unused in place), 1 = emit TOP, 2 = field TOP (rg = push).
// Defining STATE_INPLACE (builder prepends it for Statemode = inplace) reads the own output instead (Output
// Access = Read-Write, Clear Outputs off).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uP[31];   // rows: see particles_logic.step()

const float TAU = 6.283185307179586;

uint hash_u32(uint x)
{
	x ^= x >> 16u;
	x *= 0x7feb352du;
	x ^= x >> 15u;
	x *= 0x846ca68bu;
	x ^= x >> 16u;
	return x;
}

float rnd(uint id, uint salt)
{
	return float(hash_u32(id * 2654435761u + salt) >> 8u) * (1.0 / 16777216.0);
}

vec3 curl1(vec3 p, float t)
{
	return vec3(-sin(p.x - 0.6 * t) * sin(p.y + 0.5 * t) - cos(p.z + 0.9 * t) * cos(p.x + 1.1 * t),
	            -sin(p.y + 1.3 * t) * sin(p.z - 0.7 * t) - cos(p.x - 0.6 * t) * cos(p.y + 0.5 * t),
	            -sin(p.z + 0.9 * t) * sin(p.x + 1.1 * t) - cos(p.y + 1.3 * t) * cos(p.z - 0.7 * t));
}

vec3 unitDir(float r0, float r1)
{
	float z = 2.0 * r0 - 1.0;
	float ph = TAU * r1;
	float s = sqrt(max(0.0, 1.0 - z * z));
	return vec3(s * cos(ph), s * sin(ph), z);
}

vec3 forces(vec3 P, vec3 V, float age, float rr)
{
	vec3 F = vec3(0.0);
	float amp = 1.0;
	float sc = uP[3].y;
	int oc = int(uP[3].w + 0.5);
	for (int o = 0; o < 4; o++) {
		if (o >= oc) break;
		F += curl1(P * sc, uP[3].z + 17.0 * float(o)) * amp;
		amp *= 0.5;
		sc *= 2.0;
	}
	F *= uP[3].x;
	F += uP[4].xyz + uP[5].xyz - V * uP[4].w;
	if (uP[6].w != 0.0) { vec3 d = uP[6].xyz - P; F += d * (uP[6].w * pow(max(dot(d, d) + uP[9].x, 1e-6), -1.5)); }
	if (uP[7].w != 0.0) { vec3 d = uP[7].xyz - P; F += d * (uP[7].w * pow(max(dot(d, d) + uP[9].y, 1e-6), -1.5)); }
	float al = length(uP[8].xyz);
	if (al > 1e-6 && uP[8].w != 0.0) F += cross(uP[8].xyz / al, P) * uP[8].w;
	for (int k = 20; k <= 23; k += 3) {        // spiral fields 1 / 2 (TC-13): swirl + pull to the axis + lift along it
		float sw = uP[k].w, pull = uP[k + 1].w, lift = uP[k + 2].x, R = uP[k + 2].y;
		if (sw == 0.0 && pull == 0.0 && lift == 0.0) continue;
		vec3 A = uP[k + 1].xyz;
		vec3 r = P - uP[k].xyz;
		vec3 rp = r - A * dot(r, A);
		float d2 = dot(rp, rp);
		float g = (R > 0.0) ? R * R / (d2 + R * R) : 1.0;
		F += A * (lift * g);
		if (d2 > 1e-12) F += (cross(A, rp) * sw - rp * pull) * (g / sqrt(d2));
	}
	if (uP[5].w != 0.0) {
		vec2 hb = max(uP[10].xy, vec2(1e-3));
		vec2 uv = P.xy / (2.0 * hb) + 0.5;
		F.xy += uP[5].w * texture(sTD2DInputs[2], uv).rg;
	}
	if (uP[30].x != 0.0)                       // paper flutter (sideways sine, per-particle phase rr)
		F += uP[30].x * vec3(sin(TAU * (uP[30].y * age + rr)), 0.0, cos(TAU * (0.7 * uP[30].y * age + 1.3 * rr)));
#ifdef PXE_HOOK
	F += pxeParticleForce(P, V);        // shared effectors (builders/effectors.py attach; off = 0)
#endif
	return F;
}

void spawn(uint id, uint sb, out vec4 a, out vec4 b, out vec4 c)
{
	int src = int(uP[1].w + 0.5);
	float r0 = rnd(id, sb), r1 = rnd(id, sb + 1u), r2 = rnd(id, sb + 2u);
	vec3 col = vec3(1.0);
	vec3 u = vec3(0.0);
	float cw = -1.0;
	bool ok = true;
	if (src == 0) u = unitDir(r0, r1) * pow(r2, 1.0 / 3.0);
	else if (src == 1) u = vec3(2.0 * r0 - 1.0, 2.0 * r1 - 1.0, 2.0 * r2 - 1.0);
	else if (src == 2) u = vec3(cos(TAU * r0), sin(TAU * r0), 0.0);
	else if (src == 3) u = vec3(2.0 * r0 - 1.0, 0.0, 0.0);
	else if (src == 6) {                       // strand seeds: seed k of K on the unit ring + box jitter
		int K = max(int(uP[26].x + 0.5), 1);
		int k = min(int(floor(r0 * float(K))), K - 1);
		float a = TAU * float(k) / float(K);
		float j = uP[26].y;
		u = vec3(cos(a) + j * (2.0 * r1 - 1.0), sin(a) + j * (2.0 * r2 - 1.0), j * (2.0 * rnd(id, sb + 8u) - 1.0));
		cw = (float(k) + 0.5) / float(K);
	}
	else {
		ok = false;
		ivec2 esz = textureSize(sTD2DInputs[1], 0);
		for (uint k = 0u; k < 8u; k++) {
			vec2 uv = vec2(rnd(id, sb + 20u + 2u * k), rnd(id, sb + 21u + 2u * k));
			if (src == 4) {
				vec4 e = texture(sTD2DInputs[1], uv);
				float w = (uP[12].w > 0.5) ? e.a : dot(e.rgb, vec3(0.2126, 0.7152, 0.0722));
				if (w > uP[11].w) { u = vec3(2.0 * uv - 1.0, 0.0); col = e.rgb; ok = true; break; }
			} else {
				ivec2 q = clamp(ivec2(uv * vec2(esz)), ivec2(0), esz - 1);   // T-35: never read out of bounds
				vec4 e = texelFetch(sTD2DInputs[1], q, 0);
				if (e.a > 0.0) { u = e.rgb; ok = true; break; }
			}
		}
	}
	vec3 P = uP[12].xyz + u * uP[13].xyz;
#ifdef PXE_HOOK
	P = pxeSpawnAt(P, rnd(id, sb + 40u), rnd(id, sb + 41u), rnd(id, sb + 42u), rnd(id, sb + 43u));
#endif
	vec3 rd = unitDir(rnd(id, sb + 3u), rnd(id, sb + 4u));
	float el = length(uP[14].xyz);
	float spread = clamp(uP[11].z, 0.0, 1.0);
	vec3 d = (el > 1e-6) ? mix(uP[14].xyz / el, rd, spread) : rd;
	float dl = length(d);
	d = (dl > 1e-6) ? d / dl : rd;
	float life = max(uP[2].z * (1.0 + uP[2].w * (2.0 * rnd(id, sb + 5u) - 1.0)), 1e-3);
	a = vec4(P, 0.0);
	b = vec4(d * (uP[11].y * (1.0 + uP[30].z * (2.0 * rnd(id, sb + 9u) - 1.0))), ok ? life : 0.0);
	c = vec4(col, (src == 6) ? cw : rnd(id, sb + 6u));
}

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	int side = int(uP[1].x + 0.5);
	if (g.x >= side || g.y >= side) return;
	uint id = uint(g.y * side + g.x);
	uint count = uint(uP[0].w + 0.5);
	if (id >= count) return;
	ivec2 t0 = ivec2(g.x * 3, g.y);
	ivec2 t1 = t0 + ivec2(1, 0);
	ivec2 t2 = t0 + ivec2(2, 0);
	bool reset = uP[0].z > 0.5;
	vec4 a = vec4(0.0), b = vec4(0.0), c = vec4(0.0);
#ifdef STATE_INPLACE
	a = TDImageLoadOutput(0, ivec3(t0, 0));
	b = TDImageLoadOutput(0, ivec3(t1, 0));
	c = TDImageLoadOutput(0, ivec3(t2, 0));
#else
	ivec2 isz = textureSize(sTD2DInputs[0], 0);
	if (isz.x < t0.x + 3 || isz.y <= t0.y) reset = true;      // last state has another size (Count changed)
	else {
		a = texelFetch(sTD2DInputs[0], t0, 0);
		b = texelFetch(sTD2DInputs[0], t1, 0);
		c = texelFetch(sTD2DInputs[0], t2, 0);
	}
#endif
	float dt = uP[0].x;
	uint frame = uint(uP[0].y + 0.5);
	uint sb = hash_u32(uint(uP[1].y + 0.5)) ^ (frame * 0x9E3779B9u);
	int emode = int(uP[1].z + 0.5);
	uint w0 = uint(uP[2].x + 0.5);
	uint wlen = uint(uP[2].y + 0.5);
	bool inwin = wlen > 0u && ((id + count - (w0 % count)) % count) < wlen;
	if (reset) {
		spawn(id, sb, a, b, c);
		if (emode == 0 && uP[13].w > 0.5) a.w = -rnd(id, sb + 7u) * b.w;
		else if (emode == 1) { a.w = 0.0; b.w = 0.0; }
	} else if (inwin) {
		spawn(id, sb, a, b, c);
	} else if (a.w < 0.0) {
		a.w += dt;
	} else if (a.w < b.w) {
		vec3 P = a.xyz, V = b.xyz;
		vec3 F = forces(P, V, a.w, c.w);
		V += F * dt;
		P += V * dt;
		float age = a.w + dt;
		int bm = int(uP[9].z + 0.5);
		vec3 B = uP[10].xyz;
		for (int k = 0; k < 3; k++) {
			if (B[k] <= 0.0) continue;
			if (bm == 1) P[k] = mod(P[k] + B[k], 2.0 * B[k]) - B[k];
			else if (bm == 2 && abs(P[k]) > B[k]) {
				P[k] = clamp(sign(P[k]) * (2.0 * B[k] - abs(P[k])), -B[k], B[k]);
				V[k] = -V[k] * uP[11].x;
			} else if (bm == 3 && abs(P[k]) > B[k]) age = b.w;
		}
		if (uP[9].w > 0.5 && P.y < uP[10].w) { P.y = uP[10].w; V.y = abs(V.y) * uP[11].x; }
#ifdef PXE_HOOK
		if (pxeKill(P)) age = b.w;            // killed near the effectors (Effkill)
#endif
		a = vec4(P, age);
		b = vec4(V, b.w);
	}
	if (!reset && emode == 0 && a.w >= b.w) spawn(id, sb, a, b, c);   // continuous: reborn the frame it dies
	if (uP[14].w > 0.5) c.w = uP[0].y;    // Debugstamp (V2 tear check): frame number in every particle
	TDImageStoreOutput(0, ivec3(t0, 0), a);
	TDImageStoreOutput(0, ivec3(t1, 0), b);
	TDImageStoreOutput(0, ivec3(t2, 0), c);
}
