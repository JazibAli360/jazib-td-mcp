# AZ - Closest Color Palette TOX (percolated, asset 69695) + recipe for our own "palette map" COMP, 26 Oct 2026

Status: **PARTIAL. The .tox could not be downloaded, so nothing was inspected.** Internals below are UNVERIFIED inference;
the recipe in section 4 does not depend on the tox. Nothing was loaded into TD or run. `research_src/closestpalette_69695/` holds
only `NOT_DOWNLOADED.txt` and the 403 response headers.

## 1. What was established (cited)
- Page `https://derivative.ca/community-post/asset/closest-color-palette-tox/69695` (readable via WebFetch): "Closest Color Palette TOX",
  author **percolated**, posted 26 Jun 2024, tags free / tox / palette / filter, 717 reads, 0 comments.
- Description: takes a **texture** and a **color palette supplied as a CHOP**, replaces each image colour with the closest palette
  colour. Author warns of "performance drops if the palette gets too big". Asks for Patreon support (`patreon.com/percolated`).
- File: `ClosestPalette.tox`, **1.65 KB** (so almost certainly one GLSL TOP + a CHOP-to-TOP / Script-free wiring, a handful of ops).
- NOT stated: TD build, licence, parameters, Mac/Windows status, metric, dither. No GitHub, forum or video link exists on the page;
  a web search found no repo. 0 comments, so no community reports on Mac.
- Download link `/file/479043/download?token=...` returns **403 from the AWS load balancer to curl** (same block as T-asset pages
  in AO/AV). Not bypassed (no browser-UA retry). **User action: download in a browser into `research_src/closestpalette_69695/`**
  if the original is wanted; then audit per the checklist in `AO_colorpicker_widget.md`.

## 2. How it almost certainly works (UNVERIFIED)
A 1.65 KB tox cannot hold more than ~3-6 ops. Most likely: palette CHOP (one channel set r,g,b, N samples) -> CHOP to TOP (Nx1 or 1xN)
-> GLSL TOP input 2; the shader loops `for i<N: texelFetch(palette,i)`, keeps the minimum **RGB Euclidean distance**, outputs that colour.
"Performance drops if palette gets too big" matches an O(pixels x N) per-pixel loop with no acceleration. No dither is implied
(none mentioned). Palette-size limit: no hard cap, only the loop cost; a CHOP's sample count / TOP width (<= 16384) is the ceiling.

## 3. Audit
Cannot be done on the binary. Page-level: free, tiny, no links to external code, no installer. Risk is low by size, but unverified.
Verdict: **do not adopt or depend on it.** Idea is trivial; our own COMP (below) is better matched (OKLab, dither, blend, hex input).
Mac note: its shader (if multi-pass) could tear per T-46; ours is single-pass compute-style, which is the clean path.

## 4. Recipe: our own self-contained `palette_map` COMP
Out TOP only, no Python callbacks beyond a small par-menu extension, no network, no eval of external text.

### Network (inside the COMP, L-to-R, titled boxes)
`in1` (In TOP) -> `glsl_map` (GLSL TOP, **compute mode**, one pass) -> `out1` (Out TOP).
Palette: `palette_hex` (Table DAT, one hex per row, e.g. `#CA47E9`) -> `pal_oklab` (Script-free: DAT to CHOP is awkward for hex,
so instead a small **Text DAT callback / Execute-free approach**: a DAT Execute on `palette_hex` change runs a ~10-line parser that writes
`pal_rgb` (Table DAT of r g b floats 0-1)) -> `Table DAT -> DAT to CHOP` (channels r,g,b; one sample per row) -> `CHOP to TOP`
(`pal_top`, 1xN, **32-bit float RGBA**, Nearest/no filter) -> GLSL input 2. If you want zero Python: type floats not hex into the table
and let the Palette menu callback do the hex conversion on load only.
Convert to OKLab **in the shader** (N is small), or precompute once into `pal_top` (preferred when N>64: store L,a,b in rgb of a
second 1xN float TOP, avoids N conversions per pixel).

### Shader maths (single pass)
sRGB->linear: `c<=0.04045 ? c/12.92 : pow((c+0.055)/1.055,2.4)`.
linear -> LMS: `l=0.4122214708r+0.5363325363g+0.0514459929b; m=0.2119034982r+0.6806995451g+0.1073969566b; s=0.0883024619r+0.2817188376g+0.6299787005b`
-> cube root `l_=cbrt(l)`, etc. -> OKLab:
`L=0.2104542553l_+0.7936177850m_-0.0040720468s_; a=1.9779984951l_-2.4285922050m_+0.4505937099s_; b=0.0259040371l_+0.7827717662m_-0.8086757660s_`.
Distance: `d = dot(Δ,Δ)` with `Δ=(wL*ΔL, Δa, Δb)`; `wL` par (default 1.0; lower to preserve hue over lightness).
Loop: `for(int i=0;i<uCount;i++){ vec3 p=texelFetch(sTD2DInputs[1],ivec2(i,0),0).rgb; /*OKLab*/ float d=...; if(d<best){best=d;idx=i;} }`.
Dither (ordered, cheap, deterministic): compute best and **second-best** palette colour, `t = d1/(d1+d2)` (0 = on best, 0.5 = midway);
pick second if `t > threshold(x,y)` where threshold = 8x8 Bayer matrix (const array in shader) or blue-noise from a 2nd/3rd TOP input
(preferred look, optional input; fall back to Bayer if unconnected). `Dither amount` par scales `t` (0 = hard quantise, 1 = full).
Output: `mix(src.rgb, chosen.rgb, uBlend)`, alpha = source alpha (keep premultiplied: divide by alpha before mapping, multiply after; see
overlay-alpha rule). Optional `Preserve luma` par: shift chosen colour's OKLab L toward source L by that amount (keeps shading, recolours hue).
Cost: pixels x N x ~12 flops; at 1080p and N<=16 trivially cheap; up to ~64 fine; hundreds will cost (the tox's warning).

### Custom pars (page "Palette")
- `Palette` (Menu): `Custom (table)` (the `palette_hex` Table DAT, user-editable), `From file`, and built-in presets filled into
  `palette_hex` by a short Text DAT on menu change (hex lists embedded in the COMP, no network): `Pico-8` (16), `Sweetie 16`,
  `Endesga 32`, `Resurrect 64`, `Apollo`, `Game Boy (4)`, `CGA`, `Black & white (2)`, `Solarized`. Palette names/values to be copied from
  Lospec (open, mostly CC0/free; cite source in the DAT comment); exact values not verified here.
- `File` (File par) + `Load` (Pulse): reads a local list of hex colours and fills `palette_hex`. Accepted: `.txt`/`.hex` (one hex per
  line, `#` optional, Lospec export style), `.json` (array of hex strings, or object whose values are hex strings), `.gpl` (GIMP palette),
  `.ase` (Adobe Swatch Exchange, binary: parse RGB-model swatches only; CMYK/Lab/gray skipped; best-effort, UNVERIFIED). Local read only.
- `Custom` (Table-edited), `Count` (read-only int, = table rows).
- `Blend` (float 0-1, default 1), `Lightnessweight` (0-2, default 1), `Preservelumaa` (0-1, default 0).
- `Dither` (Menu: Off / Bayer 8x8 / Blue noise input), `Ditheramount` (0-1, default 0.5).
- `Colourspace` (Menu: OKLab / sRGB) - OKLab default; sRGB for A/B comparison.
House rules: look COMPs' Colours pages are RGB floats: add a `Copy to Custom` pulse that writes the chosen palette into the host
look's Colours page only when the user asks; this COMP itself never writes outside itself.

### Mac / TD 31550 constraints
Compute-mode GLSL TOP, single pass, `uniform` count via `uTD` custom uniforms (`uCount`, `uBlend`, `uLw`, `uDither`) - no multi-pass
(T-46). Palette as 32-bit float TOP: confirm no 8-bit quantisation of float colours (fine for hex anyway). Rosetta speed UNVERIFIED.
Test plan: stored-clip input, 16-colour preset (Pico-8), window capture (td_screenshot), compare OKLab vs sRGB; dither on a gradient ramp.

## 5. Open questions
1. Does the user want the tox downloaded by hand to confirm the metric? (low value; recipe stands alone)
2. Tints as separate palette entries or generated at load (recommend generated, `Tints` int par)?
3. Which presets does the user want built in (list above is a guess)? Add palette extraction from an image as a later option?
