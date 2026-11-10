# FX2: Analog video + hardware emulation (offline research, 26 Oct 2026)

Scope: effects that recreate known looks from CRTs, composite/NTSC/PAL, VHS and camcorders, analog video synthesizers
(Sandin, Rutt/Etra, Paik/Abe, LZX), oscilloscopes and vector displays, 8-bit machine palettes and dither, teletext,
LED walls and projectors. Nothing was run in TD and nothing was loaded (offline; `jazib-td` not called). Build target:
TD 2025.31550, macOS under Rosetta, Vulkan/MoltenVK: single-pass or **compute-mode** GLSL only (T-46/T-47), no Optical
Flow TOP (T-18), 60 fps, about 3 ms per COMP, 1080x1920 build size, modular COMPs with many options and presets.

Labels: **[V]** read on a page this session; **[M]** from memory / general knowledge, not re-checked (treat as UNVERIFIED
until a build checks it); perf numbers are **estimates** (M1 Max under Rosetta, 1080x1920 = 2.07 MP, RGBA16F), to be
replaced by `td_perf` numbers when built. Licences are noted but do not block study or porting (user rule); the
safety audit still applies to anything downloaded.

## 0. What already exists (do not re-propose; extend)

| Already there | Where | How this file extends it |
|---|---|---|
| CRT / VHS / Reducto / Grain / ASCII / Tone / Sort / Glitch FFGL plugins, Arena-verified (mask, slot, shadow, aperture; curvature, roll, hum bar, degauss; YIQ chroma bleed, wobble, tracking, dropouts, head switch) | `stagelab/guides/JZB_Lofi_CRT.md`, `JZB_Lofi_VHS.md`, `effects/*/manifest.yaml` | They are the **look reference and preset source** for a TD version (same names for controls). TD adds what FFGL can't: multi-pass signal path (real NTSC/PAL encode-decode), state textures, CHOP/audio inputs, scopes |
| td-port: `JZBN_RuttLines` (ribbon relief, GLSL TOP, offline gate only), `PixelFX` (LED fixture patterns), Glitch, Halftone, Echo, Kaleido, SlitScan, Strobe, Stutter, RGBSplit, Ripple, Vignette, Tunnel, ColorWarp; CRT, VHS, Datamosh, Grain, Neon, Contour, PixelSort, Bloom, Feedback = **Pending port** | `td-port/INVENTORY.md`, `td-port/rutt_lines/README.md` | Rutt/Etra is extended to a true scan-processor (AV-26). CRT/VHS/Grain/Bloom ports become AV-01..AV-08 + AV-13 here instead of 1:1 ports |
| Lab COMPs: FX_strobe, FX_motion_trail, FX_palette_map, TP_test_pattern, BO_particles, BN_fluid2d, LP_laser_path, PV_previz_stage, LK_projection_room (+ projector/dome) | `STATUS.md`, `docs/builds/*.md` | palette_map is extended by AV-34/35 (fixed hardware palettes, dither); TP_test_pattern by AV-16 (broadcast cards + OSD); LP_laser_path feeds AV-30 (vector stroke source); projection_room gets the optical artefacts of AV-42..44 |
| Community CRT: "CRT TV Filter" 68947 (greenrhyno, 5,016 views, GLSL RGB sub-pixel + bloom + lens, built on macOS 31030); `MaxMainio` dither repo 74062 (MIT, Bayer/IGN/error diffusion, built 32820); Skywalker 71378 six dither algorithms; "Procedural CRT" and "ANALOG_TV" (paid, Gumroad); olegchomp `tdx-rnd` td-analog (NTSC/modulation/CRT/datamosh; no licence, Windows; recorded only) | `docs/research/community/*`, `popular/reddit.md` | Read 68947 + 74062 expanded GLSL first (read-only); do not load them in the main TD. Everything below is a clean-room build |

## 1. Shared architecture (decide once, all effects follow)

1. **Virtual signal resolution.** Analog gear has a fixed line count and bandwidth, not the output's pixels. Every effect
   works at a `Signal Res` (e.g. 480/576/240 lines; 640/720/910 samples per line), then upsamples to 1080x1920. This is
   authentic AND 4-10x cheaper. JZB_Lofi_VHS does the same ("Lines 240/480/576").
2. **Line axis.** The build canvas is vertical, real TVs are horizontal. Every analog module has `Line Axis` = Along X
   (default) / Along Y (treat the canvas as a TV on its side). Scanlines, chroma smear and head-switch bars follow it.
3. **Float pipeline.** Signals leave 0..1 (overshoot, negative chroma). Use RGBA16F between modules, RGBA32F only for the
   video-synth bus (AV-20+). Overflow behaviour is a first-class par: Clip / Wrap / Fold / Mirror (cheap, very analog).
4. **Compute-mode GLSL, `texelFetch`** for any multi-pass chain (T-47: 441/441 clean vs 0/151 pixel mode). Fixed tap
   loops (16-48 taps), no recursion. Sequential filters (IIR, error diffusion, Amiga HAM) run as one thread per row/tile
   at virtual resolution, or as long FIR approximations; verify first on the scratch TD (T-83).
5. **Field/frame clock.** One shared `field` index (0/1) and `fieldphase` from `absTime.frame` (60 fps = 60i fields:
   odd rows from frame n, even rows from n-1 for true interlace combing) feeds dot crawl, interlace, flicker, VHS head.
6. **Chain wrapper `AN_chain`** (same idea as PX modules): source -> [synth/colorizer] -> [deflection/scan] -> NTSC/PAL
   -> tape -> CRT optics -> LED/projector emulation -> out. Each module is its own COMP with the zkit controls, so it works
   standalone; the wrapper just adds slots (add/remove/reorder, bypass, one preset recall for the whole chain).
7. **Inputs everywhere:** `Amount` (0 = exact passthrough, like the FFGL set), `Seed`, trigger pulse (Glitch/Degauss style),
   audio-effector Nulls (level/band/beat) mapped by menu to the 2-3 main pars of each module, optional second image input
   (modulator) for cross-modulation effects.
8. **Perf discipline.** Heavy modules get a `Quality` par (taps, Signal Res), park when bypassed (`allowCooking`), and
   share one noise texture (blue/white, tileable) instead of re-hashing per module.
9. **LED-wall reality (PF26).** JZB_Lofi_CRT notes mask >= 3 px vs LED pitch and recommends >= 6 px on the LED wall. The mask
   and scanline modules therefore carry `LED Safe` (clamps mask period and line thickness to the LED pitch you enter).
   The R02 stage is 9984x3840 native; TD looks are built at 1080x1920 and scaled, so mask period is defined in
   **output-canvas fractions** as well as pixels (pitch-aware), otherwise a mask that reads at 1080 is mush after scaling.

## 2. Effect list (ID, name, priority) - ranked table, details in section 3+

Priority: 1 = build first (strong look, cheap, live-useful), 2 = good, 3 = niche / later. Difficulty S/M/L.

| ID | Effect | Pri | Diff | Est. cook @1080x1920 |
|---|---|---|---|---|
| **A. CRT** | | | | |
| AV-01 | CRT Mask (aperture / slot / shadow / LED sub-pixel) | 1 | S | 0.2-0.3 ms |
| AV-02 | CRT Beam + Scanlines + interlace | 1 | M | 0.3-0.6 ms |
| AV-03 | CRT Geometry (curvature, corners, overscan, glass) | 1 | S | 0.2 ms |
| AV-04 | CRT Glow (bloom + halation, mip chain) | 1 | S | 0.4-0.8 ms |
| AV-05 | CRT Phosphor (per-channel persistence, rolling beam scan) | 1 | M | 0.3-0.5 ms |
| AV-06 | CRT Convergence + focus (misconvergence, corner defocus) | 2 | S | 0.2-0.4 ms |
| AV-07 | CRT Faults (roll, H-tear, flyback, degauss, power-on/off collapse, hum bar, raster breathing) | 1 | M | 0.2-0.4 ms |
| AV-08 | CRT Monitor macro (all of A in one + 12 monitor presets) | 1 | M | 1.5-2.5 ms |
| AV-09 | Phosphor terminal (green/amber/white, burn-in, text glow) | 2 | S | 0.4 ms |
| **B. Composite / broadcast** | | | | |
| AV-10 | NTSC composite encode/decode (dot crawl, cross-colour, ringing) | 1 | L | 1.0-2.0 ms |
| AV-11 | PAL / SECAM / S-Video / RF variants | 2 | M | +0.2 ms |
| AV-12 | Artifact-colour machines (CGA composite, Apple II, NES 2C02) | 2 | M | 1.0 ms |
| AV-13 | RF reception (ghosting, snow, sound bars, channel change, sync loss) | 2 | M | 0.4-0.7 ms |
| AV-14 | Interlace combing + bob/weave | 2 | S | 0.2 ms |
| AV-15 | Plasma display (false contour) | 3 | M | 0.5 ms |
| AV-16 | Broadcast cards + OSD (PM5544, SMPTE, EBU, bars+tone, "NO SIGNAL", PLAY/REC OSD) | 2 | S | 0.1 ms |
| **C. Tape / camera** | | | | |
| AV-17 | VHS tape (colour-under, luma FM bandwidth, wobble, tracking, dropouts, head switch, generations) | 1 | L | 1.2-2.2 ms |
| AV-18 | VHS transport (pause jitter, shuttle bars, tape stop, slow-mo, tape crease) | 2 | M | 0.4 ms |
| AV-19 | Camcorder / CCD (vertical smear, auto-exposure pump, focus hunt, date stamp, DV block errors) | 2 | M | 0.5-0.9 ms |
| AV-19b | Security cam / night vision / thermal / rolling shutter | 2 | S-M | 0.3-0.8 ms |
| **D. Video synthesizer family** | | | | |
| AV-20 | Video-synth patchbay `AN_synth` (module slots, signal bus) | 1 | L | per module |
| AV-21 | Oscillators + shapes (H/V-locked, FM, sync, drift, staircase) | 1 | M | 0.2-0.4 ms |
| AV-22 | Colorizer + overflow modes (Sandin / Paik-Abe phase colour, wrap/fold) | 1 | S | 0.15 ms |
| AV-23 | Amplitude classifier + contour bands (iso-luma lines) | 1 | S | 0.2 ms |
| AV-24 | Keyers + blend matrix + logic (luma, chroma, min/max/xor, key gen) | 1 | S-M | 0.2-0.5 ms |
| AV-25 | Video filters (LP/HP/BP + resonance, differentiator, analog smear) | 2 | M | 0.5-1.0 ms |
| AV-26 | Rutt/Etra scan processor (true deflection + glow lines) | 1 | M-L | 1.0-2.0 ms |
| AV-27 | Scanimate flying-logo look | 1 | M | 0.8-1.5 ms |
| AV-28 | Video feedback (camera-at-monitor, Crutchfield) | 1 | M | 0.6-1.2 ms |
| AV-29 | Paik magnet / wobbulator (deflection field warp) | 2 | S | 0.2 ms |
| **E. Scopes / vector** | | | | |
| AV-30 | Oscilloscope XY (audio Lissajous, beam-dwell brightness, phosphor) | 1 | M | 0.5-1.0 ms |
| AV-31 | Vector display (Vectrex / Asteroids / Tempest) | 2 | M | 0.6-1.0 ms |
| AV-32 | Goniometer + harmonograph + Lissajous generators | 2 | S | 0.3 ms |
| AV-33 | Video scopes (waveform, RGB parade, vectorscope, histogram, false colour, zebra) | 2 | M | 0.4-0.8 ms |
| **F. Retro machines + displays** | | | | |
| AV-34 | Hardware palette quantiser (GB, NES, C64, CGA/EGA, Spectrum, Apple II, PICO-8, ...) | 1 | S-M | 0.2-0.5 ms |
| AV-35 | Dither engine (Bayer, blue-noise, IGN, error diffusion, GB Camera) | 1 | M | 0.2 ms ordered / 1-3 ms diffusion |
| AV-36 | Retro screen (virtual res, pixel aspect, border, raster bars, sprite flicker) | 2 | S | 0.15 ms |
| AV-37 | Palette cycling (8-bit colour cycling) | 2 | S | 0.15 ms |
| AV-38 | Teletext / Ceefax / Videotex page | 2 | M | 0.4 ms |
| AV-39 | Text-mode (CP437, PETSCII, ANSI) | 3 | S | 0.3 ms |
| AV-40 | Small displays (LCD ghosting, VFD, Nixie, flip-dot, split-flap, 7-seg, e-ink) | 3 | M | 0.2-0.5 ms each |
| AV-41 | **LED wall emulation** (pitch, cabinets, aperture, scan/refresh, greyscale, viewing angle, camera moire/banding, fault sim) | 1 | M-L | 0.8-1.5 ms |
| **G. Projector / venue** | | | | |
| AV-42 | Projector optics (keystone, lens falloff, CA, convergence, DLP rainbow) | 2 | M | 0.4 ms |
| AV-43 | Black-level / ambient light / daylight washout | 1 | S | 0.1 ms |
| AV-44 | Camera-on-screen sim (moire, rolling shutter vs LED refresh) | 2 | M | 0.5 ms |

Recommended first wave (all priority 1, cheapest look per hour): AV-22, AV-23, AV-01+02+03+04 (as AV-08), AV-28, AV-30,
AV-34+35, AV-41, AV-43, then AV-10, AV-17 (the two big signal-path builds), then AV-26/27.

---

## 3. A. CRT

Shared sources **[V]**: libretro CRT shader catalogue (gametechwiki / docs.libretro.com: crt-geom (cgwg), crt-royale
(TroggleMonkey, dozens of options, "very demanding"), crt-lottes (from Timothy Lottes' "FixingPixelArt", Shadertoy
MsjXzh, **CC0** per the Godot port), crt-easymode (+Halation), crt-guest-advanced, crt-hyllian, crt-aperture, crt-pi,
zfast-crt (very fast), crt-potato (LUT stand-in for royale), GritsScanlines (LUT dynamic beam width), crt-mattias /
NewPixie ("crawling" scanlines), vector-glow, vt220 (bezel with dynamic reflections), meta-crt (raymarched, "very, very
demanding": skip), mame-hlsl, crt-yo6-kv-m14208b (a specific Trinitron built from data). Licences were NOT stated on
those pages: the slang-shaders repo carries per-file headers; most are GPL-family **[M]**, so port the maths, not code.
Shadertoy sources default to CC BY-NC-SA 3.0 unless a file says otherwise **[M]**. Shadow masks need ~4K to resolve
without aliasing; aperture grilles are easier at 1080p and only curve horizontally **[V]**.

### AV-01 CRT Mask
- Look: RGB phosphor structure. Trinitron = vertical R/G/B stripes with 1-2 thin horizontal damper wires **[M]**; slot
  mask = staggered slots (most consumer TVs); shadow mask = delta-triad dots (older monitors); LED sub-pixel = 3-in-1.
  Refs: JZB_Lofi_CRT (Aperture/Slot/Shadow), greenrhyno 68947, crt-aperture, crt-royale.
- Technique: per output pixel compute mask coordinate `m = fract(x / period)`; weights `w_rgb` from smooth triangle/cosine
  per sub-pixel (not hard stripes: avoids aliasing); slot = offset every other row by half a period with a dark gap at
  row boundary; dots = hex lattice with distance falloff. Multiply `rgb *= mix(1, w_rgb*3, strength)`, then gain back by
  `1/avg(w)` (energy compensation) so the screen doesn't go dark. Optional band-limit: fade mask strength as period
  approaches 2 px (anti-moire).
- TD: one GLSL TOP, mono pass, no neighbours. Cheapest module. Inputs: image, optional `Pitch` Null from AV-41.
- Pars: Mask (Off/Aperture/Slot/Shadow/LED), Period px 2-24 (default 6), Period in canvas % alt, Strength 0-1, Gap 0-1,
  Damper wires on/off + count 1-3, Subpixel Softness 0-1, Gain Comp on/off, LED Safe (clamp >= 3 px, advise >= 6).
- Presets: Trinitron PVM, Consumer slot, 80s shadow, Arcade fine, Monochrome (no mask), LED-wall safe (period 6-8).
- Perf 0.2-0.3 ms. S. Pri 1.

### AV-02 CRT Beam, Scanlines, Interlace
- Look: bright scanlines that widen with brightness and leave dark gaps for dark parts (crt-geom, Lottes, royale).
- Technique: virtual line count `L` (240/288/480/576/720; default 480). For output y: `pos = fract(y*L) - 0.5`; beam
  profile `exp(-pos^2 / (2 sigma^2))` with `sigma = mix(sigmaMin, sigmaMax, luma^gamma)` (beam widens with level; Lottes uses
  `exp2(hard*pos*pos)` with separate `hardScan`/`hardPix`) **[V partial: parameter names from the Godot port]**. Sample
  the two nearest source lines (above/below) and weight by profile, so an upscale from L lines is a true reconstruction
  and not box-filtered. Linear light: convert to linear before weighting, back after (gamma 2.4 in, display gamma out).
  Interlace: `Field` Even/Odd/Alternate; each field draws only its lines with half-line offset; Alternate flips every
  frame at 60 fps (30 fps picture with line flicker); "Deinterlace" = off shows combing (AV-14).
- TD: GLSL TOP; texelFetch of the two rows; if source is not at L lines, a Resolution TOP (nearest) before. Compute mode.
- Pars: Lines 120-1080, Beam Min/Max width 0.1-0.9, Hardness -2..-16 (Lottes style), Gamma In 1.8-2.6, Interlace
  Off/Even/Odd/Alt, Field Offset, Scanline Opacity, Line Axis, Dynamic Beam on/off, Crawl (NewPixie-style, speed -2..2).
- Presets: PVM sharp, Consumer soft, 15 kHz arcade (Lottes), 480i alternate, 240p console, Crawling lines.
- Inputs: Amount, field phase, beat (a flash widens beams: "overdrive").
- Perf 0.3-0.6 ms. M. Pri 1.

### AV-03 CRT Geometry
- Look: bulged glass, rounded corners, overscan, vignette, glass reflection/spec, bezel, optional room reflection.
- Technique: cgwg crt-geom: ray-sphere intersection of screen with radius `R` (default ~2.0) and viewer distance `d` (~1.5),
  tilt angle, corner size ~0.03 and smoothness **[M]**; simpler `uv' = uv*(1 + k*r^2)` barrel with UV clamp to black border.
  Corner mask via rounded-box SDF (smoothstep). Vignette `1 - v*r^2`. Spec highlight = soft ellipse + window-reflection
  texture input (vt220-style dynamic reflection: blurred copy of the *screen itself* mirrored faintly).
- TD: one GLSL TOP (single-sample warp) or Lens Distort TOP (native) for the pure barrel. Border: Black / Transparent
  (matches JZB_Lofi_CRT Border).
- Pars: Curvature X/Y 0-1 (aperture grille = X only), Radius, Distance, Tilt, Corner 0-1, Overscan 0-10%, Vignette,
  Glass Spec, Reflection (Image input) amount, Bezel (Off/Plastic/Wood-grain image input), Border.
- Perf 0.2 ms. S. Pri 1.

### AV-04 CRT Glow (bloom + halation)
- Look: light bleeding around bright parts, lifted blacks from glass scatter (halation, crt-easymode-Halation).
- Technique: dual-filter mip pyramid (the same one StageLab's `BlurPyramid.h` uses): down 1/2..1/32 with 13-tap, up with
  tent, sum with weights; halation = very wide low-gain level (energy conserving). Threshold + soft knee optional.
- TD: native Blur TOPs on Resolution TOPs at 1/4, 1/8, 1/16 plus Add/Composite (no GLSL, avoids T-46 entirely), or one
  compute downsample chain. Build with native ops first.
- Pars: Threshold 0-1, Knee, Radius (3 bands) 0-1 each, Gain 0-2, Halation 0-1, Tint (warm), Mode Add/Screen.
- Perf 0.4-0.8 ms (3 bands at 1/4..1/16). S. Pri 1.

### AV-05 CRT Phosphor persistence + rolling beam
- Look: motion trails with per-channel colour (red/green/blue decay differently: green fast, red lingers **[M]**), plus
  the CRT's rolling bright band (only a strip of the screen is lit at any instant).
- Technique A (cheap, persistence): Feedback TOP: `out = max(in, prev * decay_rgb)`; `decay_rgb` per channel (0.0-0.98 at
  60 fps; ms to frames conversion in the par label). Technique B (Blur Busters-style rolling scan): for each frame
  compute `beam(y,t)` = sharp front + exponential tail along y relative to a beam position that sweeps top->bottom in
  one frame period (needs sub-frame time: render N=4-8 sub-steps by weighting only, since we don't have sub-frame
  video: use the same frame with window weights; the visible effect on camera/LED is a rolling bar). Optional long-tail P7/P1
  style: very slow decay mono tail (see AV-09).
- TD: Feedback TOP + one GLSL TOP for decay and tail; format 16F so slow decays don't band.
- Pars: Persistence R/G/B 0-0.98, Tail Length, Rolling Beam on/off + Bar Speed + Bar Width, Gamma-correct decay.
- Perf 0.3-0.5 ms. M. Pri 1.

### AV-06 CRT Convergence + focus
- Technique: R/G/B sampled at offsets that grow with radius from centre (`offs = k*r^2*dir`, plus static drift); focus blur
  grows toward corners (2-3 tap radial blur by distance). Static misconvergence noise via a low-frequency noise map.
- Pars: Convergence X/Y px, Edge Growth, Focus Falloff, Blotches (colour patches, same as the FFGL "Randomness"), Seed.
- Perf 0.2-0.4 ms. S. Pri 2.

### AV-07 CRT Faults
- Items (each its own toggle/trigger, all seedable): V-hold roll with blanking bar (JZB_Lofi_CRT Roll); H-hold tear
  (per-line horizontal offset step); H-sync jitter (white noise 0-3 px per line); flyback bar and "S"-wobble from bad
  deflection; **degauss** (purple/green swirl from a magnetised mask: radial colour wobble that decays ~2 s; JZB
  Degauss button) ; **power-off collapse** (picture squeezes to a bright horizontal line then a dot that fades, ~0.3-0.5 s) and
  **power-on warm-up** (dim, small, expanding); raster breathing (picture size varies with brightness: high-voltage
  sag); mains hum bars (soft dark bands rolling at beat of 50/60 Hz vs 59.94); static buildup/arcing flashes.
- TD: one GLSL TOP with a mode stack, driven by Pulse pars and an envelope (Lag/Speed CHOP). Timer CHOP for collapse.
- Perf 0.2-0.4 ms. M. Pri 1 (power-off collapse is a perfect scene-change transition; degauss as a hit).

### AV-08 CRT Monitor macro
- All of AV-01..07 in one COMP with a `Model` menu: PVM-2030 (sharp aperture, scanline hard), Trinitron KV-27 (damper
  wires, slight bow), consumer 80s (shadow, curved both axes, soft), arcade 15 kHz, Mattel/portable B/W, Apple IIc monitor
  (green), Commodore 1084S, Vectrex (see AV-31), Sony Watchman-class (tiny curved, dim), broadcast monitor w/ tally, TV in
  a room (Reflection input), "Dead set" (heavy faults). Preset JSONs in `presets/`; ranges per control from the section
  above. Quality menu: Low (no glow, mask+lines+geo), Mid, High.
- Perf: Low ~0.7 ms, High ~2.5 ms. M. Pri 1. This is the PF26-useful CRT: same controls as the Arena plugin, so a look
  dialled in TD translates.

### AV-09 Phosphor terminal
- Look: green P1 / amber P3 / white P4 terminal (VT220, Apple II, DEC), thick glow around glyphs, slow decay, burn-in ghost,
  flicker, scanlines.
- Technique: luma -> tinted mono (`P1 #33ff33`-like, amber, white-blue), decay feedback (0.9-0.97), a very slow accumulator
  for burn-in (rate 1e-3, only for pixels bright > threshold, never clears unless Reset), AV-04 glow, AV-02 lines.
- Pars: Phosphor (Green/Amber/White/Blue-white/Custom), Decay, Burn-in Rate/Reset, Glow, Flicker, Curvature.
- Perf 0.4-0.6 ms. S. Pri 2. Pairs with AV-39 text-mode and the lyrics_feed COMP.

## 4. B. Composite / broadcast

### AV-10 NTSC composite encode/decode
- Look: rainbow cross-colour on fine stripes, dot crawl on coloured edges, soft chroma, ringing, hanging dots; "real"
  composite rather than a blur. Refs **[V]**: LMP88959 `NTSC-CRT` (any use, attribution appreciated; encodes and decodes a
  bandlimited luma + chroma signal with real sync, interlace, accurate dot crawl, NES mode), `ntsc-rs`
  (Rust; from composite-video-simulator -> zhuker/ntsc -> ntscQT; licence listed as ISC/MIT files but unclear which
  applies, check before reuse), `composite-video-simulator` (GPL-2.0, slow, accurate by design). Also snes_ntsc/nes_ntsc
  (Blargg, LGPL) **[M]**.
- Technique (maths **[M]**, standard NTSC): line frequency 15.734 kHz, `fsc = 3.579545 MHz = 227.5 cycles/line`, so
  subcarrier phase advances 180 deg per line and the dot-crawl pattern repeats every 2 frames (525 lines is odd). RGB->YIQ
  (`Y=.299R+.587G+.114B`, `I=.596R-.274G-.322B`, `Q=.211R-.523G+.312B`). Encode at virtual rate of `4*fsc` (910 samples per
  line, ~754 active): `C = I*cos(w t + phi) + Q*sin(w t + phi)`, `composite = Y + C`, with `phi = 180deg*line + 180deg*frame`
  (+ field). Decode: separate Y/C (modes: notch filter / 1-line comb / 2-line comb / none = full cross-colour), demodulate
  `I' = 2*C*cos`, `Q' = 2*C*sin`, low-pass I to ~1.3 MHz and Q to ~0.4-0.6 MHz, Y to ~4.2 MHz **[M]**. The cross-colour/dot
  crawl arise automatically from imperfect separation. Add: sharpness peaking (overshoot -> ringing), hue/sat, chroma
  phase error (tint), additive noise on the composite.
- TD: **pass 1** (compute GLSL) encode to a composite texture at `Signal Res` (R32F mono, width = samples per line, height =
  lines). **Pass 2** (compute) decode: per output pixel loop N=24-32 taps along the line from the composite texture (FIR
  low-pass windows precomputed as constants: Y, I, Q kernels), `texelFetch`, no neighbours in Y except the comb taps (1-2
  lines). **Pass 3** reconstruct/upsample to 1080x1920 (linear or Lanczos, from AV-02). Phase uses `field` index (shared
  clock). No Optical Flow, nothing needing codecs.
- Pars: Standard (NTSC/PAL/Custom), Signal Res (samples per line 320-910; lines 240/480/576), Y Bandwidth 2-6 MHz, I BW
  0.6-2.0, Q BW 0.2-1.2, Separation (Notch/Comb1/Comb2/None), Cross-colour 0-1, Dot Crawl Speed (0 freezes, 1 real),
  Peaking 0-1, Hue -180..180, Saturation 0-2, Chroma Phase Error deg, Noise 0-1 (+colour), Signal Gain.
- Presets: Clean broadcast, Cheap TV (None), S-Video, Dot-crawl demo (high-frequency stripes), Composite 1980s console.
- Perf: pass 1 ~0.2 ms; pass 2 (32 taps, 2.07 MP output) ~0.8-1.5 ms unless decode is done at virtual res (910x480 =
  0.44 MP, ~0.25 ms) then upsampled: do that, expect ~0.6-1.0 ms total. L (first of its kind: needs numpy reference
  tests like BN_fluid2d: encode/decode of a colour-bar and a zone plate against a Python model).
- Pri 1 (it is the signal-correct basis for AV-11/12/13/17).

### AV-11 PAL / SECAM / S-Video / RF / Component variants
- PAL: `fsc = 4.43361875 MHz`, 625 lines, 50 fields **[M]**; V-phase alternates each line, so chroma errors cancel against
  the neighbouring line with a delay line (colours hold, resolution loss; without it: "Hanover bars", visible alternate-line
  brightness stripes when phase is wrong). Mode in AV-10: PAL-D (delay-line averaging), PAL-S (simple, with Hanover bars).
- SECAM: FM chroma, one colour difference per line alternately (Dr/Db): look = vertical colour bleed with half the
  vertical colour resolution and dot-free but "fire" noise on edges **[M]**. Emulate as sequential colour per line + horizontal
  low-pass.
- S-Video: no Y/C mixing -> no cross-colour; component: ideal. These are preset toggles for the same module.
- Cost: +0.2 ms. M. Pri 2.

### AV-12 Artifact-colour machines
- Look: colours that exist only because of composite decoding: CGA 640x200 on a composite monitor gives 16 colours from
  a 1-bit stream; Apple II hi-res gives violet/green/blue/orange from bit patterns; NES 2C02 outputs a square-wave
  with 12 phases per colour (LMP88959's NES mode) **[V]**; Atari 2600 colours; the "waterfall rainbow" from dither on NTSC
  (`CRT_CHROMA_PATTERN` 0 in NTSC-CRT **[V]**).
- Technique: AV-10 in *Raw* mode: skip RGB->YIQ; the source texture is treated as a 1-bit/ntsc-level pixel stream clocked
  at the machine's dot rate (14.318 MHz for CGA/Apple II; 21.477/4 MHz for NES) and then decoded. Needs a "Machine Pixel
  Grid" (virtual res, nearest) in front. Ordered Bayer dither (AV-35) then gives the classic artefact rainbow.
- Presets: CGA composite 160x100/16, Apple II hi-res, NES, SNES composite, ZX81-ish, "Atari 2600 stripes".
- Perf +0.2 ms over AV-10. M. Pri 2.

### AV-13 RF reception
- Items: multipath ghost (delayed attenuated copy 2-60 px right, optionally inverted/ coloured), snow (white noise with
  streaks: noise filtered horizontally, luma-dependent), sound-carrier interference (herringbone diagonal stripes,
  frequency from audio level: **audio effector**), channel-change static flash with vertical roll, weak-signal sync loss
  (sync instability -> picture tearing, AV-07 H-tear), AGC pumping (gain breathes), colour killer (chroma off below
  threshold SNR). All driven by one `Signal Quality` 0-1 plus per-item sliders.
- TD: GLSL TOP with noise from a shared noise TOP. Perf 0.4-0.7 ms. M. Pri 2.

### AV-14 Interlace combing + bob/weave
- True 60i: odd rows from frame n, even rows from frame n-1 via Cache TOP (native), so moving edges show combing; modes:
  Weave (combs), Bob (line-double a single field with half-line offset), Blend, Off. Perf 0.2 ms. S. Pri 2.

### AV-15 Plasma display (dynamic false contour)
- Look: coloured edges / false contours on moving gradients because 8-bit levels are built from time-sliced sub-fields
  (e.g. weights 1,2,4,8,16,32,64,128) and the eye tracks motion **[M]**.
- Technique: decompose each channel into sub-fields; render sub-fields with their sub-frame time offsets displaced by the
  global motion estimate. No optical flow here (T-18): use frame-difference direction or a user motion vector (Null/CHOP);
  fallback: panel-pan synthetic motion. Perf 0.5 ms. M. Pri 3.

### AV-16 Broadcast cards + OSD
- Philips PM5544 (Europe), EBU colour bars, SMPTE RP219/ECR1, Indian Head, "Bars and tone" (audio through the TD audio
  rule: out = speakers), blue "NO SIGNAL", "NO INPUT", VCR "PLAY >", "REC ●", "PAUSE", "SP/LP", counters, `CH 03`,
  timestamp "OCT 24 2026 5:30 PM" (12 h, user rule), camcorder battery icon. Built from native ops + Text TOP (OSD font:
  a VCR/pixel font under OFL). Extends TP_test_pattern. Perf 0.1 ms. S. Pri 2.

## 5. C. Tape + camera

### AV-17 VHS tape
- Look/refs: JZB_Lofi_VHS v2 (the look reference; controls Bleed, Wobble, Tracking, Glitch, Lines, Sharpen, Chroma Shift,
  Noise, Dropouts), ntsc-rs / composite-video-simulator stages **[V names only]**, elekktronaut VHS animations (B_visual).
- Facts **[M]**: VHS luma is FM (carrier 3.4 MHz sync tip to 4.4 MHz white), luma bandwidth ~3 MHz (~240 lines); colour-under
  at 629 kHz (NTSC) with ~0.4 MHz bandwidth, so chroma is very soft horizontally and slightly misregistered; the drum has 2
  heads (30 rev/s NTSC) and the head switch lands a few lines before vertical sync, giving the bottom-of-frame tear; time-base
  error shows as per-line jitter and "flagging" (top lines bend); dropouts are short bright/dark dashes, often filled by the
  previous line (dropout compensation); SP/LP/EP lower SNR and bandwidth; copies lose bandwidth each generation.
- Technique: sits on top of AV-10 (YIQ domain, not RGB): 1) Y low-pass 3 MHz + pre-emphasis ringing (halo on edges); 2)
  chroma: I/Q low-pass 0.4 MHz, delay by `Chroma Shift` px (to the right only), add chroma noise and phase wobble
  (rainbow edges); 3) time-base: per-line horizontal offset = low-frequency noise (flagging weighted to the top 5-10 %)
  + per-line jitter 0.0-0.5 virtual px; 4) tracking band: a band moving vertically (speed, width) where offset is large and
  noise bursts, plus a bottom head-switch zone of 6-8 lines with big horizontal skew and noise; 5) dropouts: a
  per-frame random list (hash) of (line, x, length 4-80 px) painted white/black, `Dropout Compensation` replaces with the
  previous line; 6) luma noise streaks (horizontally filtered); 7) generations 1-3 (repeat 1-3 with extra loss);
  8) crease: diagonal wavy band (S-shaped offset travelling).
- TD: AV-10 core + 1 compute pass for time-base/band/dropouts/noise; dropout list from a Script CHOP or from a hash in
  shader (cheaper). Virtual lines 240/480/576 as in the plugin.
- Pars: Amount, Tape Speed (SP/LP/EP), Generations 1-3, Luma BW, Chroma BW, Chroma Shift 0-8, Sharpen 0-1, Wobble 0-1,
  Flagging 0-1, Tracking 0-1 (+ Band Pos/Speed/Width), Head Switch lines 0-12, Dropouts 0-1 (+Length, Compensation),
  Noise Luma/Chroma, Crease, Lines 240/480/576, Glitch (pulse), Seed, Line Axis.
- Presets: Fresh rental, 90s family tape (soft, slight shift), Worn, Heavily dubbed, LP bootleg, Glitch hit.
- Inputs: Glitch trigger (beat), Tracking level (audio low band), Amount (envelope).
- Perf: ~1.2-2.2 ms with AV-10; ~0.6 ms as the cheap "YIQ-lite" variant (no comb/notch, as in the plugin). L. Pri 1.

### AV-18 VHS transport
- Pause (still field with a rolling noise bar and vertical jitter), FF/REW shuttle (horizontal noise bars scrolling, picture
  doubled lines), slow-mo with field-duplicate stepping, tape stop (picture slows, colours lose lock, wobble up, snaps to
  noise), frame freeze with head-switch band, "tape eat" (picture stretches vertically and smears). Uses Cache/Time
  Machine TOP (native) as frame store. Perf 0.4 ms. M. Pri 2. Great as live transitions on beats.

### AV-19 Camcorder / CCD / DV
- Items: **vertical smear** (bright highlights streak up/down a column: column prefix-sum of values above threshold,
  blurred, added; easy), CCD/CMOS bloom, auto-exposure pumping (level follows scene average via Analyze TOP, with lag),
  focus hunting (breathing blur), white-balance drift, 4:3 pillarbox, interlace combing (AV-14), date stamp/REC/battery
  OSD (AV-16), zebra, DV macroblock errors (8x8 block repeat / green-pink blocks for a few frames: this overlaps the
  datamosh research; keep a block-corruption op only, no codec), MiniDV tape dropout. Perf 0.5-0.9 ms. M. Pri 2.

### AV-19b Security cam, night vision, thermal, rolling shutter
- CCTV: time-lapse multiplex (1-5 fps hold), 4-cam quad, grey + 8-bit compression blocks, timestamp, IR LED vignette.
  Night vision: green (P43-like phosphor) mono + gain noise + bloom + "eye shine" via threshold; image-intensifier
  halo (bright source ring). Thermal: ironbow/white-hot/rainbow LUTs (palette_map covers LUT; add noise-equivalent
  blur + isotherm lines). Rolling shutter: row r samples frame `t - r/H * shutter` via Time Machine/Cache TOP
  (skew, jello); global vs rolling toggle. Perf 0.3-0.8 ms. S-M. Pri 2.

## 6. D. Video synthesizer family

Background **[V unless marked]**: Sandin Image Processor (Dan Sandin, 1971-74, modular, "Moog for video"): module types
oscillator, camera input, adder/multiplier, comparator, differentiator (edge emphasiser), amplitude classifier, function
generator, colour encoder, plus sync and NTSC interface (Wikipedia). Paik/Abe synthesizer (WGBH 1969): phase-shifted
subcarrier per input gave colour from grey; video amplifiers rolling off at high amplitude shaped the look (Cornell/SIGGRAPH
history pages). LZX: Visual Cortex (all-in-one: sync, video in/out, mixing, waveform/shape generation), Chromagnon
(colorizer, chroma keyer, quad figure generation, raster for lasers/XY displays), Cadet-era modules listed by ModularGrid:
Video Sync Generator, Color Video Encoder, Video Waveform Generator, Triple Video Fader & Key Generator, Video
Blending Matrix, Triple Video Multimode Filter, Video Logic, Video Divisions, Color Time Base Corrector, Pre-encoder
Expander. **Hearn Videowarp: not found in this search; I cannot describe it from a source. Ask the user for a reference
(link/video) before building anything named after it; the closest buildable family is AV-26/AV-29 (scan warp).** Other
lineage worth a later pass **[M]**: Stephen Beck Direct Video Synthesizer, Vasulkas' Rutt/Etra work, Eric Siegel
Processing Chrominance Synthesizer, Scanimate (Computer Image Corp).

### AV-20 Video-synth patchbay `AN_synth`
- Concept: a rack of module slots (like the PX stack) on a shared **signal bus** of N float textures (default 6 buses
  named A-F, mono or RGB), each module reads 1-3 buses and writes one. Routing by menu per input (A..F, Camera, Clip, Audio
  scope image). Modules = AV-21..25, 27, 29 + feedback + AV-30 scope. Like analog gear, any output can modulate any input
  (cross-modulation), which gives the unplanned looks.
- Build: one parent COMP with a Python-driven slot list (add/remove/reorder, bypass, solo), each slot a child COMP with
  in/out; bus textures = Null TOPs; `Hold` bus implements a one-frame delay so loops don't create dependency cycles
  (feedback via Feedback TOP). Patch recall = JSON preset of slot order + routing.
- Perf: sum of active modules (2-6 typical, 1-2.5 ms total). L. Pri 1 (this is the platform; AV-21..29 are its modules but
  each also ships standalone).

### AV-21 Oscillators + shapes
- Look: barber-pole stripes, concentric rings, rotating spirals, checker/diamond fields; H/V-locked oscillators give fixed
  stripe counts, free-run gives drift (diagonal skew).
- Technique: `phase = f_x*x + f_y*y + f_r*r + f_a*atan2 + t*drift`; waveform Sine/Tri/Saw/Square/Pulse(width)/Staircase
  (N steps); FM `phase += k * modulator`; sync (reset phase on bus-edge); output float 0-1 (or bipolar). Shapes
  (Chromagnon-style): rect/ellipse/diamond/ring with soft edges (key-ready) and quad figures from 4 corners.
- Pars: Freq X/Y/Radial/Angular 0-200 cycles per screen, Lock H/V/Free, Drift -2..2, Waveform, Pulse Width, Steps 2-64,
  FM Amount + source, Phase, Soft Edge, Shape + size + rotation.
- Inputs: audio band -> frequency/FM; MIDI. Perf 0.2-0.4 ms. M. Pri 1.

### AV-22 Colorizer + overflow modes
- Look: grey levels turned into saturated, banded colour by three offset functions (Paik/Abe phase colour; Sandin colour
  encoder; Chromagnon colorizer); solarisation when levels overflow.
- Technique: `rgb_c = f(k_c * luma + phi_c)` with `f` = triangle/sine/saw/ramp function, per-channel gain `k_c` and phase
  `phi_c`; overflow Clip/Wrap(`fract`)/Fold(`abs(fract(x/2)*2-1)`)/Mirror; cyclic hue mode maps luma to hue (constant sat).
  This complements FX_palette_map (arbitrary palettes) by being an *analog function* palette, animatable by LFOs.
- Pars: Gain R/G/B 0-8, Phase R/G/B 0-1, Function, Overflow, Mode (Per-channel / Hue-cycle), Mix, Invert, Drift.
- Presets: Paik phase, Sandin sunset, solarize, neon fold, acid wrap. Perf 0.15 ms. S. Pri 1.

### AV-23 Amplitude classifier + contour bands
- Technique: quantise luma into N bands with soft edges (`smoothstep` around thresholds) and assign each band a colour/
  opacity; iso-luminance lines = bands' edges drawn with width w (derivative of luma: `fwidth`-like via neighbour
  samples); animate thresholds with an LFO so contours flow across the picture ("topographic" video). Sandin's amplitude
  classifier and differentiator are the references **[V names]**.
- Pars: Bands 2-32, Softness, Line Width, Line Colour, Band Palette (ramp input), Offset (animated), Edge Only.
- Perf 0.2 ms. S. Pri 1.

### AV-24 Keyers + blend matrix + logic
- Luma key (threshold, softness, invert, clip), chroma key (Chroma Key TOP native, or hue-distance in Oklab), key generator
  from a shape (AV-21) with fade, 4x4 blend matrix (each output = weighted sum of up to 4 inputs; weights are 16 pars
  or a table DAT), logic ops on thresholded signals (AND/OR/XOR, min/max, difference, "if A > B"), wipes (Cadet-like
  fader + key gen). Cost 0.2-0.5 ms. S-M. Pri 1.

### AV-25 Video filters (analog horizontal)
- Look: smear to the right, ghost echoes and ringing streaks around edges, emphasis lines (what a resonant filter does to
  a video line).
- Technique: per-line 1D filter. Causal exponential smear = FIR with one-sided kernel `e^{-n/tau}`, 48 taps. High-pass =
  `x - LP(x)`. Band-pass with resonance: damped cosine kernel `e^{-n/tau} cos(w n)`, ringing streaks. Differentiator =
  `x[n+1]-x[n-1]` with gain/sign display (grey-centred). True IIR needs sequential per-row thread: row-parallel compute
  with a serial loop over 1080/1920 samples; treat as optional "Exact" mode, test on scratch TD (T-83), it may be slow on
  MoltenVK (1920 threads only).
- Pars: Mode LP/HP/BP/Notch/Diff, Cutoff (cycles per screen), Resonance 0-1, Tau, Axis, Channels (Luma only/All), Mix.
- Perf 0.5-1.0 ms (48 taps). M. Pri 2.

### AV-26 Rutt/Etra scan processor
- Look: video as a stack of glowing deflected scan lines, picture brightness pushing lines sideways/up (not only 3D
  relief) and rotating the raster; 1970s Rutt/Etra (Bill Etra / Steve Rutt), Vasulka tapes. Refs **[V]**: Vade v002/Cycling '74
  (vertex attributes on GPU), Felix Turner's Rutt-Etra-Izer (WebGL; z from brightness), Akascape Shadertoy DdXfRj,
  derivative forum thread (do the displacement in GLSL, not TOP->CHOP, which is CPU-bound), Anton Marini write-up
  (separate textures for geometry and colour).
- Existing: td-port `JZBN_RuttLines` (GLSL TOP-only ribbons; offline-gate only, no TD verification). Extend, not duplicate.
- Technique (new vs ribbons): the unit adds video-derived voltages to the CRT **deflection amplifiers**:
  `x' = x + kx*s1(u,v)`, `y' = y + ky*s2(u,v)`, `z (brightness)` stays the source. So: (a) geometry: Grid of N lines x M
  samples; vertex shader (GLSL MAT, single pass, no T-46 exposure) samples signal textures s1/s2/colour, then global
  affine "raster" rotation/scale/shear applied after deflection; (b) draw as additive line strips or thin quads with a
  Gaussian profile; (c) glow via AV-04 + phosphor via AV-05; (d) optional perspective camera for the relief look. Using
  the same vertex positions with colour from a second texture gives Marini's separation of geometry and colour.
- TD: Geometry COMP (Grid SOP lines) + GLSL MAT + Render TOP, Add blend; instancing optional. Mirrored to the CHOP-free path:
  everything on GPU.
- Pars: Lines 16-512, Samples 64-1024, Line Width px, Deflect X/Y gain -2..2 + source (Luma, R, G, B, Bus, Audio), Z gain,
  Raster Rotation/Scale/Shear, Camera Pitch/Yaw/Persp, Colour Source (Video/Mono/Ramp), Glow, Persistence, Blend (Add/Over), Seed.
- Presets: Classic relief, Sideways scan, Face wire, Audio spectrum lines, Rotating raster.
- Perf: 256x512 samples = 131k vertices ~1.0-2.0 ms (cap like RuttLines at 131072). M-L. Pri 1.

### AV-27 Scanimate flying-logo look
- Look: 1970s TV graphics: a high-contrast logo/text smeared into glowing, banded, colourised streamers that fly, scale,
  and warp (Computer Image Corp. Scanimate) **[M]**. Instantly legible as "retro TV opening".
- Technique: mono high-contrast source (logo/text) -> analog deflection warp (sine/ramp/audio animating X/Y gain and
  rotation, AV-29 field) -> long-tail feedback trails (decay 0.9-0.97 with blur and slight zoom, AV-28) -> colorizer on
  the *trail age* (age = feedback intensity -> gradient 3-5 stops, AV-22) -> bloom (AV-04) -> optional scanlines.
  Fill: also pass the logo through AV-23 contour bands for the "neon outline layers" look.
- PF26 note: PRISM logo must be the full-colour variant elsewhere (user rule: colourful logos); here the colour comes from
  the colorizer ramp, so use PRISM brand-ramp colours, and keep the logo whole (names/words stay intact rule): no
  splitting the word; warp amount is capped so the logo stays readable at its settle keyframes.
- Pars: Logo In, Settle (0 = animated, 1 = clean logo), Warp Amount/Speed/Type, Trail Decay/Zoom/Blur, Colour Ramp, Glow, Lines.
- Perf 0.8-1.5 ms. M. Pri 1 (strong for act intros/outros).

### AV-28 Video feedback (camera at monitor)
- Look: infinite tunnel/spiral/cellular nebulae made by pointing a camera at its own monitor (Crutchfield "Space-time
  dynamics in video feedback" **[M]**; Phil Morton, Vasulka). Each loop passes through: lens (zoom, rotate, shift,
  distortion), camera (gain/auto-gain, noise, blur), CRT (gamma ~2.4, mask moire, phosphor), mixer (luma-keyed with new
  input).
- Technique: Feedback TOP -> Transform TOP (zoom 0.98-1.03, rotate +-3 deg, shift) -> Lens Distort -> Level/gamma (S-curve for
  saturation) -> HSV Adjust (hue shift per generation, e.g. 0.5-4 deg) -> Blur (1-2 px) -> Composite over new input with
  luma-key threshold -> back. Latency: 1-3 frames via Cache TOP (camera-monitor delay); inside-loop AV-01 mask creates
  moire. All native ops, no GLSL, so no T-46 risk, ideal first build. `ScreenGrab TOP` exists for a literal screen
  loop but is unsafe/unneeded.
- Pars: Zoom, Rotate, Shift X/Y, Lens K, Hue Shift/gen, Gain, Gamma, Blur, Key Threshold/Soft, Delay frames 0-3, Mask In-Loop
  on/off, Inject (how much new image enters), Clear (pulse).
- Presets: Crutchfield spiral, Tunnel, Cells, Flame, Kaleido (with a Mirror/Tile in loop), Infinite hall.
- Inputs: audio level -> Inject/Gain (beat flash re-seeds the loop), effector Null -> Shift. Perf 0.6-1.2 ms. M. Pri 1.
  Safety: gain > 1 in a loop can strobe: clamp loop gain and flash rate (show-safe rule; use FX_strobe limits).

### AV-29 Paik magnet / wobbulator
- Look: a magnet near a CRT bends the raster into dipole swirls (Paik's "Magnet TV", 1965) and the Sandin/Paik
  "wobbulator" ripples the whole raster.
- Technique: displacement field from 1-4 dipole sources (position from effector Nulls/audio): `d(p) = k * (rot90(p-c)/|p-c|^3)`
  clamp; plus raster ripple `y += A sin(2 pi f x + phi)`. Pars: Magnets 1-4 (x, y, strength, softness), Ripple A/f/phi,
  Falloff, Mix, Wrap/Mirror. Perf 0.2 ms. S. Pri 2.

## 7. E. Scopes + vector displays

### AV-30 Oscilloscope XY (audio)
- Look: stereo audio as X/Y: Lissajous knots, "oscilloscope music" (Jerobeam Fenderson: drawings from L/R signals
  played through a scope in XY mode, DC-coupled **[V]**). Beam brightness on real scopes is fixed; the visible glow
  comes from dwell time (slow beam = bright) **[V partly]**. Refs: Osci Music Player; Osci-render (jameshball, GPL-3 **[M]**);
  woscope (WebGL, m1el **[M]**); kamindustries `td-scope` (MIT, TD 099 era); uisato "Oscilloscopes Everywhere v1.2" (29 ways;
  Patreon, no file reachable; recorded only).
- Technique: Audio Device In / Audio File In CHOP (L, R) -> Resample CHOP (cubic, 4-16x oversample to ~4096-16384 points per
  frame) -> instance positions. Draw each segment P_i->P_{i+1} as a quad whose fragment intensity is
  `I = exp(-d^2/(2 s^2)) * (dt/(segmentLength + eps))` (brightness inversely proportional to beam speed = energy per area),
  Add blend, then glow (AV-04) and phosphor decay (AV-05, P31-like short green or P7 long). Z-modulation (blanking) from a
  third channel or from beat. Graticule overlay (10x8 divisions), bezel, beam noise, focus/astigmatism blur.
- TD: Geometry COMP instancing from CHOP channels (tx, ty, plus prev-sample channels from a Delay/Shift CHOP), GLSL MAT for
  the segment quad; avoid TOP<->CHOP CPU round trips (forum lesson from AV-26 sources). 735-800 samples per frame at
  44.1/48 kHz and 60 fps: oversample so lines look continuous.
- Pars: Source (Mic/File/Test), Gain X/Y, Rotate 45 (goniometer), Swap, Beam Width, Intensity, Dwell Boost, Z-mod,
  Persistence (P31/P7/custom), Glow, Graticule on/off, Noise, Color (green/amber/white/RGB by frequency band), Trace
  History 1-8 frames.
- Audio rule: out = built-in speakers, in = default input (mic hears the Mac); never mic->speaker (memory rule).
- Perf 0.5-1.0 ms for 8k segments. M. Pri 1.

### AV-31 Vector display (Vectrex / Asteroids / Tempest)
- Look: bright thin strokes with blob at vertices (beam dwell), slight overshoot at corners, flicker, ghost trails, no
  scanlines (libretro `vector-glow` exists as a post-effect **[V]**).
- Source of strokes: LP_laser_path COMP already produces an optimised path with a galvo-lag glow preview; AV-31 reuses
  that path as the stroke list (instancing like AV-30) and re-skins it: colour mono/Vectrex white-blue, overlay colours
  cellophane (Vectrex used coloured overlays), vertex blobs, flicker 20-40 Hz, optional 3D wireframe (Geometry SOP edges).
- Pars: Stroke Width, Vertex Blob, Overshoot, Flicker, Overlay (None/Cellophane image), Persistence, Glow, Wireframe 3D.
- Perf 0.6-1.0 ms. M. Pri 2.

### AV-32 Goniometer, harmonograph, Lissajous generators
- Generators (CHOP): `x = sin(a t + p1) e^{-d1 t}`, `y = sin(b t + p2) e^{-d2 t}` (harmonograph, damped), rose curves, spirograph,
  Lissajous knots with a:b ratios locked to the beat (audio-quantised); goniometer = M/S rotation with correlation meter
  (red when out of phase, practical for audio checks). Feeds AV-30. Perf 0.3 ms. S. Pri 2.

### AV-33 Video scopes
- Waveform (luma by column), RGB parade, vectorscope (U/V with skin-tone line and 75 % colour-bar targets), histogram,
  false colour, zebra, clipping warnings; useful for checking LED-wall levels and for the show operator.
- Technique: sample a 128x128 (or 256x144) downscale into points; instance 16-32k point sprites at scope positions with the
  pixel colour, Add blend (no atomics needed; atomic image ops under MoltenVK are UNVERIFIED so avoid for histograms:
  use point accumulation or Analyze TOP row/column stats). Native TD has no Vectorscope TOP in the 31550 dump
  (grep of `ops_TOP_2025.31550.json`: analyze/convolve/lookup exist; no histogram or vectorscope). Overlays (graticule)
  as a Text/Rectangle TOP stack.
- Pars: Scope type, Intensity, Graticule, Rec.601/709, Size, Pixel step, Hold. Perf 0.4-0.8 ms. M. Pri 2.

## 8. F. Retro machines, palettes, dither, teletext, displays

### AV-34 Hardware palette quantiser
- Palettes (hex lists live in a DAT table; load more via palette DAT import; Lospec palettes mostly free to use but note
  per-palette terms): Game Boy DMG 4 greens (common set `#9bbc0f #8bac0f #306230 #0f380f` **[M]**), Pocket 4 greys, GBC modes;
  NES (54 usable colours from 2C02, several named tables: FCEUX, Nestopia, "Smooth"), C64 Pepto 16 colours **[M]**, CGA
  (modes: palette 1 high `#000 #55ffff #ff55ff #fff`), EGA 16/64, ZX Spectrum (8 colours x bright; **attribute clash**:
  per 8x8 cell only 2 colours, ink/paper, one bright bit), Apple II (6), MSX, SMS/Genesis 9-bit, PICO-8 16, TIC-80, Amiga
  OCS 12-bit / **HAM** (hold-and-modify: per scanline, each pixel either picks a palette entry or modifies one RGB
  component of the previous pixel - sequential per row, row-parallel compute at virtual res), teletext 8 colours (AV-38).
- Technique: nearest colour in **Oklab** (JZB_Lofi_Reducto uses Oklab already) over up to 64 entries; Spectrum/C64
  cell constraints: compute per-cell best 2-colour pair at virtual res (32x24 cells x 28 pairs x 64 px = 1.4 M ops);
  HAM per row. `Virtual Res` + `Pixel Aspect` (NES 8:7, C64 0.936 **[M]**) in front, nearest upsample out.
- Pars: Machine, Palette (DAT row set), Virtual Res W/H, Aspect, Distance (Oklab/RGB/Luma-weighted), Dither (AV-35),
  Constraint (None/Cell 8x8/Scanline HAM), Contrast pre, Border colour.
- Presets: Game Boy, GB Pocket, NES, C64 multicolour, CGA pal1, EGA, Spectrum, Amiga HAM, PICO-8, Mac 1-bit.
- Perf 0.2-0.5 ms. S-M. Pri 1.

### AV-35 Dither engine
- Ordered: Bayer 2/4/8/16 (generated in shader), blue noise (64x64 void-and-cluster texture made offline in Python, shipped
  as a file), IGN (interleaved gradient noise `fract(52.9829189*fract(0.06711056 x + 0.00583715 y))`, Jimenez **[M]**),
  white noise; Game Boy Camera style 4x4 matrix with 3 thresholds per cell **[M, UNVERIFIED values]**; halftone/line screens
  already exist in Halftone. Error diffusion (Floyd-Steinberg, Atkinson, Sierra, Jarvis, Stucki): sequential by nature.
- TD options for error diffusion: (a) **tile-parallel**: independent 32x32 tiles at virtual res, one thread per tile
  serial raster scan; seams are visible only at high zoom, good enough for pixel art; (b) the MaxMainio repo (74062, MIT,
  built on 32820, error-diffusion TOPs with bit depth) and Skywalker 71378 (6 algorithms) show how others did it: read
  expanded GLSL before building; (c) row-wavefront with N+W dispatches (too many for 1080x1920). Temporal stability: ordered
  dither with a *static* mask (no shimmer) or animate via blue-noise scroll at <= 24 Hz (LED rule from Grain).
- Pars: Method, Matrix Size, Levels per channel 2-16, Palette link (AV-34), Scale (pixel size), Serpentine, Strength,
  Animate Hz 0-24, Colour (RGB/Luma only).
- Perf: ordered 0.2 ms; tile error diffusion at virtual res ~1-3 ms (UNVERIFIED on MoltenVK). M. Pri 1.

### AV-36 Retro screen (console/computer framing)
- Virtual res + nearest scale, pixel aspect, **border** (C64 / NES overscan colour), 4:3 safe area, **raster bars**
  (Amiga copper / C64: per-scanline colour sine bars, animated), sprite flicker (every other frame odd/even), screen
  shake on hit, colour fade. Perf 0.15 ms. S. Pri 2.

### AV-37 Palette cycling
- Mark Ferrari's 8-bit "Living Worlds" colour cycling (indexed image + rotating palette ranges) **[M]**: quantise luma/hue
  to N indices (32-128) and rotate the palette ramp with per-range speeds (water, clouds, fire). Works on any clip; best
  with a stills pipeline. Pars: Indices, Ranges (up to 8, each start/end/speed/direction), Palette ramp, Blend Between
  Steps (smooth or hard). Perf 0.15 ms. S. Pri 2.

### AV-38 Teletext / Ceefax / Videotex
- Look (EN 300 706 / Level 1, 1976 **[V partly]**): 40x24 character grid, 8 colours chosen per character, 2x3 mosaic
  "sixel" block graphics (contiguous or separated), control codes: double height, flash, conceal, hold graphics; Fastext
  coloured buttons footer; header row "P100 CEEFAX 1 100 Mon 26 Oct 18:30/45" (12 h per user rule); page-loading: rows
  populate top-to-bottom. SAA5050 character ROM is Mullard/NXP; use an open teletext font (Bedstead, Unscii; licences
  to check) **[M]**; the chip also smoothed diagonals of the 5x9 glyph bitmaps.
- Technique: render source to a 80x72 sixel grid; for each 2x3 cell choose the best 2 colours (fg/bg) from 8 and a 6-bit
  mask (compute, one thread per cell: 28 pairs x 64 masks reduced by thresholding = cheap); text layer from a DAT (pages)
  with a per-cell glyph atlas lookup; flash 1 Hz toggle; hold/double-height from a small control-code parser in Python
  that writes a 40x25 cell texture (R = char, G = fg|bg|flags). Subtitle mode: black box + white/yellow text (Ceefax
  subtitles) - a pure lyrics_feed styling target for Urdu/Roman/English lines per the lyrics rules (one script per line).
- Pars: Mode (Page / Subtitle / Image-to-sixel), Grid 40x24/25, Colours 8, Separated Graphics, Flash Hz, Double Height Rows,
  Page Load Animation speed, Header Text, Font, Fastext Labels.
- Perf 0.4 ms. M. Pri 2.

### AV-39 Text-mode (CP437 / PETSCII / ANSI)
- Extends td-port ASCII: fixed 80x25 grid, 16 EGA colours, blink attribute, 9x16 CP437 bitmap font (Unscii etc. **[M]**),
  PETSCII graphics set, ANSI block shading (`░▒▓█`). Perf 0.3 ms. S. Pri 3.

### AV-40 Small displays
- Items: **LCD ghosting** (response-time feedback with asymmetric rise/fall: the Game Boy smear; cheap and a staple), STN
  contrast shift; VFD (cyan-green segments with grid lines + bloom); Nixie (orange neon digits with stacked cathode
  glow); flip-dot (bistable disc flips with a flip time and click-on-change); split-flap (rotating flap cards with an
  alphabet sweep); 7/14/16-segment; HD44780 5x8 character LCD; e-ink (ghosting + full-refresh flash on page change).
- Each ~0.2-0.5 ms; M; Pri 3. Text content comes from lyrics_feed/cuelist DATs.

### AV-41 LED wall emulation (PF26-critical)
- Look: how content really appears on an LED wall (and how it breaks) so looks can be judged without the wall. Joins the
  R02 stage (nine faces, 9984x3840 native), previz_stage and the Lofi_CRT mask-vs-pitch rule.
- Technique: (1) **pixel structure**: `Pitch mm` (P2.6/P3.9/P4.8/P6.25 typical **[M]**), SMD 3-in-1 vs discrete, cabinet size
  (500x500 / 500x1000 mm), per-LED Gaussian emission (`LED Size %`) and dark gap, optional cabinet seam lines;
  (2) **greyscale/PWM**: bit depth (8-14), gamma LUT, low-brightness banding and dithered low levels (a visible truth:
  dark gradients band on LED), peak nits clamp (`Max Nits` vs content);
  (3) **viewing**: angle brightness falloff (cos law / LED binning), colour shift off-axis;
  (4) **refresh/scan**: refresh rate (1920/3840 Hz), scan ratio (1/8, 1/16), phase bars for camera capture (see AV-44);
  (5) **faults**: dead pixels, dead module/cabinet (black rect), brightness/colour mismatch between cabinets (+-5 %),
  stuck-on pixel, cable sparkle (random lit pixels), cabinet-ID overlay, low-refresh flicker (uses `Strobe` limits);
  (6) **content-safe checks**: thin lines vs pitch (flag details under 2 px at native), text height vs distance
  (reuse readability rule: read from far on any background: big, solid, outlined).
- TD: render at an integer multiple of virtual LED grid (e.g. 1080x1920 canvas = N LED cells; `Cells W/H` par) ->
  nearest down to LED grid -> upsample with the LED emission mask shader (single GLSL TOP, computes per-pixel cell
  coordinates, gaussian per LED, gap) -> glow (AV-04, optional) -> viewing/greyscale -> faults overlay. Single-pass shaders
  plus the glow chain; no neighbour dependency beyond the cell, so low risk.
- Pars: Pitch mm, Cabinet W/H mm, LED Size %, Gap, Seams, Bit Depth, Gamma, Max Nits, Ambient (AV-43), View Angle, Camera Mode
  (AV-44), Dead Pixels %, Dead Cabinets (table), Cabinet Mismatch %, Sparkle %, Show Cabinet IDs, Zoom.
- Presets: P3.9 indoor, P4.8 outdoor, P2.6 IMAG, P6.25 outdoor stage, "PF26 R02 face" (cells per face from show.json), fault drill.
- Perf 0.8-1.5 ms. M-L. Pri 1.

## 9. G. Projector + venue

### AV-42 Projector optics
- Items on top of LK_projection_room (which already models throw, lens shift, coverage, brightness, dome): keystone (Corner Pin
  TOP native), lens barrel/pincushion (Lens Distort TOP native), lateral chromatic aberration (R/B radial scale +-0.1-0.5 %),
  focus falloff toward edges (field curvature), `cos^4` brightness falloff + lamp hotspot, vignette, 3-LCD panel
  misconvergence (R/G/B shifts varying across the field), screen texture (gain, speckle), **DLP rainbow** (single-chip colour
  wheel: R,G,B sampled at three sub-frame times; emulate with Cache TOP offsets so moving edges show red/blue
  fringes), lamp flicker, lens flare/ghost optionally. Perf 0.4 ms. M. Pri 2.

### AV-43 Black level / ambient light / daylight washout
- Technique: `out = content * gain + ambient * screenReflectance` in linear light; contrast ratio floor (native black
  0.0005 for 2000:1 **[M]**); tone shaping so dark colours lose saturation; shows what a look does at 5:30 PM daylight
  (the show starts 5:30 PM, Karachi sunset in late October is about 18:00 **[M]**, so the first hour is in daylight: a good
  guard for content that depends on deep blacks). Pars: Ambient lux, Screen Nits, Reflectance, Contrast Ratio, Time of day
  preset (Day/Dusk/Night), Gamma. Perf 0.1 ms. S. Pri 1.

### AV-44 Camera-on-screen sim (IMAG)
- When a camera films an LED wall: moire (alias of the camera pixel grid vs LED grid: render AV-41 at 4x, downsample with
  nearest/box to camera res), black rolling bars when shutter and refresh/scan don't match (bar position = phase between
  shutter and PWM; scrolls slowly if rates differ), rolling shutter skew (AV-19b), exposure/clipping (highlights), colour
  cast, lens blur. Pars: Camera Res, Shutter angle/speed, LED Refresh Hz, Scan ratio, Sync Offset, Moire gain, Rolling
  Shutter. Perf 0.5 ms. M. Pri 2.

---

## 10. Preset ideas (cross-module "looks", one-click)

1. **Rental tape 1994**: AV-17 Worn + AV-03 mild + AV-02 + AV-16 PLAY OSD.
2. **Arcade cabinet**: AV-35 ordered Bayer 4 + AV-34 15-colour + AV-08 arcade + AV-31 for HUD.
3. **Ceefax night**: AV-38 page + AV-08 shadow-mask consumer + AV-10 composite.
4. **Rutt/Etra performance**: AV-26 + audio deflection + AV-04 glow.
5. **Scanimate intro**: AV-27 logo + AV-22 colorizer ramp from PRISM brand.
6. **Monitor loop**: AV-28 spiral, beat re-seed, gain clamped.
7. **Scope club**: AV-30 on the live mix, AV-32 goniometer corner inset.
8. **LED reality check**: AV-41 P3.9 + AV-43 Day + AV-44 camera, on any look, to judge it.
9. **Gameboy ghost**: AV-34 DMG + AV-35 GBCam + AV-40 LCD ghost + AV-36 shake.
10. **TV off**: AV-07 power-off collapse as a scene transition; **TV on**: warm-up.

## 11. Not possible here and the best substitute

| Wanted | Why not | Substitute |
|---|---|---|
| Real motion vectors from codecs (MPEG/H.264 macroblock motion for authentic datamosh/plasma false contour) | no codec access in TD 31550 TOPs; Optical Flow TOP unsupported on Mac (T-18) | frame-difference / user motion vectors (CHOP/Null), block-wise Cache TOP corruption, GLSL block-matching at 16x16 (compute) if needed; handled in the datamosh research file |
| Real IIR filters everywhere | sequential; MoltenVK compute dispatch per row is low-parallel | FIR 32-64 taps; optional row-serial "Exact" mode on scratch TD |
| Atomic histogram | atomic image ops UNVERIFIED under MoltenVK | point accumulation (instancing) or Analyze TOP row/column stats |
| Multi-pass pixel-mode GLSL chains | T-46 tears | compute mode + `texelFetch` (T-47), or native ops (Blur, Feedback, Transform) |
| Raymarched CRT in a room (meta-crt) | libretro lists it as "very, very demanding" **[V]** | AV-03 glass reflection + Image input |
| Authentic Mullard SAA5050 ROM | copyright of the ROM | open teletext font, own sixel renderer |
| Exact hardware spectra (P-phosphor curves, real LED binning) | no measured data in this research | parametric curves, mark presets "approximate" |

## 12. Build order proposal

1. **Native-op quickies (no GLSL risk):** AV-28 feedback, AV-04 glow, AV-43 daylight, AV-22 colorizer, AV-23 bands.
2. **One-pass shaders:** AV-01, AV-03, AV-06, AV-07, AV-34, AV-35 ordered, AV-36/37, AV-41 (core), AV-16.
3. **Signal path:** AV-10 (with numpy reference tests) then AV-17, AV-11/12/13.
4. **Geometry/scopes:** AV-30 (instanced), AV-26, AV-27, AV-31, AV-33.
5. **Platform:** AV-20 patchbay + AV-08 monitor macro + AN_chain; then AV-38, AV-40, AV-42, AV-44.
Live checks to define when building: each module `Amount 0` = exact passthrough; cook ms at 60 fps with the other lab COMPs
parked; mask/lines readable at LED-wall scale (render a 9984x3840 crop offline at 1:1 as the check); no flash > 3 per second
in any loop (show-safe).

## 13. Open questions for the user

- Hearn Videowarp: which device/work do you mean (link or video)? Not found in this search.
- Are the CRT/VHS looks for the **LED wall** (mask must scale to pitch; 6+ px advised) or for screens/IMAG only?
- Should AV-26..29 be treated as one **video-synth rack** (AV-20 first) or as separate showpieces first?
- Is a physical oscilloscope or ILDA/XY-audio output wanted later (AV-30 could also *emit* the XY audio via the laser path)?

## Sources

Read this session: libretro CRT shader list (gametechwiki `CRT_Shaders`, docs.libretro.com index), Godot port of Lottes
CRT (godotshaders 3406; CC0, Shadertoy MsjXzh), LMP88959/NTSC-CRT, valadaptive/ntsc-rs, joncampbell123/composite-video-simulator,
derivative forum "Rutt-Etra synth simulation" (4959), Wikipedia (Sandin Image Processor, Teletext, Game Boy), ModularGrid LZX
vendor/module pages, Osci/Fenderson workshop pages (CCC camp 2019, xythobuz osci music player), SIGGRAPH history "Now Indigo
Blue" and Cornell Goldsen video tools pages for Paik/Abe, local repo files (STATUS.md, td-port/INVENTORY.md and READMEs,
stagelab guides and plugin-stack, docs/research community/popular, projector_dome.md, ops index). Search results that
returned only snippets (no page read): Shadertoy Rutt-Etra DdXfRj, rutt etra izer, Magic Music Visuals, nas.sr scanlines,
Gumroad CRT/ANALOG_TV listings. Everything tagged [M] is from general knowledge and must be checked when built.
