# fx_trans: FX_trans, the G-TRANS transition bank, 53 transition types (27 at first live) (live in main, 26 Oct 2026, TD 2025.31550)

`/project1/lab/FX_trans`: transitions from picture A to picture B for live shows. Research: `docs/research/FX0_effects_backlog.md`
row 69 (and rows 3 / 15: mosh cut, CRT power-off), `docs/research/FX4_software_fx_emulation.md` 1.8 (Arena transition
mixers, gl-transitions gap), the Notch / Universe transition lists there.
**Status: LIVE on b5 (31550, 26 Oct 2026), brought home into main (JazibTD_home.442.toe, 412 ops, 0 errors, parked).**
All LIVE CHECKS T1-T13 ran; see "Verified live" below. `python3 -I -m unittest discover -s test -p 'test_fx_trans.py'`
passes 34 tests (~6 s): source parse, wrapper, perf patches apply, progress / tempo / easing maths, the per-cook `chan`
cache, knob relabel, numpy references (wipe, circle, matte, fadecolor), the TV-off port checked against
`fx_analog_crt_logic.power_shape`, a dry build on a fake TD (with the moshcut sub-COMP), and a glslc compile of the
whole bank shader and of each of the 27 one-type shaders.

## Files
| File | What |
|---|---|
| `builders/fx_trans.py` | Builder: `build(parent='/project1/lab', panel=True)` (idempotent). Pages, presets, the Parameter Execute text |
| `builders/fx_trans_logic.py` | Pure logic (the COMP's `fx_trans_logic` DAT is the same text): bank, parser, wrapper, shader generator, progress / tempo / easing, runtime hooks (`values`, `on_go`, `on_cut`, `apply_type`), numpy references |
| `builders/glsl/fx_trans/*.glsl` | The 25 gl-transitions, unchanged (MIT). `SOURCES.md` there: commit, author and licence per file |
| `test/test_fx_trans.py` | Offline tests |

## Transitions (Type menu, 28)
gl-transitions (25, MIT, authors in `builders/glsl/fx_trans/SOURCES.md`): `fade`, `fadecolor`, `wipe` (DirectionalWipe), `circleopen`,
`clock`, `crosswarp`, `crosszoom`, `cube`, `swirl`, `pixelize`, `morph`, `glitchmem` (GlitchMemories), `burn`
(BurnThrough), `filmburn`, `ripple`, `dreamy`, `doorway`, `kaleido`, `doommelt`, `slices` (WindowSlices), `polka`
(PolkaDotsCurtain), `hexagon`, `displace` (DisplacementMap: the map is the matte input), `glitchdisplace`, `stripmosh`
(StripDatamoshGlitch).
Ours (3):
* `matte`: a luma-matte wipe from any TOP (in3, or the Mattetop path, or a built-in ramp / radial ramp / noise). A
  pixel turns to B when the progress passes its matte value. Knobs: softness, invert, channel (luma / r / g / b / a),
  gamma.
* `tvoff`: A powers off like a CRT, there is a black gap, then B powers on. The maths is a port of
  `fx_analog_crt_logic.power_shape` (FX_analog crtfault's Power): off squeezes the picture to a bright line, then to a
  dot that fades; on is dim and small, then grows to full. The port is tested equal to the original at 121 points.
  Knobs: gap, dot size, glow (gain cap on the line), line height.
* `mosh`: the datamosh cut, which is FX_glitch's `moshcut` module (`fx_glitch_moshcut.py` + the `fx_glitch_mosh.py`
  engine). It is built unchanged inside the sub-COMP `mosh` by FX_glitch's own `_pars` / `H` helpers. Nothing is
  copied, so a fix in those files reaches FX_trans on the next build. Knobs K1..K8 drive its Melt, Order, Cutmode, Gain, Residual,
  Decay, Bloomgain and Seed; its Progress follows FX_trans.

* `beatripple` (TC-33, clean-room from blues-Qing's "Image Transition" description; lane C, 27 Oct): K1 drops are
  born on evenly spaced beats of the run (drop k at progress k / drops; Drive beats with Beats = drops = one drop per
  beat; preset 9 quantizes the start to the beat) at hashed spots (K6 seed). Each ring grows (radius f^grow x the
  spot's farthest corner) so the union of the discs is all B at progress 1; B shows inside a disc (K5 soft edge);
  damped sine waves at each ring front (K2 amp, K3 waves per frame height, K4 gaussian width, K7 damp, fading to 0 by
  the end) bend both pictures. Knobs: drops, amp, waves, width, soft, seed, damp, grow. Loop capped at 16 drops.
  Mirror `fx_trans_logic.ref_beatripple` (mask + uv offset). New types are appended to the Type menu (zkit presets
  store the menu index). Existing COMPs: `fx_trans.upgrade()` (logic + sources DATs, Type menu, shader text, missing
  preset slots; no mosh / panel rebuild).

**Wave 2 types (lane C, 27 Oct; FX7a SX-31 + SX-34), 14 more gl-transitions (MIT, same commit, `GL_MORE`, appended
after `beatripple` so preset indices never move; 43 types):** `lummelt` (LuminanceMelt), `burnout`
(UndulatingBurnOut), `glowdissolve`, `perlindissolve`, `noisedissolve`, `overexposure`, `edgeglow`, `linearblur`,
`dirwarp` (DirectionalWarp), `tanblur` (TangentMotionBlur), `squeeze`, `flyeye`, `shatter`, `crazyfun`
(CrazyParametricFun). Same `wrap_gl()` route, no source edits; glslc compiles each alone and the whole bank.
LIVE CHECKS T19: `upgrade()` -> 43 types, bank compiles (record the first-compile freeze: the bank is ~1.5x
longer), each new type at Progress 0.5 on the test clips: no errors, out differs from A and B (mean diff > 0.02),
ends exact (T2); cost per type at raw 0.5.

**Wave 2 verified live (scratch, 2025.31550, 27 Oct, load average ~90):** `upgrade()` -> 43 types, bank shader
60.3k chars; **first compile of the bank froze scratch 3.37 s** (was ~0.5 s for 27 types; T-154 rule: compile once at
build / bring-home, in a quiet minute). All 14 at Progress 0.5 on paused test clips: out_sel 2, 0 errors, finite, mean
diff vs A / vs B: lummelt 0.18 / 0.18, burnout 0.23 / 0.14, glowdissolve 0.02 / 0.36 (still mostly A at 0.5),
perlindissolve 0.23 / 0.13, noisedissolve 0.18 / 0.18, overexposure 0.29 / 0.16, edgeglow 0.22 / 0.36, linearblur
0.17 / 0.20, dirwarp 0.19 / 0.18, tanblur 0.27 / 0.34, squeeze 0.23 / 0.18, flyeye 0.18 / 0.20, shatter 0.35 / 0.02
(mostly B at 0.5), crazyfun 0.20 / 0.28. GPU ms (one cook each, noisy): lummelt 0.62, burnout 0.94, glowdissolve 0.64,
perlindissolve 0.24, noisedissolve 0.24, overexposure 0.80, edgeglow 1.13, **linearblur 3.68** (6 x 6 taps x 2, over
the aim while it runs), dirwarp 0.54, **tanblur 1.49**, squeeze 0.33, flyeye 0.40, shatter 0.67, crazyfun 0.24.

**Wave 3 types (lane C2, 27 Oct; FX7a SX-32 / SX-33 / SX-35, FX7c 7C-06 / 7C-29), appended after `crazyfun` (53
types; earlier menu indices unchanged):** 9 more gl-transitions (same commit, `GL_W3`): `tvstatic` (TvStatic) and
`colorphase` (ColorPhase) = the two picked from the signal-failure family (GlitchBands / GlitchFlicker overlap
`stripmosh`, StaticFade / StaticWipe overlap `tvstatic`); `bookflip` (BookFlip), `pagecurl` (InvertedPageCurl, **BSD
3-Clause**, notice kept in the file and the `fx_trans_src` DAT) and `rolls` (Rolls) = page / flip / 3D (7C-06's page
flip as a transition; the Keijiro StrobePages strobe of captured frames is not built); `heart` (HeartWipe), `pinwheel`
(Pinwheel), `lissajous` (LissajousTiles, Scanimate tiles; its two nested count-down loops run over a const 10 x 10
grid, early exit) and `gridflip` (GridFlip) = shape / tile wipes (a logo-shaped wipe = `matte` with the logo TOP as
matte). Plus ours: **`jigsaw`** (7C-29, clean-room from the Notch Jigsaw manual text): K1 cols x K2 rows of
interlocking pieces, one round knob (K3 size) per inner edge whose side is a hash of the edge (both neighbours agree,
no loops), each piece flips around its vertical centre line (A front, B back) at its own time = diagonal sweep mixed
with a hash (K4 random), spread over the run (K5), K6 seed, K7 edge-on shade, K8 border width (cell units), K9 gap
grey. Mirror `fx_trans_logic.ref_jigsaw` / `jg_piece`. Presets 10 page flip 2 beats, 11 jigsaw 1 bar, 12 static cut
(0.5 s).

**Wave 3 LIVE CHECKS (b4, then main by builder):**
| # | Check | Expected |
|---|---|---|
| T20 | `build()` fresh on b4 (or `upgrade()`), errors | 0 errors; 53 types ending `... crazyfun tvstatic colorphase bookflip pagecurl rolls heart pinwheel lissajous gridflip jigsaw`; bank compiles once (record the freeze); presets 10-12 added, 1-9 unchanged |
| T21 | each new type at Progress 0.5 (Ease linear), test clips | no errors, finite, out differs from A and from B (mean diff > 0.02) |
| T22 | jigsaw mask: red / blue, K defaults, Progress 0.3 / 0.5 / 0.8, linear | per pixel = `ref_jigsaw` which (A red, B blue, gap grey 0) agreement >= 0.995 |
| T23 | cost per new type at raw 0.5 (bank) | GPU ms; anything > 3 ms noted |

**Wave 3 verified live (b4, 2025.31550, 27 Oct; FX_trans built fresh on b4 from `build()`; load average ~25):**
| # | Result |
|---|---|
| T20 | build: 412 ops, 0 errors, 53 types ending `... crazyfun tvstatic colorphase bookflip pagecurl rolls heart pinwheel lissajous gridflip jigsaw`, 13 preset rows (1-12), build exec 3.7 s incl. the bank compile |
| T21 | each new type at 0.5 (linear, paused test clips): out_sel 2, 0 errors, finite; mean diff vs A / vs B: tvstatic 0.32 / 0.46, colorphase 0.23 / 0.25, bookflip 0.25 / 0.23, pagecurl 0.45 / 0.17, rolls 0.40 / 0.14, heart 0.35 / 0.13, pinwheel 0.32 / 0.16, lissajous 0.34 / 0.49, gridflip 0.40 / 0.26, jigsaw 0.26 / 0.32 |
| T22 | jigsaw on red / blue (Constant TOPs wired, K defaults, linear), full frame every 2nd pixel vs `ref_jigsaw`: agreement **1.0** at 0.3 / 0.5 / 0.8 (B share 0.016 / 0.382 / 0.980, gap 0.146 / 0.253 / 0.020, live = ref) |
| T23 | `trans` GPU median ms (perf_pull 120 pulled frames, raw 0.5, playing test clips, bank): fade 0.23, tvstatic 0.27, colorphase 0.26, bookflip 0.21, pagecurl 0.26, rolls 0.22, heart 0.41, pinwheel 0.37, **lissajous 3.40** (p90 4.5: the source's 10 x 10 tile search per pixel; over the aim only while it runs, like crosszoom / filmburn), gridflip 0.32, jigsaw 0.89; pull fps 56-60 |

Capture `output/fx_trans_jigsaw_045.png` (test clips, 0.45: pieces mid-flip, the knob holes are neighbours' knobs
turning edge-on). **In main (lane C2, 27 Oct, by builder):** quiet main; `lane.py add`; un-park; `upgrade('/project1/lab')`
(5.98 s exec incl. the 79.5k-char bank compile) -> 53 types, presets 10-12 added; jigsaw at 0.5 compiled and cooked
(out_sel 2, 0 errors); rest state fade / 0 / smooth; parked; **main saved `JazibTD_home.706.toe`**.

Why this set: the Arena mixer list (push, wipe ellipse, zoom, rotate, tile, twitch, shift RGB) and the Notch / Universe
names (cube, swirl, glitch, burn, shape wipe, VHS, warp, film burn) are covered. It picks one or two from each family
(fade, wipe, iris, 3D, warp, blur-zoom, pixel / hex, glitch, burn, melt, kaleido, doors), leaves out near-duplicates
(13 directional / split / slide variants) and leaves out transitions that need extra textures we cannot feed live.
Adding one = copy the file into `builders/glsl/fx_trans/`, add `(id, stem)` to `GL`, a SOURCES row, rebuild (no other change).

## Mixer or standalone: standalone `FX_trans` (decision)
* **The smaller change is no change to `td_layer_mixer`.** The mixer already takes a COMP as a source (it uses the
  COMP's Out TOP) and has a master `fx_slot`. So FX_trans plugs in as it is: put it in the source bank (A / B from any
  TOPs, e.g. two clip decks), or put it inside `fx_slot`.
* td_layer_mixer is a typed MCP command in `td/handlers.py` (another lane's file, plus `src/server.js`,
  `docs/PROTOCOL.md` and offline tests). A transition engine inside it would change the protocol and the
  handler for one feature, and its per-layer Cross TOP model (opacity crossfade) is not an A -> B model.
* Transitions need their own state: a run clock, beat quantize, swap, a sub-COMP for mosh. A COMP with its own panel
  and presets keeps that state out of the mixer. The same COMP also serves the cue list, the timeline, or a plain A/B
  deck pair.
* **Optional mixer proposal (not done; for the td_layer_mixer owner):** add a per-layer `L<n>trans` menu (none / a
  path to an FX_trans). When the layer's Source changes, the old and new source TOPs are wired into that FX_trans's in1
  / in2, then its `Go` is pulsed and the layer shows FX_trans's out1 until the run ends. That is about 30 lines in
  `cmd_layer_mixer`, a `trans` column in the `sources` Table and one Parameter Execute. Build it only if the user
  wants per-layer transitions in the mixer. The standalone COMP covers the need today.

## Network (`FX_trans`)
| Stage | Ops |
|---|---|
| Logic | `fx_trans_logic` (module DAT = the logic file), `fx_trans_src` (JSON: the 25 sources, so a Type change needs no repo files), `pexec` (pulses Go / Back / Cut / Resetknobs; value change Type / Compile), `prog` (Constant CHOP: raw, p, swap, out, type; `chan()`: one logic call per cook, channels 1..4 reuse it) |
| 1 Inputs | `in1` (A), `in2` (B), `in3` (matte); `test_a` (webcam 5 s clip), `test_b` (testsrc2 clip, moving: mosh needs motion in B) -> `a_src` / `b_src` (auto = the in when wired) -> `a_fit` / `b_fit` (Resw x Resh, Fit); matte `m_ramp` (horizontal / radial), `m_noise`, `m_sel` (Mattetop), in3 -> `m_src` -> `m_fit` |
| 2 Transition | `trans` (compute GLSL TOP, rgba16float, 3 wired inputs A / B / matte, T-88; docked `trans_compute`); `mosh_a` / `mosh_b` (swap) -> `mosh` (moshcut sub-COMP, B = `mosh_b` via Btop) |
| 3 Out | `out_sel` (0 A exact at raw 0, 1 B exact at raw 1, 2 shader, 3 mosh: only the picked input cooks) -> `out1` |

Shader: `fx_trans_logic.shader_text(types)`. The prelude provides the gl-transitions API: `progress`, `ratio`,
`getFromColor` and `getToColor` (straight alpha; Outside hold or transparent). Each transition is wrapped. Its
top-level names and `#define`s get a `t<id>_` prefix. Its uniforms become globals filled by `t<id>_init()` from the
knobs (`uK0..uK2`). Its sampler becomes the matte input. `texture2D` becomes `texture`, and its macros are `#undef`'d
after it. `main()` switches on `uT.y` and writes premultiplied rgba. Every loop in the 25 sources is bounded by a
compile-time constant (tested).
**Compile** `bank` (default since the live run): all 27 types in one shader, compiled once (~0.5 s at build / load);
a Type change costs nothing. `selected`: the shader holds only the current type (0.05-0.15 ms cheaper per cook), but
the FIRST compile of each new type froze b5 for 0.5-0.75 s (filmburn 534 ms, burn 659, crosszoom 750, glitchmem 640;
cached afterwards, ~10 ms). Use `selected` only when the type is fixed for the show.
`main()` has no early return (out-of-range threads skip only the store), so a type may use `barrier()`.
**Perf patches** (`PATCHES` in the logic, applied to the wrapped text; vendored files unchanged): filmburn computes its
13 light-leak positions and 50 blur offsets once per 8x8 workgroup in shared memory, takes the blur tap radius per tap
(not per pixel: the original's 100 scattered taps per pixel cost 21-38 ms), and fetches A or B alone while the blend
weight is < 0.001 / > 0.999. Same look (capture compared), 5-6x cheaper.

## Parameters
| Page | Pars |
|---|---|
| Trans | **Type**, **Progress** (slider, 0 = A exact, 1 = B exact), **Drive** manual / seconds / beats, **Go** (runs toward the other side from where it is; from manual it switches Drive to seconds), **Back** (to A), **Cut** (instant), Duration (s), Beats, **Ease** linear / smooth / in / out / inout / expo / sine, Steps (0 = continuous; N = stepped progress), **Backstyle** rewind (the run back is the reverse play) / forward (B -> A plays forward with A and B swapped), **Quantize** off / next beat / next bar, **Randompool** (type ids or `all`: a random type, never the same twice, on each Go) |
| Knobs | **K1..K10**: on a Type change they take the type's parameter names as labels (e.g. `K1 persp`), its defaults and its slider ranges (`@range` where the source gives one); unused knobs are disabled. Keepknobs (keep values), Resetknobs. Slider ranges only, no clamps |
| Tempo | Bpm (used when no CHOP), Bpmchop (a CHOP path, e.g. AU_features), Bpmchan (`bpm`), Phasechan (a 0..1 beat phase channel; without it the beat grid is anchored at absTime 0) |
| Input | Asource / Bsource auto / test, Mattesource auto / ramp / radial / noise / top + Mattetop, Resw / Resh (1080 x 1920), Fit, Outside hold / transparent, Compile bank (default) / selected |
| State | Gofrom, Goto, Gotime, Godur, Goswap (written by Go / Back / Cut; read by `prog`) |

Presets (zkit, full states incl. all 10 knobs, T-124 (1)): 1 fade 2 s, 2 wipe 1 bar (beats 4, quantize bar, inout),
3 cube 2 beats (quantize beat), 4 glitch hit (stripmosh 0.6 s), 5 tv off (1.2 s), 6 datamosh cut (2 s), 7 film burn
(2.5 s, sine), 8 matte wipe (1.5 s).

## Build (live lane, ~20 min incl. checks)
On a build TD first (T-120), then bring it home:
```python
# td_exec target:'b4' (lane.py add FX_trans "<label>" first)
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_trans.py').read(), ns)
ns['build']('/project1/lab')
```
Then: `td_errors` (recurse), `td_layout` flow check, `td_checkpoint`, the LIVE CHECKS, `td_bring_home {comp:
'/project1/lab/FX_trans', from:'b4'}`, park, save. The build reads `fx_glitch.py` / `fx_glitch_moshcut.py` /
`fx_glitch_mosh.py` (not edited).

## LIVE CHECKS (expected numbers; 1080x1920, rgba16float)
Read pixels with `numpyArray()` (rows bottom-first). Use `in1` = Constant red (1, 0, 0, 1) and `in2` = Constant blue
(0, 0, 1, 1) for the colour checks, and the test clips for the looks. Set Progress in one exec and read in a later exec.

| # | Check | Expected |
|---|---|---|
| T1 | Build, `td_errors` recurse | 0 errors. `trans` compiles for the default type (fade) and after `Compile = bank` (the whole 27-type shader). If TD rejects a name, it is a TD reserved word / macro clash: fix it in `wrap_gl`, then glslc + rebuild |
| T2 | Ends: Progress 0 / 1 for 3 types (fade, cube, mosh) | `out_sel.par.index` 0 / 1; out1 vs `a_fit` / `b_fit` max diff 0.0; `trans` cook count does not rise while the slider stays at an end (no cook) |
| T3 | Knob relabel: Type wipe -> cube -> stripmosh | K1 label `K1 direction x` -> `K1 persp` -> `K1 strength`; K values = defaults (0.7, 0.3, 0.4, 3.0 for cube); K5..K10 disabled for cube. Record the frame time of the Type change (selected mode recompile): expect one frame of 10-60 ms. Confirm `par.label` / `par.enable` are writable on custom pars in 31550 (else fall back to a `knob_names` Text DAT readout, LEARNINGS) |
| T4 | Wipe numbers: Type wipe, K1 1, K2 0, K3 0 (direction +x, hard edge), Progress 0.5, red / blue | left half blue, right half red: column 270 = (0, 0, 1), column 810 = (1, 0, 0); blue fraction 0.50 +- 0.002 (`ref_mask('wipe', 0.5, knobs=[1, 0, 0])`) |
| T5 | Circle: Type circleopen, K1 0, K2 1, Progress 0.5 | centre pixel (540, 960) blue; corner (0, 0) red; the blue disc radius = 0.5 / sqrt 2 of the unit square (uv space, so an ellipse at 9:16) |
| T6 | Matte: Type matte, Mattesource ramp, K1 0, Progress 0.25 / 0.5 | blue fraction 0.25 / 0.50 +- 0.003 (left part first); K2 (invert) 1: right part first |
| T7 | FadeColor at 0.5 (K defaults: black, phase 0.4), red / blue | out = (1/27, 0, 1/27) +- 0.002 = `ref_fadecolor(0.5, red, blue)`, i.e. near black |
| T8 | TV off: Type tvoff, K defaults, Progress 0.05 / 0.2 / 0.3 / 0.5 / 0.95 / 1 (`ref_tvoff`) | 0.05: A squeezed to sy 0.90, gain 1.054 (rows beyond +-0.45 of the height black); 0.2: a bright line 0.4 % high, 53 % wide (gain 4); 0.3: only the centre dot, value 0.211 at the centre; 0.5: all black (0, 0, 0, 1); 0.95: B at sy 0.986 / sx 0.991, gain 0.966; 1: out_sel 1 = B exact |
| T9 | Go timing: Drive seconds, Duration 1, Go, read `prog` raw every frame | raw 0 -> 1 in 1.0 s +- 1 frame, ends with out_sel 1; Go again returns to 0 (out_sel 0). Backstyle forward: going back, `prog` swap 1 and p = 1 - raw |
| T10 | Beats: Drive beats, Beats 4, Bpm 120, Quantize bar | run 2.0 s, starts on the next 2 s boundary of absTime (or the Phasechan phase); with Bpmchop = an AU_features `bpm` channel the run length follows it |
| T11 | Mosh: Type mosh, test clips, Go 2 s | mid run looks moshed (out vs A and vs B both > 0.05 mean diff at raw 0.5); ends exact (T2). Its first cook after leaving raw 0 re-inits S = A (moshcut's gap rule). The sub-COMP's B is `mosh_b` (Btop resolves; else set Btop to the absolute path, LEARNINGS) |
| T12 | Randompool `wipe cube swirl`, Compile bank, Go x 6 | a different type each Go, never twice in a row; no recompile (cook time flat) |
| T13 | Cost (pane elsewhere, out1 pulled, raw held at 0.5) | per-type GPU ms, see below; report cook ms + project fps with other COMPs parked |

**beatripple LIVE CHECKS (lane C, scratch then main):**
| # | Check | Expected |
|---|---|---|
| T14 | `upgrade()`, errors | 0 errors; Type menu 29 names ending `tvoff mosh beatripple`; bank shader compiles (one compile); preset 9 added, slots 1-8 unchanged |
| T15 | Mask: Type beatripple, Ease linear, K defaults but K2 amp 0, red / blue, Progress 0.2 / 0.5 / 0.8 | blue fraction = `ref_mask('beatripple', p)` mean +- 0.003 (0.2: one disc around spot 0); per-pixel agreement >= 0.998 |
| T16 | Bend: A = B = a horizontal 32f ramp, amp 0.05, Progress 0.5 | out1 red = the ramp read at uv + `ref_beatripple` offset (max err <= 2e-3 away from ring edges) |
| T17 | Run: preset 9 (Drive beats, Beats 4, quantize beat, Bpm 120), Go | starts on a beat, 2.0 s, ends at out_sel 1 (B exact) |
| T18 | Cost at raw 0.5, 1080 x 1920, test clips, bank | GPU median (estimate 0.3-0.6 ms) |

**beatripple verified live (scratch TD, 2025.31550, 27 Oct; main's FX_trans loaded read-only, `upgrade()`):**
| # | Result |
|---|---|
| T14 | `upgrade()`: 29 types (`... tvoff mosh beatripple`), preset 9 added (slots 1-8 kept), bank shader 39.9k chars compiled, 0 errors; knobs relabel `K1 drops` ... `K8 grow`, K9 / K10 disabled |
| T15 | amp 0, red / blue, linear: blue fraction 0.0031 / 0.2425 / 0.9995 at 0.2 / 0.5 / 0.8 = ref 0.0031 / 0.2426 / 0.9995; per-pixel agreement 1.0, max diff 0.0005 (16f) |
| T16 | A = B = horizontal 32f ramp, amp 0.05, 0.5: out red = ramp at uv + ref offset, max err **4.9e-4** (offsets up to 43 px) |
| T17 | Drive beats, Beats 4, Bpm 120, quantize beat, Go at 2401.017 s -> start 2401.5 (next beat), Godur 2.0, ends raw 1 / out_sel 1 (B exact) |
| T18 | raw 0.5, test clips, bank: `trans` **0.43 ms GPU** + 0.16 CPU (fade 0.25 GPU in the same run); the testsrc2 clip decode (`test_b`, 5.6-6.3 ms GPU) dominates the COMP, not the transition |

**beatripple in main (lane C, 27 Oct, by builder):** `upgrade()` in main: 29 types, preset 9 added, 0 errors; Type
beatripple at Progress 0.5 compiled and cooked (out_sel 2, no errors/warnings), restored to the rest state (fade, 0);
parked, **main saved `JazibTD_home.572.toe`**.

**Wave 2 in main (lane C, 27 Oct, by builder):** `upgrade()` -> 43 types; bank pre-compiled in main with a forced
cook at lummelt 0.5 (**1.46 s** freeze, once per TD process), no errors; rest state restored (fade, 0); parked, **main
saved `JazibTD_home.590.toe`**. Library `FX_trans` 0.2.0.

## Verified live (b5, TD 2025.31550, 26 Oct 2026; 6 TDs on the Mac, other lab COMPs parked)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
Number checks used Ease **linear** (the default `smooth` eases the shader progress: at Progress 0.25 the matte read
0.156 = smooth(0.25), and tvoff ran on the smoothed time; both exact once linear).
| # | Result |
|---|---|
| T1 | 0 errors (td_errors recurse); `trans` compiled for fade and for the whole bank (36.9k chars) on 31550, no reserved-word clash; after the perf patch too (bank 37.7k) |
| T2 | fade and cube: Progress 0 -> out_sel 0, out1 = a_fit max diff 0.0; Progress 1 -> out_sel 1, = b_fit 0.0; `trans` totalCooks flat for 1 s at either end. mosh: run end out_sel 1, = b_fit 0.0 |
| T3 | `par.label`, `par.enable`, normMin / normMax and default are writable on custom pars at runtime: wipe `K1 direction x` (1.0), `K2 direction y` (-1.0), `K3 smoothness` (0.5); cube `K1 persp` 0.7, `K2 unzoom` 0.3, `K3 reflection` 0.4, `K4 floating` 3.0, K5..K10 disabled; stripmosh K1..K9 named, K10 disabled. Recompile cost: see Compile above |
| T4 | wipe (1, 0, 0) at 0.5: column 270 = (0, 0, 1), column 810 = (1, 0, 0), blue fraction 0.5000 |
| T5 | circleopen: centre blue, corner red; disc half-width 382 px (expect 381.8), half-height 679 (678.8) |
| T6 | matte ramp: 0.2482 / 0.5002 at 0.25 / 0.5 (left first); invert: 0.2470 / 0.4998 (right first) |
| T7 | fadecolor 0.5 = (0.03702, 0, 0.03702, 1) = 1/27, flat (std 5e-4) |
| T8 | tvoff 0.05: lit rows 96..1823 (sy 0.90); 0.2: line 8 rows x 572 cols (0.4 % x 53 %); 0.3: dot 0.2108 at the centre; 0.5: black; 0.95: B 1894 x 1070 px (sy 0.986, sx 0.991), value 0.965 (gain 0.966); 1.0: out_sel 1 |
| T9 | Duration 1: raw = (t - Gotime) / 1 within 3e-8 every sampled frame, reaches 1 exactly 60 frames (1.000 s) after Go, out 1; Go again goes back to 0. Backstyle forward: Goswap 1, swap 1 all run, p = 1 - raw (3e-8), ends at raw 0 / out 0 |
| T10 | Beats 4, Bpm 120, Quantize bar: Godur 2.0, Go at 7078.4 s started at 7080.0 (a 2 s boundary); Bpmchop = a CHOP `bpm` 90: Godur 2.667 |
| T11 | mosh (test clips) at raw 0.74: out vs A 0.347, vs B 0.123 mean diff (A vs B 0.441): moshed (capture); `mosh_b` resolves as Btop; ends exact |
| T12 | Randompool `wipe cube swirl`, bank, Go x 6: cube, wipe, cube, swirl, wipe, cube (never twice in a row); shader text unchanged, trans cookTime 0.17-1.6 ms |
| T13 | below; real cook rate with filmburn running at raw 0.5: `trans` 59.0 cooks/s (b5 with nothing running: 50-53, the Mac was at load average 47-65), project.cookRate 60 |

**Cost (T13), `trans` GPU median ms over 60 frames at raw 0.5, 1080x1920, test clips, bank / selected:**
fade 0.22 / 0.18, fadecolor 0.25 / 0.13, wipe 0.24 / 0.16, matte 0.35 / 0.15, circleopen 0.27 / 0.17, clock 0.31 / 0.17,
crosswarp 0.22 / 0.14, **crosszoom 3.1 / 2.8** (82 taps: the original algorithm, kept), cube 0.24 / 0.18, swirl 0.25 / 0.27,
pixelize 0.23 / 0.11, morph 0.37 / 0.27, glitchmem 0.41 / 0.27, burn 0.43 / 0.41, **filmburn 5.5 / 4.1** (was 21.8 at
selected before the patch; paired alternation old / new: 25.8 / 4.7, 32.2 / 6.7), ripple 0.31 / 0.14, dreamy 0.27 / 0.19,
doorway 0.16 / 0.12, kaleido 0.36 / 0.22, doommelt 0.21 / 0.15, slices 0.23 / 0.13, polka 0.23 / 0.10, hexagon 0.22 /
0.17, displace 0.36 / 0.16, glitchdisplace 0.36 / 0.25, stripmosh 0.68 / 0.64, tvoff 0.16 / 0.22. mosh sub-COMP GPU sum
1.8 ms. CPU: `trans` 0.17-0.24, `prog` 0.25-0.28 (was 0.43-0.62 with 5 logic calls per cook). b5 shares the GPU with
5 other TDs, so single numbers vary ~1.5x run to run (T-151 (3)). At the ends (raw 0 / 1) the shader does not cook.
filmburn and crosszoom are the two over the 3 ms aim while they run (2-3 s); everything else is under 0.7 ms.

## Estimated cost (offline guess, superseded by "Verified live")
At 1080x1920 the shader cooks only while 0 < raw < 1. At the ends out_sel passes A or B through for ~0.
Estimated GPU per cook: simple ones (fade, fadecolor, wipe, matte, circleopen, clock, crosswarp, morph, dreamy, ripple, swirl,
slices, polka, pixelize, hexagon, doommelt, displace, tvoff) 0.1-0.3 ms; cube / doorway / kaleido (7 iterations) /
glitchmem / glitchdisplace (9 taps) 0.2-0.5 ms; burn (fbm octaves) / stripmosh 0.4-0.8 ms; crosszoom (41 x 2 taps)
1-1.5 ms; **filmburn (50 x 2 taps + 13 noise rounds) 2-3 ms**: it is the one to watch at 60 fps. mosh = moshcut's
measured 2.13 ms median (FX_glitch doc), plus its b_test decode only with test clips. The prog CHOP adds ~0.05 ms CPU
(5 Python calls per frame), and the fits ~0.05 ms each when the source is not already 1080x1920.
