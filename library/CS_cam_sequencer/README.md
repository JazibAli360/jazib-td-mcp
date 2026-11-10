# CS_cam_sequencer

> CS_cam_sequencer v2: a Camera COMP that eases between camera presets (how-to)

v2.0.0 - TD 2025.31550 - exported 2026-10-29 00:09:33 from `/project1/lab/CS_cam_sequencer`

TD 2025.31550 (macOS, Rosetta). Clean-room: built from the public description and videos of Function Store's
CamSequencer only (research and sources: `docs/research/CS_camsequencer.md`); no file, code or asset of the product was
used. Builder `builders/cam_seq.py` (v2.0.0), logic `builders/cam_seq_logic.py` (tests `test/test_cam_seq.py`),
TD runtime `builders/cam_seq_rt.py`, v1 upgrade `builders/cam_seq_migrate.py`. Library: `library/CS_cam_sequencer/`.

**v2 (28 Oct 2026) replaces v1** (a Base COMP with hidden `cam_edit` / `cam_out` cameras). The user: "camsequencer
originally has a camera in comp that u can move around ... i can create and drop it in different comps with existing
3d scenes and have it to animate it". So the COMP now IS the camera, as in the original.

Build doc: `docs/builds/cs_cam_sequencer.md`

## Inputs / outputs

- in `in1` (inCHOP)
- out `out1` (outCHOP)

## Custom parameters

### Seq

| name | label | style | default | value |
|---|---|---|---|---|
| Append | Append | Pulse | False | False |
| Replace | Replace | Pulse | False | False |
| Insert | Insert | Pulse | False | False |
| Remove | Remove | Pulse | False | False |
| Init | Init | Pulse | False | False |
| Override | Ease Override | Toggle | False | False |
| Easing | Easing | Menu | inOutSine | inOutSine |
| Splineinterp | Spline Interpolation | Toggle | False | False |
| Select | Select | Float | 0.0 | 0.0 |
| Length | Length | Int | 0 | 4 |
| Bind | Bind | Toggle | True | True |

### Presets

| name | label | style | default | value |
|---|---|---|---|---|
| Opencampresets | Open Cam Presets | Pulse | False | False |
| Openlookatpresets | Open Lookat Presets | Pulse | False | False |

### About

| name | label | style | default | value |
|---|---|---|---|---|
| Help | About | Str | A Camera COMP that stores camera positions as presets and eases between them. Drop it in, set your Render TOP Camera to it, activate its viewer and navigate, then Init / Append. Set Xform > Look At to a Null to sequence its transform too. Drive Select (fraction = blend). Bind off = edit freely. | A Camera COMP that stores camera positions as presets and eases between them. Drop it in, set your Render TOP Camera to it, activate its viewer and navigate, then Init / Append. Set Xform > Look At to a Null to sequence its transform too. Drive Select (fraction = blend). Bind off = edit freely. |
| Version | Version | Str | 2.0.0 | 2.0.0 |
| Docs | Docs | Str | jazib-td-mcp docs/builds/cs_cam_sequencer.md | jazib-td-mcp docs/builds/cs_cam_sequencer.md |
| Status | Status | Str |  | Bind on: the sequencer owns the camera pars |

### Play

| name | label | style | default | value |
|---|---|---|---|---|
| Playmode | Playmode | Menu | manual | manual |
| Loopmode | Loopmode | Menu | loop | loop |
| Quant | Quantise cuts (beats) | Float | 4.0 | 4.0 |
| Defaulthold | Hold (beats) | Float | 8.0 | 8.0 |
| Tdur | Transition (beats) | Float | 2.0 | 2.0 |
| Trans | Transition | Menu | ease | ease |
| Minhold | Random min hold | Float | 4.0 | 4.0 |
| Maxhold | Random max hold | Float | 12.0 | 12.0 |
| Seed | Random seed | Int | 1 | 1 |
| Trignext | Next | Pulse | False | False |
| Trigprev | Previous | Pulse | False | False |
| Trigrandom | Random | Pulse | False | False |
| Trigcut | Cut to selected | Pulse | False | False |
| Gotopreset | Go to preset (any to any) | StrMenu |  |  |
| Go | Go (again) | Pulse | False | False |
| Gotoblend | Go-to blend | Menu | arc | arc |
| Gototime | Go-to time (beats) | Float | 1.0 | 1.0 |
| Gotoease | Go-to ease | Menu | inOutSine | inOutSine |
| Splinetension | Spline amount | Float | 1.0 | 1.0 |
| Shortrot | Shortest rotation | Toggle | False | False |
| Lag | Select lag (s) | Float | 0.0 | 0.0 |
| Customease | Custom ease CHOP | CHOP |  |  |
| Reset | Reset playhead | Pulse | False | False |

### Clock

| name | label | style | default | value |
|---|---|---|---|---|
| Clockmode | Clockmode | Menu | internal | internal |
| Bpm | BPM (internal / fallback) | Float | 120.0 | 120.0 |
| Seek | Seek (beats, manual clock) | Float | 0.0 | 0.0 |
| Beatsperbar | Beats per bar | Int | 4 | 4 |
| Auop | AU_features COMP (optional) | COMP |  |  |
| Tlop | TL_timeline COMP (optional) | COMP |  |  |

### Shake

| name | label | style | default | value |
|---|---|---|---|---|
| Shakeprofile | Shakeprofile | Menu | off | off |
| Shakeamount | Shake amount | Float | 1.0 | 1.0 |
| Shakepos | Position scale | Float | 1.0 | 1.0 |
| Shakerot | Rotation scale | Float | 1.0 | 1.0 |
| Shakespeed | Speed | Float | 1.0 | 1.0 |
| Shakeseed | Seed | Int | 0 | 0 |
| Shakebeat | Beat kick | Float | 0.0 | 0.0 |
| Shakeperlens | Scale by FOV | Toggle | False | False |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Targetmode | Targetmode | Menu | presets | presets |
| Targetop | Global target op | Object |  |  |
| Effop | Effectors COMP (optional) | COMP |  |  |
| Targeteff | Global target effector | StrMenu |   |   |
| Lookdamp | Look damping (s) | Float | 0.0 | 0.0 |
| Frame | Frame the look point | Toggle | False | False |
| Frameradius | Frame radius | Float | 1.0 | 1.0 |
| Framepad | Frame padding | Float | 0.2 | 0.2 |
| Roll | Roll offset | Float | 0.0 | 0.0 |
| Fovoffset | FOV offset | Float | 0.0 | 0.0 |

### Output

| name | label | style | default | value |
|---|---|---|---|---|
| Resx | Frame width (framing aspect) | Int | 1080 | 1080 |
| Resy | Frame height (framing aspect) | Int | 1920 | 1920 |
| Outchop | Out CHOP channels | Str | out1: cs_tx..cs_fov cs_la_tx..cs_la_pz cs_select cs_preset cs_progress cs_blend cs_cut cs_goto cs_beats cs_bar cs_shake cs_dist cs_haslook cs_ver | out1: cs_tx..cs_fov cs_la_tx..cs_la_pz cs_select cs_preset cs_progress cs_blend cs_cut cs_goto cs_beats cs_bar cs_shake cs_dist cs_haslook cs_ver |
| Opencontrols | Open controls (zkit, optional) | Pulse | False | False |

## Perf

cook 4.351 ms (CPU 4.351 / GPU 1.029) summed over the 32 ops that cooked in the last frame at export (0 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "CS_cam_sequencer", "parent": "/project1/lab"}` (lands parked)
