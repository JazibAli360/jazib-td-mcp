# Popular on the Derivative forum: most replied / liked / recently active (`forum_hot`)

Agent `forum_hot`, 26 Oct 2026. Source: forum.derivative.ca Discourse JSON API (public, no login), plus the linked
derivative.ca community-post pages (for view counts) and GitHub. **Numbers are as fetched on 26 Oct 2026.**
Raw data: `research_src/popular/forum_hot/` (`topics/` 76 thread JSONs, `repos/`, `files/`); items:
`research_src/popular/forum_hot.jsonl` (75 rows). Companion agent (top-VIEWED per category) lives in `research_src/forum/`.

## Method
- Lists pulled per category (ids 5,49,6,7,8,9,10,11,12,13) with `order=likes` and `order=posts` (3 pages for the big
  ones), `/l/top.json?period=monthly|quarterly` per category, and global `top.json` (monthly/quarterly/yearly) and
  `latest.json?order=likes|posts`: 76 list files, 1,372 distinct topics. Removed the 216 ids the views-agent already
  holds, selected 76 (top posts, top likes, recent-by-likes, community-post comment threads, Shared .tox by likes),
  read each first page of the thread (OP, Derivative-staff replies, most-liked reply, attachment links).
- Rows are ranked by `likes + posts/4` (replies weigh less than likes); each row carries all three numbers. This is a
  **forum-engagement** ranking, not a download ranking: Discourse exposes no download counts. Community-post pages
  (derivative.ca) do expose page views; GitHub release assets expose download counts (TDMCP only).
- Downloads obeyed the BRIEF (free, no login, <= 50 MB, own folder per item, nothing opened or run in TD).
  Repos without a stated licence were not kept (td-rs cloned, found unlicensed, deleted).

## Headline findings (read these first)
1. **Derivative now ships its own official TD MCP: `TouchDesigner/TDMCP`** (beta, forum thread t/1017912, Sep 25 2026;
   releases 1.1.54-1.1.56 = 2,469 asset downloads; 62 stars). One `TDMCP.tox` runs an MCP server *inside* TD
   (streamable HTTP `127.0.0.1:13316/mcp`, OAuth consent panel, localhost-only, no telemetry, every edit = one undo
   step, editor flashes touched ops). 26 tools: project_info, list/search_operators, get_operator_info, get_connections,
   get_help, get_docs (reads TD docs), get/set_parameters, pulse_parameter, edit_custom_parameters, create_operator,
   build_network, wiring, edit/reposition/delete_operator, annotation, get/set_dat_content, get_errors, inspect_values,
   view_operator (image capture), get_cook_performance, execute_code, save_project. Companion `TDMCPSkills` (19 `td-*`
   skills, 13.3k words: general, colab, working-mode, build-planning, node-layout, network-cleanup, performance-check,
   per-family top/chop/sop/dat/mat/pop, glsl-shaders, python-extension, comp-architecture, lister-ui, review-network,
   geometry-instancing). **Requires TD 2025.33230+; our target is 2025.31550, so it cannot be used as-is.**
   Licence: Derivative Shared Use License + Tool Terms (use with licensed TD; modified redistribution allowed with notice).
   Staff advice (Jarrett): models read networks well, build complex ones badly; keep the human in the loop, use `/td-colab`.
   -> Prior art to mine for this MCP: tool surface, skills text, consent/undo/flash UX. Downloaded, not run.
2. **Text project format is coming**: robmc (t/309048, t/298851): `toeexpand`/`toecollapse` exist in TD's `/bin` today; a
   JSON, git-friendly format (single file / file-per-network / file-per-node) is in internal testing. Highest-value
   future capability for an MCP (read/write projects as text). 28 and 49 likes.
3. **Shared .tox category is retired**: ben (t/1018374): new shares go in "ASSET posts" in the derivative.ca Community feed;
   the forum category is an import of old posts. Asset pages show a GitHub link (e.g. Keyframer -> IntentDev/Keyframer).
4. **Naming**: greg (t/1011213) asks community tools to use a `TDX` prefix (TDMorph -> TDXMorph, TDN -> TDXN). Apply to our tool names.
5. Most-liked thread overall is the Linux request (t/11349, 178 likes, 113 posts) and Vulkan (t/144033, 91): both
   already in the views-agent set; they say what the community wants from Derivative, not components.

## Top 30 (forum engagement, `likes + posts/4`)
1. **POPs-A new Operator Family for TouchDesigner - 2024-05-19** (t/476729, comments) - likes/posts/views 61 / 37 / 4724; community page 30,537 views; rel 3.  
   POPs announcement community post (new operator family, GPU point/particle ops): 30,537 views on derivative.ca; Mac: yes (Vulkan/Metal path). Licence: -.
2. **Next Devices, Protocols and Tools to Support in TD** (t/961393, general) - likes/posts/views 53 / 30 / 1062; rel 2.  
   Derivative's 2026 planning poll: which devices/protocols/tools should TD interface with next. Mac: n/a. Licence: -.
3. **Git compatible toe / tox files** (t/298851, wishlist) - likes/posts/views 49 / 27 / 1696; rel 3.  
   Git-compatible toe/tox. Mac: n/a. Licence: -.
4. **Keyframer Comp - 2021-04-12 12:29** (t/180791, comments) - likes/posts/views 37 / 75 / 4583; community page 3,214 views; rel 2.  
   Keyframer: keyframe editor panel COMP replacing the built-in animation editor; Mac: likely (no GLSL). Licence: none stated on GitHub.
5. **Reading timecode from Blackmagic / AJA devices** (t/169902, wishlist) - likes/posts/views 41 / 39 / 4748; rel 1.  
   Timecode from Blackmagic/AJA: BMD VITC send/receive added in 2021.12450+ via Info CHOP on Video Device In TOP; Mac: BMD driver dependent. Licence: -.
6. **Experimental Build 2021.39010 posted** (t/232651, general) - likes/posts/views 41 / 18 / 1465; rel 2.  
   Experimental 2021.39010: entire graphics pipeline ported OpenGL->Vulkan (the reason all current TD is Vulkan; Mac: explains MoltenVK on macOS. Licence: -.
7. **RFE: Disable/Hide Timeline** (t/198286, wishlist) - likes/posts/views 41 / 15 / 1290; rel 1.  
   Timeline dialog costs 0.5-2 ms/frame; Mac: path differs on macOS. Licence: -.
8. **2022 Official Update - 2022-05-25 14:28** (t/265743, comments) - likes/posts/views 38 / 16 / 3229; community page 48,232 views; rel 1.  
   2022 Official Update community post: 48,232 views (largest community post found); Mac: -. Licence: -.
9. **Nvidia Flex Build** (t/120669, general) - likes/posts/views 32 / 31 / 5738; rel 0.  
   Nvidia Flex experimental build: Flex Solver COMP, Actor COMP, Force COMP; Mac: NO: Windows/NVIDIA only. Licence: -.
10. **Covid19 Community Check-in, Resources, What's in Development & Let's T** (t/136705, general) - likes/posts/views 35 / 12 / 2136; rel 0.  
   Covid community check-in; Mac: -. Licence: -.
11. **Gaussian Splatting - 2024-03-04** (t/439835, comments) - likes/posts/views 28 / 39 / 2287; community page 17,928 views; rel 2.  
   Gaussian Splatting example (Mar 2024): 17,928 views; Mac: fork needed for Apple Silicon. Licence: forks have no licence.
12. **A simple Q&A bot from the TouchDesigner offline wiki (OpenAI, Pinecone** (t/331508, general) - likes/posts/views 32 / 17 / 1184; rel 2.  
   Q&A bot over the TD offline wiki (OpenAI+Pinecone+LangChain); Mac: yes. Licence: -.
13. **Python debugger/profiler** (t/298670, wishlist) - likes/posts/views 29 / 29 / 1454; rel 2.  
   Python debugger/profiler requests for TD; Mac: yes. Licence: -.
14. **Preset System - 2019-10-23 13:58** (t/110130, comments) - likes/posts/views 14 / 89 / 6983; community page 6,519 views; rel 2.  
   Preset System community asset (6,519 views, 89 posts): presetSaver/presetFader tox. Mac: yes. Licence: unstated.
15. **Lottie for TouchDesigner?** (t/223940, wishlist) - likes/posts/views 31 / 10 / 843; rel 1.  
   Lottie for TD wishlist; Mac: yes. Licence: -.
16. **A plugin framework for custom operators in Rust!** (t/395221, general) - likes/posts/views 30 / 11 / 1162; rel 2.  
   td-rs: Rust framework for writing custom TD operators (CHOP/DAT/SOP/TOP/POP) with PyO3 python integration; Mac: yes (macOS env vars documented). Licence: none stated in repo (not cloned).
17. **Remote Controlling Touchdesigner from iOS devices** (t/239406, general) - likes/posts/views 21 / 47 / 3744; rel 2.  
   TMote: iOS remote for TD - NDI receiver app sends back TUIO; Mac: TD side yes. Licence: unstated.
18. **TDMorph - 2020-01-08 02:25** (t/118937, comments) - likes/posts/views 18 / 57 / 5917; community page 780 views; rel 3.  
   TDMorph (renamed TDXMorph Aug 2026): preset/parameter morphing; Mac: yes. Licence: MIT.
19. **Request: HEX Support in Native Color Picker** (t/215219, wishlist) - likes/posts/views 29 / 9 / 2347; rel 2.  
   Hex support for TD color picker: community hex_paster.tox (43 KB) and hexler.tox (1.4 KB); Mac: yes. Licence: unstated (forum post).
20. **TouchDesigner on Linux - Automated Installer, Auto-Patching & Multi-ve** (t/978051, general) - likes/posts/views 28 / 13 / 1492; rel 1.  
   TouchDesigner on Linux via Wine: one-command idempotent installer, multi-version manager, Wayland tweaks. Mac: n/a (Linux). Licence: MIT.
21. **Just a Line TOP** (t/283772, wishlist) - likes/posts/views 25 / 25 / 2370; rel 2.  
   Just a Line TOP: staff reply with lineRender.tox (sopRender hacked with Line MAT); Mac: yes. Licence: -.
22. **Several issues after extensive Orbbec Femto Bolt testing** (t/426057, bugs) - likes/posts/views 23 / 33 / 3880; rel 0.  
   Orbbec Femto Bolt: switching Orbbec/Azure TOPs crashes; Mac: Windows (Azure SDK). Licence: -.
23. **.toe files in text format** (t/309048, general) - likes/posts/views 28 / 11 / 1144; rel 3.  
   How to see/write .toe as text. Mac: check /bin for macOS equivalents. Licence: -.
24. **AI upscaling and faster upscaler with Nvidia Maxine SDK** (t/239202, wishlist) - likes/posts/views 24 / 27 / 3492; rel 0.  
   Nvidia Maxine SuperRes/upscaler request; Mac: NO: NVIDIA. Licence: -.
25. **Experimental Setup: TouchDesigner on Linux via Bottles - 2025-10-04** (t/809825, comments) - likes/posts/views 24 / 26 / 1540; community page 8,250 views; rel 0.  
   Official experimental Linux-via-Bottles setup (Oct 2025), 8,250 views; Mac: n/a (Linux). Licence: -.
26. **Add "Rename CHOP" functionality to all CHOPs** (t/504242, wishlist) - likes/posts/views 28 / 8 / 249; rel 1.  
   Add rename to all CHOPs (28 likes); Mac: -. Licence: -.
27. **FIXED: Engine Comp License Error - TouchDesigner099.2019.30550** (t/12566, bugs) - likes/posts/views 15 / 56 / 3423; rel 1.  
   Engine COMP license error fixed; Mac: -. Licence: -.
28. **RFE: integrate Poetry package manager with TD** (t/168073, wishlist) - likes/posts/views 25 / 14 / 1391; rel 2.  
   Poetry package manager for TD python envs; Mac: yes. Licence: GPL-3.0.
29. **Linear vs Gamma PBR workflows in Touch** (t/135812, general) - likes/posts/views 24 / 18 / 5582; rel 3.  
   Linear vs gamma (sRGB) in PBR render networks; Mac: yes. Licence: -.
30. **Add Gemini 5.2 support ( Ultraleap )** (t/224190, wishlist) - likes/posts/views 20 / 22 / 1823; rel 0.  
   Ultraleap Gemini 5.2 support pending; Mac: Windows/mac drivers vary. Licence: -.

## What recurs
- **Derivative asks the community for direction and answers in-thread**: roadmap polls (t/961393: glTF + splats, TUIO 2.0,
  .spz), RFE threads with staff (greg, robmc, malcolm, eric.b, Ivan, snaut/Markus) answering in detail. Most-liked RFEs:
  text/git project files, timecode, hex colour picker, timeline hide, Python debugger, rename in CHOPs.
- **Authors who recur as sharers**: alphamoonbase (Preset System, run() trick), dylanroscover (hexler, Timecode, Lottie
  advice), timgerritsen (volumetric fog, LineTOP, webserver IP), lucasm (linear/gamma, FFT ocean PBR, wiki bot),
  Darien.Brito (TDXMorph), keithlostracco (Keyframer), snaut/Markus (Kantan, RabbitControl, optical flow).
- **Component themes by likes/replies**: preset/parameter morphing (Preset System, TDXMorph), keyframing UI (Keyframer),
  remote control (TMote, RabbitControl, TDAbleton), GLSL tricks (volumetric fog, physarum compute, attribute transfer,
  FFT ocean), Gaussian splats, depth sensors (Kinect/Orbbec/ZED/RealSense), Linux/Wine, Vulkan migration fallout.
- **Ops that recur in the shares**: GLSL TOP/compute, Script/Text DAT + Python extensions, Custom Parameters, Render+Depth
  TOP, Speed/Math CHOPs, NDI/TUIO/OSC/WebSocket, MIDI In DAT.
- Recent (last 90 days, small counts): TDAbleton 2.6.8 bugs, .ply loading regression (33070), AML (macOS ANE operator
  family, Patreon), POPTOBER, ValYouLa pricing DB, TDMCP.

## Downloaded (listing only; nothing opened or run)
- `repos/TDMCP` (licence + README + docs + CHANGELOG; no source: the logic lives in the .tox), `repos/TDMCPSkills`
  (19 skill folders, build_plugin.py, validate.py, smoketest/), `files/TDMCP_release_1.1.56/` (`TDMCP.tox` 305 KB,
  `TDMCP-Skills-1.4.1.zip` 75 KB). Commits in the jsonl.
- `repos/TDXMorph` (MIT; README, Assets/ pngs; downloads table points to release .tox files, not fetched),
  `repos/RCP-TD` (Unlicense), `repos/TD-Remote-Tools` (MIT, igalabs), `repos/TouchDesigner-Linux` (MIT),
  `repos/Quick-Fast-Hurry-HAPQ-Converter` (MIT), `repos/touchdesigner.camera-calibration` (MIT, C++ DAT, 17 MB),
  `repos/poetry-managed-td` and `repos/LTC-Timecode-Generator` (GPL-3.0). All shallow clones.
- `files/` 36 forum attachments (plus the 2 TDMCP release files above) (all .tox/.toe, forum uploads, unlicensed unless the post says so): hex_paster/hexler,
  lineRender, LineTOPExample*, TMote(+Example), VolumetricFog (+2022), endless_slider + MIDI CC, GLSL_compute (+2021),
  FFTOcean (+pbrWIP), timeline/Timecode/setBottomPaneHeight, presetFader/presetSaver, vocal pitch tracker,
  Attribute_Transfer, kinectDepth/depthProjection, createProperty/delExt, RunTime/timeTest, wine_ui_fixes, FlexSnippets.
  Not downloaded: .dmp/.crash files, paid/Patreon (AML), repos without licence (Keyframer, GaussianSplat forks, td-rs).

## Windows / NVIDIA-only flags
Flex (Windows+NVIDIA), Maxine upscaling (NVIDIA), original Gaussian-splat GLSL (Windows+NVIDIA; Apple-Silicon fork exists
but unlicensed), Orbbec/Kinect Azure/ZED/RealSense/Slamtec/3Dconnexion/Leap (Windows drivers or CUDA), TouchEngine for
Unreal (Windows), DirectX/TextureShare sharing. Linux = Wine/Bottles only. TDMCP itself documents macOS paths but needs a newer TD.

## Gaps
- Discourse has no download counts; Community **Asset** posts (the real "most downloaded .tox" list) are only reachable per
  page on derivative.ca, and I found no ranked index to crawl (a Drupal listing query returned nothing usable). Ranking
  assets by downloads needs another approach (e.g. crawl `derivative.ca/community-post/asset/*` links from the forum).
- Only the first page (about 20 posts) of long threads was read; accepted-answer flags are rarely used on this forum.
- Shared .tox category totals 430 topics; the views-agent covers most-viewed ones, I covered most-liked/replied.
- Attachment licences are not stated; treat all forum .tox as study material, not redistributable.

## Open questions
- Can the user's TD be moved to 2025.33230+ so TDMCP could be tested next to `jazib-td`? (decision for the user).
- Does the new text project format ship in a release newer than 2025.33230? Probe `toeexpand` in
  `/Applications/TouchDesigner 2.app` (macOS binaries) before assuming.
- Worth porting TDMCP's skills text (td-general, td-working-mode, td-node-layout, td-glsl-shaders) into our docs under the
  Shared Use License notice rules? Needs the user's go-ahead.
