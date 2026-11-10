// gen_sim_vor_jfa: GEN_sim 'voronoi' Jump Flood (compute, npasses = Pm + Extra; pass n+1 reads pass n as input 0,
// T-91 (3)). Pass i < Pm uses step 2^(Pm - 1 - i), the Extra passes step 1 (JFA+1 / +2 clean-up). Every texel keeps
// the nearest seed (vec4 seed px, id + 1, 1) among itself and its 8 neighbours at +-step; strict < keeps the current
// one on ties; neighbour order dy then dx (== gen_sim_logic.jfa). uJ = W H Pm 0 (JFA size).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uJ;

void main()
{
	ivec2 sz = ivec2(uJ.xy);
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	if (p.x >= sz.x || p.y >= sz.y) return;
	int Pm = int(uJ.z + 0.5);
	int step = uTDPass < Pm ? (1 << (Pm - 1 - uTDPass)) : 1;
	vec2 pc = vec2(p) + 0.5;
	vec4 best = texelFetch(sTD2DInputs[0], p, 0);
	vec2 d0 = pc - best.xy;
	float bd = best.z > 0.0 ? dot(d0, d0) : 1e30;
	for (int dy = -1; dy <= 1; dy++) {
		for (int dx = -1; dx <= 1; dx++) {
			if (dx == 0 && dy == 0) continue;
			ivec2 q = p + ivec2(dx, dy) * step;
			if (q.x < 0 || q.y < 0 || q.x >= sz.x || q.y >= sz.y) continue;
			vec4 s = texelFetch(sTD2DInputs[0], q, 0);
			if (s.z <= 0.0) continue;
			vec2 d = pc - s.xy;
			float dd = dot(d, d);
			if (dd < bd) { bd = dd; best = s; }
		}
	}
	TDImageStoreOutput(0, ivec3(p, 0), best);
}
