// PX_pointfx sort keys (S1): ONE compute pass, side x side rgba32float, texel id = (P.xyz this frame, id). Ids past the
// splat draw end (pool embers, unused) get id -1 and are culled by the splat adapter. A TOP to POP turns this into one
// POP point per texel (P + custom attribute pid), the Sort POP orders them by the sort camera (the BL_splat_render
// route), and the splat Geometry COMP instances the sorted points: instance custom attribute 0 = pid.
// Input 0 = state (update output, 5 texels per point). uSp[0] = (side, count, scene + actor end, sort off).
// Phase C auto quality: uKs = (point fraction f, key texture side). f < 1: the texture is smaller (ceil(end x f) keys)
// and key texel k holds id floor(k / f), so the Sort POP and the instancing really get fewer points. f >= 1 (or 0:
// no uniform) = the full map above, unchanged.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSp[5];
uniform vec4 uKs;

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	int side = max(int(uSp[0].x + 0.5), 1);
	float kf = (uKs.x > 0.0 && uKs.x < 1.0) ? uKs.x : 1.0;
	int ks = kf < 1.0 ? max(int(uKs.y + 0.5), 1) : side;
	if (g.x >= ks || g.y >= ks) return;
	if (g.x >= int(uTDOutputInfo.res.z) || g.y >= int(uTDOutputInfo.res.w)) return;
	int k = g.y * ks + g.x;
	int id = kf < 1.0 ? int(floor(float(k) / kf)) : k;
	int end = int(uSp[0].z + 0.5);
	ivec2 t = ivec2((id % side) * 5, id / side);
	ivec2 sz = textureSize(sTD2DInputs[0], 0);
	vec4 s0 = (t.x < sz.x && t.y < sz.y) ? texelFetch(sTD2DInputs[0], t, 0) : vec4(0.0);
	bool ok = id < end && t.x < sz.x && t.y < sz.y;
	TDImageStoreOutput(0, ivec3(g, 0), ok ? vec4(s0.xyz, float(id)) : vec4(0.0, 0.0, 1e6, -1.0));
}
