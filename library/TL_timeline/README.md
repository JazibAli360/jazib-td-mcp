# TL_timeline

> TL_timeline phase 2: clips track (live v1 26 Oct 2026, TD 2025.31550, T-93; live checks 3, 8, 9 open)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:40 from `/project1/lab/TL_timeline`

Plan: `docs/builds/timeline_phases.md` (phase 2). COMP: `/project1/lab/TL_timeline`. Phase 1 stays as it was (same
builder, same 28 tests); phase 2 is added by the same `build()` call.

Build doc: `docs/builds/timeline_phase2.md`

## Inputs / outputs

- out `audio_out` (outCHOP)
- out `program_out` (outTOP) 1080x1920
- out `tl_out` (outCHOP)

## Custom parameters

### Timeline

| name | label | style | default | value |
|---|---|---|---|---|
| Play | Play / pause | Toggle | False | False |
| Loop | Loop in/out | Toggle | True | True |
| Rate | Rate (x) | Float | 1.0 | 1.0 |
| Seek | Playhead / scrub (s) | Float | 0.0 | 0.0 |
| Stop | Stop (pause + to in) | Pulse | False | False |
| Gotostart | Go to in point | Pulse | False | False |
| Stepback | Step back 1 frame | Pulse | False | False |
| Stepfwd | Step forward 1 frame | Pulse | False | False |
| Gotoend | Go to out point | Pulse | False | False |
| Inpoint | Loop in (s) | Float | 0.0 | 0.0 |
| Outpoint | Loop out (s) | Float | 16.0 | 16.0 |
| Snap | Snap to grid | Toggle | True | True |
| Lane | Selected lane | Int | 0 | 1 |
| Keyvalue | Key value | Float | 0.5 | 0.9 |
| Keyinterp | Key interpolation | Menu | linear | linear |
| Addkey | Add key at playhead | Pulse | False | False |
| Deletekey | Delete key at playhead | Pulse | False | False |
| Prevkey | Previous key | Pulse | False | False |
| Nextkey | Next key | Pulse | False | False |
| Addmarker | Add marker at playhead | Pulse | False | False |
| Prevmarker | Previous marker | Pulse | False | False |
| Nextmarker | Next marker | Pulse | False | False |
| Opencontrols | Open controls window | Pulse | False | False |

### Setup

| name | label | style | default | value |
|---|---|---|---|---|
| Length | Length (s) | Float | 16.0 | 16.0 |
| Fps | Frame rate | Float | 30.0 | 30.0 |
| Clockmode | Clock | Menu | realtime | realtime |
| Bpm | BPM | Float | 120.0 | 120.0 |
| Beatsperbar | Beats per bar | Int | 4 | 4 |
| Snapdiv | Snap divisions per beat | Int | 1 | 1 |
| Snapunit | Snap to | Menu | beat | beat |
| Tcmode | Timecode | Menu | smpte | smpte |
| Markername | New marker name | Str | Marker | Marker |

### Info

| name | label | style | default | value |
|---|---|---|---|---|
| Timecode | Timecode | Str |  | 00:00:00:00 |
| Barbeat | Bar.beat.16th | Str |  | 1.1.1 |
| Marker | Current marker | Str |  | Intro |
| Lanecount | Lanes | Int | 0 | 2 |
| Clipactive | Clips on screen | Str |  | ramp |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 56 |
| Zkcols | Columns | Int | 8 | 12 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |
| Zkm1 | Tempo | Float | 0.0 | 0.5 |
| Zkm2 | Audio | Float | 0.0 | 0.5 |

### Clips

| name | label | style | default | value |
|---|---|---|---|---|
| Program | Program out | Menu | clips | clips |
| Maxplayers | Players (full res) | Int | 2 | 2 |
| Sourcemode | Source | Menu | full | auto |
| Blendmode | Blend | Menu | over | over |
| Premult | Premultiply inputs (straight alpha) | Toggle | True | True |
| Fit | Fit | Menu | fit | fit |
| Preroll | Preload ahead (s) | Float | 0.5 | 0.5 |
| Clip | Selected clip | Str |  |  |
| Refreshmedia | Re-read media info | Pulse | False | False |
| Makeproxies | Make proxies (ffmpeg, background) | Pulse | False | False |

### Record

| name | label | style | default | value |
|---|---|---|---|---|
| Recin | Record in (s) | Float | 0.0 | 0.0 |
| Recout | Record out (s; <= in = loop range) | Float | 5.0 | 5.0 |
| Recfps | File frame rate | Float | 60.0 | 60.0 |
| Reccodec | Codec | Menu | prores4444 | prores4444 |
| Recfile | File (.mov; empty = output/timeline/renders/TL_<time>.mov) | Str |  |  |
| Record | Record (offline, frame-accurate) | Pulse | False | False |
| Recabort | Abort take | Pulse | False | False |
| Recording | Recording | Toggle | False | False |
| Recstatus | Status | Str |  | ok 60 frames -> p3_take_30fps.mov |
| Exportformat | Marker export format | Menu | csv | ae |
| Exportmarkers | Export markers | Pulse | False | False |
| Exportlanes | Export lanes (per-frame CSV, record range) | Pulse | False | False |
| Lastexport | Last export | Str |  | ~/Documents/StageLab_PrismFest/jazib-td-mcp/output/timeline/export/lanes_20261026_183319.csv |

### Audio

| name | label | style | default | value |
|---|---|---|---|---|
| Audiofile | Master audio file (empty = none) | File |  |  |
| Audiooffset | Master starts at (s) | Float | 0.0 | 0.0 |
| Audiogain | Master gain | Float | 1.0 | 1.0 |
| Clipaudio | Clip audio | Toggle | True | True |
| Clipgain | Clip audio gain | Float | 1.0 | 1.0 |
| Listen | Listen (Mac default output, only while playing) | Toggle | False | False |
| Outvolume | Output volume | Float | 0.8 | 0.8 |

## Perf

cook 1.58 ms (CPU 1.58 / GPU 0.0) summed over the 3 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "TL_timeline", "parent": "/project1/lab"}` (lands parked)
