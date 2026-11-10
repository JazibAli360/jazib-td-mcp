// eff_field2d (compute GLSL TOP): the selected effectors as a 2D field on a world plane, for the 2D adapters
// (BN_fluid2d force + dye, FX_destroy mask). Output pixel (u, v) <- world point (cx + (u - .5) w, cy + (v - .5) h, z).
// Modes (uEffPlane2.y): 0 force = input + (push x outward dir + swirl x tangent + wake x effector velocity) x weight
// / plane height (screen heights per s^2, BN_fluid2d in3 units), alpha = weight; 1 dye = input premultiplied
// (rgb x a) + colour x amount x weight, alpha 1 (BN_fluid2d in1 adds rgb x a); 2 mask = weight (rgb), alpha 1.
// Input 0 (optional, uEffPlane2.x = 1): the image the field is added to (sampled at the same uv).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uEffPlane;   // centre x, centre y, width, height (world units)
uniform vec4 uEffPlane2;  // has input 0, mode, plane z, 0
uniform vec4 uEffOut;     // push, swirl, wake, dye amount
uniform vec4 uEffCol;     // dye colour rgb, 0

void main()
{
	ivec2 T = ivec2(gl_GlobalInvocationID.xy);
	ivec2 sz = ivec2(uTDOutputInfo.res.zw);
	if (T.x >= sz.x || T.y >= sz.y) return;
	vec2 uv = (vec2(T) + 0.5) / vec2(sz);
	vec4 base = vec4(0.0);
#if defined(TD_NUM_2D_INPUTS) && TD_NUM_2D_INPUTS > 0
	if (uEffPlane2.x > 0.5) base = textureLod(sTD2DInputs[0], uv, 0.0);
#endif
	// (live 31550: a GLSL TOP with no input declares no sTD2DInputs, so an unguarded read fails to compile)
	int mode = pxI(uEffPlane2.y);
	vec3 p = vec3(uEffPlane.x + (uv.x - 0.5) * uEffPlane.z, uEffPlane.y + (uv.y - 0.5) * uEffPlane.w, uEffPlane2.z);
	int b;
	float w = pxeConsumerW(p, b);
	vec4 o;
	if (mode == 1) {
		o = vec4(base.rgb * base.a + uEffCol.rgb * (uEffOut.w * w), 1.0);
	} else if (mode == 2) {
		o = vec4(vec3(w), 1.0);
	} else {
		vec2 f = vec2(0.0);
		if (b >= 0 && w > 0.0) {
			vec3 d = pxeGrad(b, p);
			vec3 t = cross(vec3(0.0, 0.0, 1.0), d);
			f = (d.xy * uEffOut.x + t.xy * uEffOut.y + pxeVelAt(b, p).xy * uEffOut.z) * (w / max(uEffPlane.w, 1e-6));
		}
		o = vec4(base.rg + f, base.b, max(base.a, w));
	}
	TDImageStoreOutput(0, ivec3(T, 0), o);
}
