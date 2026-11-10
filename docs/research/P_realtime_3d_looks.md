# P. Real-time 3D looks in TouchDesigner for PRISMFEST'26: chrome, gold, glass, light (16 Oct 2026)

Research agent P (Sonnet). Web + local-file research only. **No TouchDesigner probe was run, nothing downloaded, nothing
generated.** Target: TD **2025.31550** (`TouchDesigner 2.app`, Rosetta) on an Apple M1 Max (32-core GPU, 64 GB), builds at
**1080x1920**, live into Arena 7.23.2 via Syphon/NDI. Brand direction "chrome, glass and gold 3D"; full-colour PRISM logo.
Guardrails and brand rules are in `BRIEF.md` and `prism-brand/CLAUDE.md`; I do not repeat them. Things marked
**UNVERIFIED** come from a single secondary source, from memory, or are my own proposal. "Mine" = my engineering
judgement, no source.

Two limits on this file: (1) the session's web-search budget ran out mid-run, so TD-specific community tutorials for
god rays, depth of field and caustics were **not found** (listed in Open questions) and those items rest on first-party
docs plus the classic papers; (2) there is **no measured 3D cost on this machine yet** (see section 2), so every cost
cell says what is measured and what is arithmetic.

---

## 0. Summary

1. **The chrome/gold look is an environment-map problem, not a material problem.** PBR MAT metal reflects only what the
   Environment Light COMP gives it; on a dark plum scene a chrome object reads black unless the env map holds bright
   softboxes. The PBR MAT in 2025.31550 has **no IOR, transmission, clearcoat or iridescence parameter** (live par dump,
   `ops/ops_MAT_2025.31550.json`: 202 pars, none of those). So "glass" is built by other means (section 3, P3/P4).
2. **Best first build: a brand-coloured procedural equirect environment** (plum base, orchid/pink softboxes, a gold strip),
   built from TOPs, feeding an Environment Light COMP. Zero licence exposure, animatable, matches the palette. Poly Haven
   studio HDRIs (CC0) are the photographic alternative; two are close to PRISM's colours (section 3, P2).
3. **No hardware ray tracing and no RTX path on this Mac.** TD's own docs: hardware ray tracing "is currently not supported
   on MacOS", and it only exists for POP ops (Ray POP, GLSL POP), never the Render TOP. Apple's own newsroom puts hardware
   ray tracing first on the M3 family, so the M1 Max has none. Everything here is rasterised or raymarched.
4. **Macs have a hard GPU-timeout.** A Derivative forum reply (25 May 2026, M1 Max, Tahoe 26.5): a Blur TOP at 5906x4169
   killed TD with a "Vulkan Device Error" because the op ran past the OS GPU timeout, which "can't be raised on macOS".
   A second thread reports intermittent Vulkan Device Errors on **build 2025.31550** itself (MacBook Pro M4). At 1080x1920
   (2.07 Mpx, 1/10.4 of the 7488x2880 wall) heavy shaders are far from that limit, but long raymarch loops must be budgeted.
5. **Dispersion must be palette-limited.** The user rejected rainbow and the "Liquid Spectrum" family (L-16, D4); only
   orchid / pink / gold refraction is on-brand. Build dispersion as a per-channel offset whose spectrum is **remapped
   through a three-stop brand ramp**, never red-green-blue.
6. **The logo never goes through 3D materials.** Brand hard rules and `pop-concert-styles.md` forbid chroming, glowing,
   rotating or outlining the mark; a chrome or glass triangle may exist only as labelled **decor**. Logo = flat, unlit,
   composited last (or the existing HyperFrames overlays in Arena). Section 3, P10.
7. **User-taste filter on everything below:** approved house looks are "soft, glowing, organic light"; denied are
   "hard/graphic (shards, blades, neon rings, laser rays, caustic net, chroma band)" and "no caustics/liquid chrome for NN
   and AH" (`C_pf26_fit.md` §1 quoting STATES.md and AS_directions.md). So caustics and hard beams rank last; soft haze,
   soft chrome and slow glass rank high. Generic abstract CGI was also rejected (v1).
8. **Ranked top 10 for PF26** is in section 4. Order: procedural brand env map, PBR chrome/gold hero objects, HDR finishing
   chain, instanced facet wall, palette-limited fake dispersion, soft beams and haze, tall-frame camera rig, cheap DOF and
   depth fog, raymarched hero for stings only, projector-map caustics only on request.

---

## 1. Findings table

Cost classes are mine and scale with section 2. L light, M medium, H heavy (per-pixel loops). "State" uses the PF26 banks
(Ident / Hold / Safe / Artist / Moments). "Brand fit" = against the user-taste filter in Summary 7.

| ID | Item | Look | Core TD chain | Cost class at 1080x1920 | Mac / licence flags | Brand fit |
|---|---|---|---|---|---|---|
| P1 | PBR chrome + gold objects | Slow-turning polished prisms/triangles, reflecting soft studio light | Geometry COMP + PBR MAT + Environment Light COMP + Camera + Render TOP | M | No RT; Env prefilter cost; PBR ignores custom instance attrs | High if soft; chrome on logo forbidden |
| P2 | Environment maps | What chrome/gold/glass reflect | Procedural TOP equirect (or Poly Haven .exr) > Environment Light COMP (+ PreFilter Map TOP) | L (static) / M (animated) | Poly Haven CC0; `.hdr` support in Movie File In **unverified**, `.exr` listed | Enabler |
| P3 | Fake glass: refraction + dispersion | Translucent slabs/prism bending a backdrop, brand-spectrum fringe | Render TOP(s) > GLSL TOP (per-channel UV offset) > Add > Bloom; or Displace-TOP trick | M | Pure TOP/GLSL, Vulkan 430/460 | High if palette-limited |
| P4 | SDF raymarching (true refraction/dispersion) | Hero glass/gold form, true bending, gyroid/blob | GLSL TOP raymarcher, or RayTK (`raymarchRender3d`) | H | MoltenVK compile/timeouts; RayTK CC BY 4.0, Mac **unverified** | Stings only |
| P5 | Volumetric light, god rays, haze | Soft shafts through haze | Post radial-blur (GLSL) / additive cone geometry / Camera COMP fog | L (post) to H (true volumetric) | No built-in volumetric light (Derivative workshop page) | High if soft; hard laser rays denied |
| P6 | Depth of field, depth fog | Scale and depth cue | Render TOP > Depth TOP > mask > Blur TOP (pre-shrink); Camera fog | L-M | No DOF-named op in the 2025.31550 dump | Fits |
| P7 | Bloom, tone map, AA, grain | The "glow" finish on all of the above | Render (16-bit float) > Bloom TOP > Tone Map TOP > Anti Alias TOP > 8-bit out | L-M | Syphon is 8-bit RGBA (E §results) | Fits |
| P8 | Caustics | Dancing refracted light on a surface | Light COMP projector map fed by an animated caustic-style TOP | L-M | Shadertoy sources are non-commercial by default | **Risky: "caustic net" denied** |
| P9 | Instanced geometry walls | Fields of triangles/facets | Grid/Sprinkle SOP or POP > Geometry COMP instancing > PBR/Phong/Constant > Render TOP | M | 128-texture instancing cap on macOS; PBR ignores custom instance attrs | High (triangle = logomark) |
| P10 | 3D logo and 3D type | Logo whole, flat; type extruded | Logo: Constant MAT quad or Over TOP last. Type: Text SOP > Extrude SOP | L | Text SOP LOD ignored on Mac | Names/Urdu/numerals not TD |
| P11 | Tall vertical camera | Slow crane/dolly with parallax | Camera COMP `vertfov`, window pars, Look At | L | none | Fits |
| P12 | Matcap chrome (no env light) | Cheap chrome from a baked sphere image | GLSL MAT sampling a matcap TOP by view-space normal | L | mine, **UNVERIFIED** | Fallback |

---

## 2. Cost basis: what is measured, what is arithmetic

**Pixel arithmetic (exact).** 1080x1920 = 2,073,600 px = 2.07 Mpx. 7488x2880 = 21,565,440 px. Ratio 0.0962, i.e. a
1080x1920 frame is 1/10.4 of a wall-size frame.

**Measured on this exact machine (not 3D), from `E_live_rig.md` "Results" (agent E, clean-baseline protocol, T-42):**
- GLSL generator, 96 noise lookups per pixel: 17.0 ms at 3744x1440 (5.4 Mpx), 40.5 ms at 7488x2880, ~70-77 ms at 9984x3840;
  about 1.9 ms per Mpx once above the 16.7 ms cap, GPU-bound, linear in pixels.
- Six-op feedback loop at 7488x2880: 60 fps (8-bit), 57.8 fps (16-bit float).
- POP particle render at 7488x2880: 60 fps up to 2 M sprites; 38.6 fps at 4 M; 11.5 fps at 10 M.
- **Render TOP alone held 784.7 MB at 7488x2880 8-bit** (multisample + depth buffers); 86.3 MB per 8-bit wall-size TOP.
- 8-bit vs 16-bit float: no measurable difference except 2 fps in the feedback loop.

**Arithmetic from those (mine, linear scaling, not a measurement of any 3D look):** the same 96-lookup shader would cost
about 1.9 x 2.07 = **~3.9 ms** per frame at 1080x1920; the Render TOP buffers would be about 785 x 0.0962 = **~75 MB**
(AA level not stated in E, so treat as order of magnitude). A 30 fps show cook gives 33 ms; 60 Hz gives 16.7 ms.

**Not measured anywhere in this repo (UNVERIFIED until a clean run):** Render TOP + PBR MAT at any size; Environment Light
prefilter cost; Bloom/Blur/Tone Map TOP; instanced triangle fields; a dispersion shader; a raymarcher; Syphon/NDI out.
`td_perf` shows no GPU time on this build (T-42), so the only valid method is fps = cooked frames per wall second, run
alone in TD after a 64x64 baseline. Proposed list in Open questions. No claim in this file gives an fps for a 3D look.

Other sources on cost: Derivative's Transparency page says depth-peel OIT costs one full render per pass and "you'll only
need 3-5 passes to get an image that's acceptable" ([docs](https://docs.derivative.ca/Transparency)). SSAO TOP: "the
complexity of the scene has no bearing on how expensive it is"; run it at Half/Quarter pass resolution to cut cost
([docs](https://docs.derivative.ca/SSAO_TOP), edited 16 Nov 2021). GPU Gems 3 gives a 2007 DOF figure (1-1.5 ms at
1024x768 on a Radeon X1900 / GeForce 7900) that is far too old to extrapolate ([ch. 28](https://developer.nvidia.com/gpugems/gpugems3/part-iv-image-effects/chapter-28-practical-post-process-depth-field)); I do not use it.

---

## 3. Per-item details

### P1. PBR chrome and gold objects (Render TOP + PBR MAT)

- **Look.** Polished chrome and gold triangular prisms, facets, rings, slowly turning or drifting, lit by soft rect lights.
  Local look refs (internal mood only, copyrighted, per `concert-visuals-research/CLAUDE.md` rule 3): ref 113 chrome
  sticker-pop, 117 cyber-Y2K chrome hearts, 125 pink bubble type with gold rim
  (`~/Documents/StageLab_PrismFest/concert-visuals-research/references/113-*.jpg`, `117-*.jpg`, `125-*.jpg`;
  family notes in `pop-concert-styles.md`, `styles.json`). 125's pink-and-gold pair is already PRISM's accent pair.
- **What PBR MAT in this build offers** (live dump `ops/ops_MAT_2025.31550.json`; doc
  [PBR MAT](https://docs.derivative.ca/PBR_MAT), edited 28 Oct 2025): base colour, `metallic`, `roughness`,
  `specularlevel`, `ambientocclusion`, `envlightquality`, emit, normal/height/AO/alpha maps, rim lights, `substance`,
  `outputshader` (export to GLSL MAT), blending/depth/cull. **No IOR, transmission, clearcoat, sheen, iridescence.** The
  doc says "Simply applying alpha to an object does not make it transparent" and does not cover refraction.
  Triplanar mapping was added in 2025.30000 ([release notes](https://docs.derivative.ca/Release_Notes)).
- **Chain.** SOP shape (Circle SOP polygon, 3 divisions > Extrude SOP for a triangular prism; Torus; Tube) >
  Attribute Create SOP (`compnml`, `comptang` if a normal map is used) > Geometry COMP with PBR MAT (metallic 1,
  roughness 0.05-0.3) + Environment Light COMP + optional cone Light COMP > Camera COMP > Render TOP (16-bit float) >
  P7 finishing. Chrome = base colour near white, gold = brand gold `#FFB903` as base colour (tune by eye). For reference,
  physicallybased.info lists gold as 1.059, 0.773, 0.307 and chromium 0.654, 0.685, 0.701, **colour space not labelled
  and no licence stated** ([site](https://physicallybased.info/)); treat as a starting guess only.
- **Colour space.** PBR needs linear light. In 2025 builds the project default is `PASS_THROUGH` (not colour-correct); the
  opt-in is `project.workingColorSpace = SRGB_LINEAR`, **which needs a project save and restart to take effect**
  ([Working Color Space](https://docs.derivative.ca/Working_Color_Space), edited 28 Oct 2025). Lucas Morgan's 2020 post
  says PBR "specifically requires" linear textures and ships a GLSL tone-mapping TOP for the conversion
  ([post](https://derivative.ca/community-post/tutorial/linear-vs-gamma-pbr-render-pipelines/62871), no licence stated for
  the download). Decision for the lead: set the working colour space once, before looks are built.
- **Render TOP knobs** ([Render TOP](https://docs.derivative.ca/Render_TOP)): `antialias` (1x...32x, "higher values use
  more graphics memory"), `transparency` (sorted blending / OIT depth peel / alpha-to-coverage), `depthformat`
  (fixed24 or float32), `premultrgbbyalpha`, background alpha (set alpha 1 to see the colour, A §recipes). Release notes
  for 2025.32050 (after our build): "The low/medium/high differences did not do anything since the change to Vulkan
  graphics API in 2022", so pick aa4/aa8/aa16 by sample count only.
- **Cost.** Measured: none for PBR. Memory baseline: Render TOP 784.7 MB at 7488x2880 (section 2). Cost class M.
- **Mac limits.** No hardware RT (Summary 3). `lineMAT`/`wireframeMAT` rely on geometry shaders, which Metal lacks
  ([ops/SOP_MAT.md](ops/SOP_MAT.md) citing a 2021 forum thread); do not design neon-wire looks on them untested.
- **Licence.** TD Pro licence covers TD output; no asset needed (geometry and env map are procedural).
- **References.** [PBR MAT tutorial 16](https://derivative.ca/community-post/tutorial/pbr-material-touchdesigner-tutorial-16/71235)
  (Pao Olea, 4 Feb 2025; page gives no op chain, video only); [Irisdescent material](https://derivative.ca/community-post/tutorial/irisdescent-material-touchdesigner/71416)
  (Eusebi, 1 Mar 2025; technique not stated on the page); Derivative PBR tag
  [list](https://derivative.ca/tags/pbr) (9 posts, none about chrome/gold/HDRI).

### P2. Environment maps and HDRI

- **How the Environment Light COMP works** ([doc](https://docs.derivative.ca/Environment_Light_COMP), edited 2 Jan 2024):
  takes a sphere map (**equirectangular only** among 2D types) or a cube map; rotate X/Y/Z; quality is multiplied by the PBR
  MAT's `envlightquality`; **pre-filtering Off / Automatic / From PreFilter Map TOP**: "A pre-filtered environment map is
  expensive to create, but results in much better rendering quality"; Off suits animated maps. The
  [PreFilter Map TOP](https://docs.derivative.ca/PreFilter_Map_TOP) (edited 16 Nov 2021) outputs Diffuse or Specular maps
  that "can not have further processing done" before the light uses them and should be saved lossless.
- **Option A, procedural brand environment (recommended, mine).** Build an equirect TOP (2:1, e.g. 2048x1024, 16-bit
  float) from Ramp/Rectangle/Noise TOPs: plum `#3B132F` base, large soft rectangles in orchid `#CA47E9` and pink `#FF447F`,
  one thin gold `#FFB903` strip, values above 1.0 on the softboxes so highlights bloom. Animate by sliding the rectangles
  (prefilter Off, or prefilter Automatic on a static map and animate lights separately). No licence, exact palette, and
  "what chrome reflects" becomes a design object. Measured cost: none; shape = one small TOP chain + the prefilter.
- **Option B, Poly Haven studio HDRIs.** Licence is **CC0**: "You can use our assets for any purpose", no credit needed,
  redistributable inside your own work ([licence](https://polyhaven.com/license), fetched 16 Oct 2026). Catalogue queried
  via the public API metadata only (nothing downloaded): the Studio category has 96 HDRIs. Closest to PRISM's colours:
  - `ferndale_studio_05`: "moody pink-purple studio with high-contrast lamp and umbrella fills on an infinity cove"
    (Dimitrios Savva, Jarod Guest; up to 20480x10240). Best colour match.
  - `ferndale_studio_10`: magenta key + teal fill (teal is off-palette). `ferndale_studio_12`: neon tubes, blue-magenta.
  - `monochrome_studio_02`: octabox and two tall softboxes under a dark ceiling (Grzegorz Wronkowski; neutral, good for
    gold). `wooden_studio_09/14`: RGB LED panels on black floor (colours off-palette).
  - API file sizes for `ferndale_studio_05`: 1k `.hdr` 1.4 MB / `.exr` 5.9 MB; 2k `.hdr` 5.5 MB / `.exr` 22 MB; 4k `.exr`
    85 MB ([api](https://api.polyhaven.com/files/ferndale_studio_05)). A 2k map is ample for a reflection source.
  - Format: the Movie File In TOP page lists `.exr`; it does **not** list `.hdr` (Radiance), so `.hdr` support is
    UNVERIFIED ([doc](https://docs.derivative.ca/Movie_File_In_TOP), edited 28 May 2026). Prefer `.exr`; one-line test.
- **Colour caveat.** A coloured HDRI tints every chrome surface. The PRISM brand look needs a controlled palette, which is
  why Option A ranks first.
- **Cube map from the scene itself** (dynamic reflections): Render TOP `rendermode = cubemap` is documented; the
  Multi-Camera Rendering page lists hardware support as "Nvidia Pascal ... or AMD Polaris ... and newer" with no Apple GPU
  named, so on this Mac a cube render is probably six passes (**UNVERIFIED inference**). Static env maps avoid the question.
- **Reflections of moving objects.** MIR's 2019 post: "cube maps can be very convincing as long as you move the camera,
  but not the reflective object" ([post](https://derivative.ca/community-post/tutorial/reflections-refractions/61024)).
  An env light has the same limit (no inter-object reflections). For PF26 hero objects this is acceptable.

### P3. Fake glass: refraction and brand-limited dispersion

- **Look.** Translucent slabs/triangles that bend the plum backdrop and throw a soft orchid-pink-gold fringe. Local refs:
  122 "chromatic glass room" (spectral light through translucent slabs; `references/122-chromatic-glass-room.jpg`;
  `pop-concert-styles.md` calls it "the one family that *is* a prism" and the proposed house look). I viewed 122: its
  slabs carry full rainbow gradients, which the user's L-16 bans, so PRISM's version must use the three-colour ramp.
- **Why not PBR for glass.** No transmission/IOR (P1). Alpha-blended PBR objects need OIT or sorted draw
  ([Transparency](https://docs.derivative.ca/Transparency)): sorted blending is "very fast but labor intensive", OIT "will
  also disable ... anti-aliasing" and costs one full render per pass; alpha-to-coverage is "a hacky way". Render TOP docs:
  depth peel or OIT disables multi-camera rendering.
- **Technique 1: normal/UV displacement (cheap, recommended).** Render the background (Render TOP A). Render the glass
  slabs to a buffer that stores view-space normals or a UV offset (Render TOP B with a Constant/GLSL MAT, or MIR's
  pre-computed UV map). A GLSL TOP samples A at `uv + offset * k_c` per channel with three slightly different strengths
  (IOR ratios). MIR's own method: Carlos Garcia's Displace TOP approach + a Threshold TOP on alpha instead of a second
  render pass, "the sleight of hand that hints at refraction, but isn't necessarily true to the physics"
  ([post](https://derivative.ca/community-post/tutorial/reflections-refractions/61024), 7 Oct 2019, no perf numbers).
- **Technique 2: dispersion math (reference, not code to copy).** Maxime Heckel (24 Jan 2023, updated 14 Jun 2023; no
  licence stated on page): per-channel IOR, a short loop adding a growing offset per sample and averaging, a saturation
  restore, Fresnel rim, and a back-face pass before the front-face pass; "the per-sample loop is the main cost"
  ([article](https://blog.maximeheckel.com/posts/refraction-dispersion-and-other-shader-light-effects/)). It is WebGL;
  the idea ports to a GLSL TOP, but I did not find a TD-specific dispersion tutorial that I could open (an aggregator page
  lists "Refraction, Transparency and Dispersion: GLSL Materials in TouchDesigner" and "Glass Dispersion & Prism Cubes",
  **contents unverified**: [listing](https://baks.verde.ag/touchdesigner-glass-effect.html)).
- **Brand-limited spectrum (mine).** Do not output the three channels as R/G/B fringes. Compute one scalar dispersion
  amount per pixel (difference between sample offsets) and colour it through a 3-stop ramp orchid > pink > gold. For a
  smooth multi-band spectrum without branching, Alan Zucconi's "Zucconi6" two-bump-per-channel wavelength-to-RGB fit
  is the cheapest good one, "free to use ... as long as you credit me" (article text, no code licence stated), but its
  output is a full rainbow, so use it only to shape a ramp, not as the colour
  ([article](https://www.alanzucconi.com/2017/07/15/improving-the-rainbow-2/)). Inigo Quilez's cosine palette
  `a + b*cos(6.283185*(c*t+d))` is a one-line way to parametrise a 3-colour ramp
  ([page](https://iquilezles.org/articles/palettes/); no licence text on the page; it is a formula, write your own).
- **Cheap "fluted/reeded glass" 2D variant.** A 4.1 KB community asset, "Fractal Glass Effect" (Konstantin_I, 30 Sep 2026):
  a Ramp drives displacement and sets the number of glass divisions, a Blur softens the ramp transitions; no GLSL; no
  licence, TD version or perf stated ([post](https://derivative.ca/community-post/asset/fractal-glass-effect-touchdesigner/75431)).
  Not downloaded; rebuild from the description. It distorts an image rather than rendering 3D glass, so it suits Hold/Safe
  looks over a gradient.
- **Cost.** Measured: none. Shape: two Render TOPs + one GLSL TOP with N samples per pixel. At 1080x1920 the GLSL pass is
  a 2.07 Mpx fill-bound shader, same class as the measured noise-lookup generator (~1.9 ms/Mpx at 96 lookups, section 2).
- **Mac limits.** GLSL TOP is Vulkan/MoltenVK, `__VERSION__` 430 (460 selectable); out-of-bounds sampler/uniform array
  access can crash the whole app (`ops/TOP.md`, doc "Debugging crashes triggered by GLSL errors"; T-10, T-02).
- **Licence.** Own code; formulas above are standard; credit Zucconi if his constants are used.

### P4. SDF raymarching (true refraction and dispersion, hero forms)

- **Look.** One hero form (glass prism, gold blob, gyroid) with true internal bending. The only way to get real
  per-wavelength refraction inside TD, because PBR MAT has none.
- **Routes.**
  - *Custom GLSL TOP* (or a GLSL MAT on a Rectangle SOP quad): the Derivative-hosted series by exsstas (6 Apr 2020, ~5 h,
    advanced): Part 2 covers lighting, reflections, environment mapping and combining a raymarcher with Render-TOP
    polygon geometry; **the page does not mention refraction** ([series](https://derivative.ca/community-post/tutorial/raymarching-touchdesigner-tutorial-series/62745),
    files on GitHub `exsstas/Raymarching-in-TD`, licence not checked: UNVERIFIED).
  - *RayTK* (tekt / Tommy Etkin): node library that builds raymarch shaders from COMPs, **CC BY 4.0**
    ([repo](https://github.com/t3kt/raytk)). Operator list on [t3kt.github.io/raytk](https://t3kt.github.io/raytk/) includes
    `raymarchRender3D`, `volumetricRaymarchRender3D`, `reflectContrib`/`reflectMat`, hard/soft shadow ops, `fieldVolume`,
    `sdfVolume`, light ops. **I found no operator named for refraction or dispersion there**; B's "reflection and
    refraction" comes from a Derivative tag blurb ([tags/glsl-0](https://derivative.ca/tags/glsl-0), summary only), so
    **RayTK refraction is UNVERIFIED**. Release 0.46 (26 Aug 2025): "compatible with the TD 2025.30770 experimental build",
    threaded shader compile, image-based 2D SDF ([release](https://github.com/t3kt/raytk/releases),
    [Derivative post](https://derivative.ca/community-post/asset/raytk-v046-release/72698)); 2025.31550 is newer than
    30770 but **no source confirms RayTK on macOS/Apple Silicon**. Performance series by tekt exists as three videos
    ([post](https://derivative.ca/community-post/tutorial/optimizing-raytk-performance/68992), 11 Feb 2024; no text figures).
  - *Spectral raymarched glass reference (Shadertoy, study only).* "Diamond test" (`XdtGDj`, dispersion toggle off by
    default "because it slows compilation"), "Simple Diamond SDF" (`dsyBDD`, separate IOR per colour channel), "A Simple
    Diamond" (`sdyyRd`) ([search summary](https://www.shadertoy.com/view/dsyBDD)). **Licence:** Shadertoy default is
    CC BY-NC-SA 3.0 unless the author says otherwise (secondary sources only; the terms page returned 403 to me:
    UNVERIFIED). Non-commercial means **do not copy into a show**; reimplement from the maths.
- **TD build approach (mine).** GLSL TOP at 1080x1920 (output alpha for compositing). March budget: cap steps (e.g.
  48-64), early-out on sky, 3 refraction samples for dispersion; render at half res and upscale if over budget.
  Compile on a threaded setting (`glslMAT compilebehavior` has `threaded*` options; dump).
- **Cost.** Measured: none. Class H. **Risk beyond fps:** the macOS GPU timeout. Reported case: Blur TOP at 5906x4169 on an
  M1 Max, Tahoe 26.5, "Vulkan Device Error" and crash, reply: "taking too long for the GPU to complete" and the OS
  timeout "can't be raised" ([thread](https://forum.derivative.ca/t/vulkan-device-error-while-working-with-blur-top/991446),
  25-26 May 2026). A single dispatch at 2.07 Mpx is ~10x smaller than that case, but unbounded loops are the danger
  (TD doc: infinite loops or "a shader too slow for the GPU can crash the whole app", `ops/TOP.md`).
- **Mac limits.** MoltenVK translates SPIR-V to MSL, "the slowest step" is that conversion
  ([MoltenVK guide](https://raw.githubusercontent.com/KhronosGroup/MoltenVK/main/Docs/MoltenVK_Runtime_UserGuide.md));
  the first compile of a big shader can stall. No hardware RT.
- **PF26 use.** A hero sting only (Ident/Moments), pre-warmed, never the continuous bed.

### P5. Volumetric light, god rays, fog

- **Facts.** TD has no built-in volumetric light: Derivative's own workshop page says "some popular rendering techniques
  like volumetric lights have been impossible to achieve out of the box"; Lucas Morgan (GeoPix) taught custom GLSL on
  spot lights, Berlin, 18 Aug 2024 ([page](https://derivative.ca/workshop/volumetric-lights-touchdesigner/63131), paid;
  not attended). RayTK has volumetric ops (`volumetricRaymarchRender3D`, `lightVolume`; ops list, P4).
- **Route A: screen-space god rays (recommended for soft haze, mine from the paper).** Render emitters as bright shapes
  against occluders (black), then a GLSL TOP steps from each pixel toward the light's screen position, summing samples with
  `weight`, `decay`, `density`, `exposure`, then adds the result over the scene. This is Mitchell, GPU Gems 3 ch. 13,
  which gives **no GPU or timing figures**, notes streaking, flicker as occluders leave the screen, and recommends
  down-sampling the source ([chapter](https://developer.nvidia.com/gpugems/gpugems3/part-ii-light-and-shadows/chapter-13-volumetric-light-scattering-post-process)).
  Palette `radialBlur` exists in this build's palette (`ops/PLATFORM.md` §3.1, **never loaded on this Mac**) and is a
  possible shortcut.
- **Route B: additive cone geometry + Camera COMP fog.** Tube SOP cones with additive blending are noted in
  `ops/SOP_MAT.md` ("beams, bars, cone lasers (with additive blend)"); Camera COMP has `fog` off/linear/exp/exp2 with
  `fogdensity`, `fognear`, `fogfar`, `fogcolor*` (live dump, `ops/COMP_UI.md`). This is depth haze, not light scattering.
  Cheapest; soft; no tutorial source found.
- **Route C: Light COMP cone + shadows.** Light types point/cone/distant, shadow types off / hard 2D / soft 2D / custom,
  shadow map = extra depth-only pass; lights with `dimmer < 0.001` are skipped; **no light-count limit is stated**
  ([doc](https://docs.derivative.ca/Light_COMP), edited 2 Jan 2024). Release notes say "Fixed 'Custom Shadow Maps' not
  working correctly" in 2025.31760, so they are probably still broken in our 31550 (my inference from the note's
  date; [release notes](https://docs.derivative.ca/Release_Notes)); avoid `custom`.
- **PF26 filter.** Approved = soft glowing; denied = laser rays, blades. Keep rays wide, low-contrast, slow.
- **Cost.** Measured: none. Route A: one GLSL pass at 2.07 Mpx x N samples, same class as the noise-lookup generator.
  Quarter-res source cuts it.
- **Mac limits.** None specific; no geometry shaders for `lineMAT` beams (use cones).
- **Licence.** Own code from a published algorithm.

### P6. Depth of field and depth fog

- **Facts.** No operator in the 2025.31550 dump is named for DOF or bokeh (grep of `ops/INDEX_2025.31550.json`). The
  Camera COMP page does not mention DOF ([doc](https://docs.derivative.ca/Camera_COMP), edited 3 Apr 2024).
  The **Depth TOP** reads a Render TOP's depth ("black at the near plane, white at the far plane"), 24-bit fixed or
  32-bit float; use camera-space depth; when re-ranging with a Level TOP set it to 16/32-bit "or you lose much of the
  24-bit data" ([doc](https://docs.derivative.ca/Depth_TOP), edited 16 Nov 2021). It does not mention DOF itself.
- **Build (mine, from the papers).** Render TOP (`depthformat` float32) > Depth TOP (camera space) > Level (range around
  focus distance, 32-bit) as a blur-amount mask > composite between sharp, a **pre-shrunk** Blur TOP and a larger one.
  Blur TOP's docs: "Use Pre-shrink when the blurs are high and you want to optimize performance"; no bokeh shapes
  ([doc](https://docs.derivative.ca/Blur_TOP), edited 28 Oct 2025). Hammon (GPU Gems 3 ch. 28) uses near/far blur layers,
  warns focused objects bleed onto blurred backgrounds, and transparent surfaces take the CoC of the opaque object behind
  ([chapter](https://developer.nvidia.com/gpugems/gpugems3/part-iv-image-effects/chapter-28-practical-post-process-depth-field)),
  so glass slabs (P3) will not DOF correctly. Camera `fog` gives a cheaper depth cue (P5 B).
- **SSAO.** Needs the Render/Render Pass TOP directly upstream, Half/Quarter resolution option, cost independent of scene
  complexity ([doc](https://docs.derivative.ca/SSAO_TOP)). Useful to ground facets; irrelevant on a black void.
- **Cost.** Measured: none. Shape: mask + 2-3 blur passes on a 2.07 Mpx image; the Blur TOP timeout case in P4 was at 12x
  this pixel count with a huge kernel.
- **PF26.** Gentle: scale and depth on the facet wall, never a hard-blurred foreground over the logo area.

### P7. Bloom, tone map, anti-alias, grain (the finishing chain)

- **Bloom TOP** ([doc](https://docs.derivative.ca/Bloom_TOP), edited 26 Feb 2025): preprocess (pre-black, gamma,
  brightness) > mip-chain blend between Min/Max Bloom Radius > shaping (threshold, S-curve, fill, intensity); output can
  be "bloom with alpha" to Add over the scene; no performance notes, no HDR notes. Use `output = bloom` to preview.
- **Tone Map TOP** (in this build; pars from the live dump `ops/TOP.md`): `type` acesapprox / lottes / filmic /
  hablefilmic / reinhard / extendedreinhard / extendedreinhardlum, `exposurebias`, nits fields. The Derivative offline doc
  for it lists parameters only (no notes). Bloom needs values above 1.0 to look like light: render and bloom in
  16-bit float, tone-map, then output 8-bit. LearnOpenGL's HDR page makes the same argument ("colour values are clamped
  to 0.0-1.0 ... very bright lights turn into flat white") ([page](https://learnopengl.com/Advanced-Lighting/HDR), no licence stated).
- **Anti Alias TOP** = SMAA, screen-space, "does not need the extra memory of Render TOP anti-aliasing", no temporal
  pass ([doc](https://docs.derivative.ca/Anti_Alias_TOP), edited 16 Nov 2021). Use it instead of high Render TOP AA on
  3D passes that were not OIT.
- **Output.** Syphon is 8-bit RGBA (E); clips with alpha go out premultiplied (user memory `overlay-alpha-premultiplied`).
  Grain (Noise TOP, small amplitude) last; the feed's texture is plum + grain (B §4).
- **Cost.** Measured: none for these ops; 16-bit float vs 8-bit made no difference in compute/fill-bound tests and 2 fps in
  the feedback loop (E). Class L-M.
- **Flash limits.** A bloom that pulses with specular glints can breach `concert-visuals-research/README.md` §4 (3 flashes
  per second over 25 % of screen). Keep glints slower than ~1 Hz and check frame luma.

### P8. Caustics

- **Look.** Dancing light patterns on a floor/wall as if through water or glass. **Denied by the user** as "caustic net"
  and "no caustics/liquid chrome for NN and AH" (C §1). Include only if asked, and only as a faint, slow wash.
- **Cheap route (mine).** Light COMP **projector map**: spot or equirect projection of any TOP, with U/V/W extend and
  filtering ([doc](https://docs.derivative.ca/Light_COMP)). Feed an animated caustic-style TOP (two layers of
  Voronoi/Worley noise, thresholded and blurred, drifting in opposite directions). One extra texture in a lit pass; no
  real light transport. True caustics (photon-style accumulation) are not offered by any TD op I found and would be a custom
  multi-pass GLSL job (Class H, no source).
- **Sources.** Shadertoy caustic shaders exist, but default licence is non-commercial (P4). Evan Wallace's WebGL Water
  (caustics on a tiled pool) was in my notes but I could not read its README or licence: **UNVERIFIED**
  ([repo](https://github.com/evanw/webgl-water)). Do not copy either.
- **Cost / Mac.** Not measured; class L-M for the projector route; no Mac-specific flags.

### P9. Instanced geometry walls (facet fields)

- **Look.** A wall or field of triangles (the PRISM logomark is a triangle) in chrome, glass or gold, each with its own
  rotation/colour/phase, assembling or drifting; ref 122's slabs, B1-3 "facet assembly" in
  `concert-visuals-research/branded-look-ideas.md`.
- **Mechanism** ([Geometry COMP](https://docs.derivative.ca/Geometry_COMP), edited 26 Jun 2026): Instancing creates
  "hardware instances"; per-instance transform/colour/texture from CHOP channels, DAT columns, TOP RGBA or SOP
  attributes; instance count manual or from CHOP samples/DAT rows; zero `Active` skips an instance. Per-instance textures
  feed a PBR MAT's Base Color Map, but **custom instance attributes are ignored by the PBR MAT** (they work only in a GLSL
  MAT), and **on macOS at most 128 textures can be used at once** (16384 on Windows). POP attributes can drive instancing
  and Render TOP renders POPs and SOPs together ([Learning About POPs](https://docs.derivative.ca/Learning_About_POPs),
  edited 19 Aug 2026); the POP > Geometry COMP > Render chain was verified live in this build (A recipes, T-15; `instanceop`
  is the instance source).
- **Geometry rules** (offline doc `Optimize Geometry for Rendering`, installed with the app): triangles and triangle strips
  batch into one draw call; Circle/Tube/Sphere **`prim`** types render one batch each and "have a large CPU cost" in
  numbers; "if two SOPs share the same material ... a Merge SOP ... single batch". So: polygon triangles, instancing.
- **Chain.** Grid SOP or Sprinkle SOP (or Grid/Sprinkle POP) > CHOP/TOP-driven transforms, instance colour from a brand
  ramp > Geometry COMP (triangle prism from Circle SOP + Extrude SOP) with PBR MAT + env light (P1/P2) > Render TOP > P7.
- **Cost.** Measured, nearest: POP point-sprite render 60 fps up to 2 M sprites at 7488x2880 (sprite fill-bound), 38.6 fps
  at 4 M (E). That is sprites, not lit meshes; PBR instanced facets are **UNVERIFIED**. Class M; Render TOP buffers
  ~75 MB arithmetic (section 2).
- **Mac limits.** 128-texture cap; no geometry-shader beams; Text SOP LOD ignored (P10).
- **Licence.** None needed.

### P10. 3D logo and 3D type treatments (policy first)

- **Hard rules.** Never recolour, distort, rotate, outline or add effects (glow, shadow) to the logo; supplied PNGs only
  (`prism-brand/CLAUDE.md`, guidelines p9). `pop-concert-styles.md` line 116: "Never inflate, chrome, outline or restyle
  the PRISM logo or the PRISMFEST'26 wordmark"; a chromed mark must be labelled decor. Logos are 2084x2084 PNGs with a
  `content_bbox`; there is no vector (gap in `prism-brand/CLAUDE.md`), so tracing the PNG to extruded geometry would be a
  restyle of a raster.
- **Treatments that obey the rules (mine).**
  1. **Not in TD (recommended).** TD renders the world; the full-colour logo is composited by the existing HyperFrames
     overlays in Arena (`hyperframes/INVENTORY.md` per C §1; they own names, logos, Urdu). Zero risk.
  2. **Flat unlit quad, last.** If TD must carry it: Over TOP of the unaltered PNG after all post (bloom, grain, DOF),
     parallel to the image plane, never in the camera's perspective, no lens flare or glow touching it. Keep
     the camera's parallax and DOF masks off the logo area.
  3. **Decor object.** A chrome/glass triangle prism that is visibly a separate object near, not replacing, the logo,
     named "decor" in the look catalogue. Its shape echoes the mark without being the mark.
  4. **Reflections of the logo are forbidden** in chrome/glass (they distort and duplicate it).
- **Type.** Text SOP > Extrude SOP gives 3D lettering ("set Text SOP Output = Closed Polygons first", `ops/SOP_MAT.md`);
  **Text SOP level of detail is ignored on macOS** (forum, `ops/SOP_MAT.md` Gotcha 3), so curves can look coarse. Geo Text
  COMP renders text directly with the Slug library, "can be lit and textured with any MAT", but the page has **no extrude/
  bevel and no Urdu/complex-script information** ([doc](https://docs.derivative.ca/Geo_Text_COMP), edited 31 Dec 2025).
  Scope per DIRECTIONS: not artist names, not Urdu, not the countdown numerals (StageLab plugin); at most the whole
  campaign line "Built different." for a TD stinger, user-gated.

### P11. Camera moves for tall vertical framing

- **Camera COMP facts** ([doc](https://docs.derivative.ca/Camera_COMP), edited 3 Apr 2024): `viewanglemethod` = Horizontal
  FOV / Vertical FOV / Focal Length and Aperture; with aperture the doc gives `aperture_y = resy/resx * aperture_x`, so a
  portrait render widens the vertical field automatically. Projection: perspective / ortho / persp-ortho blend / custom
  matrix (must use the Vulkan 0..1 depth range). Window X/Y/Size/Roll "as though you are panning the camera without
  actually moving the camera" (no lens-shift wording). `lookat` + up-vector options. Reduce near-to-far range for z-fight.
- **Framing (mine).** For 1080x1920 set `viewanglemethod = vertfov` (30-40 degrees reads natural; very wide FOV bends
  facets at the edges). Hero in the central third (the 9:16 look is later cut to R02's 576x2880 faces per DIRECTIONS §1,
  1:5, so side thirds get cropped; confirm with C §2). Moves that suit a tall frame and flash limits: slow **vertical
  crane** (camera `ty`) with Look At on the hero; slow **dolly-in** (`tz`) with a matching FOV compensation; **orbit
  <= ~10-15 degrees** for parallax; **window X/Y drift** for a no-parallax "float". Avoid fast lateral moves and spins
  (specular glints sweep and flicker).
- **Ortho.** `ortho` with `orthowidth` for a flat, perspective-free facet wall, which also keeps a logo plane
  undistorted if it must sit inside the scene (still prefer P10-2).
- **Cost.** Zero.

### P12. Matcap chrome (fallback, mine, UNVERIFIED in TD)

A "matcap" bakes lighting into a sphere image sampled by view-space normal. In a GLSL MAT it needs no Light or
Environment Light COMP, no prefilter, one texture fetch, and is a standard real-time technique, but the reflection is
camera-locked and cannot show a changing environment. No TD source found; treat as an idea if P1 proves too heavy.

---

## Mac limits (consolidated, build 2025.31550 unless stated)

| Limit | Evidence |
|---|---|
| **No hardware ray tracing, no RTX path.** Only Ray/Sprinkle(volume)/GLSL/GLSL Advanced **POP** use it; Mac excluded; a Derivative staff reply (forum) says the hardware supports it but MoltenVK does not (search summary, **UNVERIFIED wording**). Render TOP has no RT mode. M1 family predates "hardware-accelerated ray tracing comes to the Mac for the first time" with M3 | [HW Ray Tracing doc](https://docs.derivative.ca/Hardware_Ray_Tracing) (edited 14 Jan 2026); [Apple newsroom, 30 Oct 2023](https://www.apple.com/newsroom/2023/10/apple-unveils-m3-m3-pro-and-m3-max-the-most-advanced-chips-for-a-personal-computer/) (does not name M1) |
| Graphics API = Vulkan, on macOS via MoltenVK over Metal; GLSL 430 default, 460 selectable | T-10; [Release notes](https://docs.derivative.ca/Release_Notes); [MoltenVK guide](https://raw.githubusercontent.com/KhronosGroup/MoltenVK/main/Docs/MoltenVK_Runtime_UserGuide.md) |
| Geometry shaders unsupported on Metal (Line MAT risk) | `ops/SOP_MAT.md` (forum 2021, OpenGL era); [derivative.ca/solr/vulkan](https://derivative.ca/solr/vulkan) (search summary, UNVERIFIED) |
| **GPU timeout cannot be raised on macOS**; one op too long = "Vulkan Device Error" crash | [forum, 25 May 2026, M1 Max](https://forum.derivative.ca/t/vulkan-device-error-while-working-with-blur-top/991446) |
| Intermittent Vulkan Device Errors reported on **2025.31550**, MacBook Pro M4, cause unknown | [forum thread](https://forum.derivative.ca/t/vulkan-device-error-followed-by-fatal-error-message-on-m4-pro/821807) |
| Our own TD crashed twice on 16 Oct (SIGSEGV 18:42, fatal 19:10), cause not established | `STATUS.md` open item 5 |
| Multi-camera rendering (cube map in one pass) lists only Nvidia Pascal+ / AMD Polaris+ | installed offline doc `Multi-Camera_Rendering.htm` in the app bundle (edited 1 Jun 2021) |
| Instance texturing: max 128 textures on macOS | [Geometry COMP](https://docs.derivative.ca/Geometry_COMP) |
| Text SOP level of detail ignored on macOS | `ops/SOP_MAT.md` Gotcha 3 |
| Render TOP AA menu levels (low/med/high) did nothing since the 2022 Vulkan switch | Release notes 2025.32050 (after our build) |
| Substance TOP GPU engine uses Metal on macOS; Apple Silicon not stated | [doc](https://docs.derivative.ca/Substance_TOP), edited 22 Aug 2026 |
| TD runs under Rosetta (x86_64); GPU work is not CPU-limited in measured generators, Python-heavy ops are slower | E; A §2 |

## Licence table

| Thing | Licence / terms | Evidence |
|---|---|---|
| Poly Haven HDRIs | **CC0**, any purpose, no credit, redistributable; covers assets only, not the site | [polyhaven.com/license](https://polyhaven.com/license) |
| RayTK | **CC BY 4.0** (credit tekt) | [repo](https://github.com/t3kt/raytk) |
| Shadertoy shaders | default CC BY-NC-SA 3.0 unless the author states otherwise (secondary sources; terms page 403) | UNVERIFIED; study only |
| Alan Zucconi rainbow constants | "free to use ... as long as you credit me"; no code licence stated | [article](https://www.alanzucconi.com/2017/07/15/improving-the-rainbow-2/) |
| Maxime Heckel dispersion article | no licence stated; use the idea, write own shader | [article](https://blog.maximeheckel.com/posts/refraction-dispersion-and-other-shader-light-effects/) |
| Inigo Quilez palette formula | no licence text on the page; a formula | [page](https://iquilezles.org/articles/palettes/) |
| physicallybased.info values | no licence stated | [site](https://physicallybased.info/) |
| GPU Gems 3 algorithms | NVIDIA book chapters; implement from the description, do not copy code | chapters above |
| Community TD assets (Fractal Glass, PBR posts) | none stated; do not download or redistribute | pages above |
| TD built-in ops, palette, snippets | TD Pro licence (Pro on `TouchDesigner 2.app`, A §1) | `DIRECTIONS.md` §1 |

---

## 4. Ranked recommendations for PF26 (top 10)

Ranking = brand fit and user-taste filter first, then risk on this Mac, then cost. All are live-capable at 1080x1920 in
principle, but **none has a measured cost**; the first Gate is a measurement run (Open questions 1).

| # | Item | Why it ranks here | Good for | Guard |
|---|---|---|---|---|
| 1 | **P2 Brand procedural env map** (Option A) | Everything chrome/gold/glass depends on it; palette-exact; no licence; cheap | all 3D looks | high values on softboxes; prefilter Off if animated |
| 2 | **P1 PBR chrome/gold hero objects** (prism/triangle forms) | The literal "chrome, glass and gold 3D"; slow turns suit soft glow | Ident, Hold, Moments | no logo chroming; flash-check glints; set working colour space once |
| 3 | **P7 Finishing chain** (float render > Bloom > Tone Map > SMAA > grain > 8-bit) | Makes 1, 4, 5 read as light, not CGI; adds the feed's grain | every 3D look | bloom pulses slower than 1 Hz |
| 4 | **P9 Instanced triangle-facet wall** | Logomark shape as the instance; the house-look glass wall (ref 122); hardware instancing | Hold, Safe, Ident | 128-texture cap; no `prim` primitives |
| 5 | **P3 Fake dispersion glass**, ramp-limited to orchid>pink>gold | The prism concept in the cheapest form; loop-friendly | Ident, Moments | never R/G/B fringes; L-16 "no rainbow" |
| 6 | **P5 Soft beams / haze** (GPU Gems god-ray post + Camera fog) | Soft light is the approved register; cheap if quarter-res | Ident, Hold | wide and slow; hard laser rays denied |
| 7 | **P11 Tall-frame camera rig** | Free; defines how every look moves; vertical FOV and central-third rule | all | thirds get cropped on R02 faces; slow moves only |
| 8 | **P6 Cheap DOF + depth fog** | Scale and depth on the facet wall | Hold, Ident | glass will not DOF correctly; keep logo area sharp |
| 9 | **P4 Raymarched hero** (custom GLSL TOP; RayTK optional) | Only route to true refraction; hero sting | Moments, Ident stings | step caps, pre-warm shader, macOS GPU timeout, RayTK on Mac unverified |
| 10 | **P8 Projector-map caustics** | Cheap to try but on the user's denied list | only if the user asks | faint/slow; "caustic net" denied |

Not ranked: P10 (policy, not a look: logo stays flat and unlit, ideally HyperFrames' overlay), P12 (fallback idea).

**Suggested first two builds when the user says go (proposals, nothing built):** (a) a "Chrome Prism Hold": P2-A env +
P1 triangular prisms + P7 + P11 slow crane; (b) the P9 facet wall variant with P3 dispersion on a few slabs. 3 ideas per
round, then wait (DIRECTIONS §5).

---

## Open questions for the lead

1. **Measure before promising.** One clean run (alone in TD, 64x64 baseline first, T-42) at 1080x1920 of: (a) Render TOP +
   PBR MAT sphere, env prefilter Automatic vs Off, aa4 vs aa8 vs aa16; (b) 20k and 100k instanced triangles; (c) Bloom +
   Tone Map + SMAA; (d) a GLSL dispersion pass with 3 and 8 samples; (e) a 64-step raymarcher; (f) memory per Render TOP.
   Whose go-ahead and who runs it? I did not touch TD.
2. **Working colour space.** Set `SRGB_LINEAR` (needs save + restart) for all PBR looks, or keep `PASS_THROUGH` and
   convert by hand? It affects every look and the show framework's saved project.
3. **Env map source.** Procedural brand env (my pick) or a Poly Haven CC0 HDRI such as `ferndale_studio_05`? If HDRI, OK
   to download one 2k `.exr` (22 MB) for a test? Also confirm `.hdr` loading, or use `.exr`.
4. **Taste gate.** Is soft chrome/gold "generic abstract CGI" (rejected, v1)? Chrome and glass have not yet been shown to
   the user in 3D; D4/L-16 and the denied list make the first round a risk. Which acts should see it first?
5. **Dispersion palette.** Confirm orchid > pink > gold only, no blue/green, no white fringe.
6. **Logo handling.** Confirm: TD never carries the logo; Arena composites the HyperFrames overlay. Any TD-side logo use
   (flat quad) needs a rule on where it sits.
7. **RayTK on this Mac.** No source confirms macOS/Apple Silicon or refraction ops. Test needs a download (user's OK +
   `AUDIT.md`), so park until a hero sting is actually requested.
8. **Stability.** Two TD crashes today (STATUS item 5) and a reported 2025.31550 Vulkan Device Error on M4: should 3D looks
   run only with the watchdog up, and is there a go/no-go on lowering Render TOP AA and prefilter to cut risk?
9. **Not found (search budget exhausted):** TD-specific tutorials for god rays, DOF and caustics; Interactive &
   Immersive HQ "up your render quality" (page body truncated on fetch); Derivative's `Experimental` shadow/PBR notes
   beyond the offline doc. A later pass could fetch those.
10. **Tall frame vs R02 faces.** Confirm how a 1080x1920 look is cropped/mapped to the 1:5 side faces (C §2) so camera
    framing keeps the hero inside the safe third.

## Sources

Derivative docs (fetched 16 Oct 2026): [PBR MAT](https://docs.derivative.ca/PBR_MAT), [Environment Light COMP](https://docs.derivative.ca/Environment_Light_COMP),
[Render TOP](https://docs.derivative.ca/Render_TOP), [Bloom TOP](https://docs.derivative.ca/Bloom_TOP),
[Transparency](https://docs.derivative.ca/Transparency), [Light COMP](https://docs.derivative.ca/Light_COMP),
[PreFilter Map TOP](https://docs.derivative.ca/PreFilter_Map_TOP), [SSAO TOP](https://docs.derivative.ca/SSAO_TOP),
[Hardware Ray Tracing](https://docs.derivative.ca/Hardware_Ray_Tracing), [Release Notes](https://docs.derivative.ca/Release_Notes),
[Working Color Space](https://docs.derivative.ca/Working_Color_Space), [Camera COMP](https://docs.derivative.ca/Camera_COMP),
[Geometry COMP](https://docs.derivative.ca/Geometry_COMP), [Geo Text COMP](https://docs.derivative.ca/Geo_Text_COMP),
[Depth TOP](https://docs.derivative.ca/Depth_TOP), [Movie File In TOP](https://docs.derivative.ca/Movie_File_In_TOP),
[Blur TOP](https://docs.derivative.ca/Blur_TOP), [Anti Alias TOP](https://docs.derivative.ca/Anti_Alias_TOP),
[Render Simple TOP](https://docs.derivative.ca/Render_Simple_TOP), [Learning About POPs](https://docs.derivative.ca/Learning_About_POPs),
[Substance TOP](https://docs.derivative.ca/Substance_TOP). Installed offline docs (read from
`/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/Learn/OfflineHelp/https.docs.derivative.ca/`, read-only):
`Optimize_Geometry_for_Rendering.htm`, `Multi-Camera_Rendering.htm`, `Experimental-Tone_Map_TOP.htm`,
`PBR_MAT.htm` (grep for refract/transmission/IOR/clearcoat/iridescence: none).

Derivative community and forum: [Reflections & Refractions (MIR)](https://derivative.ca/community-post/tutorial/reflections-refractions/61024),
[Volumetric Lights workshop](https://derivative.ca/workshop/volumetric-lights-touchdesigner/63131),
[Fractal Glass Effect](https://derivative.ca/community-post/asset/fractal-glass-effect-touchdesigner/75431),
[Glass Material and Distance Light](https://derivative.ca/community-post/tutorial/glass-material-and-distance-light/65190)
(tormozgh, 28 Aug 2021, beginner, Persian; MAT and settings not given),
[Linear vs Gamma in PBR](https://derivative.ca/community-post/tutorial/linear-vs-gamma-pbr-render-pipelines/62871),
[How to make a better look using PBR](https://derivative.ca/community-post/tutorial/how-make-better-look-using-pbr/62865)
(Kohui, 11 May 2020; video and Patreon only), [PBR tutorial 16](https://derivative.ca/community-post/tutorial/pbr-material-touchdesigner-tutorial-16/71235),
[Irisdescent material](https://derivative.ca/community-post/tutorial/irisdescent-material-touchdesigner/71416),
[Advanced Kinect Rendering](https://derivative.ca/community-post/tutorial/advanced-kinect-rendering-instancing-pbr-depth-refinement-shadows-and-more)
(prismatic, 17 Mar 2025; no PBR/perf detail on page), [Abstract 3D sculpture](https://derivative.ca/community-post/tutorial/abstract-3d-sculpture/65117),
[Raymarching series](https://derivative.ca/community-post/tutorial/raymarching-touchdesigner-tutorial-series/62745),
[Optimizing RayTK performance](https://derivative.ca/community-post/tutorial/optimizing-raytk-performance/68992),
[RayTK 0.46](https://derivative.ca/community-post/asset/raytk-v046-release/72698),
[RayTK masses](https://derivative.ca/community-post/asset/raytk-raymarching-masses/63620) (2020, v0.9, TD 2020.44350),
tags [pbr](https://derivative.ca/tags/pbr), [glass](https://derivative.ca/tags/glass), [volumetric](https://derivative.ca/tags/volumetric),
forum [Blur TOP Vulkan Device Error](https://forum.derivative.ca/t/vulkan-device-error-while-working-with-blur-top/991446),
[M4 Pro Vulkan error](https://forum.derivative.ca/t/vulkan-device-error-followed-by-fatal-error-message-on-m4-pro/821807),
[Vulkan tag](https://forum.derivative.ca/tag/vulkan).

RayTK: [github.com/t3kt/raytk](https://github.com/t3kt/raytk), [releases](https://github.com/t3kt/raytk/releases),
[t3kt.github.io/raytk](https://t3kt.github.io/raytk/).

Assets and external: [Poly Haven licence](https://polyhaven.com/license), [Poly Haven API](https://api.polyhaven.com/assets?t=hdris&c=studio)
(metadata only, queried 16 Oct 2026), [physicallybased.info](https://physicallybased.info/),
[MoltenVK guide](https://raw.githubusercontent.com/KhronosGroup/MoltenVK/main/Docs/MoltenVK_Runtime_UserGuide.md),
[Apple M3 newsroom](https://www.apple.com/newsroom/2023/10/apple-unveils-m3-m3-pro-and-m3-max-the-most-advanced-chips-for-a-personal-computer/),
[GPU Gems 3 ch. 13](https://developer.nvidia.com/gpugems/gpugems3/part-ii-light-and-shadows/chapter-13-volumetric-light-scattering-post-process),
[GPU Gems 3 ch. 28](https://developer.nvidia.com/gpugems/gpugems3/part-iv-image-effects/chapter-28-practical-post-process-depth-field),
[Maxime Heckel](https://blog.maximeheckel.com/posts/refraction-dispersion-and-other-shader-light-effects/),
[Alan Zucconi](https://www.alanzucconi.com/2017/07/15/improving-the-rainbow-2/),
[Inigo Quilez palettes](https://iquilezles.org/articles/palettes/),
[LearnOpenGL HDR](https://learnopengl.com/Advanced-Lighting/HDR), [LearnOpenGL diffuse irradiance](https://learnopengl.com/PBR/IBL/Diffuse-irradiance),
Shadertoy [Simple Diamond SDF](https://www.shadertoy.com/view/dsyBDD) and search results (pages returned 403 to fetch;
descriptions from search summaries), [evanw/webgl-water](https://github.com/evanw/webgl-water),
glass-title aggregator [baks.verde.ag](https://baks.verde.ag/touchdesigner-glass-effect.html) (contents unverified).

Local files used: `jazib-td-mcp/docs/research/` `BRIEF.md`, `README.md`, `DIRECTIONS.md`, `B_visual_techniques.md`,
`C_pf26_fit.md`, `E_live_rig.md`, `ops/SOP_MAT.md`, `ops/TOP.md`, `ops/COMP_UI.md`, `ops/PLATFORM.md`,
`ops/ops_MAT_2025.31550.json`, `ops/INDEX_2025.31550.json`; `jazib-td-mcp/STATUS.md`, `LEARNINGS.md`;
`concert-visuals-research/pop-concert-styles.md` and `references/113,117,122,125`; `prism-brand/CLAUDE.md`;
`prismfest26-show/production/LEARNINGS.md` (L-16).
