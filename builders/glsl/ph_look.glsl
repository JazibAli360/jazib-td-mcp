// ph pass fx_look (Resw x Resh): trail sampled bilinear -> per species tone (soft / linear / log) -> species colours
// (or palette / ramp / gray of the total), halo glow, agents view (deposit counts), exposure, gamma, background,
// alpha (opaque or value), premultiplied option.
// in0 = fx_trail (sim res), in1 = ramp_in (ramp TOP along x), in2 = deposit (agent counts in a)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;    // simw, simh, aspect, edge
uniform vec4 uLook;   // valuemode, lo, hi, colormode
uniform vec4 uLook2;  // exposure, gamma, alphamode, premult
uniform vec4 uLook3;  // glow, agents view, nspecies, 0
uniform vec4 uCol1;
uniform vec4 uCol2;
uniform vec4 uCol3;
uniform vec4 uBg;
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
	vec2 uv = (vec2(T) + 0.5) / vec2(sz);
	vec3 tr = texture(sTD2DInputs[0], uv).rgb;
	if (uLook3.x > 0.0) {
		vec2 px = 4.0 / uSim.xy;
		vec3 h = texture(sTD2DInputs[0], uv + vec2(px.x, 0.0)).rgb + texture(sTD2DInputs[0], uv - vec2(px.x, 0.0)).rgb
		       + texture(sTD2DInputs[0], uv + vec2(0.0, px.y)).rgb + texture(sTD2DInputs[0], uv - vec2(0.0, px.y)).rgb;
		tr += uLook3.x * 0.25 * h;
	}
	int ns = int(uLook3.z + 0.5);
	if (ns < 2) tr.g = 0.0;
	if (ns < 3) tr.b = 0.0;
	int vm = int(uLook.x + 0.5);
	float tot = toneV(tr.r + tr.g + tr.b, vm, uLook.y, uLook.z);
	int cm = int(uLook.w + 0.5);
	vec3 col;
	if (cm == 1) col = palette(tot);
	else if (cm == 2) col = texture(sTD2DInputs[1], vec2(tot, 0.5)).rgb;
	else if (cm == 3) col = vec3(tot);
	else col = uCol1.rgb * toneV(tr.r, vm, uLook.y, uLook.z) + uCol2.rgb * toneV(tr.g, vm, uLook.y, uLook.z)
	         + uCol3.rgb * toneV(tr.b, vm, uLook.y, uLook.z);
	if (uLook3.y > 0.0) col += vec3(uLook3.y * clamp(texture(sTD2DInputs[2], uv).a * 0.5, 0.0, 1.0));
	col *= exp2(uLook2.x);
	col = pow(max(col, vec3(0.0)), vec3(1.0 / max(uLook2.y, 1e-3)));
	float a = 1.0;
	if (int(uLook2.z + 0.5) == 1) {
		a = clamp(tot, 0.0, 1.0);
		if (uLook2.w > 0.5) col *= a;
	} else {
		col += uBg.rgb * (1.0 - clamp(tot, 0.0, 1.0));
	}
	TDImageStoreOutput(0, ivec3(T, 0), vec4(col, a));
}
