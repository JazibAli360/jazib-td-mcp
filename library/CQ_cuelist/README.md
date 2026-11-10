# CQ_cuelist

> CQ_cuelist — cue list + timecode show control (v1)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:05 from `/project1/lab/CQ_cuelist`

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

Spec: `docs/research/BQ_show_control_timecode.md` §3 (clean-room). COMP `/project1/lab/CQ_cuelist`, TD 2025.31550.
Builder `builders/cuelist.py` (`build(parent_path, panel=True, reset_cues=False)`, idempotent, keeps the cue table),
pure logic `builders/cuelist_logic.py` (copied into `cq_logic`), TD runtime in the generated `cq_rt` Text DAT,
offline tests `test/test_cuelist.py`.

```python
ns = dict(globals()); exec(open('<repo>/builders/cuelist.py').read(), ns); ns['build']('/project1/lab')
```

Build doc: `docs/builds/cuelist.md`

## Inputs / outputs

- in `in1` (inCHOP)
- in `in2` (inDAT)
- out `out1` (outCHOP)
- out `out2` (outDAT)

## Custom parameters

### Transport

| name | label | style | default | value |
|---|---|---|---|---|
| Go | GO | Pulse | False | False |
| Goback | Back | Pulse | False | False |
| Standbyprev | Standby up | Pulse | False | False |
| Standbynext | Standby down | Pulse | False | False |
| Gotocue | Goto cue (name/num) | Str |  |  |
| Stop | Stop fades | Pulse | False | False |
| Pause | Pause fades | Toggle | False | False |
| Reset | Reset standby | Pulse | False | False |
| Rate | Fade rate | Float | 1.0 | 1.0 |
| Queuemode | GO during fade | Menu | queue | queue |

### Clock

| name | label | style | default | value |
|---|---|---|---|---|
| Clocksrc | Clock source | Menu | internal | internal |
| Clockplay | Internal play | Toggle | False | False |
| Locate | Locate to | Str | 00:00:00:00 | 00:00:00:00 |
| Dolocate | Locate | Pulse | False | False |
| Manualtc | Manual TC | Str |  |  |
| Tcchop | TC CHOP (else In1) | CHOP |  |  |
| Tcrate | TC rate | Menu | 25 | 25 |
| Tcoffset | TC offset | Str | 00:00:00:00 | 00:00:00:00 |
| Chase | Chase (lock) | Toggle | True | True |
| Chaselag | Chase lag s | Float | 0.0 | 0.0 |
| Freewheel | Freewheel s | Float | 2.0 | 2.0 |
| Lockwindow | Lock window fr | Float | 3.0 | 3.0 |
| Jumpthreshold | Jump threshold s | Float | 1.0 | 1.0 |

### Cues

| name | label | style | default | value |
|---|---|---|---|---|
| Cuetable | Cue table (else cues) | DAT |  |  |
| Reloadcues | Reload cues | Pulse | False | False |
| Tracking | Tracking | Toggle | True | True |
| Autofollow | Autofollow | Toggle | True | True |
| Defaultfade | Default fade s | Float | 0.0 | 0.0 |
| Defaultcurve | Defaultcurve | Menu | linear | linear |
| Presetkit | ZC preset kit | COMP |  |  |
| Timeline | TL timeline | COMP |  |  |

### Targets

| name | label | style | default | value |
|---|---|---|---|---|
| Allowtl | Allowtl | Toggle | True | True |
| Allowzc | Allowzc | Toggle | True | True |
| Allowosc | Allowosc | Toggle | False | False |
| Allowarena | Allowarena | Toggle | False | False |
| Oscdest | Oscdest | Str | 127.0.0.1 | 127.0.0.1 |
| Oscport | Oscport | Int | 7000 | 7000 |
| Arenasend | Arena send (else dry) | Toggle | False | False |
| Oscmap | Oscmap | DAT |  |  |

### Log

| name | label | style | default | value |
|---|---|---|---|---|
| Logfile | Logfile | Str | logs/cq_<yyyymmdd>.csv | logs/cq_<yyyymmdd>.csv |
| Logon | Logon | Toggle | True | True |
| Logmax | Logmax | Int | 500 | 500 |
| Clearlog | Clearlog | Pulse | False | False |

### Status

| name | label | style | default | value |
|---|---|---|---|---|
| Standby | Standby | Str |  | 1 Preset |
| Running | Running | Str |  |  |
| Fadepct | Fadepct | Float | 100.0 | 100.0 |
| Tc | Tc | Str |  | 00:00:00:00 |
| Clockstate | Clockstate | Str |  | free |
| Lastevent | Lastevent | Str |  | fade_end par:/project1/show_rig:L1opacity |
| Lasterror | Lasterror | Str |  |  |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Opencontrols | Open controls | Pulse | False | False |
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 56 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |
| Zkm1 | Snap | Float | 0.0 | 1.0 |
| Zkm2 | Tolerance | Float | 0.0 | 0.35 |

## Perf

cook 18.47 ms (CPU 18.47 / GPU 0.0) summed over the 66 ops that cooked in the last frame at export (0 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "CQ_cuelist", "parent": "/project1/lab"}` (lands parked)
