# particles: BO_particles GPU particle system (live v1 in main, 26 Oct 2026, TD 2025.31550; V5 partial)

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

`/project1/lab/BO_particles`. Spec: `docs/research/BO_particle_sims.md` section 4 (clean-room; credits there: Tim
Gerritsen's Compute Particle System, CC BY 4.0, for the state-texture + instanced-fetch idea; Bridson et al. 2007 curl
noise). **Status: v1 built live 26 Oct on 31550 (`panel=False`, zkit blocked by T-84); V0 V1 V3 V4 V6 pass, V5 partial (T-84); `output/backups/BO_particles_v1.tox`.** Everything marked **LIVE CHECK** must be confirmed
on 31550 and written to LEARNINGS (new T-nn) by the live lane.

## Which engine and why
Only the spec's **engine B (compute)** is built: one compute GLSL TOP holds all state in a float texture and a GLSL MAT
draws instanced quads that read that texture, so the whole loop stays on the GPU (no POP loop, no CPU readback).
Reasons: compute-mode GLSL TOP is the multi-pass form proven clean on this Mac (T-47), the compute + Feedback TOP loop
is already verified live (motion_trail), POP loops have an open macOS crash class (F11), and the POP attribute names
are not yet probed. The POP engine A is **not cheap** (a second network, its own probe, its own crash risk), so there
is no `Engine` par; add it later only if V5 shows compute cannot hold 60 fps.

## Build (live lane, ~15 min)
0. Read CLAUDE.md, `docs/USING_TD.md`, LEARNINGS T-46/T-47/T-64..T-78. `td_guide`, `td_status`. At most 2 live
   builders; un-park only `BO_particles`; viewers stay on.
1. Build (one td_exec):
   ```python
   ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/particles.py').read(), ns); ns['build']('/project1/lab')
   ```
   Idempotent and T-70 safe (closes its own `controls_window`, `_sd` = safe_destroy, zkit panel rebuilt in place, the
   pane is never moved). No numpyArray/evalTextSize in the builder (T-74/T-76); cookRate untouched (T-64).
2. Next call (>= 2 frames later): `td_errors /project1/lab/BO_particles` (compile errors of `state`, `pmat`, `trail`,
   `cam_diff` show here), `td_layout check` (ok, no intruders/unboxed/overlaps), list children for strays (e.g. a
   `pmat_vertex1` would mean TD auto-docked DATs under other names).
3. Default look: 65 536 particles, a curl-noise cloud from a 0.3 ball, orange -> pink -> blue by age, additive.
4. Run the checks below in order, `td_tox_save` to `output/backups/BO_particles_<stage>.tox` after each verified stage,
   tell the main session to save the .toe (agents never save, T-71), write every new fact/bug to LEARNINGS at once.

Offline tests (39, ~1 s): `python3 -I -m unittest discover -s test -p 'test_particles.py'` (logic, the float64
reference of the shader, GLSL compiled against TD-like stubs with glslc, builder static checks).

## Files
| File | What |
|---|---|
| `builders/particles.py` | builder `build(parent_path='/project1/lab', panel=True)` |
| `builders/particles_logic.py` | pure logic (copied into `particles_logic`): par contract `PAGES`, per-frame `step()`, float64 reference `reference_run()`, `compare_state()` for V1 |
| `builders/glsl/particles_state.glsl` | compute: spawn / curl + forces / bounds (copied into `state_compute`; `state_inplace` = same with `#define STATE_INPLACE 1`) |
| `builders/glsl/particles_vert.glsl`, `particles_pixel.glsl` | GLSL MAT `pmat`: instance -> state texels -> camera-facing soft dot |
| `builders/glsl/particles_trail.glsl` | compute: trails = max(render, last * Trail keep) |
| `builders/glsl/particles_camdiff.glsl` | compute: webcam clip frame difference (rgb colour, a = motion) for the emit test |
| `test/test_particles.py` | 39 offline tests |

## Network (stages, left to right)
Controls (zkit `controls` + `controls_window`, `particles_pulses` Reset/Burst -> engine) | 1 Inputs (`in_emit` /
white `emit_default` / webcam `test_clip -> test_small -> test_prev -> cam_diff` -> `emit_src`; `in_field` /
`field_default` -> `field_src`; `in_ctl`) | 2 Engine CPU (`particles_logic`, `engine` Script CHOP = 20 samples x
`x y z w` = the `uP[20]` rows, `info` named channels -> `out_info`) | State feedback (`state_init` zeros 32F,
`state_fb` Feedback TOP of `state`, `state_src` switch) | 3 Simulate (`state` compute GLSL TOP, rgba32float, width
3*side, height side, -> `out_state`) | 4 Render (`pgeo` Geometry COMP: one 1x1 `quad`, instancing manual, count =
Count; `pmat`; `pcam`; `render` Resx x Resy 16F, transparent) | Trail feedback (`trail_blank`, `trail_fb`) | 5 Post +
out (`trail` compute, `sw_trail`, `bloom`, `sw_bloom`, `out1`). Only the selected switch inputs cook (trail, bloom,
webcam chain).

State texture, particle id = y*side + x: texel (3x, y) = P.xyz, age; (3x+1, y) = V.xyz, life; (3x+2, y) = colour.rgb,
r. Alive = 0 <= age < life; age < 0 = dormant (Stagger: first births spread over one life); life 0 = dead slot.
Row 0 = bottom (T-58). `particles_logic.id_texel(i, Count)` gives the texel of id i.

## Parameters (custom pages; zkit panel shows all seven; pulse `Opencontrols`)
| Page | Pars |
|---|---|
| System | Play, Reset, Seed, Count (re-inits; rounds up to side^2 slots), Speed, Stagger, Statemode (feedback = Feedback TOP, default / inplace = read-write own output), Debugstamp (V2 only), Resx, Resy |
| Emit | Source (ball / box / ring / line / top = `in_emit` weight map / points = `in_emit` RGB as XYZ, a > 0), Emitinput (auto / in_emit / webcam clip diff / none = white), Emitweight (luma / alpha), Emitmode (continuous = reborn the frame it dies / rate), Rate (per sim second), Life, Lifevar, Emitpos, Emitsize, Emitdir, Initspeed, Initspread (0 = along Emitdir, 1 = any direction), Emitthreshold, Burst, Burstcount |
| Forces | Curlstrength, Curlscale, Curlspeed, Curloctaves (0-4), Gravity, Drag, Wind, Att1on/pos/strength/soft, Att2..., Vortexon/axis/strength, Fieldstrength (`in_field` rg over the Boundsize x/y box), Bounds (none/wrap/bounce/kill), Boundsize, Floor, Floory, Bounce |
| Audio | Audiosrc (off / manual / bpm / chop), Bpm, Tapnudge (phase), Chop (CHOP with `kick bass mid high level`; empty = `in_ctl`), Smooth s, Amtcurl (bass), Amtsize (kick), Amtbright (level), Amtburst (kick rising edge -> Amtburst x Burstcount births), Amtatt (mid -> both attractors), Amtspeed (level), Manual1..4 (kick bass mid high; level = mean) |
| Look | Size (quad half-width, world units), Sizevar, Sizeage (0 = constant, 1 = 4x(1-x) grow/shrink), Colormode (age / speed / in_emit colour / white), Speedref, Bright, Blend (add / alpha over), Softness, Trails, Trailfade (keep per frame), Bloom |
| Colours | Colour1 (young), Colour2, Colour3 (old) |
| Camera | Camdist, Fov, Orbit deg/s, Camx, Camy, Ortho |
Maths (same in shader and reference): fixed step dt = Speed/60 per cooked frame; `F = curlk * sum_o 0.5^o curl(Psi)(P *
Curlscale * 2^o, t + 17o) + G + Wind - Drag V + attractors (s d / (|d|^2 + soft)^1.5) + vortex (s axis x P) + field`;
`V += F dt; P += V dt`. Curl is the **analytic** curl of the spec's Psi (the spec sketched central differences; analytic
is exact in float32 and tested equal to central differences to 1e-6). Hash = lowbias32, salt = hash(Seed) ^
frame * 0x9E3779B9 (integer frame, wraps at 2^24; curl time wraps at 2000*pi). No limits on the look.

## Live checks (in order; write every number to LEARNINGS)
Read pixels only with the state unchanged (Play off) and >= 2 frames after any change (T-74); one readback at a time.
Snippet used below (td_exec, after Play off and 2+ frames):
```python
c = op('/project1/lab/BO_particles'); L = c.op('particles_logic').module
arr = c.op('state').numpyArray(delayed=False)          # H x W x 4, row 0 = bottom
raw = {p.name: p.eval() for p in c.customPars if p.style != 'Pulse' and p.page.name != 'Zkit'
       and isinstance(p.eval(), (bool, int, float, str))}
F = int(c.op('info')['frame'].eval())
result = L.compare_state(arr.tolist(), raw, F + 1)    # frames incl. the reset frame
```
| ID | Do | Expected |
|---|---|---|
| V0 | build, td_errors, td_layout check, look at out1 | no errors; check ok; a coloured cloud moving; `info` frame counting up |
| V1 | `td_set_pars` = `particles_logic.V1_PARS` (Count 4096, Seed 1, Stagger off, Life 100, Drag 0.8, curl only), Reset, wait ~4 s, Play off, 2 frames, snippet | `result` P < 1e-3, V < 1e-3, age < 1e-4 (float32 GPU vs float64 reference; offline a 1e-6 start offset grows to 9e-6 in 240 frames). At F = 240 for instance: id 12 texel (36, 0) P (-2.278207, -2.326381, -2.330937) age 4.0, V (-0.023842, -0.354292, -0.865856); id 94 texel (90, 1) P (-2.190602, -1.376189, -1.995031) |
| V2 | Count 4096, Debugstamp on, an Execute DAT `_v2` (underscore: the next rebuild removes it) `onFrameEnd` reading `state.numpyArray(delayed=True)[:, 2::3, 3]` for 300 frames: min == max (one stamp per texture) | 300/300 single-stamp frames (T-47 metric). Run for Statemode feedback AND inplace; if inplace < 300/300 keep feedback (the default) and note it |
| V3 | Curlstrength 50, Drag 0, Bounds wrap, 30 s, Play off, `np.isfinite(arr).all()`, max abs P per axis | finite; abs P <= Boundsize per axis (2.5, 4.5, 2.5) |
| V4 | defaults, 60 s: alive = `(a >= 0) & (a < life)` over ids < Count (`a = arr[:, 0::3, 3]`, `life = arr[:, 1::3, 3]`); then Emitmode rate, Rate 5000, Lifevar 0, Reset, 10 s | continuous 1.000 (reference: 1.0 at 60 s); rate: alive 20 000 +- 84 (= Rate x Life, one frame of births), `info` head = births so far mod Count (reference: 49 999 births in 600 frames) |
| V5 | perf: pane on another COMP (T-73), other lab COMPs parked, 60 s each at 1080x1920, bloom/trails off, then each on: Count 65 536, 262 144, 1 048 576. `td_perf` per op (engine CPU, state, render GPU) + real fps from wall-clock frame starts (T-73, not absTime) | **target: 262 144 at 60 fps with the COMP <= 3 ms** (user budget); stretch: 1 048 576 >= 30 fps (spec). Engine Script CHOP expected ~0.3-0.5 ms (reads ~110 pars; strobe's engine 0.21 ms). Record GPU ms of `state` and `render` |
| V6 | V1 pars with Play off, Reset, 2 frames, `arr[:, 0::3, :3].sum()` over ids < 4096; Reset again, same | sum P 17.839611 (reference, 4096 ids, spawn state) to 1e-4 relative, identical across the two resets; sum life 409 600 |
| V7 | no POP engine, so: defaults, statistics over all alive particles at 5 s and 30 s vs reference (512 sampled ids) | 5 s: alive 0.975, mean speed 0.749, rms radius 1.585; 30 s: alive 1.000, mean speed 0.746, rms radius 1.840; within 10 % |
| V8 | Audiosrc bpm, Bpm 120, Smooth 0: record `info` kick 10 s; then Emitmode rate, Rate 0, Amtburst 1, Burstcount 10 | 20 kick peaks, 30 frames apart at 60 fps; `info` births = 10 on each kick frame only (offline: 200 in 10 s) |
| V9 | 30 min at 262 144 (pane elsewhere) | fps drift < 3 %, no GPU memory growth (`td_perf`) |
| V10 | close `controls_window`, safe_destroy the panel (T-70), `td_set_pars Curlstrength 3` | look responds; `Opencontrols` rebuilds/reopens the panel |
| V11 | Emitinput cam, Source top, Emitweight alpha, Emitthreshold 0.3, Emitmode rate, Rate 20000, Life 1 | particles appear only where the clip moves; no crash with the mp4 |

## LIVE CHECK (facts this prep could not confirm offline; probe first, record in LEARNINGS)
1. **Compute in-place read**: `TDImageLoadOutput(0, ivec3)` exists on 31550 with `outputaccess = 'readwrite'`
   (menu name) and `clearoutputs` off keeps content across frames. If the name differs, edit the `#ifdef STATE_INPLACE`
   lines to `imageLoad(mTDComputeOutputs[0], ivec3(t0, 0))` (check the declared image type in the GLSL info DAT).
   Default Statemode is `feedback` (proven form), so this only gates the `inplace` option.
2. **Array uniform on a GLSL TOP**: `array0` (`uP`, vec4, CHOP `engine`, `uniformarray`) from a 20-sample, 4-channel
   Script CHOP fills `uP[0..19]` in sample order (proven on GLSL MAT in projector_dome; not yet on a GLSL TOP).
3. `computedat` switched by expression between `state_compute` / `state_inplace` recompiles; a leading
   `#define STATE_INPLACE 1` line is accepted before TD's own header.
4. **Instancing without an instance OP**: `pgeo` `instancing` on, `instancecountmode 'manual'`, `numinstances` =
   Count draws Count quads and `TDInstanceID()` = 0..Count-1. Also whether the Render TOP culls `pgeo` by the 1x1
   quad's bounds (particles vanishing when the origin leaves the view = culling; then look for a bounds/cull par).
5. `uTDMats[TDCameraIndex()].worldCam` / `.proj` member names in a GLSL MAT vertex shader (TD's TDMatrix struct).
6. `pmat.postmultalpha = False` gives straight premultiplied output; additive (`srcblend one`, `destblend one`)
   and alpha (`omsa`) look right over a dark background; `TDOutputSwizzle` exists in a MAT pixel shader.
7. Menu names not in the 31550 dump: `glslTOP.inputfiltertype 'nearest'`, `outputaccess 'readwrite'`,
   `renderTOP.antialias 'aa1'` (builder falls back to `aa2`), `cameraCOMP.projection 'ortho'`.
8. Feedback TOP `state_fb` keeps `rgba32float` (format follows `state_init`); after a Count change the shader's size
   guard resets the state (T-35: no out-of-bounds reads). Change Count at 4096 -> 16384 first, watch for a crash.
9. In TOP detection: with nothing wired into the COMP, `emit_src` / `field_src` index 0 (`CONNECTED` expression,
   from strobe.py).
10. Script CHOP `engine` cooks once per frame via its `Frame` par (`absTime.frame`, strobe pattern) and its cost.
11. `rectangleSOP` `sizex`/`sizey` = 1 gives P.xy in -0.5..0.5 (the shaders assume it).

## Not done / open
- POP engine A (spec 4.3) and its V7 parity: not built (see above).
- Audio file / device input inside the COMP (spec 4.5): use Audiosrc CHOP with `AC_audio/ctl_out` or `td_live_audio`.
- `in_field` from the webcam (Slope TOP of the blurred difference): wire it externally for now.
- Collision with a sphere SDF; flocking; `BO_flowfield` (spec 5).

## Perf note (26 Oct, 31550, perf lane; T-100)
262 144 particles: render 3.6 ms (1080x1920, Size 0.012), 3.1 ms at Size x0.25, not lower at 540x960: the cost is per
instance (instanced 4-vertex quad, 3 state texel fetches per vertex), not fill. Options, not built: point sprites
(one vertex per particle, gl_PointSize + point coord in the pixel shader, no instancing), or an LOD that draws Count/2
instances with Size x1.4 for the far / dense case. Engine Script CHOP 0.43 ms CPU per frame. Panel: see zkit_perf.md.

## Lane G (27 Oct 2026, TD 2025.31550, build TD b3): light trails, vortex, strands, palette, presets
Rows TC-08 (light-trail ribbons, `docs/research/FX7b_td_creators_2025.md`) and TC-13 (spiral light strands). GLSL /
state-texture routes only (no POP buffers, T-124). Offline: `builders/particles_logic.py` (pars, rows, float64
reference incl. the new forces / source, presets), `particles_state.glsl` / `particles_vert.glsl`, builder, 46 tests
(`test_particles.py`, class `LaneG`), glslc. Live checks: `builders/particles_checks.py`.

| Piece | What |
|---|---|
| Spiral fields (Forces page, `Sp1*`, `Sp2*`) | Force-Radial-POP-like, each on its own: centre, axis, swirl (tangent), pull (toward the axis), lift (along it), radius R: everything x R^2 / (d^2 + R^2), d = distance to the axis line (R 0 = no falloff). Rows uP[20..25]; both in the shader loop and `spiral_force()` |
| Source `strands` (Emit page `Strands`, `Strandjitter`) | each birth picks seed k of K on the unit ring (x Emitsize) + a box jitter; particles of one seed follow nearly the same path, trails / feedback join them into strands. colour.w = (k + 0.5) / K, so Size var and palette `random` give one value per strand |
| Palette (Palette page, Colormode `palette`) | W1-B convention: `pal` Script CHOP (palette_map_logic, read only) -> `uPal[16]` + `uPalCtl` on `pmat`; t = Palpos + Palspread x attribute (age / speed / random = strand / height); `px_palette.glsl` prepended to the vertex shader |
| Light trails (Lines page, TC-08) | `PX_lines` built INSIDE by `builders/px_lines.py` (imported, not edited): Trails in points mode, in_points = `state` (Ptstride 3 = the P texel), Camera = `pcam`, Maxseg = tracks x samples; its pars linked by expression to the Lines / Palette pages (`LINE_PAIRS`), the rest of its pages stay editable. `dots_sw` = dots or black under the trails (Linedots off: the dots render never cooks), `sw_lines` (Lineson) feeds bloom. A respawn jump > Linemaxjump starts a new trail (no bridge). Ortho camera is not followed by PX_lines (perspective only) |
| Presets (`particles_logic.PRESETS`, builder `preset(comp, name)`, zkit rows 1-5) | FULL state (defaults + preset; `PRESET_KEEP` = Resx Resy Statemode Debugstamp left alone): default, lighttrails, vortex, strands, lightvortex |

### LIVE CHECKS (lane G, b3)
| # | Check | Expected |
|---|---|---|
| G1 | build from the builder on b3; `td_errors`; layout check | no errors; state / pmat (with palette) / pal / PX_lines seg + hist + lmat compile |
| G2 | V1 pars -> `state(C, 'V1')`; V12 pars (spirals + strands) -> `state(C, 'V12')` after ~4 s, Play off | P, V < 1e-3, age < 1e-4 (float32 vs float64) |
| G3 | each preset, then `preset_state` | 0 mismatches; vortex -> default leaves Sp1on off (no inheritance) |
| G4 | lighttrails: `lines(C)` (Play off) | head vs state max err <= 1e-6; slots written > 0.9; finite |
| G5 | Lineson off -> `passthrough(C)` | max diff 0 |
| G6 | Colormode palette, Palsource cyan_magenta -> `palette(C)` | uPalCtl.x = 3; pal rows = the preset stops; capture |
| G7 | cost per preset (`cost_start` / `cost_read`, other COMPs parked, pane off) | default <= ~3 ms target; record lighttrails / vortex / strands |

### Verified live (lane G, 27 Oct 2026, 2025.31550, build TD b3; machine load avg 36-44, 5 TDs)
Built from the builder on b3 (`build('/project1/lab')`, 63 ops + PX_lines 27, zkit panel 152 knobs, presets seeded in
zk_presets slots 1-5), td_errors clean, layout ok. Checks with `builders/particles_checks.py` (second delayed read):
| # | Result |
|---|---|
| G1 | 0 errors; state, pmat (palette prepended), pal, PX_lines seg / hist / lmat / comp compile; Effon on: state (effector prefix) compiles |
| G2 | V1: P 4.5e-7, V 4.3e-7, age 9.2e-7 (104 frames); V12 (both spirals + strands + curl): P 1.6e-6, V 1.7e-6, age 1.1e-6 (115 frames) |
| G3 | every preset 153 / 153 pars = `preset_pars` (0 mismatches) in the order vortex -> default -> strands -> lightvortex -> lighttrails; zkit Recall slot 3 = vortex exactly |
| G4 | lighttrails, Play off: hist head vs state max err 0.0 (1024 tracks x 40), slots written 1.0, finite; Status "segments 40960 of 40960" |
| G5 | Lineson off: sw_lines == sw_trail (max diff 0), PX_lines seg stops cooking; Lineson on + Linedots off: the dots render stops cooking |
| G6 | Colormode palette: pal rows = the stop preset, uPalCtl bound on pmat (count from the stops) |
| G7 | cost (cost_start / cost_read: median of 120 pulled frames, cpu + gpu of every op in the COMP incl. PX_lines, pane off): default 4.3-5.2 ms (dots render CPU 1.4-1.7 = the floor, engine 0.7); lighttrails 4.9 (PX_lines render CPU ~2 + GPU ~0.9); lightvortex 6.4; vortex 6.9 (131k + trails + bloom: the stock Bloom TOP alone is ~1.8-2 ms GPU at 1080x1920); strands 5.5. **~3 ms is not reached** under this load: two Render TOP CPU floors (dots + lines) and Bloom; light-trail presets ship with Bloom 0 (Halo 1.5 makes the glow) and Lineevery 2 x 24 samples |
Captures: `output/laneG_lighttrails_final_*_blk.jpg`, `laneG_lightvortex_final_*`, `laneG_vortex3_*`, `laneG_strands2_*`
(premultiplied out1 flattened over black). Live fixes: pcam pose reads absTime only while Orbit != 0 (a static camera
made PX_lines `rows` cook every frame, 1.9-2.1 ms CPU, LEARNINGS T-185); engine par list cached and the Lines page left
out of the per-frame read (engine 0.9 -> 0.7 ms).

### Lane G item: confetti (FX7c card 11)
| Piece | What |
|---|---|
| Look page `Shape` | `dot` (the soft disc, default), `paper` (a quad Paperaspect high, turning about its own random axis at Spinrate x (0.5..1.5) rev/s (Rodrigues in the vertex shader), two-sided shading Ambient + (1 - Ambient) x abs(n . Lightdir): faces flip bright / dark, hard-edged rectangle in the pixel shader), `streamer` (a ribbon Streamerlen x Size long along the view-space velocity whose width and brightness twist with abs(cos(spin))) |
| Forces `Flutter`, `Flutterhz` | sideways sine flutter per particle phase (colour.w): F += Flutter (sin 2pi (hz age + r), 0, cos 2pi (0.7 hz age + 1.3 r)); with Drag + Gravity the pieces fall at terminal speed g / drag |
| Hit / Auto (U7 default) | Hit = the Burst pulse (Burstcount births, always); the kick edge of the Audio CHOP fires Amtburst x Burstcount only while `Autohit` is on. Confetti presets: Audiosrc chop, Chop = `/project1/lab/AC_audio/out_ctl` (kick), Amtburst 1, **Autohit off**: wired to the kick, the operator turns it on. No limiter |
| Presets | 6 confetti (cannon from below, 5000 per Hit), 7 streamers (700 ribbons per Hit), 8 confetti rain (continuous from the top) |
Rows: uP[28] (shape, spin, aspect, ambient), uP[29] (light dir, streamer length), uP[30] (flutter, hz). Offline tests
(49): flutter = the formula and 0 when off, rows, Hit vs Autohit (kick edge with Auto off = 0 births, Hit = Burstcount,
Auto on = Burstcount), confetti vertical speed -> -g / drag (-2.08).
| # | LIVE CHECK (b3) | Expected |
|---|---|---|
| C1 | rebuild, td_errors | clean (state with flutter, pmat shapes) |
| C2 | V1 + V12 parity again; V12 + Flutter 1.5 | P, V < 1e-3 |
| C3 | confetti preset, Burst pulse, then 3 s | info births = Burstcount on that frame only; capture (paper pieces, bright / dark faces) |
| C4 | Manual kick edges with Autohit off -> 0 births; on -> Burstcount each | as offline |
| C5 | cost confetti after a Hit (32k slots, 5000 alive) and streamers | record |
**Confetti verified live (27 Oct, 2025.31550, b3):** rebuild 0 errors (state with flutter + Initspeedvar, pmat shapes).
V12 + Flutter 1.5 + Initspeedvar 0.3: P 5.6e-6, V 6.7e-6, age 2e-6 (173 frames). Confetti: one Hit (Burst) = exactly
5000 alive / head 5000 (Rate 0); Manual kick edge with Autohit off: head unchanged (0 births), Autohit on: +5000.
Cost (120 pulls after a Hit, pane off): confetti 4.0 ms (CPU 3.2: dots render floor + engine), streamers 3.4, confetti
rain 3.9. Captures `output/laneG_confetti2_*_blk.jpg` (paper cloud, faces flip bright / dark), `laneG_streamers_*`.
Added live: `Initspeedvar` (Emit page, init speed x (1 +- var), salt sb + 9) because one speed made the burst a flat
slab (all pieces reached the same height together); confetti 0.45, streamers 0.4.

**Lane G in main (27 Oct 2026, 2025.31550):** BO_particles rebuilt in main by the builder (63 ops + PX_lines, zkit panel
with the 8 presets), then again after the menu fix (T-190): V12 parity P 3.5e-6, V 6.2e-6 (175 frames); presets
vortex / default / confetti / lighttrails 165-166 / 165-166 pars equal (0 mismatches); lighttrails trails head err 0.0,
24 576 segments; td_errors 0; left at preset default, parked, saved `JazibTD_home.670.toe`. Library
`library/BO_particles/` 0.2.0.
