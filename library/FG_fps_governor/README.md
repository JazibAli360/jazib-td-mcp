# FG_fps_governor

> FG_fps_governor: hold 60 fps, any COMP can follow (28 Oct 2026, TD 2025.31550)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:33 from `/project1/lab/FG_fps_governor`

`/project1/lab/FG_fps_governor`: a small generic controller. It measures the real frame rate, keeps a quality step
with hysteresis and publishes it on `out1`. **It never writes another COMP's pars**: consumers read it, so manual
control always wins (a consumer that is not bound, or whose own switch is off, ignores it). `Active` is **off** by
default.

Files: `builders/fps_gov.py` (builder), `builders/fps_gov_logic.py` (pure logic, copied into `fg_logic`),
`test/test_fps_gov.py` (offline, 18 tests: `python3 -I -m unittest discover -s test -p 'test_fps_gov.py'`).
Build / refresh in TD: `ns = dict(globals()); exec(open('<repo>/builders/fps_gov.py').read(), ns); ns['build']('/project1/lab')`.

Build doc: `docs/builds/fps_governor.md`

## Inputs / outputs

- out `out1` (outCHOP)

## Custom parameters

### Governor

| name | label | style | default | value |
|---|---|---|---|---|
| Active | Active | Toggle | False | False |
| Target | Target fps | Float | 60.0 | 60.0 |
| Downafter | Down after frames | Int | 30 | 30 |
| Upafter | Up after frames | Int | 300 | 300 |
| Steps | Steps | Int | 5 | 5 |
| Floor | Floor quality | Float | 0.25 | 0.25 |
| Upmargin | Up headroom ms | Float | 3.0 | 3.0 |
| Reset | Reset | Pulse | False | False |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Opencontrols | Open controls | Pulse | False | False |
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 56 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |

## Perf

cook 11.979 ms (CPU 11.979 / GPU 0.0) summed over the 56 ops that cooked in the last frame at export (0 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FG_fps_governor", "parent": "/project1/lab"}` (lands parked)
