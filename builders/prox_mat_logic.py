"""prox_mat_logic: pure logic + numpy reference of MX_prox_material (proximity-driven PBR material; no td import).

Build doc: docs/builds/prox_mat.md. Tests: test/test_prox_mat.py. Copied into the material unit's `mx_logic` Text DAT.
Effector maths is PX's (builders/px_logic.py + builders/glsl/px_common.glsl), imported, not copied: same uE row layout
(6 vec4 rows per effector, max 8), same falloff shapes / combine modes / ragged edge. Point-set effectors
(px_requirements item 8) live in px_common.glsl too (pxPts*, pxField*); their numpy twins are here.

Uniforms: two vec4 arrays (GLSL MAT + both compute passes): `uE[48]` = effector rows (PX layout) from the `mx_eff`
Script CHOP (pack_eff; reads effector transforms, so it cooks when an effector moves) and `uMX[MAT_ROWS]` = the
material rows of ROWS below from `mx_rows` (pack_mat; reads pars, cooks only when a par changes). Split so moving
effectors never re-pack the ~110 material pars (T-115). Time comes from a par-expression vec4 uMXT.
`glsl_header()` generates the `#define MX_<ROW> uMX[i]` lines from the same table, so Python and GLSL cannot drift.
ASCII only. No limits (user rule): slider ranges only, nothing clamps a look.
"""
import math
import os
import sys

_BUILDERS = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
if os.path.isdir(_BUILDERS) and _BUILDERS not in sys.path:
    sys.path.insert(0, _BUILDERS)
import px_logic as PXL  # noqa: E402  (effector rows, falloffs, noise: one source of truth)

E_ROWS, E_PER, MAX_EFF = PXL.E_ROWS, PXL.E_PER, PXL.MAX_EFF
PTS_MAX = 4096            # = PX_PTS_MAX in px_common.glsl (brute-force cap per pass)
PTS_ROW_W = 1024          # points texture width cap
FALLOFFS = PXL.FALLOFFS
COMBINES = PXL.COMBINES

# ---------------------------------------------------------------------------------------------------- menus
POINTSRC = [('none', 'None'), ('chop', 'CHOP (tx ty tz or <name>x/y/z)'), ('top', 'TOP (rgb = xyz)'),
            ('sop', 'SOP points'), ('pop', 'POP points')]
POINTLAYOUT = [('auto', 'Auto'), ('samples', 'Samples = points (tx ty tz)'),
               ('channels', 'Channels = points (<name>x <name>y <name>z)')]
POINTPATH = [('auto', 'Auto (direct <= Directmax, else field)'), ('direct', 'Direct (brute force per pixel)'),
             ('field', 'Field (3D distance grid)')]
POINTMODE = [('nearest', 'Nearest point'), ('density', 'Soft density')]
COLOURMODES = [('off', 'Off'), ('tint', 'Tint (multiply)'), ('replace', 'Replace'), ('ramp', 'Ramp far -> near'),
               ('hue', 'Hue shift'), ('add', 'Add')]
DISSOLVEMODES = [('off', 'Off'), ('near', 'Near dissolves'), ('far', 'Far dissolves (reveal near)')]
DISPMODES = [('off', 'Off'), ('push', 'Push / pull'), ('attract', 'Attract to effector'), ('swell', 'Swell ring'),
             ('ripple', 'Ripple'), ('noise', 'Noise'), ('wake', 'Wake (point velocity)')]
DISPDIRS = [('normal', 'Normal'), ('outward', 'Away from effector'), ('axis', 'Effector up axis'), ('worldy', 'World Y')]
TRACK = [('change', 'When they change (no per-frame Python)'), ('frame', 'Every frame')]
# Effsource 'list' = the shared /project1/effectors list (packed texture buffer, any count, by name / tag; doc
# docs/builds/effectors.md); 'objects' = the Effectors par's objects through uE[48] (max 8, the v1 path).
EFFSOURCE = [('list', 'Shared list (/project1/effectors)'), ('objects', 'Objects in Effectors (max 8)')]
LISTFALL = [('effector', 'Each effector (list columns)'), ('material', 'This material (Radius / exponent / shape)')]
# Environment (W1-E GE3, docs/builds/px_geo.md): what env1 lights the demo with. scene = a low-res cube render of
# Envgeo from Envcentre (prox_mat.env_capture, every Enveveryn frames) so chrome objects show the scene.
ENVMODES = [('gradient', 'Gradient (env_map)'), ('top', 'TOP (Envtop: HDRI / cube)'),
            ('scene', 'Scene cube (Envgeo from Envcentre)')]
PRESET_NAMES = ['molten_touch', 'chrome_reveal', 'glow_aura', 'dissolve_shell', 'ripple_pool', 'point_stir',
                'chrome_mirror']
PRESET_LABELS = ['Molten touch', 'Chrome reveal', 'Glow aura', 'Dissolve shell', 'Ripple pool', 'Point stir',
                 'Chrome mirror']


def names(menu):
    return [m[0] for m in menu]


def labels(menu):
    return [m[1] for m in menu]


def _m(menu, label, extra=None):
    o = {'names': names(menu), 'labels': labels(menu), 'label': label}
    o.update(extra or {})
    return o


def _f(lo, hi, label):
    return {'min': lo, 'max': hi, 'label': label}


# ---------------------------------------------------------------------------------------------------- pars
# (name, style, default, opts). Pages = zkit panel pages. Drives: <X>near / <X>far / <X>curve (w = 1 near, 0 far;
# value = mix(far, near, w ^ curve)).
PAGES = [
    ('Effectors', [
        ('Effectors', 'Str', 'eff_box eff_sphere eff_null', {'label': 'Effectors (names / paths)', 'menu': 'objects'}),
        ('Radius', 'Float', 0.6, _f(0.001, 5, 'Radius (falloff width)')),
        ('Falloffexp', 'Float', 1.0, _f(0.05, 8, 'Falloff exponent')),
        ('Shape', 'Menu', 'smooth', _m(FALLOFFS, 'Falloff shape')),
        ('Combine', 'Menu', 'max', _m(COMBINES, 'Combine effectors')),
        ('Gain', 'Float', 1.0, _f(0, 4, 'Weight gain')),
        ('Flip', 'Toggle', False, {'label': 'Flip (far = 1)'}),
        ('Ragged', 'Float', 0.0, _f(0, 2, 'Ragged edge (noise x Radius)')),
        ('Raggedfreq', 'Float', 4.0, _f(0.1, 40, 'Ragged noise freq')),
        ('Track', 'Menu', 'change', _m(TRACK, 'Update effectors')),
        ('Effsource', 'Menu', 'list', _m(EFFSOURCE, 'Effector source')),
        ('Effselect', 'Str', 'all', {'label': 'List: use (all / names / #tags)', 'menu': 'select'}),
        ('Listfalloff', 'Menu', 'effector', _m(LISTFALL, 'List: falloff from')),
    ]),
    ('Points', [
        ('Pointsource', 'Menu', 'none', _m(POINTSRC, 'Point set source')),
        ('Pointop', 'Str', '', {'label': 'Point op (path)'}),
        ('Pointlayout', 'Menu', 'auto', _m(POINTLAYOUT, 'CHOP layout')),
        ('Pointchans', 'Str', 'tx ty tz', {'label': 'CHOP xyz channels (samples layout)'}),
        ('Topstride', 'Int', 1, {'min': 1, 'max': 8, 'clampmin': 1, 'label': 'TOP texels per point'}),
        ('Topoffset', 'Int', 0, {'min': 0, 'max': 7, 'clampmin': 0, 'label': 'TOP texel offset'}),
        ('Pointscale', 'XYZ', (1.0, 1.0, 1.0), _f(-10, 10, 'Point scale')),
        ('Pointoffset', 'XYZ', (0.0, 0.0, 0.0), _f(-10, 10, 'Point offset')),
        ('Pointspace', 'Str', '', {'label': 'Point space COMP (optional)'}),
        ('Pointmax', 'Int', 4096, {'min': 1, 'max': 4096, 'clampmin': 1, 'label': 'Max points (stride decimate)'}),
        ('Pointpath', 'Menu', 'auto', _m(POINTPATH, 'Point proximity path')),
        ('Directmax', 'Int', 64, {'min': 1, 'max': 1024, 'clampmin': 1, 'label': 'Direct path max points'}),
        ('Pointmode', 'Menu', 'nearest', _m(POINTMODE, 'Point mode')),
        ('Pointradius', 'Float', 0.05, _f(0, 1, 'Point radius')),
        ('Densityfull', 'Float', 2.0, _f(0.01, 20, 'Density for full weight')),
        ('Pointweight', 'Float', 1.0, _f(0, 4, 'Point-set weight')),
        ('Velsmooth', 'Float', 0.6, _f(0, 0.99, 'Velocity smoothing')),
        ('Gridres', 'Int', 48, {'min': 8, 'max': 128, 'clampmin': 4, 'label': 'Field grid cells / axis'}),
        ('Gridcentre', 'XYZ', (0.0, 0.0, 0.0), _f(-10, 10, 'Field box centre')),
        ('Gridsize', 'XYZ', (4.0, 4.0, 4.0), _f(0.01, 20, 'Field box size')),
    ]),
    ('Colour', [
        ('Basecolour', 'RGB', (0.55, 0.55, 0.6), {'label': 'Base colour'}),
        ('Basealpha', 'Float', 1.0, _f(0, 1, 'Base alpha')),
        ('Pointcolour', 'Toggle', True, {'label': 'Multiply by point colour (Cd, as TD PBR)'}),
        ('Colourmode', 'Menu', 'tint', _m(COLOURMODES, 'Colour mode')),
        ('Colournear', 'RGB', (1.0, 0.35, 0.1), {'label': 'Near colour'}),
        ('Colourfar', 'RGB', (0.1, 0.12, 0.2), {'label': 'Far colour (ramp)'}),
        ('Colouramt', 'Float', 1.0, _f(0, 2, 'Colour amount')),
        ('Colourcurve', 'Float', 1.0, _f(0.05, 8, 'Colour curve')),
        ('Huenear', 'Float', 0.25, _f(-1, 1, 'Hue shift near (turns)')),
    ]),
    ('Surface', [
        ('Roughnear', 'Float', 0.15, _f(0, 1, 'Roughness near')),
        ('Roughfar', 'Float', 0.6, _f(0, 1, 'Roughness far')),
        ('Roughcurve', 'Float', 1.0, _f(0.05, 8, 'Roughness curve')),
        ('Metalnear', 'Float', 0.0, _f(0, 1, 'Metallic near')),
        ('Metalfar', 'Float', 0.0, _f(0, 1, 'Metallic far')),
        ('Metalcurve', 'Float', 1.0, _f(0.05, 8, 'Metallic curve')),
        ('Specular', 'Float', 0.5, _f(0, 2, 'Specular level')),
        ('Ao', 'Float', 1.0, _f(0, 1, 'Ambient occlusion')),
        ('Nrmnear', 'Float', 0.0, _f(0, 2, 'Detail normal near')),
        ('Nrmfar', 'Float', 0.0, _f(0, 2, 'Detail normal far')),
        ('Nrmcurve', 'Float', 1.0, _f(0.05, 8, 'Detail normal curve')),
        ('Nrmfreq', 'Float', 6.0, _f(0.1, 80, 'Detail noise freq')),
        ('Nrmspeed', 'Float', 0.0, _f(0, 5, 'Detail noise speed')),
        ('Nrmoct', 'Int', 3, {'min': 1, 'max': 6, 'clampmin': 1, 'label': 'Detail octaves'}),
        ('Shadowstrength', 'Float', 1.0, _f(0, 1, 'Shadow strength')),
        ('Shadowcolour', 'RGB', (0.0, 0.0, 0.0), {'label': 'Shadow colour'}),
    ]),
    ('Emission', [
        ('Emitbase', 'RGB', (0.0, 0.0, 0.0), {'label': 'Base emission'}),
        ('Emitcolour', 'RGB', (1.0, 0.45, 0.12), {'label': 'Proximity emission colour'}),
        ('Emitnear', 'Float', 0.0, _f(0, 20, 'Emission near')),
        ('Emitfar', 'Float', 0.0, _f(0, 20, 'Emission far')),
        ('Emitcurve', 'Float', 1.0, _f(0.05, 8, 'Emission curve')),
        ('Rimcolour', 'RGB', (0.4, 0.7, 1.0), {'label': 'Rim colour'}),
        ('Rimnear', 'Float', 0.0, _f(0, 20, 'Rim glow near')),
        ('Rimfar', 'Float', 0.0, _f(0, 20, 'Rim glow far')),
        ('Rimcurve', 'Float', 1.0, _f(0.05, 8, 'Rim curve')),
        ('Rimpower', 'Float', 3.0, _f(0.2, 16, 'Rim power (fresnel)')),
    ]),
    ('Dissolve', [
        ('Dissolvemode', 'Menu', 'off', _m(DISSOLVEMODES, 'Dissolve')),
        ('Dissolvecurve', 'Float', 1.0, _f(0.05, 8, 'Dissolve curve')),
        ('Dissolveoffset', 'Float', 0.0, _f(-1, 1, 'Dissolve offset')),
        ('Noisescale', 'Float', 5.0, _f(0.05, 60, 'Edge noise scale')),
        ('Noiseoct', 'Int', 3, {'min': 1, 'max': 6, 'clampmin': 1, 'label': 'Edge noise octaves'}),
        ('Noisespeed', 'Float', 0.2, _f(0, 5, 'Edge noise speed')),
        ('Burnwidth', 'Float', 0.08, _f(0, 0.5, 'Burnt rim width')),
        ('Burncolour', 'RGB', (1.0, 0.4, 0.05), {'label': 'Burnt rim colour'}),
        ('Burnemit', 'Float', 6.0, _f(0, 50, 'Burnt rim emission')),
        ('Char', 'Float', 0.8, _f(0, 1, 'Char (darken near the rim)')),
        ('Opacityon', 'Toggle', False, {'label': 'Opacity drive (blending on)'}),
        ('Opanear', 'Float', 1.0, _f(0, 1, 'Opacity near')),
        ('Opafar', 'Float', 1.0, _f(0, 1, 'Opacity far')),
        ('Opacurve', 'Float', 1.0, _f(0.05, 8, 'Opacity curve')),
    ]),
    ('Displace', [
        ('Dispmode', 'Menu', 'off', _m(DISPMODES, 'Displace mode')),
        ('Dispnear', 'Float', 0.2, _f(-2, 2, 'Displace near')),
        ('Dispfar', 'Float', 0.0, _f(-2, 2, 'Displace far')),
        ('Dispcurve', 'Float', 1.0, _f(0.05, 8, 'Displace curve')),
        ('Dispdir', 'Menu', 'normal', _m(DISPDIRS, 'Direction')),
        ('Ripplefreq', 'Float', 12.0, _f(0, 80, 'Ripple freq (rad / unit)')),
        ('Ripplespeed', 'Float', 6.0, _f(-40, 40, 'Ripple speed (rad / s)')),
        ('Dispnoisefreq', 'Float', 3.0, _f(0.05, 40, 'Noise freq')),
        ('Wakegain', 'Float', 0.05, _f(-1, 1, 'Wake gain (s)')),
        ('Normalfix', 'Toggle', True, {'label': 'Recompute normals'}),
        ('Normaleps', 'Float', 0.01, _f(0.0005, 0.2, 'Normal step (world)')),
        ('Dispcache', 'Toggle', True, {'label': 'Vertex cache (displace once per point)'}),
    ]),
    ('Presets', [
        ('Preset', 'Menu', 'molten_touch', {'names': PRESET_NAMES, 'labels': PRESET_LABELS, 'label': 'Preset'}),
        ('Applypreset', 'Pulse', None, {'label': 'Apply preset'}),
        ('Resx', 'Int', 1080, {'min': 64, 'max': 3840, 'clampmin': 1, 'label': 'Out width (demo)'}),
        ('Resy', 'Int', 1920, {'min': 64, 'max': 3840, 'clampmin': 1, 'label': 'Out height (demo)'}),
        ('Antialias', 'Menu', 'aa2', {'names': ['aa1', 'aa2', 'aa4', 'aa8mid'], 'labels': ['1x', '2x', '4x', '8x'],
                                      'label': 'Antialias (demo renders)'}),
        ('Animate', 'Toggle', True, {'label': 'Animate demo effectors'}),
        ('Showeff', 'Toggle', True, {'label': 'COMP viewer: preview with gizmos'}),
    ]),
    ('Environment', [
        ('Envmode', 'Menu', 'gradient', _m(ENVMODES, 'Environment (demo env1)')),
        ('Envtop', 'Str', '', {'label': 'Environment TOP (path)'}),
        ('Envgeo', 'Str', 'geo_torus geo_plane', {'label': 'Scene cube: geometry', 'menu': 'geos'}),
        ('Envcentre', 'XYZ', (0.0, 1.35, 0.0), _f(-10, 10, 'Scene cube: centre (the chrome object)')),
        ('Envres', 'Int', 256, {'min': 16, 'max': 1024, 'clampmin': 16, 'label': 'Scene cube px'}),
        ('Enveveryn', 'Int', 4, {'min': 1, 'max': 30, 'clampmin': 1, 'label': 'Scene cube every N frames'}),
        ('Envdimmer', 'Float', 0.8, _f(0, 4, 'Environment dimmer')),
    ]),
]
PANEL_PAGES = ['Effectors', 'Points', 'Colour', 'Surface', 'Emission', 'Dissolve', 'Displace', 'Presets', 'Environment']
DEMO_ONLY = ('Resx', 'Resy', 'Antialias', 'Animate', 'Showeff', 'Envmode', 'Envtop', 'Envgeo', 'Envcentre', 'Envres',
             'Enveveryn', 'Envdimmer')


def par_specs():
    return dict((n, (st, d, o)) for _, pars in PAGES for n, st, d, o in pars)


def defaults():
    out = {}
    for n, (st, d, o) in par_specs().items():
        if st in ('RGB', 'XYZ'):
            for c, v in zip(('rgb' if st == 'RGB' else 'xyz'), d):
                out[n + c] = v
        elif st != 'Pulse':
            out[n] = d
    return out


def menu_index(menu, val):
    ns = names(menu)
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return int(val)
    return ns.index(val) if val in ns else 0


# ---------------------------------------------------------------------------------------------------- uMX rows
# Each row = 4 items: a par name (menus give their index, toggles 0/1), a float constant, or '@key' = a derived value
# (pack_rows' `derived` dict). Order = index after the 48 effector rows.
ROWS = [
    ('G0', ['@neff', '@ptpath', '@ptm', 'Flip']),
    ('PROX', ['Radius', 'Falloffexp', 'Shape', 'Combine']),
    ('RAG', ['Ragged', 'Raggedfreq', 'Gain', 'Pointweight']),
    ('PTS', ['@ptm', '@ptw', '@pth', 'Pointradius']),
    ('PTS2', ['Pointmode', 'Densityfull', 'Velsmooth', '@ptn']),
    ('PSRC', ['@srcw', '@srch', '@stride', '@toff']),
    ('PXF0', ['@pxf00', '@pxf01', '@pxf02', '@pxf03']),
    ('PXF1', ['@pxf10', '@pxf11', '@pxf12', '@pxf13']),
    ('PXF2', ['@pxf20', '@pxf21', '@pxf22', '@pxf23']),
    ('GRID', ['@glox', '@gloy', '@gloz', 'Gridres']),
    ('GRID2', ['Gridsizex', 'Gridsizey', 'Gridsizez', '@gtiles']),
    ('BASE', ['Basecolourr', 'Basecolourg', 'Basecolourb', 'Basealpha']),
    ('COL', ['Colourmode', 'Colouramt', 'Colourcurve', 'Huenear']),
    ('CNEAR', ['Colournearr', 'Colournearg', 'Colournearb', 'Pointcolour']),
    ('CFAR', ['Colourfarr', 'Colourfarg', 'Colourfarb', 0.0]),
    ('ROUGH', ['Roughnear', 'Roughfar', 'Roughcurve', 'Specular']),
    ('METAL', ['Metalnear', 'Metalfar', 'Metalcurve', 'Ao']),
    ('NRM', ['Nrmnear', 'Nrmfar', 'Nrmcurve', 'Nrmfreq']),
    ('NRM2', ['Nrmspeed', 'Nrmoct', 'Shadowstrength', 0.0]),
    ('SHC', ['Shadowcolourr', 'Shadowcolourg', 'Shadowcolourb', 0.0]),
    ('EMIT', ['Emitnear', 'Emitfar', 'Emitcurve', 'Rimpower']),
    ('ECOL', ['Emitcolourr', 'Emitcolourg', 'Emitcolourb', 0.0]),
    ('EBASE', ['Emitbaser', 'Emitbaseg', 'Emitbaseb', 0.0]),
    ('RIM', ['Rimnear', 'Rimfar', 'Rimcurve', 0.0]),
    ('RCOL', ['Rimcolourr', 'Rimcolourg', 'Rimcolourb', 0.0]),
    ('DIS', ['Dissolvemode', 'Dissolvecurve', 'Dissolveoffset', 'Noisescale']),
    ('DIS2', ['Noiseoct', 'Noisespeed', 'Burnwidth', 'Burnemit']),
    ('BCOL', ['Burncolourr', 'Burncolourg', 'Burncolourb', 'Char']),
    ('OPA', ['Opanear', 'Opafar', 'Opacurve', 'Opacityon']),
    ('DSP', ['Dispnear', 'Dispfar', 'Dispcurve', 'Dispmode']),
    ('DSP2', ['Dispdir', 'Ripplefreq', 'Ripplespeed', 'Dispnoisefreq']),
    ('DSP3', ['Wakegain', 'Normalfix', 'Normaleps', 'Dispcache']),
]
MAT_ROWS = len(ROWS)
MX_ROWS = E_ROWS + MAT_ROWS      # combined list (pack_rows: effector rows then material rows) for the references
MENUS = {'Shape': FALLOFFS, 'Combine': COMBINES, 'Pointmode': POINTMODE, 'Colourmode': COLOURMODES,
         'Dissolvemode': DISSOLVEMODES, 'Dispmode': DISPMODES, 'Dispdir': DISPDIRS, 'Pointsource': POINTSRC,
         'Pointlayout': POINTLAYOUT, 'Pointpath': POINTPATH, 'Track': TRACK, 'Effsource': EFFSOURCE,
         'Listfalloff': LISTFALL, 'Preset': list(zip(PRESET_NAMES, PRESET_LABELS))}


def mat_index(name):
    """Index in uMX / the mx_rows CHOP."""
    return [r[0] for r in ROWS].index(name)


def row_index(name):
    """Index in the combined pack_rows list."""
    return E_ROWS + mat_index(name)


def glsl_header():
    """Uniform declarations + #defines shared by mx_vert, mx_pixel, pts, field (prepended by the builder)."""
    out = ['// generated by prox_mat_logic.glsl_header() - do not edit by hand',
           '#define PX_NO_TEX_INPUTS',
           'uniform vec4 uE[%d];  // effector rows (PX layout), mx_eff' % E_ROWS,
           'uniform vec4 uMX[%d];  // material rows, mx_rows' % MAT_ROWS,
           'uniform vec4 uMXT;   // seconds, frame dt, frame, 0',
           'vec4 uG[%d];          // PX lib globals: only uG[1].z (effector count) is used here, set by mxInit()' % PXL.G_ROWS]
    for k, (n, _) in enumerate(ROWS):
        out.append('#define MX_%s uMX[%d]' % (n, k))
    return '\n'.join(out) + '\n'


def item_value(item, get, derived):
    if isinstance(item, (int, float)) and not isinstance(item, bool):
        return float(item)
    if item.startswith('@'):
        return float(derived.get(item[1:], 0.0))
    v = get(item)
    if item in MENUS:
        return float(menu_index(MENUS[item], v))
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    return float(v)


# ---------------------------------------------------------------------------------------------------- points
def pts_size(n, pointmax):
    """Points texture: M = min(N, Pointmax, PTS_MAX) points as W x H (texture W x 2H with the velocity rows)."""
    m = max(0, min(int(n), int(max(pointmax, 1)), PTS_MAX))
    w = max(1, min(m, PTS_ROW_W))
    h = max(1, -(-m // w)) if m else 1
    return m, w, h


def pts_path(source, path, n_pts, directmax):
    """0 none, 1 direct, 2 field."""
    if source == 'none' or n_pts <= 0:
        return 0
    if path == 'direct':
        return 1
    if path == 'field':
        return 2
    return 1 if n_pts <= int(directmax) else 2


def field_tiles(res):
    return max(1, int(math.ceil(math.sqrt(max(int(res), 1)))))


def field_size(res):
    """Atlas resolution (w, h) for an R^3 grid: R*T x 2*R*T (distance/density rows + velocity rows)."""
    r = max(int(res), 1)
    t = field_tiles(r)
    return r * t, 2 * r * t


_ALT = [('tx', 'ty', 'tz'), ('x', 'y', 'z'), ('P0', 'P1', 'P2'), ('P(0)', 'P(1)', 'P(2)'), ('px', 'py', 'pz')]


def points_from_chans(chans, layout='auto', want=('tx', 'ty', 'tz'), z=0.0):
    """chans = [(name, values)] (lists or numpy) -> (n, 3) float32. 'samples': one point per sample from 3 named
    channels (want, then common aliases, then the first channels; a missing z = z). 'channels': one point per channel
    group <key>x <key>y [<key>z] at sample 0 (FT_face_track out_pts style), in first-seen order."""
    import numpy as np
    if not chans:
        return np.zeros((0, 3), dtype=np.float32)
    ns = max(len(v) for _, v in chans)
    if layout == 'auto':
        layout = 'samples' if ns > 1 else 'channels'
    d = dict(chans)
    if layout == 'samples':
        trip = None
        for cand in [tuple(want)] + _ALT:
            if len(cand) >= 2 and cand[0] in d and cand[1] in d:
                trip = cand
                break
        if trip is None:
            trip = tuple(n for n, _ in chans[:3])
        cols = [np.asarray(d[t], dtype=np.float32).reshape(-1) for t in trip if t in d]
        n = min(len(c) for c in cols)
        out = np.full((n, 3), float(z), dtype=np.float32)
        for k, c in enumerate(cols[:3]):
            out[:, k] = c[:n]
        return out
    keys, grp = [], {}
    for name, vals in chans:
        if not name or name[-1].lower() not in 'xyz' or len(vals) == 0:
            continue
        k, ax = name[:-1], name[-1].lower()
        if k not in grp:
            grp[k] = {}
            keys.append(k)
        grp[k][ax] = float(vals[0])
    rows = [(g.get('x', 0.0), g.get('y', 0.0), g.get('z', float(z))) for g in (grp[k] for k in keys)
            if 'x' in g and 'y' in g]
    return np.asarray(rows, dtype=np.float32).reshape(-1, 3)


def count_points(src, n_chop_pts=0, top_w=0, top_h=0, stride=1, offset=0):
    """N source points: CHOP / SOP / POP = the normalised point count; TOP = (w * h - offset) // stride."""
    if src == 'top':
        return max(0, (int(top_w) * int(top_h) - int(offset)) // max(int(stride), 1))
    if src in ('chop', 'sop', 'pop'):
        return int(n_chop_pts)
    return 0


def count_chop_points(names, nsamples, layout='auto'):
    """Point count of a CHOP without reading values (same rules as points_from_chans)."""
    if not names:
        return 0
    if layout == 'auto':
        layout = 'samples' if nsamples > 1 else 'channels'
    if layout == 'samples':
        return int(nsamples)
    keys = set()
    have = {}
    for n in names:
        if n and n[-1].lower() in 'xyz':
            have.setdefault(n[:-1], set()).add(n[-1].lower())
    return sum(1 for k, v in have.items() if 'x' in v and 'y' in v)


def tex_dims(n, row_w=PTS_ROW_W):
    """(W, H) of points_image for n points."""
    w = max(1, min(int(n), row_w))
    return w, (max(1, -(-int(n) // w)) if n else 1)


def points_image(pts, row_w=PTS_ROW_W):
    """Points (n, 3) -> (H, W, 4) float32 rows (texel i = (i % W, i // W), a = 1 valid, 0 pad) for a Script TOP."""
    import numpy as np
    a = np.asarray(pts, dtype=np.float32).reshape(-1, 3)
    n = len(a)
    w = max(1, min(n, row_w))
    h = max(1, -(-n // w)) if n else 1
    img = np.zeros((h, w, 4), dtype=np.float32)
    if n:
        flat = img.reshape(-1, 4)
        flat[:n, :3] = a
        flat[:n, 3] = 1.0
    return img


def point_affine(scale, offset, space_world=None):
    """Point xform rows (3x4): world = Space * (p * scale + offset)."""
    s, o = [float(v) for v in scale], [float(v) for v in offset]
    m = [[s[0], 0.0, 0.0, o[0]], [0.0, s[1], 0.0, o[1]], [0.0, 0.0, s[2], o[2]]]
    if space_world is None:
        return m
    W = space_world
    return [[sum(W[r][k] * m[k][c] for k in range(3)) + (W[r][3] if c == 3 else 0.0) for c in range(4)]
            for r in range(3)]


# ---------------------------------------------------------------------------------------------------- effectors
def kind_of(optype, comp_type='geometryCOMP'):
    """Effector kind from the COMP type and its rendered SOP/POP type (box / sphere / plane / null)."""
    if comp_type != 'geometryCOMP':
        return 'null'
    t = (optype or '').lower()
    if t.startswith('box'):
        return 'box'
    if t.startswith('sphere'):
        return 'sphere'
    if t.startswith('grid') or t.startswith('rectangle'):
        return 'plane'
    return 'null'


def effector_world(world, kind, bmin=None, bsize=None):
    """Object world 3x4 + its shape bounds -> (world', size) where the PX unit SDF fits the shape: the box / sphere is
    centred on the bounds centre; a plane's normal is its thinnest bounds axis (rotated onto local y)."""
    if bmin is None or bsize is None:
        return world, None
    c = [bmin[k] + 0.5 * bsize[k] for k in range(3)]
    t = [sum(world[r][k] * c[k] for k in range(3)) + world[r][3] for r in range(3)]
    w = [[world[r][0], world[r][1], world[r][2], t[r]] for r in range(3)]
    if kind == 'box':
        return w, tuple(0.5 * float(v) for v in bsize)
    if kind == 'sphere':
        return w, (0.5 * float(max(bsize)), 0.0, 0.0)
    if kind == 'plane':
        k = min(range(3), key=lambda i: abs(bsize[i]))
        perm = {0: (1, 0, 2), 1: (0, 1, 2), 2: (0, 2, 1)}[k]       # local axes -> columns, normal axis to y
        return [[w[r][perm[0]], w[r][perm[1]], w[r][perm[2]], w[r][3]] for r in range(3)], None
    return w, None


def effector_rows(effs):
    """[{'kind', 'world', 'size'(opt)}] -> 48 rows (PX layout, PX code)."""
    return PXL.effector_rows([dict(e, speed=0.0) for e in effs])


# ---------------------------------------------------------------------------------------------------- pack
def derived_values(get, neff, n_src, src_w, src_h, space_world=None):
    src = get('Pointsource')
    m, w, h = pts_size(n_src if src != 'none' else 0, get('Pointmax'))
    path = pts_path(src, get('Pointpath'), m, get('Directmax'))
    sc = [get('Pointscale' + c) for c in 'xyz']
    of = [get('Pointoffset' + c) for c in 'xyz']
    A = point_affine(sc, of, space_world)
    d = {'neff': min(int(neff), MAX_EFF), 'ptpath': path, 'ptm': m if path else 0, 'ptw': w, 'pth': h,
         'ptn': n_src, 'srcw': src_w, 'srch': src_h, 'gtiles': field_tiles(get('Gridres')),
         'stride': max(1, int(get('Topstride'))) if src == 'top' else 1,
         'toff': max(0, int(get('Topoffset'))) if src == 'top' else 0}
    for r in range(3):
        for c in range(4):
            d['pxf%d%d' % (r, c)] = A[r][c]
    for k, ax in enumerate('xyz'):
        d['glo' + ax] = get('Gridcentre' + ax) - 0.5 * get('Gridsize' + ax)
    return d


def pack_eff(effs):
    """-> 48 x 4 floats for uE (mx_eff)."""
    return [list(map(float, r)) for r in effector_rows(effs)]


def pack_mat(get, neff, n_src=0, src_w=1, src_h=1, space_world=None):
    """-> MAT_ROWS x 4 floats for uMX (mx_rows)."""
    der = derived_values(get, neff, n_src, src_w, src_h, space_world)
    return [[item_value(it, get, der) for it in items] for _, items in ROWS]


def pack_rows(get, effs, n_src=0, src_w=1, src_h=1, space_world=None):
    """Combined list (effector rows + material rows) used by the numpy references and tests."""
    return pack_eff(effs) + pack_mat(get, len(effs), n_src, src_w, src_h, space_world)


def rows_to_chans(rows):
    """Rows -> 4 channel lists x y z w (samples = rows), the GLSL uniform array CHOP layout (particles / PX)."""
    return [[r[c] for r in rows] for c in range(4)]


# ---------------------------------------------------------------------------------------------------- demo scene
# Demo effector motion (par expressions while Animate is on; Animate off freezes them as constants to place by hand).
T = 'absTime.seconds'
DEMO_ANIM = {
    'eff_box': {'tx': '1.25 * math.sin(%s * 0.45)' % T, 'ty': '1.35 + 0.25 * math.sin(%s * 0.7)' % T,
                'tz': '0.35 * math.cos(%s * 0.45)' % T, 'ry': '%s * 20' % T},
    'eff_sphere': {'tx': '1.05 * math.cos(%s * 0.6)' % T, 'ty': '0.2 + 0.15 * math.sin(%s * 1.1)' % T,
                   'tz': '0.8 * math.sin(%s * 0.6)' % T},
    'eff_null': {'tx': '1.0 * math.sin(%s * 0.35)' % T, 'ty': '-0.95', 'tz': '0.3 + 0.5 * math.cos(%s * 0.5)' % T},
}
# ---------------------------------------------------------------------------------------------- vertex cache
# vc_cache (compute) runs the vertex displacement once per POINT of each cached geometry (perf-b2-w4); slot k = one
# geometry drawn with this unit's MAT k. vc_rows packs the slot table (uVG texture buffer), vc_src the SOP-space
# points (P rows then N rows). The vertex shader checks every texel against its own rest point (no match: own path).
VC_W = 256               # cache texture width (points per row)
VC_SLOT_ROWS = 7         # world rows 0-2, normal rows 3-5, (offset, count, 0, 0)


def vc_layout(counts, w=VC_W):
    """Point counts per slot -> (offsets, total, rows H) of the packed W x H point grid."""
    offs, n = [], 0
    for c in counts:
        offs.append(n)
        n += max(int(c), 0)
    return offs, n, max(1, (n + w - 1) // w)


def _inv3(m):
    a, b, c = m[0][:3], m[1][:3], m[2][:3]
    det = (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0]))
    if abs(det) < 1e-30:
        return None
    r = [[(b[1] * c[2] - b[2] * c[1]) / det, (a[2] * c[1] - a[1] * c[2]) / det, (a[1] * b[2] - a[2] * b[1]) / det],
         [(b[2] * c[0] - b[0] * c[2]) / det, (a[0] * c[2] - a[2] * c[0]) / det, (a[2] * b[0] - a[0] * b[2]) / det],
         [(b[0] * c[1] - b[1] * c[0]) / det, (a[1] * c[0] - a[0] * c[1]) / det, (a[0] * b[1] - a[1] * b[0]) / det]]
    return r


def normal_rows(world):
    """Rows of the normal matrix = inverse transpose of the world 3 x 3 (TD's worldForNormals), as 3 vec4 (w 0)."""
    inv = _inv3(world)
    if inv is None:
        return [(1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0)]
    return [(inv[0][r], inv[1][r], inv[2][r], 0.0) for r in range(3)]   # row r of inv^T = column r of inv


def vc_rows(slots, on=True, w=VC_W):
    """slots = [(world 4x4 row-major (rows of 4), point count)] -> uVG rows: (on, W, H, nslots), then per slot the 3
    world rows, 3 normal rows, (offset, count, 0, 0). A slot with count 0 (no SOP / not cacheable) is kept, empty."""
    offs, n, h = vc_layout([c for _, c in slots], w)
    out = [(1.0 if (on and n > 0) else 0.0, float(w), float(h), float(len(slots)))]
    for (world, c), o in zip(slots, offs):
        out += [tuple(float(x) for x in world[r][:4]) for r in range(3)]
        out += normal_rows(world)
        out.append((float(o), float(max(int(c), 0)), 0.0, 0.0))
    return out


def vc_image(chunks, w=VC_W):
    """chunks = [(P (n x 3), N (n x 3))] per slot -> float32 (2H, W, 4): P rows (a = 1) then N rows."""
    np = _np()
    offs, n, h = vc_layout([len(P) for P, _ in chunks], w)
    a = np.zeros((2 * h, w, 4), np.float32)
    fp = a[:h].reshape(-1, 4)
    fn = a[h:].reshape(-1, 4)
    for (P, N), o in zip(chunks, offs):
        k = len(P)
        if k:
            fp[o:o + k, :3] = np.asarray(P, np.float32).reshape(k, 3)
            fp[o:o + k, 3] = 1.0
            fn[o:o + k, :3] = np.asarray(N, np.float32).reshape(k, 3)
    return a


DEMO_HOME = {'eff_box': {'tx': 0.9, 'ty': 1.35, 'tz': 0.2, 'ry': 0.0}, 'eff_sphere': {'tx': 0.8, 'ty': 0.2, 'tz': 0.4},
             'eff_null': {'tx': 0.3, 'ty': -0.95, 'tz': 0.3}}
DEMO_MESHES = [
    # name, sop kind, transform (tx ty tz rx), comment
    ('geo_sphere', 'sphere', (0.0, 1.35, 0.0, 0.0), 'Polygon sphere r 0.55 (80 x 80).'),
    ('geo_torus', 'torus', (0.0, 0.2, 0.0, 70.0), 'Torus 0.6 / 0.22 (60 x 120).'),
    ('geo_plane', 'grid', (0.0, -1.15, 0.0, 0.0), 'Dense plane 2.4 x 2.4, 200 x 200 (displacement / ripples).'),
]


# ---------------------------------------------------------------------------------------------------- presets
PRESETS = {
    'molten_touch': {
        'Radius': 0.7, 'Shape': 'smooth', 'Falloffexp': 1.4, 'Ragged': 0.35, 'Raggedfreq': 5.0,
        'Basecolour': (0.08, 0.07, 0.07), 'Colourmode': 'ramp', 'Colourfar': (0.08, 0.07, 0.07),
        'Colournear': (1.0, 0.32, 0.05), 'Colourcurve': 1.5, 'Roughnear': 0.25, 'Roughfar': 0.85, 'Metalnear': 0.0,
        'Metalfar': 0.0, 'Emitcolour': (1.0, 0.35, 0.06), 'Emitnear': 4.0, 'Emitfar': 0.0, 'Emitcurve': 2.0,
        'Rimnear': 0.0, 'Rimfar': 0.0, 'Dissolvemode': 'off', 'Opacityon': False, 'Dispmode': 'swell',
        'Dispnear': 0.12, 'Dispfar': 0.0, 'Dispdir': 'normal', 'Nrmnear': 0.6, 'Nrmfar': 0.0, 'Nrmfreq': 9.0,
        'Nrmoct': 2},
    'chrome_reveal': {
        'Radius': 0.5, 'Shape': 'smooth', 'Falloffexp': 1.0, 'Ragged': 0.0, 'Basecolour': (0.92, 0.92, 0.95),
        'Colourmode': 'replace', 'Colournear': (0.95, 0.95, 0.98), 'Colourfar': (0.2, 0.2, 0.22),
        'Roughnear': 0.04, 'Roughfar': 0.7, 'Metalnear': 1.0, 'Metalfar': 0.0,
        'Emitnear': 0.0, 'Emitfar': 0.0, 'Rimnear': 0.0, 'Rimfar': 0.0, 'Dissolvemode': 'off', 'Opacityon': False,
        'Dispmode': 'push', 'Dispnear': 0.04, 'Dispfar': 0.0, 'Nrmnear': 0.0, 'Nrmfar': 0.3, 'Nrmfreq': 14.0},
    'glow_aura': {
        'Radius': 0.9, 'Shape': 'gaussian', 'Falloffexp': 1.0, 'Ragged': 0.0, 'Basecolour': (0.05, 0.05, 0.09),
        'Colourmode': 'hue', 'Huenear': 0.35, 'Roughnear': 0.3, 'Roughfar': 0.45, 'Metalnear': 0.3, 'Metalfar': 0.0,
        'Emitcolour': (0.35, 0.6, 1.0), 'Emitnear': 2.5, 'Emitfar': 0.0, 'Emitcurve': 1.0,
        'Rimcolour': (0.6, 0.35, 1.0), 'Rimnear': 6.0, 'Rimfar': 0.3, 'Rimpower': 2.5, 'Dissolvemode': 'off',
        'Opacityon': False, 'Dispmode': 'off', 'Nrmnear': 0.0, 'Nrmfar': 0.0},
    'dissolve_shell': {
        'Radius': 0.6, 'Shape': 'smooth', 'Falloffexp': 1.0, 'Ragged': 0.25, 'Basecolour': (0.75, 0.72, 0.68),
        'Colourmode': 'off', 'Roughnear': 0.5, 'Roughfar': 0.5, 'Metalnear': 0.0, 'Metalfar': 0.0,
        'Emitnear': 0.0, 'Emitfar': 0.0, 'Rimnear': 0.0, 'Rimfar': 0.0, 'Dissolvemode': 'near', 'Dissolvecurve': 1.0,
        'Dissolveoffset': -0.15, 'Noisescale': 6.0, 'Noiseoct': 3, 'Noisespeed': 0.3, 'Burnwidth': 0.1,
        'Burncolour': (1.0, 0.45, 0.08), 'Burnemit': 8.0, 'Char': 0.85, 'Opacityon': False, 'Dispmode': 'off'},
    'ripple_pool': {
        'Radius': 1.2, 'Shape': 'linear', 'Falloffexp': 1.0, 'Ragged': 0.0, 'Basecolour': (0.05, 0.12, 0.2),
        'Colourmode': 'add', 'Colournear': (0.1, 0.35, 0.5), 'Colouramt': 0.6, 'Roughnear': 0.05, 'Roughfar': 0.2,
        'Metalnear': 0.0, 'Metalfar': 0.0, 'Emitnear': 0.0, 'Emitfar': 0.0, 'Rimnear': 0.0, 'Rimfar': 0.0,
        'Dissolvemode': 'off', 'Opacityon': False, 'Dispmode': 'ripple', 'Dispnear': 0.08, 'Dispfar': 0.0,
        'Ripplefreq': 18.0, 'Ripplespeed': 8.0, 'Dispdir': 'normal', 'Nrmnear': 0.0, 'Nrmfar': 0.0},
    'point_stir': {
        'Pointsource': 'chop', 'Pointmode': 'nearest', 'Pointradius': 0.03, 'Radius': 0.35, 'Shape': 'gaussian',
        'Basecolour': (0.1, 0.1, 0.12), 'Colourmode': 'ramp', 'Colourfar': (0.1, 0.1, 0.12),
        'Colournear': (0.3, 0.9, 1.0), 'Roughnear': 0.1, 'Roughfar': 0.6, 'Metalnear': 0.6, 'Metalfar': 0.0,
        'Emitcolour': (0.3, 0.9, 1.0), 'Emitnear': 1.5, 'Emitfar': 0.0, 'Dissolvemode': 'off', 'Opacityon': False,
        'Dispmode': 'wake', 'Wakegain': 0.08, 'Dispnear': 0.05, 'Dispfar': 0.0},
    # W1-E GE3: mirror metal everywhere (no proximity look) for reflective objects in a splat scene; pair with a
    # scene environment (MX Envmode scene / BL Geoenv) so it shows the scene. Glow comes from Emitbase if wanted.
    'chrome_mirror': {
        'Radius': 0.5, 'Shape': 'smooth', 'Ragged': 0.0, 'Basecolour': (0.95, 0.95, 0.97), 'Colourmode': 'off',
        'Roughnear': 0.04, 'Roughfar': 0.06, 'Metalnear': 1.0, 'Metalfar': 1.0, 'Emitnear': 0.0, 'Emitfar': 0.0,
        'Rimnear': 0.0, 'Rimfar': 0.0, 'Dissolvemode': 'off', 'Opacityon': False, 'Dispmode': 'off',
        'Nrmnear': 0.0, 'Nrmfar': 0.0},
}


def preset_values(name):
    """Flat {par: value} (RGB/XYZ tuples expanded to r g b / x y z) for a preset."""
    out = {}
    specs = par_specs()
    for k, v in PRESETS.get(name, {}).items():
        st = specs.get(k, (None,))[0]
        if st in ('RGB', 'XYZ') and isinstance(v, (tuple, list)):
            for c, x in zip('rgb' if st == 'RGB' else 'xyz', v):
                out[k + c] = x
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------------------------------- reference maths
def _np():
    import numpy
    return numpy


def curve(w, c):
    np = _np()
    return np.clip(np.asarray(w, dtype=np.float64), 0.0, 1.0) ** max(float(c), 1e-3)


def drive(w, near, far, c):
    """mxDrive: mix(far, near, clamp(w)^curve)."""
    t = curve(w, c)
    return far + (near - far) * t


def ref_pts_nearest(p, pts):
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    P = np.asarray(pts, dtype=np.float64).reshape(-1, 3)
    if not len(P):
        return np.full(p.shape[:-1], 1e9), np.full(p.shape[:-1], -1)
    d = np.linalg.norm(p[..., None, :] - P, axis=-1)
    return d.min(-1), d.argmin(-1)


def ref_pts_density(p, pts, r):
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    P = np.asarray(pts, dtype=np.float64).reshape(-1, 3)
    if not len(P):
        return np.zeros(p.shape[:-1])
    q = np.sum((p[..., None, :] - P) ** 2, axis=-1)
    return np.exp(-4.0 / max(r * r, 1e-10) * q).sum(-1)


def ref_eq_dist(mode, dist, dens, prad, R, full):
    np = _np()
    if mode == 1:
        return R * (1.0 - np.clip(np.asarray(dens) / max(full, 1e-6), 0.0, 1.0))
    return np.asarray(dist) - prad


def ref_field(pts, lo, size, R, prad_r=0.05):
    """The field pass: (R, R, R, 2) [z, y, x] = nearest distance, density at cell centres."""
    np = _np()
    lo, size = np.asarray(lo, dtype=np.float64), np.asarray(size, dtype=np.float64)
    g = (np.arange(R) + 0.5) / R
    Z, Y, X = np.meshgrid(g, g, g, indexing='ij')
    c = lo + np.stack([X, Y, Z], -1) * size
    d, _ = ref_pts_nearest(c, pts)
    return np.stack([d, ref_pts_density(c, pts, prad_r)], -1)


def ref_field_sample(field, p, lo, size):
    """pxFieldSample row 0 (trilinear, clamped, + distance to the box on x)."""
    np = _np()
    R = field.shape[0]
    p = np.asarray(p, dtype=np.float64)
    lo, size = np.asarray(lo, dtype=np.float64), np.maximum(np.asarray(size, dtype=np.float64), 1e-6)
    q = np.clip(p, lo, lo + size)
    g = (q - lo) / size * R - 0.5
    i = np.floor(g)
    f = g - i
    i = i.astype(int)

    def at(dx, dy, dz):
        x = np.clip(i[..., 0] + dx, 0, R - 1)
        y = np.clip(i[..., 1] + dy, 0, R - 1)
        z = np.clip(i[..., 2] + dz, 0, R - 1)
        return field[z, y, x]
    fx, fy, fz = f[..., 0:1], f[..., 1:2], f[..., 2:3]
    a = (at(0, 0, 0) * (1 - fx) + at(1, 0, 0) * fx) * (1 - fy) + (at(0, 1, 0) * (1 - fx) + at(1, 1, 0) * fx) * fy
    b = (at(0, 0, 1) * (1 - fx) + at(1, 0, 1) * fx) * (1 - fy) + (at(0, 1, 1) * (1 - fx) + at(1, 1, 1) * fx) * fy
    v = a * (1 - fz) + b * fz
    v = v.copy()
    v[..., 0] += np.linalg.norm(p - q, axis=-1)
    return v


def _comb(a, b, comb):
    np = _np()
    if comb == 1:
        return a + b
    if comb == 2:
        return a * b
    if comb == 3:
        return a + b - a * b
    return np.maximum(a, b)


def ref_weight(p, rows, pts=None):
    """mxProx weight w (no ragged noise) at world points p from packed uMX rows (+ the point set, nearest/density
    brute force = the direct path). Mirrors prox_mat_common.glsl mxProx."""
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    g0, prox, rag = rows[row_index('G0')], rows[row_index('PROX')], rows[row_index('RAG')]
    pts2 = rows[row_index('PTS2')]
    neff, path, ptm, flip = int(round(g0[0])), int(round(g0[1])), int(round(g0[2])), g0[3] > 0.5
    R, k, shape, comb = prox[0], prox[1], int(round(prox[2])), int(round(prox[3]))
    have_e = neff > 0
    we = PXL.ref_prox_w(p, rows[:E_ROWS], (1 << neff) - 1, neff, R, k, shape, comb) if have_e else None
    wp = None
    if path > 0 and pts is not None and ptm > 0:
        P = np.asarray(pts, dtype=np.float64).reshape(-1, 3)[:ptm]
        prad = rows[row_index('PTS')][3]
        dist, _ = ref_pts_nearest(p, P)
        dens = ref_pts_density(p, P, max(prad, 1e-4)) if int(round(pts2[0])) == 1 else 0.0
        wp = PXL.ref_fall(ref_eq_dist(int(round(pts2[0])), dist, dens, prad, R, pts2[1]), R, k, shape) * rag[3]
    if we is None and wp is None:
        w = np.zeros(p.shape[:-1])
    elif we is None:
        w = wp
    elif wp is None:
        w = we
    else:
        w = _comb(we, wp, comb)
    w = w * rag[2]
    return 1.0 - w if flip else w


def ref_push(p, rows, nrm, pts=None):
    """Dispmode push along the given normals: p + n * drive(w, Dispnear, Dispfar, Dispcurve)."""
    np = _np()
    d = rows[row_index('DSP')]
    w = ref_weight(p, rows, pts)
    a = drive(w, d[0], d[1], d[2])
    return np.asarray(p, dtype=np.float64) + np.asarray(nrm, dtype=np.float64) * a[..., None], a
