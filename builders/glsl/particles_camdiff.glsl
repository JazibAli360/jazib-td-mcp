// BO_particles webcam test emitter: ONE compute pass (T-47). in0 = current clip frame, in1 = previous frame
// (Cache TOP). out rgb = current colour, a = motion mask (smoothstep of |cur - prev|). Use Emit weight = Alpha.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uD;   // threshold, softness, 0, 0
void main()
{
	ivec2 px = ivec2(gl_GlobalInvocationID.xy);
	ivec2 res = ivec2(uTDOutputInfo.res.zw);
	if (px.x >= res.x || px.y >= res.y) return;
	vec4 c = texelFetch(sTD2DInputs[0], px, 0);
	vec4 p = texelFetch(sTD2DInputs[1], px, 0);
	vec3 d = abs(c.rgb - p.rgb);
	float m = smoothstep(uD.x, uD.x + max(uD.y, 1e-4), max(d.r, max(d.g, d.b)));
	TDImageStoreOutput(0, ivec3(px, 0), vec4(c.rgb, m));
}
