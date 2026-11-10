// gen_interactive_pigment_splat: particles -> pigment dots (compute scatter, trail res = Quality x slot size,
// rgba16float, clearoutputs on, manual dispatch ceil(Side / 8)^2: one thread per particle, T-138 dust pattern).
// in0 = state, in1 = colour source (`colsrc`: the Atlas TOP in Colormode atlas when set, else the slot input).
// Each live particle stores a Size x Quality px square (1..16 px, last write wins, no atomics) of premultiplied
// colour x a, a = Opacity x fade-in / fade-out over the first / last Agefade share of its life. Untouched texels = 0.
// Colour (Colormode): 0 source = colsrc at the anchor, 1 atlas = Atlascells^2 images: cell (floor(seed x N^2) +
// T x Atlasrate) mod N^2 cross-faded into the next cell (the 'latent morph'), uv in the cell = anchor / frame,
// 2 speed = palette(speed / Speedref), 3 age = palette(age / life), 4 seed = palette(seed).
// == builders/gen_interactive_pigment_logic.py splat.  uS = Side, Size, Opacity, Agefade; uC = Colormode,
// Atlascells, Atlasrate, Speedref; uQ = Quality, W, H, 0.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS;
uniform vec4 uC;
uniform vec4 uQ;

vec3 cellCol(vec2 uv, float cell, float N)
{
	float c = mod(cell, N * N);
	vec2 o = vec2(mod(c, N), floor(c / N));
	return texture(sTD2DInputs[1], (o + clamp(uv, 0.0, 1.0)) / N).rgb;
}

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	int S = int(uS.x + 0.5);
	if (g.x >= S || g.y >= S) return;
	vec4 A = texelFetch(sTD2DInputs[0], ivec2(2 * g.x, g.y), 0);
	vec4 Bv = texelFetch(sTD2DInputs[0], ivec2(2 * g.x + 1, g.y), 0);
	if (A.w <= 0.0 || A.z < 0.0) return;
	float T = texelFetch(sTD2DInputs[0], ivec2(0, S), 0).y;
	vec2 sz = uQ.yz;
	float af = max(uS.w, 1e-4) * A.w;
	float a = uS.z * clamp(A.z / af, 0.0, 1.0) * clamp((A.w - A.z) / af, 0.0, 1.0);
	if (a <= 0.0) return;
	int mode = int(uC.x + 0.5);
	vec3 col;
	vec2 uv = Bv.xy / sz;
	if (mode == 0) col = texture(sTD2DInputs[1], uv).rgb;
	else if (mode == 1) {
		float N = max(floor(uC.y + 0.5), 1.0);
		float k = Bv.z * N * N + T * uC.z;
		float f = fract(k);
		col = mix(cellCol(uv, floor(k), N), cellCol(uv, floor(k) + 1.0, N), f * f * (3.0 - 2.0 * f));
	} else if (mode == 2) col = gs_pal(Bv.w / max(uC.w, 1e-6));
	else if (mode == 3) col = gs_pal(A.z / A.w);
	else col = gs_pal(Bv.z);
	ivec2 osz = ivec2(max(vec2(1.0), floor(sz * uQ.x + 0.5)));
	int s = clamp(int(uS.y * uQ.x + 0.5), 1, 16);
	ivec2 c0 = ivec2(floor(A.xy * uQ.x)) - ivec2((s - 1) / 2);
	vec4 o = vec4(col * a, a);
	for (int dy = 0; dy < 16; dy++) {
		if (dy >= s) break;
		for (int dx = 0; dx < 16; dx++) {
			if (dx >= s) break;
			ivec2 q = c0 + ivec2(dx, dy);
			if (q.x >= 0 && q.y >= 0 && q.x < osz.x && q.y < osz.y) TDImageStoreOutput(0, ivec3(q, 0), o);
		}
	}
}
