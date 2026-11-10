# palette_convention - ONE shared palette for points, lines, haze, glow, embers, lights (lane W1-B, 27 Oct 2026)

User (27 Oct): "ability to change colors" for lines, haze, glow, embers, effector glow and splat / point recolour, with
palettes and BPM / audio colour changes. RUBENFRO_COVERAGE rows CO2-CO5. This is the convention every coloured element
uses: one palette per COMP, one GLSL include, one Python spec. **Offline only so far** (logic + reference + tests + glslc);
there is no live phase in this lane: each consumer (W1-A, W1-C, W1-D, PX wave 2) wires it in and runs the live checks
below. TD target 2025.31550.

## Files
- `builders/glsl/px_palette.glsl` - the include (prepend its text to any compute / pixel / vertex stage; guarded,
  pure ASCII). `pxPal(t)`, `pxPalStep(i)`, `pxColSrc(cs, solid, src, attrT)`; `palette(t)` / `palette_step(i)` only
  when the shader defines `PX_PAL_SHORT_NAMES` first (ph_look / rd_look already have their own `palette()`).
- `builders/palette_map_logic.py`, section "Shared palette convention" (appended; FX_palette_map's functions are
  unchanged): spec -> stops, uniform rows, drives, TD binding, and a float64 reference of the shader.
- `test/test_palette_conv.py` - 26 offline tests:
  `python3 -I -m unittest discover -s test -p 'test_palette_conv.py'` (FX_palette_map's 20 still pass).

## The uniforms (no TOP input: PX's GLSL TOPs already use all 3, T-84 / T-88)
| Uniform | Page | Size | Content |
|---|---|---|---|
| `uPal[16]` (`PX_PAL_MAX` = `PAL_MAX` = 16) | Arrays, type `vec4`, `uniformarray`, from a CHOP | 16 x vec4 | stop i = (r, g, b, pos). CHOP = 16 samples, channels **r g b pos in that order** (= x y z w). rgb as in a TD RGB par (display values, > 1 allowed for HDR); pos 0..1 ascending. Rows past `count` repeat the last stop and are never read. |
| `uPalCtl` | Vectors | vec4 | x **count** 0..16 (0 = black), y **shift** (palette-t offset, wraps; drives write this), z **mode** 0 gradient / 1 steps / 2 cycle, w **interp** 0 rgb / 1 oklab |
| one `vec4` per coloured element, e.g. `uLineCs`, `uHazeCs`, `uGlowCs` | Vectors | vec4 | **colour source** cs = (mode, pos, spread, keep), see below |

Python: `stops = palette_stops(spec, custom_rows, file_hex, pixels)`; `rows = pal_rows(stops)` (always 16 x 4);
`ctl = pal_ctl(stops, mode, interp, shift)`; `cook_chop(scriptOp, rows)` (Script CHOP onCook);
`bind_glsl(glslOp, chop, ctl, parmode=ParMode)` sets the Arrays block `uPal` + the Vectors block `uPalCtl` (reuses
blocks already named so, idempotent; strings in `ctl` become expressions, e.g. a drive).

## Modes (the same maths in GLSL and `pal_eval`)
- **gradient** (0): t clamped 0..1, blend between positioned stops, ends hold. Two stops at one position = a hard edge.
- **steps** (1): n equal bands, positions ignored; stop i owns [i/n, (i+1)/n) (same as FX_motion_trail's smooth off).
- **cycle** (2): t wraps; the last stop blends back into the first over [p_last, 1 + p_first] (seamless loops, rings,
  time cycles).
- A non-zero **shift** rotates (wraps) in every mode; shift k/n = exactly k stops on (`pxPalStep(i)` with shift 1/n ==
  `pxPalStep(i + 1)`).
- **interp oklab** blends in OKLab (perceptual; no muddy midpoints between neon colours), rgb = plain mix. HDR stops are
  kept (no upper clamp).
- Default positions when none are given: gradient i/(n-1), cycle i/n (so the wrap segment is as wide as the others).

## Sources (spec key `source`; menu `PAL_SOURCES`)
| Source | What |
|---|---|
| `custom` | a Table DAT, one stop per row: `hex [pos]` (`#` optional, `#RGB` ok; empty pos = filled in between neighbours, a missing first / last = 0 / 1), or inline `spec['stops']` (`'#hex'`, `['#hex', pos]`, or `[r, g, b, pos]` for HDR) |
| `file` | any file FX_palette_map reads (.txt .hex .json .gpl .pal .ase) via `parse_file`, even positions |
| `image` | sampled from a TOP: `stops_from_pixels(TOP.numpyArray(), n)` = deterministic k-means in OKLab (<= 4096 samples, alpha < 0.5 skipped), sorted dark -> light |
| stop presets | `neon_green`, `cyan_magenta`, `neon_trio` (green / cyan / magenta), `acid`, `magenta_inv`, `fire`, `px_ramp` (= PX `colour_ramp` col0..col3 defaults, so palette mode can reproduce the old look), `rainbow`. Our own picks by eye from the Ruben Fro looks in `docs/research/BR_rubenfro_pointcloud_fx.md` (his values are not published) |
| Lospec / hardware | FX_palette_map's 20 presets (PICO-8, Endesga 32, Resurrect 64, Game Boy, CGA, Solarized ...), even positions |
More than 16 colours: 16 picked evenly, first and last kept (FX_palette_map stays the tool for 64-colour quantise).
`reverse: True` flips any palette. A stop preset in cycle mode keeps its spacing scaled to (n-1)/n.

## Drives (what moves `uPalCtl.y`)
`pal_shift(drive, count, base, beats, level, onsets)` -> shift wrapped 0..1; `base` = the consumer's `Palshift` par.
| kind | shift |
|---|---|
| `manual` | base |
| `bpm_step` | floor(beats / every) x step / count + base: one stop on every `every` beats (the beat jump) |
| `bpm_cycle` | beats / every + base: a full turn every `every` beats (smooth) |
| `audio` | gain x level + base (continuous) |
| `onset_step` | floor(onsets) x step / count + base (one stop per detected hit) |
`beats` = a continuous beat count: `au_features` `beat_count`, or `beats_from(seconds, bpm)` with the consumer's tempo
(PX Drive: project tempo or Bpm). PX's own drive grammar (`Palshift:bar*1`, `Palshift:beat*0.25`) also works once PX
has a `Palshift` par: `apply_drives` adds to it like any float par. Any CHOP (OSC / MIDI) = an expression on
`uPalCtl.y`. Only the shift moves per frame; the CHOP recooks only when the palette changes (a Script CHOP reading the
palette pars recooks on change, T-115; it needs no Frame par because nothing in it is per-frame, T-113).

## Colour source: how each element picks its colour
`pxColSrc(cs, solid, src, attrT)`, cs = `colsrc_vec(mode, pos, spread, keep)` = (mode index, pos, spread, keep):
| mode | colour |
|---|---|
| 0 `solid` | the element's own RGB par (today's behaviour: the default) |
| 1 `palette` | `pxPal(pos)` |
| 2 `attr` | `pxPal(pos + spread x attrT)`: attrT = the consumer's attribute (depth, height, age, along-line, time, light distance) |
| 3 `source` | src (keep what it had: scan colour, light colour) |
| 4 `index` | `pxPalStep(round(pos + spread x attrT))`: ring k / line k / light k gets stop k |
`keep` 0..1 mixes back toward src. Standard pars per element: `colsrc_pars('line')` -> `Linecol` (RGB), `Linecolsrc`
(menu), `Linepalpos`, `Linepalspread`, `Linekeep`; the vec4 = (menu index, palpos, palspread, keep). The consumer
multiplies by its own gain / emission (HDR) afterwards.

## How each consumer uses it
- **TD wiring, any COMP**: a Script CHOP `pal_chop` (onCook: `palette_stops` from the COMP's Palette pars ->
  `cook_chop(scriptOp, pal_rows(stops))`), then `bind_glsl(glsl, 'pal_chop', [count, shift_expr, mode, interp])` on
  every GLSL TOP / MAT that colours something; prepend `px_palette.glsl` to that shader's text. One palette per COMP:
  every element of the COMP shares it and differs only by its cs vec4.
- **W1-C lines** (rings / contour / trails / connect / polyline / edges): one cs per lines pass (`uLineCs`); attrT =
  along-line 0..1 (gradient lines), ring / line index with mode `index` (one colour per ring), depth or age. Lines are
  HDR: emission x `pxColSrc(...)` so bloom catches them.
- **W1-D haze + glow**: haze colour = `pxColSrc(uHazeCs, Hazecol, lightCol, attrT)` with src = the light's colour
  (mode `source` = haze takes each light's colour) and attrT = height or depth; bloom `Bloomtint` = `pxColSrc(uGlowCs,
  Bloomtint, vec3(1), t)` (mode solid white = today's glow, diff 0).
- **W1-A lights**: a light's colour stays its Light COMP colour (TD lights it natively for MX); the palette applies
  when the light row is packed: Python `colsrc_eval(cs, light_rgb, light_rgb, k, rows, ctl)` with k = light index
  (mode `index`: light k = stop k, the beat step moves all lights one colour on) or in the shader via `pxColSrc` if
  the consumer recolours per pixel.
- **PX recolour (wave 2, PX owner)**: Palette page on PX = source / mode / interp / Palshift / drive; `colour_ramp`
  gains blend mode `palette` (attrT = its attribute between lo and hi, incl. new attribute `luma` for CO3 remaps);
  `prox_colour` ramp / colour, `prox_burn` fire ramp (`fire` preset), effector `Glowcolour`, `Edgecol`, `Hazecol`,
  `Flaretint`: each one cs. Splats recolour SH0 the same way (v2 S2).
- **Embers / pool sprites**: `pxColSrc(uEmberCs, solid, fireCol, lifefrac)`.

## Verified offline (27 Oct 2026, this Mac, glslc from Homebrew)
| Check | Result |
|---|---|
| `pal_eval` (scalar mirror of the GLSL) vs an independent numpy reference (searchsorted, vectorised) | 2000 t in -2..3, 8 palettes (presets, Lospec, hard edge, HDR inset) x 3 modes x 2 interps x 3 shifts: max diff < 1e-6 |
| steps / shift / cycle | CGA bands exact; shift 1/3 on a 3-stop palette == step + 1 for i in -4..6; cycle seam continuous (< 1e-4 at t = 1 - 1e-7 vs 1e-7) for rainbow / neon_green / fire |
| OKLab | mid of black -> white L = 0.5 (1e-7); HDR round trip (3.0, 0.5, 0.1), (0, 0, 6) within 1e-5 (published inverse constants) |
| sources | all 8 stop presets x 3 modes ascending in 0..1; Resurrect 64 -> 16 (ends kept); .gpl file; custom rows with gaps; reverse; empty -> count 0, black |
| image | two-colour pixel list -> those two colours (1e-4), transparent pixels skipped, deterministic; numpy RGBA TOP-like array -> 2 stops |
| drives | bpm_step every 2 beats on 4 stops: 0, 0, 0.25, ..., wraps after 4 steps; bpm_cycle / audio / onset / base |
| TD binding (fake op) | `bind_glsl` adds Arrays block 1 `uPal` (vec4, uniformarray) next to an existing `uPts`, Vectors `uPalCtl`, expressions kept, second call reuses the blocks; `cook_chop` 16 samples r g b pos |
| glslc (OpenGL) | compute kernel calling pxPal / pxPalStep / pxColSrc compiles (include twice: guard ok); fragment with `PX_PAL_SHORT_NAMES` compiles; without it `palette()` is undefined (no clash with ph_look / rd_look) |

## LIVE CHECKS for the first consumer (not run: no live phase in this lane)
1. Arrays page `uniformarray` vec4 from a 16-sample, 4-channel CHOP fills `uPal[i]` = sample i, channel order r g b
   pos -> x y z w (T-113's PX arrays are the precedent; confirm on the consumer's op).
2. GPU `pxPal` vs `pal_eval` at 1 k positions per mode (expect float32: <= 1e-5, oklab <= 1e-4; steps may differ only
   at band edges).
3. `uPalCtl.y` from an expression (beat drive) changes colour without a shader recompile; the CHOP cooks only on
   palette edits (cook count over 300 frames = edits).
4. Cost: one `pxPal` per pixel at 1080x1920 (rgb < 0.05 ms expected, oklab ~0.1 ms); report real fps.
5. FX_palette_map renders identically after this change (its functions are untouched: diff 0).

## Open
- PNG palette images (1 x N swatches) read as an image source work through `stops_from_pixels` only by clustering;
  an exact "one pixel per stop" reader is not built.
- Per-stop alpha is not in the convention (a vec4 holds rgb + pos); add a second array only when a consumer needs it.
