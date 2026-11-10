# BL - Gaussian splats and point clouds in TouchDesigner (26 Oct 2026)

Research agent BL. Offline: TouchDesigner was **not touched** (no `td_*` call, nothing loaded into TD, no downloaded code run, no pip,
no logins). Target build **TD 2025.31550** (Intel/Rosetta, Vulkan/MoltenVK) on an M1 Max; Python 3.11 x86_64 with cv2 4.11 + numpy 2.1.2.
Tags: [V] read/measured by me today, [S] stated by a page/forum post (cited), [U] unverified, [L:T-nn] our LEARNINGS (wins over this file).
Sources on disk: `research_src/BL_gaussian_splats_pointclouds/` (samples, expanded toes; `ex7/`, `yeataro_expanded/`, `deformer_71841/`,
`b2bk_62516/` are `toeexpand` text only) plus `research_src/community/files/69107/expanded/` (done earlier by another lane).

## 0. Top findings

1. **The most-viewed splat asset (Tim Gerritsen, asset 69107, 17,928 views, rank 3 of our scrape, 4 Mar 2024, no licence) cannot be used as is
   here.** [V] It is built in 2023.11510/Windows, sorts with a **multi-pass pixel-mode bitonic GLSL network** re-run on every camera move (the
   author says it is slow above 1 M splats) and that is exactly the pattern T-46 says tears on this Mac. Its **vertex/fragment shader and SH code are
   clean and portable** (read below) and are the reference for our clean-room shader.
2. **TD 2025.31500+ has the POP route that replaces the TOP sort**: Derivative staff (vincentDev, Jan 2025) ported Gerritsen's setup to POPs and the
   gain is the **Sort POP (AMD FidelityFX radix sort)** [S forum 562056]. I expanded the Derivative-shipped example (`EXAMPLE 7 - POPS GAUSSIAN SPLATTING
   (experimental).toe`, inside the Fulldome repo, built 2025.30060): Point File In POP (manual attribute mapping) -> Sort POP (`ptmethod object`, camera
   as object) -> Null POP -> Geometry COMP **instancing, one quad per splat, 4 custom instance attributes (P, scale, rot, Color)** -> GLSL MAT -> Render TOP.
3. **31550 specifics** [V from `ops_POP_2025.31550.json`]: `pointfileinPOP` (37 pars) has **no `splat` (Gaussian Splat Format Auto/PLY/SPZ) menu**, that
   came in later docs. Splat attributes must be mapped by hand with `attr0..N` blocks (`scale_0..2`, `rot_0..3`, `f_dc_*`, `opacity`, `f_rest_*`) like ex7 does.
   `sortPOP`, `glsladvancedPOP` (139 pars), `choptoPOP`, `toptoPOP` (67 pars, has `camera/fov/dispscale/deletenear/deletefar`), `poptoTOP`, `lookuptexturePOP`
   all exist; `rayPOP` and doubles do not work on Mac [L:T-35]. `.spz` loading in 31550 is [U] (the app ships `Samples/PointClouds/SmileyPinata.spz`
   but no splat example .toe). So: **own Python decoders for .splat/.spz** are part of the spec, `.ply` goes through Point File In POP.
4. **Paid/closed state of the art (all ranked below):** TDGS 1.3.1 (Lake Heckaman / "Watershed", macOS + Apple Silicon, TD 2025.31760+, Patreon, ~USD 30
   per a Reddit comment) and **GSOPs** (same author, POP-native custom operators, `.ply` + `.spz`, TD **2025.32820+**, free Lite non-commercial tier,
   tested on an Apple M3). Neither is downloadable without an account, so neither is audited or adopted; both prove the POP approach works on Apple GPUs.
5. **Cheap CPU sort is a real fallback**: [V, M1 Max arm64 numpy 2.5.2] `np.argsort` of 1 M float32 depths = 90 ms (quick) / 106 ms (stable), but with
   **16-bit quantised keys and `kind='stable'` (numpy radix) = 5 ms per 1 M** (9 ms per 1.8 M). Rosetta (x86_64 numpy 2.1.2) will be slower: **measure, do not trust**.
6. **File formats checked against real files** [V]: `hornedlizard.spz` (Niantic, MIT) = gzip -> 16-byte header `NGSP`, v2, **786,233 splats, SH degree 3**,
   24-bit fixed-point positions (12 fractional bits), planar layout positions/alpha/colour/log-scale/rotation(3 bytes)/SH, and the bytes left after rotations
   equal exactly `n*45`, so the layout in section 5.1 is right. `nike.splat` (antimatter15 format, 32 B/splat) = **270,491 splats**.
   Our own SHARP ply (`~/ComfyUI-Shared/output/sharp_*.ply`, 66 MB each, not copied) = **1,179,648 splats, SH degree 0**, 14 float properties.
7. **Depth-from-image is already solved on this Mac by our native helper**: `td-port/camera_bridge` kind 1 = Depth Anything V2 Small (Core ML F16),
   **66.7 ms median round trip (helper compute 54 ms), ~15 maps/s** through the socket from TD 2's Python [V in td-port README]. `toptoPOP` can unproject a depth
   TOP with a camera in one op (par list above) [U behaviour].

## 1. Landscape (ranked; "Mac/31550" = status for our TD 2025.31550 under Rosetta)

| # | Item | What | Mac / 31550 | Licence | Status here |
|---|---|---|---|---|---|
| 1 | **Gaussian Splatting tox**, timgerritsen (asset 69107; [page](https://derivative.ca/community-post/asset/gaussian-splatting/69107)), 17,928 views, 28 likes, 0 page comments, forum thread 439835 | 55 KB tox, `.ply` -> Render TOP, GLSL MAT instancing (1024 quads/instance), SH degree 3, bitonic sort pulse + `Autosort`, `alpha threshold 0.015` | Authored 2023.11510 Windows. Sort = multi-pass pixel GLSL: T-46 risk [U live]. Vulkan Y/clip-space issue discussed in thread (fixed by normalising the quaternion, 4 Mar 2024) | none stated (ask author) | **read and used as reference**, not adopted |
| 2 | **Derivative `EXAMPLE 7 - POPS GAUSSIAN SPLATTING (experimental)`** (in github Fulldome repo; vincentDev POP port, [forum 562056](https://forum.derivative.ca/t/4d-gaussian-splat/562056); v1.0.37 for 2025 Alpha 5.3, 1.0.39 Alpha 6) | Point File In POP + Sort POP + instancing; same shader maths | Built 2025.30060 Windows; "runs extremely slowly or freezes in 5.3 (2023.32127)" Feb 2025 (staff investigating) [S]; 31550 [U] | none stated | **read** (ex7), the structural template |
| 3 | **TDGS 1.3.1** (Lake Heckaman, [radiancefields](https://radiancefields.com/tdgs-for-gaussian-splatting-in-touchdesigner), Dec 2025) | commercial toolkit: SPZ, thin/limit sort to a bounding box, "Blowout", dissolve, relighting | **macOS + Apple Silicon, TD 2025.31760+** [S] (a Glama MCP page still says NVIDIA/Windows only; newer source wins) | Patreon, paid (~USD 30 [S reddit]) | not downloaded (login/spend) |
| 4 | **GSOPs** (Heckaman, [radiancefields](https://radiancefields.com/gsops-brings-native-gaussian-splatting-to-touchdesigner)) | POP-native: Splat Scene, Load Splat (.ply/.spz), Write Splat PLY, Frustum Delete, Thin Splat, Blowout, Splat Geo, Refractive; effects: alpha accumulation, bokeh, motion blur, relighting, chroma key; TDFam (Apache-2.0 framework by dotsimulate + function.str) | **TD 2025.32820+** [S], tested macOS M3; 31550 **not enough** | free Lite non-commercial, paid Create tier | not downloaded; needs the arm64 32820 app |
| 5 | **TouchDesigner-GaussianSplat-ParticleSystem** (lakeheck, [repo](https://github.com/lakeheck/TouchDesigner-GaussianSplat-ParticleSystem), 19 stars, pushed 20 Jun 2025) | repo holds README only; tox is Patreon. Features list: "WORKS ON MAC", turbulence dissolve, splat <-> point cloud fade, home-location return, optional depth + velocity buffers, bounding volumes, sort toggle | Mac yes [S] | CC BY-NC-ND 4.0 [V README] | feature list used as idea bank |
| 6 | **TD-Gaussian-Splatting** (yeataro, [repo](https://github.com/yeataro/TD-Gaussian-Splatting), 64 stars, 173 MB, Jun 2025) | TOP/GLSL rasteriser (2022 + 2023 toes), depth/DOF, relighting, stylise; sorters `CHOP_sort`, `NumpySort`, `GPU_bitonic_mergesort` | Windows-authored (2022.33910) [V .build]; Mac [U] | none stated | 3 small sorter toxes downloaded and expanded (text only): NumpySort = `argsort` of the blue (depth) channel in a Script TOP; confirms the CPU-sort idea |
| 7 | **TD tutorial 05, ETCH-01** ([page](https://derivative.ca/community-post/tutorial/touchdesigner-tutorial-05-3d-gaussian-splatting-trainingrefiningmanipulating), 30 Mar 2025, 2,034 views) | PostShot train/clean/export, show as points and splats with Gerritsen's tox | video only; auto-subs in `samples/etch01_tutorial05_autosubs.srt` (noisy, low value) | n/a | read |
| 8 | **POINTCLOUDS from 2D images (+depth)** (gnomalab/B2BK, asset 62516, 7,472 views, 2020) | colour + depth JPG pairs -> instanced point/line render, Level/Add noise, LFO camera | 2019.36500; instancing from TOPs = portable [V toe] | none | downloaded + expanded: confirms the TOP-instancing recipe `instancetx/ty/tz = r/g/b` from a Null TOP |
| 9 | **Point Cloud Surface Deformer V1** (timgerritsen, asset 71841, 4,407 views, Apr 2025) | attractor + auto-centre; reuses `glslSplat_vertex`; ex-Gerritsen splat shader as point-cloud renderer | 2023.12370 Windows | none | expanded (toe), shader = same as #1 |
| 10 | **Point cloud tutorials** (supermarket sallad, YouTube 223,489 views "Pointclouds (without lidar)"; nicholaspjm "Wispy Real Time PointClouds" 104,980 views; dcheesman "video -> 3D point cloud", Reddit, Jun 2025) | render-depth -> TOP -> instancing; Video Depth Anything | files on Patreon | per creator | not fetched; techniques noted |
| 11 | **Josef Pelz PCR (Point Cloud Render)** | point render with built-in DOF, named in 3 Reddit threads | platform [U] | [U] | not found free |
| 12 | **TD Depth Anything** (olegchomp, 188 stars, MIT) | TensorRT depth | NVIDIA/Windows only | MIT | out for this Mac; use camera_bridge instead |
| 13 | Sensor clouds: **FreenectTD** (stosumarte, LGPL-2.1, 104 stars, Kinect v1 on Mac), Depth Cam Merger (snaut, 3,782 views), TDLidar (iOS app, free since 29 Apr 2026 [S reddit]) | live depth/point sources | Kinect/Azure/ZED/Body Track unsupported on macOS [L:T-18]; RealSense/OAK created without OS error, device output [U] | mixed | for a later input module |
| 14 | **SHARP** (Apple ml-sharp) via ComfyUI-Sharp on this Mac | single image -> splat `.ply` in 15 s [L AL] | Mac MPS yes | Apple ML Research Licence, research/non-commercial [S HF mirror] | 10 outputs exist locally (66 MB each, 1.18 M splats, SH0): ready test data |

Authoring/format tools (not TD): **SuperSplat** (PlayCanvas editor, MIT; imports/exports PLY, compressed PLY, SOG), **SOG** (Self-Organizing Gaussians, WebP images in a
ZIP, >20x smaller, [PlayCanvas blog](https://blog.playcanvas.com/playcanvas-adopts-sogs-for-20x-3dgs-compression)), **SPZ** (Niantic, [repo](https://github.com/nianticlabs/spz), MIT, v2/v3 gzip,
**SPZ 4 (May 2026) = six parallel ZSTD streams, 32-byte plaintext header, no 10 M cap** [S nianticspatial.com/blog/spz4]), glTF **KHR_gaussian_splatting** (Khronos
release candidate Feb 2026, not ratified as far as I found), Inria 3DGS reference (non-commercial research licence, [U exact text]), PostShot (jawset), Luma/Polycam exports (PLY).

## 2. How a splat renders (maths the shader must match)

Each splat has centre `p`, log-scale `s` (3), unit quaternion `q`, opacity (stored as logit in INRIA .ply: `a = sigmoid(opacity)`; in .splat/.spz already 0..1)
and colour = SH coefficients (`f_dc_0..2` DC; `f_rest_0..44` for degree 3; INRIA stores them channel-major: all R, then all G, then all B).

1. 3D covariance `Sigma = R S S^T R^T`, `S = diag(exp(s))`, `R = quat->mat3(normalize(q))`. **Normalise the quaternion** (that was Gerritsen's orientation bug, [S forum 374866]).
2. Project: camera-space `t = View*p`, clamp `t.xy/t.z` to `1.3*tan(fov/2)`, Jacobian `J = [[f/z,0,-f x/z^2],[0,f/z,-f y/z^2]]`, `Sigma2D = J W Sigma W^T J^T`, **add 0.3 to both diagonal entries** (low-pass).
3. `det = a c - b^2`; conic `= (c, -b, a)/det`; quad half-size = `3*sqrt(a), 3*sqrt(c)` pixels.
4. Fragment: `power = -0.5(conic.x dx^2 + conic.z dy^2) - conic.y dx dy`; `alpha = min(0.99, opacity*exp(power))`; discard if `power > 0` or `alpha < max(thr, 1/255)`; output premultiplied.
5. Order: **back to front by view depth**, blend `src ONE-MINUS-SRC-ALPHA` premultiplied (ex7 uses `srcblenda omda, destblenda one` = front-to-back variant for the alpha channel), no depth write.
6. Colour: DC `0.5 + 0.28209479*f_dc`; degree 1 adds `0.4886025*(-y c1 + z c2 - x c3)` using direction `normalize(p - camPos)`; clamp at 0. (Gerritsen/ex7 code verified by reading.)

Cost drivers: splat count (instances), **overdraw** (large alpha-blended quads x 1080x1920 = 2.07 M px), and the **sort on every camera move**.

## 3. How it fits TD 2025.31550 on this Mac

Three renderers exist in the wild; which are safe here:

| Path | Data | Sort | Verdict on this Mac |
|---|---|---|---|
| T (tex) Gerritsen | 32F TOPs (pos, rot, scale, SH) from Point File In TOP + Select; GLSL MAT `texelFetch` through a sorted lookup texture | multi-pass pixel GLSL bitonic | **avoid** (T-46: stale/torn pixels, negatives; rule "multi-pass GLSL on TD 2 is compute") |
| P (POP) ex7 / vincentDev / GSOPs | POP attributes; Geometry COMP instancing with 4 custom attribs | Sort POP (radix, compute) | **primary**; Sort POP/Point File In POP/GLSL MAT unprobed on 31550 -> first probes |
| C (CPU) | numpy decode + argsort | `np.argsort(uint16 keys, kind='stable')` | fallback and for `.splat/.spz` decoding |
| W (sort-free) | any | none: weighted-sum order-independent blending (Mobile-GS / "Sort-free Gaussian Splatting via Weighted Sum Rendering", arXiv 2410.18931: ~1.23x faster on mobile) | stylised option, approximate colours [U in TD] |

Facts that bound the design:
- Geometry COMP instance pars on 31550: `instanceop` (Default Instance OP; not `instancepop`), `instancecountmode oplength`, `instancetx/ty/tz = P(0..2)`, 8 custom
  attribute slots `instance0customx..w` readable in a GLSL MAT (`TDInstanceCustomAttrib0..3(index)`) [L:T-15, V ex7 geo1.parm].
- Texture instancing on macOS is capped at about 128 textures (irrelevant: we use POP attributes) [docs via P_realtime_3d_looks].
- GLSL out-of-bounds array access can crash the whole app under Vulkan [L:T-35]: every `texelFetch`/array index in our shaders clamps.
- Memory: POP outputs grow but are not freed until `freeextragpumem`; "set the memory limit before looping Copy POPs" [AD]; scale up point counts in steps.
- Point File In **TOP** had a `.ply` regression in 2025.33070 (fixed after 18 Aug 2026 per forum 1006134, `32820` fine); 31550 is unaffected as far as reported.
- POP colours are **not** colour-space converted on import in this era (`Accurate colors in POP-made pointclouds`, forum 620758: staff said no POP does sRGB<->linear; a colour-space-aware
  Point File In POP was "in development", Jul 2025). Rule: do the sRGB->linear (or the SH `+0.5` then `^2.2`) in our shader, and make it a parameter.
- 8-bit PLY colours: `/255` (a university project needed `/127` for 0..127 data, so check max first).
- Depth of splat renders: no per-pixel depth (Gerritsen, forum 684985); Watershed writes distance to a second Render TOP output (needs 32F pass, artefacts, "alpha/experimental POP builds don't support render image output"). Use a separate "centre depth" pass or post depth estimation instead.
- Heavy numpy in TD 2's Python can fail (T-48: `numpy._core.multiarray` ImportError for a whole session). The decoder module must `try: import numpy` and report a clear error in the COMP's status field.
- Rendering at 1080x1920 default (CLAUDE.md); the COMP takes a resolution par.

## 4. Point clouds in TD (what else the second COMP needs)

- Import: Point File In **POP** (`.ply .obj .fits .exr .xyz .pts .csv .txt`, thin pars, `rerange`, `inputcolorspace`) or the older Point File In **TOP** + Point File Select (xyz in RGB of a 32F TOP, extra fields via select) [S docs]. Sample files in the app: `Samples/PointClouds/{banana.ply (49,106 pts ASCII x y z nx ny nz r g b a, 3.9 MB), bananaNorm.ply, sphere.xyz (X Y Z U V Nx Ny Nz), SmileyPinata.spz (5.1 MB)}` [V].
- Render: (a) Geometry COMP instancing of a tiny quad/circle with Point Sprite MAT or Constant MAT (baseline of every tutorial above); (b) Line MAT for B2BK-style lines; (c) our splat quad shader with isotropic scale = "soft points".
- Create: depth image -> cloud (Section 4.1), Grid/Sprinkle/Sphere/Torus POP generators, SOP to POP, Text TOP -> TOP to POP (typography clouds), Particle POP (existing recipes in AD).
- Morph (Section 7.2): equal-count matching, then blend in the vertex stage or with Blend/Math Mix POP.
- LOD / budget: `thinstep`/`thinrandom` in Point File In POP (index-based, load-time), `maxpoints`, distance-based point size (screen-space), frustum cull + bounding box in our shader/Delete POP, **Blowout** (push far splats away to reduce overlap, TDGS idea), progressive load (first 100k then rest). Literature: Octree-GS (LOD levels, 10x faster in large scenes, arXiv 2403.17898) and "A LoD of Gaussians" (out-of-core hierarchy, 60 M+ on 24 GB, arXiv 2507.01110) need LOD-trained files; not usable with ordinary `.ply`. A simple substitute: precompute importance `= opacity * volume` offline and keep the top-K per frame via the `thin` pars (spec: `Budget` par).

### 4.1 Depth from an image (our Vision helper)

`td-port/camera_bridge` (read-only here): arm64 helper `jzb_camera_bridge`, Unix socket, request kind 1 = Depth Anything V2 Small F16 (49.9 MB model, Apache-2.0), sides <= 2048,
BGRA8 in, float32 depth out (bottom-up rows), **percentiles lo/hi** returned with each map; **66.7 ms median / 67.2 p95 round trip, 15 maps/s**, model load 8.25 s first ever, ~70 ms later [V, README].
The map is **relative (affine-invariant inverse depth)**, not metres. Unproject with a guessed pinhole: `d' = (d - lo)/(hi - lo)` in 0..1, `z = zfar/(1 + d'*(zfar/znear - 1))` (z from inverse
depth, `znear/zfar` parameters), `x = (u-cx)/f*z`, `y = (v-cy)/f*z`, `f = 0.5*W/tan(fov/2)` (default fov 60 degrees = [U] user par). Alternatives: pre-baked depth JPG pairs (B2BK), SHARP/ComfyUI splat, Video Depth Anything for temporal stability [S dcheesman]. Not usable: TDDepthAnything (TensorRT), Kinect/ZED/Body Track (T-18).

## 5. Formats (decoders the splat COMP needs; all offline-testable)

### 5.1 Layouts [V against real files]
- **INRIA `.ply`** (binary little endian): properties `x y z (nx ny nz) f_dc_0..2 f_rest_0..44 opacity scale_0..2 rot_0..3`; `rot_0` = w. The SHARP files have only
  `x y z f_dc_0..2 opacity scale_0..2 rot_0..3` (14 floats, SH degree 0). Parse the header, build a numpy structured dtype, `np.fromfile(..., offset=header_len)`; the 66 MB file loads in well under a second.
- **`.splat`** (antimatter15): 32 bytes/splat = `f32 x3 pos, f32 x3 scale (linear, NOT log), u8 x4 RGBA (colour already DC-applied, alpha already sigmoid), u8 x4 quaternion (`(u8-128)/128`, order w,x,y,z)`; no SH. [V nike.splat: 8,655,712 B = 270,491 x 32; positions in (-1.7..2.6), scales 4.7e-8..0.33].
- **`.spz` v2/v3** (Niantic, MIT): `gzip` -> header `u32 magic 0x5053474e ("NGSP"), u32 version, u32 numPoints, u8 shDegree, u8 fractionalBits, u8 flags, u8 reserved`; then planar arrays: positions `n*9` bytes (3 x 24-bit little-endian two's complement, `/ 2^fractionalBits`),
  alphas `n` (u8/255, already sigmoid), colours `n*3` (`(u8/255 - 0.5)/0.15` = `f_dc`), scales `n*3` (`u8/16 - 10` = log-scale), rotations (**v2: 3 bytes** `xyz = u8/127.5 - 1`, `w = sqrt(1-|xyz|^2)`; **v3: 4 bytes** "smallest-three" packing, take the exact bit layout from `src/cc/load-spz.cc`, [U] not decoded by me), SH `n*shDim*3` bytes (shDim 3/8/15; remaining bytes after rotations were exactly `n*45` for degree 3 on `hornedlizard.spz`). `hornedlizard.spz` decoded: 786,233 splats, positions -200..200 (far floaters, expect a crop), alpha mean 0.57, log-scale -10..1.125, f_dc -2.65..2.92.
- **SPZ 4** uses ZSTD streams; TD 2's Python has no `zstandard` module [U probe] -> unsupported in v1 (FUTURE).
- **SOG / compressed PLY (PlayCanvas)** and glTF KHR_gaussian_splatting: FUTURE.

## 6. Mac / MoltenVK performance and the T-46 rule

- No measured TD splat number exists for this machine yet. Published splat figures are for CUDA (4DGS 70 fps at 800x800 on an RTX 3090 [S forum]) or mobile (Mobile-GS 116 fps Snapdragon 8 Gen 3) and are not transferable.
- What is measured on this Mac: compute-mode GLSL is clean (340/340 and 441/441 frames, T-47), pixel-mode chains tear; POP ops are compute. That is why Sort POP / GLSL Advanced POP are the plan and why any extra GLSL is **compute mode or single pass** with a measured check.
- Guard pattern for any multi-op chain: read back the final output with `numpyArray()` and compare to the offline reference (section 7.1, tests R1-R7) before trusting it.
- Budget gates (to be measured by the builder with `td_perf`, numbers below are targets, **not** claims): 100 k splats >= 55 fps, 300 k >= 30 fps, 1 M >= 12 fps with sort-on-pulse, all at 1080x1920, nothing else cooking. If 300 k misses 30 fps, ship `Budget` and `Sortmode` defaults that hit it and say so.
- Overdraw control: `Scalemult`, `Alphathreshold` (default 0.015 like Gerritsen; 0 is heavy), min pixel radius cull, opacity cull at load (`opacity < 1/255`).
- GPU memory is unified (no separate VRAM); a 1.18 M splat SHARP file with SH0 = 1.18 M x (3+3+4+3 floats + opacity) ~ 62 MB as floats, small; degree-3 files add 45 floats/splat (hornedlizard: 35 MB of u8 -> 141 MB as float32) -> **drop SH above degree 1 at load** (parameter `Shdegree`, default 1; 0 for speed).

## 7. CLEAN-ROOM BUILD SPECS

Rules from the brief apply to both: self-contained COMP (everything inside, custom pars drive internals, Out ops output only), own controls panel + `controls_window` opened by an `Opencontrols` pulse, **no safety limits or warnings** (the operator decides; give BPM / manual / audio options), Mac speakers default for audio out and **never mic -> speaker**, webcam tests on `media/webcam/webcam_ref_5s.mp4`, networks arranged L-to-R with titled stage boxes (`td_layout flow`, T-65/T-66/T-69), viewers on, unique probe names (T-20). **Saving (user, 26 Oct: "save ur projects always so u dont lose ur progress or learnings or node setups"):** agents never save inside TD (T-71: the main session saves after every verified build and autosave runs every 10 min); the builder therefore ends each verified stage by asking the main session for `td_save_project` + `td_tox_save` of the COMP to `projects/lab_tox/<name>_vNN.tox`, and writes every new fact to LEARNINGS at once.

### 7.1 `BL_splat_render` at `/project1/lab/BL_splat_render` - Gaussian splat renderer (primary build, ~8-10 h incl. probes)

**In/out.** In: optional Select-path par for an external Camera COMP (default = internal orbit camera), optional audio CHOP path (e.g. `/project1/audio/analysis`), optional bg TOP. Out: `out1` Out TOP (premultiplied RGBA, `Resolution` par default 1080x1920, 16F), `out_info` Out CHOP (channels `splats`, `drawn`, `sort_ms`, `fps_cook`, `ok`). Nothing else leaves.

**Custom pars (pages, all with real units; no limits enforced):**
- Source: `File`, `Format` (auto/ply/splat/spz), `Reload` (pulse), `Maxsplats` (0 = all), `Thinstep`, `Thinrandom`, `Opacitycull`, `Shdegree` (0/1), `Coordfix` (menu: none / flipY / flipZ / rotX180; INRIA scenes are Y-down, SHARP and others differ), `Cropcenter xyz`, `Cropsize xyz`, `Cropradius` (outlier floaters like hornedlizard +-200).
- Camera: `Cammode` (internal orbit / external), `Camcomp`, `Orbitaz/el/dist`, `Target xyz`, `Fov`, `Autorbit` (deg/s), `Orbitsync` (None/BPM/Audio), `Bpm`, `Beatsperrev`.
- Splat: `Scalemult`, `Opacitygain`, `Alphathreshold` (default 0.015), `Lowpass` (the 0.3, default 0.3), `Brightness`, `Gamma`, `Srgbtolinear` (toggle), `Pointmix` (0 splat .. 1 round point), `Pointsize`.
- Sort: `Sortmode` (sortpop / cpu / sortfree-wsr / frozen), `Sorteveryn` (frames), `Sortmovedeg` (re-sort when the view direction moved more than N degrees), `Sortnow` (pulse).
- Look: `Dissolve` (0..1, per-splat noise threshold on opacity), `Dissolveseed`, `Noiseamp/freq/speed` (position noise), `Explode` (radial push), `Reveal` (z-sweep along camera axis), `Audiomap` table (band -> par, gain), `Beatpulse` (BPM-locked kick on Scalemult).
- Output: `Resolution`, `Bgcolor`, `Premult`, `Outputalpha`.
- Panel: `Opencontrols` (pulse -> `controls_window`), `Status` (read-only string), `Reset`.

**Network (stage boxes, left to right).**
1. **LOAD** - `Format` router. `.ply`: `pointfileinPOP` with attribute blocks for 31550 (ex7 recipe): `colorfields "f_dc_0 f_dc_1 f_dc_2 opacity"` (Color), `attr0` = `scale_0 scale_1 scale_2` name `scale`, `attr1` = `rot_0..3` name `rot` qualifier quaternion, `attr2..` = `f_rest_*` blocks (`sh0..sh14` as float3, built by a small Python that sets `seq.numBlocks`, like ex7's `text_fillParameters`; only if `Shdegree >= 1`). `.splat/.spz`: DAT text module `bl_decode` (pure numpy) -> `scriptCHOP` with one sample per splat and channels `tx ty tz r g b a sx sy sz qw qx qy qz [sh..]` -> `choptoPOP` mapped to the same attribute names. Both -> `mergePOP`/`nullPOP` `loaded`. Thin/crop/cull = `Thin` pars and `Delete POP` by expression on attributes (opacity, crop box).
2. **PREP** - one `glsladvancedPOP` (compute) that converts per splat once: `opacity = sigmoid(opacity)` (ply only), `scale = exp(scale)` (ply/spz), `rot = normalize(rot)`, `colour = SH0 -> 0.5 + 0.28209479 f_dc`, applies `Coordfix`, writes `Color(rgba)`. (Compute-mode, one pass: T-47.)
3. **ORDER** - `sortPOP` `ptmethod object`, `pointobj` = the camera COMP (Z-axis-relative sort = view depth), `pointrev` as needed, then `nullPOP sorted`. Gated: `Sortnow`, `Sorteveryn`, `Sortmovedeg` drive `bypass` of the Sort POP through a tiny CHOP/Execute DAT (resort only when needed; the unsorted order persists). `Sortmode cpu`: Script CHOP/DAT computes `key = (dot(P - cam, forward) -> uint16 over [min,max])`, `order = np.argsort(key, kind='stable')[::-1]`, writes `order` channel -> `choptoPOP` -> a `glsladvancedPOP` gather (`out[i] = in[order[i]]`) - positions are read back once at load (`poptoTOP` numpy 16 B/splat) and cached in a DAT-stored array. `Sortmode wsr`: skip stage; stage 5 switches to additive weighted blend + normalise TOP.
4. **LOOK** - `glsladvancedPOP`/`mathmixPOP`/`noisePOP` per-splat effects (dissolve, noise, explode, reveal, audio gain); output `nullPOP final`.
5. **DRAW** - `geometryCOMP draw` with `instancing on`, `instanceop = final`, `instancecountmode oplength`, `instancetx/ty/tz = P(0..2)`, custom attribs 1/2/3 = `scale`, `rot`, `Color` (as ex7), `material = glslMAT splatmat`, child = one `rectanglePOP`/SOP unit quad (`size 2x2`, no normals/texture). Shader `splatmat` = clean-room vertex + fragment of section 2 (about 90 lines, GLSL sketch below). Premultiplied output, `depthwriting off`, blend `ONE, ONE_MINUS_SRC_ALPHA`.
6. **RENDER** - `cameraCOMP` (internal) + `renderTOP` (`bgcolora` 0 so alpha is real, T-15; antialias off; 16F) -> optional `glslTOP` (compute, single pass) for WSR normalise / point mix / tone -> `out1`.
7. **CONTROL** - Execute DATs: BPM/audio mapping, orbit time (absTime based, one reader per frame, T-21), `Status`, `out_info` Script CHOP, `Opencontrols` -> `controls_window` with `autoUI` panel (T-45/T-52 recipe: Parameter COMP).

**GLSL sketch (vertex, GLSL MAT, one pass; names per TD 2025 MAT API as in ex7).**
```
uniform vec3 uFocal;          // tan(fov/2)*?  -> x,y: tanHalfFov.xy, z: focal in pixels (resolution aware)
uniform float uScale, uLowpass, uAlphaThr, uPointMix, uPointSize;
// per instance: TDInstanceCustomAttrib0 = P (unused, TDDeform used), 1 = scale (already exp), 2 = rot (w,x,y,z), 3 = colour+alpha
void main(){
  int i = TDInstanceID();
  vec4 col = TDInstanceCustomAttrib3(i);
  if (col.a <= 0.0) { gl_Position = vec4(2.,2.,2.,1.); return; }        // cull: outside clip
  vec3 s = TDInstanceCustomAttrib1(i).xyz * uScale;
  mat3 R = quatToMat3(normalize(TDInstanceCustomAttrib2(i)));           // (w,x,y,z) order checked by test
  mat3 M = R * mat3(s.x,0,0, 0,s.y,0, 0,0,s.z);  mat3 Sigma = M*transpose(M);
  vec3 p = P_instance;                                                   // from instance tx/ty/tz
  vec4 vp = TDCameraView * vec4(p,1.);                                   // use uTDMats[cam].cam as in ex7
  vec2 lim = 1.3*uFocal.xy; vec2 t = clamp(vp.xy/vp.z, -lim, lim)*vp.z; // clamp as INRIA
  mat3 J = mat3(f/vp.z,0,-f*t.x/(vp.z*vp.z),  0,f/vp.z,-f*t.y/(vp.z*vp.z),  0,0,0);
  mat3 T = mat3(viewRot) * J;  mat3 C = transpose(T)*Sigma*T;
  vec3 cov = vec3(C[0][0]+uLowpass, C[0][1], C[1][1]+uLowpass);
  float det = max(cov.x*cov.z - cov.y*cov.y, 1e-12);
  conic = vec3(cov.z,-cov.y,cov.x)/det;  vec2 ext = 3.*sqrt(cov.xz);   // pixels
  // NDC offset = quad corner * ext * 2 / resolution ; clamp ext to [0.5, 1024] px for sanity of the fill rate? NO limit unless Maxradius par>0
}
// fragment: power = -.5*(c.x dx^2 + c.z dy^2) - c.y dx dy; a = min(.99, col.a*exp(power)); if(power>0.||a<max(uAlphaThr,1./255.)) discard;
//           rgb *= a; fragColor = TDOutputSwizzle(vec4(rgb,a));
```
Every index into arrays/textures clamped (T-35). Use TD's own matrix helpers; the handedness / Y flip is decided by test R3 in 7.1 (single splat reference), not by guessing.

**Offline-testable logic (pure Python, `bl_splat_math.py`, pytest, no TD):** `parse_ply_header`/`load_ply` (fixtures: synthetic 3-splat ply, SHARP header copy), `load_splat` (nike first 100), `load_spz` v2 (hornedlizard header + SH byte count == n*45, positions range), `quat_to_mat3` (orthonormal, matches scipy-free reference), `cov3d`, `project_cov2d` vs finite differences of a projected unit sphere, `conic_from_cov`, `sh_eval_dc_deg1` vs closed form, `depth_keys_u16` + `radix_order` (permutation, monotonic back-to-front, ties stable, == `np.argsort(float)` except within a quantisation bin), `orbit_camera(az, el, dist, target)` -> position/forward/view matrix, `cpu_reference_raster(splats, cam, w, h)` (tile-free vectorised numpy rasteriser used as ground truth for small res), `thin_indices`, `crop_mask`, `importance_budget`.

**Live verification numbers (builder must record in LEARNINGS):**
- R1 load: `splats` equals file header (nike 270,491; hornedlizard 786,233 before crop; SHARP 1,179,648); POP bounds equal offline bounds within 1e-3 (read via `poptoTOP` + `numpyArray`).
- R2 sort: read the sorted positions, project on the camera axis: fraction of adjacent inversions <= 0.05% (Sort POP) / <= quantisation bin (cpu); re-run 200 times with the camera moving - 0 stale/torn results (T-46 style: compare each to the offline order).
- R3 single-splat reference: one splat at origin, scale 1, identity rotation, opacity 0.8, camera at z=5: centre pixel alpha = 0.8 (+-1/255), pixel at 1 sigma radius = 0.8*exp(-0.5) (+-2/255), no pixel beyond 3 sigma; swap `rot` to a 90 degree turn and check the ellipse axes swap.
- R4 scene: nike.splat 256x256 internal render vs `cpu_reference_raster`: PSNR >= 28 dB (alpha-blend order identical), `Shdegree 0`.
- R5 perf: fps and `sort_ms` at 100 k / 300 k / 1 M with `td_perf` (single reader), Sortmode sortpop vs cpu vs frozen; record cook time of Render TOP and of the Sort POP separately.
- R6 stability: 10 min orbit at 300 k, memory (`app` GPU mem) flat within 5%, no `td_errors`, no T-70-style UI crash while the controls window opens/closes 20 times.
- R7 formats: same logical scene (hornedlizard cropped to +-10) via spz and via ply conversion (offline script) renders identically within PSNR >= 35 dB.

**Mac caveats / fallbacks.** If `sortPOP` fails R2 -> `cpu` mode; if `pointfileinPOP` cannot map the attribute blocks on 31550 -> all formats through the Script CHOP path; if POP instancing of 1 quad/instance stalls above 300 k -> stack N quads per instance (ex7 `numinstances = count/256` with a Copy POP rectangle stack of 256 and `CopyId`), if instancing itself is the limit -> Path T texture-fetch with CPU `order` texture (reuse the shader, change the fetch). If MoltenVK shows flicker in the Render TOP at high counts -> render in two halves (front/back by depth) and composite. Native arm64 TD 2025.32820 is the upgrade that unlocks GSOPs/Point File In `splat` format (FUTURE).

### 7.2 `BL_cloud_morph` at `/project1/lab/BL_cloud_morph` - point-cloud viewer and morph (second build, ~5-6 h; also the safest first build to de-risk POP instancing and loading)

**Pars:** Source A/B: `Filea`/`Fileb` (ply/xyz/obj/spz-centres), `Sourcea/b` menu (file / depth image / generator: grid, sphere, torus / text), `Imagea/b` + `Deptha/b` TOP paths, `Fov`, `Znear`, `Zfar`, `Depthlohi` (auto from helper percentiles); `Count` (common N), `Match` (morton / sliced / index), `Slices` (default 8), `Morph` (0..1 manual), `Morphmode` (manual / BPM / audio / LFO), `Bpm`, `Beatsperswap`, `Ease`, `Stagger` (per-point delay by distance from centre or noise), `Arc` (curl-noise path height), `Colourmix`, `Size`, `Sizebydepth`, `Shape` (point / line / splat-iso), `Camera` as in 7.1, `Resolution`, `Opencontrols`, `Status`. No limits.

**Network:** LOAD A / LOAD B (Point File In POP or TOP-to-POP depth unprojection via `toptoPOP` with `camera`, `dispscale`, or the decoder module of 7.1) -> **MATCH** (resample both to `Count` by `thin` or repeat; order both by **Morton/Z-order code** of normalised positions, optionally refined by `Slices` rounds of sliced-optimal-transport matching: per round a random direction, sort both sets along it, pair by rank, average displacement) in Python/numpy on load (cost: Morton sort 1 M ~ 0.1 s offline order of magnitude; measure under Rosetta), stored as attribute `partner` / re-ordered arrays via Script CHOP -> `choptoPOP` -> **BLEND** (`mathmixPOP`/`glsladvancedPOP`: `P = mix(Pa, Pb, e) + arc*curl(Pa,t)*sin(pi e)`, `e = ease(clamp((Morph*(1+Stagger) - delay_i)))`, colour mix) -> **DRAW** (Geometry COMP instancing + Point Sprite/Constant MAT or Line MAT; `Sizebydepth` for DOF-like look) -> Render TOP -> `out1`. Depth sources: `camera_bridge` kind 1 client (the td-port `lib/camera_bridge.py` pattern, copied into this COMP's own DAT, 1 request in flight, newest frame wins; stored `webcam_ref_5s.mp4` for tests, no live camera unless asked) or pre-baked depth TOP.

**Offline-testable:** `unproject_depth(depth, fov, znear, zfar, lo, hi)` (round trip with a known plane/sphere), `morton_codes`, `morton_match` (permutation, equal-count, cost vs random pairing lower), `sliced_match` (energy decreases with rounds), `ease`, `stagger_delay`, `resample_to_count`.

**Live verification:** L1 `toptoPOP` unprojection of a synthetic ramp depth gives z within 1e-3 of the formula; L2 morph = 0 equals cloud A, 1 equals cloud B, per-point max error < 1e-5; L3 mid-morph centroid equals the mean of the two centroids within 1e-3; L4 3 clouds x 200 k at 30 fps target; L5 helper path: depth map for `webcam_ref_5s.mp4` frame arrives in <= 100 ms median with no queue growth; L6 `Count` change does not leak POP memory (flat after 20 changes; `freeextragpumem`).

## 8. Open questions for the user
1. May the builder test the **native arm64 TD 2025.32820** app (`/Applications/TouchDesigner.app`)? It is the build GSOPs needs, has the newer Point File In POP `splat` menu, and avoids Rosetta; T-46's open question asks the same. (Needs the user's OK; nothing launched.)
2. Spend/login gate: TDGS (~USD 30 Patreon) and GSOPs Lite (free, account) are the only polished splat tools with macOS reports; do you want them evaluated, or is the clean-room route enough? (Not downloaded.)
3. Do we allow `.splat/.spz` decode in TD's Python (numpy, no new modules) or in the native arm64 camera_bridge helper (needed for SPZ 4 / ZSTD)? Default: TD's Python for v2/v3, helper later.

## 9. MCP tool ideas
- `td_splat_info {path}`: offline header scan (no TD): format, count, SH degree, bounds, percentile outliers, memory estimate, suggested `Cropradius`/`Maxsplats` (works for .ply/.splat/.spz; uses the BL decoders).
- `td_splat_build {path, name?}` / `td_cloud_build`: build or load the saved `.tox` under `/project1/lab/`, set `File`, run the probes R1/R3, report the numbers (typed tool; same style as `td_comfy_build`).
- `td_splat_convert {in,out}`: ply <-> splat <-> spz(v2) conversion and crop, offline, so the COMP never sees a bad file.
- `td_pop_stats {path}`: POP count, bounds, attributes via a throwaway `poptoTOP` numpy read (also useful for every POP look).
- `td_sorter_probe`: runs the T-46 style stale/torn check against a Sort POP chain (generalises R2).
- Autosave link: after a verified build the tool asks the main session for `td_save_project` and `td_tox_save` (T-71 rule).

## 10. Gated items for `docs/FUTURE.md`
| Item | Gate |
|---|---|
| `pointfileinPOP` `splat` format menu (Auto/Custom/PLY/SPZ) and native `.spz` | gate on par `splat` existing / `app.build` (31550 has no such par); then drop the manual attribute blocks |
| Colour-space-aware Point File In POP (sRGB -> working space, "in development" Jul 2025) | gate on `inputcolorspace` behaviour; remove our `Srgbtolinear` par default |
| Render TOP extra image outputs from POP renders for splat depth (Watershed method; "alpha builds don't support") | gate on Render TOP outputs for POP geometry |
| GSOPs / TDGS adoption | needs TD 2025.32820+ (GSOPs), user's login/spend OK |
| SPZ 4 (ZSTD), SOG, compressed PLY, glTF KHR_gaussian_splatting loaders | needs `zstandard` in an arm64 helper or newer TD Python |
| 4D / dynamic splats (staff: not planned, Nov 2024), splat relighting, Refractive/bokeh effects | revisit after GSOPs evaluation |
| Hierarchy/LOD-trained splats (Octree-GS, LoD of Gaussians) | needs LOD files and out-of-core streaming |
| Depth/normal G-buffer for DOF on splats | as above |
| Native arm64 TD as default host | user decision (T-46 question) |

## 11. Licences (noted, not a blocker for research)
Gerritsen tox: none stated. Derivative example 7: none stated. yeataro repo: none. lakeheck repo: CC BY-NC-ND 4.0. TDGS/GSOPs: commercial / non-commercial Lite. TDFam: Apache-2.0. Niantic SPZ: MIT. SuperSplat/splat-transform: MIT. Inria 3DGS: non-commercial research [U text]. SHARP weights: Apple ML Research Licence (research/non-commercial) [S mirror]. TDDepthAnything: MIT. FreenectTD: LGPL-2.1. Depth Anything V2 Small: Apache-2.0 (camera_bridge asset). `nike.splat` (huggingface `cakewalk/splat-data`): licence unknown, kept only as a local test fixture. Nothing from these is copied into our code: shaders and decoders are re-derived from the published maths.

## 12. Files left in `research_src/BL_gaussian_splats_pointclouds/`
`samples/{hornedlizard.spz 18.1 MB, nike.splat 8.7 MB, lakeheck_README.md, spz_README.md, etch01_tutorial05_autosubs.srt}`, `yeataro_playground/*.tox` + `yeataro_expanded/` (3 sorters), `ex7/` (expanded Derivative POP splat example, 607 files), `b2bk_62516/` (zip + expanded toe), `deformer_71841/` (expanded toe), `gs69107/` (empty). Total about 27 MB + expansions. Nothing was loaded into TD or executed.
