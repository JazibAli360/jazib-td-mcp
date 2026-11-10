// gen_sim_lic_field: GEN_sim 'lic' vector field at Fieldres x the slot input's size (compute, rgba16float).
// Texel: xy = unit direction (output px space), z = raw magnitude, w = 1. Positions are output px.
// Source: 0 curl noise (fbm stream function, finite differences), 1 input edges (luma gradient rotated 90 deg:
// streaks follow the picture's edges), 2 input gradient (across edges), 3 vortex (around the centre, Spiral bends
// it inward), 4 Field TOP (rg = velocity, e.g. BN_fluid2d), 5 circuit (curl angle snapped to Snap directions).
// Then rotated by Rotate. in0 = slot input, in1 = clock, in2 = Field TOP (or the slot input when none).
// uLf = source scale octaves seed; uLf2 = rotate(rad) blur(px) snap spiral(rad); uLf3 = outW outH FW FH;
// uLf4 = drift 0 0 0. == gen_sim_logic.lic_field
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uLf;
uniform vec4 uLf2;
uniform vec4 uLf3;
uniform vec4 uLf4;

float fbm(vec2 x, float t, int sd)
{
	float a = 0.0, w = 1.0, s = 0.0;
	int oc = clamp(int(uLf.z + 0.5), 1, 6);
	for (int o = 0; o < 6; o++) {
		if (o >= oc) break;
		a += w * gs_vnoise(x * exp2(float(o)) + vec2(t * (0.37 + 0.11 * float(o)), t * 0.23), sd + o);
		s += w;
		w *= 0.5;
	}
	return a / s;
}

float lumaAt(vec2 x)
{
	return gs_luma(texture(sTD2DInputs[0], x / uLf3.xy).rgb);
}

void main()
{
	ivec2 f = ivec2(gl_GlobalInvocationID.xy);
	ivec2 fsz = ivec2(uLf3.zw);
	if (f.x >= fsz.x || f.y >= fsz.y) return;
	vec2 x = (vec2(f) + 0.5) * uLf3.xy / uLf3.zw;
	float t = texelFetch(sTD2DInputs[1], ivec2(0), 0).x * uLf4.x;
	int src = int(uLf.x + 0.5);
	int sd = int(uLf.w);
	vec2 v;
	if (src == 0 || src == 5) {
		float sc = max(uLf.y, 1.0);
		vec2 q = x / sc;
		float h = 0.25;
		float dx = fbm(q + vec2(h, 0.0), t, sd) - fbm(q - vec2(h, 0.0), t, sd);
		float dy = fbm(q + vec2(0.0, h), t, sd) - fbm(q - vec2(0.0, h), t, sd);
		v = vec2(dy, -dx) / (2.0 * h);
		if (src == 5) {
			float n = max(floor(uLf2.z + 0.5), 1.0);
			float an = floor(atan(v.y, v.x) / (2.0 * GS_PI) * n + 0.5) * (2.0 * GS_PI) / n;
			v = length(v) * vec2(cos(an), sin(an));
		}
	} else if (src == 1 || src == 2) {
		float b = max(uLf2.y, 1.0);
		vec2 gr = vec2(lumaAt(x + vec2(b, 0.0)) - lumaAt(x - vec2(b, 0.0)), lumaAt(x + vec2(0.0, b)) - lumaAt(x - vec2(0.0, b)));
		v = src == 1 ? vec2(-gr.y, gr.x) : gr;
		v *= 4.0;
	} else if (src == 3) {
		vec2 d = x - 0.5 * uLf3.xy;
		float an = atan(d.y, d.x) + 0.5 * GS_PI + uLf2.w;
		v = vec2(cos(an), sin(an));
	} else {
		v = texture(sTD2DInputs[2], (vec2(f) + 0.5) / vec2(fsz)).rg;
	}
	float cr = cos(uLf2.x), sr = sin(uLf2.x);
	v = vec2(cr * v.x - sr * v.y, sr * v.x + cr * v.y);
	float m = length(v);
	TDImageStoreOutput(0, ivec3(f, 0), vec4(m > 1e-9 ? v / m : vec2(0.0), m, 1.0));
}
