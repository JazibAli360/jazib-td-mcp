# PX_pointfx

> PX_pointfx: modular point-cloud / splat FX (live in main, splats verified 27 Oct 2026, TD 2025.31550)

v0.6.1 - TD 2025.31550 - exported 2026-10-29 00:09:29 from `/project1/lab/PX_pointfx`

`/project1/lab/PX_pointfx`. A point cloud (file scan, Gaussian splat scene, the depth camera, or a generated shape,
or a morph between two of them, plus an optional **actor layer** and an **ember pool**) goes through a **stack of
effector modules** that the user adds, removes, reorders and duplicates. Proximity modules are driven by **visible
effector objects** (boxes, spheres, planes, Nulls, CHOP points, point sets, the actor, the camera) seen as gizmos in a
preview; effectors can follow **motion paths**, leave **trails** and **glow** in the output. The look is rendered as
sprites (soft / shapes / oriented cubes and slabs) or as **real anisotropic Gaussian splats** (BL_splat_render's shader,
reused) and graded to `out1`.
Binding user rules: `docs/builds/px_requirements.md` (items 1-9). Look research + per-module maths:
`docs/research/BR_rubenfro_pointcloud_fx.md` (section 4; v2 = the 4b/4c effector study). Splat / point-cloud loaders:
`BL_gaussian_splats_pointclouds.md`, reused from `BL_splat_render` / `BL_cloud_morph` (their `*_logic.py` files are
copied in read-only; `splat_render.glsl` is read at build time and shared through empty-by-default hooks). Clean-room.

Build doc: `docs/builds/px.md`

## Inputs / outputs

- in `in_ctl` (inCHOP)
- in `in_depth` (inTOP) 128x128
- in `in_eff` (inCHOP)
- in `in_mask` (inTOP) 128x128
- in `in_video` (inTOP) 128x128
- in `in_xyz` (inTOP) 128x128
- out `out1` (outTOP) 1080x1920
- out `out_info` (outCHOP)
- out `out_preview` (outTOP) 540x960
- out `out_state` (outTOP) 2390x478

## Custom parameters

### Source

| name | label | style | default | value |
|---|---|---|---|---|
| Quality | Quality | Menu | std | custom |
| Count | Count (Quality custom) | Int | 131072 | 228287 |
| Amode | A source | Menu | gen | file |
| Afile | A file | File |  | ~/Downloads/Classroom of Class 6 Grade 9, China/scene.ply |
| Agen | A generator | Menu | sphere | sphere |
| Agenp | A size | Float | 1.0 | 1.79 |
| Agenp2 | A param 2 | Float | 0.3 | 0.3 |
| Agenp3 | A param 3 | Float | 0.0 | 1.6 |
| Aspin | A spin rad/s | Float | 0.0 | 0.0 |
| Acolmode | A colour | Menu | position | position |
| Acolourr | A solid colour | RGBA | 1.0 | 1.0 |
| Acolourg | A solid colour | RGBA | 1.0 | 1.0 |
| Acolourb | A solid colour | RGBA | 1.0 | 1.0 |
| Ascale | Ascale | Float | 1.0 | 1.0 |
| Arot | A rotate y deg | Float | 0.0 | 0.0 |
| Aoffsetx | Aoffset | XYZW | 0.0 | 0.0 |
| Aoffsety | Aoffset | XYZW | 0.0 | 0.0 |
| Aoffsetz | Aoffset | XYZW | 0.0 | 0.0 |
| Aup | A file up axis | Menu | y | y |
| Bmode | B source | Menu | off | off |
| Bfile | B file | File |  |  |
| Bgen | B generator | Menu | torus | torus |
| Bgenp | B size | Float | 1.0 | 1.0 |
| Bgenp2 | B param 2 | Float | 0.3 | 0.3 |
| Bgenp3 | B param 3 | Float | 0.0 | 0.0 |
| Bspin | B spin rad/s | Float | 0.0 | 0.0 |
| Bcolmode | B colour | Menu | position | position |
| Bcolourr | B solid colour | RGBA | 1.0 | 1.0 |
| Bcolourg | B solid colour | RGBA | 0.5 | 0.5 |
| Bcolourb | B solid colour | RGBA | 0.2 | 0.2 |
| Bscale | Bscale | Float | 1.0 | 1.0 |
| Brot | B rotate y deg | Float | 0.0 | 0.0 |
| Boffsetx | Boffset | XYZW | 0.0 | 0.0 |
| Boffsety | Boffset | XYZW | 0.0 | 0.0 |
| Boffsetz | Boffset | XYZW | 0.0 | 0.0 |
| Bup | B file up axis | Menu | y | y |
| Morph | Morph A -> B | Float | 0.0 | 0.0 |
| Stagger | Stagger | Float | 0.5 | 0.5 |
| Staggermode | Staggermode | Menu | random | random |
| Arc | Morph arc | Float | 0.3 | 0.3 |
| Ease | Ease | Menu | smooth | smooth |
| Match | File A/B matching | Menu | morton | morton |
| Depthfov | Depth fov deg | Float | 60.0 | 50.2 |
| Depthnear | Depthnear | Float | 1.0 | 1.0 |
| Depthfar | Depthfar | Float | 4.0 | 4.0 |
| Depththr | Depth keep above | Float | 0.02 | 0.02 |
| Depthscale | Depthscale | Float | 1.0 | 1.0 |
| Depthmirror | Depthmirror | Toggle | True | True |
| Depthgain | Depth colour gain | Float | 1.0 | 1.0 |
| Splatscale | Size from splat scale | Toggle | False | False |
| Splatk | Splat size factor | Float | 3.0 | 3.0 |
| Reload | Reload | Pulse | False | False |
| Actormode | Actor source | Menu | off | off |
| Actorfile | Actor file | File |  |  |
| Actorseq | Actor sequence folder (frames) | Folder |  |  |
| Actorfps | Actor sequence fps | Float | 24.0 | 24.0 |
| Actorcount | Actor points | Int | 16384 | 16384 |
| Actorgen | Actor generator | Menu | cylinder | cylinder |
| Actorgenp | Actor size | Float | 0.9 | 0.9 |
| Actorgenp2 | Actor param 2 | Float | 0.3 | 0.3 |
| Actorgenp3 | Actor param 3 | Float | 0.0 | 0.0 |
| Actorspin | Actor spin rad/s | Float | 0.0 | 0.0 |
| Actorscale | Actorscale | Float | 1.0 | 1.0 |
| Actorrot | Actor rotate y deg | Float | 0.0 | 0.0 |
| Actoroffsetx | Actoroffset | XYZW | 0.0 | 0.0 |
| Actoroffsety | Actoroffset | XYZW | 0.0 | 0.0 |
| Actoroffsetz | Actoroffset | XYZW | 0.0 | 0.0 |
| Actorfollow | Actor follows effector (name) | StrMenu |  |  |
| Actorup | Actor file up axis | Menu | y | y |
| Actorcolmode | Actor colour | Menu | solid | solid |
| Actorcolourr | Actor solid colour | RGBA | 1.0 | 1.0 |
| Actorcolourg | Actor solid colour | RGBA | 0.9 | 0.9 |
| Actorcolourb | Actor solid colour | RGBA | 0.8 | 0.8 |
| Actorsamples | Actor effector samples | Int | 256 | 256 |
| Pool | Pool % (ember points) | Float | 0.0 | 0.0 |
| Clip | Load: keep within radius of the median (0 off) | Float | 0.0 | 0.0 |
| Opacitymin | Load: drop splats below opacity (floaters) | Float | 0.0 | 0.0 |
| Pointstop | Points TOP (rgb xyz; else the in_xyz input) | TOP |  |  |
| Echoes | Actor echoes (copies, 0 = off) | Int | 0 | 0 |
| Echoevery | Echo every N frames | Int | 6 | 6 |
| Echofade | Echo fade (alpha gamma) | Float | 1.5 | 1.5 |
| Echooffsetx | Echo offset per copy (stack / gravity) | XYZW | 0.0 | 0.0 |
| Echooffsety | Echo offset per copy (stack / gravity) | XYZW | 0.0 | 0.0 |
| Echooffsetz | Echo offset per copy (stack / gravity) | XYZW | 0.0 | 0.0 |
| Imagefile | Image file (when no Pointstop; image / top modes) | File |  |  |
| Imagerelief | Image relief height (x brightness) | Float | 0.4 | 0.4 |
| Imagesrc | Image height from | Menu | luma | luma |
| Imagecut | Image: drop pixels below (height source) | Float | 0.02 | 0.02 |
| Echoscale | Echo size per copy (x, older = smaller) | Float | 0.8 | 0.8 |
| Echothin | Echo thinning per copy (fraction dropped) | Float | 0.25 | 0.25 |

### Sim

| name | label | style | default | value |
|---|---|---|---|---|
| Play | Play | Toggle | True | True |
| Speed | Speed | Float | 1.0 | 1.0 |
| Reset | Reset | Pulse | False | False |
| Seed | Seed | Int | 1 | 1 |
| Spring | Spring to home | Float | 4.0 | 4.0 |
| Damping | Damping | Float | 1.5 | 1.5 |
| Drag | Drag | Float | 0.2 | 0.2 |
| Maxspeed | Max speed (0 off) | Float | 0.0 | 0.0 |
| Heatdecay | Heatdecay | Float | 0.5 | 0.5 |
| Disrecover | Dissolve heal /s | Float | 1.0 | 1.0 |
| Statemode | Statemode | Menu | feedback | feedback |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Size | Point size (world) | Float | 0.01 | 0.011 |
| Attenuation | Size by depth | Float | 1.0 | 1.0 |
| Minpx | Minpx | Float | 0.7 | 1.6 |
| Maxpx | Maxpx | Float | 64.0 | 64.0 |
| Sprite | Sprite | Menu | soft | soft |
| Softness | Softness | Float | 0.6 | 0.6 |
| Aspect | Aspect | Float | 1.0 | 1.0 |
| Spin | Sprite random spin | Float | 0.0 | 0.0 |
| Streak | Velocity streak | Float | 0.0 | 0.0 |
| Streakmax | Streak max px | Float | 64.0 | 64.0 |
| Blend | Blend | Menu | add | add |
| Hdr | HDR gain | Float | 1.0 | 1.0 |
| Alpha | Alpha | Float | 1.0 | 1.0 |
| Bright | Colour gain (stage) | Float | 1.0 | 1.0 |
| Focus | Focus | Float | 5.0 | 1.3 |
| Aperture | DOF aperture px | Float | 0.0 | 0.0 |
| Maxcoc | Maxcoc | Float | 48.0 | 48.0 |
| Bokehbright | Bokehbright | Float | 1.0 | 1.0 |
| Bokehrim | Bokehrim | Float | 0.5 | 0.5 |
| Minenergy | Minenergy | Float | 0.02 | 0.02 |
| Fog | Depth fog | Float | 0.0 | 0.0 |
| Disfade | Dissolve fade | Float | 1.0 | 1.0 |
| Dissize | Dissolve size | Float | 0.3 | 0.3 |
| Edgegain | Dissolve edge glow | Float | 2.0 | 2.0 |
| Edgecolr | Edge colour | RGBA | 1.0 | 1.0 |
| Edgecolg | Edge colour | RGBA | 0.5 | 0.5 |
| Edgecolb | Edge colour | RGBA | 0.15 | 0.15 |
| Camdist | Camera distance | Float | 4.0 | 1.3 |
| Orbit | Orbit deg/s | Float | 0.0 | 0.0 |
| Camheight | Camheight | Float | 0.0 | 0.15 |
| Fov | Fov | Float | 45.0 | 45.0 |
| Resolution | Render resolution | Menu | 1080x1920 | 1080x1920 |
| Resx | Resx | Int | 1080 | 1080 |
| Resy | Resy | Int | 1920 | 1920 |
| Render | Render | Menu | auto | auto |
| Splatthr | Splat alpha threshold | Float | 0.015 | 0.015 |
| Splatlowpass | Splat low-pass px2 | Float | 0.3 | 0.3 |
| Splatscalemult | Splat scale | Float | 1.0 | 1.0 |
| Sortmode | Sortmode | Menu | auto | auto |
| Sorteveryn | Re-sort every N frames when centres move | Int | 6 | 6 |
| Sortmovedeg | Re-sort after camera deg | Float | 1.0 | 1.0 |
| Sortnow | Sortnow | Pulse | False | False |
| Ptopacity | Sprites: source opacity (splat scenes; 0 = opaque points) | Float | 0.0 | 0.0 |
| Ptcut | Sprites: hide below source opacity | Float | 0.08 | 0.08 |
| Sortmaxhz | Max re-sorts per second (auto; 0 = no cap) | Float | 20.0 | 20.0 |
| Splatmaxpx | Splat max sigma px (0 off) | Float | 0.0 | 0.0 |
| Glyphmode | Glyph / atlas cell | Menu | random | random |
| Glyphrate | Glyph cycle cells/s | Float | 2.0 | 2.0 |
| Atlastop | Atlas TOP (white on black, square grid) | TOP |  |  |
| Atlascols | Atlas cells per row | Int | 4 | 4 |
| Dabjitter | Dab colour jitter | Float | 1.0 | 1.0 |
| Splataa | Splat antialias (MSAA) | Menu | aa1 | aa1 |

### Grade

| name | label | style | default | value |
|---|---|---|---|---|
| Exposure | Exposure | Float | 0.0 | 0.0 |
| Tonemap | Tonemap | Menu | aces | aces |
| Saturation | Saturation | Float | 1.0 | 1.0 |
| Contrast | Contrast | Float | 1.0 | 1.0 |
| Hue | Hue | Float | 0.0 | 0.0 |
| Tealorange | Teal / orange macro | Float | 0.0 | 0.0 |
| Split | Split tone amount | Float | 0.0 | 0.0 |
| Shadowtintr | Shadowtint | RGBA | 0.05 | 0.05 |
| Shadowtintg | Shadowtint | RGBA | 0.25 | 0.25 |
| Shadowtintb | Shadowtint | RGBA | 0.3 | 0.3 |
| Hightintr | Hightint | RGBA | 1.0 | 1.0 |
| Hightintg | Hightint | RGBA | 0.55 | 0.55 |
| Hightintb | Hightint | RGBA | 0.2 | 0.2 |
| Balance | Balance | Float | 0.35 | 0.35 |
| Lift | Lift | Float | 0.0 | 0.0 |
| Gamma | Gamma | Float | 1.0 | 1.0 |
| Gain | Gain | Float | 1.0 | 1.0 |
| Haze | Haze | Float | 0.0 | 0.0 |
| Hazecolr | Hazecol | RGBA | 0.06 | 0.06 |
| Hazecolg | Hazecol | RGBA | 0.12 | 0.12 |
| Hazecolb | Hazecol | RGBA | 0.14 | 0.14 |
| Chromatic | Chromatic | Float | 0.0 | 0.0 |
| Vignette | Vignette | Float | 0.0 | 0.0 |
| Grain | Grain | Float | 0.0 | 0.0 |
| Bloom | Bloom | Float | 0.0 | 0.0 |
| Bloomthr | Bloom threshold | Float | 0.8 | 0.8 |
| Trails | Trails | Toggle | False | False |
| Trailkeep | Trailkeep | Float | 0.85 | 0.85 |
| Flare | Lens flare (ghosts + streak) | Float | 0.0 | 0.0 |
| Flarethr | Flare threshold | Float | 1.5 | 1.5 |
| Flarestreak | Flare streak px | Float | 120.0 | 120.0 |
| Flareghosts | Flareghosts | Int | 3 | 3 |
| Flaredisp | Ghost spacing | Float | 0.35 | 0.35 |
| Flaretintr | Flaretint | RGBA | 1.0 | 1.0 |
| Flaretintg | Flaretint | RGBA | 0.75 | 0.75 |
| Flaretintb | Flaretint | RGBA | 0.55 | 0.55 |
| Bloomknee | Bloom soft knee | Float | 0.0 | 0.0 |
| Bloomtight | Bloom tight scale (1/4 res; 0 = off) | Float | 0.0 | 0.0 |
| Bloomtightspace | Bloom tight tap spacing | Float | 1.0 | 1.0 |
| Bloomclamp | Bloom firefly clamp (0 = off) | Float | 0.0 | 0.0 |
| Bloomtintr | Bloomtint | RGBA | 1.0 | 1.0 |
| Bloomtintg | Bloomtint | RGBA | 1.0 | 1.0 |
| Bloomtintb | Bloomtint | RGBA | 1.0 | 1.0 |
| Bloomsat | Bloom saturation | Float | 1.0 | 1.0 |
| Bloomcolsrc | Bloom colour source | Menu | solid | solid |
| Bloompalpos | Bloom palette position | Float | 0.0 | 0.0 |
| Bloompalspread | Bloom palette spread | Float | 1.0 | 1.0 |
| Bloomkeep | Bloom keep own colour | Float | 0.0 | 0.0 |
| Bloomring | Bloom ring halo | Float | 0.0 | 0.0 |
| Bloomringr | Ring radius (screen height) | Float | 0.12 | 0.12 |
| Bloomringw | Ring width | Float | 0.5 | 0.5 |
| Bloomringchroma | Ring chroma | Float | 0.0 | 0.0 |

### Drive

| name | label | style | default | value |
|---|---|---|---|---|
| Audiochop | Audio CHOP (low mid high level s0..s15) | CHOP |  |  |
| Drivechop | Control CHOP (OSC / MIDI): channels as drive sources | CHOP |  |  |
| Tempo | Tempo | Menu | project | manual |
| Bpm | Bpm | Float | 120.0 | 120.0 |
| Beatdecay | Beatdecay | Float | 6.0 | 6.0 |
| Trig1 | Trig1 | Pulse | False | False |
| Trig2 | Trig2 | Pulse | False | False |
| Trig3 | Trig3 | Pulse | False | False |
| Trig4 | Trig4 | Pulse | False | False |
| Trigdecay | Trigdecay | Float | 2.0 | 1.2 |
| Trigauto | Auto trigger every N s (0 off) | Float | 0.0 | 0.0 |
| Trigautowhich | Auto trigger fires | Menu | all | all |
| Trigsource | Trigger source | Menu | manual | manual |
| Trigbeats | Every N beats (Trigsource) | Int | 4 | 4 |
| Audiosrc | Audio features COMP (AU_features; empty = off) | COMP | /project1/lab/AU_features | /project1/lab/AU_features |
| Beatsync | Beat sync (beat / tempo / triggers / transitions follow the audio) | Toggle | False | False |
| Lfo1rate | Lfo1rate | Float | 0.25 | 0.08 |
| Lfo2rate | Lfo2rate | Float | 1.0 | 0.5 |
| Lfoshape | Lfoshape | Menu | sine | sine |

### Stack

| name | label | style | default | value |
|---|---|---|---|---|
| Addtype | Module type (browser) | StrMenu | prox_push | prox_colour |
| Add | Add module | Pulse | False | False |
| Addafter | Add after the selected module (off = at the end) | Toggle | False | False |
| Sel | Selected uid | StrMenu | 1 | 5 |
| Remove | Remove | Pulse | False | False |
| Duplicate | Duplicate | Pulse | False | False |
| Moveup | Moveup | Pulse | False | False |
| Movedown | Movedown | Pulse | False | False |
| Toggleon | Enable / disable | Pulse | False | False |
| Solo | Solo the selected module (only it runs) | Pulse | False | False |
| Unsolo | Unsolo (the enabled set comes back) | Pulse | False | False |
| Effkind | Effector kind | Menu | box | box |
| Addeffector | Add effector object | Pulse | False | False |
| Effname | Effector to remove | StrMenu |  |  |
| Removeeffector | Removeeffector | Pulse | False | False |
| Status | Status (read only) | Str |  | loaded A 228287 pts \| 228287 points (scene 228287), side 478 |

### Presets

| name | label | style | default | value |
|---|---|---|---|---|
| Presetname | Preset name | StrMenu | look1 | default |
| Store | Store | Pulse | False | False |
| Recall | Recall | Pulse | False | False |
| Deletepreset | Deletepreset | Pulse | False | False |
| Presetsource | Presets change the source | Toggle | False | False |
| Morphto | Morph to preset | Pulse | False | False |
| Presetup | Move preset up | Pulse | False | False |
| Presetdown | Move preset down | Pulse | False | False |
| Newname | New name (for Rename) | Str |  |  |
| Presetrename | Rename preset | Pulse | False | False |
| Presetsort | Sort presets A-Z (built-ins first) | Pulse | False | False |
| Morphtime | Morph seconds | Float | 4.0 | 4.0 |
| Morphcurve | Morphcurve | Menu | smooth | smooth |
| Stopmorph | Stopmorph | Pulse | False | False |
| Next | Setlist: next scene | Pulse | False | False |
| Prev | Setlist: previous scene | Pulse | False | False |
| Cue | Setlist scene (pick, then Go) | StrMenu |  |  |
| Go | Setlist: go to the scene | Pulse | False | False |
| Transition | Transition (s; beats with Beat sync; 0 = cut) | Float | 2.0 | 2.0 |
| Transcurve | Transition curve | Menu | ease | ease |
| Current | Current scene (read only) | Str | - | - |
| Cueindex | Go to scene # (CQ / TL hook; 0 = none) | Int | 0 | 0 |
| Setlist | Setlist table (empty = presets order) | DAT | ./px_setlist | /project1/lab/PX_pointfx/px_setlist |
| Setlistfill | Fill setlist with the presets order | Pulse | False | False |
| Preview | Gizmo preview on | Toggle | True | True |
| Previewcount | Previewcount | Int | 65536 | 65536 |
| Opencontrols | Opencontrols | Pulse | False | False |

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
| Zkm1 | Energy | Float | 0.0 | 0.3333 |
| Zkm2 | Glow | Float | 0.0 | 0.0 |
| Zkm3 | Mood | Float | 0.0 | 0.0 |
| Zkm4 | Chaos | Float | 0.0 | 0.0 |

### M1_prox_push

| name | label | style | default | value |
|---|---|---|---|---|
| M1amount | amount | Float | 1.0 | 0.054 |
| M1maskin | mask input | Menu | none | none |
| M1invert | invert mask | Toggle | False | False |
| M1chunk | chunk cell (0 = per point) | Float | 0.0 | 0.0 |
| M1effectors | effectors (names) | StrMenu | E1 | E1 E2 |
| M1drive | drive (param:src*gain+off) | Str |  |  |
| M1radius | radius | Float | 1.0 | 8.49 |
| M1falloff | falloff exp | Float | 1.0 | 3.64 |
| M1shape | shape | Menu | smooth | smooth |
| M1combine | combine | Menu | max | max |
| M1flip | flip (far = 1) | Toggle | False | False |
| M1noiseedge | ragged edge | Float | 0.0 | 0.31 |
| M1noisefreq | edge noise freq | Float | 2.0 | 1.71 |
| M1space | space | Menu | current | current |
| M1edge | front edge (x radius; behind/ahead) | Float | 0.02 | 0.032 |
| M1strength | strength (neg = pull) | Float | 0.5 | 0.4 |
| M1mode | mode | Menu | displace | displace |
| M1dir | dir | Menu | outward | centre |
| M1publish | publish weight to | Menu | none | none |

### M2_curl

| name | label | style | default | value |
|---|---|---|---|---|
| M2amount | amount | Float | 1.0 | 0.42 |
| M2maskin | mask input | Menu | none | none |
| M2invert | invert mask | Toggle | False | False |
| M2chunk | chunk cell (0 = per point) | Float | 0.0 | 1.682 |
| M2effectors | effectors (names) | StrMenu |  |  |
| M2drive | drive (param:src*gain+off) | Str |  |  |
| M2strength | strength | Float | 1.0 | 1.23 |
| M2scale | scale | Float | 1.0 | 1.0 |
| M2speed | speed | Float | 0.3 | 0.3 |
| M2octaves | octaves | Int | 2 | 2 |
| M2mode | mode | Menu | force | force |
| M2distance | displace distance | Float | 0.2 | 0.2 |

### M3_prox_colour

| name | label | style | default | value |
|---|---|---|---|---|
| M3amount | amount | Float | 1.0 | 3.152 |
| M3maskin | mask input | Menu | none | none |
| M3invert | invert mask | Toggle | False | False |
| M3chunk | chunk cell (0 = per point) | Float | 0.0 | 0.0 |
| M3effectors | effectors (names) | StrMenu | E1 | E1 E2 |
| M3drive | drive (param:src*gain+off) | Str |  |  |
| M3radius | radius | Float | 1.0 | 1.0 |
| M3falloff | falloff exp | Float | 1.0 | 1.0 |
| M3shape | shape | Menu | smooth | smooth |
| M3combine | combine | Menu | max | max |
| M3flip | flip (far = 1) | Toggle | False | False |
| M3noiseedge | ragged edge | Float | 0.0 | 0.0 |
| M3noisefreq | edge noise freq | Float | 2.0 | 2.0 |
| M3space | space | Menu | current | current |
| M3edge | front edge (x radius; behind/ahead) | Float | 0.02 | 0.081 |
| M3mode | mode | Menu | tint | tint |
| M3colourr | colour | RGBA | 1.0 | 1.0 |
| M3colourg | colour | RGBA | 0.45 | 0.45 |
| M3colourb | colour | RGBA | 0.1 | 0.1 |
| M3colour2r | colour2 | RGBA | 0.1 | 0.1 |
| M3colour2g | colour2 | RGBA | 0.6 | 0.6 |
| M3colour2b | colour2 | RGBA | 1.0 | 1.0 |
| M3emission | emission | Float | 2.0 | 0.5 |
| M3flicker | flicker | Float | 0.0 | 0.026 |
| M3hueshift | hueshift | Float | 0.3 | 0.037 |
| M3cover | cover (colour full early in the falloff: solid bands) | Float | 0.0 | 0.0 |
| M3colsrc | colour source | Menu | solid | solid |
| M3palpos | palette position | Float | 0.0 | 0.374 |
| M3palspread | palette spread (x weight) | Float | 1.0 | -0.15 |
| M3palkeep | keep point colour | Float | 0.0 | 0.0 |

### M4_dissolve_noise

| name | label | style | default | value |
|---|---|---|---|---|
| M4amount | amount | Float | 1.0 | 0.0 |
| M4maskin | mask input | Menu | none | none |
| M4invert | invert mask | Toggle | False | False |
| M4chunk | chunk cell (0 = per point) | Float | 0.0 | 0.516 |
| M4effectors | effectors (names) | StrMenu |  |  |
| M4drive | drive (param:src*gain+off) | Str |  |  |
| M4progress | progress | Float | 0.0 | 0.983 |
| M4auto | auto progress | Menu | off | off |
| M4rate | auto rate Hz (cycles/s) | Float | 0.1 | 0.1 |
| M4automax | auto top (progress max) | Float | 1.0 | 1.0 |
| M4scale | scale | Float | 2.0 | 2.0 |
| M4octaves | octaves | Int | 3 | 3 |
| M4soft | soft | Float | 0.1 | 0.1 |
| M4biasx | direction bias | XYZW | 0.0 | 0.0 |
| M4biasy | direction bias | XYZW | 0.0 | 0.0 |
| M4biasz | direction bias | XYZW | 0.0 | 0.0 |
| M4release | release | Float | 0.5 | 0.5 |
| M4curl | curl | Float | 1.0 | 1.0 |
| M4up | up | Float | 0.5 | 0.5 |

### Palette

| name | label | style | default | value |
|---|---|---|---|---|
| Palsource | Palette | Menu | neon_trio | neon_trio |
| Palstops | Custom stops (hex [pos], ...) | Str | #39FF14 0, #00F0FF 0.5, #FF00E6 1 | #39FF14 0, #00F0FF 0.5, #FF00E6 1 |
| Palfile | Palette file (.txt .hex .json .gpl .pal .ase) | File |  |  |
| Palmode | Palmode | Menu | gradient | gradient |
| Palinterp | Palinterp | Menu | oklab | oklab |
| Palreverse | Palreverse | Toggle | False | False |
| Palshift | Shift (rotate; drive-able) | Float | 0.0 | 0.0 |
| Paldrive | Shift drive | Menu | manual | manual |
| Palevery | Beats per step / cycle | Float | 1.0 | 1.0 |
| Palgain | Audio drive gain | Float | 1.0 | 1.0 |
| Edgecolsrc | Edge colour source | Menu | solid | solid |
| Edgepalpos | Edge palette position | Float | 0.0 | 0.0 |
| Edgepalspread | Edge palette spread | Float | 1.0 | 1.0 |
| Edgekeep | Edge keep own colour | Float | 0.0 | 0.0 |
| Hazecolsrc | Haze colour source | Menu | solid | solid |
| Hazepalpos | Haze palette position | Float | 0.0 | 0.0 |
| Hazepalspread | Haze palette spread | Float | 1.0 | 1.0 |
| Hazekeep | Haze keep own colour | Float | 0.0 | 0.0 |
| Flarecolsrc | Flare colour source | Menu | solid | solid |
| Flarepalpos | Flare palette position | Float | 0.0 | 0.0 |
| Flarepalspread | Flare palette spread | Float | 1.0 | 1.0 |
| Flarekeep | Flare keep own colour | Float | 0.0 | 0.0 |
| Glowcolsrc | Glow colour source | Menu | solid | solid |
| Glowpalpos | Glow palette position | Float | 0.0 | 0.0 |
| Glowpalspread | Glow palette spread | Float | 1.0 | 1.0 |
| Glowkeep | Glow keep own colour | Float | 0.0 | 0.0 |

### Lights

| name | label | style | default | value |
|---|---|---|---|---|
| Addltype | Light type | Menu | point | point |
| Addlcolourr | Light colour | RGBA | 1.0 | 1.0 |
| Addlcolourg | Light colour | RGBA | 1.0 | 1.0 |
| Addlcolourb | Light colour | RGBA | 1.0 | 1.0 |
| Addlintensity | Light intensity | Float | 2.0 | 2.0 |
| Addlposx | Light position | XYZW | 0.0 | 0.0 |
| Addlposy | Light position | XYZW | 1.5 | 1.5 |
| Addlposz | Light position | XYZW | 1.0 | 1.0 |
| Addlight | Add light to /project1/effectors | Pulse | False | False |
| Lightinfo | Lights (read only; light module + haze use them) | Str |  | 1 lights on: light1 |

### Haze

| name | label | style | default | value |
|---|---|---|---|---|
| Vhon | Volumetric haze + shafts | Toggle | False | True |
| Vhamount | Vhamount | Float | 1.0 | 1.0 |
| Vhres | Vhres | Menu | quarter | quarter |
| Vhlights | Lights (all / #tag / names; max 8) | StrMenu | all | all |
| Vhdensity | Density | Float | 0.08 | 0.08 |
| Vhfloor | Floor height (y) | Float | 0.0 | 0.0 |
| Vhfalloff | Height falloff | Float | 0.35 | 0.35 |
| Vhnoise | Patchiness | Float | 0.5 | 0.5 |
| Vhnoisescale | Vhnoisescale | Float | 0.35 | 0.35 |
| Vhwindx | Drift (units/s) | XYZW | 0.3 | 0.3 |
| Vhwindy | Drift (units/s) | XYZW | 0.05 | 0.05 |
| Vhwindz | Drift (units/s) | XYZW | 0.1 | 0.1 |
| Vhextinction | Extinction (dims the scene) | Float | 1.0 | 1.0 |
| Vhambient | Ambient haze | Float | 0.25 | 0.25 |
| Vhcolr | Haze colour | RGBA | 0.55 | 0.55 |
| Vhcolg | Haze colour | RGBA | 0.6 | 0.6 |
| Vhcolb | Haze colour | RGBA | 0.7 | 0.7 |
| Vhcolsrc | Vh colour source | Menu | source | source |
| Vhpalpos | Vh palette position | Float | 0.0 | 0.0 |
| Vhpalspread | Vh palette spread | Float | 1.0 | 1.0 |
| Vhkeep | Vh keep own colour | Float | 0.0 | 0.0 |
| Vhtintr | Lit fog tint | RGBA | 1.0 | 1.0 |
| Vhtintg | Lit fog tint | RGBA | 1.0 | 1.0 |
| Vhtintb | Lit fog tint | RGBA | 1.0 | 1.0 |
| Vhgain | Lit fog gain | Float | 1.0 | 1.0 |
| Vhg | Forward scatter (g) | Float | 0.35 | 0.35 |
| Vhsteps | Vhsteps | Int | 8 | 8 |
| Vhsoft | Light size | Float | 0.05 | 0.05 |
| Vhshafts | Shafts (0 = off) | Float | 0.6 | 0.6 |
| Vhdecay | Vhdecay | Float | 0.96 | 0.96 |
| Vhlength | Vhlength | Float | 0.85 | 0.85 |
| Vhtaps | Vhtaps | Int | 12 | 12 |
| Vhthreshold | Bright pixels emit shafts (0 = off) | Float | 0.0 | 0.0 |
| Vhdisc | Light disc | Float | 0.06 | 0.06 |
| Vhocclusion | Scene blocks shafts | Float | 1.0 | 1.0 |
| Vhshaftlod | Shaft mip (perf) | Float | 1.0 | 1.0 |
| Vhobjdist | Object distance (covered pixels) | Float | 6.0 | 6.0 |
| Vhmaxdist | Max distance (sky) | Float | 60.0 | 60.0 |

### Geo

| name | label | style | default | value |
|---|---|---|---|---|
| Geoon | Geometry in the scene (occludes both ways) | Toggle | False | True |
| Geocomps | Geometry COMPs (paths / patterns) | Str |  |  |
| Geolights | Lights (paths, #tag; #light = all in /project1/effectors) | StrMenu | #light | #light |
| Geokey | Built-in key light | Toggle | True | True |
| Geodepthbias | Splat depth bias (world) | Float | 0.0 | 0.0 |
| Geoaddkind | Add kind | Menu | sphere | sphere |
| Geoaddcolourr | Add: base colour | RGBA | 0.8 | 0.8 |
| Geoaddcolourg | Add: base colour | RGBA | 0.8 | 0.8 |
| Geoaddcolourb | Add: base colour | RGBA | 0.85 | 0.85 |
| Geoaddmetal | Add: metallic | Float | 1.0 | 1.0 |
| Geoaddrough | Add: roughness | Float | 0.15 | 0.15 |
| Geoaddemit | Add: emission (blooms) | Float | 0.0 | 0.0 |
| Geoadd | Add geometry object (geo/) | Pulse | False | False |
| Geoenv | Scene reflections (chrome; env capture) | Toggle | False | False |
| Geoenvres | Environment cube px | Int | 128 | 128 |
| Geoenveveryn | Environment every N frames | Int | 4 | 4 |
| Geoenvdimmer | Environment dimmer | Float | 1.0 | 1.0 |
| Geoenvcentrex | Environment centre (the chrome object) | XYZW | 0.0 | 0.0 |
| Geoenvcentrey | Environment centre (the chrome object) | XYZW | 0.0 | 0.0 |
| Geoenvcentrez | Environment centre (the chrome object) | XYZW | 0.0 | 0.0 |

### Lines

| name | label | style | default | value |
|---|---|---|---|---|
| Lineson | Lines layer (PX_lines inside; its page: Opencontrols there) | Toggle | False | False |
| Linesdepth | Lines hidden behind geometry (Geo depth) | Toggle | False | False |

### Camera

| name | label | style | default | value |
|---|---|---|---|---|
| Camsource | Camera source | Menu | internal | internal |
| Camcomp | External Camera COMP (pick) | StrMenu |  |  |
| Cammode | Camera rig | Menu | orbit | orbit |
| Camtargetx | Target / crane base | XYZW | 0.0 | 0.0 |
| Camtargety | Target / crane base | XYZW | 0.0 | 0.0 |
| Camtargetz | Target / crane base | XYZW | 0.0 | 0.0 |
| Camheading | Crane heading deg | Float | 0.0 | 0.0 |
| Campitch | Crane pitch deg | Float | 20.0 | 20.0 |
| Camlength | Crane arm length | Float | 4.0 | 4.0 |
| Camheadspeed | Crane heading deg/s | Float | 10.0 | 10.0 |
| Campitchamp | Crane pitch swing deg | Float | 0.0 | 0.0 |
| Campitchfreq | Crane swing Hz | Float | 0.1 | 0.1 |
| Camdollyax | Dolly from | XYZW | 0.0 | 0.0 |
| Camdollyay | Dolly from | XYZW | 0.5 | 0.5 |
| Camdollyaz | Dolly from | XYZW | 6.0 | 6.0 |
| Camdollybx | Dolly to | XYZW | 0.0 | 0.0 |
| Camdollyby | Dolly to | XYZW | 0.5 | 0.5 |
| Camdollybz | Dolly to | XYZW | 2.0 | 2.0 |
| Camdollysec | Dolly seconds (ping-pong) | Float | 10.0 | 10.0 |
| Campoints | Path points (x y z; ...) | Str | -3 0.5 4; 0 1.5 3; 3 0.5 4; 0 0.3 6 | -3 0.5 4; 0 1.5 3; 3 0.5 4; 0 0.3 6 |
| Campathsec | Path seconds per loop | Float | 20.0 | 20.0 |
| Camfollow | Follow effector (name) | StrMenu |  |  |
| Camoffsetx | Follow offset | XYZW | 0.0 | 0.0 |
| Camoffsety | Follow offset | XYZW | 1.0 | 1.0 |
| Camoffsetz | Follow offset | XYZW | 4.0 | 4.0 |
| Camlag | Follow lag s | Float | 0.4 | 0.4 |
| Camshots | Director shots (rig:beats ...) | Str | crane:8 orbit:8 dolly:4 path:8 | crane:8 orbit:8 dolly:4 path:8 |
| Camdirmode | Camdirmode | Menu | random | random |
| Camquant | Cut on multiples of N beats | Float | 4.0 | 4.0 |
| Camtrans | Camtrans | Menu | cut | cut |
| Camtdur | Transition beats | Float | 1.0 | 1.0 |
| Camseed | Camseed | Int | 1 | 1 |
| Camroll | Roll deg | Float | 0.0 | 0.0 |
| Camshake | Shake (units) | Float | 0.0 | 0.0 |
| Camshakerot | Shake rotation deg | Float | 0.0 | 0.0 |
| Camshakefreq | Shake Hz | Float | 6.0 | 6.0 |

### Grid

| name | label | style | default | value |
|---|---|---|---|---|
| Hotthr | Hot point: heat above | Float | 0.3 | 0.3 |
| Hotemit | Hot point: colour luma above (0 = heat only) | Float | 0.0 | 0.0 |
| Hotmax | Hot points sampled (grid cloud size) | Int | 4096 | 4096 |
| Gridfit | Fit the shared grid around this scene (when PX turns it on) | Toggle | True | True |

### Sound

| name | label | style | default | value |
|---|---|---|---|---|
| Soundon | Sound on (Audio Device Out, default output) | Toggle | False | False |
| Soundvol | Volume | Float | 0.15 | 0.15 |
| Soundpitch | Pitch (x) | Float | 1.0 | 1.0 |
| Sounddrone | Drone (pitch = mean height, fades as it dissolves) | Float | 1.0 | 1.0 |
| Soundshimmer | Shimmer (pitch + level = mean speed) | Float | 0.5 | 0.5 |
| Soundnoise | Noise (level = dissolved fraction) | Float | 0.3 | 0.3 |
| Soundspeed | Speed for full shimmer (units / s) | Float | 2.0 | 2.0 |

### Output

| name | label | style | default | value |
|---|---|---|---|---|
| Proj | Projection | Menu | perspective | perspective |
| Projface | Cube face size (px) | Int | 1024 | 1058 |
| Projfov | Fisheye angle deg | Float | 180.0 | 180.0 |
| Projtilt | Dome tilt deg (x) | Float | 0.0 | -9.4 |

### Perf

| name | label | style | default | value |
|---|---|---|---|---|
| Autoquality | Auto quality | Menu | off | off |
| Govop | Governor CHOP (Autoquality governor; quality 1 = full) | Str | /project1/lab/FG_fps_governor/out1 | /project1/lab/FG_fps_governor/out1 |
| Aqfps | Auto: step down under fps | Float | 57.0 | 57.0 |
| Aqframes | Auto: frames under before a step | Int | 45 | 45 |
| Aqheadroom | Auto: step up when frame ms under | Float | 10.0 | 10.0 |
| Aqstate | Auto quality now (read only) | Str | off | off |
| Sortstill | Skip re-sorts while nothing moves (Sortmode auto) | Toggle | True | True |
| Lod | LOD: fewer, bigger splats / points far away | Toggle | False | False |
| Loddist | LOD starts at camera distance (full at 2x) | Float | 6.0 | 6.0 |
| Lodkeep | LOD: share kept far away | Float | 0.35 | 0.35 |

## Perf

cook 11.566 ms (CPU 11.566 / GPU 12.74) summed over the 26 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- `.` Afile `~/Downloads/Classroom of Class 6 Grade 9, China/scene.ply` (outside)

## Load

`td_library_load {"name": "PX_pointfx", "parent": "/project1/lab"}` (lands parked)
