// FX_scope vector source: a laser / path stream (LP_laser_path out1 by reference, any x y [r g b] CHOP, or the
// module's SOP path) drawn as vector strokes. Segment j is lit by sample j+1's colour (the beam lands with it);
// weight = its max channel x flicker, colour = rgb / max (so the beam keeps full hue). Overshoot pushes corner points
// outward along the second difference (galvo / deflection ringing look). Streams longer than CAP are decimated.
uniform vec4 uV0;   // gain x, gain y, colour from the stream (1) or white (0), blank threshold
uniform vec4 uV1;   // overshoot, flicker factor (this frame), 0, 0
int vIdx(int j, int np) {
    int n = BUF_N();
    return n <= CAP ? j : int(float(j) * float(n - 1) / float(max(np - 1, 1)) + 0.5);
}
vec2 vP(int j, int np) { return BUF_XY(vIdx(clamp(j, 0, np - 1), np)); }
int scopeCount() { return min(BUF_N(), CAP); }
vec2 scopePoint(int j, int np, out vec3 col, out float w) {
    vec2 p = vP(j, np);
    if (uV1.x != 0.0 && j > 0 && j < np - 1) p += uV1.x * (2.0 * p - vP(j - 1, np) - vP(j + 1, np));
    vec3 c = BUF_RGB(vIdx(min(j + 1, np - 1), np));
    float lit = max(max(c.r, c.g), c.b);
    if (uV0.z > 0.5) {
        w = lit > uV0.w ? lit * uV1.y : 0.0;
        col = clamp(c / max(lit, 1e-6), 0.0, 1.0);
    } else {
        w = uV1.y;
        col = vec3(1.0);
    }
    return p * uV0.xy;
}
