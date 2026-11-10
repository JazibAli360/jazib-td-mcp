// fluid2d pass fx_advvel (sim res): semi-Lagrangian self-advection of each face component from its own face
// position (manual bilinear, edge rule per Edge), * exp(-Veldiss dt); faces touching a solid = 0. Loop end of vel_fb.
// in0 = fx_grad (ux, uy, solid, 0)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uStep;   // dt, run, edge, aspect
uniform vec4 uForce;  // curl, force gain, mask threshold, velocity decay /s

vec4 V(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[0], 0), velMode(e))) return vec4(0.0);
	return texelFetch(sTD2DInputs[0], t, 0);
}

float SB(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[0], 0), solidMode(e))) return solidConst(e);
	return texelFetch(sTD2DInputs[0], t, 0).b;
}

// x component sampled at continuous cell position p (x-face of texel k sits at k + (1, 0.5))
float sampleX(vec2 p, int e)
{
	vec2 q = p - vec2(1.0, 0.5);
	vec2 q0 = floor(q);
	ivec2 i = ivec2(q0);
	return mix4(V(i, e).x, V(i + ivec2(1, 0), e).x, V(i + ivec2(0, 1), e).x, V(i + ivec2(1, 1), e).x, q - q0);
}

// y component (y-face of texel k sits at k + (0.5, 1))
float sampleY(vec2 p, int e)
{
	vec2 q = p - vec2(0.5, 1.0);
	vec2 q0 = floor(q);
	ivec2 i = ivec2(q0);
	return mix4(V(i, e).y, V(i + ivec2(1, 0), e).y, V(i + ivec2(0, 1), e).y, V(i + ivec2(1, 1), e).y, q - q0);
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
	float dec = exp(-uForce.w * dt);
	vec2 Fx = vec2(T) + vec2(1.0, 0.5);
	vec2 vx = vec2(c.x, sampleY(Fx, e));
	float nx = sampleX(Fx - dt * vx, e) * dec;
	vec2 Fy = vec2(T) + vec2(0.5, 1.0);
	vec2 vy = vec2(sampleX(Fy, e), c.y);
	float ny = sampleY(Fy - dt * vy, e) * dec;
	float sc = c.b;
	if (sc > 0.5 || SB(T + ivec2(1, 0), e) > 0.5) nx = 0.0;
	if (sc > 0.5 || SB(T + ivec2(0, 1), e) > 0.5) ny = 0.0;
	TDImageStoreOutput(0, ivec3(T, 0), vec4(nx, ny, sc, 0.0));
}
