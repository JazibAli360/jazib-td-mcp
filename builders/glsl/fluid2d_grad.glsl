// fluid2d pass fx_grad (sim res): subtract the pressure gradient (ux -= p(i+1) - p(i), uy -= p(j+1) - p(j));
// faces touching a solid = 0. This is the projected velocity (out2, advection, look, stats). Paused: copy in1.
// in0 = last fx_press (p), in1 = fx_vort (ux, uy, solid, 0)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uStep;   // dt, run, edge, aspect

float P(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[0], 0), presMode(e))) return 0.0;
	return texelFetch(sTD2DInputs[0], t, 0).r;
}

float SB(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[1], 0), solidMode(e))) return solidConst(e);
	return texelFetch(sTD2DInputs[1], t, 0).b;
}

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec4 c = texelFetch(sTD2DInputs[1], clamp(T, ivec2(0), textureSize(sTD2DInputs[1], 0) - 1), 0);
	if (uStep.y < 0.5) { TDImageStoreOutput(0, ivec3(T, 0), vec4(c.xyz, 0.0)); return; }
	int e = int(uStep.z + 0.5);
	float pc = P(T, e);
	vec2 u = c.xy - vec2(P(T + ivec2(1, 0), e) - pc, P(T + ivec2(0, 1), e) - pc);
	float sc = c.b;
	if (sc > 0.5 || SB(T + ivec2(1, 0), e) > 0.5) u.x = 0.0;
	if (sc > 0.5 || SB(T + ivec2(0, 1), e) > 0.5) u.y = 0.0;
	TDImageStoreOutput(0, ivec3(T, 0), vec4(u, sc, 0.0));
}
