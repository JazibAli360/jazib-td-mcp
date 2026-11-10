# AC - Audio-reactive visual designs for TD 2025.31550 (web research, 26 Oct 2026)

Task: 32 audio-driven looks people build, what feature drives what, op chains with par names from our dump, then 8 build plans
on ONE shared analysis COMP. Research only: no TD call, nothing downloaded or installed, **no video watched**, Instagram/YouTube
pages are not readable by my tools. Extends `K_audio_reactive.md` (design rules, feeds, flash governor) and
`W_tutorials_control_audio_python.md` (analysis recipes R1-R6); does not repeat them. Scope (lead, 26 Oct): the TD MCP is general-purpose, so looks and plans are ranked for any real-time use (installations, interactive, VJ, screens) and the resolution is chosen per use case (section 3a); 1080x1920 is only the PF26 default. Build rules: flash limits from K 2.9 apply to anything an audience sees,
multi-pass pixel GLSL tears here (T-46) so use single pass or Compute mode (T-47), test audio = Audio File In of a local file.

Tags: **[V]** page/doc read this session (URL in section 5). **[S]** search snippet only. **[U]** unverified / my design / par not in dump.
**[D]** op and par names confirmed in `ops/ops_<FAMILY>_2025.31550.json`. Cost: **S** small, **M** medium, **L** large - all design guesses,
nothing measured. "Mac" = Rosetta, Vulkan/MoltenVK.

## 0. Summary

1. **Most public tutorials are teasers.** derivative.ca posts give author, date, video link and a 2-line blurb; the op chain is only in the
   YouTube video (S1-S14). So each "chain" below is *my* chain built from the blurb's idea plus par names verified in our dump. Written
   chains I could read are few: LucieMrc (MIT, spectrum strip on a 1080x1920 canvas, S15), the Derivative docs (S20, S21, S32) and a few forum threads.
2. **Eight feature types cover every look:** smoothed bands (low/mid/high), overall level, kick/snare/hat pulses, beat ramp (phase), a spectrum
   texture (1 row), a Shadertoy-layout 512x2 texture, a waveform window, and a depth master. All 32 looks read only those.
3. **Shadertoy audio is a 512x2 texture**: row 0 = FFT (48 kHz/4 over 512 texels = about 23 Hz per texel), row 1 = waveform, one texel per mono
   sample (S17). `Audio Spectrum CHOP -> CHOP to TOP` (S15, S19) rebuilds it, so audio shaders port by copy (licence caveat: `L_shader_sources_licences.md`).
4. **Rules that make audio looks safe on any big or public screen:** luminance only from slow bands or a 0.5 s-spaced pulse; kick drives motion (scale, zoom, force),
   not brightness; spectrum bars wide and few (stripe rule, K 2.9); one primary driver per look (K 2.8).
5. **Mac plan:** 6 of 8 build plans are single-pass GLSL or POP/instancing; only P3 (feedback; P4 has a small fade loop) needs a torn-frame check (T-46).
6. Not found: any tutorial for a spectrogram *terrain* (built from Texture 3D + Time Machine + POP lookup, [U]); nothing readable from Instagram
   TD artists; Paketa12 only as a name inside another post (S31).

## 1. Looks table (32)

Driver column: feature -> par (smoothing). Smoothing codes defined in section 2: **B** band lag 0.08/0.40 s, **Bs** slow lag 0.30/1.5 s,
**H** hit (Trigger decay 0.20, retrigger 0.12), **HL** luminance-safe hit (attack 0.07, decay 0.30, retrigger 0.5 s), **PH** beat ramp. Source ids S# in section 5.

| # | Look - source (author, date) | Audio -> parameter | Chain (key pars) | Cost / Mac |
|---|---|---|---|---|
| 1 | Spectrum bars (LED-style) - tdmcp "glsl" style [S22]; LucieMrc [S15] | spec TOP -> bar height (Lag 0.03/0.15 in spec) | `audiospectrumCHOP` (visual, fftsize 2048, frequencylog 1, outputmenu setmanually, outlength 64) -> `mathCHOP` gain -> `choptoTOP` (r, rowscropped) -> single-pass `glslTOP` floor(uv.x*8) bars [D] | S; ok. Max 8 wide soft bars (stripe rule) |
| 2 | Radial spectrum ring - tdmcp "geometric" style [S22] | spec TOP sampled by angle -> radius offset (B); level -> ring glow (Bs) | same spec TOP -> `glslTOP` polar: a=atan(p.y,p.x); texture(sTD2DInputs[0], vec2(a/6.2832+.5,.5)) [D] | S; ok |
| 3 | Spectrum strip as colour field - LucieMrc, undated, MIT [S15] | stereo spectrum -> R,G (pan); amplitude -> intensity | `audiospectrumCHOP` -> `choptoTOP` dataformat rg -> `constantTOP` black at the canvas size -> `compositeTOP` add [V/D] | S; ok |
| 4 | Waveform line / scope - tdmcp waveform sketch [S22] | wave CHOP window -> y of a line; level -> thickness (Bs) | `trailCHOP` (wlength 0.0233 s, resample on, samples 512) -> `choptoPOP` surftype linestrip -> Geometry COMP -> Render [D, mapping U] | S; ok |
| 5 | XY scope / Lissajous, phosphor - Derivative xyScope palette (ed. 30 Apr 2019) [S32]; Fenderson/Hansi3D site [S33] | L -> x, R -> y; gain from level (Bs) | stereo audio -> `choptoPOP`/`choptoSOP` (chan1=x, chan2=y) -> points -> `renderTOP` -> `feedbackTOP`+`levelTOP` opacity 0.9 decay [D] | M; ok (feedback: check T-46) |
| 6 | Oscilloscope-music shapes - Fenderson/Hansi3D patches [S33] | x=sin(t), y=cos(t); low -> radius, mid -> second freq | `waveCHOP`/`patternCHOP` x2 -> `mathCHOP` -> `choptoPOP`; ellipse=unequal gain, spiral=moving along a line (S33) | S; ok |
| 7 | Spectrum LED grid, instancing - tdmcp "instancing" style [S22] | spec bin(column) -> instance scale y (B) | `gridPOP` (cols 32, rows 32) -> Geometry COMP instancing on, instanceop=grid, instancesy from TOP `instancetop`/spec [D, T-15] | M; ok, 1k instances trivial |
| 8 | Sine-field spheres - Marco/elburz, 20 Jun 2025 [S2] | level (B) -> instance size; sines -> position | `patternCHOP` sin -> instance translate; `mathCHOP` level -> `instancesx..z` [V idea, D pars] | M; ok |
| 9 | Reactive boxes - Pao Olea, 18 Aug 2026 [S7] | beat+amplitude -> scale, rotation, colour; post FX last | boxes via `gridPOP` instancing; scale <- kick (H), rotation <- Speed CHOP of level, colour <- high (B) [idea V, chain U] | M; ok |
| 10 | Mandala instancing - elburz, 15 May 2024 [S9] | audio -> instance transform animated by `patternCHOP` | `patternCHOP` (sin/cos) -> translate; low (Bs) -> radius | M; ok |
| 11 | Audio point cloud - Crystal/elburz, 1 Jul 2023 [S10] | any audio -> instance scale/offset | `pointgeneratorPOP` -> Geometry COMP instancing; level (B) -> `instancesx` | M; ok |
| 12 | Kick feedback burst + zoom - blankensmithing, 28 Dec 2021 [S11]; IIHQ drawn-content [S26] | kick HL -> `transformTOP` sx/sy 1.00..1.03; low Bs -> hue drift | `feedbackTOP`(top=loop Null) -> `transformTOP` (sx,sy,rotate) -> `levelTOP` opacity 0.96 -> `compositeTOP` add new element [D, A §6 #1 built live] | M; **T-46 check** |
| 13 | Voxel ripples (optical flow + instancing) - dcheesman, 6 Aug 2024 [S12] | audio drives ripple source; flow advects | `opticalflowTOP` on a driven source -> instancing with TOPs [chain U] | L; flow ok, check torn frames |
| 14 | Tunnel / zoom on bass - UE4+TD tunnel listing [S30]; tdmcp "feedback" ring tunnel [S22] | low Bs -> tunnel speed via `speedCHOP`; kick HL -> FOV/zoom pulse | single-pass `glslTOP` tunnel: z = uTime_acc + 1/r; uTime_acc from Speed CHOP (speed = low*k) [D] | S; ok, no feedback |
| 15 | Spectrogram waterfall (history texture) - own design from Time Machine/Texture 3D docs [S20,S21] | spec column -> history; age -> x | spec 1x256 (rotate) -> `texture3dTOP` (cachesize 256, step 1) -> `timemachineTOP` (second input = `rampTOP` horizontal; blackoffset -256, whiteoffset 0 indices) [D, behaviour U] | M (256x1x256 tiny); ok |
| 16 | Spectrogram terrain - Aristides.Lab wavefield idea [S18] + design | spectrogram height -> grid Y; kick HL -> camera ty | `gridPOP` 128x128 -> `lookuptexturePOP` (top=waterfall, `usedepthoffset`) -> `mathPOP`/`transformPOP` to P.y -> Geometry COMP -> Render [D, wiring U] | M; ok |
| 17 | POP particles + audio forces - elburz/Joel, 19 Oct 2026 [S4]; elburz POP audio, 21 Oct 2025 [S3] | kick H -> `forceradialPOP` radialstrength; mid B -> `noisePOP` amp0; level -> birthrate | `pointgeneratorPOP` -> `particlePOP` (targetpop=Null POP) -> `forceradialPOP` -> `noisePOP` -> `nullPOP`; Select POP in Geometry COMP, `pointspriteMAT` [D, S4 doc] | M-L (maxparticles 100k); ok |
| 18 | Spectrogram from Particle POP - exsstas, 23 Jul 2026 [S5] | spectrum bins -> particle attributes over time | Particle POP with attribute-driven emission (`emissionmode attr`) [V idea, chain U] | M; ok |
| 19 | Wavefield POP, audio waveform equation - Aristides.Lab, 7 Jun 2026 [S18] | waveform (Resample CHOP) -> displacement; Amplitude <- level (B) | `glslPOP` compute displaces points; TOX uses Resample CHOP to cut cost [V] | M; third-party tox, licence unstated |
| 20 | Audio-driven noise field - blankensmithing [S11]; Hermes chain note [S25] | low -> noise `period`/`amp`; mid -> `harmon`; high -> grain | `noiseTOP` (type simplex3d; tz = Speed CHOP of level) -> `levelTOP` -> palette `lookupTOP` [D] | S; ok |
| 21 | Ink / fluid-ish displace feedback - IIHQ drawn content [S26] | low (B) -> `displaceTOP` displaceweightx/y; kick HL -> noise offset | `noiseTOP` -> `displaceTOP` -> `feedbackTOP` after displace -> `levelTOP` [D] | M; **T-46 check** |
| 22 | Reactive geometry: sphere deform - IIHQ beginner guide, 22 May 2025 [S1] | kick (Select->Math 0.7..3->Filter->Null) -> Noise amplitude | POP version: `spherePOP` -> `noisePOP` amp0 <- kick H / low B -> Geometry COMP -> Render (SOP twin: Sphere SOP + Noise SOP `amp`, CPU) [D] | M; ok |
| 23 | Reactive grid terrain - IIHQ SOP lesson [S27] | level (Trail+Analyze) -> noise amplitude | `gridPOP` -> `noisePOP` amp0 <- level (Bs) | M; ok |
| 24 | Beat-synced camera in a 3D scene - Pao Olea Reactive CHOP, 15 Oct 2024 [S8] | beat ramp PH -> dolly tz; level Bs -> orbit speed; kick HL -> FOV | `beatCHOP` ramp -> `mathCHOP` cos -> cameraCOMP tz; `speedCHOP` -> ry; `fov` kick punch [D] | S; ok |
| 25 | Strobe within limits - K 2.9 rules | kick HL only, depth <= 0.08 | `levelTOP` brightness2 = 1 + 0.08*kick_lum on a base of >= 0.35 luma; never pure white; <= 2 per s | S; test on the real output / viewer |
| 26 | Colour/palette shift per section - own, from K 2.7 | `bar` count / `every8` hold -> palette index; centroid -> hue | `holdCHOP` on bar pulse -> `lagCHOP` lag1=lag2=2 s -> `lookupTOP` index (palette ramp, `rampTOP`) [D] | S; ok |
| 27 | RGB split / chroma on hits - Reactive boxes post FX [S7]; chromatic aberration tutorial (not audio) [S28] | snare HL -> channel offset 0..6 px | 3x `transformTOP` (tx +-) + `channelmixTOP` + `compositeTOP` add, or single-pass `glslTOP` with 3 texture() taps [D] | S; ok |
| 28 | Audio-reactive typography - audiodevout, 9 Oct 2025 [S13] | band -> whole-word scale/glow/displace; NEVER split letters (project rule) | `textTOP` -> `displaceTOP` (noise driven by mid B) -> glow; instancing only around the word, not on glyphs | M; ok |
| 29 | Shadertoy audio port - Carrigan 2020 [S17]; GregFinger converter [S16] | spec2 TOP (512x2) -> iChannel0 | `choptoTOP` rows of [spec 512, wave 512] -> `glslTOP` input 0; sample `texture(sTD2DInputs[0], vec2(x, 0.25))` for FFT, `0.75` for waveform [V layout, TOP row order U] | S-M; ok; licence check |
| 30 | Edge outline pulse - own | high (B) -> `edgeTOP` strength; hat -> small sparkle | `edgeTOP` select luminance, strength <- high -> `compositeTOP` screen [D] | S; ok |
| 31 | Bloom pulse - own | low (Bs) -> `bloomTOP` bloomintensity (0.6..1.0) | `bloomTOP` bloomthreshold 0.6 [D] | M (blur); ok |
| 32 | Kaleido spin - own | mid Bs -> Speed CHOP -> `mirrorTOP` rotate; kick no | `mirrorTOP` (extend mirror, rotate <- speedCHOP) [D] | S; ok |

## 2. Shared analysis COMP spec: `AC_audio` (Base COMP, build once, looks read only its outputs)

Every look wires to **Null CHOP `out_ctl`** (plus the two TOPs/one CHOP below). All values 0..1 and already multiplied by `Depth` (reactivity master).
Names are lowercase, one word, so `op('AC_audio/out_ctl')['kick']` and exports are unambiguous. Custom pars (page `Audio`, capital first letter, T-00e): `Source` (menu 0 file, 1 device), `Audiofile`, `Trim` (0..4, default 1), `Depth` (0..1, 0.7), `Bpm`, `Lumdepth` (0.08), pulse `Beat1`.

| Channel / output | Type | How (ops and key pars, [D] unless [U]) | Smoothing |
|---|---|---|---|
| source | CHOP | `audiofileinCHOP` (file=Audiofile, play 1, repeat on) [D]; `audiodeviceinCHOP` only on the user's go-ahead [U, not in dump]; `switchCHOP` index=Source; `mathCHOP` gain=Trim -> Null `n_stereo` (keeps L/R for scopes); `mathCHOP` chanop avg -> mono `n_mono` | none |
| `low` `mid` `high` | CHOP | `n_mono` -> 3x `audiofilterCHOP` (lowpass 120 Hz; bandpass ~1.2 kHz; highpass 6 kHz; cutofffrequency [D]) -> `analyzeCHOP` function rmspower [D] -> auto-gain (below) -> `lagCHOP` **B**: lag1 0.08, lag2 0.40 | B (fast attack 2-3 frames, ok for luminance) |
| `lowslow` | CHOP | `low` -> `lagCHOP` lag1 0.30, lag2 1.5 (energy for camera, hue, speed) | Bs |
| `level` | CHOP | `n_mono` -> `analyzeCHOP` rmspower -> auto-gain -> `lagCHOP` lag1 0.10, lag2 0.50 | |
| `kick` | CHOP | `low` fast path: audiofilter lowpass 120 Hz -> analyze rmspower -> `lagCHOP` 0.01/0.15 -> `triggerCHOP` threshup 0.5, triggeron increase, attack 0, peaklen 0.04, decay 0.20, release 0, retrigger 0.12 s, clamppeak [D] (W R3) | H |
| `kick_lum` | CHOP | same trigger, attack 0.07, decay 0.30, **retrigger 0.5 s** (max 2 per s; K 2.9). ONLY this channel may touch whole-frame brightness | HL |
| `snare` `hat` | CHOP | bandpass 1.8 kHz / highpass 8 kHz -> analyze -> lag -> trigger as `kick`, retrigger 0.15 | H |
| `beat` `bar_ramp` | CHOP | `beatCHOP` (playmode global, ramp, pulse, beat, bar [D]); tempo from custom `Bpm` via `op('/local/time').tempo` (typed per test song; no live BPM here: that is JZBA's job, K) | none |
| `depth` | CHOP | `Depth` as a constant channel for looks that want to scale their own range | none |
| `out_spec` | TOP | `n_mono` -> `audiospectrumCHOP` (mode visual, fftsize 2048, frequencylog 1, highfreqboost 0.75, outputmenu setmanually, outlength 256) -> `mathCHOP` gain (SpecGain) -> `lagCHOP` 0.03/0.15 -> `choptoTOP` (r, rowscropped) -> Null TOP: **256x1** | per bin |
| `out_spec2` | TOP | `audiospectrumCHOP` outlength 512 + `trailCHOP` (wlength 0.0233 s, resample on, samples 512) of the waveform -> `renameCHOP` spec, wave -> `mergeCHOP` -> `choptoTOP` (r, rowscropped): **512x2**, Shadertoy layout (S17); row order [U] | |
| `out_wave` | CHOP | stereo `trailCHOP` window 512 samples (for scopes) | none |

**Auto-gain per band (W R5, [U] design):** `lagCHOP` lag1 0.05 / lag2 20 s -> `peak`; `mathCHOP` with 2 inputs chopop div (signal/peak, [D menu]) -> `limitCHOP` type clamp, min 0, max 1 [D]; floor: `postoff` so silence does not amplify. Gain changes slowly, never inside a bar.
**Safe defaults for looks:** luminance modulation <= `Lumdepth` 0.08 (linear), base floor >= 0.35 luma, big accents <= 1 per 8 bars, `Depth` 0 fades everything to free-running within 1 s.
**Verify by values, not ears:** with a looped test track the agent reads `out_ctl` via `td_get_pars`/Info CHOP; kick count per bar and `peak` must be plausible. Whether the Rosetta build hears a real device is still open (`ops/CHOP.md` 2).

## 3. Build plans: top 8, ranked for general use (each look is its own Base COMP `LK_<name>` with custom pars `Resw`, `Resh`, `Reactivity` and ends in a Null TOP `out`)

### 3a. Resolution per use case (all values [U] design choices; set `Resw`/`Resh` once, every `resolutionw/h`, camera aspect and pixel offset reads them)
| Use | Canvas | Why |
|---|---|---|
| VJ / projector / landscape screen | 1920x1080 (4K 3840x2160 only if the GPU holds fps) | standard output; bars/ring/tunnel designed aspect-free via `uv*vec2(Resw/Resh,1)` |
| Vertical screen, phone-style, PF26 look work | 1080x1920 (user rule for PF26) | portrait; same plans, swap values |
| Installation / interactive kiosk | native panel size; preview at half (`resmult` 0.5) | cooks less; only the final Null at full |
| LED wall or multi-face canvas | the canvas size (e.g. PF26 9984x3840 per `C_pf26_fit.md`) rendered offline or after a fps test (E) | A section 3: float noise at that size was cooked; feedback loops at that size are untested |
| Quick iteration / agent testing | 540x960 or 960x540 | faster `td_perf`, still shows the logic |
Rules that do not depend on use: feedback and multi-pass stay at the smallest size that looks right; offset effects are fractions (RGB split `off = snare*0.006` = 0.6% of width) not pixels.

### 3b. Ranking (general use; #1 first). Fit: V=VJ/live, I=installation, X=interactive, S=screen/signage; cost per section 1; Mac risk per T-46
| Rank | Plan | Best for | Why this rank |
|---|---|---|---|
| 1 | P7 Section Aurora | V I S | all single pass, reads well on any aspect, palette per section, safest on a Mac |
| 2 | P1 Spectrum Glass | V S X | the harness that ports Shadertoy audio shaders; trivial cost |
| 3 | P8 Camera Orbit on Reactive Sphere | V I S | 3D depth, beat-synced camera, POP only |
| 4 | P2 Instanced Reactive Grid | V I | scales to any size by grid counts |
| 5 | P6 Force Particles | V I X | strongest "energy"; needs particle-count tuning |
| 6 | P4 Phosphor Scope | V X | iconic, cheap; feedback fade needs a check |
| 7 | P5 Spectrogram Waterfall + Terrain | I S | informative; Time Machine step is unproven |
| 8 | P3 Kick Tunnel Feedback | V | classic, but the only plan that needs the T-46 torn-frame check |


Common start (step 0, not counted): `AC_audio` exists and plays a local file (`Source` 0); pick the canvas from 3a. For every GLSL TOP: `outputresolution custom`, `resolutionw`/`resolutionh` = the look's `Resw`/`Resh`, `format rgba16float` [D]; shader uses `out vec4 fragColor` + `TDOutputSwizzle` (A §6 #2). After each step `td_errors`; after the last `td_layout flow`.

**P1 Spectrum Glass (looks 1, 2, 29; single pass).** Why: the harness every shader port reuses.
1 `glslTOP` `g_bars` (pixel mode); 2 DAT `g_bars_pixel`: 8 soft bars, `float h = texture(sTD2DInputs[0], vec2((floor(uv.x*8.)+.5)/8., .5)).r`, bar edge `smoothstep`, gap 25% of width (stripe rule); 3 input 0 = `out_spec`;
4 `vec0name uLevel`, `vec0valuex` = `op('../AC_audio/out_ctl')['level']`; luminance of bars <= 0.6; 5 second `glslTOP` `g_ring` same input, polar mapping, radius = 0.30 + 0.20*h; 6 `compositeTOP` operand add of ring and bars (ring in upper 60%, bars lower 25%);
7 `rampTOP` PRISM-ish 2 colours -> `lookupTOP` on luminance; 8 `glslTOP` `g_toy`: input 0 = `out_spec2`, FFT `texture(.., vec2(x,.25))`, waveform `vec2(x,.75)` (S17), paste a Shadertoy audio shader after checking licence (L); 9 `switchTOP` between `g_ring` and `g_toy`; 10 `levelTOP` + `nullTOP out`.
Check: bars move with the track (read `out_spec` max > 0.3), 0 compile warnings (Info DAT, T-02). Cost S.

**P2 Instanced Reactive Grid (looks 7, 9, 10).**
1 `gridPOP` surftype points, cols 24, rows = cols*Resh/Resw, sizex 2.0, sizey 3.5; 2 `geometryCOMP` `inst`: instancing on, instancecountmode oplength, instanceop=grid (T-15: not instancepop); 3 inside: `boxPOP` or `spherePOP` small (scale 0.05); 4 `instancesy` from `out_spec` via `instancetop` mapping: bin = column index (map columns 24 -> 24 of 256 log bins) [U]; 5 `instancerz` <- `speedCHOP` of `level` * 40 deg/s; 6 `instancecolormode` multiply, `instancecolorop` palette lookup, hue <- `high` (B);
7 kick H -> `scale` par of the Geometry COMP 1.0..1.08 (motion, not luminance); 8 `cameraCOMP` tz 6, fov 40; 9 `lightCOMP` + `phongMAT` (diffr/diffg/diffb brand colour); 10 `renderTOP` res Resw x Resh, antialias aa4; 11 `bloomTOP` bloomintensity <- `lowslow`; 12 `nullTOP out`. Cost M. Mac: Geometry COMP instancing fine (T-15); instance textures limit 128 on macOS (S21), unused.

**P3 Kick Tunnel Feedback (looks 12, 14).** Mac: T-46 check mandatory.
1 `circleTOP` ring radius 0.2, border only, alpha 1; 2 `feedbackTOP` `fb` top = `nullTOP loopend`; 3 `transformTOP` sx=sy = `1.004 + 0.02*low` (slow), rotate = `op(speedCHOP)*0.3`; 4 `levelTOP` opacity 0.965 (decay); 5 `compositeTOP` add, input 1 = ring; ring radius <- `kick` H (0.2..0.26);
6 `hsvadjustTOP` hueoffset <- `lowslow`*0.2; 7 `nullTOP loopend` (feeds step 2); 8 `levelTOP` clamphigh2 0.85 + final brightness cap (Lumdepth) -> `out`. 9 Force-cook loop end each frame (T-29: Execute DAT pump). 10 Check: record 300 frames `moviefileoutTOP` ProRes, ffprobe, look for torn/stale frames (T-46); if bad, replace step 3-5 by a Compute-mode `glslTOP` that reads its own previous frame (T-47). Cost M.

**P4 Phosphor Scope (looks 4, 5, 6).**
1 `n_stereo` -> `trailCHOP` (wlength 0.02, resample 1024) = `out_wave`; 2 `mathCHOP` gain `0.8*(1+level)` (keep within +-1); 3 `choptoPOP` `chop`=that, surftype points (or linestrip); the x/y mapping via `attrs`/`chanssel` [U: set chan1 -> P(0), chan2 -> P(1)]; 4 `geometryCOMP` + `constantMAT` colour, `pointspriteMAT` size 3 for dots;
5 `cameraCOMP` ortho (projection ortho, orthowidth 2.2); 6 `renderTOP` Resw x Resh, black bg; 7 `feedbackTOP` + `transformTOP` (scale 1.0) + `levelTOP` opacity 0.88; 8 `compositeTOP` add render + feedback; 9 `bloomTOP` threshold 0.4; 10 optional second `waveCHOP` pair for Lissajous test (x=sin(2*pi*f1*t), y=sin(2*pi*f2*t), f2/f1 <- mid); 11 `nullTOP out`. Cost M. Stripe rule: thin moving lines on black are fine; do not fill the frame with parallel lines.

**P5 Spectrogram Waterfall + Terrain (looks 15, 16).**
1 `out_spec` -> `transformTOP` rotate 90 (becomes 1x256 column) -> `texture3dTOP` `t3d` (type texture3d, cachesize 256, step 1, active on) [D];
2 `rampTOP` horizontal (type horizontal, 0..1) 256x256 = age map; 3 `timemachineTOP` input 0 = t3d, input 1 = ramp, blackoffset -255, whiteoffset 0, unit indices -> 256x256 spectrogram (x = age, y = frequency) [U: behaviour with 1-px-wide layers];
4 `lookupTOP` palette -> `levelTOP` -> preview strip (waterfall look done); 5 `gridPOP` 160x160 sizex 3, sizey 3; 6 `lookuptexturePOP` top = step-3 TOP, lookupindexattr0 = `uv`-style attribute [U name] -> attribute `h`; 7 `mathPOP` scale h*0.6 -> add to P.y;
8 `geometryCOMP` + `phongMAT`, `cameraCOMP` tx 0, ty 1.8, tz 5, rx -25; 9 dolly: camera tz = 5 - 0.5*cos(2*pi*`bar_ramp`) (PH, motion only); 10 `renderTOP`; 11 `nullTOP out`. Cost M; texture history memory: 256x256x4x2 B ~ 0.5 MB [design].

**P6 Force Particles (look 17).** Based on A §6 #5 (verified minimal) plus the force chain (unverified).
1 `pointgeneratorPOP` sphere, numpoints 2000; 2 `particlePOP` maxparticles 80000, birthrate <- `level`*8000, life 3, damping 0.1, initvelocity small; `targetpop` = `nullPOP` (loop end); 3 `forceradialPOP` radial on, radialstrength <- `kick`*3 (set by CHOP export, [U] Map page is attribute-only per S20), falloff scurve, radius 2;
4 `noisePOP` amp0 <- `mid`*0.4, period 0.7 (swirl); 5 `nullPOP` loop end; 6 `geometryCOMP` + `selectPOP` (pop = particle), `pointspriteMAT` pointsize 4, additive blending on [D]; 7 `cameraCOMP`; 8 `renderTOP` Resw x Resh, bg alpha 1; 9 `bloomTOP`; 10 colour: `particlePOP` attr Cd life-ramped. 11 pump + 300-frame check for stuck count (T-02). Cost M-L: lower maxparticles first.

**P7 Section Aurora (looks 20, 26, 27, 30, 31).** The all-round look; everything single pass.
1 `noiseTOP` simplex3d at Resw x Resh, period 0.8 (low-freq), harmon 3, tz = `absTime.seconds*0.1 + speed(level)`; 2 `noiseTOP` period `0.5+0.8*mid`; 3 `displaceTOP` (input 0 = noise A, input 1 = noise B) displaceweightx 0.05+0.1*low;
4 `holdCHOP` (sample = `bar_ramp` reset) -> channel `palette_idx` = random 0..4 each bar when `bar % 8 == 0` [U logic via CHOP Execute]; 5 `lagCHOP` lag1=lag2=2.0 s; 6 `lookupTOP` index = luminance of 3, lookup = 5-stop `rampTOP` per palette, `switchTOP` by palette_idx; 7 `bloomTOP` bloomintensity <- `lowslow`;
8 RGB split: `glslTOP` single pass: `r = texture(in, uv + vec2(off,0)).r; g = texture(in, uv).g; b = texture(in, uv - vec2(off,0)).b`, off = `snare` * 0.006 (about 6 px at 1080 wide); 9 `levelTOP` brightness2 = 1 + `Lumdepth`*`kick_lum`; 10 `nullTOP out`. Cost S-M.

**P8 Camera Orbit on Reactive Sphere (looks 22, 24, 32).**
1 `spherePOP` freq 5 (geodesic/ico type), radius 1; 2 `noisePOP` amp0 = `0.1 + 0.5*low` (B), period 1.1, offset tz = `absTime.seconds*0.3`; 3 `normalPOP` (recompute normals) [D exists]; 4 `geometryCOMP` + `pbrMAT` or `phongMAT` colour; 5 `lightCOMP` warm, dimmer 1; second light cool from the back;
6 `cameraCOMP` orbit: parent null `rig` with `ry` = `speedCHOP`(level*30 deg/s), `rx` 10; camera tz = `5.5 - 0.6*sin(2*pi*beat ramp)` (PH, motion only); fov punch: `fov` = 40 - 4*`kick` (H) [D]; 7 `renderTOP` Resw x Resh aa4; 8 `edgeTOP` strength <- `high` composite screen (look 30); 9 `bloomTOP`; 10 `nullTOP out`. Cost M; if CPU SOP twin is used the SOP is frozen (SOP_MAT note), prefer POP.

## 4. Open questions

1. **Chains in the videos:** the user could give transcripts for 3-5 videos (suggest S1 audio-reactive beginner, S4 POP particles, S12 voxel ripples, S11 blankensmithing); until then chains here are [U] design.
2. Does `choptoPOP` take `chan1/chan2` as P(x,y) directly, and what are its attribute-mapping par names? (look 4/5, P4 step 3.)
3. `timemachineTOP` with a 1-pixel-wide Texture 3D stack (P5 step 3) and `lookuptexturePOP` attribute name for UV: probe first.
4. Row order of a 2-channel `choptoTOP` (rowscropped): is the first channel the bottom row? Decides whether Shadertoy row 0 (FFT) maps to y 0.25.
5. Is `forceradialPOP` strength drivable by a CHOP export, or only via attribute Map (S20 says attribute only)?
6. Real device input on Rosetta (mic permission, K 2.2) and BPM for the test song: typed `Bpm` only; live tempo belongs to JZBA.
7. Licences: GregFinger converter (none stated), Aristides.Lab wavefield tox (none stated), Shadertoy shaders (default CC BY-NC-SA, see L). Reference only until checked.
8. Measured cost: all S/M/L classes and the 128-instance-texture limit are unmeasured; run `td_perf` after a few normal frames (T-05).

## 5. Sources (S#: title - author - date - URL; all fetched 26 Oct 2026 unless marked)

TouchDesigner community tutorials (derivative.ca; page = teaser, chain in video)
- S1 Beginner's Guide to TD Audio Reactive Visuals - elburz/IIHQ - 22 May 2025 - https://derivative.ca/community-post/beginners-guide-touchdesigner-audio-reactive-visuals/71998 [V]; chain from search snippet of https://interactiveimmersive.io/blog/touchdesigner-3d/audio-reactive-visuals-a-beginner-guide/ [S] (Select kick -> Math 0.7..3 or 0.7..5 -> Filter -> Null -> Noise SOP amplitude; Low/Mid/High smooth, Kick/Snare/Rhythm 0/1 pulses)
- S2 Audio Reactive Visualizers in TD - Marco/elburz - 20 Jun 2025 - https://derivative.ca/community-post/tutorial/audio-reactive-visualizers-touchdesigner/72251 (video https://www.youtube.com/watch?v=zcPlFsEk-as) [V]
- S3 Using POPs to Drive Audio Reactive Visuals - elburz/IIHQ - 21 Oct 2025 - https://derivative.ca/community-post/using-pops-drive-audio-reactive-visuals/73078 [V teaser], chain Math -> Audio Spectrum -> Trim -> average -> trail -> multiply -> threshold -> Trigger [S] via https://interactiveimmersive.io/blog/touchdesigner-operators-tricks/using-pops-to-drive-audio-reactive-visuals/
- S4 Audio Reactive Particles using TD POPs - elburz (presenter Joel) - 19 Oct 2026 - https://derivative.ca/community-post/tutorial/audio-reactive-particles-using-touchdesigner-pops/75525 (video https://www.youtube.com/watch?v=4shfXcXvLDk) [V]
- S5 Audio Spectrogram from Particles POP - exsstas - 23 Jul 2026 - https://derivative.ca/community-post/tutorial/audio-spectrogram-particles-pop/75080 (video https://www.youtube.com/watch?v=QnX8WBQ6nXU) [V]
- S6 TD Audio Reactive Visuals with GLSL - elburz (Lake Heckaman) - 19 Nov 2025 - https://derivative.ca/community-post/tutorial/touchdesigner-audio-reactive-visuals-glsl/73339 (video https://www.youtube.com/watch?v=1pO8rA-vvUo) [V]
- S7 Reactive Boxes (Tutorial 32) - Pao Olea - 18 Aug 2026 - https://derivative.ca/community-post/tutorial/reactive-boxes-touchdesigner-tutorial-32/75201 [V]; Reactive Noodles (28) - 28 May 2026 - https://derivative.ca/community-post/tutorial/reactive-noodles-touchdesigner-tutorial-28/74697 (video https://youtu.be/V2nJHYzZZrw) [V]
- S8 Reactive CHOP (Tutorial 08) - Pao Olea - 15 Oct 2024 - https://derivative.ca/community-post/tutorial/reactive-chop-touchdesigner-tutorial-08/70452 (video https://www.youtube.com/watch?v=R7U_0zz4nmU) [V]: beat/rhythm -> rotation, scale, line animation, light intensity
- S9 Audio Reactivity and Instancing - elburz - 15 May 2024 - https://derivative.ca/community-post/tutorial/audio-reactivity-and-instancing-tutorial/69454 (video https://www.youtube.com/watch?v=FohwxBzbNwY) [V]
- S10 Audio Reactive 3D Point Clouds - elburz (Crystal) - 1 Jul 2023 - https://derivative.ca/community-post/tutorial/audio-reactive-3d-point-clouds-touchdesigner/68021 [V]
- S11 Audio-Reactive Visuals in TD - blankensmithing (Torin Blankensmith) - 28 Dec 2021 - https://derivative.ca/community-post/tutorial/audio-reactive-visuals-touchdesigner/65638 (video https://www.youtube.com/watch?v=R7sAomk2vR4) [V]
- S12 Audio Reactive Voxel Ripples - dcheesman - 6 Aug 2024 - https://derivative.ca/community-post/tutorial/audio-reactive-voxel-ripples/69907 (video https://youtu.be/47Sk1aYrY3k) [V]
- S13 AudioReactive Text with Tracing and Instancing - audiodevout - 9 Oct 2025 - https://derivative.ca/community-post/tutorial/audioreactive-text-tracing-and-instancing-touchdesigner-tutorial/73009 (video https://youtu.be/sDOvmhu6DWY; files on Patreon) [V]
- S14 Beat Detection - elekktronaut - 13 Feb 2020 - https://derivative.ca/community-post/tutorial/beat-detection/62551 [V]; Instancing for Generative Art session 4 (Spheres and Audio Setup) - Music Hackspace - https://musichackspace.org/?p=8015 [S]
Written / doc sources
- S15 TD_audioreact_love_EN - LucieMrc - undated, MIT - https://github.com/LucieMrc/TD_audioreact_love_EN [V]
- S16 TD-Shadertoy_Converter - GregFinger - undated, licence not stated - https://github.com/GregFinger/TD-Shadertoy_Converter [V]
- S17 Shadertoy audio texture layout 512x2 - richard carrigan, Cycling '74 forum - ~11 May 2020 - https://cycling74.com/forums/input-texture-into-gl3-shader-toy-loader [V]; FFT sampled as texture(iChannel0, vec2(x, 0.1)).x then squared - pietroLama, Processing forum - Nov 2017 - https://forum.processing.org/two/discussion/comment/110281/ [V]
- S18 Wavefield TOX (POPs without hassle) - Aristides.Lab - 7 Jun 2026 - https://derivative.ca/community-post/tutorial/wavefield-tox-pops-without-hassle/74758 [V]
- S19 Chop Lookup in GLSL POP - illusive / Guillaume.L - 24 and 30 Mar 2026 - https://forum.derivative.ca/t/chop-lookup-in-glsl-pop-code-review-best-practices/974814 [V]: CHOP to TOP, then texture() in GLSL, extend mode on the TOP
- S20 Derivative docs: Particle POP (ed. 6 Sep 2026) https://docs.derivative.ca/Particle_POP ; Force Radial POP https://docs.derivative.ca/Force_Radial_POP [V]
- S21 Derivative docs: Audio Spectrum CHOP https://docs.derivative.ca/Audio_Spectrum_CHOP ; Trail CHOP https://docs.derivative.ca/Trail_CHOP ; Cache TOP https://docs.derivative.ca/Cache_TOP ; Time Machine TOP https://docs.derivative.ca/Time_Machine_TOP ; Geometry COMP https://docs.derivative.ca/Geometry_COMP [V]
- S32 Palette xyScope (ed. 30 Apr 2019) https://docs.derivative.ca/Palette:xyScope [V] 
- S33 Oscilloscope Music (Jerobeam Fenderson / Hansi3D), Pure Data page, undated - https://oscilloscopemusic.com/puredata.php [V] 
- S22 tdmcp "create_audio_reactive" tool listing (unofficial MCP) - https://glama.ai/mcp/servers/lucasmaher-hash/touch-designer-mcp/tools/create_audio_reactive [V]: styles glsl bars, geometric radial, particle dots, feedback ring tunnel, instancing LED grid; sidechain_duck, transient_gate
- S25 TD network-patterns reference (unofficial Hermes skill mirror, unreachable on re-fetch) [S]: Audio File In -> Spectrum -> Math -> Noise TOP pars -> Level -> Feedback -> Composite
- S26 IIHQ audio reactive drawn content (Render -> Displace -> feedback component) - https://interactiveimmersive.io/blog/content-inputs/audio-reactive-drawn-content-in-touchdesigner/ [S]
- S27 IIHQ SOPs/MATs lesson (Audio Device In -> Trail -> Analyze -> Noise amp) - https://interactiveimmersive.io/touchdesigner-operators-sops-and-mats/ [S]
- S28 Chromatic aberration effect - https://derivative.ca/community-post/tutorial/chromatic-aberration-effect/69723 [S] (not audio)
- S30 UE4 infinite tunnel audio-reactive loop (TD over OSC) - https://derivative.ca/community-post/tutorial/ue4-infinite-tunnel-audio-reactive-loop-unreal-engine-touchdesigner/65160 [S listing]
- S31 Paketa12 only as a credit in another derivative.ca post [S]; mapping guides (bass -> scale, treble -> glow, onset -> pop): https://skills.sh/heygen-com/hyperframes/audio-reactive [S]
Project: `K_audio_reactive.md` 2.6-2.9, `W_tutorials_control_audio_python.md` R1-R6, `A_td_2025_howto.md` section 6, `ops/*_2025.31550.json`, `LEARNINGS.md` T-02, T-05, T-15, T-29, T-46, T-47.
