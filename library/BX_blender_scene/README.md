# BX_blender_scene

v0.1.0 - TD 2025.31550 - exported 2026-10-26 19:47:40 from `/project1/lab/BX_blender_scene`

## Inputs / outputs

- none

## Custom parameters

### Blender

| name | label | style | default | value |
|---|---|---|---|---|
| Camera | Camera | Menu | cam_Cam_FOH | cam_Cam_FOH |
| Lightdimmer | Light dimmer | Float | 1.0 | 1.0 |
| Ambient | Ambient | Float | 0.15 | 0.15 |
| Resw | Render width | Int | 1920 | 1920 |
| Resh | Render height | Int | 1080 | 1080 |

## Perf

cook 0.465 ms (CPU 0.465 / GPU 0.0) summed over the 7 ops that cooked in the last frame at export (0 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "BX_blender_scene", "parent": "/project1/lab"}` (lands parked)
