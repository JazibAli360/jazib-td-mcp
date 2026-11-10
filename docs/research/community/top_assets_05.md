# derivative.ca assets by views, listing pages 27-32 (agent 05, 26 Oct 2026)

Source: `https://derivative.ca/community?sort_by=views&type[]=24&page=27..32` (type 24 = Asset). 93 unique assets read (all 93 post pages fetched,
2 s apart, no errors). Data: `research_src/community/top_assets_05.jsonl` (one line per asset). Files: `research_src/community/files/<postid>/`.
Rank = brief formula `page*20+index+1` (non-featured only); `F27` etc. = only seen in the featured block (see caveats). Mac column: `yes` = native
ops only per toeexpand (NOT run), `unk` = unknown, `WIN` = Windows/NVIDIA/C++-dll only. free*: free with a condition (non-commercial / Patreon extras / time-limited).

## Listing caveats (read first)
- **This is not the "least-viewed end".** Displayed views RISE with page number: p27 avg ~2k, p31 avg ~6k, and p32 ends with the two biggest here
  (Colour Lover Palette Picker 64.8k, Project File Pack Vol.2 57.7k). The `sort_by=views` listing is not strictly descending by the shown count; verify against
  page 0 before trusting the order. (Page 32 has only 4 normal rows, so the listing holds ~485 assets, not 660.)
- Each page = a **featured block of 5** (1 wide + 4 mid teasers; same few posts repeat across pages: 14 unique here, low views 156-2182) + **15 ranked rows**
  (p32: 4). Featured items are flagged `listing_featured_block_only` in the JSONL and get no `views_rank`.
- Comments show 0 everywhere (loaded from Discourse via JS, so unreliable). `reads` = `views` on every page.
- Older posts (2019-2022) dominate this range; 2024-2026 posts sit in the featured block.

## Ranked table (listing order)
| rank | title (post id) | author | views | free? | licence | build | Mac | technique |
|---|---|---|---|---|---|---|---|---|
| 546 | Tweener (62839) | alphamoonbase | 2,280 | free | not stated | - | yes | op('tweener').AbsoluteTween(par,end,time,curve); fades pr~ |
| 547 | OSC Query Server Component (62663) | manuel_mitasch | 2,119 | free | MIT (repo) | - | yes | Web Server DAT serving HTTP/WebSocket OSC Query JSON + OS~ |
| 548 | Physarum without GLSL (66377) | josefpelz | 2,739 | free* | non-commercial only | - | yes | Feedback TOP + Remap/Math |
| 549 | Tap Tempo / Tap Sync (65370) | igierard | 4,666 | free | MIT (repo) | - | yes | Tap timestamps -> average interval -> Time COMP bpm |
| 550 | TD-Mirobot (62591) | matthewwachter | 1,562 | free | MIT (repo) | - | unk | Serial DAT + Python extension, G-code builder, JSON locat~ |
| 551 | TLTINTACT - COMPUTER VISION CONTROL (71515) | THETOUCHLAB | 1,372 | free | not stated | - | yes | Python cv2 colour detection -> custom controls |
| 552 | Instancing Geometric Shapes ┃ Audiovi~ (69023) | Skywalker.Vis~ | 2,256 | free | not stated | - | yes | SOP-to-CHOP-to-TOP with two feedback loops and instancing |
| 553 | Video Wall Mapping (69336) | Sebby | 1,108 | free | not stated | - | yes | Geometry grid from input pars, camera-rendered panels, 13~ |
| 554 | BANANA_CurrentlyPlaying (62774) | JetXS | 1,590 | free | GPL (repo) | - | yes | Python extension with OAuth via browser (webbrowser.open_~ |
| 555 | Lunochod UI Designer (62143) | alphamoonbase | 1,648 | free* | free non-commercial; comm~ | - | unk | Container-based widget system with parexec/panelexec, 1.4~ |
| 556 | OpenCV Face Detect Custom TOP (62407) | mouren | 1,463 | free | GPL (repo) | - | yes | TD Custom Operator C++ TOP + OpenCV 3.4 |
| 557 | FlexCHOP (62053) | vinz99 | 1,573 | free | MIT (repo) | 2019.10000 | WIN | C++ CHOP plugin (CUDA, FleX) + GLSL instancing |
| 558 | Autosave tox (61073) | cataliz3er | 3,531 | free | not stated | - | yes | Timer CHOP + Execute DATs calling project.save with incre~ |
| 559 | Layer Based Timeline Tool - Beta (62689) | TimFranklin | 1,674 | free | GPL-3 (repo) | - | unk | Instancing + render picking, segment DAT feeding a master~ |
| 560 | OSCToolset (69117) | Eusebi | 1,755 | ? | plugin on author site | - | yes | OSC Out CHOP/DAT from tox; UE5 plugin |
| 566 | CMYK Halftone Dot Filter (70288) | meatwithdreams | 1,712 | free | not stated | - | yes | GLSL TOP |
| 567 | Flashlight paint in 3D with Trace SOP (62777) | xnimax | 1,960 | free | not stated | - | yes | Video In -> Threshold -> Trace SOP -> Delete SOP -> trail~ |
| 568 | QR Code Maker (65759) | amazingrobot | 4,907 | free | not stated | - | yes | Python pyqrcode (pip) -> PNG via pypng -> Movie File In |
| 569 | Generative spider character (63882) | josefpelz | 1,578 | free | not stated | - | yes | GLSL MAT + instancing + IK-like leg solving |
| 570 | TD Network Visualization Tool (62783) | lucasm | 2,136 | free | open source (unspecified) | - | unk | Opens every toe in sequence, diffs contents, writes Gourc~ |
| 571 | TD Scripts: a Blender Add-on for Touc~ (66520) | Artechs | 3,439 | free | free v1.1 (download on Pa~ | - | yes | Blender Python add-on |
| 572 | Flame Vortex (61054) | Darien.Brito | 2,459 | free | not stated | - | WIN | NVIDIA Flow COMP + audioAnalysis + big parameter UI (1492~ |
| 573 | Spout For Python Library (62921) | Vasily | 2,246 | free | not stated | - | WIN | Python ctypes/wrapper around Spout, version autodetect |
| 574 | FaceCHOP C++, Landmark Detection and ~ (62239) | DavidBraun | 1,730 | free | see LICENSE.md in repo | - | WIN | C++ CHOP plugin with dlib 68-point model + OpenCV |
| 575 | TD Initiative Library (62936) | valentindufois | 1,593 | free | GPL (repo) | - | yes | Repo of tox files, CC-style contributions |
| 576 | Iridescent GLSL MAT (62799) | mickeyvanolst | 2,079 | free | not stated | - | yes | GLSL MAT with view-angle based colour ramp |
| 577 | Physarum transport network clean TOX (65070) | ciphrd | 3,903 | free | not stated | - | yes | Feedback + GLSL TOP trail map + instanced agents |
| 578 | uv unwrapping inside TouchDesigner (62605) | jacqueshoepff~ | 2,282 | free | not stated | - | yes | Constant/over/comp TOPs building UV layouts + Camera COMP~ |
| 579 | Point Field COMP (63627) | greg | 2,427 | free | not stated | 2022.20300 | yes | Field CHOP/TOP math over positions; Geometry instancing |
| 580 | Point Cloud Surface Deformer .V1 (71841) | Milkorva | 4,407 | free | not stated | - | yes | Point File Select TOP + GLSL deformation + Render |
| 586 | Tileable noise collection (63593) | exsstas | 2,406 | free* | MIT (source repo); free f~ | - | yes | GLSL TOP per noise, Render Select for preview |
| 587 | Portals - [TouchDesigner + Stable War~ (69160) | uisato | 4,471 | paid | paid (Patreon/linktree) | - | unk | TD audio-reactive render -> Stable WarpFusion |
| 588 | B2BK Custom Tools & Buffer Techniques~ (65007) | b2bk | 2,157 | free | not stated | - | yes | Render TOP buffers + masks from world position/normal pas~ |
| 589 | Blob Track Interactive Installation │~ (68972) | Skywalker.Vis~ | 3,563 | free | not stated | - | WIN | Blob Track TOP, Nvidia Background TOP, instancing |
| 590 | USB camera video switcher made with T~ (62823) | takashi_sasaki | 2,399 | free | not stated | - | yes | Video Device In x N + Switch TOP + Button/Keyboard In/MID~ |
| 591 | Laser Cube Ethernet LAN + WiFi Workin~ (65251) | Dorian | 3,268 | free | free to use | - | yes | Python socket DAT scripts, asyncio |
| 592 | Colorpicker UI Widget (63124) | Artechs | 5,326 | free | not stated | - | unk | Container/GLSL based picker widget |
| 593 | VST effects and instruments in TouchD~ (63676) | DavidBraun | 1,870 | free | JUCE licence text in repo | - | WIN | C++ CHOP built on JUCE |
| 594 | INSIDE DOME (61078) | anodin | 3,592 | free | not stated | - | unk | Render + fisheye/azimuthal UV remap in GLSL/TOPs, Movie F~ |
| 595 | Text Space Explosion with Blend SOP (62780) | xnimax | 2,595 | free | not stated | - | yes | Text SOP -> SOP to CHOP -> Noise CHOP -> Blend SOP; feedb~ |
| 596 | TouchDesigner MCP for Claude — macOS ~ (74528) | Lostfound | 4,479 | paid | Patreon | - | yes | tox + Claude Desktop config install |
| 597 | Fluid simulation component (65741) | devart.space | 7,283 | free | credit to Bruno Imbrizi +~ | - | yes | GLSL TOP Navier-Stokes iterations |
| 598 | Serum Template (66309) | josefpelz | 10,344 | free* | non-commercial only, cred~ | - | yes | TOP feedback + instancing |
| 599 | ATTRAKTORS DESIGNER v0.7 (66142) | JiveFaury | 2,795 | paid | paid via Patreon | 2021.16410 | yes | Several particle systems, GLSL; packaged app |
| 600 | TD-Completes-Me. A Simple Auto-Comple~ (62836) | davet | 3,434 | free | none stated in repo | - | yes | VS Code LSP shim <-> TCP <-> TD Python extension using re~ |
| 606 | Keyframer Comp (64088) | keithlostracco | 3,214 | free | none stated (repo) | - | yes | Render-picked keyframe editor driving animationCOMP via P~ |
| 607 | Interaction Display [Free .tox] – Key~ (65107) | elekktronaut | 3,982 | free | free, credit welcome | - | yes | Keyboard In, Mouse In, ui.panes hover, timers |
| 608 | GlowSticks (63640) | timgerritsen | 3,874 | free | not stated | 2020.27390 | yes | GLSL multi TOP ray-capsule intersection; reads CHOP like ~ |
| 609 | Lidar Component: LidarTracker (63013) | Zink | 3,169 | free | not stated | - | WIN | C++ CHOP + tox UI |
| 610 | geoMusica 1.220320 (63067) | ruigato | 3,455 | free* | GPL-3 (commercial: contac~ | 2020.25380 | unk | Python/TD app with geometry -> note generation, MIDI out,~ |
| 611 | Claude Code + MCP_server + Touchdesig~ (74168) | Winfred_Nak | 3,620 | free | none stated | - | yes | mcp_webserver_base.tox + Python modules; Node hub |
| 612 | Bubble Bubble with Particle SOP (62781) | xnimax | 3,446 | free | not stated | - | yes | Particle SOP, Noise CHOP, instancing |
| 613 | Linea ROOM #1 - watch the inspiration~ (62847) | xnimax | 3,100 | free | not stated | - | WIN | Kinect TOP/CHOP -> SOP -> Sweep SOP; Lag+Spring CHOP |
| 614 | Color Curves (62913) | Vasily | 3,506 | free | not stated | - | yes | Interactive curve editor via render picking + lookup tabl~ |
| 615 | TD PIP (63077) | alphamoonbase | 6,819 | free | not stated | - | yes | Python extension running pip into project Lib folder, sys~ |
| 616 | Download iKeleton OSC for free until ~ (67733) | fredfred | 2,954 | free* | app store app | - | yes | iOS Vision pose -> OSC -> OSC In CHOP |
| 617 | Audio Analysis 2.0 (73946) | Skywalker.Vis~ | 2,738 | free | not stated | - | yes | CHOP math/trigger/count networks |
| 618 | Slamtec RPLidar support (67156) | Vasily | 8,977 | free | not stated | - | WIN | C++ CHOP + SDK |
| 619 | Shadertoy to Touchdesigner to Raspber~ (63259) | louiselessel | 5,943 | free | none stated (shaders keep~ | - | yes | Text DAT conversion script rewriting Shadertoy main/unifo~ |
| 620 | RabbitControl - Remote Control Anythi~ (63238) | snaut | 4,792 | free | Unlicense (public domain) | - | yes | WebSocket DAT/Web Server DAT, RCP binary protocol in Pyth~ |
| 626 | RayTK: Raymarching for the masses (63620) | tekt | 3,891 | free | CC BY 4.0 (repo) | 2020.44350 | yes | tox library of SDF/material/light/render ops generating G~ |
| 627 | 3 templates for Kinect skeleton visua~ (63863) | exsstas | 7,025 | free* | not stated | - | WIN | Kinect CHOP -> Select/Line SOP/Metaball |
| 628 | Water ripple effect (63763) | exsstas | 8,297 | free | not stated | - | yes | Feedback-based height field in GLSL TOP, Displace TOP use |
| 629 | Tau Ceti Preset Engine (61075) | alphamoonbase | 6,519 | free | not stated | - | unk | Stack of parameter references + Tweener interpolation + p~ |
| 630 | TouchDesigner (62917) | mir.works | 5,124 | free | MIT (repo) | - | yes | Instancing from CHOP/DAT/TOP/SOP; GLSL, physics, flex, ar~ |
| 631 | timeBase - a Multi-Layer Timeline Com~ (61146) | greg | 5,555 | free | not stated; 'mod and use ~ | 2019.30000 | unk | Scenes of layers mixing video/audio/channels via Python e~ |
| 632 | td-shadertoy (62238) | matthewwachter | 6,806 | free | MIT (repo) | - | yes | Python (requests) fetches shader JSON -> text conversion ~ |
| 633 | Ninja Puppet with Kinect CHOP + Nvidi~ (62856) | xnimax | 5,425 | free | not stated | - | WIN | Kinect CHOP -> Spring/Lag -> NVIDIA Flow COMP; 1000 ops |
| 634 | Compute Particle System v2.0 (62080) | timgerritsen | 5,525 | free | not stated | - | yes | GLSL TOP compute shaders writing position textures, Geome~ |
| 635 | 3D volumetric rendering (using near/f~ (65663) | Winfred_Nak | 5,779 | free | not stated | - | yes | Camera near/far slicing -> pixel mapping -> Spout/ArtNet |
| 636 | Depth Cam Merger (63795) | Darien.Brito | 3,782 | free* | MIT (repo) | 2025.33070 | yes | Writes clouds to temp folder, runs external Python (Open3~ |
| 637 | Normal Map v.2 (65562) | paketa12 | 6,151 | free* | not stated | - | yes | Normal TOP + math/level offsets, 15 ops |
| 638 | POINTCLOUDS from 2D images (+depth) (62516) | b2bk | 7,472 | free | not stated | - | yes | Depth map + colour -> point positions via TOPs/SOP, render |
| 639 | Tweening with Tweener! A python based~ (65629) | amazingrobot | 6,077 | free | not stated | - | yes | Global OP shortcut + Execute DAT frame loop, tween array |
| 640 | TouchDesigner and Lasers (63736) | danieldalfovo | 13,065 | free | none stated | - | unk | Laser CHOP -> Audio Device Out (AVB) |
| 646 | TDNeuron (62633) | TDNeuron | 6,764 | free | GPL v3; commercial licenc~ | - | WIN | Networks of layers as COMPs with GLSL TOP compute; traini~ |
| 647 | Constraint Simulation Tool (65109) | josefpelz | 9,930 | free* | NON COMMERCIAL ONLY | - | yes | GLSL multi TOP compute + Script SOP |
| 648 | Touchdesigner Project File Pack Vol.2~ (64793) | Kohui | 57,726 | free | free download; Patreon fo~ | - | yes | Instancing, feedback loops |
| 649 | Colour Lover Palette Picker (62697) | michelchrome | 64,800 | free | 'free to use' (no licence~ | 2022.33600 | yes | Web DAT/Python fetches COLOURlovers API JSON; GUI contain~ |
| F27 | Vintage Lens Effect Tool (69724) | dcheesman | 1,311 | paid | paid (Patreon page) | - | yes | TOP chain |
| F28 | Wifi Network Manager (69981) | pdubost | 263 | free | not stated | - | WIN | Python subprocess calling netsh |
| F30 | Procedural Hilbert patterns (70707) | Unveil_studio | 530 | paid | paid (Patreon) | - | yes | SOP/TOP generation |
| F27 | UV Wall Extrusion tool (71010) | harveymoon | 395 | free | not stated | - | yes | Curve SOP -> sweep/extrude -> UV math |
| F31 | PiNODEs Beta (71417) | pitheorem | 542 | free | GPL (repo) | - | yes | tox of GLSL TOP components |
| F28 | iXeRemin - Free Download through June~ (72196) | fredfred | 488 | free* | app store | - | unk | visionOS app -> OSC |
| F31 | Audioreactive Video Playhead - Defini~ (72379) | uisato | 2,182 | paid | paid (Patreon) | - | unk | TD + Gemini API |
| F28 | RayTK v0.46 Release (72698) | tekt | 269 | free | CC BY 4.0 | - | yes | tox release |
| F27 | SORA2 INSIDE TOUCHDESIGNER (73039) | Infratonal | 778 | free | MIT (stated in post) | - | yes | Python requests to OpenAI API, base64, files |
| F31 | TD Copier Tool (73164) | GRNCH | 156 | free | post: License None | - | yes | Python |
| F31 | Repository of Custom Morphological Op~ (73301) | MaxMainio | 227 | free | see repo | - | yes | Image processing tox |
| F28 | Post Process Volume for TouchDesigner (73359) | tormozgh | 861 | free | not stated | 2022.24200 | yes | World-position based masking |
| F27 | Repository of Custom Signed Distance ~ (74343) | MaxMainio | 253 | free | see repo | - | yes | tox library |
| F27 | Web is OP (74725) | Unveil_studio | 205 | free | free via Patreon | - | yes | Web Server DAT + browser pages |
## Deep notes: 15 picks for an all-round TD expert (chosen by use, not views)
1. **Claude Code + MCP + TD (74168, Winfred_Nak, 2026)** - Peer of jazib-td. `mcp_webserver_base.tox` = Web Server DAT MCP endpoint (port you set); full "TD-Codex Ultimate" repo
   (familienak-tech, commit ead13c4, 2026-10-06): `td-bridge/TD_mcp.tox` serves MCP at 127.0.0.1:5326 with 68 `td_*` tools (create/connect/inspect ops, pars, DAT text, Python exec,
   validation, snapshots, .tox export, knowledge/rule packs) + Node hub on :3000 adding 43 tools (creative-prompt pipeline, vision check, perf, show control, LED planning). Needs TD 2025+,
   Node 18+. No licence file. Audit: exec-python tool by design; modules folder via env/par; open() of schema files. Idea to borrow: `td_get_connection_protocol` first-call rules, validators, knowledge packs.
2. **TouchDesigner MCP for Claude, macOS+Windows (74528, Lostfound, 2026)** - tox with a "Claude Setup" page: one click writes the Claude Desktop MCP config, uses TD's bundled Python, no pip.
   Paid/gated via Patreon (tier not shown); not fetched. Borrow: in-tox installer button that edits the client config.
3. **Depth Cam Merger (63795, Darien.Brito)** - markerless multi-depth-camera point-cloud merge (Azure/Orbbec/ZED/any TOP pair), pulse Calibrate; output is a POP. v0.4.0 built on TD 2025.33070. Open3D runs OUTSIDE TD:
   component writes clouds to a temp folder, `subprocess.run` of a user-chosen Python 3.11+, reads a 4x4 matrix back. MIT, commit 7ed89c3 (2026-09-03). Pattern worth copying for heavy Python deps.
4. **OSC Query Server (62663)** - Web Server DAT publishes custom pars with type + range via OSC Query so Chataigne/Vezer/TouchOSC auto-map; MIT; TD 2020+. Pairs with **RabbitControl RCP-TD (63238)**
   (bidirectional remote control of tagged COMPs, websocket + web panel, Unlicense). Both = standard answers for "control TD params remotely without wiring".
5. **Tweener (62839 alphamoonbase; 65629 amazingrobot)** - two Python tween engines. alphamoonbase: `op('tweener').AbsoluteTween/RelativeTween/CreateFade`, expression-mode fades, only cooks on change, curve COMP;
   amazingrobot (GreenSock-style): global `op.Tweener.To/FromTo/KillTweenByID`, 7 files + easing examples. Tau Ceti preset engine (61075) builds on the first. Only audit hit: a website button calls `webbrowser.open`.
6. **RayTK (63620 v0.9; 72698 v0.46)** - raymarching built from ops, no GLSL; ALT+R operator menu; also 2D processing and volumetric LED sampling. CC BY 4.0 (repo). v0.46 is for the 2025 experimental builds, UI re-implemented,
   threaded shader compilation, image-based 2D SDF (68k ops in the tox; another agent holds it in `files/72698`).
7. **3D volumetric rendering via camera near/far (65663, Winfred_Nak)** - slice a 3D scene into 2D planes for LED volumes -> Madrix/Resolume/ArtNet; includes RayTK sampling, TOP and POP versions, Dragon-O patches, 53k-op "pointMap" tutorial. Native ops. Relevant to Resolume output.
8. **Video Wall Mapping (69336, Sebby)** - Geo COMP builds a pixel-accurate panel grid from input pars, camera-textured, per-screen pixel maps for Novastar/disguise, test pattern (1372 ops, native).
   Plus **UV Wall Extrusion (71010)** and **uv unwrapping (62605)** (stage box with continuous UV across 3 walls + floor): the stage-mapping trio.
9. **Instancing Examples (62917, mir.works, MIT)** - 40+ techniques behind a navigator UI; macOS scrollbar bug noted by author. **Keyframer (64088, IntentDev)** - Animation COMP editor replacement (still maintained, Jan 2026).
10. **TD-Completes-Me (62836, davet)** - VS Code LSP shim <-> TCP <-> TD extension: completion for `op('')`, pars, channels, DAT cols. Editor-side counterpart to an MCP.
11. **TD PIP (63077, alphamoonbase)** - `op('td_pip').Import_Module("qrcode", pip_name=...)` installs into a per-project Lib folder; file lives on OLIB (not fetched). Same need as QR Code Maker (65759: pyqrcode via external Python).
12. **SORA2 inside TD (73039, Infratonal)** - AIMods_Sora2.toe: OpenAI Sora 2 txt2video/img2video through `requests`, key via env loader, MIT per post; needs `pip install openai`; part of an "AIMods" series (Nano Banana earlier).
13. **Audio Analysis 2.0 Extended (73946)** - downstream of Palette audioAnalysis: count/trigger/logic per kick/snare subdivision (4th/8th/16th), jumper, zig-zagger; seven small tox. Plus **Tap Sync (65370, MIT)** for BPM.
14. **Post Process Volume (73359, tormozgh)** - region-limited 3D post effects, Unreal-style; TD 2022.24200+. **Point Cloud Surface Deformer (71841)** - PLY clouds, attractors; Mac adaptation credited.
15. **Colour Lover Palette Picker (62697, 64.8k views)** and **Color Curves (62913)** - most-used here. Palette picker: COLOURlovers API -> Ramp TOP + Table DAT; Curves: render-picked editor, v2.2.3 by dylanroscover (histogram, A/B).

## Downloaded files (mine) and audit
- 70 files from derivative.ca, 65.1 MB total (all free, no login; `.tox/.toe/.zip`; biggest B2BK 39.4 MB). Skipped: 3 JPG screenshots (62783), Stereolux03 toe 45.5 MB (superseded by the 2023 file).
  Posts whose folder another agent had already made (62823, 65370, 65562, 65629, 65663, 66377, 69336, 69981, 70288, 71010, 71417, 73039, 73359) were not touched; I read their files in place.
- 22 new git repos cloned depth 1 (plus 4 already cloned by other agents, read in place) (commits in JSONL `files[]`), e.g. FlexCHOP be1592c, td-shadertoy 95e0b48, OSC-query 02538e6, RCP-TD 0bac384, TDAzureMerger 7ed89c3, Keyframer 0ef4396, TD-Codex MCP ead13c4.
  Removed for the rules: Windows C++ binaries (LidarTracker, SlamtecCHOP, OpenCV3TOP Plugins/Data = 210 MB), geoMusica 60 MB .rar, instancing-examples 127 MB `assets`. Not cloned: 62921 (repo 404), RayTK (another agent), 62633 TDNeuron (link only).
- toeexpand (TD 2 app, `Contents/MacOS/toeexpand`) run on copies in `files/<id>/expanded/<name>/`; nothing was loaded into TD. Zips unzipped into `files/<id>/unzipped/`.
  Mostly native op networks; typical 10-1500 ops. Biggest: RayTK-0.46 68k ops, B2BK pointMap tutorial 53k, timeBase 15k, PiNODEs 10.6k.
- **Audit flags (real, not boilerplate):**
  - 62783 Network Visualization Tool: temporarily patches a system tox in the TD install; a crash makes every toe quit on open (post warns; fix = reinstall or restore backup). Avoid on the Resolume/PF26 install.
  - 63795 subprocess.run of external Python + temp-file write/remove (documented); 69981 wifiManager runs `netsh` (Windows only); 73164 Copier tool opens a hard-coded Windows path via webbrowser.
  - Network: td-shadertoy (requests to shadertoy.com), Colour Lover Picker (colourlovers API), Banana (Spotify OAuth, browser), SORA2 (OpenAI API + key), OSC-query/RCP (open listening ports), Laser Cube (UDP), TD-Completes-Me (local TCP).
  - Installs at runtime: TD PIP (pip), QR Maker (pyqrcode), SORA2 (`pip install openai`), MCP bridge (sys.path edits).
  - `eval(` hits (Flame Vortex, Tweener, SKYMORPH...) are `par.eval()` / expression helpers; Execute DAT hooks with onStart/onCreate are the stock empty template in most files (real ones: timeBase cleanStartup, interactionDisplay timers, Tweener, Sora2 START_TOOLS).
  - No file ran code at load beyond those; none writes outside its project except autosave (project copy), Mirobot JSON, SORA2 video/image output.

## Recurring authors
xnimax (5 beginner SOP/CHOP assets with videos), alphamoonbase (Tweener, Preset engine, Lunochod UI, TD PIP; files on OLIB; Lunochod non-commercial), josefpelz (4; all non-commercial, credit), Skywalker.Visuals (3), Vasily (3: Color Curves, Spout lib, RPLidar), exsstas (3 GLSL, Patreon extras),
Darien.Brito (Flame Vortex, Depth Cam Merger), Artechs (Blender add-on, Colorpicker; Patreon), DavidBraun (FaceCHOP, TD-JUCE: both Windows C++), b2bk (2), MaxMainio (2 repos), Winfred_Nak (volumetric + MCP), timgerritsen/yfxlab (Compute particles, GlowSticks; credited in Surface Deformer), t3kt (RayTK), uisato/Unveil_studio/Artechs (Patreon-gated).

## Windows / NVIDIA only
Flame Vortex (NVIDIA Flow), FlexCHOP (CUDA FleX dll), FaceCHOP (dlib, Windows build), TDNeuron (compute shaders per post), LidarTracker + SlamtecCHOP (Windows dlls), TD-JUCE (OSX untested), Kinect CHOP assets (Linea, Ninja Puppet, Kinect SOP templates),
Spout for Python (Spout = Windows), Wifi Network Manager (netsh), Blob Track (Nvidia Background TOP optional), Mirobot/Laser (hardware dependent).

## Skipped / not fetched
No leaks found. Patreon-gated (title only): Attraktors Designer, Portals (uisato), Vintage Lens, Hilbert patterns, Audioreactive Video Playhead/Veo, MCP for Claude (74528), Web is OP (free but Patreon login). Off-site not fetched: OLIB (Tweener, TD PIP, Preset Manager), enviral-design zip, OSCToolset site, Google Drive point cloud, iOS apps (iKeleton, iXeRemin).
Large-binary / C++ plugin releases recorded only.

## Open questions
Is `sort_by=views` really descending (see caveats)? Does 2025.31550 on macOS run compute-shader assets (Compute Particles, Constraint Simulation) - needs a live probe, not done. Which MaxMainio repo licence applies (clone gone from my folder, another agent has `repo_MaxMainio__TD_`).
