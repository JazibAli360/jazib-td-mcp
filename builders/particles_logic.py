"""particles_logic: pure logic for BO_particles (no td import; tested by test/test_particles.py).

Spec: docs/research/BO_particle_sims.md section 4 (clean-room; design ideas credited there: compute state texture +
instanced GLSL MAT fetch from Tim Gerritsen's Compute Particle System, CC BY 4.0; curl noise per Bridson et al. 2007).
Engine = compute GLSL TOP (engine B of the spec, the one most likely to hold 60 fps on this Mac). ASCII only.
Copied into the COMP's `particles_logic` Text DAT.

Three parts:
1. PAGES: the custom-parameter contract (names, defaults, ranges, menus) the builder creates.
2. step(st, raw, ctl_in, events, t): runs once per frame on the CPU (Script CHOP `engine`). Advances the clock,
   the emission ring, the audio/BPM control layer, and returns the uniform rows `uP[NROWS]` the shaders read.
3. A float64 reference of the GPU update (spawn/update per particle, same maths and hash as particles_state.glsl)
   for the live comparison V1/V6: reference_run(raw, frames, ids).

Particle state (GPU, one rgba32float texture, width 3*side, height side; particle id = y*side + x):
  texel (3x, y)   = P.xyz, age      (age < 0 = dormant: waits at its spawn point until age reaches 0)
  texel (3x+1, y) = V.xyz, life     (alive = 0 <= age < life; life 0 = dead slot)
  texel (3x+2, y) = colour.rgb, r   (r = per-particle random 0..1 for size variation; frame stamp when Debugstamp)
"""
import math

M32 = 0xFFFFFFFF
TAU = 6.283185307179586
FPS_NOMINAL = 60.0              # fixed step: dt = Speed / 60 per cooked frame (frame dips do not change the sim)
FRAME_WRAP = 1 << 24            # frame counter wraps (exact in a float uniform; hashes never see a float time)
CURL_WRAP = TAU * 1000.0        # curl time wraps (float32 sin precision on long shows; one jump every ~1.7 h at 1x)
NROWS = 31                      # vec4 rows in uP[] (keep equal to the array size in the GLSL files)
TEXELS = 3                      # texels per particle
MAX_OCTAVES = 4                 # shader loop bound
MAX_STRANDS = 4096              # strand seeds (Source strands)
LUMA = (0.2126, 0.7152, 0.0722)

SOURCES = ['ball', 'box', 'ring', 'line', 'top', 'points', 'strands']
EMITINPUTS = ['auto', 'input', 'cam', 'none']
EMITWEIGHTS = ['luma', 'alpha']
EMITMODES = ['continuous', 'rate']
BOUNDS = ['none', 'wrap', 'bounce', 'kill']
AUDIOSRCS = ['off', 'manual', 'bpm', 'chop']
COLORMODES = ['age', 'speed', 'emit', 'white', 'palette']
PALBY = ['age', 'speed', 'random', 'height']
BLENDS = ['add', 'alpha']
SHAPES = ['dot', 'paper', 'streamer']
KICK_CHOP = '/project1/lab/AC_audio/out_ctl'     # AC_audio's control CHOP (kick bass mid high level)
STATEMODES = ['feedback', 'inplace']
CTL_CHANS = ('kick', 'bass', 'mid', 'high', 'level')
# W1-B palette (docs/builds/palette_convention.md): copied names so this file imports nothing in TD; the tests check
# they equal palette_map_logic's / px_lines_logic's ('file' / 'image' sources are not offered here).
PAL_SOURCES = ['custom', 'neon_green', 'cyan_magenta', 'neon_trio', 'acid', 'magenta_inv', 'fire', 'px_ramp', 'rainbow']
PAL_MODES = ['gradient', 'steps', 'cycle']
PAL_INTERP = ['rgb', 'oklab']
# PX_lines (light trails on the particles, TC-08): its colour sources / attributes, same names as px_lines_logic
LINE_COLSRC = ['solid', 'palette', 'attr', 'source', 'index']
LINE_ATTR = ['along', 'index', 'depth', 'random']
LINE_BLENDS = ['add', 'max']

def spiral_pars(k, pos, axis):
    """Spiral force field k (Force-Radial-POP-like, TC-13): swirl around an axis + pull toward it + lift along it,
    Lorentzian falloff R^2 / (d^2 + R^2) with d = distance to the axis line (R 0 = no falloff)."""
    s = 'Sp%d' % k
    return [
        (s + 'on', 'Toggle', False, {'label': 'Spiral %d' % k}),
        (s + 'pos', 'XYZ', pos, {'min': -5, 'max': 5, 'label': 'Spiral %d centre' % k}),
        (s + 'axis', 'XYZ', axis, {'min': -1, 'max': 1, 'label': 'Spiral %d axis' % k}),
        (s + 'swirl', 'Float', 1.5, {'min': -10, 'max': 10, 'label': 'Spiral %d swirl' % k}),
        (s + 'pull', 'Float', 0.5, {'min': -10, 'max': 10, 'label': 'Spiral %d pull in' % k}),
        (s + 'lift', 'Float', 0.0, {'min': -10, 'max': 10, 'label': 'Spiral %d lift (along axis)' % k}),
        (s + 'radius', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Spiral %d radius (falloff, 0 = none)' % k}),
    ]


# (page, [(name, style, default, opts)]); XYZ / RGB = 3-tuples; menus = (names, labels)
PAGES = [
    ('System', [
        ('Play', 'Toggle', True, {}),
        ('Reset', 'Pulse', None, {}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 100}),
        ('Count', 'Int', 65536, {'min': 1, 'max': 1048576, 'label': 'Count (re-inits)'}),
        ('Speed', 'Float', 1.0, {'min': 0, 'max': 4}),
        ('Stagger', 'Toggle', True, {'label': 'Stagger first births'}),
        ('Statemode', 'Menu', 'feedback', {'names': STATEMODES, 'labels': ['Feedback TOP', 'In place (r/w)'],
                                            'label': 'State mode'}),
        ('Debugstamp', 'Toggle', False, {'label': 'Debug: frame stamp'}),
        ('Resx', 'Int', 1080, {'min': 64, 'max': 7680}),
        ('Resy', 'Int', 1920, {'min': 64, 'max': 7680}),
    ]),
    ('Emit', [
        ('Source', 'Menu', 'ball', {'names': SOURCES, 'labels': ['Ball', 'Box', 'Ring', 'Line', 'TOP (in_emit)',
                                                                   'Points (in_emit XYZ)', 'Strand seeds (ring)']}),
        ('Strands', 'Int', 9, {'min': 1, 'max': MAX_STRANDS, 'label': 'Strand seeds'}),
        ('Strandjitter', 'Float', 0.02, {'min': 0, 'max': 1, 'label': 'Strand jitter'}),
        ('Emitinput', 'Menu', 'auto', {'names': EMITINPUTS, 'labels': ['Auto', 'in_emit', 'Webcam clip diff', 'None (white)'],
                                       'label': 'Emit TOP'}),
        ('Emitweight', 'Menu', 'luma', {'names': EMITWEIGHTS, 'labels': ['Luma', 'Alpha'], 'label': 'Emit weight'}),
        ('Emitmode', 'Menu', 'continuous', {'names': EMITMODES, 'labels': ['Continuous (respawn)', 'Rate'],
                                            'label': 'Emit mode'}),
        ('Rate', 'Float', 5000.0, {'min': 0, 'max': 200000, 'label': 'Rate /s'}),
        ('Life', 'Float', 4.0, {'min': 0.05, 'max': 20}),
        ('Lifevar', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Life var'}),
        ('Emitpos', 'XYZ', (0.0, 0.0, 0.0), {'min': -5, 'max': 5, 'label': 'Emit pos'}),
        ('Emitsize', 'XYZ', (0.3, 0.3, 0.3), {'min': 0, 'max': 5, 'label': 'Emit size'}),
        ('Emitdir', 'XYZ', (0.0, 1.0, 0.0), {'min': -1, 'max': 1, 'label': 'Emit dir'}),
        ('Initspeed', 'Float', 0.2, {'min': 0, 'max': 5, 'label': 'Init speed'}),
        ('Initspread', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Init spread'}),
        ('Initspeedvar', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Init speed variation'}),
        ('Emitthreshold', 'Float', 0.1, {'min': 0, 'max': 1, 'label': 'Emit threshold'}),
        ('Burst', 'Pulse', None, {'label': 'Burst (Hit)'}),
        ('Burstcount', 'Int', 5000, {'min': 0, 'max': 100000, 'label': 'Burst count'}),
    ]),
    ('Forces', [
        ('Curlstrength', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Curl'}),
        ('Curlscale', 'Float', 1.5, {'min': 0.05, 'max': 10, 'label': 'Curl scale'}),
        ('Curlspeed', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Curl speed'}),
        ('Curloctaves', 'Int', 1, {'min': 0, 'max': MAX_OCTAVES, 'label': 'Curl octaves'}),
        ('Gravity', 'XYZ', (0.0, 0.0, 0.0), {'min': -5, 'max': 5}),
        ('Drag', 'Float', 0.8, {'min': 0, 'max': 5}),
        ('Wind', 'XYZ', (0.0, 0.0, 0.0), {'min': -5, 'max': 5}),
        ('Att1on', 'Toggle', False, {'label': 'Attractor 1'}),
        ('Att1pos', 'XYZ', (0.0, 1.0, 0.0), {'min': -5, 'max': 5, 'label': 'Att 1 pos'}),
        ('Att1strength', 'Float', 0.5, {'min': -5, 'max': 5, 'label': 'Att 1 strength'}),
        ('Att1soft', 'Float', 0.05, {'min': 0.001, 'max': 1, 'label': 'Att 1 soft'}),
        ('Att2on', 'Toggle', False, {'label': 'Attractor 2'}),
        ('Att2pos', 'XYZ', (0.0, -1.0, 0.0), {'min': -5, 'max': 5, 'label': 'Att 2 pos'}),
        ('Att2strength', 'Float', 0.5, {'min': -5, 'max': 5, 'label': 'Att 2 strength'}),
        ('Att2soft', 'Float', 0.05, {'min': 0.001, 'max': 1, 'label': 'Att 2 soft'}),
        ('Vortexon', 'Toggle', False, {'label': 'Vortex'}),
        ('Vortexaxis', 'XYZ', (0.0, 1.0, 0.0), {'min': -1, 'max': 1, 'label': 'Vortex axis'}),
        ('Vortexstrength', 'Float', 0.5, {'min': -5, 'max': 5, 'label': 'Vortex strength'}),
    ] + spiral_pars(1, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)) + spiral_pars(2, (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)) + [
        ('Fieldstrength', 'Float', 0.0, {'min': -10, 'max': 10, 'label': 'Field (in_field)'}),
        ('Bounds', 'Menu', 'wrap', {'names': BOUNDS, 'labels': ['None', 'Wrap', 'Bounce', 'Kill']}),
        ('Boundsize', 'XYZ', (2.5, 4.5, 2.5), {'min': 0, 'max': 10, 'label': 'Bound size'}),
        ('Floor', 'Toggle', False, {}),
        ('Floory', 'Float', -3.0, {'min': -10, 'max': 10, 'label': 'Floor y'}),
        ('Bounce', 'Float', 0.5, {'min': 0, 'max': 1}),
    ]),
    ('Audio', [
        ('Audiosrc', 'Menu', 'off', {'names': AUDIOSRCS, 'labels': ['Off', 'Manual', 'BPM', 'CHOP'], 'label': 'Audio'}),
        ('Bpm', 'Float', 120.0, {'min': 20, 'max': 300, 'label': 'BPM'}),
        ('Tapnudge', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Phase nudge'}),
        ('Chop', 'CHOP', '', {'label': 'CHOP (kick bass mid high level)'}),
        ('Smooth', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Smooth s'}),
        ('Amtcurl', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Bass -> curl'}),
        ('Amtsize', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Kick -> size'}),
        ('Amtbright', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Level -> bright'}),
        ('Amtburst', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Kick -> burst'}),
        ('Autohit', 'Toggle', True, {'label': 'Auto: kick fires bursts (Kick -> burst)'}),
        ('Amtatt', 'Float', 0.0, {'min': 0, 'max': 5, 'label': 'Mid -> attract'}),
        ('Amtspeed', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Level -> speed'}),
        ('Manual1', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Manual kick'}),
        ('Manual2', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Manual bass'}),
        ('Manual3', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Manual mid'}),
        ('Manual4', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Manual high'}),
    ]),
    ('Look', [
        ('Size', 'Float', 0.012, {'min': 0, 'max': 0.1}),
        ('Sizevar', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Size var'}),
        ('Sizeage', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Size by age'}),
        ('Colormode', 'Menu', 'age', {'names': COLORMODES, 'labels': ['By age', 'By speed', 'From in_emit', 'White',
                                                                      'Palette (Palette page)'],
                                      'label': 'Colour mode'}),
        ('Speedref', 'Float', 2.0, {'min': 0.01, 'max': 10, 'label': 'Speed ref'}),
        ('Bright', 'Float', 0.6, {'min': 0, 'max': 4}),
        ('Blend', 'Menu', 'add', {'names': BLENDS, 'labels': ['Add', 'Alpha over']}),
        ('Softness', 'Float', 0.6, {'min': 0, 'max': 1}),
        ('Trails', 'Toggle', False, {}),
        ('Trailfade', 'Float', 0.9, {'min': 0, 'max': 1, 'label': 'Trail keep'}),
        ('Bloom', 'Float', 0.0, {'min': 0, 'max': 4}),
        ('Shape', 'Menu', 'dot', {'names': SHAPES, 'labels': ['Soft dot', 'Paper (spinning, two-sided)',
                                                             'Streamer (ribbon along the velocity)'],
                                  'label': 'Particle shape'}),
        ('Spinrate', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Spin / twist rev per s'}),
        ('Paperaspect', 'Float', 0.6, {'min': 0.05, 'max': 4, 'label': 'Paper aspect (h / w)'}),
        ('Ambient', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Paper dark side'}),
        ('Lightdir', 'XYZ', (0.3, 0.6, 1.0), {'min': -1, 'max': 1, 'label': 'Paper light dir'}),
        ('Streamerlen', 'Float', 6.0, {'min': 1, 'max': 40, 'label': 'Streamer length (x size)'}),
        ('Flutter', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Flutter force (sideways sine)'}),
        ('Flutterhz', 'Float', 1.2, {'min': 0, 'max': 10, 'label': 'Flutter rate Hz'}),
    ]),
    ('Colours', [
        ('Colour1', 'RGB', (1.0, 0.55, 0.2), {'label': 'Young'}),
        ('Colour2', 'RGB', (0.95, 0.2, 0.6), {'label': 'Middle'}),
        ('Colour3', 'RGB', (0.2, 0.4, 1.0), {'label': 'Old'}),
        ('Linecol', 'RGB', (0.25, 1.0, 0.4), {'label': 'Trail line colour (solid)'}),
    ]),
    ('Palette', [
        ('Palsource', 'Menu', 'neon_trio', {'names': PAL_SOURCES, 'labels': PAL_SOURCES, 'label': 'Palette'}),
        ('Palmode', 'Menu', 'gradient', {'names': PAL_MODES, 'labels': ['Gradient', 'Steps', 'Cycle (wraps)'],
                                         'label': 'Palette mode'}),
        ('Palinterp', 'Menu', 'oklab', {'names': PAL_INTERP, 'labels': ['RGB', 'OKLab'], 'label': 'Blend space'}),
        ('Palreverse', 'Toggle', False, {'label': 'Reverse palette'}),
        ('Palshift', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Palette shift (drive me)'}),
        ('Palby', 'Menu', 'age', {'names': PALBY, 'labels': ['Age', 'Speed (/ Speed ref)', 'Random (strand)',
                                                             'Height (Bound size y)'], 'label': 'Dots palette by'}),
        ('Palpos', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Palette position'}),
        ('Palspread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Palette spread'}),
    ]),
    ('Lines', [
        ('Lineson', 'Toggle', False, {'label': 'Light trails (PX_lines on the particles)'}),
        ('Linedots', 'Toggle', True, {'label': 'Draw the dots too'}),
        ('Linetracks', 'Int', 1024, {'min': 1, 'max': 4096, 'label': 'Trails (tracks)'}),
        ('Linesamples', 'Int', 32, {'min': 2, 'max': 128, 'label': 'Samples per trail'}),
        ('Lineevery', 'Int', 1, {'min': 1, 'max': 30, 'label': 'Frames per sample'}),
        ('Linewidth', 'Float', 1.5, {'min': 0.25, 'max': 16, 'label': 'Core width px'}),
        ('Linehalo', 'Float', 3.0, {'min': 0, 'max': 64, 'label': 'Halo px'}),
        ('Linehalogain', 'Float', 0.35, {'min': 0, 'max': 2, 'label': 'Halo gain'}),
        ('Lineintensity', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Intensity (HDR)'}),
        ('Linetaper', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Width taper'}),
        ('Linefade', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Fade along'}),
        ('Linemaxjump', 'Float', 0.5, {'min': 0, 'max': 100, 'label': 'Max jump (respawn = new trail)'}),
        ('Linecolsrc', 'Menu', 'attr', {'names': LINE_COLSRC, 'labels': ['Solid (Linecol)', 'Palette at position',
                                                                        'Palette by attribute', 'Source',
                                                                        'Palette stop by index'],
                                        'label': 'Trail colour'}),
        ('Lineattr', 'Menu', 'along', {'names': LINE_ATTR, 'labels': ['Along the trail', 'Trail index', 'Depth',
                                                                      'Random per trail'], 'label': 'Trail attribute'}),
        ('Linepalpos', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Trail palette position'}),
        ('Linepalspread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Trail palette spread'}),
        ('Lineblend', 'Menu', 'add', {'names': LINE_BLENDS, 'labels': ['Add (crossings brighten)', 'Max'],
                                      'label': 'Trail blend'}),
    ]),
    ('Camera', [
        ('Camdist', 'Float', 6.0, {'min': 0.5, 'max': 30, 'label': 'Distance'}),
        ('Fov', 'Float', 45.0, {'min': 5, 'max': 120, 'label': 'FOV'}),
        ('Orbit', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Orbit deg/s'}),
        ('Camx', 'Float', 0.0, {'min': -5, 'max': 5, 'label': 'Pan x'}),
        ('Camy', 'Float', 0.0, {'min': -5, 'max': 5, 'label': 'Pan y'}),
        ('Ortho', 'Toggle', False, {}),
    ]),
]
PANEL_PAGES = [pg for pg, _ in PAGES]


def flat_defaults():
    """{TD par name: default} as TD names them (XYZ -> name+x/y/z, RGB -> name+r/g/b); pulses/CHOP left out."""
    d = {}
    for _, pars in PAGES:
        for name, style, default, _o in pars:
            if style in ('XYZ', 'RGB'):
                for suf, v in zip('xyz' if style == 'XYZ' else 'rgb', default):
                    d[name + suf] = v
            elif style not in ('Pulse', 'CHOP'):
                d[name] = default
    return d


DEFAULTS = flat_defaults()
PAR_STYLE = dict((name, style) for _pg, pars in PAGES for name, style, _d, _o in pars)
MENUS = dict((name, o['names']) for _pg, pars in PAGES for name, style, _d, o in pars if style == 'Menu')


def menu_index(names, v):
    try:
        return names.index(v)
    except ValueError:
        return 0


def emit_index(mode, connected):
    """emit_src Switch TOP index: 0 = white 1x1 default, 1 = in_emit, 2 = webcam clip frame difference."""
    if mode == 'cam':
        return 2
    if mode == 'input' or (mode == 'auto' and connected):
        return 1
    return 0


def side(count):
    """Particles sit on a side x side grid (one thread each); Count rounds up to it, extra slots never render."""
    return max(1, int(math.ceil(math.sqrt(max(1, int(count))) - 1e-9)))


def state_res(count):
    s = side(count)
    return (TEXELS * s, s)


# ---------------------------------------------------------------- hash (identical to particles_state.glsl)
def hash_u32(x):
    x &= M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def rnd(i, salt):
    """0..1 (24-bit, exact in float32) per (particle id, salt)."""
    return (hash_u32((i * 2654435761 + salt) & M32) >> 8) / 16777216.0


def spawn_salt(seed, frame):
    return (hash_u32(int(seed) & M32) ^ ((int(frame) * 0x9E3779B9) & M32)) & M32


# ---------------------------------------------------------------- control layer (audio / BPM / manual / CHOP)
def bpm_env(bpm, t, nudge=0.0):
    """Synthetic beat envelopes: kick on the beat, mid off-beat, high on 8ths. Returns kick bass mid high level beat phase."""
    beat = float(t) * float(bpm) / 60.0 + float(nudge)
    ph = beat % 1.0
    kick = math.exp(-8.0 * ph)
    bass = math.exp(-3.0 * ph)
    mid = math.exp(-8.0 * ((ph + 0.5) % 1.0))
    high = math.exp(-12.0 * ((ph * 2.0) % 1.0))
    return {'kick': kick, 'bass': bass, 'mid': mid, 'high': high, 'level': (kick + bass + mid + high) / 4.0,
            'beat': beat, 'phase': ph}


def smooth(prev, x, dt, tau):
    """One-pole lag; tau <= 0 or no previous value = pass through."""
    if prev is None or tau <= 0 or dt <= 0:
        return x
    return prev + (x - prev) * (1.0 - math.exp(-dt / tau))


def ctl_raw(mode, raw, chop_vals, t):
    """Unsmoothed control channels for this frame."""
    z = {k: 0.0 for k in CTL_CHANS}
    z['beat'] = z['phase'] = 0.0
    if mode == 'manual':
        m = [float(raw.get('Manual{}'.format(k), 0.0)) for k in (1, 2, 3, 4)]
        z.update(kick=m[0], bass=m[1], mid=m[2], high=m[3], level=sum(m) / 4.0)
    elif mode == 'bpm':
        z.update(bpm_env(raw.get('Bpm', 120.0), t, raw.get('Tapnudge', 0.0)))
    elif mode == 'chop':
        cv = chop_vals or {}
        got = [k for k in CTL_CHANS[:4] if k in cv]
        for k in CTL_CHANS[:4]:
            z[k] = float(cv.get(k, 0.0))
        z['level'] = float(cv['level']) if 'level' in cv else (sum(z[k] for k in got) / len(got) if got else 0.0)
    return z


# ---------------------------------------------------------------- per-frame CPU step
def new_state():
    return {'frame': 0, 'simt': 0.0, 'head': 0, 'acc': 0.0, 'key': None, 't': None, 'ctl': None, 'kick_prev': 0.0,
            'started': False}


def _g(raw, k):
    return raw[k] if k in raw else DEFAULTS[k]


def _v3(raw, k):
    return (float(_g(raw, k + 'x')), float(_g(raw, k + 'y')), float(_g(raw, k + 'z')))


def unit3(v, fb=(0.0, 1.0, 0.0)):
    l = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / l, v[1] / l, v[2] / l) if l > 1e-9 else tuple(fb)


def spiral_rows(raw, k):
    """3 rows of spiral k: (centre, swirl), (unit axis, pull), (lift, radius, 0, 0); off = all strengths 0."""
    s = 'Sp%d' % k
    on = bool(_g(raw, s + 'on'))
    g = lambda n: float(_g(raw, s + n)) if on else 0.0
    return [_v3(raw, s + 'pos') + (g('swirl'),), unit3(_v3(raw, s + 'axis')) + (g('pull'),),
            (g('lift'), float(_g(raw, s + 'radius')), 0.0, 0.0)]


def step(st, raw, ctl_in=None, events=(), t=0.0):
    """One cooked frame. raw = {TD par name: value} (flat, as the COMP's custom pars evaluate), ctl_in = CHOP channel
    values (Audiosrc chop), events = 'reset' / 'burst' pulses since the last step, t = wall seconds (BPM clock).
    Returns (st, {'rows': NROWS x 4 floats, 'info': {...}})."""
    st = dict(st) if st else new_state()
    ev = list(events or ())
    t = float(t)
    wdt = 0.0 if st['t'] is None else max(0.0, t - st['t'])
    st['t'] = t
    count = max(1, int(_g(raw, 'Count')))
    seed = int(_g(raw, 'Seed')) & 0xFFFFFF
    key = (count, seed, str(_g(raw, 'Statemode')))
    reset = (not st['started']) or ('reset' in ev) or key != st['key']
    st['key'] = key
    st['started'] = True

    # control layer
    mode = str(_g(raw, 'Audiosrc'))
    cr = ctl_raw(mode, raw, ctl_in, t)
    prev = st['ctl'] or {}
    tau = float(_g(raw, 'Smooth'))
    ctl = {k: smooth(prev.get(k), cr[k], wdt, tau) for k in CTL_CHANS}
    ctl['beat'], ctl['phase'] = cr['beat'], cr['phase']
    st['ctl'] = ctl
    kick_edge = ctl['kick'] >= 0.5 > st['kick_prev']
    st['kick_prev'] = ctl['kick']

    play = bool(_g(raw, 'Play'))
    speed = float(_g(raw, 'Speed')) * (1.0 + float(_g(raw, 'Amtspeed')) * ctl['level'])
    dt = speed / FPS_NOMINAL if play else 0.0

    if reset:
        st.update(frame=0, simt=0.0, head=0, acc=0.0)
        dt_row, wlen = 0.0, 0
    else:
        if play:
            st['frame'] = (st['frame'] + 1) % FRAME_WRAP
        st['simt'] += dt
        dt_row = dt
        births = 0
        if play and str(_g(raw, 'Emitmode')) == 'rate':
            st['acc'] += max(0.0, float(_g(raw, 'Rate'))) * dt
            n = int(math.floor(st['acc']))
            st['acc'] -= n
            births += n
        bc = max(0, int(_g(raw, 'Burstcount')))
        if 'burst' in ev:
            births += bc
        amt_b = float(_g(raw, 'Amtburst'))
        if play and kick_edge and amt_b > 0 and bool(_g(raw, 'Autohit')):
            births += int(round(amt_b * bc))
        wlen = min(count, births)
    w0 = st['head']
    st['head'] = (st['head'] + (0 if reset else wlen)) % count

    curlk = float(_g(raw, 'Curlstrength')) + float(_g(raw, 'Amtcurl')) * ctl['bass']
    curlt = (st['simt'] * float(_g(raw, 'Curlspeed'))) % CURL_WRAP
    amt_att = float(_g(raw, 'Amtatt')) * ctl['mid']
    a1 = (float(_g(raw, 'Att1strength')) + amt_att) if _g(raw, 'Att1on') else 0.0
    a2 = (float(_g(raw, 'Att2strength')) + amt_att) if _g(raw, 'Att2on') else 0.0
    vs = float(_g(raw, 'Vortexstrength')) if _g(raw, 'Vortexon') else 0.0
    size = float(_g(raw, 'Size')) * (1.0 + float(_g(raw, 'Amtsize')) * ctl['kick'])
    bright = float(_g(raw, 'Bright')) + float(_g(raw, 'Amtbright')) * ctl['level']
    s = side(count)
    oct_ = max(0, min(MAX_OCTAVES, int(_g(raw, 'Curloctaves'))))
    rows = [
        (dt_row, float(st['frame']), 1.0 if reset else 0.0, float(count)),
        (float(s), float(seed), float(menu_index(EMITMODES, _g(raw, 'Emitmode'))),
         float(menu_index(SOURCES, _g(raw, 'Source')))),
        (float(w0), float(wlen), float(_g(raw, 'Life')), float(_g(raw, 'Lifevar'))),
        (curlk, float(_g(raw, 'Curlscale')), curlt, float(oct_)),
        _v3(raw, 'Gravity') + (float(_g(raw, 'Drag')),),
        _v3(raw, 'Wind') + (float(_g(raw, 'Fieldstrength')),),
        _v3(raw, 'Att1pos') + (a1,),
        _v3(raw, 'Att2pos') + (a2,),
        _v3(raw, 'Vortexaxis') + (vs,),
        (float(_g(raw, 'Att1soft')), float(_g(raw, 'Att2soft')), float(menu_index(BOUNDS, _g(raw, 'Bounds'))),
         1.0 if _g(raw, 'Floor') else 0.0),
        _v3(raw, 'Boundsize') + (float(_g(raw, 'Floory')),),
        (float(_g(raw, 'Bounce')), float(_g(raw, 'Initspeed')), float(_g(raw, 'Initspread')),
         float(_g(raw, 'Emitthreshold'))),
        _v3(raw, 'Emitpos') + (float(menu_index(EMITWEIGHTS, _g(raw, 'Emitweight'))),),
        _v3(raw, 'Emitsize') + (1.0 if _g(raw, 'Stagger') else 0.0,),
        _v3(raw, 'Emitdir') + (1.0 if _g(raw, 'Debugstamp') else 0.0,),
        (size, float(_g(raw, 'Sizevar')), float(_g(raw, 'Sizeage')), bright),
        (float(_g(raw, 'Softness')), float(menu_index(COLORMODES, _g(raw, 'Colormode'))), float(_g(raw, 'Speedref')),
         float(menu_index(BLENDS, _g(raw, 'Blend')))),
        (float(_g(raw, 'Colour1r')), float(_g(raw, 'Colour1g')), float(_g(raw, 'Colour1b')), 1.0),
        (float(_g(raw, 'Colour2r')), float(_g(raw, 'Colour2g')), float(_g(raw, 'Colour2b')), 1.0),
        (float(_g(raw, 'Colour3r')), float(_g(raw, 'Colour3g')), float(_g(raw, 'Colour3b')), 1.0),
    ]
    for k in (1, 2):
        rows += spiral_rows(raw, k)
    ld = unit3(_v3(raw, 'Lightdir'), (0.0, 0.0, 1.0))
    rows += [
        (float(max(1, min(MAX_STRANDS, int(_g(raw, 'Strands'))))), float(_g(raw, 'Strandjitter')), 0.0, 0.0),
        (float(menu_index(PALBY, _g(raw, 'Palby'))), float(_g(raw, 'Palpos')), float(_g(raw, 'Palspread')), 0.0),
        (float(menu_index(SHAPES, _g(raw, 'Shape'))), float(_g(raw, 'Spinrate')), float(_g(raw, 'Paperaspect')),
         float(_g(raw, 'Ambient'))),
        ld + (float(_g(raw, 'Streamerlen')),),
        (float(_g(raw, 'Flutter')), float(_g(raw, 'Flutterhz')), float(_g(raw, 'Initspeedvar')), 0.0),
    ]
    info = {'frame': float(st['frame']), 'simt': st['simt'], 'dt': dt_row, 'reset': 1.0 if reset else 0.0,
            'head': float(st['head']), 'births': float(wlen), 'count': float(count), 'side': float(s),
            'curlk': curlk, 'size': size, 'bright': bright}
    for k in CTL_CHANS + ('beat', 'phase'):
        info[k] = float(ctl[k])
    return st, {'rows': rows, 'info': info}


# ---------------------------------------------------------------- camera
def cam_pose(dist, orbit_deg_s, t, camx=0.0, camy=0.0):
    """Camera on a circle of radius dist around the origin, looking at it; Orbit = deg/s. Returns (tx, ty, tz, ry)."""
    ang = (float(orbit_deg_s) * float(t)) % 360.0
    a = math.radians(ang)
    return (float(dist) * math.sin(a) + float(camx), float(camy), float(dist) * math.cos(a), ang)


def ortho_width(dist, fov_deg):
    """Ortho width that frames what the perspective view shows at the origin."""
    return 2.0 * float(dist) * math.tan(math.radians(float(fov_deg)) * 0.5)


# ---------------------------------------------------------------- float64 reference of particles_state.glsl
def curl1(p, t):
    """Analytic curl of Psi(p,t) = (sin(y+1.3t)cos(z-0.7t), sin(z+0.9t)cos(x+1.1t), sin(x-0.6t)cos(y+0.5t)).
    Divergence-free by construction; exact (no finite-difference noise in float32)."""
    x, y, z = p
    return (-math.sin(x - 0.6 * t) * math.sin(y + 0.5 * t) - math.cos(z + 0.9 * t) * math.cos(x + 1.1 * t),
            -math.sin(y + 1.3 * t) * math.sin(z - 0.7 * t) - math.cos(x - 0.6 * t) * math.cos(y + 0.5 * t),
            -math.sin(z + 0.9 * t) * math.sin(x + 1.1 * t) - math.cos(y + 1.3 * t) * math.cos(z - 0.7 * t))


def psi(p, t):
    x, y, z = p
    return (math.sin(y + 1.3 * t) * math.cos(z - 0.7 * t), math.sin(z + 0.9 * t) * math.cos(x + 1.1 * t),
            math.sin(x - 0.6 * t) * math.cos(y + 0.5 * t))


def curl_fd(p, t, h=1e-4):
    """Central-difference curl of psi (the spec's sketch); used only to check curl1."""
    def d(ax, comp):
        a = list(p)
        b = list(p)
        a[ax] += h
        b[ax] -= h
        return (psi(a, t)[comp] - psi(b, t)[comp]) / (2 * h)
    return (d(1, 2) - d(2, 1), d(2, 0) - d(0, 2), d(0, 1) - d(1, 0))


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _len(a):
    return math.sqrt(_dot(a, a))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit_dir(r0, r1):
    z = 2.0 * r0 - 1.0
    ph = TAU * r1
    s = math.sqrt(max(0.0, 1.0 - z * z))
    return (s * math.cos(ph), s * math.sin(ph), z)


SPIRAL_ROWS = (20, 23)          # uP rows of spiral 1 / 2 (3 rows each)
STRAND_ROW = 26
PAL_ROW = 27


def spiral_force(P, r0, r1, r2):
    """Spiral field (== the GLSL loop in forces()): swirl x tangent + pull toward the axis + lift along it, all
    scaled by g = R^2 / (d^2 + R^2) (R 0 -> 1), d = distance from P to the axis line through the centre."""
    sw, pull, lift, R = r0[3], r1[3], r2[0], r2[1]
    if sw == 0.0 and pull == 0.0 and lift == 0.0:
        return (0.0, 0.0, 0.0)
    A = r1[:3]
    r = (P[0] - r0[0], P[1] - r0[1], P[2] - r0[2])
    ra = _dot(r, A)
    rp = (r[0] - A[0] * ra, r[1] - A[1] * ra, r[2] - A[2] * ra)
    d2 = _dot(rp, rp)
    g = R * R / (d2 + R * R) if R > 0.0 else 1.0
    F = _mul(A, lift * g)
    if d2 > 1e-12:
        F = _add(F, _mul(_add(_mul(_cross(A, rp), sw), _mul(rp, -pull)), g / math.sqrt(d2)))
    return F


FLUTTER_ROW = 30
SHAPE_ROW = 28


def flutter(age, r, U):
    """Sideways sine flutter of paper (== the GLSL in forces()): per-particle phase r, rate Flutterhz."""
    k, hz = U[FLUTTER_ROW][0], U[FLUTTER_ROW][1]
    if k == 0.0:
        return (0.0, 0.0, 0.0)
    return (k * math.sin(TAU * (hz * age + r)), 0.0, k * math.cos(TAU * (0.7 * hz * age + 1.3 * r)))


def forces(P, V, U, field=None, age=0.0, r=0.0):
    curlk, sc0, ct, oc = U[3]
    F = (0.0, 0.0, 0.0)
    amp, sc = 1.0, sc0
    for o in range(MAX_OCTAVES):
        if o >= int(oc + 0.5):
            break
        F = _add(F, _mul(curl1(_mul(P, sc), ct + 17.0 * o), amp))
        amp *= 0.5
        sc *= 2.0
    F = _mul(F, curlk)
    g, drag = U[4][:3], U[4][3]
    F = _add(_add(F, g), _add(U[5][:3], _mul(V, -drag)))
    for row, soft in ((U[6], U[9][0]), (U[7], U[9][1])):
        if row[3] != 0.0:
            d = (row[0] - P[0], row[1] - P[1], row[2] - P[2])
            F = _add(F, _mul(d, row[3] * max(_dot(d, d) + soft, 1e-6) ** -1.5))
    ax = U[8][:3]
    al = _len(ax)
    if al > 1e-6 and U[8][3] != 0.0:
        F = _add(F, _mul(_cross(_mul(ax, 1.0 / al), P), U[8][3]))
    for base in SPIRAL_ROWS:
        F = _add(F, spiral_force(P, U[base], U[base + 1], U[base + 2]))
    F = _add(F, flutter(age, r, U))
    if U[5][3] != 0.0 and field is not None:
        hb = (max(U[10][0], 1e-3), max(U[10][1], 1e-3))
        fx, fy = field(P[0] / (2 * hb[0]) + 0.5, P[1] / (2 * hb[1]) + 0.5)
        F = (F[0] + U[5][3] * fx, F[1] + U[5][3] * fy, F[2])
    return F


def spawn(i, sb, U, emit=None):
    """New particle i. emit(u, v) -> (r, g, b, a) samples in_emit for the top/points sources (None = white 1x1)."""
    src = int(U[1][3] + 0.5)
    r0, r1, r2 = rnd(i, sb), rnd(i, sb + 1), rnd(i, sb + 2)
    col = (1.0, 1.0, 1.0)
    ok = True
    if src == 0:
        d = _unit_dir(r0, r1)
        u = _mul(d, r2 ** (1.0 / 3.0))
    elif src == 1:
        u = (2 * r0 - 1, 2 * r1 - 1, 2 * r2 - 1)
    elif src == 2:
        u = (math.cos(TAU * r0), math.sin(TAU * r0), 0.0)
    elif src == 3:
        u = (2 * r0 - 1, 0.0, 0.0)
    elif src == 6:
        u, cw = strand_seed(i, sb, U)
    else:
        u = (0.0, 0.0, 0.0)
        ok = False
        em = emit or (lambda uu, vv: (1.0, 1.0, 1.0, 1.0))
        for k in range(8):
            uu, vv = rnd(i, sb + 20 + 2 * k), rnd(i, sb + 21 + 2 * k)
            e = em(uu, vv)
            if src == 4:
                w = e[3] if U[12][3] > 0.5 else (e[0] * LUMA[0] + e[1] * LUMA[1] + e[2] * LUMA[2])
                if w > U[11][3]:
                    u, col, ok = (2 * uu - 1, 2 * vv - 1, 0.0), (e[0], e[1], e[2]), True
                    break
            elif e[3] > 0.0:
                u, ok = (e[0], e[1], e[2]), True
                break
    P = _add(U[12][:3], (u[0] * U[13][0], u[1] * U[13][1], u[2] * U[13][2]))
    rd = _unit_dir(rnd(i, sb + 3), rnd(i, sb + 4))
    ed = U[14][:3]
    el = _len(ed)
    spread = min(max(U[11][2], 0.0), 1.0)
    d = tuple(ed[k] / el + (rd[k] - ed[k] / el) * spread for k in range(3)) if el > 1e-6 else rd
    dl = _len(d)
    d = _mul(d, 1.0 / dl) if dl > 1e-6 else rd
    V = _mul(d, U[11][1] * (1.0 + U[FLUTTER_ROW][2] * (2.0 * rnd(i, sb + 9) - 1.0)))
    life = max(U[2][2] * (1.0 + U[2][3] * (2.0 * rnd(i, sb + 5) - 1.0)), 1e-3)
    w = cw if src == 6 else rnd(i, sb + 6)
    return [P[0], P[1], P[2], 0.0], [V[0], V[1], V[2], life if ok else 0.0], [col[0], col[1], col[2], w]


def strand_seed(i, sb, U):
    """Source strands: seed k of K on the unit ring (x y) + a box jitter; returns (u, strand id share (k+0.5)/K)
    which the particle keeps in colour.w (size var + palette 'random' = one colour per strand)."""
    K = max(int(U[STRAND_ROW][0] + 0.5), 1)
    k = min(int(math.floor(rnd(i, sb) * K)), K - 1)
    a = TAU * k / K
    j = U[STRAND_ROW][1]
    u = (math.cos(a) + j * (2.0 * rnd(i, sb + 1) - 1.0), math.sin(a) + j * (2.0 * rnd(i, sb + 2) - 1.0),
         j * (2.0 * rnd(i, sb + 8) - 1.0))
    return u, (k + 0.5) / K


def in_window(i, w0, wlen, count):
    if wlen <= 0:
        return False
    return ((i - int(w0)) % count) < wlen


def update(i, s, U, emit=None, field=None):
    """One frame for particle i; s = [a, b, c] (lists of 4) or None (fresh texture = zeros). Mirrors main()."""
    a, b, c = ([list(x) for x in s] if s is not None else [[0.0] * 4, [0.0] * 4, [0.0] * 4])
    dt, frame, reset, count = U[0]
    count = int(count + 0.5)
    sb = spawn_salt(int(U[1][1] + 0.5), int(frame + 0.5))
    emode = int(U[1][2] + 0.5)
    if reset > 0.5:
        a, b, c = spawn(i, sb, U, emit)
        if emode == 0 and U[13][3] > 0.5:
            a[3] = -rnd(i, sb + 7) * b[3]
        elif emode == 1:
            a[3], b[3] = 0.0, 0.0
    elif in_window(i, U[2][0], int(U[2][1] + 0.5), count):
        a, b, c = spawn(i, sb, U, emit)
    elif a[3] < 0.0:
        a[3] += dt
    elif a[3] < b[3]:
        P, V = tuple(a[:3]), tuple(b[:3])
        F = forces(P, V, U, field, a[3], c[3])
        V = _add(V, _mul(F, dt))
        P = _add(P, _mul(V, dt))
        age, life = a[3] + dt, b[3]
        P, V = list(P), list(V)
        bm = int(U[9][2] + 0.5)
        B = U[10][:3]
        if bm == 1:
            for k in range(3):
                if B[k] > 0.0:
                    x = P[k] + B[k]
                    P[k] = x - 2.0 * B[k] * math.floor(x / (2.0 * B[k])) - B[k]
        elif bm == 2:
            for k in range(3):
                if B[k] > 0.0 and abs(P[k]) > B[k]:
                    sg = 1.0 if P[k] > 0 else -1.0
                    P[k] = min(max(sg * (2.0 * B[k] - abs(P[k])), -B[k]), B[k])
                    V[k] = -V[k] * U[11][0]
        elif bm == 3:
            if any(B[k] > 0.0 and abs(P[k]) > B[k] for k in range(3)):
                age = life
        if U[9][3] > 0.5 and P[1] < U[10][3]:
            P[1] = U[10][3]
            V[1] = abs(V[1]) * U[11][0]
        a = [P[0], P[1], P[2], age]
        b = [V[0], V[1], V[2], life]
    if reset <= 0.5 and emode == 0 and a[3] >= b[3]:      # continuous: reborn the frame it dies
        a, b, c = spawn(i, sb, U, emit)
    if U[14][3] > 0.5:
        c[3] = frame
    return [a, b, c]


def alive(s):
    return s is not None and 0.0 <= s[0][3] < s[1][3]


def reference_run(raw, frames, ids, ctl_in=None, emit=None, field=None, t0=0.0, events_at=None):
    """Run `frames` cooked frames (frame 1 = the reset frame, as in TD) for the particle ids given.
    Particles are independent, so only the sampled ids are simulated. Returns ({id: [a, b, c]}, last step out)."""
    st, out = None, None
    S = {i: None for i in ids}
    for f in range(frames):
        ev = (events_at or {}).get(f, ())
        st, out = step(st, raw, ctl_in, ev, t0 + f / FPS_NOMINAL)
        U = out['rows']
        for i in ids:
            if i < int(U[0][3] + 0.5):
                S[i] = update(i, S[i], U, emit, field)
    return S, out


def sample_ids(count, n=64, seed=12345):
    """The fixed ids the live V1/V6 checks read (spread over the grid, deterministic)."""
    count = max(1, int(count))
    return sorted(set(int(rnd(k, seed) * count) for k in range(n * 2)))[:n]


def id_texel(i, count):
    """Texel coords (x, y) of particle i's first texel (P, age) in the state texture (row 0 = bottom, T-58)."""
    s = side(count)
    return (TEXELS * (i % s), i // s)


# Live check V1 pars: forces off except curl (+ drag, which keeps float32-vs-float64 drift bounded), no deaths
V1_PARS = {'Seed': 1, 'Count': 4096, 'Stagger': False, 'Life': 100.0, 'Lifevar': 0.0, 'Bounds': 'none', 'Drag': 0.8,
           'Initspeed': 0.0, 'Curlstrength': 1.0, 'Curlscale': 1.5, 'Curlspeed': 0.3, 'Curloctaves': 1,
           'Emitmode': 'continuous', 'Source': 'ball', 'Speed': 1.0, 'Audiosrc': 'off', 'Gravityx': 0.0,
           'Gravityy': 0.0, 'Gravityz': 0.0, 'Windx': 0.0, 'Windy': 0.0, 'Windz': 0.0, 'Att1on': False,
           'Att2on': False, 'Vortexon': False, 'Fieldstrength': 0.0, 'Floor': False, 'Debugstamp': False,
           'Play': True, 'Statemode': 'feedback'}


# Live check V12 pars (lane G): both spirals + strand seeds + curl, no deaths: parity of the new forces / source
V12_PARS = dict(V1_PARS, Source='strands', Strands=7, Strandjitter=0.05, Emitsizex=1.2, Emitsizey=1.2, Emitsizez=1.0,
                Sp1on=True, Sp1swirl=2.0, Sp1pull=0.6, Sp1lift=0.4, Sp1radius=0.8, Sp1axisx=0.0, Sp1axisy=0.0,
                Sp1axisz=1.0, Sp2on=True, Sp2posy=0.8, Sp2swirl=-1.2, Sp2pull=0.0, Sp2lift=0.0, Sp2radius=0.6,
                Sp2axisx=1.0, Sp2axisy=0.0, Sp2axisz=0.0, Initspeed=0.3, Initspread=1.0)

# ---------------------------------------------------------------- PX_lines light trails (TC-08)
# Constant pars of the PX_lines child (only trails, points mode on the BO state texture: texel 3x = P.xyz, age)
LINE_CONST = {'Rings': False, 'Contour': False, 'Connect': False, 'Polyline': False, 'Edges': False, 'Trails': True,
              'Trmotion': 'points', 'Outmode': 'composite', 'Ptstride': TEXELS, 'Trfirst': 0, 'Trcount': 0,
              'Usedepth': False, 'Occlusion': 'over', 'Amount': 1.0}
# child par <- BO par (menus by name)
LINE_PAIRS = [('Ptcount', 'Count'), ('Resx', 'Resx'), ('Resy', 'Resy'), ('Trtracks', 'Linetracks'),
              ('Trsamples', 'Linesamples'), ('Trevery', 'Lineevery'), ('Width', 'Linewidth'), ('Halo', 'Linehalo'),
              ('Halogain', 'Linehalogain'), ('Intensity', 'Lineintensity'), ('Trtaper', 'Linetaper'),
              ('Trfade', 'Linefade'), ('Trmaxjump', 'Linemaxjump'), ('Linecolsrc', 'Linecolsrc'),
              ('Trattr', 'Lineattr'), ('Linepalpos', 'Linepalpos'), ('Linepalspread', 'Linepalspread'),
              ('Blend', 'Lineblend'), ('Palsource', 'Palsource'), ('Palmode', 'Palmode'),
              ('Palinterp', 'Palinterp'), ('Palreverse', 'Palreverse'), ('Palshift', 'Palshift'),
              ('Linecolr', 'Linecolr'), ('Linecolg', 'Linecolg'), ('Linecolb', 'Linecolb')]


def line_links():
    """{PX_lines par: TD expression} for the child (evaluated in the child COMP's par context: parent() = BO)."""
    d = dict((child, 'parent().par.%s.eval()' % mine) for child, mine in LINE_PAIRS)
    d['Maxseg'] = 'max(1024, int(parent().par.Linetracks.eval()) * max(2, int(parent().par.Linesamples.eval())))'
    return d


def line_segments(raw):
    """Trail segments PX_lines will draw (tracks x (samples - 1) pieces, the history ring), for docs / checks."""
    return int(_g(raw, 'Linetracks')) * (max(int(_g(raw, 'Linesamples')), 2) - 1)


# ---------------------------------------------------------------- presets (FULL state: defaults + the preset, T-124 (1))
# Pars a preset never touches (deployment / debug choices): output size, state mode, debug stamp, the CHOP path.
PRESET_KEEP = ('Resx', 'Resy', 'Statemode', 'Debugstamp')
PRESETS = [
    (1, 'default', {}),
    # TC-08 light-trail ribbons: few fast particles fly at the camera through a soft curl, PX_lines draws each one's
    # trail as a tapering neon ribbon (colour running along it), dots off (the render does not cook)
    (2, 'lighttrails', {'Count': 1024, 'Source': 'box', 'Emitpos': (0.0, 0.0, -12.0), 'Emitsize': (4.0, 7.0, 2.0),
                        'Emitdir': (0.0, 0.0, 1.0), 'Initspeed': 3.0, 'Initspread': 0.06, 'Life': 3.0, 'Lifevar': 0.3,
                        'Curlstrength': 0.8, 'Curlscale': 0.35, 'Curlspeed': 0.15, 'Drag': 0.0, 'Bounds': 'none',
                        'Lineson': True, 'Linedots': False, 'Linetracks': 1024, 'Linesamples': 24, 'Lineevery': 2,
                        'Linewidth': 1.4, 'Linehalo': 1.5, 'Lineintensity': 0.9, 'Linetaper': 1.0, 'Linefade': 1.2,
                        'Linecolsrc': 'attr', 'Lineattr': 'along', 'Linepalspread': 1.0,
                        'Palsource': 'cyan_magenta', 'Palmode': 'gradient', 'Bloom': 0.0}),
    # TC-13 vortex: a spiral field (swirl + pull + lift) turns a box of dust into a rising column that wraps forever
    (3, 'vortex', {'Count': 131072, 'Source': 'box', 'Emitpos': (0.0, -4.0, 0.0), 'Emitsize': (2.5, 0.3, 2.5),
                   'Initspeed': 0.1, 'Life': 10.0, 'Lifevar': 0.3, 'Curlstrength': 0.25, 'Curlscale': 1.2,
                   'Drag': 0.4, 'Bounds': 'wrap', 'Boundsize': (6.0, 4.5, 6.0), 'Sp1on': True, 'Sp1swirl': 3.5,
                   'Sp1pull': 2.0, 'Sp1lift': 1.5, 'Sp1radius': 1.5, 'Size': 0.006, 'Bright': 1.0,
                   'Colormode': 'palette', 'Palby': 'speed', 'Palsource': 'neon_trio', 'Speedref': 2.5,
                   'Palspread': 1.5,
                   'Trails': True, 'Trailfade': 0.9, 'Bloom': 0.7, 'Camdist': 9.0}),
    # TC-13 strands: particles born on a few seed points follow nearly the same path through two spirals + curl, the
    # trail feedback joins them into fine curling strands (one palette colour per strand)
    (4, 'strands', {'Count': 32768, 'Source': 'strands', 'Strands': 9, 'Strandjitter': 0.015,
                    'Emitsize': (1.2, 1.2, 0.0), 'Initspeed': 0.0, 'Initspread': 1.0, 'Life': 6.0, 'Lifevar': 0.2,
                    'Curlstrength': 0.8, 'Curlscale': 0.8, 'Drag': 0.6, 'Bounds': 'none',
                    'Sp1on': True, 'Sp1axis': (0.0, 0.0, 1.0), 'Sp1swirl': 1.6, 'Sp1pull': 0.3, 'Sp1lift': 0.6,
                    'Sp1radius': 1.0, 'Sp2on': True, 'Sp2pos': (0.0, 0.8, 0.0), 'Sp2axis': (1.0, 0.0, 0.0),
                    'Sp2swirl': -1.2, 'Sp2pull': 0.0, 'Sp2radius': 0.6, 'Size': 0.004, 'Sizevar': 0.2,
                    'Bright': 0.8, 'Colormode': 'palette', 'Palby': 'random', 'Palsource': 'rainbow',
                    'Trails': True, 'Trailfade': 0.97, 'Bloom': 1.0, 'Orbit': 6.0}),
    # light vortex: the spiral field drawn as neon trails (lines), one palette stop per trail
    (5, 'lightvortex', {'Count': 1024, 'Source': 'ring', 'Emitsize': (2.5, 2.5, 0.0), 'Initspeed': 0.2,
                        'Life': 8.0, 'Lifevar': 0.4, 'Curlstrength': 0.3, 'Drag': 0.3, 'Bounds': 'wrap',
                        'Boundsize': (3.0, 3.0, 3.0), 'Sp1on': True, 'Sp1axis': (0.0, 0.0, 1.0), 'Sp1swirl': 3.0,
                        'Sp1pull': 1.0, 'Sp1lift': 0.8, 'Sp1radius': 1.2, 'Lineson': True, 'Linedots': False,
                        'Linetracks': 1024, 'Linesamples': 32, 'Linewidth': 1.0, 'Linehalo': 1.5,
                        'Lineintensity': 1.2, 'Lineblend': 'max', 'Linecolsrc': 'index', 'Lineattr': 'index',
                        'Linepalspread': 1.0, 'Linemaxjump': 1.0, 'Palsource': 'neon_trio', 'Palmode': 'steps',
                        'Bloom': 0.0}),
    # 7C-11 confetti cannon: paper pieces burst up on Hit (Burst pulse) or on the kick (AC_audio out_ctl kick, U7:
    # wired but Autohit OFF, the operator turns it on), tumble two-sided, flutter and fall at terminal speed
    (6, 'confetti', {'Count': 32768, 'Source': 'box', 'Emitpos': (0.0, -4.2, 0.0), 'Emitsize': (1.5, 0.2, 0.5),
                     'Emitdir': (0.0, 1.0, 0.0), 'Initspeed': 7.0, 'Initspread': 0.35, 'Emitmode': 'rate',
                     'Rate': 0.0, 'Burstcount': 5000, 'Life': 7.0, 'Lifevar': 0.3, 'Curlstrength': 0.6,
                     'Initspeedvar': 0.45,
                     'Curlscale': 0.8, 'Gravity': (0.0, -2.5, 0.0), 'Drag': 1.2, 'Bounds': 'none',
                     'Flutter': 1.5, 'Flutterhz': 1.2, 'Shape': 'paper', 'Spinrate': 1.5, 'Paperaspect': 0.6,
                     'Size': 0.035, 'Sizevar': 0.3, 'Sizeage': 0.0, 'Softness': 0.3, 'Colormode': 'palette',
                     'Palby': 'random', 'Palsource': 'rainbow', 'Palmode': 'steps', 'Blend': 'alpha', 'Bright': 1.0,
                     'Audiosrc': 'chop', 'Chop': KICK_CHOP, 'Amtburst': 1.0, 'Autohit': False, 'Camdist': 9.0}),
    # streamers: long twisting ribbons along the velocity, fewer and bigger
    (7, 'streamers', {'Count': 4096, 'Source': 'box', 'Emitpos': (0.0, -4.2, 0.0), 'Emitsize': (1.5, 0.2, 0.5),
                      'Emitdir': (0.0, 1.0, 0.0), 'Initspeed': 7.5, 'Initspread': 0.3, 'Emitmode': 'rate',
                      'Rate': 0.0, 'Burstcount': 700, 'Life': 7.0, 'Lifevar': 0.3, 'Curlstrength': 0.5,
                      'Initspeedvar': 0.4,
                      'Curlscale': 0.6, 'Gravity': (0.0, -2.0, 0.0), 'Drag': 1.0, 'Bounds': 'none', 'Flutter': 1.0,
                      'Flutterhz': 0.8, 'Shape': 'streamer', 'Spinrate': 1.0, 'Streamerlen': 8.0, 'Size': 0.02,
                      'Sizevar': 0.2, 'Sizeage': 0.0, 'Softness': 0.3, 'Colormode': 'palette', 'Palby': 'random',
                      'Palsource': 'neon_trio', 'Palmode': 'steps', 'Blend': 'alpha', 'Bright': 1.0,
                      'Audiosrc': 'chop', 'Chop': KICK_CHOP, 'Amtburst': 1.0, 'Autohit': False, 'Camdist': 9.0}),
    # confetti rain: continuous paper falling from the top (no hit needed)
    (8, 'confetti rain', {'Count': 16384, 'Source': 'box', 'Emitpos': (0.0, 4.8, 0.0), 'Emitsize': (3.5, 0.1, 1.5),
                          'Initspeed': 0.0, 'Life': 6.0, 'Lifevar': 0.2, 'Curlstrength': 0.4, 'Curlscale': 0.5,
                          'Gravity': (0.0, -1.5, 0.0), 'Drag': 1.5, 'Bounds': 'none', 'Flutter': 1.2,
                          'Flutterhz': 1.0, 'Shape': 'paper', 'Spinrate': 1.2, 'Paperaspect': 0.6, 'Size': 0.03,
                          'Sizevar': 0.3, 'Sizeage': 0.0, 'Softness': 0.3, 'Colormode': 'palette', 'Palby': 'random',
                          'Palsource': 'fire', 'Palmode': 'steps', 'Blend': 'alpha', 'Bright': 1.0, 'Camdist': 9.0}),
]
PRESET_NAMES = [n for _s, n, _v in PRESETS]


def _flat(name, v):
    """One preset entry -> flat TD names (XYZ / RGB tuples split)."""
    st = PAR_STYLE.get(name)
    if st in ('XYZ', 'RGB'):
        return dict((name + s, float(x)) for s, x in zip('xyz' if st == 'XYZ' else 'rgb', v))
    return {name: v}


def preset_pars(name):
    """FULL state of a preset as {flat TD name: value} (menus by name): defaults, then the preset; PRESET_KEEP left out."""
    vals = next(v for _s, n, v in PRESETS if n == name or str(_s) == str(name))
    d = dict(DEFAULTS)
    for k, v in vals.items():
        d.update(_flat(k, v))
    for k in PRESET_KEEP:
        d.pop(k, None)
    return d


def preset_zk(name):
    """preset_pars with menus as indexes (zkit zk_presets data form)."""
    d = preset_pars(name)
    for k, v in list(d.items()):
        if k in MENUS:
            d[k] = menu_index(MENUS[k], v)
    return d


def compare_state(arr, raw, frames, ids=None):
    """Compare a state readback with the reference. arr[y][x] = (r, g, b, a) floats, row 0 = bottom (TD numpyArray,
    T-58); frames = cooked frames since the reset INCLUDING the reset frame (= info 'frame' channel + 1).
    Returns max abs errors for P, V, age plus the worst id."""
    r = dict(DEFAULTS)
    r.update(raw)
    count = int(r['Count'])
    ids = ids if ids is not None else sample_ids(count)
    S, _ = reference_run(r, int(frames), ids)
    worst = {'P': 0.0, 'V': 0.0, 'age': 0.0, 'id': None, 'n': len(ids)}
    for i in ids:
        x, y = id_texel(i, count)
        a, b = arr[y][x], arr[y][x + 1]
        ra, rb = S[i][0], S[i][1]
        eP = max(abs(float(a[k]) - ra[k]) for k in range(3))
        eV = max(abs(float(b[k]) - rb[k]) for k in range(3))
        if eP > worst['P']:
            worst['P'], worst['id'] = eP, i
        worst['V'] = max(worst['V'], eV)
        worst['age'] = max(worst['age'], abs(float(a[3]) - ra[3]))
    return worst
