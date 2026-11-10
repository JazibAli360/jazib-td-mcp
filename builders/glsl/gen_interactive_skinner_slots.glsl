// gen_interactive_skinner_slots: GEN_interactive 'skinner' point slots (compute, 64 x (ceil(N / 64) + 1), rgba32f).
// in0 = last slots (Feedback `slots_fb`), in1 = rack mask (gi_mask: r presence, g motion). Slot i = texel (i % 64,
// i / 64) = (x px, y px, valid, motion at it). A slot keeps its point while the point stays inside the mask
// (presence > Threshold) and a Respawn x dt draw passes; else it tries 8 hashed pixels for a new one inside the mask.
// Last row = meta: texel 0 = (cook count, T module time, last absTime, epoch). Self-clocked: Speed 0 or a second cook
// in the same frame holds. == builders/gen_interactive_skinner_logic.py slots_step.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uTime;   // now, Speed, epoch, respawn / s
uniform vec4 uK;      // slots N, presence threshold, seed, -
uniform vec4 uSz;     // frame W, H, -, -

float sk_pres(vec2 q) { return texture(sTD2DInputs[1], q / uSz.xy).r; }

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	int N = max(int(uK.x + 0.5), 1), R = (N + 63) / 64;
	if (p.x >= 64 || p.y > R) return;
	ivec2 ssz = textureSize(sTD2DInputs[0], 0);
	bool fresh = ssz.x != 64 || ssz.y != R + 1;
	vec4 m0 = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], ivec2(0, R), 0);
	fresh = fresh || m0.w != uTime.z;
	bool same = !fresh && m0.z == uTime.x;
	float dt = same ? 0.0 : gi_dt(m0, uTime.x, fresh) * uTime.y;
	bool hold = same || (!fresh && dt <= 0.0);
	float cnt = hold ? m0.x : (fresh ? 0.0 : m0.x) + 1.0;
	if (p.y == R) {
		vec4 o = p.x == 0 ? vec4(cnt, (fresh ? 0.0 : m0.y) + dt, uTime.x, uTime.z) : vec4(0.0);
		TDImageStoreOutput(0, ivec3(p, 0), o);
		return;
	}
	vec4 old = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], p, 0);
	int i = p.y * 64 + p.x;
	if (hold || i >= N) { TDImageStoreOutput(0, ivec3(p, 0), i < N ? old : vec4(0.0)); return; }
	int c = int(cnt), sd = int(uK.z + 0.5);
	vec4 o = vec4(0.0);
	if (!fresh && old.z > 0.5 && sk_pres(old.xy) > uK.y && gs_hash3(i, c, sd) >= uTime.w * dt)
		o = vec4(old.xy, 1.0, texture(sTD2DInputs[1], old.xy / uSz.xy).g);
	else {
		for (int t = 0; t < 8; t++) {
			vec2 q = vec2(gs_hash3(i, c * 8 + t, sd + 1), gs_hash3(i, c * 8 + t, sd + 2)) * uSz.xy;
			if (sk_pres(q) > uK.y) { o = vec4(q, 1.0, texture(sTD2DInputs[1], q / uSz.xy).g); break; }
		}
	}
	TDImageStoreOutput(0, ivec3(p, 0), o);
}
