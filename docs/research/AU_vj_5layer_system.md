# AU - Versatile VJ System, 5-layer control and custom UI (Black-Pomeranian, asset 73834)

Researched 2026-10-26. Nothing was loaded into TD or run; the `.tox` and `.toe` were expanded with `toeexpand` (text only).
Sources kept in `research_src/vj5layer_73834/`: `repo/` (the two files, no `.git`), `x_tox/` and `x_toe/` (expanded), `x_tox/types.txt` (op-type census).

## 1. What it is

| Item | Finding |
|---|---|
| Page | https://derivative.ca/community-post/asset/release-versatile-vj-system-5-layer-control-custom-ui/73834 ; author Black-Pomeranian (programmer/VJ/DJ), posted 25 Jan 2026, tag `free`, 1,220 views, 0 comments |
| Download | Page link `VJ_System.tox` (893 KB) is a tokenised derivative.ca file URL: **403 / HTML, not bypassed, not obtained from there**. The same file is in the GitHub repo |
| GitHub | https://github.com/black-pomeranian/VJ-System_Sample - 3.3 MB, 2 files only: `VJ_System.tox` (915 KB) and `BlackPomeranian_VJ_System_Sample.toe` (847 KB). **No README, no licence file** (GitHub API: `license: null`). Shallow-cloned, `.git` removed |
| Forum / video / shop | None linked. Author site black-pomeranian.com returned only a title (VJ / DJ / creative programmer); no TouchDesigner, shop or price text. Instagram `_black_pomeranian` linked, not opened |
| Licence / price | Free tag, no licence terms anywhere. Treat as "free to use, redistribution unstated" |
| Built with | **TD 2025.32050, Windows 10** (`.build` in both files) - 1 build newer than our 31550. Mac status not stated; nothing in the file is Windows-only except hardware names (AKAI MIDI port) and the Sound2Light .exe it expects |
| Outputs | Window COMP `window1` (display 1, fill, borderless) on `out` TOP; toggled by Ctrl+. (`count_UI1['kperiod']` drives `performance`). **No Syphon/NDI/Spout** in the file. Control UI window `main_UI_window` on Ctrl+, (`kcomma`) |
| Inputs | AKAI APC mini mk2 pre-mapped (8x8 pads, faders), mouse; audio features from ETC **Sound2Light** over OSC (127.0.0.1:8001, `oscin` CHOP, address `s2l/out/bpm` etc.) |
| Colour | Uses the community ColorPicker UI Widget (see `AO_colorpicker_widget.md`) |

Size of the network: about 3,000 operators (535 container, 355 base, 462 text DAT, 441 parexec, 51 widget COMPs); most are UI widgets and Palette internals, the actual video engine is small.

## 2. Architecture (verified from the expanded tox)

```
/VJ_System (base)
  main_UI (widget COMP, 1024x810)  --out1 DAT, out2 CHOP, out3 --+
     |  panels: out (layer/param page), container2, container3   |   one CHOP "bus" of named channels
     |  inputs: out/out1 DAT, container3/out1 CHOP, container2/out1 CHOP
  AKAI_APC (base): midiin1 -> 14 math + ~15 select -> out1 CHOP -> `midi` null  (also midiout1 for pad LED feedback)
  Sound2Light (base): oscin -> select/lfo/kick -> out1 -> audioSwitch (CHOP switch, index from UI) -> `audio` null
  movLayer (base) <- in1 CHOP (UI bus), in2 DAT, in3 CHOP (audio)
     |
     +-- select1..10, selectPos/Color/Effector/posteffect : split the bus by channel-name pattern l1*..l5*
     |
     +-- base1..base5  = the FIVE LAYERS (each a base COMP)
     |      mov0..mov10 = clips/generators (each a base COMP; ALL allowCooking=off except the active one)
     |      switch1 (TOP switch, index = midi['index'])  -> out1   (active clip)
     |      cache0..10 (Cache TOP, 75x42, cacheonce, prefill) -> select1..8 -> layout2 -> out2 (thumbnail grid for UI)
     |      movNumMax constant -> out3 CHOP (clip count for UI)
     |      chopexec1: on index change -> all mov*.allowCooking=False, then target mov = True, cache.prefillpulse
     |      some "mov" slots are themselves containers with mov0..2 + count/lfo (sub-variants, a loop through a Switch)
     |
     +-- layer1..5  (Constant TOP, input = baseN/out1, alpha = channel_paramN['sN'])  -- per-layer opacity fader
     +-- chopexec1..5  (CHOP Execute on a per-layer on/off channel): baseN.allowCooking = val   <- hidden layers stop cooking
     +-- Fader (base): in1..in5 (layer5..layer1) -> comp4(in1,const,comp3) -> comp3 -> comp2 -> comp1 -> out1   (Composite TOPs, operand `over`, bottom layer = layer1)
     +-- Effecter (base)   master FX: Invert, Edge, flash, mosaic, strech, tile, acid, pattern, transition, mix; each effect sits in its own base with switch1 (bypass) and its *Num CHOP chosen by the UI
     +-- PostEffect (base) master post FX, ~20 modules: bitmap, bloom, contrast, edge, fish, flare, grid, lens, line, mono, noise, rgb(+rgbaDelay), sharpen, solarize ... each `xxxNum` select CHOP carries its on/amount
     +-- color (base): TOP switch(in1, constant2) fed by colour channels (r g b a)  -> master tint
     +-- transform1 (TOP transform, tx/ty/s from selectPos) -> out1 (TOP out)
     |   thumbnail_manager (Execute DAT): on start, steps through every mov* one at a time (WAIT 180 frames, COOL_DOWN 120), turning cooking on, filling its Cache, turning it off again - builds the thumbnails without cooking everything at once
     +-- out2 = thumbnail layout (256x256 = 75*8 x 42*5), out3 = rename1 CHOP "mov5Num..mov1Num"
  fit1 (TOP fit, 1920x1080) <- movLayer/out1 -> `out` TOP out -> window1 (output)
  engine1 (Engine COMP, file movLayer.tox, cook off, unwired experiment: not used)
  probe, annotate2-5 (Palette probe + annotations), keyboardin_UI, count_UI (kcomma / kperiod toggles)
```

Order of the picture: clip switch (per layer) -> layerN opacity -> Fader (over stack) -> Effecter -> PostEffect -> colour -> transform -> Fit 1920x1080 -> output window.
Effects are **master only** (not per layer): layers have clip select, on/off, opacity, colour (via the shared `color` chain), position/scale; layer 1 = bottom, layer 5 = top (the page says top layers carry overlays/text).

Blend mode: only `over` in the Fader comps (fixed; no per-layer blend selector). Opacity: `alpha` par of each layerN Constant TOP bound by expression to `channel_paramN['sN']` - **exact fade maths unverified** (the Constant TOP is fed by the clip as input; how its alpha results in a faded layer inside the Composite chain was not traced further, treat as UNVERIFIED).

### Clip loading
No file browser or runtime loader. All clips are **pre-built child COMPs** (`movN`: generators such as noise/rectangles/SOP geo/fluid GLSL/text, plus a few `moviefilein`/photo `.tif/.png` stills). Samples reference the author's `C:/Users/ryoro/...png` (broken on our machine) or `app.samplesFolder` Banana/Jellybeans. Choosing a clip = changing the Switch index from MIDI/UI. Adding a clip = copying a base into `movN` and extending `movNumMax` / the switch inputs by hand.

## 3. UI design patterns

- **Not a Parameter-Palette autoUI.** It is a hand-built **widget COMP** (`main_UI`, 1024 x 810, `h = w*9/16` expression, `align horizlr`, spacing 8) containing sub-containers: a "param" page (radio buttons, rocker buttons, master knobs, text editor, colour picker), a sliders block (6 containers: one fader per layer plus master) and a position block (`pos/sliders`, 3 sliders). 51 `widget` COMPs in total (buttonRadio, buttonRocker, masterButton, masterKnob with a **GLSL knob** `glslKnobWidget`, slider, masterTextEditor, spacer). They are the Derivative "basicWidgets"-style widget set, not custom classes; the `externaltox` pars point at `TDPackages/button/button.tox` and `slider/slider.tox` but `enableexternaltox` is **off** everywhere, so the tox is self-contained.
- **Single screen, no scrolling.** Instead of a long column, density is solved with: fixed 16:9 canvas; five parallel layer columns each with a clip picker, on/off and fader; a **thumbnail grid** (Cache TOPs + Layout TOP) so clip choice is visual; one **radio/rocker row** per effect group (FX on a row of toggles, amount on a single shared knob set `peKnob1..5`, `masterKnob1..5`); master pages for Effector / Post-Effects / Text are separate containers shown in turn. No tabs implemented as a tab bar; pages are fixed rectangles.
- **Binding.** Each widget has `output` base + `code` base + `label`/`overlay` containers; widgets write values to a Custom-parameter-like `Value0` which is read by CHOP exports. All widgets feed **one CHOP bus** (`out2` / container2/container3 `out1`) whose channel names encode layer and function (`ch1n1..ch1n8`, `ch1n120-..`, `ch1ctrl56-..` -> renamed by Select CHOPs using `l1* .. l5*`, `r g b a`, `s tx ty`, `peKnobN`, `mov5Num..mov1Num`). The same bus naming is produced by the `AKAI_APC` base (note numbers 1-120, ctrl 56), so **MIDI hardware and mouse UI write the same channels** (one control surface abstraction).
- **Hotkeys.** Ctrl+, opens the controls window, Ctrl+. the output; both are Keyboard In CHOP -> Count CHOP -> window pars.
- **Preset/cue system: none.** No preset/cue/scene store, no table of scenes. State lives only in the widgets.
- **MIDI/OSC.** MIDI In (APC mini mk2) + MIDI Out (LED feedback); OSC In on 127.0.0.1:8001 for Sound2Light; no OSC out, no Resolume/Syphon/NDI.

## 4. Cooking and performance patterns

1. **allowCooking as a layer switch.** `CHOP Execute` DATs set `baseN.allowCooking = val` from the layer on/off channel, so a hidden layer costs almost nothing.
2. **One live clip per layer.** On clip change, `chopexec1` first turns *every* `mov*` off (`allowCooking = False`), then turns only the new one on. All `movN` ship with `cook off` saved.
3. **Switch not Cross/Comp for source choice** (TOP Switch, index from MIDI); crossfade/blend is a separate Composite chain. Clip count limited via `limitmax` on Count CHOP.
4. **Cache TOP thumbnails**: tiny (75x42) `cacheonce`+`prefill`; a Prefill pulse after a clip turns on; `thumbnail_manager` fills them serially (3 s load wait, 2 s cool-down per clip) so start-up never cooks 55 clips at once.
5. **Effects as bypassable modules**: each effect has its own switch/level so unused modules are skipped, controlled by CHOP "Num" channels.
6. `timeslice off` on most utility CHOPs to avoid per-frame cost; Engine COMP experiment left cooking off (shows intent to isolate clips in separate processes; not wired).
7. Not used: no instancing tricks, no `Cook Type`-based throttling, no Null-cached expressions. Heavy part is the master Effecter/PostEffect chain (always in the graph).

## 5. Audit

| Check | Result |
|---|---|
| Network | `oscin` listens on 127.0.0.1:8001 (loopback). One `socket.gethostbyname_ex(gethostname())` in `Sound2Light/execute1` only to show the host's IP in a table. No HTTP, no outbound sockets |
| Subprocess / os / pip / importlib | none found in any of the 1,359 text DATs (grep with `-a`) |
| eval / exec | ~980 hits are the Palette `par.eval()` / `ppar.X.eval()` methods; no `exec(`, no `eval(` on external strings |
| File access | `.png/.tif` paths to the author's `C:/Users/ryoro/...` (missing on other machines) and `app.samplesFolder`; shader files `fluid/shader/*.frag` (relative); external tox disabled |
| Hardware | MIDI In/Out, Keyboard In, OSC In, Window COMP output; no Audio Device |
| Licences in file | MIT (Thomas Diewald fluid shaders, 5 mentions), Derivative Palette agreement, DBraun TouchDesigner_Shared |
| Op types | 195 distinct op types census: all long-standing ops (Engine COMP and engineout exist in 31550). Names that did not match our `ops/INDEX_2025.31550.json` are just the short internal keys (`comp`=compositeTOP, `mono`=monochromeTOP, `midiin`=midiinCHOP, `keyboardin`, `oscin`, `parexec`, `panelexec`, `chopexec`, `opexec`, `eval`, `engine`...). None are newer-than-31550 types. Built on 32050, so a few parameter defaults may differ: UNVERIFIED until loaded |
| Verdict | **Safe to read and borrow; loading is low risk.** Not tested live. Needs Windows-only fix-ups (media paths, AKAI port name) |

## 6. Verdict for us

- **Not adopted as-is**: Windows build, hard-coded APC mapping, no presets, one fixed `over` blend, master-only effects, no Syphon/NDI output, no licence. Our show rig needs per-artist cue state and Arena as the output host.
- **Worth borrowing (ideas, no code copied):** the cooking pattern (allowCooking per layer and per clip, only one live source), the single named-channel control bus shared by MIDI + UI, thumbnail previews via small Cache TOPs filled serially, fixed-canvas dense panel, GLSL knob widget, bypass-by-switch effect modules.
- Avoid: ~3000 ops of UI scaffolding; hand-copying clips; always-present master chains.

## 7. Patterns our MCP should adopt

1. **`td_build` layer-mixer macro** (`layer_mixer`): args `layers=N`, `sources=[comp paths or tox]`, `blend='over'|'add'|...`. Builds N slot COMPs (a Switch TOP over the source COMPs, index par `Source`), per-layer custom pars `Active`, `Opacity`, `Blend` (menu), `Source` (menu), an Opacity (Level TOP or Composite alpha) per layer, a Composite chain bottom->top, `Master` Level, and a clean `Out` TOP. Add a CHOP Execute / Par Execute on `Active` that sets `slot.allowCooking`, and on `Source` that sets cooking on only the chosen source (set all sources `allowCooking=False` at build).
2. **Cooking guard utility**: `td_cook_only_active(parent, active_index)` - the 3-line pattern above; also as an option on `td_build` effect banks (all effect modules built with `bypass` Switch + `allowCooking`).
3. **Serial thumbnail builder**: optional "thumbs" mode that makes a Cache TOP per source and fills them one at a time with a cool-down (use only when asked; keeps our "no extra tools" rule).
4. **Named-channel control bus**: one Null CHOP per rig with channels `l<layer>_<param>` (e.g. `l2_opacity`) that custom pars, MIDI and OSC all write; documented naming so a controls panel (autoUI) and an Arena/OSC bridge can bind to the same names.
5. **Controls panel without a long column**: fixed-size window; one *column per layer* + a master column, a header row of page buttons (radio buttons that swap which `container` is visible via `display` pars, not separate windows), grouped parameters; for our autoUI panels add a collapsible-section helper (Section header button toggles `display` of its child container and re-flows with `align`). Test with `td_screenshot`.
6. **Multi-output**: add to the macro an optional Syphon Out / NDI Out TOP fed from `Out` (Syphon on Mac) - this system lacks it, and it is exactly our Resolume link.
7. **Hotkey windows**: Keyboard In -> Count CHOP -> Window `winopen`/`performance` for controls and output windows (matches our "controls window"). Do not copy the Engine COMP experiment (cook-off, unused).

## 8. Open items / UNVERIFIED

- Whether the file runs unchanged in 31550 (built in 32050); media paths in clips are the author's Windows paths.
- Exact fade math of `layerN` Constant TOPs inside the Fader chain; the sample `.toe` was only checked for structure (it wraps the same `project1`).
- No live UI test; no price/forum/video links existed to follow; the tokenised page download was 403.
