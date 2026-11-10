// rd pass fx_look (Resw x Resh): state sampled bilinear -> value (B, A-B, 1-A, edges) -> Lo..Hi -> palette / ramp /
// raw / gray, emboss shade, edge glow, exposure, gamma, alpha (opaque or value), premultiplied option.
// in0 = fx_rd (state, sim res), in1 = ramp_in (ramp TOP, sampled along x)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;    // simw, simh, aspect, edge
uniform vec4 uLook;   // valuemode, lo, hi, colormode
uniform vec4 uLook2;  // invert, shade, shade height, light angle (rad)
uniform vec4 uLook3;  // exposure, gamma, alphamode, premult
uniform vec4 uEdge;   // edge colour rgb, edge glow
uniform vec4 uPal0;
uniform vec4 uPal1;
uniform vec4 uPal2;
uniform vec4 uPal3;
uniform vec4 uPal4;

vec3 palette(float t)
{
	t = clamp(t, 0.0, 1.0) * 4.0;
	if (t < 1.0) return mix(uPal0.rgb, uPal1.rgb, t);
	if (t < 2.0) return mix(uPal1.rgb, uPal2.rgb, t - 1.0);
	if (t < 3.0) return mix(uPal2.rgb, uPal3.rgb, t - 2.0);
	return mix(uPal3.rgb, uPal4.rgb, t - 3.0);
}

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	int e = int(uSim.w + 0.5);
	vec2 ssz = vec2(textureSize(sTD2DInputs[0], 0));
	vec2 uv = (vec2(T) + 0.5) / vec2(sz);
	vec2 px = 1.0 / ssz;
	// hardware bilinear (perf: 5 fetches instead of 20 manual ones; the look needs no reference parity)
	vec4 c = texture(sTD2DInputs[0], uv);
	float gx = (texture(sTD2DInputs[0], uv + vec2(px.x, 0.0)).g - texture(sTD2DInputs[0], uv - vec2(px.x, 0.0)).g) * 0.5;
	float gy = (texture(sTD2DInputs[0], uv + vec2(0.0, px.y)).g - texture(sTD2DInputs[0], uv - vec2(0.0, px.y)).g) * 0.5;
	float gl = length(vec2(gx, gy));
	int vm = int(uLook.x + 0.5);
	float val = vm == 1 ? c.r - c.g : (vm == 2 ? 1.0 - c.r : (vm == 3 ? gl * 8.0 : c.g));
	float t = (val - uLook.y) / max(uLook.z - uLook.y, 1e-6);
	if (uLook2.x > 0.5) t = 1.0 - t;
	int cm = int(uLook.w + 0.5);
	vec3 col;
	if (cm == 1) col = texture(sTD2DInputs[1], vec2(clamp(t, 0.0, 1.0), 0.5)).rgb;
	else if (cm == 2) col = vec3(c.r, c.g, 0.0);
	else if (cm == 3) col = vec3(t);
	else col = palette(t);
	if (uLook2.y > 0.0) {
		float hs = uLook2.z * 20.0 / max(uLook.z - uLook.y, 1e-6);
		vec3 n = normalize(vec3(-gx * hs, -gy * hs, 1.0));
		vec3 L = normalize(vec3(cos(uLook2.w), sin(uLook2.w), 1.0));
		float diff = max(dot(n, L), 0.0) / L.z;
		float spec = pow(max(dot(reflect(-L, n), vec3(0.0, 0.0, 1.0)), 0.0), 24.0);
		col = col * mix(1.0, diff, uLook2.y) + uLook2.y * spec * 0.4;
	}
	col += uEdge.rgb * uEdge.w * gl * 8.0;
	col *= exp2(uLook3.x);
	col = pow(max(col, vec3(0.0)), vec3(1.0 / max(uLook3.y, 1e-3)));
	float a = 1.0;
	if (int(uLook3.z + 0.5) == 1) {
		a = clamp(t, 0.0, 1.0);
		if (uLook3.w > 0.5) col *= a;
	}
	TDImageStoreOutput(0, ivec3(T, 0), vec4(col, a));
}
