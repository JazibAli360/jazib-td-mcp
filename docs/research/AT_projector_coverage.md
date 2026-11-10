# AT - Projector Coverage Tool (asterix, derivative.ca asset 74222) and a coverage mode for LK_projection_room (26 Oct 2026; TD 2025.31550, macOS, Rosetta, Vulkan/MoltenVK)

Web research only. Nothing run or loaded in TD. Tags: **[V]** page fetched and read; **[U]** unverified or my own design; **[D]** in our ops dump (`ops/ops_COMP_2025.31550.json`).
Evidence saved in `research_src/projcoverage_74222/`: `gumroad.html` (product page), `gumroad_description.txt` (full manual text, the best source), `gumroad_thumb.jpg`.

## 1. What it is
- Community asset "Projector Coverage Tool", author **asterix**, posted 23 Mar 2026, 620 views, 0 comments [V]. A single `Projector_Coverage.tox` (planning component: put it where the projector hangs, it points down -Z) [V].
- **Paid, not obtainable here.** The derivative.ca page links only to Gumroad (seller shown as "Peter Walker", store 5426953996894), **AUD 15** (about USD 10.5), no free tier, no GitHub, no forum thread [V]. derivative.ca returned 403 to curl (not bypassed; WebFetch got the text). The YouTube video (WVvFNEKOZHc) has no description text or links [V]. So: **no .tox, no toeexpand, no build/Mac/licence statement.** TD build required: not stated. Platform: not stated (plain .tox, so no OS gate expected [U]). Licence: not stated; paid single-asset sale.
- Buying is a spend: needs the user's go-ahead. Recommendation below is not to buy; the maths is simple and we can build it into our rig.

## 2. What it computes (all from the Gumroad manual [V])
| Area | Pars (as stored) | Notes |
|---|---|---|
| Specs | `Lensethrow` (throw ratio), `Lumens` (ANSI), `Fnumber` (2.0), `Nativeoffset` (%), `Aspectw/Aspecth` (16:9) | native offset 0% = lens centred on image, 110% = image wholly above lens (ceiling mount) |
| Throw | `Lensedistance` (m), `Screendimensions1/2` (auto W,H), `Projectioncenter` (read only XYZ) | |
| Lens shift | `Verticalshift`, `Horizontalshift`, -100..+100 % | + = image up / right |
| FOV (auto) | `Camerafov`, `Cameravfov`, `Cameradiagonalfov` | |
| Brightness (auto) | `Nits`, `Candelas` (= foot-lamberts) | guide: 50-100 nits indoor, 200+ bright |
| Display | `Displayfrustum`, `Measurement`, `Res` (720p/1080p/4K) | 3D frustum + measurement guides |
| Camera sync | `Camera` (a Camera COMP) | copies position, rotation, FOV, lens shift so a normal Camera renders what the projector sees |
| Utility | `Recommend` | builds a "find me a projector" search query from the specs and copies it to the clipboard |

It is a **single-projector planner**: frustum, screen size, nits/fL, camera sync, shadows (per description: "previsualize shadows on structures or immersive floors", "simulate a depth camera"). **Not described: coverage/overlap heatmap, pixels-per-inch map, blend zones, multi-projector.** How it is built (GLSL, depth maps, Render TOP) is not documented; the shadow preview is most likely a Light COMP/camera shadow render [U]. We learn the parameter set and the maths, not an implementation.

## 3. Formulas (standard optics; the tool's own convention for lens shift/offset is UNVERIFIED since no file)
Let T = throw ratio (distance / image width), D = throw distance (m), image aspect aw:ah, native resolution Nx x Ny.
- Image width `W = D / T`; height `H = W * ah/aw`; diagonal `sqrt(W²+H²)`.
- `hFOV = 2*atan(1 / (2T))`; `vFOV = 2*atan(H / (2D)) = 2*atan(ah / (2*aw*T))`. Inverse: `T = 1 / (2*tan(hFOV/2))`. Zoom lens: T range (e.g. 1.2-1.9) gives a min/max W at one D.
- **Lens shift** (Epson/Panasonic style, % of image size, the image centre moves off the lens axis): `centre offset = (sH*W, sV*H)`; sV = +50 % puts the image bottom edge on the lens axis. Frustum becomes asymmetric: at unit distance, left/right = `-0.5/T + sH/T` .. `+0.5/T + sH/T`, bottom/top = `(-0.5+sV)*ah/(aw*T)` .. `(0.5+sV)*ah/(aw*T)`. "Native offset 110 %" in asterix's wording looks like the same quantity expressed per half-height (100 % = edge on axis) [U]: store ours as shift in % of image height and say so in the par help.
- **Pixel density** on a surface point P with unit normal n, projector at C: `d = |P-C|`, `L = (P-C)/d`, `cosθ = max(dot(n,-L), 0)`. Pixel pitch on a normal plane = `d / (T*Nx)`. So `px per metre = T*Nx*cosθ / d` (oblique surfaces stretch pixels: divide by cosθ in pitch, so multiply here); `ppi = (px per m)/39.37`; `mm per pixel = 1000 / (px per m)`. Rule of thumb to colour by: viewing distance / 3438 per arcminute pixel => "sharp" when pixel pitch < viewing distance/3438.
- **Brightness** (uniform lens, ignoring cos⁴ vignette): normal-plane illuminance `E = lumens / (W_d * H_d)` with `W_d = d/T`, so `E_lux = lumens * T² * aw/ah / d²`; oblique surface `* cosθ`. Luminance of a diffuse screen of gain g: `nits = E_lux * g / π`; `foot-lamberts = nits / 3.426` (equivalently `E_lux*0.0929*g/π...` use nits/3.426). Real projectors lose light to throw/zoom; ANSI lumens is a centre-and-average figure, so treat results as +-20 % [U].
- **Coverage**: point is covered if it projects inside the image rectangle: `q = M*(P-C)` in the projector's camera basis (x right, y up, z forward = -Z), `u = q.x/(q.z... ) ` as below in the GLSL; covered when `0<=u<=1, 0<=v<=1, z>0` and not shadowed.
- **Overlap count**: sum of coverage masks over projectors (0 = black hole, 1 = single, 2+ = blend zone). Blend zone width as % of image width = overlap/W.

## 4. Audit (of what we could see; the .tox itself is not available)
- Product page: Gumroad scripts only; cable.gumroad.com websocket is the storefront, not the asset. Nothing from the author's code is visible.
- `.tox` contents: **unknown.** Claims implying code: Python extensions ("all extensions pre-configured"), clipboard copy in `Recommend` (likely `ui.clipboard` or a subprocess like `pbcopy`) [U]. No evidence of network/eval/pip/subprocess either way. Per audit rules this asset cannot be imported: no file, closed seller, paid. **Not audited = not usable.**
- Our own build below uses only built-in ops and one GLSL MAT; no Python beyond par expressions, nothing phones home.

## 5. Verdict
- **Do not buy / do not depend on it.** It covers one projector's planning numbers (a subset of what LK_projection_room already approximates) and adds nothing we cannot compute: formulas above are textbook. We borrow only its **parameter vocabulary** (throw ratio, lumens, F-number, native offset, aspect, lens shift H/V, auto FOV, nits/fL, frustum toggle, camera sync, find-projectors) and **go further** with the pixel-density and overlap views, which it lacks.
- Derivative's own `projectorBlend` (palette, AB) already handles real edge-blend; our overlap view is only an *analysis* view, not output.

## 6. Recipe for LK_projection_room (sketch; nothing built or tested)
### 6.1 Custom pars on the projector (Light COMP stays the light; a Base `proj_ctl` or the COMP's page "Projector")
`Throw` (float, 0.4-3, default 1.5), `Resx`,`Resy` (int, default 1920,1080; presets 1280x800, 1920x1200, 3840x2160), `Lumens` (float, 6000), `Fnum` (2.0, informational/derating), `Shifth`,`Shiftv` (% of image, -100..100), `Throwdist` (read only, = distance from projector to look-at/target), `Gain` (screen gain 1.0), `Heat` (menu: Off, Coverage, PixelDensity, Brightness, Overlap), `Unit` (menu m / ft / in), `Maxppi` / `Minppi` (colour ramp ends), `Show frustum` toggle.
Read-only outputs: `Imgw`,`Imgh` at target (= D/T, aspect), `Hfov`,`Vfov`, `Pxpm` at target, `Nits`, `Fl`.
Wiring (par expressions, all [U] until tested):
- `Hfov = 2*degrees(atan(1/(2*Throw)))`; `Vfov = 2*degrees(atan(Resy/(2*Resx*Throw)))`.
- Light COMP `projangle` = the larger of the two FOV (hFOV) so the projection map spans the image [D: `projangle` exists]; the projector image is the content TOP going into `projmap`, **resized to Resx x Resy** (Resolution TOP / custom size) so aspect matches. Verify the Light COMP maps the image to the cone as image-width = hFOV; if it uses the diagonal or a circular cone, crop with a Rectangle mask TOP (alpha) and compare against a test chart at 2 distances.
- Lens shift: shifting the *content* inside a symmetric frustum is NOT physical lens shift; the correct model is an off-axis (asymmetric) frustum. For the **viewer-side "projector view" Camera COMP** (used for the frustum preview and for a sanity render): `projection=custommatrix` with the asymmetric matrix from section 3 (near/far from par), or `winx/winy/winsize` [D: present on Camera and Light COMP] with `winx = Shifth/100`, `winy = Shiftv/100*(Resy/Resx)` in units of window width (convention [U], check by rendering a corner marker). If the Light COMP honours `winx/winy`, set them identically so the lit area shifts too; if not, draw the lit area through the shader in 6.3 and keep the Light for shadows only.
- `Nits = Lumens*Throw**2*(Resx/Resy)/D**2*Gain/pi` with D = `Throwdist`; `Fl = Nits/3.426`.
### 6.2 Viewer camera extras (user asked)
Pars: `Fov` or focal+sensor menu (Super35 / full-frame 36 mm / 1-inch), `Dist`, `Orbit`, `Elev`, `Height`, `Lookat X/Y/Z`, `Shiftx/Shifty` (winx/winy), `Persp` toggle (ortho for plan view: `projection=orthographic`, `orthowidth`), preset buttons: Plan (top), Front, Side, Audience eye height 1.7 m, "Through projector" (copy projector basis + FOV + shift). Distances in the unit chosen by `Unit` with a Text TOP overlay showing `Pxpm / ppi / mm per px` at the screen centre.
### 6.3 Coverage / pixel-density / overlap view (GLSL MAT, one pass, no extra buffers)
Ops: the room/target Geometry COMPs get a **GLSL MAT** `view_mat` (replaces the content material only while `Heat != Off`; switch the Geometry `material` par with an expression) -> the existing Render TOP with the viewer camera. Vertex shader: pass `vW` = world position (`TDDeform(P)` style: `vec4 w = TDDeform(P); vW = w.xyz` or `uTDMats[...]`; use the built-in `TDDeform`/`TDWorldToProj` helpers in TD's GLSL MAT, same as the stock template [U on exact names in 31550]) and `vN` = normalize(world normal) (`TDDeformNorm(N)` [U]). Uniforms from a Vectors page on the MAT (or a Table DAT -> `uProj[0..3]`, `uPos`, `uRight`, `uUp`, `uFwd`, `uParams` = (T, Resx, Resy, Lumens), `uShift` = (sH, sV), `uCount` = number of projectors, up to 4 in the first version): set from the projector COMPs via CHOP-to-par or Python-free expressions (`op('light1').worldTransform` via a Transform/Object CHOP -> `Vectors` values).
Fragment shader core:
```glsl
// per projector i: uniforms pos[i], R[i], U[i], F[i] (unit basis, world), P[i] = vec4(T, resx, resy, lumens), S[i] = vec2(shiftH, shiftV) (fraction of image)
struct Res { float cov; float ppm; float lux; };
Res probe(int i, vec3 W, vec3 n){
  vec3 v = W - pos[i]; float d = length(v); vec3 L = v/d;
  float z = dot(v, F[i]); Res r = Res(0.,0.,0.);
  if (z <= 0.) return r;
  float T = P[i].x, ar = P[i].y/P[i].z;                 // aspect w/h
  float u = dot(v,R[i])/z * T + 0.5 - S[i].x;           // 0..1 across image width, lens shift moves image centre by +S.x
  float vv = dot(v,U[i])/z * T * ar + 0.5 - S[i].y;      // 0..1 up the image height
  if (u<0.||u>1.||vv<0.||vv>1.) return r;
  float c = max(dot(n,-L), 0.);
  r.cov = c > 0. ? 1. : 0.;                              // facing the projector
  r.ppm = P[i].x * P[i].y * c / d;                       // px per metre
  r.lux = P[i].w * T*T*ar / (d*d) * c;                   // lumens / lit area, times cos
  return r;
}
void main(){
  vec3 n = normalize(vN); float cnt=0., ppm=0., lux=0.;
  for(int i=0;i<uCount;i++){ Res r = probe(i,vW,n); cnt += r.cov; ppm = max(ppm, r.ppm); lux += r.lux; }
  vec3 col;
  if(mode==1) col = cnt<.5 ? vec3(.1) : vec3(.1,.7,.2);               // coverage
  else if(mode==2) col = ramp(clamp(ppm*0.0254/ uMaxPpi,0.,1.), cnt); // pixel density: ppi = ppm/39.37, ramp turbo/viridis (see dataviz ramp: red = too coarse)
  else if(mode==3) col = ramp(clamp(lux*uGain/3.14159/ uMaxNits,0.,1.), cnt); // nits
  else col = overlapColour(int(cnt));                                  // 0 black, 1 grey/green, 2 amber, 3+ red
  fragColor = TDOutputSwizzle(vec4(col,1.));
}
```
(The `u` and `v` lines: for a point at depth z, `x/z * T` is the offset in image widths, so u = 0.5 + that; the sign of the shift term must be tested once with a corner marker. Use 32-bit float Render TOP if a ramp lookup via Ramp TOP + `texture()` is preferred to inline maths.)
- **Shadows/occlusion (stage 2):** extra Render TOP from each projector's camera with a depth-only GLSL MAT writing linear distance to a 32-bit float TOP (`rgba32float`), fed to `view_mat` as `sampler2D uDepth[i]`, compare `d` to stored distance (+bias) to zero `cov`. Cheaper first version: skip occlusion and rely on the existing Light COMP shadows in the normal view.
- **Overlap/blend view:** same shader, mode 4 (cnt colours). Blend width readout: sample row at screen centre or compute analytically from two neighbours' `Imgw`.
- **Legend and numbers:** Ramp TOP + Text TOP legend (ppi min..max, nits min..max) composited over the Render TOP; Analyze TOP / a Python-free Math CHOP over the screen mask gives min/avg/max ppi if wanted.
- **Cost:** one extra material, per-pixel loops of <=4 projectors: negligible on Vulkan/MoltenVK. GLSL MAT on macOS is GLSL 4.60 via TD's Vulkan translation; keep arrays small and avoid dynamic indexing of sampler arrays (use fixed `uDepth0..3`) [U].
### 6.4 Multi-projector
Duplicate the projector Base N times (replicator-free: 2-4 fixed copies), each with its own `Throw/Res/Shift/Lumens` and a `Enabled` toggle; `uCount` = enabled ones. Overlap view uses all.
### 6.5 Checks before calling it done
1. Test chart (grid Ramp/Checker) at D = 3 and 6 m: measured image width = D/T within 1 %. 2. Shift 50 %: bottom edge of the image on the lens axis horizon. 3. A flat wall perpendicular: ppi in shader = Resx/(W) /39.37. 4. Rotate the wall 60 degrees: ppi drops by cos60. 5. Two projectors overlapped by 20 %: overlap view shows the 2-count strip of 20 % width.

## 7. Open questions for the user
1. Does the user want the paid asset anyway (AUD 15) for comparison? We recommend no.
2. Real projector models/lenses on the PF26 job (throw ratios, native resolutions, lumens, shift range) to preload as presets? None are known.
3. Is the Light COMP projection map honoured with `winx/winy` shift in 31550? Needs one live test (user go-ahead to touch the rig).
