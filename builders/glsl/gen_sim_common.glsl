// gen_sim_common: prefixed to every GEN_sim compute pass by builders/gen_sim.py (compute GLSL, T-46/T-47).
// Hash / noise == builders/gen_sim_logic.py (hash3, vnoise; test/test_gen_sim.py checks). TD adds the version line.
// Look uniforms (set on the look passes only): uLook = blend palette palshift amount, uCa / uCb = Colour A / B rgb.
#define GS_PI 3.14159265358979
uniform vec4 uLook;
uniform vec4 uCa;
uniform vec4 uCb;

uint gs_hashu(uint x)
{
	x ^= x >> 16u; x *= 0x7feb352du; x ^= x >> 15u; x *= 0x846ca68bu; x ^= x >> 16u;
	return x;
}

// float in [0, 1) from three ints; exact in float32 (24 bits) == gen_sim_logic.hash3
float gs_hash3(int i, int j, int s)
{
	uint h = gs_hashu(uint(i) + gs_hashu(uint(j) + gs_hashu(uint(s))));
	return float(h >> 8u) * (1.0 / 16777216.0);
}

// value noise in [0, 1), smoothstep blend == gen_sim_logic.vnoise
float gs_vnoise(vec2 p, int s)
{
	vec2 i = floor(p);
	vec2 f = p - i;
	ivec2 q = ivec2(i);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = gs_hash3(q.x, q.y, s), b = gs_hash3(q.x + 1, q.y, s);
	float c = gs_hash3(q.x, q.y + 1, s), d = gs_hash3(q.x + 1, q.y + 1, s);
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float gs_luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

// Palette (Colour page): 0 Colour A -> B, 1 fire, 2 ice, 3 neon, 4 rainbow, 5 mono white, 6 input (module decides;
// falls back to A -> B). t in 0..1 (+ Palette shift). == gen_sim_logic.palette
vec3 gs_pal(float t)
{
	int m = int(uLook.y + 0.5);
	float u = t + uLook.z;
	if (m == 1) { float c = clamp(u, 0.0, 1.0); return clamp(vec3(c * 3.0, c * 3.0 - 1.0, c * 3.0 - 2.0), 0.0, 1.0); }
	if (m == 2) { float c = clamp(u, 0.0, 1.0); return mix(vec3(0.0, 0.05, 0.2), vec3(0.55, 0.9, 1.0), c) + vec3(c * c * c * 0.45); }
	if (m == 3) return 0.5 + 0.5 * cos(2.0 * GS_PI * (u + vec3(0.3, 0.2, 0.2)));
	if (m == 4) return 0.5 + 0.5 * cos(2.0 * GS_PI * (u + vec3(0.0, 0.33, 0.67)));
	if (m == 5) return vec3(1.0);
	return mix(uCa.rgb, uCb.rgb, clamp(u, 0.0, 1.0));
}

// The generator's picture over the slot input. col = premultiplied colour, a = coverage. Blend (Colour page):
// 0 replace, 1 over, 2 add, 3 screen, 4 multiply, 5 lighten, 6 difference, 7 alpha out (premultiplied).
// Amount mixes from the input (Amount 0 never gets here: out_sel passes in1 through untouched).
vec4 gs_blend(vec4 base, vec3 col, float a)
{
	int m = int(uLook.x + 0.5);
	vec4 o;
	if (m == 0) o = vec4(col, 1.0);
	else if (m == 1) o = vec4(col + base.rgb * (1.0 - a), a + base.a * (1.0 - a));
	else if (m == 2) o = vec4(base.rgb + col, base.a);
	else if (m == 3) o = vec4(1.0 - (1.0 - base.rgb) * (1.0 - col), base.a);
	else if (m == 4) o = vec4(base.rgb * col, base.a);
	else if (m == 5) o = vec4(max(base.rgb, col), base.a);
	else if (m == 6) o = vec4(abs(base.rgb - col), base.a);
	else o = vec4(col, a);
	return mix(base, o, uLook.w);
}
