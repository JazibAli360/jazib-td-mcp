# bg_person_mask - Apple Vision person mask (CPlusPlus TOP)

Status (26 Oct 2026 18:24): **loaded by path and measured in the scratch TD (LEARNINGS T-99); not loaded in the main TD.** Verdict: go at 960x540 input + Balanced (2.7 ms cook, 3 frames latency, 60 fps); mask is in alpha only; main-TD load waits for the user's OK. **The lab COMP is `/project1/lab/CV_person_mask` (`docs/builds/person_mask.md`): built on main with Vision off; never unload/reload the plugin while it runs (T-106).** Before: A later lane loads and measures it in a **scratch** TD
project (never `JazibTD_home.toe` first). Source, provenance, build and binary checks: `helpers/bgremoval/README.md`.
Research, audit and IMAG use: `docs/research/AV_macos_background_removal.md`.

## What it is

`helpers/bgremoval/build/AppleVisionMask.plugin` (universal x86_64 + arm64, rebuilt from the MIT upstream; TD 2025.31550
under Rosetta loads the x86_64 slice). One input TOP; Apple Vision `VNGeneratePersonSegmentationRequest` on a serial
queue (async, CPU readback of the input each frame).

- Op type `Applevisionmask`, label "Apple Vision Mask", 1 input.
- Output 0: mask. Output 1: the input delayed to match the mask (Render Select TOP, Color Buffer Index 1).
- Info CHOP: 2 channels (latency frames, queue size).
- Pars: `Opacity` (float, 1), `Outputmode` (`Composited` | `Maskonly`, default Maskonly), `Quality` (`Accurate` |
  `Balanced` | `Fast`, default Balanced), `Syncframes` (int, 3), `Processinterval` (int, 1),
  `Nativeresolution` (`Input` | `Native`, default Input).

## How to load (pick one)

1. **By path (preferred for the test, no TD restart):** create a CPlusPlus TOP in the scratch project and set its
   `plugin` par to the absolute path
   `~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/bgremoval/build/AppleVisionMask.plugin`.
   TD loads the bundle into its process at that moment; a native crash takes TD down (watchdog T-77 recovers), so save
   first and do it only in the scratch TD.
2. **Plugin folder (needs a TD restart):** copy the bundle into
   `~/Library/Application Support/Derivative/TouchDesigner099/Plugins/<subfolder>/` (system-wide, every project) or into
   a `Plugins/` folder next to the scratch `.toe` (that project only); then it appears as "Apple Vision Mask" in the
   TOP Create dialog. Only after the by-path test passed, and with the user's OK.

Rollback: delete the CPlusPlus TOP (path route) or the copied bundle (folder route, then restart TD).

## Test recipe (scratch TD, build 31550, stored clip only)

1. `td_status` / `td_errors` clean; scratch project; save.
2. Movie File In TOP `media/webcam/webcam_ref_5s.mp4` (1920x1080, 30 fps) -> CPlusPlus TOP (path above) -> Null.
   Info CHOP on the CPlusPlus TOP; Render Select TOP (index 1) for the delayed RGB.
3. `td_errors` must be clean. "wrong architecture" / "could not load" / API-version error: stop, LEARNINGS T-nn, no retry
   loop.
4. `Outputmode = Maskonly`; for `Quality` Fast, Balanced, Accurate in turn (and `Nativeresolution` Native vs Input):
   `td_perf` cook ms of the CPlusPlus TOP, project fps (60 target, <= 3 ms per COMP), Info CHOP latency frames,
   `td_screenshot` of the mask. Vision runs translated under Rosetta (likely no Neural Engine), so expect slower than
   the author's ~30 ms Full HD; if over budget, try `Processinterval` 2-3 and a 960x540 input (Fit/Resolution TOP before it).
5. Composite check: Render Select (delayed RGB) x mask -> Premultiply -> Over a test look; edges with Level/Blur.
   Towards Resolume the result goes out premultiplied (overlay-alpha rule).
6. Record ms per quality level + verdict in LEARNINGS T-nn and in `docs/research/AV_macos_background_removal.md` section 4.
