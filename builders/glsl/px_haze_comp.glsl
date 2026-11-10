// PX haze composite (W1-D; doc docs/builds/px_haze.md): ONE compute pass at the output resolution. Input 0 = scene
// RGBA premultiplied, input 1 = the half-res haze (px_haze.glsl; bilinear, inputfiltertype linear). Haze over scene:
// rgb = src * (1 - h.a) + h.rgb; alpha (uHc.y = 1) = src.a * (1 - h.a) + h.a so empty pixels take the haze.
// uHc.x = amount: 0 = exact passthrough (nothing sampled). PX wave 2 can fold pxhApply into px_post instead (its
// input 2 is free) and drop this op. Mirrors px_haze_logic.ref_composite. ASCII only.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uHc;        // x amount, y alpha mode (1 = haze raises alpha), z w -

vec4 pxhApply(vec4 src, vec4 h, float amount, float alphaMode)
{
	h *= amount;
	vec4 o = src;
	o.rgb = src.rgb * (1.0 - h.a) + h.rgb;
	if (alphaMode > 0.5) o.a = src.a * (1.0 - h.a) + h.a;
	return o;
}

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	if (g.x >= sz.x || g.y >= sz.y) return;
	if (g.x >= int(uTDOutputInfo.res.z) || g.y >= int(uTDOutputInfo.res.w)) return;
	vec4 src = texelFetch(sTD2DInputs[0], g, 0);
	if (uHc.x <= 0.0) { TDImageStoreOutput(0, ivec3(g, 0), src); return; }
	vec2 uv = (vec2(g) + 0.5) / vec2(sz);
	vec4 h = textureLod(sTD2DInputs[1], uv, 0.0);
	TDImageStoreOutput(0, ivec3(g, 0), pxhApply(src, h, uHc.x, uHc.y));
}
