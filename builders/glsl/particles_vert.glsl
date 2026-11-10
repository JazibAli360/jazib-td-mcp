// BO_particles render, GLSL MAT vertex shader: one camera-facing quad per instance (Geometry COMP instancing,
// manual count = Count; the child is a 1x1 Rectangle SOP, so P.xy is -0.5..0.5). The particle comes straight from
// the state texture (no CPU readback): instance i -> texels (3*(i % side), i / side). Dead / dormant = size 0.
// The builder prepends builders/glsl/px_palette.glsl (W1-B palette: uPal[16] + uPalCtl, pxPal) for Colormode palette.
uniform vec4 uP[31];          // same rows as the compute pass (particles_logic.step)
uniform sampler2D sState;     // the state GLSL TOP (nearest, rgba32float)
out Vertex { vec4 color; vec2 q; } oVert;
const float TAU = 6.283185307179586;

vec3 ramp3(float x)
{
	x = clamp(x, 0.0, 1.0);
	return (x < 0.5) ? mix(uP[17].rgb, uP[18].rgb, x * 2.0) : mix(uP[18].rgb, uP[19].rgb, x * 2.0 - 1.0);
}

void main()
{
	int i = TDInstanceID();
	int side = max(int(uP[1].x + 0.5), 1);
	ivec2 t0 = ivec2((i % side) * 3, i / side);
	vec4 a = texelFetch(sState, t0, 0);
	vec4 b = texelFetch(sState, t0 + ivec2(1, 0), 0);
	vec4 c = texelFetch(sState, t0 + ivec2(2, 0), 0);
	bool alive = i < int(uP[0].w + 0.5) && a.w >= 0.0 && a.w < b.w;
	float x = alive ? clamp(a.w / max(b.w, 1e-6), 0.0, 1.0) : 0.0;
	float shape = mix(1.0, 4.0 * x * (1.0 - x), clamp(uP[15].z, 0.0, 1.0));
	float sz = alive ? uP[15].x * max(1.0 + uP[15].y * (2.0 * fract(c.w) - 1.0), 0.0) * shape : 0.0;
	int cm = int(uP[16].y + 0.5);
	vec3 col;
	if (cm == 0) col = ramp3(x);
	else if (cm == 1) col = ramp3(length(b.xyz) / max(uP[16].z, 1e-6));
	else if (cm == 2) col = c.rgb;
	else if (cm == 4) {                                      // palette (W1-B): t = Palpos + Palspread x attribute
		int pb = int(uP[27].x + 0.5);
		float at = (pb == 0) ? x : ((pb == 1) ? length(b.xyz) / max(uP[16].z, 1e-6)
		         : ((pb == 2) ? fract(c.w) : a.y / max(2.0 * uP[10].y, 1e-6) + 0.5));
		col = pxPal(uP[27].y + uP[27].z * at);
	}
	else col = vec3(1.0);
	float fade = clamp(x * 20.0, 0.0, 1.0) * clamp((1.0 - x) * 10.0, 0.0, 1.0);
	int shp = int(uP[28].x + 0.5);
	float rr = fract(c.w);
	float spin = TAU * (uP[28].y * (0.5 + rr) * max(a.w, 0.0) + rr);
	vec4 cp;
	if (shp == 1) {                                          // paper: quad turning about its own random axis
		vec3 ax = normalize(vec3(fract(rr * 13.37), fract(rr * 71.31), fract(rr * 3.71)) * 2.0 - 1.0 + vec3(1e-3));
		vec3 q = vec3(P.x * 2.0 * sz, P.y * 2.0 * sz * uP[28].z, 0.0);
		float cs = cos(spin), sn = sin(spin);
		q = q * cs + cross(ax, q) * sn + ax * dot(ax, q) * (1.0 - cs);           // Rodrigues
		vec3 n = vec3(0.0, 0.0, 1.0) * cs + cross(ax, vec3(0.0, 0.0, 1.0)) * sn + ax * ax.z * (1.0 - cs);
		col *= uP[28].w + (1.0 - uP[28].w) * abs(dot(n, uP[29].xyz));       // two-sided: faces flip bright / dark
		cp = uTDMats[TDCameraIndex()].worldCam * vec4(a.xyz + q, 1.0);
	} else {
		cp = uTDMats[TDCameraIndex()].worldCam * vec4(a.xyz, 1.0);
		if (shp == 2) {                                      // streamer: ribbon along the view-space velocity, twisting
			vec2 v2 = (uTDMats[TDCameraIndex()].worldCam * vec4(b.xyz, 0.0)).xy;
			float vl = length(v2);
			vec2 d2 = vl > 1e-6 ? v2 / vl : vec2(0.0, 1.0);
			float tw = abs(cos(spin));
			col *= 0.35 + 0.65 * tw;
			cp.xy += d2 * (P.y * 2.0 * sz * uP[29].w) + vec2(-d2.y, d2.x) * (P.x * 2.0 * sz * (0.05 + 0.95 * tw));
		}
		else cp.xy += P.xy * (2.0 * sz);                     // Size = quad half-width in world units
	}
	oVert.color = vec4(col * (uP[15].w * fade), fade);      // premultiplied
	oVert.q = P.xy + 0.5;
	gl_Position = uTDMats[TDCameraIndex()].proj * cp;
}
