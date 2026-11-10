// gen_sim_clock: 1x1 rgba32float in place (outputaccess readwrite, clearoutputs off; T-110 (5), T-111 (1)).
// x = module time (integrates dt * Speed, so a Speed change never jumps the motion), y = absTime of the last cook,
// z = last dt, w = 1 once started. Cooks only when a consumer cooks; a second cook in the same frame (readback,
// T-116 (4) / T-117 (4)) keeps the value. dt is capped at 0.1 s (a stall or a bypass does not jump the motion).
// uClk = absTime.seconds, Speed, 0, 0.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uClk;
void main()
{
	vec4 s = TDImageLoadOutput(0, ivec3(0));
	if (s.w > 0.5 && s.y == uClk.x) { TDImageStoreOutput(0, ivec3(0), s); return; }
	float dt = (s.w > 0.5) ? clamp(uClk.x - s.y, 0.0, 0.1) : 0.0;
	TDImageStoreOutput(0, ivec3(0), vec4(s.x + dt * uClk.y, uClk.x, dt, 1.0));
}
