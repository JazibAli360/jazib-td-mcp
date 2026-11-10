# B. The visual landscape: what TouchDesigner makes for concert and festival LED screens (16 Oct 2026)

Research agent B. Web research only, no TD touched, nothing generated or installed. Builds against `BRIEF.md` guardrails.
Everything marked **estimate** or **unverified** is my judgement or comes from memory/a single secondary source; there
are **no fps or render-time numbers measured here**. Saved stills + credits: `refs/B_visuals/` (30 images) and
`refs/B_visuals/SOURCES.md`. Image numbers below ("img 18") refer to that folder.

Canvas arithmetic (mine, exact): 7488x2880 = 21,565,440 px = **10.4x** a 1080p frame and **2.6x** UHD 3840x2160;
the 9984x3840 native canvas = 38.3 MP. Cost classes below are **estimates** scaled from that, not measurements. The
brief says final clips are mastered via `prismfest26-show/production/` (DXV3), so I read "cost" as *render time and
VRAM for an offline/near-real-time render*, not a live-performance guarantee. Real numbers need a `td_perf` probe
on this M1 Max (agent A or the lead).

## 1. Technique catalogue (16)

Cost class at 7488x2880: **L** light (mostly texture ops / few passes), **M** medium (several full-canvas passes or
moderate 3D), **H** heavy (per-pixel loops such as raymarching, big particle counts, many full-res feedback passes).
PF26 states = the banks in `concert-visuals-research/CLAUDE.md` (Ident / Hold / Safe / Artist / Moments).

| # | Technique | What it looks like | Known for it | Links | Core TD chain | Cost | PF26 state |
|---|---|---|---|---|---|---|---|
| 1 | **Feedback and trails** | Smeared echoes, tunnels, flow-field "fake particles", melting colour; the most common TD look | elekktronaut (Bileam Tschepe) feedback courses; Elburz; gnomalab | [Secret of feedback loops](https://derivative.ca/community-post/tutorial/secret-feedback-loops-touchdesigner-tutorial/66168) (img 10) · [Fractals via feedback](https://derivative.ca/community-post/tutorial/fractals-tutorial/64861) (img 09) · [Flowfield fake particles](https://derivative.ca/community-post/tutorial/touchdesigner-beginner-tutorial-feedback-flowfield-fake-particle-look/71665) (img 11) · [Trails vs Cache TOP](https://derivative.ca/community-post/tutorial/trails-frame-delays-touchdesigner-tutorial/64075) | Feedback TOP > Transform/Displace/Level/Blur > Composite, noise as driver. Elburz notes the Cache TOP gives "crisp, easy to control, efficient" trails vs feedback | L-M (estimate; each pass is one 21.6 MP texture op) | Hold, Safe (slow), Artist, Moments |
| 2 | **Slit-scan / time displacement** | Streaked, time-bent motion; a moving image smeared along a time axis | Elburz; Lake Heckaman (GLSL); elekktronaut (feedback version); official lesson | [Easy slitscan](https://derivative.ca/community-post/tutorial/easy-slitscan-touchdesigner-tutorial/65586) (img 29) · [GLSL slit-scan](https://derivative.ca/community-post/tutorial/glsl-slit-scan-effect-touchdesigner/74007) (img 28) · [Time Machine TOP lesson](https://learn.derivative.ca/courses/200-intermediate/lessons/202-tops-intermediate/topic/slit-scan-using-the-time-machine-top/) | Texture 3D / Time Machine TOP (frame history) > GLSL or Lookup sampling by a gradient. Needs N stored frames: **VRAM scales with canvas x history length** | M-H (estimate; memory-bound at 21.6 MP) | Artist, Moments (acts on an image/video source) |
| 3 | **GLSL raymarching and SDF shapes** | Smooth organic blobs, fractals, metallic or glassy forms, infinite tunnels; the "math sculpture" look in img 01/18 | elekktronaut-style series, Matthew Ragan "SDFs 101", t3kt (Tommy Etkin) RayTK | [Raymarching series ~5 h](https://derivative.ca/community-post/tutorial/raymarching-touchdesigner-tutorial-series/62745) (img 16) · [RayTK](https://derivative.ca/community-post/asset/raytk-raymarching-masses/63620) (img 18) · [RayTK fractal column](https://derivative.ca/community-post/tutorial/raytk-fractal-column-tutorial/68316) (img 19) · [SDFs 101 (paid, ~4 h)](https://pro.interactiveimmersive.io/?p=32371) | GLSL TOP with SDF + normal/light functions; or RayTK nodes > raymarcher. RayTK has "reflection and refraction, soft shadows" (per [RayTK page](https://derivative.ca/community-post/asset/raytk-raymarching-masses/63620)). RayTK 0.46 needs TD 2025.30770+ per one third-party listing (**unverified**; check vs 2025.31550) | **H** (per-pixel march x 21.6 MP; estimate; the single most expensive family) | Ident, Moments, Artist (hero shot) |
| 4 | **Instancing grids and TOP instancing** | Fields of repeated cubes/spheres/tiles/triangles, each driven by a texture or audio channel; sculptures; each instance with its own texture | elekktronaut; polyhop (Simon Alexander-Adams); Interactive & Immersive HQ | [Abstract 3D sculpture](https://derivative.ca/community-post/tutorial/abstract-3d-sculpture/65117) (img 14) · [Solar system, texture instancing](https://derivative.ca/community-post/tutorial/solar-system-texture-instancing/63560) (img 15) · [Instancing course (paid)](https://musichackspace.org/product/generative-instancing-in-touchdesigner-live-session-workshop-series) | Grid/Sphere SOP or TOP-to-CHOP positions > Geometry COMP instancing > Camera/Light > Render TOP | M (estimate; cost is the Render TOP at 21.6 MP plus instance count) | Hold, Ident (facet assembly), Safe |
| 5 | **POPs and GPU particles** | Millions of points: swarms, explosions, particle fields shaped by forces, formed into text/logo | Matthew Ragan + SudoMagic (official POP lessons); Vassilis Malamas workshop; Scott Mann | [Official POPs lessons](https://derivative.ca/community-post/new-pops-lessons-learnderivativeca/74561) (img 21) · [POPs instance field](https://derivative.ca/community-post/tutorial/touchdesigner-pops-instance-field/71904) (img 20) · [POP Fundamentals (paid, 3 h)](https://pro.interactiveimmersive.io/courses/pop-fundamentals-in-touchdesigner/) | Particle POP / Math Mix POP > attributes > Render. POPs are the newest operator family (GPU geometry), per Derivative. Older route: Particles GPU TOP/GLSL compute (img 17). **Check on 2025.31550 that POP ops exist; not probed** | M-H (estimate; scales with count) | Moments (shatter, burst), Ident |
| 6 | **Noise displacement and terrains** | Rolling landscapes, liquid surfaces, pulsing meshes, noise-warped images | Everywhere; Interactive & Immersive HQ noise tutorials | [CDM noise tutorial round-up](https://cdm.link/touchdesigner-noise-tutorials/) · [Audio-reactive beginner guide (binds audio to Noise SOP amplitude)](https://interactiveimmersive.io/blog/touchdesigner-3d/audio-reactive-visuals-a-beginner-guide/) | Noise TOP/SOP > Displace / Geometry height > Phong/PBR > Render TOP; or Displace TOP for 2D | L-M (estimate) | Hold, Safe, Artist |
| 7 | **Audio-reactive spectrum geometry** | Bars, rings, meshes that dance to a band split; the classic "EQ" look done in 3D | Crystal; Jack DiLaura; TDAbleton workflows | [Reactive texture](https://derivative.ca/community-post/tutorial/reactive-chop-touchdesigner-tutorial-09/70572) (img 23) · [Concert visuals with Ableton](https://derivative.ca/community-post/tutorial/concert-visuals-touchdesigner-ableton/72855) (img 24) | Audio Spectrum/Analyze CHOP > bands > Math > drive instance scale / displacement. **For PF26 clips the audio would be the set's own track or an Ableton send; no live feed exists for pre-rendered clips** | L on top of whichever look it drives | Artist (needs the act's audio), Moments |
| 8 | **Kinetic typography** | Type that instances, tumbles, traces and settles; per-letter motion | the "sentence instancing" series authors; "Touching Typography" series | [Sentence instancing pt 1](https://derivative.ca/community-post/tutorial/kinetic-typography-touchdesigner-part-1-fundament/62255) (img 26) · [Audio-reactive text tracing](https://derivative.ca/community-post/tutorial/audioreactive-text-tracing-and-instancing-touchdesigner-tutorial/73009) (img 25) · [Stair Cube](https://derivative.ca/community-post/tutorial/touching-typography-case-3-stair-cube/63592) (img 27) | Text TOP/SOP > instancing per glyph (positions from a path/shape) > Render. **Project rule: a name stays whole and uncovered (`names-words-intact`), so any per-letter motion must resolve to the full word; Urdu shaping needs the HarfBuzz route in `hyperframes/`, not a Text TOP per glyph (unverified in TD)** | L-M | Ident, Moments (countdown numerals B6-22), Hold (non-name words) |
| 9 | **Logo builds and reveals** | Light stroke draws on, facets fly in and assemble, particles resolve into the mark | studio ident work generally; SDF-text and POP reveal tutorials | [SDFs 101](https://pro.interactiveimmersive.io/?p=32371) · [POP text/logo forming, see #5](https://derivative.ca/community-post/new-pops-lessons-learnderivativeca/74561) | Logo PNG > Threshold/Edge or SDF > drives POP/instances; **last frames cut to the supplied PNG, unaltered** (`prism-brand/CLAUDE.md` hard rules: no glow/shadow/recolour on the logo) | M | Ident (B1-2, B1-3) |
| 10 | **Light beams / volumetric rays** | Shafts, lasers, light cones, god rays through haze | Lucas Morgan (GeoPix) workshop; RayTK volumetrics workshop; also an easy fake | [Volumetric Lights in TD (paid workshop)](https://derivative.ca/workshop/volumetric-lights-touchdesigner/63131) · [Volumetrics with RayTK](https://derivative.ca/workshop/volumetrics-raytk-los-angelesonline/67278) | Cheap fake: bright shape > radial/directional blur or feedback with Transform scale > Add over dark base. True: custom GLSL on spot lights, or RayTK volumetric. Derivative's workshop page says volumetric lights are not available out of the box | L (fake) / H (true volumetric), estimate | Ident (beam split), Hold, Moments |
| 11 | **Glass, refraction and chromatic dispersion** | Translucent slabs/prisms that bend the picture, RGB-split edges, a white beam fanning into a spectrum | RayTK (refraction); refractive-raymarching workshop (TDSW, on Rutube); no famous single owner found | [RayTK](https://derivative.ca/community-post/asset/raytk-raymarching-masses/63620) · [GLSL chromatic aberration tutorial (Rutube)](https://rutube.ru/video/48705e38ea342338d0ad7c03d9c2ba67/) · [Refractive raymarching, TDSW (Rutube)](https://rutube.ru/video/e01dcc2cf857451cdab0f6edc8eb82fd/) | Fake: Render TOP geometry normals/Displace to bend a background, then per-channel (R, G, B) offset/scale in a GLSL TOP. True: raymarcher with a per-wavelength IOR loop (3-9 samples, **estimate**). Titles "Refraction, Transparency and Dispersion: GLSL Materials" and "Glass Dispersion & Prism Cubes" exist on an aggregator page, **contents unverified** ([listing](https://baks.verde.ag/touchdesigner-glass-effect.html)) | M (fake, mesh + 1 GLSL) / H (true dispersion raymarch), estimate | Ident (B1-1 beam split), Moments (A3 prism B6-21), Hold (glass house look B7-24) |
| 12 | **Point clouds** | A shape made of thousands of dots/sprites drifting, breathing to audio | Crystal (audio-reactive point cloud); Function Store (volumetric LED work) | [Audio-reactive 3D point clouds](https://derivative.ca/community-post/tutorial/audio-reactive-3d-point-clouds-touchdesigner/68021) (img 22) · [Function Store profile](https://interactiveimmersive.io/blog/touchdesigner-operators-tricks/function-store-tools/) | Image/depth/noise > TOP-to-CHOP > instance small sprites > Render TOP | M | Hold, Artist, Safe |
| 13 | **Generative patterns, tiling, kaleidoscope** | Mirrored mandala fields, Truchet tiles, kaleido tunnels; seamless looping backgrounds | Official fundamentals lessons; Book of Shaders patterns chapter; many GLSL creators | [Building Patterns (learn.derivative.ca)](https://learn.derivative.ca/courses/100-fundamentals/lessons/102-tops-working-with-images/topic/building-patterns/) · [Book of Shaders, patterns](https://thebookofshaders.com/09/) | Tile/Mirror TOP or GLSL Truchet > Ramp/Lookup colour > loop via a cycled time CHOP. No TD-specific Truchet tutorial found; shader port is mine (**unverified**) | L (estimate; single GLSL pass) | Safe, Hold (spectrum drift B2-7) |
| 14 | **3D scenes with Render TOP and PBR (chrome / glass objects)** | Glossy objects with real reflections: chrome type, glass triangles, jewel forms; "cyber chrome" style family | Matthew Ragan (paid workshop); Interactive & Immersive HQ "Pristine Rendering" | [PBR material tutorial [16]](https://derivative.ca/community-post/tutorial/pbr-material-touchdesigner-tutorial-16/71235) (img 30) · [Up your render quality](https://interactiveimmersive.io/blog/3d/how-to-up-your-touchdesigner-render-quality/) · [Substance TOP](https://derivative.ca/UserGuide/Substance_TOP) | Geometry > PBR MAT (Substance/Env map) > Camera + Light + environment light > Render TOP > post (glow, DoF). Reflections need an environment map to reflect | M (estimate; anti-aliasing and 21.6 MP render target dominate) | Ident, Moments, Hold |
| 15 | **RGB-split / chromatic aberration and glitch/VHS/grain post** | Edge colour fringing, scanline glitch, dither/grain finish | Jack DiLaura (ShaderToy port); elekktronaut (VHS animations); `td-port/` already did an RGBSplit pilot (CLAUDE.md) | [Glitchy trails GLSL](https://derivative.ca/community-post/tutorial/glitchy-trails-glsl-touchdesigner/68789) (img 13) · [Simple VHS animations](https://derivative.ca/community-post/tutorial/simple-vhs-animations) | Final-stage GLSL TOP / Channel Mix / Noise grain overlay. Note `concert-visuals-research` B-idea 17 (spectrum-split IMAG) is this | L | all states as the finishing pass; IMAG |
| 16 | **Video treatment, colour curves, playhead drive** | An existing branded loop re-graded and scrubbed to audio, rather than new 3D | Louie McGill for Gala 2024 (audio drives "colour curves changes and video play head manipulation") | [Gala 2024 case](https://louiemcgill.co.uk/gala) | Movie File In > Level/Lookup/Time controlled by Audio analysis CHOPs > out. **Fits PF26 only if we render the result offline to a clip** | L | Artist (act footage), Hold |

## 2. Real examples on big LED stages, and what was TD vs pre-rendered

| Production | What was TD | What was not | Source |
|---|---|---|---|
| **Red Hot Chili Peppers, Unlimited Love World Tour 2022** (SETUP) | Content generation, mixing and show control. "More than 150 scene algorithms", four TD instances (two mirrored, one for six cameras, one master). Main LED 13.2 x 36.6 m, two side screens 9.6 x 12 m. grandMA2 sent control over sACN. "Not a single frame drop" | Some neural-network content was pre-rendered. **Lesson in the article: too much utility logic (screen distribution, pixel mapping) in TD caused memory shortages; they "would probably leave only the generation and management of content in TouchDesigner" and use a separate output server.** No pixel counts given | [derivative.ca](https://derivative.ca/community-post/how-setup-did-world-tour-red-hot-chili-peppers/66633) (img 01) |
| **Calvin Harris, Coachella 2023 main stage** (Pointshader for Human Person) | Custom shaders in TD to render for an LED wall "wider than 10,000 pixels"; real-time editing at native resolution with lowered detail | Final full-quality frames exported slower than real time on one machine, "without cluster rendering" (i.e. effectively pre-rendered). This is the closest match to PF26's method | Secondary: web-search summary of [pointshader.com](https://www.pointshader.com/calvin-harris-coachella-2023-visual-content/); **direct fetch failed from this machine (DNS), so unverified; open the page** |
| **Gala Festival 2024, main stage** (Louie McGill with Studio Lowrie) | A custom TD audio-reactive tool on the live LED; control UI for technicians; used all three nights | Base flower animation came from the studio's branding (whether pre-rendered not stated) | [louiemcgill.co.uk/gala](https://louiemcgill.co.uk/gala) |
| **Boomtown Fair 2023, Metropolis** | TD generated shapes moving up the LED pillars | Notch added particles/fields (real-time); Resolume was the media server | [notch.one](https://notch.one/portfolio/boomtown-metropolis-2023) (img 06) |
| **Secret Dreams 2022, Jade Cicada** (Tenorless) | TD media server and performance UI | Notch for 3D; looks pre-rendered in NotchLC "at highest settings", "impossible to discern" from real-time; re-rendered hours before the set after a stage change | [notch.one](https://notch.one/portfolio/jade-cicada-secret-dreams) (img 07) |
| **EDC 2010** (V Squared Labs) | TD routed two HD feeds into a pixel map; a generative audio-reactive synth ("Epic") | Live-mixed VJ video is the other half; no tile count or resolution in the article | [derivative.ca](https://derivative.ca/community-post/v-squared-labs-touchdesigner-create-pure-mayhem-edc2010/60805) (img 02) |
| **Rush 30th Anniversary Tour** | Per-song real-time TD "synths" played by a touring VJ on triple-width LED | n/a (old, 2004) | [derivative.ca](https://derivative.ca/community-post/rush-30th-anniversary-tour/60822) (img 03) |
| **Amon Tobin ISAM** | TD projection mapping, generative audio-reactive graphics, Kinect, iPad control | Also "traditionally rendered media" | [derivative.ca](https://derivative.ca/community-post/visualizing-amon-tobins-isam-v-squared-team/60785) (img 04); detail via search summary only |
| **ProLight & ProVisual 2022** (AVC) | "Key tool" for 3D staging link between transparent LED, Kinesys motion control, lighting, laser, sound | trade-show stage, not a concert | [derivative.ca](https://derivative.ca/community-post/prolight-provisual-2022/66256) (img 05) |

Not found: any named TD-built content on **Tomorrowland, Ultra or Coachella main-stage shows other than #2**, and none
at all for the festivals in the next paragraph. The pattern in every case found: **TD generates or processes, a
separate server (Resolume, Notch, Disguise-class) or an offline render carries it to the wall.**

**South Asia / Pakistan / India.** I found **no verifiable credit** of TD content on a Pakistani or Indian festival
LED stage. Leads only: (a) a Fiverr profile (Hassan Rehman, handle @mcirowave, Pakistan) lists TD visuals for Atif
Aslam, Asim Azhar, Hasan Raheem, Young Stunners, Farhan Saeed at ROX Lahore, Uraan Fest, Supersede, Amplify, Laam
Fashion Week, but it is **self-advertised, no independent confirmation** ([profile](https://www.fiverr.com/mcirowave));
(b) a Deccan Herald profile of a Bengaluru VJ working all major Indian festivals, tools not named
([article](https://deccanherald.com/india/karnataka/bengaluru/visual-element-entertainment-2254020)); (c) a TD session
listed at a Bengaluru festival (Sixth Sense, Feb 2026), community evidence only. This supports "the tool is in use
locally"; it supports nothing about what the production stack looked like.

## 3. Evidence on size and cost (what I could and could not source)

- Coachella case above: >10,000 px wide wall done with TD custom shaders, offline full-quality export (secondary
  source, unverified directly).
- A 2017 TD LED installation (Leviathan's 150 Media Stream, Chicago) ran a 15360x2160 canvas at 60 fps on PCs with a
  single Quadro M6000 24 GB, ~10 M active pixels ([derivative.ca](https://derivative.ca/events/2017/150MediaStream/);
  via search summary). 2017 hardware on a mostly playback workload, so only a loose anchor.
- A forum user reported ~6.5 GB GPU memory on a heavy project and used the **Global Resolution Modifier = Half**
  (Preferences > TOPs) to cut it (search summary of a forum post, **unverified**). Probably the practical lever for
  dev at 7488x2880: preview at half, render at full.
- I found **no official Derivative figure for max TOP size or VRAM at 8K+**. Marked as a gap.
- RHCP: keep pixel mapping/distribution out of TD (above). For PF26 that is already true: Arena does the mapping.

## 4. The six that fit PRISM best (and why)

PRISM's own concept is "one beam in, the spectrum out" (`concert-visuals-research/branded-look-ideas.md` Part B
intro). The feed look is dark plum `#19041E`, purple duotone, grain, gold type; **no generic abstract CGI** (v1
rejected, 14 Oct). So I rank for concept fit first, cost second.

1. **#11 Glass, refraction, dispersion.** It *is* the brand story and the only technique that makes B1-1 (beam split),
   B6-21 (anamorphic prism) and B7-24 (spectrum glass house look) real. Start with the fake (geometry-bent backdrop +
   per-channel offset in a GLSL TOP) which is mid-cost and loop-friendly; use RayTK refraction only for the hero
   ident, since the raymarch is the heavy path.
2. **#10 Light beams / spectrum rays.** The "one pure beam" half of the concept, and the cheap fake (blur-and-add) is
   light enough to run at full canvas. Pairs with #11.
3. **#4 Instancing of triangle facets (with #5 POPs for the shatter).** B1-3 facet assembly, B6-22 countdown facets
   and the house-look glass wall are all "many triangles". The logomark is a triangle, so the brand shape is also the
   cheapest instance primitive.
4. **#1 Feedback/trails plus #2 slit-scan.** The feed's artist posters use duotone double exposure with motion blur
   (`prism-brand/BRAND_GUIDE.md` §5 table); feedback and slit-scan produce that smear from an artist's own footage in
   purple/gold. Best fit for the Artist and Moments banks. Both need flash-limit care (stripe patterns).
5. **#8 Kinetic type, used for non-name words and numerals.** Countdowns and "Built different." lockups in wide caps
   with gold accents suit TD instancing. **Hard constraint:** artist names stay whole and calligraphy comes only
   from the client's file (user memory `names-words-intact`), so it is not for names.
6. **#13 Generative gradient/tiling plus #15 grain finish.** Safe/Hold looks (B2-7 "spectrum drift" is called the
   cheapest loop) are one GLSL pass at estimated light cost, loop cleanly by a cycled time, and the grain pass gives
   the feed's texture. Safe looks must pass `README.md` §5 anyway, and this family is the easiest to prove safe.

Runner-ups: #14 PBR chrome/glass objects (good for the "cyber chrome" or "chromatic glass" families in
`pop-concert-styles.md` if the user picks them; they have not yet), #3 raymarching (best-looking, worst cost).

Flash limits (`concert-visuals-research/README.md` §4): not >3 flashes/s over >25% of screen; >5 light-dark stripe
pairs counts as a harmful pattern. Slit-scan, kaleidoscope and tiling (#2, #13) are the techniques most likely to
produce stripes. Check every loop.

## Open questions for the lead

1. Is POP availability (and which POPs) confirmed in **2025.31550**? I did not probe; RayTK 0.46's stated minimum
   (2025.30770) also needs a check before relying on it.
2. Do you want a real cost table? A `td_perf` probe of 3-4 representative networks (feedback, instancing, a
   raymarch, GLSL dispersion) at 7488x2880 on this M1 Max would replace all "estimate" cells. Agent A or a separate
   run, since I was not allowed to touch TD.
3. Pointshader's Coachella page: open it by hand (my fetch failed on DNS). It is the closest published precedent
   for PF26's native-width, shader-driven, offline-render path.
4. Dispersion: should the first TD build for B1-1 be the fake (cheap) or true per-wavelength raymarch? That is a
   look decision for the user, not a research one.
5. Audio: PF26 clips are pre-rendered, so is there a per-act audio file to drive #7 (audio-reactive geometry), or
   do we treat audio-reactive as out of scope?
6. Urdu/name type in TD: nothing in my sources covers shaped Urdu text in TD; `hyperframes/` already has HarfBuzz.
   Is TD only for non-name words, or should someone research Urdu in TD properly?
7. Pakistan precedent is unverifiable from the web here. If it matters for a pitch, it needs a person (the user)
   asking the local visual crews directly.
