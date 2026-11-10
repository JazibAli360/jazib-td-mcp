# V - Real TD tutorials for visual craft with built-in operators (web research, 26 Oct 2026)

Scope: feedback / TOP compositing, instancing, POPs, 3D rendering, ParticlesGPU, point typography. Nothing was run in TD,
nothing downloaded or installed. Target build **2025.31550, macOS** (`../../LEARNINGS.md` T-nn wins over this file).
Tags: **[V]** = read this session on the cited derivative.ca / docs.derivative.ca / learn.derivative.ca page or in the
local 31550 op dump (`ops/ops_*_2025.31550.json`); **[S]** = seen only in a search snippet or a third-party page;
**[U]** = my reconstruction from general TD practice, not seen in the source. Read this first (the honest limits):

## 1. Summary

- **What I could and could not get.** Every tutorial below exists (title, author, date, URL read on its derivative.ca post
  [V]). But those posts are 1-3 sentence teasers: the build itself is only in the YouTube video or a Patreon file. I could
  not read video transcripts and YouTube pages returned nothing, so **no video length is known** ("n/s" = not stated, for every
  row) and **operator chains are mostly [U]** (named from the post's own tag list where it gave one, otherwise rebuilt from the
  operator docs). Par names in the recipes are different: they come from the 31550 dump [V], so they are real on our build.
- **Best free, text-backed sources** (chains readable without video): Derivative's own wiki pages for Particle / Force Radial /
  Feedback / Trail / Ray / Proximity / Projection POP, Time Machine / Texture 3D / SSAO / Render Pass TOP, Environment Light
  COMP (all read [V], used in the recipes) and the learn.derivative.ca lessons (100: 102 TOPs, 104 rendering, 109 POPs; 200: 201
  instancing, 202 TOPs). The lessons ship an example `.tox` per topic ("Load Example") - the single best thing to open in TD.
- **The tutorial boom is 2025-26 POPs**: the elburz / Interactive & Immersive HQ channel posts one POP video every 1-2 weeks
  (Derivative's tutorials page, 58 pages). Derivative + Sudo Magic released an 11-lesson POPs series (recorded by Matthew Ragan,
  12 May 2026 [V]). Bileam Tschepe (elekktronaut), Dean Cheesman, polyhop, pao.olea and audiodevout all post POP/feedback/
  instancing work with Patreon files.
- **Build floor warning.** Several 2026 tutorials target newer builds than 31550. In our dump **Trace POP, Text POP, Voronoi POP
  do not exist** (Trace POP tutorial, Voronoi-sphere tutorial are out); Projection POP, Ray POP, Trail POP, Proximity POP, Extrude
  POP, TOP to POP, Feedback POP, Force Radial POP, Noise POP, Lookup Texture POP **do** exist [V]. The polyhop Projection POP
  tutorial says it was made on 2025.32460 [V]; the wiki documents up to 2025.33230 (T-33). Expect renamed/extra pars.
- **Mac/platform flags.** Optical Flow TOP, Nvidia Flow/Flex (audiodevout's Flex tutorial), Kinect/ZED/Body Track are
  Windows-or-hardware-bound (T-18; Kinect-on-Mac via FreeNect exists in a dcheesman post but T-18 says native ops are
  unsupported here). Feedback POP with a Null target crashed macOS in 2025.32260 (fixed 32280, 31550 unverified, T-35):
  build POP loops one structural change per call + `td_errors`.
- **Authors checked.** Real and found: elburz / Interactive & Immersive HQ (Elburz Sorkhabi; presenters Jack DiLaura, Crystal
  Jowperson, Marco, Joel, Christian, Scott Mann), Matthew Ragan (POPs lessons, Pristine Rendering course), Bileam Tschepe /
  elekktronaut, Dean Cheesman (dcheesman), Simon Alexander-Adams (polyhop), pao.olea (Pao Olea), audiodevout, a.melv, Paketa12
  (YouTube @paketa12, one video title confirmed: "linear interpolation in Touchdesigner"; date and other titles not found),
  Supermarket Sallad (okVJ, Patreon only; no tutorial title found), Acrylicode (YouTube + Gumroad; no 2025-26 title found),
  PPPANIK (Patreon only; titles seen without years). **Not found / not verified:** Noones Img, SimpleTD, The NAM Project,
  Torin Blankensmith (derivative.ca user `blankensmithing` posted a 2025 watercolor hand-tracking brush; I did not confirm that
  account is Torin), Dan Molnar, Kevin Moon (not searched). None are listed as tutorials below.
- **Ranked recipes (section 3)** are for 1080x1920 LED/concert looks. Top picks: edge-feedback tunnel, Particle POP curl field,
  instanced PBR chrome field, a render-polish chain. Everything in them uses ops present in 31550.

## 2. Tutorial table (40 rows, about 50 videos/lessons)

Columns: tutorial - author - posted | URL | what it teaches + chain | 31550/Mac note | MCP can reproduce?
Base for `d:` = https://derivative.ca/community-post/ ; `L:` = https://learn.derivative.ca/courses/ ; YouTube IDs are the video.
All lengths n/s. "chain [U]" = rebuilt, not read from the source.

### 2a. POPs (GPU points; 2025 family)

| # | Tutorial - author - date | URL | Teaches / chain | Compat | MCP? |
|---|---|---|---|---|---|
| 1 | POPs: Working with Points (11 lessons: fundamentals, attributes, math, fields, Noise POP, Feedback POP, color, Copy POP, line metrics, Point File In, particles) - Derivative + Sudo Magic, rec. Matthew Ragan - lessons announced 12 May 2026 [V] | L:100-fundamentals/lessons/109-pops-working-with-points/ ; d:new-pops-lessons-learnderivativeca/74561 | Official intro. Names Attribute, Pattern, Math/Math Mix/Math Combine, Noise, Feedback, Copy, Line Smooth/Break/Metrics, Point File In POPs. No chain text on page; each topic has an example .tox | Official; 2026 so may use post-31550 pars | yes: open each example .tox via `td_tox_load`, then read it with `td_list`/`td_get_pars` |
| 2 | Wavy Particle Systems using POPs - elburz (I&I HQ) - 17 Nov 2025 [V] | d:tutorial/wavy-particle-systems-touchdesigner-using-pops/73315 | Particle POP + Math Mix POP basics. chain [U]: Point Generator/Grid POP -> Particle POP -> Math Mix POP (sine on P/PartForce) -> Null POP (= targetpop) -> Geometry COMP -> Render TOP | Official 2025.3x; fine | yes (parts known from T-15) |
| 3 | TouchDesigner POPs: Exploding Particles (Crystal) - elburz - 21 Jul 2025 [V] | d:tutorial/touchdesigner-pops-exploding-particles/72444 ; yt iTe-2B764vg | Intro to POPs; "use POPs to instance translate, rotation, scale"; particle explosion. chain [U]: sphere points -> Particle POP (high birth, damping) -> Force Radial/Noise -> Geometry COMP instancing | Jul 2025 = pre-official; par names may differ | partly (instance pars known: T-15) |
| 4 | Extra Forces and Smoky Particles in TouchDesigner - Derivative forum - 12 Nov 2025 [V title/date only] | forum.derivative.ca/t/extra-forces-and-smoky-particles-in-touchdesigner-tutorial-2025-11-12/845256 | Page says nothing about content; likely Force Radial POP stacking + feedback smoke [U] | unknown | partly (Force Radial pars [V], see recipe 2) |
| 5 | Audio Reactive Particles using TouchDesigner POPs - elburz - 19 Oct 2026 [V] | d:tutorial/audio-reactive-particles-using-touchdesigner-pops/75525 ; yt 4shfXcXvLDk | Particle POP, attributes -> "sparking" system, audio drive. chain [U]: Audio Device In -> Analyze/Math CHOP -> CHOP to POP or Particle POP birth/ force pars | Oct 2026 (newer than our build) | partly: audio CHOP side fine (see K_audio_reactive.md) |
| 6 | Audio Reactivity with Basic POPs (Joel) - elburz - 17 Aug 2026 [V] | d:tutorial/audio-reactivity-basic-pops/75196 ; yt XTIh2jwM_UY | Proximity POP -> audio-reactive line geometry. Pars [V]: `maxdist`, `maxlinesperpoint`, `output` | ok on 31550 | yes (recipe 5) |
| 7 | Generative Starry Night in TouchDesigner (Crystal Jowperson) - elburz - 3 Sep 2026 [V] | d:tutorial/generative-starry-night-touchdesigner/75286 ; yt 23UbM0XbcBA | Van Gogh-style swirl with POPs; chain not given [U] (likely Noise POP curl on points + Trail/Line) | 2026 build? | partly |
| 8 | Working with POP Normals in TouchDesigner - elburz - 20 Sep 2026 [V] | d:working-pop-normals-touchdesigner/75381 (full text on interactiveimmersive.io, could not be read) | Normals on POPs for shading/displacement | Normal POP exists in 31550 [V] | partly |
| 9 | AURA FLOW [34] - pao.olea - 20 Oct 2026 [V] | d:tutorial/aura-flow-touchdesigner-tutorial-34/75535 ; yt qBBll7HmCqc | Trail shaped with POPs, color along its length from attributes, material, motion, lights, post. Intermediate. chain [U]: Particle/Line POP -> Trail POP -> Lookup Texture/ Math Mix color -> Line MAT/PBR -> Render -> post | Likely ok (Trail POP pars [V]) | partly |
| 10 | Surface Trails on any Geometry using POPs - elburz (Jack DiLaura) - 2 Feb 2026 [V] | d:tutorial/surface-trails-any-geometry-using-touchdesigner-pops/73881 ; yt ljGcFkMxBPg | Ray POP keeps particles/trails on a mesh: prepare geometry, configure Ray POP, inject movement, trails | Ray POP exists [V] | yes (recipe 11; Ray pars [V]) |
| 11 | Particle Collisions with Ray POP - elekktronaut - 24 Apr 2026 [V] | d:tutorial/particle-collisions-ray-pop/74455 ; yt X6RgNdsYMLA | Particles bounce off collision objects, 2 examples (Patreon file). Ray POP input 1 = collision tris; `numbounces`, `doreflectedray` [V] | Ray POP ok | partly |
| 12 | 3D Particles from 2D Textures - elburz (Jack DiLaura) - 29 Jan 2026 [V] | d:tutorial/touchdesigner-3d-particles-2d-textures/73861 ; yt q3WKf6CfrOQ | TOP patterns animated by one LFO CHOP -> POP net turns texture into 3D points -> particles + color attrs. chain [U]: Noise/Ramp TOP -> TOP to POP -> Noise POP/Math Mix -> Particle POP | TOP to POP exists [V] | yes |
| 13 | Create Point Typography - dcheesman - 17 Feb 2026 [V] | d:tutorial/create-point-typography/73967 ; yt xmOC9QW2lDg | Text/image -> pointillised, "no traditional instancing" (tags POPs, Voxelizer). chain [U]: Text TOP -> TOP to POP -> Noise POP -> Point Sprite MAT. Whole-word rule applies (Q_live_typography.md) | Text POP not in 31550; Text TOP route ok | yes (recipe 7) |
| 14 | Flip-Dot Display: POPs, Dithering and Feedback - dcheesman - 6 May 2026 [V] | d:tutorial/flip-dot-display-tutorial-pops-dithering-and-feedback/74546 ; yt 1JcPI2ggs40 | Grid POP, Lookup Texture POP, normal-based logic, Bayer dithering, Feedback-driven animation, 3D render. Great LED-matrix look | Grid/Lookup Texture POP [V] | partly (Feedback POP crash note T-35) |
| 15 | Build Texture-Driven 3D Systems (Projection POP) - polyhop (Simon Alexander-Adams) - 22 Apr 2026 [V] | d:tutorial/build-texture-driven-3d-systems-touchdesigner/74430 ; yt FzugbBNACG4 | Projection POP makes 3D respond to a 2D texture; interactive grass on a twisted torus; mouse circle TOP input. **Made on 2025.32460** | Projection POP exists; pars [V]; build newer | partly |
| 16 | Controlling a POPs System with Logic (Jack DiLaura) - elburz - 19 Mar 2026 [V] | d:tutorial/controlling-touchdesigner-pops-system-logic/74194 ; yt 9_a4LaUjmbs | Particle POP driven by logic on emitter-geometry position | ok | partly |
| 17 | Procedural 3D Modelling (Utah teapot from POPs + SOPs) - elburz - 15 Dec 2025 [V] | d:tutorial/procedural-3d-modelling-touchdesigner/73556 ; yt oyZNUL9iZw0 | Mixed POP/SOP modelling; no ops named | ok | partly |
| 18 | TouchDesigner POP Attributes 101 - elburz - 20 May 2026 [V] | d:tutorial/touchdesigner-pop-attributes-101/74641 | Attribute names, sizes, types: the key concept before any POP work (see `ops/POP.md` s1) | ok | yes |
| 19 | Rolling Tiles using POPs, CHOPs and DATs - vtln - 20 Oct 2026 [V] | d:tutorial/rolling-tiles-using-pops-chops-and-dats/75531 | Grid with looping rows/columns (LED-wall-like tile motion) | newer build? | partly |
| 20 | POPs Experimental: Extrude POP - Polyhop (Patreon, Sep 2025) [S] | patreon.com/posts/138914228 | Extrude POP distance from a 2D texture + Noise POP; author says 2025.32460+ replaces attribute conversions with a Map page | paid, build newer | partly |

### 2b. Feedback, displacement, Time Machine (TOPs)

| # | Tutorial - author - date | URL | Teaches / chain | Compat | MCP? |
|---|---|---|---|---|---|
| 21 | Creating a Feedback (lesson 102) - Derivative - n/d [V] | L:100-fundamentals/lessons/102-tops-working-with-images/topic/creating-a-feedback/ | Feedback TOP for trails; no cook dependency/recursion. Pars [V]: `top` (target), `reset`, `resetpulse`; verified live chain in `A_td_2025_howto.md` s6.1 | ok | yes (done once) |
| 22 | Slit Scan using the Time Machine TOP (lesson 202) + Using the Texture 3D TOP - Derivative - n/d [V] | L:200-intermediate/lessons/202-tops-intermediate/topic/slit-scan-using-the-time-machine-top/ | Texture 3D TOP (ring buffer of frames) -> Time Machine TOP input 0; input 1 = grey map choosing the age per pixel [V docs] | both ops in dump [V] | yes (recipe 6) |
| 23 | Easy Slitscan - elburz - 15 Dec 2021 [V] | d:tutorial/easy-slitscan-touchdesigner-tutorial/65586 ; yt 1ACBmGYB8uw | "Only a few operators" slit-scan. **Pre-2023 build** | old; idea still valid | partly |
| 24 | Create Edge Feedback Concert Visuals - dcheesman - 20 Jul 2026 [V] | d:tutorial/create-edge-feedback-concert-visuals/75058 ; yt DkZ8dJlO6yg | High-contrast concert feedback. Named ops [V]: Edge, Feedback, Lookup, Bloom, Displace TOPs; basic loop, Lookup colorise, keyboard triggers, self-displacement. Order [U]. Project file on Patreon | all ops present [V] | yes (recipe 1) |
| 25 | Feedback Effects with the Bloom TOP (Jack DiLaura) - elburz - 21 Aug 2024 [V] | d:tutorial/feedback-effects-bloom-top-touchdesigner/69971 ; yt TLx18b2HFWM | Flowy liquid feedback; Bloom TOP before the loop and inside it | 2024 but TOPs unchanged | yes |
| 26 | Glitch / Feedback in Post-Processing - elburz - 17 Dec 2025 [V] | d:tutorial/touchdesigner-glitch-feedback-post-processing/73573 ; yt IKhywYY3_54 | Feedback TOP as post: glitchy buffering look + light smoke | ok | yes (recipe 8) |
| 27 | Painterly Feedback Effect - elburz - 29 Mar 2025 [V] | d:tutorial/painterly-feedback-effect-touchdesigner/71632 ; yt orM14jS-6LU | Feedback loop in TOPs -> painterly. chain [U] | ok | yes |
| 28 | Jen Stark-Inspired Colour Drip Effect - elburz - 15 Apr 2025 [V] | d:tutorial/jen-stark-inspired-colour-drip-effect-touchdesigner/71765 ; yt VFgJa8pdB7E | Colour drips via feedback + displacement (recipe 9) | ok | yes |
| 29 | Feedback Flowfield "Fake" Particle Look - a.melv - 2 Apr 2025 [V] | d:tutorial/touchdesigner-beginner-tutorial-feedback-flowfield-fake-particle-look/71665 ; yt y9ufPnSAzpM | Flowfield particle look with no particles: feedback + noise-driven motion; no external assets | ok | yes |
| 30 | Generative Art with TouchDesigner: Feedback (Marco) - elburz - 1 Jan 2025 [V] | d:tutorial/generative-art-touchdesigner-feedback/71044 ; yt 0o_NoWTi6oo | Ways to modify a feedback loop for varied art | ok | yes |
| 31 | Noise Sculpting Part 7: Ghostly Particles - audiodevout - 27 Sep 2025 [V] | d:tutorial/noise-sculpting-touchdesigner-part-7-ghostly-particles/72896 ; yt 4GkBT_fUNOM | Slope TOP + Displace TOP = ghostly web texture (named [V]) (recipe 10) | ok | yes |
| 32 | Smoky Particle Feedback FX (Jack DiLaura) - elburz - 20 Nov 2023 [V] | d:tutorial/smoky-particle-feedback-fx-touchdesigner/68591 ; yt c4Fur-XG7tk | Particle-generator SOP net, attributes for color/opacity, displacement + feedback = smoke trails | SOP-based, 2023; idea reusable with Particle POP | partly |
| 33 | Psychedelic Flower - elekktronaut (Bileam Tschepe) - 8 Feb 2025 [V] | d:tutorial/psychedelic-flower/71260 ; yt eTSKz_iiFOY | Instancing + feedback, ambient look; chromatic-aberration .tox on Patreon | ok | partly |

### 2c. Instancing, ParticlesGPU, 3D rendering

| # | Tutorial - author - date | URL | Teaches / chain | Compat | MCP? |
|---|---|---|---|---|---|
| 34 | Converting Data Types and Instancing (201: basics, TOPs, CHOPs, DATs) - Derivative - n/d [V] | L:200-intermediate/lessons/201-converting-data-types-and-instancing/ | Canonical instancing lesson with example .tox per topic. POP instancing pars are in T-15 | ok | yes |
| 35 | Instancing with the Event CHOP (Jack) / Three Creative Ways to Use Instancing - elburz - 21 May / 26 Jul 2025 [V] | d:tutorial/instancing-event-chop-touchdesigner/71993 ; d:three-creative-ways-use-instancing-touchdesigner/72496 | Event CHOP drives instances (MIDI-style triggers); the article shows 3 uses incl. Replicator | ok | yes |
| 36 | Instancing Sine Cos [33] / Reactive Boxes [32] - pao.olea - 6 Oct / 18 Aug 2026 [V]; Textures and Instancing - audiodevout - 20 Aug 2026 [V] | d:tutorial/instancing-sine-cos-touchdesigner-tutorial-33/75458 (yt AbszphQ-K64) ; d:tutorial/reactive-boxes-touchdesigner-tutorial-32/75201 ; d:tutorial/textures-and-instancing-touchdesigner-tutorial/75213 (yt owC0QyOcs5U) | John Whitney-style sine/cos instance fields; scale/rotation/color via instancing; Phong material + noise/ramp textures vary instances | ok | yes |
| 37 | 3D Render Tips for TouchDesigner (Christian) - elburz - 31 Oct 2025 [V] | d:tutorial/3d-render-tips-touchdesigner/73188 ; yt e1UlWujK1H0 | Post-processing, lighting, color design for better renders; no ops named | ok | partly (recipe 4 uses docs) |
| 38 | Physically Based Rendering (104) + Working with Render Passes (202) - Derivative - n/d [V] | L:100-fundamentals/lessons/104-rendering-3d-scenes/topic/physically-based-rendering/ ; L:200-intermediate/lessons/202-tops-intermediate/topic/working-with-render-passes/ | PBR MAT needs tangents+normals, an Environment Light COMP and a second Light COMP; Render Pass keeps depth/color for a second pass | ok | yes |
| 39 | Depth of Field in TouchDesigner (I&I HQ blog, date n/s) [S]; Pristine Rendering and Post Processing (Matthew Ragan, HQ PRO course ~3 h, paid) [S] | interactiveimmersive.io/blog/touchdesigner-3d/depth-of-field-in-touchdesigner/ ; pro.interactiveimmersive.io/courses/pristine-rendering-post-processing/ | DOF from Depth TOP (Range From values); course has Render Pass, DOF, SSAO lessons. Content not readable | ok | partly |
| 40 | External Forces for ParticlesGPU (Scott Mann) - elburz - 27 Nov 2025; Force Fields and Mouse Inputs - audiodevout - 12 Sep 2025 [V] | d:tutorial/touchdesigner-particlesgpu-using-external-forces/73406 (yt IfZljTxQYoo) ; d:tutorial/force-fields-and-mouse-inputs-particlesgpu-touchdesigner-tutorial/72808 (yt uusZcyW7o9Q) | Palette ParticlesGPU with several force fields; mouse-driven force | palette tool is GLSL; Mac ok per GLSL rules (T-10, T-47) but unverified here | partly (not checked in 31550) |

Not worth a row (checked, skip): audiodevout "Experiments with NVIDIA Flex Solver" 12 Nov 2025 (Flex is NVIDIA/Windows,
the post states no platform); Trace POP (elekktronaut, 9 Jun 2026) and "Voronoi spheres" (vtln, 13 Sep 2026) need ops absent
in 31550; Kinect + POPs (elburz, 22 Apr 2026) and Optical-Flow looks (J_interactive_camera_effects.md); paid-only POPs 201
"Procedural Environments" (HQ PRO, early 2026) [S].

## 3. Recipes - 12 best for LED/concert at 1080x1920, ranked

Ranking = LED readability (contrast, big shapes) x cost on M-class GPU x repeatability for an agent x fit to ops in 31550.
Common: set the container/Render to **1080x1920** (`outputresolution`=custom, `resolutionw=1080`, `resolutionh=1920`) [V par names];
build one structural change per `td_exec`, then `td_errors`; ops that nothing views do not cook (T-02): give each recipe a
viewed Null; screenshots flatten alpha over white (T-12). Par names below are from the 31550 dump [V]; step order is [U]
unless a docs page is named. Colours: use PRISM brand ramps (`../../../prism-brand`), not default rainbow.

1. **Edge-feedback tunnel** (tutorial 24 + 21; live-verified feedback in A s6.1)
   1. `Noise TOP` (monochrome, animate `tz`/period) or `Text TOP` as the seed -> `Edge TOP` (`strength` 1-3, `blacklevel` ~0).
   2. `Composite TOP` (`operand` add) input0 = Edge, input1 = `Feedback TOP` (`top` = the final Null, `reset`=0).
   3. Loop body: Feedback -> `Transform TOP` (`sx`,`sy` 1.01-1.03, `rotate` 0.2-1) -> `Level TOP` (`opacity` 0.94-0.98).
   4. `Lookup TOP` (input1 = `Ramp TOP`, brand colours) colours the loop; `Displace TOP` (input0 = loop, input1 = own Edge/Noise,
      `displaceweightx/y` small) bends it. `Bloom TOP` (`bloomthreshold`, `bloomintensity`, `maxbloomradius`) -> `Null TOP`.
   5. Pitfall: the loop accumulates; add `resetpulse` on a button/timer. Keyboard triggers in the source are a Keyboard In CHOP.
2. **Particle POP curl field with sprite glow** (docs: Particle POP, Force Radial POP, Noise POP [V]; T-15 verified the base)
   1. `Point Generator POP` (`shape` sphere, `numpoints` 5000, `radiusx/y/z`) -> `Particle POP` (`maxparticles` 100000, `birthrate`,
      `life`, `lifevariance`, `damping`, `initvelocityx/y/z`).
   2. After it: `Force Radial POP` (`globforcex/y/z`, `radialstrength`, `falloff`) -> `Noise POP` (`curl3d` on, `curl3doutputattrscope`
      = `PartForce`, `combineop` add, `amp0`, `period`) -> `Null POP`. Set Particle `targetpop` = that Null; then Initialize/Start
      (`initializepulse`, `startpulse`, `play`).
   3. Render: `Geometry COMP` holding a `Select POP` of the Null (T-15), `Point Sprite MAT` (`pointsize`, `colormap`), `Camera COMP`, `Render TOP`
      (`bgcolora` 1 to see), then `Bloom TOP` + optional `Feedback TOP` smoke (recipe 8).
   4. Risk: Feedback/Particle loops with Null target crashed macOS in 2025.32260 (T-35); save before, one change per call.
3. **Instanced PBR chrome field** (docs: Environment Light COMP, PBR learn lesson [V]; instancing pars T-15)
   1. `Grid POP` (cols/rows) -> `Noise POP` (move `P`) -> `Math Mix POP` (scale attr `PointScale`) -> `Null POP`.
   2. `Geometry COMP`: `instancing` on, `instanceop` = the Null POP (NOT `instancepop`, T-15), `instancecountmode` oplength,
      `instancetx/ty/tz` = P(0..2); inner SOP/POP shape (box/torus), `material` = `PBR MAT` (`metallic` 1, `roughness` 0.15-0.3,
      `basecolor*` light grey, `envlightquality`).
   3. `Environment Light COMP`: `envlightmap` = a TOP with an equirect brand/HDRI image (brand env map: `P_realtime_3d_looks.md`),
      `envlightmapprefilter` automatic for a static map, off for an animated one (docs [V]). A second `Light COMP` is expected.
      For pure chrome set the PBR diffuse/specular to 0 per the docs note.
   4. `Camera COMP` + `Render TOP` (`antialias` 4-8x) -> polish chain (recipe 4). PBR needs tangents on SOPs; POP geometry route untested.
4. **3D render polish chain** (docs: SSAO, Render Pass, Depth TOP [V]; tutorial 37, 39)
   `Render TOP` -> `SSAO TOP` (must sit directly after Render/Render Pass; `ssaoradius`, `contrast`, `blurradius`, `ssaopassres` half)
   -> `Bloom TOP` -> `Level TOP` (`contrast`, `gamma1`) -> `Lens Distort TOP` (`k1` small, or fake dispersion per P_realtime_3d_looks.md)
   -> `Null TOP`. Depth of field: `Depth TOP` (`rangefrom1/2`) as a mask into `Blur TOP` (`size`) composited over the sharp render.
   Second pass: `Render Pass TOP` (`renderinput`, `geometry`, `cleardepth`) for objects that must sit behind others.
5. **Proximity constellation lines** (tutorial 6; Proximity POP docs [V])
   `Point Generator POP` / `Particle POP` points -> `Proximity POP` (`maxdist`, `mindist`, `maxlinesperpoint` 3-5, `uniformdist` on,
   `duplines` avoid, `output` lines shared points) -> `Null POP` -> `Geometry COMP` with `Line MAT` (width/colour pars `widthnear`,
   `linenearcolor*`) -> `Render TOP` -> `Bloom`. Audio: `maxdist` bound to a CHOP envelope. `numhashbuckets` near point count.
6. **Slit-scan / Time Machine warp** (lesson 202; Time Machine and Texture 3D docs [V])
   `Movie File In TOP` (`media/webcam/webcam_ref_5s.mp4`, never live cam without ask) -> `Texture 3D TOP` (`type` texture3d,
   `cachesize` 60-120, `step` 1, `active` 1; Pre Fill needs `$F` input) -> `Time Machine TOP` input0; input1 = `Ramp TOP`
   (vertical) or `Noise TOP` greyscale; `blackoffset` -60, `whiteoffset` 0, units frames. Memory [U]: 1080x1920 RGBA8 = 8.3 MB/slice
   (float16 double), so 120 slices ~1-2 GB: keep `cachesize` modest and measure with `td_perf`. Loop-safe if source loops.
7. **Point typography** (tutorial 13; TOP to POP + Noise POP pars [V])
   `Text TOP` (large, bold; Urdu rules in `Q_live_typography.md`) -> `TOP to POP` (`maxpoints`, `uniquepoints`, `input0top`) -> `Noise POP`
   (small `amp0` jitter, animated `t4d`) -> `Null POP` -> `Geometry COMP` + `Point Sprite MAT` -> `Render TOP`. Rule (memory "names stay
   intact"): the word must resolve whole and uncovered on its hold frames; animate jitter to 0 on a CHOP envelope, never crop or split.
8. **Smoke / glitch post FX on any render** (tutorial 26, 32)
   Source -> `Composite TOP` (`operand` screen/add) with `Feedback TOP` loop: Feedback -> `Blur TOP` (`size` 2-6) -> `Transform TOP`
   (`ty` +0.002 for rising smoke) -> `Level TOP` (`opacity` 0.9-0.97) -> back. Glitch variant: `Displace TOP` driven by a stepped
   `Noise TOP` (`Level` `stepping`) and per-channel offsets via `Channel Mix TOP`. Flash safety: Level `brightness2` cap (K_audio_reactive.md governor).
9. **Colour-drip feedback** (tutorial 28 [chain U])
   `Ramp TOP` bands / `Noise TOP` -> `Composite TOP` over `Feedback TOP` -> `Displace TOP` (vertical `displaceweighty`, source = Noise
   stretched in y) -> `Transform TOP` (`ty` -0.003) -> `Level TOP` (`opacity` 0.99) -> `Lookup TOP` brand ramp -> `Null`. Drips run down the 1920 axis.
10. **Slope + Displace ghost web** (tutorial 31 [V ops])
    `Noise TOP` (`type` sparse/ridged, slow `tz`) -> `Slope TOP` (`strength`, `method`) -> `Displace TOP` (input1 = the Slope) over a
    second Noise -> `Level TOP` -> `Bloom TOP`. Add a `Feedback TOP` for lingering strands. Cheap, safe for long LED holds.
11. **Ray POP surface trails** (tutorial 10; Ray POP + Trail POP docs [V])
    Emit points (`Sprinkle POP` or `Particle POP`) -> `Ray POP` input0 points, input1 collision mesh (a `Sphere/Torus POP` or imported
    model; `rayattrib` direction, `scale` 1 to snap on, `lift` small) -> `Trail POP` (`length` 1-2 s, `lengthunit` seconds, `ageattr`, `closed` off)
    -> colour from age via `Lookup Texture POP` (`top` = ramp) -> `Line MAT` -> `Render`. Needs the Null-target Particle loop (T-35 risk).
12. **Flip-dot / LED-matrix tile display** (tutorial 14 [named ops V, order U])
    `Grid POP` (cell lattice) -> `Lookup Texture POP` (`top` = a video/Render TOP, `lookupindexattr0` = Tex) -> Math Mix threshold (Bayer
    dither pattern from a `Noise`/`Pattern POP`) -> Feedback for flip animation -> `Geometry COMP` instancing small discs -> `Render TOP` orthographic.
    Reads as an LED pixel wall on the R02 faces; pairs well with the real LED aesthetic. Risk: Feedback POP crash note (T-35).

## 4. Sources

- Derivative tutorials index (58 pages) https://derivative.ca/tutorials ; tag pages https://derivative.ca/tags/pops , /tags/feedback , /tags/instancing , /tags/particles , /tags/3d , /tags/typography [V]
- POPs lessons announcement https://derivative.ca/community-post/new-pops-lessons-learnderivativeca/74561 [V]; curriculum https://learn.derivative.ca/ (100: 102, 104, 109; 200: 201, 202) [V]
- Wiki pages read [V]: https://docs.derivative.ca/Particle_POP , /Force_Radial_POP , /Feedback_POP , /Trail_POP , /Ray_POP , /Proximity_POP , /Projection_POP , /Feedback_TOP , /Time_Machine_TOP , /Texture_3D_TOP , /SSAO_TOP , /Render_Pass_TOP , /Environment_Light_COMP
- Authors: elburz https://derivative.ca/user/63627 [V link on page]; Bileam Tschepe https://derivative.ca/community-post/bileam-tschepe-teaching-and-learning-touchdesigner/65419 [S]; pao.olea https://youtube.com/@pao_olea [V]; Paketa12 https://www.youtube.com/@paketa12 [V via oEmbed]; Patreon (Polyhop) https://www.patreon.com/posts/138914228 [S]; PPPANIK https://www.patreon.com/pppanik [S]; okVJ / Supermarket Sallad https://www.patreon.com/okvj [S]; Acrylicode https://acrylicode.gumroad.com [S]
- Courses (paid, not readable): https://pro.interactiveimmersive.io/courses/pristine-rendering-post-processing/ , https://pro.interactiveimmersive.io/skill/3d/ (POPs 201) [S]
- Local: `ops/POP.md`, `A_td_2025_howto.md` s6, `../../LEARNINGS.md` T-12, T-15, T-18, T-33, T-35, T-47; `O_generative_simulations.md`, `P_realtime_3d_looks.md`, `Q_live_typography.md`, `K_audio_reactive.md`

## 5. Open questions

1. **Video chains**: only the videos contain the real chains. Should a later pass transcribe a few (e.g. 24, 9, 14) with the user's go-ahead (download is an approval gate), or is "open the lesson .tox from learn.derivative.ca" enough?
2. **Lengths** are unknown for all rows; fetch from YouTube metadata only if the user wants them.
3. Do Particle POP / Feedback POP loops run stable on 31550 + Rosetta (T-35 lists a crash on 32260; 31550 unverified)? Test before recipes 2, 11, 12.
4. Does the Geometry COMP accept a POP as instance source *and* a POP shape inside with the PBR MAT in 31550 (needs tangents)? T-15 verified instancing only with the default torus.
5. ParticlesGPU palette tool: not checked in our palette; confirm it exists in the 278 .tox before relying on tutorial 40.
6. Whether `blankensmithing` = Torin Blankensmith; and Noones Img / SimpleTD / NAM Project need exact channel names from the user.
7. Post-31550 features (Trace POP, Text POP, Voronoi POP, Python `point()` access in 32820): the user said 7.23.2/Arena is final, not TD; is a TD upgrade allowed? Today the dump decides.
