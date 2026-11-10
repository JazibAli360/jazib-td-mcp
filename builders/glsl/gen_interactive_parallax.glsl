// gen_interactive_parallax: GEN_interactive 'parallax' (FX7a SX-30 / FX7c 7C-31 / FX7b TC-05: a still + its depth map
// becomes a slowly moving 2.5D "3D photo"; depth bands as a mode). ONE compute pass, frame size.
// in0 = slot input (base for the blend), in1 = colour (the still, or the slot input), in2 = depth (r, larger = nearer
// after Depthlo / Depthhi / Invert). Relief march (parallax occlusion, front to back): the surface at layer t in 1..0
// shows the picture point uv - D(t), D(t) = O t + (uv - 0.5) Dolly t; the first layer whose depth there is >= t is
// hit (nearer layers first = correct occlusion), then a binary refine between the last miss and the hit.
// O = 0 and Dolly = 0 = the colour exactly (texelFetch at the same size). Fog to Colour A by (1 - depth) x Fog,
// depth bands (TC-05) = gs_pal(band) x (0.4 + 0.8 luma) mixed by Bandmix. == builders/gen_interactive_parallax_logic.py
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uO;      // offset x, y (uv), dolly, steps
uniform vec4 uQ;      // refine steps, depth lo, depth hi, invert
uniform vec4 uB;      // bands, band mix, fog, -

float px_depth(vec2 uv)
{
	float r = texture(sTD2DInputs[2], uv).r;
	float d = clamp((r - uQ.y) / max(uQ.z - uQ.y, 1e-6), 0.0, 1.0);
	return uQ.w > 0.5 ? 1.0 - d : d;
}

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	if (p.x >= sz.x || p.y >= sz.y) return;
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	vec2 uv = (vec2(p) + 0.5) / vec2(sz);
	vec2 O = uO.xy;
	vec2 Dl = (uv - 0.5) * uO.z;
	vec4 col;
	float dep;
	if (O == vec2(0.0) && uO.z == 0.0) {
		col = textureSize(sTD2DInputs[1], 0) == sz ? texelFetch(sTD2DInputs[1], p, 0) : texture(sTD2DInputs[1], uv);
		dep = px_depth(uv);
	} else {
		int n = clamp(int(uO.w + 0.5), 1, 256);
		float tp = 1.0, th = 0.0;
		bool hit = false;
		for (int i = 0; i <= 256; i++) {
			if (i > n) break;
			float t = 1.0 - float(i) / float(n);
			if (px_depth(uv - (O + Dl) * t) >= t) { th = t; hit = true; break; }
			tp = t;
		}
		if (!hit) th = 0.0;
		else if (th < tp) {
			float a = th, b = tp;                            // a = hit, b = the miss before it
			for (int j = 0; j < 16; j++) {
				if (j >= int(uQ.x + 0.5)) break;
				float m = 0.5 * (a + b);
				if (px_depth(uv - (O + Dl) * m) >= m) a = m; else b = m;
			}
			th = a;
		}
		vec2 q = uv - (O + Dl) * th;
		col = texture(sTD2DInputs[1], q);
		dep = px_depth(q);
	}
	int nb = int(uB.x + 0.5);
	if (nb > 0 && uB.y > 0.0) {
		float bi = min(floor(dep * float(nb)), float(nb - 1));
		vec3 bc = gs_pal(nb > 1 ? bi / float(nb - 1) : 0.0) * (0.4 + 0.8 * gs_luma(col.rgb));
		col.rgb = mix(col.rgb, bc, uB.y);
	}
	col.rgb = mix(col.rgb, uCa.rgb, clamp((1.0 - dep) * uB.z, 0.0, 1.0));
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col.rgb * col.a, col.a));
}
