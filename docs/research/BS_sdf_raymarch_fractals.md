# BS - SDF raymarching + fractals: who made it already, what GEN_sdf takes (26 Oct 2026)

Research-first note for `GEN_sdf` (FX0 rows 41 + 67, FX5 G13 + G14). Sources read or recalled; the build is our own
code in `builders/gen_sdf*.py` (doc `docs/builds/gen_sdf.md`). Licences do not limit study (user rule); IQ's article
snippets are MIT by his own statement (`L_shader_sources_licences.md`), his shader art is not copied.

## Existing work
| Source | What it is | Use for GEN_sdf |
|---|---|---|
| RayTK (t3kt / Tommy Etkin), [releases](https://github.com/t3kt/raytk/releases), [Derivative asset](https://derivative.ca/community-post/asset/raytk-raymarching-masses/63620) | Node library that assembles raymarch shaders from COMPs (CC BY 4.0); shadows, volumetric, reflect ops; Mac support unverified (P_realtime_3d_looks P4) | Proof the "operators + scene + one render shader" split works in TD; we keep ONE fixed shader per module (no runtime assembler, no recompiles on scene change) because 31550/MoltenVK compiles are slow and a menu switch must not hitch |
| hrtlacek `TDraymarchToolkit` ([GitHub](https://github.com/hrtlacek/TDraymarchToolkit)) | TD 2019 node toolkit on Mercury hg_sdf + IQ formulas, one light | Same idea, older; hg_sdf is CC BY-NC (not ported) |
| Derivative "Raymarching in TouchDesigner" series ([post](https://derivative.ca/community-post/tutorial/raymarching-touchdesigner-tutorial-series/62745)), Ragan "SDFs 101" | ~5 h tutorial: SDF construction, lighting, fractal / kaleidoscopic folds in a GLSL TOP | Confirms the single GLSL TOP route |
| Derivative "GLSL shaders, generative visuals, TouchDesigner + Claude Code" ([post](https://derivative.ca/community-post/tutorial/glsl-shaders-generative-visuals-touchdesigner-claude-code/74828)) | Mandelbulb + raymarcher in a GLSL TOP | Same maths; nothing to copy |
| IQ articles ([index](https://iquilezles.org/articles/)): distance functions, smooth minimum, Menger fractal, normals for an SDF (tetrahedron 4-tap), soft shadows (`res = min(res, k h / t)`), ambient occlusion (5 taps `h = 0.01 + 0.12 i / 4`), quaternion Julia DE `0.25 |z| ln|z| / |z'|`, Apollonian (sphere inversion fold) | The primitives and lighting core of the shared ray code are these textbook forms, written fresh |
| Mandelbulb (White + Nylander 2009, [Wikipedia](https://en.wikipedia.org/wiki/Mandelbulb)); DE `0.5 ln r r / dr` (running derivative) | Power-n triplex map | `fractal` type 0; Juliamix morphs c from p to a constant (Mandel -> Julia) |
| Mandelbox (Tom Lowe 2010): box fold, sphere fold (min / fixed radius), scale; DE `|z| / |dr|` | | `fractal` type 1 |
| Knighty KIFS (fractalforums): abs fold + sort + rotate + scale-offset (Menger-type) | | `fractal` type 3 |
| Perturbation deep zoom: reference orbit at high precision + per-pixel low-precision deltas ([mrob muency](https://mrob.com/pub/muency/perturbationmethods.html), [Ultra Fractal](https://www.ultrafractal.com/help/formulas/perturbationcalculations.html), Kalles Fraktaler, [rust-fractal-core](https://github.com/rust-fractal/rust-fractal-core)); rebasing (Zhuoran, fractalforums.org 2021: when `|Z_m + dz| < |dz|` or the reference ends, `dz = z - Z0`, restart the reference) replaces Pauldelbrot glitch detection | | `fractal2d` Precision perturb: Python float64 (or Decimal with Deepx/Deepy digits) reference orbit in a Script TOP, float32 deltas in the shader |
| Two-float (double-float) arithmetic (FX5 G14 idea) | Emulated doubles per pixel | Not used: per-iteration cost x10-20 and Metal fast-math may reassociate the error terms; perturbation is cheaper and deeper. The reference itself is stored as hi + lo float32 pairs (only used where z is small) |

## Decisions (adapted, not copied)
- One compute pass per module renders at `Quality` x output res into rgba32float (premultiplied rgb + alpha), then a
  shared composite pass upscales and blends over the slot input. Every loop has a compile-time cap (T-124): march
  512, shadow 64, AO 8, fractal 32, 2D 8192; the user's pars choose how much of the cap is used.
- Hit threshold is in pixels (`Epsilon` x pixel angle x t), so Quality / resolution changes keep the same look.
- Scenes are a menu inside one shader (no recompiles); morph = `mix(dA, dB, m)` with only the needed side evaluated.
- Offline numpy mirror (float32) of every line = the reference for live parity at sample texels (`View` data: t, hit,
  steps, k / mu, escaped, trap, edge px).
- Deep-zoom limits measured offline: at 1e10 on the seahorse point (counts 1000-1500, chaotic), float32 perturbation
  matches exact Decimal iteration (smooth mu within 0.05) on 85 % of pixels, float64 deltas on 93 %; the misses are
  chaos, not glitches. Decimal reference recompute costs CPU only when centre / iterations / Julia c change.
