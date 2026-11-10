# zctl (`/project1/lab/ZC_control_surface`)

Parameter control surface: bind any op's parameters as 0-1 knobs, store / recall / morph / randomise presets, a
control-in hook for MIDI (or any CHOP), and an Out CHOP with one channel per knob. Clean-room design from
`docs/research/BE_rudiment_zerror.md` (v1 scope). Built and checked on TD 2025.31550.

## Build / rebuild
```python
# through td_exec
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/zctl.py').read(), ns)
ns['build']('/project1/lab')        # demo=False leaves out the demo target ops
```
Idempotent and T-70 safe: a rebuild updates the COMP **in place** (ops reused by name, no op or custom page destroyed;
binds, presets, knob/lock values and settings stay; code DATs refreshed from `builders/zctl_logic.py` +
`builders/zctl_ext.py`). Its own window is closed first and reopened after if it was open. Offline tests:
`python3 -I -m unittest discover -s test -p 'test_zctl.py'`.

## Use (all from the COMP's pars, or Python on the promoted extension)
- **Bind:** `Bindpath` (op, relative to the COMP or absolute) + `Bindpar` (`tx ty, period`, wildcards ok) -> `Bind selected`.
  With `Bindpath` empty, the ops selected in a network pane are bound. Python: `op(comp).Bind('/path/op', 'tx ty')`.
  Kinds: float / int (normMin..normMax, a flat range falls back to 0..1), toggle (>= 0.5 = on), menu (index spread over 0-1).
  Each bind makes `Knob<n>` + `Lock<n>` on page Knobs. `Unbind` (`Knob id`), `Clear binds`; a removed knob's values
  leave the presets too.
- **Presets:** `Store` (slot `Preset slot`, 0 = new), `Store as new`, `Recall` (morphs over `Morph time` with
  `Morph curve` linear / ease / smooth; 0 s = jump), `Delete preset`, `Stop morph`. A knob moved by hand mid-morph
  drops out of that morph. Presets = JSON {knob: 0-1} in the `presets` table.
- **Randomise:** `Random amount` 0 = unchanged, 1 = uniform 0-1; in between pulls toward a random point; locked
  knobs are skipped (and never shift the other knobs' draws). Morphs like a recall.
- **Control in (MIDI hook):** wire any CHOP into the COMP's input: a channel named `Knob3`, `k3`, `3` or a bind's
  `src` column value (e.g. `ch1c21` from a MIDI mapper) sets that knob to its value (0-1; use `cc_to_unit` for raw CC).
  No MIDI device code inside; `jazib_midi` (td_midi_*) can also write `Knob<n>` directly.
- **Out:** `out_values` CHOP, one channel per knob (0-1). Targets are written with `par.val` (constant mode only;
  a non-constant target sets `Lasterror`). `Active` off = knobs move, targets are left alone.
- **Controls:** `Open controls` pulse -> own window (autoUI of pages Zctl + Knobs).

## Network (stages)
Controls (panel + window) | Data (binds, binds_watch, presets, zctl_logic, zctl_ext) | Control in (in_ctrl, ctrl_exec)
| Morph + apply (actions_exec, morph_tick (active only while morphing), apply_exec) | Output (knob_vals -> out_values)
| Demo targets (test_const, test_noise 1080x1920).

## T-70 safety (crash-safe panel refills)
- autoUI's `GenerateUI` destroys every child of the panel it fills. `ZCtl.RebuildUI` therefore runs in phases:
  now = window closed, panes inside the panel sent to the COMP; +2 frames = panel tile off, autoUI refill;
  +2 frames = tile on, window reopened if it was open. Several binds in a row queue one refill.
- `Unbind` / `Clear binds` close the window before the Knob pars its widgets show are destroyed.

## Measured (TD 2025.31550, 6 binds, 26 Oct 2026)
- Recall P1 -> P2, 2 s linear, sampled in TD: t 0.49 s Knob3 0.2946 (expected 0.296), 0.99 s 0.4946 (0.495),
  1.99 s 0.8946, 2.49 s 0.9 + morph done; target `period` = 2 x knob throughout.
- Randomise 0 = identical; 1 = all in 0-1, locked Knob2 held at 0.5. Menu bind (noiseTOP type, 12 entries):
  knob 0.5 -> index 6, 1.0 -> 11. Control in: a CHOP channel `k4` = 0.66 -> Knob4 0.66.
- Idle: 0 cooks inside the COMP over 60 frames (window open). During a morph: Tick 0.14 ms (after the binds cache;
  1.1 ms before), ApplyAll of 6 = 0.44 ms; the panel widgets cook ~12 of 30 frames, ~1.8 ms/frame est.
- Rebuild with the window open: same op ids, window closed and reopened, 31 widgets, no errors.

## Left (v2+)
Real MIDI device learn / feedback (use td_midi_*), knob widgets (zkit) instead of autoUI sliders, preset bar, XY,
layouts, expression links, 88-bind perf run (not measured), save/reload .tox round trip.
