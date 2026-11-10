// PX_pointfx layers (splat render mode): ONE compute pass, out = splats (input 0, premultiplied "over", sorted) +
// sprites (input 1: pool embers + effector glow, additive premultiplied). Alpha = splats + sprites (clamped).
layout (local_size_x = 8, local_size_y = 8) in;

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	if (g.x >= int(uTDOutputInfo.res.z) || g.y >= int(uTDOutputInfo.res.w)) return;
	ivec2 sa = textureSize(sTD2DInputs[0], 0);
	ivec2 sb = textureSize(sTD2DInputs[1], 0);
	vec4 a = (g.x < sa.x && g.y < sa.y) ? texelFetch(sTD2DInputs[0], g, 0) : vec4(0.0);
	vec4 b = (g.x < sb.x && g.y < sb.y) ? texelFetch(sTD2DInputs[1], g, 0) : vec4(0.0);
	TDImageStoreOutput(0, ivec3(g, 0), vec4(a.rgb + b.rgb, clamp(a.a + b.a, 0.0, 1.0)));
}
