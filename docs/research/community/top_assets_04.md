# derivative.ca most-viewed ASSETS, listing pages 20-26 (slice top_assets_04)

Crawled 26 Oct 2026 by one Sonnet agent. Listing `https://derivative.ca/community?sort_by=views&type[]=24&page=20..26`.
Data: `research_src/community/top_assets_04.jsonl` (119 posts, one JSON line each, with `views_rank`, `views`, `reads`, `comments`, `price`, `audit`).
Downloads under `research_src/community/files/<postid>/` (tox/toe/zips) with `expanded/<name>/` = `toeexpand` output; nothing was loaded into TD.

## How to read this listing (important)
- Each page shows **20 cards = 5 "featured" cards + 15 ranked cards**. The 5 featured cards rotate from a pool of 14 promoted assets and
  repeat on every page (7 pages x 5 = 35 slots, only 14 distinct posts). So 140 cards = **119 distinct assets: 105 organically ranked + 14 featured-only**.
- Rank column below = organic rank (page x 15 + index; pages 20-26 = ranks 301-405); the brief's formula `page*20+index+1` is in brackets and is stored as `views_rank`
  (`views_rank_organic` = the first number). Featured-only assets have `views_rank_organic = null`, `featured_slot = true`.
- Views shown on each post (lifetime counter, 156 to 4943) do **not** fall in step with the sort order (e.g. rank 337 has 2.1k, rank 303 has 744), so the sort key is evidently not that counter. Comments are 0 everywhere (comments live on the forum).
- "Mac" = evidence level: `yes` author says Mac/tox saved on macOS; `likely` pure TD network or GLSL with no plugin/OS calls found (NOT tested here);
  `unknown`; `windows-only`; `nvidia-only`. All 119 posts are type Asset. Builds in the table = TD build the tox was last saved in (W = Windows, M = macOS), or the stated minimum.

## Ranked table (organic ranks 301-405)
| rank (listing) | title | author | views | free? | licence | build | Mac | what it is |
|---|---|---|---|---|---|---|---|---|
| 301 (406) | TDYolo | patrick_hartono | 1129 | free | MIT | 2023.12000+ | yes | YOLOv11 object detection in TD, no Python env (headless browser + ONNX) |
| 302 (407) | [Release] Versatile VJ System with 5-Layer Con | Black-Pomeranian | 1220 | free | not stated | 2025.32050 W | likely | VJ system: 5 layers, custom control UI, APC mini mk2 map, Sound2Light OSC |
| 303 (408) | Colour Scheme | wizartist | 744 | free | not stated | 2019.18300 W | likely | Colour scheme generator: base colour -> 7 schemes |
| 304 (409) | TLKEYOPS - SPEED UP YOUR WORKFLOW | THETOUCHLAB | 523 | free | not stated | 2023.12000 M | likely | TLKEYOPS: hotkey instant creation of favourite operators (workflow) |
| 305 (410) | Twitch Chat | alphamoonbase | 614 | free | not stated | - | likely | Twitch chat IRC component (based on Elburz) |
| 306 (411) | Sourcerer | matthewwachter | 685 | free | MIT | 2025.32280 (repo) | yes | Sourcerer: media bin / source switcher with transitions, follow actions, prese |
| 307 (412) | Reorient style normal map combiner COMP | lucasm | 719 | free | not stated | 2020.23680 W | likely | Reorient-style normal-map combiner COMP (correct blending of normals) |
| 308 (413) | TLCHAT - CHAT/SHARE/CONTROL | THETOUCHLAB | 457 | free | not stated | 2023.12000 M | yes | TLCHAT: chat, image share and live-value exchange between TD users |
| 309 (414) | File Collector Tox | mouren | 936 | free | GPL-3.0 | 2020.20625 W | likely | File Collector: gather all referenced files into project folder, repoint pars |
| 310 (415) | FAUST (Audio Processing) for TouchDesigner | DavidBraun | 874 | free | GPL-2.0+ | 2023.11290+ | yes | TD-Faust: FAUST DSP code compiled JIT inside TD (audio synth/FX, MIDI) |
| 311 (416) | FullDome PENUMBRA | videoso | 919 | free | not stated | 2019.15230 W | likely | Fulldome previz project (Carlos Serrano session) for dome work |
| 312 (417) | Delaunay Triangulation SOP Node | Tyrell | 1137 | free | MIT (repo) | - | windows-only | Delaunay triangulation SOP (2D points), C++ custom SOP |
| 313 (418) | Midi_learn COMP | Unveil_studio | 552 | free | not stated | - | likely | MIDI learn COMP: map controller to selected COMP custom/built-in pars |
| 314 (419) | Feedback 3D | incognite | 763 | free | not stated | 2020.28110 W | likely | Feedback 3D: depth-aware feedback TOP effect |
| 315 (420) | Attraktor Creator v0.1 | JiveFaury | 968 | free | not stated | 2021.16410 W | yes | Attraktors Creator (lite): strange attractor particle system, pos/vel textures |
| 316 (426) | Browser Interface component | Deltacut | 850 | free | not stated | - | likely | Browser Interface: auto-generates HTML control UI for a project (multi-client) |
| 317 (427) | DistThresholdChop | vinz99 | 791 | free | not stated | - | windows-only | DistThresholdCHOP: find point pairs closer than distance (C++ CHOP) |
| 318 (428) | Convex Hull SOP node | Tyrell | 790 | free | MIT (repo) | - | windows-only | Convex hull SOP (C++ custom SOP) |
| 319 (429) | Unreal Sequencer Sync | L05 | 961 | free | MIT | 2021.16270 W | likely | Unreal Sequencer Sync: UE editor sequencer frame -> TD time COMP over OSC |
| 320 (430) | Flashlight Evolution Text in 3D | xnimax | 715 | free | not stated | 2020.22080 W | likely | Light-paint text in 3D: track a flashlight Z with mono camera |
| 321 (431) | Color Picker/Screen Shot Grabber for Windows | mouren | 779 | free | GPL-3.0 | 2019.20140 W | windows-only | Colour picker + screen grabber across desktops |
| 322 (432) | Color Harmony - Beta | Kephalos | 893 | free | not stated | 2020.20625 W | likely | Colour harmony generator (complementary, triad, analogous...) like Adobe Color |
| 323 (433) | Apple Vision Suite TOP | Alaghast | 716 | Patreon | proprietary (Patreon/K | 2025+ (macOS arm64) | yes | Apple Vision Suite: 4 C++ TOPs (mask, optical flow, super-res, depth) for macO |
| 324 (434) | gateCHOPComp - Max/Msp gate emulator | robcass | 1260 | free | not stated | 2020.22080 W | likely | gateCHOPComp: Max/MSP-style gate (pass value to one of N outputs) |
| 325 (435) | TLSNAKE - PLAY THE UI | THETOUCHLAB | 644 | free | not stated | 2023.11760 M | likely | TLSNAKE: Snake game played in TD UI |
| 326 (436) | iXR OSC & NDI(visionOS) - Free Download until  | fredfred | 617 | free app | GitHub repo | - | yes | iXR OSC & NDI: visionOS app receives NDI 360 video, sends hand OSC |
| 327 (437) | Par.Help Translator | yeataro | 895 | free | MIT | 2021.16960 W | likely | Par.Help Translator: translate parameter help/OP summaries/DAT text on hover |
| 328 (438) | Native Background Removal on MacOS | aaronmylespereira | 881 | free | MIT | (macOS arm64) C++ TOP | yes | Native background removal on macOS via Apple Vision person segmentation (C++ T |
| 329 (439) | Distance Calculator | fredfred | 1247 | free | not stated | - | likely | Distance calculator COMP between two xyz points |
| 330 (440) | OSCToolset v2.0 - Simplifying the communicatio | Eusebi | 749 | paid/Gumroad | proprietary | - | unknown | OSCToolset v2: Unreal Engine 5 plugin simplifying OSC from TD |
| 331 (446) | Depth map viewer for 2D to 3D assets | SilentChaos | 1991 | free | not stated | 2022.28040 W | likely | Depth-map viewer/exporter: image + height map -> displaced frames for photogra |
| 332 (447) | Motion Tracer Effect Tool | dcheesman | 665 | Patreon | not stated | - | unknown | Motion tracer effect (trails) tool |
| 333 (448) | Tube Hands - Leap Motion Basic Bones | harveymoon | 1057 | free | not stated | 2020.22080 W | likely | Leap Motion basic hand bones geometry |
| 334 (449) | Simple wave simulation | gormonboza | 754 | free | not stated | 2020.22080 W | likely | Simple wave simulation (feedback TOPs) |
| 335 (450) | Spray Can | Simplo | 1210 | free | not stated | - | unknown | Spray Can: hand-tracked spray painting game (Interactive & Immersive HQ round  |
| 336 (451) | Pure CHOP Matrix Transform Module ( px,py,pz : | lucasm | 740 | free | not stated | 2019.36500 W | likely | Pure-CHOP matrix transform (px,py,pz + t/r/s per sample) |
| 337 (452) | Bridgets | emintzer | 1095 | free | LGPL-3.0 | 2019.20140 W | likely | Bridgets: learn/forget mapping of 13 input devices to widgets |
| 338 (453) | Camera Fly Through | anodin | 1586 | free | not stated | 2019.17550 W | likely | Camera fly-through controlled like a drone |
| 339 (454) | Stage Window | TimFranklin | 769 | free | GPL-3.0 | 2019.20250 W | likely | Stage Window: media-server-style layout canvas; outputs are ortho cameras |
| 340 (455) | TouchDesigner X Computer Music (v0.2.0) - Addi | fredfred | 609 | free | GitHub repo | 2023.12000 M | likely | Additive synthesizer (TouchDesigner x Computer Music) |
| 341 (456) | TouchOut - Control Your Computer | THETOUCHLAB | 739 | free | not stated | 2023.11760 M | yes | TouchOut: simulate mouse clicks in other macOS apps from TD |
| 342 (457) | SENSING VOLUMES-Interactive multi sensory art  | SENSING_VOLUMES | 737 | n/a | n/a | - | unknown | Sensing Volumes installation case study (cameras -> light and sound) |
| 343 (458) | GPU Bloom | Unveil_studio | 928 | free | Shadertoy source (unsp | - | likely | Multi-pass GPU bloom from Shadertoy XtKfRV (8 iterations) |
| 344 (459) | Speedy Shaker - Muti-layer compositing tool wi | _shandor | 776 | free | GPL-3.0 | 2020.41040 W | likely | Speedy Shaker: 8-layer compositing with masks, blend modes, colour correction  |
| 345 (460) | RayTK Version 0.11 and documentation website | tekt | 729 | free | CC-BY-4.0 | 2021.10330 | likely | RayTK 0.11 + docs website (older release) |
| 346 (466) | TLPAD - TOUCH MONITOR | THETOUCHLAB | 626 | free | not stated | 2023.12230 M | yes | TLPAD: read all Mac trackpad / Magic Mouse finger touches into TD |
| 347 (467) | TouchDesigner user interface localization. | yeataro | 929 | free | MIT | 2019.16600 W | likely | Translate TD main menu and OP Create dialog to 12 languages |
| 348 (468) | Random CHOP | function.store | 1875 | free | not stated | 2022.32660 W | likely | Random CHOP with unique/no-repeat generation |
| 349 (469) | Projector Coverage Tool | asterix | 620 | paid/Gumroad | proprietary | - | unknown | Projector coverage tool: throw, lumens, distance, shadows, frustum, depth cam  |
| 350 (470) | UI Theme 1.0 | Eusebi | 897 | paid/Gumroad | proprietary | - | likely | UI Theme: bulk-style TD basic widgets with presets |
| 351 (471) | VideoBin | vento303 | 1170 | free | not stated | 2021.13610 W | likely | VideoBin: VDMX-style media bin with tree lister and previews |
| 352 (472) | Generative color palettes | exsstas | 1398 | free | not stated | 2020.25380 W | likely | Generative colour palettes (Inigo Quilez cosine palettes) for GLSL/MAT |
| 353 (473) | New music video for Voltaine | Voltaine | 810 | n/a | n/a | - | n/a | Music video made with TD (Voltaine) |
| 354 (474) | File Downloader | alphamoonbase | 1530 | free | not stated | - | likely | File Downloader COMP with queue and callbacks |
| 355 (475) | Image Dithering Algorithms | Skywalker.Visuals | 2132 | free | not stated | 2023.11340 W | likely | Six image dithering algorithms (Floyd-Steinberg, Atkinson, Bayer...) |
| 356 (476) | Right Side Up - ArcBall COMP | lucasm | 998 | free | not stated | 2019.20140 W | likely | Arcball camera COMP (Maya/Blender style, no roll) |
| 357 (477) | Realtime Audioreactive Time Remap - [Free Touc | uisato | 1700 | Patreon | not stated | - | unknown | Audio-reactive time remap (Twixtor-like) via Flowframes |
| 358 (478) | Curve Editor | why | 1162 | free | not stated | 2019.19930 W | likely | Curve editor usable in perform mode, outputs CHOP channel |
| 359 (479) | TLMOTION - STOPMOTION CREATOR | THETOUCHLAB | 811 | free | not stated | 2023.11760 M | yes | TLMOTION stop-motion capture/export app |
| 360 (480) | PHOTOGRAMMETRY Workshop - 3D Scans & TOE File | b2bk | 1039 | free | not stated | - | likely | Photogrammetry workshop files (xyz scans + toe) |
| 361 (486) | SpotifyBridge - Real-time Spotify Lyrics in To | Lostfound | 685 | Patreon | not stated | - | likely | SpotifyBridge: live Spotify lyrics in TD |
| 362 (487) | Colorpicker UI widget: v1.3 | Artechs | 2695 | free | not stated | - | likely | Colour picker UI widget (Affinity-style) |
| 363 (488) | ARuco markers reader | ruigato | 1351 | free | not stated | 2022.20150 (Py3.9) | likely | ArUco marker reader using OpenCV in TD Python 3.9 |
| 364 (489) | bypassHandler COMP - Bypass operators with tog | robcass | 1773 | free | not stated | 2020.22080 W | likely | bypassHandler: toggle pars for bypassing found ops |
| 365 (490) | real-time colorGrading in TouchDesigner | jacqueshoepffner | 1537 | free | not stated | 2021.13610 W | likely | Real-time colour grading prototype (Resolve-style) |
| 366 (491) | Fancy Frustum - Advanced Frustum Visualization | _shandor | 1235 | free | not stated | - | likely | Fancy Frustum: camera/projector frustum visualisation + multi-camera sync |
| 367 (492) | RTK - Raymarching Toolkit | hrtlacek | 1265 | free | not stated | 2019.33020 W | likely | RTK raymarching toolkit (precursor of RayTK idea) |
| 368 (493) | UberGui V4 - A lightweight multi-threaded, Web | lucasm | 1285 | free | MIT | 2021.12380 | likely | UberGui V4: web-rendered, threaded UI layer over custom parameters |
| 369 (494) | zuweiser - more experiments for controller map | snaut | 1594 | free | not stated | - | likely | zuweiser: controller mapping through Bind CHOP |
| 370 (495) | Lygia for TouchDesginer | LeithBA | 1730 | free | MIT upstream | 2022.28040 W | likely | LYGIA for TD: #include resolver for the LYGIA GLSL library |
| 371 (496) | Cycles COMP - Loops, Timing, Shaping | greg | 1167 | free | not stated | 2021.15790 W | likely | Cycles COMP: tap tempo, BPM, ramps, time-warp, Ableton Link |
| 372 (497) | webGUI : a custom parameter to web GUI wrapper | lescurej | 1240 | free | not stated | 2020.26630 M | likely | webGUI: custom pars of containers wrapped in a web page over websocket |
| 373 (498) | Web Control Wizards | THETOUCHLAB | 870 | free | not stated | 2023.11760 M | yes | Web control wizards: simulate mouse clicks on webBrowser overlays |
| 374 (499) | PICMA : PICKER & MAPPER | anodin | 1050 | free | not stated | 2019.19930 W | likely | PICMA: picker and mapper for projection mapping (rect/triangle, bezier) |
| 375 (500) | sudoSignals Beta v2 | raganmd | 1122 | free | proprietary | - | yes | sudoSignals beta v2: installation monitoring/remote control platform |
| 376 (506) | MIDI Vu-Meter for Akai APC Mini | Deltacut | 1670 | free | not stated | - | likely | Audio -> VU meter on Akai APC mini (MIDI out) |
| 377 (507) | UI Theme - Presets update | Eusebi | 846 | see 67320 | proprietary | - | likely | UI Theme presets update (JSON presets, tag targeting) |
| 378 (508) | Twitcher - Twitchwatching for everyone | snaut | 1313 | free | see repo | - | likely | Twitcher: Twitch auth (Web Client, Web Server DAT) + API |
| 379 (509) | VoronoCubes Tox | gnomalab | 1088 | free | not stated | 2020.20625 M | likely | VoronoCubes (Paketa12 method) abstract graphics |
| 380 (510) | Waterfall effect with Nvidia Flow + Water Ripp | xnimax | 4090 | free | not stated | 2022.32120 W | nvidia-only | Waterfall using NVIDIA Flow + ripple shader + optical flow displace |
| 381 (511) | CHARACTERS ANIMATION | anodin | 934 | free | OFL fonts bundled | 2022.35320 W | likely | Character-by-character title animation COMP (intro/stay/outro, decode FX) |
| 382 (512) | Strobber Tox ┃ TOP Effector + Audio-reactive | Skywalker.Visuals | 1878 | free | not stated | 2023.11340 W | likely | Strobber: strobe/glitch TOP effectors with audio reaction (5 variants) |
| 383 (513) | Generative Isolation | andreihingan | 1067 | free | not stated | 2020.22080 W | likely | Generative Isolation community exquisite-corpse project |
| 384 (514) | TLMODS - CUSTOM TOOLS | THETOUCHLAB | 1202 | free | not stated | 2023.12370 M | yes | TLMODS: editor hotkey mods (show related ops, connect/cut wire, insert op, cop |
| 385 (515) | Sand & Steel | snaut | 1043 | free | not stated | 2020.21460 W | likely | Sand & Steel: feedback + displace offset-map technique |
| 386 (516) | Warpa: 2D Mesh Projection Mapping Tool | Ennui | 2053 | free | MIT | 2023.12230 | likely | Warpa: 2D mesh projection mapping/warp tool |
| 387 (517) | Alfred ROOM - The Ping Pong Wrestler | xnimax | 1404 | free | not stated | 2021.10330 W | windows-only | Alfred ROOM: Kinect V2 gesture particles, blend SOP puppet |
| 388 (518) | LTC Timecode Cue List | TimFranklin | 1111 | free | see repo | - | likely | LTC timecode generator + cue list builder |
| 389 (519) | Multi-level noise generator | tekt | 1466 | free | not stated | 2019.18580 W | likely | Multi-level noise TOP generator (4 noise gens, blend modes) |
| 390 (520) | FFT Ocean simulation | devart.space | 2560 | free | not stated | 2021.14360 W | likely | FFT ocean simulation (inverse FFT) for TD |
| 391 (526) | Complex UV Math toolkit | function.store | 1537 | paid/Gumroad | proprietary | - | likely | Complex-number UV math toolkit (ComplexOP, Mix, Iterator fractals) |
| 392 (527) | WaveTOP | timgerritsen | 4036 | free | not stated | 2022.32660 W | likely | WaveTOP: wave equation in TOPs only, heightmap for grid SOP |
| 393 (528) | graphPlot COMP - 2D Graph Plotter | greg | 1846 | free | not stated | 2021.13940 W | likely | graphPlot COMP: 2D plotting of CHOP/SOP/DAT data + audio spectrum |
| 394 (529) | Schedule CHOP | Ennui | 1444 | free | Unlicense | - | windows-only | Schedule CHOP: enable by system clock/day (C++) |
| 395 (530) | Introduction to POPs - Example files from Touc | ParseError | 2980 | free | not stated | 2025.30060 experimental | unknown | Intro to POPs: 3 example files (particles, proximity, trail + skin) |
| 396 (531) | Mirror/Glitch Lab's 'Topology 3D' in TouchDesi | function.store | 1000 | paid/Gumroad | proprietary | - | nvidia-only | Topology 3D (Mirror/Glitch Lab effect) as Geo COMP |
| 397 (532) | Galileo Mapper Family | alphamoonbase | 1768 | free | non-commercial free | 2019.19930 W | likely | Galileo mapper family: drag-par DMX / OSC / MIDI mappers with learn |
| 398 (533) | LIDAR COMPONENT: LIDARTRACKER v3.0 | Zink | 4943 | free | not stated | 2022+ | windows-only | LidarTracker v3.0: C++ CHOP for Hokuyo/Slamtec/EAI lidars, TUIO/UDP |
| 399 (534) | chainGpu Physics Simulation Tool | mickeyvanolst | 4202 | free | CC BY-NC-SA 4.0 | 2022.32660 (Win) | unknown | chainGpu: compute-shader chain physics (plants, hair, tentacles) |
| 400 (535) | Covid Tracker Map | soma-cg | 1053 | free | see repo | - | likely | Covid tracker map (JHU data) |
| 401 (536) | Swaggy Bokeh - Physical DOF for TD | _shandor | 2036 | free | not stated | 2020.20020 W | likely | Swaggy Bokeh: physical DOF post effect (GLSL) |
| 402 (537) | Delaunay Triangulation POP | Alaghast | 1080 | free | MIT | 2025 (POP plugin) | yes | Delaunay Triangulation POP (C++ POP plugin) |
| 403 (538) | OpenCV-Tracker | igalabs | 1401 | free | see repo | 2021.10330+ | likely | OpenCV tracker component (ROI tracking, several trackers) |
| 404 (539) | ATTRAKTORS DESIGNER v0.8 and v2022 (New Releas | JiveFaury | 2273 | Patreon | proprietary | 2021.16410 / 2022.2xxx | yes | Attraktors Designer v0.8 / v2022: design and play strange attractors |
| 405 (540) | PyTorchTOP | DavidBraun | 1181 | free | MIT | - | windows-only | PyTorchTOP: run PyTorch models in a TOP (C++/LibTorch) |

## Featured-only assets (14; shown 5 per page on every page)
| id | title | author | views | free? | licence | build | Mac | what it is |
|---|---|---|---|---|---|---|---|---|
| 68631 | PROMOTE | Unveil_studio | 412 | free | not stated | 2022.35320 W | likely | PROMOTE: make custom pars via keyboard shortcut |
| 69724 | Vintage Lens Effect Tool | dcheesman | 1311 | Patreon | not stated | - | unknown | Vintage lens look: chromatic aberration, blur, grain, RGB delay, vignette |
| 69981 | Wifi Network Manager | pdubost | 263 | free | not stated | 2021.16410 W | windows-only | Wifi Network Manager: scan, refresh, connect SSID |
| 71010 | UV Wall Extrusion tool | harveymoon | 395 | free | not stated | 2023.12003.42 W | likely | UV wall extrusion: textured curved wall from bezier line, aspect and PPI |
| 71417 | PiNODEs Beta | pitheorem | 542 | free | GPL-3.0 (repo) | 2023.11340 W | likely | PiNODEs: GLSL/TOP parametric point-processing node kit (PiKit) |
| 72196 | iXeRemin - Free Download through June 20 | fredfred | 488 | free app | GitHub repo | - | yes | iXeRemin: visionOS theremin app sending OSC; TD demo project |
| 72379 | Audioreactive Video Playhead - Definitive Ed | uisato | 2182 | Patreon | not stated | - | unknown | Audio-reactive video playhead + Veo (Gemini API) text-to-video TOX |
| 72698 | RayTK v0.46 Release | tekt | 269 | free | CC-BY-4.0 | 2025 experimental | likely | RayTK v0.46: raymarching/shader toolkit built from COMPs (SDF ROPs) |
| 73039 | SORA2 INSIDE TOUCHDESIGNER | Infratonal | 778 | free | not stated | 2023.12370 W | likely | AIMods_Sora2: OpenAI Sora 2 text/image-to-video API in TD + prototyping UI |
| 73164 | TD Copier Tool | GRNCH | 156 | free | none found in repo | 2023.12480 W | likely | ParameterCopier + OperatorCopier (batch copy to up to 10 COMPs) |
| 73301 | Repository of Custom Morphological Operators | MaxMainio | 227 | free | MIT (repo) | 2025.32820 M | likely | Morphological operator TOPs (extend palette Dilate): opening/closing/analysis |
| 73359 | Post Process Volume for TouchDesigner | tormozgh | 861 | free | not stated | 2022.24200+ | likely | Post Process Volume: apply effects inside a 3D volume (Unreal-style) |
| 74343 | Repository of Custom Signed Distance Field ( | MaxMainio | 253 | free | MIT (repo) | - | likely | Signed-distance-field TOP components (soft transitions, contours, smooth boole |
| 74725 | Web is OP | Unveil_studio | 205 | free | not stated | - | likely | Web is OP: p5.js, ML5 hand tracking, transformers.js depth, MediaPipe via WebS |

## Deep notes: 15 most useful for a general-purpose TD MCP
(Selected by relevance 3 and Mac/2025-build fit; all facts from the post, the repo README or the `toeexpand` audit. "Install" = what the author says.)
1. **TDYolo (72494, MIT, patrick_hartono)**: YOLO11 object detection with no Python env: a headless browser bundled with TD runs the model (repo README, v2); frames 640x640 so it fits the
   Non-Commercial 720p cap. Outputs `report` DAT (Object_Type, Confidence, X/Y centre, W/H, ID, ClassID), `summary` DAT, bbox/label/source TOPs. Install: drag `TDYolo_v2.tox` from GitHub Releases into a TD 2023.12000+ project. Needs internet while running. Author: ~50 fps on M4 Mac. Repo is 250 MB (models/videos): not cloned, README read raw.
2. **Versatile VJ System (73834, no licence stated, Black-Pomeranian)**: 5-layer mixer + control UI (preview, multi-layer, effector, post FX, text), pre-mapped for AKAI APC mini mk2, audio/BPM via Sound2Light OSC (127.0.0.1:8001). Open .toe, Ctrl+, = control UI, Ctrl+. = output.
   Audit: tox saved on Windows 2025.32050, 8,833 ops, 1,359 python DATs; only OS call is `socket.gethostbyname_ex` (S2L IP). Good reference for a large modular show tox.
3. **Sourcerer (62526, MIT, matthewwachter / VT Pro Design)**: media bin + source switcher: list UI, multi-select edits, file or TOP sources, transitions (Dissolve, Dip, Slide, Wipe, Blur, File, TOP), follow actions, pending-queue state machine, callbacks, preset import/export, safety lock. **Updated 2026-09-22 for TD 2025.32280** (commit f1eff8f); `sourcerer.tox` saved 2025.33070. 496 ops, 135 python DATs; only file open (presets). Pure Python extension, so Mac is very likely fine.
4. **Native Background Removal macOS (73414, MIT, aaronmylespereira)**: C++ TOP `.plugin` over Apple Vision `VNGeneratePersonSegmentationRequest`; async queue, Accurate/Balanced/Fast, ~30 ms Full HD; 2nd output = delayed original (Render Select TOP, colour buffer 1). Apple Silicon only; build with CMake or take the release and unquarantine the plugin. Not downloaded (binary).
5. **Apple Vision Suite TOP (74457, proprietary, Alaghast = Edwin Lucchesi)**: four custom TOPs (Mask, Optical Flow with Z estimate, Super Resolution via Core ML, Depth Estimation e.g. Depth Anything) for TD 2025+ on macOS arm64; .toe example. Released 24 Apr 2026; price not visible (Patreon / Ko-fi). Same author: Delaunay POP (free), Voronoi POP, L-System POP, ACID 303 / KICK CHOPs, MCX operator family (MCX Radio free).
6. **RayTK 0.46 (72698, CC-BY-4.0, tekt)**: raymarching/shader toolkit as COMPs: each ROP emits a definition DAT, an Output ROP (e.g. `raymarchRender3d`) assembles GLSL; v0.46 (27 Aug 2025) adds image-based 2D SDF and threaded shader compile, built for 2025 experimental builds (palette UI reimplemented). Docs site t3kt.github.io/raytk; install: GitHub release tox. Older 0.11 = 63888; precursor RTK = 61086.
7. **UberGui V4 (63859, MIT, lucasm / Enviral Design)**: UI layer over custom parameters rendered by the webRender TOP (separate Chromium thread; many UIs, near-zero resting cost; touch + mouse; CSS-styled via a styles page). `UGV4.tox` 290 ops, 79 python DATs, needs TD 2021.12380+. Same author: ArcBall COMP, normal-map combiner, CHOP matrix transform (Patreon EnviralDesign).
8. **Stage Window (62640, GPL-3.0, TimFranklin)**: media-server canvas: "Media Items" (any TOP) and "Output Items" (ortho cameras) placed freely; snapping, stacking order, shortcuts (Ctrl+D duplicate, alt-snap), callbacks, edge-blend concept toe. Last commit 2020-03-17 (v1.02, build 2020.20020). Same author: LTC Timecode Cue List (62701, GPL-3.0; cue ranges, transport, 1.03 fixed Mac icons).
9. **Warpa (66430, MIT, Ennui)**: 2D mesh projection-mapping warp tool: load OBJ meshes (demo cubes), pick points/polys, nudge, zoom/pan, wireframe, canvas edge; `warpa.tox` 1,336 ops / 442 python DATs, saved 2023.12230 (commit fad6feb, Apr 2025). Same author: Schedule CHOP (Windows C++ CHOP, public domain).
10. **LYGIA for TD (66804, MIT upstream, LeithBA)**: Text DAT of GLSL in, resolved GLSL out; `#include "lygia/filter/boxBlur.glsl"`. **Audit flag:** `datexec1` uses urllib to fetch include code from lygia.xyz at runtime (needs internet, trusts remote GLSL). 54 ops, saved 2022.28040.
11. **Strobber (71752, no licence, Skywalker.Visuals)**: 5 strobe/glitch TOP effectors (Classic_Audio, Complex, MAX_Audio, Scan, MAX_Complex_Audio) + toe; frequency, dry/wet, strobe speed, noise amount, audio analysis in, ramps/easings (Shadertoy tlcGzf, Function Store tools). Saved 2023.11340. Same author: Image Dithering (71378, 6 algorithms, GPU heavy).
12. **TLMODS (72693, THETOUCHLAB, free)**: keyboard mods for the network editor: Show Related Ops, Connect Wire (2-step select), Cut Wire (hold key over wire), Insert/Disconnect ops, Copy Error/Warning to clipboard, Get Table DAT... Beta tox/toe saved on macOS 2023.12230/12370, 594 ops, 136 python DATs, no network/subprocess flags. Useful reference for editor automation the MCP could expose.
13. **Delaunay Triangulation POP (74014, MIT, Alaghast)**: C++ POP plugin, 2D Delaunay from POP points or CHOP reference; Sync/Async, output Triangles/Edges/None, optional PrimCenter/PrimArea/Colour/Circumcircle/NeighborCount attributes; releases `Delaunay-1.9.4-MAC.zip` / `-WIN.zip`. Not downloaded (binary).
14. **Introduction to POPs (72388, ParseError)**: three example files (particles + Proximity, advanced Proximity, Trail + 3D skin) from TD Summer Event Paris 2025, made on experimental 2025.30060; free on Patreon (patreon.com/parseerror_); not fetched. POPs are in the official 2025 line, so these are the entry examples.
15. **PiNODEs (71417, GPL-3.0, pitheorem)**: GLSL-TOP point-processing kit (12 categories INITIATE..EFFECT), 10,642 ops and 6,983 custom pars in one tox (saved 2023.11340), v0.69 Mar 2025; author says POPs will supersede it and PiNODEs will be refactored. Docs on Notion, siblings PiCompositor (67533) and PiKit.
Also worth a look: UV Wall Extrusion (71010, curved LED/projection wall UVs + aspect for PPI), Projector Coverage Tool (74222, Gumroad ~$15), Galileo Mapper family (62142, DMX/OSC/MIDI learn, free non-commercial), VideoBin (66031, VDMX-style bin, repo vento17/VJ_TOOLS), TD Copier Tool (73164, bulk parameter/operator copy, Oct 2025), Web is OP (74725, p5/ML5/transformers.js in WebServer DAT, Patreon free), AIMods Sora2 (73039), Fancy Frustum (62623), PICMA (62394), webGUI (63523), Cycles (63702, tap tempo + Ableton Link), sudoSignals (64784).

## Files downloaded (all free, no login, <= 50 MB; nothing loaded into TD)
- **81 derivative.ca/GitHub-raw files, 18.2 MB** (80 attachments from 49 posts + `multi_noise_gen_module.tox` from t3kt/vjzual4; 11 more attachments were already fetched by another agent and reused), each `toeexpand`-ed on a copy (`files/<id>/expanded/<name>/`): **171 tox/toe audited** = 83 attachments + 7 from unzipped zips (Sora2, CharAnimation x2, Galileo) + 81 from cloned repos (MaxMainio/TD_ capped at 40).
  SHA-256 for every attachment is in the jsonl (`files[].sha256`). Attachment licences are mostly unstated (see table); build info is in `audit.buildinfo`.
- **27 git clones (depth 1), ~198 MB incl. .git**, commit in `files[].commit`: Curve_Editor 62089, UESequencerSync 66050, chainGpu 68172, Speedy-Shaker 63231, UberGui 63859, VJ-System_Sample 73834, Warpa 66430, TD_Copier_Tools 73164, td-sourcerer 62526,
  Covid_World_Tracker 62704, Distance-Calculator 66227, Computer-Music 69924, TD_Stage_Window 62640, TDraymarchToolkit 61086, TD-Localization 61007, ParHelpTranslator 64009, colorGrading 64907, File-Collector 62406, ColorPicker-ScreenGrabber 62495, Attraktors_Creator 66082,
  PiNodes 71417, MaxMainio/TD_ 73301 (shared with 74343), VJ_TOOLS 66031, Post_Process_Volume 73359, ScheduleCHOP 62054, LidarTracker 66632 (+ Twitcher/zuweiser already cloned by another agent). Windows .dll files that came with clones (LidarTracker x2, ScheduleCHOP, MouseInAltCHOP) were deleted again (record-only rule).
- Largest attachment sets: TLSNAKE 4.7 + 4.9 MB, PiNODEs 1.0 MB, VJ_System.tox 0.9 MB.

## Audit flags (what the expanded tox/toe do besides ops; "eval/exec/onStart" appear in almost every large tox and are not listed)
- **Shell / OS access:** TouchOut 69571 (`osascript` click simulation via subprocess), TLPAD 73186 (**compiles C++ `multitouch_monitor` with `g++` at runtime**, runs/kills it with pkill; macOS, IOKit), TLCHAT 70847 (`osascript` opens Terminal to run **ngrok** on 8080, queries 127.0.0.1:4040; exposes a server),
  Wifi manager 69981 (`netsh`, Windows), dome previz 62690 (`ctypes.windll`), Sora2 AIMod 73039 (reads OpenAI key from env var `OA1`, expects a conda/venv; README mentions pip).
- **Network:** LYGIA 66804 (urllib fetches GLSL from lygia.xyz), Par.Help Translator 64009 + 61007 (unofficial Google translate endpoint / UI-string patching), VJ System (socket, local IP), webGUI 63523 (socket + websocket server), SpotifyBridge 74390 (Patreon, local OAuth callback 127.0.0.1:8888, lrclib.net).
- **Browser opens:** TD Copier Tool and MaxMainio components open documentation URLs (`webbrowser`); MaxMainio SVG_Out / CMYK_In/Out scripts mention `pip` and use `shutil` (SVG/print helpers; not inspected further).
- **Opaque:** LidarTracker (3 tox) are encrypted `.enc`; chainGpu and Attraktors Creator tox are locked (`.lod` blob, no readable network).
- A keyword scan (os.system, subprocess, socket, urllib/requests, ctypes, eval/exec, shutil, pip, osascript, environ) found no obvious exfiltration or credential harvesting; it is not a full code review. Nothing was executed or loaded.

## Recurring authors
THETOUCHLAB 8 (TLCHAT, TLKEYOPS, TLSNAKE, TouchOut, Web Wizards, TLPAD, TLMOTION, TLMODS: macOS-built, free, tips via buymeacoffee) | lucasm/Enviral 4 | Unveil_studio 4 (midi learn, PROMOTE, bloom, Web is OP) | fredfred 4 (visionOS/OSC/NDI + synth + distance) |
alphamoonbase 3 (Galileo mappers, Twitch chat, downloader; olib) | tekt 3 (RayTK x2, noise) | xnimax 3 | Eusebi 3 (UI Theme, OSCToolset) | anodin 3 (PICMA, CharAnim, camera) | _shandor 3 (Fancy Frustum, Swaggy Bokeh, Speedy Shaker) | function.store 3 (Random CHOP, Complex UV, Topology 3D; Gumroad pay-0 options) |
snaut 3 | MaxMainio 2 (library repo MaxMainio/TD_, 2025.3xxxx saves) | Alaghast 2 (Mac/POP plugins) | uisato 2 and dcheesman 2 (Patreon only) | DBraun 2 (TD-Faust, PyTorchTOP).

## Windows-only / NVIDIA-only (11)
Delaunay SOP 65383, Convex Hull SOP 65356, DistThresholdCHOP 61108, Schedule CHOP 62054, LidarTracker 66632 (all C++ Windows CHOP/SOP dlls); Wifi Network Manager 69981 (netsh); Color Picker/Screen Grabber 62495 (custom Mouse In CHOP dll);
Alfred ROOM 64136 (Kinect V2); PyTorchTOP 62578 (README: no OSX, LibTorch CUDA); NVIDIA-only: Waterfall with NVIDIA Flow 67784, Topology 3D 65266 ("not compatible with most Macs").
Mac-positive: TDYolo, Native BG removal, Apple Vision Suite, Delaunay POP, TD-Faust, Attraktors Designer, sudoSignals and all THETOUCHLAB tools.

## Skipped / not fetched
- No leak, crack or rights-dubious items in these 119 posts.
- Size: Photogrammetry Workshop zip 66333 (78 MB, >50 MB); TDYolo repo clone removed after clone (250 MB).
- Dead/blocked: Spray Can 63082 Dropbox link returned an HTML page, not the zip (dl=1 tried).
- Paid / login-gated, recorded only: Patreon (uisato 72379/73408, dcheesman 69724/69710, ParseError 72388, SpotifyBridge 74390, Web is OP 74725, Alaghast Apple Vision Suite 74457, Attraktors Designer 66839, PROMOTE page), Gumroad/self-hosted
  (Projector Coverage Tool, OSCToolset v2 ~$30, UI Theme, Topology 3D, Complex UV), olib.amb-service.net links (Twitch Chat, File Downloader, Random CHOP, midi learn, GPU bloom).
- C++ plugins, binaries not downloaded: TD-Faust, Delaunay POP, AppleVisionMask, PyTorchTOP, convexhullsop, DistThresholdCHOP (README + licence read via raw.githubusercontent only).
- Gumroad price figures (`price_cents` seen on pages) and "paid?" flags are unverified.

## Open questions
- Why displayed views are not monotonic against the sort order (possibly a recent-views or weighted counter).
- Which featured assets Derivative promotes is rotation-based; the full promoted pool may be larger than the 14 seen on pages 20-26.
- Mac status of the "likely" group is untested; before using any of them in the MCP, load in a scratch project and check `td_errors`.
