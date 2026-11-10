// BN_cloth per-vertex stats (compute, W x H rgba32f) = cloth_logic.stats_ref:
// r = max strain |len/L - 1| of its structural springs, g = kinetic energy 0.5 m v^2, b = 1 if position or velocity
// is not finite, a = mean strain. Analyze TOPs (average, maximum) reduce it for out3. in0 = state, in1 = rest.
layout (local_size_x = 8, local_size_y = 8) in;
uniform samplerBuffer uP;

vec4 R(int k) { return texelFetch(uP, k); }

void main()
{
	vec4 grid = R(R_GRID);
	int W = int(grid.x + 0.5), H = int(grid.y + 0.5);
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	if (c.x >= W || c.y >= H) return;
	if (textureSize(sTD2DInputs[0], 0) != ivec2(2 * W, H)) { TDImageStoreOutput(0, ivec3(c, 0), vec4(0.0)); return; }
	vec3 p = texelFetch(sTD2DInputs[0], c, 0).xyz;
	vec3 v = texelFetch(sTD2DInputs[0], ivec2(c.x + W, c.y), 0).xyz;
	float smax = 0.0, ssum = 0.0, cnt = 0.0;
	for (int k = 0; k < 4; k++) {                               // STENCIL[0..3] = structural
		ivec2 n = c + STENCIL[k].xy;
		if (n.x < 0 || n.y < 0 || n.x >= W || n.y >= H) continue;
		float L = length(vec2(STENCIL[k].xy) * grid.zw);
		float s = abs(length(p - texelFetch(sTD2DInputs[0], n, 0).xyz) / L - 1.0);
		smax = max(smax, s);
		ssum += s;
		cnt += 1.0;
	}
	float winv = R(R_MASS).y;
	float m = winv > 0.0 ? 1.0 / winv : 0.0;
	bool bad = any(isnan(p)) || any(isinf(p)) || any(isnan(v)) || any(isinf(v));
	TDImageStoreOutput(0, ivec3(c, 0), vec4(smax, 0.5 * m * dot(v, v), bad ? 1.0 : 0.0, ssum / max(cnt, 1.0)));
}
