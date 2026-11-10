// FX_scope xy source: stereo audio (or the test tones) as X / Y, Catmull-Rom oversampled (fx_scope_audio.glsl).
uniform vec4 uX;    // gain x, gain y, swap, 0
int scopeCount() { return audioCount(); }
vec2 scopePoint(int j, int np, out vec3 col, out float w) {
    vec2 v = audioPoint(j, np);
    if (uX.z > 0.5) v = v.yx;
    col = vec3(1.0);
    w = 1.0;
    return v * uX.xy;
}
