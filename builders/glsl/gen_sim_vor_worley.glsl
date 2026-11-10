// gen_sim_vor_worley: GEN_sim 'voronoi' analytic Worley (one pass, no JFA): one feature point per grid cell of
// Cell px (jitter + wander keep it inside +-1 cell), 3x3 search -> F1, F2, id. in0 = slot input, in1 = clock.
// uW = mode cellpx jitter seed (mode 0 F1, 1 F2, 2 F2 - F1 edges, 3 cells); uW2 = wander edgewidth glow 0.
// == gen_sim_logic.worley
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uW;
uniform vec4 uW2;

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= osz.x || p.y >= osz.y) return;
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	float t = texelFetch(sTD2DInputs[1], ivec2(0), 0).x;
	float cs = max(uW.y, 2.0);
	int sd = int(uW.w);
	vec2 x = (vec2(p) + 0.5) / cs;
	ivec2 g = ivec2(floor(x));
	float f1 = 1e9, f2 = 1e9;
	int id1 = 0;
	float amp = clamp(uW.z, 0.0, 1.0) * (1.0 - 0.5 * clamp(uW2.x, 0.0, 1.0));
	for (int dy = -1; dy <= 1; dy++) {
		for (int dx = -1; dx <= 1; dx++) {
			ivec2 c = g + ivec2(dx, dy);
			vec2 h = vec2(gs_hash3(c.x, c.y, sd), gs_hash3(c.x, c.y, sd + 1));
			float ph = 2.0 * GS_PI * gs_hash3(c.x, c.y, sd + 2);
			vec2 fp = vec2(c) + 0.5 + (h - 0.5) * amp
				+ 0.25 * clamp(uW2.x, 0.0, 1.0) * vec2(sin(t + ph), cos(t * 0.9 + ph));
			float d = length(x - fp);
			if (d < f1) { f2 = f1; f1 = d; id1 = c.x * 7919 + c.y; }
			else if (d < f2) f2 = d;
		}
	}
	int mode = int(uW.x + 0.5);
	float v;
	float tt;
	if (mode == 0) { v = 1.0 - clamp(f1, 0.0, 1.0); tt = v; }
	else if (mode == 1) { v = clamp(f2 * 0.75, 0.0, 1.0); tt = v; }
	else if (mode == 2) {
		float e = 0.5 * (f2 - f1) * cs;                 // ~ px to the cell edge
		float lw = max(uW2.y, 0.0), gl = max(uW2.z, 0.0);
		v = clamp(max(1.0 - smoothstep(lw * 0.5 - 0.5, lw * 0.5 + 0.5, e), gl > 0.0 ? exp(-e / gl) : 0.0), 0.0, 1.0);
		tt = v;
	} else { v = 1.0; tt = gs_hash3(id1, 9, sd); }
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, gs_pal(tt) * v, v));
}
