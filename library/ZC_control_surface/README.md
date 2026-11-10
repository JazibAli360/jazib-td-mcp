# ZC_control_surface

> zctl (`/project1/lab/ZC_control_surface`)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:31 from `/project1/lab/ZC_control_surface`

Parameter control surface: bind any op's parameters as 0-1 knobs, store / recall / morph / randomise presets, a
control-in hook for MIDI (or any CHOP), and an Out CHOP with one channel per knob. Clean-room design from
`docs/research/BE_rudiment_zerror.md` (v1 scope). Built and checked on TD 2025.31550.

Build doc: `docs/builds/zctl.md`

## Inputs / outputs

- in `in_ctrl` (inCHOP)
- out `out_values` (outCHOP)

## Custom parameters

### Zctl

| name | label | style | default | value |
|---|---|---|---|---|
| Active | Active (write targets) | Toggle | True | True |
| Morphtime | Morph time (s) | Float | 1.0 | 1.0 |
| Morphcurve | Morph curve | Menu | linear | linear |
| Activepreset | Preset slot | Int | 0 | 1 |
| Store | Store (slot; 0 = new) | Pulse | False | False |
| Storenew | Store as new | Pulse | False | False |
| Recall | Recall (morph) | Pulse | False | False |
| Delete | Delete preset | Pulse | False | False |
| Stopmorph | Stop morph | Pulse | False | False |
| Randamount | Random amount | Float | 0.5 | 0.5 |
| Randomize | Randomize | Pulse | False | False |
| Bindpath | Bind op (or selection) | Str |  |  |
| Bindpar | Bind pars (e.g. tx ty, *) | Str |  |  |
| Bindselected | Bind selected | Pulse | False | False |
| Unbindknob | Knob id | Int | 0 | 0 |
| Unbind | Unbind knob | Pulse | False | False |
| Clearbinds | Clear binds | Pulse | False | False |
| Opencontrols | Open controls | Pulse | False | False |

### State

| name | label | style | default | value |
|---|---|---|---|---|
| Nbinds | Binds | Int | 0 | 6 |
| Npresets | Presets | Int | 0 | 2 |
| Morphing | Morphing | Toggle | False | False |
| Lasterror | Last error | Str |  |  |

### Knobs

| name | label | style | default | value |
|---|---|---|---|---|
| Knob1 | test_const const0value | Float | 0.0 | 1.0 |
| Lock1 |     lock (randomize skips) | Toggle | False | False |
| Knob2 | test_const const1value | Float | 0.0 | 0.5 |
| Lock2 |     lock (randomize skips) | Toggle | False | False |
| Knob3 | test_noise Period | Float | 0.0 | 0.9 |
| Lock3 |     lock (randomize skips) | Toggle | False | False |
| Knob4 | test_noise Amplitude | Float | 0.0 | 1.0 |
| Lock4 |     lock (randomize skips) | Toggle | False | False |
| Knob5 | test_noise Monochrome | Float | 0.0 | 1.0 |
| Lock5 |     lock (randomize skips) | Toggle | False | False |
| Knob6 | test_noise Type | Float | 0.0 | 0.999676 |
| Lock6 |     lock (randomize skips) | Toggle | False | False |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 56 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |

## Perf

cook 20.309 ms (CPU 20.309 / GPU 0.0) summed over the 71 ops that cooked in the last frame at export (0 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "ZC_control_surface", "parent": "/project1/lab"}` (lands parked)
