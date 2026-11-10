// PX_pointfx splat adapter (S1-S6): prepended to builders/splat_render.glsl (BL_splat_render's live-verified Gaussian
// splat GLSL MAT) so PX reuses that renderer instead of a second one. The instance custom attributes the BL shader reads
// (P, scale + id, rot, colour) are mapped to PX's state / look / rest textures of point pid = the sorted POP's instance
// attribute 0 (px_sortkey.glsl -> TOP to POP -> Sort POP). Its hooks add: S3 stretch / thin on the covariance
// (t0 -> M t0, M = th (I - a a^T) + (1 + st) a a^T), S6 depth of field (footprint + (coc/2)^2, energy kept, bokeh disc
// + rim in the pixel stage) and depth fog. S2: opacity = look alpha (dissolve fade etc.), scale x look size, a
// dissolving splat flattens along its normal (smallest axis) = peel; recolour = look rgb (SH0 only: PX loads splats
// with SH degree 0). S4: rotation = state texel 4 (rest quaternion x module rotations; lattice -> identity).
// uSp[5] rows: px_logic.splat_rows(). Pool ids (embers) and unused ids are culled (alpha 0): embers are sprites (S5).
// Phase C LOD (uSp[4] = on, start distance, share kept far away): past the start distance a splat is kept when its id
// hash < px_logic.lod_keep(view depth), and kept ones grow by 1 / sqrt(share) (covered area kept). Off = no change.
uniform vec4 uSp[5];
uniform sampler2D sState;
uniform sampler2D sLook;
uniform sampler2D sRest;

#define SPLAT_VERTEX_EXTRA float bokeh;

#ifdef TD_VERTEX_SHADER
float pxsBokeh = 0.0;

int pxsPid(int idx) { return int(floor(TDInstanceCustomAttrib0(idx).x + 0.5)); }


ivec2 pxsG(int pid) { int side = max(int(uSp[0].x + 0.5), 1); return ivec2(pid % side, pid / side); }

vec4 pxsState(int pid, int k) { ivec2 g = pxsG(pid); return texelFetch(sState, ivec2(g.x * 5 + k, g.y), 0); }

vec4 pxsLook(int pid, int k) { ivec2 g = pxsG(pid); return texelFetch(sLook, ivec2(g.x * 3 + k, g.y), 0); }

vec4 pxsRest(int pid, int k) { ivec2 g = pxsG(pid); return texelFetch(sRest, ivec2(g.x * 4 + k, g.y), 0); }

int pxsLodPid = -2;                                                // LOD, computed once per vertex (A0..A3 share it)
bool pxsLodCut = false;
float pxsLodScale = 1.0;

void pxsLod(int pid)
{
	if (pid == pxsLodPid) return;
	pxsLodPid = pid;
	pxsLodCut = false;
	pxsLodScale = 1.0;
	if (uSp[4].x < 0.5) return;
	vec4 cp = uTDMats[TDCameraIndex()].worldCam * vec4(pxsState(pid, 0).xyz, 1.0);
	float d0 = max(uSp[4].y, 1e-3);
	float k = mix(1.0, clamp(uSp[4].z, 0.01, 1.0), clamp((-cp.z - d0) / d0, 0.0, 1.0));
	if (k >= 1.0) return;
	uint h = uint(pid) * 2654435761u + 40503u;
	h = ((h >> 16u) ^ h) * 73244475u;
	if (float((h >> 8u) & 0xFFFFFFu) * (1.0 / 16777216.0) >= k) pxsLodCut = true;
	else pxsLodScale = inversesqrt(k);
}

bool pxsOk(int pid)
{
	if (pid < 0 || pid >= int(uSp[0].z + 0.5)) return false;
	pxsLod(pid);
	return !pxsLodCut;
}

vec4 pxsA0(int idx)
{
	int pid = pxsPid(idx);
	return pxsOk(pid) ? vec4(pxsState(pid, 0).xyz, 1.0) : vec4(0.0);
}

vec4 pxsA1(int idx)
{
	int pid = pxsPid(idx);
	if (!pxsOk(pid)) return vec4(0.0);
	vec3 s = pxsRest(pid, 2).xyz;
	if (s.x + s.y + s.z <= 0.0) s = vec3(uSp[2].w * 0.5);          // plain points: sigma = Look Size / 2
	else s *= uSp[3].w;                                            // file splats follow the scene scale (Ascale)
	vec4 L1 = pxsLook(pid, 1);
	s *= max(L1.x, 0.0);                                           // size multiplier (dissolve shrink, prox_scale)
	float dd = clamp(pxsState(pid, 3).w, 0.0, 1.0);
	if (dd > 0.0) {                                                // peel: flatten along the normal (smallest axis)
		if (s.x <= s.y && s.x <= s.z) s.x *= 1.0 - 0.9 * dd;
		else if (s.y <= s.z) s.y *= 1.0 - 0.9 * dd;
		else s.z *= 1.0 - 0.9 * dd;
	}
	s = mix(s, vec3(L1.w * 0.7), clamp(L1.z, 0.0, 1.0));           // lattice: isotropic cell blob
	return vec4(s * pxsLodScale, float(pid));                      // LOD: kept far splats grow (phase C)
}

vec4 pxsA2(int idx)
{
	int pid = pxsPid(idx);
	return pxsOk(pid) ? pxsState(pid, 4) : vec4(1.0, 0.0, 0.0, 0.0);
}

vec4 pxsA3(int idx)
{
	int pid = pxsPid(idx);
	return pxsOk(pid) ? pxsLook(pid, 0) : vec4(0.0);
}

// S3: stretch along the look's axis (or the velocity), thin across it, on the 3D covariance.
void pxsStretch(inout vec3 t0, inout vec3 t1, int idx)
{
	int pid = pxsPid(idx);
	if (!pxsOk(pid)) return;
	vec4 L1 = pxsLook(pid, 1);
	vec4 L2 = pxsLook(pid, 2);
	vec3 a = L2.xyz;
	if (dot(a, a) < 1e-8) { vec3 v = pxsState(pid, 2).xyz; a = length(v) > 1e-4 ? v : vec3(0.0); }
	float st = max(L1.y, -0.95);
	float th = 1.0 - 0.75 * clamp(L2.w, 0.0, 1.0);
	if (dot(a, a) < 1e-8) { t0 *= th; t1 *= th; return; }
	a = normalize(a);
	t0 = th * t0 + (1.0 + st - th) * a * dot(a, t0);
	t1 = th * t1 + (1.0 + st - th) * a * dot(a, t1);
}

// S6: depth of field on the 2D footprint (sigma = coc / 2 px, energy kept, min energy), + depth fog.
void pxsDof(inout float a, inout float b, inout float c, inout float alpha, float z)
{
	alpha *= exp(-uSp[2].z * z);
	float coc = min(uSp[1].y * abs(z - uSp[1].x) / max(z, 1e-4), uSp[1].z);
	pxsBokeh = 0.0;
	if (coc <= 0.0) return;
	float s2 = 0.25 * coc * coc;
	float d0 = max(a * c - b * b, 1e-12);
	a += s2;
	c += s2;
	float d1 = max(a * c - b * b, 1e-12);
	alpha *= clamp(sqrt(d0 / d1), uSp[1].w, 1.0);
	pxsBokeh = uSp[1].z > 0.0 ? clamp(coc / uSp[1].z, 0.0, 1.0) : 0.0;
}

#define SPLAT_HOOK_T(t0, t1, idx) pxsStretch(t0, t1, idx)
// Footprint cap (Splatmaxpx, uSp[3].z; 0 off): splats have no Maxpx like sprites, so a few splats right at the camera
// filled the frame as white fog (b4 lane, 27 Oct). Larger 2D sigma > cap -> covariance x k, alpha x k (energy kept).
void pxsClamp(inout float a, inout float b, inout float c, inout float alpha)
{
	float mx = uSp[3].z;
	if (mx <= 0.0) return;
	float mid = 0.5 * (a + c);
	float l1 = mid + sqrt(max(mid * mid - (a * c - b * b), 0.0));
	float m2 = mx * mx;
	if (l1 <= m2) return;
	float k = m2 / l1;
	a *= k;
	b *= k;
	c *= k;
	alpha *= k;
}

#define SPLAT_HOOK_COV(a, b, c, alpha, z, idx) pxsDof(a, b, c, alpha, z); pxsClamp(a, b, c, alpha)
#define SPLAT_HOOK_OUT(idx) oV.bokeh = pxsBokeh; oV.color.rgb *= 1.0 + uSp[2].y * pxsBokeh * smoothstep(1.0, 4.0, dot(oV.color.rgb, vec3(0.2126, 0.7152, 0.0722)))

#define TDInstanceCustomAttrib0(i) pxsA0(i)
#define TDInstanceCustomAttrib1(i) pxsA1(i)
#define TDInstanceCustomAttrib2(i) pxsA2(i)
#define TDInstanceCustomAttrib3(i) pxsA3(i)
#define TDInstanceCustomAttrib4(i) vec4(0.0)
#define TDInstanceCustomAttrib5(i) vec4(0.0)
#define TDInstanceCustomAttrib6(i) vec4(0.0)
#endif

#ifdef TD_PIXEL_SHADER
// S6 bokeh: defocused splats become a flat disc (~2.2 sigma, 0.41 x the peak keeps the energy) with a brighter rim.
float pxsPix(float power, float a, float bk, float ca)
{
	if (bk <= 0.0) return a;
	float r2 = -2.0 * power;
	float disc = 1.0 - smoothstep(4.0, 6.25, r2);
	float rim = 0.55 + 0.45 * smoothstep(1.0, 4.5, r2) * (1.0 + uSp[2].x);
	return mix(a, min(0.99, ca * disc * rim * 0.41 / 0.55), bk);
}
#define SPLAT_HOOK_PIX(power, a) a = pxsPix(power, a, iV.bokeh, iV.color.a)
#endif
