// PX_pointfx trails: ONE compute pass, out = max(render, last * keep) (persistence). Input 0 = render,
// input 1 = last trail frame (Feedback TOP). uT.x = keep per frame (0..1). Cooks only when Trails is on.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uT;

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	if (g.x >= sz.x || g.y >= sz.y) return;
	if (g.x >= int(uTDOutputInfo.res.z) || g.y >= int(uTDOutputInfo.res.w)) return;
	vec4 a = texelFetch(sTD2DInputs[0], g, 0);
	ivec2 sb = textureSize(sTD2DInputs[1], 0);
	vec4 b = (g.x < sb.x && g.y < sb.y) ? texelFetch(sTD2DInputs[1], g, 0) * clamp(uT.x, 0.0, 1.0) : vec4(0.0);
	TDImageStoreOutput(0, ivec3(g, 0), max(a, b));
}
