# BO - Particle systems in TouchDesigner 2025.31550 (POPs, GPU compute, instancing) + clean-room build spec, 26 Oct 2026

Offline research (no `td_*` tool used, nothing loaded in TD, nothing downloaded or run except my own numpy file). General-purpose
TD (PF26 no longer a constraint). Build: **2025.31550, M1 Max, Rosetta/x86_64, Vulkan/MoltenVK**. Tags: `[T-nn]` LEARNINGS,
`[dump]` `ops/*_2025.31550.json`, `[doc]` docs.derivative.ca (fetched 26 Oct), `[tut]` our `tutorials/slice_*.md` transcripts,
`[local]` files already on disk under `research_src/`, `[web]` search result 26 Oct. **UNVERIFIED** = not run in this build.
Earlier notes win where they overlap: `ops/POP.md` (all 97 POP classes), `O_generative_simulations.md` (F1-F22, sims, counts).
This file adds: what exists *for particles*, a TOP-compute engine read from a real tox, and the build spec.

## 0. Top findings

1. **Everything needed exists in 31550 [dump]:** `particlePOP`, `feedbackPOP`, `forceradialPOP`, `fieldPOP`, `trailPOP`, `neighborPOP`,
   `proximityPOP`, `noisePOP` (curl3d/curl2d outputs), `randomPOP`, `mathmixPOP`/`mathcombinePOP`, `glslPOP`, `glsladvancedPOP`, `glslcopyPOP`,
   `lookuptexturePOP`, `copyPOP`, and the bridges `toptoPOP`, `soptoPOP`, `choptoPOP`, `dattoPOP`, `poptoTOP/CHOP/DAT/SOP`. `glslTOP` has
   `buffer0pop` (reads a POP buffer) and `glslPOP` has `sampler0top` (reads a TOP): both directions of the TOP/POP bridge are native.
2. **31550's Particle POP is older than its docs [dump vs doc]:** no "Enable Time Integration", no Jitter Birth Position/Jitter Births During Frame
   (docs add them in 2025.32460). Emitting from input points therefore spawns every child on the point; emit from a volume (Point Generator POP,
   or a TOP-to-POP grid with a birth attribute). Integration is the doc formula `V += F/m*dt; P += V*dt` (semi-implicit Euler).
   Attributes created: `PartId PartVel PartAge PartLifeSpan PartForce PartMass PartDrag (PartDeath)`; **read exact names off a live op with POP to DAT first.**
3. **A second, POP-free engine is proven by a real tox [local]:** Tim Gerritsen's *Compute Particle System v2.x* (asset 62080, CC BY 4.0, free,
   2019, fixed for 2022.24200 as v2.2). One **GLSL TOP in compute mode** holds all state in an `rgba32float` texture (4 texels per particle),
   updates it **in place** (`Output Access = readwrite`, `imageLoad` its own output), and a **GLSL MAT vertex shader** does `TDInstanceID()` ->
   `texelFetch` -> position, so the whole loop is on the GPU with **no POP loop, no CPU readback, no Feedback TOP**. This is the right fallback
   because POP loops carry an open crash class on macOS (F11, `ops/POP.md` gotcha 8) and compute-mode GLSL TOP is the one multi-pass form that
   is clean on this Mac **[T-47: 441/441 vs 0/151 pixel mode]**.
4. **Counts that are measured on this Mac exist only for the bare render [F14]:** 2 M sprites 60 fps, 4 M 38.6 fps, 10 M 11.5 fps, at **7488x2880**.
   No measurement of a simulated loop (forces, neighbours) exists anywhere; external POP forum anecdote: ~30 fps with previews on, ~60 with previews off
   on an unnamed MacBook (F16). 1080x1920 has 10.4x fewer pixels than 7488x2880, so fill cost drops; compute cost is resolution-independent.
   **Turn node previews/viewers off for timing** (but keep the user-visible rule: viewers on while building, off only in the timed run).
5. **Hazards to design around:** Ray POP / GLSL ray queries unsupported on macOS (no HW ray tracing) so tutorial 74455 collisions need analytic
   shapes instead; `double` attributes and atomic float unsupported; Line MAT/Common `Line Width` has no effect on macOS (Line MAT's own width pars
   unverified); Math Mix/Combine **Scope** pars holding changing expressions recompile every frame (F12), drive values through `vec` uniforms;
   wrap time-fed hashes on long shows (31550 notes: particlesGpu fixed "bad hash distribution upwards of 24 h") [F22];
   never change `cookRate` live (T-64); never destroy ops a window/pane shows (T-70).
6. Recommended single deliverable: **`BO_particles`**, one COMP, `Engine` menu `pop | compute`, same custom pars, same controls panel, same `Out`.

## 1. Landscape (ranked by usefulness here; Mac/31550 status; licence)

| # | Tool / asset / source | What it gives | Mac / 31550 | Licence | Use |
|---|---|---|---|---|---|
| 1 | **Particle POP + Force Radial/Noise/Math Mix POPs** (built in) [doc,dump] | the native route; millions of points, forces from POP ops, trails, per-point attributes | classes exist; only T-15 sprite chain run live; loop with forces **not yet run** here | Derivative | engine A |
| 2 | **Compute Particle System v2.2** (Tim Gerritsen / yfxlab, asset 62080; 2.2 fixed 'texel offset' compile error on 2022.24200) [local `research_src/community/files/62080`, [web]](https://derivative.ca/community-post/asset/compute-particle-system-v20/62080) | compute TOP state texture + GLSL MAT instanced render; heightmap collision, emitter matrix, lifetime/size curve `4x(1-x)`; commented | compute-mode GLSL TOP is clean on this Mac (T-47); this tox **not loaded** here; v2.0/2.1 failed to compile on newer builds (forum thread 271549) | **CC BY 4.0** (credit Tim Gerritsen) | engine B design source (clean-room) |
| 3 | Palette `Tools/particlesGpu.tox` + Derivative tutorials (reactive GPU particles 65068; 2022 forces) [local, [web]](https://derivative.ca/community-post/tutorial/reactive-gpu-particles-touchdesigner/65068) | forces, optical-flow input, GLSL Multi TOP compute, 896-line shader | authored on Windows 2023.12159; Metal run **UNVERIFIED**; 31550 notes fix its 24 h hash | Derivative palette | read-only study (F21) |
| 4 | **elburz / IIHQ "Audio Reactive Particles with POPs"** (75525, Oct 2026) [tut slice_01-03] | pointgenerator -> random(N) -> particle -> mathcombine gravity -> trail(PartId) -> Line MAT; audio RMS -> birthrate | 31550-era names match (slice_03 note) | video, none stated | audio mapping + trail recipe |
| 5 | Logic-driven particles 74194 (birth attribute from a Math Mix flag, noise curl -> initial velocity, age -> PointScale) [tut slice_01 #6] | `emissionmode=attr`, `Map` page, `1-age/life` | names in dump | none stated | emit-from-TOP/mask recipe |
| 6 | Dean Cheesman "3D Flocking with POPs" 73049 (400 -> 4000 pts @ 60 fps, "too many points can blow up a Mac: build small") [tut] | feedbackPOP + neighborPOP | Mac-built; Patreon files | none | optional flock force (not v1) |
| 7 | elekktronaut "Particle collisions with Ray POP" 74455 [tut] | floor/sphere bounce by ray reflect | **Ray POP hardware path unsupported on macOS** | none | replace by analytic plane/sphere in `glslPOP` |
| 8 | Simple Particle Systems with TOPs (73598, IIHQ): `particlesGpuCOMP` 1 M, 512x512 32F, feedback 32-bit to avoid ghosting [tut slice_02 #7] | confirms 1 M particlesGpu + float feedback for trails | Mac **UNVERIFIED** | none | trail path for engine B |
| 9 | Zenn omakazu GPU particles [web](https://zenn.dev/omakazu/articles/b03ca981123906) | classic ping-pong: pos/vel float textures, Feedback TOP, `layout(location=n)` MRT, nearest filter, 1-pixel-high strip OK, Geo instancing from texture RGB | pixel-mode multi-output: **T-46 tear risk** -> write as compute | none | explains the pattern; do not copy pixel-mode |
| 10 | Pao Olea "Cosmic particles, TOP-as-positions" 74543 [tut slice_01 #11] | noise TOP 32F RGB=XYZ -> Geo `instanceop`=TOP | **CPU readback cost unknown** | none | fallback render if the GLSL MAT route fails |
| 11 | DBraun `TouchDesigner_Shared` (Starters: boids, physarum, optical_flow_particles_compute) [community notes] | compute flocking/physarum starters | GPL-3.0 | **GPL-3.0** | read only, never paste |
| 12 | kamindustries `touchFluid` (2D semi-Lagrangian fluid) [web](https://github.com/kamindustries/touchFluid) | velocity field to push particles | pixel-pass chain: T-46 risk, port to compute | **MIT** | later `Field TOP` source |
| 13 | Brownian Motion TOX (74233, REM_Visuals), Magnetosphere (flight404, files not public), Moving sands 10 M attractor POPs (forum 479) | looks/benchmarks claims only | no files / 2025.32280 | MIT / none | inspiration |
| 14 | Bridson, Hourihane, Nordenstam "Curl-noise for procedural fluid flow" (SIGGRAPH 2007) | divergence-free field from a vector potential | maths | paper | the force definition (section 3) |
| 15 | Third-party MCP tool pages (`create_gpu_particle_field`, 262 k, noise/curl/gravity) [web glama.ai] | tool-shape idea only | n/a | n/a | MCP ideas (section 6) |

Gaps (searched, nothing found): any Apple-Silicon POP benchmark with forces; a GitHub repo for TD ping-pong particles; the Function Store
"particlesGPU toolbar" claim in our notes could not be confirmed ([web] 26 Oct).

## 2. How particle systems work in TD, in one page

**State + update + render**, three engines:

- **POP loop (engine A).** Points are GPU buffers with attributes. `particlePOP` creates/ages/kills and integrates; the chain after it writes `PartForce`
  (and may write `PartVel`/`P`/`Color`/`PointScale`); a `nullPOP` closes the loop and is named in `targetpop` [doc]. Count downstream must not change;
  kill with `PartDeath` (needs `usedeathattr`). Render: `selectPOP` inside a `geometryCOMP` (render flag) + `pointspriteMAT` + `cameraCOMP` + `renderTOP`
  [T-15]. Instancing a mesh per point: `geometryCOMP.instanceop = POP`, `instancetx/ty/tz = P(0..2)`, `instancecountmode oplength` [T-15; `instancepop` is the pivot].
- **Compute TOP loop (engine B).** `glslTOP mode=compute`, one thread per particle, state in float texture(s), `TDImageLoadOutput`/`TDImageStoreOutput`
  (API per T-47). Initialisation and reset by `clearoutputs`/a reset flag in the shader. Render: GLSL MAT vertex shader with `TDInstanceID()`
  and a sampler on the state TOP, geometry COMP with `instancecountmode manual`, `numinstances = N` [local yfx]. Time/fps/speed are uniforms.
- **Hybrid.** GLSL POP can read a TOP (`sampler0top`) so a force field / emitter map / audio texture drives either engine; GLSL TOP can read POP buffers
  (`buffer0pop`) so a POP result can be baked to a texture. `toptoPOP` (`rgba`, `resx/resy`, `maxpoints`, `texture`) makes a point grid coloured by a TOP.

**Forces** are just `F` accumulations: gravity, drag `-c*V`, curl (divergence-free so particles do not clump), radial/spiral attractors
(softened inverse-square), wind, vortex, per-pixel field from a TOP. **Curl noise** = curl of a vector potential Psi; `noisePOP` gives it directly
(`curl3d -> NoiseCurl`, `curl2d -> NoiseCurl2` [dump]); in a compute shader use an analytic potential of sine products (no noise library needed; section 4.2).
**Audio** = CHOP envelopes -> uniform values (POP: `vec` uniforms of `glslPOP`/`mathmixPOP`, never an expression in a Scope par [F12]).
**Trails** = POP `trailPOP` (attrmatch `PartId`, memory = length x points) or, for engine B, a Feedback TOP with decay (32-bit float to avoid ghosts that never fade [tut 73598]).
**Instancing millions of points**: POP -> `instanceop` is GPU-side [T-15 position only]; TOP instancing may read back to the CPU (UNVERIFIED, probe); the GLSL-MAT-fetch route has no readback by construction.

## 3. Mac / 31550 facts that shape the spec

| Topic | Fact | Source |
|---|---|---|
| Multi-pass GLSL TOP, pixel mode | tears (0/328 right) under MoltenVK | T-46/T-47 |
| Compute-mode GLSL TOP | clean: 340/340 (256x256 32F), 441/441 (1080x1920 16F); needs custom resolution par, `local_size 8x8`, `TDImageStoreOutput(0, ivec3(gl_GlobalInvocationID), c)` | T-47 |
| Compute **in-place read-write of own output across frames** | used by yfx on Windows; **not tested here** -> V2 test; fallback = Feedback TOP target (input 0 = last state), also a compute-reads-input pattern T-47 covers | local, UNVERIFIED |
| GLSL TOP uniform slots | `g.seq.vec.numBlocks = 8` for more vec4s (a sequence) | T-68 |
| POP loop crash class | Feedback POP + Null target crashed on macOS 32260 (hotfix 32280); freeze reports; **31550 exposure unknown**; build the first loop in a scratch COMP, restart plan, one TD | F11 |
| Ray POP / GLSL ray query | unsupported on macOS | POP.md gotcha 5 |
| Double attrs, atomic float | unsupported | POP.md gotcha 5 |
| GLSL POP | each attribute is an SSBO; `TDIndex()/TDNumElements()` guard; `TDIn_<Attr>()` reads; outputs are plain arrays `P[id]`, atomics need Read-Write; `Initialize Output Attributes` costs a dispatch (off when every output is written); outputs start uninitialised | [doc Write_a_GLSL_POP] |
| GPU -> CPU reads | stall; `poptoCHOP/DAT` default `nextframe` | POP.md gotcha 6 |
| Textures in instances | 128 on macOS (texture instancing, irrelevant to position-only instancing) | POP.md section 2 |
| `numpyArray()` right after `cook(force=True)` is zeros | read a frame later | T-13 |
| TD under Rosetta: python 3.11 x86_64 cv2 4.11 numpy 2.1.2; no mediapipe/onnxruntime | camera input = frame-difference TOP, not Optical Flow TOP (T-18) | context |

## 4. CLEAN-ROOM BUILD SPEC: `BO_particles` (`/project1/lab/BO_particles`)

PREPARED (offline): run builders/particles.py build(); verify per docs/builds/particles.md

One self-contained COMP (user rule): custom pars drive everything; `Out` ops carry output only; own `controls` panel + `controls_window`
opened by an `Opencontrols` pulse; `Pagescope` = slider page, `Pagetabs` off (T-68). No built-in safety limits or warnings: the operator decides
(offer BPM / manual / audio modes, no clamp or flash limiter on by default). Build resolution default 1080x1920 (changeable `Resx/Resy`).

### 4.1 Interface

Outputs: `out` (Null TOP, premultiplied RGBA, 16F, `bgcolora` 0, additive-friendly), `out_state` (Null TOP: engine B state, or a POP->TOP bake for A; for chaining), optional `out_info` (Info CHOP: alive, fps, engine). Inputs (In TOPs, all optional, each with a safe default so the COMP runs alone):
`in_emit` (TOP: emitter map; luma = emit weight, RGB = colour), `in_field` (TOP, RG = 2D push force, e.g. from a blurred frame-difference), `in_points` (TOP 32F RGB positions) and `in_pop`/`in_sop` handled by the `Source` menu.

Custom pages (names are the contract; lower-case par names generated by TD from these labels):

| Page | Pars |
|---|---|
| **System** | `Engine` menu pop/compute; `Play` toggle; `Reset` pulse; `Seed` int; `Count` int (default 65536 compute, 100000 pop; compute rounds to a square N=side^2); `Speed` float 1; `Resx` `Resy` 1080/1920; `Opencontrols` pulse |
| **Emit** | `Source` menu ball / box / ring / line / top / points / sop; `Emitsize` xyz; `Emitpos` xyz; `Rate` (per s) or `Continuous` toggle (compute: respawn on death); `Life` `Lifevar`; `Initspeed` `Initspread` (cone); `Burst` pulse + `Burstcount`; `Emitthreshold` (TOP luma); `Sop` (SOP picker) |
| **Forces** | `Curlstrength` `Curlscale` `Curlspeed` `Curloctaves`(1-3); `Gravity` xyz; `Drag`; `Wind` xyz; `Att1on/pos xyz/strength/soft`; `Att2...`; `Vortexon/axis xyz/strength`; `Fieldstrength` (in_field); `Bounds` menu none/wrap/bounce/kill + `Boundsize`; `Floor` toggle + `Floory` + `Bounce` |
| **Audio** | `Audiosrc` menu off / manual / bpm / chop / file / device; `Bpm`; `Tapnudge`; `Chop` (CHOP picker, channels `kick bass mid high level`); `Smooth`; `Amtcurl` `Amtsize` `Amtbright` `Amtburst` `Amtatt` `Amtspeed` (each 0 = unused); `Manual1..4` sliders |
| **Look** | `Size` `Sizeage` (curve 0-1 start/end) `Sizevar`; `Colormode` gradient-by-age / by-speed / from `in_emit`; `Colour1/2/3` (RGB on a `Colours` page, T-68); `Bright`; `Blend` add/alpha; `Softness` (sprite falloff); `Trails` toggle + `Traillen` + `Trailfade`; `Bloom` amount |
| **Camera** | `Camdist` `Fov` `Orbit` (auto-rotate speed) `Camx/y` ; `Ortho` toggle (2D flow look) |

### 4.2 Shared maths (identical in both engines, so they can be compared)

- Integrator: `F = Curl*k*curl(Psi) + G + Wind + sum(att) + Field - Drag*V ; V += F*dt ; P += V*dt ; age += dt` (mass 1). `dt = Speed/fps_nominal` (fixed step; do not use real dt, so frame-rate dips do not change the sim).
- Hash: `hash_u32` (Wang/lowbias32: `x^=x>>16; x*=0x7feb352d; x^=x>>15; x*=0x846ca68b; x^=x>>16`), `rnd(id,salt)` = `hash(id*2654435761u+salt)>>8 / 2^24`. Respawn salt = frame count (integer, wraps naturally; no float time in hashes, per F22).
- Curl: analytic potential, no texture noise: `Psi(p,t) = (sin(py+1.3t)cos(pz-0.7t), sin(pz+0.9t)cos(px+1.1t), sin(px-0.6t)cos(py+0.5t))` with `p = pos*Curlscale`, curl by central differences h=1e-3. Divergence-free by construction. **Verified offline (my numpy file): max |div| 1.2e-11** (`research_src/BO_particle_sims/ref_particles.py`). Engine A may use `noisePOP curl3d` instead (different field, same statistics) - parity V7 is statistical.
- Age curve: `s = 1 - age/life`; size `Size*(Sizeage lerp)`; default `4s(1-s)`-style grow/shrink from yfx (clean-room formula, credit in notes).

### 4.3 Engine A - POP path (stage by stage, left to right inside the COMP)

Stage boxes (annotate, T-66/T-69), one stage per column:
1. **Source**: `pointgeneratorPOP` (ball/box volume: `shape`, `numpoints`=Count/ratio, `distribution volume`, `createpointprim`) | `toptoPOP` from `in_emit` (`resx/resy`, `rgba color`, `maxpoints`) with a `mathmixPOP` writing `Emit = luma(Color) > Emitthreshold` | `soptoPOP`/`dattoPOP`/`choptoPOP`/`in_points` converted; `switchPOP` on `Source`. Tiny init velocity from `randomPOP` (type direction, attribute `N`) -> particle `Map` page (`initvelocity*`).
2. **Particle**: `particlePOP` (`maxparticles`=Count, `emissionmode` rate|attr, `birthrate`<-Rate (+ audio burst), `life`/`lifevariance`, `initmass 1`, `initdrag 0`, `damping 0` (drag lives in the force shader so both engines match), `attrs` = `Color Emit` carried in, `targetpop` = `loop_end`). **Turn on the input attribute tick marks or the attribute is lost [tut 75525]**.
3. **Fields**: `noisePOP` (`type simplex4d`, `curl3d` on -> `NoiseCurl`, `period`<-Curlscale inverse, `t4d`<-wrapped time, `harmon`<-octaves) ; `lookuptexturePOP` of `in_field` (`lookupindexattr0/1` = `P(0)`,`P(1)`) -> `FieldVec`; `forceradialPOP` x2 (Att1/Att2, `radial` on, `falloff inversedistance`; remember `globforcemult` defaults 0 [dump]).
4. **Force combine (one shader)**: `glslPOP` `bo_force` (`outputattrs = PartForce`, `outputaccess readwrite`, `initoutputattrs` off if every output is written, uniforms on `vec` pages): single dispatch instead of 6-8 Math Mix blocks (cheaper, and avoids the per-frame recompile of F12).
5. **Look attributes**: `glslPOP` `bo_look` writes `Color` (ramp by age/speed from `color` uniforms) and `PointScale` (size curve). Optional `trailPOP` (`attrmatch` on, `attrname PartId`, `length` frames, `ageattr seconds`, `maxls` > real count; resets when count changes).
6. **Loop end**: `nullPOP loop_end`. Everything between particle and `loop_end` re-enters next frame.
7. **Render**: `selectPOP` -> `geometryCOMP` (render+display on, default child deleted) + `pointspriteMAT` (`blending` additive, `pointscaleattrib PointScale`, `colormap` = soft-dot ramp TOP for `Softness`) + `cameraCOMP` + `renderTOP` (`Resx x Resy`, `antialias aa2`, 16F, `bgcolora 0`) -> `bloomTOP` (amount) -> `out`. Trails: Line MAT (width macOS unverified) or points + Feedback TOP fade.
8. **Bake for chaining**: `poptoTOP` (`layout square`) -> `out_state` (optional, off by default: a readback-free GPU->TOP op, cost UNVERIFIED).

GLSL POP force sketch (names must be checked with POP to DAT; `TDIn_X()` reads input 0 at `TDIndex()`):
```glsl
// vec uniforms: uK (curlk, drag, gravity.y, fieldk) ; uAtt1 (xyz, strength) ; uAtt2 ; uWind (xyz, 0)
void main(){
  const uint id = TDIndex(); if (id >= TDNumElements()) return;
  vec3 P = TDIn_P(); vec3 V = TDIn_PartVel();
  vec3 F = uK.x * TDIn_NoiseCurl() + vec3(0, uK.z, 0) + uWind.xyz - uK.y * V;
  vec3 d = uAtt1.xyz - P; F += uAtt1.w * d * inversesqrt(pow(dot(d,d) + 0.05, 3.0));
  d = uAtt2.xyz - P;      F += uAtt2.w * d * inversesqrt(pow(dot(d,d) + 0.05, 3.0));
  F.xy += uK.w * TDIn_FieldVec().xy;
  PartForce[id] = F;
}
```

### 4.4 Engine B - compute TOP path (the fallback; also the default if POP loops misbehave)

State layout (clean-room, simpler than yfx's 4-texel strip): **N = side*side** particles, `side = ceil(sqrt(Count))`; one texel per particle, **3 colour outputs** of one compute `glslTOP` (`mode compute`, `format rgba32float`, custom resolution `side x side`, `outputaccess readwrite`, `clearoutputs` on `Reset`, `inputfiltertype nearest`, `local_size 8x8`, dispatch `ceil(side/8)`):
- out0 = `P.xyz, age` ; out1 = `V.xyz, life` ; out2 = `colour.rgb, seed`.
Inputs: 0 = `in_emit` (or 1x1 white), 1 = `in_field` (or 1x1 zero), 2 = `in_points` (or 1x1 zero). Time/frames/speed/etc. in `vec` slots (`g.seq.vec.numBlocks = 8`, T-68), including an integer `frame` for hashing.

Compute shader sketch (our own; same structure as any particle updater, API names per T-47 and the yfx reference):
```glsl
layout(local_size_x = 8, local_size_y = 8) in;
// uniform vec4 uA = (dt, curlk, curlscale, drag) ; uB = (frame, count, life, lifevar) ; uC = gravity.xyz, fieldk ; ...
uint hash(uint x){ x^=x>>16; x*=0x7feb352du; x^=x>>15; x*=0x846ca68bu; x^=x>>16; return x; }
float rnd(uint id, uint salt){ return float(hash(id*2654435761u+salt)>>8) / 16777216.0; }
vec3 psi(vec3 p, float t){ return vec3(sin(p.y+1.3*t)*cos(p.z-0.7*t), sin(p.z+0.9*t)*cos(p.x+1.1*t), sin(p.x-0.6*t)*cos(p.y+0.5*t)); }
vec3 curlf(vec3 p, float t){ const float h=1e-3; /* six psi taps, central differences */ ... }
void main(){
  ivec2 xy = ivec2(gl_GlobalInvocationID.xy); int side = int(uTDOutputInfo.res.z);
  if (xy.x >= side || xy.y >= side) return;
  uint id = uint(xy.y*side + xy.x); if (id >= uint(uB.y)) return;
  ivec3 c = ivec3(xy, 0);
  vec4 a = TDImageLoadOutput(0, c);   vec4 b = TDImageLoadOutput(1, c);   // UNVERIFIED across frames (V2)
  if (uReset > 0.5 || b.w <= 0.0 || a.w >= uLifeOf(id)) { /* respawn: ball/box/top/points by Source; new life; age 0 */ }
  else { vec3 P=a.xyz, V=b.xyz; vec3 F = ...same terms as 4.3...; V += F*dt; P += V*dt; a = vec4(P, a.w+dt); b.xyz = V; }
  /* bounds: wrap|bounce|kill */
  TDImageStoreOutput(0, c, a); TDImageStoreOutput(1, c, b); TDImageStoreOutput(2, c, col);
}
```
If V2 fails (in-place read-write not stable): switch to the T-47-proven form: `feedbackTOP` (`Target TOP` = the compute out Null, input 0 = initial state) feeding compute **input 0..2**, outputs written with `TDImageStoreOutput` only; one extra texture copy per frame. Keep both behind a `Statemode` menu (`inplace | feedback`) in the System page's advanced section.

Render for B (no readback): `geometryCOMP` `bo_geo`: `instancing` on, `instancecountmode manual`, `numinstances = Count`, child = one `rectangleSOP`/`gridSOP` quad (camera is fixed-facing; for orbit use `instancerottoop` or a tiny billboard in the vertex shader), material = `glslMAT` `bo_mat` (vertex: `int i=TDInstanceID(); ivec2 t=ivec2(i%side,i/side); vec4 a=texelFetch(sState0,t,0);` `pos = P*size(a.w) + a.xyz`; fragment: soft dot * colour * `Bright`, additive blend, kill if `life<=0`) ; sampler `sState0/1/2` = the three outputs. Camera + `renderTOP` as in A -> `bloomTOP` -> `out`. **Probe order if the GLSL MAT cannot see the state**: (1) `instanceop`=state Null TOP with `instancetx/ty/tz = r/g/b` (readback cost UNVERIFIED, measure), (2) `toptoPOP` bake + engine-A render chain, (3) a single full-screen GLSL TOP that splats by gather on a coarse grid (loses exactness; last resort).
Trails for B: `feedbackTOP` (16F/32F) + `levelTOP` multiply `Trailfade` + `compositeTOP` add, behind `out` only when `Trails` on.

### 4.5 Control layer (both engines)

`ctl` CHOP (1 sample per channel, all named): `kick bass mid high level beat phase`. Modes: `off` (zeros), `manual` (sliders), `bpm` (`phase = (absTime.seconds*Bpm/60) mod 1`; `kick = exp(-phase*8)`; off-beat `mid` etc.; Tap nudge shifts phase), `chop` (Select CHOP of the user's channels), `file`/`device` (Audio File In / Audio Device In CHOP -> Audio Spectrum CHOP -> Analyze/Math/Lag, bands 20-120 / 120-500 / 500-4k / 4k+ Hz). Never route the mic to the speakers; this COMP only *analyses* (default output stays Mac speakers, no Audio Device Out inside the COMP). Mapping: each `Amt*` multiplies one channel and adds to the matching uniform before it enters either engine (`Amtcurl` -> Curlstrength, `Amtsize`, `Amtbright`, `Amtburst` -> Burst on kick rising edge, `Amtatt`, `Amtspeed`). No limiter. `ctl` feeds `vec` uniforms only (never Scope expressions).

Camera test input: `media/webcam/webcam_ref_5s.mp4` -> Movie File In -> Resolution -> Frame Difference (Cache/Subtract) -> Blur -> `in_emit` (emit where people move) and Slope TOP of the blur -> `in_field` (push along the motion edges). Optical Flow TOP is unsupported [T-18].

### 4.6 Build order for the builder (stop at each gate, `td_errors` clean, then continue)

0. Read CLAUDE.md, `docs/USING_TD.md` (crash-safe, self-contained COMPs), T-46/T-47/T-64/T-68/T-70/T-71; `td_guide`, `td_status`. Build inside `/project1/lab/BO_particles` only; at most 2 live builders; viewers stay on.
1. **P0 probe (5 min, scratch child `_probe`)**: create `particlePOP`, `glslPOP`, `noisePOP`, `glslTOP`, `glslMAT`, `toptoPOP`; dump `td_get_pars`; Info/POP to DAT of a running Particle POP to record the exact `Part*` names and the Noise POP curl attribute name; check `glslTOP` compute API names (`TDImageLoadOutput`) via a 1-line shader compile. Write the facts to LEARNINGS (T-nn).
2. **Engine B first at N=4096, 64x64** (cheapest, no POP loop crash class): state + update + render; run V1-V4; scale 64k -> 256k -> 1M with `td_perf` between steps.
3. Engine A at 20 k -> 100 k (scratch COMP, restart plan if TD hangs; F11); V5-V7.
4. Control layer + audio + camera input, custom pars, `controls` panel, `Opencontrols`, `td_layout flow`, stage boxes (T-69), look at a window capture (human-readable network).
5. Final: housekeeping, `td_tox_save` the COMP to `output/backups/BO_particles_<stage>.tox` after **every** verified stage (user rule 26 Oct: "save ur projects always so u dont lose ur progress or learnings or node setups"). Agents do not call `td_save_project` (T-71: main session saves after each verified build and autosave runs every 10 min): the builder tells the main session the stage is verified so it saves the `.toe`; the builder writes each new fact/bug into LEARNINGS at once (new T-nn, evidence, cause, rule) and updates the 'Done' list below.

### 4.7 Offline-testable logic (no TD needed)

`research_src/BO_particle_sims/ref_particles.py` (my own numpy, runs with `python3 -I`): hash RNG, analytic curl, integrator, respawn. Results run 26 Oct: divergence max 1.2e-11 PASS; two runs bit-identical PASS; finite PASS; `age <= life` PASS. A builder should extend it into a `td/particles_logic.py` + unit test (same pattern as `builders/previz_stage_logic.py`): `bpm_env(bpm,t)`, `source sampling`, `ctl mapping`, and a `reference_state(seed, frames)` that dumps 64 particles for the live comparison V1.

### 4.8 Live verification numbers (all must be measured, written to LEARNINGS, nothing assumed)

| ID | Test | Pass |
|---|---|---|
| V1 | Engine B, N=4096, `Seed 1`, forces off except curl, Reset, run exactly 240 frames; `td_inspect` 64 sample texels vs `reference_state` | max abs err < 1e-3 (float32 vs float32 maths; exact-hash match for respawn ids) |
| V2 | In-place read-write stability: debug build writes the frame counter into out2.a; 300 frames, read 4 sampled texels a frame late (T-13) | 300/300 equal to the frame stamp (as T-47's metric); if < 100% switch `Statemode` to `feedback` and rerun |
| V3 | NaN/Inf: `td_inspect` min/max of out0/out1 after 30 s and with extreme pars (Curlstrength 50, Drag 0) | finite; position bounded by `Bounds` |
| V4 | Count conservation / respawn: alive fraction `life>0` after 60 s with `Continuous` | 1.0 +- 0.01 (compute); POP: `Info`/POP to DAT numpoints == Count at steady state |
| V5 | Perf (viewers off for the timed run, `td_perf`, 60 s average, 1080x1920 16F, bloom off): B 262 144 (512^2), 1 048 576 (1024^2); A 100 k, 250 k, 500 k | **targets**: B 262 k >= 58 fps, 1 M >= 30 fps; A 250 k >= 58 fps, 500 k >= 30 fps; each with and without trails; record GPU/CPU ms per op |
| V6 | Reset determinism: Reset twice with the same `Seed`; sum of P.xyz over the buffer | equal to 1e-4 relative (B); A statistical only |
| V7 | A vs B parity (same pars, no audio): mean speed, RMS radius, alive fraction at 5 s, 30 s | within 15 % of each other |
| V8 | Audio logic: `Bpm 120` manual clock; kick peaks over 10 s | 20 peaks +-1 frame spacing 30 frames at 60 fps; `Amtburst` adds births only on the rising edge |
| V9 | Long run: 30 min at 250 k (B), watch memory (`td_perf`), no creeping fps | fps drift < 3 %; no VRAM growth (POP VRAM may not drop when cooking is off, POP.md gotcha 7) |
| V10 | Self-contained: delete the controls panel / close `controls_window` (safe_destroy, T-70) and drive `Curlstrength` by `td_set_pars` | look still responds; `Opencontrols` reopens the panel |
| V11 | Webcam ref clip: emit follows motion | alive count rises where frame-difference > threshold; no crash with the mp4 only |

### 4.9 Mac / 31550 caveats to carry into the build

- Engine B state is 32F: 1 M particles x 3 outputs x 16 B = 48 MB; fine. Do not use 8-bit anywhere in the state.
- No `double`, no atomics needed; no Ray POP; collisions are analytic (floor plane, bounds, sphere SDF) in the force shader.
- `maxparticles`/`Count` or `Resx/Resy` changes recreate buffers: changing them live may stall (like yfx's note about changing Particles); the Count par re-inits state on change and is not for performance moves.
- First-run shader compile stall 1-3 s on Metal: warm before a show (T-27 pattern).
- If TD hangs after the first POP loop: stop, do not retry blindly, note build 31550, restart one TD, add the crash to LEARNINGS (F11 class).

## 5. Second, optional spec - `BO_flowfield` (not for v1)

A `glslTOP` compute 2D semi-Lagrangian velocity field (port of touchFluid MIT, in compute form per T-47) that outputs `Field` for `in_field`
so a person or an audio impulse stirs the particles. Only after BO_particles V1-V7 pass; compute-form port is itself unverified.

## 6. MCP tool ideas

- `td_particles_new {engine, count, source}`: builds BO_particles (or any named preset) and returns the V1-V4 numbers (typed builder like `td_comfy_build`).
- `td_pop_probe`: list one POP's attributes, count, bounds, min/max per attribute (POP to DAT behind the scenes; `nextframe`, no stall) - generalises `td_inspect` for attributes.
- `td_sim_check {path, frames, ref}`: run N frames, sample texels, compare with a numpy reference function; reports pass/fail (V1/V6).
- `td_perf_sweep {op, par, values[], seconds}`: step a count par and record fps/ms (V5), viewers off, restore after.
- `td_tear_check {path}`: the T-47 metric packaged (frame-stamp, N frames, ratio right).
- `td_fix_pops {}`: note the POP crash class: on startup warn if a POP loop is cooking and the last session crashed (reads `projects/CrashAutoSave*`).

## 7. Gated items for `docs/FUTURE.md` (not added by this lane)

| Feature | Needs | Note |
|---|---|---|
| Particle POP time-integration toggle, Jitter Birth Position / Jitter Births During Frame, birth-rate fix < 1/frame | 2025.32460 / 32820 | gate `BO_particles` emit-from-points path on `par.jitterbirth`; until then emit from a volume |
| `Render Simple POP`, Text POP, Trace POP, Script POP, Time Filter POP, GLSL Create POP, Line Thick POP | newer builds | text-as-particles and script-driven emitters |
| POP `point()/prim()/vert()` Python access | 2025.32820 | direct state asserts in tests instead of POP to DAT |
| Native arm64 TouchDesigner (T-46 open question) and Hardware Ray Tracing | arm64 build / MoltenVK RT | would re-open Ray POP collisions and pixel-mode multi-pass |
| Object Detection POP (AQ) -> emit points on detections | 2025.32820+, Windows/NVIDIA | a fed `in_points` already accepts any point cloud |
| Optical Flow TOP into `in_field` | not on macOS (T-18) | frame-difference substitute now |

## 8. Done / not done

Done: landscape, mechanisms, spec, offline numpy reference (PASS), gated list. Not done (needs live TD): P0 probe, V1-V11, any perf number, whether the compute in-place
loop and the GLSL MAT state fetch work on 31550/Rosetta/MoltenVK, whether the POP loop with forces survives (F11).

## Sources

[Particle POP](https://docs.derivative.ca/Particle_POP) (fetched 26 Oct) · [GLSL POP](https://docs.derivative.ca/GLSL_POP) · [Write a GLSL POP](https://docs.derivative.ca/Write_a_GLSL_POP) · [Noise POP](https://docs.derivative.ca/Noise_POP) ·
[Compute Particle System v2.0 asset 62080](https://derivative.ca/community-post/asset/compute-particle-system-v20/62080) (CC BY 4.0, Tim Gerritsen / yfxlab; local copy `research_src/community/files/62080/expanded/`, read-only text) ·
[forum 271549: v2.0/2.1 compile failure and v2.2 fix](https://forum.derivative.ca/t/this-marvelous-compute-particle-system-does-not-work-i-leave-it-to-the-experts/271549) ·
[Zenn: GPU particles in TD](https://zenn.dev/omakazu/articles/b03ca981123906) · [Reactive GPU particles 65068](https://derivative.ca/community-post/tutorial/reactive-gpu-particles-touchdesigner/65068) ·
[touchFluid (MIT)](https://github.com/kamindustries/touchFluid) · Bridson et al. 2007 (see O 4.1) · our `ops/POP.md`, `O_generative_simulations.md`, `tutorials/slice_01-03.md`, LEARNINGS T-13/T-15/T-18/T-46/T-47/T-64/T-68/T-70/T-71.
