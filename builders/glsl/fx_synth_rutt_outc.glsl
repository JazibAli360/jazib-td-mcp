// FX_synth ruttetra out (compute, input format): background (black / dimmed input / transparent) + the beam state,
// then Amount against the input. in0 = in1 (picture), in1 = post (16f state). Amount 0 = texelFetch (exact; the
// module's out_sel also skips the whole engine then).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, background (black input transparent), input dim, 0
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= sz.x || p.y >= sz.y) return;
    vec4 a = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), a); return; }
    vec4 s = texelFetch(sTD2DInputs[1], p, 0);
    int bg = int(uA.y + 0.5);
    vec4 o;
    if (bg == 0) o = vec4(s.rgb, 1.0);
    else if (bg == 1) o = vec4(a.rgb * uA.z + s.rgb, a.a);
    else o = vec4(s.rgb, s.a);
    TDImageStoreOutput(0, ivec3(p, 0), mix(a, o, uA.x));
}
