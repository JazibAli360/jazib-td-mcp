# Community slice 01: derivative.ca/community pages 0-19 (newest, 26 Oct 2026)

Crawled 26 Oct 2026, one lane, 2 s spacing, no errors/429s. 400 listing rows = **305 unique posts** (about 5 pinned posts repeat on
every page), dated 8 Apr to 24 Oct 2026. Full records: `research_src/community/slice_01.jsonl` (305 lines).
Relevance is scored for general TouchDesigner mastery (0-3): 3 = 50, 2 = 122, 1 = 49, 0 = 84 (mostly events/workshops).
Many tutorials are only a teaser plus an off-site link (YouTube, interactiveimmersive.io blog): the video/blog bodies were not fetched.

## Counts per type
tutorial 88, asset 59, event 51, post 49, workshop 45, other 13 (7 company posts by Derivative staff, 6 gallery). 32 posts carry
attachments or files; 33 of 59 assets host their files off-site (Patreon, GitHub, own shop).

## Top 15 by relevance
1. **75406 Derivative TDMCP (beta)**: official MCP server as a single .tox (26 tools, `get_help`/`get_docs` per build, render-to-image,
   localhost-only, auth+HTTPS beyond) plus TDMCPSkills repo (19 `td-*` skills). Licence: Derivative Shared Use (TD licensees only).
   Closest prior art to jazib-td; cloned.
2. **75403 td-atlas** (MIT, macOS-tested on 2025.32460): per-install operator index, undoable edit blocks, `td_health` (never-cooking
   branches, dead feedback, negative float Levels), frame-stepping timeline jobs, offline .toe/.tox search/diff. Cloned.
3. **75078 TdHttpApi.tox** (cacheflowe): REST bridge for agents, 235 KB tox, plus `td-docs-mcp` repo (MIT). Downloaded and cloned.
4. **74528 TouchDesigner MCP for Claude** (Lostfound): one-click tox that registers itself in Claude Desktop; mac+Windows; Patreon.
5. **74550 Devs' Choice**: Derivative's digest of features since 2025.Official up to 2025.32820 (Trace/Triangulate/Extrude/Text POP,
   array-attribute math `[:]`, DMX POP speed, drag-drop Python subscribers, Blob Track limit lifted, Alembic Out POP).
6. **75326 Build 2025.33070 digest**: glTF support and the new Script POP (newer than our 31550).
7. **74570 TDFam**: free Apache-2.0 framework (function.store + dotsimulate) for third-party operator families; 12 families/8 creators.
8. **75562 AVY** (elekktronaut): modular live-performance framework (presets, MIDI, OSC, Ableton Link, web UI); alpha on Patreon, paid key.
9. **75106 SonomikaTD**: free VJ app inside TD (column grid, 32 scenes, TOX effect chains, MIDI/OSC). **75184** (tekt) shows
   mixing TD into a Resolume set; **75147** shows Syphon/Spout into MadMapper.
10. **74980 PosiStageNet sender CHOP** (grandMA tracking out) and **74438 PONK** (UDP laser-path protocol, MadMapper-funded): show control.
11. **75468 OSCAR**: open-source phone/tablet control rack sending OSC, MCP helper, two demo .tox. Cloned and .tox downloaded.
12. **74906 TDMap** (Function Store): MIDI-mapping workflow tool replacing hand-wired MIDI chains.
13. **74641 POP Attributes 101** and **75538 POPs vs SOPs**: the best two orientation pieces for the POP family.
14. **75355 TDXvCon**: batch HAP/HapQ/NotchLC/ProRes/H.26x transcoder inside TD (GPU, CLI over TCP); useful for Resolume media prep.
15. **75218 Professional Project Walkthrough** (tekt): conference installation with ML camera analysis driving LED tubes over DMX.
Next tier (3): 74468 LED walls, 74780 RF-DETR (Mac MPS), 74796 SH lighting, 74720/74251 DMX POPs, 74698 TDAbleton, 74347 TD Synapse.

## Files downloaded (never opened or loaded)
Root `research_src/community/files/<postid>/`. Totals: 14 files (about 13.4 MB) + 21 shallow git clones (about 165 MB, each under 50 MB).
- Derivative attachments (12): 74246 td_lastBeatStanding.tox (871 KB), 74247 Droste.tox + InfiniteRegression.tox, 74259 4DGLSLNoise.tox,
  74519 DMX4AllUsb.tox (Windows), 75017 ClothPOP_free_NOTCOMMERCIAL.zip (list only: ClothPOPFree.dll + example .toe, NVIDIA/Windows),
  75049 Gestation.toe (11.4 MB), 75078 TdHttpApi.tox, 75162 Color Picker.tox, 75188 MetaballTangency_0.tox, 75431 Fractal Glass.toe,
  75485 camera_crane.tox. Builds are not stated on the pages. 74360 TLMONKEY.tox (prank that deletes nodes) was downloaded then deleted.
- OSCAR (75468): oscar-type-tunnel.tox, oscar-kaleido-feedback.tox from createwithoscar.site.
- Clones (commit in jsonl): TDMCP 149e25ca and TDMCPSkills c24db4bd (Derivative licence), td-atlas 7cf8f57f (MIT), td-docs-mcp ddb3f2a1 (MIT),
  OSCAR 1fb633ee, td_lastBeatStanding 0be100f3 (GPL-3), Ponk c1ecb1cb (Apache-2), TDFam fa1c8d24 (Apache-2), SH-in-TD 83808ccd (no licence file),
  td-synapse 5d95b65d, brownian-motion 8f40f6c3 (MIT), CK-TD-Free 94b4f214 (MIT; GridPOPLOD, 4DGLSLNoise, Dmx4AllUsb),
  TD-SOP-USD-Anim-Bridge 9f73aa22 (MIT), FlyBrain 2e4f11df (CC BY-SA), MultiplayerServer_TD 0592b57c (MIT), Max Mainio TD_ 9689834b (SDF/SVG comps),
  OSCToolset 64e12e71 (GPL-3, Unreal plugin), L-System-POP 8d23023a and MCX-Radio-CHOP 966b89b9 (all rights reserved, C++ sources),
  mylesjaeger/Touchdesigner a8c4686e (GPL-3; TurgorSystem + Metaball zips), FreenectTD 824ea32d (LGPL-2.1).
- Inside TDMCP: `docs/` (component, security, setup, troubleshooting); TDMCPSkills `skills/`: td-build-planning, td-chop/dat/mat/pop/sop/top-family,
  td-comp-architecture, td-glsl-shaders, td-python-extension, td-network-cleanup, td-node-layout, td-performance-check, td-review-network, td-working-mode.
- Not cloned: jpkelly/TDXvCon (repo not found; PyPI `tdxvcon` linked). Note: other processes also use these post folders (att_top01, expanded/, AUDIT_*.json appeared).

## Recurring techniques and ops
- **POPs dominate 2026**: Particle, Math Combine/Mix, Proximity, Ray (collisions), Trace/Triangulate/Extrude, Text, Projection, Grid, DMX, Feedback POP,
  GLSL Advanced POP compute; attribute-driven design; Houdini and Blender hand-offs.
- **Audio-reactive**: audio spectrum to instancing/POP attributes; Essentia/MCX CHOP suites; beat tracking; TDAbleton; sonification.
- **Control/show**: OSC, MIDI mapping, DMX/Art-Net (DMX POP), PSN, PONK/ILDA lasers, NDI/Syphon/Spout to Resolume and MadMapper, Unreal OSC.
- **Agentic TD**: TDMCP, td-atlas, TdHttpApi, Lostfound MCP, Claude-written GLSL/custom ops; common rule: read docs of the installed build.
- **Custom C++ operators and TDFam families** (STOP, FOP, MCX, Alaghast POPs) sold via Patreon or LemonSqueezy; Windows/CUDA or Apple Silicon only.
- Feedback (Edge/Lookup/Displace/Bloom), GLSL TOP/MAT/POP, RayTK, MediaPipe (hand/face/object), blob tracking (no 2-blob cap now), depth cameras.

## Authors who post a lot
elburz/Interactive Immersive HQ 51 (teasers to YouTube/blog), Aristides.Lab 15 (Apple Silicon ML/iPhone tools, Patreon), tekt 12 (workflow basics, RayTK),
pao.olea 10 (numbered tutorial series), isabelle (Derivative staff) 9, Alaghast 7 (MCX/POP plugins), Unveil_studio 6, Spiraldiver 6 (Patreon op families),
uisato 5, dcheesman 5 (Mac-friendly depth cameras, feedback), Tyrell 5 (tdplugins.shop CUDA ops), The_NODE_Institute 19 course/event posts.

## Windows-only / NVIDIA-only / Apple-Silicon-only
- Windows/RTX: 75521 Harlow Engine (OptiX), 75143/75017 ClothPOP (CUDA), 74954 Object Detection POP, 74945 Object Segmentation TOP, 74927 CUDA tiling TOPs, 74519 DMX4ALL.
- **Apple Silicon (arm64) native plugins will not load in our Rosetta (x86_64) TD 2025.31550** (unverified, see questions): 75423 GeneratorSOP, 75258 MCX Radio (also 2025.33070+),
  75075 EssentiaTD, 74457 Apple Vision Suite, 74435 Kinect POP, 74428/74429/74427 CoreML tools, 74780 RF-DETR (MPS).
- Cross-platform and plugin-free: 75187 STOP (2025.32460+), 75403 td-atlas, 74246 beat tracker (pure numpy), 74476 Motion Extraction, TDLidar (iPhone app).

## Skipped
- 75512 "Ultra_r3ve .tox files leak 16.10.2026": title says leak; author's text claims it is their own free Google Drive of 700+ .tox. Recorded only; not downloaded.
- Patreon/paid (title, tier only): AVY (key via Polar), SD TOP (15 EUR per 6 months), ClothPOP PRO (10 EUR+), Harlow, FOP, STOP Pro, uisato projects, Aristides.Lab toxes.

## Open questions
- Is jazib-td's TD really x86_64 under Rosetta? If yes, arm64-only plugins are out; if an arm64 build is possible, the Apple-Silicon tools open up.
- Newer builds exist (2025.32820, 32460, 33070) than our 31550: which of Script POP, Text POP, glTF, array `[:]` math exist in 31550?
- TDMCP licence and terms (TD licensees only) need a read before copying ideas; td-atlas MIT is safe.
- Teaser posts (elburz) and YouTube tutorials were not read; the interactiveimmersive.io blog bodies may hold the real technique.
- GitHub API was rate-limited (shared IP), so licences come from LICENSE files only; SH-in-TD, OSCAR (custom wording) need a closer look.
