# GN_physarum

> physarum: GN_physarum slime mould COMP (live-verified v1 on 2025.31550, 26 Oct 2026, T-112)

v0.1.1 - TD 2025.31550 - exported 2026-10-29 00:08:54 from `/project1/lab/GN_physarum`

`/project1/lab/GN_physarum`. Jones / Jenson physarum: agents with a heading and three sensors (front-left, front,
front-right) sense a trail map, rotate, move and deposit; the trail diffuses (3x3 mean) and decays. Research:
`docs/research/O_generative_simulations.md` 4.3 (reimplemented from the model description; no GPL / unlicensed code).
Every sim pass is a **compute** GLSL TOP (T-46/T-47). The deposit (a scatter) is a **Render TOP of one 1-px point per
agent with additive blending into rgba32float**: Mac has no float atomics (research O F13), and blending gives exact
sums. **No limits** (user rule): open ranges, nothing clamps the look.

Build doc: `docs/builds/physarum.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- in `in2` (inTOP) 128x128
- in `in5` (inCHOP)
- in `in6` (inCHOP)
- out `out1` (outTOP) 1080x1920
- out `out2` (outTOP) 540x960
- out `out3` (outTOP) 512x512

## Custom parameters

### Sim

| name | label | style | default | value |
|---|---|---|---|---|
| Agents | Agents | Int | 262144 | 262144 |
| Simh | Trail cells (height) | Int | 960 | 960 |
| Resw | Out width | Int | 1080 | 1080 |
| Resh | Out height | Int | 1920 | 1920 |
| Edge | Edges | Menu | wrap | wrap |
| Species | Species (1-3) | Int | 1 | 1 |
| Speciesmode | Species layout | Menu | interleave | interleave |
| Selfw | Own trail weight | Float | 1.0 | 1.0 |
| Otherw | Other species weight (- avoid) | Float | -1.0 | -1.0 |
| Speedspread | Species speed spread | Float | 0.0 | 0.0 |

### Preset

| name | label | style | default | value |
|---|---|---|---|---|
| Preseta | Preset A | Menu | network | network |
| Presetb | Preset B | Menu | cells | cells |
| Morph | Morph A -> B | Float | 0.0 | 0.0 |
| Morphgo | Morph go (A <-> B) | Pulse | False | False |
| Morphtime | Morph go time s | Float | 4.0 | 4.0 |
| Morphlfo | Morph LFO | Menu | off | off |
| Morphrate | LFO rate Hz | Float | 0.05 | 0.05 |
| Morphdepth | LFO depth | Float | 0.0 | 0.0 |
| Sagain | x Sensor angle | Float | 1.0 | 1.0 |
| Sogain | x Sensor distance | Float | 1.0 | 1.0 |
| Ragain | x Rotate angle | Float | 1.0 | 1.0 |
| Ssgain | x Step | Float | 1.0 | 1.0 |
| Depgain | x Deposit | Float | 1.0 | 1.0 |
| Decaygain | x Decay | Float | 1.0 | 1.0 |
| Diffgain | x Diffuse | Float | 1.0 | 1.0 |
| Jittergain | x Jitter | Float | 1.0 | 1.0 |
| Customsa | Custom Sensor angle deg | Float | 22.5 | 22.5 |
| Customso | Custom Sensor distance cells | Float | 9.0 | 9.0 |
| Customra | Custom Rotate angle deg | Float | 45.0 | 45.0 |
| Customss | Custom Step cells/frame | Float | 1.0 | 1.0 |
| Customdep | Custom Deposit | Float | 1.0 | 1.0 |
| Customdecay | Custom Decay per frame | Float | 0.1 | 0.1 |
| Customdiffuse | Custom Diffuse (3x3 mix) | Float | 1.0 | 1.0 |
| Customjitter | Custom Jitter deg | Float | 0.0 | 0.0 |

### Seed

| name | label | style | default | value |
|---|---|---|---|---|
| Seedmode | Agent seed | Menu | disc | disc |
| Heading | Start heading | Menu | random | random |
| Seedsize | Seed size (heights) | Float | 0.3 | 0.3 |
| Seed | Seed | Int | 1 | 1 |
| Seedtext | Seed text | Str | PRISM | PRISM |
| Textsize | Text size (heights) | Float | 0.12 | 0.12 |
| Reseed | Reseed (new seed + reset) | Pulse | False | False |
| Reset | Reset | Pulse | False | False |
| Respawn | Respawn per frame (fraction) | Float | 0.002 | 0.002 |

### Food

| name | label | style | default | value |
|---|---|---|---|---|
| Foodw | Food map attract (in1 / text) | Float | 0.0 | 0.0 |
| Foodinject | Food -> trail inject | Float | 0.0 | 0.0 |
| Foodsrc | Food source | Menu | image | image |
| Maskthresh | Mask threshold (in2) | Float | 0.5 | 0.5 |
| Effon | Effectors on | Toggle | True | True |
| Effectors | Effector Nulls (names/paths/patterns) | StrMenu | eff* | eff* |
| Planeh | Plane height (world units) | Float | 1.0 | 1.0 |
| Effradius | Effector radius | Float | 0.15 | 0.15 |
| Effstrength | Effector attract (- repels) | Float | 10.0 | 10.0 |
| Effdeposit | Effector trail inject | Float | 0.0 | 0.0 |
| Efffalloff | Effector falloff | Menu | gauss | gauss |
| Pointradius | in5 point radius | Float | 0.05 | 0.05 |
| Mousemode | Mouse | Menu | off | off |
| Mouseradius | Mouse radius | Float | 0.08 | 0.08 |
| Mousestrength | Mouse strength | Float | 5.0 | 5.0 |

### Audio

| name | label | style | default | value |
|---|---|---|---|---|
| Audiomode | Audio (in6) | Menu | off | off |
| Audiotarget | Level drives | Menu | step | step |
| Audiogain | Audio gain | Float | 4.0 | 4.0 |
| Audioamt | Level amount | Float | 1.0 | 1.0 |
| Lowhz | Low band Hz | Float | 150.0 | 150.0 |
| Kickthresh | Kick threshold | Float | 0.3 | 0.3 |
| Refractory | Kick refractory s | Float | 0.15 | 0.15 |
| Kickspeed | Kick step x | Float | 3.0 | 3.0 |
| Kickrelease | Kick release s | Float | 0.3 | 0.3 |
| Burst | Burst | Pulse | False | False |
| Burstpattern | Burst pattern | Menu | random | random |
| Burstcount | Burst spots | Int | 3 | 3 |
| Burstradius | Burst radius | Float | 0.08 | 0.08 |
| Burststrength | Burst attract (- scatters) | Float | -8.0 | -8.0 |
| Burstframes | Burst frames | Int | 6 | 6 |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Valuemode | Tone | Menu | soft | soft |
| Lo | Value low | Float | 0.0 | 0.0 |
| Hi | Value high / soft scale | Float | 8.0 | 8.0 |
| Colormode | Colour | Menu | species | species |
| Palette | Palette | Menu | prism | prism |
| Ramptop | Ramp TOP (empty = inner ramp) | TOP |  |  |
| Col1r | Species 1 colour | RGBA | 0.79 | 0.79 |
| Col1g | Species 1 colour | RGBA | 0.28 | 0.28 |
| Col1b | Species 1 colour | RGBA | 0.91 | 0.91 |
| Col2r | Species 2 colour | RGBA | 1.0 | 1.0 |
| Col2g | Species 2 colour | RGBA | 0.27 | 0.27 |
| Col2b | Species 2 colour | RGBA | 0.5 | 0.5 |
| Col3r | Species 3 colour | RGBA | 1.0 | 1.0 |
| Col3g | Species 3 colour | RGBA | 0.73 | 0.73 |
| Col3b | Species 3 colour | RGBA | 0.01 | 0.01 |
| Bgr | Background | RGBA | 0.0 | 0.0 |
| Bgg | Background | RGBA | 0.0 | 0.0 |
| Bgb | Background | RGBA | 0.0 | 0.0 |
| Exposure | Exposure (stops) | Float | 0.0 | 0.0 |
| Gamma | Gamma | Float | 1.0 | 1.0 |
| Glow | Halo glow | Float | 0.0 | 0.0 |
| Agentsview | Show agents (deposit) mix | Float | 0.0 | 0.0 |
| Alpha | Alpha | Menu | opaque | opaque |
| Premult | Premultiplied | Toggle | True | True |
| Showeff | Preview gizmos | Toggle | True | True |
| Pal1r | Palette 1 (low) | RGBA | 0.02 | 0.02 |
| Pal1g | Palette 1 (low) | RGBA | 0.0 | 0.0 |
| Pal1b | Palette 1 (low) | RGBA | 0.06 | 0.06 |
| Pal2r | Palette 2 | RGBA | 0.25 | 0.25 |
| Pal2g | Palette 2 | RGBA | 0.05 | 0.05 |
| Pal2b | Palette 2 | RGBA | 0.55 | 0.55 |
| Pal3r | Palette 3 | RGBA | 0.85 | 0.85 |
| Pal3g | Palette 3 | RGBA | 0.15 | 0.15 |
| Pal3b | Palette 3 | RGBA | 0.65 | 0.65 |
| Pal4r | Palette 4 | RGBA | 1.0 | 1.0 |
| Pal4g | Palette 4 | RGBA | 0.55 | 0.55 |
| Pal4b | Palette 4 | RGBA | 0.3 | 0.3 |
| Pal5r | Palette 5 (high) | RGBA | 1.0 | 1.0 |
| Pal5g | Palette 5 (high) | RGBA | 0.95 | 0.95 |
| Pal5b | Palette 5 (high) | RGBA | 0.85 | 0.85 |

### Control

| name | label | style | default | value |
|---|---|---|---|---|
| Pause | Pause | Toggle | False | False |
| Step | Step (while paused) | Pulse | False | False |
| Stopat | Pause at step (0 = off) | Int | 0 | 0 |
| Testmode | Test mode | Menu | off | off |

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
| Zkm1 | Chaos | Float | 0.0 | 0.5 |
| Zkm2 | Density | Float | 0.0 | 0.5 |
| Zkm3 | Glow | Float | 0.0 | 0.0 |

## Perf

cook 2.286 ms (CPU 2.286 / GPU 9.395) summed over the 12 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "GN_physarum", "parent": "/project1/lab"}` (lands parked)
