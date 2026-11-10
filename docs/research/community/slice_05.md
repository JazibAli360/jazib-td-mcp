# Community scrape, slice 05 (listing pages 80-99), 26 Oct 2026

Data: `research_src/community/slice_05.jsonl` (301 lines, one per post). Crawled 26 Oct 2026 with the BRIEF manners (2 s between
requests, no login, 0 failures, 0 rate limits). Relevance is scored 0-3 for general TouchDesigner mastery (scope update from the lead).
**Summaries are the post's own first sentences (auto-trimmed), not re-written; `notes` hold my judgement for ~130 posts.**
Build/licence/mac are recorded only where the post says so; `mac: unknown` is the common case.

## Counts
- 301 posts from 20 listing pages (pages return 19-20 links; duplicates removed). Dates 2023-02-01 to 2026-10-24 (not sorted, see questions).
- By type: tutorial 93, post 80, asset 49, workshop 47, event 29, other 3 (open calls). No jobs.
- By relevance: 3 = 17, 2 = 111, 1 = 135, 0 = 38. Posts with a downloadable/gated file: 41; 36 files + 4 repos downloaded by me.

## Top 15 by relevance
1. **68832 iTRAP / Banana API** (CorbinWhite): dependency-free tox serving a REST API (port 29980, Swagger on 8000) for operators,
   parameters, ID maps and NAPs. Direct prior art for remote control like jazib-td. Repo cloned (has LICENSE, type not read).
2. **68568 RANDoFRAMo** (anodin): maps video onto randomly placed LEDs; writes a 32-bit EXR with one row per DMX universe; Art-Net out. 170 KB tox.
3. **68940 Optical flow warp loop** (aulerius): iterative Optical Flow TOP warp in a feedback loop plus Blender scene input; 3 MB toe + blog guide.
4. **68815 PosiStageNet Sender CHOP** (Tyrell/VYV): PSN protocol so lighting consoles/media servers track performers. No file on the page.
5. **67702 CuryCue** (netzzy): generic cue-list sequencer COMP (presets, lighting cues) with docs and video; repo has a licence file.
6. **68350 FunctionStore_tools** (function.store): free workflow toolkit (default-par op placement, swap positions, promote custom pars,
   toolbar section, global components). Repo cloned (44 MB).
7. **67490 Shadertoy2TD** (devart.space): Shadertoy URL to TD network (iTime, iResolution, iMouse, buffers, textures, webcam); post mentions a business licence.
8. **68278 MediaPipe GPU plugin** (Torin Blankensmith): face, hand, pose, object tracking, GPU accelerated, **Mac and PC, no install**. No file on the page.
9. **68125 Body-tracking plugin** (Torin Blankensmith): webcam-only body tracking, Mac and PC, no Kinect.
10. **68166 External files in 2023.10k** (JetXS, Derivative): "Enable External .tox" replaces Re-Init Network, relative external paths. Affects tox sharing.
11. **68688 2023 Official update** (Derivative): OAK-D / Femto devices, Python, parameter and external-file workflow changes. Build-era reference.
12. **67533 PiCompositor** (pitheorem): layer-based compositing COMP (drop TOPs in as layers). Zip holds PiCompositor.tox + Example tox; repo cloned.
13. **67726 13 Tap Bloom** (lucasm/EnviralDesign): high-quality bloom component; repo cloned (has LICENSE).
14. **75562 AVY** (elekktronaut): modular live/VJ framework (presets, MIDI map, fx, OSC, Ableton Link, web UI), built with AI help;
    **paid key** + Patreon alpha. Newest post in the slice (24 Oct 2026).
15. **67874 State Circuits** (Coelepinda): native operator network for state-flow backbones (statful_container.tox, 39 KB).
Also 3: 67175 Simple Preset System (zip), 67220 UI-modification tutorial (Bookmark Bar mute/volume via Python).

## Files downloaded (derivative.ca attachments, my copies; all free, no login, listing only, nothing opened)
Under `research_src/community/files/<postid>/`. **25 of these post folders already existed** (made by other slices, incl. `expanded/` dirs);
same-named files were re-downloaded over them (same size), space-named duplicates of their underscore copies were deleted by hash.
Only 68508, 68466, 68457, 67967 were new folders. Builds are not stated on any attachment page; licences are not stated unless noted.
- 69023 six SUPERMORPH/SKYMORPH `.toe` (13-150 KB): sliders, AV, Leap Motion, LPD8, APC40 variants.
- 68972 two Blob Track `.toe` (20 KB, Nvidia Background TOP); 68964 Hue_Slider_0.tox; 68947 CRT_Filter.tox (GLSL); 68904 _TUNEL_TD_.toe (Shadertoy-derived).
- 68940 optical flow warp `.toe` (3.1 MB); 68820 yfx-HappyNewYear.tox (compute shaders); 68668 unwrapper2.tox; 68631 Promoter.tox;
  68568 RANDoFRAMo_231113.tox; 68508 TELEPROMPTER_V1.toe; 68466 UnrwrappedGeo2.tox; 68457 UnwrappedGeo1.tox (8.1 MB); 68425 Audio spectrum TOP.toe.
- 67967 Yin & Yang_0.toe; 67874 statful_container.tox; 67849 randomCHOP1.tox; 67796 WaveTOP.1.0.tox; 67794 AUDIO_MIX.tox; 67793 ZONE_TRACKING.tox;
  67792 FPC_LOCATION_CONTROL.tox; 67779 FPC_INPUT.tox; 67784 WaterFall.toe; 67744 grabWindow.toe; 67490 shadertoy2TD.tox;
  67470 PoissonFill.tox + PoissonFillExample.toe; 67235 fish_wiggle.toe.
- 67533 PiCompositor_v0.1.zip (376 KB): lists `PiCompositor.tox`, `PiCompositor_Example.tox`.
- 67175 Presets_0.zip (135 KB): lists `Presets/preset_component.tox`, `presets.tox`, 2 template `.toe`, `data/presets/preset3..9.txt`, `Backup/`.
- Total mine: 36 files, 14.0 MB.
GitHub clones (`git clone --depth 1`, dir `repo_<owner>__<name>`, commit in the jsonl):
- My clones: 68351 TD-SuperDirt `24d2cee` (0.2 MB; README + `TD+SuperDirt`), 67195 TD-Assimp `8b71d4f` (24 MB; C++ SOP source, VS/Xcode projects,
  `TD_Assimp.tox`, LICENSE), 68194 BlackMagicCamera-Touchdesigner-ESP32 `565352a` (10.5 MB; USB driver for Mac, TD project, LICENSE),
  68350 functionStore_tools `dc6ae6d` (44.5 MB; FNS_CMS, modules, scripts, tests, LICENSE). Total 79 MB.
- Already cloned by other slices, reused (not counted): 68939 OpenAI-API `ae64162`, 68832 iTRAP `c646b69`, 68561 duarte-amorim `9744629`,
  67726 13-tap-bloom `06cd1cf`, 67702 CuryCue `2b29535`, 67636 NAPs `54cc775`, 67533 PiCompositor `5fceda0`, 67447 iTAT `c31e7d0`.
  **68784 hekuli/touchdesigner-public is 87 MB, over the 50 MB cap (someone else's clone; lead may want to trim it).**
- Not kept: 68549 Overstim-Sim (clone passed 344 MB; aborted, deleted). Licence types were not read (only "LICENSE file present").
- Not downloaded by rule: 68153 Python_Code.txt (.txt not allowed), 67726 two comparison images, 67355 69 MB mp4, all Patreon/Gumroad items.

## Recurring techniques and ops
- **RayTK** (tekt, 15 posts): tutorials (flower grid, folding box, warped grid/hexagons, tentacles, nested shapes, fractal column) and release
  notes 0.30/0.33/0.35; performance series; volumetric LED workshop. Strong lead for SDF/volumetric LED content.
- **particlesGPU + Cache TOP trails + feedback**, optical flow, point clouds/instancing (Jack DiLaura, Crystal Jow via Interactive & Immersive HQ).
- **POPs** (new Oct 2026 posts): 75535 POP trail build, 75538 POPs vs SOPs. Timecode CHOP (75551). These match the build we run.
- **Integrations**: TDBitwig/TDAbleton (7+6 posts), Unreal via OSC/DMX/API/TouchEngine, MQTT, Stream Deck MIDI, SuperDirt OSC, PosiStageNet.
- **LED/DMX/laser**: Art-Net and DMX in 10 posts, lasers (Laser Device CHOP for ShowNET/Helios/EtherDream, 68339), pixel-map workshops.
- **AI**: Stable Diffusion/StreamDiffusion/ComfyUI, OpenAI via `pip install openai` + Python module path, MediaPipe plugins (Mac-friendly).
- **Workflow/show tools**: NAPs, FunctionStore_tools, Promote, UI Theme presets, preset systems, state circuits, CuryCue, TD Trebuchet.
- **TD as Game Engine** series (invisiblesignal, 11 posts) with 6 reusable tox files (input, camera, zones, audio mix).
- NODE Institute SS23 curriculum (MXZEHN, 15 module pages 4/2023-7/2023): syllabus pages on projection mapping, DMX/Art-Net, show sequencing,
  GLSL, RayTK, audio reactivity, web APIs, lasers, Arduino. Titles only, no files.

## Authors who post a lot
elburz (73; Interactive & Immersive HQ teasers, full text lives on interactiveimmersive.io and was NOT fetched), tekt (16), MXZEHN (15),
isabelle (13, Derivative editorial), invisiblesignal (11), Unveil_studio (10, Patreon-gated GLSL/unwrapping), 3dwalker (8),
elekktronaut/blankensmithing/blndtpe/chicmonster/function.store (6 each).

## Windows-only / NVIDIA-only / platform notes
- Windows+NVIDIA: 68875 Body Track CHOP, 68019 NVIDIA Flex, 67784 NVIDIA Flow waterfall, 68893 Omniverse link (RTX; Mac/AMD unsupported),
  68972 Nvidia Background TOP (rest of the toe unknown), 68987 StreamDiffusion tox (CUDA oriented, my inference).
- Windows-only: 67744 NDICapture.exe window grab, 67447 iTAT Telegraf agent, 67593 TD Trebuchet (Mac version "in development"),
  Kinect v2/Azure sensors (68502, 67513); grandMA2 onPC (68806).
- Explicitly Mac-OK: 68278, 68125, 67158 (Stable Diffusion, no big GPU), 68939 (macOS pip steps), 68688 (OAK cameras), 68543 TDBitwig demo, 68194.
- Paid/gated: 75562 AVY (key via polar.sh, alpha on Patreon), 69030/68036 TD Scripts Blender add-on (Patreon), 67593 Trebuchet (Gumroad $15),
  Unveil_studio and b2bk project files (Patreon), 67355 gamepad tool (Gumroad), 68901 designer.tox (Patreon, free).

## Skipped
- No leak/crack/rights posts in this slice.
- Overstim-Sim repo (size), items above. Teaser-only posts (about 60 elburz pages) record the teaser text and outbound link only.

## Open questions
- The listing is not strictly chronological: Oct 2026 posts (75535-75562) appear on page 80 next to Feb 2024 posts, and other slices had already
  downloaded 25 of my posts' files, so slice ranges overlap or the listing shifted mid-crawl. De-duplicate by post id when merging.
- `tags` on many posts look author-wide, not post-specific (e.g. every elburz post carries "Python, Spout, blob tracking").
- Relevance 1/2 for the ~110 posts I did not annotate individually is a keyword heuristic; only 3-scored and annotated posts are hand-judged.
- Builds are rarely stated (68939 says 2023.11340); none of the files was opened, so the build inside each tox/toe is unknown.
- Does the lead want 68784's 87 MB clone reduced to fit the 50 MB rule? Should interactiveimmersive.io full articles (73 elburz posts) be crawled?
