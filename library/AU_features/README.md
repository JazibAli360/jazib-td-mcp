# AU_features

> au_features - `/project1/lab/AU_features` (TD 2025.31550, 26 Oct 2026)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:07:48 from `/project1/lab/AU_features`

Audio features from the **EssentiaTD v2.0.3** C++ CHOPs (Rhythm, Loudness, Tonal, Spectral), loaded **by absolute
path** at runtime from `helpers/installs/disabled/Essentia/` (T-99), never from the per-user Plugins folder (T-81).
One clean Out CHOP of named channels for looks, the show rig and AC_audio.

**State:** built and verified on the **main TD** (plugins loaded there, Analysison on), then parked (allowCooking off).
The plugins stay loaded for the session (T-106: never unload). Turning it on: un-park the COMP; a fresh session pays
one 1.3-2.3 s stall per plugin on the first `Analysison` (staggered 30 frames apart) - do it before doors.

Build doc: `docs/builds/au_features.md`

## Inputs / outputs

- in `in1` (inCHOP)
- out `out1` (outCHOP)

## Custom parameters

### Features

| name | label | style | default | value |
|---|---|---|---|---|
| Bpmrange | BPM range | Menu | wide | wide |
| Bpmmin | BPM min (custom) | Float | 60.0 | 60.0 |
| Bpmmax | BPM max (custom) | Float | 180.0 | 180.0 |
| Onsetsens | Onset sensitivity | Float | 0.5 | 0.5 |
| Onsetmethod | Onset method | Menu | complex | complex |
| Beatdecay | Beat pulse decay s | Float | 0.25 | 0.25 |
| Lufsfloor | Loud floor LUFS | Float | -60.0 | -60.0 |
| Keymode | Key mode | Menu | windowed | windowed |
| Resetcounts | Reset counters | Pulse | False | False |
| Bpmsource | BPM from | Menu | beats | beats |
| Bandfloor | Band floor dBFS (bass / mid / high) | Float | -60.0 | -60.0 |

### Setup

| name | label | style | default | value |
|---|---|---|---|---|
| Analysison | Analysis on (loads the Essentia plugins) | Toggle | False | True |
| Source | Source | Menu | file | file |
| Audiofile | Audio file | File | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/demo/audio_tests/kick_128bpm_30s.wav | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/demo/audio_tests/kick_128bpm_30s.wav |
| Acaudiopath | AC_audio mono CHOP | Str | ../AC_audio/n_mono | ../AC_audio/n_mono |
| Pluginfolder | Essentia plugin folder | Folder | ~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/installs/disabled/Essentia/ | ~/Documents/StageLab_PrismFest/jazib-td-mcp/helpers/installs/disabled/Essentia/ |
| Reinitplugins | Re-init analysers (clears key/BPM history) | Pulse | False | False |
| Alwayscook | Cook every frame (needed for BPM/onsets) | Toggle | True | True |

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
| Zkm1 | Reactive | Float | 0.0 | 0.5 |
| Zkm2 | Tempo window | Float | 0.0 | 0.5 |

## Perf

cook 14.626 ms (CPU 14.626 / GPU 0.0) summed over the 61 ops that cooked in the last frame at export (0 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "AU_features", "parent": "/project1/lab"}` (lands parked)
