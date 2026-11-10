# person_mask - `/project1/lab/CV_person_mask` (TD 2025.31550, 26 Oct 2026)

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

Apple Vision person matte -> premultiplied cut-out, matte and inverse. Uses the AppleVisionMask C++ TOP
(`helpers/bgremoval/build/AppleVisionMask.plugin`, provenance `helpers/bgremoval/README.md`) loaded **by absolute
path** at runtime, never from the per-user Plugins folder (T-81, T-99).

**State:** built on the main TD with **Visionon off** (plugin not loaded there: the main-TD load waits for the user's
OK, `docs/builds/bg_person_mask.md`). With Vision off the matte is full (pass-through). Everything below with Vision
on was verified on the **scratch TD**. To turn it on in the main TD: `Setup > Vision on` (or
`build('/project1/lab', vision=True)`); load before doors (native load).

## Files
- `builders/person_mask.py` - `build(parent_path='/project1/lab', name='CV_person_mask', controls=True, vision=None)`,
  idempotent, T-70 safe: `g = dict(globals()); exec(open('<repo>/builders/person_mask.py').read(), g); g['build']('/project1/lab')`
- `builders/person_mask_logic.py` - pure logic (Vision input size, Feather/Grow -> blur + edge remap, temporal,
  latency -> cache index, composite reference), copied into the COMP as `person_mask_logic`.
- `test/test_person_mask.py` - 20 offline tests: `python3 -I -m unittest discover -s test -p 'test_person_mask.py'`.

## How it works
`clip` (stored webcam clip) or `in1` -> `src` -> `vis_in` (Resolution TOP, Inputscale; half of 1080p = 960x540, the
fast path) -> `avm` (C++ TOP, Outputmode Maskonly, mask in **alpha only**) -> `mask_sel` (Vision off -> `nomask`,
alpha 1) -> `mask_blur` (gaussian, size = 2 x (Feather + |Grow|)) -> **`matte`** (one compute pass at source size:
linear remap [lo, hi] from `edge_params`, `mix(new, last, Smooth)` with `matte_fb`, Invert) -> **`comp`** (one
compute pass: person = delayed source or Fill colour, over transparent / Bg colour / `in2`, **premultiplied**) ->
`out1`. `matte_view` -> `out2` (white = person), `inverse` -> `out3`. RGB delay: `rgb_delay` = Cache TOP on the
full-res source at index `-latency_frames` (avm_info), or the plugin's own delayed RGB (`avm_rgb`, Render Select
`bufferindex` 1, mask res), or none. Compute mode only (T-46/T-47).

## Pars
- **Matte** (knobs): Feather px, Choke/grow px (+ grows, - chokes; px at Vision input size), Temporal smooth (0..0.95),
  Invert, Opacity.
- **Look** (knobs): Person (source / fill), Fill colour, Background (transparent / colour / in2), Bg colour, Bg alpha,
  View on out1 (cut-out / matte / inverse).
- **Setup**: Vision on (loads the plugin once; off = bypass, never unload: T-106), Vision quality (Fast / Balanced /
  Accurate), Vision input size (full / half / quarter / fixed 960 long side), Vision resolution (Input / Native),
  RGB delay (match / plugin / none), Source, Clip file, Plugin path, Reset smoothing (pulse).

## Verified (26 Oct, 31550)
Scratch TD (pid 45327), `media/demo/faces/ward_cunningham_8s.mp4` (1280x720, clear person), Inputscale fixed = 960x540,
Balanced, pane off the COMP, out1..3 pulled each frame by a run() chain:

| Check | Result |
|---|---|
| mask in alpha only | avm RGB max 0; avm alpha > 0.5 = 35.26 %, matte coverage 35.26 % (Feather 2, Grow 0) |
| Feather (Grow 0) | coverage 35.20 / 35.20 / 35.18 % at F 0 / 2 / 8; soft-edge band 2.39 -> 3.00 -> 6.26 % |
| Choke/grow (F 2) | -6 px 33.26 %, 0 35.20 %, +6 37.01 %, +12 38.97 % (monotonic, about symmetric) |
| Temporal smooth 0.7 | step 0 -> 1: 0.298 0.510 0.655 0.761 0.831 vs 1 - 0.7^n 0.300 0.510 0.657 0.760 0.832 |
| Invert | coverage 64.71 % (= 100 - 35.29) |
| matte + inverse | max error 0.0039 (one 8-bit step) |
| premultiplied | 0 pixels with rgb > alpha in every mode; out1 alpha == matte (max diff 0) |
| Fill colour (1, 0, 0.5) | person rgb 0.992 / 0 / 0.498 |
| Bg colour blue | alpha 1 everywhere, outside rgb 0.001 / 0.001 / 0.997 |
| RGB delay | plugin RGB vs source over 90 frames of the ramp clip: best match at lag 3 (error 0) = latency_frames 3 = cache index -3 |
| stability | 8 Vision on/off (bypass) cycles, 12 Quality x Inputscale changes every 30 frames, a rebuild with the plugin running: no errors, no crash |

**Cost** (scratch, 240 frames): avm **2.8 ms CPU** median (T-99: 2.7) + 9.9 ms GPU timer (synchronous readback wait,
does not cost fps); own ops ~1.7 ms (mask_blur 0.58, rgb_delay 0.44, matte 0.29, comp 0.19, rest < 0.1 each);
**real 60.0 fps**. Vision off: own ops ~0.7 ms, 60 fps.
Main TD (Vision off, stored 1080p webcam clip, other lanes building): real 60.0 fps with the COMP cooking and pulled
(one earlier window at 48 fps under other lanes' load; 60.0 with the COMP parked in the same session). The clip's
1080p decode (~0.8 ms CPU, large GPU upload timer) is test content, not the effect.
Capture: `pm_main_network.png` (session scratchpad).

## Notes / left
- With Vision on, the COMP is ~4.5 ms per frame (2.8 plugin CPU + 1.7 own): over the 3 ms aim because of the plugin
  itself; `Inputscale` quarter or Fast cut it (T-99 numbers). Off = bypass, so Vision costs nothing while off.
- `latency_frames` changes with Quality (Fast 2, Balanced 3, Accurate 7); the cache follows it live; expect one empty
  frame on a Quality switch (T-99).
- webcam_ref_5s.mp4 has the head only at the bottom edge (0-5 % coverage, T-99): use the ward clip or a real camera to
  judge quality.
- Never unload/reload the plugin while it runs (T-106). Delete the COMP only after Vision off + >= 10 frames.
- Not done: main-TD plugin load (user OK), real camera input, a 1080x1920 portrait source.

## Light wrap + despill (FX7c 7C-08, lane F, 27 Oct 2026)
Wrap page: `Lightwrap` (0 = off), `Wrapwidth` px (edge band = ring of 16 matte taps at Wrapwidth and Wrapwidth / 2),
`Wrapblur` px (blur of the wrap light), `Wrapgamma` (band falloff), `Wrapsrc` background (in2, or the Bg colour when
Background = colour) / source (the blurred camera picture itself: no plate needed), `Despill` (green pulled to
max(r, b) on the person). One compute pass `wrap` after `comp`: band = m x (1 - mean ring m) ^ gamma, person rgb
screened with Lightwrap x band x light **scaled by the matte**, so the output stays premultiplied (rgb <= alpha);
`wrap_sel` = comp exactly while Lightwrap and Despill are 0 (wrap / wrap_blur not cooked). Reference
`person_mask_logic.wrap_ref`; tests `test/test_person_mask_wrap.py` (4, glslc of the pass).

Verified live (b2, 31550; Vision off, a 960x540 circle matte wired into mask_sel for the check, removed after, the
stored clip paused): out1 vs `wrap_ref(comp, matte, wrap_blur)` max 5.1e-4, over 2/255 **0**; 2.1 % of pixels changed
(the edge band); premultiplied violations 0; Lightwrap 0 + Despill 0: out1 = comp (diff **0**). Cost at 1920x1080
(clip playing, Wrapsrc source): wrap 0.50 ms + wrap_blur 1.10 ms; with a static in2 the blur cooks once. The Blur
TOP's FIRST cook took 819 ms (one freeze when the wrap is first switched on: switch it on before doors).
In main (27 Oct, JazibTD_home.654): rebuilt by its builder (un-parked for the step, T-146; Visionon was already on in
main and kept), Wrap page + panel (17 knobs), td_errors none, `wrap_sel` = comp at rest (Lightwrap 0), re-parked;
library `CV_person_mask` 0.2.0.
