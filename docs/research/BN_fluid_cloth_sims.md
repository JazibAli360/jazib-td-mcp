# BN - Fluid, smoke, cloth and soft-body simulation in TouchDesigner on this Mac, plus two clean-room build specs

Researched 26 Oct 2026 (offline research lane). Nothing loaded into TD, no jazib-td tool called, no downloaded code run, no pip, no logins. Build target TD 2025.31550, M1 Max, Rosetta x86_64 (Python 3.11, numpy 2.1.2, cv2 4.11), Vulkan/MoltenVK. Facts are tagged: [V] read at the source this session, [L] our own notes/measurements (LEARNINGS, docs/research), [S] search summary only, UNVERIFIED = do not rely. Licences are noted, not a gate (user rule: licences irrelevant for research).

Read-only local copy: `research_src/BN_fluid_cloth_sims/touchFluid/` (9 `.frag` files + LICENSE, plain text from raw.githubusercontent.com, never executed).

## 1. Findings in six lines

1. The Mac constraint decides the design: **every multi-step sim must be GLSL TOP in compute mode** (T-46: pixel-mode chains of GLSL TOPs sample unfinished inputs on 31550; T-47: compute mode was right 340/340 at 256x256 32F and 441/441 at 1080x1920 16F; Nvidia Flex/Flow/CUDA do not exist on macOS [L F13]).
2. Every free TD fluid on the market is a **pixel-shader multi-pass Navier-Stokes** that predates this finding (touchFluid 2015-16 shaders [V], Fluid Simulation TOPs 2025 [V page], Dobryakov WebGL [L]). Their maths is reusable; their node chains are exactly what T-46 says not to trust. **No source anywhere does stable fluids in a TD compute-mode GLSL TOP** (searched; none found), so that part is new work.
3. Cloth in TD is either CUDA-only (ClothPOP, ClothPOP PRO), or non-commercial compute (Pelz Constraint Simulation Tool, 9.85 MB zip, "NON COMMERCIAL USE ONLY", build/Mac not stated), or a 2010 GLSL 1.2 file that stopped rendering in later builds. Nothing is clean for Mac 31550 as is.
4. For cloth I chose a **position-texture (grid in an rgba32f TOP) Verlet/XPBD solver in compute GLSL**, not POPs: POPs on macOS have a recorded crash class around Feedback POP + Null (fixed only in 32280+ [L F11]), GLSL POP multi-pass and Connected-mode neighbours on quads are unverified on 31550 [L F4/F7], whereas compute-TOP chains are proven here.
5. Reaction-diffusion and physarum are not fluids but share the machinery. RD is the same one-texture compute step (spec 2.9 gives it as a free extra `Kind` of the same COMP shell). Physarum needs a scatter (deposit) which on Mac has no float atomics [L F13]; leave it to O_generative_simulations 4.3 and `Noisemaker` (needs 32820+, FUTURE).
6. 3D fluid/SPH/Flex: not recommended on this Mac (no Flex; a 3D grid solver is pass-count and VRAM-heavy under MoltenVK). Recorded as FUTURE only.

## 2. Landscape (ranked for us)

Status columns: **Mac/31550** = what is known about running it here. All "not downloaded" rows are page-level facts only.

| # | Tool / asset / repo | What | Licence | Mac / 31550 status | Use for us |
|---|---|---|---|---|---|
| 1 | **kamindustries/touchFluid** [V] ([repo](https://github.com/kamindustries/touchFluid)) | "lightweight 2d Semi-Lagrangian fluid solver": vorticity confinement, temperature, buoyancy, obstacles; `fluid.tox` + `touchFluid.toe` + 9 shaders in `include/` (advect, buoyancy, divergence, impulse, jacobi, obstacleBounds, subGradient, vorticity1/2), 64 commits, 237 stars [L]; (c) 2015-2016 Kurt Kaminski, originally CUDA | **MIT** [V LICENSE] | Pixel-mode multi-pass, TD build not stated, pre-Vulkan; **expected to show T-46 stale-input artefacts** (UNVERIFIED, not loaded). Shaders read and understood (section 4) | Best reference for the obstacle-aware boundary handling and the buoyancy/temperature split. Port shaders to compute (clean-room, MIT allows even copying; we rewrite anyway) |
| 2 | **Pavel Dobryakov WebGL-Fluid-Simulation** ([repo](https://github.com/PavelDoGreat/WebGL-Fluid-Simulation)) [L O 4.8] | Reference step order and constants: sim 128, dye 1024, pressure 20 iterations, curl 30, vel dissipation 0.2; pressure warm-started and decayed | **MIT** | Algorithm only (JS/WebGL) | Primary reference for the step order and the "velocity coarse, dye fine" split |
| 3 | **NVIDIA GPU Gems ch. 38 "Fast Fluid Dynamics Simulation on the GPU"** (Harris) [L] | Textbook: advect, diffuse, project; 40-80 pressure iterations recommended, below 20 error is visible | (c) NVIDIA, algorithm only | n/a | Maths reference, no code copied |
| 4 | **Fluid Simulation TOPs** (Aurelian Ionus / paketa12, asset 71458, 6 Mar 2025, presented Berlin meetup May 2024) [V page] | Bruno Imbrizi's fluid translated into **native TOPs only** (tag noGLSL); Optical Flow from the palette component (**unsupported on Mac, T-18**); one 18.35 KB `.toe`, tokenised download | No licence stated | Not downloaded. No GLSL, so no compute-vs-pixel problem, but native TOP chains still go through the same render path (T-46 untested for them), and the optical-flow input is dead here | Idea: a native-TOP fallback if compute turns out slow; test as an A/B once built (FUTURE row) |
| 5 | **Constraint Simulation Tool** (Josef Pelz, asset 65109, 6 Aug 2021) [V page] | Spring-constraint cloth/fabric on polygon SOP geometry in **compute shaders**; stiffness, stress resistance, gravity, wind; per-point `mass`, per-prim `stressResistanceScale`/`stiffnessScale`; points/wireframe/PBR with UVs; `constraint_simulation.zip` 9.85 MB | **NON COMMERCIAL USE ONLY** | TD build, OS, counts not stated; not downloaded. Compute-based, so the right family for Mac | Closest to our cloth spec: copy the attribute names idea (`mass`, `stiffnessScale`), build ours clean-room. A later optional read-only inspection of the zip is allowed (no login stated, not tried) |
| 6 | **Josef Pelz GLSL workshops** (derivative.ca 67502, 2023; 2021 meetup "real-time cloth simulation using GLSL in TD", paid recording) [S] | "Cloth with surprisingly few lines, state lives in textures" | paid | Not accessible | Confirms the texture-as-state design of spec 3 |
| 7 | **WaveTOP** (asset 67796) and **Water ripple effect** (asset 63763, Wave_ripples.tox 2.56 KB) [S] | Wave equation heightfield in native TOPs (red channel adds volume, input 2 = reflecting boundaries) / GLSL ripple, based on a Shadertoy | not stated | Not downloaded; WaveTOP is native-TOP (T-46 risk unknown) | The 2-texture wave equation is a 10-line compute step: offered as `Kind = ripple` in the fluid COMP (section 3.9). Both assets: reference only |
| 8 | **jack DiLaura / elburz "Generative Liquid Paintings"** (derivative.ca 68643, 27 Nov 2023) [L O 4.8] | Shadertoy single-pass CFD (Florian Berger) adapted to TD | not stated | Single pass: **does not suffer from T-46**, looks "painterly", not a true projection solve | Cheap "fluid-lite" mode idea (FUTURE) |
| 9 | **yeataro TD-ScreenSpaceFluid** [L N] | Screen-space particle "fluid" blob filter | MIT | 2023, build not stated | Not a solver; a look filter for POP particles |
| 10 | **Noisemaker for TouchDesigner** (noisefactorllc) [L N] | 210 procedural effects including fluids, physarum, reaction-diffusion; text DSL | MIT | Needs 2025.32820+ (arm64-native); **not usable on our 31550** | FUTURE: re-test after an upgrade |
| 11 | **DBraun/TouchDesigner_Shared** [L N] | turing_pattern (reaction-diffusion), Physarum starter, curl noise, JFA | GPL-3.0 | 2018-22 era GLSL, pixel mode | Reference for RD parameters; do not copy into closed work |
| 12 | **TD Summit 2018 "touchfluids" (`ancillarymagnet/touchfluids`)** [S] | Scratch Navier-Stokes advection as a hello-world | unknown | Repo not re-found in this lane: **UNVERIFIED** | Skip unless found |
| 13 | **Nvidia Flex Solver COMP / Flex TOP** (built in), **FlexCHOP** (vinz9, 2019) [S], **Nvidia Flow** | Particle fluid, Windows + NVIDIA only; FlexCHOP wraps FleX 1.2, GTX 1070+, DLLs from Releases | built-in / unknown | **Not on macOS** ([macOS page](https://docs.derivative.ca/MacOS), F13) | Excluded |
| 14 | **ClothPOP** (asset 75017) / **ClothPOP PRO** (75143, XPBD, 10 EUR, 1 seat/1 PC/1 year, online activation) [L O 4.9] | CUDA cloth POPs | free = non-commercial, 5,000 points; PRO paid | **CUDA = NVIDIA only; not Mac** | Excluded |
| 15 | **vinz99 "Simple GPU Cloth Sim"** (2010; port by T. Gerritsen 2018) [L] | Verlet cloth with cache TOPs, GLSL 1.2 | none | "nothing renders in later builds" per forum users | Concept only |
| 16 | **Matthias Mueller "Ten Minute Physics"** (XPBD cloth/soft body video series; official page `matthias-research.github.io/pages/tenMinutePhysics/`) [S] | The clearest XPBD + shape-matching derivations; third-party ports are MIT; licence of his originals not seen | unknown for originals | Maths only | Source of the XPBD compliance form and soft-body ideas (spec 3); cite, do not copy |
| 17 | **Karl Sims RD tutorial** and Pao Olea TD tutorial 19 [L O 4.2] | Gray-Scott constants (f 0.055, k 0.062, DA 1, DB 0.5; Laplacian 0.2/0.05/-1) | page text | maths | Constants for spec 2.9 |

Search gap: TD forum threads for POP-based cloth/soft body/PBD returned nothing (searched), `derivative.ca/tags/simulations` has no clean-for-Mac cloth entry. YouTube transcripts were not pulled (no timing need; the algorithms are textbook).

## 3. How these work in TD and what is clean on MoltenVK

### 3.1 The stable-fluids step (Stam 1999; Harris GPU Gems 38; Dobryakov), 2D
State: velocity `u` (RG), pressure `p` (R), dye `d` (RGB or density), optional temperature `T`, obstacle mask `o`. One time step:
1. **curl** w = dv/dx - du/dy (small texture)
2. **forces**: add splats (Gaussian: `u += F * exp(-|x-c|^2 / r)`), buoyancy `(T - Tamb)*sigma - density*kappa` upward, **vorticity confinement** `f = eps * (N x w)`, N = normalise(grad|w|) (Kaminski's `vorticity2` does exactly this with a safe normalise epsilon 2^-12 [V])
3. **divergence** div = 0.5 * ((uE.x - uW.x) + (uN.y - uS.y)) (Kaminski's `halfInverseCell^2` scaling [V])
4. **pressure Jacobi x K**: p' = (pW + pE + pS + pN - div) * 0.25 (alpha = -h^2, inverseBeta = 0.25; Kaminski `jacobi`: `(pW+pE+pS+pN + alpha*b) * inverseBeta` with Neumann boundary by mixing in the centre value where the neighbour is solid [V])
5. **gradient subtract** u -= grad p (makes u divergence-free)
6. **advect velocity** (semi-Lagrangian, backtrace `x - dt*u(x)`, bilinear), then **advect dye** (and T) with dissipation `* exp(-dt*k)`.
Cost shape: ~6 small passes + K pressure passes at velocity resolution (128-256 per side) + 1 big pass at dye resolution (1080x1920). "Velocity coarse, dye fine" is the main saving [L O 4.8].

### 3.2 Why compute-mode on this machine
- Pixel-mode GLSL TOP chain: stale/mixed-frame inputs, 0/328 right at 20 passes [L T-47]; "InkFlow keeps stirring with zero force (vel 3..26, div of a zero field = 121)" is the visible symptom of exactly this on a fluid [L T-46].
- Compute mode: `mode=compute`, `computedat`, `layout(local_size_x=8, local_size_y=8)`, write with `TDImageStoreOutput(0, ivec3(gl_GlobalInvocationID), c)`, custom resolution (compute has no input-driven size), auto dispatch. Proven 340/340 (256x256 32F) and 441/441 (1080x1920 16F) over a 20-pass copy chain [L T-47]. Our existing builders (`builders/face_track.py` `_glsl`) already wrap this.
- Untested here and to be probed first (live, with numbers, section 5): (a) whether `npasses` on a compute GLSL TOP feeds pass n output into input 0 of pass n+1 (docs F10 say so for pixel TOPs; **UNVERIFIED for compute**), else unroll K nodes by script; (b) Feedback TOP around a compute chain; (c) reading a `texelFetch` from an rgba32f TOP that is also the `outputaccess` target (avoid: always write to a different node than you read).
- Windows/other platform differences: the same shaders run on Windows; the T-46 issue is Mac-specific as far as we know (UNVERIFIED on other machines).

### 3.3 Cloth / soft body in TD
- POP route: gridPOP -> feedbackPOP -> glslPOP (Verlet) with neighbours via `TDDimCoords`. Plausible, never run here; Feedback POP crash class on macOS (32260 fixed in 32280) [L F11]; GLSL POP `Passes` semantics for relaxation unverified [L F7]. **Parked** as a later `Backend = pops` option (FUTURE).
- Texture route (chosen): positions in an rgba32f TOP `W x H` (one texel per cloth vertex); `Pold` in a second; compute passes: integrate + collide, then K Jacobi constraint passes, then output. Rendering by displacing a Grid SOP in a GLSL MAT (vertex shader samples the position texture) or, fallback, POP points via `toptoPOP`/`sampler`. Both are sketches until probed.
- Constraint solving as **gather-Jacobi** (each vertex computes the sum of corrections of its neighbours' springs and moves itself) has no write conflicts, so it needs no atomics and no graph colouring; it converges slower than Gauss-Seidel, compensated with XPBD compliance (stiffness independent of iteration count) and K = 8-16.
- Soft body ("jelly"): **shape matching** (Mueller et al. 2005): goal position `g_i = c + R (q_i - q_cm)`, R from polar decomposition of the covariance of the current positions against the rest shape. The covariance is 9 sums over all vertices: on the GPU a compute pass writes the 9 products, an Analyze TOP (`op` = sum/average, in the 31550 dump) reduces them, a tiny Python step (numpy SVD, 3x3) returns R one frame later. Gives a bouncy sheet/blob with no volume loss problem (a spring system alone collapses; Houdini forum note [S]).

### 3.4 Format and precision notes (all to be confirmed live)
rgba32float for velocity/pressure/positions (small textures; 256x256x16 B = 1 MB), rgba16float for the 1080x1920 dye (proven in T-47). Denormal/packHalf NaN problem in Shadertoy fluids under 2025 GLSL: do **not** pack data with `packHalf2x16` [L Z]. Wrap time fed to hashes/noise (F22). Shader recompile per frame if a constantly changing value is in a Math scope par (F12): all animated values go through Vectors/Array uniforms.

## 4. What touchFluid's shaders tell us (read, not run)
- `advect`: backtrace `(fragCoord - dt*v) * res` where `uTD2DInfos[SOURCE].res.xy` is the **inverse** resolution (TD's `res` = 1/width,1/height,width,height), result `* diffusionRate` (one dissipation constant per channel group); solid cell (`obstacle.b > 0`) writes 0. Samples with `texture()` (bilinear).
- `jacobi`: `texelFetchOffset`; Neumann pressure boundary by `mix(P_neighbour, P_opposite, obstacleFlagByDirection)` where the obstacle-neighbour texture stores one flag per direction (`.x` north, `.y` south, `.z` east, `.w` west); `alpha`, `inverseBeta` as uniforms.
- `divergence`: same direction flags flip the neighbour offset and negate that velocity component (free-slip walls).
- `vorticity2`: confinement force with `abs()` of neighbouring curl, normalised with epsilon 2^-12, multiplied by `vorticityConfinementScale * vortCenter * vec2(1,-1)`. Note: its neighbour lookups use `TC - ivec2(-1,0)` (left/right swapped but symmetric); a bug-for-bug port is unnecessary.
- `buoyancy`: reads density (R,G) + temperature (B) and an ambient-temperature 1x1 TOP; force `= (dt*(T-Tamb)*sigma - densityB*kappa) * 0.01` upward.
- `obstacleBounds`: builds the per-direction flag texture from the mask.
Design takeaways for ours: keep the **per-direction solid flags** texture (one extra small pass or fused into divergence), keep **Neumann by mix**, replace `fragCoord`/`texture` with `gl_GlobalInvocationID`/`texelFetch` + manual bilinear, and replace the 1/res uniform with an explicit `uInvRes`.

## 5. CLEAN-ROOM BUILD SPEC A: `BN_fluid2d` (2D fluid COMP: dye + velocity)

PREPARED (offline): run builders/fluid2d.py build(); verify per docs/builds/fluid2d.md

Suggested path `/project1/lab/BN_fluid2d`. Base COMP, self-contained (custom pars drive internals; Out ops carry output only; own `controls` panel and `controls_window` opened by an `Opencontrols` pulse, T-68 layout pattern). **No built-in safety limits or warnings**: all pars unclamped by design (clamp-min/max off), no luminance limiter, no flash guard; operator decides. Control sources offered side by side: manual (mouse/panel/pulses), BPM (internal beat clock), audio (level/band triggers). Builder file proposal: `builders/fluid2d.py` + `td/fluid2d_logic.py` (pure Python/numpy, no `td` import) + `test/test_fluid2d_logic.py`, house style of `db_meter.py` / `zctl.py`.

### 5.1 Interface
Inputs (all optional; unconnected = Constant black / no-op):
- `in1` In TOP **Source**: colour injected as dye (rgb) with alpha or luma as strength (a logo, a webcam clip, a noise).
- `in2` In TOP **Mask**: white = solid obstacle (threshold `Maskthresh`); solids get zero velocity and reflect/stop flow.
- `in3` In TOP **Force**: RG = a velocity field added each frame (e.g. frame-difference or a motion vector TOP; **no Optical Flow TOP on Mac, T-18**: the camera path is frame difference of the stored clip `media/webcam/webcam_ref_5s.mp4`).
- `in4` In CHOP **Points**: up to 8 emitters, channel groups per sample `x y vx vy radius strength r g b` (normalised 0-1 coords, one sample per emitter). Mouse, MIDI, Kinect-like trackers can feed it.
- `in5` In CHOP **Audio**: any audio CHOP (1-2 channels). The COMP never touches the audio output (no Audio Device Out inside; default output stays the Mac speakers, never mic -> speaker).
Outputs:
- `out1` Out TOP **Dye** (rgba16float, `Resw` x `Resh`).
- `out2` Out TOP **Velocity** (RG raw in rgba32float at `Simw` x `Simh`; plus an optional visual version via `Velview`).
- `out3` Out CHOP **Stats**: `maxvel`, `meanvel`, `divmax`, `dyesum`, `cookms`, `steps`, `beat` (0/1), `audiolevel`.
Outs hold only output; no controls inside them.

### 5.2 Custom parameters (names: one capital then lowercase/digits; ranges documented, never clamped)
- Page `Sim`: `Simw` / `Simh` (velocity grid, default 256 x 456 for 9:16; derived from `Dyeaspect` if `Auto`), `Resw` / `Resh` (dye, default 1080 x 1920), `Iterations` (pressure Jacobi K, 20), `Dt` (0.016 or `Auto` = real frame delta), `Timescale` (1.0), `Veldiss` (velocity decay per s, 0.2), `Dyediss` (1.0), `Curl` (vorticity confinement, 30), `Buoy` (0), `Temp` (0), `Edge` (menu wall / wrap / open), `Visc` (viscosity iterations, 0 = off, optional diffuse pass), `Warmstart` (pressure carry-over factor 0.8), `Kind` (menu fluid / ripple / reactiondiffusion, section 5.9).
- Page `Input`: `Srcgain`, `Srcmode` (menu dye / dye+velocity-from-luma-gradient), `Maskthresh`, `Forcegain`, `Mouse` (menu off / panel / external), `Mouseradius`, `Mouseforce`, `Mousecolor` (RGB), `Emitradius`, `Emitforce`.
- Page `Audio`: `Audiomode` (menu off / level-stir / kick-burst / band-colour), `Audiogain`, `Lowhz`/`Highhz` split, `Burstthresh`, `Burstrefractory` (s), `Burstforce`, `Burstring` (radius of the radial burst ring), `Bpmmode` (menu off / internal / external CHOP beat), `Bpm` (120), `Bpmdiv` (1 beat, 1/2, 2 bars), `Bpmpattern` (menu ring / sweep / random / point list), `Burst` (pulse, manual).
- Page `Look`: `Colormode` (menu rgb / palette-by-density / palette-by-speed / hue-by-angle), `Pal1..Pal5` (RGB), `Exposure`, `Gamma`, `Dyeblend` (add / over), `Velview` (off / hsv / arrows), `Bg` (RGB), `Alpha` (menu opaque / density), `Premult` (toggle: premultiplied output for Arena, per memory overlay-alpha rule).
- Page `Control`: `Reset` (pulse, clears all state), `Pause` (toggle), `Step` (pulse: one step while paused), `Seed` (int for deterministic test splats), `Opencontrols` (pulse), `Testmode` (menu off / zero-force / fixed-splat for verification).

### 5.3 Internal network, stage by stage (titled boxes via `td_layout stages`, L-to-R, role colours: input blue, analysis orange, sim purple, display green, controls on top of column 0)
1. **"Inputs"**: `in1..in5` + `src_prep` (Level/Resolution to `Resw x Resh`), `mask_prep` (Threshold -> compute pass "flags": per-cell direction flags RGBA = N,S,E,W solid, plus `.b` solid itself, at sim res; border walls added by `Edge`), `force_prep` (Resolution to sim res).
2. **"Control sources"**: `emit` Script CHOP (Python from `fluid2d_logic.emitters()`): merges panel mouse (Panel CHOP from `controls/preview`), `in4` points, BPM bursts (beat clock from `Timer`/`Count` CHOP, `Bpm`/`Bpmdiv`), audio bursts (Analyze + Trigger with refractory) and the `Burst` pulse into **8 emitter rows**; output as a CHOP read by the shader Array uniforms (`array0chop`, as `builders/face_track.py` does). Audio analysis: `Audio Spectrum` -> band energies -> Lag. No limiter on any of it.
3. **"Forces"** (compute, sim res; one node `fx_forces`): reads previous velocity (Feedback TOP `vel_fb`), curl texture, `emit` array, `force_prep`, flags, temperature/dye for buoyancy; writes velocity'. Curl itself is computed inline from 4 neighbours of 4 neighbours (12 fetches) so no separate curl pass is needed (one fewer dispatch).
4. **"Project"**: `fx_div` (divergence with flags, writes `.r`), then **`fx_press` x K**: Jacobi; first one reads warm-start pressure from `press_fb`. K nodes are generated by the builder as an unrolled chain `fx_press_01..K` (default K = 20; if the probe in 5.7 proves compute `npasses` correct, replace the chain with one node and `npasses = K`). Then `fx_grad` (subtract gradient, enforce solids).
5. **"Advect"**: `fx_advvel` (self-advect velocity at sim res), `fx_advdye` at dye res: backtrace uses bilinear sampling of velocity (manual bilinear in shader from the sim-res texture), dye += `src_prep * Srcgain` (and emitter colour), `* exp(-Dt*(1-Dyediss...))`.
6. **"Feedback"**: `vel_fb`, `press_fb`, `dye_fb` Feedback TOPs, each `top` = the `Null` at the loop end (`vel_out`, `press_out`, `dye_out`). Only one Feedback loop per state; reset via `Reset` pulse and an initial Constant black.
7. **"Look"**: `fx_look` compute (dye res, single pass): `Colormode`, palette ramp (uniform array of 5 colours), exposure/gamma, alpha/premult. `vel_view` (sim res) HSV/arrow visualisation. -> `out1`, `out2`.
8. **"Stats"**: `Analyze TOP` (`op` average/maximum, 1x1) -> TOP to CHOP -> `out3`; `cookms` via `perform` info; `steps` counter. The stats chain is cheap (1x1) and always on.
9. **"Controls"**: `controls` container (autoUI, `Pagescope` = Sim Input Audio Look Control, `Pagetabs` off, widgets cut so the COMP stands alone, T-68), `preview` tile of `out1` with the panel mouse, a green `OUTPUT` node, `controls_window` opened by a Parameter Execute on `Opencontrols`. Everything arranged L-to-R, real names, comments.
Number of dispatches per frame: forces 1 + div 1 + pressure K + grad 1 + adv 2 + look 1 = K + 6 (26 at K = 20); only `fx_advdye` and `fx_look` are at dye res.

### 5.4 Shader sketches (compute, GLSL 4.30; TD uniforms via Vectors/Array pages; shown for pressure, advect and forces)
```glsl
// fx_press (one Jacobi iteration), sim res, in0 = pressure (R), in1 = divergence (R), in2 = flags (N,S,E,W)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec2 uSim;                // sim width, height (also set via Vectors)
void main() {
  ivec2 T = ivec2(gl_GlobalInvocationID.xy);
  if (T.x >= int(uSim.x) || T.y >= int(uSim.y)) return;
  float c  = texelFetch(sTD2DInputs[0], T, 0).r;
  float pN = texelFetch(sTD2DInputs[0], clamp(T+ivec2(0, 1), ivec2(0), ivec2(uSim)-1), 0).r;
  float pS = texelFetch(sTD2DInputs[0], clamp(T+ivec2(0,-1), ivec2(0), ivec2(uSim)-1), 0).r;
  float pE = texelFetch(sTD2DInputs[0], clamp(T+ivec2( 1,0), ivec2(0), ivec2(uSim)-1), 0).r;
  float pW = texelFetch(sTD2DInputs[0], clamp(T+ivec2(-1,0), ivec2(0), ivec2(uSim)-1), 0).r;
  vec4 f = texelFetch(sTD2DInputs[2], T, 0);   // 1 where the neighbour is solid
  pN = mix(pN, c, f.x); pS = mix(pS, c, f.y); pE = mix(pE, c, f.z); pW = mix(pW, c, f.w);
  float b = texelFetch(sTD2DInputs[1], T, 0).r;
  TDImageStoreOutput(0, ivec3(T, 0), vec4((pN+pS+pE+pW - b) * 0.25, 0, 0, 1));
}
```
```glsl
// fx_advdye, dye res; velocity is a sim-res texture sampled with manual bilinear in uv space
vec2 bilerpVel(vec2 uv) { /* 4 texelFetch + mix on sTD2DInputs[1] at sim res */ }
void main() {
  ivec2 P = ivec2(gl_GlobalInvocationID.xy);  if (outside) return;
  vec2 uv = (vec2(P) + 0.5) / uDye;
  vec2 v  = bilerpVel(uv);                      // velocity in sim cells per second
  vec2 back = uv - uDt * v / uSim;              // backtrace in uv
  vec4 d = bilerpDye(back) * exp(-uDt * uDyeDiss);   // bilinear, edge mode per Edge
  d.rgb += texture(sTD2DInputs[2], uv).rgb * uSrcGain * uDt;  // src_prep
  for (int i = 0; i < 8; i++) d.rgb += splat(uv, i) * uEmitCol[i].rgb;  // gaussian
  TDImageStoreOutput(0, ivec3(P, 0), d);
}
```
The Gaussian splat is `strength * exp(-dot(dp,dp) / (r*r))` with aspect-corrected `dp`; force splat adds `vec2(vx,vy) * splat`. The burst ring is an emitter row generator in `fluid2d_logic`, not shader code.

### 5.5 Offline-testable logic (`td/fluid2d_logic.py`, numpy, pure Python; pytest in `test/`)
A reference numpy implementation of the same step: `step(state, params, emitters)` with identical formulas so GLSL and Python can be compared. Tests:
1. `splat()` normalised: integral over the grid equals strength * pi r^2 within 1% for r >> 1 cell.
2. **Zero in, zero out**: zero velocity/dye, no emitters, 200 steps -> all exactly 0 (the T-46 failure mode InkFlow showed: vel 3..26 after Reset).
3. **Projection**: random velocity -> divergence + pressure K=20 + gradient subtract -> `max|div|` decreases by >= 10x vs before; increases monotonically with K down; with K=200 below 1e-3 of the initial norm (periodic grid).
4. **Jacobi residual** decreases monotonically on a manufactured Poisson problem (known solution `p = sin(2 pi x) sin(2 pi y)`), residual ratio per iteration <= 1 (Jacobi spectral radius ~ cos(pi/N)), error vs analytic < 5% after 500 iterations at 64^2.
5. **Advection**: uniform velocity (1 cell/step) shifts a Gaussian by exactly one cell with <= 2% peak loss per step (bilinear diffusion bound); dissipation `Dyediss` gives `exp(-k t)` decay of the sum within 1e-6 on a zero-velocity field.
6. **Boundaries**: with solid mask, no dye flux into solid cells; wall mode keeps `sum(dye)` within 0.1% over 100 steps with dissipation 0 and zero emitters (semi-Lagrangian clamp); wrap mode keeps it within 1%.
7. **Obstacle flags**: `flags_from_mask()` against a hand-built 5x5 example.
8. **Emitters**: `bpm_ticks(t0, t1, bpm, div)` returns the exact beat times (120 bpm, div 1 -> every 0.5 s, 60 s window = 120 ticks, no drift over 1 h); burst refractory prevents a second trigger within `Burstrefractory`; kick detector on a synthetic sine burst train (numpy) triggers on the 4 loud bursts and not on the 4 quiet ones.
9. **Shader contract**: the shader text is generated from a template; a test asserts the constants in the generated text (workgroup 8x8, inverse beta 0.25, 8 emitters, the splat formula) equal those in the Python reference.

### 5.6 Live verification on 31550 (numbers a builder reports; save the project first, see 5.8)
Probe first in a scratch COMP, report each:
1. **P1 compute pass chain**: 20 `fx_press` copies of the same node chained on a constant increasing per frame: correct on 100% of 300 frames at 256x456 32F (re-run of T-47 with our node pattern) with the Feedback TOP loop in place.
2. **P2 `npasses` on compute GLSL**: one node, `npasses = 5`, shader adds 1 to R: output R = input + 5 (pass chaining) or input + 1 (no chaining). Choose chain vs `npasses` accordingly.
3. **P3 zero-force stillness**: `Testmode = zero-force`, Reset, 600 frames: `maxvel` == 0.0 exactly and `divmax` == 0.0 (hard criterion; failure = T-46 hazard still present in our loop).
4. **P4 determinism vs numpy**: `Testmode = fixed-splat` (Seed 1, 3 emitters at fixed frames), 60 steps at 64x64 sim / 128x128 dye, `Dt = 1/60`: download velocity via `numpyArray()` and compare to `fluid2d_logic.step` run 60 times with the same params: relative L2 error < 1e-3 at 32F velocity, < 5e-3 for 16F dye.
5. **P5 incompressibility**: after warm-up, `divmax` of the projected field below 5% of the pre-projection divergence at K = 20, below 1% at K = 40.
6. **P6 mass**: closed box, `Dyediss` = 0, no sources: `dyesum` constant within 2% over 1,000 steps.
7. **P7 colour/range**: dye `out1` no NaN/Inf over a 10 min run (Analyze max finite), alpha mode premult verified by the Arena-style Over test from the overlay-alpha memory (only if the user later wants Arena; no Arena calls here).
8. **P8 audio/BPM/manual**: feed an Audio Oscillator CHOP (no speaker routing) with a pulse train at 2 Hz: kick bursts counted 120 in 60 s; `Bpm = 120` internal clock gives `beat` rising edges 120 in 60 s (+-1); `Burst` pulse fires one burst.
9. **P9 webcam**: `in1` = a Movie File In of `media/webcam/webcam_ref_5s.mp4` (frame difference to `in3`): `meanvel` > 0 only while the subject moves; stored clip loops cleanly.
10. **P10 teardown**: close the `controls_window`, then rebuild the COMP twice in a row without a crash (T-70 rules: `safe_destroy`, never destroy panels while a window shows them).
Perf targets (measure, do not assume; none were measured in this lane): total cook < 6 ms/frame at sim 256x456 + dye 1080x1920 + K = 20 (so >= 60 fps with headroom for a second COMP; use `td_perf`); K = 20 holds 60 fps for 10 minutes (`cookms` p99 < 12 ms); fallback ladder if over budget: dye 720x1280 -> K = 12 -> sim 192x342 -> warm start only (K = 6). Memory < 150 MB for the COMP. Re-run at 1920x1080 horizontal.

### 5.7 Mac / 31550 caveats and decisions the builder must record in LEARNINGS
- Never use pixel-mode multi-pass here (T-46); never trust a sim until P3 passes.
- Float atomics unavailable on macOS [L F13]: nothing in this spec needs them (gather style only).
- Compute has no input-driven resolution: set `outputresolution=custom` with expressions to `Simw/Simh/Resw/Resh`.
- Feedback TOP + compute: read `vel_fb`, write the node, close the loop at the Null; do not give the same node `outputaccess=readwrite` plus a Feedback source (aliasing risk).
- Viewers on Feedback loops (UI viewers) were a crash class in later builds [L F11]; keep the project Viewer open on `out1` only, not inside loops; no cookRate changes live (T-64).
- Doubles unavailable; 32F is enough.
- Shader recompile each frame if animated values are baked in (F12): use Vectors/Arrays only.

### 5.8 Saving (user rule: "save ur projects always so u dont loose ur progress or learnings or node setups")
The main session saves the project after every verified build stage (autosave T-71 runs every 10 min: `autosave` command; agents do not call save themselves). The builder, after each stage, also: writes the COMP out as a `.tox` through `td_tox_save` to `output/lab/BN_fluid2d_<stage>.tox` (not overwriting the previous), appends node-setup facts and every bug found to `LEARNINGS.md` at once (memory: bugs go in LEARNINGS), and records the build/stage in `STATUS.md`. The research lane keeps no live state.

### 5.9 Optional kinds sharing the shell (cheap add-ons once v1 passes)
- `Kind = ripple`: wave equation, two textures (h, h_prev), `h_new = 2h - h_prev + c^2 (laplacian h) - damp*(h - h_prev)`; mask input = reflecting boundaries; `in1` red = volume added (WaveTOP semantics [S]). One compute pass, no K loop, perfect for a first end-to-end probe.
- `Kind = reactiondiffusion`: Gray-Scott, A in R, B in G; Laplacian weights centre -1, edges 0.2, diagonals 0.05; DA 1.0, DB 0.5, f 0.055, k 0.062, dt 1.0; 4-12 substeps per frame as a compute chain; coral f 0.0545 k 0.062, mitosis f 0.0367 k 0.0649 [L O 4.2]. Test: with A=1,B=0 everywhere the state is a fixed point (exactly unchanged); seeded patch of B grows; total A+B bounded.
- v2: temperature/buoyancy smoke look, viscosity diffuse pass, MacCormack advection (second-order, reduces numeric diffusion), dye-colour-by-emitter, GPU particle tracer reading the velocity texture (`sampler0top` in a GLSL POP; POP route stays an option [L F8]), 3-pass bloom for the look.

Estimated builder time: 6-8 h to v1 including probes P1-P3 first (1 h), tests and controls panel.

## 6. CLEAN-ROOM BUILD SPEC B: `BN_cloth` (cloth + soft-body COMP)

Suggested path `/project1/lab/BN_cloth`. Same house rules as spec A (self-contained, Out ops output only, own `controls` + `controls_window`, no limiter/warnings, manual/BPM/audio drivers, speakers untouched). Builder files: `builders/cloth.py`, `td/cloth_logic.py`, `test/test_cloth_logic.py`.

### 6.1 Interface
- `in1` In TOP **Texture** (cloth print; default internal checker), `in2` In TOP **Pins** (white = pinned point; used when `Pins = mask`), `in3` In CHOP **Colliders** (up to 4: `type x y z r` or box extents; moving spheres from a tracker/mouse), `in4` In CHOP **Wind** (x y z strength; optional), `in5` In CHOP **Audio**.
- `out1` Out TOP **Render** (Render TOP of the cloth, `Resw x Resh`, with alpha), `out2` Out TOP **Positions** (rgba32float, the `W x H` position texture: lets anyone render it elsewhere or sample it from POP/GLSL), `out3` Out CHOP **Stats** (`maxstretch`, `meanstretch`, `energy`, `cookms`, `steps`, `beat`).

### 6.2 Custom parameters
- `Sim`: `Gridw` / `Gridh` (default 128 x 128 = 16,384 vertices; up to 512 x 512 allowed), `Mode` (cloth / jelly), `Iterations` (K = 12), `Substeps` (2), `Dt` (Auto), `Gravity` (xyz, 0 -9.8 0), `Damping` (0.01), `Stretch` compliance (0), `Shear` compliance (1e-6), `Bend` compliance (1e-4), `Shape` (jelly stiffness 0..1, 0.1), `Mass` (1), `Size` (rest width/height in m), `Pins` (menu none / top edge / corners / mask), `Floor` (toggle + y), `Selfcollide` (off; v2), `Tear` (v2).
- `Wind`: `Windmode` (off / constant / noise / audio / bpm), `Windx/y/z`, `Windgain`, `Gust` (noise frequency), `Bpm`, `Bpmdiv`, `Burst` (pulse: impulse force wave), `Audiogain`, `Burstthresh`, `Burstrefractory`.
- `Collide`: `Sphere1..4` enables with `Cx Cy Cz R`, `Friction`, `Thickness`, `Mousecollide` (a sphere that follows the preview mouse).
- `Look`: `Resw`, `Resh`, `Cam` (menu front / orbit / top / free), `Orbitspeed`, `Light` (xyz), `Shading` (menu flat / phong / sheen), `Colorfront` / `Colorback` (RGB), `Texmix`, `Wire` (toggle), `Bg`, `Alpha`, `Premult`.
- `Control`: `Reset` (pulse: back to rest shape), `Pause`, `Step`, `Release` (pulse: drop all pins), `Opencontrols`, `Testmode`, `Seed`.

### 6.3 Internal network
1. **"Inputs"** as in spec A; `rest` Script TOP/Constant generates the rest-position texture (u,v -> (x, y, 0) * Size) and an `invmass` channel in `.w` (0 for pinned).
2. **"Control sources"**: `wind` Script CHOP producing the force vector per frame from `Windmode` (noise via Noise CHOP; audio level; BPM gust pulses; manual `Burst`); colliders CHOP (`in3` merged with `Mousecollide`).
3. **"Integrate"** compute `cl_int` (grid res): `Pnew = P + (P - Pold) * (1 - Damping) + a * dt^2` (a = gravity + wind term + mass), pinned vertices copy `rest`; writes `Pnew` and keeps `Pold = P` in a second Feedback TOP.
4. **"Constrain" x K**: `cl_con_01..K` (unrolled; or `npasses` if P2 of spec A proves compute chaining): gather-Jacobi, 12-neighbour stencil (4 structural at distance 1, 4 shear at sqrt2, 4 bend at distance 2): for each neighbour `n` of rest length `L`: `d = P - Pn; len = length(d); C = len - L; lambda = -C / (w_i + w_n + alpha/dt^2); corr_i += w_i * lambda * d/len;` average with factor `1/stencilcount` and a relaxation factor 1.0 (XPBD compliance form from Mueller's Ten Minute Physics series [S], alpha = compliance). Collisions (spheres, floor, mask ball) are applied in the last constraint pass as projection with friction.
5. **"Jelly"** (only when `Mode = jelly`): `cl_cov` compute writes the 9 covariance products + centroid (4 reduced values) to a small TOP; `Analyze TOP` (average) -> TOP to CHOP -> Script CHOP runs numpy: `R = polar(A_pq)` (SVD of the 3x3, fix reflections); `jelly_goal` compute sets `g = c + R(q - q_cm)` and adds `Shape * (g - P)` before the constraint passes. One frame of latency in R is accepted (rotation changes slowly).
6. **"Normals"** compute: central differences on `P` in the grid -> normal texture; double-sided.
7. **"Render"**: `cloth_geo` Geometry COMP with a **Grid SOP** (`Gridw x Gridh` points, UVs) and a **GLSL MAT** whose vertex shader samples `out2` (Positions) and the normal texture by `uv`; fragment shader: Phong/sheen, texture `in1`, front/back colours, optional wire. `cam`, `light`, Render TOP (`Resw x Resh`) -> `out1`. Fallback if the GLSL MAT path misbehaves under MoltenVK: `toptoPOP` -> points/sprites render.
8. **"Stats"**: `cl_stats` compute (per-vertex stretch of structural springs) -> Analyze TOP (average, maximum) -> `out3`.
9. **"Controls"** same pattern as spec A.
Dispatches per frame: Substeps * (1 integrate + K constraints) + normals + stats; with 128x128 the cost is dominated by dispatch overhead, not arithmetic.

### 6.4 Offline-testable logic (`td/cloth_logic.py`, numpy)
Reference solver `step()` with identical stencil/compliance math. Tests:
1. **Rest is stable**: a flat cloth at rest with zero gravity stays within 1e-7 of rest for 500 steps; with gravity and all pinned stays pinned exactly.
2. **Hanging cloth stretch**: top row pinned, gravity 9.8, K = 12, 2 substeps, 64 x 64, 1 m: after settling `max stretch` of structural springs < 5% (with K = 4 > 15%: demonstrates why K is exposed); energy decreasing monotonically after damping.
3. **Compliance invariance**: halving K with the XPBD form changes the static stretch by < 2x for the same `Stretch` compliance but the stiff-limit (alpha = 0) converges as K grows (monotone decrease of stretch in K).
4. **Collision**: cloth dropped on a sphere r = 0.3 at 1 m: no vertex closer than `r - 1e-3` to the centre after 300 steps; friction 0 vs 1 changes the final lateral spread.
5. **Pins**: pinned vertices never move; `Release` frees them next step.
6. **Shape matching**: `polar_rotation(A)` returns a proper rotation (det +1, R^T R = I within 1e-12) for random A; a rigidly rotated and translated rest shape gives zero goal error; jelly with `Shape = 1` returns to the rest shape from a random perturbation (RMS error halves each 10 steps).
7. **Wind**: constant wind moves the centroid along the wind direction; `Windmode = bpm` impulses occur at exact beat times (same `bpm_ticks` as spec A).
8. **Shader contract**: generated shader constants (stencil offsets, rest lengths for the 12 neighbours at spacing d: d, d*sqrt2, 2d) equal the Python.

### 6.5 Live verification on 31550
1. L1: `Testmode = rest`: downloaded `out2` array matches `rest` to 1e-6 for 300 frames (no tearing, T-46/47 class).
2. L2: numpy parity after 120 steps on 32 x 32 with fixed seed: relative L2 of positions < 1e-4 (32F both sides; float rounding order differs).
3. L3: hanging cloth numbers from the pytest (stretch < 5% at K = 12) reproduced live within 20%.
4. L4: sphere collision: min distance to centre >= r - 2e-3.
5. L5: render: `out1` not black; silhouette bounding box compared with a numpy projection of `out2` through the same camera (cheap sanity of the GLSL MAT displacement) within 2 px.
6. L6: jelly: after a `Burst`, `energy` peaks then decays to < 5% in 5 s at default damping; centroid momentum bounded.
7. L7: audio/BPM/manual wind each tested as in spec A P8.
8. L8: soak 10 min: no NaN (Analyze max of Positions finite), `cookms` stable, no growth in memory.
Perf targets (to be measured): 128 x 128, K = 12, 2 substeps: total < 3 ms; 256 x 256: < 8 ms (>= 60 fps); render 1080x1920 < 4 ms.

### 6.6 Mac caveats
Same list as 5.7; additionally: GLSL MAT vertex texture fetch under Vulkan/Metal is unverified on 31550 (ops: probe `glslMAT` exists via the MAT dump first); Connected-mode Neighbor POP on quads is documented only for 32280+ [L F4], hence the texture grid route; normals must not use Atomic Float (NormalPOP) [L F13]; no cloth self-collision in v1 (needs spatial hash scatter = atomics).

Estimated builder time: 8-10 h to v1 (render path is the risk).

## 7. MCP tool ideas
- `td_sim_probe` (read-only helper that builds a scratch compute chain and reports the T-46/T-47 numbers in one call: stale-frame percentage for N passes at a given resolution/format, and whether `npasses` chains on compute): reuses `td-port/lib/td_settle.py` ideas; makes every future sim builder start with evidence.
- `td_sim_check` : download a TOP with `numpyArray()` and compute `max|div|`, `sum`, NaN count, maxvel; returns numbers (the stats the COMP already exports, but works on any TOP).
- `td_compute_chain` builder: given shader text(s), resolution, format and K, build an unrolled compute chain with Feedback TOP, arranged and titled (the `_glsl` helper from `builders/face_track.py` generalised).
- `td_tox_snapshot`: stage-wise `.tox` save under `output/lab/` with a timestamp (the "save your progress" rule as one call).

## 8. Gated items for docs/FUTURE.md (rows added by the builder/maintainer, not by this lane)
| Feature | Needs build | Status | Where | How to test |
|---|---|---|---|---|
| Noisemaker for TouchDesigner (fluids, physarum, RD; MIT) | 2025.32820+ arm64 | idea only | BN 2 #10 | install on a scratch native build, A/B against BN_fluid2d |
| POP backend for cloth (gridPOP -> feedbackPOP -> glslPOP) | probe on 31550; Feedback POP crash fixes 32280+ | idea only | BN 3.3 | build scratch, soak 30 min |
| Native-TOP fluid (Fluid Simulation TOPs, asset 71458) as speed A/B | 31550 | not downloaded | BN 2 #4 | download from the page if allowed, count cook ms |
| 3D fluid / SPH / Flex-like | none on Mac | not recommended | BN 1 | only if Mac gets Flex or a stable 3D compute path |
| Cloth self-collision / tearing | needs atomics or spatial hash | idea only | BN 6.6 | after Metal atomic float support or integer-atomic hashing |
| MacCormack advection, viscosity, temperature smoke look | 31550 | v2 of BN_fluid2d | BN 5.9 | numbers vs P4 |

## 9. Open questions
1. Does `npasses` chain on a compute-mode GLSL TOP (pass n output into input 0 of n+1)? Probe P2 answers it.
2. Is a compute chain with a Feedback TOP loop right on 31550 for >10 min (our probe T-47 had no loop)? Probe P1/P3.
3. Does the GLSL MAT exist and sample vertex textures correctly on 31550/Metal? Needs a MAT dump check before spec B.
4. Is rg32float or rgba32float better for velocity for bandwidth (O leaves this open)? Measure once.
5. Pelz's Constraint Simulation Tool zip and Fluid Simulation TOPs `.toe`: optionally download and `toeexpand` read-only in a later research lane (no login stated for either; not tried here).

## 10. Sources
[touchFluid repo](https://github.com/kamindustries/touchFluid) (MIT, shaders read) · [Fluid Simulation TOPs, asset 71458](https://derivative.ca/community-post/asset/fluid-simulation-tops/71458) · [Constraint Simulation Tool, asset 65109](https://derivative.ca/community-post/asset/constraint-simulation-tool/65109) · [WaveTOP, asset 67796](https://derivative.ca/community-post/asset/wavetop/67796) · [Water ripple effect, asset 63763](https://derivative.ca/community-post/asset/water-ripple-effect/63763) · [Simple GPU Cloth Sim thread](https://forum.derivative.ca/t/simple-gpu-cloth-sim/1990) · [ClothPOP](https://derivative.ca/community-post/asset/clothpop/75017), [ClothPOP PRO](https://derivative.ca/community-post/asset/clothpop-pro/75143) · [FlexCHOP](https://github.com/vinz9/FlexCHOP), [Flex in TD](https://derivative.ca/UserGuide/Flex), [NVIDIA FleX](https://developer.nvidia.com/flex.md) · [Generative Liquid Paintings](https://derivative.ca/community-post/tutorial/generative-liquid-paintings-touchdesigner/68643) · [Pelz GLSL workshop](https://derivative.ca/workshop/josef-pelz-%E2%80%93-advanced-glsl-shader-programming-12-ss23-%E2%80%93-0506/67502) · [Feedback POP](https://docs.derivative.ca/Feedback_POP) · [Ten Minute Physics soft bodies](https://matthias-research.github.io/pages/tenMinutePhysics/10-softBodies.html) · [Houdini soft body volume note](https://www.sidefx.com/forum/post/23056/) · [MoltenVK release notes](https://github.com/KhronosGroup/MoltenVK/releases) (barriers via Metal fences, read-write texture hazard fixes; nothing rgba32f-specific found) · our notes: O_generative_simulations 4.2/4.8/4.9, N_community_components, LEARNINGS T-18/T-46/T-47/T-64/T-68/T-70/T-71.
