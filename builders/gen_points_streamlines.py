# gen_points_streamlines - GEN_points module 'streamlines' (FX5 G01): flow-field agents. Each point moves through a 2D
# field (RK2 midpoint) for its life (Life x 0.5..1.5), then respawns; Persist turns the dots into silk / hair lines.
# Fields: curl noise (PX's analytic curl, z slice), angle noise (Tyler Hobbs style, Turns), snapped angle (circuit),
# input-picture contours / gradient (slot input luma), vortex + sink, rain; Turbulence adds curl to any field. Spawn:
# anywhere / left edge / centre disc / bright input pixels. Shared effectors: push / vortex / wake / kill / spawn
# (BO_particles adapter, Effon default off). Mirror: gen_points_logic.streamlines_*. ASCII only.
MODULE = 'streamlines'
KIND = '2d'
BLURB = 'Agents ride a 2D field (curl / angle / circuit / picture / vortex / rain) for a life, then respawn.'
FIELDS = ['curl', 'angle', 'circuit', 'contours', 'gradient', 'vortex', 'rain']
SPAWNS = ['anywhere', 'leftedge', 'centre', 'image']
COLORBY = ['direction', 'age', 'xpos', 'index']
EFFECTORS = 'particles'
EPOCH = '0'
W_IS_ANGLE = True        # state w = the motion angle (colour coordinate; live check compares it wrapped)

PAGES = [('Flow', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Field', 'Menu', 'curl', {'names': FIELDS, 'labels': ['Curl noise', 'Angle noise', 'Circuit (snapped angle)',
                                                          'Picture contours', 'Picture gradient', 'Vortex + sink',
                                                          'Rain']}),
    ('Freq', 'Float', 1.5, {'min': 0.05, 'max': 16, 'label': 'Field frequency (per world unit)'}),
    ('Octaves', 'Int', 2, {'min': 1, 'max': 4, 'label': 'Octaves'}),
    ('Evolve', 'Float', 0.1, {'min': 0, 'max': 4, 'label': 'Field evolve speed'}),
    ('Flow', 'Float', 0.25, {'min': 0, 'max': 4, 'label': 'Flow speed (world units/s)'}),
    ('Life', 'Float', 4.0, {'min': 0.1, 'max': 30, 'label': 'Life s (x 0.5..1.5)'}),
    ('Turns', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Angle turns (angle fields)'}),
    ('Snap', 'Int', 4, {'min': 1, 'max': 16, 'label': 'Circuit directions'}),
    ('Turbulence', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Turbulence (curl added)'}),
    ('Imagegain', 'Float', 20.0, {'min': 0, 'max': 200, 'label': 'Picture field gain'}),
    ('Swirl', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Vortex swirl'}),
    ('Sink', 'Float', 0.2, {'min': -4, 'max': 4, 'label': 'Vortex sink'}),
    ('Spawn', 'Menu', 'anywhere', {'names': SPAWNS, 'labels': ['Anywhere', 'Left edge', 'Centre disc',
                                                              'Bright input pixels']}),
    ('Edge', 'Menu', 'respawn', {'names': ['respawn', 'wrap'], 'labels': ['Respawn when out', 'Wrap']}),
    ('Fade', 'Float', 0.15, {'min': 0, 'max': 0.5, 'label': 'Fade in/out (share of life)'}),
    ('Colorby', 'Menu', 'direction', {'names': COLORBY, 'labels': ['Direction', 'Age', 'x position', 'Index']}),
])]
DEFAULTS = {'Count': 32768, 'Persist': 0.95, 'Tonemap': 0, 'Palette': 0, 'Intensity': 1.0}
PANEL_PAGES = ['Flow', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'silk', {'Field': 0, 'Freq': 1.2, 'Octaves': 2, 'Flow': 0.2, 'Life': 5.0, 'Persist': 0.96, 'Palette': 0,
                 'Colorby': 0, 'Count': 32768, 'Exposure': -1.0}),
    (2, 'hair', {'Field': 1, 'Freq': 0.8, 'Turns': 1.5, 'Flow': 0.3, 'Life': 3.0, 'Persist': 0.97, 'Palette': 5,
                 'Colorby': 1, 'Count': 32768, 'Exposure': -1.5}),
    (3, 'circuit', {'Field': 2, 'Freq': 1.0, 'Turns': 2.0, 'Snap': 4, 'Flow': 0.4, 'Life': 2.0, 'Persist': 0.93,
                    'Palette': 6, 'Colorby': 0, 'Count': 32768}),
    (4, 'vortex', {'Field': 5, 'Swirl': 1.0, 'Sink': 0.3, 'Turbulence': 0.6, 'Flow': 0.3, 'Life': 4.0,
                   'Persist': 0.95, 'Palette': 3, 'Colorby': 2, 'Count': 32768}),
    (5, 'rain', {'Field': 6, 'Turbulence': 0.5, 'Freq': 2.0, 'Flow': 0.6, 'Life': 3.0, 'Persist': 0.9,
                 'Palette': 4, 'Colorby': 3, 'Count': 32768, 'Spawn': 0}),
]
UNIFORMS = [('uM0', ['{Field#}', '{Freq}', '{Octaves}', '{Evolve}']),
            ('uM1', ['{Flow}', '{Life}', '{Turns}', '{Snap}']),
            ('uM2', ['{Spawn#}', '{Edge#}', '{Colorby#}', '{Turbulence}']),
            ('uM3', ['{Imagegain}', '{Swirl}', '{Sink}', '{Fade}'])]

STEP = """
float sl_lum(vec2 uv) { return lum(texture(GP_IN, uv).rgb); }
vec2 sl_field(vec2 p) {
    int f = int(uM0.x + 0.5);
    float fr = uM0.y;
    int oct = clamp(int(uM0.z + 0.5), 1, 4);
    float te = T * uM0.w;
    vec2 cn = pxCurl(vec3(p * fr, 0.37), te, oct).xy;
    vec2 v;
    if (f == 0) v = cn;
    else if (f == 1 || f == 2) {
        float a = (pxFbm(vec3(p * fr, te), oct, SEED) - 0.5) * TAU * uM1.z;
        if (f == 2) { float st = TAU / max(uM1.w, 1.0); a = floor(a / st + 0.5) * st; }
        v = vec2(cos(a), sin(a));
    } else if (f == 3 || f == 4) {
        vec2 uv = vec2(p.x / (2.0 * ASP) + 0.5, p.y * 0.5 + 0.5);
        vec2 e = 2.0 / vec2(textureSize(GP_IN, 0));
        float gx = (sl_lum(uv + vec2(e.x, 0.0)) - sl_lum(uv - vec2(e.x, 0.0))) * uM3.x;
        float gy = (sl_lum(uv + vec2(0.0, e.y)) - sl_lum(uv - vec2(0.0, e.y))) * uM3.x;
        v = f == 3 ? vec2(-gy, gx) : vec2(gx, gy);
    } else if (f == 5) v = vec2(-p.y, p.x) * uM3.y - p * uM3.z;
    else v = vec2(0.0, -1.0);
    return v + cn * uM2.w;
}
vec2 sl_spawn(int i, uint salt) {
    int sp = int(uM2.x + 0.5);
    vec2 r = vec2(rnd(i, salt), rnd(i, salt + 1u));
    if (sp == 1) return vec2(-ASP, r.y * 2.0 - 1.0);
    if (sp == 2) { float a = TAU * r.x; float rr = 0.25 * sqrt(r.y); return rr * vec2(cos(a), sin(a)); }
    vec2 best = vec2((r.x * 2.0 - 1.0) * ASP, r.y * 2.0 - 1.0);
    if (sp == 3) {
        for (int k = 0; k < 16; k++) {
            vec2 q = vec2(rnd(i, salt + 2u + 2u * uint(k)), rnd(i, salt + 3u + 2u * uint(k)));
            if (sl_lum(q) > rnd(i, salt + 40u + uint(k))) { best = vec2((q.x * 2.0 - 1.0) * ASP, q.y * 2.0 - 1.0); break; }
        }
    }
    return best;
}
vec4 pt_seed(int i) { return vec4(sl_spawn(i, 31u), rnd(i, 33u), 0.0); }
vec4 pt_step(int i, vec4 s, float dt) {
    if (dt <= 0.0) return s;
    vec2 p = s.xy;
    float sp = uM1.x;
    vec2 v1 = sl_field(p);
    vec2 vel = sl_field(p + v1 * sp * dt * 0.5) * sp;
#ifdef PXE_PARTICLES
    vel += pxeParticleForce(vec3(p, 0.0), vec3(vel, 0.0)).xy;     // effector force = extra world velocity
#endif
    p += vel * dt;
    float life = uM1.y * (0.5 + rnd(i, 35u));
    float prog = s.z + dt / max(life, 1e-3);
    bool outside = abs(p.x) > ASP || abs(p.y) > 1.0;
    if (int(uM2.y + 0.5) == 1) {
        p = vec2(mod(p.x + ASP, 2.0 * ASP) - ASP, mod(p.y + 1.0, 2.0) - 1.0);
        outside = false;
    }
    bool dead = prog >= 1.0 || outside;
#ifdef PXE_PARTICLES
    if (pxeKill(vec3(p, 0.0))) dead = true;
#endif
    if (dead) {
        vec2 q = sl_spawn(i, FR * 4u + 5u);
#ifdef PXE_PARTICLES
        uint sb = FR * 8u + 60u;
        q = pxeSpawnAt(vec3(q, 0.0), rnd(i, sb), rnd(i, sb + 1u), rnd(i, sb + 2u), rnd(i, sb + 3u)).xy;
#endif
        return vec4(q, 0.0, 0.0);
    }
    return vec4(p, prog, atan(vel.y, vel.x));
}
"""

PLACE = """
bool pt_place(int i, vec4 s, out vec3 P, out vec4 C) {
    P = vec3(s.xy, 0.0);
    float fd = uM3.w;
    float a = fd > 0.0 ? clamp(s.z / fd, 0.0, 1.0) * clamp((1.0 - s.z) / fd, 0.0, 1.0) : 1.0;
    int cb = int(uM2.z + 0.5);
    float k = cb == 0 ? s.w / TAU + 0.5 : (cb == 1 ? s.z : (cb == 2 ? s.x / (2.0 * ASP) + 0.5 : rnd(i, 5u)));
    C = vec4(ptpal(k), a);
    return true;
}
"""
