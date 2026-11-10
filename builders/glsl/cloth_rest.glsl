// BN_cloth rest shape (compute, W x H rgba32f): xyz = rest position, w = 1 if pinned. = cloth_logic.rest_arrays.
// in0 = pin mask (in2 or black; luma > 0.5 pins when Pins = mask). Cooks only when its pars change.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uRestA;   // W, H, Sizew, Sizeh
uniform vec4 uRestB;   // orient (0 vertical, 1 horizontal), Top, pin mode index, 0

void main()
{
	ivec2 c = ivec2(gl_GlobalInvocationID.xy);
	int W = int(uRestA.x + 0.5), H = int(uRestA.y + 0.5);
	if (c.x >= W || c.y >= H) return;
	float u = float(c.x) / float(max(W - 1, 1));
	float v = float(c.y) / float(max(H - 1, 1));
	vec3 p;
	p.x = (u - 0.5) * uRestA.z;
	if (uRestB.x > 0.5) p = vec3(p.x, uRestB.y, (0.5 - v) * uRestA.w);
	else p = vec3(p.x, uRestB.y - (1.0 - v) * uRestA.w, 0.0);
	int pm = int(uRestB.z + 0.5);
	bool pin = false;
	if (pm == PIN_TOP) pin = c.y == H - 1;
	else if (pm == PIN_TOPCORNERS) pin = c.y == H - 1 && (c.x == 0 || c.x == W - 1);
	else if (pm == PIN_CORNERS) pin = (c.y == 0 || c.y == H - 1) && (c.x == 0 || c.x == W - 1);
	else if (pm == PIN_MASK) {
		vec4 m = texture(sTD2DInputs[0], (vec2(c) + 0.5) / vec2(W, H));
		pin = dot(m.rgb, vec3(0.2126, 0.7152, 0.0722)) > 0.5;
	}
	TDImageStoreOutput(0, ivec3(c, 0), vec4(p, pin ? 1.0 : 0.0));
}
