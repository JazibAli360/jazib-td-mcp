// BL_cloud_morph pixel shader (GLSL MAT, one pass). Copied by builders/pointcloud.py into the DAT `pc_pixel`.
// Shapes: 0 disc, 1 soft (gaussian), 2 square, 3 ring, 4 streak. Blend (uCol.w): 0 add, 1 over -> premultiplied out;
// 2 opaque -> alpha-tested (>= 0.5), depth tested by the MAT. Mirrors pointcloud_logic.shape_alpha().
uniform vec4 uDof;     // .w = shape
uniform vec4 uCol;     // .w = blend

in Vertex {
	vec4 color;
	vec2 uv;
} iV;

out vec4 fragColor;

void main()
{
	TDCheckDiscard();
	vec2 q = iV.uv;
	float r = length(q);
	float w = max(fwidth(r), 1e-3);
	int shape = int(uDof.w + 0.5);
	float a;
	if (shape == 1)      a = exp(-4.0 * r * r) * (1.0 - smoothstep(1.0 - w, 1.0, r));
	else if (shape == 2) a = 1.0;
	else if (shape == 3) a = smoothstep(0.6 - w, 0.6, r) * (1.0 - smoothstep(1.0 - w, 1.0, r));
	else if (shape == 4) a = (1.0 - smoothstep(1.0 - max(fwidth(q.y), 1e-3), 1.0, abs(q.y))) * mix(0.15, 1.0, q.x * 0.5 + 0.5);
	else                 a = 1.0 - smoothstep(1.0 - w, 1.0, r);
	a *= iV.color.a;
	if (uCol.w > 1.5) {
		if (a < 0.5) discard;
		fragColor = TDOutputSwizzle(vec4(iV.color.rgb, 1.0));
		return;
	}
	if (a < 1.0 / 255.0) discard;
	fragColor = TDOutputSwizzle(vec4(iV.color.rgb * a, a));
}
