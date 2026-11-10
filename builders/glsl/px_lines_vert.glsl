// px_lines_vert.glsl - PX lines pass, GLSL MAT vertex shader (one render pass; T-46 does not apply). One instance =
// one segment of the segment texture (px_lines_seg.glsl); the instanced geometry is a 1x1 Rectangle SOP (P.xy in
// -0.5..0.5: x = along A -> B, y = side). Both ends are projected with the RENDER camera (T-89: uTDMats proj x worldCam,
// TDCamToProj does not exist on 31550), clipped to the near side in clip space, and the quad is built in SCREEN pixels:
// half width = Width x width mult / 2 + 2 Halo + 1 px on every side, so the core width is real px at any depth.
// Mirrors px_lines_logic.ref_quad. Text = glsl_header() + px_lines_common.glsl + this.
uniform sampler2D sSeg;
out Vertex { vec4 color; vec2 pp; flat vec4 seg; flat vec4 ue; flat float hw; flat float caps; } oV;

void main()
{
	int s = TDInstanceID();
	ivec2 b = ivec2((s % SEG_W) * 4, s / SEG_W);
	vec4 T0 = texelFetch(sSeg, b, 0), T1 = texelFetch(sSeg, b + ivec2(1, 0), 0);
	vec4 T2 = texelFetch(sSeg, b + ivec2(2, 0), 0), T3 = texelFetch(sSeg, b + ivec2(3, 0), 0);
	oV.color = vec4(0.0); oV.pp = vec2(0.0); oV.ue = vec4(0.0); oV.seg = vec4(0.0); oV.hw = 0.0; oV.caps = 0.0;
	gl_Position = vec4(2.0, 2.0, 2.0, 1.0);                               // outside clip = culled
	if (T3.w < 0.5 || T2.a <= 0.0) return;
	mat4 VP = uTDMats[TDCameraIndex()].proj * uTDMats[TDCameraIndex()].worldCam;
	vec4 ca = VP * vec4(T0.xyz, 1.0), cb = VP * vec4(T1.xyz, 1.0);
	float ua = T0.w, ub = T1.w;
	const float NW = 1e-3;
	if (ca.w < NW && cb.w < NW) return;
	if (ca.w < NW) { float f = (NW - ca.w) / (cb.w - ca.w); ca = mix(ca, cb, f); ua = mix(ua, ub, f); }
	else if (cb.w < NW) { float f = (NW - cb.w) / (ca.w - cb.w); cb = mix(cb, ca, f); ub = mix(ub, ua, f); }
	vec2 res = uL[R_G0].xy;
	vec2 sa = (ca.xy / ca.w * 0.5 + 0.5) * res, sb = (cb.xy / cb.w * 0.5 + 0.5) * res;
	vec2 d = sb - sa;
	float len = length(d);
	vec2 dir = len > 1e-4 ? d / len : vec2(1.0, 0.0);
	vec2 nrm = vec2(-dir.y, dir.x);
	float hw = 0.5 * uL[R_ST0].x * T3.x;
	float ext = hw + 2.0 * uL[R_ST0].y + 1.0;
	float al = P.x + 0.5;
	vec2 pos = mix(sa, sb, al) + dir * ext * (al < 0.5 ? -1.0 : 1.0) + nrm * ext * (P.y > 0.0 ? 1.0 : -1.0);
	gl_Position = vec4(pos / res * 2.0 - 1.0, 0.5, 1.0);                 // z 0.5: inside GL and Vulkan clip ranges
	oV.color = T2;
	oV.pp = pos;
	oV.ue = vec4(ua, ub, ca.w, cb.w);                                    // u and eye depth at both ends (pixel: mix by f)
	oV.seg = vec4(sa, sb);
	oV.hw = hw;
	oV.caps = T3.y;
}
