// FX_synth out mix (compute, input format): live -> state by Amount (vfeedback). in0 = in1 picture, in1 = state.
// Amount 0 = texelFetch of in0 (exact); the state keeps evolving underneath.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, 0, 0, 0
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= sz.x || p.y >= sz.y) return;
    vec4 a = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), a); return; }
    TDImageStoreOutput(0, ivec3(p, 0), mix(a, texelFetch(sTD2DInputs[1], p, 0), uA.x));
}
