# fx_track: FX_track rack + shared tracker + plexus / hud / analytics (lane F, 27 Oct 2026, TD 2025.31550 target)

`/project1/lab/FX_track`. Plan: `docs/builds/BUILD_PLAN_27OCT.md` s2 ("FX_track YES, small": one tracker shared by
plexus, HUD and analytics) and lane F. Specs: FX7b **TC-01** (blob plexus), **TC-02** (tracking HUD), **TC-04**
(surveillance analytics). Technique emulation from the public descriptions (elekktronaut T76, Dean Cheesman blob
tracker 2026, Gaku Lange / Guinutil tracking-VFX trend, uisato A.S.S.); no files of theirs used.

**Status: verified live on build TD b2 (2025.31550)**: tracker + plexus + hud + analytics, see "Verified live".
14 offline tests incl. glslc of every pass.

## Structure (lean)
- **Rack = FX_glitch's** (`builders/fx_glitch.py` exec'd by `builders/fx_track.py`, like FX_stylise): `slots`,
  per slot module -> `_mix` -> `_slot`, Panic, Input auto / live / test clip (`media/webcam/webcam_ref_5s.mp4`).
- **One tracker at rack level** (Track page), the only shared piece (3 modules read it):
  `trk_src` (img_src, or the `Tracktop` TOP: e.g. `CV_person_mask/out2`) -> `det` (Detw x Deth, rgba16f: r key, g luma,
  b motion vs `det_fb`; Key bright / dark / motion / bright x motion / alpha / red, x Keygain) -> Detector:
  - **cells** (default, GPU): `cells` = one thread per grid cell (Cellsx x Cellsy) scanning its det pixels (<= 128 per
    axis): the point = `Cellpick` peak (brightest pixel over Threshold, ties broken by a pixel hash: organic plexus) or
    centroid (key-weighted: a regular grid on flat bright areas), share over (fill), mean key, bounds of those pixels.
    A cell is a point when fill >= Minfill. Deterministic, ids = cell index.
  - **blobs**: `bt` Blob Track TOP (OpenCV SimpleBlobDetector, CPU; Download type nextframe; mono source red = key) ->
    `bt_info` (Info DAT) -> `bt_pack` (Script TOP: (2, Maxblobs, 4) row 0 u v w h, row 1 id age active) -> `bt_sel`.
    Real tracking ids + age. Only cooks while Detector = blobs. (T-186: create it in its own exec.)
  -> `trk_pts` (compute, 256 wide, ceil(N/64) rows, rgba32f; Feedback `trk_pts_fb`): 4 texels per point
  (`builders/fx_track_lib.py`): T0 world x y 0 valid (on PX_lines' own camera plane: x = (u - 0.5) 2 WX, WX = 5
  tan 22.5 deg; absent points far away at x = 1e4 + 10 i), T1 centre u v strength fill, T2 box u0 v0 u1 v1, T3 id age
  velocity (uv/s); the LAST row holds the 8x8 font (bytes, T-187 (1)) and the clock texel (time of the cook: velocity
is self-clocked, a gap > 0.25 s resets smoothing). Smooth = share of the last centre kept when the same id holds the
slot.
- Modules read `trk_pts` through a Select TOP `pts` (analytics also `det`). N (point count) comes from rack pars only
  (never a TOP size: PX_lines' rows Script CHOP would re-cook every frame, T-169 (5)).

## Modules
| Module | What | Passes | Inputs |
|---|---|---|---|
| plexus (TC-01) | **PX_lines built inside the module from its own builder** (`builders/px_lines.py`, instance not copy) in `connect` mode: Ptstride 4, Ptcount = Cnpoints = N, Cnradius = Radius px x 2 WX / Resw; module pars bound by expressions (links, pieces + jitter = lightning, width, halo, intensity, blend, reveal, flicker, line colour / palette). `fx`: dots at the points (filled / ring / cross, 1 px AA, colour solid / palette by id / strength / speed) + posterise (Levels: the quantised finish) | lines (PX_lines), fx | fx: lines out1, pts, in1 |
| hud (TC-02) | per point: box / corner brackets / circle around its bounds (+ pad, >= min size), crosshair at the centroid, 1-2 label lines in the 8x8 font (`fx_retro_font8x8.py`, read-only): ID 017 / #017 / X0512 Y0960 / speed / age, dark plate, flicker per id, Share of ids shown, colour source | fx | in1, pts |
| analytics (TC-04) | `hs` (Detw x (Deth + 1), self-clocked): heat = decayed key over Threshold; stats row = count, movers (speed > Moverthr px/s), mean strength, per zone share + movers. `fx`: mono CCTV picture, heat overlay / thermal (palette), zone grid + hot zones (share >= Zonethr) + "Z01 045%" labels, redaction (bars / mosaic) on movers or all, CAM nn / REC hh:mm:ss + blinking dot / COUNT / MOVING text. No face identification: movers are redacted, not named | hs, fx | hs: det, pts, hs_fb; fx: in1, pts, hs |

## Outputs: tracked points for effectors + misc arcs (lane F leftovers, 27 Oct 2026; live scratch + main .738)
Rack-level, built by `tracker()` -> `outputs(c)` (idempotent): `trk_chop` (TOP to CHOP of trk_pts, downloadtype
nextframe = one frame late, no GPU stall; crop full; passthrough) -> `out_pts` (Script CHOP, `OUT_PTS_CB`): samples =
the VALID points in index order, channels `tx ty tz` (T0: world on PX_lines' plane = TD's default camera view at z 0,
x +-2.07, y +-3.68) `u v` (centre uv, v up) `id strength`; over **Outpts** (Track page, default 64, <= 4096) the
strongest Outpts are kept, still in index order (ids stay put, the effectors' per-point velocity holds). No points =
NO channels (a CHOP keeps >= 1 sample: zeros would be a point at the origin, T-200). `out_uv` = Select CHOP of `u v`
(arcs reads tx/ty before u/v). Cooks only while pulled; FX_track must be cooking (un-parked) for live points.
- **Effector:** a `pts` row with ref `/project1/lab/FX_track/out_pts` (default name `track`, tag `track`): every
  proximity consumer (PX, BO_particles, MX_prox_material, BL_*, BN_*, GEN_clone, FX_destroy eff_mask) with Effon and
  Effselect `all` / `#track` / `track` is pushed by the tracked people / blobs. Move / scale the row's gizmo object
  to fit the points into a scene (points space = the object).
- **Arcs:** FX_glitch misc `Pointchop` = `out_uv`, Pointspace uv; look `ARCS_LOOK` "tracked arcs" (full state =
  misc's `_D` + Type arcs, pairs, Reach 0.22, Arcfalloff 1.2, Maxarcs 24, Rate 16, cyan; misc's 8 zkit preset slots
  are full, so `link_fx` applies it). Feed FX_glitch the same picture as FX_track. In cells mode the closest pairs
  win, so arcs are short sparks over bright areas; for arcs BETWEEN separate people use Detector blobs (13-27 ms CPU,
  T-186) or a small Outpts (8-16) with a larger Reach.
- **One click** (td_exec): `ns = dict(globals()); exec(open('<repo>/builders/fx_track.py').read(), ns);
  ns['link_fx']()` = both (effector row `track` on, misc1 Pointchop + the look). Options: `effector=None` /
  `glitch=None` skip a part, `eff_enabled=False`, `look=False`, `enable_slot=1` turns the misc slot on, `misc='misc2'`.
  Idempotent (an existing row keeps its values; only ref is re-pointed).

Verified live (scratch, 31550, racks from builders): out_pts = the valid points of a trk_pts readback **exactly**
(348 / 348 at Outpts 4096; 64 at 64; max diff 0); effector row packed: count 64, centroid = CHOP mean (2e-8), points
= out_pts (0); arcs CHOP = `arc_list(read_points(out_uv))` (4.6e-5 px, float32); 0 points: out_pts no channels,
effector count 0, arcs none, no errors; 1 point: effector 1 point exact, no arc (no Point / Point 2 fallback while a
Points CHOP is set). Cost (clip playing, 64 points, 24 arcs, median CPU ms): trk_chop 0.49, out_pts 0.57 (p90 1.4),
arcs 0.74 (p90 1.9; was 3.6 before the numpy arc path), misc fx GPU 1.2; eff_rows 0.86 with the 64-point set
(4 rows); real fps 60.0 on scratch (other TDs busy). Capture `output/fx_track/tracked_arcs_misc1.png`.
Main (.738, by builder, quiet minute): `outputs` + Outpts par on FX_track (parity vs trk_pts 0), misc1 `upgrade`
(presets 1-8 replaced, arcs fixes), `link_fx(eff_enabled=False, look=False)`: row `track` in /project1/effectors
**off** (toggle it on), misc1 Pointchop = out_uv (misc1 stays bend, slot off: recall the look with `link_fx()`);
temporary arcs check 24 arcs from out_uv; 0 errors; both racks parked. Library FX_track 0.2.0, FX_glitch 0.3.1.

Candidate culling (T-172 rule: never loop every point per pixel): cells mode looks only at the pixel's cell +- reach
(<= 4 cells each side, `FT_REACH`); blobs mode at all Maxblobs (<= 256). Labels wider than 4 cells at large
Labelscale clip at that reach. Offline test `test_candidates_conservative` (3000 random cases).

Presets (full state, T-124 (1)): plexus 1 web, 2 lightning, 3 dense lace, 4 posterised, 5 cross hairs; hud 1 tracker,
2 target boxes, 3 scan rings, 4 data storm, 5 minimal ids; analytics 1 cctv analytics, 2 thermal, 3 redacted crowd,
4 mosaic movers, 5 data wall.

## Files
`builders/fx_track.py` (rack + tracker), `fx_track_lib.py` (GLSL lib: points fetch, candidates, font, text; numpy
mirrors det_ref / cells_ref / pts_ref / text), `fx_track_plexus.py`, `fx_track_hud.py`, `fx_track_analytics.py`,
`fx_track_logic.py` (per-pixel references plexus_pixel / hud_pixel / hs_step / analytics_pixel), `fx_track_checks.py`
(live checks; generic helpers from `fx_stylise_checks.py`), `test/test_fx_track.py` (18 tests, Outputs incl.:
`python3 -I -m unittest discover -s test -p 'test_fx_track.py'`). Reused read-only: `fx_glitch.py`, `px_lines.py`,
`fx_stylise_pal.py`, `palette_map_logic.py`, `fx_retro_font8x8.py`.

Build (td_exec):
```python
ns = dict(globals()); exec(open('<repo>/builders/fx_track.py').read(), ns)
ns['build']('/project1/lab')                               # rack + tracker + plexus1 (on)
ns['add']('/project1/lab/FX_track', 'hud', enabled=1)       # one module per exec
ns['add']('/project1/lab/FX_track', 'analytics', enabled=0)
```

## LIVE CHECKS (build TD b2; reads >= 3 frames after a change, in their own exec, T-74)
| # | Check | Expected |
|---|---|---|
| K1 | build, td_errors + GLSL warnings (T-177) | clean; det / cells / trk_pts / module fx compile |
| K2 | tracker parity (`tracker_parity`, clip paused) | det <= 2e-3 (16F), cells centroid <= 1e-4, valid set equal, trk_pts = pts_ref <= 1e-4 |
| K3 | Detector blobs | blob count = Blob Track Info DAT rows; trk_pts valid = rows; v orientation matches (u, v up) |
| K4 | plexus segments (`lines_segments`) | valid connect segments = sum over points of min(K, neighbours within R) x Pieces |
| K5 | module parity (`module_parity`, 400 px, 70 % near points) | over-tol (2/255) <= 1 % per module and preset |
| K6 | analytics `hs_parity` | heat <= 1e-4, stats exact (count = valid points) |
| K7 | Amount 0 / slot enabled 0 / mix 0 / Panic | max diff 0 vs img_src |
| K8 | presets 1-5 per module recall full state | mismatch {} |
| K9 | cost (pane off, 120 pulls) | each module <= ~3 ms at defaults incl. tracker; real fps |

## Verified live (27 Oct 2026, TD 2025.31550, build TD b2; other lanes busy on b3 / b4 / b5 / scratch = loaded GPU)
Method: `builders/fx_track_checks.py` (two execs per check: change, then read >= 2 frames later; clip paused with
`freeze`), parity = numpy mirrors fed with the live inputs; cost = `cost_all` (120 forced out1 pulls, every TOP in the
rack incl. PX_lines' inner ops, In / Movie TOPs excluded, pane off the COMP); fps = real frames over wall time.

| # | Result |
|---|---|
| K1 | builds clean (det / cells / trk_pts / plexus fx / hud fx / hs / analytics fx compile); stage box warnings (T-170) cleared with `initializeExtensions()` |
| K2 | tracker (cells, peak): det max 4.9e-4 (16F), cells max 8e-8, valid set equal (330-349 of 576), trk_pts max 2e-7 |
| K3 | blobs: bt_info 66 rows -> trk_pts 32 valid (Maxblobs 32) = mirror (max 1e-7); white circle at det centroid (0.300, 0.200) -> blob (0.298, 0.199): v up; **Blob Track TOP cost 13-27 ms CPU** while the clip plays (T-186): opt-in only |
| K4 | plexus segments: 990 / 990 (cells), 67 / 67 (blobs) = pairs within radius (min(K, neighbours)) x pieces |
| K5 | module parity (400-1500 px, 70 % next to points): plexus, hud, analytics over-tol **0** (max 5e-4..1e-3, 16F), on default + palette presets (plexus 3 / 4, hud 3 / 4, analytics 4) and in blobs mode |
| K6 | analytics hs: heat max 4.5e-7, stats max 2e-7 (count = valid points exactly); movers 58 while the clip plays (pane on the COMP: cooked per frame), 0 when paused |
| K7 | Amount 0 / slot enabled 0 / mix 0 / Panic: max diff **0** for all three modules |
| K8 | presets 1-5 of each module recall full state: mismatch {} (plexus after its panel was rebuilt: a build that failed half way left plexus1 without `controls`) |
| K9 | cost (median, tracker included, 1080x1920): hud **2.0 ms** (fx 0.40 after the tile list; 2.4 before), analytics **3.0 ms** (fx 0.83, hs 0.41), plexus **5.6-6.8 ms** (PX_lines Render TOP **2.0-2.7 ms CPU**, GPU 0.19; fx 0.7, lines comp 0.5, seg 0.4), all three 8.2 ms; tracker alone det 0.25-0.3 + cells 0.25-0.3 + trk_pts 0.12; real fps 60.2-62 on b2 |

Over budget: plexus (the reused PX_lines Render TOP's fixed CPU cost, T-143 / px_lines.md "Perf"; a compute line
drawer would avoid it but the plan says reuse PX_lines) and the Blob Track TOP mode. Captures: `output/fx_track/`
(plexus1_peak, hud1_tracker, plexus4_hud4, analytics1_cctv, analytics1_mosaic, blobs_all3).
Live fixes: COMP source wired by its output connector; `Cellpick` peak; integer digits + rounded read-outs, font in
the points texture, hud tile list (T-187); self-clocked velocity; sparser HUD defaults (Share 0.12: all 340 labels
are unreadable).

## In main (27 Oct 2026, JazibTD_home.654)
Built in main BY BUILDER (T-152): exec 1 the COMP + `bt` alone (T-186), exec 2 `build` (rack + tracker + plexus1 +
panel), exec 3 `add hud` (enabled 1), exec 4 `add analytics` (enabled 0); 1169 ops, td_errors none (stage box
warning T-170 cleared). Re-check in main (clip paused): tracker det 4.9e-4 / cells 8e-8 / trk_pts 5.9e-7 (343 valid =
mirror), plexus segments 1029 / 1029, plexus + hud parity over-tol **0**, Panic diff 0. Cost in main at rest (plexus1
+ hud1 on, pane off): **8.7 ms** median (PX_lines render 3.1 ms CPU, lines comp 1.1, plexus fx 0.7, hud fx 0.4,
tracker 0.7), real fps 62.9 (others parked). Placed in the lab plan's **Camera + tracking** stage (`jz_stages` +
`restage`: ok, no overlaps / intruders). Rests **parked**. Library: `library/FX_track/` (0.1.0).

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (.758).
