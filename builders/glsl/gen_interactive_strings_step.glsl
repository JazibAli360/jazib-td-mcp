// gen_interactive_strings_step: GEN_interactive 'strings' physics (FX7b TC-28 repelling strings; compute, K x (S + 1),
// rgba32float). ONE workgroup per string (local size 256 = nodes; threads >= K idle but join the barriers), so the
// substeps of one cook share node offsets through shared memory. Row s < S = string s: texel k = (offset x, y px,
// velocity x, y px/s) from the rest position. Row S = meta: texel 0 = (0, T module time, last absTime, epoch),
// texel 1 = (last beat count, 0, 0, 0). == builders/gen_interactive_strings_logic.py step.
// in0 = last state (Feedback `state_fb`), in1 = points (`pts`, rack pts_tex: x y vx vy, absent x = -10), in2 = mask
// (`mask`, rack gi_mask: r presence).
// Node acceleration = -Stiffness off + Tension (off[k-1] + off[k+1] - 2 off) - Damping vel + gravity + wind
// + point force (push / pull / swirl within Radius, (1 - r / R)^2) - Maskforce x grad(presence); beat kick = an
// impulse across the strings once per beat; pinned ends stay at rest. dt = module time step (Speed 0 = frozen,
// a second cook in the same frame holds), split into substeps <= Substep s.
layout (local_size_x = 256, local_size_y = 1) in;
uniform vec4 uTime;   // now, Speed, epoch, max substep s
uniform vec4 uS;      // strings S, nodes K, orient (0 vertical, 1 horizontal), margin
uniform vec4 uPh;     // stiffness, tension, damping, gravity px/s2
uniform vec4 uF;      // force px/s2, radius px, mode (0 push, 1 pull, 2 swirl), mask force px/s2
uniform vec4 uX;      // kick px/s, wind px/s2, pin (0 top, 1 both, 2 none), points used
uniform vec4 uSz;     // frame W, H, -, -
uniform vec4 uDrv;
uniform vec4 uDg;

shared vec2 sO[256];

// rest position (frame px) of node k of string s
vec2 st_rest(int s, int k, int S, int K)
{
	float c = uS.w + (float(s) + 0.5) / float(S) * (1.0 - 2.0 * uS.w);
	float a = float(k) / float(K - 1);
	return uS.z < 0.5 ? vec2(c * uSz.x, a * uSz.y) : vec2(a * uSz.x, c * uSz.y);
}

void main()
{
	int k = int(gl_LocalInvocationID.x), s = int(gl_WorkGroupID.y);
	int S = max(int(uS.x + 0.5), 1), K = clamp(int(uS.y + 0.5), 2, 256);
	ivec2 ssz = textureSize(sTD2DInputs[0], 0);
	bool fresh = ssz.x != K || ssz.y != S + 1;
	vec4 m0 = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], ivec2(0, S), 0);
	vec4 m1 = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], ivec2(1, S), 0);
	fresh = fresh || m0.w != uTime.z;
	bool same = !fresh && m0.z == uTime.x;
	float dt = same ? 0.0 : gi_dt(m0, uTime.x, fresh) * uTime.y;
	float T = (fresh ? 0.0 : m0.y) + dt;
	float beat = floor(uDrv.x);
	bool kick = !fresh && !same && beat > m1.x;
	if (s >= S) {                                             // meta row (no barriers in this workgroup)
		if (k == 0) TDImageStoreOutput(0, ivec3(0, S, 0), vec4(0.0, T, uTime.x, uTime.z));
		else if (k == 1) TDImageStoreOutput(0, ivec3(1, S, 0), vec4(same ? m1.x : beat, 0.0, 0.0, 0.0));
		else if (k < K) TDImageStoreOutput(0, ivec3(k, S, 0), vec4(0.0));
		return;
	}
	vec4 old = (fresh || k >= K) ? vec4(0.0) : texelFetch(sTD2DInputs[0], ivec2(min(k, K - 1), s), 0);
	if (same || dt <= 0.0) {                                  // uniform per workgroup: no barrier skipped unevenly
		if (k < K) TDImageStoreOutput(0, ivec3(k, s, 0), old);
		return;
	}
	vec2 off = old.xy, vel = old.zw;
	int kk = min(k, K - 1);
	vec2 P0 = st_rest(s, kk, S, K);
	int pin = int(uX.z + 0.5);
	bool pinned = (kk == 0 && pin < 2) || (kk == K - 1 && pin == 1);
	vec2 side = uS.z < 0.5 ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
	float lev = 1.0 + gi_level(uDrv, uDg);
	if (kick) vel += side * uX.x * lev * ((s & 1) == 0 ? 1.0 : -1.0) * sin(3.14159265 * float(kk) / float(K - 1));
	int n = clamp(int(ceil(dt / max(uTime.w, 1e-4))), 1, 16);
	float h = dt / float(n);
	int np = clamp(int(uX.w + 0.5), 0, min(textureSize(sTD2DInputs[1], 0).x, 64));
	for (int it = 0; it < 16; it++) {
		if (it >= n) break;
		sO[k] = off;
		barrier();
		vec2 lap = kk == 0 ? sO[1] - off : (kk == K - 1 ? sO[K - 2] - off : sO[kk - 1] + sO[kk + 1] - 2.0 * off);
		vec2 P = P0 + off;
		vec2 a = -uPh.x * off + uPh.y * lap - uPh.z * vel + vec2(0.0, -uPh.w);
		a += side * uX.y * sin(T * 1.7 + float(s) * 0.9 + float(kk) * 0.13);
		for (int i = 0; i < 64; i++) {
			if (i >= np) break;
			vec4 q = texelFetch(sTD2DInputs[1], ivec2(i, 0), 0);
			if (!gi_present(q)) continue;
			vec2 d = P - q.xy * uSz.xy;
			float r = length(d);
			if (r >= uF.y || r < 1e-4) continue;
			float f = uF.x * lev * (1.0 - r / uF.y) * (1.0 - r / uF.y);
			vec2 dir = d / r;
			int md = int(uF.z + 0.5);
			a += f * (md == 0 ? dir : (md == 1 ? -dir : gi_perp(dir)));
		}
		if (uF.w != 0.0) {
			vec2 e = vec2(2.0) / uSz.xy;
			vec2 uv = P / uSz.xy;
			float gx = texture(sTD2DInputs[2], uv + vec2(e.x, 0.0)).r - texture(sTD2DInputs[2], uv - vec2(e.x, 0.0)).r;
			float gy = texture(sTD2DInputs[2], uv + vec2(0.0, e.y)).r - texture(sTD2DInputs[2], uv - vec2(0.0, e.y)).r;
			a -= uF.w * vec2(gx, gy);
		}
		vel += a * h;
		off += vel * h;
		if (pinned) { off = vec2(0.0); vel = vec2(0.0); }
		barrier();
	}
	if (k < K) TDImageStoreOutput(0, ivec3(k, s, 0), vec4(off, vel));
}
