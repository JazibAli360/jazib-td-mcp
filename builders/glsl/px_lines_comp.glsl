// px_lines_comp.glsl - PX lines pass, COMPOSITE: ONE compute pass (T-46/T-47) at Resx x Resy, rgba16float. Mirrors
// px_lines_logic.ref_comp. Text = glsl_header() + px_lines_common.glsl + this. Inputs (linear filtering, any sizes):
// 0 = scene (in1), 1 = line render (or black when no source is on), 2 = edges (or black when Edges is off).
// Outmode 0 composite: scene x (1 - Bgdim) + Amount x (lines + edges), alpha = max(scene a, layer a);
// Outmode 1 lines only (for PX: add it before PX's trail / glow): Amount x (lines + edges), alpha = layer a.
layout (local_size_x = 8, local_size_y = 8) in;

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = ivec2(uTDOutputInfo.res.zw);
	if (g.x >= osz.x || g.y >= osz.y) return;
	vec2 uv = (vec2(g) + 0.5) / vec2(osz);
	vec4 sc = texture(sTD2DInputs[0], uv);
	vec4 ln = texture(sTD2DInputs[1], uv);
	vec4 ed = texture(sTD2DInputs[2], uv);
	float am = uL[R_OUT0].x;
	vec3 layer = (ln.rgb + ed.rgb) * am;
	float la = clamp(max(ln.a, ed.a) * am, 0.0, 1.0);
	vec4 o = uL[R_OUT0].y > 0.5 ? vec4(layer, la) : vec4(sc.rgb * (1.0 - uL[R_OUT0].z) + layer, max(sc.a, la));
	TDImageStoreOutput(0, ivec3(g, 0), o);
}
