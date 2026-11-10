// ph pass fx_trail (sim res): T1 = trail + deposit; diffuse (3x3 mean mix); decay; injects (effector rows with a
// deposit, food map); mask -> 0. Reset -> 0; paused -> copy. == trail_pass() in the logic.
// in0 = trail_fb, in1 = deposit (Render TOP, rgb = species deposit, a = agent count), in2 = fx_maps
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;    // simw, simh, aspect, edge
uniform vec4 uCtl;    // run, reset, steps, seed
uniform vec4 uTrail;  // diffuse, decay, nspecies, maskthresh
uniform vec4 uFood;   // food attract, food inject, nrows, 0
uniform samplerBuffer uRows;

vec3 T1(ivec2 t, ivec2 sz, int e)
{
	ivec2 q = edgeT(t, sz, e);
	return texelFetch(sTD2DInputs[0], q, 0).rgb + texelFetch(sTD2DInputs[1], q, 0).rgb;
}

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	if (uCtl.y > 0.5) { TDImageStoreOutput(0, ivec3(T, 0), vec4(0.0)); return; }
	if (uCtl.x < 0.5) {
		TDImageStoreOutput(0, ivec3(T, 0), vec4(texelFetch(sTD2DInputs[0], T, 0).rgb, 0.0));
		return;
	}
	int e = int(uSim.w + 0.5);
	vec3 c = T1(T, sz, e);
	vec3 m = vec3(0.0);
	for (int dy = -1; dy <= 1; dy++)
		for (int dx = -1; dx <= 1; dx++)
			m += T1(T + ivec2(dx, dy), sz, e);
	m /= 9.0;
	vec3 t2 = c + uTrail.x * (m - c);
	vec3 t3 = t2 * (1.0 - uTrail.y);
	float inj = 0.0;
	int n = min(int(uFood.z + 0.5), NROWS);
	float asp = float(sz.x) / float(sz.y);
	vec2 uv = (vec2(T) + 0.5) / vec2(sz);
	for (int k = 0; k < n; k++) {
		vec4 r0 = texelFetch(uRows, k * ROW_TEXELS);
		vec4 r1 = texelFetch(uRows, k * ROW_TEXELS + 1);
		if (r1.w < 0.5 || r1.x == 0.0) continue;
		float d = length((uv - r0.xy) * vec2(asp, 1.0)) / max(r0.z, 1e-6);
		inj += r1.x * falloffW(d, int(r1.y + 0.5));
	}
	vec4 mp = texelFetch(sTD2DInputs[2], min(T, textureSize(sTD2DInputs[2], 0) - 1), 0);
	if (uFood.y != 0.0) inj += uFood.y * mp.g;
	int ns = int(uTrail.z + 0.5);
	vec3 add = vec3(inj, ns > 1 ? inj : 0.0, ns > 2 ? inj : 0.0);
	t3 += add;
	if (mp.r > uTrail.w) t3 = vec3(0.0);
	TDImageStoreOutput(0, ivec3(T, 0), vec4(t3, 0.0));
}
