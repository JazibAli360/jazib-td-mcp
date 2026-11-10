// rd pass fx_stat (sim res): (A, B, B > 0.25, |central grad B| with half differences, wrap) -> Analyze average.
// == stats() in the logic. in0 = fx_rd
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;    // simw, simh, aspect, edge

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec4 c = F0(T, 0);
	float gx = (F0(T + ivec2(1, 0), 0).g - F0(T + ivec2(-1, 0), 0).g) * 0.5;
	float gy = (F0(T + ivec2(0, 1), 0).g - F0(T + ivec2(0, -1), 0).g) * 0.5;
	TDImageStoreOutput(0, ivec3(T, 0), vec4(c.r, c.g, c.g > 0.25 ? 1.0 : 0.0, length(vec2(gx, gy))));
}
