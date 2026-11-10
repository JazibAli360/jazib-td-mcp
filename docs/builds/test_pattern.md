# test_pattern: TP_test_pattern test patterns + sync checks (26 Oct 2026, TD 2025.31550)

`/project1/lab/TP_test_pattern`. A self-contained generator: no input, `out1` TOP only. Spec/recipe:
`docs/research/BB_test_patterns_sync.md` section 5 (our own clean-room design; ideas from Mallin's Wallin Pattern
Generator and Video sync test wheel, whose files were never obtained, licence unstated). Pattern names follow
`stagelab/guides/JZB_Slice_Test.md`, so the TD pattern and the Arena FFGL one use the same words.

Exact: a lit pixel is exactly the **Level** code on the **Channel** components (8-bit RGBA; Gradient 16-bit float),
whole-pixel lines, deterministic (no seed). Only the cabinet numbers, slice labels and counter text are anti-aliased.

## Build
```python
ns = dict(globals()); exec(open('<repo>/builders/test_pattern.py').read(), ns); ns['build']('/project1/lab')
```
Idempotent, T-70 safe (closes its own controls_window, zkit rebuilds the panel in place, `_sd` = safe_destroy, never
moves the pane). Files: `builders/test_pattern.py` (builder), `builders/test_pattern_logic.py` (pure logic, copied into
`tp_logic`), `builders/test_pattern_shader.glsl` (the one pixel shader, copied into `pattern_pixel`). 39 offline tests:
`python3 -I -m unittest discover -s test -p 'test_test_pattern.py'`.

## Face table
`faces` Table DAT, one row per face: `name, x, y, w, h` in LED px, top-left origin, max 16. Default: one face
`Wall 0 0 1920 1080`. Or point `Facestable` (Layout page) at any Table DAT with those columns.
Composition px = LED px x `Resx` / `Nativewidth` (`Nativewidth` 0 = 1:1, the default). Example R02 (native 9984 at
7488x2880): `L1 0 0 1536 3840`, `L2 1536 0 768 3840`, `C 2304 0 2304 3840`, ...

## Parameters (zkit panel shows Pattern, Cabinet, Sync; pulse `Opencontrols`)
| Page | Pars |
|---|---|
| Pattern | Pattern (Cabinets, Slices, Solid, Bars, Ramp, Checker, Crosshatch, Walk, Circles, Gradient, Pixel check), Channel (White, Red, Green, Blue, Cyan, Magenta, Yellow, Black), Level 0-255, Area (Slices = per face from its own corner, Canvas = whole frame), Walk (Line Across, Line Down, Diagonal, Dot, Cabinet), Speed (steps/s; = fps -> one step per frame; 0 parks), Reset walk, Line width px, Cell (LED px, 0 = one cabinet), Ramp steps 2-256, Show face outlines (XOR over the pattern) |
| Cabinet | Resolution preset (custom, 1920x1080, 1080x1920, 3840x2160, 7488x2880, 9984x3840 -> sets Width/Height), Width px, Height px, Native LED width, Cabinet width / height LED px (128) |
| Sync | Frame counter (text `F 0001234  HH:MM:SS:FF  60 fps` + strip: start cell, 24 frame bits MSB first, end cell), Counter x/y/size px, Sync wheel (rings 24, 30, 48, 60, 120 Hz on project seconds, inner -> outer, outermost = project frame mod fps; one lit segment per ring, one turn per second), Wheel x/y (0..1), Wheel size px, Flash frame (cabinet-wide white column at the right edge on frames where frame % N == 0), Flash every N frames, Audio blip (sine on the flash frame for Blip frames, Mac built-in speakers), Blip Hz, Blip frames, Blip volume, Counter fps (expression `project.cookRate`) |
| Layout | Facestable |
Pattern geometry as in JZB_Slice_Test: Cabinets = ring inside every cabinet + `column-row`; Slices = outline, both
diagonals, name / `WxH` LED / `NxM cab`; Bars = white yellow cyan green magenta red blue black at Level; Ramp exact
8-bit steps along the longer side; Crosshatch from the area centre + edge; Checker on cells. Extras: Circles (edge,
inscribed circle, concentric rings every cell from the centre), Gradient (continuous, 16F, for banding), Pixel check
(top half 1-px checker; bottom-left vertical / bottom-right horizontal 1-px lines every Line width px).

## Network (stages)
Controls (zkit `controls` + `controls_window`, `tp_parexec`) | 1 Faces (`faces`, `faces_chop` Script CHOP -> 16 rects
for the GLSL uniform array `uFaces`, `tp_logic`) | 2 Clock + uniforms (`walk_rate` -> `walk_speed` Speed CHOP, `uni`
Script CHOP = every uniform from `tp_logic.uniforms` + blip gate; its `Clock` par reads absTime.frame only while a
clock feature is on, so static patterns cook once) | 3 Labels (`cab_spec` / `slice_spec` Script DATs -> `cab_text` /
`slice_text` Text TOPs -> `labels`; `cab_measure` / `slice_measure` measure text widths; `counter_text`) | 4 Pattern
(`pattern` GLSL TOP, ONE pixel pass for pattern + outlines + labels + wheel + counter + flash, -> `out1`) | 5 Audio
blip (`blip_osc` -> `blip_out` Audio Device Out, `BuiltInSpeakerDevice`, active only while Blip is on).

## Verified live (26 Oct, 31550)
- **GLSL = reference:** the output read back (numpyArray) against `tp_logic.pixel()` on sample grids, text pixels
  skipped: 0 mismatches in every case: all 10 static patterns at 1920x1080 (~59k px each); 4 faces at a fractional
  scale (2269x1891, Native 4608: 58.17-ish px cabinets) for Cabinets slices/canvas, Slices, Checker canvas + face
  outlines, Crosshatch Cell 200, Ramp 256, Circles lw 5 (~477k px each), Red at Level 191; all 5 walks x slices/canvas
  (lw 3); 7488x2880 Native 9984 (96 px cabinets) Cabinets, Ramp, Crosshatch (~270k px each).
- Walk Speed 60 at 60 fps: step advanced exactly with the frame count over 240 frames (236 x +1, dropped frames
  +4/+12 matched by the step: time-based, no skipped cell beyond the dropped frames themselves).
- Frame counter strip decoded from the output pixels = the frame (200937, 3 reads); start/end cells lit.
- Sync wheel: lit segment found on each ring by sampling = expected (24: 14, 30: 18, 48: 29, 60: 37, 120: 74,
  frame ring 37 at 60 fps).
- Flash on frames % 60 == 0 (4 in 240); Blip (Bliplen 2) gate on frames % 60 in {0, 1}, osc amp = Blipvol; Audio
  Device Out active on BuiltInSpeakerDevice; blip_out does not cook while Blip is off.
- Labels: Text TOP spec rows are placed from x / baseline whatever alignx/aligny say (probe: identical ink box for
  left/bottom and center/center, also with extra alignx/aligny columns), so the scripts centre rows themselves with
  `evalTextSize` on the measure TOPs (`tp_logic.centre_rows`).
- td_errors clean, td_layout check ok (no intruders / unboxed / box overlaps), /project1/lab check ok.
- **Perf** (1920x1080, counter + wheel + flash on, out1 pulled each frame, median of 239 frames, one other lane live):
  uni 0.33 ms CPU, pattern 0.17 CPU + 0.24 GPU, counter_text 0.15 CPU + 0.03 GPU, walk/osc/out < 0.03: **~0.95 ms per
  frame**; static patterns with no clock feature cook only on change. 7488x2880: pattern 1.23 ms GPU; a label rebuild
  of 2340 cabinet numbers ~55 ms once (on a par/table change only). Project ~59.6 fps wall-clock, cookRate 60 untouched.
- Captures (session scratchpad): `tp_cabinets.png`, `tp_slices.png` (output), `tp_controls.png` (zkit panel),
  `tp_network_final.png` (network).

## Not done / open
- Latency TD -> Arena (Syphon/NDI with the counter in the picture) not run: needs the user's go-ahead for the senders
  and a camera; no latency numbers claimed.
- The blip was gated and routed to the speakers but not recorded with the flash (no audio/video capture made).
- Network stages stack in one column (the stages link by expressions, not wires); readable, but `mixed` did not put
  them side by side.
- Wheel ring labels (rates) are not drawn; inner -> outer order is in this doc and the COMP comment.
- Frame value passes as a float uniform: exact up to 2^24 frames (~77 h at 60 fps).
