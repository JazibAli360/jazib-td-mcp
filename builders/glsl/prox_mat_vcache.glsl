// MX_prox_material vertex cache pass `vc_cache` (compute, after header + effectors block + px_common + prox_mat_common
// with MX_VC_PASS; W x 3H rgba32f): one invocation per POINT of every cached geometry (slots in uVG, vc_rows) runs the
// vertex stage's displacement once (mxVertDisp) instead of once per vertex invocation. Bands: rows 0..H-1 offset
// (xyz, 1), H..2H-1 displaced normal (xyz, 1), 2H..3H-1 rest point in world space (xyz, 1 = valid; the vertex shader
// uses a texel only when this equals its own TDDeform(TDPos())). in0 = vc_src (SOP-space P rows, then N rows, same
// W x H layout), in1 / in2 = the MAT's sPts / sField textures (vc_s0 / vc_s1).
uniform samplerBuffer uVG;  // texel 0 (on, W, H, nslots); slot k at 1 + 7k: world rows 0-2, normal rows 3-5, (offset, count, 0, 0)
layout (local_size_x = 8, local_size_y = 8) in;

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	vec4 h = textureSize(uVG) > 0 ? texelFetch(uVG, 0) : vec4(0.0);
	int W = max(mxI(h.y), 1), H = max(mxI(h.z), 1), ns = mxI(h.w);
	if (g.x >= W || g.y >= H) return;
	int i = g.y * W + g.x;
	vec4 o0 = vec4(0.0), o1 = vec4(0.0), o2 = vec4(0.0);
	int k = -1;
	vec4 s = vec4(0.0);
	for (int j = 0; j < 65536; j++) {
		if (j >= ns) break;
		vec4 sj = texelFetch(uVG, 1 + 7 * j + 6);
		if (i >= mxI(sj.x) && i < mxI(sj.x) + mxI(sj.y)) { k = j; s = sj; break; }
	}
	if (h.x > 0.5 && k >= 0) {
		mxInit();
		int b = 1 + 7 * k;
		vec4 P = vec4(texelFetch(sTD2DInputs[0], g, 0).xyz, 1.0);
		vec3 N = texelFetch(sTD2DInputs[0], ivec2(g.x, g.y + H), 0).xyz;
		// = TDDeform(TDPos()) / TDDeformNorm(TDNormal()) of a plain (not instanced, not skinned) geometry
		vec3 rest = vec3(dot(texelFetch(uVG, b), P), dot(texelFetch(uVG, b + 1), P), dot(texelFetch(uVG, b + 2), P));
		vec3 wn = normalize(vec3(dot(texelFetch(uVG, b + 3).xyz, N), dot(texelFetch(uVG, b + 4).xyz, N),
		                         dot(texelFetch(uVG, b + 5).xyz, N)));
		vec3 d0 = vec3(0.0);
		if (mxI(MX_DSP.w) > 0) d0 = mxVertDisp(rest, wn);
		o0 = vec4(d0, 1.0);
		o1 = vec4(wn, 1.0);
		o2 = vec4(rest, 1.0);
	}
	TDImageStoreOutput(0, ivec3(g, 0), o0);
	TDImageStoreOutput(0, ivec3(g.x, g.y + H, 0), o1);
	TDImageStoreOutput(0, ivec3(g.x, g.y + 2 * H, 0), o2);
}
