// PX_pointfx effector glow (A5): prepended to builders/splat_render.glsl (the reused BL splat MAT) so a glowing
// effector is drawn into out1 as an additive 3D Gaussian of its own shape and orientation (a plane = a thin slab /
// beam, a sphere = a ball, + fading copies along its trail). No POP: instance i reads rows i*4.. of uGl
// (px_logic.glow_rows: P, sigma xyz, quaternion wxyz, rgb x intensity + alpha). Manual instance count = glows.
uniform vec4 uGl[288];

#ifdef TD_VERTEX_SHADER
vec4 pxgRow(int idx, int k)
{
	int r = idx * 4 + k;
	return (r >= 0 && r < 288) ? uGl[r] : vec4(0.0);
}
#define TDInstanceCustomAttrib0(i) pxgRow(i, 0)
#define TDInstanceCustomAttrib1(i) vec4(pxgRow(i, 1).xyz, float(i))
#define TDInstanceCustomAttrib2(i) pxgRow(i, 2)
#define TDInstanceCustomAttrib3(i) pxgRow(i, 3)
#define TDInstanceCustomAttrib4(i) vec4(0.0)
#define TDInstanceCustomAttrib5(i) vec4(0.0)
#define TDInstanceCustomAttrib6(i) vec4(0.0)
#endif
