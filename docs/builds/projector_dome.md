# projector_dome: LK_projection_room upgrade (projector planner + fulldome mode), 26 Oct 2026, TD 2025.31550

COMP: `/project1/lab/LK_projection_room` (upgraded in place; in/out architecture, Room page and stage plan kept).
Builder: `builders/projector_dome.py` (`build(parent_path)`, idempotent, T-70 safe), logic `builders/projector_dome_logic.py`
(copied into `pd_logic`), tests `test/test_projector_dome.py` (23, offline:
`python3 -I -m unittest discover -s test -p 'test_projector_dome.py'`). Backup of the COMP before the upgrade:
`output/backups/LK_projection_room_before_projector_dome_2026-10-26.tox`.
Specs: `docs/research/AT_projector_coverage.md` (sections 3, 6) and `AW_fulldome_simulator.md` (sections 5, 7).
Clean-room: par vocabulary from asterix "Projector Coverage Tool" (paid, never obtained); dome preview idea from
Theinfranet "Fulldome Simulator" (no licence, never loaded). Turbo colormap polynomial: Google / Ruofei Du, Apache-2.0.

```python
ns = dict(globals()); exec(open('<repo>/builders/projector_dome.py').read(), ns); ns['build']('/project1/lab')
```

## Pages
| Page | Pars |
|---|---|
| Room (kept) | Throw (now "Cone angle", used when Lens input = angle), Brightness, Ambient, Orbit, Height, Shadows, Projx/y/z, Projtilt, Projpan, Camfov, Camdist, Lookheight, Opencontrols |
| Projector | Lensinput (throw ratio / legacy cone angle), Throwratio (1.2564 = the old 43.4 deg), Respreset (WXGA/HD/WUXGA/UHD/DCI 4K/custom, writes Resx/Resy; editing them = custom), Resx, Resy, Lumens, Fnum (info), Shifth/Shiftv (% of image width/height, + = image right/up), Gain, Fitcontent (fit/fill/stretch), Testchart, Mapres, Showfrustum, Unit (m/ft) |
| Projb | Projbon + pose, throw ratio, lens shift, lumens of a 2nd projector (same content / native res) |
| View | Viewmode (lit / coverage / pixel density / brightness / overlap), Maxppi, Maxnits, Heatshadows (occlusion), Shadowres (probe width), Shadowbias, Showhud |
| Camera | Campreset (orbit = the old formula, plan, front, side, audience eye, through projector A/B), Camproj (persp/ortho), Orthowidth, Lookx, Lookz, Eyeheight, Camshiftx/y (winx/winy %) |
| Dome | Domemode (off / preview / domemaster), Inputformat (flat window / domemaster / equirect / the room as fisheye), Domefov, Dometilt, Domeradius, Seatx/z, Domeeye, Domeyaw/pitch, Domecamfov, Domeres, Winaz/el/hw/hh, Template (angle rings, red front spoke) + opacity, Domemask, Scenex/y/z |
| Readouts (read-only) | Throwdist, Imgw/h/diag, Hfov, Vfov, Pxpm, Ppi, Mmpx, Lux, Nits, Fl (image centre), Avgppi, Minppi, Coverage, Bthrowdist, Bppi, Bnits |

Outputs: `room_out` (out 1) = room view with HUD, or the dome preview / domemaster per Domemode; `domemaster_out`
(out 2) = square domemaster. Panel: zkit, 76 knobs (Room, Projector, Projb, View, Camera, Dome), pulse Opencontrols.

## Network (stages)
Controls | 1 Input (content_in -> canvas_a / canvas_b compute: fit to native aspect or test chart, placed in the padded light
map) | 2 Room | 3 Rig maths (pd_logic, rig, proj_uniforms) | 4 Projectors (Light COMPs, lens cameras proj_cam/_b,
frustum lines) | 5 Analysis (probe_a/_b renders with probe_mat, pa_avg/pa_max analyze, pa_c/pb_c centre crops,
probe_vals, readouts, hud_lines, view_mat) | 6 Audience view -> output (viewer, render with overridemat in heat views,
hud_text, hud compute, out_switch, out) | 7 Dome (dome_scene fisheye180, dome_src switch, dome_master compute,
dome_geo sphere + dome_mat, dome_cam, dome_render).

## Probes on 31550 (facts used by the build)
- Light COMP `projmapmode simplehorzfov`: `projangle` = full horizontal FOV across the map width; the map aspect sets
  the height (16:9 map at 40 deg: 2.92 x 1.68 m at 4 m, expected 2.912; 9:16 map: height x 1.776). Light default
  position is tz 10 (not 0).
- Light `projmapmode useview` + `aspectcorrect` = same as above; `projection custommatrix` with a 4x4 Table DAT in
  `customproj` (row- or column-major) was ignored (lit area stayed a fixed +-1 square). The Light COMP has no
  winx/winy. So lens shift = padded map: wider symmetric frustum (2 atan((0.5+|s|)/T)), image off-centre in a black
  canvas (exact for a pinhole).
- Camera COMP `winx/winy`: window shift in fractions of frame width / height (+0.25 moves the scene 0.25 left / down);
  `winsize` scales the window about its centre. Through-projector camera: winx = Shifth/100, winy = Shiftv/100.
- Render TOP: OP-name pars of a Geometry COMP (`material`) resolve beside the COMP (`'dome_mat'`), not `'../dome_mat'`.
- TOP to CHOP with crop `full` on a 1x1 TOP names channels with a suffix (`a_avgppm0`); a Render TOP background is
  premultiplied by bg alpha (bg b = 1e9 with alpha 0 reads 0).
- A Render TOP that is pulled re-renders every frame even for a static scene (fresh geo, constant camera: 48/60 frames
  while its viewer was visible). TOP to CHOPs on the probes, or a Script CHOP reading them every cook, therefore kept
  readouts / HUD / frustum cooking every frame (3.9-6.8 ms). Fix: `probe_vals` reads the 1x1 TOPs only when a key
  (pars, rig, stage SOP cooks) changes; otherwise it returns stored numbers without touching the TOPs, so the chain
  goes idle (0 cooks over 129 frames with the pane elsewhere).
- Fisheye180 Render TOP from a camera at rx 90: front (-Z) at the bottom, +X on the right = our domemaster convention.

## Verified live (31550; numbers read back)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
- Old look kept: projangle 43.401 (was 43.4), viewer camera = the old expressions (tx -4.124, rx -23.40, ry -23.2).
- Throw: projector perpendicular to the wall at 9 m: probe distance 9.000, 268.03 px/m (expected 1.2564*1920/9 =
  268.0 = 6.81 ppi = Resx / W / 39.37, AT check 3). Readouts at the default pose: throw 5.99 m, image 4.77 x 2.68 m,
  10.0 ppi, 460 lux, 147 nits, 42.8 fL.
- Image size on the wall at 6 m (front ortho view, lit bbox): 4.788 x 2.70 m (expected 4.776 x 2.686).
- Lens shift: V -50 % -> image top edge at 2.006 m = the lens axis height 2.0 (AT check 2); H +50 % -> left edge at
  x -0.006 (axis x 0). Through-projector view with shift (25, -40): test chart corners at the frame corners.
- Overlap: B at 0.8 W beside A -> 2-count strip 1.431..2.381 m = 19.9 % of W (AT check 5). Perpendicular wall: pixel
  density colour std 0 across the image (uniform pixels), brightness doubles in the overlap, coverage colours A / B / both.
- Dome: room fisheye front at the bottom (1.67 vs 0 mean), +X right (0.20 vs 0 when the projector pans right);
  flat window corners in the domemaster within 0.0006 of pd_logic.dome_uv; preview looking up: rings centred
  (0.5, 0.51), front spoke at the bottom; looking front: horizon ring on the frame's middle row.
- td_errors clean, td_layout check ok (no intruders / unboxed / box overlaps).

## Perf (force-cooked, ms CPU + GPU)
lit: canvas_a 0.5+0.5, render 0.76+0.51, hud_text 0.33, hud 0.18+0.71; heat view: render 0.46+0.31 plus probes
(probe_a 0.94+0.12, probe_b 0.24) when they re-render; first heat view compiles view_mat once (~200 ms). Dome:
dome_master 0.25+2.1 at 2048 (Domeres), dome_render 0.65+0.47. Idle (nothing changing, pane elsewhere): 0 cooks.
Project fps 60.0-60.2 during the measurements.

## Left / open
- HUD text: see the build report (Text TOP position check pending when the run was interrupted).
- Multi-projector dome (AW 7e), edge-blend output (projectorBlend palette), more than 2 projectors.
- Through-projector view uses the room render's aspect (1920x1080); a 16:10 projector shows a little more height.
