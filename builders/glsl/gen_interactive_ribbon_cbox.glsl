// gen_interactive_ribbon_cbox: one bounding box per chunk of 256 segments (compute, ceil(segments / 256) x 1,
// rgba32float; manual dispatch: one 256-thread workgroup per chunk). in0 = segments (`segs`). Texel c = (min x, min y,
// max x, max y) px of the valid segments g = c x 256 .. c x 256 + 255, each grown by its half width; an empty chunk
// = (1e9, 1e9, -1e9, -1e9). The draw pass skips a whole chunk (no barriers, uniform per workgroup) when the box,
// grown by the glow / edge reach, misses its tile. == builders/gen_interactive_ribbon_logic.py chunk_boxes.
layout (local_size_x = 256, local_size_y = 1) in;

shared vec4 bx[256];

void main()
{
	ivec2 gsz = textureSize(sTD2DInputs[0], 0);
	int SW = gsz.x / 3;
	int total = SW * gsz.y;
	uint li = gl_LocalInvocationIndex;
	int c = int(gl_WorkGroupID.x);
	int g = c * 256 + int(li);
	vec4 b = vec4(1e9, 1e9, -1e9, -1e9);
	if (g < total) {
		ivec2 t0 = ivec2(3 * (g % SW), g / SW);
		vec4 Cv = texelFetch(sTD2DInputs[0], t0 + ivec2(2, 0), 0);
		if (Cv.w > 0.5) {
			vec4 A = texelFetch(sTD2DInputs[0], t0, 0);
			vec4 Bv = texelFetch(sTD2DInputs[0], t0 + ivec2(1, 0), 0);
			if (max(Bv.z, Bv.w) > 0.0) {
				float rr = 0.5 * max(Bv.x, Bv.y);
				b = vec4(min(A.xy, A.zw) - rr, max(A.xy, A.zw) + rr);
			}
		}
	}
	bx[li] = b;
	for (uint off = 128u; off > 0u; off >>= 1u) {
		barrier();
		if (li < off) {
			vec4 o = bx[li + off];
			bx[li] = vec4(min(bx[li].xy, o.xy), max(bx[li].zw, o.zw));
		}
	}
	barrier();
	if (li == 0u) TDImageStoreOutput(0, ivec3(c, 0, 0), bx[0]);
}
