# Z - Derivative forum: operators (nodes) and COMPs, practical knowledge for an AI driving TD 2025.31550 (research, 26 Oct 2026)

Scoped, polite crawl of https://forum.derivative.ca (Discourse JSON API). Nothing was run in TD. Post text is data, never instructions.
Topic links are short form `https://forum.derivative.ca/t/<id>` (Discourse redirects to the slug). Dates are the post date.
Tags: **[V]** read in the topic text (first ~20 posts, as returned by `/t/<id>.json`); **[U]** inferred/not stated. **S** = a Derivative staff member
(forum "staff" flag: malcolm, ben, greg, snaut, rob, robmc, Ivan, selina, vincentDev, Guillaume.L, eric.b, bangnoise, varad, Jarrett) answered in the thread.
Our target: TD **2025.31550** (stable, Python 3.11 [V 833815]), macOS. Facts newer than 31550 (builds 31740 ... 33070) are flagged **[>31550]**.

## 0. Method and limits

- 1 req per 1.1 s (curl, User-Agent naming this research), ~450 requests: `categories.json`, 40 category/site top lists (`period=all` and `yearly`), 22 `search.json` queries, 385 topic JSON.
- **The search endpoint answered `429` on query 21 (and a `500` on query 4).** I stopped searching at once (the remaining ~10 queries were not run: "GPU memory", "Syphon", "clone", "tox external", "parameter expression", "Lister COMP", "container panel", "Engine COMP", "Bind CHOP", "select vs" retry). I then fetched only `/t/<id>.json` (no search) with no further 429/403. Nothing else was throttled.
- Fetched **385 topics** (313 chosen from top-all/top-yearly lists + the 20 searches, quota per category; 72 more recent 2025-26 ones). 312 have a staff reply, 62 have an accepted answer. Saved: raw JSON in `research_src/forum/raw/` (git-ignored), compact `research_src/forum/topics.jsonl` (id, title, category, views, likes, dates, url, OP excerpt, staff/accepted text).
- Forum categories are few (General, **POPs**, Beginners, Techniques, Bugs, Wishlist, Hardware, Documentation, Shared .tox, Gallery). There are no per-family categories (no "TOPs", "CHOPs", "COMPs").
- **Bias:** "top all time" is dominated by 2008-2018 threads (TD 077-099). Only the POPs category and 2025-26 threads describe our build. Old facts are kept only where the principle still holds, and flagged in section 6.
- **ben (staff), 2026-10-19 [V 1018374]: the forum's "Shared .tox" section is superseded by "Assets" posts in the Community feed.** The Shared .tox list below is therefore old; current assets live on derivative.ca/community (not crawled).

## 1. Summary (ten facts that matter for driving TD from an MCP)

1. **POPs are the 2025 growth area and the only family with live staff answers.** Official docs: "Learning About POPs" (Notion), the experimental examples package (`Overview.toe`, `POPGuide/`, `GLSLPOPs_Update.toe`) [V 707716, 2025-06-06]; Darien Brito's community guide is outdated (ben 2025-08-21 [V 705888]). S.
2. **Ray POP, GLSL ray queries and hardware collision do not work on macOS** (MoltenVK lacks the extension; Guillaume.L 2026-01-06 [V 909593], vincentDev 2025-12-01 [V 863074]). S.
3. **Extensions only initialise when TD asks the COMP for something** (a cook, a viewer, a reference). It is "a black box"; the "Init Extensions on Start" toggle exists since ~Dec 2023 (Ivan, selina 2026-06/07 [V 999696]). S. Matters for any MCP that builds an extension and expects it live.
4. **Callback templates changed in 2025.30000**: new Execute-DAT callbacks come with docstrings and type hints (Ivan 2025-11-21 [V 853690]). S. Replace the whole DAT text, do not append.
5. **`op()` of a path string with embedded quote characters returns None in 2025** (it "would have worked in 2023.10k") (snaut 2025-11-26 [V 860568]). S.
6. **Do not trust LLM performance advice**: malcolm 2025-07-08 on a GPT-based profiler: setting cook type to "Always" is "the opposite of correct"; Feedback and compositing TOPs are cheap [V 727206]. S.
7. **Performance regressions are build-specific**: DMX Out CHOP slow in 31740-31760 (M4 MacBook user, 2 fps; fixed 31890+), Group POP recompiling shaders every frame in 32280/32460, Container COMP layout bug in 32820/33070, two Engine COMPs hanging on RTX 5080 after 32280. Our 31550 is before all but the DMX one. All S.
8. **macOS has real gaps**: TDI python stubs missing in the 31550 mac app (fixed 31760+, ben 2025-12-13 [V 833815]); no Kinect; Intel GPUs unsupported; Leap Motion works on Apple Silicon since 2023.10000 official. A third-party **AML** operator family (Apple Neural Engine) exists [V 1014942, Patreon, 2026-09].
9. **Two open-source/third-party MCP servers for TD are known on the forum** (tdmcp/MindDesigner 2026-06-01 [V 993195]; a docs-serving MCP 2025-08-05 [V 747858]). Jarrett (staff, 2025-08-30): Derivative is "experimenting internally with MCP integration", no direction settled.
10. **Roadmap flagged in the 2025.30060 post (2025-06-06 [V 707716])**: an ASCII project/tox file format, a cloning overhaul and new workflows for custom parameters were held back "for a follow-up experimental release". Not confirmed in 31550 [U]: check with `td_info`/docs before relying on either.

## 2. Per family

### 2.1 TOPs
- **Most TOPs process 3D textures** in 2025 (release summary) [V 707716]; **H264/H265 encoding on macOS** is new in 2025 [V 707716]. Dates: 2025-06. S.
- **Feedback TOP is cheap (just a copy at end of frame); Composite is cheap** (malcolm 2025-07-08) [V 727206]. S. Do not "optimise" them first.
- **Shadertoy ports into GLSL TOP (2025, GLSL 4.3):** `texture2D()` is gone, use `texture()` (snaut 2024-08-27 [V 9178]). A Shadertoy fluid that packs data with `packHalf2x16` goes NaN in a feedback loop in 2025 because denormal float bit patterns are flushed to 0 (malcolm 2026-04-09). The fix both Derivative and tim gerritsen give: **output several colour buffers (GLSL TOP "# of color buffers") and use one Feedback TOP each, no packing** [V 979006, 2026-04]. S.
- **GLSL TOP compile errors:** drop an Info DAT on the GLSL op; a red/blue grid means a compile error (malcolm 2014 [V 4067]); an Info DAT with its viewer on keeps ops cooking (malcolm 2010 [V 2042]). S, old but still how it works [U].
- **Movie File In in Index/Sequential mode with Photo/Motion JPEG** (18+ files, M2 Max) hits the CPU; re-encode to **HapQ / NotchLC** (GPU decode), use chunked Hap; Performance Monitor "Frame Trigger" shows only slow frames (snaut/nettoyeur 2023-10 [V 383683]). S.
- **TOP to CHOP downloads GPU to CPU and is slow** on GeForce vs Quadro (malcolm 2015 [V 7311]); one TOP to CHOP, then Fan/Shuffle/Join CHOP, never 49 TOP to CHOPs (malcolm 2013 [V 4585]). Mac unified memory effect [U].
- **Web Browser/Web Render audio into Movie File Out TOP:** take the Web Browser COMP's own audio CHOP output (3rd output) into the Movie File Out; ben 2026-01-16 reproduced it recording fine [V 918494]. S.
- **Engine COMP (TouchEngine):** stuck "engine_launching" on 2025.31550 / Windows with a TOX from 2023 builds; bangnoise (staff) asked for GPU/driver and suggested 2025.31740 (2025-11-17 [V 848062]); unresolved in thread. Mac not mentioned [U]. Two Engine COMPs mixed in parallel froze TD after 32280 on RTX 5080 (2026-05 [V 985605]) [>31550].
- **GPU memory:** the "1x1 resolution trick" frees memory but fragments it and causes hiccups: last resort (snaut 2023-10-25 [V 6142]). S.
- Custom TOP/OP users cannot see inside built-in ops; "all ops are C++ at the core" (malcolm 2025-12-10 [V 877003]). C++ custom COMPs are only a wish (RFE, snaut 2026-07-06 [V 982668]).

### 2.2 CHOPs
- **Math is much faster in CHOPs than DATs** (native floats vs strings) (rob 2016 [V 7756]). S. Keep per-frame numeric work in CHOPs.
- A CHOP network (Transform CHOPs) scales better than a Script SOP for camera projection of points: 0.15 ms vs 0.23 ms at 240 pts, 0.17 vs 0.37 ms at 480 (snaut 2020/2025 [V 133140]). S. Example `cameraToSOPwithCHOP.tox`.
- **No Lag/Filter POP in 31550**; use Cache POP + Cache Blend POP (Guillaume.L 2025-08-12 [V 752956]); a Lag/Filter POP "will be in the upcoming build" (greg 2026-08-09 [V 1008738]) [>31550]. A Button COMP + Spring CHOP drives a CHOP to POP ripple (snaut 2025-12-22 [V 888963]). S.
- **Choosing a CHOP over expressions:** a Math CHOP after a Constant CHOP with a Python-linked value did not cook; a Parameter CHOP pulling the value fixed it (snaut 2017-03 [V 8757]; TD 088/099, may be fixed [U]).
- **DMX Out CHOP** performance bug introduced in **2025.31740**, "fixed in 2025.31890+"; an M4 MacBook Pro user dropped to ~2 fps on 31760 and rolled back to **31550** which was fine (eric.b 2025-11-27 [V 862029]) [>31550]. S.
- Timer CHOP segments + callbacks + Clock CHOP for timed shows (raganmd 2015 [V 7277]); LFO ramp "on to off" Count trigger for random numbers (ben 2017 [V 8788]).
- Lyrics/cue lines: table of lines, **Select DAT in row-by-index mode + Count CHOP on a Keyboard In CHOP**; show with a **Text COMP** (Type = Multi-Line enables Word Wrap) instead of Text TOP (bramb09, Ivan S 2026-07-24/25 [V 1005339]). Relevant to PF26 lyric work.
- Audio: `base_spectrum.tox` (snaut 2023-10-11 [V 382690]) shows Audio Spectrum CHOP as a texture; Audio Analysis Extended (v.rtx_void 2024-03, ben moved it to Techniques [V 472736]) adds normalisation to the Palette AudioAnalysis.

### 2.3 SOPs
- SOPs are CPU; heavy animated high-point-count SOPs are the usual cause of low fps even on an M4 Max. Fixes named by staff and users: Cache SOP for things that need not update each frame, **cook things once early in the chain**, move geometry work to TOP space, and use **GPU instancing** (ben 2024-12-17, snaut 2024-12-13, flowb, r-ssek [V 578918]). POPs are "conceptually very different", not a 1-to-1 replacement (snaut). S.
- Script SOP vs CHOP network: see 2.2. SOP cheat sheet (~95 SOPs with pictures) by a user, 2022 [V 275002]; staff added snippets for missing ones in 2023.
- Alembic: the Alembic POP is "actively" being built; Alembic In POP currently cooks on CPU; int64 `Pid` imports as double (eric.b 2025-09/11 [V 790281, 852247]). S [>31550 maybe].

### 2.4 POPs (the richest source; all S)
**Docs and examples**
- "Learning About POPs" Notion page; POP examples/OP Snippets in the experimental package (vincentDev 2025-06). Math Mix/Combine "glossary" is undocumented, implemented from GLSL functions (Guillaume.L 2025-09-17 [V 781911]).
- Darien Brito's POP examples (4 releases, 2025-02..06) [V 619769, 671856, 693912, 705888] are for alpha 6.x; superseded by the official folder.

**Particles, feedback, forces**
- **Feedback POP only runs while the timeline plays or on step** (Guillaume.L 2025-05-20 [V 602298]). If you change the input geometry, **restart the feedback loop** (vincentDev 2025-03-05 [V 634487], SpringFeedbackPOP.toe).
- **Feedback POP freeze** when the feedback target is a Null (reported 2025-09 on 2025.30960, "fixed in next Experimental", reported again 2026-01 on 32260): workaround = switch off viewers inside the loop, or put a Copy POP (1 copy) right after the Feedback POP (vincentDev 2026-05-07 [V 779867]).
- New points in a loop: **Point POP + Merge POP**, then GLSL POP only to set values (vincentDev 2025-07-16 [V 734310]).
- Particles on a curve do not "stick": add steering forces or a Lookup Attribute over point-index range (Guillaume.L 2026-03/04 [V 976134]). Collision: Ray POP sample in `Overview.toe` (Particles/ParticleBasics); Ray POP tests every triangle (vincentDev 2025-06-11 [V 710910]).
- Smooth an attribute over time: Cache POP + Cache Blend POP; the cost grows with the number of attribute buffers bound, pass through only the attributes needed (Guillaume.L 2026-03-09 [V 752956]).

**Geometry and instancing**
- **Prefer Geometry COMP instancing to Copy POP** for speed, and map instancing **directly to POP attributes, not via CHOP samples** (Guillaume.L 2025-06-20, 2025-08-29 [V 717095, 765516]; greg 2026-02-22 [V 964090]).
- Texture instancing with POPs: Texture Index op needs the same sample count as the Translate op (Merge CHOP to align) [V 765516]; Point Sprite MAT ignores the POP texture attribute (2025-06-23 [V 717095]); bugs in 2025.30770 fixed; a GLSL TOP texture-array/3D texture is the alternative (vincentDev 2025-09-03/08).
- A `uint` attribute used as GEO scale becomes **0** (needs float) (Guillaume.L 2024-08-15 [V 513441]). Delete POP on `Inside==0` beats scaling instances to 0 (vincentDev 2024-08-21).
- Compare floats with a tolerance (`abs(P(0))<0.0001`) in Delete POP (josefpelz 2025-06-25 [V 719950]).
- **No Triangulation POP**, no L-system POP, no Wireframe/tube POP (vincentDev/Guillaume.L 2025-02, 2025-11, 2026-01 [V 621681, 860527, 924968, 536085]); use Dimension+Connectivity POP or Primitive+Skin POP for grid meshes, Neighbor/Proximity POP for local links; Extrude cannot keep the original face (merge a reversed copy) (vincentDev 2025-10-22 [V 819430]).
- Group POP cannot group by an arbitrary object; use Ray POP `RayInside` with scale 0 (vincentDev 2025-03-27 [V 652611]). Resample/blend between shapes of different point counts is not possible with Switch POP blend (Guillaume.L 2025-04-08 [V 661679]).
- Skin POP artefacts along sharp curves: Line Metrics POP computes a continuous orientation frame in **2025.33070** [>31550] (Guillaume.L 2026-08-07 [V 997254]).
- Colour: no linear/sRGB POP exists in 2025.30-ish; do it with a GLSL POP or a POP Color to TOP round trip (vincentDev 2025-02-18 [V 620758]) [may have changed, U].
- Unique text per instance with POPs: Text POP is mostly CPU, reuse strings; index via `mapping` (vincentDev 2026-05-18 [V 986562]).

**GLSL POPs**
- **GLSL Create POP was deprecated and removed** (vincentDev 2025-05-19 [V 693912]); everything is **GLSL Advanced POP** now. **Multi-pass added in 2025.30960** (points/topology changes disabled in multi-pass) [V 697383]. Only triangles and quads exist as polygons; write the index buffer by setting the number of output primitives or use Topology POP (vincentDev 2025-07, 2026-03-19 [V 720890, 502907]). Dimension helper functions `TDDimPointIndex()` in 2025.31310 (vincentDev 2025-10-08 [V 758961]). POP shaders cannot `imageLoad/imageStore` to TOPs. A GLSL TOP can read a POP buffer (example `GlslTOPSamplePOP.toe`, now in `GLSLPOPs_Update.toe` TOP_MAT container [V 620440]).
- Old compute GLSL TOP files (2023 builds) can crash or run at 1 fps in 2025 because cook dependencies changed; **lock a Null** to stop upstream expressions cooking every frame (Guillaume.L 2025-09-08 [V 680946]).

**DMX POPs (stage LED relevance)**
- DMX Fixture treats a **primitive as a fixture**: use a **line strip** (Grid POP connectivity None, then Attribute POP to line strip, Lookup POP, DMX Fixture POP); point-prims connectivity is the slow path; **60 fps, <1 ms** after 30200+ with `base_ledVolume.tox` (snaut/eric.b 2025-06-17..07-23 [V 714957, 707668]); the docked **DMX Map DAT is for debugging, keep it off** (eric.b 2025-07-23). "Fixture has no channels": expand the channel block with `>>` and set attribute name e.g. Color (eric.b 2025-07-10 [V 731025]). Universe value >15 bug fixed in a 2025.30770 hotfix (eric.b 2025-08-12 [V 745084]).

### 2.5 DATs
- **Python storage by key ~ table by index; table lookup by row name is ~30x slower** (5000 ops: table by index 1.6 ms, by name 55 ms, storage dict 1.6 ms) (keithlostracco 2014-05 [V 5322]) [old build, ratio probably holds, U]. Use `op.store/fetch` for data, tables for human-edited data.
- Writing a table cell per frame propagates a change per write; locking did not help, do the maths in CHOPs (selina/elburz 2015 [V 6310, 6310]). A table read passively does not trigger cooks (selina 2015).
- Info DAT shows GLSL errors; Execute DAT / CHOP Execute run in the main thread and block cooking (malcolm 2013 [V 4794]).
- **2025 callback templates** carry docstrings/type hints (Ivan 2025-11-21 [V 853690]); some users want them optional.
- **`op('/a' + 'quoted')` with literal `'` inside the string returns None in 2025** (snaut 2025-11-26 [V 860568]); build paths with f-strings.
- Par menus can be fed from a DAT with a small class exposing `menuNames`/`menuLabels` (rob 2016-02 [V 7454]).
- UDP/binary protocols: parse with `struct.unpack_from` in the UDP In DAT `onReceive` (robmc 2019 [V 8655]).

### 2.6 COMPs and UI
- **Cooking:** nodes with viewers on inside a network cook; a Switch cooks only the selected input; COMPs have a cook toggle (`opset -c`); a **Select COMP** swaps UI panels; use `Display` expressions to hide others (rob/greg/tekt 2014 [V 4940]; principle current [U]). A parameter dialog no longer causes a cook (selina 2026-06 [V 999696]).
- **Scene/cook pattern (drmbt 2023-12-04 [V 1242], S in thread):** Palette `sceneChanger` only requests one scene so unrequested ones do not cook; external animated data (MIDI, OSC, LFO, beat) forces cooks, so publish those pars to the parent, pull them in with a Parameter CHOP and end in a `null_data` that each scene references; on exit freeze `null_data` through a table/DAT-to-CHOP switch. Dozens of heavy scenes at usable fps.
- **Extensions:** see 1.3 and 2.7. Create extensions on a COMP; expect init only on first demand.
- **Container COMP layout bug** with anchors/fill in builds 32820/33070 for files saved in 32460; rob: reproduced 2026-07-31 [V 1006758] [>31550]. Output-to-multiple-input connection of COMPs fixed in 32645+ (varad 2026-03/05 [V 943697]) [>31550].
- **Exports vs expressions:** exports behave like pointers (cheap), expressions are evaluated every cook; copy/paste of a node that receives exports breaks (fixed in 099: the system turns exports off on the copy) (raganmd 2016 [V 8307]; ben 2017 [V 8548]).
- **Panel parameters:** the panel dialog "Override CHOP" field is deprecated, use the Override CHOP/Bind route (rob 2017 [V 8816]); drag-and-drop panel script args are `args[0]` (elburz 2015 [V 6650]).
- **Perform mode / windows:** one Window COMP is better than two (vsync can update windows alternately: 30 Hz on 60 Hz) (malcolm 2015-12 [V 7341]); to open a floating network pane while in perform mode: `op.TDModules.mod.TDFunctions.showInPane(op('/project1'), pane='Floating', inside=True)` (drmbt, accepted 2021-12-30 [V 234418]); for VR switch off Window vsync and match headset fps (malcolm 2025-12-09 [V 877003]). Minimise-by-Python hack does not work on Mac (Ivan 2020 [V 132014]).
- **Colour UI:** the native colour picker has no hex field; malcolm: hex is 8-bit sRGB and fades with wider gamuts (2025-11-11 [V 842864]). dylanroscover's `hexler.tox` (TDComponents repo) converts hex to RGB.
- **Rive:** a Rive Renderer TOP plugin exists (TDRive, medcelerate, 2026-05-28 [V 992271]); native Rive TOP is a wish (2025-11 [V 842270]).

### 2.7 Python and extensions
- **Threads:** in a worker thread do not touch any `td`/`tdu` object, use native types and a queue; poll results from a frame callback (malcolm 2013 [V 4742]). 2025 adds a **Python Thread Manager and a Python Environment Manager** (release post [V 707716]). `TDAsyncIO` (sndmtk) runs asyncio in TD; re-init the extension if it fails (2021-22 [V 190487]).
- **Pip packages on Apple Silicon:** modules installed with Homebrew python are invisible to TD; install into TD's own Python or point TD at the site-packages (accepted 2023-08 [V 368298]); `ssl` works in the Apple Silicon build (JetXS S 2022-12 [V 308299]).
- **TDI library** (python stubs for IDEs, in 2025) was missing from the macOS **2025.31550** app; copying the Windows `tdi` folder into `.../Python.framework/Versions/3.11/lib/python3.11/tdi` worked for one user, another crashed after re-signing; **working in 31760+** (ben 2025-12-13 [V 833815]). S. Runtime does not need it [U].
- `me`/`parent()` shortcuts and extension state machines: David Braun's Tic-Tac-Toe teaching example (snaut S 2025-01-10 [V 594343]).
- Python in tables: setting a Constant CHOP value from Python is "changing parameters", rare use (snaut 2015 [V 6599]).
- **MCP-for-TD on the forum:** tdmcp/MindDesigner (dpantani, open source, bridge inside TD, "629 operators, 68 Python classes" knowledge base; the author says rename-everywhere style refactors are "the direction", not guaranteed) [V 993195, 2026-06]; docs MCP server (bottobot, 2025-08 [V 747858]). Neither studied further.

### 2.8 Performance
- Tools staff and users point to: **Performance Monitor (F2)** with Frame Trigger, **Probe** (Palette), Info CHOP `last_frame_decode_time` for movies (malcolm 2013) [V 383683, 578918].
- **Never set cook type to "Always" or add Nulls to "save" cooks** (malcolm 2025-07-08 [V 727206]). Cooking is pull-based; keep unused branches unreferenced, viewers off.
- A single TD process is on one CPU core except specially threaded ops (movie load) (elburz 2015 [V 6142]).
- Apple Silicon performance per watt "mind boggling"; an M3 Max runs hours on battery (flowb 2024-12-12 [V 578918]).
- Regressions: DMX Out CHOP 31740-31760 (fixed 31890+); Group POP 32280/32460; Engine COMP hang 32280+ on RTX 5080; Container layout 32820/33070. All reported on Windows except the DMX one (M4 Mac). Staff ask for `.toe` + dump to support@derivative.ca.
- Laptop issues are mostly background bloatware and drivers (nettoyeur 2026-06 [V 985605]) (Windows).

### 2.9 macOS
- **Vulkan on Mac is MoltenVK**: no ray-query hardware path (Ray POP, GLSL ray queries, hardware collisions, Sprinkle POP volume) even on M-series; "hardware supports it, MoltenVK doesn't" (S, 2025-12-01, 2026-01-06).
- **GLSL 1.20 shaders do not compile on macOS** (malcolm 2017-01 [V 8568]); use `#version 330`+/TD's GLSL 4.3 style [U for 2025].
- **Intel GPUs are not supported on macOS** ("An intel GPU was detected. These are not supported on MacOS", build 2025.32050.intel, 2025-12-17 [V 22]); Intel Macs with AMD GPUs do not run POPs, crash often (Skin POP thread 2025-08 [V 724713]). Mediapipe plugin tox did nothing on an Intel i9 MBP / 10.15 with 2025.32460; staff: "your system might fall outside current requirements" (snaut 2026-03-19 [V 971846]). Our N doc says the Mac runs the x86_64 build under Rosetta: so Rosetta-specific POP/GPU limits are not covered by any thread [U].
- **No Kinect on Mac** (staff 2017/2023 [V 9012, 262575]); Orbbec/Kinect Azure not for Mac; Leap Motion works on Apple Silicon from **2023.10000 official**; copy `libLeap.dylib` into the app's Frameworks (robmc 2023-11-20 [V 363524]).
- **Webcam:** Video Device In "Library" must be AVFoundation (macOS) (ben 2019 [V 12208]).
- H264/H265 encode on macOS new in 2025 [V 707716]. ProRes decode: a 2016 report said not supported then [V 8308]; our own pipeline docs say otherwise [U]; not re-verified here.
- Apple-specific add-ons: **AML** (Apple Neural Engine pose/masking/classification TOP/CHOP family by mickeyvanolst, Patreon, 0.9.21, needs 2025.33070 per a user, 2026-09 [V 1014942]); **VOID Shared Memory** (C++ CHOPs, macOS Apple Silicon only, Ableton Live 12, Gumroad, 2026-01 [V 929115]).
- TD for Mac "a distant dream, now we have it" (2018) and Derivative says it supports new Macs after release (ben 2020 [V 149176]). A user switching to VDMX/Isadora/Millumin is the Mac-lockedness conversation (2025-11 [V 842636]); snaut S only confirmed the TDI bug there.

## 3. Shared components and tools worth a look (not duplicated from N)

Licence is **not stated** in any post I read unless noted ("none stated" = ask the author, per the BRIEF rule). Build = what the post says or implies.

| Name | Author | Link | Licence | Build / note |
|---|---|---|---|---|
| Derivative POP examples (`Overview.toe`, `POPGuide`, `GLSLPOPs_Update.toe`, snippets) | Derivative | /t/707716 | none stated (shipped with TD) | experimental 2025 package; use this, not the community guide |
| POPs examples / POPs guide | Darien.Brito | /t/619769 /t/693912 /t/705888 | none stated | alpha 6.x; ben: out of date |
| SmoothOverTime, SpringFeedbackPOP, ParticlesFollowingPath, AccurateColoring, MultiPassBlur, orderHacker.tox (lines to quads) | Derivative staff | /t/752956 /t/634487 /t/976134 /t/620758 /t/606236 /t/631051 | none stated | small POP recipes attached to staff answers, 2025-26 builds |
| `base_ledVolume.tox`, `base_ovationCYC3FC.tox` (DMX POP fixtures) | snaut | /t/714957 /t/973230 | none stated | 2025.30xxx+ DMX POPs; stage-LED relevant |
| `base_spectrum.tox` (spectrum CHOP as texture) | snaut | /t/382690 | none stated | 2023 |
| `cameraToSOPwithCHOP.tox` | snaut | /t/133140 | none stated | 2020, CHOP-only camera projection |
| hexler (hex to RGB) in TDComponents | dylanroscover | /t/842864 | GPL-3.0 for the repo (per N, row 18) | v0.1.5 |
| TDRive (Rive TOP plugin) | medcelerate | /t/992271 | not stated (GitHub) | 2026-05; Mac build unknown |
| tdmcp / MindDesigner (MCP bridge) | dpantani | /t/993195 | "open source" (licence not read) | 2026-06; competitor/prior art for our MCP |
| TD docs MCP server | bottobot | /t/747858 | not read | 2025-08; docs only, Roo Code |
| TouchProfiler (GPT perf hints) | saimgulay | /t/727206 | n/a | **malcolm: advice often wrong** |
| VOID Shared Memory (CHOPs for Live/Max) | Julien Bayle / Structure Void | /t/929115 | commercial (Gumroad) | macOS Apple Silicon only |
| AML (Apple ML ops) | mickeyvanolst | /t/1014942 | Patreon | 2026-09, macOS, 2025.33070 |
| TDAsyncIO | sndmtk | /t/190487 | not stated | asyncio in TD, 2021-22 |
| Tic-Tac-Toe (extension + state machine) | David Braun | /t/594343 | not stated | teaching example 2025-01 |
| Kalman Filter CHOP, Audio Analysis Extended | (users) | /t/332990 /t/472736 | not stated / GitHub | Script CHOP, 2023-24 |
| gal.tox gadget library, sliders+buttons+presets, timeBase, moviePlayer, Probe, Threaded Web COMP | greg / keithlostracco / snaut | /t/7485 /t/5842 /t/8485 /t/9491 /t/5705 /t/8044 | none stated | 2014-2018 (some now in Palette); UI gadgets are superseded by the Palette widgets [U] |
| td_fb_forum_examples (example explorer) | raganmd | /t/8169 | GitHub repo | 2016, many 099-era examples |

## 4. Gotchas (what an MCP should do or avoid)

1. After `td_create` of an extension COMP, **trigger init by touching it** (a cook/viewer or a reference) [U from 999696]; do not assume Init on Start.
2. Never build op paths with embedded quote characters; log the resolved path before `op()`.
3. When replacing an Execute-DAT script, **write the whole DAT text** (2025 template has docstrings); do not patch around the old comments.
4. Do not set cook flags "to save cooking"; fix references/viewers instead (malcolm).
5. A table cell write per frame costs a change propagation; keep numeric loops in CHOPs or storage.
6. For many points: **POP instancing straight from attributes**, not POP to CHOP to instance; Geometry COMP instancing beats Copy POP.
7. Feedback POP needs the timeline to run (or Step); after an input change restart the loop; Null as feedback target froze TD in some builds: add Copy POP / viewers off.
8. Uint attributes feeding a float parameter become 0; compare floats with tolerance.
9. Ray POP, GLSL ray query, hardware collision: **not on macOS**. Don't generate networks using them.
10. GLSL: use `texture()` not `texture2D()`; no half-float packing in feedback loops: use multiple colour buffers.
11. Movies: GPU codecs (Hap/HapQ) not Photo-JPEG for many simultaneous Movie File Ins.
12. DMX POPs: line strips, Map DAT off.
13. `TDI` python stubs absent in 31550 mac: `import tdi` fails [U]; avoid in generated scripts.
14. LLM performance advice (including from tools) is often wrong: verify with Performance Monitor.
15. Ask for staff-reproducible repros: `.toe` + dump to support@derivative.ca.

## 5. Practical patterns worth copying

- **Lyric/cue switching:** Table DAT lines, Select DAT (row by index), Count CHOP, Text COMP Multi-Line + Word Wrap [1005339].
- **Scene host with static data gates** (drmbt) [1242].
- **Attribute smoothing:** Cache POP + Cache Blend POP, few attributes [752956].
- **LED volume to DMX:** Grid POP (connectivity None) + Attribute POP (line strip) + Lookup POP + DMX Fixture POP [714957].
- **Meshes from a grid of points:** Primitive POP + Skin POP, or Dimension + Connectivity POP [924968].
- **Hex colours to RGB:** hexler tox; mind colour space (malcolm) [842864].

## 6. Possibly outdated for 2025.31550 (flagged with date)

- Everything from 2008-2018 TD versions: Override CHOP in panel (2017), GLSL 1.20 on Mac (2017), ProRes on Mac (2016), Mac DOF render bug (2016), exports copy/paste (2017), Replicator crash with `me.parent().destroy()` fixed in 54020+ (2015), 1x1 resolution trick (2015, caution 2023), DAT vs storage timings (2014), Window COMP "onstart" parameter (2015), OP Snippets are now built in (Help menu).
- 2025 POP facts that moved: GLSL Create POP removed; multi-pass added 30960; Feedback POP timeline rule; Alembic POP in progress; Lag/Filter POP due; Line Metrics frames 33070; Group POP recompile fixed after 32460; DMX performance fixes 30200+. Which of these are in **31550 stable (Oct 2025)** needs a live check.
- Shared .tox tables: all superseded by Community "Assets" (2026-10-19).

## 7. Sources

Topic ids (all `https://forum.derivative.ca/t/<id>`): POPs 619769 671856 693912 705888 602298 602597 606236 620440 620758 621681 634487 652611 660839 661679 691652 692635 696642 697383 707668 710910 714957 717095 719950 720890 724713 731025 734310 745084 752956 758961 765516 779867 781911 790281 795815 819430 852247 859921 860527 863074 909593 924968 964090 976134 986562 990522 997254 1008738 1018374; General 22 707716 747858 842636 842864 853690 877003 929115 961393 993195 999696 1005339 144033 190487; Bugs 833815 848062 860568 943697 970062 985605 862029 1006758 308299 368298; Techniques 1242 5322 4940 6142 6310 4742 4794 133140 382690 383683 472736 594343 727206 134436; Beginners 7756 8548 8816 6650 4585 234418; Hardware 578918 262575 363524 12208; Wishlist 842270 982668 7454; Shared 7485 5842 8485 9491 5705 8044 8169. Raw JSON and `topics.jsonl` in `research_src/forum/`.

## 8. Open questions for the lead

1. Which of the POP/Container/Group fixes above exist in **31550**? A live `td_exec` check of POP parameter names (Feedback POP, GLSL Advanced multi-pass page, Lookup Attribute) against `ops/ops_POP_2025.31550.json` would settle it.
2. Do the "new workflows for custom parameters" and "cloning overhaul" (announced 2025-06 for a later experimental) ship in 31550 stable? Check `td_custom_pars` behaviour and the Clone COMP pars.
3. Name and behaviour of the "Init Extensions on Start" parameter in 31550; should `td_create` for extension COMPs force init?
4. Search was rate-limited (429) after 20 queries: a retry later (or 1 req per 3 s) could cover "Syphon", "Engine COMP", "Lister COMP", "Bind CHOP", "container panel", "tox external", "clone".
5. The Community "Assets" feed (replacement for Shared .tox) was not crawled; it is a different site (derivative.ca) and may hold the current shared components with licences.
6. Should the tdmcp/MindDesigner project (prior art, MCP bridge, 629-operator KB) be read for ideas? Licence not read.
7. Rosetta (x86_64 build on M1 Max, per N): any POP or GLSL limits specific to it are not covered by any forum thread I read.
