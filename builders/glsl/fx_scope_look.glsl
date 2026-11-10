// FX_scope look (compute, input size, format useinput): the beam state + glow tone-mapped (1 - exp(-x): bright
// cores burn to white) inside the panel, graticule, overlay (cellophane bands), goniometer meter, background mode,
// Amount mix. Outside the panel = texelFetch of in0 (exact). in0 = picture, in1 = beam state, in2 = glow or 1x1.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uPn;   // panel x0 y0 w h (output px)
uniform vec4 uE;    // exposure, glow, flash, amount
uniform vec4 uF;    // flash tint r g b, background (0 add, 1 dim, 2 black, 3 screen)
uniform vec4 uC;    // phosphor tint r g b (graticule / screen), bg dim
uniform vec4 uGr;   // graticule opacity, style (0 none 1 scope 2 polar 3 cross), div x, div y
uniform vec4 uO;    // overlay on, split (panel y 0..1), meter on, meter value (-1..1)
uniform vec4 uO1;   // overlay top rgb
uniform vec4 uO2;   // overlay bottom rgb
float gline(float q, float div, float px) {           // distance (px) to the nearest of div + 1 lines -> 1 px AA
    float d = abs(fract(q * div + 0.5) - 0.5) * px / max(div, 1.0);
    return clamp(1.0 - d, 0.0, 1.0);
}
float graticule(vec2 q) {
    int st = int(uGr.y + 0.5);
    if (st == 0 || uGr.x <= 0.0) return 0.0;
    vec2 S = uPn.zw;
    float g = 0.0;
    if (st == 1) {
        g = max(gline(q.x, uGr.z, S.x), gline(q.y, uGr.w, S.y));
        vec2 dc = abs(q - 0.5) * S;                     // minor ticks (5 per division) on the centre axes
        if (dc.y < 5.0) g = max(g, gline(q.x, uGr.z * 5.0, S.x));
        if (dc.x < 5.0) g = max(g, gline(q.y, uGr.w * 5.0, S.y));
    } else if (st == 2) {
        float m = 0.5 * min(S.x, S.y);
        float r = length((q - 0.5) * S) / m;
        g = clamp(1.0 - abs(r * 4.0 - floor(r * 4.0 + 0.5)) * m * 0.25, 0.0, 1.0) * step(r, 1.02);
    }
    vec2 dc = abs(q - 0.5) * S;
    g = max(g, max(clamp(1.0 - dc.x, 0.0, 1.0), clamp(1.0 - dc.y, 0.0, 1.0)));   // centre cross (all styles)
    return g;
}
void main() {
    ivec2 P = ivec2(gl_GlobalInvocationID.xy);
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    if (P.x >= R.x || P.y >= R.y) return;
    vec4 src = texelFetch(sTD2DInputs[0], P, 0);
    vec2 q = (vec2(P) + 0.5 - uPn.xy) / uPn.zw;
    if (q.x < 0.0 || q.y < 0.0 || q.x >= 1.0 || q.y >= 1.0) { TDImageStoreOutput(0, ivec3(P, 0), src); return; }
    vec4 st = texture(sTD2DInputs[1], q);
    vec3 D = st.rgb + uE.z * uF.rgb * st.a;
    vec3 G = uE.y > 0.0 ? texture(sTD2DInputs[2], q).rgb : vec3(0.0);
    vec3 sc = 1.0 - exp(-uE.x * (D + uE.y * G));
    if (uO.x > 0.5) sc *= q.y >= uO.y ? uO1.rgb : uO2.rgb;
    sc += uGr.x * graticule(q) * uC.rgb;
    if (uO.z > 0.5) {                                   // correlation meter: bottom bar, green in phase, red out
        float y = q.y * uPn.w;
        if (y > 6.0 && y < 18.0) {
            float x = (q.x - 0.5) * 2.0;
            float v = clamp(uO.w, -1.0, 1.0);
            if ((v >= 0.0 && x >= 0.0 && x <= v * 0.9) || (v < 0.0 && x <= 0.0 && x >= v * 0.9))
                sc += v >= 0.0 ? vec3(0.1, 0.9, 0.2) : vec3(0.95, 0.15, 0.1);
            if (abs(x) * uPn.z * 0.5 < 1.0 || abs(abs(x) - 0.9) * uPn.z * 0.5 < 1.0) sc += vec3(0.7);
        }
    }
    int bg = int(uF.w + 0.5);
    vec4 base = src;
    if (bg == 1) base.rgb *= 1.0 - uC.w;
    else if (bg == 2) base = vec4(0.0, 0.0, 0.0, 1.0);
    else if (bg == 3) base = vec4(uC.rgb * 0.035, 1.0);
    vec4 o = vec4(base.rgb + sc, bg == 0 ? clamp(base.a + max(max(sc.r, sc.g), sc.b), 0.0, 1.0) : 1.0);
    o = clamp(mix(src, o, uE.w), 0.0, 1.0);
    TDImageStoreOutput(0, ivec3(P, 0), o);
}
