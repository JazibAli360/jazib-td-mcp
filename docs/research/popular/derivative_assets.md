# Popular: derivative.ca shared assets (key `derivative_assets`), numbers as of 26 Oct 2026

Data: `research_src/popular/derivative_assets.jsonl` (top 60, one line each). Raw files: `research_src/popular/derivative_assets/`.

## Method
- Asset list = the derivative.ca sitemap (`sitemap.xml?page=1,2`): **489 unique `/community-post/asset/...` pages**, every one fetched
  once (single lane, ~2.2 s apart; the server was slow because ~30 other curls hit it at the same time). `robots.txt` asks
  for `Crawl-delay: 10`; the brief said 2 s and I used 2.2 s, so I did not honour the 10 s. Say so if that matters.
- **Metric = "views" printed on each asset page** (the page footer calls the same number "reads"). It is a lifetime counter,
  so older posts are favoured: 2020 posts hold 30% of all asset views, 2026 posts only 5%. Total over all 489 assets:
  789,825 views, median 739 per asset.
- **Comments / likes**: the page shows "0 Comments" for every post (an unfilled template placeholder), so I read the
  Discourse topic each page embeds (`forum.derivative.ca/t/<topicId>.json`): comments = `posts_count - 1`, likes =
  `like_count`. No Discourse topic for td-shadertoy (#13), timeBase (#20); CamSequencer's topic is 404 (#59).
- The tag pages (`/tags/asset`, `/tags/free`, `/tags/tox`) list only ~10 posts, no counts, no pagination: no use for ranking.
  The "Most viewed" sort (`/community?type[]=24&sort_by=views`) did **not** follow the printed counts (412, 395, 778, 253 ...
  in its first rows), so I ranked by the per-page number, not by that sort. There is no "featured/most read" block anywhere
  on derivative.ca (home, community, resources checked).
- **Palette** (docs.derivative.ca `Category:Palette`): lists **142 component pages**, no popularity numbers at all (MediaWiki
  gives none). Names only, see "Palette" below. OP Snippets doc says "1000+ live examples", also no numbers.
- GitHub numbers (stars, licence, push date) via `gh api`, same day.

## Top 30 (views | comments | likes)
1. **Colour Lover Palette Picker** 64,800 | 32 | 12. Browse colourlovers.com palettes (TOP/NEW/RANDOM/HUE/FAV tabs), drag out. 238 KB tox, downloaded.
2. **TouchDesigner Project File Pack Vol.2** (polyhop) 57,726 | 3 | 1. Four small .toe files (hexagon instancing, mouse-light feedback, TOP instancing particles). Views look inflated by YouTube traffic. Downloaded.
3. **Gaussian Splatting** (Milkorva, 2024) 17,928 | 38 | 28. PLY splat renderer in a Render TOP; heavy at low alpha thresholds. Most-discussed asset. Downloaded 55 KB tox.
4. **TouchDesigner and Lasers** 13,065 | 3 | 0. ILDA laser output via Laser CHOP and AVB audio device. Repo Laser-Control (53 stars, no licence). Laser safety text.
5. **Serum Template** (snaut) 10,344 | 4 | 0. 2D particle system without GLSL; non-commercial, credit required. Downloaded.
6. **Constraint Simulation Tool** (Josef Pelz) 9,930 | 5 | 1. Cloth via compute-shader spring constraints. Non-commercial. Zip has Houdini files. Downloaded 9.9 MB.
7. **Slamtec RPLidar support** 8,977 | 56 | 5. C++ CHOP for RPLIDAR A1..S3 (SlamtecCHOP, 40 stars). 56 comments = support thread.
8. **Water ripple effect** 8,297 | 0 | 0. GLSL TOP height-field wave, from Shadertoy 4dK3Ww. 2.6 KB tox. Downloaded.
9. **POINTCLOUDS from 2D images (+depth)** (gnomalab/B2BK) 7,472 | 12 | 4. Depth-map point clouds morphing. Downloaded.
10. **Fluid simulation component** 7,283 | 9 | 7. 2D stable fluids (Stam, Bruno Imbrizi GLSL), mouse source. Downloaded.
11. **3 templates for Kinect skeleton visualization** 7,025 | 0 | 0. Points/lines/metaballs. Kinect CHOP, Windows.
12. **TD PIP** 6,819 | 21 | 3. Per-project Lib folder + `InstallPackage(name)`; hosted on olib.amb-service.net. Directly useful for MCP/Python work.
13. **td-shadertoy** (Matthew Wachter) 6,805 | n/a. Shadertoy API browser/converter. MIT, 103 stars. Cloned.
14. **TDNeuron** 6,764 | 2 | 0. Neural nets in compute shaders. GPL-3.0, 158 stars. **Windows only** per page.
15. **Tau Ceti Preset Engine** 6,519 | 88 | 14. Preset Stack, Tweener, dashboard, cuelist, mapper. Hosted on olib. Largest comment thread in the top 30.
16. **Normal Map v.2** 6,151 | 0 | 0. Clean normal map from any heightmap. 1.7 KB tox. Downloaded.
17. **Tweener** 6,077 | 26 | 13. GreenSock-like Python tweens (global shortcut "Tweener"). Downloaded 3 tox.
18. **Shadertoy to TD to Raspberry Pi** 5,943 | 0 | 1. Paste shader into a DAT, "Make TD Shader". Repos louiselessel/*, no licence.
19. **3D volumetric rendering (camera near/far)** (tolch) 5,779 | 10 | 5. Slice scene for LED volumes, DMX/Art-Net or into Resolume/Madrix. Directly relevant to PRISMFEST-type LED work. Downloaded.
20. **timeBase multi-layer timeline** 5,554 | n/a. v15, custom-par driven, "learn from internals". Downloaded 1.5 MB.
21. **Compute Particle System v2.0** (yfx) 5,525 | 8 | 5. Instanced compute particles with heightmap collision, commented GLSL. Downloaded 2 tox.
22. **Ninja Puppet (Kinect CHOP + Nvidia Flow)** 5,425 | 0 | 0. Windows/NVIDIA only. Downloaded.
23. **Colorpicker UI Widget** (Darien.Brito) 5,326 | 0 | 0. Client-facing colour picker (v1.3 by Vasily: 2,695 views).
24. **Instancing Examples** (mir.works) 5,124 | 2 | 1. 40+ instancing examples with explorer UI. MIT, 87 stars. Best learning set in the list.
25. **CRT TV Filter** (hrtlacek, 2024) 5,016 | 8 | 4. GLSL RGB sub-pixel CRT + bloom. Downloaded.
26. **LidarTracker v3.0** 4,943 | 8 | 0. Multi-lidar C++ CHOP, TUIO/UDP; TD 2022+.
27. **QR Code Maker** 4,907 | 6 | 1. Python `qrcode` package; needs external Python path. Downloaded.
28. **RabbitControl (RCP)** 4,792 | 41 | 11. Bidirectional remote control of custom pars (RCP-TD Unlicense, rcp LGPL-3.0). Cloned RCP-TD.
29. **Tap Tempo / Tap Sync** (elekktronaut) 4,666 | 0 | 0. BPM by tapping. MIT. Cloned + 2 tox.
30. **TouchDesigner MCP for Claude (macOS & Windows)** (May 2026) 4,479 | 0 | 0. Drag tox, "Install/Update Claude Desktop". **Patreon-gated, not fetched.** Closest peer to this MCP.

Ranks 31-60 are in the jsonl. Notable: #31 Portals (uisato, Patreon), #32/#53 TD Scripts Blender add-on (Patreon), #34 chainGpu
(CC BY-NC-SA, 116 stars), #36 WaveTOP (TOPs only), #38 Physarum, #39 **RayTK** (3,891 views here but 357 GitHub stars, the best-known
TD library), #40 FreenectTD (Kinect on **Mac**, LGPL), #42 Depth Cam Merger (23 comments), #43 Fluid sim in TOPs, #44 **Claude Code +
MCP server in TD** (3,621; zip of an MCP server + TD-Codex), #47 TD Depth Anything (TensorRT), #50 TouchDiffusion, #54 Simple Preset
System, #55 TD-Completes-Me (162 stars), #57 **Keyframer** (74 comments, 37 likes: most engaged post of the top 60).

## Engagement vs reach (top 60)
- Most discussed: Tau Ceti Preset Engine 88, Keyframer 74, Slamtec RPLidar 56, RabbitControl 41, Gaussian Splatting 38 (+28 likes).
- Most liked: Keyframer 37, Gaussian Splatting 28, Tweener 13, TD-Completes-Me 13, Colour Lover Picker 12, RabbitControl 11.
- Big views but nearly no talk: Project File Pack (57.7k), Lasers (13k), Serum (10k): traffic from YouTube/Patreon funnels.

## What recurs
- **Themes by tag frequency** (all 489 assets): GLSL 43, Python 27, UI 20, tox 18, audio 15, C++ 13, AI 13, MIDI 13, OSC 11,
  RayTK/raymarching 11, VJ 9. Ordered by *views* the top is simulation (fluid, water, cloth, physarum, particles) and
  tooling (presets, tweening, timelines, pip, autosave, completion, keyframing).
- **Ops that carry the list**: GLSL TOP / compute shaders, feedback TOPs, instancing, Python extensions + custom pars,
  C++ CHOPs for hardware (lidar, Kinect), Render TOP.
- **Authors by total asset views** (page account "isabelle" = Derivative's posting/migration account, 155 posts, 246k views,
  so real author often only in the text): polyhop 60k, gnomalab 24k (B2BK), Darien.Brito 23k, snaut 21k, Milkorva 18k,
  videoso 16k, mir.works 12k (Matthew Ragan), elekktronaut 11k, exsstas 9k, jacqueshoepffner 8k, elburz 7.6k. Many are
  Patreon-funded: free tox on derivative.ca, paid extras elsewhere.
- **AI/MCP is new and rising**: two MCP assets are in the top 44 although posted in 2026 (about 4k views each in months).
  Remaining 2026 posts are mostly small; 2020 (93 posts, 235k views) is the golden year.

## Palette (142 pages in Category:Palette, no metrics)
Groups: audio (audioAnalysis, audioSet, equalizer), cameras/3D (camera, cameraBrowser, cameraViewport, arcBallCamera, camSchnappr,
cornerPinSOP/POP, kantanMapper, projectorBlend, quadReproject, stitcher, sweetSpot*, domeViewer), image FX (bloom, feedback,
feedbackEdge, hsvBlur, rgbaBlur, radialBlur, chromaKey, convolve, dilate, pixelate, pointillize, solarize, twirl, sharpen,
softenAlpha, opticalFlow), POPs (pointGenerator, pointMerge, pointRender, pointRepack, pointTransform, pointWeight,
particlesGpu, popDialog, customAttributes), media (moviePlayer, movieEngine, moviePlaylist, autoMediaPlayer, sceneChanger,
synchro* x7), Gaussian splat (gsGeo, gsLoader, gsScene, gsTransform), Bitwig (13 pages), Kinect (kinectCalibration,
kinectPointcloud), tools (logger, probe, operatorPath, search, searchReplace, debugControl, tdPyEnvManager,
threadManagerClient, threadsMonitor, testGrid, virtualFile, webBrowser, webRTC*, signaling*), UI (onScreenKeyboard, geoPanel,
remotePanel, materialDesignIcons, graphPlot). **Which are used most is unmeasured here**; the only numbers I could get for
Palette-like use are the community assets above. A usage ranking needs the forum agents' mention counts.

## Downloaded (all free, no login, never opened in TD)
`research_src/popular/derivative_assets/<rank>_<nid>/` holds **44 files, 23 MB** from derivative.ca download links for
ranks 1-60 that offered a free `.tox/.toe/.zip` (ranks without a link are GitHub/Patreon/off-site). Contents known from
`unzip -l`: Pack 02 (3 .toe + readme), constraint_simulation.zip (9.9 MB, Houdini .hiplc/.hclassic files + tox),
b2bk pointcloud zip (1 .toe + 4 JPG sources), QR Maker zip (tox + sample .toe + PNG), Presets_0.zip (preset .txt files),
**AI_TouchDesigner_MCP_v2.0.0 zip** (`mcp_server/server.py`, `ai_engine/engine.py`, `touchdesigner/orchestrator.py`,
`config/tools_manifest.json`, install.py, examples) and **TD-Codex-Phase6.zip** (README, pytest tests: test_memory,
test_synthesis, test_bridge_client) plus `mcp_webserver_base.tox` (all from post 74168, no licence stated).
Cloned (`--depth 1`, licence on repo): `repos/td-shadertoy` MIT 95e0b48, `repos/TD-tapsync` MIT 08d1973,
`repos/TDDepthAnything` MIT 7e15bbb, `repos/RCP-TD` Unlicense 0bac384, `repos/TDAzureMerger` MIT 7ed89c3.
Not fetched: Patreon/Gumroad items (#2 extras, #30 MCP, #31, #32, #53, #59), big repos (RayTK 5.7 MB is fine but covered
by the github agent; geoMusica 495 MB; mir-lab instancing 115 MB; function-store 1.3 GB), oversized/no-extension attachments.
Per-file sha256 prefixes were not stored in the jsonl; commits are.

## Windows / NVIDIA / hardware-only flags
TDNeuron (page: Windows only, compute shaders), Kinect CHOP items #11, #22, #60, Nvidia Flow items #22, #35, #36 (WaveTOP
page itself mentions Flow in an example), Nvidia Background TOP #46 (skippable), TensorRT/CUDA #47, #50, GlowSticks (#41,
built on Windows+Nvidia, not stated as required), lidar C++ CHOPs #7, #26, #58 (binaries presumably Windows; no Mac note),
AVB laser output #4. **Mac-friendly with evidence**: FreenectTD (#40 explicit), mir.works instancing (macOS note only about a
scrollbar), MCP for Claude (#30 explicit, paid). Pure TOP/GLSL-TOP/Python assets are likely fine on our Rosetta/Vulkan
build but **compute-shader ones (#6, #14, #21, #34) are untested on MoltenVK**: not claimed.

## Gaps and open questions
- Views are lifetime and age-biased; no per-year rate. A "views per year since posting" rerank would lift the 2024-2026 items.
- Tutorials (video series with .toe) are not in this key (other agents); derivative.ca tutorials are not in my ranks.
- Licence is rarely stated on asset pages: most "not stated" mean unspecified, not free for commercial use. Serum and
  Constraint Simulation say non-commercial.
- Authors blank or "isabelle" for ~60% of posts; real authorship needs the post text or repo.
- Do the two 2026 MCP assets (#30, #44) overlap this project's tools? Downloaded #44 files are readable for comparison only.
- Palette usage ranking is open (no metric exists on docs.derivative.ca).
