// PX bloom v2 (W1-D; doc docs/builds/px_haze.md "Bloom"): drop-in for px_glow.glsl (ONE compute pass). Two scales:
// wide = 7x7 gaussian of the excess on input 0 (the 1/8 mipmap glow_in, as px_glow), tight = the same on input 1 (a
// 1/4 mipmap Resolution TOP); optional ring halo (a ring of radius Ringradius around every bright spot, r/g/b at
// slightly different radii = rainbow ring); tint = pxColSrc(uGlowCs, Bloomtint, white, 0) (W1-B shared palette:
// px_haze_logic.shader_text() prepends px_palette.glsl; cs mode solid + white = today's glow) + saturation.
// Splat-aware: thresholds premultiplied rgb (what the splat render writes), optional soft knee and a firefly clamp
// (excess luma cap) so lone hot splats do not flicker the glow. Output alpha 0 (px_post raises alpha from the glow).
// Legacy: uB.w = 0, uB2 = (1, 0, -, 0), uBt = (1, 1, 1, 1), uBr.x = 0 and output res = input 0 res run the px_glow
// maths unchanged (input 1 never sampled). Inputs wired: 0 and 1 (input 1 may be the same TOP as 0 in legacy).
// Mirrors px_haze_logic.ref_bloom. ASCII only.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uB;      // x threshold, y intensity, z wide tap spacing (input 0 texels), w soft knee (0 = hard, legacy)
uniform vec4 uB2;     // x wide weight (1 legacy), y tight weight (0 = one scale), z tight tap spacing, w firefly clamp
uniform vec4 uBt;     // Bloomtint rgb (solid colour of the cs; white = legacy), w saturation (1 = legacy)
uniform vec4 uGlowCs; // W1-B colour source (mode, pos, spread, keep); mode 0 solid = uBt.rgb
uniform vec4 uBr;     // ring: x amount (0 = off), y radius (fraction of screen height), z width (0 tight..1 wide), w chroma

float pbLuma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

vec3 pbExcess(vec3 c)
{
	vec3 e;
	if (uB.w > 0.0) {                                      // soft knee (fx_film kneex, by brightest channel)
		float br = max(c.r, max(c.g, c.b));
		float rq = clamp(br - uB.x + uB.w, 0.0, 2.0 * uB.w);
		rq = rq * rq / (4.0 * uB.w + 1e-5);
		e = c * (max(rq, br - uB.x) / max(br, 1e-5));
	} else {
		e = max(c - vec3(uB.x), vec3(0.0));
	}
	if (uB2.w > 0.0) {
		float l = pbLuma(e);
		e *= min(l, uB2.w) / max(l, 1e-6);
	}
	return e;
}

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	ivec2 res = ivec2(uTDOutputInfo.res.zw);
	if (g.x >= res.x || g.y >= res.y) return;
	vec2 uv = (vec2(g) + 0.5) / vec2(res);
	vec3 o = vec3(0.0);
	if (uB2.x > 0.0) {                                     // wide: px_glow's loop, same order
		ivec2 isz = textureSize(sTD2DInputs[0], 0);
		vec2 stp = max(uB.z, 0.0) / vec2(isz);
		vec3 s = vec3(0.0);
		float ws = 0.0;
		bool legacy = uB.w <= 0.0 && uB2.w <= 0.0;
		if (legacy) {                                    // px_glow's loop, as a separate loop (a select inside it
			for (int j = -3; j <= 3; j++) {              // changed the driver's codegen: 1 ulp, PX wave 2 W2-4)
				for (int i = -3; i <= 3; i++) {
					float w = exp(-float(i * i + j * j) / 4.5);
					vec3 c = texture(sTD2DInputs[0], uv + vec2(float(i), float(j)) * stp).rgb;
					s += max(c - vec3(uB.x), vec3(0.0)) * w;
					ws += w;
				}
			}
		} else {
			for (int j = -3; j <= 3; j++) {
				for (int i = -3; i <= 3; i++) {
					float w = exp(-float(i * i + j * j) / 4.5);
					vec3 c = texture(sTD2DInputs[0], uv + vec2(float(i), float(j)) * stp).rgb;
					s += pbExcess(c) * w;
					ws += w;
				}
			}
		}
		o = s / max(ws, 1e-6) * uB.y;
		if (uB2.x != 1.0) o *= uB2.x;
	}
	if (uB2.y > 0.0) {                                     // tight
		ivec2 isz = textureSize(sTD2DInputs[1], 0);
		vec2 stp = max(uB2.z, 0.0) / vec2(isz);
		vec3 s = vec3(0.0);
		float ws = 0.0;
		for (int j = -3; j <= 3; j++) {
			for (int i = -3; i <= 3; i++) {
				float w = exp(-float(i * i + j * j) / 4.5);
				s += pbExcess(texture(sTD2DInputs[1], uv + vec2(float(i), float(j)) * stp).rgb) * w;
				ws += w;
			}
		}
		o += s / max(ws, 1e-6) * (uB2.y * uB.y);
	}
	if (uBr.x > 0.0) {                                     // ring halo: 16 directions x 3 radii (r, g, b)
		float asp = float(res.x) / float(max(res.y, 1));
		vec3 r = vec3(0.0);
		// per-pixel start angle (interleaved gradient noise): fixed taps drew the ring as 12 beads (live b5)
		float jr = fract(52.9829189 * fract(dot(vec2(g), vec2(0.06711056, 0.00583715))));
		for (int k = 0; k < 16; k++) {
			float a = 6.283185307179586 * (float(k) + jr) / 16.0;
			vec2 dv = vec2(cos(a) / asp, sin(a));
			vec2 c0 = uv + dv * (uBr.y * (1.0 - uBr.w));
			vec2 c1 = uv + dv * uBr.y;
			vec2 c2 = uv + dv * (uBr.y * (1.0 + uBr.w));
			r.r += pbExcess(mix(texture(sTD2DInputs[1], c0), texture(sTD2DInputs[0], c0), uBr.z).rgb).r;
			r.g += pbExcess(mix(texture(sTD2DInputs[1], c1), texture(sTD2DInputs[0], c1), uBr.z).rgb).g;
			r.b += pbExcess(mix(texture(sTD2DInputs[1], c2), texture(sTD2DInputs[0], c2), uBr.z).rgb).b;
		}
		o += r * (uBr.x / 16.0);
	}
	vec3 tint = pxColSrc(uGlowCs, uBt.rgb, vec3(1.0), 0.0);
	if (tint.r != 1.0 || tint.g != 1.0 || tint.b != 1.0) o *= tint;
	if (uBt.w != 1.0) { float l = pbLuma(o); o = max(mix(vec3(l), o, uBt.w), vec3(0.0)); }
	TDImageStoreOutput(0, ivec3(g, 0), vec4(o, 0.0));
}
