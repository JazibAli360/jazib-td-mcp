# MX_prox_material

> MX_prox_material: proximity-driven PBR material for any mesh (26 Oct 2026, TD 2025.31550)

v0.3.0 - TD 2025.31550 - exported 2026-10-29 00:09:03 from `/project1/lab/MX_prox_material`

`/project1/lab/MX_prox_material`. User ask (26 Oct): "yes add proximity pbr materials for meshes too" + "proximity can
be just points too - like in ruben fros videos" (`px_requirements.md` item 8). Effector objects (box / sphere / plane
Geometry COMPs, Nulls) and **point sets** (CHOP / TOP / SOP / POP points: face landmarks, depth points, particles, mesh
vertices) drive **lit PBR material properties** and **vertex displacement** of any mesh.

**Status: LIVE-VERIFIED v1 on 31550 (26 Oct), parked.** Offline: 33 tests (`python3 -I -m unittest discover -s test -p
'test_prox_mat.py'`, ~1 s): par / row / header agreement, shader rows, menus vs shader indices, packing, point paths,
CHOP point parsing (samples + FT_face_track channel layout), point images, field vs brute force (numpy), drive maths,
known-distance displacement numbers, combine / flip / gain, effector shapes, presets, glslc compiles of all 4 stages
against TD stubs, builder API + T-70/T-74 text rules.

Build doc: `docs/builds/prox_mat.md`

## Inputs / outputs

- out `out1` (outTOP) 1080x1920

## Custom parameters

### Effectors

| name | label | style | default | value |
|---|---|---|---|---|
| Effectors | Effectors (names / paths) | StrMenu | eff_box eff_sphere eff_null | eff_box eff_sphere eff_null |
| Radius | Radius (falloff width) | Float | 0.6 | 1.72 |
| Falloffexp | Falloff exponent | Float | 1.0 | 2.93 |
| Shape | Falloff shape | Menu | smooth | smooth |
| Combine | Combine effectors | Menu | max | max |
| Gain | Weight gain | Float | 1.0 | 0.695 |
| Flip | Flip (far = 1) | Toggle | False | False |
| Ragged | Ragged edge (noise x Radius) | Float | 0.0 | 1.291 |
| Raggedfreq | Ragged noise freq | Float | 4.0 | 5.0 |
| Track | Update effectors | Menu | change | change |
| Effsource | Effector source | Menu | list | list |
| Effselect | List: use (all / names / #tags) | StrMenu | all | all |
| Listfalloff | List: falloff from | Menu | effector | effector |

### Points

| name | label | style | default | value |
|---|---|---|---|---|
| Pointsource | Point set source | Menu | none | none |
| Pointop | Point op (path) | Str |  |  |
| Pointlayout | CHOP layout | Menu | auto | auto |
| Pointchans | CHOP xyz channels (samples layout) | Str | tx ty tz | tx ty tz |
| Topstride | TOP texels per point | Int | 1 | 1 |
| Topoffset | TOP texel offset | Int | 0 | 0 |
| Pointscalex | Point scale | XYZW | 1.0 | 1.0 |
| Pointscaley | Point scale | XYZW | 1.0 | 1.0 |
| Pointscalez | Point scale | XYZW | 1.0 | 1.0 |
| Pointoffsetx | Point offset | XYZW | 0.0 | 0.0 |
| Pointoffsety | Point offset | XYZW | 0.0 | 0.0 |
| Pointoffsetz | Point offset | XYZW | 0.0 | 0.0 |
| Pointspace | Point space COMP (optional) | Str |  |  |
| Pointmax | Max points (stride decimate) | Int | 4096 | 4096 |
| Pointpath | Point proximity path | Menu | auto | auto |
| Directmax | Direct path max points | Int | 64 | 64 |
| Pointmode | Point mode | Menu | nearest | nearest |
| Pointradius | Point radius | Float | 0.05 | 0.05 |
| Densityfull | Density for full weight | Float | 2.0 | 2.0 |
| Pointweight | Point-set weight | Float | 1.0 | 1.0 |
| Velsmooth | Velocity smoothing | Float | 0.6 | 0.6 |
| Gridres | Field grid cells / axis | Int | 48 | 48 |
| Gridcentrex | Field box centre | XYZW | 0.0 | 0.0 |
| Gridcentrey | Field box centre | XYZW | 0.0 | 0.0 |
| Gridcentrez | Field box centre | XYZW | 0.0 | 0.0 |
| Gridsizex | Field box size | XYZW | 4.0 | 4.0 |
| Gridsizey | Field box size | XYZW | 4.0 | 4.0 |
| Gridsizez | Field box size | XYZW | 4.0 | 4.0 |

### Colour

| name | label | style | default | value |
|---|---|---|---|---|
| Basecolourr | Base colour | RGBA | 0.55 | 0.08 |
| Basecolourg | Base colour | RGBA | 0.55 | 0.07 |
| Basecolourb | Base colour | RGBA | 0.6 | 0.07 |
| Basealpha | Base alpha | Float | 1.0 | 1.0 |
| Pointcolour | Multiply by point colour (Cd, as TD PBR) | Toggle | True | True |
| Colourmode | Colour mode | Menu | tint | ramp |
| Colournearr | Near colour | RGBA | 1.0 | 1.0 |
| Colournearg | Near colour | RGBA | 0.35 | 0.32 |
| Colournearb | Near colour | RGBA | 0.1 | 0.05 |
| Colourfarr | Far colour (ramp) | RGBA | 0.1 | 0.08 |
| Colourfarg | Far colour (ramp) | RGBA | 0.12 | 0.07 |
| Colourfarb | Far colour (ramp) | RGBA | 0.2 | 0.07 |
| Colouramt | Colour amount | Float | 1.0 | 1.0 |
| Colourcurve | Colour curve | Float | 1.0 | 1.5 |
| Huenear | Hue shift near (turns) | Float | 0.25 | 0.25 |

### Surface

| name | label | style | default | value |
|---|---|---|---|---|
| Roughnear | Roughness near | Float | 0.15 | 0.25 |
| Roughfar | Roughness far | Float | 0.6 | 0.85 |
| Roughcurve | Roughness curve | Float | 1.0 | 1.0 |
| Metalnear | Metallic near | Float | 0.0 | 0.0 |
| Metalfar | Metallic far | Float | 0.0 | 0.0 |
| Metalcurve | Metallic curve | Float | 1.0 | 1.0 |
| Specular | Specular level | Float | 0.5 | 0.5 |
| Ao | Ambient occlusion | Float | 1.0 | 1.0 |
| Nrmnear | Detail normal near | Float | 0.0 | 0.6 |
| Nrmfar | Detail normal far | Float | 0.0 | 0.0 |
| Nrmcurve | Detail normal curve | Float | 1.0 | 1.0 |
| Nrmfreq | Detail noise freq | Float | 6.0 | 9.0 |
| Nrmspeed | Detail noise speed | Float | 0.0 | 0.0 |
| Nrmoct | Detail octaves | Int | 3 | 2 |
| Shadowstrength | Shadow strength | Float | 1.0 | 1.0 |
| Shadowcolourr | Shadow colour | RGBA | 0.0 | 0.0 |
| Shadowcolourg | Shadow colour | RGBA | 0.0 | 0.0 |
| Shadowcolourb | Shadow colour | RGBA | 0.0 | 0.0 |

### Emission

| name | label | style | default | value |
|---|---|---|---|---|
| Emitbaser | Base emission | RGBA | 0.0 | 0.0 |
| Emitbaseg | Base emission | RGBA | 0.0 | 0.0 |
| Emitbaseb | Base emission | RGBA | 0.0 | 0.0 |
| Emitcolourr | Proximity emission colour | RGBA | 1.0 | 1.0 |
| Emitcolourg | Proximity emission colour | RGBA | 0.45 | 0.35 |
| Emitcolourb | Proximity emission colour | RGBA | 0.12 | 0.06 |
| Emitnear | Emission near | Float | 0.0 | 4.0 |
| Emitfar | Emission far | Float | 0.0 | 0.0 |
| Emitcurve | Emission curve | Float | 1.0 | 2.0 |
| Rimcolourr | Rim colour | RGBA | 0.4 | 0.4 |
| Rimcolourg | Rim colour | RGBA | 0.7 | 0.7 |
| Rimcolourb | Rim colour | RGBA | 1.0 | 1.0 |
| Rimnear | Rim glow near | Float | 0.0 | 0.0 |
| Rimfar | Rim glow far | Float | 0.0 | 0.0 |
| Rimcurve | Rim curve | Float | 1.0 | 1.0 |
| Rimpower | Rim power (fresnel) | Float | 3.0 | 3.0 |

### Dissolve

| name | label | style | default | value |
|---|---|---|---|---|
| Dissolvemode | Dissolve | Menu | off | near |
| Dissolvecurve | Dissolve curve | Float | 1.0 | 1.4 |
| Dissolveoffset | Dissolve offset | Float | 0.0 | 0.0 |
| Noisescale | Edge noise scale | Float | 5.0 | 5.0 |
| Noiseoct | Edge noise octaves | Int | 3 | 3 |
| Noisespeed | Edge noise speed | Float | 0.2 | 0.2 |
| Burnwidth | Burnt rim width | Float | 0.08 | 0.08 |
| Burncolourr | Burnt rim colour | RGBA | 1.0 | 1.0 |
| Burncolourg | Burnt rim colour | RGBA | 0.4 | 0.4 |
| Burncolourb | Burnt rim colour | RGBA | 0.05 | 0.05 |
| Burnemit | Burnt rim emission | Float | 6.0 | 6.0 |
| Char | Char (darken near the rim) | Float | 0.8 | 0.8 |
| Opacityon | Opacity drive (blending on) | Toggle | False | False |
| Opanear | Opacity near | Float | 1.0 | 1.0 |
| Opafar | Opacity far | Float | 1.0 | 1.0 |
| Opacurve | Opacity curve | Float | 1.0 | 1.0 |

### Displace

| name | label | style | default | value |
|---|---|---|---|---|
| Dispmode | Displace mode | Menu | off | swell |
| Dispnear | Displace near | Float | 0.2 | -0.542 |
| Dispfar | Displace far | Float | 0.0 | 0.0 |
| Dispcurve | Displace curve | Float | 1.0 | 1.0 |
| Dispdir | Direction | Menu | normal | normal |
| Ripplefreq | Ripple freq (rad / unit) | Float | 12.0 | 12.0 |
| Ripplespeed | Ripple speed (rad / s) | Float | 6.0 | 6.0 |
| Dispnoisefreq | Noise freq | Float | 3.0 | 3.0 |
| Wakegain | Wake gain (s) | Float | 0.05 | 0.05 |
| Normalfix | Recompute normals | Toggle | True | True |
| Normaleps | Normal step (world) | Float | 0.01 | 0.01 |
| Dispcache | Vertex cache (displace once per point) | Toggle | True | True |

### Presets

| name | label | style | default | value |
|---|---|---|---|---|
| Preset | Preset | Menu | molten_touch | molten_touch |
| Applypreset | Apply preset | Pulse | False | False |
| Resx | Out width (demo) | Int | 1080 | 1080 |
| Resy | Out height (demo) | Int | 1920 | 1920 |
| Animate | Animate demo effectors | Toggle | True | True |
| Showeff | COMP viewer: preview with gizmos | Toggle | True | True |
| Antialias | Antialias (demo renders) | Menu | aa2 | aa2 |

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
| Zkm1 | Reach | Float | 0.0 | 0.5 |
| Zkm2 | Glow | Float | 0.0 | 0.0 |
| Zkm3 | Ripple | Float | 0.0 | 0.5 |
| Zkm4 | Burn | Float | 0.0 | 0.5 |

### Environment

| name | label | style | default | value |
|---|---|---|---|---|
| Envmode | Environment (demo env1) | Menu | gradient | gradient |
| Envtop | Environment TOP (path) | Str |  |  |
| Envgeo | Scene cube: geometry | StrMenu | geo_torus geo_plane | geo_torus geo_plane |
| Envcentrex | Scene cube: centre (the chrome object) | XYZW | 0.0 | 0.0 |
| Envcentrey | Scene cube: centre (the chrome object) | XYZW | 1.35 | 1.35 |
| Envcentrez | Scene cube: centre (the chrome object) | XYZW | 0.0 | 0.0 |
| Envres | Scene cube px | Int | 256 | 256 |
| Enveveryn | Scene cube every N frames | Int | 4 | 4 |
| Envdimmer | Environment dimmer | Float | 0.8 | 0.8 |

## Perf

cook 285.189 ms (CPU 285.189 / GPU 10.796) summed over the 7 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "MX_prox_material", "parent": "/project1/lab"}` (lands parked)
