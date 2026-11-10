// gen_sim_ripple_look: GEN_sim 'ripple' look (compute, output = slot input size). in0 = slot input, in1 = water state
// (sim res, sampled bilinear). Height gradient by central differences (one sim texel) -> normal (Bump) ->
// Look 0 refract: the slot input seen through the water (Refract px along the normal) + specular;
// 1 height: palette by height (0.5 + Contrast x h); 2 shaded: palette by height x diffuse + specular.
// Specular: sun at Lightangle (deg, 35 deg above the water), Shine, Spec, tinted Colour B. Over the slot input (Blend).
// == builders/gen_sim_logic.py ripple_look.
// uRl = look refract(px) bump contrast; uSp = spec shine lightangle(rad) 0.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uRl;
uniform vec4 uSp;

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= osz.x || p.y >= osz.y) return;
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	vec2 ssz = vec2(textureSize(sTD2DInputs[1], 0));
	vec2 uv = (vec2(p) + 0.5) / vec2(osz);
	vec2 du = 1.0 / ssz;
	float h = texture(sTD2DInputs[1], uv).r;
	float gx = 0.5 * (texture(sTD2DInputs[1], uv + vec2(du.x, 0.0)).r - texture(sTD2DInputs[1], uv - vec2(du.x, 0.0)).r);
	float gy = 0.5 * (texture(sTD2DInputs[1], uv + vec2(0.0, du.y)).r - texture(sTD2DInputs[1], uv - vec2(0.0, du.y)).r);
	vec3 n = normalize(vec3(-gx * uRl.z, -gy * uRl.z, 1.0));
	vec3 L = normalize(vec3(cos(uSp.z), sin(uSp.z), 0.7));
	vec3 r = vec3(2.0 * n.z * n.x, 2.0 * n.z * n.y, 2.0 * n.z * n.z - 1.0);
	float sp = uSp.x * pow(max(dot(r, L), 0.0), uSp.y);
	int look = int(uRl.x + 0.5);
	vec3 col;
	if (look == 0) {
		vec4 refr = texture(sTD2DInputs[0], uv + n.xy * uRl.y / vec2(osz));
		col = refr.rgb + sp * uCb.rgb;
	} else {
		col = gs_pal(0.5 + h * uRl.w);
		if (look == 2) col = col * (0.35 + 0.65 * max(dot(n, L), 0.0)) + sp * uCb.rgb;
	}
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col, 1.0));
}
