# zkit rollout to the finished lab COMPs (26 Oct 2026, TD 2025.31550)

The zerror-style controls kit (`docs/builds/zkit.md`) replaced the autoUI panels of 8 COMPs, one at a time, in place
(T-70 safe: own window closed first, the `controls` container kept, old widgets through `safe_destroy`, window
reopened after when it was open). `Opencontrols` + `controls_window` keep their names and work (the COMPs' own
`controls_open` DATs stay; the kit's `zk_sync` also opens the window). LK_projection_room was skipped (another lane).

How to apply: `ns = dict(globals()); exec(open('<repo>/builders/zkit.py').read(), ns); ns['build_controls'](path)`.
The COMPs' own builders now refresh the kit in place instead of making autoUI widgets (`_zkit_refresh` in
`db_meter.py`, `face_track.py`, `previz_stage.py`; `timeline.py` keeps a kit in `controls/params`; ZC's
`ZCtl.RebuildUI` re-reads the kit after Bind/Unbind instead of running autoUI).

## Results (values read back from the pars; pars driven through the kit's own press/drag/release logic)

| COMP | knobs | panel | widgets | driven through the kit -> COMP | panel cook per change | fps |
|---|---|---|---|---|---|---|
| AC_audio | 5 | 579x232 | file (string, shows file name), 3 knobs, menu `device`/`file` | Trim 0.5 -> 2.5 (drag 100 px): `trim` CHOP peak 0.022 -> 0.170 vs src 0.068 (x2.5); Specgain 5 -> 1.1 = `spec_gain.gain`; Source click device -> file: `src_sel.index` 1 -> 0 | face 0.25 + 0.24 GPU ms, Python 0.8 ms/event | 57-63 |
| LK_typecore | 5 | 579x365 | string, 3 knobs, RGB swatch | Glow 1.6 -> 2.05 = `compose.vec1valuex`; Fontsize 380 -> 470 = `word.fontsizex`; Outline swatch drag -40 px = (0.62,0.28,0.95) -> (0.49,0.22,0.75) = `compose.vec2`; out pixel (0.5,0.6) white -> outline colour | face 0.15 + 0.33 GPU, one text bucket ~0.15; Python 0.6-0.9 ms | 55-59 |
| LK_spectrum_glass | 8 | 579x365 | int, 5 knobs, 2 swatches | Barcount 56 -> 28 (int drag), Ringsize 0.181 -> 0.251, Colora -> 0.36/0.13/0.55 = `glass.vec4/vec5`; 69 of 576 grid samples of `look_out` changed (max 1.28) | face 0.13 + 0.26 GPU, text ~0.25 GPU; Python 0.56 ms | 60.4 |
| AU_db_meter | 32 | 666x805 | 5 menus, knobs, 2 ints, 3 toggles, pulse, 7 swatches | Orient click vertical -> horizontal: out1 samples changed (3 of 7 points); Showscale toggle on -> off -> on; Gap 4 -> 23.2 | face 0.15 + 1.32 GPU, text 1.44 GPU; Python 1.25-1.4 ms/event | 59.9-60.3 |
| ZC_control_surface | 29 | 666x626 | toggle, menu, ints, 9 pulses, 2 strings, 6 knob + 6 lock pairs | Knob1 1 -> 0.7 (drag -60 px) -> bound target `test_const.const0value` 0.7, `out_values` Knob1 0.7; Lock2 off -> on; Morphcurve linear -> ease; Bind/Unbind of a 7th knob re-reads the kit (29 -> 31 -> 29 items, window reopened) | Python 3.6 ms/event (first), steady ~1 ms | 60.4 |
| TL_timeline | 31 | 974x452 (+ ruler 1024x360 above) | toggles, knobs, menus, pulses, string | Rate 1 -> 2.2 -> `tl_out.tl_rate` 2.2; Keyinterp linear -> ease; Gotoend pulse | while playing + window open the playhead knob redraws every frame: Python 1.4 ms + face 0.77 + comp 0.69 GPU; window closed: 0 cooks (was 1.4 ms/frame Python before the `_shown` fix) | 59.5-60.5 |
| PV_previz_stage | 70 | 796x1206 (Zkd 46, Zkcols 12) | menus, knobs, ints, toggles, swatches, pulses | Exposure 0 -> 1.6 -> `grade.brightness1` 3.03, out1 samples changed; Preset FOH -> next; Hazeon on -> off = `haze.vec1valuew` 0 | Python 2.5 ms/event (70 knobs) | 60.6 |
| FT_face_track | 28 | 666x672 | toggles, ints, knobs, 5 menus, 2 file strings (file names), pulse, swatch | Wireopacity 1 -> 0.7 = `overlay.vec0valuew` 0.7; Showboxes off -> on; Wirewidth 2 -> 3.5 | Python 1.07 ms/event | 60.2 |

All values restored after the checks. td_errors clean and `td_layout flow` ok (stage plan re-applied; no intruders,
unboxed ops or box overlaps) on every COMP and inside each panel. Idle panel = 0 cooks (120 frames, window open).
Read-only (Info/State/Output) pars are not shown (kit limitation, listed in zkit.md). Captures of every window:
session scratchpad `zk_<COMP>*.png`.

Cooking state restored: AC_audio, LK_typecore, LK_spectrum_glass, TL_timeline, PV_previz_stage parked again;
AU_db_meter, ZC_control_surface (windows open as found) and FT_face_track left cooking as found.

## Kit fixes made during the rollout (builders/zkit*.py; test/test_zkit.py 29/29)
- **Labels kept whole** (user rule: names and words intact): `fit_label_size` tries the font at 1.0/0.85/0.72,
  measured with the panel's own text widths; if still too long a bracketed note goes first ("kick glow (flash-safe)"
  -> "kick glow"), then whole trailing words; a single over-long word is end-cut. Menu item names in the knob body
  use the same fit ("vertical", not "vertic").
- **Text TOP minimum size (31550):** `evalTextSize` at fontsizex 3..9.6 px returns the same width as 9 px and sizes
  quantise (10..11 px equal, 11.5..12.5 equal): `_tw` clamps at `MIN_FONT = 9`, or small labels overlapped.
- **File/Folder pars** show the file name, not the path's start.
- **No redraw while nobody sees the panel:** a par moving every frame (TL playhead) cost ~1.4 ms Python per frame
  with the window closed; now `Sync` marks the panel dirty when `controls_window` exists and is closed, and it draws
  on `Opencontrols` or the next mouse event.
- **GLSL TOP docked DATs:** a new `zk_face` docks its own info/pixel/compute DATs; they go right after creation
  (they were removed as "strays" on the second build).
- `build_controls(..., winop=None, keep=())`: `panel_name` may be a path inside the COMP (`controls/params`, used by
  TL_timeline so its ruler view stays above the knobs); `winop` = what the window shows; `keep` = children of the
  panel that are not strays. (The first TL pass removed the ruler as a stray; it was rebuilt from timeline.py's
  settings and `ruler_input` re-pointed.)

## Notes
- The first `zk_face` cook after a (re)build or the first window open costs ~110-125 ms CPU (shader compile); later
  cooks 0.13-0.25 ms CPU. One-off hitch, not per frame.
- Large panels: AU (32 knobs) ~3 ms GPU on frames that change; PV (70 knobs) 2.5 ms Python per mouse event. Idle 0.
  Perf pass (offline, not yet live-checked): `docs/builds/zkit_perf.md`.
- Module state of `zk_rt` resets whenever its DAT recompiles (td_errors force-cooks it); `OnPanel`/`Render` rebuild
  lazily, so scripted drives must call `Rebuild()` first when `S['lay']` is None.

## Pages + scroll + Main tab rollout (28 Oct 2026, T-231 / T-232)
Panels carry their own copies of the kit, so each changes only when rebuilt. One exec per COMP in main, one at a time
(T-70 / T-213: `refresh_panel` closes an open window first, reopens it 5 frames later, moves the network pane to the
COMP's parent, un-parks a parked ancestor only for the build):
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/zkit.py').read(), ns)
ns['refresh_panel']('/project1/lab/PX_pointfx')
```
It re-runs `build_controls` with the panel's own arguments (`zk_cfg` pages / exclude, its path inside the COMP, the
window's target, non-zk children kept), so knob properties, presets, collapse, `Zkd` / `Zkcols` and the remembered
tab / scroll stay. Returns `before` / `after` panel px and `notes` (essentials names skipped). Start with a small
panel, check `after` is <= the screen, then the tall ones (PX_pointfx, PX_lines, BO_particles, MX, GN_*). A COMP's
own builder (`px_rt.rebuild_ui`, `_zkit_refresh`, `fx_film`) gives the same result next time it runs.

## Dropdown fields rollout (28 Oct 2026)
The new kit (StrMenu = dropdown field + pop-up list, `zkit.md` "Dropdown fields") reaches a panel only when it is
refreshed. One exec per host COMP in main (the hosts = the `target` of every `zk_cfg` under /project1), small panels
first; it refreshes every panel of that host (a COMP can have more than one, e.g. TL_timeline `controls/params`):
```python
HOST = '/project1/lab/PX_pointfx'
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/zkit.py').read(), ns)
c = op(HOST)
[ns['refresh_panel'](c.path, panel=t.parent().path[len(c.path) + 1:])
 for t in c.findChildren(name='zk_cfg', maxDepth=3)
 if t.OPType == 'tableDAT' and t['target', 1] is not None and t['target', 1].val == c.path]
```
