// fluid2d pass fx_vort (sim res): vorticity confinement f = Curl * w * (N.y, -N.x), N = normalised grad |w|,
// averaged from the two cells of each face. Paused: copy. in0 = fx_pre (ux, uy, solid, curl)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uStep;   // dt, run, edge, aspect
uniform vec4 uForce;  // curl, force gain, mask threshold, velocity decay /s

float W(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[0], 0), velMode(e))) return 0.0;
	return texelFetch(sTD2DInputs[0], t, 0).a;
}

float SB(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[0], 0), solidMode(e))) return solidConst(e);
	return texelFetch(sTD2DInputs[0], t, 0).b;
}

vec2 vforce(ivec2 t, int e)
{
	float w0 = W(t, e);
	vec2 N = 0.5 * vec2(abs(W(t + ivec2(1, 0), e)) - abs(W(t + ivec2(-1, 0), e)),
	                    abs(W(t + ivec2(0, 1), e)) - abs(W(t + ivec2(0, -1), e)));
	float ln = length(N) + VORT_EPS;
	return uForce.x * w0 * vec2(N.y, -N.x) / ln;
}

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec4 c = texelFetch(sTD2DInputs[0], clamp(T, ivec2(0), textureSize(sTD2DInputs[0], 0) - 1), 0);
	if (uStep.y < 0.5) { TDImageStoreOutput(0, ivec3(T, 0), vec4(c.xyz, 0.0)); return; }
	int e = int(uStep.z + 0.5);
	float dt = uStep.x;
	vec2 f0 = vforce(T, e);
	vec2 fe = vforce(T + ivec2(1, 0), e);
	vec2 fn = vforce(T + ivec2(0, 1), e);
	vec2 u = c.xy + dt * 0.5 * vec2(f0.x + fe.x, f0.y + fn.y);
	float sc = c.b;
	if (sc > 0.5 || SB(T + ivec2(1, 0), e) > 0.5) u.x = 0.0;
	if (sc > 0.5 || SB(T + ivec2(0, 1), e) > 0.5) u.y = 0.0;
	TDImageStoreOutput(0, ivec3(T, 0), vec4(u, sc, 0.0));
}
