# fx_analog_signalloss: FX_analog module `signalloss` (offline prep, 26 Oct 2026, target TD 2025.31550)

Lost-signal looks for `/project1/lab/FX_analog` (rack = `builders/fx_analog.py`, the FX_glitch rack; template:
`docs/builds/fx_glitch.md`). Research: FX0 row 51 (DG-11 / DG-24), FX2 AV-07 (power-off collapse, V/H hold), AV-13
(weak sync, snow), AV-14 (interlace). No StageLab twin (JZB_Lofi_CRT's Roll / power ideas are the nearest; the CRT lane
covers those for the `crt` / `crtfault` modules). **Nothing here has run in TD yet: every behaviour below is a LIVE
CHECK.** Offline: `python3 -I -m unittest discover -s test -p 'test_fx_analog_vhs.py'` (shared with `vhs`).

Files: `builders/fx_analog_signalloss.py` (pars, presets, the shader, `build`), `builders/fx_analog_signal_logic.py`
(`power_state`, `collapse`, `warmup`, `collapse_lit`, `vroll_line`, `slant_src`, `ref_sl_vhold`, `ref_sl_slant`, GLSL
lib, `stamp`, Pulse exec).

## Build (td_exec, ~2 min)
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_analog.py').read(), ns)
ns['build']('/project1/lab')                          # rack if FX_analog does not exist yet; idempotent
ns['add']('/project1/lab/FX_analog', 'signalloss')     # -> signalloss1, wired last, zkit panel + 7 presets
```
Lane rules as in `fx_analog_vhs.md` (lane.py, allowCooking, checkpoints, td_layout, td_errors).

## Network (inside `signalloss1`)
`in1` (+ `cprev` Cache TOP -> `prev_src` Switch: weave / blend only) + `stamp` (cook clock, T-111) + `osd` Text TOP /
`osd_blank` 1x1 -> `osd_src` Switch (text only while Osd on and No signal > 0) -> `fx` (ONE compute pass, input size,
`useinput`) -> `out_sel` (0 = in1, 1 = fx) -> `out1`. `pulses`: Hit -> `Hittime`, Power off -> `Offtime`, Power on ->
`Ontime` (absTime.seconds). `out_sel` = 1 while Amount > 0, a Hit burst runs (< Hitdecay x 4.605 s), a power
transition / the off state is on, or Manual phase >= 0; else in1 straight out (nothing cooks).

Shader order per pixel (tape coordinates, Line axis): power state -> collapse / warm-up geometry (outside = black) ->
V-hold (offset + roll + jumps, blanking bar at 0.02) -> H sync (H-hold drift wraps the line, torn segments re-picked
at Rate, line jitter) -> sample (+ interlace) -> no-signal card + OSD -> snow -> collapse whiteness x gain.

## Pars
| Page | Par | What |
|---|---|---|
| Sync | Amount | 0 = exact passthrough; scales every continuous effect (events fire at any Amount) |
| Sync | Htear, Tearsize | chance a band of the frame (12 bands, re-picked at Rate) tears sideways, by up to Tearsize px |
| Sync | Hslant | H-hold drift: line l shifts Hslant x l px and wraps (diagonal bars, the classic lost horizontal hold) |
| Sync | Hjitter | per-line random shift, px, re-picked at Rate |
| Sync | Vroll, Vpos, Vbar, Vjump | V-hold: picture rolls Vroll frames/s, sits Vpos frames up, blanking bar Vbar tall; random jumps |
| Sync | Rate, Seed | tick rate of tears / jitter / jumps; pattern |
| Sync | Hit (pulse), Hitdecay | burst: + tears, + snow (half), + a 0.1-frame jump, decaying exp(-t / Hitdecay) |
| Nosignal | Nosignal, Card, Snow, Osd | card mix (blue / snow / black / 75 % bars), snow over the picture, OSD text on the card |
| Interlace | Interlace, Fieldpitch, Combshift | weave (one field from the previous frame: combing on motion) / bob (single field, line-doubled: twitter) / blend; field row height px; old-field shift px |
| Power | Poweroff, Poweron (pulses), Powerdur, Warmup, Offhold, Powerphase, Glow | CRT collapse (0-0.5 squeeze to a 4 px line, 0.5-0.8 to an 8 px dot, 0.8-1 fade; whiteness + Glow gain), warm-up (55 % -> 100 %, gain q^2), hold black until Power on; Manual phase -1 = pulses, 0..1 = hold that collapse phase, 1 = off |
| Setup | Lineaxis, Cardr/g/b, Osdtext | TV orientation; blue card colour (default 0.05, 0.12, 0.85); OSD text |
| State | Hittime, Offtime, Ontime | written by the pulses |

Presets (zkit): 1 v-hold, 2 h-hold, 3 weak sync, 4 no signal (blue + OSD), 5 dead air (snow card), 6 interlaced
(weave, comb shift 6), 7 bars.

## LIVE CHECKS (expected numbers from `fx_analog_signal_logic`; ~15 min)
Setup as `fx_analog_vhs.md` (Input = test, clip paused, other slots enabled 0; read >= 3 frames after a change in a
separate exec). `I` / `O` = numpyArray of `signalloss1/in1` / `out1` (TD order, row 0 = bottom), 1080x1920.

| # | Check | Expected |
|---|---|---|
| S1 | Build: `td_errors` on signalloss1; `osd.comment` lists Text TOP pars missing on 31550 | no errors; missing list empty (else fix the names: alignx / aligny / fontsizex / bgalpha) |
| S2 | Amount 0: out_sel index, max abs O - I | 0, 0.0. Amount 1 with every effect at its default (all 0, Vbar 0.08, Interlace off, Powerphase -1): out_sel 1, max abs O - I = 0.0 (the full pass is an exact copy) |
| S3 | Hslant 0.25 (rest default, Amount 1): `R = lg['ref_sl_slant'](I, 0.25)` | max abs O - R = 0.0; Lineaxis y with `axis=1`: 0.0 |
| S4 | Vpos 0.25, Vbar 0.1: `R = lg['ref_sl_vhold'](I, 0.25, 0.1)` | rows 1440-1631 = 5/255 (bar 0.02), 192 rows; max abs O - R <= 1/255 |
| S5 | Nosignal 1, Card blue, Osd off | every px (13, 31, 217) +-1 (0.05, 0.12, 0.85); Card bars: 7 columns of 191 / 0 levels, boundaries at x = 1080 k / 7 (+-1 px); Osd on: white px only in the middle rows (text), count > 0 |
| S6 | Powerphase 0.25 / 0.65 / 0.9 / 1.0 (Glow 1.5) | lit rows 962 (+-1), all other rows 0; 4 rows x 544 columns; 4 x 8 px block (gain 0.75); all 0 |
| S7 | Power off pulse (Offhold on, Amount 0): read at 0.6 s; Power on pulse: read at 1.4 s | all 0 and out_sel 1; then out_sel 0 and max abs O - I = 0 |
| S8 | Hit pulse at Amount 0 (Hitdecay 0.6): read at 0.2 s and at 3.0 s | O != I (tears / snow) and out_sel 1; then out_sel 0, diff 0 |
| S9 | Interlace bob, Fieldpitch 2, clip paused | for one parity class c of row pairs (y // 2) & 1: O[y] = I[y]; for the other: O[y] = I[pair(y)] with pair(y) = (((y // 2) ^ 1) * 2 + y % 2): max diff 0 |
| S10 | Interlace weave, Combshift 0, clip PLAYING | one parity class of row pairs = I exactly (max diff 0); the other differs where the picture moves; clip paused: whole frame = I |
| S11 | Presets: zkit Recall 1-7 | pars exactly as `PRESETS` (menus by index) |
| S12 | Cost: pane elsewhere, 120 frames, preset 3 (weak sync) and preset 4 (Osd) | fx GPU <= 0.6 ms median; `osd` cooks <= 1 time in 60 frames (if it re-cooks every frame because of the in1-size expressions, set its size once instead); project 60 fps |

Assumed from other live work: compute `texture()` on an input (chroma module), Cache TOP previous cook (mosh),
Parameter Execute `onPulse`. Any failure: fix the builder + LEARNINGS (T-nn) + rerun the offline tests.

## Verified live (26 Oct, 31550; scratch TD with other lanes, then brought home to main)
- S1: `td_errors` clean; `fx` is a GLSL Multi TOP (4 inputs, rack fix from vhs); osd comment "Missing pars: none".
- S2: Amount 0 -> out_sel 0, diff 0; Amount 1 at defaults -> out_sel 1, diff 0 (exact copy).
- S3: Hslant 0.25 vs `ref_sl_slant`: max 0.0 (Lineaxis x and y). S4: Vpos 0.25 / Vbar 0.1 vs `ref_sl_vhold`: max
  0.0004 (0.1 level); bar rows 1440-1631 (192) at 5/255.
- S5: blue card every px (13, 31, 217). S6 (Glow 1.5): phase 0.25 -> 962 lit rows (479-1440); 0.65 -> 4 rows x 544
  cols; 0.9 -> 4 x 8 block, max 0.73; 1.0 -> all 0.
- S8: Hit at Amount 0 -> out_sel 1, diff 0.81; 3 s later out_sel 0, diff 0. S11: Recall 1-7 exact (twice).
- S12 cost (clip playing, 120 frames): weak sync 1.11 ms median (fx 0.36, stamp 0.19), no signal + OSD 1.09 ms; `osd`
  cooked once in total (not per frame).
- Not run: S7 (power pulses with timing), S9 / S10 (interlace row classes).
- Main TD: in FX_analog (slot signalloss1 enabled 0, preset weak sync), errors clean, restaged, parked, saved
  (JazibTD_home.290). Capture: `output/project1_lab_FX_analog_out1_2026-10-26T15-12-48-319Z.png` (no signal + OSD).

## Not done / open
- Hum bars, degauss, raster breathing, arcing: CRT-family items the `crtfault` lane covers (AV-07); not duplicated.
- Interlace stale history: after a bypass gap > 0.25 s the weave / blend fields use the current frame (stamp), not a
  frame from before the gap.
- The OSD font is the Text TOP default (a VCR / pixel OFL font is AV-16's job).
