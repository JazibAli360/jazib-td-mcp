// gen_sim_vor_seed: GEN_sim 'voronoi' seed scatter (compute, manual dispatch ceil(Count / 64) x 1; the output is
// cleared every cook, clearoutputs on). One invocation per seed writes vec4(position px, id + 1, 1) at its texel of
// the JFA-size texture; every other texel stays 0 (no seed). Two seeds in one texel: one wins (rare, harmless).
// in0 = slot input (Source input: luma-weighted seeds), in1 = clock (x = module time).
// uVs = count source wander seed; uVs2 = jfaW jfaH jitter bias. == gen_sim_logic.seed_positions
layout (local_size_x = 64, local_size_y = 1) in;
uniform vec4 uVs;
uniform vec4 uVs2;

vec2 seedPos(int k, float t)
{
	vec2 sz = uVs2.xy;
	int n = max(int(uVs.x + 0.5), 1);
	int sd = int(uVs.w);
	int mode = int(uVs.y + 0.5);                        // 0 random, 1 grid (hex rows + jitter), 2 input luma
	float cell = sqrt(sz.x * sz.y / float(n));
	vec2 b;
	if (mode == 1) {
		int cols = max(1, int(floor(sqrt(float(n) * sz.x / sz.y) + 0.5)));
		int rows = (n + cols - 1) / cols;
		int i = k % cols, j = k / cols;
		vec2 cw = vec2(sz.x / float(cols), sz.y / float(rows));
		b = vec2((float(i) + 0.5 + 0.5 * float(j & 1)) * cw.x, (float(j) + 0.5) * cw.y)
			+ (vec2(gs_hash3(k, 1, sd), gs_hash3(k, 2, sd)) - 0.5) * uVs2.z * cw;
	} else if (mode == 2) {
		ivec2 isz = textureSize(sTD2DInputs[0], 0);
		b = vec2(0.0);
		for (int tr = 0; tr < 8; tr++) {
			b = vec2(gs_hash3(k, 2 * tr + 1, sd), gs_hash3(k, 2 * tr + 2, sd)) * sz;
			ivec2 q = clamp(ivec2(b * vec2(isz) / sz), ivec2(0), isz - 1);
			float l = gs_luma(texelFetch(sTD2DInputs[0], q, 0).rgb);
			if (gs_hash3(k, 40 + tr, sd) < pow(max(l, 0.0), uVs2.w)) break;
		}
	} else {
		b = vec2(gs_hash3(k, 1, sd), gs_hash3(k, 2, sd)) * sz;
	}
	float w1 = 0.3 + gs_hash3(k, 5, sd), w2 = 0.3 + gs_hash3(k, 6, sd);
	float p1 = 2.0 * GS_PI * gs_hash3(k, 7, sd), p2 = 2.0 * GS_PI * gs_hash3(k, 8, sd);
	b += uVs.z * cell * vec2(sin(t * w1 + p1), cos(t * w2 + p2));
	return sz - abs(mod(b, 2.0 * sz) - sz);             // reflect at the frame (seeds bounce, never pile up)
}

void main()
{
	int k = int(gl_GlobalInvocationID.x);
	if (k >= max(int(uVs.x + 0.5), 1)) return;
	float t = texelFetch(sTD2DInputs[1], ivec2(0), 0).x;
	vec2 b = seedPos(k, t);
	ivec2 px = clamp(ivec2(floor(b)), ivec2(0), ivec2(uVs2.xy) - 1);
	TDImageStoreOutput(0, ivec3(px, 0), vec4(b, float(k + 1), 1.0));
}
