// px_lines_pixel.glsl - PX lines pass, GLSL MAT pixel shader. Exact distance (px) to the projected segment: core =
// anti-aliased Width px (width < 1 px fades instead of thinning), halo = Halogain x exp(-2 (d / Halo)^2) outside the
// core; round caps only where the segment owns them (bit 0 start, bit 1 end: polylines own only their start cap, so
// every joint is covered once). Then reveal / cut / dash on u, then occlusion: 1 depth = fade where the line is
// behind the scene depth (sDepth: LINEAR eye depth in R, 0 = nothing) by more than Occbias over Occsoft; 2 alpha = fade
// by the scene's alpha (lines go behind anything drawn). Premultiplied HDR out: blend add (one, one) or max.
// Mirrors px_lines_logic.ref_coverage. Text = glsl_header() + px_lines_common.glsl + this.
uniform sampler2D sDepth;
uniform sampler2D sScene;
in Vertex { vec4 color; vec2 pp; flat vec4 seg; flat vec4 ue; flat float hw; flat float caps; } iV;
layout(location = 0) out vec4 fragColor;

void main()
{
	TDCheckDiscard();
	vec2 sa = iV.seg.xy, d = iV.seg.zw - iV.seg.xy;
	float L2 = dot(d, d);
	float f = L2 > 1e-8 ? dot(iV.pp - sa, d) / L2 : 0.0;
	int caps = int(iV.caps + 0.5);
	if ((f < 0.0 && (caps & 1) == 0) || (f > 1.0 && (caps & 2) == 0)) discard;
	float fc = clamp(f, 0.0, 1.0);
	float dist = length(iV.pp - (sa + d * fc));
	float u = mix(iV.ue.x, iV.ue.y, fc), eye = mix(iV.ue.z, iV.ue.w, fc);
	float hw = iV.hw;
	float core = clamp(hw + 0.5 - dist, 0.0, 1.0) * min(2.0 * hw, 1.0);
	float hr = uL[R_ST0].y;
	float halo = hr > 0.0 ? uL[R_ST0].z * exp(-2.0 * pow(max(dist - hw, 0.0) / hr, 2.0)) : 0.0;
	float I = core + (1.0 - core) * halo;
	float w = plReveal(u);
	if (uL[R_ST1].x > 0.0)
	{
		float x = u * uL[R_ST1].x - uL[R_ST1].z * uT.x;
		float ph = fract(x);
		float aa = max(fwidth(x), 1e-4);
		w *= clamp((uL[R_ST1].y - ph) / aa + 0.5, 0.0, 1.0);
	}
	int om = int(uL[R_ST3].x + 0.5);
	vec2 uv = gl_FragCoord.xy / uL[R_G0].xy;
	if (om == 1 && uL[R_ST3].w > 0.5)
	{
		float sd = texture(sDepth, uv).r;
		if (sd > 0.0) w *= 1.0 - smoothstep(uL[R_ST3].y, uL[R_ST3].y + max(uL[R_ST3].z, 1e-5), eye - sd);
	}
	else if (om == 2) w *= 1.0 - clamp(texture(sScene, uv).a, 0.0, 1.0);
	float k = I * w * iV.color.a;
	if (k <= 0.0) discard;
	fragColor = TDOutputSwizzle(vec4(iV.color.rgb * k, min(k, 1.0)));
}
