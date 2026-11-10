// PX_pointfx SOURCE stage: ONE compute pass that writes the rest texture (4 texels per point, rgba32float, width
// 4*side): R0 = p0 xyz, valid   R1 = colour rgba   R2 = splat scale xyz (0 = none: plain points), 0   R3 = quat wxyz.
// Scene ids [0, NSCENE): two sides A and B, each: 0 file (input 0 = rest_files: A rows 0..side-1, B rows
// side..2 side-1, same 4-texel layout), 1 generator (analytic, by id), 2 depth (input 2: rgb colour, a nearness 0..1,
// unprojected on a side x side grid), 3 off (B only). Morph A -> B per point: u = clamp(M (1 + st) - st * delay),
// eased, + curl arc. Actor ids [NSCENE, NSCENE + NACTOR) (A4): file / sequence frame (input 1 = rest_actor, its own
// side), generator or depth, with its own transform (+ the followed effector's position). Pool ids (the rest):
// embers parked at the bounds centre until prox_burn spawns them. Mirrors px_logic.ref_gen / ref_unproject.
// //@DECL = uniform decls + px_common.glsl (codegen.source_text).
layout (local_size_x = 8, local_size_y = 8) in;
#define PX_STATE_TEX(t) vec4(0.0)
#define PX_STATE_SIZE ivec2(0)
//@DECL
uniform vec4 uSrc[18];   // rows: px_logic.source_rows()

// Generators (kind: px_logic.GENERATORS order). prm = (p1 size, p2, p3, spin angle rad). n = count.
vec3 pxGen(int kind, uint id, int n, vec4 prm)
{
	float fi = float(id);
	float fn = float(max(n, 1));
	float s = prm.x;
	vec3 p;
	if (kind == 1) {                                                     // grid cube
		int k = int(ceil(pow(fn, 1.0 / 3.0) - 1e-3));
		if (k * k * k < n) k++;
		k = max(k, 1);
		int ii = int(id);
		vec3 c = vec3(float(ii % k), float((ii / k) % k), float(ii / (k * k)));
		p = ((c + 0.5) / float(k) * 2.0 - 1.0) * s;
	} else if (kind == 2) {                                              // torus R = p1, r = p2
		float a = PX_TAU * pxWeyl(id, 2654435769u);
		float b = PX_TAU * pxWeyl(id, 3242174889u);
		p = vec3((s + prm.y * cos(b)) * cos(a), prm.y * sin(b), (s + prm.y * cos(b)) * sin(a));
	} else if (kind == 3) {                                              // plane (xy, facing the camera)
		int k = max(int(ceil(sqrt(fn) - 1e-3)), 1);
		if (k * k < n) k++;
		int ii = int(id);
		p = vec3((float(ii % k) + 0.5) / float(k) * 2.0 - 1.0, (float(ii / k) + 0.5) / float(k) * 2.0 - 1.0, 0.0) * s;
	} else if (kind == 4) {                                              // cube surface
		float u = pxWeyl(id, 2654435769u) * 2.0 - 1.0;
		float w = pxWeyl(id, 3242174889u) * 2.0 - 1.0;
		int f = int(id % 6u);
		float sg = (f % 2 == 0) ? 1.0 : -1.0;
		p = (f < 2) ? vec3(sg, u, w) : ((f < 4) ? vec3(u, sg, w) : vec3(u, w, sg));
		p *= s;
	} else if (kind == 5) {                                              // helix, p2 turns, p3 jitter
		float t = (fi + 0.5) / fn;
		float a = t * PX_TAU * prm.y;
		p = vec3(0.5 * s * cos(a), (t * 2.0 - 1.0) * s, 0.5 * s * sin(a)) + (pxRnd3(id, 201u) - 0.5) * prm.z;
	} else if (kind == 6) {                                              // ring, p2 thickness
		float a = PX_TAU * pxWeyl(id, 2654435769u);
		float r = s + (pxRnd(id, 211u) - 0.5) * prm.y;
		p = vec3(r * cos(a), (pxRnd(id, 212u) - 0.5) * prm.y * 0.5, r * sin(a));
	} else if (kind == 7) {                                              // spiral galaxy, p2 winding
		float arm = float(id % 3u);
		float r = pow(pxWeyl(id, 3242174889u), 0.7) * s;
		float a = r * prm.y / max(s, 1e-5) + arm * PX_TAU / 3.0 + (pxRnd(id, 221u) - 0.5) * 0.4;
		p = vec3(r * cos(a), (pxRnd(id, 222u) - 0.5) * 0.08 * (1.2 - r / max(s, 1e-5)) * s, r * sin(a));
	} else if (kind == 8) {                                              // cylinder
		float a = PX_TAU * pxWeyl(id, 2654435769u);
		p = vec3(0.5 * s * cos(a), ((fi + 0.5) / fn * 2.0 - 1.0) * s, 0.5 * s * sin(a));
	} else if (kind == 9) {                                              // ball (uniform volume)
		float z = 2.0 * pxRnd(id, 231u) - 1.0;
		float ph = PX_TAU * pxRnd(id, 232u);
		float rr = sqrt(max(0.0, 1.0 - z * z));
		p = vec3(rr * cos(ph), rr * sin(ph), z) * pow(pxRnd(id, 233u), 1.0 / 3.0) * s;
	} else {                                                             // 0 sphere (Fibonacci / Weyl)
		float y = 1.0 - 2.0 * (fi + 0.5) / fn;
		float r = sqrt(max(0.0, 1.0 - y * y));
		float a = PX_TAU * pxWeyl(id, 2654435769u);
		p = vec3(r * cos(a), y, r * sin(a)) * s;
	}
	float ca = cos(prm.w), sa = sin(prm.w);
	return vec3(ca * p.x + sa * p.z, p.y, -sa * p.x + ca * p.z);         // spin about y
}

void pxSide(int which, int mode, uint id, int n, ivec2 g, int side, out vec3 p, out vec4 c, out vec3 sc, out vec4 qt, out bool ok)
{
	p = vec3(0.0);
	c = vec4(1.0);
	sc = vec3(1.0);
	qt = vec4(1.0, 0.0, 0.0, 0.0);
	ok = false;
	vec4 sr = uSrc[3];
	float scale = which == 0 ? sr.x : sr.y;
	float rot = which == 0 ? sr.z : sr.w;
	vec4 offs = uSrc[4 + which];
	if (mode == 0) {
		ivec2 t0 = ivec2(g.x * 4, g.y + which * side);                // rest_files: B sits below A
		ivec2 sz = textureSize(sTD2DInputs[0], 0);
		if (sz.x < t0.x + 4 || sz.y <= t0.y) return;
		vec4 a = texelFetch(sTD2DInputs[0], t0, 0);
		c = texelFetch(sTD2DInputs[0], t0 + ivec2(1, 0), 0);
		vec4 b = texelFetch(sTD2DInputs[0], t0 + ivec2(2, 0), 0);
		qt = texelFetch(sTD2DInputs[0], t0 + ivec2(3, 0), 0);
		p = a.xyz;
		sc = b.xyz;
		ok = a.w > 0.5;
	} else if (mode == 1) {
		vec4 prm = uSrc[8 + which];
		p = pxGen(pxI(which == 0 ? uSrc[1].x : uSrc[1].y), id, n, prm);
		int cm = pxI(offs.w);
		vec3 rgb = uSrc[10 + which].rgb;
		c = vec4(cm == 1 ? rgb : (cm == 2 ? vec3(1.0) : clamp(p / max(prm.x, 1e-5) * 0.5 + 0.5, 0.0, 1.0)), 1.0);
		sc = vec3(0.0);
		ok = true;
	} else if (mode == 2) {
		vec4 d6 = uSrc[6];
		vec4 d7 = uSrc[7];
		vec2 uv = (vec2(g) + 0.5) / float(side);
		vec4 t = texture(sTD2DInputs[2], uv);
		float nr = t.a;
		float z = mix(d6.z, d6.y, nr);
		float th = tan(radians(d6.x) * 0.5);
		vec2 xy = (uv * 2.0 - 1.0) * th * vec2(d7.x, 1.0) * z;
		if (d7.z > 0.5) xy.x = -xy.x;
		p = vec3(xy, -z + 0.5 * (d6.y + d6.z)) * d7.y;
		c = vec4(t.rgb * d7.w, 1.0);
		sc = vec3(0.0);
		ok = nr > d6.w;
	} else if (mode == 4) {                                              // wave 3 K19 / K28: any TOP of points
		ivec2 sz = textureSize(sTD2DInputs[2], 0);                    // (input 2 = Pointstop / in_xyz): rgb xyz,
		int k = int(id);                                               // a > 0.5 valid, point k = texel k
		if (k >= sz.x * sz.y) return;
		vec4 a = texelFetch(sTD2DInputs[2], ivec2(k % sz.x, k / sz.x), 0);
		p = a.xyz;
		int cm = pxI(offs.w);
		vec3 rgb = uSrc[10 + which].rgb;
		c = vec4(cm == 1 ? rgb : (cm == 2 ? vec3(1.0) : clamp(p * 0.5 + 0.5, 0.0, 1.0)), 1.0);
		sc = vec3(0.0);
		ok = a.w > 0.5;
	} else if (mode == 5) {                                              // wave 4 K27: image relief (input 2 =
		vec4 im = uSrc[17];                                            // the picture): x y = the image (2 units
		vec2 uv = (vec2(g) + 0.5) / float(side);                       // tall, its aspect = uSrc[7].x), z = relief
		vec4 t = texture(sTD2DInputs[2], uv);                          // x height source; colour = the pixel
		int hs = pxI(im.y);
		float mx = max(t.r, max(t.g, t.b)), mn = min(t.r, min(t.g, t.b)), dd = mx - mn;
		float hue = dd < 1e-6 ? 0.0 : (mx == t.r ? mod((t.g - t.b) / dd, 6.0) : (mx == t.g ? (t.b - t.r) / dd + 2.0
		            : (t.r - t.g) / dd + 4.0)) / 6.0;
		float h = hs == 1 ? hue : (hs == 2 ? t.a : (hs == 3 ? t.r : dot(t.rgb, vec3(0.2126, 0.7152, 0.0722))));
		p = vec3((uv.x * 2.0 - 1.0) * uSrc[7].x, uv.y * 2.0 - 1.0, h * im.x);
		c = vec4(t.rgb * uSrc[7].w, 1.0);
		sc = vec3(0.0);
		ok = h >= im.z && t.a > 0.0;
	} else {
		return;
	}
	float ca = cos(rot), sa = sin(rot);
	p *= scale;
	p = vec3(ca * p.x + sa * p.z, p.y, -sa * p.x + ca * p.z) + offs.xyz;
	sc *= abs(scale);
}

// Actor layer point k (0..NACTOR-1): uSrc[12] (mode 1 file / 2 gen / 3 depth, generator, count, side_a),
// [13] gen params + spin, [14] (scale, rotate y, -, colour mode), [15] offset (+ followed effector), [16] colour.
void pxActor(int k, out vec3 p, out vec4 c, out vec3 sc, out vec4 qt, out bool ok)
{
	p = vec3(0.0);
	c = vec4(uSrc[16].rgb, 1.0);
	sc = vec3(0.0);
	qt = vec4(1.0, 0.0, 0.0, 0.0);
	ok = false;
	int md = pxI(uSrc[12].x);
	int na = max(pxI(uSrc[12].z), 1);
	int sa_ = max(pxI(uSrc[12].w), 1);
	if (md == 4) {                                                       // wave 3 K19: actor from a TOP of points
		ivec2 sz = textureSize(sTD2DInputs[2], 0);
		if (k < sz.x * sz.y) {
			vec4 a = texelFetch(sTD2DInputs[2], ivec2(k % sz.x, k / sz.x), 0);
			p = a.xyz;
			if (pxI(uSrc[14].w) == 0) c = vec4(clamp(p * 0.5 + 0.5, 0.0, 1.0), 1.0);
			ok = a.w > 0.5;
		}
	} else if (md == 1) {
		ivec2 t0 = ivec2((k % sa_) * 4, k / sa_);
		ivec2 sz = textureSize(sTD2DInputs[1], 0);
		if (sz.x < t0.x + 4 || sz.y <= t0.y) return;
		vec4 a = texelFetch(sTD2DInputs[1], t0, 0);
		vec4 cc = texelFetch(sTD2DInputs[1], t0 + ivec2(1, 0), 0);
		sc = texelFetch(sTD2DInputs[1], t0 + ivec2(2, 0), 0).xyz;
		qt = texelFetch(sTD2DInputs[1], t0 + ivec2(3, 0), 0);
		p = a.xyz;
		if (pxI(uSrc[14].w) == 0) c = cc;                              // position mode = the file's own colours
		ok = a.w > 0.5;
	} else if (md == 2) {
		vec4 prm = uSrc[13];
		p = pxGen(pxI(uSrc[12].y), uint(k), na, prm);
		if (pxI(uSrc[14].w) == 0) c = vec4(clamp(p / max(prm.x, 1e-5) * 0.5 + 0.5, 0.0, 1.0), 1.0);
		ok = true;
	} else if (md == 3) {
		vec4 d6 = uSrc[6];
		vec4 d7 = uSrc[7];
		vec2 uv = (vec2(float(k % sa_), float(k / sa_)) + 0.5) / float(sa_);
		vec4 t = texture(sTD2DInputs[2], uv);
		float z = mix(d6.z, d6.y, t.a);
		float th = tan(radians(d6.x) * 0.5);
		vec2 xy = (uv * 2.0 - 1.0) * th * vec2(d7.x, 1.0) * z;
		if (d7.z > 0.5) xy.x = -xy.x;
		p = vec3(xy, -z + 0.5 * (d6.y + d6.z)) * d7.y;
		if (pxI(uSrc[14].w) == 0) c = vec4(t.rgb * d7.w, 1.0);
		ok = t.a > d6.w;
	}
	if (pxI(uSrc[14].w) == 2) c = vec4(1.0);
	float rot = uSrc[14].y;
	float scale = uSrc[14].x;
	float ca = cos(rot), sa = sin(rot);
	p *= scale;
	p = vec3(ca * p.x + sa * p.z, p.y, -sa * p.x + ca * p.z) + uSrc[15].xyz;
	sc *= abs(scale);
}

float pxEase(float u, int k)
{
	u = clamp(u, 0.0, 1.0);
	if (k == 1) return u * u * (3.0 - 2.0 * u);
	if (k == 2) return 0.5 - 0.5 * cos(PX_PI * u);
	if (k == 3) return u < 0.5 ? 4.0 * u * u * u : 1.0 - pow(-2.0 * u + 2.0, 3.0) * 0.5;
	return u;
}

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	int side = max(pxI(uSrc[0].w), 1);
	if (g.x >= side || g.y >= side) return;
	uint id = uint(g.y * side + g.x);
	int n = max(pxI(uSrc[1].z), 0);
	ivec2 t0 = ivec2(g.x * 4, g.y);
	ivec2 osz = ivec2(uTDOutputInfo.res.zw);                          // T-35: never store out of bounds
	if (t0.x + 3 >= osz.x || t0.y >= osz.y) return;
	if (id >= uint(n)) {
		for (int k = 0; k < 4; k++) TDImageStoreOutput(0, ivec3(t0 + ivec2(k, 0), 0), vec4(0.0));
		return;
	}
	int ns = pxI(NSCENE);
	int na = pxI(NACTOR);
	if (int(id) >= ns) {
		vec3 p = uG[7].xyz;                                           // pool: parked at the bounds centre (embers)
		vec4 c = vec4(1.0, 0.45, 0.1, 1.0);
		vec3 sc = vec3(0.0);
		vec4 qt = vec4(1.0, 0.0, 0.0, 0.0);
		bool ok = true;
		if (int(id) < ns + na) pxActor(int(id) - ns, p, c, sc, qt, ok);
		TDImageStoreOutput(0, ivec3(t0, 0), vec4(p, ok ? 1.0 : 0.0));
		TDImageStoreOutput(0, ivec3(t0 + ivec2(1, 0), 0), c);
		TDImageStoreOutput(0, ivec3(t0 + ivec2(2, 0), 0), vec4(sc, 0.0));
		TDImageStoreOutput(0, ivec3(t0 + ivec2(3, 0), 0), qt);
		return;
	}
	n = max(ns, 1);                                                   // generators spread over the scene ids only
	vec3 pa, pb, sa, sb;
	vec4 ca, cb, qa, qb;
	bool oka, okb;
	pxSide(0, pxI(uSrc[0].x), id, n, g, side, pa, ca, sa, qa, oka);
	float m = uSrc[0].z;
	int mb = pxI(uSrc[0].y);
	vec3 p = pa, sc = sa;
	vec4 c = ca, qt = qa;
	bool ok = oka;
	if (mb <= 2 && m > 0.0) {
		pxSide(1, mb, id, n, g, side, pb, cb, sb, qb, okb);
		float st = max(uSrc[2].x, 0.0);
		int sm = pxI(uSrc[2].y);
		float delay = sm == 1 ? clamp(length(pa - uG[7].xyz) / max(uG[7].w, 1e-5), 0.0, 1.0)
		            : (sm == 2 ? clamp((pa.y - uG[7].y) / max(2.0 * uG[7].w, 1e-5) + 0.5, 0.0, 1.0)
		            : (sm == 3 ? 0.0 : pxRnd(id, 241u)));
		float e = pxEase(m * (1.0 + st) - st * delay, pxI(uSrc[2].w));
		p = mix(pa, pb, e);
		p += pxCurl(p * 1.3, 0.0, 1) * (uSrc[2].z * sin(PX_PI * e));
		c = mix(ca, cb, e);
		sc = mix(sa, sb, e);
		qt = e < 0.5 ? qa : qb;
		ok = e < 0.5 ? oka : okb;
	}
	TDImageStoreOutput(0, ivec3(t0, 0), vec4(p, ok ? 1.0 : 0.0));
	TDImageStoreOutput(0, ivec3(t0 + ivec2(1, 0), 0), c);
	TDImageStoreOutput(0, ivec3(t0 + ivec2(2, 0), 0), vec4(sc, 0.0));
	TDImageStoreOutput(0, ivec3(t0 + ivec2(3, 0), 0), qt);
}
