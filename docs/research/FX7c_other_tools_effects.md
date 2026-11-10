# FX7c - Effects other real-time / VJ / VFX tools ship that this repo lacks (27 Oct 2026)

User (27 Oct): "research more and build more". Offline research lane: **TD, Arena, Resolume REST/OSC and Syphon were not
touched, nothing was installed or run.** Target when this is built: TD 2025.31550, macOS Rosetta, MoltenVK, 1080x1920,
60 fps, ~3 ms per COMP (CLAUDE.md). Every ms figure below is an **estimate, not a measurement** (replace with `td_perf` at
build time). Multi-pass = compute-mode GLSL only (T-46/T-47); no Optical Flow TOP (T-18); no flash caps or safety guides
inside effects (user rule 26 Oct).

**34 new effects** (FX7c-01..34). "New" = not a built module, not a row in FX0 (82-row backlog), not a named gap in FX4/FX5,
and not a covered/partial row in `docs/builds/RUBENFRO_COVERAGE.md` (checked by grep of builders/, docs/builds/,
docs/research/ for the effect's keywords plus reading FX0, FX4 s1-5, the README and the RUBENFRO table). Where a prior
note or tool is close, the card says so ("Near:").

## 0. Method, sources and how far to trust each

Evidence tags used on every card: **[O]** page opened and read this session; **[S]** search-result snippet only; **[K]** from
general knowledge, not re-verified (Shadertoy returned 403 to every fetch, so Shadertoy ids are not given; names only);
**[R]** repo doc already in this folder.

| Source | What was read | Result |
|---|---|---|
| Keijiro Takahashi GitHub (first 295 non-fork repos listed through the API, his account has ~950; 8 repo pages opened) | Skinner, KinoGlitch, Kino, Retro3D, NoPersRetro, KinoAqua, SonarFx, StrobePages, HdrpVatExample, MetavidoVFX, ComputeMarchingCubes, SdfVfxSamples | Best new source: technique-level READMEs for Skinner, Retro3D, StrobePages, VAT. Most are Unity-only: ideas ported, no code copied. |
| Notch 2026.1 manual (node tree [O] + Image Distance and Jigsaw pages [O], Soft Ball [S]) | Whole node list incl. generators, particle renderers, deformers, procedurals | FX4 already tabled the Post-FX names; new here: Image Distance, Jigsaw, Soft Ball, Onion, Greeble, Pyroclastic, Deformer bank |
| Boris FX Sapphire index [O] | all groups to the Procedural Textures cut-off | Already named in FX4 s4.3; used only to check overlaps |
| Vidvox ISF-Files (371 entries, listed via `gh api`) [O] | names + Long Exposure and Motion Heat Map headers | Long Exposure = absorb/discharge feedback (already `FX_motion_trail` territory, so dropped); names used for Hyperspace, Hexagonalize, Triangle Mosaic, Grid Flip |
| Smode docs: 3D modifiers/particle fields catalog, legacy presets [O] | Connect Points, Motion Lines, Transform Triangles, fur box / fur geosphere presets, Clifford/Lorenz/de Jong fields | Mostly covered (attractors, trails); fur/shell presets used |
| Cables.gl `Ops.Gl.ImageCompose` [O] | ~110 ops | all basic filters; nothing new (Wobble, GrowPixels, PatternLookup are covered by TD natives) |
| Millumin effects page [O] | colouring/standard/special lists | nothing new (basic filters + Laser/Blob/Skeleton trackers, which we cover) |
| MadMapper docs [O], Synesthesia site [O], Isadora [S], Vizzie [S], Resolume FFGL list [S], Magic Music Visuals (403) | library categories only; no scene/module name lists readable | **No new effects came from these** (honest gap: Synesthesia's 80 scene names and MMV modules are not public text). |
| Pixera / disguise | not found beyond "disguise runs Notch Blocks" | nothing new beyond Notch |
| Unreal Niagara: Audio Reactive FX packs on Fab/Marketplace [S] | pack descriptions (108 effects in pack 02, 55 tentacle/worm effects in pack 04) | tentacle/worm family (card 28) |
| AE plugin families: Saber [O article], Deep Glow [S], Plexus (403), Universe 2025.1 news [S] | features lists | Saber (card 09). Deep Glow = bloom variant, rejected as duplicate (s4). |

Prior art already in this lab that cards reuse: `gen_sim_vor_jfa.glsl` (jump flood), `BO_particles`, `person_mask`,
`DC_depth_cam`, `px_haze`, `laser_path`, `fx_glitch_timeshuffle` (Cache/Texture 3D), `gen_sdf` (smin scenes), `td_import_blender`.

## 1. Ranked summary (star = top 10)

Cost = estimated cook ms @1080x1920 (unmeasured). Size S <2 h, M 2-6 h, L >6 h one lane incl. live checks. Home = existing
COMP unless "new".

| # | Star | Effect | Group | Tool it comes from | Home | Size | Cost ms | Fit |
|---|---|---|---|---|---|---|---|---|
| 01 | * | Line boil / animated-on-twos | stylise | Spider-Verse look, ISF Doodler/Etch-a-Sketch | FX_paint (new) | S | 0.3-0.5 | anything with a camera or clip |
| 02 | * | Watercolour wash | stylise | KinoAqua, Arena Acuarela | FX_paint | M | 0.8-1.5 | stills/clips, soft acts |
| 03 | | Painterly brush-stroke render | stylise | Sapphire AutoPaint, Arena Strokes | FX_paint | M | 1-2 | IMAG stylise |
| 04 | | Engraving / banknote line screen | stylise | Sapphire Etching | FX_paint | S | 0.3 | logos, portraits |
| 05 | * | Distance-field contour echo | stylise | Notch Image Distance | FX_paint | S | 0.5-0.8 | logos, names, people: top LED look |
| 06 | | Page-flip strobe | stylise/transition | Keijiro StrobePages | FX_trans | S | 0.3-0.5 | cuts, beat accents |
| 07 | | PS1 / early-3D console look | 3D post | Keijiro Retro3D, NoPersRetro | GEN_sdf/3D scenes + FX_retro | S | 0.2-0.5 | retro acts, game themes |
| 08 | | Light wrap + edge feather | compositing | BCC Light Wrap | person_mask | S | 0.2-0.4 | IMAG alpha frames |
| 09 | * | Saber energy beam on paths / text / masks | light | Video Copilot Saber | FX_film (light) | M | 0.5-0.9 | neon signs, logo strokes |
| 10 | * | Fireworks (shell types, barrage) | particles | Niagara/VFX Graph staple | BO_particles | M | 1-2 | finale, drops |
| 11 | | Confetti / streamer cannon | particles | Niagara packs, Notch cloners | BO_particles | M | 0.8-1.5 | drops, finale |
| 12 | | N-body galaxy | sim | GPU Gems 3 ch.31 | GEN_points | M | 1-2 | space/ambient |
| 13 | | Aurora curtains | generator | Shadertoy "Auroras" family | GEN_pattern | S | 1-1.5 | ambient, intros |
| 14 | | Stylised ocean + caustics | generator | Seascape/Tessendorf | GEN_pattern | M | 1.5-2.5 | ambient, water acts |
| 15 | * | Falling-sand playground | sim | Noita, Sandspiel | GEN_sim | M | 0.5-0.8 | interactive, pixel look |
| 16 | | Ferrofluid | sim/3D | club visuals, Rosensweig | GEN_sdf | M | 1.5-2.2 | dark chrome looks |
| 17 | | Synthwave horizon | generator | VJ staple | GEN_pattern | S | 0.2 | retro acts |
| 18 | | Hyperspace star streaks | generator | ISF Hyperspace, Arena WarpSpeed | GEN_points | S | 0.5-1 | builds, transitions |
| 19 | | Mirror-ball light spots | generator | disco/EDM staple | GEN_points | S | 0.3-0.5 | dance sets |
| 20 | | Virtual laser show | generator | MadLaser/Beyond content | laser_path | M | 0.6-1.2 | EDM drops |
| 21 | | Wet mirror floor reflection | venue | Notch/Arena floor trick | FX_venue | S | 0.3-0.6 | tall LED with floor |
| 22 | * | Thin-film holo-foil | surface | three.js iridescence, IQ palettes | FX_film | S | 0.2-0.4 | video to oil-slick foil |
| 23 | * | Liquid-glass lens | UI/glass | liquidGL, Liquid Glass Studio | FX_film (glass) | M | 0.6-1.0 | moving glass pills over video |
| 24 | | Liquid-metal particles | 3D | Notch Soft Ball, yeataro SSF | BO_particles | L | 1.5-2.5 | mercury/chrome drops |
| 25 | | Skinner shards + speed trails on a performer | interactive | Keijiro Skinner | GEN_interactive | M | 1-2 | depth cam / person |
| 26 | * | VAT: baked-sim playback | 3D | SideFX Labs VAT, Keijiro VAT | new tool + FX_destroy | M | 0.3-1 | Blender sims at 60 fps |
| 27 | | Metavido decoder (colour+depth video) | interactive | Keijiro Metavido | pointcloud | S-M | 0.5-1 | recorded dancers as points |
| 28 | | Tentacles / anemone / jellyfish | 3D | Niagara Audio Reactive FX 04 | GEN_sdf or BO | M | 0.5-1 | creature looks |
| 29 | | Jigsaw tiles + puzzle transition | generator | Notch Jigsaw | GEN_pattern + FX_trans | S | 0.3-0.5 | cuts, reveals |
| 30 | | Depth-buffer scanner grid (sonar) | 3D post | Keijiro SonarFx | PX / px_post | S | 0.3 | scan reveals |
| 31 | * | 2.5D depth-parallax photo animator | stills | Depth Anything V2, "3D photo" apps | new `FX_depth25` or `person_mask`-style COMP | M | 0.6-1.2 + ML | the user's generated stills |
| 32 | | Fur / grass shell field | 3D | Smode fur presets, KvantGrass | GEN_sdf or MX | M | 1-1.5 | tactile looks |
| 33 | | Hex / triangle cell mosaic with beat flips | stylise | ISF Hexagonalize, Triangle Mosaic, Grid Flip | FX_glitch (mosaic) | S | 0.2 | cheap rhythm FX |
| 34 | | Rain on glass | lens | BigWings "Heartfelt" idea | FX_film (lens) | S-M | 0.6-1 | moody intros |

**Top 10 starred** (value for live shows x cost x fit with this lab): 31, 05, 09, 10, 23, 01, 26, 15, 22, 02.
Reasons in one line each: 31 turns the user's AI stills into moving 3D scenes (Depth Anything V2 Small already measured at
66.7 ms in `T_realtime_ml.md`); 05 is the cheapest "designed" LED look for logos and names; 09 neon/laser strokes; 10 the
finale effect no one has built yet; 23 the 2025-26 glass trend; 01 a 0.3 ms look that changes how any footage feels;
26 gives the approved Blender integration real-time destruction/fluid; 15 interactive and reads as chunky pixel art on LED;
22 near-free colour on any footage; 02 painterly complement to Kuwahara.

## 2. Cards

Card format: look; tool + URL (tag); technique; TD 31550 approach; cost / size; fit and overlaps. Naming: modules go in the
home COMP's rack (`docs/builds/fx_glitch.md` module template); no new framework (user rule: no bloat).

### 2.1 Stylise (new `FX_paint` rack: merges backlog row 71 "paint" with these)

**01 Line boil / animated-on-twos.** Look: hand-drawn animation feel: outlines wobble and re-draw at 8-12 fps while the video
holds on twos/threes; paper grain; slight posterised fills. Tool: *Spider-Verse*-style limited animation [K]; ISF Doodler /
Etch-a-Sketch exist but only draw lines [O listing, https://github.com/vidvox/isf-files]. Technique: time quantiser
(hold frame index = floor(t*hold_fps)) + Sobel edge + two or three noise-field seeds cycled per hold tick displacing the edge
UV; fill = posterise. TD: Cache TOP / Feedback hold on a Pulse CHOP at hold_fps; one compute GLSL (edge, displace, posterise,
grain). Pars: HoldFPS 6-24, Boil amount, LineWidth, Fill levels, Paper. Cost 0.3-0.5 ms, S. Fit: any clip or webcam; the
hold clock is independent of the 60 fps render, so it stays smooth elsewhere. Near: `fx_glitch_ghost` (frame difference),
td-port `halftone`; none hold-and-boil.

**02 Watercolour wash.** Look: bleeding pigment, darkened wet edges, paper granulation, soft white gaps. Tool: Keijiro
KinoAqua (shader adapted from a flockaroo Shadertoy; the README names no parameters) [O, https://github.com/keijiro/KinoAqua];
Arena Wire "Acuarela" [R: FX4 s1.7]. Technique: multi-offset gradient-guided colour smear (flockaroo style: sample along the
image gradient with several radii), edge darkening = gradient magnitude, paper = tiling noise multiply, pigment = low-freq
noise on saturation. TD: 2 compute passes at half res then upscale + edge pass at full. Pars: Wetness, EdgeDark, Paper,
Granulation, Palette lock (via `palette_map`). Cost 0.8-1.5 ms, M. Fit: stills and slow clips; complements 03. Near:
FX0 row 71 (Kuwahara oil), which is a different look.

**03 Painterly brush-stroke render.** Look: the picture rebuilt from visible oriented strokes, coarse to fine. Tool: Arena
"Strokes" (Wire) [R]; Sapphire AutoPaint, Brush:Oil [O index]; technique papers Haeberli 1990 / Hertzmann 1998 [K]. Technique:
structure-tensor orientation (blur of gradient outer product) -> strokes as instanced quads on a jittered grid, size by layer
(3 layers), colour = source at stroke centre, orientation = tensor angle, length by coherence; temporal stability by keeping
strokes screen-anchored and low-passing colour. TD: orientation compute pass + instancing (Geometry COMP / glsl MAT) of
40-60 k quads. Cost 1-2 ms, M. Fit: IMAG stylise; unlike FX_glitch it is not a filter. Near: `gen_interactive_ribbon` (strokes
from motion, not from an image).

**04 Engraving / banknote line screen.** Look: curved parallel lines whose thickness follows darkness, lines bending around
forms, like an etching. Tool: Sapphire Etching [O index]; ISF "Line Screen" is straight only [O listing]. Technique: take a
smoothed luminance L; lines = iso-contours of (y + k*L_blurred) so they warp along tone; thickness = smoothstep on L; optional
second crossing set for deep shadow. TD: single-pass GLSL TOP. Cost 0.3 ms, S. Fit: logos, portraits, posters. Near: FX4
G-PAINT cross-hatch (tonal art map, different).

**05 Distance-field contour echo.** Look: concentric coloured contour lines or bands growing out of (and into) any shape:
logo, name, silhouette; palette bands repeat, bounce or sine; the offset animates so the shape "ripples". Tool: Notch **Image
Distance** (luminance threshold -> inside/outside -> distance from the outline -> colour gradient, up to 16 colours, Clamp /
Repeat / Bounce / Sine, inward / outward / both, Colour Gap) [O,
https://manual.notch.one/2026.1/en/docs/reference/nodes/post-fx/stylisation/image-distance/]. Technique: threshold the input,
jump-flood distance transform (reuse `gen_sim_vor_jfa.glsl`: ~11 passes at 1080x1920 but half-res is enough), gradient function
on distance, palette from `palette_map`. TD: compute passes chained as in `gen_sim` voronoi. Pars: Threshold, Direction,
Scale, Offset (animatable, audio), Function, Gap, Fill, Blend. Cost 0.5-0.8 ms, S. Fit: top LED look for logos and names
(whole word rasters only, names never cut). Near: FX_synth `bands` (contours of luminance, not of a shape distance).

**06 Page-flip strobe.** Look: frames captured every N seconds flip over like pages with a shaded curl and motion blur.
Tool: Keijiro **StrobePages** (Auto Page Turn, Page Interval, Page Stiffness, Motion Blur with sample count, Shade Width /
Strength, Opacity) [O, https://github.com/keijiro/StrobePages]; ISF Flipbook, Inverted Page Curl [O listing]. Technique:
Cache/Feedback snapshot at the interval; cylinder-fold UV map (rolled page) with eased angle; 8-16 time samples for blur. TD:
one compute GLSL + Cache TOP. Cost 0.3-0.5 ms (blur samples cost), S. Fit: beat accents, transition bank (`FX_trans`).

**07 PS1 / early 3D console look.** Look: vertex wobble from low-precision snapping, affine (no perspective) texture swim,
dithered low colour depth, no anti-aliasing. Tool: Keijiro **Retro3D** (reduced vertex precision + affine texture mapping,
unlit) [O, https://github.com/keijiro/Retro3D] and **NoPersRetro** (Shader Graph "No Perspective" interpolation + vertex
quantisation + dithering) [O, https://github.com/keijiro/NoPersRetro]. Technique: in the GLSL MAT vertex shader quantise
clip-space xy to a coarse grid after the projection divide; pass UV with the `noperspective` qualifier (or UV*w, divide in
fragment); render at 320x240-ish via Render TOP resolution, nearest-filter upscale; Bayer dither + 15-bit colour in the
`fx_retro` dither module. Cost 0.2-0.5 ms (resolution is tiny), S. Fit: retro/game acts; works on every 3D look (`gen_sdf` is
raymarched, so this applies to mesh scenes: chrome logo, previz). Check: `noperspective` in MoltenVK GLSL (probe, T-35 rules).

**33 Hex / triangle cell mosaic with beat flips.** Look: image rebuilt from hexagons or triangles whose cells flip, recolour or
shrink on beat. Tool: ISF Hexagonalize, Triangle Mosaic, Grid Flip, Squares Wire [O listing]. Technique: cell id from hex/tri
lattice math, sample at cell centre, per-cell hash drives flip phase (scale Y through 0), gap lines. TD: single-pass GLSL. Cost
0.2 ms, S. Fit: cheap rhythm FX; sits next to `FX_glitch.mosaic` (quadtree). Near: td-port `pixel_fx`.

### 2.2 Light, glass, surface

**09 Saber energy beam on paths / text / masks.** Look: a hot white core with coloured exponential falloff along any line:
neon sign strokes, laser beams, logo outlines drawn on over time, with noise distortion and flicker. Tool: Video Copilot
**Saber** (free; core, glow falloff, spread, bias, distortion, applied to a solid, mask or text outline, 25 presets) [O,
https://www.provideocoalition.com/saber-new-free-effects-plug-video-copilot/]. Technique: build an SDF of the input: for
polylines an analytic capsule loop over up to 64 segments (Table DAT), for masks/text a JFA distance (as card 05); core =
1/(1+(d/w)^p), glow = sum of 2-3 exponentials with Spread and Bias; domain-warp d by noise for the Distortion; Start/End
animate the draw-on; colour core->halo ramp. TD: one compute GLSL; paths from `laser_path` (SOP/Text -> beam) so beams, signs
and ILDA share a path source. Cost 0.5-0.9 ms, M. Fit: logos, names (raster the whole word first), sign boards. Near: td-port
`beam_fx`, FX_film `streak` (those are image-driven, not path-driven).

**22 Thin-film holo-foil.** Look: oil-slick / soap-bubble / holographic foil colour that shifts with angle; turns footage
luminance into film thickness. Tool: three.js `evalIridescence` chunk and IQ cosine palettes already ledgered in
`L_shader_sources_licences.md` rows 4 and 12 [R]; Belcour & Barla 2017 thin-film BRDF [K]. Technique: thickness map =
smoothed luma/normal-from-luma + noise; interference colour per channel with phase 2*n*d*cos(theta), view angle from a
pseudo-normal; mix with the source. The PBR MAT has no iridescence (P_realtime_3d_looks s1), so this is a post/GLSL module.
TD: single-pass GLSL TOP, optional second input as normal map. Cost 0.2-0.4 ms, S. Fit: near-free colour on any footage or
chrome backgrounds; palette stays editable (user colour rule). Near: none built (sources only).

**23 Liquid-glass lens.** Look: translucent lens shapes (pills, blobs merging with smooth union) floating over video: edge
bevel refracts the background, blur behind, dispersion at the rim, Fresnel + specular highlight. Tool: liquidGL (aberration
option disperses R/B along the refraction vector) [S, https://github.com/naughtyduk/liquidGL], @ybouane/liquidglass (crop,
blur, refraction + chromatic aberration + Fresnel + rim, "dome" bevel mode) [S, https://liquid-glass.ybouane.com/], Liquid
Glass Studio (4 passes: background, V blur, H blur, composite; SDF shapes) [S, github.com/iyinchao/liquid-glass-studio].
Technique: SDF of up to 8 shapes (rounded rect/ellipse), smooth-union; bevel normal = gradient of distance near the edge;
refract UV = uv - normal*strength; blurred background via 2 blur passes (or Blur TOP at half res); R/G/B sampled at 3 slightly
different strengths; Fresnel rim + spec from the same normal. TD: 1 GLSL compute for shapes+composite, Blur TOP before it.
Shapes follow performers (person_mask centroid), beat, or a path. Pars: Shapes table, Thickness, IOR-ish Strength, Blur,
Dispersion, Rim. Cost 0.6-1.0 ms, M. Fit: 2025-26 look for lower-thirds, lens-over-crowd shots (the glass can magnify).
Near: td-port `elastic_lens`, `prism_glass` (no bevel/blur model).

**08 Light wrap + edge feather (compositing helper).** Look: the background light bleeds a few pixels over the keyed
subject's edge so people sit inside the plate instead of looking cut out. Tool: Boris BCC Light Wrap / standard keying
practice [K]. Technique: blur background (radius R), take the alpha edge band (alpha - eroded alpha, or distance to edge),
add `blurBG * band * strength` in screen/add, plus spill suppress (limit green or key colour) and an alpha feather. TD: one
compute GLSL with `person_mask` alpha + Blur TOP. Cost 0.2-0.4 ms, S. Fit: `imag-frames-production-requirements` ("real
alpha window over cam"); premultiplied rule for Arena applies to the output.

**21 Wet mirror floor.** Look: glossy stage floor mirroring the LED content or logo: flipped copy fading with distance,
slight ripple, blur growing with distance, Fresnel. Tool: a standard Notch/Arena floor trick [K]. Technique: 2D: flip +
gradient fade + displace by noise + vertical blur whose radius rises with y; 3D: Render TOP with mirrored camera + plane MAT
with roughness. TD: 2D = 1 GLSL; 3D = second Render TOP. Cost 0.3-0.6 ms, S. Fit: tall R02 faces over a floor line;
`FX_venue` (previz). Near: none built.

**34 Rain on glass.** Look: refracting droplets that run down the pane, blurred background, trails. Tool: BigWings
"Heartfelt" Shadertoy (name) [K]; Arena "Rain" effects are 2D drops only [K]. Technique: grid of droplet cells with hash
sizes, drops as a normal field (bumps + trails), refract sample UV, blur layer for fogged glass, wipe-clear mask optional.
TD: single compute GLSL + Blur. Cost 0.6-1.0 ms, S-M. Fit: moody intros, cinematic IMAG. Near: FX3 L9 "lens dirt" (dust, not
water).

### 2.3 Particles and simulations

**10 Fireworks (shell types, barrage).** Look: rockets climb with spark trails, burst as peony, ring, heart, willow,
chrysanthemum, crossette; glitter crackle, colour shift, smoke glow; barrages on drops. Tool: staple of Niagara/VFX Graph
sample sets and Shadertoy ("Fireworks" by BigWings) [K]; Particular-style Aux (child) spawning is already in FX4 G-PART2 [R].
Technique: shell state in a small buffer (position, velocity, fuse, type); on burst, spawn N child points with spherical /
ring / shaped direction tables, drag + gravity, colour-over-life ramp, glitter by hash flicker; trails by history or velocity
streak sprites; additive 1-px points + log tonemap (the `gen_points` path, T-112). Triggers: kick = launch, drop = barrage,
`Seed`. TD: BO_particles Aux spawn mode (so this is a preset pack on that engine) or a stand-alone compute chain. Cost 1-2 ms
@100-200 k points, M. Fit: finale; no limiter by user rule. Near: `BO_particles` ember/spark presets (no shells).

**11 Confetti / streamer cannon.** Look: bursts of tumbling two-sided paper pieces that flutter and fall; streamers as
short ribbons. Tool: Niagara marketplace packs and Notch cloners [S]; Audio Reactive FX packs [S,
https://docs.unrealengine.com/marketplace/ja/product/audio-reactive-fx-04]. Technique: instanced quads with random axis spin,
brightness = |dot(normal, light)| so faces flip bright/dark, air drag + sine flutter, terminal velocity; streamers = 6-8
segment Verlet chains. TD: BO_particles + instancing, or Geometry COMP with a state texture. Cost 0.8-1.5 ms @30 k, M. Fit:
drops, finale, count-ins. Near: none.

**12 N-body galaxy.** Look: a spiral disc of tens of thousands of stars with dust lanes; two galaxies collide on a trigger
and throw tidal tails. Tool: GPU Gems 3 ch.31 "Fast N-body simulation with CUDA" tiling [K]. Technique: all-pairs gravity with
softening, shared-memory tiles (FX6 probe: shared memory + barrier works to local_size 1024), leapfrog; 8-16 k bodies, rest as
decorative stars; init disc with rotation curve + halo; render with the density2d additive + log tonemap path. TD: compute
chain; budget 8 k^2 = 64 M interactions per step. Cost 1-2 ms (estimate; probe first), M. Fit: ambient space looks.

**15 Falling-sand playground.** Look: chunky pixels of sand, water, oil, lava, fire, plants, gas obeying simple rules; pour
from audio hits or from the performer's silhouette. Tool: Noita (GDC 2019 talk) and Sandspiel (github.com/MaxBittker/sandspiel) [K].
Technique: block (Margolus) cellular automaton on an RGBA8 state texture at 540x960, alternating checkerboard offsets so moves
never collide, material id + life in channels, emitters from `person_mask` / hand points / beat; palette via `palette_map`.
TD: 2-pass compute per step (even/odd), several steps per frame via Cache loop only if cost allows (T-46 form). Cost 0.5-0.8
ms, M. Fit: interactive, reads as pixel art on LED. Near: GEN_sim `ca` (Life-likes, Wireworld; not gravity materials).

**16 Ferrofluid.** Look: black glossy fluid whose surface erupts into a regular lattice of spikes under a "magnetic field",
merging blobs underneath; reflects a bright environment. Tool: ferrofluid displays in club/concert visuals [K]; Rosensweig
instability gives the hex spike lattice. Technique: raymarch SDF = smooth-union blobs + spikes displacement = field-strength *
hex-lattice cone profile above a threshold; chrome shading from an env map (P_realtime_3d_looks brand env); audio -> field
strength. TD: new scene in `gen_sdf` scene shader (8 scenes today). Cost 1.5-2.2 ms, M. Fit: dark chrome looks; hard on
anti-aliasing (use half-res + upscale).

**24 Liquid-metal particles.** Look: thousands of droplets that merge into mercury or chrome surfaces with a smooth skin, not
sprites. Tool: Notch **Soft Ball** renderer (each particle a squishy sphere; Max Radius, Spring Dampening, Smooth Iterations,
Subdivisions) [S, https://manual.notch.one/2026.1/en/docs/reference/nodes/particles/rendering/soft-ball-renderer/]; yeataro
TD-ScreenSpaceFluid (MIT, 2020, untested) [R: N_community row 11]; van der Laan et al. 2009 curvature-flow SSF [K]. Technique:
screen-space fluid: splat particle depth as spheres, bilateral/curvature-flow blur of depth, normals, thickness for
absorption, env reflection + Fresnel. TD: 4-5 compute passes at half res. Cost 1.5-2.5 ms @50 k particles, L. Fit: mercury
drops from BO/fluid2d; fix by reading yeataro's shaders first (it exists).

**17 Synthwave horizon.** Look: perspective grid receding to a striped sun, mountain silhouette, stars. Tool: VJ staple [K].
Technique: single-pass: 1/z grid lines, sun disc with horizontal cut bands that widen toward the bottom, 1D noise mountains,
star hash; bass -> grid speed, kick -> sun pulse. TD: one GLSL TOP. Cost 0.2 ms, S. Fit: retro acts; palette editable.

**18 Hyperspace star streaks.** Look: stars stretching to lines in a forward jump, optional tunnel flash. Tool: ISF
"Hyperspace" [O listing]; Arena WarpSpeed (Wire) [R: FX4 s1.7]. Technique: POP/compute points with z advancing, projected
streak length = speed; colour shift at jump; ramp speed on build-ups. TD: GEN_points mode (same additive path). Cost 0.5-1
ms, S. Fit: builds and drops. Near: `gen_points` density2d "starfield" preset (static dust, no streaks).

**19 Mirror-ball light spots.** Look: dozens of bright dots sweeping across the wall as a disco ball turns, with soft flare.
Tool: dance-floor staple [K]. Technique: ~1,500 facet normals on a sphere, rotate, reflect one light direction, intersect with
the wall plane, draw additive soft discs where the dot product is positive; faint halo. TD: POP points + instancing, or a
compute splat. Cost 0.3-0.5 ms, S. Fit: dance sets; also works as a light cue for the previz stage.

**20 Virtual laser show.** Look: fans of beams, rotating cones, tunnels and wave lines cutting through haze, EDM-style.
Tool: MadLaser/Beyond/Pangolin-style content [S: https://docs.madmapper.com/madmapper/6/7.-laser-madlaser lists generative
laser materials]. Technique: paths from the `laser_path` generators plus new fan/cone/tunnel shapes, drawn as additive thick
lines with radial shaft haze (reuse `px_haze` shafts). TD: extend `laser_path` sources + a screen look; no real laser output
needed. Cost 0.6-1.2 ms, M. Fit: EDM drops. Near: td-port `beam_fx`, `LP_laser_path` (ILDA path engine, not a screen show).

**28 Tentacles / anemone / jellyfish.** Look: soft chains that wave, curl and follow audio, in clusters on a sphere or
floating bells with trailing arms. Tool: Niagara **Audio Reactive FX 04** (55 tentacle- and worm-like effects) [S,
https://docs.unrealengine.com/marketplace/ja/product/audio-reactive-fx-04]. Technique: chain of N segments with a travelling
sine + audio-phase offset (FK), instanced capsules/spheres with PBR; bell = displaced hemisphere with pulse. TD: Instancing
from a CHOP/compute chain or a `gen_sdf` scene with smin capsule chains. Cost 0.5-1 ms, M. Fit: creature looks; keeps clear of
text areas.

**30 Depth-buffer scanner grid (sonar).** Look: a bright ring or plane sweeps across the 3D scene; surfaces show a thin world
grid and glow where the front passes. Tool: Keijiro **SonarFx** ("renders animated wave-like patterns on all surfaces", a
replacement shader; MIT) [O, https://github.com/keijiro/SonarFx]. Technique: reconstruct world position from the depth
buffer (Render TOP depth + inverse view-proj), distance from origin -> ring width/brightness, grid = fract(world*k) lines,
noise break-up. TD: one GLSL post pass in `px_post`. Cost 0.3 ms, S. Fit: scan/reveal moments on splat and mesh scenes. Near:
PX `shockwave` effector (acts on points, not on a depth-buffer grid).

### 2.4 Interactive, stills and baked content

**31 2.5D depth-parallax photo animator.** Look: a still image becomes a slowly moving 3D scene: camera drifts +-10-15
degrees, foreground slides over background, depth-of-field, volumetric dust between layers. Tool: Depth Anything V2 Small
(Apache-2.0, 66.7 ms round trip on this Mac, `T_realtime_ml.md` s3.4) [R, https://github.com/DepthAnything/Depth-Anything-V2];
"3D photo" research (Kopf et al. 2020) and apps [K]. Technique: depth once per still (offline or on load, not per frame):
smooth + edge-aware filter; render a dense grid mesh displaced by depth (Geometry COMP or instanced GLSL MAT) with a camera
path; hide disocclusion by penalising stretch (discard long triangles, fill with a blurred background layer built by dilating
the far depth edge); add DOF and fog from depth; optional dust particles per depth layer. TD: Movie File In -> depth TOP (from
`camera_bridge`) -> displacement MAT -> Render TOP. Cost 0.6-1.2 ms per frame + one ML call per new still, M. Fit: the user's
generated Flow/ImagineArt stills (production rule: stills approved before video); S_trend row 7 ("hand-painted poster
theatre") is the same idea with cut-out layers. Near: `DC_depth_cam` (live depth), none for stills.

**25 Skinner shards + speed trails on a performer.** Look: the silhouette is replaced by random-triangle shard geometry
(long, thin triangles stretched across the body) plus particle bursts and trails whose width/size follow speed. Tool:
Keijiro **Skinner** (Glitch: 21,845 triangles between random source vertices, thresholds pull out long/large ones; Particle:
life and rotation scale with vertex speed; Trail: width by speed, trail length from a template) [O,
https://github.com/keijiro/Skinner]. Technique: sample N points from depth cam / person mask (grid POP), velocity = position
minus previous frame's (ring buffer or Cache), triangle picks 3 random point indices per tri per frame with an edge-length
reject, trails = line strips from a history ring. TD: compute chain + instanced triangles; reuse `BO_particles` for the burst
half. Cost 1-2 ms, M. Fit: camera acts, body-reactive. Near: `GEN_interactive` ribbon/pigment (brush-like), FX_destroy
`shatter` (shards fall, they do not wrap the body).

**26 VAT: baked-sim playback.** Look: Blender/Houdini fracture, cloth, fluid or soft-body sims play back at full quality
and 60 fps, scrubbable by audio. Tool: SideFX Labs VAT as used in Keijiro **HdrpVatExample** (Houdini exports .fbx + .exr
position textures + .json with frame count and position min/max; Soft, Rigid, Fluid shader graphs; Soft Lerp interpolates frames;
sprite VAT for particles) [O, https://github.com/keijiro/HdrpVatExample]. Technique: exporter in `tools/blender_export.py`
bakes per-vertex positions (and per-piece position+quaternion for rigid) into 32F EXR rows (frames) x columns (vertex id);
TD: a GLSL MAT vertex shader fetches by `gl_VertexID` and current frame (lerp), normal from baked or recomputed; fluid = sprite
mode via a Geometry COMP of points reading the same texture. Pars: Frame, Speed, Loop, Audio scrub. New tool `td_vat_load`
(json + exr -> MAT). Cost 0.3-1 ms regardless of how heavy the sim was, M (+ exporter 2 h). Fit: closes the Blender
integration (BC): shatter/DG-26 3D destruction at zero runtime sim cost.

**27 Metavido decoder (colour + depth video).** Look: a performer recorded once (iPhone LiDAR) replays as a coloured
point cloud or mesh with the original camera path. Tool: Keijiro **Metavido** / MetavidoVFX (volumetric video "with camera
tracking data, using a burnt-in barcode"; VFX Graph) [O, https://github.com/keijiro/MetavidoVFX]; the container spec is in
the separate Metavido repo (not opened) [S]. Technique: split the packed video frame into colour and depth halves, decode
depth (hue-encoded) and the barcode (camera pose, projection), unproject to points with the intrinsics. TD: Movie File In ->
GLSL decode -> existing `Source depth` colour+depth pair path of PX / `pointcloud`. Cost 0.5-1 ms, S-M. Fit: recorded
dancers as holograms; no live camera needed (stored-clip rule). Near: BL `pointcloud` (depth from image) and RUBENFRO K19.

**32 Fur / grass shell field.** Look: video or a colour field rendered as fuzzy fur or grass that bends in wind and ripples with
audio. Tool: Smode legacy presets "fur box", "fur geosphere" [O,
https://www.smode.io/doc/ref/compo/catalog/legacy-presets-catalog.htm]; Keijiro KvantGrass / KvantWig (listing only) [S].
Technique: shell texturing: draw the mesh 24-32 times with each layer pushed out along the normal, strand mask = hash cell
threshold falling with layer height, colour from the source texture, wind = noise offset growing with height. TD: instanced
Geometry COMP layers or one GLSL MAT with layer index as instance id. Cost 1-1.5 ms, M. Fit: tactile looks on plane or
sphere; mind the word rule: never over text.

### 2.5 Generators

**13 Aurora curtains.** Look: vertical rippling light curtains, green to magenta, over a starry sky. Tool: Shadertoy
"Auroras" (nimitz) family [K]. Technique: 24-40 raymarch steps through layered curtain noise (triNoise2d style), colour by
height, star hash; slow time. TD: single GLSL at half res + upscale. Cost 1-1.5 ms, S. Fit: intros, calm sections. Near: AC
"Section Aurora" is an audio-reactive colour field, a different look.

**14 Stylised ocean + caustics.** Look: rolling sea with sun glitter, foam, or seabed caustics. Tool: Shadertoy "Seascape"
(TDM) [K]; Tessendorf FFT ocean [K]. Technique: heightfield via warped sine FBM raymarch (cheap) or a 256^2 compute FFT with
foam from the Jacobian; caustics = Voronoi/normal-focus pattern projected on a floor; sun spec + sky gradient. TD: single
GLSL (cheap) or compute chain (FFT). Cost 1.5-2.5 ms, M. Fit: water acts; caustics reusable on other scenes (FX4 G-GEN
mentions Caustics only as a Voronoi texture).

**29 Jigsaw tiles + puzzle transition.** Look: the screen cut into interlocking jigsaw pieces: coloured, chessboard-shaded or
each piece showing the source image; pieces fly out or in on cuts. Tool: Notch **Jigsaw** generator (Use Num Tiles, Gap Width,
Tile Shading: random from gradient / chessboard / source image, Border Colour, Seed) [O,
https://manual.notch.one/2026.1/en/docs/reference/nodes/generators/jigsaw/]. Technique: per-cell grid with a bezier/circle
knob on each edge chosen by a hash shared by both neighbours; tile id from the grid cell and the knob test; transition = tile
id texture + per-tile transform (needs a second pass or instanced quads). TD: single GLSL for the pattern; transition via
`FX_trans` family. Cost 0.3-0.5 ms, S. Fit: cuts and reveals.

## 3. Build order and parallel lanes (nothing built yet)

Time per item as above; 5 lanes; every lane registers with `tools/lane.py`; risky GLSL on the scratch TD first (T-83).

| Lane | Items | Why together | Est. |
|---|---|---|---|
| A (stylise rack) | `FX_paint`: 05, 01, 04, then 02, 03, 06 | one rack + template, 05 reuses JFA | ~14 h |
| B (light / glass) | 09, 23, 22, 08, 21, 34 | shared SDF/JFA helper from 05, shared blur | ~16 h |
| C (particles / sim) | 10, 11 (BO Aux first), 18, 19, 12, then 24 | all on the additive/point engines | ~18 h |
| D (sim / generators) | 15, 17, 13, 14, 29, 33 | GLSL one-pass or small compute | ~14 h |
| E (3D / interactive) | 26, 31, 25, 27, then 07, 30, 16, 28, 32, 20 | Blender, depth, ML helper | ~26 h |

Total ~85-90 agent-hours; wall clock about 18-20 h with 5 lanes. Pilot first (one item, then the rest at once): 05 (smallest
and starred) for lane A/B, 10 for C. Probes before building: (a) JFA at half-res timing (FX6), (b) `noperspective` varying in
a GLSL MAT (card 07), (c) EXR 32F texture row fetch by `gl_VertexID` in a MAT (card 26), (d) shared-memory N-body tile at 8 k
(card 12), (e) depth to mesh displacement MAT on a 1080x1920 grid (card 31).

## 4. Considered and rejected (so nobody re-researches them)

| Idea | Why not |
|---|---|
| Deep Glow (inverse-square multi-radius HDR glow, RGB radius multipliers) [S: aescripts.com/deep-glow] | A bloom mode: add as a `Falloff` option to `FX_film.diffusion` / `px_bloom`, not a module |
| ISF Long Exposure / Motion Heat Map [O] | Long Exposure = absorb/discharge feedback = `FX_motion_trail`; heat map = difference + palette ramp (`fx_glitch_ghost` + `palette_map`) |
| Plexus / Notch Line Connection / Smode Connect Points | RUBENFRO G5 (lines `connect`) plans it; td-port `Constellation` exists as a spec |
| Marching-cubes isosurface (Keijiro ComputeMarchingCubes [O]) | Same look from `gen_sdf` smooth-union raymarch with no mesh; writing a SOP/POP mesh from compute is a crash risk on 31550 |
| Keijiro KinoGlitch / Kino Recolor / Utility / TestCard / Streak | covered by FX_glitch, palette_map, FX_film, TP_test_pattern |
| Keijiro LightGridShader, KinoFeedback, KinoEight | LED wall emulation (`FX_venue`), `FX_synth.vfeedback`, `FX_retro` |
| Cables.gl / Millumin / MadMapper basics | all basic filters TD has natively |
| Notch Greeble, Onion, Pyroclastic, Tessellate, 3D Deformer bank | 3D mesh authoring tools; Blender (BC) is the better place, then card 26 plays the result |
| Notch Dot Matrix particles | `FX_retro.smalldisplay` + `FX_venue.ledwall` |
| Sapphire PrismLens/ColorFuse/WarpMagnify/Hotspots/TimeAverage | tiny; G-WARP bank / grade; TimeAverage = Cache TOP average |
| Searchlight reveal (Arena Wire SearchLight) | a masked brightness spot: `DX_field` radial + mask, no module |
| Synesthesia scene library, Magic Music Visuals modules | names not readable from public pages (403 / app-only): open the apps to list them |

## 5. Open questions for the user

1. New rack `FX_paint` (stylise: boil, watercolour, painterly, engraving, distance echo, page-flip) or fold into `FX_retro`/`FX_film`? (recommended: new rack, same module template, merges backlog row 71)
2. Card 31 needs one ML call per new still (Depth Anything V2 Small, Apache-2.0, helper exists). OK to wire it into the camera_bridge helper as a `depth_still` kind?
3. Card 26: bake sims in Blender only (installed, 5.2.2), or also accept Houdini VAT files if someone sends them?
4. Fireworks / confetti: pre-trigger on kick automatically, or on a pad / cue only?
5. Shadertoy references: all unopened (403). Allowed to ask you for specific Shadertoy URLs (user may paste), or is memory + clean-room maths enough?

## 6. Light verification done for this file

| Claim | Check | Result |
|---|---|---|
| Keijiro repo facts | opened 8 repo pages, `gh api users/keijiro/repos` for the 295-repo list | confirmed (descriptions above are from those pages) |
| Notch Image Distance / Jigsaw parameters | opened both manual pages at offset 100000 | confirmed |
| Notch Soft Ball = squishy spheres, not fluid surface | search snippet of manual 2026.1 | quoted as snippet only [S] |
| ISF names (Hyperspace, Hexagonalize, Triangle Mosaic, Grid Flip, Doodler, Etch-a-Sketch, Long Exposure, Motion Heat Map) | `gh api repos/vidvox/isf-files/contents/ISF` (371 entries) + two raw headers | confirmed |
| Repo novelty | grep of builders/, docs/builds/, docs/research/ for ~120 keywords (see s0); keywords with 0 hits: fireworks, falling sand, ferrofluid, light wrap, saber, sonar, retro3d, hyperspace, engraving (1 hit in AN list only), page turn, metavido, VAT | consistent with "new" |
| JFA, laser_path, px_haze, BO_particles, person_mask, td_import_blender exist | `builders/` listing and `docs/research/README.md` | present |
| Depth Anything V2 Small figures | `T_realtime_ml.md` lines 16, 43, 99 | as cited [R] |

Not checked: any par name in TD, any ms figure, Shadertoy/ISF code (not copied), Synesthesia/MMV/Plexus contents.
