# zkit panel perf pass (26 Oct 2026, offline; target TD 2025.31550)

Why: the rollout (`docs/builds/zkit_rollout.md`) measured panels over the < 1 ms target while someone uses them:
AU_db_meter ~3 ms GPU on changing frames (face 1.32 + text 1.44), ZC_control_surface 1-3.6 ms Python per event,
PV_previz_stage 2.5 ms Python per event (70 knobs), TL_timeline 2.9 ms per frame while playing with the window open
(Python 1.4 + face 0.77 + composite 0.69 GPU). Idle panels were already 0 cooks; that stays.

**Status: offline only.** Built and tested without TD (no jazib-td calls; 4 live lanes were using TD). Nothing here
has been run in TD yet. The live numbers at the bottom are **expected**, not measured. They become verified only when
the live lane runs the checks below.

## What changed
| Where | Before | Now |
|---|---|---|
| Python per event (`zkit_rt.Render`) | every event redrew every knob: ~250 instance tuples x 16 `round()`s, all labels re-fitted, all text rows re-bucketed (profile: `round` = 25 % of the time) | **segments**: groups, presets bar, one per knob, properties menu. A knob's segment is rebuilt only when its signature (value, flags, pressed, typing buffer) changes. `Render(only=ids)`: the caller names the knobs whose value changed; hover/press/typing changes come from comparing the UI state with the previous draw. Bar, theme, popup, morph and random still take the full pass, where unchanged knobs only re-check their signature |
| Echo of the kit's own write | each drag move rendered twice (the drag, then `zk_sync` -> `Flush` one frame later) | `Sync` records the par names; `Flush` redraws only those knobs, and a knob already drawn with that value is skipped (0 writes) |
| u/v mouse events | one move = a `u` and a `v` event, both re-rendered | a drag event with no vertical movement returns at once |
| Hit test | linear over every box per mouse move; properties-menu geometry recomputed per call | 64 px hit grid built at `Rebuild` (`L.hit_grid` / `L.hit_fast`, same answer as `L.hit`); menu geometry cached per popup + layout generation |
| Table writes | instances: changed cells only (already); text buckets rewritten whenever any value text changed | instances and text: changed cells only (`L.diff_columns`, `_write_spec`); Text TOP font sizes and preset state are cached instead of read every draw |
| Text GPU | a dragged knob's value text sat in a size bucket with ~20-60 other labels, so that whole Text TOP re-rendered on every change | **hot text slots** `zk_hot0/1` (+ `zk_hs0/1`): the value text of the knob being pressed, wheeled or typed into, or of a par changing from outside (TL playhead), moves to a Text TOP of its own (2 slots, least recently used one reused, slots never reorder). The big buckets stay still while one knob moves |
| Composite | `zk_comp` composited 8 full-size Text TOPs on every text change (TL: 0.69 ms GPU) | gone: the face shader reads each Text TOP itself (inputs 2..9 buckets, 10..11 hot; constant sampler indices only). A `tcol` instance's `u` field names its text input. An older panel's `zk_comp` is removed as a stray on rebuild (safe_destroy, window closed) |
| Face GPU | every pixel looped over **all** instances (4 texel fetches each just to reject) | **tile lists**: `zk_tiles` (Table) -> DAT to CHOP -> CHOP to TOP (r32float) -> face input 1; per 64 px tile, row 0 = count, rows 1.. = instance indices in draw order (`L.tile_lists` / `L.tile_rows`). Each pixel loops over its tile only. The lists use the knob's cell box, so a changing value text does not change them, and the table is rewritten only when the layout changes. `uInfo.w` = tile size (0 = old loop over all) |

Still single-pass (T-46 safe): one pixel-mode GLSL TOP whose inputs are CHOP to TOP / Text TOPs, not a GLSL chain.
A "dirty rectangle" redraw (keep last frame, redraw only changed knobs) was rejected: it needs a feedback loop, which
T-46/T-47 warn against on this build. With tile culling, a full redraw is cheap enough.

## Offline numbers (fake TD, `python3 -I test/test_zkit_perf.py bench [rt]`, native arm64 CPython 3.13, 70 knobs = PV-sized, 666x1240)
| Per event | 643a043 (rollout) | now |
|---|---|---|
| drag move (event + its sync echo) | 3.42 ms | 0.12 ms |
| hover change | 1.69 ms | 0.13 ms |
| par changed from outside, per frame (TL playhead) | 1.69 ms | 0.11 ms |
| `Rebuild` (layout + full draw) | 2.0 ms | 2.45 ms (also builds the hit grid, par map and segments; runs only on structure changes) |
| tables written during a drag | `zk_gpu` + a whole label bucket `zk_tsN` | `zk_gpu` (~1-3 cells) + one hot slot `zk_hs0` |

Face loop per pixel (pixel-weighted mean over the panel): 70 knobs: 236 instances -> 7.1 (max 13 per tile);
32 knobs (AU-like): 125 -> 7.2 (max 15). Tile table: 1.8-3.1 k cells, rewritten only on layout changes.

Pinned by tests (`test/test_zkit_perf.py`, 12; `test/test_zkit.py` Perf class, 6): idle render = 0 writes; a drag
event rebuilds 1 segment, <= 6 `zk_gpu` cells, 0 text-bucket and 0 tile writes, one par write per move; a u-only move
while dragging = 0 writes; a hover change rebuilds <= 2 segments with no text writes; a par moving every frame touches
only its hot slot after the first frame; window closed = 0 writes; the incremental draw equals a from-scratch draw
after 40 random events (drag, wheel, popup, sync) and after presets/morph/theme/collapse/typing; an older panel without
the new ops still works (no tiles, no hot slots); **the same instances and text as the rollout runtime (643a043) for
the same events** (except the tcol `u` field and text moved to hot slots); tile lists are conservative and in draw
order for 3000 random pixels (with the shader's own tile formula); the hit grid matches `hit` at 4000 random points.
The new shader compiles with `glslc` (fragment stage, a stub for TD's `sTD2DInputs[12]` / `uTDOutputInfo`).

## Applying it (live lane, one COMP at a time, T-70)
Panels carry their own copies of `zk_rt`/`zk_logic`/`zk_face_glsl`, so a COMP changes only when its kit is rebuilt:
`ns = dict(globals()); exec(open('<repo>/builders/zkit.py').read(), ns); ns['build_controls'](path, ...)` with the
COMP's own arguments (or its builder's `_zkit_refresh`; TL_timeline: `panel_name='controls/params', winop='controls',
keep=(...)`, as in timeline.py). The builder closes the window, adds `zk_tiles*`, `zk_hot*`, `zk_hs*`, rewires
`zk_face` (12 textures: 3 wired + 9 in its `tops` par, T-84/T-88) and safe_destroys `zk_comp`. **Any COMP whose builder runs `build_controls` from now on gets the
new kit**, so the first live check should be one small COMP (ZK_controls_kit demo), then AU, ZC, PV, TL.
Rollback: `git checkout 643a043 -- builders/zkit.py builders/zkit_rt.py builders/zkit_face.glsl` and rebuild the
panel (the old builder brings `zk_comp` back; the extra ops are left over and harmless; remove them with safe_destroy).

## What to measure live, and the numbers to expect
Do it with the COMP's window open, the network pane on the COMP, the other lab COMPs parked (CLAUDE.md), td_errors
clean first.
1. **Draws right:** capture the window before/after a rebuild (same knobs, labels, colours). Check: no tile seams (a
   knob arc cut at a 64 px line = a cull bug); text in the right colour, including the hot knob's value text while
   dragging; the properties menu covers knob text; day theme; a collapsed group; a string/file pill.
2. **Python per event:** time the kit's own handlers in one td_exec, the way the rollout drove them:
   `rt = op(path + '/controls/zk_rt').module`, `rt.Rebuild()` if `rt.S['lay'] is None`, then
   `rt._press(x, y)`, 20 x (`t = time.perf_counter(); rt._drag(x, y - k * 3); rt.Flush(); dt.append(...)`),
   `rt._release(...)`; `rt.S['stats']['segs']` = segments rebuilt. Expect **<= 0.3 ms per drag step** on PV (70 knobs;
   was 2.5) and ZC (was 1-3.6 ms), <= 0.2 ms on smaller panels; 1 segment per step.
3. **Hover:** drive the panel's own panel values as the rollout did (fires `zk_mouse`), or time
   `rt.S['hover'] = iid; rt.Render(only=())` across 20 knobs: expect <= 0.2 ms per change.
4. **GPU per changing frame** (60-frame drag, `gpuCookTime` of `zk_face`, every `zk_text*`, `zk_hot*`): expect
   `zk_face` **<= 0.3 ms** on AU (was 1.32) and PV; `zk_text*` **0 cooks** during the drag after the first move;
   `zk_hot0` a few hundredths of a ms per cook; no `zk_comp`. AU total on changing frames <= 0.5 ms (was ~3).
5. **TL_timeline playing, window open:** Python per frame <= 0.2 ms (was 1.4), `zk_face` <= 0.3 ms (was 0.77), no
   composite (was 0.69), only `zk_hot*` among the Text TOPs cooks: total **<= 0.6 ms per frame** (was 2.9).
6. **Idle:** 0 cooks over 120 frames, window open (unchanged).
7. **fps:** 60 held with the window open while dragging and while TL plays (measure frame intervals by wall clock,
   T-73).
8. **Rebuild with the window open** (twice): no crash, `zk_comp` gone, `td_layout check` ok (new ops land in the Faces
   / Text stages).
Report cook ms + fps per COMP into `docs/builds/zkit_rollout.md` (or this file) with the build number.

## Risks to watch
- 12 textures on one GLSL TOP: a GLSL TOP has only 3 connectors from Python on 31550 (T-84; c326769 wired 12 and every
  build_controls failed with IndexError). Fixed in `wire_face`: 3 wired + 9 via `tops` (T-88), compiled and drawing live.
- DAT to CHOP channel/row orientation of `zk_tiles` must match `zk_gpu` (row 0 = first channel; the same convention
  the instance texture already uses live).
- Hot slots use the row's own font size; a menu knob whose name shrinks to fit changes `zk_hot` size (one recook).
- Module state still resets when `zk_rt` recompiles; `Render` then rebuilds lazily (unchanged behaviour).

## Live results (TD 2025.31550, 26 Oct, after the T-88 wiring fix)
Window open, 40-frame drag driven through `rt._press/_drag/Flush` from per-frame `run()` calls; other lanes' COMPs
cooking (project ~23 cooks/s from BN_fluid2d, BK_dmx_*, BO_particles' engine, not the panels), so fps is not a panel figure.

| COMP (knobs, panel px) | zk_face GPU per changing frame | hot Text TOPs | zk_text* cooks in drag | Python per drag step |
| --- | --- | --- | --- | --- |
| ZK_controls_kit (14, 666x365) | 0.25 ms (max 0.53) | 0.06 ms | 0 | 0.45 ms (max 1.55) |
| BO_particles (102, 666x1813) | 1.15 ms (max 1.8) | 0.18 ms | 0 | 0.82 ms (max 3.6) |

Demo meets the <= 0.3 ms face target; the 102-knob BO panel does not (face cost scales with panel area; tiles cull per
64 px but the whole 666x1813 face redraws per change). CQ_cuelist (43 knobs) and BP_io_router (87) rebuilt clean, not
timed. Not re-run here: AU, ZC, PV, TL (steps 4-5 above).

### AU_db_meter + PV_previz_stage (zkit_perf lane, 26 Oct, TD 2025.31550)
Both rebuilt in place with `build_controls(path)` (window closed first; `zk_comp` removed, tiles + hot slots added),
td_errors clean, faces captured (`output/project1_lab_AU_db_meter_controls_zk_face_2026-10-26T12-00-23-750Z.png`,
`output/project1_lab_PV_previz_stage_controls_zk_face_2026-10-26T12-00-57-380Z.png`: knobs, labels, groups right,
no tile seams). Window open, 40-frame drag (`rt._press/_drag/Flush`, one step per frame via `run(delayFrames=1)`),
other lanes' COMPs cooking (BN_fluid2d etc.), so fps is a project figure. Dragged par restored after.

| COMP (knobs, panel px) | zk_face GPU per changing frame | hot Text TOP | zk_text* cooks in drag | Python per drag step | fps (wall clock) |
| --- | --- | --- | --- | --- | --- |
| AU_db_meter (32, 666x805), Gain | 0.28 ms (max 0.59; was 1.32) | 0.19 ms | 1 (first move) | 0.53 ms (max 1.78) | 53 |
| PV_previz_stage (70, 796x1206), Curve | 1.43 ms (max 2.30) | 0.03 ms | 1 (first move) | 0.74 ms (max 1.30; was 2.5) | 58 |

AU: face meets <= 0.3 ms; total per changing frame ~0.5 ms GPU + 0.5 ms Python (was ~3 ms GPU). Idle after the
drag: 0 text cooks (1 face + 1 hot cook from the restore write). PV: Python 3.4x faster but over the <= 0.3 ms
target; face 1.43 ms fails the <= 0.3 target - same as BO (face cost scales with panel area: 796x1206 redraws whole
per change). Segments rebuilt per step ~1 (PV 33 over 40 steps). Python per step on both is ~2-3x the offline bench
(Rosetta + live tables). Next for big panels: draw only dirty tiles (scissor the face to the changed knob's tiles)
or a smaller face resolution. Not re-run: ZC, TL (steps 4-5). Both COMPs parked again.

### Packed instance texture (perf lane, 26 Oct, TD 2025.31550; T-100)
`zk_gpu_chop` -> `zk_gpu_sel` (fields k-major) -> `zk_gpu_pack` (Shuffle seqn, N 4) -> `zk_gpu_tex` RGBA32F, one row
of 4n texels: texel k*n+i = fields 4k..4k+3. The face reads 1 texel to reject an instance and 4 to draw it (was 4 and
16). BO_particles (102 knobs, 666x1813): zk_face full redraw **1.53 -> 0.60 ms GPU** median (mean 0.69, max 1.48),
capture identical in layout. Panels pick it up on their next `build_controls` (old panels keep their own shader +
texture pair, so nothing breaks before). Inputs unchanged (3 wired + tops, T-88). Paging/collapsing groups not needed
for now; the panel still redraws whole per change (dirty tiles remain the next step).
