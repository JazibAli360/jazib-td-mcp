# Community scrape, slice 09 (derivative.ca/community?page=160..179)

Crawled 26 Oct 2026. Data: `research_src/community/slice_09.jsonl` (300 records). Content is 14 Nov 2019 to 12 Jun 2020
(TD 2019/2020 builds); everything below is old-build material, so op names/behaviour need re-checking on 2025.31550.
Method: 20 listing pages, 15 posts each (5 pinned 2025 featured posts repeat on every page and were left to the page-0
slice: 75538, 75535, 75551, 75560, 75562). Each post fetched once (no 429/403/5xx). Sequential, 2 s sleeps.

## Counts
| type | n |
|---|---|
| tutorial | 91 |
| post (blog / news / artwork / interview) | 84 |
| asset | 66 |
| workshop | 42 |
| event | 17 |
| job | 0 |

Relevance (0-3, general TD mastery): 3 = 38, 2 = 108, 1 = 103, 0 = 51 (mostly workshop/event listings).
Mac: windows-only 15, confirmed mac-ok 6, unknown 279 (pages rarely say; none of these were run).

## Top 15 by relevance
1. 62917 TouchDesigner | Instancing Examples (mir.works): 40+ instancing techniques with in-network readme; GitHub repo is 112 MB so NOT downloaded. Page says macOS works (small readme scrollbar bug).
2. 62745 Raymarching in TD series (exsstas): 3 videos, ~5 h, GLSL raymarching; repo `exsstas/Raymarching-in-TD` (MIT, 17 .toe) downloaded.
3. 62936 TD Initiative Library (valentindufois): community utility .tox collection (14 tox) from a studio; GPL-3.0; downloaded.
4. 62701 LTC Timecode Cue List (TimFranklin): LTC timecode generator + named-range cue list app; GPL; show-control pattern; repo downloaded (39 .toe).
5. 62689 Layer Based Timeline Tool beta (TimFranklin): multi-layer timeline built in 3D with render-picking UI, 18 tox + Python; GPL; downloaded.
6. 62526 Sourcerer (matthewwachter): media organisation / switching / processing system for images + generative sources; MIT; repo still active (last commit 2026-09-22); downloaded.
7. 62577 Bridgets (emintzer): mapping engine from 13 input device types to Widgets with learn/forget; LGPL v3 (stated); .tox attached, downloaded (TD2020.20020).
8. 62663 OSC Query Server component (manuel_mitasch): exposes custom pars over OSCQuery so TouchOSC/Chataigne can discover them; MIT; downloaded with Vidvox proposal.
9. 62142 Galileo Mapper Family (alphamoonbase): drag a par in, learn DMX/OSC/MIDI channel, range auto from par; zip attached, downloaded.
10. 62623 Fancy Frustum (_shandor): camera/projector frustum visualisation + multi-camera sync (tox pre/post 20020); downloaded.
11. 62238 td-shadertoy (matthewwachter): convert/browse Shadertoy shaders via its API into TD components; MIT; downloaded.
12. 62819 Python Optimization and Pro Tips (elburz, video): when to use Python vs nodes, perf pitfalls. Video only.
13. 62835 Ultimate Movie Loading Guide (elburz, video): load assets of any size without dropped frames via Python preload patterns.
14. 62861 Control Your TD Installation Remotely (elburz, guest Ben Benjamin): WebSocket + ngrok remote control; pairs with 62855 (web frontends) and 62907 (Node-red).
15. 62208 LED Basics for TouchDesigner Pros (elburz): LED wall terms, bottlenecks, processors; the most on-topic for LED stage work.
Next tier (rel 3, not listed): 62605/62625 UV-unwrap a stage box for mapping (jhoepffner, downloaded), 62394 PICMA picker+mapper, 62542
PatternGenerator test patterns, 62551 beat detection, 62764 BPM detection, 62665 DMX controller tutorial, 62600/62576 vertex shaders in
GLSL MAT, 62808 GLSL point-cloud tricks, 62854 undo/redo UI, 62254 Widgets tips, 62614 Engine COMP, 62631 point clouds, 62588 top 2020
features, 62570 2020 Official update, 62754 collaboration best practice, 62931 keeping time.

## Files downloaded (41 GitHub clones + 83 attachments, 132 MB working tree; 291 MB on disk incl. .git)
Folder: `research_src/community/files/<postid>/`. Nothing opened, run or loaded. Zips were listed with `unzip -l` only (no extraction).
- GitHub clones (commit hash in the jsonl): TouchDesigner_Shared 62963 (GPL-3.0; 34 tox, 5 toe, DBraun starters); Twitcher 62962 (Unlicense; 1 tox);
  Touchdesigner.GenerativeMeshes 62960 (MIT; 5 py, 1 toe); TD-Initiative-Library 62936 (GPL-3.0); Tutorial-Repo 62870/62854 (GPL-3.0; 4 toe,
  point sprites + undo/redo); zuweiser 62827 (MIT; toe+tox); videoswitcher 62823 (no licence; 3 toe); Banana_CurrentlyPlaying 62774 (GPL;
  Spotify API, 9 py, 4 tox); SimpleMixer-2 62771 (MIT; 13 toe, 7 tox); TD_GLSL_Particules 62769 and TDinitiation 62753 (no licence; 4 toe each);
  TD_Github 62766 (no licence; 1 tox); ColorizeTOP 62761 (no licence; C++ Custom TOP source, VS project, CUDA, Windows); Raymarching-in-TD 62745 (MIT);
  dynamic-backgrounds 62740 (no licence; 1 toe); Covid_World_Tracker 62704 (no licence; 1 toe, 2019.20140); LTC-Timecode-Generator 62701 (GPL);
  Multi-Layer-Timeline 62689 (GPL); face_recognition 62675 (MIT; Python lib, not TD); td-osc-query-server 62663 (MIT) + OSCQueryProposal (docs);
  TD-Tutorials 62655/62086/62085/62084/62083 (MIT; 13 toe, 3 tox, polyhop tutorials); TD_Stage_Window 62640 (GPL-3.0; ~97 files, versioned toe backups + examples);
  TDNeuron 62633 (GPL; 34 MB, docs + 1 tox + 1 toe); uvUnwrappingBox 62625, uvUnwrapping_TD 62605 (no licence; toe+tox+pdf);
  td-mirobot 62591 (MIT; G-code robot arm); td-sourcerer 62526 (MIT); TD-ColorPicker-ScreenGrabber 62495 (GPL; ships a .dll, Windows);
  TD-OpenCV3TOP 62407 (GPL; C++ Custom TOP, plist = Mac project files present); TD-File-Collector 62406 (GPL; 1 tox); SenselMorphTDRaw 62405 (GPL; C++ CHOP + dll);
  TD-FaceCHOP 62239 (custom licence text; C++ CHOP, Mac plist present); td-shadertoy 62238 (MIT); TD-Curve_Editor 62089 (no licence; 5 py + tox);
  ScheduleCHOP 62054 (Unlicense; C++ CHOP + dll, page says Windows only).
- Attachments from derivative.ca (`/file/<id>/download`, no login): 65 .toe/.tox/other + 18 .zip across 64 posts, e.g. waveSimulation 62925, easing
  functions 62899, iridescent GLSL MAT 62799, Leap hand bones 62874, color curves 62913 (two builds), 1_32mapperfamily.zip 62142, Fancy Frustum 62623,
  patterngenerator 62542, VoronoCubes 62744, abstract grid.zip 62743, bridgets 62577. Zip listings are in each jsonl record (`zip_listing`).
- Licence of attachments is almost always not stated (269 of 300 records say "not stated"); treat as unlicensed reference only.

## Recurring techniques / ops
Python extensions + callbacks (26 posts), GLSL TOP/MAT/vertex (23), feedback loops (21: slitscan, pixel sort, VHS, spectrum), instancing (17: Geometry COMP,
Line MAT, distance-based, cellular noise), MIDI/OSC/DMX control mapping (15/12/7: Galileo, Bridgets, Zuweiser, OSC Query, DMX controller), NDI (8:
Skype/NDI, iPhone->Zoom, social streaming), point clouds (6), PBR (6), compute shader particles (62080, 62951), Widgets/UI building (Franklin's undo/redo,
infinite scroll, auto-UI), web frontends / WebSocket / Node-red remote control, mapping aids (frustum viz, UV unwrap box, test patterns, PICMA).

## Authors who post a lot
elburz 39 (Derivative HQ blog, mostly video posts on workflow, hardware, Python, LED, web control), isabelle 12 (Derivative news/interviews/InSession),
gnomalab 12 (Spanish beginner tutorials + tools), videoso 10 (Spanish MARATON NTRCTV sessions), narumin256 9 (TDSW Tokyo events), tolch 9 (Spanish
tutorials), elekktronaut 8 (beginner effects: slitscan, pixel sort, beat detection), alphamoonbase 8 (Callback Manager, D'n'D, Galileo, Tweener, BPM, DMX),
exsstas 7 (GLSL, raymarching, voxels, perfect loops), lucasm 7 (PBR, matrix, enviral-design tools), TimFranklin (LTC, timeline, Stage Window, UI).

## Windows-only / NVIDIA-only (15)
62921 Spout for Python (also GitHub repo gone: 404), 62914 NVIDIA Flow fire, 62717 Flow clouds, 62608 theRob Flow visuals, 62856 Kinect+Flow puppet,
62824 and 62817 NVIDIA Flex (Windows+NVIDIA features), 62850/62847/62712 Kinect, 62761 Colorizing TOP (CUDA), 62534 Style Transfer TOP (CUDA),
62495 Color Picker (Windows dll), 62788 Infinite Scroll (ctypes), 62054 Schedule CHOP (page says Windows only). Not usable on our Mac as-is; Spout -> Syphon
equivalents exist. Mac-OK evidence: 62711 Kinetic Typography part 4 (Mac OSX workaround for texture error), 62737 NDI broadcast works on Mac OS, 62740 iPhone->Zoom
(Mac workaround), 62917, 62784 (tested on MacBook Catalina), 62823.

## Skipped / not fetched
- Over the 50 MB cap, not downloaded: 62917 instancing repo (112 MB), 62871 Pbr_Linear_Gamma zip (65 MB), 62783 Network Visualization Tool zip (77 MB),
  62713/62695 wuestenarchitekten/workshops repo (94 MB), 62578 PyTorchTOP-cpumem (55 MB).
- Not an allowed type: gifs/Gource videos (62788, 62783), a 0-byte course timelapse (62580), a reference-sheet file (62135).
- Patreon / paid: 62939 (Contraption), 62930, 62928, 62885, 62877, 62865, 62864, 62808 (exsstas / Kohui project files on Patreon), 62900 and 62788
  (EnviralDesign Patreon support links); not fetched. 62914 NVIDIA Flow extra files on a Dropbox link (not fetched, off-site).
- Leaks/rights: none seen in this slice.
- 404 repos: Ajasra/Spout-for-Python (62921, 62675), ianleblanc/kbui (62857).

## Open questions
- Which of the .tox files (Galileo, Bridgets, Sourcerer, Stage Window, Layer Timeline, LTC) still load cleanly on 2025.31550? Untested on purpose (nothing was loaded).
- Many tutorials are video-only; their technique detail is only in the video, which this slice did not transcribe.
- Slices overlap: other agents appear to be downloading some of the same post IDs (extra folders named expanded*, repo_*__* appeared under my IDs), so the lead should dedupe by post id.
- Events/workshops (59) are 2020 and mostly stale; kept for the author/instructor list only.
