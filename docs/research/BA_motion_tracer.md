# BA: Motion Tracer Effect Tool (dcheesman) and our own motion-trail COMP

Researched 2026-10-26. Nothing loaded into TD, nothing run. Files: `research_src/motiontracer_69710/SOURCES.md` only (no downloadable file exists).

## 1. What it is (evidence we have)

- Derivative asset 69710 "Motion Tracer Effect Tool", author dcheesman (Dean Cheesman, Provo, Utah), posted 2024-06-28, tag "Motion Trace Effect",
  665 views, 0 comments. The page has **no description, no parameter list, no TD build, no OS, no price/licence**.
- Links: YouTube https://youtu.be/FbILBVxFOR0 ("Motion Trace Effect tool for TouchDesigner"; only the title was readable, no description/transcript),
  Patreon post "Motion Tracer" (the .tox is "on my Patreon"; **HTTP 403 for us, not bypassed**), author site deancheesman.com. No GitHub, no forum thread.
- So: **paid/Patreon-gated .tox, unauditable by us, internals unknown.** Everything about how it is built is UNVERIFIED. By its name it is a
  motion-trail look (moving things leave traces); the exact method (frame difference + feedback vs cache/time displacement vs optical flow) is not stated anywhere we could read.
- Price/licence: not shown on the page (Patreon membership presumed; UNVERIFIED). Mac/Windows: not stated.

## 2. Audit

Not possible (no file). Rule: do not subscribe/buy on our own; if the user wants it, they download it and we `toeexpand` + audit before any load.

## 3. Relevant 31550 facts (from our op index, docs/research/ops)

- `cacheTOP`, `timemachineTOP`, `cacheselectTOP`, `feedbackTOP`, `glslTOP`, `glslmultiTOP`, `compositeTOP`, `levelTOP`, `lookupTOP` exist in the 31550 index.
- **`opticalflowTOP` is NOT usable here** (Nvidia-only; T-18 proved it unsupported although it creates). If Motion Tracer used it, it would not work on this Mac.
  Alternative: OpenCV Farneback in a Script TOP (verified in TOP.md, CPU, keep images small).
- T-46: multi-pass GLSL can tear on this Mac; compute-mode GLSL is clean. Avoid multi-pass GLSL TOP; use stock TOPs or one compute-mode shader.
- VRAM (arithmetic): one RGBA8 frame = W*H*4 bytes; 1920x1080 = 8.3 MB, so a 60-frame cache = 498 MB; 8-bit 1280x720 x 60 = 221 MB. Use 8-bit and a
  reduced working resolution for the trail; upscale at the end. Float32 x4 this.

## 4. Verdict

Not adopted, not purchased: no evidence, no audit, no way to test. Build our own (stock ops only, self-contained, audited by construction).

## 5. Recipe: `motion_trail` COMP (in TOP, out TOP only)

Custom pars (page "Trail"): `Length` (frames, 1-60, int), `Decay` (0-1, float, how fast old trail fades), `Threshold` (0-1, motion cutoff),
`Softness` (0-0.2), `Agecolor` (menu: Off / Ramp), `Colornew`/`Colorold` (RGB), `Mix` (0-1 blend of trail over source), `Quality` (Full/Half res working size).

Network (L to R, titled boxes: Input, Motion, Trail, Colour, Output):
1. `in1` -> Resolution/Fit TOP (Half-res option via `Quality`) -> Level TOP to luma (monochrome, 8-bit).
2. **Motion**: Cache TOP (`Cache size` 2) holds previous frame; Composite TOP `difference` of current vs previous (Cache Select with index 1) -> Level TOP (Threshold: brightness1 offset / contrast) -> Blur/Edge TOP optional for Softness. Result = per-frame motion mask.
3. **Trail** (feedback, no GLSL): Feedback TOP target = Composite TOP `maximum` of (new motion mask, Level TOP of feedback * (1 - Decay)); Level brightness1 = 1-Decay gives exponential fade, so `Length` ~ 1/Decay frames. Fixed 8-bit; clamp so it does not stick at 1/255 (add small subtract, e.g. Level post-offset -0.004).
4. **Colour by age** (alternative/extra, cache based): Cache TOP size = `Length`; Cache Select taps at ages 0, L/4, L/2, 3L/4 (or Time Machine TOP) each multiplied by Ramp colour age k, composited `add`/`maximum`. Cost = Length frames of VRAM (section 3). Cheaper: with the feedback path, store age in the Lookup TOP: Lookup TOP maps trail intensity (1 = fresh, 0 = old) through a Ramp TOP (Colornew -> Colorold), so colour-by-age is free (intensity encodes age).
5. Output: Composite `over` trail (premultiplied by mask) on source by `Mix`; `out1`. Nothing else leaves the COMP; no Python beyond par expressions, no network, no subprocess.
6. Performance target: all stock TOPs, GPU, one feedback loop, 720p working size; expected cheap. No numbers of ours yet.

Test (when the user says go; webcam rule): Movie File In TOP on `media/webcam/webcam_ref_5s.mp4` (loop), never the live camera unless asked. Checks: (a) static scene -> trail empty after Decay; (b) moving hand -> trail length visibly scales with `Length`/`Decay`; (c) `Threshold` kills sensor noise; (d) `td_perf` cook time, GPU memory before/after at Length 60; (e) no tearing on screenshot (T-46); (f) loop point of the 5 s clip does not leave a ghost (reset feedback on loop).

## 6. Open questions for the user

- Do you want the Patreon .tox downloaded by you so we can audit it? Otherwise we build only the recipe above.
- Trail look for IMAG: white-only ghost, or colour-by-age in PRISM palette?
