# FX0 - Effects + emulation build backlog (compiled from FX1-FX5, 26 Oct 2026)

One ranked, de-duplicated build backlog for the TD MCP lab, compiled from five research files written the same day:
`FX1_destruction_datamosh_glitch.md` (DG-xx), `FX2_analog_video_hardware_emulation.md` (AV-xx),
`FX3_film_lens_camera_emulation.md` (F/L/C/S-x), `FX4_software_fx_emulation.md` (D-x, G-XXX),
`FX5_generative_and_artist_looks.md` (Gxx, Ex). User ask: "destruction type effects, datamoshing and etc - go n research
first all of what we can add"; destruction / datamosh / glitch is built first.

**Nothing here is measured.** TD was not touched for FX0-FX5. Every ms figure is the source file's estimate for
1080x1920 on the M1 Max under Rosetta/MoltenVK (TD 2025.31550) and must be replaced by `td_perf` + real fps at build
time (CLAUDE.md: 60 fps, ~3 ms per COMP, park idle COMPs). Read the source card (ID column) before building a row; this
file only ranks, merges and groups.

## 0. Light verification done for this compile (no TD calls)

| Claim in FX1-FX5 | Checked how | Result |
|---|---|---|
| `cacheTOP`, `timemachineTOP`, `texture3dTOP`, `tonemapTOP`, `opencolorioTOP`, `lensdistortTOP`, `sortPOP` exist in 31550 | grep of `docs/research/ops/ops_{TOP,POP}_2025.31550.json` | present (names only; pars not re-read) |
| Optical Flow TOP unusable here | `opticalflowTOP` IS in the op dump; T-18 says unsupported on this Mac | consistent: listed but not usable; every flow need goes through block matching / Vision helper |
| T-46 (pixel-mode multi-pass tears) / T-47 (compute mode clean) | `LEARNINGS.md` lines 200 / 216 | present; every multi-pass module below is compute-mode GLSL |
| ffmpeg `noise` bsf, `codecview`, `mestimate` on this Mac (offline datamosh tool) | `ffmpeg -bsfs` / `-filters` | present |
| td-port has `glitch`, `rgb_split`, `shatter`, `slit_scan`, `rutt_lines`, `vignette`, `ascii`, `halftone`, `kaleido`, `flow_fx`, `shockwave`, `echo`... and NO datamosh / pixelsort / CRT / VHS / grain folder | `ls td-port/`, `td-port/INVENTORY.md` "Pending port" rows | consistent with FX1-FX4 ("pending port" = StageLab FFGL exists, TD port missing) |
| Lab COMPs to extend (`FX_strobe`, `FX_motion_trail`, `FX_palette_map`, `TP_test_pattern`, `BO_particles`, `BN_fluid2d`, `BN_cloth`, PX) | `builders/*.py`, `docs/builds/*.md` | builders + build docs exist |
| Datamosh cost 1.0-2.5 ms (FX1) vs 1.5-3 ms (FX4) | cross-read | sources disagree; FX0 uses 1-3 ms |

Not checked: any par name, any perf figure, Shadertoy/ISF code, artist techniques beyond what the sources say.

> **User rule (26 Oct): "dont bloat stuff just for modularity - it should make sense".** The kit below is the
> ceiling, not the plan: build only the parts the modules in the current phase use (Phase 1: a simple slot rack +
> panic; masks/triggers only when a destruction module needs them; no codegen/registry/field framework up front).
> **Pilot built (26 Oct, live): `FX_glitch` rack + `smear` module, module template in `docs/builds/fx_glitch.md`.**
> **`FX_film` wave A + B prepared offline (26 Oct, not live yet): rack + tonecurve (with the display dither), stock,
> halation, grain, leaks, ca, diffusion/bloom, streak, flare, star; LIVE CHECKS + expected numbers in
> `docs/builds/fx_film.md`.**

## 1. The modular COMP plan (few powerful COMPs, not 150 small ones)

Every source file proposed its own chain wrapper (FX1 shared kit, FX2 `AN_chain`, FX3 `FC_filmchain`, FX4 `G-STACK`,
PX module rule). FX0 merges them: **one rack framework, used by every FX COMP**.

### 1.0 `DX_kit` - the shared base (build first, every COMP below depends on it)

| Part | What | From |
|---|---|---|
| `DX_rack` | module slot list (add / remove / reorder table, Bypass + Mix per slot, one preset recall for the whole stack, per-slot cook ms row, Cost meter, `Lite` switch, `allowCooking` off for bypassed slots) | FX2 `AN_chain`, FX3 `FC_filmchain`, FX4 G-STACK, PX rule |
| `DX_panic` | `Panic` = instant passthrough of the whole rack + a status CHOP. **No flash / luminance / red caps or safety guides (user rule 26 Oct: "no limits or unsafe guides - user running it decides")** | user rule (replaces the FX1 DG-29 / FX3 s0 / FX5 `Safe` limiter proposals) |
| `DX_field` | single-channel field TOP: linear / radial / box / ring / noise / luma / edge / person mask / depth / audio waves / Effector Null gizmo + combine ops; every module's `Amount` x field; also the `Protect` mask (logos, names, Urdu never pass through destruction) | FX4 G-FIELD, FX1 DX_masks |
| `DX_triggers` | kick / onset / bar from `AC_audio`, `Hit` pulse, refractory (no machine-gunning), latch, one-shot Hold | FX1 DX_triggers |
| `DX_lib` | GLSL snippet DATs: hash/noise, YCbCr/YIQ, DCT 8x8, bitonic step, blue-noise texture (one shared), pyramid down/up (dual-Kawase), highlight extractor (soft knee) | FX1 s9, FX2 s1.8, FX3 s2 |
| Conventions | `Amount 0` = exact passthrough, `Seed`, `Quality` (Full/Half/Quarter), `Signal Res` for analog, linear 16F working format, zkit controls + 5-10 presets per module, MIDI/OSC exposable | all five |

### 1.1 The COMPs and their module lists

| COMP | Modules (source IDs) | Extends / absorbs |
|---|---|---|
| **`FX_glitch`** (digital breakage) | `mosh` datamosh engine (DG-01/D1), `moshcut` transition (DG-02), `pixelsort` true sort (DG-04/D2), `smear` stretch + displace-feedback mode (DG-05/06, G-SMEAR), `block` macroblock + tile scramble (DG-07/D8), `dct` JPEG crush + generation loss (DG-08/D9), `bits` bit-crush/plane/flip + databend (DG-09/25), `chroma` RGB/prism/spectral split (DG-10), `mosaic` quadtree decay (DG-20), `timeshuffle` per-block time offset (DG-12), `timedisplace` slit-scan / time map (DG-13/D10), `feedbackkill` generation loss / burn-in (DG-21), `slash` cuts (DG-27), `ghost` frame-difference (D12) | td-port `glitch` (stays the fine layer, gets `Hit` hook), `rgb_split`, `slit_scan` (swap script ring for `timemachineTOP`), `flow_fx` (block-SAD estimator reused), `FX_motion_trail` (prev-frame Cache tap) |
| **`FX_destroy`** (physical destruction) | `melt` drip/sag/liquify (DG-14/D7), `burn` erode/dissolve edge + fire-spread CA (DG-18), `crack` glass/broken LCD/dead pixels (DG-16/D5), `shatter` shards with physics + refraction (DG-15/D3/D11), `disintegrate` dust (DG-17/D4), `explode` 2D/3D implode-explode + blast (DG-19/D6) | td-port `shatter` (no-physics version stays), `shockwave`, `hit`; `BO_particles` / PX for the dust back-end (a PX `Disintegrate` module, not a private engine) |
| `GM_destroy` (3D, separate) | Blender pre-fracture, poly explode, vertex rot (DG-26) | `td_import_blender` (BC) |
| **`FX_analog`** (CRT, signal, tape) | `crt` mask + beam/scanlines + geometry + convergence + phosphor + glow (AV-01..06, G-CRT), `crtfault` roll/tear/degauss/power-off (AV-07), `monitor` macro with 12 presets (AV-08), `terminal` phosphor text (AV-09), `ntsc` composite encode/decode (AV-10), `pal` PAL/SECAM/S-Video/RF (AV-11), `artifactcolour` CGA/Apple II/NES (AV-12), `rf` reception/snow (AV-13), `interlace` (AV-14), `vhs` tape (AV-17/DG-23/G-VHS), `transport` pause/shuttle/stop (AV-18), `camcorder` CCD/DV (AV-19), `cctv` security/night vision/thermal (AV-19b, G-HEAT), `signalloss` sync loss/no-signal/combing (DG-11/24), `plasma` (AV-15) | StageLab `JZB_Lofi_CRT` / `JZB_Lofi_VHS` (same control names + presets so Arena and TD match), td-port pending CRT/VHS ports become these modules |
| **`FX_synth`** (video-synth rack) | `osc` oscillators/shapes (AV-21), `colorize` Sandin/Paik-Abe + overflow/wavefold/solarize (AV-22/DG-22), `bands` amplitude classifier + contour (AV-23/G24), `keyer` keyers + logic blend (AV-24), `vfilter` analog filters (AV-25), `ruttetra` scan processor (AV-26), `scanimate` (AV-27), `vfeedback` camera-at-monitor (AV-28), `magnet` wobbulator (AV-29), `holo` hologram (G-HOLO) | td-port `rutt_lines` (extended to true deflection) |
| **`FX_retro`** (palettes, dither, text, small displays) | `palette` hardware palettes (AV-34), `dither` Bayer/blue-noise/IGN/diffusion/GB Cam (AV-35/G-DITHER/S4/G25), `retroscreen` (AV-36), `cycle` palette cycling (AV-37), `teletext` (AV-38), `glyph` text-mode/ASCII/matrix rain (AV-39/G-ASCII/G21), `smalldisplay` LCD/VFD/Nixie/flip-dot/split-flap/e-ink (AV-40), `halftone` | `FX_palette_map` (palette + dither modes live there; FX_retro calls it), td-port `ascii`, `halftone` |
| **`FX_film`** (= FC_filmchain; film, lens, camera, colour) | film: `tonecurve` (F1), `stock` + bleach/cross/Technicolor (F2), `halation` (F3), `grain` 3 models (F4), `weave` (F5), `dust` (F6), `leaks` (F7), `gate` (F8); lens: `streak` anamorphic (L1), `flare` (L2/G-LENSFLARE), `star` (L3/G-STARGLOW), `diffusion` Pro-Mist + `bloom` (L4/G-BLOOM/AV-04 shares pyramid), `ca` spectral (L5; same shader as FX_glitch `chroma`), `distort` (L6), `vignette` (L7), `tiltshift` (L8), `lensdirt` (L9), `dof` + `bokeh` (L10/L11/G-DOF), `vintage` presets (L12); camera: `shutter` motion blur (C1), `rolling` shutter + flash banding (C2), `exposure` flicker/AE/WB (C3), `iso` (C4), `ccd` artefacts (C5), `cine` pulldown (C7), `handheld` (C8); colour: `aces` (S1), `lut` bank (S2), `grade` (S3/FX_grade), `display` dither/LED-safe (S4), `logview` (S5) | td-port `vignette`, `rgb_split`, `shake`, `slit_scan` (rolling engine); pending ports Grain, Grade, Bloom, FlowFX, DepthFX (port the .frag, don't rewrite); native Tone Map / OCIO / Lens Distort / Blur |
| **`FX_scope`** (scopes, vector, HUD) | `xy` audio XY oscilloscope with phosphor (AV-30/G19), `vector` Vectrex/Asteroids (AV-31), `lissajous` goniometer/harmonograph/spirograph (AV-32/G38), `scopes` waveform/parade/vectorscope/histogram (AV-33), `hud` zebra/peaking/false colour/REC (C6/G-HUD), `ridgeline` (G18), `spectro` spectrogram/radial (G23) | `LP_laser_path` (same path source), `FX_motion_trail` (persistence) |
| **`FX_venue`** (reality check, not a look) | `ledwall` pitch/cabinet/scan/greyscale/viewing angle/faults (AV-41/DG-28), `daylight` black level/washout (AV-43), `projector` optics/DLP rainbow (AV-42), `camonscreen` moire/rolling vs LED refresh (AV-44) | `PV_previz_stage`, `LK_projection_room` |
| **`GEN_pattern`** (one-pass generators; LIVE 26 Oct on 31550, 12 modules, in the main .toe: `docs/builds/gen_pattern.md`) | `truchet` (G06), `opart` moire (G17), `wallpaper` quasicrystal/Islamic star (G07), `domainwarp` ink/marble (G28), `gyroid` (G29), `cymatics` (G27), `split` recursive split / grid hits (E7/G30), `barcode` Ikeda data look (G20/E2), `columns` light-column/LED array (E5/G35), `kaleido2` + `droste` + `infzoom` (G16/G-KALEIDO2/G-INFZOOM), generator pack (G-GEN) | td-port `kaleido`, `tunnel`, `tile`; `TP_test_pattern` (barcode family) |
| **`GEN_sim`** (compute-chain state textures) | `ca` lab incl. Wireworld/Lenia (G08/G26), `voronoi` JFA Voronoi/Delaunay/Worley (G10), `lowpoly` (G11), `stipple` (G25), `dla` Laplacian growth/lightning/coral (G09), `lic` ink (G02), `blobs` metaballs (G12) | `BN_fluid2d` (velocity in), reaction-diffusion + physarum (in progress) |
| **`GEN_points`** (POP / additive point looks) | `streamlines` flow field (G01), `attractor3d` (G03), `density2d` Clifford/de Jong (G04), `flame` fractal flame (G15), `graph` force-directed (G22), `lsystem` (G05), `form` Trapcode Form grid + Particular modules (G-FORM/G-PART2), `sparkle` (G-SPARKLE) | `BO_particles` (new modes), PX point-fx effectors |
| **`GEN_sdf`** | `sdfscene` raymarch toolkit with preset scenes (G13), `fractal` Mandelbulb/Mandelbox/Julia/2D (G14) | - |
| `GEN_interactive` (artist looks needing person/face input) | `ribbon` Lieberman ribbon brush (E8), `flowers` teamLab flowers/waterfall (E4), `pigment` Anadol data pigment (E1), `linevolume` Lemercier (E3) | `FT_face_track`, person mask, `BN_fluid2d`, `BO_particles` |
| Tools (not COMPs) | `tools/mosh.py` offline I-frame-drop / codec corruption (DG-03), `td_isf` ISF -> compute GLSL importer (G-ISF), `G-CLONE` cloner COMP, `G-TRANS` transition bank in `td_layer_mixer` (gl-transitions + moshcut + TV off), `MO_motion` behaviours (G-SPRING) | `td_shadertoy`, `td_layer_mixer` |

Existing-COMP extensions (no new COMP): `FX_strobe` (Stroboscope modes, FlashBulbs; no limiter, user rule),
`FX_motion_trail` (Echospace transform chain, Iterate; prev-frame source for `mosh`), `FX_palette_map` (hardware
palettes, PseudoColor, thermal ramp, Tritone, LUT loader), `TP_test_pattern` (broadcast cards + OSD AV-16, barcode
family), `BO_particles` (streamline/attractor/flame/flowers/pigment modes, G-PART2), `BN_cloth` (balloon/grains, P3).

## 2. Ranked backlog (de-duplicated)

Columns: **#** global rank; **D** difficulty S/M/L; **P** priority 1-3 (1 = build first for live); **ms** = estimate
@1080x1920 from the source (unmeasured); **Home** = COMP.module from section 1; **Extends** = existing thing it builds
on. Rank inside P1 follows the user's order: shared kit, then destruction/datamosh/glitch, then analog, film, generative.

### Priority 1

| # | Effect | Category | Emulates | TD technique (one line) | D | P | ms | Home | Extends | Src |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Rack + panic + field + triggers kit | framework | Arena effect rack, Notch Fields, Cavalry falloffs | slot table + Switch/Bypass, panic passthrough (no limiter), field TOP combine, trigger CHOP | M | 1 | 0.2-0.3 | DX_kit | zkit | DG-29, G-FIELD, G-STACK, AN_chain, FC core |
| 2 | Datamosh engine | glitch | codec P-frame bloom (Notch Motion Datamosh, Rammstein 2019 IMAG) | hold reference frame in Feedback, estimate per-block MVs (block-match compute GLSL / diffgrad / LK / Vision helper / stored MVs), advect held frame by them, inject residual | L | 1 | 1-3 | FX_glitch.mosh | flow_fx block SAD, FX_motion_trail Cache | DG-01, D1 |
| 3 | Mosh transition | glitch / transition | datamosh cut A->B | B's motion vectors drag A's pixels until I-frame snap | M | 1 | +0.3 | FX_glitch.moshcut | mosh, td_layer_mixer | DG-02 |
| 4 | Offline datamosh / codec corruption tool | tool | real I-frame drop | ffmpeg `-bsf:v noise=drop=...` (verified), `codecview`/`mestimate` to bake MVs for stored clips | S | 1 | offline | tools/mosh.py | - | DG-03 |
| 5 | Pixel sort (true sort) | glitch | ASDF/Sapphire PixelSort, Notch Pixel Sort | segmented bitonic sort in compute GLSL along rows/columns, threshold spans by luma/hue/sat, Instant or Melt | L | 1 | 1-3 | FX_glitch.pixelsort | StageLab `JZB_Lofi_Sort` names | DG-04, D2 |
| 6 | Smear / pixel stretch | glitch | Arena Blow, pixel stretch, Myles displace-feedback | single-pass directional stretch from mask/threshold edge; feedback-displace mode | S | 1 | 0.4-1.0 | FX_glitch.smear | Myles pixelSorting (baseline) | DG-05, DG-06, G-SMEAR |
| 7 | Block / macroblock glitch + tile scramble | glitch | macroblock corruption, Sapphire TileScramble, Arena Fragment | 16x16 block hash: offset/hold/stale-frame/colour-plane per block, trigger + density | M | 1 | 0.3-1.0 | FX_glitch.block | td-port glitch Hit hook | DG-07, D8 |
| 8 | Melt / drip / liquify | destruction | Arena Goo, Sapphire WarpPuddle, AE Liquify | feedback + gravity-biased displacement by luma/noise, Recover on kick | M | 1 | 0.4-0.8 | FX_destroy.melt | BN_fluid2d velocity option | DG-14, D7 |
| 9 | Burn / erode / dissolve edge | destruction | film burn-through, paper burn dissolve | noise/field threshold sweep with glowing ember edge; optional fire-spread CA | M | 1 | 0.4-1.0 | FX_destroy.burn | DX_field | DG-18 |
| 10 | Shatter with physics | destruction | Notch Voronoi Fracture + RBD, Houdini RBD | hash/JFA Voronoi shards in a state texture (pos/vel/rot per shard) stepped in compute, drawn by instancing; floor + settle | L | 1 | 1-2 | FX_destroy.shatter | td-port shatter (names, crack colour) | DG-15, D3 |
| 11 | Disintegrate / dust | destruction | Thanos snap, Trapcode Particular layer emitter | dissolve mask front -> per-pixel birth time -> particles from the image colour, curl drift | L | 1 | 1.5-3 | FX_destroy.disintegrate | BO_particles / PX module | DG-17, D4 |
| 12 | DCT / JPEG crush + bit corruption bank | glitch | Sapphire JpegDamage / DigitalDamage, Notch Bit Crush | 8x8 DCT + quantise + coefficient damage in compute; uint bit-crush/plane/flip | M | 1 | 0.8-1.5 | FX_glitch.dct + .bits | - | DG-08, DG-09, D9 |
| 13 | VHS tape | analog | VHS colour-under, Universe VHS, Notch VHS | YIQ at signal res: chroma low-pass + delay, luma bandwidth, line wobble, tracking band, dropouts, head switch | L | 1 | 0.5-2.2 | FX_analog.vhs | JZB_Lofi_VHS | AV-17, DG-23, G-VHS |
| 14 | CRT (mask, scanlines, geometry, glow, phosphor) + monitor macro | analog | aperture/slot/shadow-mask CRTs, consumer/PVM/arcade | one-pass mask + Gaussian beam + curvature, pyramid glow, Feedback phosphor; 12 presets; LED-safe pitch clamp | M | 1 | 1.5-2.5 (all) | FX_analog.crt + .monitor | JZB_Lofi_CRT | AV-01..05, AV-08, G-CRT |
| 15 | CRT faults (roll, tear, degauss, power-off/on) | analog / transition | CRT failures, TV-off | UV warps + collapse to line/dot, timed by trigger | M | 1 | 0.2-0.4 | FX_analog.crtfault | - | AV-07 |
| 16 | NTSC composite encode/decode | analog | dot crawl, cross-colour, ringing | modulate YIQ on subcarrier at signal res, FIR comb/notch decode, numpy reference test | L | 1 | 1-2 | FX_analog.ntsc | - | AV-10 |
| 17 | Video feedback (camera at monitor) | synth | Crutchfield, studio monitor loops | Feedback TOP + transform + gain clamp + colour rotate, beat re-seed | M | 1 | 0.6-1.2 | FX_synth.vfeedback | FX_motion_trail | AV-28 |
| 18 | Colorizer + overflow + wavefold | synth | Sandin IP, Paik-Abe, LZX | luma -> phase colour ramp, Clip/Wrap/Fold/Mirror overflow | S | 1 | 0.15-0.2 | FX_synth.colorize | FX_palette_map | AV-22, DG-22 |
| 19 | Amplitude classifier / contour bands | synth / generative | LZX/Sandin classifier, topo lines | iso-luma bands + line extraction | S | 1 | 0.2-0.3 | FX_synth.bands | - | AV-23, G24 |
| 20 | Oscillators + keyers + logic blend | synth | analog video synth modules | H/V-locked oscillators, luma/chroma keys, min/max/xor matrix | M | 1 | 0.2-0.5 | FX_synth.osc + .keyer | - | AV-21, AV-24 |
| 21 | Rutt/Etra scan processor | synth | Rutt/Etra | luma-displaced scan lines as instanced line strips with glow | M-L | 1 | 1-2 | FX_synth.ruttetra | td-port rutt_lines | AV-26 |
| 22 | Scanimate flying logo | synth | Scanimate | logo raster through deflection warps + feedback trails + colorizer | M | 1 | 0.8-1.5 | FX_synth.scanimate | colorize, PRISM brand palette | AV-27 |
| 23 | Hardware palettes + dither engine | retro | GB/NES/C64/CGA/Spectrum/PICO-8; Bayer, blue noise, diffusion | OKLab nearest-palette + ordered/blue-noise dither (diffusion = row-serial compute, probe) | M | 1 | 0.2-3 | FX_retro.palette + .dither | FX_palette_map | AV-34, AV-35, G-DITHER, S4 |
| 24 | LED wall emulation + daylight washout | venue | P3.9 LED cabinets, outdoor sun | pitch grid + aperture + greyscale steps + viewing angle + ambient add | M-L | 1 | 0.9-1.6 | FX_venue.ledwall + .daylight | PV_previz_stage | AV-41, AV-43, DG-28 |
| 25 | XY audio oscilloscope | scope | Jerobeam Fenderson oscilloscope music | audio L/R -> points/lines, beam-dwell brightness, phosphor feedback | M | 1 | 0.5-1.0 | FX_scope.xy | LP_laser_path, FX_motion_trail | AV-30, G19 |
| 26 | Filmic curve + film stock engine | film | negative/print stocks, bleach bypass, cross-process, Technicolor | Tone Map TOP + per-channel curves + dye-coupling matrix | M | 1 | 0.3-0.4 | FX_film.tonecurve + .stock | native Tone Map | F1, F2, G-FILM |
| 27 | Halation | film | red halo around highlights on film | highlight extract -> pyramid blur -> red-shifted add | S-M | 1 | 0.5-0.8 | FX_film.halation | DX_lib pyramid | F3 |
| 28 | Film grain (3 models) | film | 8/16/35 mm grain | luma-dependent blue-noise grain, per-gauge size | S-M | 1 | 0.15-0.3 | FX_film.grain | td-port Grain .frag (pending) | F4 |
| 29 | Light leaks / film burn | film | leaks, end-of-roll burn | animated warm gradients + noise mask, screen blend | S | 1 | 0.15 | FX_film.leaks | - | F7 |
| 30 | Bloom / glow / diffusion | lens | Arena Bloom, Notch Glow, Pro-Mist, Sapphire UltraGlow | soft-knee highlights + pyramid (or Blur preshrink) | S | 1 | 0.4-0.8 | FX_film.diffusion | DX_lib pyramid | L4, G-BLOOM, AV-04 |
| 31 | Chromatic aberration (lateral/spectral) | lens / glitch | lens CA, prism split | radial per-channel or N-tap spectral offset | S | 1 | 0.1-0.8 | FX_film.ca = FX_glitch.chroma | td-port rgb_split | L5, DG-10 |
| 32 | Anamorphic streak + lens flare + star | lens | anamorphic flares, ghosts, cross screen, Trapcode Shine/Starglow | highlight -> 1D horizontal pyramid streak; ghost chain; rotated streaks | M | 1 | 0.6-1.2 each | FX_film.streak + .flare + .star | DX_lib pyramid | L1, L2, L3, G-STARGLOW, G-LENSFLARE |
| 33 | Motion blur / shutter angle | camera | 180/360-degree shutter | feedback accumulation; block-match velocity blur mode | M-L | 1 | 0.15-1.8 | FX_film.shutter | FX_motion_trail, flow_fx | C1 |
| 34 | Rolling shutter + flash banding | camera | CMOS jello, LED/strobe banding | per-row time offset via Cache/timemachine | M | 1 | 0.1-0.3 | FX_film.rolling | td-port slit_scan | C2, AV-19b |
| 35 | Colour pipeline: ACES-ish, LUT bank, grade | colour | ACES, .cube LUTs, lift/gamma/gain/CDL | OCIO TOP + own fit, Lookup/3D LUT, OKLab grade | M | 1 | 0.2-0.4 each | FX_film.aces/.lut/.grade | td-port Grade (pending), FX_palette_map | S1, S2, S3, FX_grade |
| 36 | DOF + bokeh | lens | cine shallow focus | CoC from depth (DC_depth_cam / Render depth / fake), gather blur, highlight discs | L | 1 | 1-1.5 | FX_film.dof | td-port DepthFX, DC_depth_cam | L10, L11, G-DOF |
| 37 | Truchet / op-art / domain-warp / ridgeline pack | generative | Carlson Truchet, Riley/Vasarely op-art, IQ warped fbm, Unknown Pleasures | one-pass GLSL patterns with audio inputs; op-art behind `Safe` | S | 1 | 0.3-0.8 | GEN_pattern | - | G06, G17, G28, G18 |
| 38 | Data barcode (Ikeda look) + recursive split (Max Cooper) | generative / artist | Ikeda test pattern, Max Cooper "Parting Ways" | beat-clocked barcode/grid; recursive subdivide on hits; `Safe` on flicker | S-M | 1 | 0.3-0.4 | GEN_pattern.barcode + .split | TP_test_pattern | G20, E2, E7/G30 |
| 39 | CA lab (Life ... Lenia) + JFA Voronoi toolkit + blobs | generative | cellular automata, Voronoi/Worley, metaballs | state textures stepped in compute; JFA log2 passes | M | 1 | 0.4-3 | GEN_sim | reaction-diffusion lab | G08, G10, G12 |
| 40 | Attractor dust + flow-field streamlines | generative | strange attractors, flow-field line art | POP points advected, additive Render TOP | M | 1 | 1-4 | GEN_points | BO_particles | G03, G01 |
| 41 | SDF raymarch toolkit | generative | Shadertoy/IQ SDF scenes | single-pass raymarch with module scene table | L | 1 | 0.8-2 | GEN_sdf | - | G13 |
| 42 | Ribbon brush + flowers/waterfall | artist | Lieberman ribbons, teamLab flowers | face/hand/person-mask driven strokes and blooms | M-L | 1 | 1-3 | GEN_interactive | FT_face_track, person mask | E8, E4 |
| 43 | ISF importer | tool | VDMX / ISF ecosystem (~200 filters) | parse ISF JSON header -> custom pars, GLSL -> compute TOP, PASSES -> compute chain | M | 1 | n/a | `td_isf` | td_shadertoy | G-ISF |
| 44 | Trapcode Form / Particular modules | generative | Trapcode Form / Particular | grid of points with field-driven displacement; layer emitter, aux, life curves | M | 1 | per BO/PX | GEN_points.form | BO_particles, PX | G-FORM, G-PART2 |

### Priority 2

| # | Effect | Category | Emulates | TD technique | D | P | ms | Home | Extends | Src |
|---|---|---|---|---|---|---|---|---|---|---|
| 45 | Glass crack / broken LCD / dead pixels | destruction | smashed screen | crack SDF from impact + refraction offset + bleeding LCD columns | M | 2 | 0.4-0.8 | FX_destroy.crack | DX_field impact | DG-16, D5 |
| 46 | Explode / implode + blast | destruction | Universe Bang, Notch shockwave | radial 2D push + 3D polygon explode; smoke via fluid2d | M | 2 | 0.5-2 | FX_destroy.explode | td-port shockwave, BN_fluid2d | DG-19, D6 |
| 47 | Mosaic decay / quadtree | glitch | quadtree pixelation | per-cell variance split, decay over time | S | 2 | 0.3 | FX_glitch.mosaic | - | DG-20 |
| 48 | Frame shuffle / per-block time offset | glitch | temporal glitch | Texture 3D ring, per-block frame index | M | 2 | 0.5-1 + VRAM | FX_glitch.timeshuffle | td-port stutter | DG-12 |
| 49 | Time displacement / slit-scan hub | glitch / time | Sapphire TimeDisplace, Universe Echospace | `timemachineTOP` with field/flow/audio maps | S-M | 2 | 0.5-0.6 + VRAM | FX_glitch.timedisplace | td-port slit_scan | DG-13, D10 |
| 50 | Feedback destruction / generation loss | glitch | copy-of-copy decay, burn-in | feedback with blur/quantise/hue drift per pass | M | 2 | 0.5-1 | FX_glitch.feedbackkill | - | DG-21 |
| 51 | Sync tear / V-hold / signal loss / no-signal | analog | lost sync, TV no signal | line offsets, roll, blue screen / snow cards | S | 2 | 0.3 | FX_analog.signalloss | td-port glitch tears | DG-11, DG-24 |
| 52 | 3D geometry destruction | destruction 3D | Houdini RBD pre-fracture | Blender pre-fracture import + instanced pieces | L | 2 | scene | GM_destroy | td_import_blender | DG-26 |
| 53 | PAL/SECAM/RF/interlace/artifact colour | analog | broadcast variants, CGA/Apple II/NES | variants of the NTSC module | M | 2 | +0.2-1 | FX_analog.pal/.rf/.interlace/.artifactcolour | ntsc | AV-11..14 |
| 54 | VHS transport + camcorder + CCTV/thermal | analog / camera | pause/shuttle, CCD/DV, night vision, thermal | small modules on the VHS / grade path | M | 2 | 0.3-0.9 | FX_analog.transport/.camcorder/.cctv | FX_palette_map thermal ramp | AV-18, AV-19, AV-19b, G-HEAT |
| 55 | Phosphor terminal + CRT convergence | analog | green/amber terminals, misconvergence | text glow + per-channel offset | S | 2 | 0.2-0.4 | FX_analog.terminal / .crt | - | AV-09, AV-06 |
| 56 | Broadcast cards + OSD | analog | PM5544, SMPTE bars, PLAY/REC OSD | patterns + Text TOP | S | 2 | 0.1 | TP_test_pattern ext | TP_test_pattern | AV-16 |
| 57 | Video filters + magnet/wobbulator + hologram | synth | analog filters, Paik magnet TV, sci-fi hologram | FIR filters, deflection warp field, scan bars + fresnel | S-M | 2 | 0.2-1 | FX_synth.vfilter/.magnet/.holo | - | AV-25, AV-29, G-HOLO |
| 58 | Vector display + goniometer/harmonograph + video scopes + HUD | scope | Vectrex, goniometer, waveform/vectorscope, zebra/peaking | line instancing; Analyze-TOP stats; false colour | M | 2 | 0.3-1 | FX_scope | - | AV-31, AV-32, AV-33, C6, G-HUD, G38 |
| 59 | Retro screen + palette cycling + teletext | retro | 8-bit framing, colour cycling, Ceefax | virtual res + border, index-texture cycling, sixel renderer | S-M | 2 | 0.15-0.4 | FX_retro | - | AV-36, AV-37, AV-38 |
| 60 | Glyph / ASCII / matrix rain | retro | text-mode, Hacker Text | glyph atlas lookup, per-glyph colour/size from source | S | 2 | 0.3-0.4 | FX_retro.glyph | td-port ascii | G-ASCII, AV-39, G21 |
| 61 | Projector optics + camera-on-screen | venue | keystone/DLP rainbow, camera moire vs LED | optics warps, rolling-vs-refresh banding sim | M | 2 | 0.4-0.5 | FX_venue | LK_projection_room | AV-42, AV-44 |
| 62 | Gate weave, dust/scratches, lens distort, physical vignette, tilt-shift, lens dirt | film / lens | projector weave, film dirt, barrel/fisheye, miniature | small one-pass modules | S-M | 2 | 0.05-0.5 | FX_film | td-port vignette | F5, F6, L6, L7, L8, L9 |
| 63 | Exposure flicker / ISO noise / CCD artefacts / pulldown | camera | auto-exposure pump, sensor noise, smear | luma pumps, noise models, column smear | S-M | 2 | 0.05-0.5 | FX_film | - | C3, C4, C5, C7 |
| 64 | Kaleido2 / hyperbolic / Droste / infinite zoom | generative / warp | Sapphire kaleidos, Escher Droste, Arena Infinite Zoom | fold libraries, log-polar, feedback zoom | M | 2 | 0.5 | GEN_pattern.kaleido2/.droste/.infzoom | td-port kaleido, tunnel | G16, G-KALEIDO2, G-INFZOOM |
| 65 | Quasicrystal / wallpaper / cymatics / harmonograph | generative | Islamic star, Chladni | one-pass math patterns | S-M | 2 | 0.3-1 | GEN_pattern | - | G07, G27, G38 |
| 66 | LIC, DLA growth, low-poly, density maps, fractal flame | generative | ink flow, lightning/coral, low-poly video, Electric Sheep | compute chains / additive render | M-L | 2 | 1-3 | GEN_sim / GEN_points | BN_fluid2d | G02, G09, G11, G04, G15 |
| 67 | Fractal explorer, L-systems, force graph | generative | Mandelbulb, plants, networks | raymarch (two-float zoom), Python-cached strings, Neighbor POP | L | 2 | 0.5-8 | GEN_sdf / GEN_points | G13 | G14, G05, G22 |
| 68 | Data pigment, line volumes, light columns, spectrogram | artist / generative | Anadol, Lemercier, UVA/Volume | BO + fluid pigment, previz-checked lines, LED arrays | M-L | 2 | 0.3-6 | GEN_interactive / GEN_pattern / FX_scope | BO, fluid2d, previz | E1, E3, E5, G23 |
| 69 | Transition bank | transition | Arena mixers, gl-transitions | transition shaders in the layer mixer family | M | 2 | 0.2-0.5 | G-TRANS (td_layer_mixer) | td_layer_mixer, moshcut, crtfault | G-TRANS |
| 70 | Cloner | framework | Arena/Notch cloners, Cavalry Duplicator | instancing with field-driven per-instance transforms + Cache time offsets | M | 2 | 0.5 | G-CLONE | DX_field | G-CLONE |
| 71 | Kuwahara / paint / warp bank | stylise | Notch Kuwahara, Sapphire paint, Arena warps | anisotropic Kuwahara compute, small warps | M | 2 | 0.5-1 | FX_glitch (warp) / own `paint` module | - | G-PAINT, G-KUWAHARA, G-WARP |

### Priority 3

| # | Effect | Home | Src |
|---|---|---|---|
| 72 | Wavefold / solarize as standalone (else inside FX_synth.colorize) | FX_synth | DG-22 |
| 73 | Databend 1D byte filters | FX_glitch.bits | DG-25 |
| 74 | Slash cuts / parted image | FX_glitch.slash (LIVE 26 Oct) | DG-27 |
| 75 | LED module failure as a look | FX_venue.ledwall faults | DG-28 |
| 76 | Glass refraction shatter shader | FX_destroy.shatter Look glass (LIVE 26 Oct) | D11 |
| 77 | Frame-difference ghost | FX_glitch.ghost (LIVE 26 Oct) | D12 |
| 78 | Plasma false contour, small displays (LCD/VFD/Nixie/flip-dot/e-ink) | FX_analog.plasma (LIVE 26 Oct) / FX_retro.smalldisplay | AV-15, AV-40 |
| 79 | Gate overlays, vintage-lens presets, handheld moves, log view | FX_film | F8, L12, C8, S5 |
| 80 | Gyroid slice, stipple | GEN_pattern / GEN_sim | G29, G25 |
| 81 | POP grains, balloon, 3D pyro, procedural motion behaviours | BN_cloth / BO / MO_motion | FX4 5.3, G-SPRING |
| 82 | Micro effects: bend, tri, long shadow, electrify, autolevel, displace, sparkle, zap, Tao, Mir | FX_glitch.misc (LIVE 26 Oct: bend, suck, tri, longshadow, electrify, autolevel, displace, zap; sparkle = GEN_points.sparkle, Tao / Mir = 3D generators, skipped) | FX4 G-* (S) |

Totals after de-dup: ~150 source items -> 82 backlog rows -> **14 COMPs + 1 kit + 5 tools** (DX_kit, FX_glitch, FX_destroy,
GM_destroy, FX_analog, FX_synth, FX_retro, FX_film, FX_scope, FX_venue, GEN_pattern, GEN_sim, GEN_points, GEN_sdf,
GEN_interactive).

## 3. Build order (destruction / datamosh / glitch first), times and parallel lanes

Time units are agent build hours per item including builder script, offline logic test, live checks and checkpoint
(S ~1-2 h, M ~3-5 h, L ~6-10 h; estimates, not measured). Live lanes follow the lab rules: register with
`tools/lane.py`, park others, risky GLSL on the scratch TD first (T-83), 2-6 live builders at once. Wall-clock assumes 5
lanes.

| Phase | What | Lanes (parallel) | Agent-h | Wall-clock |
|---|---|---|---|---|
| **0. Probes + kit + pilot** (serial gate) | Scratch-TD probes: compute shared memory + `barrier()` + local_size 512 (decides bitonic sort, DCT), uint bit ops, RGBA32F image load/store (shard/state rows), block-match dispatch at 1080x1920, Blur preshrink ms, OCIO `.cube` load; then `DX_kit` (rack, panic, field, triggers, lib); pilot = `FX_glitch.smear` to lock the module template | 1 lane (probes can split into 2) | ~8-10 | ~6-8 h |
| **1. Destruction + datamosh + glitch** | A: `mosh` (L) -> `moshcut` (M). B: `pixelsort` (L). C: `block` -> `dct` + `bits` -> `chroma` -> `mosaic`. D: `FX_destroy` `melt` -> `burn` -> `shatter` (L). E: `disintegrate` (L, PX/BO module) -> `explode`. Offline anytime: `tools/mosh.py` (no TD, ~1 h, half-verified already) | 5 live + 1 offline | ~55-65 | ~12-15 h (A and D are the long poles) |
| **2. Glitch time + analog core** | A: `timedisplace` + `timeshuffle` + `feedbackkill`. B: `FX_analog.vhs` (L). C: `crt` + `monitor` + `crtfault`. D: `ntsc` (L, numpy reference first). E: `crack` + `signalloss` + `GM_destroy` (Blender) | 5 | ~45-55 | ~10-12 h |
| **3. Film + retro + venue** | A: FX_film wave A (tonecurve, stock, halation, grain, leaks, display dither). B: wave B lens (ca, diffusion/bloom, streak, flare, star). C: `FX_retro` palette + dither + glyph. D: `FX_venue` ledwall + daylight. E: `td_isf` importer (mostly MCP code, offline tests + one live check) | 5 | ~45-50 | ~10 h |
| **4. Synth + scope + camera** | A: `FX_synth` colorize, bands, osc/keyer, vfeedback. B: ruttetra + scanimate. C: `FX_scope` xy + vector + scopes/hud. D: FX_film camera (shutter, rolling, exposure, iso) + colour (aces, lut, grade). E: `dof` (L) | 5 | ~45-55 | ~10-12 h |
| **5. Generative packs** | pilot `GEN_pattern.truchet` (module template for GEN), then A: GEN_pattern rest. B: GEN_sim (CA, JFA, blobs). C: GEN_points (attractors, streamlines, form) via scratch TD for POP loops. D: GEN_sdf. E: GEN_interactive (ribbon, flowers) | 5 | ~50-60 | ~12 h |
| **6. P2/P3 tail** | transitions, cloner, remaining analog/film/generative P2, then P3 by need | 3-5 | ~40+ | by need |

Total P1+P2 ~ 290-340 agent-hours; with 5 lanes ~ 60-70 wall-clock hours (about 6-8 working days). Phase 1 alone
(the user's first ask) is ~1.5-2 days after a ~1 day Phase 0. Each phase ends with a combined fps check (all new
modules in one rack, others parked) before the next starts.

Can run in parallel with no TD: `tools/mosh.py`, `td_isf` parser + offline tests, numpy reference tests for NTSC / DCT /
bitonic / CA, preset tables, docs.

## 4. Open questions carried from FX1-FX5 (for the user)

1. Datamosh on live IMAG camera, or stored clips only? (no limiter: user rule) (FX1 Q1, FX4 Q1)
2. OK to add an Apple Vision optical-flow helper kind (arm64, system framework, speed UNVERIFIED)? (FX1 Q2)
3. ffglitch / Datamosher Pro install for the offline tool, or ffmpeg only? (FX1 Q3)
4. CRT/VHS looks for the LED wall (mask scaled to pitch, 6+ px) or IMAG/screens only? (FX2)
5. Shatter shards transparent over a second clip (Arena alpha, premultiplied) or opaque in TD? (FX4 Q2)
6. ISF importer: convert third-party ISF files beyond the MIT Vidvox set? (FX4 Q3)
7. Film first look: neon/tungsten night (halation + streak) or clean cinema (stock + DOF)? Preset names descriptor-only? (FX3)
8. Hearn Videowarp: which device/work? Moment Factory / Tundra techniques not found. (FX2, FX5)
9. Confirm the P1 list order above (kit -> mosh/sort/block/melt/burn/shatter/disintegrate -> VHS/CRT -> film -> generative).

## 5. Sources

`FX1_destruction_datamosh_glitch.md` s2, s9, s11, s14; `FX2_analog_video_hardware_emulation.md` s0-2, s10-12;
`FX3_film_lens_camera_emulation.md` s1-2, s7-8; `FX4_software_fx_emulation.md` s1, s5-7; `FX5_generative_and_artist_looks.md`
s0-1, s7-8. Checks in section 0: `docs/research/ops/ops_TOP_2025.31550.json`, `ops_POP_2025.31550.json`, `LEARNINGS.md`
T-18/T-46/T-47, `../td-port/` listing + `INVENTORY.md`, `builders/`, `docs/builds/`, local ffmpeg. TD, Arena, REST, OSC and
Syphon were not touched.
