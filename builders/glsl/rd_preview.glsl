// rd pass fx_preview (Resw/2 x Resh/2): fx_look + gizmos for the injector rows (effector Nulls cyan, in5 points
// yellow, mouse white; bursts not drawn): a ring at the radius + a centre dot. Preview only, never in out1.
// in0 = fx_look
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uSim;    // simw, simh, aspect, edge
uniform vec4 uInj;    // inject, maskthresh, morphdecay, nrows
uniform samplerBuffer uRows;

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec2 uv = (vec2(T) + 0.5) / vec2(sz);
	vec4 col = texture(sTD2DInputs[0], uv);
	col.rgb = col.rgb * col.a + vec3(0.06) * (1.0 - col.a);
	col.a = 1.0;
	float asp = float(sz.x) / float(sz.y);
	float px = 1.0 / float(sz.y);
	int n = min(int(uInj.w + 0.5), NROWS);
	for (int k = 0; k < n; k++) {
		vec4 r0 = texelFetch(uRows, k * ROW_TEXELS);
		vec4 r1 = texelFetch(uRows, k * ROW_TEXELS + 1);
		int kind = int(r1.z + 0.5);
		if (r1.w < 0.5 || kind == 3) continue;
		vec3 gc = kind == 0 ? vec3(0.1, 1.0, 1.0) : (kind == 1 ? vec3(1.0, 0.9, 0.1) : vec3(1.0));
		if (r0.w < 0.0) gc = vec3(1.0, 0.3, 0.2);
		float d = length((uv - r0.xy) * vec2(asp, 1.0));
		float ring = 1.0 - smoothstep(px * 1.0, px * 2.5, abs(d - r0.z));
		float dot_ = 1.0 - smoothstep(px * 2.0, px * 3.5, d);
		col.rgb = mix(col.rgb, gc, max(ring, dot_));
	}
	TDImageStoreOutput(0, ivec3(T, 0), col);
}
