"""px_logic - PX_pointfx pure logic (no td import; numpy only inside ref_*/np_* functions). Clean-room, 26 Oct 2026.

Copied into the COMP as the Text DAT `px_logic` by builders/px.py; tested by test/test_px.py.
Design: docs/builds/px.md. Catalog / maths: docs/research/BR_rubenfro_pointcloud_fx.md section 4. User rules:
docs/builds/px_requirements.md (modules added/removed/reordered/duplicated, effectors = visible scene objects,
gizmo preview, wide ranges, presets that morph whole looks).

What lives here:
  * MODULES - every effector module as data: stages, param schema (name, kind, default, slider range, menu).
    Its GLSL is the matching `//@module <type> <stage>` section of builders/glsl/px_modules.glsl.
  * The module STACK (list of instances {uid, type, enabled, label}) and its edits (add/remove/move/duplicate).
  * layout() + codegen(): the ENABLED instances, in stack order, become ONE compute shader per stage (update,
    colour). Param values are never baked in: each instance owns rows of the uniform array uM[] (header row =
    amount, effector bit mask, mask input, invert; then its params), so changing values / effector links never
    recompiles. structure_hash() changes only when the compiled text would (types, order, enable, uids, sources).
  * Per-frame packing (pack_module_rows, effector_rows, global_rows, render_rows, post_rows, source_rows), drives
    (audio / beat / triggers / LFO / effector speed / CHOP channels onto any param), rate params integrated to phases.
  * Presets: snapshot / morph between whole looks.
  * Reference maths in numpy (ref_* / np_*) mirroring px_common.glsl, px_source.glsl and selected modules; the
    numbers in docs/builds/px.md's live checks come from these.
"""
import hashlib
import json
import math
import re

NAME = 'PX_pointfx'
VERSION = 2

G_ROWS = 26          # uG[]: globals (decl() defines; 24, 25 = camera motion, wave 3 K25)
E_PER = 11           # rows per effector in uE[] (see effector_rows)
MAX_EFF = 8
E_ROWS = E_PER * MAX_EFF
R_ROWS = 10          # uR[]: render (row 8 = actor echoes, wave 4; row 9 = LOD, phase C)
Q_ROWS = 10          # uQ[]: post grade (+ flare)
SRC_ROWS = 18        # uSrc[]: source stage (+ actor layer; row 17 = image relief, wave 4)
SP_ROWS = 5          # uSp[]: splat adapter (PX side of the reused BL_splat_render shader; row 4 = LOD, phase C)
STATE_TEXELS = 5     # P/age, o/life, v/heat, mk/dis, q (final orientation wxyz)
REST_TEXELS = 4      # p0/valid, colour, scale (0 = no splat scale), quat
LOOK_TEXELS = 3      # rgb/alpha, size/stretch/iso/isosize, stretch dir xyz/thin
HEADER_ROWS = 3      # per instance: (amount, effmask, maskin, invert), (chunk, shared tag mask, all, on), (4 shared ids)
PTS_MAX = 4096       # point-set effector texture buffer (all pts effectors together)
TRAIL_MAX = 64       # trail ring buffer length per effector
GLOW_PER = 4         # uGl rows per glow instance (P, scale, quat, colour)
GLOW_MAX = 72        # glow instances (8 effectors x (1 + 8 trail glows))
STAGES = ('update', 'colour')

SPLAT_AA = [('aa1', '1x (fast)'), ('aa2', '2x'), ('aa4', '4x'), ('aa8mid', '8x'), ('aa16mid', '16x')]   # srender MSAA
QUALITY = [('draft', 'Draft 65k', 65536), ('std', 'Standard 131k', 131072), ('high', 'High 262k', 262144),
           ('ultra', 'Ultra 1M', 1048576), ('max', 'Max 4M (runs 2.68M: texture cap)', 4194304), ('custom', 'Custom (Count)', 0)]

# ----------------------------------------------------------------------------------------------- menus

FALLOFFS = [('smooth', 'Smooth'), ('linear', 'Linear'), ('gaussian', 'Gaussian'), ('step', 'Step (hard edge)'),
            ('shell', 'Shell (surface band)'), ('core', 'Core (inside only)'),
            ('behind', 'Behind (front: tail behind the motion)'), ('ahead', 'Ahead (front: tail ahead)'),
            ('wake', 'Wake (tube along the trail)')]
COMBINES = [('max', 'Max'), ('sum', 'Sum'), ('product', 'Product'), ('screen', 'Screen')]
MASKSEL = [('none', 'None (1)'), ('m0', 'Mask 0'), ('m1', 'Mask 1'), ('m2', 'Mask 2'), ('visible', 'Visible (1 - dissolve)'),
           ('dissolved', 'Dissolved'), ('heat', 'Heat'), ('scene', 'Scene layer only'), ('actor', 'Actor layer only'),
           ('pool', 'Pool (embers) only')]
MASKOUT = [('m0', 'Mask 0'), ('m1', 'Mask 1'), ('m2', 'Mask 2')]
MASKOPS = [('set', 'Set'), ('max', 'Max'), ('min', 'Min'), ('multiply', 'Multiply'), ('add', 'Add'), ('subtract', 'Subtract')]
PUBLISH = [('none', 'None'), ('m0', 'Mask 0'), ('m1', 'Mask 1'), ('m2', 'Mask 2')]
SPACES = [('current', 'Current position'), ('rest', 'Rest / home')]
AXES = [('x', 'X'), ('y', 'Y'), ('z', 'Z'), ('effector', 'Effector up axis'), ('view', 'View (camera forward)')]
STRETCH_AXES = [('velocity', 'Velocity (motion)'), ('view', 'View axis (camera forward)'), ('x', 'World X'),
                ('y', 'World Y'), ('z', 'World Z'), ('effector', 'Effector up axis'),
                ('radial_eff', 'Radial from effector'), ('radial_cam', 'Radial from camera')]
GENERATORS = [('sphere', 'Sphere'), ('grid', 'Grid cube'), ('torus', 'Torus'), ('plane', 'Plane'), ('cube', 'Cube surface'),
              ('helix', 'Helix'), ('ring', 'Ring'), ('spiral', 'Spiral galaxy'), ('cylinder', 'Cylinder'), ('ball', 'Ball')]
SOURCEMODES = [('file', 'File (ply xyz obj csv splat spz)'), ('gen', 'Generator'), ('depth', 'Depth TOP (DC_depth_cam)'),
               ('off', 'Off (B only)'), ('top', 'Points TOP (rgb xyz, a valid: Pointstop / in_xyz)'),
               ('image', 'Image relief (Pointstop / in_xyz picture: brightness -> height)')]   # wave 4 K27
IMGSRC = [('luma', 'Brightness'), ('hue', 'Hue'), ('alpha', 'Alpha'), ('red', 'Red')]
ACTORMODES = [('off', 'Off'), ('file', 'File (or sequence folder)'), ('gen', 'Generator'), ('depth', 'Depth TOP'),
              ('top', 'Points TOP (Pointstop / in_xyz)')]
AMODES = SOURCEMODES[:3] + SOURCEMODES[4:]
STAGGERS = [('random', 'Random'), ('radial', 'Radial'), ('height', 'Height'), ('none', 'None')]
EASES = [('linear', 'Linear'), ('smooth', 'Smoothstep'), ('sine', 'Sine'), ('cubic', 'Cubic in-out')]
COLMODES = [('position', 'Position ramp'), ('solid', 'Solid colour'), ('white', 'White')]
SPRITES = [('disc', 'Disc'), ('soft', 'Soft (gaussian)'), ('ring', 'Ring'), ('star', 'Star'), ('square', 'Square'),
           ('streak', 'Streak'), ('cube', 'Cube (shaded, oriented)'), ('quad', 'Quad (oriented slab)'),
           ('glyph', 'Glyph tiles (5x5 font, K21)'), ('dab', 'Pointillist dab (SA35)'), ('atlas', 'Atlas TOP cells')]
RENDERS = [('auto', 'Auto (splats for splat files)'), ('sprites', 'Sprites'), ('splats', 'Gaussian splats (sorted)')]
SORTMODES = [('auto', 'Auto (camera move / moving centres)'), ('always', 'Every frame'), ('frozen', 'Frozen (pulse)'),
             ('off', 'Off (additive, no sort)')]
BLENDS = [('add', 'Additive (no sort)'), ('alpha', 'Alpha over (unsorted)')]
TONEMAPS = [('none', 'None'), ('aces', 'ACES fit'), ('reinhard', 'Reinhard'), ('filmic', 'Filmic')]
EFF_KINDS = [('box', 'Box (Geometry COMP)'), ('sphere', 'Sphere (Geometry COMP)'), ('plane', 'Plane (Geometry COMP)'),
             ('null', 'Null COMP (point)'), ('capsule', 'Capsule'), ('torus', 'Torus'), ('chop', 'CHOP xyz (point)'),
             ('pts', 'Point set (CHOP / SOP, placed by a Null)'), ('actor', 'Actor layer (point set)'),
             ('camera', 'Camera (output camera)')]
# kind -> (sdf type, local size): unit shapes (box 1x1x1, sphere d=1, ...); the object's scale makes them bigger.
# 6 = point set (texture buffer uPts), 7 = actor layer points (read from the state texture); size x = point radius.
EFF_SDF = {'null': (0, (0.0, 0.0, 0.0)), 'chop': (0, (0.0, 0.0, 0.0)), 'point': (0, (0.0, 0.0, 0.0)),
           'sphere': (1, (0.5, 0.0, 0.0)), 'box': (2, (0.5, 0.5, 0.5)), 'plane': (3, (0.0, 0.0, 0.0)),
           'capsule': (4, (0.25, 0.5, 0.0)), 'torus': (5, (0.5, 0.15, 0.0)), 'pts': (6, (0.02, 0.0, 0.0)),
           'actor': (7, (0.02, 0.0, 0.0)), 'camera': (0, (0.0, 0.0, 0.0))}
MOTIONS = [('none', 'None (move it by hand)'), ('line', 'Line A -> B'), ('circle', 'Circle (centre A, radii B)'),
           ('lissajous', 'Lissajous (centre A, amp B, freq)'), ('chop', 'CHOP path (tx ty tz samples)'),
           ('wander', 'Noise wander (centre A, amp B)'), ('follow', 'Follow an object (+ A offset)')]
LOOPS = [('loop', 'Loop'), ('pingpong', 'Ping-pong'), ('once', 'Once')]
PTSMODES = [('nearest', 'Nearest point'), ('density', 'Density (soft sum)')]
# W1-B shared palette menus (copies of palette_map_logic's; test_px checks they match: px_logic stays import-free in TD)
COLSRC_MODES = [('solid', 'Solid colour'), ('palette', 'Palette at position'), ('attr', 'Palette by attribute'),
                ('source', 'Keep source colour'), ('index', 'Palette stop by index')]
PAL_MODES = [('gradient', 'Gradient (positioned stops)'), ('steps', 'Steps (equal bands)'),
             ('cycle', 'Cycle (wraps, last -> first)')]
PAL_INTERP = [('rgb', 'RGB'), ('oklab', 'OKLab')]
PAL_DRIVES = [('manual', 'Manual (Palshift)'), ('bpm_step', 'BPM step (one stop every N beats)'),
              ('bpm_cycle', 'BPM cycle (full turn every N beats)'), ('audio', 'Audio level (continuous)'),
              ('onset_step', 'Audio onsets (one stop per onset)')]
PAL_SOURCES = [('custom', 'Custom stops (Palstops: hex [pos], ...)'), ('file', 'From file'),
               ('neon_green', 'Neon green lines'), ('cyan_magenta', 'Cyan / magenta'),
               ('neon_trio', 'Neon green / cyan / magenta'), ('acid', 'Acid remap'), ('magenta_inv', 'Magenta inversion'),
               ('fire', 'Fire ramp'), ('px_ramp', 'PX ramp default (teal / orange)'), ('rainbow', 'Rainbow (use mode cycle)'),
               ('pico8', 'PICO-8'), ('sweetie16', 'Sweetie 16'), ('endesga32', 'Endesga 32'), ('resurrect64', 'Resurrect 64'),
               ('apollo', 'Apollo'), ('aap64', 'AAP-64'), ('db16', 'DawnBringer 16'), ('db32', 'DawnBringer 32'),
               ('slso8', 'SLSO8'), ('oil6', 'Oil 6'), ('twilight5', 'Twilight 5'), ('nyx8', 'Nyx8'),
               ('lostcentury', 'Lost Century'), ('gameboy', 'Game Boy (bgb)'), ('demichrome', '2bit Demichrome'),
               ('cga0hi', 'CGA 0 (high)'), ('monitorglow', '1bit Monitor Glow'), ('grey16', 'Grayscale 16'),
               ('solarized', 'Solarized'), ('bw', 'Black & white')]
LIGHT_MODELS = [('halflambert', 'Half-Lambert (soft)'), ('lambert', 'Lambert'), ('wrap', 'Wrap'),
                ('glow', 'No normal (glow by distance)')]          # = W1-A pxeLight mode.x 0..3
LIGHT_NORMALS = [('auto', 'Auto (splats: smallest axis; points: no normal)'), ('splat', 'Splat axis (smallest scale)'),
                 ('view', 'Facing the camera'), ('radial', 'Radial from the scene centre'), ('up', 'Up (world y)')]
LTYPES = [('point', 'Point'), ('spot', 'Spot (cone)'), ('area', 'Area / bar'), ('directional', 'Directional')]
CAM_MODES = [('orbit', 'Orbit (Camdist / Orbit / Camheight, the v2 camera)'), ('crane', 'Crane (arm looks at its base)'),
             ('dolly', 'Dolly A -> B (ping-pong)'), ('path', 'Path (Catmull-Rom through points)'),
             ('follow', 'Follow an effector'), ('director', 'Director (cuts on the beat)')]
GOV_DEFAULT = '/project1/lab/FG_fps_governor/out1'   # phase C: Autoquality governor
CAMSOURCES = [('internal', 'Internal (orbit / Camera rig)'), ('external', 'External Camera COMP (Camcomp)')]   # phase C
AUTOQ = [('off', 'Off (manual only)'), ('hold60', 'Hold 60 fps (steps down / up by itself)'),
         ('governor', 'Follow FG_fps_governor (Govop quality)')]                     # phase C
GEO_KINDS = [('box', 'Box'), ('sphere', 'Sphere'), ('torus', 'Torus'), ('plane', 'Plane (floor)'), ('tube', 'Tube / pillar')]
DRIVE_SOURCES = ['low', 'mid', 'high', 'level', 'beat', 'bar', 'trig1', 'trig2', 'trig3', 'trig4', 'lfo1', 'lfo2',
                 'espd1', 'espd2', 'espd3', 'espd4', 'espd5', 'espd6', 'espd7', 'espd8']


def names(menu):
    return [m[0] for m in menu]


def labels(menu):
    return [m[1] for m in menu]


def menu_index(menu, v):
    """token or index -> index (unknown token -> 0)."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    toks = names(menu)
    return toks.index(v) if v in toks else 0


# ----------------------------------------------------------------------------------------------- module schema

def P(name, kind, default, lo=0.0, hi=1.0, menu=None, label=None, rate=False):
    """Param: kind float | int | toggle | menu | xyz | rgb. lo/hi = slider range only (no clamps: no limits).
    rate=True: the engine integrates value*dt into a phase the GLSL reads as $<name>ph."""
    return {'name': name, 'kind': kind, 'default': default, 'lo': lo, 'hi': hi, 'menu': menu, 'label': label or name,
            'rate': rate}


def _prox():
    return [P('radius', 'float', 1.0, 0.0, 10.0), P('falloff', 'float', 1.0, 0.1, 8.0, label='falloff exp'),
            P('shape', 'menu', 'smooth', menu=FALLOFFS), P('combine', 'menu', 'max', menu=COMBINES),
            P('flip', 'toggle', 0, label='flip (far = 1)'), P('noiseedge', 'float', 0.0, 0.0, 2.0, label='ragged edge'),
            P('noisefreq', 'float', 2.0, 0.01, 50.0, label='edge noise freq'), P('space', 'menu', 'current', menu=SPACES),
            P('edge', 'float', 0.02, 0.0, 1.0, label='front edge (x radius; behind/ahead)')]


# auto progress (28 Oct, user: "i just put explode and the animation froze"): explode / dissolve_noise /
# dissolve_gradient are pure functions of `progress`; auto runs it by itself in the GLSL, 0 -> automax (fract of the
# integrated `rate` phase: no per-frame Python beyond the existing rate phases). Off for presets and the user's stack;
# a module ADDED from the Stack page starts in ping-pong (NEW_MODULE_VALUES). progress stays the manual control (user:
# "i like the progress bar too - its so i can animate it if i want to"): touching it by hand, or giving it an
# expression / export / a drive, switches auto Off (px_rt.auto_guard, a Parameter Execute event, never per frame);
# auto_vals is the uniform-path backstop for a drive.
AUTO_MODES = [('off', 'Off (progress knob / drive)'), ('loop', 'Loop (0 -> 1, repeat)'),
              ('pingpong', 'Ping-pong (0 -> 1 -> 0, eased)')]
AUTO_TYPES = ('explode', 'dissolve_noise', 'dissolve_gradient')
NEW_MODULE_VALUES = dict((t, {'auto': 'pingpong', 'rate': 0.1}) for t in AUTO_TYPES)


def _auto():
    return [P('auto', 'menu', 'off', menu=AUTO_MODES, label='auto progress'),
            P('rate', 'float', 0.1, 0.0, 2.0, label='auto rate Hz (cycles/s)', rate=True),
            P('automax', 'float', 1.0, 0.0, 1.0, label='auto top (progress max)')]


def auto_vals(mtype, vals, drives):
    """A drive on `progress` wins over auto: auto off (vals copied only when changed)."""
    if mtype in AUTO_TYPES and any(d[0] == 'progress' for d in drives) and vals.get('auto', 'off') not in ('off', 0):
        vals = dict(vals)
        vals['auto'] = 'off'
    return vals


def rate_live(mtype, vals, p):
    """Does rate param p make this module change every frame? auto's `rate` only while auto is on."""
    if not p.get('rate'):
        return False
    if mtype in AUTO_TYPES and p['name'] == 'rate' and menu_index(AUTO_MODES, vals.get('auto', 'off')) == 0:
        return False
    try:
        return float(vals.get(p['name'], p['default']) or 0.0) != 0.0
    except (TypeError, ValueError):
        return False


def auto_progress(progress, auto, phase, top=1.0):
    """Python twin of the GLSL: effective progress (off: the knob; loop: fract; ping-pong: eased triangle), x top."""
    m = menu_index(AUTO_MODES, auto)
    if m == 0:
        return float(progress)
    f = float(phase) - math.floor(float(phase))
    if m == 1:
        return f * float(top)
    x = 1.0 - abs(2.0 * f - 1.0)
    return x * x * (3.0 - 2.0 * x) * float(top)


AUTO_GUARD_RE = re.compile(r'^M(\d+)(progress|drive)$')


def auto_guard_off(name, value, auto, constant=True, own=None):
    """Should this par event switch the module's auto progress Off? name = TD par name, value = its value, auto = the
    module's auto value, constant = the par is in constant mode, own = the last value PX itself wrote there (recall,
    morph, page sync: their late events are echoes, T-236). -> uid or None."""
    m = AUTO_GUARD_RE.match(str(name))
    if not m or menu_index(AUTO_MODES, auto) == 0:
        return None
    if m.group(2) == 'drive':
        return int(m.group(1)) if any(d[0] == 'progress' for d in parse_drives(value)[0]) else None
    if constant and own is not None:
        try:
            if abs(float(value) - float(own)) < 1e-9:
                return None
        except (TypeError, ValueError):
            pass
    return int(m.group(1))


def trig_which(which):
    """Trigautowhich -> trigger indices (all = 0..3)."""
    w = str(which or 'all')
    return [0, 1, 2, 3] if w == 'all' else ([int(w[4:]) - 1] if w[:4] == 'trig' and w[4:].isdigit() else [0])


def trig_auto(t, last, every, which):
    """Auto trigger: -> (fire indices, new last). every <= 0 = off; first fire at once when switched on."""
    every = float(every or 0.0)
    if every <= 0.0:
        return [], None
    if last is not None and t - last < every and t >= last:
        return [], last
    return trig_which(which), t


# ---- beat sync (28 Oct, phase A): audio drive sources from an AU_features COMP (Drive page Audiosrc) --------------
# The engine reads a handful of channels of <Audiosrc>/out_features once per frame, and only while something uses
# them (Beatsync on, an audio trigger source, or a drive word below). Beats / onsets are counted edges of AU's
# beat_count / onset_count (a counter never misses a one-frame tick); envelopes and the tempo phase are computed here.
AUDIO_SRCS = ('onset', 'beat', 'bass', 'mid', 'high', 'level', 'tempo')
AUDIO_NEED = ('onset', 'bass', 'mid', 'high', 'level')      # drive words that read Audiosrc (beat / tempo: Beatsync)
AUDIO_CHANS = ('beat_count', 'onset_count', 'bpm', 'live', 'bass', 'mid', 'high', 'band_level', 'loud')
TRIG_SOURCES = [('manual', 'Manual (pulses + Trigauto s)'), ('beat', 'Every beat'), ('onset', 'Every onset (audio)'),
                ('nbeats', 'Every N beats (Trigbeats)')]
AUDIO_DEFAULT = '/project1/lab/AU_features'


def audio_tick(st, ch, now, decay):
    """One frame of the audio clock. st = last state (plain dict), ch = {channel: value} from the audio source, or
    None (off / missing / parked: every source reads 0). now = wall seconds, decay = Beatdecay (1/s).
    -> (src {onset beat bass mid high level tempo}, state, events {'beat', 'onset'}, bpm (0 = none), beat index)."""
    st = dict(st or {})
    ev = {'beat': False, 'onset': False}
    src = dict((k, 0.0) for k in AUDIO_SRCS)
    if ch is None:
        return src, {}, ev, 0.0, None
    g = lambda k: float(ch.get(k, 0.0) or 0.0)
    live = g('live') >= 0.5
    for cnt, tk, nk, e in (('beat_count', 'bt', 'bn', 'beat'), ('onset_count', 'ot', 'on', 'onset')):
        n = int(round(g(cnt)))
        if st.get(nk) is not None and n > st[nk]:
            ev[e] = True
            st[tk] = now
        st[nk] = n                                    # first read / a counter reset (n < last): resync, no event
    bpm = g('bpm') if live and g('bpm') > 0 else 0.0
    if live and st.get('bt') is not None:
        age = max(now - st['bt'], 0.0)
        src['beat'] = math.exp(-max(decay, 0.0) * age)
        if bpm > 0:
            x = age * bpm / 60.0
            src['tempo'] = x - math.floor(x)
    if live and st.get('ot') is not None:
        src['onset'] = math.exp(-max(decay, 0.0) * max(now - st['ot'], 0.0))
    for k in ('bass', 'mid', 'high'):
        src[k] = g(k)
    src['level'] = g('loud') if live else g('band_level')
    return src, st, ev, bpm, st.get('bn')


def clock_beat(t, bpm, last):
    """Internal clock beat edge (Beatsync off): -> (fired, beat index). last = the previous index (None = first)."""
    k = int(math.floor(float(t) * max(float(bpm), 1e-3) / 60.0))
    return (last is not None and k > last), k


def trig_fire(source, every, beat_ev, beat_idx, onset_ev):
    """Does the trigger source fire this frame? manual never (pulses / Trigauto do); nbeats on beats whose index is a
    multiple of every (>= 1)."""
    if source == 'beat':
        return bool(beat_ev)
    if source == 'onset':
        return bool(onset_ev)
    if source == 'nbeats':
        return bool(beat_ev) and beat_idx is not None and int(beat_idx) % max(int(every or 1), 1) == 0
    return False


def drives_need_audio(drives):
    """Any drive word that reads the audio source (AUDIO_NEED)?"""
    return any(d[2] in AUDIO_NEED for d in drives)


# ---- setlist (28 Oct, phase A): presets as scenes in show order -----------------------------------------------------
# The setlist only REFERENCES preset names (table px_setlist, one column `name`; empty = the presets table order).
# A name that is not a preset reads "(missing)" and is skipped by Next / Prev; Go refuses it. Nothing here changes a
# preset. Transition = Morph (load-safe since T-237) over Transition seconds (beats with Beatsync on); 0 = cut (Recall).
TRANSCURVES = [('linear', 'Linear'), ('ease', 'Ease in / out')]
SETLIST_PARS = ('Setlist', 'Setlistfill', 'Cue', 'Go', 'Next', 'Prev', 'Cueindex', 'Transition', 'Transcurve',
                'Current')
# phase C (28 Oct): perf + routing pars are the rig's, not a look's (a recall never turns auto quality or the external
# camera on / off)
PHASEC_NOSNAP = ('Autoquality', 'Govop', 'Aqfps', 'Aqframes', 'Aqheadroom', 'Aqstate', 'Sortstill', 'Lod', 'Loddist', 'Lodkeep',
                 'Camsource', 'Camcomp')
NOSNAP = ('Status', 'Presetname', 'Newname', 'Audiosrc', 'Beatsync', 'Addafter', 'Presetsource') + SETLIST_PARS + PHASEC_NOSNAP   # never stored in a preset

# ---- Presetsource (28 Oct, user: "changing a preset also changes the pointcloud or splat file that i have imported")
# With Presetsource Off (the default) a recalled / morphed / setlist look keeps the user's source: every Source-page
# par (and its tuplet parts), the pars that reload the scene (px_rt.LOAD_PARS) and the external camera routing are
# left out of the values it applies. Store still writes them, so Presetsource On is the old behaviour.
SOURCE_EXTRA = ('Afile', 'Bfile', 'Amode', 'Bmode', 'Aup', 'Bup', 'Quality', 'Count', 'Match', 'Actormode', 'Actorfile',
                'Actorseq', 'Actorcount', 'Actorup', 'Pool', 'Clip', 'Opacitymin', 'Camsource', 'Camcomp')
SOURCE_KEPT_NOTE = 'source kept (Presetsource off)'


def _spec_names(name, style):
    if style == 'XYZ':
        return [name + 'x', name + 'y', name + 'z']
    if style == 'RGB':
        return [name + 'r', name + 'g', name + 'b']
    if style == 'XY':
        return [name + 'x', name + 'y']
    return [name]


def source_par_names(page_names=()):
    """Par names a look leaves alone while Presetsource is off: the Source page of CORE_PAGES (tuplets per part),
    SOURCE_EXTRA, and page_names (the live COMP's own Source-page pars, so a newer par is covered too)."""
    out = set(SOURCE_EXTRA)
    for pg, pars in CORE_PAGES:
        if pg == 'Source':
            for spec in pars:
                out.update(_spec_names(spec[0], spec[1]))
    out.update(page_names or ())
    return out


def keep_source(flag):
    """Presetsource value -> True when looks must keep the source. A PX without the par (None) keeps it too."""
    return flag is None or not bool(flag)


def strip_source(values, names):
    """-> (values without the source pars, sorted names that were left out)."""
    names = set(names)
    gone = sorted(k for k in values if k in names)
    return dict((k, v) for k, v in values.items() if k not in names), gone


def setlist_names(rows, presets):
    """Table names (blank rows skipped, header row excluded by the caller) or, when empty, the presets order."""
    names = [str(r).strip() for r in rows if str(r).strip()]
    return names if names else list(presets)


def setlist_labels(names, presets):
    have = set(presets)
    return ['%d %s%s' % (k + 1, n, '' if n in have else ' (missing)') for k, n in enumerate(names)]


def setlist_missing(names, presets):
    have = set(presets)
    return [n for n in names if n not in have]


def setlist_step(names, presets, pos, delta):
    """Next (+1) / Prev (-1) from pos (None = before the first / after the last), wrapping, skipping missing names.
    -> (new pos or None when nothing is playable, [skipped missing names])."""
    n = len(names)
    if n == 0:
        return None, []
    have = set(presets)
    p = (-1 if delta > 0 else 0) if pos is None else int(pos)
    skipped = []
    for _k in range(n):
        p = (p + (1 if delta > 0 else -1)) % n
        if names[p] in have:
            return p, skipped
        skipped.append(names[p])
    return None, skipped


def cue_index(names, cue):
    """Cue text -> setlist index: a name, '3 name' (a menu label), or a number (1-based). None when not found."""
    s = str(cue or '').strip()
    if not s:
        return None
    if s in names:
        return names.index(s)
    head, _sp, rest = s.partition(' ')
    if head.isdigit():
        k = int(head) - 1
        if 0 <= k < len(names) and (not rest or rest.replace(' (missing)', '') == names[k]):
            return k
    return None


def transition_seconds(trans, beatsync, bpm):
    """Transition par -> seconds (beats x 60 / bpm with Beatsync on and a bpm)."""
    x = max(float(trans or 0.0), 0.0)
    return x * 60.0 / float(bpm) if beatsync and bpm and float(bpm) > 0 else x


def trans_curve(name):
    """Transcurve -> a `curve` kind (ease = smooth in / out)."""
    return 'smooth' if str(name) == 'ease' else 'linear'


def current_text(names, pos):
    if pos is None or not (0 <= int(pos) < len(names)):
        return '-'
    return '%d/%d %s' % (int(pos) + 1, len(names), names[int(pos)])


def hand_moved(value, own, tol=1e-6):
    """During a morph: was this par moved by someone else (value differs from what the morph wrote last)? tol is
    relative (1e-6: a float32 round trip through a panel is not a hand)."""
    if own is None:
        return False
    try:
        a, b = float(value), float(own)
        return abs(a - b) > tol * max(1.0, abs(b))
    except (TypeError, ValueError):
        return value != own


def new_module_values(mtype, uid):
    """{TD par name: value} a module ADDED from the Stack page starts with (auto progress on), on top of defaults."""
    return dict((par_name(uid, k), v) for k, v in NEW_MODULE_VALUES.get(mtype, {}).items())


def _release():
    return [P('release', 'float', 0.5, 0.0, 20.0), P('curl', 'float', 1.0, 0.0, 10.0), P('up', 'float', 0.5, -10.0, 10.0)]


MODULES = {
    # ---- proximity (effector objects) ----
    'prox_push': {'name': 'Proximity push / pull', 'desc': 'points near an effector get pushed away or pulled in',
                  'cat': 'proximity', 'stages': ('update',), 'eff': True,
                  'params': _prox() + [P('strength', 'float', 0.5, -10.0, 10.0, label='strength (neg = pull)'),
                                       P('mode', 'menu', 'displace', menu=[('displace', 'Displace'), ('force', 'Force')]),
                                       P('dir', 'menu', 'outward', menu=[('outward', 'Outward (surface normal)'),
                                         ('centre', 'From centre'), ('axis', 'Effector axis'), ('tangent', 'Tangent (swirl)'),
                                         ('velocity', 'Effector velocity (stir; per point for point sets)')]),
                                       P('publish', 'menu', 'none', menu=PUBLISH, label='publish weight to')]},
    'prox_vortex': {'name': 'Proximity vortex', 'desc': 'points near an effector swirl around it',
                    'cat': 'proximity', 'stages': ('update',), 'eff': True,
                    'params': _prox() + [P('strength', 'float', 3.0, -30.0, 30.0), P('pull', 'float', 0.0, -5.0, 5.0),
                                         P('lift', 'float', 0.0, -10.0, 10.0),
                                         P('mode', 'menu', 'force', menu=[('force', 'Force (swirl flow)'), ('twist', 'Twist (angle)')])]},
    'prox_dissolve': {'name': 'Proximity dissolve', 'desc': 'points near an effector dissolve into drifting dust',
                      'cat': 'proximity', 'stages': ('update',), 'eff': True,
                      'params': _prox() + [P('threshold', 'float', 0.5, 0.0, 1.0), P('soft', 'float', 0.2, 0.0, 1.0),
                                           P('noisescale', 'float', 3.0, 0.01, 50.0), P('noisegain', 'float', 0.5, 0.0, 2.0),
                                           P('release', 'float', 1.0, 0.0, 20.0), P('curl', 'float', 1.0, 0.0, 10.0),
                                           P('curlscale', 'float', 1.5, 0.01, 20.0)]},
    'prox_burn': {'name': 'Proximity burn / ignite', 'desc': 'points near an effector heat up, glow and throw embers',
                  'cat': 'proximity', 'stages': ('update', 'colour'), 'eff': True,
                  'params': _prox() + [P('rise', 'float', 2.0, 0.0, 20.0, label='heat rise /s'),
                                       P('flamefreq', 'float', 3.0, 0.1, 30.0), P('flamespeed', 'float', 1.0, 0.0, 10.0),
                                       P('lift', 'float', 1.5, -10.0, 10.0), P('embers', 'float', 0.5, 0.0, 5.0),
                                       P('consume', 'float', 0.0, 0.0, 4.0, label='consume at heat (0 off)'),
                                       P('heatscale', 'float', 1.0, 0.0, 4.0), P('ramphue', 'float', 0.0, -0.5, 0.5),
                                       P('emission', 'float', 4.0, 0.0, 50.0),
                                       # pool embers (Source page Pool %): spawned points that fly beyond the scan
                                       P('source', 'menu', 'scan', menu=[('scan', 'Scan (burning points)'),
                                         ('volume', 'Effector volume'), ('surface', 'Effector surface')],
                                         label='ember source'),
                                       P('rate', 'float', 1.0, 0.0, 20.0, label='ember spawn /s (share of pool)'),
                                       P('cone', 'float', 25.0, 0.0, 180.0, label='ember cone deg'),
                                       P('speed', 'float', 1.0, 0.0, 20.0, label='ember speed'),
                                       P('lifespan', 'float', 2.0, 0.05, 20.0, label='ember life s'),
                                       P('keep', 'float', 0.3, 0.0, 1.0, label='ember keeps source colour'),
                                       P('firesrc', 'menu', 'fire', menu=[('fire', 'Fire ramp (built in, ramphue)'),
                                         ('palette', 'Shared palette (Palette page)')], label='fire colours')]},
    'prox_magnet': {'name': 'Proximity magnet to shape', 'desc': 'points near an effector snap onto its shape',
                    'cat': 'proximity', 'stages': ('update',), 'eff': True,
                    'params': _prox() + [P('pull', 'float', 0.8, 0.0, 1.0), P('shell', 'float', 0.0, -1.0, 1.0),
                                         P('jitter', 'float', 0.0, 0.0, 1.0)]},
    'prox_stretch': {'name': 'Proximity stretch / lattice', 'desc': 'points near an effector stretch into streaks, cells or slices',
                     'cat': 'proximity', 'stages': ('update', 'colour'), 'eff': True,
                     'params': _prox() + [P('stretch', 'float', 4.0, 0.0, 50.0), P('thin', 'float', 0.5, 0.0, 1.0),
                                          P('snap', 'float', 0.0, 0.0, 1.0, label='lattice snap'),
                                          P('cell', 'float', 0.05, 0.001, 2.0),
                                          P('tint', 'rgb', (1.0, 0.1, 0.05)), P('tintamt', 'float', 0.0, 0.0, 1.0),
                                          P('axis', 'menu', 'velocity', menu=STRETCH_AXES, label='stretch axis'),
                                          P('mode', 'menu', 'stretch', menu=[('stretch', 'Stretch (streaks)'),
                                            ('lattice', 'Lattice (snap to cells)'), ('slices', 'Slices (bands + gaps)')]),
                                          P('gap', 'float', 0.0, 0.0, 1.0, label='slice gap'),
                                          P('bandwidth', 'float', 0.1, 0.001, 5.0, label='slice band width')]},
    'prox_scale': {'name': 'Proximity size / alpha', 'desc': 'points near an effector grow, shrink or fade',
                   'cat': 'proximity', 'stages': ('colour',), 'eff': True,
                   'params': _prox() + [P('sizegain', 'float', 2.0, -1.0, 10.0), P('alphagain', 'float', 0.0, -1.0, 10.0),
                                        P('cull', 'float', 0.0, 0.0, 1.0, label='hide below w')]},
    'prox_colour': {'name': 'Proximity colour', 'desc': 'points near an effector change colour',
                    'cat': 'proximity', 'stages': ('colour',), 'eff': True,
                    'params': _prox() + [P('mode', 'menu', 'tint', menu=[('tint', 'Tint'), ('replace', 'Replace'),
                                           ('ramp', 'Ramp colour -> colour 2'), ('hue', 'Hue shift'), ('invert', 'Invert'),
                                           ('emissive', 'Emission only')]),
                                         P('colour', 'rgb', (1.0, 0.45, 0.1)), P('colour2', 'rgb', (0.1, 0.6, 1.0)),
                                         P('emission', 'float', 2.0, 0.0, 50.0), P('flicker', 'float', 0.0, 0.0, 1.0),
                                         P('hueshift', 'float', 0.3, -1.0, 1.0),
                                         P('cover', 'float', 0.0, 0.0, 1.0,
                                           label='cover (colour full early in the falloff: solid bands)'),
                                         # W1-B colour source of `colour` (solid = the RGB par, today's look)
                                         P('colsrc', 'menu', 'solid', menu=COLSRC_MODES, label='colour source'),
                                         P('palpos', 'float', 0.0, 0.0, 1.0, label='palette position'),
                                         P('palspread', 'float', 1.0, -4.0, 4.0, label='palette spread (x weight)'),
                                         P('palkeep', 'float', 0.0, 0.0, 1.0, label='keep point colour')]},
    # ---- motion fields ----
    'curl': {'name': 'Curl noise', 'desc': 'smooth swirling flow',
             'cat': 'motion', 'stages': ('update',), 'eff': False,
             'params': [P('strength', 'float', 1.0, 0.0, 20.0), P('scale', 'float', 1.0, 0.01, 20.0),
                        P('speed', 'float', 0.3, 0.0, 5.0, rate=True), P('octaves', 'int', 2, 1, 4),
                        P('mode', 'menu', 'force', menu=[('force', 'Force (flow)'), ('displace', 'Displace (rest field)')]),
                        P('distance', 'float', 0.2, 0.0, 5.0, label='displace distance')]},
    'wind': {'name': 'Wind / gravity', 'desc': 'gravity, wind and gusts, with an optional floor',
             'cat': 'motion', 'stages': ('update',), 'eff': False,
             'params': [P('gravity', 'xyz', (0.0, 0.0, 0.0), -20.0, 20.0), P('wind', 'xyz', (0.0, 0.0, 0.0), -20.0, 20.0),
                        P('gust', 'float', 0.0, 0.0, 2.0), P('gustfreq', 'float', 0.5, 0.0, 10.0),
                        P('buoyancy', 'float', 0.0, -10.0, 10.0, label='buoyancy x heat'), P('floor', 'toggle', 0),
                        P('floory', 'float', -1.0, -10.0, 10.0), P('bounce', 'float', 0.4, 0.0, 1.0)]},
    'attractor': {'name': 'Strange attractor', 'desc': 'points flow along a strange attractor (Lorenz, Aizawa ...)',
                  'cat': 'motion', 'stages': ('update',), 'eff': True,
                  'params': [P('type', 'menu', 'aizawa', menu=[('lorenz', 'Lorenz'), ('aizawa', 'Aizawa'), ('thomas', 'Thomas'),
                                                               ('halvorsen', 'Halvorsen'), ('dadras', 'Dadras'), ('chen', 'Chen')]),
                             P('strength', 'float', 2.0, 0.0, 20.0), P('scale', 'float', 0.5, 0.001, 5.0),
                             P('speed', 'float', 1.0, 0.0, 10.0), P('offset', 'xyz', (0.0, 0.0, 0.0), -50.0, 50.0),
                             P('custom', 'toggle', 0, label='custom constants'), P('a', 'float', 0.95, -50.0, 50.0),
                             P('b', 'float', 0.7, -50.0, 50.0), P('c', 'float', 0.6, -50.0, 50.0), P('d', 'float', 3.5, -50.0, 50.0),
                             P('limit', 'float', 50.0, 0.0, 500.0, label='speed limit (0 off)')]},
    'orbit': {'name': 'Orbit / spin', 'desc': 'points spin around an axis',
              'cat': 'motion', 'stages': ('update',), 'eff': True,
              'params': [P('axis', 'menu', 'y', menu=AXES), P('speed', 'float', 0.5, -10.0, 10.0, label='speed rad/s', rate=True),
                         P('falloff', 'float', 0.0, -2.0, 2.0, label='radius falloff'), P('minr', 'float', 0.05, 0.0, 2.0)]},
    'twist': {'name': 'Twist', 'desc': 'twists or bends the cloud along an axis',
              'cat': 'motion', 'stages': ('update',), 'eff': True,
              'params': [P('axis', 'menu', 'y', menu=AXES), P('twist', 'float', 1.0, -10.0, 10.0, label='rad per unit'),
                         P('wobble', 'float', 0.0, 0.0, 5.0), P('wobblespeed', 'float', 1.0, 0.0, 10.0, rate=True),
                         P('mode', 'menu', 'twist', menu=[('twist', 'Twist (about the axis)'),
                                                          ('bend', 'Bend (curve along the axis, curvature = twist)')])]},
    'explode': {'name': 'Explode / reassemble', 'desc': 'points fly out and back',
                'cat': 'motion', 'stages': ('update',), 'eff': True,
                'params': [P('progress', 'float', 0.0, 0.0, 1.0)] + _auto() + [P('distance', 'float', 3.0, 0.0, 50.0),
                           P('power', 'float', 1.0, 0.1, 8.0), P('random', 'float', 0.5, 0.0, 1.0),
                           P('swirl', 'float', 0.0, -10.0, 10.0),
                           P('mode', 'menu', 'radial', menu=[('radial', 'Radial'), ('axis', 'Along axis'), ('noise', 'Random dirs')]),
                           P('axis', 'menu', 'y', menu=AXES)]},
    'wave': {'name': 'Wave', 'desc': 'waves ripple through the cloud',
             'cat': 'motion', 'stages': ('update',), 'eff': True,
             'params': [P('type', 'menu', 'sine', menu=[('sine', 'Sine'), ('ripple', 'Ripple (from centre)'),
                                                         ('standing', 'Standing'), ('noise', 'Noise terrain')]),
                        P('amp', 'float', 0.1, -2.0, 2.0), P('freq', 'float', 3.0, 0.0, 50.0),
                        P('speed', 'float', 1.0, -20.0, 20.0, rate=True), P('dir', 'xyz', (1.0, 0.0, 0.0), -1.0, 1.0),
                        P('axis', 'menu', 'y', menu=AXES + [('radial', 'Radial')]), P('decay', 'float', 0.0, 0.0, 10.0)]},
    'jitter': {'name': 'Jitter / shiver', 'desc': 'a small random shiver per point',
               'cat': 'motion', 'stages': ('update',), 'eff': False,
               'params': [P('amp', 'float', 0.02, 0.0, 1.0), P('rate', 'float', 12.0, 0.0, 60.0),
                          P('mode', 'menu', 'stepped', menu=[('stepped', 'Stepped'), ('smooth', 'Smooth'), ('static', 'Static')])]},
    'glitch': {'name': 'Glitch blocks', 'desc': 'blocks of points jump and snap back',
               'cat': 'motion', 'stages': ('update',), 'eff': False,
               'params': [P('block', 'float', 0.2, 0.001, 5.0), P('prob', 'float', 0.15, 0.0, 1.0),
                          P('offset', 'float', 0.3, 0.0, 5.0), P('hold', 'float', 0.12, 0.01, 5.0),
                          P('quantize', 'float', 0.0, 0.0, 1.0), P('qcells', 'float', 4.0, 1.0, 64.0),
                          # SA18 packet glitch (wave 3): rigid packets + reassemble envelope
                          P('gmode', 'menu', 'blocks', menu=[('blocks', 'Blocks (offsets)'),
                            ('packet', 'Packets (rigid offset + rotation, splats rotate)')], label='glitch mode'),
                          P('rot', 'float', 30.0, 0.0, 180.0, label='packet rotation deg'),
                          P('envsrc', 'menu', 'constant', menu=[('constant', 'Constant'), ('beat', 'Beat (reassemble between beats)'),
                            ('trig1', 'Trigger 1'), ('trig2', 'Trigger 2'), ('trig3', 'Trigger 3'), ('trig4', 'Trigger 4')],
                            label='envelope (break on the hit, reassemble as it decays)')]},
    'audio_displace': {'name': 'Audio displace', 'desc': 'points move with the music (bass, mid, high, spectrum)',
                       'cat': 'motion', 'stages': ('update',), 'eff': True,
                       'params': [P('band', 'menu', 'low', menu=[('low', 'Low'), ('mid', 'Mid'), ('high', 'High'), ('level', 'Level'),
                                                                 ('spec_height', 'Spectrum by height'), ('spec_radius', 'Spectrum by radius'),
                                                                 ('spec_id', 'Spectrum by point')]),
                                  P('amp', 'float', 0.3, -5.0, 5.0),
                                  P('dir', 'menu', 'radial', menu=[('radial', 'Radial'), ('up', 'Up'), ('x', 'X'), ('z', 'Z'), ('curl', 'Curl')]),
                                  P('beatkick', 'float', 0.0, 0.0, 5.0)]},
    'shockwave': {'name': 'Shockwave ring', 'desc': 'a ring of force and colour expands on a trigger',
                  'cat': 'motion', 'stages': ('update', 'colour'), 'eff': True,
                  'params': [P('trigger', 'menu', 'trig1', menu=[('trig1', 'Trigger 1'), ('trig2', 'Trigger 2'), ('trig3', 'Trigger 3'),
                                                                   ('trig4', 'Trigger 4'), ('beat', 'Every beat')]),
                             P('speed', 'float', 4.0, 0.0, 50.0), P('width', 'float', 0.3, 0.001, 5.0),
                             P('amp', 'float', 0.3, -5.0, 5.0), P('decay', 'float', 1.5, 0.0, 20.0),
                             P('ringcol', 'rgb', (1.0, 0.8, 0.5)), P('colourmix', 'float', 0.5, 0.0, 1.0),
                             P('emission', 'float', 3.0, 0.0, 50.0)]},
    # ---- masks / dissolve / lifetime ----
    'mask_region': {'name': 'Mask: effector region', 'desc': 'marks the points inside an effector (for other modules)',
                    'cat': 'mask', 'stages': ('update',), 'eff': True,
                    'params': [p if p['name'] != 'radius' else P('radius', 'float', 0.1, 0.0, 10.0, label='soft edge')
                               for p in _prox()] + [P('out', 'menu', 'm0', menu=MASKOUT), P('op', 'menu', 'set', menu=MASKOPS)]},
    'mask_image': {'name': 'Mask: image / body (TOP)', 'desc': 'marks points from an image or body mask TOP',
                   'cat': 'mask', 'stages': ('update',), 'eff': True,
                   'params': [P('proj', 'menu', 'screen', menu=[('screen', 'Screen (output camera)'), ('planar_xy', 'Planar XY'),
                                                                 ('planar_xz', 'Planar XZ')]),
                              P('chan', 'menu', 'lum', menu=[('lum', 'Luminance'), ('alpha', 'Alpha'), ('red', 'Red')]),
                              P('threshold', 'float', 0.1, 0.0, 1.0), P('soft', 'float', 0.1, 0.0, 1.0),
                              P('size', 'float', 2.0, 0.01, 50.0, label='planar size'), P('mirror', 'toggle', 0),
                              P('out', 'menu', 'm0', menu=MASKOUT), P('op', 'menu', 'set', menu=MASKOPS)]},
    'mask_attr': {'name': 'Mask: attribute band', 'desc': 'marks points by height, distance, colour, speed ...',
                  'cat': 'mask', 'stages': ('update',), 'eff': True,
                  'params': [P('by', 'menu', 'height', menu=[('height', 'Height (rest y)'), ('x', 'Rest x'), ('z', 'Rest z'),
                                                               ('radius', 'Distance to centre'), ('depth', 'Camera distance'),
                                                               ('luma', 'Luminance'), ('seed', 'Random'), ('speed', 'Speed'),
                                                               ('age', 'Age'), ('splatsize', 'Splat size (SA15)'),
                                                               ('opacity', 'Splat / point opacity'),
                                                               ('flatness', 'Splat flatness (min / max scale)')]),
                             P('lo', 'float', 0.0, -10.0, 10.0), P('hi', 'float', 1.0, -10.0, 10.0),
                             P('soft', 'float', 0.1, 0.0, 5.0), P('out', 'menu', 'm0', menu=MASKOUT),
                             P('op', 'menu', 'set', menu=MASKOPS)]},
    'dissolve_noise': {'name': 'Dissolve: noise', 'desc': 'points vanish in noisy patches as progress rises',
                       'cat': 'dissolve', 'stages': ('update',), 'eff': False,
                       'params': [P('progress', 'float', 0.0, 0.0, 1.0)] + _auto() + [P('scale', 'float', 2.0, 0.01, 50.0),
                                  P('octaves', 'int', 3, 1, 6), P('soft', 'float', 0.1, 0.001, 1.0),
                                  P('bias', 'xyz', (0.0, 0.0, 0.0), -2.0, 2.0, label='direction bias')] + _release()},
    'dissolve_gradient': {'name': 'Dissolve: gradient', 'desc': 'points vanish front by front along a direction',
                          'cat': 'dissolve', 'stages': ('update',), 'eff': True,
                          'params': [P('axis', 'menu', 'y', menu=AXES + [('radial', 'Radial'), ('custom', 'Custom dir'),
                                       ('camera', 'From the camera (distance)'), ('spiral', 'Spiral (helix about y)')]),
                                     P('dirv', 'xyz', (0.0, 1.0, 0.0), -1.0, 1.0, label='custom dir'),
                                     P('progress', 'float', 0.0, 0.0, 1.0)] + _auto() + [P('range', 'float', 2.0, 0.01, 50.0),
                                     P('soft', 'float', 0.2, 0.001, 1.0), P('warp', 'float', 0.2, 0.0, 2.0),
                                     P('warpscale', 'float', 2.0, 0.01, 50.0)] + _release() + [
                                     P('pitch', 'float', 0.5, 0.01, 10.0, label='spiral pitch (units per turn)'),
                                     P('linger', 'float', 0.0, 0.0, 2.0, label='linger before release (front units)'),
                                     P('swirl', 'float', 0.0, -10.0, 10.0, label='release swirl about y')]},
    'dissolve_time': {'name': 'Dissolve: time', 'desc': 'points vanish and come back in a loop',
                      'cat': 'dissolve', 'stages': ('update',), 'eff': False,
                      'params': [P('rate', 'float', 0.2, 0.0, 10.0, label='cycles/s', rate=True),
                                 P('spread', 'float', 1.0, 0.0, 10.0), P('width', 'float', 0.3, 0.0, 1.0),
                                 P('soft', 'float', 0.05, 0.001, 1.0),
                                 P('order', 'menu', 'random', menu=[('random', 'Random'), ('height', 'Height'), ('radial', 'Radial')])]
                      + _release()},
    'lifetime': {'name': 'Lifetime / respawn / fade', 'desc': 'points fade out and respawn on a timer',
                 'cat': 'dissolve', 'stages': ('update', 'colour'), 'eff': False,
                 'params': [P('life', 'float', 4.0, 0.05, 60.0), P('lifevar', 'float', 0.5, 0.0, 1.0),
                            P('fadein', 'float', 0.2, 0.0, 10.0), P('fadeout', 'float', 0.5, 0.0, 10.0),
                            P('stagger', 'toggle', 1)]},
    'density': {'name': 'Density / LOD', 'desc': 'thins the cloud, everywhere or by camera distance',
                'cat': 'dissolve', 'stages': ('colour',), 'eff': False,
                'params': [P('density', 'float', 1.0, 0.0, 1.0), P('bydist', 'toggle', 0, label='by camera distance'),
                           P('near', 'float', 2.0, 0.0, 100.0), P('far', 'float', 30.0, 0.0, 500.0),
                           P('minlod', 'float', 0.1, 0.0, 1.0)]},
    # ---- colour / material ----
    'colour_ramp': {'name': 'Colour ramp by attribute', 'desc': 'colours points by height, speed, heat ...',
                    'cat': 'colour', 'stages': ('colour',), 'eff': False,
                    'params': [P('attr', 'menu', 'height', menu=[('height', 'Height'), ('depth', 'Camera distance'), ('speed', 'Speed'),
                                                                   ('age', 'Age'), ('heat', 'Heat'), ('noise', 'Noise'), ('m0', 'Mask 0'),
                                                                   ('m1', 'Mask 1'), ('m2', 'Mask 2'), ('dissolve', 'Dissolve'),
                                                                   ('radius', 'Distance to centre'), ('seed', 'Random'), ('x', 'X'),
                                                                   ('z', 'Z'), ('lifefrac', 'Life fraction'),
                                                                   ('luma', 'Luminance (colour so far)'),
                                                                   ('splatsize', 'Splat size (SA15)'), ('opacity', 'Splat / point opacity'),
                                                                   ('flatness', 'Splat flatness (min / max scale)')]),
                               P('lo', 'float', -1.0, -20.0, 20.0), P('hi', 'float', 1.0, -20.0, 20.0),
                               P('col0', 'rgb', (0.05, 0.25, 0.30)), P('col1', 'rgb', (0.1, 0.55, 0.6)),
                               P('col2', 'rgb', (1.0, 0.55, 0.2)), P('col3', 'rgb', (1.0, 0.95, 0.8)),
                               P('blend', 'menu', 'replace', menu=[('replace', 'Replace'), ('multiply', 'Multiply'), ('add', 'Add'),
                                                                   ('screen', 'Screen'), ('emissive', 'Emission only')]),
                               P('noisescale', 'float', 2.0, 0.01, 50.0), P('emission', 'float', 0.0, 0.0, 20.0),
                               P('ramp', 'menu', 'stops', menu=[('stops', 'col0..col3'), ('palette', 'Shared palette (Palette page)')],
                                 label='ramp colours')]},
    # ---- strands / blades (wave 4, K22): every point drawn as a blade along up + a swaying curl-noise wind
    'strands': {'name': 'Strands / blades (grass, hair)', 'desc': 'every point grows a swaying blade (grass, hair)',
                'cat': 'motion', 'stages': ('colour',), 'eff': False,
                'params': [P('length', 'float', 6.0, 0.0, 60.0, label='blade length (point radii)'),
                           P('lengthvar', 'float', 0.6, 0.0, 1.0, label='length variation'),
                           P('thin', 'float', 0.85, 0.0, 1.0),
                           P('up', 'xyz', (0.0, 1.0, 0.0), -1.0, 1.0, label='blade direction'),
                           P('sway', 'float', 0.5, 0.0, 4.0, label='wind sway'),
                           P('swayscale', 'float', 1.2, 0.01, 50.0, label='wind scale'),
                           P('swayspeed', 'float', 0.4, 0.0, 10.0, label='wind speed'),
                           P('bylum', 'float', 0.0, 0.0, 1.0, label='length by source brightness (K27 pillars)')]},
    'colour_adjust': {'name': 'Colour adjust', 'desc': 'exposure, saturation, hue and tint of the points',
                      'cat': 'colour', 'stages': ('colour',), 'eff': False,
                      'params': [P('exposure', 'float', 0.0, -8.0, 8.0), P('saturation', 'float', 1.0, 0.0, 3.0),
                                 P('contrast', 'float', 1.0, 0.0, 3.0), P('hue', 'float', 0.0, -1.0, 1.0),
                                 P('gamma', 'float', 1.0, 0.1, 4.0), P('tint', 'rgb', (1.0, 1.0, 1.0)),
                                 P('tintamt', 'float', 0.0, 0.0, 1.0), P('alphamul', 'float', 1.0, 0.0, 4.0),
                                 P('emission', 'float', 0.0, 0.0, 20.0)]},
    # ---- heat spread (wave 3, SA21): fire creeps to neighbouring points through the shared voxel grid
    'heat_spread': {'name': 'Heat spread (shared grid)', 'desc': 'fire creeps from hot points to their neighbours',
                    'cat': 'proximity', 'stages': ('update',), 'eff': False,
                    'grid': True,
                    'params': [P('rate', 'float', 2.0, 0.0, 20.0, label='heat /s near hot points'),
                               P('radius', 'float', 0.15, 0.001, 2.0, label='spread radius'),
                               P('falloff', 'float', 1.0, 0.1, 8.0, label='falloff exp')]},
    # ---- light (wave 2, RUBENFRO L1 / L2): relight points + splats by the light effectors of /project1/effectors
    # (kind light, W1-A). `effectors` = a selection of the shared list (all / #tag / light names), default all.
    'light': {'name': 'Light (light effectors)', 'desc': 'lights the points with the light effectors',
              'cat': 'colour', 'stages': ('colour',), 'eff': True,
              'effdefault': 'all', 'shared_only': True,
              'params': [P('relight', 'float', 1.0, 0.0, 1.0, label='relight (0 = baked colour)'),
                         P('ambient', 'float', 0.15, 0.0, 2.0),
                         P('gain', 'float', 1.0, 0.0, 10.0, label='light gain'),
                         P('add', 'float', 0.0, 0.0, 5.0, label='add light (glow onto points)'),
                         P('emit', 'float', 0.0, 0.0, 20.0, label='lit parts emit (HDR, bloom)'),
                         P('model', 'menu', 'halflambert', menu=LIGHT_MODELS),
                         P('wrap', 'float', 0.5, 0.0, 1.0),
                         P('spec', 'float', 0.0, 0.0, 4.0, label='specular (Blinn)'),
                         P('rough', 'float', 0.5, 0.02, 1.0, label='roughness'),
                         P('normal', 'menu', 'auto', menu=LIGHT_NORMALS),
                         P('colsrc', 'menu', 'source', menu=COLSRC_MODES, label='light colour'),
                         P('palpos', 'float', 0.0, 0.0, 1.0, label='palette position'),
                         P('palspread', 'float', 1.0, -4.0, 4.0, label='palette spread (x light index)'),
                         P('palkeep', 'float', 0.0, 0.0, 1.0, label='keep light colour'),
                         P('tint', 'rgb', (1.0, 1.0, 1.0), label='solid colour'),
                         # SA5 bounce (wave 3): hot / emissive points light their surroundings (shared grid field)
                         P('bounce', 'float', 0.0, 0.0, 10.0, label='bounce from hot points (grid)'),
                         P('bouncecol', 'rgb', (1.0, 0.45, 0.15), label='bounce colour'),
                         P('bounceradius', 'float', 0.5, 0.01, 5.0, label='bounce radius')]},
    'velocity_streak': {'name': 'Velocity streak / motion blur', 'desc': 'fast points smear into motion streaks',
                        'cat': 'colour', 'stages': ('colour',), 'eff': False,
                        'params': [P('gain', 'float', 0.2, 0.0, 10.0), P('maxlen', 'float', 20.0, 0.0, 200.0),
                                   P('colourspeed', 'float', 0.0, 0.0, 5.0),
                                   P('source', 'menu', 'force', menu=[('force', 'Force motion (v1)'),
                                     ('camera', 'Camera motion (K25 blur)'), ('both', 'Both')],
                                     label='velocity source')]},
}

# header params every instance has: row 0 of its uM block = (amount, effector mask, mask input, invert), row 1 =
# (chunk, 0, 0, 0). chunk > 0: the module runs at the centre of the point's rest cell (size chunk) with the cell's id
# and seed, and the point moves by the cell's displacement, so points move in groups (tiles / slabs, VN4 / KANDA).
HEADER = [P('amount', 'float', 1.0, 0.0, 4.0), P('maskin', 'menu', 'none', menu=MASKSEL, label='mask input'),
          P('invert', 'toggle', 0, label='invert mask'),
          P('chunk', 'float', 0.0, 0.0, 2.0, label='chunk cell (0 = per point)')]
HEADER_STR = ['effectors', 'drive']     # string pars: effector names (space separated), drive spec

PAR_RE = re.compile(r'^[a-z][a-z0-9]*$')
TOKEN_RE = re.compile(r'\$([a-z][a-z0-9]*)')
SECTION_RE = re.compile(r'^//@module[ \t]+([a-z0-9_]+)[ \t]+(update|colour)[ \t]*$', re.M)


def module_types():
    return list(MODULES.keys())


def param(mtype, pname):
    for p in MODULES[mtype]['params']:
        if p['name'] == pname:
            return p
    return None


# ----------------------------------------------------------------------------------------------- snippets

def parse_snippets(text):
    """px_modules.glsl -> {(type, stage): code}. Sections run to the next marker or EOF."""
    out = {}
    ms = list(SECTION_RE.finditer(text))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        key = (m.group(1), m.group(2))
        if key in out:
            raise ValueError('duplicate snippet section %s %s' % key)
        out[key] = text[m.end():end].strip('\n') + '\n'
    return out


def check_snippets(snips, modules=None):
    """Problems list (empty = schema and GLSL agree)."""
    modules = modules or MODULES
    errs = []
    for t, m in modules.items():
        valid = set()
        for p in m['params']:
            valid.add(p['name'])
            if p.get('rate'):
                valid.add(p['name'] + 'ph')
            if not PAR_RE.match(p['name']):
                errs.append('%s: bad param name %r' % (t, p['name']))
        for st in STAGES:
            code = snips.get((t, st))
            if st in m['stages'] and code is None:
                errs.append('%s: no %s snippet' % (t, st))
            if st not in m['stages'] and code is not None:
                errs.append('%s: %s snippet but stage not declared' % (t, st))
            if code:
                for tok in TOKEN_RE.findall(code):
                    if tok not in valid:
                        errs.append('%s %s: unknown token $%s' % (t, st, tok))
    for (t, st) in snips:
        if t not in modules:
            errs.append('snippet for unknown module %s' % t)
    return errs


# ----------------------------------------------------------------------------------------------- stack

def new_instance(mtype, uid, enabled=True, label=''):
    if mtype not in MODULES:
        raise ValueError('unknown module type %r' % mtype)
    return {'uid': int(uid), 'type': mtype, 'enabled': bool(enabled), 'label': label or MODULES[mtype]['name']}


def next_uid(stack):
    return max([i['uid'] for i in stack] + [0]) + 1


def add_module(stack, mtype, at=None, label=''):
    """-> (new stack, uid). at = index (None = end)."""
    s = list(stack)
    inst = new_instance(mtype, next_uid(s), True, label)
    s.insert(len(s) if at is None else max(0, min(int(at), len(s))), inst)
    return s, inst['uid']


def find(stack, uid):
    for k, i in enumerate(stack):
        if i['uid'] == int(uid):
            return k
    return -1


def remove_module(stack, uid):
    return [i for i in stack if i['uid'] != int(uid)]


def move_module(stack, uid, delta):
    s = list(stack)
    k = find(s, uid)
    if k < 0:
        return s
    j = max(0, min(len(s) - 1, k + int(delta)))
    s.insert(j, s.pop(k))
    return s


def duplicate_module(stack, uid):
    """-> (new stack, new uid): a copy right after the original (values copied by copy_values)."""
    s = list(stack)
    k = find(s, uid)
    if k < 0:
        return s, None
    src = s[k]
    inst = new_instance(src['type'], next_uid(s), src['enabled'], src['label'] + ' copy')
    s.insert(k + 1, inst)
    return s, inst['uid']


def set_enabled(stack, uid, on):
    return [dict(i, enabled=bool(on)) if i['uid'] == int(uid) else i for i in stack]


STACK_COLS = ['uid', 'type', 'enabled', 'label']


def stack_rows(stack):
    return [STACK_COLS] + [[str(i['uid']), i['type'], '1' if i['enabled'] else '0', i['label']] for i in stack]


def stack_from_rows(rows):
    """Table rows (header first) -> stack; unknown types and bad uids are skipped (reported by the runtime)."""
    out, seen = [], set()
    if not rows:
        return out
    head = [str(c).strip().lower() for c in rows[0]]
    col = dict((n, head.index(n)) for n in STACK_COLS if n in head)
    for r in rows[1:]:
        try:
            uid = int(float(r[col['uid']]))
        except (ValueError, KeyError, IndexError):
            continue
        t = str(r[col['type']]).strip() if 'type' in col else ''
        if t not in MODULES or uid in seen or uid < 1:
            continue
        seen.add(uid)
        en = str(r[col['enabled']]).strip().lower() not in ('0', 'false', 'off', '') if 'enabled' in col else True
        lab = str(r[col['label']]) if 'label' in col and col['label'] < len(r) else ''
        out.append(new_instance(t, uid, en, lab))
    return out


# ----------------------------------------------------------------------------------------------- par names / pages

def par_name(uid, pname):
    """TD custom par name of an instance param: 'M3strength' (capital first, lower alnum after: TD's rule)."""
    return 'M%d%s' % (int(uid), pname)


def page_name(inst):
    return 'M%d_%s' % (inst['uid'], inst['type'])


_STYLE = {'float': 'Float', 'int': 'Int', 'toggle': 'Toggle', 'menu': 'Menu', 'xyz': 'XYZ', 'rgb': 'RGB'}


def _spec(name, p):
    o = {'label': p['label'], 'min': p['lo'], 'max': p['hi']}
    d = p['default']
    if p['kind'] == 'menu':
        o['names'], o['labels'] = names(p['menu']), labels(p['menu'])
    if p['kind'] == 'toggle':
        d = bool(d)
    return (name, _STYLE[p['kind']], d, o)


def eff_default(mtype):
    m = MODULES[mtype]
    return m.get('effdefault', 'E1') if m['eff'] else ''


# Render resolution menu (user, 28 Oct: "an option to change the render resolution and the hierarchy should follow
# it"): picking an item sets Resx / Resy; every screen-space TOP follows Resx / Resy (or a fixed divisor of them).
# 'custom' leaves Resx / Resy as typed; typing a size no item has switches the menu to custom. Max 3840: Metal's
# texture limit is 16384 (T-231).
RESOLUTIONS = [('1080x1920', '1080 x 1920 (vertical HD, default)'), ('720x1280', '720 x 1280 (vertical)'),
               ('540x960', '540 x 960 (vertical, quarter)'), ('1920x1080', '1920 x 1080 (landscape HD)'),
               ('1280x720', '1280 x 720 (landscape)'), ('2160x3840', '2160 x 3840 (vertical 4K)'),
               ('3840x2160', '3840 x 2160 (landscape 4K)'), ('custom', 'Custom (Resx / Resy)')]


def res_size(name):
    """'1080x1920' -> (1080, 1920); 'custom' / unknown -> None."""
    try:
        w, h = str(name).lower().split('x')
        return int(w), int(h)
    except ValueError:
        return None


def res_name(w, h):
    """The Resolution item of a size, else 'custom'."""
    k = '%dx%d' % (int(w), int(h))
    return k if k in names(RESOLUTIONS) else 'custom'


MENU_SRC = "me.op('px_rt').module.menu(me, %r)"   # dropdowns (T-233): px_rt.menu builds the items on each read


def menu_source(name):
    """menuSource of a PX name field (spec option 'menu': True): the items come from px_rt.menu(comp, name)."""
    return MENU_SRC % str(name)


def menu_specs(specs):
    """Names of the specs that are live dropdowns ('menu': True)."""
    return [s[0] for s in specs if len(s) > 3 and (s[3] or {}).get('menu')]


def sel_label(inst, solo=None):
    """Sel menu label of a stack instance: '4 Dissolve: noise (off)'; the soloed one reads '(solo)' (phase B)."""
    lab = inst.get('label') or MODULES.get(inst.get('type'), {}).get('name', inst.get('type', ''))
    if solo is not None and int(inst['uid']) == int(solo):
        tail = ' (solo)'
    else:
        tail = '' if inst.get('enabled', True) else ' (off)'
    return '%d %s%s' % (int(inst['uid']), lab, tail)


# ---- phase B (28 Oct): module browser, solo, size limits, preset checks, one PX per name in the shared list ---------
# Module browser: Addtype is a dropdown of every module, grouped by category; item NAME = the module type (what Add
# reads), label = 'Motion > Explode / reassemble - points fly out and back' (U+203A / U+2014 in the label text; this
# source stays ASCII).
CATEGORIES = [('proximity', 'Proximity'), ('motion', 'Motion'), ('dissolve', 'Dissolve'), ('mask', 'Mask'),
              ('colour', 'Colour')]
SEP_CAT = ' \u203a '
SEP_DESC = ' \u2014 '


def module_label(mtype):
    m = MODULES[mtype]
    cat = dict(CATEGORIES).get(m.get('cat'), str(m.get('cat', '')).capitalize())
    return cat + SEP_CAT + m['name'] + (SEP_DESC + m['desc'] if m.get('desc') else '')


def module_browser():
    """-> (names, labels) of the Addtype dropdown: category order, then MODULES order inside a category."""
    order = [k for k, _l in CATEGORIES]
    types = sorted(MODULES, key=lambda t: (order.index(MODULES[t]['cat']) if MODULES[t]['cat'] in order else 99,
                                           list(MODULES).index(t)))
    return types, [module_label(t) for t in types]


def addtype_of(text):
    """Addtype text -> module type or None: the type name, or a label picked / pasted whole ('Motion > Explode ...')."""
    s = str(text or '').strip()
    if s in MODULES:
        return s
    for t in MODULES:
        if s and (s == module_label(t) or s == MODULES[t]['name']):
            return t
    return None


def add_index(stack, sel, after):
    """Where Add puts a new module: after the selected one (Addafter on and Sel in the stack), else the end (None)."""
    if not after:
        return None
    k = find(stack, sel) if sel is not None else -1
    return None if k < 0 else k + 1


# Solo (Stack page, acting on Sel): only the selected module runs; Unsolo puts back the enabled set saved at the first
# Solo, exactly. The saved set lives in the COMP's storage (plain dict, T-67), never in a preset: Store writes the
# saved (real) set, and a recall / morph / setlist scene ends solo (the new look has its own set).
def solo_stack(stack, uid, saved=None):
    """-> (stack with only uid enabled, saved enabled set {uid: bool}). Solo on another module while soloed keeps the
    first saved set. uid not in the stack -> (stack unchanged, saved)."""
    if find(stack, uid) < 0:
        return list(stack), saved
    if saved is None:
        saved = dict((str(i['uid']), bool(i['enabled'])) for i in stack)
    return [dict(i, enabled=(i['uid'] == int(uid))) for i in stack], saved


def unsolo_stack(stack, saved):
    """Saved enabled flags back on the modules still in the stack; modules added while soloed keep their state."""
    saved = saved or {}
    return [dict(i, enabled=bool(saved[str(i['uid'])])) if str(i['uid']) in saved else dict(i) for i in stack]


def real_stack(stack, saved):
    """The stack as the user set it (the saved set while soloed): what Store writes."""
    return unsolo_stack(stack, saved) if saved else [dict(i) for i in stack]


# Hard size limits (T-231: Metal aborts on a texture over 16384 a side). Every texture PX derives stays <= TEX_MAX a
# side: the widest point texture is the state (STATE_TEXELS x side), so Count is clamped to (TEX_MAX // 5)^2 points;
# Resx / Resy scale down together (aspect kept); cube faces (Projface, Geoenvres) <= CUBE_MAX; PX_lines' segment
# texture (4 x 256 wide, Maxseg / 256 tall) <= TEX_MAX rows. The user's par value is kept; the effective one is used and
# Status says so. Raise TEX_MAX to 16384 (Metal's hard limit) only with margin checked on the target Mac.
TEX_MAX = 8192
CUBE_MAX = 4096
COUNT_MAX = (TEX_MAX // STATE_TEXELS) ** 2          # 1638^2 = 2 683 044 points (state 8190 x 1638)
LINES_SEG_W = 256                                  # px_lines_logic.SEG_W (segments per row of its segment texture)
LINES_SEG_MAX = TEX_MAX * LINES_SEG_W


def clamp_count(n):
    return max(1, min(int(n), COUNT_MAX))


def eff_res(w, h):
    """Render size actually used for Resx x Resy: both scaled down together so the larger side is <= TEX_MAX."""
    w, h = max(1, int(w)), max(1, int(h))
    k = min(1.0, float(TEX_MAX) / max(w, h))
    return max(1, int(w * k)), max(1, int(h * k))


def _short(n):
    n = int(n)
    if n >= 1000000:
        return '%.3gM' % (n / 1e6)
    if n >= 10000:
        return '%.3gk' % (n / 1e3)
    return str(n)


def size_notes(raw, maxseg=None):
    """Status text for every PX size par past its limit: 'Count 80M -> clamped to 2.68M (8192 px state texture)'.
    [] when everything is inside the limits."""
    out = []
    q = raw.get('Quality', 'std')
    n = next((x for k, _l, x in QUALITY if k == q and x), None)
    if n is None:
        n = int(raw.get('Count', 131072))
    if n > COUNT_MAX:
        out.append('%s %s -> clamped to %s (%d px state texture)' % ('Count' if q == 'custom' else 'Quality ' + q,
                                                                     _short(n), _short(COUNT_MAX), TEX_MAX))
    w, h = int(raw.get('Resx', 1080)), int(raw.get('Resy', 1920))
    ew, eh = eff_res(w, h)
    if (ew, eh) != (max(1, w), max(1, h)):
        out.append('Res %dx%d -> %dx%d (%d px max)' % (w, h, ew, eh, TEX_MAX))
    for k in ('Projface', 'Geoenvres'):
        v = raw.get(k)
        if v is not None and int(v) > CUBE_MAX:
            out.append('%s %d -> %d (cube faces <= %d)' % (k, int(v), CUBE_MAX, CUBE_MAX))
    if maxseg is not None and int(maxseg) > LINES_SEG_MAX:
        out.append('Lines Maxseg %s -> %s' % (_short(maxseg), _short(LINES_SEG_MAX)))
    return out


# Expression clamps (the user's par stays as typed; the TOPs read the effective size). `parent().par.X` (or
# `parent().par.X.eval()`) inside PX's own ops becomes the clamped form, spelled with `me.parent()` so a second run finds
# nothing to change (idempotent). Rules 'px' apply to ops whose parent is PX, 'lines' to ops inside PX_lines.
_RE_TOK = re.compile(r'(?<![\w.])parent\(\)\.par\.(Resx|Resy|Projface|Geoenvres|Maxseg)(?!\w)(\.eval\(\))?')
_RX = ("int(me.parent().par.Res{a}.eval() * min(1.0, %d.0 / max(1, me.parent().par.Resx.eval(), "
       "me.parent().par.Resy.eval())))" % TEX_MAX)
CLAMP_FORMS = {
    'px': {'Resx': _RX.format(a='x'), 'Resy': _RX.format(a='y'),
           'Projface': 'min(%d, int(me.parent().par.Projface.eval()))' % CUBE_MAX,
           'Geoenvres': 'min(%d, int(me.parent().par.Geoenvres.eval()))' % CUBE_MAX},
    'lines': {'Maxseg': 'min(%d, int(me.parent().par.Maxseg.eval()))' % LINES_SEG_MAX},
}


def clamp_expr(expr, rules='px'):
    """-> the expression with PX's size pars read through their clamps (unchanged when nothing applies)."""
    forms = CLAMP_FORMS[rules]

    def rep(m):
        f = forms.get(m.group(1))
        return '(%s)' % f if f else m.group(0)
    return _RE_TOK.sub(rep, str(expr))


# Preset checks on recall (phase B): never fail silently, never raise. The runtime collects what it could not apply;
# these turn it into one Status line + px_notes rows.
FILE_PARS = (('Afile', 'Amode', ('file',)), ('Bfile', 'Bmode', ('file',)), ('Actorfile', 'Actormode', ('file',)),
             ('Actorseq', 'Actormode', ('file',)), ('Imagefile', None, None), ('Palfile', 'Palsource', ('file',)))


def preset_unknown_types(d):
    """Module types in a stored preset's stack that this PX does not have (preset_loads drops them)."""
    return [str(i.get('type')) for i in (d.get('stack') or []) if isinstance(i, dict) and i.get('type') not in MODULES]


def preset_files(values, exists):
    """File / folder pars of a look that are in use and do not exist (exists = os.path.exists)."""
    out = []
    for k, mode_par, modes in FILE_PARS:
        v = str(values.get(k, '') or '').strip()
        if not v:
            continue
        if mode_par is not None and str(values.get(mode_par, '')) not in modes:
            continue
        if not exists(v):
            out.append(v)
    return out


def preset_eff_missing(stack, values, own, shared):
    """Effector names the look's modules select that are neither PX's own effectors nor rows of the shared list
    ('all', '*', '#tags' and empty selections are not names)."""
    have = set(own) | set(shared)
    miss = []
    for i in stack:
        if not MODULES.get(i['type'], {}).get('eff'):
            continue
        for w in str(values.get(par_name(i['uid'], 'effectors'), '') or '').replace(',', ' ').split():
            if w in ('all', '*') or w.startswith('#') or '*' in w or w in have or w in miss:
                continue
            miss.append(w)
    return miss


def _names(xs, k=4):
    xs = list(xs)
    return ', '.join(str(x) for x in xs[:k]) + (' ...' if len(xs) > k else '')


def preset_summary(name, notes, verb='recalled'):
    """'recalled X: 2 pars skipped (Foo, Bar); module type unknown: zap' (verb only when notes are empty)."""
    parts = []
    n = notes or {}
    if n.get('pars'):
        parts.append('%d par%s skipped (%s)' % (len(n['pars']), '' if len(n['pars']) == 1 else 's', _names(n['pars'])))
    if n.get('failed'):
        parts.append('%d not set (%s)' % (len(n['failed']), _names(n['failed'])))
    if n.get('types'):
        parts.append('module type unknown: %s' % _names(n['types']))
    if n.get('effectors'):
        parts.append('effector missing: %s' % _names(n['effectors']))
    if n.get('files'):
        parts.append('file missing: %s' % _names([str(f).replace('\\', '/').split('/')[-1] for f in n['files']], 2))
    if n.get('error'):
        parts.append('error: %s' % n['error'])
    if n.get('source_kept'):
        parts.append(SOURCE_KEPT_NOTE)
    return '%s %s%s' % (verb, name, (': ' + '; '.join(parts)) if parts else '')


# One PX per name in the shared list (/project1/effectors): each PX instance registers its hot points (heat spread /
# bounce) under its own row name, so two copies never fight over 'px_hot' (main 28 Oct: the only px_hot row pointed at
# PX_pointfx1's hot_pts, the original had none).
HOT_PREFIX = 'px_hot_'


def hot_key(comp_name, taken=()):
    """Shared-list row name for a PX COMP's hot points: 'px_hot_' + its name (lower case, [a-z0-9_]); a number is
    added when another PX already holds it."""
    base = HOT_PREFIX + (re.sub(r'[^a-z0-9_]', '_', str(comp_name).lower()) or 'px')
    nm, k = base, 2
    while nm in set(taken):
        nm = '%s_%d' % (base, k)
        k += 1
    return nm


def path_swap(text, old, new):
    """Rewrite references to `old` (an op path) and its children to `new` inside a par value; '/a/PX' never matches
    '/a/PX1'. -> (text, changed)."""
    s = str(text)
    pat = re.compile(re.escape(old) + r'(?=/|\s|$|[\'"),])')
    out = pat.sub(new.replace('\\', r'\\'), s)
    return out, out != s


def sel_uid(value, default=0):
    """Sel's value (StrMenu text since T-233, Int in older COMPs) -> uid int; default when it is not a number."""
    try:
        return int(float(str(value).split()[0]))
    except (ValueError, IndexError, TypeError):
        return default


def instance_par_specs(inst):
    """(name, style, default, opts) for the instance's page (zkit / particles builder format)."""
    u = inst['uid']
    specs = [_spec(par_name(u, p['name']), p) for p in HEADER]
    specs.append((par_name(u, 'effectors'), 'Str', eff_default(inst['type']),
                  {'label': 'effectors (own names; shared: names / #tag / all)', 'menu': True}))
    specs.append((par_name(u, 'drive'), 'Str', '', {'label': 'drive (param:src*gain+off)'}))
    specs += [_spec(par_name(u, p['name']), p) for p in MODULES[inst['type']]['params']]
    return specs


def flat_par_names(inst):
    """Every TD par name of an instance (xyz/rgb expanded)."""
    out = []
    for name, style, _d, _o in instance_par_specs(inst):
        if style == 'XYZ':
            out += [name + 'x', name + 'y', name + 'z']
        elif style == 'RGB':
            out += [name + 'r', name + 'g', name + 'b']
        else:
            out.append(name)
    return out


def instance_defaults(inst):
    """{param name (schema, not TD): value} incl. header + strings."""
    d = dict((p['name'], p['default']) for p in HEADER)
    d['effectors'] = eff_default(inst['type'])
    d['drive'] = ''
    for p in MODULES[inst['type']]['params']:
        d[p['name']] = p['default']
    return d


def instance_values(inst, flat):
    """flat = {TD par name: value} -> {schema name: value} (xyz/rgb -> tuples); missing -> defaults."""
    u = inst['uid']
    vals = instance_defaults(inst)
    for p in HEADER + MODULES[inst['type']]['params']:
        n = par_name(u, p['name'])
        if p['kind'] in ('xyz', 'rgb'):
            suf = 'xyz' if p['kind'] == 'xyz' else 'rgb'
            if all(n + s in flat for s in suf):
                vals[p['name']] = tuple(float(flat[n + s]) for s in suf)
        elif n in flat:
            vals[p['name']] = flat[n]
    for s in HEADER_STR:
        n = par_name(u, s)
        if n in flat:
            vals[s] = str(flat[n])
    return vals


def copy_values(flat, src_uid, dst_uid):
    """Duplicate: {TD name: value} entries of src renamed to dst."""
    a, b = 'M%d' % int(src_uid), 'M%d' % int(dst_uid)
    out = {}
    for k, v in flat.items():
        if k.startswith(a) and k[len(a):len(a) + 1].isalpha():
            out[b + k[len(a):]] = v
    return out


# ----------------------------------------------------------------------------------------------- layout + codegen

def layout(stack):
    """Enabled instances in order -> [{uid, type, base, nrows, slots{name: (row, comp)}, slot, nslot}], total rows.
    Rows base, base+1 = header (amount, effmask, maskin, invert), (chunk, 0, 0, 0). Scalars pack 4 per row in schema
    order (comp 0..3), each rate param adds a scalar '<name>ph'; xyz/rgb params take a whole row (comp 'xyz').
    slot / nslot = index of the instance among the enabled instances of its type / their count (pool sharing)."""
    out = []
    row = 0
    per_type = {}
    for inst in stack:
        if inst['enabled']:
            per_type[inst['type']] = per_type.get(inst['type'], 0) + 1
    seen = {}
    for inst in stack:
        if not inst['enabled']:
            continue
        base = row
        row += HEADER_ROWS
        slots = {}
        cur, used = None, 4
        for p in MODULES[inst['type']]['params']:
            items = [p['name']] + ([p['name'] + 'ph'] if p.get('rate') else [])
            if p['kind'] in ('xyz', 'rgb'):
                slots[p['name']] = (row, 'xyz')
                row += 1
                continue
            for nm in items:
                if used >= 4:
                    cur, used = row, 0
                    row += 1
                slots[nm] = (cur, used)
                used += 1
        k = seen.get(inst['type'], 0)
        seen[inst['type']] = k + 1
        out.append({'uid': inst['uid'], 'type': inst['type'], 'base': base, 'nrows': row - base, 'slots': slots,
                    'hdr': HEADER_ROWS,
                    'label': inst['label'], 'slot': k, 'nslot': per_type[inst['type']]})
    return out, row


def slot_expr(slot):
    r, c = slot
    return 'uM[%d].xyz' % r if c == 'xyz' else 'uM[%d].%s' % (r, 'xyzw'[c])


def substitute(code, slots, where=''):
    def rep(m):
        n = m.group(1)
        if n not in slots:
            raise ValueError('%s: unknown token $%s' % (where, n))
        return slot_expr(slots[n])
    return TOKEN_RE.sub(rep, code)


DEFINES = """#define PX_G_ROWS 26
#define PX_EP 11
#define PX_ST 5
#define PX_LK 3
#define DT uG[0].x
#define TIME uG[0].y
#define FRAME uG[0].z
#define SIDE uG[0].w
#define COUNT uG[1].x
#define RESET uG[1].y
#define ECOUNT uG[1].z
#define SEED uG[1].w
#define LOW uG[2].x
#define MID uG[2].y
#define HIGH uG[2].z
#define LEVEL uG[2].w
#define BEAT uG[3].x
#define BEATPH uG[3].y
#define BPM uG[3].z
#define BAR uG[3].w
#define SPRING uG[6].x
#define DAMP uG[6].y
#define DRAG uG[6].z
#define MAXSPEED uG[6].w
#define BBC uG[7].xyz
#define BBR uG[7].w
#define CAMPOS uG[8].xyz
#define HEATDECAY uG[8].w
#define DISRECOVER uG[9].x
#define DISFADE uG[9].y
#define DISSIZE uG[9].z
#define EDGEGAIN uG[9].w
#define EDGECOL uG[10].xyz
#define BRIGHT uG[10].w
#define LFO1 uG[11].x
#define LFO2 uG[11].y
#define CAMFWD uG[20].xyz
#define NSCENE uG[21].x
#define NACTOR uG[21].y
#define NPOOL uG[21].z
#define ACTORVEL uG[22].xyz
#define NECHO uG[21].w
#define ECHOEVERY uG[22].w
#define ECHOOFF uG[23].xyz
#define ECHOFADE uG[23].w
#define CAMVEL uG[24].xyz
#define CAMOMEGA uG[25].xyz
"""


def decl(nrows=None):
    """Uniform declarations + defines (+ uM when nrows is not None). The library comes after this.
    uPts / uPtsV / uTrail: CHOP texture buffers (vec4 per sample; T-110 pattern): point-set effector points (world
    xyz), their velocities, effector trail ring buffers (xyz + age s)."""
    s = ('uniform vec4 uG[%d];\nuniform vec4 uE[%d];\nuniform samplerBuffer uPts;\nuniform samplerBuffer uPtsV;\n'
         'uniform samplerBuffer uTrail;\n' % (G_ROWS, E_ROWS))
    if nrows is not None:
        s += 'uniform vec4 uM[%d];\n' % max(int(nrows), 1)
        # wave 2 (K37): the shared /project1/effectors list as a texture buffer (PX's eff_in), effector index >= 8
        s += '#define PX_SHARED_EFF 1\n#define PXE_ROWS uEffRows\nuniform samplerBuffer uEffRows;\n'
    return s + DEFINES


def block(inst_lay, code, stage='update'):
    """One instance as a { } block: header (G = amount x mask input, EM = effector bits, SLOT / NSLOT) + its code.
    Chunk (header row 1 x > 0): the module code runs in an inner block that shadows id / seed / p0 / P with the
    rest cell's (cell of p0, size chunk), and in the update stage home is moved to the cell centre first and moved
    back after, so the point takes the cell's displacement (and rotation, S4): points move in groups. chunk 0 = exact
    v1 behaviour (shift 0, same id/seed)."""
    b = inst_lay['base']
    label = re.sub(r'[^ -~]', '?', inst_lay['label'])
    head = ('\t{\t// [%d] %s: %s\n'
            '\tpxShSel = vec4(uM[%d].yzw, 1.0);\n'
            '\tpxShIds = uM[%d];\n'
            '\tfloat Gm = pxMaskSel(pxI(uM[%d].z), mk, dis, heat, LAYER);\n'
            '\tfloat G = uM[%d].x * (uM[%d].w > 0.5 ? 1.0 - Gm : Gm);\n'
            '\tint EM = pxI(uM[%d].y);\n'
            '\tconst int SLOT = %d, NSLOT = %d;\n'
            '\tfloat CH = uM[%d].x;\n'
            '\tvec3 _cc = CH > 0.0 ? (floor(p0 / CH) + 0.5) * CH : p0;\n'
            '\tvec3 _dp = _cc - p0;\n'
            '\tuint _ci = CH > 0.0 ? pxCellId(floor(p0 / CH)) : id;\n'
            '\tfloat _cs = CH > 0.0 ? pxRnd(_ci, 1u) : seed;\n'
            '\tvec3 _cP = P + _dp;\n'
            % (inst_lay['uid'], inst_lay['type'], label, b + 1, b + 2, b, b, b, b, inst_lay.get('slot', 0),
               inst_lay.get('nslot', 1), b + 1))
    if stage == 'update':
        head += '\thome += _dp;\n'
    head += '\t{\n\tuint id = _ci; float seed = _cs; vec3 p0 = _cc; vec3 P = _cP;\n'
    body = '\n'.join('\t' + ln if ln.strip() else ln for ln in code.rstrip('\n').split('\n'))
    tail = '\n\t}\n' + ('\thome -= _dp;\n' if stage == 'update' else '') + '\t}\n'
    return head + body + tail


def structure_hash(stack, lib='', templates=None, snippets_text='', pal_text=''):
    """Changes only when the generated shader text would change: enabled types/order/uids + code texts."""
    key = [(i['uid'], i['type']) for i in stack if i['enabled']]
    h = hashlib.sha1(json.dumps([VERSION, HEADER_ROWS, key]).encode())
    for t in [lib, snippets_text, pal_text] + list(templates or []):
        h.update(t.encode())
    return h.hexdigest()[:16]


# Actor echoes (wave 3, SA31 + TC-37): code pasted into the stage templates only while Echoes > 0 (off = the v2 text,
# only an empty line where the marker was). Echo ids follow the pool: copy k (0..K-1) of actor point j. Every ECHOEVERY
# frames copy 0 takes the actor point's last position and copy k takes copy k-1's (a shift register in the state
# feedback), + ECHOOFF per copy (depth stack / gravity); colour = the actor rest colour through the colour modules,
# alpha x (1 - (k + 1) / (K + 1))^ECHOFADE. Drawn as sprites (also under splats: sprite_range).
ECHO_UPDATE = '''	if (int(id) >= ns + pxI(NACTOR) + pxI(NPOOL) && pxI(NACTOR) > 0) {   // actor echoes (SA31)
		int ena = pxI(NACTOR);
		int e0 = ns + ena + pxI(NPOOL);
		int ek = (int(id) - e0) / ena;
		int ej = (int(id) - e0) % ena;
		vec4 e_s0 = s0;
		vec4 e_q = pxStateT(int(id), 4);
		if (JUSTRESET || (int(FRAME) % max(pxI(ECHOEVERY), 1)) == 0) {
			int esrc = ek == 0 ? ns + ej : e0 + (ek - 1) * ena + ej;
			e_s0 = vec4(pxStateT(esrc, 0).xyz + ECHOOFF, 0.0);
			e_q = pxStateT(esrc, 4);
			if (JUSTRESET) e_s0 = vec4(r0.xyz, 0.0);
		}
		if (any(isnan(e_s0))) e_s0 = vec4(r0.xyz, 0.0);
		pxStore(t0, e_s0, vec4(0.0), vec4(0.0), vec4(0.0), length(e_q) > 0.5 ? e_q : vec4(1.0, 0.0, 0.0, 0.0));
		return;
	}
'''
ECHO_LAYER = '''	bool ECHO = int(id) >= ns + pxI(NACTOR) + pxI(NPOOL) && pxI(NACTOR) > 0;
	if (ECHO) LAYER = 3;
'''
ECHO_FADE = '''	if (ECHO) {
		float eK = max(floor(NECHO / max(NACTOR, 1.0) + 0.5), 1.0);
		float ek = floor(float(int(id) - ns - pxI(NACTOR) - pxI(NPOOL)) / max(NACTOR, 1.0));
		alpha *= pow(clamp(1.0 - (ek + 1.0) / (eK + 1.0), 0.0, 1.0), max(ECHOFADE, 0.0));
	}
'''


def grid_section(eff_consumer_text):
    """The shared voxel grid accessors (pxgLayer / pxgFetch / pxgSample / pxgFieldNearest / pxePaint) cut out of lane E's
    eff_consumer.glsl (read only): from `const int PXG_FIELD` to the first adapter helper (those need the adapter's
    uniforms). '' when the text has no grid section."""
    t = str(eff_consumer_text or '')
    a = t.find('const int PXG_FIELD')
    b = t.find('// Weight + strongest effector', a)
    return t[a:b] if a >= 0 and b > a else ''


def stack_grid(stack):
    """True when an enabled module reads the shared voxel grid (heat_spread, or light with bounce: the light module's
    bounce code is always compiled under PXE_GRID, so any enabled light module counts)."""
    return any(i['enabled'] and (MODULES[i['type']].get('grid') or i['type'] == 'light') for i in stack)


def stack_cloud(stack, eff_names, rows, hot='px_hot'):
    """K36 (wave 4): True when an enabled module's shared selection can reach an enabled `cloud` row of
    /project1/effectors (a point TOP of any size through the shared grid's distance field): the stages then compile
    PXE_GRID so pxeSd / pxeGrad answer for it. PX's own hot row (heat spread) does not count. rows = eff_rt.rows()."""
    clouds = [r for r in (rows or []) if r.get('kind') == 'cloud' and r.get('name') != hot
              and not str(r.get('name', '')).startswith('px_hot')        # any PX's hot row (phase B: one per PX)
              and str(r.get('enabled', '1')).strip() not in ('0', 'False', 'false', '')]
    if not clouds:
        return False
    for i in stack:
        if not i['enabled'] or not MODULES[i['type']].get('eff'):
            continue
        _own, rest = split_effectors(i.get('values', {}).get('effectors', ''), eff_names,
                                     shared_only=i['type'] == 'light')
        for w in rest:
            if w in ('all', '*'):
                if any('pub' not in str(r.get('tags', '')).replace(',', ' ').split() for r in clouds):
                    return True                          # 29 Oct: 'all' = own rows; a #pub cloud only by name / tag
                continue
            for r in clouds:
                tags = str(r.get('tags', '')).replace(',', ' ').split()
                if w == r.get('name') or w.lstrip('#') in tags:
                    return True
    return False


def stack_mask_image(stack):
    return any(i['enabled'] and i['type'] == 'mask_image' for i in stack)


def codegen(stack, lib, tmpl_update, tmpl_colour, snippets_text, pal_text='', echo=False, grid_text='', cloud=False):
    """-> {'update', 'update_inplace', 'colour', 'rows', 'layout', 'hash'}: the ONE compute shader per stage.
    pal_text = px_palette.glsl (W1-B), put in the colour stage only (uPal[16] + uPalCtl uniforms)."""
    snips = parse_snippets(snippets_text)
    lay, nrows = layout(stack)
    parts = {'update': [], 'colour': []}
    for il in lay:
        for st in STAGES:
            code = snips.get((il['type'], st))
            if code is not None:
                parts[st].append(block(il, substitute(code, il['slots'], '%s[%d] %s' % (il['type'], il['uid'], st)), st))
    # wave 3 grid (SA5 / SA21): the update / colour stages read the shared voxel grid field on input 2 (the mask input:
    # mask_image wins when both are in the stack), accessors = eff_consumer.glsl's grid section (grid_text)
    # K36 (wave 4): also while a module's shared selection reaches a `cloud` row (cloud = stack_cloud(...))
    gridon = bool(grid_text) and (stack_grid(stack) or bool(cloud)) and not stack_mask_image(stack)
    gdef = '#define PXE_GRID sTD2DInputs[2]\n' if gridon else ''
    gtxt = (grid_text.rstrip('\n') + '\n') if gridon else ''
    head = decl(nrows) + gdef + lib + gtxt
    pal = (pal_text.rstrip('\n') + '\n') if pal_text else ''

    def fill(tmpl, mods, h=head):
        txt = mods and ''.join(mods) or '\t// (no modules in this stage)\n'
        return _marker(_marker(tmpl, 'DECL', h), 'MODULES', txt)

    up = fill(tmpl_update, parts['update'])
    col = fill(tmpl_colour, parts['colour'], decl(nrows) + gdef + pal + lib + gtxt)
    if '//@ECHO' in tmpl_update:                     # wave-3 templates (older ones have no marker)
        up = _marker(up, 'ECHO', ECHO_UPDATE if echo else '')
        col = _marker(_marker(col, 'ECHO', ECHO_LAYER if echo else ''), 'ECHOFADE', ECHO_FADE if echo else '')
    out = {'update': up, 'update_inplace': '#define PX_INPLACE 1\n' + up, 'colour': col,
           'rows': nrows, 'layout': lay,
           'grid': gridon, 'hot': gridon and stack_grid(stack),
           'hash': structure_hash(stack, lib, [tmpl_update, tmpl_colour], snippets_text,
                                  pal_text + ('echo' if echo else '') + (gtxt if gridon else ''))}
    return out


def source_text(lib, tmpl_source):
    return _marker(tmpl_source, 'DECL', decl(None) + lib)


def _marker(tmpl, name, text):
    """Replace the line that is exactly //@<name> (indent allowed); markers quoted inside comments are left alone."""
    rx = re.compile(r'^[ \t]*//@' + name + r'[ \t]*$\n?', re.M)
    if len(rx.findall(tmpl)) != 1:
        raise ValueError('template needs exactly one //@%s line' % name)
    return rx.sub(lambda m: text if text.endswith('\n') else text + '\n', tmpl, count=1)


# ----------------------------------------------------------------------------------------------- drives

DRIVE_RE = re.compile(r'^([a-z][a-z0-9]*)(?:\.([xyzrgb]))?:([A-Za-z0-9_]+)(?:\*([-+]?[0-9.]+(?:e[-+]?\d+)?))?'
                      r'([-+][0-9.]+(?:e[-+]?\d+)?)?$')


def drive_name(ch):
    """K33: a CHOP channel name as a drive source word (DRIVE_RE source: A-Z a-z 0-9 _)."""
    return re.sub(r'[^A-Za-z0-9_]', '_', str(ch)).strip('_')


def parse_drives(text):
    """'strength:low*2 radius:beat*-0.5+0.1 gravity.y:trig1*-3' -> [(param, comp|None, src, gain, offset)].
    Unparsable words are returned in the second list."""
    out, bad = [], []
    for w in str(text or '').replace(',', ' ').split():
        m = DRIVE_RE.match(w)
        if not m:
            bad.append(w)
            continue
        out.append((m.group(1), m.group(2), m.group(3), float(m.group(4)) if m.group(4) else 1.0,
                    float(m.group(5)) if m.group(5) else 0.0))
    return out, bad


def apply_drives(vals, mtype, drives, src):
    """vals {name: value} + drives -> new vals (value += gain * src[s] + offset). Unknown sources count as 0."""
    out = dict(vals)
    for pname, comp, s, gain, off in drives:
        p = param(mtype, pname) or next((h for h in HEADER if h['name'] == pname), None)
        if p is None or p['kind'] in ('menu', 'toggle'):
            continue
        x = gain * float(src.get(s, 0.0)) + off
        if p['kind'] in ('xyz', 'rgb'):
            v = list(out[pname])
            k = 'xyzrgb'.index(comp) % 3 if comp else None
            if k is None:
                v = [c + x for c in v]
            else:
                v[k] += x
            out[pname] = tuple(v)
        else:
            out[pname] = float(out[pname]) + x
    return out


# ----------------------------------------------------------------------------------------------- per-frame packing

def effector_mask(names_text, eff_names):
    m = 0
    for n in str(names_text or '').replace(',', ' ').split():
        if n in eff_names:
            k = eff_names.index(n)
            if k < MAX_EFF:
                m |= 1 << k
    return m


def integrate_phases(phases, lay, vals_by_uid, dt):
    """Rate params: phase[uid][name] += value * dt (returns a new dict). Keeps a speed change from jumping."""
    out = {}
    for il in lay:
        u = il['uid']
        prev = phases.get(u, {})
        cur = {}
        for p in MODULES[il['type']]['params']:
            if p.get('rate'):
                cur[p['name']] = prev.get(p['name'], 0.0) + float(vals_by_uid.get(u, {}).get(p['name'], p['default'])) * dt
        out[u] = cur
    return out


def split_effectors(text, eff_names, shared_only=False):
    """Module `effectors` text -> (PX's own names, the rest for the shared list). Own names win; shared_only modules
    (light) send every word to the shared list."""
    toks = str(text or '').replace(',', ' ').split()
    own = [] if shared_only else [t for t in toks if t in eff_names]
    return own, [t for t in toks if t not in own]


def shared_sel(rest, shared):
    """[tag mask, all, on] + [4 ids] for the shared words (shared = text -> effectors_logic.sel_vec's 6 numbers, e.g.
    eff_rt.sel_vec). Nothing selected (no words, unknown words, no list) -> all zeros (on 0 = the old path)."""
    if not rest or shared is None:
        return [0.0, 0.0, 0.0], [0.0] * 4
    try:
        v = [float(x) for x in shared(' '.join(rest))]
    except Exception:
        return [0.0, 0.0, 0.0], [0.0] * 4
    on = 1.0 if (v[0] != 0.0 or v[1] > 0.5 or any(x > 0.0 for x in v[2:6])) else 0.0
    return [v[0], v[1], on], list(v[2:6])


def pack_module_rows(lay, nrows, vals_by_uid, eff_names, phases=None, shared=None):
    """-> nrows x [x, y, z, w] for uM[]. shared = text -> sel_vec numbers of /project1/effectors (None: own only)."""
    rows = [[0.0, 0.0, 0.0, 0.0] for _ in range(max(nrows, 1))]
    phases = phases or {}
    for il in lay:
        u = il['uid']
        mt = il['type']
        v = vals_by_uid.get(u) or {}
        dflt = None
        b = il['base']
        own, rest = split_effectors(v.get('effectors', ''), eff_names, MODULES[mt].get('shared_only', False))
        sv, ids = shared_sel(rest, shared)
        rows[b] = [float(v.get('amount', 1.0)), float(effector_mask(' '.join(own), eff_names)),
                   float(menu_index(MASKSEL, v.get('maskin', 0))), 1.0 if _truthy(v.get('invert', 0)) else 0.0]
        if il.get('hdr', 2) >= 3:                    # wave 2 layout; an older compiled layout keeps its 2 header rows
            rows[b + 1] = [max(float(v.get('chunk', 0.0)), 0.0)] + sv
            rows[b + 2] = ids
        else:
            rows[b][1] = float(effector_mask(v.get('effectors', ''), eff_names))
            rows[b + 1] = [max(float(v.get('chunk', 0.0)), 0.0), 0.0, 0.0, 0.0]
        for p in MODULES[mt]['params']:
            if p['name'] in v:
                val = v[p['name']]
            else:
                dflt = dflt or dict((q['name'], q['default']) for q in MODULES[mt]['params'])
                val = dflt[p['name']]
            if p['name'] not in il['slots']:            # a layout compiled by an older px_logic (upgrade in flight)
                continue
            r, c = il['slots'][p['name']]
            try:
                if c == 'xyz':
                    rows[r][0:3] = [float(x) for x in val]
                elif p['kind'] == 'menu':
                    rows[r][c] = float(menu_index(p['menu'], val))
                elif p['kind'] == 'toggle':
                    rows[r][c] = 1.0 if _truthy(val) else 0.0
                else:
                    rows[r][c] = float(val)
            except (TypeError, ValueError):             # a recall in flight: the same uid is another module type for a
                continue                                # frame or two (compiled layout vs new values; wave 4 b5)
            if p.get('rate'):
                r2, c2 = il['slots'][p['name'] + 'ph']
                rows[r2][c2] = float(phases.get(u, {}).get(p['name'], 0.0))
    return rows


def _truthy(v):
    if isinstance(v, str):
        return v.strip().lower() not in ('', '0', 'false', 'off')
    return bool(v)


# ---- effectors

def affine_from_points(o, ex, ey, ez):
    """World images of the local origin and unit axes -> 3x4 row-major world matrix [A | t]."""
    cols = [[ex[k] - o[k] for k in range(3)], [ey[k] - o[k] for k in range(3)], [ez[k] - o[k] for k in range(3)]]
    return [[cols[0][r], cols[1][r], cols[2][r], o[r]] for r in range(3)]


def affine_inverse(m):
    """3x4 [A | t] -> 3x4 inverse [A^-1 | -A^-1 t]. Singular -> translate-only inverse."""
    a = [row[:3] for row in m]
    t = [row[3] for row in m]
    det = (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
           + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
    if abs(det) < 1e-12:
        return [[1.0, 0.0, 0.0, -t[0]], [0.0, 1.0, 0.0, -t[1]], [0.0, 0.0, 1.0, -t[2]]]
    inv = [[(a[1][1] * a[2][2] - a[1][2] * a[2][1]) / det, (a[0][2] * a[2][1] - a[0][1] * a[2][2]) / det,
            (a[0][1] * a[1][2] - a[0][2] * a[1][1]) / det],
           [(a[1][2] * a[2][0] - a[1][0] * a[2][2]) / det, (a[0][0] * a[2][2] - a[0][2] * a[2][0]) / det,
            (a[0][2] * a[1][0] - a[0][0] * a[1][2]) / det],
           [(a[1][0] * a[2][1] - a[1][1] * a[2][0]) / det, (a[0][1] * a[2][0] - a[0][0] * a[2][1]) / det,
            (a[0][0] * a[1][1] - a[0][1] * a[1][0]) / det]]
    return [[inv[r][0], inv[r][1], inv[r][2], -(inv[r][0] * t[0] + inv[r][1] * t[1] + inv[r][2] * t[2])] for r in range(3)]


def affine_det(m):
    a = [row[:3] for row in m]
    return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))


def chop_affine(t, s=1.0):
    s = float(s) if s else 1.0
    return [[s, 0.0, 0.0, t[0]], [0.0, s, 0.0, t[1]], [0.0, 0.0, s, t[2]]]


def effector_rows(effs):
    """effs = [{'kind', 'world': 3x4, 'speed', 'vel'?, 'axis'?, 'size'?, 'pts'?: (start, count, mode),
    'trail'?: (start, count)}] (index = effector id, max 8) -> E_ROWS x 4 for uE[]. Rows per effector (E_PER 11):
    0..2 inverse world matrix (world -> local), 3 (sdf type, local size xyz), 4 (world centre xyz, world scale),
    5 (up axis xyz (camera: forward), speed units/s), 6 (velocity xyz, pts start), 7 (pts count, pts mode,
    trail start, trail count), 8..10 world matrix (local -> world: volume / surface sampling for embers)."""
    rows = [[0.0, 0.0, 0.0, 0.0] for _ in range(E_ROWS)]
    for i, e in enumerate(effs[:MAX_EFF]):
        w = e['world']
        inv = affine_inverse(w)
        ty, sz = EFF_SDF.get(e.get('kind', 'null'), EFF_SDF['null'])
        b = i * E_PER
        rows[b] = list(inv[0])
        rows[b + 1] = list(inv[1])
        rows[b + 2] = list(inv[2])
        rows[b + 3] = [float(ty)] + [float(x) for x in e.get('size', sz)]
        sc = abs(affine_det(w)) ** (1.0 / 3.0) or 1.0
        rows[b + 4] = [w[0][3], w[1][3], w[2][3], sc]
        ax = e.get('axis') or (w[0][1], w[1][1], w[2][1])
        rows[b + 5] = [float(ax[0]), float(ax[1]), float(ax[2]), float(e.get('speed', 0.0))]
        vel = e.get('vel') or (0.0, 0.0, 0.0)
        ps, pc, pm = e.get('pts') or (0, 0, 0)
        ts, tc = e.get('trail') or (0, 0)
        rows[b + 6] = [float(vel[0]), float(vel[1]), float(vel[2]), float(ps)]
        rows[b + 7] = [float(pc), float(pm), float(ts), float(tc)]
        rows[b + 8] = [float(x) for x in w[0]]
        rows[b + 9] = [float(x) for x in w[1]]
        rows[b + 10] = [float(x) for x in w[2]]
    return rows


# ---- effector settings (custom pars on each effector object's 'Effector' page; px_rt reads them per frame)

EFF_PARS = [
    ('Motion', 'Menu', 'none', {'names': [m[0] for m in MOTIONS], 'labels': [m[1] for m in MOTIONS]}),
    ('Mperiod', 'Float', 18.0, {'min': 0.1, 'max': 120, 'label': 'Seconds per cycle'}),
    ('Mphase', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Phase'}),
    ('Mloop', 'Menu', 'loop', {'names': [m[0] for m in LOOPS], 'labels': [m[1] for m in LOOPS]}),
    ('Mease', 'Menu', 'smooth', {'names': [m[0] for m in EASES], 'labels': [m[1] for m in EASES]}),
    ('Ma', 'XYZ', (-2.0, 0.0, 0.0), {'min': -20, 'max': 20, 'label': 'A (start / centre / offset)'}),
    ('Mb', 'XYZ', (2.0, 0.0, 0.0), {'min': -20, 'max': 20, 'label': 'B (end / radii / amplitude)'}),
    ('Mfreq', 'XYZ', (1.0, 2.0, 3.0), {'min': 0, 'max': 10, 'label': 'Lissajous freq'}),
    ('Mchop', 'Str', '', {'label': 'CHOP path (tx ty tz)'}),
    ('Mfollow', 'Str', '', {'label': 'Follow object (path)'}),
    ('Mlag', 'Float', 0.3, {'min': 0, 'max': 5, 'label': 'Follow lag s'}),
    ('Mplay', 'Toggle', True, {'label': 'Motion play (time = sim time; COMP Reset restarts)'}),
    ('Trail', 'Int', 0, {'min': 0, 'max': TRAIL_MAX, 'label': 'Trail length (0 off)'}),
    ('Traildt', 'Float', 0.05, {'min': 0.0, 'max': 1, 'label': 'Trail sample s'}),
    ('Glow', 'Toggle', False, {'label': 'Glow in out1 (additive light)'}),
    ('Glowcolour', 'RGB', (1.0, 0.6, 0.25), {}),
    ('Glowintensity', 'Float', 2.0, {'min': 0, 'max': 50}),
    ('Glowsize', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Glow size (x shape)'}),
    ('Glowtrail', 'Toggle', False, {'label': 'Glow along the trail'}),
    ('Ptssource', 'Str', '', {'label': 'Point set (CHOP tx ty tz / SOP)'}),
    ('Ptsmode', 'Menu', 'nearest', {'names': [m[0] for m in PTSMODES], 'labels': [m[1] for m in PTSMODES]}),
    ('Ptsradius', 'Float', 0.02, {'min': 0, 'max': 1, 'label': 'Point radius'}),
    ('Ptsmax', 'Int', 512, {'min': 1, 'max': PTS_MAX, 'label': 'Max points (stride subsample)'}),
]
EFF_PAR_NAMES = [p[0] for p in EFF_PARS]


def eff_settings(raw):
    """{par name: value} (possibly partial, from an effector object's page) -> full settings with defaults."""
    out = {}
    for name, style, default, _o in EFF_PARS:
        if style == 'Pulse':
            continue
        if style in ('XYZ', 'RGB'):
            suf = 'xyz' if style == 'XYZ' else 'rgb'
            out[name] = tuple(float(raw.get(name + s_, d)) for s_, d in zip(suf, default))
        else:
            out[name] = raw.get(name, default)
    return out


# ---- motion paths (A2): pure, the runtime writes the result into the effector object's translate

def _loop_u(t, period, loop, phase=0.0):
    """Cycle fraction 0..1 at time t: loop (saw), pingpong (tri), once (clamped)."""
    x = t / max(float(period), 1e-6) + float(phase)
    if loop == 'once':
        return max(0.0, min(1.0, x))
    f = x - math.floor(x)
    if loop == 'pingpong':
        return 1.0 - abs(2.0 * f - 1.0)
    return f


def _noise1(x, seed):
    """Smooth 1D value noise in -1..1 (python twin of the GLSL lattice hash, stable across runs)."""
    i = math.floor(x)
    f = x - i
    u = f * f * (3.0 - 2.0 * f)

    def h(k):
        v = (int(k) * 73856093 ^ (seed * 2654435761)) & 0xFFFFFFFF
        v ^= v >> 16
        v = (v * 0x7feb352d) & 0xFFFFFFFF
        v ^= v >> 15
        v = (v * 0x846ca68b) & 0xFFFFFFFF
        v ^= v >> 16
        return (v >> 8) / 16777216.0 * 2.0 - 1.0
    return h(i) + (h(i + 1) - h(i)) * u


def motion_pos(kind, t, s, chop_pts=None, follow=None, prev=None, dt=0.0, seed=0):
    """Effector position at time t (seconds since the motion started). s = eff_settings(). chop_pts = list of xyz
    (chop path), follow = xyz of the followed object, prev = last position (follow lag). Returns xyz or None (none)."""
    a = s['Ma']
    b = s['Mb']
    per = float(s['Mperiod'])
    if kind == 'line':
        u = ref_ease(_loop_u(t, per, s['Mloop'], float(s['Mphase'])), menu_index(EASES, s['Mease']))
        return tuple(a[k] + (b[k] - a[k]) * u for k in range(3))
    if kind == 'circle':
        ang = 2.0 * math.pi * _loop_u(t, per, 'loop' if s['Mloop'] != 'once' else 'once', float(s['Mphase']))
        return (a[0] + b[0] * math.cos(ang), a[1] + b[1] * math.sin(ang), a[2] + b[2] * math.sin(ang))
    if kind == 'lissajous':
        f = s['Mfreq']
        ph = 2.0 * math.pi * (t / max(per, 1e-6) + float(s['Mphase']))
        return (a[0] + b[0] * math.sin(f[0] * ph), a[1] + b[1] * math.sin(f[1] * ph + 0.5 * math.pi),
                a[2] + b[2] * math.sin(f[2] * ph))
    if kind == 'chop':
        pts = list(chop_pts or [])
        if not pts:
            return None
        if len(pts) == 1:
            return tuple(pts[0])
        u = ref_ease(_loop_u(t, per, s['Mloop'], float(s['Mphase'])), menu_index(EASES, s['Mease']))
        x = u * (len(pts) - 1)
        i = min(int(math.floor(x)), len(pts) - 2)
        f = x - i
        return tuple(pts[i][k] + (pts[i + 1][k] - pts[i][k]) * f for k in range(3))
    if kind == 'wander':
        x = t / max(per, 1e-6) * 4.0
        return tuple(a[k] + b[k] * _noise1(x + 17.0 * k, seed + 31 * k) for k in range(3))
    if kind == 'follow':
        if follow is None:
            return None
        tgt = tuple(follow[k] + a[k] for k in range(3))
        lag = float(s['Mlag'])
        if prev is None or lag <= 0.0 or dt <= 0.0:
            return tgt
        k_ = 1.0 - math.exp(-dt / lag)
        return tuple(prev[k] + (tgt[k] - prev[k]) * k_ for k in range(3))
    return None


# ---- trails (A3): ring buffer of past centres, newest first

def trail_push(buf, pos, t, n, dt_min):
    """buf = list of (xyz, t) newest first -> new list: pos is added when dt_min passed since the newest sample
    (else the newest sample is replaced, so the head follows the effector), length <= n (n 0 = empty)."""
    n = max(0, min(int(n), TRAIL_MAX))
    if n == 0:
        return []
    b = list(buf)
    if b and t - b[0][1] < float(dt_min):
        b[0] = (tuple(pos), b[0][1])
    else:
        b.insert(0, (tuple(pos), float(t)))
    return b[:n]


def trail_rows(bufs, t):
    """bufs = [list of (xyz, t)] per effector -> (rows [x, y, z, age s], [(start, count)] per effector)."""
    rows, spans = [], []
    for b in bufs:
        st = len(rows)
        for p, tt in (b or []):
            rows.append([float(p[0]), float(p[1]), float(p[2]), max(float(t) - float(tt), 0.0)])
        spans.append((st, len(rows) - st))
    return (rows or [[0.0, 0.0, 0.0, 0.0]]), spans


# ---- point sets (A1)

def pts_subsample(pts, nmax):
    """Even stride subsample to at most nmax points (keeps the first, order preserved)."""
    n = len(pts)
    nmax = max(1, int(nmax))
    if n <= nmax:
        return list(range(n))
    return [int(i * n / nmax) for i in range(nmax)]


def pts_from_chans(chans):
    """CHOP channels {name: [samples]} -> list of xyz. Layouts: (a) samples = points, channels tx ty tz (or x y z /
    P0 P1 P2); (b) one point per channel triple '<prefix>tx/ty/tz' or '<prefix>x/y/z' (landmark CHOPs), in name order;
    z may be missing (2D landmarks, e.g. FT_face_track out_pts '<lm>x/<lm>y': z = 0)."""
    for kx, ky, kz in (('tx', 'ty', 'tz'), ('x', 'y', 'z'), ('P0', 'P1', 'P2'), ('px', 'py', 'pz'), ('P_0', 'P_1', 'P_2'),
                       ('r', 'g', 'b')):          # POP to CHOP P_0..2; TOP to CHOP of an xyz texture (r g b)
        if kx in chans and ky in chans and kz in chans:
            n = min(len(chans[kx]), len(chans[ky]), len(chans[kz]))
            return [(float(chans[kx][i]), float(chans[ky][i]), float(chans[kz][i])) for i in range(n)]
    out = []
    names = list(chans.keys())
    seen = set()
    for nm in names:
        for sx, sy, sz in (('tx', 'ty', 'tz'), ('x', 'y', 'z')):
            if nm.endswith(sx) and len(nm) > len(sx):
                pre = nm[:-len(sx)]
                if pre in seen:
                    continue
                if pre + sy in chans:                 # z optional: 2D landmark CHOPs (FT_face_track x / y pairs)
                    seen.add(pre)
                    z = float(chans[pre + sz][0]) if pre + sz in chans else 0.0
                    out.append((float(chans[nm][0]), float(chans[pre + sy][0]), z))
                break
    return out


def xform_pts(world, pts):
    return [tuple(world[r][0] * p[0] + world[r][1] * p[1] + world[r][2] * p[2] + world[r][3] for r in range(3))
            for p in pts]


def pts_velocity(cur, prev, dt):
    """Per-point frame-difference velocity (units/s); zeros when the counts differ or dt is 0."""
    if prev is None or len(prev) != len(cur) or dt <= 0.0:
        return [(0.0, 0.0, 0.0)] * len(cur)
    return [tuple((a[k] - b[k]) / dt for k in range(3)) for a, b in zip(cur, prev)]


def pack_pts(sets):
    """sets = [(points xyz, velocities xyz)] per pts effector -> (rows [x y z 1], vrows [vx vy vz 0], spans
    [(start, count)]). Total capped at PTS_MAX (later sets get what is left)."""
    rows, vrows, spans = [], [], []
    for pts, vel in sets:
        st = len(rows)
        room = max(PTS_MAX - st, 0)
        for p, v in list(zip(pts, vel))[:room]:
            rows.append([float(p[0]), float(p[1]), float(p[2]), 1.0])
            vrows.append([float(v[0]), float(v[1]), float(v[2]), 0.0])
        spans.append((st, len(rows) - st))
    return (rows or [[0.0, 0.0, 0.0, 0.0]]), (vrows or [[0.0, 0.0, 0.0, 0.0]]), spans


# ---- quaternions (wxyz, the splat convention of splat_render_logic.quat_to_mat3)

def quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw)


def quat_axis(axis, ang):
    n = math.sqrt(sum(c * c for c in axis)) or 1.0
    s = math.sin(0.5 * ang) / n
    return (math.cos(0.5 * ang), axis[0] * s, axis[1] * s, axis[2] * s)


def quat_from_mat3(R):
    """Rotation matrix (rows) -> unit quaternion wxyz (Shepperd)."""
    tr = R[0][0] + R[1][1] + R[2][2]
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        q = (0.25 * s, (R[2][1] - R[1][2]) / s, (R[0][2] - R[2][0]) / s, (R[1][0] - R[0][1]) / s)
    elif R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = math.sqrt(1.0 + R[0][0] - R[1][1] - R[2][2]) * 2.0
        q = ((R[2][1] - R[1][2]) / s, 0.25 * s, (R[0][1] + R[1][0]) / s, (R[0][2] + R[2][0]) / s)
    elif R[1][1] > R[2][2]:
        s = math.sqrt(1.0 + R[1][1] - R[0][0] - R[2][2]) * 2.0
        q = ((R[0][2] - R[2][0]) / s, (R[0][1] + R[1][0]) / s, 0.25 * s, (R[1][2] + R[2][1]) / s)
    else:
        s = math.sqrt(1.0 + R[2][2] - R[0][0] - R[1][1]) * 2.0
        q = ((R[1][0] - R[0][1]) / s, (R[0][2] + R[2][0]) / s, (R[1][2] + R[2][1]) / s, 0.25 * s)
    n = math.sqrt(sum(c * c for c in q)) or 1.0
    q = tuple(c / n for c in q)
    return q if q[0] >= 0.0 else tuple(-c for c in q)


def affine_scale_quat(w):
    """World 3x4 [A | t] of a COMP (scale then rotate, no shear) -> (column scales xyz, quaternion wxyz)."""
    cols = [[w[r][k] for r in range(3)] for k in range(3)]
    sc = [math.sqrt(sum(c * c for c in col)) or 1e-9 for col in cols]
    R = [[cols[k][r] / sc[k] for k in range(3)] for r in range(3)]
    if affine_det(w) < 0.0:                                  # mirrored: flip one axis so R stays a rotation
        sc[0] = -sc[0]
        for r in range(3):
            R[r][0] = -R[r][0]
    return tuple(abs(x) for x in sc), quat_from_mat3(R)


# ---- glow (A5): effectors drawn into out1 as additive 3D gaussians through the reused splat renderer

GLOW_SHAPE = {'sphere': (0.5, 0.5, 0.5), 'box': (0.5, 0.5, 0.5), 'plane': (0.5, 0.02, 0.5), 'capsule': (0.25, 0.75, 0.25),
              'torus': (0.65, 0.15, 0.65), 'null': (0.1, 0.1, 0.1), 'chop': (0.1, 0.1, 0.1), 'pts': (0.1, 0.1, 0.1),
              'actor': (0.2, 0.4, 0.2), 'camera': (0.0, 0.0, 0.0)}


def glow_rows(effs, recol=None):
    """effs = [{'kind', 'world', 'settings': eff_settings(), 'trail': [(xyz, t)]}] -> rows (GLOW_PER per glow
    instance: (P, 1), (sigma xyz, 0), quat wxyz, (rgb * intensity, alpha)), instance count. Sigma = shape half size
    x object scale x Glowsize / 2 (the splat quad reaches ~2-3 sigma). Trail glows: up to 8 per effector, fading."""
    rows = []
    gk = 0
    for e in effs:
        s = e.get('settings') or {}
        if not _truthy(s.get('Glow', False)):
            continue
        sc, q = affine_scale_quat(e['world'])
        hs = GLOW_SHAPE.get(e.get('kind', 'null'), (0.1, 0.1, 0.1))
        g = float(s.get('Glowsize', 1.0))
        sig = [max(hs[k] * sc[k] * g * 0.5, 1e-4) for k in range(3)]
        col = s.get('Glowcolour', (1.0, 0.6, 0.25))
        if recol is not None:                       # wave 2: Glow colour source (Palette page; index = glow k)
            col = recol(gk, tuple(col))
        gk += 1
        it = float(s.get('Glowintensity', 2.0))
        w = e['world']
        pts = [((w[0][3], w[1][3], w[2][3]), 1.0)]
        if _truthy(s.get('Glowtrail', False)):
            tr = list(e.get('trail') or [])
            for k in pts_subsample(tr, 8):
                pts.append((tr[k][0], 1.0 - (k + 1.0) / (len(tr) + 1.0)))
        for p, fade in pts:
            if len(rows) // GLOW_PER >= GLOW_MAX:
                break
            rows += [[float(p[0]), float(p[1]), float(p[2]), 1.0], sig + [0.0], list(q),
                     [col[0] * it * fade, col[1] * it * fade, col[2] * it * fade, 0.99]]
    n = len(rows) // GLOW_PER
    return (rows or [[0.0] * 4] * GLOW_PER), n


# ---- clock / drives sources

def beat_state(t, bpm, decay=6.0, beats_per_bar=4):
    """-> (env, phase, bar_phase). env = exp(-decay * seconds since the beat)."""
    bpm = max(float(bpm), 1e-3)
    beats = t * bpm / 60.0
    ph = beats - math.floor(beats)
    env = math.exp(-decay * ph * 60.0 / bpm)
    bar = (beats / beats_per_bar) - math.floor(beats / beats_per_bar)
    return env, ph, bar


def trig_env(age, decay):
    return math.exp(-max(decay, 0.0) * max(age, 0.0)) if age < 1e5 else 0.0


def lfo(t, rate, shape='sine', phase=0.0):
    x = t * rate + phase
    f = x - math.floor(x)
    if shape == 'tri':
        return 1.0 - abs(2.0 * f - 1.0)
    if shape == 'saw':
        return f
    if shape == 'square':
        return 1.0 if f < 0.5 else 0.0
    return 0.5 + 0.5 * math.sin(2.0 * math.pi * x)



def cam_viewproj(cam_row, fov_deg, resx, resy, near=0.01, far=1000.0):
    """proj * view rows (clip = row . (p, 1)) of the output camera from its orbit numbers (tx ty tz ry deg) and a
    horizontal FOV; pure maths, so the engine never reads pcam (pcam reads eng_cam: reading it back was a cook loop)."""
    tx, ty, tz, ry = [float(v) for v in cam_row[:4]]
    a = math.radians(ry)
    ca, sa = math.cos(a), math.sin(a)
    # view = Ry(-a) * T(-p): rows of the 3x4 world -> camera transform
    rot = [[ca, 0.0, -sa], [0.0, 1.0, 0.0], [sa, 0.0, ca]]
    view = [r + [-(r[0] * tx + r[1] * ty + r[2] * tz)] for r in rot] + [[0.0, 0.0, 0.0, 1.0]]
    fx = 1.0 / math.tan(math.radians(max(float(fov_deg), 1e-3)) * 0.5)
    fy = fx * float(resx) / max(float(resy), 1.0)
    n, f = float(near), float(far)
    proj = [[fx, 0.0, 0.0, 0.0], [0.0, fy, 0.0, 0.0], [0.0, 0.0, -(f + n) / (f - n), -2.0 * f * n / (f - n)],
            [0.0, 0.0, -1.0, 0.0]]
    return [[sum(proj[r][k] * view[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def global_rows(g):
    """g: dict with dt t frame side count reset ecount seed low mid high level beat beatph bpm bar trig[4] trigage[4]
    spring damp drag maxspeed bbc(3) bbr campos(3) heatdecay disrecover disfade dissize edgegain edgecol(3) bright
    lfo1 lfo2 spec(16) viewproj (4 rows of 4) camfwd(3) nscene nactor npool actorvel(3) -> G_ROWS x 4."""
    z4 = [0.0, 0.0, 0.0, 0.0]
    gv = lambda k, d=0.0: float(g.get(k, d))
    spec = list(g.get('spec', [0.0] * 16))[:16] + [0.0] * max(0, 16 - len(g.get('spec', [])))
    vp = g.get('viewproj') or [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
    tr = list(g.get('trig', [0.0] * 4))
    ta = list(g.get('trigage', [1e6] * 4))
    rows = [
        [gv('dt'), gv('t'), gv('frame'), gv('side', 1)],
        [gv('count'), gv('reset'), gv('ecount'), gv('seed')],
        [gv('low'), gv('mid'), gv('high'), gv('level')],
        [gv('beat'), gv('beatph'), gv('bpm', 120), gv('bar')],
        [float(x) for x in tr],
        [float(x) for x in ta],
        [gv('spring', 4.0), gv('damp', 1.5), gv('drag', 0.2), gv('maxspeed', 0.0)],
        [float(x) for x in g.get('bbc', (0.0, 0.0, 0.0))] + [gv('bbr', 1.0)],
        [float(x) for x in g.get('campos', (0.0, 0.0, 5.0))] + [gv('heatdecay', 0.5)],
        [gv('disrecover', 1.0), gv('disfade', 1.0), gv('dissize', 0.3), gv('edgegain', 2.0)],
        [float(x) for x in g.get('edgecol', (1.0, 0.5, 0.15))] + [gv('bright', 1.0)],
        [gv('lfo1'), gv('lfo2'), 0.0, 0.0],
        spec[0:4], spec[4:8], spec[8:12], spec[12:16],
        [float(x) for x in vp[0]], [float(x) for x in vp[1]], [float(x) for x in vp[2]], [float(x) for x in vp[3]],
        [float(x) for x in g.get('camfwd', (0.0, 0.0, -1.0))] + [0.0],
        [gv('nscene', g.get('count', 0)), gv('nactor'), gv('npool'), gv('necho')],
        [float(x) for x in g.get('actorvel', (0.0, 0.0, 0.0))] + [gv('echoevery', 0.0)],
        [float(x) for x in g.get('echooff', (0.0, 0.0, 0.0))] + [gv('echofade', 0.0)],
        [float(x) for x in g.get('camvel', (0.0, 0.0, 0.0))] + [0.0],
        [float(x) for x in g.get('camomega', (0.0, 0.0, 0.0))] + [0.0],
    ]
    assert len(rows) == G_ROWS
    return [list(r) if len(r) == 4 else (list(r) + z4)[:4] for r in rows]


# ----------------------------------------------------------------------------------------------- core pages (COMP pars)

def cs_pars(prefix, default='solid'):
    """W1-B colour source pars of one element (the element keeps its own RGB par): <P>colsrc, <P>palpos,
    <P>palspread, <P>keep (palette_map_logic.colsrc_pars without the colour)."""
    return [(prefix + 'colsrc', 'Menu', default, {'names': names(COLSRC_MODES), 'labels': labels(COLSRC_MODES),
                                                 'label': prefix + ' colour source'}),
            (prefix + 'palpos', 'Float', 0.0, {'min': 0, 'max': 1, 'label': prefix + ' palette position'}),
            (prefix + 'palspread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': prefix + ' palette spread'}),
            (prefix + 'keep', 'Float', 0.0, {'min': 0, 'max': 1, 'label': prefix + ' keep own colour'})]


def cs_vec(raw, prefix):
    """(mode index, pos, spread, keep) of an element's colour source from the COMP's pars."""
    return [float(menu_index(COLSRC_MODES, raw.get(prefix + 'colsrc', 'solid'))), float(raw.get(prefix + 'palpos', 0.0)),
            float(raw.get(prefix + 'palspread', 1.0)), float(raw.get(prefix + 'keep', 0.0))]


def cs_is_solid(cs):
    return cs[0] == 0.0 and cs[3] <= 0.0


CORE_PAGES = [
    ('Source', [
        ('Quality', 'Menu', 'std', {'names': [q[0] for q in QUALITY], 'labels': [q[1] for q in QUALITY]}),
        ('Count', 'Int', 131072, {'min': 1, 'max': 2683044, 'label': 'Count (Quality custom)'}),   # = COUNT_MAX (phase B)
        ('Amode', 'Menu', 'gen', {'names': names(AMODES), 'labels': labels(AMODES), 'label': 'A source'}),
        ('Afile', 'File', '', {'label': 'A file'}),
        ('Agen', 'Menu', 'sphere', {'names': names(GENERATORS), 'labels': labels(GENERATORS), 'label': 'A generator'}),
        ('Agenp', 'Float', 1.0, {'min': 0.01, 'max': 20, 'label': 'A size'}),
        ('Agenp2', 'Float', 0.3, {'min': 0, 'max': 20, 'label': 'A param 2'}),
        ('Agenp3', 'Float', 0.0, {'min': 0, 'max': 5, 'label': 'A param 3'}),
        ('Aspin', 'Float', 0.0, {'min': -5, 'max': 5, 'label': 'A spin rad/s'}),
        ('Acolmode', 'Menu', 'position', {'names': names(COLMODES), 'labels': labels(COLMODES), 'label': 'A colour'}),
        ('Acolour', 'RGB', (1.0, 1.0, 1.0), {'label': 'A solid colour'}),
        ('Ascale', 'Float', 1.0, {'min': 0.01, 'max': 20}),
        ('Arot', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'A rotate y deg'}),
        ('Aoffset', 'XYZ', (0.0, 0.0, 0.0), {'min': -10, 'max': 10}),
        ('Aup', 'Menu', 'y', {'names': ['y', 'z', '-y', '-z'], 'labels': ['Y up', 'Z up (scans)', 'Y down (splats)', 'Z down'],
                              'label': 'A file up axis'}),
        ('Bmode', 'Menu', 'off', {'names': names(SOURCEMODES), 'labels': labels(SOURCEMODES), 'label': 'B source'}),
        ('Bfile', 'File', '', {'label': 'B file'}),
        ('Bgen', 'Menu', 'torus', {'names': names(GENERATORS), 'labels': labels(GENERATORS), 'label': 'B generator'}),
        ('Bgenp', 'Float', 1.0, {'min': 0.01, 'max': 20, 'label': 'B size'}),
        ('Bgenp2', 'Float', 0.3, {'min': 0, 'max': 20, 'label': 'B param 2'}),
        ('Bgenp3', 'Float', 0.0, {'min': 0, 'max': 5, 'label': 'B param 3'}),
        ('Bspin', 'Float', 0.0, {'min': -5, 'max': 5, 'label': 'B spin rad/s'}),
        ('Bcolmode', 'Menu', 'position', {'names': names(COLMODES), 'labels': labels(COLMODES), 'label': 'B colour'}),
        ('Bcolour', 'RGB', (1.0, 0.5, 0.2), {'label': 'B solid colour'}),
        ('Bscale', 'Float', 1.0, {'min': 0.01, 'max': 20}),
        ('Brot', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'B rotate y deg'}),
        ('Boffset', 'XYZ', (0.0, 0.0, 0.0), {'min': -10, 'max': 10}),
        ('Bup', 'Menu', 'y', {'names': ['y', 'z', '-y', '-z'], 'labels': ['Y up', 'Z up (scans)', 'Y down (splats)', 'Z down'],
                              'label': 'B file up axis'}),
        ('Morph', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Morph A -> B'}),
        ('Stagger', 'Float', 0.5, {'min': 0, 'max': 4}),
        ('Staggermode', 'Menu', 'random', {'names': names(STAGGERS), 'labels': labels(STAGGERS)}),
        ('Arc', 'Float', 0.3, {'min': 0, 'max': 5, 'label': 'Morph arc'}),
        ('Ease', 'Menu', 'smooth', {'names': names(EASES), 'labels': labels(EASES)}),
        ('Match', 'Menu', 'morton', {'names': ['morton', 'kd', 'index'], 'labels': ['Morton', 'k-d split', 'Index (none)'],
                                     'label': 'File A/B matching'}),
        ('Depthfov', 'Float', 60.0, {'min': 10, 'max': 150, 'label': 'Depth fov deg'}),
        ('Depthnear', 'Float', 1.0, {'min': 0.01, 'max': 20}),
        ('Depthfar', 'Float', 4.0, {'min': 0.1, 'max': 100}),
        ('Depththr', 'Float', 0.02, {'min': 0, 'max': 1, 'label': 'Depth keep above'}),
        ('Depthscale', 'Float', 1.0, {'min': 0.01, 'max': 10}),
        ('Depthmirror', 'Toggle', True, {}),
        ('Depthgain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Depth colour gain'}),
        ('Splatscale', 'Toggle', False, {'label': 'Size from splat scale'}),
        ('Splatk', 'Float', 3.0, {'min': 0, 'max': 20, 'label': 'Splat size factor'}),
        ('Clip', 'Float', 0.0, {'min': 0, 'max': 200, 'label': 'Load: keep within radius of the median (0 off)'}),
        ('Opacitymin', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Load: drop splats below opacity (floaters)'}),
        ('Reload', 'Pulse', None, {}),
        # actor layer (A4): a second point / splat source inside the same budget (ids after the scene)
        ('Actormode', 'Menu', 'off', {'names': names(ACTORMODES), 'labels': labels(ACTORMODES), 'label': 'Actor source'}),
        ('Actorfile', 'File', '', {'label': 'Actor file'}),
        ('Actorseq', 'Folder', '', {'label': 'Actor sequence folder (frames)'}),
        ('Actorfps', 'Float', 24.0, {'min': 1, 'max': 60, 'label': 'Actor sequence fps'}),
        ('Actorcount', 'Int', 16384, {'min': 0, 'max': 1048576, 'label': 'Actor points'}),
        ('Actorgen', 'Menu', 'cylinder', {'names': names(GENERATORS), 'labels': labels(GENERATORS), 'label': 'Actor generator'}),
        ('Actorgenp', 'Float', 0.9, {'min': 0.01, 'max': 20, 'label': 'Actor size'}),
        ('Actorgenp2', 'Float', 0.3, {'min': 0, 'max': 20, 'label': 'Actor param 2'}),
        ('Actorgenp3', 'Float', 0.0, {'min': 0, 'max': 5, 'label': 'Actor param 3'}),
        ('Actorspin', 'Float', 0.0, {'min': -5, 'max': 5, 'label': 'Actor spin rad/s'}),
        ('Actorscale', 'Float', 1.0, {'min': 0.01, 'max': 20}),
        ('Actorrot', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Actor rotate y deg'}),
        ('Actoroffset', 'XYZ', (0.0, 0.0, 0.0), {'min': -10, 'max': 10}),
        ('Actorfollow', 'Str', '', {'label': 'Actor follows effector (name)', 'menu': True}),
        ('Actorup', 'Menu', 'y', {'names': ['y', 'z', '-y', '-z'], 'labels': ['Y up', 'Z up (scans)', 'Y down (splats)', 'Z down'],
                                  'label': 'Actor file up axis'}),
        ('Actorcolmode', 'Menu', 'solid', {'names': names(COLMODES), 'labels': labels(COLMODES), 'label': 'Actor colour'}),
        ('Actorcolour', 'RGB', (1.0, 0.9, 0.8), {'label': 'Actor solid colour'}),
        ('Actorsamples', 'Int', 256, {'min': 1, 'max': PTS_MAX, 'label': 'Actor effector samples'}),
        ('Pool', 'Float', 0.0, {'min': 0, 'max': 50, 'label': 'Pool % (ember points)'}),
        # wave 3 K19 / K28: any TOP of points (rgb = xyz, a > 0.5 valid) as a source (A / B / actor mode top): text,
        # logos and meshes through SOP / POP to TOP, BO_particles state, GEN_points, an animated character
        ('Pointstop', 'TOP', '', {'label': 'Points TOP (rgb xyz; else the in_xyz input)'}),
        # wave 4 K27: mode image = the Pointstop / in_xyz picture as a relief (2 units tall, aspect kept, x Ascale)
        ('Imagefile', 'File', '', {'label': 'Image file (when no Pointstop; image / top modes)'}),
        ('Imagerelief', 'Float', 0.4, {'min': -4, 'max': 4, 'label': 'Image relief height (x brightness)'}),
        ('Imagesrc', 'Menu', 'luma', {'names': names(IMGSRC), 'labels': labels(IMGSRC), 'label': 'Image height from'}),
        ('Imagecut', 'Float', 0.02, {'min': 0, 'max': 1, 'label': 'Image: drop pixels below (height source)'}),
        # actor echoes (wave 3, SA31 + TC-37): copies of the actor layer, each a snapshot N frames older
        ('Echoes', 'Int', 0, {'min': 0, 'max': 12, 'label': 'Actor echoes (copies, 0 = off)'}),
        ('Echoevery', 'Int', 6, {'min': 1, 'max': 60, 'label': 'Echo every N frames'}),
        ('Echofade', 'Float', 1.5, {'min': 0, 'max': 8, 'label': 'Echo fade (alpha gamma)'}),
        ('Echooffset', 'XYZ', (0.0, 0.0, 0.0), {'min': -2, 'max': 2, 'label': 'Echo offset per copy (stack / gravity)'}),
        # wave 4: echo cost = sprite fill; each older copy draws smaller and thinner (copy k: size Echoscale^k, keeps
        # (1 - Echothin)^k of its points), 6 echoes ~ 0.9 copies of fill instead of 6
        ('Echoscale', 'Float', 0.8, {'min': 0.1, 'max': 1, 'label': 'Echo size per copy (x, older = smaller)'}),
        ('Echothin', 'Float', 0.25, {'min': 0, 'max': 0.9, 'label': 'Echo thinning per copy (fraction dropped)'}),
    ]),
    ('Sim', [
        ('Play', 'Toggle', True, {}),
        ('Speed', 'Float', 1.0, {'min': 0, 'max': 4}),
        ('Reset', 'Pulse', None, {}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 100}),
        ('Spring', 'Float', 4.0, {'min': 0, 'max': 200, 'label': 'Spring to home'}),
        ('Damping', 'Float', 1.5, {'min': 0, 'max': 50}),
        ('Drag', 'Float', 0.2, {'min': 0, 'max': 20}),
        ('Maxspeed', 'Float', 0.0, {'min': 0, 'max': 200, 'label': 'Max speed (0 off)'}),
        ('Heatdecay', 'Float', 0.5, {'min': 0, 'max': 10}),
        ('Disrecover', 'Float', 1.0, {'min': 0, 'max': 20, 'label': 'Dissolve heal /s'}),  # 28 Oct, user: "dissolve doesnt come back"; 0 = sticky
        ('Statemode', 'Menu', 'feedback', {'names': ['feedback', 'inplace'], 'labels': ['Feedback TOP', 'In place (r/w)']}),
    ]),
    ('Look', [
        ('Size', 'Float', 0.01, {'min': 0.0005, 'max': 0.5, 'label': 'Point size (world)'}),
        ('Attenuation', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Size by depth'}),
        ('Minpx', 'Float', 0.7, {'min': 0, 'max': 8}),
        ('Maxpx', 'Float', 64.0, {'min': 1, 'max': 512}),
        ('Sprite', 'Menu', 'soft', {'names': names(SPRITES), 'labels': labels(SPRITES)}),
        ('Glyphmode', 'Menu', 'random', {'names': ['random', 'luma', 'time'],
                                         'labels': ['Random per point', 'By brightness (ascii art)', 'Cycling (Glyphrate)'],
                                         'label': 'Glyph / atlas cell'}),
        ('Glyphrate', 'Float', 2.0, {'min': 0, 'max': 30, 'label': 'Glyph cycle cells/s'}),
        ('Atlastop', 'TOP', '', {'label': 'Atlas TOP (white on black, square grid)'}),
        ('Atlascols', 'Int', 4, {'min': 1, 'max': 16, 'label': 'Atlas cells per row'}),
        ('Dabjitter', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Dab colour jitter'}),
        ('Softness', 'Float', 0.6, {'min': 0, 'max': 1}),
        ('Aspect', 'Float', 1.0, {'min': 0.1, 'max': 10}),
        ('Spin', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Sprite random spin'}),
        ('Streak', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Velocity streak'}),
        ('Streakmax', 'Float', 64.0, {'min': 0, 'max': 512, 'label': 'Streak max px'}),
        ('Blend', 'Menu', 'add', {'names': names(BLENDS), 'labels': labels(BLENDS)}),
        ('Hdr', 'Float', 1.0, {'min': 0, 'max': 20, 'label': 'HDR gain'}),
        ('Alpha', 'Float', 1.0, {'min': 0, 'max': 4}),
        ('Ptopacity', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Sprites: source opacity (splat scenes; 0 = opaque points)'}),
        ('Ptcut', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Sprites: hide below source opacity'}),
        ('Bright', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Colour gain (stage)'}),
        ('Focus', 'Float', 5.0, {'min': 0, 'max': 200}),
        ('Aperture', 'Float', 0.0, {'min': 0, 'max': 200, 'label': 'DOF aperture px'}),
        ('Maxcoc', 'Float', 48.0, {'min': 0, 'max': 200}),
        ('Bokehbright', 'Float', 1.0, {'min': 0, 'max': 8}),
        ('Bokehrim', 'Float', 0.5, {'min': 0, 'max': 1}),
        ('Minenergy', 'Float', 0.02, {'min': 0, 'max': 1}),
        ('Fog', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Depth fog'}),
        ('Disfade', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Dissolve fade'}),
        ('Dissize', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Dissolve size'}),
        ('Edgegain', 'Float', 2.0, {'min': 0, 'max': 20, 'label': 'Dissolve edge glow'}),
        ('Edgecol', 'RGB', (1.0, 0.5, 0.15), {'label': 'Edge colour'}),
        ('Camdist', 'Float', 4.0, {'min': 0.1, 'max': 100, 'label': 'Camera distance'}),
        ('Orbit', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Orbit deg/s'}),
        ('Camheight', 'Float', 0.0, {'min': -10, 'max': 10}),
        ('Fov', 'Float', 45.0, {'min': 5, 'max': 150}),
        ('Resolution', 'Menu', '1080x1920', {'names': names(RESOLUTIONS), 'labels': labels(RESOLUTIONS),
                                              'label': 'Render resolution'}),     # sets Resx / Resy (28 Oct)
        ('Resx', 'Int', 1080, {'min': 64, 'max': 7680}),
        ('Resy', 'Int', 1920, {'min': 64, 'max': 7680}),
        # splat render (S1-S6): the BL_splat_render shader on PX's state textures
        ('Render', 'Menu', 'auto', {'names': names(RENDERS), 'labels': labels(RENDERS)}),
        ('Splatthr', 'Float', 0.015, {'min': 0, 'max': 0.2, 'label': 'Splat alpha threshold'}),
        ('Splatlowpass', 'Float', 0.3, {'min': 0, 'max': 2, 'label': 'Splat low-pass px2'}),
        ('Splatscalemult', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Splat scale'}),
        ('Splatmaxpx', 'Float', 0.0, {'min': 0, 'max': 512, 'label': 'Splat max sigma px (0 off)'}),
        # perf wave 27 Oct (b3): MSAA on the splat render costs ~1.3-1.6 ms GPU at aa4 and changes nothing visible on
        # soft Gaussian splats (aa1 vs aa4 differs no more than two aa4 frames 3 s apart); aa4 and up one click away.
        ('Splataa', 'Menu', 'aa1', {'names': [a[0] for a in SPLAT_AA], 'labels': [a[1] for a in SPLAT_AA],
                                    'label': 'Splat antialias (MSAA)'}),
        ('Sortmode', 'Menu', 'auto', {'names': names(SORTMODES), 'labels': labels(SORTMODES)}),
        # 6 (was 2, perf wave 27 Oct): local module motion re-sorts ~10 / s at 60 fps; camera moves still re-sort at
        # Sortmaxhz through the camera gate; 1 = every frame
        ('Sorteveryn', 'Int', 6, {'min': 0, 'max': 60, 'label': 'Re-sort every N frames when centres move'}),
        ('Sortmovedeg', 'Float', 1.0, {'min': 0, 'max': 20, 'label': 'Re-sort after camera deg'}),
        ('Sortmaxhz', 'Float', 20.0, {'min': 0, 'max': 120, 'label': 'Max re-sorts per second (auto; 0 = no cap)'}),
        ('Sortnow', 'Pulse', None, {}),
    ]),
    ('Grade', [
        ('Exposure', 'Float', 0.0, {'min': -8, 'max': 8}),
        ('Tonemap', 'Menu', 'aces', {'names': names(TONEMAPS), 'labels': labels(TONEMAPS)}),
        ('Saturation', 'Float', 1.0, {'min': 0, 'max': 3}),
        ('Contrast', 'Float', 1.0, {'min': 0, 'max': 3}),
        ('Hue', 'Float', 0.0, {'min': -1, 'max': 1}),
        ('Tealorange', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Teal / orange macro'}),
        ('Split', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Split tone amount'}),
        ('Shadowtint', 'RGB', (0.05, 0.25, 0.30), {}),
        ('Hightint', 'RGB', (1.0, 0.55, 0.20), {}),
        ('Balance', 'Float', 0.35, {'min': 0, 'max': 1}),
        ('Lift', 'Float', 0.0, {'min': -0.5, 'max': 0.5}),
        ('Gamma', 'Float', 1.0, {'min': 0.2, 'max': 4}),
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 4}),
        ('Haze', 'Float', 0.0, {'min': 0, 'max': 1}),
        ('Hazecol', 'RGB', (0.06, 0.12, 0.14), {}),
        ('Chromatic', 'Float', 0.0, {'min': 0, 'max': 0.05}),
        ('Vignette', 'Float', 0.0, {'min': 0, 'max': 1}),
        ('Grain', 'Float', 0.0, {'min': 0, 'max': 0.2}),
        ('Bloom', 'Float', 0.0, {'min': 0, 'max': 8}),
        ('Bloomthr', 'Float', 0.8, {'min': 0, 'max': 8, 'label': 'Bloom threshold'}),
        ('Flare', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Lens flare (ghosts + streak)'}),
        ('Flarethr', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Flare threshold'}),
        ('Flarestreak', 'Float', 120.0, {'min': 0, 'max': 600, 'label': 'Flare streak px'}),
        ('Flareghosts', 'Int', 3, {'min': 0, 'max': 6}),
        ('Flaredisp', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Ghost spacing'}),
        ('Flaretint', 'RGB', (1.0, 0.75, 0.55), {}),
        ('Trails', 'Toggle', False, {}),
        ('Trailkeep', 'Float', 0.85, {'min': 0, 'max': 1}),
        # bloom v2 (W1-D px_bloom.glsl; defaults = the old px_glow exactly: one 1/8 scale, white)
        ('Bloomknee', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Bloom soft knee'}),
        ('Bloomtight', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Bloom tight scale (1/4 res; 0 = off)'}),
        ('Bloomtightspace', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Bloom tight tap spacing'}),
        ('Bloomclamp', 'Float', 0.0, {'min': 0, 'max': 20, 'label': 'Bloom firefly clamp (0 = off)'}),
        ('Bloomtint', 'RGB', (1.0, 1.0, 1.0), {}),
        ('Bloomsat', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Bloom saturation'}),
    ] + cs_pars('Bloom') + [
        ('Bloomring', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Bloom ring halo'}),
        ('Bloomringr', 'Float', 0.12, {'min': 0.01, 'max': 0.5, 'label': 'Ring radius (screen height)'}),
        ('Bloomringw', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Ring width'}),
        ('Bloomringchroma', 'Float', 0.0, {'min': 0, 'max': 0.5, 'label': 'Ring chroma'}),
    ]),
    ('Palette', [
        ('Palsource', 'Menu', 'neon_trio', {'names': names(PAL_SOURCES), 'labels': labels(PAL_SOURCES),
                                            'label': 'Palette'}),
        ('Palstops', 'Str', '#39FF14 0, #00F0FF 0.5, #FF00E6 1', {'label': 'Custom stops (hex [pos], ...)'}),
        ('Palfile', 'File', '', {'label': 'Palette file (.txt .hex .json .gpl .pal .ase)'}),
        ('Palmode', 'Menu', 'gradient', {'names': names(PAL_MODES), 'labels': labels(PAL_MODES)}),
        ('Palinterp', 'Menu', 'oklab', {'names': names(PAL_INTERP), 'labels': labels(PAL_INTERP)}),
        ('Palreverse', 'Toggle', False, {}),
        ('Palshift', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Shift (rotate; drive-able)'}),
        ('Paldrive', 'Menu', 'manual', {'names': names(PAL_DRIVES), 'labels': labels(PAL_DRIVES), 'label': 'Shift drive'}),
        ('Palevery', 'Float', 1.0, {'min': 0.25, 'max': 32, 'label': 'Beats per step / cycle'}),
        ('Palgain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Audio drive gain'}),
    ] + cs_pars('Edge') + cs_pars('Haze') + cs_pars('Flare') + cs_pars('Glow')),
    ('Lights', [
        ('Addltype', 'Menu', 'point', {'names': names(LTYPES), 'labels': labels(LTYPES), 'label': 'Light type'}),
        ('Addlcolour', 'RGB', (1.0, 1.0, 1.0), {'label': 'Light colour'}),
        ('Addlintensity', 'Float', 2.0, {'min': 0, 'max': 20, 'label': 'Light intensity'}),
        ('Addlpos', 'XYZ', (0.0, 1.5, 1.0), {'min': -10, 'max': 10, 'label': 'Light position'}),
        ('Addlight', 'Pulse', None, {'label': 'Add light to /project1/effectors'}),
        ('Lightinfo', 'Str', '', {'label': 'Lights (read only; light module + haze use them)'}),
    ]),
    ('Haze', [
        ('Vhon', 'Toggle', False, {'label': 'Volumetric haze + shafts'}),
        ('Vhamount', 'Float', 1.0, {'min': 0, 'max': 1}),
        ('Vhres', 'Menu', 'quarter', {'names': ['quarter', 'half'], 'labels': ['Quarter res', 'Half res (~4x cost)']}),
        ('Vhlights', 'Str', 'all', {'label': 'Lights (all / #tag / names; max 8)', 'menu': True}),
        ('Vhdensity', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Density'}),
        ('Vhfloor', 'Float', 0.0, {'min': -5, 'max': 5, 'label': 'Floor height (y)'}),
        ('Vhfalloff', 'Float', 0.35, {'min': 0, 'max': 4, 'label': 'Height falloff'}),
        ('Vhnoise', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Patchiness'}),
        ('Vhnoisescale', 'Float', 0.35, {'min': 0.01, 'max': 4}),
        ('Vhwind', 'XYZ', (0.3, 0.05, 0.1), {'min': -2, 'max': 2, 'label': 'Drift (units/s)'}),
        ('Vhextinction', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Extinction (dims the scene)'}),
        ('Vhambient', 'Float', 0.25, {'min': 0, 'max': 4, 'label': 'Ambient haze'}),
        ('Vhcol', 'RGB', (0.55, 0.6, 0.7), {'label': 'Haze colour'}),
    ] + cs_pars('Vh', 'source') + [
        ('Vhtint', 'RGB', (1.0, 1.0, 1.0), {'label': 'Lit fog tint'}),
        ('Vhgain', 'Float', 1.0, {'min': 0, 'max': 20, 'label': 'Lit fog gain'}),
        ('Vhg', 'Float', 0.35, {'min': -0.9, 'max': 0.9, 'label': 'Forward scatter (g)'}),
        ('Vhsteps', 'Int', 8, {'min': 1, 'max': 32}),
        ('Vhsoft', 'Float', 0.05, {'min': 0.001, 'max': 1, 'label': 'Light size'}),
        ('Vhshafts', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Shafts (0 = off)'}),
        ('Vhdecay', 'Float', 0.96, {'min': 0.5, 'max': 1}),
        ('Vhlength', 'Float', 0.85, {'min': 0, 'max': 1}),
        ('Vhtaps', 'Int', 12, {'min': 1, 'max': 64}),
        ('Vhthreshold', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Bright pixels emit shafts (0 = off)'}),
        ('Vhdisc', 'Float', 0.06, {'min': 0.001, 'max': 0.5, 'label': 'Light disc'}),
        ('Vhocclusion', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Scene blocks shafts'}),
        ('Vhshaftlod', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Shaft mip (perf)'}),
        ('Vhobjdist', 'Float', 6.0, {'min': 0, 'max': 100, 'label': 'Object distance (covered pixels)'}),
        ('Vhmaxdist', 'Float', 60.0, {'min': 1, 'max': 500, 'label': 'Max distance (sky)'}),
    ]),
    ('Geo', [
        ('Geoon', 'Toggle', False, {'label': 'Geometry in the scene (occludes both ways)'}),
        ('Geocomps', 'Str', '', {'label': 'Geometry COMPs (paths / patterns)'}),
        ('Geolights', 'Str', '#light', {'label': 'Lights (paths, #tag; #light = all in /project1/effectors)',
                                        'menu': True}),
        ('Geokey', 'Toggle', True, {'label': 'Built-in key light'}),
        ('Geodepthbias', 'Float', 0.0, {'min': -0.5, 'max': 0.5, 'label': 'Splat depth bias (world)'}),
        ('Geoaddkind', 'Menu', 'sphere', {'names': names(GEO_KINDS), 'labels': labels(GEO_KINDS), 'label': 'Add kind'}),
        ('Geoaddcolour', 'RGB', (0.8, 0.8, 0.85), {'label': 'Add: base colour'}),
        ('Geoaddmetal', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Add: metallic'}),
        ('Geoaddrough', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Add: roughness'}),
        ('Geoaddemit', 'Float', 0.0, {'min': 0, 'max': 20, 'label': 'Add: emission (blooms)'}),
        ('Geoadd', 'Pulse', None, {'label': 'Add geometry object (geo/)'}),
        # wave 4 GE3: chrome objects reflect the scene (a low-res cube of the decimated preview, every N frames)
        ('Geoenv', 'Toggle', False, {'label': 'Scene reflections (chrome; env capture)'}),
        ('Geoenvres', 'Int', 128, {'min': 16, 'max': 1024, 'label': 'Environment cube px'}),
        ('Geoenveveryn', 'Int', 4, {'min': 1, 'max': 30, 'label': 'Environment every N frames'}),
        ('Geoenvdimmer', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Environment dimmer'}),
        ('Geoenvcentre', 'XYZ', (0.0, 0.0, 0.0), {'min': -10, 'max': 10, 'label': 'Environment centre (the chrome object)'}),
    ]),
    ('Camera', [
        # phase C (28 Oct) Usecam: PX's own pose (pcam + every projection / sort / lines / haze uniform) follows any
        # Camera COMP (e.g. /project1/lab/CS_cam_sequencer/cam_out); internal = the orbit / rig below, as before
        ('Camsource', 'Menu', 'internal', {'names': names(CAMSOURCES), 'labels': labels(CAMSOURCES),
                                           'label': 'Camera source'}),
        ('Camcomp', 'Str', '', {'label': 'External Camera COMP (pick)', 'menu': True}),
        ('Cammode', 'Menu', 'orbit', {'names': names(CAM_MODES), 'labels': labels(CAM_MODES), 'label': 'Camera rig'}),
        ('Camtarget', 'XYZ', (0.0, 0.0, 0.0), {'min': -20, 'max': 20, 'label': 'Target / crane base'}),
        ('Camheading', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Crane heading deg'}),
        ('Campitch', 'Float', 20.0, {'min': -89, 'max': 89, 'label': 'Crane pitch deg'}),
        ('Camlength', 'Float', 4.0, {'min': 0.1, 'max': 50, 'label': 'Crane arm length'}),
        ('Camheadspeed', 'Float', 10.0, {'min': -180, 'max': 180, 'label': 'Crane heading deg/s'}),
        ('Campitchamp', 'Float', 0.0, {'min': 0, 'max': 80, 'label': 'Crane pitch swing deg'}),
        ('Campitchfreq', 'Float', 0.1, {'min': 0, 'max': 2, 'label': 'Crane swing Hz'}),
        ('Camdollya', 'XYZ', (0.0, 0.5, 6.0), {'min': -50, 'max': 50, 'label': 'Dolly from'}),
        ('Camdollyb', 'XYZ', (0.0, 0.5, 2.0), {'min': -50, 'max': 50, 'label': 'Dolly to'}),
        ('Camdollysec', 'Float', 10.0, {'min': 0.5, 'max': 120, 'label': 'Dolly seconds (ping-pong)'}),
        ('Campoints', 'Str', '-3 0.5 4; 0 1.5 3; 3 0.5 4; 0 0.3 6', {'label': 'Path points (x y z; ...)'}),
        ('Campathsec', 'Float', 20.0, {'min': 1, 'max': 300, 'label': 'Path seconds per loop'}),
        ('Camfollow', 'Str', '', {'label': 'Follow effector (name)', 'menu': True}),
        ('Camoffset', 'XYZ', (0.0, 1.0, 4.0), {'min': -20, 'max': 20, 'label': 'Follow offset'}),
        ('Camlag', 'Float', 0.4, {'min': 0, 'max': 5, 'label': 'Follow lag s'}),
        ('Camshots', 'Str', 'crane:8 orbit:8 dolly:4 path:8', {'label': 'Director shots (rig:beats ...)'}),
        ('Camdirmode', 'Menu', 'random', {'names': ['list', 'random'], 'labels': ['In order', 'Random (no repeat)']}),
        ('Camquant', 'Float', 4.0, {'min': 0, 'max': 16, 'label': 'Cut on multiples of N beats'}),
        ('Camtrans', 'Menu', 'cut', {'names': ['cut', 'ease', 'arc'], 'labels': ['Cut', 'Ease', 'Arc (swing round)']}),
        ('Camtdur', 'Float', 1.0, {'min': 0, 'max': 16, 'label': 'Transition beats'}),
        ('Camseed', 'Int', 1, {'min': 0, 'max': 999}),
        ('Camroll', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Roll deg'}),
        ('Camshake', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Shake (units)'}),
        ('Camshakerot', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Shake rotation deg'}),
        ('Camshakefreq', 'Float', 6.0, {'min': 0, 'max': 30, 'label': 'Shake Hz'}),
    ]),
    ('Grid', [                                       # wave 3 SA5 / SA21: the shared voxel grid (/project1/effectors)
        ('Hotthr', 'Float', 0.3, {'min': 0, 'max': 5, 'label': 'Hot point: heat above'}),
        ('Hotemit', 'Float', 0.0, {'min': 0, 'max': 20, 'label': 'Hot point: colour luma above (0 = heat only)'}),
        ('Hotmax', 'Int', 4096, {'min': 64, 'max': 65536, 'label': 'Hot points sampled (grid cloud size)'}),
        ('Gridfit', 'Toggle', True, {'label': 'Fit the shared grid around this scene (when PX turns it on)'}),
    ]),
    ('Output', [                                     # wave 4 K26: dome / 360 output (sprites + splats rendered as a
        # cube map of Projface per face, then a Projection TOP to fisheye / equirect at Resx x Resy (equirect 2:1);
        # Geo / Lines / Haze stay perspective-only (they composite on the 2D image)
        ('Proj', 'Menu', 'perspective', {'names': ['perspective', 'fisheye', 'equirect'],
                                         'labels': ['Perspective (camera Fov)', 'Fisheye / dome (Projfov)',
                                                    'Equirectangular 360 (Resx = 2 x Resy)'], 'label': 'Projection'}),
        ('Projface', 'Int', 1024, {'min': 128, 'max': 4096, 'label': 'Cube face size (px)'}),
        ('Projfov', 'Float', 180.0, {'min': 30, 'max': 360, 'label': 'Fisheye angle deg'}),
        ('Projtilt', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Dome tilt deg (x)'}),
    ]),
    ('Perf', [                                       # phase C (28 Oct): speed levers; manual wins (auto is a layer)
        ('Autoquality', 'Menu', 'off', {'names': names(AUTOQ), 'labels': labels(AUTOQ), 'label': 'Auto quality'}),
        ('Govop', 'Str', GOV_DEFAULT, {'label': 'Governor CHOP (Autoquality governor; quality 1 = full)'}),
        ('Aqfps', 'Float', 57.0, {'min': 20, 'max': 60, 'label': 'Auto: step down under fps'}),
        ('Aqframes', 'Int', 45, {'min': 5, 'max': 600, 'label': 'Auto: frames under before a step'}),
        ('Aqheadroom', 'Float', 10.0, {'min': 1, 'max': 16, 'label': 'Auto: step up when frame ms under'}),
        ('Aqstate', 'Str', 'off', {'label': 'Auto quality now (read only)', 'readonly': True}),
        ('Sortstill', 'Toggle', True, {'label': 'Skip re-sorts while nothing moves (Sortmode auto)'}),
        ('Lod', 'Toggle', False, {'label': 'LOD: fewer, bigger splats / points far away'}),
        ('Loddist', 'Float', 6.0, {'min': 0.1, 'max': 100, 'label': 'LOD starts at camera distance (full at 2x)'}),
        ('Lodkeep', 'Float', 0.35, {'min': 0.05, 'max': 1, 'label': 'LOD: share kept far away'}),
    ]),
    ('Sound', [                                      # wave 4 K34: the cloud's motion as sound (OFF by default; the
        # default output device = the built-in speakers; no input device is ever used, nothing routes a mic out)
        ('Soundon', 'Toggle', False, {'label': 'Sound on (Audio Device Out, default output)'}),
        ('Soundvol', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Volume'}),
        ('Soundpitch', 'Float', 1.0, {'min': 0.25, 'max': 4, 'label': 'Pitch (x)'}),
        ('Sounddrone', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Drone (pitch = mean height, fades as it dissolves)'}),
        ('Soundshimmer', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Shimmer (pitch + level = mean speed)'}),
        ('Soundnoise', 'Float', 0.3, {'min': 0, 'max': 2, 'label': 'Noise (level = dissolved fraction)'}),
        ('Soundspeed', 'Float', 2.0, {'min': 0.01, 'max': 50, 'label': 'Speed for full shimmer (units / s)'}),
    ]),
    ('Lines', [
        ('Lineson', 'Toggle', False, {'label': 'Lines layer (PX_lines inside; its page: Opencontrols there)'}),
        ('Linesdepth', 'Toggle', False, {'label': 'Lines hidden behind geometry (Geo depth)'}),
    ]),
    ('Drive', [
        ('Audiochop', 'CHOP', '', {'label': 'Audio CHOP (low mid high level s0..s15)'}),
        # wave 4 K33: any control CHOP (OSC In / MIDI In / a fader bank): every channel is a drive source by name
        # (characters outside A-Z a-z 0-9 _ become _, e.g. OSC '1/fader1' -> 1_fader1)
        ('Drivechop', 'CHOP', '', {'label': 'Control CHOP (OSC / MIDI): channels as drive sources'}),
        ('Tempo', 'Menu', 'project', {'names': ['project', 'manual'], 'labels': ['Project tempo', 'Bpm par']}),
        ('Bpm', 'Float', 120.0, {'min': 20, 'max': 240}),
        ('Beatdecay', 'Float', 6.0, {'min': 0, 'max': 30}),
        ('Trig1', 'Pulse', None, {}), ('Trig2', 'Pulse', None, {}), ('Trig3', 'Pulse', None, {}), ('Trig4', 'Pulse', None, {}),
        ('Trigdecay', 'Float', 2.0, {'min': 0, 'max': 20}),
        # 28 Oct: trigger looks (Radial blast...) sit still until a Trig pulse; Trigauto fires by itself every N s
        ('Trigauto', 'Float', 0.0, {'min': 0, 'max': 16, 'label': 'Auto trigger every N s (0 off)'}),
        ('Trigautowhich', 'Menu', 'all', {'names': ['all', 'trig1', 'trig2', 'trig3', 'trig4'],
                                          'labels': ['All four', 'Trig 1', 'Trig 2', 'Trig 3', 'Trig 4'],
                                          'label': 'Auto trigger fires'}),
        # 28 Oct phase A (beat sync): triggers on the beat / onsets; the same Trigautowhich picks which ones fire
        ('Trigsource', 'Menu', 'manual', {'names': names(TRIG_SOURCES), 'labels': labels(TRIG_SOURCES),
                                          'label': 'Trigger source'}),
        ('Trigbeats', 'Int', 4, {'min': 1, 'max': 16, 'label': 'Every N beats (Trigsource)'}),
        ('Audiosrc', 'COMP', AUDIO_DEFAULT, {'label': 'Audio features COMP (AU_features; empty = off)'}),
        ('Beatsync', 'Toggle', False, {'label': 'Beat sync (beat / tempo / triggers / transitions follow the audio)'}),
        ('Lfo1rate', 'Float', 0.25, {'min': 0, 'max': 10}),
        ('Lfo2rate', 'Float', 1.0, {'min': 0, 'max': 10}),
        ('Lfoshape', 'Menu', 'sine', {'names': ['sine', 'tri', 'saw', 'square'], 'labels': ['Sine', 'Triangle', 'Saw', 'Square']}),
    ]),
    ('Stack', [
        # phase B: a browser dropdown (category > name - what it does), was a static Menu; the value = the type
        ('Addtype', 'Str', 'prox_push', {'label': 'Module type (browser)', 'menu': True}),
        ('Add', 'Pulse', None, {'label': 'Add module'}),
        ('Addafter', 'Toggle', False, {'label': 'Add after the selected module (off = at the end)'}),
        ('Sel', 'Str', '1', {'label': 'Selected module (uid)', 'menu': True}),     # was Int (dropdowns, T-233)
        ('Remove', 'Pulse', None, {}), ('Duplicate', 'Pulse', None, {}), ('Moveup', 'Pulse', None, {}),
        ('Movedown', 'Pulse', None, {}), ('Toggleon', 'Pulse', None, {'label': 'Enable / disable (bypass)'}),
        ('Solo', 'Pulse', None, {'label': 'Solo the selected module (only it runs)'}),
        ('Unsolo', 'Pulse', None, {'label': 'Unsolo (the enabled set comes back)'}),
        ('Effkind', 'Menu', 'box', {'names': names(EFF_KINDS), 'labels': labels(EFF_KINDS), 'label': 'Effector kind'}),
        ('Addeffector', 'Pulse', None, {'label': 'Add effector object'}),
        ('Effname', 'Str', '', {'label': 'Effector to remove', 'menu': True}),
        ('Removeeffector', 'Pulse', None, {}),
        ('Status', 'Str', '', {'label': 'Status (read only)'}),
    ]),
    ('Presets', [
        ('Presetname', 'Str', 'look1', {'label': 'Preset name (pick, or type a new one)', 'menu': True}),
        ('Store', 'Pulse', None, {}), ('Recall', 'Pulse', None, {}), ('Deletepreset', 'Pulse', None, {}),
        # 28 Oct (user): a preset must not replace the imported cloud / splat. Off = Recall / Morphto / setlist skip
        # the Source page (files, modes, generators, counts, load pars) + Camsource / Camcomp; Store still records them
        ('Presetsource', 'Toggle', False, {'label': 'Presets change the source'}),
        ('Morphto', 'Pulse', None, {'label': 'Morph to preset'}),
        ('Presetup', 'Pulse', None, {'label': 'Move preset up'}), ('Presetdown', 'Pulse', None, {'label': 'Move preset down'}),
        ('Newname', 'Str', '', {'label': 'New name (for Rename)'}), ('Presetrename', 'Pulse', None, {'label': 'Rename preset'}),
        ('Presetsort', 'Pulse', None, {'label': 'Sort presets A-Z (built-ins first)'}),
        ('Morphtime', 'Float', 4.0, {'min': 0, 'max': 60, 'label': 'Morph seconds'}),
        ('Morphcurve', 'Menu', 'smooth', {'names': ['linear', 'ease', 'smooth'], 'labels': ['Linear', 'Ease', 'Smooth']}),
        ('Stopmorph', 'Pulse', None, {}),
        # 28 Oct phase A: the presets as a setlist (names only; px_setlist empty = presets order)
        ('Next', 'Pulse', None, {'label': 'Setlist: next scene'}), ('Prev', 'Pulse', None, {'label': 'Setlist: previous scene'}),
        ('Cue', 'Str', '', {'label': 'Setlist scene (pick, then Go)', 'menu': True}),
        ('Go', 'Pulse', None, {'label': 'Setlist: go to the scene'}),
        ('Transition', 'Float', 2.0, {'min': 0, 'max': 32, 'label': 'Transition (s; beats with Beat sync; 0 = cut)'}),
        ('Transcurve', 'Menu', 'ease', {'names': names(TRANSCURVES), 'labels': labels(TRANSCURVES),
                                        'label': 'Transition curve'}),
        ('Current', 'Str', '-', {'label': 'Current scene (read only)', 'readonly': True}),
        ('Cueindex', 'Int', 0, {'min': 0, 'max': 64, 'label': 'Go to scene # (CQ / TL hook; 0 = none)'}),
        # './x' = a child of PX; a bare 'x' resolves next to PX (a sibling) on 31550 (T-244)
        ('Setlist', 'DAT', './px_setlist', {'label': 'Setlist table (empty = presets order)'}),
        ('Setlistfill', 'Pulse', None, {'label': 'Fill setlist with the presets order'}),
        ('Preview', 'Toggle', True, {'label': 'Gizmo preview on'}),
        ('Previewcount', 'Int', 65536, {'min': 1024, 'max': 1048576}),
        ('Opencontrols', 'Pulse', None, {}),
    ]),
]
CORE_PAGE_NAMES = [pg for pg, _ in CORE_PAGES]
PANEL_CORE_PAGES = ['Look', 'Source', 'Sim', 'Grade', 'Palette', 'Lights', 'Haze', 'Geo', 'Lines', 'Camera', 'Grid', 'Output', 'Sound',
                    'Perf', 'Drive', 'Stack', 'Presets']
NEW_PAGES = ('Palette', 'Lights', 'Haze', 'Geo', 'Lines', 'Camera', 'Grid', 'Output', 'Sound')   # wave 2-4: off by default = the v2 look


def quality_count(raw):
    """Points of the Quality / Count pars, clamped to COUNT_MAX (phase B: no par value makes a texture past TEX_MAX)."""
    q = raw.get('Quality', 'std')
    for k, _l, n in QUALITY:
        if k == q and n:
            return clamp_count(n)
    return clamp_count(max(int(raw.get('Count', 131072)), 1))


def count_from_pars(quality, count):
    return quality_count({'Quality': quality, 'Count': count})


def side_from_pars(quality, count):
    """For TOP resolution expressions: side of the square point grid."""
    return side_for(count_from_pars(quality, count))


def side_for(n):
    s = int(math.ceil(math.sqrt(max(int(n), 1))))
    while s * s < n:
        s += 1
    return s


def tex_sizes(n):
    s = side_for(n)
    return {'side': s, 'state': (STATE_TEXELS * s, s), 'rest': (REST_TEXELS * s, s), 'look': (LOOK_TEXELS * s, s)}


def layers(raw, n=None):
    """Id ranges inside Count: scene [0, ns), actor [ns, ns + na), pool [ns + na, ns + na + np), echoes (wave 3,
    SA31) after the pool (echo_count). -> (ns, na, np). The actor takes Actorcount (0 when Actormode is off), the pool
    Pool % of Count; the scene keeps >= 1 point."""
    n = quality_count(raw) if n is None else int(n)
    na = max(int(raw.get('Actorcount', 0)), 0) if raw.get('Actormode', 'off') != 'off' else 0
    npool = int(round(n * max(float(raw.get('Pool', 0.0)), 0.0) / 100.0))
    na = min(na, max(n - 1, 0))
    npool = min(npool, max(n - 1 - na, 0))
    ne = min(echo_count(raw, na), max(n - 1 - na - npool, 0))
    return n - na - npool - ne, na, npool


def echo_count(raw, na):
    """Echo ids (SA31 / TC-37): Echoes copies of the actor layer (0 = off, or no actor)."""
    return max(int(raw.get('Echoes', 0)), 0) * int(na)


def render_mode(raw, is_splat_file=False):
    """'splats' or 'sprites' (Render auto: splats when the A file is a Gaussian splat file)."""
    r = raw.get('Render', 'auto')
    if r == 'auto':
        return 'splats' if is_splat_file else 'sprites'
    return 'splats' if r == 'splats' else 'sprites'


def sprite_range(mode, ns, na, npool, ne=0):
    """(first id, count) of the instanced sprite render: every point, or the pool (+ actor echoes) only under splats
    (S5: embers stay point sprites, the splat render draws scene + actor)."""
    if mode == 'splats':
        return ns + na, npool + ne
    return 0, ns + na + npool + ne


def render_rows(raw, side, count, resx=None, resy=None, first=0, end=None, echo=None):
    """uR rows of the sprite render. Row 8 (wave 4): echo copies (first echo id or -1, actor count, size per copy,
    thinning per copy); echo = (first echo id, actor count) or None (no echoes)."""
    rv = lambda k, d: float(raw.get(k, d))
    return [
        [rv('Size', 0.01), rv('Attenuation', 1.0), rv('Minpx', 0.7), rv('Maxpx', 64.0)],
        [float(menu_index(SPRITES, raw.get('Sprite', 'soft'))), rv('Softness', 0.6), rv('Aspect', 1.0), rv('Spin', 0.0)],
        [rv('Streak', 0.0), rv('Streakmax', 64.0), rv('Ptcut', 0.08), rv('Hdr', 1.0)],
        [rv('Focus', 5.0), rv('Aperture', 0.0), rv('Maxcoc', 48.0), rv('Bokehbright', 1.0)],
        [float(resx if resx is not None else raw.get('Resx', 1080)), float(resy if resy is not None else raw.get('Resy', 1920)),
         float(side), float(count)],
        [rv('Alpha', 1.0), 1.0 if _truthy(raw.get('Splatscale', False)) else 0.0, rv('Splatk', 3.0), rv('Ptopacity', 0.0)],
        [rv('Bokehrim', 0.5), rv('Minenergy', 0.02), rv('Fog', 0.0), rv('Dabjitter', 1.0)],
        [float(first), float(count if end is None else end), float(menu_index([('random', ''), ('luma', ''), ('time', '')],
                                                                              raw.get('Glyphmode', 'random'))),
         float(raw.get('Atlascols', 4))],
        [float(echo[0]) if echo else -1.0, float(echo[1]) if echo else 0.0, rv('Echoscale', 0.8), rv('Echothin', 0.25)],
        lod_row(raw),                                 # row 9 (phase C): LOD by camera distance (x 0 = off)
    ]


def proj_res(raw):
    """K26: (resx, resy) of the renders: the cube face size while Proj is fisheye / equirect, else Resx x Resy."""
    if raw.get('Proj', 'perspective') != 'perspective':
        f = float(min(int(raw.get('Projface', 1024)), CUBE_MAX))
        return f, f
    w, h = eff_res(raw.get('Resx', 1080), raw.get('Resy', 1920))     # phase B: the clamped render size
    return float(w), float(h)


def splat_rows(raw, count, resx=None, resy=None, ns=None, na=0, sortoff=False):
    """The reused BL_splat_render shader's uniforms (uRes, uP1..uP6, in its own meaning) + PX's uSp[4]:
    -> (vec rows (7), sp rows (4)). uRes.z = 0 (no order texture: the Sort POP order comes as the instance custom
    attribute pid), dissolve / noise / explode / reveal / SH off (PX's modules do those), point mix 0.
    uSp: 0 (side, count, ns + na (draw end), sort off), 1 (Focus, Aperture, Maxcoc, Minenergy) for splat DOF (S6),
    2 (Bokehrim, Bokehbright, Fog, Size), 3 (Splatscale on, Splatk, Splatmaxpx (footprint cap, 0 off), Ascale (file
    splat scales follow the scene scale, 27 Oct))."""
    rv = lambda k, d: float(raw.get(k, d))
    side = side_for(count)
    ns = count if ns is None else ns
    vec = [
        [float(resx if resx is not None else raw.get('Resx', 1080)), float(resy if resy is not None else raw.get('Resy', 1920)),
         0.0, float(count)],
        [rv('Splatscalemult', 1.0), rv('Alpha', 1.0), rv('Splatthr', 0.015), rv('Splatlowpass', 0.3)],
        [0.0, 3.0, 1.0, 1.0],
        [0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0],
    ]
    sp = [
        [float(side), float(count), float(ns + na), 1.0 if sortoff else 0.0],
        [rv('Focus', 5.0), rv('Aperture', 0.0), rv('Maxcoc', 48.0), rv('Minenergy', 0.02)],
        [rv('Bokehrim', 0.5), rv('Bokehbright', 1.0), rv('Fog', 0.0), rv('Size', 0.01)],
        [1.0 if _truthy(raw.get('Splatscale', False)) else 0.0, rv('Splatk', 3.0), rv('Splatmaxpx', 0.0),
         rv('Ascale', 1.0)],
        lod_row(raw),                                 # row 4 (phase C): LOD by camera distance (x 0 = off)
    ]
    return vec, sp


TEAL = (0.05, 0.25, 0.30)
ORANGE = (1.0, 0.55, 0.20)


def post_rows(raw, frame=0):
    rv = lambda k, d: float(raw.get(k, d))
    to = rv('Tealorange', 0.0)
    sh = [float(raw.get('Shadowtintr', 0.05)), float(raw.get('Shadowtintg', 0.25)), float(raw.get('Shadowtintb', 0.30))]
    hi = [float(raw.get('Hightintr', 1.0)), float(raw.get('Hightintg', 0.55)), float(raw.get('Hightintb', 0.20))]
    k = max(0.0, min(1.0, to))
    sh = [a + (b - a) * k for a, b in zip(sh, TEAL)]
    hi = [a + (b - a) * k for a, b in zip(hi, ORANGE)]
    return [
        [rv('Exposure', 0.0), float(menu_index(TONEMAPS, raw.get('Tonemap', 'aces'))), rv('Saturation', 1.0), rv('Contrast', 1.0)],
        sh + [rv('Split', 0.0)],
        hi + [rv('Balance', 0.35)],
        [rv('Lift', 0.0), rv('Gamma', 1.0), rv('Gain', 1.0), to],
        [rv('Vignette', 0.0), rv('Grain', 0.0), float(frame % 65536), rv('Hue', 0.0)],
        [float(raw.get('Hazecolr', 0.06)), float(raw.get('Hazecolg', 0.12)), float(raw.get('Hazecolb', 0.14)), rv('Haze', 0.0)],
        [rv('Chromatic', 0.0), rv('Flare', 0.0), rv('Flarethr', 1.5), rv('Flarestreak', 120.0)],
        [rv('Flareghosts', 3), rv('Flaredisp', 0.35), 0.0, 0.0],
        [float(raw.get('Flaretintr', 1.0)), float(raw.get('Flaretintg', 0.75)), float(raw.get('Flaretintb', 0.55)), 0.0],
        [0.0, 0.0, 0.0, 0.0],
    ]


def source_rows(raw, side, count, spin_a=0.0, spin_b=0.0, depth_aspect=1.0, spin_actor=0.0, actor_offset=None):
    """uSrc[SRC_ROWS]. Rows 12..16 = actor layer: (mode, generator, count, its side), (gen p1 p2 p3, spin angle),
    (scale, rotate y rad, 0, colour mode), (offset xyz incl. follow, 0), (solid colour rgb, 0). File sides A / B sit
    stacked in ONE rest image (rest_files: A rows 0..side-1, B rows side..2 side-1); the actor's own file / frame is
    input 1 (rest_actor)."""
    rv = lambda k, d: float(raw.get(k, d))
    ma = menu_index(SOURCEMODES, raw.get('Amode', 'gen'))
    mb = menu_index(SOURCEMODES, raw.get('Bmode', 'off'))
    _ns, na, _np_ = layers(raw, count)
    am = menu_index(ACTORMODES, raw.get('Actormode', 'off'))
    off = actor_offset if actor_offset is not None else (rv('Actoroffsetx', 0.0), rv('Actoroffsety', 0.0),
                                                         rv('Actoroffsetz', 0.0))
    return [
        [float(ma), float(mb), rv('Morph', 0.0), float(side)],
        [float(menu_index(GENERATORS, raw.get('Agen', 'sphere'))), float(menu_index(GENERATORS, raw.get('Bgen', 'torus'))),
         float(count), rv('Seed', 1)],
        [rv('Stagger', 0.5), float(menu_index(STAGGERS, raw.get('Staggermode', 'random'))), rv('Arc', 0.3),
         float(menu_index(EASES, raw.get('Ease', 'smooth')))],
        [rv('Ascale', 1.0), rv('Bscale', 1.0), math.radians(rv('Arot', 0.0)), math.radians(rv('Brot', 0.0))],
        [rv('Aoffsetx', 0.0), rv('Aoffsety', 0.0), rv('Aoffsetz', 0.0), float(menu_index(COLMODES, raw.get('Acolmode', 'position')))],
        [rv('Boffsetx', 0.0), rv('Boffsety', 0.0), rv('Boffsetz', 0.0), float(menu_index(COLMODES, raw.get('Bcolmode', 'position')))],
        [rv('Depthfov', 60.0), rv('Depthnear', 1.0), rv('Depthfar', 4.0), rv('Depththr', 0.02)],
        [float(depth_aspect), rv('Depthscale', 1.0), 1.0 if _truthy(raw.get('Depthmirror', True)) else 0.0, rv('Depthgain', 1.0)],
        [rv('Agenp', 1.0), rv('Agenp2', 0.3), rv('Agenp3', 0.0), float(spin_a)],
        [rv('Bgenp', 1.0), rv('Bgenp2', 0.3), rv('Bgenp3', 0.0), float(spin_b)],
        [rv('Acolourr', 1.0), rv('Acolourg', 1.0), rv('Acolourb', 1.0), 0.0],
        [rv('Bcolourr', 1.0), rv('Bcolourg', 0.5), rv('Bcolourb', 0.2), 0.0],
        [float(am), float(menu_index(GENERATORS, raw.get('Actorgen', 'cylinder'))), float(na), float(side_for(max(na, 1)))],
        [rv('Actorgenp', 0.9), rv('Actorgenp2', 0.3), rv('Actorgenp3', 0.0), float(spin_actor)],
        [rv('Actorscale', 1.0), math.radians(rv('Actorrot', 0.0)), 0.0,
         float(menu_index(COLMODES, raw.get('Actorcolmode', 'solid')))],
        [float(off[0]), float(off[1]), float(off[2]), 0.0],
        [rv('Actorcolourr', 1.0), rv('Actorcolourg', 0.9), rv('Actorcolourb', 0.8), 0.0],
        [rv('Imagerelief', 0.4), float(menu_index(IMGSRC, raw.get('Imagesrc', 'luma'))), rv('Imagecut', 0.02), 0.0],
    ]


def flat_core_defaults():
    d = {}
    for _pg, pars in CORE_PAGES:
        for name, style, default, _o in pars:
            if style in ('XYZ', 'RGB'):
                for suf, v in zip('xyz' if style == 'XYZ' else 'rgb', default):
                    d[name + suf] = v
            elif style not in ('Pulse',):
                d[name] = default
    return d


def gen_bounds(kind, p1, p2=0.3):
    """(centre, radius) of a generator (for uG[7] before any file is loaded)."""
    if kind == 'torus':
        return (0.0, 0.0, 0.0), abs(p1) + abs(p2)
    if kind in ('grid', 'cube'):
        return (0.0, 0.0, 0.0), abs(p1) * math.sqrt(3.0)
    if kind in ('plane',):
        return (0.0, 0.0, 0.0), abs(p1) * math.sqrt(2.0)
    if kind in ('ring',):
        return (0.0, 0.0, 0.0), abs(p1) + abs(p2)
    return (0.0, 0.0, 0.0), abs(p1)


def place_bounds(bb, scale=1.0, rot_deg=0.0, offset=(0.0, 0.0, 0.0)):
    """(centre, radius) of source A in file/generator space -> where px_source.glsl puts it (p * scale, rotate y,
    + offset), so BBC / BBR (uG[7]) match the points the modules see. Live bug before this: the bounds stayed in file
    space, so a scan moved by Aoffset dissolved from a centre 2 units away."""
    (cx, cy, cz), r = bb
    s = float(scale)
    a = math.radians(float(rot_deg))
    ca, sa = math.cos(a), math.sin(a)
    x, y, z = cx * s, cy * s, cz * s
    return ((ca * x + sa * z + float(offset[0]), y + float(offset[1]), -sa * x + ca * z + float(offset[2])), abs(s) * float(r))


# ----------------------------------------------------------------------------------------------- wave 2: palette, colour
# sources, haze (27 Oct 2026; docs/builds/px.md "Wave 2"). palette_map_logic (W1-B) lives in the COMP as `px_palmap`;
# these helpers take its functions as arguments so px_logic stays import-free.

def palette_spec(raw):
    """Palette page -> (spec for palette_map_logic.palette_stops, custom rows (Palstops 'hex [pos], ...'))."""
    spec = {'source': raw.get('Palsource', 'neon_trio'), 'mode': raw.get('Palmode', 'gradient'),
            'reverse': _truthy(raw.get('Palreverse', False))}
    rows = []
    for item in str(raw.get('Palstops', '') or '').split(','):
        w = item.split()
        if w:
            rows.append(w[:2])
    return spec, rows


def pal_drive(raw):
    """Palette page -> palette_map_logic.pal_shift drive dict."""
    return {'kind': raw.get('Paldrive', 'manual'), 'every': float(raw.get('Palevery', 1.0)),
            'gain': float(raw.get('Palgain', 1.0)), 'step': 1.0}


SCALAR_CS = (('Edge', 'Edgecol', (1.0, 0.5, 0.15)), ('Haze', 'Hazecol', (0.06, 0.12, 0.14)),
             ('Flare', 'Flaretint', (1.0, 0.75, 0.55)))


def scalar_colours(raw, colsrc_eval, pal_rows, pal_ctl):
    """Colours of the one-colour elements (Look Edgecol, Grade Hazecol / Flaretint) through their colour sources
    (CPU = pxColSrc: palette_map_logic.colsrc_eval). Solid (default) returns the par colour unchanged."""
    out = {}
    for pre, par, d in SCALAR_CS:
        rgb = tuple(float(raw.get(par + c, x)) for c, x in zip('rgb', d))
        cs = cs_vec(raw, pre)
        out[par] = rgb if cs_is_solid(cs) else tuple(float(v) for v in colsrc_eval(cs, rgb, rgb, 0.0, pal_rows, pal_ctl))
    return out


def apply_scalar_colours(grows, qrows, cols):
    """Write scalar_colours into uG[10].xyz (EDGECOL) and uQ[5].rgb / uQ[8].rgb (haze, flare tint). In place."""
    grows[10][0:3] = list(cols['Edgecol'])
    qrows[5][0:3] = list(cols['Hazecol'])
    qrows[8][0:3] = list(cols['Flaretint'])
    return grows, qrows


def glow_recolour(raw, colsrc_eval, pal_rows, pal_ctl):
    """-> None (Glow colour source solid: each effector's Glowcolour) or f(k, rgb) for glow_rows: glowing effector k
    takes the colour source (index: stop k)."""
    cs = cs_vec(raw, 'Glow')
    if cs_is_solid(cs):
        return None
    return lambda k, rgb: tuple(float(v) for v in colsrc_eval(cs, rgb, rgb, float(k), pal_rows, pal_ctl))


def haze_params(raw):
    """Haze page (Vh*) -> px_haze_logic.haze_params keys (W1-D). Depth: the geometry's depth while Geo is on (fog
    stops at placed objects); splats / points end the march at Vhobjdist by their alpha; the sky at Vhmaxdist."""
    rv = lambda k, d: raw.get(k, d)
    return {'colour': tuple(float(rv('Vhcol' + c, d)) for c, d in zip('rgb', (0.55, 0.6, 0.7))),
            'cs': tuple(cs_vec(raw, 'Vh')), 'density': float(rv('Vhdensity', 0.08)), 'floor': float(rv('Vhfloor', 0.0)),
            'falloff': float(rv('Vhfalloff', 0.35)), 'noise': float(rv('Vhnoise', 0.5)),
            'noisescale': float(rv('Vhnoisescale', 0.35)),
            'wind': tuple(float(rv('Vhwind' + c, d)) for c, d in zip('xyz', (0.3, 0.05, 0.1))),
            'extinction': float(rv('Vhextinction', 1.0)),
            'tint': tuple(float(rv('Vhtint' + c, 1.0)) for c in 'rgb'), 'gain': float(rv('Vhgain', 1.0)),
            'g': float(rv('Vhg', 0.35)), 'ambient': float(rv('Vhambient', 0.25)), 'steps': int(rv('Vhsteps', 8)),
            'shafts': float(rv('Vhshafts', 0.6)), 'decay': float(rv('Vhdecay', 0.96)), 'length': float(rv('Vhlength', 0.85)),
            'taps': int(rv('Vhtaps', 12)), 'threshold': float(rv('Vhthreshold', 0.0)), 'disc': float(rv('Vhdisc', 0.06)),
            'occlusion': float(rv('Vhocclusion', 1.0)),
            # wave 3: with Geo on the haze gets the geometry's eye depth (lines_depth, Depth TOP cameraspace = view z)
            # and keeps the alpha end for the splats / points (depthalpha)
            'depthmode': 'viewz' if _truthy(rv('Geoon', False)) else 'none', 'depthscale': 1.0,
            'depthalpha': _truthy(rv('Geoon', False)),
            'objdist': float(rv('Vhobjdist', 6.0)), 'maxdist': float(rv('Vhmaxdist', 60.0)),
            'softradius': float(rv('Vhsoft', 0.05)), 'jitter': 0.0, 'shaftlod': float(rv('Vhshaftlod', 1.0)),
            'noisemode': 'light'}


def ref_light_module(col, P, n, campos, blocks, vals, pal=None):
    """Float64 twin of the `light` colour module for ONE point: col (rgb), P, n (unit normal, or None = model 3 / no
    normal), campos, blocks = W1-A light blocks [(7 texels x 4)] of the SELECTED lights in order, vals = module values
    (relight, ambient, gain, add, model, wrap, spec, rough, colsrc..., tint; G = 1). pal = (colsrc_eval, rows, ctl)
    for palette colour modes. -> rgb. Uses the same maths as effectors_logic.ref_light (TD attenuation + cone)."""
    import math as _m
    v = [campos[k] - P[k] for k in range(3)]
    vl = _m.sqrt(sum(x * x for x in v)) or 1.0
    v = [x / vl for x in v]
    model = menu_index(LIGHT_MODELS, vals.get('model', 'halflambert'))
    if n is None:
        model, n = 3, v
    Ls = [0.0, 0.0, 0.0]
    cs = [float(menu_index(COLSRC_MODES, vals.get('colsrc', 'source'))), float(vals.get('palpos', 0.0)),
          float(vals.get('palspread', 1.0)), float(vals.get('palkeep', 0.0))]
    for k, b in enumerate(blocks):
        t = [list(map(float, x)) for x in b]
        ty = int(round(t[1][3]))
        F = t[2][:3]
        if ty == 3:
            L, a = [-x for x in F], 1.0
        else:
            q = list(t[1][:3])
            if ty == 2:
                U, V = t[5][:3], t[6][:3]
                r = [P[i] - q[i] for i in range(3)]
                du = max(min(sum(r[i] * U[i] for i in range(3)) / max(sum(x * x for x in U), 1e-12), 1.0), -1.0)
                dv = max(min(sum(r[i] * V[i] for i in range(3)) / max(sum(x * x for x in V), 1e-12), 1.0), -1.0)
                q = [q[i] + U[i] * du + V[i] * dv for i in range(3)]
            dv_ = [q[i] - P[i] for i in range(3)]
            d = _m.sqrt(sum(x * x for x in dv_))
            L = [x / d for x in dv_] if d > 1e-9 else [-x for x in F]
            a = 1.0
            if t[3][3] > 0.5:
                a = _m.sin(min(max((t[3][1] - d) / max(t[3][1] - t[3][0], 1e-6), 0.0), 1.0) * _m.pi / 2) ** t[3][2]
            if ty == 1:
                ai, ao = _m.acos(max(min(t[4][0], 1.0), -1.0)), _m.acos(max(min(t[4][1], 1.0), -1.0))
                ang = _m.acos(max(min(-sum(L[i] * F[i] for i in range(3)), 1.0), -1.0))
                x = min(max((ao - ang) / max(ao - ai, 1e-6), 0.0), 1.0)
                a *= (x * x * (3 - 2 * x)) ** max(t[4][2], 1e-3)
        if a <= 0.0:
            continue
        dif, sp = 1.0, 0.0
        if model != 3:
            ndl = sum(n[i] * L[i] for i in range(3))
            if model == 1:
                dif = max(ndl, 0.0)
            elif model == 2:
                dif = max((ndl + float(vals.get('wrap', 0.5))) / (1.0 + float(vals.get('wrap', 0.5))), 0.0)
            else:
                h = ndl * 0.5 + 0.5
                dif = h * h
            spec = float(vals.get('spec', 0.0))
            if spec > 0.0 and ndl > 0.0:
                rr = min(max(float(vals.get('rough', 0.5)), 0.02), 1.0)
                hv = [L[i] + v[i] for i in range(3)]
                hl = _m.sqrt(sum(x * x for x in hv)) or 1.0
                sp = spec * max(sum(n[i] * hv[i] / hl for i in range(3)), 0.0) ** (2.0 / rr ** 4 - 2.0)
        sh = a * (dif + sp)
        lc = t[0][:3]
        if not (cs[0] == 3.0 and cs[3] <= 0.0):
            ev, rows, ctl = pal
            lc = list(ev(cs, tuple(vals.get('tint', (1.0, 1.0, 1.0))), tuple(lc), float(k), rows, ctl))
        for i in range(3):
            Ls[i] += lc[i] * t[0][3] * sh
    rl = min(max(float(vals.get('relight', 1.0)), 0.0), 1.0)
    amb, gain, add = float(vals.get('ambient', 0.15)), float(vals.get('gain', 1.0)), float(vals.get('add', 0.0))
    return [col[i] + (col[i] * (amb + Ls[i] * gain) - col[i]) * rl + Ls[i] * add for i in range(3)]


# ---- wave 3 camera rigs (K24 / TC-36): builders/cam_rig_logic.py (Text DAT `cam_rig`) passed in as CR

def cam_rig_active(raw):
    """True when the Camera page drives the camera (else the v2 orbit numbers, unchanged)."""
    return (raw.get('Cammode', 'orbit') != 'orbit' or float(raw.get('Camroll', 0.0)) != 0.0
            or float(raw.get('Camshake', 0.0)) > 0.0 or float(raw.get('Camshakerot', 0.0)) > 0.0)


def _xyz(raw, n, d):
    return tuple(float(raw.get(n + c, x)) for c, x in zip('xyz', d))


def cam_points(text):
    out = []
    for seg in str(text or '').split(';'):
        w = seg.replace(',', ' ').split()
        if len(w) >= 3:
            try:
                out.append(tuple(float(x) for x in w[:3]))
            except ValueError:
                pass
    return out or [(0.0, 0.5, 5.0), (3.0, 0.5, 0.0)]


def cam_shots(raw, CR):
    """Camshots 'crane:8 orbit:8 dolly:4 path:8' -> Director shots with this page's rig parameters."""
    tgt = _xyz(raw, 'Camtarget', (0.0, 0.0, 0.0))
    fov = float(raw.get('Fov', 45.0))
    out = []
    for w in str(raw.get('Camshots', '') or '').split():
        rig, _s, hold = w.partition(':')
        try:
            hold = float(hold) if hold else 8.0
        except ValueError:
            hold = 8.0
        kw = {'fov': fov}
        if rig == 'crane':
            kw.update(base=tgt, heading=float(raw.get('Camheading', 0.0)), pitch=float(raw.get('Campitch', 20.0)),
                      length=float(raw.get('Camlength', 4.0)), heading_speed=float(raw.get('Camheadspeed', 10.0)),
                      pitch_amp=float(raw.get('Campitchamp', 0.0)), pitch_freq=float(raw.get('Campitchfreq', 0.1)))
        elif rig == 'orbit':
            kw.update(centre=tgt, radius=float(raw.get('Camdist', 4.0)), height=float(raw.get('Camheight', 0.0)),
                      speed_deg=float(raw.get('Orbit', 0.0)) or 10.0)
        elif rig == 'dolly':
            kw.update(a=_xyz(raw, 'Camdollya', (0.0, 0.5, 6.0)), b=_xyz(raw, 'Camdollyb', (0.0, 0.5, 2.0)), target=tgt)
        elif rig == 'path':
            kw.update(points=cam_points(raw.get('Campoints')), closed=True, target=tgt)
        else:
            continue
        out.append(CR.shot(rig, hold, raw.get('Camtrans', 'cut'), float(raw.get('Camtdur', 1.0)), **kw))
    return out or [CR.shot('orbit', 8.0, centre=tgt, radius=4.0, fov=fov)]


def cam_pose(raw, CR, t, beats, state, follow_point=None, dt=0.0):
    """Camera page -> pose (cam_rig_logic dict) at sim time t / beat count `beats`; state = a dict kept by the runtime
    (Director / Path objects, follow memory)."""
    mode = raw.get('Cammode', 'orbit')
    fov = float(raw.get('Fov', 45.0))
    tgt = _xyz(raw, 'Camtarget', (0.0, 0.0, 0.0))
    if mode == 'crane':
        p = CR.crane(tgt, float(raw.get('Camheading', 0.0)) + float(raw.get('Camheadspeed', 10.0)) * t,
                     float(raw.get('Campitch', 20.0)) + float(raw.get('Campitchamp', 0.0)) *
                     math.sin(2.0 * math.pi * float(raw.get('Campitchfreq', 0.1)) * t),
                     float(raw.get('Camlength', 4.0)), 0.0, (0.0, 0.0, 0.0), fov)
    elif mode == 'dolly':
        per = max(float(raw.get('Camdollysec', 10.0)), 1e-3)
        u = (t / per) % 2.0
        p = CR.dolly(_xyz(raw, 'Camdollya', (0.0, 0.5, 6.0)), _xyz(raw, 'Camdollyb', (0.0, 0.5, 2.0)),
                     u if u <= 1.0 else 2.0 - u, tgt, 'smooth', 0.0, fov)
    elif mode == 'path':
        key = (str(raw.get('Campoints')),)
        if state.get('path_key') != key:
            state['path'] = CR.Path(cam_points(raw.get('Campoints')), True)
            state['path_key'] = key
        p = CR.path_pose(state['path'], (t / max(float(raw.get('Campathsec', 20.0)), 1e-3)) % 1.0, tgt, 0.05, 0.0, fov)
    elif mode == 'follow':
        p = CR.follow(state.get('follow_prev'), follow_point or tgt, _xyz(raw, 'Camoffset', (0.0, 1.0, 4.0)),
                      float(raw.get('Camlag', 0.4)), max(dt, 1e-4), 0.0, fov)
        state['follow_prev'] = p
    elif mode == 'director':
        key = tuple(str(raw.get(k)) for k in ('Camshots', 'Camdirmode', 'Camquant', 'Camtrans', 'Camtdur', 'Camseed',
                                               'Camtarget' + 'x', 'Camtargety', 'Camtargetz', 'Camheading', 'Campitch',
                                               'Camlength', 'Camheadspeed', 'Campitchamp', 'Campitchfreq', 'Camdist',
                                               'Camheight', 'Orbit', 'Fov', 'Campoints', 'Camdollyax', 'Camdollybx'))
        if state.get('dir_key') != key:
            state['dir'] = CR.Director(cam_shots(raw, CR), raw.get('Camdirmode', 'random'), int(raw.get('Camseed', 1)),
                                       float(raw.get('Camquant', 4.0)), 4.0, 16.0, 120.0)
            state['dir_key'] = key
        p, info = state['dir'].at(beats, t)
        state['dir_info'] = info
    else:                                           # orbit (+ roll / shake): the v2 orbit position, looking level
        a = math.radians(float(state.get('orbit_deg', 0.0)))
        d = float(raw.get('Camdist', 4.0))
        pos = (math.sin(a) * d, float(raw.get('Camheight', 0.0)), math.cos(a) * d)
        p = CR.pose(pos, (pos[0] - math.sin(a), pos[1], pos[2] - math.cos(a)), 0.0, fov)
    p = dict(p)
    p['roll'] = float(p.get('roll', 0.0)) + float(raw.get('Camroll', 0.0))
    p['fov'] = fov
    if float(raw.get('Camshake', 0.0)) > 0.0 or float(raw.get('Camshakerot', 0.0)) > 0.0:
        p = CR.shake(p, t, float(raw.get('Camshake', 0.0)), float(raw.get('Camshakerot', 0.0)),
                     float(raw.get('Camshakefreq', 6.0)), 7)
    return p


def cam_motion(row0, row1, dt):
    """(camera velocity xyz, angular velocity xyz) between two engine camera rows over dt (sim s); 0 for dt 0."""
    if dt <= 0.0 or not row0 or not row1:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    p0, x0, y0, f0 = cam_basis(row0)
    p1, x1, y1, f1 = cam_basis(row1)
    vel = tuple((b - a) / dt for a, b in zip(p0, p1))
    z0 = [-v for v in f0]
    z1 = [-v for v in f1]
    R0 = [[x0[r], y0[r], z0[r]] for r in range(3)]
    R1 = [[x1[r], y1[r], z1[r]] for r in range(3)]
    dR = [[sum(R1[r][k] * R0[c][k] for k in range(3)) for c in range(3)] for r in range(3)]     # R1 R0^T
    w = ((dR[2][1] - dR[1][2]) * 0.5 / dt, (dR[0][2] - dR[2][0]) * 0.5 / dt, (dR[1][0] - dR[0][1]) * 0.5 / dt)
    return vel, w


def cam_row(p, CR):
    """Pose -> engine camera row (tx ty tz ry rx rz; rotate order xyz = pcam's)."""
    v = CR.td_pars(p, 'xyz')
    return [v['tx'], v['ty'], v['tz'], v['ry'], v['rx'], v['rz']]


def cam_basis(row):
    """Engine camera row (tx ty tz ry [rx rz], degrees, rotate order xyz) -> (pos, right, up, forward)."""
    rx = math.radians(float(row[4])) if len(row) > 4 else 0.0
    ry = math.radians(float(row[3]))
    rz = math.radians(float(row[5])) if len(row) > 5 else 0.0
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    Rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    mm = lambda a, b: [[sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3)] for r in range(3)]
    R = mm(Rz, mm(Ry, Rx))
    col = lambda k: (R[0][k], R[1][k], R[2][k])
    z = col(2)
    return (float(row[0]), float(row[1]), float(row[2])), col(0), col(1), (-z[0], -z[1], -z[2])


def cam_viewproj_row(row, fov_deg, resx, resy, near=0.01, far=1000.0):
    """proj * view of a full engine camera row (any rx / rz); equals cam_viewproj when rx = rz = 0."""
    if len(row) <= 4 or (float(row[4]) == 0.0 and float(row[5]) == 0.0):
        return cam_viewproj(row, fov_deg, resx, resy, near, far)
    pos, rt, up, fw = cam_basis(row)
    bk = [-x for x in fw]
    view = [list(rt) + [-sum(a * b for a, b in zip(rt, pos))], list(up) + [-sum(a * b for a, b in zip(up, pos))],
            bk + [-sum(a * b for a, b in zip(bk, pos))], [0.0, 0.0, 0.0, 1.0]]
    fx = 1.0 / math.tan(math.radians(max(float(fov_deg), 1e-3)) * 0.5)
    fy = fx * float(resx) / max(float(resy), 1.0)
    n, f = float(near), float(far)
    proj = [[fx, 0.0, 0.0, 0.0], [0.0, fy, 0.0, 0.0], [0.0, 0.0, -(f + n) / (f - n), -2.0 * f * n / (f - n)],
            [0.0, 0.0, -1.0, 0.0]]
    return [[sum(proj[r][k] * view[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


# ----------------------------------------------------------------------------------------------- presets

def snapshot(stack, flat, effectors=None, name='', effpars=None, make=None, **extra):
    """Whole look: structure + every value (core + module pars) + effector object transforms + effector settings
    (Effector page: motion, trail, glow, point set) + 'make' = effectors to create when missing [(name, kind)].
    Wave 2 extras (optional): 'lights' (light effectors in /project1/effectors), 'geo' (objects in PX's geo/),
    'lines' (PX_lines par values)."""
    d = {'version': VERSION, 'name': name, 'stack': [dict(i) for i in stack], 'values': dict(flat),
         'effectors': dict(effectors or {}), 'effpars': dict(effpars or {}), 'make': [list(m) for m in (make or [])]}
    for k in ('lights', 'geo', 'lines'):
        if extra.get(k) is not None:
            d[k] = extra[k]
    return d


def preset_dumps(snap):
    return json.dumps(snap, sort_keys=True, separators=(',', ':'))


def preset_loads(text):
    d = json.loads(text)
    if not isinstance(d, dict) or 'stack' not in d or 'values' not in d:
        raise ValueError('not a PX preset')
    d['stack'] = [new_instance(i['type'], i['uid'], i.get('enabled', True), i.get('label', '')) for i in d['stack']
                  if i.get('type') in MODULES]
    d.setdefault('effectors', {})
    d.setdefault('effpars', {})
    d.setdefault('make', [])
    for i in d['stack']:                            # presets older than auto progress (28 Oct) keep their look: auto off
        if i['type'] in AUTO_TYPES:
            for p in _auto():
                d['values'].setdefault(par_name(i['uid'], p['name']), p['default'])
    return d


# ---- v1 looks' effectors (28 Oct preset sweep): px_looks' v1 looks moved N1-N3 / W1 by absTime expressions and were
# stored before presets carried `make`, so a recall left their proximity modules with no effector (no hands, no fire
# walker). The fix gives those rows the effectors as `make` + a lissajous Motion close to the old expressions
# (period 2 pi s: phase = seconds). Only rows whose `make` lacks the names are changed (fix_v1_preset, idempotent).
_TAU = 2.0 * math.pi
V1_EFFECTORS = {
    'N1': ('null', {'tz': 0.15}, {'Ma': (0.0, 0.0, 0.15), 'Mb': (0.75, 0.45, 0.0), 'Mfreq': (0.9, 0.7, 0.0), 'Mphase': 0.0}),
    'N2': ('null', {'tz': 0.1}, {'Ma': (0.0, 0.0, 0.1), 'Mb': (0.85, 0.4, 0.0), 'Mfreq': (0.5, 1.1, 0.0), 'Mphase': 0.3}),
    'N3': ('null', {'tz': -0.1}, {'Ma': (0.0, 0.0, -0.1), 'Mb': (0.55, 0.5, 0.0), 'Mfreq': (1.3, 0.6, 0.0), 'Mphase': 0.6}),
    'W1': ('sphere', {'ty': 0.05, 'sx': 0.5, 'sy': 0.9, 'sz': 0.5},
           {'Ma': (0.0, 0.05, 0.0), 'Mb': (0.7, 0.0, 0.45), 'Mfreq': (0.35, 0.0, 0.27), 'Mphase': 0.25}),
}
V1_FIX_PRESETS = {'hand_push_cloud': ('N1', 'N2', 'N3'), 'lattice_collapse': ('N1', 'N2'), 'ember_splat': ('W1',),
                  'ember_splat (splats)': ('W1',)}   # = 'ember_splat' + SPLAT_SUFFIX (defined below)


def fix_v1_preset(name, snap):
    """-> (snapshot, changed). Adds the missing v1 effectors (make + transform + Motion settings) to a stored v1 look."""
    need = [n for n in V1_FIX_PRESETS.get(name, ()) if n not in [m[0] for m in snap.get('make', [])]]
    if not need:
        return snap, False
    s = json.loads(json.dumps(snap))
    s.setdefault('make', [])
    s.setdefault('effectors', {})
    s.setdefault('effpars', {})
    for n in need:
        kind, xf, mot = V1_EFFECTORS[n]
        s['make'].append([n, kind])
        full = dict(zip(XF_KEYS, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0)))
        full.update(xf)
        s['effectors'][n] = [float(full[k]) for k in XF_KEYS]
        ep = dict((n_, list(d_) if isinstance(d_, (list, tuple)) else d_) for n_, st_, d_, _o in EFF_PARS if st_ != 'Pulse')
        ep.update({'Motion': 'lissajous', 'Mperiod': _TAU, 'Mloop': 'loop'})
        ep.update(dict((k, list(v) if isinstance(v, tuple) else v) for k, v in mot.items()))
        s['effpars'][n] = ep
    return s, True


# ---- preset table order (28 Oct, user: "how do i re-arrange them"): pure list edits on the names in px_presets order;
# the runtime rewrites the table's cells in the new order (row count never changes, nothing is deleted)

def is_builtin_name(name):
    """Built-in looks + their splat versions + splat_showcase (install_builtins refreshes these by name)."""
    return (name in BUILTIN or name == SPLAT_SHOWCASE[0]
            or any(name == nm + SPLAT_SUFFIX for nm, _sc in SPLAT_LOOKS))


def preset_move(names, name, delta):
    """-> new order with the first `name` moved by delta (-1 up, +1 down), clamped; unknown name -> unchanged."""
    out = list(names)
    if name not in out:
        return out
    k = out.index(name)
    j = max(0, min(len(out) - 1, k + int(delta)))
    out.insert(j, out.pop(k))
    return out


def preset_sort(names):
    """A-Z (case-insensitive), built-ins first; stable for equal names."""
    return sorted(names, key=lambda n: (0 if is_builtin_name(n) else 1, n.lower(), n))


def preset_rename_check(names, old, new):
    """'' when old -> new is allowed, else the reason."""
    new = str(new or '').strip()
    if old not in names:
        return 'no preset %r' % old
    if not new:
        return 'type the new name in Newname'
    if new == old:
        return 'same name'
    if new in names:
        return 'a preset %r exists already' % new
    return ''


def same_structure(a, b):
    return [(i['uid'], i['type'], i['enabled']) for i in a['stack']] == [(i['uid'], i['type'], i['enabled']) for i in b['stack']]


def curve(t, kind='linear'):
    t = max(0.0, min(1.0, float(t)))
    if kind == 'ease':
        return 1.0 - (1.0 - t) * (1.0 - t)
    if kind == 'smooth':
        return t * t * (3.0 - 2.0 * t)
    return t


def discrete_keys(stack):
    """TD par names that never lerp (menus, toggles, ints, strings): switch at t = 0.5."""
    out = set()
    for _pg, pars in CORE_PAGES:
        for name, style, _d, _o in pars:
            if style in ('Menu', 'Toggle', 'Int', 'Str', 'File', 'Folder', 'CHOP', 'COMP', 'DAT', 'Pulse'):
                out.add(name)
    for inst in stack:
        for p in HEADER + MODULES[inst['type']]['params']:
            if p['kind'] in ('menu', 'toggle', 'int'):
                out.add(par_name(inst['uid'], p['name']))
        for s in HEADER_STR:
            out.add(par_name(inst['uid'], s))
    return out


def morph_flat(a, b, t, kind='linear', discrete=()):
    """Values at morph time t: numeric keys in both lerp (curve), discrete keys switch at 0.5, keys only in b jump to b,
    keys only in a stay."""
    u = curve(t, kind)
    out = dict(a)
    for k, vb in b.items():
        va = a.get(k)
        if va is None or k in discrete or isinstance(vb, str) or isinstance(va, str) or isinstance(vb, bool):
            out[k] = vb if (va is None or u >= 0.5) else va
        else:
            try:
                out[k] = float(va) + (float(vb) - float(va)) * u
            except (TypeError, ValueError):
                out[k] = vb if u >= 0.5 else va
    return out


def morph_plan(a, b):
    """'lerp' when the stacks match; else 'switch': B's stack is installed at the start (one recompile), modules
    that exist in both (same uid + type) lerp, the rest take B's values at once."""
    return 'lerp' if same_structure(a, b) else 'switch'


# ---- built-in looks (D): stack + values + the effectors they need (created on recall when missing)
# (type, {param: value}) per module; core pars by TD name; effectors (name, kind, xform, Effector-page settings).
XF_KEYS = ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz')
DEMO_IMAGES = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/demo/paintings'   # wave 4 K27 (git-ignored)
BUILTIN = {
    'KANDA swipe': {
        'about': 'plane front crossing in 18 s: cream at the front, red tail, back to the scan colour; sparkle edge',
        'stack': [('prox_colour', {'effectors': 'Esw', 'mode': 'ramp', 'shape': 'behind', 'radius': 3.0, 'falloff': 3.0,
                                   'cover': 1.0,
                                   'colour': (0.85, 0.05, 0.02), 'colour2': (1.0, 0.93, 0.8), 'emission': 1.5,
                                   'flicker': 0.3, 'noiseedge': 0.35, 'noisefreq': 14.0, 'edge': 0.03}),
                  ('prox_scale', {'effectors': 'Esw', 'shape': 'behind', 'radius': 0.4, 'sizegain': 1.5,
                                  'alphagain': 0.5, 'noiseedge': 0.5, 'noisefreq': 20.0}),
                  ('jitter', {'amp': 0.004, 'rate': 20.0})],
        'core': {'Sprite': 'soft', 'Bloom': 0.3, 'Flare': 0.3},
        'effectors': [('Esw', 'plane', {'rz': -90.0, 'sx': 6.0, 'sz': 6.0},
                       {'Motion': 'line', 'Ma': (-3.0, 0.0, 0.0), 'Mb': (3.0, 0.0, 0.0), 'Mperiod': 18.0,
                        'Mloop': 'pingpong', 'Mease': 'linear'})]},
    'Hanging streaks': {
        'about': 'vertical streaks above a rising plane (ragged edge); the front climbs in 4 s, so only the top stays frayed',
        'stack': [('prox_stretch', {'effectors': 'Ehs', 'shape': 'ahead', 'radius': 3.0, 'axis': 'y', 'stretch': 18.0,
                                    'thin': 0.85, 'noiseedge': 0.6, 'noisefreq': 6.0, 'edge': 0.05})],
        'core': {'Sprite': 'square', 'Tealorange': 0.6, 'Streakmax': 256.0, 'Alpha': 0.55, 'Bright': 1.2, 'Size': 0.007},
        'effectors': [('Ehs', 'plane', {'sx': 8.0, 'sz': 8.0},
                       {'Motion': 'line', 'Ma': (0.0, -1.2, 0.0), 'Mb': (0.0, 2.0, 0.0), 'Mperiod': 8.0,
                        'Mloop': 'pingpong', 'Mease': 'smooth'})]},
    'Alley people fire': {
        'about': 'an actor (person stand-in) walks the alley; the scan burns near it, embers fly from the pool, teal jets on the actor',
        'stack': [('prox_burn', {'effectors': 'Eact', 'maskin': 'scene', 'radius': 0.7, 'rise': 3.0, 'source': 'scan',
                                 'rate': 4.0, 'cone': 30.0, 'speed': 1.5, 'lifespan': 2.5, 'embers': 1.5,
                                 'emission': 6.0}),
                  ('prox_colour', {'effectors': 'Eact', 'maskin': 'actor', 'mode': 'emissive', 'radius': 0.1,
                                   'emission': 3.0}),
                  ('colour_ramp', {'maskin': 'actor', 'attr': 'height', 'lo': -1.0, 'hi': 1.0,
                                   'col0': (0.1, 0.9, 0.8), 'col3': (1.0, 1.0, 1.0), 'blend': 'replace'}),
                  ('wind', {'maskin': 'pool', 'buoyancy': 2.0}),
                  ('curl', {'maskin': 'actor', 'mode': 'displace', 'distance': 0.06, 'scale': 6.0, 'speed': 1.5})],
        'core': {'Actormode': 'gen', 'Actorgen': 'cylinder', 'Actorcount': 6144, 'Actorgenp': 0.55,
                 'Actorfollow': 'Ewalk', 'Pool': 15.0, 'Bloom': 1.0},
        'effectors': [('Ewalk', 'null', {}, {'Motion': 'line', 'Ma': (-2.0, 0.0, 1.0), 'Mb': (2.0, 0.0, -1.0),
                                             'Mperiod': 20.0, 'Mloop': 'pingpong', 'Trail': 32}),
                      ('Eact', 'actor', {}, {})]},
    'Radial blast': {
        'about': 'Trig1: a white-hot shockwave rolls out from the camera, the scene stretches into warp streaks toward the '
                 'vanishing point and bursts outward from its centre, then re-forms (sur.render 8-12 s, DR1 86-96 s)',
        'stack': [('shockwave', {'effectors': 'Ecam', 'trigger': 'trig1', 'speed': 4.0, 'width': 1.5, 'amp': 0.5,
                                 'decay': 1.0, 'ringcol': (1.0, 0.95, 0.85), 'colourmix': 1.0, 'emission': 40.0}),
                  ('prox_stretch', {'effectors': 'Ecam', 'radius': 100.0, 'axis': 'radial_cam', 'stretch': 0.0,
                                    'thin': 0.9, 'drive': 'stretch:trig1*160'}),
                  ('explode', {'effectors': '', 'progress': 0.0, 'distance': 1.6, 'random': 0.6,
                               'drive': 'progress:trig1*0.7'})],
        'core': {'Bloom': 1.6, 'Bloomthr': 0.7, 'Flare': 0.5, 'Flareghosts': 0, 'Chromatic': 0.006, 'Trigdecay': 1.2,
                 'Streakmax': 400.0, 'Bright': 2.6, 'Tealorange': 0.15, 'Saturation': 1.1},
        'effectors': [('Ecam', 'camera', {}, {})]},
    'Slice bike': {
        'about': 'horizontal ring bands with gaps (stepped scanlines) inside the box, turning slowly',
        'stack': [('prox_stretch', {'effectors': 'Esl', 'mode': 'slices', 'axis': 'y', 'radius': 0.3, 'bandwidth': 0.06,
                                    'gap': 0.45, 'snap': 0.8, 'stretch': 0.0}),
                  ('orbit', {'effectors': 'Esl', 'axis': 'y', 'speed': 0.3})],
        'core': {'Sprite': 'disc'},
        'effectors': [('Esl', 'box', {'sx': 1.6, 'sy': 1.6, 'sz': 1.6}, {})]},
    'Tile city': {
        'about': 'the scene breaks into flat tiles (chunk 0.25) that drift and rearrange on LFO 1, oriented slabs',
        'stack': [('explode', {'effectors': '', 'chunk': 0.25, 'mode': 'noise', 'distance': 1.5, 'random': 0.8, 'swirl': 0.5,
                               'drive': 'progress:lfo1*1'}),
                  ('jitter', {'chunk': 0.25, 'amp': 0.01, 'rate': 2.0, 'mode': 'smooth'})],
        'core': {'Sprite': 'quad', 'Lfo1rate': 0.08, 'Size': 0.009, 'Aperture': 0.0},
        'effectors': []},
    # ---- wave 2 looks (27 Oct): lines, haze + shafts, lights, geometry, palette. 'scene' = SPLAT_SCENES key (full
    # scene), 'lights' = light effectors made in /project1/effectors (tag pxpreset; a recall removes the previous
    # look's), 'geo' = objects made in PX's geo/ (Geo page), 'lines' = PX_lines par values (others to defaults).
    'Green line sweep': {
        'about': 'neon-green contour lines scroll across the dark street scan while a green front sweeps it (TFM '
                 '320-370 s, DR1 17-35 s)',
        'scene': 'truck',
        'stack': [('prox_colour', {'effectors': 'Egs', 'mode': 'emissive', 'shape': 'behind', 'radius': 1.2,
                                   'falloff': 2.0, 'emission': 4.0, 'colsrc': 'palette', 'palpos': 0.8, 'edge': 0.05}),
                  ('colour_adjust', {'exposure': -1.6, 'saturation': 0.4})],
        'core': {'Bloom': 1.0, 'Bloomthr': 0.6, 'Palsource': 'neon_green', 'Lineson': True, 'Tonemap': 'aces',
                 'Bloomtight': 0.4},
        'lines': {'Rings': False, 'Contour': True, 'Ctaxis': 'x', 'Cttangent': 'view', 'Ctspacing': 0.35,
                  'Ctband': 0.03, 'Ctlen': 0.08, 'Ctspeed': 0.15, 'Ctwave': 0.08, 'Ctwavefreq': 1.5, 'Ctmax': 65536,
                  'Linecolsrc': 'palette', 'Linepalpos': 0.75, 'Width': 1.5, 'Halo': 1.0, 'Intensity': 2.0,
                  'Bgdim': 0.35, 'Blend': 'max'},
        'effectors': [('Egs', 'plane', {'rz': -90.0, 'sx': 8.0, 'sz': 8.0},
                       {'Motion': 'line', 'Ma': (-3.0, 0.0, 0.0), 'Mb': (3.0, 0.0, 0.0), 'Mperiod': 12.0,
                        'Mloop': 'pingpong', 'Mease': 'linear', 'Glow': True, 'Glowsize': 0.08,
                        'Glowcolour': (0.2, 1.0, 0.4), 'Glowintensity': 1.2})]},
    'Neon rings': {
        'about': 'concentric neon rings expand and orbit around the scan, one palette colour per ring, a stop on every '
                 'beat (TFM 40-60 s, 600-620 s; OSC rainbow ring)',
        'scene': 'smiley',
        'stack': [('colour_adjust', {'exposure': -0.8, 'saturation': 0.7})],
        'core': {'Bloom': 1.2, 'Bloomthr': 0.7, 'Bloomring': 0.3, 'Bloomringr': 0.08, 'Bloomringchroma': 0.15,
                 'Palsource': 'neon_trio', 'Palmode': 'steps', 'Paldrive': 'bpm_step', 'Palevery': 1.0, 'Lineson': True},
        'lines': {'Rings': True, 'Ringcount': 6, 'Ringradius': 0.35, 'Ringspacing': 0.12, 'Ringexpand': 0.25,
                  'Ringtilt': 35.0, 'Ringorbit': 40.0, 'Ringcentre': (0.0, 0.1, 0.0), 'Ringattr': 'index',
                  'Linecolsrc': 'index', 'Width': 3.0, 'Halo': 8.0, 'Intensity': 2.5, 'Contour': False}},
    'Haze shafts': {
        'about': 'two spot lights cut beams through drifting haze over the street scan; the scan is relit by the same '
                 'lights (BTNA 0-6 s, TRS 40 s, Shibuya underpass)',
        'scene': 'truck',
        'stack': [('light', {'effectors': '#pxpreset', 'relight': 0.85, 'ambient': 0.12, 'model': 'halflambert',
                             'gain': 1.2})],
        'core': {'Vhon': True, 'Vhlights': '#pxpreset', 'Vhdensity': 0.12, 'Vhfalloff': 0.3, 'Vhfloor': -0.2,
                 'Vhshafts': 1.2, 'Vhambient': 0.015, 'Vhextinction': 0.25, 'Vhg': 0.6, 'Vhtaps': 16, 'Vhdisc': 0.04,
                 'Bloom': 0.6, 'Tonemap': 'aces', 'Exposure': -0.2},
        'lights': [('pxL_haze1', 'spot', (-1.2, 2.4, 0.5), (-70.0, 0.0, 15.0), (1.0, 0.7, 0.35), 3.0,
                    {'cone_angle': 35.0, 'cone_delta': 12.0, 'att_end': 8.0}),
                   ('pxL_haze2', 'spot', (1.4, 2.6, -0.4), (-75.0, 0.0, -20.0), (0.35, 0.6, 1.0), 2.5,
                    {'cone_angle': 30.0, 'cone_delta': 10.0, 'att_end': 8.0})]},
    'Light sweep': {
        'about': 'a warm light travels along the street and reveals the dark scan as it passes (KANDA 25-45 s, NdCV)',
        'scene': 'truck',
        'stack': [('light', {'effectors': '#pxpreset', 'relight': 1.0, 'ambient': 0.05, 'add': 0.15,
                             'model': 'halflambert', 'gain': 1.5})],
        'core': {'Bloom': 0.5, 'Tonemap': 'aces'},
        'lights': [('pxL_sweep', 'point', (0.0, 0.9, 0.6), (0.0, 0.0, 0.0), (1.0, 0.75, 0.45), 3.0,
                    {'att_end': 2.5, 'expr': {'tx': 'math.sin(absTime.seconds * 0.35) * 3.0'}})]},
    'Lit splats + geometry': {
        'about': 'a chrome sphere (reflecting the scene, GE3) and a glowing ring placed inside the splat scene, '
                 'occluding both ways, lit by the same magenta / cyan lights that relight the splats (TFM 200-210 s '
                 'chrome hands, 620 s green sphere)',
        'scene': 'smiley',
        'stack': [('light', {'effectors': '#pxpreset', 'relight': 0.9, 'ambient': 0.2, 'model': 'halflambert',
                             'spec': 0.4, 'rough': 0.35})],
        'core': {'Geoon': True, 'Geokey': False, 'Geolights': '#pxpreset', 'Bloom': 0.9, 'Bloomthr': 0.9,
                 'Geoenv': True, 'Geoenvcentre': (0.18, 0.05, 0.25), 'Geoenvres': 128, 'Geoenveveryn': 4},   # wave 4 GE3
        'lights': [('pxL_geo1', 'point', (0.6, 0.5, 0.6), (0.0, 0.0, 0.0), (1.0, 0.2, 0.8), 3.0, {'att_end': 3.0}),
                   ('pxL_geo2', 'point', (-0.6, 0.4, 0.5), (0.0, 0.0, 0.0), (0.2, 0.8, 1.0), 2.5, {'att_end': 3.0})],
        'geo': [('Gp_chrome', 'sphere', {'tx': 0.18, 'ty': 0.05, 'tz': 0.25, 'sx': 0.35, 'sy': 0.35, 'sz': 0.35},
                 (0.85, 0.85, 0.9), 1.0, 0.05, 0.0),         # wave 4: true chrome (reflects the scene, Geoenv)
                ('Gp_ring', 'torus', {'tx': 0.0, 'ty': 0.1, 'tz': 0.0, 'rx': 70.0, 'sx': 0.9, 'sy': 0.9, 'sz': 0.9},
                 (0.2, 1.0, 0.4), 0.0, 0.5, 3.0)]},
    'Palette beat cycle': {
        'about': 'the scan coloured by height through the shared palette, which turns a full cycle every 4 beats; '
                 'edge lines in the same palette (OSC tempo colour, TFM cuts)',
        'scene': 'truck',
        'stack': [('colour_ramp', {'attr': 'height', 'lo': -0.5, 'hi': 2.5, 'ramp': 'palette', 'emission': 0.6})],
        'core': {'Palsource': 'rainbow', 'Palmode': 'cycle', 'Palinterp': 'oklab', 'Paldrive': 'bpm_cycle',
                 'Palevery': 4.0, 'Bloom': 0.6, 'Lineson': True},
        'lines': {'Rings': False, 'Contour': False, 'Edges': True, 'Edthr': 0.12, 'Edwidth': 1.5,
                  'Edgecolsrc': 'attr', 'Edattr': 'screeny', 'Intensity': 1.5, 'Bgdim': 0.2}},
    'Acid palette': {
        'about': 'brightness remapped through an acid yellow / magenta / cyan palette (AVA 8-12 s, TFM 420-430 s)',
        'scene': 'smiley',
        'stack': [('colour_ramp', {'attr': 'luma', 'lo': 0.05, 'hi': 0.9, 'ramp': 'palette', 'emission': 0.3}),
                  ('jitter', {'amp': 0.002, 'rate': 12.0})],
        'core': {'Palsource': 'acid', 'Palmode': 'gradient', 'Palinterp': 'oklab', 'Bloom': 0.5, 'Saturation': 1.4,
                 'Edgecolsrc': 'palette', 'Edgepalpos': 0.5}},
    'Fire clouds': {
        'about': 'the scan burns near a drifting volume, flame clouds of large soft embers rise through warm haze, '
                 'colours from the fire palette (SPRWL 4-16 s, ALLEY 9-19 s)',
        'scene': 'truck',
        'stack': [('prox_burn', {'effectors': 'Efc', 'maskin': 'scene', 'radius': 1.2, 'rise': 2.0, 'source': 'volume',
                                 'rate': 3.0, 'cone': 50.0, 'speed': 0.6, 'lifespan': 3.0, 'embers': 0.4, 'lift': 0.5,
                                 'heatscale': 0.6, 'emission': 0.8, 'firesrc': 'palette', 'keep': 0.1}),
                  ('wind', {'maskin': 'pool', 'buoyancy': 1.5}),
                  ('curl', {'maskin': 'pool', 'strength': 1.5, 'scale': 0.8})],
        'core': {'Pool': 12.0, 'Palsource': 'fire', 'Palinterp': 'oklab', 'Bloom': 0.6, 'Bloomthr': 1.0,
                 'Bloomclamp': 4.0, 'Vhon': True, 'Vhlights': '#pxpreset', 'Vhdensity': 0.05, 'Vhambient': 0.12,
                 'Vhshafts': 0.0, 'Vhcol': (0.9, 0.4, 0.15), 'Vhcolsrc': 'solid', 'Vhextinction': 0.3,
                 'Exposure': -0.6},
        'lights': [('pxL_fire', 'point', (0.0, 0.6, 0.0), (0.0, 0.0, 0.0), (1.0, 0.45, 0.1), 1.2, {'att_end': 4.0})],
        'effectors': [('Efc', 'sphere', {'sx': 1.2, 'sy': 1.2, 'sz': 1.2},
                       {'Motion': 'wander', 'Ma': (0.0, 0.3, 0.0), 'Mb': (1.5, 0.2, 0.8), 'Mperiod': 20.0})]},
    # ---- wave 3 looks (27 Oct): packets, camera director + blur, fire spread + bounce, echoes, glyphs, dabs, spiral
    # reveal, k-NN lace (docs/builds/px.md "Wave 3")
    'Packet glitch': {
        'about': 'the street breaks into rigid packets that slide and turn on every beat and reassemble between them '
                 '(Superman holograms, SA18)',
        'scene': 'truck',
        'stack': [('glitch', {'gmode': 'packet', 'block': 0.6, 'prob': 0.35, 'offset': 0.25, 'rot': 35.0, 'hold': 0.5,
                              'envsrc': 'beat'})],
        'core': {'Tempo': 'manual', 'Bpm': 120.0, 'Beatdecay': 4.0, 'Bloom': 0.4, 'Sortmode': 'always'}},
    'Crane director': {
        'about': 'the camera cuts between crane, orbit, dolly and path shots on the bar, with camera motion blur on the '
                 'moves (K24, TC-36, K25)',
        'scene': 'truck',
        'stack': [('velocity_streak', {'source': 'camera', 'gain': 1.5, 'maxlen': 30.0})],
        'core': {'Cammode': 'director', 'Camshots': 'crane:8 orbit:8 dolly:4 path:8', 'Camtarget': (0.0, 0.8, 0.0),
                 'Camlength': 5.0, 'Campitch': 15.0, 'Camheadspeed': 25.0, 'Camdist': 5.0, 'Camheight': 1.0,
                 'Orbit': 12.0, 'Camdollya': (0.0, 1.0, 8.0), 'Camdollyb': (0.0, 0.9, 3.5),
                 'Campoints': '-4 1 4; 0 2 5; 4 1 4; 3 0.6 -3; -3 0.6 -3', 'Camquant': 4.0, 'Camtrans': 'cut',
                 'Tempo': 'manual', 'Bpm': 120.0, 'Bloom': 0.4}},
    'Fire spreads': {
        'about': 'a wandering flame sets the street alight, the fire creeps along the scan and its glow lights the '
                 'surroundings (ALLEY; SA21 heat spread + SA5 bounce through the shared voxel grid)',
        'scene': 'truck',
        'stack': [('prox_burn', {'effectors': 'Efs', 'maskin': 'scene', 'radius': 0.25, 'rise': 2.5, 'lift': 0.3,
                                 'embers': 0.3, 'heatscale': 0.6, 'emission': 1.5, 'firesrc': 'palette', 'rate': 0.0}),
                  ('heat_spread', {'rate': 1.5, 'radius': 0.15}),
                  ('light', {'effectors': '#pxpreset', 'relight': 0.7, 'ambient': 0.25, 'bounce': 2.0,
                             'bouncecol': (1.0, 0.45, 0.12), 'bounceradius': 0.8})],
        'core': {'Palsource': 'fire', 'Heatdecay': 0.15, 'Hotthr': 0.6, 'Hotmax': 8192, 'Bloom': 0.8, 'Bloomthr': 0.9,
                 'Exposure': -0.3},
        'effectors': [('Efs', 'sphere', {'sx': 0.3, 'sy': 0.3, 'sz': 0.3},
                       {'Motion': 'wander', 'Ma': (0.0, 0.4, 0.0), 'Mb': (2.0, 0.3, 1.0), 'Mperiod': 30.0})]},
    'Echo dancer': {
        'about': 'a figure walks through the scene leaving a trail of fading echoes of itself (TDLidar echo, SA31 / TC-37)',
        'scene': 'smiley',
        'stack': [('colour_ramp', {'maskin': 'actor', 'attr': 'height', 'lo': -0.3, 'hi': 0.3, 'ramp': 'palette',
                                   'emission': 1.5}),
                  ('colour_adjust', {'maskin': 'scene', 'exposure': -1.5, 'saturation': 0.5})],
        'core': {'Actormode': 'gen', 'Actorgen': 'cylinder', 'Actorcount': 6144, 'Actorgenp': 0.08, 'Actorgenp2': 0.25,
                 'Actorfollow': 'Ewk', 'Echoes': 6, 'Echoevery': 5, 'Echofade': 1.2, 'Echooffset': (0.0, 0.0, 0.0),
                 'Palsource': 'cyan_magenta', 'Bloom': 0.7},
        'effectors': [('Ewk', 'null', {}, {'Motion': 'lissajous', 'Ma': (0.0, 0.0, 0.0), 'Mb': (0.4, 0.05, 0.3),
                                            'Mfreq': (1.0, 2.0, 1.0), 'Mperiod': 12.0})]},
    'Glyph city': {
        'about': 'the street drawn as glowing letter tiles, denser glyphs where it is brighter (Avatara glyph tiles, '
                 'K21)',
        'scene': 'truck',
        'stack': [('colour_ramp', {'attr': 'luma', 'lo': 0.05, 'hi': 0.8, 'ramp': 'palette', 'emission': 0.4})],
        'core': {'Render': 'sprites', 'Quality': 'high', 'Sprite': 'glyph', 'Glyphmode': 'luma', 'Size': 0.012,
                 'Minpx': 5.0, 'Palsource': 'neon_green', 'Bloom': 0.25, 'Blend': 'alpha'}},
    'Pointillist': {
        'about': 'the scan painted with warm, jittered brush dabs in a soft haze (Andy Shauf "Clove Cigarette", SA35)',
        'scene': 'truck',
        'stack': [('colour_adjust', {'saturation': 1.3, 'exposure': 0.2})],
        'core': {'Render': 'sprites', 'Quality': 'high', 'Sprite': 'dab', 'Size': 0.03, 'Softness': 0.7,
                 'Dabjitter': 1.5, 'Blend': 'alpha', 'Vhon': True, 'Vhambient': 0.35, 'Vhdensity': 0.04,
                 'Vhshafts': 0.0, 'Vhcol': (1.0, 0.8, 0.6), 'Vhcolsrc': 'solid', 'Vhextinction': 0.2, 'Bloom': 0.3}},
    'Spiral reveal': {
        'about': 'the scene unrolls along a helix, fragments lingering then swirling away, and re-forms (Spark Unroll, '
                 'SA19 / SA20)',
        'scene': 'smiley',
        'stack': [('dissolve_gradient', {'effectors': '', 'axis': 'spiral', 'range': 0.6, 'pitch': 0.25, 'soft': 0.08,
                                         'warp': 0.05, 'linger': 0.08, 'swirl': 1.5, 'up': 0.4, 'release': 0.3,
                                         'drive': 'progress:lfo1*0.85'})],
        'core': {'Lfo1rate': 0.06, 'Lfoshape': 'tri', 'Disrecover': 1.0, 'Bloom': 0.5, 'Edgegain': 4.0,
                 'Edgecolsrc': 'palette', 'Palsource': 'neon_trio'}},
    'kNN lace sweep': {
        'about': 'a faint wire lace between neighbouring points of the whole scan (voxel index, any point count), lit '
                 'where a scan plane sweeps across it (LiDAR scan look, SA33)',
        'scene': 'truck',
        'stack': [('colour_adjust', {'exposure': -2.0, 'saturation': 0.3})],
        'core': {'Lineson': True, 'Palsource': 'cyan_magenta', 'Bloom': 0.8},
        'lines': {'Rings': False, 'Contour': False, 'Connect': True, 'Cnindex': 'grid', 'Cngrid': 64, 'Cnpoints': 49152,
                  'Maxseg': 147456, 'Cnk': 3, 'Cnradius': 0.16,
                  'Width': 1.0, 'Halo': 0.0, 'Intensity': 2.0, 'Linecolsrc': 'palette', 'Linepalpos': 0.2,
                  'Maskmode': 'front', 'Maskop': 'effectors/Elc', 'Masksoft': 0.4, 'Bgdim': 0.3},
        'effectors': [('Elc', 'plane', {'rz': -90.0, 'sx': 6.0, 'sz': 6.0},
                       {'Motion': 'line', 'Ma': (-4.0, 0.0, 0.0), 'Mb': (4.0, 0.0, 0.0), 'Mperiod': 10.0,
                        'Mloop': 'pingpong', 'Mease': 'linear', 'Glow': True, 'Glowsize': 0.05,
                        'Glowcolour': (0.3, 0.9, 1.0), 'Glowintensity': 1.0})]},
    # ---- wave 4 looks (27 Oct)
    'Grass field': {
        'about': 'the scan drawn as grass blades swaying in a curl-noise wind (P459 lidar terrain as blades, K22)',
        'scene': 'truck',
        'stack': [('strands', {'length': 2.5, 'lengthvar': 0.6, 'thin': 0.95, 'sway': 0.7, 'swayscale': 1.5,
                               'swayspeed': 0.5}),
                  ('colour_ramp', {'attr': 'height', 'lo': -1.2, 'hi': 1.2, 'ramp': 'palette', 'emission': 0.0})],
        'core': {'Palsource': 'neon_green', 'Bloom': 0.2, 'Exposure': -0.8}},
    'Painting pillars': {
        'about': 'a painting as pillars of light, taller where it is brighter, rolling in a wave (L9 voxel painting, '
                 'K27; Van Gogh "The Starry Night", public domain, media/demo/paintings)',
        'nosplat': True,                             # an image source: no splat version
        'stack': [('strands', {'up': (0.0, 0.0, 1.0), 'length': 30.0, 'lengthvar': 0.0, 'thin': 0.3, 'sway': 0.0,
                               'bylum': 1.0}),
                  ('wave', {'type': 'ripple', 'amp': 0.12, 'freq': 2.0, 'speed': 1.5, 'axis': 'z'})],
        'core': {'Amode': 'image', 'Imagefile': DEMO_IMAGES + '/starry_night_1280.jpg', 'Pointstop': '',
                 'Imagerelief': 0.35, 'Imagesrc': 'luma', 'Imagecut': 0.0, 'Bmode': 'off', 'Morph': 0.0,
                 'Quality': 'custom', 'Count': 262144, 'Render': 'sprites', 'Sprite': 'square', 'Size': 0.004,
                 'Minpx': 1.0, 'Maxpx': 32.0, 'Ascale': 1.0, 'Arot': 0.0, 'Aoffsetx': 0.0, 'Aoffsety': 0.0,
                 'Aoffsetz': 0.0, 'Camdist': 3.2, 'Camheight': 0.9, 'Orbit': 4.0, 'Focus': 3.2, 'Aperture': 0.0,
                 'Actormode': 'off', 'Pool': 0.0, 'Echoes': 0, 'Bloom': 0.25, 'Bright': 0.8, 'Exposure': -0.4}},
}


# Built-in looks are WHOLE looks (T-124: partial presets inherit what the previous one left): every Look / Grade par
# goes to its default, then BUILT_LOOK (the shared starting grade of the built-ins), then the look's own core. Scene
# pars stay with the scene: camera, resolution, render mode, sort, splat, point size and opacity, focus.
LOOK_SCENE_KEYS = {'Camdist', 'Orbit', 'Camheight', 'Fov', 'Resolution', 'Resx', 'Resy', 'Render', 'Sortmode', 'Sorteveryn', 'Sortmaxhz',
                   'Sortmovedeg', 'Sortnow', 'Splataa', 'Splatthr', 'Splatlowpass', 'Splatscalemult', 'Splatmaxpx', 'Size', 'Minpx', 'Maxpx',
                   'Attenuation', 'Ptopacity', 'Ptcut', 'Focus', 'Aperture', 'Maxcoc', 'Camsource', 'Camcomp'}
BUILT_LOOK = {'Blend': 'alpha', 'Bright': 2.0, 'Alpha': 1.0, 'Exposure': 0.3, 'Saturation': 1.3, 'Softness': 0.35,
              'Haze': 0.02, 'Bloom': 0.5, 'Vignette': 0.25, 'Grain': 0.015}


def look_defaults():
    out = {}
    for pg, pars in CORE_PAGES:
        if pg not in ('Look', 'Grade') + NEW_PAGES or pg == 'Lights':
            continue
        for nm, style, default, _o in pars:
            if style in ('Pulse',) or nm in LOOK_SCENE_KEYS:
                continue
            out[nm] = tuple(default) if isinstance(default, (list, tuple)) else default
    return out


def builtin_preset(name):
    """BUILTIN[name] -> a preset snapshot (stack uids 1.., values by TD par name, effector transforms + settings,
    make = effectors to create)."""
    d = BUILTIN[name]
    st, vals = [], look_defaults()
    vals.update(BUILT_LOOK)
    if d.get('scene'):                              # wave 2 looks are whole scenes (splat file, camera, Render)
        vals.update(SPLAT_SCENES[d['scene']])
        vals['Bright'] = float(BUILT_LOOK.get('Bright', 1.0)) * SPLAT_BRIGHT
        vals['Echoes'] = 0                          # wave 3 Source-page extras back to off (whole scenes)
    vals.update(d.get('core', {}))
    for t, v in d['stack']:
        st, uid = add_module(st, t)
        # whole looks (T-124 / T-195): every module param the look leaves out goes to its default, so a uid that a
        # previous look used for the same module type does not keep that look's values (wave 4: strands `up` / `bylum`)
        for k, x in instance_defaults(st[find(st, uid)]).items():
            vals[par_name(uid, k)] = '' if k == 'effectors' else (tuple(x) if isinstance(x, list) else x)
        for k, x in v.items():
            vals[par_name(uid, k)] = x
    flat = {}
    for k, x in vals.items():                       # xyz / rgb tuples -> TD component names
        if isinstance(x, tuple):
            p = None
            if k.startswith('M') and k[1:2].isdigit():
                uid = int(re.match(r'M(\d+)', k).group(1))
                inst = st[find(st, uid)]
                p = param(inst['type'], k[len('M%d' % uid):])
            suf = 'rgb' if (p is not None and p['kind'] == 'rgb') or (p is None and _is_rgb_core(k)) else 'xyz'
            for s_, c in zip(suf, x):
                flat[k + s_] = c
        else:
            flat[k] = x
    eff = {}
    effpars = {}
    make = []
    for en, kind, xf, ep in d.get('effectors', []):
        make.append([en, kind])
        full = dict(zip(XF_KEYS, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0)))
        full.update(xf)
        if kind not in ('chop', 'actor', 'camera'):
            eff[en] = [float(full[k]) for k in XF_KEYS]
        full_ep = dict((n_, tuple(d_) if isinstance(d_, (list, tuple)) else d_) for n_, st_, d_, _o in EFF_PARS
                       if st_ != 'Pulse')
        full_ep.update(ep)                          # whole effector settings: a glow / trail left by the last look is
        effpars[en] = full_ep                       # reset on recall (T-124 (1) for effectors, splat lane 27 Oct)
    lights = [list(x[:5]) + [x[5], dict(x[6])] for x in d.get('lights', [])]
    geo = [[g[0], g[1], dict(g[2]), list(g[3]), g[4], g[5], g[6]] for g in d.get('geo', [])]
    lines = dict((k, list(v) if isinstance(v, tuple) else v) for k, v in d.get('lines', {}).items()) \
        if 'lines' in d else None
    return snapshot(st, flat, eff, name, effpars, make, lights=lights, geo=geo, lines=lines)


# ---- splat versions of the looks (27 Oct, splat lane; requirement 6 / 9.9): the same look on a Gaussian splat scene.
# A splat version = the scene (source file + Render splats + count + camera) then the look's own values on top; the
# preset is named '<look> (splats)'. Scene None = the look keeps its own source (v1 presets carry Afile) + Render splats.
DEMO_SPLATS = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/demo/splats'
TD_SPLATS = '/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/PointClouds'
SPLAT_SCENES = {
    'truck': {'Amode': 'file', 'Afile': DEMO_SPLATS + '/truck.splat', 'Bmode': 'off', 'Morph': 0.0, 'Quality': 'custom',
              'Count': 524288, 'Splatmaxpx': 48.0,
              'Render': 'splats', 'Ascale': 1.0, 'Arot': 0.0, 'Aoffsetx': 0.0, 'Aoffsety': 1.2, 'Aoffsetz': 0.0,
              'Clip': 3.0, 'Opacitymin': 0.06, 'Camdist': 4.4, 'Camheight': 0.6, 'Orbit': 0.0, 'Focus': 3.4,
              'Aperture': 0.2, 'Actormode': 'off', 'Pool': 0.0, 'Sortmode': 'auto'},
    'smiley': {'Amode': 'file', 'Afile': TD_SPLATS + '/SmileyPinata.spz', 'Bmode': 'off', 'Morph': 0.0,
               'Quality': 'custom', 'Count': 228287, 'Splatmaxpx': 0.0, 'Render': 'splats', 'Ascale': 1.0, 'Arot': 0.0,
               'Aoffsetx': 0.0,
               'Aoffsety': 0.0, 'Aoffsetz': 0.0, 'Clip': 0.0, 'Opacitymin': 0.0, 'Camdist': 1.3, 'Camheight': 0.15,
               'Orbit': 0.0, 'Focus': 1.3, 'Aperture': 0.0, 'Actormode': 'off', 'Pool': 0.0, 'Sortmode': 'auto'},
}
SPLAT_SUFFIX = ' (splats)'
SPLAT_LOOKS = [('KANDA swipe', 'truck'), ('Hanging streaks', 'truck'), ('Alley people fire', 'truck'),
               ('Radial blast', 'truck'), ('Slice bike', 'truck'), ('Tile city', 'truck'), ('ember_splat', None)]
# splats are opaque, full-size gaussians: the sprite looks' colour gain (BUILT_LOOK Bright 2, tuned for faint sprites)
# blows them out, and motion looks that swing the far scan past the camera (orbit, explode) fill the frame with near
# splats, so the splat versions halve Bright and clip the scan closer (live b5 captures + b4 lane, 27 Oct: Clip 3 for
# the truck: splats have no Maxpx cap, so near-camera ground splats fogged the lower frame at Clip 6).
SPLAT_BRIGHT = 0.5
SPLAT_TUNE = {'Slice bike': {'Clip': 2.2}, 'Tile city': {'Clip': 2.2},
              'ember_splat': {'Aperture': 2.0}}     # big DOF discs cost srender 5-10 ms (b4 lane)
SPLAT_SHOWCASE = ('splat_showcase', 'KANDA swipe', 'truck', {'E': {'Glow': True, 'Glowintensity': 1.5,
                                                                   'Glowsize': 0.15, 'Glowcolour': (1.0, 0.85, 0.7)}})


def splat_variant(snap, scene, name, glow=None, tune=None):
    """A look snapshot -> its splat version: scene values first, the look's values on top, Render = splats. glow =
    {'E': Effector-page values} adds glow to the look's first object effector (showcase)."""
    s = json.loads(json.dumps(snap))
    v = dict(SPLAT_SCENES[scene]) if scene else {}
    v.update(s['values'])
    v['Render'] = 'splats'
    v['Bright'] = float(v.get('Bright', 1.0)) * SPLAT_BRIGHT
    v.update(tune or {})
    s['values'] = v
    s['name'] = name
    if glow:
        objs = [m[0] for m in s.get('make', []) if m[1] not in ('chop', 'actor', 'camera')]
        if objs:
            s.setdefault('effpars', {}).setdefault(objs[0], {}).update(glow['E'])
    return s


def splat_presets(get=None):
    """[(name, snapshot)] of every splat version + splat_showcase. get(name) -> a stored (non built-in) snapshot or None
    (ember_splat lives in the preset table, made by px_looks); looks that are missing are skipped."""
    def base(nm):
        if nm in BUILTIN:
            return builtin_preset(nm)
        return get(nm) if get is not None else None
    out = []
    for nm, scene in SPLAT_LOOKS:
        b = base(nm)
        if b is not None:
            out.append((nm + SPLAT_SUFFIX, splat_variant(b, scene, nm + SPLAT_SUFFIX, tune=SPLAT_TUNE.get(nm))))
    sc, nm, scene, glow = SPLAT_SHOWCASE
    b = base(nm)
    if b is not None:
        out.append((sc, splat_variant(b, scene, sc, glow)))
    return out


def _is_rgb_core(name):
    for _pg, pars in CORE_PAGES:
        for n, style, _d, _o in pars:
            if n == name:
                return style == 'RGB'
    return False


# ---- phase C (28 Oct): auto quality, LOD by distance, sort only on change, external camera --------------------------
# Manual wins everywhere: auto quality never writes a par. It is a separate layer (the px_auto Constant CHOP: aa, countf,
# resf, kside) that the render expressions and the engine rows multiply in; the user's Splataa / Count / Resx / Resy stay
# as set and Aqstate shows what runs.

def lod_row(raw):
    """uR[9] / uSp[4]: (on, start distance, share kept far away, 0). Off = (0, ...): the shaders skip LOD entirely."""
    return [1.0 if _truthy(raw.get('Lod', False)) else 0.0, max(float(raw.get('Loddist', 6.0)), 1e-3),
            min(max(float(raw.get('Lodkeep', 0.35)), 0.01), 1.0), 0.0]


def lod_keep(z, dist, keep):
    """Share of points kept at view depth z (GLSL twin in px_vert / the splat adapter): 1 up to `dist`, falling
    linearly to `keep` at 2 x dist and beyond. A point is kept when its id hash < this; kept ones grow by
    1 / sqrt(share) (area kept)."""
    d = max(float(dist), 1e-3)
    f = min(max((float(z) - d) / d, 0.0), 1.0)
    return 1.0 + (min(max(float(keep), 0.01), 1.0) - 1.0) * f


def id_hash01(i):
    """The GLSL id hash (px_vert echo thinning / LOD): uniform in [0, 1)."""
    h = (int(i) * 2654435761 + 40503) & 0xFFFFFFFF
    h = (((h >> 16) ^ h) * 73244475) & 0xFFFFFFFF
    return ((h >> 8) & 0xFFFFFF) / 16777216.0


AQ_COUNTS = (0.75, 0.5)          # point fractions (exact in binary: the key texel -> id map floor(k / countf) is exact)
AQ_RES = (0.75, 0.5)             # render resolution fractions (post + out1 stay at Resx x Resy)
AQ_SETTLE = 30                   # frames ignored after a step (texture reallocation hitches)
AQ_EMA = 0.1                     # frame-time average weight
AQ_PX_PARS = (('Minpx', 0.7), ('Maxpx', 64.0), ('Streakmax', 64.0), ('Maxcoc', 48.0), ('Aperture', 0.0),
              ('Splatmaxpx', 0.0))
AQ_SIZE_PARS = (('Size', 0.01), ('Minpx', 0.7), ('Maxpx', 64.0), ('Splatscalemult', 1.0))


def aq_steps(raw, splats):
    """The auto-quality ladder for this look, mildest first: (force splat MSAA 1x, point fraction, resolution
    fraction). Step 0 = full quality. The MSAA step exists only when the render is splats and Splataa is above 1x."""
    out = [(False, 1.0, 1.0)]
    aa = bool(splats) and str(raw.get('Splataa', 'aa1')) != 'aa1'
    if aa:
        out.append((True, 1.0, 1.0))
    for cf in AQ_COUNTS:
        out.append((aa, cf, 1.0))
    for rf in AQ_RES:
        out.append((aa, AQ_COUNTS[-1], rf))
    return out


def gov_plan(q):
    """Autoquality governor: FG_fps_governor quality q (1 = full) -> (force splat AA 1x, point fraction, resolution
    fraction), the same rungs as aq_steps (twin of fps_gov_logic.px_plan, tested equal)."""
    q = float(q)
    return (q < 0.9, 1.0 if q >= 0.8 else (0.75 if q >= 0.65 else 0.5),
            1.0 if q >= 0.5 else (0.75 if q >= 0.35 else 0.5))


def aq_effect(steps, level):
    return steps[max(0, min(int(level), len(steps) - 1))]


def aq_res(w, h, resf=1.0):
    """Effective render size: the phase B clamp (larger side <= TEX_MAX), x resf (the auto-quality fraction). The same
    arithmetic as the TOP expressions (_RX_AQ), so Python and the TOPs agree to the pixel."""
    w, h = max(1, int(w)), max(1, int(h))
    k = min(1.0, float(TEX_MAX) / max(1, w, h))
    return max(1, int(w * k * resf)), max(1, int(h * k * resf))


def aq_raw(raw, countf=1.0, resf=1.0):
    """Core values the render / splat rows see at an auto-quality step (the user's pars are untouched): Resx / Resy x
    resf with the pixel sizes (Minpx, Maxpx, Streakmax, Maxcoc, Aperture, Splatmaxpx) scaled the same way, so the look
    keeps its proportions; with fewer points (countf) the kept ones grow by 1 / sqrt(countf) (Size, Minpx, Maxpx,
    Splatscalemult: covered area kept). Step 0 returns raw itself."""
    if countf >= 1.0 and resf >= 1.0:
        return raw
    r = dict(raw)
    if resf < 1.0:
        r['Resx'], r['Resy'] = aq_res(raw.get('Resx', 1080), raw.get('Resy', 1920), resf)
        for k, d in AQ_PX_PARS:
            r[k] = float(raw.get(k, d)) * resf
    if countf < 1.0:
        g = 1.0 / math.sqrt(max(float(countf), 1e-3))
        for k, d in AQ_SIZE_PARS:
            r[k] = float(r.get(k, d)) * g
    return r


def aq_key_side(end, countf):
    """Side of the sort-key texture at a point fraction: ceil(end x countf) keys; key texel k -> id floor(k / countf)
    (ids >= end read -1, culled), so the Sort POP and the splat instancing really get fewer points."""
    if countf >= 1.0:
        return side_for(max(1, int(end)))
    return side_for(max(1, int(math.ceil(float(end) * float(countf) - 1e-9))))


def aq_key_ids(end, countf, nkeys):
    """Python twin of px_sortkey.glsl's map: the ids the first nkeys key texels draw (-1 past the draw end)."""
    out = []
    for k in range(int(nkeys)):
        i = k if countf >= 1.0 else int(math.floor(k / float(countf)))
        out.append(i if i < end else -1)
    return out


def aq_new():
    return {'level': 0, 'fps': None, 'ms': None, 'below': 0, 'above': 0, 'hold': 0, 'upwait': 1.0,
            'last_down': -1e9, 'last_up': -1e9}


def aq_step(st, fps, ms, now, nsteps, thr=57.0, frames=45, headroom=10.0):
    """One frame of the controller (pure; plain data, so it can live in COMP storage). fps / ms = the Perform CHOP's
    fps and msec (frame cook time). Averages are exponential (AQ_EMA). Down one step after `frames` frames with the
    average fps under thr; up one step after 3 x frames x upwait frames with the average frame time under headroom ms
    while fps >= thr. A step up followed by a step down within 10 s doubles upwait (max 8x): no ping-pong. After any
    step AQ_SETTLE frames are ignored. -> (state, delta): +1 = one step down in quality, -1 = one step up, 0 = none."""
    st = dict(st or aq_new())
    st['fps'] = float(fps) if st.get('fps') is None else st['fps'] + (float(fps) - st['fps']) * AQ_EMA
    st['ms'] = float(ms) if st.get('ms') is None else st['ms'] + (float(ms) - st['ms']) * AQ_EMA
    if st.get('hold', 0) > 0:
        st['hold'] -= 1
        st['below'] = st['above'] = 0
        return st, 0
    lvl = int(st.get('level', 0))
    if st['fps'] < thr:
        st['below'] = st.get('below', 0) + 1
        st['above'] = 0
    elif st['ms'] < headroom:
        st['above'] = st.get('above', 0) + 1
        st['below'] = 0
    else:
        st['below'] = st['above'] = 0
    if st['below'] >= int(frames) and lvl < nsteps - 1:
        if now - st.get('last_up', -1e9) < 10.0:
            st['upwait'] = min(8.0, float(st.get('upwait', 1.0)) * 2.0)
        st.update(level=lvl + 1, last_down=now, hold=AQ_SETTLE, below=0, above=0, fps=None, ms=None)
        return st, 1
    if lvl > 0 and st['above'] >= int(3 * int(frames) * float(st.get('upwait', 1.0))):
        st.update(level=lvl - 1, last_up=now, hold=AQ_SETTLE, below=0, above=0, fps=None, ms=None)
        return st, -1
    return st, 0


def aq_label(steps, level, res=None, fps=None):
    """Aqstate text: 'step 2/5: points 75% (fps 52)'; 'full quality (0/5)' at step 0."""
    n = len(steps) - 1
    tail = (' (fps %.0f)' % fps) if fps is not None else ''
    if level <= 0:
        return 'full quality (0/%d)%s' % (n, tail)
    aa, cf, rf = aq_effect(steps, level)
    parts = []
    if aa:
        parts.append('splat AA 1x')
    if cf < 1.0:
        parts.append('points %d%%' % int(round(cf * 100)))
    if rf < 1.0:
        parts.append('res %d%%%s' % (int(round(rf * 100)), (' = %dx%d' % tuple(res)) if res else ''))
    return 'step %d/%d: %s%s' % (min(level, n), n, ', '.join(parts), tail)


# Clamp form of the render-chain TOPs (phase B _RX) -> the same x px_auto resf (phase C). post (grade, out1) and
# render_preview keep Resx x Resy: post samples a smaller input by uv, so out1 never changes size.
_RX_AQ = ("max(1, int(me.parent().par.Res{a}.eval() * min(1.0, %d.0 / max(1, me.parent().par.Resx.eval(), "
          "me.parent().par.Resy.eval())) * me.parent().op('px_auto')['resf']))" % TEX_MAX)
AQ_RES_SKIP = ('post', 'render_preview')


def aq_res_expr(expr):
    """Clamped Resx / Resy reads -> the auto-quality form; idempotent (the new form no longer contains the old)."""
    e = str(expr)
    for a in 'xy':
        old = _RX.format(a=a)
        if old in e:
            e = e.replace(old, _RX_AQ.format(a=a))
    return e


# Sort only on change: can anything move the point centres this frame? A module is "still" when, at its values, it is
# a pure function of the rest points, its values and the effector objects (no sim time, no live rate phase, no force
# that keeps points moving); unknown modules count as moving. Colour-stage modules never move centres.
def _nz(v):
    if isinstance(v, (tuple, list)):
        return any(float(x) != 0.0 for x in v)
    try:
        return float(v) != 0.0
    except (TypeError, ValueError):
        return bool(v)


def _mi(mtype, v, name):
    for p in MODULES[mtype]['params']:
        if p['name'] == name:
            return menu_index(p['menu'], v.get(name, p['default']))
    return 0


def _zero(v, *names):
    return not any(_nz(v.get(n, 0.0)) for n in names)


STILL_RULES = {
    'prox_push': lambda v: _mi('prox_push', v, 'mode') == 0,                # displace (force keeps points moving)
    'prox_vortex': lambda v: _mi('prox_vortex', v, 'mode') == 1,            # twist (an angle, not a flow)
    'prox_dissolve': lambda v: _zero(v, 'curl', 'release'),
    'prox_magnet': lambda v: True,
    'prox_stretch': lambda v: True,
    'curl': lambda v: _mi('curl', v, 'mode') == 1 or _zero(v, 'strength'),  # displace on the rest field
    'wind': lambda v: _zero(v, 'gravity', 'wind', 'buoyancy'),
    'orbit': lambda v: True,                                                 # its speed is a rate (checked first)
    'twist': lambda v: True,                                                 # wobblespeed: a rate, gated by wobble
    'explode': lambda v: True,                                               # progress static while auto is off
    'wave': lambda v: True,                                                  # speed: a rate, gated by amp
    'jitter': lambda v: _mi('jitter', v, 'mode') == 2 or _zero(v, 'amp', 'rate'),
    'glitch': lambda v: _zero(v, 'offset') or _zero(v, 'prob'),
    'audio_displace': lambda v: _zero(v, 'amp', 'beatkick'),
    'shockwave': lambda v: _zero(v, 'amp'),
    'dissolve_noise': lambda v: _zero(v, 'curl', 'up', 'release') or (not _nz(v.get('progress', 0.0))
                                                                      and not _nz(v.get('bias', (0.0, 0.0, 0.0)))),
    'dissolve_gradient': lambda v: _zero(v, 'curl', 'up', 'release', 'swirl'),
    'dissolve_time': lambda v: _zero(v, 'curl', 'up', 'release'),           # its rate is a rate (checked first)
    'heat_spread': lambda v: True,                                           # heat only (colour; wind reads heat)
}
RATE_GATES = {'twist': {'wobblespeed': 'wobble'}, 'wave': {'speed': 'amp'}}   # a rate that moves nothing at 0 x
NOOP_RULES = {                                       # the module does nothing at these values (its rates do not matter)
    'curl': lambda v: _zero(v, 'strength') if _mi('curl', v, 'mode') == 0 else _zero(v, 'distance'),
    'wave': lambda v: _zero(v, 'amp'),
    'jitter': lambda v: _zero(v, 'amp'),
}


def module_still(mtype, v):
    """True when this enabled module cannot keep the centres moving at these values (see STILL_RULES)."""
    m = MODULES.get(mtype)
    if m is None:
        return False
    if mtype in MOVING_EXCLUDE or 'update' not in m['stages']:
        return True
    if not _nz(v.get('amount', 1.0)):
        return True
    noop = NOOP_RULES.get(mtype)
    if noop is not None and noop(v):
        return True
    gates = RATE_GATES.get(mtype, {})
    for p in m['params']:
        if rate_live(mtype, v, p) and _nz(v.get(gates.get(p['name'], p['name']), 1.0)):
            return False
    rule = STILL_RULES.get(mtype)
    return bool(rule(v)) if rule is not None else False


def stack_motion(items, dt, eff_moving=False, src_moving=False):
    """items = [(type, values, drives)] of the enabled, compiled stack. True when the centres can move this frame:
    a drive on an update module, an effector moving (any update module reads the effectors), the source moving
    (spin / depth / actor), or a module that is not still; nothing moves while the sim is paused (dt 0) except by
    drives and effectors."""
    upd = [(t, v, d) for t, v, d in items if t in MODULES and 'update' in MODULES[t]['stages']
           and t not in MOVING_EXCLUDE]
    if any(d for _t, _v, d in upd):
        return True
    if eff_moving and upd:
        return True
    if dt <= 0.0:
        return False
    if src_moving:
        return True
    return not all(module_still(t, v) for t, v, _d in upd)


def settle_s(raw):
    """Seconds points keep moving after the last change (spring + damping): to ~2 % amplitude, 7.8 / (Damping +
    Drag), between 1 and 8 s. Sorts keep their every-N rhythm for this long after anything changed."""
    b = float(raw.get('Damping', 1.5)) + float(raw.get('Drag', 0.2))
    return min(8.0, max(1.0, 7.8 / max(b, 0.1)))


# Usecam: an external Camera COMP -> PX's engine camera row (tx ty tz ry rx rz; rotate order xyz, R = Rz Ry Rx, as
# cam_basis reads it). From the camera's world axes, so any rord / parent / look-at the external COMP uses is kept.
def basis_row(pos, right, up, back):
    def n(v):
        ln = math.sqrt(sum(float(x) * float(x) for x in v)) or 1.0
        return [float(x) / ln for x in v]
    X, Y, Z = n(right), n(up), n(back)
    s = max(-1.0, min(1.0, -X[2]))
    ry = math.asin(s)
    if abs(s) < 0.999999:
        rx = math.atan2(Y[2], Z[2])
        rz = math.atan2(X[1], X[0])
    else:                                            # gimbal: ry = +-90, rz folded into rx
        rz = 0.0
        rx = math.atan2(Y[0], Y[1]) if s > 0 else math.atan2(-Y[0], Y[1])
    return [float(pos[0]), float(pos[1]), float(pos[2]), math.degrees(ry), math.degrees(rx), math.degrees(rz)]


def hfov_from_proj(p00):
    """Horizontal fov (deg, PX's Fov meaning) from a projection matrix's [0][0] (Camera COMP .projection(w, h))."""
    return math.degrees(2.0 * math.atan(1.0 / max(float(p00), 1e-6)))


def cam_menu_items(paths, own_prefix=''):
    """Camcomp dropdown: Camera COMP paths (sorted), minus PX's own cameras (inside own_prefix)."""
    return sorted(p for p in paths if not (own_prefix and (p == own_prefix or p.startswith(own_prefix + '/'))))


# ---- splat sort gate (S1): when the splat order must be rebuilt

MOVING_EXCLUDE = ('mask_region', 'mask_image', 'mask_attr')


def stack_moves(stack):
    """True when an enabled module can move point centres (any update-stage module except the masks)."""
    for i in stack:
        if i['enabled'] and 'update' in MODULES[i['type']]['stages'] and i['type'] not in MOVING_EXCLUDE:
            return True
    return False


def sort_due(mode, frame, last_frame, every_n, moving, cam_due, pulse=False, data_changed=False, since_s=None,
             max_hz=0.0):
    """auto: pulse / data change / camera gate (cam_due = splat_render_logic.need_sort, the BL gate) / every N frames
    while centres move. always: every frame. frozen: pulse / data change. off: never (additive, no order).
    frame / last_frame count ENGINE frames (cooks), not absTime frames (T-143: under load absTime skips 3-4 frames per
    cook, so 'every 2 frames' sorted on every cook). auto also waits >= 1 / max_hz s since the last sort (Sortmaxhz;
    pulse / data change ignore the cap)."""
    if mode == 'off':
        return False
    if pulse or data_changed or last_frame is None:
        return True
    if mode == 'always':
        return True
    if mode == 'frozen':
        return False
    if max_hz and max_hz > 0 and since_s is not None and since_s < 1.0 / max_hz:
        return False
    if moving and every_n > 0 and frame - last_frame >= every_n:
        return True
    return bool(cam_due)


# ----------------------------------------------------------------------------------------------- perf model

BL_SPLATS = 228287          # SmileyPinata.spz, BL_splat_render live (f6ecc8f): render 4.2 ms, sort 3.0 ms on ticks


def perf_model(n, resx=1080, resy=1920, avg_px=3.0, render='sprites', sort_every=2, pts=0, actor_samples=0):
    """Order-of-magnitude budget (NOT a measurement). Compute bytes from the texel layout; render cost scaled
    from our own live numbers on this Mac (T-84: 262k instanced sprites = 3.0 ms GPU + 1.07 ms CPU; T-89: 200k
    = 1.66 GPU + 1.47 CPU; BL_splat_render: 228k splats render 4.2 ms, Sort POP 3.0 ms per sort). Splats: sort
    amortised over sort_every frames (every frame when 1; the spike itself is 3.0 ms x n / 228k). pts /
    actor_samples: point-set effector points scanned per point (brute force) -> extra update ms at an assumed
    ~40 G point-pairs/s. Returns ms estimates per part."""
    side = side_for(n)
    slots = side * side
    upd = slots * 16 * (STATE_TEXELS * 2 + 3)              # read+write state, read rest p0/c0/q
    col = slots * 16 * (STATE_TEXELS + 2 + LOOK_TEXELS)    # read state + rest, write look
    bw = 200e9                                             # effective bytes/s assumed on M1 Max under MoltenVK
    if render == 'splats':
        render_gpu = 4.2 * n / float(BL_SPLATS)
        sort_ms = 3.0 * n / float(BL_SPLATS)
        sort_avg = sort_ms / max(int(sort_every), 1)
        keys_ms = slots * 16 * (1 + 1) / bw * 1e3 + 0.05    # sort_keys compute (read P, write key)
    else:
        render_gpu = 3.0 * n / 262144.0 * max(avg_px / 3.0, 0.5)
        sort_ms = sort_avg = keys_ms = 0.0
    render_cpu = 1.07 + 0.0 * n                            # instancing submit is ~flat (one draw)
    post = 0.5 * (resx * resy) / (1080 * 1920)
    pts_ms = n * float(pts + actor_samples) / 40e9 * 1e3
    upd_ms = upd / bw * 1e3 + 0.05 + pts_ms
    col_ms = col / bw * 1e3 + 0.05
    total = upd_ms + col_ms + render_gpu + render_cpu + post + sort_avg + keys_ms
    return {'n': n, 'side': side, 'render': render, 'update_bytes': upd, 'colour_bytes': col,
            'update_ms': round(upd_ms, 3), 'colour_ms': round(col_ms, 3), 'render_gpu_ms': round(render_gpu, 2),
            'render_cpu_ms': render_cpu, 'post_ms': round(post, 2), 'sort_spike_ms': round(sort_ms, 2),
            'sort_avg_ms': round(sort_avg, 2), 'sort_keys_ms': round(keys_ms, 3), 'pts_ms': round(pts_ms, 3),
            'total_ms': round(total, 2),
            'state_mb': round(slots * 16 * (STATE_TEXELS * 2 + REST_TEXELS * 3 + LOOK_TEXELS) / 1048576.0, 1)}


def max_count_for(budget_ms=3.0, resx=1080, resy=1920):
    n = 1024
    while perf_model(n * 2, resx, resy)['total_ms'] <= budget_ms and n < (1 << 24):
        n *= 2
    return n


# ----------------------------------------------------------------------------------------------- numpy reference
# Mirrors px_common.glsl / px_source.glsl / selected modules (float64 here, float32 on the GPU).

def _np():
    import numpy
    return numpy


def np_hash(x):
    np = _np()
    x = np.asarray(x, dtype=np.uint64) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    x = (x * 0x7feb352d) & 0xFFFFFFFF
    x = x ^ (x >> 15)
    x = (x * 0x846ca68b) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return x


def ref_strands(ids, length, lengthvar, up=(0.0, 1.0, 0.0)):
    """K22 strands with sway 0 and G 1: (stretch (n,), sdir (3,)) = length (1 - lengthvar rnd(id, 71)), up."""
    import numpy as np
    u = np.asarray(up, dtype=np.float64)
    n = np.linalg.norm(u)
    return length * (1.0 - lengthvar * np_rnd(ids, 71)), (u / n if n > 1e-12 else np.array([0.0, 1.0, 0.0]))


def ref_sound(P, V, dis, count, side, bbcy, bbr):
    """K34 mirror of px_sound.glsl + Analyze average: (mean speed, mean dissolve, mean height (y - bbcy) / bbr) of the
    first `count` points (P, V (n, 3), dis (n,))."""
    import numpy as np
    n = int(count)
    sp = np.linalg.norm(np.asarray(V, dtype=np.float64)[:n], axis=1)
    h = (np.asarray(P, dtype=np.float64)[:n, 1] - bbcy) / max(bbr, 1e-6)
    return float(sp.mean()), float(np.asarray(dis, dtype=np.float64)[:n].mean()), float(h.mean())


def sound_freqs(speed, dis, height, pitch=1.0, drone=1.0, shimmer=0.5, noise=0.3, full=2.0):
    """K34 mapping (the oscillator expressions in px.py _sound): -> {osc: (frequency Hz, amplitude)}."""
    x = min(max(speed / max(full, 1e-6), 0.0), 1.0)
    h = min(max(height, -1.0), 1.0)
    return {'drone': (55.0 * pitch * 2.0 ** (1.0 + h), 0.5 * drone * (1.0 - min(max(dis, 0.0), 1.0))),
            'shimmer': (220.0 * pitch * (1.0 + 3.0 * x), 0.3 * shimmer * x),
            'noise': (0.0, 0.3 * noise * min(max(dis, 0.0), 1.0))}


def np_rnd(idx, salt):
    np = _np()
    i = np.asarray(idx, dtype=np.uint64)
    return (np_hash((i * 2654435761 + salt) & 0xFFFFFFFF) >> 8).astype(np.float64) / 16777216.0


def np_weyl(idx, k):
    np = _np()
    i = np.asarray(idx, dtype=np.uint64)
    return (((i * k) & 0xFFFFFFFF) >> 8).astype(np.float64) / 16777216.0


def np_lattice(c, seed):
    np = _np()
    c = np.asarray(c, dtype=np.int64) & 0xFFFFFFFF
    h = ((c[..., 0] * 73856093) & 0xFFFFFFFF) ^ ((c[..., 1] * 19349663) & 0xFFFFFFFF) ^ ((c[..., 2] * 83492791) & 0xFFFFFFFF)
    h = h ^ ((seed * 2654435761) & 0xFFFFFFFF)
    return (np_hash(h.astype(np.uint64)) >> 8).astype(np.float64) / 16777216.0


def np_noise(p, seed):
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    i = np.floor(p)
    f = p - i
    u = f * f * (3.0 - 2.0 * f)
    c = i.astype(np.int64)
    n = {}
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                n[(dx, dy, dz)] = np_lattice(c + np.array([dx, dy, dz]), seed)
    lx = lambda a, b: a + (b - a) * u[..., 0]
    y0 = n[(0, 0, 0)] + (n[(1, 0, 0)] - n[(0, 0, 0)]) * u[..., 0]
    y1 = n[(0, 1, 0)] + (n[(1, 1, 0)] - n[(0, 1, 0)]) * u[..., 0]
    y2 = lx(n[(0, 0, 1)], n[(1, 0, 1)])
    y3 = lx(n[(0, 1, 1)], n[(1, 1, 1)])
    z0 = y0 + (y1 - y0) * u[..., 1]
    z1 = y2 + (y3 - y2) * u[..., 1]
    return z0 + (z1 - z0) * u[..., 2]


def np_fbm(p, oct, seed):
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    a, s, n = 0.5, 0.0, 0.0
    for o in range(min(int(oct), 6)):
        s = s + a * np_noise(p, seed + o * 101)
        n += a
        p = p * 2.0 + np.array([17.1, 3.7, 9.3])
        a *= 0.5
    return s / n if n > 0 else np.full(p.shape[:-1], 0.5)


PXK = [(1.31, 1.73, -0.67), (-1.11, 0.53, 1.97), (0.79, -1.63, 1.21), (1.89, -0.41, 0.93), (-0.57, 1.37, -1.49),
       (1.07, 1.19, 1.51), (-1.71, -0.83, 0.47), (0.61, 1.91, -1.03), (1.43, -1.27, -0.89)]
PXW = [0.31, -0.47, 0.23, 0.53, -0.29, 0.41, -0.37, 0.19, 0.44]


def np_psi(p, t):
    """The curl potential psi (3 components), for the divergence check."""
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    K = np.array(PXK)
    out = []
    for c in range(3):
        s = 0.0
        for k in range(3):
            j = 3 * c + k
            s = s + np.sin(p @ K[j] + PXW[j] * t + j)
        out.append(s)
    return np.stack(out, -1)


def np_curl1(p, t):
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    K = np.array(PXK)
    g = []
    for c in range(3):
        s = 0.0
        for k in range(3):
            j = 3 * c + k
            s = s + K[j] * np.cos(p @ K[j] + PXW[j] * t + j)[..., None]
        g.append(s)
    return 0.25 * np.stack([g[2][..., 1] - g[1][..., 2], g[0][..., 2] - g[2][..., 0], g[1][..., 0] - g[0][..., 1]], -1)


def np_curl(p, t, oct):
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    s, a, sc, n = 0.0, 1.0, 1.0, 0.0
    for o in range(min(int(oct), 4)):
        s = s + a * np_curl1(p * sc + o * np.array([5.3, 1.7, 3.1]), t)
        n += a
        a *= 0.5
        sc *= 2.0
    return s / n if n > 0 else np.zeros_like(p)


def ref_sd_shape(ty, q, s):
    np = _np()
    q = np.asarray(q, dtype=np.float64)
    if ty == 1:
        return np.linalg.norm(q, axis=-1) - s[0]
    if ty == 2:
        d = np.abs(q) - np.asarray(s[:3])
        return np.linalg.norm(np.maximum(d, 0.0), axis=-1) + np.minimum(np.max(d, axis=-1), 0.0)
    if ty == 3:
        return q[..., 1]
    if ty == 4:
        q = q.copy()
        q[..., 1] -= np.clip(q[..., 1], -s[1], s[1])
        return np.linalg.norm(q, axis=-1) - s[0]
    if ty == 5:
        d0 = np.linalg.norm(q[..., [0, 2]], axis=-1) - s[0]
        return np.sqrt(d0 * d0 + q[..., 1] ** 2) - s[1]
    return np.linalg.norm(q, axis=-1)


def ref_effector_sd(erows, i, p):
    np = _np()
    E = np.asarray(erows, dtype=np.float64)
    b = i * E_PER
    h = np.concatenate([np.asarray(p, dtype=np.float64), np.ones(np.shape(p)[:-1] + (1,))], -1)
    q = np.stack([h @ E[b], h @ E[b + 1], h @ E[b + 2]], -1)
    return ref_sd_shape(int(round(E[b + 3][0])), q, E[b + 3][1:]) * E[b + 4][3]


def ref_fall(d, R, k, shape):
    np = _np()
    d = np.asarray(d, dtype=np.float64)
    R = max(R, 1e-5)
    k = max(k, 1e-3)

    def ss(e0, e1, x):
        t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)
    if shape == 1:
        return np.clip(1.0 - np.maximum(d, 0.0) / R, 0.0, 1.0) ** k
    if shape == 2:
        x = np.maximum(d, 0.0) / R
        return np.exp(-4.0 * k * x * x)
    if shape == 3:
        return (d < R).astype(np.float64)
    if shape == 4:
        return (1.0 - ss(0.0, R, np.abs(d))) ** k
    if shape == 5:
        return ss(0.0, R, -d) ** k
    return (1.0 - ss(0.0, R, np.maximum(d, 0.0))) ** k


def ref_prox_w(p, erows, em, ecount, R, k, shape=0, comb=0):
    """pxW without the noise edge."""
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    w = np.ones(p.shape[:-1]) if comb == 2 else np.zeros(p.shape[:-1])
    any_ = False
    for i in range(min(ecount, MAX_EFF)):
        if not (em >> i) & 1:
            continue
        any_ = True
        wi = ref_fall(ref_effector_sd(erows, i, p), R, k, shape)
        if comb == 1:
            w = w + wi
        elif comb == 2:
            w = w * wi
        elif comb == 3:
            w = w + wi - w * wi
        else:
            w = np.maximum(w, wi)
    return w if any_ else np.zeros(p.shape[:-1])


def ref_push_displace(p, erows, em, ecount, R, k, strength, shape=0, gain=1.0):
    """prox_push, mode displace, dir outward, one effector of type point/sphere (gradient = centre direction)."""
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    w = gain * ref_prox_w(p, erows, em, ecount, R, k, shape)
    i = next(j for j in range(ecount) if (em >> j) & 1)
    c = np.asarray(erows[i * E_PER + 4][:3])
    d = p - c
    n = d / np.maximum(np.linalg.norm(d, axis=-1, keepdims=True), 1e-12)
    return p + n * (strength * w)[..., None]


def ref_move_dir(erows, i):
    """Effector motion direction: unit velocity (row 6), else its up axis (row 5)."""
    np = _np()
    E = np.asarray(erows, dtype=np.float64)
    v = E[i * E_PER + 6][:3]
    if np.linalg.norm(v) > 1e-4:
        return v / np.linalg.norm(v)
    a = E[i * E_PER + 5][:3]
    return a / max(np.linalg.norm(a), 1e-8)


def ref_front(p, erows, i, R, k, shape, edge=0.02, noise=0.0):
    """Falloff shapes 6 behind / 7 ahead (pxFront): a front through the effector centre, perpendicular to its motion.
    s = (p - c).m (+ noise); behind: s > 0 (ahead of the front) drops to 0 over edge x R, s <= 0 decays over R
    ((1 + s/R)^k); ahead mirrors it."""
    np = _np()
    E = np.asarray(erows, dtype=np.float64)
    c = E[i * E_PER + 4][:3]
    m = ref_move_dir(erows, i)
    s = (np.asarray(p, dtype=np.float64) - c) @ m + noise
    if shape == 7:
        s = -s
    R = max(R, 1e-5)
    e = max(edge * R, 1e-5)
    lead = 1.0 - _np_ss(0.0, e, s)
    tail = np.clip(1.0 + s / R, 0.0, 1.0) ** max(k, 1e-3)
    return np.where(s > 0.0, lead, tail)


def _np_ss(e0, e1, x):
    np = _np()
    t = np.clip((np.asarray(x, dtype=np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ref_wake(p, c, trail, R, k, rshape=0.0):
    """Falloff shape 8 (pxWake): tube of radius R around the polyline centre -> trail[0] -> trail[1] ... (trail =
    [(xyz, age s)] newest first; age normalised by the oldest). w = (1 - ss(0, R, d - rshape)) (1 - age)^k."""
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    pts = [(np.asarray(c, dtype=np.float64), 0.0)] + [(np.asarray(q, dtype=np.float64), float(a)) for q, a in trail]
    amax = max(max(a for _q, a in pts), 1e-6)
    w = np.zeros(p.shape[:-1])
    for (a, aa), (b, ab) in zip(pts[:-1], pts[1:]):
        ab_ = b - a
        L2 = max(float(ab_ @ ab_), 1e-12)
        u = np.clip(((p - a) @ ab_) / L2, 0.0, 1.0)
        q = a + u[..., None] * ab_
        d = np.linalg.norm(p - q, axis=-1)
        age = (aa + (ab - aa) * u) / amax
        wi = (1.0 - _np_ss(0.0, max(R, 1e-5), d - rshape)) * np.clip(1.0 - age, 0.0, 1.0) ** max(k, 1e-3)
        w = np.maximum(w, wi)
    return w


def ref_pts_nearest(p, pts, vel=None, radius=0.02, mode=0):
    """Point-set distance (pxPtsNear): nearest |p - q| - radius, and the nearest point's velocity; mode 1 (density):
    d = -radius ln(sum exp(-|p - q|^2 / (2 radius^2)))."""
    np = _np()
    p = np.asarray(p, dtype=np.float64)
    Q = np.asarray(pts, dtype=np.float64)
    d2 = ((p[:, None, :] - Q[None, :, :]) ** 2).sum(-1)
    j = np.argmin(d2, axis=1)
    rr = max(radius, 1e-4)
    if mode == 1:
        dens = np.exp(-d2 / (2.0 * rr * rr)).sum(1)
        d = -rr * np.log(np.maximum(dens, 1e-8))
    else:
        d = np.sqrt(d2[np.arange(len(p)), j]) - rr
    V = np.zeros_like(Q) if vel is None else np.asarray(vel, dtype=np.float64)
    return d, V[j]


def ref_bend_frame(a):
    np = _np()
    a = np.asarray(a, dtype=np.float64)
    a = a / np.linalg.norm(a)
    up = np.array([0.0, 1.0, 0.0])
    bd = up - a * (up @ a)
    if np.linalg.norm(bd) < 1e-3:
        bd = np.array([1.0, 0.0, 0.0]) - a * a[0]
    bd = bd / np.linalg.norm(bd)
    return a, bd, np.cross(a, bd)


def ref_bend(r, a, k):
    """twist mode bend (pxBend): the axis a curves toward bd with curvature k (rad per unit); arc length kept.
    s = r.a, y = r.bd, rho = 1/k - y: r' = r - a s - bd y + a rho sin(k s) + bd (1/k - rho cos(k s))."""
    np = _np()
    r = np.asarray(r, dtype=np.float64)
    a, bd, _n = ref_bend_frame(a)
    if abs(k) < 1e-6:
        return r.copy()
    s = r @ a
    y = r @ bd
    th = k * s
    rho = 1.0 / k - y
    base = r - a * s[..., None] - bd * y[..., None]
    return base + a * (rho * np.sin(th))[..., None] + bd * (1.0 / k - rho * np.cos(th))[..., None]


def ref_stretch_matrix(a, stretch, thin):
    """S3: M = (1 - 0.75 thin) (I - a a^T) + (1 + stretch) a a^T; the splat covariance becomes M Sigma M (applied in
    the reused shader as t0 -> M t0, t1 -> M t1)."""
    np = _np()
    a = np.asarray(a, dtype=np.float64)
    a = a / max(np.linalg.norm(a), 1e-12)
    th = 1.0 - 0.75 * min(max(thin, 0.0), 1.0)
    P = np.outer(a, a)
    return th * (np.eye(3) - P) + (1.0 + max(stretch, -0.95)) * P


def ref_splat_dof(cov2d, coc, minenergy=0.02):
    """S6: blur a 2D splat footprint by a gaussian of sigma coc/2 px: cov + s^2 I, alpha x sqrt(det0 / det1) (energy
    kept), clamped to [minenergy, 1]. -> (cov', alpha factor)."""
    np = _np()
    C = np.asarray(cov2d, dtype=np.float64)
    s2 = (0.5 * max(coc, 0.0)) ** 2
    C2 = C + np.eye(2) * s2
    d0 = max(float(np.linalg.det(C)), 1e-12)
    d1 = max(float(np.linalg.det(C2)), 1e-12)
    return C2, min(max(math.sqrt(d0 / d1), minenergy), 1.0)


def ref_splat_clamp(cov2d, maxpx):
    """Splat footprint cap (px_splat_adapter pxsClamp): if the larger 2D sigma exceeds maxpx, the covariance scales by
    k = maxpx^2 / l1 and alpha by k (energy kept, so a splat right at the camera fades instead of filling the frame).
    -> (a, b, c, alpha factor)."""
    a, b, c = [float(x) for x in cov2d]
    if maxpx <= 0.0:
        return a, b, c, 1.0
    mid = 0.5 * (a + c)
    l1 = mid + math.sqrt(max(mid * mid - (a * c - b * b), 0.0))
    m2 = maxpx * maxpx
    if l1 <= m2:
        return a, b, c, 1.0
    k = m2 / l1
    return a * k, b * k, c * k, k


def ref_slices(p0, c, ax, bandwidth, gap):
    """prox_stretch slices: band coordinate s = (p0 - c).ax / bandwidth; a point is in a gap when fract(s) > 1 - gap;
    snapped position (snap 1) = the band's centre plane."""
    np = _np()
    p0 = np.asarray(p0, dtype=np.float64)
    ax = np.asarray(ax, dtype=np.float64)
    ax = ax / np.linalg.norm(ax)
    bw = max(bandwidth, 1e-4)
    s = (p0 - np.asarray(c)) @ ax / bw
    f = s - np.floor(s)
    snapped = p0 + ax * ((np.floor(s) + 0.5 - s) * bw)[..., None]
    return f > 1.0 - gap, snapped


def ref_cone_dirs(ids, frame, ax, cone_deg):
    """pxCone: unit directions inside a cone of half angle cone_deg around ax (uniform in solid angle)."""
    np = _np()
    ax = np.asarray(ax, dtype=np.float64)
    ax = ax / np.linalg.norm(ax)
    u1 = np_rnd(ids, (int(frame) * 19 + 131) & 0xFFFFFFFF)
    u2 = np_rnd(ids, (int(frame) * 23 + 137) & 0xFFFFFFFF)
    cmin = math.cos(math.radians(min(max(cone_deg, 0.0), 180.0)))
    ct = 1.0 - u1 * (1.0 - cmin)
    st = np.sqrt(np.maximum(1.0 - ct * ct, 0.0))
    ph = 2.0 * math.pi * u2
    t = np.array([1.0, 0.0, 0.0]) if abs(ax[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(ax, t)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(ax, e1)
    return ax * ct[:, None] + e1 * (st * np.cos(ph))[:, None] + e2 * (st * np.sin(ph))[:, None]


def ref_rot(v, ax, a):
    np = _np()
    v = np.asarray(v, dtype=np.float64)
    ax = np.asarray(ax, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)[..., None]
    return v * np.cos(a) + np.cross(ax, v) * np.sin(a) + ax * (v @ ax)[..., None] * (1.0 - np.cos(a))


def ref_twist(home, c, ax, twist, wobble=0.0, ph=0.0, gain=1.0):
    np = _np()
    r = np.asarray(home, dtype=np.float64) - np.asarray(c)
    return np.asarray(c) + ref_rot(r, ax, (twist + wobble * math.sin(ph)) * (r @ np.asarray(ax)) * gain)


def ref_wave_sine(p0, dirv, freq, ph, amp, axis=(0.0, 1.0, 0.0), gain=1.0):
    np = _np()
    d = np.asarray(dirv, dtype=np.float64)
    d = d / max(np.linalg.norm(d), 1e-8)
    s = np.sin(np.asarray(p0) @ d * freq - ph)
    return np.asarray(p0) + np.asarray(axis) * (amp * s * gain)[..., None]


def ref_explode(home, c, idx, seed, progress, distance, power=1.0, random=0.5, gain=1.0):
    """explode mode radial, swirl 0."""
    np = _np()
    r = np.asarray(home, dtype=np.float64) - np.asarray(c)
    n = r / np.maximum(np.linalg.norm(r, axis=-1, keepdims=True), 1e-8)
    e = max(progress, 0.0) ** power * gain
    k = distance * e * (1.0 - random + random * 2.0 * np.asarray(seed))
    return np.asarray(c) + r + n * k[..., None]


def ref_dissolve_front(p0, c, campos, mode, rng, progress, soft, pitch=0.5):
    """dissolve_gradient fronts of wave 3 (warp 0): mode 'camera' (distance from the camera / range) or 'spiral'
    (helix about y through c). -> dissolve amount per point (G 1), mirrors px_modules."""
    np = _np()
    p0 = np.asarray(p0, dtype=np.float64)
    c = np.asarray(c, dtype=np.float64)
    if mode == 'camera':
        gr = np.linalg.norm(p0 - np.asarray(campos, dtype=np.float64), axis=1) / max(rng, 1e-5)
    else:
        ang = np.arctan2(p0[:, 2] - c[2], p0[:, 0] - c[0]) / (2.0 * math.pi) + 0.5
        pt = max(pitch, 1e-4)
        gr = (ang + (p0[:, 1] - c[1] + rng) / pt) / (2.0 * rng / pt + 1.0)
    s = max(soft, 1e-4)
    e = progress * (1.0 + s)
    x = np.clip((gr - (e - s)) / s, 0.0, 1.0)
    return 1.0 - x * x * (3.0 - 2.0 * x)


def ref_dissolve_noise(p0, progress, scale=2.0, octaves=3, soft=0.1, bias=(0.0, 0.0, 0.0), bbc=(0.0, 0.0, 0.0), gain=1.0):
    np = _np()
    p0 = np.asarray(p0, dtype=np.float64)
    n = np_fbm(p0 * scale, octaves, 13) + (p0 - np.asarray(bbc)) @ np.asarray(bias, dtype=np.float64)
    s = max(soft, 1e-4)
    e = progress * (1.0 + s)
    t = np.clip((n - (e - s)) / s, 0.0, 1.0)
    return (1.0 - t * t * (3.0 - 2.0 * t)) * gain


def ref_integrate(o, v, acc, dt, spring=4.0, damp=1.5, drag=0.2, maxspeed=0.0, dis=0.0):
    """The core semi-implicit step (px_update.glsl after the modules)."""
    np = _np()
    o = np.asarray(o, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    hold = 1.0 - np.clip(dis, 0.0, 1.0)
    a = np.asarray(acc, dtype=np.float64) - spring * hold * o - damp * v
    v = (v + a * dt) * math.exp(-drag * dt)
    if maxspeed > 0:
        sp = np.linalg.norm(v, axis=-1, keepdims=True)
        v = np.where(sp > maxspeed, v * maxspeed / np.maximum(sp, 1e-12), v)
    return o + v * dt, v


def ref_gen(kind, ids, n, p1=1.0, p2=0.3, p3=0.0, spin=0.0):
    """px_source.glsl pxGen for sphere / grid / torus / plane / cylinder (the deterministic ones)."""
    np = _np()
    i = np.asarray(ids, dtype=np.int64)
    fi = i.astype(np.float64)
    fn = float(max(n, 1))
    tau = 2.0 * math.pi
    if kind == 'grid':
        k = int(math.ceil(fn ** (1.0 / 3.0) - 1e-3))
        if k * k * k < n:
            k += 1
        k = max(k, 1)
        c = np.stack([i % k, (i // k) % k, i // (k * k)], -1).astype(np.float64)
        p = ((c + 0.5) / k * 2.0 - 1.0) * p1
    elif kind == 'torus':
        a = tau * np_weyl(i, 2654435769)
        b = tau * np_weyl(i, 3242174889)
        p = np.stack([(p1 + p2 * np.cos(b)) * np.cos(a), p2 * np.sin(b), (p1 + p2 * np.cos(b)) * np.sin(a)], -1)
    elif kind == 'plane':
        k = max(int(math.ceil(math.sqrt(fn) - 1e-3)), 1)
        if k * k < n:
            k += 1
        p = np.stack([((i % k) + 0.5) / k * 2.0 - 1.0, ((i // k) + 0.5) / k * 2.0 - 1.0, np.zeros(len(i))], -1) * p1
    elif kind == 'cylinder':
        a = tau * np_weyl(i, 2654435769)
        p = np.stack([0.5 * p1 * np.cos(a), ((fi + 0.5) / fn * 2.0 - 1.0) * p1, 0.5 * p1 * np.sin(a)], -1)
    elif kind == 'sphere':
        y = 1.0 - 2.0 * (fi + 0.5) / fn
        r = np.sqrt(np.maximum(0.0, 1.0 - y * y))
        a = tau * np_weyl(i, 2654435769)
        p = np.stack([r * np.cos(a), y, r * np.sin(a)], -1) * p1
    else:
        raise ValueError('ref_gen: %s not mirrored' % kind)
    ca, sa = math.cos(spin), math.sin(spin)
    return np.stack([ca * p[:, 0] + sa * p[:, 2], p[:, 1], -sa * p[:, 0] + ca * p[:, 2]], -1)


def ref_unproject(nearness, side, fov=60.0, near=1.0, far=4.0, aspect=1.0, scale=1.0, mirror=True, sample=None):
    """Depth side of px_source.glsl for a side x side grid; nearness(u, v) callable or (side, side) array [y, x]."""
    np = _np()
    ys, xs = np.mgrid[0:side, 0:side]
    u = (xs + 0.5) / side
    v = (ys + 0.5) / side
    nr = nearness(u, v) if callable(nearness) else np.asarray(nearness, dtype=np.float64)
    z = far + (near - far) * nr
    th = math.tan(math.radians(fov) * 0.5)
    x = (u * 2.0 - 1.0) * th * aspect * z
    y = (v * 2.0 - 1.0) * th * z
    if mirror:
        x = -x
    return np.stack([x, y, -z + 0.5 * (near + far)], -1).reshape(-1, 3) * scale


def ref_ease(u, k):
    u = max(0.0, min(1.0, u))
    if k == 1:
        return u * u * (3.0 - 2.0 * u)
    if k == 2:
        return 0.5 - 0.5 * math.cos(math.pi * u)
    if k == 3:
        return 4.0 * u ** 3 if u < 0.5 else 1.0 - (-2.0 * u + 2.0) ** 3 * 0.5
    return u


def ref_sprite_radius(size, z, fy, att=1.0, minpx=0.7, maxpx=64.0, aperture=0.0, focus=5.0, maxcoc=48.0, minenergy=0.02):
    """-> (radius px, alpha factor) of px_vert.glsl."""
    rpx = min(max(size * fy / (z ** max(0.0, min(1.0, att))), minpx), max(maxpx, minpx))
    coc = min(aperture * abs(z - focus) / z, maxcoc)
    r = max(rpx, coc)
    return r, min(max((rpx * rpx) / max(r * r, 1e-6), minenergy), 1.0)


# ---- rest texture packing (runtime upload; numpy)

def pack_rest(P, C=None, S=None, Q=None, side=None, count=None):
    """(n,3) positions (+ (n,4) colour, (n,3) scale, (n,4) quat wxyz) -> (side, 4*side, 4) float32 rest image,
    point id = y*side + x at [y, 4x + k] (k = texel). Rows past count stay zero (valid = 0). No scale (plain point
    clouds) = 0: 'no splat scale' (the splat render then uses Look Size, the sprite Splatscale ignores it)."""
    np = _np()
    P = np.asarray(P, dtype=np.float32)
    n = P.shape[0] if count is None else min(int(count), P.shape[0])
    side = side or side_for(max(n, 1))
    img = np.zeros((side * side, REST_TEXELS, 4), np.float32)
    img[:n, 0, :3] = P[:n]
    img[:n, 0, 3] = 1.0
    img[:n, 1] = np.asarray(C, dtype=np.float32)[:n] if C is not None else 1.0
    img[:n, 2, :3] = np.asarray(S, dtype=np.float32)[:n] if S is not None else 0.0
    if Q is not None:
        img[:n, 3] = np.asarray(Q, dtype=np.float32)[:n]
    else:
        img[:n, 3, 0] = 1.0
    return img.reshape(side, side * REST_TEXELS, 4)


def stack_files(img_a, img_b, side):
    """rest_files image: A rows 0..side-1, B rows side..2 side-1 (an empty side is zeros = invalid points), so ONE
    Script TOP feeds both file sides (the source pass keeps input 1 for the actor, 3 inputs max: T-84)."""
    np = _np()
    z = np.zeros((side, side * REST_TEXELS, 4), np.float32)
    a = z if img_a is None else np.asarray(img_a, np.float32)
    if img_b is None:
        return np.ascontiguousarray(a)
    return np.ascontiguousarray(np.concatenate([a, np.asarray(img_b, np.float32)], 0))


def actor_frame(t, fps, nframes, loop=True):
    """Index of the actor sequence frame at time t (seconds)."""
    if nframes <= 0:
        return -1
    k = int(math.floor(max(t, 0.0) * max(float(fps), 1e-3) + 1e-9))
    return k % nframes if loop else min(k, nframes - 1)


def load_keep(P, C=None, clip=0.0, amin=0.0):
    """Indices kept at load (before resampling to Count): within `clip` of the median point (0 = all; scans carry
    sky shells / floaters far away) and colour alpha >= amin (splat opacity; 0 = all). Never empty (falls back to all)."""
    np = _np()
    P = np.asarray(P, dtype=np.float64)
    keep = np.ones(len(P), bool)
    if clip and clip > 0 and len(P):
        keep &= np.linalg.norm(P - np.median(P, 0), axis=1) <= float(clip)
    if amin and amin > 0 and C is not None and np.shape(C)[-1] >= 4:
        keep &= np.asarray(C)[:, 3] >= float(amin)
    idx = np.nonzero(keep)[0]
    return idx if len(idx) else np.arange(len(P))


def resample_to(P, n, seed=0):
    """Index list of length n drawn from len(P) points (repeat when fewer, even subsample when more)."""
    np = _np()
    m = len(P)
    if m == 0:
        return np.zeros(0, np.int64)
    if m >= n:
        return np.round(np.linspace(0, m - 1, n)).astype(np.int64)
    rng = np.random.default_rng(seed)
    extra = rng.integers(0, m, n - m)
    return np.concatenate([np.arange(m), extra])


def up_fix(P, up):
    np = _np()
    P = np.asarray(P, dtype=np.float32)
    if up == 'z':
        return np.stack([P[:, 0], P[:, 2], -P[:, 1]], 1)
    if up == '-y':
        return np.stack([P[:, 0], -P[:, 1], -P[:, 2]], 1)
    if up == '-z':
        return np.stack([P[:, 0], -P[:, 2], P[:, 1]], 1)
    return P


def bounds(P):
    np = _np()
    P = np.asarray(P, dtype=np.float64)
    if len(P) == 0:
        return (0.0, 0.0, 0.0), 1.0
    c = np.median(P, 0)
    r = float(np.percentile(np.linalg.norm(P - c, axis=1), 98)) or 1.0
    return tuple(float(x) for x in c), r


def morton_order(P, bits=10):
    np = _np()
    P = np.asarray(P, dtype=np.float64)
    lo, hi = P.min(0), P.max(0)
    q = ((P - lo) / np.maximum(hi - lo, 1e-12) * (2 ** bits - 1)).astype(np.uint64)
    code = np.zeros(len(P), np.uint64)
    for b in range(bits):
        for k in range(3):
            code |= ((q[:, k] >> np.uint64(b)) & np.uint64(1)) << np.uint64(3 * b + k)
    return np.argsort(code, kind='stable')
