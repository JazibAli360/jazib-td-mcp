// MX_prox_material point-set pass `pts` (compute, after header; W x 2H rgba32f): source TOP texels -> world points
// (stride decimated to M = min(N, Pointmax), point xform rows MX_PXF0..2) + velocity (frame difference vs the previous
// output, smoothed by Velsmooth). in0 = pts_src (Script TOP of a CHOP/SOP/POP, or the user's TOP), in1 = pts_fb.
layout (local_size_x = 8, local_size_y = 8) in;

int mxI(float x) { return int(floor(x + 0.5)); }

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	int W = mxI(MX_PTS.y), H = mxI(MX_PTS.z), M = mxI(MX_PTS.x);
	if (g.x >= W || g.y >= H) return;
	int i = g.y * W + g.x;
	vec4 pos = vec4(0.0), vel = vec4(0.0);
	if (i < M) {
		int N = max(mxI(MX_PTS2.w), 1);
		int j = (M < N) ? int(floor(float(i) * float(N) / float(M))) : i;
		int sw = max(mxI(MX_PSRC.x), 1);
		int tx = j * max(mxI(MX_PSRC.z), 1) + mxI(MX_PSRC.w);
		vec4 s = texelFetch(sTD2DInputs[0], ivec2(tx % sw, tx / sw), 0);
		vec4 h = vec4(s.xyz, 1.0);
		vec3 q = vec3(dot(MX_PXF0, h), dot(MX_PXF1, h), dot(MX_PXF2, h));
		pos = vec4(q, 1.0);
		vec4 pp = texelFetch(sTD2DInputs[1], g, 0);
		if (pp.a > 0.5) {
			vec4 pv = texelFetch(sTD2DInputs[1], ivec2(g.x, g.y + H), 0);
			vec3 v = (q - pp.xyz) / max(uMXT.y, 1e-4);
			v = mix(v, pv.xyz, clamp(MX_PTS2.z, 0.0, 0.999));
			if (any(isnan(v)) || any(isinf(v))) v = vec3(0.0);
			vel = vec4(v, length(v));
		}
	}
	TDImageStoreOutput(0, ivec3(g, 0), pos);
	TDImageStoreOutput(0, ivec3(g.x, g.y + H, 0), vel);
}
