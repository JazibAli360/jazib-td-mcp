// fluid2d pass fx_div (sim res): div = ux(i) - ux(i-1) + uy(j) - uy(j-1); 0 in solids. Out (div, solid, 0, 0).
// in0 = fx_vort (ux, uy, solid, 0)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uStep;   // dt, run, edge, aspect

vec4 V(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[0], 0), velMode(e))) return vec4(0.0);
	return texelFetch(sTD2DInputs[0], t, 0);
}

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	int e = int(uStep.z + 0.5);
	vec4 c = texelFetch(sTD2DInputs[0], clamp(T, ivec2(0), textureSize(sTD2DInputs[0], 0) - 1), 0);
	float d = c.x - V(T + ivec2(-1, 0), e).x + c.y - V(T + ivec2(0, -1), e).y;
	if (c.b > 0.5) d = 0.0;
	TDImageStoreOutput(0, ivec3(T, 0), vec4(d, c.b, 0.0, 0.0));
}
