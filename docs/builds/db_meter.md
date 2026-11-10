# db_meter (`/project1/lab/AU_db_meter`)

Stereo peak / RMS level meter: dB scale, peak hold line, clip lamps, labels that line up with the bars at any size,
vertical or horizontal. Clean-room design from `docs/research/BG_rudiment_db_meter.md`. Built and checked on TD 2025.31550.

## Build / rebuild
```python
# through td_exec
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/db_meter.py').read(), ns)
ns['build']('/project1/lab')              # panel=True also remakes the controls panel sections
```
Idempotent: ops are reused by name and their text/pars/wires re-set; custom parameter values and the panel are kept.
Logic (`builders/db_meter_logic.py`) is copied into the `meter_logic` Text DAT; offline tests:
`python3 -I -m unittest discover -s test -p 'test_db_meter.py'`.

## Use
- Wire audio (1 or 2 channel CHOP, any rate) into the COMP's input (`in1`). Nothing inside goes to an audio output.
- `out1` (TOP): the meter, `Resw` x `Resh` (default 256 x 1024), rgba8, premultiplied; `Transparent` = alpha 0 bg.
- `out2` (CHOP): `l r` (bar, dB), `lpeak rpeak` (hold line, dB), `lclip rclip` (0/1).
- Something must pull `out1`/`out2` every frame (a viewer, a Syphon/NDI out, a CHOP Execute...) or it stops cooking, as
  any TD op does.
- Controls: pulse `Opencontrols` (page Controls) -> own window with the Meter, Input and Look pages; colours on page Colours.

## Parameters
- Meter: `Mode` peak/rms, `Floor`/`Ceil` dB, `Step` label dB, `Gain` dB, `Attack` s (0 = instant), `Release` dB/s fall
  (bar and hold line), `Hold` s (peak line and clip lamp), `Clipdb`, `Holdreset`.
- Input: `Source` In CHOP / Test tone (internal Audio Oscillator, never routed to a speaker), `Channels` auto (1 ch on both
  bars) / mono (first channel on both) / stereo (missing R = silent), `Testamp`, `Testfreq`, `Testchan` both/left/right.
- Look: `Resw` `Resh` `Orient` `Gap` `Scalew` `Showscale` `Showpeak` `Peakpx` `Fontsize` (0 = auto) `Transparent`.
- Colours: `Gradlow` (below -18 dB) `Gradmid` (-6 dB) `Gradhigh` (0 dB and up, clip lamp) `Track` `Bg` `Peakcol` `Labelcol`.

## Network (stages)
1 Input (In CHOP / test tone / silence -> Switch -> per-channel Select + gain -> Merge `lr`) -> 2 Level (Analyze max of
|x| or rmspower per frame block) -> 3 dB (Expression CHOP) -> 4 Ballistics (Script CHOP: meter_logic.meter_step; state in
its callbacks module, a `Frame` clock par = cooks every frame) -> `levels` -> `out2`.
5 Geometry (`geometry`, `label_table` Script DATs, one layout) -> 6 Bars (single-pass GLSL) + 7 Scale labels (Script TOP,
cv2, ink centre placed on the bar row) -> 8 Compose (Over) -> `out1`. Controls stage: panel, window, Parameter Execute.

## Crash safety (T-70)
The builder never calls `.destroy()` directly: `_sd()` = `safe_destroy` (td_exec namespace, else the handlers module).
`build()` closes the COMP's own `controls_window` first; the `controls` container and its `sec_*` sections are kept and
refilled in place (only their widgets are cleared, with the window closed). The network pane is not moved by the builder.

## Verified live (TD 2025.31550, 26 Oct 2026, test tone inside the COMP, no audio out)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
- Peak: amp 1.0 / 0.5 / 0.01 / 1.2 -> `l` 0.00 / -6.02 / -40.00 / +1.58 dB; RMS at amp 1.0 = -3.01 dB.
- Hold 1.5 s, Release 24 dB/s: after a 0 dB -> -40 dB step the bar fell 24 dB/s (-16.4 dB at 0.683 s); `lpeak` held
  0 dB to 1.5 s, then fell 24 dB/s (-7.6 dB at 1.817 s); `lclip` held 1 for 1.5 s, lamp pixel = Gradhigh.
- Testchan left: `r` = floor (-60), `l` -6.02 (channel order). No input wired, Source In CHOP: silence -> -60.
- Picture: bar top row 844 vs mapping 843.41 (vertical 256x1024), 837 vs 836.27 (horizontal 1024x256).
- Labels: label ink centres and ticks within 0.5 px of the bar mapping at Resh 256, 1024 and 1920 (12 labels each).
- Perf per frame (CPU): bars 0.42 ms, ballistics 0.14, compose 0.09, rest < 0.05 each (~0.75 ms total); labels Script
  TOP cooks only on change (3-5 ms at 256x1024; first cook at 1080x1920 ~1 s, once).
- Not yet checked: real audio through `in1` (needs a source wired outside the COMP, e.g. AC_audio).
