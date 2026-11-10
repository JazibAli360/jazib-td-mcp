# FX3 - Film, lens and camera emulation (26 Oct 2026)

Offline research for the user's request "all the effects we can add, with emulation of known looks". Territory: film stock,
lens, camera body, colour science. **Nothing was run in TD, no jazib-td tool called, nothing downloaded.** Build target
TD 2025.31550, macOS Rosetta, Vulkan/MoltenVK, 1080x1920, 60 fps, ~3 ms per COMP. Evidence tags: **[doc]** read on
docs.derivative.ca this session, **[src]** read on the page named, **[mem]** from my own knowledge, not re-verified
(treat as UNVERIFIED until a live probe), **[est]** performance guess (no measurement exists; measure with `td_perf`
before any claim). Web search returned little for shader names (Shadertoy pages are not indexed by the search tool and
shadertoy.com/howto answered 403), so Shadertoy items below are technique names to look up by hand, not read code.

## 0. Hard rules this file obeys

- Multi-pass = **compute-mode GLSL TOPs** (T-47); pixel-mode chains only single-pass (T-46). Blur/Bloom/Tone Map/Lens
  Distort/OpenColorIO/Cache/Lookup are native TOPs and are not GLSL, so they are safe to chain.
- Not possible here: Optical Flow TOP (T-18), codec motion vectors, real depth from a flat video. Substitutes: GPU block
  matching (td-port `flow_fx` already has it: quarter-size grey, SAD search; reuse its `blocksad.frag` idea), a depth
  source from `DC_depth_cam` (Apple/Vision depth helper), Render TOP depth for 3D looks, or a luma/edge fake depth.
- Work in **linear light, 16F** until the last node (OpenColorIO page: "the colour space of TouchDesigner TOPs is
  linear" [doc]; P7 in `P_realtime_3d_looks.md`). Output stage converts + dithers to 8-bit.
- PF26 flash safety: any effect that can pulse brightness (exposure flicker, rolling-shutter flash bands, lens-flare on
  strobe, halation pop) gets a **Safe cap** par (max 3 flashes/s, luminance-delta limit) per
  `concert-visuals-research/README.md` s4 (cited from P_realtime_3d_looks.md; not re-read here).

## 1. What we already have (do not rebuild; extend)

| Existing | Where | Extend with |
|---|---|---|
| Bloom / Blur / Tone Map / Lens Distort / OpenColorIO / Lookup / Cache TOPs | native 31550 | Used as parts below; Tone Map TOP has 7 operators: ACES Approx, Lottes, Filmic, Hable Filmic (Peak Input Nits, Exposure Bias), Reinhard, Extended Reinhard, Extended Reinhard Luminance [doc]. |
| `FX_palette_map`, `FX_strobe`, `FX_motion_trail` | lab | motion_trail = feedback decay; becomes the "shutter angle" engine in C1. palette_map's OKLab maths reused in the grade (S3). |
| Vignette (`JZBC_Vignette`, ellipse/rect, colour, pump) | td-port, saved .tox, tested | L7 adds cos^4 law, anamorphic oval, edge colour cast. |
| RGB Split (`JZBD_RGBSplit`) | td-port | L5 adds radial/spectral CA. |
| Glitch, Echo, Shake, SlitScan (`JZBT_SlitScan`, Cache-based), Halftone, Kaleido, Tunnel, Tile, Ripple, Shockwave, ElasticLens, AnamorphicCollapse, LightSweep, Strobe | td-port, saved .tox | SlitScan = the C3 rolling-shutter engine; Shake = C8 base. |
| Pending in td-port (shader exists, never run in TD): Grain, Grade, Bloom, CRT, VHS, Datamosh, CamLevels, LumaMix, FlowFX (block matching), DepthFX, light_shafts | td-port/INVENTORY.md | **Port, don't re-write**: F4 reuses Grain, S3 reuses Grade, C1/C3 reuse FlowFX, L10 reuses DepthFX. Read the .frag first (each is single-pass, matches T-46). |
| Motion / depth / person | lab: DC_depth_cam, person mask (in progress), face_track | depth for DOF (L10), mask for subject-protected halation/grain. |

CRT/VHS/datamosh/glitch belong to other research lanes; this file only touches them where a camera body does it (C5, C6).

## 2. Shared engine (build once, every effect below uses it)

1. **Linear working format**: all FX3 COMPs take/return RGBA16F; an `Inputfmt` menu (sRGB-8bit / linear / Rec709 /
   LogC-ish) converts at the door via one tiny GLSL or the OpenColorIO TOP. Output `Outfmt` converts + dithers.
2. **Pyramid helper** (compute GLSL, 6 downsample + 6 upsample dispatches, dual-Kawase style [mem]): the single cheapest
   way to get big radii (bloom, halation, diffusion, streak, glare) under 1 ms. Native alternative: Blur TOP with
   `preshrink` ("acts like a larger kernel size with less performance cost, lower quality" [doc]). Plan: Blur TOP
   route first (zero risk), compute pyramid when the quality is not enough.
3. **Highlight extractor**: soft-knee threshold on luma (or max-channel), output the excess only (so bloom/halation
   add energy, not re-add the image). Pars: Threshold, Knee, Clamp.
4. **Chain COMP `FC_filmchain`** (the product the user sees): fixed physically-ordered slots, each slot a COMP with
   Bypass + Mix: `Input -> [lens: distort, CA, DOF, tilt-shift] -> [flare/glare/diffusion/streak] -> [sensor: motion
   blur, rolling shutter, auto-exposure, ISO noise, CCD smear] -> [film: halation, weave, grain, dust, leaks] ->
   [colour: grade, stock curve, LUT, tone map] -> [display: vignette, letterbox, dither] -> Out`. Order list is a
   reorderable table (PX rule: modules add/remove/reorder). Per-slot cook ms shown in a debug row.
5. **Audio/effector inputs** (house convention, `zkit` knobs): every key amount has a CHOP-export-friendly par; Null
   effectors named `fx_*` (kick -> halation pop, snare -> flare flash, bass -> weave amount, bar -> light leak
   sweep, level -> ISO). Randomness always has a `Seed`; time sources are `absTime`-free (par `Time`/`Speed`).
6. **Quality par** on the COMP: Full / Half / Quarter working size for blurs (cost scales ~linearly with pixels).
7. **Budget** (est, unmeasured; 2.07 Mpx 16F): one compute pass ~0.15-0.4 ms; a Blur TOP size-60 with preshrink 4 ~0.2-0.5
   ms. A full chain with everything on is ~8-14 ms [est], so the chain exposes a **Cost meter** and a `Lite` preset
   switch (halation + grain + grade + vignette ~1.5 ms [est]). First lab task: measure these on the real Mac.

## 3. FILM emulation

Grain, halation, weave and the stock curve are the four things that make footage read as film. Everything is
"inspired by", never a claim to match a stock: real stock data (spectral sensitivities, print LUTs) is proprietary and
we invent none; presets are tuned by eye against public look references and named by descriptor
("warm 35mm print", "tungsten teal 500T-style"), not by trademark, in the UI.

### F1 Filmic tone curve (toe / shoulder / contrast) - priority 1, S
- **Look**: highlights roll off instead of clipping; lifted-then-crushed blacks. Reference: any ACES/filmic render.
- **Technique**: curve on linear RGB. (a) Native **Tone Map TOP** (ACES Approx, Hable, Lottes... [doc]) for zero-cost
  start. (b) Custom single-pass: Narkowicz ACES fit `saturate(x*(2.51x+0.03)/(x*(2.43x+0.59)+0.14))`, "free to use under
  public domain CC0 or MIT"; fit pre-exposed so input 1 ~ 0.8, error <= 0.0138; luminance-only so it over-saturates
  bright pixels [src: knarkowicz.wordpress.com/2016/01/06/aces-filmic-tone-mapping-curve]. (c) Parametric
  toe/shoulder S-curve (Filmic Worlds / Uncharted2 shape [mem]) with par-driven toe strength, shoulder start, white point.
- **Pars**: Exposure (-6..+6 stops), Curve (Off, ACES-fit, Hable, Lottes, Reinhard-ext, Parametric), Toe (0-1), Shoulder
  (0-1), WhitePoint (1-16), Contrast pivot (0.18), Highlight desat (0-1: counter the ACES over-saturation), Per-channel
  vs luminance mode.
- **Inputs**: exposure par from audio level CHOP (slow) / auto-exposure (C7).
- **Perf**: Tone Map TOP ~0.1 ms; custom 1 pass ~0.15 ms [est]. **Extend**: lab FX_palette_map is separate; this feeds it.

### F2 Film-stock colour response ("LUT-free" stock engine) - priority 1, M
- **Look**: the stock identity. Preset families (descriptors): warm 35mm print (orange mids, green-cyan shadows,
  creamy shoulder); tungsten-balanced teal-orange 500T-style (halated reds, blue shadows); slide-film punch (saturated,
  contrasty, crushed); desaturated 90s documentary; Super 8 / 16mm (soft, warm, fade); cold bleach-bypass; black-and-white
  high-contrast panchromatic; faded vintage print (lifted black, yellowed highlights).
- **Technique** (one compute pass, all in linear/log): (1) optional log encode (Cineon-like `log10` with 0.18 pivot [mem])
  so curves act in a perceptual domain; (2) 3x3 channel-crosstalk matrix (dye cross-density; rows = in, cols = out);
  (3) per-channel S-curves with independent toe/shoulder (this is what gives colour shifts in shadows vs highlights:
  "crossover"); (4) saturation as function of luma (3 anchor points: shadows/mids/highlights); (5) split-tone (shadow
  tint, highlight tint, balance); (6) film "fade" = black lift + white gamut compression; (7) B&W: weighted channel mix
  (panchromatic / orthochromatic / red-filter) before the curve.
- **Process modes** (all become presets of the same maths):
  - **Bleach bypass**: blend colour with its own luma-contrast image: `rgb' = mix(rgb, luma(rgb)*k + overlay-contrast, amount)` -> low sat, high contrast, silvery [mem].
  - **Cross-process**: swap per-channel curve slopes: R steep S, G mid, B inverted-shoulder -> cyan-yellow cast, high sat [mem].
  - **Two-strip Technicolor** (R+G only, B from G) and **three-strip** (saturated primaries, deep cyan-red) as crosstalk matrices [mem].
  - **Day-for-night**: darken + blue cast + desaturate + crush (preset only).
  - **Sepia / cyanotype / duotone**: B&W then map through 2-3 colours (ties to FX_palette_map).
  - **ENR / skip bleach, solarisation (Sabattier)** (priority 3): curve with a fold at a pivot; solarize = `abs`-style fold.
- **Pars**: Preset, Strength (mix), Log pivot/Encode, 3x3 matrix (9 floats), Per-channel Toe/Shoulder/Slope/Pedestal,
  Sat-by-luma (3), Shadow/Highlight tint + Balance, Fade, B&W filter colour.
- **Perf**: 1 compute pass ~0.2 ms [est]. **Difficulty**: M (the matrix/curve tuning is the work: 10 presets x 1 h).
- **Extend**: bake any result to a 17^3/33^3 `.cube` (see S2) so a stock look can also go to Resolume/other tools.

### F3 Halation - priority 1, S-M
- **Look**: red-orange glow bleeding from bright highlights/lights, strongest on tungsten night shots (CineStill 800T
  look; also all consumer colour negative to a lesser degree). Reference: neon signs on film.
- **Physics** (single secondary source, not a measured spec): light passing through emulsion reflects off the film base
  and re-exposes the emulsion; red is the deepest layer, so it picks the most. One paper gives per-channel radius ratios
  r_R = 1.4r, r_G = 1.0r, r_B = 0.7r; a design note gives green ~0.25 x red - they conflict, so both are tuning starting
  points [src: arXiv "Deep Analog" 2608.14702 (as returned by search), photrio.com forum thread]. Dehancer's method is not
  published; do not claim to match it.
- **Technique**: highlight extract (steep soft knee) -> three blurs with different radii (R widest) -> colour-tint
  (default orange-red, per-channel gains) -> add in linear before the grade; optional "anti-halation" = reduce radius for
  stocks with a rem-jet layer. Cheap native route: Level/threshold -> Blur TOP x3 (preshrink 2-4) -> Channel Mix -> Add.
  Better: compute pyramid (section 2.2) with R using levels 1-6, G 1-4, B 1-2.
- **Pars**: Threshold, Knee, Radius (px at 1080 wide), R/G/B radius ratios, Tint colour, Intensity (0-3), Mix mode (Add /
  Screen), Preserve-source-edges (subtract blurred-core), Only-bright-areas mask input (person mask to keep skin clean).
- **Inputs**: kick -> Intensity pop (Safe cap), mask TOP.
- **Perf**: Blur route ~0.8 ms; pyramid route ~0.5 ms [est]. **Presets**: "800T-neon", "subtle print", "Super 8 glow", "hot lamps".

### F4 Film grain (three models) - priority 1, S-M
- **Look**: organic, luma-dependent, evolves per frame, size/colour per gauge.
- **Models**: (1) **Hash/white** (cheap, TV-like; td-port has a pending `Grain` .frag: port it). (2) **3D-noise grain**:
  Matt DesLauriers `glsl-film-grain`, **MIT**, 3D noise with time on Z, signature `grain(texCoord, resolution, frame,
  q)` returning mono float; blend soft-light/overlay/add and reduce in bright areas with `smoothstep(0.05,0.5,luma)`
  [src: github.com/mattdesl/glsl-film-grain]. (3) **Clumped / dye-cloud grain**: 2-3 octaves of band-passed noise at
  different scales, sum as Poisson-style variance `sigma^2 ~ a*L + b` (mid-weighted, lowest in clean highlights), per-
  channel decorrelated seeds with a luma-correlated component so it is mostly luminance with weak chroma.
- **Gauge presets**: 8mm (coarse, 3-4 px, strong), Super 8, 16mm (2 px), 35mm (1 px, subtle), 65mm/IMAX (fine), "pushed 3200"
  (clumpy + contrast). Grain size is in px at the 1080 width (par scales with resolution multiplier).
- **Pars**: Amount (0-1), Size (0.5-8 px), Softness, Luma response (shadow/mid/highlight weights), Chroma amount (0-1),
  Animation (24 fps hold / every frame / frozen), Seed, Blend (Soft light / Overlay / Add / Multiply), Model.
  **Grain at 24 fps on a 60 fps output**: re-seed every 2.5 frames (hold) - a signature film cue; par `Grain fps`.
- **Perf**: ~0.15-0.3 ms [est] (3D-noise model costliest). **Extend**: also feeds C4 ISO noise.

### F5 Gate weave, projector flicker, frame jitter - priority 2, S
- **Look**: the picture drifts a few pixels, tiny rotation, brightness breathes at 24/18 Hz; sprocket-pull "pop" on cuts.
- **Technique**: low-frequency band-limited noise (1/f, 2-5 Hz) -> translate X/Y (+- up to 6 px), rotate (+- 0.1 deg), zoom
  (+- 0.3%); flicker = brightness multiplier from smoothed random at 12-24 Hz, shape = sum of sin + noise; "frame
  pop" = decaying kick impulse (Lag CHOP). Implementation: Transform TOP driven by a CHOP (Noise CHOP, no GLSL needed) -> ~0.1
  ms. Lens-distort-free; edges `Mirror` or black gate (see F9).
- **Pars**: Weave X/Y/Rot/Zoom amount, Weave speed, Flicker amount + rate + Safe cap, Projector bounce (vertical
  jump on beat), Seed. **Inputs**: bass -> Weave amount (slow-lag), beat -> pop.
- **Extend**: Shake (td-port) = handheld; weave = projector. Keep separate, same CHOP backbone.

### F6 Dust, scratches, hairs, gate debris - priority 2, M
- **Look**: white/black specks, long vertical scratches, hairs in the gate corner, blotches (emulsion damage), cue marks.
- **Technique**: all procedural in one compute pass over a cell grid: per-frame hash gives N dust specks (random
  position, radius 0.5-4 px, bright or dark, lifetime 1-2 frames); scratches = thin vertical lines at random x with
  slow drift, 1 px, brightness variation along y by 1D noise; hairs = short curved SDF segments (Bezier, 2 points) near
  the gate edge; blotches = thresholded low-freq noise; reel-change cue marks = rare small circle top-right. Alpha-
  composite or screen onto picture. Optional **sprite mode**: user dust scan PNG sheet (we do not ship third-party scans)
  picked randomly per frame with Switch TOP.
- **Pars**: Dust density/size, Scratch count/width/opacity, Hair count, Blotch amount, Colour (white / black / mix), Frame
  hold (24 fps), Seed, Mask (keep off logo area).
- **Perf**: ~0.2 ms [est]. Beware: bright specks on an LED wall at 1080 px read as dead pixels: default sizes >= 2 px.

### F7 Light leaks and film burn - priority 1, S
- **Look**: warm orange/red/magenta bloom washes sweeping in from the frame edge; flash-burn transitions to white-orange.
- **Technique**: procedural: 2-3 animated blobs (SDF circles/lines pinned to an edge) coloured from a ramp
  (red -> orange -> yellow -> hot pink), distorted by 2 octaves of noise, drifting by a slow LFO, blended with
  **Screen** (never Add on 8-bit) in linear. **Burn** = threshold-driven expansion: noise + rising `level`, colour ramp
  from white-hot to orange to black edge (like emulsion burning). Optional stock clip overlay (user provides; media
  folder rule). Beat sync: a bar-clock triggers one sweep, ADSR envelope.
- **Pars**: Preset (Edge warm, Corner magenta, Full wash, Burn flash), Colour ramp, Position/Angle, Size, Softness, Speed,
  Intensity, Trigger (pulse), Attack/Hold/Release, Safe cap (default on: peak luminance delta <= 0.25/frame).
- **Perf**: ~0.15 ms [est].

### F8 Frame, gate and camera format overlays - priority 3, S
- Film gate edge (rounded corners, black or lightly vignetted border), 4-perf sprocket strip (stylised, not a specific
  stock's edge print), frame-line between stacked frames (two frames on a vertical canvas = film strip loop on 1080x1920),
  edge print text (ties to Urdu type), **aspect letterbox** (2.39:1 / 1.85 / 4:3 pillarbox, inside a vertical canvas = bars
  top/bottom). **Vertical-canvas note**: our 1080x1920 canvas is portrait; a 2.39 letterbox leaves ~452 px tall picture -
  offer "Rotate 90 deg inside" mode (picture rotated in the frame) as a stylised option, default off.

## 4. LENS emulation

### L1 Anamorphic horizontal streak - priority 1, M
- **Look**: long blue/cyan (or amber, magenta) horizontal streaks from every bright light, as in anamorphic cinema and
  "J.J. Abrams" flares. Reference: any anamorphic night driving shot.
- **Technique**: highlight extract (L3 of section 2) -> **1D anisotropic blur** with very long kernel (200-1000 px) via
  down-up pyramid with **horizontal-only** filtering at each level, summing the levels with exponential falloff
  (Kino Streak by keijiro, **MIT**, "a quick implementation of anamorphic lens flares for Unity" - the README does not
  describe the method; read `Assets` shader in the repo to confirm [src: github.com/keijiro/KinoStreak]); tint with a
  colour ramp along the streak (blue core fading to purple); add to image. Native fallback: Blur TOP with `scaley=0` /
  `scalex` large, `preshrink`, Gaussian [doc].
- **Vertical canvas**: our portrait output flips the usual geometry; the streak par `Angle` (0 deg = horizontal) so a
  streak can run along the wide axis OR across the narrow one. Build the kernel direction as a vector in the compute pass,
  not as a rotate-blur-rotate.
- **Pars**: Threshold, Knee, Length (px), Falloff, Tint colour + second colour (gradient along length), Intensity,
  Angle, Squeeze (aspect bias), Streak-only output (for debug), Per-light colour (use source hue vs fixed tint).
- **Inputs**: audio level -> Length; strobe -> Intensity (Safe cap). **Perf**: ~0.6-1 ms (7-level pyramid x 2 dirs) [est].
- **Sub-effect: oval/anamorphic bokeh** = L11 with squeeze ~2:1.

### L2 Pseudo lens flare (ghosts, halo, starburst, dirt) - priority 1, M
- **Look**: chains of coloured ghosts mirrored through frame centre, a ring halo, optional dirt-textured starburst. Reference:
  John Chapman's pseudo lens flare (technique article; no code licence stated, so re-implement from the description).
- **Technique** [src: john-chapman-graphics.blogspot.com/2013/02/pseudo-lens-flare.html]: downsample + scale/bias threshold;
  flip texcoords about centre; `ghosts` samples along the vector from pixel to centre spaced by `ghostDispersal`, weight
  by radial falloff (exponent 10 in his example) and tint by a 1D radial colour gradient; halo = normalised flip vector
  x `haloWidth` with ring weight (exponent 5); chromatic distortion = R/G/B sampled at offsets along the direction
  (3x taps); blur; multiply by dirt texture; add rotating starburst texture (matrix from camera rotation); add before tone-map.
- **Pars**: Ghosts (0-12), Dispersal, Halo width, Distortion (CA), Falloff exps, Lens-colour ramp, Threshold/Scale,
  Dirt amount (procedural noise or user texture), Starburst on/off + blades, Rotation (LFO or CHOP), Center (follow a
  point: brightest-pixel Analyze TOP or tracker), Intensity.
- **Inputs**: Center from `person` or light position; strobe -> Intensity (Safe cap). **Perf**: ~0.5-0.9 ms [est] (ghost loop 8-12 taps on a quarter-size buffer).
- **Extend**: td-port `light_shafts` (god rays) and `JZBC_LightSweep` stack with it.

### L3 Star filter / cross screen - priority 2, S-M
- **Look**: 4/6/8-point star spikes from highlights (cross screen filter, aperture diffraction).
- **Technique**: highlight extract -> N directional 1D blurs (N = 2,3,4 lines crossing; each 2 arms) at angles k*pi/N + rot,
  length L, exponential falloff; sum; tint with spectral ramp (optional rainbow fringing along the arm). Reuse the L1
  streak engine with a direction array; each line is one compute dispatch (or one dispatch looping arms).
- **Pars**: Points (4/6/8/12 arms), Length, Rotation, Falloff, Threshold, Rainbow spread, Intensity.
- **Perf**: ~0.7-1.2 ms [est] at 4 arm-pairs. **Alt**: diffraction-spike texture convolved with highlights via FFT (not in TD; skip).

### L4 Diffusion / Pro-Mist / Glimmerglass - priority 1, S
- **Look**: highlights bloom softly, blacks lift slightly, contrast lowered, skin glows. Reference: Black Pro-Mist 1/4-1/2.
- **Technique**: blend original with a heavy blur of itself weighted by luminance (`mix(img, blur, w)` with w ramping up
  with luma), plus **veiling glare** (global small lift proportional to average blurred luminance: `rgb += k *
  mean(blur)`) and a bit of local-contrast reduction. Different filter "grades" = different kernel shape: 1/8 tight
  halo, 1/2 broad. A glimmer variant adds sparkly micro-dots (high-pass noise multiplied by blurred bright).
- **Pars**: Grade (1/8, 1/4, 1/2, 1, 2), Radius, Highlight bias, Veil (black lift), Colour tint (warm), Glimmer.
- **Perf**: ~0.4-0.8 ms [est] (shares the F3 pyramid when F3 on: keep **one** pyramid per chain). **Mix** 0 = pass-through.

### L5 Chromatic aberration (lateral, longitudinal, spectral) - priority 1, S
- **Look**: coloured fringes growing towards frame edges (lateral), coloured halos on defocus (longitudinal), rainbow
  smear (prism/dispersion). Reference: cheap and vintage lenses; pmndrs/postprocessing (Zlib) lists chromatic aberration
  [src: `L_shader_sources_licences.md` row 40].
- **Technique**: lateral = R/B scaled radially about the centre by `1 +/- k*r^2` (G fixed); longitudinal = R/B blur radii
  differ (R wider: ties to halation) or R/B sampled with defocus-weighted offsets; **spectral** = N (8-16) wavelength samples,
  each with a different radial scale, tinted by a spectrum ramp, summed - smooth rainbow (RGB 3-tap is the cheap mode).
- **Pars**: Amount (px at the edge), Falloff power (1-4), Centre, Mode (RGB 3-tap / Spectral N), Samples, Anisotropy (horizontal-only
  for sensor CA), Axis rotation. **Perf**: 3-tap ~0.1 ms; spectral 12-tap ~0.3 ms [est].
- **Extend**: td-port `JZBD_RGBSplit` (linear/directional split) stays the stylised "glitch" one; this is the physical one.

### L6 Lens distortion (barrel, pincushion, mustache, fisheye) and breathing - priority 2, S
- **Look**: edges bulge or pinch; wide-angle stretch; focus-pull "breathing" (frame zooms slightly as focus changes).
- **Technique**: native **Lens Distort TOP**, Brown-Conrady (K1, K2, K3 radial; P1, P2 tangential; Optical Center;
  Focal Lengths; Extend Mode Hold/Zero/Repeat/Mirror; Optimal alpha crop; Invert) [doc]. Mustache = K1 and K2 of opposite
  signs. Custom compute pass only for what it lacks: equidistant/stereographic fisheye, animated per-axis (anamorphic
  squeeze X vs Y) distortion, and chromatic variant (one call per channel = L5 for free).
- **Breathing**: scale = `1 + b*(focus - focus0)` on the Transform TOP, driven by the same CHOP as the rack focus (L10).
- **Pars**: K1/K2/K3, P1/P2, Squeeze (X:Y 1.0-2.0), Fisheye model/FOV, Edge fill, Breathing amount. **Perf**: ~0.1-0.2 ms [est].
- **Pitfall** [doc]: the inverse approximation ignores K3 and cannot recover content outside the frame.

### L7 Vignette (physical) - priority 2, S
- cos^4 natural falloff `cos^4(atan(r/f))`, mechanical (hard edge of a hood), anamorphic oval, colour shift (edges go
  warmer/cooler), corner softness; asymmetric centre drift (weave link). **Extend** `JZBC_Vignette` from td-port (add
  cos^4, colour cast, drift); do not duplicate. ~0.05 ms.

### L8 Tilt-shift / miniature - priority 2, S
- Blurred bands top/bottom (band = focus plane line, angle par), saturation + contrast push, optional streak/halation. Two
  Blur TOPs + mask gradient (Ramp TOP) -> Composite. **Vertical canvas**: default focus band runs horizontally across the portrait image. ~0.4 ms [est]. Uses L10 gather engine when L10 on.

### L9 Lens dirt, smudge and rain on lens - priority 2, M
- Smudge/dust mask (procedural 3-octave noise + streak texture; user PNG optional) multiplies the bloom/flare light so
  bright sources reveal the dirt (as in Chapman's dirt mask). Rain/water droplets on lens (priority 3): droplets as SDF
  circles with refraction displacement (drop normal -> UV offset), drift down and merge; trails; sharp inside, blurred
  around. Shadertoy "Heartfelt" by BigWings is the best-known rain-on-glass (name only, licence not verified [mem]).

### L10 Depth of field (CoC gather bokeh) - priority 1, L
- **Look**: out-of-focus areas turn into discs, in-focus subject crisp; rack focus.
- **Inputs for depth**: (1) `DC_depth_cam` depth for live footage, (2) Render TOP depth for 3D scenes (Depth TOP in camera
  space, float32 [doc via P6]), (3) a person mask (subject sharp, background blurred), (4) fake: luma, Y-gradient (ground plane
  gets blurrier toward the horizon), or a noise map.
- **Technique**: (a) CoC map = `|depth - focus| * aperture / depth` clamped; (b) **gather** bokeh: for each pixel sample N=16-48
  points on a golden-angle (Vogel) spiral inside radius = CoC, weight by sample CoC (reject sharp-foreground bleeding); polygon
  aperture = sample positions on N-gon edge/interior; (c) **near/far split** layers to stop foreground leaking [src: Hammon,
  GPU Gems 3 ch. 28, via P6]. Cheaper alternative: **separable** disc-like kernel with complex phasors (2 passes, Niemitalo's
  method; Bart Wronski's explanation and Shadertoy; 2-component version ~4 RGBA16F textures; licence not stated) [src:
  bartwronski.com/2017/08/06/separable-bokeh]. Also hex bokeh from 3 skewed 1D blurs (DICE, SIGGRAPH 2011, Barré-Brisebois) and
  polygon-aperture separable filters (McIntosh et al. 2012) [src: search result, post text itself not read].
- **Build**: compute pass 1 = CoC; pass 2 = half-res gather (bokeh at half res looks fine); pass 3 = composite sharp + gather
  with CoC-weighted blend. Quality par = taps (16/32/48). No native DOF/bokeh op exists in the 31550 dump (P6).
- **Pars**: Focus distance (0-1 depth), Focus range (depth of field), Aperture (f-stop 1.4-16), Max blur (px), Shape (disc,
  hex, 5-blade, 8-blade, oval 2:1, cat's-eye), Blade rotation, Highlight boost (bokeh ball bright), Near/far toggle,
  Autofocus target (follow person-mask centroid / brightest point), Rack time.
- **Perf**: gather 32 taps at half res ~1-1.5 ms [est]; the top cost line in this file. Difficulty L.
- **Extend**: td-port `depth_fx` (pending) gives a depth-driven look; check before building.

### L11 Bokeh shapes and highlight discs - priority 2, M
- Disc, hexagon, pentagon, 8-blade, **oval (anamorphic 2:1)**, **cat's-eye** (shape clipped by vignette toward edges),
  **swirly Petzval / Helios** (sample offsets rotate with radius), **soap-bubble** (bright rim, dark centre), **onion-ring**
  (rings from aspherical element), **custom shape from image** (Kernel TOP as the aperture). Technique options: gather with
  weights from the aperture image (best, same pass as L10); or splat bright points as sprites (Instancing) when highlights
  are sparse (a "bokeh bubble" generator for night scenes: Analyze TOP threshold -> positions -> sprite instancing).
- Pars: Shape menu, Blades, Rotation, Squeeze, Rim brightness, Swirl strength, Cat's-eye strength, Custom shape TOP.
- Perf: same as L10 when merged; splat route 0.3 ms with <1000 sprites [est].

### L12 Vintage-lens character - priority 3, S
- Soft corners (field curvature = blur radius grows with r), spherical-aberration glow (center-weighted halo), coma (corner
  highlights comet-shaped), low micro-contrast. Combine L4 + L10 (radius map) + L5; deliver as presets "Soviet swirl", "50s
  portrait glow", "cheap zoom".

## 5. CAMERA emulation

### C1 Motion blur with shutter angle - priority 1, M-L
- **Look**: fast movement smears along its path; 180 deg shutter = half a frame of blur; 360 deg = trailing smear; 45 deg = crisp "Saving Private Ryan" staccato.
- **What is NOT possible**: codec motion vectors; Optical Flow TOP (T-18). **What is**: (1) **feedback accumulation**:
  `out = mix(prev_out, in, 1 - decay)`; shutter angle maps to decay (`decay = 1 - angle/360 * 60/fps`) - cheap, same engine as
  `FX_motion_trail`; blurs everything including stationary noise, so it is a "trail" not true blur; (2) **velocity-guided
  blur**: GPU block matching on a quarter-size grey copy (as td-port `flow_fx` does: `blocksad.frag`, ~16 px blocks, SAD) -> flow
  texture -> directional gather blur along (u,v) with N taps (8-16) weighted by shutter fraction. Real per-pixel motion blur
  without vectors from the source. Has the usual "block" artefact at edges; mask by gradient; (3) **analytic camera-motion
  blur** when the camera is ours (Transform/Camera COMP): pass previous-frame transform; blur kernel = radial (zoom), rotational,
  or translation computed per pixel from the known matrices (exact, ~0.2 ms); (4) **subframe supersample** for generators we
  own (re-cook at t + k/N, accumulate) - only if the source is a COMP we can time-sample (lab fluid/particles cannot be
  re-cooked cheaply).
- **Pars**: Shutter angle (0-720 deg), Fps basis (24/30/60), Mode (Feedback / Flow / Analytic / Subframe), Samples (4-24), Flow
  quality (block size, search range), Edge protect, Max blur px, Per-pixel speed gain.
- **Perf**: feedback 0.15 ms; flow+gather ~1.2-1.8 ms [est: block matching 8x8 +-8 over 270x480]; analytic 0.2 ms.
- **Extend**: `FX_motion_trail` (feedback), td-port FlowFX (block matching).

### C2 Rolling shutter (jello, skew, wobble, flash banding) - priority 1, M
- **Look**: fast pan skews verticals ("parallelogram frame"); propeller/guitar-string wobble; fast flash lights only a band of
  the frame (concert-cam signature when lights strobe). Rolling shutter reads rows at different times; Blender Cycles models the
  same with a per-scanline time sample and a rolling-shutter duration [src: blender-archive cycles/camera.h via search]; a
  patent filing describes the frame boundary as a parallelogram; a DFKI paper uses per-pixel velocities for real time [src:
  search results, only abstracts].
- **Technique**: (a) **Slit-scan route (exact for time-varying content)**: Cache TOP stores last N frames [doc: Output Index,
  Step Size, Interpolate Frames]; each output row y samples frame at delay `d(y) = readout * y/H` frames back -> true row-time
  skew of ANY content. The `slit.frag` + Cache pattern already exists in td-port `JZBT_SlitScan`: reuse, restrict delay range to
  0-1 frame, vertical axis. 2.07 Mpx x 8 cached 16F frames = ~265 MB [est]; keep N small (<= 6) and a Quality half-res cache.
  (b) **Velocity-skew route (cheap)**: row offset `dx(y) = vx * readout * (y/H - 0.5)`, where (vx,vy) = global motion from C1
  flow average or a CHOP (camera pan speed, Shake CHOP): one pass, no cache, ~0.1 ms. (c) **Flash banding**: strobe/exposure
  multiplier applied with row-dependent time: row is lit if `t_row` falls within the pulse -> horizontal dark/bright band
  that scrolls; band edge soft. Exposure flicker (C3) feeds the same pass.
- **Pars**: Readout time (0-1 frame), Direction (top-down, bottom-up, left-right, right-left), Mode (Cache / Velocity / Flash),
  Skew gain, Wobble (sine on dx(y), freq/amp), Cache length, Band softness.
- **Perf**: Cache route ~0.3 ms + memory; velocity route 0.1 ms [est].

### C3 Exposure flicker, AC banding, auto-exposure, white-balance drift - priority 2, S-M
- **Look**: shutter-vs-mains beat creates rolling dark bands (50/60 Hz lamps seen on a 1/60 s shutter); auto-exposure lag
  after a flash (picture blows out then settles); autofocus/WB hunting.
- **Technique**: bands = `1 + a*sin(2pi*(f_mains*t_row*... - shutter alias))` where t_row = t + readout*y/H, f_beat = |f_mains
  - n*fps|; auto-exposure = Analyze TOP / downscale to 1x1 -> Lag CHOP with separate attack and release (attack fast 80 ms,
  release 600 ms) -> gain -(log-mean-target); WB drift = slow Noise CHOP on temp/tint matrix. All single passes (<0.1 ms).
- **Pars**: Mains (50/60 Hz), Shutter angle, Band depth, Band speed, Exposure target (0.18), Attack/Release, Max gain (+-4
  stops), Over-exposure knee, WB drift amount, Safe cap on Depth and on gain step per frame.
- **Inputs**: fx_* nulls to fire "camera flash" (exposure kick).

### C4 Sensor noise (ISO) - priority 2, S-M
- **Look**: shadows noisy and colourful (high ISO), banding (fixed-pattern columns), hot pixels, chroma blotches, noise-reduction
  mush. Different from film grain: signal-dependent, Bayer-shaped, no clumps.
- **Technique**: Poisson-Gaussian model `n = sqrt(a*I + b) * N(0,1)` per channel (a = shot noise gain ~ ISO, b = read noise);
  chroma noise low-pass (blur chroma by 2-4 px in YCoCg); fixed-pattern column offset (per-column constant from a seeded
  noise texture, ~0.2-1% amplitude); hot pixels (sparse hash); temporal denoise smear (blend 20% of previous frame in shadows
  only, i.e. NR ghosting); optional Bayer demosaic mosaic pattern at 1:1 (priority 3). Share noise source with F4.
- **Pars**: ISO (100-25600, maps a,b), Chroma noise, Fixed-pattern, Hot pixels count, NR smear, Shadow bias, Seed.
- **Perf**: ~0.2 ms [est].

### C5 Digital-camera artefacts (CCD smear, blooming, purple fringing, clip, over-sharpen) - priority 2, S-M
- **CCD smear**: bright sources draw vertical streaks (column integration) - great on portrait stage footage; technique = column
  sum of highlight excess with exponential decay in y direction (a 1D vertical streak via the L1 engine, angle 90 deg) +
  colour cast. **Blooming**: saturation spills to neighbours in channels (capped at the clip). **Highlight clip**: hard clip
  to magenta/cyan on channels exceeding 1 in turn. **Purple fringing**: CA (L5) limited to high-contrast edges and
  purple/green. **Over-sharpening ringing**: unsharp-mask with negative lobes (Blur TOP Sinc type produces ringing from
  negative weights [doc]). **Moire / aliasing**: sample the source without a prefilter (Input Smoothness Nearest [doc]) and
  downscale by a non-integer factor.
- **Pars**: Smear length/intensity, Bloom spill, Clip mode, Sharpen halo, Fringe amount, Aliasing.
- **Perf**: sum ~0.5 ms [est].

### C6 Camera HUD / monitoring overlays (zebra, focus peaking, false colour, histogram, REC) - priority 2, S-M
- **Look**: the viewfinder: zebra stripes where luma > threshold, red focus-peaking on edges, false-colour exposure map, waveform
  / histogram, REC dot + timecode + battery, safe-area frame, crosshair. Useful as a "behind the camera" visual and as an actual
  engineering aid for the LED wall (clip detection!).
- **Technique**: zebra = `luma>thr && fract((x+y)*k + t) < 0.5`; peaking = Sobel magnitude > thr coloured; false colour = 1D palette
  by luma (Lookup TOP with CHOP/ramp [doc: Lookup with 2nd-input line or CHOP]); waveform = column histogram (compute atomic add
  is risky on MoltenVK: use the cheaper approach of 64 Analyze TOP strips, or a Script TOP); REC dot blinks 1 Hz; timecode from the
  lab `TC` hub. Overlay-only; flat unlit.
- **Perf**: ~0.3 ms [est]; waveform only on demand.

### C7 Cine frame rate, pulldown and shutter-feel - priority 2, S
- 24/25/30 fps hold on a 60 fps timeline (sample-and-hold via Cache `Step Size` or Switch + Trigger), 3:2 pulldown judder cadence,
  12/8 fps stop-motion, "reverse wagon wheel" is out of scope; temporal fidelity ties to C1 (shutter). Existing: td-port Stutter.
  Pars: Fps, Pulldown, Jitter, Interpolate (Cache `Interpolate Frames` for smooth). ~0.05 ms.

### C8 Handheld / dolly / zoom camera moves - priority 3, S
- Procedural camera shake (1/f noise, footfall impulses), push-in / dolly-zoom (vertigo: scale + counter-FOV, with L6), whip pan
  (linear blur + exposure peak), speed ramps. Extend td-port `Shake` with 1/f noise, per-axis pivot, rolling-shutter coupling to C2,
  breathing coupling. Preset set only; engine exists.

### C9 Analog camcorder frame (cross-handoff) - priority 3
- Date-stamp OSD, tape tracking lines, chroma bleed, dropouts: belongs to the VHS/CRT lane (td-port VHS pending). FX3 only adds
  the camera-side: viewfinder HUD (C6), auto-exposure lag (C3) and interlace combing (priority 3).

## 6. COLOUR SCIENCE

### S1 ACES-ish pipeline - priority 1, M
- **Look**: neutral, filmic, scene-linear grade with highlight roll-off.
- **TD route**: **OpenColorIO TOP** (OCIO 2.3.2 bundled; sample configs shipped in `Samples/OpenColorIO`: aces_0.1.1, aces_0.7.1,
  aces_1.3.0, nuke-default, ocio-v2, spi-anim, spi-vfx, confirmed present on this Mac). Pars [doc]: `config`, `usecolorspacetransform`
  `incolorspace`/`outcolorspace`, `usefiletransform` `filesource` `interpolation` (Nearest/Linear/Tetrahedral/Best) `filedirection`,
  CDL (`cdlmode`, slope/offset/power x,y,z, saturation), Output (`display`, `view`, `gain`, `gamma`). Transform order is fixed
  Color Space -> File -> CDL -> Output; chain several OCIO TOPs to reorder. "File transforms do not handle colour space internally"
  [doc]. ACES is not mentioned on the page; it comes from the config.
- **Own route** (no config, one pass): IDT sRGB -> ACEScg (3x3), exposure, Narkowicz/Hill RRT+ODT fit (F1), ODT to sRGB/P3 + OETF.
  Quality: the fit is luminance-only so it over-saturates [src]; add the `Highlight desat` par.
- **Pars**: Input space (sRGB, Rec709, linear, ACEScg, LogC-like, S-Log-like), View (SDR 100 nits / P3 / raw), Exposure, Gamut compress,
  Sat. **Perf**: OCIO TOP ~0.2-0.4 ms [est]; own route 0.15 ms.
- **UNVERIFIED**: OCIO TOP pixel cost on Rosetta; whether the config path with spaces works; display transform with HDR.

### S2 LUT application + LUT bank - priority 1, M
- **Facts** [doc]: OCIO TOP loads LUT file formats via OCIO ("spi1d and spi3d to name a couple"; the page gives no full list;
  a tutorial says `.cube` loads via File Transform / File Source [src: interactiveimmersive.io stylizing-footage-with-luts]).
  Lookup TOP is a 1D remap only (second-input line or CHOP, `Index Channel` mode, "RGBA Independent" does per-channel 1D curves)
  and says nothing about 3D LUTs [doc]; it does accept 3D textures.
- **Build**: (1) OCIO TOP + file transform: easiest, interpolation Tetrahedral. (2) **Own 3D LUT pass**: parse `.cube` in Python
  (LUT_1D_SIZE / LUT_3D_SIZE, DOMAIN_MIN/MAX, TITLE; GStreamer's loader only supports 3D LUTs with 0..1 domain [src]) into a
  32^3 float table -> **Texture 3D TOP** (UNVERIFIED op name/availability in 31550; probe) or the common 2D "strip" layout
  (1024x32) / Hald CLUT image; compute shader does trilinear or tetrahedral interpolation with half-texel inset. 2D strip is the
  safe fallback and works with only a Script TOP/Movie File In. (3) **Bank + morph**: up to 8 LUTs, crossfade by weight (lerp of two
  lookups; audio-driven), A/B wipe split-screen, intensity. (4) **Procedural LUTs**: generate identity cube + F2/S3 grade, bake to
  `.cube` (export for other tools).
- **Pars**: LUT file(s), Slot A/B, Mix, Interpolation, Input space (the LUT may expect log: needs the conversion before), Intensity,
  Split view, Bake. **Perf**: ~0.2 ms (two taps) [est].
- **Licence**: no third-party LUT shipped; users provide theirs (many free "creative" LUT packs are CC/own licence: check before including).

### S3 Colour grade (lift/gamma/gain, CDL, curves, qualifiers) - priority 1, M
- Primary: Lift/Gamma/Gain per channel + offset (CDL: slope/offset/power/sat is exactly OCIO's CDL page [doc]), white balance
  (temperature/tint as a Bradford-style matrix or simple Planckian ramp [mem]), exposure, contrast around a pivot, saturation, vibrance
  (less boost on already saturated), highlight/shadow recover. Secondary: **hue-vs-hue/sat/lum curves** (Lookup TOP on a hue-
  indexed ramp, 360 entries), HSV/OKLab qualifier mask (reuse palette_map OKLab maths) with feather, vignette-power window.
  Curves: RGB master + per-channel via Lookup TOP CHOP method [doc]. td-port has `Grade` pending: read its .frag before building
  to avoid a second implementation. Presets: the F2 stocks use the same maths.
- **Perf**: one pass ~0.2 ms + Lookup 0.05 ms [est].

### S4 Display stage: dither, gamut/clip safety, LED safe - priority 1, S
- **Dither**: ordered Bayer/interleaved gradient noise (as already in palette_map) or blue noise, 1 LSB, before 8-bit out: kills
  banding in dark gradients that LED processors expose (dark ramps + 8-bit Syphon, see E_live_rig / P7 note). **Gamut clip**:
  soft-clip to sRGB/P3 by chroma compress toward the achromatic axis (instead of per-channel clip hue shifts). **LED safe**: cap
  white (e.g. 235/255) and saturated-primary level on request, flash limiter output (ties to Strobe), flat black floor. Pars: Dither
  type/amount, White cap, Gamut mode, Flash limiter (Hz, delta). ~0.1 ms.

### S5 Log / HDR looks and tonemap comparison - priority 3, S
- Log profile simulation (view a "flat log" image: gamma crush + low sat, the typical un-graded footage look; invert to grade), a
  scope-like **A/B tone-map compare** (split view of Tone Map TOP operators) as a tuning aid for the user; HDR highlight bloom
  when values > 1 (Bloom TOP needs >1 values to read as light, per P7).

## 7. Priority summary (build order)

| Pri | Effect | Id | Diff | Cost est (ms) |
|---|---|---|---|---|
| 1 | Filmic curve / Tone map | F1 | S | 0.1-0.2 |
| 1 | Film stock engine + process looks (bleach, cross, two/three-strip) | F2 | M | 0.2 |
| 1 | Halation | F3 | S-M | 0.5-0.8 |
| 1 | Grain (3 models, gauges) | F4 | S-M | 0.15-0.3 |
| 1 | Light leaks / burn | F7 | S | 0.15 |
| 1 | Anamorphic streak flare | L1 | M | 0.6-1 |
| 1 | Pseudo lens flare (ghosts/halo/starburst/dirt) | L2 | M | 0.5-0.9 |
| 1 | Diffusion / Pro-Mist | L4 | S | 0.4-0.8 |
| 1 | Chromatic aberration (lateral/spectral) | L5 | S | 0.1-0.3 |
| 1 | DOF + bokeh gather | L10 | L | 1-1.5 |
| 1 | Motion blur / shutter angle | C1 | M-L | 0.15-1.8 |
| 1 | Rolling shutter + flash banding | C2 | M | 0.1-0.3 |
| 1 | ACES-ish pipeline (OCIO + own fit) | S1 | M | 0.2-0.4 |
| 1 | LUT application + bank/morph | S2 | M | 0.2 |
| 1 | Colour grade | S3 | M | 0.25 |
| 1 | Display dither / gamut / LED-safe | S4 | S | 0.1 |
| 2 | Gate weave + projector flicker | F5 | S | 0.1 |
| 2 | Dust / scratches / hairs | F6 | M | 0.2 |
| 2 | Star filter | L3 | S-M | 0.7-1.2 |
| 2 | Lens distortion / breathing | L6 | S | 0.1-0.2 |
| 2 | Physical vignette (extend td-port) | L7 | S | 0.05 |
| 2 | Tilt-shift | L8 | S | 0.4 |
| 2 | Lens dirt / rain | L9 | M | 0.2-0.5 |
| 2 | Bokeh shapes + highlight discs | L11 | M | merged |
| 2 | Exposure flicker / auto-exposure / WB drift | C3 | S-M | 0.1 |
| 2 | ISO noise | C4 | S-M | 0.2 |
| 2 | Digital-camera artefacts (CCD smear, clip, fringe) | C5 | S-M | 0.5 |
| 2 | Camera HUD (zebra, peaking, false colour, REC) | C6 | S-M | 0.3 |
| 2 | Cine fps / pulldown | C7 | S | 0.05 |
| 3 | Gate / format overlays | F8 | S | 0.1 |
| 3 | Vintage lens character | L12 | S | presets |
| 3 | Camera moves (extend Shake) | C8 | S | presets |
| 3 | Log / compare view | S5 | S | 0.1 |

## 8. Suggested first build wave (tell the user: "start here")

1. **FC core**: pyramid helper + highlight extractor + `FC_filmchain` shell (slots, Cost meter, Lite switch). ~4 h.
2. **Wave A (film look in one go)**: F1 + F2 + F3 + F4 + F7 + S4 (dither). Single-pass or Blur-TOP only: lowest risk (T-46).
   ~7-9 h. This alone moves any lab COMP to "shot on film".
3. **Wave B (lens)**: L5 -> L4 -> L1 -> L2 -> L3 (all share the pyramid). ~8-10 h.
4. **Wave C (camera)**: C3, C4, C2 (velocity route first, then the Cache route), C1 feedback mode, C1 flow mode (borrowing FlowFX).
5. **Wave D**: S1/S2/S3 (OCIO first, own LUT pass after a probe), L10 + L11 (the big one), C6.
Pilot each wave with one effect at 1080x1920 on a stored clip (`media/webcam/webcam_ref_5s.mp4`) and fps meter; park other COMPs while measuring.

## 9. Open questions for the user

1. Which look first: neon/tungsten night (halation + streak) or clean cinema (stock + DOF)?
2. Presets named by descriptor only (default), or may they use stock/lens brand names in the UI (trademark caution)?
3. Should the chain also write a baked `.cube` of the final grade (for use outside TD)?
4. Is it OK to un-park only the `FC_*` COMPs during build, as the park rule says?

## 10. Probes to run before building (nothing run in this file)

P1 Blur TOP size 100 + preshrink 4 at 1080x1920 16F: ms. P2 OCIO TOP loads a `.cube` and an ACES 1.3 view on 31550/Rosetta. P3 Texture 3D TOP
existence and `sTD3DInputs` sampling from a compute GLSL TOP. P4 Cache TOP depth 8 at 16F: memory and ms (`gpu_memory_used` Info CHOP
channel on the OCIO page suggests this channel exists on TOPs [doc]). P5 compute GLSL 7-level pyramid correctness (T-46/T-47 check) and ms.
P6 block-matching flow COMP reuse from td-port FlowFX: ms at quarter size. P7 Lens Distort TOP: Extend Mode Mirror at 1080x1920.

## 11. Sources

- docs.derivative.ca: [OpenColorIO TOP](https://docs.derivative.ca/OpenColorIO_TOP), [Lens Distort TOP](https://docs.derivative.ca/Lens_Distort_TOP),
  [Tone Map TOP](https://docs.derivative.ca/Tone_Map_TOP), [Blur TOP](https://docs.derivative.ca/Blur_TOP), [Lookup TOP](https://docs.derivative.ca/Lookup_TOP),
  [Cache TOP](https://docs.derivative.ca/Cache_TOP).
- [Narkowicz ACES fit](https://knarkowicz.wordpress.com/2016/01/06/aces-filmic-tone-mapping-curve/) (CC0/MIT).
- [mattdesl/glsl-film-grain](https://github.com/mattdesl/glsl-film-grain) (MIT). [keijiro/KinoStreak](https://github.com/keijiro/KinoStreak) (MIT, README has no method).
  [keijiro/KinoGlitch](https://github.com/keijiro/KinoGlitch) (MIT, analog + digital glitch; for the glitch lane).
- [John Chapman, pseudo lens flare](https://john-chapman-graphics.blogspot.com/2013/02/pseudo-lens-flare.html).
- [Bart Wronski, separable disk-like DOF](https://bartwronski.com/2017/08/06/separable-bokeh/).
- [Interactive & Immersive HQ, stylizing footage with LUTs](https://interactiveimmersive.io/blog/content-inputs/stylizing-footage-with-luts/) (only the search snippet read).
- Search-only (abstract level, pages not read): arXiv 2608.14702 (halation per-channel radii), photrio.com halation thread, Blender Cycles
  rolling-shutter commits, DFKI rolling-shutter-with-velocities paper, USPTO "Simulated rolling shutter image data", Colin Barré-Brisebois hexagonal bokeh,
  McIntosh/Riecke/DiPaola polygonal bokeh (EG 2012).
- In-repo: `P_realtime_3d_looks.md` (P6 DOF, P7 finishing), `L_shader_sources_licences.md` (pmndrs, VIDVOX, grain), `docs/builds/palette_map.md`,
  `td-port/INVENTORY.md`, `td-port/flow_fx/README.md`, LEARNINGS T-18, T-46, T-47.
- Shadertoy default licence is CC BY-NC-SA 3.0 unless the author says otherwise [mem, not re-verified: the howto page returned 403]:
  treat any Shadertoy code as study-only and re-implement (user rule: licences irrelevant for research, but note the source).
