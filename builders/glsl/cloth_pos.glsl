// BN_cloth positions out (compute, W x H rgba32f): xyz = position, w = 1. The left half of `state`; this is out2
// and the texture the render MAT displaces the grid with. in0 = state (2W x H).
layout (local_size_x = 8, local_size_y = 8) in;

void main()
{
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	ivec2 o = ivec2(uTDOutputInfo.res.zw);
	if (c.x >= o.x || c.y >= o.y) return;
	vec4 p = vec4(0.0, 0.0, 0.0, 1.0);
	if (textureSize(sTD2DInputs[0], 0) == ivec2(2 * o.x, o.y)) p = vec4(texelFetch(sTD2DInputs[0], c, 0).xyz, 1.0);
	TDImageStoreOutput(0, ivec3(c, 0), p);
}
