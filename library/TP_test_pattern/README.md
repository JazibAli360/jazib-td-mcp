# TP_test_pattern

> test_pattern: TP_test_pattern test patterns + sync checks (26 Oct 2026, TD 2025.31550)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:31 from `/project1/lab/TP_test_pattern`

`/project1/lab/TP_test_pattern`. A self-contained generator: no input, `out1` TOP only. Spec/recipe:
`docs/research/BB_test_patterns_sync.md` section 5 (our own clean-room design; ideas from Mallin's Wallin Pattern
Generator and Video sync test wheel, whose files were never obtained, licence unstated). Pattern names follow
`stagelab/guides/JZB_Slice_Test.md`, so the TD pattern and the Arena FFGL one use the same words.

Exact: a lit pixel is exactly the **Level** code on the **Channel** components (8-bit RGBA; Gradient 16-bit float),
whole-pixel lines, deterministic (no seed). Only the cabinet numbers, slice labels and counter text are anti-aliased.

Build doc: `docs/builds/test_pattern.md`

## Inputs / outputs

- out `out1` (outTOP) 1920x1080

## Custom parameters

### Pattern

| name | label | style | default | value |
|---|---|---|---|---|
| Pattern | Pattern | Menu | cabinets | gradient |
| Channel | Channel | Menu | white | red |
| Level | Level (8-bit code) | Int | 255 | 255 |
| Area | Area | Menu | slices | slices |
| Walk | Walk | Menu | across | across |
| Speed | Walk speed (steps/s) | Float | 10.0 | 19.5 |
| Resetwalk | Reset walk | Pulse | False | False |
| Linewidth | Line width px | Int | 2 | 4 |
| Cell | Cell LED px (0 = cabinet) | Float | 0.0 | 433.0 |
| Steps | Ramp steps | Int | 16 | 256 |
| Showfaces | Show face outlines | Toggle | False | False |

### Cabinet

| name | label | style | default | value |
|---|---|---|---|---|
| Respreset | Resolution preset | Menu | 1920x1080 | 1920x1080 |
| Resx | Width px | Int | 1920 | 1920 |
| Resy | Height px | Int | 1080 | 1080 |
| Nativewidth | Native LED width (0 = 1:1) | Float | 0.0 | 0.0 |
| Cabw | Cabinet width LED px | Float | 128.0 | 128.0 |
| Cabh | Cabinet height LED px | Float | 128.0 | 128.0 |

### Sync

| name | label | style | default | value |
|---|---|---|---|---|
| Counter | Frame counter | Toggle | False | True |
| Counterx | Counter x px | Int | 16 | 16 |
| Countery | Counter y px | Int | 16 | 16 |
| Countersize | Counter size px | Int | 24 | 24 |
| Wheel | Sync wheel | Toggle | False | False |
| Wheelu | Wheel x (0..1) | Float | 0.5 | 0.5 |
| Wheelv | Wheel y (0..1) | Float | 0.5 | 0.5 |
| Wheelsize | Wheel size px | Float | 360.0 | 360.0 |
| Flash | Flash frame | Toggle | False | False |
| Flashevery | Flash every N frames | Int | 60 | 60 |
| Blip | Audio blip (speakers) | Toggle | False | False |
| Blipfreq | Blip Hz | Float | 1000.0 | 1000.0 |
| Bliplen | Blip frames | Int | 1 | 1 |
| Blipvol | Blip volume | Float | 0.5 | 0.5 |
| Fps | Counter fps | Float | 60.0 | 60.0 |

### Layout

| name | label | style | default | value |
|---|---|---|---|---|
| Facestable | Face table DAT (empty = faces) | DAT |  |  |

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
| Zkm1 | Detail | Float | 0.0 | 0.14 |
| Zkm2 | Sync size | Float | 0.0 | 0.33 |

## Perf

cook 36.68 ms (CPU 36.68 / GPU 0.434) summed over the 4 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "TP_test_pattern", "parent": "/project1/lab"}` (lands parked)
