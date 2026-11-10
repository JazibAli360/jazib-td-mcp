// FX_scope audio source (xy + lissajous goniometer): N samples from the CHOP texture buffer (BUF_* from the
// builder's header) or the built-in test tones; point j of np sits at sample-space s = j (N-1)/(np-1), Catmull-Rom
// (oversample K or decimate past CAP with the same rule; logic.audio_points).
uniform vec4 uS0;   // source (0 test, 1 chop), test fx (cycles/sample), test fy, test amplitude
uniform vec4 uS1;   // test phase x (cycles), test phase y, test samples per frame, oversample K
int audioN() { return uS0.x > 0.5 ? BUF_N() : int(uS1.z + 0.5); }
vec2 audioSample(int i, int n) {
    i = clamp(i, 0, n - 1);
    if (uS0.x > 0.5) return BUF_XY(i);
    float fi = float(i);
    return uS0.w * vec2(sin(6.283185307179586 * (uS1.x + uS0.y * fi)), sin(6.283185307179586 * (uS1.y + uS0.z * fi)));
}
int audioCount() {
    int n = audioN();
    if (n < 2) return 0;
    return min(CAP, (n - 1) * max(int(uS1.w + 0.5), 1) + 1);
}
vec2 audioPoint(int j, int np) {
    int n = audioN();
    float s = float(j) * float(n - 1) / float(max(np - 1, 1));
    int i = int(floor(s));
    float f = s - float(i);
    if (i >= n - 1) { i = n - 2; f = 1.0; }
    vec2 p0 = audioSample(i - 1, n), p1 = audioSample(i, n), p2 = audioSample(i + 1, n), p3 = audioSample(i + 2, n);
    float f2 = f * f, f3 = f2 * f;
    return 0.5 * (2.0 * p1 + (p2 - p0) * f + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * f2
                  + (3.0 * p1 - p0 - 3.0 * p2 + p3) * f3);
}
