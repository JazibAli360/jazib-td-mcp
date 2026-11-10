// BO_particles render, GLSL MAT pixel shader: soft round dot, premultiplied colour (Blend add = one/one,
// alpha = one/one-minus-src-alpha, set on the MAT's blend pars by the builder). Softness 0 = hard disc.
uniform vec4 uP[31];
in Vertex { vec4 color; vec2 q; } iVert;
layout(location = 0) out vec4 fragColor;

void main()
{
	TDCheckDiscard();
	vec2 d = iVert.q * 2.0 - 1.0;
	float soft = clamp(uP[16].x, 0.001, 1.0);
	float m;
	if (int(uP[28].x + 0.5) != 0) m = 1.0 - smoothstep(1.0 - 0.15 * soft, 1.0, max(abs(d.x), abs(d.y)));   // paper / ribbon
	else {
		float r = length(d);
		if (r > 1.0) discard;
		m = 1.0 - smoothstep(1.0 - soft, 1.0, r);
	}
	fragColor = TDOutputSwizzle(iVert.color * m);
}
