// px_lines_index.glsl - PX lines pass, CONNECT GRID INDEX (wave 4, PX owner, 27 Oct 2026; SA33 kNN lace on the whole
// cloud). Mirrors px_lines_logic.ref_index. Text = glsl_header() + this (no uL: its uniforms come from par expressions,
// so a static index TOP (PX's rest positions) is indexed once and never recooks with the per-frame rows).
// Input 0 = the index points (any rgba32f TOP, point id -> texel ((id % side) * stride, id / side), xyz = position).
// Output: atlas of N^3 voxels (voxel (x, y, z) -> texel (x + (z % TX) N, y + (z / TX) N)): xyz = the position of ONE
// representative point of the voxel, w = its id + 1 (0 = empty voxel). Representative = smallest key
// (priority << 22 | id): priority = pcg(id) >> 22 (random pick) or the distance to the voxel centre (centre pick).
// One workgroup per 8^3 brick (dispatch N/8 per axis); its 512 threads walk every point and keep the brick's keys with
// shared-memory uint atomics (no image atomics, lane E / T-124 rule). Cost = points x bricks, once per index change.
layout(local_size_x = 8, local_size_y = 8, local_size_z = 8) in;
uniform vec4 uCnG;     // origin xyz (min corner), cell
uniform vec4 uCnN;     // N, TX, stride, count (0 = every texel)
uniform vec4 uCnP;     // pick (0 random, 1 centre), 0, 0, 0
shared uint sKey[512];

uint ixPcg(uint v)
{
	uint s = v * 747796405u + 2891336453u;
	uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
	return (w >> 22u) ^ w;
}

void main()
{
	uint li = gl_LocalInvocationIndex;
	sKey[li] = 0xFFFFFFFFu;
	barrier();
	memoryBarrierShared();
	int N = int(uCnN.x + 0.5), tx = max(int(uCnN.y + 0.5), 1), stride = max(int(uCnN.z + 0.5), 1);
	ivec3 b0 = ivec3(gl_WorkGroupID) * 8;
	float cell = max(uCnG.w, 1e-9);
	ivec2 psz = textureSize(sTD2DInputs[0], 0);
	int side = max(psz.x / stride, 1);
	int P = min(side * psz.y, 4194304);
	int cnt = int(uCnN.w + 0.5);
	if (cnt > 0) P = min(P, cnt);
	bool centre = uCnP.x > 0.5;
	for (int k = int(li); k < P; k += 512) {
		vec3 q = texelFetch(sTD2DInputs[0], ivec2((k % side) * stride, k / side), 0).xyz;
		vec3 g = (q - uCnG.xyz) / cell;
		ivec3 v = ivec3(floor(g));
		ivec3 r = v - b0;
		if (any(lessThan(r, ivec3(0))) || any(greaterThanEqual(r, ivec3(8))) || any(greaterThanEqual(v, ivec3(N))))
			continue;
		uint pr;
		if (centre) pr = uint(min(length(g - (vec3(v) + 0.5)) * (1023.0 / 0.8660254) + 0.5, 1023.0));
		else pr = ixPcg(uint(k)) >> 22u;
		atomicMin(sKey[uint(r.x + 8 * (r.y + 8 * r.z))], (pr << 22u) | uint(k));
	}
	barrier();
	memoryBarrierShared();
	ivec3 v = b0 + ivec3(gl_LocalInvocationID);
	if (any(greaterThanEqual(v, ivec3(N)))) return;
	ivec2 a = ivec2(v.x + (v.z % tx) * N, v.y + (v.z / tx) * N);
	uint key = sKey[li];
	vec4 o = vec4(0.0);
	if (key != 0xFFFFFFFFu) {
		int id = int(key & 0x3FFFFFu);
		o = vec4(texelFetch(sTD2DInputs[0], ivec2((id % side) * stride, id / side), 0).xyz, float(id) + 1.0);
	}
	TDImageStoreOutput(0, ivec3(a, 0), o);
}
