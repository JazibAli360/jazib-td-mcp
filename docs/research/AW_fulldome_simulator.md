# AW - Fulldome Simulator TOX (Theinfranet, derivative.ca asset 72740) and a fulldome preview + domemaster output mode for LK_projection_room (26 Oct 2026; TD 2025.31550, macOS, Rosetta, Vulkan/MoltenVK)

Research only. Nothing loaded into TD, no code run. Tags: **[V]** read in the page/repo/expanded file; **[D]** in our ops dump (`ops/*_2025.31550.json`); **[U]** unverified or my own design.
Evidence: `research_src/fulldome_72740/` = `repo/` (shallow clone at commit `8ecd56c`, 5 Sep 2025, with `.git` and the 82 MB `Point Cloud Files/` removed: the repo is 74 MB on GitHub, over the 50 MB rule, so I kept only the .tox, templates, screenshots, 7 example .toe and README), `x_tox/` (the .tox run through `toeexpand`, text only), `x_ex2/` (EXAMPLE 2 expanded), `derivative_download_stub.html.txt` (derivative.ca's file link returned 403; not bypassed, the repo copy is the same 33.9 KB tox).

## 1. What it is [V]
- "TouchDesigner Fulldome Simulator TOX (beta)" v0.2, author **Theinfranet** (theinfra.net, Chile), posted 4 Sep 2025, 2,758 reads, free. Made for the TouchDesigner Meetup STGO (Planetario Huechuraba). Tags fulldome / simulator / planetarium.
- One 34 KB `FulldomeSimulator.tox` + `FulldomeTemplates/` (3 PNG test patterns, 4096x4096, "by Paul Bourke", paulbourke.net/dome/testpattern) + 7 example .toe (2D, 3D fisheye render, point clouds incl. a PLY by Sutilmetal, RayTK fractal, two experimental POP examples).
- **Licence: none** (GitHub `license: null`, page silent). All rights reserved by default: study and port the idea (our rule: licences irrelevant for research, note the source), do not redistribute the file. Test patterns are Paul Bourke's, his terms apply.
- **Build:** saved in **2022.32120 on Windows 10** (`.build`); the embedded Palette `cameraViewport` was saved with 2022.29850 (Camera COMP palette v0.38.0). Page: "2023+ should behave similarly, not fully tested". Mac: not stated. Every op type in it exists in 31550 [D] (carve, torus, sphere, transform, material SOPs; constant, line MAT; render, level, rgbkey, comp, switch, ramp, moviefilein, in/out, null TOPs; annotate, cam, geo COMPs; table/parameter DATs/CHOPs). Nothing here needs a newer build. Not tested on Mac or Rosetta by the author; nothing exotic (no GLSL, no native code), so no reason to fail [U].

## 2. What it simulates [V]
- A **single dome, a single fisheye input**: the input TOP is a **square domemaster** (azimuthal equidistant, 180 degree, "FishEye Equidistant 180"), wrapped onto a hemisphere, then viewed from a free camera **inside** the dome (spectator view). So: dome geometry = unit hemisphere with tilt; viewer = an orbit/zoom Camera COMP (Palette cam, FOV par); input formats = **domemaster only** (no equirect, no cubemap in the component; the README says to feed a square image; 3D content must be rendered with Render TOP `rendermode = fisheye180`, shown in EXAMPLE 2 at 4096x4096).
- **Not modelled:** multi-projector domes (no warp/blend, no projector positions), real dome radius or seat positions in metres, dome that is not a hemisphere (no truncated/horizon-lowered shapes), lighting/brightness, audience eye height presets, projector pixel density. It is a **content previewer**, not a projection simulator. The "3 templates" are just three test PNGs, not three dome layouts (README wording "dome projection layouts" is generous; the switch is `Templatenumber` 1-3 into a `switchTOP`).
- Extras: Sweet Spot overlay = a small red wire grid patch on the dome showing the "focus area" of vision (size/rotation/offset pars); a horizon ring (torus).

## 3. How it is built (from the expanded network) [V]
Layout is in `repo/Screenshots/1.png` (boxes: DefaultView, InputView, FulldomeTemplates, DomeGeometry, DomeConfig, SweetPoint, Camera, Output).

| Stage | Ops | Detail |
|---|---|---|
| Input | `input` (In TOP) -> `over` (Composite TOP, `add`, size = input1, custom res 256, par `Inputresolution` 4096 meant) with `level1` (opacity = `Templateopacity`) of `switch1` (3 `moviefileinTOP`, relative path `FulldomeTemplates/TEMPLATE-n.png`, hence the "folder beside the project" requirement) over a default `ramp` (circular, 4 colours, phase = frame/100) when nothing is plugged | the test pattern is *added* over your content at adjustable opacity |
| Mirror | `flip` (Transform TOP `sx = -1`) -> `null2` | inside view mirrors the image; flipping it keeps text readable from inside |
| Dome | `sphere1` (Sphere SOP, rows 100, cols 100, **`texture = equiazimuth`**, `rx = Dometilt`) -> `carve1` (Carve SOP, first v 0.5 = **keep the upper half**) -> `material2` -> `constant1` (Constant MAT, colour map = `null2`) -> `geo1` | **The whole trick: the Sphere SOP generates azimuthal-equidistant (domemaster) UVs, so no GLSL and no cube map.** An unlit Constant MAT shows the image 1:1 |
| Horizon | `torus1` (NURBS, radx 1, rady 0.01) -> `transform1` -> `geo2` | thin ring at the dome rim |
| Sweet spot | `sphere2` (rows 40, cols 50, equiazimuth, `rx = Dometilt`, `ry = 45-7`) -> `reorientation` -> `tilt` -> `carve2` (domains driven by `Sweetpointw/h/t/size`) -> `material4` -> `line3` (Line MAT, red, width 1.5 near / 1 far) -> `geoSweetPoint` (render flag = `Sweetpoint`) | wire patch over part of the sphere, only a coloured grid |
| View | `cameraViewport` = Derivative's Palette **Camera COMP viewport** (ArcBall + `CameraExt`, key/mouse: LMB orbit, RMB pan, wheel zoom, middle smooth zoom, H reset), `fov` = `Camerafov` (default 45), near 0.4 | `render2` (Render TOP, 1280x720, AA aa2, `camera = cameraViewport`, geometry `geo1,geo2`) -> `rgbkey1` -> `out1` |
| Config | `par1` (Parameter CHOP of the parent) -> `null1` (exported to a table); sphere/transform pars reference `op('null1')['Dometilt']` etc. | one DomeConfig page |

Custom parameters (page DomeConfig, from `.cparm`) [V]: `Templatenumber` (1-3), `Templateopacity` (0-1, default 0.192 stored), `Camerafov` (default 45, up to 100), `Inputresolution` (1280 default, up to 4096), `Outputresolution` (1280 x 720 default, up to 4096 x 4096... stored 1920 x 1080 on the second tuple), `Dometilt` (-30..0 slider, default 0; stored -15), `Sweetpoint` (toggle), `Sweetpointtilt` (SweetSpotRotate, 0-90), `Sweetpointw`/`Sweetpointh` (0-2, stored 1.4/1.5), `Sweetpointt` (-0.1..0.1). Outputs: one TOP (`out1`, the rendered spectator view; the README says export the node **before** the simulator, i.e. your own domemaster, with Movie File Out in image-sequence mode at 30/60 fps).

Performance: nothing special. The only cost is a 100x100 sphere mesh and one Render TOP at 1280x720; the real cost is whatever renders the 4096x4096 domemaster upstream (EXAMPLE 2 uses a 4096 fisheye Render TOP, which is 1 render pass in 31550 [D `rendermode`: render2d/cubemap/cubemapods/fisheye180/dualparaboloid/uvunwrap]). No feedback, no Python in the loop.

## 4. Audit [V]
- Scripts in the tox: only Derivative's Palette Camera COMP internals (`CameraExt`, `ArcBallExt`, `DocsHelper`, parexecs, keyboardin/renderpick callbacks) and the 9 Palette `annotate` COMPs. A grep over the whole expanded tox for `subprocess`, `os.system`, `popen`, `urllib`, `requests`, `socket`, `webbrowser`, `__import__`, `import os`, `sys.path`, `pip`: **no hits in any script**; only `.eval()` parameter-expression calls (normal). No `eval(`/`exec(` string execution. No Execute DAT, no Web/Network/Serial ops, no file write. EXAMPLE 2 expanded: same (no network/subprocess hits).
- Disk: reads only `FulldomeTemplates/*.png` (relative path). One reference to `app.samplesFolder+'/Map/Banana.tif'` is only the default expression of `TEMPLATE_1`'s file par (overridden by the PNG path).
- Risk: low. Not audited: the other 6 example .toe (point cloud, RayTK 9.9 MB, POP experiments; not needed), and the `.ply/.spz` data files (deleted).

## 5. What the maths is (so we can build our own) [V + standard geometry]
Domemaster = azimuthal equidistant fisheye with 180 degree FOV, square image, circle inscribed, **zenith at the centre, horizon at the circle edge**:
- Image coords (u, v) in [-1, 1] (centre 0): `r = sqrt(u²+v²) <= 1`, `phi = atan2(v, u)`, zenith angle `theta = r * (pi/2)` (equidistant: radius linear in angle; this is the `equiazimuth` UV mode).
- Direction on the unit dome: `d = (sin(theta) cos(phi), cos(theta), sin(theta) sin(phi))` (Y up) up to axis convention; inverse (3D direction to domemaster pixel): `theta = acos(d.y)`, `phi = atan2(d.z, d.x)`, `r = theta/(pi/2)`, `u = r cos(phi)`, `v = r sin(phi)`. Pixels with r > 1 are black (outside the circle).
- Tilted dome (projection onto a tilted planetarium): rotate `d` by the tilt about the X axis before the inverse. The simulator does this with `rx` on the sphere SOP.
- Cubemap -> fisheye (what a 6-camera render would use): sample the cube map along `d` for every pixel of the circle (that is exactly what `projectionTOP input=cubemap, output=fisheye, fov=180` does [D]); `fov > 180` gives fisheye beyond the horizon (for domes whose spring line is below the horizon, e.g. 200-220 degrees).
- Equirect -> fisheye: `lon = atan2(d.z, d.x)`, `lat = asin(d.y)`; sample equirect at `((lon/2pi)+0.5, (lat/pi)+0.5)`.

## 6. Verdict
- **Useful as an idea, not as a file to adopt.** Small, clean, no licence, window-dressing (annotate COMPs, Palette camera) around about 12 ops of real logic. The central trick (Sphere SOP with `equiazimuth` UVs, upper half carved, unlit Constant MAT, camera inside) is worth copying in 10 minutes and it exists natively in 31550 (sphereSOP `texture` menu has equiazimuth and equiazimuth360 [D]).
- Its limits for us: single-projector-less content previewer, domemaster only, no real-world scale, fixed spectator camera defaults, hard 3-png template folder, 2022 build, Windows only tested. We do not need to load it. Do not copy the file into the project (no licence); rebuild from the recipe below, credit "idea: Theinfranet Fulldome Simulator, test patterns Paul Bourke" in the COMP's About text.
- Relevance to PF26: the show is an LED wall, not a dome (`projectionTOP` is marked "domes (not PF26)" in `ops/TOP.md`), so this belongs in the **general mapping/projection toolkit** (new-scope work), not the PF26 path.

## 7. Recipe: fulldome preview + domemaster output mode for LK_projection_room (design, not built)
Goal: LK_projection_room gets a mode `Domemode = Off | Preview | Domemaster out` that previews how any content lands on a dome and exports a square domemaster. Everything native, vertical rule applies to PF26 looks only; a domemaster is square (2048, 4096; 4096 for production, 2048 for live preview).

### 7a. Preview (flat or domemaster content -> spectator view of the dome), ~12 ops, no GLSL
1. `domemaster_in` (Select TOP -> the content; if content is not already a domemaster use 7b/7c first).
2. `dome_geo`: `sphereSOP` (`type mesh`, rows/cols 100x100, `texture = equiazimuth`, `rx = Dometilt`) -> `carveSOP` (keep upper half: `firstv on`, `domainv1 0.5`; verify live which v range gives the top half, the tox uses 0.5) -> `geometryCOMP` with `constantMAT` (colour map = flipped content). Pass a texture-capable material; `constantMAT` avoids lighting. Optional `torusSOP` rim and a `lineMAT` sweet-spot patch as in section 3.
3. `flip_x` (Transform TOP `sx -1`) between content and MAT, because the camera looks at the inside of the surface (or set the camera `sx -1`; do not mirror twice).
4. Viewer camera: reuse the LK_projection_room viewer camera (FOV, orbit); add `Eyeheight` and `Viewerseat` (x, z) pars so the camera starts at a seat position inside the dome instead of the centre; dome radius `Domeradius` (m) scales `sphereSOP radx/rady/radz` so seat positions and projector positions are in metres [U]. Near plane 0.05-0.4.
5. `renderTOP` 1280x720 (or the room viewer's resolution), `camera` = viewer cam, `geometry = dome_geo`, `lights` empty, AA aa2.
Pars on the COMP (custom page `Dome`): `Domemode` (menu), `Inputformat` (domemaster / equirect / cubemap / flat), `Domefov` (default 180; 200-220 for lowered domes), `Dometilt` (-30..30), `Domeradius`, `Eyeheight`, `Seatx/Seatz`, `Templateopacity` + `Template` (test pattern menu from `docs/research/refs/`), `Sweetspot*` (optional).

### 7b. Domemaster output from flat 2D content (fisheye warp) - GLSL TOP
When the source is a flat 16:9 or square image or a video that should be "projected" onto the dome (e.g. a window on the dome front):
```glsl
// glsl TOP, 1 input = flat content, output square domemaster (4096 or 2048)
uniform float uTilt;      // radians, dome tilt (rotate about X)
uniform float uFov;       // radians, 3.14159 = 180 degrees
uniform vec2  uWindow;    // horizontal/vertical half angle in radians the flat image covers (e.g. 1.2, 0.7)
uniform vec2  uCentre;    // window centre as (azimuth, elevation) radians
out vec4 fragColor;
void main(){
  vec2 p = vUV.st*2.0-1.0;               // -1..1, zenith at centre
  float r = length(p);
  if(r>1.0){ fragColor=vec4(0,0,0,1); return; }
  float theta = r*(uFov*0.5);            // equidistant
  float phi   = atan(p.y,p.x);
  vec3 d = vec3(sin(theta)*cos(phi), cos(theta), sin(theta)*sin(phi)); // Y up
  float c=cos(uTilt), s=sin(uTilt);
  d = vec3(d.x, c*d.y - s*d.z, s*d.y + c*d.z);                        // tilt about X
  float az  = atan(d.x, d.z) - uCentre.x;                             // look along +Z
  float el  = asin(clamp(d.y,-1.0,1.0)) - uCentre.y;
  vec2 uv = vec2(az/uWindow.x, el/uWindow.y)*0.5+0.5;
  bool inside = all(greaterThanEqual(uv,vec2(0))) && all(lessThanEqual(uv,vec2(1)));
  fragColor = inside ? texture(sTD2DInputs[0], uv) : vec4(0,0,0,1);
}
```
Check on the live build: GLSL TOP built-in `vUV` and `sTD2DInputs` (documented), mac GLSL via Vulkan/MoltenVK uses GLSL 4.60 [U]; keep one texture read, no loops.

### 7c. Domemaster from a 3D scene - two routes
- **Fast: `renderTOP rendermode = fisheye180`** (square 4096x4096, one pass; as EXAMPLE 2) [D]. Limit: 180 degrees only, fixed projection centre = camera, tilt by rotating the camera.
- **Flexible: cubemap -> `projectionTOP`** (`input cubemap`, `output fisheye`, `fov` 180-220, `rx/ry/rz` = tilt/rotation) [D]: `renderTOP rendermode = cubemap` (one TOP, face size 2048, ~6 passes) -> Projection TOP. Use this for fov > 180 and for reuse of the same cubemap for a 360 preview (`output equirectangular`). Cost is 6 renders: fine for previews at 1024-2048 faces, heavy at 4096 on Rosetta/MoltenVK [U]; test with `td_perf`.
- Equirect video -> domemaster: `projectionTOP input equirectangular output fisheye fov 180`; domemaster -> equirect preview: reverse.

### 7d. Output and export
- `domemaster_out` = Null TOP (4096 sq). Live: send via Syphon/NDI at 2048 or 4096 (Arena/dome server). Offline: Movie File Out image sequence (as README) with fixed fps and range limit once; for dome servers a 4096 PNG/JPG sequence or HAP at 4096 (HAP is a plugin gate, see AK).
- Dome mask: an optional `circle` TOP at radius 1 multiplied over the output to hard-cut outside r > 1 (many dome servers want black corners).
- Safe zone/sweet spot: keep the simulator's idea as an overlay (wire grid) but expose it as a TOP mask in the domemaster itself (angle rings at 30, 60, 90 degrees) to compose content.

### 7e. Multi-projector dome (next step, not in the simulator)
Per projector: Light COMP projection map (as in LK_projection_room) rendering the dome mesh from that projector's pose, blend masks from overlap area; the preview in 7a then shows the dome with the *actual* content as seen by the viewer. This reuses AT (coverage view) rather than the Fulldome Simulator.

### 7f. Build plan (when the user says go)
1. Pilot in a scratch .toe: 7a with a Paul Bourke pattern, compare to the simulator's look once by eye (their tox opens only in a copy, user go-ahead needed).
2. Add 7b GLSL TOP, test with a grid image: straight lines must bend, centre stays still.
3. 7c cubemap route; check `td_perf` at 2048/4096 face size.
4. Add custom pars via `td_custom_pars`; document in `docs/FUTURE.md` (below); update `LK_projection_room` README.
No build now (research brief only).

## 8. FUTURE rows to add (not yet written to FUTURE.md; nothing dropped)
- `LK_projection_room` `Domemode` (Off/Preview/Domemaster): sections 7a-7d.
- Multi-projector dome (7e), coverage heatmap (AT).
- Seat/eye position presets and `Domeradius` in metres.

## 9. Open questions for the user
1. Is a dome ever in scope (planetarium client, a PF26 after-show) or is this only for the general toolkit? That decides if we build 7a now.
2. Preferred domemaster size (2048 live, 4096 export) and fps.
3. May we open a copy of the Theinfranet tox in a scratch project for a side-by-side check (a load into TD needs your go-ahead)?
