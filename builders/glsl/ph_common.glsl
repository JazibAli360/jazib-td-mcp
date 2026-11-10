// ph_common: prefixed to every GN_physarum compute pass by builders/physarum.py (compute, T-46/T-47).
// Constants and formulas == builders/physarum_logic.py (test/test_physarum.py checks). TD adds the version line.
// Agent texel: r = x, g = y (sim texel units), b = heading rad (0..2pi), a = species (-1 = unused slot).
// Trail texel: r g b = species 0 1 2 trail. Edge e: 0 wrap, 1 bounce (clamped reads).
#define NROWS 32
#define ROW_TEXELS 2
#define NSPECIES 3
#define PI 3.14159265358979
#define TWO_PI 6.28318530717959

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

float wrapf(float x, float n) { return x - n * floor(x / n); }

ivec2 edgeT(ivec2 t, ivec2 sz, int e)
{
	if (e == 0) return ivec2(int(wrapf(float(t.x), float(sz.x))), int(wrapf(float(t.y), float(sz.y))));
	return clamp(t, ivec2(0), sz - 1);
}

float falloffW(float d, int mode)
{
	if (mode == 1) return max(1.0 - d, 0.0);
	if (mode == 2) return d < 1.0 ? 1.0 : 0.0;
	if (mode == 3) { float z = (d - 1.0) * 4.0; return exp(-z * z); }
	return exp(-d * d);
}

float lum(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }

// tone of a trail value: 0 soft (1 - exp), 1 linear Lo..Hi, 2 log  (== tone() in the logic)
float toneV(float v, int mode, float lo, float hi)
{
	if (mode == 1) return clamp((v - lo) / max(hi - lo, 1e-6), 0.0, 1.0);
	if (mode == 2) return clamp(log(1.0 + max(v - lo, 0.0)) / log(1.0 + max(hi - lo, 1e-6)), 0.0, 1.0);
	return 1.0 - exp(-max(v - lo, 0.0) / max(hi, 1e-6));
}
