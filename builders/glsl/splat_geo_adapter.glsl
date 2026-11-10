// splat_geo_adapter (W1-E, docs/builds/px_geo.md): geometry in the splat scene. Put in front of
// builders/splat_render.glsl by splat_render_logic.geo_patch() ONLY while the Geo page's Geoon is set (off = the
// block is removed and BL compiles to its original text). Goes AFTER the shared effectors block (effectors.py attach)
// so the W1-A light functions are declared first.
// Occlusion itself is not shader work: geometry renders first (geo_render, opaque, depth write) and the splats are
// drawn on top by a Render Pass TOP with depth test ON / depth write OFF (splatmat Depthtest = Geoon).
// uGeo: x = relight (0 = baked colour, 1 = baked x (ambient + lights)), y = ambient, z = light model (W1-A pxeLight
//       mode.x: 0 half-lambert, 1 lambert, 2 wrap, 3 no-normal glow by distance), w = depth bias (world units toward
//       the camera; > 0 lets splats lying on a coincident surface win the depth test).
uniform vec4 uGeo;

#ifdef TD_VERTEX_SHADER
// depth of the splat centre moved `bias` toward the camera along its view ray (NDC z, then back to clip space)
float sgeoBiasClipZ(mat4 Pm, vec4 vc, float z, float w)
{
	vec4 cb = Pm * vec4(vc.xyz * max(1.0 - uGeo.w / max(z, 1e-4), 1e-3), 1.0);
	return cb.z / cb.w * w;
}
#define SPLAT_HOOK_CLIP(clip, vc, z) if (uGeo.w != 0.0) clip.z = sgeoBiasClipZ(Pm, vc, z, clip.w);

#if defined(PXE_HOOK) && defined(SGEO_LIGHTS)
// Relight the splat colour by the light effectors (kind light, W1-A: /project1/effectors, packed header v2, functions in
// builders/glsl/px_common.glsl). SGEO_LIGHTS is defined by splat_render_logic.geo_patch only when the effectors block
// in front of this one has those functions. v1: every enabled light (sel 'all'); no specular.
// Numpy twin: splat_render_logic.geo_relight_ref (with effectors_logic's light refs per light).
vec3 sgeoLight(vec3 rgb, vec3 p, vec4 q, vec3 s)
{
	if (uGeo.x <= 0.0) return rgb;
	vec3 v = normalize(uTDMats[TDCameraIndex()].camInverse[3].xyz - p);
	vec3 n = pxeSplatNormal(q, s, v);                 // smallest-scale axis, facing the eye
	vec3 L = vec3(uGeo.y) + pxeLights(p, n, v, vec4(0.0, 1.0, 1.0, 0.0), vec4(0.0), vec4(uGeo.z, 0.5, 0.0, 0.5));
	return mix(rgb, rgb * L, uGeo.x);
}
#define SPLAT_HOOK_LIGHT(rgb, p, q, s, idx) rgb = sgeoLight(rgb, p, q, s);
#endif
#endif
