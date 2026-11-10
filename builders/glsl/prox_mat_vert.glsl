// MX_prox_material GLSL MAT vertex shader (after header + px_common + prox_mat_common). TDDeform/TDDeformNorm keep
// instancing / skinning working (any Geometry COMP). Displacement is applied in world space at the deformed (rest)
// position; same TD calls as TD's own PBR MAT export (TDPos/TDNormal/TDColor, uv-unwrap projection). Normalfix rebuilds the normal from two displaced neighbours along the tangent plane (3x mxDisplace).
// Vertex cache (Dispcache, perf-b2-w4): vc_cache (compute) runs mxVertDisp ONCE PER POINT of this MAT's geometry
// (slot uVC.x) and stores offset / normal / rest point; a vertex takes them when its index is in the slot and the
// stored rest point equals its own (instancing, deforms, a moved parent, a split vertex list: no match), else it
// runs mxVertDisp itself. Same function both ways (prox_mat_common.glsl).
uniform samplerBuffer uVG;  // vertex cache slots (vc_rows): texel 0 (on, W, H, nslots); slot k at 1 + 7k: world rows
                            // 0-2, normal rows 3-5, (offset, count, 0, 0) at 6
uniform sampler2D sVC;      // vc_cache (W x 3H rgba32f: offsets, normals, rest points) or blank4
uniform vec4 uVC;           // x = this MAT's slot in the vertex cache (-1 = none)

// Cached offset / normal of vertex gl_VertexIndex in slot uVC.x when valid for this rest point.
bool mxVcFetch(vec3 rest, inout vec3 wn, out vec3 d0)
{
	d0 = vec3(0.0);
	if (MX_DSP3.w < 0.5 || uVC.x < -0.5 || textureSize(uVG) < 1) return false;
	vec4 h = texelFetch(uVG, 0);
	int k = mxI(uVC.x);
	if (h.x < 0.5 || k >= mxI(h.w) || 1 + 7 * k + 6 >= textureSize(uVG)) return false;
	vec4 s = texelFetch(uVG, 1 + 7 * k + 6);
	int vi = gl_VertexIndex;
	if (vi < 0 || vi >= mxI(s.y)) return false;
	int i = mxI(s.x) + vi, W = max(mxI(h.y), 1), H = mxI(h.z);
	ivec2 c = ivec2(i % W, i / W);
	vec4 r = texelFetch(sVC, ivec2(c.x, c.y + 2 * H), 0);
	if (r.w < 0.5 || any(greaterThan(abs(r.xyz - rest), 1e-5 * (1.0 + abs(rest))))) return false;
	d0 = texelFetch(sVC, c, 0).xyz;
	if (MX_DSP3.y > 0.5) wn = texelFetch(sVC, ivec2(c.x, c.y + H), 0).xyz;
	return true;
}
out MXVert {
	vec4 color;
	vec3 worldSpacePos;
	vec3 restPos;
	vec3 worldSpaceNorm;
	flat int cameraIndex;
} oVert;

void main()
{
	mxInit();
	vec4 wp = TDDeform(TDPos());
	vec3 wn = normalize(TDDeformNorm(TDNormal()));
	vec3 rest = wp.xyz;
	if (mxI(MX_DSP.w) > 0) {
		vec3 d0;
		if (!mxVcFetch(rest, wn, d0)) d0 = mxVertDisp(rest, wn);
		wp.xyz += d0;
	}
	gl_Position = TDWorldToProj(wp, TDInstanceTexCoord(TDUVUnwrapCoord()));
#ifndef TD_PICKING_ACTIVE
	oVert.cameraIndex = TDCameraIndex();
	oVert.worldSpacePos = wp.xyz;
	oVert.restPos = rest;
	oVert.worldSpaceNorm = wn;
	oVert.color = TDInstanceColor(TDColor());
#else
	TDWritePickingValues();
#endif
}
