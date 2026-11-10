// gen_sim_ca_look: GEN_sim 'ca' picture at the slot input's size. in0 = slot input, in1 = state (sim res).
// Each cell gives a palette coordinate t and a brightness v (== gen_sim_logic.ca_value); picture = palette(t) * v,
// coverage v, blended over the input (Colour page). uSim = W H family C-or-N; uCv = colourmode shape gap agescale.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;
uniform vec4 uCv;

vec2 cellTV(ivec2 ci)
{
	ivec2 sz = ivec2(uSim.xy);
	ci = clamp(ci, ivec2(0), sz - 1);
	vec4 s = texelFetch(sTD2DInputs[1], ci, 0);
	int fam = int(uSim.z + 0.5);
	int si = int(s.r + 0.5);
	float C = max(uSim.w, 2.0);
	float sv;
	if (fam == 0) sv = si == 1 ? 1.0 : (si >= 2 ? 1.0 - float(si - 1) / (C - 1.0) : 0.0);
	else if (fam == 1) sv = si == 1 ? 1.0 : (si == 2 ? 0.6 : (si == 3 ? 0.25 : 0.0));
	else if (fam == 2) sv = s.r / (C - 1.0);
	else sv = clamp(s.r, 0.0, 1.0);
	int cm = int(uCv.x + 0.5);                          // 0 state, 1 glow, 2 age
	if (cm == 1) return vec2(s.g, s.g);
	if (cm == 2) return vec2(1.0 - exp(-s.b / max(uCv.w, 1e-3)), max(sv, s.g * 0.5));
	return vec2(sv, sv);
}

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= osz.x || p.y >= osz.y) return;
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	vec2 cs = vec2(osz) / uSim.xy;                      // cell size in output px
	vec2 q = (vec2(p) + 0.5) / cs;                      // sim coordinates
	int shape = int(uCv.y + 0.5);                       // 0 square, 1 round, 2 smooth
	vec2 tv;
	if (shape == 2) {
		vec2 g = q - 0.5;
		ivec2 i0 = ivec2(floor(g));
		vec2 f = g - vec2(i0);
		vec2 a = cellTV(i0), b = cellTV(i0 + ivec2(1, 0)), c = cellTV(i0 + ivec2(0, 1)), d = cellTV(i0 + ivec2(1, 1));
		tv = mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
	} else {
		tv = cellTV(ivec2(floor(q)));
		vec2 f = fract(q) - 0.5;
		float aa = 1.0 / max(min(cs.x, cs.y), 1.0);
		float m;
		if (shape == 1) m = 1.0 - smoothstep(0.5 - uCv.z * 0.5 - aa, 0.5 - uCv.z * 0.5, length(f));
		else m = (max(abs(f.x), abs(f.y)) <= 0.5 - uCv.z * 0.5) ? 1.0 : 0.0;
		tv.y *= m;
	}
	float v = clamp(tv.y, 0.0, 1.0);
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, gs_pal(tv.x) * v, v));
}
