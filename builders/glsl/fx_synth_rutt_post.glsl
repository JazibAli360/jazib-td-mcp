// FX_synth ruttetra post (compute, T-47): beam glow + phosphor persistence. in0 = the line render (inputfiltertype
// mipmap: glow = weighted mip levels 1-5 of the lines, T-116 (1)), in1 = previous post (Feedback TOP).
// state = max(lines + Glow * mips, previous * Persist) in 16-bit float; alpha = brightest channel (for transparent).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // glow, persist, 0, 0
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= sz.x || p.y >= sz.y) return;
    vec3 c = texelFetch(sTD2DInputs[0], p, 0).rgb;
    if (uA.x > 0.0) {
        vec2 uv = (vec2(p) + 0.5) / vec2(sz);
        vec3 g = 0.30 * textureLod(sTD2DInputs[0], uv, 1.0).rgb + 0.25 * textureLod(sTD2DInputs[0], uv, 2.0).rgb
               + 0.20 * textureLod(sTD2DInputs[0], uv, 3.0).rgb + 0.15 * textureLod(sTD2DInputs[0], uv, 4.0).rgb
               + 0.10 * textureLod(sTD2DInputs[0], uv, 5.0).rgb;
        c += uA.x * g * 4.0;
    }
    if (uA.y > 0.0) c = max(c, texelFetch(sTD2DInputs[1], p, 0).rgb * uA.y);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(c, clamp(max(c.r, max(c.g, c.b)), 0.0, 1.0)));
}
