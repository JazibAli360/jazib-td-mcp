# Community slice 08: listing pages 140-159 (26 Oct 2026)

Crawled `derivative.ca/community?page=140..159` (20 pages), then every post page: **305 posts read, 0 failed**. Dates mostly Jun 2020 to Feb 2021 (the old end of the feed), plus 5 pinned/new Oct 2026 posts that appear on these pages (75535, 75538, 75551, 75560, 75562). Relevance is scored 0-3 for general TouchDesigner mastery (user scope update, 26 Oct). Data: `research_src/community/slice_08.jsonl`.

Counts by type: tutorial 121, post 85 (community/company/gallery), asset 49, event 32, workshop 18, job 0. Relevance 3: 47, 2: 84, 1: 100, 0: 74. Server was slow (6-20 s per page) because ten agents crawl at once; rules kept (2 s sleep, one lane, no login).

## Top 15 by relevance
1. **RayTK: raymarching for the masses (tekt/t3kt)** (63620). Node-based raymarching toolkit, no GLSL; Alt+R op menu, self-contained, usable for 2D image processing and volumetric sampling for LED rigs. Releases 0.9 and 0.11 (+docs site, posts 63888, 63712, 63732, 63893) target 2020-2021 builds; repo is >50 MB so not stored by me. Modern RayTK versions track newer builds: check the current release before use.
2. **TouchDesigner POPs vs SOPs (elburz, Oct 2026)** (75538). Teaser for the POP (GPU point operator) vs SOP comparison and point-cloud workflows. POPs are the 2025-era geometry system; follow the link for the full article. Companion: 75535 Aura Flow POP trail tutorial (colour via point attributes, material, motion).
3. **UberGui V4 (lucasm / EnviralDesign)** (63859). HTML/CSS UI rendered by Web Render TOP on top of Custom Parameters; claims ~1 ms cook at 60 fps. MIT, GitHub EnviralDesign/UberGui (built for 2021.12380). Strong candidate pattern for responsive control UIs.
4. **RabbitControl RCP-TD (snaut)** (63238). Exposes custom parameters bidirectionally over the RCP protocol to other TD instances, web or apps. Unlicense, GitHub wuestenarchitekten/RCP-TD v0.87. Sibling: 63523 webGUI (Custom Parameters to web page via WebSocket) and 62976 Browser Interface.
5. **Shadertoy to TouchDesigner converter (louiselessel)** (63259). Paste Shadertoy code, press Make TD Shader; mouse/video inputs pre-wired; errors show in the GLSL TOP info DAT. Respect each shader licence. GitHub louiselessel/Touchdesigner-tools (also shaders-to-Pi route and mesh/point tools).
6. **Generative color palettes (exsstas)** (63171). Inigo Quilez cosine palettes in GLSL, with GLSL MAT, raymarching and fractal examples; palettes.toe works without GLSL knowledge. Downloaded (.toe x2).
7. **Tileable noise collection (exsstas)** (63593). GLSL ports of seamless noises from an MIT-licensed repo for textures and displacement maps. Downloaded (.toe).
8. **The Big Bad Lister parts 1-3 (mir.works / Ragan / DelSol)** (63514). Deep dive into the palette Lister COMP, plus Blister (63797) as a simpler parameter-driven setup. Raw .toe files from GitHub raganmd/touchdesigner-lister-blog downloaded (parts 1-3: 63514, 63551, 63568).
9. **TD PIP (alphamoonbase)** (63077). Per-project Lib folder + pip installer so external Python libraries ship with the .toe; useful for any Python/AI-library work. Same author: Python Tips n Tricks #2 (62965), File Downloader, Stream Fileserver, Twitch Chat, Storage Viewer.
10. **2021 Official Update (Derivative)** (63810). Op inventory of the 2021 build: Lens Distort TOP, FreeD CHOP, Phaser CHOP, Sprinkle SOP, Point Transform TOP, JSON DAT, SRT/HLS streaming, NotchLC; Spectrum TOP and wrnchAI/cuDNN features need NVIDIA/Windows.
11. **Engine COMP intro + pro tricks (63004) (elburz)** (63059). Run parts of a project on other threads/processes. Video tutorials; useful for heavy-UI or Python isolation patterns.
12. **Pro workflow set (elburz)** (63116). Movie loading without frame drops (63116), Python optimisation (63141), packaging projects (63122), a non-crashing while loop (63273), output movies (62995), Text TOP tricks (63063, 63524), LUT stylising (63149/63587), workflow speed boosts (62966). Mostly video or blog pointers.
13. **Script TOP + OpenCV tutorials (elburz)** (63688). How to get OpenCV results back into a TOP (numpy array in/out) and out into CHOPs (63692). Core technique for CV/ML work in TD.
14. **Depth Cam Merger v0.4.0 (Darien Brito)** (63795). Merges multi-depth-camera point clouds (Kinect Azure, Orbbec, ZED or any TOP pair) with markerless calibration; Open3D runs in an external Python process, TD uses only numpy. MIT, tested on 2025.33070. Best example here of external-process Python from TD.
15. **AVY performance framework (elekktronaut, Oct 2026)** (75562). Modular live framework (presets, MIDI map, FX, modules, audio analysis, OSC, Ableton Link, web UI), built with AI over 6-8 months. Paid/key via Patreon, not fetched; design reference for a rig.

## Files downloaded (never opened, run or imported)
**45 single files** (.tox/.toe, 1.8 MB total) in `research_src/community/files/<postid>/`, all free, no login, <= 340 KB each. Licence is not stated on any of the posts (treat as personal-use reference; credit author). Build stated only where noted. Names by post: 
63863: Kinect SOP setup.toe; 63890: Easing_Functions_0.tox; 63882: spider.toe; 63894: KinectRenderPickBasic.toe; 63821: uiStatus_NodePar_Subs.tox; 63797: Blister.361.toe; 63765: bypassHandler.tox; 63757: audioSpectrum8.5.tox, graphPlot8.5.tox; 63763: Wave_ripples.tox; 63702: cycles.7.tox; 63717: StepperMotor_TouchdesignerCode.2.toe; 63686: BS_902.tox; 63627: PointField.238.toe, PointField.297.toe, PointField.327.toe; 63677: EcuacionesParametricas_Tutorial_Parte_3.toe; 63675: Color_Harmony_beta.tox; 63640: yfxGlowSticks-1.0.tox, yfxGlowSticksExample.tox, GlowSticksExample-1.1.tox - version 2022.28040, yfxGlowSticks-1.1.tox - version 2022.28040; 63654: EcuacionesParametricas_Tutorial_Parte_2.toe; 63664: 2D vector fields - public.toe; 63625: Circle_Tutorial.toe; 63593: Tileable noises (public version).toe; 63568: big-bad-lister-part3.toe; 63551: big-bad-lister-part2.toe; 63557: VHS#tutorial.toe; 63523: webGUI_0.tox, webGUIExample_0.toe; 63514: big-bad-lister-part1.toe; 63516: Particles on SDF - tutorial.toe; 63277: gateCHOPComp.tox, gateCHOPComp_examples.toe; 63285: REATOUCH.toe; 63208: MP_ADAM6060D_IF1.tox, MP_ADAM6060D_IF1_sampleOSC.toe; 63146: FRUIT_QUIZ.5.toe; 63171: palettes.toe, palettes_examples.toe; 63125: Quantization Height Map Free.toe; 63075: MP_dmxFader1_013.toe; 62997: TD_SearchPalette.v.1.3.tox; 62978: storageViewer.tox.

**Git clones (depth 1, hash, size, top-level contents from listing only):**
- 63835 `picturesbyrobots/TD-threaded-tcp-transfer` @ 6b94904 (3.2 MB): examples, README, release, src (TCP file transfer toxes + scripts); no licence file.
- 63284 `wuestenarchitekten/folderToServer` @ 0886df5 (1.1 MB): folderToServer.tox, README; no licence file.
- 63055 `simplo/qtter` @ b283825 (30 MB): qtter.toe, README, png + mp4 demo; no licence file.
- 62997 `yeataro/TD-SearchPalette` @ f3097a6 (0.7 MB): TD_SearchPalette.tox, src, img, README; MIT.
- 62983 `wuestenarchitekten/collection` @ ae4e835 (3.8 MB): many small examples (ASCII, crossHatch, frequencyModulation, gameOfLife, hyperCube, imgBBUploader, LEDCubeRender, OPColorSetter, perInstanceDeform, smoothAcid...); Unlicense.
- 63528 `visual-gate/nature_controled_sounds` @ 400d845 (2.0 MB): v1.toe, README, sea.PNG (GLSL sea driven by MIDI); no licence file.
- Already present from another slice (same post-id folders, reused; I only read `git rev-parse` and listings): 63859 UberGui a46ac68 (MIT; css, javascript, python, UberGui_V4_Release.toe, UGV4.tox); 63795 TDAzureMerger 7ed89c3 (MIT; TDXDepthCamMerger.tox, src, tests, tools); 63736 Laser-Control 66f397d (Laser.toe, pathCreator.tox; README says Windows / Mac); 63676 TD-JUCE 2421168 (C++/CMake JUCE plugin; Windows tested, OSX not fully tested); 63238 RCP-TD 0bac384 (RCP_TD.tox; Unlicense); 63259 Touchdesigner-tools 16bb487 (shader converters, utilities, mesh/point tox files); 63231 TD-Speedy-Shaker 6853b6b (Speedy_Shaker_v1_11.tox + examples; GPL-3.0); 63013 LidarTracker c435edd (tox v3.2.3/3.2.6; TD 2022+).
- Not stored: `t3kt/raytk` (clone passed 110 MB, aborted; another slice holds it at files/72698/raytk) and `ruigato/geoMusica` (61 MB, GPL-3.0). External-hosted files (Google Drive, Dropbox, bit.ly, Patreon, qualia.social) were recorded only.

## Recurring techniques and operators
- GLSL everywhere (25 GLSL-tagged posts): GLSL TOP/MAT, compute-style particles, fluid sim, ports from Shadertoy and Inigo Quilez; instancing (geometry, texture, TOP-driven) is the other staple; raymarching via RayTK or exsstas tutorials.
- Web-based control: Web Server DAT, WebSocket, Web Render TOP (UberGui, webGUI, Browser Interface, RCP, folderToServer, 'web front-ends' video) is the community's answer to control panels.
- Python infrastructure: extensions with properties, `run()` instead of while loops, TD PIP, storage viewer, Script TOP + OpenCV/numpy, external-process Python (Open3D).
- Ops most named: Text TOP (typography series 'Touching Typography', 'Kinetic Typography'), Math/Lookup/Function CHOPs, Engine COMP, JSON DAT, Script TOP/CHOP/SOP, Lookup TOP/Ramp TOP for palettes and LUTs, Lister COMP, Edge/Displace TOPs plus Feedback for ripples and pixel sorting.
- Ableton/MIDI/OSC: TDAbleton (several tutorials, Korean series), Ableton Link, Reaper OSC, MIDI mapping, DMX/Art-Net fader, laser CHOP over AVB, ESP8266 LED pixel-mapping.
- Sensors: Kinect (7 posts), Leap, lidar, blob tracking from a webcam; depth-camera merging.

## Authors who post a lot
elburz (70 posts; mostly Interactive & Immersive HQ video tutorials and blog pointers), isabelle (18; Derivative staff: events and company stories), noones_img (18 short tutorials, video only), narumin256 (11 TDSW workshops, Japan), exsstas (9; GLSL/raymarching, free .toe plus Patreon), digital.rain (9; Korean tutorials), alphamoonbase (9; utility components), Artechs (7), elekktronaut (7), tekt (6; RayTK), Simplo (6), orelln (6; gallery videos).

## Windows-only / NVIDIA-only items
Notch-related posts (Blocks need Windows, 58, 62, 84, 108, 119, 128, 134), Kinect posts (2, 17, 75), Show Machine Setup for Windows 10 (63572), Control Room 42 and Elsewhere (Windows VMs, NVIDIA AR), 'Time for RTX?', Spectrum TOP, wrnchAI and cuDNN features in the 2021 update. GlowSticks (63640) was built on Windows+NVIDIA but is GLSL, so Mac status is untested. Mac statements in the data are 'unknown' unless a repo README said otherwise (Laser-Control: Windows / Mac).

## Skipped items
None skipped for leak/rights; no title mentions leaks or cracks. Patreon-only extras (not fetched): AVY alpha (75562), Kinect templates with examples, exsstas project files (63728, 63664, 63516, 63593 extras), Kohui project files, midi/audio sync TOX (63753), UberGui support.

## Open questions
- Many assets are 2020-2021 era: they were not run, so which still work on 2025.31550/macOS is unverified. Candidates to test first: Easing Functions CHOP, bypassHandler, storageViewer, TD_SearchPalette, palettes.toe, tileable noises (GLSL/Python only, no hardware).
- Licence is unstated on most posts; only repo LICENSE files give MIT/Unlicense/GPL-3 facts.
- Event/workshop pages (50) carry no reusable technique; 'noones_img' and many elburz posts are video-only, so techniques are inferred from title/tags and marked as such in the JSONL.
- RayTK current release, POP tutorial series (75535) and Open3D article (75560) are worth a targeted follow-up fetch.
