// splat_render: Gaussian splat GLSL MAT (vertex + pixel in one DAT). Clean-room from the 3DGS maths
// (docs/research/BL_gaussian_splats_pointclouds.md section 2). One quad (-1..1) per instance.
// Instance custom attribs: 0 = P, 1 = linear scale + stable id, 2 = rot (w,x,y,z), 3 = colour (SH0) + alpha,
// 4/5/6 = SH degree-1 coefficients of r/g/b (c1, c2, c3; INRIA order: c1 ~ -y, c2 ~ z, c3 ~ -x).
uniform vec4 uRes;     // render width, height, use order texture (cpu sort), splat count
uniform vec4 uP1;      // scale mult, opacity gain, alpha threshold, low-pass (px^2)
uniform vec4 uP2;      // point mix, point size (radius px), brightness, gamma
uniform vec4 uP3;      // dissolve, dissolve seed, noise amp, noise freq
uniform vec4 uP4;      // noise phase (time), explode, reveal, sRGB->linear
uniform vec4 uP5;      // target xyz (explode centre), SH degree
uniform vec4 uP6;      // reveal near distance, reveal far distance, 0, 0
uniform sampler2D sOrder;   // r = splat index in draw order (cpu sort), 4096 wide

// Hooks (empty here, so BL_splat_render compiles to the same code): PX_pointfx prepends an adapter that defines them
// to reuse this renderer on its own state textures (builders/glsl/px_splat_adapter.glsl, docs/builds/px.md S1-S6).
#ifndef SPLAT_VERTEX_EXTRA
#define SPLAT_VERTEX_EXTRA
#endif
#ifndef SPLAT_HOOK_T
#define SPLAT_HOOK_T(t0, t1, idx)
#endif
#ifndef SPLAT_HOOK_COV
#define SPLAT_HOOK_COV(a, b, c, alpha, z, idx)
#endif
#ifndef SPLAT_HOOK_OUT
#define SPLAT_HOOK_OUT(idx)
#endif
#ifndef SPLAT_HOOK_PIX
#define SPLAT_HOOK_PIX(power, a)
#endif
// Geometry-in-the-scene hooks (W1-E, docs/builds/px_geo.md): BL_splat_render's Geo page puts
// builders/glsl/splat_geo_adapter.glsl in front only when Geoon is set. Called WITHOUT a trailing ';' so the
// empty defaults add no token at all (BL's preprocessed text stays identical, test/test_px_geo.py).
#ifndef SPLAT_HOOK_CLIP
#define SPLAT_HOOK_CLIP(clip, vc, z)
#endif
#ifndef SPLAT_HOOK_LIGHT
#define SPLAT_HOOK_LIGHT(rgb, p, q, s, idx)
#endif

#ifdef TD_VERTEX_SHADER
out Vertex {
	vec4 color;
	vec2 d;        // pixel offset from the splat centre (u right, v up)
	vec3 conic;
	SPLAT_VERTEX_EXTRA
} oV;
#else
in Vertex {
	vec4 color;
	vec2 d;
	vec3 conic;
	SPLAT_VERTEX_EXTRA
} iV;
#endif

#ifdef TD_VERTEX_SHADER
float hash11(float n) { return fract(sin(n * 12.9898 + 78.233) * 43758.5453); }

void cull() { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); oV.color = vec4(0.0); oV.d = vec2(0.0); oV.conic = vec3(0.0); }

void main()
{
	int n = max(int(uRes.w), 1);
	int idx = TDInstanceID();
	if (uRes.z > 0.5) {
		ivec2 sz = textureSize(sOrder, 0);
		int ci = clamp(idx, 0, n - 1);
		ivec2 tc = ivec2(ci % 4096, ci / 4096);
		tc = clamp(tc, ivec2(0), sz - ivec2(1));                       // T-35: every fetch clamped
		idx = clamp(int(texelFetch(sOrder, tc, 0).r + 0.5), 0, n - 1);
	}
	vec4 col = TDInstanceCustomAttrib3(idx);
	vec4 sc = TDInstanceCustomAttrib1(idx);
	float alpha = min(col.a * uP1.y, 0.99);
	if (uP3.x > 0.0) alpha *= clamp((hash11(sc.w + uP3.y * 1013.0) - uP3.x) * 20.0 + 1.0, 0.0, 1.0);
	float thr = max(uP1.z, 1.0 / 255.0);
	if (alpha <= thr) { cull(); return; }

	vec3 p = TDInstanceCustomAttrib0(idx).xyz;
	if (uP4.y != 0.0) p += (p - uP5.xyz) * uP4.y;
	if (uP3.z != 0.0) {
		vec3 q = p * uP3.w;
		p += uP3.z * vec3(TDSimplexNoise(vec4(q, uP4.x)), TDSimplexNoise(vec4(q + 17.13, uP4.x)),
		                 TDSimplexNoise(vec4(q + 41.71, uP4.x)));
	}

#ifdef PXE_HOOK
	PXEFx efx = pxePointFx(p, sc.w);       // shared effectors: push / dissolve / grow (builders/effectors.py attach)
	p += efx.off;
	alpha *= efx.alpha;
	if (alpha <= thr) { cull(); return; }
#endif
	int ci = TDCameraIndex();
	mat4 V = uTDMats[ci].cam;
	mat4 Pm = uTDMats[ci].proj;
	vec4 vc = V * vec4(p, 1.0);
	float z = -vc.z;
	if (z <= 0.01) { cull(); return; }
	if (uP4.z < 1.0) {
		float rr = (z - uP6.x) / max(uP6.y - uP6.x, 1e-6);
		alpha *= clamp((uP4.z - rr) / 0.05, 0.0, 1.0);
		if (alpha <= thr) { cull(); return; }
	}

	float fx = abs(Pm[0][0]) * 0.5 * uRes.x;
	float fy = abs(Pm[1][1]) * 0.5 * uRes.y;
	vec2 lim = 1.3 * vec2(0.5 * uRes.x / fx, 0.5 * uRes.y / fy);
	vec2 t = clamp(vc.xy / z, -lim, lim) * z;
	vec3 j0 = vec3(fx / z, 0.0, fx * t.x / (z * z));
	vec3 j1 = vec3(0.0, fy / z, fy * t.y / (z * z));
	mat3 W = mat3(V);
	vec3 t0 = transpose(W) * j0;     // rows of J W, in world space
	vec3 t1 = transpose(W) * j1;
	SPLAT_HOOK_T(t0, t1, idx);

	vec4 q = TDInstanceCustomAttrib2(idx);
	q = (dot(q, q) > 1e-12) ? normalize(q) : vec4(1.0, 0.0, 0.0, 0.0);
	float qw = q.x, qx = q.y, qy = q.z, qz = q.w;
	vec3 r0 = vec3(1.0 - 2.0 * (qy * qy + qz * qz), 2.0 * (qx * qy - qw * qz), 2.0 * (qx * qz + qw * qy));
	vec3 r1 = vec3(2.0 * (qx * qy + qw * qz), 1.0 - 2.0 * (qx * qx + qz * qz), 2.0 * (qy * qz - qw * qx));
	vec3 r2 = vec3(2.0 * (qx * qz - qw * qy), 2.0 * (qy * qz + qw * qx), 1.0 - 2.0 * (qx * qx + qy * qy));
	mat3 Rt = mat3(r0, r1, r2);      // columns = rows of R -> R^T
	vec3 s = sc.xyz * uP1.x;
#ifdef PXE_HOOK
	s *= efx.scale;
#endif
	vec3 g0 = s * (Rt * t0);
	vec3 g1 = s * (Rt * t1);
	float a = dot(g0, g0) + uP1.w;
	float b = dot(g0, g1);
	float c = dot(g1, g1) + uP1.w;
	if (uP2.x > 0.0) {
		float ps = max(uP2.y, 1e-3) / 3.0;
		a = mix(a, ps * ps, uP2.x); b = mix(b, 0.0, uP2.x); c = mix(c, ps * ps, uP2.x);
	}
	SPLAT_HOOK_COV(a, b, c, alpha, z, idx);
	float det = a * c - b * b;
	if (det <= 1e-12) { cull(); return; }
	float mid = 0.5 * (a + c);
	float rad = sqrt(max(mid * mid - det, 0.0));
	float l1 = mid + rad, l2 = max(mid - rad, 1e-6);
	vec2 v1 = (abs(b) > 1e-9) ? normalize(vec2(b, l1 - a)) : ((a >= c) ? vec2(1.0, 0.0) : vec2(0.0, 1.0));
	vec2 v2 = vec2(-v1.y, v1.x);
	float k = min(3.0, sqrt(2.0 * log(alpha / thr)));
	vec2 corner = TDPos().xy;
	vec2 off = corner.x * k * sqrt(l1) * v1 + corner.y * k * sqrt(l2) * v2;

	vec4 clip = Pm * vc;
	SPLAT_HOOK_CLIP(clip, vc, z)
	vec2 ndc = clip.xy / clip.w;
	if (any(greaterThan(abs(ndc) - (k * sqrt(l1)) * 2.0 / uRes.xy, vec2(1.0)))) { cull(); return; }
	gl_Position = vec4(ndc + off * 2.0 / uRes.xy * vec2(sign(Pm[0][0]), sign(Pm[1][1])), clip.z / clip.w, 1.0);

	vec3 rgb = col.rgb;
	if (uP5.w > 0.5) {
		vec3 cp = uTDMats[ci].camInverse[3].xyz;
		vec3 dir = normalize(p - cp);
		vec3 c1 = vec3(TDInstanceCustomAttrib4(idx).x, TDInstanceCustomAttrib5(idx).x, TDInstanceCustomAttrib6(idx).x);
		vec3 c2 = vec3(TDInstanceCustomAttrib4(idx).y, TDInstanceCustomAttrib5(idx).y, TDInstanceCustomAttrib6(idx).y);
		vec3 c3 = vec3(TDInstanceCustomAttrib4(idx).z, TDInstanceCustomAttrib5(idx).z, TDInstanceCustomAttrib6(idx).z);
		rgb += 0.4886025 * (-dir.y * c1 + dir.z * c2 - dir.x * c3);
	}
	rgb = pow(max(rgb * uP2.z, vec3(0.0)), vec3(max(uP2.w, 1e-3)));
	if (uP4.w > 0.5) rgb = pow(rgb, vec3(2.2));
	SPLAT_HOOK_LIGHT(rgb, p, q, s, idx)
	oV.color = vec4(rgb, alpha);
	oV.d = off;
	oV.conic = vec3(c, -b, a) / det;
	SPLAT_HOOK_OUT(idx);
}
#endif

#ifdef TD_PIXEL_SHADER
out vec4 fragColor;
void main()
{
	vec2 d = iV.d;
	vec3 cn = iV.conic;
	float power = -0.5 * (cn.x * d.x * d.x + cn.z * d.y * d.y) - cn.y * d.x * d.y;
	float a = min(0.99, iV.color.a * exp(power));
	SPLAT_HOOK_PIX(power, a);
	if (power > 0.0 || a < max(uP1.z, 1.0 / 255.0)) discard;
	fragColor = TDOutputSwizzle(vec4(iV.color.rgb * a, a));
}
#endif
