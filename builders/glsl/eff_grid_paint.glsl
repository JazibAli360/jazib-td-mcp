// eff_grid_paint (compute GLSL TOP, /project1/effectors/grid; SA23 persistent painted mask volume; numpy twin
// effectors_grid_logic.paint_step_ref): input 0 = the previous paint (Feedback TOP), per voxel centre c:
// paint' = clamp(paint (1 - decay dt) + rate dt (wAdd - wErase), 0, 1), wAdd / wErase = pxeW of the paint / erase
// selections (any effector kind, the rows' own falloffs). Clear (uPaint.z) -> 0. Out (paint, wAdd, wErase, 1).
// Needs the effectors adapter prefix (px_common packed + eff_consumer) before this text.
layout(local_size_x = 8, local_size_y = 8) in;
uniform vec4 uGrid;      // origin xyz (min corner), cell size
uniform vec4 uGridN;     // N, tiles across, 0, 0
uniform vec4 uPaint;     // rate x dt, decay x dt, clear, 0
uniform vec4 uPaintSel;  // paint selection: tag mask, all, on, gain
uniform vec4 uPaintIds;
uniform vec4 uEraseSel;  // erase selection
uniform vec4 uEraseIds;

void main()
{
	ivec2 a = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (a.x >= sz.x || a.y >= sz.y) return;
	int N = int(uGridN.x + 0.5), tx = int(uGridN.y + 0.5);
	int z = (a.y / N) * tx + a.x / N;
	if (z >= N) { TDImageStoreOutput(0, ivec3(a, 0), vec4(0.0)); return; }
	vec3 c = uGrid.xyz + (vec3(a.x % N, a.y % N, z) + 0.5) * uGrid.w;
	float prev = 0.0;
#if defined(TD_NUM_2D_INPUTS) && TD_NUM_2D_INPUTS > 0
	prev = texelFetch(sTD2DInputs[0], a, 0).r;
#endif
	int b;
	vec4 mixv = vec4(0.0, 1.0, 0.0, 4.0), fall = vec4(0.0);
	float wa = pxeW(c, uPaintSel, uPaintIds, mixv, fall, b);
	float we = pxeW(c, uEraseSel, uEraseIds, mixv, fall, b);
	float p = uPaint.z > 0.5 ? 0.0 : clamp(prev * max(0.0, 1.0 - uPaint.y) + uPaint.x * (wa - we), 0.0, 1.0);
	TDImageStoreOutput(0, ivec3(a, 0), vec4(p, wa, we, 1.0));
}
