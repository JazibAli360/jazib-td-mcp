# FG_fps_governor: hold 60 fps, any COMP can follow (28 Oct 2026, TD 2025.31550)

`/project1/lab/FG_fps_governor`: a small generic controller. It measures the real frame rate, keeps a quality step
with hysteresis and publishes it on `out1`. **It never writes another COMP's pars**: consumers read it, so manual
control always wins (a consumer that is not bound, or whose own switch is off, ignores it). `Active` is **off** by
default.

Files: `builders/fps_gov.py` (builder), `builders/fps_gov_logic.py` (pure logic, copied into `fg_logic`),
`test/test_fps_gov.py` (offline, 18 tests: `python3 -I -m unittest discover -s test -p 'test_fps_gov.py'`).
Build / refresh in TD: `ns = dict(globals()); exec(open('<repo>/builders/fps_gov.py').read(), ns); ns['build']('/project1/lab')`.

## Pars (page Governor = the zkit Main tab, 8 controls)
| Par | Default | What |
|---|---|---|
| Active | off | off = 0 cooks, out1 = quality 1, step 0, fps 0, headroom 0 |
| Target | 60 | fps to hold |
| Downafter | 30 | too-slow frames in a row before one step down |
| Upafter | 300 | good frames before one step up (not necessarily in a row; a too-slow frame restarts it) |
| Steps | 5 | number of steps (0 = never below 1.0) |
| Floor | 0.25 | quality at the last step |
| Upmargin | 3 ms | frame-cook headroom needed to step up; a slow frame counts only below it |
| Reset | pulse | fresh state, quality 1 |

## How it works
- `fg_frame` (Execute DAT, `onFrameStart`, active only while `Active`): interval = `time.perf_counter()` between frame
  starts; busy = `perform1` (Perform CHOP) `msec` every 4th frame. Both smoothed (EMA, ~10 frames). headroom_ms =
  1000 / Target - busy.
- Too slow = smoothed fps < 0.95 x Target **and** headroom < Upmargin (a drop while this TD's own frame is cheap comes
  from outside; lowering quality would not fix it). Keeping up = fps >= 0.985 x Target and headroom >= Upmargin.
  In between: hold. Each step change re-seeds the EMA. A step down within Upafter frames of a step up doubles the
  next up wait (max 8x); it resets once a step up holds.
- quality = 1 - (1 - Floor) x step / Steps. `vals` (Constant CHOP) -> `out1`: `quality`, `step` written at once,
  `fps` / `headroom_ms` every 30 frames (each write re-cooks out1's consumers, T-253).
- `fg_pexec` (Parameter Execute): par change -> config; Active / Reset -> fresh state. State lives in `fg_logic`
  module memory (no functions in storage).

## Use it from any COMP
1. Un-park it (`allowCooking = True`; in main it is parked like every lab COMP) and turn `Active` on.
2. Bind a multiplier: `op('/project1/lab/FG_fps_governor/out1')['quality']` (1.0 = full -> Floor). Give the consumer
   its own on/off (e.g. `Followgov`) so the user can ignore it.
3. Never write the governor's or anybody's pars from the consumer's side either: read, map, apply to your own
   effective values only.

## PX hook recipe (for the PX lane; PX files not touched here)
Ordered thresholds on `quality`, cheapest visible loss first, on the same rungs as PX's own ladder
(`px_logic.aq_steps`: splat MSAA 1x -> `AQ_COUNTS` 0.75 / 0.5 -> `AQ_RES` 0.75 / 0.5):

| quality below | PX does |
|---|---|
| 0.9 | splat AA -> 1x |
| 0.8 | count fraction 0.75 |
| 0.65 | count fraction 0.5 |
| 0.5 | resolution fraction 0.75 |
| 0.35 | resolution fraction 0.5 |

With Steps 5 / Floor 0.25 the qualities 1 / .85 / .7 / .55 / .4 / .25 land on one rung each.
`fps_gov_logic.px_plan(q)` returns the same `(force_aa1, countf, resf)` tuple as `px_logic.aq_effect`, so a PX
Autoquality option "governor" can be a few lines where PX now runs its own `aq_step`:

```python
g = op('/project1/lab/FG_fps_governor/out1')
q = g['quality'][0] if g is not None and g.parent().par.Active.eval() else 1.0
aa1, countf, resf = (q < 0.9, 1.0 if q >= 0.8 else (0.75 if q >= 0.65 else 0.5),
                     1.0 if q >= 0.5 else (0.75 if q >= 0.35 else 0.5))   # = fps_gov_logic.px_plan(q)
# then the existing phase C path: aq_raw(raw, countf, resf) + the MSAA override, user pars untouched
```
Resolution rungs reallocate textures (a hitch), which is why they are last and stepped, never continuous.

## Verified live (b2, 31550, 28 Oct; main + b3 also running)
Load = a 1920x1080 GLSL TOP (`/project1/lab/_fg_load`, b2 only, parked, not brought home) pulled every frame, plus a
Constant CHOP bound to `out1['quality']`. Defaults (Target 60, Downafter 30, Upafter 300, Steps 5, Floor 0.25):
- Idle: 60.0 fps, headroom ~10.5 ms, step 0.
- Load on at 6.12 s (smoothed 47-49 fps, headroom -2.4 ms): steps 1..5 at 7.73 / 8.34 / 9.00 / 9.66 / 10.39 s ->
  quality 0.85 / 0.70 / 0.55 / 0.40 / 0.25.
- Load off at 14.26 s (60 fps, headroom ~11 ms): steps back at 20.01 / 25.06 / 30.09 / 35.14 / 40.44 s (one per
  ~5 s = Upafter) -> quality 1.0.
- **Cost:** 0.032-0.040 ms per frame in-frame while Active (Python + the Perform CHOP cook every 4th frame,
  perform1 cpuCookTime 0.022 ms when it cooks). Active off: 0 cooks (perform1 totalCooks unchanged over 3 s).
- The bound consumer cooked ~2x / s (the 30-frame fps / headroom refresh), not every frame.
- Brought home with `tools/bring_home.mjs` (242 ops equal, 0 errors), parked, Active off, main saved
  `JazibTD_home.1324.toe`.

## Not done
- No PX binding (PX lane). The panel shows no read-only state (zkit has no state knobs): read out1 or the COMP viewer.
