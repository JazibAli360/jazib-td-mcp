# physarum: GN_physarum slime mould COMP (live-verified v1 on 2025.31550, 26 Oct 2026, T-112)

`/project1/lab/GN_physarum`. Jones / Jenson physarum: agents with a heading and three sensors (front-left, front,
front-right) sense a trail map, rotate, move and deposit; the trail diffuses (3x3 mean) and decays. Research:
`docs/research/O_generative_simulations.md` 4.3 (reimplemented from the model description; no GPL / unlicensed code).
Every sim pass is a **compute** GLSL TOP (T-46/T-47). The deposit (a scatter) is a **Render TOP of one 1-px point per
agent with additive blending into rgba32float**: Mac has no float atomics (research O F13), and blending gives exact
sums. **No limits** (user rule): open ranges, nothing clamps the look.

## Files
| File | What |
|---|---|
| `builders/physarum.py` | builder, `build(parent_path='/project1/lab', panel=True, upto=None)`, idempotent, T-70 safe (`upto=1` = sim only) |
| `builders/physarum_logic.py` | pure logic (engine: run / pause / stopat, reset on Agents/Simh/Res change, preset morph go + LFO + audio, gains, kick speed envelope, effectors / points / mouse / bursts -> rows, palettes; par + pass tables) + numpy reference of every sim shader (copied into the COMP's `ph_logic` DAT) |
| `builders/glsl/ph_common.glsl` + `ph_{maps,agents,trail,look,preview,stat,astat}.glsl` | the 7 compute passes |
| `builders/glsl/ph_deposit_{vertex,pixel}.glsl` | the deposit GLSL MAT (points) |
| `test/test_physarum.py` | 34 offline tests (~2.5 s): hash, agent side, presets/morph, pages, exact deposit, trail mass (diffuse conserves, decay scales), steady-state mean = analytic, every preset forms a network, Jones rule turn directions, species avoid/attract, attractor gathers / repeller empties, bounce bounds + mask blocks, seeds (image seed lands on the image), species layouts, respawn fraction, stats order, engine (reset frame, size-change reset, pause / step / stopat, morph + gains + audio + testmode, morph go, kick speed + burst frames, effector / mouse rows), rows pack, shader contract (uniforms == pass table, <= 3 inputs, menu indices, `TDPos()` in the MAT), ASCII, builder text |

## Model (one sim step per frame; each step needs a deposit render)
Agent texture rgba32float, side x side (side = ceil(sqrt(Agents))): x, y (trail cells), heading (0..2pi), species
(-1 = unused slot). Trail rgba32float at sim res: r g b = species 0 1 2.
- **Sense** at `floor(p + SO * dir(a + {SA, 0, -SA}))`: `dot(trail.rgb, W[s]) + Foodw * food + field(rows)`;
  W[s][s] = Selfw, others = Otherw (- avoid, + attract).
- **Rotate** (Jones): F > L and F > R keep; F < L and F < R +-RA (hash); L > R +RA; R > L -RA; plus Jitter.
- **Move** Step (x species speed spread, x kick envelope); Edge wrap or bounce (mirror + reflected heading); a masked
  target (in2) keeps the agent and gives a random heading; Respawn re-places a fraction at random each frame.
- **Deposit**: `deposit` Render TOP: rgb += Deposit in the agent's species channel, a = agent count.
- **Trail**: T1 = T + D; T2 = T1 + Diffuse (mean3x3(T1) - T1); T3 = T2 (1 - Decay) + injects (effector Deposit,
  Foodinject x food); mask -> 0. Steady-state mean (wrap, no injects) = (1 - Decay) N Deposit / (Decay W H): the
  `stats` CHOP's `expected` channel.
Presets (SA deg, SO cells, RA deg, step, deposit, decay, diffuse, jitter): network 22.5/9/45/1/1/.1/1/0 (Jones),
veins 30/20/15/1.5/1/.05/.6/0, cells 45/14/45/1/1/.15/1/0, coral 11.25/28/11.25/1.2/1/.08/.5/2, worms
90/4/45/1.5/1/.2/1/0, storm 22.5/12/45/3/1/.2/1/10, mesh 60/6/30/1/1/.12/1/0, custom (Custom* pars). Preset A -> B
morph (Morph + Morphgo + LFO + audio), then the x-gain pars (Sagain ... Jittergain) multiply. Distances are in trail
cells: changing Simh changes the look's scale.

## Network (stages L-to-R, titled boxes)
Controls (zkit, `ph_pulses`, `ph_logic`) | Effectors (`eff1` attractor +15, `eff2` repeller -15) | 1 Inputs (`in1`
food / image seed, `in2` mask, `seed_text`, `food_sel`, `mask_sel` -> `fx_maps`, blanks) | 2 Control sources (`in5`,
`in6` -> `aud_low`, `mouse`, `engine`, `rows`) | State (`agents_fb`, `trail_fb`) | 3 Agents (`fx_agents`, `out3`) |
4 Deposit (`pts` Grid POP, `dep_mat`, `dep_geo`, `dep_cam`, `deposit`) | 5 Trail (`fx_trail`, `out2`) | 6 Look + out
(`ramp`, `ramp_in`, `fx_look` -> `out1`, `fx_preview` -> `preview`) | 7 Stats (`fx_stat`/`fx_astat` -> Analyze ->
`stats`, internal: only updates while pulled). Outputs: out1 look (Resw x Resh 16F), out2 raw trail (32F), out3 agents.

## Options
Agents (default 262144), Simh (960), Edge, Species 1-3 + layout (interleave / bands / rings), Selfw / Otherw, species
speed spread; presets + morph + gains; seeds random / disc / ring / spiral / lines / image (in1) / text / centre point,
start heading random / outward / inward / swirl, Respawn (default 0.002 per frame: keeps the network exploring instead
of coarsening into a few strands, see below); food map (in1 or text: attract Foodw, trail inject Foodinject), mask in2;
effector Nulls (`Effectors` pattern; Effector page Active / Strength (+ attract, - repel) / Radius / Deposit /
Falloff), in5 points, mouse attract / repel; audio in6: kick -> step x Kickspeed with Kickrelease envelope + burst rows
(Burststrength, Burstframes), level -> step / deposit / sensor angle / morph; look: tone soft / linear / log, species
colours (PRISM orchid / pink / gold) or palette / ramp / gray, halo glow, agents view, exposure, gamma, background,
alpha, premultiplied; Pause, Step, Stopat, Testmode fixed (no rows / audio / food / respawn).

## Live verification (26 Oct, 2025.31550)
| Check | Result |
|---|---|
| Deposit probe (scratch) | 262144 points -> render sum 262144, per-cell max diff 0 vs np.add.at |
| Scratch build | 46 ops (upto=1), then 88 with look/stats/panel; no errors; layout check ok |
| Parity step 1 (262k, disc, 540x960) | agent positions max diff 1.4e-4 (float32), 99.995 % same cell; trail sum 235929.596 vs 235929.600; stats identical |
| Parity 5 / 20 / 300 steps | chaotic divergence from float32 floor/compare flips (90 % same cell at 5 steps, respawn on or off alike); stats at 300: mean 4.55111 both (= analytic), cover 0.14688 vs 0.14701, peak 0.0987 vs 0.0981 |
| Main build | 89 ops + zkit panel (98 knobs), td_errors none, layout check ok |
| Steady mean on main | 262k: 4.5511 = expected; 1M: 18.2044 = expected |
| Look (main, saved preview) | veins converge on eff1, radiate from eff2; 3 species in bands keep apart (Otherw -1); morph go and bursts (5 rows) live |
| Cost (other lanes running, out1 pulled, median per frame over 300) | **262k / 540x960: 4.4 ms** (deposit 2.2 = Render TOP CPU ~1.6 + GPU 0.6, trail 0.5, engine 0.5, agents 0.5, look 0.45), real 59.2 fps. **1M / 540x960: 6.4 ms** (deposit 3.8, agents 0.8), 59.4 fps. **1M / 1080x1920: 8.0 ms** (deposit 4.4, agents 1.3, trail 0.95), 58.8 fps |

Over the 3 ms budget at the default: the deposit Render TOP's CPU side (Rosetta draw overhead, cf. T-90 / T-100) is
the floor. Cheaper settings: fewer Agents (the deposit GPU scales with them), and the stats/preview only when viewed.
Not built: a compute scatter (racy without atomics) or several agents per drawn vertex.

## Rules learned (T-112)
- GLSL MAT on POP points: read the position with `TDPos()`; the raw `P` attribute gave garbage (4 px of 0.7).
- A Render TOP of 1-px points (`gl_PointSize = 1`, aa1, blend one/one, depth off) into 32F is an exact scatter-add.
- The Jones model coarsens into a few thick strands over minutes (reference, every preset); Respawn keeps it alive.

## Rebuild
```
ns = dict(globals()); exec(open('<repo>/builders/physarum.py').read(), ns); ns['build']('/project1/lab')
```
Measurement without the pane: pull out1 from a `run(..., delayFrames=1)` chain and sum cpu+gpu of ops whose
`cookAbsFrame` equals out1's (T-102). Parity: Testmode fixed + Stopat N + Reset, read out3 / out2 >= 2 frames after it
stops (scratch TD), compare with `physarum_logic` (`seed_agents`, `agent_pass`, `deposit_map`, `trail_pass`).

## Perf wave 27 Oct (b3): uniform array + cached pars
Engine-fed uniforms (uAg, uCtl, uSense, uMove, uSpec, uSeed, uFood, uTrail, uLook3, uPal0-4) come from the `uni`
Script CHOP as one `uniform vec4 uV[14]` (the builder rewrites the declarations to `#define uX uV[k]`; .glsl files
unchanged); `ph_parwatch` tells the engine when to re-read its pars. Bit-exact; CPU 2.2-2.4 -> 1.6-1.75 ms, total
~3.9 ms (deposit Render TOP is the floor; LEARNINGS T-214, PERF_FINAL "Perf wave 27 Oct (b3)").
