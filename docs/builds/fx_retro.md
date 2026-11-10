# fx_retro: FX_retro rack + 5 modules (palette, dither, glyph, teletext, smalldisplay), live in main, 26 Oct 2026

`/project1/lab/FX_retro`: retro machines and displays. The rack is the lean FX_glitch rack, copied as FX_destroy did
(template: `docs/builds/fx_glitch.md`). Research: `docs/research/FX0_effects_backlog.md` rows 23 / 59 / 60 / 78,
`docs/research/FX2_analog_video_hardware_emulation.md` AV-34, 35, 38, 39 and 40, FX5 G21 / G25, FX3 S4.
**Status: LIVE on 31550** (built module by module on build TD b2, brought home into the main .toe, parked, saved):
every LIVE CHECK passes ("Verified live" below; live fixes in LEARNINGS T-141). Offline status:
`python3 -I -m unittest discover -s test -p 'test_fx_retro.py'` passes 57 tests. They cover the logic, the palette_map
reuse, the numpy references used by the live checks, the Script CHOP adapters on fakes, a dry build of every module on
a fake TD with the rack's real helpers, and a glslc compile (OpenGL target, TD stubs) of all 7 compute shaders.

## Files
| File | What |
|---|---|
| `builders/fx_retro.py` | Rack: slots / chain / Panic / Input (auto, live, test clip, **test ramp**). It also holds the shared pieces (each is used by 2+ modules): the logic DATs, the palette bank texture, the 64x64 blue noise, the font texture, the GLSL lib, the codes Script CHOP, the pulse exec, and `_compute` (manual dispatch, texture-buffer arrays, extra buffers) |
| `builders/fx_retro_logic.py` | Pure logic. It mirrors the GLSL and gives the references the checks use. It **imports `palette_map_logic`** (hex, OKLab, Bayer 8x8, pick rule, Lospec presets: reused, not copied) and `fx_retro_font8x8` |
| `builders/fx_retro_font8x8.py` | 214 glyphs, 8x8 1-bit: ASCII 21-7E, block elements 2580-259F, hiragana 3040-309F. Source: font8x8 by Daniel Hepper, public domain, https://github.com/dhepper/font8x8 (fetched 26 Oct) |
| `builders/fx_retro_<module>.py` | `pages(Lg)` / `presets(Lg)` -> `PAGES` / `PRESETS`, `shader_texts(lib)`, `build(m, H, Lg)` |
| `builders/fx_retro_checks.py` | Live checks: `setup(c, id)` (exec 1) and `check(c, id)` (exec 2), plus `settext`, `eink_flash` and `cost` / `cost_result` |
| `test/test_fx_retro.py` | Offline tests |

## Build (lane, ~3 min)
On a build TD first (T-120), then bring it home:
```python
# td_exec target:'b2' (or main if the user says so)
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_retro.py').read(), ns)
ns['build']('/project1/lab')            # rack + palette1 (enabled 1) + dither1 / glyph1 / teletext1 / smalldisplay1 (enabled 0)
# Rest state in main (27 Oct, FX racks rule, MAIN_AUDIT_27OCT A2): every slot enabled 0, palette1 too (a first build still
# turns palette1 on; the rack rests as a clean passthrough when un-parked).
ns['add']('/project1/lab/FX_retro', 'glyph')     # another instance (glyph2), wired last; ns['remove'](c, 'glyph2')
```
Then: `td_layout` flow, `td_errors` clean, `td_checkpoint`, and `td_bring_home {comp:'/project1/lab/FX_retro', from:'b2'}`.
Lane rules (CLAUDE.md): `python3 tools/lane.py add FX_retro "<label>"`, `allowCooking = True` at each step, other idle
COMPs parked, 60 fps with the rest parked. `build` makes the 64x64 blue noise in Python once (~1 s, void-and-cluster).

## Network
| Stage | Ops |
|---|---|
| Rack | `slots` (name module enabled order mix), Text DATs `fx_retro_logic`, `palette_map_logic`, `fx_retro_font8x8` (same text as the files; the logic imports the other two) |
| Shared data | `pal_custom` (Table: hex per row) -> `pal_bank` (Script DAT, `bank_rows`) -> `pal_chop` (DAT to CHOP, channel per column) -> `pal_top` (CHOP to TOP r32float: width = 590 entries, 6 rows r g b L A B, the palette_map layout). `bn_table` -> `bn_chop` -> `bn_top` (64x64 r32float, (rank + 0.5) / 4096; `firstcolumn values`, T-141 (4)). `font_table` -> `font_chop` -> `font_top` (428 x 2 r32float: uint32 glyph words, row 0 lo / row 1 hi 16 bits; read by glyph / teletext / smalldisplay through a Select TOP `font`; a `const uint FONT[428]` cost ~3 ms per pass, T-141 (1)). All cook only on change |
| 1 Input | `in1`, `test_clip` (webcam 5 s, 1080x1920), `test_ramp` (horizontal black -> white) -> `img_src` |
| 2 Slots | `<name>` -> `<name>_mix` (Cross) -> `<name>_slot` (Switch 0 bypass / 1 module / 2 mix) |
| 3 Out | `panic` -> `out1` |

Each module ends in `out_sel` (Switch). At Amount 0 it selects `in1`, so the result is bit-exact and no pass cooks.
Modules read the bank, the blue noise and the font through Select TOPs `pal` / `bn` / `font` (`../pal_top`, `../bn_top`, `../font_top`). Every pass is a
compute GLSL TOP (T-46 / T-47) with at most 3 wired inputs (T-88). All passes run in one dispatch, with no multi-pass
pixel chains.

### Machines (palette bank, `fx_retro_logic.MACHINES` + every palette_map Lospec preset + Custom)
| Key | Entries (bank offset) | Note |
|---|---|---|
| dmg / gbbgb / gbpocket | 4 (0) / 4 / 4 | DMG greens [M], bgb (palette_map preset), Pocket greys [M] |
| nes | 55 (12) | 2C02 common table [M], duplicate blacks dropped |
| c64 | 16 (67) | Pepto [M] |
| cga0lo / cga0hi / cga1lo / cga1hi / cga16 / ega64 | 4 / 4 / 4 / 4 / 16 (99) / 64 (115) | mode 4 palettes, RGBI, all 64 EGA |
| spectrum | 16 (179) | 8 + 8 bright (black twice, so the halves rule works), Constraint auto = cell |
| amiga12 | 0 | bits 4/4/4 (shader quantises, no bank) |
| amigaham | 16 (195) | 16-step grey base, Constraint auto = ham |
| pico8 / teletext / mac1 | 16 (211) / 8 (227) / 2 | |
| pm_* | | the 16 other palette_map presets (Sweetie 16 ... Solarized) |
| custom | rows after 588 | `pal_custom` (1 black 'none' row when empty) |

There are 588 fixed entries. With the default 2-row `pal_custom`, `pal_bank` has 591 rows (header included) and
`pal_top` is 590 x 6.

## Modules
### `palette` (AV-34): ops `fx`, `ham`, `out_sel`
Virtual pixels are Pixelsize x (Pixelsize x Pixelaspect), whole pixels anchored bottom-left, sampled at the centre or
by box average, then pre-adjusted (Contrast / Brightness / Saturation). Kinds:
- **list**: nearest bank entry in OKLab (Lightness weight) or sRGB. Dither uses palette_map's rule: the second-nearest
  wins when `t x Ditheramt > threshold`, with `t = d1 / (d1 + d2)`. Thresholds are Bayer 2-16, IGN, white or blue,
  and Ditheranim Hz offsets them.
- **bits** (amiga12): per channel `floor(v (2^b - 1) + thr) / (2^b - 1)`.
- **Constraint cell**: one workgroup per 8x8 virtual-pixel cell. 64 threads search all `n(n-1)/2` pairs (cost = sum of
  min dist^2, Spectrum pairs from the same half), then reduce in shared memory (ties go to the lowest pair). Each pixel
  takes the nearer of the two.
- **Constraint ham** (`ham`): one workgroup per virtual row, left to right in 256-px chunks: the 64 threads find each
  pixel's colour and best base entry in parallel (shared memory), thread 0 runs the hold-and-modify scan, all 64 write
  the blocks (T-141 (3)). Each pixel is the best of 16 base entries or the previous pixel with ONE channel set to
  `floor(c x 15 + 0.5) / 15`.

Dispatch: `fx` = ceil(VW/8) x ceil(VH/8), `ham` = VH.

Presets: 1 game boy, 2 nes (aspect 8:7), 3 c64 (0.936), 4 spectrum clash, 5 amiga ham, 6 pico-8 (bayer8).

### `dither` (AV-35, G25, S4): ops `fx`, `fxd`, `out_sel`
- **Method** none / bayer2-16 / ign / white / blue: ordered, per virtual pixel, Strength and Animate Hz.
- **gbcam**: luma -> Gbcontrast around 0.5 -> + Gbedge x (4y - 4 neighbours) -> n levels with Bayer 4x4. Each level
  shows the palette entry of that OKLab-L rank (Machine dmg). The threshold matrix is not the real M64282FP register
  set [M].
- **Diffusion** (fs, atkinson, sierralite, jarvis, stucki, burkes) runs in `fxd`, **tile-parallel**. Each thread scans
  one Tile x Tile block (4 <= Tile <= 64, default 16) serially and can go serpentine, 64 threads per workgroup.
  Errors live in a 3-row ring per thread in colour buffer 1 (rgba32float, readwrite), interleaved by thread; errors
  that leave a tile are dropped. (A 12 KB shared-memory ring per 4-thread group ran 12-29 ms live, T-141 (2).)
- **Colour**: Levels per channel / grey levels / palette (Machine). Linear quantises in linear light (rgb and luma
  only).

Presets: 1 bayer 1-bit, 2 blue 4-level, 3 atkinson mac, 4 gb camera, 5 floyd pico-8, 6 shimmer (IGN 12 Hz).

### `glyph` (AV-39, G21, G-ASCII): ops `fx`, `out_sel`
There is one workgroup per Cellw x Cellh cell, counted from the top-left, and dispatch = cols x rows. The 64 threads
sample the cell on an 8x8 bilinear grid into shared memory. Each mode then picks a glyph:
Reductions (cell mean, textmode pattern bits, half means, best shape) are 6-step shared-memory trees (T-141 (3)).
- **ascii**: luma -> Contrast, Gamma, Invert -> `ramp[floor(l x n)]`. Ramps: ascii (10), dense (resampled to 33),
  blocks, digits, binary, hex, hiragana, or custom. Custom sorts the Chars by ink coverage. Ramps reach the shader as
  3 vec4 of packed bytes, up to 33 glyphs.
- **matrix**: up to 4 streams per column. Each stream gets hash speed, trail, phase and gap, with the head in its own
  colour. The glyph changes at Changerate. Rainmask is none, luma or colour, and Mirror flips the glyphs.
- **textmode**: the cell's 8x8 above-mean pattern is matched against the Shapeset glyphs by
  `bitCount(pattern ^ glyph)`, with inverted glyphs and space allowed. fg / bg are the two half means, or the nearest
  Machine entries (cga16).

Bgmode: black / source dim / transparent / Bg. Presets: 1 ascii colour, 2 green terminal, 3 matrix rain,
4 ega textmode, 5 blocks.

### `teletext` (AV-38): ops `page` (Table), `codes` (Script CHOP), `pulse_exec`, `fx`, `out_sel`
The grid is Columns x Rows, and Rows 0 = auto from Cellaspect: 40 x 59 at 1080x1920. The colours are the 8 of
teletext level 1.
- **image**: per cell the best (fg, bg, 6-bit mask) of 8 x 8 ordered pairs over 6 sixel samples in OKLab. A sixel
  takes fg on ties, the lowest index wins, and sixel rows split 0.3 / 0.4 / 0.3. Separated mosaics use Sepgap.
- **page**: row 0 is the Header with `%a %d %b %l %M %S %p %P`, always 12-hour, so the default reads
  `P100 TELETEXT 100 Mon 26 Oct  6:30/45 PM`. The page table (or Pagedat) follows, using markup. Spacing attributes
  take one cell, as on a real decoder: `{red}`..`{white}` set an alpha colour, `{gred}`..`{gwhite}` set a mosaic
  colour (chars 20-3F / 60-7F become sixels), `{bg}` sets the new background, and `{black}`, `{dh}` / `{nh}`, `{flash}`
  / `{steady}`, `{conceal}`, `{sep}` / `{cont}` work as named. `{{` prints a brace.
  - A `{dh}` row puts its bottom halves in the next screen row, and the following lines move down one row.
  - Rows after the text and empty lines (`''`) show the picture mosaic (Imagebody) or black; a line of one space is a
    black row. The default page has 17 empty lines so Fastext lands on row 24 (`PAGE_GAP`).
  - Reload starts the page load: row r appears at `r / rows x Loadtime`.
- **subtitle**: Subtitle or Subtitledat lines (`|` or rows) are wrapped to cols - 4, centred, boxed in black and
  double height, Subrow rows from the bottom, in Subcolour.

Flash hides fg during the second half of each 1/Flashhz period. Conceal hides text until Reveal. Text uses the 8x8
font with optional SAA5050-style corner rounding (Smooth). There are no Urdu glyphs; use urdu_type. Codes are packed
per cell into a float-exact int (`tt_pack`: char 7 bits, fg 3, bg 3, mosaic, sep, flash, conceal, dh top / bottom,
image). The `codes` Script CHOP cooks when the pars it reads change, and once a second through the Tick par
(`int(absTime.seconds)`) for the clock. It reaches the shader as `uniform samplerBuffer uCodes` (T-110).

Presets: 1 mosaic, 2 separated (56 cols), 3 page (25 rows), 4 subtitles (yellow).

### `smalldisplay` (AV-40): ops `codes`, `pulse_exec`, `state`, `fx`, `out_sel`
`state` is a compute pass, rgba32float, read-write with **2 colour buffers** (T-110 (5)), one texel per dot or cell.
Buffer 0 holds the display state, with w = display id + 1 (any other value re-inits). Buffer 1 x holds that texel's
last update time, so dt = now - that time. A second cook in the same frame (readbacks, T-116 (4)) is therefore a
no-op, and a gap > 0.25 s re-inits. There is no stamp op. `fx` renders at the input size. The six displays:

| Display | State texel | Render |
|---|---|---|
| lcd | displayed rgb (Levels, Rise / Fall exp response) | dot = mix(On dark, Off light, value), gap = Bg, drop shadow of the dot Shadow px up-left x Shadowamt; Lcdcolour = RGB stripes |
| vfd | intensity (Threshold 1-bit or Levels) | rounded dot + 3x3 neighbour glow (Glow), faint unlit dots, Meshpitch grid darkening, Flicker |
| nixie | digit (0-9, 10 ':', 11 '.', -1), previous, change time | glass tube (Gap), numeral stroke SDFs (141 segments), unlit cathodes inside the digit box (Cathodes), glow, Fade crossfade, hex anode mesh |
| flipdot | side, flip start (-1 idle), new side | disc of radius (1 - Gap) / 2 squashed by abs(cos(pi p)) over Fliptime, old side until p = 0.5; Flipscan all / columns / rows / random over Sweep s |
| splitflap | alphabet index (46: space A-Z 0-9 . , : - ! ? / & '), flap start | card + hinge line; top half shows the next char behind the falling flap, bottom half shows the flap's back (next char) after p = 0.5; one card per Flapstep until on target |
| eink | displayed grey, target, last update | partial updates at Updatehz leave Ghost x old; full refresh (Refresh pulse / Refreshperiod) = inverted, black, white, new in quarters of Flashtime |

Content: image (dot displays, 2x2 bilinear box per dot), text (Text / Textdat), clock (12 h: nixie ` 6:30:45` on 8 tubes, split-flap
`6:30 PM`, dots `6:30:45 PM`) or value (Format). For dot displays, text is drawn with the 8x8 font, one char per 8x8
dots. Presets: 1 game boy lcd, 2 vfd, 3 nixie clock (8 tubes), 4 flip-dot (columns sweep), 5 split-flap (8x6), 6 e-ink.

### `pixelart` (SX-08, lane D 27 Oct): ops `low`, `fx`, `out_sel`
Pixel-art re-render: `low` (compute, VW x VH rgba16float, one texel per virtual pixel: centre / box sample, Contrast /
Brightness / Saturation, Colour = source / Levels per channel / rack palette Machine with the rack's ordered dither)
-> `fx` (full res: nearest upscale; a virtual pixel with a 4-neighbour brighter by > Edge (luma step, or RGB
distance with a brighter neighbour) gets the Outline colour x Outline = a 1-px outline on the DARK side of every
edge; otherwise, if it is brighter than its neighbour away from Lightangle (8 directions) by > Edge, it is lightened
by Highlight = the lit rim; Grid darkens the left column / top row of every virtual pixel). Premultiplied out, Amount
mix; bits machines (amiga12) fall back to source colours. Mirror: `fx_retro_pixelart_logic.py` (none / levels;
palette = the palette module's maths). Presets 1 sprite, 2 pico-8 toon (bayer4), 3 chunky clean (box, grid), 4 nes
outline (8:7, RGB edges), 5 neon edge (cyan outline). Est. 0.2-0.4 ms (low is tiny; fx 5 fetches per pixel).

LIVE CHECKS (pixelart): PA1 builds clean, both passes compile; PA2 Amount 0 / slot enabled 0 / mix 0 / Panic ->
**0**; PA3 parity vs `reference` (clip paused, Colour levels, no dither): within (2/255) >= 0.995 at Pixelsize 6 and
4 x aspect 8/7; PA4 palette preset: every pixel's colour is a bank entry of the Machine (`outside_palette` 0 as P1);
PA5 presets full state; PA6 cost, fps.

Verified live (pixelart, scratch, 27 Oct 2026, 31550; rack built from the builder with palette1 + pixelart1): PA1
clean (686 ops, errors 0); PA2 **0 / 0 / 0 / 0**; PA3 levels Pixelsize 6 within **1.0** (max 0.0020, 99 % of pixels
changed), Pixelsize 4 x 8/7 + RGB edges + grid 0.3 within **1.0**; PA4 pico-8 toon (outline / highlight off):
outside_palette **0**, 13 distinct colours; PA5 presets 1-5 full state; PA6 cost (median / p90) sprite 0.90 / 1.54
ms, pico-8 toon 0.85 / 1.60, chunky clean (box) 1.24 / 2.81, nes outline 1.01 / 1.66, neon edge 0.97 / 2.34;
project 60.12 fps.
Main (JazibTD_home.676): `add` pixelart1 by builder (enabled 0, 7 wires), errors 0, presets full state, parked.

### `scaler` (SX-09, lane D 27 Oct): ops `low`, `src_top`, `src`, `fx`, `out_sel`
Shimmer-free scaling of a low-res source to the rack size. Source = this picture on a virtual grid (`low`, Pixelsize,
centre / box) or any low-res TOP (Inputs page Sourcetop, Source = top; used at its own resolution through `src`).
Modes: nearest; sharp bilinear (= box-filter pixel AA: inside a texel the sample stays at its centre, and only the
last Sharpness output pixel at each texel edge blends, so integer scales equal nearest exactly and non-integer scales
never crawl); EPX / Scale2x corners (a corner takes the neighbour colour when its two neighbours match and the
opposite ones differ, Tolerance = colour match); diagonal (the same corners cut on a 45 degree line with a one-output-
pixel antialiased edge). Fit stretch / fit (aspect kept, transparent borders) / integer (largest whole scale).
**Clean-room code**: the ideas are public (sharp-bilinear / pixel_aa concept, EPX 1992); no libretro file was copied,
so no per-file licence applies (the SX-09 "check each header" note is moot). Mirror: `fx_retro_scaler_logic.py`
(texelFetch only on both sides). Presets 1 clean diagonals, 2 sharp bilinear, 3 scale2x, 4 soft pixels (box, 0.3), 5
integer nearest. Est. 0.1-0.3 ms.

LIVE CHECKS (scaler): SC1 compiles; SC2 Amount 0 / enabled 0 / mix 0 / Panic -> **0**; SC3 parity vs `reference`
(clip paused, grid source Pixelsize 8) for nearest / sharp / epx / diag: within (2/255) >= 0.999; SC4 Source TOP
(a 270 x 480 Constant/ramp TOP) with Fit integer -> borders 0, parity with `reference(src=...)`; SC5 presets full
state; SC6 cost, fps.

Verified live (scaler, scratch, 27 Oct 2026, 31550): SC1 clean; SC2 **0 / 0 / 0 / 0**; SC3 grid source Pixelsize 8
(135 x 240 -> 8x exactly): nearest / sharp / EPX **max 0.0**, diag within **1.0** (max 0.0020); SC4 Source TOP = a 97 x
173 Noise TOP: sharp + stretch (11.13 x 11.10) within **1.0**, diag + integer (11x, rows 0-7 / 1912-1919 transparent
0.0) within **1.0**; SC5 presets 1-5 full state; SC6 cost (median / p90) 0.70-0.86 / 1.46-2.49 ms (low + fx; grid
source), project 59.79 fps.

### `stitch` (TC-27, lane D 27 Oct): ops `low`, `fx`, `out_sel`
Digital embroidery / cross-stitch. `low` = pixelart's virtual-pixel pass (same shader text + uniforms: the two
modules share it; one thread colour per cell, default palette Sweetie 16, box sample). `fx`: Aida-like fabric
(Fabric colour, Weave ridges, Holes at the cell corners) and per cell a stitch: cross (\ under /), half (/), satin
(Strands parallel diagonal strands); threads are capsules Thread wide with cylinder shading, Twist ridges along the
strand, Gloss, a drop Shadow on the cloth, per-cell Jitter of the stitch ends; cells within Skip of the fabric colour
stay bare cloth. Mirror: `fx_retro_stitch_logic.render(img, cells, ...)` (feed the live `low` texels). Presets 1
sampler, 2 fine cross, 3 half stitch, 4 satin patch (pico-8), 5 dark denim. Est. 0.4-0.8 ms.

LIVE CHECKS (stitch): ST1 compiles; ST2 passthrough **0**; ST3 parity vs `render(in1, low texels, pars)` (clip paused)
within (3/255) >= 0.99 for cross, half, satin; ST4 presets full state; ST5 cost, fps.

Verified live (stitch, scratch, 27 Oct 2026, 31550): ST1 clean; ST2 **0 / 0 / 0 / 0**; ST3 parity vs `render(in1, live
low texels 60 x 107, pars)` cross / half / satin within (3/255) **1.0** (max 0.0020); ST4 presets 1-5 full state; ST5
cost (median / p90) 1.11-1.45 / 2.14-2.99 ms, project 59.91 fps (fine cross). Capture (fine cross, 10 px cells):
`output/project1_lab_FX_retro_stitch1_out1_2026-10-26T23-53-51-871Z.png`.

### `ps1` (7C-07, lane D 27 Oct): ops `fx`, `out_sel` + `ps1_mat()` for meshes
Rack module (any picture, one compute pass): Wobble (triangle lattice Wobblesize px whose vertices jump up to Wobble
px Wobblerate times a second; the picture is warped piecewise-affine across it = vertex-snap / affine swim on 2D
content) -> low-res frame buffer (Downscale px per virtual pixel, nearest, no AA) -> Bits per channel (5 = 15-bit)
after adding the PlayStation GPU 4x4 dither table in 8-bit units x Ditheramt (psx-spx table; or Bayer 4x4 / none),
expanded back to full range. Mirror: `fx_retro_ps1_logic.py`. Presets 1 psx, 2 swimmy, 3 saturn (no dither), 4
crunchy (4-bit). Est. 0.2-0.4 ms.
`ps1_mat(comp, name, snap=(320, 240), amount, tex)` (builder function, TD side) makes a GLSL MAT for real meshes:
vertex snap after the projection divide (Snap grid in virtual screen px, amount 0..1), `noperspective` UVs (affine
texture mapping), flat per-vertex light, nearest texture (sampler0 filter nearest). Render its Render TOP small (e.g.
320 x 240 / 270 x 480) and put the rack's ps1 module after it.

LIVE CHECKS (ps1): PS0 **MAT probe first** (scratch): `ps1_mat` on a Box SOP Geometry COMP + camera + Render TOP:
the MAT compiles (errors none, `noperspective` accepted by 31550 / MoltenVK), a moving camera shows the snapped
vertices (Snap 64 x 48 -> vertex x / y on the grid in a readback) and affine UV swim; PS1 rack: compiles; PS2
passthrough **0**; PS3 parity vs `reference` (clip paused, wobble 0 and wobble 6 at a fixed epoch: Wobblerate 0)
within (2/255) >= 0.999; PS4 presets full state; PS5 cost, fps.

Verified live (ps1, scratch, 27 Oct 2026, 31550): PS0 MAT probe: `ps1_mat` on a rotated Box (Geometry COMP + camera,
Render TOP 320 x 240): vertex + pixel shader "Compiled Successfully", linked, `noperspective` + `flat` varyings accepted
by 31550 / MoltenVK; Snap 32 x 24 (10 px cells) puts the silhouette bounds on the grid (x 90-240, y 50-190) vs 88-241
/ 47-186 unsnapped; a missing sampler gave "Uniform 'sTex' is unassigned" -> `ps1_mat` now binds a 1x1 white
Constant when no texture is given (warning gone). Capture `output/project1_ps1_probe_render1_2026-10-26T23-57-11-633Z.png`.
Rack module: PS1 clean; PS2 **0 / 0 / 0 / 0**; PS3 psx defaults within **1.0** (max 0.0019), Wobble 6 / 160 px +
Bayer + 4-bit within **0.99999** (28 px of 2.07 M on float32 floor edges); PS4 presets 1-4 full state; PS5 cost
(median / p90) 0.42-0.51 / 0.88-1.44 ms, project 59.9 fps.

### `retroscreen` (AV-36, FX0 row 59; lane D tail): ops `fx`, `out_sel`
Console / computer framing in one pass: the picture fitted (Fill fit / crop) into a Screen rectangle (full / 4:3 /
16:9 / 1:1 / 3:4, Margin) on a virtual grid (Pixelsize, Pixelaspect, nearest) inside a Border colour; raster bars
(Bars, Barheight, Barspeed cycles/s, Barhue + Barspread per bar; in the border / behind dark screen pixels / over
everything), interlace Flicker (odd / even virtual lines dim on alternate frames), Shake (px, re-rolled Shakerate / s;
bind it to a hit CHOP), Fade to black / white. Mirror `fx_retro_retroscreen_logic.py`. Presets 1 c64 frame, 2 amiga
copper, 3 arcade 3:4 (crop, flicker), 4 demo bars (behind), 5 hit shake. Est. 0.1-0.3 ms.
LIVE CHECKS (retroscreen): compiles; passthrough **0**; parity (clip paused, Barspeed 0, Shake 0, Flicker 0) within
(2/255) >= 0.999 for presets 1-4 geometry; presets full state; cost, fps.
Verified live (retroscreen, scratch, 27 Oct 2026, 31550): compiles; presets 1-4 parity (Barspeed / Shake / Flicker
0) within **1.0** (max <= 0.002; arcade 3:4 bit-exact); pass_seq **0 / 0 / 0 / 0**; presets 1-5 full state; cost
(median / p90) 0.49-0.80 / 0.79-1.40 ms; project 59.88 fps.

### `cycle` (AV-37 palette cycling, FX0 row 59; lane D tail): ops `pal`, `fx`, `out_sel`
Mark Ferrari style colour cycling on any picture, one stateless pass: index = luma / hue / saturation (Contrast,
Offset) x Indices; up to 4 index ranges (R1-R4 start / end as shares, speed in indices per second, sign = direction)
rotate (the shift is computed in the uniform expression: speed x absTime wrapped by the range length); Blend mixes
the two ramp steps a fractional shift falls between (wrapping inside its range); Ramp fire / water / rainbow / grey /
sunset or the rack palette bank (Machine). Mirror `fx_retro_cycle_logic.py` (analytic ramps; Machine by
colours-in-palette). Presets 1 lava, 2 waterfall (range 0.3-1, backwards), 3 rainbow road (hue, hard steps), 4 two
zones, 5 pico cycle (Machine pico-8). Est. 0.1-0.2 ms.
LIVE CHECKS (cycle): compiles; passthrough **0**; parity with the live shift uniforms read in the dump exec
(`uS0..3.z`) within (2/255) >= 0.999 for presets 1-4; preset 5: every pixel a pico-8 entry; presets full state; cost.
Verified live (cycle, scratch, 27 Oct 2026, 31550): compiles; parity (speeds 0, shift uniforms read 0) lava **1.0**,
waterfall **1.0**, two zones **0.99999**, rainbow road (hue, 64 hard steps) **0.9964** (hue floor boundaries of 8-bit
colours, float32 vs float64; max 0.095); pico cycle: outside_palette **0**, 16 colours; pass_seq **0 / 0 / 0 / 0**;
presets 1-5 full state; cost 0.52-0.61 / 1.06-1.39 ms; project 59.91 fps.

### `halftone` (FX0 FX_retro row; lane D tail): ops `fx`, `out_sel`
Print screens, adapted from td-port `halftone/halftone.frag` (the StageLab FFGL Halftone port, same owner): Mode mono /
RGB (additive) / CMYK (C 15, M 75, Y 0, K 45 deg + Angle), Shape round / square / line / diamond, Sampling cell
centre (true dots: each dot's size from the picture at its cell centre) or per pixel (the td-port threshold screen),
Cellsize, Softness, Gamma, dot jitter (Randomness, lowbias32 hash), Paper / Ink colours. Compute, no fwidth (AA = one
output pixel in cell units). Mirror `fx_retro_halftone_logic.py`. Presets 1 cmyk print, 2 newspaper (mono 45 deg),
3 pop art (red ink on yellow), 4 rgb screen (diamonds), 5 line engraving (per pixel lines). Est. 0.2-0.5 ms.
LIVE CHECKS (halftone): compiles; passthrough **0**; parity for presets 1-5 within (3/255) >= 0.99; presets full
state; cost, fps.
Verified live (halftone, scratch, 27 Oct 2026, 31550): compiles; parity cmyk print **0.99938**, newspaper **0.99978**
(rotated cell-centre floors at tile edges, float32), pop art / rgb screen / line engraving **1.0**; pass_seq **0 / 0 /
0 / 0**; presets 1-5 full state; cost 0.56-0.78 / 1.20-2.40 ms; project 60.5 fps. Capture (cmyk print)
`output/project1_lab_FX_retro_halftone1_out1_2026-10-27T00-47-56-554Z.png`.

## LIVE CHECKS (expected numbers; ~15 min per module on one lane)
**Setup and reads.** Rack built, lane registered. Each check is two execs with the checks file:
`ns = dict(globals()); exec(open('<repo>/builders/fx_retro_checks.py').read(), ns)`. Exec 1 runs
`ns['setup'](c, '<id>')`, which solos the slot, resets the module's pars, applies the check's pars, sets the Input and
pauses the clip. Exec 2 runs `ns['check'](c, '<id>')` at least `read_after_s` later and returns `pass` and numbers.
All numbers are at 1080x1920. TD numpyArray rows are bottom-first (the checks handle this).

| # | Check | Expected |
|---|---|---|
| R1 | Build on b2: `td_errors` on FX_retro, recurse | 0 errors. Every compute DAT compiles (glslc passed offline; TD's own header is the check). If `smooth` / `sample` / `patch` appear as names, they are reserved words (fixed offline) |
| R2 | Logic DATs at runtime: `c.op('fx_retro_logic').module.PM.__name__`, `.FONTDATA` | the palette_map_logic / fx_retro_font8x8 DAT modules: **the DAT import hook resolves the sibling DATs**. If not, the `op(...)` fallback in the file must work. Record which (LEARNINGS) |
| R3 | Shared data | `pal_bank.numRows` 591, `pal_top` 590 x 6, `bn_top` 64 x 64, 4096 distinct `bn_table` values in (0, 1). After an edit to `pal_custom`, pal_bank recooks once |
| R4 | Passthrough: P0 / D0 / G0 / T0 / S0 (Amount 0), slot enabled 0, mix 0, Panic | `max_diff` 0.0 each; `out_sel.par.index` 0 |
| P1 | dmg, Pixelsize 4, box | `outside_palette` 0, `blocks_not_uniform` 0, `agree` (numpy OKLab nearest of the 4x4 means) >= 0.995 |
| P2 | nes, aspect 8/7 -> 5 x 4 px blocks | outside 0, blocks 0, `unique` <= 55, agree >= 0.995 |
| P3 | spectrum (auto = cell) | `cells_bad` 0 (every 32x32 px cell has <= 2 colours from one half); `ref_cells_agree_of_50` >= 48 (`cell_pair` on the block means) |
| P4 | amiga12, Pixelsize 2 | `not_mult_17` 0, blocks 0 |
| P5 | amigaham, Pixelsize 3 (360 x 640 virtual) | `ham_violations` 0, `ham_ref_agree` >= 0.98 (`ham_row` on 6 rows) |
| P6 | pico8 + bayer8 on the test ramp | outside 0, `agree` >= 0.99 (palette_map's pick rule with Bayer thresholds) |
| D1 | bayer8, luma, Levels 2, ramp | `values` [0, 255], `agree` with `floor(v + bayer)` >= 0.999 |
| D2 | blue, rgb, Levels 4, ramp | values within {0, 85, 170, 255}; `tile_mean_err_max` (64 px tiles) <= 0.02 |
| D3 | fs, luma, Levels 2, Tile 32, serpentine, ramp | values [0, 255]; `tile_mean_err_max` <= 0.03; `tile0_agree` vs `diffuse()` >= 0.9 (float32 vs float64 flips propagate) |
| D4 | gbcam, dmg, Pixelsize 8 | outside 0, 8x8 blocks uniform |
| G1 | ascii mono white on black, 12x12 cells (90 x 160) | colours within {black, white}; `cells_match` (expected glyph bitmap from the numpy 8x8 bilinear cell mean) >= 0.98 |
| G2 | textmode, cga16, 8x16 cells | `outside_palette` 0, `cells_over_2_colours` 0 |
| G3 | matrix (call check twice, 0.5 s apart) | `lit_share` 0.005-0.6 (defaults ~0.016), `px_changed` (share of pixels that changed) > 0.005 |
| T1 | image 40 x 59 | `outside_8` 0, `cells_over_2_colours` 0 (cells = ceil boundaries of 27 x 32.54 px) |
| T2 | page 40 x 25, Loadtime 0 | `codes` 1000, `header_ok` True (first 20 chars of the header equal `header_text`); capture: header, double-height banner, fastext row 24, picture rows 6-23 |
| T3 | Reload with Loadtime 1.5 (page mode); capture at ~0.3 s | rows >= 5 still black; all rows shown after 1.5 s |
| S1 | lcd image, Dotsize 8 (135 x 240 state), Levels 4, after 1 s | `state_levels_ok` >= 0.999, `state_size` [135, 240]. Response: set Brightness 0.5 and read state about 0.1 s later. The values should have moved by about `1 - exp(-0.1 / Rise)` = 0.71 of the step (+-0.15, frame quantised) |
| S2 | flipdot, Dotsize 18 (60 x 107), after 1.5 s | `state_agree` (luma of the 2x2 box > 0.5) >= 0.995, `flipping` 0. Then toggle Invert and read at ~0.3 s (Sweep 0.6 columns, Fliptime 0.12): left third about 100 % flipped, right third about 0 % |
| S3 | nixie clock 8 x 1 | `digits` = codes - 1 (e.g. `10:03:40` -> [1, 0, 10, 0, 3, 10, 4, 0]; ` 6:30:45` -> [-1, 6, 10, ...]); cell layout 135 x 256.5 px, y0 831.75 |
| S4 | splitflap 8 x 6, blank board; then `ns['settext'](c)` (HELLO, WORLD) | at ~0.25 s `moving` > 0; at >= 1.5 s `cells_on_target` 1.0, `moving` 0 (WORLD: 23 flaps x 2 frames = ~0.77 s) |
| S5 | eink, Dotsize 3 (360 x 640), after 1 s | `displayed_eq_target` >= 0.95. Then `ns['eink_flash'](c)` and, 2 s later, read `c.storage['fx_retro_check']['reads']`: mean at 0.15 s about (ink + paper) - the settled mean = 0.96 - settled (inverted); at 0.45 s about the ink level (0.12-0.13); at 0.75 s about paper (0.84); at 1.5 s back to the settled mean +-0.02 |
| S6 | vfd, Dotsize 10 (108 x 192), Threshold 0.45 | `state_agree` >= 0.995 |
| C1 | Cost per module: `ns['cost'](c)` then, 3 s later, `ns['cost_result'](c)` with the pane elsewhere and the test clip excluded | Estimates: palette list 0.3-0.8 ms, cell (Spectrum) ~0.5, ham 1-3; dither ordered ~0.3, diffusion 1-3; glyph 0.3-0.5; teletext ~0.3; smalldisplay 0.3-1.5 (nixie with cathodes the most). Project 60 fps with one module on. Over 3 ms: record it, and lower the default (ham Pixelsize, diffusion Tile, nixie Cathodes 0) |
| C2 | Presets: zkit Recall on each module | pars exactly as `PRESETS` (menus by index) |

Facts these modules take from other live work: compute `textureSize(samplerBuffer)` and float texture buffers
(T-110), `dispatchsizex/y` with `autodispatchsize` off (T-114), in-place `readwrite` + `clearoutputs off` (T-110 (5)),
`numcolorbufs` 2 with `TDImageLoadOutput(1, ...)` (FX6 5a read buffers 1-2 through Render Select; the in-shader load of
buffer 1 is new), and the Parameter Execute pulse pattern (fx_destroy).

Facts that are new here, so record them:
- The DAT `import` of sibling module DATs (R2).
- A custom Tick par on a Script CHOP feeding a texture buffer.
- `texelFetch(samplerBuffer)` from a Script CHOP's 1000-sample channel.

Anything that fails: fix the builder, add a LEARNINGS entry (T-nn), rerun the offline tests.

## Verified live
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
26 Oct 2026, TD 2025.31550. Built module by module on build TD **b2** (`/project1/lab/FX_retro`), checks run there,
transfer `output/transfer/FX_retro.tox` saved after each module, brought home into the **main** TD after palette +
dither and again at the end (`/project1/lab/FX_retro`, 1503 ops, errors 0, layout check ok, parked,
`JazibTD_home.398.toe`); in main P1 / D3 / G1 / T2 / S1 re-run: all pass, main 60 fps with S1 soloed. b2 checkpoints
`output/checkpoints_b2/FX_retro/`. Captures `output/project1_lab_FX_retro_<m>1_out1_2026-10-26T*.png` (c64 bayer4,
atkinson 1-bit, ascii dense colour, teletext page, nixie clock) and b2 window captures `output/window_*2026-10-26T16-3*`
.. `T17-05*`. Passthrough (Amount 0, slot enabled 0, mix 0, Panic) = max diff **0** for every module.
Costs: GPU ms of the module's own TOPs (median over 40-50 cooked frames, clip playing), with 6 TDs on one GPU (the same
setting reads 2-3x apart between runs); every module soloed kept b2 at 60 fps.

| Check | Live (31550) |
|---|---|
| R1 | 0 errors / warnings (all compute shaders compile) |
| R2 | `PM` = the `palette_map_logic` DAT module, `FONTDATA` = the font DAT module: the DAT import hook resolves sibling DATs |
| R3 | pal_bank 591 rows, pal_top 590 x 6, bn_top 64 x 64 (after T-141 (4); 64 x 63 before), 4096 distinct values = table (max err 5e-9); font_top 428 x 2 = table exactly |
| P0-P6 | P1 outside 0, blocks 0, agree 1.0; P2 unique 18, agree 1.0; P3 cells_bad 0, ref 50 / 50; P4 not_mult_17 0; P5 ham_violations 0, ham_ref_agree 1.0 (old and new ham shader); P6 agree 1.0 |
| D0-D4 | D1 values [0, 255], agree 1.0; D2 values {0, 85, 170, 255}, tile err 0.0011; D3 values [0, 255], tile err 0.012, tile0_agree 1.0 (old and new diffusion pass); D4 outside 0, 8x8 uniform |
| G0-G3 | G1 2 colours, cells_match 1.0; G2 outside 0, cells > 2 colours 0; G3 lit 0.015-0.018, px_changed 0.027-0.032 |
| T0-T3 | T1 outside_8 0, cells > 2 colours 0; T2 codes 1000, header `P100 TELETEXT 100 Mon 26 Oct  9:53/00 PM` ok, capture shows header / dh banner / picture rows 7-23 / Fastext row 24; T3 at 0.28 s rows 0-4 lit (rows >= 5 black), at 1.68 s all 25 |
| S0-S6 | S1 state 135 x 240, levels ok 1.0, response 0.767 of the step at 0.117 s (expected 1 - exp(-0.117 / 0.08) = 0.767); S2 60 x 107, agree 1.0, flipping 0, Invert sweep at 0.30 s: left third 100 %, middle 35 %, right 0 %; S3 digits = codes - 1, 8 tubes, cells 135 x 256.5, y0 831.75; S4 at 0.23 s 8 cells moving, at 1.7 s on target 1.0, moving 0; S5 eq target 1.0, flash trace (default colours ink 0.111 / paper 0.416 means): inverted 0.271 (= 0.111 + 0.416 - 0.256 settled), black 0.111, white 0.416, back to 0.256 by 1.23 s; S6 agree 1.0 |
| C1 | palette list 0.23-0.66, cell (Spectrum) 0.65, amiga12 0.12, ham Pixelsize 4 2.2 (3: 4.3-8.8); dither ordered 0.07-0.22, fs Tile 16 1.8-2.4, atkinson Pixelsize 2 2.0-3.2 (Pixelsize 1 4.0), jarvis 4.6-7.5, fs + pico8 palette Tile 16 ~3.6; glyph ascii 0.29-0.45, textmode 0.87, matrix 0.43, 6 px cells 0.7; teletext 0.01-0.3 + codes 0.66 CPU once a second; smalldisplay 0.01-0.1 per op (T-141 (6): timer may under-read with arrays) |
| C2 | zkit Recall of all 27 presets: every par as PRESETS (menus by index) |

Over 3 ms (recorded, defaults lowered where it helps): ham at Pixelsize <= 3, error diffusion with the 12-tap kernels
(jarvis / stucki) or Pixelsize 1 atkinson, fs at Tile 32. Ordered dither, palette list / cell, glyph, teletext and the
small displays sit well under 1 ms.

## Sources
- font8x8 (Daniel Hepper, public domain; from the Marcel Sondaar and IBM public-domain VGA fonts):
  https://github.com/dhepper/font8x8. basic, block and hiragana sets were parsed into `fx_retro_font8x8.py`.
- Blue noise: Ulichney's void-and-cluster, an own implementation (`void_and_cluster`; sigma 1.5, toroidal). The
  offline test checks its low-frequency energy share is under 1e-3 (white noise is about 0.05).
- Palettes: FX2 AV-34 tables and palette_map_logic's Lospec presets. Values marked [M] in `MACHINES` come from memory.
- Teletext: EN 300 706 level-1 attribute rules (spacing attributes, 2x3 sixels, double height) and SAA5050 character
  rounding, as described in FX2 AV-38. The font is not the SAA5050 ROM.
- td-port `ascii` (JetBrains Mono MSDF atlas) was read. It was not reused: an 8x8 bitmap font from a table texture
  needs no Script TOP / Text TOP (T-76) and no atlas (first built as a GLSL const array: ~3 ms per pass, T-141 (1)).

## Not done / open
- `retroscreen` (AV-36), `cycle` (AV-37) and `halftone`: built in the lane D tail (27 Oct, sections above).
- Cell mode with a large palette costs grows as n^2. ega64 in cell mode is roughly 32 pairs x 128 distances per
  thread; measure it before using it live.
- C64 multicolour (4x8 cells, 4 colours) is not covered; cell mode is the hires 2-colour clash only.
- Diffusion seams show at tile edges at high zoom (accepted in AV-35). There are no blue-noise-jittered tiles.
- Faster diffusion for the 12-tap kernels: a per-row register window instead of per-tap buffer read-modify-writes.
- Fair 60 fps / ms numbers need a quiet machine (today: 6 TDs share the GPU).
- Teletext hold graphics (`{hold}`) takes a cell but holds nothing. There is no Fastext interaction.
- Urdu is not in the font. Subtitle lines are wrapped by characters, not by shaping.

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (JazibTD_home.770).
