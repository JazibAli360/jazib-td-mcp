// FX_synth ruttetra, GLSL MAT vertex shader (one render pass; T-46 does not apply). Rutt/Etra scan processor
// (FX2 AV-26): the picture's voltages are ADDED TO THE DEFLECTION of a raster of Lines scan lines (x' = x + Defx*s1,
// y' = y + Defy*s2), the beam brightness stays the picture, then the whole raster is scaled / sheared / rotated and
// optionally seen through a yaw/pitch/perspective camera with z = Z * luma (the td-port JZBN_RuttLines relief,
// read-only idea source). Geometry: a Grid SOP of 2 rows x Samples columns (size 1x1, P.x -0.5..0.5 = along the
// line, P.y +-0.5 = the two ribbon edges), instanced Lines times; TDInstanceID() = line index. The ribbon is expanded
// in screen pixels across the projected line, so Width is real pixels at any deflection. Camera COMP matrices are
// not used: the shader writes clip space itself (= builders/fx_synth_logic.py rt_place(); change both together).
uniform vec4 uA;   // lines, samples, width px, intensity
uniform vec4 uB;   // blank (luma below = beam off), scan (0 horizontal 1 vertical), colour mode, 0
uniform vec4 uC;   // deflect x source, deflect x gain, deflect y source, deflect y gain (picture heights)
uniform vec4 uD;   // z (relief gain), wave amp, wave freq (cycles per line), wave speed (cycles/s)
uniform vec4 uE;   // jitter (heights), jitter rate (Hz, 0 = static), seed, time s
uniform vec4 uF;   // rotate deg, scale x, scale y, shear
uniform vec4 uG;   // offset x, offset y (heights), yaw deg, pitch deg
uniform vec4 uH;   // perspective 0..1, mono colour rgb
uniform vec4 uR;   // output width, height (px), 0, 0
uniform sampler2D sSrc;
out Vertex { vec4 color; float across; } oV;
const float TAU = 6.28318530718;

float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
uint pcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                   return (w >> 22u) ^ w; }
float h3(uint a, uint b, uint c) { return float(pcg(a ^ pcg(b ^ pcg(c))) >> 8) / 16777215.0; }
vec3 hsv2rgb(float h, float s, float v) {
    vec3 k = clamp(abs(fract(h + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    return v * mix(vec3(1.0), k, s);
}
float signal(vec4 c, int w) {
    if (w == 0) return lum(c.rgb);
    if (w == 4) return 1.0 - lum(c.rgb);
    return c[w - 1];
}

vec2 place(float u, float li, out vec4 col) {
    vec2 res = uR.xy;
    float a = res.x / res.y;
    float L = max(floor(uA.x + 0.5), 1.0);
    float v = (li + 0.5) / L;
    bool hz = uB.y < 0.5;
    vec2 uv = hz ? vec2(u, v) : vec2(v, u);
    vec2 p = hz ? vec2((u - 0.5) * a, v - 0.5) : vec2((v - 0.5) * a, u - 0.5);
    col = textureLod(sSrc, uv, 0.0);
    p += vec2(uC.y * signal(col, int(uC.x + 0.5)), uC.w * signal(col, int(uC.z + 0.5)));
    float wv = uD.y * sin(TAU * (uD.z * u + uD.w * uE.w));
    float jt = 0.0;
    if (uE.x != 0.0) {
        uint tick = uE.y > 0.0 ? uint(floor(uE.w * uE.y)) : 0u;
        jt = (h3(uint(li), tick, uint(uE.z)) - 0.5) * uE.x;
    }
    if (hz) p.y += wv + jt; else p.x += wv + jt;
    float z = uD.x * lum(col.rgb);
    p *= uF.yz;
    p.x += uF.w * p.y;
    float ra = radians(uF.x), cr = cos(ra), sr = sin(ra);
    p = vec2(p.x * cr - p.y * sr, p.x * sr + p.y * cr) + uG.xy;
    float cy = cos(radians(uG.z)), sy = sin(radians(uG.z)), cp = cos(radians(uG.w)), sp = sin(radians(uG.w));
    vec3 c0 = vec3(cy, -sp * sy, -cp * sy), c1 = vec3(0.0, cp, -sp), c2 = vec3(sy, sp * cy, cp * cy);
    vec3 r = p.x * c0 + p.y * c1 + z * c2;
    float w = 1.0 / max(1.0 - uH.x / 3.0 * r.z, 1e-4);
    vec2 s = r.xy * w;
    return vec2((s.x / a + 0.5) * res.x, (s.y + 0.5) * res.y);
}

void main() {
    float li = float(TDInstanceID());
    float S = max(floor(uA.y + 0.5), 2.0);
    float du = 1.0 / (S - 1.0);
    float u = clamp(P.x + 0.5, 0.0, 1.0);
    vec4 col, cn;
    vec2 pa = place(u, li, col);
    vec2 tg = u + du <= 1.0 + 1e-6 ? place(min(u + du, 1.0), li, cn) - pa : pa - place(u - du, li, cn);
    float tl = length(tg);
    tg = tl > 1e-6 ? tg / tl : (uB.y < 0.5 ? vec2(1.0, 0.0) : vec2(0.0, 1.0));
    vec2 n = vec2(-tg.y, tg.x);
    float off = (P.y > 0.0 ? 1.0 : -1.0) * (uA.z * 0.5 + 1.0);
    vec2 pos = pa + n * off;
    gl_Position = vec4(pos / uR.xy * 2.0 - 1.0, 0.5, 1.0);   // z 0.5: inside both GL and Vulkan clip ranges
    int cm = int(uB.z + 0.5);
    float l = lum(col.rgb);
    vec3 rgb;
    if (cm == 0) rgb = col.rgb;
    else if (cm == 1) rgb = uH.yzw;
    else if (cm == 2) rgb = hsv2rgb(0.66 - 0.66 * l, 1.0, 1.0);
    else rgb = hsv2rgb(li / max(floor(uA.x + 0.5), 1.0), 0.8, 1.0);
    float on = l < uB.x ? 0.0 : uA.w;
    oV.color = vec4(rgb * on, on);
    oV.across = off;
}
