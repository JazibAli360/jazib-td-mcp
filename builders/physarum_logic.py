"""physarum_logic: pure logic + numpy reference of GN_physarum (no td import).

Tests: test/test_physarum.py. Build doc: docs/builds/physarum.md. Research: docs/research/O_generative_simulations.md
4.3 (Jones 2010 / Jenson model: agents with a heading and three sensors - front-left, front, front-right; sense ->
rotate -> move -> deposit into a trail map -> 3x3 mean diffuse -> multiplicative decay). Reimplemented from that
description (no GPL / unlicensed code copied). Mac has no float atomics (F13): the deposit is a Render TOP of one
1-px point per agent with additive blending (exact sums in 32F), everything else is compute GLSL (T-46/T-47).
The numpy reference uses the SAME formulas, hash and edge rules as builders/glsl/ph_*.glsl, so a live download of
out2 / the agent texture can be compared with it. Copied into the COMP's `ph_logic` Text DAT: the engine Script CHOP
calls engine_step() once per frame. numpy is imported lazily (T-48). No limits (user rule). ASCII only.

Agent texture (rgba32float, side x side, side = ceil(sqrt(Agents))): r = x, g = y (sim texel units, row 0 = bottom),
b = heading (radians, kept in 0..2pi), a = species (0, 1, 2), -1 = unused slot (index >= Agents).
Trail texture (rgba32float, sim res): r g b = trail of species 0 1 2, a = 0.
One sim step per frame (each step needs a deposit render):
  sense: for species s, value(q) = dot(trail(q).rgb, W[s]) + Foodw * food(q) + field(q) (effector rows, + attract,
         - repel); W[s][s] = Selfw, W[s][o] = Otherw. q = floor(p + SO * dir(a + {SA, 0, -SA})).
  rotate (Jones): F > L and F > R: keep; F < L and F < R: +-RA (hash); L > R: +RA; R > L: -RA; else keep. Plus jitter.
  move: p += SS * dir(a); Edge wrap (mod) or bounce (mirror + heading reflected); masked target (in2): stay, random
  heading.
  deposit: trail[floor(p)][s] += Deposit.
  trail: T1 = T + D; T2 = T1 + Diffuse * (mean3x3(T1) - T1); T3 = T2 * (1 - Decay) + injects (rows, food); mask -> 0.
"""
import math
import random

WG = 8
NROWS = 32
ROW_TEXELS = 2
EPS_T = 1e-9
TWO_PI = 2.0 * math.pi
DEG = math.pi / 180.0
NSPECIES = 3

# Preset table: name -> (sensor angle deg, sensor offset cells, rotate angle deg, step cells, deposit, decay, diffuse,
# jitter deg). Tuned with the reference at 270x480 (test/test_physarum.py keeps them alive: cover in range).
PRESET_FIELDS = ['sa', 'so', 'ra', 'ss', 'dep', 'decay', 'diffuse', 'jitter']
PRESETS = [
    ('network', (22.5, 9.0, 45.0, 1.0, 1.0, 0.10, 1.0, 0.0)),
    ('veins', (30.0, 20.0, 15.0, 1.5, 1.0, 0.05, 0.6, 0.0)),
    ('cells', (45.0, 14.0, 45.0, 1.0, 1.0, 0.15, 1.0, 0.0)),
    ('coral', (11.25, 28.0, 11.25, 1.2, 1.0, 0.08, 0.5, 2.0)),
    ('worms', (90.0, 4.0, 45.0, 1.5, 1.0, 0.2, 1.0, 0.0)),
    ('storm', (22.5, 12.0, 45.0, 3.0, 1.0, 0.2, 1.0, 10.0)),
    ('mesh', (60.0, 6.0, 30.0, 1.0, 1.0, 0.12, 1.0, 0.0)),
    ('custom', None),
]
PRESET_NAMES = [p[0] for p in PRESETS]
PRESET_LABELS = ['Network (Jones)', 'Veins', 'Cells', 'Coral', 'Worms', 'Storm', 'Mesh', 'Custom (Custom* pars)']
EDGES = ['wrap', 'bounce']
SEEDMODES = ['random', 'disc', 'ring', 'spiral', 'lines', 'image', 'text', 'center']
HEADINGS = ['random', 'outward', 'inward', 'swirl']
SPECIESMODES = ['interleave', 'bands', 'rings']
FALLOFFS = ['gauss', 'linear', 'hard', 'ring']
LFOS = ['off', 'sine', 'triangle', 'saw']
AUDIOMODES = ['off', 'kick', 'level']
AUDIOTARGETS = ['step', 'deposit', 'sensor', 'morph']
BURSTPATTERNS = ['random', 'center', 'ring']
MOUSEMODES = ['off', 'attract', 'repel']
VALUEMODES = ['soft', 'linear', 'log']
COLORMODES = ['species', 'palette', 'ramp', 'gray']
ALPHAMODES = ['opaque', 'value']
TESTMODES = ['off', 'fixed']
KIND_EFF, KIND_POINT, KIND_MOUSE, KIND_BURST = 0, 1, 2, 3
PALETTES = {
    'prism': ((0.02, 0.0, 0.06), (0.25, 0.05, 0.55), (0.85, 0.15, 0.65), (1.0, 0.55, 0.3), (1.0, 0.95, 0.85)),
    'bio': ((0.0, 0.02, 0.03), (0.0, 0.2, 0.25), (0.0, 0.6, 0.55), (0.5, 1.0, 0.6), (0.95, 1.0, 0.9)),
    'gold': ((0.0, 0.0, 0.0), (0.25, 0.1, 0.0), (0.8, 0.45, 0.05), (1.0, 0.8, 0.3), (1.0, 1.0, 0.9)),
    'ice': ((0.0, 0.01, 0.05), (0.02, 0.1, 0.3), (0.1, 0.4, 0.8), (0.5, 0.8, 1.0), (1.0, 1.0, 1.0)),
    'mono': ((0.0, 0.0, 0.0), (0.25, 0.25, 0.25), (0.5, 0.5, 0.5), (0.75, 0.75, 0.75), (1.0, 1.0, 1.0)),
}
PALETTE_NAMES = ['prism', 'bio', 'gold', 'ice', 'mono', 'custom']
SPECIES_COLOURS = ((0.79, 0.28, 0.91), (1.0, 0.27, 0.5), (1.0, 0.73, 0.01))   # PRISM orchid, pink, gold


def _preset_pars():
    out = []
    lab = {'sa': ('Sensor angle deg', 0, 180), 'so': ('Sensor distance cells', 0, 64), 'ra': ('Rotate angle deg', 0, 180),
           'ss': ('Step cells/frame', 0, 8), 'dep': ('Deposit', 0, 5), 'decay': ('Decay per frame', 0, 1),
           'diffuse': ('Diffuse (3x3 mix)', 0, 1), 'jitter': ('Jitter deg', 0, 90)}
    base = dict(zip(PRESET_FIELDS, PRESETS[0][1]))
    for f in PRESET_FIELDS:
        label, lo, hi = lab[f]
        out.append(('Custom' + f, 'Float', base[f], {'min': lo, 'max': hi, 'label': 'Custom ' + label}))
    return out


# Custom parameters: (page, [(Name, style, default, opts)]). Float ranges are slider ranges only (no clamps).
PAGES = [
    ('Sim', [
        ('Agents', 'Int', 262144, {'min': 1024, 'max': 4194304, 'clampmin': 1, 'label': 'Agents'}),
        ('Simh', 'Int', 960, {'min': 64, 'max': 3840, 'clampmin': 8, 'label': 'Trail cells (height)'}),
        ('Resw', 'Int', 1080, {'min': 64, 'max': 3840, 'clampmin': 1, 'label': 'Out width'}),
        ('Resh', 'Int', 1920, {'min': 64, 'max': 3840, 'clampmin': 1, 'label': 'Out height'}),
        ('Edge', 'Menu', 'wrap', {'names': EDGES, 'labels': ['Wrap', 'Bounce'], 'label': 'Edges'}),
        ('Species', 'Int', 1, {'min': 1, 'max': 3, 'clampmin': 1, 'label': 'Species (1-3)'}),
        ('Speciesmode', 'Menu', 'interleave', {'names': SPECIESMODES, 'labels': ['Interleave', 'Bands (x)', 'Rings'],
                                               'label': 'Species layout'}),
        ('Selfw', 'Float', 1.0, {'min': -2, 'max': 2, 'label': 'Own trail weight'}),
        ('Otherw', 'Float', -1.0, {'min': -2, 'max': 2, 'label': 'Other species weight (- avoid)'}),
        ('Speedspread', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Species speed spread'}),
    ]),
    ('Preset', [
        ('Preseta', 'Menu', 'network', {'names': PRESET_NAMES, 'labels': PRESET_LABELS, 'label': 'Preset A'}),
        ('Presetb', 'Menu', 'cells', {'names': PRESET_NAMES, 'labels': PRESET_LABELS, 'label': 'Preset B'}),
        ('Morph', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Morph A -> B'}),
        ('Morphgo', 'Pulse', None, {'label': 'Morph go (A <-> B)'}),
        ('Morphtime', 'Float', 4.0, {'min': 0, 'max': 30, 'label': 'Morph go time s'}),
        ('Morphlfo', 'Menu', 'off', {'names': LFOS, 'labels': ['Off', 'Sine', 'Triangle', 'Saw'], 'label': 'Morph LFO'}),
        ('Morphrate', 'Float', 0.05, {'min': 0, 'max': 2, 'label': 'LFO rate Hz'}),
        ('Morphdepth', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'LFO depth'}),
        ('Sagain', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'x Sensor angle'}),
        ('Sogain', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'x Sensor distance'}),
        ('Ragain', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'x Rotate angle'}),
        ('Ssgain', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'x Step'}),
        ('Depgain', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'x Deposit'}),
        ('Decaygain', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'x Decay'}),
        ('Diffgain', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'x Diffuse'}),
        ('Jittergain', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'x Jitter'}),
    ] + _preset_pars()),
    ('Seed', [
        ('Seedmode', 'Menu', 'disc', {'names': SEEDMODES, 'labels': ['Random', 'Disc', 'Ring', 'Spiral', 'Lines',
                                                                    'Image (in1)', 'Text', 'Centre point'],
                                      'label': 'Agent seed'}),
        ('Heading', 'Menu', 'random', {'names': HEADINGS, 'labels': ['Random', 'Outward', 'Inward', 'Swirl'],
                                       'label': 'Start heading'}),
        ('Seedsize', 'Float', 0.3, {'min': 0.01, 'max': 1, 'label': 'Seed size (heights)'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
        ('Respawn', 'Float', 0.002, {'min': 0, 'max': 0.05, 'label': 'Respawn per frame (fraction)'}),
        ('Seedtext', 'Str', 'PRISM', {'label': 'Seed text'}),
        ('Textsize', 'Float', 0.12, {'min': 0.01, 'max': 0.5, 'label': 'Text size (heights)'}),
        ('Reseed', 'Pulse', None, {'label': 'Reseed (new seed + reset)'}),
        ('Reset', 'Pulse', None, {'label': 'Reset'}),
    ]),
    ('Food', [
        ('Foodw', 'Float', 0.0, {'min': -5, 'max': 5, 'label': 'Food map attract (in1 / text)'}),
        ('Foodinject', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Food -> trail inject'}),
        ('Foodsrc', 'Menu', 'image', {'names': ['image', 'text'], 'labels': ['Image (in1)', 'Text'],
                                      'label': 'Food source'}),
        ('Maskthresh', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Mask threshold (in2)'}),
        ('Effon', 'Toggle', True, {'label': 'Effectors on'}),
        ('Effectors', 'Str', 'eff*', {'label': 'Effector Nulls (names/paths/patterns)', 'menu': 'objects@'}),
        ('Planeh', 'Float', 1.0, {'min': 0.1, 'max': 10, 'label': 'Plane height (world units)'}),
        ('Effradius', 'Float', 0.15, {'min': 0.005, 'max': 0.5, 'label': 'Effector radius'}),
        ('Effstrength', 'Float', 10.0, {'min': -20, 'max': 20, 'label': 'Effector attract (- repels)'}),
        ('Effdeposit', 'Float', 0.0, {'min': 0, 'max': 5, 'label': 'Effector trail inject'}),
        ('Efffalloff', 'Menu', 'gauss', {'names': FALLOFFS, 'labels': ['Gauss', 'Linear', 'Hard', 'Ring'],
                                         'label': 'Effector falloff'}),
        ('Pointradius', 'Float', 0.05, {'min': 0.002, 'max': 0.3, 'label': 'in5 point radius'}),
        ('Mousemode', 'Menu', 'off', {'names': MOUSEMODES, 'labels': ['Off', 'Attract (left button)',
                                                                     'Repel (left button)'], 'label': 'Mouse'}),
        ('Mouseradius', 'Float', 0.08, {'min': 0.002, 'max': 0.3, 'label': 'Mouse radius'}),
        ('Mousestrength', 'Float', 5.0, {'min': 0, 'max': 20, 'label': 'Mouse strength'}),
    ]),
    ('Audio', [
        ('Audiomode', 'Menu', 'off', {'names': AUDIOMODES, 'labels': ['Off', 'Kick bursts', 'Level'],
                                      'label': 'Audio (in6)'}),
        ('Audiotarget', 'Menu', 'step', {'names': AUDIOTARGETS, 'labels': ['Step', 'Deposit', 'Sensor angle',
                                                                          'Morph'], 'label': 'Level drives'}),
        ('Audiogain', 'Float', 4.0, {'min': 0, 'max': 20, 'label': 'Audio gain'}),
        ('Audioamt', 'Float', 1.0, {'min': -2, 'max': 4, 'label': 'Level amount'}),
        ('Lowhz', 'Float', 150.0, {'min': 20, 'max': 1000, 'label': 'Low band Hz'}),
        ('Kickthresh', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Kick threshold'}),
        ('Refractory', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Kick refractory s'}),
        ('Kickspeed', 'Float', 3.0, {'min': 1, 'max': 10, 'label': 'Kick step x'}),
        ('Kickrelease', 'Float', 0.3, {'min': 0.01, 'max': 2, 'label': 'Kick release s'}),
        ('Burst', 'Pulse', None, {'label': 'Burst'}),
        ('Burstpattern', 'Menu', 'random', {'names': BURSTPATTERNS, 'labels': ['Random', 'Centre', 'Ring'],
                                            'label': 'Burst pattern'}),
        ('Burstcount', 'Int', 3, {'min': 1, 'max': 16, 'clampmin': 1, 'label': 'Burst spots'}),
        ('Burstradius', 'Float', 0.08, {'min': 0.002, 'max': 0.3, 'label': 'Burst radius'}),
        ('Burststrength', 'Float', -8.0, {'min': -20, 'max': 20, 'label': 'Burst attract (- scatters)'}),
        ('Burstframes', 'Int', 6, {'min': 1, 'max': 60, 'clampmin': 1, 'label': 'Burst frames'}),
    ]),
    ('Look', [
        ('Valuemode', 'Menu', 'soft', {'names': VALUEMODES, 'labels': ['Soft (1 - exp)', 'Linear Lo..Hi', 'Log'],
                                       'label': 'Tone'}),
        ('Lo', 'Float', 0.0, {'min': 0, 'max': 5, 'label': 'Value low'}),
        ('Hi', 'Float', 8.0, {'min': 0.01, 'max': 60, 'label': 'Value high / soft scale'}),
        ('Colormode', 'Menu', 'species', {'names': COLORMODES, 'labels': ['Species colours', 'Palette (total)',
                                                                         'Ramp TOP', 'Gray'], 'label': 'Colour'}),
        ('Palette', 'Menu', 'prism', {'names': PALETTE_NAMES, 'labels': ['PRISM', 'Bio', 'Gold', 'Ice', 'Mono',
                                                                       'Custom (Pal1..5)'], 'label': 'Palette'}),
        ('Ramptop', 'TOP', '', {'label': 'Ramp TOP (empty = inner ramp)'}),
        ('Col1', 'RGB', SPECIES_COLOURS[0], {'label': 'Species 1 colour'}),
        ('Col2', 'RGB', SPECIES_COLOURS[1], {'label': 'Species 2 colour'}),
        ('Col3', 'RGB', SPECIES_COLOURS[2], {'label': 'Species 3 colour'}),
        ('Bg', 'RGB', (0.0, 0.0, 0.0), {'label': 'Background'}),
        ('Exposure', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Exposure (stops)'}),
        ('Gamma', 'Float', 1.0, {'min': 0.2, 'max': 3, 'label': 'Gamma'}),
        ('Glow', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Halo glow'}),
        ('Agentsview', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Show agents (deposit) mix'}),
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

# Passes. inputs = wired op names (<= 3 per GLSL TOP, T-84/T-88). res: 'agents' (side x side) | 'sim' | 'out' | 'half'.
PASSES = [
    ('maps', {'inputs': ['food_sel', 'mask_sel'], 'vecs': ['uSim'], 'arrays': [], 'res': 'sim', 'fmt': 'rgba16float'}),
    ('agents', {'inputs': ['agents_fb', 'trail_fb', 'fx_maps'],
                'vecs': ['uSim', 'uAg', 'uCtl', 'uSense', 'uMove', 'uSpec', 'uSeed', 'uFood'], 'arrays': ['uRows'],
                'res': 'agents', 'fmt': 'rgba32float'}),
    ('trail', {'inputs': ['trail_fb', 'deposit', 'fx_maps'], 'vecs': ['uSim', 'uCtl', 'uTrail', 'uFood'],
               'arrays': ['uRows'], 'res': 'sim', 'fmt': 'rgba32float'}),
    ('look', {'inputs': ['fx_trail', 'ramp_in', 'deposit'],
              'vecs': ['uSim', 'uLook', 'uLook2', 'uLook3', 'uCol1', 'uCol2', 'uCol3', 'uBg',
                       'uPal0', 'uPal1', 'uPal2', 'uPal3', 'uPal4'], 'arrays': [], 'res': 'out', 'fmt': 'rgba16float'}),
    ('preview', {'inputs': ['fx_look'], 'vecs': ['uSim', 'uFood'], 'arrays': ['uRows'], 'res': 'half',
                 'fmt': 'rgba8fixed'}),
    ('stat', {'inputs': ['fx_trail'], 'vecs': ['uSim', 'uLook'], 'arrays': [], 'res': 'sim', 'fmt': 'rgba32float'}),
    ('astat', {'inputs': ['fx_agents'], 'vecs': ['uAg'], 'arrays': [], 'res': 'agents', 'fmt': 'rgba32float'}),
]
STAT_CHANS = ['mean', 'cover', 'peak', 'meanr', 'order', 'alive', 'steps', 'agents', 'cookms', 'level', 'morph',
              'nrows', 'expected']
ENGINE_CHANS = (['run', 'reset', 'steps', 'time', 'seed', 'morph', 'n', 'side', 'nspecies']
                + PRESET_FIELDS + ['level', 'kick', 'kenv', 'nrows', 'testmode']
                + ['pal%d%s' % (k, c) for k in range(5) for c in 'rgb'])


def menu_index(names, val):
    try:
        return names.index(val)
    except ValueError:
        return 0


def sim_size(resw, resh, simh):
    """Trail grid (w, h): h = Simh, w follows the output aspect so cells stay square."""
    h = max(1, int(round(float(simh))))
    w = max(1, int(round(h * float(resw) / max(float(resh), 1.0))))
    return w, h


def agent_side(n):
    """Agent texture side: smallest square holding n agents (>= 1)."""
    n = max(1, int(n))
    s = int(math.isqrt(n))
    return s if s * s >= n else s + 1


def preset_values(name, custom=None):
    """Preset name -> dict over PRESET_FIELDS (custom: dict of the Custom* values)."""
    for n, vals in PRESETS:
        if n == name:
            if vals is None:
                base = dict(zip(PRESET_FIELDS, PRESETS[0][1]))
                base.update({k: float(v) for k, v in (custom or {}).items() if k in base})
                return base
            return dict(zip(PRESET_FIELDS, vals))
    return dict(zip(PRESET_FIELDS, PRESETS[0][1]))


def morph_presets(a, b, m):
    """Linear blend of two preset dicts (m unclamped: no limits)."""
    return {k: a[k] + (b[k] - a[k]) * float(m) for k in PRESET_FIELDS}


def palette_colours(name, custom=None):
    if name == 'custom' and custom:
        return tuple(tuple(float(v) for v in c) for c in custom)
    return PALETTES.get(name, PALETTES['prism'])


def lfo(kind, phase):
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


def row(x, y, radius, strength, deposit=0.0, falloff=0, kind=KIND_EFF):
    """One effector row: centre uv (0..1, y up), radius in heights, attract strength (- repels), trail inject."""
    return (float(x), float(y), float(radius), float(strength), float(deposit), float(falloff), float(kind), 1.0)


def pack_rows(rows):
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
    """Effector Null -> row (optional gain: shared effectors). World -> uv: plane Planeh tall, centred at 0, Planeh * aspect
    wide; scale = radius."""
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
    d = float(p['effdeposit']) if e.get('deposit') is None else float(e['deposit'])
    fo = e.get('falloff')
    fo = int(p['efffalloff']) if fo is None else int(fo)
    return row(u, v, r, s, d, fo, KIND_EFF)


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
    """in5 CHOP: x y (uv) + optional radius strength deposit channels, one point per sample."""
    xs, ys = chans.get('x') or chans.get('tx'), chans.get('y') or chans.get('ty')
    if not xs or not ys:
        return []
    n = min(len(xs), len(ys))

    def g(name, i, d):
        c = chans.get(name)
        return float(c[i]) if c and i < len(c) else d
    return [row(xs[i], ys[i], g('radius', i, p['pointradius']), g('strength', i, p['effstrength']),
                g('deposit', i, 0.0), 0, KIND_POINT) for i in range(n)]


ENGINE_DEFAULTS = {
    'agents': 262144, 'species': 1, 'pause': False, 'stopat': 0, 'preseta': 'network', 'presetb': 'cells',
    'morph': 0.0, 'morphtime': 4.0, 'morphlfo': 'off', 'morphrate': 0.05, 'morphdepth': 0.0, 'seed': 1,
    'audiomode': 'off', 'audiotarget': 'step', 'audiogain': 4.0, 'audioamt': 1.0, 'kickthresh': 0.3,
    'refractory': 0.15, 'kickspeed': 3.0, 'kickrelease': 0.3, 'burstpattern': 'random', 'burstcount': 3,
    'burstradius': 0.08, 'burststrength': -8.0, 'burstframes': 6, 'effon': True, 'planeh': 1.0, 'effradius': 0.15,
    'effstrength': 10.0, 'effdeposit': 0.0, 'efffalloff': 0, 'pointradius': 0.05, 'mousemode': 'off',
    'mouseradius': 0.08, 'mousestrength': 5.0, 'aspect': 1080.0 / 1920.0, 'testmode': 'off', 'palette': 'prism',
    'custompal': None, 'custom': None, 'gains': None, 'sizekey': None,
}
GAIN_PARS = {'sa': 'Sagain', 'so': 'Sogain', 'ra': 'Ragain', 'ss': 'Ssgain', 'dep': 'Depgain', 'decay': 'Decaygain',
             'diffuse': 'Diffgain', 'jitter': 'Jittergain'}


def engine_params(get, aspect=None):
    """get(ParName) -> value for each engine field (TD side: lambda n: getattr(P.par, n).eval())."""
    p = dict(ENGINE_DEFAULTS)
    m = {'agents': 'Agents', 'species': 'Species', 'pause': 'Pause', 'stopat': 'Stopat', 'preseta': 'Preseta',
         'presetb': 'Presetb', 'morph': 'Morph', 'morphtime': 'Morphtime', 'morphlfo': 'Morphlfo',
         'morphrate': 'Morphrate', 'morphdepth': 'Morphdepth', 'seed': 'Seed', 'audiomode': 'Audiomode',
         'audiotarget': 'Audiotarget', 'audiogain': 'Audiogain', 'audioamt': 'Audioamt', 'kickthresh': 'Kickthresh',
         'refractory': 'Refractory', 'kickspeed': 'Kickspeed', 'kickrelease': 'Kickrelease',
         'burstpattern': 'Burstpattern', 'burstcount': 'Burstcount', 'burstradius': 'Burstradius',
         'burststrength': 'Burststrength', 'burstframes': 'Burstframes', 'effon': 'Effon', 'planeh': 'Planeh',
         'effradius': 'Effradius', 'effstrength': 'Effstrength', 'effdeposit': 'Effdeposit',
         'pointradius': 'Pointradius', 'mousemode': 'Mousemode', 'mouseradius': 'Mouseradius',
         'mousestrength': 'Mousestrength', 'testmode': 'Testmode', 'palette': 'Palette'}
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
    try:
        p['custom'] = {f: float(get('Custom' + f)) for f in PRESET_FIELDS}
    except Exception:
        p['custom'] = None
    try:
        p['gains'] = {f: float(get(GAIN_PARS[f])) for f in PRESET_FIELDS}
    except Exception:
        p['gains'] = None
    try:
        p['sizekey'] = (int(get('Agents')), int(get('Simh')), int(get('Resw')), int(get('Resh')))
    except Exception:
        pass
    if aspect is not None:
        p['aspect'] = float(aspect)
    return p


def new_engine(t=0.0):
    return {'t0': t, 'steps': 0, 'seed': None, 'kick': None, 'goal': 0.0, 'gofrom': 0.0, 'got0': None,
            'nburst': 0, 'kenv': 0.0, 'tlast': t, 'bursts': [], 'sizekey': None, 'rng': random.Random(1).getstate()}


def go_value(st, t, morphtime):
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
    events: 'reset', 'reseed', 'step', 'burst', 'go'. A changed Agents / Simh / Res resets (textures re-allocate)."""
    inp = inp or {}
    reset = st is None
    st = dict(st) if st else new_engine(t)
    ev = list(events)
    seed = int(p['seed'])
    if p.get('sizekey') is not None and st.get('sizekey') != p['sizekey']:
        reset = reset or st.get('sizekey') is not None
        st['sizekey'] = p['sizekey']
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
    run = 1
    if p['pause'] and not reset:
        run = 1 if 'step' in ev else 0
    stopat = int(p['stopat'])
    if stopat > 0 and st['steps'] >= stopat and not reset:
        run = 0
    if reset:
        run = 0                     # the reset frame seeds the agents and clears the trail; stepping starts next frame
    st['steps'] += run
    dt = max(0.0, t - st.get('tlast', t))
    st['tlast'] = t
    morph = float(p['morph']) + go_value(st, t, p['morphtime'])
    if p['morphlfo'] != 'off':
        morph += float(p['morphdepth']) * lfo(p['morphlfo'], (t - st['t0']) * float(p['morphrate']))
    level = float(inp.get('level', 0.0)) * float(p['audiogain'])
    low = float(inp.get('low', 0.0)) * float(p['audiogain'])
    kick = False
    if not test and p['audiomode'] == 'kick':
        st['kick'], kick = kick_step(st['kick'], t, low, float(p['kickthresh']), float(p['refractory']))
    rel = max(float(p['kickrelease']), 1e-4)
    st['kenv'] = 1.0 if kick else st.get('kenv', 0.0) * math.exp(-dt / rel)
    lvl = level * float(p['audioamt']) if (not test and p['audiomode'] == 'level') else 0.0
    if p['audiotarget'] == 'morph':
        morph += lvl
    a = preset_values(p['preseta'], p.get('custom'))
    b = preset_values(p['presetb'], p.get('custom'))
    v = morph_presets(a, b, morph)
    g = p.get('gains') or {}
    for k in PRESET_FIELDS:
        v[k] *= float(g.get(k, 1.0))
    if lvl:
        tgt = p['audiotarget']
        if tgt == 'step':
            v['ss'] *= 1.0 + lvl
        elif tgt == 'deposit':
            v['dep'] *= 1.0 + lvl
        elif tgt == 'sensor':
            v['sa'] *= 1.0 + lvl
    if not test:
        v['ss'] *= 1.0 + (float(p['kickspeed']) - 1.0) * st['kenv']
    # rows
    rng = random.Random()
    rng.setstate(st['rng'])
    rows = []
    bursts = [b_ for b_ in st.get('bursts', []) if b_[0] > 0]
    if not test:
        if p['effon']:
            for e in inp.get('effectors') or ():
                r = effector_row(e, p)
                if r is not None:
                    rows.append(r)
        rows.extend(inp.get('points') or ())
        mo = inp.get('mouse')
        if p['mousemode'] != 'off' and mo is not None and mo[2]:
            s = float(p['mousestrength']) * (1.0 if p['mousemode'] == 'attract' else -1.0)
            rows.append(row(mo[0], mo[1], p['mouseradius'], s, 0.0, 0, KIND_MOUSE))
        nb = ev.count('burst') + (1 if kick else 0)
        for _ in range(nb):
            bursts.append([max(1, int(p['burstframes'])), burst_rows(st['nburst'], p, rng)])
            st['nburst'] += 1
        for b_ in bursts:
            rows.extend(b_[1])
            b_[0] -= 1 if run else 0
    st['bursts'] = [b_ for b_ in bursts if b_[0] > 0]
    st['rng'] = rng.getstate()
    rows = rows[:NROWS]
    n = max(1, int(p['agents']))
    pal = palette_colours(p['palette'], p.get('custompal'))
    o = {'run': float(run), 'reset': 1.0 if reset else 0.0, 'steps': float(st['steps']), 'time': t - st['t0'],
         'seed': float(st['seed']), 'morph': morph, 'n': float(n), 'side': float(agent_side(n)),
         'nspecies': float(min(max(int(p['species']), 1), NSPECIES)), 'level': level, 'kick': 1.0 if kick else 0.0,
         'kenv': st['kenv'], 'nrows': float(len(rows)), 'testmode': 1.0 if test else 0.0}
    o.update({k: float(v[k]) for k in PRESET_FIELDS})
    for k in range(5):
        for ci, c in enumerate('rgb'):
            o['pal%d%s' % (k, c)] = float(pal[k][ci])
    return st, o, rows


def expected_mean(n, dep, decay, w, h):
    """Steady-state mean trail (all species summed), wrap edges, no mask / injects: M = (1 - d) (M + N dep)."""
    decay = float(decay)
    if decay <= 0:
        return float('inf')
    return (1.0 - decay) * float(n) * float(dep) / (decay * float(w) * float(h))


# ------------------------------------------------------------------------------------------------------------------
# numpy reference (same formulas as the shaders)

def _np():
    import numpy as np
    return np


M32 = 0xffffffff


def hash_u32(x):
    """lowbias32 (Wellons), uint32 wraparound, == ph_common.glsl hashu()."""
    np = _np()
    x = np.asarray(x).astype(np.uint64) & M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def hash3(i, j, s):
    """float in [0, 1) from three ints (== hash3() in GLSL)."""
    np = _np()
    i = np.asarray(i).astype(np.int64) & M32
    j = np.asarray(j).astype(np.int64) & M32
    s = np.asarray(s).astype(np.int64) & M32
    h = hash_u32(i + hash_u32(j + hash_u32(s)))
    return (h >> 8).astype(np.float64) * (1.0 / 16777216.0)


REF_DEFAULTS = {
    'edge': 0, 'nspecies': 1, 'speciesmode': 'interleave', 'selfw': 1.0, 'otherw': -1.0, 'speedspread': 0.0,
    'seedmode': 'disc', 'heading': 'random', 'seedsize': 0.3, 'seed': 1, 'foodw': 0.0, 'foodinject': 0.0,
    'maskthresh': 0.5, 'sa': 22.5, 'so': 9.0, 'ra': 45.0, 'ss': 1.0, 'dep': 1.0, 'decay': 0.1, 'diffuse': 1.0,
    'jitter': 0.0, 'respawn': 0.0,
}


def species_of(idx, x, y, w, h, p):
    """Species per agent from Speciesmode (== speciesOf() in ph_agents)."""
    np = _np()
    ns = int(p['nspecies'])
    if ns <= 1:
        return np.zeros_like(idx, dtype=np.float64)
    mode = p['speciesmode']
    if mode == 'bands':
        return np.minimum(np.floor(x / w * ns), ns - 1).astype(np.float64)
    if mode == 'rings':
        r = np.hypot(x - 0.5 * w, y - 0.5 * h) / (0.5 * h)
        return np.minimum(np.floor(r * ns), ns - 1).astype(np.float64)
    return np.mod(idx, ns).astype(np.float64)


def seed_agents(n, side, w, h, p, img=None):
    """fx_agents reset: [side, side, 4] float64 agent texture (row-major index i = y * side + x)."""
    np = _np()
    T = np.arange(side * side, dtype=np.int64)
    s = int(p['seed'])
    u1, u2, u3 = hash3(T, 11, s), hash3(T, 12, s), hash3(T, 13, s)
    size = float(p['seedsize']) * h
    cx, cy = 0.5 * w, 0.5 * h
    mode = p['seedmode']
    if mode == 'disc':
        r = size * np.sqrt(u1)
        a = TWO_PI * u2
        x, y = cx + r * np.cos(a), cy + r * np.sin(a)
    elif mode == 'ring':
        a = TWO_PI * u1
        r = size * (1.0 + 0.02 * (u2 - 0.5))
        x, y = cx + r * np.cos(a), cy + r * np.sin(a)
    elif mode == 'spiral':
        tt = u1
        a = TWO_PI * 3.0 * tt + 0.3 * (u2 - 0.5)
        r = size * tt
        x, y = cx + r * np.cos(a), cy + r * np.sin(a)
    elif mode == 'lines':
        k = np.floor(u1 * 5.0)
        x = (k + 0.5) / 5.0 * w + (u3 - 0.5) * 2.0
        y = u2 * h
    elif mode == 'center':
        x, y = np.full(T.shape, cx), np.full(T.shape, cy)
    elif mode in ('image', 'text') and img is not None:
        x, y = u1 * w, u2 * h
        done = np.zeros(T.shape, bool)
        for k in range(32):
            ux, uy, ua = hash3(T, 20 + 3 * k, s), hash3(T, 21 + 3 * k, s), hash3(T, 22 + 3 * k, s)
            px, py = ux * w, uy * h
            v = img[np.minimum(py.astype(np.int64), h - 1), np.minimum(px.astype(np.int64), w - 1)]
            ok = (~done) & (v > ua)
            x, y = np.where(ok, px, x), np.where(ok, py, y)
            done |= ok
    else:
        x, y = u1 * w, u2 * h
    hd = p['heading']
    out_a = np.arctan2(y - cy, x - cx)
    if hd == 'outward':
        a = out_a
    elif hd == 'inward':
        a = out_a + math.pi
    elif hd == 'swirl':
        a = out_a + 0.5 * math.pi
    else:
        a = TWO_PI * u3
    a = a - TWO_PI * np.floor(a / TWO_PI)
    x = x - w * np.floor(x / w)
    y = y - h * np.floor(y / h)
    sp = species_of(T, x, y, w, h, p)
    sp = np.where(T < n, sp, -1.0)
    ag = np.stack([x, y, a, sp], -1).reshape(side, side, 4)
    return ag


def falloff(d, mode):
    np = _np()
    if mode == 1:
        return np.maximum(1.0 - d, 0.0)
    if mode == 2:
        return (d < 1.0).astype(np.float64)
    if mode == 3:
        return np.exp(-((d - 1.0) * 4.0) ** 2)
    return np.exp(-d * d)


def _wrap_i(t, n):
    np = _np()
    return t - n * np.floor(t / n)


def field_at(px, py, w, h, rows):
    """Effector attract/repel field at sim texel positions (== fieldAt() in ph_agents)."""
    np = _np()
    out = np.zeros(np.shape(px))
    asp = w / float(h)
    for r in rows:
        u, v = (px + 0.5) / w, (py + 0.5) / h
        d = np.hypot((u - r[0]) * asp, v - r[1]) / max(r[2], 1e-6)
        out = out + r[3] * falloff(d, int(r[5] + 0.5))
    return out


def _sense(trail, maps, ag, ang, so, w, h, p, rows, wmat):
    np = _np()
    x, y, sp = ag[..., 0], ag[..., 1], ag[..., 3]
    qx = np.floor(x + so * np.cos(ang))
    qy = np.floor(y + so * np.sin(ang))
    if int(p['edge']) == 0:
        qx, qy = _wrap_i(qx, w), _wrap_i(qy, h)
    else:
        qx, qy = np.clip(qx, 0, w - 1), np.clip(qy, 0, h - 1)
    ix, iy = qx.astype(np.int64), qy.astype(np.int64)
    t = trail[iy, ix, :3]
    si = np.clip(sp, 0, NSPECIES - 1).astype(np.int64)
    val = (t * wmat[si]).sum(-1)
    if float(p['foodw']) != 0.0 and maps is not None:
        val = val + float(p['foodw']) * maps[iy, ix, 1]
    if rows:
        val = val + field_at(qx, qy, w, h, rows)
    return val


def weight_matrix(p):
    np = _np()
    wm = np.full((NSPECIES, NSPECIES), float(p['otherw']))
    np.fill_diagonal(wm, float(p['selfw']))
    return wm


def agent_pass(ag, trail, p, step, maps=None, rows=()):
    """fx_agents (no reset): sense / rotate / move. step = engine steps (the hash's time index)."""
    np = _np()
    h, w = trail.shape[:2]
    side = ag.shape[0]
    T = np.arange(side * side, dtype=np.int64).reshape(side, side)
    s = int(p['seed'])
    sa, ra = float(p['sa']) * DEG, float(p['ra']) * DEG
    so, ss = float(p['so']), float(p['ss'])
    wm = weight_matrix(p)
    a = ag[..., 2]
    sp = ag[..., 3]
    F = _sense(trail, maps, ag, a, so, w, h, p, rows, wm)
    L = _sense(trail, maps, ag, a + sa, so, w, h, p, rows, wm)
    R = _sense(trail, maps, ag, a - sa, so, w, h, p, rows, wm)
    r1 = hash3(T, step * 4 + 1, s)
    r2 = hash3(T, step * 4 + 2, s)
    r3 = hash3(T, step * 4 + 3, s)
    turn = np.where((F > L) & (F > R), 0.0,
                    np.where((F < L) & (F < R), np.where(r1 < 0.5, -ra, ra),
                             np.where(L > R, ra, np.where(R > L, -ra, 0.0))))
    a2 = a + turn + float(p['jitter']) * DEG * (2.0 * r2 - 1.0)
    spd = ss * (1.0 + float(p['speedspread']) * (np.clip(sp, 0, 2) - 1.0))
    x2 = ag[..., 0] + spd * np.cos(a2)
    y2 = ag[..., 1] + spd * np.sin(a2)
    if int(p['edge']) == 0:
        x2, y2 = _wrap_i(x2, w), _wrap_i(y2, h)
    else:
        bx = (x2 < 0) | (x2 >= w)
        by = (y2 < 0) | (y2 >= h)
        x2 = np.where(x2 < 0, -x2, np.where(x2 >= w, 2.0 * w - x2 - 1e-3, x2))
        y2 = np.where(y2 < 0, -y2, np.where(y2 >= h, 2.0 * h - y2 - 1e-3, y2))
        x2, y2 = np.clip(x2, 0, w - 1e-3), np.clip(y2, 0, h - 1e-3)
        a2 = np.where(bx, math.pi - a2, a2)
        a2 = np.where(by, -a2, a2)
    if maps is not None:
        blk = maps[np.clip(y2, 0, h - 1).astype(np.int64), np.clip(x2, 0, w - 1).astype(np.int64), 0] \
            > float(p['maskthresh'])
        x2 = np.where(blk, ag[..., 0], x2)
        y2 = np.where(blk, ag[..., 1], y2)
        a2 = np.where(blk, TWO_PI * r3, a2)
    rs = float(p.get('respawn', 0.0))
    if rs > 0.0:                                      # respawn: a fraction re-placed at random (keeps it exploring)
        j = step * 4
        hit = hash3(T, j, s) < rs
        x2 = np.where(hit, hash3(T, j, s + 101) * w, x2)
        y2 = np.where(hit, hash3(T, j, s + 102) * h, y2)
        a2 = np.where(hit, hash3(T, j, s + 103) * TWO_PI, a2)
    a2 = a2 - TWO_PI * np.floor(a2 / TWO_PI)
    live = sp >= 0
    out = ag.copy()
    out[..., 0] = np.where(live, x2, ag[..., 0])
    out[..., 1] = np.where(live, y2, ag[..., 1])
    out[..., 2] = np.where(live, a2, a)
    return out


def deposit_map(ag, w, h, dep):
    """The deposit Render TOP: one 1-px point per live agent, additive (exact sums)."""
    np = _np()
    D = np.zeros((h, w, 4))
    a = ag.reshape(-1, 4)
    live = a[:, 3] >= 0
    a = a[live]
    ix = np.clip(np.floor(a[:, 0]).astype(np.int64), 0, w - 1)
    iy = np.clip(np.floor(a[:, 1]).astype(np.int64), 0, h - 1)
    ch = np.clip(a[:, 3], 0, 2).astype(np.int64)
    np.add.at(D, (iy, ix, ch), float(dep))
    np.add.at(D, (iy, ix, 3), 1.0)
    return D


def mean3(T, edge):
    np = _np()
    if edge == 0:
        acc = sum(np.roll(T, (dy, dx), (0, 1)) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    else:
        h, w = T.shape[:2]
        pad = np.pad(T, ((1, 1), (1, 1), (0, 0)), mode='edge')
        acc = sum(pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    return acc / 9.0


def trail_pass(trail, D, p, maps=None, rows=()):
    """fx_trail: T1 = T + D, diffuse, decay, injects (rows, food), mask."""
    np = _np()
    h, w = trail.shape[:2]
    T1 = trail.copy()
    T1[..., :3] = T1[..., :3] + D[..., :3]
    T1[..., 3] = 0.0
    m = mean3(T1, int(p['edge']))
    T2 = T1 + float(p['diffuse']) * (m - T1)
    T3 = T2 * (1.0 - float(p['decay']))
    inj = np.zeros((h, w))
    X, Y = np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64))
    asp = w / float(h)
    for r in rows:
        if r[4] != 0.0:
            d = np.hypot(((X + 0.5) / w - r[0]) * asp, (Y + 0.5) / h - r[1]) / max(r[2], 1e-6)
            inj = inj + r[4] * falloff(d, int(r[5] + 0.5))
    if maps is not None and float(p['foodinject']) != 0.0:
        inj = inj + float(p['foodinject']) * maps[..., 1]
    ns = int(p['nspecies'])
    for c in range(ns):
        T3[..., c] = T3[..., c] + inj
    if maps is not None:
        solid = maps[..., 0] > float(p['maskthresh'])
        T3[solid] = 0.0
    T3[..., 3] = 0.0
    return T3


def run_fixed(steps=200, n=4096, w=90, h=160, p=None, img=None, maps=None):
    """Reset (seed agents, clear trail), then `steps` frames of agents -> deposit -> trail. Returns (agents, trail)."""
    np = _np()
    q = dict(REF_DEFAULTS)
    q.update(p or {})
    side = agent_side(n)
    ag = seed_agents(n, side, w, h, q, img)
    tr = np.zeros((h, w, 4))
    for k in range(1, steps + 1):
        ag = agent_pass(ag, tr, q, k, maps)
        D = deposit_map(ag, w, h, q['dep'])
        tr = trail_pass(tr, D, q, maps)
    return ag, tr


def tone(v, mode, lo, hi):
    np = _np()
    if mode == 'linear':
        return np.clip((v - lo) / max(hi - lo, 1e-6), 0, 1)
    if mode == 'log':
        return np.clip(np.log1p(np.maximum(v - lo, 0)) / math.log1p(max(hi - lo, 1e-6)), 0, 1)
    return 1.0 - np.exp(-np.maximum(v - lo, 0) / max(hi, 1e-6))


def stats(trail, ag, lo=0.0, hi=3.0, mode='soft'):
    """== fx_stat / fx_astat + Analyze average: mean (sum of species), cover (soft tone > 0.25), peak (tone > 0.75),
    meanr (species 0), order |mean heading vector| of live agents, alive (live fraction of slots)."""
    np = _np()
    tot = trail[..., :3].sum(-1)
    tn = tone(tot, mode, lo, hi)
    a = ag.reshape(-1, 4)
    live = a[:, 3] >= 0
    if live.any():
        cx, cy = np.cos(a[live, 2]).mean(), np.sin(a[live, 2]).mean()
    else:
        cx = cy = 0.0
    return {'mean': float(tot.mean()), 'cover': float((tn > 0.25).mean()), 'peak': float((tn > 0.75).mean()),
            'meanr': float(trail[..., 0].mean()), 'order': float(math.hypot(cx, cy)), 'alive': float(live.mean())}


def rel_l2(a, b):
    np = _np()
    n = float(np.sqrt((b * b).sum()))
    return float(np.sqrt(((a - b) ** 2).sum())) / max(n, 1e-12)
