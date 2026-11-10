// persist_add: beam_render + persist_fb x decay in one pass (perf wave 3, 27 Oct; replaced the persist_decay Level TOP
// + the persist_add Composite TOP). Like the Level brightness, the decay scales rgb only. PIXEL mode on purpose: a
// compute output (storage texture) made the glow Blur that reads it ~2x dearer on this Mac (T-222); one pixel pass
// reading a Render TOP + a Feedback TOP is the same risk class as the stock Level / Composite it replaced (T-46).
uniform vec4 uDecay;   // x = per-frame decay (lp_rt.decay_factor)
out vec4 fragColor;
void main()
{
	ivec2 p = ivec2(gl_FragCoord.xy);
	vec4 r = texelFetch(sTD2DInputs[0], p, 0);
	vec4 f = texelFetch(sTD2DInputs[1], p, 0);
	fragColor = r + vec4(f.rgb * uDecay.x, f.a);
}
