# BB - Test patterns and sync checks: Wallin Pattern Generator (69276) and Video sync test wheel (69246)

Researched 2026-10-26. Nothing was loaded into TD or run. **Both files could not be obtained**: derivative.ca returns 403 to curl on the tokenised `/file/<id>/download` URLs (and on the asset pages themselves); bot protection was not bypassed. Page text came via the fetch tool and web search only, so nothing below about internals (GLSL, ops, custom pars) is verified from the files. Empty dirs with a `NOT_DOWNLOADED.txt` note: `research_src/wallin_69276/`, `research_src/syncwheel_69246/` (each also holds the 118-byte 403 bodies as `*_403.html`; delete them freely). No GitHub repo exists for either (GitHub API search: none found).

## 1. Wallin Pattern Generator (asset 69276)

| Item | Finding |
|---|---|
| Page | https://derivative.ca/community-post/asset/wallin-pattern-generator/69276 ; author Mallin (derivative.ca/user/78075), posted 5 Apr 2024 |
| Files | `Wallin_Pattern_Generator.tox` 858 KB (file 447071), `Wallin_Pattern_Generator_Examples_0.toe` 1.96 MB (file 447079); both 403 to curl |
| TD build / OS / licence | Not stated on the page (UNVERIFIED; 2024 post, so a 2023.x build is likely; the author mentions a GTX 3080, so Windows is the likely platform) |
| What it makes | Pattern generator "mainly for LED walls", also an interactive drawing tool. Single-image test patterns; the author reports a 26K x 5K pattern on a GTX 3080 |
| Modes | Unary (mono), binary (duo), ternary (trios) tile colouring |
| Tiles | Alphanumeric text overlay per tile, logo overlay, per-tile colours; each tile and the logo can be replaced by a custom input design |
| Interaction | Right-click removes a tile, left-click restores, holding paints; middle wheel zoom, middle drag pan, `H` recentres |
| Aspect grid | Optional overlay: screen name, resolution, and a circle for aspect-ratio checks |
| Export | Save design as PNG |
| Not described | Sync / timecode / audio; any per-face slice table; pixel-pitch checks. It is a tile-and-label generator, static |

How it is built: unknown without the file (likely Text/GLSL/Replicator-style tile grid; UNVERIFIED). Audit: not done (no file). If the user later downloads the tox by hand in a browser, run `toeexpand` and grep for `subprocess|os.|eval|exec|pip|http|import` before loading.

## 2. Video sync test wheel (asset 69246)

| Item | Finding |
|---|---|
| Page | https://derivative.ca/community-post/asset/video-sync-test-wheel/69246 ; author Mallin, posted 30 Mar 2024; tags camera, genlock, sync, virtual production, framerate, broadcast |
| File | `video_sync_wheel.tox` 427 KB (file 444715); 403 to curl |
| TD build / OS / licence | Not stated (UNVERIFIED) |
| What it makes | A wheel to test sync between cameras and playback screens. Static rings for 120, 60, 48, 30, 24 rates; the outer ring is dynamic and follows the project's local time component (so it reads the project fps/time) |
| Use | Film the screen with a camera and read the rings: which frames repeat or skip between playback rates. The wheel can be recorded and played back from another playback system |
| Not described | Frame counter, timecode burn-in, flash/beep, audio |

Internals unknown (probably rotating segments driven by absTime, a GLSL or SOP wheel; UNVERIFIED). Same audit note as above.

## 3. Verdicts

- Neither adopted: not verifiable (files unobtained, licence unstated). Both are 2024 community items from one author; the descriptions give only ideas.
- Ideas worth borrowing: (a) Wallin: per-tile on/off painting, custom tile input, aspect circle with screen name + resolution, PNG export. (b) Wheel: several fixed-rate rings plus one ring tied to the project clock; record the wheel to test another player.
- Other prior art found: forum `pGen.tox` (devy, 2014; test screens of different resolutions with numbers; a fix for number placement on resolution change: `(me.parent().digits*2-17) * (op('constant1').width/(2*(op('../table1').numRows-1)))`, forum.derivative.ca/t/test-pattern-generator/6099) and the TD Palette `testGrid` (Palette > Tools, per snaut on that thread). Both are in the user's own install or small; not downloaded. The Palette one is the safest first thing to read (ships with TD).

## 4. Alignment with StageLab (read-only check)

`stagelab/guides/JZB_Slice_Test.md` (FFGL, Arena-side, v1) already defines the vocabulary; reuse it so the TD pattern and the Arena one agree:
- Patterns: Cabinets (ring + `column-row` number), Slices (outline, diagonals, name, LED size, cabinet count), Solid, Bars (white, yellow, cyan, green, magenta, red, blue, black), Ramp (Steps 2-256), Checker, Crosshatch, Walk (Line Across/Down, Diagonal, Dot, Cabinet).
- Exactness rules: lit pixel = exactly Level code (no gamma/dither), whole-pixel lines, text the only anti-aliased part, deterministic (no seed).
- Cabinet 128 x 128 LED px (RFI04 unconfirmed); Native Width 9984; composition px = LED px x comp width / Native Width (7488 delivered: 96 px cabinet). R02 faces 20/10/10/10/30/10/10/10/20 ft = 12/6/6/6/18/6/6/6/12 cabinets wide x 30 high (L1 `1536x3840`, L2 `768x3840`, C `2304x3840` LED px).
- Walk Speed = comp fps (30) gives one step per frame. Use in a TEST column only.

## 5. Recipe: self-contained `test_pattern` COMP (out TOP only)

**Structure** (L-to-R, titled boxes): `params` (custom pars) -> `faces` Table DAT -> `pattern` GLSL TOP -> `overlay` (Text TOPs for labels/counter, Composite) -> `out1` Out TOP. A `syncwheel` branch and `audio` branch described below.

**Custom pars** (page "Pattern"): `Resx`/`Resy` (default 7488 x 2880; menu of 9984x3840 native), `Nativewidth` (9984), `Cabw`/`Cabh` (128), `Pattern` menu {cabinets, faces, solid, bars, ramp, checker, crosshatch, circles, gradient, idlabels, pixelcheck, walk}, `Channel` menu, `Level` 0-255, `Linewidth` 2-64, `Cell` (0 = cabinet), `Steps`, `Walk` menu + `Speed`, `Showfaces` toggle; page "Sync": `Syncwheel` toggle, `Counter` toggle, `Blip` toggle, `Blipfreq` (1000 Hz), `Bliplen` (frames = 1), `Fps` (default `project.cookRate`); page "Layout": `Facestable` DAT ref.

**Face table** (Table DAT, one row per face): `name, x_led, w_led, h_led, cabs_x, cabs_y` e.g. `L1,0,1536,3840,12,30`; the GLSL gets it as a uniform array (max 16 faces) or a small 16x1 float Script/DAT-to-CHOP texture; pixel-to-LED conversion `led = px * Nativewidth / Resx`.

**Patterns in one pass.** One GLSL TOP, fragment mode, single pass, no feedback (T-46: multi-pass tears on this Mac; if any tear shows, port the same code to compute mode with `imageStore`). Per-pixel: find the face by `led.x`, derive cabinet index `floor(local/cab)` and test cases:
- cabinets/faces/idlabels: ring via `min(local mod cab, cab - local mod cab) < linew`; labels via a small Text TOP atlas or Text TOP per face composited above (anti-aliased, the only soft pixels, matching JZB).
- bars (SMPTE-style 8 bars, 100%/75% via `Level`), ramp (`floor(t*Steps)/(Steps-1)*Level/255`, rounded exactly, with Pixel Format 8-bit so codes are exact), gradient (continuous 16-bit float, for banding checks), solid, checker, crosshatch.
- circles: centred circle of radius height/2 per face (aspect check), plus an overall one; concentric rings every `Cell`.
- pixelcheck: 1-px on/off checker and 1-px lines every N px (pitch/scaling; any blur or resample shows as grey).
- walk: line/dot position from a `frame` uniform (`absTime.frame` mod span); step = one frame at Speed = fps.

Set the GLSL TOP to nearest filtering, no mipmaps, 8-bit RGBA (or 16-bit for gradient) and output resolution = `Resx/Resy` exactly (1:1 pixels: wrong resolution invalidates pixel checks).

**Sync wheel + frame counter** (corner or per-face, `Syncwheel`/`Counter`):
- Wheel: second GLSL TOP (own single pass) with rings at 120/60/48/30/24 Hz: each ring has N spokes whose lit phase is `fract(time * rate / spokes)`, where `time = absTime.seconds` (project clock) for the fixed rings and `absTime.frame / Fps` for one dynamic ring; a camera filming the wall sees which rate rings stand still or alias (this is the Wallin-sibling "wheel" idea as the page describes it, our own build).
- Frame counter: Text TOP `{absTime.frame}` plus a binary strip of 24 cells (frame bits, one GLSL step) so a photo or capture can be decoded to the exact frame; plus HH:MM:SS:FF from `absTime.seconds` and `Fps`. Lock identical text to every output (see Syphon/NDI below).
- Flash: a full-height 1-cell white bar on frame `mod 60 == 0` (a "flash" frame), the visual twin of the audio blip.

**Audio blip (optional)**: Audio Oscillator CHOP (`Blipfreq`) x a Trigger/Pulse CHOP firing on `absTime.frame % 60 == 0` with `Bliplen` frames, to Audio Device Out CHOP (per the rule: out = built-in speakers). Measure by recording flash and blip together (phone, or Arena capture + loopback) and comparing offsets. Default off so nothing sounds on the rig by accident; the blip frame equals the flash frame by construction.

**Latency measurement TD -> Arena**: send the COMP's `out1` via Syphon/NDI, with the frame counter in the picture; in Arena put the clip on a layer with no effects, output on the wall or a capture; film the wall and a reference display showing the TD counter side by side; the counter difference at 30 fps times 33.3 ms is the end-to-end latency (+/- 1 frame). Do this with every Syphon/NDI path and each Arena output. Evidence level is "measured with method" only after it is run on hardware; no numbers claimed here.

## 6. Open questions for the user
1. Download the two `.tox`/`.toe` in a browser if wanted (links are on the asset pages; free, no login stated); then audit by `toeexpand` and extend this file with real internals.
2. Should the test COMP be a tox shipped with the MCP (`td_tox_load`) or a macro that builds it? (Build only after the user asks.)
