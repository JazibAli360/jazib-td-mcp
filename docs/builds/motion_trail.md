# motion_trail - `/project1/lab/FX_motion_trail` (TD 2025.31550, 26 Oct 2026)

Moving things leave a fading trail, coloured by age. Our own clean-room build of the recipe in
`docs/research/BA_motion_tracer.md` section 5 (dcheesman's Patreon .tox was never downloaded or loaded).

## Files
- `builders/motion_trail.py` - builder, `build(parent_path='/project1/lab', name='FX_motion_trail', controls=True)`, idempotent, T-70 safe:
  `g = dict(globals()); exec(open('<repo>/builders/motion_trail.py').read(), g); g['build']('/project1/lab')`
- `builders/motion_trail_logic.py` - pure logic (length/beats -> step, Decay -> gamma, Quality -> size, reset, audio mix,
  palette position / colour, hue, Cycle phase) + a Python reference model of both shaders; copied into the COMP as
  `motion_trail_logic` (par expressions call it).
- `builders/palette_map_logic.py` (FX_palette_map's) - copied in as `palette_map_logic`: the same Lospec presets,
  hex parsing and palette files (.txt .hex .json .gpl .pal .ase) for the Palette age colour.
- `test/test_motion_trail.py` - 25 offline tests: `python3 -I -m unittest discover -s test -p 'test_motion_trail.py'`.

## How it works
`clip` (stored webcam clip) or `in1` -> `src` -> `work` (Quality: full/half/quarter) -> `prev` (Cache TOP, size 2,
index -1 = previous frame) -> **`trail`** (one compute GLSL pass, rgba16float): motion = smoothstep(Threshold,
Threshold+Softness, max |cur - prev| over RGB); age = max(motion, last age - 1/Length) (Hold = no fade); rgb = the
colour the pixel moved with; input 2 = `trail_fb` (Feedback TOP of `trail`, reset source `blank` alpha 0) ->
**`look`** (one compute pass at source size, bilinear upscale of the trail): opacity = age ^ gamma(Decay) * Mix;
colour = Ramp new -> mid -> old (neutral greys by default), White only, Source (captured colour), **Palette by age**
or **Rainbow cycle**; Blend over / add / screen / trail only (premultiplied alpha) -> `out1` (output only). Compute
mode only (T-46/T-47).
**Palette:** `pal_custom` (table, one hex per row, newest -> oldest; default a warm 5-colour ramp) / a preset / a file
-> `pal_active` (Script DAT, rows hex r g b, via `palette_map_logic.resolve`) -> `pal_chop` -> `pal_top` (N x 1 rgb
texture, look input 3). Position p = (1 - t) * Spread + phase, phase = Cycle (cycles/s) * seconds wrapped; with Spread
<= 1 and Cycle 0 p is clamped (first colour = newest, last = oldest), otherwise it wraps (a hard seam where the last
colour meets the first). Smooth pal blends neighbours, off = hard bands. **Rainbow:** hue = (1 - t) * Spread + phase
(full saturation and value; Spread = hue cycles over a trail's life, Cycle spins it with time).

## Pars
- **Trail** (knobs): Length (frames, min 1, no upper cap), Unit (frames / beats), Beats, BPM (beats mode: length =
  beats * 60 / BPM * cookRate), Decay (0 hangs on, 0.5 linear, 1 fades fast), Threshold, Softness, Mix, Source lvl,
  Audio mix (scales Mix by `in_level` channel 0, 0..1; nothing wired = Mix), Hold, Clear (pulse).
- **Colour** (knobs): Age colour (ramp / white / source / palette / rainbow), Blend, New, Mid, Old, Palette (Custom
  table, From file, 20 presets), Smooth pal, Spread (0..4, default 1), Cycle /s (-2..2, default 0).
- **Setup**: Source (clip / In TOP), Clipfile (default `media/webcam/webcam_ref_5s.mp4`), Quality (default half),
  Resetonloop (clears the trail at the clip's loop point: no ghost), Palettefile (Palette = From file).
- **Zkit**: Opencontrols opens the zkit panel (`controls` + `controls_window`).

## Verified live (26 Oct, 31550, M1 Max, webcam_ref_5s.mp4)
| Check | Result |
|---|---|
| (a) static scene (clip paused, 45 frames) | trail alpha max 0; out1 == src exactly (max diff 0) |
| (b) Length scales | trail coverage (alpha > 0.004, mean of 8 samples) L10 1.75 % -> L60 4.05 % |
| (c) Threshold | 0.0 -> 99.4 % (codec noise everywhere), 0.02 -> 5.65 %, 0.08 (default) ~2.9 %, 0.30 -> 0.26 % |
| Beats | 2 beats at 128 BPM, 60 fps -> step 0.017778 = 1/56.25 (expected) |
| Clear | coverage 0 for the 2 frames after the pulse, then regrows from new motion |
| Hold | nothing fades (alpha sum 0 -> 22223 over 60 frames while the clip played) |
| White only (trail-only blend) | 106001 px: r = g = b exactly, rgb = alpha exactly (premultiplied) |
| Ramp colour by age | unpremultiplied colour at alpha 0.9-1.0 = 0.988 (exp ~0.96-1.0), 0.45-0.55 = 0.618/0.637/0.676 (exp 0.62/0.64/0.68), 0.08-0.15 = 0.31/0.319/0.354 (exp 0.312/0.324/0.357) |
| (f) loop point | Resetonloop on: coverage 0-0.19 % at index < 4; off: 3.0-3.5 % (old trail + cut) |
| (e) tearing | compute-only chain; static/pass-through exact and ramp numbers match the model (no stale pixels seen); not a T-47 frame-counter probe |
| td_errors / layout check | clean / ok (no intruders, unboxed, box overlaps, back wires) |

**Perf** (half quality, 960x540 trail, 1920x1080 out): COMP total median CPU 1.07 ms (max 1.7), GPU 1.85 ms (sum of
op GPU times incl. clip decode ~0.4-0.5 ms) over 120 frames. Project fps: 60 with this COMP cooking in one 3 s
window, 43 with it parked in the window before: the other lane's load dominates, not this COMP. Full quality: trail
CPU 0.44 ms / look 0.24 ms (single sample). VRAM: 2 working frames + 2 rgba16f trail frames (no 60-frame cache).

Captures (session scratchpad): `mt_network.png`, `mt_controls.png`, `mt_out_ramp_over.png`, `mt_out_white_add.png`.

## Palette + rainbow modes, verified live (26 Oct, 31550, webcam_ref_5s.mp4, Blend trail only, Decay 0.5, Mix 1)
Method: read out1, unpremultiply every pixel with alpha > 0.15 (~190k px, 9.2 % cover), compare up to 4000 samples
with `motion_trail_logic.shade` at the pixel's alpha (palette from `pal_active`, phase from the `uC` uniform).
| Mode | Model error (max over rgb): mean / p95 / max | Mean rgb at alpha 0.9-1.0 / 0.6-0.7 / 0.3-0.4 |
|---|---|---|
| Palette, custom 5 (smooth) | 0.0026 / 0.0077 / 0.017 | 1, .943, .816 / 1, .555, .213 / .694, .088, .317 |
| Palette, Sweetie 16, bands | 0.0064 / 0.0068 / 0.50 (band edges: 8-bit alpha) | .218, .128, .258 / .659, .854, .435 / .277, .627, .925 |
| Palette, .gpl file (3 colours), Spread 2 | 0.0059 / 0.0089 / 0.024 | .177, .824, 1 / 1, .362, .638 / .608, .392, 1 |
| Palette, custom, Cycle 0.5 | 0.0025 / 0.007 / 0.89 (wrap seam) | phase 0.792 |
| Rainbow, Cycle 0 | 0.0037 / 0.0106 / 0.020 | 1, .363, 0 / .042, 1, .112 / .034, .131, 1 |
| Rainbow, Cycle 0.5 (2 reads 40 frames apart) | 0.0044 / 0.011 / 0.018; 0.0028 / 0.012 / 0.024 | fresh .163, .01, 1 (phase .65) -> .927, .959, 0 (phase .133) |
| White (regression) | 0 / 0 / 0 | 1, 1, 1 |
Palette / Palettefile changes re-read `pal_active` at once (par_exec + the Script DAT's own par dependency). td_errors
clean, layout check ok. **Perf** (palette mode, half quality, pulled every frame, 180 frames, other lanes running):
COMP median CPU 0.94 ms, GPU 3.94 ms of which the clip decode is 3.39 (look + trail + prev ~0.55 ms); project fps
59.7 pulling out1, 59.6 not pulled (T-102: the measuring sampler itself dropped it to 45.5). Capture:
`mt_palette_network.png` (session scratchpad).

## Notes / left
- The trail inherits the clip's 30 fps: every second 60 fps frame has no motion (head fades 1/Length, invisible).
- Resetonloop clears a real trail at the loop point too (2 frames); off = a 3 % cut ghost.
- Not done: Source = In TOP from another COMP (path exists, untested), real audio into `in_level`, the 1080x1920
  vertical look rule (the COMP follows its source size), a T-47-style tear probe.
- The docked `trail_pixel` / `look_pixel` DATs are TD's auto pixel shaders (unused in compute mode).
