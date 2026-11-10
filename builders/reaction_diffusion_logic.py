"""reaction_diffusion_logic: pure logic + numpy reference of GN_reaction_diffusion (no td import).

Tests: test/test_reaction_diffusion.py. Build doc: docs/builds/reaction_diffusion.md.
Research: docs/research/O_generative_simulations.md 4.2 and BN_fluid_cloth_sims.md 5.9 (Gray-Scott after Karl Sims'
"Reaction-Diffusion Tutorial": 3x3 Laplacian centre -1, edges 0.2, diagonals 0.05; DA 1, DB 0.5, dt 1). Preset
(f, k) pairs from Sims' page (coral, mitosis) and the well known Pearson / xmorphia regimes (worms, spots, waves,
mazes, solitons, holes, chaos, u-skate), checked in this scheme with the reference (6000 steps, 12 spots seed): the
literature pairs for spots (.035/.065) and waves (.014/.045) die out here, so spots = .03/.0625 (stable spots, cover
~0.17) and waves = .018/.051 (cover keeps moving 0.08..0.12). The numpy reference uses the SAME formulas, hash and edge rules as
builders/glsl/rd_*.glsl so a live download of out2 can be compared with it (docs/builds/reaction_diffusion.md).
Copied into the COMP's `rd_logic` Text DAT: the engine Script CHOP calls engine_step() once per frame.
numpy is imported lazily (the TD runtime part is plain Python, T-48). No limits (user rule). ASCII only.

State texture (rgba32float, sim res, arrays here are [y, x], row 0 = bottom like numpyArray):
  .r = A (substrate, 1 at rest), .g = B (activator), .b = local morph from effectors/points (decays by Morphdecay),
  .a = solid flag (in2 mask; solid cells are held at A = 1, B = 0).
Per pixel: m = Morph + Mapamt * map(uv) + state.b + Mapimg * in4;  f = mix(fA, fB, m) + Feedoff,
  k = mix(kA, kB, m) + Killoff  (Mapmode pearson: f along y Fmin..Fmax, k along x Kmin..Kmax).
  lap = (1 - An) * lap9 + An * 0.6 * d2/dd2 (anisotropic, bilinear along the direction d; 0.6 = trace match of lap9)
  A' = A + (Da lapA - A B^2 + f (1 - A)) dt,  B' = B + (Db lapB + A B^2 - (k + f) B) dt  (Clampstate: 0..1).
  Flow (advected variant): the whole stencil is read at p - v (semi-Lagrangian, bilinear), v in cells per step.
"""
import math
import random

WG = 8
NROWS = 32                 # injector rows (effectors + points + mouse + bursts), 2 vec4 texels each in uRows
ROW_TEXELS = 2
LAP_EDGE, LAP_DIAG = 0.2, 0.05
ANISO_TRACE = 0.6          # lap9 ~ 0.3 * laplacian -> one-direction second derivative gets 2 * 0.3
EPS_T = 1e-9

# Preset table: name -> (f, k). Da / Db are global pars (Sims: 1.0 / 0.5).
PRESETS = [
    ('coral', 0.0545, 0.062),
    ('mitosis', 0.0367, 0.0649),
    ('worms', 0.078, 0.061),
    ('spots', 0.03, 0.0625),
    ('waves', 0.018, 0.051),
    ('mazes', 0.029, 0.057),
    ('solitons', 0.025, 0.06),
    ('holes', 0.039, 0.058),
    ('chaos', 0.026, 0.051),
    ('uskate', 0.062, 0.06093),
    ('custom', None, None),
]
PRESET_NAMES = [p[0] for p in PRESETS]
PRESET_LABELS = ['Coral', 'Mitosis', 'Worms', 'Spots', 'Waves', 'Mazes', 'Solitons', 'Holes', 'Chaos', 'U-Skate',
                 'Custom (Customf / Customk)']
EDGES = ['wrap', 'clamp']
SEEDMODES = ['center', 'spots', 'noise', 'ring', 'stripes', 'image', 'text', 'clear']
MAPMODES = ['none', 'x', 'y', 'radial', 'noise', 'pearson']
ANISOMODES = ['off', 'angle', 'radial', 'swirl', 'flow', 'noise']
FLOWMODES = ['off', 'input', 'drift', 'swirl', 'curl']
FALLOFFS = ['gauss', 'linear', 'hard', 'ring']
LFOS = ['off', 'sine', 'triangle', 'saw']
AUDIOMODES = ['off', 'kick', 'level', 'morph']
BURSTPATTERNS = ['random', 'center', 'ring']
MOUSEMODES = ['off', 'screen']
VALUEMODES = ['b', 'ab', 'a', 'edge']
COLORMODES = ['palette', 'ramp', 'raw', 'gray']
ALPHAMODES = ['opaque', 'value']
TESTMODES = ['off', 'fixed']
KIND_EFF, KIND_POINT, KIND_MOUSE, KIND_BURST = 0, 1, 2, 3
PALETTES = {
    'prism': ((0.02, 0.0, 0.06), (0.25, 0.05, 0.55), (0.85, 0.15, 0.65), (1.0, 0.55, 0.3), (1.0, 0.95, 0.85)),
    'ink': ((0.95, 0.93, 0.88), (0.75, 0.72, 0.68), (0.35, 0.33, 0.32), (0.08, 0.08, 0.1), (0.0, 0.0, 0.0)),
    'bio': ((0.0, 0.02, 0.03), (0.0, 0.2, 0.25), (0.0, 0.6, 0.55), (0.5, 1.0, 0.6), (0.95, 1.0, 0.9)),
    'fire': ((0.0, 0.0, 0.0), (0.35, 0.02, 0.0), (0.9, 0.25, 0.0), (1.0, 0.7, 0.1), (1.0, 1.0, 0.8)),
    'ice': ((0.0, 0.01, 0.05), (0.02, 0.1, 0.3), (0.1, 0.4, 0.8), (0.5, 0.8, 1.0), (1.0, 1.0, 1.0)),
    'mono': ((0.0, 0.0, 0.0), (0.25, 0.25, 0.25), (0.5, 0.5, 0.5), (0.75, 0.75, 0.75), (1.0, 1.0, 1.0)),
}
PALETTE_NAMES = ['prism', 'ink', 'bio', 'fire', 'ice', 'mono', 'custom']

# Custom parameters: (page, [(Name, style, default, opts)]). Float ranges are slider ranges only (no clamps).
PAGES = [
    ('Sim', [
        ('Simh', 'Int', 448, {'min': 32, 'max': 2048, 'clampmin': 8, 'label': 'Sim cells (height)'}),
        ('Resw', 'Int', 1080, {'min': 64, 'max': 3840, 'clampmin': 1, 'label': 'Out width'}),
        ('Resh', 'Int', 1920, {'min': 64, 'max': 3840, 'clampmin': 1, 'label': 'Out height'}),
        ('Steps', 'Int', 8, {'min': 1, 'max': 64, 'clampmin': 1, 'label': 'Steps per frame'}),
        # perf wave 27 Oct (b3): up to 8 steps per dispatch in shared memory (iso, no flow); off = one dispatch per step
        ('Fusesteps', 'Toggle', True, {'label': 'Fuse steps (8 per dispatch)'}),
        ('Dt', 'Float', 1.0, {'min': 0, 'max': 1.2, 'label': 'Dt per step'}),
        ('Da', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Diffusion A'}),
        ('Db', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Diffusion B'}),
        ('Edge', 'Menu', 'wrap', {'names': EDGES, 'labels': ['Wrap', 'Clamp'], 'label': 'Edges'}),
        ('Clampstate', 'Toggle', True, {'label': 'Clamp A/B to 0..1'}),
        ('Feedoff', 'Float', 0.0, {'min': -0.02, 'max': 0.02, 'label': 'Feed offset'}),
        ('Killoff', 'Float', 0.0, {'min': -0.01, 'max': 0.01, 'label': 'Kill offset'}),
    ]),
    ('Preset', [
        ('Preseta', 'Menu', 'coral', {'names': PRESET_NAMES, 'labels': PRESET_LABELS, 'label': 'Preset A'}),
        ('Presetb', 'Menu', 'mitosis', {'names': PRESET_NAMES, 'labels': PRESET_LABELS, 'label': 'Preset B'}),
        ('Morph', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Morph A -> B'}),
        ('Morphgo', 'Pulse', None, {'label': 'Morph go (A <-> B)'}),
        ('Morphtime', 'Float', 4.0, {'min': 0, 'max': 30, 'label': 'Morph go time s'}),
        ('Morphlfo', 'Menu', 'off', {'names': LFOS, 'labels': ['Off', 'Sine', 'Triangle', 'Saw'], 'label': 'Morph LFO'}),
        ('Morphrate', 'Float', 0.05, {'min': 0, 'max': 2, 'label': 'LFO rate Hz'}),
        ('Morphdepth', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'LFO depth'}),
        ('Mapmode', 'Menu', 'none', {'names': MAPMODES, 'labels': ['None', 'Along x', 'Along y', 'Radial', 'Noise',
                                                                 'Pearson map (f by y, k by x)'], 'label': 'Morph map'}),
        ('Mapamt', 'Float', 0.5, {'min': -2, 'max': 2, 'label': 'Map amount'}),
        ('Mapscale', 'Float', 3.0, {'min': 0.1, 'max': 20, 'label': 'Map noise scale'}),
        ('Mapimg', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Morph from in4 TOP'}),
        ('Fmin', 'Float', 0.01, {'min': 0, 'max': 0.1, 'label': 'Pearson f min'}),
        ('Fmax', 'Float', 0.09, {'min': 0, 'max': 0.1, 'label': 'Pearson f max'}),
        ('Kmin', 'Float', 0.045, {'min': 0.03, 'max': 0.075, 'label': 'Pearson k min'}),
        ('Kmax', 'Float', 0.07, {'min': 0.03, 'max': 0.075, 'label': 'Pearson k max'}),
        ('Customf', 'Float', 0.055, {'min': 0, 'max': 0.1, 'label': 'Custom f'}),
        ('Customk', 'Float', 0.062, {'min': 0.03, 'max': 0.075, 'label': 'Custom k'}),
    ]),
    ('Seed', [
        ('Seedmode', 'Menu', 'spots', {'names': SEEDMODES, 'labels': ['Centre square', 'Random spots', 'Noise', 'Ring',
                                                                     'Stripes', 'Image (in1)', 'Text', 'Clear'],
                                       'label': 'Seed on reset'}),
        ('Seedsize', 'Float', 0.04, {'min': 0.002, 'max': 0.3, 'label': 'Seed size (heights)'}),
        ('Seedcount', 'Int', 24, {'min': 1, 'max': 200, 'clampmin': 0, 'label': 'Spot count'}),
        ('Seeddensity', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Noise density'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
        ('Seedtext', 'Str', 'PRISM', {'label': 'Seed text'}),
        ('Textsize', 'Float', 0.12, {'min': 0.01, 'max': 0.5, 'label': 'Text size (heights)'}),
        ('Inject', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Continuous inject (in1 / text)'}),
        ('Injectsrc', 'Menu', 'image', {'names': ['image', 'text'], 'labels': ['Image (in1)', 'Text'],
                                        'label': 'Inject source'}),
        ('Reseed', 'Pulse', None, {'label': 'Reseed (new seed + reset)'}),
        ('Reset', 'Pulse', None, {'label': 'Reset'}),
    ]),
    ('Flow', [
        ('Anisomode', 'Menu', 'off', {'names': ANISOMODES, 'labels': ['Off', 'Angle', 'Radial', 'Swirl', 'Along flow',
                                                                      'Noise field'], 'label': 'Anisotropy'}),
        ('Aniso', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Anisotropy amount'}),
        ('Anisoangle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Angle deg'}),
        ('Anisoscale', 'Float', 2.0, {'min': 0.1, 'max': 20, 'label': 'Noise field scale'}),
        ('Flowmode', 'Menu', 'off', {'names': FLOWMODES, 'labels': ['Off', 'Input (in3 RG)', 'Drift', 'Swirl',
                                                                    'Curl noise'], 'label': 'Flow advection'}),
        ('Flowgain', 'Float', 0.3, {'min': 0, 'max': 2, 'label': 'Flow gain'}),
        ('Flowx', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Drift x (cells/step)'}),
        ('Flowy', 'Float', 0.1, {'min': -1, 'max': 1, 'label': 'Drift y (cells/step)'}),
        ('Flowscale', 'Float', 3.0, {'min': 0.1, 'max': 20, 'label': 'Curl noise scale'}),
        ('Flowspeed', 'Float', 0.1, {'min': 0, 'max': 2, 'label': 'Curl noise speed'}),
    ]),
    ('Inject', [
        ('Effon', 'Toggle', True, {'label': 'Effectors on'}),
        ('Effectors', 'Str', 'eff*', {'label': 'Effector Nulls (names/paths/patterns)', 'menu': 'objects@'}),
        ('Planeh', 'Float', 1.0, {'min': 0.1, 'max': 10, 'label': 'Plane height (world units)'}),
        ('Effradius', 'Float', 0.08, {'min': 0.005, 'max': 0.5, 'label': 'Effector radius'}),
        ('Effstrength', 'Float', 0.05, {'min': -1, 'max': 1, 'label': 'Effector inject (- erases)'}),
        ('Effmorph', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Effector morph'}),
        ('Efffalloff', 'Menu', 'gauss', {'names': FALLOFFS, 'labels': ['Gauss', 'Linear', 'Hard', 'Ring'],
                                         'label': 'Effector falloff'}),
        ('Morphdecay', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Morph memory (0 = none)'}),
        ('Maskthresh', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Mask threshold (in2)'}),
        ('Pointradius', 'Float', 0.03, {'min': 0.002, 'max': 0.3, 'label': 'in5 point radius'}),
        ('Mousemode', 'Menu', 'off', {'names': MOUSEMODES, 'labels': ['Off', 'Screen mouse (left button)'],
                                      'label': 'Mouse'}),
        ('Mouseradius', 'Float', 0.03, {'min': 0.002, 'max': 0.3, 'label': 'Mouse radius'}),
        ('Mousestrength', 'Float', 1.0, {'min': -1, 'max': 1, 'label': 'Mouse inject'}),
    ]),
    ('Audio', [
        ('Audiomode', 'Menu', 'off', {'names': AUDIOMODES, 'labels': ['Off', 'Kick bursts', 'Level spots',
                                                                     'Level morph'], 'label': 'Audio (in6)'}),
        ('Audiogain', 'Float', 4.0, {'min': 0, 'max': 20, 'label': 'Audio gain'}),
        ('Lowhz', 'Float', 150.0, {'min': 20, 'max': 1000, 'label': 'Low band Hz'}),
        ('Kickthresh', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Kick threshold'}),
        ('Refractory', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Kick refractory s'}),
        ('Audiomorph', 'Float', 0.5, {'min': -2, 'max': 2, 'label': 'Level -> morph'}),
        ('Burst', 'Pulse', None, {'label': 'Burst'}),
        ('Burstpattern', 'Menu', 'random', {'names': BURSTPATTERNS, 'labels': ['Random', 'Centre', 'Ring'],
                                            'label': 'Burst pattern'}),
        ('Burstcount', 'Int', 3, {'min': 1, 'max': 16, 'clampmin': 1, 'label': 'Burst spots'}),
        ('Burstradius', 'Float', 0.04, {'min': 0.002, 'max': 0.3, 'label': 'Burst radius'}),
        ('Burststrength', 'Float', 1.0, {'min': -1, 'max': 1, 'label': 'Burst inject'}),
    ]),
    ('Look', [
        ('Valuemode', 'Menu', 'b', {'names': VALUEMODES, 'labels': ['B', 'A - B', '1 - A', 'Edges |grad B|'],
                                    'label': 'Value'}),
        ('Lo', 'Float', 0.0, {'min': -0.5, 'max': 1, 'label': 'Value low'}),
        ('Hi', 'Float', 0.35, {'min': 0, 'max': 1.5, 'label': 'Value high'}),
        ('Colormode', 'Menu', 'palette', {'names': COLORMODES, 'labels': ['Palette', 'Ramp TOP', 'Raw A/B', 'Gray'],
                                          'label': 'Colour'}),
        ('Palette', 'Menu', 'prism', {'names': PALETTE_NAMES, 'labels': ['PRISM', 'Ink', 'Bio', 'Fire', 'Ice', 'Mono',
                                                                       'Custom (Pal1..5)'], 'label': 'Palette'}),
        ('Ramptop', 'TOP', '', {'label': 'Ramp TOP (empty = inner ramp)'}),
        ('Invert', 'Toggle', False, {'label': 'Invert value'}),
        ('Shade', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Emboss shade'}),
        ('Shadeheight', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Emboss height'}),
        ('Lightangle', 'Float', 135.0, {'min': -180, 'max': 180, 'label': 'Light angle deg'}),
        ('Edgeglow', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Edge glow'}),
        ('Edgecolor', 'RGB', (1.0, 0.9, 0.7), {'label': 'Edge colour'}),
        ('Exposure', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Exposure (stops)'}),
        ('Gamma', 'Float', 1.0, {'min': 0.2, 'max': 3, 'label': 'Gamma'}),
        ('Alpha', 'Menu', 'opaque', {'names': ALPHAMODES, 'labels': ['Opaque', 'Value alpha'], 'label': 'Alpha'}),
        ('Premult', 'Toggle', True, {'label': 'Premultiplied'}),
        ('Showeff', 'Toggle', True, {'label': 'Preview gizmos'}),
        ('Pal1', 'RGB', PALETTES['prism'][0], {'label': 'Palette 1 (low)'}),
        ('Pal2', 'RGB', PALETTES['prism'][1], {'label': 'Palette 2'}),
        ('Pal3', 'RGB', PALETTES['prism'][2], {'label': 'Palette 3'}),
        ('Pal4', 'RGB', PALETTES['prism'][3], {'label': 'Palette 4'}),
        ('Pal5', 'RGB', PALETTES['prism'][4], {'label': 'Palette 5 (high)'}),
    ]),
    ('Control', [
        ('Pause', 'Toggle', False, {'label': 'Pause'}),
        ('Step', 'Pulse', None, {'label': 'Step (while paused)'}),
        ('Stopat', 'Int', 0, {'min': 0, 'max': 5000, 'clampmin': 0, 'label': 'Pause at step (0 = off)'}),
        ('Testmode', 'Menu', 'off', {'names': TESTMODES, 'labels': ['Off', 'Fixed (no injectors/audio)'],
                                     'label': 'Test mode'}),
    ]),
]
PANEL_PAGES = [pg for pg, _ in PAGES]

# Compute passes (builders/glsl/rd_common.glsl + rd_<name>.glsl). inputs = wired op names (<= 3 per GLSL TOP).
# res: 'sim' (Simw x Simh) | 'out' (Resw x Resh) | 'half' (Resw/2 x Resh/2). fx_rd runs with npasses = Steps, or
# ceil(Steps / FUSE_H) when the fused path applies (fused_ok).
PASSES = [
    ('maps', {'inputs': ['mask_sel', 'mmap_sel', 'flow_sel'], 'vecs': ['uSim'], 'arrays': [], 'res': 'sim',
              'fmt': 'rgba32float'}),
    ('seed', {'inputs': ['state_fb', 'seed_prep', 'fx_maps'],
              'vecs': ['uSim', 'uCtl', 'uSeed', 'uInj'], 'arrays': ['uRows'], 'res': 'sim', 'fmt': 'rgba32float'}),
    ('rd', {'inputs': ['fx_seed', 'fx_maps'],
            'vecs': ['uSim', 'uCtl', 'uFK', 'uRD', 'uMorph', 'uPear', 'uAniso', 'uFlow', 'uFlow2', 'uBlk'], 'arrays': [],
            'res': 'sim', 'fmt': 'rgba32float'}),
    ('look', {'inputs': ['fx_rd', 'ramp_in'],
              'vecs': ['uSim', 'uLook', 'uLook2', 'uLook3', 'uEdge', 'uPal0', 'uPal1', 'uPal2', 'uPal3', 'uPal4'],
              'arrays': [], 'res': 'out', 'fmt': 'rgba16float'}),
    ('preview', {'inputs': ['fx_look'], 'vecs': ['uSim', 'uInj'], 'arrays': ['uRows'], 'res': 'half',
                 'fmt': 'rgba8fixed'}),
    ('stat', {'inputs': ['fx_rd'], 'vecs': ['uSim'], 'arrays': [], 'res': 'sim', 'fmt': 'rgba32float'}),
]
FUSE_H = 8                 # steps per dispatch on the fused path (rd_rd.glsl RD_H)


def fused_ok(fusesteps, flowmode, anisomode):
    """The fused (shared-memory) step path covers the isotropic, no-flow stencil only."""
    return bool(fusesteps) and flowmode == 'off' and anisomode == 'off'


def rd_npasses(steps, fused):
    steps = max(1, int(steps))
    return (steps + FUSE_H - 1) // FUSE_H if fused else steps


STAT_CHANS = ['meana', 'meanb', 'cover', 'edge', 'steps', 'cookms', 'level', 'morph', 'nrows']
ENGINE_CHANS = ['run', 'nsteps', 'reset', 'steps', 'time', 'ftime', 'morph', 'fa', 'ka', 'fb', 'kb', 'seed',
                'level', 'kick', 'nrows', 'testmode'] + ['pal%d%s' % (k, c) for k in range(5) for c in 'rgb']


def menu_index(names, val):
    try:
        return names.index(val)
    except ValueError:
        return 0


def sim_size(resw, resh, simh):
    """Sim grid (w, h): h = Simh, w follows the output aspect so cells stay square."""
    h = max(1, int(round(float(simh))))
    w = max(1, int(round(h * float(resw) / max(float(resh), 1.0))))
    return w, h


def preset_fk(name, customf=0.055, customk=0.062):
    for n, f, k in PRESETS:
        if n == name:
            return (float(customf), float(customk)) if f is None else (f, k)
    return PRESETS[0][1], PRESETS[0][2]


def palette_colours(name, custom=None):
    if name == 'custom' and custom:
        return tuple(tuple(float(v) for v in c) for c in custom)
    return PALETTES.get(name, PALETTES['prism'])


def palette_at(pal, t):
    """Piecewise-linear 5-key palette at t (clamped 0..1 for the lookup only)."""
    t = min(max(float(t), 0.0), 1.0) * (len(pal) - 1)
    i = min(int(math.floor(t)), len(pal) - 2)
    u = t - i
    return tuple(pal[i][c] * (1 - u) + pal[i + 1][c] * u for c in range(3))


def lfo(kind, phase):
    """0..1 LFO of phase (cycles)."""
    ph = phase - math.floor(phase)
    if kind == 'sine':
        return 0.5 - 0.5 * math.cos(2 * math.pi * ph)
    if kind == 'triangle':
        return 1.0 - abs(2.0 * ph - 1.0)
    if kind == 'saw':
        return ph
    return 0.0


def smooth01(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def block_rms(blocks):
    n = 0
    s = 0.0
    for b in blocks or ():
        for v in b:
            s += float(v) * float(v)
            n += 1
    return math.sqrt(s / n) if n else 0.0


def kick_step(st, t, level, thresh, refractory):
    st = dict(st) if st else {'prev': 0.0, 'last': None}
    fire = st['prev'] < thresh <= level and (st['last'] is None or t - st['last'] >= refractory - EPS_T)
    if fire:
        st['last'] = t
    st['prev'] = level
    return st, fire


def row(x, y, radius, strength, morph=0.0, falloff=0, kind=KIND_EFF):
    """One injector: centre uv (0..1, y up), radius in screen heights, inject strength (- erases), morph push."""
    return (float(x), float(y), float(radius), float(strength), float(morph), float(falloff), float(kind), 1.0)


def pack_rows(rows):
    """NROWS rows -> 2*NROWS texels x 4 channel lists (x y z w) for the uRows texture buffer; unused rows 0."""
    rows = list(rows)[:NROWS]
    flat = []
    for k in range(NROWS):
        flat.extend(rows[k] if k < len(rows) else (0.0,) * 8)
    return [flat[c::4] for c in range(4)]


def unpack_rows(chans):
    n = len(chans[0]) // ROW_TEXELS
    out = []
    for k in range(n):
        r = []
        for t in range(ROW_TEXELS):
            r.extend(chans[c][k * ROW_TEXELS + t] for c in range(4))
        if r[7] > 0.5:
            out.append(tuple(r))
    return out


def effector_row(e, p):
    """Effector Null -> row. e: tx ty sx sy + optional per-effector strength radius morph falloff active gain.
    World -> uv: the sim plane is Planeh tall, centred at the origin, Planeh * aspect wide."""
    if e.get('active') is not None and not e['active']:
        return None
    ph = max(float(p['planeh']), 1e-6)
    asp = float(p['aspect'])
    u = float(e['tx']) / (ph * asp) + 0.5
    v = float(e['ty']) / ph + 0.5
    sc = max(abs(float(e.get('sx', 1.0))), abs(float(e.get('sy', 1.0))))
    rad = e.get('radius')
    r = (float(p['effradius']) if rad is None else float(rad)) * sc / ph
    s = (float(p['effstrength']) if e.get('strength') is None else float(e['strength'])) * float(e.get('gain', 1.0))
    m = float(p['effmorph']) if e.get('morph') is None else float(e['morph'])
    fo = e.get('falloff')
    fo = int(p['efffalloff']) if fo is None else int(fo)
    return row(u, v, r, s, m, fo, KIND_EFF)


def burst_rows(n_burst, p, rng):
    pat = p['burstpattern']
    n = max(1, int(p['burstcount']))
    out = []
    for i in range(n):
        if pat == 'center':
            x, y = 0.5, 0.5
        elif pat == 'ring':
            a = 2 * math.pi * (i + 0.25 * n_burst) / n
            x = 0.5 + 0.25 * math.cos(a) / max(p['aspect'], 1e-6)
            y = 0.5 + 0.25 * math.sin(a)
        else:
            x, y = rng.random(), rng.random()
        out.append(row(x, y, p['burstradius'], p['burststrength'], 0.0, 0, KIND_BURST))
    return out


def points_from_chans(chans, p):
    """in5 CHOP: x y (uv) + optional radius strength morph channels, one point per sample."""
    xs, ys = chans.get('x') or chans.get('tx'), chans.get('y') or chans.get('ty')
    if not xs or not ys:
        return []
    n = min(len(xs), len(ys))

    def g(name, i, d):
        c = chans.get(name)
        return float(c[i]) if c and i < len(c) else d
    return [row(xs[i], ys[i], g('radius', i, p['pointradius']), g('strength', i, 1.0), g('morph', i, 0.0), 0,
                KIND_POINT) for i in range(n)]


ENGINE_DEFAULTS = {
    'steps': 8, 'pause': False, 'stopat': 0, 'preseta': 'coral', 'presetb': 'mitosis', 'customf': 0.055,
    'customk': 0.062, 'morph': 0.0, 'morphtime': 4.0, 'morphlfo': 'off', 'morphrate': 0.05, 'morphdepth': 0.0,
    'seed': 1, 'audiomode': 'off', 'audiogain': 4.0, 'kickthresh': 0.3, 'refractory': 0.15, 'audiomorph': 0.5,
    'burstpattern': 'random', 'burstcount': 3, 'burstradius': 0.04, 'burststrength': 1.0, 'effon': True,
    'planeh': 1.0, 'effradius': 0.08, 'effstrength': 0.05, 'effmorph': 0.0, 'efffalloff': 0, 'pointradius': 0.03,
    'mousemode': 'off', 'mouseradius': 0.03, 'mousestrength': 1.0, 'aspect': 1080.0 / 1920.0, 'flowspeed': 0.1,
    'testmode': 'off', 'palette': 'prism', 'custompal': None,
}


def engine_params(get, aspect=None):
    """get(ParName) -> value for each engine field (TD side: lambda n: getattr(P.par, n).eval())."""
    p = dict(ENGINE_DEFAULTS)
    m = {'steps': 'Steps', 'pause': 'Pause', 'stopat': 'Stopat', 'preseta': 'Preseta', 'presetb': 'Presetb',
         'customf': 'Customf', 'customk': 'Customk', 'morph': 'Morph', 'morphtime': 'Morphtime', 'morphlfo': 'Morphlfo',
         'morphrate': 'Morphrate', 'morphdepth': 'Morphdepth', 'seed': 'Seed', 'audiomode': 'Audiomode',
         'audiogain': 'Audiogain', 'kickthresh': 'Kickthresh', 'refractory': 'Refractory', 'audiomorph': 'Audiomorph',
         'burstpattern': 'Burstpattern', 'burstcount': 'Burstcount', 'burstradius': 'Burstradius',
         'burststrength': 'Burststrength', 'effon': 'Effon', 'planeh': 'Planeh', 'effradius': 'Effradius',
         'effstrength': 'Effstrength', 'effmorph': 'Effmorph', 'pointradius': 'Pointradius', 'mousemode': 'Mousemode',
         'mouseradius': 'Mouseradius', 'mousestrength': 'Mousestrength', 'flowspeed': 'Flowspeed',
         'testmode': 'Testmode', 'palette': 'Palette'}
    for k, n in m.items():
        try:
            p[k] = get(n)
        except Exception:
            pass
    try:
        p['efffalloff'] = menu_index(FALLOFFS, get('Efffalloff'))
    except Exception:
        pass
    try:
        p['custompal'] = [tuple(get('Pal%d%s' % (i, c)) for c in 'rgb') for i in range(1, 6)]
    except Exception:
        p['custompal'] = None
    if aspect is not None:
        p['aspect'] = float(aspect)
    return p


def new_engine(t=0.0):
    return {'t0': t, 'steps': 0, 'seed': None, 'kick': None, 'goal': 0.0, 'gofrom': 0.0, 'got0': None,
            'nburst': 0, 'pending': 0, 'rng': random.Random(1).getstate()}


def go_value(st, t, morphtime):
    """Morph-go offset: smoothstep from gofrom to goal over morphtime s (0 s = jump)."""
    if st['got0'] is None:
        return st['goal']
    T = float(morphtime)
    if T <= EPS_T:
        return st['goal']
    u = smooth01((t - st['got0']) / T)
    return st['gofrom'] + (st['goal'] - st['gofrom']) * u


def engine_step(st, t, p, inp=None, events=()):
    """One frame. Returns (state, out dict over ENGINE_CHANS, rows).
    inp: effectors (list of dicts), points (rows), mouse (u, v, down) or None, level (rms), low (rms).
    events: 'reset', 'reseed', 'step', 'burst', 'go'."""
    inp = inp or {}
    reset = st is None
    st = dict(st) if st else new_engine(t)
    ev = list(events)
    seed = int(p['seed'])
    if 'reseed' in ev:
        st['seed'] = (st['seed'] if st['seed'] is not None else seed) + 1
        reset = True
    if st['seed'] is None or ('reset' in ev and 'reseed' not in ev):
        st['seed'] = seed
    if 'reset' in ev:
        reset = True
    if reset:
        st['steps'] = 0
    if 'go' in ev:
        cur = go_value(st, t, p['morphtime'])
        st['gofrom'] = cur
        st['goal'] = 0.0 if st['goal'] > 0.5 else 1.0
        st['got0'] = t
    test = p['testmode'] == 'fixed'
    # steps this frame
    want = max(1, int(p['steps']))
    if p['pause'] and not reset:
        want = 1 if 'step' in ev else 0
    stopat = int(p['stopat'])
    if stopat > 0:
        want = max(0, min(want, stopat - st['steps']))
    st['steps'] += want
    # morph
    morph = float(p['morph']) + go_value(st, t, p['morphtime'])
    if p['morphlfo'] != 'off':
        morph += float(p['morphdepth']) * lfo(p['morphlfo'], (t - st['t0']) * float(p['morphrate']))
    level = float(inp.get('level', 0.0)) * float(p['audiogain'])
    low = float(inp.get('low', 0.0)) * float(p['audiogain'])
    kick = False
    if not test and p['audiomode'] != 'off':
        st['kick'], kick = kick_step(st['kick'], t, low, float(p['kickthresh']), float(p['refractory']))
        if p['audiomode'] == 'morph':
            morph += level * float(p['audiomorph'])
    # rows
    rng = random.Random()
    rng.setstate(st['rng'])
    rows = []
    if not test and want > 0:
        if p['effon']:
            for e in inp.get('effectors') or ():
                r = effector_row(e, p)
                if r is not None:
                    rows.append(r)
        rows.extend(inp.get('points') or ())
        mo = inp.get('mouse')
        if p['mousemode'] != 'off' and mo is not None and mo[2]:
            rows.append(row(mo[0], mo[1], p['mouseradius'], p['mousestrength'], 0.0, 0, KIND_MOUSE))
        nb = ev.count('burst') + (1 if kick and p['audiomode'] == 'kick' else 0)
        for _ in range(nb):
            rows.extend(burst_rows(st['nburst'], p, rng))
            st['nburst'] += 1
        if p['audiomode'] == 'level' and level > 1e-4:
            rows.append(row(rng.random(), rng.random(), float(p['burstradius']) * min(level, 4.0),
                            float(p['burststrength']) * min(level, 1.0), 0.0, 0, KIND_BURST))
    st['rng'] = rng.getstate()
    rows = rows[:NROWS]
    fa, ka = preset_fk(p['preseta'], p['customf'], p['customk'])
    fb, kb = preset_fk(p['presetb'], p['customf'], p['customk'])
    pal = palette_colours(p['palette'], p.get('custompal'))
    o = {'run': 1.0 if want > 0 or reset else 0.0, 'nsteps': float(want), 'reset': 1.0 if reset else 0.0,
         'steps': float(st['steps']), 'time': t - st['t0'], 'ftime': (t - st['t0']) * float(p['flowspeed']),
         'morph': morph, 'fa': fa, 'ka': ka, 'fb': fb, 'kb': kb, 'seed': float(st['seed']), 'level': level,
         'kick': 1.0 if kick else 0.0, 'nrows': float(len(rows)), 'testmode': 1.0 if test else 0.0}
    for k in range(5):
        for ci, c in enumerate('rgb'):
            o['pal%d%s' % (k, c)] = float(pal[k][ci])
    return st, o, rows


# ------------------------------------------------------------------------------------------------------------------
# numpy reference (same formulas as the shaders)

def _np():
    import numpy as np
    return np


M32 = 0xffffffff


def hash_u32(x):
    """lowbias32 (Wellons), uint32 wraparound, == rd_common.glsl hashu()."""
    np = _np()
    x = np.asarray(x).astype(np.uint64) & M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def hash3(i, j, s):
    """float in [0, 1) from three ints (== hash3() in GLSL): exact in float32 (24-bit)."""
    np = _np()
    i = np.asarray(i).astype(np.int64) & M32
    j = np.asarray(j).astype(np.int64) & M32
    s = np.asarray(s).astype(np.int64) & M32
    h = hash_u32(i + hash_u32(j + hash_u32(s)))
    return (h >> 8).astype(np.float64) * (1.0 / 16777216.0)


def vnoise(x, y, s):
    """Value noise in [0, 1): lattice hash3, smoothstep blend."""
    np = _np()
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    ix, iy = ix.astype(np.int64), iy.astype(np.int64)
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = hash3(ix, iy, s)
    b = hash3(ix + 1, iy, s)
    c = hash3(ix, iy + 1, s)
    d = hash3(ix + 1, iy + 1, s)
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


REF_DEFAULTS = {
    'aspect': 1080.0 / 1920.0, 'edge': 0, 'seedmode': 'spots', 'seedsize': 0.04, 'seedcount': 24,
    'seeddensity': 0.05, 'seed': 1, 'inject': 0.0, 'maskthresh': 0.5, 'morphdecay': 0.0,
    'fa': 0.0545, 'ka': 0.062, 'fb': 0.0367, 'kb': 0.0649, 'da': 1.0, 'db': 0.5, 'dt': 1.0, 'clamp': True,
    'morph': 0.0, 'mapmode': 'none', 'mapamt': 0.5, 'mapscale': 3.0, 'mapimg': 0.0, 'feedoff': 0.0, 'killoff': 0.0,
    'fmin': 0.01, 'fmax': 0.09, 'kmin': 0.045, 'kmax': 0.07,
    'anisomode': 'off', 'aniso': 0.6, 'anisoangle': 0.0, 'anisoscale': 2.0,
    'flowmode': 'off', 'flowgain': 0.3, 'flowx': 0.0, 'flowy': 0.1, 'flowscale': 3.0, 'ftime': 0.0,
}


def grid_uv(w, h):
    np = _np()
    X, Y = np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64))
    return X, Y, (X + 0.5) / w, (Y + 0.5) / h


def seed_pattern(w, h, p, img=None):
    """B at reset for Seedmode (img = seed luminance [h, w] for image / text)."""
    np = _np()
    X, Y, u, v = grid_uv(w, h)
    asp = w / float(h)
    dx, dy = (u - 0.5) * asp, v - 0.5
    size = float(p['seedsize'])
    mode = p['seedmode']
    s = int(p['seed'])
    B = np.zeros((h, w))
    if mode == 'center':
        B[np.maximum(abs(dx), abs(dy)) < size] = 1.0
    elif mode == 'spots':
        for k in range(int(p['seedcount'])):
            cx, cy = float(hash3(k, 1, s)), float(hash3(k, 2, s))
            rr = size * (0.5 + float(hash3(k, 3, s)))
            B[np.hypot((u - cx) * asp, v - cy) < rr] = 1.0
    elif mode == 'noise':
        B[hash3(X, Y, s) < float(p['seeddensity'])] = 1.0
    elif mode == 'ring':
        B[abs(np.hypot(dx, dy) - 0.25) < size * 0.5] = 1.0
    elif mode == 'stripes':
        q = dx / (size * 4.0)
        B[(q - np.floor(q)) < 0.25] = 1.0
    elif mode in ('image', 'text') and img is not None:
        B = np.clip(img, 0.0, 1.0)
    return B


def falloff(d, mode):
    np = _np()
    if mode == 1:
        return np.maximum(1.0 - d, 0.0)
    if mode == 2:
        return (d < 1.0).astype(np.float64)
    if mode == 3:
        return np.exp(-((d - 1.0) * 4.0) ** 2)
    return np.exp(-d * d)


def seed_pass(state, p, reset=False, run=True, img=None, maps=None, rows=()):
    """fx_seed. state [h, w, 4] (A, B, morph, solid). img = seed luminance; maps [h, w, 4] (mask, mmap, flow xy)."""
    np = _np()
    h, w = state.shape[:2]
    out = state.copy()
    if maps is None:
        maps = np.zeros((h, w, 4))
    solid = (maps[..., 0] > float(p['maskthresh'])).astype(np.float64)
    if reset:
        out[..., 0] = 1.0
        out[..., 1] = seed_pattern(w, h, p, img)
        out[..., 2] = 0.0
    elif not run:
        return out
    else:
        A, B = out[..., 0], out[..., 1]
        if img is not None and float(p['inject']) > 0:
            q = np.clip(float(p['inject']) * img, 0.0, 1.0)
            B = B + (1.0 - B) * q
        _, _, u, v = grid_uv(w, h)
        asp = w / float(h)
        infl = np.zeros((h, w))
        for r in rows:
            d = np.hypot((u - r[0]) * asp, v - r[1]) / max(r[2], 1e-6)
            wgt = falloff(d, int(r[5] + 0.5))
            s = r[3]
            if s >= 0:
                q = np.clip(s * wgt, 0.0, 1.0)
                B = B + (1.0 - B) * q
            else:
                q = np.clip(-s * wgt, 0.0, 1.0)
                A = A + (1.0 - A) * q
                B = B * (1.0 - q)
            infl = infl + wgt * r[4]
        out[..., 0], out[..., 1] = A, B
        out[..., 2] = out[..., 2] * float(p['morphdecay']) + infl
    out[..., 3] = solid
    out[solid > 0.5, 0] = 1.0
    out[solid > 0.5, 1] = 0.0
    return out


def _fetch(a, X, Y, edge):
    np = _np()
    h, w = a.shape[:2]
    if edge == 0:
        X, Y = np.mod(X, w), np.mod(Y, h)
    else:
        X, Y = np.clip(X, 0, w - 1), np.clip(Y, 0, h - 1)
    return a[Y, X]


def bilerp(a, px, py, edge):
    """Sample a [h, w, c] at texel-space positions (centres at i + 0.5)."""
    np = _np()
    x, y = px - 0.5, py - 0.5
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    x0, y0 = x0.astype(np.int64), y0.astype(np.int64)
    a00 = _fetch(a, x0, y0, edge)
    a10 = _fetch(a, x0 + 1, y0, edge)
    a01 = _fetch(a, x0, y0 + 1, edge)
    a11 = _fetch(a, x0 + 1, y0 + 1, edge)
    return (a00 * (1 - fx) + a10 * fx) * (1 - fy) + (a01 * (1 - fx) + a11 * fx) * fy


def flow_field(w, h, p, maps=None):
    """Velocity in cells per step for Flowmode (None = off)."""
    np = _np()
    mode = p['flowmode']
    if mode == 'off':
        return None
    _, _, u, v = grid_uv(w, h)
    asp = w / float(h)
    dx, dy = (u - 0.5) * asp, v - 0.5
    g = float(p['flowgain'])
    if mode == 'input':
        return maps[..., 2] * g, maps[..., 3] * g
    if mode == 'drift':
        return np.full((h, w), float(p['flowx'])), np.full((h, w), float(p['flowy']))
    if mode == 'swirl':
        return -dy * 2.0 * g, dx * 2.0 * g
    sc = float(p['flowscale'])
    nx, ny = u * asp * sc + float(p['ftime']), v * sc
    e = 0.01
    s = int(p['seed']) + 11
    dpdx = (vnoise(nx + e, ny, s) - vnoise(nx - e, ny, s)) / (2 * e)
    dpdy = (vnoise(nx, ny + e, s) - vnoise(nx, ny - e, s)) / (2 * e)
    return dpdy * g, -dpdx * g


def aniso_dir(w, h, p, vel=None):
    np = _np()
    mode = p['anisomode']
    if mode == 'off':
        return None
    _, _, u, v = grid_uv(w, h)
    asp = w / float(h)
    dx, dy = (u - 0.5) * asp, v - 0.5
    if mode == 'angle':
        a = math.radians(float(p['anisoangle']))
        return np.full((h, w), math.cos(a)), np.full((h, w), math.sin(a))
    if mode in ('radial', 'swirl'):
        n = np.maximum(np.hypot(dx, dy), 1e-6)
        ex, ey = dx / n, dy / n
        return (ex, ey) if mode == 'radial' else (-ey, ex)
    if mode == 'flow':
        if vel is None:
            return None
        n = np.hypot(vel[0], vel[1])
        ok = n > 1e-6
        return np.where(ok, vel[0] / np.maximum(n, 1e-6), 1.0), np.where(ok, vel[1] / np.maximum(n, 1e-6), 0.0)
    a = vnoise(u * asp * float(p['anisoscale']), v * float(p['anisoscale']), int(p['seed']) + 5) * (4 * math.pi)
    return np.cos(a), np.sin(a)


def morph_map(w, h, p, maps=None):
    np = _np()
    _, _, u, v = grid_uv(w, h)
    asp = w / float(h)
    mode = p['mapmode']
    if mode == 'x':
        m = u
    elif mode == 'y':
        m = v
    elif mode == 'radial':
        m = np.hypot((u - 0.5) * asp, v - 0.5) * 2.0
    elif mode == 'noise':
        m = vnoise(u * asp * float(p['mapscale']), v * float(p['mapscale']), int(p['seed']) + 7)
    else:
        m = np.zeros((h, w))
    out = float(p['morph']) + float(p['mapamt']) * m
    if maps is not None:
        out = out + float(p['mapimg']) * maps[..., 1]
    return out


def rd_pass(state, p, maps=None):
    """fx_rd: one Gray-Scott step (iso / anisotropic, optional flow advection)."""
    np = _np()
    h, w = state.shape[:2]
    X, Y, u, v = grid_uv(w, h)
    edge = int(p['edge'])
    vel = flow_field(w, h, p, maps)
    px, py = X + 0.5, Y + 0.5
    if vel is not None:
        px, py = px - vel[0], py - vel[1]
    S = lambda ox, oy: bilerp(state[..., :2], px + ox, py + oy, edge)  # noqa: E731
    a2 = state[..., :2]
    if vel is None:                                   # integer stencil: same numbers as bilerp at f = 0, faster
        if edge == 0:
            SI = lambda ox, oy: np.roll(a2, (-oy, -ox), (0, 1))  # noqa: E731
        else:
            pad = np.pad(a2, ((1, 1), (1, 1), (0, 0)), mode='edge')
            SI = lambda ox, oy: pad[1 + oy:1 + oy + h, 1 + ox:1 + ox + w]  # noqa: E731
    else:
        SI = S
    c = SI(0, 0)
    e4 = sum((SI(ox, oy) - c) for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    d4 = sum((SI(ox, oy) - c) for ox, oy in ((1, 1), (-1, 1), (1, -1), (-1, -1)))
    lap = LAP_EDGE * e4 + LAP_DIAG * d4               # sum of differences: exactly 0 on a uniform field
    d = aniso_dir(w, h, p, vel)
    if d is not None:
        an = float(p['aniso'])
        dd = S(d[0], d[1]) - 2.0 * c + S(-d[0], -d[1])
        lap = (1.0 - an) * lap + an * ANISO_TRACE * dd
    m = morph_map(w, h, p, maps) + state[..., 2]
    if p['mapmode'] == 'pearson':
        f = float(p['fmin']) + (float(p['fmax']) - float(p['fmin'])) * v + float(p['feedoff'])
        k = float(p['kmin']) + (float(p['kmax']) - float(p['kmin'])) * u + float(p['killoff'])
    else:
        f = float(p['fa']) + (float(p['fb']) - float(p['fa'])) * m + float(p['feedoff'])
        k = float(p['ka']) + (float(p['kb']) - float(p['ka'])) * m + float(p['killoff'])
    A, B = c[..., 0], c[..., 1]
    abb = A * B * B
    dt = float(p['dt'])
    A2 = A + (float(p['da']) * lap[..., 0] - abb + f * (1.0 - A)) * dt
    B2 = B + (float(p['db']) * lap[..., 1] + abb - (k + f) * B) * dt
    if p['clamp']:
        A2, B2 = np.clip(A2, 0, 1), np.clip(B2, 0, 1)
    out = state.copy()
    sol = state[..., 3] > 0.5
    out[..., 0] = np.where(sol, 1.0, A2)
    out[..., 1] = np.where(sol, 0.0, B2)
    return out


def new_state(w, h):
    np = _np()
    s = np.zeros((h, w, 4))
    s[..., 0] = 1.0
    return s


def run_fixed(steps=600, w=72, h=128, p=None):
    """Reset with Seedmode (default centre) then `steps` rd passes, no injectors (Testmode fixed)."""
    q = dict(REF_DEFAULTS)
    q['seedmode'] = 'center'
    q.update(p or {})
    st = seed_pass(new_state(w, h), q, reset=True)
    for _ in range(steps):
        st = rd_pass(st, q)
    return st


def stats(state):
    """== fx_stat + Analyze average: mean A, mean B, cover (B > 0.25), edge (mean |central grad B| * 0.5)."""
    np = _np()
    B = state[..., 1]
    gx = (np.roll(B, -1, 1) - np.roll(B, 1, 1)) * 0.5
    gy = (np.roll(B, -1, 0) - np.roll(B, 1, 0)) * 0.5
    return {'meana': float(state[..., 0].mean()), 'meanb': float(B.mean()), 'cover': float((B > 0.25).mean()),
            'edge': float(np.hypot(gx, gy).mean())}


def look_value(A, B, mode, lo, hi, invert=False, edge=None):
    np = _np()
    if mode == 'ab':
        val = A - B
    elif mode == 'a':
        val = 1.0 - A
    elif mode == 'edge':
        val = edge * 8.0 if edge is not None else B * 0
    else:
        val = B
    t = (val - lo) / max(hi - lo, 1e-6)
    return 1.0 - t if invert else t


def rel_l2(a, b):
    np = _np()
    n = float(np.sqrt((b * b).sum()))
    return float(np.sqrt(((a - b) ** 2).sum())) / max(n, 1e-12)
