// gen_interactive_ribbon_hist: GEN_interactive 'ribbon' history ring (compute, Length x (Ribbons + 1), rgba32float).
// in0 = last state (Feedback TOP `hist_fb`), in1 = points (`pts`, rack pts_tex). Row i < R = ribbon i: texel k =
// ring sample (x px, y px, t module time when taken, valid 1 / 0 = pen up). Row R = meta: texel 0 = (head, T module
// time, last absTime, epoch), texel 1 = (time of the last sample, samples taken, 0, 0).
// A cook in a new frame advances T by dt x Speed; a new sample is taken when T - last >= Sampleevery (Speed 0 =
// frozen: no samples, ages hold). A second cook in the same frame copies (readbacks never step it). A new epoch
// (Reset) or a size change clears the ring.  == builders/gen_interactive_ribbon_logic.py hist_step.
// uTime = now (absTime.seconds), Speed, epoch, Sampleevery; uRib = R, L, Pointstart, 0; uSz = frame W, H, 0, 0.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uTime;
uniform vec4 uRib;
uniform vec4 uSz;

void main()
{
	ivec2 p = ivec2(gl_GlobalInvocationID.xy);
	int R = int(uRib.x + 0.5), L = int(uRib.y + 0.5);
	if (p.x >= L || p.y > R) return;
	ivec2 ssz = textureSize(sTD2DInputs[0], 0);
	bool fresh = ssz.x != L || ssz.y != R + 1;
	vec4 m0 = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], ivec2(0, R), 0);
	vec4 m1 = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], ivec2(1, R), 0);
	fresh = fresh || m0.w != uTime.z;
	if (fresh) { m0 = vec4(float(L - 1), 0.0, uTime.x, uTime.z); m1 = vec4(-1e9, 0.0, 0.0, 0.0); }
	vec4 old = fresh ? vec4(0.0) : texelFetch(sTD2DInputs[0], p, 0);
	if (!fresh && m0.z == uTime.x) { TDImageStoreOutput(0, ivec3(p, 0), old); return; }   // same frame: hold
	float dt = gi_dt(m0, uTime.x, fresh);
	float T = m0.y + dt * uTime.y;
	bool take = (T - m1.x) >= max(uTime.w, 0.0) && (fresh || T != m1.x);
	int head = int(m0.x + 0.5);
	if (take) head = (head + 1) % L;
	if (p.y == R) {
		vec4 o = vec4(0.0);
		if (p.x == 0) o = vec4(float(head), T, uTime.x, uTime.z);
		else if (p.x == 1) o = vec4(take ? T : m1.x, m1.y + (take ? 1.0 : 0.0), 0.0, 0.0);
		TDImageStoreOutput(0, ivec3(p, 0), o);
		return;
	}
	if (take && p.x == head) {
		int i = p.y + int(uRib.z + 0.5);
		ivec2 psz = textureSize(sTD2DInputs[1], 0);
		vec4 q = (i >= 0 && i < psz.x) ? texelFetch(sTD2DInputs[1], ivec2(i, 0), 0) : vec4(-10.0, -10.0, 0.0, 0.0);
		bool ok = gi_present(q);
		old = vec4(ok ? q.xy * uSz.xy : vec2(0.0), T, ok ? 1.0 : 0.0);
	}
	TDImageStoreOutput(0, ivec3(p, 0), old);
}
