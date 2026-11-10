# strobe: FX_strobe strobe effector (26 Oct 2026, TD 2025.31550)

`/project1/lab/FX_strobe`. A self-contained TOP strobe: picture in, flashed picture out. Spec/recipe:
`docs/research/AX_strobber.md` (our own clean-room design; idea credit: Strobber by Skywalker.Visuals, no licence
stated; nothing of its files used). **No limits** (user rule): open ranges, no flash cap, no limiter; Hold = 0 means
every trigger flashes. The operator decides.

In: `in1` TOP (picture), `in2` CHOP (`low` `level` `kick` 0..1, e.g. `AC_audio/ctl_out`). Out: `out1` TOP only.
Test inputs inside: `test_noise` (1080x1920 noise) and `test_kick` (square 0..1 at Testrate Hz) + `test_wave`
(sine low/level at Testrate/4). `Input` menu: auto (in1/in2 when wired, else test) / live / test.

## Build
```python
ns = dict(globals()); exec(open('<repo>/builders/strobe.py').read(), ns); ns['build']('/project1/lab')
```
Idempotent, T-70 safe (closes its own controls_window, panel rebuilt in place by zkit, `_sd` = safe_destroy, never
moves the pane). Logic: `builders/strobe_logic.py` (copied into `strobe_logic`), 22 offline tests:
`python3 -I -m unittest discover -s test -p 'test_strobe.py'`.

## Parameters (custom pages; zkit panel shows all five, pulse `Opencontrols`)
| Page | Pars |
|---|---|
| Trigger | Source (kick / low / level / bpm / lfo / manual), Threshold (re-arm below Threshold-0.15), Division (every 1/2/4/8/16th trigger), Hold gap s (automatic hits only), Rate (LFO Hz) |
| Tempo | Tempo (project = TD timeline tempo, manual, link = `Linkchop` CHOP's `tempo` channel else project, tap), Bpm, Tap (last 4 taps -> Bpm, resyncs), Note (4 bars .. 1/32), Feel (straight / triplet / dotted), Phase, Swing (odd hits delayed), Resync |
| Manual | Fire (pulse), Flash (momentary hold), Burst (Burstcount hits at Note spacing, 1/Rate in LFO mode), Burstcount, Key (Keyboard In key, default space, only while the controls panel has focus) |
| Look | Mode (Lift add / Dip to black / Invert difference / Colour replace), Attack s, Release s, Ease (linear / in / out / in-out), Depth, Mix, Colour, Blackout |
| Input | Input (auto / live / test), Testrate, Linkchop |
Manual hits (Fire, Key, Burst) work in every Source mode and ignore Hold. MIDI: map any par with `td_midi_learn`.

## Network (stages)
Controls (zkit `controls` + `controls_window`, `strobe_pulses` Parameter Execute: Fire/Burst/Resync/Tap ->
engine) | 1 Picture in (`in1`, `test_noise` -> `img_src`) | 2 Control in (`in2`, test LFOs -> `ctl_src`; `key_in`)
| 3 Engine (`engine` Script CHOP once per frame running `strobe_logic.step`, `tap_times`, `env` = env lin hit count
beat bpm armed hits value blackout) | 4 Image (`strobe` single-pass GLSL TOP, shader in its docked `strobe_pixel`,
uniforms uFx = env, mode, mix, blackout + uColour; -> `out1`).

## Verified live (26 Oct, 31550; numbers from a per-frame recorder on `env`, since removed)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
- kick, test 2 Hz, Division 1: 10 hits in 5 s, gaps 0.500 s; Division 4: 10 triggers -> 3 hits, gaps 2.0 s.
- Hold 0.5 s with triggers every 0.125 s (Testrate 8): 40 triggers -> 10 hits, all gaps 0.500.
- bpm manual 120, 1/8: 21 hits in 5.02 s, mean gap 0.2492 (frame-quantised 0.233/0.25); Swing 0.25: alternating
  0.183 / 0.317 (expected 0.1875 / 0.3125 at 60 fps). Project tempo reads 120 = /local/time tempo.
- LFO 7.5 Hz: 37 hits in 5.0 s (7.4/s).
- Fire -> 1 hit; Burst (4, 1/8 @120) -> hits at +0, 0.25, 0.5, 0.75 s; Flash held 30 frames -> env 1.0 throughout,
  then release. Env peaks at 1.0 on the hit frame (attack shorter than a frame).
- Tap x5 at ~0.5 s -> Bpm 122.03 (intervals 0.467, 0.5, 0.5, 0.5: delayed-run timing), engine bpm follows.
- Pixels (u .3 v .6): in 0.482 0.376 0.373 -> Invert (white, env 1) 0.518 0.624 0.627; Dip 0 0 0; Lift Depth 0.5
  0.984 0.875 0.875; Blackout 0 0 0 1 on the same frame it was set.
- td_errors clean, td_layout check ok (no intruders / unboxed / box overlaps), /project1/lab check ok.
- **Perf** (median over 240 frames, other lab COMPs parked, one other agent live): engine 0.21 ms CPU (max 0.41),
  strobe GLSL 0.09 CPU + 0.05 GPU, env/out/switches < 0.02 each: **effect ~0.4 ms**. Test noise 1.59 ms GPU (only
  cooks while the test picture is selected). Whole COMP with test input ~2.2 ms. Project ~60 fps (62.9 measured
  frames/wall-clock, cookRate 60 untouched).
- Captures: session scratchpad `strobe_controls.png` (zkit panel), `strobe_network3.png` (network).

## Not done / open
- Key: no real keystroke sent (would type into the user's TD); the Keyboard In CHOP builds `kspace`, the engine
  fires on its rising edge (offline-tested path).
- `auto` input detection with a real wire into the COMP inputs: in2 detection by numChans and in1 by the COMP's
  connector were probed on a scratch COMP, not on FX_strobe wired to AC_audio (AC_audio is parked).
- Link: tempo only (phase is ours); not tried with a running td_link.
- zkit menu knobs show menu names (n4, projec...) rather than labels.
- A multi-sample (audio-rate) control CHOP is reduced to its max per frame.
