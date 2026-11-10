// ph pass fx_agents (side x side, one texel per agent): reset -> seed (shape, heading, species); run -> sense
// (3 sensors), rotate (Jones rule + jitter), move (wrap / bounce, mask blocks). Paused: copy.
// == seed_agents() / agent_pass() in the logic. in0 = agents_fb, in1 = trail_fb, in2 = fx_maps (mask r, food g)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;    // simw, simh, aspect, edge
uniform vec4 uAg;     // n agents, side, nspecies, speciesmode (0 interleave 1 bands 2 rings)
uniform vec4 uCtl;    // run, reset, steps, seed
uniform vec4 uSense;  // sensor angle rad, sensor offset cells, rotate angle rad, jitter rad
uniform vec4 uMove;   // step cells, deposit, own weight, other weight
uniform vec4 uSpec;   // speed spread, mask threshold, nrows, heading mode (0 random 1 out 2 in 3 swirl)
uniform vec4 uSeed;   // seedmode, seedsize (heights), respawn fraction, 0
uniform vec4 uFood;   // food attract, food inject, nrows, 0
uniform samplerBuffer uRows;  // per row 2 texels: (x y radius strength) (deposit falloff kind active)

float speciesOf(int i, vec2 p, vec2 sz)
{
	int ns = int(uAg.z + 0.5);
	if (ns <= 1) return 0.0;
	int mode = int(uAg.w + 0.5);
	if (mode == 1) return min(floor(p.x / sz.x * float(ns)), float(ns - 1));
	if (mode == 2) return min(floor(length(p - 0.5 * sz) / (0.5 * sz.y) * float(ns)), float(ns - 1));
	return float(i - ns * (i / ns));
}

vec4 seedAgent(int i, vec2 sz)
{
	int s = int(uCtl.w + 0.5);
	float u1 = hash3(i, 11, s), u2 = hash3(i, 12, s), u3 = hash3(i, 13, s);
	float size = uSeed.y * sz.y;
	vec2 c = 0.5 * sz;
	int mode = int(uSeed.x + 0.5);
	vec2 p;
	if (mode == 1) { float r = size * sqrt(u1); float a = TWO_PI * u2; p = c + r * vec2(cos(a), sin(a)); }
	else if (mode == 2) { float a = TWO_PI * u1; float r = size * (1.0 + 0.02 * (u2 - 0.5)); p = c + r * vec2(cos(a), sin(a)); }
	else if (mode == 3) { float a = TWO_PI * 3.0 * u1 + 0.3 * (u2 - 0.5); float r = size * u1; p = c + r * vec2(cos(a), sin(a)); }
	else if (mode == 4) { float k = floor(u1 * 5.0); p = vec2((k + 0.5) / 5.0 * sz.x + (u3 - 0.5) * 2.0, u2 * sz.y); }
	else if (mode == 7) { p = c; }
	else if (mode == 5 || mode == 6) {
		p = vec2(u1, u2) * sz;
		ivec2 msz = textureSize(sTD2DInputs[2], 0);
		for (int k = 0; k < 32; k++) {
			vec2 q = vec2(hash3(i, 20 + 3 * k, s), hash3(i, 21 + 3 * k, s)) * sz;
			float ua = hash3(i, 22 + 3 * k, s);
			float v = texelFetch(sTD2DInputs[2], min(ivec2(q), msz - 1), 0).g;
			if (v > ua) { p = q; break; }
		}
	}
	else { p = vec2(u1, u2) * sz; }
	int hd = int(uSpec.w + 0.5);
	float oa = atan(p.y - c.y, p.x - c.x);
	float a = hd == 1 ? oa : (hd == 2 ? oa + PI : (hd == 3 ? oa + 0.5 * PI : TWO_PI * u3));
	a = wrapf(a, TWO_PI);
	p = vec2(wrapf(p.x, sz.x), wrapf(p.y, sz.y));
	return vec4(p, a, speciesOf(i, p, sz));
}

float fieldAt(vec2 q, vec2 sz)
{
	float f = 0.0;
	int n = min(int(uSpec.z + 0.5), NROWS);
	float asp = sz.x / sz.y;
	vec2 uv = (q + 0.5) / sz;
	for (int k = 0; k < n; k++) {
		vec4 r0 = texelFetch(uRows, k * ROW_TEXELS);
		vec4 r1 = texelFetch(uRows, k * ROW_TEXELS + 1);
		if (r1.w < 0.5) continue;
		float d = length((uv - r0.xy) * vec2(asp, 1.0)) / max(r0.z, 1e-6);
		f += r0.w * falloffW(d, int(r1.y + 0.5));
	}
	return f;
}

float sense(vec2 p, float a, int sp, vec2 sz, int e)
{
	vec2 q = floor(p + uSense.y * vec2(cos(a), sin(a)));
	if (e == 0) q = vec2(wrapf(q.x, sz.x), wrapf(q.y, sz.y));
	else q = clamp(q, vec2(0.0), sz - 1.0);
	ivec2 t = ivec2(q);
	vec3 tr = texelFetch(sTD2DInputs[1], min(t, textureSize(sTD2DInputs[1], 0) - 1), 0).rgb;
	vec3 w = vec3(uMove.w);
	w[clamp(sp, 0, 2)] = uMove.z;
	float v = dot(tr, w);
	if (uFood.x != 0.0) v += uFood.x * texelFetch(sTD2DInputs[2], min(t, textureSize(sTD2DInputs[2], 0) - 1), 0).g;
	if (uSpec.z > 0.5) v += fieldAt(q, sz);
	return v;
}

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 asz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= asz.x || T.y >= asz.y) return;
	int i = T.y * asz.x + T.x;
	vec2 sz = uSim.xy;
	if (uCtl.y > 0.5) {
		vec4 o = i < int(uAg.x + 0.5) ? seedAgent(i, sz) : vec4(0.0, 0.0, 0.0, -1.0);
		TDImageStoreOutput(0, ivec3(T, 0), o);
		return;
	}
	vec4 ag = texelFetch(sTD2DInputs[0], min(T, textureSize(sTD2DInputs[0], 0) - 1), 0);
	if (uCtl.x < 0.5 || ag.w < 0.0) {
		TDImageStoreOutput(0, ivec3(T, 0), ag);
		return;
	}
	int e = int(uSim.w + 0.5);
	int s = int(uCtl.w + 0.5);
	int st = int(uCtl.z + 0.5);
	int sp = int(ag.w + 0.5);
	float a = ag.z;
	float F = sense(ag.xy, a, sp, sz, e);
	float L = sense(ag.xy, a + uSense.x, sp, sz, e);
	float R = sense(ag.xy, a - uSense.x, sp, sz, e);
	float r1 = hash3(i, st * 4 + 1, s), r2 = hash3(i, st * 4 + 2, s), r3 = hash3(i, st * 4 + 3, s);
	float turn = 0.0;
	if (F > L && F > R) turn = 0.0;
	else if (F < L && F < R) turn = r1 < 0.5 ? -uSense.z : uSense.z;
	else if (L > R) turn = uSense.z;
	else if (R > L) turn = -uSense.z;
	float a2 = a + turn + uSense.w * (2.0 * r2 - 1.0);
	float spd = uMove.x * (1.0 + uSpec.x * (clamp(ag.w, 0.0, 2.0) - 1.0));
	vec2 p2 = ag.xy + spd * vec2(cos(a2), sin(a2));
	if (e == 0) {
		p2 = vec2(wrapf(p2.x, sz.x), wrapf(p2.y, sz.y));
	} else {
		bool bx = p2.x < 0.0 || p2.x >= sz.x;
		bool by = p2.y < 0.0 || p2.y >= sz.y;
		p2.x = p2.x < 0.0 ? -p2.x : (p2.x >= sz.x ? 2.0 * sz.x - p2.x - 1e-3 : p2.x);
		p2.y = p2.y < 0.0 ? -p2.y : (p2.y >= sz.y ? 2.0 * sz.y - p2.y - 1e-3 : p2.y);
		p2 = clamp(p2, vec2(0.0), sz - 1e-3);
		if (bx) a2 = PI - a2;
		if (by) a2 = -a2;
	}
	ivec2 mt = clamp(ivec2(p2), ivec2(0), textureSize(sTD2DInputs[2], 0) - 1);
	if (texelFetch(sTD2DInputs[2], mt, 0).r > uSpec.y) { p2 = ag.xy; a2 = TWO_PI * r3; }
	if (uSeed.z > 0.0 && hash3(i, st * 4, s) < uSeed.z) {     // respawn (== agent_pass respawn)
		p2 = vec2(hash3(i, st * 4, s + 101) * sz.x, hash3(i, st * 4, s + 102) * sz.y);
		a2 = hash3(i, st * 4, s + 103) * TWO_PI;
	}
	a2 = wrapf(a2, TWO_PI);
	TDImageStoreOutput(0, ivec3(T, 0), vec4(p2, a2, ag.w));
}
