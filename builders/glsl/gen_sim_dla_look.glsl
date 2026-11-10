// gen_sim_dla_look: GEN_sim 'dla' picture at the slot input's size. in0 = slot input, in1 = cluster (sim size,
// inputfiltertype mipmap: textureLod gives the glow), in2 = field (phi). Mode 0 age (newest = palette 1, fading
// to 0 over Fade steps), 1 solid, 2 field (phi bands + the cluster). Glow = cluster coverage at mip level Glowlod.
// uDl = mode fade glow now (step stamp of this frame); uDl2 = W H glowlod bands.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uDl;
uniform vec4 uDl2;

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= osz.x || p.y >= osz.y) return;
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	vec2 uv = (vec2(p) + 0.5) / vec2(osz);
	ivec2 sz = ivec2(uDl2.xy);
	ivec2 ci = clamp(ivec2(floor(uv * uDl2.xy)), ivec2(0), sz - 1);
	vec4 s = texelFetch(sTD2DInputs[1], ci, 0);
	int mode = int(uDl.x + 0.5);
	float t, v;
	if (mode == 2) {
		float phi = clamp(textureLod(sTD2DInputs[2], uv, 0.0).r, 0.0, 1.0);
		float bands = max(uDl2.w, 1.0);
		float ln = 1.0 - smoothstep(0.0, 0.08, abs(fract(phi * bands + 0.5) - 0.5));
		t = phi;
		v = max(s.r, 0.15 + 0.35 * phi + 0.5 * ln);
		if (s.r > 0.5) t = 1.0;
	} else if (mode == 1) {
		t = 1.0;
		v = s.r;
	} else {
		t = s.r > 0.5 ? exp(-max(uDl.w - s.g, 0.0) / max(uDl.y, 1e-3)) : 0.0;
		v = s.r;
	}
	float g = uDl.z > 0.0 ? textureLod(sTD2DInputs[1], uv, uDl2.z).r * uDl.z : 0.0;
	vec3 col = gs_pal(t) * v + gs_pal(1.0) * g;
	float a = clamp(max(v, g), 0.0, 1.0);
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col, a));
}
