// BN_cloth jelly covariance, one row group per node (compute, W x H rgba32f): for group g (uCov.x = 0 x, 1 y, 2 z)
// writes (p_g q.x, p_g q.y, p_g q.z, p_g) with q = rest - rest centroid. An Analyze TOP (average) of each gives row g
// of A = mean(p q^T) and centroid component g (cloth_logic.cov_from_chop, COV_CHANS). in0 = state_fb (last frame,
// so the engine reading it makes no cook loop), in1 = rest. Cooks only in Mode = jelly (the engine reads it then).
layout (local_size_x = 8, local_size_y = 8) in;
uniform samplerBuffer uP;
uniform vec4 uCov;     // group index, 0, 0, 0

vec4 R(int k) { return texelFetch(uP, k); }

void main()
{
	vec4 grid = R(R_GRID);
	int W = int(grid.x + 0.5), H = int(grid.y + 0.5);
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	if (c.x >= W || c.y >= H) return;
	if (textureSize(sTD2DInputs[0], 0) != ivec2(2 * W, H) || textureSize(sTD2DInputs[1], 0) != ivec2(W, H)) {
		TDImageStoreOutput(0, ivec3(c, 0), vec4(0.0));
		return;
	}
	vec3 p = texelFetch(sTD2DInputs[0], c, 0).xyz;
	vec3 q = texelFetch(sTD2DInputs[1], c, 0).xyz - R(R_REST).xyz;
	int g = int(uCov.x + 0.5);
	float pg = g == 0 ? p.x : (g == 1 ? p.y : p.z);
	TDImageStoreOutput(0, ivec3(c, 0), vec4(pg * q, pg));
}
