# Camera rig logic: crane, dolly, orbit, path, view store, auto director (27 Oct 2026, TD 2025.31550)

Build plan 27 Oct, lane E item 1 (rank 18, rows K24 + TC-36). Structure decision (BUILD_PLAN s2): **no CAM_rig COMP**:
the rigs are pure Python in `builders/cam_rig_logic.py`, used by PX's Camera page (W3, PX owner) and BL_splat_render's
camera; lift into a COMP only if a third consumer asks. Research: FX7b TC-36 (exsstas Camera Crane: Heading / Pitch /
Length arm that always looks at its base, clean-room; uisato's procedural camera that cuts to new angles and follows a
body / hand).

**Status: 26 offline tests (`python3 -I -m unittest discover -s test -p 'test_cam_rig.py'`, ~0.1 s); LIVE on b2 (31550,
27 Oct): CR1-CR3, CR5 pass, CR4 checked on the logic, CR6 for the PX / BL owners (results at the end).**

**Third consumer (28 Oct): `CS_cam_sequencer`** (`docs/builds/cs_cam_sequencer.md`) lifts this module as is (Text DAT
`cam_rig_logic` inside the COMP) for a standalone camera shot sequencer; PX / BL keep their own copies.

## API (all pure, no td import)
| Piece | Functions | Notes |
|---|---|---|
| Pose | `pose(pos, target, roll, fov)` | roll = degrees about the viewing axis (+ = TD local rz); fov HORIZONTAL (TD `viewanglemethod` horzfov default, same as `px_logic.cam_viewproj`) |
| Matrices | `axes`, `rot3`, `pose_matrix` (= the Camera COMP's worldTransform), `view_matrix`, `proj_matrix`, `viewproj` | camera looks down its -Z; up hint world +Y, straight up / down falls back (no NaN); `viewproj` equals `px_logic.cam_viewproj` for a level camera (tested) |
| TD values | `td_pars(pose, order)` -> tx ty tz rx ry rz fov; `euler_from_matrix` / `matrix_from_euler` | every TD `rord` (xyz xzy yxz yzx zxy zyx: rotate about order[0] first, fixed axes, R = R2 R1 R0); round-trips incl. gimbal lock (tested) |
| Rigs | `orbit` / `orbit_at(t, speed_deg)`, `crane(base, heading, pitch, length)`, `dolly(a, b, u, target or look_dir, ease)`, `Path(points, closed)` + `path_pose(path, u, target / look-ahead, bank)`, `follow(prev, point, offset, lag, dt)` | crane = arm end looking at the base (arcs when heading / pitch are LFO'd); path = Catmull-Rom through the points, arc-length table (even speed, max/min step 1.02 tested) |
| Shake | `shake(pose, t, amp, rot_deg, freq, seed, octaves)` | deterministic value noise; position, aim (target offset at its distance) and roll; 0 / 0 = unchanged |
| Blend | `blend(p0, p1, u, mode cut / ease / arc, ease)` | arc = swing around the target (direction slerp + distance lerp): flies on the circle, keeps framing |
| Eases | `ease(u, linear / smooth / smoother / in / out / sine / expo / back)` | clamped 0..1 |
| View store | `Views`: store / get / remove / names / fly(a, b, u, mode); `to_rows` / `from_rows` (Table DAT `name px py pz tx ty tz roll fov`) | survives in the .toe as a table |
| Director | `shot(rig, hold, trans, tdur, ease, **params)`; `Director(shots, mode list / random, seed, quant, min_hold, max_hold, bpm, views)`; `at(beats, seconds, follow_point)` -> (pose, info); `segment`, `cuts(b0, b1)`, `ensure` | holds in beats; every cut lands on a multiple of `quant` beats (1 beat, 4 bar); `random` never repeats a shot, holds drawn in [min, max], seeded = same show every run; the transition INTO a shot (cut / ease / arc over tdur beats) starts at the cut while the old shot keeps moving; moving rigs run on the beat clock (seconds = beats x 60 / bpm), seconds only feed the follow lag |
| Binding | `bind_exprs(module_expr, clock_expr, order_expr)`, `apply_bind(cam, exprs, ParMode)`, `Memo(fn).cam_par(t, order, name)` | each Camera COMP par gets `<module>.cam_par(<clock>, me.par.rord.eval(), 'tx')`; the clock is read IN the expression (time dependency, T-113); Memo computes the pose once per clock value for all 7 pars |

## How a consumer binds it (example: BL_splat_render external camera, or PX W3)
1. A Text DAT `cam_rig` with this file's text (like `eff_logic`), a Text DAT `cam_show` whose module builds the rig and
   exposes `cam_par`:
   ```python
   L = op('cam_rig').module
   views = L.Views.from_rows([[c.val for c in r] for r in op('cam_views').rows()])
   D = L.Director([L.shot('crane', 8, base=(0, 1, 0), heading_speed=12, pitch=25, length=4),
                   L.shot('view', 4, 'arc', 2, name='close'), L.shot('orbit', 8, 'ease', 1, radius=3)],
                  'random', seed=3, quant=4, min_hold=4, max_hold=12, bpm=128, views=views)
   M = L.Memo(lambda beats: L.shake(D.at(beats)[0], beats * 60 / 128, amp=0.01, rot_deg=0.3))
   cam_par = M.cam_par
   ```
2. `L.apply_bind(op('cam1'), L.bind_exprs("op('cam_show').module", "op('/project1/AC_audio/beat')['beats']"),
   ParMode)` (or clock `absTime.seconds * 128 / 60` without an audio clock).
3. Shader consumers that need view-proj numbers call `viewproj(pose, resx, resy)` in Python (no camera read-back).

## LIVE CHECKS (any free TD; a disposable COMP; nothing parked needs to wake)
| # | Check | Expected |
|---|---|---|
| CR1 | Camera COMP with `apply_bind`, 20 random poses (pos, target, roll) x each `rord` | `cam.worldTransform` = `pose_matrix(pose)` within 1e-5 (if TD's rord means the reverse order, swap the order in `matrix_from_euler` only + LEARNINGS) |
| CR2 | Render TOP through that camera: a small sphere at `target` | sphere at the image centre (+-1 px at 1080 x 1920); fov horizontal: a 1-unit box at distance d spans 1080 / (2 d tan(fov/2)) px wide |
| CR3 | Director on a beat clock (AC_audio or a Beat CHOP at 128 bpm), quant 4 | `info['segment']` changes only on bar starts (log 60 s); `random` never shows the same shot twice; cuts land in the frame the bar starts (no 1-frame lag: the clock is read in the expression) |
| CR4 | Crane with heading_speed 20 + pitch LFO; arc transition between two stored views | smooth arcs, no flips at pitch +-90 (gimbal fallback), no roll pops; capture 3 frames |
| CR5 | Cost | Camera COMP cook with 7 bound pars: Memo -> 1 pose per frame; < 0.05 ms CPU (`td_perf`), project 60 fps |
| CR6 | PX / BL binding | BL_splat_render `Cammode external` + `Camcomp` = the bound camera: sort gate re-sorts on camera moves (`need_sort`), image follows the rig |

## Live results (27 Oct 2026, TD 2025.31550, build TD b2)
| # | Result |
|---|---|
| CR1 | 20 random poses x each of the 6 `rord`: Camera COMP `worldTransform` = `pose_matrix` within 2.4e-7 (TD's rord = rotate about order[0] first, as coded) |
| CR2 | Render TOP 1080 x 1920 through the posed camera (roll 20, fov 50): sphere at the target at (540.0, 960.0) exactly; spheres at target +- 0.5 camera-X land 226.0 px apart (horizontal-fov formula 226.03) |
| CR3 | `apply_bind` with clock `absTime.seconds * 128 / 60`, random director (quant 4, holds 4-8): 6 cuts in 45 s, each in the first frame at / after a multiple of 4 beats (e.g. 1583.964 -> 1584.0), never the same shot twice |
| CR4 | (logic, 60 s at 60 fps with a crane pitch LFO of +-60 deg + arc transitions) max Euler step 2.9 deg / frame inside a segment, no flips; no capture taken |
| CR5 | Memo: exactly 1 pose per frame for the 7 bound pars; Camera COMP cook 0.08 ms CPU |
| CR6 | not run here (BL_splat_render / PX not in b2): for the PX W3 / BL owners |
