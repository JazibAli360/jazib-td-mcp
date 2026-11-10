// gen_sim_lavalamp look (compute, output = slot input size). in0 = slot input, in1 = state (sim res, linear).
// Density -> wax: e = smoothstep(Edge - Soft, Edge + Soft, density) (crisp blobs) -> palette (k = e, + Glow x the
// fluid speed as a hot rim); Look 1 glossy adds a soft highlight from the density gradient (wax lit from Lightangle).
// Look 2 bath shows the raw density (smoke). Over the slot input (Blend). == builders/gen_sim_logic.py lava_look.
// uLl = look edge soft glow; uLs = gloss lightangle(rad) 0 0.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uLl;
uniform vec4 uLs;

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= osz.x || p.y >= osz.y) return;
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	vec2 ssz = vec2(textureSize(sTD2DInputs[1], 0));
	vec2 uv = (vec2(p) + 0.5) / vec2(osz);
	vec4 s = texture(sTD2DInputs[1], uv);
	int look = int(uLl.x + 0.5);
	float e = look == 2 ? clamp(s.z, 0.0, 1.0) : smoothstep(uLl.y - uLl.z, uLl.y + uLl.z, s.z);
	float k = e + uLl.w * min(length(s.xy), 1.0);
	vec3 col = gs_pal(k);
	if (look == 1) {
		vec2 du = 1.0 / ssz;
		float gx = texture(sTD2DInputs[1], uv + vec2(du.x, 0.0)).z - texture(sTD2DInputs[1], uv - vec2(du.x, 0.0)).z;
		float gy = texture(sTD2DInputs[1], uv + vec2(0.0, du.y)).z - texture(sTD2DInputs[1], uv - vec2(0.0, du.y)).z;
		vec2 L = vec2(cos(uLs.y), sin(uLs.y));
		col += uLs.x * max(dot(normalize(vec2(gx, gy) + 1e-6), L), 0.0) * smoothstep(0.02, 0.3, length(vec2(gx, gy)));
	}
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col, 1.0));
}
