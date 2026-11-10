// FX_synth scanimate warp (compute, T-47; FX2 AV-27). The Scanimate raster: every output line samples the source
// through the deflection functions (fly-in zoom + spin, perspective taper, horizontal sine bend that travels along
// the lines), Settle 1 = the clean source (all warps x 0). The source is keyed to a high-contrast mask (luma above
// Key, Keysoft wide). Out (rgba16f): premultiplied source colour x key, alpha = key.
// = builders/fx_synth_logic.py sc_warp(). in0 = source (in1 picture or the logo text TOP).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // key, key softness, settle, time s
uniform vec4 uB;   // bend (widths), bend freq (cycles per height), bend speed (cycles/s), taper
uniform vec4 uC;   // zoom, fly (zoom swing), fly speed (Hz), rotate deg
uniform vec4 uD;   // spin deg/s, 0, 0, 0
const float TAU = 6.28318530718;
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
float rise(float x, float e, float s) { return s > 0.0 ? clamp((x - e) / s + 0.5, 0.0, 1.0) : (x >= e ? 1.0 : 0.0); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec2 sz = vec2(isz);
    float a = sz.x / sz.y;
    float t = uA.w;
    float k = 1.0 - uA.z;
    vec2 c = vec2(((float(p.x) + 0.5) / sz.x - 0.5) * a, (float(p.y) + 0.5) / sz.y - 0.5);
    float Z = uC.x * (1.0 + k * uC.y * sin(TAU * uC.z * t));
    float th = radians(uC.w + k * uD.x * t);
    vec2 q = vec2(c.x * cos(th) + c.y * sin(th), -c.x * sin(th) + c.y * cos(th)) / Z;
    float s = 1.0 + k * uB.w * 2.0 * q.y;
    float b = k * uB.x * a * sin(TAU * (uB.y * q.y + uB.z * t));
    float sx = (q.x - b) / max(s, 1e-3);
    vec2 uv = vec2(sx / a + 0.5, q.y + 0.5);
    vec4 col = vec4(0.0);
    if (s > 1e-3 && all(greaterThanEqual(uv, vec2(0.0))) && all(lessThanEqual(uv, vec2(1.0))))
        col = texture(sTD2DInputs[0], uv);
    float m = rise(lum(col.rgb), uA.x, uA.y);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(col.rgb * m, m));
}
