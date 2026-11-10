# Community slice 04: derivative.ca/community?page=60..79 (scraped 26 Oct 2026)

Data: `research_src/community/slice_04.jsonl` (305 posts, one JSON line each, newest first, 2024-02-18 to 2026-10-24).
Listing pages 60-79 gave 305 unique links (pages 61-79 list 15 each, page 60 lists 20). All 305 post pages fetched, 0 failed
(one 504 on first try, retried OK). Relevance is scored 0-3 for general TouchDesigner mastery (any use case), not PF26 only.
Mac status is `unknown` for 293 posts: the site almost never states platform or TD build. Build stated in only 2 posts.

## Counts
Types: tutorial 106, post 65, asset 53, workshop 46, event 35, job 0. Relevance: 3 = 16, 2 = 63, 1 = 118, 0 = 108
(events and generic workshops are 0). Link-only posts are the norm: ~65% of tutorials/posts are an Interactive & Immersive HQ
(elburz) blurb that points to a YouTube video or an IIHQ blog page ("click here to continue"); the real content is off-site.

## Top 15 by relevance
1. **75562 AVY modular performance system** (elekktronaut, 2026-10-24). Lightweight live-performance framework: presets, MIDI map, FX, custom
   modules, audio analysis, OSC, Ableton Link, web UI. Patreon-gated download; walkthrough video only. Model for a show-control layer.
2. **70278 Intro to POPs** (IIHQ / Jack DiLaura video). POP data types (points, prims), instancing and render use, perf gains vs SOPs.
3. **75538 POPs vs SOPs** (IIHQ, 2026-10-21). Compares POPs and SOPs: performance, point-cloud workflow. Pair with 69864 (announcement) and 70271 (POPs FAQ).
4. **70528 Feedback with POPs** (IIHQ). Feedback POP setup, loops, example networks. Key for the new feedback-style looks.
5. **70497 Embody: Automate Externalization** (dylanroscover). Externalises a .toe into text/tox files for git and diffs. Repo is 54 MB (over cap, not
   cloned): https://github.com/dylanroscover/Embody . Directly useful to an MCP that edits projects.
6. **69333 New Timecode tools** (IIHQ video, TD 2023.11290) and **75551 Timecode CHOP + Python timed effects** (2026-10-23). Timecode CHOP params, timecode in
   operators, driving timed effects from video/audio timecode. Core show-control material.
7. **69336 Video Wall Mapping** (Sebby; downloaded `video wall map.toe`, 2.4 MB). Modified Geo COMP builds a pixel-accurate panel grid, mapped in 3D, textured from a
   camera, each screen laid out in its own pixel map for Novastar/disguise. Tags: novastar, disguise, pixelmapping. Strong LED-wall pattern.
8. **69617 Pixel mapping to DMX LEDs and lights** (dcheesman video) and **70319 LED strips with WLED** (IIHQ; ESP32 + WLED) and **70269 LED sculpture content
   pipeline** (2D image to LED). Pixel/DMX output methods.
9. **69401 TDWatchdog** (Vasily; repo cloned @f11b74d). Python watchdog server plus TD component: ping, error count, logging/status for installations. Windows `.bat` present.
10. **69043 Resolume vs TouchDesigner vs VVVV** (IIHQ). When to use which; context for TD to Resolume output decisions.
11. **69483 Uniforms in the GLSL TOP** (IIHQ). Feeding CHOP/Table DAT values into GLSL via uniforms; pair with 70852 (Chromatic Aberration GLSL snippet).
12. **70755 ComfyUI with TouchDesigner** (Scott Mann video) and **69062 TD + Omniverse USD stage for live performance** (Unveil_studio; Patreon).
13. **69316 PluginBuilder** (keithlostracco; MIT; cloned @65a56b2). Build/compile C++ plugins from inside TD via CMake + Ninja with hot reload. Windows-oriented.
14. **69669 BPM Sequencer TOX** (Artechs, free) and **69304/69980 iControl / iXR OSC+NDI** (fredfred, cloned). BPM counter/beat sequencing; OSC + NDI
    control from visionOS (example .toe files).
15. **69236 Mediapipe + Flex particle hands** (Skywalker.Visuals; torinmb/mediapipe-touchdesigner MIT, cloned) and **69551/69552 TD Depth Anything / TouchDiffusion**
    (olegchomp; TensorRT, NVIDIA only). AI hand tracking, depth, real-time SD.

## Files downloaded (details per post in the jsonl `files[]`; paths under `research_src/community/files/<postid>/`)
55 items in 40 post folders, about 251 MB total (by `du`; other agents also keep `expanded*`, `repo_*`, `release_*`, `unzipped` folders in these
post folders, those are not mine and not counted). Nothing was opened, run or loaded; zips were only listed with `zipfile`.
Build is not stated anywhere for these files. Licence is "not stated" unless noted.
- Repos (git clone --depth 1, commit in jsonl): shader-park-touchdesigner @1e6b9b9 (MIT; `Shader_Park_TD.tox`, 5 files), TDDepthAnything @7e15bbb (MIT; `.tox` + `accelerate_model.py` + `.bat`),
  PluginBuilder @65a56b2 (MIT, 1012 files incl. bundled Python headers), TopArray @6748746 (MIT; `TensorIO.tox`, CUDA tensors), mediapipe-touchdesigner @bb01606 (MIT; 108 files),
  FunctionStore_tools @dc6ae6d (MIT; VSCode/externalize tools, 606 files, 44 MB), TD-chainGpu-Physics-Sim-Tool @f3bed2b (CC BY-NC-SA 4.0; fbx/obj assets),
  TDWatchdog @f11b74d, TouchDiffusion @33dd7e8, TouchDesigner-X-Computer-Music @b46cde9 (synth `.toe`s; cloned twice for posts 69702 and 69924), iControl-OSC-NDI @c828c6b,
  iXR-OSC-NDI @a23c4af (visionOS, thesis `.toe` + obj).
- Single files: 69336 `video wall map.toe`; 69276 `Wallin_Pattern_Generator.tox` + examples `.toe` (1.9 MB); 69246 `video_sync_wheel.tox`; 69107 `GaussianSplatting-1.0.tox`;
  69051 `SequenceAnimator.tox`; 69211 `CHARACTER_ANIMATION` `.tox` + zips with fonts; 69888 nanoKontrol Studio MIDI map `.tox`; 69196 APC40 mkII widget `.toe` (4 MB);
  69473 `KINECT_STUDIO_V1_0.tox`; 70288 `cmyk.tox` halftone; 69725 infinity LFO `.tox`; 69695 `ClosestPalette.tox`; 69981 `wifiManager.tox`; 69506 web-control `.tox` x2;
  THETOUCHLAB utilities: TLCHAT 70847, TLVPN 70731 (zip, 115 entries), TLRADIO 70617, TLMOTION 70541, TDMAIL 70225, TLCUBE 69790 (4 files, 9 MB), TouchOut 69571, SONY FX9 control 69505,
  TLBOY 69744 (45.6 MB zip: bundled Python 3.11 + PyBoy, LGPL v3 per post); Unveil_studio 69958 (orto_particles.tox, PTZ_VISCA `.toe`, totem bubbles `.toe`);
  ETCH-01 tutorials 69328, 69296 (`.toe`); paketa12 69465 distance-function `.toe`.
- Not downloaded, over 50 MB or failed: UnveilStudio/SharedToxs_Unveil_Studio (216 MB; Patreon-adjacent shared toxes, referenced by 9 posts), dylanroscover/Embody (54 MB),
  CraftKontrol/Terrain-Tools (59 MB), ComfyUI (63 MB, not TD-specific), gwangyu-lee/iDepth-NDI (clone failed, likely gone), jhoepffner/SRT_reader (0.2 MB; clone raced with a
  duplicate run and was removed, post 69515, re-clone if wanted), t3kt/raytk (clone failed in the run; RayTK is a major library worth a dedicated slice).
  Readme `.txt` and `.jpg` attachments were skipped by extension rule.

## Recurring techniques and ops
- POPs (new Point Operator family, 5+ posts: announcement, FAQ, intro, vs SOPs, Feedback POP), Timecode CHOP (3), Bloom TOP feedback, instancing (primer + audio-reactive + GLSL instancing),
  GLSL TOP with uniforms, RayTK raymarching (tekt: 7 posts, SDF fields, kaleidoscope, noise patterns), particle systems in TOPs/GLSL (dcheesman), Kinect/depth point clouds,
  face/hand tracking (Mediapipe), OSC + NDI control, WebSocket to cables.gl, DMX/WLED pixel mapping, MIDI controller maps, externalisation/tox tooling.
- AI: StreamDiffusion (dotsimulate/olegchomp), ComfyUI, ONNX models via Script TOP, Depth Anything, Teachable Machine, Maxine.
- Top tags: python 12, ai 11, raytk 7, raymarching 6, particles 6, pops 5, instancing 5, osc 4, ndi 4, glsl 4, dmx 3, led 3.

## Authors who post a lot
elburz (Interactive & Immersive HQ) 63, dcheesman 22 (tutorials + paid "effect tool" Patreon), The_NODE_Institute 21 (workshops), isabelle (Derivative staff) 16,
pao.olea 12 (numbered tutorial series 01-11, 34), Unveil_studio 12 (Patreon series incl. "Python in TouchDesigner 0 to Hero" pt 1-4), THETOUCHLAB 10 (free utility .toes),
tekt 7 (RayTK), audiodevout 7 (Noise Sculpting series, Patreon files), elekktronaut 6, fredfred 5.

## Windows-only / NVIDIA-only (text or repo contents mention nvidia/cuda/tensorrt/.bat; unverified, 10 items)
69338 StreamDiffusion TD setup (NVIDIA), 69552 TouchDiffusion, 69551 TD Depth Anything (TensorRT), 69726 real-time Stable Diffusion, 69230 TopArray (CUDA), 70871 Flex/Bullet
solver (NVIDIA Flex), 70421 AI tools (Maxine), 69401 Watchdog (.bat), 69168 Body Tracking Orb, 69055 AI Upscaling. Mac confirmed `yes` only for TLBOY 69744 and TouchOut 69571 (post text).
PluginBuilder bundles Windows Python headers; treat as Windows-first.

## Paid / Patreon / store (recorded, not fetched): 29 posts
Unveil_studio (12; membership + per-post Patreon), audiodevout (Noise Sculpting parts 1,3,4,5; grid patterns; "noise between the lines" free tox but via Patreon file), dcheesman Vintage Lens
and Motion Tracer tools, uisato "Portals" (WarpFusion project files), 3710tomoya SoftyDMX, AuralEye CopyTOP, percolated palette tox, paketa12 Segment, alphamoonbase 69957,
Eusebi OSCToolset v2.0 (Gumroad), elekktronaut AVY (Patreon). Prices and tiers are not shown on the post pages.

## Skipped
No leak/crack/ripped items found in this range (keyword filter ran on all 305 posts; 0 matches). 3 repos skipped by size, see above.

## Open questions / notes for compile
- Crawler ran twice concurrently by mistake (a background launch survived my first, apparent, failure), so for roughly the first 30 minutes there were two requesters at 2 s
  spacing each. Records were de-duplicated by URL and merged (kept the version with downloads, unioned notes). No 429/403 was seen.
- Is the RayTK GitHub repo (t3kt/raytk) and the dotsimulate StreamDiffusionTD covered by another slice? Both recur here and are central.
- Build/OS requirements live inside the shared `.toe/.tox` files and READMEs. Nothing was opened here; a later pass (in a sandboxed TD, user go-ahead) could read the stored build.
- 108 posts score 0 (events, meetups, workshop listings): kept in the jsonl for completeness.
