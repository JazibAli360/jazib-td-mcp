// px_sound.glsl - PX_pointfx K34 data -> sound (wave 4, 27 Oct 2026): ONE compute pass, 64 x 64 blocks of the state
// texture (input 0 = update, 5 texels per point). Block b = y * 64 + x sums its points k in [b per, (b + 1) per):
// out = (sum speed |v|, sum dissolve, sum height (y - bounds centre y) / bounds radius, point count). An Analyze TOP
// (average) then gives mean = channel / count exactly (sum over blocks / sum of counts). Mirror: px_logic.ref_sound.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSn;      // count, side, bounds centre y, bounds radius

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	if (g.x >= 64 || g.y >= 64) return;
	int n = int(uSn.x + 0.5), side = max(int(uSn.y + 0.5), 1);
	int per = (n + 4095) / 4096;
	int k0 = (g.y * 64 + g.x) * per;
	vec4 s = vec4(0.0);
	float br = max(uSn.w, 1e-6);
	for (int j = 0; j < 1024; j++) {                 // per <= 1024 (4 M points); bounded loop (T-35)
		int k = k0 + j;
		if (j >= per || k >= n) break;
		ivec2 t = ivec2((k % side) * 5, k / side);
		vec4 P = texelFetch(sTD2DInputs[0], t, 0);
		vec4 V = texelFetch(sTD2DInputs[0], t + ivec2(2, 0), 0);
		vec4 M = texelFetch(sTD2DInputs[0], t + ivec2(3, 0), 0);
		s += vec4(length(V.xyz), M.w, (P.y - uSn.z) / br, 1.0);
	}
	TDImageStoreOutput(0, ivec3(g, 0), s);
}
