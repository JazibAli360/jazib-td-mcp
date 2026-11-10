# BE: twozero rudiment "ZERROR" (26 Oct 2026) and a clean-room build spec

Scope: the user asked us to build our own component with similar functionality to
https://twozero.ai/rudiments/twozero/zerror (one of six rudiment links; the other five are separate jobs). Clean-room:
nothing of theirs is copied; this file records what it does and a spec of our own. Nothing was loaded into TD, nothing run
or installed, no sign-in.

**Key finding: ZERROR is not an error reporter.** It is a drag-and-drop parameter **control surface** (knobs, morphing
presets, MIDI, timeline, layouts) by 404.zero, now distributed through twozero rudiments. The name misleads. Our
error tooling is a different thing (`td_errors`); this spec builds the control surface, named `zctl` here.

## 1. Sources and what could not be reached

| Source | Got |
|---|---|
| twozero.ai/rudiments, /rudiments/twozero/zerror (curl + WebFetch) | JS single page app; only title and meta: "Drag-and-drop parameter controller for TouchDesigner - knobs, morphing presets, MIDI, XY & DMX surfaces, layouts. Open network, agent-ready." No body text without JS. |
| `.../zerror/zerror.tox` | Returns the same HTML shell (SPA fallback, 200 text/html). **No .tox downloadable without login; nothing was downloaded, so `research_src/rudiments_zerror/` was not created.** No bot protection bypassed. |
| https://www.404zero.com/zerror | Full feature list (below). |
| derivative.ca community posts 60966 (Feb 2019, v1.6) and 69165 (V5) | History and V5 features. |
| forum.derivative.ca/t/zerror-ui-link/239548 | 2022: site was down, 404.zero said unsupported; later revived as a rudiment. |

Licence/price (research only): was $50 Pro in 2019; per-machine key, 1 year of updates, non-transferable; free tier = 5
parameter knobs + 5 preset knobs; 14-day trial needs internet; "open network" now. Mac + Windows, "latest official TD", Apple
silicon since V5. Exact current price and rudiment licence: UNVERIFIED (page text not reachable).

## 2. What the original does

Features (404zero.com page, V5 post):
- **Parameter bindings:** drag any OP parameter into the viewer to make a knob; automatic binding; expression linking.
- **Presets as knobs:** a preset stores and recalls any number of parameters; created by dragging a "+" widget.
- **Preset / state morphing:** smooth transition between presets; random variations drift toward saved looks.
- **Randomizers:** randomize connections, parameters, presets; build a patch from random nodes.
- **Widgets:** knobs, menu/momentary/toggle buttons, layout switcher, XY and DMX surfaces (twozero meta), timeline
  (zTimeline, "DAW-like", not public in V5).
- **Layout editor:** multi-knob arrange and align, colour tags, scene ordering by priority or time.
- **MIDI:** fast mapping, two-way (feedback to the device), Midi Fighter Twister / Spectra native, knobs follow colour tags.
  2019 version also had multi-touch and OSC.
- **UI/keys:** right-click COMP > view; LMB tweak, RMB move; right-click item = properties; W new widget, P settings and
  tools, L layout mode. Online single-click update. Pure native TD, no dependencies.
- **Samples:** AVsynthy.toe, audioReactiveTimeline.toe, zerrorBenchmark.toe (88 knobs + timeline = their perf target).
- Not known: exact parameter names, internal storage format, exact DMX/XY behaviour (UNVERIFIED).

## 3. Clean-room build spec: `zctl` COMP

House rules applied (USING_TD "Readable networks", "Self-contained effect COMPs"): own custom pages, Out carries only the
output, own `controls` panel + `controls_window`, `td_layout stages`, then `td_window_capture`.

### 3.1 Custom parameters (name = one capital letter then lowercase/digits)
- **Zctl** page: `Active` (toggle), `Mode` (menu: Run, Layout, Learn), `Morphtime` (float s, 0-30, default 1.0),
  `Morphcurve` (menu: Linear, Ease, Smooth), `Activepreset` (int), `Store` (pulse), `Recall` (pulse), `Delete` (pulse),
  `Randamount` (float 0-1), `Randomize` (pulse), `Midiin` (menu from Midi In device list), `Midiout` (toggle, feedback),
  `Learn` (toggle), `Oscport` (int, default 9100), `Oscon` (toggle), `Opencontrols` (pulse), `Clearlinks` (pulse).
- **State** page (read-only): `Nbinds`, `Npresets`, `Morphing` (toggle), `Lasterror` (str).
- `controls` shows page `Zctl` only (`Pagescope`, `Pagetabs` off, `align verttb`).

### 3.2 Ops
Inputs: none required (optional `in_midi` In CHOP for external MIDI-like channels). Output: `out_values` Out CHOP (one
channel per binding, value 0-1 normalised; carries only that). Bindings write straight to target parameters.

Stages (L to R):
1. **Store** - `binds` Table DAT (id, label, target path, par name, min, max, colour, midi cc, osc addr, mode), `presets`
   Table DAT (preset id, name, json of {bind id: value}), a Text DAT `zctl_ext` (extension class `ZCtl`) with methods
   `Bind(path,par)`, `Unbind`, `Store()`, `Recall(i)`, `Randomize()`, `Normalize(v,min,max)`.
2. **Inputs** - `midiin1` MIDI In CHOP (cc channels), `oscin1` OSC In CHOP, `keyboardin1`; a `learn` CHOP Execute DAT
   catches the first moving channel while `Learn` is on and writes its CC/address into `binds`.
3. **Morph engine** - `target` Constant CHOP (one chan per bind, set by Recall) -> `lag1` Lag CHOP (Lag1/Lag2 = Morphtime,
   driven by expression) -> `shape` Math/Lookup CHOP for the curve -> `morph_out` Null. While moving, `Morphing` is on.
   Manual knob input overrides: a knob touched sets target = value and bypasses lag for that chan (select + switch).
4. **Apply** - a CHOP Execute DAT on `morph_out` (onValueChange) calls `ext.Apply()`, which sets each bound parameter in
   Python (rounded to par range; menus by index). Batch in one callback; only write changed values (cuts cost at 88+ binds).
5. **Feedback** - `midiout1` MIDI Out CHOP mirrors values when `Midiout` on (two-way). Colour tags map to a velocity.
6. **UI** - `knobs` Container COMP with a Replicator COMP cloning one `knob` base (Slider COMP + label Text COMP +
   colour bar) from `binds`; `presetbar` Replicator of Button COMPs from `presets`; "+" Button = Store. Layout mode: panel
   drag via Panel Execute DAT writing x/y back to `binds`. Drag-and-drop of a parameter into the viewer: Container
   `Drop` callbacks (`onDropGetResults`, TD drag/drop callbacks) -> `Bind(...)`. `controls` panel (autoUI) +
   `controls_window` Window COMP opened by `Opencontrols`.
7. **Out** - `out_values` Out CHOP only.

Persistence: tables are DATs inside the COMP so a `td_tox_save` carries bindings and presets. Presets as JSON strings.

### 3.3 Python logic that is unit-testable offline (plain module `zctl_logic.py`, no `td` import)
`normalize/denormalize`, `morph(a, b, t, curve)`, `blend_presets`, `randomize(values, amount, rng, bounds)`,
`quantize_menu`, `learn_pick(prev, cur, threshold)`, `preset_json_roundtrip`, `grid_align(items, mode)` (arrange/align),
`midi_cc_to_unit` and back. Test with pytest in the jazib-td-mcp venv (no TD, per CLAUDE.md "neither suite touches TD").

### 3.4 Live verification (td_inspect numbers, then capture)
- Create a Noise TOP + Constant CHOP target; bind 3 params; `td_inspect out_values`: 3 channels, min/max in 0-1.
- Store preset A, change values, Store B, set `Morphtime`=2; Recall A: sample `target` vs `morph_out` at t=0, 1, 2.2 s:
  expect ~0 %, ~50 %, 100 % of the way (Linear). Bound parameter values read back via `td_get_pars` match.
- Perf: 88 binds with `td_perf`: cook of `zctl` < 1 ms idle (nothing changing) is the target; compare to their 88-knob bench.
- Randomize with `Randamount` 0 = unchanged, 1 = within par min/max. Save + reload the tox: bindings and presets return.
- MIDI: no device needed; feed `in_midi`/a Constant CHOP faking `cc1`; real hardware only on the user's go-ahead.
- Layout: `td_layout stages` + `td_window_capture`; knob panel scrolls? (one page, no scroll needed).

### 3.5 Mac / 31550 caveats and fallbacks
- Pure CHOP/DAT/COMP, no GPU shader, so none of the T-46 / T-18 issues apply.
- Midi In needs CoreMIDI device; none present = channels stay 0, UI still works. Use `Learn` with the fake source.
- TD under Rosetta (x86_64): no native code; all Python is stdlib + `td`.
- Check parameter drag-drop callbacks exist on 31550 (probe `onDropGetResults` via `td_exec`); fallback: a "Bind" text field
  taking `/path.par` or a selection-based "Bind selected pars" pulse.
- No `timelineCOMP` in our op index: timeline = our own Timer CHOP / Keyframe-style table (v2, see below).
- Index check: midiin/out, oscin/out, dmxout, lag, lookup, slider, button, container, table/chopexecute/panelexecute DATs,
  keyboardin, merge, null, constant all present; `paneCOMP` and `timelineCOMP` are not in the 31550 index.

### 3.6 Gated on newer builds / for docs/FUTURE.md
Per-parameter binding via the new parameter-reference/Bindings feature if a newer build has a native one (unverified);
native Timeline/Pane components; any API additions to drag-and-drop. Keep our fallbacks active on 31550 and gate on
`app.build`.

### 3.7 Scope tiers
- **v1:** bind (drag or selected), knobs, presets store/recall, morph, randomize, MIDI in + learn, out CHOP, panel + window.
- **v2:** MIDI out feedback, OSC in/out, layout editor, colour tags, menu/toggle/momentary buttons.
- **v3:** XY pad, DMX out surface, timeline (own), layout switcher.

### 3.8 Estimated build time
v1 ~2.5 h (one agent, with offline tests ~30 min of that); v2 +2 h; v3 +3 h. With parallel lanes (logic+tests / UI build
/ MIDI+OSC) v1 ~1.5 h wall-clock.

## 4. Open questions for the user (see also section 6 for the visual spec)
1. Confirm "ZERROR = control surface" is what you meant (the name suggests errors, the product is a controller).
2. v1 only, or all tiers? 3. Hardware MIDI available to test (Midi Fighter?), or fake source only?


## 5. v5 release page findings (26 Oct 2026, second pass)

### 5.1 Sources and what was got
| Source | Got |
|---|---|
| derivative.ca/community-post/404zero-release-zerror-v5-and-it-mighty/69165 (20 Mar 2024, Q&A with Kristina Karpysheva + Alexander Letcius) | Full text (curl). Design intent only; its 11 images are photos/screenshots of performances (not downloaded; the 404zero.com screenshots were enough). Links: 404zero.com/zerror.html, YouTube 76eOp_YEZKQ. |
| https://www.404zero.com/zerror (page) | Full text, quick start, updates list, links to screenshots, samples, docs. Saved in `research_src/zerror_v5/pages/`. |
| https://www.404zero.com/zerrordocs.html | **Full documentation (21 chapters), the best source.** Text saved as `pages/docs.txt`. |
| YouTube 76eOp_YEZKQ (52 s, 1280x720 downloaded, auto-subs = music only, description 3 lines) | 17 frames at 1 per 3 s in `frames/t001..t017.jpg` (t(n) = (n-1)*3 s). |
| Screenshots `zerror_img/s1..s6.jpg`, `zerror.gif` (1920x1080, 2.6 MB) | Downloaded to `img/`; s1 = full 4x11 knob panel (3776 px wide, best detail). |
| `zerror/zerror.tox` (334 758 bytes) | **Free, no login, direct link on the 404zero page**, saved in `img/zerror.tox`. toeexpand ran: output is `zerror.enc` only (container is locked/encrypted, "privately locked" per docs, build 2025.32820). **Not decryptable and we did not try: widget internals, preset storage format and drag-drop callback code are NOT readable.** Everything below comes from docs + frames. Correction to section 1: a .tox download does exist on 404zero.com (the twozero.ai page did not offer one). |

Licence notes (research only): free = 5 parameter knobs + 5 preset knobs; Pro with 14-day trial; **no longer sold, now distributed through twozero rudiments**. Mac: M1+ (Rosetta TD on x86 is not the stated target). **Current v5.471 (27 Jul 2026) requires TD build 2025.32820 minimum** (min was 2023.12480 until 5.418, Apr 2026); our 31550 is older than that, so the real component would not be supported on our TD even if licensed; the clean-room build also guarantees no such dependency.

### 5.2 Facts that matter (from docs, v5.47x)
- **Creation:** drop any OP parameter into the viewer = a knob configured from the par (range, type, menu). Drop a par group (tx,ty,tz) with Ctrl/Cmd held to split into separate knobs; multi-select drops: Ctrl splits per OP, Alt transposes direction. Default link = **bind**; option = **expression** (with a per-knob `filter` smoothing that only works on expression links; global `split chans` limits cooks). Max 512 parameter knobs (5.424). Zerror also outputs a CHOP of all channels (`chan` name per knob).
- **Mouse map (Run mode):** LMB drag = tweak; MMB click = toggle min/max or restore default (per-knob `MMB action`); RMB click = properties menu; RMB drag on knob = move it; RMB drag on empty background = marquee select + enter Layout mode; double LMB click = toggle "recallable" (ring colour shows it); typed value: click knob (or marquee-select several), type number, Enter or click away. Multi-select tweak is supported (`multi tweak`).
- **Keys:** P settings (or knob settings), W widgets menu, L/H layout mode (H = also fit view to all), G utils/beta, M MIDI mapping, Delete removes selected.
- **Presets store raw values** (not normalised to knob range), every parameter knob is recallable by default; recall can be filtered by colour tag (`recall by color`) and by recallable flag. `rand ranges` makes each par morph at slightly different times. `save preset` overwrites; in Layout mode `store to presets` writes selected pars into selected presets.
- **4 preset knob types:** Morph (aka float), Toggle (A/B: A = arbitrary captured state, B = stored), Momentary (toggle without latch), Classic (instant recall). **Morph preset maths/behaviour:** on LMB press capture the live state of all knobs; turning the preset knob clockwise from 0 to 1 interpolates captured -> stored; releasing and pressing again recaptures from the current mixed state; any other knob change resets the preset indicator to 0 so the next press captures the new state. MMB makes a morph preset act as a toggle.
- **Pills (widgets, W menu):** Random pill (morph: capture -> random state, counter-clockwise returns to captured, fully back = new random target next time; momentary = instant), `max rand` = fraction of each knob's range, filters rand-by-colour / rand-by-recall. Offset (shift) pill: adds a delta to all matching pars. Random-preset pill (picks a random preset, morph or instant, `max rand` caps recall). **Play pill** (experimental): orbiting dot, each pass of 12 o'clock selects the next preset; settings period (s), rand period, fade in (fraction of period, grey outline arc), rand fade in, fade curve (linear / ease in / ease out / ease in-out), rand order 0..1 (sequential..random), max value, rand value.
- **XY controller:** surface with free-positioned preset knobs inside; handle Y picks the row (rows inferred from vertical positions, no dead zones, `band tol`), X morphs between the two nearest presets of that row (clamped at ends); on/off circle top right; custom pars `Xyx1 / Xyy1 / Xyon1` (numbered per instance) so a timeline can drive it.
- **Layouts widget:** 3 layouts (red/green/blue circle, click cycles, `Gotolayout` par); each stores every knob's position and size ("banks"); MIDI surfaces and the Layouts widget itself are not stored in layouts. `copy to layout` per knob.
- **Layout mode (grid background):** scroll zoom, LMB drag background pans, LMB/RMB drag knob moves, LMB click knob selects, click background exits, H fit. Marquee then arrangement frame: corner drag = proportional scale; Shift = + equalise sizes; Alt = fit to rectangle; Alt+Shift = fit + sort by type and label; Ctrl = align to arbitrary grid; Ctrl+Shift = align + equalise sizes.
- **Per-knob options:** knob type, recall, sensitivity (also scales MIDI encoder response), menu items (preselect + reorder, shift/ctrl click rules), min/max, filter, clamp min/clamp max, set default value, MMB action, label, size, colour, show value, menu display (names or labels), chan, show OP (navigate), save to layout, set as default (for new knobs), delete. **Out-of-range indicator: the label turns red** (not an error).
- **MIDI:** conventional mapping (M key; encoder CCs auto-detected and marked with a dotted circle; direct vs pickup per device; manages TD's MIDI mapper dialog). **MIDI surfaces**: a virtual copy of the controller (rows x cols, configure dialog assigns each slot by wiggling the control), RMB-drag knobs into a slot, knobs "stick" to the slot and show a small dot when mapped; virtual banks by cloning the surface; `MIDI out` (feedback) and `cc pickup` combos per controller type; `create presets` / `create pars` on an empty slot with CC 127 (create pars needs the cursor over a TD parameter). **Midi Fighter Twister/Spectra:** auto-configure, 2-way colour + value feedback, own virtual banking, left side buttons act on the last-touched knob (1 recall/override with confirm, 2 colour, 3 delete with confirm), right side buttons next bank / cycle layouts / previous bank. The 2024 interview: the aim is to look at the monitor less during a live set.
- **DMX surface** (July 2026): Art-Net only input, rows/cols/start address (1-512, left to right then down), universe/subnet/net, 8-bit values, live dots show incoming value brightness, `pickup`, global `Dmxactive` and `Dmxlocaladdress` pars. Input only.
- **Global settings (P):** bg colour, text colour, value colour, knob colour, active colour (inner circle on mouse down), colour palette for tags, **day/night themes (two fully custom colour sets + quick switch)**, bg TOP (+ opacity, `Bgtop` par), bind type, global sensitivity, multi tweak, split chans, OP colours (colours the linked OP when tagging), menu size (compact sizes since 5.469), check updates.
- **UI integration:** works through the COMP's panel; "panel size can be easily changed and adapted to existing UI". Requires playbar playing, global cooking on, COMP cooking on. External-facing pars on the COMP: Checkupdates, Dmxinterface, Gotolayout, Externaldata/Refreshdata, Xy* pars, Bgtop.
- **Implementation hints stated by the vendor:** "Built with native TD, no side dependencies"; changelog mentions "glsl cache optimize" and "TD 3D texture bug" = the knob graphics are GLSL-rendered into a TOP, with panel interaction layered on the COMP panel; performance claim: 88 knobs + timeline benchmark.
- Timeline-light (free companion, not downloaded): rows of preset blocks p1..p14 on a time ruler with transport (frame t=2, `img/m2.jpg`): pause/stop/rewind/loop buttons, time readouts "0.07 / 00:00" and a home button; presets are coloured blocks (grey and orange), resizable, overlapping allowed.

## 6. Visual + interaction spec for our kit (clean-room; name `zk_*`, built by us)

All values below are **measured by eye/pixel-sample from the 404zero screenshots and video frames (approximate; hex values are from JPEG samples) or taken from the docs**. They are a style target, not copied assets. Evidence: `img/c1.png` (crop of s1 panel, dark), `img/m2.jpg`, `img/m4.jpg`, `img/g01.jpg` (light theme, video t=0 s of the gif), `frames/t006.jpg` (video 15 s: knobs tweaking beside an Arena-style param dialog), `frames/t015.jpg`, `frames/t003.jpg` (video 6 s and 42 s, hardware shot: the panel on a small 9:16 screen).

### 6.1 Overall look
- Flat, matte, minimal ("Tokyo minimalism, on-grid"): no gradients, no bevels, no shadows. Round shapes on a rectangular dark panel. One accent colour per knob; accent is a saturated red-orange by default (arc about #e8421c; sampled dim part #a83925). Colour is a **tag** used for recall / random / MIDI filtering and mirrored to MIDI LEDs.
- **Dark theme (default):** panel bg ~#18191d (video frames show #101010..#1c1c1c), knob body ~#1a1a1a to #212121, unused arc track = dark grey slightly lighter than the body (~#2b2b2b), label/value text off-white ~#d0d0d0 (labels) and ~#bdbdbd (value). **Light theme (night/day switch):** bg ~#c4c4c4 flat grey, knob body ~#31302c, accent orange ~#d8561a (sampled #c87c42 under JPEG), group frame ~#d0cccd, white ring ~#d5d5d3, text ~#222.
- Font: a clean grotesque sans (looks like a rounded humanist sans in the video, 404zero's site uses IBM Plex Mono for text and a monospaced readout look in the dark screenshots); lower-case labels, no bold. We will use **IBM Plex Mono Regular (OFL) or a TD-default sans**; labels 9-11 px at the 56 px knob size, values 9-10 px. **[CHANGED, s5FV29yoZq8 5 s / 40 s, 0tP7jkdddgg 114 s: all text, incl. values and menus, is a proportional humanist sans (Open Sans / Noto Sans look), not mono. Use TD default sans or Open Sans; drop IBM Plex Mono.]**
- Layout rhythm: a knob cell is roughly **knob diameter D plus ~0.3 D of label below plus gaps**: in `c1.png` (4x11 panel) knob diameter about 62 px (crop scale) in a cell about 80 px wide by 80 px tall; label text height about 0.16 D; gaps between cells about 0.25 D; panel inner padding about 0.4 D; the "+" preset button (a dark circle 0.85 D with a white plus) sits top-right, 0.4 D from the corner. Densities seen: 4x11 (44 knobs) in 620x970; 11x2 + 4x4 + 4x4 bank frames on a 1080p window (`g01.jpg`); about 46 knobs at once in the landscape layout (`m4.jpg`).
- Group frames (MIDI surfaces) **[CORRECTED, Kow8WZaYE4k 62 s: the frame/title/dot are BLUE (#5b8fd0-ish), not the accent colour; details in 7.3]**: a 1.5 px outline rectangle in the accent colour, rounded ~6 px, a small caps title ("TWISTER", "SPECTRA") top-left in the accent colour, an accent dot top-right (filled = active bank, grey = inactive), empty slots drawn as plain dark knobs with the slot label p1, p2, ... Active bank colours, inactive banks go monochrome.

### 6.2 Knob (parameter float/int)
- Shape: circular body (D = 48..64 px at 1080 scale; user-resizable, 4 sizes in practice: 0.5x, 1x, 1.5x, 2x of the default); a thin **outer arc track** about 0.08 D thick, ~0.08 D outside the body (a visible gap between body and arc, see `c1.png`). Arc sweeps **about 270 degrees: starts about 7 o'clock (lower left, -135 deg from top) and ends about 5 o'clock (+135 deg)**, like a hardware pot; the fill is accent colour from the start to the current value; unfilled track dark grey. **The fill arc has square/butt caps.** **[CONFIRMED v: s5FV menu1 5 s, 0tP7 q3 130 s; plus: each param knob has a dimmer coloured outline ring on the body (~#5f271e orange), gap, then the bright arc. The tick is a small diamond that exists on PRESET knobs only and takes the preset colour (8YKniBSSGAo 20 s). Param knobs show a tiny stub at 7 o'clock near zero, no diamond.]** A small accent **tick/marker** (a short diagonal bar) sits at the 7 o'clock start position on empty knobs (visible on every p4..p7 knob in `c1.png`) = the "zero" mark.
- Text inside the body: **the current value** (numeric, 3-4 significant digits like 0.322, 1.098, 19.70, 4030, or the menu item name like "perlin4d", "simplex3d", "repeat", "horizontal"); ~0.2 D tall, centred, off-white. Below the knob: the **label**, truncated with the end cut at about 9 characters ("noise2-Peri", "noise3-Harm"); label is "<opname>-<parname first letters>" when auto-created. **Label goes red when the value is outside the knob range.**
- Recall ring: a thin ring between body and arc indicates the "recallable" flag (a full ring = recallable, none = not). We will draw a thin 1 px accent ring inside the arc track when recallable, absent when not. **[REVISED, 0tP7 q3, s5FV 40 s: the ring is the knob's colour tag and is on every parameter knob (also on non-recall ones as far as seen); what the recall flag changes visually is UNVERIFIED. Size is a continuous float (1.502, 2.625, 1.781 seen), not 4 steps (7.0 #5).]**
- States: idle; hover = body lightens ~8% (no scale); active (mouse down) = body fills with the "active colour" (a lighter or accent circle inside, per the global `active color` setting) **[v5 CONFIRMED: body fills solid accent while pressed, 0tP7 20 s; v4 instead shows a small dark-blue ring at the pointer, s5FV 5 s]**; MIDI-mapped = small dot at top right of the knob (about 0.12 D); selected (layout mode) = 1 px accent outline around the cell.
- Mapped-to-hardware: arcs light on the MIDI device in the same colour.

### 6.3 Fader
Not a primary widget in v5: everything is a rotary (any knob can become button/toggle; values are arcs). If we need a fader (TD sliders are useful for narrow strips), make it as a **vertical flat bar** with the same dark body, accent fill, value text over the fill, label below: same tokens as the knob. Low priority (v2).

### 6.4 Button types (any parameter knob can be switched type by RMB > knob type)
- **Toggle:** **[0tP7 q3: OFF = body filled with a dim accent tint (#432823) + bright ring, text 0.0000, no outer arc; menu knob shows a short 7 o'clock arc + item name]** the same round knob body; ON = body fully filled with the accent colour and the text shows "1.0000" in white; OFF = dark body with accent ring and "0.0000" (see noise3-Mono, noise3-Aspe in `c1.png`).
- **Momentary:** same look, lit only while the mouse/MIDI key is down; hover/press = active colour.
- **Pulse / large-dot variant:** a **dim filled dot** (about 0.45 D, darker accent ~#a83925) in the middle of the dark body for toggle-type presets or MIDI notes; fully bright when on (p28..p35 in `c1.png`, `frames/t003.jpg`: round red dots).
- **Menu knob:** the arc shows the item index; the value text shows the item name. Items preselectable/reorderable in the properties menu.
- Layout-switcher widget **[v4 = vertical pill with green dot bottom right, FhQEl4UkleU; v5 = circle, 0tP7 170 s]**: a 24 px circle in red/green/blue; a global on/off like switch is a vertical pill (see the green dot toggle at lower right, `frames/t015.jpg`).

### 6.5 XY pad
A free-form rectangle with 1 px outline (accent or white at 60%), label top-left (small caps), on/off circle top-right; inside: preset knobs placed freely (the pad is transparent) and a **round handle** (about 1 D) that you drag; the active row's presets show lit; expose `Xyx1 / Xyy1 / Xyon1` as normal custom pars. Behaviour per docs section 5.2.

### 6.6 Colour swatch / colour tag
No dedicated swatch widget: colour is a property (`color`) chosen from a palette (global `color palette`) in the properties menu; the swatch is the accent colour itself shown on the knob. Our kit: a row of 8 small circles (0.4 D) in the properties menu, plus the colour name; accent also feeds MIDI LEDs.

### 6.7 Presets bar and pills
- The "+" widget (dark circle with a plus) is the **create preset** handle: **drag it out into the workspace to spawn a preset knob** at the drop position (not a click); the new preset knob captures all recallable parameters.
- **[REFINED 7.0 #3-4: classic preset = solid dot ~0.3 D + diamond at 7 o'clock in the preset colour; morph preset = empty body + bright 270 degree arc + diamond head; empty slot = dim track; hovered morph = red arc with arrow heads; `rand` = coarse pixel-noise disc, `randPres` = fine noise disc, with a white arc outside while dragged (0tP7 q3, FhQEl)]** A preset knob looks like a knob whose face shows a **small thumbnail/noise-like texture** for pills (e.g. "rand", "randPres" circles filled with a pixel-grid texture in a white arc ring, `g01.jpg` centre, about 2 D) and a plain dark knob with the accent dot for stored presets; label = name (p1, p2, ... default).
- Morph: preset arc ring shows the 0..1 morph position; Classic = instant; Toggle/Momentary as in 5.2.
- Random pill = morph or momentary, drag clockwise/counter-clockwise; max rand, rand by colour/recall; Offset pill; Random-preset pill; Play pill (orbiting dot with a grey fade-in arc, period setting).
- Our "store / recall / morph / randomise" UI: `+` drag = store; click classic = recall; hold + turn = morph; pills for randomise; per-preset menu `save preset` = overwrite; morph time from the global `Morphtime` custom par is only the *timed* morph of Play pill / our Recall pulse (Zerror itself morphs by the user's hand).

### 6.8 Panel layout
- Free positioning, no fixed grid in Run mode; **Layout mode** shows a background grid, snap on "align to arbitrary grid" (Ctrl+corner drag). To avoid long scrolling: **3 layouts (R/G/B) as banks** + MIDI-surface virtual banks + zoom/pan in layout mode (scroll zoom, H fits all). There is no scroll bar and no collapsible sections: density is solved by bank switching and small sizes (`Menu size` compact option).
- Our kit: keep the same idea (banks + free grid) but add what the vendor lacks: auto-flow arrange with a **12-column grid** and group frames with a title (collapsible via click on the title), default panel 1080x1920 portrait window with a 4-column, up to 12-row knob grid (D = 56 px) per page; and tabs by layout colour.

### 6.9 Interaction table (ours; vendor's where known)
| Gesture | Action |
|---|---|
| LMB drag on knob | tweak; **sensitivity per knob** and global (vendor: both; exact px per full sweep not documented). Our default: 200 px of vertical drag = full range, Shift = 1/10 fine adjust, Ctrl+Shift = 1/50, Alt = hold coarse x4 (vendor does not document a shift modifier; this is our addition) |
| scroll wheel | not documented for Run mode; ours: +/- 1% of range per notch (Shift 0.1%) |
| double LMB click | vendor: toggles "recallable" (ring). **Ours: same, plus MMB click = reset to default (vendor behaviour, per `MMB action`)** so double-click is not ambiguous |
| click knob then type | type exact value, Enter / click away commits |
| MMB click | toggle min/max or restore default (option) |
| RMB click | properties menu (knob type, recall, sensitivity, min/max, filter, clamp, default, MMB action, label, size, colour, show value, menu display, chan, show OP, save to layout, set as default, delete) |
| RMB drag on knob | move; RMB drag on background | marquee + Layout mode |
| drag param from TD param dialog | create a bound knob (Ctrl splits groups) |
| W / P / L / H / G / M | widgets menu / settings / layout mode / fit all / utils / MIDI (W and P confirmed: zGld7ypMiFA 0:02, vAYEB10QEqU 0:05; P applies to all marquee-selected knobs) |
| Delete | remove selected knobs (unlinks the par) |

### 6.10 How to build it in TD 31550 (our recommendation)
1. **Draw all knob faces in ONE GLSL TOP, not N containers.** Pass an instance table (one row per knob: x, y, D, value, min, max, colour, type, state flags) via a Table/CHOP-to-TOP texture or an array uniform; the shader draws the arcs (smoothstep SDF ring from angle -135..+135), body, ring, tick, dot and toggle fill in one pass. Value text and labels cost: render them with one **Text TOP atlas** or a **Replicator of Text TOPs composited**, or draw text in the shader from a font-atlas TOP; start with Text COMPs on a Container per knob only for the first 50 knobs if the atlas path is slow. (Vendor evidence: "glsl cache optimize", 88 knobs benchmark with no lag, max 512 knobs.) Test GLSL knob with T-46 / T-18 caveats from LEARNINGS; the previous finding in 3.5 ("no GPU shader") is superseded for the UI layer.
2. **Interaction layer = one transparent Container COMP (the panel) with a Panel Execute DAT**, reading `panel.inside.u/v`, `panel.insideu`, `lselect/rselect/mselect`, `panel.u/v` and `panel.shift/ctrl/alt` (Panel CHOP `u`, `v`, `lselect`, `rselect`, `mselect`, `shift`, `ctrl`, `alt` channels) and hit-testing the instance table in Python (a pure function in `zk_logic.py`: `hit(x,y)`, `drag_delta`, `apply_sensitivity`). This keeps the node count constant and avoids a Container per knob; drag-drop of a parameter onto the panel uses the Container's `Drop` callbacks (`onDrop` on a Panel Execute / Drag-Drop DAT; **verify availability on 31550 first**; fallback = "Bind selected pars" pulse from TD's selection).
3. **Where a Replicator COMP is still right:** the presets bar and pill widgets (fewer, heavier items with their own state), and optional per-knob Container COMPs only for the properties dialog. **Slider COMP / Widget COMPs are not used for knobs**: they cannot draw arcs and would bloat the network. Use the Slider COMP only if a plain fader is needed.
4. Keep numbers in a **Table DAT + Constant/Script CHOP** (one channel per knob 0..1, `out_values` carries only that), preset morph in a **Lag/Math CHOP chain** or in Python driven by a Timer CHOP (Morph preset = interpolate captured -> stored on drag, so it needs no timer: the drag value is the t).
5. Key and mouse state: Panel Execute DAT `onOffToOn`, `onValueChange` for `u/v` while `lselect`; **Keyboard In** for W/P/L/H keys; right-click menu = our own Container popup (Replicator of Button COMPs) positioned at the cursor (TD's popMenu COMP is an alternative).
6. Theme: two Constant CHOPs (day / night) driving the shader uniforms; colour palette = Table DAT.
7. Verify with `td_window_capture` against `img/c1.png` side by side; check cooks with `td_perf` at 44, 88, 200 knobs (target: nothing cooks while idle).
8. Our own additions vs the vendor: auto-flow into groups and tabs, a fine-adjust modifier, scroll-wheel step, double-click reset, per-parameter undo. All optional and marked "ours".

### 6.11 Gaps (UNVERIFIED)
See also 7.5. The videos did not give drag sensitivity numbers or hover colours.
Exact knob pixel sizes, drag sensitivity numbers, hover colours, fonts and morph curve shape are not documented; the tox is locked so they cannot be read. The pixel numbers above are our estimates from screenshots. Confirm Drop-callback availability on 31550 before committing to drag-to-bind.


## 7. 404zero channel findings (26 Oct 2026, third pass)

Channel `youtube.com/@404zero/videos` listed with `yt-dlp --flat-playlist` (40 videos; the flat list gives no upload dates, `NA`). 9 zerror videos studied (8 downloaded <=720p; frames in `research_src/zerror_v5/channel/<id>/` = `fr/` scene-change+5 s frames, `sheet*.jpg` contact sheets 1 tile / 6 s, and named crops `*.png`). Descriptions and auto-subs fetched one video at a time with 6 s gaps; **0tP7jkdddgg subs hit HTTP 429 twice (initial + one retry after 5 min), so skipped** (no bypass tried; this video has a voice-over, so its spoken steps are not captured, only what is visible). Not studied: `sLuwuhLvx4k` TWOZERO Quick Start (a different product, description empty, subs 429) and the non-zerror art/festival videos. Nothing was run in TD, nothing decrypted.
All timestamps are **approximate (+/- 3 s, from contact-sheet tiles)**. No dates: the TD title bars show builds 2023.11340 (zerror4_28), 11510 (zerror4_29 / 4_52), 11600 (build "301", MIDI surfaces) = **v4-era, 2023**; only 0tP7jkdddgg looks like v5 (2024).

### 7.0 Corrections for the builder (firmest first, each tied to a video)
1. **Font is a humanist sans (Open Sans / Noto Sans look), not mono and not rounded.** Labels, values, pill names, surface titles and the properties menu all use it, regular weight, lower case; value digits are proportional. Use TD default sans or Open Sans/Noto Sans (OFL), not IBM Plex Mono. (s5FV29yoZq8 5 s and 40 s, 0tP7jkdddgg 114 s, zGld7ypMiFA 12 s.)
2. **Knob body has a coloured outline ring (the knob's colour, dimmer: ~#5f271e for orange) PLUS a separate outer arc in the bright accent, with a visible gap between them** (0tP7 q1/q3 crops, s5FV menu1). Arc thickness about 0.07 D, ring about 0.03 D, body #2d2a2c-ish (v5) / #1e1e1e (v4). Arc starts at **7 o'clock** and sweeps clockwise to **5 o'clock** (270 degrees; "5.000" at max fills almost the whole sweep with a gap at the bottom; "775" of a large range shows a tiny stub at 7 o'clock). This matches 6.2 but the ring is the *tag colour of every parameter knob*, not a "recallable" mark (unverified what the recall flag changes; see 7.3).
3. **The diamond tick (small rotated square) belongs to PRESET knobs only, not to parameter knobs**, and takes the **preset's colour tag** (orange, green, purple, blue seen). Parameter knobs have no tick. (8YKniBSSGAo 20 s crop: p1 green diamond, p2 purple, p24 green; 0tP7 q3: p1 orange, "whatever" blue.)
4. **Preset knob faces by type (colour of every element = the preset's tag):**
   - classic (instant recall) = body with a **solid dot ~0.3 D centred** + diamond at 7 o'clock (0tP7 q3 p1 orange dot, "whatever" blue dot);
   - morph (float) = empty dark body, **bright 270-degree arc** + diamond that marks the morph head (7 o'clock = 0, 5 o'clock = 1; head side estimated) (0tP7 q3 p2; zLBU w2 p1);
   - unused / empty slot = very dim grey track, diamond only, no ring (8YKn 20 s);
   - hovered morph preset = red arc with **arrow heads at both ends** and a faint red glow (s5FV menu1, "rf" pill, 5 s).
5. **Size is a continuous float multiplier, not 4 fixed sizes**: properties show `size 1.502`, `2.625`, `1.781`; a MIDI surface has `size 10.0`. One panel mixes 0.5x..2.6x knobs freely (Kow8WZaYE4k 62 s, 8YKn 20 s). Build `size` as a float par; label text stays the same size under big knobs (labels scale slightly, see s5FV menu1: 2.6x knob label barely larger).
6. **Mouse-down ("active") look differs per version:** v4 = a **small dark-blue ring (~0.3 D) drawn at the pointer** inside the knob/pill (s5FV menu1 5 s, zLBU w2 80 s); **v5 = the whole body fills solid with the accent (#c0392b-ish) while pressed**, arc stays (0tP7 q4, 20 s). Use the v5 one (body fill), make it the `active colour`; the blue ring is optional/v4 only. Update 6.2 "active" and the global setting accordingly.
7. **Toggle-type knobs: off = body filled with a dim tint of the accent (#432823) + bright ring, value text "0.0000"; no outer arc**; on = full accent (white text "1.0000"). Menu knobs (e.g. "perlin3d") show a **short arc at 7 o'clock** (index/option count) and the item name as value. (0tP7 q3: noise1-Mono, feedback1-R, noise1-Type.)
8. **Properties menu (RMB or P) is a flat list, black header row with the knob name, then zebra rows (#1b1b1b / #333034-ish), label left, value right (value column starts at ~47% of width), radio = ring that shows an inner filled dot when on.** Row order, v4 and v5: `knob type` (float / toggle / momentary dropdown), `recall`, `sensitivity` (default 1; 0.5 seen), `min`, `max`, `filter`, `clamp min`, `clamp max`, `label`, `size`, `color` (6 dots), `show value`, `chan`, then a second block with **tinted labels**: `MIDI`, `show OP` (teal), `save to layout` (green, with 3 circle choices green/blue/red), `set as default` (blue-grey), `delete` (red, red ring). Pills add `include`/`WIDGETS` rows. **Knob colour palette (v5): pink, orange-red, lime, cyan, blue, white; v4: red, green, blue, magenta, orange, grey.** Menu opens at the panel's top edge beside the panel (v4, s5FV 40 s) or at the pointer (v5 0tP7 114 s), about 0.3 D per row at size 1. Editing min on a selected knob while it is "out of range": the label turns red (confirmed in s5FV 40 s: "noise2-Ampl" red corner brackets + value 5.000 outside 1.0 min).
9. **Selection looks:** Run mode marquee-select (RMB drag on empty background) = **small red L-shaped corner brackets** at the corners of each selected knob cell (s5FV 40 s, vAYE 5 s). Layout mode = faint grid on the background, **one grey rectangle outline around the marquee with large grey L-corner handles**, plus tiny red corner ticks per cell (0tP7 q2 140 s, zLBU w2). A new/selected MIDI surface shows big red corner brackets (zGld 0 s).
10. **Layout switcher evolved: v4 = a vertical pill, bottom-right, dark with a green dot (FhQEl4UkleU all frames; 8YKn 4:37 voice-over calls it "a small green button in the bottom right corner" that switches the controller's three interfaces); v5 = free-placed small circles (green here, 0tP7 q3 170 s).** Keep the circle (6.4) and add the pill as an optional compact style.

### 7.1 Videos (table)
| Video id | Title | Length | What it shows (approx. timestamps) |
|---|---|---|---|
| 0tP7jkdddgg | ZERROR.tox. Quick start. (v5-era, voice-over, subs 429) | 209 s | 0:06 empty panel with "+" ; 0:12 drop `noise1 Period` -> first knob; **0:20 press fills the body solid red-orange (q4)**; 1:00-2:00 more drops (Harm, Type, Mono, feedback), preset knobs appear (drag "+" out); **1:54 RMB menu on knob (q1: full property list, colour dots)**; 2:10-2:20 layout mode: grid, marquee, grey frame with corner handles (q2/q5); 2:50 `rand` and `randPres` pills plus green layout dot (q3); output visuals change as presets morph. |
| vAYEB10QEqU | ZERROR. Parameters. | 40 s | 0:05 marquee over knobs (red corner brackets), P opens settings menu for the selection; 0:20 colour change; recall radio detaches a parameter from the presets ("control this parameter independently"). Panel bg #0c0c0c, red knobs, TD 2023.11340. |
| s5FV29yoZq8 | ZERROR. Parameters and presets settings. | 79 s | 0:05 hovering a preset ("rf" random pill): red arc with arrow heads + blue pointer ring (menu1.png); 0:08 preset menu has `knob type` dropdown (float / toggle / momentary); **0:40 full parameter properties menu next to the panel (menu2.png)**; text: preset menu = appearance, sensitivity, colour, filter, name; parameter menu = knob appearance, value display, sensitivity, colour, MIDI. |
| FhQEl4UkleU | ZERROR. Random pills. | 301 s | "+" at top right; white arrow cursor while dragging a parameter from a TD dialog onto the panel (0:25, 0:55); knobs created one by one; first preset by dragging "+" out (~1:20-3:10); **`rand` pill = disc of coarse random pixel noise (0:09 onward), shown with a white arc outside while dragged**; layout of many 1x knobs in one column then free placement of p1..p9 (2:00-5:00); transform pars with expressions (`absTime.seconds`) as a knob drop (4:00 sheet2). Green pill at lower right throughout. |
| zLBUVeJvCyA | ZERROR. AV Performance in 10 min. Part 1. | 264 s | noise + ramp + displace, params dropped in; 0:17-0:50 knob column grows; **1:18 W opens widgets popup (lists Midi Fighter Twister etc.)**; 1:30 rand pill red when active (w2/sheet3); 1:55 ramp colour picker. Voice: "add a parameter randomizer by calling the menu with W", limit the randomizer by min/max. |
| 8YKniBSSGAo | ZERROR. AV Performance in 10 min. Part 2. | 315 s | 0:00 settings; 0:48 **TD's own MIDI Mapper dialog** opens (Twister rows) ; 1:00-1:30 W -> choose Twister, place the surface, P/RMB enables widget, drop params/presets onto it (red-bracket selection of the empty surface, 3:00); Twister mirrored live, LEDs light; 3:10-5:00 audio setup (not UI). Pills near bottom right. Voice: 3 left buttons on Twister (re-save/new param, colour, delete). |
| Kow8WZaYE4k | ZERROR. MIDI Fighters tutorial. | 158 s | Spectra + Twister surfaces side by side (blue frames, titles, dots); **1:02 ghost drop target: a grey double ring with "+" and a small rounded rectangle while dragging a parameter over an empty slot (s1.png)**; multi-drop, new preset from encoder push, parameter from pushing an encoder while hovering a TD parameter, left-side buttons, virtual banks. |
| zGld7ypMiFA | ZERRROR. MIDI Surface tutorial (nanoKONTROL2, build 301) | 189 s | 0:02 W, add MIDI surface; **0:05 label RMB menu (g1.png)**; 0:15 rows x cols, configure; 0:25 config dialog with slot list and ch/cc readout, selected slot crimson; 0:40 drop operator params into the surface (auto-assign), create/delete presets; 1:11 random pill set to momentary and bound to a button; 1:32 `create presets` / `create pars`; 2:02 clone surface = virtual bank; 2:34 save/load config to file. |
| 76eOp_YEZKQ | already covered in 5.1 | 52 s | - |

### 7.2 New interaction facts (with source)
- **Creating knobs:** drag from the TD parameter dialog onto the Zerror window; the cursor is TD's white arrow with a small label box (FhQEl 0:25). Over an empty MIDI slot the drop target shows a ghost "+" in a grey double ring with a small rounded rectangle underneath (Kow8 1:02). Dropping several at once assigns them to the next empty slots automatically (zGld 0:42). A parameter can also be turned into a knob **from the controller**: mouse over a TD parameter, then push/turn the encoder on an empty slot (`create pars`) (Kow8 1:23; zGld 1:44).
- **Presets:** the "+" circle is dragged out to the workspace to create a preset knob (FhQEl, 0tP7); on a surface, push a button/encoder or turn an encoder **fully clockwise** on an empty slot with `create presets` on (zGld 1:40). Presets are deletable from either side and stay in sync (8YKn 1:11). Twister re-save: select the preset, edit knobs on the panel, left button 1, press the preset again (8YKn 1:20).
- **Pills:** W menu -> drag the pill out. Random pill can be switched to momentary and bound to a button (zGld 1:11). `rand` is a coarse pixel-noise disc, `randPres` a fine-grain noise disc with a diamond (0tP7 q3).
- **Selection/properties:** marquee (RMB drag background) then P applies the settings menu to all selected knobs at once (vAYE 0:05; matches 5.2). Recall radio per knob detaches that parameter from the presets (vAYE 0:30).
- **Surfaces:** configure dialog lists slot1..N with ch/cc; selected slot is crimson, advances automatically on each tweak, mouse click or up/down arrow keys move it (zGld 0:25). Click a surface label or its top-right dot (or a bound hardware button) to switch virtual bank (zGld 2:15, Kow8 2:16). Bank = a cloned surface; surface config saved/loaded as a file (zGld 2:34). Device picked from the label's RMB menu `device` (zGld 0:05). Device LEDs follow the panel in real time; presets/params dropped into a surface light on the device immediately (8YKn 0:34).
- **Panel window** can be resized freely, also to a wide monitor layout (8YKn 0:13). Knobs can be driven from both Zerror and TD's own parameter dialog (zGld 0:58): two-way bind.
- **Value text format:** about 4 significant digits and trims to fit: `0.9304`, `0.2740`, `0.0550`, `0.552`, `1.948`, `16.45`, `4030`, `-0.134`; integer pars show `3`, `775`; always centred in the body (estimated rule: 4 sig. digits, precision from the par's own step).
- Drag sensitivity in numbers: **not recoverable from video** (cursor drags are slow and unmeasured). The `sensitivity` field exists per knob (default 1, 0.5 seen) and also on surfaces.

### 7.3 Surface look (firm, Kow8 62 s, zGld 12 s, 8YKn 20 s)
Frame = 1.5 px rounded rectangle in **blue (#5b8fd0-ish; cyan-blue)**, title (e.g. SPECTRA, TWISTER, "MIDI Surface") **top-left, caps or as typed, same blue, about 0.4 D tall**, filled blue dot **top-right** (active bank; menu `on`), empty slots = thin outline circles in dim blue-grey (#34506b), ~0.85 of the cell, grid rows x cols from the menu (Spectra 4x4, Twister 4x4, nanoKONTROL2 5x6 with `rows`/`cols`). Knobs in slots keep their colour/size scaled to the slot, name below. Surface RMB menu: black header with the label, **orange "WIDGETS" and blue "MIDI" section titles with coloured dots**, then `sensitivity`, `label`, `size`, `color` (pink, red, light green, teal, blue, white), `device`, `on`, `MIDI out`, `cc pickup`, `rows`, `cols`, `configure`, `create presets`, `create pars`, then red-orange text rows `fill empty slots`, `clone surface`, `load config`, `save config`, `delete`.

### 7.4 Evolution v4 -> v5 (from comparing frames)
| Aspect | v4 (2023 builds) | v5 (0tP7 quick start) |
|---|---|---|
| Panel bg | near-black #0c0c0c | #222 inside TD dark UI (bg colour now a setting) |
| Default accent | red-orange #d94a2a, arc brighter (#e8421c) | orange-red, a bit lighter; colour palette now pink / orange / lime / cyan / blue / white |
| Pointer/press feedback | blue ring at pointer | body fills with accent |
| Layout selector | vertical green pill, bottom right | round dot (R/G/B) free-placed |
| Surface menu | WIDGETS + MIDI headings, `cc pickup`, `configure` | same, more rows later (docs: DMX etc.) |
| Property menu | same row set (already has `save to layout`, `show OP`, `set as default`) | same; labels tinted |
Unchanged: "+" circle (dark disc ~1.1 D, white plus), knob arc geometry, label and value placement.

### 7.5 Still unverified
Exact drag sensitivity, scroll behaviour, hover colour, fonts' exact family (judged Open Sans/Noto by eye), the exact morph curve, what the `recall` flag changes visually, spoken narration of 0tP7jkdddgg (subs 429), whether the green pill is layout or bank selector, upload dates.
