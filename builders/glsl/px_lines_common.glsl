// px_lines_common.glsl - PX lines pass (lane W1-C, 27 Oct 2026; doc docs/builds/px_lines.md). Shared by every stage
// (seg / hist / edges / comp computes and the line MAT's vertex + pixel). Prepended after the #define header from
// builders/px_lines_logic.py glsl_header() (row indices R_*, PL_NROWS, SEG_W) and, in the colouring stages, after
// builders/glsl/px_palette.glsl (W1-B convention: uPal[16], uPalCtl, pxColSrc). Mirrors: px_lines_logic ref_*.
// uL[] = one vec4 per row (px_lines_logic.rows, a Script CHOP uniform array). uT = (time s, frame, dt s, reset n).
#ifndef PX_LINES_COMMON
#define PX_LINES_COMMON
uniform vec4 uL[PL_NROWS];
uniform vec4 uT;
const float PL_TAU = 6.28318530718;
const float PL_PI = 3.14159265359;

uint plPcg(uint v)
{
	uint s = v * 747796405u + 2891336453u;
	uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
	return (w >> 22u) ^ w;
}
// 0..1, same as px_lines_logic.h3 (24 bits)
float plH3(uint a, uint b, uint c) { return float(plPcg(a ^ plPcg(b ^ plPcg(c))) >> 8) / 16777215.0; }
uint plU(float x) { return uint(int(floor(x + 0.5)) + 65536); }   // line ids may be negative (contour bands)

// World-space mask (Mask page): 0 off, 1 sphere (1 inside R, fades out over soft), 2 front (visible behind the plane
// through the centre with normal axis: d = dot(p - c, axis) < 0, fades over soft). Invert flips it.
float plMask(vec3 p)
{
	int m = int(uL[R_MK0].x + 0.5);
	if (m == 0) return 1.0;
	float soft = max(uL[R_MK0].z, 1e-5);
	float w;
	if (m == 1) w = 1.0 - smoothstep(uL[R_MK0].y, uL[R_MK0].y + soft, length(p - uL[R_MK1].xyz));
	else w = 1.0 - smoothstep(0.0, soft, dot(p - uL[R_MK1].xyz, uL[R_MK2].xyz));
	return uL[R_MK0].w > 0.5 ? 1.0 - w : w;
}

// Draw-on / cut on the line coordinate u (0..1): visible where cut < u < reveal, soft edges of width rs. reveal 1 and
// cut 0 show everything (u in 0..1 included); reveal 0 or cut 1 hide everything.
float plReveal(float u)
{
	float rs = max(uL[R_ST2].z, 1e-4);
	float R = uL[R_ST2].x * (1.0 + rs);
	float C = uL[R_ST2].y * (1.0 + rs) - rs;
	return (1.0 - smoothstep(R - rs, R, u)) * smoothstep(C, C + rs, u);
}
#endif
