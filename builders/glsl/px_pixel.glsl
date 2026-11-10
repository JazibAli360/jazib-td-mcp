// PX_pointfx render, GLSL MAT pixel shader: sprite shapes (px_logic.SPRITES: disc, soft, ring, star, square,
// streak, cube, quad), premultiplied colour (blend set on the MAT: add = one/one, alpha = one/one-minus-src-alpha).
// Streaks: the quad is longer than wide; distance is measured to a capsule so the ends stay round.
// Bokeh rim: defocused points (large CoC) get a brighter rim (Bokehrim). Cube: ray-cast box impostor (camera at the
// origin of camera space, box centre vcen, axes vr0..vr2, half size hs), lit by a fixed camera-space light.
// Quad: an oriented slab (the vertex shader placed it in world space), rounded-square mask. Mirrors ref_sprite_alpha.
uniform vec4 uR[10];
uniform sampler2D sAtlas;    // wave 3 sprite atlas (shape atlas): Atlastop, Atlascols x Atlascols cells
// K21 glyph tiles: a 5x5 pixel font, 32 glyphs sorted sparse -> dense (". / Y 1 7 T V X + K = 4 3 6 8 9 H M N S W Z % 2 A R 0 5 E # * @")
const uint PXGLYPH[32] = uint[32](198u, 1118480u, 18157700u, 4591758u, 32575752u, 32641156u, 18400580u, 18157905u,
	4357252u, 19554962u, 1016800u, 19496002u, 31496254u, 15235630u, 15252014u, 15252526u, 18415153u, 18732593u,
	18667121u, 16267326u, 18405233u, 32575775u, 27070835u, 31504927u, 15269425u, 32045714u, 15324974u, 33060926u,
	33061407u, 11512810u, 22511061u, 15455951u);
in Vertex { vec4 color; vec2 q; float stretch; float bokeh; vec3 vpos; flat vec3 vcen; flat vec3 vr0; flat vec3 vr1;
            flat vec3 vr2; flat float hs; } iVert;
layout(location = 0) out vec4 fragColor;

void main()
{
	TDCheckDiscard();
	int shape = int(uR[1].x + 0.5);
	float soft = clamp(uR[1].y, 0.001, 1.0);
	float s = max(iVert.stretch, 1.0);
	vec2 d = vec2(max(abs(iVert.q.x) * s - (s - 1.0), 0.0), iVert.q.y);
	float r = length(d);
	float m;
	float shade = 1.0;
	if (shape == 6) {
		vec3 rd = normalize(iVert.vpos);
		vec3 ro = -iVert.vcen;                                         // camera (origin) relative to the box centre
		mat3 Rv = mat3(iVert.vr0, iVert.vr1, iVert.vr2);
		vec3 o = transpose(Rv) * ro;
		vec3 dd = transpose(Rv) * rd;
		vec3 inv = 1.0 / (abs(dd) + 1e-8) * sign(dd + 1e-12);
		vec3 t1 = (-vec3(iVert.hs) - o) * inv;
		vec3 t2 = (vec3(iVert.hs) - o) * inv;
		vec3 tn = min(t1, t2);
		vec3 tf = max(t1, t2);
		float tN = max(max(tn.x, tn.y), tn.z);
		float tF = min(min(tf.x, tf.y), tf.z);
		if (tN > tF || tF < 0.0) discard;
		vec3 nl = tN == tn.x ? vec3(-sign(dd.x), 0.0, 0.0) : (tN == tn.y ? vec3(0.0, -sign(dd.y), 0.0) : vec3(0.0, 0.0, -sign(dd.z)));
		vec3 nv = Rv * nl;
		shade = 0.35 + 0.65 * max(dot(nv, normalize(vec3(0.3, 0.6, 0.7))), 0.0);
		m = 1.0;
	}
	else if (shape == 7) m = 1.0 - smoothstep(1.0 - soft * 0.5, 1.0, max(abs(iVert.q.x), abs(iVert.q.y)));
	else if (shape == 8) {                     // glyph tile (K21): cell = int(hs) (px_vert: random / luma / time)
		vec2 u = clamp(iVert.q * 0.5 + 0.5, 0.0, 0.9999);
		ivec2 px = ivec2(floor(u * 5.0));
		int bit = 24 - ((4 - px.y) * 5 + px.x);
		m = ((PXGLYPH[int(iVert.hs) & 31] >> uint(bit)) & 1u) != 0u ? 1.0 : 0.0;
	}
	else if (shape == 9) {                     // pointillist dab (SA35): rotated elongated stroke with bristles
		float h = fract(iVert.hs);
		float an = h * 6.283185307;
		vec2 v = mat2(cos(an), sin(an), -sin(an), cos(an)) * iVert.q;
		float asp = 1.4 + 1.2 * h;
		float e = v.x * v.x / (asp * asp * 0.36) + v.y * v.y / 0.16;
		m = exp(-e * 2.0 / (soft * soft + 0.2)) * (0.7 + 0.3 * sin(v.y * 31.0 + h * 57.0));
		m = clamp(m * 1.3, 0.0, 1.0);
	}
	else if (shape == 10) {                    // atlas sprite (any TOP of Atlascols x Atlascols cells)
		int n = max(int(uR[7].w + 0.5), 1);
		int cell = int(iVert.hs) % (n * n);
		vec2 u = clamp(iVert.q * 0.5 + 0.5, 0.0, 1.0);
		vec4 t = texture(sAtlas, (vec2(float(cell % n), float(n - 1 - cell / n)) + u) / float(n));
		m = max(t.r, max(t.g, t.b));
	}
	else if (shape == 1) m = r > 1.0 ? 0.0 : exp(-r * r * 2.0 / (soft * soft));
	else if (shape == 2) m = 1.0 - smoothstep(0.0, soft * 0.5 + 0.02, abs(r - 0.8));
	else if (shape == 3) m = exp(-abs(d.x * d.y) * 40.0 / soft) * (1.0 - smoothstep(0.6, 1.0, r)) + exp(-r * r * 12.0);
	else if (shape == 4) m = 1.0 - smoothstep(1.0 - soft, 1.0, max(abs(d.x), abs(d.y)));
	else if (shape == 5) m = exp(-d.y * d.y * 4.0 / soft) * (1.0 - smoothstep(1.0 - soft, 1.0, r));
	else m = 1.0 - smoothstep(1.0 - soft, 1.0, r);
	m *= mix(1.0, 0.55 + 0.45 * smoothstep(0.55, 0.95, r) * (1.0 + uR[6].x), iVert.bokeh * clamp(uR[6].x, 0.0, 1.0));
	if (m <= 0.0) discard;
	fragColor = TDOutputSwizzle(vec4(iVert.color.rgb * shade, iVert.color.a) * m);
}
