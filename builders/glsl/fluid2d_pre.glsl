// fluid2d pass fx_pre (sim res): curl of the incoming velocity -> .a; emitter impulses + external force on the
// faces; solid flag from the mask -> .b; faces touching a solid = 0. Paused (run 0): copy.
// in0 = vel_fb (ux, uy, solid, curl), in1 = force_prep (RG, screen heights/s^2), in2 = mask_prep (R > thresh = solid)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;    // simw, simh, resw, resh
uniform vec4 uStep;   // dt, run, edge, aspect
uniform vec4 uForce;  // curl, force gain (x forceon), mask threshold, velocity decay /s
uniform samplerBuffer uEmit;  // per emitter 3 texels: (x y vx vy) (radius dye force active) (r g b 0)

vec4 V(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[0], 0), velMode(e))) return vec4(0.0);
	return texelFetch(sTD2DInputs[0], t, 0);
}

float S(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[2], 0), solidMode(e))) return solidConst(e);
	return texelFetch(sTD2DInputs[2], t, 0).r > uForce.z ? 1.0 : 0.0;
}

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec4 c = texelFetch(sTD2DInputs[0], clamp(T, ivec2(0), textureSize(sTD2DInputs[0], 0) - 1), 0);
	if (uStep.y < 0.5) { TDImageStoreOutput(0, ivec3(T, 0), c); return; }
	int e = int(uStep.z + 0.5);
	float dt = uStep.x;
	float eY = 0.5 * (V(T + ivec2(1, -1), e).y + V(T + ivec2(1, 0), e).y);
	float wY = 0.5 * (V(T + ivec2(-1, -1), e).y + V(T + ivec2(-1, 0), e).y);
	float nX = 0.5 * (V(T + ivec2(-1, 1), e).x + V(T + ivec2(0, 1), e).x);
	float sX = 0.5 * (V(T + ivec2(-1, -1), e).x + V(T + ivec2(0, -1), e).x);
	float w = 0.5 * ((eY - wY) - (nX - sX));
	vec2 u = c.xy;
	vec2 f = texelFetch(sTD2DInputs[1], clamp(T, ivec2(0), textureSize(sTD2DInputs[1], 0) - 1), 0).rg;
	u += f * (uForce.y * uSim.y * dt);
	vec2 fx = (vec2(T) + vec2(1.0, 0.5)) / uSim.xy;
	vec2 fy = (vec2(T) + vec2(0.5, 1.0)) / uSim.xy;
	int n = min(NEMIT, textureSize(uEmit) / EMIT_TEXELS);
	for (int i = 0; i < n; i++) {
		vec4 a = texelFetch(uEmit, EMIT_TEXELS * i);
		vec4 b = texelFetch(uEmit, EMIT_TEXELS * i + 1);
		if (b.w < 0.5 || b.x <= 0.0) continue;
		u.x += a.z * b.z * uSim.y * splat(fx, a.xy, b.x, uStep.w);
		u.y += a.w * b.z * uSim.y * splat(fy, a.xy, b.x, uStep.w);
	}
	float sc = S(T, e);
	if (sc > 0.5 || S(T + ivec2(1, 0), e) > 0.5) u.x = 0.0;
	if (sc > 0.5 || S(T + ivec2(0, 1), e) > 0.5) u.y = 0.0;
	TDImageStoreOutput(0, ivec3(T, 0), vec4(u, sc, w));
}
