// BL_cloud_morph post: ONE compute pass (T-47), copied by builders/pointcloud.py into `post_compute`.
// in0 = point render (premultiplied, rgba16float; additive mode can exceed 1). Gain, optional Reinhard tone map,
// background colour under, alpha on/off, premultiplied or straight out. Mirrors pointcloud_logic.post_pixel().
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uPost;    // gain, tone map (0/1), output alpha (0/1), premultiplied out (0/1)
uniform vec4 uBg;      // background rgb + alpha (straight)
void main()
{
	ivec2 px = ivec2(gl_GlobalInvocationID.xy);
	ivec2 res = ivec2(uTDOutputInfo.res.zw);
	if (px.x >= res.x || px.y >= res.y) return;
	ivec2 isz = textureSize(sTD2DInputs[0], 0);
	vec4 c = texelFetch(sTD2DInputs[0], clamp(px * isz / max(res, ivec2(1)), ivec2(0), isz - ivec2(1)), 0);
	c.rgb *= uPost.x;
	if (uPost.y > 0.5) c.rgb = c.rgb / (1.0 + c.rgb);
	c.a = clamp(c.a, 0.0, 1.0);
	vec4 bg = vec4(uBg.rgb * uBg.a, uBg.a);
	c = c + bg * (1.0 - c.a);
	if (uPost.z < 0.5) c.a = 1.0;
	else if (uPost.w < 0.5) c.rgb = c.rgb / max(c.a, 1e-6);
	TDImageStoreOutput(0, ivec3(px, 0), TDOutputSwizzle(c));
}
