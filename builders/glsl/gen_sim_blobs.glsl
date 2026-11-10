// gen_sim_blobs: GEN_sim 'blobs' 2D metaballs / SDF blend, one compute pass at the slot input's size.
// Blob k (0..Count-1, Count <= MAXB) moves analytically from the module clock (Motion), radius r_k (Radius, Rvar,
// Pulse). Field 0 metaball: F = sum (1 - d^2 / S^2)^3 (d < S, Wyvill soft object, compact support), S = r /
// sqrt(1 - T^(1/3)) so a lone blob's surface (F = T) is exactly r. Field 1 SDF: smooth-min (polynomial, k =
// Softness px) of circles |p - c| - r. Signed distance sd (px, < 0 inside): field 1 directly, field 0 (T - F) / |grad F|.
// Tile culling: each 16x16 workgroup lists the blobs whose support reaches it (ordered by k: a prefix-sum
// compaction, no atomics), so the per-pixel loop only visits those. == gen_sim_logic.blob_params / blob_field.
// in0 = slot input, in1 = clock. uB1 = count radius rvar pulse; uB2 = field threshold softness motion;
// uB3 = style edgewidth bands refract; uB4 = seed pulserate height spec.
// Style: 0 flat (per-blob palette), 1 mercury, 2 neon outline, 3 contour bands, 4 glass (refracts the input).
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uB1;
uniform vec4 uB2;
uniform vec4 uB3;
uniform vec4 uB4;

#define MAXB 1024
#define PER 4
shared vec4 bl[MAXB];          // cx cy r S (support radius, px)
shared float bh[MAXB];         // palette coordinate of the blob
shared uint scn[2 * 256];
shared uint nlist;

vec4 blobAt(int k, vec2 sz, float t, out float hue)
{
	int sd = int(uB4.x);
	float h1 = gs_hash3(k, 1, sd), h2 = gs_hash3(k, 2, sd), h3 = gs_hash3(k, 3, sd), h4 = gs_hash3(k, 4, sd);
	float h5 = gs_hash3(k, 5, sd), h6 = gs_hash3(k, 6, sd);
	hue = gs_hash3(k, 9, sd);
	float m = min(sz.x, sz.y);
	int motion = int(uB2.w + 0.5);       // 0 wander (Lissajous), 1 lava (rise / fall), 2 orbit, 3 drift (noise)
	vec2 c;
	float w1 = 0.2 + 0.4 * h3, w2 = 0.2 + 0.4 * h4;
	float p1 = 2.0 * GS_PI * h5, p2 = 2.0 * GS_PI * h6;
	if (motion == 1) c = vec2(sz.x * (0.1 + 0.8 * h1) + 0.06 * m * sin(t * w2 + p2), sz.y * (0.5 + 0.42 * sin(t * w1 * 0.5 + p1)));
	else if (motion == 2) {
		float a = t * (w1 - 0.4) * 1.5 + p1;
		c = 0.5 * sz + (0.1 + 0.35 * h2) * m * vec2(cos(a), sin(a));
	} else if (motion == 3)
		c = sz * vec2(gs_vnoise(vec2(t * 0.25 * w1, float(k) * 7.31), sd + 11), gs_vnoise(vec2(t * 0.25 * w2, float(k) * 3.17), sd + 12));
	else c = sz * (0.5 + 0.42 * vec2(sin(t * w1 + p1), sin(t * w2 + p2)));
	float r = uB1.y * (1.0 + uB1.z * (2.0 * h2 - 1.0)) * (1.0 + uB1.w * sin(t * uB4.y * 2.0 * GS_PI + p2));
	r = max(r, 0.5);
	float T = clamp(uB2.y, 0.001, 0.999);
	float S = (uB2.x < 0.5) ? r / sqrt(1.0 - pow(T, 1.0 / 3.0)) : r + max(uB2.z, 0.0);
	return vec4(c, r, S);
}

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	vec2 sz = vec2(osz);
	float t = texelFetch(sTD2DInputs[1], ivec2(0), 0).x;
	int n = clamp(int(uB1.x + 0.5), 0, MAXB);
	uint li = gl_LocalInvocationIndex;
	vec2 lo = vec2(gl_WorkGroupID.xy * 16u), hi = lo + 16.0;
	float pad = max(uB3.y, 0.0) * 4.0 + 2.0 + max(uB3.w, 0.0);   // outline / glow / refraction reach
	// 1) each thread tests its PER consecutive blobs (k = li * PER + j) against the tile
	uint mine = 0u;
	vec4 cb[PER];
	float ch[PER];
	for (int j = 0; j < PER; j++) {
		int k = int(li) * PER + j;
		cb[j] = vec4(0.0);
		ch[j] = 0.0;
		if (k >= n) continue;
		float hue;
		vec4 b = blobAt(k, sz, t, hue);
		vec2 dq = max(max(lo - b.xy, b.xy - hi), vec2(0.0));
		if (length(dq) <= b.w + pad) { cb[mine] = b; ch[mine] = hue; mine++; }
	}
	// 2) exclusive prefix sum of the counts (Hillis-Steele, 8 steps) -> deterministic order by k
	scn[li] = mine;
	uint src = 0u;
	for (uint off = 1u; off < 256u; off <<= 1u) {
		barrier();
		uint v = scn[src * 256u + li];
		if (li >= off) v += scn[src * 256u + li - off];
		scn[(1u - src) * 256u + li] = v;
		src = 1u - src;
	}
	barrier();
	uint start = scn[src * 256u + li] - mine;
	for (uint j = 0u; j < mine; j++) { bl[start + j] = cb[j]; bh[start + j] = ch[j]; }
	if (li == 255u) nlist = scn[src * 256u + li];
	barrier();
	if (p.x >= osz.x || p.y >= osz.y) return;
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	vec2 x = vec2(p) + 0.5;
	uint nl = nlist;
	bool meta = uB2.x < 0.5;
	float T = clamp(uB2.y, 0.001, 0.999);
	float k = max(uB2.z, 1e-3);
	float F = 0.0, sdv = 1e9, wsum = 0.0;
	vec2 gr = vec2(0.0);
	float hue = 0.0;
	for (uint i = 0u; i < nl; i++) {
		vec4 b = bl[i];
		vec2 d = x - b.xy;
		float dd = dot(d, d);
		if (meta) {
			float S2 = b.w * b.w;
			if (dd >= S2) continue;
			float q = 1.0 - dd / S2;
			float w = q * q * q;
			F += w;
			gr += -6.0 * q * q * d / S2;
			hue += bh[i] * w;
			wsum += w;
		} else {
			float dl = sqrt(dd);
			float si = dl - b.z;
			vec2 gi = dl > 1e-6 ? d / dl : vec2(0.0);
			float w = exp(-max(si, 0.0) / k);
			hue += bh[i] * w;
			wsum += w;
			if (sdv > 1e8) { sdv = si; gr = gi; continue; }
			float h = max(k - abs(sdv - si), 0.0) / k;
			if (si < sdv) { gr = (1.0 - 0.5 * h) * gi + 0.5 * h * gr; sdv = si - h * h * k * 0.25; }
			else { gr = (1.0 - 0.5 * h) * gr + 0.5 * h * gi; sdv = sdv - h * h * k * 0.25; }
		}
	}
	float gl = length(gr);
	float sd = meta ? ((F > 0.0) ? (T - F) / max(gl, 1e-6) : 1e9) : sdv;
	vec2 nrm = gl > 1e-9 ? (meta ? -gr / gl : gr / gl) : vec2(0.0);   // outward normal in the plane
	hue = wsum > 0.0 ? hue / wsum : 0.0;
	float cov = clamp(0.5 - sd, 0.0, 1.0);
	int style = int(uB3.x + 0.5);
	float ew = max(uB3.y, 0.0);
	vec3 col;
	float a = cov;
	float depth = clamp(-sd / max(uB4.z, 1.0), 0.0, 1.0);          // 0 at the rim, 1 deeper than Height px
	vec3 n3 = normalize(vec3(nrm * (1.0 - depth), max(depth, 0.05)));
	if (style == 1) {                                               // mercury: env bands + specular
		float env = 0.5 + 0.5 * n3.y;
		float spec = pow(max(dot(n3, normalize(vec3(-0.4, 0.6, 0.7))), 0.0), 40.0) * uB4.w;
		col = (gs_pal(env) * (0.35 + 0.65 * env) + spec) * cov;
	} else if (style == 2) {                                        // neon outline
		float ln = 1.0 - smoothstep(ew * 0.5 - 0.5, ew * 0.5 + 0.5, abs(sd));
		float glo = exp(-abs(sd) / max(ew * 2.0, 1.0)) * 0.6;
		a = clamp(ln + glo, 0.0, 1.0);
		col = gs_pal(hue) * a;
	} else if (style == 3) {                                        // contour bands inside
		float bw = max(uB3.z, 1.0);
		float u = -sd / bw;
		float ln = 1.0 - smoothstep(ew * 0.5 - 0.5, ew * 0.5 + 0.5, abs(fract(u + 0.5) - 0.5) * bw);
		col = gs_pal(clamp(u * 0.25, 0.0, 1.0)) * cov * max(ln, 0.25);
	} else if (style == 4) {                                        // glass: the input refracted through the dome
		vec2 off = -nrm * (1.0 - depth) * uB3.w;
		vec3 refr = texture(sTD2DInputs[0], (x + off) / sz).rgb;
		float spec = pow(max(dot(n3, normalize(vec3(-0.4, 0.6, 0.7))), 0.0), 40.0) * uB4.w;
		col = (refr * mix(vec3(1.0), uCa.rgb, 0.35) + spec) * cov;
	} else {
		col = gs_pal(hue) * cov;
	}
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col, a));
}
