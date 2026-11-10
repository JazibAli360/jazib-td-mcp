// BN_cloth frame-start normals (compute, W x H rgba32f) for the wind term. = cloth_logic.normals_ref:
// central differences, one-sided at the edges, (0,0,1) when degenerate. in0 = state_fb (2W x H, positions left).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uGrid;    // W, H, 0, 0

void main()
{
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	ivec2 G = ivec2(uGrid.xy + 0.5);
	if (c.x >= G.x || c.y >= G.y) return;
	vec3 n = vec3(0.0, 0.0, 1.0);
	if (textureSize(sTD2DInputs[0], 0) == ivec2(2 * G.x, G.y)) {
		vec3 pe = texelFetch(sTD2DInputs[0], ivec2(min(c.x + 1, G.x - 1), c.y), 0).xyz;
		vec3 pw = texelFetch(sTD2DInputs[0], ivec2(max(c.x - 1, 0), c.y), 0).xyz;
		vec3 pn = texelFetch(sTD2DInputs[0], ivec2(c.x, min(c.y + 1, G.y - 1)), 0).xyz;
		vec3 ps = texelFetch(sTD2DInputs[0], ivec2(c.x, max(c.y - 1, 0)), 0).xyz;
		vec3 x = cross(pe - pw, pn - ps);
		float l = length(x);
		if (l > 1e-12) n = x / l;
	}
	TDImageStoreOutput(0, ivec3(c, 0), vec4(n, 0.0));
}
