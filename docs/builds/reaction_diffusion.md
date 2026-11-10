# reaction_diffusion: GN_reaction_diffusion Gray-Scott COMP (live-verified v1 on 2025.31550, 26 Oct 2026, T-108)

`/project1/lab/GN_reaction_diffusion`. Gray-Scott reaction-diffusion with every pass written as a **compute** GLSL TOP
(T-46/T-47), the step pass running `npasses = Steps` (T-91 (3)). Research: `docs/research/O_generative_simulations.md`
4.2, `BN_fluid_cloth_sims.md` 5.9 (Karl Sims' scheme: 3x3 Laplacian centre -1 / edges 0.2 / diagonals 0.05,
DA 1, DB 0.5, dt 1). **No limits** (user rule): open ranges, nothing clamps the look.

## Files
| File | What |
|---|---|
| `builders/reaction_diffusion.py` | builder, `build(parent_path='/project1/lab', panel=True)`, idempotent, T-70 safe |
| `builders/reaction_diffusion_logic.py` | pure logic (engine: steps / pause / stopat, reset / reseed, preset morph go + LFO + audio, effectors / points / mouse / bursts -> rows, palettes; par + pass tables) + numpy reference of every sim shader (copied into the COMP's `rd_logic` DAT) |
| `builders/glsl/rd_common.glsl` + `rd_{maps,seed,rd,look,preview,stat}.glsl` | the 6 compute passes |
| `test/test_reaction_diffusion.py` | 34 offline tests (~0.5 s): hash parity with an independent lowbias32, rest state is an exact fixed point (iso / aniso / flow / pearson / clamp edge), stencil weights, mass conservation, one-cell drift + wrap, anisotropy spreads along x only, morph is a linear f/k blend, pearson map, solids held, seed patterns, rows inject / erase / morph memory, engine (reset, pause, step, stopat, reseed, morph go + LFO, effector world->uv mapping, row sources, testmode, kick + refractory, audio morph, pack/unpack, palettes), shader contract (uniforms == pass table, <= 3 inputs, constants, menu order, ASCII), builder text (callbacks parse, every uniform has 4 expressions, no TOP readback / text measuring / typeface changes) |

## Maths
State rgba32float at sim res: r = A, g = B, b = local morph (effectors), a = solid (in2 mask).
Per pixel `m = Morph(+go +LFO +audio) + Mapamt * map(uv) + Mapimg * in4 + state.b`, `f = mix(fA, fB, m) + Feedoff`,
`k = mix(kA, kB, m) + Killoff` (Mapmode pearson: f along y Fmin..Fmax, k along x Kmin..Kmax: the classic parameter map).
Laplacian = sum of weighted differences (exactly 0 on a uniform field). Anisotropy: `(1 - An) lap9 + An * 0.6 * d2/dd2`
along a direction field (angle / radial / swirl / along flow / noise). Flow: the whole stencil is read at `p - v`
(bilinear, v in cells per step: in3 RG, drift, swirl, curl noise). Clampstate keeps A, B in 0..1.
Presets (f, k): coral .0545/.062, mitosis .0367/.0649, worms .078/.061, **spots .03/.0625, waves .018/.051** (the
literature pairs .035/.065 and .014/.045 die out in this scheme, checked with the reference over 6000 steps), mazes
.029/.057, solitons .025/.06, holes .039/.058, chaos .026/.051, u-skate .062/.06093, custom (Customf/Customk).

## Network (stages L-to-R, titled boxes)
Controls (zkit, `rd_pulses`, `rd_logic`) | Effectors (`eff1`, `eff2` Null COMPs) | 1 Inputs (`in1..in4`, `blank`,
`seed_text`, `seed_sel` -> `seed_prep`, `mask_sel` / `mmap_sel` / `flow_sel` -> `fx_maps`) | 2 Control sources (`in5`
points, `in6` audio -> `aud_low`, `mouse`, `engine`, `rows`) | 3 Seed + inject (`state_fb` <- fx_rd, `fx_seed`) |
4 React (`fx_rd`, npasses = Steps) | 5 Look + out (`ramp`, `ramp_in`, `fx_look` -> `out1`, `out2` = raw state,
`fx_preview` -> `preview`) | 6 Stats (`fx_stat` -> `an_avg` -> `tc_avg` -> `stats`, internal).
Outputs are TOPs only: out1 look (Resw x Resh, 16F, premultiplied option), out2 raw state (sim res, 32F).
The COMP viewer shows `preview` (look + gizmos) while Showeff is on, else out1.

## Inputs, effectors, options
- **Effectors**: Null (or any object) COMPs named by `Effectors` (space-separated names / patterns relative to the
  COMP, or absolute paths; default `eff*`). World -> sim plane: `Planeh` world units tall, centred at 0; radius =
  `Radius` x max(sx, sy) / Planeh. Each Null's Effector page: Active, Strength (+ inject B, - erase to A = 1, B = 0),
  Radius, Morph (pushes its area toward Preset B), Falloff gauss / linear / hard / ring; missing pars fall back to the
  COMP's Eff* pars. Gizmos (cyan, red when erasing) in `preview` only. Up to 32 rows (effectors + in5 points + mouse +
  bursts). Defaults: eff1 gentle inject (0.03), eff2 morph-only area (Morph 1, radius 0.18).
- **Seed** on Reset / Reseed: centre square, random spots, noise, ring, stripes, image (in1), text (Seedtext, TD's
  default typeface), clear. Continuous `Inject` from in1 or the text.
- **Mask** in2 (R > Maskthresh = blocked), **flow** in3 (RG cells/step), **morph map** in4 (luminance x Mapimg).
- **Audio** in6: kick bursts (low band Lowhz, threshold + refractory), level spots, level -> morph.
- **Look**: value B / A-B / 1-A / edges, Lo..Hi, palette (PRISM, ink, bio, fire, ice, mono, custom Pal1..5) / Ramp TOP
  (inner `ramp` or `Ramptop`) / raw / gray, invert, emboss shade + light angle, edge glow, exposure, gamma, alpha
  opaque / value, premultiplied.
- **Control**: Pause, Step, Stopat (exact step cap: passes beyond copy), Testmode fixed (no injectors / audio / inject).

## Live verification (26 Oct, 2025.31550)
| Check | Result |
|---|---|
| Scratch TD build (T-83) | 72 ops, notes [], no errors / warnings; every pass compiles |
| Parity, centre seed, coral, 600 steps (Stopat), 288x512 | out2 vs float64 reference: B rel L2 8.0e-7, A 5.8e-8; stats meanb 0.006610 vs 0.006610, cover 0.015408 both |
| Parity, spots seed (GLSL hash), worms->mazes noise morph map, noise anisotropy 0.7, curl flow 0.3, 240 steps | stats meana 0.608775 / ref 0.608779, meanb 0.442777 / 0.442777, cover identical (0.606228); rel L2 A 8.7e-4, B 3.4e-4 (float32 bilinear + noise) |
| Effector rows (eff1 moved, linear falloff, morph 0.5; eff2 scaled 1.5) seed + 2 steps | B rel L2 1.2e-6, morph field 2.0e-7, sums equal to 5 digits |
| Main TD build | 74 ops + zkit panel (100 knobs), td_errors none, td_layout check ok |
| Look | coral maze; eff1 injects; eff2's area turns to mitosis spots; gizmos drawn (output/ capture) |
| Cost (pane on the lab, out1 pulled, other lanes running; median per frame over 300) | Steps 12 / Simh 512: fx_rd 2.2-2.6 ms, total 4.6-5.1. **Defaults now Steps 8 / Simh 448**: fx_rd 1.58, fx_look 0.68, fx_seed 0.60, engine 0.55 CPU, rows 0.08, state_fb 0.07 = ~3.6 ms (+0.6 ms when the preview is viewed); td_watch 5 s 59.9 fps (54 cooks/s of this COMP) |

Perf notes: fx_rd is dispatch-bound (~0.2 ms per pass, T-100): fewer Steps is the lever; Simh barely matters.
fx_look went 1.28 -> 0.49 ms with hardware bilinear (inputextenduv follows Edge). Under 3 ms would need several RD
steps per dispatch (shared-memory tiles with a halo; iso / no-flow path only) - not built.

## Rules learned (T-108)
- Script CHOP: `numChans` cannot be read while it cooks; writing values in place (`scriptOp[i][0] = v`) works when the
  callback remembers its own channel list (STATE['chans']).
- A cache filled in the build's first cook (before the Nulls existed) stayed empty: empty caches re-scan every frame.

## Rebuild
```
ns = dict(globals()); exec(open('<repo>/builders/reaction_diffusion.py').read(), ns); ns['build']('/project1/lab')
```
Measurement without the pane: pull out1 from a `run(..., delayFrames=1)` chain and sum cpu+gpu of ops whose
`cookAbsFrame` equals fx_rd's (absTime.frame is a different counter).

## Perf wave 27 Oct (b3): fused steps
`Fusesteps` (Sim page, on): with Flowmode and Anisomode off, fx_rd runs up to 8 steps per dispatch on a 16 x 16 tile
with an 8-cell halo in shared memory (`rd_rd.glsl` `rdFused`, npasses = ceil(Steps / 8), `rd_logic.fused_ok` /
`rd_npasses`); otherwise one dispatch per step as before. Bit-exact vs the per-step path on b3; COMP 4.4-4.7 ->
2.2-2.3 ms at the defaults (docs/builds/PERF_FINAL_27OCT.md "Perf wave 27 Oct (b3)").
