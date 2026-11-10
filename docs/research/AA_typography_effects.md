# AA: typography effects people build in TouchDesigner, ranked build plans for 1080x1920 LED (research, 26 Oct 2026)

Research only: web pages read/searched on 26 Oct 2026; **nothing was run in TD** (no TD access). Target build **2025.31550** (macOS, Rosetta, Vulkan/MoltenVK).
Extends `Q_live_typography.md` (whole-word raster rule, Urdu engines, calligraphy plate, fonts, licences, far-read arithmetic) and `V_tutorials_visual_craft.md`
recipes 7 (point type) and 12 (flip-dot); not repeated here. Binding: names/words whole and uncovered; Urdu/calligraphy only from the client's file;
looks 1080x1920; multi-pass GLSL = compute mode or single pass (T-46/T-47).
Tags: **[V]** source page read by me (content seen) · **[S]** only a search snippet/title · **[U]** unverified / my own design · **[D]** op and par names confirmed in
`ops/INDEX_2025.31550.json` (every op/par named in a chain below is [D] unless marked otherwise; common pars `outputresolution`, `resolutionw/h`, `filtertype`, `inputfiltertype` are [D]).
Cost class (estimates, **not measured**): L = few TOPs at 1080x1920; M = feedback/cache loop, 3D render or POPs; H = many passes or big caches.

## 1. Summary

1. Public TD typography material is thin and mostly video-only: Derivative pages for Sliced Type, Touching Typography, Kinetic Typography, Point Typography give a summary and a
   YouTube link but **no operator list** [V]. Where a chain below says [U] it is my build from named ops plus docs, not a transcript of the video.
2. **Most famous TD type effects work per letter** (sentence instancing, Characters Animation, typewriter, point/assemble). They break the whole-word rule or the Mac (texture instancing capped at
   **128 on macOS** per Geo Text COMP docs [V]; Kinetic Typography Part 4 exists only as a Mac workaround [V]). Rows 12, 14, 19, 20, 23, 24, 29 (and dissolve-in, #13) are flagged "needs OK" for that reason.
3. **The portable pattern is the one Q found: render the whole word once (Text TOP), then do every effect as image processing around an always-intact copy.** All top-8 plans
   keep a clean word as the top layer, so the rest frame is pixel-identical to the plain word (each plan has that check).
4. **Far-readability is a layer, not an effect**: bold face, light fill, dark outline, glow behind, grey-scale check (Daktronics: bold thick fonts, dark outline on bright text, check in greyscale [V]). Plan 1 builds it
   once as `TypeCore`; every other plan takes `TypeCore` out as its word source.
5. **Text TOP Stroke on macOS was fixed in 2025.32820** (6 May 2026, release notes [V]), i.e. after 31550: do not rely on `dispmethod=stroke`; use the blur/threshold ring (plan 1).
6. **Extrude POP exists in this build** (`extrudePOP`: `distance, inset, keepconnected, maxprimsperpoint, cpureadback` [D]) but there is **no Text POP**; the wiki page is newer (Taper, line strips from 2025.32460 [V]).
   Hero 3D = Text SOP with its own `extrude`/`extrudedepth` [D] + PBR MAT, Latin names only until Text SOP is probed on Urdu and for the macOS LOD bug (Q §4.7).
7. Glitch, liquid and sliced looks are safe only as **fringe effects**: displacement amplitude under half a stroke width, clean word on top, forced hold frames, flash governor (`K_audio_reactive.md`).
8. **Urdu/calligraphy**: raster effects work on a supplied plate; recolour (gold fill), video-in-letters and displacement on a plate need the lead's OK (Q §4.2). Details in §3.
9. **Top 8 to build first** (§4): 1 TypeCore (fill + outline + glow), 2 whole-word entry + light sweep + echo, 3 video-in-type, 4 chrome/gold relief, 5 readable glitch,
   6 liquid fringe, 7 extruded 3D PBR (Latin), 8 LED dot-matrix type. Next: word-per-cue lines, audio binding, marquee.
10. Biggest unknowns to probe first: Text TOP stroke on 31550; Extrude POP on SOP-to-POP triangles; Text SOP counters/LOD; Cache TOP memory at 1080x1920; sRGB/premult of the ring/glow composite on Arena's blend.

## 2. Effects table (31 rows)

Cols: Whole = keeps the word whole and uncovered (Y; Y* = only if the stated condition holds; **OK?** = needs the lead's OK). Far = far readability (A best, B good with outline, C poor/background only).
Chains are op by op, key pars in backticks. "Mac" = caveat on this machine.

| # | Effect | Source (date) | Look | Chain | Cost | Mac | Far | Whole |
|---|---|---|---|---|---|---|---|---|
| 1 | Whole-word Text TOP base | Derivative Text TOP docs [V]; Text TOP Pro Tricks, elburz, 2 Aug 2020 [S] | Big solid word, sized to frame | `textTOP` (`text`, `fontfile`, `dispmethod`=Scalable (Slug), `fontautosize`, `fontsizex`, `alignx/aligny`, `wordwrap`, `bgalpha`=0) | L | Urdu joins OK (T-16); Slug Urdu unverified | A | Y |
| 2 | Whole-word spring/overshoot entry | own [U]; Spring/Lag CHOP docs | Word slides/scales in, overshoots, settles | `timerCHOP` (`length`,`start`) -> `lagCHOP` (`lag1`,`overshoot1`) or `springCHOP` (`springk`,`mass`,`dampingk`) -> `transformTOP` (`ty`,`sx`,`sy`,`rotate`) | L | none | A | Y (uniform scale only) |
| 3 | Echo/trail behind word | I&I HQ "TouchDesigner Trails" [S: Cache + Cache Select crisper than Feedback]; Derivative Feedback lesson [V] | Ghost copies lag behind motion | `textTOP` -> `cacheTOP` (`cachesize`,`step`,`active`) -> N x `cacheselectTOP` (`cachetop`,`index`) -> `levelTOP` (`opacity`) -> `compositeTOP` (`operand` add) UNDER live word | M | 16 slices x ~8 MB 8-bit [U] | B | Y (behind, never over) |
| 4 | Gold/gradient fill + light sweep | Q §4.2 chain; Text Formatting Codes `grad`/`color2` [V] | Flowing gold in letters, glint passes | `noiseTOP` -> `lookupTOP`(in2 `rampTOP` brand) -> `insideTOP`(in2 = word) ; sweep `rampTOP` -> `transformTOP`(`tx`) -> `insideTOP` -> `addTOP` | L | none | A | Y; **recolours a calligraphy plate: OK?** |
| 5 | Outline + neon glow ring | Daktronics "dark outline with bright text" [V]; own ring chain [U] | Dark ring, glow behind | word alpha -> `blurTOP` (`size`) -> `thresholdTOP` (`threshold`,`soften`) -> `subtractTOP` (minus word) = ring ; blur+`bloomTOP` behind | L | `dispmethod=stroke` buggy until 32820 | A | Y |
| 6 | SDF / JFA contours (multi-ring, bevel) | Red Blob Games, 27 Mar 2024 [V: outline = distance band, glow = blurred distance]; three.js JFA demo [S] | Echoing contour lines, soft inner glow | word -> N x `glslTOP` **mode=compute** (JFA halving, `autodispatchsize`) ~11 passes at 1920 -> distance shader -> bands | H | multi-pass: compute only (T-47); verify output path | A | Y |
| 7 | Video-in-type | Derivative "Mattes & Masks" [V]; Q §4.8 | Footage inside the letters | `moviefileinTOP` -> `levelTOP` (`outlow`=floor) -> `insideTOP` (in2 = word) over gold backing + ring | L | none | B (A with floor+ring) | Y*; dark clip hides letters: floor mandatory |
| 8 | Glass/refraction type | own [U]; Normal Map/Displace docs | Word acts as a lens on the background | word -> `blurTOP` -> `normalmapTOP` (`heightmap`,`zscale`) -> `displaceTOP`(in1 = bg video, in2 = normal map; `displaceweightx/y`) + rim `edgeTOP` | M | none | B | Y* (rim + fill needed) |
| 9 | Chrome/gold relief (2.5D) | Q §4.2 + P_realtime_3d_looks.md | Lit metal slab from a raster | word -> `channelmixTOP` (alpha->rgb) -> `blurTOP` x2 -> `normalmapTOP` -> `glslTOP` (single-pass compute shade; `vec0name` light) -> `insideTOP` | L-M | none | A | Y; plate: OK? (relight only) |
| 10 | Extruded 3D type, PBR | glama create_text_3d [S low trust: Text SOP + Extrude + Geo COMP]; Extrude SOP docs [V] | Chrome/gold slab letters | `textSOP` (`extrude`,`extrudedepth`,`levelofdetail`) -> `geometryCOMP` (`material`=`pbrMAT`) + `environmentlightCOMP` + `lightCOMP` + `cameraCOMP` -> `renderTOP` -> `bloomTOP` | M | **macOS ignores LOD** (Q, SOP_MAT gotcha 3) | A | Y (rotation <= ±25 deg) |
| 11 | Extrude POP type | Patreon Polyhop, Sep 2025 [S]; Extrude POP docs [V] | GPU-extruded letters | `textSOP` -> `soptoPOP` (`polygons`) -> `extrudePOP` (`distance`) -> `normalPOP` -> `geometryCOMP` | M | untested in 31550; POP readback stalls | A | Y |
| 12 | Point typography | Create Point Typography, dcheesman, 17 Feb 2026 [V page, video only] | Name made of dots | `textTOP` -> `toptoPOP` (`maxpoints`,`input0top`) -> `noisePOP` (`amp0`,`t4d`) -> `nullPOP` -> `geometryCOMP` + `pointspriteMAT` -> `renderTOP` | M | Feedback/Particle POP loops crash risk (T-35) | B | Y* (jitter -> 0 on hold) ; assemble = **OK?** |
| 13 | Burn/dissolve-out | Q §4.2 ink-bleed; own [U] | Word eaten by noise as last move | `noiseTOP` (animated `tz`) -> `thresholdTOP` (`threshold` ramps 0->1,`soften`) -> `matteTOP`/`multiplyTOP` on word | L | none | B | Y until the last move; dissolve-in = **OK?** |
| 14 | Sliced Type | threedashes, 25 Jun 2020 [V page; yt DeCaJ5EwyIg]: noise + masks + Displace, audio | Word cut into horizontal bands that slide | `noiseTOP` (stretched) -> `levelTOP` (`stepping`) -> `displaceTOP` (`displaceweightx`) on word | L | none | B | **OK?** (offset slices); safe: offset < half stroke, 0 on hold |
| 15 | Readable glitch (RGB split + tear) | elburz VHS glitch GLSL, 26 Jan 2026 [V]; exsstas Glitches, 29 May 2021 [V]; elburz Glitchy Trails, 24 Dec 2023 [V] | Colour fringes + band tears, word legible | clean word + `glslTOP` (single pass, 3 offset taps) + `displaceTOP` (stepped `noiseTOP`) UNDER clean word; gate by `logicCHOP` | L | pixel-mode single pass only (T-46) | B | Y (clean top layer) |
| 16 | Liquid / feedback displacement | Okamirufu Metallic Fluid (Feedback+Blur+Displace) [S]; YT "Fluid Text Morphing" nQ9Ksh_G3r0 [S title only]; Derivative feedback lesson [V] | Word melts/drips at edges, chrome liquid | `feedbackTOP`(`top`=loop null) -> `blurTOP` -> `displaceTOP`(noise) -> `transformTOP`(`ty`) -> `levelTOP`(`opacity`<1) -> `compositeTOP` + word | M | washout/black-out risk (LucieMrc README [V]) | B | Y (clean anchor on top) |
| 17 | Wave/ripple warp | Red Blob "wavy, bounce, warp" list [V, names only] | Word undulates | `rampTOP`/`noiseTOP` -> `displaceTOP` (low `displaceweight`) on word | L | none | B | Y* amplitude < stroke |
| 18 | One-word-per-cue lines | Table DAT + Text TOP pattern [S]; Q §4.4 | Whole line replaces whole line on cue | `tableDAT` -> `textTOP` (`dat`,`rowindex`) driven by `countCHOP`/`timerCHOP`; `switchTOP` crossfade | L | Urdu DAT round trip unverified | A | Y |
| 19 | Typewriter / letter-by-letter | LucieMrc TD_textEffects `letterbyletter.toe`, MIT [V]: Parameter/Select DAT -> DAT-to CHOP, Timer CHOP, Text TOP; forum thread (supafur) [V] | Text types on | `timerCHOP` -> `mathCHOP` -> `textTOP` `text` expr slicing a string | L | none | A | **OK?** (partial word); safe variant = #18 |
| 20 | Marquee / ticker | Teleprompter, THETOUCHLAB, 27 Oct 2023 [S]; own [U] | Words crawl through the frame | wide `textTOP` -> `transformTOP` (`ty` = -absTime.seconds*k, `extend` repeat) or `tileTOP` | L | Text TOP width <= 16384 (A §1) | B | **OK?** (words cross the frame edge) |
| 21 | Whole-word tile walls (noise grid / cache grid) | Touching Typography Case 1 (19 Jun 2020, TOPs, yt D4n6ohCSIKQ) and Case 2 (29 Oct 2020, Cache TOP + Cache Select + Animation COMP, yt ogE9-RhDZXU), Artechs [V pages, video-only] | Grid of word copies scaling in waves | `textTOP` -> `tileTOP` (`repeatx/y`) or `layoutTOP`; per-cell scale by `noiseTOP`/`cacheselectTOP` index offsets via `glslTOP` single pass | M | none | B | Y* (each cell a whole word) |
| 22 | Stair cube / Animation COMP | Touching Typography Case 3, Artechs, 15 Nov 2020 [V: Animation COMP, FBX import, camera, Layout TOP] | Type on a Blender-animated solid | `animationCOMP` -> `geometryCOMP` + text texture -> `renderTOP` | M | FBX pipeline | B | Y* |
| 23 | Sentence instancing (per glyph) | Kinetic Typography Parts 1-4, Artechs, 28 Dec 2019 - 29 Mar 2020 [V pages; yt zrA9gaCymjM] | Letters follow paths | `geotextCOMP` / `textSOP` + `geometryCOMP` instancing | M | **instance textures capped 128 on macOS** | B | **OK?** (per glyph; breaks Urdu joins) |
| 24 | Characters Animation asset | anodin, 24 Mar 2024 [V page]: Geo Text COMP intro/stay/outro | Per-char in/out presets | `geotextCOMP` + custom pars | M | licence/TD version not stated | B | **OK?** |
| 25 | 3D words in space + camera dolly | Geo Text COMP docs [V]: Spec DAT blocks, `sorted`, `facecam` | Camera flies past whole words | `tableDAT`/spec DAT -> `geotextCOMP` (`specdat`,`sorted`,`facecam`,`drawpriority`) -> `cameraCOMP` (path/`lfoCHOP`) -> `renderTOP` | M | glyphs are alpha quads: draw order | B | Y (block = word) |
| 26 | Type tracking a camera / 3D point | forum "Geo Text COMP labels" [S]: Object Merge SOP points -> Spec DAT | Label stays on a moving 3D object | `objectmergeSOP` / `objectCHOP` -> `choptoDAT` -> spec DAT -> `geotextCOMP` (`widthaffectedbyfov` off or `depthScale*`) | M | none | B | Y |
| 27 | Audio-reactive type | audiodevout, 9 Oct 2025 [V page; yt sDOvmhu6DWY; AudioAnalysis tool]; Sliced Type audio section [V] | Word pulses/glows/warps | `audiospectrumCHOP` -> `analyzeCHOP`/`mathCHOP`/`lagCHOP` -> pars of #5, #14, #15, #17 (glow, amp, bloom) | L | live audio-in op not named `audio*` in dump: use `JZBA_AudioAnalysis` (K) | A | Y (word-level pars only) |
| 28 | LED dot-matrix / flip-dot type | dcheesman Flip-Dot, 6 May 2026 [V page]; own TOP version [U] | Word rendered as LED cells | word -> `levelTOP` (`outputresolution` custom 108x192, linear) -> `levelTOP` (`stepping`) -> `levelTOP` up 1080x1920 (`inputfiltertype` nearest) x `circleTOP` tiled by `tileTOP` | L | none | A (cells <= 1/3 stroke) | Y (flicker only, never off) |
| 29 | Text on curved/3D surfaces | LucieMrc `curvedText.toe`, MIT [V]: Text SOP + Creep SOP + Twist SOP, cube text texture | Word wraps a tube/sphere | `textSOP` + `gridSOP` -> `twistSOP` -> `creepSOP` -> `geometryCOMP` -> `renderTOP` | M | CPU SOPs | C | **OK?** (far side hidden when it turns) |
| 30 | Collage typography | mattrosslive, 22 Jan 2023 [V page; yt m5ZupBiaZGE; free file martross.gumroad.com/l/efxleb] | Letterforms built of image tiles | `replicatorCOMP` / instancing of image tiles masked by word | M | instancing limits | B | Y* (whole word silhouette) |
| 31 | Formatting-code emphasis | Text Formatting Codes docs [V]: `stretch, track, skew, scale, color, color2, grad, reset` | Per-word colour/scale/skew inside one line | `textCOMP` (`formatcodes` on, `text` with `{#color(..)}`) | L | no per-glyph offsets/animation codes | A | Y (word level); **never `track` on Urdu** (Q) |

(#22 is a series sibling of #21.)

## 3. Rules these effects obey (from Q + memory) and Urdu use

- **Safe on a whole-word raster:** 2, 3 (behind), 4 (Latin), 5, 7*, 8*, 9, 13 (exit only), 15, 16, 17, 18, 25, 26, 27, 28, 31.
- **Needs the lead's OK before any use:** 12 assemble, 14 slices, 19 typewriter, 20 marquee entry/exit, 23, 24, 29, dissolve-in.
- **Urdu text (Text TOP, Noto Nastaliq, native-reader proofed):** same chains, but outline ring thin (hyperframes U-07), bold weight, padded frame (tall overhang), no `trackingx`, word spacing by space padding.
- **Client calligraphy plate (Movie File In PNG alpha):** feed it where `word` is used. Allowed without recolour: glow under (5), light sweep inside alpha (4 sweep only), relief relight (9), entry (2), echo behind (3), fade/blur-in.
  **Not without OK:** gold fill (recolour), video-in (7), displacement of the plate (8, 14-17), dots (28).

## 4. Top 8 to build first: ranking and build plans

Ranking = far readability x rule safety x Mac safety x reuse by other plans x agent-runnability. Order: **1 TypeCore, 2 Entry+Sweep+Echo, 3 Video-in-type, 4 Relief, 5 Readable glitch, 6 Liquid fringe, 7 Extruded PBR, 8 Dot-matrix.**
Runnable next (not in top 8): #18 cue lines, #27 audio binding (bind to plan 1/2 pars), #20 marquee (if allowed), #12 point type (V recipe 7).

**Common rules for every plan:** container `/project1/typ_<plan>` (baseCOMP, unique name per agent, T-20); every generator TOP `outputresolution`=custom, `resolutionw`=1080, `resolutionh`=1920; end with `nullTOP out`;
one structural change per `td_exec`, then `td_errors`; `td_layout` flow; viewers on; judge alpha from composites not screenshots (T-12); colours from `prism-brand/brand.json` (do not invent); fonts OFL only (Q §4.11).
Start values marked [U] are guesses to tune live. "Rest check" = with all animation at hold, `out` equals the plain word (numpy max abs diff < 2/255; if numpy fails restart TD, T-48).

### Plan 1: TypeCore (fill + dark outline + glow), the base of everything
1. `textTOP word`: `text`=NAME, `font`/`fontfile`=bold brand Latin face, `dispmethod`=Scalable, `fontautosize`=Auto-Fit if Too Large, `alignx/aligny` center, `wordwrap` on (breaks only between words), `bgalpha`=0, white, `premultrgbbyalpha` off; size so the word spans <= 90% of 1080.
2. `rampTOP gold` (vertical, brand gold stops via `color1..4`, `position1/2`) and `noiseTOP flow` (mono, `period` ~0.6, animate `tz`; `sx` stretch) -> `lookupTOP` (in1 flow, in2 gold) -> `insideTOP fill` (in1 = lookup, in2 = word): gold only inside letters.
3. Ring: `blurTOP grow` on word (`size` ~ 5% of cap height) -> `thresholdTOP` (`threshold` 0.1, `soften` small) -> `subtractTOP` (in1 grown, in2 word) = outline ring alpha -> `multiplyTOP` with `constantTOP dark` (brand dark).
4. Glow: grown mask -> `blurTOP glow` (`size` ~ 40) -> `multiplyTOP` gold * 0.5.
5. Stack with `overTOP` x3, bottom to top: glow, ring, fill. (Over: in1 over in2.)
6. `bloomTOP` (`bloomthreshold` ~0.85, `bloomintensity` ~0.25: high threshold so thin strokes are not eaten) -> `levelTOP` (`brightness2` cap for flash safety) -> `nullTOP out`.
7. Custom pars via `td_custom_pars` on the container: `Text`, `Outline` (grow size), `Glow`, `Goldspeed`; bind step values with expressions.
8. Greyscale check branch: `monochromeTOP` after `out`; word must read in grey. Test the longest PF26 name and a 2-word name.
9. Rest check vs step 1 alpha (shape unchanged; only colour added). Cost L; `td_perf` after ~10 s.
For a calligraphy plate: replace step 1 with `moviefileinTOP` (PNG alpha), **skip step 2** (no recolour), keep 3-6 with a thinner ring.

### Plan 2: Whole-word entry + light sweep + echo (uses Plan 1 `out`)
1. `selectTOP word_src` -> plan 1 `out`.
2. `timerCHOP t` (`length` 1.4 s, `cycle` off, `play` 0; a `start` pulse via custom par `Go`) -> channel `timer_fraction`.
3. `lagCHOP ease`: `lag1` ~0.25 s, `overshoot1` ~0.4 [U] on a `mathCHOP` that maps `timer_fraction` 0..1 -> 0..1 (hard step feel).
4. `transformTOP move` on `word_src`: `ty` from `ease` (-0.7 -> 0), `sx`=`sy` from `ease` (0.85 -> 1.0), `rotate`=0. Bind with expressions `op('ease')['chan1']`.
5. `blurTOP` `size` = (1 - fraction) * 30 and `levelTOP` `opacity` = fraction: blur-in + fade (never partial word).
6. Sweep: `rampTOP` narrow bright band (transparent-white-transparent), `transformTOP` `rotate` 20, `tx` driven by `t` (-1 -> +1) -> `insideTOP` (in2 = word alpha) -> `addTOP` onto the word. Glint stays inside letters.
7. Echo: `cacheTOP hist` (`cachesize` 16, `step` 1, `active` 1) fed by the moved word -> 4 x `cacheselectTOP` (`cachetop`=hist, `index` 3, 6, 9, 12) -> `levelTOP` `opacity` .5/.35/.2/.1 -> `compositeTOP` (`operand` add).
8. Order: echo composite UNDER the moved live word (`overTOP`); fade echoes to 0 with `t` done (`levelTOP opacity` from `1-fraction`).
9. `nullTOP out`. Rest check: after `t` done, `out` == plan 1 `out`. Cost M (cache memory ~ 16 x 8 MB).
Audio: bind sweep speed and echo opacity to `lagCHOP`ed `audiospectrumCHOP` band (word-level, no tracking).

### Plan 3: Video-in-type (footage inside the name)
1. `moviefileinTOP clip`: `file`=`media/webcam/webcam_ref_5s.mp4` (house) or an approved loop; `playmode` loop; `fitTOP` fill to 1080x1920.
2. `levelTOP floor`: `outlow` 0.25 (luma floor), `outhigh` 0.95, `gamma1` tune: the footage inside letters never goes near black.
3. `transformTOP drift`: slow `tx`/`ty` drift (<= 2% per second) so the footage moves, the mask never does.
4. `selectTOP word` = plan 1 word alpha (not the gold fill). Mask is full-size from frame 0 (never grows from smaller).
5. `insideTOP clipword` (in1 = floored clip, in2 = word).
6. Backing: `constantTOP` brand dark gold -> `insideTOP` (in2 = word) -> `overTOP` with `levelTOP` (`opacity` 0.85) clip layer on top: texture inside gold.
7. Ring + glow from plan 1 steps 3-5 laid over/under; keep ring opaque.
8. `bloomTOP` light -> `nullTOP out`.
9. Check: letters' min luma >= 0.25 via numpy on `clipword` masked by word; greyscale view.
Not for Urdu text with hairlines; plates need OK. Cost L.

### Plan 4: Chrome/gold relief (lit metal from the word raster)
1. `selectTOP word` = white word alpha (plan 1 step 1, no fill).
2. `channelmixTOP a2rgb`: `red4`=`green4`=`blue4`=1, `red1`=`green2`=`blue3`=0, `alpha4`=1: alpha into RGB as height.
3. `blurTOP h1` (`size` 3) and `blurTOP h2` (`size` 14) on a2rgb -> `addTOP` (h1 + 0.5 x h2 via `levelTOP` `opacity`) = rounded bevel height.
4. `normalmapTOP nrm`: `heightmap` = wired height, `zscale` 4 [U], `offset1/2` 1 px.
5. `glslTOP shade`: `mode`=compute, custom resolution 1080x1920, `computedat` shader, input0 = nrm, input1 = word; `vec0name`=`uLight`, `vec1name`=`uShine`, `color0name`=`uC0` and `uC1` gold dark/light. Core (T-47 pattern):
   `layout(local_size_x=8,local_size_y=8) in; void main(){ ivec2 p=ivec2(gl_GlobalInvocationID.xy); vec3 n=normalize(texelFetch(sTD2DInputs[0],p,0).xyz*2.-1.); float a=texelFetch(sTD2DInputs[1],p,0).a; vec3 L=normalize(uLight); float d=max(dot(n,L),0.); float s=pow(max(dot(reflect(-L,n),vec3(0,0,1)),0.),uShine); vec3 g=mix(uC0,uC1,smoothstep(.2,.8,n.y*.5+.5)); TDImageStoreOutput(0,ivec3(gl_GlobalInvocationID),vec4((g*(.35+.65*d)+s)*a,a)); }` [U]
6. `lfoCHOP` drives `uLight` x slowly (period 6 s) so the highlight travels over the letters.
7. Rim: `edgeTOP` on blurred alpha -> `addTOP` 0.3. Dark ring + glow from plan 1 under it.
8. `bloomTOP` -> `nullTOP out`. Check `td_errors` for shader compile (Info DAT, T-02). Rest check: silhouette (alpha) identical to plan 1.
Plate: relight only, keep the plate's own colour in `uC0/uC1` (sampled from the plate) = needs OK if it changes the gold. Cost L-M.

### Plan 5: Readable glitch (fringe only)
1. `selectTOP clean` = plan 1 `out`.
2. Gate: `noiseCHOP g` (`period` 0.4 s) -> `mathCHOP` (map 0..1) -> `logicCHOP` (bound > 0.8) = burst on; `timerCHOP hold` forces gate 0 for the first 2 s after each name appears and at least 1 s between bursts (governor: <= 3 bursts/s, `K_audio_reactive.md`).
3. `noiseTOP bands`: mono, `sx` large vs `sy` (rows differ, columns similar), animate `tz` -> `levelTOP` (`stepping` on, `stepsize` ~0.1) = quantised rows.
4. `displaceTOP tear`: in1 = clean, in2 = bands; `displaceweightx` = 0.01 * gate (<= 11 px at 1080, less than half a stroke), `displaceweighty` 0.
5. `glslTOP rgbsplit` (pixel mode, **single pass only**, T-46): `vec0name`=`uOff`; sample R at uv + uOff, G at uv, B at uv - uOff; `uOff` = (0.006*gate, 0). Input = tear output.
6. `levelTOP` `opacity` 0.7 on rgbsplit; `overTOP`: clean word on TOP of it. Fringes show outside letters; the word is never altered.
7. Optional: a darker second tear copy under; scanline `rampTOP` only on background.
8. `levelTOP` `brightness2` cap; `nullTOP out`. Rest check with gate = 0: equals clean. Check burst frame in greyscale: word still readable.
Cost L. Do not use on a plate without OK.

### Plan 6: Liquid fringe (word melts at the edges, stays whole)
1. `selectTOP clean` = plan 1 `out`; `levelTOP feed` (`opacity` 0.25) on clean.
2. Loop: `feedbackTOP fb` (`top`=`loop_out`, `reset` 0) -> `blurTOP` (`size` 1.5) -> `displaceTOP` (in2 = `noiseTOP flow`: `period` 0.25, animated `tz`; `displaceweightx/y` 0.002-0.004, `midpointx/y` 0.5) -> `transformTOP` (`ty` -0.0015 for drips; `sx/sy` 1.001) -> `levelTOP decay` (`opacity` 0.96).
3. `compositeTOP loop_in` (`operand` add): in1 = feed, in2 = decay output -> `nullTOP loop_out`.
4. Colour: `lookupTOP` (in2 = brand `rampTOP`) on loop_out luma -> liquid body colour.
5. Anchor: `overTOP` plan 1 `out` ABOVE the coloured liquid: the word is intact; liquid only grows beyond edges and tints behind.
6. Safety: a timer pulse into `fb.resetpulse` every 20 s (hidden by a short crossfade); `levelTOP` cap after loop. Watch for washout/black-out (LucieMrc README [V]).
7. `nullTOP out`. Run 60 s and check max/mean luma stable (no growth), `td_perf` cook time; save a copy first (feedback is a crash-risk class for POP loops only; TOP feedback verified in A §6).
Cost M (16F loop at 1080x1920 ~ 16 MB). Not on a plate without OK.

### Plan 7: Extruded 3D PBR type (Latin names only)
1. `textSOP t3d`: `text`, `font`/`fontfile` (heavy OFL face), `fontsizex` 1, `extrude` on, `extrudedepth` 0.25, `levelofdetail` high, `output` closed polys; `alignx/aligny` center.
2. Size to frame: `td_exec` bbox of t3d; `transformSOP` `sx=sy=sz` = 0.9*frustum width/bbox width (perspective) -> centered.
3. `geometryCOMP geo`: display SOP = t3d, `material` = `pbrMAT gold`: brand `basecolorr/g/b`, `metallic` 1, `roughness` 0.25, `ambientocclusion` 1, `envlightquality` high.
4. `environmentlightCOMP env`: `envlightmap` = brand env TOP (P_realtime_3d_looks.md brand env) or a ramp/noise equirect for the first test; `dimmer` 1. PBR expects a second `lightCOMP key` (`lighttype` point/distant, `dimmer` 0.6).
5. `cameraCOMP cam`: `projection` perspective, `fov` 30, `tz` so the word fits; (alt: orthographic with `orthowidth` to avoid perspective stretch).
6. `renderTOP r`: `camera`=cam, `geometry`=geo, `lights`=env key, `antialias` 8, `bgcolora` 0, 1080x1920.
7. Motion: `lfoCHOP` -> `geo.ry` +/-12 deg, period 8 s, never beyond +/-25 deg (word stays readable). Flat-front hold at `ry`=0 for name reads.
8. Post (V recipe 4): `ssaoTOP` optional (must follow Render), `bloomTOP`, `levelTOP` -> composite plan 1 ring/glow behind -> `nullTOP out`.
9. Mac checks: point count on t3d (LOD bug); counters (inside of O/A/R) present; thin serifs not broken; `td_perf`. If bad, fall back to `extrudeSOP` chain (Text SOP `closedpolys` -> `holeSOP` -> `extrudeSOP`) or HyperFrames pre-render.
10. Variation (untested): #11 `soptoPOP` -> `extrudePOP` (`distance`) -> `normalPOP`.
Cost M. Urdu: not until Text SOP Urdu is probed (Q §7).

### Plan 8: LED dot-matrix type (reads like the wall itself)
1. `selectTOP word` = white word alpha (plan 1 step 1).
2. `levelTOP lo`: `outputresolution` custom 108 x 192, `inputfiltertype` linear: each cell = coverage.
3. `levelTOP quant`: `contrast`/`gamma1` to harden, `stepping` on, `stepsize` 0.25 (4 levels).
4. `levelTOP hi`: `outputresolution` custom 1080 x 1920, `inputfiltertype` nearest: each cell = 10 x 10 px block.
5. Dot mask: `circleTOP dot` (10 x 10 px res, `radiusx/y` ~0.42, `softness` small) -> `tileTOP` (`repeatx` 108, `repeaty` 192) at 1080 x 1920.
6. `multiplyTOP` hi * dot -> `multiplyTOP` brand `constantTOP` (gold or white).
7. LED bleed: `blurTOP` (`size` 4) -> `addTOP` at 0.4 + `bloomTOP`.
8. Dark panel between cells: `constantTOP` near-black under (`overTOP`).
9. Motion: brightness shimmer +/-10% via `noiseTOP` * `levelTOP` (never cells off); optional whole-word scan light (plan 2 step 6 on cell values).
10. `nullTOP out`. Check: thinnest stroke >= 2 cells (20 px); if not, use 72 x 128 grid (15 px). Greyscale view. Cost L.

## 5. Sources

TD docs: Text TOP https://docs.derivative.ca/Text_TOP (Display Method: Automatic/Polygon/Stroke/Bitmap/Scalable; Stroke Width; Auto-Fit) · Text Formatting Codes https://docs.derivative.ca/Text_Formatting_Codes ·
Geo Text COMP https://docs.derivative.ca/Geo_Text_COMP (Spec DAT blocks, sorted, facecam, macOS 128 instance textures) · Extrude POP https://docs.derivative.ca/Extrude_POP · Release notes https://docs.derivative.ca/Release_Notes (Stroke macOS fix 2025.32820, 6 May 2026; Extrude POP line strips 2025.32460, 10 Mar 2026; Text COMP colour glyphs 2025.32280) · Q file docs.
Community: https://derivative.ca/community-post/tutorial/sliced-type/62992 (yt https://www.youtube.com/watch?v=DeCaJ5EwyIg) · Touching Typography https://derivative.ca/community-post/tutorial/touching-typography-case-1-noise-grid-part-1-2/62979 , .../case-2-cache-grid/63534 , .../case-3-stair-cube/63592 ·
Kinetic Typography https://derivative.ca/community-post/tutorial/kinetic-typography-touchdesigner-part-1-fundament/62255 , .../part-4-non-kepler-mac-osx-workaround/62711 · https://derivative.ca/community-post/asset/characters-animation/69211 ·
https://derivative.ca/community-post/tutorial/create-point-typography/73967 · https://derivative.ca/community-post/tutorial/audioreactive-text-tracing-and-instancing-touchdesigner-tutorial/73009 · https://derivative.ca/community-post/tutorial/collage-typography-touchdesigner-instancing-tutorial/67113 ·
https://derivative.ca/community-post/tutorial/glitchy-trails-glsl-touchdesigner/68789 · .../glitches-pixel-sorting-and-data-moshing/64888 · .../touchdesigner-glitch-effect-glsl/73842 ·
https://derivative.ca/community-post/tutorial/teleprompter-autocue-touchdesigner/68508 · tag pages https://derivative.ca/tags/text , /tags/typographic , /tags/typography ·
https://github.com/LucieMrc/TD_textEffects (MIT; letterbyletter, curvedText, feedback_video_text) · forum typewriter https://forum.derivative.ca/t/typewriter-effect-refresh-at-new-paragraph/979733 · https://interactiveimmersive.io/blog/touchdesigner-lessons/touchdesigner-trails/ [S] ·
https://alltd.org/metallic-fluid-in-touchdesigner-using-feedback-blur-and-displace-top-super-fast-tutorial-series/ [S] · https://www.youtube.com/watch?v=nQ9Ksh_G3r0 [S] · https://www.patreon.com/posts/138914228 [S, 403 on fetch].
Techniques/legibility: Red Blob Games https://www.redblobgames.com/blog/2024-03-27-distance-field-effects/ · JFA https://discourse.threejs.org/t/demo-realtime-sdf-effects-with-the-jump-flood-algorithm/88012 [S] ·
Daktronics https://daktronics.com/blog/best-practices-for-led-display-design · low trust (third-party MCP listings, structure only): glama create_text_3d / create_sdf_text / create_kinetic_text / create_glitch.
Local: `Q_live_typography.md`, `V_tutorials_visual_craft.md` (recipes 1, 4, 7, 8, 12), `K_audio_reactive.md`, `P_realtime_3d_looks.md`, `ops/*`, `../../LEARNINGS.md` T-02, T-12, T-16, T-20, T-35, T-46, T-47, T-48.

## 6. Open questions

1. **Partial-word effects:** typewriter (#19), marquee entry/exit (#20), sliced (#14), dissolve-in, point assemble (#12) show part of a word for a moment. Allowed at all, or only the safe variants?
2. **Brand values:** exact gold stops, dark, Latin heading face for TypeCore come from `prism-brand/brand.json`; not read here (confirm face + licence for TD `fontfile`).
3. Probe on 31550 (one afternoon, `_probe_typ`): Text TOP `dispmethod=stroke`; `extrudePOP` fed by `soptoPOP` triangles; Text SOP counters + point count; `cacheTOP` 16 slices memory/fps; Slug Urdu in Text TOP Scalable.
4. **Calligraphy file** format and whether a lit-metal relight (plan 4) or glow under (plan 1) counts as altering it (Q open question 1 still open).
5. **Vertical long names:** rotate the word 90 deg on the tall canvas, or stack by words (plan 1 `wordwrap`)? Rotation changes reading direction.
6. Flash governor numbers for glitch/audio pulses: take the limits from `K_audio_reactive.md`/`concert-visuals-research/README.md` §4 (not re-derived).
7. LED pitch and distance to set the outline width and plan 8 cell size (all px values here are [U] starting points).
8. Native arm64 TD or newer build (T-46 question, Text POP/Stroke fixes): still the user's decision; this file assumes 31550.
