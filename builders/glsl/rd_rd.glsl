// rd pass fx_rd (sim res, npasses = Steps): ONE Gray-Scott step per pass; passes >= nsteps copy (Pause / Stopat).
// Isotropic 3x3 Laplacian (Sims) or anisotropic (bilinear second derivative along a direction field); optional
// semi-Lagrangian flow: the whole stencil is read at p - v. == rd_pass() in the logic.
// in0 = previous pass (fx_seed for pass 0), in1 = fx_maps (mask, mmap, flow.xy)
// Fused path (perf wave 27 Oct, uBlk.x = 1: Fusesteps on, iso, no flow): each pass runs up to RD_H steps on a
// 16 x 16 output tile with an RD_H-cell halo in shared memory (temporal blocking, T-199 (3)); npasses = ceil(Steps /
// RD_H). Same per-cell arithmetic as the single-step path below (one dispatch instead of RD_H).
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uSim;    // simw, simh, aspect, edge
uniform vec4 uCtl;    // nsteps this frame, reset, mapimg, seed
uniform vec4 uFK;     // fA, kA, fB, kB
uniform vec4 uRD;     // Da, Db, dt, clamp
uniform vec4 uMorph;  // morph, mapmode, mapamt, mapscale
uniform vec4 uPear;   // fmin, fmax, kmin, kmax
uniform vec4 uAniso;  // mode, amount, angle (rad), noise scale
uniform vec4 uFlow;   // mode, gain, drift x, drift y (cells / step)
uniform vec4 uFlow2;  // curl scale, curl time, feed offset, kill offset
uniform vec4 uBlk;    // fused (0/1), 0, 0, 0

vec2 flowAt(vec2 uv, vec2 dp, vec4 mp, float asp, int s)
{
	int fm = int(uFlow.x + 0.5);
	float g = uFlow.y;
	if (fm == 1) return mp.zw * g;
	if (fm == 2) return uFlow.zw;
	if (fm == 3) return vec2(-dp.y, dp.x) * 2.0 * g;
	if (fm == 4) {
		vec2 n = vec2(uv.x * asp * uFlow2.x + uFlow2.y, uv.y * uFlow2.x);
		float e = 0.01;
		int ss = s + 11;
		float dx = (vnoise(n + vec2(e, 0.0), ss) - vnoise(n - vec2(e, 0.0), ss)) / (2.0 * e);
		float dy = (vnoise(n + vec2(0.0, e), ss) - vnoise(n - vec2(0.0, e), ss)) / (2.0 * e);
		return vec2(dy, -dx) * g;
	}
	return vec2(0.0);
}

#define RD_H 8
#define RD_IN 16
#define RD_T 32
#define RD_PER 4
shared vec2 rdS[2][RD_T * RD_T];

// f, k of one cell (constant over the steps of a frame): == the single-step path's morph / pearson block
vec2 rdFK(ivec2 T, ivec2 sz, vec4 st, vec4 mp, int s)
{
	vec2 uv = (vec2(T) + 0.5) / vec2(sz);
	float asp = float(sz.x) / float(sz.y);
	vec2 dp = (uv - 0.5) * vec2(asp, 1.0);
	int mm = int(uMorph.y + 0.5);
	float mv = 0.0;
	if (mm == 1) mv = uv.x;
	else if (mm == 2) mv = uv.y;
	else if (mm == 3) mv = length(dp) * 2.0;
	else if (mm == 4) mv = vnoise(vec2(uv.x * asp, uv.y) * uMorph.w, s + 7);
	float m = uMorph.x + uMorph.z * mv + uCtl.z * mp.y + st.b;
	float f, k;
	if (mm == 5) {
		f = uPear.x + (uPear.y - uPear.x) * uv.y + uFlow2.z;
		k = uPear.z + (uPear.w - uPear.z) * uv.x + uFlow2.w;
	} else {
		f = uFK.x + (uFK.z - uFK.x) * m + uFlow2.z;
		k = uFK.y + (uFK.w - uFK.y) * m + uFlow2.w;
	}
	return vec2(f, k);
}

void rdFused(ivec2 sz, int e)
{
	int li = int(gl_LocalInvocationIndex);
	ivec2 O = ivec2(gl_WorkGroupID.xy) * RD_IN - RD_H;
	int s = int(uCtl.w + 0.5);
	int nsteps = clamp(int(uCtl.x + 0.5) - uTDPass * RD_H, 0, RD_H);
	ivec2 isz = textureSize(sTD2DInputs[0], 0) - 1;
	ivec2 msz = textureSize(sTD2DInputs[1], 0) - 1;
	vec4 st[RD_PER];
	vec2 fk[RD_PER];
	ivec2 gg[RD_PER];
	for (int j = 0; j < RD_PER; j++) {
		int i = li + j * 256;
		ivec2 L = ivec2(i % RD_T, i / RD_T);
		ivec2 g = edgeT(O + L, sz, e);                     // wrap: the wrapped cell; clamp: the nearest cell
		gg[j] = g;
		st[j] = texelFetch(sTD2DInputs[0], clamp(g, ivec2(0), isz), 0);
		vec4 mp = texelFetch(sTD2DInputs[1], clamp(g, ivec2(0), msz), 0);
		fk[j] = rdFK(g, sz, st[j], mp, s);
		rdS[0][i] = st[j].rg;
	}
	int cur = 0;
	for (int t = 0; t < nsteps; t++) {
		barrier();
		for (int j = 0; j < RD_PER; j++) {
			int i = li + j * 256;
			ivec2 L = ivec2(i % RD_T, i / RD_T);
			if (L.x < 1 || L.y < 1 || L.x > RD_T - 2 || L.y > RD_T - 2) { rdS[1 - cur][i] = rdS[cur][i]; continue; }
			vec2 c2 = rdS[cur][i];
			if (st[j].a > 0.5) { rdS[1 - cur][i] = vec2(1.0, 0.0); continue; }
			int xm = L.x - 1, xp = L.x + 1, ym = L.y - 1, yp = L.y + 1;
			if (e != 0) {                                  // clamp: neighbours of the real cell, clamped to the grid
				ivec2 g = O + L;
				xm = max(g.x - 1, 0) - O.x; xp = min(g.x + 1, sz.x - 1) - O.x;
				ym = max(g.y - 1, 0) - O.y; yp = min(g.y + 1, sz.y - 1) - O.y;
				xm = clamp(xm, 0, RD_T - 1); xp = clamp(xp, 0, RD_T - 1);
				ym = clamp(ym, 0, RD_T - 1); yp = clamp(yp, 0, RD_T - 1);
			}
			vec2 nE = rdS[cur][L.y * RD_T + xp], nW = rdS[cur][L.y * RD_T + xm];
			vec2 nN = rdS[cur][yp * RD_T + L.x], nS = rdS[cur][ym * RD_T + L.x];
			vec2 nNE = rdS[cur][yp * RD_T + xp], nNW = rdS[cur][yp * RD_T + xm];
			vec2 nSE = rdS[cur][ym * RD_T + xp], nSW = rdS[cur][ym * RD_T + xm];
			vec2 lap = LAP_EDGE * ((nE - c2) + (nW - c2) + (nN - c2) + (nS - c2));
			lap += LAP_DIAG * ((nNE - c2) + (nNW - c2) + (nSE - c2) + (nSW - c2));
			float f = fk[j].x, k = fk[j].y;
			float A = c2.x, B = c2.y;
			float abb = A * B * B;
			float A2 = A + (uRD.x * lap.x - abb + f * (1.0 - A)) * uRD.z;
			float B2 = B + (uRD.y * lap.y + abb - (k + f) * B) * uRD.z;
			if (uRD.w > 0.5) { A2 = clamp(A2, 0.0, 1.0); B2 = clamp(B2, 0.0, 1.0); }
			rdS[1 - cur][i] = vec2(A2, B2);
		}
		cur = 1 - cur;
	}
	barrier();
	for (int j = 0; j < RD_PER; j++) {
		int i = li + j * 256;
		ivec2 L = ivec2(i % RD_T, i / RD_T);
		ivec2 T = O + L;
		if (L.x < RD_H || L.y < RD_H || L.x >= RD_H + RD_IN || L.y >= RD_H + RD_IN) continue;
		if (T.x >= sz.x || T.y >= sz.y) continue;
		vec4 o = st[j];
		if (nsteps > 0) o.rg = rdS[cur][i];
		TDImageStoreOutput(0, ivec3(T, 0), o);
	}
}

void main()
{
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (uBlk.x > 0.5) { rdFused(sz, int(uSim.w + 0.5)); return; }
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	if (T.x >= sz.x || T.y >= sz.y) return;
	int e = int(uSim.w + 0.5);
	vec4 st = texelFetch(sTD2DInputs[0], clamp(T, ivec2(0), textureSize(sTD2DInputs[0], 0) - 1), 0);
	if (float(uTDPass) >= uCtl.x - 0.5) { TDImageStoreOutput(0, ivec3(T, 0), st); return; }
	if (st.a > 0.5) { TDImageStoreOutput(0, ivec3(T, 0), vec4(1.0, 0.0, st.b, st.a)); return; }
	vec4 mp = texelFetch(sTD2DInputs[1], clamp(T, ivec2(0), textureSize(sTD2DInputs[1], 0) - 1), 0);
	vec2 uv = (vec2(T) + 0.5) / vec2(sz);
	float asp = float(sz.x) / float(sz.y);
	vec2 dp = (uv - 0.5) * vec2(asp, 1.0);
	int s = int(uCtl.w + 0.5);
	int fm = int(uFlow.x + 0.5);
	vec2 v = flowAt(uv, dp, mp, asp, s);
	vec2 c2;
	vec2 lap;
	vec2 P = vec2(T) + 0.5 - v;
	if (fm == 0) {
		c2 = st.rg;
		// perf: neighbour columns/rows resolved once (the +-1 wrap / clamp of edgeT, without float divisions)
		int xm = T.x - 1, xp = T.x + 1, ym = T.y - 1, yp = T.y + 1;
		if (e == 0) {
			xm = xm < 0 ? sz.x - 1 : xm; xp = xp >= sz.x ? 0 : xp;
			ym = ym < 0 ? sz.y - 1 : ym; yp = yp >= sz.y ? 0 : yp;
		} else {
			xm = max(xm, 0); xp = min(xp, sz.x - 1); ym = max(ym, 0); yp = min(yp, sz.y - 1);
		}
		vec2 nE = texelFetch(sTD2DInputs[0], ivec2(xp, T.y), 0).rg, nW = texelFetch(sTD2DInputs[0], ivec2(xm, T.y), 0).rg;
		vec2 nN = texelFetch(sTD2DInputs[0], ivec2(T.x, yp), 0).rg, nS = texelFetch(sTD2DInputs[0], ivec2(T.x, ym), 0).rg;
		vec2 nNE = texelFetch(sTD2DInputs[0], ivec2(xp, yp), 0).rg, nNW = texelFetch(sTD2DInputs[0], ivec2(xm, yp), 0).rg;
		vec2 nSE = texelFetch(sTD2DInputs[0], ivec2(xp, ym), 0).rg, nSW = texelFetch(sTD2DInputs[0], ivec2(xm, ym), 0).rg;
		lap = LAP_EDGE * ((nE - c2) + (nW - c2) + (nN - c2) + (nS - c2));
		lap += LAP_DIAG * ((nNE - c2) + (nNW - c2) + (nSE - c2) + (nSW - c2));
	} else {
		c2 = BL0(P, e).rg;
		lap = LAP_EDGE * ((BL0(P + vec2(1, 0), e).rg - c2) + (BL0(P + vec2(-1, 0), e).rg - c2) + (BL0(P + vec2(0, 1), e).rg - c2) + (BL0(P + vec2(0, -1), e).rg - c2));
		lap += LAP_DIAG * ((BL0(P + vec2(1, 1), e).rg - c2) + (BL0(P + vec2(-1, 1), e).rg - c2) + (BL0(P + vec2(1, -1), e).rg - c2) + (BL0(P + vec2(-1, -1), e).rg - c2));
	}
	int am = int(uAniso.x + 0.5);
	if (am > 0) {
		vec2 d = vec2(1.0, 0.0);
		bool ok = true;
		if (am == 1) d = vec2(cos(uAniso.z), sin(uAniso.z));
		else if (am == 2 || am == 3) {
			vec2 ex = dp / max(length(dp), 1e-6);
			d = am == 2 ? ex : vec2(-ex.y, ex.x);
		} else if (am == 4) {
			if (fm == 0) ok = false;
			else { float n = length(v); d = n > 1e-6 ? v / n : vec2(1.0, 0.0); }
		} else {
			float a = vnoise(vec2(uv.x * asp, uv.y) * uAniso.w, s + 5) * (4.0 * PI);
			d = vec2(cos(a), sin(a));
		}
		if (ok) {
			vec2 dd = BL0(P + d, e).rg - 2.0 * c2 + BL0(P - d, e).rg;
			lap = (1.0 - uAniso.y) * lap + uAniso.y * ANISO_TRACE * dd;
		}
	}
	int mm = int(uMorph.y + 0.5);
	float mv = 0.0;
	if (mm == 1) mv = uv.x;
	else if (mm == 2) mv = uv.y;
	else if (mm == 3) mv = length(dp) * 2.0;
	else if (mm == 4) mv = vnoise(vec2(uv.x * asp, uv.y) * uMorph.w, s + 7);
	float m = uMorph.x + uMorph.z * mv + uCtl.z * mp.y + st.b;
	float f, k;
	if (mm == 5) {
		f = uPear.x + (uPear.y - uPear.x) * uv.y + uFlow2.z;
		k = uPear.z + (uPear.w - uPear.z) * uv.x + uFlow2.w;
	} else {
		f = uFK.x + (uFK.z - uFK.x) * m + uFlow2.z;
		k = uFK.y + (uFK.w - uFK.y) * m + uFlow2.w;
	}
	float A = c2.x, B = c2.y;
	float abb = A * B * B;
	float A2 = A + (uRD.x * lap.x - abb + f * (1.0 - A)) * uRD.z;
	float B2 = B + (uRD.y * lap.y + abb - (k + f) * B) * uRD.z;
	if (uRD.w > 0.5) { A2 = clamp(A2, 0.0, 1.0); B2 = clamp(B2, 0.0, 1.0); }
	TDImageStoreOutput(0, ivec3(T, 0), vec4(A2, B2, st.b, st.a));
}
