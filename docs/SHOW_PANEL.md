# Show control framework (`/project1/show`, built by `tools/build_show_panel.py`)

User decisions (16 Oct 2026): each look has **its own specific controls**; framework first; sliders/buttons now,
MIDI later; every look 1080x1920. Research behind it: `docs/research/H_control_panel.md`.

| COMP | What |
|---|---|
| `state` | Page **Show**: Master (0-1), Blackout, Look (menu of `looks/*`), Fade (s), Refresh look list (pulse). The single source of truth. |
| `looks/<name>` | One COMP per look. **Its controls are its own custom pars (page Controls).** Output: Null TOP `out`, 1080x1920. `test_a` (radial ramp: Phase, Period) and `test_b` (noise: Speed, Amount) are plain test looks; delete them once real looks exist. |
| `mixer` | `sel_a`/`sel_b` slots → `cross` (xf lagged by Fade) → `master` (Level: Master × (1 − Blackout)) → `null_out`. `look_switch` (Parameter Execute on state.Look) loads the new look into the idle slot and fades to it. Only the looks in the two slots cook. **Syphon/NDI Out goes after `null_out`.** |
| `panel` + `ui_window` | **Operator panel (26 Oct, replaces the old Parameter-COMP `ui`):** Basic Widgets built by autoUI, bound two-way. `global_w` = SHOW section (Master, Blackout, Look, Fade, Refresh) on `state`; `look_w` = LOOK section for the live look, rebuilt by `look_follow` (Parameter Execute on state.Look) -> `look_panel.Rebuild()`. `ui_window` opens it as "PF26 Show Panel" (600x900). |
| `tools` | Shipped palette tools used by `panel`: `basicWidgets` (package 2.2.6, shortcut `TDBasicWidgets`, widgets clone from it) and `autoUI` (0.4.7). Never re-flow or edit inside (T-50). |
| `midi_map` | Empty table `device, msg, number, channel, target, par, min, max, pickup`: the MIDImix / MPK Mini MK3 get rows later, no rebuild. |

## Add a look
1. Research first (someone probably made it). 2. `td_create` a baseCOMP in `/project1/show/looks/<name>`; add its
controls with `td_custom_pars` on page `Controls`; build inside it (generators default to 1080x1920); end in a Null TOP
named `out`. 3. Pulse `state` → Refresh look list. 4. Pick it in Look: it fades in over Fade seconds.

## Verified live (16 Oct, TD 2025.31550)
Build clean (td_errors empty), every COMP arranged + check ok; Look test_a → test_b crossfades (xf rising, sel_b loaded,
look_ctrl follows the live look); output 1080x1920; Blackout → 0, Master 0.5 → 0.5. Pull model: with nothing viewing
`null_out` the fade only advances when something cooks it; the Syphon/NDI Out node pulls every frame at the show.

Panel (26 Oct, TD 2025.31550): Basic Widgets + autoUI done (T-52); checked live: widget -> state, state -> widget, look widget -> look par, look section follows the Look switch. COMP tiles: `mixer` shows `null_out`, `looks` the live look (Common `opviewer`). `tools/build_show_panel.py` still builds the old `ui`; rebuild by hand from this section until it is updated. UI Engine skipped (`docs/research/I_ui_engine.md`).
