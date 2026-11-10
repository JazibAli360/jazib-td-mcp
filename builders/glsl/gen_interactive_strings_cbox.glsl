// gen_interactive_strings_cbox: one bounding box per chunk of 8 segments of a string (compute, ceil((K - 1) / 8) x S,
// rgba32float: min x y, max x y frame px). in0 = string state. The draw's tile lists test these boxes instead of
// every segment (ribbon cbox pattern).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS;      // strings S, nodes K, orient, margin
uniform vec4 uSz;     // frame W, H, -, -

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	int S = max(int(uS.x + 0.5), 1), K = clamp(int(uS.y + 0.5), 2, 256);
	int C = (K - 1 + 7) / 8;
	if (p.x >= C || p.y >= S) return;
	vec2 lo = vec2(1e30), hi = vec2(-1e30);
	ivec2 ssz = textureSize(sTD2DInputs[0], 0);
	bool ok = ssz.x == K && ssz.y == S + 1;
	for (int i = 0; i <= 8; i++) {
		int k = p.x * 8 + i;
		if (k >= K) break;
		float c = uS.w + (float(p.y) + 0.5) / float(S) * (1.0 - 2.0 * uS.w);
		float a = float(k) / float(K - 1);
		vec2 r = uS.z < 0.5 ? vec2(c * uSz.x, a * uSz.y) : vec2(a * uSz.x, c * uSz.y);
		vec2 q = r + (ok ? texelFetch(sTD2DInputs[0], ivec2(k, p.y), 0).xy : vec2(0.0));
		lo = min(lo, q);
		hi = max(hi, q);
	}
	TDImageStoreOutput(0, ivec3(p, 0), vec4(lo, hi));
}
