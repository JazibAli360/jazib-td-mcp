// ph pass fx_maps (sim res): in0 food (luminance -> g; also the image/text agent seed), in1 mask (R -> r).
// Inputs may have any resolution (sampled at the texel's uv). Unwired inputs are zero (blank in the switch).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;    // simw, simh, aspect, edge

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec2 uv = (vec2(T) + 0.5) / vec2(sz);
	float f = lum(texture(sTD2DInputs[0], uv).rgb);
	float m = texture(sTD2DInputs[1], uv).r;
	TDImageStoreOutput(0, ivec3(T, 0), vec4(m, f, 0.0, 1.0));
}
