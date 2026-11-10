// gen_interactive_ribbon_draw: segments -> picture over the slot input (compute, slot input size, 16x16 groups).
// in0 = slot input, in1 = segments (`segs`, 3 texels per segment), in2 = chunk boxes (`cbox`). Each workgroup walks
// the segment list in chunks of 256 (one per thread): a chunk whose box (+ reach) misses the tile is skipped whole
// (uniform per workgroup, no barriers); else a thread keeps its segment if the tapered capsule (+ glow / edge reach)
// touches the 16x16 tile, an ordered prefix sum (no atomics, as gen_sim_blobs) packs the kept ones into shared memory, every pixel
// shades that list, then the next chunk. Any segment count works (cost grows with it); nothing is dropped.
// Tapered capsule: d = distance to the segment, r = mix(w0, w1, h) / 2, sd = d - r, coverage clamp(0.5 - sd, 0, 1)
// (1 px AA), alpha = mix(a0, a1, h). Style 0 solid (the strongest segment's colour wins: clean joins), 1 light
// (additive), 2 outline (|sd| < Edge / 2). Glow (all styles): + colour x alpha x Glow x exp(-max(sd, 0) / Glowwidth)
// where sd < 4.5 Glowwidth (1.1 %: the cull reach).
// == builders/gen_interactive_ribbon_logic.py draw.  uD = Style, Glow, Glowwidth, Edge.
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uD;

shared vec4 sA[256];
shared vec4 sB[256];
shared vec4 sC[256];
shared uint scn[2 * 256];
shared uint nlist;

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	ivec2 gsz = textureSize(sTD2DInputs[1], 0);
	int SW = gsz.x / 3;
	int total = SW * gsz.y;
	uint li = gl_LocalInvocationIndex;
	vec2 lo = vec2(gl_WorkGroupID.xy * 16u), hi = lo + 16.0;
	int style = int(uD.x + 0.5);
	float glow = max(uD.y, 0.0), gw = max(uD.z, 1e-3), edge = max(uD.w, 0.0);
	float pad = 1.0 + edge + (glow > 0.0 ? gw * 4.5 : 0.0);   // glow cut at exp(-4.5) = 1.1 %
	bool inside = p.x < osz.x && p.y < osz.y;
	vec2 x = vec2(p) + 0.5;
	float best = 0.0, asum = 0.0;
	vec3 bcol = vec3(0.0), csum = vec3(0.0), gsum = vec3(0.0);
	for (int base = 0; base < total; base += 256) {
		vec4 cb = texelFetch(sTD2DInputs[2], ivec2(base / 256, 0), 0);
		if (cb.z + pad < lo.x || cb.x - pad > hi.x || cb.w + pad < lo.y || cb.y - pad > hi.y) continue;
		int g = base + int(li);
		uint mine = 0u;
		vec4 A = vec4(0.0), Bv = vec4(0.0), Cv = vec4(0.0);
		if (g < total) {
			ivec2 t0 = ivec2(3 * (g % SW), g / SW);
			Cv = texelFetch(sTD2DInputs[1], t0 + ivec2(2, 0), 0);
			if (Cv.w > 0.5) {
				A = texelFetch(sTD2DInputs[1], t0, 0);
				Bv = texelFetch(sTD2DInputs[1], t0 + ivec2(1, 0), 0);
				float rr = 0.5 * max(Bv.x, Bv.y) + pad;
				vec2 bmin = min(A.xy, A.zw) - rr, bmax = max(A.xy, A.zw) + rr;
				if (max(Bv.z, Bv.w) > 0.0 && bmax.x >= lo.x && bmin.x <= hi.x && bmax.y >= lo.y && bmin.y <= hi.y)
					mine = 1u;
			}
		}
		scn[li] = mine;
		uint src = 0u;
		for (uint off = 1u; off < 256u; off <<= 1u) {
			barrier();
			uint v = scn[src * 256u + li];
			if (li >= off) v += scn[src * 256u + li - off];
			scn[(1u - src) * 256u + li] = v;
			src = 1u - src;
		}
		barrier();
		uint start = scn[src * 256u + li] - mine;
		if (mine == 1u) { sA[start] = A; sB[start] = Bv; sC[start] = Cv; }
		if (li == 255u) nlist = scn[src * 256u + li];
		barrier();
		if (inside) {
			uint nl = nlist;
			for (uint k = 0u; k < nl; k++) {
				vec4 a = sA[k], b = sB[k];
				float h;
				float d = gi_segdist(x, a.xy, a.zw, h);
				float sd = d - 0.5 * mix(b.x, b.y, h);
				float al = mix(b.z, b.w, h);
				vec3 c = sC[k].rgb;
				if (glow > 0.0 && sd < 4.5 * gw) gsum += c * (al * glow * exp(-max(sd, 0.0) / gw));
				float v;
				if (style == 2) v = al * clamp(0.5 + 0.5 * edge - abs(sd), 0.0, 1.0);
				else v = al * clamp(0.5 - sd, 0.0, 1.0);
				if (style == 1) { csum += c * v; asum += v; }
				else if (v > best) { best = v; bcol = c; }
			}
		}
		barrier();
	}
	if (!inside) return;
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	vec3 col;
	float a;
	if (style == 1) { col = csum + gsum; a = clamp(asum + gs_luma(gsum), 0.0, 1.0); }
	else { col = bcol * best + gsum; a = clamp(best + gs_luma(gsum), 0.0, 1.0); }
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col, a));
}
