// gen_interactive_mask: the rack's shared presence / motion map `gi_mask` (compute, Maskw x Maskh, rgba16float).
// in0 = mask source at mask res (`mask_small`: the Mask TOP in mode top, else the background picture), in1 = the
// last output (Feedback TOP `mask_fb`). Out: r = presence 0..1, g = motion (|luma - last luma| x Motiongain, one-pole
// smoothed by Motionsmooth per cook), b = this luma (for the next cook), a = 1.
// == builders/gen_interactive_logic.py mask_step. uM1 = mode channel thresh soft; uM2 = motiongain motionsmooth
// invert 0. No history yet (the blank's alpha 0, or a size change) = motion 0.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uM1;
uniform vec4 uM2;

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= sz.x || p.y >= sz.y) return;
	vec4 s = texelFetch(sTD2DInputs[0], p, 0);
	float lum = gs_luma(s.rgb);
	int mode = int(uM1.x + 0.5);
	int ch = int(uM1.y + 0.5);
	float pres;
	if (mode == 0) pres = 1.0;
	else if (mode == 1) pres = clamp(ch == 0 ? s.r : (ch == 1 ? s.a : lum), 0.0, 1.0);
	else {
		float sf = max(uM1.w, 1e-4);
		float t = clamp((lum - (uM1.z - sf)) / (2.0 * sf), 0.0, 1.0);
		pres = t * t * (3.0 - 2.0 * t);
	}
	if (uM2.z > 0.5) pres = 1.0 - pres;
	ivec2 psz = textureSize(sTD2DInputs[1], 0);
	float mot = 0.0;
	if (psz == sz) {
		vec4 pv = texelFetch(sTD2DInputs[1], p, 0);
		if (pv.a > 0.5) mot = pv.g * uM2.y + abs(lum - pv.b) * uM2.x * (1.0 - uM2.y);
	}
	TDImageStoreOutput(0, ivec3(p, 0), vec4(pres, mot, lum, 1.0));
}
