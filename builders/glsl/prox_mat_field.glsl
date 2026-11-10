// MX_prox_material field pass `field` (compute, after header + px_common; R*T x 2*R*T rgba32f atlas, layout in
// px_common pxFieldFetch): per grid cell the nearest point distance, the soft density (density mode only) and the
// nearest point's velocity, brute force over the M points of `pts` (in0). numpy twin: prox_mat_logic.ref_field.
layout (local_size_x = 8, local_size_y = 8) in;

int mxI(float x) { return int(floor(x + 0.5)); }

void main()
{
	int R = max(mxI(MX_GRID.w), 1), T = max(mxI(MX_GRID2.w), 1);
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	if (g.x >= R * T || g.y >= R * T) return;
	int z = (g.y / R) * T + g.x / R;
	vec4 o0 = vec4(1e9, 0.0, 0.0, 0.0), o1 = vec4(0.0);
	if (z < R) {
		vec3 c = vec3(float(g.x % R), float(g.y % R), float(z));
		vec3 p = MX_GRID.xyz + (c + 0.5) / float(R) * MX_GRID2.xyz;
		int W = mxI(MX_PTS.y), H = mxI(MX_PTS.z), M = mxI(MX_PTS.x);
		int bi;
		float d = pxPtsNearest(sTD2DInputs[0], p, M, W, H, bi);
		float D = (mxI(MX_PTS2.x) == 1) ? pxPtsDensity(sTD2DInputs[0], p, M, W, H, max(MX_PTS.w, 1e-4)) : 0.0;
		o0 = vec4(d, D, 0.0, 1.0);
		if (bi >= 0) o1 = pxPtsTexel(sTD2DInputs[0], bi, W, H, 1);
	}
	TDImageStoreOutput(0, ivec3(g, 0), o0);
	TDImageStoreOutput(0, ivec3(g.x, g.y + R * T, 0), o1);
}
