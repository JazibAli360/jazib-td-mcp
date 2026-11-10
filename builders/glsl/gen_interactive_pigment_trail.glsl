// gen_interactive_pigment_trail: pigment persistence (compute, trail res, rgba16float). in0 = splat (this cook's
// dots), in1 = last trail (Feedback TOP `trail_fb`), in2 = state (meta texel 1 .x = dts, the sim step of this cook).
// decay = exp(-|dts| / Trail) (Trail 0 = no persistence; Speed 0 = dts 0 = the picture holds exactly).
// Trailmode: 0 max(last x decay, dot), 1 add (last x decay + dot), 2 paint (a dot replaces, else last x decay).
// == builders/gen_interactive_pigment_logic.py trail_step.  uT = Trail, Trailmode, Side, 0.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uT;

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= sz.x || p.y >= sz.y) return;
	vec4 s = texelFetch(sTD2DInputs[0], p, 0);
	ivec2 fsz = textureSize(sTD2DInputs[1], 0);
	vec4 f = fsz == sz ? texelFetch(sTD2DInputs[1], p, 0) : vec4(0.0);
	int S = int(uT.z + 0.5);
	float dts = abs(texelFetch(sTD2DInputs[2], ivec2(1, S), 0).x);
	float decay = uT.x > 0.0 ? exp(-dts / uT.x) : 0.0;
	int mode = int(uT.y + 0.5);
	vec4 o;
	if (mode == 1) o = f * decay + s;
	else if (mode == 2) o = s.a > 0.0 ? s : f * decay;
	else o = max(f * decay, s);
	TDImageStoreOutput(0, ivec3(p, 0), o);
}
