// GEN_clone render, GLSL MAT vertex shader: one instance per clone (Geometry COMP instancing, manual count = N; no
// instance attributes, no POPs, T-124). The clone data comes from the `clones` texture (sClones, 5 texels per clone,
// layout in gen_clone_layout.glsl): p = pos + rotate(q, TDPos() * scale xyz * uniform scale * card aspect).
// Hidden / out-of-range clones have scale 0 -> a degenerate instance (no pixels). Mirror: gen_clone_logic.vertex_ref.
uniform sampler2D sClones;
uniform vec4 uR;   // CW, count N, card (1 = the source is a card: x scaled by uR.w), card aspect (w / h)
out Vert { vec3 wpos; vec3 wnorm; vec2 tuv; vec4 col; float toff; } oVert;

vec3 gcRot(vec4 q, vec3 v) { return v + 2.0 * cross(q.yzw, cross(q.yzw, v) + q.x * v); }

void main()
{
	int i = TDInstanceID();
	int cw = max(int(uR.x + 0.5), 1);
	ivec2 b = ivec2(5 * (i % cw), i / cw);
	vec4 t0 = texelFetch(sClones, b, 0);
	vec4 t1 = texelFetch(sClones, b + ivec2(1, 0), 0);
	vec4 t2 = texelFetch(sClones, b + ivec2(2, 0), 0);
	vec4 t3 = texelFetch(sClones, b + ivec2(3, 0), 0);
	bool ok = i < int(uR.y + 0.5);
	float ql = length(t1);
	vec4 q = ql > 1e-8 ? t1 / ql : vec4(1.0, 0.0, 0.0, 0.0);
	vec3 s = t3.xyz * (ok ? t0.w : 0.0);
	if (uR.z > 0.5) s.x *= uR.w;
	vec3 p = t0.xyz + gcRot(q, TDPos() * s);
	vec4 worldSpacePos = TDDeform(p);
	gl_Position = TDWorldToProj(worldSpacePos);
#ifndef TD_PICKING_ACTIVE
	oVert.wpos = worldSpacePos.xyz;
	oVert.wnorm = normalize(TDDeformNorm(gcRot(q, TDNormal())));
	oVert.tuv = uv[0].st;
	oVert.col = t2;
	oVert.toff = t3.w;
#else
	TDWritePickingValues();
#endif
}
