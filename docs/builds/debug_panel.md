# /project1/debug: zkit skin (26 Oct 2026, TD 2025.31550)

The debug panel (`td/debug.py` cmd_debug_panel_build + `td/debug_panel_rt.py`, T-72/T-73) predates the zkit
controls kit. `td_debug_panel {style:'zkit'}` now calls `builders/zkit.py` `style_debug_panel(comp, theme='night')`
(themes `night`, `day`: `zkit_logic.DEBUG_THEMES`, from the kit's THEMES / PALETTE / SURFACE_BLUE / RED).

## What the skin changes (and why it costs nothing per frame)

| Part | Plain | zkit skin | Cost |
|---|---|---|---|
| Text colours | amber/grey/red | white head, kit blue titles, kit label grey body, red errors | param writes only when different |
| View background | Constant TOP `view_bg` | `zk_bg` GLSL TOP: black head band + orange accent rule, title bands with a 3 px blue bar, zebra rows per section (bands from `debug_panel_rt.view_lines` slots via `zkit_logic.debug_bands`) | no inputs, no time: cooked 4 times in total (shader compile + rebuilds) |
| fps graph | OP Viewer of `fps_chop` (CHOP viewer, red line, black) | OP Viewer of `zk_graph`: GLSL TOP, fps_chop as a texture-buffer uniform `uFps`; kit-night bg, grid at 60 and 30, orange line + gradient area, red where < 90 % of target | cooks only when fps_hist changes (2 Hz) and only while the window shows it |
| Font | Menlo 12 | Menlo 12 kept: the view is fixed-width columns (CHARS 61 at 7.0 px); Open Sans would break alignment and click mapping | - |

Reversible: `td_debug_panel {style:'plain'}` reconnects `view_bg` and points `fps_graph` back at `fps_chop`; the zk_
ops then sit unpulled (0 cooks). T-70: the skin closes the window first and reopens it 10 frames later; it destroys
nothing that a window or pane shows (only a new GLSL TOP's auto-docked DATs, and the first skin's `zk_graph_tex`).

## Measured (main TD, window OPEN, pane on /project1/lab, lab mostly parked; td_watch 10 s + rt.stats)

| | fps (td_watch avg / min) | real fps 2 s | slow frames 2 s | rt tick ms | panel cook ms/s |
|---|---|---|---|---|---|
| Before (plain) | 59.76 / 54.7 | 60.2 | 1 | 0.43 | 2.01 |
| Skin v1 (CHOP to TOP) | 59.83 / 57.2 | - | - | - | 4.26 (zk_graph_tex 0.66 ms GPU a cook) |
| Skin v2 (texture buffer, shipped) | 59.91 / 58.2 | 60.0 | 0 | 0.41 | 1.34 |

The AU_features lane was cooking during "before" (its rows fill the top list), so before/after load is not identical;
the point is the window-open fps stays 60 and the skin adds no per-frame work. Captures: window before/after
(scratchpad, not kept). Tests: `test/test_zkit_debug.py` (bands vs the real slots, shaders static/clamped, fake-TD
style run idempotent, old CHOP to TOP removed). Scratch TD first for the window step (T-79/T-83).
