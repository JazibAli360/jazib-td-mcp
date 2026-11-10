# Popular TD: Reddit (r/TouchDesigner, r/vjing) - 26 Oct 2026

Data: `research_src/popular/reddit.jsonl` (90 lines: 85 threads + 5 derived tool/tutorial lines). Numbers dated **26 Oct 2026**.

## Method (and a deviation)
- Reddit's own `.json` endpoints return **403** to the crawler UA (retried once after 60 s; old.reddit `.json` and HTML
  return a bot wall). The **Atom `.rss` listings work**: `top.rss?t=all|year|month` and
  `search.rss?q=tox|tutorial|free|project file|how did you make&restrict_sr=1&sort=top` plus r/vjing `q=touchdesigner`
  (`how did you make` returned only 19 hits; r/vjing "touchdesigner tox" returned empty). 680 unique posts.
- RSS carries no scores, so **score and num_comments come from the Arctic Shift public archive** (`arctic-shift.photon-reddit.com`,
  no login) for those 680 ids, and comments from its `comments/search?link_id=`. Archive scores are snapshots: recent posts may
  be a little low; nothing was fetched from reddit.com except RSS.
- Rank = score + 5 x num_comments (threads with many comments carry the HOW). Top 60 on that, plus 25 extra posts whose title
  looks like a release/tutorial/free-tool. For all 85 I read the post and the top/OP comments for ops and links.
- Scores in this subreddit are low in absolute terms for older classics (e.g. bileam's beginner course = 92) because the sub grew.
  Top-all by raw score is dominated by 2025-26 showcase clips.
- Manners kept: 2 s spacing, 429 handled with waits, no login, all text treated as data.

## Top 30 (score / comments, composite rank)
1. **Running 2 machines for all live graphics, The International Dota 2** (1129/50, ScytheDota) - 2 TD machines, 4x 3840x2160,
   1426 m2 LED. Dota Game State Integration API -> custom parser -> webserver -> TD 1; TD 2 mirrors via Touch Out DAT.
   24 game events trigger grandMA3 light cues. Best "TD in production" reference.
2. **Plexus** (893/23, PERFECTLO0P) - Win95-look plexus in POPs, Render TOP 600x600 no AA, wireframe MAT, cube points.
   Thread links the MIT **Delaunay Triangulation POP** (downloaded).
3. **Projection mapping onto 13-layer plywood** (837/32, 4MC) - Katana mapper; Procreate Dreams animation as Movie File In;
   Ramp TOP -> Lookup TOP with absTime.seconds phase for colour scroll.
4. **Perspective tracking on 12 CRT wall** (841/21, ordinaireX) - Kinect head track, B2BK quad-reprojection, Resolume via Spout.
5. **3D generative visuals in Unreal controlled from TD** (582/66, TheVisualCast) - OSC from TD to Unreal (midi, TouchOSC,
   transforms), Resolume only for projector mapping, MADRIX for DMX; open issue is TD<->UE texture sharing latency.
6. **More practice** (594/57, EliaGud) - Add SOP -> Convert (particles per point) -> Point normals -> instancing; Phong MAT;
   high shadow resolution camera, small light. Replies point to GLSL-free tutorial NuIShUTg3nI.
7. **The Illusion of Depth** (604/20, io-av) - 2D noise-channel-driven geometry instances; optical illusion.
8. **X ray vision** (612/16) - hand-tracked reveal, no build detail.
9. **how i can achieve this?** (611/16) - answers: noise terrain + Dither/posterize TOPs + depth/displacement; likely AI source.
10. **Magnetosphere 2.0 update** (460/42, flight404 = Robert Hodgin) - 1M flocking particles, 60 fps RTX 4090; 95% GLSL compute;
    per-band audio listeners; beat detection learned from Bileam. First post (303/23, #52) says POPs + compute shaders.
11. **using TD to eat up worlds** (546/19) - Edge TOP inside Feedback loop (black, barely transparent) eats bright areas; Twirl in feedback.
12. **Mouth and hands control visuals and sound** (457/35) - MediaPipe fingertips -> lines; OSC In/Out CHOP to VCV Rack; Mac webcam.
13. **Hand/eye chrome POPs** (557/12) - POPs tutorial GJMIXo8pwSY + After Effects chrome.
14. **Case study of live-show setup** (404/42, krxzor) - Kinect clouds, realtime AI, Unreal; Intech Grid; audio analyzer at project
    root feeds every visual component; master file switches patches; 14900K + 4090.
15. **New here** (420/35) - DJ/visual set, no build info.
16. **Moving sands** (479/22) - 10M attractor particles in POPs; hard shadows quadrupled count; Patreon planned.
17. **Karleido (browser audio-reactive tool)** (109/96) - mostly a VJ-community debate, not TD.
18. **Prisms** (516/10) - author published a tutorial (youtu tZt1SQUZl6U).
19. **Looks like TD?** (485/14) - Python re-creation of a camera look.
20. **birb** (440/23) - particle text effect; project-file request unanswered.
21. **Kinect point cloud + free .toe** (475/15, sometimes-equable) - Google Drive .toe + demo video 9QIBTFaaYKo (downloaded).
22. **frenesi** (450/17) - full breakdown: Ramp LFO circles, Circle POP + Copy POP, Lookup per petal, keying, VHS filters.
23. **StreamDiffusion + POPs hand trails** (313/43) - Circle TOP per hand + Feedback; SD-Turbo 512x512; RTX 5070 Ti.
24. **Organic Growth** (420/21) - mini_uv pattern + sarv.vj ARE audio; circular ramp spawn.
25. **Evangelion music player** (376/28) - touchscreen UI (File DAT, Audio CHOP, Container/Slider COMP); sold on Patreon.
26. **A hero among men** (386/26) - image post, no detail.
27. **I finally have one to show** (404/22) - no detail.
28. **Audiovisual experiment** (379/24) - tutorial G4wyR-Nxyzo + Comp TOP (Negate) of pos Nulls driving instance scale; 0.6 alpha MAT.
29. **Kirby feedback paint flow** (426/14) - feedback network; thread about visual identity vs tutorial clones.
30. **Bad Apple in TD** (405/17) - ASCII/instancing (Polyhop tutorial), animated noise sampling.

Other high-value (lower composite): Perlin-style recipes in **"Help a sister out"** (186/17; top answer 74: Line SOP + 3D noise TOP ->
Math -> Null pos/rotate -> instance), **"Any idea how to recreate this effect"** (301/20; Cache TOP -> 3D texture -> instance rectangles,
Z uv by array index, 53 votes), **"how to make this"** (314/9; top answer 87: animated ramp + noise displace caustics + RGB offset),
**first commission visualizer** (304/22; particlesGPU + HSV Adjust x3 + audio Switch TOP), **mini_uv POPs extension** (166/12).

## What recurs
- **POPs** is the dominant new topic from Nov 2025 (22 of 85 threads): Copy POP, Circle POP, attractors, StreamDiffusion + POPs,
  Delaunay POP, mini_uv's POPs extension (popsextension.com). Sources: 2025 experimental builds referenced in "Help a sister out".
- **Feedback TOP** loops (22 threads), **instancing** (17), **noise** (21), render at low res no-AA then upscale (retro look).
- **Hardware inputs**: Kinect (7), Orbbec Femto Mega, MediaPipe (hand/face), RPLiDAR, IR touch frames, phone sensors (M2T, TDLidar).
- **Output chain**: Spout/Syphon/NDI to Resolume/MadMapper for mapping; CRT/LED walls; Ableton / MIDI / OSC / TouchOSC control.
- **Learning sources named**: elekktronaut/Bileam (beginner course, 6), Supermarket Salad (3), dcheesman (2), mini_uv (2), Polyhop, paketa12, pppanik007,
  B2BK reprojection. **Authors/tool makers**: uisato (6 posts, Patreon), sarv.vj/SARV7 (fluid, ARE), Josef Pelz (PCR), DotSimulate
  (StreamDiffusionTD), olegchomp (analog), ordinaireX, PERFECTLO0P (pops + feedback GIFs), BRINGIT303 (3D scans + PCR).
- Many shared tools sit behind **Patreon** (uisato, Zeuber, M2T, TouchFractal, ordinaireX, DecayingSun, DotSimulate): recorded only, not fetched.
- Culture: "give a tutorial link" pressure; attribution disputes (1tbh15d Chladni, 1mnmmrh resold StreamDiffusion file).

## Downloaded (all into `research_src/popular/reddit/`, never opened in TD)
- `delaunay-triangulation-pop/repo` - github.com/Alaghast/Delaunay-Triangulation-POP, **MIT**, commit
  `81cec354cae92a3fb805d693753b10e2ec70d9e1`; README + assets only (compiled POP plugin built from release; no tox in the clone).
  Features: 2D Delaunay from POP points or CHOP ref, Triangles/Edges output, async mode, attributes PrimCenter/Area/Circumcircle.
- `mediapipe-touchdesigner/repo` - github.com/torinmb/mediapipe-touchdesigner, **MIT**, 2839 stars, commit
  `bb01606926edeec828cc123e86a4a300bdc96c9b` (last commit 6 Oct 2026). Contains `MediaPipe.tox`, example toxes (face/hand/pose/
  segmentation/object tracking), `td_scripts/`, Vite/JS harness hosted in Chromium; **runs on Mac and PC**, 720p input limit.
- `kinect-pointcloud-toe/kinect_demo_creoanima.toe` - 13.8 KB free .toe from a Google Drive link (author creoanima; no licence
  stated; binary, contents not listed). Kinect support on Mac was reported broken by commenters.
- Not cloned: olegchomp/tdx-rnd (td-analog: NTSC, modulation, CRT, datamosh) - **no licence file/SPDX**, so recorded only.

## Windows / NVIDIA-only flags
- StreamDiffusionTD (DotSimulate, CUDA), Flowframes time remap, Magnetosphere-class compute (4090), td-analog (Windows; Mac users ask),
  Zeuber dither V1 (C++ TOP, Windows; V2 claims macOS), Spout (Windows only; Mac uses Syphon), Kinect v1/v2 (unsupported on Apple Silicon per thread),
  Orbbec. MediaPipe plugin, Syphon/NDI, Resolume, OSC, most TOP/SOP/POP tricks work on Mac.

## Gaps and open questions
- Raw reddit.com JSON blocked; Arctic Shift scores are archive snapshots. `t=year/month` lists were merged into candidates but not
  separately ranked. Search `how did you make` yielded only 19 posts.
- Patreon/Instagram/Gumroad payloads were not fetched. Whether Katana, PCR and sarv.vj tools run on Mac is unverified.
- Ask: is the user interested in POPs-heavy examples (need 2025 experimental builds; verify against TD 2025.31550 Mac/Rosetta)?
  Also whether to evaluate mini_uv POPs extension and MediaPipe tox in a sandbox later.
