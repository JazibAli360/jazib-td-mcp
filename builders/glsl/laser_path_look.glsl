// preview_comp (compute, T-47): persistence + glow + background in one pass (perf wave 3, 27 Oct; replaced the
// 3-input add Composite TOP and the bg Constant TOP). The background keeps the old 8-bit Constant's steps.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uBg;      // rgb = Bgr Bgg Bgb (alpha 1)
void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	if (p.x >= int(uTDOutputInfo.res.z) || p.y >= int(uTDOutputInfo.res.w)) return;
	vec4 bg = vec4(round(clamp(uBg.rgb, 0.0, 1.0) * 255.0) / 255.0, 1.0);
	TDImageStoreOutput(0, ivec3(p, 0), texelFetch(sTD2DInputs[0], p, 0) + texelFetch(sTD2DInputs[1], p, 0) + bg);
}
