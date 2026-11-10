// gen_sim_vor_look: GEN_sim 'voronoi' picture from the JFA map at the slot input's size. in0 = slot input,
// in1 = JFA map (vec4 seed px, id + 1, 1; JFA size). Edge distance = distance to the bisector between this pixel's
// seed A and any other seed B found in 16 samples around it (8 directions at the band radius and half of it): exact
// for the edges inside the band. Delaunay = the Gabriel subgraph of the seeds near the pixel (a pair whose midpoint's
// nearest seed is one of the pair), drawn as segments. == gen_sim_logic.vor_edge_dist / gabriel_edges.
// uVl = mode edgewidth glow count; uVl2 = jfaW jfaH seed outline.
// Mode: 0 cells, 1 stained (slot input at the seed), 2 edges, 3 distance, 4 delaunay.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uVl;
uniform vec4 uVl2;

vec4 jfaAt(vec2 q)
{
	ivec2 jsz = ivec2(uVl2.xy);
	return texelFetch(sTD2DInputs[1], clamp(ivec2(floor(q)), ivec2(0), jsz - 1), 0);
}

float segDist(vec2 p, vec2 a, vec2 b)
{
	vec2 ab = b - a;
	float h = clamp(dot(p - a, ab) / max(dot(ab, ab), 1e-9), 0.0, 1.0);
	return length(p - a - ab * h);
}

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= osz.x || p.y >= osz.y) return;
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	float sc = float(osz.x) / uVl2.x;                   // output px per JFA px
	vec2 q = (vec2(p) + 0.5) / sc;
	vec4 A = jfaAt(q);
	if (A.z <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), base); return; }
	int mode = int(uVl.x + 0.5);
	float lw = max(uVl.y, 0.0);
	float gl = max(uVl.z, 0.0);
	float cellpx = sqrt(float(osz.x) * float(osz.y) / max(uVl.w, 1.0));
	float band = (mode == 4) ? 0.6 * cellpx : lw * 0.5 + 3.0 * gl + 1.0;
	float r = max(band / sc, 1.0);
	float e = 1e9;                                      // distance to the nearest edge, output px
	vec4 cand[8];
	int nc = 0;
	for (int k = 0; k < 16; k++) {
		float an = float(k % 8) * (GS_PI / 4.0);
		vec4 B = jfaAt(q + vec2(cos(an), sin(an)) * (k < 8 ? r : 0.5 * r));
		if (B.z <= 0.0 || B.z == A.z) continue;
		vec2 n = normalize(A.xy - B.xy);
		e = min(e, dot(q - 0.5 * (A.xy + B.xy), n) * sc);
		bool seen = false;
		for (int j = 0; j < nc; j++) seen = seen || cand[j].z == B.z;
		if (!seen && nc < 8) { cand[nc] = B; nc++; }
	}
	e = max(e, 0.0);
	float line = 1.0 - smoothstep(lw * 0.5 - 0.5, lw * 0.5 + 0.5, e);
	float glow = gl > 0.0 ? exp(-e / gl) : 0.0;
	float id = A.z - 1.0;
	vec3 col;
	float a = 1.0;
	if (mode == 0 || mode == 1) {
		vec3 fill = (mode == 1)
			? texelFetch(sTD2DInputs[0], clamp(ivec2(A.xy * sc), ivec2(0), osz - 1), 0).rgb
			: gs_pal(gs_hash3(int(id), 9, int(uVl2.z)));
		col = fill * (1.0 - line * uVl2.w) + gs_pal(1.0) * glow * 0.6;
	} else if (mode == 2) {
		float v = clamp(max(line, glow), 0.0, 1.0);
		col = gs_pal(v) * v;
		a = v;
	} else if (mode == 3) {
		float v = 1.0 - clamp(length(q - A.xy) * sc / cellpx, 0.0, 1.0);
		col = gs_pal(v) * v;
		a = v;
	} else {                                            // delaunay (Gabriel): pairs among A + the candidates
		vec4 S[9];
		S[0] = A;
		for (int j = 0; j < nc; j++) S[j + 1] = cand[j];
		float dl = 1e9;
		for (int i = 0; i <= nc; i++) {
			for (int j = i + 1; j <= nc; j++) {
				float ds = segDist(q, S[i].xy, S[j].xy) * sc;
				if (ds >= dl || ds > lw + 3.0 * gl + 1.0) continue;
				float o = jfaAt(0.5 * (S[i].xy + S[j].xy)).z;
				if (o == S[i].z || o == S[j].z) dl = ds;
			}
		}
		float ln = 1.0 - smoothstep(lw * 0.5 - 0.5, lw * 0.5 + 0.5, dl);
		float v = clamp(max(ln, gl > 0.0 ? exp(-dl / gl) : 0.0), 0.0, 1.0);
		col = gs_pal(v) * v;
		a = v;
	}
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col, a));
}
