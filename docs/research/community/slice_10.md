# Community slice 10: derivative.ca/community pages 180-196 (oldest posts)

Crawled 26 Oct 2026. Data: `research_src/community/slice_10.jsonl` (251 records). Relevance is scored 0-3 for general
TouchDesigner mastery (any use case), per the revised brief. Target build for the reader: **2025.31550**.

## Counts
- Listing pages 180-196 each held 20 rows; 5 of them are a "featured" strip repeated on every page (ids 75551, 75535,
  75538, 75560, 75562, not in my slice, left to the newer slices). 251 unique posts read, 0 failed fetches, 0 skipped.
- By type: post 181 (almost all Derivative "TouchDesigner in the wild" press features by `isabelle`), tutorial 26,
  asset 22, workshop 18, event 3, other 1.
- Date spread: 2019 = 56 (the only dense block of assets/tutorials, Oct-Nov 2019), 2013-2018 = ~110 (features),
  2001-2012 = ~65 (historic press, near zero technical content).
- Relevance: 3 = 8, 2 = 31, 1 = 145, 0 = 67.
- **Everything here predates TD 2020: built for 099 (2017-2019) or earlier (077/088).** Treat as concepts, not recipes.
  No POPs, no 2023+ GLSL/Python 3.11 changes, no Vulkan/Apple-Silicon. Python in these files is 3.5.
- Mac status is rarely stated: marked `unknown` unless the post says so (pure-TD tox files almost certainly open on Mac).

## Top 15 by relevance
1. **61132 Introduction to GLSL in TouchDesigner** (vinz99, workshop Jul 2018, posted Oct 2019): 8-part YouTube series +
   notes PDF + `workshop_day_with_extra.2.toe` (downloaded). GLSL TOP/MAT basics; syntax still valid, OpenGL-era details need checking vs Vulkan.
2. **61021 Modular Architectures** (mir.works, TD Summit 2019): extensions, inheritance, env variables, sandbox; repo cloned (`large-systems-finished`).
3. **61022 External Python Libraries** (mir.works): pip/sys.path handling, per-project libs, dominant-colour example; repo cloned. Python 3.5 era, ideas still apply.
4. **61023 Template Toxes** (mir.works / Matthew Ragan): reusable tox template with extensions + external libs, MIT repo cloned.
5. **61020 GitHub & External Toxes** (mir.works): git workflow with external .tox files, 3 short Vimeo videos.
6. **61081 TouchDesigner + Resolume bidirectional** (tolch, ES/EN video): Resolume FFGL "dummy parameter" plugins (4/8/12/16 params) in Resolume `plugins/vfx` fed by TD over OSC, video over Syphon/Spout. Repo `Leskos/FFGLDummyParams` cloned (dll is Windows; sources included).
7. **61072 Texture Sharing with TouchDesigner** (elburz): decision guide NDI / Spout / Syphon / Touch In-Out / shared mem. Link-post to interactiveimmersive.io.
8. **61086 RTK Raymarching Toolkit** (hrtlacek): node-based SDF raymarching tox, depth-buffer integration with TD renderer, reflection/refraction, soft shadows (MERCURY hg_sdf + iq formulas). Cloned by another slice; 13 MB.
9. **61146 timeBase** (greg): multi-layer timeline COMP (Scenes > Layers > Elements), custom-parameter driven, v15 tox downloaded (1.5 MB).
10. **61135 Simple Mixer** (Ennui / Richard Burns): open-source (Unlicense) VJ tox/video mixer built fully in TD, repo cloned (39 MB, `simplemixer.toe`, Lib/ tox modules, post-FX).
11. **61075 Tau Ceti Preset Engine** (alphamoonbase): stack-of-parameter-references preset manager with tweener interpolation; pattern for show state recall.
12. **61123 How-To Audio in TouchDesigner** (owenkirby): .toe of audio generation techniques + troubleshooting (downloaded, 1.4 MB).
13. **61100-61102 TDAbleton series** (elekktronaut): connect TD to Ableton Live 10, map kick velocity / keyboard notes to visuals + feedback.
14. **61043 Output Controller** (alphamoonbase) and **61073 Autosave tox** (cataliz3er): small show-safety tools (multi-display perform output; 15-min autosave with incremented backup). Both downloaded, a few KB.
15. **62036 Point Clouds in TouchDesigner** (snaut, 3-part video: instancing, star database, point clouds) and **60780 / 60779 MUTEK 2012 / Norway 2016 workshop videos** (Derivative devs, fundamentals; Norway zip is on Dropbox, not fetched).
Also 2: 61133 render quality/PBR, 61051 blob-tracking tricks, 61024 reflections & refractions, 62041 Line MAT, 61121 ZIG SIM PRO (OSC/NDI sensor app), 61078 INSIDE DOME (fisheye/dome UV), 61052 multi-noise TOP module (vjzual4), 60709 coral feedback look (Blur+Edge+Feedback TOPs), 60694 Threshold TOP+Trace SOP line art, 60765/60720/60681 community performance apps (DEVISION, Luminosity).

## Files downloaded (17 attachments, 7.9 MB; plus 8 git clones, ~48 MB)
Nothing was opened, run or loaded. Zip contents listed only. Derivative `/file/<n>/download?token=` links needed no login. Licences are almost never stated on derivative.ca; "not stated" below means exactly that.

| post | path under `research_src/community/files/` | what | licence | build |
|---|---|---|---|---|
| 61146 | `61146/timebase.15_1.tox` (1.5 MB) | timeBase v15 timeline COMP | not stated | 099 2019.10000 |
| 61132 | `61132/07_14_2018_glsl_in_touchdesigner_with_extra_sample.zip` | zip: `TD GLSL Workshop Notes.pdf`, `workshop_day_with_extra.2.toe` | not stated | 099 2018-19 |
| 61123 | `61123/howtoaudio_0.toe` (1.4 MB) | audio generation guide | not stated | 099 2019 |
| 61078 | `61078/INSIDE_DOME_V3.3.tox` (1.6 MB) | dome/fisheye preview + record | not stated | 099 2019 |
| 61077 | `61077/camfly2.tox` | joystick fly camera | not stated | 099 2019 |
| 61073 | `61073/autosave.tox` | autosave component | not stated | 099 2019 |
| 61061 | `61061/box_fillet_01a.toe` | box with fillet/chamfer SOP/GLSL | not stated | 099 2019 |
| 61059 | `61059/multislider.tox`, `multisliderdoc.zip` (PDF), `tdsliders.zip` (`TDsliders.touchosc`) | OSC multislider | not stated | 099 2019 |
| 61055 | `61055/gemotryinterpolationshader.tox` | geometry interpolation shader | not stated | 099 2019 |
| 61054 | `61054/flamevortex.tox` | NVIDIA Flow flame vortex (Windows/NVIDIA) | not stated | 099 2019 |
| 61048 | `61048/mytimer.tox`, `mytimer.zip` (contains myTimer.tox) | timer COMP | not stated | 099 2019 |
| 61043 | `61043/1_3_outputcontroller.zip` | `outputController.tox`, `version_info.json` | not stated | 099 2019 |
| 61007 | `61007/td_localization.tox` | TD UI localisation | MIT (repo) | 099 2019 |
| 61004 | `61004/introduccion_td_categorias_operadores.1.toe` | Spanish intro to operator families | not stated | 099 2019 |

Git clones (`--depth 1`, commit in the jsonl): `61108` DistThresholdCHOP (MIT, C++ sln, Windows) cac985b321d7; `61135` SimpleMixer (Unlicense) dcec03a87a2e; `61059` TD_mutiSlider d40cce576bef; `61023` touchdesigner-template-tox-dev (MIT; `assets`, `dev/dev-env.toe`, `td-modules`) 25bba9a721ef; `61022` summit-2019-external-python (`ext-python`, `dev-template`, `dominant-color`, `*-finished/*.toe`) bc69b999d3a7; `61021` summit-2019-large-systems (`inheritance-example`, `environment-variables`, `sandbox`, `tools`, `large-systems-finished`) ce94baba6fff; `61081` FFGLDummyParams (`dll/FFGLDummyParams.dll`, VS project, `src`) ccd027d59668; `60683` TouchDesigner_fadecandy (`TDfadecandy.toe`, fadecandy server config) dc90c77e20db.
Already present from another slice (not mine, listed only): `62053/FlexCHOP` (MIT, be1592ca9c), `61007/TD-Localization` (MIT, 44fb88cf0b), `61086/TDraymarchToolkit` (052d2e526d, hg_sdf licence applies), `61056/repo_t3kt__TektTDCommon` (0b1a8d2409), `61048/repo_jhoepffner__TD_myTimer` (ccdd961104).
Not downloaded: 7 slide `.jpg` in 61004; GitHub release dll zips (FlexCHOP, DistThreshold: binary); Dropbox Norway workshop zip (external, unknown size); `indaehwang.com` example toes (external site); Vimeo/YouTube videos.

## Recurring techniques and ops
- Operators named most: Noise/Composite/Feedback/Blur/Edge/Threshold TOPs, Blob Track TOP, NDI In TOP, OSC In/Out CHOP, Trace/Copy SOP, Line MAT, PBR MAT, Cam COMP, Leap Motion CHOP, Window COMP (output controller).
- Patterns: Python extensions + custom parameters as the "best-practice" component style (timeBase, Modular Architectures); stored presets with tweened recall (Tau Ceti); external tox + git; OSC remote surfaces (TouchOSC, ZIG SIM); texture sharing between apps (NDI/Spout/Syphon); reaction-diffusion by Feedback+Blur+Edge; dome/fisheye UV; custom C++ ops (FlexCHOP, DistThreshold, TektTDCommon).
- Mac-relevant: Syphon for Resolume, NDI, OSC; TDAbleton (path in the tutorial is Windows, Mac Remote Scripts folder differs).

## Authors who post a lot
`isabelle` (Derivative, 180 of 251; press features), Derivative (21 workshop/event pages), `tolch` (6, Spanish tutorials incl. the Resolume one), `mir.works` (6, TD Summit 2019 and refraction series; Matthew Ragan / Zoe Sandoval), `elburz` (5, link-posts to interactiveimmersive.io), `vinz99`, `elekktronaut`, `Darien.Brito` (3 each).

## Windows-only / NVIDIA-only
FlexCHOP 62053 (CUDA FleX, Windows dll), DistThresholdCHOP 61108 (Windows dll; source builds elsewhere), Flame Vortex 61054 (NVIDIA Flow), Install-TD-Experimental 61095 (Windows .bat, obsolete since 2020.23680), FFGLDummyParams dll (Windows, source available), Spout part of 61081/61072 (Mac uses Syphon).

## Skipped
None. No leak/crack/rights-problem posts found in this range (regex hits were false positives in page markup). Patreon/paid items: none seen.

## Open questions
- Does the Resolume FFGL dummy-parameter approach (61081) still beat OSC-only on Arena 7.23.2 on Mac? Needs a Mac FFGL build from the repo `src`.
- Do timeBase, Output Controller, Tau Ceti, Autosave still load cleanly in 2025.31550 (Python 3.5 -> 3.11, deprecated par/op names)? Not tested; nothing was opened.
- TD Summit 2019 repos: the `*-finished` tox/toe files should be loaded in a throw-away project first; expect extension API drift.
- The newer slices carry the real 2020-2026 asset flow; this slice is mainly a 2019 snapshot plus 2001-2018 press.
- Oldest-page duplicates: several of my posts (61007, 61048, 61056, 61059, 61086, 62053) already had folders from another slice, so listing pages overlap or shifted while crawling; dedupe by id when merging.
