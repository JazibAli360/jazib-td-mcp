// BO_particles trails: ONE compute pass (T-47). in0 = this frame's render, in1 = last trail (Feedback TOP).
// out = max(render, last * keep): never grows past the brightest frame, fades by Trail keep per frame.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uT;   // keep (0..1 per frame), 0, 0, 0
void main()
{
	ivec2 px = ivec2(gl_GlobalInvocationID.xy);
	ivec2 res = ivec2(uTDOutputInfo.res.zw);
	if (px.x >= res.x || px.y >= res.y) return;
	vec4 cur = texelFetch(sTD2DInputs[0], px, 0);
	ivec2 psz = textureSize(sTD2DInputs[1], 0);
	vec4 prev = (px.x < psz.x && px.y < psz.y) ? texelFetch(sTD2DInputs[1], px, 0) : vec4(0.0);
	TDImageStoreOutput(0, ivec3(px, 0), TDOutputSwizzle(max(cur, prev * clamp(uT.x, 0.0, 1.0))));
}
