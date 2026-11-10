// px_palette.glsl - the ONE shared palette convention (lane W1-B, 27 Oct 2026; doc docs/builds/palette_convention.md).
// Prepend this text to any GLSL TOP / MAT stage (compute, pixel, vertex) that needs a palette. Pure text include: no
// TOP input is used (PX's GLSL TOPs already use all 3 inputs, T-84 / T-88), the palette arrives as UNIFORMS:
//   uPal[16]  Arrays page, type vec4, uniformarray, from a 16-sample CHOP with channels r g b pos (in that order):
//             stop i = (rgb as in a TD RGB par, may be > 1 for HDR; position 0..1, ascending).
//   uPalCtl   Vectors page: x count (0..16, 0 = black), y shift (palette-t offset, wraps; drives write it),
//             z mode (0 gradient, 1 steps, 2 cycle), w interp (0 rgb, 1 oklab).
// Python side (fills both): builders/palette_map_logic.py pal_rows / pal_ctl / bind_glsl; pal_eval is the reference.
// Names are prefixed (pxPal*) because ph_look / rd_look already define their own palette(); a shader that wants the
// short names defines PX_PAL_SHORT_NAMES before this text and gets palette(t) / palette_step(i).
#ifndef PX_PALETTE_GLSL
#define PX_PALETTE_GLSL
#define PX_PAL_MAX 16

uniform vec4 uPal[PX_PAL_MAX];
uniform vec4 uPalCtl;

int pxPalCount() { return clamp(int(uPalCtl.x + 0.5), 0, PX_PAL_MAX); }

// OKLab (Bjorn Ottosson) with the sRGB transfer, same constants as palette_map_logic.srgb_to_oklab; no upper clamp
// so HDR stops survive, negatives clamp to 0.
float pxPalLin(float c) { c = max(c, 0.0); return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4); }
float pxPalEnc(float c) { c = max(c, 0.0); return c <= 0.0031308 ? 12.92 * c : 1.055 * pow(c, 1.0 / 2.4) - 0.055; }
float pxPalCbrt(float x) { return sign(x) * pow(abs(x), 1.0 / 3.0); }

vec3 pxPalToLab(vec3 c)
{
	float r = pxPalLin(c.r), g = pxPalLin(c.g), b = pxPalLin(c.b);
	float l = pxPalCbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
	float m = pxPalCbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
	float s = pxPalCbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
	return vec3(0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
	            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
	            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s);
}

vec3 pxPalFromLab(vec3 q)
{
	float l = q.x + 0.3963377774 * q.y + 0.2158037573 * q.z;
	float m = q.x - 0.1055613458 * q.y - 0.0638541728 * q.z;
	float s = q.x - 0.0894841775 * q.y - 1.2914855480 * q.z;
	l = l * l * l; m = m * m * m; s = s * s * s;
	return vec3(pxPalEnc(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
	            pxPalEnc(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
	            pxPalEnc(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s));
}

vec3 pxPalMix(vec3 a, vec3 b, float f)
{
	if (uPalCtl.w > 0.5) return pxPalFromLab(mix(pxPalToLab(a), pxPalToLab(b), f));
	return mix(a, b, f);
}

// Stop i rotated by the shift (shift 1/n = one stop on). Any int i (wraps both ways). Use for "colour k" picks:
// ring k, line k, light k, the k-th beat.
vec3 pxPalStep(int i)
{
	int n = pxPalCount();
	if (n == 0) return vec3(0.0);
	int k = int(floor(uPalCtl.y * float(n) + 0.5));
	int j = ((i + k) % n + n) % n;
	return uPal[j].rgb;
}

// Colour at palette position t. gradient: t clamped to 0..1, blend between positioned stops (two stops at the same
// position = a hard edge), ends hold. steps: n equal bands (positions ignored), stop i owns [i/n, (i+1)/n).
// cycle: t wraps, the last stop blends back into the first across [p_last, 1 + p_first]. A non-zero shift rotates
// (wraps) in every mode.
vec3 pxPal(float t)
{
	int n = pxPalCount();
	if (n == 0) return vec3(0.0);
	if (n == 1) return uPal[0].rgb;
	int mode = int(uPalCtl.z + 0.5);
	float u;
	if (mode == 2) u = fract(t + uPalCtl.y);
	else
	{
		u = clamp(t, 0.0, 1.0);
		if (uPalCtl.y != 0.0) u = fract(u + uPalCtl.y);
	}
	if (mode == 1) return uPal[min(int(u * float(n)), n - 1)].rgb;
	float p0 = uPal[0].a, pl = uPal[n - 1].a;
	if (mode == 2 && (u < p0 || u >= pl))
	{
		float x = u < p0 ? u + 1.0 : u;
		return pxPalMix(uPal[n - 1].rgb, uPal[0].rgb, clamp((x - pl) / max(p0 + 1.0 - pl, 1e-6), 0.0, 1.0));
	}
	if (u <= p0) return uPal[0].rgb;
	if (u >= pl) return uPal[n - 1].rgb;
	for (int i = 0; i < PX_PAL_MAX - 1; i++)
	{
		if (i + 1 >= n) break;
		float a = uPal[i].a, b = uPal[i + 1].a;
		if (u < b) return pxPalMix(uPal[i].rgb, uPal[i + 1].rgb, clamp((u - a) / max(b - a, 1e-6), 0.0, 1.0));
	}
	return uPal[n - 1].rgb;
}

// Colour source: how ANY coloured element (line, haze, glow, ember, effector glow, light, point recolour) picks its
// colour. One vec4 uniform per element, cs = (mode, pos, spread, keep) from palette_map_logic.colsrc_vec:
//   mode 0 solid (the element's own RGB par)   1 palette at pos            2 palette at pos + spread * attrT
//        3 source colour (keep what it had)     4 stop index round(pos + spread * attrT) via pxPalStep
//   keep 0..1 mixes the result back toward src (1 = source unchanged).
// attrT = whatever the consumer maps (depth, height, age, along-line, ring index, time); src = the element's own
// colour before recolouring (scan colour, light colour); use solid for src when there is none.
vec3 pxColSrc(vec4 cs, vec3 solid, vec3 src, float attrT)
{
	int m = int(cs.x + 0.5);
	vec3 c;
	if (m == 0) c = solid;
	else if (m == 1) c = pxPal(cs.y);
	else if (m == 2) c = pxPal(cs.y + cs.z * attrT);
	else if (m == 4) c = pxPalStep(int(floor(cs.y + cs.z * attrT + 0.5)));
	else c = src;
	return mix(c, src, clamp(cs.w, 0.0, 1.0));
}

#ifdef PX_PAL_SHORT_NAMES
vec3 palette(float t) { return pxPal(t); }
vec3 palette_step(int i) { return pxPalStep(i); }
#endif
#endif
