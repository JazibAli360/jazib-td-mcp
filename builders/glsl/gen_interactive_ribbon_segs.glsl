// gen_interactive_ribbon_segs: ring samples -> drawable segments (compute, 3 x (L - 1) x Sub wide, R x Strands high,
// rgba32float). in0 = history (`hist`), in1 = slot input (colour mode 'source').
// Segment (x / 3 = j * Sub + q, y = i * Strands + s): ribbon i, strand s, between ring samples j (newer, age order:
// j = 0 is the newest) and j + 1, sub-segment q of a Catmull-Rom curve through samples j-1 .. j+2 (endpoints
// repeated where a neighbour is missing). Texel 0 = (p0.xy, p1.xy) px; 1 = (w0, w1, a0, a1) full widths px + fade
// alpha at both ends; 2 = (r, g, b, valid). Strand s is offset along the curve normal by (s - (S-1)/2) x Spread px x (width / Width),
// plus Wobble px of value noise that sticks to the stroke (keyed by the sample time).
// == builders/gen_interactive_ribbon_logic.py segments.
// uRib = R, L, Sub, Strands; uW = Width, Widthlaw, Speedref, Taper; uW2 = Widthmin, Widthmax, Spread, Wobble;
// uF = Fade, Fadecurve, Wobblefreq, Wobblespeed; uC = Colormode, Seed, Colourspread, 0;
// uDrv = rack drive (beats bpm level 0); uDg = Beatgain Beatdecay Audiogain Manual (beat / audio -> width).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uRib;
uniform vec4 uW;
uniform vec4 uW2;
uniform vec4 uF;
uniform vec4 uC;
uniform vec4 uDrv;
uniform vec4 uDg;

int gR, gL, gHead, gN;
float gT;

// sample j (age order) of ribbon i: (x, y, t, valid); invalid outside the samples taken so far
vec4 smp(int i, int j)
{
	if (j < 0 || j >= gN || j >= gL) return vec4(0.0);
	int k = ((gHead - j) % gL + gL) % gL;
	return texelFetch(sTD2DInputs[0], ivec2(k, i), 0);
}

float speedAt(int i, int j)
{
	vec4 a = smp(i, j), b = smp(i, j + 1);
	if (a.w < 0.5 || b.w < 0.5) {
		vec4 c = smp(i, j - 1);
		if (a.w > 0.5 && c.w > 0.5) return length(c.xy - a.xy) / max(c.z - a.z, 1e-4);
		return 0.0;
	}
	return length(a.xy - b.xy) / max(a.z - b.z, 1e-4);
}

float widthLaw(float sp)
{
	int law = int(uW.y + 0.5);
	float r = sp / max(uW.z, 1e-6);
	float w = uW.x;
	if (law == 1) w = uW.x * r;
	else if (law == 2) w = uW.x / (1.0 + r);
	return clamp(w, uW2.x, max(uW2.y, uW2.x));
}

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	gR = int(uRib.x + 0.5);
	gL = int(uRib.y + 0.5);
	int SUB = max(int(uRib.z + 0.5), 1), S = max(int(uRib.w + 0.5), 1);
	int SW = (gL - 1) * SUB;
	if (p.x >= 3 * SW || p.y >= gR * S) return;
	int comp = p.x % 3, sx = p.x / 3;
	int j = sx / SUB, q = sx % SUB;
	int i = p.y / S, s = p.y % S;
	vec4 m0 = texelFetch(sTD2DInputs[0], ivec2(0, gR), 0), m1 = texelFetch(sTD2DInputs[0], ivec2(1, gR), 0);
	gHead = int(m0.x + 0.5);
	gT = m0.y;
	gN = int(m1.y + 0.5);
	vec4 P1 = smp(i, j), P2 = smp(i, j + 1);
	vec4 o = vec4(0.0);
	if (P1.w < 0.5 || P2.w < 0.5) { TDImageStoreOutput(0, ivec3(p, 0), o); return; }
	vec4 P0 = smp(i, j - 1), P3 = smp(i, j + 2);
	if (P0.w < 0.5) P0 = P1;
	if (P3.w < 0.5) P3 = P2;
	float u0 = float(q) / float(SUB), u1 = float(q + 1) / float(SUB);
	// Catmull-Rom position + tangent at u0 / u1
	vec2 cA[2], tA[2];
	float uu[2];
	uu[0] = u0; uu[1] = u1;
	for (int e = 0; e < 2; e++) {
		float u = uu[e], u2 = u * u, u3 = u2 * u;
		vec2 a = P0.xy, b = P1.xy, c = P2.xy, d = P3.xy;
		cA[e] = 0.5 * (2.0 * b + (c - a) * u + (2.0 * a - 5.0 * b + 4.0 * c - d) * u2 + (3.0 * b - a - 3.0 * c + d) * u3);
		tA[e] = 0.5 * ((c - a) + 2.0 * (2.0 * a - 5.0 * b + 4.0 * c - d) * u + 3.0 * (3.0 * b - a - 3.0 * c + d) * u2);
		if (dot(tA[e], tA[e]) < 1e-12) tA[e] = c - b;
	}
	float sp1 = speedAt(i, j), sp2 = speedAt(i, j + 1);
	float boost = 1.0 + gi_env(uDrv, uDg) + gi_level(uDrv, uDg);
	float fade = uF.x;
	float off = (float(s) - 0.5 * float(S - 1)) * uW2.z;
	vec2 pe[2];
	float we[2], ae[2];
	for (int e = 0; e < 2; e++) {
		float u = uu[e];
		float t = mix(P1.z, P2.z, u);
		float age = max(gT - t, 0.0);
		float al = fade > 0.0 ? pow(clamp(1.0 - age / fade, 0.0, 1.0), max(uF.y, 1e-3)) : 1.0;
		float w = mix(widthLaw(sp1), widthLaw(sp2), u);
		if (fade > 0.0) w *= mix(1.0, clamp(1.0 - age / fade, 0.0, 1.0), clamp(uW.w, 0.0, 1.0));
		w *= boost;
		vec2 tg = tA[e];
		vec2 n = gi_perp(tg / max(length(tg), 1e-9));
		float wob = uW2.w != 0.0 ?
			uW2.w * (2.0 * gs_vnoise(vec2(t * uF.z + gT * uF.w, float(i * 8 + s) * 7.31), int(uC.y) + 3) - 1.0) : 0.0;
		pe[e] = cA[e] + n * (off * max(w / max(uW.x, 1e-6), 0.0) + wob);
		we[e] = max(w, 0.0);
		ae[e] = al;
	}
	if (comp == 0) o = vec4(pe[0], pe[1]);
	else if (comp == 1) o = vec4(we[0], we[1], ae[0], ae[1]);
	else {
		int mode = int(uC.x + 0.5);
		vec2 dv = pe[1] - pe[0];
		float key;
		if (mode == 1) key = atan(dv.y, dv.x) / GI_TAU + 0.5;
		else if (mode == 2) key = fade > 0.0 ? (gT - mix(P1.z, P2.z, 0.5 * (u0 + u1))) / fade : 0.0;
		else if (mode == 3) key = mix(sp1, sp2, 0.5 * (u0 + u1)) / max(uW.z, 1e-6);
		else key = (float(i) + float(s) / float(S)) / max(float(gR), 1.0);
		key *= uC.z;
		vec3 col;
		if (mode == 4) {
			ivec2 isz = textureSize(sTD2DInputs[1], 0);
			ivec2 c = clamp(ivec2(0.5 * (pe[0] + pe[1])), ivec2(0), isz - 1);
			col = texelFetch(sTD2DInputs[1], c, 0).rgb;
		} else col = gs_pal(key);
		o = vec4(col, 1.0);
	}
	TDImageStoreOutput(0, ivec3(p, 0), o);
}
