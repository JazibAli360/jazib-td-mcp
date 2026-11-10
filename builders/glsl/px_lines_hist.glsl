// px_lines_hist.glsl - PX lines pass, TRAIL HISTORY: ONE compute pass per frame (T-46/T-47), cooks only while Trails
// is on. Mirrors px_lines_logic.ref_hist_step. Text = glsl_header() + px_lines_common.glsl + this.
// Inputs: 0 = points (as px_lines_seg), 1 = last history (Feedback TOP of this op).
// Output rgba32f, width samples + 2, height tracks. Row = one track:
//   col 0 = head P.xyz, age s        col 1 = life id, life s, reset n, 0
//   col 2 + i = ring slot i: P.xyz, life id + 1 (0 = never written). Slot h = floor(frame / every) % samples is written
//   on frames where frame % every == 0, so the newest slot is always h.
// Motion 0 (points): the head IS point id = first + floor(track * count / tracks) (PX state P: moving points leave
// trails; a jump > Maxjump starts a new life = no segment across the jump). Motion 1 (flow): the head is a particle
// spawned on a random point (or in a unit ball around the vortex centre when there are no points), advected by
// Trdir * speed + an analytic curl field + a vortex (swirl around the axis, pull toward the centre), respawned after
// its life (life = Trlife x (0.5 + rand)).
layout (local_size_x = 8, local_size_y = 8) in;

int plSide() { return max(textureSize(sTD2DInputs[0], 0).x / max(int(uL[R_G1].y + 0.5), 1), 1); }
int plAvail()
{
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	int n = plSide() * sz.y;
	int c = int(uL[R_G1].x + 0.5);
	return c > 0 ? min(c, n) : n;
}
vec3 plPoint(int id)
{
	int side = plSide();
	return texelFetch(sTD2DInputs[0], ivec2((id % side) * max(int(uL[R_G1].y + 0.5), 1), id / side), 0).xyz;
}

// curl of A = (sin(a y + t1) cos(b z + t2), sin(a z + t3) cos(b x + t4), sin(a x + t5) cos(b y + t6)), divergence free;
// scaled so |v| <= 2 x Trcurl
vec3 plCurl(vec3 p, float t)
{
	float a = uL[R_TR3].x, b = 1.31 * uL[R_TR3].x;
	float t1 = 0.0 + 0.11 * t, t2 = 1.7 + 0.13 * t, t3 = 2.9 + 0.07 * t, t4 = 4.1 + 0.17 * t, t5 = 5.3 + 0.05 * t,
	      t6 = 0.6 + 0.19 * t;
	float dAzdy = -b * sin(a * p.x + t5) * sin(b * p.y + t6);
	float dAydz = a * cos(a * p.z + t3) * cos(b * p.x + t4);
	float dAxdz = -b * sin(a * p.y + t1) * sin(b * p.z + t2);
	float dAzdx = a * cos(a * p.x + t5) * cos(b * p.y + t6);
	float dAydx = -b * sin(a * p.z + t3) * sin(b * p.x + t4);
	float dAxdy = a * cos(a * p.y + t1) * cos(b * p.z + t2);
	return vec3(dAzdy - dAydz, dAxdz - dAzdx, dAydx - dAxdy) * (2.0 * uL[R_TR2].w / max(a + b, 1e-6));
}
vec3 plFlow(vec3 p, float t)
{
	vec3 v = uL[R_TR2].xyz * uL[R_TR1].w + plCurl(p, t);
	vec3 r = p - uL[R_TR4].xyz;
	vec3 k = uL[R_TR5].xyz;
	vec3 sw = cross(k, r);
	if (length(sw) > 1e-6) v += uL[R_TR3].y * normalize(sw);
	if (length(r) > 1e-6) v -= uL[R_TR3].z * normalize(r);
	return v;
}

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = ivec2(uTDOutputInfo.res.zw);
	if (g.x >= osz.x || g.y >= osz.y) return;
	int ns = max(int(uL[R_TR0].y + 0.5), 2);
	int tracks = max(int(uL[R_TR0].x + 0.5), 1);
	int tr = g.y;
	bool sizeok = textureSize(sTD2DInputs[1], 0) == osz;
	vec4 H0 = sizeok ? texelFetch(sTD2DInputs[1], ivec2(0, tr), 0) : vec4(0.0);
	vec4 H1 = sizeok ? texelFetch(sTD2DInputs[1], ivec2(1, tr), 0) : vec4(0.0);
	bool init = !sizeok || abs(H1.z - uT.w) > 0.5;
	float lid = init ? 0.0 : H1.x, life = init ? 0.0 : H1.y, age = init ? 0.0 : H0.w;
	vec3 P = H0.xyz;
	float dt = uT.z;
	int av = plAvail();
	int f = clamp(int(uL[R_TR1].x + 0.5), 0, av);
	int cnt = int(uL[R_TR1].y + 0.5);
	cnt = cnt > 0 ? min(cnt, av - f) : av - f;
	uint seed = uint(uL[R_G1].z);
	if (uL[R_TR0].w < 0.5)
	{
		vec3 Pn = cnt > 0 ? plPoint(f + int(floor(float(tr) * float(cnt) / float(tracks)))) : vec3(0.0);
		if (!init && uL[R_TR5].w > 0.0 && length(Pn - P) > uL[R_TR5].w) lid += 1.0;
		P = Pn;
		age = init ? 0.0 : age + dt;
	}
	else if (init || age >= life)
	{
		lid += 1.0;
		uint L = uint(lid);
		if (cnt > 0) P = plPoint(f + min(int(plH3(uint(tr), L, seed) * float(cnt)), cnt - 1));
		else
		{
			vec3 rnd = vec3(plH3(uint(tr), L, seed + 3u), plH3(uint(tr), L, seed + 4u), plH3(uint(tr), L, seed + 5u));
			P = uL[R_TR4].xyz + (rnd * 2.0 - 1.0);
		}
		age = 0.0;
		life = uL[R_TR1].z * (0.5 + plH3(uint(tr), L, seed + 1u));
	}
	else
	{
		P += plFlow(P, uT.x) * dt;
		age += dt;
	}
	if (g.x == 0) { TDImageStoreOutput(0, ivec3(g, 0), vec4(P, age)); return; }
	if (g.x == 1) { TDImageStoreOutput(0, ivec3(g, 0), vec4(lid, life, uT.w, 0.0)); return; }
	int ev = max(int(uL[R_TR0].z + 0.5), 1);
	int fr = int(uT.y + 0.5);
	int h = (fr / ev) % ns;
	vec4 prev = init ? vec4(0.0) : texelFetch(sTD2DInputs[1], g, 0);
	TDImageStoreOutput(0, ivec3(g, 0), (fr % ev == 0 && g.x - 2 == h) ? vec4(P, lid + 1.0) : prev);
}
