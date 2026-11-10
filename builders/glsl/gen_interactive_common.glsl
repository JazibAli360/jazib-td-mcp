// gen_interactive_common: put after gen_sim_common.glsl (hash, value noise, palette gs_pal, blend gs_blend) in front
// of every GEN_interactive pass by builders/gen_interactive.py glsl_text(). No uniforms here (each pass declares its
// own). == builders/gen_interactive_logic.py (env, level, ABSENT).
// Points texture (rack `pts_tex`, N x 1 rgba32f): texel i = (x, y, vx, vy), x y in 0..1 of the frame (y up),
// velocity in frame units / s; absent = x = y = -10 (test: x > -1).
#define GI_TAU 6.28318530718

bool gi_present(vec4 q) { return q.x > -1.0; }

// beat pulse: d = rack drive (beats, bpm, level, 0), g = module Drive (Beatgain, Beatdecay, Audiogain, Manual)
float gi_env(vec4 d, vec4 g)
{
	float age = (d.x - floor(d.x)) * 60.0 / max(d.y, 1.0);
	return g.x * exp(-age / max(g.y, 1e-3));
}

float gi_level(vec4 d, vec4 g) { return g.z * d.z + g.w; }

vec2 gi_perp(vec2 v) { return vec2(-v.y, v.x); }

// distance from p to segment a-b; h = position along it (0 at a, 1 at b)
float gi_segdist(vec2 p, vec2 a, vec2 b, out float h)
{
	vec2 pa = p - a, ba = b - a;
	float bb = dot(ba, ba);
	h = bb > 1e-12 ? clamp(dot(pa, ba) / bb, 0.0, 1.0) : 0.0;
	return length(pa - ba * h);
}

// self-clocked state: meta texel m = (a, T module time, last absTime, epoch). Returns dt of this cook (0 on a second
// cook in the same frame or on a fresh state; capped at 0.1 s so a stall or a bypass never jumps the motion).
float gi_dt(vec4 m, float now, bool fresh)
{
	if (fresh) return 0.0;
	return clamp(now - m.z, 0.0, 0.1);
}
