# AV: Native Background Removal on macOS (Apple Vision person mask as a C++ TOP)

Researched 2026-10-26. Nothing was loaded into TD, no binary was run, no pip. Source: Derivative asset 73414 + its GitHub repo.
Files: `research_src/bgremoval_73414/` (`repo/` shallow clone 2.3 MB, `release/` v1.2 zip + sha256, `exp/` toeexpand of the example).

## 1. What it is

- Derivative asset page "Native Background Removal on macOS" (https://derivative.ca/community-post/asset/native-background-removal-macos/73414),
  author aaronmylespereira, posted 2025-11-28, free, no comments. Page says: modelled on NVIDIA background removal, runs on Apple's
  neural engine through a CPlusPlus TOP, outputs an alpha mask of the person; Full HD about 30 ms; "fairly heavy"; quality Accurate / Balanced / Fast.
  Page states no macOS, TD build, architecture or licence (all from the repo instead).
- Repo https://github.com/aaronmylespereira/AppleVisionMask-TouchDesigner (MIT, 1 commit on main, last push 2026-03-11, releases v1.0 Nov 2025, v1.2 Mar 2026).
  No forum thread or video linked.
- Tech (source read): **Apple Vision `VNGeneratePersonSegmentationRequest`** (not Core ML directly, not AVFoundation matte). Request reused,
  `outputPixelFormat = OneComponent8`, `VNImageRequestHandler initWithCVPixelBuffer` on a serial dispatch queue (async).

## 2. Packaging, I/O, parameters

- Objective-C++ `.mm` **Custom (CPlusPlus) TOP**, built as a CMake MODULE bundle `AppleVisionMask.plugin`. Loaded in a CPlusPlus TOP's `plugin` par
  (the example .toe stores `/Users/aaronpereira/BGRemove/build/AppleVisionMask.plugin`, so the path must be repointed). TOP API version 12 header
  (`TOPCPlusPlusAPIVersion = 12`); whether 2025.31550 accepts it is UNVERIFIED (settled by the live test, step 5).
- Input: one TOP, downloaded to CPU as BGRA8 (`downloadTexture`, so a GPU->CPU readback each frame). Execute mode CPUMem.
- Output 0: mask (`Maskonly` = 8-bit A8 single channel, or `Composited` = white RGB + alpha as mask). Output 1: the input delayed to match the mask
  latency (read it with a Render Select TOP, Color Buffer Index 1). Info CHOP: `latency_frames`, `queue_size`.
- Pars: Opacity, Output Mode, Vision Quality (Accurate/Balanced/Fast), Sync Delay (frames, default 3), Process Every N Frames, Output Resolution
  (Input = bilinear upscale of the mask / Native = model size, faster).
- Mask is the model's native size (low-res), upscaled bilinear on the CPU: edges are soft; hair/fingers are only as good as Apple's model.
- Speed (claims only): page 30 ms Full HD; README "stable 60 fps at least on M3 Max", 2-4 frames latency. No numbers of ours.

## 3. Requirements and audit

- macOS: Vision person segmentation needs macOS 12+; repo states only "macOS, Apple Silicon recommended". Our Mac: macOS 27.0, arm64 hardware.
- Licence MIT (LICENSE in repo). Plugin header says "Author Name / email@email.com" (template left in).
- Audit (source read, 3 .mm files; `CPlusPlus_Common.h` / `TOP_CPlusPlusBase.h` are Derivative's stock headers): links only Vision, CoreVideo,
  Foundation, CoreFoundation, libc++, libSystem, libobjc. **No network, no subprocess, no eval, no pip.** `strings` on the release binary: no http,
  no /bin/, no NSTask/popen/socket. No file writes. Runs entirely in the TD process. `MyBackgroundRemover.*` is an unused earlier copy (not in CMake).
- Signing: adhoc, linker-signed, no TeamIdentifier, not notarized (per project rule, not a gate). The README says to strip the quarantine xattr;
  the downloaded zip we have carries only `com.apple.provenance`.
- Repo oddity: `build/` (CMake cache, `.o`, a built plugin) is committed; all arm64. Release v1.2 zip sha256
  `60fc3860fee757be87348e3de50fffcef00592189ef749d13329d08a2c7f99c8`.

## 4. Rosetta feasibility verdict

**Live (26 Oct, 31550, scratch TD, T-99):** loads by path at runtime; 1080p input 5.9-6.5 ms (CPU readback), 960x540 input 2.6-3.2 ms, 60 fps; latency Fast 2 / Balanced 3-4 / Accurate 7 frames; Fast loses parts of the body, Balanced soft, Accurate crisp. Go at 960x540 Balanced.

**The shipped binary will NOT load in our TD.** `/Applications/TouchDesigner 2.app/Contents/MacOS/TouchDesigner` is `Mach-O 64-bit executable x86_64`
(version 2025.31550). Both the release plugin and the committed build output are:

```
Mach-O 64-bit bundle arm64    lipo -info: Non-fat file ... is architecture: arm64
```

CMakeLists hard-codes `CMAKE_OSX_ARCHITECTURES "arm64"`. An x86_64 process cannot dlopen an arm64-only bundle (arch mismatch error in the CPlusPlus TOP).
(Same family of problem as Alaghast's Apple Vision Suite TOP, a separate asset, "Apple Silicon" only; not evaluated here.)

**Fix is small: rebuild from source for x86_64 (or universal).** Source is 472 lines + stock headers, uses only system frameworks, MIT.
Xcode is installed (`/Applications/Xcode.app`, clang present); cmake is NOT installed, but plain clang suffices (recipe below), so no install is needed.
Open questions for the live test (UNVERIFIED):
1. Vision under Rosetta: the x86_64 process calls the system Vision framework through Rosetta's translated frameworks. It should work, but the
   Neural Engine is probably not reachable from a translated process, so inference likely runs on CPU/GPU: slower than the author's numbers.
   Measure on the stored clip with the Info CHOP and `td_perf`.
2. TOP API 12 vs build 31550 (header mismatch makes TD reject the plugin; then rebuild with 31550's own `TOP_CPlusPlusBase.h`/`CPlusPlus_Common.h` from the app's samples if present, else the author's headers).
3. Whether a plugin must live in `~/Library/Application Support/Derivative/TouchDesigner099/Plugins` or can be pointed at by path (the .toe uses a path).

## 5. Comparison with native options on 31550

| Option | Mac / Rosetta | Notes |
|---|---|---|
| Nvidia Background TOP | Windows + NVIDIA only | not available on this Mac |
| Chroma Key TOP / Luma Key / GLSL difference | yes, any GPU | needs a green screen or static background; zero ML, cheapest, hard edges tunable with Blur/Level; the safe fallback for IMAG |
| MediaPipe selfie segmentation (browser/Web Render TOP or MediaPipe tox, see D_camera_mediapipe.md) | yes (WebGL/CPU in Chromium) | mask quality good, but needs a Web Render TOP route or the tox; heavier setup |
| This plugin (Apple Vision) | only after an x86_64 rebuild | best quality per effort on Apple hardware; not a certainty under Rosetta |

## 6. Gated install + test recipe (needs the user's OK for the build and for loading anything into TD)

Test input is the stored clip only: `media/webcam/webcam_ref_5s.mp4` (1920x1080, 30 fps) in a Movie File In TOP; no camera.
1. User OK for: compiling (writes only in a new scratch dir) and loading a plugin into a scratch TD project (not `JazibTD_home.toe`).
2. Build x86_64 (no cmake needed), from a scratch copy, e.g.:
   `clang++ -std=c++17 -fobjc-arc -arch x86_64 -bundle -o AppleVisionMask AppleVisionMask.mm -framework Vision -framework CoreVideo -framework Foundation -framework CoreFoundation`
   then place it in `AppleVisionMask.plugin/Contents/MacOS/` with the repo's `Info.plist`. (Add `-arch arm64` too for universal.) Verify
   `lipo -info` shows x86_64, `otool -L` unchanged, `codesign -s - -f` ad hoc.
3. New scratch project; Movie File In (stored clip) -> CPlusPlus TOP (par `plugin` = the new bundle) -> `td_errors` must be clean. If "wrong architecture"
   or API-version error: stop and record it in LEARNINGS.
4. Set Output Mode Maskonly, Quality Fast / Balanced / Accurate in turn; Info CHOP `latency_frames`, `td_perf` cook ms and `td_screenshot` of the mask each.
   Record ms per level in LEARNINGS and in section 4 here (that decides if Rosetta is fast enough at 1080p; try Native resolution too).
5. Rollback: delete the scratch project and the built bundle; nothing else was touched.

## 7. How it would feed a PF26 IMAG alpha frame

IMAG frame = designed frame (light-native, all slices) with a real alpha window over the camera. Two different uses, pick by the brief:
- **Person cut-out over a look** (artist on the LED wall with a generated background): camera -> CPlusPlus TOP (mask) -> Level/Blur/Threshold for edge
  -> Over/Composite onto the look; use Output 1 (delayed original, Render Select index 1) as the RGB so the colour and mask are frame-aligned, then
  `Premult` by the mask. Keep the delay (default 3 frames, about 100 ms at 30 fps) in mind against audio/camera sync of other layers.
- **Rectangular window over the live feed** (frame with a hole): no segmentation needed, a plain rectangle/rounded-rect alpha; this plugin is only
  for shaped (person) holes or "person in front of frame" depth effects.
- Output towards Resolume: alpha clips/Syphon must be premultiplied (memory: overlay-alpha-premultiplied); verify with Arena's blend, not a straight composite.

## 8. FUTURE.md-style notes

| Feature | Build gate | Status | Where | How to enable |
|---|---|---|---|---|
| Apple Vision person mask TOP for IMAG cut-outs | 31550 x86_64 needs an x86_64 rebuild; shipped plugin is arm64-only | idea only, no TD load done | docs/research/AV_macos_background_removal.md | user OK, section 6 steps 1-5 on the stored clip |
| Same plugin on a native arm64 TD (if the user ever moves off Rosetta) | arm64 TD build | would work as shipped (still adhoc/quarantine) | same file | `xattr -dr com.apple.quarantine` then load by path |

## 9. Open questions for the user

1. OK to compile the plugin from source (x86_64) into a scratch dir and load it into a scratch TD project to measure Rosetta speed on the stored clip?
2. Does IMAG need a person-shaped cut-out at all, or only a rectangular/shaped alpha window (then no plugin)?
3. Is a green-screen/static-background chroma route acceptable as the primary, with Apple Vision as the optional upgrade?
