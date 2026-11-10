# Community scrape, slice 02 (listing pages 20-39, 26 Oct 2026)

Source: `https://derivative.ca/community?page=20..39`. Data: `research_src/community/slice_02.jsonl` (296 records).
Posts date mostly Sep 2025 to Mar 2026 (the pages also carry a few pinned Oct 2026 items). The 20 pages list 391 links,
but only 296 are unique: the listing shifts as new posts arrive, so adjacent pages repeat posts. Post pages were read
with `curl` at 2 s spacing, no login, no failures. Relevance = general TD mastery (0-3), not PF26-only.

## Counts
- By type: asset 58, tutorial 63, post/blog/case study 67, event 55, workshop 53.
- By relevance: 3 = 31, 2 = 70, 1 = 107, 0 = 88 (events and meetups are mostly 0-1).
- Files: 40 files downloaded from derivative.ca attachments (13.5 MB) and 22 GitHub repos cloned `--depth 1` (about 200 MB).
- Nothing was opened, unzipped, run, imported or loaded. Zip contents were read with the zip index only.
- The same `files/<postid>/` folders also hold `repo_*`, `expanded` and `unzipped` folders from the later top-assets
  agents. Those are not mine and are not listed here.

## Top 15 by relevance
1. **74168 Claude Code + MCP server + TouchDesigner (Winfred_Nak).** Closest prior art to jazib-td: a Web Server DAT
   `mcp_webserver_base.tox` plus a GitHub repo ("TD-Codex Ultimate MCP", 68 `td_*` bridge tools on port 5326, plus a Node
   hub with 43 more incl. show control, LED planning, media servers). Includes AI prompt rules (no overlaps, left-to-right).
   Needs TD 2025+. Repo has no licence file. Worth diffing its tool list against ours.
2. **74207 The Great Inversion (dylanroscover).** Essay behind Embody / Envoy / TDN: text-serialised TD networks that can be
   diffed, plus an LLM bridge. Links: `dylanroscover.github.io/Embody/envoy` and `/tdn/specification`. Read next.
3. **73414 Native Background Removal on macOS (aaronmylespereira).** C++ TOP plugin on Apple Vision (neural engine), about 30 ms
   for Full HD, 3 quality modes. MIT, Mac native, needs the quarantine step. Replaces NVIDIA background removal for us.
4. **73386 BasicTouch (vacuum).** Auto-generates a bidirectional TouchOSC surface for any Base COMP's pars, randomise buttons,
   TauCeti preset sync, UDP/TCP. CC0. Tested on 2025.30960 (close to our build). Phone/tablet control of live looks.
5. **73268 TDMorph (Darien Brito).** Preset storage, morphing, random search, cueing, MIDI/OSC auto-learn, generated UIs. MIT
   (free PresetManager; some modules paid on Patreon). Cloned.
6. **73521 Custom Cuelist Sequencer (GabPelland).** Timed cues with fade-in over a master Base COMP preset; outputs
   TOP/CHOP/SOP/POP/DAT; timeline, timer or manual trigger. 26 KB tox downloaded.
7. **73899 Auto BPM Sync with AI (shum).** TCN BPM detector (7,000+ tracks) via TDPyEnvManager, torch device mps/cpu/cuda so it
   runs on Apple Silicon. Cloned (no licence file).
8. **72891 PoST (GRNCH).** End-of-chain post stack: levels, LUT, colour balance, AA, monochrome. tox + toe downloaded.
9. **73429 UberRamp (ChaosandLogic).** One GLSL TOP generating 14+ 2D/3D patterns from 2 ramps + control map. tox, toe, glsl.
10. **73946 Audio Analysis 2.0 Extended (Skywalker.Visuals).** Beat-logic components on top of palette audioAnalysis (count
    analysis, kick/snare triggers, low/mid/high drivers). 8 files downloaded.
11. **73834 Versatile VJ System (Black-Pomeranian).** 5-layer mixer, control UI, APC mini mk2 map, Sound2Light OSC audio.
12. **72940 YOLO + DepthAnything plugins (blankensmithing).** Tracking and depth from any webcam/TOP on Mac and PC via ONNX.
    Paid on Patreon (tutorial 73018 shows it).
13. **74222 Projector Coverage Tool (asterix).** Throw ratio, lumens, lens shift, frustum, coverage, previs shadows. Gumroad
    link, price not shown on the page, not downloaded.
14. **73153 2025 Official Update (ben).** POP family introduction (GPU-resident points with attributes), TDPyEnvManager,
    Thread Manager, POPsExamples + POPGuide download link, 3D viewer overlays.
15. **75562 AVY (elekktronaut).** Modular performance framework: presets, MIDI map, FX, modules, audio, OSC, Ableton Link.
    Patreon + purchasable key.
Also worth a look: 75551 (Timecode CHOP + Python), 73074 (Perform Mode), 73800 (LED pixel mapping), 72855 (Ableton concert
visuals), 73800/73538 (projector + LED tips) in the tutorials and blogs, all from Interactive Immersive HQ (elburz).

## Files downloaded (derivative.ca attachments, all free, no login; licence/build as stated on the post)
| Post | Files | Licence | Build | Contents |
|---|---|---|---|---|
| 72740 | FulldomeSimulator.tox 33 KB | unstated | TD 2022 | dome preview tox |
| 72758 | AIMods_Nano_Banana_v1.zip | free on Patreon | 2025 exp. | zip index: .toe, Export/, Temp/ (Gemini API key needed) |
| 73039 | AIMods_Sora2_V1.zip | unstated | 2025 exp. | zip index: .toe, Export/, Temp/ (OpenAI key) |
| 72863 | LaunchControlXL Utility .tox | unstated | n/a | MIDI mapping utility |
| 72891 | PoST.tox, POST.toe (3 MB) | unstated | n/a | post-processing component + demo |
| 73001 | video_fragmenter.toe | unstated | n/a | audio-reactive fragment effect |
| 73072 | Slamtec.plugin.zip | unstated | n/a | macOS .plugin bundle (Mach-O binary, not run) |
| 73155 | Pop_Truss.tox | unstated | n/a | parametric truss |
| 73186 | TLPAD tox + toe | unstated | n/a | Mac trackpad capture (Mac only) |
| 73359 | PostProcessVolume tox + sample toe | unstated | 2022.24200+ | region-based post fx |
| 73421 | wine_ui_fixes.tox | unstated | n/a | Wine/Linux fix |
| 73429 | UberRamp.tox, UberRamp_Example.toe | none in repo | n/a | GLSL pattern TOP |
| 73494 | LCh_Picker, LCh_Adjust, feedbackEdgeLCh .tox | none in repo | n/a | OKLCH colour tools |
| 73521 | cuelist_sequencer.tox | unstated | n/a | cue sequencer |
| 73642 | TLRocket tox (5.3 MB) | unstated | n/a | fireworks tool |
| 73817 | TLWEB_V4.tox, GAMEBOY_MOD tox | free | n/a | web page control |
| 73834 | VJ_System.tox (0.9 MB) | free | n/a | VJ system |
| 73858 | hand_to_coordinates.tox | unstated | n/a | MediaPipe hand naming |
| 73946 | 6 tox + 2 toe | unstated | 3.0.6 era | audio analysis components |
| 74064 | TLSTRUDEL_V1.tox | unstated | n/a | Strudel inside TD |
| 74073 | PCSD_POP_V2.toe | free | 2025 POPs | point cloud surface deformer |
| 74099 | Timeline_Toggle_Addon.tox | none in repo | n/a | UI add-on |
| 74168 | mcp_webserver_base.tox, TD-Codex-Phase6.zip, AI_TouchDesigner_MCP_v2.0.0.zip | none | 2025 | MCP bridge; zip index lists install.py, README, requirements, tests |
| 74219 | TLLORD_V1.tox | unstated | n/a | remote control bridge |

GitHub clones (commit short hash): MaxMainio/TD_ 9689834b (MIT, 239 tox, C++ sources; kept once under 72852), DarienBrito/TDMorph
55578f03 (MIT), flowb/TD-pipeOp f215e4fc (MIT), AppleVisionMask 4eafaefa (MIT), from-vacuum/basic-touch fe72087e (CC0),
moebius-transformation b75ddf0f (CC0), Alaghast Delaunay-Triangulation-POP 81cec354 and Voronoi-POP 73e63d98 (MIT, README only,
binaries in releases), SlamtecCHOP-MacOS 384dfdcb, TD_Copier_Tools d43e6823, Post_Process_Volume 9050dd90, UberRamp acd00730,
TouchDesigner-OKLCH 76356da1, Blend2TD 800cf466, VJ-System_Sample 4a2ad094, tdautobpmsync 1e90713f, Presetter cd385b52,
TD-WAV-Cue-Importer 33159532, Timeline-Toggle 88d8ede4, Matplotlib4TD e179ce6d, Hu-Tutututu TDCN assistant ce99283a,
familienak-tech Touchdesigner---MCP-server ead13c48. Repos without a licence file are all-rights-reserved by default.

## Recurring techniques and ops
- POPs everywhere after the 2025 release (14 tagged items): flocking, particle logic, trails (RayPOP), Voronoi/Delaunay
  plugins, point typography, GLSL POP transforms. Several custom POPs need **2025.33070+**, newer than our 31550.
- Audio-reactive: audioAnalysis palette plus beat/count logic, adaptive Python reactivity, BPM from ML, Ableton via TDAbleton.
- Control: MIDI/OSC/TouchOSC, preset and cue managers (TDMorph, Presetter, Cuelist, BasicTouch), web panels (seeplayshow).
- AI: StreamDiffusionTD (Daydream hosted), ComfyTD, Nano Banana, Sora 2, VEO 3, depth and YOLO on-device.
- Tooling: TDPyEnvManager for Python deps, GLSL TOP one-shot generators, `.tox` toolkits on GitHub, MCP/LLM bridges.

## Authors who post a lot
elburz (Interactive Immersive HQ, 48 tutorials/blogs), cmuir (Daydream, 17), The NODE Institute (16 workshops/events),
isabelle (Derivative, 9 articles), tekt (9, RayTK, workflow), audiodevout (9, noise sculpting tutorials), pao.olea (6),
GRNCH (5 tools), THETOUCHLAB (5 tools), uisato (5 AI components, Patreon), GATE1 (5 Notch case studies), function.store (3).

## Windows-only / NVIDIA-only / non-Mac
NVIDIA Flex Solver (73165, 73269); Kinect-based items (74013, 72988); Wine/Linux notes (73421, 72962); workshop 73599 asks for a
Windows laptop. 73186 TLPAD is Mac-only. Mac confirmed in text: 73414, 73072, 74014, 74215, 73899 (mps), 72940.

## Skipped or not downloaded
- No leak/crack/rights items found.
- Over limit or wrong type: 73382 (38 MB mp4 demo; tox is on Patreon), 73213 (six .MOV, 7-35 MB), README/manual `.txt` files
  (73817, 74064, 74219), repos over 50 MB removed: 72891 PoST (63 MB), 73133 Hydra2TD (72 MB), 73917 TD-ML (86 MB),
  73935 TD-Launcher-Plus (104 MB), 72740 Fulldome repo (179 MB).
- Patreon/paid only (recorded, not fetched): 72857, 73124 (uisato VEO3/Sora2), 72940 (YOLO, DepthAnything), 73236
  (StreamDiffusionTD SDXL), 73620 ElevenLabs SFX, 73603 Colorpicker, 74172 Acid 303 CHOP, 74222 (Gumroad), 75562 AVY.
- Blog posts by elburz are stubs ("click here to continue") pointing to interactiveimmersive.io; only titles and summaries kept.

## Open questions
- Which of the custom POP plugins (Voronoi, Delaunay, Acid 303) load on 2025.31550? They state 2025.33070+.
- 74168's MCP tool list versus jazib-td: which of its 68 bridge tools and 43 hub tools are worth adding?
- Embody/Envoy/TDN (74207): should TDN-style text export be added to our MCP for diffing networks?
- Events and workshops were summarised from listing text only; 72730 (workshop) page had no usable body.
