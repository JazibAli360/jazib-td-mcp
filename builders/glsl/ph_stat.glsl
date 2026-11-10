// ph pass fx_stat (sim res): (total trail, tone > 0.25, tone > 0.75, species 0 trail) -> Analyze average.
// == stats() in the logic (mean, cover, peak, meanr). in0 = fx_trail
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;    // simw, simh, aspect, edge
uniform vec4 uLook;   // valuemode, lo, hi, colormode

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec3 t = texelFetch(sTD2DInputs[0], T, 0).rgb;
	float tot = t.r + t.g + t.b;
	float tn = toneV(tot, int(uLook.x + 0.5), uLook.y, uLook.z);
	TDImageStoreOutput(0, ivec3(T, 0), vec4(tot, tn > 0.25 ? 1.0 : 0.0, tn > 0.75 ? 1.0 : 0.0, t.r));
}
