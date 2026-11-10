// FX_scope lissajous source: analytic figures (logic.figure_points) or the goniometer (audio M/S).
uniform vec4 uL0;   // figure (0 lissajous 1 harmonograph 2 spirograph 3 rose 4 goniometer), points, turns, drift
uniform vec4 uL1;   // a, b, phase (cycles), damping
uniform vec4 uL2;   // c, d, second-pendulum mix, window start (pendulum s)
uniform vec4 uL3;   // spiro R, spiro r, pen d, window length (pendulum s)
uniform vec4 uL4;   // rainbow, hue shift, gain, theta range (spirograph / rose, rad)
uniform vec4 uL5;   // rose k, 0, 0, 0
int scopeCount() {
    if (int(uL0.x + 0.5) == 4) return audioCount();
    return clamp(int(uL0.y + 0.5), 2, CAP);
}
vec2 scopePoint(int j, int np, out vec3 col, out float w) {
    int fig = int(uL0.x + 0.5);
    float u = float(j) / float(max(np - 1, 1));
    const float TP = 6.283185307179586;
    vec2 p;
    w = 1.0;
    col = uL4.x > 0.5 ? hsv2rgb(u + uL4.y) : vec3(1.0);
    if (fig == 0) {
        float th = TP * uL0.z * u;
        p = vec2(sin(uL1.x * th + TP * (uL1.z + uL0.w)), sin(uL1.y * th));
    } else if (fig == 1) {
        float t = uL2.w + u * uL3.w;
        float dm = exp(-uL1.w * t);
        p = dm * vec2((1.0 - uL2.z) * sin(TP * (uL1.x * t + uL1.z + uL0.w)) + uL2.z * sin(TP * uL2.x * t),
                      (1.0 - uL2.z) * sin(TP * uL1.y * t) + uL2.z * sin(TP * (uL2.y * t + 0.25)));
    } else if (fig == 2) {
        float th = uL4.w * u;
        float Rr = uL3.x - uL3.y;
        float k = Rr / max(uL3.y, 1e-6);
        float sc = 1.0 / max(abs(Rr) + abs(uL3.z), 1e-6);
        vec2 q = vec2(Rr * cos(th) + uL3.z * cos(k * th), Rr * sin(th) - uL3.z * sin(k * th)) * sc;
        float ca = cos(TP * uL0.w), sa = sin(TP * uL0.w);
        p = vec2(q.x * ca - q.y * sa, q.x * sa + q.y * ca);
    } else if (fig == 3) {
        float th = uL4.w * u;
        float r = cos(uL5.x * th + TP * uL0.w);
        p = r * vec2(cos(th), sin(th));
    } else {
        vec2 v = audioPoint(j, np);
        p = vec2(v.x - v.y, v.x + v.y) * 0.7071067811865476;
    }
    return p * uL4.z;
}
