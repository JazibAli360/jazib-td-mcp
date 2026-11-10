// fluid2d pass fx_press (sim res): ONE weighted-Jacobi iteration p' = (1-w) pc + w (sum pn - div) * INV_BETA,
// Neumann at solids (pn = pc), Dirichlet 0 outside in open mode. uPress.x scales the incoming pressure (Warmstart on
// the first iteration, 1 after). Paused: copy (pressure frozen). Out (p, 0, 0, 0).
// in0 = pressure (press_fb for the first node, else the previous fx_press), in1 = fx_div (div, solid)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uStep;   // dt, run, edge, aspect
uniform vec4 uPress;  // scale of in0, Jacobi weight w, 0, 0

float P(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[0], 0), presMode(e))) return 0.0;
	return texelFetch(sTD2DInputs[0], t, 0).r;
}

float SD(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[1], 0), solidMode(e))) return solidConst(e);
	return texelFetch(sTD2DInputs[1], t, 0).g;
}

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec4 c = texelFetch(sTD2DInputs[0], clamp(T, ivec2(0), textureSize(sTD2DInputs[0], 0) - 1), 0);
	if (uStep.y < 0.5) { TDImageStoreOutput(0, ivec3(T, 0), vec4(c.r, 0.0, 0.0, 0.0)); return; }
	int e = int(uStep.z + 0.5);
	float s = uPress.x;
#ifdef FLUID2D_NPASSES
	if (uTDPass > 0) s = 1.0;   // npasses mode (LIVE CHECK P2): only the first pass scales the warm start
#endif
	vec4 d = texelFetch(sTD2DInputs[1], clamp(T, ivec2(0), textureSize(sTD2DInputs[1], 0) - 1), 0);
	if (d.g > 0.5) { TDImageStoreOutput(0, ivec3(T, 0), vec4(0.0)); return; }
	float pc = s * c.r;
	float acc = 0.0;
	ivec2 o[4] = ivec2[4](ivec2(1, 0), ivec2(-1, 0), ivec2(0, 1), ivec2(0, -1));
	for (int k = 0; k < 4; k++) {
		ivec2 q = T + o[k];
		acc += SD(q, e) > 0.5 ? pc : s * P(q, e);
	}
	float w = uPress.y;
	float pn = (1.0 - w) * pc + w * (acc - d.r) * INV_BETA;
	TDImageStoreOutput(0, ivec3(T, 0), vec4(pn, 0.0, 0.0, 0.0));
}
