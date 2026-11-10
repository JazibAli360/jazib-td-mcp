# MIDI_mapper

v0.1.0 - TD 2025.31550 - exported 2026-10-26 19:46:35 from `/project1/lab/MIDI_mapper`

## Inputs / outputs

- none

## Custom parameters

### MIDI

| name | label | style | default | value |
|---|---|---|---|---|
| Enable | Enable | Toggle | True | True |
| Device | Device (MIDI Device Mapper id) | Menu | 1 | 1 |
| Activebank | Active bank (0 = always) | Int | 1 | 1 |
| Learn | Learn (hover a par, move a control) | Pulse | False | False |
| Feedback | LED feedback | Toggle | True | True |
| Sendfeedback | Send all feedback | Pulse | False | False |
| Openeditor | Open editor | Pulse | False | False |
| Refreshdevices | Refresh devices | Pulse | False | False |

## Perf

cook 0.605 ms (CPU 0.605 / GPU 0.0) summed over the 10 ops that cooked in the last frame at export (0 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- `midi_out` file `untitled.midi` (repo, MISSING)

## Load

`td_library_load {"name": "MIDI_mapper", "parent": "/project1/lab"}` (lands parked)
