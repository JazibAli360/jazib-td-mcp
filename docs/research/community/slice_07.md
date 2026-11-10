# Community slice 07: derivative.ca/community?page=120..139 (26 Oct 2026)

Crawl: 20 listing pages, 305 unique post pages fetched (0 failures, 2 s spacing; server TTFB was 30-50 s under load). Data: `research_src/community/slice_07.jsonl`.
Dates: almost all posts are **Jan-Dec 2021** (some Jan 2022). Five Oct-2026 posts (75535/75538/75551/75560/75562) sit at the top of
page 120 (pinned/newest block); 73 events/workshops have no date on the page. Build for the era: TD 2021.1xxxx; "build" is only filled where the page states one.
Relevance = 0-3 for general TD mastery (any use case).

## Counts
tutorial 116, post 69, asset 47, workshop 38, event 35 (= 305). Relevance 3: 30, 2: 127, 1: 144, 0: 4.
Posts with a downloadable attachment: 34 (54 files). Posts linking a GitHub repo we cloned: 7. Leaks/cracks found: 0.
Most "tutorial" and many "post" entries are stubs: a video link plus 2-4 sentences (Elburz / Interactive & Immersive HQ), the technique is in the video.

## Top 15 by relevance
1. **65663 3D volumetric rendering (near/far on camera)**, Winfred_Nak. Slice 3D scene into 2D planes with camera near/far; send to Madrix/Resolume
   (they pixelmap) or pixelmap in TD to DMX/Art-Net. 9 files incl. TOPs and POPs volumetric versions, RayTK sampling example. Direct LED/Resolume value.
2. **64897 LED Mapping & GPU Pipelines (Lucas Morgan)**: GeoPix, open-source LED mapping tool for TD (Enviral Design) and its GPU pipeline. No file on page; find repo.
3. **65064 QFH HapQ Converter**, lucasm/EnviralDesign: batch HapQ transcode at 300-1000+ fps by disabling real-time flag and Perform COMP draw (must run in Perform mode). Media prep for VJ servers. No attachment on page (Patreon/GitHub sponsor links).
4. **64840 Best Communication Protocols in TD**, Elburz: Spout, NDI, Touch In/Out, OSC, UDP, Dante chosen per TOP/CHOP/DAT/SOP/audio. Output-to-Resolume decision guide.
5. **64866 Projection Mapping Tools in TD** and **65015 Cameras as Projectors**, Elburz: built-in mapping tools overview; camera = projector inverse for projection texturing.
6. **65007 B2BK Custom Tools & Buffer Techniques**: 3D render-pass workflow (FastMAT, FastENV, NormMask, PosMask, UVPaint); two big .toe (89 MB). 2023 fixes.
7. **65629 Tweener** (amazingrobot): Python tweening engine, `op.Tweener.To/FromTo/KillAllTweens`, 30 easings, delay, repeat, pingpong, onComplete. Global OP shortcut "Tweener". 7 files.
8. **64784 sudoSignals Beta v2** (raganmd/SudoMagic): remote-control dashboard + TD plugin for installations; repo cloned (docs site only).
9. **64818 WebWelder** (djipco): 2-way WebSocket/JSON bridge TD <-> web page; Apache-2.0; repo cloned with tox + `www` example.
10. **65109 Constraint Simulation Tool** (josefpelz): compute-shader spring/cloth sim on SOP geometry with PBR render. Non-commercial only.
11. **65070 Physarum clean tox** (ciphrd) and **64845 Complex UV Math toolkit** (function.store): slime-mould agent sim via instancing; complex-function UV warps/fractals.
12. **64094 TD-Faust** and **65624 ChucKDesigner** (David Braun): Faust DSP and ChucK live-coded audio inside TD; GPL-2.0; Windows and macOS build scripts in repos.
13. **64951 miniSEQ**, **65370 TapSync**, **64088 Keyframer**, **65034 keyFrameitor**, **65011 AnimBox**: sequencers, tap tempo, animationCOMP editors/cue systems for show control.
14. **65657 / 64950 / 65487 / 65154 / 65022 / 64131 / 63954 RayTK 0.12-0.20** (t3kt): raymarching toolkit with SDF palette, GLSL; 0.20 not compatible with experimental 30000 builds. Releases on GitHub (not downloaded here).
15. **75538 POPs vs SOPs**, **75551 New Timecode features**, **75562 AVY performance framework**, **64841 Media Server in TD** (workshop), **64073/64057/64054 live-visuals workshops**: current-era POPs/timecode, modular live framework (Patreon/polar paid), media-server pattern, live performance primers.
Also useful: 65353 Easy Optimization Tricks, 64122 Make Anything Audio Reactive, 65017 EDID simulation (Windows/NVIDIA), 65246 Boids compute shader (David Braun starters).

## Files downloaded (attachments: 34 posts, 54 files, 118.7 MB; clones: 7 repos, 71 MB). Nothing opened/run (toe/tox only listed by name)
Folder `research_src/community/files/<postid>/`. Licence "not stated" unless noted; builds not stated on pages (era 2021) unless noted.
- 65663 (9 files, 16 MB): Galaxy3D free placement.toe, RayTK volumetric sampling example (.toe, 5.3 MB), SDF depth approach (test.3.toe), TDintoMADRIX5Spout3Dvolumetric.toe, Dragon-O renderpatch (2 toes ~1 MB), EASY DEPTH SETUP.toe, 3Dvolumetric POPS.11.toe, Volumetric display in TOPS.zip (zip list: 2 .toe, Running kopie.fbx, 2 .tdc cache in TDImportCache).
- 65629 Tweener (7): Tweener_v1.3.4.tox, v1.3, TweenerUI.tox, 3 example .toe + easing examples.
- 65109 constraint_simulation.zip (10 MB; non-commercial): constraint_simulation_tool.toe, Simulation.tox, Houdini assets (.hclassic, .hiplc), dalleTexture.png.
- 65007 (89 MB): B2BK_AdvancedRendering_2023.toe, Stereolux03_SHARED_01.toe.
- 64793 PACK 02 zip (Kohui): Hexagon instancing.toe, Mouse light feedback.toe, TOP based instancing particle.toe, Read me.txt.
- Single tools: TapSync(+V2).tox 65370; miniSEQ.tox 64951; keyFrameitor_v1.1.tox 65034; recordMovie.5.tox 64788; MultiPlayalizer.tox 65097; PHYSARUM.tox 65070;
  TOPs-stacker CPU/GPU/GLSL + example 65168; OpenCV_Tracker.tox+example 65253 (needs build 2021.10330+); Country_flag.tox 65170; de-flicker 64889;
  interactionDisplay.tox 65107; NormalMap_TOPs.tox 65562; webRender.toe 65592; ReaRouteTD_MONO_1_4.tox (Gumroad post, attachment was free); twitterFilteredStream.tox 63953;
  TD_ParHelpTranslator 64009; Laser Cube LAN/WiFi toe 65251; srt_in_example_TD.toe 65038; Glitches free version.toe 64888; Alfred_ROOM.toe (Kinect V2) 64136;
  PAGE_MAG_Example.toe 64101; 2D vector fields 2 public.toe 65176; Spanish tutorial toes 64008/64029/64050/64067/64099/65194; matrix-cube-tutorial 65617.
- Git clones (depth 1; folder `files/<postid>/<repo>/`, commit):
  - 65624 DBraun/ChucKDesigner `2fb6addf`: GPL-2.0; ChucKDesigner.toe, src, Plugins, build_macos.sh/build_windows.bat, docs.
  - 64094 DBraun/TD-Faust `19802261`: GPL-2.0; TD-Faust.toe, SketchSynth.toe, toxes, faust2td.py, Plugins; latest needs TD 2023.11290+.
  - 65246 DBraun/TouchDesigner_Shared `0fc3a27a`: GPL-3.0; Starters (boids, Physarum, optical_flow_particles_compute, MediaPipeProjects, stippling, uv_math, NodeRender, web_scraping...), TOPs/SOPs/CHOPs/COMPs/DATs/MATs, Audio, Beat, Camera.
  - 65618 twistcube/touchdesigner `3910cb91`: no licence file; td_speech_to_text (py scripts 1-8, OSC), tunneltokyo_led.toe, vol011_audiovisual.toe, chromacky.toe.
  - 65430 Tech-Directors-Association/ZIGCAM_Samples `4b80e881`: MIT; Sample_TouchDesigner (NDI AR camera app samples).
  - 64818 djipco/webwelder `027f469f`: Apache-2.0; WebWelder.tox, Example.158.toe, www.
  - 64784 SudoMagicCode/SudoSignals `235b2cae`: no licence file; docs site (Docusaurus) only, no tox.
Note: other processes later created `expanded*/` folders inside several of my per-post folders (toeexpand output); I did not create or touch these.

## Recurring techniques / ops (counts from page text)
Python (30), feedback (27), instancing (23), GLSL (17), Kinect (16), OSC (14), MIDI (14), Ableton/TDAbleton (21), RayTK raymarching (10+), Nvidia RTX AR SDK (10), Perform mode (9),
extensions (8), Unreal/TouchEngine (7+3), NDI (6), Arduino (6), Notch (6), DMX/Art-Net (3), OpenCV (3), Kantan Mapper (3).
Patterns: compute-shader sims (cloth, boids, particles via GLSL TOP/SOP emitters), Replicator-free instancing from TOP data, Animation COMP as cue/keyframe engine,
point-cloud GLSL clipping, Texture 3D, Kinect skeleton visuals, Python pip/conda environments, WebSocket/JSON web UIs, Spout/NDI to Madrix/Resolume.

## Authors who post a lot
elburz (77, Interactive & Immersive HQ; mostly video stubs), elekktronaut (13, Bileam Tschepe; Patreon-linked tutorials), tekt (10, RayTK), isabelle (9, Derivative editorial/interviews),
Unveil_studio (9), noones_img (7, GLSL particles/Flex), internetbigboi (7, Spanish tutorials with toes), Kohui (5, Patreon packs), DavidBraun (3), igalabs (3, GitHub tools), narumin256 (TDSW streams).

## Windows-only / NVIDIA-only (heuristic from page text)
65625 + 65619 Kinect Azure displacement/point cloud; 65172 AR filters, 65161 + 64084 RTX face tracking, 65104 RTX denoising, 65078 RTX background removal, 65105 Nvidia Broadcast
(Nvidia AR SDK, RTX); 65033, 63905, 64136 Kinect V2/Azure; 65017 EDID emulation (Nvidia Quadro tool). Spout-based items (65663 Madrix) are Windows-side; on Mac use Syphon/NDI.
Mac: only TD-Faust and ChucKDesigner are explicitly stated/seen to support macOS. Everything else Mac status unknown.

## Paid / Patreon (recorded only, files not fetched)
75562 AVY (Patreon + polar.sh purchase link); 65562 Normal Map explanation (Patreon); 65176 Vector fields 2 (Patreon); 64888 Glitches full (Patreon, free version attached);
Kohui / notothetalkingball Patreon packs (65028, 64947, 64793, 64103, 64013); TDSW Patreon (64782, 64087, 64017, 63966, 63918, 63942); 65638 blankensmithing; rearoute... Gumroad (price not shown);
65064 sponsor/Patreon links. No prices shown on the pages.

## Skipped
- Leaks/rights: none found (one "crackled" false positive in 64062).
- 65571 VIDEO1.mp4 (21.6 MB, mp4 not an allowed type). RayTK GitHub releases (build-0.12..0.20) linked, not downloaded (release zips not fetched in this slice).
- 65153 yeataro/TD_KIWI repo (59 MB > 50 MB, clone removed); 65019 coreprinciple97/CompArt_Vol1 clone timed out (240 s).
- Non-tool repos linked (conda, YouCompleteMe, NVIDIA BROADCAST-AR-SDK, TouchEngine-UE4) not cloned.

## Open questions
- Events/workshops pages carry no date in the fields I parsed (73 blank); dates may be in the body text.
- Does GeoPix (64897) live at github.com/EnviralDesign/GeoPix? Page gives no link; worth a targeted fetch (high value for LED mapping).
- QFH HapQ Converter (65064) has no attachment on the page: is the tox on Patreon only? Same for Value_Matrix style items without files.
- Which Mac-compatible equivalents exist for Spout/Kinect Azure/RTX items (Syphon, NDI, Vision/Apple depth)?
- Data quality: summaries/ops/mac/licence in the jsonl are rule-extracted from the page text; relevance for ~170 stub tutorials is heuristic. Pages were not cross-checked against their videos.
