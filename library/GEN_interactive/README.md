# GEN_interactive

> gen_interactive: GEN_interactive rack + 4 people-driven artist looks (live in main, 26 Oct 2026, TD 2025.31550)

v0.2.1 - TD 2025.31550 - exported 2026-10-29 00:08:41 from `/project1/lab/GEN_interactive`

`/project1/lab/GEN_interactive`. FX0 row "GEN_interactive" (backlog ranks 42 + 68): FX5 E8 ribbon brush (Zach
Lieberman look), E4 flowers / waterfall (teamLab look), E1 data pigment (Refik Anadol look), E3 line volumes (Joanie
Lemercier look). Technique emulation only: neutral par names, no frames / logos / assets of the artists; credits are
these names in this doc.

**Status: all four modules verified live on 2025.31550 (build TD b4, 26 Oct): see "Verified live". 92 offline tests.** Offline tests: `python3 -I -m unittest discover -s test -p
'test_gen_interactive*.py'` (rack, points logic, mask, fake-TD builder dry run, glslc compile of every pass against TD
compute stubs = a syntax / type check, not a TD compile, numpy references per module).

Build doc: `docs/builds/gen_interactive.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Points

| name | label | style | default | value |
|---|---|---|---|---|
| Source | Source | Menu | demo | demo |
| Maxpoints | Points (samples of pts) | Int | 16 | 16 |
| Smooth | Smooth (share kept per 1/60 s) | Float | 0.5 | 0.5 |
| Demoshape | Demoshape | Menu | lissajous | lissajous |
| Demospeed | Demo speed | Float | 1.0 | 1.0 |
| Demoseed | Demo seed | Int | 1 | 1 |
| Faceop | Face tracker COMP (out_pts) | Str | /project1/lab/FT_face_track | /project1/lab/FT_face_track |
| Facepts | Landmarks (glob on f<n>_<region>_<kk>) | Str | f1_nose_* f1_pupil_* f1_lips_outer_* | f1_nose_* f1_pupil_* f1_lips_outer_* |
| Facestride | Landmark stride | Int | 1 | 1 |
| Facemirror | Mirror face x | Toggle | False | False |
| Effselect | Effectors (all / names / #tag) | StrMenu | all | all |
| Effsets | Point sets give their points | Toggle | True | True |
| Effcentres | Other effectors give their centre | Toggle | True | True |
| Nulls | Null COMPs (names / paths) | StrMenu | pen1 | pen1 |
| Mousepen | Mouse draws only while pressed | Toggle | False | False |
| Pointchop | Point CHOP (Source chop) | CHOP |  |  |
| Chopunits | Chopunits | Menu | unit | signed |
| Planecx | Plane centre x (world) | Float | 0.0 | 0.0 |
| Planecy | Plane centre y (world) | Float | 0.0 | 0.0 |
| Planew | Plane width (world units = frame) | Float | 1.125 | 1.125 |
| Planeh | Plane height (world units = frame) | Float | 2.0 | 2.0 |

### Mask

| name | label | style | default | value |
|---|---|---|---|---|
| Masksource | Masksource | Menu | none | none |
| Masktop | Mask TOP (e.g. CV_person_mask/out2, FT_face_track/out_face) | TOP |  |  |
| Maskchannel | Maskchannel | Menu | r | r |
| Lumathresh | Luma threshold | Float | 0.5 | 0.6 |
| Lumasoft | Luma softness | Float | 0.1 | 0.1 |
| Maskinvert | Invert presence | Toggle | False | False |
| Motiongain | Motion gain | Float | 4.0 | 4.0 |
| Motionsmooth | Motion smooth (per cook) | Float | 0.8 | 0.8 |
| Maskw | Mask width | Int | 270 | 270 |
| Maskh | Mask height | Int | 480 | 480 |

### Drive

| name | label | style | default | value |
|---|---|---|---|---|
| Beatsource | Beatsource | Menu | internal | internal |
| Bpm | Bpm | Float | 120.0 | 120.0 |
| Bpmchop | Bpm CHOP (e.g. AU_features/out1) | CHOP |  |  |
| Bpmchan | Bpm channel | Str | bpm | bpm |
| Beatchop | Beat CHOP (e.g. AU_features/out1) | CHOP |  |  |
| Phasechan | Beat phase channel | Str | beat_phase | beat_phase |
| Countchan | Beat count channel | Str | beat_count | beat_count |
| Audiochop | Audio CHOP (e.g. AC_audio/out_ctl) | CHOP |  |  |
| Audiochan | Audio channel | Str | low | low |
| Resync | Resync (beat 1 now) | Pulse | False | False |

### Rack

| name | label | style | default | value |
|---|---|---|---|---|
| Panic | Panic (background only) | Toggle | False | False |
| Input | Input | Menu | auto | auto |
| Resw | Width (black bg) | Int | 1080 | 1080 |
| Resh | Height (black bg) | Int | 1920 | 1920 |

## Perf

cook 95.622 ms (CPU 95.622 / GPU 0.891) summed over the 22 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "GEN_interactive", "parent": "/project1/lab"}` (lands parked)
