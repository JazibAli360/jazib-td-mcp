// GEN_clone `clones` (compute GLSL TOP, rgba32float, T-47): one clone per 5 texels, CW clones per row.
// Clone i -> texels (5 * (i % CW) + k, i / CW), k = 0 pos.xyz + uniform scale, 1 orientation quaternion (w x y z),
// 2 colour rgba (straight), 3 scale xyz + time offset (frames), 4 effector weight, index, hidden, 0.
// Layout (Mode): 0 grid, 1 radial, 2 linear, 3 path, 4 points (in0 = point texture, rgb = xyz), 5 random.
// Then modifiers (step / random / noise, all by clone index), then the shared effectors (/project1/effectors,
// adapter prefix in front of this text: pxeConsumerW / pxeGrad), then the colour / scale map (in1).
// Mirror: builders/gen_clone_logic.py (clone_ref). Every loop is bounded (T-35). ASCII only.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uC0;   // mode, count N, CW, seed
uniform vec4 uC1;   // countx, county, countz, centre (linear: 1 = centred on the origin)
uniform vec4 uC2;   // spacex, spacey, spacez, radius
uniform vec4 uC3;   // arc start deg, arc end deg, plane (0 xy 1 xz 2 yz), align (0 off 1 on)
uniform vec4 uC4;   // linear offset xyz, path shape (0 circle 1 line 2 lissajous 3 spiral 4 helix 5 points)
uniform vec4 uC5;   // path size, turns, start, end
uniform vec4 uC6;   // path phase (speed x time), helix height, point step, align axis (0 x 1 y 2 z)
uniform vec4 uC7;   // random box xyz, time s
uniform vec4 uM0;   // step rot xyz deg, step scale
uniform vec4 uM1;   // step hue, random hue, random scale, noise scale
uniform vec4 uM2;   // random pos xyz, noise freq
uniform vec4 uM3;   // random rot xyz deg, noise speed
uniform vec4 uM4;   // noise pos, noise rot deg, time offset (frames per step), time mode (0 index 1 random 2 distance)
uniform vec4 uM5;   // colour rgb, alpha
uniform vec4 uM6;   // size, map mode (0 off 1 colour 2 scale 3 both), map amount, map size (world units across)
uniform vec4 uM7;   // scale xyz (per axis), 0
uniform vec4 uEffA; // effector offset xyz, push (along the effector gradient)
uniform vec4 uEffB; // effector rot xyz deg, scale (x 1 + s w)
uniform vec4 uEffC; // effector colour rgb, colour mix
uniform vec4 uEffD; // effector time (frames x w), hide at weight (0 = off), 0, 0

const float PI = 3.14159265358979;

uint gcPcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                     return (w >> 22u) ^ w; }
float gcH(uint i, uint k) { return float(gcPcg(i * 1664525u ^ gcPcg(k)) >> 8) * (1.0 / 16777216.0); }
float gcLat(ivec3 c, uint k) { return gcH(uint(c.x + 4096) * 73856093u ^ uint(c.y + 4096) * 19349663u ^
                                          uint(c.z + 4096) * 83492791u, k); }
float gcNoise(vec3 p, uint k) {          // value noise 0..1, smooth trilinear
    vec3 f = floor(p), t = p - f;
    t = t * t * (3.0 - 2.0 * t);
    ivec3 c = ivec3(f);
    float a = mix(gcLat(c, k), gcLat(c + ivec3(1, 0, 0), k), t.x);
    float b = mix(gcLat(c + ivec3(0, 1, 0), k), gcLat(c + ivec3(1, 1, 0), k), t.x);
    float d = mix(gcLat(c + ivec3(0, 0, 1), k), gcLat(c + ivec3(1, 0, 1), k), t.x);
    float e = mix(gcLat(c + ivec3(0, 1, 1), k), gcLat(c + ivec3(1, 1, 1), k), t.x);
    return mix(mix(a, b, t.y), mix(d, e, t.y), t.z);
}
vec4 gcQMul(vec4 a, vec4 b) {             // (w, x, y z)
    return vec4(a.x * b.x - dot(a.yzw, b.yzw), a.x * b.yzw + b.x * a.yzw + cross(a.yzw, b.yzw));
}
vec4 gcQAxis(vec3 ax, float deg) { float h = radians(deg) * 0.5; return vec4(cos(h), ax * sin(h)); }
vec4 gcQEuler(vec3 d) {                   // X first, then Y, then Z (q = qz qy qx)
    return gcQMul(gcQAxis(vec3(0.0, 0.0, 1.0), d.z), gcQMul(gcQAxis(vec3(0.0, 1.0, 0.0), d.y),
                                                           gcQAxis(vec3(1.0, 0.0, 0.0), d.x)));
}
vec4 gcQFromTo(vec3 a, vec3 b) {          // shortest rotation a -> b (unit vectors)
    float c = dot(a, b);
    if (c < -0.99999) {
        vec3 o = abs(a.x) < 0.9 ? cross(a, vec3(1.0, 0.0, 0.0)) : cross(a, vec3(0.0, 1.0, 0.0));
        return vec4(0.0, normalize(o));
    }
    vec4 q = vec4(1.0 + c, cross(a, b));
    return q / length(q);
}
vec3 gcPlane(vec2 v, int plane) { return plane == 1 ? vec3(v.x, 0.0, v.y) : (plane == 2 ? vec3(0.0, v.x, v.y)
                                                                                         : vec3(v, 0.0)); }
vec3 gcHue(vec3 c, float turns) {         // rotate hue around the grey axis (Rodrigues)
    float a = turns * 2.0 * PI;
    vec3 k = vec3(0.57735026919);
    return c * cos(a) + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - cos(a));
}
vec3 gcPts(float f, int npts) {           // point / path sample f (0..npts-1), linear between samples
    ivec2 sz = textureSize(sTD2DInputs[0], 0);
    int a = clamp(int(floor(f)), 0, max(npts - 1, 0));
    int b = min(a + 1, max(npts - 1, 0));
    vec3 pa = texelFetch(sTD2DInputs[0], ivec2(a % sz.x, a / sz.x), 0).rgb;
    vec3 pb = texelFetch(sTD2DInputs[0], ivec2(b % sz.x, b / sz.x), 0).rgb;
    return mix(pa, pb, f - float(a));
}
vec3 gcPath(float t, int shape, int npts) {
    float r = uC5.x, turns = max(uC5.y, 0.0);
    int plane = int(round(uC3.z));
    if (shape == 1) return gcPlane(vec2((t - 0.5) * r * 2.0, 0.0), plane);
    if (shape == 2) return gcPlane(r * vec2(sin(2.0 * PI * 3.0 * t + 0.5 * PI), sin(2.0 * PI * 2.0 * t)), plane);
    if (shape == 3) { float a = 2.0 * PI * turns * t; return gcPlane(r * t * vec2(cos(a), sin(a)), plane); }
    if (shape == 4) { float a = 2.0 * PI * turns * t;
                      return vec3(r * cos(a), (t - 0.5) * uC6.y, r * sin(a)); }
    if (shape == 5) return gcPts(fract(t) * float(max(npts - 1, 0)), npts);
    float a = 2.0 * PI * t;
    return gcPlane(r * vec2(cos(a), sin(a)), plane);
}

// base position + the direction "align" points the align axis at (0 = none)
void gcLayout(int i, int n, float tsec, out vec3 pos, out vec3 dir) {
    int mode = int(round(uC0.x));
    dir = vec3(0.0);
    if (mode == 0) {
        ivec3 c = max(ivec3(round(uC1.xyz)), ivec3(1));
        ivec3 g = ivec3(i % c.x, (i / c.x) % c.y, i / (c.x * c.y));
        pos = (vec3(g) - 0.5 * vec3(c - 1)) * uC2.xyz;
        dir = normalize(pos + vec3(1e-6, 0.0, 0.0));
    } else if (mode == 1) {
        float span = uC3.y - uC3.x;
        float f = abs(span) >= 359.999 ? float(i) / float(max(n, 1)) : float(i) / float(max(n - 1, 1));
        float a = radians(uC3.x + span * f);
        vec3 o = gcPlane(vec2(cos(a), sin(a)), int(round(uC3.z)));
        pos = o * uC2.w;
        dir = o;
    } else if (mode == 2) {
        float k = float(i) - (uC1.w > 0.5 ? 0.5 * float(n - 1) : 0.0);
        pos = uC4.xyz * k;
        dir = length(uC4.xyz) > 0.0 ? normalize(uC4.xyz) : vec3(0.0);
    } else if (mode == 3) {
        int shape = int(round(uC4.w));
        int npts = textureSize(sTD2DInputs[0], 0).x * textureSize(sTD2DInputs[0], 0).y;
        float f = n > 1 ? float(i) / float(n - 1) : 0.0;
        float t = uC5.z + (uC5.w - uC5.z) * f + uC6.x;
        if (shape == 0 || shape == 2) t = fract(t);
        pos = gcPath(t, shape, npts);
        vec3 d = gcPath(t + 1e-3, shape, npts) - gcPath(t - 1e-3, shape, npts);
        dir = length(d) > 1e-9 ? normalize(d) : vec3(0.0);
    } else if (mode == 4) {
        int npts = textureSize(sTD2DInputs[0], 0).x * textureSize(sTD2DInputs[0], 0).y;
        int step = max(int(round(uC6.z)), 1);
        pos = gcPts(float(min(i * step, max(npts - 1, 0))), npts);
        dir = length(pos) > 1e-9 ? normalize(pos) : vec3(0.0);
    } else {
        uint s = uint(uC0.w) * 7919u;
        pos = (vec3(gcH(uint(i), s + 1u), gcH(uint(i), s + 2u), gcH(uint(i), s + 3u)) - 0.5) * uC7.xyz;
        dir = length(pos) > 1e-9 ? normalize(pos) : vec3(0.0);
    }
}

void main() {
    ivec2 T = ivec2(gl_GlobalInvocationID.xy);
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    if (T.x >= R.x || T.y >= R.y || T.x % 5 != 0) return;
    int cw = max(int(round(uC0.z)), 1);
    int i = T.y * cw + T.x / 5;
    int n = int(round(uC0.y));
    if (i >= n) {
        for (int k = 0; k < 5; k++) TDImageStoreOutput(0, ivec3(T.x + k, T.y, 0), vec4(0.0));
        return;
    }
    float fi = float(i);
    uint seed = uint(uC0.w) * 7919u;
    // time offset (frames) by index / random / distance; drives the modifier animation time and the card ring
    int tmode = int(round(uM4.w));
    vec3 p0, dir;
    gcLayout(i, n, uC7.w, p0, dir);
    float toff = tmode == 1 ? gcH(uint(i), seed + 11u) * uM4.z * float(n) : (tmode == 2 ? length(p0) * uM4.z
                                                                                       : fi * uM4.z);
    float tl = uC7.w - toff / 60.0;
    // modifiers: step, random, noise
    vec3 rot = uM0.xyz * fi;
    float us = uM6.x * max(1.0 + uM0.w * fi, 0.0);
    float hue = uM1.x * fi;
    vec3 hr = vec3(gcH(uint(i), seed + 4u), gcH(uint(i), seed + 5u), gcH(uint(i), seed + 6u)) - 0.5;
    vec3 hq = vec3(gcH(uint(i), seed + 7u), gcH(uint(i), seed + 8u), gcH(uint(i), seed + 9u)) - 0.5;
    float hs = gcH(uint(i), seed + 10u) - 0.5;
    vec3 pos = p0 + 2.0 * hr * uM2.xyz;
    rot += 2.0 * hq * uM3.xyz;
    us *= max(1.0 + 2.0 * hs * uM1.z, 0.0);
    hue += hs * uM1.y;
    if (uM4.x != 0.0 || uM4.y != 0.0 || uM1.w != 0.0) {
        vec3 np = p0 * uM2.w + vec3(0.0, 0.0, tl * uM3.w);
        vec3 nv = vec3(gcNoise(np, seed + 21u), gcNoise(np, seed + 22u), gcNoise(np, seed + 23u)) - 0.5;
        pos += 2.0 * nv * uM4.x;
        rot += 2.0 * nv * uM4.y;
        us *= max(1.0 + 2.0 * nv.x * uM1.w, 0.0);
    }
    vec3 sc = uM7.xyz;
    vec4 col = vec4(gcHue(uM5.rgb, hue), uM5.a);
    // effectors (/project1/effectors): weight at the clone's position
    float w = 0.0;
#ifdef PXE_ROWS
    int b;
    w = pxeConsumerW(pos, b);
    if (w > 0.0) {
        vec3 g = b >= 0 ? pxeGrad(b, pos) : vec3(0.0);
        pos += w * (uEffA.xyz + g * uEffA.w);
        rot += w * uEffB.xyz;
        us *= max(1.0 + uEffB.w * w, 0.0);
        col.rgb = mix(col.rgb, uEffC.rgb, clamp(w * uEffC.a, 0.0, 1.0));
        toff += w * uEffD.x;
    }
#endif
    // colour / scale map (in1) at the clone's base position: uv = p0.xy / map size + 0.5
    int mm = int(round(uM6.y));
    if (mm > 0 && uM6.z != 0.0) {
        vec4 m = texture(sTD2DInputs[1], p0.xy / max(uM6.w, 1e-6) + 0.5);
        if (mm == 1 || mm == 3) col.rgb = mix(col.rgb, col.rgb * m.rgb, clamp(uM6.z, 0.0, 1.0));
        if (mm == 2 || mm == 3) us *= max(1.0 + uM6.z * (dot(m.rgb, vec3(0.2126, 0.7152, 0.0722)) - 1.0), 0.0);
    }
    float hidden = (uEffD.y > 0.0 && w >= uEffD.y) ? 1.0 : 0.0;
    if (hidden > 0.5) us = 0.0;
    vec4 q = gcQEuler(rot);
    if (uC3.w > 0.5 && dot(dir, dir) > 0.0) {
        int ax = int(round(uC6.w));
        vec3 a = ax == 0 ? vec3(1.0, 0.0, 0.0) : (ax == 2 ? vec3(0.0, 0.0, 1.0) : vec3(0.0, 1.0, 0.0));
        q = gcQMul(gcQFromTo(a, normalize(dir)), q);
    }
    TDImageStoreOutput(0, ivec3(T.x, T.y, 0), vec4(pos, us));
    TDImageStoreOutput(0, ivec3(T.x + 1, T.y, 0), q);
    TDImageStoreOutput(0, ivec3(T.x + 2, T.y, 0), clamp(col, 0.0, 1.0));
    TDImageStoreOutput(0, ivec3(T.x + 3, T.y, 0), vec4(sc, max(toff, 0.0)));
    TDImageStoreOutput(0, ivec3(T.x + 4, T.y, 0), vec4(w, fi, hidden, 0.0));
}
