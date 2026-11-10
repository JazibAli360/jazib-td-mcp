// PX_pointfx UPDATE stage template: ONE compute pass per frame (T-46/T-47). px_logic.codegen replaces //@DECL with
// the uniform declarations + defines + px_common.glsl and //@MODULES with the enabled update modules in stack order.
// Inputs: 0 = last state (Feedback TOP; own output when PX_INPLACE), 1 = rest (source stage), 2 = mask TOP.
// State texture rgba32float, width 5*side (PX_ST), height side; point id = y*side + x, texels:
//   (5x, y) = P visible pos, age   (5x+1, y) = o offset, life   (5x+2, y) = v velocity, heat   (5x+3, y) = mk, dis
//   (5x+4, y) = q: final orientation (wxyz) = module rotation (qrot, S4) x rest quaternion; splats + oriented sprites.
// Rest texture (4 texels): R0 = p0, valid   R1 = colour rgba   R2 = splat scale xyz (0 = none)   R3 = quaternion wxyz.
// Layers (uG[21]): ids [0, NSCENE) scene, then NACTOR actor points, then NPOOL pool points (embers: not pulled home,
// alive while age < life; spawned by prox_burn). Pool points keep their spawn colour in mk (masks do not apply).
layout (local_size_x = 8, local_size_y = 8) in;
#ifdef PX_INPLACE
#define PX_STATE_TEX(t) TDImageLoadOutput(0, ivec3(t, 0))
#define PX_STATE_SIZE ivec2(uTDOutputInfo.res.zw)
#else
#define PX_STATE_TEX(t) texelFetch(sTD2DInputs[0], t, 0)
#define PX_STATE_SIZE textureSize(sTD2DInputs[0], 0)
#endif
//@DECL

void pxStore(ivec2 t0, vec4 a, vec4 b, vec4 c, vec4 d, vec4 e)
{
	TDImageStoreOutput(0, ivec3(t0, 0), a);
	TDImageStoreOutput(0, ivec3(t0 + ivec2(1, 0), 0), b);
	TDImageStoreOutput(0, ivec3(t0 + ivec2(2, 0), 0), c);
	TDImageStoreOutput(0, ivec3(t0 + ivec2(3, 0), 0), d);
	TDImageStoreOutput(0, ivec3(t0 + ivec2(4, 0), 0), e);
}

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	int side = max(pxI(SIDE), 1);
	if (g.x >= side || g.y >= side) return;
	uint id = uint(g.y * side + g.x);
	ivec2 t0 = ivec2(g.x * PX_ST, g.y);
	ivec2 osz = ivec2(uTDOutputInfo.res.zw);                          // T-35: never store out of bounds
	if (t0.x + PX_ST - 1 >= osz.x || t0.y >= osz.y) return;
	bool JUSTRESET = RESET > 0.5;
	vec4 s0 = vec4(0.0), s1 = vec4(0.0), s2 = vec4(0.0), s3 = vec4(0.0);
#ifdef PX_INPLACE
	s0 = TDImageLoadOutput(0, ivec3(t0, 0));
	s1 = TDImageLoadOutput(0, ivec3(t0 + ivec2(1, 0), 0));
	s2 = TDImageLoadOutput(0, ivec3(t0 + ivec2(2, 0), 0));
	s3 = TDImageLoadOutput(0, ivec3(t0 + ivec2(3, 0), 0));
#else
	ivec2 isz = textureSize(sTD2DInputs[0], 0);
	if (isz.x < t0.x + PX_ST || isz.y <= t0.y) JUSTRESET = true;      // last state has another size (Count changed)
	else {
		s0 = texelFetch(sTD2DInputs[0], t0, 0);
		s1 = texelFetch(sTD2DInputs[0], t0 + ivec2(1, 0), 0);
		s2 = texelFetch(sTD2DInputs[0], t0 + ivec2(2, 0), 0);
		s3 = texelFetch(sTD2DInputs[0], t0 + ivec2(3, 0), 0);
	}
#endif
	ivec2 r0p = ivec2(g.x * 4, g.y);
	vec4 r0 = vec4(0.0), r1 = vec4(0.0), r3 = vec4(1.0, 0.0, 0.0, 0.0);
	ivec2 rsz = textureSize(sTD2DInputs[1], 0);
	if (rsz.x >= r0p.x + 4 && rsz.y > r0p.y) {
		r0 = texelFetch(sTD2DInputs[1], r0p, 0);
		r1 = texelFetch(sTD2DInputs[1], r0p + ivec2(1, 0), 0);
		r3 = texelFetch(sTD2DInputs[1], r0p + ivec2(3, 0), 0);
	}
	if (id >= uint(max(pxI(COUNT), 0)) || r0.w < 0.5) {               // unused slot / invalid source point
		pxStore(t0, vec4(r0.xyz, 0.0), vec4(0.0), vec4(0.0), vec4(0.0, 0.0, 0.0, 1.0), vec4(1.0, 0.0, 0.0, 0.0));
		return;
	}
	int ns = pxI(NSCENE);
	int LAYER = int(id) < ns ? 0 : (int(id) < ns + pxI(NACTOR) ? 1 : 2);
	bool POOLPT = LAYER == 2;
	//@ECHO
	vec3 p0 = r0.xyz;
	vec4 c0 = r1;
	float seed = pxRnd(id, 1u);
	float dt = DT;
	vec3 P = s0.xyz;
	float age = s0.w;
	vec3 o = s1.xyz;
	float life = s1.w;
	vec3 v = s2.xyz;
	float heat = s2.w;
	float dis = s3.w;
	vec3 pcol = s3.xyz;                                               // pool points: spawn colour
	if (JUSTRESET) { P = p0; age = 0.0; o = vec3(0.0); life = 0.0; v = vec3(0.0); heat = 0.0; dis = 0.0; pcol = vec3(0.0); }
	vec3 mk = vec3(0.0);
	heat = max(heat - HEATDECAY * dt, 0.0);
	dis = max(dis - DISRECOVER * dt, 0.0);
	age += dt;
	vec3 home = p0;
	vec3 acc = vec3(0.0);
	vec4 qrot = vec4(1.0, 0.0, 0.0, 0.0);                             // module rotations this frame (S4)
	float qid = 0.0;                                                  // pull toward identity orientation (lattice snap)
	//@MODULES
	float hold = POOLPT ? 0.0 : 1.0 - clamp(dis, 0.0, 1.0);           // dissolved / pool points are not pulled home
	acc += -SPRING * hold * o - DAMP * v;
	v += acc * dt;
	v *= exp(-DRAG * dt);
	float sp = length(v);
	if (MAXSPEED > 0.0 && sp > MAXSPEED) v *= MAXSPEED / sp;
	o += v * dt;
	if (POOLPT && !(life > 0.0 && age < life)) { o = vec3(0.0); v = vec3(0.0); }   // dead ember: parked at home
	if (any(isnan(o)) || any(isinf(o)) || any(isnan(v)) || any(isinf(v))) { o = vec3(0.0); v = vec3(0.0); }
	if (any(isnan(home)) || any(isinf(home))) home = p0;
	if (isnan(heat) || isinf(heat)) heat = 0.0;
	if (isnan(dis) || isinf(dis)) dis = 0.0;
	P = home + o;
	vec4 qf = pxQToId(pxQMul(pxQNorm(qrot), pxQNorm(r3)), qid);
	if (any(isnan(qf))) qf = vec4(1.0, 0.0, 0.0, 0.0);
	pxStore(t0, vec4(P, age), vec4(o, life), vec4(v, heat), vec4(POOLPT ? pcol : mk, dis), qf);
}
