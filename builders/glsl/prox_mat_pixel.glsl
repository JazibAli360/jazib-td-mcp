#include <TDColorSpace>
// MX_prox_material GLSL MAT pixel shader (after header + px_common + prox_mat_common). The lighting block follows
// TD 2025.31550's own PBR MAT export (pbrMAT.outputShader(), read live 26 Oct): base x alpha x TDPixelColor before
// lighting, roughness >= 1e-4, TDLightingPBR / TDEnvLightingPBR loops, fog, dither, alpha test, TDConvertColorSpace,
// swizzle; checked against a plain PBR MAT render of the same scene (docs/builds/prox_mat.md M3).
// Proximity is evaluated at the rest (undisplaced) world position so material and displacement agree.
in MXVert {
	vec4 color;
	vec3 worldSpacePos;
	vec3 restPos;
	vec3 worldSpaceNorm;
	flat int cameraIndex;
} iVert;
layout(location = 0) out vec4 oFragColor[TD_NUM_COLOR_BUFFERS];

void main()
{
	TDCheckDiscard();
	mxInit();
	float t = uMXT.x;
	vec3 wp = iVert.worldSpacePos;
	vec3 rp = iVert.restPos;
	float w = mxProx(rp, false).w;

	// dissolve (discard) + burnt rim. MX_NO_DISSOLVE (mx_pixel_solid, picked while Dissolvemode is off): no discard in
	// the shader at all, so the GPU's early depth / hidden-surface removal works (~1 ms at 1080x1920, perf-b2-w4)
	float burn = 0.0;
#ifndef MX_NO_DISSOLVE
	int dm = mxI(MX_DIS.x);
	if (dm > 0) {
		float a = pow(clamp(dm == 1 ? w : 1.0 - w, 0.0, 1.0), max(MX_DIS.y, 1e-3)) + MX_DIS.z;
		float nz = pxFbm(rp * MX_DIS.w + vec3(0.0, t * MX_DIS2.y, 0.0), mxI(MX_DIS2.x), 23u);
		float e = a - nz;                           // > 0: dissolved
		if (e > 0.0) discard;
		if (MX_DIS2.z > 0.0 && a > 1e-4) burn = clamp(1.0 + e / MX_DIS2.z, 0.0, 1.0);
	}
#endif

	// base colour + colour drive
	vec4 base = MX_BASE;
	if (MX_CNEAR.w > 0.5) base *= TDPixelColor(iVert.color);
	vec3 col = base.rgb;
	int cm = mxI(MX_COL.x);
	float ct = pow(clamp(w, 0.0, 1.0), max(MX_COL.z, 1e-3)) * MX_COL.y;
	if (cm == 1) col *= mix(vec3(1.0), MX_CNEAR.rgb, ct);
	else if (cm == 2) col = mix(col, MX_CNEAR.rgb, ct);
	else if (cm == 3) col = mix(MX_CFAR.rgb, MX_CNEAR.rgb, ct);
	else if (cm == 4) col = max(pxHue(col, MX_COL.w * ct), vec3(0.0));
	else if (cm == 5) col += MX_CNEAR.rgb * ct;
	col *= 1.0 - MX_BCOL.w * burn;
	float rough = max(mxDrive(w, MX_ROUGH), 0.0001);
	float metal = mxDrive(w, MX_METAL);

	// normal (+ detail noise)
	vec3 n = normalize(iVert.worldSpaceNorm);
	vec3 V = normalize(uTDMats[iVert.cameraIndex].camInverse[3].xyz - wp);
	if (!TDFrontFacing(wp, n)) n = -n;
	float ns = mxDrive(w, MX_NRM);
	if (ns != 0.0) {
		vec3 q = rp * MX_NRM.w + vec3(0.0, t * MX_NRM2.x, 0.0);
		int oc = mxI(MX_NRM2.y);
		const float e = 0.35;                       // 4-tap tetrahedral gradient (4 fbm instead of 6, perf T-115)
		const vec3 k0 = vec3(1.0, -1.0, -1.0), k1 = vec3(-1.0, -1.0, 1.0), k2 = vec3(-1.0, 1.0, -1.0), k3 = vec3(1.0);
		vec3 g = (k0 * pxFbm(q + e * k0, oc, 31u) + k1 * pxFbm(q + e * k1, oc, 31u) + k2 * pxFbm(q + e * k2, oc, 31u)
		          + k3 * pxFbm(q + e * k3, oc, 31u)) / (4.0 * e);
		g -= n * dot(g, n);
		n = normalize(n - ns * g);
	}

	// PBR lighting (TD's functions; 0.08 x specular level = dielectric F0 as in TD's PBR MAT)
	float alpha = base.a;
	if (MX_OPA.w > 0.5) alpha *= mxDrive(w, MX_OPA);
	col *= alpha;                                   // premultiplied before lighting, as TD's PBR MAT
	vec3 diffuseColor = col * (1.0 - metal);
	vec3 specularColor = mix(vec3(0.08 * MX_ROUGH.w), col, metal);
	vec3 lit = vec3(0.0);
	for (int i = 0; i < TD_NUM_LIGHTS; i++) {
		TDPBRResult res = TDLightingPBR(i, diffuseColor, specularColor, wp, n, MX_NRM2.z, MX_SHC.rgb, V, rough);
		lit += res.diffuse + res.specular;
	}
	for (int i = 0; i < TD_NUM_ENV_LIGHTS; i++) {
		TDPBRResult res = TDEnvLightingPBR(i, diffuseColor, specularColor, n, V, rough, MX_METAL.w);
		lit += res.diffuse + res.specular;
	}

	// emission: base + proximity glow + rim (fresnel) + burnt rim
	vec3 emit = MX_EBASE.rgb + MX_ECOL.rgb * mxDrive(w, MX_EMIT);
	float rim = mxDrive(w, MX_RIM);
	if (rim != 0.0) emit += MX_RCOL.rgb * rim * pow(1.0 - clamp(dot(n, V), 0.0, 1.0), MX_EMIT.w);
	emit += MX_BCOL.rgb * (MX_DIS2.w * burn * burn);

	vec4 o = TDFog(vec4(lit + emit * alpha, alpha), wp, iVert.cameraIndex);
	o = TDDither(o);
	TDAlphaTest(o.a);
	oFragColor[0] = TDOutputSwizzle(TDConvertColorSpace(o));
	for (int i = 1; i < TD_NUM_COLOR_BUFFERS; i++) oFragColor[i] = vec4(0.0);
}
