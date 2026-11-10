// gen_interactive_linevolume: GEN_interactive 'linevolume' line-volume light sculpture (compute, slot input size,
// stateless). in0 = slot input, in1 = rack points (`pts`), in2 = rack mask (`mask`: r presence).
// Camera at (0, 0, D) looking down -z, focal f = 0.5 / tan(Fov / 2) in screen heights; a view point X lands at
// px = res / 2 + off * H + X.xy * f / (D - X.z) * H (off = Pos + Follow x the first / centroid point).
// Scene 0 wire: the chosen Platonic solid (unit circumradius x Size, Nest copies x Nestscale) rotated R = Rz Ry Rx,
//   every edge a hairline (1 px AA band of Linewidth), depth fade, glow. Scene 1 hatch: ray-sphere (radius Size),
//   object-space stripes Hatchdensity per diameter whose duty follows the light (tonal hatching), optional cross set,
//   rim line. Scene 2 relief: Rows lines on a plane (z = Size .. -Size, near first) tilted by Tilt, raised by
//   Height x the height field (mask presence / slot luma / value noise) at the line's base pixel, nearer lines hide
//   farther ones (Occlude). Scene 3 moire: two line gratings (Spacing, + Moireangle, x (1 + Moirescale)), drifting.
// Drive: beat pulse x Kick -> rotation (y; moire: grating angle), audio / manual -> glow + relief height.
// Reveal: lines x mix(1, presence, Reveal). Loops are bounded (Nest <= 8, Rows <= 512, points <= 256).
// == builders/gen_interactive_linevolume_logic.py shade / pixel (float64 twin, LIVE CHECK V*).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;      // scene solid nest nestscale
uniform vec4 uB;      // size dist f follow
uniform vec4 uRot;    // rx ry rz (rad, incl. spin x T) kick (rad)
uniform vec4 uPos;    // posx posy followrot followmode
uniform vec4 uLn;     // linewidth glow glowwidth depthfade
uniform vec4 uHt;     // hatchdensity hatchangle crosshatch hatchcontrast
uniform vec4 uLt;     // light xyz rim
uniform vec4 uRl;     // rows gridwidth tilt height
uniform vec4 uRl2;    // heightsource noisescale noiseoffset occlude
uniform vec4 uMo;     // spacing moireangle moirescale driftpx
uniform vec4 uMisc;   // reveal revealinvert colourspread seed
uniform vec4 uDrv;
uniform vec4 uDg;

#define MAXNEST 8
#define MAXROWS 512
#define MAXPTS 256
// %SOLIDS%

vec2 RESV;
shared vec3 sPV[MAXNEST * 20];    // wire: projected vertices, once per workgroup (not per pixel)
shared vec4 sFol;                 // follow: offset xy, extra rx, extra ry, once per workgroup

mat3 rotm(float rx, float ry, float rz)
{
	float cx = cos(rx), sx = sin(rx), cy = cos(ry), sy = sin(ry), cz = cos(rz), sz = sin(rz);
	mat3 Rx = mat3(1.0, 0.0, 0.0, 0.0, cx, sx, 0.0, -sx, cx);        // column-major
	mat3 Ry = mat3(cy, 0.0, -sy, 0.0, 1.0, 0.0, sy, 0.0, cy);
	mat3 Rz = mat3(cz, sz, 0.0, -sz, cz, 0.0, 0.0, 0.0, 1.0);
	return Rz * Ry * Rx;
}

vec3 proj(vec3 X, float D, float f, vec2 off)
{
	float den = max(D - X.z, 1e-3);
	return vec3(RESV * 0.5 + off * RESV.y + X.xy * f / den * RESV.y, X.z);
}

float bandpx(float d, float w) { return clamp(0.5 + 0.5 * w - d, 0.0, 1.0); }

vec4 fetchN(int s, vec2 uv)
{
	ivec2 sz = textureSize(sTD2DInputs[s], 0);
	ivec2 c = clamp(ivec2(floor(uv * vec2(sz))), ivec2(0), sz - 1);
	if (s == 0) return texelFetch(sTD2DInputs[0], c, 0);
	if (s == 1) return texelFetch(sTD2DInputs[1], c, 0);
	return texelFetch(sTD2DInputs[2], c, 0);
}

float pyAt(float hh, float z, float ct, float st, float D, float f, float cy)
{
	return cy + (hh * ct - z * st) * f / max(D - (hh * st + z * ct), 1e-3) * RESV.y;
}

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = textureSize(sTD2DInputs[0], 0);
	RESV = vec2(osz);
	float W = RESV.x, H = RESV.y;
	vec2 x = vec2(p) + 0.5;
	int scene = int(uA.x + 0.5);
	float size = uB.x, D = uB.y, f = uB.z;
	uint li = gl_LocalInvocationIndex;
	// follow: first present point or the centroid (thread 0, shared with the workgroup)
	if (li == 0u) {
		vec2 off0 = uPos.xy;
		float arx0 = 0.0, ary0 = 0.0;
		int np_ = min(textureSize(sTD2DInputs[1], 0).x, MAXPTS);
		vec2 acc = vec2(0.0), first = vec2(0.0);
		float cnt = 0.0;
		for (int i = 0; i < MAXPTS; i++) {
			if (i >= np_) break;
			vec4 q = texelFetch(sTD2DInputs[1], ivec2(i, 0), 0);
			if (!gi_present(q)) continue;
			if (cnt == 0.0) first = q.xy;
			acc += q.xy;
			cnt += 1.0;
		}
		if (cnt > 0.0) {
			vec2 t = int(uPos.w + 0.5) == 1 ? acc / cnt : first;
			off0 += uB.w * (t * RESV - 0.5 * RESV) / H;
			arx0 = -uPos.z * GS_PI * (t.y - 0.5);
			ary0 = uPos.z * GS_PI * (t.x - 0.5);
		}
		sFol = vec4(off0, arx0, ary0);
	}
	barrier();
	vec2 off = sFol.xy;
	float arx = sFol.z, ary = sFol.w;
	float env = gi_env(uDrv, uDg), lvl = gi_level(uDrv, uDg);
	float rx = uRot.x + arx, ry = uRot.y + ary + uRot.w * env, rz = uRot.z;
	float lw = uLn.x, glow = uLn.y * (1.0 + lvl), gw = max(uLn.z, 1e-3), dfade = uLn.w;
	float best = 0.0, key = 0.0, gsum = 0.0, dmin = 1e30;
	ivec4 rg = LV_R[clamp(int(uA.y + 0.5), 0, 4)];
	int nest = clamp(int(uA.z + 0.5), 1, MAXNEST);
	if (scene == 0) {                                   // project every vertex once per workgroup
		mat3 R = rotm(rx, ry, rz);
		for (int idx = int(li); idx < MAXNEST * 20; idx += 64) {
			int k = idx / 20, i = idx % 20;
			if (k >= nest || i >= rg.y) continue;
			float sc = size;
			for (int j = 0; j < MAXNEST; j++) { if (j >= k) break; sc *= uA.w; }
			sPV[idx] = proj(R * LV_V[rg.x + i] * sc, D, f, off);
		}
	}
	barrier();
	if (p.x >= osz.x || p.y >= osz.y) return;
	if (scene == 0) {
		float sc = size;
		for (int k = 0; k < MAXNEST; k++) {
			if (k >= nest) break;
			for (int e = 0; e < 30; e++) {
				if (e >= rg.w) break;
				ivec2 ed = LV_E[rg.z + e] - ivec2(rg.x);
				vec3 a = sPV[k * 20 + ed.x], b = sPV[k * 20 + ed.y];
				float h;
				float d = gi_segdist(x, a.xy, b.xy, h);
				float zz = clamp(mix(a.z, b.z, h) / max(sc, 1e-6), -1.0, 1.0);
				float fd = 1.0 - dfade * (0.5 - 0.5 * zz);
				float v = fd * bandpx(d, lw);
				if (v > best) best = v;
				if (d < dmin) { dmin = d; key = 0.5 + 0.5 * zz; }
				if (glow > 0.0) gsum += fd * glow * exp(-d / gw);
			}
			sc *= uA.w;
		}
	} else if (scene == 1) {
		vec2 s = (x - 0.5 * RESV) / H - off;
		vec3 d = normalize(vec3(s, -f));
		float bq = D * d.z;
		float disc = bq * bq - (D * D - size * size);
		float dist = sqrt(max(D * D - bq * bq, 0.0));
		if (uLt.w > 0.5) {
			float rim = abs(dist - size) * f * H / D;
			float v = bandpx(rim, lw);
			if (v > best) { best = v; key = 1.0; }
			if (glow > 0.0) gsum += glow * exp(-rim / gw);
		}
		if (disc > 0.0) {
			float t = -bq - sqrt(disc);
			vec3 X = vec3(t * d.x, t * d.y, D + t * d.z);
			vec3 n = X / size;
			float sh = max(dot(n, uLt.xyz), 0.0);
			vec3 loc = transpose(rotm(rx, ry, rz)) * X;
			float ha = uHt.y, kk = uHt.x / max(2.0 * size, 1e-6);
			float nv = max(abs(dot(n, d)), 0.2);
			float aa = max(kk * (D - X.z) / (f * H) / nv, 1e-4);
			float duty = clamp(0.5 + (sh - 0.5) * uHt.w, 0.0, 1.0);
			float u1 = (loc.x * cos(ha) + loc.y * sin(ha)) * kk;
			float v = clamp(0.5 + (duty * 0.5 - abs(fract(u1) - 0.5)) / aa, 0.0, 1.0);
			if (uHt.z > 0.5) {
				float duty2 = clamp(2.0 * duty - 1.0, 0.0, 1.0);
				float u2 = (-loc.x * sin(ha) + loc.y * cos(ha)) * kk;
				v = max(v, clamp(0.5 + (duty2 * 0.5 - abs(fract(u2) - 0.5)) / aa, 0.0, 1.0));
			}
			if (v >= best) { best = v; key = sh; }
		}
	} else if (scene == 2) {
		int rows = clamp(int(uRl.x + 0.5), 1, MAXROWS);
		float gwid = uRl.y * size, tilt = uRl.z, hgt = uRl.w * (1.0 + lvl);
		int hs = int(uRl2.x + 0.5);
		bool occl = uRl2.w > 0.5;
		float ct = cos(tilt), st = sin(tilt);
		float pad = 1.0 + lw + (glow > 0.0 ? gw * 6.0 : 0.0);
		float ymax = -1e30;
		float cy = 0.5 * H + off.y * H;
		float sxx = (x.x - 0.5 * W) / H - off.x;
		float loh = min(0.0, hgt), hih = max(0.0, hgt);
		for (int k = 0; k < MAXROWS; k++) {
			if (k >= rows) break;
			float t = rows > 1 ? float(k) / float(rows - 1) : 0.0;
			float z = size * (1.0 - 2.0 * t);
			float den0 = max(D - z * ct, 1e-3);
			float xw = sxx * den0 / f;
			if (abs(xw) > gwid) continue;
			float ya = pyAt(loh, z, ct, st, D, f, cy), yb = pyAt(hih, z, ct, st, D, f, cy);
			if (occl && min(ya, yb) > x.y + pad) break;
			if (max(ya, yb) < x.y - pad) continue;
			float y0 = pyAt(0.0, z, ct, st, D, f, cy);
			vec2 uv = vec2(x.x / W, y0 / H);
			float hf;
			if (hs == 0) hf = fetchN(2, uv).r;
			else if (hs == 1) hf = gs_luma(fetchN(0, uv).rgb);
			else hf = gs_vnoise(vec2(xw * uRl2.y, z * uRl2.y + uRl2.z), int(uMisc.w));
			float py = pyAt(hgt * hf, z, ct, st, D, f, cy);
			float dd = abs(x.y - py);
			float vis = occl ? clamp(py - ymax + 0.5, 0.0, 1.0) : 1.0;
			ymax = max(ymax, py);
			float fd = 1.0 - dfade * t;
			float v = vis * fd * bandpx(dd, lw);
			if (v > best) best = v;
			if (dd < dmin) { dmin = dd; key = t; }
			if (glow > 0.0) gsum += vis * fd * glow * exp(-dd / gw);
		}
	} else {
		float sp = max(uMo.x, 1e-3), ang = rz + uRot.w * env;
		vec2 q = x - (0.5 * RESV + off * H);
		for (int g = 0; g < 2; g++) {
			float a = ang + (g == 1 ? uMo.y : 0.0);
			float s_ = g == 1 ? sp * (1.0 + uMo.z) : sp;
			float u = (q.x * cos(a) + q.y * sin(a) + (g == 0 ? uMo.w : -uMo.w)) / s_;
			float dpx = abs(fract(u + 0.5) - 0.5) * s_;
			float v = bandpx(dpx, lw);
			if (v > best) best = v;
			if (dpx < dmin) { dmin = dpx; key = float(g); }
			if (glow > 0.0) gsum += glow * exp(-dpx / gw);
		}
	}
	if (uMisc.x != 0.0) {
		float pres = fetchN(2, x / RESV).r;
		if (uMisc.y > 0.5) pres = 1.0 - pres;
		float k_ = mix(1.0, pres, uMisc.x);
		best *= k_;
		gsum *= k_;
	}
	vec3 c = gs_pal(key * uMisc.z);
	vec3 col = c * (best + gsum);
	float a = clamp(best + gsum * gs_luma(c), 0.0, 1.0);
	vec4 base = texelFetch(sTD2DInputs[0], p, 0);
	TDImageStoreOutput(0, ivec3(p, 0), gs_blend(base, col, a));
}
