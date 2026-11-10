// FX_synth modulate (compute, T-47; FX7a SX-12 Hydra modulate bank, maths re-written, not copied: hydra-synth is
// AGPL, its API was read only). in0 = A (the picture that bends), in1 = B (the modulator: A itself, any TOP, or the
// built-in noise; sampled at the same uv, any size). = builders/fx_synth_logic.py modulate(). Modes:
//  0 modulate  uv + (B.rg - Offset) * Multiple            5 repeat   uv x Repeat, odd rows / columns shifted, + B.rg x Multiple
//  1 scale     about the centre by 1 / (1 + Offset + Multiple B.r)   6 kaleid   Sides-fold about the centre, radius x (1 + Multiple B.r)
//  2 rotate    about the centre by Offset + Multiple B.r (rad)       7 scrollx  x + Multiple B.r + Speed t
//  3 hue       uv + (B.g - B.r, B.b - B.g) Multiple px              8 scrolly  y + Multiple B.r + Speed t
//  4 pixelate  cells = Offset + Multiple B.rg (min 1)
// then uv = mix(uv0, uv, Amount) (aspect: uv units, like Hydra), Wrap: repeat / mirror / hold / transparent.
// Amount 0 = texelFetch of A (exact; out_sel also bypasses the pass). No loops.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, mode, multiple, offset
uniform vec4 uB;   // repeat x, repeat y, sides, speed
uniform vec4 uC;   // wrap (0 repeat 1 mirror 2 hold 3 transparent), time s, 0, 0
const float TAU = 6.28318530718;
const float PI = 3.14159265359;
vec2 rot(vec2 v, float a) { float c = cos(a), s = sin(a); return vec2(c * v.x - s * v.y, s * v.x + c * v.y); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= sz.x || p.y >= sz.y) return;
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), texelFetch(sTD2DInputs[0], p, 0)); return; }
    vec2 st = (vec2(p) + 0.5) / vec2(sz);
    vec4 c = texture(sTD2DInputs[1], st);
    int mode = int(uA.y + 0.5);
    float mul = uA.z, ofs = uA.w;
    vec2 uv = st;
    if (mode == 0) {
        uv = st + (c.rg - ofs) * mul;
    } else if (mode == 1) {
        float f = 1.0 + ofs + mul * c.r;
        f = abs(f) < 1e-3 ? (f < 0.0 ? -1e-3 : 1e-3) : f;
        uv = (st - 0.5) / f + 0.5;
    } else if (mode == 2) {
        uv = rot(st - 0.5, ofs + mul * c.r) + 0.5;
    } else if (mode == 3) {
        uv = st + vec2(c.g - c.r, c.b - c.g) * mul / vec2(sz);
    } else if (mode == 4) {
        vec2 cells = max(vec2(ofs) + mul * c.rg, vec2(1.0));
        uv = (floor(st * cells) + 0.5) / cells;
    } else if (mode == 5) {
        vec2 q = st * uB.xy;
        q.x += step(1.0, mod(q.y, 2.0)) + c.r * mul;
        q.y += step(1.0, mod(q.x, 2.0)) + c.g * mul;
        uv = fract(q);
    } else if (mode == 6) {
        vec2 d = st - 0.5;
        float r = length(d);
        float n = max(uB.z, 1.0);
        float a = mod(atan(d.y, d.x), TAU / n);
        a = abs(a - PI / n);
        uv = 0.5 + vec2(cos(a), sin(a)) * r * (1.0 + mul * c.r);
    } else if (mode == 7) {
        uv = st + vec2(mul * c.r + uB.w * uC.y, 0.0);
    } else {
        uv = st + vec2(0.0, mul * c.r + uB.w * uC.y);
    }
    uv = mix(st, uv, uA.x);
    int wrap = int(uC.x + 0.5);
    vec4 o;
    if (wrap == 3 && (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0)) {
        o = vec4(0.0);
    } else {
        if (wrap == 0) uv = fract(uv);
        else if (wrap == 1) uv = 1.0 - abs(1.0 - mod(uv, 2.0));
        o = texture(sTD2DInputs[0], uv);
    }
    TDImageStoreOutput(0, ivec3(p, 0), o);
}
