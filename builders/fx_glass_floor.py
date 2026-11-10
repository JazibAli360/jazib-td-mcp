# fx_glass_floor - FX_glass module 'floor' (FX7c 7C-21 wet mirror floor: a glossy stage floor mirroring the content
# above a floor line: flipped copy fading with distance, ripple, blur growing with distance, Fresnel, optional
# perspective tiles; the standard Notch / Arena 2D floor trick, clean-room). Template: docs/builds/fx_glitch.md "Module
# template" (rack = builders/fx_glass.py). Doc: docs/builds/fx_glass.md. Mirror: builders/fx_glass_floor_logic.py.
# One compute pass (in1 + pre-blurred backdrop): above Horizon (uv from the bottom) the picture (Layout fit = squeezed
# into the part above the line, overlay = left as is); below it the floor: base colour + perspective tiles (Tiles,
# Tilewidth, Persp) + the reflection of the picture mirrored at the line (Stretch), rippled (Ripple px, Ripplefreq,
# Ripplespeed), blurred toward the backdrop with distance (Blurdist), fading (Fade, Fadepow) and stronger near the line
# (Fresnel). Amount 0 = in1 exact (out_sel). ASCII only.
import os

MODULE = 'floor'

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']
BACKDROP_PAGE = ('Backdrop', [
    ('Backblur', 'Float', 24.0, {'min': 0, 'max': 200, 'label': 'Backdrop blur px (full-res px)'}),
    ('Backdown', 'Menu', 'half', {'names': ['full', 'half', 'quarter'], 'labels': ['Full', 'Half', 'Quarter'],
                                  'label': 'Backdrop resolution'}),
])                                                           # = fx_glass.BACKDROP_PAGE (the rack's _backdrop reads it)

PAGES = [
    ('Floor', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Layout', 'Menu', 'fit', {'names': ['fit', 'overlay'], 'labels': [
            'Fit (picture above the floor line)', 'Overlay (picture as is, floor over the bottom)']}),
        ('Horizon', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Floor line (uv from the bottom)'}),
        ('Reflect', 'Float', 0.7, {'min': 0, 'max': 2, 'label': 'Reflectivity'}),
        ('Fade', 'Float', 0.25, {'min': 0.01, 'max': 1, 'label': 'Fade distance (uv)'}),
        ('Fadepow', 'Float', 1.5, {'min': 0.2, 'max': 6, 'label': 'Fade power'}),
        ('Fresnel', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Fresnel (stronger at the line)'}),
        ('Stretch', 'Float', 1.3, {'min': 0.2, 'max': 4, 'label': 'Reflection stretch'}),
        ('Ripple', 'Float', 4.0, {'min': 0, 'max': 60, 'label': 'Ripple px'}),
        ('Ripplefreq', 'Float', 0.05, {'min': 0, 'max': 0.5, 'label': 'Ripple frequency (cycles / px)'}),
        ('Ripplespeed', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Ripple speed'}),
        ('Blurdist', 'Float', 0.2, {'min': 0.01, 'max': 1, 'label': 'Fully blurred at this distance (uv)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed (ripple noise)'}),
    ]),
    ('Surface', [
        ('Floorr', 'Float', 0.02, {'min': 0, 'max': 1, 'label': 'Floor R'}),
        ('Floorg', 'Float', 0.02, {'min': 0, 'max': 1, 'label': 'Floor G'}),
        ('Floorb', 'Float', 0.03, {'min': 0, 'max': 1, 'label': 'Floor B'}),
        ('Tiles', 'Float', 0.0, {'min': 0, 'max': 40, 'label': 'Tiles across (0 = none)'}),
        ('Tilewidth', 'Float', 0.04, {'min': 0, 'max': 0.5, 'label': 'Tile line width'}),
        ('Tileglow', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Tile line brightness'}),
        ('Persp', 'Float', 3.0, {'min': 0.2, 'max': 20, 'label': 'Perspective'}),
        ('Tilesrc', 'Menu', 'solid', {'names': ['solid', 'palette'], 'labels': ['Floor colour', 'Palette stop per row']}),
    ]),
    BACKDROP_PAGE,
    pal_page('neon_trio', 'steps'),  # noqa: F821
]
PANEL_PAGES = ['Floor', 'Surface', 'Backdrop', 'Palette']

_SKIP = ('Palstops', 'Palfile')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
_D['Palreverse'] = int(_D['Palreverse'])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'wet stage', _p()),
    (2, 'mirror', _p(Reflect=1.0, Fade=0.6, Ripple=0.0, Blurdist=1.0, Backblur=8.0, Fresnel=0.2)),
    (3, 'puddle', _p(Ripple=12.0, Ripplefreq=0.03, Ripplespeed=2.5, Reflect=0.8, Fade=0.35, Seed=3)),
    (4, 'neon grid floor', _p(Tiles=12.0, Tilewidth=0.05, Tileglow=1.2, Persp=4.0, Tilesrc=1, Reflect=0.5, Seed=4)),
    (5, 'overlay shine', _p(Layout=1, Horizon=0.22, Reflect=0.5, Fade=0.18, Seed=5)),
]

FX = """// floor fx (compute). in0 picture (bilinear), in1 pre-blurred backdrop.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, layout, horizon, reflect
uniform vec4 uB;   // fade, fade power, fresnel, stretch
uniform vec4 uC;   // ripple px, ripple freq, ripple time, blurdist
uniform vec4 uD;   // floor rgb, tiles
uniform vec4 uE;   // tile width, tile glow, persp, tile source
uniform vec4 uF;   // seed, -, -, -
""" + GLSL_LIB + PAL_GLSL + """
vec2 fs;
vec3 S0(vec2 uv) { return texture(sTD2DInputs[0], uv).rgb; }
vec3 S1(vec2 uv) { return texture(sTD2DInputs[1], uv).rgb; }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    fs = vec2(isz);
    vec2 uv = (vec2(p) + 0.5) / fs;
    float h = clamp(uA.z, 0.0, 0.999);
    bool fit = uA.y < 0.5;
    vec4 o;
    if (uv.y >= h) {
        o = fit ? vec4(S0(vec2(uv.x, (uv.y - h) / (1.0 - h))), c.a) : c;
    } else {
        float dy = h - uv.y;
        float sy = h + dy * uB.w;                                         // mirrored at the line (scene uv)
        float rx = uC.x * sin(6.2831853 * (uC.y * dy * fs.y) * (1.0 + 0.5 * vnoise(vec2(uv.x * 7.0, dy * 9.0), uint(uF.x))) - uC.z) / fs.x;
        vec2 suv = vec2(uv.x + rx, fit ? (sy - h) / (1.0 - h) : sy);
        float out_ = suv.y > 1.0 ? 0.0 : 1.0;
        suv.y = min(suv.y, 1.0);
        float bl = clamp(dy / max(uC.w, 1e-3), 0.0, 1.0);
        vec3 r = mix(S0(suv), S1(suv), bl);
        float fade = pow(clamp(1.0 - dy / max(uB.x, 1e-3), 0.0, 1.0), uB.y);
        float fr = 1.0 + uB.z * (1.0 - clamp(dy / max(uB.x, 1e-3), 0.0, 1.0));
        vec3 floorc = uD.rgb;
        if (uD.w > 0.0) {                                                   // perspective tiles
            float z = 1.0 / (dy * uE.z + 0.02);
            float xw = (uv.x - 0.5) * z;
            float gx = abs(fract(xw * uD.w * 0.1 + 0.5) - 0.5);
            float gz = abs(fract(z * 0.25) - 0.5);
            float lw = uE.x;
            float line = max(1.0 - smoothstep(0.0, lw, gx), 1.0 - smoothstep(0.0, lw * 2.0, gz * dy * uE.z * 4.0));
            vec3 lc = uE.w > 0.5 ? pxPalStep(int(floor(z * 0.25))) : vec3(1.0);
            floorc += lc * line * uE.y * clamp(dy * 8.0, 0.0, 1.0);
        }
        o = vec4(floorc + r * uA.w * fade * fr * out_, 1.0);
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, o, uA.x));
}
"""

SHADERS = {'fx': FX}
NIN = {'fx': 2}                          # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"


def uniforms():
    return {
        'fx': [('uA', [P.format('Amount'), 'parent().par.Layout.menuIndex', P.format('Horizon'), P.format('Reflect')]),
               ('uB', [P.format('Fade'), P.format('Fadepow'), P.format('Fresnel'), P.format('Stretch')]),
               ('uC', [P.format('Ripple'), P.format('Ripplefreq'), '%s * absTime.seconds' % P.format('Ripplespeed'),
                       P.format('Blurdist')]),
               ('uD', [P.format('Floorr'), P.format('Floorg'), P.format('Floorb'), P.format('Tiles')]),
               ('uE', [P.format('Tilewidth'), P.format('Tileglow'), P.format('Persp'),
                       'parent().par.Tilesrc.menuIndex']),
               ('uF', [P.format('Seed'), '0', '0', '0'])],
    }


def build(m, H):
    """in1 -> bd (backdrop) -> fx (in1, bd) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    bd = H['backdrop'](m, in1)
    fx = H['pas'](m, 'fx', FX, [in1, bd], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    H['uniforms'](fx, U['fx'])
    fx.comment = 'floor: mirrored reflection below the floor line, ripple, distance blur, fade, Fresnel, tiles.'
    pal_bind(m, H, [fx])  # noqa: F821
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact.'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'bd_down', 'bd']},
        {'title': '2 Floor', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'fx', 'fx_compute'],
         'body': 'Wet floor reflection + tiles below the floor line.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
