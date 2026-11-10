// fluid2d pass fx_stat (sim res): (|cell velocity|, |div|, solid, 0) of the projected field -> Analyze TOPs -> out3.
// in0 = fx_grad (ux, uy, solid, 0)
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
	vec4 c = V(T, e);
	vec4 w = V(T + ivec2(-1, 0), e);
	vec4 s = V(T + ivec2(0, -1), e);
	vec2 uc = 0.5 * vec2(w.x + c.x, s.y + c.y);
	float d = c.x - w.x + c.y - s.y;
	if (c.b > 0.5) d = 0.0;
	TDImageStoreOutput(0, ivec3(T, 0), vec4(length(uc), abs(d), c.b, 0.0));
}
