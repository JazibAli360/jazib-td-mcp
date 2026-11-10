// BN_cloth initial state (compute, 2W x H rgba32f): left half = rest positions, right half = zero velocity.
// Feeds the Feedback TOP `state_fb` (used on its first cook / reset). in0 = rest (W x H).
layout (local_size_x = 8, local_size_y = 8) in;

void main()
{
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	ivec2 rs = textureSize(sTD2DInputs[0], 0);
	if (c.x >= 2 * rs.x || c.y >= rs.y) return;
	vec4 o = vec4(0.0);
	if (c.x < rs.x) o = vec4(texelFetch(sTD2DInputs[0], c, 0).xyz, 1.0);
	TDImageStoreOutput(0, ivec3(c, 0), o);
}
