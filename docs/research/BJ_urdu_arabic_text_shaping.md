# BJ - Urdu / Arabic (RTL, Nastaliq) text shaping in TouchDesigner, and a clean-room `urdu_type` COMP (research, 26 Oct 2026)

Target: TD 2025.31550 (final build for this project), macOS M1 Max, TD under Rosetta (x86_64 Python 3.11), Vulkan/MoltenVK (T-46: multi-pass GLSL can tear, compute-mode GLSL is clean; T-18: Optical Flow TOP etc. unsupported).
General-purpose TD; PF26 is not a constraint here. Licences are noted, not gating (user rule: licences irrelevant for research).
Notation: **page** = read from a web page or the offline docs bundled in the TD app; **probed** = measured on this Mac without TD; **prior** = earlier note in this folder; **UNVERIFIED** = not established.
Nothing was loaded into TD (no `jazib-td` call), no code downloaded or run (only the already-installed `hb-shape` / `fribidi` / `python3 -I` for read-only probing), no pip, no logins. `research_src/BJ_urdu_arabic_text_shaping/` was **not created**: nothing needed downloading.

Already covered elsewhere, not repeated: Text TOP Urdu live probe (`A_td_2025_howto.md` section 5, images `refs/A_td_howto/urdu_*.png`), engine table, overhang/word-space/language-tag gotchas, calligraphy-as-plate recipes (`Q_live_typography.md` 4.1-4.2), HyperFrames/HarfBuzz pipeline (`~/Documents/StageLab_PrismFest/hyperframes/LEARNINGS.md` U-01..U-07, H-20; `AUDIT.md` section 3). This file adds the shaping landscape, new measurements, mixed-line/bidi handling and the build spec.

---

## 1. Top findings

1. **Text TOP shapes Urdu natively** (prior, probed live: joined forms, right-to-left word order in Noto Nastaliq Urdu and Geeza Pro). TD text uses the macOS system text layout (CoreText) for the Text TOP; that is why joins work with no HarfBuzz in the app. The docs never state this: the offline page `Unicode.htm` says only "Unicode text is fully supported", "fallback fonts will be used if a Unicode character can not be displayed" and (important for pipelines) "**Tscript does not support Unicode**, so anything that goes through TScript will lose Unicode characters". No Arabic/shaping/bidi sentence exists in the Text TOP/SOP/COMP/POP pages (page, offline bundle + docs.derivative.ca).
2. **There is no HarfBuzz, FriBidi, FreeType or Pillow inside the TD app** (probed: `find` of the bundle; site-packages = attrs, cv2, numpy 2.1.2, depthai, jsonschema, PyYAML, requests, pygdtf, pymvr, etc.; no fonttools, no PIL, no arabic_reshaper, no bidi). CEF (Web Render TOP) bundles Chromium, whose text stack is HarfBuzz-based (prior: hyperframes RESEARCH). Slug (Text COMP / Geo Text COMP / Text TOP "Scalable") is a **renderer**, not a shaper, per its own repo ("reference shader implementations", no mention of shaping/layout/Arabic: page, [github.com/EricLengyel/Slug](https://github.com/EricLengyel/Slug)); how TD feeds Slug Arabic text is **UNVERIFIED** (see 5.2 probe P3).
3. **Text POP is not in 31550** (new in 2025.32460, 10 Mar 2026; macOS/font-file fixes in 2025.32820: page, [release 2025.32460](https://derivative.ca/release/202532460/74120), [Text POP docs](https://docs.derivative.ca/Text_POP)). Its docs have `Reading Direction`, `Break Language`, `GlyphId`/`CpIndex`/`GlyphIndex` attributes, "does most of its work on the CPU", and say **nothing** about shaping/Arabic/bidi. The 32460 notes list no Arabic/RTL change; they mention only "fixed issues with fallback fonts for various text nodes", which implies **fallback fonts in 31550 can misbehave** (UNVERIFIED, see probe P5). Build 2025.33230 is the current official build (1 Sep 2026); upgrading is not allowed (project directive), so everything POP goes to FUTURE.
4. **Best route in 31550 = whole-word rasters from the Text TOP, with our own thin layout layer.** Arabic-script joining stops at spaces, so shaping each word on its own is identical to shaping the whole line (exception: kerning across the space, which Nastaliq does not use; own reasoning). That makes **word-level animation, per-run fonts, mixed-script lines, Nastaliq word spacing and exact overhang bounds** possible without touching a glyph. It also respects the "names stay whole" rule from earlier notes.
5. **Measured facts about Noto Nastaliq Urdu** (probed with HarfBuzz 14.6.0 `hb-shape` on `hyperframes/studio/assets/fonts/noto-nastaliq-urdu/NotoNastaliqUrdu-VF.ttf`; the system copy is `/System/Library/Fonts/NotoNastaliq.ttc`, which has the families "Noto Nastaliq Urdu" and "Noto Nastaliq Urdu UI"):
   - UPM 1000, hhea ascent 1904 / descent -596 (**line box 2.5 em**), OS/2 win ascent/descent 1904/1382 (3.29 em). A Text TOP tile must be about **2.5-3 em tall**, not 1.2 em.
   - Shaping is heavy: `اردو زبان` = 9 code points -> **13 glyphs** (dots/marks are separate glyphs with y offsets down to -275 units; whole-line advance 3393 units = 3.39 em). Further oracles: `پرزم` 7 glyphs / 1617; `علی ظفر` 11 / 2515; `حسن رحیم` 12 / 3605 (advance units, UPM 1000). These are the "live verification numbers" for the build (width of the trimmed alpha raster should land within about 10 % of advance x fontsize / 1000, more because marks overhang).
   - Axes: variable font, `wght` 400-700 (prior, hyperframes AUDIT). TD exposes no variation-axis parameter (prior): weight in TD = pick `typeface` Bold, or the Web Render route.
   - With shaping features switched off (`-init,-medi,-fina,-calt,-rlig,-liga,-ccmp`) the same string comes out as isolated letters (Alef, Beh, Zain, ...): a ready-made "broken" negative control for tests.
   - `hb-shape` cost: 17 ms per call including process start (50 calls = 0.87 s), arm64 binary at `/opt/homebrew/bin/hb-shape`; a Rosetta (x86_64) parent can spawn it. FriBidi 1.0.16 (`/opt/homebrew/bin/fribidi`) is also installed and is the **offline oracle for bidi ordering** (e.g. `ہیلو hello اردو 2026 world` -> levels `1 1 1 1 1 2 2 2 2 2 1 ...`, digits stay LTR inside the RTL run, visual order reversed per level).
   - Pillow 12.3 on the system Python has **no raqm/fribidi/harfbuzz** (probed `features.check`), so it cannot be a text oracle; use `hb-shape`/`hb-view`/`fribidi`.
6. **Pure-Python options without pip exist only as vendored source** (needs the user's go-ahead because it is an install/import): `arabic_reshaper` (MIT, reshapes to Presentation Forms, [repo](https://github.com/mpcabd/python-arabic-reshaper); README says "Arabic, Farsi, and Urdu"; Nastaliq/ligature-rich fonts like Noto Nastaliq depend on GSUB shaping rather than presentation forms, so it is a poor fit; own reasoning) and `python-bidi` (**LGPL-3.0**, pure-Python V5 implementation plus a Rust wrapper, [repo](https://github.com/MeirKriheli/python-bidi)). Notch documents the same pattern "reshape the string before rendering, then enable Right To Left" ([Notch Reshape Arabic Text](https://manual.notch.one/2026.1/en/docs/reference/nodes/text-fx/reshape-arabic-text/)): that is for renderers that cannot shape; TD's Text TOP can. **Not needed** for the recommended build.
7. **Do not apply `tracking` to Arabic-script text** (prior: W3C CSS Text 3 "breaks cursive joins"); use word gaps. Do not split a word into per-letter elements (prior U-01).
8. **Per-glyph work (3D, atlases, letter animation) needs an outline/shaping source TD 31550 does not have.** The only clean path is offline: shape with HarfBuzz, rasterise/MSDF the glyph ids (msdf-atlas-gen supports `-glyphset` by font **index**, MIT, needs vcpkg/CMake build, no Arabic mention: [repo](https://github.com/Chlumsky/msdf-atlas-gen), page) and feed a table of glyph id / position. Parked in FUTURE (section 8).

---

## 2. Landscape (ranked for 31550 on this Mac)

| Rank | Tool / asset | What it gives | Mac / 31550 status | Licence | Verdict |
|---|---|---|---|---|---|
| 1 | **Text TOP** (system layout), Display Method Automatic/Scalable (Slug) or Fixed | Correct joins + RTL order for a word or a line; fallback fonts; `fontfile`, `readingdirection`, `trackingx`, `strokewidth` | **Verified live** (prior A section 5) | built in | Primary. One Text TOP per word. |
| 2 | **Own layout layer** (Python bidi-lite + alpha-bbox measuring + per-word transforms) | Word-level animation, mixed lines, per-run fonts, wrapping, Nastaliq spacing | Buildable now; logic testable offline against `fribidi` and `hb-shape` | ours | The build spec below. |
| 3 | **Web Render TOP** (CEF 132, Chromium HarfBuzz) | Real OpenType shaping incl. variable `wght`, `lang="ur"`, CSS `word-spacing`, GSAP per-word spans | CEF helpers are bundled; `transparent` par exists; **alpha, 30 fps cap (`maxrenderrate`) and 2.0 `dpiscale` on this Mac UNVERIFIED** (prior Q 4.1) | CEF BSD, our HTML ours | Optional second backend (spec B). |
| 4 | **Text COMP / Geo Text COMP** (Slug) | RTL option + "Bidirectional layout is also supported when LTR characters are detected when using RTL mode" (page: offline `Text_COMP.htm`), inline `{#color();track()}` codes | Whether Arabic shaping happens before Slug is **UNVERIFIED** (probe P3). Geo Text instancing limited to 128 textures on macOS (prior) | Slug MIT/Apache + patent dedicated to public domain 17 Mar 2026 (page, [coverage](https://hackaday.com/blog/page/179/?cat=GNB)); credit required if distributed | UI text and 3D; test before trusting. |
| 5 | **Text SOP** | Extruded 3D; `Language` hint (`ur`, `ar`, `fa` in `SOP_Unicode_Language_Abbreviations`), `Reading Direction` | Joining **UNVERIFIED** (probe P4) | built in | Test only if 3D needed. |
| 6 | Text POP | glyph attributes, extrude | **Not in 31550** | built in | FUTURE. |
| 7 | HyperFrames pre-render (sibling repo) | Finished Urdu motion with alpha via real HarfBuzz | Works (their U-05, H-20) | Apache-2.0 / MIT harfbuzzjs 1.6.3 | Use as a clip source via Movie File In when a finished animation is wanted. Read-only here. |
| 8 | harfbuzzjs 1.6.3 (WASM, MIT) in a Web Render page | In-page shaping, `glyphToPath` outlines for per-glyph SVG | Their recipe works in Chrome; in CEF **UNVERIFIED** | MIT | Spec B bonus, still word/word-level. |
| 9 | `uharfbuzz` (Apache-2.0, [repo](https://github.com/harfbuzz/uharfbuzz)) | Python bindings, bundles HarfBuzz, shaping + glyph infos (outline draw API not on the page I read) | Needs pip; macOS x86_64 wheel availability **UNVERIFIED** | Apache-2.0 | FUTURE (gated install). |
| 10 | `msdf-atlas-gen` (MIT) | MSDF atlas + JSON metrics from glyph indices | Build needs CMake/vcpkg; offline pre-bake tool, not TD | MIT | FUTURE glyph-atlas route. |
| 11 | `arabic_reshaper` + `python-bidi` | Presentation Forms reshape + bidi | Pure Python vendored source possible; python-bidi LGPL | MIT / LGPL-3.0 | Not needed; fallback if a font lacks GSUB shaping. |
| 12 | Community assets | No Arabic/Urdu-specific TD tutorial or component found (searches: Text TOP + Arabic, forum Arabic/Persian/Urdu, TD + HarfBuzz returned nothing from derivative.ca). The one hit is an old forum thread that Arabic text shows "?" through the UE TouchEngine plugin (prior Q 4.1). | - | - | Absence is evidence only of low search reach: UNVERIFIED. |

Searches that produced nothing useful (record so nobody repeats them): "TouchDesigner Arabic text shaping Text TOP letters disconnected", "forum.derivative.ca Arabic Persian Urdu Text COMP Slug", "Slug Lengyel Arabic shaping HarfBuzz", "TouchDesigner Text POP 2025.32460 HarfBuzz". YouTube transcripts were not pulled (no TD+Arabic video surfaced in text results; yt-dlp left unused to avoid rate trouble).

---

## 3. How it works in TD (mechanics that matter)

- **Shaping happens inside the Text TOP/SOP/COMP via the OS font stack**; the app exposes only `font`/`fontfile`, `typeface`, `readingdirection`, `breaklang` (menu has english, german, spanish, french, japanese, korean, russian, chinese: **no Urdu/Arabic entry**; prior dump) and, on Text SOP/POP, a `Language` string using Unicode abbreviations (page: `ur`, `ar`, `fa`). `breaklang` only affects line breaking.
- **Reading Direction** flips paragraph direction. For a pure-RTL word both settings gave the same glyph order in the prior probe (RTL order comes from the Unicode bidi algorithm in the text engine); mixed lines need the direction set to the *base* direction (page: Text COMP "Bidirectional layout is also supported when LTR characters are detected when using RTL mode"). For Text TOP the same applies **UNVERIFIED** (probe P2).
- **Unicode in DATs/Python is fine; TScript is not** (page `Unicode.htm`): never route Urdu text through `tscript`, `op('x').run()` strings containing TScript, or old-style `me.` TScript evals. Python `par.text = ...` and Table DAT cells are fine. Text files must start with a BOM or TD assumes CP1252 (page); write cue files as UTF-8 **with BOM** or load them with a Python read.
- **Raster size vs overhang**: Nastaliq line box is 2.5 em and marks overhang the advance box (prior U-03); the Text TOP resolution must cover `fontsize x 2.7` high and `advance x 1.2 + 0.4 em` wide. Alignment inside a fixed tile shifts for RTL; measure, do not assume.
- **Slug path** (`dispmethod=scalable`, default at font size >= 16 per page `Slug_Library.htm`): "ignores font hinting" (Slug repo), good for large sizes; macOS Text TOP Stroke fix landed only in 2025.32820 (prior), so the `strokewidth` par on 31550 may misbehave on macOS: build outlines from the alpha (section 5, stage 6), not from `strokewidth`.
- **Variable font weight** is not reachable from TD pars (prior); `typeface` Bold on a variable font picks a named instance if the OS exposes it (UNVERIFIED).
- **Alpha**: Text TOP can output premultiplied (`premultrgbbyalpha`); our COMP's final output is premultiplied (project rule `overlay-alpha-premultiplied` is PF26-specific, but the same trap applies to any glow edge).

---

## 4. Mixed lines and bidi (what the COMP must implement)

Unicode bidi (UAX #9) matters when an Urdu line contains Latin words, numbers or punctuation. The Text TOP resolves it internally for one string, but a **per-word** layout needs it at the layout layer.

**Bidi-lite spec (Python, ~80 lines, no deps):**
1. Classify each word by its first strong character: Arabic-script ranges (U+0600-06FF, 0750-077F, 08A0-08FF, FB50-FDFF, FE70-FEFF) = `R`; Latin/other letters = `L`; digits = `EN` (Urdu digits U+06F0-06F9 and Arabic-Indic U+0660-0669 = `AN`, rendered by the font's own forms); punctuation-only tokens = neutral.
2. Base direction `Direction` par: `auto` (first strong word decides), `rtl`, `ltr`.
3. Resolve neutrals and numbers like UAX #9 rules W/N: a number between two RTL words stays LTR *internally* but takes its place in the RTL run; a neutral between two same-direction words takes that direction, otherwise the base direction.
4. Output `visual order`: reverse runs by embedding level (rule L2: reverse from the highest level down to the lowest odd level). Words inside an LTR run keep logical order; the run as a block sits in RTL flow.
5. Each word's Text TOP gets `readingdirection` = its own run direction, and the Urdu/Latin font par for its script. Punctuation attached to a word (the Urdu full stop `۔`, comma `،`, quotes) stays in the word token so it renders in the same raster (avoids mirroring/ordering bugs; mirrored brackets: swap `(` `)` for RTL runs, UAX #9 rule L4, own list of 4 pairs).
6. **Offline test oracle**: `fribidi --nopad --nobreak --charset UTF-8 --levels` on the same string. The test compares *which words end up left/right of which*, not glyph shapes. Pass criterion: for a corpus of at least 30 lines (pure Urdu, Urdu+English, Urdu+digits, English+Urdu, brackets, URLs), word visual order equals FriBidi's, and `levels` per word equal. Known: FriBidi splits at character level; the tool only needs word granularity, so tokens that mix scripts without a space (`2026ء`) are flagged and rendered as one raster.

**Per-run fonts**: `Fontrtl` (default `Noto Nastaliq Urdu`), `Fontltr` (default `Helvetica Neue`/any), `Fontdigits` (optional). Because fallback-font handling had bug fixes later (32460), a Latin run in an Urdu font should be avoided by this split (UNVERIFIED that 31550 misbehaves; probe P5).

---

## 5. Clean-room build spec A: `urdu_type` (self-contained effect COMP)

**Suggested path:** `/project1/lab/BJ_urdu_type` (builder may rename the COMP `urdu_type`). **Goal:** shape Urdu/Arabic/mixed text into per-word rasters and animate **words** (stagger, reveal, slide, scale, pulse), with an exact layout, wrapping, outline and glow, controlled by custom pars, BPM, manual progress or audio level. No per-letter motion in v1.

Rules applied: self-contained (custom pars drive the internals, no outside refs), `out` ops only output, own controls panel + `controls_window` opened by an `Opencontrols` pulse, no built-in limiters/warnings (the operator decides; ranges are soft), BPM/manual/audio options, Mac default speaker unaffected (the COMP has no audio output; optional audio-in is a CHOP input, never mic->speaker), arranged left-to-right with titled stage boxes (T-66/T-69), `td_layout flow` after building.

### 5.1 Custom parameters (names: one capital then lowercase/digits)

Page `Text`:
- `Text` (Str, multiline; default `اردو زبان` plus a second test line), `Textdat` (OP; if set, line N of the Table/Text DAT overrides `Text`; cue index `Line`), `Line` (Int cue index), `Direction` (menu auto/rtl/ltr), `Fontrtl` (Str menu from the Text TOP font list), `Fontfilertl` (File, overrides), `Fontltr`, `Fontfileltr`, `Typefacertl` (menu Regular/Bold), `Size` (Float px, default 160 for 1920x1080 out), `Wordgap` (Float em, default 0.30; Nastaliq space is narrow, prior U-07), `Linegap` (Float em of the line box, default 1.0 => 2.5 em Nastaliq line box; soft range 0.4-2), `Maxwidth` (Float px, 0 = no wrap), `Align` (menu start/center/end; "start" = right for RTL), `Anchorx`, `Anchory` (0-1 inside the output), `Maxwords` (Int, default 24; fixed pool size).
Page `Style`: `Fill` (RGB), `Fillalpha`, `Outline` (RGB), `Outlinepx`, `Glow` (Float), `Glowcolor`, `Shadow` (Float), `Bgalpha` (0 = transparent), `Bgcolor`, `Premult` (toggle, default on).
Page `Anim`: `Mode` (menu none/fade/slide/scale/wipe/blur/pulse), `Stagger` (Float 0-1 fraction of the transition), `Order` (menu reading/reverse/random/center-out), `Slidex`, `Slidey` (px), `Scalefrom` (Float), `Blurmax` (px), `Pulseamt`, `Timing` (menu manual/seconds/bpm/audio), `Progress` (Float 0-1; manual and the readback), `Seconds` (duration), `Bpm`, `Beats` (duration in beats), `Audiolevel` (Float, or CHOP input `in1` channel `level`), `Audiogain`, `Trigger` (pulse: restarts the time-based transition), `Hold` (toggle: freeze Progress), `Loop` (toggle), `Ease` (menu linear/ease/expo).
Page `Layout`: `Measure` (menu alpha/hbshape; hbshape only if `/opt/homebrew/bin/hb-shape` exists, else silently alpha), `Tilew`, `Tileh` (word tile size, default 1536x768 at Size 160), `Pad` (em, default 0.55 x 0.4 per prior U-03), `Rebuild` (pulse).
Page `Control`: `Opencontrols` (pulse), `Showinfo` (toggle).
Read-only `Info` page: `Nwords`, `Nlines`, `Layoutms`, `Cooktilesms`.

### 5.2 In / out

- Inputs: `in1` TOP (optional background; composited under), `in2` CHOP (optional; channels `level`, `beat`, `progress` override `Audiolevel`/`Progress` when `Timing` says so). Nothing else is read from outside the COMP.
- Outputs: `out1` TOP (RGBA, premultiplied if `Premult`), `out_words` DAT (Out DAT: word table), `out_rest` CHOP (per-word channels). Out ops hold no logic.

### 5.3 Stage-by-stage network (left to right, one titled box per stage, T-66/T-69)

1. **Parse** (Text DAT `parse` + Script DAT; output Table DAT `words`): tokenise `Text` on spaces/newlines (Unicode whitespace, keep the Urdu full stop `۔` and `،` glued to the word), run bidi-lite (section 4), write columns `idx, text, dir, level, script, line, visual_idx`. Pure function `parse(text, direction) -> rows`: **offline-testable** against `fribidi` and a fixed corpus (no TD needed; run with the system `python3 -I`).
2. **Rasterise** (pool of `Maxwords` Text TOPs `w00..wNN`, each `text = op('words')[i,'text']`, `font`/`fontfile` per script, `readingdirection` per dir, `bgalpha=0`, `alignx=center`, `aligny=center`, resolution `Tilew x Tileh`, `premultrgbbyalpha` per `Premult`): static tiles; cooks only when the word table changes. `Maxwords` is a hard pool: extra words beyond the pool wrap to the next cue (operator's choice; no warning).
3. **Measure** (Python on `Rebuild`/table change, not per frame): for each tile read `op('wNN').numpyArray()` (float32 RGBA), find the alpha bounding box (threshold 0.02), store `bbx0,bby0,bbx1,bby1` and the baseline offset in `measure` Table DAT. Optional `Measure=hbshape`: also run `hb-shape --output-format=json` per word through `subprocess` to cross-check width within 10 % (a **diagnostic**; any failure falls back to alpha silently). GPU readback happens only here (about 24 tiles x 1536x768x16 B = 450 MB peak if all read at once: read one tile at a time and discard, or switch the pool to 8-bit via `format=rgba8fixed` for measuring, a builder decision to verify).
4. **Layout** (Python, pure function `layout(measure_rows, params) -> rest positions`): lines are filled from the start edge (right for RTL), `Wordgap` x Size between boxes (box = trimmed bbox, **not** advance), wrap at `Maxwidth`, line pitch = `Linegap` x 2.5 x Size for Nastaliq (read from the font's hhea when `Measure=hbshape`, else a `Lineh` internal default 2.5; keep an override par `Lineh` in the Layout page), alignment per `Align`, anchored by `Anchorx/Anchory`. Output `out_rest` CHOP: channels `x{i}`, `y{i}`, `w{i}`, `h{i}`, plus `rank{i}` (animation order from `Order`). **Offline test**: layout of two fixed measure tables must produce identical positions on every run and respect: no box overlap, line 1's start edge at the anchor, wrapped lines never exceed `Maxwidth` (except a single word wider than the width).
5. **Animate** (Script CHOP `anim`, 1 sample, `Maxwords x 7` channels: `tx,ty,sx,sy,rot,alpha,reveal`, pure function `anim(i, rank, n, p, params)`): `p` comes from `Timing`: manual `Progress`; seconds `(absTime.seconds - t0)/Seconds`; bpm `beats = (absTime.seconds-t0) * Bpm/60 / Beats`; audio `Audiolevel x Audiogain` (smoothed with a Lag CHOP). Per-word local progress `lp = clamp((p - rank*Stagger/n) / (1 - Stagger*(n-1)/n), 0, 1)` then `Ease`. Modes: fade = alpha; slide = tx/ty from `Slide*` toward 0; scale = from `Scalefrom`; wipe = `reveal` 0-1 along the word's reading direction (mask edge, padded so tails are not clipped, prior U-03; a wipe shows part of the word during the transition, acceptable only if the operator chooses it); blur = `Blurmax` x (1-lp); pulse = scale 1+`Pulseamt` x level. **Offline test**: tabulated `anim()` values at p = 0, 0.25, 0.5, 1 for 3 words in each mode equal a golden table; word 0 is first in reading order (right-most for RTL).
6. **Place + style** (per word, only the first `Nwords` are live; the rest bypassed): `Text TOP wNN -> Crop TOP (to trimmed bbox, plus Pad)` (also drives `reveal` through animated crop edge in reading direction) `-> Transform TOP (translate x,y from CHOP, scale, rotate, pixel units, filter: bilinear)`. One **Composite TOP** (Over, `Maxwords` inputs) merges them: single pass, no GLSL tearing risk (T-46). Outline: from the merged alpha: `Blur (outline radius) -> Level (threshold) -> Subtract the unblurred alpha` for a hard rim, `Over` behind the fill (no `strokewidth` par, 31550/macOS risk). Glow: `Blur (Glow) -> Add behind`. Shadow: `Transform + Blur + Level`. If any step needs per-pixel math use one **GLSL TOP in compute mode** (T-46, clean), never a chain of render-mode passes.
7. **Compose + out**: background (`in1` or `Bgcolor`) under the text, premultiply toggle, `Null` named `result`, `out1` = Out TOP. Preview TOP of the same size for the controls panel.
8. **Controls**: panel COMP `controls` (autoUI-free; sliders/fields bound to custom pars, the Basic Widgets route works on 31550: T-52/T-68) plus a Window COMP `controls_window`; the `Opencontrols` par's `onPulse` opens it (`controls_window.par.winopen.pulse()`); `Showinfo` shows `Nwords/Nlines/Layoutms`. **Never destroy ops/panels while a window or pane shows them** (T-70: SIGBUS).

### 5.4 Offline-testable logic (no TD)

All five pure functions (`parse`, `layout`, `anim`, `bbox_from_alpha`, `hb_advance_check`) live in one `urdu_logic.py` stored in the COMP as a Text DAT **string, not a function in op storage** (T-67), and mirrored on disk for tests. Tests run with `python3 -I` plus `numpy` (system) and the installed `fribidi`/`hb-shape`:
- bidi order and levels = FriBidi's on 30+ lines (section 4.6);
- `anim` golden table;
- `layout` invariants (no overlap, wrap width, determinism);
- `bbox_from_alpha` on synthetic alpha arrays (empty, single pixel, negative offsets);
- `hb_advance_check`: for the four words in 1.5 the advance sums are 1617 / 2515 / 3605 / 3393 (UPM 1000) with `--language=ur` and the negative control (features off) produces isolated letters (glyph count equals code-point count).

### 5.5 Live verification numbers (builder checks in TD, using the existing Text TOP, no new probes needed beyond P1-P5)

- `اردو زبان` in Noto Nastaliq Urdu at Size 160 -> two tiles; trimmed width of word 2 (`زبان`) and word 1 (`اردو`) together plus a `Wordgap` gap about 0.30 x 160 px; total shaped advance 3.393 em = 543 px (+/- 10 % because marks overhang; the alpha bbox may exceed the advance by up to about 0.2 em on tails).
- Tile height needs `Size x 2.7` = 432 px minimum; the default 768 gives headroom; confirm no tail is clipped by zooming the alpha edge at the tile borders (expect 0 non-zero alpha pixels on the outermost 2 px).
- Joined glyphs: take a visual capture and compare the word to the HarfBuzz negative control rendering of the same string (`hb-view`, features off): the live render must **not** look like isolated letters.
- Mixed line `ہیلو hello اردو` -> `visual_idx` right-to-left: `ہیلو`, `hello`, `اردو` (RTL base), FriBidi agrees.
- Cook cost: parse+measure+layout under 40 ms for 24 words on `Rebuild`; per-frame cost (anim + 24 Transforms + 1 Composite at 1920x1080 RGBA8) under 1.5 ms GPU on M1 Max (target; measure with `td_perf`); zero per-frame Python allocation beyond the Script CHOP (one 7 x 24 table). Memory: 24 tiles x 1536x768 x RGBA8 = 108 MB (use 8-bit tiles; 16-bit float would be 216 MB).
- A rebuild (text change) must not drop frames at 60 fps: do measure+layout in one callback and swap the table atomically (builder verifies by watching `Cooktilesms`).

### 5.6 Mac caveats

- TD is x86_64 under Rosetta; the Text TOP and numpy readback behave normally. Keep numpy readback off the per-frame path (GPU sync stall).
- Vulkan/MoltenVK: one Composite TOP + compute-mode GLSL only; avoid multi-pass GLSL (T-46); Optical Flow TOP is not used.
- `Measure=hbshape` calls an **arm64 Homebrew binary from the x86_64 TD process**; this works for spawning (arm64 child of a Rosetta parent) but is Mac-only and optional; no pip, no install.
- Text TOP `strokewidth` is not trusted on macOS in 31550 (fix in 32820): not used.
- Nastaliq UI variant: the system face "Noto Nastaliq Urdu UI" exists too; expose via `Fontrtl` but default to the non-UI face.
- Unicode safety: never pass Urdu through TScript (`Unicode.htm`); Table/Text DAT cells and Python only.
- Persistence (user rule 26 Oct: save projects always): the COMP must be a saved `.tox` (`td_tox_save`) at every verified step and live inside the autosaved project (T-71); **agents never save the project, the main session does after each verified build** (T-71). Node setups, learnings (new T-nn) and the `.tox` path go into `LEARNINGS.md` at once.

### 5.7 Probes the builder runs first (2 minutes each, scratch COMP, TD busy-lane rules apply)

- P1 Text TOP: joined forms for each of the four oracle words with `Fontrtl` = Noto Nastaliq Urdu (regression of prior A section 5).
- P2 Text TOP: mixed line `ہیلو hello اردو 2026` once with `readingdirection=righttoleft` and once lefttoright; record the visual order.
- P3 Text COMP (and Geo Text COMP): Urdu word with `Reading Direction` RTL; joined or isolated? (decides whether Slug-based COMP text is usable.)
- P4 Text SOP: Urdu word with `Language` = `ur`; joined or isolated? (decides 3D text.)
- P5 Text TOP fallback: put the Latin word `hello` in Noto Nastaliq Urdu (does it have Latin glyphs, or does the fallback misrender?).
Results go into `LEARNINGS.md` as a T-nn and into this file's section 5.

---

## 6. Build spec B (optional, second backend): `urdu_web_type`

**Path:** `/project1/lab/BJ_urdu_web_type`. Same custom-parameter names as A for Text/Style/Anim so the two are interchangeable; output = Out TOP. Use only if probe P6 passes.

- **What:** a Web Render TOP (CEF 132) loads a local HTML page (`file://`, generated into the COMP's folder, text from `Text` via a messaging bridge or by rewriting the file and `Reload`) containing one `<span lang="ur" dir="rtl">` per word, `font-family` = the OFL fonts from `hyperframes/studio/assets/fonts/` (copy path read at build time, never written back), CSS `word-spacing` for `Wordgap`, `font-variation-settings: "wght" N` for weight (not reachable in the Text TOP), `line-height: 2.0-2.5` for Nastaliq, GSAP for word-level stagger exactly like the sibling repo. Real HarfBuzz, so the glyph-exact result matches HyperFrames output; `transparent` background.
- **P6 (must pass first):** (a) Web Render TOP with `transparent` produces real alpha on this Mac (corner pixels alpha 0, text pixels alpha 1); (b) frame rate: `maxrenderrate` 60 honoured at 1920x1080 and `dpiscale` 1.0; (c) joined Nastaliq in the render; (d) CPU of the CEF helper under 25 % of one core at 30 fps; (e) startup time under 3 s; (f) page can be driven from TD (Python -> `executeJavaScript` style method, UNVERIFIED API name; check the TOP's methods with `td_info`).
- **Trade-offs:** better typography and weight axis, smoother CSS/GSAP animation; but a CEF process, 30 fps default cap, a one- to two-frame latency, and non-deterministic timing (TD time and page time differ, so BPM sync needs `Progress` pushed per frame). A is the default; B is for variable-weight pulses and finished HTML motion.
- **Offline-testable:** the generated HTML is checked in headless Chrome the same way HyperFrames is, comparing rendered word order against FriBidi.

---

## 7. MCP tool ideas (not built; for later)

- `td_urdu_type` (build A with the pars above; params: text, direction, fonts, size, mode, timing, outputs; builds in `/project1/lab`, arranges, returns the COMP path and verification numbers).
- `td_text_probe` (runs P1-P5 in a scratch COMP and returns a one-line table: joined/isolated, visual order, fallback behaviour), so future builds of 3D/POP text know which engines shape.
- `text_shape_check` (pure host-side tool, no TD: given a string and a font file, runs `hb-shape` and `fribidi` if present and returns glyph counts, advances, levels and a "looks joined" flag): usable for proofing without opening TD. Mac helper only.
- `td_cue_text` (a cue list DAT, UTF-8 BOM-safe, one line per cue, `Line` stepping from MIDI/OSC/BPM).

---

## 8. Gated items for `docs/FUTURE.md`

| Item | Build gate | Status | Source | Gate / test |
|---|---|---|---|---|
| Text POP for Urdu/Arabic (glyph attributes `GlyphId`/`CpIndex`, extrude, per-glyph attributes) | 2025.32460+ (fixes in 2025.32820) | idea only; not testable on 31550 (final) | BJ section 1.3, [Text POP](https://docs.derivative.ca/Text_POP) | Needs a newer TD; test joined forms and `GlyphId` count on `اردو زبان` (oracle: 13 glyphs, 9 code points) |
| Per-glyph / glyph-atlas pipeline (HarfBuzz shape -> msdf-atlas-gen by glyph index -> TD instancing table) | any build (needs pip/CMake outside TD) | idea only, needs the user's go-ahead (install) | BJ sections 1.8, 2 | Bake atlas offline, check shaped output against `hb-shape` ids |
| `uharfbuzz` inside TD for live glyph ids and positions | any build (needs pip; x86_64 macOS wheel UNVERIFIED) | idea only | BJ section 2 row 9 | install gate, then compare to `hb-shape` JSON on the four oracle words |
| Vendored `arabic_reshaper` / `python-bidi` | any build | idea only (LGPL for python-bidi) | BJ section 1.6 | only if a font lacks GSUB shaping |
| Variable-font `wght` axis control for the Text TOP | unknown build | idea only | BJ section 3 | check release notes of newer builds; use spec B meanwhile |
| Text COMP/Geo Text COMP Arabic shaping | probe P3 | UNVERIFIED | BJ P3 | scratch COMP test |
| Text TOP `strokewidth` on macOS | 2025.32820 | known not trusted on 31550 | prior Q | re-test after any upgrade |
| `urdu_web_type` | probe P6 | idea only | BJ section 6 | P6 |

---

## 9. Open questions

1. Do you want word-level only (recommended, v1), or per-glyph animation later with the glyph-atlas route (needs an install and the HyperFrames "names stay whole" rule relaxed)?
2. Is Noto Nastaliq Urdu (OFL, system-installed) the default, or should the COMP default to Geeza Pro/Gulzar for lighter display? Real names should be proofed by a native reader before a show (prior U-06).
3. Should spec B be built at all, or is Web Render only to be used via finished HyperFrames clips?

Sources used (all read as pages; nothing downloaded): TD offline docs inside the app bundle (`Unicode.htm`, `Font_SOP.htm`, `Slug_Library.htm`, `Text_COMP.htm`, `Text_SOP.htm`, `Text_TOP.htm`, `Geo_Text_COMP.htm`, `Text_Formatting_Codes.htm`), [Text POP](https://docs.derivative.ca/Text_POP), [2025.32460 release](https://derivative.ca/release/202532460/74120), [Slug repo](https://github.com/EricLengyel/Slug), [Slug patent news](https://hackaday.com/blog/page/179/?cat=GNB), [python-arabic-reshaper](https://github.com/mpcabd/python-arabic-reshaper), [python-bidi](https://github.com/MeirKriheli/python-bidi), [uharfbuzz](https://github.com/harfbuzz/uharfbuzz), [msdf-atlas-gen](https://github.com/Chlumsky/msdf-atlas-gen), [Notch Reshape Arabic Text](https://manual.notch.one/2026.1/en/docs/reference/nodes/text-fx/reshape-arabic-text/), [SuttaCentral tall-script line height](https://discourse.suttacentral.net/t/testing-for-line-height-with-tall-scripts/6196), hyperframes notes (read-only), and local probes with `hb-shape` 14.6.0 and `fribidi` 1.0.16.
