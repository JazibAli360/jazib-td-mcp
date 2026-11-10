// fluid2d pass fx_look (output res Resw x Resh, single pass; the dye may be smaller (Quality): bilinear): colour (dye rgb / palette by density / palette by speed), exposure,
// gamma, alpha (opaque over Bg / density alpha, premultiplied or straight). -> out1.
// in0 = fx_advdye (dye), in1 = fx_grad (sim res velocity, for speed colour)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uLook;   // colour mode (0 rgb, 1 density, 2 speed), exposure stops, gamma, speed ref (cells/s)
uniform vec4 uLook2;  // alpha mode (0 opaque, 1 density), premult (0/1), 0, 0
uniform vec4 uBg;     // background rgb
uniform vec4 uPal0;
uniform vec4 uPal1;
uniform vec4 uPal2;
uniform vec4 uPal3;
uniform vec4 uPal4;

vec3 pal(float t)
{
	t = clamp(t, 0.0, 1.0) * 4.0;
	int k = min(int(floor(t)), 3);
	float f = t - float(k);
	if (k == 0) return mix(uPal0.rgb, uPal1.rgb, f);
	if (k == 1) return mix(uPal1.rgb, uPal2.rgb, f);
	if (k == 2) return mix(uPal2.rgb, uPal3.rgb, f);
	return mix(uPal3.rgb, uPal4.rgb, f);
}

float VX(ivec2 t, ivec2 s)
{
	if (t.x < 0) return 0.0;
	return texelFetch(sTD2DInputs[1], clamp(t, ivec2(0), s - 1), 0).x;
}

float VY(ivec2 t, ivec2 s)
{
	if (t.y < 0) return 0.0;
	return texelFetch(sTD2DInputs[1], clamp(t, ivec2(0), s - 1), 0).y;
}

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec4 d = textureLod(sTD2DInputs[0], (vec2(T) + 0.5) / vec2(sz), 0.0);
	float dens = max(d.r, max(d.g, d.b));
	float a = clamp(dens, 0.0, 1.0);
	int mode = int(uLook.x + 0.5);
	vec3 col;
	if (mode == 0) col = d.rgb;
	else if (mode == 1) col = pal(a) * a;
	else {
		ivec2 s = textureSize(sTD2DInputs[1], 0);
		ivec2 cs = clamp(ivec2(floor((vec2(T) + 0.5) / vec2(sz) * vec2(s))), ivec2(0), s - 1);
		vec2 uc = 0.5 * vec2(VX(cs - ivec2(1, 0), s) + VX(cs, s), VY(cs - ivec2(0, 1), s) + VY(cs, s));
		col = pal(length(uc) / max(uLook.w, 1e-6)) * a;
	}
	col *= exp2(uLook.y);
	col = pow(max(col, vec3(0.0)), vec3(1.0 / max(uLook.z, 1e-4)));
	vec4 o;
	if (uLook2.x < 0.5) o = vec4(col + uBg.rgb * (1.0 - a), 1.0);
	else if (uLook2.y > 0.5) o = vec4(col, a);
	else o = vec4(a > 0.0 ? col / a : vec3(0.0), a);
	TDImageStoreOutput(0, ivec3(T, 0), TDOutputSwizzle(o));
}
