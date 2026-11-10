# Most-viewed TouchDesigner videos on YouTube (key `youtube`, 26 Oct 2026)

Numbers are YouTube view counts read on **26 Oct 2026**. Full ranked list (62 rows, with ops, files, Mac flag, licence):
`../../../research_src/popular/youtube.jsonl`. Nothing was run or opened in TD.

## Method
- No API key. Search result pages (`/results?search_query=...&sp=CAM%3D`, sorted by view count; about 30 queries incl. beginner,
  audio reactive, particles, POPs, kinect, mediapipe, GLSL, AI, projection mapping, VJ, Resolume) and, for each channel,
  `/@handle/videos` then the **Popular** chip: its continuation token POSTed to `/youtubei/v1/browse` with the page's own
  public web key (3 pages = top ~90 per channel). Parsed from `ytInitialData`. 2 s sleep between requests, no login, no 429.
- Channel pages give **rounded** counts (e.g. 319K); the ranking uses the **exact** count from each video page's
  `ytInitialPlayerResponse` (`videoDetails.viewCount`, `shortDescription`, publish date).
- Candidate pool: 1,172 TD-titled or TD-channel videos; top 62 non-showcase videos kept (cut-off 101,401 views). Shorts/art
  reels excluded from the ranking (Audio Curtain 295K, Genuary brutalism 246K, Aha water 155K, RmaN OSC 128K, Alvie Starr 113K).
- **Transcripts: not reachable.** The caption `timedtext` URLs in the player response return an empty body without a PO token.
  Ops listed as "(inf)" in the jsonl are inferred from title and description; chapters/descriptions were read, videos were not watched.
- Channel ids: Matthew Ragan UCKAAKTI2xLNNBJRkdf8E58A, PPPANIK UCWBbakpo_cATqJy9Dzf9x4w, Torin UC4X3gD_Z_cOZNJOZ2IhV3ug.

## Top 30 by views (all 62 in the jsonl)
| # | Views | Posted | Author - title (min) | Notes |
|---|---|---|---|---|
| 1 | 417,641 | 2024-06 | Okamirufu Vizualizer - What is TouchDesigner (6) | Pure explainer, funnel to paid packs. |
| 2 | 376,686 | 2018-02 | Derivative - Intro to TouchDesigner, Ben Voigt (232) | Official 4-hour workshop, workflow and concepts. |
| 3 | 319,131 | 2020-06 | bileam tschepe - 00 Introduction, Beginner Course (8) | Opens a 20+ part free course; glossary link. |
| 4 | 318,612 | 2021-09 | Interactive & Immersive HQ - 00 Intro, Beginner Crash Course (1) | Course funnel (iihq.tv); downloads need trial. |
| 5 | 295,246 | 2020-01 | Derivative - 3D Projection Mapping Workflow, Richard Burns (207) | Needs a projector; GitHub files have no licence. |
| 6 | 275,694 | 2021-04 | bileam - Make Anything Audio Reactive, Tips 12 (32) | Audio/MIDI/TDAbleton/Beat CHOP into any sketch. |
| 7 | 226,402 | 2023-12 | PPPANIK - Blob Track Instancing (audioreactive) (68) | Blob Track TOP drives instancing; Patreon. |
| 8 | 225,708 | 2022-01 | Acrylicode - Absolute Beginner, zero to hero (130) | 2h10 course in one video. |
| 9 | 223,489 | 2023-09 | supermarket sallad - Pointclouds without lidar (14) | Render to pointcloud, feedback, particles; chaptered. |
| 10 | 218,257 | 2023-03 | Acrylicode - Audio-reactive psychedelic visuals (19) | Beginner audio-reactive. |
| 11 | 212,973 | 2021-02 | bileam - Interactive Particles, Kinect (26) | Kinect v2 + Optical Flow + particlesGPU (Windows). |
| 12 | 211,861 | 2020-06 | bileam - 01 About TouchDesigner (7) | Concepts, use cases, showcase. |
| 13 | 211,736 | 2023-08 | Function Store - Interactive Particles, particlesGpu (32) | Webcam/Kinect into particlesGPU; toolbar on GitHub (MIT). |
| 14 | 200,300 | 2025-05 | Xtal - pixelate (12) | Noise + Threshold + Feedback + Beat CHOP pixel look. Newest video in the top 20. |
| 15 | 192,484 | 2024-11 | nicholaspjm - Trace and Blob Tracking (20) | Blob Track + text overlay; free file behind Patreon login. |
| 16 | 190,335 | 2021-09 | Acrylicode - Beginner Tutorial 1 (6) | First-steps. |
| 17 | 187,112 | 2019-09 | bileam - Audioreactive Particle Cloud 10 (16) | Old particlesGPU; remade as tutorial 65 (#52). |
| 18 | 181,557 | 2023-09 | Torin Blankensmith - Free Motion Tracking plugin (29) | **MediaPipe plugin, MIT, Mac+PC. Cloned.** |
| 19 | 180,591 | 2020-05 | Noto The Talking Ball - spectrum shape via feedback (7) | Feedback-driven spectrum art. |
| 20 | 172,725 | 2019-07 | bileam - Audio Wheel, Tutorial 1 (18) | A whole song as one circular image. |
| 21 | 170,200 | 2024-02 | supermarket sallad - Exploding Star (15) | Particles constrained to a sphere. |
| 22 | 169,237 | 2024-04 | Daniel Steenhoff - Realtime White Visuals (6) | Edge TOP + feedback, tiny network. |
| 23 | 166,011 | 2021-09 | Interactive & Immersive HQ - 01 Get Started (7) | Install and downloads. |
| 24 | 162,793 | 2025-02 | Torin - Hand Tracking Master Class 1 (17) | MediaPipe hand data, smoothing, clamp component. |
| 25 | 162,036 | 2023-10 | eclipsys - particlewave (15) | Audio-reactive particle wave. |
| 26 | 160,189 | 2019-08 | bileam - Particle Displacement 7 (11) | Feedback, composite, blur, displace on particles. |
| 27 | 159,567 | 2024-06 | Dean Cheesman - Trace and Blob Tracking Effect (18) | Same look as #15, earlier. |
| 28 | 156,326 | 2023-12 | PPPANIK - Image/Video to Particles (35) | Merry-crisis special. |
| 29 | 155,931 | 2025-06 | Xtal - Blob Track (38) | Interior of the blob, not just outline. |
| 30 | 155,070 | 2023-10 | supermarket sallad - Custom Interactive 3D Particle System (28) | Particles without particlesGPU; feedback grid. |

Ranks 31-62 (jsonl): Exporting quick tip (bileam 151K), Acrylicode audio-reactive (149K), DeRe fluffy noise (144K), Deconstructing
Sculptures (141K), **StreamDiffusionTD (dotsimulate 139K, Windows+NVIDIA)**, **Collages (bileam 138K, DBraun repo, cloned)**, Aurora
Spectrum (135K), Derivative complex-systems workshop (134K, reaction-diffusion), Sonic Flowers x StableDiffusion (131K), Pixel Sorting
(128K), PPPANIK data-graph (126K), Controlling Video With Audio, Line MAT, Crash Course 02/03, Collapsing Noise, Interface, Dancing
Lights, Audio Histogram, Torin audio-reactive (114K), FBX into particles, Kinect TOP 2016, particle cloud (new), Particle Paths,
watercolour, Pseudo-Plexus, Motion Visualisation, wispy pointclouds, Abstract 3D Sculpture, Fluid Simulation (103K), Ragan 2015 class
(103K), noones img point-file instancing (101K).

## Channels (rounded counts, sum of each channel's top-90 popular uploads)
| Channel | Top video | Sum of top-90 views | Videos in the 100K+ pool |
|---|---|---|---|
| bileam tschepe (elekktronaut) | 319K | 6.9M | 19 |
| Interactive & Immersive HQ | 318K | 3.6M | 4 |
| PPPANIK | 226K | 2.5M | 4 |
| Derivative (official) | 377K | 2.1M | 3 |
| supermarket sallad | 223K | 1.7M (37 videos) | 7 |
| Acrylicode | 225K | 1.7M | 4 |
| Okamirufu Vizualizer | 417K | 1.6M | 1 |
| Torin Blankensmith | 182K | 1.1M (35) | 4 |
| noones img | 101K | 0.87M (31) | 0 (1 at 101K) |
| Matthew Ragan | 102K | 1.2M (older, 2013-17) | 0 |
| Paketa12 | 36K | 0.66M | 0 |
| dotsimulate | 139K | 0.29M (17) | 1 |
Paketa12 is a 2026-active POP channel (collisions, L-systems, tree structures) with small view counts; poor on views, rich on current POP technique.
Elekktronaut's newest (26 Oct): "Manipulating TOPs with POPs, Tutorial 80" (11 d ago), "Trace POP, Tutorial 79" (4 mo), and a modular performance system walkthrough (AVY, 1 d ago): fresh but only ~9K views each so far.

## What recurs
- **Beginner funnels dominate the very top** (explainers, "Beginner Course", "Crash Course"): ranks 1-4, 8, 12, 16, 23 are orientation, not technique.
- **Audio reactive** is the biggest technique theme: Audio Spectrum/Analyze/Beat CHOP into TOPs/instancing (#6, 10, 19, 20, 25 and about 12 more).
- **Particles**: particlesGPU palette component (#11, 13, 17, 26) then hand-built feedback-grid particle systems (supermarket sallad, #9, 21, 30).
- **Point clouds / instancing** (#9, 28, noones img, sallad, nicholaspjm) and **feedback/displace** (#22, 26, pixel sorting, fluid).
- **Tracking**: blob track / Trace (#7, 15, 27, 29), Kinect (Windows), MediaPipe (#18, 24 - the one Mac-safe path).
- **AI**: StreamDiffusionTD and SD-API (both GPU-bound, Windows/NVIDIA or slow).
- Authors keep project files on **Patreon** (bileam, PPPANIK, sallad, Acrylicode, Xtal, Daniel Steenhoff, Function Store, nicholaspjm);
  only a few link free GitHub (Torin, DBraun, Function Store, Richard Burns).
- Newest big movers (2024-25) are Xtal's reactive-effect shorts-style tutorials and Torin's hand tracking; **no POP tutorial is in the top 62**
  (POP videos are 2025-26 and mostly under 30K views, see `../V_tutorials_visual_craft.md`).

## Downloaded (all under `research_src/popular/youtube/`; not opened in TD)
- `torinmb_mediapipe-touchdesigner/repo` - MIT, commit bb01606926edeec828cc123e86a4a300bdc96c9b, 13 MB. Contains `MediaPipe TouchDesigner.toe`,
  `segmentation_demo.toe`, 16 files in `toxes/` (face_detector, face_tracking, hand_tracking(2), image_classification, face_mapping/filter/3D
  examples, build_release), `td_scripts/`, `src/` + vite web app (the detection runs in a WebView/browser page). Linked by #18 and #24.
- `dbraun_TouchDesigner_Shared/repo` - GPL-3.0, commit 0fc3a27afa970dc642aae46e38422ba30622ead3, 11 MB. 107 `.tox` + 30 `.toe`: TOPs
  (bloom, dither, depth of field, curl noise 4D, barrel blur, bitonic sort), Starters (boids, Physarum, stippling, Hilbert curve, moebius,
  optical-flow particles, MediaPipeProjects), Audio, Beat (tap tempo), CHOPs/COMPs/DATs/MATs/SOPs/Utilities. Linked by #36 (Collages).
- Not downloaded: Function Store tools (MIT but 1.3 GB), Richard Burns projection repo (no licence), all Patreon/Gumroad files (paid, record only).

## Windows/NVIDIA or hardware flags
- StreamDiffusionTD (#35): Windows + NVIDIA CUDA, TD 2023 only (stated in the description).
- Kinect v2 / Kinect TOP videos (#11, #51), Optical Flow TOP, Nvidia Background TOP (#36, #56 option): Windows or hardware-bound (T-18).
- Stable Diffusion API tutorial (#39): the A1111 server needs a GPU; the TD side is fine on Mac.
- MediaPipe plugin: states "works on Mac and PC with no installation" (Torin, video #18). Verify under Rosetta on 2025.31550 before relying on it.
- Projection mapping workshops need a physical projector to verify.

## Gaps
- Channel-page counts are rounded to 2-3 digits; only the 62 ranked videos have exact counts. Channels beyond the 90-video popular window
  (I&I HQ has hundreds, Derivative has more workshop recordings) may hide a few 100K+ videos at ranks 80-200 of their own list.
- Not scanned beyond search hits: uisato, anya maryina, Ab_out, threedashes, CutMod, Crazy Radio, SimpleTD, NAM Project.
  Xtal's channel page had no Popular chip (few uploads): taken from search only.
- Matthew Ragan's newer videos (POPs course) are not on the main YouTube channel scan; his count is for the old channel uploads.
- No transcripts; "ops (inf)" entries are inference. No likes/comment counts (not in the fetched JSON).
- Shorts and showcase reels excluded from the tutorial ranking (listed above).
- Search with sp=CAM gives only the first page (about 20) per query; deeper pagination was not used.

## Open questions
- Does the MediaPipe plugin run on 2025.31550 under Rosetta/Vulkan (WebView/CEF dependency)? Worth a gated test through the MCP.
- Which Xtal/Daniel Steenhoff free networks (feedback + Edge + Beat CHOP) can be rebuilt from the descriptions alone, since the
  files are Patreon-only? Candidate for a recipe file.
- Check DBraun's `Starters/` (boids, Physarum, stippling) for the general-purpose MCP library; license is GPL-3.0, so read-only reference.
