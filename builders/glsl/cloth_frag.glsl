// BN_cloth render, GLSL MAT pixel shader: front/back colours, checker / in1 texture, flat / phong / sheen, wire
// grid lines. Lighting is our own (one point light at Light xyz, camera from the engine), not TD lights.
uniform sampler2D sTex;
uniform vec4 uGrid;    // W, H, 0, 0
uniform vec4 uLook0;   // shading (0 flat, 1 phong, 2 sheen), texture (0 checker, 1 in1, 2 none), Texmix, Wire (0/1)
uniform vec4 uLook1;   // light xyz, Texscale (checker cells across)
uniform vec4 uFront;   // rgb, 1
uniform vec4 uBack;    // rgb, 1
uniform vec4 uCam;     // camera position xyz, 0
in Vert { vec3 wpos; vec3 wnorm; vec2 tuv; } iVert;
layout(location = 0) out vec4 fragColor;

void main()
{
	TDCheckDiscard();
	vec3 n = normalize(iVert.wnorm);
	bool front = gl_FrontFacing;
	if (!front) n = -n;
	vec3 base = front ? uFront.rgb : uBack.rgb;
	vec2 t = iVert.tuv;
	int tm = int(uLook0.y + 0.5);
	vec3 tex = vec3(1.0);
	if (tm == 0) {
		vec2 q = floor(t * max(uLook1.w, 1.0));
		tex = mod(q.x + q.y, 2.0) < 0.5 ? vec3(0.92) : vec3(0.35);
	} else if (tm == 1) tex = texture(sTex, t).rgb;
	base *= mix(vec3(1.0), tex, uLook0.z);
	vec3 L = normalize(uLook1.xyz - iVert.wpos);
	vec3 V = normalize(uCam.xyz - iVert.wpos);
	int sh = int(uLook0.x + 0.5);
	vec3 col = base;
	if (sh >= 1) {
		float diff = max(dot(n, L), 0.0);
		float spec = pow(max(dot(reflect(-L, n), V), 0.0), 32.0) * 0.25;
		col = base * (0.25 + 0.75 * diff) + vec3(spec);
		if (sh == 2) col += base * pow(1.0 - max(dot(n, V), 0.0), 3.0) * 0.6;
	}
	if (uLook0.w > 0.5) {
		vec2 g = t * (uGrid.xy - 1.0);
		vec2 f = abs(fract(g - 0.5) - 0.5) / max(fwidth(g), vec2(1e-6));
		col = mix(col, vec3(1.0), 1.0 - min(min(f.x, f.y), 1.0));
	}
	fragColor = TDOutputSwizzle(vec4(col, 1.0));
}
