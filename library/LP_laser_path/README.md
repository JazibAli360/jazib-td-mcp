# LP_laser_path

> laser_path: LP_laser_path laser path generator + beam preview (live v1 in main, 26 Oct 2026, no laser hardware)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:00 from `/project1/lab/LP_laser_path`

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

`/project1/lab/LP_laser_path`. Spec: `docs/research/BM_lasers.md` section 4 (clean-room, our own code). Any source
(test pattern / SOP / CHOP / POP / TOP trace / Text / audio scope) -> laser sample stream (`x y r g b i flag`) through
either the built-in **Laser CHOP** (Engine = Native, default) or our **numpy engine** (Engine = Own: draw order,
resample, corner dwell, 5-phase blanking, colour delay, frame budget), plus a beam-simulation preview and a stats table.
**No device output here** (that is LO_laser_out, spec section 5) and **no limits** (operator decides; interlock,
shutter and e-stop are the operator's). Nothing is routed to audio output.

**Status: BUILT LIVE v1 (26 Oct 2026, TD 2025.31550, Rosetta; no laser hardware).** `/project1/lab/LP_laser_path`,
backup `output/backups/LP_laser_path_build.tox`. Live facts: LEARNINGS T-85. Results (spec 4.9):

Build doc: `docs/builds/laser_path.md`

## Inputs / outputs

- in `in1` (inSOP)
- in `in2` (inCHOP)
- in `in3` (inTOP) 128x128
- in `in4` (inPOP)
- out `out1` (outCHOP)
- out `out2` (outTOP) 1080x1080
- out `out3` (outDAT)

## Custom parameters

### Source

| name | label | style | default | value |
|---|---|---|---|---|
| Source | Source | Menu | pattern | pattern |
| Pattern | Pattern | Menu | square | circle |
| Count | Count | Int | 5 | 52 |
| Size | Size | Float | 0.8 | 0.646 |
| Sop | SOP (empty = in1) | SOP |  |  |
| Chop | CHOP (empty = in2) | CHOP |  |  |
| Pop | POP (empty = in4) | POP |  |  |
| Fitsource | Fit SOP/POP to -1..1 | Toggle | True | True |
| Text | Text | Str | LASER | LASER |
| Font | Font | Str | Helvetica | Helvetica |
| Tracesrc | Tracesrc | Menu | clip | in3 |
| Tracelevel | Trace threshold | Float | 0.5 | 0.5 |
| Traceblur | Trace blur px | Float | 4.0 | 4.0 |
| Tracesteps | Trace res / | Int | 3 | 3 |
| Audiochop | Audio CHOP (L/R) | CHOP |  |  |

### Path

| name | label | style | default | value |
|---|---|---|---|---|
| Engine | Engine | Menu | native | own |
| Pps | Points/s | Float | 30000.0 | 48000.0 |
| Fps | Frame rate | Float | 60.0 | 60.0 |
| Stepsize | Step | Float | 0.02 | 0.02 |
| Bstepsize | Blank step | Float | 0.1 | 0.1 |
| Minhold | Min corner hold ms | Float | 0.1 | 0.1 |
| Maxhold | Max corner hold ms | Float | 0.3 | 0.1 |
| Holdadd | Hold add | Int | 0 | 0 |
| Cornertol | Corner above deg | Float | 25.0 | 25.0 |
| Closedoverlap | Closed overlap ms | Float | 0.0 | 0.0 |
| Order | Order | Menu | twoopt | none |
| Orderms | Order budget | Float | 3.0 | 3.0 |
| Startpoint | Startpoint | Menu | centre | centre |
| Preblankon | Pre-blank on ms | Float | 0.0 | 0.0 |
| Postblankon | Post-blank on ms | Float | 0.1 | 0.1 |
| Preblankoff | Pre-blank off ms | Float | 0.1 | 0.1 |
| Postblankoff | Post-blank off ms | Float | 0.0 | 0.0 |
| Colordelay | Colour delay ms | Float | 0.0 | 0.0 |
| Interpcolors | Interp colours | Toggle | True | True |
| Overflow | Overflow | Menu | frames | frames |

### Shape

| name | label | style | default | value |
|---|---|---|---|---|
| Scalex | Scale X | Float | 1.0 | 1.0 |
| Scaley | Scale Y | Float | 1.0 | 1.0 |
| Rotate | Rotate | Float | 0.0 | 0.0 |
| Offsetx | Offset X | Float | 0.0 | 0.0 |
| Offsety | Offset Y | Float | 0.0 | 0.0 |
| Flipx | Flip X | Toggle | False | False |
| Flipy | Flip Y | Toggle | False | False |
| Swap | Swap XY | Toggle | False | False |
| Warp | Warp (warptable) | Toggle | False | False |
| Intensity | Intensity | Float | 1.0 | 1.0 |
| Gain | Gain | Float | 1.0 | 1.0 |
| Rgbr | Colour | RGBA | 0.1 | 0.1 |
| Rgbg | Colour | RGBA | 1.0 | 1.0 |
| Rgbb | Colour | RGBA | 0.25 | 0.25 |

### Drive

| name | label | style | default | value |
|---|---|---|---|---|
| Intensitysrc | Intensitysrc | Menu | manual | manual |
| Bpm | BPM | Float | 120.0 | 120.0 |
| Beatdiv | Beat mult | Float | 1.0 | 1.0 |
| Audioch | Audio CHOP (level) | CHOP |  |  |
| Audioamt | Audio amount | Float | 1.0 | 1.0 |
| Drivechop | Drive CHOP (chan 0) | CHOP |  |  |
| Strobe | Strobe | Menu | off | off |
| Strobeon | Strobe button | Momentary | False | False |
| Blackout | Blackout | Toggle | False | False |
| Hold | Hold image | Toggle | False | False |

### Preview

| name | label | style | default | value |
|---|---|---|---|---|
| Previewon | Preview on | Toggle | True | True |
| Previewres | Preview px | Int | 1080 | 1080 |
| Galvobw | Galvo bandwidth Hz | Float | 6000.0 | 6000.0 |
| Galvozeta | Galvo damping | Float | 0.7 | 0.7 |
| Showlag | Show galvo lag | Toggle | False | False |
| Showblank | Show blanked travel | Toggle | False | False |
| Persist | Persistence ms | Float | 60.0 | 60.0 |
| Glow | Glow px | Float | 6.0 | 6.0 |
| Spotgain | Spot gain | Float | 0.35 | 0.35 |
| Spotsize | Spot px | Float | 10.0 | 10.0 |
| Bgr | Background | RGBA | 0.0 | 0.0 |
| Bgg | Background | RGBA | 0.0 | 0.0 |
| Bgb | Background | RGBA | 0.0 | 0.0 |

### Controls

| name | label | style | default | value |
|---|---|---|---|---|
| Opencontrols | Open controls | Pulse | False | False |
| Savesnap | Save snapshot | Pulse | False | False |
| Exportilda | Export ILDA | Pulse | False | False |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 52 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |
| Zkm1 | Size | Float | 0.0 | 0.75 |
| Zkm2 | Brightness | Float | 0.0 | 1.0 |
| Zkm3 | Glow | Float | 0.0 | 0.3 |

### About

| name | label | style | default | value |
|---|---|---|---|---|
| Version | Version | Str |  | 0.1.0 |
| Touchbuild | Touch build | Str |  | 2025.31550 |
| Saved | Saved | Str |  | 2026-10-26 16:51 |

## Perf

cook 1.424 ms (CPU 1.424 / GPU 1.556) summed over the 7 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "LP_laser_path", "parent": "/project1/lab"}` (lands parked)
