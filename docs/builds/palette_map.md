# palette_map - `/project1/lab/FX_palette_map` (TD 2025.31550, 26 Oct 2026)

Maps every pixel to the nearest colour of a palette (OKLab or sRGB distance), with ordered / noise dither, blend
and preserve-luma. Our own clean-room build of the recipe in `docs/research/AZ_closest_color_palette.md` section 4
(idea credit: "Closest Color Palette TOX" by percolated, derivative.ca asset 69695; never downloaded or loaded).

## Files
- `builders/palette_map.py` - builder, `build(parent_path='/project1/lab', panel=True)`, idempotent, T-70 safe:
  `ns = dict(globals()); exec(open('<repo>/builders/palette_map.py').read(), ns); ns['build']('/project1/lab')`
- `builders/palette_map_logic.py` - pure logic: presets, hex parsing, file readers (.txt .hex .json .gpl .pal .ase),
  OKLab maths, Bayer matrix, a Python model of the shader's pick; copied into the COMP as `palette_map_logic`.
- `test/test_palette_map.py` - 20 offline tests: `python3 -I -m unittest discover -s test -p 'test_palette_map.py'`.

## How it works
`in1` / stored clip (`media/webcam/webcam_ref_5s.mp4`) / test ramp -> `src` -> **`map`** (ONE compute GLSL pass,
rgba8fixed, source size) -> `out1` (output only).
Palette: `palette_custom` (Table DAT, one hex per row, `#` optional, `#RGB` ok) -> `palette_active` (Script DAT: the
preset, the custom table or the file, as rows `hex r g b L A B`; OKLab computed once per palette change) -> `pal_chop`
(DAT to CHOP, channel per column) -> `pal_top` (CHOP to TOP, mono 32-bit float, width = colours, one row per channel:
row 0 r .. row 5 OKLab b, probed live: texture row 0 = CHOP channel 0) -> `map` input 2. Input 3 = `in2` (dither noise
image, e.g. blue noise) when wired, else a blank and the shader uses IGN.
Shader: unpremultiply, convert to OKLab, loop over N colours keeping best + second best (L weighted by
`Lightnessweight`), dither: t = d1/(d1+d2) (0 on the best colour, 0.5 midway), second colour wins when
t x `Ditheramount` > threshold (Bayer 8x8 / interleaved gradient noise / in2 red channel); preserve luma moves the chosen
colour's OKLab L toward the source; blend with the source; premultiply out.
`par_exec` re-reads the palette on Palette / File change and on `Load`; `Copytotable` copies the active palette into
`palette_custom` and switches to Custom (edit a preset). Parameter Execute callbacks run on the next frame.

## Pars
- **Palette** (zkit knobs): Palette (Custom table, From file, 20 presets), Colour space (OKLab / sRGB), Blend, Lightness
  weight, Preserve luma, Dither (Off / Bayer 8x8 / Noise IGN / Noise input in2), Dither amount (1 = correct mix, more
  = noisier; no clamp), Animate dither (offset per frame, 64-frame cycle), Copy to table, Load file.
- **Setup**: File (palette file), Count (read-only: colours in use, 0 = empty palette -> black), Source (auto / in1 /
  clip / test ramp), Clipfile.
- **Zkit**: Opencontrols opens the panel (`controls` + `controls_window`).
No caps: any palette size (cost grows with N), dither amount open-ended.

## Presets (hex fetched from Lospec's JSON, `https://lospec.com/palette-list/<slug>.json`, 26 Oct 2026)
PICO-8 (16), Sweetie 16, Endesga 32 (ENDESGA), Resurrect 64 (Kerrie Lake), Apollo (46, AdamCYounis), AAP-64 (Adigun A.
Polack), DawnBringer 16, DawnBringer 32, SLSO8 (Luis Miguel Maldonado), Oil 6, Twilight 5 (Star), Nyx8, Lost Century
(SurrealEmber), Game Boy bgb (4), 2bit Demichrome (Space Sandwich), CGA 0 high (4), 1bit Monitor Glow (Polyducks),
Grayscale 16 (SZIEBERTH Adam), plus Solarized (Ethan Schoonover, MIT, github.com/altercation/solarized README) and
Black & white. Lospec palettes are shared for free use; credit the authors named above.

## Verified live (26 Oct, 31550, M1 Max, webcam_ref_5s.mp4 1920x1080 unless noted)
| Check | Result |
|---|---|
| pal_top | Pico-8: 16 x 6 r32float, values = palette_active (e.g. 1D2B53 L 0.29973 a -0.00353 b -0.07477, negatives kept) |
| every out pixel in the palette (dither off) | OKLab 100 %, sRGB 100 % (11 distinct colours used of 16) |
| shader = Python reference (`pick`) | 400 / 400 random pixels, OKLab and sRGB |
| OKLab vs sRGB | 16.7 % of pixels pick a different colour |
| Bayer, B&W on the grey ramp | white share per 8 columns 0.234 / 0.422 / 0.594 / 0.797 / 0.922 vs source OKLab L 0.239 / 0.420 / 0.600 / 0.802 / 0.919 |
| IGN, B&W ramp | white share per column 0.245 .. 0.905 vs L 0.244 .. 0.904; output strictly 0/255 |
| Dither amount 0 | hard quantise (no mix) |
| Noise input path | forced on with a blank texture: threshold 0 -> second colour everywhere it is not exact (texture read) |
| Blend 0 / 0.5 | out == src exactly / max diff 0.002 from the src-out midpoint |
| Preserve luma 1 | mean OKLab dL 0.0008 vs 0.0444 at 0 |
| premultiplied alpha | src (0.4, 0.051, 0.051, 0.502) -> AB5236 x 0.502 = (0.337, 0.161, 0.106, 0.502) exactly |
| Files | .gpl 3 colours, .ase 2 RGB (CMYK skipped), Lospec .json 6, File change re-reads, missing file -> Count 0 + warning |
| Custom table | edits re-cook at once; `#C4E` -> CC44EE; bad cell skipped with a warning |
| Copy to table | Pico-8 -> 16 rows in palette_custom, Palette -> Custom |
| Perf | map 0.17 ms CPU, 1.34 ms GPU (Pico-8, Bayer); 2.39 ms GPU at 64 colours (Resurrect 64, Bayer); project 60.06 fps with map cooking every frame |
| td_errors / layout check | clean / ok (no intruders, unboxed, box overlaps) |

## Shared palette (W1-B, 27 Oct)
`palette_map_logic.py` also holds the shared palette convention every other coloured element uses (16-stop
`uniform vec4 uPal[16]` + `uPalCtl`, `builders/glsl/px_palette.glsl`, presets incl. these 20, drives, colour source):
`docs/builds/palette_convention.md`. Appended only; FX_palette_map's functions and behaviour are unchanged.

## Left / open
- No-palette-extraction (k-means from an image) yet; tints per entry (spec open question 2) not built.
- .ase read only tested with our own writer's bytes (no real Adobe file); PNG palette images not read.
- Over ~256 colours a precomputed 3D LUT would beat the per-pixel loop (not built).
