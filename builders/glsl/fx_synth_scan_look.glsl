// FX_synth scanimate look (compute, T-47): trail intensity -> colour ramp (Palette, 4 stops fresh -> old; Bands
// quantise the age = banded streamers), Colour logo keeps the source colours where the trail is fresh, raster
// scanlines (Lines visible lines, Linegap dark share), glow from the trail's mips (inputfiltertype mipmap, lods 1-4),
// background black / input / transparent, then Amount against the input. = builders/fx_synth_logic.py
// sc_colourise() + palette(). in0 = in1 picture (sets the format + size), in1 = trail state (16f).
// Amount 0 = texelFetch of in0 (exact).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, colour (ramp logo), palette, bands (0 = smooth)
uniform vec4 uB;   // lines (0 off), line gap, glow, background (black input transparent)
const vec3 PAL[20] = vec3[20](
    vec3(1.0, 0.725, 0.012), vec3(1.0, 0.267, 0.498), vec3(0.792, 0.278, 0.914), vec3(0.231, 0.075, 0.184),
    vec3(1.0, 0.97, 0.8), vec3(1.0, 0.7, 0.15), vec3(0.95, 0.2, 0.15), vec3(0.35, 0.05, 0.4),
    vec3(0.9, 1.0, 1.0), vec3(0.1, 0.9, 1.0), vec3(0.15, 0.25, 1.0), vec3(0.6, 0.0, 0.8),
    vec3(1.0, 1.0, 1.0), vec3(0.75, 0.8, 0.85), vec3(0.3, 0.45, 0.65), vec3(0.05, 0.08, 0.15),
    vec3(1.0, 1.0, 1.0), vec3(0.66, 0.66, 0.66), vec3(0.33, 0.33, 0.33), vec3(0.0, 0.0, 0.0));
vec3 pal(int idx, float x) {
    x = clamp(x, 0.0, 1.0) * 3.0;
    int k = min(int(floor(x)), 2);
    int b = clamp(idx, 0, 4) * 4;
    return mix(PAL[b + k], PAL[b + k + 1], x - float(k));
}
vec3 colourise(vec4 tr) {
    float a = clamp(tr.a, 0.0, 1.0);
    float nb = floor(uA.w + 0.5);
    float aq = nb > 0.0 ? max(ceil(a * nb - 1e-4) / nb, 0.0) : a;
    vec3 col = pal(int(uA.z + 0.5), 1.0 - a) * aq;
    if (uA.y > 0.5) col = mix(col, tr.rgb, pow(a, 16.0));
    return col;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 live = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), live); return; }
    vec2 sz = vec2(isz);
    vec4 tr = texelFetch(sTD2DInputs[1], p, 0);
    vec3 c = colourise(tr);
    if (uB.x > 0.0) {
        float f = fract((float(p.y) + 0.5) / sz.y * uB.x);
        c *= f < 1.0 - uB.y ? 1.0 : 0.0;
    }
    if (uB.z > 0.0) {
        vec2 uv = (vec2(p) + 0.5) / sz;
        vec3 g = 0.35 * colourise(textureLod(sTD2DInputs[1], uv, 1.0)) + 0.3 * colourise(textureLod(sTD2DInputs[1], uv, 2.0))
               + 0.2 * colourise(textureLod(sTD2DInputs[1], uv, 3.0)) + 0.15 * colourise(textureLod(sTD2DInputs[1], uv, 4.0));
        c += uB.z * g;
    }
    int bg = int(uB.w + 0.5);
    float cov = clamp(tr.a, 0.0, 1.0);
    vec4 o;
    if (bg == 0) o = vec4(c, 1.0);
    else if (bg == 1) o = vec4(live.rgb * (1.0 - cov) + c, live.a);
    else o = vec4(c, clamp(max(cov, max(c.r, max(c.g, c.b))), 0.0, 1.0));
    TDImageStoreOutput(0, ivec3(p, 0), mix(live, o, uA.x));
}
