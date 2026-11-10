// FX_synth scanimate trail (compute, T-47): the long-tail streamers. state = warp OVER (previous state resampled with
// Trailzoom / Trail x,y drift, softened by Trailblur, x Decay x (1 - Settle)), premultiplied, 16-bit float; alpha =
// trail intensity (1 = drawn this cook, Decay^n = n generations old) -> the look pass colours by it.
// in0 = warp, in1 = previous state (Feedback TOP), in2 = stamp (z = 0 -> fresh: restart from warp).
// Point-wise part = builders/fx_synth_logic.py sc_trail_step().
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // decay, trail zoom, trail x px, trail y px
uniform vec4 uB;   // trail blur 0..1, reset, settle, 0
vec4 tap(vec2 q, vec2 sz) {
    if (any(lessThan(q, vec2(0.0))) || any(greaterThan(q, sz))) return vec4(0.0);
    return texture(sTD2DInputs[1], q / sz);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec2 sz = vec2(isz);
    vec4 w = texelFetch(sTD2DInputs[0], p, 0);
    vec4 st = texelFetch(sTD2DInputs[2], ivec2(0), 0);
    if (st.z < 0.5 || uB.y > 0.5) { TDImageStoreOutput(0, ivec3(p, 0), w); return; }
    vec2 C = sz * 0.5;
    vec2 q = C + (vec2(p) + 0.5 - C) / max(uA.y, 1e-4) - uA.zw;
    vec4 d = tap(q, sz);
    if (uB.x > 0.0) {
        vec4 b = (d + tap(q + vec2(1.0, 0.0), sz) + tap(q - vec2(1.0, 0.0), sz) + tap(q + vec2(0.0, 1.0), sz)
                  + tap(q - vec2(0.0, 1.0), sz)) * 0.2;
        d = mix(d, b, uB.x);
    }
    d *= uA.x * (1.0 - uB.z);
    TDImageStoreOutput(0, ivec3(p, 0), w + d * (1.0 - w.a));
}
