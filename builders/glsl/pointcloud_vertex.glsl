// BL_cloud_morph vertex shader (GLSL MAT, one pass; T-46 does not apply). Clean-room, spec
// docs/research/BL_gaussian_splats_pointclouds.md 7.2. Copied by builders/pointcloud.py into the DAT `pc_vertex`.
// One quad (-1..1, rectangle SOP) per instance = one point. Mirrors builders/pointcloud_logic.py:
// ease(), point_morph(), unproject_uv()/depth_to_z(), radius_px(); change both together.
// Instance custom attribs (CHOP channels or POP attributes, see pointcloud_logic.SLOTS):
//   0 = A xyz + stagger delay, 1 = B xyz + seed, 2 = A rgba, 3 = B rgba, 4 = uv A (xy) + uv B (zw) for depth-TOP sides.
uniform vec4 uMorph;   // raw morph 0..1, stagger, arc, time s
uniform vec4 uEase;    // ease kind (0 lin 1 in 2 out 3 inout 4 sine), noise amp, noise freq, noise speed
uniform vec4 uSize;    // size px, size by depth 0..1, reference distance, opacity
uniform vec4 uDof;     // dof px per unit, focus distance, streak (fraction of path), shape
uniform vec4 uCol;     // colour mix, tint amount, brightness, blend (0 add 1 over 2 opaque)
uniform vec4 uTint;    // tint rgb, 0
uniform vec4 uRes;     // render w, h, 0, 0
uniform vec4 uTexA;    // A is depth TOP (0/1), fov deg (vertical), znear, zfar
uniform vec4 uTexB;
uniform vec4 uFitA;    // fit centre xyz, scale (= Scale / radius) for a depth-TOP side
uniform vec4 uOffA;    // offset xyz, image aspect w/h
uniform vec4 uFitB;
uniform vec4 uOffB;
uniform vec4 uKind;    // depth kind A, B (0 inverse, 1 depth), has colour TOP A, B
uniform vec4 uLoHi;    // depth lo A, hi A, lo B, hi B (raw TOP values mapped to 0..1)
uniform sampler2D sDepthA;
uniform sampler2D sColA;
uniform sampler2D sDepthB;
uniform sampler2D sColB;

out Vertex {
	vec4 color;    // straight rgb + alpha
	vec2 uv;       // quad corner -1..1 (x = along the streak)
} oV;

float easeK(float x, float k)
{
	x = clamp(x, 0.0, 1.0);
	if (k < 0.5) return x;
	if (k < 1.5) return x * x;
	if (k < 2.5) return 1.0 - (1.0 - x) * (1.0 - x);
	if (k < 3.5) return x * x * (3.0 - 2.0 * x);
	return 0.5 - 0.5 * cos(3.14159265 * x);
}

vec3 texSide(sampler2D sd, sampler2D sc, vec2 uv, vec4 tex, float kind, float lo, float hi, vec4 fit, vec4 off,
             float hasCol, inout vec3 rgb)
{
	vec2 u = clamp(uv, vec2(0.0), vec2(1.0));                     // T-35: no out-of-range fetches
	float d = textureLod(sd, u, 0.0).r;
	float dn = clamp((d - lo) / max(hi - lo, 1e-9), 0.0, 1.0);
	float zn = max(tex.z, 1e-6);
	float z = (kind > 0.5) ? (tex.z + dn * (tex.w - tex.z)) : (tex.w / (1.0 + dn * (tex.w / zn - 1.0)));
	float t = tan(radians(tex.y) * 0.5);
	vec3 p = vec3((u.x - 0.5) * 2.0 * t * off.w * z, (u.y - 0.5) * 2.0 * t * z, -z);
	rgb = (hasCol > 0.5) ? textureLod(sc, u, 0.0).rgb : vec3(dn);
	return (p - fit.xyz) * fit.w + off.xyz;
}

void cull()
{
	gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
	oV.color = vec4(0.0);
	oV.uv = vec2(0.0);
}

void main()
{
	int id = TDInstanceID();
	vec4 a = TDInstanceCustomAttrib0(id);
	vec4 b = TDInstanceCustomAttrib1(id);
	vec4 ca = TDInstanceCustomAttrib2(id);
	vec4 cb = TDInstanceCustomAttrib3(id);
	vec4 uvs = TDInstanceCustomAttrib4(id);

	vec3 pa = a.xyz;
	vec3 pb = b.xyz;
	if (uTexA.x > 0.5) pa = texSide(sDepthA, sColA, uvs.xy, uTexA, uKind.x, uLoHi.x, uLoHi.y, uFitA, uOffA, uKind.z, ca.rgb);
	if (uTexB.x > 0.5) pb = texSide(sDepthB, sColB, uvs.zw, uTexB, uKind.y, uLoHi.z, uLoHi.w, uFitB, uOffB, uKind.w, cb.rgb);

	float s = max(uMorph.y, 0.0);
	float e = easeK(uMorph.x * (1.0 + s) - a.w * s, uEase.x);
	float bump = sin(3.14159265 * e);

	vec3 p = mix(pa, pb, e);
	if (uMorph.z != 0.0 || uEase.y != 0.0) {
		vec3 q = pa * uEase.z + vec3(b.w * 7.31);
		float ph = uMorph.w * uEase.w;
		vec3 nz = vec3(TDSimplexNoise(vec4(q, ph)), TDSimplexNoise(vec4(q + 17.13, ph)),
		               TDSimplexNoise(vec4(q + 41.71, ph)));
		p += nz * (uMorph.z * bump + uEase.y);
	}

	vec4 col = mix(ca, cb, e * uCol.x);
	col.rgb = mix(col.rgb, uTint.rgb, uCol.y) * uCol.z;
	col.a *= uSize.w;
#ifdef PXE_HOOK
	PXEFx efx = pxePointFx(p, float(id));   // shared effectors (builders/effectors.py attach)
	p += efx.off;
	col.a *= efx.alpha;
#endif

	int ci = TDCameraIndex();
	vec4 vc = uTDMats[ci].cam * vec4(p, 1.0);
	float z = -vc.z;
	if (z <= 1e-3 || col.a <= 0.0) { cull(); return; }
	vec4 clip = (uTDMats[ci].proj * vc);
	vec2 ndc = clip.xy / clip.w;

	float r0 = uSize.x * ((1.0 - uSize.y) + uSize.y * uSize.z / max(z, 1e-4));
#ifdef PXE_HOOK
	r0 *= efx.scale;
#endif
	float r = (uDof.x > 0.0) ? r0 + abs(z - uDof.y) * uDof.x : r0;
	r = max(r, 0.5);
	col.a *= clamp((r0 * r0) / max(r * r, 1e-6), 0.0, 1.0);    // DOF: bigger disc, same energy

	vec2 corner = TDPos().xy;
	vec2 off = corner * r;
	vec2 centre = ndc;
	if (uDof.w > 3.5 && uDof.z > 0.0) {                            // streak along the projected A -> B path
		vec4 ka = (uTDMats[ci].proj * (uTDMats[ci].cam * vec4(pa, 1.0)));
		vec4 kb = (uTDMats[ci].proj * (uTDMats[ci].cam * vec4(pb, 1.0)));
		vec2 path = (kb.xy / max(kb.w, 1e-4) - ka.xy / max(ka.w, 1e-4)) * 0.5 * uRes.xy;
		float L = uDof.z * bump * length(path);
		if (L > 0.5) {
			vec2 dir = normalize(path);
			vec2 perp = vec2(-dir.y, dir.x);
			off = corner.x * (r + 0.5 * L) * dir + corner.y * r * perp;
			centre -= dir * (0.5 * L) * 2.0 / uRes.xy;
		}
	}
	gl_Position = vec4(centre + off * 2.0 / uRes.xy, clip.z / clip.w, 1.0);
	oV.color = col;
	oV.uv = corner;
}
