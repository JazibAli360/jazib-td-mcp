# AC_audio

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:09:34 from `/project1/lab/AC_audio`

## Inputs / outputs

- out `ctl_out` (outCHOP)
- out `spec_out` (outTOP) 256x1

## Custom parameters

### Audio

| name | label | style | default | value |
|---|---|---|---|---|
| Audiofile | Audio file | File |  | ~/Documents/StageLab_PrismFest/jazib-td-mcp/media/demo/audio/aa_house128_breakdown.wav |
| Trim | Trim | Float | 0.0 | 1.7466300000000001 |
| Depth | Depth | Float | 0.0 | 0.7 |
| Source | Analyse | Menu | file | device |
| Specgain | Spectrum gain | Float | 5.0 | 5.0 |
| Opencontrols | Open controls window | Pulse | False | False |
| Features | Merge AU_features (out_ctl_feat) | Toggle | False | False |
| Featurespath | Features CHOP | Str | ../AU_features/out_features | ../AU_features/out_features |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 56 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |

## Perf

cook 241.59 ms (CPU 241.59 / GPU 0.249) summed over the 13 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "AC_audio", "parent": "/project1/lab"}` (lands parked)
