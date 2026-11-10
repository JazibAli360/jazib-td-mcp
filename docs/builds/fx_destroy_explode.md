# fx_destroy_explode: FX_destroy module `explode` (26 Oct 2026, TD 2025.31550; scratch first, then main)

2D / 3D implode-explode of the picture in tiles (FX1 DG-19, FX4 D6, FX0 backlog #46). A module of the `FX_destroy`
rack (`builders/fx_destroy.py`, lean slot rack: module COMP + Cross + Switch, zkit panel + presets, Panic); the rack
finds it by name, nothing in the rack changed.

Files: `builders/fx_destroy_explode.py` (PAGES, PRESETS, 3 shaders, `build(m, H)`), `builders/fx_destroy_explode_logic.py`
(float64 reference of the tile motion + one-tile ray cast), `test/test_fx_destroy_explode.py` (8 offline tests incl.
glslc compile): `python3 -I -m unittest discover -s test -p 'test_fx_destroy_explode.py'`.

```python
ns = dict(globals()); exec(open('<repo>/builders/fx_destroy.py').read(), ns)
ns['add']('/project1/lab/FX_destroy', 'explode')        # explode1, wired last, zkit panel + 5 presets
```

## How it works
| Op | What |
|---|---|
| `hit` | compute 2x1 rgba32float in place: latches hit time + blast centre px (Effector Null tx/ty + 0.5, else Point u/v) when Hittime / Auto moves past the last seen time; Reset clears; a fresh texture never replays an old hit; `Ignorehits` drops hits while tiles still fly |
| `tiles` | compute 64 x 73 (one texel per tile, up to 4608), 2 rgba32float buffers, no state: b0 = 3D centre px + alpha (-1 = at rest), b1 = rotation quaternion x scale; row 72 = global "anything moving" flag. Motion is a closed-form function of the time since the hit (or Progress x Duration when Drive = manual), so a bypassed / parked slot never goes stale |
| `tiles_b1` | Render Select of buffer 1 |
| `fx` | compute 16x16: each workgroup lists in shared memory the moving tiles whose projected bound reaches it (max 128), then every pixel casts a ray from the camera (distance Focal x height) through them; the nearest hit wins (true depth sort, tilted tiles intersect correctly); own tile at rest = texelFetch (exact) |

Motion per tile (hashed per tile and Seed): release delayed by `Stagger` x distance (shock front). **explode**:
velocity Force x falloff(distance) along the radial mixed with a random direction (Scatter), rotated by Swirl;
drag-integrated (1 - e^-kt)/k, gravity, z kick (Depth, both sides of the picture plane), Spin (z), Tilt (random x/y
axes = 3D). **implode**: pulled into the centre with Swirl as a vortex, shrinking (Shrink) and sinking back.
**assemble**: the explode run backwards from Duration to rest (fly-in). `Hold` + `Return` (smoothstep back to rest; 0 =
stay), `Fade`. Amount scales all motion (0 = exact passthrough). Look: Gap (grows from 0 as a tile leaves), edge glow
(Edgewidth / Edgeglow / Edgecolor), tilt shading, back faces x Backside, holes = Back (dimmed picture or alpha).
Triggers: Trigger pulse, Beat CHOP rising edge (`beat_exec`), Auto s. Presets: 1 pop on beat (Auto 0.5, Return 0.3;
set Auto 0 and bind Beatchop for the show), 2 debris cloud (44 cells, gravity, tilt, fade), 3 implode pull (swirl),
4 3D tilt blast (10 cells, edge glow), 5 assemble (brick rows).

## Verified live (26 Oct, 31550)
Scratch TD first (lane-owned `/project1/xpl_lane/FX_destroy`, removed after), then main `/project1/lab/FX_destroy/explode1`
(chain after crack1; checks compare explode1/in1 vs explode1/out1, clip paused, reads in separate execs).
- **Exact passthrough** (numpy max abs diff): no hit 0 (scratch + main); Amount 0 while flying 0; Drive manual Progress
  0 -> 0; after Reset 0; after Return reassembly (scratch) 0; assemble finished (scratch, 5.7 s) 0.
- **Tile state = reference** (`fx_destroy_explode_logic.tile`): main, preset 4, Point (0.3, 0.7): 180/180 moving, 0
  rest/moving mismatches, max position error 1.4e-4 px, quaternion 3.9e-7; manual drive with Effector
  `/project1/lab/PX_pointfx/effectors/E2` (tx -0.8, ty 0.3 -> centre (-324, 1536) px): 180/180, 9.8e-5 px. Scratch
  defaults 0.45 s after a hit: 1032 moving, 0 mismatches, 0.024 px (float32 time).
- **Pixels = CPU ray cast** (nearest tile along the ray, bilinear sample, shade, back face, edge glow): 25 tile-centre
  pixels of preset 4 mid-flight, max error 0.0019 (< 1/255).
- **Hit sources**: Trigger latched the Point centre; a 2 Hz square LFO as Beat CHOP latched hits at the beat edges with
  the Effector centre (temp op removed after); Reset cleared to -1.
- **Cost** (out1 pulled per frame, sum cpu+gpu of hit / tiles / tiles_b1 / fx, 110 frames, median [max]): scratch preset 4
  (10 cells, 180 tiles) 1.01 [3.8] ms; scratch debris (44 cells, ~3800 tiles flying) 1.76 [5.4] ms (fx 0.96); main debris
  1.13 [4.7] ms (fx 0.86). Idle (no hit) only the 1-texel global flag is read: fx copies the input. td_watch on main
  with all 5 FX_destroy modules cooking: 60.0 fps (absTime), but only 45 cooks/s for the rack ops (crack1 fx is the
  largest at ~3 ms/cook) - not a fair project fps for this module alone.
- `td_errors` clean, checkpoint `output/checkpoints/FX_destroy/FX_destroy_20261026-202517.tox`, project saved
  (JazibTD_home.300.toe), COMP parked. explode1 left on its slot (enabled 1), preset 1 values with Auto 0, Reset (intact
  = passthrough).
- Captures: `output/project1_xpl_lane_FX_destroy_out1_2026-10-26T15-21-21-346Z.png` (3D tilt blast, scratch),
  `output/project1_xpl_lane_FX_destroy_out1_2026-10-26T15-21-55-832Z.png` (implode, scratch),
  `output/project1_lab_FX_destroy_explode1_out1_2026-10-26T15-24-56-548Z.png` (debris, main). cap.sh grabbed the scratch
  TD window again (T-121 (6)): use td_screenshot of out1 while a scratch TD is open.

## Not done / open
- A workgroup lists at most 128 moving tiles; when many small tiles converge (implode at 40+ cells) some can drop
  out near the centre (they are small and shrinking there).
- A new hit restarts the motion from the intact picture (tiles snap home) unless `Ignorehits` is on.
- Hit times are float32 absTime: about 1 ms resolution at 3 h uptime, 8 ms after ~28 h.
- Tile grid is capped at 4608 tiles (Cells reduced automatically for small Aspect); no Voronoi / triangle tiles (shatter
  covers Voronoi), no 3D-mesh explode (DG-26 `GM_destroy`), no smoke / sparks layer (D6 macro: fluid2d, particles).
