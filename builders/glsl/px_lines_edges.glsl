// px_lines_edges.glsl - PX lines pass, EDGE / OUTLINE LINES (G2): ONE compute pass (T-46/T-47) at Edres (half by
// default), cooks only while Edges is on. Mirrors px_lines_logic.ref_edges. Text = glsl_header() + px_palette.glsl +
// px_lines_common.glsl + this. Inputs (linear filtering): 0 = scene (rgba), 1 = scene depth (LINEAR eye depth in R, 0 =
// nothing; read only when Usedepth), 2 unused.
// Per output pixel: 3x3 Sobel at +-Edwidth/2 full-res px of luma, alpha and depth (depth relative to the centre depth,
// so far edges are not over-weighted); g = max(Edluma |grad luma|, Edalpha |grad a|, Eddepth |grad z| / z); strength
// e = smoothstep(Edthr, Edthr + Edsoft, g) x reveal / cut along the screen wipe direction x the world mask (only with
// depth: the pixel's world position is rebuilt from the inverse view-proj rows IV0..IV3 and the depth).
// Out rgba16float: rgb = colour x Edgain x e (HDR), a = e.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uEdgeCs;      // W1-B colour source of the edge lines (mode, pos, spread, keep)

float plLum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	ivec2 osz = ivec2(uTDOutputInfo.res.zw);
	if (g.x >= osz.x || g.y >= osz.y) return;
	vec2 uv = (vec2(g) + 0.5) / vec2(osz);
	vec2 o = 0.5 * uL[R_ED1].y / uL[R_G0].xy;
	bool dep = uL[R_ST3].w > 0.5;
	float L[9], A[9], Z[9];
	vec4 c0 = vec4(0.0);
	for (int j = 0; j < 3; j++)
		for (int i = 0; i < 3; i++)
		{
			vec2 q = uv + vec2(float(i - 1), float(j - 1)) * o;
			vec4 c = texture(sTD2DInputs[0], q);
			L[j * 3 + i] = plLum(c.rgb);
			A[j * 3 + i] = c.a;
			Z[j * 3 + i] = dep ? texture(sTD2DInputs[1], q).r : 0.0;
			if (i == 1 && j == 1) c0 = c;
		}
	// Sobel / 4: a 0 -> 1 step between taps gives |grad| = 1
	float gl = length(vec2(L[2] + 2.0 * L[5] + L[8] - L[0] - 2.0 * L[3] - L[6],
	                       L[6] + 2.0 * L[7] + L[8] - L[0] - 2.0 * L[1] - L[2])) * 0.25;
	float ga = length(vec2(A[2] + 2.0 * A[5] + A[8] - A[0] - 2.0 * A[3] - A[6],
	                       A[6] + 2.0 * A[7] + A[8] - A[0] - 2.0 * A[1] - A[2])) * 0.25;
	float gz = length(vec2(Z[2] + 2.0 * Z[5] + Z[8] - Z[0] - 2.0 * Z[3] - Z[6],
	                       Z[6] + 2.0 * Z[7] + Z[8] - Z[0] - 2.0 * Z[1] - Z[2])) * 0.25 / max(Z[4], 1e-3);
	float gm = max(uL[R_ED0].x * gl, max(uL[R_ED0].y * ga, dep ? uL[R_ED0].z * gz : 0.0));
	float e = smoothstep(uL[R_ED0].w, uL[R_ED0].w + max(uL[R_ED1].x, 1e-5), gm);
	vec2 wd = vec2(cos(uL[R_ED2].y), sin(uL[R_ED2].y));
	float wu = dot(uv - 0.5, wd) / (abs(wd.x) * 0.5 + abs(wd.y) * 0.5) * 0.5 + 0.5;   // 0..1 across the frame
	e *= plReveal(wu);
	float zt = 0.0;
	if (dep && Z[4] > 0.0)
	{
		vec4 w = vec4(dot(uL[R_IV0], vec4(uv * 2.0 - 1.0, 1.0, 1.0)), dot(uL[R_IV1], vec4(uv * 2.0 - 1.0, 1.0, 1.0)),
		              dot(uL[R_IV2], vec4(uv * 2.0 - 1.0, 1.0, 1.0)), dot(uL[R_IV3], vec4(uv * 2.0 - 1.0, 1.0, 1.0)));
		vec3 dir = normalize(w.xyz / w.w - uL[R_G2].xyz);
		vec3 Pw = uL[R_G2].xyz + dir * (Z[4] / max(dot(dir, uL[R_G3].xyz), 1e-4));
		e *= plMask(Pw);
		zt = clamp((Z[4] - uL[R_CL2].x) / max(uL[R_CL2].y - uL[R_CL2].x, 1e-6), 0.0, 1.0);
	}
	else if (int(uL[R_MK0].x + 0.5) != 0 && dep) e = 0.0;
	int at = int(uL[R_ED1].z + 0.5);
	float t = at == 0 ? L[4] : (at == 1 ? zt : (at == 2 ? wu : uv.y));
	vec3 src = c0.rgb / max(max(c0.r, max(c0.g, c0.b)), 1e-3);         // scene colour at full brightness
	vec3 col = pxColSrc(uEdgeCs, uL[R_CL1].xyz, src, t);
	TDImageStoreOutput(0, ivec3(g, 0), vec4(col * uL[R_ED1].w * uL[R_G1].w * e, e));
}
