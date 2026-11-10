// GEN_clone render, GLSL MAT pixel shader: clone colour x source look. Card source: the TOP (sTex), or with a time
// offset the frame `toff` cooks ago from the Texture 3D ring (sRing; slice order = uRing.z, LIVE CHECK C9). Shapes:
// flat or headlight Lambert (own lighting, no TD lights). Output premultiplied (TD / Resolume).
uniform sampler2D sTex;
uniform sampler3D sRing;
uniform vec4 uL;     // shading (0 flat 1 lambert), card (1 = textured card), ambient, alpha cut (discard below)
uniform vec4 uRing;  // ring on (0/1), depth D, slice order (0 newest last, 1 newest first), 0
uniform vec4 uCam;   // camera world position xyz, 0
in Vert { vec3 wpos; vec3 wnorm; vec2 tuv; vec4 col; float toff; } iVert;
layout(location = 0) out vec4 fragColor;

void main()
{
	TDCheckDiscard();
	vec4 c = iVert.col;
	if (uL.y > 0.5) {
		vec4 t;
		if (uRing.x > 0.5) {
			float D = max(uRing.y, 1.0);
			float k = clamp(floor(iVert.toff + 0.5), 0.0, D - 1.0);
			float slice = uRing.z > 0.5 ? k : D - 1.0 - k;
			t = texture(sRing, vec3(iVert.tuv, (slice + 0.5) / D));
		} else {
			t = texture(sTex, iVert.tuv);
		}
		vec3 ts = t.a > 1e-5 ? t.rgb / t.a : vec3(0.0);   // TD TOPs are premultiplied -> straight
		c = vec4(c.rgb * ts, c.a * t.a);
	}
	if (uL.x > 0.5) {
		vec3 n = normalize(iVert.wnorm);
		vec3 v = normalize(uCam.xyz - iVert.wpos);
		float d = abs(dot(n, v));
		c.rgb *= uL.z + (1.0 - uL.z) * d;
	}
	if (c.a < uL.w) discard;
	fragColor = TDOutputSwizzle(vec4(c.rgb * c.a, c.a));
}
