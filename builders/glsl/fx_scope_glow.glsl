// FX_scope glow (compute): 1/8 of the beam buffer, two 7x7 Gaussians (near + 3x wide, 0.6 / 0.4) of the display
// energy D = S + Flash x flash tint x E, read at mip lod 3 (inputfiltertype mipmap = an 8x8 box, T-116) so 1-px
// lines are not missed. Pulled only while Glow > 0.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uF;    // flash tint r g b, Flash
uniform vec4 uGl;   // radius (glow texels per tap), lod, 0, 0
vec3 D(vec2 uv) {
    vec4 s = textureLod(sTD2DInputs[0], uv, uGl.y);
    return s.rgb + uF.w * uF.rgb * s.a;
}
void main() {
    ivec2 g = ivec2(gl_GlobalInvocationID.xy);
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    if (g.x >= R.x || g.y >= R.y) return;
    vec2 uv = (vec2(g) + 0.5) / vec2(R);
    vec2 stp = max(uGl.x, 0.0) / vec2(R);
    vec3 n = vec3(0.0), w = vec3(0.0);
    float ws = 0.0;
    for (int j = -3; j <= 3; j++) {
        for (int i = -3; i <= 3; i++) {
            float k = exp(-float(i * i + j * j) / 4.5);
            vec2 o = vec2(float(i), float(j)) * stp;
            n += k * D(uv + o);
            w += k * D(uv + 3.0 * o);
            ws += k;
        }
    }
    TDImageStoreOutput(0, ivec3(g, 0), vec4((0.6 * n + 0.4 * w) / ws, 1.0));
}
