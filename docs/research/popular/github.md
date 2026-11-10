# Popular on GitHub (agent `github`, 26 Oct 2026)

Part of the "what the TD world uses most" sweep (`BRIEF.md`). Data: `research_src/popular/github.jsonl` (100 lines, one per repo).
Numbers (stars, forks, pushed date) were read from the GitHub API on **26 Oct 2026**; stars move daily.

## Method
- `gh api search/repositories`, sort=stars, 100 per page x 3 pages, for 10 queries: `topic:touchdesigner`, `topic:touch-designer`,
  `touchdesigner in:name,description`, `touchdesigner in:readme`, `topic:td`, `language:GLSL touchdesigner`, `tox in:name,description touchdesigner`,
  `topic:derivative touchdesigner`, `touchdesigner mcp`, `topic:touchdesigner-python`. 1243 hits -> de-duplicated -> **711** repos whose name,
  description or topics name TouchDesigner / .tox / Derivative -> top **100 by stars** ranked (cut-off: 52 stars). 2 s sleep between calls, no 403/429.
- For all 100: git tree (counts of .tox/.toe/.py/.glsl, size) and licence endpoint. READMEs read for the top 45 (head 6 KB each).
- Cloned (depth 1, no submodules, LFS off, hooks off) 15 repos with a stated free licence that ship .tox/.toe/Python. Nothing run, loaded or opened in TD.
- Rank = stars (forks and push date in the jsonl). `relevance` 0-3 is my judgement for general TD mastery and for this MCP.
- Not done: `search/code` (a .tox is binary, not searchable). Repos that never say "TouchDesigner" in name/description/topics are missed (e.g. a repo called only "tdport").

## Top 30 by stars
Columns: stars (forks), last push, licence, what it is, build/Mac.

1. **torinmb/mediapipe-touchdesigner** - 2839 stars (134 forks), push 2026-10-14, MIT. [rel 3]  
   GPU-accelerated MediaPipe plugin: hand/face/pose/object/segmentation/gesture tracking, self-contained, no install; sample toxes for face filter, face mapping, hand tracking. Build: README: 2023.10k+ external-tox note; exact floor not stated. Mac: README: "runs on Mac and PC with no installation".
2. **DBraun/TouchDesigner_Shared** - 1042 stars (135 forks), push 2025-04-18, GPL-3.0. [rel 3]  
   Largest free .tox grab-bag (107 tox, 30 toe): TOP effects, starters (physarum, boids), CHOPs, SOPs, MATs, audio, beat, camera, utilities. Build: varies per file, 2018-2022 era. Mac: not stated.
3. **8beeeaaat/touchdesigner-mcp** - 602 stars (65 forks), push 2026-10-12, MIT. [rel 3]  
   MCP server (npm) + TD .tox: create/modify/delete nodes, query project, run Python via WebServer DAT. Closest peer to jazib-td. Build: not stated in README (version handshake on API, not TD build). Mac: Node + TD; platform-neutral.
4. **interactiveimmersivehq/Introduction-to-touchdesigner** - 576 stars (80 forks), push 2024-02-06, CC (README mentions Creative Commons; no LICENSE file; read before reuse). [rel 2]  
   Elburz Sadeghi "Introduction to TouchDesigner 088" open manual with 136 .toe example files; foreword by Greg Hermanovic. Build: TD 088 (very old). Mac: n/a (examples).
5. **EnviralDesign/GeoPix** - 407 stars (34 forks), push 2026-02-27, MIT. [rel 1]  
   Free LED/DMX pixel-mapping and previz suite built in TD (strips, DMX, video surfaces). Build: TD 2021.16410 (stated). Mac: starts via Windows .bat; no Mac claim.
6. **raganmd/TD-Examples** - 397 stars (59 forks), push 2018-03-18, none stated. [rel 2]  
   Matthew Ragan + Ian Shelanskey + Barakooda: 198 tox / 77 toe example library with video write-ups; full courses and discrete answers. Build: TD 099-era (2018 last push). Mac: n/a.
7. **t3kt/raytk** - 357 stars (21 forks), push 2026-02-04, CC BY 4.0 (LICENSE.md; API NOASSERTION). [rel 3]  
   KNOWN (N): raymarching/SDF toolkit, 1191 tox. Ranked only. Build: 2025.30770 experimental. Mac: NVIDIA faster; supported per author.
8. **olegchomp/TouchDiffusion** - 301 stars (14 forks), push 2024-07-12, none stated. [rel 0]  
   Real-time Stable Diffusion via StreamDiffusion inside TD. Benchmarks table (4090 55-60 FPS). Build: 2023-24 era. Mac: NVIDIA/CUDA + Windows .bat -> NOT usable on our Mac.
9. **function-store/FNSTools** - 297 stars (5 forks), push 2026-10-26, MIT. [rel 3]  
   KNOWN (N): 80+ installable workflow packages. Ranked only. Build: 2025+. Mac: Windows+macOS.
10. **olegchomp/TDComfyUI** - 284 stars (14 forks), push 2025-01-09, none stated. [rel 1]  
   TD front-end for the ComfyUI API: drop workflow JSON in a Text DAT, generate; image send/receive over base64 nodes. Build: not stated. Mac: needs a running ComfyUI (own host); no GPU lock in TD side.
11. **Richard-Burns/SimpleMixer** - 266 stars (23 forks), push 2026-05-29, Unlicense. [rel 2]  
   Four-bank VJ video mixer built entirely in TD; loads clips and .tox as sources; post FX; 41 tox. Build: tested 2023.12000. Mac: not stated.
12. **chungbwc/TouchDesigner** - 264 stars (29 forks), push 2026-05-20, none stated. [rel 2]  
   HKBU teaching repo (Kin Wah Chung): 59 toe tutorials on Script TOP/CHOP with OpenCV, MediaPipe, Python libraries. Build: 2021-2026 mixed. Mac: not stated.
13. **kamindustries/touchFluid** - 237 stars (22 forks), push 2022-10-18, MIT. [rel 3]  
   KNOWN (N): 2D semi-Lagrangian fluid. Ranked only. Build: pre-Vulkan GLSL. Mac: not stated.
14. **TouchDesigner/TouchEngine-UE** - 224 stars (13 forks), push 2026-03-02, NOASSERTION (LICENSE file present; read before use). [rel 0]  
   Official Derivative plugin to run TD components inside Unreal Engine 5.7. Build: TouchEngine 2025.31760+. Mac: Windows UE; paid TD licence needed.
15. **dylanroscover/Embody** - 209 stars (10 forks), push 2026-10-25, MIT. [rel 3]  
   Second MCP peer: "Envoy" embedded MCP server with 70 tools + TDXN (networks as readable YAML), per-project .venv, externalisation, tagger, portable tox export. Build: **Requires TD 2025.33230+** (above our 31550). Mac: Windows + macOS.
16. **DarienBrito/TDXMorph** - 201 stars (11 forks), push 2026-10-09, MIT. [rel 3]  
   Preset/morph/cue toolbox v4 (PresetManager, PresetSnap, ControlMapper, ListView, JSONTree, PresetInspector); JSON presets. Build: not stated (v4 public beta). Mac: not stated.
17. **TouchDesigner/GenerativeDesign** - 196 stars (15 forks), push 2019-05-31, none stated. [rel 1]  
   Official Derivative port of examples from the book Generative Design: 90 tox. Build: 2019. Mac: n/a; no licence file.
18. **raganmd/BOS-in-TouchDesigner** - 196 stars (12 forks), push 2023-09-27, MIT. [rel 2]  
   Book of Shaders examples ported to TD; 75 GLSL files. Build: TD 099. Mac: n/a; shader text belongs to Book of Shaders authors.
19. **monkeymonk/awesome-touchdesigner** - 194 stars (11 forks), push 2026-02-25, none stated. [rel 2]  
   Curated awesome-list: tutorials, channels, plugins, assets, VJing, community. Build: n/a. Mac: n/a.
20. **trafalmejo/OSCAR** - 192 stars (8 forks), push 2026-10-24, BSD-3-Clause. [rel 2]  
   KNOWN (N): browser OSC GUI editor. Ranked only. Build: TD side plain OSC In. Mac: Mac arm64+Intel installers.
21. **exsstas/StyleTransfer-in-TD** - 189 stars (20 forks), push 2018-09-18, none stated. [rel 0]  
   Neural style transfer with TensorFlow 1.4 driven from TD. Build: TD 2018 era. Mac: Windows + CUDA setup.
22. **olegchomp/TDDepthAnything** - 188 stars (12 forks), push 2026-10-24, MIT. [rel 0]  
   Depth Anything v1/v2 TensorRT depth in TD. Build: 2023.11340. Mac: NVIDIA/Windows (.bat) -> not usable on Mac.
23. **raganmd/touchdesigner-sop-to-svg** - 185 stars (17 forks), push 2021-08-05, MIT. [rel 2]  
   SOP geometry to SVG pipeline for plotters/laser cutters; svgwrite lib. Build: TD 099. Mac: Python lib path differs on Mac, documented.
24. **olegchomp/TDDiffusionAPI** - 183 stars (7 forks), push 2023-10-17, none stated. [rel 1]  
   TD interface for AUTOMATIC1111 API: img2img, multi-ControlNet, inpaint, stream mode. Build: not stated. Mac: needs A1111 host.
25. **IntentDev/Luminosity** - 168 stars (25 forks), push 2025-01-11, GPL-3.0. [rel 1]  
   Operator front-end/perform GUI for realtime media (GPLv3), TD 099 era 2020.22080. Build: 2020.22080+. Mac: not stated.
26. **JiSenHua/ComfyUI-TD** - 168 stars (8 forks), push 2026-08-20, AGPL-3.0. [rel 1]  
   ComfyUI custom node streaming images/video/PLY point clouds/audio to TD over WebSocket via ComfyUI2TD.tox. Build: ComfyUI2TD tox v5.1.x. Mac: not stated.
27. **yeataro/TD_KIWI** - 166 stars (17 forks), push 2022-03-03, NOASSERTION (LICENSE file present; read before use). [rel 1]  
   Yea Chen experimental projects archive: 42 toe, 16 tox, 2413 py (mostly a Python env). Build: 2022. Mac: n/a; NO licence stated.
28. **picturesbyrobots/td-completes-me** - 162 stars (7 forks), push 2023-03-04, none stated. [rel 2]  
   Language-server tox + VS Code extension giving TD-aware autocompletion (op names, par names, channel names). Build: TD 2022-era. Mac: not stated; no licence stated.
29. **tdneuron/TDNeuron** - 158 stars (13 forks), push 2020-03-31, GPL-3.0. [rel 1]  
   Educational deep-learning framework built in TD ops (visual modelling). Build: 2020. Mac: not stated.
30. **raganmd/learningGLSL** - 156 stars (9 forks), push 2019-09-22, MIT. [rel 2]  
   GLSL for TD 099 tutorials (Ragan, Houze, Walczyk): 73 tox. Build: TD 099. Mac: n/a.

## What recurs
- **Three kinds dominate the star table**: (1) ML/vision bridges (MediaPipe 2839 stars, then TouchDiffusion, TDComfyUI, TDDepthAnything, ComfyUI-TD, YOLO, appletd); (2) example/teaching repos (Ragan, exsstas, Introduction to TouchDesigner 088 book, chungbwc, Derivative's GenerativeDesign); (3) tool/workflow components (FNSTools, TDXMorph, SimpleMixer, UberGui, TDFam, okVJ).
- **MCP-for-TD is now a crowded niche** and is all 2026: 8beeeaaat/touchdesigner-mcp (602 stars), dylanroscover/Embody "Envoy" (209 stars, 70 tools), satoruhiga/claude-touchdesigner (128), bottobot (80), Pantani/tdmcp (55), and **Derivative's own TouchDesigner/TDMCP (62 stars, beta, 21 Oct 2026)**. Shared design: a component inside TD plus an HTTP/WebSocket bridge; Python exec, create/wire/set-par, read errors, layout, docs lookup; Claude Code skills. See "Open questions" for what to compare with jazib-td.
- **Authors**: Matthew Ragan (raganmd: 7 repos in the 100, MIT, mostly 099-era), olegchomp (4, ML bridges, mostly no licence, NVIDIA/Windows), yeataro (6, mixed licences, many none), DBraun (5, audio/ML/C++), Richard-Burns (3, Unlicense/MIT), exsstas (3, MIT), satoruhiga (3), dylanroscover (2), torinmb (2, MediaPipe/YOLO), the official `TouchDesigner` org (6: TouchEngine, CustomOperatorSamples, GenerativeDesign, TDMCP).
- **Techniques recurring in the repos I read**: Web Render TOP as an engine (MediaPipe JS, UberGui, Shader Park, okVJ UI); GLSL TOP/MAT generation (ShaderBuilder, RayTK); Python extensions + custom pars (TDXMorph, TDFam, FNSTools); sidecar processes with shared memory (appletd, TouchDiffusion, ComfyUI) because heavy ML does not live inside TD's Python; JSON/YAML-readable networks (Embody TDXN, TDXMorph presets).
- **Licences**: MIT dominates (37 of 100). GPL-3.0 (TouchDesigner_Shared, Luminosity, TDXComponents, Artio, yeataro filters), AGPL-3.0 (EssentiaTD, yolo-touchdesigner, ComfyUI-TD), CC BY-NC-SA (chainGpu) restrict reuse. 23 of the 100 have **no licence stated** (plus 14 NOASSERTION custom/unrecognised texts) = all rights reserved: not copied.

## Downloaded (15, all in `research_src/popular/github/<name>/`, depth 1, commit hashes in the jsonl)
| Repo | Licence | Inside (from file listing) |
|---|---|---|
| mediapipe-touchdesigner | MIT | 16 tox (MediaPipe.tox, face/hand/pose/object/segmentation/classification detectors, examples), 2 toe, Vite/TS `src/`, `td_scripts/`, 27 py |
| TouchDesigner_Shared | GPL-3.0 | 107 tox + 30 toe in Audio, Beat, Camera, CHOPs, COMPs, DATs, MATs, SOPs, Starters, TOPs, Utilities |
| touchdesigner-mcp | MIT | TS MCP server `src/`, `td/` Python modules, 1 tox, docs, tests, Dockerfile, plugin/ and mcpb/ packaging |
| SimpleMixer | Unlicense | simplemixer.toe, Lib, Assets, 41 tox (about 27 MB of tox) |
| Embody | MIT | 12 tox, 4 toe, 361 py, docs (mkdocs), CLAUDE.md/AGENTS.md, `platform/` (web app), `specimens/` |
| TDXMorph | MIT | PresetManager, PresetSnap, ControlMapper, ListView, JSONTree, PresetInspector (6 tox), docs |
| BOS-in-TouchDesigner | MIT | 10 tox, 1 toe, 75 GLSL files (Book of Shaders ports; the shader text is Patricio Gonzalez Vivo's: study, do not copy) |
| learningGLSL | MIT | 73 tox (small GLSL lessons), 3 toe |
| TD-tutorials (exsstas) | MIT | 32 toe + 3 tox: trails, vertex shaders, god rays, complex functions, loops |
| shader-park-touchdesigner | MIT | 1 tox |
| TouchDesigner-ShaderBuilder | MIT | ShaderBuilder.tox, example.toe, `src/`, `tool/` |
| TDFam | Apache-2.0 | opfam-create_dev.toe, 9 tox, 30 py modules, docs, examples |
| appletd | MIT | appletd.tox + .toe, pyobjc sidecar `appletd/` python, docs, design, examples |
| TD-UberGui | MIT | UGV4.tox, V4 release toe, css/javascript/python for the Chromium UI layer |
| touchdesigner-save-external | MIT | 6 tox, Python helper |

Not cloned: GeoPix (tree about 56 MB, over the 50 MB cap; Windows .bat), yasuhirohoshino PostEffects (51 MB; MIT, worth a later look: bloom/SSAO/SSR/DoF), mir-lab instancing examples (140 MB), TouchDiffusion/TDDepthAnything/FlexCHOP (NVIDIA), all no-licence repos, Derivative's TDMCP (custom licence), RayTK/FNSTools/OSCAR/touchFluid (known).

## Windows / NVIDIA / build gates (our TD is 2025.31550, Rosetta TD 2.app, macOS)
- **NVIDIA/CUDA only, skip**: TouchDiffusion, TDDepthAnything (TensorRT), FlexCHOP, PyTorchTOP (CUDA OpenCV), TD-OpenCV3TOP, StyleTransfer-in-TD (TF 1.4 + CUDA).
- **Windows only**: GeoPix (.bat), TouchEngine-Windows, TDXComponents and Artio (headers say Windows), chainGpu (tested Windows, NC), TouchDesigner-Linux (Wine, Linux).
- **Needs a newer TD than ours**: **Embody needs 2025.33230+; Derivative TDMCP needs 2025.33230+** (ours 31550). Both are the best MCP peers and cannot be run on our build as-is.
- **Apple Silicon native only** (arm64 plugin vs our x86_64 Rosetta TD 2.app; inference, untested): EssentiaTD. appletd is a Python sidecar (separate process), so Rosetta TD plus a native arm64 Python 3.11 may work; untested.
- **Pure tox/GLSL/Python, no gate expected**: mediapipe-touchdesigner (README says Mac + PC), TouchDesigner_Shared, SimpleMixer, TDXMorph, TD-UberGui (needs Web Render TOP, Chromium), ShaderBuilder, shader-park (README: tested macOS), exsstas files.

## Gaps
- 711 candidate repos, only top 100 ranked; the long tail (<52 stars) has many useful one-offs (e.g. td-BrownianMotion, TD-13TapBloom, TD-State-Machine from `N_community_components.md`).
- READMEs were read for the top 45 only; ranks 46-100 carry the GitHub description, not a reading. Repo `.tox` contents were listed, never opened (binary).
- Stars measure age as much as use: the 2026 MCP repos are young; 2016-2019 example repos are old and 099-era (many ops/params since renamed). Downloads (release counts) were not collected.
- Org/user-level GitHub (e.g. function-store, t3kt other repos, DBraun) and gists not swept.

## Open questions for the lead
1. **Compare jazib-td with three peers** in the clones: 8beeeaaat (npm package, OpenAPI-generated client, API version handshake), Embody Envoy (70 tools, TDXN YAML export of networks, per-project venv), satoruhiga (Claude skills for GLSL/instancing). Worth lifting: network-as-YAML for diffing, skills content, undo-stack integration (Derivative TDMCP). Embody and TDMCP need a TD above 31550.
2. Is a TD upgrade past 31550 acceptable for tool evaluation, or do we only read their code? (they need 2025.33230+)
3. mediapipe-touchdesigner is in the PF26/camera notes already (`D_camera_mediapipe.md`); reuse that doc, then check the cloned `td_scripts/` for how it uses Web Render.
4. TouchDesigner_Shared is GPL-3.0 with per-file provenance mixed: use as study material; copy nothing into show assets without checking that file.
