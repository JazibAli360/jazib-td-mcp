# Community scrape, slice 06 (listing pages 100-119, 26 Oct 2026)

Source: `https://derivative.ca/community?page=100..119`, fetched 26 Oct 2026 (2 s sleeps, 2 lanes, no 429/403/5xx, no failures).
Data: `research_src/community/slice_06.jsonl` (291 rows, one per post). Post ids 60786-75562.
Date span: mostly **Jan 2022 to early Feb 2023** (page 100 also carries five fresh 20-24 Oct 2026 pinned posts: 75535, 75538, 75551, 75560, 75562).
The listing is live, so neighbouring slices overlap a little (other agents also wrote into some `files/<postid>/` folders, e.g. an `expanded/` dir in 66019 that is not mine).
Summaries in the jsonl are auto-trimmed from the page text (not rewritten); `relevance` is my judgement (0-3, general TD mastery); `technique` is null because pages rarely state an op chain; Elburz/Interactive & Immersive HQ posts are teasers ("click here" to interactiveimmersive.io), so only the teaser was read.

## Counts
| type | n | | type | n |
|---|---|---|---|---|
| tutorial | 88 | | workshop | 38 |
| post | 79 | | event | 35 |
| asset | 51 | | job | 0 |
Relevance: 3 = 53, 2 = 96, 1 = 79, 0 = 63 (events/workshops mostly 0-1).
Files: 72 posts carry a file/repo/store link. Downloaded 67 items (40 derivative.ca attachments, 27 GitHub shallow clones), about 158 MB on disk incl. `.git` (about 76 MB without), 26 distinct repos.

## Top 15 by relevance
1. **75538 TouchDesigner POPs vs SOPs** (elburz): POP vs SOP differences, performance, point-cloud workflows. Current-build knowledge for 2025.31550. Teaser only.
2. **75535 Aura Flow tutorial 34** (pao.olea): trail shape built with POPs and attributes. YouTube video, no file.
3. **75551 New Timecode features** (elburz/Sal): Timecode CHOP + Python to fire timed effects from media timecode. Show-control relevant.
4. **75562 AVY modular performance system** (elekktronaut): TD framework with presets, MIDI mapping, fx, audio analysis, OSC, Ableton Link, web UI. Patreon only (not downloaded).
5. **66804 Lygia for TouchDesigner** (LeithBA) + **66847 LygiaTD v1.0.0** (vectorsize): LYGIA shader function library for GLSL TOP. Prosperity licence (non-commercial). Cloned both.
6. **66736 Pixel Wrangle** (miu-lab): GLSL TOP framework with UI, presets, shared include functions (raymarch lib). GPL, release candidate, tested on Windows.
7. **66408 Artio** (dylanroscover): dynamic pixel-map generator for multi-display / LED walls via a replicator. GPL; v0.4 to v0.6 tox in repo. Directly useful for LED mapping.
8. **66430 Warpa** (Ennui): 2D mesh-warp projection mapping tool, MIT, tox + repo.
9. **67099 Web GUI for TD** (blankensmithing): web page auto-generated from a container, controls TD over websockets (torinmb td-web-gui + Socket-Server-Template, MIT).
10. **67004 WebRTC Remote Panel web demo** (JetXS/Derivative): official open-source browser client for the WebRTC remote panel (Shared Use License).
11. **66493 NDI Tools for immersive experiences** + **66462/66492/66509 Installation Networking 1-3** (elburz): NDI tools and IP/port/firewall basics. Teasers.
12. **66527 TDAbleton 2.0** (Ivan) and **66144 VST install Mac+Windows** / **65676 Vulkan+VST+comments build tour**: audio-plugin and Ableton links.
13. **66826 macOS 1-week review** (M2 Air) and **65790 Background removal on Mac without RTX**: Mac-specific facts and workarounds.
14. **66031 VideoBin** (vento303): VDMX-style media bin / VJ player, tree of folders with previews; tox + repo (no licence file).
15. **67032 TD Data Model**, **66947 run() to delay Python** (example .toe), **66402 Python vs operators**: core concepts. Also **65958 Instant Probe** and **65709 disable all viewers** (performance helpers), **65707/65708/65719/65740 UI Basics series** (amazingrobot: custom buttons/sliders/tweener).
Runners-up: 66499/66474/66824 particlesGPU 2022 (forces, optical flow), 66312/66229/65777 RayTK tutorials, 66836 audio reactivity over OSC, 66825 3D projection mapping, 66870 GLSL chromatic aberration, 66168/66191 feedback loops, 66811 MIDI In CHOP quirks, 66209 TD web servers, 66467 RGB to RGBW shader, 67014/66427 TouchEngine for Unreal.

## Files downloaded (under `research_src/community/files/<postid>/`, nothing opened or run)
derivative.ca attachments (40; licence mostly not stated on the page; builds mostly not stated):
- **tox/toe, single:** 67145 XTouchMini_0.tox + midi_abstracter.py (X-Touch Mini mapping); 66947 runExamples.toe; 66888 listerUpdateExamples.toe; 66940 Depth_Map_Viewer.tox; 66795 FOLDERS.tox; 66804 Lygia.tox + Lygia.toe; 66430 warpa.tox; 66467 RGBToRGBW.tox; 66361 RealRamp1.tox; 66377 TOPPhysarum.toe ("non commercial use only"); 66309 SerumTemplate.toe (credit me, non-commercial; "TD2022"); 66202 tmi.tox + tmi example.toe (GLSL colour temperature); 66232 ResetPLS1.tox; 66084 slowfeedback.toe; 66089 StepSequencer.tox; 65985 ListerMix.tox; 66019 feedback3D.tox; 66031 VIDEO_BIN.35.tox; 65920 ARuco_0.tox (needs TD 2022.20150, Python 3.9 OpenCV); 65958 instant_probe_0_5.tox; 65782 webcam_background_changer.tox; 65852 Dart-throwing p1.toe; 65719 Tweener_v1.1_0.tox; 65732 FFTOcean_V1.0.tox; 65741 Fluid_simulation.tox; 65754 Lines Complete.2.toe; 65756 TweenerStressTest.toe; 65759 QRMaker.tox; 65698 ARAS_DragAndDrop_0.toe; 65702 Dualsense_Controller.tox; 65709 viewer_status.tox.
- **zips (listed with `unzip -l`, not extracted):** 66517 LTouch-1.0.0.zip (L-ISA OSC controller: tox, PDF docs, Python extensions, GPL LICENSE.md); 65719 Custom_UI_Buttons Part 3 (Tweener transitions, .toe + PNG/JPG assets); 65707 Part 1, 65708 Part 2 (buttons / content control, .toe + assets); 65740 ARAS_SimpleCustomSlider.zip (.toe + handle.png); 65759 ARAS_QRMaker_Demo.zip (QRMaker.tox + QR png).
- Skipped >50 MB: 66333 B2BK_WORKSHOP_2022.zip (74.4 MB, photogrammetry scans + toe).
GitHub clones (depth 1, commit hash in jsonl `files[].commit`), licence from the repo's LICENSE file:
| post | repo | commit | licence | inside (top level) |
|---|---|---|---|---|
| 67099, 66707 | torinmb/Socket-Server-Template | ba41467b | MIT | websocket server template (Node) |
| 67099 | torinmb/td-web-gui | dbcbffc7 | MIT | web GUI client + tox |
| 67014, 66427 | TouchDesigner/TouchEngine-UE | 59265022 | Shared Use License | Unreal plugin source (9.7 MB) |
| 67004 | TouchDesigner/WebRTC-Remote-Panel-Web-Demo | 796ad17a | Shared Use License | web demo client |
| 66847, 66804 | patriciogonzalezvivo/lygia | aa7580be | Prosperity 3.0 (non-commercial) | GLSL/HLSL/WGSL function library |
| 66847 | vectorsize/lygia-td | 7818681b | Prosperity 3.0 | LygiaTD tox + docs |
| 66795 | drmbt/FOLDERS | 08a622ae | MIT | FOLDERS tox |
| 66736 | miu-lab/Pixel-Wrangle | 9e2bcf66 | GPL | Pixel_Wrangle.tox, Tox/*.tox, Common/*.glsl, Presets, raymarch GLSL functions, vscode config |
| 66517 | Ethereotek/LTouch | d3da95db | GPL | L-ISA controller tox + Python |
| 66430 | Richard-Burns/Warpa | fad6febe | MIT | warpa tox, docs |
| 66408 | theexperiential/Artio | e038ad25 | GPL | release/Artio-v0.4..0.6 tox, dev toe, README |
| 66177 | shader-park/shader-park-touchdesigner | 1e6b9b93 | MIT | Shader Park plugin tox |
| 66089 | igierard/TD-step-sequencer | baabc9c6 | MIT | StepSequencer tox |
| 66050 | L05/UESequencerSync | 7e2f7322 | MIT | UE widget + TD tox |
| 65739 | ovvostudio/TD-Monogram | 72544dca | CC (legal code) | Monogram console tox |
| 65696, 65699 | KaeganCasey/hsv_constant, meta_ramp | b997b95c, 40d4820e | MIT | HSV Constant TOP, MetaRamp TOP (OLIB) |
| 66082 | Jive-Faury/Attraktors_Creator | 0c85e6ed | none in repo | Attraktors_Creator.tox, demo .toe, attractor XML defs |
| 66031 | vento17/VJ_TOOLS | dd673074 | none in repo | VideoBin tox versions |
| 65798 | kylebmeredith/L-System-Plus | 918fe513 | none in repo | L_System_Plus.tox, demo toe, recording.mov (40 MB) |
| 66381, 66227 | fredfred Speed/Distance calculator | c86a1b51, fc1fc84e | none in repo | small tox COMPs |
| 66632 | FifthChat/LidarTracker | c435edd7 | none in repo | LidarTracker v3.x tox + v1.0 **.dll** C++ CHOP (Windows) |
| 67156 | Ajasra/SlamtecCHOP | f26f13bb | none in repo | C++ CHOP source, Visual Studio project, Windows DLLs |
Not cloned: 67014/66427 TouchEngine-UE-Samples (156 MB), 66582 TD_Launcher (96 MB, Windows-only), 65859 turntable repo (72 MB), 65732 oreon-engine (unrelated Java engine); GitHub release-only / sponsors / wiki links recorded only.

## Recurring techniques / ops
Python (extensions, run(), tdu.Dependency, type hints, Python tags): ~38 mentions; TOP/CHOP/DAT basics; instancing (collage typography, Lego bricks, vera molnar series); feedback loops (3 tutorials + 2 assets); GLSL (chromatic aberration, Lygia, Pixel Wrangle, physarum, FFT ocean, fluid sim); particlesGPU 2022; RayTK (7); VST3/AudioVST CHOP (8, new in 2022 builds); NDI (5); Arduino (5); Kinect/RealSense/ZED/Oak-D sensors; web (WebRTC, websockets, Web Server DAT); Lister-based UIs (Unveil_studio, amazingrobot); TouchEngine (UE5); Unreal/Blender/Ableton/Max/TouchOSC bridges; Elburz's "artist-inspired" generative series (Vasarely, Riley, Le Parc, Joy Division, Whitney, Ikeda, Kandinsky, etc.).

## Authors who post a lot
elburz (92, Interactive & Immersive HQ teasers), isabelle (14, Derivative editor/showcases), jbthiebaut (13, Music Hackspace meetups), 3dwalker (9, Hou2Touch courses), Unveil_studio (8, free assets), function.store (7, utilities + Patreon), amazingrobot (7, UI/tweener), tekt (6, RayTK), Tyrell (5), aelab (5), blankensmithing (4, Patreon), JetXS (4, Derivative TouchEngine/WebRTC).

## Windows-only / NVIDIA-only / Mac notes
Windows or NVIDIA: 67085 and 66794 (Maxine / RTX face tracking), 65957 and 65763 (NVIDIA Flex), 66288 (TensorFlow-GPU, "Windows users only"), 65782 (RTX background changer), 66582 (Windows launcher), 66233 (Spout to Unreal), 66632 and 67156 (C++ CHOPs shipped as .dll), 67129 (Wacom "Tablet to OSC" app is Windows; TC-Data iPad part not). 66736 Pixel Wrangle: author tested on Windows RTX only.
Mac: 66826 macOS review, 65790 background removal on Mac, 65702 Dualsense OSC (Mac app), 66839 and 66142 Attraktors Designer (Windows and macOS, TD 2021/2022; non-commercial render limited to 1280x1280), 66144 VST install on Mac. Elgato Stream Deck API Ninja plugin only visible on Windows (66326).

## Skipped / paid
No leaks or cracks found. Paid or Patreon-gated, recorded only: 75562 AVY (elekktronaut), 67099/66707/66177/65790 blankensmithing, 66906/66520 (patreon posts), 66839/66287/66142 JiveFaury, 66900/66361/66233/65805 function.store (some Gumroad), 66795 drmbt, 67113 and 67129 Gumroad project files, 65779 Kohui (Patreon), 66980 tekt DMX workshop (Patreon). 3dwalker's Hou2Touch courses are paid. Elburz posts: body behind external link.

## Open questions
- Many elburz tutorials are only teasers; fetch the interactiveimmersive.io pages if the technique detail is wanted (not in scope here).
- Lygia licence (Prosperity) restricts commercial use: confirm before using in client work.
- The tox/toe builds are mostly unknown (pages rarely state them); anything from 2022 or earlier needs a load test on 2025.31550 before trusting.
- Event/workshop pages are not technique sources (63 rows scored 0); keep only if the series names matter.
