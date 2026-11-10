// ph pass fx_astat (side x side): (cos heading, sin heading, live, 0) per agent slot -> Analyze average.
// order = |(avg cos, avg sin)| / alive (== stats() order / alive). in0 = fx_agents
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uAg;     // n agents, side, nspecies, speciesmode

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec4 a = texelFetch(sTD2DInputs[0], T, 0);
	bool live = a.w >= 0.0;
	TDImageStoreOutput(0, ivec3(T, 0), live ? vec4(cos(a.z), sin(a.z), 1.0, 0.0) : vec4(0.0));
}
