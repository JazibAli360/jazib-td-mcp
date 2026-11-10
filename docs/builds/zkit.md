# zkit: zerror-style controls kit (26 Oct 2026, TD 2025.31550)

The standard controls panel for our COMPs: zerror-style knobs, presets with hand morph, randomise, properties menu,
night/day themes, two-way with the COMP's custom parameters. Clean-room, our own code. Spec:
`docs/research/BE_rudiment_zerror.md` sections 6 + 7.0 (corrections followed: humanist sans, outline ring + gap +
270-degree arc, diamond only on presets, continuous size, v5 mouse-down body fill, menu knob short arc + item name,
properties list order, blue surface frames).

Demo: `/project1/lab/ZK_controls_kit` (noise look driven by its Look + Motion pages; pulse `Opencontrols`).

## Use it on any COMP

```python
# in TD (td_exec)
ns = dict(globals()); exec(open('<repo>/builders/zkit.py').read(), ns)
ns['build_controls']('/project1/lab/MY_COMP')                      # all custom pages except Zkit
ns['build_controls']('/project1/lab/MY_COMP', pages=['Look'], d=64, cols=6, open_window=True)
```

`build_controls(comp_path, pages=None, exclude=(), d=56, cols=8, panel_name='controls', open_window=False, winop=None,
keep=(), essentials=None)` (`panel_name` may be a path inside the COMP, e.g. `controls/params` with `winop='controls'` when the kit is one
part of a bigger panel; `keep` = panel children that are not strays):
adds a **Zkit** page once (`Opencontrols`, `Zktheme` night/day, `Zkd` knob px, `Zkcols`, `Zkmaxh` max panel height px
(0 = fit the screen), `Zkrandamount`, `Zkrandomize`, `Zkshowall`, `Zkrebuild`, plus the COMP's macro knobs `Zkm1..`),
makes or refreshes `<comp>/controls` (Container COMP) and `<comp>/controls_window`.
Idempotent; knob properties, presets and collapsed groups survive rebuilds. **T-70 safe:** the COMP's own window is
closed first and reopened 5 frames after; the panel container is never destroyed; only stray non-`zk_` children of an
older panel (e.g. autoUI widgets) go, through `safe_destroy`; the network pane is never moved. No functions in storage.

## Files
| File | What |
|---|---|
| `builders/zkit.py` | builder (`build_controls`, `build_demo`) |
| `builders/zkit_logic.py` | pure logic, no `td` (copied into `controls/zk_logic`) |
| `builders/zkit_rt.py` | TD runtime: items, mouse, keys, presets, drawing (copied into `controls/zk_rt`) |
| `builders/zkit_face.glsl` | the one face shader (copied into `controls/zk_face_glsl`) |
| `builders/zk_essentials.json` | Main tab per COMP name: `main` par names + `macros` (validator: `test/test_zk_essentials.py`) |
| `test/test_zkit.py` | 60 offline logic tests: `python3 -I -m unittest discover -s test -p 'test_zkit.py'` |
| `test/test_zkit_perf.py` | 36 offline runtime tests on a fake TD (writes per event, incremental = full draw, same picture as the rollout runtime for a panel that fits, viewport / tabs / scroll / essentials, dropdowns with a live menuSource); bench: `python3 -I test/test_zkit_perf.py bench [big]` (`big` = 432 knobs, PX-sized) |

## How it is built (inside `controls`)
- **Faces:** every knob, preset slot, pill, group frame and menu row is one *instance* (16 floats, `zkit_logic.FIELDS`)
  in `zk_gpu` -> DAT to CHOP -> CHOP to TOP (32-bit float) -> **one GLSL pixel pass** (`zk_face`, single pass, so T-46
  does not apply) that draws them all. Knobs: body, dim tag ring, gap, 270-degree track + butt-capped fill arc from the
  zero point (tiny stub at zero), body fills with the accent while pressed (v5). Toggle off = dim tint + bright ring,
  on = full accent. Menu = short arc segment of the current item + item name. Swatch (RGB par) = body in that colour,
  arc = brightness. Presets: classic = 0.3 D dot + diamond at 7 o'clock, morph drag = arc + diamond head, hover = red
  arc with arrow heads. `rand` = pixel-noise disc with a white arc while dragged.
- **Text:** Open Sans, white, one Text TOP per font size (`zk_text0..7` + spec tables `zk_ts0..7`) plus two hot Text
  TOPs (`zk_hot0/1` + `zk_hs0/1`) holding only the value text of a knob being dragged / changing every frame; the face
  shader reads them directly (no composite since the perf pass) and colours the text pixels per instance box (kind
  `tcol`, field `u` = which text input), in draw order, so the properties menu covers knob text.
- **Perf (26 Oct, `docs/builds/zkit_perf.md`):** cached per-knob draw segments, `Render(only=...)` per event, hit-test
  grid, only changed cells written, 64 px tile lists (`zk_tiles` -> face input 1) so each pixel loops over ~7
  instances instead of all.
- **Input:** `zk_mouse` (Panel Execute: u v lselect rselect mselect wheel rollover), `zk_keys` (Keyboard In, active only
  while typing), `zk_sync` (Parameter Execute on the host: two-way + Zkit pulses), `zk_tick` (on only while `filter`
  glides). State tables: `zk_cfg`, `zk_props` (per knob), `zk_presets` (raw values as json, like the original).
- Cooks only on change: idle panel = 0 cooks.

## Pages + scroll (28 Oct 2026, T-231; user: "knobs and controls are falling off the screen")
The panel is a **viewport**, never sized to its content (T-231: PX_pointfx's 666 x 6935 panel aborted main in Metal).
- **Size:** width as before (columns cut when they would pass the screen width); height = min(content, `Zkmaxh`), and
  `Zkmaxh 0` = the screen (`monitors` `scaledHeight`, stored in `zk_cfg` `screen` by the builder) minus 160 pt. Every
  texture the kit makes is <= 4096 a side (`zkit_logic.TEX_CAP`), at most 1024 instances (`MAX_INST`).
- **Header (fixed):** presets bar, then one pill per tab: **Main** (default), one per custom page, **All**. The
  selected tab is kept in `zk_cfg` `tab`. One page and no Main = no tabs. The panel keeps the same size on every tab.
- **Main** = the COMP's essentials (`builders/zk_essentials.json` by COMP name, read at build time into `zk_cfg`
  `main` / `macros`, unknown names noted in `ess_notes`), then its macros. No entry = the first 12 controls of the
  first page, no macros. PX module pars are uid-named (`M4progress`): shown / driven only while that uid holds the
  type of PX's DEFAULT_STACK (`zk_cfg` `uidtypes`), else skipped with a note in `rt_notes`.
- **Macros** `Zkm<n>` = Float pars 0..1 on the Zkit page; a change of the macro (only) sets each driven par linearly
  from -> to (a driven par moved by hand is not fought). Presets and randomise include them (a preset's driven values
  win over its macro position).
- **Hidden while unused:** PX module pages whose `px_stack` row is disabled (a `zk_watch` DAT Execute on `px_stack`
  rebuilds when the stack changes); a page whose first par is a `...on` switch toggle (Vhon, Geoon, Lineson, Soundon)
  shows only that toggle while it is off. No reliable signal = the page shows. FX / GEN rack module panels are per
  module (`FX_glitch/smear1`): they use the fallback Main.
- **Balance:** rows within a group are split evenly when it costs no extra row (9 cells on 8 columns = 5 + 4).
- **Scroll:** content scrolls under the header, slim scrollbar in a right gutter; position clamped, per tab, in
  `zk_cfg` `scroll`. Only knobs in a **stage band** (the viewport plus half a view above and below) are in the tables;
  content instances carry flag 256 and the shader moves them by the `uView` uniform and clips them under the header.
  A notch inside the band writes the thumb's cells + one uniform; leaving the band rebuilds it once (~10-17 ms).
- Typing, hover, the properties menu (opens beside its knob in view px; closes on scroll), presets and drags all hit
  through the scroll offset (`zkit_logic.where`).
- Live b2 (31550, PX_pointfx copy, 379 knobs on All): face 666 x 6935 -> **678 x 1169**; scroll notch 0.21 ms Python
  + 0.35 ms face GPU, drag after scroll 1.19 ms Python + 0.46 ms GPU, 60 fps; idle 0 cooks (188 frames, window open).

## Gestures
| Gesture | Action |
|---|---|
| LMB drag up/down | tweak; 200 px = full range / sensitivity; Shift 1/10, Ctrl(Cmd)+Shift 1/50, Alt x4; incremental (a modifier pressed mid-drag applies from there) |
| click knob | type a value (Enter commits, Esc cancels, leaving the panel or clicking elsewhere commits); typed values may leave the range unless clamp min/max (label goes red) |
| click toggle / menu | flip / next item (Shift = previous); momentary = on while held; pulse = pulse (static `Menu` pars only) |
| click a dropdown field (StrMenu) | pop-up list of its CURRENT items; click an item = set the par to that item's name; the header row ("type...") = type a value |
| Alt+click a dropdown field | type a value (starts from the current text; any text: spaces, `#`, `*`, `/`; Enter commits, Esc cancels) |
| Esc / click outside / leaving the panel / RMB / wheel outside the list | close the pop-up list (nothing else happens on that click) |
| double click | recall on/off (not recallable: grey ring; skipped by presets + random) |
| MMB | default (par default or "set as default") |
| RMB knob | properties menu (rows in 7.0 #8 order); RMB on a stored slot = delete preset |
| wheel over a knob | 1 % per notch (Ctrl/Cmd 0.1 %); int/menu one step; a dropdown field's value never changes (the panel scrolls) |
| wheel over an open pop-up list | scroll its rows |
| wheel elsewhere (empty space, group title, scrollbar, header) / Shift+wheel anywhere | scroll half a knob row per notch |
| scrollbar | drag the thumb; click the track = a page up / down |
| tab pill click | show that page (Main / page / All) |
| `+` click / drag onto a slot | store into the next free slot / into that slot |
| slot click / drag up | classic recall / morph captured -> stored (drag back = back to captured) |
| Shift+click slot | overwrite |
| `rand` click / drag | jump to / morph toward a random state (`Zkrandamount` = fraction of each range) |
| group title | collapse / expand; theme circle = night/day |

## Verified live (26 Oct, 31550; values read back from the pars; mouse driven by setting the panel's own panel values, which fires `zk_mouse` like a real mouse)
- Drag Period (0.1..8, from 1.2): +50 px -> 3.175 (expected 3.175); then Shift +100 px -> 3.570 (3.570); Ctrl+Shift
  +100 px -> 3.649 (3.649); Alt +10 px -> 5.229 (5.229). Harmonics (0..8, 3) +30 px -> 4. Wheel on Speed 1.0 -> 1.04.
- Menu click simplex3d -> perlin2d; toggle Mono off -> on; Flash True while held, False on release; Reseed pulses
  (seed +1, one frame later); MMB on Gain 0.7 -> 0.0; external `Rotate = 90` -> knob u 0.75 (two-way).
- Presets: A stored by `+` (slot 1), B by dragging `+` onto p3; p1 click recalls A exactly (1.0, -0.5, 2, perlin2d,
  off); dragging p3 up 100 px = t 0.5 -> Period 3.0, Gain 0.0, Harmonics 4, Type random, Mono on; dragging back -> A.
  Double click Gain -> recall 0 -> p1 recall keeps Gain 0.9. Random amount 0 -> unchanged; amount 1 -> Period 3.424,
  3.502, 0.817, 5.648, 1.969 over 5 clicks, locked Gain untouched. RMB p3 -> deleted.
- Typing: "2.5" Enter -> 2.5; "9.5" -> 9.5 with a red label (range 0.1..8); string Caption "Hi". Properties: colour ->
  blue, clamp max on, size 1.6 (relayout), knob type float -> toggle -> momentary -> float, delete hides, `Zkshowall`.
- Day theme, collapsed group, rebuild with the window open (closed, rebuilt, reopened, no crash), `Opencontrols`.
- td_errors clean; td_layout check ok (no intruders / unboxed / box overlaps) on the demo COMP and inside the panel.
- **Perf:** idle 0 cooks in 120 frames. A 60-frame drag: `zk_face` cooked 47 times, GPU 0.36 ms, CPU 0.18 ms; one text
  bucket recooks. Python redraw 2 ms per change (14 knobs). Bench 88 knobs (287 instances, 666x1102): redraw 3.6 ms
  median (13.1 ms before incremental table writes), face GPU ~1.8 ms.
- Captures: the window in the session scratchpad (`zk_window.png`, `zk_window2.png`, `zk_props5.png`, `zk_day.png`).

## Rollout (26 Oct): 8 lab COMPs, results + fixes in `docs/builds/zkit_rollout.md`
Labels kept whole (shrink to 0.85/0.72, then a bracketed note and whole trailing words go), Text TOP minimum ~9 px
(`MIN_FONT`), file pars show the file name, no redraw while `controls_window` is closed (draws on open / next mouse).

## Dropdown fields (28 Oct 2026; StrMenu with a live `menuSource`, T-233)
Name fields (PX presets / Sel / Effname, effectors Target / Refto / Addref, every Effselect and the `+ name / - word`
helper menus) are StrMenu pars whose items come from a `menuSource` evaluated on every read. The kit used to copy the
items once at panel build and cycle them by `menuIndex` (stale lists; a typed value read as item 0; a helper menu
applied a different edit per click). Now:
- **Every StrMenu = a dropdown field** (two cells wide, kind `dropdown`, shader kind 19 `drop`): the current text
  (case kept, a long op path shows `../` + its tail, the op's own name whole: `zkit_logic.fit_value`) and a small
  down triangle (accent while open / hovered). Static `Menu` pars keep the knob (short arc + item name, click = next).
- **Click = pop-up list**: `menuNames` / `menuLabels` are read **at click time** (`zk_rt._open_drop`), never at build
  (offline test: 0 reads at build, presets or random). Drawn by the same face pass as the properties menu (rows,
  zebra, hover, the current value blue, a slim scrollbar when long); placed under the field when the whole list fits,
  else above, else on the roomier side with the rest scrolling (`zkit_logic.drop_geom`); always inside the capped
  viewport and under the header, never over the field. `zk_keys` is active while it is open (Esc).
- **Pick = the NAME** (`_write_par(par, name)`): helper items already hold the whole new text (`+ #demo` on `all` ->
  `#demo`, then `+ sphere1` -> `#demo sphere1`, `- #demo` -> `sphere1`).
- **Presets store the text; randomise skips names** (a StrMenu has no random spec). An index stored by an older
  preset for such a par is not applied.
- Live b2 (31550): /project1/effectors (Target / Addref / Refto) and /project1/perf2/GEN_clone (Effselect helper menu,
  overflow panel 678 x 1169): an effector added by the Add pulse was in the Target list at the next click with no
  rebuild (`gen` unchanged); pick -> Target `null1`; helper picks `all` -> `#demo` -> `#demo sphere1` -> `sphere1`;
  wheel over the closed field: value unchanged; Alt+click typed ` #zk` -> `sphere1 #zk`; Esc closed the list and
  turned `zk_keys` off. Python per event: open 4.4 ms (effectors) / 7.4 ms (GEN_clone, 103 instances), hover 0.7 /
  1.1 ms, close 2.5 / 4.1 ms. Idle 0 cooks of zk_face / zk_gpu_chop / zk_tiles_chop / zk_text0 / zk_out over 190
  frames, window open, with and without a list open. Captures (panel TOP, T-242): session scratchpad `zk_menus/`.
- A panel gets this when it is refreshed (`refresh_panel`, see `zkit_rollout.md`).

## Not done / open
- Real keystrokes into the Keyboard In DAT were not sent (would type into the user's TD); `Key()` was fed key events
  with the documented fields. `zk_keys` listens globally while a value is being typed (ends on Enter/Esc/leaving).
- Layout mode (marquee, move knobs, align), the 3 R/G/B layouts (the `save to layout` row is drawn dim), drag a TD
  parameter onto the panel to bind it, MIDI surfaces + learn (the `MIDI` row only names `td_midi_learn`), XY pad,
  Play / Offset pills, per-preset colour editing, `chan` output CHOP, read-only (state) pars, section headers inside a
  page. Hover colour and the recall-flag look are our choice (vendor unverified, 7.5).
- `fmt4` shows about 4 significant digits; ints and menus plain.
