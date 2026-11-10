// eff_grid_jfa (compute GLSL TOP, 8 chained passes in /project1/effectors/grid; numpy twin
// effectors_grid_logic.jfa_pass_ref): 3D jump flooding on the seed atlas (input 0: nearest seed so far, world xyz +
// has). Step uJfa.x = N/2 .. 1, then 1 (JFA+1), then 0 = copy (effectors_grid_logic.jfa_steps). Per voxel: its own
// seed, then 26 taps at +-step (dz, dy, dx from -1 to 1); the seed nearest to the voxel centre wins (strict <).
layout(local_size_x = 8, local_size_y = 8) in;
uniform vec4 uGrid;    // origin xyz (min corner), cell size
uniform vec4 uGridN;   // N, tiles across, 0, 0
uniform vec4 uJfa;     // step, 0, 0, 0

ivec2 gridAtlas(ivec3 v, int N, int tx) { return ivec2(v.x + (v.z % tx) * N, v.y + (v.z / tx) * N); }

void main()
{
	ivec2 a = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (a.x >= sz.x || a.y >= sz.y) return;
	vec4 best = vec4(0.0);
#if defined(TD_NUM_2D_INPUTS) && TD_NUM_2D_INPUTS > 0
	int N = int(uGridN.x + 0.5), tx = int(uGridN.y + 0.5);
	int z = (a.y / N) * tx + a.x / N;
	best = texelFetch(sTD2DInputs[0], a, 0);
	int k = int(uJfa.x + 0.5);
	if (z < N && k > 0) {
		ivec3 v = ivec3(a.x % N, a.y % N, z);
		vec3 c = uGrid.xyz + (vec3(v) + 0.5) * uGrid.w;
		float bd = best.w > 0.5 ? dot(best.xyz - c, best.xyz - c) : 3.4e38;
		for (int dz = -1; dz <= 1; dz++)
		for (int dy = -1; dy <= 1; dy++)
		for (int dx = -1; dx <= 1; dx++) {
			if (dx == 0 && dy == 0 && dz == 0) continue;
			ivec3 n = v + ivec3(dx, dy, dz) * k;
			if (any(lessThan(n, ivec3(0))) || any(greaterThanEqual(n, ivec3(N)))) continue;
			vec4 s = texelFetch(sTD2DInputs[0], gridAtlas(n, N, tx), 0);
			if (s.w < 0.5) continue;
			float d = dot(s.xyz - c, s.xyz - c);
			if (d < bd) { bd = d; best = s; }
		}
	}
	if (z >= N) best = vec4(0.0);
#endif
	TDImageStoreOutput(0, ivec3(a, 0), best);
}
