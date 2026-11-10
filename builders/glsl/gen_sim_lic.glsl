// gen_sim_lic: GEN_sim 'lic' line integral convolution at the slot input's size (one compute pass).
// For each pixel: integrate the field both ways (RK2 midpoint, Step px, Taps per side), average a white noise of
// Grain px along the streamline with a Hann window x (1 + Flow cos(2 pi (s Ripples - phase))) (Cabral / Leedom;
// the moving phase makes the ink flow). v = (avg - 0.5) Contrast + 0.5 + Bright. in0 = slot input, in1 = field
// (inputextenduv hold, linear), in2 = clock. == gen_sim_logic.lic
// uL = taps step grain seed; uL2 = contrast flow ripples colourmode; uL3 = flowspeed bright 0 0.
// Colourmode: 0 value (palette(v), opaque), 1 angle (palette by field direction x v), 2 speed, 3 input (x v).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uL;
uniform vec4 uL2;
uniform vec4 uL3;

vec2 dirAt(vec2 x, vec2 osz) { return texture(sTD2DInputs[1], x / osz).xy; }

float noiseAt(vec2 x)
{
	float g = max(uL.z, 1.0);
	return gs_hash3(int(floor(x.x / g)), int(floor(x.y / g)), int(uL.w));
}

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 isz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= isz.x || p.y >= isz.y) return;
	vec2 osz = vec2(isz);
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	float ph = texelFetch(sTD2DInputs[2], ivec2(0), 0).x * uL3.x;
	int T = clamp(int(uL.x + 0.5), 1, 64);
	float h = uL.y;
	float fl = uL2.y, rp = uL2.z;
	vec2 x0 = vec2(p) + 0.5;
	float w0 = max(1.0 + fl * cos(-2.0 * GS_PI * ph), 0.0);
	float acc = w0 * noiseAt(x0), ws = w0;
	for (int sgn = -1; sgn <= 1; sgn += 2) {
		vec2 y = x0;
		for (int i = 1; i <= 64; i++) {
			if (i > T) break;
			vec2 d1 = dirAt(y, osz);
			vec2 d2 = dirAt(y + 0.5 * h * float(sgn) * d1, osz);
			y += h * float(sgn) * d2;
			float s = float(i * sgn) / float(T);
			float w = (0.5 + 0.5 * cos(GS_PI * abs(s))) * max(1.0 + fl * cos(2.0 * GS_PI * (s * rp - ph)), 0.0);
			acc += w * noiseAt(y);
			ws += w;
		}
	}
	float v = clamp((acc / max(ws, 1e-6) - 0.5) * uL2.x + 0.5 + uL3.y, 0.0, 1.0);
	vec4 fd = texture(sTD2DInputs[1], x0 / osz);
	int cm = int(uL2.w + 0.5);
	vec3 col;
	if (cm == 1) col = gs_pal(fract(atan(fd.y, fd.x) / (2.0 * GS_PI) + 1.0)) * v;
	else if (cm == 2) col = gs_pal(1.0 - exp(-fd.z)) * v;
	else if (cm == 3) col = base.rgb * v * 2.0;
	else col = gs_pal(v);
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col, 1.0));
}
