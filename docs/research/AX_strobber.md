# AX: Strobber (Skywalker.Visuals, asset 71752), TOP strobe effector, audio-reactive

Researched 26 Oct 2026. Nothing loaded into TD, nothing run. Files expanded with `toeexpand` (text only).
Source copy: `jazib-td-mcp/research_src/strobber_71752/` (page.html, 5 .tox, STROBBER.toe, `*.dir` expansions).

## What it is
- Page: https://derivative.ca/community-post/asset/strobber-tox-%E2%94%83-top-effector-audio-reactive/71752
  (posted 14 Apr 2025, Luka Papashvili / Skywalker.Visuals, 1.9k views, no comments). Page says "functional with TD 2023".
  Page links: two YouTube videos (zlA_R_1PfUc, XjMHQ2Vg2bw; not watched, no transcript fetched), Instagram, skywalker.vision.
  **No GitHub, no forum thread, no shop, no price, no licence text on the page.** First fetch of the page gave 504 once; retry worked.
- Free anonymous download (tokenised links on the page, no login). Files: `Strobber_Classic_Audio.tox` (20 KB),
  `Strobber_Complex.tox` (23 KB), `Strobber_MAX_Audio.tox` (26 KB), `Strobber_MAX_Complex_Audio.tox` (36 KB),
  `Strobber_Scan.tox` (13 KB), `STROBBER.toe` (163 KB demo, includes Dan's `audioAnalysis1` audio mapper).
  The page also lists a sixth file id (623585 = the .toe).
- Platform: pure TD networks (no C++, no .dll/.dylib/.py shipped). Mac/Windows neutral in principle; author's demo
  file points at `C:/Users/lukac/...mkv` (a demo movie, irrelevant). Only one GLSL (compute) TOP, and it is
  Function Store's `ComplexOp1` template; the strobe itself has no shader.

## How it works (from the expanded networks)
**Classic_Audio** (the core idea, ~40 ops):
- `lfo1` ramp, frequency = custom par `Frequency` (saved 2.69 Hz) -> `switch1` picks LFO (free-run) or audio (`Audio-reactive Strobe` toggle).
- Audio path: `select1` picks a channel by name (custom par `Audio Trigger`: `*`, kick, snare, or beat-division channels
  logic4k/trigger4k/express4k/...4s). `lag1` smooths (par `Smoothing` 0.22) -> `math1` range map -> `trail1`.
- `Count_Analysis` COMP: from one audio channel builds beat divisions: `count` (limitmax 3/7/15) -> `trigger`
  (all envelope times 0) -> `logic` (toggle) and `express` (`if($V==1,1,0)`), i.e. every 4th/8th/16th kick or snare
  (the `4k/8k/16k/4s/8s/16s` channels). This is a counter, not a BPM clock; no BPM par.
- Output "easer" channel -> `easeInterpolator1` (Function Store, 30 easings incl. InCirc default, CustomEase) -> becomes
  the alpha of a white `constant2` over the input, then `compositeSelectiveTOP1` blends it with the input using
  `Blendmode` menu: difference / luminance difference / negate / dodge (invert-type flashes). `rgbaDelay` (Dan) gives the
  RGB-split "RGB Delay" dry/wet. No blackout/colour pickers: flash is white/inverse only.
- `chopexec1` only makes `Frequency` read-only while audio mode is on.
**MAX_Audio / MAX_Complex_Audio**: same plus per-trigger audio for Strobe, Scroll and Seed (three separate channel
selectors), noise, displace X/Y, stretch, threshold, blur, `Period`, `Seed`. **Complex** adds ramps/noise/complex-op
(Dan's `ComplexOp1`, MIT, (c) 2021 Function Store) with `Strobespeed`, `Harmonic Gain`, `Op`, gradient colours.
**Scan**: ramp scan lines + displace, no audio.

Custom pars (Classic): Frequency, Drywet (RGB Delay), Blendmode, Easing, Smoothing, Audio Trigger, Audio-reactive Strobe.
Audio input: not built in; each tox has a CHOP `In` (audio analysis channels in). The `.toe` feeds it from Dan's
`audioAnalysis1` (audiodevin -> audiospect/audiodyna/beat -> per-band low/kick/etc., thresholds, with a `/gal/mapper`).
Per-band triggers: yes via channel select (kick, snare, low...). BPM: no (beat counters only). Envelope: smoothing (lag)
+ easing curve; trigger CHOPs have 0 attack/decay.

## Flash safety
**None.** `Frequency` is a free slider (saved defaults 1.5 to 2.7 Hz; range not decoded from the binary cparm, treat as
unbounded above 3 Hz), audio mode fires on every trigger with no refractory period, no luminance-delta cap, no
area/red check. Whole-frame white / inverted flashes are exactly what the ITC/Ofcom rule limits (>3 per second over
>25% of screen; see `concert-visuals-research/README.md` section on flash limits). Do not use as is on LED.

## Audit
- No network, subprocess, socket, `os`, `urllib`, `webbrowser`, `pip` in any DAT (grep over all `.text/.parm/.n`).
  Only URLs are comment/docs links (derivative.ca, easings.net, shadertoy tlcGzf).
- `eval(prefix+ppar.Value1.expr)` and `op('/gal/mapper/assign').run(...)` appear only in the `.toe`'s audioAnalysis1 panel
  scripts (UI parameter-mapping helper, local, only on mouse events). The five .tox files contain only parexec/chopexec/
  panelexec UI helpers. Pars with external reads: none (movie file in demo `.toe` only).
- Licence: not stated for Strobber; embedded Function Store pieces are MIT (kept in `copyright.text`: asks for an IG tag).
  Per our policy licences do not block study/porting; note the sources (Skywalker.Visuals, Function Store) if adapted.
- TD build: made in 2023-era TD; cparm uses only classic ops; should open on 31550 (not tested, not loaded).

## Verdict
Do not install the tox as the show effect: no flash limiter, white-flash over the full frame, ~40-ops per variant
plus a pile of helper COMPs, audio channels are naming conventions of another toolbox. **Worth borrowing:** the idea
(LFO ramp or audio envelope -> eased alpha -> blend modes difference/negate/dodge), the count-based beat
division (every Nth kick), and the easing menu. Rebuild small and self-contained (below).

## Recipe: `JZB_Strobe` COMP (in: TOP + audio control CHOP; out: TOP)
**User rule (26 Oct 2026): no limits or unsafe guides; the operator decides.** Full ranges, no caps, no limiter stage.
Inputs: `in1` TOP, `in2` CHOP (channels `low`, `level`, `kick` 0..1 from AC_audio). Output: `out1` TOP only.
Custom pars (page "Strobe"):
| Par | Type | Default | Meaning |
|---|---|---|---|
| Source | menu | kick | kick / low / level (audio) / bpm (tempo-synced) / lfo (free run) / manual |
| Threshold | float | 0.6 | rising-edge level for the trigger (hysteresis: re-arm below Threshold-0.15) |
| Division | menu | 1 | audio: fire on every Nth trigger (1, 2, 4, 8, 16) |
| Tempo | menu | project | bpm source: project (TD timeline tempo / Beat CHOP), manual (Bpm par), link (Ableton Link via td_link), tap |
| Bpm | float | 120 | manual tempo (open range) |
| Tap | pulse | - | tap tempo: averages the last 4 taps into Bpm, resyncs the phase on the tap |
| Note | menu | 1/4 | bpm: 4 bars, 2 bars, 1 bar, 1/2, 1/4, 1/8, 1/16, 1/32, plus triplet / dotted |
| Phase | float | 0 | bpm: offset within the note (0..1), Resync pulse snaps the phase to now |
| Swing | float | 0 | bpm: delay every second hit (0..0.5) |
| Rate | float | 2.0 Hz | LFO rate when Source=lfo (open range) |
| Fire | pulse | - | manual single hit (works in every Source mode; MIDI-mappable) |
| Flash | momentary | off | manual hold: flash stays on while held (button, key or MIDI pad) |
| Burst | pulse | - | manual burst of Burstcount hits at the current Note / Rate spacing |
| Burstcount | int | 4 | hits per Burst |
| Key | str | space | keyboard key for Fire (Keyboard In CHOP, only while the COMP's panel or window has focus) |
| Hold | float s | 0 | optional minimum gap between flashes (0 = every trigger) |
| Attack / Release | float s | 0.01 / 0.15 | envelope of the flash |
| Depth | float | 1 | flash amount 0..1 |
| Ease | menu | linear | easing of the envelope (linear, in, out, in-out) |
| Mode | menu | Lift | Lift (add), Dip (to black), Invert (difference), Colour |
| Colour | rgb | white | flash colour |
| Mix | float | 1 | dry/wet |
| Blackout | toggle | off | forces the output to black (panic) |
Trigger logic (CHOPs): `select` source channel -> `logic` threshold with hysteresis -> `count` (mod Division) ->
optional Hold gap (`timer`/expression on absTime.seconds) -> `trigger` CHOP attack/release -> ease (`lookup`).
BPM branch: a `beat` CHOP (Tempo = project, or its bpm driven by the Bpm par / Link channel) gives the beat ramp;
`math` scales it by the Note length (beats per hit, x2/3 triplet, x1.5 dotted), + Phase, swing on odd hits, `frac`,
rising wrap = hit. Tap: a small Parameter Execute DAT stores the last 4 tap times (Table DAT, plain data) -> Bpm.
`switch` picks the active hit source (audio / bpm / lfo / manual), `Fire` is OR-ed into all of them.
Image stage (one GLSL TOP, single pass): uniforms `uAmt` (envelope*Depth), `uMode`, `uColour`. Pixel:
`vec4 c = texture(sTD2DInputs[0], vUV.st); lift: c.rgb = mix(c.rgb, c.rgb+uColour, uAmt);
dip: c.rgb *= 1.0-uAmt; invert: c.rgb = mix(c.rgb, abs(c.rgb-uColour), uAmt); fragColor = TDOutputSwizzle(c);`
If a GLSL TOP tears on this Mac, use the same body in a compute-mode GLSL TOP per LEARNINGS T-46.
Wiring: CHOP -> GLSL uniforms via the TOP's `Vectors` page exports; `out1` TOP only.
Tests (targeted): pulse train into `in2` fires on every Nth trigger, Hold gap honoured when set, Blackout zeroes in one frame.

## Open questions
1. Watch the two YouTube videos (not fetched here) for per-mode behaviour; not needed for the recipe.
2. Decode `Frequency` min/max (binary cparm field order unverified).
