# BO_particles

> particles: BO_particles GPU particle system (live v1 in main, 26 Oct 2026, TD 2025.31550; V5 partial)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:04 from `/project1/lab/BO_particles`

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

`/project1/lab/BO_particles`. Spec: `docs/research/BO_particle_sims.md` section 4 (clean-room; credits there: Tim
Gerritsen's Compute Particle System, CC BY 4.0, for the state-texture + instanced-fetch idea; Bridson et al. 2007 curl
noise). **Status: v1 built live 26 Oct on 31550 (`panel=False`, zkit blocked by T-84); V0 V1 V3 V4 V6 pass, V5 partial (T-84); `output/backups/BO_particles_v1.tox`.** Everything marked **LIVE CHECK** must be confirmed
on 31550 and written to LEARNINGS (new T-nn) by the live lane.

Build doc: `docs/builds/particles.md`

## Inputs / outputs

- in `in_ctl` (inCHOP)
- in `in_emit` (inTOP) 128x128
- in `in_field` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920
- out `out_info` (outCHOP)
- out `out_state` (outTOP) 768x256

## Custom parameters

### System

| name | label | style | default | value |
|---|---|---|---|---|
| Play | Play | Toggle | True | True |
| Reset | Reset | Pulse | False | False |
| Seed | Seed | Int | 1 | 1 |
| Count | Count (re-inits) | Int | 65536 | 65536 |
| Speed | Speed | Float | 1.0 | 1.0 |
| Stagger | Stagger first births | Toggle | True | True |
| Statemode | State mode | Menu | feedback | feedback |
| Debugstamp | Debug: frame stamp | Toggle | False | False |
| Resx | Resx | Int | 1080 | 1080 |
| Resy | Resy | Int | 1920 | 1920 |

### Emit

| name | label | style | default | value |
|---|---|---|---|---|
| Source | Source | Menu | ball | ball |
| Emitinput | Emit TOP | Menu | auto | auto |
| Emitweight | Emit weight | Menu | luma | luma |
| Emitmode | Emit mode | Menu | continuous | continuous |
| Rate | Rate /s | Float | 5000.0 | 5000.0 |
| Life | Life | Float | 4.0 | 4.0 |
| Lifevar | Life var | Float | 0.5 | 0.5 |
| Emitposx | Emit pos | XYZW | 0.0 | 0.0 |
| Emitposy | Emit pos | XYZW | 0.0 | 0.0 |
| Emitposz | Emit pos | XYZW | 0.0 | 0.0 |
| Emitsizex | Emit size | XYZW | 0.3 | 0.3 |
| Emitsizey | Emit size | XYZW | 0.3 | 0.3 |
| Emitsizez | Emit size | XYZW | 0.3 | 0.3 |
| Emitdirx | Emit dir | XYZW | 0.0 | 0.0 |
| Emitdiry | Emit dir | XYZW | 1.0 | 1.0 |
| Emitdirz | Emit dir | XYZW | 0.0 | 0.0 |
| Initspeed | Init speed | Float | 0.2 | 0.2 |
| Initspread | Init spread | Float | 1.0 | 1.0 |
| Emitthreshold | Emit threshold | Float | 0.1 | 0.1 |
| Burst | Burst | Pulse | False | False |
| Burstcount | Burst count | Int | 5000 | 5000 |
| Strands | Strand seeds | Int | 9 | 9 |
| Strandjitter | Strand jitter | Float | 0.02 | 0.02 |
| Initspeedvar | Init speed variation | Float | 0.0 | 0.0 |

### Forces

| name | label | style | default | value |
|---|---|---|---|---|
| Curlstrength | Curl | Float | 1.0 | 1.0 |
| Curlscale | Curl scale | Float | 1.5 | 1.5 |
| Curlspeed | Curl speed | Float | 0.3 | 0.3 |
| Curloctaves | Curl octaves | Int | 1 | 1 |
| Gravityx | Gravity | XYZW | 0.0 | 0.0 |
| Gravityy | Gravity | XYZW | 0.0 | 0.0 |
| Gravityz | Gravity | XYZW | 0.0 | 0.0 |
| Drag | Drag | Float | 0.8 | 0.8 |
| Windx | Wind | XYZW | 0.0 | 0.0 |
| Windy | Wind | XYZW | 0.0 | 0.0 |
| Windz | Wind | XYZW | 0.0 | 0.0 |
| Att1on | Attractor 1 | Toggle | False | False |
| Att1posx | Att 1 pos | XYZW | 0.0 | 0.0 |
| Att1posy | Att 1 pos | XYZW | 1.0 | 1.0 |
| Att1posz | Att 1 pos | XYZW | 0.0 | 0.0 |
| Att1strength | Att 1 strength | Float | 0.5 | 0.5 |
| Att1soft | Att 1 soft | Float | 0.05 | 0.05 |
| Att2on | Attractor 2 | Toggle | False | False |
| Att2posx | Att 2 pos | XYZW | 0.0 | 0.0 |
| Att2posy | Att 2 pos | XYZW | -1.0 | -1.0 |
| Att2posz | Att 2 pos | XYZW | 0.0 | 0.0 |
| Att2strength | Att 2 strength | Float | 0.5 | 0.5 |
| Att2soft | Att 2 soft | Float | 0.05 | 0.05 |
| Vortexon | Vortex | Toggle | False | False |
| Vortexaxisx | Vortex axis | XYZW | 0.0 | 0.0 |
| Vortexaxisy | Vortex axis | XYZW | 1.0 | 1.0 |
| Vortexaxisz | Vortex axis | XYZW | 0.0 | 0.0 |
| Vortexstrength | Vortex strength | Float | 0.5 | 0.5 |
| Fieldstrength | Field (in_field) | Float | 0.0 | 0.0 |
| Bounds | Bounds | Menu | wrap | wrap |
| Boundsizex | Bound size | XYZW | 2.5 | 2.5 |
| Boundsizey | Bound size | XYZW | 4.5 | 4.5 |
| Boundsizez | Bound size | XYZW | 2.5 | 2.5 |
| Floor | Floor | Toggle | False | False |
| Floory | Floor y | Float | -3.0 | -3.0 |
| Bounce | Bounce | Float | 0.5 | 0.5 |
| Sp1on | Spiral 1 | Toggle | False | False |
| Sp1posx | Spiral 1 centre | XYZW | 0.0 | 0.0 |
| Sp1posy | Spiral 1 centre | XYZW | 0.0 | 0.0 |
| Sp1posz | Spiral 1 centre | XYZW | 0.0 | 0.0 |
| Sp1axisx | Spiral 1 axis | XYZW | 0.0 | 0.0 |
| Sp1axisy | Spiral 1 axis | XYZW | 1.0 | 1.0 |
| Sp1axisz | Spiral 1 axis | XYZW | 0.0 | 0.0 |
| Sp1swirl | Spiral 1 swirl | Float | 1.5 | 1.5 |
| Sp1pull | Spiral 1 pull in | Float | 0.5 | 0.5 |
| Sp1lift | Spiral 1 lift (along axis) | Float | 0.0 | 0.0 |
| Sp1radius | Spiral 1 radius (falloff, 0 = none) | Float | 1.0 | 1.0 |
| Sp2on | Spiral 2 | Toggle | False | False |
| Sp2posx | Spiral 2 centre | XYZW | 0.0 | 0.0 |
| Sp2posy | Spiral 2 centre | XYZW | 1.0 | 1.0 |
| Sp2posz | Spiral 2 centre | XYZW | 0.0 | 0.0 |
| Sp2axisx | Spiral 2 axis | XYZW | 1.0 | 1.0 |
| Sp2axisy | Spiral 2 axis | XYZW | 0.0 | 0.0 |
| Sp2axisz | Spiral 2 axis | XYZW | 0.0 | 0.0 |
| Sp2swirl | Spiral 2 swirl | Float | 1.5 | 1.5 |
| Sp2pull | Spiral 2 pull in | Float | 0.5 | 0.5 |
| Sp2lift | Spiral 2 lift (along axis) | Float | 0.0 | 0.0 |
| Sp2radius | Spiral 2 radius (falloff, 0 = none) | Float | 1.0 | 1.0 |

### Audio

| name | label | style | default | value |
|---|---|---|---|---|
| Audiosrc | Audio | Menu | off | off |
| Bpm | BPM | Float | 120.0 | 120.0 |
| Tapnudge | Phase nudge | Float | 0.0 | 0.0 |
| Chop | CHOP (kick bass mid high level) | CHOP |  | /project1/lab/AC_audio/out_ctl |
| Smooth | Smooth s | Float | 0.05 | 0.05 |
| Amtcurl | Bass -> curl | Float | 0.0 | 0.0 |
| Amtsize | Kick -> size | Float | 0.0 | 0.0 |
| Amtbright | Level -> bright | Float | 0.0 | 0.0 |
| Amtburst | Kick -> burst | Float | 0.0 | 0.0 |
| Amtatt | Mid -> attract | Float | 0.0 | 0.0 |
| Amtspeed | Level -> speed | Float | 0.0 | 0.0 |
| Manual1 | Manual kick | Float | 0.0 | 0.0 |
| Manual2 | Manual bass | Float | 0.0 | 0.0 |
| Manual3 | Manual mid | Float | 0.0 | 0.0 |
| Manual4 | Manual high | Float | 0.0 | 0.0 |
| Autohit | Auto: kick fires bursts (Kick -> burst) | Toggle | True | True |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Size | Size | Float | 0.012 | 0.012 |
| Sizevar | Size var | Float | 0.5 | 0.5 |
| Sizeage | Size by age | Float | 0.5 | 0.5 |
| Colormode | Colour mode | Menu | age | age |
| Speedref | Speed ref | Float | 2.0 | 2.0 |
| Bright | Bright | Float | 0.6 | 0.6 |
| Blend | Blend | Menu | add | add |
| Softness | Softness | Float | 0.6 | 0.6 |
| Trails | Trails | Toggle | False | False |
| Trailfade | Trail keep | Float | 0.9 | 0.9 |
| Bloom | Bloom | Float | 0.0 | 0.0 |
| Shape | Particle shape | Menu | dot | dot |
| Spinrate | Spin / twist rev per s | Float | 1.5 | 1.5 |
| Paperaspect | Paper aspect (h / w) | Float | 0.6 | 0.6 |
| Ambient | Paper dark side | Float | 0.25 | 0.25 |
| Lightdirx | Paper light dir | XYZW | 0.3 | 0.3 |
| Lightdiry | Paper light dir | XYZW | 0.6 | 0.6 |
| Lightdirz | Paper light dir | XYZW | 1.0 | 1.0 |
| Streamerlen | Streamer length (x size) | Float | 6.0 | 6.0 |
| Flutter | Flutter force (sideways sine) | Float | 0.0 | 0.0 |
| Flutterhz | Flutter rate Hz | Float | 1.2 | 1.2 |

### Colours

| name | label | style | default | value |
|---|---|---|---|---|
| Colour1r | Young | RGBA | 1.0 | 1.0 |
| Colour1g | Young | RGBA | 0.55 | 0.55 |
| Colour1b | Young | RGBA | 0.2 | 0.2 |
| Colour2r | Middle | RGBA | 0.95 | 0.95 |
| Colour2g | Middle | RGBA | 0.2 | 0.2 |
| Colour2b | Middle | RGBA | 0.6 | 0.6 |
| Colour3r | Old | RGBA | 0.2 | 0.2 |
| Colour3g | Old | RGBA | 0.4 | 0.4 |
| Colour3b | Old | RGBA | 1.0 | 1.0 |
| Linecolr | Trail line colour (solid) | RGBA | 0.25 | 0.25 |
| Linecolg | Trail line colour (solid) | RGBA | 1.0 | 1.0 |
| Linecolb | Trail line colour (solid) | RGBA | 0.4 | 0.4 |

### Camera

| name | label | style | default | value |
|---|---|---|---|---|
| Camdist | Distance | Float | 6.0 | 6.0 |
| Fov | FOV | Float | 45.0 | 45.0 |
| Orbit | Orbit deg/s | Float | 0.0 | 0.0 |
| Camx | Pan x | Float | 0.0 | 0.0 |
| Camy | Pan y | Float | 0.0 | 0.0 |
| Ortho | Ortho | Toggle | False | False |

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
| Zkm1 | Energy | Float | 0.0 | 0.4 |
| Zkm2 | Chaos | Float | 0.0 | 0.5 |
| Zkm3 | Glow | Float | 0.0 | 0.4 |
| Zkm4 | Size | Float | 0.0 | 0.4 |

### About

| name | label | style | default | value |
|---|---|---|---|---|
| Version | Version | Str |  | 0.1.0 |
| Touchbuild | Touch build | Str |  | 2025.31550 |
| Saved | Saved | Str |  | 2026-10-26 16:46 |

### Effectors

| name | label | style | default | value |
|---|---|---|---|---|
| Effon | Effectors on (/project1/effectors) | Toggle | False | False |
| Effselect | Use effectors (all / names / #tags) | StrMenu | all | all |
| Effgain | Weight gain | Float | 1.0 | 1.0 |
| Effcombine | Combine | Menu | max | max |
| Effradscale | Radius scale | Float | 1.0 | 1.0 |
| Effragged | Ragged edge | Float | 0.0 | 0.0 |
| Effraggedfreq | Ragged freq | Float | 4.0 | 4.0 |
| Effoverride | Own falloff (ignore per-effector) | Toggle | False | False |
| Effradius | Own radius | Float | 0.5 | 0.5 |
| Effexp | Own exponent | Float | 1.0 | 1.0 |
| Effshape | Own shape | Menu | smooth | smooth |
| Effpush | Push (outward) | Float | 2.0 | 2.0 |
| Effattract | Attract (to the surface) | Float | 0.0 | 0.0 |
| Effvortex | Vortex (around the up axis) | Float | 0.0 | 0.0 |
| Effwake | Wake (effector velocity) | Float | 0.0 | 0.0 |
| Effdrag | Drag near effectors | Float | 0.0 | 0.0 |
| Effkill | Kill at weight (0 = off) | Float | 0.0 | 0.0 |
| Effspawn | Spawn at effectors (fraction) | Float | 0.0 | 0.0 |
| Effspawnr | Spawn radius | Float | 0.2 | 0.2 |

### Palette

| name | label | style | default | value |
|---|---|---|---|---|
| Palsource | Palette | Menu | neon_trio | neon_trio |
| Palmode | Palette mode | Menu | gradient | gradient |
| Palinterp | Blend space | Menu | oklab | oklab |
| Palreverse | Reverse palette | Toggle | False | False |
| Palshift | Palette shift (drive me) | Float | 0.0 | 0.0 |
| Palby | Dots palette by | Menu | age | age |
| Palpos | Palette position | Float | 0.0 | 0.0 |
| Palspread | Palette spread | Float | 1.0 | 1.0 |

### Lines

| name | label | style | default | value |
|---|---|---|---|---|
| Lineson | Light trails (PX_lines on the particles) | Toggle | False | False |
| Linedots | Draw the dots too | Toggle | True | True |
| Linetracks | Trails (tracks) | Int | 1024 | 1024 |
| Linesamples | Samples per trail | Int | 32 | 32 |
| Lineevery | Frames per sample | Int | 1 | 1 |
| Linewidth | Core width px | Float | 1.5 | 1.5 |
| Linehalo | Halo px | Float | 3.0 | 3.0 |
| Linehalogain | Halo gain | Float | 0.35 | 0.35 |
| Lineintensity | Intensity (HDR) | Float | 1.5 | 1.5 |
| Linetaper | Width taper | Float | 1.0 | 1.0 |
| Linefade | Fade along | Float | 1.0 | 1.0 |
| Linemaxjump | Max jump (respawn = new trail) | Float | 0.5 | 0.5 |
| Linecolsrc | Trail colour | Menu | attr | attr |
| Lineattr | Trail attribute | Menu | along | along |
| Linepalpos | Trail palette position | Float | 0.0 | 0.0 |
| Linepalspread | Trail palette spread | Float | 1.0 | 1.0 |
| Lineblend | Trail blend | Menu | add | add |

## Perf

cook 124.325 ms (CPU 124.325 / GPU 0.996) summed over the 11 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "BO_particles", "parent": "/project1/lab"}` (lands parked)
