# BK_dmx_out

v0.1.0 - TD 2025.31550 - exported 2026-10-26 19:46:21 from `/project1/lab/BK_dmx_out`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inCHOP)
- in `in3` (inCHOP)
- out `out1` (outTOP) 128x128
- out `out2` (outCHOP)
- out `out3` (outCHOP)

## Custom parameters

### Output

| name | label | style | default | value |
|---|---|---|---|---|
| Active | Active (send) | Toggle | False | True |
| Protocol | Protocol | Menu | artnet | artnet |
| Targetmode | Target | Menu | unicast | unicast |
| Targetip | Target IP | Str | 127.0.0.1 | 127.0.0.1 |
| Localip | Local IP (blank = OS) | Str |  |  |
| Rate | Rate Hz | Float | 40.0 | 40.0 |
| Firstuniv | First universe | Int | 0 | 0 |
| Priority | sACN priority | Int | 100 | 100 |
| Sourcename | Source name | Str | BK_dmx_out | BK_dmx_out |
| Sendsync | Send ArtSync | Toggle | False | False |
| Syncms | Sync timeout ms | Int | 20 | 20 |
| Netport | Port (0 = default) | Int | 0 | 0 |
| Loopback | Loopback check | Toggle | False | True |
| Sender | Sender | Menu | tddmx | tddmx |
| Universes | Universes (read) | Int | 0 | 2 |
| Slotsused | Slots used (read) | Int | 0 | 224 |
| Packetsrate | Packets/s (read) | Float | 0.0 | 80.0 |
| Mapok | Map ok (read) | Toggle | True | True |

### Mapping

| name | label | style | default | value |
|---|---|---|---|---|
| Pixelsrc | Pixel source (blank = in1) | TOP |  |  |
| Pixelblur | Blur px | Float | 0.0 | 0.0 |
| Colororder | Colour order | Menu | rgb | rgb |
| Whitemode | White | Menu | none | none |
| Gamma | Gamma | Float | 1.0 | 1.0 |
| Pixperuniv | Pixels / universe | Int | 170 | 170 |
| Spanuniv | Span universes | Toggle | False | False |
| Pixelscale | Full scale | Float | 255.0 | 255.0 |
| Interp | Interp | Menu | nearest | nearest |

### Master

| name | label | style | default | value |
|---|---|---|---|---|
| Master | Master | Float | 1.0 | 1.0 |
| Blackout | Blackout | Toggle | False | False |
| Blackoutmode | Blackout acts on | Menu | intensity | intensity |
| Freeze | Freeze | Toggle | False | False |
| Masterfrom | Master from | Menu | manual | manual |
| Bpm | BPM | Float | 120.0 | 120.0 |
| Beatshape | Beat shape | Menu | pulse | pulse |
| Beatdepth | Beat depth | Float | 1.0 | 1.0 |
| Audioamt | Audio amount | Float | 1.0 | 1.0 |
| Tapbpm | Tap BPM | Pulse | False | False |

### Test

| name | label | style | default | value |
|---|---|---|---|---|
| Pattern | Pattern | Menu | live | live |
| Patternmix | Pattern mix | Menu | replace | replace |
| Level | Level | Float | 1.0 | 1.0 |
| Speed | Speed (Hz / beats) | Float | 1.0 | 1.0 |
| Solofixture | Solo fixture (pattern) | Str |  |  |
| Solochan | Solo slot (0 = off) | Int | 0 | 0 |
| Univfilter | Universe filter (e.g. 0-3 7) | Str |  |  |

### Monitor

| name | label | style | default | value |
|---|---|---|---|---|
| Monfirst | First row | Int | 0 | 0 |
| Moncount | Rows shown | Int | 16 | 16 |
| Moncell | Px per slot | Int | 6 | 6 |
| Monmode | Mode | Menu | heat | heat |
| Monw | Monitor width | Int | 1024 | 1024 |
| Monh | Monitor height | Int | 768 | 768 |

### Patch

| name | label | style | default | value |
|---|---|---|---|---|
| Profile | Profile | Menu | generic_rgb_3ch | generic_rgb_3ch |
| Mode | Mode (blank = first) | Str |  |  |
| Count | Count | Int | 1 | 1 |
| Fixname | Name | Str | fx | fx |
| Univ | Universe | Int | 0 | 0 |
| Addr | Address | Int | 1 | 10 |
| Autonext | Next free | Toggle | True | True |
| Quantize | Quantize | Menu | fixture | fixture |
| Gap | Gap slots | Int | 0 | 0 |
| Addfixture | Add fixture(s) | Pulse | False | False |
| Checkpatch | Check patch | Pulse | False | False |
| Pixlayout | Pixel layout | Menu | strip | strip |
| Pixw | Pixels W / count | Int | 50 | 50 |
| Pixh | Pixels H | Int | 1 | 1 |
| Serpentine | Serpentine | Toggle | True | True |
| Genpixels | Make pixel map | Pulse | False | False |
| Importfile | Import (OFL .json / .csv) | File |  |  |
| Importpulse | Import | Pulse | False | False |
| Clearpatch | Clear patch | Pulse | False | False |

### Controls

| name | label | style | default | value |
|---|---|---|---|---|
| Bypass | Bypass (send nothing) | Toggle | False | False |
| Resetdefaults | Reset defaults | Pulse | False | False |

## Perf

cook 41.676 ms (CPU 41.676 / GPU 0.0) summed over the 66 ops that cooked in the last frame at export (0 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "BK_dmx_out", "parent": "/project1/lab"}` (lands parked)
