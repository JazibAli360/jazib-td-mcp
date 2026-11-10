# BG - twozero "dB Meter" rudiment + our clean-room build (`db_meter` COMP)

Researched 26 Oct 2026. Nothing loaded into TD, nothing run, no sign-in. Build target TD 2025.31550, macOS Apple Silicon (Rosetta x86_64).

## 1. What the original is (sources and what we could and could not get)

Sources fetched (HTTP 200, curl + WebFetch):
- `https://twozero.ai/rudiments/twozero/db-meter` : a SvelteKit single-page app. The pre-rendered HTML carries only the title and meta tags; the body (features, parameters, download) is rendered client-side by JS and was NOT readable without running a browser (not done). `https://twozero.ai/rudiments` (listing) is the same: empty shell, no list in the HTML. No GitHub/video/docs links in either page. Rudiments appear to live inside the twozero app (`app.twozero.ai`), i.e. probably delivered through the twozero TD plugin, not as a public .tox: no free .tox download found, so nothing to toeexpand. Licence/price/TD version: UNVERIFIED.
- Meta description (verbatim): "Stereo peak level meter with a dB scale, peak hold and labels that always line up with the bars."
- Cover image `.../db-meter/cover.jpg` (saved at `research_src/rudiments_db_meter/cover.jpg`, public og:image): four copies of the same meter at four sizes (tiny to tall).

Facts that are evidenced (description + cover image):
- Stereo: two vertical bars side by side (L, R), narrow, with a dark-grey track behind each.
- dB scale to the right of the bars on a black strip. Labels: 3, 0, -6, -12, -18 ... -60 (6 dB steps, top headroom +3 dB; floor -60 dB). On the smallest copy the labels shrink with the meter: the scale scales with the component.
- Bar fill is a vertical gradient: dark green at the bottom, through olive, to yellow-amber near the top of the filled part (the gradient is fixed to the scale, not to the current level; red zone above 0 dB not visible in the cover).
- Peak hold: a thin light line that sits at the highest recent level of each bar (visible on each bar, at different heights per channel).
- "Labels always line up with the bars": label positions are computed from the same dB-to-height mapping as the bars, at any size.
Not known (UNVERIFIED, do not claim): parameter names, input type (CHOP or audio device), attack/release/hold times, output (TOP most likely), whether RMS is offered. The spec below defines its own.

## 2. Clean-room build spec: `db_meter` (Base COMP)

Same functionality, our own design, own code. Name rule: custom pages and pars = one capital then lowercase/digits.

### 2.1 Interface
- Inputs: `in1` In CHOP (audio, 1 or 2 channels, any sample rate; 1 channel = mono drawn on both bars). Fed by `AC_audio` (it feeds the default input device) or any CHOP. Optional `in2` unused.
- Outputs: `out1` Out TOP (the meter picture, `Resw` x `Resh`, rgba8 with alpha) and `out2` Out CHOP (`l`,`r` level in dB, `lpeak`,`rpeak` hold in dB, `lclip`,`rclip` 0/1). Outs carry only output.
- The COMP never touches the audio output: default out stays the Mac speakers (do not add an Audio Device Out inside).

### 2.2 Custom parameters (names; T-00e capital-first)
Page `Meter`: `Mode` (menu peak / rms), `Floor` (dB, -60), `Ceil` (dB, +3), `Step` (dB between labels, 6), `Attack` (s, 0.0), `Release` (dB/s fall, 24 or release time 0.3), `Hold` (s, 1.5), `Holdreset` (pulse), `Clipdb` (0), `Channels` (menu auto/mono/stereo), `Gain` (dB trim, 0).
Page `Look`: `Resw`/`Resh` (default 256 x 1024 vertical; 1080x1920 when used as a PF26 overlay), `Orient` (vertical/horizontal), `Gap` (px between bars), `Scalew` (fraction of width for label strip, 0.4), `Showscale` toggle, `Showpeak` toggle, `Gradlow` / `Gradmid` / `Gradhigh` RGB (green / yellow / red), `Bg` RGBA, `Trackcol` RGBA, `Fontsize`.
Page `Controls`: pulse `Opencontrols`.

### 2.3 Internal network, stage by stage (uses `td_layout stages`; titles in quotes)
1. "Input": `in1` (In CHOP) -> `selectchan` (Select CHOP, `l r`; mono duplicates via `Channels`) -> `gain` (Math CHOP, Multiply = 10^(Gain/20)).
2. "Level" (needs a block of ~1 frame at 48 kHz = 800 samples): `abs` (Math CHOP abs) then Mode peak: `Analyze` CHOP function Maximum, collapsing the per-frame block to one sample per frame (or Trail CHOP window = 1 frame + Analyze max); Mode rms: Math (square) -> Analyze Average -> Math (sqrt). A Switch CHOP picks by `Mode`. Floor the value at 1e-6 before log.
3. "dB": Expression CHOP `20*math.log10(max(me.inputVal,1e-6))` (or Math CHOP postop log10 then multiply 20); clamp to [Floor, Ceil] with Limit CHOP.
4. "Ballistics": Lag CHOP (Lag1 attack = `Attack`, Lag2 release = `Release`) on dB for smooth fall; instantaneous rise by default. Peak hold: Hold CHOP is not enough (it samples); build the peak line with a CHOP Execute DAT (onValueChange / Execute DAT frame callback, small and pure Python, see 2.5) that keeps `peak` and `peak_t`, writes both into a Constant CHOP `peakstate`. Clip: Logic CHOP `level >= Clipdb` -> Hold with `Hold` time -> `lclip`,`rclip`.
5. "Geometry": a CHOP-to-values Reference: the shader takes `uL, uR, uLpk, uRpk, uClipL, uClipR` as vec/float uniforms from `op('level')['l']` etc. (GLSL TOP Vectors page, expressions). No per-frame Python needed.
6. "Bars" (ONE single-pass `glslTOP`, so no multi-pass tearing on MoltenVK, T-46): outputs rgba8; per pixel: map y to dB = mix(Floor, Ceil, y); bar fill where dB <= level; colour = gradient by dB (stops at -18 and -6/0 dB, smoothstep), track colour elsewhere, peak line = 2 px where |dB - peak| < half-pixel width in dB, clip lamp = top 6 px red when clipped. Layout: 2 bars with `Gap`, label strip on the right (`Scalew`) kept black.
7. "Scale labels": a `scriptTOP` (numpy + cv2 putText; cv2 ships in TD's Python) renders the whole label strip, re-cooking only when Floor/Ceil/Step/size/font change. Label y positions come from the same function the shader uses (exact alignment). Fallback: up to 20 native Text TOPs placed with Transform TOPs from the same function.
8. "Compose": `over` Composite TOP (labels over bars over `Bg`) -> `out1`.
9. "Controls": own `controls` panel (autoUI, `Pagescope` = Meter, `Pagetabs` off, `align verttb`, widget clones cut so the COMP stands alone) + `controls_window` opened by `Opencontrols`. Output has no controls in it.
Roles/colours per house rule: input blue, analysis orange, display green, controls on top of column 0.

### 2.4 Optional extras (after v1)
`Weighting` menu (flat / A) via Audio Filter CHOP; LUFS-style short-term mean (400 ms RMS) read-out; correlation meter; numeric read-out text of peak dB; EBU +9 scale preset; horizontal orientation (same shader, swapped axes).

### 2.5 Pure-Python logic testable offline (no TD)
Put in one ASCII module `td/db_meter_logic.py` (no `td` import) with pytest in `test/`:
- `amp_to_db(a, floor)`: 0 -> floor, 1.0 -> 0, 0.5 -> -6.02, clamp.
- `db_to_frac(db, floor, ceil)` and its inverse; labels use this same function as the shader contract (a unit test asserts the shader constants equal it).
- `label_rows(floor, ceil, step)`: rows 3, 0, -6 ... -60 (include the exact ceil label and 0 even if not on the step grid, as in the original's 3/0), no label closer than 1/30 of the height to another.
- `PeakHold` class: `update(db, t)`: holds `hold` seconds then falls at `release` dB/s, resets on `reset()`; deterministic with injected time.
- `rms`/`peak` of a numpy block (equals sine amplitude / sqrt(2): a full-scale sine is 0 dBFS peak, -3.01 dBFS RMS).
- `Ballistics` (attack/release lag) step response vs. closed form.

### 2.6 Verify live (TD 31550; name the build in the note)
1. Feed a Constant/Wave CHOP sine at amplitude 1.0, 0.5, 0.1, 0.01 (Audio Oscillator CHOP, 440 Hz) into `in1` (no sound needed: do not route it to the speakers): `td_inspect out2`: `l` = 0.0, -6.02, -20.0, -40.0 dB (+-0.1). RMS mode: -3.01 below peak.
2. `td_inspect out1`: not black, `sample:4` shows the bar top at the right row: with Floor -60, Ceil 3: frac = (db+60)/63. Compare to the shader row within 1 px.
3. Left only: feed a 2-channel source with only `l`: R bar at floor, L bar up (checks channel order).
4. Peak hold: step 1.0 -> 0.0 amplitude: `lpeak` stays 0 dB for `Hold` s (+-1 frame) then falls at `Release` dB/s.
5. Clip: amplitude 1.2 with `Clipdb` 0 -> `lclip` 1 held; screenshot red lamp.
6. Label alignment: capture window at 3 `Resh` values (256, 1024, 1920): each label centre on its bar row within 1 px (numbers from the script TOP row table, not eyeballed).
7. Real audio: `AC_audio` default input on, play music on the Mac: level moves, `td_perf` cook time of the COMP < 1 ms; `td_errors` empty. Output stays on built-in speakers (check, do not change).
8. `td_layout check`, `td_window_capture`; pause the controls panel and confirm nothing breaks (self-contained).

### 2.6b Mac / 31550 caveats and fallbacks
- Single-pass GLSL only (T-46); the shader fits in one pass. Use `out vec4 fragColor` + `TDOutputSwizzle`; `rgba8` is enough; float uniforms from CHOP expressions are fine.
- Audio Device In CHOP block size: Level stage must use per-frame blocks (Analyze) not per-sample loops in Python.
- Rosetta TD: cv2 in bundled Python is present (`site-packages/cv2`) for the label Script TOP; if its putText font is too ugly, fallback to N Text TOPs (Text TOP is native, safe) or a pre-rendered label atlas PNG from the system font.
- Do not hold the mic in the COMP itself; the `In CHOP` only. Never route to speakers (feedback rule: mic -> speaker forbidden).
- Gated on newer builds (for `docs/FUTURE.md`): a POP/GLSL-compute path for the bars (not needed); `Audio Device In` loudness mode / any built-in loudness CHOP if a later build adds one; EBU R128 via EssentiaTD (AP note) once installed.

## 3. Estimate
Logic module + tests: 30 min; CHOP chain + shader + label strip: 90 min; controls panel/window + layout + live verification: 60 min. About 3 h with one agent; 2 h with logic/tests and TD build in parallel.

## 4. Companion notes for the other five twozero/vankrav links (not researched here)
Face tracking (vankrav) must run on the stored clip `media/webcam/webcam_ref_5s.mp4`; TD's bundled Python has `cv2` (OpenCV: Haar/DNN face detection works in a Script TOP), `numpy`, no `mediapipe` visible in site-packages. MediaPipe via Web Render TOP (WASM) or Apple Vision stay options; Nvidia ops out; Optical Flow TOP unsupported (T-18). Separate research tasks.
