// PX_pointfx render, GLSL MAT vertex shader: one quad per instance (Geometry COMP instancing, manual count; the
// child is a 1x1 Rectangle SOP, P.xy = -0.5..0.5). Reads the state, look and rest textures (no CPU readback).
// Instance i -> point id = uR[7].x + i * stride (the splat render draws the pool only: uR[7].x = first pool id).
// Size in world units -> px (fy = proj[1][1] * resy / 2), clamped to Minpx..Maxpx, then per-point depth of field:
// CoC px = Aperture * |z - Focus| / z (capped by Maxcoc), alpha scaled by (r0 / r)^2 (energy conserving, no post blur).
// Streak: along the screen velocity (look stretch dir 0), or along a world axis (prox_stretch axis: the two ends
// P +- dir * stretch * size are projected, so view / radial axes fan out from the vanishing point).
// Sprites cube / quad (6 / 7) are oriented by the point's orientation q (state texel 4: splat rotation x module
// rotations): quad = a world-space slab, cube = a ray-cast box impostor (px_pixel.glsl). Mirrors px_logic.ref_sprite.
// T-89: TDCamToProj does not exist on 31550 -> uTDMats[TDCameraIndex()].proj.
// Phase C: uPv.x is a float stride (auto quality draws ceil(n x f) instances, stride 1 / f); uR[9] = LOD (on, start
// distance, share kept far away): past the start a point is kept when its id hash < px_logic.lod_keep(depth), kept
// ones grow by 1 / sqrt(share). Both off = the old shader's numbers exactly.
uniform vec4 uR[10];     // rows: px_logic.render_rows() (row 8: actor echoes, wave 4; row 9: LOD, phase C)
uniform vec4 uPv;        // x = instance stride (preview decimation; auto quality; 1 = every id), y = 1: all ids (preview)
uniform sampler2D sState;
uniform sampler2D sLook;
uniform sampler2D sRest;
out Vertex { vec4 color; vec2 q; float stretch; float bokeh; vec3 vpos; flat vec3 vcen; flat vec3 vr0; flat vec3 vr1;
             flat vec3 vr2; flat float hs; } oVert;

mat3 pvQMat(vec4 q)
{
	float l = length(q);
	q = l > 1e-8 ? q / l : vec4(1.0, 0.0, 0.0, 0.0);
	float w = q.x, x = q.y, y = q.z, z = q.w;
	return mat3(vec3(1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y + w * z), 2.0 * (x * z - w * y)),
	            vec3(2.0 * (x * y - w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z + w * x)),
	            vec3(2.0 * (x * z + w * y), 2.0 * (y * z - w * x), 1.0 - 2.0 * (x * x + y * y)));
}

void main()
{
	float stride = max(uPv.x, 1.0);
	bool all_ = uPv.y > 0.5;                       // preview: every point, whatever the output render draws
	int i = (all_ ? 0 : int(uR[7].x + 0.5)) + int(float(TDInstanceID()) * stride);
	int side = max(int(uR[4].z + 0.5), 1);
	int count = all_ ? int(uR[4].w + 0.5) : min(int(uR[4].w + 0.5), int(uR[7].y + 0.5));
	ivec2 g = ivec2(i % side, i / side);
	bool ok = i < count && i >= 0;
	float esc = 1.0;                               // wave 4: echo copy k draws at Echoscale^k, keeps (1 - Echothin)^k
	if (ok && uR[8].x >= 0.0 && float(i) >= uR[8].x) {
		float k1 = floor((float(i) - uR[8].x) / max(uR[8].y, 1.0)) + 1.0;
		esc = pow(clamp(uR[8].z, 0.0, 1.0), k1);
		uint he = uint(i) * 2654435761u + 40503u;
		he = ((he >> 16u) ^ he) * 73244475u;
		ok = float((he >> 8u) & 0xFFFFFFu) * (1.0 / 16777216.0) < pow(clamp(1.0 - uR[8].w, 0.0, 1.0), k1);
	}
	int shape = int(uR[1].x + 0.5);
	vec4 S0 = vec4(0.0), S2 = vec4(0.0), S4 = vec4(1.0, 0.0, 0.0, 0.0), L0 = vec4(0.0), L1 = vec4(0.0), L2 = vec4(0.0);
	vec4 R1 = vec4(1.0), R2 = vec4(0.0);
	if (ok) L0 = texelFetch(sLook, ivec2(g.x * 3, g.y), 0);
	ok = ok && L0.a * uR[5].x > 0.0;               // early-out (T-143): a dissolved / faded point fetches 1 texel, not 8
	if (ok) S0 = texelFetch(sState, ivec2(g.x * 5, g.y), 0);
	mat4 wc = uTDMats[TDCameraIndex()].worldCam;
	mat4 pr = uTDMats[TDCameraIndex()].proj;
	vec4 cp = wc * vec4(S0.xyz, 1.0);
	float z = max(-cp.z, 1e-4);
	float lodk = 1.0;                              // phase C LOD by distance (uR[9])
	if (ok && uR[9].x > 0.5) {
		float d0 = max(uR[9].y, 1e-3);
		float kk = mix(1.0, clamp(uR[9].z, 0.01, 1.0), clamp((z - d0) / d0, 0.0, 1.0));
		if (kk < 1.0) {
			uint hl = uint(i) * 2654435761u + 40503u;
			hl = ((hl >> 16u) ^ hl) * 73244475u;
			if (float((hl >> 8u) & 0xFFFFFFu) * (1.0 / 16777216.0) >= kk) ok = false;
			else lodk = inversesqrt(kk);
		}
	}
	if (ok) {
		S2 = texelFetch(sState, ivec2(g.x * 5 + 2, g.y), 0);
		S4 = texelFetch(sState, ivec2(g.x * 5 + 4, g.y), 0);
		L1 = texelFetch(sLook, ivec2(g.x * 3 + 1, g.y), 0);
		L2 = texelFetch(sLook, ivec2(g.x * 3 + 2, g.y), 0);
		R1 = texelFetch(sRest, ivec2(g.x * 4 + 1, g.y), 0);
		R2 = texelFetch(sRest, ivec2(g.x * 4 + 2, g.y), 0);
	}
	float fy = pr[1][1] * 0.5 * uR[4].y;
	float wsize = uR[0].x * L1.x * (1.0 - 0.75 * clamp(L2.w, 0.0, 1.0)) * esc;
	float rsum = R2.x + R2.y + R2.z;
	if (uR[5].y > 0.5 && rsum > 0.0) wsize *= rsum / 3.0 * uR[5].z;
	float rpx = clamp(wsize * fy / pow(z, clamp(uR[0].y, 0.0, 1.0)), uR[0].z * esc, max(uR[0].w, uR[0].z * esc)) * lodk;
	float coc = min(uR[3].y * abs(z - uR[3].x) / z, uR[3].z);
	float r = max(rpx, coc);
	float alpha = L0.a * uR[5].x;
	// Source opacity (splat scenes: rest alpha = splat opacity, median ~0.05 on a trained scene): sprites draw it as
	// ra^Ptopacity (0 = opaque points) and hide the floaters below Ptcut. Plain clouds have ra = 1 (no change).
	float ra = clamp(R1.a, 0.0, 1.0);
	alpha = ra < uR[2].z ? 0.0 : alpha * pow(max(ra, 1e-3), uR[5].w - 1.0);
	alpha *= clamp((rpx * rpx) / max(r * r, 1e-6), uR[6].y, 1.0);
	alpha *= exp(-uR[6].z * z);
	vec3 col = L0.rgb;
	float bk = uR[3].z > 0.0 ? clamp(coc / uR[3].z, 0.0, 1.0) : 0.0;
	col *= 1.0 + uR[3].w * smoothstep(1.0, 4.0, dot(col, vec3(0.2126, 0.7152, 0.0722))) * bk;
	// streak direction / length (px): world axis when the look gives one, else the screen-space velocity
	vec2 dir = vec2(1.0, 0.0);
	float slen = 0.0;
	float st = max(L1.y, 0.0);
	if (dot(L2.xyz, L2.xyz) > 1e-8) {
		vec3 ea = S0.xyz + L2.xyz * (st * wsize);
		vec4 ce = wc * vec4(ea, 1.0);
		vec2 se = (ce.xy / max(-ce.z, 1e-4) - cp.xy / z) * fy;
		float sl = length(se);
		dir = sl > 1e-3 ? se / sl : dir;
		slen = min(2.0 * sl, uR[2].y);
	} else if (dot(S2.xyz, S2.xyz) > 1e-12) {      // T-143: a point at rest keeps dir (1, 0); its 'velocity' from
		vec4 cv = wc * vec4(S0.xyz + S2.xyz * 0.01, 1.0);  // projection round-off turned Aspect / star sprites at random
		vec2 vs = (cv.xy / max(-cv.z, 1e-4) - cp.xy / z) * fy * 100.0;
		float vl = length(vs);
		dir = vl > 1e-3 ? vs / vl : dir;
		slen = min(vl * uR[2].x / 60.0 + st * r, uR[2].y);
	} else {
		slen = min(st * r, uR[2].y);
	}
	vec2 c2 = P.xy * 2.0;
	vec2 across = vec2(-dir.y, dir.x);
	float ext = r + 0.5 * slen;
	vec2 off = dir * (c2.x * ext) + across * (c2.y * r * max(uR[1].z, 1e-3));
	float ang = uR[1].w * (fract(float(i) * 0.6180339887) - 0.5) * 6.283185307;
	if (slen < 0.5 && ang != 0.0) {
		float cs = cos(ang), sn = sin(ang);
		off = vec2(cs * off.x - sn * off.y, sn * off.x + cs * off.y);
	}
	mat3 Rq = pvQMat(S4);
	mat3 Rv = mat3(wc) * Rq;                       // box / slab axes in camera space
	float hs = max(rpx * z / max(fy, 1e-4), 1e-6) * 0.6;
	vec4 pos;
	if (shape == 7) {                              // oriented slab: corners in world space (no screen-space clamp)
		vec3 wp = S0.xyz + (Rq[0] * (c2.x * max(uR[1].z, 1e-3)) + Rq[1] * c2.y) * (r * z / max(fy, 1e-4));
		pos = pr * (wc * vec4(wp, 1.0));
		cp = wc * vec4(wp, 1.0);
	} else {
		if (shape == 6) off = c2 * (r * 1.15);     // cube impostor: a screen quad that covers the box
		cp.xy += off * z / max(fy, 1e-4);
		pos = pr * cp;
	}
	bool show = ok && alpha > 0.0 && wsize > 0.0;
	gl_Position = show ? pos : vec4(-9.0, -9.0, -9.0, 1.0);
	float a = clamp(alpha, 0.0, 1.0);
	oVert.color = vec4(col * a * uR[2].w, a);
	oVert.q = c2;
	oVert.stretch = ext / max(r, 1e-4);
	oVert.bokeh = bk;
	oVert.vpos = cp.xyz;
	oVert.vcen = (wc * vec4(S0.xyz, 1.0)).xyz;
	oVert.vr0 = Rv[0];
	oVert.vr1 = Rv[1];
	oVert.vr2 = Rv[2];
	oVert.hs = hs;
	if (shape >= 8) {                              // wave 3 K21 / SA35: glyph / dab / atlas cell (int part) + random (fract)
		uint hx = uint(i) * 747796405u + 2891336453u;                 // pcg hash: no pattern along the id order
		hx = ((hx >> ((hx >> 28u) + 4u)) ^ hx) * 277803737u;
		float h = float((hx >> 22u) ^ hx) * (1.0 / 4294967296.0);
		int ncell = shape == 8 ? 32 : (shape == 10 ? max(int(uR[7].w + 0.5) * int(uR[7].w + 0.5), 1) : 1);
		int md = int(uR[7].z + 0.5);
		int cell = md == 1 ? int(clamp(dot(L0.rgb, vec3(0.2126, 0.7152, 0.0722)), 0.0, 0.9999) * float(ncell))
		         : (md == 2 ? int(h * float(ncell) + uPv.z) % ncell : int(h * float(ncell)));
		oVert.hs = float(cell) + h;
		if (shape == 9 && uR[6].w > 0.0) {         // painterly colour jitter: value +-10 %, a small hue twist
			float h2 = fract(h * 97.31 + 0.37) - 0.5;
			vec3 cj = oVert.color.rgb * (1.0 + 0.2 * h2 * uR[6].w);
			oVert.color.rgb = mix(cj, cj.gbr, 0.08 * uR[6].w * h);
		}
	}
}
