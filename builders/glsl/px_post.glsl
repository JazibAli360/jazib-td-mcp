// PX_pointfx post: ONE compute pass (T-47) after trail + bloom: exposure, hue, saturation, contrast, split tone
// (teal/orange macro), tone map (none / ACES fit / Reinhard / filmic), lift-gamma-gain, haze, chromatic shift,
// vignette, grain, lens flare (ghosts + streak). Input 0 = premultiplied RGBA 16F, input 1 = 1/8-res bloom glow
// (added first; 0 when Bloom = 0), input 2 = volumetric haze (wave 2, px_haze.glsl; applied first while uQh.x > 0). Mirrors px_logic.ref_grade. Alpha passes through (haze, glow and flare raise it).
// Output = Resx x Resy always; an input of another size (auto quality resolution step) is sampled by uv.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uQ[10];     // rows: px_logic.post_rows()
uniform vec4 uQf;        // x = frame for the grain hash (TOP expression: uQ stays static, T-143)
uniform vec4 uQh;        // wave 2 haze: x = amount (0 = off: input 2 never sampled), y = alpha mode (1 = haze raises it)

uint pqHash(uint x)
{
	x ^= x >> 16u;
	x *= 0x7feb352du;
	x ^= x >> 15u;
	x *= 0x846ca68bu;
	x ^= x >> 16u;
	return x;
}

float pqLum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

vec3 pqAces(vec3 x) { return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }

vec3 pqHue(vec3 c, float turns)
{
	float a = turns * 6.283185307179586;
	float y = dot(c, vec3(0.299, 0.587, 0.114));
	float i = dot(c, vec3(0.596, -0.274, -0.322));
	float q = dot(c, vec3(0.211, -0.523, 0.312));
	float ca = cos(a), sa = sin(a);
	float i2 = i * ca - q * sa, q2 = i * sa + q * ca;
	return vec3(y + 0.956 * i2 + 0.621 * q2, y - 0.272 * i2 - 0.647 * q2, y - 1.106 * i2 + 1.703 * q2);
}

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	ivec2 os = ivec2(uTDOutputInfo.res.zw);
	bool same = sz == os;                          // phase C auto quality: the chain may run smaller, out1 does not
	if (same && (g.x >= sz.x || g.y >= sz.y)) return;
	if (g.x >= os.x || g.y >= os.y) return;
	vec2 uv = (vec2(g) + 0.5) / vec2(same ? sz : os);
	vec4 src = same ? texelFetch(sTD2DInputs[0], g, 0) : texture(sTD2DInputs[0], uv);
	vec3 c = src.rgb;
	float ch = uQ[6].x;
	if (ch != 0.0) {
		vec2 dv = (uv - 0.5) * ch;
		c.r = texture(sTD2DInputs[0], uv + dv).r;
		c.b = texture(sTD2DInputs[0], uv - dv).b;
	}
	if (uQh.x > 0.0) {                                             // volumetric haze (W1-D pxhApply, input 2, 1/4 res)
		vec4 hz = textureLod(sTD2DInputs[2], uv, 0.0) * uQh.x;
		c = c * (1.0 - hz.a) + hz.rgb;
		if (uQh.y > 0.5) src.a = src.a * (1.0 - hz.a) + hz.a;
	}
	vec4 bl = texture(sTD2DInputs[1], uv);                         // half-res glow (bloom only), 0 when Bloom = 0
	c += bl.rgb;
	src.a = max(src.a, clamp(pqLum(bl.rgb), 0.0, 1.0));
	// lens flare (Grade Flare): horizontal streak (16 taps each side over Flarestreak px) + up to 6 ghosts mirrored
	// through the centre (spacing Flaredisp), both from what exceeds Flarethr; tinted by Flaretint. Off = no taps.
	float fa = 0.0;
	if (uQ[6].y > 0.0) {
		vec3 fc = vec3(0.0);
		float thr = uQ[6].z;
		float sl = uQ[6].w / float(max(os.x, 1));      // Flarestreak px of the output (= sz.x at full quality)
		for (int k = 1; k <= 16; k++) {
			float o = sl * float(k) / 16.0;
			float wk = exp(-3.0 * float(k) / 16.0);
			fc += (max(texture(sTD2DInputs[0], uv + vec2(o, 0.0)).rgb - thr, vec3(0.0))
			     + max(texture(sTD2DInputs[0], uv - vec2(o, 0.0)).rgb - thr, vec3(0.0))) * wk;
		}
		fc *= 1.0 / 16.0;
		int ng = clamp(int(uQ[7].x + 0.5), 0, 6);
		vec2 gv = (vec2(0.5) - uv) * uQ[7].y;
		for (int k = 1; k <= 6; k++) {
			if (k > ng) break;
			vec2 gu = uv + gv * float(k);
			if (any(lessThan(gu, vec2(0.0))) || any(greaterThan(gu, vec2(1.0)))) continue;
			float wg = 1.0 - smoothstep(0.0, 0.7, length(gu - 0.5));
			fc += max(texture(sTD2DInputs[0], gu).rgb - thr, vec3(0.0)) * (wg * 0.5);
		}
		fc *= uQ[8].rgb * uQ[6].y;
		c += fc;
		fa = clamp(pqLum(fc), 0.0, 1.0);
	}
	c *= exp2(uQ[0].x);
	c = pqHue(c, uQ[4].w);
	c = mix(vec3(pqLum(c)), c, uQ[0].z);
	c = max((c - 0.18) * uQ[0].w + 0.18, vec3(0.0));
	// split tone: shadows -> uQ[1].rgb, highlights -> uQ[2].rgb, weight by luminance around Balance
	float l = pqLum(c);
	float hw = smoothstep(uQ[2].w - 0.25, uQ[2].w + 0.25, l);
	vec3 tone = mix(uQ[1].rgb, uQ[2].rgb, hw);
	float split = clamp(uQ[1].w + uQ[3].w, 0.0, 1.0);
	c = mix(c, l * tone * 2.0, split);
	int tm = int(uQ[0].y + 0.5);
	if (tm == 1) c = pqAces(c);
	else if (tm == 2) c = c / (1.0 + c);
	else if (tm == 3) { vec3 x = max(c - 0.004, vec3(0.0)); c = (x * (6.2 * x + 0.5)) / (x * (6.2 * x + 1.7) + 0.06); c = pow(c, vec3(2.2)); }
	c = uQ[3].z * (c + uQ[3].x * (1.0 - c));
	c = pow(max(c, vec3(0.0)), vec3(1.0 / max(uQ[3].y, 1e-3)));
	float a = clamp(src.a + fa * (1.0 - src.a), 0.0, 1.0);
	vec3 haze = uQ[5].rgb * uQ[5].w;
	c += haze * (1.0 - a);
	a = clamp(a + uQ[5].w * (1.0 - a), 0.0, 1.0);
	float vg = 1.0 - uQ[4].x * smoothstep(0.3, 0.9, length(uv - 0.5) * 1.41421356);
	c *= vg;
	if (uQ[4].y != 0.0) {
		uint h = pqHash(uint(g.x) * 1973u + uint(g.y) * 9277u + uint(uQ[4].z + uQf.x) * 26699u);
		c += (float(h >> 8u) * (1.0 / 16777216.0) - 0.5) * uQ[4].y;
	}
	c = max(c, vec3(0.0));
	TDImageStoreOutput(0, ivec3(g, 0), vec4(c, a));
}
