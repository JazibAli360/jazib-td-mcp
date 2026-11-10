// eff_grid_seed (compute GLSL TOP, /project1/effectors/grid; numpy twin effectors_grid_logic.seeds_ref): the scatter
// atlas (input 0: sum of cell-local offsets xyz, count) -> seeds (world centroid xyz, 1) for voxels with points, else 0.
// Atlas texels outside the used tiles are written 0. Output = the atlas size, auto dispatch (8 x 8).
layout(local_size_x = 8, local_size_y = 8) in;
uniform vec4 uGrid;    // origin xyz (min corner), cell size
uniform vec4 uGridN;   // N, tiles across, 0, 0

void main()
{
	ivec2 a = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (a.x >= sz.x || a.y >= sz.y) return;
	int N = int(uGridN.x + 0.5), tx = int(uGridN.y + 0.5);
	int z = (a.y / N) * tx + a.x / N;
	vec4 o = vec4(0.0);
#if defined(TD_NUM_2D_INPUTS) && TD_NUM_2D_INPUTS > 0
	if (z < N) {
		vec4 s = texelFetch(sTD2DInputs[0], a, 0);
		if (s.w > 0.5) o = vec4(uGrid.xyz + (vec3(a.x % N, a.y % N, z) + s.xyz / s.w) * uGrid.w, 1.0);
	}
#endif
	TDImageStoreOutput(0, ivec3(a, 0), o);
}
