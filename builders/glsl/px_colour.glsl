// PX_pointfx COLOUR stage template: ONE compute pass per frame. //@DECL and //@MODULES as in px_update.glsl.
// Inputs: 0 = state (this frame's update output), 1 = rest, 2 = mask TOP.
// Look texture rgba32float, width 3*side (PX_LK): (3x, y) = rgb (HDR, emission applied), alpha
//   (3x+1, y) = size multiplier, stretch (extra length in radii; splats: scale along the stretch axis, may be < 0 to
//   flatten), iso (0..1: blend a splat to an isotropic blob of radius isosize, lattice look), isosize
//   (3x+2, y) = stretch direction xyz (world unit; 0 = screen velocity, the v1 streak), thin (0..1, across it).
// Dissolve fade / size / edge glow are core (DISFADE DISSIZE EDGE*). Pool points: visible only while alive.
layout (local_size_x = 8, local_size_y = 8) in;
#define PX_STATE_TEX(t) texelFetch(sTD2DInputs[0], t, 0)
#define PX_STATE_SIZE textureSize(sTD2DInputs[0], 0)
//@DECL

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	int side = max(pxI(SIDE), 1);
	if (g.x >= side || g.y >= side) return;
	uint id = uint(g.y * side + g.x);
	ivec2 t0 = ivec2(g.x * PX_ST, g.y);
	ivec2 r0p = ivec2(g.x * 4, g.y);
	ivec2 l0 = ivec2(g.x * PX_LK, g.y);
	ivec2 osz = ivec2(uTDOutputInfo.res.zw);                          // T-35: never store out of bounds
	if (l0.x + PX_LK - 1 >= osz.x || l0.y >= osz.y) return;
	ivec2 isz = textureSize(sTD2DInputs[0], 0);
	ivec2 rsz = textureSize(sTD2DInputs[1], 0);
	bool ok = id < uint(max(pxI(COUNT), 0)) && isz.x >= t0.x + PX_ST && isz.y > t0.y && rsz.x >= r0p.x + 4 && rsz.y > r0p.y;
	vec4 r0 = ok ? texelFetch(sTD2DInputs[1], r0p, 0) : vec4(0.0);
	if (!ok || r0.w < 0.5) {
		for (int k = 0; k < PX_LK; k++) TDImageStoreOutput(0, ivec3(l0 + ivec2(k, 0), 0), vec4(0.0));
		return;
	}
	vec4 s0 = texelFetch(sTD2DInputs[0], t0, 0);
	vec4 s1 = texelFetch(sTD2DInputs[0], t0 + ivec2(1, 0), 0);
	vec4 s2 = texelFetch(sTD2DInputs[0], t0 + ivec2(2, 0), 0);
	vec4 s3 = texelFetch(sTD2DInputs[0], t0 + ivec2(3, 0), 0);
	vec4 c0 = texelFetch(sTD2DInputs[1], r0p + ivec2(1, 0), 0);
	int ns = pxI(NSCENE);
	int LAYER = int(id) < ns ? 0 : (int(id) < ns + pxI(NACTOR) ? 1 : 2);
	//@ECHO
	vec3 p0 = r0.xyz;
	float seed = pxRnd(id, 1u);
	vec3 P = s0.xyz;
	float age = s0.w;
	vec3 o = s1.xyz;
	float life = s1.w;
	vec3 v = s2.xyz;
	float heat = s2.w;
	vec3 mk = LAYER == 2 ? vec3(0.0) : s3.xyz;
	vec3 pcol = s3.xyz;                                               // pool: spawn colour
	float dis = s3.w;
	vec3 col = c0.rgb;
	float alpha = c0.a;
	float size = 1.0;
	float stretch = 0.0;
	float emis = 0.0;
	float iso = 0.0;
	float isosize = 0.0;
	vec3 sdir = vec3(0.0);
	float sthin = 0.0;
	//@MODULES
	if (LAYER == 2) {                                                 // embers: only while alive, fading
		bool alive = life > 0.0 && age < life;
		float f = alive ? smoothstep(0.0, 0.05, age) * smoothstep(0.0, 0.2, 1.0 - age / max(life, 1e-3)) : 0.0;
		alpha *= f;
		if (!alive) size = 0.0;
	}
	//@ECHOFADE
	float dd = clamp(dis, 0.0, 1.0);
	alpha *= 1.0 - dd * DISFADE;
	size *= mix(1.0, DISSIZE, dd);
	col += EDGECOL * (4.0 * dd * (1.0 - dd) * EDGEGAIN);
	vec3 outc = max(col, vec3(0.0)) * max(1.0 + emis, 0.0) * BRIGHT;
	if (any(isnan(outc)) || any(isinf(outc))) outc = vec3(0.0);
	TDImageStoreOutput(0, ivec3(l0, 0), vec4(outc, clamp(alpha, 0.0, 1.0)));
	TDImageStoreOutput(0, ivec3(l0 + ivec2(1, 0), 0), vec4(max(size, 0.0), stretch, clamp(iso, 0.0, 1.0), max(isosize, 0.0)));
	TDImageStoreOutput(0, ivec3(l0 + ivec2(2, 0), 0), vec4(sdir, clamp(sthin, 0.0, 1.0)));
}
