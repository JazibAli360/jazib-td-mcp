// px_lines_seg.glsl - PX lines pass, SEGMENT GENERATOR: ONE compute pass per frame (T-46/T-47). Mirrors
// px_lines_logic.ref_segments (float64 reference). Text = glsl_header() + px_palette.glsl + px_lines_common.glsl + this.
// Inputs: 0 = points (any rgba32f TOP, point id -> texel ((id % side) * stride, id / side), xyz = position; PX state:
// stride 5), 1 = trail history (px_lines_hist output, or a black 8x8 when Trails is off), 2 = polyline path (one row,
// texel i = xyz + w; w < 0 = pen up; CHOP to TOP of tx ty tz, or black).
// Output: segment texture rgba32f, width 4 * SEG_W, height ceil(Maxseg / SEG_W); segment s -> texels (4 (s % SEG_W) + k,
// s / SEG_W): T0 = A.xyz, uA   T1 = B.xyz, uB   T2 = rgb (HDR, x gain x mask), alpha   T3 = width mult, caps (bit 0
// start cap, bit 1 end cap), line id, source + 1 (0 = no segment). Ranges per source: rows RN0..RN2 (plan()).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uLineCs;      // W1-B colour source of the lines (mode, pos, spread, keep)

int plSide() { return max(textureSize(sTD2DInputs[0], 0).x / max(int(uL[R_G1].y + 0.5), 1), 1); }
int plAvail()
{
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	int n = plSide() * sz.y;
	int c = int(uL[R_G1].x + 0.5);
	return c > 0 ? min(c, n) : n;
}
vec3 plPoint(int id)
{
	int side = plSide();
	return texelFetch(sTD2DInputs[0], ivec2((id % side) * max(int(uL[R_G1].y + 0.5), 1), id / side), 0).xyz;
}
// first + count inside the available points -> (first, count)
ivec2 plRange(float first, float count)
{
	int av = plAvail();
	int f = clamp(int(first + 0.5), 0, av);
	int c = int(count + 0.5);
	c = c > 0 ? min(c, av - f) : av - f;
	return ivec2(f, max(c, 0));
}

void plStore(int s, vec4 a, vec4 b, vec4 c, vec4 d)
{
	ivec2 t = ivec2((s % SEG_W) * 4, s / SEG_W);
	if (t.y >= int(uTDOutputInfo.res.w)) return;                     // T-35: never store out of bounds
	TDImageStoreOutput(0, ivec3(t, 0), a);
	TDImageStoreOutput(0, ivec3(t + ivec2(1, 0), 0), b);
	TDImageStoreOutput(0, ivec3(t + ivec2(2, 0), 0), c);
	TDImageStoreOutput(0, ivec3(t + ivec2(3, 0), 0), d);
}
void plNone(int s) { plStore(s, vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0)); }

// attrT for the colour source: 0 along (u), 1 index (line id), 2 depth (Depthnear..far -> 0..1), 3 random per line
float plAttr(int mode, float u, float lid, vec3 m)
{
	if (mode == 1) return lid;
	if (mode == 2) return clamp((length(m - uL[R_G2].xyz) - uL[R_CL2].x) / max(uL[R_CL2].y - uL[R_CL2].x, 1e-6), 0.0, 1.0);
	if (mode == 3) return plH3(plU(lid), 7u, uint(uL[R_G1].z));
	return u;
}

void plEmit(int s, vec3 A, float ua, vec3 B, float ub, float lid, float attr, float gain, float wm, float caps,
            float src)
{
	vec3 m = 0.5 * (A + B);
	float a = gain * plMask(m);
	float fl = uL[R_ST1].w;
	if (fl > 0.0)
	{
		uint tick = uint(max(floor(uT.x * uL[R_ST2].w), 0.0));
		a *= 1.0 - fl * plH3(plU(lid), tick, uint(uL[R_G1].z) + 11u);
	}
	vec3 c = pxColSrc(uLineCs, uL[R_CL0].xyz, uL[R_CL0].xyz, plAttr(int(attr + 0.5), 0.5 * (ua + ub), lid, m));
	plStore(s, vec4(A, ua), vec4(B, ub), vec4(c * uL[R_G1].w, a), vec4(wm, caps, lid, src + 1.0));
}

// ---------------------------------------------------------------------------------------------------- rings (G1)
vec3 plRot(vec3 v, vec3 k, float a) { return v * cos(a) + cross(k, v) * sin(a) + k * dot(k, v) * (1.0 - cos(a)); }

void plRing(int s, int l)
{
	int nr = max(int(uL[R_RG0].x + 0.5), 1), ns = max(int(uL[R_RG0].y + 0.5), 3);
	int ci = min(l / (nr * ns), 3), k = (l / ns) % nr, j = l % ns;
	vec4 C = uL[R_RC0 + 2 * ci], N = uL[R_RC0 + 2 * ci + 1];
	float t = uT.x;
	vec3 n = length(N.xyz) > 1e-6 ? normalize(N.xyz) : vec3(0.0, 1.0, 0.0);
	vec3 e1 = normalize(cross(n, abs(n.y) < 0.99 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0)));
	vec3 e2 = cross(n, e1);
	if (uL[R_RG1].z != 0.0)
	{
		float phi = uL[R_RG1].w * t + float(k) * PL_PI / float(nr);
		vec3 q = cos(phi) * e1 + sin(phi) * e2;
		e1 = plRot(e1, q, uL[R_RG1].z);
		e2 = plRot(e2, q, uL[R_RG1].z);
	}
	float r, al = 1.0;
	if (uL[R_RG1].x != 0.0)
	{
		float e = fract(float(k) / float(nr) + uL[R_RG1].x * t);
		r = uL[R_RG0].z + e * float(nr) * uL[R_RG0].w;
		al = sin(PL_PI * e);
	}
	else r = uL[R_RG0].z + float(k) * uL[R_RG0].w;
	r *= C.w;
	float sp = uL[R_RG1].y * t;
	float a0 = PL_TAU * float(j) / float(ns) + sp, a1 = PL_TAU * float(j + 1) / float(ns) + sp;
	vec3 A = C.xyz + r * (cos(a0) * e1 + sin(a0) * e2);
	vec3 B = C.xyz + r * (cos(a1) * e1 + sin(a1) * e2);
	plEmit(s, A, float(j) / float(ns), B, float(j + 1) / float(ns), float(k + ci * nr), uL[R_RG2].x,
	       uL[R_RG2].y * al, 1.0, 1.0, 0.0);
}

// -------------------------------------------------------------------------------------------- contour / slices (G4)
void plContour(int s, int l, int n)
{
	ivec2 rg = plRange(uL[R_CT4].y, uL[R_CT4].z);
	if (rg.y <= 0) { plNone(s); return; }
	int id = rg.x + int(floor(float(l) * float(rg.y) / float(n)));
	vec3 P = plPoint(id);
	vec3 a = uL[R_CT0].xyz, o = uL[R_CT1].xyz;
	float sp = max(uL[R_CT0].w, 1e-6);
	vec3 e1 = normalize(cross(a, abs(a.y) < 0.99 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0)));
	vec3 e2 = cross(a, e1);
	vec3 r = P - o;
	vec3 T = cross(a, uL[R_CT3].z > 0.5 ? P - uL[R_G2].xyz : r);
	T = length(T) > 1e-9 ? normalize(T) : e1;
	float q = uL[R_CT3].z > 0.5 ? dot(r, e1) : atan(dot(r, e2), dot(r, e1)) / PL_TAU + 0.5;
	float h = dot(r, a) - uL[R_CT2].w * sin(PL_TAU * (uL[R_CT3].x * q + uL[R_CT3].y * uT.x));
	float ph = h / sp - uL[R_CT2].z * uT.x;
	float bi = floor(ph + 0.5);
	float d = (ph - bi) * sp;
	if (abs(d) > 0.5 * uL[R_CT1].w) { plNone(s); return; }
	vec3 C = P - a * d * uL[R_CT2].y;
	float hl = 0.5 * uL[R_CT2].x;
	plEmit(s, C - T * hl, q, C + T * hl, q, bi, uL[R_CT3].w, uL[R_CT4].x, 1.0, 3.0, 1.0);
}

// ------------------------------------------------------------------------------------- trails / ribbons (G3, G5)
// History layout (px_lines_hist.glsl): width samples + 2, row = track; col 0 = head P + age, col 1 = life id, life,
// reset n; col 2 + i = slot i: P, life id + 1 (0 = never written). Newest slot h = floor(frame / every) % samples.
vec3 plJit(int tr, int slot)
{
	float J = uL[R_TR3].w;
	if (J == 0.0) return vec3(0.0);
	uint tick = uint(max(floor(uT.x * uL[R_TR4].w), 0.0));
	uint a = uint(tr) * 977u + uint(slot);
	return J * (vec3(plH3(a, tick, 1u), plH3(a, tick, 2u), plH3(a, tick, 3u)) * 2.0 - 1.0);
}
void plTrail(int s, int l)
{
	int ns = max(int(uL[R_TR0].y + 0.5), 2);
	int tr = l / ns, j = l % ns;
	int ev = max(int(uL[R_TR0].z + 0.5), 1);
	int h = (int(uT.y + 0.5) / ev) % ns;
	vec4 A, B;
	int sa = (h - j + 1 + ns) % ns, sb = (h - j + ns) % ns;
	if (j == 0)
	{
		A = texelFetch(sTD2DInputs[1], ivec2(0, tr), 0);
		A.w = texelFetch(sTD2DInputs[1], ivec2(1, tr), 0).x + 1.0;
	}
	else
	{
		A = texelFetch(sTD2DInputs[1], ivec2(2 + sa, tr), 0);
		A.xyz += plJit(tr, sa);
	}
	B = texelFetch(sTD2DInputs[1], ivec2(2 + sb, tr), 0);
	B.xyz += plJit(tr, sb);
	if (A.w < 0.5 || B.w < 0.5 || abs(A.w - B.w) > 0.25) { plNone(s); return; }
	float ua = float(j) / float(ns), ub = float(j + 1) / float(ns), um = 0.5 * (ua + ub);
	float wm = pow(max(1.0 - um, 0.0), uL[R_TR6].z);
	float fd = pow(max(1.0 - um, 0.0), uL[R_TR6].w);
	plEmit(s, A.xyz, ua, B.xyz, ub, float(tr), uL[R_TR6].x, uL[R_TR6].y * fd, wm, 1.0, 2.0);
}

// ----------------------------------------------------------------------------- connect / plexus / lightning (G5)
// The first thread of each selected point does the brute-force search over the selected set (np^2) and writes all
// k * sub segments of that point; the other threads of the block return. Pieces of a pair are generated from the
// lower id's end, so i -> j and j -> i draw the same zigzag.
// Wave 4 (SA33, whole cloud): sample -> its K nearest voxel representatives (cn_index, input 3) among the 27 voxels
// around the sample's REST position (index points, input 4, stride CN4.z). Search + distances in rest space (static
// topology), drawn at the live positions (input 0). Mirror: px_lines_logic.ref_segments (index_points).
#if defined(TD_NUM_2D_INPUTS) && TD_NUM_2D_INPUTS > 4
vec3 plRest(int id)
{
	int st = max(int(uL[R_CN4].z + 0.5), 1);
	int side = max(textureSize(sTD2DInputs[4], 0).x / st, 1);
	return texelFetch(sTD2DInputs[4], ivec2((id % side) * st, id / side), 0).xyz;
}
void plConnectGrid(int s, int l, int np, int K, int sub, int per)
{
	int pi = l / per;
	ivec2 rg = plRange(uL[R_CN1].z, uL[R_CN1].w);
	if (rg.y <= 0) { for (int m = 0; m < per; m++) plNone(s + m); return; }
	float R = max(uL[R_CN0].z, 1e-6);
	int id = rg.x + int(floor(float(pi) * float(rg.y) / float(np)));
	vec3 Ri = plRest(id);
	int N = int(uL[R_CN4].x + 0.5), tx = max(int(uL[R_CN4].y + 0.5), 1);
	ivec3 v0 = ivec3(floor((Ri - uL[R_CN3].xyz) / max(uL[R_CN3].w, 1e-9)));
	float bd[4] = float[4](1e30, 1e30, 1e30, 1e30);
	int bj[4] = int[4](-1, -1, -1, -1);
	for (int c = 0; c < 27; c++)
	{
		ivec3 v = v0 + ivec3(c % 3 - 1, (c / 3) % 3 - 1, c / 9 - 1);
		if (any(lessThan(v, ivec3(0))) || any(greaterThanEqual(v, ivec3(N)))) continue;
		vec4 e = texelFetch(sTD2DInputs[3], ivec2(v.x + (v.z % tx) * N, v.y + (v.z / tx) * N), 0);
		if (e.w < 0.5) continue;
		int q = int(e.w + 0.5) - 1;
		if (q == id) continue;
		float d = length(e.xyz - Ri);
		if (d >= R || d >= bd[K - 1]) continue;
		int m = K - 1;
		while (m > 0 && bd[m - 1] > d) { bd[m] = bd[m - 1]; bj[m] = bj[m - 1]; m--; }
		bd[m] = d;
		bj[m] = q;
	}
	uint tick = uint(max(floor(uT.x * uL[R_CN1].y), 0.0));
	for (int m = 0; m < K; m++)
	{
		int q = bj[m];
		if (q < 0) { for (int k = 0; k < sub; k++) plNone(s + m * sub + k); continue; }
		int lo = min(id, q), hi = max(id, q);
		vec3 P0 = plPoint(lo), P1 = plPoint(hi);
		uint key = plPcg(uint(lo)) ^ uint(hi);
		float fall = (1.0 - bd[m] / R) * (1.0 - bd[m] / R);
		vec3 X0 = P0;
		for (int k = 0; k < sub; k++)
		{
			float f1 = float(k + 1) / float(sub);
			vec3 X1 = mix(P0, P1, f1);
			if (k + 1 < sub)
				X1 += uL[R_CN1].x * sin(PL_PI * f1) *
				      (vec3(plH3(key, uint(k + 1), tick), plH3(key, uint(k + 1), tick + 7919u),
				            plH3(key, uint(k + 1), tick + 15838u)) * 2.0 - 1.0);
			plEmit(s + m * sub + k, X0, float(k) / float(sub), X1, f1, float(lo), uL[R_CN2].x,
			       uL[R_CN2].y * fall, 1.0, 1.0, 3.0);
			X0 = X1;
		}
	}
}
#endif

void plConnect(int s, int l)
{
	int np = max(int(uL[R_CN0].x + 0.5), 1), K = clamp(int(uL[R_CN0].y + 0.5), 1, 4);
	int sub = clamp(int(uL[R_CN0].w + 0.5), 1, 8), per = K * sub;
	if (l % per != 0) return;
	if (uL[R_CN2].z > 0.5)
	{
#if defined(TD_NUM_2D_INPUTS) && TD_NUM_2D_INPUTS > 4
		plConnectGrid(s, l, np, K, sub, per);
#else
		for (int m = 0; m < per; m++) plNone(s + m);
#endif
		return;
	}
	np = min(np, 4096);                       // brute force: n^2 per frame, never past 4096 (GPU hang guard)
	int pi = l / per;
	ivec2 rg = plRange(uL[R_CN1].z, uL[R_CN1].w);
	if (rg.y <= 0) { for (int m = 0; m < per; m++) plNone(s + m); return; }
	float R = max(uL[R_CN0].z, 1e-6);
	vec3 Pi = plPoint(rg.x + int(floor(float(pi) * float(rg.y) / float(np))));
	float bd[4] = float[4](1e30, 1e30, 1e30, 1e30);
	int bj[4] = int[4](-1, -1, -1, -1);
	for (int q = 0; q < np; q++)
	{
		if (q == pi) continue;
		float d = length(plPoint(rg.x + int(floor(float(q) * float(rg.y) / float(np)))) - Pi);
		if (d >= R || d >= bd[K - 1]) continue;
		int m = K - 1;
		while (m > 0 && bd[m - 1] > d) { bd[m] = bd[m - 1]; bj[m] = bj[m - 1]; m--; }
		bd[m] = d;
		bj[m] = q;
	}
	uint tick = uint(max(floor(uT.x * uL[R_CN1].y), 0.0));
	for (int m = 0; m < K; m++)
	{
		int q = bj[m];
		if (q < 0) { for (int k = 0; k < sub; k++) plNone(s + m * sub + k); continue; }
		int lo = min(pi, q), hi = max(pi, q);
		vec3 P0 = plPoint(rg.x + int(floor(float(lo) * float(rg.y) / float(np))));
		vec3 P1 = plPoint(rg.x + int(floor(float(hi) * float(rg.y) / float(np))));
		uint key = plPcg(uint(lo)) ^ uint(hi);
		float fall = (1.0 - bd[m] / R) * (1.0 - bd[m] / R);
		vec3 X0 = P0;
		for (int k = 0; k < sub; k++)
		{
			float f1 = float(k + 1) / float(sub);
			vec3 X1 = mix(P0, P1, f1);
			if (k + 1 < sub)
				X1 += uL[R_CN1].x * sin(PL_PI * f1) *
				      (vec3(plH3(key, uint(k + 1), tick), plH3(key, uint(k + 1), tick + 7919u),
				            plH3(key, uint(k + 1), tick + 15838u)) * 2.0 - 1.0);
			plEmit(s + m * sub + k, X0, float(k) / float(sub), X1, f1, float(lo), uL[R_CN2].x,
			       uL[R_CN2].y * fall, 1.0, 1.0, 3.0);
			X0 = X1;
		}
	}
}

// -------------------------------------------------------------------------- polyline / logo / typography (G6)
void plPoly(int s, int l)
{
	int N = int(uL[R_PO0].x + 0.5);
	bool cl = uL[R_PO0].y > 0.5 && N > 2;
	int i0 = l, i1 = l + 1;
	if (i1 >= N) { if (cl && i0 == N - 1) i1 = 0; else { plNone(s); return; } }
	vec4 a = texelFetch(sTD2DInputs[2], ivec2(i0, 0), 0), b = texelFetch(sTD2DInputs[2], ivec2(i1, 0), 0);
	if (a.w < 0.0 || b.w < 0.0) { plNone(s); return; }
	vec3 A = vec3(dot(uL[R_PM0], vec4(a.xyz, 1.0)), dot(uL[R_PM1], vec4(a.xyz, 1.0)), dot(uL[R_PM2], vec4(a.xyz, 1.0)));
	vec3 B = vec3(dot(uL[R_PM0], vec4(b.xyz, 1.0)), dot(uL[R_PM1], vec4(b.xyz, 1.0)), dot(uL[R_PM2], vec4(b.xyz, 1.0)));
	if (uL[R_PO0].z > 0.0 && length(B - A) > uL[R_PO0].z) { plNone(s); return; }
	float den = float(max(cl ? N : N - 1, 1));
	plEmit(s, A, float(i0) / den, B, float(i0 + 1) / den, 0.0, uL[R_PO0].w, uL[R_PO1].x, 1.0, 1.0, 4.0);
}

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	if (g.x >= SEG_W) return;
	int s = g.y * SEG_W + g.x;
	if (g.y >= int(uTDOutputInfo.res.w)) return;
	if (s >= int(uL[R_G0].z + 0.5)) { plNone(s); return; }
	if (s >= int(uL[R_RN0].x + 0.5) && s < int(uL[R_RN0].x + uL[R_RN0].y + 0.5)) { plRing(s, s - int(uL[R_RN0].x + 0.5)); return; }
	if (s >= int(uL[R_RN0].z + 0.5) && s < int(uL[R_RN0].z + uL[R_RN0].w + 0.5))
	{ plContour(s, s - int(uL[R_RN0].z + 0.5), int(uL[R_RN0].w + 0.5)); return; }
	if (s >= int(uL[R_RN1].x + 0.5) && s < int(uL[R_RN1].x + uL[R_RN1].y + 0.5)) { plTrail(s, s - int(uL[R_RN1].x + 0.5)); return; }
	if (s >= int(uL[R_RN1].z + 0.5) && s < int(uL[R_RN1].z + uL[R_RN1].w + 0.5)) { plConnect(s, s - int(uL[R_RN1].z + 0.5)); return; }
	if (s >= int(uL[R_RN2].x + 0.5) && s < int(uL[R_RN2].x + uL[R_RN2].y + 0.5)) { plPoly(s, s - int(uL[R_RN2].x + 0.5)); return; }
	plNone(s);
}
