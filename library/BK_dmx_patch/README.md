# BK_dmx_patch

> dmx_patch: BK_dmx_patch fixture patch sheet + stage plot + previs + aim helper (26 Oct 2026, TD 2025.31550)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:07:51 from `/project1/lab/BK_dmx_patch`

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60) (BK_dmx_patch).

`/project1/lab/BK_dmx_patch`. The second COMP of `docs/research/BK_dmx_artnet_sacn.md` (sections 2.8, 3.4-3.6 and the
"Previz of fixtures" row of section 7). Clean-room, our own code. It sits next to **BK_dmx_out** (`builders/dmx_out.py`)
and only **reads** it: BK_dmx_out's `patch` / `pixels` / `profiles_json` tables and its `out3` universes CHOP
(`u<flat>` x 512). The add / check / import / pixel-map pulses stay on BK_dmx_out (Patch page); this COMP adds what
it lacks: where each fixture hangs, what it is doing (previs from the bytes on the wire), a slot ownership map, a
printable patch sheet and moving-head aiming. **No limits** (user rule): no brightness cap, no warnings.

**Status: live-verified v1 on 31550 (26 Oct, T-90).** P1-P9, P11-P14 pass with the exact numbers below; P10 by eye (2 tiles drawn, layout 5 x 4 for Mapcount 16, clash fixture at 0.10 -> Conflicts 3 = slots, not fixtures). Fixes found live: '.' in CHOP names becomes '_' (out3 reads `mh1_pan`; BK_dmx_out resolve_inputs accepts both), tube rad1/rad2 swapped, window reopened after a rebuild, stage cells 6 decimals. Cost: state 0.6 ms, render 2.4-3.5 ms CPU + 0.36 ms GPU (over the 1 ms target; aa/res is the lever). Captures: front previs live + Pattern full, address map.

Build doc: `docs/builds/dmx_patch.md`

## Inputs / outputs

- out `out1` (outTOP) 1080x1920
- out `out2` (outTOP) 1024x768
- out `out3` (outCHOP)

## Custom parameters

### Source

| name | label | style | default | value |
|---|---|---|---|---|
| Dmxcomp | DMX out COMP | COMP | /project1/lab/BK_dmx_out | /project1/lab/BK_dmx_out |
| Univchop | Universes CHOP (blank = Dmxcomp out3) | CHOP |  |  |
| Chanfmt | Channel name ({u} = universe) | Str | u{u} | u{u} |
| Autosync | Auto sync stage | Toggle | True | True |
| Syncpatch | Sync from patch | Pulse | False | False |
| Prune | Prune stale rows | Pulse | False | False |
| Checkpatch | Check patch + stage | Pulse | False | False |
| Fixtures | Fixtures (read) | Int | 0 | 7 |
| Pixelsshown | Pixels shown (read) | Int | 0 | 50 |
| Conflicts | Slot conflicts (read) | Int | 0 | 0 |
| Statems | Python ms (read) | Float | 0.0 | 1.157 |

### Stage

| name | label | style | default | value |
|---|---|---|---|---|
| Arrange | Arrange | Menu | line | line |
| Arrangeset | Fixtures (pattern) | Str | * | * |
| Spanx | Span m | Float | 12.0 | 12.0 |
| Height | Height m | Float | 6.0 | 6.0 |
| Depth | Depth z m | Float | 0.0 | 0.0 |
| Curve | Arc deg | Float | 60.0 | 60.0 |
| Cols | Grid columns | Int | 8 | 8 |
| Rowgap | Row gap m | Float | 1.0 | 1.0 |
| Hang | Hanging (rx 180) | Toggle | True | True |
| Applyarrange | Arrange | Pulse | False | False |
| Wallx | Pixel wall x | Float | 0.0 | 0.0 |
| Wally | Pixel wall y | Float | 3.0 | 3.0 |
| Wallz | Pixel wall z | Float | -1.0 | -1.0 |
| Wallw | Pixel wall w | Float | 8.0 | 8.0 |
| Wallh | Pixel wall h | Float | 4.5 | 4.5 |
| Pixmax | Pixels drawn (max) | Int | 4096 | 4096 |

### View

| name | label | style | default | value |
|---|---|---|---|---|
| View | View | Menu | front | front |
| Fit | Fit view | Pulse | False | False |
| Centerx | Centre x | Float | 0.0 | 0.0 |
| Centery | Centre y | Float | 3.0 | 4.5 |
| Centerz | Centre z | Float | 0.0 | -0.5 |
| Viewsize | View size m | Float | 16.0 | 13.8 |
| Orbit | Orbit deg | Float | 30.0 | 30.0 |
| Elev | Elevation deg | Float | 20.0 | 20.0 |
| Fov | FOV deg | Float | 40.0 | 40.0 |
| Beams | Beams | Toggle | True | True |
| Beamlen | Beam length m | Float | 8.0 | 8.0 |
| Beamangle | Beam angle deg | Float | 15.0 | 15.0 |
| Beamgain | Beam gain | Float | 0.5 | 0.5 |
| Bodysize | Fixture size m | Float | 0.25 | 0.25 |
| Pixsize | Pixel size m | Float | 0.06 | 0.06 |
| Pixgain | Pixel gain | Float | 1.0 | 1.0 |
| Mingrey | Dark fixture grey | Float | 0.12 | 0.12 |
| Grid | Floor grid | Toggle | True | True |
| Highlight | Highlight (pattern) | Str |  |  |
| Resw | Width | Int | 1080 | 1080 |
| Resh | Height | Int | 1920 | 1920 |

### Aim

| name | label | style | default | value |
|---|---|---|---|---|
| Aimon | Aim on (out3) | Toggle | False | True |
| Aimset | Fixtures (pattern) | Str | * | * |
| Targetx | Target x | Float | 0.0 | 0.0 |
| Targety | Target y | Float | 0.0 | 0.0 |
| Targetz | Target z | Float | 4.0 | 4.0 |
| Targetchop | Target CHOP (tx ty tz) | CHOP |  |  |
| Calfixture | Calibrate fixture | Str |  | mh1 |
| Calpan | Measured pan 0..1 | Float | 0.5 | 0.52 |
| Caltilt | Measured tilt 0..1 | Float | 0.5 | 0.61 |
| Calibrate | Calibrate (at target) | Pulse | False | False |
| Aimmissed | Out of range (read) | Int | 0 | 0 |

### Sheet

| name | label | style | default | value |
|---|---|---|---|---|
| Mapmode | Map mode | Menu | ownervalue | ownervalue |
| Mapfirst | First row | Int | 0 | 0 |
| Mapcount | Rows shown | Int | 16 | 16 |
| Mapcell | Px per slot | Int | 6 | 6 |
| Mapw | Map width | Int | 1024 | 1024 |
| Maph | Map height | Int | 768 | 768 |
| Sheetname | Sheet name | Str | dmx_patch | dmx_patch |
| Sheetdir | Sheet folder | Folder | ~/Documents/StageLab_PrismFest/jazib-td-mcp/output/dmx | ~/Documents/StageLab_PrismFest/jazib-td-mcp/output/dmx |
| Exportsheet | Export sheet (csv + md) | Pulse | False | False |

### Controls

| name | label | style | default | value |
|---|---|---|---|---|
| Resetdefaults | Reset defaults | Pulse | False | False |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Opencontrols | Open controls | Pulse | False | False |
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 52 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |
| Zkm1 | Beams | Float | 0.0 | 0.5 |
| Zkm2 | Pixels | Float | 0.0 | 0.5 |
| Zkm3 | Frame | Float | 0.0 | 0.5 |

## Perf

cook 68.975 ms (CPU 68.975 / GPU 0.062) summed over the 2 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "BK_dmx_patch", "parent": "/project1/lab"}` (lands parked)
