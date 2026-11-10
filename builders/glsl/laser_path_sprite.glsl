// LP_laser_path sprite: soft round beam spot used as the colour map of the instanced preview spots.
// GLSL TOP, Vertex/Pixel mode, ONE pass, no inputs (T-46 multi-pass hazard does not apply), custom res 64x64,
// format rgba16float. Copied by builders/laser_path.py into the GLSL TOP's docked pixel DAT (sprite_pixel).
// Alpha = brightness so the additive Constant MAT (src one, dst one) piles spots: dwell = brighter.
out vec4 fragColor;
void main()
{
    vec2 uv = vUV.st * 2.0 - 1.0;
    float r2 = dot(uv, uv);
    float a = exp(-r2 * 6.0) * (1.0 - smoothstep(0.8, 1.0, r2));
    fragColor = TDOutputSwizzle(vec4(vec3(a), a));
}
