# fluid2d: BN_fluid2d 2D fluid COMP (live-verified v1 in main, 26 Oct 2026, TD 2025.31550, T-91)

`/project1/lab/BN_fluid2d`. A self-contained stable-fluids COMP: dye + velocity, wall / wrap / open edges, obstacle
mask, external force, 8 emitters driven by manual / BPM / audio / in4 points. Every multi-step pass is a **compute**
GLSL TOP (T-46/T-47); no pixel-mode chain anywhere. Spec: `docs/research/BN_fluid_cloth_sims.md` section 5
(clean-room). **No limits** (user rule): open ranges, no luminance / flash guard.

Everything below marked **LIVE CHECK** is a TD fact this offline prep could not confirm; the live lane confirms it and
writes the answer (and any bug) to `LEARNINGS.md` at once.

## Files
| File | What |
|---|---|
| `builders/fluid2d.py` | builder, `build(parent_path='/project1/lab', panel=True, press_mode='npasses')`, idempotent, T-70 safe |
| `builders/fluid2d_logic.py` | pure logic (engine: dt, BPM clock, kick, bursts, emitter rows; par table; pass table) + numpy reference of every shader (copied into the COMP's `fluid2d_logic` Text DAT) |
| `builders/glsl/fluid2d_common.glsl` + `fluid2d_{pre,vort,div,press,grad,advvel,advdye,look,stat}.glsl` | the 9 compute passes; the builder writes `common + pass` into `fx_<pass>_compute` |
| `test/test_fluid2d.py` | 45 offline tests: `python3 -I -m unittest discover -s test -p 'test_fluid2d.py'` (~5 s) |

Offline tests cover: splat integral = pi r^2, zero in -> exactly zero out (200 steps, every edge mode, with a mask),
projection convergence (monotone in K, periodic and walled with an obstacle, 1e-3 of the start), weighted Jacobi on a
manufactured Poisson problem (< 5 % vs analytic, residual monotone), exact one-cell advection, exp dissipation,
no dye / flow in solids, mass drift bounds, edge rules, BPM ticks (no drift over 1 h), kick detector (4 loud of 8
bursts), emitters / patterns / test modes / Pause-Step-Stopat, look modes, shader contract (constants, uniforms ==
pass table, <= 3 inputs, compute only, ASCII), and a **builder dry run against a fake TD** (wiring, feedback loop
ends, uniforms, idempotent rebuild, Iterations 20 -> 12 removes 8 nodes via safe_destroy, npasses mode).

## Maths (what the shaders and the numpy reference share)
- MAC grid in one rgba32float texture at sim res: texel (i,j) `.x` = x-face velocity at (i+1, j+0.5), `.y` = y-face
  at (i+0.5, j+1), in sim cells / s. `.b` carries the solid flag through the chain, `.a` the curl (fx_pre only).
- div = ux(i) - ux(i-1) + uy(j) - uy(j-1); gradient ux -= p(i+1) - p(i): exactly consistent with the 5-point Jacobi, so
  the projected field converges to divergence-free (the collocated centred version of Harris/Dobryakov does not).
- Pressure: **weighted** Jacobi `p' = (1-w) pc + w (sum pn - div) / 4`, `Relax` w = 0.8 (plain Jacobi, w = 1, never
  damps the checkerboard mode on a periodic grid), Neumann at solids (pn = pc), warm start `Warmstart` * last p.
- Semi-Lagrangian advection, manual bilinear, each face component from its own face position; dye at dye res
  backtraced with the sim-res velocity. Vorticity confinement `Curl * w * (N.y, -N.x)`, N = normalised grad |w|.
- Emitters: 3 texels each in the `uEmit` texture buffer (x y vx vy)(radius dye force active)(r g b 0); impulse per
  frame `v * force * Simh * exp(-|dp|^2 / r^2)` (dp in screen heights, aspect-corrected), dye `col * dye * g` (add or
  over). in3 force = acceleration (x Forcegain x Simh x dt). in1 source = `rgb * a * Srcgain * dt`.
- Edge: wall = outside solid (velocity 0, dye clamp), wrap = periodic, open = outside fluid at p = 0 (approximate).
- Pause / Stopat / Testmode fixed: every pass copies its state (run = 0), so the state is frozen bit-exactly.

## Network (stages, L-to-R; titled boxes via layout_stages)
Controls (zkit `controls` + `controls_window`, `fluid_pulses`, `fluid2d_logic`) | 1 Inputs (`in1..in3` -> `*_sel`
switch with a blank when unwired -> `src_prep` dye res 16F, `mask_prep` sim res 8-bit, `force_prep` sim res 32F) |
2 Control sources (`in4` points, `in5` audio -> `aud_low` Audio Filter -> `engine` Script CHOP -> `emit` 24x4, and `uni` 3x4: uDye / uForce / uStep packed as `uniform vec4 uV[3]` for every pass that reads the engine, perf 28 Oct, T-214 / T-229) |
Feedback (`blank_sim`, `blank_dye`, `vel_fb` <- fx_advvel, `press_fb` <- last press, `dye_fb` <- fx_advdye) |
3 Forces (`fx_pre`, `fx_vort`) | 4 Project (`fx_div`, `fx_press_01..K` sharing `fx_press_compute`, `fx_grad`) |
5 Advect (`fx_advvel`, `fx_advdye`) | 6 Look + out (`fx_look` -> `out1`; `out2` = fx_grad raw velocity) |
7 Stats (`fx_stat` -> `an_max` / `an_avg` / `an_dye` Analyze -> `tc_*` TOP to CHOP -> `stats` -> `out3`).
GLSL TOPs per frame: K + 8 (28 at K = 20); only fx_advdye and fx_look run at dye res (1080x1920).
out3 channels: maxvel meanvel (cells/s, |cell velocity|), divmax (|div| of the projected field while running),
dyesum (sum of r+g+b over the dye), cookms (sum of child cpu+gpu cook times), steps, beat, audiolevel.

## Parameters
| Page | Pars |
|---|---|
| Sim | Simh (342; width follows Resw/Resh), Resw/Resh (1080x1920), Iterations (8, **rebuild to apply**), Relax (0.8), Dtmode auto (Timescale / cookRate) / fixed (Dt), Dt, Timescale, Veldiss (0.2 /s), Dyediss (1.0 /s), Curl (30), Edge wall/wrap/open, Warmstart (0.8) |
| Input | Srcgain, Maskthresh (R > it = solid), Forcegain, Emitradius, Emitforce, Emitcolor |
| Audio | Audiomode off / levelstir / kickburst, Audiogain (4), Lowhz (150), Burstthresh (0.3), Burstrefractory (0.15 s), Bpmmode off / internal / external (Beatchop: `beat` channel or chan 0, rising edge), Bpm, Bpmdiv (1/4 beat .. 2 bars), Bpmpattern ring / sweep / random / points (in4), Burst (pulse), Burstforce, Burstring, Burstradius |
| Look | Colormode dye rgb / palette by density / palette by speed (Speedref), Exposure, Gamma, Dyeblend add / over, Alpha opaque over Bg / density, Premult (on: Arena-ready premultiplied), Bg, Pal1..Pal5 |
| Control | Reset, Pause, Step, Stopat (auto-pause at step N, 0 = off), Seed, Testmode off / zero / fixed |
Not in v1 (left for v2, spec 5.9): Kind ripple / reaction-diffusion, Velview (out2 is raw), temperature / buoyancy,
panel-mouse emitter (use in4: any tracker / Mouse In CHOP mapped to x y vx vy), Srcmode velocity-from-luma.

## Build (live lane, ~15 min; nothing else is touched)
Before: `td_status`; check `logs/exec.log` for which COMPs other lanes touch (never park them); the builder only
un-parks its own COMP. Do not move the network pane in loops; viewers stay on.

1. **Build (2 min).** One `td_exec`:
   ```python
   ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fluid2d.py').read(), ns)
   r = ns['build']('/project1/lab'); r
   ```
   Expect `press: 'chain x20'`, `ops` = 71 built by us + the controls panel/window + whatever DATs TD docks to each of the 28 GLSL TOPs, `layout` ok. `notes` lists every par the builder could not set
   (LIVE CHECK 3-5 below): record them, fix the par name in the builder, rebuild.
2. **Errors (1 min).** `td_errors` on `/project1/lab/BN_fluid2d` with frames >= 2: expect none. A GLSL compile error
   names the op (`fx_<pass>` / `fx_press_NN`); the info DAT next to it holds the line.
3. **Look (1 min).** Pulse `Burst` (Bpmpattern ring): out1 shows 8 coloured splats flying outward and curling.
   `td_screenshot` out1. Then Bpmmode internal: a ring every beat.
4. **P3 zero-force stillness (2 min).** Pause on, Testmode zero, pulse Reset, wait 2 frames, Pause off, wait >= 600
   frames, then read out3 (a separate td_exec):
   `{n: op('/project1/lab/BN_fluid2d/out3')[n].eval() for n in ('maxvel','divmax','dyesum','steps')}`.
   **Expected: maxvel == 0.0, divmax == 0.0, dyesum == 0.0 exactly**, steps >= 600. Anything else = the T-46 hazard
   in our loop (stop and record it).
5. **P4 parity with the numpy reference (4 min).** Set Simh 64, Resw 128, Resh 128, Dtmode fixed, Dt 1/60 (0.0166667
   is fine), Edge wall, Curl 0, Pause on, Testmode fixed, Seed 1, Stopat 60; wait 2 frames; pulse Reset; wait 2
   frames; Pause off; wait ~1.5 s (steps reaches 60 and freezes). Then, in a **separate** td_exec (T-74: never in the
   exec that changed resolutions):
   ```python
   import numpy as np
   c = op('/project1/lab/BN_fluid2d')
   np.save('/private/tmp/claude-501/<scratch>/p4_vel.npy', c.op('out2').numpyArray(delayed=True))
   np.save('/private/tmp/claude-501/<scratch>/p4_dye.npy', c.op('fx_advdye').numpyArray(delayed=True))
   [c.op('out3')[n].eval() for n in ('maxvel', 'meanvel', 'dyesum', 'steps')]
   ```
   Compare offline (shell, not TD):
   ```bash
   cd jazib-td-mcp && python3 -I -c "
   import sys, numpy as np; sys.path.insert(0, 'builders'); import fluid2d_logic as L
   r = L.run_fixed(60, 64, 128, 128, 1, {'curl': 0.0}); v = np.load('<scratch>/p4_vel.npy'); d = np.load('<scratch>/p4_dye.npy')
   print(L.rel_l2(v[..., 0], r['ux']), L.rel_l2(v[..., 1], r['uy']), L.rel_l2(d[..., :3], r['dye']))"
   ```
   **Expected (Curl 0): ux, uy rel L2 < 1e-4; dye < 2e-3** (float32 / float16 rounding measured offline: 6e-8 and
   4.7e-4). out3 while frozen (stats of the frozen velocity): **maxvel 12.452, meanvel 1.238, dyesum 422.03** (+-0.5 %),
   steps 60. Then Curl 30 (same steps): reference maxvel 46.03, meanvel 5.011, dyesum 413.92; rel L2 < 3e-2
   (vorticity confinement amplifies rounding: an f32 Dt alone moves the reference 2.2e-3). Rows are bottom-up
   (`numpyArray` row 0 = bottom, T-58) like the reference. Run P4 twice: the two downloads must be bit-identical.
   A wrong-frame / stale-input problem shows here as rel L2 ~ 1 (K = 1 gives 1.45).
6. **P2 npasses probe (3 min, optional).** `ns['build']('/project1/lab', press_mode='npasses')`, td_errors, repeat P4.
   LIVE CHECK: (a) does `uTDPass` compile in compute mode (if not: compile error in fx_press -> stay on chain);
   (b) does pass n+1 read pass n's output as input 0? Same P4 numbers as the chain = yes (keep npasses: 19 fewer
   ops, fewer CPU cook overheads); numbers like K = 1 (reference Curl 30, K = 1: meanvel 2.977, dyesum 860.2) = no.
   Record the answer in LEARNINGS (open question 1 of the research doc). Rebuild with the winner.
7. **P5 incompressibility (1 min).** Defaults (Simh 456, 1080x1920, Curl 30, Testmode off, Pause off, Stopat 0),
   Bpmmode internal 120: while running, divmax / maxvel < 0.05 between bursts (offline: 0.27 / 54.8 = 0.5 % at K = 20,
   64^2, 60 steps; higher on the frames a burst lands). Iterations 40 + rebuild halves divmax (offline 0.27 -> 0.11).
8. **P6 mass (1 min).** P4 setup with Dyediss 0, Curl 30: reference dyesum 911.35 at step 60. Bilinear
   semi-Lagrangian is not conservative: offline drift -3.8 % (wall) / +6.1 % (wrap) over 100 steps on a blob, -9 %
   with an obstacle (backtraces into solids return 0). Compare with the reference, not with a 2 % absolute.
9. **P8 BPM / audio / manual (2 min).** Engine channel `bursts` counts bursts (`op('.../engine')['bursts']`): Bpmmode
   internal 120, Bpmdiv 1 beat: +120 (+-1) over 60 s. Burst pulse: +1. Kick: in5 = Audio Oscillator CHOP (60 Hz sine,
   amp 0.8) gated by a 2 Hz square (LFO at audio rate, Math CHOP multiply), Audiomode kickburst, Audiogain 1: +120
   (+-1) in 60 s. Nothing routed to an Audio Device Out (speakers stay the Mac's, never mic -> speaker).
10. **P9 webcam (optional).** in1 = Movie File In of `media/webcam/webcam_ref_5s.mp4`: out1 shows the clip's colours
    flowing; dyesum grows while Srcgain > 0.
11. **P10 teardown.** Pulse Opencontrols (window open), rebuild twice: no crash, panel reopens (T-70).
12. **Perf + fps.** Other lab COMPs parked (never one a live lane is using), pane on BN_fluid2d: `td_perf` on the COMP
    and the real frame rate (T-73: wall clock between frame starts, not absTime) with controls_window OPEN (T-72).
    **Target: project 60 fps; COMP <= 3 ms cook (CLAUDE.md), spec ceiling 6 ms.** Expect CPU to dominate (28 GLSL TOP
    cooks + 3 Script CHOPs + Analyze). Fallback ladder if over budget: npasses (if P2 = yes) -> Iterations 12 ->
    Resw/Resh 720x1280 -> Simh 342 -> Iterations 6 (warm start carries it). Report cook ms + fps. Then save the COMP
    (`td_tox_save` to `output/lab/BN_fluid2d_v1.tox`), park it (allowCooking off) when done.

## LIVE CHECK list (unconfirmed TD facts; answer each in LEARNINGS)
1. Feedback TOP reset par is `resetpulse` (fluid_pulses checks it exists; else Reset only resets the engine): after
   Reset, dyesum == 0 on the next frames.
2. `uTDPass` in a compute GLSL TOP and npasses chaining in compute mode (step 6).
3. Analyze TOP `op` = `maximum` / `average` and `analyzechannel` = `independent` (as in projector_dome; misses show in
   `notes`); TOP to CHOP channel order r g b a on a 1x1 and `downloadtype` `nextframe`.
4. Audio Filter CHOP: `filter` menu has a low-pass entry; cutoff par is `cutofffrequency` (else `cutoff`).
5. Array uniform `texturebuffer` from the 24-sample `emit` CHOP: sample k -> texel k, channels x y z w -> .xyzw
   (face_track uses the same pattern); `textureSize(uEmit)` = 24.
6. `OP.docked` exists (used to put the GLSL TOPs' docked DATs into their stage boxes).
7. A Script CHOP's auto callbacks DAT is named `<op>_callbacks` (the builder renames / creates it otherwise).
8. In CHOP of a time-sliced audio CHOP: `vals` = this frame's slice (the RMS uses it).
9. `cpuCookTime` / `gpuCookTime` are ms (cookms in out3).
10. rgba32float Feedback TOP keeps 32F exactly (P4) and a format / resolution change re-inits the loop cleanly.
11. Defaults look right on the LED canvas: Curl 30, Burstforce 1, Burstradius 0.04, Dyediss 1 (tune by eye with the
    user; no limits).
12. The WIRED expression (`parent().inputConnectors ... inOP.name == 'in1'`) switches to the In TOP when a wire is
    connected into the COMP (strobe probed it on a scratch COMP only).

## Live results (26 Oct, 31550; details T-91)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
Defaults changed after the live perf run: **npasses, Simh 342, Iterations 8** (were chain, 456, 20). P4 needs
Iterations 20 + rebuild (the reference uses 20). Quality knobs: Resw/Resh (dye + output), Simh, Iterations.
| Check | Result |
|---|---|
| Build / errors | npasses x8, 90 ops incl. zkit panel (52 knobs), notes [], td_errors none |
| Look | Burst ring: 8 coloured splats curl outward; BPM internal: a ring per beat |
| P3 stillness | maxvel = divmax = dyesum = 0.0 exactly over 843 steps (after the Reset fix: hold `reset` 3 frames) |
| P4 Curl 0 | ux / uy rel L2 3.3e-6; out3 12.4516 / 1.2381; dye vs truncating-f16 reference 9e-5 (vs round-nearest 1.7e-2, sum 414.96 vs 422.03: GPU f16 stores truncate); two runs bit-identical |
| P4 Curl 30 | 1.7e-5 at step 12, 7e-2 at 60 (chaotic growth); out3 46.04 / 5.002 vs 46.03 / 5.011 |
| P2 npasses | uTDPass compiles in compute; pass n+1 reads pass n (3.3e-6, = chain): **npasses kept** |
| P5 | divmax / maxvel median 0.046 (K 20) / 0.075 (K 8), p90 0.065 / 0.11 (burst frames) |
| P10 | 2 rebuilds with controls_window open: no crash, window reopens (builder fix) |
| Perf | pane off, out1 pulled, other lab COMPs parked: 1080x1920 / 456 / chain x20 6.6 ms -> defaults **3.97 ms** median (p90 4.4), real 59.9 fps (wall clock) with the window open, td_watch 60.2. 720x1280 / 342 / x8 = 3.3 ms. Stats chain (out3) +~4 ms, cooks only when out3 is used |
Not run: P6 mass, P8 BPM / audio counts, P9 webcam, LIVE CHECKs 3-5, 8, 12 (no notes from the builder, so the
par names resolved). LIVE CHECK 1: `resetpulse` exists but does not clear the loop (T-91). 2: yes. 9: cookms sums
the last cook of every child TOP/CHOP, so stale ops (inputs) inflate it; use the per-frame sampler (T-91).

## Not done / open
- 3 ms aim: 3.97 ms at 1080x1920 output; 720x1280 meets 3.3 ms but breaks the 1080x1920 rule (an upscaled out1
  would). P6, P8, P9 not run live yet.
- v2 items: ripple / RD kinds, temperature / buoyancy, MacCormack, Velview, panel-mouse emitter, Srcmode.

## Perf pass (26 Oct, 31550, perf lane; T-100)
`Quality` (Sim page): high = dye at Resw x Resh, **balanced (default) = dye 3/4**, fast = dye 1/2; fx_look always
renders Resw x Resh and samples the dye bilinearly (textureLod), so out1 keeps its size. `Idlesleep` (default on):
`out_sel` shows `sleep_bg` (Bg opaque, or transparent black for density alpha) once nothing has injected for
`sleep_after(Dyediss, Exposure)` s (~9.7 s at Dyediss 1); the sim is then not pulled. Engine channel `awake`.
Measured (pane off, out1 pulled, other lanes cooking, median per frame): high 4.5 ms, balanced 3.9, fast 3.7 (BPM
bursts on), asleep 0.5 ms; project 59.8 fps (td_watch 5 s). Still over 3 ms awake: next = fewer dispatches (fold
fx_div into the first Jacobi pass, fx_vort into fx_pre); each compute TOP costs ~0.2-0.5 ms whatever its size.

## Perf lane 2 (27 Oct, b2, 31550)
- **Blocked pressure solve (new default `press_mode='blocked'`, `builders/glsl/fluid2d_press_blocked.glsl`):** a 16x16
  group loads its tile + an 8-cell halo (32 x 32: pressure, divergence, solid) into shared memory and runs up to 8
  weighted-Jacobi iterations there (shrinking exact region); `npasses = ceil(Iterations / 8)`, `uPress.z` = Iterations.
  Same per-cell maths, edge rules (wall = outside solid, open = 0, wrap = wrapped cells) and Warmstart on the first
  iteration only. `npasses` and `chain` stay available.
- Paired same-frame A/B (copies, T-145/T-150), fx_press: 1.06-1.25 -> 0.32-0.42 ms (0.31-0.35x total, GPU 0.16-0.25x).
  Parity vs npasses after Testmode fixed + Reset: wall / wrap / open, Iterations 8 and 12: max |diff| = 1 ulp of the
  field (rel <= 1.1e-7; FMA contraction differs, ~50 % of cells differ by that ulp).
- Home: main BN_fluid2d rebuilt by builder (`blocked x8`, 0 errors), parked, saved JazibTD_home.720; library 0.2.0.
