// gen_interactive_flowers_water: GEN_interactive 'flowers' waterfall drops (compute, 128 x (ceil(Drops / 64) + 1),
// rgba32float). in0 = last state (Feedback `water_fb`), in1 = rack mask (`mask`: r presence). Drop d = texels
// (2 (d % 64), d / 64): A = (x px, y px, vx px/s, vy px/s), B = (splash 0..1, seed, alive, 0). Meta row (last):
// texel 0 = (cooks, T, last absTime, epoch).
// Step (module dt): v.y -= Gravity dt, v.x += Wind dt; inside a person (presence > 0.5) the velocity into the body
// is removed along n = -grad(presence) (central differences on the mask; flat inside = a hashed side) and Part x dt
// pushes out along n; splash = 1 there, then x exp(-dt / 0.3). Drops below -(64 + |vy| Streak) px or off the sides respawn at the
// top (x hashed, y = H (1 + Topspread h), vy = -Fallspeed (1 + Dropvar (2h - 1))). Mode flowers = no drops.
// == builders/gen_interactive_flowers_logic.py water_step.
// uTime = now Speed epoch Drops; uSz = frame W H Seed Mode; uW1 = Fallspeed Gravity Part Wind;
// uW2 = Topspread Dropvar Streak 0.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uTime;
uniform vec4 uSz;
uniform vec4 uW1;
uniform vec4 uW2;

float presAt(ivec2 q, ivec2 ms)
{
	return texelFetch(sTD2DInputs[1], clamp(q, ivec2(0), ms - 1), 0).r;
}

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	int N = max(int(uTime.w + 0.5), 1);
	int rows = (N + 63) / 64;
	if (p.x >= 128 || p.y > rows) return;
	ivec2 ssz = textureSize(sTD2DInputs[0], 0);
	bool fresh = ssz.x != 128 || ssz.y != rows + 1;
	vec4 m0 = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], ivec2(0, rows), 0);
	fresh = fresh || m0.w != uTime.z;
	if (fresh) m0 = vec4(0.0, 0.0, uTime.x, uTime.z);
	if (!fresh && m0.z == uTime.x) { TDImageStoreOutput(0, ivec3(p, 0), texelFetch(sTD2DInputs[0], p, 0)); return; }
	float dt = gi_dt(m0, uTime.x, fresh) * uTime.y;
	float T = m0.y + dt;
	int cook = int(m0.x + 0.5);
	if (p.y == rows) {
		TDImageStoreOutput(0, ivec3(p, 0), p.x == 0 ? vec4(float(cook + 1), T, uTime.x, uTime.z) : vec4(0.0));
		return;
	}
	int d = p.y * 64 + p.x / 2;
	ivec2 base = ivec2(2 * (p.x / 2), p.y);
	vec4 A = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], base, 0);
	vec4 B = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], base + ivec2(1, 0), 0);
	int mode = int(uSz.w + 0.5);
	vec2 S = uSz.xy;
	int sd = int(uSz.z) + 101;
	if (d >= N || mode == 0) { A = vec4(0.0); B = vec4(0.0); }
	else {
		if (B.z > 0.5 && dt > 0.0) {
			vec2 v = A.zw + vec2(uW1.w, -uW1.y) * dt;
			ivec2 ms = textureSize(sTD2DInputs[1], 0);
			ivec2 q = ivec2(A.xy / S * vec2(ms));
			if (q.x >= 0 && q.y >= 0 && q.x < ms.x && q.y < ms.y && presAt(q, ms) > 0.5) {
				vec2 g = vec2(presAt(q + ivec2(1, 0), ms) - presAt(q - ivec2(1, 0), ms),
				              presAt(q + ivec2(0, 1), ms) - presAt(q - ivec2(0, 1), ms));
				vec2 n = dot(g, g) > 1e-8 ? -normalize(g) : vec2(B.y < 0.5 ? -1.0 : 1.0, 0.0);
				v -= n * min(dot(v, n), 0.0);
				v += n * uW1.z * dt;
				B.x = 1.0;
			} else B.x *= exp(-dt / 0.3);
			A = vec4(A.xy + v * dt, v);
			if (A.y < -(64.0 + abs(A.w) * max(uW2.z, 0.0)) || A.x < -64.0 || A.x > S.x + 64.0) B.z = 0.0;
		}
		if (B.z < 0.5 && (dt > 0.0 || fresh)) {                 // (re)spawn at the top
			float h1 = gs_hash3(d, cook * 4 + 1, sd), h2 = gs_hash3(d, cook * 4 + 2, sd);
			float h3 = gs_hash3(d, cook * 4 + 3, sd);
			A = vec4(h1 * S.x, S.y * (1.0 + max(uW2.x, 0.0) * h2), 0.0, -uW1.x * (1.0 + uW2.y * (2.0 * h3 - 1.0)));
			B = vec4(0.0, h3, 1.0, 0.0);
		}
	}
	TDImageStoreOutput(0, ivec3(p, 0), p.x % 2 == 0 ? A : B);
}
