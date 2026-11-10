# BF - twozero "Screen Reprojection" rudiment: what it does + clean-room build spec (26 Oct 2026)

Research only: nothing loaded into TD, no code run, no sign-in, no pip. Build: 2025.31550, macOS Apple silicon, TD under Rosetta (x86_64), Vulkan/MoltenVK.
Notation: **[page]** = fetched from twozero.ai; **[idx]** = our `ops/INDEX_2025.31550.json`; **[spec]** = our design, not verified in TD.

## 1. What the original is, and what we could actually learn

### 1.1 Sources and access (honest record)
| Source | Result |
|---|---|
| `https://twozero.ai/rudiments/twozero/screen-reprojection` | HTTP 200, but a SvelteKit shell: **the body is rendered by JS**, WebFetch returned an empty page. Only the head metadata is readable: title "Screen Reprojection"; description **"Anamorphic reprojection: content authored for one viewpoint, re-laid into a physical screen's own pixel raster."** |
| `https://twozero.ai/rudiments` | 200, same shell, no list in the static HTML. `robots.txt` allows pages, disallows `/api/` (not touched). |
| `https://twozero.ai/docs/rudiments` | 200, readable. Facts: rudiments are by **404.zero and setupdesign** "for real shows"; most open with a **PRO subscription**, a few are free; page, screenshots and docs are readable without an account; buttons ADD TO HUB / DOWNLOAD .TOX / GET LINK are **locked without PRO ("signing in is not enough")**. |
| .tox download | **Not obtainable** (PRO-gated; we do not sign in or bypass). `research_src/rudiments_screen_reprojection/` is left empty on purpose; no toeexpand possible. Whether this rudiment is one of the free ones is **UNVERIFIED**. |
| Sibling meta descriptions (same shell trick) | Face Tracking (vankrav): "87 landmarks per face as named CHOP channels, eye and mouth openness, head roll, face/eyes/mouth masks, Apple Vision on macOS, MediaPipe elsewhere". Previz Stage: "LED screen, crowd and stage light that follows your screen content. Wire any TOP in". ZERROR: "drag-and-drop parameter controller, knobs, morphing presets, MIDI, XY and DMX surfaces". TIMELINE: "clips, keyframes, proxies, recording, AI audio tools". dB Meter: "stereo peak level meter with a dB scale, peak hold and labels that always line up with the bars". (Other four rudiments are covered by their own BG-BK notes if the lead writes them.) |

### 1.2 What it does (only what the page text proves)
One sentence is all that is verifiable: it takes **content authored for one viewpoint** (a camera / seat / the "sweet spot") and **re-lays it into the physical screen's own pixel raster**, i.e. anamorphic, view-dependent mapping onto real screen geometry (LED walls, floor/angled screens), so that from that viewpoint the picture looks undistorted although the screen is not facing the viewer.
**Parameters, inputs, outputs and UI of the original: UNVERIFIED** (page body not readable, file not downloadable). Everything below is our own inference from the technique name and is labelled spec.

## 2. Why we want it (PRISMFEST'26 fit)
R02 stage = nine faces 20/10/10/10/30/10/10/10/20 ft, 9984x3840 native (CLAUDE.md `prismfest26-show`). Faces are flat panels at different angles, so a "window" or a 3D object that looks right from the FOH/IMAG camera needs per-face re-projection. Same maths feeds the existing viewer rig. Related prior notes: `AB_projection_mapping.md` (Stoner/camSchnappr/cornerpin, human-in-loop calibration), `AW_fulldome_simulator.md`, `AT_projector_coverage.md`.

## 3. CLEAN-ROOM BUILD SPEC: `JZ_reproject` COMP

### 3.1 Concept (own maths)
Per output pixel of each screen face: world point P on the face -> ray from the eye E through P -> intersect the **content plane** (a virtual window of size Cw x Ch at distance Cd in front of the eye, or a 3D scene rendered through the same off-axis frustum) -> content UV. Result: the face shows exactly the slice of the content the viewer would see through that rectangle. Equivalent to a projective texture from the eye: for planar content it is a homography per face.
Two modes:
- **Plane** (default, GLSL): content TOP is the flat picture "authored for the viewpoint".
- **Scene** (optional): a Render TOP per face using an off-axis camera (Camera COMP `Projection` custom/ window pars) so real 3D renders correctly; output is already in the face raster. Same face table drives both.

### 3.2 Custom parameter pages (names: one capital then lowercase/digits)
- **Viewer**: `Eyex Eyey Eyez` (m), `Lookx Looky Lookz` (m), `Fov` (deg of authored content), `Contentd` (m, content plane distance), `Contentar` (menu auto/16:9/custom), `Flipy`.
- **Screens**: `Facetable` (DAT ref), `Facecount` (readonly), `Active` (menu all/one), `Face` (index), `Unitscale` (m per table unit; ft->m 0.3048), `Pixelsperm`.
- **Output**: `Outres` (menu native/75%/custom), `Outw` `Outh`, `Layout` (menu stack/atlas/single), `Edge` (menu clamp/black/mirror), `Soft` (edge feather px), `Pixelaspect` check.
- **Debug**: `Showgrid` (menu off/uv/eye-rays), `Showframe`, `Markeye`.
- **Controls**: `Opencontrols` (pulse), `Bypass`, `Resetview` (pulse).
Face table DAT columns: `name, cx, cy, cz, ux, uy, uz, vx, vy, vz, wm, hm, px, py` (centre, unit u/v axes, size in m, pixel size/offset in atlas). Pure data, human-editable, stored in the COMP.

### 3.3 Ops (In/Out)
- `in_content` (inTOP) : authored picture. `in_faces` optional (inDAT) overrides `Facetable`.
- `out_main` (outTOP) : **output only**, the face atlas. `out_map` (outTOP, optional) : the UV map as a float texture (for baking into Arena/Resolume as a displacement/remap). `out_face` (outCHOP) : per-face eye-distance and coverage % (for the UI), no controls in Outs [idx: inTOP/outTOP/inDAT/outCHOP all exist].

### 3.4 Internal network, stages (td_layout stages, L->R)
1. **Table** : `faces` tableDAT (+ selectDAT/inDAT switch) -> `parse` scriptDAT/Python module `reproj_math` (below) -> `uniforms` tableDAT/CHOP (matrices per face).
2. **Viewer** : `eye_params` parameterCHOP (or expressions) -> `build_uniforms` scriptCHOP producing, per face, a 3x3 homography H (world-face-UV -> content-UV) = 9 channels x faceCount samples. A CHOP keeps it numeric and `td_inspect`-able.
3. **Content** : `in_content` -> `fit` (fitTOP/resolutionTOP to content AR) -> `content_null`.
4. **Reproject** : `reproject` **glslTOP in compute mode** (T-46: multi-pass tears on MoltenVK; this is one pass anyway). Inputs: content (sampler), `uHomog[]` array via CHOP uniform or a 3xN float texture; output = atlas. Sketch:
```glsl
// per output pixel: find its face from the atlas layout, get face UV (u,v in 0..1)
vec3 P  = centre + (u-0.5)*wm*U + (v-0.5)*hm*V;       // world point on the face
vec3 d  = P - eye;                                     // eye ray
float t = Contentd / dot(d, fwd);                      // hit content plane
vec3 H  = eye + d*t;
vec2 cuv = vec2(dot(H-eye, right)/Cw, dot(H-eye, up)/Ch) + 0.5;
bool ok = t>0.0 && all(greaterThanEqual(cuv,vec2(0))) && all(lessThanEqual(cuv,vec2(1)));
// sample content with edge mode, feather by distance to edge
```
   Compute mode writes with `imageStore`; use `texelFetch`-free `textureLod` sampling with explicit LOD from derivative-free estimate (compute has no auto-derivatives): pick LOD from `|dcuv/dpixel|` computed analytically, or sample 4 taps.
5. **Scene (optional)** : `cam_face` cameraCOMP (off-axis via window pars, per face) + `render` renderTOP + `geo` of the content scene; switchTOP selects Plane/Scene.
6. **Overlay** : `grid` glslTOP/rampTOP checks, `frame` outlines, composite over output when `Showgrid`.
7. **Out** : `null_main` -> `out_main`; `map_gen` (same shader, writes cuv instead of colour, 32-bit float) -> `out_map`.
8. **Controls** : `controls` autoUI panel (`Pagescope` Viewer+Screens+Output, `Pagetabs` off, `align verttb`, widget clones cut), `controls_window` windowCOMP opened by `Opencontrols`; plus a small `viewer_pad` panel (XY pad = eye x/z). Panels never gate the internals: parameters drive everything.

### 3.5 Pure-Python (offline unit tests, no TD)
Module `reproj_math.py` (numpy 2.1.2 is available in TD's Python; for offline tests use any python with numpy, `-I`): `face_basis(face)`, `eye_basis(eye, look)`, `homography(face, eye, content)` returning 3x3, `project(P, eye, content)`, `inverse_map(cuv)`, `face_pixel_to_world`, `coverage(face)`, `ft_to_m`. Tests (pytest, `jazib-td-mcp/tests/`):
1. Eye on the face normal, content plane parallel -> homography = scale+translate (identity-like).
2. Round trip: pixel -> world -> cuv -> world on content plane within 1e-9.
3. Four face corners map to the corners of the visible window for a rectangle that exactly fills the content frustum.
4. Face behind the eye -> `ok=false`; face edge-on -> no NaN.
5. R02 table (9 faces, 20/10/10/10/30/10/10/10/20 ft at 9984x3840) loads, pixel widths sum to 9984, ft->m exact.
6. GLSL parity: evaluate the same maths in numpy for 8 sample pixels and compare to a 1x8 probe readback from the TOP (live check).

### 3.6 Live verification
- `td_inspect` on `out_main` (not black, stats per RGBA, `sample:4` grid) and on `out_face` CHOP (coverage 0..100, eye distance > 0).
- Test content = checker + numbered grid + circle (the `BB_test_patterns_sync` pattern). Put the eye on the screen normal: output must equal the content cropped (a straight, undistorted grid). Move the eye 30 degrees: grid lines must stay straight in the **viewer's** frame (check with a second Render TOP / virtual camera at the eye viewing the faces in the 3D previz: it must reproduce the original picture). That second view is the real proof; a numeric stand-in is the 4 corner pixels (UV values) matching `reproj_math`.
- `td_perf` : cook time of `reproject` at 9984x3840 (target < 6 ms on M1 Max; no number is claimed until measured). `td_errors` clean.
- `td_window_capture` of the readable network and of `controls_window`.

### 3.7 Mac / 31550 caveats and fallbacks
- Compute-mode GLSL TOP is the safe path (T-46). Fall back: fragment-mode single pass (still single pass), or a **remapTOP** fed by a baked float UV map (this is also the Arena-friendly deliverable: a displacement map). cornerpinTOP per face is the zero-GLSL fallback for planar faces [idx: cornerpinTOP, remapTOP, displaceTOP exist].
- 9984x3840 float maps are 150 MB; bake the map at 16-bit or compute live. Resolution under Rosetta: test 75% (7488x2880) first (show rule).
- No Optical Flow, no Nvidia ops needed. No pip needed.
- Anisotropic/oblique faces alias: add LOD or 4-tap sampling; `Soft` for edge feather.

### 3.8 Newer-build features for `docs/FUTURE.md`
None required. Ideas only: GLSL TOP compute `Uniform arrays` improvements and Camera COMP custom-projection pars if later builds expose them; add as "idea only" when verified. (Do not add a row until probed.)

## 4. Estimated build time
Half a day to a day with parallel lanes: math module + tests (1 h), face table + uniforms CHOP (1 h), compute GLSL + probe parity (1.5 h), scene mode (1 h), controls/window/layout (1 h), live verify + LEARNINGS (1 h). Needs no user approvals except the sign-in-free items above.

## 5. Open questions
1. Is the original free (page body unreadable)? User could paste the page text or a screenshot to refine section 1.
2. Eye position source: fixed seat, or tracked (links to the Face Tracking COMP for head-tracked reprojection)?
3. Output: atlas for Resolume, or per-face Syphon feeds?

## 6. Cross-notes for the sibling builds the user listed (not specced here)
- **Face tracking** (stored clip `media/webcam/webcam_ref_5s.mp4` only; live camera on request): TD's bundled Python has OpenCV 4.11 + NumPy 2.1.2, no mediapipe/onnxruntime (D note). Routes: arm64 Apple Vision helper (td-port `jzb_camera_bridge` design, kind 4 faces; landmarks need Vision landmarks request), MediaPipe in Web Render TOP (permission unverified), OpenCV Haar/DNN in a Script TOP (box only). Nvidia ops unsupported.
- **dB meter**: `inCHOP` [idx] fed by AC_audio; our index lists no `audiodeviceinCHOP` (check before relying on it); default output stays the Mac speakers.
