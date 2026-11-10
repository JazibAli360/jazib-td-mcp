# FX_destroy

> fx_destroy: FX_destroy rack + 6 modules `melt`, `burn`, `shatter`, `crack`, `explode`, `disintegrate` (26-27 Oct 2026, TD 2025.31550)

v0.1.0 - TD 2025.31550 - exported 2026-10-29 00:08:13 from `/project1/lab/FX_destroy`

`/project1/lab/FX_destroy`. The destruction COMP (FX1 DG-14 / DG-18 / DG-15). It is the **same lean rack as
FX_glitch** (`docs/builds/fx_glitch.md`), copied rather than abstracted: `slots` table (name module enabled order mix),
a slot = module COMP + Cross (`<name>_mix`) + Switch (`<name>_slot`), Panic toggle, zkit panel + presets per module,
`test_clip` / `in1` input. Module X = `builders/fx_destroy_X.py`. No codegen, no registry.

```python
ns = dict(globals()); exec(open('<repo>/builders/fx_destroy.py').read(), ns)
ns['build']('/project1/lab')                          # rack + melt1 / burn1 / shatter1 on first build; idempotent
ns['add']('/project1/lab/FX_destroy', 'shatter')       # shatter2, wired last
ns['remove']('/project1/lab/FX_destroy', 'shatter2'); ns['rewire'](op('/project1/lab/FX_destroy'))
```

Build doc: `docs/builds/fx_destroy.md`

## Inputs / outputs

- in `in1` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920

## Custom parameters

### Rack

| name | label | style | default | value |
|---|---|---|---|---|
| Panic | Panic (passthrough) | Toggle | False | False |
| Input | Input | Menu | auto | auto |

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
| Effcentrex | Plane centre (world) | XYZW | 0.0 | 0.0 |
| Effcentrey | Plane centre (world) | XYZW | 0.0 | 0.0 |
| Effcentrez | Plane centre (world) | XYZW | 0.0 | 0.0 |
| Effplanew | Plane width (world) | Float | 1.0 | 1.0 |
| Effplaneh | Plane height (world) | Float | 1.0 | 1.0 |

## Perf

cook 11.328 ms (CPU 11.328 / GPU 1.571) summed over the 16 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "FX_destroy", "parent": "/project1/lab"}` (lands parked)
