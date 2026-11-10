# A - TouchDesigner 2025.31550: how to make show visuals, concretely (research, 16 Oct 2026)

Agent A for the lead. Build: **2025.31550**, `/Applications/TouchDesigner 2.app`, Rosetta, Apple M1 Max. Research only; nothing was built for
the show. Live probes ran in `/project1/_research_probe` (deleted, project not saved, `/jazib_mcp` untouched). Evidence images:
`refs/A_td_howto/` (`SOURCES.md`). Notation: **probed** = ran live in 2025.31550; **doc** = URL cited; **unverified** = memory or older build.

## Short answer (the facts that matter)
1. **This install is TouchDesigner Pro. There is no 1280x1280 cap.** Probed: `licenses.type` = `'TouchDesigner Pro'`, `licenses.isPro` = True,
   `licenses.isNonCommercial` = False. A 9984x3840 float32 noise TOP rendered with real pixels (numpyArray shape (3840, 9984, 4), 613 MB).
2. A real **ProRes 422 HQ file at 7488x2880** was written by Movie File Out TOP and read back with ffprobe (`prores`, `apch`, 7488x2880,
   yuv422p10le), and so was **Hap Q at 7488x2880** (`HapY`). Non-realtime recording wrote 1 file frame per timeline frame; realtime recording at that size dropped frames.
3. TD **cannot write DXV** (no DXV in the codec menu). PF26's chain (ProRes master -> DXV3) stays as in `production/SYSTEM.md`; TD supplies the ProRes master.
4. GLSL on macOS is **not OpenGL 4.1** any more (Vulkan on MoltenVK/Metal): GLSL TOP `glslversion` offers 430-460, probed `__VERSION__` = 430 default, 460 selectable.
   The td-port note "TD on macOS is GL 4.1" (td-port/LEARNINGS.md) is out of date for this build.
5. **Urdu in the Text TOP shapes and joins correctly** (probed, with Noto Nastaliq Urdu and Geeza Pro, both installed).
6. **POPs exist and work** (97 POP classes; particle chain, POP instancing rendered).

## 1. Licence and resolution cap
- Probed (`td_exec`): `licenses.type` -> `'TouchDesigner Pro'`; `licenses.isPro` -> `True`; `licenses.isNonCommercial` -> `False`; `len(licenses.dongles)` -> 0
  (a software licence). `licenses.type` is documented as the highest-ranking licence installed
  ([Licenses Class](https://derivative.ca/UserGuide/Licenses_Class)). Not read on purpose: `systemCode` (machine id); not touched: `install`, `disablePro`,
  `app.addResolutionLimit/removeResolutionLimit/addNonCommercialLimit/removeNonCommercialLimit` (they exist in `dir(app)`).
- Docs: Non-Commercial = "image resolution is limited to 1280x1280" (1 or 2 px high images may be wider), excludes Shared Memory / DirectX OPs, one-time keys
  ([TouchDesigner Non-Commercial](https://derivative.ca/UserGuide/TouchDesigner_Non-Commercial), [Licensing](https://docs.derivative.ca/Licensing)). Commercial, Educational and Pro: "Unlimited" resolution.
  Pro adds Sync In/Out, RenderStream, camera tracking, private .toe, Clip Blender, support. Prices on the shop page: Commercial $600, Pro $2,200.
- Evidence the cap is absent (probed): 7488x2880 and 9984x3840 constants cooked at full size in rgba8/16fixed/16float/32float with no errors or warnings; the
  noise TOP at 9984x3840 float16 returned a 3840x9984x4 float32 array. Writing: see section 4.
- **The other app differs:** `/Applications/TouchDesigner.app` is 2025.32820, arm64 (lipo; Info.plist). td-port/LEARNINGS.md records it as Non-Commercial (that app was not run by me,
  so its current licence is unverified). If it were ever used for PF26 renders, the 1280x1280 cap would block them. This install is the one for show work.
- Resolume Alley is installed (`/Applications/Resolume Alley`); not probed.

## 2. What is new in the 2025 series that matters for visuals
Release notes: [Release Notes](https://docs.derivative.ca/Release_Notes) (2025.31550 is the Oct 30 2025 official build; the series also has 31760, 32050, 32280, 32460, 32820, 33070, 33230 (Sep 2026)).
The user's 2025.31550 build has everything in its own section only; later builds add more POPs (Script POP, Text POP, Trace POP are named in later builds, not in this one - confirmed below by the live class list).
- **POPs (Point Operators), headline feature of 2025.31550.** doc: GPU operator family for point data with attributes (P, Color, N, user attributes), outputs to Render TOP, DMX, lasers, LEDs
  ([POP](https://docs.derivative.ca/POP), [Particle POP](https://docs.derivative.ca/Particle_POP): "fully run on the GPU", millions of points).
  Probed: **97 POP classes** in `td`, among them: `particlePOP, noisePOP, gridPOP, spherePOP, boxPOP, torusPOP, tubePOP, circlePOP, linePOP, curvePOP, pointgeneratorPOP, forceradialPOP, fieldPOP,
  feedbackPOP, trailPOP, copyPOP, transformPOP, mathPOP, glslPOP, glsladvancedPOP, glslcopyPOP, glslselectPOP, proximityPOP, neighborPOP, sprinklePOP, lookuptexturePOP, texturemapPOP,
  toptoPOP / poptoTOP, choptoPOP, dattoPOP, soptoPOP, fileinPOP, fileoutPOP, alembicinPOP, pointfileinPOP, skinPOP, skindeformPOP, dmxfixturePOP, dmxoutPOP`. No `scriptPOP/textPOP/tracePOP`.
  Geometry COMP in this build holds POPs: a new `geometryCOMP` contains `torus1` whose `family` is `POP` (probed). FBX/USD COMPs default to POPs (doc, release notes).
- **New TOPs in this build (doc):** Layer Mix TOP (unlimited layers, per-layer adjustments), Render Simple TOP (geometry without cameras/lights), NVIDIA RTX Video TOP, ST2110 In/Out TOP.
  Probed: `layermixTOP, rendersimpleTOP, poptoTOP, toptoPOP, st2110inTOP/outTOP, syphonspoutinTOP/outTOP, ndiinTOP/ndioutTOP, glslmultiTOP, feedbackTOP, cacheTOP, layoutTOP, tileTOP, textTOP, webrenderTOP,
  moviefileinTOP/outTOP, svgTOP, opencolorioTOP, bloomTOP, tonemapTOP, ssaoTOP, opticalflowTOP, nvidia*TOP` exist as classes (148 TOP classes). Caution: `td` lists classes that are Windows-only (`directxinTOP`, `nvidia*`),
  so a class existing is not proof it works on a Mac.
- **GLSL:** probed on a GLSL TOP: `glslversion` menu = `glsl120, glsl430, glsl440, glsl450, glsl460`; `__VERSION__` evaluated to **430** (new TOP default) and **460** after selecting `glsl460`.
  `GL_KHR_shader_subgroup_basic`, `GL_ARB_gpu_shader_int64`, `GL_EXT_shader_explicit_arithmetic_types_float16` are all defined (probed with `#ifdef`). GLSL TOP `mode` = `vertexpixel` or `compute`; it can take POP data (`buffer0pop`),
  `compilebehavior` = stalluntildone / threadedcheckerboard / threadedblack / threadedprevious. Doc for the switch: the 2022 official release notes say OpenGL was removed, Vulkan is the graphics API, macOS uses MoltenVK on Metal,
  GLSL on macOS rises from 3.30 to 4.60 and compute shaders work on macOS ([2022.24200 notes](https://derivative.ca/release/202224200/66252)). Release note 2025.31550 also: GLSL TOP recompiles when input size changes,
  `TDCreateRotMatrix()` in all shaders, Noise TOP gradient for 4D Simplex/Perlin. GLSL MAT adds `TDImageStore_*/TDImageLoad_*`. Geometry shaders are not available on Metal (doc search summary of the same 2022 page; unverified on this build).
- **Rosetta (why Intel).** Facts: `TouchDesigner 2.app` binary is `x86_64` (lipo); `sysctl sysctl.proc_translated` = 1 while TD runs (probed from TD's Python); `hw.optional.arm64` = 1 (M1 Max). Per td-port/LEARNINGS.md the user chose to keep TD 2
  (reasons recorded there: it is the 31550 install; the native app is Non-Commercial). I found **no Derivative statement** on why/if an Intel build is needed, or on its perf cost. Known measured consequences (td-port/LEARNINGS.md, 13 Oct):
  TD's Python is x86_64 3.11.10 + numpy 2.1.2; Script CHOP maths ran ~2x slower than native; C++ plugins must be built x86_64 (universal works). GPU work still goes through Vulkan->Metal; I have **no measurement** of GPU
  cost under Rosetta (unverified that it is nil). Apple's own Rosetta timeline (Rosetta limited from macOS 28) is from [eclecticlight](https://eclecticlight.co/2026/03/14/how-to-survive-the-loss-of-rosetta/) and Apple support pages via search; the Mac here
  reports OS 27 (`app.osVersion` = 27.0). Relevant only for later TD upgrades.
- Python: 3.11.10 + NumPy 2.1.2 (release notes; matches `app.pythonExecutable`). Minimum macOS 12, GPU memory >= 4 GB, 8 GB recommended (release notes). Movie File Out hardware H.264/HEVC on macOS (release notes).

## 3. Big canvas
- GPU texture limit (probed): a Constant TOP asked for 32768x32768 reports **16384x16384** with the warning "Width clamped due to GPU limitations" (and height); 16384x6000 and 16384x16384 allocate with no warning.
  So 7488x2880 (75%) and 9984x3840 (100%) are well inside. Doc agrees in spirit: "resolution is only limited by GPU hardware, most GPUs allowing 16K" ([High-performance media](https://derivative.ca/feature/high-performance-media-systems/74)).
- Pixel formats (probed menu `format`): `rgba8fixed, rgba16float, rgba32float, rgb10a2fixed, rgba16fixed, rgba11float, mono8/16fixed, mono16/32float, rg8/16fixed, rg16/32float, a8/16fixed, a16/32float, monoalpha*`.
  All four of rgba8fixed / rgba16fixed / rgba16float / rgba32float cooked at 9984x3840.
- Memory per frame (probed `gpuMemory`, equals width*height*bytes):

| size | rgba8fixed | rgba16 (fixed/float) | rgba32float |
|---|---|---|---|
| 7488x2880 | 86.3 MB | 172.5 MB | 345.0 MB |
| 9984x3840 | 153.4 MB | 306.7 MB | 613.4 MB |

  A Feedback loop at 7488x2880 rgba16float holds at least one extra 172.5 MB buffer per feedback/cache; Release notes advise >= 8 GB GPU memory (4 GB minimum). This Mac has 64 GB unified memory (brief); GPU memory ceiling not probed.
- Readback: `numpyArray()` of the 9984x3840 float16-format TOP took 0.51 s (once, includes download; not a render figure). Only use it for checks, not per frame.
- Rendering many faces: build **one canvas TOP at 7488x2880** and cut faces with Crop TOPs (probed, below), or build each face at its own size and place with Layout/Composite. Face widths for R02 (20/10/10/10/30/10/10/10/20 ft, 130 ft total)
  at 57.6 px/ft: 1152, 576, 576, 576, 1728, 576, 576, 576, 1152 (sum 7488, probed: nine Crop TOPs gave exactly those sizes, 2880 high). Full 9984 wide = 76.8 px/ft: 1536/768/768/768/2304/768/768/768/1536 (arithmetic; not probed). Face heights are the lead's data; I assumed all faces are the full canvas height.

## 4. Getting frames out
### Movie File Out TOP codec menu (probed `par.videocodec`, par `videocodectype`, `videopixelformat`)
Containers: automatic, mov, mp4, mkv, webm. Types: movie, image, imagesequence, stopframemovie.
| codec (menu label) | sub-type menu | pixel formats (probed) |
|---|---|---|
| Apple ProRes (`prores`) | ProRes 422 HQ, 422, 422 LT, 422 Proxy, **4444**, **4444 XQ** | 422: yuv422 8/10/12 bit; 4444 / 4444 XQ: yuv444 10 bit or **yuva4444 12 bit (alpha)** |
| Hap (`hap`) | Hap, **Hap Q**, Hap R, Hap HDR | rgb / rgba (alpha); Hap HDR rgbu / rgbs |
| H.264, H.265/HEVC | - | yuv420 / yuv444 8 bit; H.265 also 10 bit |
| Animation (`rle`), GoPro-Cineform, NotchLC, Photo/Motion JPEG, MPEG 4, GIF, VP8, VP9, VVC/H.266 (slow), AV1 (NVIDIA) | - | Animation rgb/rgba, Cineform rgba, NotchLC rgb/rgba, VP9 yuv420/444/10 bit |
**No DXV, no HAP-only-DXV.** Image types: tiff, jpeg, bmp, exr, png, dds; image sequence writes those. Also ProRes alpha-recognition fix and new VVC/AV1/AAC/Opus in this build (release notes). Docs:
[Movie File Out TOP](https://docs.derivative.ca/Movie_File_Out_TOP): alpha codecs = Animation, Cineform, Hap/Hap Q; "Turning off the Realtime flag records without frame drops"; H.264/H.265/AV1 need Commercial/Pro (this is Pro); NVIDIA codecs need NVIDIA hardware.
[Hap](https://docs.derivative.ca/Hap): Hap Q = high quality for very high resolution; TD always encodes **12 chunks**; Hap R (BC7) "can hit GPU driver timeouts at high resolution"; secondary compression (Snappy) can be turned off for large frames.

### Recording tests (probed; files written to the session scratchpad and deleted afterwards)
Source: Noise TOP, rgba8fixed; Movie File Out TOP, `type=movie`, container automatic.
| test | result (ffprobe) |
|---|---|
| ProRes 422 HQ, 7488x2880, realtime on, ~30 timeline frames asked | `prores`/`apch`, 7488x2880, yuv422p10le, 60 fps, **1 frame**, 6.2 MB. Realtime recording at this size dropped almost all frames |
| Hap Q, 7488x2880, realtime on | `hap`/`HapY`, 7488x2880, **1 frame**, 7.5 MB |
| ProRes 422 HQ, 1280x720, realtime on, 261 timeline frames | **260 frames**, 104.9 MB |
| **ProRes 422 HQ, 7488x2880, `project.realTime = False`**, record on for 71 timeline frames (45150 -> 45221) | **69 frames**, 7488x2880, 426 MB (6.2 MB per noise frame; a noise frame is hard to compress, real content will differ). File was not readable (no moov) until a few seconds after Record went off |
Takeaways: (a) realtime recording of 7488x2880 is not safe; use non-realtime. (b) file frame count was within 2 of timeline frames at start/end boundaries, so start/stop must be driven exactly (see loops). (c) I did not test ProRes at 9984x3840, ProRes 4444, Hap alpha, image sequence output or the real-time Hap playback in Arena (unverified). (d) the 69-vs-71 gap is unexplained; measure start/end properly before trusting frame-exactness.
Offline procedure used: `project.realTime = False`; pump (Execute DAT `onFrameEnd` cooking the Movie File Out TOP, because an unviewed TOP does not cook - T-02); `par.record = True/False`; set `project.realTime = True` again afterwards.
Max-size doc: none found for ProRes or Hap in TD docs (searched; the Movie File Out page states no resolution limit). Resolume forum notes of old DXV3 export caps (8192 from Media Encoder/QuickTime) are old and about other tools ([forum](https://www.resolume.com/forum/viewtopic.php?p=92176)); not applicable to TD's writers; unverified for Arena 7.23.2.

### Frame-exact loops
Probed project timeline: `op('/').time.rate` 60, `start` 1, `end` 600, `loop` True (the user's home project; I changed nothing). **Unverified recipes (from general TD practice, not tested):**
set Start/End of the timeline (or a Timer CHOP) to the exact loop length N frames; drive every animated value from `absTime.frame % N / N` (a 0-1 loop phase) instead of `absTime.seconds`; for Noise TOP loop by moving on a circle in 4D noise
(Noise TOP 4D / `tz`+`period`, doc: release notes mention 4D derivatives) with `cos(2*pi*phase)`, `sin(2*pi*phase)`; feedback loops are not loop-safe (history) so crossfade the last K frames into the first K or pre-roll.
Use Movie File Out `limitlength` (`length` in `frames`) so the clip stops after exactly N frames, and start Record on the loop's first frame (Timer CHOP / CHOP export to `record`). Probed pars: `limitlength`, `length`, `lengthunit` (indices/frames/seconds), `fps`, `addframe`, `pause`, `type=stopframemovie`.
For stop-frame ("render N frames at any speed"): `type = stopframemovie`, `pause` on, pulse `addframe` per frame (doc: Add Frame requires Pause on).

### Live paths into Resolume 7.23.2 (probed existence only; not created, nothing started)
- `syphonspoutoutTOP` exists (class). Doc ([Syphon Spout Out TOP](https://docs.derivative.ca/Syphon_Spout_Out_TOP)): on macOS it is Syphon; **Syphon is limited to 8-bit RGBA**; Active par, Sender Name par; same computer only; no maximum size stated.
- `ndioutTOP` / `ndiinTOP` exist (class). Doc ([NDI Out TOP](https://docs.derivative.ca/NDI_Out_TOP)): Include Alpha toggle, 8/16-bit fixed output; page is silent on macOS and licence. Resolume Alley's folder contains `libndi.dylib` (file seen). Arena NDI behaviour at 7488x2880 is unverified.
- Not probed: Arena-side receive, frame rate at this size.

## 5. Audio-reactive and text
- **Audio (probed pars, no device opened):** `audiofileinCHOP` (`file, play, playmode, speed, cue, repeat, trim..., volume, timeslice`) default file = the TD sample mp3; fed to `audiospectrumCHOP` (`fftsize` 64..16384, `frequencylog`, `highfreqboost`, `outputmenu` = matchtofrequency / setmanually, `outlength`)
  it cooked (probed `numChans` 2, `numSamples` 22050 at 44.1 kHz). `beatCHOP` (`period, multiples, bpm, ramp, pulse, sine, count, bar, beat, sixteenths, updateglobal`) exists. Also present: `audiodeviceinCHOP, audiodeviceoutCHOP, audiobandeqCHOP, audiofilterCHOP, audiodynamicsCHOP, audiostreamin/outCHOP, analyzeCHOP, envelopeCHOP, lagCHOP, filterCHOP, triggerCHOP, midiinCHOP, oscinCHOP, timerCHOP`.
  `audioenvelopeCHOP` is listed in `td` but `create()` raised "Invalid number or type of arguments" (probably not creatable here; see Bugs). I did **not** create `audiodeviceinCHOP` (macOS microphone permission prompt) - unverified.
  Existing house component: `JZBA_AudioAnalysis` (td-port/LEARNINGS.md, 13 Oct; Script CHOP ~2x slower under Rosetta; the user later chose external 0-1 values over TD mic analysis, 12 Oct). Beat/onset: no dedicated "onset" op seen in the CHOP list (search of names for audio/beat/spectrum/analyze/envelope/trigger/lag); build as Audio Spectrum -> Analyze/Envelope -> Trigger CHOP (unverified).
- **Text TOP (probed):** pars include `font` (203 menu entries, includes `Geeza Pro`, `Noto Nastaliq Urdu`, `DecoType Naskh`, `Baghdad`, `Arial Hebrew`), `fontfile`, `typeface`, `bold/italic`, `readingdirection` (lefttoright/righttoleft),
  `breaklang` (english, german, spanish, french, japanese, korean, russian, chinese - no Urdu entry), `wordwrap`, `alignx/aligny`, `fontsizex` + unit (pixels/fract/relfract/points), `fontautosize` (nofit/alwaysfit/fitiffat), `trackingx/y`, `linespacing`, `strokewidth`, `dispmethod`, `antialias`, `fontcolor*`, `bgcolor*`, `bgalpha`.
- **Urdu shaping: works** (probed, evidence `refs/A_td_howto/urdu_*.png`). My own test string rendered with contextual joined forms (not isolated letters) in Noto Nastaliq Urdu and in Geeza Pro, with the first word at the right (right-to-left word order) in both Reading Direction settings.
  Judged by eye on my own text, not by an Urdu reader: **the client/user must check real names**. Nastaliq's tall glyphs overflow a short frame (set `fontautosize` or leave vertical room). Custom fonts: `fontfile` par (td-port/hyperframes have OFL Urdu fonts - not tested). The brand rule applies: names and words stay whole; calligraphy only from the client's file (use an image/SVG via Movie File In / SVG TOP, not the Text TOP).
  No docs page states Urdu support; this rests on the live probe only. TouchDesigner text uses macOS system text layout (unverified: not documented in the pages I read).

## 6. Recipes (op chains in 2025.31550; "verified" = built and cooked in the probe COMP, error-free, checked with `td_screenshot` or pixel readout)
Common: ops cook only if viewed, so an offscreen network needs a pump or a viewer; `td_errors` force-cooks (T-02). `td_screenshot` flattens alpha **over white** (a half-transparent black trail shows as grey) - check alpha with `numpyArray()`.
1. **Feedback loop - verified (trails confirmed by pixel readout; render looked grey in the screenshot because of the white flattening).**
   `Constant(black, alpha 1) -> Feedback TOP [par top = the loop-end Null] -> Transform TOP (scale/rotate small) -> Level TOP (opacity ~0.97) -> Composite TOP -> Null TOP`; the Composite's second input is the new element (Circle TOP, `centerx/centery` expressions of `absTime.seconds`).
   Feedback TOP pars: `top, reset, resetpulse` plus resolution/format. Composite `operand` (add, over, ...): input 0 is on top for `over`. Pump: an Execute DAT cooking the Null each frame. Mind: transform in the loop accumulates; reset with `resetpulse`. td-port/LEARNINGS.md has the Feedback/Cache rules.
2. **GLSL TOP generator - verified.** `GLSL TOP` (res custom, format rgba8/32) + auto DAT `<name>_pixel`: `out vec4 fragColor; fragColor = TDOutputSwizzle(...)`; `vUV.st`, `uTDOutputInfo.res` (z/w = width/height). Time uniform: `vec0name='uTime'`, `vec0valuex` expression `absTime.seconds`. No `#version` line. `glslversion` par for 430-460. Concentric-ring test rendered correctly (`refs/A_td_howto/glsl_rings.png`).
3. **Instancing - verified (POP-driven).** `Grid POP (surftype points, cols/rows/size) -> Geometry COMP`: in the Geometry COMP `instancing = on`, `instanceop = /path/grid` (**Default Instance OP; not "instancepop", which is Pivot OP and broke my first try**), `instancecountmode = oplength`, `instancetx/ty/tz = P(0)/P(1)/P(2)` (menus; also `N(0..2)`, `Tex(0..2)`),
   scale/rotate from further attributes. Geometry shown by the default `torus1` POP inside. Camera COMP + Render TOP (`camera`, `geometry`, `antialias aa1..aa32`, `format`). Rendered a grid of tori (`pop_instancing.png`). The 2025 Geometry COMP doc page does not mention POP instancing (WebFetch of [Geometry COMP](https://docs.derivative.ca/Geometry_COMP)); the pars were found live.
4. **Noise / displacement - not built; ops confirmed present.** `noiseTOP` (par `format`, `tz` has `absTime.seconds` default expression, Noise TOP "period"/4D) -> `displaceTOP`; or `noisePOP` (type, noisesize, period, harmon, gain, amplitude `amp0`, offsets `tx..`, curl/gradient outputs, `outputattrscope`) onto a `gridPOP` for point displacement.
   Verified: Noise TOP at 9984x3840 float16 (section 3). Displace chain: **unverified**.
5. **Particles via POPs - verified (minimal).** `Point Generator POP (shape sphere, numpoints, radius*) -> Particle POP (maxparticles 20000, birthrate, life, initvelocityx/y/z, damping, play)`; inside `Geometry COMP` place a **Select POP** (`pop` = the particle POP) with Display + Render flags on and delete the default torus;
   `Point Sprite MAT (pointsize, color)` on the Geometry COMP (`material`), Camera COMP, Render TOP (set `bgcolora=1` to see). Result: pink sprites in a sphere (`pop_particles.png`; point count grew 50 -> 150 only because the unviewed TOP cooked rarely: pump it).
   Doc ([Particle POP](https://docs.derivative.ca/Particle_POP)) wants forces added downstream, ending in a **Null POP** that `targetpop` points to (feedback loop); my test did not do this, so a force chain (`forceradialPOP`, `noisePOP`, `fieldPOP`, `Null POP` + `targetpop`) is **unverified**.
   Another path from docs/class list (unverified): `poptoTOP` converts POP attributes to textures. The classic particlesGPU palette component was not checked. `pointMAT` is listed in `td` but `create()` raised an argument error (see Bugs); `pointspriteMAT`, `constantMAT`, `phongMAT`, `pbrMAT`, `glslMAT`, `lineMAT`, `wireframeMAT` are creatable by name list.
6. **Text TOP layouts - verified for Urdu (section 5).** `Text TOP (text/dat, font, fontsizex+unit pixels, alignx/aligny, bgalpha=1 for a bg) [-> Transform/Composite]`; for tall scripts (Nastaliq) allow vertical room. Non-text layout: `layoutTOP`, `tileTOP`, `fitTOP` exist (not probed).
7. **Compositing to a multi-face canvas - verified (crops).** `Canvas (Noise/GLSL/Render, custom res 7488x2880, rgba8fixed)` -> nine `Crop TOP`s with `cropleftunit/croprightunit/cropbottomunit/croptopunit = pixels`, `cropleft = x0`, `cropright = x0 + w` (this build's Crop "right" is the right edge in pixels, not a margin: probed result sizes 1152/576/576/576/1728/576/576/576/1152 x 2880),
   `cropbottom = 0, croptop = 2880`. For separately rendered faces: Constant/Render per face (face width x 2880) -> `Layout TOP` or `Composite TOP` with `Transform TOP` offsets (unverified). To preview 3D mock vs final, see `prismfest26-show/production/mockup/README.md`.
   The final clip stays one 7488x2880 image; Arena's own slicing is the pipeline's business (SYSTEM.md).

## Bugs hit / surprises (for the lead to log in LEARNINGS)
- **B1 - `td_screenshot` of an RGBA TOP flattens alpha over white.** Black with alpha 0.17 looked uniform grey (#2a2a2a); pixel readout showed the true values. Rule: use `numpyArray()` for alpha work.
- **B2 - `numpyArray()` returned all zeros right after `cook(force=True)` in the same exec for a Circle TOP that was visibly rendering** (screenshot showed the circle a call later). Cause not found (unverified: readback timing). Noise/Constant read back fine in the same pattern. Rule: re-read in a later call / verify with a screenshot.
- **B3 - listed-but-uncreatable classes:** `td.pointMAT` and `td.audioenvelopeCHOP` appear in `dir(td)` but `parent.create(cls, name)` raised `tdError: Invalid number or type of arguments`. Likely legacy/Windows classes (unverified). Rule: do not assume `dir(td)` = usable ops.
- **B4 - The bridge restarted mid-session** (status showed a new bridge pid 3157 -> 29290, `since` 13:27:06; one `td_screenshot` failed with "not connected"; TD itself kept running, pid 12186, no new crash file). Not a TD fault; someone (lead/another agent) restarted the bridge. Retry after `td_status` worked.
- **B5 - Docs lag the build:** the Geometry COMP doc page does not describe POP instancing; the 2025.31550 release-notes URL variants (`/Release_Notes/2025.31550`) 404, only `/Release_Notes` works (long page, newest first).
- **B6 - td-port/LEARNINGS.md assumes GL 4.1 as TD's macOS GLSL level ("Mac's own GL 4.1 driver, same GL version as TD on macOS").** Probed `__VERSION__` = 430/460 and the 2022 release notes say OpenGL was removed (Vulkan+MoltenVK). The offline checker is stricter than TD (safe direction), but its premise is wrong. A shader that fails the 4.1 check may still compile in TD (unverified for specific cases).
- Observation: `td_exec(frames=N)` returned results ~N frames later; forced cooks of unviewed ops (feedback, particles, Movie File Out) need a per-frame pump, as in T-02.
- No crash, no hang occurred; the probe COMP and all children were destroyed (the first cleanup call raised "Invalid OP object" because deleting a GLSL TOP also removes its auto DATs; a second pass finished it). `/project1` ends with its original 6 children.

## Open questions for the lead
1. Is the Pro licence on `TouchDesigner 2.app` expected to stay (Rosetta) for the whole PF26 build, or should the native `TouchDesigner.app` (2025.32820) get a licence too? I did not run the native app, so its licence is unverified.
2. Should I (or another agent) test the unprobed render risks before any PF26 build: ProRes 422 HQ and Hap Q at **9984x3840**, ProRes 4444 with alpha, a 600-frame offline record with real content (timing per frame), a seamless 10 s loop, and Arena playback of TD's Hap Q (Arena step needs the user's go-ahead)?
3. Does the pipeline want ProRes 422 HQ (matching the current `--master` ProRes wall) from TD, then DXV3 as usual? TD itself cannot write DXV.
4. Urdu: should real names/lines be shaped in TD's Text TOP at all, or always come from the client's calligraphy file (names stay whole; the Text TOP result is only reviewed by eye by me)?
5. Audio: stay with the "external 0-1 values" decision (td-port, 12 Oct) or test Audio Device In / loopback in TD (microphone permission prompt on macOS)?
6. Fix `td-port/LEARNINGS.md` and its shader checker premise (GL 4.1 vs the actual GLSL 430-460 / Vulkan), or leave as the conservative bound?
7. Which faces are 3840/2880 high in the R02 package, and are the faces contiguous (no gaps)? I assumed all nine share the canvas height and sit side by side.
