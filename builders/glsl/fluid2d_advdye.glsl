// fluid2d pass fx_advdye (dye res): backtrace with the projected sim-res velocity (manual bilinear), bilinear dye
// fetch (edge rule per Edge), * exp(-Dyediss dt), + in1 source (rgb * a * Srcgain * dt) + emitter splats (add / over);
// 0 inside solids. Loop end of dye_fb. Paused: copy.
// in0 = dye_fb (dye res), in1 = fx_grad (sim res: ux, uy, solid), in2 = src_prep (dye res)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;    // simw, simh, resw, resh
uniform vec4 uStep;   // dt, run, edge, aspect
uniform vec4 uDye;    // dye decay /s, source gain (x srcon), blend (0 add, 1 over), 0
uniform samplerBuffer uEmit;  // per emitter 3 texels: (x y vx vy) (radius dye force active) (r g b 0)

vec4 D(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[0], 0), dyeMode(e))) return vec4(0.0);
	return texelFetch(sTD2DInputs[0], t, 0);
}

vec4 V(ivec2 t, int e)
{
	if (!resolveT(t, textureSize(sTD2DInputs[1], 0), velMode(e))) return vec4(0.0);
	return texelFetch(sTD2DInputs[1], t, 0);
}

float sampleX(vec2 p, int e)
{
	vec2 q = p - vec2(1.0, 0.5);
	vec2 q0 = floor(q);
	ivec2 i = ivec2(q0);
	return mix4(V(i, e).x, V(i + ivec2(1, 0), e).x, V(i + ivec2(0, 1), e).x, V(i + ivec2(1, 1), e).x, q - q0);
}

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
	if (uStep.y < 0.5) { TDImageStoreOutput(0, ivec3(T, 0), D(T, 1)); return; }
	int e = int(uStep.z + 0.5);
	float dt = uStep.x;
	vec2 dres = vec2(sz);
	vec2 sres = vec2(textureSize(sTD2DInputs[1], 0));
	vec2 uv = (vec2(T) + 0.5) / dres;
	vec2 ps = uv * sres;
	vec2 v = vec2(sampleX(ps, e), sampleY(ps, e));
	vec2 q = (uv - dt * v / sres) * dres - 0.5;
	vec2 q0 = floor(q);
	ivec2 i = ivec2(q0);
	vec2 f = q - q0;
	vec4 a00 = D(i, e), a10 = D(i + ivec2(1, 0), e), a01 = D(i + ivec2(0, 1), e), a11 = D(i + ivec2(1, 1), e);
	vec3 d = mix(mix(a00.rgb, a10.rgb, f.x), mix(a01.rgb, a11.rgb, f.x), f.y) * exp(-uDye.x * dt);
	vec4 s = textureLod(sTD2DInputs[2], uv, 0.0);
	d += s.rgb * s.a * uDye.y * dt;
	int n = min(NEMIT, textureSize(uEmit) / EMIT_TEXELS);
	for (int k = 0; k < n; k++) {
		vec4 a = texelFetch(uEmit, EMIT_TEXELS * k);
		vec4 b = texelFetch(uEmit, EMIT_TEXELS * k + 1);
		vec4 col = texelFetch(uEmit, EMIT_TEXELS * k + 2);
		if (b.w < 0.5 || b.x <= 0.0) continue;
		float g = b.y * splat(uv, a.xy, b.x, uStep.w);
		if (uDye.z < 0.5) d += col.rgb * g;
		else d = mix(d, col.rgb, clamp(g, 0.0, 1.0));
	}
	ivec2 cs = clamp(ivec2(floor(ps)), ivec2(0), ivec2(sres) - 1);
	if (texelFetch(sTD2DInputs[1], cs, 0).b > 0.5) d = vec3(0.0);
	TDImageStoreOutput(0, ivec3(T, 0), vec4(d, 0.0));
}
