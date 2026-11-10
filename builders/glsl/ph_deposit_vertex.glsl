// GN_physarum deposit, GLSL MAT vertex shader: one 1-px point per Grid POP point (side x side grid, TDPos() in
// -0.5..0.5; raw `P` reads garbage on POP points here, T-112) -> agent texel -> the agent's trail texel centre.
// Unused slots go outside the clip volume. Additive blend (one/one) into a 32F Render TOP = exact deposit sums.
uniform sampler2D sAg;   // fx_agents (nearest, rgba32float)
uniform vec4 uDep;       // simw, simh, side, deposit
out Vertex { vec4 color; } oV;

void main()
{
	vec2 g = TDPos().xy + 0.5;
	int side = int(uDep.z + 0.5);
	ivec2 t = ivec2(floor(g * float(side - 1) + 0.5));
	vec4 a = texelFetch(sAg, t, 0);
	vec2 ndc = (floor(a.xy) + 0.5) / uDep.xy * 2.0 - 1.0;
	gl_Position = a.w < 0.0 ? vec4(2.0, 2.0, 0.0, 1.0) : vec4(ndc, 0.0, 1.0);
	gl_PointSize = 1.0;
	int s = clamp(int(a.w + 0.5), 0, 2);
	vec3 c = vec3(0.0);
	c[s] = uDep.w;
	oV.color = vec4(c, 1.0);
}
