// fluid2d_common: prefixed to every fluid2d pass by builders/fluid2d.py (compute mode, T-46/T-47).
// Constants must equal builders/fluid2d_logic.py (test/test_fluid2d.py checks). No #version (TD adds it).
// Grid: texel (i,j) = cell; .x = x-face velocity at (i+1, j+0.5), .y = y-face velocity at (i+0.5, j+1), cells/s.
// Edge e: 0 wall (outside solid, velocity 0), 1 wrap, 2 open (outside fluid, p = 0).
#define NEMIT 8
#define EMIT_TEXELS 3
#define INV_BETA 0.25
#define VORT_EPS 1e-5
#define M_CLAMP 0
#define M_WRAP 1
#define M_CONST 2

int wrapi(int x, int n) { return x - n * int(floor(float(x) / float(n))); }

// true = fetch texel t (resolved in place); false = outside in M_CONST mode (caller uses its constant)
bool resolveT(inout ivec2 t, ivec2 sz, int mode)
{
	if (t.x >= 0 && t.y >= 0 && t.x < sz.x && t.y < sz.y) return true;
	if (mode == M_WRAP) { t = ivec2(wrapi(t.x, sz.x), wrapi(t.y, sz.y)); return true; }
	if (mode == M_CLAMP) { t = clamp(t, ivec2(0), sz - 1); return true; }
	return false;
}

int velMode(int e) { return e == 1 ? M_WRAP : (e == 2 ? M_CLAMP : M_CONST); }
int solidMode(int e) { return e == 1 ? M_WRAP : M_CONST; }
float solidConst(int e) { return e == 0 ? 1.0 : 0.0; }
int presMode(int e) { return e == 1 ? M_WRAP : (e == 2 ? M_CONST : M_CLAMP); }
int dyeMode(int e) { return presMode(e); }

// Gaussian splat, dp aspect-corrected (screen heights): integral = pi r^2
float splat(vec2 uv, vec2 c, float r, float aspect)
{
	vec2 dp = (uv - c) * vec2(aspect, 1.0);
	return exp(-dot(dp, dp) / (r * r));
}

float mix4(float a00, float a10, float a01, float a11, vec2 f)
{
	return mix(mix(a00, a10, f.x), mix(a01, a11, f.x), f.y);
}
