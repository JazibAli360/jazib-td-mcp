// gen_interactive_pigment_look: trail -> picture over the slot input (compute, slot size). in0 = slot input,
// in1 = trail (bilinear upsample, inputfiltertype linear). Glow = Glow x mean of 12 taps on a ring of Glowwidth px
// (+ 6 at half radius). col = (trail.rgb + glow) x Exposure (premultiplied), a = clamp((trail.a + luma(glow)) x
// Exposure); then gs_blend (Colour page).  == builders/gen_interactive_pigment_logic.py look.
// uL = Exposure, Glow, Glowwidth, 0.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uL;

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= osz.x || p.y >= osz.y) return;
	vec2 x = vec2(p) + 0.5;
	vec2 inv = 1.0 / vec2(osz);
	vec4 t = texture(sTD2DInputs[1], x * inv);
	vec3 gl = vec3(0.0);
	if (uL.y > 0.0) {
		float r = max(uL.z, 0.5);
		for (int k = 0; k < 12; k++) {
			float a = GI_TAU * (float(k) + 0.5) / 12.0;
			gl += texture(sTD2DInputs[1], (x + r * vec2(cos(a), sin(a))) * inv).rgb;
			if (k % 2 == 0) gl += texture(sTD2DInputs[1], (x + 0.5 * r * vec2(cos(a + 0.26), sin(a + 0.26))) * inv).rgb;
		}
		gl *= uL.y / 18.0;
	}
	vec3 col = (t.rgb + gl) * uL.x;
	float a = clamp((t.a + gs_luma(gl)) * uL.x, 0.0, 1.0);
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(texelFetch(sTD2DInputs[0], p, 0), col, a));
}
