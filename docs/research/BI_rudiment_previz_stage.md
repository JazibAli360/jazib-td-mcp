# BI - twozero "Previz Stage" rudiment (vankrav) and a clean-room build spec (26 Oct 2026)

Research only. Nothing loaded into TD, nothing installed, no sign-in. TD 2025.31550, macOS Apple Silicon, TD 2 = x86_64 under Rosetta, Vulkan/MoltenVK (T-46: multi-pass GLSL can tear, compute-mode GLSL clean; T-18: Optical Flow / Face Track / Body Track not supported on this Mac).
Tags: **[V]** read this session, **[D]** confirmed in our op index (`ops/INDEX_2025.31550.json`), **[U]** unverified / my design.

## 1. What the original is

### 1.1 What was actually obtained (thin, honest)
- `https://twozero.ai/rudiments/vankrav/previz-stage` (200) and `https://twozero.ai/rudiments` (200) are a **client-rendered SPA shell**: WebFetch returned only the title; curl returned HTML with no body text. No login wall, no 403, nothing bypassed. The parent listing returns the same shell (no list in static HTML). The shell loads analytics (PostHog, Plausible); nothing was run.
- Only static text available [V] (page `<meta>`): title **"Previz Stage"**, author path `vankrav`, description: *"A stage previz in haze: LED screen, crowd and stage light that follows your screen content. Wire any TOP in and see it in the hall."* Canonical host `app.twozero.ai/rudiments/vankrav/previz-stage`.
- `cover.jpg` at that host (51 KB) was fetched and viewed: it shows a **face-landmark overlay** (green outline on a person), i.e. it looks like the *face-tracking* rudiment's cover, not a stage. Treat it as a cover mix-up; it says nothing about previz-stage.
- **No downloadable .tox, no GitHub link, no video link, no licence text, no parameter list** were reachable without running the SPA's JS. So `research_src/rudiments_previz_stage/` was not created (empty dir would mean nothing) and toeexpand was not used. Prior note `AF_peer_td_mcps.md`: twozero's own tools are closed `.tox`; rudiments are presumably downloaded inside twozero's app after login (UNVERIFIED), so their licence is unknown; irrelevant for clean-room.
- Everything below in 1.2 is therefore **inferred from the one-sentence description** [U]; the spec in section 2 is our own design and does not depend on the original's internals.

### 1.2 Inferred feature set (from the description)
| Feature | Inference [U] |
|---|---|
| Input | one TOP in ("wire any TOP in") = the screen content |
| LED screen | a 3D quad / curved or multi-face wall in a virtual hall textured with the input TOP, emissive |
| Haze | volumetric atmosphere, light beams visible in air (fog, additive cones or ray-march) |
| Crowd | audience silhouettes (instanced low-poly heads/bodies) lit by the screen and stage light |
| "Stage light that follows your screen content" | screen-reactive lighting: average / regional colour and brightness of the input drive light colours/intensity on stage and crowd |
| Output | a rendered TOP of the hall (camera view), probably with an orbit/camera control |
Not known: parameter names, camera presets, crowd count, UI.

### 1.3 Related prior art in our repo (reuse, do not rebuild)
`AB_projection_mapping.md` (virtual room, Light COMP projmap, quadReproject), `AW_fulldome_simulator.md`, `P_realtime_3d_looks.md`, `AT_projector_coverage.md`, `BB_test_patterns_sync.md` (test_pattern COMP can be the input), `AC_audio_reactive_designs.md`, `td-port` LEARNINGS (no stage mockups in generated visuals applies to *generation*, not to this previz tool). The PF26 stage is Vendor Package R02: nine faces 20/10/10/10/30/10/10/10/20 ft, 9984x3840 native (CLAUDE.md); the previz should default to those faces.

## 2. Clean-room build spec: `previz_stage` COMP

Goal: drop in any TOP (our content, Syphon in from Resolume) and see it on a virtual PF26 R02 wall in a hazy hall with a crowd and screen-following stage light. Self-contained COMP per USING_TD rules; no shared panel.

### 2.1 Custom parameters (page names: capital then lowercase/digits)
- **Stage** page: `Faces` (menu: r02 nine-face / flat single / custom), `Facew1`..`Facew9` (ft, defaults 20/10/10/10/30/10/10/10/20), `Faceh` (ft, default derived so 9984x3840 aspect holds), `Gapft`, `Anglestep` (deg between faces, default 0 flat), `Stagedepth`, `Screenelev`, `Screenemit` (emission gain, default 1.0).
- **Crowd** page: `Crowdon`, `Count` (default 1500), `Rows`, `Spacing`, `Heightvar`, `Seed`, `Sway` (0-1), `Swayspeed`, `Hands` (fraction with raised arm), `Crowdlit` (how much the screen lights them).
- **Haze** page: `Hazeon`, `Density`, `Falloff` (height), `Drift` (noise speed), `Scatter` (beam visibility), `Hazecolor`.
- **Lights** page: `Lightson`, `Beams` (count 2-12), `Spread`, `Intensity`, `Follow` (0-1 how much beams take screen colour), `Reactmode` (menu: average / left-right regions / per-face / dominant), `React speed` -> `Reactlag` (s), `Beamsweep`, `Beamsweepspeed`, `Strobe` (0-1, safe-capped, see 2.9).
- **Camera** page: `Preset` (menu: foh, stage left, stage right, drone, crowd pov, orbit), `Fov`, `Orbitx/Orbity/Orbitdist` (also drive-able), `Tilt`, `Autoorbit`, `Orbitspeed`.
- **Output** page: `Resx`, `Resy` (default 1920 x 1080), `Msaa`, `Showscreenonly` (bypass hall, show input), `Exposure`, `Bloom`.
- **Audio** page (optional): `Audioreact`, `Audiogain` -> modulates beam intensity / sway from an In CHOP (`audio` In CHOP, wired by the user from `AC_audio`; no device opened inside).
- **Window** page: `Opencontrols` (pulse), `Openview` (pulse), `Reset` (pulse).

### 2.2 I/O
`in1` (In TOP: content, any res; unwired -> internal test ramp so the COMP is never black by accident), `in_audio` (In CHOP, optional). `out1` (Out TOP) = the rendered hall only. `out_screen` (Out TOP, second output) = the content after resolution fit, handy for the real wall. `out_react` (Out CHOP): `r g b lum` + per-face lum, so other COMPs can use the same analysis. No control op sits in any Out chain.

### 2.3 Internal network, stage by stage (plan stored via `td_layout stages`)
1. **Input**: `in1` -> `fit` (Resolution/Fit TOP to the face aspect) -> `screen_tex` (Null). Cache not needed.
2. **Analysis**: `screen_tex` -> `an_down` (Resolution TOP to e.g. 16x6) -> `an_chop` (TOP to CHOP; channels r,g,b per pixel) -> `an_math` / `an_lag` (Lag CHOP, `Reactlag`) -> `react` Script CHOP or Math chain producing region colours (average, L/R, per-face, dominant via max-saturation pick). Avoid Analyze TOP latency issues by using the small TOP to CHOP only (cheap, no GPU readback of full frame). [D] toptoCHOP, lagCHOP, mathCHOP, analyzeTOP exist.
3. **Stage geometry**: `faces` Script SOP or Table DAT + Replicator: one Geometry COMP with a `Grid SOP` per face (or one merged mesh with UVs laid out in the 9984 atlas as in PF26 mapping). Material: `Constant MAT` or `Phong MAT` with `screen_tex` as colour map + emission gain (`Screenemit`); for the atlas case each face samples its own UV window (UV from the face table). Frame/truss: `Box SOP`s with Phong grey.
4. **Crowd**: one Geometry COMP, instancing a single low-poly body (sphere+capsule or small imported-free SOP) from an instance table (Script DAT builds N rows with tx,ty,tz,scale,rot,sway-phase; **pure function, seeded**). Sway done in the instance chain (Noise CHOP / GLSL MAT vertex offset by time+phase) so no per-frame Python. Material `Phong MAT` dark rim; screen light on them = a Light COMP (area-ish) of the screen average colour (`react`) plus a cheap emissive rim term by distance to the screen. Raised hands: second instance set (thin capsule) for a `Hands` fraction.
5. **Lights**: `Beams` Light COMPs (cone type) on a truss row; colour = `Follow` mix of base colour and `react` region colour, intensity = `Intensity` x (audio opt.) x lum; pan/tilt from a `Beamsweep` LFO CHOP. Spec check needed: Light COMP cone/`lighttype`, `coneangle`, `projmap` pars must be read from `ops_COMP_2025.31550.json` before building (not asserted here) [U].
6. **Haze**: two layers, both cheap: (a) in-render: Render TOP depth + a `glsl_haze` TOP (**compute mode or single pass**, T-46) that takes colour + depth TOP, computes exp fog by depth and height plus noise-scrolled density; (b) beam visibility: add cone volumes (`Cone`/tube geo with additive, depth-faded MAT) per light so beams show in air without real ray-marching. Optional later: true ray-march of the cone in the haze GLSL (needs light positions as uniforms; compute mode).
7. **Camera + render**: Camera COMP driven by `Preset` table (Table DAT of poses) + orbit pars; `Render TOP` (`Resx/Resy`, MSAA, linear half-float so beams and screen can exceed 1.0) -> `glsl_haze` -> `bloom` (blur + composite or built-in Bloom if present, verify) -> `grade` (Level TOP: exposure) -> `out1`. `Showscreenonly` switches via a Switch TOP.
8. **Controls**: `controls` (autoUI panel, `Pagescope` = slider page, `Pagetabs` off, `align verttb`, clones cut), `controls_window`, `view_window` (Window COMP showing `out1`, opened by `Openview`). `Opencontrols` pulse callback in a Parameter Execute DAT.

### 2.4 Key GLSL / Python sketches (ours)
```glsl
// glsl_haze (single pass, no feedback). Inputs: sTD2DInputs[0]=colour, [1]=depth (linear)
uniform float uDensity, uFalloff, uTime; uniform vec3 uHaze;
out vec4 fragColor;
void main(){
  vec2 uv = vUV.st; vec4 c = texture(sTD2DInputs[0], uv);
  float d = texture(sTD2DInputs[1], uv).r;           // view distance
  float n = texture(sTD2DInputs[2], uv*2.0+vec2(uTime*0.02,0)).r;
  float y = (1.0-uv.y);                              // cheap height term; replace with world-y later
  float fog = 1.0 - exp(-uDensity * d * (0.6+0.8*n) * exp(-uFalloff*y));
  fragColor = TDOutputSwizzle(vec4(mix(c.rgb, uHaze*(0.2+c.rgb), fog), 1.0));
}
```
```python
# pure, unit-testable (module crowd_logic.py, no td import)
import random
def crowd_rows(count, rows, spacing, hvar, seed, hall_w, front_z):
    r = random.Random(seed); per = -(-count // rows); out = []
    for i in range(count):
        row, col = divmod(i, per)
        x = (col - per/2) * spacing + r.uniform(-.2, .2) * spacing
        z = front_z + row * spacing * 0.9 + r.uniform(-.2, .2) * spacing
        out.append((x, 0.0, z, 1.0 + r.uniform(-hvar, hvar), r.uniform(0, 6.2832)))
    return out
def region_colors(grid, mode):   # grid: [[(r,g,b)...]] small; returns list of (r,g,b)
    ...
def r02_face_layout(widths_ft, height_ft, gap_ft, angle_deg): ...   # positions + UV windows
def lerp_follow(base, screen, follow, lag_alpha): ...
```

### 2.5 Pure-Python (offline unit tests, no TD)
`crowd_rows` (determinism by seed, count, bounds, row spacing), `r02_face_layout` (widths sum to 130 ft, aspect 9984:3840 target, UV windows tile 0..1 without overlap), `region_colors` (average/L-R/per-face/dominant on synthetic grids), `lerp_follow`/lag maths, camera preset table interpolation, strobe-safety limiter (max 3 flashes/s, section 2.9). Tests live beside the module under `td-port`-style layout is **not** used (nothing shared); put them in `jazib-td-mcp/tests/` per existing convention (check before creating) [U].

### 2.6 Verify live (numbers to check; `td_inspect`, `td_window_capture`, `td_errors`, `td_perf`)
1. COMP cooks with no errors; `td_errors` clean; `td_perf` shows `out1` render time (record ms; no fps claim without a measured number).
2. Feed `test_pattern` (BB) or a ramp: `td_inspect out1` not black, mean in range, no NaN; `out_screen` equals input resized.
3. Change input colour red -> `react` Out CHOP `r` rises, `g,b` fall within `Reactlag`; beam colour follows (`td_get_pars` on a Light COMP `colorr`).
4. `Follow=0` -> beams stay base colour (assert unchanged). `Crowdon=0` -> instance count 0 and render mean drops.
5. Haze `Density=0` vs 1: far-region luminance (sample grid) differs; look for tearing/partial frames (T-46): capture 5 consecutive frames and compare edges.
6. Stage faces: world width = 130 ft x unit scale; 9 UV windows non-overlapping; zoom camera, check seams.
7. Audio: feed `AC_audio`; `Audioreact` on -> beam intensity channel moves with level; speakers untouched (Out stays default speakers; we add no device ops).
8. Capture with `td_window_capture` for the readable-network check and a viewport still.

### 2.7 Mac / 31550 caveats and fallbacks
- Render + GLSL under Vulkan/MoltenVK: keep haze to single-pass or compute GLSL (T-46); no feedback chains for haze (use noise scroll). If tearing: fall back to non-GLSL fog (Level/Composite with depth-ramp) [U].
- 1500+ instances with MSAA at 1080p is fine in principle but not measured; start at 600 and measure on this Mac; instancing via Geometry COMP `instancing` [D].
- Lights: many shadowless cone Lights are cheap; no shadow maps. If Light count is slow, replace with additive cone meshes only.
- Atlas 9984x3840 texture is big: previz uses a down-fit (`Fit` to e.g. 2496x960) not the native.
- Syphon/NDI input is the user's job (own In wiring); the COMP only takes `in1`.

### 2.8 Newer-build features for `docs/FUTURE.md`
POP-based crowd (Particle POP / instancing from POPs, [D] POP ops exist in 31550 but behavior unverified for large counts); true volumetric ray-march haze using compute shaders with 3D textures; `Render Pick`/`Depth of field` improvements; any Light COMP volumetric option if a newer build adds one. Gate by build/API, list one line each.

### 2.9 Safety
Strobe/flash simulation must obey the project's flash limits (<=3 flashes/s default, brightness delta cap) from `concert-visuals-research`; previz-only, default `Strobe=0`.

## 3. Estimated build time (previz_stage only)
Spec + pure-Python + tests: 1-1.5 h. Network, instancing, lights, haze, camera presets: 2-3 h. Controls/windows + readable layout + live verification and fixes: 1-1.5 h. **Total ~4-6 h of agent time; ~2.5 h wall-clock with parallel lanes** (logic/tests, network build, GLSL/haze).

## 4. Other five rudiments in the request (not covered here)
The user's message also lists timeline, zerror, screen-reprojection, db-meter (twozero) and vankrav face-tracking. This file covers previz-stage only (the assigned step). Notes for those lanes: face tracking on this Mac cannot use Face Track CHOP/SOP (T-18); see `D_camera_mediapipe.md` (TD Python has OpenCV 4.11.0 x86_64 + NumPy 2.1.2, no mediapipe/onnxruntime; routes = Web Render MediaPipe plugin, arm64 helper e.g. Apple Vision via td-port `jzb_camera_bridge`, or OpenCV Haar/DNN in a Script TOP); test on `media/webcam/webcam_ref_5s.mp4`, live camera only on request. db-meter: In CHOP -> Analyze CHOP (rms) -> Math (20*log10) -> ballistic Lag; fed by `AC_audio`, output stays the Mac speakers. The same static-shell limitation (SPA, no body text via fetch) will likely apply to those pages.

## 5. Open questions for the user
1. Can you paste the page's visible text or a screenshot (or the .tox if you own a copy)? Then section 1 gets real parameters.
2. Default wall: R02 nine faces at 9984x3840 (my default), or a generic single LED screen?
3. Crowd density / look: dark silhouettes (default) or lit?
