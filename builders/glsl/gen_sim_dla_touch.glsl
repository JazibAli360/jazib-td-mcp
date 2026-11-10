// gen_sim_dla_touch: GEN_sim 'dla' strike detector + growth normaliser, 2x1 rgba32float in place (outputaccess
// readwrite, clearoutputs off), ONE 32x32 workgroup (manual dispatch 1 x 1).
// (1) Touch: an occupied cell of the current epoch next to an electrode side or within 1.5 cells of the electrode
// disc. While touched the growth stops (the strike holds); Hold s later (Autoregrow on) the regrow count b goes up,
// which changes the effective epoch E = Epoch + 4096 * (b mod 4096) that the field and growth passes compare -> a
// fresh growth. (2) phimax = the largest phi on the field's frontier (a free cell, phi > 0, with a 4-neighbour at
// phi == 0 = grounded); the growth uses phi / (phimax * Phiref), the dielectric breakdown model's normalisation.
// Texel 0: r = touched, g = time of the touch (absTime s), b = regrow count, a = Epoch seen (new Epoch = Reset).
// Texel 1: r = phimax (1 when there is no frontier yet). in0 = cluster (sim size, r = occupied, a = E),
// in1 = field (Feedback, last frame; r = phi). uT = W H epoch now; uT2 = hold autoregrow FW FH;
// uBC = left right bottom top (< 0 Neumann, else electrode side); uTe = cx cy radius (sim cells; radius 0 = none).
// == gen_sim_logic.dla_touched / dla_phimax
layout (local_size_x = 32, local_size_y = 32) in;
uniform vec4 uT;
uniform vec4 uT2;
uniform vec4 uBC;
uniform vec4 uTe;
shared uint hit;                // same-value writes only (no atomics needed)
shared float mx[1024];

bool occAt(ivec2 c, float E)
{
	vec4 s = texelFetch(sTD2DInputs[0], c, 0);
	return s.r > 0.5 && s.a == E;
}

float phiAt(ivec2 f, ivec2 fsz)
{
	if (f.x < 0 || f.y < 0 || f.x >= fsz.x || f.y >= fsz.y) return 1.0;
	return texelFetch(sTD2DInputs[1], f, 0).r;
}

void main()
{
	vec4 st = TDImageLoadOutput(0, ivec3(0));
	if (st.a != uT.z) st = vec4(0.0, 0.0, 0.0, uT.z);
	float E = uT.z + 4096.0 * mod(st.b, 4096.0);
	ivec2 sz = ivec2(uT.xy);
	ivec2 fsz = ivec2(uT2.zw);
	bool ok = textureSize(sTD2DInputs[0], 0) == sz;
	bool fok = textureSize(sTD2DInputs[1], 0) == fsz && texelFetch(sTD2DInputs[1], ivec2(0), 0).a == E;
	uint li = gl_LocalInvocationIndex;
	if (li == 0u) hit = 0u;
	bool h = false;
	if (ok) {
		for (int i = int(li); i < max(sz.x, sz.y); i += 1024) {
			if (i < sz.y && uBC.x >= 0.0) h = h || occAt(ivec2(0, i), E);
			if (i < sz.y && uBC.y >= 0.0) h = h || occAt(ivec2(sz.x - 1, i), E);
			if (i < sz.x && uBC.z >= 0.0) h = h || occAt(ivec2(i, 0), E);
			if (i < sz.x && uBC.w >= 0.0) h = h || occAt(ivec2(i, sz.y - 1), E);
		}
		if (uTe.z > 0.0) {                              // ring around the electrode disc (1.5 cells wide)
			int r = int(ceil(uTe.z + 2.0));
			int bw = 2 * r + 1;
			for (int i = int(li); i < bw * bw; i += 1024) {
				ivec2 c = ivec2(uTe.xy) + ivec2(i % bw - r, i / bw - r);
				if (c.x < 0 || c.y < 0 || c.x >= sz.x || c.y >= sz.y) continue;
				if (length(vec2(c) + 0.5 - uTe.xy) <= uTe.z + 1.5) h = h || occAt(c, E);
			}
		}
	}
	float m = 0.0;
	if (fok) {
		for (int i = int(li); i < fsz.x * fsz.y; i += 1024) {
			ivec2 f = ivec2(i % fsz.x, i / fsz.x);
			float p = phiAt(f, fsz);
			if (p <= m) continue;                       // m >= 0, so this also skips grounded cells
			if (phiAt(f + ivec2(1, 0), fsz) == 0.0 || phiAt(f - ivec2(1, 0), fsz) == 0.0
				|| phiAt(f + ivec2(0, 1), fsz) == 0.0 || phiAt(f - ivec2(0, 1), fsz) == 0.0) m = p;
		}
	}
	mx[li] = m;
	barrier();
	if (h) hit = 1u;
	for (uint s = 512u; s > 0u; s >>= 1u) {
		if (li < s) mx[li] = max(mx[li], mx[li + s]);
		barrier();
	}
	if (li != 0u) return;
	if (hit != 0u && st.r < 0.5) { st.r = 1.0; st.g = uT.w; }
	if (st.r > 0.5 && uT2.y > 0.5 && uT.w - st.g >= uT2.x) { st.r = 0.0; st.b += 1.0; }
	TDImageStoreOutput(0, ivec3(0), st);
	TDImageStoreOutput(0, ivec3(1, 0, 0), vec4(mx[0] > 0.0 ? mx[0] : 1.0, 0.0, 0.0, 1.0));
}
