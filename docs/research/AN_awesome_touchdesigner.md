# AN - awesome-touchdesigner (monkeymonk) curated list, read in full (26 Oct 2026)

Source: https://github.com/monkeymonk/awesome-touchdesigner (README, 303 lines, fetched raw from `main`). Research only: nothing run or loaded in TD. Dedupe done by grepping every URL (and `owner/repo`) against `docs/research/**`.

**Counts:** 182 link entries (+ section headers). 74 already covered somewhere in our research, 108 not present by URL. Of the 108, ~85 are social/artist/channel/event/VJ-software links with no MCP value; the genuinely new technical items are listed in "Deep notes". The list is shallow (mostly link-dump, 2023-2025); our own master guide (`AD_td_master_guide.md`) and `popular/github.md` already cover its best repos. Relevance scale: 0 none, 1 background, 2 useful reference, 3 directly usable by an MCP that builds networks.

## Shallow clones (read only, never run/loaded) in `research_src/awesome_td/`
`touchpy` (2 MB), `touchDesigner_experiments` (3 MB), `touchdesigner-sop-to-svg` (3 MB), `tektshared` (5 MB), `ShaderToyTouchdesigner` (0.2 MB). Larger repos (ShaderBuilder 61 MB, PostEffects 53 MB, Terrain Tools 41 MB, Rust plugins 56 MB, TDYolo 905 MB, playground 57 MB, knotidm 1.3 GB) were read via README/API only. Git-ignore status of `research_src/` is unchanged.

## Deep notes: new technical items

| # | Item | Licence | Platform | What it gives / techniques |
|---|---|---|---|---|
| 1 | **ShaderToyTouchdesigner** (SebastienGravel, 2016) | none stated | any (GLSL TOP) | A `.tox` where Shadertoy code is pasted into a `shaderProgram` DAT and wrapped into a GLSL TOP; iResolution/iMouse/iGlobalTime set as uniforms. Works ~60%; no audio; cubemap/raymarch samplers fail; textures must be re-imported to TOP inputs. **Port the idea, not the file:** an MCP `td_shadertoy` that wraps `mainImage(out vec4,in vec2)` into TD's `out vec4 fragColor` + `vUV` + `uTD2DInfos` is ~40 lines and is more robust today (GLSL 4.60, `sTD2DInputs[]`, `TDOutputSwizzle`). L_shader_sources_licences already says Shadertoy licences vary - keep per-shader licence note. |
| 2 | **touchdesigner-sop-to-svg** (Ragan, MIT, 2018 / TD099) | MIT | any (needs `svgwrite` pip) | `svgEXT.py` class `Soptosvg`: world->camera->screen projection (`camera.transform()` inverted, `camera.projection(aspect)`, divide by z) then svgwrite polylines/polygons for AxiDraw/laser. Useful pattern: scripting a SOP -> file export from a COMP extension with custom pars (`Polylinesop`, `Svgtype`, `Aspect1/2`). Python 3.5 install notes are obsolete; TD 2025 ships 3.11 so `svgwrite` goes in a user site-packages path or write SVG text by hand (no dep). Candidate `td_export_svg` (plotter / laser / vinyl workflows; low PF26 priority). |
| 3 | **tektshared** (t3kt, 2015) | none stated | any | ~50 small tox: `paramsmoother`, `quantizer`, `gater`, `pulseratelimiter`, `spinpulser`, `triggeredanim`, `presetslot`/`preset`, `recorder`, `outputrecording1-3`, `echo`, `stutter`, `kaleidoscope`, `hsvtorgb`/`rgbtohsv`, `namedcolorpicker`, MIDI device maps (Midi Fighter Twister, Livid). Old (TD 2015); the same author's RayTK is the modern code and already covered. As a *pattern list* it is a good checklist of "small utility COMPs an MCP should be able to drop": smoother, quantizer, gate, rate limiter, preset slots. Check `AM_tdxcomponents` before building any - most exist in palette/TDxComponents. |
| 4 | **touchpy** (IntentDev, MIT, active 2026-05) | MIT | **Windows + NVIDIA only** | Runs `.tox` headless through TouchEngine with CUDA/Vulkan zero-copy TOP/CHOP/DAT/par exchange. Not usable on this Mac. Value: confirms the TouchEngine contract (load tox, start, frame_did_finish, start_next_frame) for a possible later offline batch renderer; flag to FUTURE.md as Windows/NVIDIA. |
| 5 | **TDYolo** (patrickhartono, MIT, active 2026-05) | MIT | Win + macOS (Metal), TD 2023.12000+ | YOLO11 inside a Web Render/headless-browser (WebGPU/ONNX) - no Python env. Outputs `report` table DAT (Object_Type, Confidence, X/Y_Center, Width, Height, ID, ClassID), `summary` DAT, bbox/label overlay TOPs. 640x640 frames, needs internet to bootstrap runtime. Same architecture as the mediapipe tox (browser as inference engine) - good fit for a "no pip" Mac detection route. Probe on 31550: does the Web Render TOP expose WebGPU on Rosetta? (unknown, PROBE). 905 MB repo, so take the release `.tox` only. |
| 6 | **Terrain Tools** (CraftKontrol, MIT) | MIT | any (GLSL MAT) | Heightmap + splat-map terrain, water with depth-fade/foam (simplex), tree/grass bending MATs with fake translucency, LOD instancer with cone frustum culling, boids with multiple targets/enemies (from DBraun), volumetric fog, lens flare. Techniques: instancing positions from heightmap + distribution map in a GLSL compute/TOP, frustum cull in shader. Relevant to P_realtime_3d_looks; PF26 low. |
| 7 | **PostEffects** (yasuhirohoshino, MIT, 2023) | MIT | any (SSAO/SSR need depth/normal buffers; verify under macOS GL4.1-class limits) | Bloom, camera motion blur, lens effects, simple DoF, SSAO, SSR as drop-in COMPs. Bloom and lens effects are the useful ones for stage looks. Check against our own bloom recipes in B_visual_techniques before adopting. |
| 8 | **ShaderBuilder** (satoruhiga, MIT, 2024) | MIT | any | Palette-style on-the-fly GLSL material builder with PBR; Ctrl+Shift+B opens a palette; items dragged into the network. Relevant mostly as prior art for "generate a GLSL MAT from snippets" in an MCP (snippet library -> assembled shader DAT). |
| 9 | **Rust plugins** (thatmarcel fork of tychedelia/td-rs) | not stated (fork; check td-rs, MIT/Apache) | macOS + Windows | Rust Custom Operators (CHOP/TOP). Lasercube (WiFi laser), Unreal Engine Connection CHOP (TD<->UE values). Install path on macOS is `~/Library/Application Support/Derivative/TouchDesigner099/Plugins`; Custom OPs appear under "Custom" tab in OP Create. Unsigned binaries; Mac arm64 vs Rosetta (x86_64) arch mismatch is a risk: our TD runs under Rosetta so plugins must be x86_64. Not needed for PF26. |
| 10 | **TD Script / Blender add-on** (YouTube) | - | Mac OK | Already referenced in W/AA. Blender->TD data route; no repo. |
| 11 | **Python cheat sheets (IIHQ) + SOP cheat sheet (forum)** | page content, copyright holders | n/a | Reference tables to cross-check against our `ops/` dump. The forum SOP cheat sheet is a ready "which SOP do I want" map. Low effort to compare with `ops/` for missing family notes. |
| 12 | **Custom Operators doc page** | Derivative | n/a | C++ Custom OP/CPlusPlus TOP-CHOP-SOP-DAT. Only matters if the MCP ever needs a native op; Mac needs Xcode and Rosetta x86_64 build. |
| 13 | **touchDesigner_experiments** (davidedemarco) | none stated | any | ~25 `.toe` (not clearly licensed - do not copy): chaotic attractors (Thomas, Lorenz, Dadras, Langford; GPU-iterated), camera feedback + GPGPU instancing, fractal GLSL. Reading: .toe binary; use only the technique names. Duplicates what O_generative_simulations covers. |
| 14 | **ChopChopChop / The Tox Market / All TD** | per item | n/a | Marketplaces: ChopChopChop and Tox Market have both free and paid items; already have All TD in AA. Check per-item licence; audit rule applies. |
| 15 | **Awesome lists** (generative-art, creative-coding, audio-visualization, vjing) | CC0/BY-SA lists | n/a | Meta-lists, mostly non-TD (p5/three/Processing). Audio-visualization list is a source for MilkDrop-style presets and FFT mapping ideas only. |

## What the MCP should adopt

1. **Nothing urgent from this list** - it is a thin link-dump; the high-value entries (RayTK, MediaPipe, TDComponents, FunctionStore, Artio, GeoPix, DBraun shared, Shader Park, ISF, TDAbleton, TDComfyUI) are already in `N_`, `AM_`, `AJ_`, `AL_`, `D_`, `popular/github.md`.
2. **`td_shadertoy` (new, small):** paste Shadertoy source -> create a GLSL TOP with wrapper, uniforms (`iTime`, `iResolution`, `iMouse`, `iFrame`) as Vectors/Constants, per-shader licence note. Probes: GLSL TOP `mainImage` wrap compiles on 31550; `iChannel0..3` -> `sTD2DInputs[0..3]`; error reporting through `td_errors`.
3. **Utility-COMP recipe list from tektshared:** smoother, quantizer, gater, rate limiter, preset slots, recorder. Build as MCP macros on CHOP Lag/Math/Logic/Trigger rather than importing 2015 toxes.
4. **TDYolo route** (browser-as-inference, no pip) as a candidate "detection on Mac" path; probe WebGPU in the Web Render TOP first. Add to T_realtime_ml follow-ups.
5. **Optional SVG/plotter export** using the Ragan projection maths, written dependency-free.
6. **FUTURE.md flags:** touchpy (Windows/NVIDIA), StreamDiffusionTD (NVIDIA/TensorRT), TDDepthAnything (TensorRT), Spout (Windows) - already in the "not on this Mac" family; Rust plugins need x86_64 builds for Rosetta.

Gaps in the list itself: no MCP/agent/LLM-automation tools at all (no entries for Embody, TDPilot, twozero etc. - see `AF_peer_td_mcps.md`), no POP/GLSL-compute material, and nothing past 2025 on 2025.xx builds. Licence line of the list: README badge says CC BY-SA 4.0 (the label says CC0 but the badge image is BY-SA) - only cite, don't copy the text.

## Table of all 182 entries

Columns: name | URL | section | what it teaches/provides | MCP relevance 0-3 | dedupe.

| Name | URL | Section | Provides | Rel | Dedupe |
|---|---|---|---|---|---|
| 1. Introduction & Official Resources | #1-introduction--official-resources | Table of Contents | Table of Contents | 1 | NEW |
| 2. Learning Resources | #2-learning-resources | Table of Contents | Table of Contents | 1 | NEW |
| 3. Projects, Tools, & Community Assets | #3-projects-tools--community-assets | Table of Contents | Table of Contents | 1 | NEW |
| 4. Inspiration & Creative Techniques | #4-inspiration--creative-techniques | Table of Contents | Table of Contents | 1 | NEW |
| 5. Community & Social Engagement | #5-community--social-engagement | Table of Contents | Table of Contents | 1 | NEW |
| 6. Blogs, Articles, & Media | #6-blogs-articles--media | Table of Contents | Table of Contents | 1 | NEW |
| 7. Events, Meetups & Newsletters | #7-events-meetups--newsletters | Table of Contents | Table of Contents | 1 | NEW |
| 8. Artists & Studios | #8-artists--studios | Table of Contents | Table of Contents | 1 | NEW |
| 9. Other VJing Software | #9-other-vjing-software | Table of Contents | Table of Contents | 1 | NEW |
| 10. Contributing & License | #10-contributing--license | Table of Contents | Table of Contents | 1 | NEW |
| derivative.ca | https://derivative.ca | Official Links | Official Links | 2 | already covered: U_housekeeping_workspace.md H_control_panel.md |
| TouchDesigner Documentation | https://docs.derivative.ca/Main_Page | Official Links | Official Links | 2 | NEW |
| Download TouchDesigner | https://derivative.ca/download | Official Links | Official Links | 2 | already covered: R_show_safe_interactive.md |
| TouchDesigner Forum | https://forum.derivative.ca | Official Links | Official Links | 2 | already covered: U_housekeeping_workspace.md O_generative_simulations.md |
| TouchDesigner Tutorials - Official Documentation | https://docs.derivative.ca/Category:Tutorials | Tutorials | video/page tutorial | 1 | NEW |
| Custom Operators | https://derivative.ca/UserGuide/Custom_Operators | Tutorials | Derivative C++ CPlusPlus/Custom Operator docs (Custom OP, CPlusPlus TOP/CHOP/SOP/DAT) | 2 | NEW |
| Matthew Ragan's TouchDesigner Tutorials | https://matthewragan.com/teaching-resources/touchdesigner/ | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md G_network_layout.md |
| Interactive & Immersive HQ Tutorials | https://interactiveimmersive.io/ | Tutorials | video/page tutorial | 1 | already covered: U_housekeeping_workspace.md H_control_panel.md |
| Morphing between Objects | https://www.youtube.com/watch?v=2EwQSCZ0Hs8 | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Particle Clouds and Pseudo-Plexus | https://www.youtube.com/watch?v=ZgYxo6o-o9s | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Interactive Particles using particlesGpu | https://www.youtube.com/watch?v=NnrWjQ_zO-s | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Generate Shapes from an Image | https://www.youtube.com/watch?v=98xNOgU1zeI | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Pointclouds and Chromatic Aberration | https://www.youtube.com/watch?v=E6yRczNElTk | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Particle Flow and Energy Absorption | https://www.youtube.com/watch?v=zcaA8JvOSEM | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Custom Interactive 3D Particle System | https://www.youtube.com/watch?v=NuIShUTg3nI | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Sketchy Toon Shader | https://www.youtube.com/watch?v=VDBja6o8yvs | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md X_tutorials_workflow_output.md |
| Trace and Blob Tracking Effect | https://www.youtube.com/watch?v=qH94dipCJiw | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Audio-Reactive Psychedelic Visuals | https://www.youtube.com/watch?v=Mt2hwb5cngA | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Particle Attractors | https://youtube.com/watch?v=dzYyrvyY-zc&si=8aLXxedJflzaQfDQ | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Make Anything Audio Reactive | https://www.youtube.com/watch?v=rGoCbVmGtPE | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md X_tutorials_workflow_output.md |
| How to Dithering | https://www.youtube.com/watch?v=nOYQGxdpYgw | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| What is Generative Art: TouchDesigner’s Role in Art, Algorithms, and Creative Systems Explained | https://www.youtube.com/watch?v=1RD83NjwNIk | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Video to ParticlesGPU | https://www.youtube.com/watch?v=hrxn_ouFyV0 | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Simon Alexander Adams's Tutorials | https://www.simonaa.media/tutorials-articles | Tutorials | video/page tutorial | 1 | NEW |
| Working with Midi | https://www.youtube.com/watch?v=XLeghJmFBh0 | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| 3D Laser scanning dissipation | https://www.youtube.com/watch?v=Nqg8T4FtbRE | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| Mouse Attracted Particles | https://www.youtube.com/watch?v=0Obt8aL8G10 | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md X_tutorials_workflow_output.md |
| Learn TouchDesigner in 1 Hour (TouchDesigner for Beginners) | https://www.youtube.com/watch?v=gQdmocb-JBQ | Tutorials | video/page tutorial | 1 | already covered: W_tutorials_control_audio_python.md X_tutorials_workflow_output.md |
| TouchDesigner Official | https://www.youtube.com/@TouchDesignerOfficial | YouTube Channels | channel | 1 | NEW |
| Interactive & Immersive HQ | https://www.youtube.com/@TheInteractiveImmersiveHQ | YouTube Channels | channel | 1 | NEW |
| Reflekkt | https://www.youtube.com/@reflekkt_net | YouTube Channels | channel | 1 | NEW |
| exsstas | https://www.youtube.com/@exsstas | YouTube Channels | channel | 1 | NEW |
| DeanCheesman | https://www.youtube.com/@DeanCheesman | YouTube Channels | channel | 1 | NEW |
| Acrylicode | https://www.youtube.com/@acrylicode | YouTube Channels | channel | 1 | NEW |
| Matthew Ragan | https://www.youtube.com/@raganmd | YouTube Channels | channel | 1 | NEW |
| Luchen Xi - Alexxi | https://www.youtube.com/@Alexxi-generativeartist | YouTube Channels | channel | 1 | NEW |
| Lake Heckaman | https://www.youtube.com/@water__shed/playlists | YouTube Channels | channel | 1 | NEW |
| bileam tschepe (elekktronaut) | https://www.youtube.com/@elekktronaut | YouTube Channels | channel | 1 | NEW |
| PPPANIK | https://www.youtube.com/@pppanik | YouTube Channels | channel | 1 | NEW |
| DotSimulate | https://www.patreon.com/dotsimulate | YouTube Channels | channel | 1 | already covered: T_realtime_ml.md |
| Official Tutorials Playlist | https://www.youtube.com/playlist?list=PLzmoq9o8x48F3QEy2VGrakgP2p8gP4pqa | Playlists & Courses | Playlists & Courses | 1 | already covered: W_tutorials_control_audio_python.md |
| Matthew Ragan's In-Depth Tutorials | https://matthewragan.com/teaching-resources/touchdesigner/ | Playlists & Courses | Playlists & Courses | 1 | already covered: W_tutorials_control_audio_python.md G_network_layout.md |
| Summit Berlin 2018 | https://www.youtube.com/playlist?list=PLSqkC3f_BStzZ9CyGW9ahN8Sb_zoCWak1 | Playlists & Courses | Playlists & Courses | 1 | already covered: W_tutorials_control_audio_python.md |
| Workshop Norway 2016 | https://www.youtube.com/watch?v=fgs6DVdUkM0&list=PLSqkC3f_BStweh-7ZF8L3oyeJWLP2aYTw | Playlists & Courses | Playlists & Courses | 1 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| TouchDesigner Beginner Course | https://www.youtube.com/playlist?list=PLFrhecWXVn5862cxJgysq9PYSjLdfNiHz | Playlists & Courses | Playlists & Courses | 1 | already covered: W_tutorials_control_audio_python.md |
| The 100 Series: TouchDesigner Fundamentals | https://learn.derivative.ca/courses/100-fundamentals/ | Playlists & Courses | Playlists & Courses | 1 | already covered: O_generative_simulations.md B_visual_techniques.md |
| A Deep Dive into the Core Knowledge of TouchDesigner | https://www.udemy.com/course/gem-seed_touchdesigner-course-continuous-course-updates/ | Playlists & Courses | Playlists & Courses | 1 | NEW |
| Learning Touchdesigner | https://bookstack.hku.nl/books/touchdesigner/page/learning-touchdesigner | Playlists & Courses | Playlists & Courses | 1 | NEW |
| The NODE Institute | https://thenodeinstitute.org/ | Playlists & Courses | Structured TouchDesigner courses with certification program. | 1 | NEW |
| Gray Area TD Intensive | https://grayarea.org/ | Playlists & Courses | 12-week TouchDesigner course culminating in a public exhibition. | 1 | NEW |
| Common Operations Cheat Sheet | https://matthewragan.com/teaching-resources/touchdesigner/touchdesigner-common-operations-cheat-sheet/ | Cheat Sheets & Guides | Cheat Sheets & Guides | 2 | already covered: G_network_layout.md |
| Python Cheat Sheet for TouchDesigner Developers | https://interactiveimmersive.io/blog/python/python-cheat-sheet-for-touchdesigner-developers/ | Cheat Sheets & Guides | IIHQ td-Python basics (op(), par, tdu, run) | 2 | NEW |
| Python Cheat Sheet Part 2 (Intermediate) | https://interactiveimmersive.io/blog/python/python-touchdesigner-cheat-sheet-part-2-intermediate/ | Cheat Sheets & Guides | IIHQ intermediate (extensions, storage, callbacks) | 2 | NEW |
| Python in TouchDesigner / Extensions | https://matthewragan.com/2016/07/14/python-in-touchdesigner-extensions-touchdesigner/ | Cheat Sheets & Guides | Cheat Sheets & Guides | 2 | NEW |
| Understanding Extensions in TouchDesigner | https://matthewragan.com/2015/07/05/touchdesigner-understanding-extensions/ | Cheat Sheets & Guides | Cheat Sheets & Guides | 2 | already covered: W_tutorials_control_audio_python.md |
| TouchDesigner Keyboard Shortcuts | https://matthewragan.com/teaching-resources/touchdesigner/touchdesigner-keyboard-shortcuts/ | Cheat Sheets & Guides | Ragan shortcuts list (UI only) | 1 | NEW |
| SOP Cheat Sheet | https://forum.derivative.ca/t/sop-cheat-sheet-w-pics-wiki-mode/275002 | Cheat Sheets & Guides | Forum wiki-mode SOP op reference with pictures; handy for op-choice table | 2 | NEW |
| MIDI Device Beginner Guide | https://interactiveimmersive.io/blog/controlling-touchdesigner/midi-device-beginner-guide/ | Cheat Sheets & Guides | IIHQ MIDI In CHOP mapping basics | 1 | NEW |
| VJing tools and resources list | https://l68k.com/things/vjing | Cheat Sheets & Guides | l68k VJ link list | 0 | NEW |
| TDAbleton | https://github.com/search?q=TDAbleton | Plugins & Tools | Palette comp for Ableton; see AJ_td_ableton | 3 | NEW |
| Spout | http://spout.zeal.co/ | Plugins & Tools | Windows-only texture sharing; not usable on Mac | 0 | NEW |
| Syphon | http://syphon.v002.info/ | Plugins & Tools | macOS texture sharing; the Resolume route (see AI_td_resolume) | 3 | NEW |
| Rust Plugins | https://github.com/thatmarcel/touchdesigner-plugins | Plugins & Tools | td-rs fork: Rust CHOP/TOP plugins incl. Lasercube, Unreal link; macOS plugin path ~/Library/Application Support/Derivative/TouchDesigner099/Plugins | 1 | NEW |
| Community Extensions | https://forum.derivative.ca | Plugins & Tools | User-contributed custom operators and tools. | 2 | already covered: U_housekeeping_workspace.md H_control_panel.md |
| Pixel Maps (Artio) | https://github.com/theexperiential/Artio | Plugins & Tools | Pixel map / DMX mapping tox; see AB | 2 | already covered: AB_projection_mapping.md N_community_components.md |
| SOP To SVG Converter | https://github.com/raganmd/touchdesigner-sop-to-svg | Plugins & Tools | Ragan svgEXT class: SOP->SVG via svgwrite (camera projection math); 2018 TD099 - Python 3.5 install notes outdated, MIT | 2 | already covered: popular/github.md |
| Constraint Simulation Tool | https://derivative.ca/community-post/asset/constraint-simulation-tool/65109 | Plugins & Tools | Derivative community post 65109; physics constraints COMP | 1 | NEW |
| TD Script - Blender Add-on for TouchDesigner | https://www.youtube.com/watch?v=olRMbGqgxp0 | Plugins & Tools | Integrate Blender with TouchDesigner | 2 | already covered: W_tutorials_control_audio_python.md AA_typography_effects.md |
| MediaPipe | https://github.com/torinmb/mediapipe-touchdesigner | Plugins & Tools | torinmb GPU MediaPipe; see D_camera_mediapipe | 3 | already covered: D_camera_mediapipe.md J_interactive_camera_effects.md |
| GeoPix | https://github.com/EnviralDesign/GeoPix | Plugins & Tools | GeoPix is a free and open source real-time lighting control and previz software. | 2 | already covered: N_community_components.md community/slice_07.md |
| TouchDiffusion | https://github.com/olegchomp/TouchDiffusion | Plugins & Tools | Real-time Stable Diffusion interactive generation with StreamDiffusion | 2 | already covered: popular/github.md |
| RayTK | https://github.com/t3kt/raytk | Plugins & Tools | t3kt raymarching toolkit; hundreds of operators as COMPs | 3 | already covered: P_realtime_3d_looks.md N_community_components.md |
| Simple Mixer | https://github.com/Richard-Burns/SimpleMixer | Plugins & Tools | A Video mixer build in TouchDesigner. | 2 | already covered: H_control_panel.md |
| touchFluid | https://github.com/kamindustries/touchFluid | Plugins & Tools | Fluids in TouchDesigner and GLSL | 2 | already covered: J_interactive_camera_effects.md O_generative_simulations.md |
| touchfluids | https://github.com/ancillarymagnet/touchfluids | Plugins & Tools | Newtonian fluids in TouchDesigner | 2 | already covered: O_generative_simulations.md |
| TDComfyUI | https://github.com/olegchomp/TDComfyUI | Plugins & Tools | see AL_td_comfyui | 2 | already covered: AL_td_comfyui.md |
| TouchEngine-UE | https://github.com/TouchDesigner/TouchEngine-UE | Plugins & Tools | The TouchEngine-UE plugin allows UE developers to load TouchDesigner components within UE while relying on the TouchEngine API. | 2 | already covered: popular/github.md community/slice_06.md |
| Style Transfer | https://github.com/exsstas/StyleTransfer-in-TD | Plugins & Tools | TensorFlow implementation of Neural Style Transfer in TouchDesigner | 2 | already covered: popular/github.md |
| TDDiffusionAPI | https://github.com/olegchomp/TDDiffusionAPI | Plugins & Tools | TouchDesigner interface for AUTOMATIC1111 | 2 | already covered: popular/github.md |
| FunctionStore Tools | https://github.com/function-store/FunctionStore_tools | Plugins & Tools | TouchDesigner workflow tools and UX improvements and more | 2 | already covered: O_generative_simulations.md W_tutorials_control_audio_python.md |
| Luminosity | https://github.com/IntentDev/Luminosity | Plugins & Tools | Front-end for TouchDesigner aimed at providing operators with an efficient interface to perform, control, and distribute realtime media while retaining the open-ended programmability of TouchDesigner. | 2 | already covered: popular/github.md |
| TD Completes Me | https://github.com/picturesbyrobots/td-completes-me | Plugins & Tools | A Simple Auto Completion Engine for Touch Designer | 2 | already covered: popular/github.md |
| ShaderBuilder | https://github.com/satoruhiga/TouchDesigner-ShaderBuilder | Plugins & Tools | Satoru Higa on-the-fly GLSL node-ish builder with PBR; palette-style tox; MIT; 61 MB repo (not cloned) | 2 | NEW |
| PostEffects | https://github.com/yasuhirohoshino/TouchDesigner_PostEffects | Plugins & Tools | Bloom, camera motion blur, lens effects, DoF, SSAO, SSR as .tox; MIT; 53 MB (not cloned); SSAO/SSR need depth - check macOS | 2 | NEW |
| Shader Park | https://github.com/shader-park/shader-park-touchdesigner | Plugins & Tools | Render Shader Park sculptures in TouchDesigner | 2 | already covered: N_community_components.md |
| Image and Video Abstraction | https://github.com/yeataro/TD-Flow-ABS | Plugins & Tools | Real-time Flow-based Image and Video Abstraction in TouchDesigner. | 2 | already covered: N_community_components.md |
| ISF TouchDesigner | https://github.com/marcinbiegun/isf-touchdesigner | Plugins & Tools | TouchDesigner component for working with ISF shader generators and filters | 2 | already covered: N_community_components.md |
| ShaderToyTouchdesigner | https://github.com/SebastienGravel/ShaderToyTouchdesigner | Plugins & Tools | Paste Shadertoy code into a DAT -> GLSL TOP wrapper (iResolution/iMouse/iGlobalTime); 60% of shaders work; no audio, issues with cubemaps/raymarch; 2016 (TD 099 era) | 2 | NEW |
| TouchDesigner Shared Components | https://github.com/DBraun/TouchDesigner_Shared | Plugins & Tools | Repository of shared components and project files. | 2 | already covered: O_generative_simulations.md N_community_components.md |
| TDComponents | https://github.com/dylanroscover/TDComponents | Plugins & Tools | A whimsical collection of everyday TouchDesigner components | 2 | already covered: AM_tdxcomponents.md |
| tektshared | https://github.com/t3kt/tektshared | Plugins & Tools | t3kt 2015 shared tox set: paramsmoother, quantizer, gater, preset slots, recorder, kaleidoscope, MIDI-controller maps; old API, pattern source only | 2 | NEW |
| TD Voronoi | https://github.com/yeataro/TD_Voronoi | Plugins & Tools | JFA Voronoi Video Filter in TouchDesigner | 2 | already covered: N_community_components.md |
| TDDepthAnything | https://github.com/olegchomp/TDDepthAnything | Plugins & Tools | TouchDesigner implementation for Depth Anything and TensorRT monocular depth estimation. | 2 | already covered: popular/github.md |
| StreamDiffusionTD | https://dotsimulate.com/docs/streamdiffusiontd | Plugins & Tools | dotsimulate, NVIDIA/TensorRT only | 1 | already covered: X_tutorials_workflow_output.md |
| Terrain Tools | https://github.com/CraftKontrol/Terrain-Tools-for-Touchdesigner | Plugins & Tools | Terrain/water/tree/grass/PBR GLSL MATs, LOD instancer, boids, volumetric fog, lens flare; MIT; 41 MB (not cloned) | 2 | NEW |
| TouchPy | https://github.com/IntentDev/touchpy | Plugins & Tools | Headless TouchEngine from Python w/ CUDA/Vulkan zero-copy; Windows+NVIDIA only; MIT; reference for TouchEngine API | 1 | NEW |
| TDYolo | https://github.com/patrickhartono/TDYolo | Plugins & Tools | YOLO11 in TD via embedded headless browser (no pip), report/summary DAT outputs; Win+macOS(Metal); needs internet; MIT; 905 MB repo (not cloned) | 2 | NEW |
| TDNeuron | https://github.com/tdneuron/TDNeuron | Plugins & Tools | GLSL deep-learning framework; research only | 1 | already covered: N_community_components.md |
| All TD | https://alltd.org/ | Assets & Marketplaces | Comprehensive library of community-shared assets. | 2 | already covered: AA_typography_effects.md |
| ChopChopChop | https://chopchopchop.org/ | Assets & Marketplaces | Curated asset marketplace; check licence per asset | 2 | NEW |
| Palette | https://docs.derivative.ca/Palette | Assets & Marketplaces | Community-contributed TouchDesigner components and tools. | 2 | already covered: W_tutorials_control_audio_python.md AE_realtime_interactive_design.md |
| The Tox Market | https://thetoxmarket.com/ | Assets & Marketplaces | Commercial/free .tox marketplace; per-item licence | 1 | NEW |
| Awesome Generative Art | https://github.com/kosmos/awesome-generative-art | Generative Art | Generative Art | 0 | NEW |
| Awesome Creative Coding | https://github.com/terkelg/awesome-creative-coding | Generative Art | Generative Art | 0 | NEW |
| Shaders For Absolute Beginners | https://clauswilke.com/art/post/shaders | Generative Art | Generative Art | 0 | NEW |
| Awesome Audio Visualization | https://github.com/willianjusten/awesome-audio-visualization | Audio-Visual Integration | Audio-Visual Integration | 0 | NEW |
| Awesome VJing | https://github.com/LimeLimeW/awesome-vjing | VJing | VJing | 0 | NEW |
| Awesome TouchDesigner (GitHub Search) | https://github.com/search?q=awesome+touchdesigner | Community Projects & Repositories | Discover community-curated repositories and lists. | 1 | NEW |
| TouchDesigner Playground | https://github.com/riebschlager/touchdesigner-playground | Community Projects & Repositories | riebschlager sketches 2020, 57 MB; no licence | 1 | NEW |
| TouchDesigner Research Repository | https://github.com/chungbwc/TouchDesigner | Community Projects & Repositories | Advanced research and explorations in TouchDesigner. | 1 | already covered: popular/github.md |
| Generative Design Projects | https://github.com/TouchDesigner/GenerativeDesign | Community Projects & Repositories | Projects focused on generative design and creative coding. | 1 | already covered: popular/github.md |
| TouchDesigner Experiments | https://github.com/davidedemarco/touchDesigner_experiments | Community Projects & Repositories | ~25 .toe experiments: chaotic attractors (Thomas, Lorenz, Dadras, Langford), GPGPU instancing feedback, fractals; no licence stated | 1 | NEW |
| TouchDesigner Projects Samples | https://github.com/knotidm/TouchDesigner-Projects/ | Community Projects & Repositories | knotidm 1.3 GB samples; GLSL; no licence; too big to clone | 1 | NEW |
| TouchDesigner Forum | https://forum.derivative.ca | Forums & Groups | community venue | 1 | already covered: U_housekeeping_workspace.md O_generative_simulations.md |
| r/TouchDesigner on Reddit | https://www.reddit.com/r/TouchDesigner/ | Forums & Groups | community venue | 1 | NEW |
| Instagram (@touchdesigner) | https://www.instagram.com/touchdesigner | Forums & Groups | community venue | 1 | NEW |
| TikTok | https://www.tiktok.com/search?q=touchdesigner | Forums & Groups | community venue | 1 | NEW |
| TouchDesigner Slack | https://touchdesigner.slack.com/ | Forums & Groups | community venue | 1 | NEW |
| TouchDesigner Discord | https://discord.com/invite/senqbr2 | Forums & Groups | community venue | 1 | NEW |
| Facebook Help Group | https://www.facebook.com/groups/touchdesignerhelp/ | Social Media & Showcases | Social Media & Showcases | 0 | NEW |
| Behance TouchDesigner Projects | https://www.behance.net/search/projects/touchdesigner | Social Media & Showcases | Social Media & Showcases | 0 | NEW |
| Explore TouchDesigner on Medium | https://medium.com/tag/touchdesigner | 6. Blogs, Articles & Media | 6. Blogs, Articles & Media | 1 | NEW |
| Official Learning Blog | https://learn.derivative.ca/ | 6. Blogs, Articles & Media | 6. Blogs, Articles & Media | 1 | already covered: J_interactive_camera_effects.md O_generative_simulations.md |
| Matthew Ragan's Blog | https://matthewragan.com/blog/ | 6. Blogs, Articles & Media | 6. Blogs, Articles & Media | 1 | NEW |
| TouchDesigner Resources by Matthew Ragan | https://matthewragan.com/teaching-resources/touchdesigner/ | 6. Blogs, Articles & Media | 6. Blogs, Articles & Media | 1 | already covered: W_tutorials_control_audio_python.md G_network_layout.md |
| Interactive Immersive | https://interactiveimmersive.io/blog/ | 6. Blogs, Articles & Media | 6. Blogs, Articles & Media | 1 | already covered: U_housekeeping_workspace.md AL_td_comfyui.md |
| TouchDesigner Meetups on Meetup.com | https://www.meetup.com/find/?keywords=touchdesigner | Events & Meetups | Events & Meetups | 0 | NEW |
| Derivative Workshops & Events | https://derivative.ca/workshops-events | Events & Meetups | Events & Meetups | 0 | NEW |
| Community Calendar on Forum | https://forum.derivative.ca | Events & Meetups | Events & Meetups | 0 | already covered: T_realtime_ml.md U_housekeeping_workspace.md |
| Derivative Newsletter | https://derivative.ca/derivative-newsletter/subscription | Newsletter & Media | Newsletter & Media | 0 | NEW |
| Interactive Immersive | https://interactiveimmersive.io/ | Newsletter & Media | Newsletter & Media | 0 | already covered: E_live_rig.md H_control_panel.md |
| Pauric Freeman | https://www.instagram.com/pauric_freeman/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| ghostsmakemusic | https://www.instagram.com/ghostsmakemusic/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| gip.hy | https://www.instagram.com/gip.hy/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| Anastasia Lapotko | https://www.instagram.com/anastasialapotko/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| bonnie2.0.0 | https://www.instagram.com/bonnie2.0.0/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| dith_idsgn | https://www.instagram.com/dith_idsgn/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| Jason Beyers | https://jasonbeyers.com/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| Cullen Hassel | https://www.instagram.com/cullenhassel/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| zpacetree | https://www.instagram.com/zpacetree | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| fractaledvisions | https://www.instagram.com/fractaledvisions | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| cerspense | https://www.instagram.com/cerspense | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| Android Jones | https://androidjones.com/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| actualizevisuals | https://www.instagram.com/actualizevisuals | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| Weidi Zang | https://www.instagram.com/w.e.i.d.i/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| Pieter Sistrom | https://www.instagram.com/archo_p/?hl=fr | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| Simon AA | https://www.simonaa.media/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| Okamirufu | https://www.patreon.com/Okamirufu | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| Torin Blankensmith | https://www.torinblankensmith.com/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| Glazov AV | https://www.instagram.com/glazov_av | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| Luchen Xi - Alexxi | https://www.instagram.com/luchen_xi/ | Featured Artists | artist showcase (inspiration only) | 0 | NEW |
| NONOTAK | https://www.nonotak.com/ | Featured Artists | Immersive light and sound installations. | 0 | already covered: S_trend_scan_2024_2026.md |
| TUNDRA | https://wearetundra.org/ | Featured Artists | New media art collective working with A/V performances, light, and robotic art. | 0 | NEW |
| Le Studio Dynamic | https://www.lestudiodynamic.com/ | Studios | Studios | 0 | NEW |
| vvvv | https://vvvv.org | 9. Other VJing Software | A visual live-programming environment that takes you from rapid prototyping to final production. | 1 | NEW |
| VJAMM | https://www.vjamm.com/ | 9. Other VJing Software | A piano for sound and vision, audio visual performance software. | 1 | NEW |
| Zwobotmax.com | https://www.zwobotmax.com/ | 9. Other VJing Software | Play videos and create visuals right inside Ableton Live. | 1 | NEW |
| MilkDrop3 | https://github.com/milkdrop2077/MilkDrop3 | 9. Other VJing Software | MilkDrop 3.0, supports any audio source, double-preset (.milk2), loading presets based on beat detection and much more... | 1 | NEW |
| VDMX6 | https://www.vidvox.net/ | 9. Other VJing Software | The ultimate real-time video playground for macOS just got a whole lot more ultimate. | 1 | already covered: K_audio_reactive.md L_shader_sources_licences.md |
| Resolume | https://www.resolume.com/ | 9. Other VJing Software | Resolume is the industry-leading software for VJ’s around the world. | 1 | already covered: E_live_rig.md A_td_2025_howto.md |
| HeavyM | https://www.heavym.net/vj-software/ | 9. Other VJing Software | VJ software for projection mapping. | 1 | NEW |
| Modul8 | https://www.garagecube.com/modul8/ | 9. Other VJing Software | The pioneering macOS VJ application. | 1 | NEW |
| ArkaOS GrandVJ | https://vj.arkaos.com/grandvj/ | 9. Other VJing Software | VJ software for live video performance. | 1 | NEW |
| Synesthesia | https://synesthesia.live/ | 9. Other VJing Software | The All-in-One Music Visual Solution. | 1 | NEW |
| Millumin | https://www.millumin.com/v5/ | 9. Other VJing Software | Complete solution to create Audiovisual Shows. | 1 | NEW |
| Lumen | lumen-app.com | 9. Other VJing Software | Video Synthesis On Your Mac. | 1 | NEW |
| Quantum VJ HD | https://www.warmplace.ru/soft/qvjhd/ | 9. Other VJing Software | Simple glitch-style audio visualizer (video generator). | 1 | NEW |
| Noisedeck | https://noisedeck.app/ | 9. Other VJing Software | An approachable, powerful video synth and a must-have for any creator's toolkit. | 1 | NEW |
| aNa | https://gitlab.com/metagrowing/ana | 9. Other VJing Software | A live coding system for visuals. | 1 | NEW |
| GoVJ | https://govjapp.com/ | 9. Other VJing Software | Allows you to run your live visual mix, straight from your iPhone or iPad. | 1 | NEW |
| Magic | https://magicmusicvisuals.com/ | 9. Other VJing Software | Fully-customizable and highly responsive visuals for live and recorded audio & MIDI. | 1 | NEW |
| Notch | https://www.notch.one/ | 9. Other VJing Software | Real-time 3D motion graphics and VFX for live events and broadcast. | 1 | already covered: B_visual_techniques.md J_interactive_camera_effects.md |
