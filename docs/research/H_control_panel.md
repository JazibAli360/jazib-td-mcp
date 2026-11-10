# H. The hand-operated show panel: what already exists, what to copy, how to build it (research agent H, 16 Oct 2026)

Task: the PRISMFEST'26 live TD rig is operated by hand from an on-screen TD panel (sliders, buttons, constants on custom
parameters). The Akai MIDImix and MPK Mini MK3 get mapped later, so adding MIDI must be a mapping step, not a rebuild.
User rule: research first, someone probably already made it. Target: TD **2025.31550** (`/Applications/TouchDesigner 2.app`,
Rosetta, M1 Max), driven through `jazib-td-mcp`. Builds on `ops/COMP_UI.md` (not repeated: panel COMP pars, Window COMP,
Perform mode, gotchas) and `E_live_rig.md` §5 (control map, states, safety). Nothing was run in TD (no `td_*` call); no
download, no install.

Evidence tags: **[X]** = read by expanding the shipped `.tox` with `toeexpand` on a copy (scratch
`/private/tmp/claude-501/-Users-vyro-Documents-StageLab-PrismFest/884be6b4-f6c3-4881-b616-b05ae1e8baed/scratchpad/h/`,
nothing touched inside the app bundle). **[FS]** = file listing of the install. **[OH]** = the offline help page shipped in the
app (`tfs/Samples/Learn/OfflineHelp/https.docs.derivative.ca/`). **[DUMP]** = `ops/*_2025.31550.json` (live dump).
**[WEB]** = a web page read on 16 Oct 2026 (URL given). **[DESIGN]** = my proposal, never run. **[UNV]** = unverified on 31550.

## 0. Short answer

1. **Nothing community-made should be adopted wholesale.** The complete VJ systems are either unlicensed (no licence on the
   GitHub repo), paid, Windows-first, built for newer TD builds, or built around a clip-deck model (layers x columns of media)
   that is not our rig (a few live generative looks, per-state fades, a kill). The best open component (TDXMorph, MIT) was built and
   tested on **2025.33230, newer than our 31550**.
2. **What is reusable is already inside the app, and it is read and confirmed by expansion:** (a) `Palette/UI/Basic Widgets/Tools/autoUI.tox`
   proves the exact "UI widget Value0 `bindExpr` -> custom parameter of a COMP" pattern (source of the shipped extension quoted in §3.1);
   (b) `Palette/Tools/sceneChanger.tox` is a ready A/B look crossfader with idle-scene cook savings, written on **macOS**;
   (c) the OP Snippets `bindCHOP`, `midiinCHOP`, `sliderCOMP`, `buttonCOMP`, `parameterCOMP` show the Bind CHOP + `pickup` + export table wiring.
3. **Correction to `E_live_rig.md` §5.1:** it says "this install's Palette folder has no Widgets folder". It does:
   `tfs/Samples/Palette/UI/Basic Widgets/` (60+ widgets, `Package/basicWidgets.tox`, v2.2.6). E listed the top level folders
   (`UI` was in the list) and did not look inside. [FS]
4. **There is no shipped preset tool.** The Palette "Presets" COMP was dropped in build 2022.29530 [OH `Palette-presets.htm`] and
   no `*preset*` file exists under `Palette/` [FS]. Presets are ours to build (a Table DAT of JSON rows; §3.5).
5. **Recommendation: build our own from the plain pattern** (state COMP of custom pars -> bound plain Slider/Button COMPs ->
   smoothing -> looks -> output), **borrowing** sceneChanger's gate design (try the Palette item itself first) and autoUI's bind
   recipe, and keeping a **MIDI stub** (map Table DAT + router) in the build from day one so MIDI is "fill rows". Details in §4–§5.

## 1. What ships in the app (exact paths, all under `/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/`)

### 1.1 Palette (278 `.tox`) items that matter for a control panel [FS]

| Path (under `Palette/`) | What it is | Read by expansion [X] / help [OH] | Use for us |
|---|---|---|---|
| `UI/Basic Widgets/Package/basicWidgets.tox` | The whole widget set in one package. Package par `opshortcut` = `TDBasicWidgets`, `Version` 2.2.6 [X]. Authored on Windows build 2023.12370 [X `.build`]. | Widgets page (§2.3 of COMP_UI) | Optional look; see §1.2 |
| `UI/Basic Widgets/{sliderHorz,sliderVert,sliderHorzXFade,sliderAutoFade,slider2D,slider3Rgb,slider3Hsv,slider4Rgba,slider4Hsva,knobFixed,knobEndless,range}.tox` | Sliders and knobs. `sliderAutoFade` = a slider with an internal Lag CHOP (`Sliderlagtime` default 0.2 s) that writes `Value0` (CHOP Execute `onValueChange` -> `parent.Widget.par.Value0 = val`) [X]. | | Smooth master/blackout slider |
| `UI/Basic Widgets/{buttonToggle,buttonMomentary,buttonRadio,buttonRocker,buttonCheckbox,buttonState,buttonScript}.tox` | Buttons. `buttonRadio` has `Radiolabels`, `Radiomaxperline`; `buttonToggle` has `Buttonofflabel/onlabel`, `Buttonstateexpression` [X cparm]. | | Look select, toggles |
| `UI/Basic Widgets/{header,footer,label,section,windowHeader,folderTabs,dropDownMenu,fieldString,float1..4,int1..4,opViewer,referenceTOP...}.tox` | Layout and value widgets. | | Optional |
| `UI/Basic Widgets/Tools/autoUI.tox` | Builds a widget panel for the custom parameters of a COMP and **binds** each widget (§3.1). Pars: `Customcomp`, `Ui`, `Generateui`, `Package` (default `/TDUI1`), `Parameterscope` (`*`), `Header`, `Pagetabs`, `Pagescope` [X cparm]. Authored 2020.42160 [X `.build`]. | | Instant engineering/test panel for `state` |
| `UI/Basic Widgets/Tools/widgetCacher.tox`, `Scripting/extensionParExec.tox` | Widget cache (draw cost), per-widget extension watcher. | | Only if widget draw cost shows up in `td_perf` |
| `UI/{lister,treeLister,simpleList,radioList,displayList,popMenu,popDialog,operatorPath,gal}.tox` | Older/other list and dialog widgets (`gal` = older set). | | `radioList`/`simpleList` for a cue list if wanted |
| `Tools/sceneChanger.tox` | Scene framework: scenes are COMPs with an `out1` TOP; A/B cross-fade; idle scenes stop cooking (§3.2). v1.0.6 [X], authored on **macOS 14.6.1, build 2023.12000** [X `.build`]. | `Palette-sceneChanger.htm` (edited 13 May 2021) | **Look switching** |
| `Tools/remotePanel.tox` | `remotePanelClient`/`Server`: see and operate a panel running in another TD on another machine (port 9500). | `Palette-remotePanel.htm` | TD-to-TD only; not a phone/tablet panel |
| `Tools/probe.tox` | CPU/GPU/memory monitor that works in Perform mode (Ctrl/Cmd-P). | `Palette-probe.htm` | Cost check with the UI open |
| `Tools/logger.tox`, `Tools/onScreenKeyboard.tox`, `Tools/moviePlaylist.tox`, `Tools/blendModes.tox`, `Tools/testGrid.tox`, `Tools/showCooks.tox` | Log/keyboard/playlist/mixer/test-grid/cook visualiser. | | `showCooks` to prove idle looks do not cook; `logger` for show log |
| `TDAbleton/…/abletonMIDI.tox`, `TDBitwig/*` | DAW remote components (not MIDI-controller mapping). | | Not relevant |

Not in the Palette: any preset/cue tool, any MIDI-learn or controller-mapping tool, any VJ deck. [FS: `find Palette -iname '*preset*' -o -iname '*cue*' -o -iname '*midi*' -o -iname '*learn*'` returned only the two `abletonMIDI.tox` and the Bitwig remotes]

### 1.2 Basic Widgets: how they are built [X], and what that means

Expanded `sliderHorz.tox` (and the package):
- A widget is a **Widget COMP** (`widgetCOMP`, Container-like) with `parentshortcut = Widget`, `clone` = `op.TDBasicWidgets.op('sliderHorz')`
  (so every loose widget is clone-linked to the master in the package), `ext0promote on`, and sub-COMPs `label`, `numericValue0`,
  `slider0`, `overlay`, `output`, `code`. `slider0` carries `SliderExt` (a Python extension built on `SubWidgetExt`, uses
  `op.TDModules.mod.TDFunctions`).
- **Custom page "Values":** `Value0` (Float, size 1; 2-4 for multi-value widgets), `Onvaluechangescript0`, `Offtoonscript0`,
  `Ontooffscript0` (per-value scripts), `Valueparexec` (+ a `Createeditvalueparexec` pulse that makes a docked Parameter Execute DAT
  watching `Value?`). Seven pages total: Values, Label, Field, Slider, Widget, OPs, About.
- The widget's `enable` par is an expression that follows the bind master: `me.par.Value0.bindMaster.enable if ... isinstance(me.par.Value0.bindMaster, Par) else True`.
  So a widget **greys out when its master par is disabled** - useful for locking controls on a custom par.
- Outputs: CHOP/DAT inside `output` (`chop`, `dat`, `numValues`), so a widget can also feed a CHOP.
- Costs and risks: each widget is ~10 COMPs plus an extension; updating a widget re-clones it from the master and wipes edits ("do not edit
  internals", COMP_UI §2.3); loose widgets need `op.TDBasicWidgets` to exist in the project (clone expression), one `basicWidgets` per file;
  the package was authored on Windows build 2023.12370 and has not been loaded on this Mac by anyone here [UNV]. A 2021 forum thread blamed widget
  fields for a ~15 fps network and advised disabling fields [WEB forum.derivative.ca/t/channel-pickup-in-bind-chop-doesnt-work/180513]; whether that
  still applies on 31550 is unmeasured.
- **Verdict:** use **plain Slider/Button/Text COMPs** for the performance panel (documented, no hidden code, cheap). Use `autoUI` (or a
  Parameter COMP) only for a hidden engineering page if one is wanted.

### 1.3 OP Snippets (one example `.tox` per op; `Learn/OPSnippets/Snippets/<FAMILY>/<op>.tox`) [FS, X]

| Snippet | What the expansion shows |
|---|---|
| `COMP/sliderCOMP.tox` | Slider COMP is read through its `Value0` par or its output channel; ex.2: a Parameter Execute DAT (`parexec2`) reacts to `Value0` changing; a CHOP Execute DAT writes `Value0` from a CHOP; a Constant CHOP "virtually clicks" the panel. Authored 2025.31424. Dump pars: `value0/1`, `valuerange0l/h`, `clampul/uh`, `slidertype` (`slideru/sliderv/slideruv`). |
| `COMP/buttonCOMP.tox` | `buttontype` menu = momentary, momentaryup, toggledown, toggleup, toggleupany, radiodown, radioup, radionupany, exclusivedown, exclusiveup, exclusivenupany [DUMP]. Ex.2: **Button Group DAT** (`buttongroupdat`) fed by an OP Find DAT makes buttons in different COMPs behave as one radio group; read with a Parameter CHOP + Fan CHOP. |
| `COMP/parameterCOMP.tox` | Parameter COMP draws the pars of `op` (`custom`, `builtin`, `pagescope`, `parscope`, `labels`, `header`...). Ex.2 `hueControls`: a panel whose UI is a Parameter COMP shown through the COMP's OP Viewer par. Ex.4: a multi-panel chooser from a Base COMP with pages, caveat "miniPanel/select1 needs to be always-cooking". |
| `CHOP/bindCHOP.tox` (author jetxs, created 1/10/2021, expanded on build 2025.31424) | Ex.1: LFO feeds a Bind CHOP; **three `sliderHorz` widgets have `Value0` with `bindExpr` = `op('bind1')['chan1']`** (the Bind CHOP channel is the bind master); Bind CHOP pars `pickup on`, `callbacks bind1_callbacks`, `exportmethod datname`, `exporttable bind1_export`. Export table columns: `name index path parameter enable` (rows such as `chan1 0 lfo2 offset 0`). Callback signature: `onValueChange(bindOp, chan, val, prev, source)`. The readMe: with Channel Pickup on, "a value doesn't update until it reaches the current value" of the receiving side; "turn off pickup and it updates instantly". |
| `CHOP/midiinCHOP.tox` ex.2 | MIDI In CHOP (`channel 1-16`, `legacypattern on`, `timeslice on`) -> Math CHOP (`fromrange 0..127`) -> Null `prep` with export by `datname` (`prep_export`: `ch1ctrl78 0 pattern1 phase 1`); a Bind CHOP with the same callbacks DAT sits next to it. readMe: exporting is "more direct and less flexible"; Bind CHOP is the alternative. |
| `CHOP/midiinmapCHOP.tox`, `DAT/midiinDAT.tox` | Device-Mapper-based channels `s1..`/`b1..`; MIDI In DAT with a `map` table and a script DAT. Not expanded further. |
| `DAT/panelexecuteDAT.tox`, `DAT/parameterexecuteDAT.tox`, `DAT/chopexecuteDAT.tox`, `DAT/jsonDAT.tox`, `DAT/tableDAT.tox`, `DAT/keyboardinDAT.tox`, `CHOP/{lag,filter,limit,logic,lookup,speed,panel}CHOP.tox`, `COMP/{windowCOMP,replicatorCOMP,animationCOMP}.tox` | Present in the snippet set for the callback shapes and smoothing ops used below. |

Snippets are authored on Windows build 2025.31424 [X `.build`]; they load on this Mac as ordinary `.tox` (same build family).

## 2. Community: what exists (read 16 Oct 2026)

Licence column is what the repo/page states; "none stated" means a public repo with **no licence file = all rights reserved by default; do not copy code
out of it**. API facts (`pushed_at`, licence) from `api.github.com/repos/<owner>/<repo>`.

| Name / link | Licence | TD / platform | What it gives | Fit |
|---|---|---|---|---|
| **TDXMorph** (was TDMorph), Darien Brito. https://github.com/DarienBrito/TDXMorph ; asset page https://derivative.ca/community-post/asset/tdmorph/73268 (11 Nov 2025). pushed 9 Oct 2026, 201 stars [WEB] | **MIT** for PresetManager 4.4.5, PresetSnap 1.3.2, PresetInspector, JSONTree, ListView, **ControlMapper 1.1.2** (MIDI and OSC mapping for any custom parameter; auto-learn in Perform mode); example project CC BY-NC 4.0; **ParameterMorpher and SceneLauncher are commercial** (Patreon, no redistribution) | "Built and tested on 2025.33230" (newer than 31550); no macOS note in the README | JSON presets, multi-track morph with curves, global and per-parameter timing, cueing with follow actions (paid SceneLauncher), MIDI/OSC auto-learn. Page does not mention pickup, banks or LED feedback. | **Best reference, not adopted.** Right idea (JSON presets on custom pars, ControlMapper on custom pars). Risk: newer-build features, unknown Mac behaviour, beta, large. Copy the *design*; if the user later wants to try it, load only the MIT parts after the lead's go-ahead (guardrail: no downloads now) |
| **SimpleMixer**, Richard Burns. https://github.com/Richard-Burns/SimpleMixer (266 stars, pushed 29 May 2026, 121 commits) | **Unlicense** (public domain) | README: "tested and working in build 2023.12000"; Spout/Syphon, NDI, RTMP out | 4 banks of clips/.tox with sliders mixing between banks, central A/B fader, post-FX slots, MIDI/OSC/key/UDP/Art-Net mapping and a "UI-Kit with MIDI learn" (v1.9.0), record button. **Presets not implemented** (to-do). | Clip-bank VJ mixer model, not our state-driven generative rig; the only complete open one with a free licence. Useful to read for its UI/MIDI-learn layout. Not adopted |
| **SonomikaTD**, Voltaine. https://derivative.ca/community-post/asset/sonomikatd-touchdesigner-vj-system/75106 (28 Jul 2026) [WEB] | Free download via Patreon; **licence not stated**, not shown as open source | TD version and OS not stated | Layer x column performance grid, up to 32 scenes, smooth column crossfade, TOX effect stack, saveable performance sets, MIDI and OSC | Clip-grid model; closed. Not adopted |
| **Versatile VJ System, 5 layers + custom UI**, Black-Pomeranian. https://derivative.ca/community-post/asset/release-versatile-vj-system-5-layer-control-custom-ui/73834 (25 Jan 2026); repo https://github.com/black-pomeranian/VJ-System_Sample (3 commits, 2 stars) [WEB] | Page: free; **repo has no licence** | version/OS not stated | Single `VJ_System.tox` 893 KB; 5 layers (top overlays/text, bottom backgrounds); pre-mapped to **AKAI APC mini mk2** (not our controllers); Sound2Light OSC for audio | Layer/overlay model; unlicensed. Reference screenshot only |
| **AAVJ**, anti-alias. https://derivative.ca/community-post/aavj-realtime-vj-mixer-built-touchdesigner/68340 (21 Sep 2023) [WEB] | Discord download; licence not stated | not stated | Composite-TOP blend layers, auto VRAM management, auto-learn UI for MIDI/OSC, drag-drop .tox, NDI/Spout out | Closed (Discord). Not adopted |
| **CuryCue**, netzzy (Evgeniy Afonin). https://github.com/netzzy/CuryCue ; asset https://derivative.ca/community-post/asset/curycue-cue-based-control-system/67702 (24 Apr 2023). 42 stars, pushed 18 Jun 2026 [WEB] | `License.md` exists; GitHub reports "Other / NOASSERTION" - **read the file before any use** | filenames carry `32820` (a 2025 build); OS not stated | QLab/lighting-console style **cue list** over TD components/parameters: cues store only changed values, per-cue and per-parameter fades, Go / GoNextCue / GoPrevCue, Show/Edit/Fixture modes, linked auto-follow cues, "Content Preset" containers, SQLite + Python, optional TouchEngine "Engine Room" | **Closest to our "state + cues + fades" need**, but a whole framework (SQLite, 3 modes). Reference for the cue model. No MIDI mentioned. Not adopted; check licence if the lead wants it |
| **Custom Cuelist Sequencer**, GabPelland. https://derivative.ca/community-post/asset/custom-cuelist-sequencer/73521 (10 Dec 2025, v1.0.0, 26 KB) [WEB] | not stated | not stated | Any Base COMP as "Master Operator" preset; timed cues, per-cue FadeIn; timeline / local timer / external index / manual index | Timed (timeline) cues; our show is hand-operated. Idea: per-cue fade-in |
| **Presetter**, JoEL8129 / bi.os. https://github.com/JoEL8129/Presetter ; asset .../td-presetter/73919 (8 Feb 2026). 1 star [WEB] | **none** | not stated | Adds a preset page to a COMP; store/recall | Too thin, unlicensed |
| **Simple Preset System**, Vasily. https://derivative.ca/community-post/asset/simple-preset-system/67175 (6 Feb 2023); **Value_Matrix**, Unveil_studio (14 Dec 2021, free); **CamSequencer**, function.store (14 Feb 2022, camera presets) [WEB] | not stated | not stated | Preset store/recall with per-preset scripts; Value_Matrix links presets to a custom-parameter COMP (credits Matthew Ragan's case study) | Reference only |
| **TDMap**, function.store (Dan Molnar). https://derivative.ca/community-post/asset/tdmap-smoothest-midi-mapping-workflow-tool-any-controller/74906 (27 Jun 2026); docs tdmap.functionstore.xyz/docs [WEB] | **Commercial**: 14-day Pro trial, Base licence (mapping, banks, scripts on buttons, config library), **Pro adds smoothing, pickup, easing curves, math between controls**; paid via Patreon/Gumroad, no prices on the page | version/OS not stated | MIDI learn (Learn on, move control, assign), banks, "faders don't jump on recall", LED feedback for hardware that supports it; factory layouts NanoKontrol, APC40 MkII, Launch Control, MiniLab, Twister, Intech; **MIDImix and MPK Mini not named** | The commercial answer to "MIDI mapping with pickup". We design the same behaviour ourselves (§3.7); buying is a later option if the scripted router disappoints |
| **Duarte Amorim, Midi_Learn_Controller**. https://github.com/duarte-amorim/Touchdesigner (13 stars, pushed Feb 2024); asset https://derivative.ca/community-post/asset/tox-midi-learn-function-midi-controllers/69078 (28 Feb 2024) [WEB] | **none** | repo says TouchDesigner099; Launchpad-oriented | A MIDI-learn component with Launchpad SysEx | Unlicensed, Launchpad-centred |
| **TouchDesigner Launchpad Utility**, monoton-music. https://github.com/monoton-music/TouchDesigner-Launchpad-Utility (pushed Nov 2024) [WEB] | MIT | Novation Launchpad Pro MK3 / X | Button mapping for Launchpad | Wrong controller |
| **Rouge** (Mary Franck, CDM 14 Jun 2013), **TouchMixerII**, FragTool, CueDesigner (Derivative 2013 "performance interfaces" post, Sept 2013, Isabelle Rousset https://derivative.ca/community-post/touchdesigner-performance-interfaces/60765) [WEB] | free/unclear | 2013 builds, Windows | Historic: one big slider per effect, generate UI from a parameter table with Replicator, make sliders large, separate performer view from output | Design lessons only (the three that still hold are in §3.3) |
| Paid courses: I&I HQ "Simple VJ Setup - Capstone" (https://pro.interactiveimmersive.io/courses/simple-vj-setup-capstone/), Matthew Ragan "Professional Python for TouchDesigner" (includes "Building a Preset manager"), Kwave Coder (Patreon preset manager/VJ system) [WEB] | paid | | Teaching material | Not pursued. I did not find Ragan's own free preset/cue code on GitHub (his public repo in the results is a SOP-to-SVG tool); his 2019 custom-parameter/cue case study is cited by Value_Matrix and CamSequencer but I could not retrieve its text [UNV] |
| Function Store tools pack (Patreon) [WEB] | paid (Patreon tiers; **price not on the pages I could read**) | | Workflow tools by Dan Molnar | I could not read the pack list (pages truncated). Not needed |

Forum evidence that shapes the design:
- **Why bind and not CHOP export for sliders.** Forum thread "Slider midi connection breaks when dragging it with mouse"
  (Feb 2026; staff reply Markus/snaut, 9 Feb 2026) [WEB forum.derivative.ca/t/slider-midi-connection-breaks-when-dragging-it-with-mouse/948342]:
  export and expression are one-way references; moving the slider with the mouse turns the parameter back to constant and breaks the
  link; the recommended pattern is **Binding through a Bind CHOP**, and the Bind CHOP callbacks can send a changed value back to the controller.
- **Pickup caveat.** Thread "Channel Pickup in Bind CHOP doesn't work" (Apr-May 2021, build 2021.12380, Windows 10, Launch Control XL)
  [WEB forum.derivative.ca/t/channel-pickup-in-bind-chop-doesnt-work/180513]: no resolution recorded; staff-side reply said the shared file did not
  have pickup on, and used CHOP export instead of a bind. So pickup has no clean confirmation on any build; **bench it on 31550** (§5 step 12).

## 3. Patterns to copy (each with what proves it)

### 3.1 State COMP of custom parameters = single source of truth; UI is bound, not scripted

- Custom par rules (names: one capital then lowercase/digits, T-00e; `td_custom_pars` styles Float, Int, Toggle, Pulse, Menu, Str, RGB, XY, File) are in COMP_UI §3.1.
- **Proof of the bind recipe [X]:** the shipped `autoUI` extension (`Palette/UI/Basic Widgets/Tools/autoUI.tox`, `AutoUIExt.text`) generates a UI by looping over a
  COMP's custom pars and, for each widget value, runs
  `valuePar.bindExpr = TDF.getShortcutPath(widget, customComp) + '.par.' + par.tuplet[v].name`
  (so a global shortcut such as `op.SHOW` is used when the target COMP has a `parentshortcut`), and for menus
  `widget.par.Menunames.expr = 'me.par.Value0.bindMaster.menuNames'`. It also asks for a `parentshortcut` on the target COMP ("Enter a parent shortcut for ...").
  The Bind CHOP snippet does the same with a CHOP channel as master (`Value0` `bindExpr` = `op('bind1')['chan1']`) [X].
- **For plain Slider/Button COMPs** (our choice): `slider.par.value0.bindExpr = "op.SHOW.par.Master"`, same for a Button's `value0` (Toggle).
  `td_set_pars {value0: {bindExpr: "op.SHOW.par.Master"}}` is supported by the MCP (`src/server.js` parValue, `td/handlers.py` `bindExpr`). [DESIGN for plain COMPs: the recipe is
  shipped for widgets, documented in Binding, but a plain Slider COMP's `value0` bind was never run here, COMP_UI Open question 3.]
- **Keep state pars normalised 0..1** (Float, min 0, max 1, clamp) except Look (Int or Menu), toggles and Preset index. Reason: a plain Slider COMP's range is its own
  `valuerange0l/h` pars (default 0..1 [DUMP]); `bindRange` only follows the master's min/max/norm range [OH Binding]. With everything 0..1, no range plumbing is needed;
  scaling to engineering units (speed in Hz, hue degrees) happens once, in the look that uses it. [DESIGN]
- **Actions are Python methods, not pulse pars.** Binding pulse pars is risky on 31550 (release notes: `.pulse()` on bound non-pulse pars fixed in 2025.32460 - newer
  than ours; COMP_UI §3.2). Buttons for GO / SAFE / STORE / RECALL use a **Panel Execute DAT** `onOffToOn(panelValue)` -> `op.SHOW.GoLook(2)` (extension method). Level-type
  controls (toggles, sliders) are bound. [DESIGN, risk reasoning from release notes]
- Engineering page: a **Parameter COMP** with `op = /project1/show/state`, `custom on`, `builtin off` gives every state par as a field for free [DUMP + X snippet].

### 3.2 Look/deck selection with smooth crossfades: the sceneChanger design [X]

Expanded `Tools/sceneChanger.tox` (Palette):
- Structure: a Replicator makes one **gate COMP** per scene (`sceneGate0..N`, master `sceneGateMaster0`); `SceneChangerExt` (promoted) has `FireScene()`, `SceneChange(indexOrName, fadeTime=None)`,
  `SwitchToScene`, `GenerateUI()` (radio-button UI), `GenerateSceneTemplate()`, `Reset()`. Custom pars: `Resolutionw/h`, `Scenescomp`, `Nextscene`, `Firescene`, `Fadetime`, `Currentscene`.
- **Cross-fade**: two Over TOPs inside `sceneSelect` with a Switch TOP whose `index` is bound to the toggle `Toggleabba`; each gate has a **Filter CHOP** whose `width` is `parent.Gate.par.Fadetime`
  (the gate value `0/1` comes from a Constant CHOP bound to `Active`), exported to the gate's Switch TOP `index` (via `null1_export` rows `gate 0 switch1 index 1`; `switch1 blend` off).
- **Idle scenes do not cook**: the gate's Select TOP `top` par is `parent.Gate.par.Scenecomp.eval().op('out1') if ... else ''` and the Switch TOP selects a Constant TOP when the gate is 0 [X]; the help page states "scenes that are not being played also will not cook" [OH].
- Scene contract [OH]: each scene COMP has parent shortcut `Scene`, tag `TDScene`, a page "Scene Settings" (`Start` and `Init` pulses, `Fadeintime`, `Fadeouttime`, `Play`, `Length`) and an `out1` TOP; **all scenes must share one resolution** (strict on purpose; our build rule is 1080x1920).
  "Do not add custom parameters to the Scene COMP" - put our look inside a child COMP.
- Use from our state: a Parameter Execute DAT on `state` watching `Look`: `op('../looks/sceneChanger').SceneChange(int(par.eval()), fadeTime=parent().par.Fade.eval())`. [DESIGN]
- Limit: it is a **one-in, one-out** A/B crossfade. It does not do N weighted layers (the slot-fader mix proposed in E §5.5). For weighted overlays, add a second mixer after it (Layer Mix TOP / Composite TOP, listed in E).
  Decision for the lead: one look at a time + crossfade (this) or N faders (E §5.5)? See Open questions.
- Fallback if the palette item misbehaves on 31550: copy the pattern (2 Select TOPs + Cross TOP/Over, one Lag/Filter CHOP per gate, Switch TOP to a Constant TOP when idle).

### 3.3 Master dimmer, blackout, safe kill

From E §5.5, §6 and the design lessons in the 2013 performance-interfaces post (one big control per effect; large hit areas; separate performer view from output) [WEB]:
- **Last in the chain, in `output`:** Level TOP (`opacity` or brightness) = `Master * (1 - Blackout)` read from the smoothed `live` CHOP (§3.4); then Null TOP `out`. Blackout fade is a slower Lag (e.g. 0.5 to 1 s) - fade, not cut. [DESIGN]
- Controls: `Master` (Float 0..1, bound slider, later the MIDImix master fader), `Blackout` (Toggle, big button in a contrasting colour, away from frequently used controls: E §5.3 says never put BLACKOUT next to buttons used constantly), `Safe` (action: recall the safe preset: calm look, Master capped, FX off).
- Kill in TD only affects TD; the Arena-side kill is separate (E §6). The panel must work with the hardware unplugged (COMP_UI §6.11).
- Window safety: `closeescape` off, Shift+Esc always closes (COMP_UI §7 gotcha 4).

### 3.4 Smooth values between state and looks (so recall and fades never jump)

[DESIGN, ops exist in the dump: parameterCHOP, lagCHOP, filterCHOP, nullCHOP]
`state` (targets, what sliders show) -> **Parameter CHOP** (`ops` = state, `custom` on, `builtin` off) -> **Lag CHOP** (per-channel lag; `lag1/lag2`, `lagunit`) -> **Null CHOP `live`**.
Looks read `op('live')['Speed']`, never `op.SHOW.par.Speed`. Sliders still show the target. Result: preset recall and MIDI jumps glide; a longer lag on `Blackout` is a separate Lag. Pickup for hardware compares the hardware value with the **target** (state par), not the lagged copy.

### 3.5 Preset save/recall (no shipped tool: the Palette Presets COMP was dropped in 2022.29530 [OH])

[DESIGN, modelled on TDXMorph (JSON, MIT) and CuryCue (store only what changes)]
- A **Table DAT `presets`**: columns `slot, name, json, saved`; `json` = `json.dumps({p.name: p.eval() for p in state.customPars if not p.isPulse and p.name not in EXCLUDE})`.
- Extension methods on `state` (promoted capitals): `Store(i)`, `Recall(i)` (writes `par.val` for each key; the `live` Lag does the glide), `GoLook(i)`, `Blackout()`, `Safe()`, `Hit(n)`.
- Persistence: the Table lives in the project file; also export to `jazib-td-mcp/projects/presets.json` on every Store (Text DAT `write` or `open(...)` in the extension) as a backup the user can see. Presets that must survive extension re-init
  live in the Table/custom pars/StorageManager, not in plain attributes (COMP_UI §6.8, [OH Extensions]).
- Look selection is **not** inside preset data by default (a preset changes values; a cue changes look + values); decide in the open questions.
- Do not recall in one frame on stage (COMP_UI §6.9). Recalled values on non-motorised faders will disagree with hardware: that is what pickup (§3.7) is for.

### 3.6 Flash limiter (rules from `concert-visuals-research/README.md` §4, lines 98-117)

Rule there: a sequence of flashes is not allowed when it covers more than 25 % of the screen and there are more than 3 flashes in any second; saturated red is especially risky; fast cuts count; leading edges >= 9 frames apart are fine (E §5.5). Three cheap layers, all [DESIGN]:
1. **Hit governor** in `Hit()`: ignore a one-shot hit if `absTime.frame - self.lastHit < 9`; also cap hits per second at 3.
2. **Rate by design:** looks keep strobe-like layers behind a `Strobelim` toggle (on by default); the limit is enforced on the *rate* control of that layer (clamp its rate par), not on trust.
3. **Output monitor**: a small copy of `out` (e.g. Resolution/Fit TOP to ~64x36) -> Analyze TOP (average) -> TOP to CHOP -> Slope/Logic CHOP to count luma swings; a lamp turns amber/red on the panel when more than 3 swings of large amplitude occur in 1 s; optional auto gain-down through the Master multiplier. Ops exist in the dump (analyzeTOP, topto/slopeCHOP, logicCHOP). **Thresholds are unmeasured and need the lead's numbers and a test clip**; this is a monitor, not a certified photosensitivity test (PSE/Harding is the real test, README §4 line 105).

### 3.7 MIDI later = mapping rows (MIDI-learn table, pickup / soft takeover)

Design principle: **MIDI never has its own state.** It writes the same `state` pars the sliders are bound to. Build the plumbing now, empty:

```
/project1/show/midi
  midi_mix  (MIDI In CHOP, device unset/Active off)      midi_mpk (second MIDI In CHOP)
  map       (Table DAT)  id | device | kind | number | chan | bank | target | lo | hi | curve | mode | pickup
  router    (CHOP Execute DAT on Null of each device)  looks up channel name in `map`, scales, applies bank, calls SetPar / ext methods
  learn     (MIDI Event DAT + `Learn(row)` ext method): arm a row, next message fills device/kind/number/chan
```
- Row `target` is a state par name (`Master`, `Speed`) or an ext action (`Safe`, `Hit:3`, `GoLook:2`). `mode`: abs | pickup | toggle | pulse | radio. `curve`: lin | exp | log | step. `bank` selects an alternate row set (MIDImix has 8 strips only).
- Adding the controllers = plug in before TD starts (T-34), set the device on each MIDI In, run Learn once per control (or type numbers), done. No new COMP, no new binds.
- **Pickup, scripted (primary, verifiable):** per control remember `engaged`; engage when `|hw - par| < tol` or hw crosses par between two messages; ignore until engaged; re-arm all after Recall/Safe/Look change. Buttons: `onOffToOn` for toggle/pulse. This writes `par.val` on the state par; sliders bound to that par follow ("a bind reference changes ... through its UI, its `val`, or its master", [OH Binding]).
- **Pickup, native (to bench):** Bind CHOP with `pickup` on, export-table rows `name index path parameter enable` pointing at `state` pars [X snippet]. Open: whether a state par that is itself the master of slider binds can also be an export-table reference of a Bind CHOP channel (chain); the snippet instead puts the **CHOP channel** as the master that sliders and the target par both reference. Test once with a signal source (LFO) before hardware arrives; the 2021 pickup thread has no recorded resolution (§2).
- Learn for MIDI is not built into TD: "There is no auto-learn currently" in the MIDI Device Mapper [COMP_UI §6.4, doc MIDI_Mapper_Dialog]; hence the small learn mode above (TDXMorph's ControlMapper and TDMap Pro are the existing implementations of the same idea).
- Controller numbers: only partially sourced and unverified (E §5.3: MIDImix faders CC 19, 23, 27, 31, 49, 53, 57, 61, master 62, knob row 1 CC 16, 20, 24, 28, 46, 50, 54, 58; MPK Mini MK3 knobs CC 70-77 in the MPC program). Read the real values with the MIDI Event DAT before filling rows; never hard-code them in the router.

## 4. Recommendation: build our own, adopt nothing wholesale

Reasons (each is a fact above):
1. **Model mismatch.** Open/free VJ systems (SimpleMixer, SonomikaTD, the 5-layer system, AAVJ) are clip-bank/column mixers. Ours is: a few generative looks, a state/cue list, per-state fades, a kill, hand control now, MIDI later.
2. **Licence.** Presetter, Black-Pomeranian, duarte-amorim, SonomikaTD, AAVJ, Cuelist Sequencer: no licence stated = cannot copy. CuryCue: custom `License.md`, unread. TDXMorph's free parts MIT, but its cue UI (SceneLauncher) and morph UI are paid.
3. **Build/OS risk.** TDXMorph built on 2025.33230 (newer than our final 31550; "7.23.2/31550 final" rule means no upgrade); several tools say nothing about macOS; this Mac runs TD x86_64 under Rosetta.
4. **Size and opacity.** The panel is ~15 controls. A framework adds extensions, SQLite or beta state we would have to audit (user rule: audit, local, free; `AUDIT.md`).
5. **The pieces we need are small and each has a shipped, expanded proof**: widget-to-custom-par bind (autoUI), A/B look crossfade with idle-cook savings (sceneChanger, macOS-authored), Bind CHOP + pickup + export table (snippet), Parameter COMP, button radio groups.
6. **MIDI cost stays low** because the map Table + router exist from step 11 of the build with zero rows.

What to borrow, by name: sceneChanger gate design (or the item itself); autoUI's `bindExpr` recipe; Bind CHOP snippet's export table; TDXMorph's JSON preset idea and ControlMapper's "MIDI on custom parameters" idea; CuryCue's "cues store changed values only" (optional later); the 2013 lessons (big controls, large hit areas, performer view separate from output).

If the user later wants a faster MIDI route: TDMap (commercial, Pro for pickup, MIDImix/MPK not in its factory list) or TDXMorph ControlMapper (MIT, 33230 build, pickup not described). Neither is needed to start.

## 5. Build order (13 steps) with the MCP

All inside `/project1/show`. Rules that apply: `td_guide` first; one structural change per call then `td_errors` (T-31); build resolution 1080x1920; never touch `/jazib_mcp`; `td_create` auto-arranges (don't pass `xy` unless needed); UI panels are positioned by `align`/`w`/`h` (panel units), not by node xy, so `td_layout` only tidies the *network*. After each step `td_errors` on `/project1/show`.

1. **Skeleton.** `td_create` baseCOMP `show` in `/project1`; then inside it baseCOMPs `state`, `live`(or CHOP network), `looks`, `output`, `ui`, `midi`. `td_set_pars` on `state`: `opshortcut = SHOW`. `td_layout` flow + annotate with titles.
2. **State pars.** `td_custom_pars` on `/project1/show/state`, pages: *Master* (`Master` Float 1 clamp 0..1, `Blackout` Toggle), *Look* (`Look` Int 0, `Fade` Float 2 seconds min 0), *Fx* (placeholders `Speed`, `Hue`, `Density`, `Intensity` Float 0..1; the lead names the real ones from the PF26 state list), *Safety* (`Strobelim` Toggle on, `Hitmin` Int 9), *Presets* (`Preset` Int). All Float pars min 0 max 1 normMin 0 normMax 1 clampMin/Max true. Check with `td_get_pars`.
3. **Extension.** `td_create` textDAT `ShowExt` in `state`; `td_dat_text` the class (`GoLook`, `Blackout`, `Safe`, `Hit`, `SetPar`, `Store`, `Recall`, `Learn`; init-safe, state lives in pars/Tables; ASCII only, T-00a); `td_set_pars` on `state`: `ext0object = op('./ShowExt').module.ShowExt(me)`, `ext0promote = on`. Reload via `td_exec` `parent().par.reinitextensions.pulse()`; check by calling a method.
4. **Smoothing.** Create in `output`/`live`: Parameter CHOP (`ops=../state`, `custom` on, `builtin` off) -> Lag CHOP -> Null CHOP `live`. Verify channel names equal par names with `td_info`.
5. **Looks container + 2-3 stub looks.** Try `td_tox_load` of `…/Palette/Tools/sceneChanger.tox` into `looks` (shipped file, not a download; first `pgrep`/`td_status`). Create `scenes` Base, `Scenescomp` = it, pulse `Generatescenetemplate`, move the template in, rename `look1`, add a Noise TOP inside, set resolution 1080x1920, copy to `look2/3`. Fall back to the hand-built A/B gate pattern (§3.2) if it errors. `td_errors`.
6. **Look driver.** Parameter Execute DAT on `state` (`pars = Look`) calling `SceneChange(int(par.eval()), fadeTime=parent().par.Fade.eval())`. `td_set_pars state Look 1` and `td_screenshot` the output Null to see the fade at two moments (flatten caveat T-12 does not matter for opaque looks).
7. **Output chain.** In `output`: Level TOP (brightness/opacity from `live` `Master` and `Blackout`, via `td_set_pars` expressions) -> Null TOP `out`. Test: `Master` 0 = black, `Blackout` on = black after the lag.
8. **Panel layout (td_exec loop, once).** `ui` Container (`sizefromwindow` later, fixed 1280x720 first): header Text COMP, left column look buttons (Button COMPs momentary, text `Look 1..N`), centre Slider COMPs (Master vertical + the Fx sliders), right Safety column (Blackout toggle big, Safe momentary), a monitor Fit/Resolution TOP (small copy of `out`, never the full image). Use `align` (verttb/horizlr) with `hmode/vmode` fill so it scales; set colours; loop in `td_exec`, then `td_layout` check.
9. **Bindings.** For each slider: `td_set_pars <slider> {value0: {bindExpr: "op.SHOW.par.<Name>"}}`; Blackout toggle `value0` likewise; `td_get_pars` to confirm mode BIND. Action buttons: Panel Execute DAT in `ui` with `onOffToOn(panelValue)` dispatching by `panelValue.owner.name` -> `op.SHOW.GoLook(i)` / `Safe()`. Look highlight: expression on each look button `colorr` comparing `op.SHOW.par.Look`. Test two-way: set the par via `td_set_pars` and check the slider's `value0` moved; set slider `value0` and check the par. **This settles COMP_UI Open question 3.** If bind misbehaves: Panel Execute `onValueChange` writes the par, expression on `value0` reads it.
10. **Window.** Window COMP (`winop=/project1/show/ui`, `closeescape` off, `size=custom` with `winw/winh` on 31550 per COMP_UI §7 gotcha 6, `display` = control screen, `setperform`). Open it, `td_perf` after a few normal frames with the UI open (T-05, T-22). `closeescape` plan documented before the show.
11. **Presets.** Table DAT `presets` (header row `slot name json saved`); `Store(i)`/`Recall(i)` in `ShowExt`; a Store and a Recall button with a slot picker (Radio group of buttons 1..8, Button Group DAT as in the buttonCOMP snippet if buttons live in different COMPs); export to `projects/presets.json`. Test: store, move sliders, recall, watch the glide through `live`.
12. **Safety + MIDI stub.** Hit governor (`Hit()` 9-frame rule), `Strobelim` clamp, the luma monitor lamp (§3.6, marked unverified until measured), `Safe()` = recall slot 0. In `midi`: `map` Table DAT (header only), `router` CHOP Execute DAT (reads rows, scaling, pickup state), two MIDI In CHOPs **inactive**, `learn` MIDI Event DAT. Optional bench: an LFO driving a Bind CHOP with `pickup` on, export-table row at `state:Speed`, to see whether slider and Bind CHOP stay in sync (settles COMP_UI Open question 2). Nothing to plug in yet.
13. **Close.** `td_errors` recursively, `td_layout` flow then check on every COMP in `show`, annotate each block (title: State / Smoothing / Looks / Output / UI / MIDI stub), `td_tox_save` `/project1/show` to the bundle (not `td_save_project` unless the lead says so), then add LEARNINGS T-nn entries for each fact settled (bind on plain Slider COMP, sceneChanger on 31550, Lag recall, Window behaviour) and update the README index row for this file.

When MIDI arrives: plug both controllers in before TD starts, set each MIDI In `device`, run Learn per control, fill `map` rows (target, range, curve, mode, bank). No other step changes.

## 6. Open questions for the lead

1. **Looks model:** one look at a time with A/B crossfade (sceneChanger; simplest, idle looks stop cooking) or N weighted slot faders mixed (E §5.5; every active look cooks)? Or both: one base look plus a few overlay faders?
2. **Does a look change belong to a preset?** (preset = values only, cue = look + values + fade time). Affects `Store/Recall` and the state list in `C_pf26_fit.md`.
3. **The control list:** names of the Fx pars, which states (DOORS, HOST, TALK, CHANGEOVER, SAFE HOLD...) get a button, and the **flash numbers** to enforce (README §4 gives 3/s and 25 %; who owns the panic look and its content).
4. **Widgets vs plain COMPs:** I recommend plain COMPs for the performance page and autoUI/Parameter COMP only for an engineering page. Do you want the Basic Widgets look (labels + numeric fields) badly enough to accept ~10 COMPs per control and the package dependency?
5. **Bench items (need TD, not done here):** plain Slider COMP `value0` bind two-way; sceneChanger load and fade on 31550; Bind CHOP `pickup` with an LFO and with a real fader; Panel Execute dispatch; UI cost beside the 7488x2880 render (td_perf).
6. **Try TDXMorph's MIT parts later?** It needs a download (guardrail) and was built on 33230. Say if you want a trial; otherwise the scripted router and JSON Table stand.
7. **Remote surface (phone/tablet):** `remotePanel` is TD-to-TD only. A browser panel would be Web Server DAT / OSC (not researched). Wanted?
8. **Controller numbers and LED feedback:** need a MIDI Event DAT session with both Akais plugged in before TD starts (T-34); MIDImix LED note numbers are unverified (E §5.3).
9. **Where does the panel sit in perform mode on the show Mac:** which display index, and does `/jazib_mcp` stay connected while the editor is closed (COMP_UI Open question 5)?
10. **Licence check of CuryCue's `License.md`** if the cue model is wanted beyond a reference (GitHub reports "Other/NOASSERTION").
