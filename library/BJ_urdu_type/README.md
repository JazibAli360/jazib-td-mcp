# BJ_urdu_type

> urdu_type (BJ build spec A): status 26 Oct 2026, TD 2025.31550 - LIVE-VERIFIED via the pre-shaped atlas route (commit 9eb3bc7: 150 s scratch soak, then main; earlier Text TOP route crashed TD, T-76/T-79)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:07:49 from `/project1/lab/BJ_urdu_type`

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

Spec: `docs/research/BJ_urdu_arabic_text_shaping.md` section 5 (clean-room). Path: `/project1/lab/BJ_urdu_type`.

Build doc: `docs/builds/urdu_type.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inCHOP)
- out `out1` (outTOP) 1080x1920
- out `out_rest` (outCHOP)
- out `out_words` (outDAT)

## Custom parameters

### Text

| name | label | style | default | value |
|---|---|---|---|---|
| Text | Text (\n = new line) | Str | اردو زبان\nہیلو hello اردو 2026 | اردو زبان\nہیلو hello اردو 2026 |
| Textdat | Text DAT (lines) | OP |  |  |
| Line | Line (cue) | Int | 0 | 0 |
| Direction | Direction | Menu | auto | auto |
| Fontrtl | Urdu font | StrMenu | Noto Nastaliq Urdu | Noto Nastaliq Urdu |
| Fontfilertl | Urdu font file | File |  |  |
| Typefacertl | Urdu typeface | Menu | Regular | Regular |
| Weight | Urdu weight (wght axis, 0 = font default) | Int | 0 | 0 |
| Fontltr | Latin font | StrMenu | Helvetica Neue | Helvetica Neue |
| Fontfileltr | Latin font file | File |  |  |
| Fontdigits | Digits font (empty = Latin) | StrMenu |  |  |
| Size | Size px | Float | 160.0 | 160.0 |
| Wordgap | Word gap em | Float | 0.3 | 0.3 |
| Linegap | Line gap | Float | 1.0 | 1.0 |
| Maxwidth | Wrap width px (0 off) | Float | 960.0 | 960.0 |
| Align | Align | Menu | center | center |
| Anchorx | Anchor x | Float | 0.5 | 0.5 |
| Anchory | Anchor y | Float | 0.5 | 0.5 |
| Maxwords | Max words | Int | 24 | 24 |

### Style

| name | label | style | default | value |
|---|---|---|---|---|
| Fillr | Fill | RGBA | 1.0 | 1.0 |
| Fillg | Fill | RGBA | 1.0 | 1.0 |
| Fillb | Fill | RGBA | 1.0 | 1.0 |
| Fillalpha | Fill alpha | Float | 1.0 | 1.0 |
| Outliner | Outline | RGBA | 0.85 | 0.85 |
| Outlineg | Outline | RGBA | 0.65 | 0.65 |
| Outlineb | Outline | RGBA | 0.2 | 0.2 |
| Outlinepx | Outline px | Float | 0.0 | 4.14 |
| Outlinealpha | Outline alpha | Float | 1.0 | 1.0 |
| Glowcolorr | Glow colour | RGBA | 1.0 | 1.0 |
| Glowcolorg | Glow colour | RGBA | 0.8 | 0.8 |
| Glowcolorb | Glow colour | RGBA | 0.4 | 0.4 |
| Glow | Glow | Float | 0.0 | 0.0 |
| Glowsize | Glow size px | Float | 24.0 | 24.0 |
| Shadow | Shadow | Float | 0.0 | 0.0 |
| Shadowsize | Shadow soft px | Float | 12.0 | 12.0 |
| Shadowoffx | Shadow offset px | XYZW | 8.0 | 8.0 |
| Shadowoffy | Shadow offset px | XYZW | -8.0 | -8.0 |
| Background | Background | Menu | none | none |
| Bgcolorr | Bg colour | RGBA | 0.0 | 0.0 |
| Bgcolorg | Bg colour | RGBA | 0.0 | 0.0 |
| Bgcolorb | Bg colour | RGBA | 0.0 | 0.0 |
| Bgalpha | Bg alpha | Float | 1.0 | 1.0 |
| Premult | Premultiplied out | Toggle | True | True |

### Anim

| name | label | style | default | value |
|---|---|---|---|---|
| Mode | Mode | Menu | fade | fade |
| Timing | Timing | Menu | seconds | bpm |
| Progress | Progress (manual) | Float | 1.0 | 1.0 |
| Stagger | Stagger | Float | 0.6 | 1.0 |
| Order | Order | Menu | reading | reading |
| Seed | Random seed | Int | 1 | 1 |
| Ease | Ease | Menu | ease | ease |
| Seconds | Seconds | Float | 2.0 | 2.0 |
| Bpm | BPM | Float | 120.0 | 94.6 |
| Beats | Beats | Float | 4.0 | 4.0 |
| Slidex | Slide x px | Float | 0.0 | 0.0 |
| Slidey | Slide y px | Float | -80.0 | -80.0 |
| Scalefrom | Scale from | Float | 0.6 | 0.6 |
| Blurmax | Blur max px | Float | 24.0 | 24.0 |
| Pulseamt | Pulse amount | Float | 0.25 | 0.25 |
| Audiolevel | Audio level | Float | 0.0 | 0.0 |
| Audiogain | Audio gain | Float | 1.0 | 1.0 |
| Audiosmooth | Audio smooth | Float | 0.6 | 0.6 |
| Trigger | Trigger | Pulse | False | False |
| Hold | Hold | Toggle | False | False |
| Loop | Loop | Toggle | False | False |
| Autotrigger | Trigger on new text | Toggle | True | True |

### Layout

| name | label | style | default | value |
|---|---|---|---|---|
| Outw | Out width | Int | 1080 | 1080 |
| Outh | Out height | Int | 1920 | 1920 |
| Lineh | Line box em | Float | 2.5 | 2.5 |
| Marginem | Raster margin em | Float | 0.6 | 0.6 |
| Showboxes | Show ink boxes | Toggle | False | False |
| Wipesoft | Wipe edge px | Float | 24.0 | 24.0 |
| Blurtaps | Blur taps | Int | 16 | 16 |
| Rebuild | Re-render | Pulse | False | False |

### Files

| name | label | style | default | value |
|---|---|---|---|---|
| Cachedir | Render cache (empty = <repo>/output/urdu_type/cache) | Folder |  |  |
| Python | Python 3 for the renderer | File | /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 | /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 |
| Timeout | Render timeout s | Float | 20.0 | 20.0 |

### Control

| name | label | style | default | value |
|---|---|---|---|---|
| Showinfo | Show info on preview | Toggle | False | False |

### Info

| name | label | style | default | value |
|---|---|---|---|---|
| Status | Status | Str |  | ok 6 words, atlas 2407x592 |
| Nwords | Words | Int | 0 | 6 |
| Nlines | Lines | Int | 0 | 3 |
| Atlasslot | Atlas slot (0 A, 1 B) | Int | 0 | 1 |
| Atlasw | Atlas width | Int | 0 | 2407 |
| Atlash | Atlas height | Int | 0 | 592 |
| Parsems | Parse ms (TD) | Float | 0.0 | 0.3 |
| Renderms | Render ms (child process) | Float | 0.0 | 483.8 |
| Layoutms | Layout ms (TD) | Float | 0.0 | 0.42 |

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
| Zkm1 | Glow | Float | 0.0 | 0.0 |
| Zkm2 | Edge | Float | 0.0 | 0.0 |
| Zkm3 | Speed | Float | 0.0 | 0.55 |

## Perf

cook 0.602 ms (CPU 0.602 / GPU 1.272) summed over the 9 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- `.` Python `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3` (outside)

## Load

`td_library_load {"name": "BJ_urdu_type", "parent": "/project1/lab"}` (lands parked)
