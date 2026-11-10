# derivative.ca top-viewed ASSETS, slice 03 (listing pages 14-19, 26 Oct 2026)

Source: `https://derivative.ca/community?sort_by=views&type%5B%5D=24&page=14..19`. 105 distinct posts read (90 teasers + 15 distinct promoted), all post pages fetched (2 s spacing, 0 errors). JSONL: `research_src/community/top_assets_03.jsonl` (full fields incl. per-file audit). Scope: general TouchDesigner use, not PF26-only. Build for live claims: TD 2025.31550 on macOS.

## Listing quirks (the lead must know before merging)
- Same finding as slices 01/02: each listing page = 20 articles; the **first 5 are a rotating promoted block** (1 wide + 4 mid; the same posts repeat across pages, e.g. 68631, 71417, 71010, 73039, 70707) followed by 15 teasers. `views_rank` = page*20 + DOM position (1-20), per the brief; promoted items are marked `*` in the table and `featured: true` in the JSONL (their rank is the first page they appeared on in this slice). `listing_index` = position among the 15 teasers.
- The displayed 'N reads' is **not monotonic** with the listing order (p14 teasers: 490, 750, 445, 515, 813, 364 ...), so the 'Most viewed' sort uses a different/cached counter. Treat `views_rank` as listing position only.
- Comment counts are JS placeholders in the HTML (always 0): `comments` left null. 'N views'/'N reads' on the page = `reads` (stored as `views` and `reads`).
- No licence field exists on asset pages; licences come from repo LICENSE files or text on the page ('n/s' = not stated = all rights reserved by default, ask before redistributing).

## Ranked table (rank = listing position, pages 14-19 = ranks 281-400, * = promoted block; Mac: yes = poster/file saved on macOS or stated; likely = pure TD ops, untested; WIN = Windows/NVIDIA only; ? = unknown). Build: W/M = machine the file was saved on
| rank | post | author | reads | cost | licence | build | Mac | what it is |
|---|---|---|---|---|---|---|---|---|
| 281* | 68631 PROMOTE | Unveil_studio | 412 | free | n/s | 2022.35320W | ? | PROMOTE: keyboard shortcut to promote a parameter to a custom parameter |
| 282* | 71417 PiNODEs Beta | pitheorem | 542 | free | GPL-3.0 | 2023.11340W | likely | PiNODEs Beta: GLSL-based point/parametric drawing nodes (TOP point processing), part of PiKi |
| 283* | 72379 Audioreactive Video Playhead - Definitive Edit | uisato | 2182 | Patreon | n/s | n/s | ? | Audioreactive Video Playhead Definitive: audio-driven playhead + Veo (Gemini API) video gene |
| 284* | 73164 TD Copier Tool | GRNCH | 156 | free | None | n/s | yes | TD Copier Tool: ParameterCopier (custom pars 1:1) + OperatorCopier (copy one op to up to 10  |
| 285* | 73301 Repository of Custom Morphological Operators | MaxMainio | 227 | free | MIT | n/s | likely | Morphological Operators repo (MaxMainio): dilate/erode/open/close etc. as TOP components |
| 286 | 65250 JDRenderEngine | jjdeprisco | 490 | free+ | n/s | n/s | ? | Render-to-file 'engine' (JDRenderEngine V3): scene/timeline-style batch render manager so TD |
| 287 | 66736 Pixel Wrangle, a minimalist GLSL framework bui | miu-lab | 750 | free | GPL-3.0 | n/s | ? | Pixel Wrangle: GLSL TOP wrapper framework with auto-generated uniform params, preset/functio |
| 288 | 74073 PCSD V.2 (POP) | Milkorva | 445 | free+ | n/s | 2025.30280W | likely | PCSD V.2: Point Cloud Surface Deformer built on POPs (field splat deformation, Proximity/Lin |
| 289 | 73817 TLWEB - WEB CONTROL | THETOUCHLAB | 515 | free | n/s | 2025.32050M | yes | TLWEB: drive any web page with gestures/sound/data via Web Browser COMP + JS injection, macr |
| 290 | 73917 TD-ML (v.0.2) - Machine Learning Toolkit for T | bi.os | 813 | free | n/s | n/s | ? | TD-ML: ML toolkit as CHOP components (MLP/LSTM classifier+regressor, VAE, UMAP/PCA/KMeans, D |
| 291 | 65200 Tox to Instant convert any TD render in 3D SBS | Simplo | 364 | free | n/s | n/s | ? | renderSBS: tox that converts any TD render to 3D side-by-side / top-bottom stereo |
| 292 | 62063 Schedule Keeper | neonlimbo | 503 | free | n/s | 2019.10700W | likely | Schedule Keeper: table-driven scheduler that fires state scripts every minute inside windows |
| 293 | 64951 miniSEQ | incognite | 453 | free | n/s | 2021.13610W | likely | miniSEQ: small trigger/value step sequencer with UI window, BPM-linked, exports lite static  |
| 294 | 63890 Easing Functions CHOP | Dorian | 529 | free | n/s | 2021.10330W | yes | Easing Functions CHOP: 30+ named easing curves as a CHOP with sample count |
| 295 | 62405 Sensel Morph Raw Output CHOP for Touchdesigner | mouren | 561 | free | GPL-3.0 | n/s | WIN | Sensel Morph raw output C++ CHOP (contact points from pressure pad) |
| 296 | 62978 Storage Viewer | alphamoonbase | 466 | free | n/s | 2020.22080W | likely | Storage Viewer: tree-view of a COMP's storage dict (ReadDict/ReadJson) |
| 297 | 73421 Minor UI Fixes for TouchDesigner on Wine | c0deous | 629 | free | n/s | 2025.31550W | WIN | Minor UI Fixes for TD on Wine: Execute DAT resets 23 text TOPs in /ui/dialogs to scalable fo |
| 298 | 63686 BS 902 | Kephalos | 373 | free | n/s | 2020.20625W | likely | BS-902: mock corporate AV video switcher (8 in, program/preview, logo store/freeze) |
| 299 | 66906 TD scripts v1.2: a Blender Add-on for Touchdes | Artechs | 628 | free+ | n/s | n/s | ? | TD scripts v1.2: Blender add-on exporting SOP/UV/materials and animated camera as CHOP to TD |
| 300 | 63797 Blister COMP - Easier Lister COMP Setup | greg | 512 | free | n/s | 2021.11180W | likely | Blister: parameter-based UI to set up Lister COMP tables (auto-create columns, callbacks, ex |
| 301* | 69724 Vintage Lens Effect Tool | dcheesman | 1311 | free | n/s | n/s | ? | Vintage Lens Effect Tool: chromatic aberration, lens blur, grain, RGB delay, vignette |
| 302* | 69981 Wifi Network Manager | pdubost | 263 | free | n/s | 2021.16410W | WIN | Wifi Network Manager: scan / refresh / connect SSID via Windows netsh |
| 303* | 72196 iXeRemin - Free Download through June 20 | fredfred | 488 | free | n/s | n/s | yes | iXeRemin: visionOS (Apple Vision Pro) theremin app that sends OSC to TD; demo project on Git |
| 304* | 72698 RayTK v0.46 Release | tekt | 269 | free | MIT | n/s | ? | RayTK v0.46: raymarching/SDF toolkit with palette UI re-implemented for TD 2025 experimental |
| 305* | 73359 Post Process Volume for TouchDesigner | tormozgh | 861 | free | n/s | 2022.24200W | likely | Post Process Volume: Unreal-style volume that applies post effects only inside a 3D region ( |
| 306 | 67726 13 Tap Bloom for TouchDesigner | lucasm | 1226 | free+ | MIT | n/s | likely | 13 Tap Bloom: high-quality dual-filter style bloom component (GLSL) |
| 307 | 69505 CONTROL SONY FX9 CAMERA WITH TOUCHDESIGNER | THETOUCHLAB | 342 | free | n/s | 2023.11760M | yes | Sony FX9 camera control from TD (iris/focus via voice or gesture) over network API |
| 308 | 67470 Poisson Fill TOX | igierard | 835 | free | n/s | 2018.28120W | likely | Poisson Fill: fills transparent image areas smoothly (port of ofxPoissonFill) |
| 309 | 73273 Contour Lines Magma Project | cmuir | 276 | free | n/s | n/s | ? | Contour Lines Magma: StreamDiffusion workflow turning contour lines into obsidian/magma |
| 310 | 67779 First Person Camera: Input TOX | invisiblesignal | 802 | free | n/s | 2022.29850M | yes | First Person Camera Input: Joystick + Keyboard In CHOP wrapper for FPS-style navigation |
| 311 | 68778 Strober Effect | hekuli | 552 | free | n/s | n/s | ? | Strober Effect: GLSL strobing with creative options |
| 312 | 67533 PiCompositor v0.1 | pitheorem | 763 | free | GPL-3.0 ? | 2022.32120W | ? | PiCompositor v0.1: layer-based compositing UI (blend, transform, masks, selection sets, solo |
| 313 | 70225 TDMAIL -  Email Trigger System | THETOUCHLAB | 621 | free | n/s | 2023.11760M | yes | TDMAIL: sends emails on triggers via SMTP_SSL |
| 314 | 65699 MetaRamp TOP | KaeganCasey | 1137 | free | n/s | n/s | likely | MetaRamp TOP: Ramp TOP whose keys are all parameter-driven (HSV option) |
| 315 | 65168 TOPs-stacker | igalabs | 498 | free | n/s | 2020.26630W | likely | TOPs-stacker: arrange N TOP inputs in a row/column (CPU, GPU, GLSL variants) |
| 316 | 61048 a minimum timer easy to use and integrate | jacqueshoepffner | 566 | free | n/s | 2019.19160W | likely | myTimer: compact performance timer with OSC out |
| 317 | 61043 Output Controller | alphamoonbase | 580 | free | n/s | 2019.18360W | likely | Output Controller: auto-setup multi-display output with perform-mode (F1) |
| 318 | 62130 AJA Kumo 32x32 SDI Router Control | deadsound | 493 | free | n/s | 2019.33840W | likely | AJA Kumo 32x32 SDI router control UI |
| 319 | 63284 folderToServer: website in vfs | snaut | 469 | free | n/s | n/s | likely | folderToServer: loads a website folder into the Virtual File System and serves it |
| 320 | 72852 Repository of Custom TouchDesigner Components | MaxMainio | 1100 | free | MIT | n/s | ? | Repository of Custom TD Components (MaxMainio): image-processing TOP tox collection with doc |
| 322* | 71010 UV Wall Extrusion tool | harveymoon | 395 | free | n/s | 2023.12003.42W | likely | UV Wall Extrusion: SOP to wall technique |
| 323* | 73039 SORA2 INSIDE TOUCHDESIGNER | Infratonal | 778 | free+ | n/s | 2023.12370W | yes | Sora2 inside TD: OpenAI video API (txt2vid, img2vid) AIMod + prototyping UI |
| 324* | 74343 Repository of Custom Signed Distance Field (SD | MaxMainio | 253 | free | MIT | n/s | ? | Repository of SDF operators (MaxMainio) |
| 325* | 74725 Web is OP | Unveil_studio | 205 | free | n/s | n/s | ? | Web is OP: p5.js, ml5 hand tracking, transformers.js depth, tf.js pose, MediaPipe inside TD  |
| 326 | 65097 MultiPlayalizer - Multitrack audio player and  | incognite | 855 | free | n/s | 2021.14360W | likely | MultiPlayalizer: loads a folder of stems, plays in sync, outputs analysis channels |
| 327 | 74754 Perceptual Display Engine - [Open-Source Proje | uisato | 437 | Patreon | n/s | n/s | ? | Perceptual Display Engine: multi-source frame-accurate video player/switcher with black-fram |
| 328 | 64031 JDRenderEngine V1 | jjdeprisco | 500 | free+ | n/s | n/s | ? | JDRenderEngine V1 (earlier version of 65250) |
| 329 | 66381 Speed Calculator | fredfred | 418 | free | n/s | n/s | ? | Speed Calculator: CHOP to speed value COMP |
| 330 | 66202 TMI color temperature tool | leclaire | 1054 | free | n/s | 2021.16410W | likely | TMI: color temperature + tint + intensity in GLSL (linear input) |
| 331 | 62622 Callback Manager | alphamoonbase | 447 | free | n/s | n/s | ? | Callback Manager: creates a docked callbackDAT for your own COMP |
| 332 | 70702 Unfold the Dragon | Unveil_studio | 484 | Patreon | n/s | n/s | ? | Unfold the Dragon: Dragon curve as TOP point cloud and SOP 3D |
| 333 | 71256 3D Audio Generator (for headphones) | HYPER_TETRA_HEDRON | 497 | free | n/s | 2023.12000W | likely | 3D Audio Generator: headphone orbit via interaural time delay + level |
| 334 | 67175 Simple Preset System | Vasily | 3437 | free | n/s | 2022.29530W | likely | Simple Preset System: two drag-drop COMPs storing presets for any COMP, with scripts per pre |
| 335 | 65011 AnimBox - Simple Cue System for the AnimationC | JiveFaury | 545 | free | n/s | n/s | ? | AnimBox: 8-cue system for Animation COMP (Vezer-like) |
| 336 | 63075 DMX(Art-Net) Fader | Takashi_MP | 876 | free | n/s | 2020.23680W | likely | DMX (Art-Net) Fader: test console for sending Art-Net without hardware |
| 337 | 66084 Feedback loop with framerate control | Kephalos | 868 | free | n/s | 2021.16410W | yes | Feedback loop with framerate control: slow feedback to watch changes between frames |
| 338 | 63285 REATOUCH OSC | Unveil_studio | 633 | free | n/s | 2020.23680W | likely | REATOUCH OSC: bidirectional OSC UI for REAPER tracks |
| 339 | 66408 Artio | dylanroscover | 1265 | free | n/s | n/s | ? | Artio: dynamic pixel-map generator for multi-display / LED setups (replicator of display geo |
| 340 | 68940 Optical flow warp on video input and Blender s | aulerius | 2684 | free | n/s | 2023.11340W | likely | Optical flow warp loops on video / Blender renders (Deforum-like) |
| 346 | 63473 Stream Fileserver | alphamoonbase | 550 | free | n/s | n/s | ? | Stream Fileserver: chunked HTTP file server component |
| 347 | 62625 uv unwrapping a box inside TouchDesigner | jacqueshoepffner | 539 | free | n/s | 2019.20140W | likely | UV unwrap a six-sided box for 3D mapping / camSchnappr calibration |
| 348 | 75106 SonomikaTD - TouchDesigner VJ System | Voltaine | 407 | free+ | n/s | n/s | ? | SonomikaTD: free VJ system (32 scenes, drag video/tox onto column grid, MIDI/OSC, audio-reac |
| 349 | 69276 Wallin Pattern Generator | Mallin | 1830 | free | n/s | 2023.11340W | likely | Wallin Pattern Generator: interactive test patterns for LED walls up to 26K x 5K, PNG export |
| 350 | 66089 Step Sequencer | igierard | 1543 | free | n/s | 2021.15800W | likely | Step Sequencer tied to TimerCOMP tempo/time signature |
| 351 | 65034 keyFrameitor | NachoArias | 584 | free | n/s | 2021.14360W | likely | keyFrameitor: drop marks on timeline to drive Animation COMP keyframes |
| 352 | 61059 multislider tool with touchOSC template | jacqueshoepffner | 775 | free | n/s | 2019.19160W | likely | multiSlider tool with TouchOSC template (labelled sliders, limits, presets) |
| 353 | 68815 PosiStageNet Sender Chop | Tyrell | 772 | free | n/s | n/s | ? | PosiStageNet sender CHOP (PSN, open stage position protocol used with grandMA / Photon) |
| 354 | 62997 TD-SearchPalette | yeataro | 762 | free | MIT | 2020.27390W | likely | TD-SearchPalette: search the Palette with wildcards, live mode |
| 355 | 63146 FRUIT QUIZ - how to simple python | xnimax | 573 | free | n/s | 2020.24520W | likely | FRUIT QUIZ: python-logic game demo (Italian), 1024 res |
| 356 | 71004 TLGIZMO - TRANSFORM+ | THETOUCHLAB | 499 | free | n/s | 2023.12000M | yes | TLGIZMO: keyboard-driven transform gizmo for COMP/geo |
| 357 | 69236 Mediapipe AI + Nvidea Flex Solver ┃  Interract | Skywalker.Visuals | 2700 | free | MIT for Mediapipe plugin; project not stated | 2023.11340W | WIN | Mediapipe hand tracking driving NVIDIA Flex particles |
| 358 | 62899 Easing Functions with GLSL | forkni | 602 | free | n/s | 2020.23680W | likely | Easing Functions with GLSL (forkni) |
| 359 | 64889 Timelapse de-flicker .tox | prema | 572 | free | n/s | 2020.27390W | likely | Timelapse de-flicker: smooths exposure bumps |
| 360 | 63954 RayTK Version 0.12 | tekt | 517 | free | MIT | n/s | ? | RayTK v0.12 release notes |
| 361* | 70707 Procedural Hilbert patterns | Unveil_studio | 530 | Patreon | n/s | n/s | ? | Procedural Hilbert patterns (Unveil_studio): Hilbert curve generation in TD |
| 366 | 62857 kbui | ianl | 520 | free | n/s | n/s | ? | kbui: keyboard-navigation of nested dict data (experimental) |
| 367 | 69078 TOX WITH MIDI LEARN FUNCTION FOR MIDI CONTROLL | duarte | 1397 | free | n/s | n/s | likely | MIDI-learn controller tox |
| 368 | 68568 RANDoFRAMo | anodin | 715 | free | n/s | 2022.32660W | likely | RANDoFRAMo: map video onto randomly placed LEDs, exports 32-bit EXR per universe |
| 369 | 73899 Auto BPM Sync with AI | shum | 559 | free | n/s | n/s | yes | Auto BPM Sync: TCN model detects BPM and sets project tempo |
| 370 | 73268 TDMorph | Darien.Brito | 780 | free+ | MIT | n/s | ? | TDMorph: preset/morph/scene/cue toolkit; free PresetManager, paid ParameterMorpher + SceneLa |
| 371 | 65487 RayTK v0.19: Heads, Beziers, Polyhedra, Oh My! | tekt | 518 | free | MIT | n/s | ? | RayTK v0.19: 3D bezier, head SDF, polyhedron |
| 372 | 65064 QFH HapQ Converter ( ~300-1000+ FPS ) | lucasm | 744 | free+ | n/s | n/s | likely | QFH HapQ Converter: batch transcode to HapQ at 300-1000 fps by disabling realtime |
| 373 | 66582 TD Launcher V1 (Automatic Build Detection) | lucasm | 1114 | free | MIT | n/s | yes | TD Launcher: opens each .toe with the right TD build, downloads/installs builds |
| 374 | 63283 Backdropper | alphamoonbase | 625 | free | n/s | n/s | ? | Backdropper: create network backdrop boxes |
| 375 | 68351 I make a tox for TouchDesigner to SuperDirt Di | toyoshi | 412 | free | n/s | n/s | ? | tox to talk to SuperDirt (TidalCycles) via OSC |
| 376 | 62542 PatternGenerator | django | 543 | free | n/s | 2018.25000W | likely | PatternGenerator: projection-mapping test patterns |
| 377 | 65782 RTX webcam background changer | slysf | 719 | free | n/s | 2021.39010W | WIN | RTX webcam background changer |
| 378 | 70617 TLRADIO - THE TOUCHDESIGNER RADIO | THETOUCHLAB | 460 | free | n/s | 2023.11760M | yes | TLRADIO: internet radio player (radio-browser API) |
| 379 | 63055 Qtter beta 0.1 | Simplo | 619 | free | n/s | n/s | ? | Qtter: cuts rectangles from scanned paper sheet into avatar TOPs (QR via pyzbar) |
| 380 | 63821 Autogenerated Subtitles | xnimax | 659 | free | n/s | 2020.27390W | likely | Autogenerated Subtitles: shows last created node / par change as subtitles for teaching |
| 386 | 71267 Run Deepseek-r1 Locally : Free Component | ButchBangher | 433 | Patreon | n/s | n/s | ? | Run DeepSeek-R1 locally inside TD |
| 387 | 61061 box on steroids: custom fillet .tox | paketa12 | 745 | free | n/s | 2019.30550W | likely | Box with fillet SOP tox |
| 388 | 62595 D'n'D Callbacks | alphamoonbase | 542 | free | n/s | 2020.20020W | likely | Drag-and-Drop Callbacks component (files/ops) for Panel COMPs |
| 389 | 74215 Voronoi POP | Alaghast | 685 | free | MIT | n/s | yes (nee | Voronoi POP: C++ POP plugin generating 2D Voronoi from point input |
| 390 | 72758 NANO BANANA INSIDE TOUCHDESIGNER : When two ba | Infratonal | 2026 | free+ | n/s | 2023.12370W | yes | Nano Banana inside TD: Gemini image model txt2img / img2img AIMod + prototyping UI |
| 391 | 68174 iDraw OSC | fredfred | 1349 | free | n/s | n/s | yes | iDraw OSC: iOS app sending drawing as OSC |
| 392 | 62983 imgBBUploader moves TOPs to imgBB | snaut | 935 | free | n/s | n/s | ? | imgBB uploader: upload a TOP to imgBB (API key) |
| 393 | 65805 Easy Easing Between Camera Positions - CamSequ | function.store | 3159 | paid | n/s | n/s | ? | CamSequencer: camera preset recall with easing |
| 394 | 72258 TLLINK - BRIDGE YOUR CONTROLLERS | THETOUCHLAB | 566 | free | n/s | 2023.11760M | yes | TLLINK: bridge Bluetooth/remote/web controls via VLC state to TD |
| 395 | 61055 Geometry Interpolator Shader | Darien.Brito | 888 | free | n/s | 2019.17550W | likely | Geometry Interpolator Shader (from paketa12 tutorial) |
| 396 | 73603 Colorpicker v1.5.4 update | Artechs | 613 | free | n/s | n/s | ? | Colorpicker v1.5.4 (Artechs) |
| 397 | 61095 Install-TD-Experimental-win | yeataro | 671 | free | n/s | n/s | WIN | TD-Install-Experimental .bat for parallel builds |
| 398 | 62788 Infinite Mouse Scroll Component | lucasm | 705 | free | n/s | 2020.22080W | WIN | Infinite mouse scroll component (value-ladder style) |
| 399 | 71196 Trippy Visual Pack | Compilervisuals | 1393 | free | n/s | 2023.11600W | likely | Trippy Visual Pack: 6 tox visuals + a full VJ project with kantanMapper (Projecter, JSON map |
| 400 | 63953 Twitter Filtered Stream (API v2) | jean-louis | 696 | free+ | n/s | 2021.10330W | likely | Twitter filtered stream API v2 |
## Deep notes, first 15 teasers (listing page 14, ranks 286-300; the page-14 promoted block 68631/71417/72379/73164/73301 is described after the list)
1. **65250 JDRenderEngine** (jjdeprisco, Sep 2021, V3): problem = fast "scene + render" workflow instead of iMovie/Premiere; a patch-based render/scene manager built Jan-Aug 2021 (V1 64031 Mar 2021, V2 Jul, V3 Aug). Page has no attachment; the download is a GitHub link. Free, tip jar (buymeacoffee). No licence, Mac unknown. Not fetched.
2. **66736 Pixel Wrangle** (miu-lab, RC2 2023-03, repo last commit 2024-01-25 `9e2bcf6`): GLSL TOP wrapped by a Python extension that parses `uniform` declarations into custom pars, offers Compute vs Vertex/Pixel macros, preset + function libraries, Lygia import, raymarch/noise helpers, instance manager panel and one-click export to a plain GLSL network. Install: `git clone --recurse-submodules` into `Documents/Derivative/Palette` or setup.sh (Git Bash). Needs TD 2022.29530+ and Git; tested on Windows/RTX only. GPL-3.0, free. Strongest "shader authoring" asset in slice.
3. **74073 PCSD V.2 (POP)** (Milkorva, Mar 2026): point-cloud surface deformer using POPs (deform field, splat size, proximity/line looks, AutoCam). Single toe (322 ops, 696 pars, 1.8k Python lines), saved 2025.30280 so POPs present in 31550. Free; author funds via Patreon. No licence.
4. **73817 TLWEB** (THETOUCHLAB, Jan 2026): drive any web page from gestures/sound/sensors with macro sequences and multi-cursor, via Web Browser COMP + JS. 1.3k ops, saved on macOS 2025.32050 (Mac fine). Free, README + Game Boy skin mod. Audit: urllib, eval/compile in callbacks.
5. **73917 TD-ML v0.2** (bi.os, Feb 2026): MLP/LSTM classifier and regressor, VAE, UMAP/Isomap/PCA/KMeans and a Datasetter as CHOP components on scikit-learn + PyTorch + skorch + umap-learn (Wekinator/FluCoMa style). Needs a Python env with torch/sklearn (CUDA optional); Beta. Free; Discord/GitHub. Most useful AI-ish tool in slice for control mapping.
6. **65200 renderSBS** (Simplo, Sep 2021): alpha tox for side-by-side / top-bottom 3D from any render. No attachment on page. Low value.
7. **62063 Schedule Keeper** (neonlimbo, 2019): table-scheduled state scripts re-fired every minute so a rebooted machine re-enters the right state (projector on/off/shutter). Clock CHOP + Chop Execute; getState.text mentions pip DateTime/pytz. 2 KB tox, build 2019.10700. Pattern worth copying for installations.
8. **64951 miniSEQ** (incognite, 2021): trigger/value step sequencer, project BPM default, `sequencer` base can be copied out as a static lite version. 385 ops, build 2021.13610. Same author: MultiPlayalizer 65097.
9. **63890 Easing Functions CHOP** (Dorian, 2021): 30 named curves (Quad..Bounce) as a CHOP, sample count par. 3 KB, pure Python.
10. **62405 Sensel Morph raw CHOP** (mouren, 2020): C++ Custom CHOP for Sensel Morph contacts; needs VS2019 + Sensel lib; repo GPL-3.0 (cloned `9207487`, includes `SenselTests`, `Source`). Windows/hardware only.
11. **62978 Storage Viewer** (alphamoonbase, 2020): tree view of a COMP's `storage` (ReadDict/ReadJson); Lister-based, 4.5k Python lines. Author has 6 helper components here (Output Controller, Callback Manager, D'n'D Callbacks, Backdropper, Stream Fileserver).
12. **73421 Minor UI Fixes on Wine** (c0deous, Nov 2025): Execute DAT sets `dispmode` of 23 text TOPs under `/ui/dialogs` at startup; Linux/Wine only. Interesting only as proof that `/ui/dialogs` is re-created at each load.
13. **63686 BS 902** (Kephalos, 2020): joke video-switcher UI (8 in, PGM/PVW, logo store) built from panel COMPs; 106 custom pars (widget library). Same author: slowfeedback 66084.
14. **66906 TD scripts v1.2** (Artechs, Nov 2022): Blender add-on exporting geometry/UV/materials/animated camera (as CHOP) to TD; free v1.2, later free LITE + Patreon PRO. No file on page. Same author: Colorpicker 73603.
15. **63797 Blister COMP** (greg, 2021): parameter UI to define Lister COMP columns/callbacks (10 data modes, expression columns, rollover help), 299 ops/684 pars, build 2021.11180. Builds on Matthew Ragan + Ivan DelSol's Big Bad Lister.

Page-14 promoted block: **68631 PROMOTE** (Unveil_studio, Nov 2023; 2.7 KB tox saved 2022.35320, Script CHOP writes one cell; shortcut-driven custom-parameter creation; known bugs listed); **71417 PiNODEs Beta v0.69** (pitheorem, Mar 2025; GPL-3.0 repo `2d2ca74`; 980 KB tox with 10.6k ops/91k Python lines, GLSL "point nodes" for parametric drawing in TOPs, Notion docs; part of PiKit with PiCompositor); **72379 Audioreactive Video Playhead Definitive** (uisato, Jul 2025; Patreon; adds Veo/Gemini API tox + MIDI/Ableton control); **73164 TD Copier Tool** (GRNCH, Oct 2025; ParameterCopier + OperatorCopier, self-contained, licence "None"); **73301 Morphological Operators** (MaxMainio, Nov 2025; MIT repo, GLSL TOP components).

## Other finds worth the MCP's attention (beyond rank 15)
- **UI/dev workflow:** 68631 PROMOTE (shortcut to promote a par), 73164 TD Copier (par + op copy), 62997 SearchPalette (MIT, wildcard palette search), 66582 TD Launcher (MIT; has Mac build script), 67175 Simple Preset System, 73268 TDMorph (MIT core; ParameterMorpher/SceneLauncher paid), 69078 MIDI-learn tox, 63797 Blister.
- **Shaders/post:** 67726 13-tap Bloom (MIT), 66202 TMI colour temperature, 62899/63890 easing, 67470 Poisson Fill, 73359 Post Process Volume, 72852/73301/74343 MaxMainio repo (MIT, 18 MB).
- **LED/mapping/projection:** 69276 Wallin Pattern Generator, 68568 RANDoFRAMo (32-bit EXR per universe), 66408 Artio pixel maps, 62542 PatternGenerator, 62625 UV box unwrap, 71196 Trippy pack (contains kantanMapper), 68815 PosiStageNet sender.
- **AI via API:** 72758 Nano Banana (Gemini), 73039 Sora 2 (OpenAI; org verification, 720p, 4/8/12 s, "expensive"), 72379 Veo tox (Patreon), 71267 DeepSeek-R1 local (Patreon), 73899 BPM TCN (torch mps/cpu/cuda), 73273 StreamDiffusion via Daydream.
- **VJ/show:** 75106 SonomikaTD (free, 32 scenes, Jul 2026), 71196 Trippy pack, 74754 Perceptual Display Engine, 73817 TLWEB.
- **Needs newer TD than 31550:** 74215 Voronoi POP (C++ plugin, `.plugin` macOS, MIT) requires **2025.33070+**; 72698 RayTK 0.46 targets "2025 experimental".

## Files downloaded, audit (`toeexpand` on copies in `files/<id>/expanded_03/`, nothing loaded in TD)
79 derivative attachments (.tox/.toe/.zip; ~15.9 MB total, 9 of them already fetched by other agents) + 11 git clones depth 1 (~87 MB incl. .git; TD_Launcher py.zip and Windows toeexpand DLLs deleted, 66582). Clone commits: myTimer `ccdd961` (61048), SenselMorphTDRaw `9207487` (62405), TD-SearchPalette `f3097a6` (62997, MIT), PiCompositor `5fceda0` (67533), TD-13TapBloom `06cd1cf` (67726, MIT), TD_Launcher `093ad26` (66582, MIT), Pixel-Wrangle `9e2bcf6` (66736, GPL-3), TDMorph `55578f0` (73268, MIT), duarte-amorim/Touchdesigner `9744629` (69078), MaxMainio/TD_ `9689834` (72852, MIT), mediapipe-touchdesigner `bb01606` (69236, MIT). Full per-file op counts, custom-par names, Python line counts and flags are in the JSONL `audit` field.
Build of saved files: mostly 2019-2023 Windows saves; macOS-saved: 67779, 69505, 70225, 70617, 71004, 72258, 73817. Newest save: 73421 (2025.31550) and 73817 (2025.32050).
**Audit flags (scripts that run on load or touch system/network):**
- Autorun `onStart/onCreate/onProjectPreSave` Execute DATs (benign init): 61043, 62978, 62997, 63146, 63797, 66089, 67175, 67533, 68568, 71196, 72758, 73039, 73421, 73817, 74073.
- **Processes:** 69236 Flex project `build_release/execute1.text` runs `yarn install` with `shell=True`, `shutil.rmtree`, `project.load/save`, `os.environ` (do not run); 72258 TLLINK `killall -9 VLC` and `lsof -t -i:6666 | xargs kill -9`; 69981 `netsh wlan` (Windows). 62595 `webbrowser.open` (help link).
- **Network/mail:** 70225 `smtplib.SMTP_SSL` login with password from a custom par; 62130 Kumo `requests/urllib` to router IP; 63953 Web Client DATs (Twitter API); 70617 `requests` to api.radio-browser.info + file writes; 73817 `urllib`; 72758/73039 API calls (Gemini/OpenAI) with keys via env/.env, file writes, pip instructions; 69505 `urllib` to camera.
- **File I/O:** 67175 `os.makedirs` presets; 71196 Projecter opens JSON via `ui.chooseFile`; 68631 only writes a Script CHOP cell (benign).
- **Dynamic code:** `eval` appears in almost every parexec (standard widget/extension template, not remote code); 73817 `compile` in a DAT Execute; 65034/67175/68568/70617 `exec` in SubWidgetExt (widget library). No obfuscated payloads, no base64/pickle/marshal anywhere in 79 files.
- No file contained binary executables; no `.dll/.plugin` downloaded.

## Recurring authors (this slice)
THETOUCHLAB x6 (TLWEB, TLGIZMO, TLLINK, TLRADIO, TDMAIL, Sony FX9; all macOS-saved, free, no licence); alphamoonbase x6 (2019-2020 helper components); Unveil_studio x5 (PROMOTE, REATOUCH, Unfold the Dragon, Hilbert, Web is OP; Patreon); lucasm/EnviralDesign x4 (13-tap Bloom, TD Launcher, HapQ converter, infinite scroll; MIT repos); MaxMainio x3 (MIT repo + docs site); tekt x3 (RayTK 0.12/0.19/0.46); fredfred x3; jacqueshoepffner x3 (myTimer, multislider, UV box); pitheorem x2 (PiNODEs + PiCompositor, GPL-3.0 PiKit); uisato x2 (Patreon); jjdeprisco x2 (JDRenderEngine).

## Windows-only / NVIDIA-only / needs newer build
WIN: 69981 (netsh), 61095 (.bat), 62788 (ctypes cursor), 62405 (VS2019 + Sensel hardware), 65782 (RTX background removal), 73421 (Wine/Linux), 69236 (NVIDIA Flex). Newer than 31550: 74215 (2025.33070+). Unverified on Mac: all older Windows-saved pure-TD tools (treat as "likely").

## Skipped / not fetched
No leak/crack content in this slice. Not downloaded: Patreon files (70702, 70707, 72379, 71267, 74754, 75106 free post, 65805 paid, 73268 paid modules), App Store apps (72196, 68174), plugin binaries (74215, 62405), GitHub-only posts without clone (65250 JDRenderEngine, 63954/65487 RayTK old releases, 65168 TOPs-stacker, 72698 RayTK 0.46 repo), images in 67726, 62788 gif, 73817 README txt. Posts with empty Asset Downloads and no repo: 65200, 62622, 63283, 63473, 63284, 64031, 65011, 66381, 66906, 68351, 68778, 69724, 73603.

## Open questions
- What counter drives the site's "Most viewed" sort (reads shown do not follow it)? Pages 0-13 and 20-32 are other slices.
- Does RayTK 0.46 or Pixel Wrangle run on 2025.31550 macOS (Vulkan)? Needs a live test later (with the user's go-ahead, never from this research).
