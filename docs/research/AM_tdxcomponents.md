# AM: TDXComponents (dylanroscover) read for jazib-td (26 Oct 2026)

Read-only static study. Nothing was loaded into TouchDesigner, no `jazib-td` tool was called, no Python/GLSL from the files
was run. Tags: [FS] read from the expanded files, [DUMP] `ops/INDEX_2025.31550.json`, [L] our LEARNINGS, UNVERIFIED = needs a probe.
Source: https://github.com/dylanroscover/TDXComponents, commit `1433c7bdaafc63c5056ef0f037c41cdcf0d719b2` (19 Aug 2026,
"Rename dev .toe files to TDXComponents naming"), GPL-3.0 (licence does not matter for research; it matters if code is copied
into jazib-td, so port ideas, not files). Local: `research_src/peers/TDXComponents/` (clone), `research_src/peers/TDXComponents_expanded/<name>/`
(one folder per tox, made with `toeexpand` on a copy; plus `dev_toe/`). The author is the same as Embody/Envoy (AF).

## 1. Summary

- The repo is **9 release `.tox` files + 2 byte-identical dev `.toe`** (`dev/TDXComponents-0.1.toe` == `...-0.1.232.toe`, `cmp` equal)
  + 1 sample masks TSV + 1 sample `.chan`. Small, plain TD: a CHOP recorder, a curve grader, an LED-map compositor, a
  timecode renderer, a mask editor and four helpers. **No MCP, no network, no web ops, no threads.**
- **"Windows only" was a label, not a limit.** README line 4 says "TouchDesigner 2025.31550 (Windows)"; the dev toe's save
  script hard-codes the string `(Windows)` into the README on every save. 8 of 9 toxes were saved on Windows 10, but
  `chop_recorder` was saved on **macOS 14.5** and carries a `Darwin` branch. No file calls a Windows API, DirectX, CUDA or NVIDIA
  anything. Real Windows-leaning bits are small (section 4): the Timecode font list, Masker's Multi Touch In DAT, Masker's mouse path.
- **Every operator type exists in 2025.31550** (checked all 11 packs against the dump with a short-name alias map:
  `chopexec`=chopexecuteDAT, `par`=parameterCHOP, `geo`=geometryCOMP, `comp`=compositeTOP, `tex3d`=texture3dTOP, ...). Only three types
  are absent from the dump: `keyboardinDAT`, `mouseinCHOP`, `multitouchinDAT` (input ops; the dump omits them, AE confirms they exist and Multi Touch In is Windows-only).
  All non-custom parameter names exist too (the only misses are sequence-block pars: `vec#name`, `const#value`, `array#chop`, `iop#op`, `ext#object`).
- **Best finds for us:** (1) **Comper**, a GLSL compositor that places native-resolution inputs in a bigger canvas with per-input
  crop/translate/rotate/scale/level/matte, "primarily for simple LED mapping": a direct fit for the R02 nine-face canvas;
  (2) **Optimeister**, a clean example of *proxy custom pars bound to a child operator's built-in pars* (a pattern `td_custom_pars` lacks);
  (3) **Hexler**, ten lines of hex<->RGB we should have in `td_set_pars`; (4) **Chop Recorder**, record any CHOP to a `.chan` and replay it
  (repeatable audio/OSC feature tracks for offline bakes); (5) the way the author stamps an **About page** (Version, Touch Build, GitHub) and
  versions on save. Color Curves is a good grader but the only multi-pass-GLSL part (histogram) falls under T-46.
- **Relation to Embody/Envoy (AF):** same author, no shared code or dependency. TDX is the older "externaltox in a dev .toe" workflow
  (`externaltox ../release/<name>-v<ver>.tox`, tag `TDComponent`, `parentshortcut`), which Embody later automates (TDN/TDXN). TDX has no
  MCP hooks; its state lives in custom pars, so any of it is already drivable through `td_set_pars` / `td_custom_pars`.
- **Build saved with vs 31550** (from each `.build`): color_curves, optimeister, timecode = **2025.31550 exactly**; comper and the dev toe =
  **2025.32050** (one step newer; nothing we found needs it); chop_recorder 2023.11880, hexler/playback/step_n_repeat 2023.11760, masker 2023.12230
  (two years older: defaults can shift on load, probe with `td_custom_pars` + `td_errors`). The `Touchbuild` custom par is a free text stamp and
  often disagrees with the file (color_curves says 2023.12230, optimeister 2023.11340): trust `.build`.
- **Safe to load all nine into a scratch COMP, none into the home rig** (gated by the user's go-ahead). Nothing here runs a subprocess except
  `open <folder>` on one pulse, and no pickled storage holds code (the 21 storage dicts in the nine toxes, plus 3 in the dev toe, were disassembled with `pickletools`: plain dicts, no GLOBAL/REDUCE opcodes).

## 2. Per-component table

| Component | Ver / saved | What it does | How it is built | Mac / 31550 | Use here (a) | Port (b) |
|---|---|---|---|---|---|---|
| **chop_recorder** | 0.2.30, macOS 14.5, 2023.11880 | Record a multi-channel CHOP to `.chan` for N seconds, replay it (one-shot/loop), pick file from a menu | 69 ops: Timer CHOPs (record/play), File Out/In CHOP, Folder DAT -> Table -> Replicator of per-channel `Lookup` bases, 14 custom pars, ParExec/Execute/Timer callbacks | OK (saved on Mac, `Darwin` branch) | Medium: freeze audio-feature/OSC/LFO tracks for a repeatable bake | `td_record_chop` idea (record/replay + folder menu) |
| **color_curves** | 3.0.0, Win, 2025.31550 | Per-channel (Master/R/G/B) curve grading of a TOP: click to add points, right-click remove, presets in JSON, split compare, histogram | 1262 ops (3195 files, most are widget copies): per channel Polyspline SOP -> SOP to CHOP -> CHOP to TOP -> **Lookup TOP**; Render + Render Pick CHOP for the handles; Derivative Palette `popMenu`/`lister`/button widgets; 4 Annotate COMPs; 22 custom pars | OK except the histogram (3 chained GLSL passes: T-46) | Yes, grade stage: Preview off, Handles on | Annotate-as-title boxes (we have them); preset-in-DAT JSON pattern |
| **comper** | 2.1.0, Win, **2025.32050** | GLSL compositor: up to 32 TOP layers on a custom canvas; per layer crop, translate (px or fraction), rotate, scale, level, matte colour; pivot; extra matte output | 49 ops: Replicator builds layer `Select` TOPs wired to one **GLSL Multi TOP** (pixel mode, 2 colour buffers, uniform arrays from CHOPs); sequence custom pars `Tops:Tops<n>top/level/translate/scale/rotate/mattebuffer/crop` | OK: arrays + `texelFetch` + `layout(location=1)` are plain GL 4.1; single pass so no T-46 | **Yes, first pick** (R02 faces) | Layer-sequence pattern (Replicator + sequence pars) |
| **hexler** | 0.1.5, Win, 2023.11760 | `Hex` string <-> `RGB` float par, two-way | 3 ops, ParExec only; `hex_to_rgb_01` / `rgb_01_to_hex` | OK | No (trivial) | **Yes**: `#rrggbb` in `td_set_pars` (round, do not truncate) |
| **masker** | 0.6.4, Win, 2023.12230 | Polygon mask editor: add/remove masks, click to add points, nudge with arrows, curved/inverted, colour/opacity, surfaces and presets saved as TSV | 286 ops: `masker` Geo COMP + Cam/Render for UI and output, masks in a Table DAT (`points` = JSON list of `tx,ty`), per mask a Polyspline + Hole + fill, Render Pick DAT, Mouse In CHOP, Keyboard In DAT, Multi Touch In DAT (callbacks empty), MaskerExt (669 lines), 59 custom pars | Loads; mouse UI works through a panel (UNVERIFIED on Mac); Multi Touch In DAT is Windows-API (AE) | Maybe, for hand-drawn LED/screen masks | **Mask-as-data**: build the TSV/JSON and render it without the UI |
| **optimeister** | 0.6.53, Win, 2025.31550 | Cooks Delay/Filter/Lag/Logic/Timer/Trigger/Speed/Slope CHOPs only when data changes; wired or par inputs; renameable outputs | 16 ops, OptimeisterExt (339 lines): destroys/recreates the `operation` child, then **mirrors every `builtinPars` of it as a custom par** with `bindExpr`, `menuSource`, `min/max`, `readOnly` | OK | Low (perf trick for many CHOP chains) | **Yes**: "mirror pars" mode for `td_custom_pars` |
| **playback** | 0.2.38, Win, 2023.11760 | Movie player on a plane: play/scrub/loop crossfade/fade active, plus a tiny `Lagger` (lag/filter one value) | 26 ops: Geo COMP + Rectangle SOP + Constant MAT + Movie File In (uses its `loopcrossfade`, `cuepoint`, `textendright`), ParExec | OK; default file is an expression into `app.samplesFolder` | Low (Movie File In does it) | `Lagger` idea (smooth a single value with lag/filter switch) |
| **step_n_repeat** | 1.0.2, Win, 2023.11760 | Grid/brick tiling of a logo over a background | 8 ops, one **GLSL Multi TOP** pixel shader; aspect-correct fit, brick offset, optional un/premultiply around an "over" | OK (single pass) | Yes for logo/sponsor walls; set Premultiply to match our premultiplied rule | Brick-offset UV maths |
| **timecode** | 0.1.7, Win, 2025.31550 | HH:MM:SS:FF as a TOP via a 3D-texture glyph cache instead of Text TOP (about 2x cheaper); internal Timer, timeline, or a Table/CHOP input | 29 ops: Text TOP -> Texture 3D TOP (prefill 120 slices) -> GLSL Multi TOP (`sTD2DArrayInputs`), two Timer CHOPs; 26 custom pars | OK; font list is Windows names, default `Open Sans Light` may be missing (use `Customfont`) | Yes: show clock / cue overlay | Glyph-cache trick for cheap counters |
| `dev_toe` (not a tox) | 0.1.232, Win, 2025.32050 | Author's build harness: all comps wired, a `perform` Window COMP, Beat/Time/MIDI sample bits, `presets_config` JSON | 86 ops, `execute_src_ctrl` | Never open or save it (see audit) | No | The version-stamp-on-save idea |

## 3. Audit (what runs, what touches disk / the network / the OS)

| Item | Where | Effect |
|---|---|---|
| On load (Execute DAT `onStart`/`onCreate`) | chop_recorder: `cook(force)` + bypass File In if no files; color_curves: `run(init, delayFrames=10)` -> `cook(force)` + `InitPresets()`; masker: `LoadPreset()` after 10 frames; playback: reload movie; Lagger: seed value | All inside the component, except the next two rows |
| Creates ops outside its own COMP | color_curves `_saveConfig`: if `Presetconfigdat` is empty it **creates a Text DAT `presets_config` in the parent network** and writes JSON; masker `addSurface` / `ensureTablesExist` create `table_masks_surf*`/`table_presets_surf*` in the parent | Do not load into a network you care about (scratch COMP) |
| Stops cooking | color_curves `InitPresets`: `allowCooking = False` at 90 frames, `True` at 95 | A visible 1.5 s freeze on first load |
| Disk writes | chop_recorder File Out CHOP writes `<project.folder>/recordings/<name>.chan` only while Record is on; masker Table DATs have `file` + `syncfile on` and `save(..., createFolders=True)` into `config/masks/*.tsv` (relative to the project folder); color_curves `SavePresetToFile` / `LoadPresetFromFile` use `open()` but no par calls them | Predictable folders; set `Recfolder` / `Savemasksfolder` to a scratch path first |
| Disk deletes | masker `removeSurface` / `removePreset`: `os.remove()` of the TSV, after a `ui.messageBox` | Only files the component made |
| Subprocess / OS | chop_recorder `Openrecfolder` pulse: `os.startfile` on Windows, `subprocess.Popen(["open", path])` on Darwin; fixed argv, path from a par | Mac branch exists and is benign |
| Browser | `webbrowser.open('https://github.com/dylanroscover/TDComponents')` on the GitHub/Help pulse (color_curves, optimeister, playback, timecode); Derivative `PopMenuExt` `ui.viewFile(docs.derivative.ca)` | Only on a click; opens the user's browser |
| **Modal dialogs** | `ui.messageBox` in color_curves `RemovePreset`, masker `Resetall/Removemask/removeSurface/removePreset` | **A modal box blocks TD's main thread, so a `td_exec` waiting on it hangs.** Never pulse those from the MCP; add a dialog check to the watchdog if we ever do |
| Project state | timecode `Updateattrs`: sets `project.realTime = False` for about 5.5 s and restores it with delayed `run()`; locks/unlocks the 3D texture | If TD stops or is saved in that window `realTime` stays off: never pulse during a show |
| Dev harness | `dev_toe/execute_src_ctrl.onProjectPreSave`: bumps each comp's `Version`, **rewrites `../README.md`, deletes the old `release/*.tox` and saves a new one** | Dangerous only if the dev toe is opened and saved. We never load it (the `.toe` was expanded as a copy) |
| Not present | No Web Client/Server, TCP/UDP/OSC, NDI/Syphon, Script CHOP/SOP/TOP, `exec`/`eval` of strings, `import` outside `random json os ast math subprocess platform webbrowser pathlib` plus Derivative's own widget/`TDFunctions` stack (`copy traceback itertools packaging`), no hard-coded absolute paths except author paths overridden by expressions (playback `Assets/Videos/MWC...mov` is replaced by `app.samplesFolder + '/Map/Nature/Movie.5.mp4'`) | |
| Third-party code | Color Curves embeds Derivative Palette widgets (`popMenu`, `lister`, `ListerExt` with Derivative's EULA header: usable only inside TD, not redistributable); Vasily Betin (Ajasra) wrote the original curve editor, Dylan built on it; Comper's shader descends from Peter Sistrom's 2015 compositor | Do not copy the widget files into jazib-td |
| Small bugs seen | masker `MaskerExt` line 1 is `#import TDFunctions as TDF` (commented) yet `TDF.createProperty` is called in `__init__` (the author ran it, so TD supplies it, but UNVERIFIED); hexler truncates (`int(x*255)`) so a round trip can drift by one level; README says masker v0.6.3, file is 0.6.4; Comper's `readme` DAT still documents "Top Left Mode" which is now the `Pivot` menu | Note, do not copy |

## 4. Mac / 2025.31550 status

- **Runs on the Mac, by reading:** all nine. GLSL is pixel-mode, GL 3.3/4.1 features only (`texelFetch`, array uniforms, a second colour buffer,
  `sTD2DArrayInputs`). Compute-mode GLSL TOPs exist in the files only as unused default templates (color_curves histogram, step_n_repeat).
- **T-46/T-47 (multi-pass GLSL tears on TD 2 / Rosetta / MoltenVK):** Comper, Step N Repeat, Timecode are **single-pass**: fine. The Color Curves
  histogram is `glsl1 -> transform -> diff(feedback) -> analyze -> glslmulti` plus `pointRepack`: multi-pass with a feedback loop, which T-46 says
  amplifies the tear. It only drives the "Levels" preview, not the grade (the grade is Polyspline -> CHOP -> TOP -> Lookup). Keep `Preview` on
  the image view; a compute rewrite would be the T-47 fix.
- **Windows-leaning bits (verified in the files):** (1) Timecode `Font` menu = 228 Windows font names (`Bahnschrift`, `Arial Black`...) and the
  default `Open Sans Light`; use `Customfont`. (2) Masker `mtouchin` DAT: its callbacks are empty, Multi Touch In is a Windows API (AE), so it is
  inert on the Mac but may show a warning on load (UNVERIFIED, probe). (3) `os.startfile` is only reached when `platform.system() == "Windows"`.
  (4) Paths in the files use forward slashes and `app.samplesFolder` / `project.folder`: portable.
- **Comper limits to probe:** the `Resolution` par is stored with a slider max of 8192. The PF26 working canvas (75 %, 7488x2880, see memory) fits;
  the native 9984x3840 may clamp at the par (UNVERIFIED: set it, read back, else drive the GLSL Multi `resolutionw/h` directly). Up to **32 inputs**
  (uniform array size), enough for nine faces. Order is "first input on top, last at back".
- **Older saves (2023.x) into 2025.31550:** same caveat as Y: defaults and Palette parts can change. Load into a scratch COMP, then `td_errors`.

## 5. Recommendations

**Use inside TD on this Mac (each in a scratch COMP, with the user's go-ahead; none touches the home rig):**
1. **Comper** for the R02 nine-face layout: three coloured Constant TOPs, then nine at the real face sizes; check placement against the vendor
   package numbers, `Fractional Translate`, Pivot `Top Left` (LED-processor convention, +Y down), the matte output, 8-bit vs 16-bit canvas.
   Pair with our `td_publish` path (alpha rule, AI).
2. **Timecode** as a show-clock/cue overlay (cheap per frame); set `Customfont`; never press `Update Attrs` live.
3. **Color Curves** as the stage grade after the look and before the publish; keep Preview/Handles as image; one probe for T-46 on the histogram
   if "Levels" is wanted; remember presets create `presets_config` outside the comp.
4. **Chop Recorder** to freeze an audio-feature CHOP (AC_audio) or an OSC track into a `.chan` so a clip bake (`td_clip_bake`, AI) is repeatable.
5. Step N Repeat for logo walls (PRISM logo, sponsors) if a design needs it; Masker only if the user wants to hand-draw masks (it needs mouse
   interaction and modal boxes).

**Port ideas into jazib-td (ideas and patterns, not files; GPL):**
1. **`td_set_pars` hex colours** (`"#00baff"` or `"00baff"` into an RGB par triple, rounded, with the Z note that hex is 8-bit sRGB): from Hexler.
2. **`td_custom_pars` mirror mode** (Optimeister): `mirror: {src:'./operation', page:'Operation'}` creates a custom par per `builtinPars` entry
   with `bindExpr`, `menuSource`, `min/max`, label; add `readOnly` and `ParMode.CONSTANT` handling; today the tool only adds pars. Probe
   `bindExpr` + `isPulse` on 31550 first.
3. **About page convention**: custom page "About" with `Version`, `Touchbuild` (= `project.saveBuild`, [DUMP/AG]) and `Github`, stamped by `td_tox_save`
   (the author does it in `onProjectPreSave`). Our saved `.tox` would then say which build made it.
4. **`td_record_chop` / `td_play_chop`** (Chop Recorder): Timer-driven File Out/In with a Folder-DAT menu; see AC and AI for the bake use.
5. **Layer-sequence builder** (Comper): Replicator + sequence block pars (`numBlocks`) so one tool call sets N layers; a typed `td_layers`.
6. **Mask-as-data** (Masker): a mask is a row `name,label,color,opacity,invert,curve,points(JSON)`; an MCP tool can write the TSV/table and let a
   Polyspline + Hole network render it, no UI needed.
7. **Dialog guard**: if `ui.messageBox` is ever reachable (these comps, Embody), the watchdog should detect a stuck exec; AF lists `list_dialogs`.
8. `Lagger` (lag or filter one value with a bypass timer) as a recipe in USING_TD.

**Not worth porting:** the Palette widget set inside Color Curves (Derivative-licensed, depends on `op.TDResources`), Playback (Movie File In does
loops/crossfade), the dev toe harness.

## 6. Gated / newer-build list (copy into `docs/FUTURE.md`)

| Feature | Needs build | Status | Where | How to test when available |
|---|---|---|---|---|
| TDX Comper saved on 2025.32050 (one step above 31550); any behaviour change in GLSL Multi TOP between the two | 2025.32050+ | nothing known; all pars it uses exist in 31550 | research_src/peers/TDXComponents_expanded/comper-v2.1.0, docs/research/AM_tdxcomponents.md | load in a scratch COMP on the new build, compare the placement result with the 31550 render |
| Color Curves histogram "Levels" view (multi-pass GLSL + feedback) | build where T-46 is fixed (unknown; native arm64 2025.32820?) or a compute rewrite (T-47) | idea only: Preview image view works now | docs/research/AM_tdxcomponents.md section 4 | toggle `Preview`, run the T-46 meter; else port to compute |
| Masker mouse/touch UI (Multi Touch In DAT, Mouse In CHOP) on macOS | unknown | UNVERIFIED | docs/research/AM_tdxcomponents.md | load Masker in a scratch COMP, open the UI panel, add 4 points by mouse; `td_errors` for the touch DAT |
| Comper `Resolution` above 8192 (native 9984x3840) | any | UNVERIFIED (par slider max 8192) | docs/research/AM_tdxcomponents.md section 4 | set 9984x3840, read back, else drive the GLSL Multi resolution |
| `td_set_pars` hex colours, `td_custom_pars` mirror mode, About-page stamp, `td_record_chop`, `td_layers` | 31550 (no gate) | idea only | docs/research/AM_tdxcomponents.md section 5 | EVOLVING.md steps: probe, LEARNINGS, small tool, test |

## 7. Open questions for the user

1. May I load Comper (and optionally Timecode, Color Curves) into a scratch COMP of the home project to run the section 5 probes?
2. Which tools from section 5 "Port" do you want first (hex colours and mirror mode are the smallest)?
