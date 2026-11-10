# fx_glass: FX_glass rack + modules (lane B, 27 Oct 2026, TD 2025.31550 target)

`/project1/lab/FX_glass`. Glass / lens surfaces over any picture: liquid glass (pilot), holo foil, rain on glass, frost
/ reeded / fly-eye, wet mirror floor (BUILD_PLAN_27OCT s2: its own rack, not FX_film, to keep FX_film's bring-home
light). Specs = research rows SX-01 / SX-02 / SX-03 (`docs/research/FX7a_shadertoy_glsl_libraries.md`), 7C-21 / 22 /
23 / 34 (`FX7c_other_tools_effects.md`).

## Rack (`builders/fx_glass.py`)
The FX_glitch rack reused through `builders/fx_stylise.py` (exec, no copy): slots table, Cross + Switch per slot,
Panic, Input auto / live / test, palette logic DAT, `H['pas']` / `H['glsl']`. Module X = `builders/fx_glass_X.py`.
**Rest state: every slot enabled 0.** Rack addition used by 2+ glass modules (liquid, rain, frost):
`H['backdrop'](m, src)` = `bd_down` (Resolution TOP at 1 / Backdown, mipmap, 16F) -> `bd` (Blur TOP gaussian, size =
Backblur / down, extend hold): the pre-blurred backdrop; the module declares `BACKDROP_PAGE` (Backblur, Backdown).
```python
ns = dict(globals()); exec(open('<repo>/builders/fx_glass.py').read(), ns)
ns['build']('/project1/lab')                               # rack + liquid1 (enabled 0); idempotent
ns['add']('/project1/lab/FX_glass', 'foil')
```
Checks: `builders/fx_stylise_checks.py` (shared with FX_stylise). Offline tests use `test/fx_stylise_testkit.py`
(glslc with the stub sized per pass, T-177).

## Module `liquid` (`builders/fx_glass_liquid.py`; SX-01 + 7C-23; pilot)
Mirror: `builders/fx_glass_liquid_logic.py` (Source shapes). Tests: `test/test_fx_glass_liquid.py` (7, glslc of fx /
matte, rack reuse).
Shapes: Table DAT `shapes`, rows `cx cy w h r rot` (centre uv, size and corner radius px, rotation deg; r = h / 2 =
pill, r = w / 2 = circle), <= 8 -> Script CHOP `shp` -> `uShp[16]`. Rounded boxes smooth-unioned (Smooth px: merging
blobs), Drift / Driftspeed move them (per-shape phases, Seed). Source **mask** instead: the matte of Masktop (a Text
TOP of a whole word, a logo) or in1 (`matte` pass, Matte / Invert) blurred by Maskblur (`mblur`) = a height field,
d = (Threshold - h) x 2 Bevel.
fx (in1, backdrop, mask height): d (px) + its gradient by central differences of the SDF itself (no dFdx); dome bevel
over Bevel px -> normal -> `refract` with 1 / IOR, shift = Thickness px, 3 IORs (Dispersion) = rim colour split;
inside = mix(sharp in1, backdrop, Frost) at the refracted spot; tint (solid, or the palette stop of the nearest
shape: Tintsrc palette) x Bright; Fresnel rim (Rim, Rimpow), Blinn spec (Spec, Shine, Lightangle), edge line (Edge);
drop shadow outside (Shadow, Shadowsoft, Shadowoffset px down). Coverage antialiased over 1.5 px.
Presets: 1 glass panels (3 default shapes), 2 lens (thick, no frost, strong dispersion), 3 merging blobs (Smooth 180,
drifting, palette tint), 4 frosted pills (Frost 1, blur 48), 5 glass word (Source mask: Masktop or the matte of in1).

### LIVE CHECKS (liquid)
1. Builds clean (rack + module); fx / matte compile; Blur TOP pars (type gaussian, extend hold).
2. Passthrough: Amount 0, enabled 0, mix 0, Panic -> **0**.
3. `liquid_parity(m)` (Drift 0, solid tint): presets 1, 2, 4: over-tol < 0.5 % (refraction samples, bilinear).
4. Source mask with a Text TOP of a whole word: glass on the letters only (glass_px > 0), no error.
5. Presets 1-5 full state; cost <= ~3 ms (estimate 0.6-1.0); fps.

### Verified live (liquid: 27 Oct 2026, 31550, b4)
- Rack built by the builder (`build('/project1/lab')`), no errors / warnings; Blur TOP pars probed live (type menu
  catmull / gaussian / ..., extend hold / repeat / mirror, size).
- Passthrough: Amount 0 / enabled 0 / mix 0 / Panic -> **0**.
- `liquid_parity` presets 1, 2, 4 (Drift 0): over-tol **0** (max 2.8e-3); 39 % of pixels touched (3 shapes + shadow).
- Source mask with a Text TOP 'GLASS' (whole word, alpha): no errors, 5.8 % of pixels changed (the letters + their
  shadow). First version darkened the whole frame (the mask pseudo-distance saturated at Bevel, so the shadow never
  faded): outside the mask the distance now grows as the blurred matte goes to 0.
- Cost, first version 2.4-3.6 ms (fx 1.4-1.7 ms GPU, mask blur 1.4 ms at full res); after (a) an early exit far from
  the shapes and outside the glass (shadow only), (b) the mask matte + blur at half res: glass panels **2.30 ms** (fx
  1.01 GPU, backdrop blur 0.43 + down 0.27), lens 2.25, merging blobs 2.27, frosted pills 1.87, glass word 1.78.
  b4 60.8 fps.

## Module `foil` (`builders/fx_glass_foil.py`; 7C-22 thin-film holo foil)
Mirror: `builders/fx_glass_foil_logic.py`. Tests: `test/test_fx_glass_foil.py` (5, glslc; zero thickness = white, a
half-wave of 532 nm = green dark).
One compute pass: smoothed luma Lb (5 bilinear taps at Smooth px) and its gradient; thickness d = Base + Range x (Lb +
Noise x (value noise - 0.5)) nm (Noisescale, Noisespeed drift); pseudo-normal from the luma relief x Tilt -> view
angle, Snell into the film (Filmior) -> Mode thinfilm: I = 0.5 + 0.5 cos(4 pi n d cos(theta_t) / lambda + phase) per
channel (650 / 532 / 450 nm); cosine: IQ rainbow of the same optical path; palette: W1-B at d / (Base + Range).
Saturation, Keepluma (scale to the picture's luma), Blend replace / multiply / screen / overlay / add; phase = Shift
+ Speed x t (bind a beat or LFO to Shift). Presets: 1 holo foil (overlay), 2 oil slick, 3 soap bubble (screen), 4
rainbow chrome (cosine, overlay), 5 palette sheen (multiply).

### LIVE CHECKS (foil)
1. Builds clean; fx compiles. 2. Passthrough: Amount 0, enabled 0, mix 0, Panic -> **0**.
3. `foil_parity(m)` (Speed 0, Noisespeed 0) presets 1-4: over-tol < 0.5 %. 4. Presets; cost <= ~3 ms (estimate
0.2-0.4); fps.

### In main (FX_glass + liquid: 27 Oct 2026, JazibTD_home.626)
NEW COMP `/project1/lab/FX_glass` built by the builder in main in a quiet minute, placed in the lab plan's **FX racks**
stage (`jz_stages` + `restage` ok), no errors. Re-check in main: liquid parity over-tol **0**, Amount 0 and rest diff
**0**. Rest: slot enabled 0, parked, saved.

### Verified live (foil: 27 Oct 2026, 31550, b4)
- Added by the builder, no errors / warnings. Passthrough: Amount 0 / enabled 0 / mix 0 / Panic -> **0**.
- `foil_parity` presets 1-4 (Speed 0, Noisespeed 0 set after the recall): over-tol **0** (max 2e-3).
- Presets full state (21 pars). Cost median: holo foil **0.48 ms** (fx 0.21 GPU), oil slick 0.48, soap bubble 0.45,
  rainbow chrome 0.43, palette sheen 0.65. b4 60.4 fps.

## Module `rain` (`builders/fx_glass_rain.py`; SX-02 + 7C-34 rain on glass)
Mirror: `builders/fx_glass_rain_logic.py`. Tests: `test/test_fx_glass_rain.py` (6, glslc; drops slide down, density,
lens flip inside drops only).
One compute pass (in1 + backdrop): Layers 1-3 of drop cells (Size x 2 Size px, layer scale 1 / 0.6 / 0.4): with
probability Rain a cell holds a drop sliding down (monotonic stick-slip, Speed), egg-shaped (0.85 y squash), radius
0.16 Size x hash; a clear trail above it (Trails) with trail droplets; a finer grid of static droplets (Static) that
fade in and out. Each drop is a lens: offset = -(1 + Refract) x (pixel - drop centre) -> the picture flipped inside;
rim darkening (Rimdark). Between drops the glass shows the pre-blurred backdrop (Fog), cleared by drops and trails;
Tint x Tintamt. Presets: 1 window rain, 2 storm (3 layers), 3 lens drops (big, slow, no fog), 4 misty, 5 still glass
(Speed 0).

### LIVE CHECKS (rain)
1. Builds clean; fx compiles. 2. Passthrough: Amount 0, enabled 0, mix 0, Panic -> **0**.
3. `rain_parity(m)` (Speed 0) presets 1, 3, 4: over-tol < 0.5 % (hash cells + bilinear).
4. Presets; cost <= ~3 ms (estimate 0.6-1.0); fps.

### Verified live (rain: 27 Oct 2026, 31550, b4)
- Added by the builder, no errors / warnings. Passthrough: Amount 0 / enabled 0 / mix 0 / Panic -> **0**.
- `rain_parity` presets 1, 3, 4 (Speed 0 after the recall): over-tol **0** (max 2.7e-3); 75 % / 2.5 % / 93 % of pixels
  changed (window rain / lens drops / misty).
- Presets full state (17 pars). Cost median: window rain **1.06 ms** (fx 0.32 GPU, backdrop blur 0.22), storm 1.54,
  lens drops 0.86, misty 1.01, still glass 1.11. b4 60.9 fps.

## Module `frost` (`builders/fx_glass_frost.py`; SX-03 frosted / reeded / fly-eye)
Mirror: `builders/fx_glass_frost_logic.py`. Tests: `test/test_fx_glass_frost.py` (6, glslc).
One compute pass (in1 + backdrop). **frosted**: each pixel samples a hashed point within Radius px (re-rolled Animate
times / s; 0 = still), mixed toward the backdrop by Blurmix. **reeded**: ribs Width px at Angle; inside a rib (s =
-0.5..0.5) the picture comes from the rib centre + s x Width x Mag (1 clear, < 1 compressed, < 0 flipped), backdrop at
the rib edges (Blurmix x edge^2), Rimlight. **flyeye**: square or hex cells of Cell px, each shows the picture around
its centre x Mag (negative = inverted), Vignette, Gap border, Rimlight. Presets: 1 frosted, 2 shower glass, 3 reeded,
4 flipped ribs (horizontal, Mag -1), 5 fly eye (hex, Mag -0.6).

### LIVE CHECKS (frost)
1. Builds clean; fx compiles. 2. Passthrough: Amount 0, enabled 0, mix 0, Panic -> **0**.
3. `frost_parity(m)` presets 1, 3, 4, 5 (Animate 0): over-tol < 0.5 %. 4. Presets; cost <= ~3 ms (estimate 0.15-0.3);
fps.

### Verified live (frost: 27 Oct 2026, 31550, b4)
- Added by the builder, no errors / warnings. Passthrough: Amount 0 / enabled 0 / mix 0 / Panic -> **0**.
- `frost_parity` presets 1, 3, 4, 5: over-tol **0** (max 2.5e-3).
- Presets full state (16 pars). Cost median: frosted **0.98 ms** (fx 0.12 GPU, backdrop 0.26), shower glass 2.18
  (blur 40 px; p90 14.7 under load), reeded 1.08, flipped ribs 0.87, fly eye 0.73. b4 60.4 fps.

## Module `floor` (`builders/fx_glass_floor.py`; 7C-21 wet mirror floor; FX_venue left untouched, U11 default)
Mirror: `builders/fx_glass_floor_logic.py`. Tests: `test/test_fx_glass_floor.py` (5, glslc).
One compute pass (in1 + backdrop). Above the floor line Horizon (uv from the bottom): the picture (Layout fit =
squeezed above the line, overlay = left as is). Below: floor colour + optional perspective tiles (Tiles across,
Tilewidth, Tileglow, Persp; line colour white or the palette stop per tile row) + the picture mirrored at the line
(Stretch), rippled (Ripple px, Ripplefreq, Ripplespeed, value noise per Seed), blurred toward the backdrop with
distance (Blurdist), faded (Fade, Fadepow) and stronger near the line (Fresnel), x Reflect. Presets: 1 wet stage, 2
mirror, 3 puddle, 4 neon grid floor (palette tiles), 5 overlay shine.

### LIVE CHECKS (floor)
1. Builds clean; fx compiles. 2. Passthrough: Amount 0, enabled 0, mix 0, Panic -> **0**.
3. `floor_parity(m)` presets 1, 2, 3, 5 (Ripplespeed 0): over-tol < 0.5 %. 4. Presets; cost <= ~3 ms (estimate
0.3-0.6); fps.

### Verified live (floor: 27 Oct 2026, 31550, b4)
- Added by the builder, no errors / warnings. Passthrough: Amount 0 / enabled 0 / mix 0 / Panic -> **0**.
- `floor_parity` presets 1, 2, 3, 5 (Ripplespeed 0 after the recall): over-tol **0** (max 2.3e-3).
- Presets full state (28 pars). Cost median: wet stage **0.91 ms** (fx 0.11 GPU, backdrop 0.20), mirror 1.26, puddle
  1.79, neon grid floor 1.35, overlay shine 1.49 (p90 up to 12 ms = load spikes on the shared GPU). b4 60.9 fps.

### In main (foil, rain, frost, floor: 27 Oct 2026)
Added by the builder one module per exec (un-park, `add`, check, rest, park, save), each in a quiet minute: foil
JazibTD_home.628, rain .632, frost .636, floor .640; each parity over-tol 0 in main, rest diff 0, parked.
Library: `library/FX_glass/` 0.1.0 (372 KB .tox).

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (.746).
