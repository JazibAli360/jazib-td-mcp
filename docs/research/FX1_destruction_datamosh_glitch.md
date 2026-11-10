# FX1 - Destruction, datamosh and glitch effects for TouchDesigner 2025.31550 on this Mac (26 Oct 2026)

Offline research. TD was not touched (no `jazib-td` calls). Nothing here is measured in TD: every cook time is an
ESTIMATE for 1080x1920 on the M1 Max under Rosetta/MoltenVK and must be replaced by `td_perf` numbers at build time.
Three things were run on this Mac outside TD (section 3, ffmpeg): the I-frame drop recipe, the `noise` bitstream
filter and the `codecview`/`mestimate` filters. Everything else is from docs, community pages and my own maths.

Scope of the user's request (26 Oct): "destruction type effects, datamoshing and etc - research first all of what we can
add". Companion files (same wave) cover other territories; this one is DESTRUCTION + DATAMOSH + GLITCH.

## 0. Read this first

- **Host limits that shape every recipe** (LEARNINGS): single-pass GLSL or Compute-mode GLSL only (T-46/T-47);
  `opticalflowTOP` unsupported (T-18); 60 fps, ~3 ms per COMP; vertical 1080x1920; no Voronoi/Delaunay/fracture op in the
  31550 op dumps (`docs/research/ops/ops_{TOP,SOP,POP}_2025.31550.json`, 97 POP classes; verify with a create probe
  before relying on that), so Voronoi = hash-grid cells or jump flooding in compute GLSL.
- **What 31550 does give us** (names from the dump): `cacheTOP` (cachesize, step, outputindex, interp),
  `timemachineTOP` (per-pixel time displacement from a map = native slit-scan), `texture3dTOP` (ring of frames, cachesize),
  `glslTOP` with `type`/`depth` (2D, array, 3D output), `feedbackTOP`, `displaceTOP`, `remapTOP`, `lookupTOP`,
  `thresholdTOP`, `edgeTOP`, `blobtrackTOP`, `cplusplusTOP`, `scriptTOP`; POPs `particlePOP`, `toptoPOP`, `glslPOP`,
  `sortPOP`, `quantizePOP`, `feedbackPOP`, `facetPOP`, `extrudePOP`; SOPs `facetSOP`, `booleanSOP`, `latticeSOP`,
  `deformSOP`, `spriteSOP`, `alembicSOP`, `fileinSOP`.
- **Already built or ported - do not re-propose, extend:** see section 1.
- **Safety is part of every effect in this file** (`concert-visuals-research/README.md` s4, `AX_strobber.md`, `J_...`
  s3: more than 3 flashes per second over more than 25 % of the screen is out; datamosh, echo and static are the worst
  offenders). Each COMP gets a `Safety` knob group: max luminance step per frame, 3 Hz flash cap on the trigger path,
  noise/static cap, `Panic` pulse = instant passthrough. Build one shared helper (`DX_safety`, section 14) and wire it into
  every COMP's `out1`.
- **Names/words/logos stay intact** (memory "Names and words stay intact"; Myles `pixelSorting` note says the same):
  destruction effects work on footage and backgrounds. Every COMP takes an optional `Protect` mask input; the PRISM logo
  and artist names are composited AFTER the effect chain, not through it, unless the user asks for a damaged name.
- **Colourful PRISM logos only** and Urdu text is never sorted/cracked (BJ, memory) - same reason.

## 1. What already exists (so we extend, not duplicate)

| Where | Existing | How this file extends it |
|---|---|---|
| `td-port/glitch` (JZBL_Glitch, built) | Radial/horizontal/RGB-tear chromatic split, fine scanline tears, wobble, grain, Steady/Trigger/Rate, no coarse tile jumps (user feedback 12 Oct removed them) | block glitch (DG-07) is a separate COMP so the glitch COMP stays the user-approved fine look; tear modes feed DG-11 |
| `td-port/rgb_split` (built .tox) | channel shift | DG-10 extra modes |
| `td-port/shatter` (JZBD_Shatter, offline gate only, TD not run) | **per-pixel procedural Voronoi shards** (shift/rotate/scale about seed, mirrored edges, crack colour, settles back); no physics, no history | DG-15 adds real shards with physics and a drop-away; this one stays the cheap single-pass version |
| `td-port/slit_scan` (JZBT_SlitScan, ported) | rows/columns/radial/angle/luma/diagonal maps over a frame ring (Texture 3D written by a frame_exec script) | DG-13 uses native `timemachineTOP` / `texture3dTOP` instead of the script ring, adds flow/audio/mask-driven maps |
| `td-port/stutter`, `echo`, `motion_trail` | beat-repeat, echo/trails | DG-12 shuffles per BLOCK in time (new); trails exist in `FX_motion_trail` |
| `td-port/pixel_fx` | LED-fixture generators (rainbow, fire, sparkle...) | unrelated (generator) |
| `td-port` other: ascii, halftone, kaleido, ripple, shake, shockwave, hit, hit_slice, slice_*, elastic_lens, anamorphic_collapse, video_relief, ink_flow, flow_fx, depth_fx, person_key | stage/hit effects | reuse as triggers/masks (hit -> trigger input) |
| `td-port/INVENTORY.md` "Pending port" (StageLab FFGL exists, TD port missing) | **Datamosh, PixelSort, CRT, Reducto, VHS(Lofi_VHS), GlitchMix, Displace, Feedback, Neon, Contour, FaceMosaic** | this file is the TD design for those; StageLab FFGL specs in `stagelab/docs/plugin-stack.md` s4 (`JZB_Lofi_Sort` = exact GPU odd-even by Luma/Hue/Sat, Instant or Melt; `JZB_Lofi_VHS` = YIQ path, chroma bleed, tracking band, head switch, interlace; `JZB_Lofi_CRT`; `JZB_Lofi_Reducto`; `JZB_Warp_Displce`) are the vocabulary to match so Arena and TD presets line up |
| `docs/builds/` lab | strobe, motion_trail, palette_map, particles, fluid2d, cloth, splats, cloud_morph, PX point-fx (in progress), reaction-diffusion + physarum (in progress), depth_cam, face_track, person mask (in progress) | masks/flow/depth are inputs; particles (compute engine) and PX modules are the dust back-end for DG-17 |
| `docs/research/Y_td_toxes_myles.md` | MIT `pixelSorting_MYLES` = NOT a sort: Difference + Displace feedback drag (elekktronaut tutorial); `dataMosh_MYLES` = UV-field feedback nudged by self-referential noise + remap (Paketa12 tutorial), needs motion video, 32F + 10 Resolution TOPs | baseline to beat; both are "smear" looks, kept as DG-06 modes |
| `docs/research/J_interactive_camera_effects.md` J13 | datamosh "not ranked (flash risk)": Rammstein 2019 used Notch Motion Datamosh on IMAG | here ranked with a limiter |
| `docs/research/BR_rubenfro_pointcloud_fx.md` | 8 mask/dissolve/lifetime PX modules, edge fray/dissolve look | DG-17/DG-18 are the 2D screen companions and share the mask vocabulary |
| TD Python has OpenCV 4.11 + numpy (T-19) | CPU only, x86_64 | optional CPU flow estimator (DG-01 Estimator = cv2) |
| Apple Vision helper `helpers/vision_bridge/` (arm64) | person mask, face | `VNGenerateOpticalFlowRequest` is an Apple API for dense flow; a new helper "kind" could serve it. UNVERIFIED here (speed, Rosetta handoff) |

## 2. Priority summary (1 = build first for live; S/M/L = effort; perf = estimate)

| ID | Effect | Pri | Size | est. cook @1080x1920 |
|---|---|---|---|---|
| DG-01 | **Datamosh engine** (P-frame bloom, 5 estimators) | 1 | L | 1.0-2.5 ms |
| DG-02 | **Mosh transition** (A->B, B's motion drags A) | 1 | M (on DG-01) | + 0.3 ms |
| DG-03 | Offline datamosh / codec corruption tool (`tools/mosh.py`) | 1 | S | offline |
| DG-04 | **Pixel sort** (segmented bitonic, true sort) | 1 | L | 1.5-3 ms |
| DG-05 | Smear sort / pixel stretch (cheap sort look + mask stretch) | 1 | S | 0.4-1.0 ms |
| DG-06 | Displace-feedback "mosh smear" (Myles/elekktronaut recipe) | 3 | S | 0.5 ms |
| DG-07 | **Block glitch / macroblock corruption** | 1 | M | 0.5-1.0 ms |
| DG-08 | JPEG / DCT compression crush + generation loss | 2 | M | 0.8-1.5 ms |
| DG-09 | Bit-crush, bit-plane, bit-flip, RGB565/1-bit | 2 | S | 0.2 ms |
| DG-10 | RGB / chromatic split extras (prism, spectral, flow, luma) | 2 | S | 0.3-0.8 ms |
| DG-11 | Scanline tearing, V-hold roll, sync loss | 2 | S | 0.3 ms |
| DG-12 | Frame shuffle / per-block temporal offset | 2 | M | 0.5-1.0 ms + VRAM |
| DG-13 | Slit-scan / time displacement (native, driven) | 2 | S | 0.5 ms + VRAM |
| DG-14 | Melt / drip / liquid sag | 1 | M | 0.4-0.8 ms |
| DG-15 | **Shatter with physics** (shards fall, floor, settle) | 1 | L | 1-2 ms |
| DG-16 | Glass crack / broken LCD / dead-pixel failure | 2 | M | 0.4-0.8 ms |
| DG-17 | **Disintegrate** (Thanos / crumble to dust) | 1 | L | 1.5-3 ms |
| DG-18 | **Burn / erode / dissolve edge** (+ fire-spread CA) | 1 | M | 0.4-1.0 ms |
| DG-19 | Explode / implode (2D radial + 3D polygon explode) | 2 | M | 0.5-1.5 ms |
| DG-20 | Mosaic decay / quadtree pixelation | 2 | S | 0.3 ms |
| DG-21 | Feedback destruction (generation loss, burn-in) | 2 | M | 0.5-1.0 ms |
| DG-22 | Wavefold / solarize / UV fold | 3 | S | 0.2 ms |
| DG-23 | **VHS / CRT breakage** (YIQ tape + CRT) | 1 | M | 0.8-1.5 ms |
| DG-24 | Signal loss, no-signal, interlace combing, CRT power-off | 2 | S | 0.3 ms |
| DG-25 | Data-bending (byte-stream filters in 1D) | 3 | M | 0.5 ms |
| DG-26 | 3D / geometry destruction (Blender fracture, poly explode, vertex rot) | 2 | L | scene dependent |
| DG-27 | Slash cuts / sliced image parting | 3 | S | 0.3 ms |
| DG-28 | LED module failure / panel dropout look | 3 | S | 0.1 ms |
| DG-29 | `DX_safety` limiter + `DX_masks` + `DX_triggers` (shared kit) | 1 | M | 0.2 ms |

Priority logic: 1 = reads at stage distance, survives LED pitch, has an audio hook, fits PRISMFEST'26 acts (energy
moments, drops, transitions). 3 = studio/close-up look or already covered by an existing COMP.

## 3. Datamosh, the real thing and how to emulate it

### 3.1 How a real datamosh works (what we must imitate)

A codec stores an I-frame (full picture) then P-frames: per 16x16 macroblock (8x8 sub-blocks) a motion vector (MV)
pointing into the previous DECODED frame plus a small residual. Datamosh = delete the I-frame at a cut (or repeat one
P-frame many times). The decoder keeps the OLD picture as reference and applies the NEW clip's motion on it: old
pixels flow like the new action ("bloom" when a P-frame's MVs are repeated; "melt" when residual is lost). Visual
signature: block-sized pixel drag, colours of clip A moving with clip B's motion, edges of B painted as residual
ghosts, sudden snaps back at the next I-frame.

What TD cannot do: read MVs from the codec (Movie File In decodes to pixels via the system decoder; no side data).
What we can do: (1) estimate the same MVs from the pictures, per block, in compute GLSL, (2) bake real MVs offline
for stored clips (s3.3), (3) corrupt the bitstream offline (s3.3 / DG-03).

### 3.2 DG-01 Datamosh engine (`FX_datamosh`), priority 1, size L

**Look.** Refs: Rammstein 2019 IMAG "Motion Datamosh" (Notch; J13/J), Buck x Apple Music Korea Memoji "moshing"
sandbox ([buck.co/sandbox/moshing](https://buck.co/sandbox/moshing): optical flow of the source displaces pixels, output is
fed back so the displacement amplifies the flow it causes, colour is injected continuously, blockiness added for angular
distortion; custom openFrameworks, no licence stated - technique read only), Codrops Sep 2026 "Breaking the Frame:
real-time datamosh with Three.js" (a fragment shader acts as the decoder, refresh is suppressed while a gesture is
active so old pixels keep displacing; page returned 403 to fetch, only the search snippet was read),
Interactive & Immersive HQ "Datamoshing in TouchDesigner" parts 1-3 ([part 2](https://interactiveimmersive.io/blog/touchdesigner-resources/datamoshing-in-touchdesigner-part-2/),
[part 3](https://interactiveimmersive.io/blog/glsl/datamoshing-in-touchdesigner-part-3/): built on the Optical Flow TOP + GLSL adding flow vectors
to the source, Feedback TOP recycling, Threshold par so tiny changes do not count; credits Ompu Co's blog; pages
truncated on fetch, so node values UNVERIFIED), Myles `dataMosh` (Y).

**Technique (per frame, two compute passes, state in rgba16float):**

1. **Estimate motion** `mv(block)` in pixels between `prevSrc` and `cur` (estimators below).
2. **Update the decoded state** `S` (feedback of its own output):
   ```
   // pass B, one thread per output pixel p (px coords)
   vec2 m   = fetchMV(blockOf(p)) * Gain;            // px, backward warp
   m        = mag(m) < MinMag ? vec2(0) : m;          // Threshold: tiny noise is not motion
   vec4 ref = texture(S_prev, (p - m + 0.5) / res);   // old picture dragged along the new motion
   vec4 res = cur(p) - prevSrc(p - m);                // "residual": new edges painted on old pixels
   vec4 out = ref + Residual * res;                   // Residual 0 = pure drag (melt), 1 = ghosted edges
   out      = mix(out, cur(p), refreshMask(p));       // I-frame / intra-refresh (Hold = 0 everywhere)
   S        = clamp(out, 0., Limit);                  // 16F drift guard
   ```
   `refreshMask` = global Refresh (the "I-frame": a pulse or trigger sets it to 1 for one frame) + per-block random
   intra refresh (probability `Refreshrate`, noise hash per block and per `Refreshevery` frames) + optional
   `Protect` mask (always refreshed = a person or logo stays clean while the background moshes).
3. **Bloom mode.** To get the "P-frame repeat" bloom, freeze the MV field (`HoldMV` on, or a trigger latches the
   current field) and apply it every frame with the multiplier `Bloomgain` > 1 (the same vectors compound).
4. **Block look.** MV is quantised to the macroblock grid (`Blocksize` 8/16/32/64) with nearest sampling; sub-pel off =
   hard blocks (the codec look), on = bilinear (fluid look, Buck). `Blockwarp` mixes the two.
5. **Output** = `S` (optionally `mix(cur, S, Dry/wet)`), colour stays in the state texture so mosh survives cuts.

**Estimators (menu `Estimator`) - all compute GLSL, T-46 safe:**

| Estimator | How | Quality | est. cost |
|---|---|---|---|
| `Diffgrad` | MV ~ -(grad I) * (I_cur - I_prev) / (|grad I|^2 + eps), single 5x5 window. One pass. Fast, only valid for small motion | rough, good for stylised | 0.3 ms |
| `LK pyramid` | Lucas-Kanade on a 3-level pyramid (1/4, 1/2, 1; Mip or 3 downsample passes), 7x7 window structure tensor per pixel, warp-and-refine 2 iterations per level | smooth fluid flow | 1-2 ms |
| `Block match` | per block (8x8 at half res or 16x16 at full): diamond/three-step search +/- R px using SAD on luma, coarse-to-fine: level 1/4 +/- 4 full search (81 candidates x 64 px) then refine at full res +/- 2 (25 x 256). Use a workgroup per block, 64 threads cooperating over candidates, shared-memory reduction. 1080x1920 = 8160 blocks at 16x16 | **the real codec look** (hard blocks, bad vectors in flat areas = the authentic mistakes) | 1-2.5 ms |
| `Helper flow` | Apple `VNGenerateOpticalFlowRequest` in an arm64 helper, texture delivered like the person mask (UNVERIFIED speed, 2-3 frames latency fine for mosh) | best quality | helper-bound |
| `cv2 DIS` | OpenCV DIS (ultrafast preset) at 240x135 in a worker thread, uploaded as a small RG float texture each N frames; x86_64 under Rosetta, no AVX, so speed UNVERIFIED | good | 0 ms on GPU, CPU thread |
| `Stored MV` | sidecar movie of baked flow (s3.3) played with the clip, frame-locked | codec-true | 0.1 ms |

Full-search cost sanity: full 16x16 +/-16 search = 1089 candidates x 256 px x 8160 blocks = 2.3 G SAD taps, far too
heavy; the pyramid + diamond search is 10-60 M taps. That is the reason for the pyramid, not a micro-optimisation.

**TD build.** `src` -> `work` (Quality full/half) -> `prev` (Cache TOP size 2, index -1, as in `motion_trail`) -> compute
pass `mv` (rg16f, block-resolution output via custom resolution, `texelFetch` only) -> compute pass `update` (inputs
cur, prev, mv, S_fb) -> Feedback TOP of `update` (reset source: `cur`) -> `out1`. Estimator chosen by `Estimator`
Switch. Stateful: a `Clear/IFrame` pulse and `Resetonloop` for stored clips (as `FX_motion_trail`).

**Not possible here, best substitute.** Real codec MVs from the live stream (no side data): block-match emulation
above, or the stored-MV sidecar for pre-recorded media. Vector accuracy against a true encoder is not claimed.

**Key parameters.** Estimator (menu), Blocksize (8/16/32/64), Gain (0-4, default 1), Bloomgain (0-8), Minmag px
(0-8, default 0.5), Residual (0-1.5, default 0.6), Refresh (pulse), Refreshrate (0-1, default 0.02), Refreshevery
frames (1-120), Hold (toggle: never refresh), HoldMV (toggle), Subpel (toggle), Decay (0-0.2: leak of S toward cur per
frame, so it always recovers), Limit (1-2), Range px (4-64), Quality (full/half/quarter for the estimator), Dry/wet,
Protect input, Safety group. Modes: Mosh (drag), Bloom (latched MVs), Melt (Residual 0), Ghost (Residual 1).

**Presets.** `Subtle drag` (Gain 0.6, Residual 0.3, rate 0.04), `IMAG mosh` (Block match 16, Gain 1, Residual 0.6),
`Bloom hit` (HoldMV on trigger, Bloomgain 3, 0.5 s then refresh), `Liquid` (LK, Subpel on, Residual 0), `Block
tears` (Block 32, Diffgrad), `Person stays` (Protect = person mask).

**Inputs.** TOP in (live/clip), optional second TOP `B` (for DG-02), Protect mask, trigger Nulls (Refresh, HoldMV),
audio CHOP (`level` -> Gain, `kick` -> Refresh), person-mask/depth as Protect.

**Perf.** Block match 2.5 ms worst, LK ~2 ms, Diffgrad ~0.7 ms with `update`. Default Quality half estimator. Plan for
two 16F full-res textures + MV texture (~16 MB). Flash risk: refresh snaps are full-frame changes; limiter caps the step.

**Preview.** `webcam_ref_5s.mp4` has real motion; stored-clip test: static source = out equals src exactly (Diffgrad
mv = 0); vertical pan = uniform drag; Refresh pulse = exact `cur` for one frame (check by numpy).

### 3.3 DG-03 Offline datamosh and codec corruption (media prep tool), priority 1, size S

Use when the mosh must be codec-true (clips for Arena, stored loops, transitions) - "tools/mosh.py" as one small script
wrapping ffmpeg; Python 3 stdlib only (PIL 12.3 is present on this Mac if stills are needed).

**Verified here (ffmpeg on this Mac, `/opt/homebrew/bin/ffmpeg`, webcam_ref_5s.mp4 -> 480 px, 3 s):**
```
ffmpeg -i in.mp4 -vf scale=480:-2 -c:v mpeg4 -q:v 4 -g 45 -bf 0 -an b.avi          # I frames 2, P 88
ffmpeg -i b.avi -c copy -bsf:v 'noise=drop=gt(key\,0)*gt(n\,0)' m.avi               # I frames 1, P 88 (drops 2nd+ keyframes)
ffmpeg -i m.avi -c:v mpeg4 -q:v 3 out.mp4                                            # 89 frames decode fine
```
Result: the I-frame count went 2 -> 1 and the file still decodes (89 of 90 frames). `-bsf noise` has `drop`, `dropamount`,
`amount` options in this build. Rules: MPEG-4 Part 2 in AVI with `-g` big and `-bf 0` (no B-frames) is the easy,
robust container for this; H.264 streams re-sync at SPS/IDR and mosh badly. Final delivery for Arena: re-encode the
result to Hap or ProRes (no further datamosh possible after that).

**Recipes in the tool:**
1. **Classic I-frame drop** (above): `--cuts t1,t2` makes keyframes at the cut points (`-force_key_frames`), drops all
   except the first. Result: clip B's motion drags clip A at every cut.
2. **P-frame bloom** (frame repeat): duplicate one P-frame packet N times (`noise=` has no dup; use an AVI chunk
   parser: split on `00dc` chunks, the MPEG-4 VOP header `00 00 01 B6` carries the coding type in the next 2 bits,
   `00` = I, `01` = P; repeat the chosen chunk N times). Python stdlib, ~60 lines. Untested here.
3. **Bitstream noise** (`-bsf:v noise=amount=<expr>`): random byte flips; MPEG-4 error concealment produces smears and
   macroblock confetti that no shader reproduces exactly. Always check the clip decodes (no black frames).
4. **ffglitch** (ramiropolla; FFmpeg-derived bitstream editor, scripts in JS; tutorial scripts in
   [ffglitch-scripts](https://cdn.jsdelivr.net/gh/ramiropolla/ffglitch-scripts@main/tutorial/readme.md): `mv_average` blends vectors over previous frames, MV
   sink/radial/zero scripts; pipe through `ffgac` to re-encode as MPEG-4 first; FFmpeg licence terms apply - note only).
   Not installed; install is the user's go-ahead.
5. **Datamosher Pro** ([Akascape/Datamosher-Pro](https://github.com/Akascape/Datamosher-Pro), GUI wrapper around ffglitch with Classic I-frame removal, FFGlitch modes;
   licence UNVERIFIED) and tomato.py (AVI-based, mentioned in community, not confirmed in this search). Not installed.
6. **Alternative manual route**: Avidemux, delete all I-frames except the first, set x264 GOP large and B-frames off
   first ([FLOSS Manuals / VideoHelp forum notes](https://forum.videohelp.com/threads/404025-Removing-I-frames-programmatically-%28automatic-workflow%29)); then `ffmpeg concat` with stream copy.
7. **Baked motion vectors for DG-01 `Stored MV`**: `ffmpeg -flags2 +export_mvs -i in.avi -vf codecview=mv=pf ...` works here
   (draws arrows; verified). To get NUMBERS, read the frame side data (PyAV is NOT installed; `ffprobe -show_frames
   -flags2 +export_mvs` side data or `mestimate` filter output, untested) and rasterise per-block (dx, dy) into a
   two-channel movie (ProRes 4444/EXR) with numpy. ffmpeg also has `mestimate` (generate motion vectors) and `minterpolate`
   (motion-compensated frame interpolation) if a codec-free MV source is wanted.

### 3.4 DG-02 Mosh transition (`FX_moshcut`), priority 1, size M (on top of DG-01)

A->B transition where A's last frame is the reference and B's motion drags it before B refreshes in blocks (the
well-known music-video datamosh transition). Inputs `A`, `B`; `Progress` 0-1 (or a trigger + `Duration` in beats):
estimator runs on B only; `S` starts as A; refresh probability rises with Progress (block order: noise, top-down,
radial from a point, or luma); end = exact B. Modes: Hard (blocks), Soft (Subpel + LK), Bloom (latched MV). Hooks:
`Go` pulse, `Beats`, audio onset. Pre-sets: `Drop cut`, `Slow melt`, `Radial refresh`. ~0.3 ms on top of DG-01.
Live value: scene changes on drops without a dissolve.

## 4. Sorting, smearing, stretching

### DG-04 Pixel sort (`FX_pixelsort`), priority 1, size L

**Look.** Kim Asendorf's pixel sorting: runs ("intervals") of pixels on each row/column are sorted by brightness, hue
or saturation where a threshold mask says "sort here" - streaks of colour bleeding out of bright shapes. Original
Processing code with white/black/bright/dark modes and a vertical-then-horizontal pass (see the pixelsort pip package
notes: lower 0.25, upper 0.8 thresholds). Boris FX Sapphire "PixelSort" is the commercial reference. StageLab already
has the exact GPU odd-even version (`JZB_Lofi_Sort`, Luma/Hue/Saturation, 90 degree angles, Instant or Melt): match
its names. Alan Zucconi's GPU-sorting series ([part 1](https://www.alanzucconi.com/2017/12/13/gpu-sorting-1/)) explains the key limit: a pixel shader can
write only its own pixel, so a sort needs odd-even or bitonic passes. Myles `pixelSorting` is NOT a sort (Y s4).

**Technique (Compute GLSL, shared memory):**
- Rotate the problem: always sort along X in a work frame; Angle 0/90/180/270 handled by transposed fetch/store; any
  other angle by sampling the source along a rotated grid and scattering back (cost ~2x).
- One workgroup = one line chunk of `Chunk` pixels (local_size_x 256/512/1024; TD auto-dispatches ceil(w/x), h). Load
  `key = f(rgb)` (luma / hue / sat / R / G / B / custom) and `mask = threshold(Lower, Upper)` into shared memory.
- **Segmented bitonic sort**: interval id = cumulative sum of mask edges (prefix scan in shared memory, log2 steps); sort
  the composite key `(intervalId << 24) | quantised key` with the bitonic network (log2(N)(log2(N)+1)/2 steps = 45 steps for
  512 elements, ~0.0 barrier cost each) - all intervals of the chunk sort in one go, masked-out pixels keep identity keys.
  Direction Asc/Desc; `Reverse` per interval by hash.
- Chunk seams: intervals cut at chunk edges are visible. Fix with `Chunkjitter` (the chunk grid origin moves each frame or
  per row by a hash) and a long chunk (1024 covers the 1080 px width in two groups; sorting along the 1920 axis uses
  two or four). Honest cost: a hard max interval length = Chunk.
- **Melt mode**: instead of the full sort, run `Steps` odd-even compare-swaps per frame on the state texture S (stateful,
  one compute pass per step or 4 unrolled steps in shared memory), mask recomputed from the live source so it keeps
  flowing; output approaches the full sort over N frames (the StageLab "Melt").
- Masks: luma/hue threshold, soft edges, `Maskin` TOP (person mask => sort only the background or only the person),
  edge-based interval breaks (Sobel > thr breaks an interval), random interval lengths (hash), noise-modulated threshold.

**Key parameters.** Sortby (Luma, Hue, Sat, R, G, B, Luma+Hue), Direction (X, Y, angle deg), Order (Asc/Desc/Random/
Reverse), Lower/Upper threshold (0-1), Mode (Between / Below / Above / Mask / Edge), Chunk (64-1024), Chunkjitter
(0-1), Maxlen (px), Melt steps (0-16), Amount (blend of sorted vs source by distance along interval = "comet" decay),
Gain, Quality (half-res sort + upscale), Protect mask, Seed. Presets: `Asendorf` (V then H, 0.25/0.8), `Comet`
(vertical, bright above), `Melt drip`, `Hue rainbow`, `Person curtain` (mask).

**Inputs.** TOP, mask TOP, audio (Lower/Upper from bass; a kick pulses Amount), triggers.
**Perf.** 512-px bitonic per row: 2M px x ~45 steps ~ 90 M shared-memory ops: 1.5-3 ms est.; Quality half = ~0.8 ms.
Risk: MoltenVK workgroup memory + barrier limits under Rosetta - a 30-minute probe on the scratch TD first (T-83).

### DG-05 Smear sort / pixel stretch (`FX_smear`), priority 1, size S

Cheap, single-pass look-alike and a distinct effect on its own:
- **Smear sort**: `out(p) = max-luma (or min-luma) pixel over the last K pixels along the direction while the interval mask
  holds` (K up to 256 with stride-2 taps; 64 taps typical). Looks like a one-sided sort ("bright pixels drip down").
- **Stretch**: `out = src(clamp(uv, bandStart, bandEnd))` - a line or band repeated along the axis (vertical/horizontal/
  radial), band position animated; `Mask` mode stretches FROM the edge of a mask (person-mask edge streaks, very
  stage-readable) using a distance-to-edge march (up to 128 taps).
- Modes: Smear max, Smear min, Stretch band, Stretch mask-edge, Stretch radial (from a centre), Streak (trails of bright
  points).
Params: Direction, Length px (1-400), Threshold, Softness, Band pos/width, Decay, Wobble (noise on the axis), Protect.
Perf: 0.4-1.0 ms. Inputs: TOP, mask, audio. Priority 1 because it is the cheap, always-safe look.

### DG-06 Displace-feedback smear (the Myles/elekktronaut recipe), priority 3, size S

Feedback + Composite(difference) + Displace + Subtract chain from `Y s4` as-is (S). Wrap as a COMP with Direction,
Amount, Enable, Reset and an Auto-clear on the Safety limiter. Kept for parity with the tutorial look; DG-05 and DG-01
cover better versions. 0.5 ms (Displace TOP + feedback at 16F).

## 5. Block, compression and bit damage

### DG-07 Block glitch / macroblock corruption (`FX_blockglitch`), priority 1, size M

**Look.** Digital-TV / bad-stream breakup: rectangles of the picture that freeze, shift, repeat from the wrong place,
turn the wrong colour, or tile a few pixels (Rammstein/TV-error look). The td-port Glitch removed "coarse tile jumps" at
the user's request, so this is a SEPARATE COMP, off by default in any glitch preset.

**Technique (single pass + history taps).** Grid of `Blocksize` (8/16/32/64 px, or irregular via 2-level quadtree hash);
each cell gets a state from a hash of (cell, `floor(time*Rate)` or the trigger count):
1. **Freeze** - shows the cell from `N` frames ago (Cache TOP tap, N 1-60) or from the last frame the cell was "good"
   (state texture, stateful).
2. **Shift** - sample from a cell offset by a vector (hash; quantised to cell units or px).
3. **Repeat/tile** - a small sub-block (4-8 px) tiled across the cell (the stuck-decoder look).
4. **Colour error** - DC drift: add (dY, dCb, dCr) to the cell in YCbCr; **Chroma-only** variant (the green/magenta
   macroblocks of broken H.264).
5. **Wrong reference** - sample the cell from `Wrongref` frames back plus the current motion (calls DG-01's mv).
6. **Dead** - cell goes black/grey/colour bars.
Probability per mode, `Density` (fraction of cells hit), `Burst` (cells hit in clusters/rows - broken slices run to the
end of a row, as slice loss does), `Holdframes`. All hits are quantised in time (hold 2-8 frames) so it reads as digital,
not noise. Slice-loss mode: a cell and everything right of it on that row repeats the cell before it.
Parameters (ranges): Blocksize 8-128, Density 0-1, Rate Hz 0-30, Modes (checkbox bank + weights), Shiftmax px 0-256,
Freezeframes 1-60, Colourerr 0-1, Seed, Burst 0-1, Quantise time frames 1-12. Presets: `Digital TV loss`,
`Green macroblocks`, `Stuck decoder`, `Slice drop`.
Inputs: TOP; trigger; audio (Density from level); `Protect`. Perf: 0.5-1.0 ms (up to 4 Cache taps). Safety: density cap
0.6 and a limiter on luminance step; DC drift capped.

### DG-08 JPEG / DCT crush and generation loss (`FX_dctcrush`), priority 2, size M

**Look.** 8x8 blocking, ringing, colour banding, 4:2:0 chroma smear; at low quality an 8x8 mosaic of DC values.
**Technique** (maths from ISO 10918 / the Intel IPP and NVIDIA CUDA DCT docs; no free real-time GLSL JPEG shader found -
a paid Unreal plugin "Realtime JPEG Compression Shader (TRUE I/DCT)" exists at [soarify.itch.io/jpeg](https://soarify.itch.io/jpeg), not used):
1. Convert to YCbCr; chroma subsampling `Chroma` (4:4:4, 4:2:2, 4:2:0, 4:1:0) = average 2x2 / 4x1 then bilinear up.
2. **Compute pass, local_size 8x8, one workgroup per block**: load 64 samples into shared memory, level-shift -128,
   separable 8-point DCT-II (rows then columns, each 8 MACs per output = ~1 K MAC per block per channel, tiny),
   **quantise** `round(C/(Q*scale))` with the standard luma/chroma tables (IJG: scale = 5000/q for q<50, else 200-2q, /100),
   optional coefficient glitches, **dequantise**, inverse DCT, level-shift, back to RGB.
3. Coefficient glitches (DCT-domain data-bend): zero the AC row/col, swap two coefficients, boost one frequency
   (`Zigzag index` + `Gain`), add random noise to DC (`DCdrift` - block brightness walks), random coefficient from a
   neighbour block (wrong-block look), clamp magnitude.
4. **Block size** 8 (JPEG), 16 (MPEG-2 macroblock luma), 4 (H.264 transform). Grid offset per frame (`Gridshift`) hides or
   exposes seams.
5. **Generation loss**: Feedback with a 1 px grid shift each pass at low Quality - JPEG-of-a-JPEG-of-... patina (DG-21).
Params: Quality 1-100 (default 30), Chroma mode, Blocksize (4/8/16), Zigzag glitch bank, DCdrift, Gridshift, Passes
(1-3 chained in the same shader is NOT possible; use feedback), Mix. Presets: `JPEG 8`, `Blocky 5`, `Chroma rot`,
`Mpeg2 mud`, `Generational`. Perf: ~0.8-1.5 ms (3 channels x 2 DCT passes in one shader). Inputs: TOP; Quality from audio.
Diff to `JZB_Lofi_Reducto`: Reducto = pixel blocks + palette; this is a real transform codec.

### DG-09 Bit-crush, bit-plane and bit-flip (`FX_bitcrush`), priority 2, size S

Colour-space crush: depth per channel (1-8 bits), RGB565 / RGB332 / 1-bit, posterise with ordered Bayer or blue-noise dither
(share with `FX_palette_map`), **bit-plane drop** (keep bit k only), **bit XOR/AND/OR** masks on the 8-bit integer value
(GLSL uint ops are available under Vulkan GLSL 4.5; verify in compute mode), **bit rotate/reverse** (data-bend look),
**bit-flip noise** with a hash and `Rate`, gamma-space vs linear quantise toggle, rare high-bit flips for the
"corrupt pixel" speckle (capped). Params: Bits R/G/B, Dither (None/Bayer4/Bayer8/Blue/Hash), Dither amount, Op (XOR/AND/OR/
NOT/Rotate), Mask 0-255, Plane, Flip rate. 0.2 ms. Presets: `4-bit arcade`, `Gameboy 2-bit`, `XOR psychedelia`,
`Speckle corrupt`. Pairs with `FX_palette_map` for the palette step.

### DG-25 Data-bending in 1D (`FX_databend`), priority 3, size M

Treat the image as a stream of bytes in scan order (row-major or column-major or Hilbert), apply AUDIO-STYLE effects as
Audacity/raw-import databenders do, and write back: delay/echo with feedback (offset N samples, wraps into the next row
= diagonal ghost), low-pass/high-pass (running mean, 1-pole), bit reduction, sample-rate reduction (hold N), reverse
chunks, wah/phaser-like sweep (modulated one-pole), reverb (3-4 combs) - each a single-pass tap loop along the scan
line (for horizontal order) or a Compute prefix scan (running filters across a long stream). Params: Order, Effect,
Delay samples (1-8000), Feedback 0-0.95, Cutoff, Rate hold, Wrap rows, Mix per channel. 0.5 ms for taps. Reference:
common databending practice; no TD component found with these exact semantics. Offline cousin: JPEG/PNG byte corruption
via Python (`random` byte edits then PIL decode) to batch-generate still sets.

## 6. Colour, line and signal breakage

### DG-10 RGB / chromatic split extras (`FX_chroma`), priority 2, size S
Exists: td-port `rgb_split` + Glitch chromatic modes (Horizontal, RGB Tear, Radial Lens). Add: **Spectral** (N=5-16 taps
across a wavelength ramp, true dispersion colour from a `rampTOP`), **Flow-driven** (offset = DG-01 mv * gain: only moving
parts separate), **Luma-driven** (bright separates more), **Prism ghost** (3 copies with hue tint, add), **Per-line random**
(scanline hash), **Lens barrel + radial**, **Chroma-delay** (chroma channels only, the YIQ mis-registration of VHS).
Params: Amount px, Angle, Mode, Taps, Falloff, Centre. 0.3-0.8 ms. Priority 2 (a quick win for every look).

### DG-11 Scanline tearing, V-hold roll, sync loss (`FX_synctear`), priority 2, size S
Exists in Glitch (fine tears). Add: **V-hold roll** (picture scrolls vertically with a black/sync bar and a bounce), **H-hold
wobble** (per-line x offset from smooth noise + hash, slope on the top 10 %), **flag-waving** (low-freq sin, amplitude
along y), **sync loss** (periods of shearing offset that ramps up then snaps), **line doubling** (every n-th line repeats),
**tear bands with hold** (height 1-80 px, quantised). Params: Roll speed, Wobble, Band height, Band count, Snap rate,
Direction. 0.3 ms. Trigger/beat input as `Hit` hook; DG-23 uses these as sub-blocks.

### DG-23 VHS / CRT breakage (`FX_vhs`), priority 1, size M
**Look.** Reference: StageLab `JZB_Lofi_VHS` (VHSifyer): YIQ signal path, rightward chroma bleed, wobble, tracking band,
noise, dropouts, scanlines, head switch, interlace, Glitch button; `JZB_Lofi_CRT`. Community shader packs
(Minecraft "VHS Nostalgic", "VHS Shader", RITEG port) list: horizontal chroma smear, line jitter, bottom head-switch band,
luma grain, YIQ bleed; a VideoHelp thread gives VHS chroma bandwidth of ~40 lines across the width, Doom9 explains the
head-switch band in blanking. Commercial "Signal Decay" (UE HLSL, ntscQT-derived) adds dot crawl and tracking damage.
No shader code was read here.

**Technique.** One compute pass chain (<= 3 passes, all compute):
1. RGB -> YIQ. Luma low-pass horizontally (`Lumabw`, ~3 MHz = 240 px at 1920 w) with a 1-D tap loop; chroma blurred much
   harder (`Chromabw`, ~40 "lines"), shifted right by `Chromaoffset` px, plus **chroma vertical bleed** (smear down 1-4 lines).
2. Per-scanline **jitter**: x offset = noise(y, t)*`Jitter` + low-freq `Wobble`; **tracking band**: a vertical window
   (Y position drifts, height 20-160 px) where jitter is x30, luma gets noisy, and white speckle appears.
3. **Head-switching band**: the last 6-12 lines of the field shift hard left/right with a ramp and a bright noise bar.
4. **Tape dropouts**: short horizontal white/colour streaks (length 20-300 px, thickness 1-3 lines, hash on (line, frame));
   density limited by Safety.
5. **Dot crawl / cross-colour** (NTSC): luma modulated by a subcarrier pattern `sin(2pi(x*0.25 + y*0.5 + t*...))` times
   chroma energy; **ghosting**: second copy delayed 12-40 px at 20 % (multipath).
6. **Interlace**: even/odd lines come from the current and the previous frame (Cache tap) when `Interlace` on (comb
   artefacts on motion), optional field swap.
7. **CRT stage** (menu CRT off/Scan/Mask/Bloom/Curve): scanline beam profile (gaussian per line, brightness-modulated
   width), aperture grille / slot mask (not for LED pitch: mask >= 3 px, per `JZB_Lofi_CRT`), barrel curvature + vignette, bloom
   (from the shared mip pyramid), phosphor persistence (Feedback per-channel decay, R slowest).
8. Tape **noise**: luma grain + chroma noise (capped) + occasional full-frame "static burst" (limited, Safety).
Params: Lumabw, Chromabw, Chromaoffset, Jitter px, Wobble, Tracking amount/pos/height/speed, Headswitch, Dropouts
density, Dotcrawl, Ghost, Interlace, CRT mode, Mask, Curve, Bloom, Persistence, Noise, Tint (tape warmth), Trigger =
Glitch button. Presets: `Worn tape`, `Camcorder 90s`, `Broadcast dropout`, `CRT arcade`, `Dying VCR`. Perf: 0.8-1.5 ms.
Inputs: TOP; trigger Null (tracking error on Hit), audio level -> Jitter.

### DG-24 Signal loss, no-signal, power-off and combing (`FX_signalloss`), priority 2, size S
States: **No signal** (blue/black/bars - SMPTE bars generator exists in `test_pattern`), **snow** (capped flicker, never above
Safety), **colour-bars roll**, **freeze with lag lines**, **CRT power-off collapse** (vertical squash to a line, then dot
with afterglow, 0.4 s), **power-on bloom**, **interlace combing**, **OSD overlay** ("PLAY / REC / NO SIGNAL", timecode,
tracking bar; Text TOP, English only unless the client supplies words). A `State` switch with crossfades and a `Fail`
trigger. 0.3 ms. This is the readable "TV breaks" moment. White static is the highest flash risk in the file: lower-
contrast and temporally smoothed by default.

### DG-22 Wavefold, solarize, UV fold (`FX_wavefold`), priority 3, size S
Triangle-wave fold of channels: `x' = abs(fract(x*g + o) * 2 - 1)` (folded colour bands, per channel `g`), solarize
(`x'=abs(x-t)`), clipping/overdrive, **UV fold** (mirror-repeat coordinates with a time-varying fold count and a noise
offset for jagged glitch stripes), cosine palette remap after fold. Params: Gain RGB, Offset, Folds, Mode, Mix. 0.2 ms.
Audio: Gain from level. A cheap "overdriven signal" colour look.

### DG-28 LED module failure / panel dropout (`FX_ledfail`), priority 3, size S
Simulated stage-hardware failure: random rectangles the size of an LED cabinet go black / freeze / show a test colour;
column/row dead lines; flicker module. Takes the face table (R02 cabinet sizes in `stagelab`) so rectangles follow real
cabinet borders. Look only; never to be mistaken for a real fault in rehearsal (label it in the control panel).
0.1 ms.

## 7. Time-based destruction

### DG-12 Frame shuffle / per-block temporal offset (`FX_timeshuffle`), priority 2, size M
Cache TOP ring (`cachesize` N frames, 16F 1080x1920 ~ 16.6 MB per frame, so N=30 ~ 0.5 GB: Quality half = 1/4 of that).
Modes: **Whole-frame shuffle** (play the last N frames in a permuted order, new permutation each bar/beat), **Reverse chunk**,
**Hold/ping-pong**, **per-block time** (each cell picks its own delay by hash/noise/luma, the "temporal macroblock" look; needs
the ring as a 2D-array or 3D texture: `glslTOP` input as array/3D via `texture3dTOP`, as `td-port/slit_scan` does; or K <= 8
`cacheselectTOP` taps as inputs), **scrub** (delay driven by a CHOP). Params: Length frames, Mode, Blocksize, Seed, Rate,
Shuffle trigger, Smooth (interp). 0.5-1.0 ms + VRAM; park when not used. Overlaps `stutter` (beat repeat, whole frame): this
adds the per-block and permutation modes.

### DG-13 Slit-scan / time displacement (`FX_slitscan`), priority 2, size S
Exists: td-port `slit_scan` (script-written ring). New TD-native build: `timemachineTOP` (per-pixel time offset from a map,
`blackoffset`/`whiteoffset`, sample mode) or a ring in `texture3dTOP` with the `timemap` made by compute GLSL (ramp, radial,
spiral, luma, noise, audio spectrum as a vertical map, DG-01 flow magnitude as the map = motion slows time, mask). Add
**feedback melt** (time map integrates). Params: Map, Depth frames, Offset, Angle, Centre, Invert, Smooth. 0.5 ms + VRAM.
Flash-safe by nature but ghosting in crowds should be reviewed.

### DG-14 Melt / drip / liquid sag (`FX_melt`), priority 1, size M
**Look.** Image sags and drips downward in streams, colours smear, like paint or hot wax. Two techniques, both cheap:
1. **UV-field melt** (stateful, no image blur): state `U` (rg16f offset) integrates `U += (g + noiseColumn(x,t)*Drip +
   luma(src)*Weight) * dt` with `Viscosity` damping; output = `src(uv - U)` (sampled from the CLEAN source each frame, so no
   resolution loss). `Recover` pulls U back to 0 (for beats).
2. **Drip streaks**: per column a random start threshold `h(x)`; below it the colour of the pixel at `h(x)` is stretched
   downward by length `L(x,t)` growing with time (the Stretch of DG-05), edge softened with a rounded drop head.
3. **Wave melt**: sin waves in x, amplitude growing in y (hot-air sag) - the cheap flag-waving form.
4. **Gravity-masked**: sag only in a mask (person, bright areas).
Params: Gravity (0-1), Drip (0-1), Viscosity, Noise scale/speed, Weight (luma), Direction (down/up/left/right/radial),
Recover, Mask, Sagrate. Presets: `Wax`, `Acid drip`, `Heat haze`, `Beat sag` (Recover on kick). 0.4-0.8 ms.

### DG-21 Feedback destruction and generation loss (`FX_feedbackkill`), priority 2, size M
Wrap a Feedback loop with a destructive transfer function: JPEG block pass (DG-08) with grid shift, level crush /
posterise, hue rotation per generation, zoom + rotate + translate, displacement by its own gradient, edge dilation
(burn-in), blur-then-sharpen, Wavefold (DG-22). Add a **stabiliser** so it can never lock to white/black: auto-gain
toward mid, leak toward the live source (`Decay`), clamp, and Safety limiter. Params: Transform (zoom/rotate/shift),
Crush bits, Hue step, Jpeg Q, Displace amount, Leak, Gain, Reset. 0.5-1.0 ms (16F feedback; compute chain, not Pixel-mode
multi-pass). Presets: `Photocopy decay`, `Tape-dub`, `Burn-in`, `Acid loop`.

## 8. Fracture, dissolve, explode (the "destruction" half)

### DG-15 Shatter with physics (`FX_shatter`), priority 1, size L
Exists: td-port `JZBD_Shatter` - a clean single-pass Voronoi shift/rotate that settles back (no physics, offline gate only).
This one makes real shards that FLY, fall and (optionally) leave a hole. Reference: screen-shatter shaders
([Godot "simple glass broken"](https://godotshaders.com/shader/simple-glass-broken/): Voronoi-like fragments, per-fragment fall delay/drift/rotation, one 0-1 `fall_progress`,
edge glow and fade) and jump flooding Voronoi ([JFA](https://www.comp.nus.edu.sg/~tants/jfa/rong-guodong-phd-thesis.pdf), coordinates in RGBA, passes = log2(max(w,h))).

**Technique (forward mapping, because moved shards break per-pixel inverse mapping):**
- **Shards = triangles of a jittered grid** (cheapest; no Voronoi/Delaunay op in 31550). `Shards` 64-4096. Build once: a
  Grid SOP/POP with jittered points -> triangulate (Grid-based triangle pair per cell, jittered corners, fixed topology;
  a Facet-unique pass gives per-triangle points and an `id` attribute) -> a Geometry COMP with an orthographic Render
  TOP at 1080x1920, material = GLSL MAT: vertex shader reads the shard state from `state` TOP by `id` (position offset,
  rotation, scale, depth), fragment shader samples `src` at the ORIGINAL uv (attribute), so the image is intact when the
  state is zero.
- **State (compute TOP, one texel per shard, RG32F position/velocity + angle/angvel):** gravity, `Impulse` radial from an
  impact point (strength falls with distance), angular velocity, drag, floor bounce at y=floor (`Bounce`,
  `Friction`), lifetime fade, optional `Return` spring (assemble back = reverse shatter, great on beat), per-shard
  stagger by distance from impact (crack propagation).
- **Crack lines**: edges drawn in the fragment shader from barycentric distance; `Crack` colour/width/glow.
- **Background**: the hole shows `Back` TOP (black, a second clip, or the previous frame = hole shows "behind the
  screen"), shards in front.
Params: Shards, Impact xy, Impulse, Gravity, Spin, Bounce, Floor, Stagger, Return (spring), Fade, Crack width/colour, Depth
(z scale/shading), Back source, Trigger/Hold, Seed. Modes: Fall (gravity), Explode (radial), Implode, Hover (anti-gravity
slow), Reassemble. Presets: `Screen smash`, `Slow-mo glass`, `Reassemble on beat`, `Floor tiles`. Perf: 1-2 ms (4096 triangles trivial;
the 1080x1920 fragment pass dominates); Render TOP + MAT is a Vulkan path used elsewhere in the lab (check against T-46:
single render pass, compute only for state).
Fallback if the render path misbehaves: pure compute **scatter** pass (each shard texel pushes its pixels with atomics
- avoid) - not recommended.

### DG-16 Glass crack, broken LCD and dead pixels (`FX_crack`), priority 2, size M
Three looks in one COMP:
1. **Glass crack**: seeds with density ~ 1/r around the impact (radial + concentric fracture), distance to the second-
   nearest cell edge gives bright crack lines; each cell displaces the image by a tiny rotation (refraction), growth
   animated by `Radius` threshold, `Fade` of cracks into chips (a few cells fall away = holes). Single pass with a 3x3 cell
   search in a hash grid (as in the existing shatter shader) + a radius-warped seed distribution.
2. **Broken LCD / ink burst**: coloured vertical/horizontal bars, ink-blot spreading from a point (radial noise growth, black
   core, magenta/green halos), stuck-pixel lines.
3. **Dead pixel clusters** (see also DG-28).
Params: Impact, Radius, Cells, Cracks width, Refract, Ink size, Bars count, Seed. 0.4-0.8 ms. Trigger: Hit.

### DG-17 Disintegrate / Thanos / crumble to dust (`FX_disintegrate`), priority 1, size L
**Look.** A sweeping front turns the picture into drifting particles that blow away (the "snap"), leaving the remaining
image eroded. Reference technique notes found: a Metal/SwiftUI Thanos shader uses a bottom-left to upper-right diagonal wave
plus per-pixel hash noise so each pixel has its own speed, angle and threshold; Unity VFX Graph variants sample the
skinned mesh with particles and sync a Shader Graph dissolve ([Rookies project](https://www.therookies.co/projects/101628); other hits were aggregator spam); basic dissolve with
burn edge = noise threshold with two thresholds ([gamedev.net shaderlab sprite dissolve](https://gamedev.net/shaderlab/14-sprite-dissolve-effect/), [Godot dissolve with burn edge](https://godotshaders.com/shader/2d-dissolve-with-burn-edge/)).
Ruben Fro's "edge fray / dissolve" is the high-end reference in BR.

**Technique, two layers composited:**
1. **Remaining image** (single pass): `front(p) = dot(p, dir)/L + noise(p)*Roughness` ; `t = progress*(1+Roughness) -
   front`; `alpha = 1 - smoothstep(0, Edge, t)` per pixel with per-pixel hash for stagger; this eats the picture as
   the front passes (reuse DG-18).
2. **Dust**: pixels converted into particles when `t` crosses 0: a compute particle engine (the `BO_particles` compute
   engine or PX point-fx) with N = 100k-500k particles seeded from a grid on the source (every k-th pixel; position,
   colour sampled from `src`, birth time from `t`); after birth: velocity = wind (`Winddir`, `Windspeed`) + curl noise *
   `Turbulence` + up-draft * `Lift`; drag; rotation of sprites; fade over `Life`; additive or premultiplied alpha (see
   `overlay-alpha-premultiplied` memory). Colour from the source pixel; optional ember/hot tint for the first 0.3 s.
   Sprites rendered with `pointspriteMAT` (BO s4) - blur/size per particle for dust.
3. **Mask-aware**: `Mask` TOP (person) restricts which pixels disintegrate; the front can ORIGINATE from the mask edge
   (distance field) instead of a direction.
Params: Progress (0-1, also auto with Duration/Beats), Direction/Centre, Roughness, Edge, Stagger, Particles count (Quality),
Wind, Turbulence, Lift, Life, Size, Tint, Mask, Reverse (reassemble from dust), Loop. Presets: `Snap`, `Ash sweep`,
`Pixel blow`, `Radial vanish`, `Person fades`. Perf: image layer 0.4 ms; particles 262k = 4.7 ms in the lab today
(STATUS), so default 100k (~2 ms): total 1.5-3 ms; Quality ladder 25k/100k/250k. Build the particle layer as a PX
module when PX lands; until then use the compute engine.
Not possible: true volumetric dust sim (needs fluid); curl-noise drift is the stand-in (or couple to `BN_fluid2d` velocity as
an option).

### DG-18 Burn / erode / dissolve edge (`FX_burn`), priority 1, size M
**Look.** A threshold eats the picture; the boundary glows white-hot -> orange -> black char -> ash; or acid, frost, ink
or hologram-glitch edge palettes. **Technique** (single pass): `m = fbm(p*Scale + flow) + Bias(front)`;
`d = m - Progress`; alpha = smoothstep on d; the burn band is `0 < d < Band` mapped through a `Ramp` (cosine palette or
`rampTOP` lookup), `Emissive` added; char band darkens the remaining image before it dies; `Outline` option. Vertical bias
makes flames rise (godot fire dissolve; edge particles via DG-17). **Fire-spread CA mode** (stateful): state `B`
(r = burn time, g = fuel from image luma/edges) in rgba16f; each frame a burning neighbour ignites a cell with probability
`Spread * (1 + wind·dir) * fuel`; burn duration scales with fuel; yields a front that follows image detail (paper-burn
look), reset on Hit. Variants: Erode (morphological min/max filter iterated 1-8 px by luma), Frost, Acid (green
edge), Hologram. Params: Progress, Scale, Roughness, Band, Ramp, Emissive, Wind, Spread, Fuel from (luma/edges/mask), Mode
(Noise/CA), Erosion px, Protect. Presets: `Paper burn`, `Acid melt`, `Frost over`, `Ember rise`. Perf 0.4-1.0 ms (CA mode
one extra compute pass). Edge colour limited by Safety (no white flicker above the flash cap).

### DG-19 Explode / implode (2D and 3D) (`FX_explode`), priority 2, size M
2D: radial push-out/pull-in from a centre, pixels moved along the radial by `Amount * falloff(r)`; **polygon explode** form
(grid of triangles as in DG-15 with higher stagger and no floor: debris cloud); **stretch bloom** (radial smear). 3D: any SOP
mesh -> `facetSOP` unique points -> per-primitive id/centre attribute -> GLSL MAT vertex shader moves each triangle along its
normal/centre vector with noise, rotation and time (the classic geometry-shader explode without a geometry shader) -
this is how to destroy an imported model (Blender export, `td_import_blender`) or the stage previz. Params: Amount, Falloff,
Centre/Axis, Noise, Spin, Gravity, Fade, Seed. 0.5-1.5 ms depending on triangle count. Trigger: Hit; `Return` spring
reassembles. Presets: `Pop`, `Debris cloud`, `Implode pull`.

### DG-20 Mosaic decay / quadtree pixelation (`FX_mosaic`), priority 2, size S
Hierarchical pixelation: for each pixel pick the finest mip level (mip chain via TOP mipmap filter, `textureLod`) where
local variance < `Detail`; high-contrast areas stay sharp, flat areas become big blocks (quadtree look). Decay mode: block
size grows with time by noise (`Decayrate`), dead blocks fall (drop alpha, drift down), and rebuild on trigger. Params: Min/Max
block (2-128 px), Detail, Blocks shape (square/hex), Decayrate, Fall, Seed. 0.3 ms. Overlaps FFGL Reducto; this is the
adaptive and animated form.

### DG-27 Slash cuts / parted image (`FX_slash`), priority 3, size S
Cut lines (straight or jagged) split the image into two parts that slide apart along the cut with a gap showing `Back`,
sparks along the line (add), multiple cuts staggered on a beat. Exists in spirit: `hit_slice`, `slice_*` stage-slice
family; this one is free-angle in image space. 0.3 ms.

### DG-26 3D and geometry destruction (`GM_destroy`), priority 2, size L
No fracture/Voronoi SOP or POP in the 31550 dumps (verify by create probe). Practical routes, best first:
1. **Pre-fractured in Blender** (Blender 5.2.2 LTS is installed here and `td_import_blender` + `tools/blender_export.py` exist):
   Cell Fracture (add-on, availability in 5.2 UNVERIFIED), Voronoi/Geometry Nodes fracture, or Rigid Body bake -> export
   **baked animation as Alembic/USD** -> `alembicSOP`/`usdCOMP` plays an exact destruction (best fidelity, zero live
   physics cost; trigger and scrub from TD).
2. **Live rigid pieces**: import the fractured pieces as separate meshes with a piece id; one state texture per piece (pos,
   rotation, velocity) from a compute TOP (gravity, floor plane, radial impulse, no piece-piece collisions - spheres proxy
   approximate); Geometry COMP instancing (or a GLSL MAT vertex shader reading the state) draws them. Same engine as
   DG-15 with 3D transforms.
3. **Polygon explode** (DG-19) for anything without pre-fracture.
4. **Vertex rot/melt**: `deformSOP`/`latticeSOP`/noise displacement with a dissolve front, `booleanSOP` slices for cut-away
   effects (cost grows with polygons - bake).
5. **Voxel crumble**: cube instancing from a point cloud (`BL_cloud_morph`, PX) with the burn/dissolve front and falling
   voxels - destruction of a scanned person/splat; ties to the Ruben-Fro look catalog.
Params shared: Impact point/radius, Strength, Gravity, Bounce, Pieces count, Spin, Fade, Return. Perf scene-dependent; budget
<= 2 ms for 2000 pieces.

## 9. Shared kit (DG-29)

- **`DX_safety`** (priority 1, S): luminance-step limiter (per-frame mean luma delta cap and per-pixel step cap), flash
  counter (3 Hz cap per region of 25 % of screen: one global mean + a 4x4 grid), noise/static contrast cap, red-saturation
  cap (only 20 % red-flash rule), `Panic` pulse, fail-safe Switch to passthrough on exceed, status CHOP (`flashes_per_s`,
  `limited`). Based on `AX_strobber.md` (that tool had no limiter) and `concert-visuals-research` flash limits.
- **`DX_masks`** (S): Protect/target mask from person mask, luma, edge, noise, shape; soft edges; feather; invert.
- **`DX_triggers`** (S): beat / kick / onset from `AC_audio`, `Hit` pulse, `Bars` counter, latch, one-shot with
  `Hold`; rate-limited (refractory) so effects cannot be machine-gunned; outputs Null CHOPs for custom-par export.
- **Common block library** in `builders/` (hash/noise/YCbCr/DCT/bitonic helpers as `#include`-style DAT snippets) so the 25+
  COMPs share verified code. Use `zkit` for the controls panel as in every lab COMP.

## 10. Audio and control mapping (common)

| Source | Maps to |
|---|---|
| Kick onset | Refresh (DG-01), Hit (DG-15/16/19), Recover (DG-14), shuffle (DG-12), glitch hit (DG-07/11/23) |
| Bass level | Gain (DG-01), Density (DG-07), Threshold sweep (DG-04), Tracking amount (DG-23) |
| High/spectrum | Chroma amount (DG-10), Detail (DG-20), Dropouts (DG-23) |
| Bars/beats counter | Mosh transition (DG-02), Burn progress (DG-18), Disintegrate progress (DG-17) |
| Person mask / depth | Protect (all), Sort mask (DG-04), Stretch-from-edge (DG-05), Disintegrate mask (DG-17) |
| MIDI | knob banks via `MIDI_mapper`, exposed through `ZC` controls (zkit) |

## 11. Suggested build order (and how to extend what exists)

1. **Shared kit** DX_safety/masks/triggers (S).
2. **DG-05 smear/stretch**, **DG-18 burn**, **DG-14 melt** (cheap, single-pass, immediately usable, test the safety kit).
3. **DG-01 datamosh engine** with Diffgrad + LK first (block match + helper later), then **DG-02** transition. Offline tool
   **DG-03** in parallel (done in an hour; already half-verified).
4. **DG-04 pixel sort** after a scratch-TD probe of shared memory / barrier / local_size 512 on MoltenVK (T-83).
5. **DG-07 block glitch**, **DG-23 VHS**, **DG-08 DCT**.
6. **DG-15 shatter physics**, **DG-17 disintegrate** (needs PX or BO engine decisions).
7. The rest by need.
Each COMP: builders/<name>.py + docs/builds/<name>.md + offline logic test + live checks (static source = identity; trigger
= expected frame; fps with other COMPs parked), per the lab pattern.

## 12. Open questions (for the user)

1. Datamosh on live IMAG camera: allowed with the limiter, or stored-clips only? (Rammstein used it on IMAG, J13 flagged it.)
2. Apple Vision optical flow helper: OK to add a new arm64 helper kind (flow) after the person mask? (Install-free: system
   framework; speed UNVERIFIED.)
3. ffglitch / Datamosher Pro install for DG-03 (nothing installed; ffmpeg alone covers the I-frame drop recipe).
4. Priorities: confirm the P1 list (datamosh, pixel sort, block glitch, melt, burn, shatter, disintegrate, VHS).
5. Pre-fractured Blender assets for DG-26: which objects (stage model, logo extrusion, a person scan)?

## 13. Sources (search results read; nothing downloaded)

- Datamosh: [Buck moshing sandbox](https://buck.co/sandbox/moshing) (fetched, technique only), [Codrops Sep 2026 datamosh](https://tympanus.net/codrops/2026/09/02/breaking-the-frame-building-a-real-time-datamosh-effect-with-three-js/)
  (403, snippet only), [Interactive & Immersive HQ part 2](https://interactiveimmersive.io/blog/touchdesigner-resources/datamoshing-in-touchdesigner-part-2/) / [part 3](https://interactiveimmersive.io/blog/glsl/datamoshing-in-touchdesigner-part-3/) (truncated),
  [Minecraft datamosh shader](https://modrinth.com/shader/datamosh) (8x8 block procedural imitation), [CDM Jitter GLSL optical flow](https://test.cdm.link/?p=42950),
  [Derivative optical-flow warp post](https://derivative.ca/community-post/asset/optical-flow-warp-video-input-and-blender-scenes/68940).
- Offline mosh: [FLOSS Manuals encoding](https://archive.flossmanuals.net/a-look-at-open-video/encoding-explained), [Datamosher Pro](https://github.com/Akascape/Datamosher-Pro), [VideoHelp I-frame removal](https://forum.videohelp.com/threads/404025-Removing-I-frames-programmatically-%28automatic-workflow%29),
  [ffglitch-scripts tutorial](https://cdn.jsdelivr.net/gh/ramiropolla/ffglitch-scripts@main/tutorial/readme.md), [FOSDEM 2025 ffglitch](https://fosdem.org/schedule/event/fosdem-2025-6416-ffglitch-the-multimedia-bitstream-editor).
- Pixel sort: [Zucconi GPU sorting](https://www.alanzucconi.com/2017/12/13/gpu-sorting-1/), [Sapphire PixelSort](https://borisfx.com/documentation/sapphire/ae/pixelsort/), [pixelsort pip](https://www.pypi.org/project/pixelsort),
  [Processing ASDF thread](https://discourse.processing.org/t/asdf-pixel-sort-with-different-sections-color-threshold/43416).
- DCT: [NVIDIA CUDA DCT8x8 paper](https://developer.download.nvidia.com/assets/cuda/files/dct8x8.pdf), [Intel IPP quant/DCT docs](https://www.smcm.iqfr.csic.es/docs/intel/ipp/ipp_manual/IPPI/ippi_ch15/functn_DCTQuantFwd8x8_JPEG.htm), [daslang dct_jpeg.das](https://daslang.io/doc/_downloads/c7b977a06df9fcdd1c09761ac07228f5/dct_jpeg.das).
- Dissolve/disintegrate/shatter: links in DG-15 and DG-17; JFA thesis (Rong Guodong); a TD MCP "create_jfa_voronoi" tool
  (glama listing, GLSL TOP chain seeds -> init -> log2 passes) exists as a pattern.
- VHS: [VHS Nostalgic](https://www.modpackindex.com/shader/200324/vhs-nostalgic), [VHS Shader](https://www.modpackindex.com/mod/161614/vhs-shader), [Signal Decay (Fab)](https://www.fab.com/listings/a922243a-7cf3-45d5-bc8b-2cf8c3280ec5),
  [VideoHelp chroma-resolution thread](https://forum.videohelp.com/showthread.php?p=2773432), [Doom9 head-switching](https://forum.doom9.org/showthread.php?p=1068809).
- Shadertoy: searched; the search tool returned no Shadertoy pages, so NO shader id is cited. When a build picks one, fetch it
  with `td_shadertoy` and record the id + licence (Shadertoy default is CC BY-NC-SA 3.0 unless stated; licences do not block
  research per memory, but record the source).
- Local: `td-port/*` READMEs and shaders, `stagelab/docs/plugin-stack.md`, `docs/research/{Y,J,BA,BO,BR,AX}_*.md`, `LEARNINGS.md`
  T-18/T-19/T-46/T-47, op dumps in `docs/research/ops/`.

## 14. Extension notes for the existing COMPs

- `FX_motion_trail`: expose its `Threshold` motion mask as the `Protect`/target mask for DG-01/05; its Cache-tap pattern is the
  `prev` frame source for DG-01.
- `FX_palette_map`: the dither modes feed DG-09; a palette step after DG-08/09 gives the cheap "Game Boy corrupt" look.
- `BO_particles` / PX: DG-17 dust layer; add a `Disintegrate` module (front texture -> birth time) to PX instead of a private engine.
- td-port `JZBL_Glitch`: keep as the fine-glitch layer; add `Hit` hooks so DG-07/11/23 fire on the same trigger.
- td-port `JZBD_Shatter`: keep as the no-physics version; DG-15 shares its crack colour, Shards and Seed names.
- `slit_scan`: swap its script ring for `timemachineTOP` after a live probe (no frame_exec script, fewer moving parts).
