// FSR 1 EASU (edge-adaptive spatial upsampling), compute GLSL TOP, shared file (no COMP). Port of AMD FidelityFX
// FSR 1 `FsrEasuF` (ffx_fsr1.h, MIT, (c) Advanced Micro Devices; via libretro slang-shaders edge-smoothing/fsr),
// float path, written for TD 2025.31550 compute. Mirror: builders/fsr_logic.py (easu). Research: FX7a SX-10.
// Input 0 = the low-res picture (any rgba; premultiplied works: one weight set for all 4 channels).
// Output = uEasu.xy pixels (set the GLSL TOP's resolution to the same numbers; T-119: never me.width).
// Same 12 taps as AMD (b c / e f g h / i j k l / n o), luma = 0.5 r + g + 0.5 b, direction + length from the 4
// bilinear quads, a stretched Lanczos-like {2/5 d2 - 1}^2 x {lob d2 - 1}^2 kernel, de-ringing clamp to the 2x2
// nearest min / max (per channel). Exact AMD constants; the approximate rcp / rsqrt are exact here (rcp(0) -> 0
// where AMD's huge rcp is multiplied by 0). uEasu.z: 1 = EASU, 0 = plain bilinear (A/B checks). No loops. (A shared-memory tile version was 1.4x SLOWER in a
// paired A/B on 31550, same output: the texture cache wins here; LEARNINGS T-171.)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uEasu;
ivec2 ESZ;
vec4 etap(ivec2 c) { return texelFetch(sTD2DInputs[0], clamp(c, ivec2(0), ESZ - 1), 0); }
float eluma(vec4 c) { return c.b * 0.5 + (c.r * 0.5 + c.g); }
void easu_set(inout vec2 dir, inout float len, float w, float lA, float lB, float lC, float lD, float lE) {
    //   a
    // b c d
    //   e
    float dc = lD - lC, cb = lC - lB;
    float lx = max(abs(dc), abs(cb));
    float dx = lD - lB;
    dir.x += dx * w;
    lx = lx > 0.0 ? clamp(abs(dx) / lx, 0.0, 1.0) : 0.0;
    len += lx * lx * w;
    float ec = lE - lC, ca = lC - lA;
    float ly = max(abs(ec), abs(ca));
    float dy = lE - lA;
    dir.y += dy * w;
    ly = ly > 0.0 ? clamp(abs(dy) / ly, 0.0, 1.0) : 0.0;
    len += ly * ly * w;
}
void easu_tap(inout vec4 aC, inout float aW, vec2 off, vec2 dir, vec2 len2, float lob, float clp, vec4 c) {
    vec2 v = vec2(off.x * dir.x + off.y * dir.y, off.x * (-dir.y) + off.y * dir.x) * len2;
    float d2 = min(v.x * v.x + v.y * v.y, clp);
    float wB = 2.0 / 5.0 * d2 - 1.0;
    float wA = lob * d2 - 1.0;
    wB *= wB;
    wA *= wA;
    wB = 25.0 / 16.0 * wB - (25.0 / 16.0 - 1.0);
    float w = wB * wA;
    aC += c * w;
    aW += w;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(int(uEasu.x + 0.5), int(uEasu.y + 0.5));
    if (p.x >= osz.x || p.y >= osz.y) return;
    ESZ = textureSize(sTD2DInputs[0], 0);
    vec2 pp = (vec2(p) + 0.5) * vec2(ESZ) / vec2(osz) - 0.5;
    vec2 fp = floor(pp);
    pp -= fp;
    ivec2 q = ivec2(fp);
    vec4 fC = etap(q), gC = etap(q + ivec2(1, 0)), jC = etap(q + ivec2(0, 1)), kC = etap(q + ivec2(1, 1));
    if (uEasu.z < 0.5) {                         // plain bilinear (clamp to edge), for A/B against EASU
        TDImageStoreOutput(0, ivec3(p, 0), mix(mix(fC, gC, pp.x), mix(jC, kC, pp.x), pp.y));
        return;
    }
    vec4 bC = etap(q + ivec2(0, -1)), cC = etap(q + ivec2(1, -1));
    vec4 eC = etap(q + ivec2(-1, 0)), hC = etap(q + ivec2(2, 0));
    vec4 iC = etap(q + ivec2(-1, 1)), lC = etap(q + ivec2(2, 1));
    vec4 nC = etap(q + ivec2(0, 2)), oC = etap(q + ivec2(1, 2));
    float bL = eluma(bC), cL = eluma(cC), eL = eluma(eC), fL = eluma(fC), gL = eluma(gC), hL = eluma(hC);
    float iL = eluma(iC), jL = eluma(jC), kL = eluma(kC), lL = eluma(lC), nL = eluma(nC), oL = eluma(oC);
    vec2 dir = vec2(0.0);
    float len = 0.0;
    easu_set(dir, len, (1.0 - pp.x) * (1.0 - pp.y), bL, eL, fL, gL, jL);
    easu_set(dir, len, pp.x * (1.0 - pp.y), cL, fL, gL, hL, kL);
    easu_set(dir, len, (1.0 - pp.x) * pp.y, fL, iL, jL, kL, nL);
    easu_set(dir, len, pp.x * pp.y, gL, jL, kL, lL, oL);
    float dirR = dir.x * dir.x + dir.y * dir.y;
    bool zro = dirR < 1.0 / 32768.0;
    dirR = zro ? 1.0 : inversesqrt(dirR);
    dir.x = zro ? 1.0 : dir.x;
    dir *= dirR;
    len = len * 0.5;
    len *= len;
    float stretch = (dir.x * dir.x + dir.y * dir.y) / max(abs(dir.x), abs(dir.y));
    vec2 len2 = vec2(1.0 + (stretch - 1.0) * len, 1.0 - 0.5 * len);
    float lob = 0.5 + ((1.0 / 4.0 - 0.04) - 0.5) * len;
    float clp = 1.0 / lob;
    vec4 aC = vec4(0.0);
    float aW = 0.0;
    easu_tap(aC, aW, vec2(0.0, -1.0) - pp, dir, len2, lob, clp, bC);
    easu_tap(aC, aW, vec2(1.0, -1.0) - pp, dir, len2, lob, clp, cC);
    easu_tap(aC, aW, vec2(-1.0, 1.0) - pp, dir, len2, lob, clp, iC);
    easu_tap(aC, aW, vec2(0.0, 1.0) - pp, dir, len2, lob, clp, jC);
    easu_tap(aC, aW, vec2(0.0, 0.0) - pp, dir, len2, lob, clp, fC);
    easu_tap(aC, aW, vec2(-1.0, 0.0) - pp, dir, len2, lob, clp, eC);
    easu_tap(aC, aW, vec2(1.0, 1.0) - pp, dir, len2, lob, clp, kC);
    easu_tap(aC, aW, vec2(2.0, 1.0) - pp, dir, len2, lob, clp, lC);
    easu_tap(aC, aW, vec2(2.0, 0.0) - pp, dir, len2, lob, clp, hC);
    easu_tap(aC, aW, vec2(1.0, 0.0) - pp, dir, len2, lob, clp, gC);
    easu_tap(aC, aW, vec2(1.0, 2.0) - pp, dir, len2, lob, clp, oC);
    easu_tap(aC, aW, vec2(0.0, 2.0) - pp, dir, len2, lob, clp, nC);
    vec4 mn = min(min(fC, gC), min(jC, kC));
    vec4 mx = max(max(fC, gC), max(jC, kC));
    TDImageStoreOutput(0, ivec3(p, 0), min(mx, max(mn, aC / aW)));
}
