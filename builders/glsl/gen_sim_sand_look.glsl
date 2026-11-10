// gen_sim_sand look (compute, output = slot input size). in0 = slot input, in1 = sand state (sim res, nearest).
// Cell under the pixel: empty = the slot input shows (coverage 0), sand = palette at the grain shade (Spread, +
// Palshift), water = Colour B x (0.6 + 0.4 shade) at Wateralpha, wall = grey; Gap darkens the cell border (pixel
// grains). Over the slot input (Blend). == builders/gen_sim_logic.py sand_look.
// uSl = cellpx gap spread wateralpha.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSl;

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= osz.x || p.y >= osz.y) return;
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	ivec2 ssz = textureSize(sTD2DInputs[1], 0);
	vec2 q = (vec2(p) + 0.5) * vec2(ssz) / vec2(osz);
	ivec2 c = clamp(ivec2(q), ivec2(0), ssz - 1);
	vec4 s = texelFetch(sTD2DInputs[1], c, 0);
	int m = int(floor(s.r * 3.0 + 0.5));
	vec2 f = q - vec2(c);
	float edge = min(min(f.x, 1.0 - f.x), min(f.y, 1.0 - f.y));
	float gap = edge < 0.5 * uSl.y ? 0.55 : 1.0;
	vec3 col = vec3(0.0); float a = 0.0;
	if (m == 1) { col = gs_pal(s.g * uSl.z) * gap; a = 1.0; }
	else if (m == 2) { a = uSl.w; col = uCb.rgb * (0.6 + 0.4 * s.g) * a; }
	else if (m == 3) { col = vec3(0.22 + 0.1 * s.g); a = 1.0; }
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col, a));
}
