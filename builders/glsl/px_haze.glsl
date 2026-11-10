// PX haze pass (W1-D; doc docs/builds/px_haze.md): ONE compute pass at quarter (FX_haze default) or half resolution. Depth haze with height falloff
// and fbm drift, fog lit by up to 8 lights (point / spot / area / directional; in-scatter by equiangular sampling,
// Kulla & Fajardo 2012) and screen-space light shafts (Mitchell, GPU Gems 3 ch. 13) occluded by the scene's alpha
// (+ depth when wired). Output rgba16float: rgb = light the haze adds (premultiplied), a = 1 - transmittance (how much
// the haze hides what is behind it); px_haze_comp.glsl (or PX post) applies it: out = src * (1 - a) + rgb.
// Inputs (exactly 2 wired, T-84/T-88): 0 = scene RGBA premultiplied (any res; alpha = occluder), 1 = depth (r; a 1x1
// Constant when there is none, depth mode none). Uniforms: px_haze_logic.haze_rows / light_rows; uHt = time from a TOP
// expression so uH stays static (T-143). Colours: the W1-B shared palette; px_haze_logic.shader_text() prepends
// px_palette.glsl (uPal[16] + uPalCtl, pxColSrc). uHazeCs = colour source: each light's fog colour =
// pxColSrc(uHazeCs, Hazecol, light colour, k) x intensity (mode source = the light's own colour, the default; index =
// light k gets stop k), ambient haze = pxColSrc(uHazeCs, Hazecol, Hazecol, march end / maxdist).
// Mirrors px_haze_logic.ref_haze. ASCII only.
//
// uH rows: 0 cam pos, tan(fovx/2) | 1 right, aspect at pack (unused: the shader takes the aspect of its own output,
//          so the rows never read a TOP size and stay event-driven, live b5) | 2 up, near | 3 fwd, far | 4 haze colour, density
//          5 floor y, falloff, noise, noise scale | 6 wind xyz, extinction | 7 lit tint rgb, gain
//          8 g, ambient, steps, soft radius | 9 shafts amount, decay, length, taps
//          10 threshold, disc radius, occlusion, light count | 11 depth mode, depth scale, objdist, maxdist
//          12 noise per sample, jitter, shaft mip lod (input filter mipmap), -
// uHL rows per light (5): pos, type (0 point 1 spot 2 area 3 directional) | axis, range | colour rgb, shaft
//          weight | cos outer, cos inner, half width, half height | intensity, area U axis xyz (0 = derived)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uH[13];
uniform vec4 uHL[40];
uniform vec4 uHazeCs;    // W1-B colour source (mode, pos, spread, keep)
uniform vec4 uHt;        // x = seconds (noise drift), y = frame (jitter)

float gAsp = 1.0, gTx = 1.0, gTy = 1.0;          // set first in main(): own aspect, tan(fov/2) x / y

float pxhFract1(float x) { return x - floor(x); }

float pxhHash(vec3 p)
{
	p = fract(p * 0.3183099 + 0.1) * 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float pxhNoise(vec3 x)
{
	vec3 i = floor(x);
	vec3 f = x - i;
	f = f * f * (3.0 - 2.0 * f);
	float x00 = mix(pxhHash(i), pxhHash(i + vec3(1.0, 0.0, 0.0)), f.x);
	float x10 = mix(pxhHash(i + vec3(0.0, 1.0, 0.0)), pxhHash(i + vec3(1.0, 1.0, 0.0)), f.x);
	float x01 = mix(pxhHash(i + vec3(0.0, 0.0, 1.0)), pxhHash(i + vec3(1.0, 0.0, 1.0)), f.x);
	float x11 = mix(pxhHash(i + vec3(0.0, 1.0, 1.0)), pxhHash(i + vec3(1.0, 1.0, 1.0)), f.x);
	return mix(mix(x00, x10, f.y), mix(x01, x11, f.y), f.z);
}

float pxhFbm(vec3 p)
{
	return (0.5 * pxhNoise(p) + 0.25 * pxhNoise(p * 2.03 + 17.1) + 0.125 * pxhNoise(p * 4.01 + 31.7)) / 0.875;
}

float pxhNoiseF(vec3 p)                         // density multiplier: max(1 + N (2 fbm - 1), 0)
{
	if (uH[5].z <= 0.0) return 1.0;
	return max(1.0 + uH[5].z * (2.0 * pxhFbm((p - uH[6].xyz * uHt.x) * uH[5].w) - 1.0), 0.0);
}

float pxhFy(float y)                            // antiderivative of exp(-H max(y - y0, 0)) dy
{
	float u = y - uH[5].x;
	float H = uH[5].y;
	if (H <= 1e-6 || u <= 0.0) return u;
	return (1.0 - exp(-H * u)) / H;
}

float pxhTau(float oy, float dy, float t)       // optical depth over [0, t] (no noise)
{
	float D = uH[4].w;
	if (abs(dy) < 1e-4) {
		float ym = oy + dy * t * 0.5;
		return D * t * (uH[5].y > 1e-6 ? exp(-uH[5].y * max(ym - uH[5].x, 0.0)) : 1.0);
	}
	return D * (pxhFy(oy + dy * t) - pxhFy(oy)) / dy;
}

float pxhSigma(float y)
{
	return uH[4].w * (uH[5].y > 1e-6 ? exp(-uH[5].y * max(y - uH[5].x, 0.0)) : 1.0);
}

float pxhHG(float c)                            // Henyey-Greenstein, isotropic = 1
{
	float g = uH[8].x;
	float q = max(1.0 + g * g - 2.0 * g * c, 1e-6);
	return (1.0 - g * g) / (q * sqrt(q));
}

vec3 pxhDir(vec2 uv)
{
	vec2 n = uv * 2.0 - 1.0;
	return normalize(uH[3].xyz + uH[1].xyz * (n.x * gTx) + uH[2].xyz * (n.y * gTy));
}

float pxhEnd(vec3 d, float alpha, float depth)  // march end distance for this ray
{
	int dm = int(uH[11].x + 0.5);
	float maxd = uH[11].w;
	float te;
	if (dm == 0) {
		te = maxd + (uH[11].z - maxd) * clamp(alpha, 0.0, 1.0);
	} else {
		float nr = uH[2].w, fr = uH[3].w;
		float cosf = max(dot(d, uH[3].xyz), 1e-4);
		bool sky;
		if (dm == 1) {
			float r = depth * uH[11].y;
			te = r / cosf;
			sky = depth <= 0.0 || r >= fr * 0.999;
		} else if (dm == 2) {
			float zn = depth * 2.0 - 1.0;
			te = 2.0 * nr * fr / max(fr + nr - zn * (fr - nr), 1e-6) / cosf;
			sky = depth >= 0.99999;
		} else {
			float r = depth * uH[11].y;
			te = r;
			sky = depth <= 0.0 || r >= fr * 0.999;
		}
		if (sky) te = maxd;
		// uH[12].w > 0.5 (PX wave 3: depth = the geometry only): covered pixels of the scene (alpha) also end the
		// march at the object distance, so splats / points keep their fog in front (min of both ends)
		if (uH[12].w > 0.5) te = min(te, maxd + (uH[11].z - maxd) * clamp(alpha, 0.0, 1.0));
	}
	return min(te, maxd);
}

// screen uv of light i (+ its distance); false when behind the camera
bool pxhScreen(int i, out vec2 suv, out float dist, out float zl)
{
	vec4 L0 = uHL[i * 5], L1 = uHL[i * 5 + 1];
	vec3 v;
	float zmin;
	if (int(L0.w + 0.5) == 3) { v = -L1.xyz; dist = 1e30; zmin = 1e-6; }
	else { v = L0.xyz - uH[0].xyz; dist = length(v); zmin = uH[2].w; }
	float z = dot(v, uH[3].xyz);
	zl = z;
	suv = vec2(0.0);
	if (z <= zmin) return false;
	suv = vec2(0.5 + 0.5 * dot(v, uH[1].xyz) / (z * gTx), 0.5 + 0.5 * dot(v, uH[2].xyz) / (z * gTy));
	return true;
}

vec3 pxhLightCol(int i)                         // fog colour x intensity of light i
{
	return pxColSrc(uHazeCs, uH[4].rgb, uHL[i * 5 + 2].rgb, float(i)) * uHL[i * 5 + 4].x;
}

// lit fog of light i along o + d t, t in [0, te]; nmid = noise factor of the transmittance, S = integral sigma T dt
vec3 pxhLight(int i, vec3 lc, vec3 o, vec3 d, float te, float nmid, float S, float j, float Fo)
{
	vec4 L0 = uHL[i * 5], L1 = uHL[i * 5 + 1], L3 = uHL[i * 5 + 3];
	int typ = int(L0.w + 0.5);
	if (typ == 3) return lc * (pxhHG(-dot(d, L1.xyz)) * S);
	float ext = uH[6].w, r0 = uH[8].w;
	int steps = int(uH[8].z + 0.5);
	vec3 P = L0.xyz;
	vec3 rel = P - o;
	float dl = dot(d, rel);
	float h0 = length(rel - d * dl);
	float hs = sqrt(h0 * h0 + r0 * r0);
	float rng = L1.w;
	float ta = 0.0, tb = te;
	if (rng > 0.0) {
		if (h0 >= rng) return vec3(0.0);
		float half_ = sqrt(max(rng * rng - h0 * h0, 0.0));
		ta = max(ta, dl - half_);
		tb = min(tb, dl + half_);
	}
	if (tb <= ta) return vec3(0.0);
	float tha = atan((ta - dl) / hs);
	float thb = atan((tb - dl) / hs);
	bool perS = uH[12].x > 0.5;
	float nl = perS ? 1.0 : pxhNoiseF(o + d * clamp(dl, ta, tb));
	vec3 an = L1.xyz, au = vec3(1.0, 0.0, 0.0), av = vec3(0.0, 0.0, 1.0);
	if (typ == 2) {
		vec3 ua = uHL[i * 5 + 4].yzw;
		if (dot(ua, ua) > 0.25) au = ua;
		else { vec3 a = abs(an.y) < 0.99 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0); au = normalize(cross(a, an)); }
		av = cross(an, au);
	}
	float acc = 0.0;
	for (int k = 0; k < 32; k++) {
		if (k >= steps) break;
		float uk = (float(k) + j) / float(steps);   // smoothstep warp: dense at both ends where T moves fast
		float wk = 6.0 * uk * (1.0 - uk);
		float th = tha + (thb - tha) * (uk * uk * (3.0 - 2.0 * uk));
		float t = dl + hs * tan(th);
		vec3 p = o + d * t;
		float nf = perS ? pxhNoiseF(p) : nl;
		// one exp shared by the density and the optical depth (live perf pass, b5)
		float u = p.y - uH[5].x;
		float e = (uH[5].y > 1e-6 && u > 0.0) ? exp(-uH[5].y * u) : 1.0;
		float tau = abs(d.y) < 1e-4 ? pxhTau(o.y, d.y, t)
		          : uH[4].w * (((uH[5].y <= 1e-6 || u <= 0.0) ? u : (1.0 - e) / uH[5].y) - Fo) / d.y;
		float T = exp(-ext * tau * nmid);
		float sg = uH[4].w * e * nf;
		vec3 lv = p - P;
		float geo = 1.0, dist;
		vec3 wi;
		if (typ == 2) {
			vec3 q = P + au * clamp(dot(lv, au), -L3.z, L3.z) + av * clamp(dot(lv, av), -L3.w, L3.w);
			vec3 lq = p - q;
			float dq2 = dot(lq, lq) + r0 * r0;
			wi = lq / max(length(lq), 1e-6);
			geo = (dot(lv, lv) + r0 * r0) / dq2 * max(dot(wi, an), 0.0);
			dist = sqrt(dq2);
		} else {
			dist = length(lv);
			wi = lv / max(dist, 1e-6);
			if (typ == 1) geo = smoothstep(L3.x, L3.y, dot(wi, an));
		}
		float win = 1.0;
		if (rng > 0.0) { float x = dist / rng; x = clamp(1.0 - x * x * x * x, 0.0, 1.0); win = x * x; }
		acc += sg * T * pxhHG(-dot(wi, d)) * geo * win * wk;
	}
	float fn = float(steps);
	return lc * ((thb - tha) / hs * acc / (fn * (1.0 + 0.5 / (fn * fn))));
}

float pxhLuma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

// screen-space shafts of all lights at uv (Mitchell radial march toward each light's screen position)
vec3 pxhShafts(vec2 uv, float j)
{
	vec3 out_ = vec3(0.0);
	float amt = uH[9].x;
	if (amt <= 0.0) return out_;
	int taps = int(uH[9].w + 0.5);
	int nl = int(uH[10].w + 0.5);
	float asp = gAsp, disc = uH[10].y, thr = uH[10].x;
	int dm = int(uH[11].x + 0.5);
	for (int i = 0; i < 8; i++) {
		if (i >= nl) break;
		float shw = uHL[i * 5 + 2].w;
		if (shw <= 0.0) continue;
		vec2 suv;
		float ldist, zl;
		if (!pxhScreen(i, suv, ldist, zl)) continue;
		// depth occlusion threshold in the depth input's own units (one compare per tap, live perf pass b5):
		// anything nearer than the light blocks it; directional lights: none
		float lz = -1.0;
		if (dm > 0 && int(uHL[i * 5].w + 0.5) != 3) {
			if (dm == 1) lz = zl / max(uH[11].y, 1e-9);
			else if (dm == 2) {
				float nr = uH[2].w, fr = uH[3].w;
				lz = 0.5 + 0.5 * (fr + nr - 2.0 * fr * nr / zl) / (fr - nr);
			} else lz = ldist / max(uH[11].y, 1e-9);
		}
		vec2 delta = (uv - suv) * (uH[9].z / float(taps));
		float acc = 0.0, dcy = 1.0;
		for (int k = 0; k < 64; k++) {
			if (k >= taps) break;
			vec2 c = uv - delta * (float(k + 1) + j);
			bool inside = all(greaterThanEqual(c, vec2(0.0))) && all(lessThanEqual(c, vec2(1.0)));
			vec4 s = textureLod(sTD2DInputs[0], c, uH[12].z);   // coarser mip: shafts are blurry anyway (perf)
			float occ = inside ? s.a * uH[10].z : 0.0;
			if (lz > 0.0 && inside) {
				float dd = textureLod(sTD2DInputs[1], c, uH[12].z).r;
				if (dd > 0.0 && dd < lz) occ = 1.0;
			}
			vec2 q = (c - suv) * vec2(asp, 1.0);
			float src = exp(-dot(q, q) / (disc * disc));
			if (thr > 0.0 && inside) src += max(pxhLuma(s.rgb) - thr, 0.0);
			acc += (1.0 - clamp(occ, 0.0, 1.0)) * src * dcy;
			dcy *= uH[9].y;
		}
		out_ += pxhLightCol(i) * (acc * (shw * amt / float(taps)));
	}
	return out_;
}

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	ivec2 res = ivec2(uTDOutputInfo.res.zw);
	if (g.x >= res.x || g.y >= res.y) return;
	vec2 uv = (vec2(g) + 0.5) / vec2(res);
	gAsp = float(res.x) / float(max(res.y, 1));
	gTx = uH[0].w;
	gTy = gTx / gAsp;
	// interleaved gradient noise (Jimenez 2014): the shaft taps always start at a per-pixel offset (fine dither
	// instead of the stair bands Mitchell's fixed taps give, seen live on b5); Jitter on = it moves per frame and the
	// in-scatter samples use it too (needs a temporal blur after)
	float jon = uH[12].y > 0.5 ? 1.0 : 0.0;
	float js = pxhFract1(52.9829189 * pxhFract1(dot(vec2(g) + 5.588238 * mod(uHt.y, 64.0) * jon,
	                                                 vec2(0.06711056, 0.00583715))));
	float j = jon > 0.5 ? js : 0.5;
	vec3 o = uH[0].xyz;
	vec3 d = pxhDir(uv);
	float al = textureLod(sTD2DInputs[0], uv, 0.0).a;
	float dep = textureLod(sTD2DInputs[1], uv, 0.0).r;
	float te = pxhEnd(d, al, dep);
	float ext = uH[6].w;
	float nmid = pxhNoiseF(o + d * (te * 0.5));
	float tauE = pxhTau(o.y, d.y, te) * nmid;
	float TE = exp(-ext * tauE);
	float Fo = pxhFy(o.y);
	float S = ext > 1e-4 ? (1.0 - TE) / max(ext, 1e-4) : tauE;
	vec3 lit = vec3(0.0);
	int nl = int(uH[10].w + 0.5);
	for (int i = 0; i < 8; i++) {
		if (i >= nl) break;
		lit += pxhLight(i, pxhLightCol(i), o, d, te, nmid, S, j, Fo);
	}
	lit += pxhShafts(uv, js);
	vec3 amb = pxColSrc(uHazeCs, uH[4].rgb, uH[4].rgb, te / uH[11].w);
	vec3 rgb = amb * (uH[8].y * S) + uH[7].rgb * uH[7].w * lit;
	TDImageStoreOutput(0, ivec3(g, 0), vec4(max(rgb, vec3(0.0)), 1.0 - TE));
}
