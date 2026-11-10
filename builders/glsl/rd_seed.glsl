// rd pass fx_seed (sim res): reset -> A = 1, B = seed pattern; else injection (in1 image x Inject, injector rows:
// effectors / in5 points / mouse / bursts) and the local morph field (.b); solid from fx_maps.r > Maskthresh.
// Paused (nsteps 0, no reset): copy. == seed_pass() in the logic.
// in0 = state_fb, in1 = seed_prep (seed / inject image at sim res), in2 = fx_maps
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;    // simw, simh, aspect, edge
uniform vec4 uCtl;    // nsteps this frame, reset, mapimg, seed
uniform vec4 uSeed;   // seedmode, seedsize, seedcount, seeddensity
uniform vec4 uInj;    // inject, maskthresh, morphdecay, nrows
uniform samplerBuffer uRows;  // per row 2 texels: (x y radius strength) (morph falloff kind active)

float pattern(ivec2 T, vec2 uv, float asp)
{
	int mode = int(uSeed.x + 0.5);
	float size = uSeed.y;
	int s = int(uCtl.w + 0.5);
	vec2 dp = (uv - 0.5) * vec2(asp, 1.0);
	if (mode == 0) return max(abs(dp.x), abs(dp.y)) < size ? 1.0 : 0.0;
	if (mode == 1) {
		int n = int(uSeed.z + 0.5);
		for (int k = 0; k < n; k++) {
			vec2 c = vec2(hash3(k, 1, s), hash3(k, 2, s));
			float rr = size * (0.5 + hash3(k, 3, s));
			if (length((uv - c) * vec2(asp, 1.0)) < rr) return 1.0;
		}
		return 0.0;
	}
	if (mode == 2) return hash3(T.x, T.y, s) < uSeed.w ? 1.0 : 0.0;
	if (mode == 3) return abs(length(dp) - 0.25) < size * 0.5 ? 1.0 : 0.0;
	if (mode == 4) { float q = dp.x / (size * 4.0); return (q - floor(q)) < 0.25 ? 1.0 : 0.0; }
	if (mode == 5 || mode == 6) {
		vec4 im = texelFetch(sTD2DInputs[1], clamp(T, ivec2(0), textureSize(sTD2DInputs[1], 0) - 1), 0);
		return clamp(lum(im.rgb), 0.0, 1.0);
	}
	return 0.0;
}

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec4 c = texelFetch(sTD2DInputs[0], clamp(T, ivec2(0), textureSize(sTD2DInputs[0], 0) - 1), 0);
	vec4 mp = texelFetch(sTD2DInputs[2], clamp(T, ivec2(0), textureSize(sTD2DInputs[2], 0) - 1), 0);
	float solid = mp.r > uInj.y ? 1.0 : 0.0;
	vec2 uv = (vec2(T) + 0.5) / vec2(sz);
	float asp = float(sz.x) / float(sz.y);
	vec4 o = c;
	if (uCtl.y > 0.5) {
		o = vec4(1.0, pattern(T, uv, asp), 0.0, 0.0);
	} else if (uCtl.x < 0.5) {
		TDImageStoreOutput(0, ivec3(T, 0), c);
		return;
	} else {
		float A = c.r, B = c.g;
		if (uInj.x > 0.0) {
			vec4 im = texelFetch(sTD2DInputs[1], clamp(T, ivec2(0), textureSize(sTD2DInputs[1], 0) - 1), 0);
			float q = clamp(uInj.x * lum(im.rgb), 0.0, 1.0);
			B = B + (1.0 - B) * q;
		}
		float infl = 0.0;
		int n = min(int(uInj.w + 0.5), NROWS);
		for (int k = 0; k < n; k++) {
			vec4 r0 = texelFetch(uRows, k * ROW_TEXELS);
			vec4 r1 = texelFetch(uRows, k * ROW_TEXELS + 1);
			if (r1.w < 0.5) continue;
			float d = length((uv - r0.xy) * vec2(asp, 1.0)) / max(r0.z, 1e-6);
			float w = falloffW(d, int(r1.y + 0.5));
			if (r0.w >= 0.0) {
				float q = clamp(r0.w * w, 0.0, 1.0);
				B = B + (1.0 - B) * q;
			} else {
				float q = clamp(-r0.w * w, 0.0, 1.0);
				A = A + (1.0 - A) * q;
				B = B * (1.0 - q);
			}
			infl += w * r1.x;
		}
		o = vec4(A, B, c.b * uInj.z + infl, 0.0);
	}
	o.a = solid;
	if (solid > 0.5) { o.r = 1.0; o.g = 0.0; }
	TDImageStoreOutput(0, ivec3(T, 0), o);
}
