// eff_grid_scatter (compute GLSL TOP; /project1/effectors/grid, one pass per enabled `cloud` effector, chained; lane E,
// 27 Oct 2026; numpy twin effectors_grid_logic.scatter_ref; doc docs/builds/effectors.md "Voxel grid").
// Adds the points of input 1 (any TOP: rgb = xyz in the cloud object's space, alpha > uGridN.w = valid) into the grid
// atlas: out = input 0 (the previous pass; uGridN.z = 0: none) + (sum of cell-local offsets xyz, count) per voxel.
// One workgroup = one 8^3 brick (dispatch N/8 x N/8 x N/8); its 512 threads walk every point and add the ones inside
// the brick with shared-memory uint atomics (exact; no image atomics, FX2 / fx_scope rule). Offsets in fixed point
// (x 1024). The cloud object's transform comes from its packed row (inverse world rows 0..2, row uCloud.x).
layout(local_size_x = 8, local_size_y = 8, local_size_z = 8) in;
uniform vec4 uGrid;    // origin xyz (min corner), cell size
uniform vec4 uGridN;   // N, tiles across, has previous (input 0), alpha threshold
uniform vec4 uCloud;   // packed row index of the cloud effector, 0, 0, 0
uniform samplerBuffer uEffRows;
shared uint sCnt[512];
shared uint sX[512];
shared uint sY[512];
shared uint sZ[512];
const float GRID_FX = 1024.0;

ivec2 gridAtlas(ivec3 v, int N, int tx) { return ivec2(v.x + (v.z % tx) * N, v.y + (v.z / tx) * N); }

void main()
{
	uint li = gl_LocalInvocationIndex;
	sCnt[li] = 0u;
	sX[li] = 0u;
	sY[li] = 0u;
	sZ[li] = 0u;
	barrier();
	memoryBarrierShared();
	int N = int(uGridN.x + 0.5), tx = int(uGridN.y + 0.5);
	ivec3 b0 = ivec3(gl_WorkGroupID) * 8;
	int row = 1 + int(uCloud.x + 0.5) * 10;
	mat4 inv = mat4(1.0);
	if (row + 2 < textureSize(uEffRows)) {
		vec4 r0 = texelFetch(uEffRows, row), r1 = texelFetch(uEffRows, row + 1), r2 = texelFetch(uEffRows, row + 2);
		inv = transpose(mat4(r0, r1, r2, vec4(0.0, 0.0, 0.0, 1.0)));       // world -> local (rows r0 r1 r2)
	}
	mat4 xf = inverse(inv);                                                // local -> world
#if defined(TD_NUM_2D_INPUTS) && TD_NUM_2D_INPUTS > 1
	ivec2 psz = textureSize(sTD2DInputs[1], 0);
	int P = psz.x * psz.y;
	for (int k = int(li); k < P; k += 512) {
		vec4 q = texelFetch(sTD2DInputs[1], ivec2(k % psz.x, k / psz.x), 0);
		if (q.a <= uGridN.w) continue;
		vec3 g = ((xf * vec4(q.xyz, 1.0)).xyz - uGrid.xyz) / uGrid.w;
		ivec3 v = ivec3(floor(g));
		ivec3 r = v - b0;
		if (any(lessThan(r, ivec3(0))) || any(greaterThanEqual(r, ivec3(8))) || any(greaterThanEqual(v, ivec3(N))))
			continue;
		uint idx = uint(r.x + 8 * (r.y + 8 * r.z));
		vec3 f = clamp(g - vec3(v), 0.0, 1.0);
		atomicAdd(sCnt[idx], 1u);
		atomicAdd(sX[idx], uint(f.x * GRID_FX + 0.5));
		atomicAdd(sY[idx], uint(f.y * GRID_FX + 0.5));
		atomicAdd(sZ[idx], uint(f.z * GRID_FX + 0.5));
	}
#endif
	barrier();
	memoryBarrierShared();
	ivec3 v = b0 + ivec3(gl_LocalInvocationID);
	if (any(greaterThanEqual(v, ivec3(N)))) return;
	ivec2 a = gridAtlas(v, N, tx);
	vec4 prev = vec4(0.0);
#if defined(TD_NUM_2D_INPUTS) && TD_NUM_2D_INPUTS > 0
	if (uGridN.z > 0.5) prev = texelFetch(sTD2DInputs[0], a, 0);
#endif
	TDImageStoreOutput(0, ivec3(a, 0), prev + vec4(vec3(float(sX[li]), float(sY[li]), float(sZ[li])) / GRID_FX,
	                                              float(sCnt[li])));
}
