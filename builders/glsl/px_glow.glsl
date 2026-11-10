// PX_pointfx glow: ONE compute pass at 1/8 resolution (input = glow_in, a mipmap-filtered 1/8 Resolution TOP of the
// render/trail image). Bright part above the threshold, 7x7 gaussian, x intensity; post adds it back (input 1,
// bilinear upscale). Replaces the stock Bloom TOP, which cost ~1.7 ms per frame at any resolution here (live 31550).
// uB: x threshold, y intensity, z tap spacing in low-res texels.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uB;

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	ivec2 res = ivec2(uTDOutputInfo.res.zw);
	if (g.x >= res.x || g.y >= res.y) return;
	ivec2 isz = textureSize(sTD2DInputs[0], 0);
	vec2 uv = (vec2(g) + 0.5) / vec2(res);
	vec2 stp = max(uB.z, 0.0) / vec2(isz);
	vec3 s = vec3(0.0);
	float ws = 0.0;
	for (int j = -3; j <= 3; j++) {
		for (int i = -3; i <= 3; i++) {
			float w = exp(-float(i * i + j * j) / 4.5);
			vec3 c = texture(sTD2DInputs[0], uv + vec2(float(i), float(j)) * stp).rgb;
			s += max(c - vec3(uB.x), vec3(0.0)) * w;
			ws += w;
		}
	}
	vec3 o = s / max(ws, 1e-6) * uB.y;
	TDImageStoreOutput(0, ivec3(g, 0), vec4(o, 0.0));
}
