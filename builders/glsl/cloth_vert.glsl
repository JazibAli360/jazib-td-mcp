// BN_cloth render, GLSL MAT vertex shader: displaces a Grid SOP (Gridw x Gridh points, uv = rowcol) by the
// positions texture (sampler sPos = `state`, 2W x H, the left half = positions; nearest). Normals from 4 neighbour texels (double-sided in the pixel
// shader). LIVE CHECK: vertex texture fetch in a GLSL MAT on 31550/MoltenVK, Grid SOP uv[0] maps 0..1 onto points.
uniform sampler2D sPos;
uniform vec4 uGrid;    // W, H, 0, 0
out Vert { vec3 wpos; vec3 wnorm; vec2 tuv; } oVert;

void main()
{
	vec2 t = uv[0].st;
	ivec2 G = ivec2(uGrid.xy + 0.5);
	ivec2 c = clamp(ivec2(floor(t * vec2(G - 1) + 0.5)), ivec2(0), G - 1);
	vec3 p = texelFetch(sPos, c, 0).xyz;
	vec3 pe = texelFetch(sPos, ivec2(min(c.x + 1, G.x - 1), c.y), 0).xyz;
	vec3 pw = texelFetch(sPos, ivec2(max(c.x - 1, 0), c.y), 0).xyz;
	vec3 pn = texelFetch(sPos, ivec2(c.x, min(c.y + 1, G.y - 1)), 0).xyz;
	vec3 ps = texelFetch(sPos, ivec2(c.x, max(c.y - 1, 0)), 0).xyz;
	vec3 n = cross(pe - pw, pn - ps);
	n = length(n) > 1e-12 ? normalize(n) : vec3(0.0, 0.0, 1.0);
	vec4 worldSpacePos = TDDeform(p);
	gl_Position = TDWorldToProj(worldSpacePos);
#ifndef TD_PICKING_ACTIVE
	oVert.wpos = worldSpacePos.xyz;
	oVert.wnorm = normalize(TDDeformNorm(n));
	oVert.tuv = t;
#else
	TDWritePickingValues();
#endif
}
