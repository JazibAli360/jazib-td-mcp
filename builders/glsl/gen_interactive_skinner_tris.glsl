// gen_interactive_skinner_tris: GEN_interactive 'skinner' shards (compute, 128 x ceil(M / 64), rgba32f). in0 = slots.
// Shard j (texels 2 (j % 64) + 0 / 1, row j / 64) = (A.xy, B.xy), (C.xy, alpha, colour t). Every shard re-rolls its
// three slots Rerollhz times / s (phase staggered per shard): up to 6 hashed triples of valid slots, kept when the
// longest edge is in Minlen..Maxlen px (Skinner's long-triangle pick); shown with chance Density + Motiongain x the
// mean motion of its slots; alpha = sin(pi x phase fraction) (fades in and out over its life). The vertices follow the
// slots' current points, so shards stick to the body. == builders/gen_interactive_skinner_logic.py tris.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uR;      // shards M, reroll / s, min edge px, max edge px
uniform vec4 uD;      // density, motion gain, seed, slots N

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	int M = max(int(uR.x + 0.5), 1), N = max(int(uD.w + 0.5), 1), R = (N + 63) / 64;
	int j = p.y * 64 + p.x / 2;
	if (p.x >= 128 || j >= M) return;
	ivec2 ssz = textureSize(sTD2DInputs[0], 0);
	bool ok = ssz.x == 64 && ssz.y == R + 1;
	float T = ok ? texelFetch(sTD2DInputs[0], ivec2(0, R), 0).y : 0.0;
	int sd = int(uD.z + 0.5);
	float ph = T * uR.y + gs_hash3(j, 7, sd);
	int ep = int(floor(ph));
	float f = ph - floor(ph);
	vec4 A = vec4(0.0), B = vec4(0.0), C = vec4(0.0);
	bool got = false;
	for (int t = 0; t < 6; t++) {
		if (!ok) break;
		int a = min(int(gs_hash3(j, ep * 6 + t, sd + 3) * float(N)), N - 1);
		int b = min(int(gs_hash3(j, ep * 6 + t, sd + 4) * float(N)), N - 1);
		int c = min(int(gs_hash3(j, ep * 6 + t, sd + 5) * float(N)), N - 1);
		if (a == b || b == c || a == c) continue;
		A = texelFetch(sTD2DInputs[0], ivec2(a % 64, a / 64), 0);
		B = texelFetch(sTD2DInputs[0], ivec2(b % 64, b / 64), 0);
		C = texelFetch(sTD2DInputs[0], ivec2(c % 64, c / 64), 0);
		if (A.z < 0.5 || B.z < 0.5 || C.z < 0.5) continue;
		float L = max(max(length(B.xy - A.xy), length(C.xy - B.xy)), length(A.xy - C.xy));
		if (L >= uR.z && L <= uR.w) { got = true; break; }
	}
	float mo = (A.w + B.w + C.w) / 3.0;
	bool show = got && gs_hash3(j, ep, sd + 9) < uD.x + uD.y * mo;
	float al = show ? sin(3.14159265 * f) : 0.0;
	vec4 o = (p.x & 1) == 0 ? vec4(A.xy, B.xy) : vec4(C.xy, al, gs_hash3(j, ep, sd + 11));
	TDImageStoreOutput(0, ivec3(p, 0), o);
}
