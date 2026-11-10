// BN_cloth: ONE fused XPBD substep (compute, T-46/T-47). Prepended at build time: cloth_logic.glsl_header().
// in0 = state 2W x H rgba32f (x < W: position xyz, x >= W: velocity xyz), in1 = rest W x H (xyz, w = pin flag),
// in2 = frame-start normals W x H (wind). Out: the new state, same layout. Maths = cloth_logic.substep_ref.
// predict (gravity + wind + jelly goal) -> one gather-Jacobi pass over the 12-stencil with XPBD compliance
// -> tethers to pins -> spheres + floor + friction -> velocity. Each invocation moves only its own vertex
// (no write conflicts, no atomics). Neighbours' predictions are recomputed inline (cheap, no extra pass).
layout (local_size_x = 8, local_size_y = 8) in;
uniform samplerBuffer uP;      // NROWS vec4 rows from the `uni` CHOP (cloth_logic.ROWS)

int gW, gH;
vec4 R(int k) { return texelFetch(uP, k); }
vec3 posAt(ivec2 c) { return texelFetch(sTD2DInputs[0], c, 0).xyz; }
vec3 velAt(ivec2 c) { return texelFetch(sTD2DInputs[0], ivec2(c.x + gW, c.y), 0).xyz; }
vec4 restAt(ivec2 c) { return texelFetch(sTD2DInputs[1], c, 0); }
vec3 nrmAt(ivec2 c) { return texelFetch(sTD2DInputs[2], c, 0).xyz; }
bool inside(ivec2 c) { return c.x >= 0 && c.y >= 0 && c.x < gW && c.y < gH; }

float weight(vec4 r)
{
	vec4 m = R(R_MASS);
	return (r.w > 0.5 && m.x < 0.5) ? 0.0 : m.y;
}

uint hash3(uvec3 v)
{
	v = v * 1664525u + 1013904223u;
	v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
	v ^= v >> 16u;
	v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
	return v.x ^ v.y ^ v.z;
}
float hn(ivec3 c, int seed) { return float(hash3(uvec3(c + ivec3(seed * 101, seed * 7, 0))) & 0xFFFFFFu) / 16777216.0; }
float vnoise3(vec3 x, int seed)
{
	ivec3 i = ivec3(floor(x));
	vec3 f = fract(x);
	vec3 u = f * f * (3.0 - 2.0 * f);
	float a = mix(mix(hn(i, seed), hn(i + ivec3(1, 0, 0), seed), u.x),
	              mix(hn(i + ivec3(0, 1, 0), seed), hn(i + ivec3(1, 1, 0), seed), u.x), u.y);
	float b = mix(mix(hn(i + ivec3(0, 0, 1), seed), hn(i + ivec3(1, 0, 1), seed), u.x),
	              mix(hn(i + ivec3(0, 1, 1), seed), hn(i + ivec3(1, 1, 1), seed), u.x), u.y);
	return mix(a, b, u.z);
}

vec3 predict(ivec2 c, vec4 r)
{
	if (weight(r) == 0.0) return r.xyz;                       // pinned: stays at rest
	vec4 st = R(R_STEP);
	vec3 p = posAt(c);
	vec3 v = velAt(c);
	vec4 wd = R(R_WIND);
	vec4 tb = R(R_TURB);
	vec3 wv = wd.xyz;
	if (tb.x != 0.0) wv *= 1.0 + tb.x * (2.0 * vnoise3(p * tb.y + vec3(0.0, 0.0, tb.z), int(tb.w)) - 1.0);
	vec3 n = nrmAt(c);
	vec3 a = R(R_GRAV).xyz + (1.0 - wd.w) * wv + wd.w * n * dot(n, wv);
	vec3 X = p + v * st.x + a * st.y;
	vec4 m = R(R_MASS);
	if (m.w > 0.5 && m.z != 0.0 && R(R_ROT0).w > 0.5) {      // jelly: pull toward the best-fit rigid rest shape
		vec3 q = r.xyz - R(R_REST).xyz;
		vec3 g = R(R_CENT).xyz + vec3(dot(R(R_ROT0).xyz, q), dot(R(R_ROT1).xyz, q), dot(R(R_ROT2).xyz, q));
		X += m.z * (g - X);
	}
	return X;
}

vec3 tether(vec3 Y, vec4 r, ivec2 a, float slack)
{
	vec3 A = restAt(a).xyz;
	float lr = length(r.xyz - A) * slack;
	vec3 d = Y - A;
	float dl = length(d);
	if (dl > lr && dl > 1e-9) Y = A + d / dl * lr;
	return Y;
}

void store(ivec2 c, vec3 p, vec3 v)
{
	TDImageStoreOutput(0, ivec3(c, 0), vec4(p, 1.0));
	TDImageStoreOutput(0, ivec3(c.x + gW, c.y, 0), vec4(v, 0.0));
}

// Perf (perf lane 2, 27 Oct): the 12-stencil reads every neighbour's prediction; the 8x8 group computes the
// predictions (and weights) of its tile + a 2-cell halo ONCE into shared memory (144 instead of 64 x 13 predict()
// calls); same function, same inputs.
shared vec3 sX[144];
shared float sW[144];

void main()
{
	vec4 grid = R(R_GRID);
	gW = int(grid.x + 0.5);
	gH = int(grid.y + 0.5);
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	ivec2 T0 = ivec2(gl_WorkGroupID.xy) * 8;
	if (T0.x >= gW || T0.y >= gH) return;                      // whole group outside (right half idle): uniform
	bool own = c.x < gW && c.y < gH;
	if (textureSize(sTD2DInputs[1], 0) != ivec2(gW, gH) || textureSize(sTD2DInputs[2], 0) != ivec2(gW, gH)) {
		if (own) store(c, vec3(0.0), vec3(0.0));               // rest / normals not at this grid yet: never read OOB
		return;
	}
	vec4 r = own ? restAt(c) : vec4(0.0);
	vec4 st = R(R_STEP);
	bool reset = R(R_GRAV).w > 0.5 || textureSize(sTD2DInputs[0], 0) != ivec2(2 * gW, gH);
	if (reset) { if (own) store(c, r.xyz, vec3(0.0)); return; }
	vec3 P0 = own ? posAt(c) : vec3(0.0);
	vec3 V0 = own ? velAt(c) : vec3(0.0);
	if (st.w < 0.5) { if (own) store(c, P0, V0); return; }     // paused
	ivec2 H0 = T0 - 2;
	for (int idx = int(gl_LocalInvocationIndex); idx < 144; idx += 64) {
		ivec2 cc = H0 + ivec2(idx % 12, idx / 12);
		if (inside(cc)) {
			vec4 rc = restAt(cc);
			sX[idx] = predict(cc, rc);
			sW[idx] = weight(rc);
		}
	}
	barrier();
	if (!own) return;

	float wi = weight(r);
	ivec2 lc = c - H0;
	vec3 X = sX[lc.y * 12 + lc.x];
	vec3 Y = X;
	if (wi > 0.0) {
		vec4 al = R(R_COMP);
		vec3 corr = vec3(0.0);
		float cnt = 0.0;
		for (int k = 0; k < NSTENCIL; k++) {
			ivec3 s = STENCIL[k];
			ivec2 nc = c + s.xy;
			if (!inside(nc)) continue;
			int ni = (lc.y + s.y) * 12 + lc.x + s.x;
			float wn = sW[ni];
			vec3 d = X - sX[ni];
			float ln = length(d);
			float L = length(vec2(s.xy) * grid.zw);
			float den = wi + wn + (s.z == 0 ? al.x : (s.z == 1 ? al.y : al.z));
			if (ln > 1e-9 && den > 1e-12) {
				corr += wi * (-(ln - L) / den) * d / ln;
				cnt += 1.0;
			}
		}
		Y = X + al.w * corr / max(cnt, 1.0);

		vec4 th = R(R_TETH);                                     // tethers (long-range attachments) to the pins
		if (th.x > 0.5 && R(R_MASS).x < 0.5) {
			int pm = int(th.z + 0.5);
			if (pm == PIN_TOP) Y = tether(Y, r, ivec2(c.x, gH - 1), th.y);
			else if (pm == PIN_TOPCORNERS) {
				Y = tether(Y, r, ivec2(0, gH - 1), th.y);
				Y = tether(Y, r, ivec2(gW - 1, gH - 1), th.y);
			} else if (pm == PIN_CORNERS) {
				Y = tether(Y, r, ivec2(0, 0), th.y);
				Y = tether(Y, r, ivec2(gW - 1, 0), th.y);
				Y = tether(Y, r, ivec2(0, gH - 1), th.y);
				Y = tether(Y, r, ivec2(gW - 1, gH - 1), th.y);
			}
		}

		vec4 fl = R(R_FLOOR);                                    // collisions: spheres, floor, then friction
		bool contact = false;
		vec3 nrm = vec3(0.0);
		for (int k = 0; k < NSPHERES; k++) {
			vec4 sp = R(R_SPH0 + k);
			if (sp.w <= 0.0) continue;
			vec3 v = Y - sp.xyz;
			float dd = length(v);
			if (dd < sp.w + fl.w) {
				vec3 u = dd > 1e-9 ? v / dd : vec3(0.0, 1.0, 0.0);
				Y = sp.xyz + u * (sp.w + fl.w);
				nrm = u;
				contact = true;
			}
		}
		if (fl.x > 0.5 && Y.y < fl.y + fl.w) {
			Y.y = fl.y + fl.w;
			nrm = vec3(0.0, 1.0, 0.0);
			contact = true;
		}
		if (contact && fl.z > 0.0) {
			vec3 dP = Y - P0;
			Y -= min(fl.z, 1.0) * (dP - nrm * dot(dP, nrm));
		}
	}
	vec3 Vn = st.x > 0.0 ? (Y - P0) / st.x * st.z : vec3(0.0);
	store(c, Y, Vn);
}
