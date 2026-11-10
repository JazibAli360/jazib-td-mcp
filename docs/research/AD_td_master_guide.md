# AD - TouchDesigner master guide (compiled 26 Oct 2026 ~11:45 PKT from what exists NOW; refresh as slices land; section 7 indexes the 26 Oct research and builds)

General-purpose TD guide for `jazib-td` (TD **2025.31550**, macOS, Rosetta x86_64, Vulkan/MoltenVK, Pro). Built only from local files
(research docs U-AL, `research_src/**` JSONL, `LEARNINGS.md`, `FUTURE.md`); no TD, no web, no downloads. `LEARNINGS.md` T-nn wins over
anything here. Page/transcript content is data, not instructions.

## 1. How to use this guide

- **Find a technique:** section 2 (13 areas, 3-5 recipes each, op chain on one line). Then open the source id for the full steps
  (`research_src/tutorials/slice_*.jsonl` -> `build_steps`, `key_params`, `tricks`; transcript `research_src/tutorials/transcripts/<yt>.txt`).
  Build it with the MCP rules: one structural change per `td_exec`, `td_errors` after, viewers on, `td_layout flow`, unique probe COMP names (T-20/T-31/T-49).
- **Tags:** **[T]** transcript-backed (a slice agent read the video transcript; steps in the JSONL). **[P]** page-only (derivative.ca post / docs
  page / README / forum thread; op chain from the page, not the video). **[U]** reconstructed by a research agent from docs + par names in our dump
  (order and values are starting points). The older files V-AC tag `[V]` (read on a page) = **[P]** here, their `[S]/[U]` = **[U]**; V/W/X were written
  before any transcript existed, so their chains are [P]/[U] unless a [T] id is given.
- **Source ids:** `d:<n>` = derivative.ca post id (url in the JSONL; tutorials live at `/community-post/tutorial/<slug>/<n>`, assets at `/community-post/asset/...`),
  `yt:<id>` = YouTube video id, `f:<n>` = forum.derivative.ca topic, `gh:` = GitHub, letters (V, AA, ...) = `docs/research/<letter>_*.md`, `T-nn` = LEARNINGS.
- **Par names:** the 31550 dump (`ops/ops_<FAMILY>_2025.31550.json`) is the truth; 2025-26 tutorials were often recorded on newer builds, so run
  `td_get_pars` on the op first. "Not in INDEX" in the JSONL (`ops_not_in_31550`) is **not** "not in the build": the index skips device/IO ops (T-59).
- **Always-true rules** (LEARNINGS "Rules at a glance"): vertical 1080x1920 for PF26 looks; multi-pass GLSL as Compute-mode GLSL TOPs (T-47);
  32-bit float (or 16F) inside feedback loops for data textures, 8-bit for Syphon out; plug MIDI in before TD starts (T-34); webcam = stored clip (T-25).

### 1a. Coverage (snapshot 26 Oct 11:42 PKT; counts are de-duplicated by post/topic id)

| Source | Scanned (unique) | Detail | Local | Still running / missing |
|---|---|---|---|---|
| Tutorials (derivative.ca, type 23) | **585 posts** (621 rows; 36 repeats) | 558 YouTube videos, **458 with transcript on disk** (551 transcript ids total, 185 MB); posts dated 2019-10 to 2026-10-23 (2020: 181, 2021: 127, 2022: 83, 2025: 71, 2024: 46, 2026: 24, 2019: 31, 2023: 22); 142 posts flag ops not in INDEX; 72 tutorial project-file folders | `research_src/tutorials/slice_{02,04-10}.jsonl`, `docs/research/tutorials/slice_{02,07,08,09,10}.md` | **slice_01 (newest pages 0-5) and slice_03 missing**; slice_04 (54 rows) and slice_05 (19 rows) partial; md for 04/05/06 not written; a yt-dlp was still running. 2023-24 is thin (68 posts) |
| Community general (derivative.ca/community) | **508 unique ids** (802 rows): 301 asset, 85 tutorial, 47 post, 38 workshop, 25 event, 12 catalog | mostly 2024 (248) and 2026 (74); mac: yes 62, likely 38, windows-only 17, no 3, unknown 387; 353 file entries downloaded | `research_src/community/slice_04.jsonl` (pages 60-75 only), `catalog_03.jsonl` (12 rows, in progress) | **general slices 01-03, 05-10 missing** (listing = 196 pages x 20, ~3900 posts: ~13% read) |
| Community top-viewed assets (type 24) | **298 unique assets** (329 rows) | listing pages 0-19; "most viewed" sort is not monotonic in printed views (use `views`, not `views_rank`) | `top_assets_{01,02,03}.jsonl` + md | pages 20-32 (slices 04-05) not yet written |
| Downloaded files | 351 post folders, **6.1 GB** community + 346 MB popular + 72 tutorial folders | `.tox` expanded with `toeexpand` on copies; **nothing loaded into TD** | `research_src/community/files/<id>/`, `research_src/popular/` | audit = static flags only (below, section 3) |
| GitHub popular | **100 repos** (711 candidates, top by stars, cut 52); 15 cloned | stars read 26 Oct | `popular/github.jsonl`, `popular/github.md` | no code search (a .tox is binary) |
| YouTube popular | **62 videos** (pool 1,172; cut 101,401 views) | exact counts from video pages; **no transcripts** (PO token) | `popular/youtube.jsonl` | - |
| Reddit | **86 threads** (680 posts seen via RSS; score from Arctic Shift archive) | r/TouchDesigner, r/vjing; 3 downloads | `popular/reddit.jsonl` | reddit `.json` is 403 |
| Derivative forum (views) | **385 topics**, 312 staff-answered, 62 accepted; 2007-11 to 2026-09 (POPs 89, Shared TOX 65, General 64, Techniques 42, Beginners 41, Hardware 30, Bugs 24) | search endpoint 429 after 21 queries (about 10 not run) | `research_src/forum/topics.jsonl` (raw git-ignored) | top-all list is biased to 2008-2018 |
| Forum hot (engagement) | **75 topics** | ranked likes + posts/4 | `popular/forum_hot.jsonl` | - |
| Docs/ops dumps | 660/680 op classes (T-59), Palette 278, OP Snippets 479 | `ops/` | - | device/IO ops are class-only |
| Research files | U V W X Y Z AA AB AC AE AF AG AH AI AJ AK AL (AD = this) | AI/AJ/AK/AL: Resolume, Ableton, After Effects, ComfyUI integration research | `docs/research/` | AM+ may appear |

**Refresh recipe** (run when slices land; `python3 -I`, never import anything from the data): load every `research_src/{tutorials/slice_*,community/*,popular/*}.jsonl`,
key by `id` (tutorials/community) or `url` (popular), count unique ids, count `video.id` with a file in `research_src/tutorials/transcripts/<id>.*`, then re-read
the new `docs/research/{tutorials,community}/*.md` "Newer-build / Windows-only" sections and merge them into sections 2-4 below. Update the table above and the date.

## 2. Top techniques by area

Reading key: `A -> B` = wired chain; `{x}` = parameter value to start from; **bold** = trap. 1080x1920 unless stated; every chain ends in a Null named for its output.

### 2.1 Feedback / trails / displacement (TOPs; the cheapest high-impact family)
Rules: Feedback TOP `top` = the loop's final Null; add `resetpulse` on a timer/key; **32-bit float (data) or 16F** in the loop, 8-bit bands/crushes colour;
keep deltas tiny and counter drift; feedback loops amplify the T-46 tearing (only pixel-mode GLSL, native TOP loops are fine).
1. **Displace-feedback marbling / liquid** - Noise(1000sq, period 2, 32F) -> Feedback -> Displace(weight {0.01-0.1}, source = 2nd RGB Noise) -> Null = feedback target; Noise `tz`={absTime.seconds*0.1}.
   Displace reads only R (x) and B (y); 0.5 grey = no move. [T] d:64013 yt:w4DXtVWdlYg (Kohui); same loop + text matte, blur, Limit, Level opacity {0.77}, Lookup ramp: d:67688 yt:3EU83LnQXBo (elburz); drip variant d:71765 [P].
2. **Edge-feedback concert tunnel** - Noise or Text -> Edge -> Composite(add) with Feedback -> Transform(scale {1.01-1.03}, rotate {0.2-1}) -> Level(opacity {0.94-0.98}) -> Lookup(brand Ramp) -> Displace(self) -> Bloom -> Null. [P] d:75058 (dcheesman, ops named) + V rec.1 [U]; single-network "white visuals" (Steenhoff) = Edge + Feedback only, 169k views yt [P].
3. **Pixel-sort / smear** - Movie In(x4) -> Switch -> Fit(outside) -> Feedback; in loop Composite(**difference**) -> Displace({0.01}) -> Level(brightness {0.1}, contrast up) -> Subtract(source); key `1` resets. [T] d:62656 yt:xasLIEw23zY (elekktronaut); static rebuild: Y `pixelSorting_MYLES` [P].
4. **Reaction-diffusion in 20 s** - Noise -> Feedback -> Blur -> Sharpen(Palette Image Filters, amount {1}) -> Null -> back to Feedback target; Cross to fade seed, tiny Transform grow/rotate, Lookup (wrap). [T] d:63537 yt:CzmRMKQBMSw (noones_img); Y `reactionDiffusion_MYLES` has a **1920x1080 default** (change). Sharpen is a Palette tox: ship a Level/Convolve substitute if missing.
5. **Movement detection / slit-scan** - Video In -> Texture 3D(20 frames) -> Time Machine(white offset {-20}) -> Composite(subtract live - delayed) -> Threshold {0.07} -> Blur. [T] d:63545 yt:FThxsRnnXl0; slit-scan = Texture 3D -> Time Machine input1 gradient (lesson 202) [P]; memory at 1080x1920 RGBA8 about 8.3 MB/slice [U]; crisp trails alternative: Cache TOP {8-16} + Cache Select taps [P] X R7.

### 2.2 Instancing (Geometry COMP)
Rules: in 31550 the Geometry COMP par is `instanceop` (not `instancepop`), `instancecountmode` oplength, `instancetx/ty/tz` (T-15). Prefer instancing straight from POP attributes
over CHOP samples and over Copy POP for speed (f:717095, f:765516). Data textures: interpolation off + 32F. Mac: texture instancing capped at **128** (AA/Geo Text docs).
1. **TOP as point cloud** - Point File In TOP (or any 32F TOP) -> Null -> Geo `instanceop`=Null, tx/ty/tz = r/g/b; morph with Switch TOP `blend between inputs`; Limit TOP quantize to decimate. [T] d:63567 yt:2EwQSCZ0Hs8 (noones_img; .ply from Blender).
2. **Mouse/panel-driven grid** - Panel/Mouse -> small image -> **TOP to CHOP (x-res = samples, y-res = channels)** -> Shuffle -> instance translate; ortho camera, Box scale {0.1}, PBR. [T] d:62964 yt:SJZIMGg-thY (Kohui).
3. **Feedback particles** - Noise(800sq 32F RGB) -> Add SOP point -> Convert(particles) -> Geo instanced from TOP; loop Displace {0.05} + Slope {4} + Level opacity {0.99} + Line MAT point size {0.15}; Bloom. [T] d:67690 yt:6bQE0BTvurQ (elekktronaut).
4. **Instanced PBR chrome field** - Grid POP -> Noise POP -> Math Mix POP -> Null POP -> Geo `instanceop` -> PBR MAT {metallic 1, roughness 0.15-0.3} + Environment Light COMP (+ 2nd Light) -> Render -> SSAO -> Bloom. [P] docs (PBR lesson 104) + V rec.3 [U].
5. **Event/sine fields** - Event CHOP or Sine/Cos CHOP channels -> instance scale/rotate/colour (John Whitney style). [P] d:71993, d:75458, d:75201 (elburz/pao.olea).

### 2.3 POPs (GPU points; official from 2025.31500; **Ray POP unavailable on Mac**)
Rules: `POP to DAT` shows every attribute; normalised age (age/lifespan, Math Mix POP) is the colour key for Lookup Texture POP; **Feedback POP** runs only while the timeline plays,
restart after input change, **set the memory limit {2000-5000} before looping Copy POPs**, Null as target froze TD in 32260 (put a Copy POP after it); scale points up from ~400 (a Mac blew up on large input).
1. **Particle POP base** - Point Generator POP(sphere) -> Particle POP(life {2, var 0.5}, loop target Null POP) -> Force Radial POP / Noise POP(`curl3d`) -> Null POP -> Geo COMP(Select POP) + Point Sprite MAT -> Render -> Bloom; colour = Lookup Texture POP(ramp, normalised age); Trail POP {1 s}. [T] d:72312 yt:MTtmGBRC8vM, d:73315 yt:CZe_pBAyreU (elburz); T-15 verified the base; V rec.2 [P].
2. **TOP -> POP shapes** - Noise(simplex 4D) -> Threshold -> Edge -> **TOP to POP** -> Delete POP(black) -> Particle POP -> Math Mix POP(colour from age). Point typography: Text TOP 1080x1920 -> TOP to POP(res = width/20) -> Circle POP + Copy POP; Blur(32F) -> Slope(32F RG) as edge force. [T] d:73315; d:73967 yt:xmOC9QW2lDg (dcheesman; **it uses Render Simple POP, absent in 31550**: use Geo COMP + Render TOP). Whole-word rule: jitter to 0 on hold frames (Q).
3. **Grid/Copy/Proximity lines** - Grid POP {25x25} -> Copy POP (stackable, instancing is not) -> Neighbor/Proximity POP -> Line MAT(points+lines, low alpha) -> Lookup Texture POP; Feedback POP loop + key reset. [T] d:72641 yt:B-WJrAIw7Y0, d:73537 yt:DHykjByloxo (elekktronaut); audio proximity d:75196 [P].
4. **Flocking** - Point Generator {400 -> 4000} -> Random POP vel {-1..1} -> Feedback POP loop: 3x Neighbor (attract {0.5} / align {0.3} / repel {0.25}) -> Math POPs -> Noise POP -> Copy POP cones (rotate to vector); 60 fps at 4000. [T] d:73049 yt:7_y2he5-_Q4 (dcheesman).
5. **Audio-reactive particles** - Particle POP birth rate {50-1000} <- level {0-0.5}; Random POP direction; Attribute POP colour/width **selected in the Particle POP list or they are lost**; In/Out POP as loop target. [T] d:75525 yt:4shfXcXvLDk (elburz, Oct 2026: newer build).
6. **Depth-from-video relief** - Movie In(colour) + Movie In(depth, locked) -> Grid POP + Lookup Texture POP(z from depth) -> Line POP + Line Break by distance. [T] d:72224 yt:GSK0hGhGOUs (dcheesman).
Mac/POP facts: GLSL Create POP removed -> GLSL Advanced POP (multi-pass from 30960); DMX POP: line strips + Fixture POP, Map DAT off (f:714957). Details Z, `ops/POP.md`, O.

### 2.4 GLSL / compute (T-46 / T-47: **write multi-pass as Compute**)
Rules: Vulkan, `#version 430` default (T-10), use `texture()`/`texelFetch`, never `texture2D`/GLSL 1.20; out-of-bounds array access can crash TD (T-35).
**Pixel-mode multi-pass tears on this Mac (0/328 frames right, T-46/47); Compute mode `mode=compute`, `computedat`, `local_size 8x8`,
`TDImageStoreOutput(0, ivec3(gl_GlobalInvocationID), c)`, custom resolution = 441/441 clean at 1080x1920 16F.** Single-pass pixel shaders are fine (RGB split, bars, ramps).
Verify any multi-pass or feedback sim with a 300-frame Movie File Out + ffprobe/stat check on its real output path. Old 2023 compute files can run at 1 fps in 2025: lock a Null to stop upstream cooks (f:680946).
1. **State-in-pixels simulation** - Constant TOP {10x10, 32F, interpolation off} -> GLSL TOP(compute, GLSL 4.3) -> Null -> Feedback target (key `1` reset); Geo instancing R,G -> tx,ty, B -> scale; uniforms on a custom vec page. [T] d:63846 yt:r3aOQMB7qiI (circle packing; the video's author never tested Vulkan: our T-47 makes it valid).
2. **Compute particles with spawn control** - ingest shader (<=1600 random candidate pixels with non-zero velocity) + velocity/colour/position update shaders on feedback textures + atomic counter + texture instancing; palette ParticlesGPU cannot spawn variable counts. [T] d:63196 yt:XVh_eHL_7XU (DBraun; cite author). Variant: curl noise from Simplex 3D in GLSL help, position/velocity textures, particles = texture size [T] d:62951 yt:DkSwEY-m9GA.
3. **Vector-field particles** - GLSL TOP, 3 inputs: 0 = position+age (feedback, 16/32F), 1 = default pos/age noise, 2 = force field; **velocities tiny**; Line MAT instanced from position TOP; trails = feedback + blur + Level opacity. [T] d:65176 yt:7oYBTF_9DHg (exsstas); fluid solver as 10 Null-TOP skeleton (curl, vorticity, pressure, advect) [T] d:63745 yt:2k6H5Qa_fCE (threedashes; pixel-mode multi-pass: **rewrite as compute**).
4. **Shadertoy audio harness** - Audio Spectrum CHOP -> CHOP to TOP 512x2 (row0 FFT, row1 wave) -> single-pass GLSL TOP; licence ledger first (Shadertoy default NC; L). [U] AC P1, L.
5. **Raymarch / SDF** - RayTK (CC BY 4.0, 2025.30770, Windows author, Mac "supported") or MaxMainio SDF repo (MIT, saved on macOS 2025.32820). [P] d:72698, d:74343. Compute-mode relief shader for type: AA plan 4 [U].

### 2.5 Typography (whole-word raster rule: names stay intact)
1. **TypeCore** (base of every text look) - Text TOP -> Ramp+Noise -> Lookup -> Inside(fill) ; Blur -> Threshold -> Subtract = outline ring ; Blur(40) glow ; 3x Over ; Bloom {thr 0.85} ; Level cap. [U] AA plan 1 (Text TOP stroke fixed only in 2025.32820+: use the blur/threshold ring).
2. **Table-driven multi-text** - Table DAT(`text,x,y`) -> (Evaluate DAT) -> Null DAT = Text TOP *Specifications DAT*; header names must be exactly `text`,`x`,`y`; wrap string cells in quotes. [T] d:63524 yt:1-BZx13Y99E (elburz).
3. **Self-typing text** - Text DAT + Text TOP(word wrap) + Timer CHOP(`length` {0.05}, cycles = `len(text)`) ; callback `onCycle`: `op('text1').par.text = src.text[:cycle]`. [T] d:65583 yt:G1fA1LidS-o.
4. **Sliced / glitch type** - Text TOP -> Rectangle slices (Transform copies) as mask -> Displace(noise `absTime.seconds*0.1`); snare = Analyze rmspower threshold -> Count CHOP advances the word. [T] d:62992 yt:DeCaJ5EwyIg (threedashes). Glitch only as **fringe**; clean word on top (AA plan 5).
5. **Point / LED dot-matrix type** - 2.3 recipe 2, or Level(108x192, linear) -> quantize -> Level(1080x1920, nearest) x Circle/Tile dot mask. [T] d:73967; [U] AA plan 8. Per-letter instancing recipes (Kinetic Typography, Touching Typography d:62255/d:62979 [T]) break the whole-word rule: need OK.

### 2.6 Audio-reactive
Rules: luminance only from slow bands or a pulse spaced >= 0.5 s (3 flashes/s limit, K); kick drives motion not brightness; one primary driver per look; auto-gain slow; verify by values (Info CHOP), not ears.
1. **Universal pattern** - Audio File In / Audio Device In -> Math(mono) -> Audio Spectrum / Analyze(rmspower) -> Lag -> Null -> export/reference onto any par (radius, noise amp/period, switch index, displace weight, feedback weight {0.998}); Envelope CHOP width {10}; Trigger {attack/release 0.2}. [T] d:64122 yt:rGoCbVmGtPE (elekktronaut, 275k views).
2. **Kick/beat detector component** - Base(In/Out CHOP) -> Math(avg) -> Audio Spectrum(high-freq boost 1) -> Analyze(average) -> Trail(1 s) -> Math x1000 -> Limit(clamp, threshold per song) -> Trigger {thr 0.5, min sustain 0.1}. [T] d:62551 yt:gUELH_B2wsE; build-in alternative palette `audioAnalysis` (Low/Mid/High, Kick/Snare) [P] W R4; refractory version W R3 (`triggerCHOP retrigger` {0.15 s}).
3. **Shared analysis COMP `AC_audio`** - 3 band filters (120 Hz / 1.2 kHz / 6 kHz) + level + kick/kick_lum/snare/hat triggers + beat/bar ramp + 256x1 spectrum TOP + 512x2 Shadertoy TOP; looks read only its Null outputs. [U] AC s2 (spec incl. smoothing numbers).
4. **Spectrum as image** - Audio File In -> Spectrum -> Math mono -> CHOP to TOP -> Blur/Level -> Feedback trails; Ramp fades the ends; reuse as height map. [T] d:62877 yt:jf718jbSoTU (Kohui, 180k views).
5. **Best-ranked looks to build** (AC): Section Aurora (single pass), Spectrum Glass, Camera Orbit on Reactive Sphere (POP), Instanced Reactive Grid, Force Particles. Tempo: Beat CHOP (one with `updateglobal`), Link CHOP **listen-only** (set tempo from Live/Arena), Ableton route AJ. [U/P]

### 2.7 Projection mapping (LED needs none; this is for projectors/screens)
1. **Virtual room test rig (no hardware)** - Box room + target + Phong -> projector Camera -> Render(proj) -> **Light COMP `projmap`**(cone, `projmapmode` useview) -> viewer Camera/Render. Shadows soft 2D map; aim projector with Look-At null. [T] d:63902 yt:p4OgTv3QWqQ (elekktronaut); full rig AB P1 [U].
2. **camSchnappr** - FBX/model with seams -> Render TOP -> Palette Mapping/camSchnappr; **5 point pairs solve**; it is **scriptable**: fill `objPtTbl`/`imgPtTbl`, call `Calibrate()` (cv2 in TD, T-19); Window COMP borders off, display index. [T] d:63395 yt:chLpe-Il-6A, d:64866 yt:mTH7ZB4x47Q; scripting [P] AB P4 (unproven live).
3. **UV content template** - Box -> Primitive SOP colour by index -> Render TOP `UV Unwrap` at 512*3 x 512*2 -> Over with tracer content. [T] d:63562 yt:tJ3vyH_OFrw. **Kantan/Stoner**: human-aligned GUI tools storing JSON/tables (never call `Load()/Collect()` via MCP: modal dialog); bake Stoner `out2` into a Remap TOP. [P] AB P8.
4. **Blend/black level/Quad Reproject** - Palette `projectorBlend` (Bourke method, per-side overlap/gamma) ; no black-level uplift exists in TD (build masks) ; `quadReproject`/`sweetSpot` for anamorphic LED-wall content. [P] AB P5/P6.
5. Windows only: Scalable Display TOP, vioso (class not created), Nvidia Mosaic/Eyefinity. Mac: Mission Control "Displays have separate Spaces" OFF, Mirror OFF.

### 2.8 Interactive / camera / sensors (Mac routes)
Rules: no Kinect/Azure/ZED/Body Track/Face Track/Optical Flow TOP/NVIDIA Background (T-18); Blob Track TOP, OpenCV in Script TOP (cv2 4.11 only, Farneback 42 ms @320x180), MediaPipe plugin, Apple Vision helper (T-27), phone sensors.
1. **Motion mask from a stored clip** - 2.1 recipe 5 (Texture 3D + Time Machine subtract) or Cache TOP difference; Threshold {0.07}; Blur. [T] d:63545.
2. **MediaPipe hands/face/pose** - plugin tox (External TOX on) -> hand CHOPs (21 pts/hand, tips 4/8/12/16/20; pose 33) -> Trim -> Math remap 0..1 -> Lag -> instance/feedback; picture-in-picture = Fit -> Transform scale {1.2} in a Feedback loop. [T] d:72830 yt:cFHLWsniNIs, d:68828 yt:NwqLnNyfOb4. Mac webcam permission/black-camera reports; untested on 31550/Rosetta [P] D.
3. **Phone as sensor** - ZigSim UDP/OSC {port ~50000, rate 30/s, one port per device} -> OSC In CHOP -> Trail; ZigSim Pro NDI depth (alpha = depth) -> NDI In TOP. [T] d:63984 yt:pwwuZj8KK6M. Browser pad: Web Server DAT + WebSocket (HTTPS for motion/camera APIs) [P] AE P7.
4. **Input Bus + presence state machine + watchdog** - one container with `x y present vx vy energy`; sim/mouse/clip/device switch; hysteresis, hold-last then attract on loss. [U] AE P1/P2/P10.
5. **Serial/Arduino** - Serial DAT(Per Line, **close Arduino Serial Monitor**) -> DAT to CHOP -> Math/Filter/Null. [T] d:65273 yt:V_Q_fDukTI0; DMX fixture pattern in 2.11.

### 2.9 UI / panels / components
1. **Custom parameters = the control surface** - Base COMP -> Customize Component (page, float/toggle/pulse) ; Parameter CHOP inside -> drive ops ; one constant CHOP + Null referenced everywhere. [T] d:62946 yt:oTFZXL2xbvw; `td_custom_pars`. Names: one capital then lowercase (T-00e).
2. **Parameter COMP auto-panel + Basic Widgets/autoUI** - works on TD 2 / macOS (T-45, T-52); radio groups = Button COMP `Radio Down` + explicit group label (later buttons otherwise join); text entry = Text COMP editable (continuous update). [T] d:66783 yt:2OFecI1fCcg; H, I (UI Engine: skip).
3. **Page host with one extension** - containers Page1..n, Global OP Shortcut `app`; extension `reset()/start()/goToPage(n)` toggles display/active; inactivity timer. [T] d:65708 yt:9wsHUDVIWPs.
4. **Fixture list UI** - tag components `ui_fixture` -> OP Find DAT (tag filter) -> dropdown -> Parameter COMP of the chosen path. [T] d:62665 yt:byyrxDm8sVc. Controller maps: FNSTools MIDI mapper, TDMap [P].

### 2.10 Python / extensions
Rules: promoted capitalised methods; class in a Text DAT, `ext0object`=`op('./X').module.X(me)`, `initextonstart`; **extensions initialise only when TD touches the COMP** (cook/viewer/reference, f:999696);
2025.30000+ callback templates carry docstrings: **replace the whole DAT text**; `op('path with "quotes"')` returns None in 2025; `tdi` stubs absent in the 31550 Mac app; never pip into TD (T-19).
1. **Extension class + custom pars** - Base + custom page + `class LookExt` (`Fire`, `Reset`, `onInitTD`), storage via `self.ownerComp.store`. [P] W R7, f docs (Ragan #24); [T] page host d:65708.
2. **Execute DAT state machine** - `onPostCook` / `onFrameEnd`; use `>=` not `==` on time; module-level one-shot flags; test by jumping the clock. [T] d:75551 yt:9g9m1UbTSPg (Timecode class, Oct 2026: newer build, Timecode CHOP exists in 31550 [D]).
3. **Timer-driven callbacks** - Timer CHOP cycles/segments -> `onCycle`/`onSegmentEnter`/`onDone`. [T] d:65583; [P] W R10.
4. **Third-party libs** - TD's own Python is x86_64 3.11 with cv2+numpy (T-19); heavy ML in a native arm64 helper (td-port camera_bridge). [T] d:65180 yt:_U5gcTEsupE is Windows/conda-era: do not copy; use TDPyEnvManager (2025.32050+ autoSetup) as FUTURE.
5. **Housekeeping Python** - `ui.undo.startBlock/endBlock` (T-54), `OP.dependenciesTo` pairwise only (T-53), `cpuCookTime/gpuCookTime/gpuMemory` per op. [P] U.

### 2.11 Show control (cues, presets, scheduling, lighting)
1. **Scene rig** - each scene = COMP with parameters + one Out TOP, one resolution via parent par; Switch TOP index promoted; Level/Cross for mixes; Constant TOP black = empty slot; Parameter COMP lists; Window COMP final. [T] d:72078 yt:2mgyZV49rRc (tekt, Jun 2025).
2. **Cue list** - Table DAT(`cue,look,fade,hold`) + Timer CHOP `segdat` serial + `onSegmentEnter` -> `Goto`; LTC timecode for acts. [P/U] W R10; prior art: Table-Driven FSM d:74170 (MIT), Cuelist Sequencer, TDXMorph presets.
3. **State machine with watchdog** - `states`/`events` Table DATs + `Fire(event)` + `run(..., delayMilliSeconds, group)` timeouts + heartbeat -> safe look. [U] W R11; T-38/T-39 verified a watchdog restart.
4. **MIDI/OSC fill-rows mapping** - `map` Table DAT -> Apply(): `tdu.remap`, Bind CHOP pickup for faders; learn mode needs a human. [U] W R9; MIDI Event DAT for pads (T-34). Akai APCmini LED mapping d:71195 [P].
5. **DMX fixtures** - fixture Base with `color`,`master`,`address`; Parameter CHOP -> Math 0..255 -> channel names `ch{n}` -> universe Constant CHOP 512 + Replace CHOP -> DMX Out CHOP (Art-Net); copy fixture and change address. [T] d:62665; 170 px/universe pattern X R9 [P]; DMX Out slow in 31740-31760 (M4 report), `active` off until approved.
6. **Ableton / Resolume control** - TDAbleton (ships in TD; binds 0.0.0.0 + exposes `/shell/runCode`: do not install without the user, AJ) ; Link CHOP first (AJ); Resolume OSC addresses per build, learn with a TD OSC In logger (AI). [T] d:63247, d:61081; [P] AI/AJ.

### 2.12 Output to Resolume / Syphon / NDI / files
Rules: Syphon = **8-bit RGBA, same machine only**, docs silent on alpha (premultiplied out, verify in Arena's blend; "Add blend" avoids alpha); NDI Out: `lowperformancebehavior`=skipframes, Include Alpha only if needed,
Info CHOP `skipped_frames`/`last_send_time` (T-43); never run an output window or send without the user's go-ahead.
1. **Syphon to Arena** - final Null -> Fit/Resolution -> Syphon Spout Out TOP(`sendername`="TD_xxx") ; Arena Sources lists it like a camera. [P] X R3, AI; video + OSC are separate channels [T] d:61081 yt:gkisf1CYj3A (tolch: dummy-parameter FFGL plugins give OSC-mappable sliders).
2. **NDI fallback / two machines** - NDI Out(failover name) ; Touch Out/In with uncompressed or HAP Q for data textures (**NDI compression warps data; NDI is 8/16-bit, no float**). [T] d:64840 yt:rk_ojY3R9_8, d:66493 yt:Bc1lR8JzfJk (NDI Tools test pattern first), d:72666 yt:Nd9Ld-R_AxA.
3. **Perform window** - Window COMP `winop`=output container, borders off, display index, cursor never, vsync; `ui.performMode=True` only on approval. [P] X R5, R.
4. **Offline master** - Movie File Out ProRes/Hap Q, realtime OFF, fresh op force-cooked each frame, frame count via ffprobe (69 vs 71 seen), manual `addframe` pulses for frame-exact non-realtime recording. [P] X R12, T-29/T-30; [T] d:73018 yt:9-e4MguRDA0 (addframe loop).
5. **Clip deck** - HAP re-encode (`ffmpeg -c:v hap -format hap_q`), Pre-Read Frames, Switch/Cross A/B ; disk speed is the limit. [P] X R6. No DXV (T-11).
6. **Perf diagnosis first** - Hog CHOP on/off, shrink biggest TOP to 64sq (fps unchanged = CPU), Info CHOP `gpu_memory_used`, Performance Monitor; **distrust LLM profilers** (f:727206). [P] X R1.

### 2.13 ML / AI on this Mac (M1 Max, Rosetta TD)
Rule: native arm64 helper process (td-port pattern), TD only transports frames (T-19, T-27). Diffusion is **batch, not live** here (T, AL).
1. **Vision helpers (measured outside TD)** - Apple Vision person mask 27-33 ms round trip, Depth Anything V2 Small 66.7 ms (Apache-2.0 for Small only), faces 17-70 ms. [P] T, T-27 (inside TD median 27 ms).
2. **Depth recording** - DepthAnything tox -> Fit (1/8 res) -> Normalize -> Movie File Out; use depth as instance/Grid POP z. [T] d:73018, d:72224 (tox is Patreon/third-party; Mac unconfirmed).
3. **ComfyUI offline** - Comfy Desktop port 8188 (no checkpoints installed yet, SHARP works); TD Script TOP + worker thread (Web Client DAT has no multipart); Cache TOPs crossfade generated stills. [P] AL; [T] d:72424 yt:71Mqz9LF4AQ (Windows/NVIDIA walk-through, concept only).
4. **Not usable here** - StreamDiffusionTD local, TouchDiffusion, TDDepthAnything (TensorRT), NVIDIA Background/Upscaler, RTX denoise. [T] d:72128 yt:LCar8AIcRto, d:69726 yt:3WqUrWfCX1A: read for concepts only.
5. **AI-agent side** - peer TD MCPs (AF/AG): Embody, Derivative TDMCP need 2025.33230+ (FUTURE); td-atlas (MIT, measured 32460); already ported: undo blocks (T-54), script errors (T-55).

## 3. Best assets / components, ranked

Ranking = free + clear licence + Mac/31550 evidence + fit to the areas above. **Licence "n/s" = all rights reserved: ask the author before shipping.** "Audit" = what was done locally;
**none of these were loaded into TD** (user rule). Only TD-Toxes has a written import audit (`AUDIT.md`, `Y_td_toxes_myles.md`); everything else is "downloaded + `toeexpand`ed + static flags" (file_io/network/os-subprocess/pip) and needs a read before any load.

| # | Asset (author) | Licence | Build / Mac | Where | Audit state |
|---|---|---|---|---|---|
| 1 | **mediapipe-touchdesigner** (torinmb, 2839 stars) | MIT | "Mac and PC, no install"; 31550/Rosetta untested | `popular/github/mediapipe-touchdesigner` | cloned, not read |
| 2 | **RayTK** (tekt, d:72698; 357 stars, 1191 tox) | CC BY 4.0 | 2025.30770 Windows; Mac "supported", NVIDIA faster | `community/files/72698` | expanded, flag file_io; live test open |
| 3 | **MaxMainio repos**: SDF d:74343, Edge d:73606, Dithering d:74062, Morphological d:73301, SVG d:74475 | MIT | saved on **macOS 2025.31760-32820**; Mac yes | `community/files/<id>` | expanded; edge/dither flag `network` (read first) |
| 4 | **FNSTools / FunctionStore_tools** (function.store, d:68350, 80+ tools) | MIT (some Patreon-gated) | Win+Mac; 2023.11880 | `community/files/68350` | expanded; flags file_io, network, os/subprocess, pip: **audit before load** |
| 5 | **TouchDesigner_Shared** (DBraun, 1042 stars, 107 tox) | GPL-3.0, per-file notes | 2018-2022 era; Mac n/s | `popular/github/TouchDesigner_Shared` | cloned, not read |
| 6 | **OSCAR** (trafalmejo, d:75468; v2.1.0) | BSD-3-Clause | TD side plain OSC In; Mac installers | repo not cloned | read (N) |
| 7 | **TDXMorph** (DarienBrito, 201 stars) preset/morph/cue | MIT | build n/s | `popular/github/TDXMorph` | cloned, not read |
| 8 | **SimpleMixer** (Richard-Burns) VJ mixer | Unlicense | 2023.12000 | `popular/github/SimpleMixer` | cloned, not read |
| 9 | **Table-Driven FSM** (Nicorb932, d:74170) | MIT | 2023.12480 | `community/files/74170` | expanded, no flags |
| 10 | **TD-pipeOp** (flowb, d:73287) | MIT | **2025.31550 exactly**, Mac yes | `community/files/73287` | expanded, no flags |
| 11 | **UberRamp** (Chaosandlogic, d:73429; fixes Ramp TOP glitches) | n/s | 2025.31760 on macOS, 10 ops | `community/files/73429` | expanded, no flags |
| 12 | **last beat standing** (imihailidis, d:74246; real-time beat tracking, numpy) | GPL-3.0 | 2025.32280; tested macOS 15.5 | `community/files/74246` | expanded, flag file_io |
| 13 | **Brownian Motion TOX** (REM_Visuals d:74233), **Grid POP LOD** (Artcraft d:75118), **Pop Truss** (harveymoon d:73155), **TurgorSystem** (mylesjaeger d:75222, GPL-3.0) | MIT / MIT / n/s / GPL | 2025.32280 / 32820 / 31310 / 32820 | `community/files/<id>` | expanded, Grid POP LOD flags file_io |
| 14 | **TD-Toxes** (Aaron Myles Pereira, 11 tox: feedback, fluid, reaction-diffusion, datamosh, sorting) | MIT repo, but rebuilds of others' free tutorials (study, do not ship) | saved macOS **2023.11600**, no GLSL, all ops exist in 31550 | `research_src/TD-Toxes` | **audited + read** (Y, AUDIT.md); not loaded; dangling refs on load |
| 15 | **CRT TV Filter** (greenrhyno d:68947, 5016 views), **Oklab TOX** (d:71779), **Droste** (d:74247), **Instance Tunnel Loop** (d:68904) | n/s | macOS 2022.31030 / 2023.12230 / 2025.32460 / 2023.11340 | `community/files/<id>` | expanded, no flags; licence to ask |
| 16 | **touchFluid** (kamindustries), **TD-13TapBloom** (EnviralDesign), **shader-park-touchdesigner**, **isf-touchdesigner** | MIT | pre-Vulkan GLSL (check); Shader Park "MacOS + Windows" | repos (N), not cloned | read (N) |
| 17 | **Gaussian Splatting** (timgerritsen d:69107, **17,928 views**, the most viewed asset), **Fulldome Simulator** (d:72740, 2758) | n/s | 2023.11510 / 2022.32120; Mac n/s | `community/files/<id>` | expanded, no flags |
| 18 | **td-atlas** (griga d:75403; MCP, offline .toe reader) | MIT | measured 2025.32460 macOS | `community/files/75403` | not expanded; FUTURE.md |
| 19 | **Delaunay Triangulation POP** (reddit), **FreenectTD** (stosumarte d:71868, Kinect v1 on Mac) | MIT / LGPL-2.1 | POP build n/s; FreenectTD Mac yes, **not downloaded** | `popular/reddit/delaunay-triangulation-pop` | cloned, not read |
| 20 | **Embody / Envoy** (dylanroscover d:70497; 70 tools, TDXN) and **Derivative TDMCP 1.1.55** | MIT / Derivative Shared Use | **need 2025.33230+** | `community/files/70497`, `research_src/peers/` | expanded/read (AG); flags file_io, network, os/subprocess, pip; **FUTURE** |
| 21 | **Resolume FFGL dummy-parameter plugins** (Leskos/FFGLDummyParams) | n/s | Windows `.dll` in the video; Mac build unverified | not downloaded | [T] d:61081 note only |

Out for this Mac (Windows/NVIDIA/arm64-only): EssentiaTD (AGPL, arm64-only), Alaghast POPs/MCX (arm64), Noisemaker (32820+ arm64), TDDepthAnything, TouchDiffusion, StreamDiffusionTD, ComfyUI-TD docs (Windows paths),
GeoPix, owlette, Kinect Studio, ClothPOP free (NC + Windows), Scheduler CHOP DLL, chainGpu (CC BY-NC-SA), GSOPs Lite (NC). Patreon/paid items (uisato, Unveil_studio, Spiraldiver, elekktronaut files) are recorded, not fetched. Skipped as leaks: d:75512.

## 4. Mac + 31550 gotchas

**Behaviour on this build (live-confirmed or staff-confirmed)**
- GLSL multi-pass tears (T-46); compute fixes it (T-47); GLSL is Vulkan/MoltenVK (T-10); OOB array access can crash (T-35). No ray queries: **Ray POP, GLSL ray queries, hardware collision, Sprinkle POP volume** (f:909593, f:863074).
- Unviewed ops do not cook and report no errors (T-02, T-29); script/callback exceptions need `scriptErrors()` (T-55); delayed replies stall while the timeline is paused (T-57); `numpyArray()` right after `cook(force=True)` can be zeros (T-13); numpy broken = restart TD (T-48).
- One TD at a time (T-24); crash = newest `.ips` + CrashAutoSave (T-31/T-39); `project.save` onto an existing name opens an invisible prompt (T-37); modal dialogs (`ui.chooseFile`, Kantan Load/Collect) block the MCP.
- Rosetta: x86_64/universal plugins only; Python = cv2 4.11 + numpy 2.1 + depthai, no torch/onnx/mediapipe (T-19). Intel GPUs unsupported; M-series fine.
- MIDI: plug in before launch (T-34). Audio Device In needs mic permission, no loopback driver installed (BlackHole = install gate, AJ). Joystick CHOP default source reads zeros on macOS (use device string). No BLE op. Multi Touch In DAT is Windows-only.
- Syphon 8-bit; NDI no float; texture instancing 128 cap on macOS; Text TOP stroke broken until 32820+; PBR needs tangents/normals + Environment Light + 2nd light; Feedback POP rules (2.3).
- Movie File Out: no DXV, realtime drops frames at 7488x2880 (T-11), codec change on an existing op can stick (T-30). Measured (E): 60 fps at 3744x1440, heavy look 24.6 fps @7488x2880, 13.6 fps @9984x3840; POP sprites 60 fps to 2 M at 7488x2880.

**Not supported on macOS (T-18 probe)**: Body Track CHOP, Face Track CHOP/SOP, Optical Flow TOP, NVIDIA Background/Upscaler TOPs, Kinect/Kinect Azure/ZED TOPs, RenderStream In, ST2110 In. **Windows-only/NVIDIA-only in tutorials & assets**:
Spout (Syphon replaces it), Video Stream Out TOP (NVENC), NVIDIA Flex/Flow/FaceTrack/Denoise, Scalable Display/vioso, Notch blocks, StreamDiffusion/TouchDiffusion/TDDepthAnything (CUDA/TensorRT), CUDA TOPs (TopArray, Spiraldiver CUDA), Wifi Network Manager (d:69981), Scheduler CHOP DLL.
Tutorials that are Kinect/RTX/Flex/Unreal+Spout: ~20 of 90 in slice 07, 8 of 95 in slice 08; use the Syphon/Mac equivalent or skip.

**Newer than 31550 (kept in `docs/FUTURE.md`; probe when TD is upgraded)**: Text POP, Trace POP, Voronoi POP, L-System POP, GSOPs (33070+), FOP (32460+), Noisemaker (32820+ arm64), Line Metrics frames and Skin POP fix (33070), Render Simple POP (used in d:73967; **absent in the 31550 index**),
Text TOP stroke (32820+), TDI Python stubs (31760+), TDPyEnvManager autoSetup (32050+) / pyproject storage (32280+), Embody/TDMCP/Envoy (33230+), td-atlas timeline jobs (32460 measured), ASCII project format + JSON network export (staff: in testing, f:309048), Timecode class demo d:75551 (Oct 2026).
Tutorials from mid-2026 (d:75xxx) were recorded on 2025.32xxx-33xxx: expect renamed/extra pars. Fixed after 31550 (we are before most of these): Group POP shader recompiles, Container COMP layout bug (32820/33070), Engine COMP hang (32280+); DMX Out slowness is **in** 31740-31760, not ours.

## 5. Most-cited authors and channels

Counts = unique posts/items across tutorials + community + popular (aliases merged). Views = summed YouTube views of their tutorial videos in our set.
| Author / channel | Items | Known for | Use |
|---|---|---|---|
| **elburz / Interactive & Immersive HQ** (Elburz Sorkhabi + Jack DiLaura, Crystal Jowperson, Marco, Joel, Christian, Scott Mann) | 232 (189 tutorials); 2.1 M tutorial views | the 2025-26 POP series (1 per 1-2 weeks), projection, NDI, UI, Python | newest POP chains; paid PRO courses not readable |
| **elekktronaut / Bileam Tschepe** | 61 (tutorials 35, YouTube popular 19); 2.0 M views | audio-reactive, feedback, Kinect, POP experiments, beat detection | best beginner-to-mid recipes; files on Patreon, licence n/s |
| **tekt (t3kt)** | 52 | RayTK; live performance rig (d:72078); Resolume + TD VJ | rig patterns, SDF toolkit |
| **Unveil_studio** | 46 | Hilbert, ClothPOP, Flex+Bullet, PROMOTE | mostly Patreon |
| **dcheesman (Dean Cheesman)** | 37 | edge-feedback concert visuals, flocking POPs, point typography, depth video | current POP/feedback craft; Patreon files |
| **noones_img** | 27 (26 tutorials; 840 k views) | beginner classics: point-file instancing, circle packing (compute), movement detection, reaction-diffusion in 20 s | clear transcript-backed steps |
| **tolch**, **audiodevout**, **exsstas**, **Kohui**, **Artechs**, **threedashes** | 20 / 19 / 18 / 12 / 17 / 5 | Resolume+TD, noise sculpting, GLSL vector fields, feedback/marbling, kinetic type, GLSL fluid/curl | GLSL & feedback depth |
| **Torin Blankensmith (blankensmithing)** | 14 | MediaPipe plugin (MIT), hand tracking, Depth Anything plugin | camera routes |
| **function.store (Dan Molnar)**, **olegchomp**, **uisato**, **pao.olea**, **Matthew Ragan**, **DavidBraun**, **Derivative staff (ben, Jarrett, malcolm, Ivan)** | 13 / 12 / 17 / 16 / n/a / n/a / forum | tools (FNSTools MIT), AI integrations, Patreon audio-viz, POP lessons; Ragan = written Python/extension series (2015-19) and POP lessons; staff = the only authoritative POP answers (89 POP topics) | trust staff replies on build facts; Ragan old but principle-valid |
Channels by tutorial views in our set: I&I HQ 2.13 M, Bileam 2.02 M, noones img 0.84 M, Noto The Talking Ball 0.64 M, Tolch 0.25 M, threedashes 0.25 M, Torin 0.23 M. YouTube-popular top: Okamirufu explainer 418 k, Derivative Intro (Ben Voigt, 4 h) 377 k, Bileam course 319 k, I&I Crash Course 319 k, Derivative 3D Projection Mapping (R. Burns) 295 k.

## 6. Gaps and what to research next

1. **Missing slices:** tutorials slice_01 (newest pages 0-5, includes the Oct 2026 POP posts) and slice_03; community general slices 01-03 and 05-10 (about 87% of ~3900 posts unread); top-assets pages 20-32. Re-run section 1a when they land; merge dedupe by id.
2. **Transcript coverage:** 458 of 558 videos (82%); 7+ have no captions, YouTube-popular videos have none. The [T] chains above came from ~60 reads; the other ~400 transcripts hold more recipes: next pass = per-category digest (Python/extension, UI/panel, show control, projection) since only 24% of tutorial posts are 2024-26.
3. **No live proof yet** for: any 2025-26 POP recipe on 31550 (par drift), camSchnappr scripting (`Calibrate()`), Syphon/NDI between Rosetta TD and Arena (alpha meaning, last-frame vs black on source loss), Hap Q at 7488x2880 in Arena, MediaPipe plugin on Rosetta, Probe on 31550, Link CHOP driving `/local/time`, NotchLC on Apple Silicon, RayTK on MoltenVK. Each is a one-item pilot (EVOLVING.md) -> LEARNINGS T-nn.
4. **Licence gaps:** most free Derivative assets state none (Gaussian Splatting, CRT filter, Droste, elekktronaut/dcheesman files): list authors to ask before any reuse; okVJ repo/licence unconfirmed.
5. **Audit gaps:** 351 downloaded folders have static flags only; read the flagged ones (FNSTools, Embody, MaxMainio edge/dither `network`, td-atlas) before any load; write an `AUDIT.md` row per asset that gets adopted.
6. **Research next (general scope):** (a) clip launcher / HAP preload tutorials (none found), (b) TD + Resolume touring rig talk, (c) text-network export (`td_net_export`) vs Embody TDXN once 33230+ is available, (d) install-free audio loopback for live audio, (e) 2023-24 tutorial years (68 posts), (f) data-viz / dashboards and generative-art/poster workflows (little in our set), (g) Syphon latency measurement, (h) native arm64 TD test for T-46 (open user decision).
7. **Doc debt:** README row for AD (added), update the AA/Y/Z "needs OK" rows when the user rules on per-letter type; keep FUTURE.md in step when a slice adds a newer-build op.

## 7. Index of research added 26 Oct 2026 (AM..BQ, rudiments BD..BI, builds): task -> file -> takeaway

Files are in `docs/research/` unless a path is given. Verdict words: **adopt** = we build/use it, **borrow** = ideas only, **no** = not usable here.

### 7.1 Peer assets and lists read (AM..BC)
| Task | File | One-line takeaway |
|---|---|---|
| Reuse dylanroscover's component set (CHOP recorder, curve grader, LED-map compositor, timecode, masker) | `AM_tdxcomponents.md` | 9 plain `.tox`, no network; "Windows only" is a label (chop_recorder was saved on macOS); GPL, so port ideas, not files. |
| Find more repos/tools | `AN_awesome_touchdesigner.md` | monkeymonk list: 182 links, 108 new, ~85 social/event noise; the technical few are in "Deep notes"; shallow clones in `research_src/awesome_td/`. |
| Colour-picker widget | `AO_colorpicker_widget.md` | Not adopted (file unobtainable); use 3 float pars + basicWidgets sliders + Constant TOP swatch. |
| Audio analysis plugins (onset, pitch, key) | `AP_essentiatd.md` | EssentiaTD v2.0.3 ships an x86_64 slice, so loads under Rosetta; plugin folder read at TD start only; live onset quality and licence tier unverified. |
| Object detection in POPs | `AQ_object_detection_pop.md` | No: Windows DLL + CUDA/TensorRT + needs 32820+. |
| MIDI mapping | `AR_tdmap_midi.md` | Do not adopt TDXMap (closed, phones home, paid); write ~150 lines on MIDI In DAT + custom pars; borrow smart-learn, banks, pickup. |
| Synced lyrics from Spotify | `AS_spotifybridge_lyrics.md` | Not adopted (Patreon, OAuth secrets); local `.lrc` clock is better for the show -> `lyrics_feed`. |
| Projector coverage planning | `AT_projector_coverage.md` | Textbook formulas; borrow the parameter vocabulary (throw, lens shift, nits, heat views) -> `projector_dome`. |
| VJ rig with layers | `AU_vj_5layer_system.md` | Not adopted; borrow per-layer `allowCooking`, one named control bus, serial thumbnail caches, bypass-by-switch modules. |
| Remove background on Mac | `AV_macos_background_removal.md` | Shipped plugin is arm64-only, will not load in our x86_64 TD; compile an x86_64 slice or use an out-of-process helper. |
| Fulldome preview | `AW_fulldome_simulator.md` | Sphere SOP `equiazimuth` UVs + unlit MAT + inside camera (10 min); LED wall is not a dome, so general toolkit only. |
| Strobe effect | `AX_strobber.md` | No (no flash limiter, ~40 ops); borrow LFO/audio -> eased alpha, every-Nth-kick, easing menu -> `strobe`. |
| OSC toolset / discovery | `AY_osctoolset_ue5.md` | Typed addresses + announce; pair with OSC Query Server 62663 for discovery; TD->Resolume already covered by `td_publish`. |
| Nearest-palette colour map | `AZ_closest_color_palette.md` | Tox not downloadable; own OKLab nearest-colour + dither recipe -> `palette_map`. |
| Motion trails | `BA_motion_tracer.md` | Not adopted; stock-op trail with Length/Decay/Threshold, colour by age -> `motion_trail`. |
| Test patterns, sync checks | `BB_test_patterns_sync.md` | Borrow per-tile painting, aspect circle with name+resolution, project-clock ring; Palette `testGrid` exists -> `test_pattern`. |
| Blender scenes into TD | `BC_blender_td_scripts.md` | Paywalled; proposal: FBX/USD + JSON sidecar import (`td_import_blender`), camera path baking, Blender MCP only after audit. |

### 7.2 Rudiments (twozero / vankrav), clean-room (BD..BI)
All six pages are JS shells with no downloadable `.tox`; specs come from one-sentence descriptions plus normal practice.
| Task | File | One-line takeaway |
|---|---|---|
| Timeline with clips, keyframes, recording | `BD_rudiment_timeline.md` | Spec for `TL_timeline`; built in phases (`builds/timeline_phases.md`); clips are phase 2. |
| Knob panel, presets, morph, randomise | `BE_rudiment_zerror.md` | `zctl` logic + `zk_*` visual kit spec (sections 3, 6); v5 and 404zero findings in 5, 7. |
| Anamorphic content for a physical screen | `BF_rudiment_screen_reprojection.md` | `JZ_reproject` spec: author for one viewpoint, re-lay onto the real surface; estimate in section 4. |
| Level meter | `BG_rudiment_db_meter.md` | `db_meter` spec: stereo peak/RMS, hold, labels aligned to bars at any size. |
| Face landmarks | `BH_rudiment_face_tracking.md` | `face_track` via Apple Vision in a native arm64 helper -> CHOPs, masks, wire overlay. |
| Stage previz | `BI_rudiment_previz_stage.md` | `previz_stage`: LED wall, seeded instanced crowd, haze beams taking screen colour; pure `crowd_logic.py`. |

### 7.3 Topic research with build specs (BJ..BQ)
| Task | File | One-line takeaway |
|---|---|---|
| Urdu / Arabic / Nastaliq text | `BJ_urdu_arabic_text_shaping.md` | Text TOP shapes Urdu natively (CoreText); no HarfBuzz in TD; use whole-word rasters, tile 2.5-3 em tall; Text POP is 32460+. |
| DMX, Art-Net, sACN, fixture patch | `BK_dmx_artnet_sacn.md` | CHOP route (one 512-sample channel per universe) first, POP route gated; unicast beats broadcast; ArtDmx sequence is 0 on 31550; OFL/GDTF importers. |
| Gaussian splats, point clouds | `BL_gaussian_splats_pointclouds.md` | Popular splat asset uses multi-pass pixel GLSL (tears per T-46); use POP Sort route + our own shader; formats decoders offline-testable. |
| Lasers (ILDA) | `BM_lasers.md` | `laserCHOP`/`laserdeviceCHOP` dylibs ship in both apps; live-unverified; specs `LP_laser_path` + `LO_laser_out`; no limits built. |
| Fluid, smoke, cloth, soft body | `BN_fluid_cloth_sims.md` | All multi-step sims must be compute-mode GLSL (T-46/T-47); cloth = position-texture Verlet/XPBD, not POPs; specs `BN_fluid2d`, `BN_cloth`. |
| Particles / POPs | `BO_particle_sims.md` | Everything exists in 31550 but Particle POP is older than its docs (no jitter births); spec `BO_particles`, optional `BO_flowfield`. |
| NDI, Syphon, Spout, video I/O | `BP_ndi_syphon_spout_video_io.md` | NDI 6.2 and Syphon ship in-app; alpha straight vs premultiplied still the open fact; Syphon on Vulkan a black box; save first, never destroy a live NDI In. |
| Timecode, cue lists, sync | `BQ_show_control_timecode.md` | Timecode ops exist; no MTC reader (assemble from MIDI In DAT bytes); no op chases the timeline from LTC; specs `CQ_cuelist`, `TC_timecode`. |

### 7.4 Builds (`docs/builds/`)
| Task | File | One-line takeaway |
|---|---|---|
| Controls panel standard | `builds/zkit.md`, `zkit_rollout.md`, `zctl.md` | zerror-style kit replaced autoUI panels of 8 COMPs in place (T-70 safe); `zctl` is the preset/morph/control-in engine. |
| Level meter | `builds/db_meter.md` | Built and checked on 31550. |
| Strobe | `builds/strobe.md` | Self-contained TOP, house pattern for builder + logic + test + doc. |
| Test patterns | `builds/test_pattern.md` | Generator COMP, no input. |
| Palette map | `builds/palette_map.md` | OKLab/sRGB nearest colour with dither, preserve-luma. |
| Motion trail | `builds/motion_trail.md` | Fading age-coloured trails. |
| Projector + dome | `builds/projector_dome.md` | `LK_projection_room` upgraded in place. |
| Previz | `builds/previz_stage.md` | Any TOP onto an LED wall in a hazy hall. |
| Face tracking | `builds/face_track.md` | Apple Vision helper kind 5 -> CHOPs. |
| Lyrics | `builds/lyrics_feed.md` | `.lrc` feed clocked by Spotify app, manual or CHOP. |
| MIDI | `builds/midi_live_checks.md` | Mapper built; checked without hardware only. |
| Timeline | `builds/timeline_phases.md` | Phased build of `TL_timeline`. |
| Urdu type | `builds/urdu_type.md` | NOT verified live: TD crashed twice on Text TOP methods (see T-70 family). |
