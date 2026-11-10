# previz_stage (`/project1/lab/PV_previz_stage`)

Drop any TOP into a stage previz: LED wall in a hazy hall, a seeded instanced crowd, beams and wash light that take
the screen's colour, camera presets. Clean-room design from `docs/research/BI_rudiment_previz_stage.md`, with a
generic wall (no show-specific layout). TD 2025.31550.

## Build / rebuild
```python
# td_exec
p = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/previz_stage.py'
g = dict(globals()); exec(open(p).read(), g); C = g['build']('/project1/lab')   # also re-applies the stage layout
```
Idempotent and T-70 safe: the COMP (and wires into it) stays; custom parameters are updated in place (values kept,
no page destroyed); its own windows are closed first; every other inside op goes through `safe_destroy` and is re-made.
The `controls` panel and both Window COMPs are never destroyed: the panel is kept when the parameter set is unchanged
(signature in storage `pv_ui_sig`), otherwise a new one is built beside it, the window is pointed at it and the old one
is renamed and destroyed 5 frames later. Backup before the resume: `output/backups/PV_previz_stage_pre_resume.tox`.
Pure logic: `builders/previz_stage_logic.py` (copied into the Text DAT `previz_logic`); tests:
`python3 -I -m unittest discover -s test -p 'test_previz_stage.py'`.

## Use
- **in1** (input 0): the screen content. `Source` (Output page): Input / Test noise / Test ramp / Test colour
  (`Testcolor` on Colours). Input with nothing wired falls back to the noise.
- **out1**: the rendered hall (`Resx` x `Resy`, default 1920x1080 landscape since it is a hall camera, 16-bit float).
  `Quality` (Output page): High = full res + `Msaa`; Medium = 3/4 res, AA capped at 2x; Draft = 1/2 res, no AA. The
  render, haze and bloom run at the reduced size and `post` scales back up, so out1 stays `Resx` x `Resy`.
  `Bloomres` (Output page, perf wave 27 Oct): the bloom runs on a Quarter (default) / Half / Full size copy of the
  hazed image and `post` adds it back (Full = the old single-size bloom, bit-equal within 16F rounding); `Bloom` 0 skips
  the bloom chain. The test noise (`Source` noise, or Input with nothing wired) is drawn at 1/4 of the screen texture at
  the wall aspect and skips the `fit` pass (`screen_sel`). `Showscreenonly` shows the fitted
  screen texture instead. **out_react** (CHOP): `r g b lum`, dominant `dr dg db`, left `lr lg lb`, right `rr rg rb`,
  per face `f1r f1g f1b ...` (lagged by `Reactlag`).
- **in_audio** (optional CHOP input): RMS of it x `Audiogain` x `Audioreact` pumps the beams. No audio device inside.
- **Wall** (Stage page): `Layout` Flat 16:9 (`Wallw` x `Wallh`, `Curve`) / Main + side screens (`Sidew`, `Sideh`,
  `Sidefold`, `Gap`) / Custom = rows of `face_table` (name, width, height, fold, curve, lift; metres and degrees, left
  to right; the widest face is centred, folds turn toward the audience). `Contentmap` Span (one canvas across all
  faces) or Repeat (full picture per face). The table `faces` shows the computed UV windows and positions.
- **Crowd**: `Count`, `Rows`, `Spacing`, `Seed` (same seed = same crowd), `Sway`, `Hands` (fraction with a raised arm),
  `Crowdlit` (screen spill on them).
- **Haze**: depth fog in one GLSL pass (`Density`, `Falloff`, `Drift`), `Scatter` = beam visibility, `Hazeglow` =
  screen colour in the air, `Hazecolor` on Colours.
- **Lights**: `Beams` cones on the truss, `Fan`, `Beamtilt`, `Spread`, `Beamlen`, `Beamsweep(speed)`, `Intensity`,
  `Follow` (0 = `Basecolor`, 1 = screen colour), `Reactmode` (average / left-right / per face / dominant), `Wash`
  (cone light onto the crowd), `Strobe` + `Strobehz`.
- **Camera**: `Preset` FOH / Stage left / Stage right / Drone / Crowd POV / Orbit, `Orbitx`/`Orbity`/`Orbitdist`
  around the preset target, `Autoorbit` + `Orbitspeed`, `Fov`. Presets scale with the wall size.
- **Window** page: `Opencontrols` (the `controls` panel: autoUI sections in three columns), `Openview` (a window on
  out1), `Reset` (all parameters to defaults).

## Network
Stages (stored plan, `layout_stages`): Controls, 1 Screen input, 2 Wall layout, 3 Screen analysis, 4 Stage + wall,
5 Crowd, 6 Lights, 7 Camera, 8 Render, haze, output. Per-frame Python is small: `react` (64 px), `beams` (<= 24
rows), `campose` (1 row); the crowd grid (`crowd_base`) only cooks on a parameter change; its sway runs on the GPU in `crowd_xf` (perf wave 3, 27 Oct: below).

## Verified live (TD 2025.31550, 26 Oct 2026, resumed after the crash)
- td_errors clean; layout check ok (no intruders / unboxed / box_overlaps); second rebuild with the controls window
  open: window closed first, panel kept (same op id), values kept, no errors.
- Test colour red -> green with `Reactlag` 0.2: out_react r 0.92 -> 0.40 in ~0.17 s -> 0.04 at 0.65 s (time constant
  ~0.2 s); beam cg 0.011 -> 0.130 and spill green follow. `Follow` 0: beams = base white (0.135 x3).
- `Crowdon` 0: crowd render off; `Density` 0 vs 1: out1 mean 0.186 vs 0.259; `Lightson` 0: mean 0.242 -> 0.223,
  beam colour 0. No NaN in out1.
- Perf (noise source, every op cooking, CPU cook ms medians): render 1.6 (High) / 1.4 (Medium) / 0.9 (Draft),
  an_chop 0.5-1.2 (download nextframe), react 0.3, beams 0.3, haze 0.1, bloom 0.15, grade 0.03. TD frame interval
  ~18-19 ms (~54 fps, another agent building in the same TD), not changed measurably by Quality: GPU time is not
  reported on this build (gpuCookTime 0), so GPU cost is unmeasured.
- Captures: output/captures/previz_stage_out1.png, previz_stage_controls.png, previz_stage_network.png.

## Perf wave 3 (27 Oct 2026, b2 -> main, 31550)
- Crowd sway on the GPU: `crowd_base` -> `crowd_tex` (CHOP to TOP, 32F, one row per channel) -> `crowd_xf` (compute,
  2 buffers: tx bob tz s / ry rz hs s; buffer 1 via `crowd_rot` Render Select, `bufferindex` 1) -> TOP instancing of
  `crowd` + `hands`. Replaced `crowd_swz` / `crowd_bob` Noise CHOPs + `crowd_inst` Merge (~0.55 ms CPU at 800 people).
  The sway is a per-person cubic B-spline of hashed values with the CHOPs' statistics (std 0.27 x amp; time
  correlation 0.84 / 0.53 / 0.27 / 0.10 at 0.5-2 s at Swayspeed 0.5; twin `previz_stage_logic.crowd_sway`, tests);
  live std rz 0.47 deg (expected 0.49), ty 0.0047 m (0.0049). Not the same random draw as the CHOPs (no seed-exact
  match exists), same motion character. Uniforms are simple expressions (time fraction + whole cells split with one
  `%`, double precision on the CPU).
- Static parity (Sway 0, Drift 0, Beamsweep 0, Source colour, Count 800) vs the old build: mean 2.6e-4, p99 0.0024,
  max 0.0195 (4 px > 0.01): TOP-instanced transforms round differently from CHOP-instanced ones.
- `react` / `beams` Script CHOPs keep their channels between cooks (`out_chans`), react reads the TOP to CHOP with one
  numpyArray, beams read react from the module (`REACT`).
- b2 (load ~35) 5.5 ms at the defaults, 58.9 fps (wave 2: 6.7-7.4). Left: render 1.6 (T-198 floor), an_chop 0.87
  (TOP to CHOP floor), bloom 0.45, src_noise 0.37 (test source), react 0.35. Beam colours from a TOP were not done:
  the spill / wash lights, the haze uniform and `out_react` need the colours on the CPU anyway, so the download stays.
