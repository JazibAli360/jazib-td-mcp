// rd_common: prefixed to every GN_reaction_diffusion pass by builders/reaction_diffusion.py (compute, T-46/T-47).
// Constants and formulas == builders/reaction_diffusion_logic.py (test/test_reaction_diffusion.py checks). TD adds the version line.
// State texel: r = A, g = B, b = local morph (effectors), a = solid. Edge e: 0 wrap, 1 clamp.
#define NROWS 32
#define ROW_TEXELS 2
#define LAP_EDGE 0.2
#define LAP_DIAG 0.05
#define ANISO_TRACE 0.6
#define PI 3.14159265358979

uint hashu(uint x)
{
	x ^= x >> 16u; x *= 0x7feb352du; x ^= x >> 15u; x *= 0x846ca68bu; x ^= x >> 16u;
	return x;
}

float hash3(int i, int j, int s)
{
	uint h = hashu(uint(i) + hashu(uint(j) + hashu(uint(s))));
	return float(h >> 8u) * (1.0 / 16777216.0);
}

float vnoise(vec2 p, int s)
{
	vec2 i = floor(p);
	vec2 f = p - i;
	ivec2 q = ivec2(i);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = hash3(q.x, q.y, s), b = hash3(q.x + 1, q.y, s);
	float c = hash3(q.x, q.y + 1, s), d = hash3(q.x + 1, q.y + 1, s);
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

int wrapi(int x, int n) { return x - n * int(floor(float(x) / float(n))); }

ivec2 edgeT(ivec2 t, ivec2 sz, int e)
{
	if (e == 0) return ivec2(wrapi(t.x, sz.x), wrapi(t.y, sz.y));
	return clamp(t, ivec2(0), sz - 1);
}

// input 0 fetch / bilinear (texel space, centres at i + 0.5), edge rule e
vec4 F0(ivec2 t, int e)
{
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	return texelFetch(sTD2DInputs[0], edgeT(t, sz, e), 0);
}

vec4 BL0(vec2 p, int e)
{
	vec2 x = p - 0.5;
	vec2 i = floor(x);
	vec2 f = x - i;
	ivec2 q = ivec2(i);
	vec4 a00 = F0(q, e), a10 = F0(q + ivec2(1, 0), e), a01 = F0(q + ivec2(0, 1), e), a11 = F0(q + ivec2(1, 1), e);
	return mix(mix(a00, a10, f.x), mix(a01, a11, f.x), f.y);
}

float falloffW(float d, int mode)
{
	if (mode == 1) return max(1.0 - d, 0.0);
	if (mode == 2) return d < 1.0 ? 1.0 : 0.0;
	if (mode == 3) { float z = (d - 1.0) * 4.0; return exp(-z * z); }
	return exp(-d * d);
}

float lum(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }
