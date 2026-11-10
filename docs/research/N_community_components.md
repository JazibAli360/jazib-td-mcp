# N - Free community TouchDesigner components and projects: catalogue for PF26 (research, 16 Oct 2026)

Agent N for the lead. Target build **2025.31550**, `/Applications/TouchDesigner 2.app` (x86_64 under Rosetta, Pro), M1 Max, macOS. Research only: nothing was downloaded, installed or opened in TD. All facts were read from GitHub (API via `gh api`, README, LICENSE, releases) and derivative.ca pages on 16 Oct 2026.

Not repeated here (already catalogued): Palette (278 .tox) and OP Snippets (479) in `ops/PLATFORM.md`; the community VJ/preset/MIDI-mapping systems (TDXMorph, SimpleMixer, SonomikaTD, Black-Pomeranian VJ System, AAVJ, CuryCue, Presetter, TDMap, Cuelist Sequencer) in `H_control_panel.md` §2; MediaPipe plugin, CoreML Syphon Bridge, TDLidar in `D_camera_mediapipe.md`. Where one of those matters to a pick below it is cross-referenced, not re-researched.

How to read licence cells: the text is what the repo `LICENSE`/README or the post states. **"none stated" = all rights reserved by default = not usable without asking the author** (BRIEF rule). Licences marked NC (non-commercial) are treated as unusable for PF26 because it is a paid client event (this is a reading of the licence for the lead, not legal advice). GPL/AGPL are flagged because they attach conditions if the component is modified or redistributed; whether using one to render show output triggers anything is the lead's call.

---

## 1. Summary

1. **The free, clearly licensed, usable-now set is small and mostly GitHub-hosted.** The strongest: **RayTK** (CC BY 4.0), **DBraun/TouchDesigner_Shared** (GPL-3.0, mixed per-file), **FNSTools** (MIT), **OSCAR** (BSD-3-Clause), **touchFluid**, **TD-13TapBloom**, **Shader Park TD**, **ISF parser**, **exsstas TD-tutorials + Raymarching-in-TD** (all MIT).
2. **Most of the Derivative "Shared"/asset posts and Patreon free tiers state no licence at all** (Aristides.Lab, uisato, exsstas Camera Crane, percolated Oklab, Konstantin_I Fractal Glass, Spiraldiver FOP, elekktronaut files, Torin's Patreon helpers). Per the rule these need an email to the author before use. I could not retrieve Derivative's own terms for community uploads (`derivative.ca/terms-of-use` returned 404).
3. **Build gate:** many 2026 releases require a newer TD than ours: Voronoi POP, L-System POP, GSOPs need **2025.33070+**; FOP needs **2025.32460+**; Noisemaker for TD needs **2025.32820+ arm64-native**; TDPyEnvManager `autoSetup` needs 2025.32050+ and `pyproject.toml` storage 2025.32280+. **2025.31550 is below all of these.** RayTK 0.46 was built for 2025.30770 (older than ours, so expected to load; not tested live).
4. **Architecture gate:** TD 2.app is x86_64. Per `A_td_2025_howto.md` line 52, C++ plugins must be x86_64 (universal works). The Apple-Silicon-only native plugins found (EssentiaTD, Alaghast POPs) will **not** load in TD 2.app (inference from that rule; not tested). Pure `.tox`/GLSL/Python items have no such problem.
5. **NVIDIA-only items are out** (StreamDiffusion TOP, TouchDiffusion, TDDepthAnything, cuda-link, ComfyUI-TD route). **Windows-only items are out** (GeoPix, owlette, TDXComponents "(Windows)").
6. **Non-commercial licences found:** chainGpu (CC BY-NC-SA 4.0), Shadertoy-sourced shader collections (originals CC BY-NC-SA 3.0 unless stated), GSOPs Lite (non-commercial only). Not for PF26.
7. **Named creators:** Bileam Tschepe (elekktronaut) has **no GitHub repos** (`public_repos: 0`); his files sit on Patreon with free join but paid posts (one is $4); licence not stated anywhere I could read. Paketa12 and polyhop likewise have empty GitHub (0 / 1 repo) and Patreon pages that did not show tiers or file types to the fetcher. Matthew Ragan's public repos are MIT but mostly 2016-2021; the newest (hueControl) is Feb 2025. The Interactive & Immersive HQ GitHub is 2015-2018 era (one MIT: Stalker, Pixel-Packing).
8. **Not found / not verifiable** (web search budget ran out mid-research, WebFetch of some sites failed): Paketa12's actual free files, polyhop's free files, I&I HQ's current free downloads page, Olib (`td-olib.org`, SSL handshake failure), Josef Pelz's T3D details. All marked UNVERIFIED below.
9. **20 ranked picks** are in §4: the top ones are RayTK, TouchDesigner_Shared, FNSTools, OSCAR, touchFluid, 13TapBloom, Shader Park, ISF, exsstas files, MediaPipe (D), TDXMorph ControlMapper (H).

---

## 2. Catalogue table

Columns: Last update = latest push/release/post I could read. TD 31550 = compatibility with our build. Mac = macOS support (Apple-silicon-only noted). Q = quality/maturity judgement from stars, docs, activity (my reading). Class: **E** effect/visual, **I** interactivity/control/sensing, **W** workflow/utility.

### 2.1 Open-source on GitHub (licence readable)

| # | Name (author) | Class | What it does | Licence (exact) | Last update | TD 31550 | Mac | Q |
|---|---|---|---|---|---|---|---|---|
| 1 | **RayTK** (t3kt / Tommy Etkin) | E | Raymarching/SDF shader toolkit made of COMPs; 2D and 3D, lights, materials, post, volumes | CC BY 4.0 (`LICENSE.md` text; GitHub API reports NOASSERTION; README also says CC BY 4.0) | release 0.46 on 2025-08-26; last push 2026-02-04 | Release notes: "compatible with the TouchDesigner 2025.30770 experimental release, and is NOT compatible with the '2023' releases". 31550 not tested | Issue #1289: author "It should be supported"; says NVIDIA GPUs "typically perform better" and TD is not M3-specific | High (357 stars, docs site, snippets zip) |
| 2 | **TouchDesigner_Shared** (DBraun) | E/W | ~60 TOP .tox (kaleidoscope, bloom, turing pattern, pixel sort, optical flow, slit-scan, barrel-blur chroma, curl noise, dither, JFA), starters (Physarum, boids, stippling, optical-flow particles) | Repo: GPL-3.0. README: "files that I've modified from the Derivative forums". TOPs/README marks some third-party items "(No license specified)" and one "CC BY 4.0" | last push 2025-04-18 | build not stated; many files are 2018-2022 era; not tested | not stated | High (1038 stars), uneven per-file provenance |
| 3 | **FNSTools** (function-store / Dan Molnar) | W/I | Toolkit of 80+ installable packages: midiMapper, oscMapper, CustomParTools, CookBar (cook time + GPU memory per op), OpTemplates, autosave etc. | MIT (README); "Most tools are free and MIT licensed... Some unlock with a Patreon membership... not in this repository" | v2.11.2 release 2026-07-17; repo push 2026-10-14 | README: "Requires TouchDesigner 2025 or newer" (exact build floor not stated) | "Windows or macOS... Everything works except clipboard image paste" | High (297 stars, active) |
| 4 | **OSCAR** (trafalmejo) | I | Browser editor + server that builds touch GUIs (faders, XY, buttons, colour) and sends OSC from phone/tablet; README lists Resolume Arena, TouchDesigner, Ableton | BSD-3-Clause (GitHub API) | v2.1.0 on 2026-10-04 | TD side is plain OSC In; TD template exists (Derivative post 7 Oct 2026) | Installers for Mac Apple silicon and Mac Intel; or `npm start` (Node 18+); builds "aren't code signed" | Good (191 stars, very active) |
| 5 | **touchFluid** (kamindustries / Kurt Kaminski) | E | 2D semi-Lagrangian GLSL fluid solver: vorticity, temperature, buoyancy, obstacles; .tox + .toe | MIT | 2022-10-18 | build not stated; GLSL era pre-Vulkan (see §3 note) | not stated | Good (235 stars), old |
| 6 | **TD-13TapBloom** (EnviralDesign / Lucas Morgan) | E | High-quality bloom component | MIT | v1.0.0 2023-05-02 | not stated | not stated | Good (46 stars) |
| 7 | **shader-park-touchdesigner** (shader-park / Torin Blankensmith) | E | Renders Shader Park (JS raymarch sculpture language) in TD; drag-in .tox | MIT | v0.2.1 2024-08-12 | not stated | README: "tested on MacOS + Windows" | Good (152 stars) |
| 8 | **isf-touchdesigner** (marcinbiegun) | E | Parser component to run ISF shader generators/filters (the VJ shader format) inside TD | MIT (the parser; each ISF shader carries its own licence) | 2022-08-21 | README mentions fix for 2022.24200; not tested | not stated | Good (99 stars), old |
| 9 | **TD-tutorials** + **Raymarching-in-TD** (exsstas) | E | All project files of his YouTube tutorials (god rays, perfect loops, palettes, 2D raycaster, voxels, SDF particles) | MIT (both repos, GitHub API); "including ex-Patreon only" files | 2025-01-23 / 2024-08-04 | files date 2019-2024; not tested | not stated | High (155 / 88 stars) |
| 10 | **Noisemaker for TouchDesigner** (noisefactorllc) | E | 210 procedural effects (noise, fluids, physarum, reaction-diffusion, 3D volume) driven by a text DSL, built as GLSL TOP networks | MIT | push 2026-10-14; repo created 2026-06-21 | **Requires 2025.32820+ arm64-native macOS** (README); not our build | "Verified on Apple Silicon / Metal" (Apple M4); Windows/Intel unverified (GAP-014) | Young (1 star) but heavily tested (277/277 sweep cases) |
| 11 | **yeataro (Yea Chen) TOP filters**: TD_Voronoi, TD-ScreenSpaceFluid, TD-Anime4K, TD-MotionBlur, TD-Raymarching-System (WIP) | E | JFA Voronoi, screen-space fluid, upscale/denoise, motion blur, object-COMP raymarching | MIT each | 2020 / 2023 / 2019 / 2020 / 2024 | old builds; not tested | not stated | Medium |
| 12 | yeataro **TD-Flow-ABS**, **TD-Anisotropic-Kuwahara** | E | Painterly flow-based abstraction / Kuwahara filter | GPL-3.0 | 2023-04-16 | old; not tested | not stated | Medium |
| 13 | **BOS-in-TouchDesigner**, **glsl2dTuts-in-TouchDesigner** (raganmd / Matthew Ragan) | E | Book of Shaders examples ported to TD 099 | MIT (Ragan's repo). The Book of Shaders repo itself: LICENSE "All rights reserved" (Patricio Gonzalez Vivo) | 2023-09-27 / 2020-02-04 | TD 099 era | n/a | Teaching quality; do not copy shader text |
| 14 | **td-BrownianMotion** (REMvisual) | E | Script CHOP: Ornstein-Uhlenbeck mean-reverting smooth motion for camera drift/instances | MIT | v2.0.0 2026-04-01 | "Requires TouchDesigner 2025+" | not stated (pure Python) | Good (26 tests) |
| 15 | **td-CurveTool FREE** (REMvisual) | I/W | Bezier curve editor + LFO as CHOP, HTML-canvas UI via Web Render | MIT (free build; "Pro" is a separate paid product) | v2.0 2026-04-13 | "TouchDesigner 202.12370 ++" (typo in README; "2025+" under Install) | not stated | Young (0 stars) |
| 16 | **td-scope** (kamindustries) | E | Oscilloscope-style audio trigger/scope visual | MIT | 2022-06-16 | "Built with TouchDesigner 099" | n/a | Old |
| 17 | **Sndviz** (dylanroscover) | E/I | Audio analysis into TOP "modules" (low/mid/high, beat detection) | GPL-3.0 | 2023-07-20 | "TouchDesigner 2022.33910 (Windows)"; needs PyQt5 | README suggests Soundflower on Mac, but marked Windows | Medium |
| 18 | **TDXComponents** (dylanroscover) | W | chop_recorder, color_curves, comper, masker, playback, step_n_repeat, timecode, hexler, optimeister | GPL-3.0 | 2026-08-20 | Header: "TouchDesigner 2025.31550 (Windows)" - same build number as ours | Windows only on the header | Medium |
| 19 | **TauCeti** (PlusPlusOneGmbH) | I/W | Preset manager, cuelist, Tweener, preset-to-CHOP mapper | GPL-3.0 | v5.1.13 2026-04-02; push 2026-07-14 | build not stated | not stated | Medium (38 stars) |
| 20 | **TD-State-Machine** (InfoMusCP) | I/W | Table-driven finite state machine with timers, CHOP I/O, Python callbacks | MIT | 2026-03-10 | not stated | pure Python/DAT | Small (9 stars), clear docs |
| 21 | **Artio** (theexperiential) | W | Pixel-map / multi-display layout generator (guides, tiles, masks, export) | GPL-3.0 | 2025-11-24 | Header "TouchDesigner 2025.31620 (Windows)" | Windows on header | Medium |
| 22 | **Shadertoy ports**: exsstas/Shadertoy-TD-ports (GPL-3.0, 2019), dariopagliaricci/shadertoy-touchdesigner-examples (none, 2025-08-04) | E | Shader ports | Repo licences as listed; dariopagliaricci README: originals "CC BY-NC-SA 3.0... prohibits commercial use" | 2019 / 2025 | not tested | n/a | NC: not for PF26 |
| 23 | **td-glitch-effects** (FollowTheDarkside) | E | Glitch effect toxes | none stated | 2023-02-25 | not tested | n/a | Medium (66 stars) - ask |
| 24 | **yolo-touchdesigner** (torinmb) | I | YOLO26/YOLO11 detection, multi-person pose, segmentation, depth via a local web runtime over WebSocket | AGPL-3.0 (core `yolo.tox` + source); visualization helpers are Patreon-only | v0.0.2 2026-08-08; push 2026-10-06 | build not stated | not stated in README | Young; AGPL conditions spelled out by author |
| 25 | **EssentiaTD** (DarienBrito) | I | 5 C++ CHOPs for audio analysis (spectrum, mel, MFCC, pitch, onset/BPM, loudness) | AGPL-3.0 | v2.0.3 2026-09-16 | build not stated | "Windows (x64) & macOS (Apple Silicon)" only: **arm64 plugin, will not load in Rosetta TD 2.app** (inference) | Good (147 stars) |
| 26 | **L-System POP**, **Voronoi POP** (Alaghast / Edwin Lucchesi) | E | C++ POP operators (plants, 2D Voronoi) | Voronoi: MIT. L-System: README "proprietary freeware (see LICENSE)", LICENSE.txt in zip not read | 2026-09-04 / 2026-08-22 | **Both require 2025.33070+** | "macOS (Apple Silicon) or Windows" only | Young |
| 27 | **moebius-transformation** POP (from-vacuum) | E | GLSL POP applying 4D Moebius warps to 3D geometry | CC0-1.0 | 2026-06-10 | POP GLSL; build not stated | n/a | Small (6 stars) |
| 28 | **GeoPix** (EnviralDesign) | W | LED/DMX pixel-mapping and previz built in TD | MIT | v2.0.15534 (2024-02-22), TD 2021.16410 | no | Starts via a Windows `.bat` | n/a - skip |
| 29 | **chainGpu** (mickeyvanolst) | E | GPU chain/tentacle/hair physics | CC BY-NC-SA 4.0; "Please inquire for any commercial applications" | 2023-08-15 post | not stated | not stated | NC: not for PF26 |
| 30 | **UberGui** (EnviralDesign), **webWelder** (djipco), **td-web-gui** (torinmb), **WebRTC Remote Panel Web Demo** (Derivative org) | I | Web/WebRTC-based UI layers and 2-way web comms for TD | MIT / Apache-2.0 / NOASSERTION (tox on Patreon) / NOASSERTION | 2023-04-28 / 2021-12-03 / 2023-01-09 / 2023-12-14 | UberGui "TD 2021.12380"; others not stated | web-based, so browser-side Mac is fine; TD side untested | Old but simple |
| 31 | **TDNeuron** (tdneuron) | I | Deep-learning framework built from TD nodes | GPL-3.0 | 2020-03-31 | pre-2021 | n/a | Obsolete for our needs |
| 32 | **Stalker**, **Pixel-Packing-Examples** (interactiveimmersivehq) | W | Process watcher; pixel packing data transfer | MIT | 2017 | TD 088/099 | n/a | Old; 2018-era other I&I HQ toxes carry no licence |

### 2.2 Derivative asset/tutorial posts, Patreon and store items (licence usually not stated)

| # | Name (author, date) | Class | What | Licence / price as shown | TD 31550 | Mac | Q |
|---|---|---|---|---|---|---|---|
| 33 | **Motion Extraction free TOX** (Aristides.Lab, 26 Apr 2026) | E | One drop-in .tox: video differenced against a time-shifted copy; 300-frame cache default | "free TOX" tag; no licence stated; download via Patreon post | TD version not stated | tags list Windows and macOS | Good, simple |
| 34 | **WaveField TOX** (Aristides.Lab, 7 Jun 2026) | E | 17 wave equations displacing a point cloud, audio-reactive, custom-par driven | Price and licence not stated; Patreon + Buy-Me-a-Coffee links | not stated | "Mac & Windows Compatible" (post text) | Unknown |
| 35 | **Camera Crane** (exsstas, 12 Oct 2026) | W | Free orbit/arc camera component; Camera Crane Views manager is paid | "free component"; licence not stated; 14.2 KB .tox | not stated | not stated | Small |
| 36 | **Oklab TOX** (percolated, 17 Apr 2025) | E | LCh<->RGB .tox pair for perceptual colour | "free" tag; licence not stated; 2 files ~1.5 KB | not stated | not stated | Tiny, useful |
| 37 | **Fractal Glass** (Konstantin_I, 30 Sep 2026) | E | One 4.1 KB .toe: ramp-driven glass divisions + blur | price/licence not stated | not stated | not stated | Tiny |
| 38 | **FOP 3D/4D Fractal Operator System** (Spiraldiver, 28 Sep 2026) | E | Wire-together fractal operator family compiled to one raymarch shader | Patreon; price/licence not stated | **needs 2025.32460+** | "Windows 10/11 or macOS"; dedicated GPU | Not usable on 31550 |
| 39 | **Realtime Audioreactive Pointclouds v1.7**, **Oscilloscopes Everywhere v1.2**, **LongExposureFX**, **Kinetic Synth** (uisato, Apr-Oct 2026) | E | Kinect-style pointcloud+audio, 29 oscilloscope presets, temporal ghosting, MIDI polyrhythm instrument | Store `uisato.studio/tools` / Patreon; price and licence not stated (Oscilloscopes: "giving away one full copy" implies paid) | not stated | not stated | Showpieces; Kinect needs a depth camera |
| 40 | **GSOPs** (Lake Heckaman) | E | 3D Gaussian-splat operators | "Copyright 2025-2026 Lake Heckaman, all rights reserved... No redistribution"; Lite free non-commercial, full paid via Patreon | **needs 2025.33070+** | "tested on macOS (M3)" | Not usable |
| 41 | **SD TOP** (Unveil_studio, 8 Oct 2026) | E | Native StreamDiffusion operator | Paid (15 EUR per 6-month licence) | not stated | **NVIDIA Ampere/Ada/Blackwell only** | Out |
| 42 | **elekktronaut (Bileam Tschepe)**: Particle Collisions with Ray POP (24 Apr 2026), Psychedelic Flower (8 Feb 2025) | E | Tutorials; files (project file, Chromatic Aberration .tox) on Patreon | Patreon "Join for free" shown; a locked post costs $4; licence not stated on any page read | not stated | not stated | Excellent teaching, files gated |
| 43 | **Paketa12** (Aurelian Ionus) | E | Generative-design tutorials; Patreon + YouTube | Patreon page showed no tiers/files to the fetcher | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| 44 | **polyhop** (Simon Alexander-Adams) | E/I | Tutorials, daily generative sketches; GitHub `polyhop/engine` (0 stars, no licence, 2026-09-03) | Patreon: "strive to keep these videos freely accessible"; bonuses for supporters; file types not shown | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| 45 | **T3D operators** (Josef Pelz) | E | Operators Shader Park supports; Patreon, latest post locked | UNVERIFIED (price, licence, build) | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| 46 | **TDAbleton** (Derivative, Palette) | I | Live Set <-> TD over OSC/UDP: parameters, clips/tracks, tempo/beat, levels/spectrum, MIDI | Part of TD Palette; Max device licence not covered on the doc page | page: "TouchDesigner 2021.20k+"; Ableton Live 11.1.5+ | Mac mentioned (a "strange default limit on Mac OS" note) | Official |
| 47 | **TDPyEnvManager** (Derivative, Palette `tdPyEnvManager`) | W | Manage venv/Conda Python envs inside TD | Licence not stated on doc page; Conda mode silently installs Miniconda and accepts Anaconda ToS | `autoSetup` needs 2025.32050+, `pyproject.toml` context needs 2025.32280+ (above 31550); basic venv path not tied to a build | no macOS-specific requirement listed | Official; sideloading "at your own risk" |
| 48 | **Olib** (Wieland Hilker / AlphaMoonbase) | W | Free .tox marketplace, per FNSTools README ("the de-facto free TD .tox marketplace") | UNVERIFIED: `td-olib.org` fetch failed (SSL handshake) | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| 49 | **VJ Combining TouchDesigner and Resolume** (tekt, 13 Aug 2026) | I | Beginner video tutorial on mixing TD live into a VJ set | Post lists no files, no licence, no TD/OS, no transport named | n/a | n/a | Relevant topic; content is a YouTube video |

---

## 3. Per-item notes (only where a decision needs more than the table)

### RayTK (t3kt)
- Licence: `LICENSE.md` in the repo is the full CC BY 4.0 legal text; README ends with "RayTK by tekt (Tommy Etkin) is licensed under CC BY 4.0". Attribution needed. Source: https://github.com/t3kt/raytk ; licence text https://github.com/t3kt/raytk/blob/master/LICENSE.md
- Install: release `.tox` dragged into a project (docs). Releases: 0.46 (2025-08-26) with `RayTK-0.46.tox`; 0.45 and earlier also had `RayTKSnippets-*.zip`; 0.46 lists only the tox.
- Release 0.46 notes: "Threaded shader compilation" (the project keeps working while shaders compile; a second recompile still stalls), palette rebuilt for the new List COMP, new `imageSdf2d`. Operator categories per docs: Camera, Combine, Convert, Custom, Field, Filter, Function, Light, Material, Output, Pattern, Post, Sdf, Sdf2d, Time, Utility, Volume. https://t3kt.github.io/raytk/guide/getting-started/
- Mac: only the issue #1289 exchange (author: "It should be supported"; performance on NVIDIA better). Our GLSL runs through Vulkan/MoltenVK (`A_td_2025_howto.md` §4, T-10); RayTK builds GLSL at runtime, so compile behaviour on 430/460 under MoltenVK is the thing to test, not assume.
- Fit: B techniques 3, 10, 11 (raymarching, light beams, glass/dispersion) for hero moments.

### TouchDesigner_Shared (DBraun)
- Most useful TOP files by name: `GLSL_Kaleidoscope.tox`, `bloom_filter.tox`, `barrel_blur_chroma.tox` (third-party, "No license specified"), `feedback_HSV.tox`, `feedback_TOP_over.tox`, `SlitScanSimplest.tox`, `OpticalFlow.tox`, `turing_pattern.tox`, `Kuwahara_paint.tox`, `dither_style.tox`, `curl_noise_4D.tox`, `pixel_sorting.toe`, `jump_flood_algorithm.tox`, `palette_gen.tox`, `color_palette_*_trigonometric.tox`; Starters `Physarum`, `boids`, `optical_flow_particles_compute`, `stippling`; Beat `tap_tempo.tox`; Camera presets.
- Licence mix: repo GPL-3.0; README entries mark some items "(No license specified)" (barrel blur) or "CC BY 4.0" (BrushStrokes) or MIT-derived (depth of field from PixelFlow). Per-file check needed before using any one tox. https://github.com/DBraun/TouchDesigner_Shared (TOPs/README.md)
- Age: last push 2025-04-18; files predate 2025 TD; compatibility with 31550 untested.

### FNSTools (function-store)
- Install model: drop `FNSTools.tox` (empty), pulse "Pick Tools", it downloads chosen packages and verifies them against a release manifest (needs internet at that moment). 47 free tools and 24 Patreon-unlocked (as of v3.2.67 per README). https://github.com/function-store/FNSTools ; docs https://functionstore.tools
- Relevant free ones: CookBar (cook time and GPU memory per op - directly useful for fps budgeting), midiMapper/oscMapper (learn mode), CustomParTools, OpTemplates. The catalogue page itself did not render for the fetcher, so the free/locked split of individual tools is README-only.
- Release assets are named `FNS_TDDefault_2023.toe` / `FunctionStore_tools_2023.tox` (v2 line) while README text says v3 requires TD 2025+. Confirm the exact floor before installing (open question).

### OSCAR (trafalmejo)
- Flow: design a rack in the browser, publish, open the LAN address on a phone/tablet; each widget sends OSC to a chosen IP/port/address. Works with TD (OSC In) and Resolume Arena OSC directly, so one phone UI could drive both. https://github.com/trafalmejo/OSCAR ; Derivative post https://derivative.ca/community-post/asset/oscar-control-touchdesigner-your-phone-parameter-rack-type-tunnel-and-kaleido
- Post ships `oscar-type-tunnel.tox` and `oscar-kaleido-feedback.tox` (a caption-in-tunnel scene and a 3/6/12-mirror noise kaleidoscope); the .tox files' own licence is not stated on the post (repo is BSD-3). Caption text there is not a PRISM name source (names rule: never from TD).
- Risks: unsigned installers (right-click Open); phone-to-Mac needs same network and open firewall - venue Wi-Fi is an unmeasured risk. This is an alternative to the on-screen TD panel decided in `H_control_panel.md`, not a replacement; it sends OSC only.

### MediaPipe plugin, TDXMorph, MIDI mapping (cross-reference only)
- MediaPipe (torinmb, MIT, v0.6.0 2026-10-14): see `D_camera_mediapipe.md` §2 for build, Mac camera issues and cost.
- TDXMorph MIT parts (PresetManager, PresetSnap, ControlMapper) and its "built on 2025.33230" caveat: see `H_control_panel.md` §2. New alternative surfaced here: **TauCeti** (GPL-3.0) presets+cuelist+Tweener, and **TD-State-Machine** (MIT) for show-state logic. Neither mentions pickup or LED feedback.

### Noisemaker for TouchDesigner
- Strong content (210 effects incl. fluid, physarum, reaction-diffusion; text DSL; MIT), but README states "TouchDesigner 2025.32820 or later (arm64-native, macOS)" and the compatibility report matrix lists only 2025.32820 and 2025.33230 on Apple M4. It is **not tested on 31550 or under Rosetta**. The native `/Applications/TouchDesigner.app` is recorded in `PLATFORM.md` as arm64 2025.32820 with an unverified Non-Commercial licence: Non-Commercial caps resolution at 1280x1280, which is why the repo itself clamps 3D volumes. https://github.com/noisefactorllc/noisemaker-for-touchdesigner ; report https://github.com/noisefactorllc/noisemaker-for-touchdesigner/issues/5

### yolo-touchdesigner and EssentiaTD (AGPL)
- Both AGPL-3.0. yolo's README is explicit that closed-source commercial use "is not automatically cleared" and that custom ONNX models stay AGPL; the lead should decide before any use. EssentiaTD is native arm64 only. Audio analysis in TD 2.app can use built-in Audio Spectrum/Analyze CHOPs and `Audio Beat`-style logic (see `ops/CHOP.md`), so neither is needed.

### Items rejected with reason
- NVIDIA-only: SD TOP (StreamDiffusion), TouchDiffusion, TDDepthAnything, TDComfyUI route, forkni/cuda-link.
- Windows-only: GeoPix (`START_GEOPIX.bat`), owlette (README "platform: Windows", licence FSL-1.1-Apache-2.0), TDXComponents header, Sndviz header, Artio header.
- NC licence: chainGpu, Shadertoy collections, GSOPs Lite.
- Build too new: FOP, Voronoi POP, L-System POP, GSOPs, Noisemaker (see §1).
- Not an effect/interaction tool: Embody, touchdesigner-mcp and the other MCP servers (8beeeaaat, Pantani/tdmcp, TDPilot...) - relevant to `jazib-td-mcp` itself, not to PF26 visuals; not assessed.
- Text-weaving/typography toolkits (`weaving-type-touchdesigner`, `Scriber`, `TD_textEffects`): names must stay whole and never come from TD (names-words rule); numerals only. Not picked.

### GitHub topic search coverage
Topic `touchdesigner` pages 1-3 sorted by stars (items >= 8 stars) plus topics vj, glsl, shader, audio-reactive, generative-art, led, ndi, syphon, osc, midi, opencv, particles, feedback, pops were read (queries listed in Sources). Topic `tox` returned mostly the unrelated Tox messenger; `touchdesigner-tox` returned nothing.

---

## 4. Ranked picks for PF26 (20)

Ranking = usefulness to the PF26 techniques (`B_visual_techniques.md` §4, `DIRECTIONS.md` §3) x licence clarity x fit to our build. **Status** says what must happen before use. "Cleared" means licence is readable and permissive; it does not mean tested in 31550. Nothing here is downloaded.

| Rank | Pick | Why for PF26 | Status |
|---|---|---|---|
| 1 | **RayTK** (CC BY 4.0) | Raymarched dispersion/glass/light-beam hero moments (F01, F03, G01, takeover hits) without hand-writing GLSL | Cleared (attribution). Needs a lead go-ahead to download + a Metal/MoltenVK compile test on 31550 |
| 2 | **TouchDesigner_Shared TOPs** (GPL-3.0, mixed) | Ready TOP effects: kaleidoscope, bloom, HSV/over feedback, slit-scan, turing pattern, pixel sort, optical flow, palette generators - the E loop pack's building blocks | Licence per file; avoid items marked "No license specified"; GPL question for the lead |
| 3 | **FNSTools** (MIT) | CookBar (cook time and GPU memory per op) to keep looks inside the fps budget; midiMapper/oscMapper for later MIDImix/MPK mapping; CustomParTools for the panel | Cleared. Confirm exact TD floor of v3 first |
| 4 | **OSCAR** (BSD-3-Clause) | Phone/tablet control rack sending OSC to TD and to Arena; a hands-free fallback to the on-screen panel | Cleared. Network test at venue needed; unsigned app |
| 5 | **touchFluid** (MIT) | Smoke/ink/fluid base for E pack "liquid" looks and hand/motion impulses | Cleared. Old GLSL: test on GLSL 430 (T-10) |
| 6 | **TD-13TapBloom** (MIT) | Clean glow on spectrum beams and numerals | Cleared |
| 7 | **Shader Park TD** (MIT) | Raymarched sculptures from short JS; README says tested on macOS | Cleared. Needs a test; runs a web-based compiler step |
| 8 | **isf-touchdesigner** (MIT) + vetted ISF shaders | Opens the large ISF shader world used by VJs; each shader has its own licence, so choose per shader | Parser cleared; shader licences to check one by one |
| 9 | **exsstas TD-tutorials / Raymarching-in-TD** (MIT) | Working files for god rays, perfect loops, generative palettes, 2D raycaster lights | Cleared; old builds, port as needed |
| 10 | **MediaPipe plugin** (MIT, D) | Hand/face/pose/segmentation for the crowd/host interactive moments | Cleared; Mac camera path unproven (D open questions) |
| 11 | **TDXMorph ControlMapper / PresetManager** (MIT parts, H) | Preset + MIDI/OSC mapping on custom pars | Cleared for MIT parts; built on 2025.33230 (H) |
| 12 | **TD-State-Machine** (MIT) | Table-driven show-state logic (states, timers, CHOP outputs) for look switching | Cleared; small project |
| 13 | **td-BrownianMotion** (MIT) | Smooth organic drift for cameras and instanced fields (no jerky random) | Cleared; "TD 2025+" |
| 14 | **td-CurveTool FREE** (MIT) | Drawn envelopes for pulses/flare shapes; helps keep flashes within the flash limits | Cleared (free build) |
| 15 | **yeataro TD_Voronoi / TD-ScreenSpaceFluid / TD-MotionBlur** (MIT) | Small GLSL filters: shard/cell textures for F02 Facet Shatter, blobby fluid, trail blur | Cleared; old builds |
| 16 | **TauCeti** (GPL-3.0) | Alternative preset/cuelist/tween stack if TDXMorph proves too heavy | GPL question; build floor not read |
| 17 | **TDAbleton** (Palette) | Only if an Ableton Live rig exists (clip/tempo/level data) | Conditional on the music source; Live 11.1.5+ |
| 18 | **TDPyEnvManager** (Palette) | Isolated venv for helper libs; D recommends separate arm64 processes for ML anyway | Conditional; two features need builds newer than 31550 |
| 19 | **Aristides.Lab Motion Extraction (free TOX)** | Ghost-trail "motion extraction" look from camera or clip; macOS tagged | Licence not stated: ask the author first |
| 20 | **Noisemaker for TD** (MIT) | 210 ready procedural effects incl. physarum and reaction-diffusion | Blocked: needs 2025.32820+ arm64-native; only if the lead clears the native app and its licence tier |

Near misses: Oklab TOX (tiny, useful for perceptual brand gradients; licence not stated), Camera Crane (free, licence not stated), Fractal Glass (4 KB .toe, licence not stated), elekktronaut Chromatic Aberration .tox (Patreon, licence/price not stated; `td-port` already has an RGBSplit pilot).

---

## 5. Open questions for the lead

1. **Licence policy:** Are GPL-3.0 / AGPL-3.0 tools acceptable for show output (no redistribution of the .tox)? Attribution (CC BY 4.0, RayTK) is fine? NC items are excluded by my reading since PF26 is a paid client event - confirm.
2. **Ask-the-author list:** Do you want me to draft short permission emails (Aristides.Lab, exsstas, percolated, Konstantin_I, elekktronaut, FollowTheDarkside, DBraun for the unlicensed third-party files)? I did not contact anyone.
3. **Download go-ahead:** which of the ranked picks (suggest 1, 3, 4, 5, 6) may I fetch for a supervised compile/fps test in `/project1/_research_probe`-style scratch (BRIEF currently bans downloads)?
4. **Which TD binary is the show host?** Items 20 (Noisemaker) and the 2025.32820+/33070+ releases need the native arm64 app (recorded as Non-Commercial in `PLATFORM.md`, unverified). Do you want a licence check there, or stay on TD 2.app 31550 and accept this list is limited to older/pure-tox items?
5. **Native plugins:** confirm the rule "C++ plugins must be x86_64/universal for TD 2.app" by a harmless probe (e.g. check what a universal binary reports) before ever trying EssentiaTD / Alaghast POPs.
6. **Phone control:** is a phone/tablet control surface (OSCAR) wanted at all, given the decision for an on-screen panel + MIDI later and venue Wi-Fi uncertainty?
7. **FNSTools v3 floor:** exact minimum TD build not stated (only "2025 or newer"); also the free/locked split of individual tools could not be read because the catalogue page did not render for the fetcher.
8. **Unverified creators:** Paketa12, polyhop, I&I HQ's current free downloads, Olib, Josef Pelz (T3D). The session's web-search budget ran out, and Patreon pages did not render tiers/file types; a human look at those pages (or a later search) would close them.
9. **Derivative's terms for community uploads:** `derivative.ca/terms-of-use` returned 404; the correct URL for the site-wide terms on user-posted assets is still unknown. Until found, "licence not stated" stays "ask".

---

## 6. Sources

Searches via `gh api search/repositories` on 16 Oct 2026: `topic:touchdesigner` (pages 1-4, sorted by stars), `topic:touchdesigner-tox`, `topic:tox`, `topic:touchdesigner-components`, `topic:touchdesigner-plugin`, and `topic:touchdesigner` combined with `vj`, `glsl`, `shader`, `audio-reactive`, `generative-art`, `particles`, `led`, `ndi`, `syphon`, `osc`, `midi`, `opencv`, `feedback`, `pops`; keyword queries "touchdesigner shadertoy / bloom / glitch / kaleidoscope / fluid / audio analysis / ISF / pixel map / lasers / hand tracking / TDNeuron / T3D". Per-repo facts: `https://api.github.com/repos/<owner>/<repo>` (+ `/readme`, `/releases`, `/contents`, `/commits`, `/issues/N`) for each repo below.

GitHub repos (README/LICENSE/releases read):
- https://github.com/t3kt/raytk ; https://github.com/t3kt/raytk/releases/tag/build-046 ; https://github.com/t3kt/raytk/issues/1289 ; docs https://t3kt.github.io/raytk/guide/getting-started/ and https://t3kt.github.io/raytk/guide/troubleshooting/
- https://github.com/DBraun/TouchDesigner_Shared (and /TOPs, /Starters READMEs)
- https://github.com/function-store/FNSTools ; https://functionstore.tools/get/
- https://github.com/trafalmejo/OSCAR ; https://www.createwithoscar.com/
- https://github.com/kamindustries/touchFluid ; https://github.com/kamindustries/td-scope
- https://github.com/EnviralDesign/TD-13TapBloom ; https://github.com/EnviralDesign/GeoPix ; https://github.com/EnviralDesign/TD-UberGui
- https://github.com/shader-park/shader-park-touchdesigner
- https://github.com/marcinbiegun/isf-touchdesigner
- https://github.com/exsstas/TD-tutorials ; https://github.com/exsstas/Raymarching-in-TD ; https://github.com/exsstas/Shadertoy-TD-ports
- https://github.com/noisefactorllc/noisemaker-for-touchdesigner ; https://github.com/noisefactorllc/noisemaker-for-touchdesigner/issues/5
- https://github.com/yeataro/TD_Voronoi ; https://github.com/yeataro/TD-ScreenSpaceFluid ; https://github.com/yeataro/TD-Flow-ABS ; https://github.com/yeataro/TD-Raymarching-System ; https://github.com/yeataro/TD-POPs
- https://github.com/raganmd/BOS-in-TouchDesigner ; https://github.com/patriciogonzalezvivo/thebookofshaders ; user list https://github.com/raganmd?tab=repositories
- https://github.com/REMvisual/td-BrownianMotion ; https://github.com/REMvisual/td-CurveTool
- https://github.com/dylanroscover/Sndviz ; https://github.com/dylanroscover/TDXComponents
- https://github.com/PlusPlusOneGmbH/TauCeti ; https://github.com/InfoMusCP/TD-State-Machine ; https://github.com/theexperiential/Artio
- https://github.com/torinmb/yolo-touchdesigner ; https://github.com/torinmb/td-web-gui ; https://github.com/torinmb/mediapipe-touchdesigner (via D)
- https://github.com/DarienBrito/EssentiaTD ; https://github.com/Alaghast/L-System-POP ; https://github.com/Alaghast/Voronoi-POP ; https://github.com/from-vacuum/moebius-transformation
- https://github.com/tridant-io/owlette ; https://github.com/TouchDesigner/WebRTC-Remote-Panel-Web-Demo
- https://github.com/dariopagliaricci/shadertoy-touchdesigner-examples ; https://github.com/FollowTheDarkside/td-glitch-effects
- https://github.com/tdneuron/TDNeuron ; https://github.com/interactiveimmersivehq (user repo list) ; https://github.com/polyhop/engine ; https://github.com/lakeheck (user repo list) ; https://github.com/lakeheck/TouchDesigner-GSOPs-Docs ; https://github.com/elekktronaut (0 repos)

Derivative pages:
- Tag listings: https://derivative.ca/tags/pops , /tags/audio-reactive , /tags/glsl , /tags/vj , /tags/particles , /tags/tox , /tags/resolume , /tags/led , /tags/feedback , /tags/shader , /tags/free , /tags/interactive , /tags/asset ; https://derivative.ca/community
- Posts: https://derivative.ca/community-post/asset/oscar-control-touchdesigner-your-phone-parameter-rack-type-tunnel-and-kaleido ; https://derivative.ca/community-post/tutorial/motion-extraction-touchdesigner-%E2%80%94-free-tox/74476 ; https://derivative.ca/community-post/tutorial/wavefield-tox-pops-without-hassle/74758 ; https://derivative.ca/community-post/asset/release-realtime-audioreactive-pointclouds-v17-full-demo/75358 ; https://derivative.ca/community-post/asset/walkthrough-oscilloscopes-everywhere-v12-29-ways-draw-sound-touchdesigner/75459 ; https://derivative.ca/community-post/asset/release-longexposurefx-comp-experimental-temporal-ghosting-long-exposure ; https://derivative.ca/community-post/asset/release-kinetic-synth-instrument/75224 ; https://derivative.ca/community-post/asset/fractal-glass-effect-touchdesigner/75431 ; https://derivative.ca/community-post/asset/fop-3d4d-modular-fractal-operator-system/75417 ; https://derivative.ca/community-post/asset/camera-crane-touchdesigner/75485 ; https://derivative.ca/community-post/asset/l-system-pop/75292 ; https://derivative.ca/community-post/asset/voronoi-pop/74215 ; https://derivative.ca/community-post/asset/oklab-tox/71779 ; https://derivative.ca/community-post/asset/chaingpu-physics-simulation-tool/68172 ; https://derivative.ca/community-post/asset/sd-top-native-streamdiffusion-operator/75469 ; https://derivative.ca/community-post/tutorial/particle-collisions-ray-pop/74455 ; https://derivative.ca/community-post/tutorial/psychedelic-flower/71260 ; https://derivative.ca/community-post/tutorial/new-shader-park-plugin-touchdesigner-t3d-support/69938 ; https://derivative.ca/community-post/tutorial/vj-combining-touchdesigner-and-resolume/75184 ; https://derivative.ca/community-post/tutorial/make-viral-blob-tracking-effect-touchdesigner-free/74680
- Docs: https://docs.derivative.ca/TDAbleton ; https://docs.derivative.ca/Palette:tdPyEnvManager

Creator pages: https://www.patreon.com/elekktronaut ; https://elekktronaut.com (+ /projects, /tutorials: JS-rendered, no content) ; https://www.patreon.com/paketa12 ; https://www.patreon.com/polyhop ; https://www.patreon.com/JosefPelz ; https://matthewragan.com/ ; https://www.youtube.com/@paketa12 and /@elekktronaut (fetch showed navigation only).

Failed or empty (so UNVERIFIED): `https://td-olib.org/` and `https://www.td-olib.org/` (SSL handshake failure); `https://interactiveimmersive.io/free-resources/` (404); `https://www.patreon.com/tblankensmith` (404); `https://derivative.ca/terms-of-use` (404); `https://derivative.ca/community-posts?type=asset` (404); WebSearch quota exhausted partway (200 per session), so the Paketa12 / polyhop / TDNeuron / T3D / GSOPs searches were not run.

Project cross-references: `docs/research/BRIEF.md`, `README.md`, `ops/PLATFORM.md`, `H_control_panel.md`, `D_camera_mediapipe.md`, `A_td_2025_howto.md` (line 52: C++ plugins x86_64; §4 GLSL 430/460 via Vulkan), `B_visual_techniques.md`, `DIRECTIONS.md`.
