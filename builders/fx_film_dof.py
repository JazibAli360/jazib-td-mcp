# fx_film_dof - FX_film module 'dof' (FX3 L10 + L11; FX0 row 36): depth of field with bokeh shapes.
#   depth_sel (Select TOP): the depth map = the Depthtop par, else (Depthsource auto) DC_depth_cam's `depth` null
#             (R = nearness) when that COMP exists, else depth_none (1 x 1) and a procedural focus plane: plane
#             (tilted by Planeangle / Planetilt: ground near, horizon far), radial, or luma (bright = near).
#   af  (1 x 1, in place): the focus distance: manual (Focus), point (depth at Afx / Afy = autofocus), or bpm (rack
#       between Focus and Focus2 every Rackbeats beats); Racktime smooths every change (rack focus).
#   coc (half / full res, rgba16float): rgb = box mean, a = signed CoC in full-res px (negative = near):
#       clamp((|d - focus| - Range / 2) x 5.6 / Fstop) x Maxblur (x Nearscale in front).
#   gather (coc res): Gustafsson-style scatter-as-gather on a Vogel spiral (Taps): a sample counts where ITS CoC
#       reaches this pixel; farther samples cannot bleed over a sharper nearer pixel; radius = max(own CoC,
#       Nearreach x Maxblur) so near blur spreads over in-focus pixels. Aperture: disc / polygon (Blades, Bladerot),
#       Squeeze (anamorphic oval), Catseye (clipped toward the frame edge), Swirl (Petzval), Rim (soap bubble),
#       Boost (bright samples weigh more = bokeh balls).
#   hl  (tile res x 2, rgba32float): HIGHLIGHT SPRITES: the excess of bright texels over Spritethr (blurred ones only,
#       |CoC| > 1.5-3 texels) is taken OUT of coc's colour and summed per tile of T x T coc texels (T = 4..32, so a CoC
#       spans <= 3.5 tiles): energy rgb + CoC, centroid. The gather draws one aperture-shaped sprite per tile (exact
#       polygon edges: a 6 px light shows its blades, which a gather alone cannot, T-156 (3)).
#   fx  (full res): sharp in1 where the blur is < 0.5 px (exact), the gather elsewhere; Show coc / blend views.
# -> out_sel (Amount 0 = in1) -> out1. Maths: builders/fx_film_dof_logic.py. ASCII only.

MODULE = 'dof'

PAGES = [
    ('Focus', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Depthsource', 'Menu', 'auto', {'names': ['auto', 'top', 'plane', 'radial', 'luma'],
                                         'labels': ['Auto (Depth TOP, Depth camera COMP / DC_depth_cam, else plane)', 'Depth TOP',
                                                    'Focus plane', 'Radial', 'Luma (bright = near)']}),
        ('Depthtop', 'TOP', '', {'label': 'Depth TOP'}),
        # drop-in (28 Oct): the depth camera COMP (its `depth` TOP) for Auto; empty = the lab's DC_depth_cam when the
        # project has one, else the focus plane
        ('Depthop', 'COMP', '', {'label': 'Depth camera COMP (Auto: its depth)'}),
        ('Depthconv', 'Menu', 'nearness', {'names': ['nearness', 'distance'],
                                           'labels': ['Nearness (1 = near)', 'Distance (0 = near)']}),
        ('Depthnear', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Depth near'}),
        ('Depthfar', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Depth far'}),
        ('Focus', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Focus distance'}),
        ('Range', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'In-focus range'}),
        ('Fstop', 'Float', 2.8, {'min': 0.7, 'max': 22, 'label': 'f-stop'}),
        ('Maxblur', 'Float', 24.0, {'min': 0, 'max': 120, 'label': 'Max blur (px)'}),
        ('Nearscale', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Near blur scale'}),
        ('Nearreach', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Near blur reach'}),
        ('Planeangle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Plane angle (deg)'}),
        ('Planetilt', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Plane tilt'}),
        ('Planex', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Plane centre x'}),
        ('Planey', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Plane centre y'}),
        ('Show', 'Menu', 'image', {'names': ['image', 'coc', 'blend'],
                                   'labels': ['Image', 'CoC (red near, blue far)', 'Blur mask']}),
    ]),
    ('Bokeh', [
        ('Shape', 'Menu', 'disc', {'names': ['disc', 'polygon'], 'labels': ['Disc', 'Polygon (blades)']}),
        ('Blades', 'Int', 6, {'min': 3, 'max': 12, 'label': 'Blades'}),
        ('Bladerot', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Blade rotation (deg)'}),
        ('Squeeze', 'Float', 1.0, {'min': 0.2, 'max': 2, 'label': 'Squeeze (x, anamorphic < 1)'}),
        ('Catseye', 'Float', 0.0, {'min': 0, 'max': 1.5, 'label': "Cat's eye"}),
        ('Swirl', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Swirl (Petzval)'}),
        ('Rim', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Rim (soap bubble)'}),
        ('Boost', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Highlight boost'}),
        ('Boostthr', 'Float', 0.8, {'min': 0, 'max': 4, 'label': 'Boost threshold'}),
        ('Taps', 'Int', 32, {'min': 8, 'max': 64, 'label': 'Taps'}),
        ('Sprites', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Highlight sprites (share)'}),
        ('Spritethr', 'Float', 0.8, {'min': 0, 'max': 4, 'label': 'Sprite threshold'}),
        ('Quality', 'Menu', 'half', {'names': ['half', 'full'], 'labels': ['Half res gather', 'Full res']}),
    ]),
    ('Rack', [
        ('Focusmode', 'Menu', 'manual', {'names': ['manual', 'point', 'bpm'],
                                         'labels': ['Manual (Focus)', 'Autofocus point', 'Bpm rack (Focus <-> Focus2)']}),
        ('Afx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'AF point x'}),
        ('Afy', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'AF point y'}),
        ('Focus2', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Focus 2 (bpm rack)'}),
        ('Rackbeats', 'Float', 4.0, {'min': 0.25, 'max': 32, 'label': 'Rack every (beats)'}),
        ('Bpm', 'Float', 120.0, {'min': 40, 'max': 200, 'label': 'Bpm'}),
        ('Racktime', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Rack time (s)'}),
    ]),
]
PANEL_PAGES = ['Focus', 'Bokeh', 'Rack']

PRESETS = [
    (1, 'portrait f1.4', {'Amount': 1.0, 'Depthsource': 0, 'Focus': 0.45, 'Range': 0.06, 'Fstop': 1.4, 'Maxblur': 30.0,
                          'Shape': 0, 'Boost': 1.0, 'Rim': 0.0, 'Squeeze': 1.0, 'Catseye': 0.3, 'Focusmode': 0}),
    (2, 'hex night', {'Amount': 1.0, 'Focus': 0.2, 'Range': 0.02, 'Fstop': 2.0, 'Maxblur': 40.0, 'Shape': 1,
                      'Blades': 6, 'Bladerot': 15.0, 'Boost': 3.0, 'Boostthr': 0.7, 'Taps': 48}),
    (3, 'anamorphic oval', {'Amount': 1.0, 'Fstop': 2.0, 'Maxblur': 36.0, 'Shape': 0, 'Squeeze': 0.5,
                            'Catseye': 0.5, 'Boost': 2.0, 'Taps': 48}),
    (4, 'swirly helios', {'Amount': 1.0, 'Fstop': 2.0, 'Maxblur': 28.0, 'Shape': 1, 'Blades': 8, 'Swirl': 0.6,
                          'Catseye': 0.4, 'Rim': 0.3, 'Boost': 1.5}),
    (5, 'beat rack', {'Amount': 1.0, 'Focusmode': 2, 'Focus': 0.3, 'Focus2': 0.75, 'Rackbeats': 4.0, 'Racktime': 0.4,
                      'Fstop': 1.8, 'Maxblur': 30.0, 'Range': 0.04}),
]

DEPTH = """
// uZ0 source(0 tex 1 plane 2 radial 3 luma) conv(0 nearness 1 distance) near far | uZ1 angle(rad) tilt cx cy
float depthAt(vec2 uv) {                                    // fx_film_dof_logic map_depth / plane / radial
    int s = int(uZ0.x + 0.5);
    if (s == 0) { float r = texture(sTD2DInputs[1], uv).r; float d = uZ0.y < 0.5 ? 1.0 - r : r;
                  return (d - uZ0.z) / max(uZ0.w - uZ0.z, 1e-6); }
    if (s == 1) return 0.5 + uZ1.y * dot(uv - uZ1.zw, vec2(sin(uZ1.x), cos(uZ1.x)));
    vec2 isz = vec2(textureSize(sTD2DInputs[0], 0));
    if (s == 2) return 0.5 + uZ1.y * length((uv - uZ1.zw) * vec2(isz.x / isz.y, 1.0));
    return 1.0 - luma(texture(sTD2DInputs[0], uv).rgb);
}
"""

SPRITE_EX = """
// fx_film_dof_logic.sprite_excess: the share of a texel moved into highlight sprites (cc = signed CoC, full px)
vec3 spriteEx(vec3 col, float cc, float amt, float thr, float sc) {
    return amt * smoothstep(1.5, 3.0, abs(cc) / sc) * max(col - vec3(thr), vec3(0.0));
}
"""

AF = """// FX_film dof af (compute, 1 x 1, rgba32float in place): r = focus after this frame, g = before, b = stamp, a = dt.
// in0 = picture, in1 = depth. uF0 mode focus focus2 racktime | uF1 afx afy bpm-select stamp | uF2 cookrate - - -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uF0;
uniform vec4 uF1;
uniform vec4 uF2;
uniform vec4 uZ0;
uniform vec4 uZ1;
%s
%s
void main() {
    if (gl_GlobalInvocationID.x != 0u || gl_GlobalInvocationID.y != 0u) return;
    int md = int(uF0.x + 0.5);
    float tgt = md == 1 ? depthAt(uF1.xy) : (md == 2 && uF1.z > 0.5 ? uF0.z : uF0.y);
    vec4 o = TDImageLoadOutput(0, ivec3(0));
    float gap = mod(uF1.w - o.b + 2048.0, 2048.0);
    float before = gap < 0.5 ? o.g : (gap < 30.5 ? o.r : tgt);   // > 30 frames: dof was off (T-156)
    float dt = gap < 0.5 ? o.a : gap / max(uF2.x, 1.0);
    float after = before + (tgt - before) * (1.0 - exp(-dt / max(uF0.w, 1e-3)));
    TDImageStoreOutput(0, ivec3(0), vec4(after, before, uF1.w, dt));
}
"""

COC = """// FX_film dof coc (compute, rgba16float, 1/scale res): rgb = box mean of in0, a = signed CoC (full-res px).
// in0 = picture, in1 = depth, in2 = af. uQ0 scale k(5.6/fstop) maxblur nearscale | uQ1 range sprites spritethr -
// rgb loses the sprite excess (spriteEx at the 16F-rounded CoC, the value hl reads back) so energy is kept.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uQ0;
uniform vec4 uQ1;
uniform vec4 uZ0;
uniform vec4 uZ1;
%s
%s
%s
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= osz.x || p.y >= osz.y) return;
    vec2 isz = vec2(textureSize(sTD2DInputs[0], 0));
    int s = int(uQ0.x + 0.5);
    vec2 uv = (vec2(p) + 0.5) * float(s) / isz;
    vec3 col = s == 1 ? texelFetch(sTD2DInputs[0], p, 0).rgb : texture(sTD2DInputs[0], uv).rgb;
    float sd = depthAt(uv) - texelFetch(sTD2DInputs[2], ivec2(0), 0).r;
    float cc = clamp(sign(sd) * max(abs(sd) - 0.5 * uQ1.x, 0.0) * uQ0.y, -1.0, 1.0) * uQ0.z;
    if (sd < 0.0) cc *= uQ0.w;
    if (uQ1.y > 0.0) col -= spriteEx(col, unpackHalf2x16(packHalf2x16(vec2(cc, 0.0))).x, uQ1.y, uQ1.z, float(s));
    TDImageStoreOutput(0, ivec3(p, 0), vec4(col, cc));
}
"""

HL = """// FX_film dof hl (compute, rgba32float, 2 tw x th): highlight sprite tiles. in0 = coc, in1 = picture.
// Tile t = T x T coc texels. Texel (2 tx, ty) = (energy rgb, CoC mean full px); (2 tx + 1, ty) = (centroid in coc
// texels, weight, -). Two layouts, one shader (uniform branch on T; perf lane 3, 27 Oct: at the default T 4 the old
// one-workgroup-per-tile layout ran 48 of 64 threads idle + a 64-way serial sum per 16 texels, 0.6 ms GPU):
//   T <= 8: one THREAD per tile (sums its T x T texels in a loop; no shared memory, no barrier), 8 x 8 tiles per
//           workgroup (dispatch ceil(tw / 8) x ceil(th / 8));
//   T >= 16: one 8 x 8 WORKGROUP per tile: thread (x, y) sums texels (x + 8a, y + 8b), shared-memory sum, thread 0
//           writes both texels (dispatch tw x th). No early return before the barrier (T-154).
// uS0 sprites spritethr T scale
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS0;
shared vec4 sE[64];
shared vec4 sC[64];
%s
void addTexel(ivec2 q, ivec2 csz, vec2 isz, int s, inout vec4 E, inout vec4 C) {
    if (q.x >= csz.x || q.y >= csz.y) return;
    vec4 k = texelFetch(sTD2DInputs[0], q, 0);
    if (all(lessThan(k.rgb, vec3(uS0.y - 1e-3)))) return;          // coc keeps >= thr where it moved excess
    vec2 uv = (vec2(q) + 0.5) * float(s) / isz;
    vec3 col = s == 1 ? texelFetch(sTD2DInputs[1], q, 0).rgb : texture(sTD2DInputs[1], uv).rgb;
    vec3 e = spriteEx(col, k.a, uS0.x, uS0.y, float(s));
    float w = e.r + e.g + e.b;
    E += vec4(e, w);
    C += vec4(w * (vec2(q) + 0.5), w * k.a, 0.0);
}
void writeTile(ivec2 tl, vec4 E, vec4 C) {
    float W = E.a;
    TDImageStoreOutput(0, ivec3(2 * tl.x, tl.y, 0), vec4(E.rgb, W > 0.0 ? C.z / W : 0.0));
    TDImageStoreOutput(0, ivec3(2 * tl.x + 1, tl.y, 0), vec4(W > 0.0 ? C.xy / W : vec2(0.0), W, 0.0));
}
void main() {
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    ivec2 csz = textureSize(sTD2DInputs[0], 0);
    vec2 isz = vec2(textureSize(sTD2DInputs[1], 0));
    int T = int(uS0.z + 0.5), s = int(uS0.w + 0.5);
    if (T <= 8) {                                            // uniform branch: the whole dispatch takes it
        ivec2 tl = ivec2(gl_GlobalInvocationID.xy);
        if (2 * tl.x + 1 >= osz.x || tl.y >= osz.y) return;
        vec4 E = vec4(0.0), C = vec4(0.0);
        for (int b = 0; b < 8; b++) {
            if (b >= T) break;
            for (int a = 0; a < 8; a++) {
                if (a >= T) break;
                addTexel(tl * T + ivec2(a, b), csz, isz, s, E, C);
            }
        }
        writeTile(tl, E, C);
        return;
    }
    ivec2 tl = ivec2(gl_WorkGroupID.xy), l = ivec2(gl_LocalInvocationID.xy);
    int id = int(gl_LocalInvocationIndex);
    vec4 E = vec4(0.0), C = vec4(0.0);                       // E = (energy rgb, weight), C = (w x pos, w x coc, -)
    for (int b = 0; b < 4; b++) {
        for (int a = 0; a < 4; a++) {
            ivec2 o = l + 8 * ivec2(a, b);
            if (o.x >= T || o.y >= T) continue;
            addTexel(tl * T + o, csz, isz, s, E, C);
        }
    }
    sE[id] = E;
    sC[id] = C;
    memoryBarrierShared();
    barrier();
    if (id == 0 && 2 * tl.x + 1 < osz.x && tl.y < osz.y) {
        E = vec4(0.0); C = vec4(0.0);
        for (int k = 0; k < 64; k++) { E += sE[k]; C += sC[k]; }
        writeTile(tl, E, C);
    }
}
"""

GATHER = """// FX_film dof gather (compute, coc res). in0 = coc (rgb, signed CoC px). Scatter-as-gather on a Vogel spiral.
// Tap colour is read at mip lod log2(tap spacing) - 0.5 (in0 mipmapped): a small light then fills the disc instead of
// stamping the Vogel pattern (T-156); the CoC (alpha) is always read at lod 0.
// uG0 taps rmax(texels) scale shape | uG1 blades bladerot(rad) squeeze catseye | uG2 swirl rim boost boostthr
// uG3 nearreach sprites T - . in1 = hl (sprite tiles): each tile within reach adds its sprite: energy / area inside
// the aperture shape (same disc / polygon / squeeze / swirl / cat's eye / rim as the taps; soft 1-texel edge); a
// farther sprite does not cover a sharper nearer pixel beyond 2 x its CoC (the taps' rule). The workgroup first
// lists its non-empty tiles in shared memory (<= 12 x 12 tiles, 4.6 KB), so a pixel only visits lit tiles; main()
// never returns before the barrier (T-154).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uG0;
uniform vec4 uG1;
uniform vec4 uG2;
uniform vec4 uG3;
shared vec4 sA[144];
shared vec4 sB[144];
shared uint sN;
%s
float apert(vec2 o, float rad, vec2 dout, float rs, out float pr) {    // o = (sprite - pixel) / rad -> coverage
    float k = clamp(uG2.x * rs, 0.0, 0.95);                            // un-swirl, un-squeeze, then the polygon
    vec2 q = o + dout * dot(o, dout) * (1.0 / (1.0 - k) - 1.0);
    q.x /= uG1.z;
    float B = max(uG1.x, 3.0), seg = 6.2831853 / B;
    pr = length(q);
    if (uG0.w > 0.5) pr *= cos(mod(atan(q.y, q.x) - uG1.y, seg) - 3.14159265 / B) / cos(3.14159265 / B);
    float cv = clamp(0.5 - (pr - 1.0) * rad, 0.0, 1.0);
    if (uG1.w > 0.0) cv *= clamp(0.5 - (length(o + uG1.w * rs * dout) - 1.0) * rad, 0.0, 1.0);
    return cv;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    int T = int(uG3.z + 0.5);
    if (uG3.y > 0.0) {                                       // uniform branch: every thread reaches the barriers
        if (gl_LocalInvocationIndex == 0u) sN = 0u;
        memoryBarrierShared();
        barrier();
        ivec2 hsz = textureSize(sTD2DInputs[1], 0);
        ivec2 w0 = ivec2(gl_WorkGroupID.xy) * 8;
        ivec2 t0 = w0 / T - 4, tn = (w0 + 7) / T + 4 - t0 + 1;
        for (int k = 0; k < 3; k++) {
            int id = int(gl_LocalInvocationIndex) + 64 * k;
            if (id >= tn.x * tn.y) break;
            ivec2 t = t0 + ivec2(id %% tn.x, id / tn.x);
            if (t.x < 0 || t.y < 0 || 2 * t.x + 1 >= hsz.x || t.y >= hsz.y) continue;
            vec4 A = texelFetch(sTD2DInputs[1], ivec2(2 * t.x, t.y), 0);
            if (A.r + A.g + A.b <= 0.0) continue;
            uint j = atomicAdd(sN, 1u);
            sA[j] = A;
            sB[j] = texelFetch(sTD2DInputs[1], ivec2(2 * t.x + 1, t.y), 0);
        }
        memoryBarrierShared();
        barrier();
    }
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    float sc = uG0.z, cC = c.a / sc, aC = abs(cC);
    float R = max(aC, uG0.y * uG3.x);
    if (R < 0.5) { TDImageStoreOutput(0, ivec3(p, 0), vec4(c.rgb, abs(c.a))); return; }
    vec2 sz = vec2(isz), P = vec2(p) + 0.5;
    vec2 rel = (P / sz - 0.5) * 2.0;
    float rs = length(rel) * 0.70710678;
    vec2 dout = length(rel) > 1e-4 ? normalize(rel) : vec2(0.0);
    int N = int(uG0.x + 0.5);
    float B = max(uG1.x, 3.0), seg = 6.2831853 / B;
    float lod = max(log2(R * sqrt(3.14159265 / float(max(N, 1)))) - 0.5, 0.0);
    vec3 acc = textureLod(sTD2DInputs[0], P / sz, lod).rgb;   // own tap at the same lod (no sharp core)
    float tot = 1.0, bl = aC;
    for (int k = 0; k < 64; k++) {
        if (k >= N) break;
        float rho = sqrt((float(k) + 0.5) / float(N)), th = float(k) * 2.39996323;
        vec2 o = rho * vec2(cos(th), sin(th));
        if (uG0.w > 0.5) o *= cos(3.14159265 / B) / cos(mod(th - uG1.y, seg) - 3.14159265 / B);
        o.x *= uG1.z;
        float ro = dot(o, dout);
        o += dout * ro * (-uG2.x * rs);
        if (uG1.w > 0.0 && length(o + uG1.w * rs * dout) > 1.0) continue;
        float r = rho * R;
        vec2 tuv = (P + o * R) / sz;
        vec4 s = vec4(textureLod(sTD2DInputs[0], tuv, lod).rgb, textureLod(sTD2DInputs[0], tuv, 0.0).a);
        float cs = s.a / sc, as_ = abs(cs);
        if (cs > cC) as_ = min(as_, 2.0 * aC);
        float m = smoothstep(r - 0.5, r + 0.5, as_);
        float w = (1.0 + uG2.z * max(luma(s.rgb) - uG2.w, 0.0)) * mix(1.0, 2.0 * rho * rho, uG2.y);
        acc += w * mix(acc / tot, s.rgb, m);
        tot += w;
        if (cs < cC) bl = max(bl, m * as_);
    }
    vec3 col = acc / tot;
    if (uG3.y > 0.0) {
        float area = (uG0.w > 0.5 ? 0.5 * B * sin(6.2831853 / B) : 3.14159265) * uG1.z
                   * (1.0 - clamp(uG2.x * rs, 0.0, 0.95));
        int n = int(sN);
        for (int i = 0; i < 144; i++) {
            if (i >= n) break;
            vec4 A = sA[i];
            vec2 L = sB[i].xy;
            float cs = A.a / sc, rad = min(max(abs(cs), 0.5), 3.5 * float(T));
            float dl = length(L - P);
            if (dl > rad + 1.0 || (cs > cC && dl > 2.0 * aC + 0.5)) continue;
            float pr;
            float cv = apert((L - P) / rad, rad, dout, rs, pr);
            if (cv <= 0.0) continue;
            col += A.rgb * cv * mix(1.0, 2.0 * pr * pr, uG2.y) / (area * rad * rad);
            if (cs < cC) bl = max(bl, cv * rad);
        }
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(col, bl * sc));
}
"""

FX = """// FX_film dof fx (compute, in0 format). in0 = picture, in1 = gather (rgb, blur px), in2 = coc.
// uC0 amount show maxblur -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uC0;
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uC0.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }
    vec2 uv = (vec2(p) + 0.5) / vec2(isz);
    vec4 g = texture(sTD2DInputs[1], uv);
    float t = g.a < 0.5 ? 0.0 : smoothstep(0.5, 1.5, g.a);
    vec3 o = mix(c.rgb, g.rgb, t);
    int sh = int(uC0.y + 0.5);
    if (sh == 1) { float cc = texture(sTD2DInputs[2], uv).a / max(uC0.z, 1e-3); o = vec3(max(-cc, 0.0), 0.0, max(cc, 0.0)); }
    if (sh == 2) o = vec3(t);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(mix(c.rgb, o, uC0.x), c.a));
}
"""

Q = "parent().par.{}.eval()"
# Auto depth: Depthop's `depth` TOP, else the lab DC_depth_cam (missing-safe). getattr: a module built before Depthop
# existed still evaluates (drop-in, 28 Oct).
DCP = ("(lambda q: (lambda d: (d.op('depth') if d is not None else None) or op('/project1/lab/DC_depth_cam/depth'))"
       "(q.eval() if q is not None else None))(getattr(parent().par, 'Depthop', None))")
# the first 28 Oct form: an EMPTY Par is falsy, so `getattr(...) and ...` handed the Par itself to the lambda
BROKEN_DCP = ("(lambda d: (d.op('depth') if d is not None else None) or op('/project1/lab/DC_depth_cam/depth'))"
              "(getattr(parent().par, 'Depthop', None) and parent().par.Depthop.eval())")
HAVE = ("(1 if parent().par.Depthsource.eval() in ('auto', 'top') and (parent().par.Depthtop.eval() is not None or "
        "(parent().par.Depthsource.eval() == 'auto' and %s is not None)) else 0)" % DCP)
DEPTH_PATH = ("(lambda t, a: t.path if t is not None else (a.path if a is not None and "
              "parent().par.Depthsource.eval() == 'auto' else parent().op('depth_none').path))"
              "(parent().par.Depthtop.eval(), %s)" % DCP)
SRC = ("(0 if %s else (2 if parent().par.Depthsource.eval() == 'radial' else "
       "(3 if parent().par.Depthsource.eval() == 'luma' else 1)))" % HAVE)
SCALE = "(1 if parent().par.Quality.eval() == 'full' else 2)"
RMAX = "%s * max(%s, 1.0) / %s" % (Q.format('Maxblur'), Q.format('Nearscale'), SCALE)
TILE = ("(lambda r: int(min(32, max(4, 2 ** math.ceil(math.log2(max(r, 1e-3) / 3.5))))))(%s)" % RMAX)  # dof_logic
# hl dispatch (tiles along one axis = ceil(n / T)): one workgroup per tile for T >= 16, one per 8 x 8 tiles for T <= 8
HLDISP = "(lambda nt, T: nt if T >= 16 else (nt + 7) // 8)(int(math.ceil(%s / %s)), %s)"
BEATSEL = "(1 if int(absTime.seconds * %s / 60.0 / max(%s, 1e-3)) %% 2 else 0)" % (Q.format('Bpm'), Q.format('Rackbeats'))
STAMP = 'absTime.frame % 2048'


def _zu(P):
    return [('uZ0', [SRC, 'parent().par.Depthconv.menuIndex', P.format('Depthnear'), P.format('Depthfar')]),
            ('uZ1', ['math.radians(%s)' % P.format('Planeangle'), P.format('Planetilt'), P.format('Planex'),
                     P.format('Planey')])]


def shaders(H):
    return {'af': AF % (H['LIB'], DEPTH), 'coc': COC % (H['LIB'], DEPTH, SPRITE_EX), 'hl': HL % SPRITE_EX,
            'gather': GATHER % H['LIB'], 'fx': FX}


def build(m, H):
    """in1 + depth_sel -> af (focus state) -> coc -> gather -> fx (composite) -> out_sel -> out1."""
    mk, P = H['mk'], H['P']
    sh = shaders(H)
    in1 = mk(m, inTOP, 'in1')
    dn = mk(m, constantTOP, 'depth_none')
    dn.par.outputresolution = 'custom'
    dn.par.resolutionw, dn.par.resolutionh = 1, 1
    dn.comment = 'No depth map: 1 x 1 placeholder (the focus plane / radial / luma source is procedural).'
    ds = mk(m, selectTOP, 'depth_sel')
    H['expr'](ds.par.top, DEPTH_PATH)
    ds.comment = 'Depth: Depthtop, else DC_depth_cam/depth (auto), else depth_none.'
    af = H['compute'](m, 'af', sh['af'], [in1, ds], res=(1, 1), fmt='rgba32float')
    af.par.outputaccess = 'readwrite'
    af.par.clearoutputs = False
    H['uniforms'](af, [
        ('uF0', ['parent().par.Focusmode.menuIndex', P.format('Focus'), P.format('Focus2'), P.format('Racktime')]),
        ('uF1', [P.format('Afx'), P.format('Afy'), BEATSEL, STAMP]),
        ('uF2', ['project.cookRate', '0', '0', '0']),
    ] + _zu(P))
    af.comment = 'af: focus distance (manual / AF point / bpm rack), smoothed by Racktime; in place, stamped.'
    coc = H['compute'](m, 'coc', sh['coc'], [in1, ds, af],
                       res=('int(math.ceil(me.inputs[0].width / %s))' % SCALE,
                            'int(math.ceil(me.inputs[0].height / %s))' % SCALE), fmt='rgba16float')
    H['uniforms'](coc, [
        ('uQ0', [SCALE, '5.6 / max(%s, 0.1)' % P.format('Fstop'), P.format('Maxblur'), P.format('Nearscale')]),
        ('uQ1', [P.format('Range'), P.format('Sprites'), P.format('Spritethr'), '0']),
    ] + _zu(P))
    coc.comment = 'coc: box mean + signed CoC px from the depth source and the af focus.'
    hl = H['compute'](m, 'hl', sh['hl'], [coc, in1],
                      res=('2 * int(math.ceil(me.inputs[0].width / %s))' % TILE,
                           'int(math.ceil(me.inputs[0].height / %s))' % TILE), fmt='rgba32float',
                      dispatch=(HLDISP % ('me.inputs[0].width', TILE, TILE), HLDISP % ('me.inputs[0].height', TILE, TILE)))
    H['uniforms'](hl, [('uS0', [P.format('Sprites'), P.format('Spritethr'), TILE, SCALE])])
    hl.comment = 'hl: highlight sprite tiles (excess over Spritethr per T x T tile: energy, CoC, centroid).'
    ga = H['compute'](m, 'gather', sh['gather'], [coc, hl], fmt='rgba16float', filt='mipmap')
    H['uniforms'](ga, [
        ('uG0', [P.format('Taps'), RMAX, SCALE, 'parent().par.Shape.menuIndex']),
        ('uG1', [P.format('Blades'), 'math.radians(%s)' % P.format('Bladerot'), P.format('Squeeze'),
                 P.format('Catseye')]),
        ('uG2', [P.format('Swirl'), P.format('Rim'), P.format('Boost'), P.format('Boostthr')]),
        ('uG3', [P.format('Nearreach'), P.format('Sprites'), TILE, '0']),
    ])
    ga.comment = 'gather: bokeh scatter-as-gather (Vogel taps, aperture shape, near over far) + highlight sprites.'
    g = H['compute'](m, 'fx', sh['fx'], [in1, ga, coc])
    H['uniforms'](g, [('uC0', [P.format('Amount'), 'parent().par.Show.menuIndex', P.format('Maxblur'), '0'])])
    g.comment = 'fx: sharp where blur < 0.5 px (exact), the gather elsewhere; Show coc / blend views.'
    sel = H['outsel'](m, in1, g)
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In + depth', 'role': 'input', 'ops': ['in1', 'depth_none', 'depth_sel'],
         'body': 'Depth TOP / DC_depth_cam / procedural plane (Depthsource).'},
        {'title': '2 Focus + CoC', 'role': 'process', 'ops': ['af', 'af_compute', 'coc', 'coc_compute'],
         'body': 'af: focus state (rack, AF point, bpm). coc: signed circle of confusion per texel.'},
        {'title': '3 Bokeh', 'role': 'process', 'ops': ['hl', 'hl_compute', 'gather', 'gather_compute', 'fx',
                                                        'fx_compute'],
         'body': 'hl: highlight sprite tiles. Vogel gather + sprites with aperture shape; composite: sharp where blur < 0.5 px.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


OLD_DCP = "op('/project1/lab/DC_depth_cam/depth')"


def depthop_upgrade(rack):
    """Existing FX_film (main / a library copy), no rebuild (drop-in, 28 Oct): every dof module gets the Depthop COMP
    par (Focus page, empty) and its expressions read the depth camera through it (DCP: Depthop's depth, else the lab
    DC_depth_cam). Idempotent; -> [(module, what)]."""
    out = []
    for ds in rack.findChildren(name='depth_sel', maxDepth=2):
        m = ds.parent()
        if getattr(m.par, 'Depthop', None) is None:
            pg = next((p for p in m.customPages if p.name == 'Focus'), None) or m.appendCustomPage('Focus')
            pg.appendCOMP('Depthop', label='Depth camera COMP (Auto: its depth)')
            out.append((m.name, 'Depthop'))
        for o in [m] + list(m.children):
            for p in o.pars():
                e = p.expr or '' if p.mode == ParMode.EXPRESSION else ''
                if BROKEN_DCP in e:
                    p.expr = e.replace(BROKEN_DCP, DCP)
                    out.append((m.name, '%s.%s' % (o.name, p.name)))
                elif OLD_DCP in e and 'Depthop' not in e:
                    p.expr = e.replace(OLD_DCP, DCP)
                    out.append((m.name, '%s.%s' % (o.name, p.name)))
    return out

