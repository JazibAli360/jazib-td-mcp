// gen_sim_lava_mass: GEN_sim 'lavalamp' mass book (compute, 1x1). in0 = avg (Analyze TOP: per-channel average of the
// state), in1 = mass_fb (this pass last frame). Out x = target mean density (taken from the first frame of an epoch,
// i.e. the seeded total), y = current mean density, a = epoch. == builders/gen_sim_logic.py lava_mass.
// uM = epoch 0 0 0.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uM;

void main()
{
	vec4 avg = texelFetch(sTD2DInputs[0], ivec2(0), 0);
	vec4 last = texelFetch(sTD2DInputs[1], ivec2(0), 0);
	float target = abs(last.a - uM.x) > 0.5 ? avg.z : last.x;
	TDImageStoreOutput(0, ivec3(0, 0, 0), vec4(target, avg.z, 0.0, uM.x));
}
