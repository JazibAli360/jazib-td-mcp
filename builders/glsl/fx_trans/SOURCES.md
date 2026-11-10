# SOURCES - gl-transitions vendored for FX_trans (G-TRANS)

Source: https://github.com/gl-transitions/gl-transitions (master, commit 0efa1651dfdbc0cdbd57f4cda55f12d8b3dbc0c5,
package `gl-transitions` 2.0.0), fetched 26 Oct 2026 as a zip into `research_src/gl_transitions/` (git-ignored).
Repo licence: MIT ("Copyright (c) 2017-present gl-transitions contributors"). Every file below carries its own
`// License: MIT` header and author line, kept unchanged. Files are byte-for-byte the upstream ones except
`CrossWarp.glsl`: the accented e in its author name ("Eke Peter") is written as a plain e (ASCII-only rule).
The code is not edited: `builders/fx_trans_logic.py wrap_gl()` prefixes the identifiers and turns the uniforms into
globals filled from the knobs K1..K10 when the shader is generated.

| File | Type id | Author | Licence | What |
|---|---|---|---|---|
| `Fade.glsl` | `fade` | gre | MIT | A linear crossfade between the two images |
| `FadeColor.glsl` | `fadecolor` | gre | MIT | A fade through a solid color, black by default |
| `DirectionalWipe.glsl` | `wipe` | gre | MIT | A soft-edged diagonal wipe |
| `CircleOpen.glsl` | `circleopen` | gre | MIT | A soft-edged circle opens from the center to reveal the incoming image |
| `ClockWipe.glsl` | `clock` | Fernando Kuteken | MIT | A wipe that sweeps around the center from a starting angle |
| `CrossWarp.glsl` | `crosswarp` | Eke Peter | MIT | The outgoing image zooms in while the incoming one zooms out into place |
| `CrossZoom.glsl` | `crosszoom` | rectalogic | MIT | A crossfade through a strong zoom blur |
| `Cube.glsl` | `cube` | gre | MIT | The two images are faces of a rotating 3D cube, with a floor reflection |
| `Swirl.glsl` | `swirl` | Sergey Kosarevsky | MIT | Both images swirl around the center while crossfading |
| `Pixelize.glsl` | `pixelize` | gre | MIT | Both images pixelate, crossfade, then sharpen again |
| `Morph.glsl` | `morph` | paniq | MIT | A crossfade in which each image is displaced by the other's colors |
| `GlitchMemories.glsl` | `glitchmem` | Gunnar Roth | MIT | A crossfade with glitchy, color-shifted blocks |
| `BurnThrough.glsl` | `burn` | liubailin2020@gmail.com | MIT | The outgoing image burns away in noisy, glowing patches |
| `FilmBurn.glsl` | `filmburn` | Anastasia Dunbar | MIT | Film-burn light leaks wash over the image and reveal the incoming one |
| `Ripple.glsl` | `ripple` | gre | MIT | Ripples spread from the center while crossfading |
| `Dreamy.glsl` | `dreamy` | mikolalysenko | MIT | A crossfade with a gentle wavy distortion |
| `Doorway.glsl` | `doorway` | gre | MIT | The outgoing image opens like double doors, with a floor reflection |
| `Kaleidoscope.glsl` | `kaleido` | nwoeanhinnogaehr | MIT | A crossfade through a spinning kaleidoscope |
| `DoomMelt.glsl` | `doommelt` | Zeh Fernando | MIT | The outgoing image melts down in uneven columns (Doom screen wipe) |
| `WindowSlices.glsl` | `slices` | gre | MIT | The incoming image appears through vertical slices that widen |
| `PolkaDotsCurtain.glsl` | `polka` | bobylito | MIT | The incoming image appears through growing polka dots |
| `Hexagonalize.glsl` | `hexagon` | Fernando Kuteken | MIT | Both images turn into hexagons, crossfade, then sharpen again |
| `DisplacementMap.glsl` | `displace` | Travis Fischer | MIT | A crossfade warped by a displacement map (FX_trans: the matte input) |
| `GlitchDisplace.glsl` | `glitchdisplace` | Matt DesLauriers | MIT | Blocks of the image are displaced in a glitch that flashes into the incoming one |
| `StripDatamoshGlitch.glsl` | `stripmosh` | bread | MIT | Torn strips, chroma shifts and scan noise drag the outgoing image into the incoming one |

**Wave 2 (lane C, 27 Oct 2026; FX7a SX-31 + SX-34), same commit, byte-for-byte except `LuminanceMelt.glsl` (an em
dash in a comment written as `-`, ASCII rule):**

| File | Type id | Author | Licence | What |
|---|---|---|---|---|
| `LuminanceMelt.glsl` | `lummelt` | 0gust1 (embedded simplex noise by "Ian McEwan, Ashima Arts.", MIT) | MIT | Array and textureless GLSL 2D simplex noise function. |
| `UndulatingBurnOut.glsl` | `burnout` | pthrasher | MIT | A circle with a wavy edge burns out from the center to reveal the incoming image |
| `GlowDissolve.glsl` | `glowdissolve` | hjm1fb | MIT | The incoming image spreads over the outgoing one with a hot, glowing edge |
| `PerlinDissolve.glsl` | `perlindissolve` | Rich Harris | MIT | The incoming image appears through blobs of Perlin noise |
| `NoiseDissolve.glsl` | `noisedissolve` | towrabbit | MIT | The incoming image appears pixel by pixel in random noise |
| `Overexposure.glsl` | `overexposure` | Ben Zhang | MIT | A crossfade through a washed-out, overexposed white |
| `EdgeGlow.glsl` | `edgeglow` | Woohyun Kim | MIT | Both images fade through black with their edges glowing |
| `LinearBlur.glsl` | `linearblur` | gre | MIT | A crossfade through a blur |
| `DirectionalWarp.glsl` | `dirwarp` | pschroen | MIT | A diagonal wipe with a warped, smeared edge |
| `TangentMotionBlur.glsl` | `tanblur` | chenkai | MIT | The outgoing image is flung away along a curve with motion blur |
| `Squeeze.glsl` | `squeeze` | gre | MIT | The outgoing image is squeezed into a line with color separation, revealing the incoming one |
| `FlyEye.glsl` | `flyeye` | gre | MIT | The image breaks into a fly's-eye grid of lenses with color separation |
| `Shatter.glsl` | `shatter` | lbl | MIT | The outgoing image shatters into fragments that fly away |
| `CrazyParametricFun.glsl` | `crazyfun` | mandubian | MIT | The outgoing image is pulled along a parametric curve into a psychedelic swirl |

Our own (no external code): `matte` (luma-matte wipe, `fx_trans_logic.MATTE`), `tvoff` (port of
`fx_analog_crt_logic.power_shape`, the FX_analog crtfault Power maths), `mosh` (FX_glitch `fx_glitch_moshcut.py` +
`fx_glitch_mosh.py` engine, built unchanged in a sub-COMP).

**Wave 3 (lane C2, 27 Oct 2026; FX7a SX-32 (2 of the signal-failure set), SX-33 + FX7c 7C-06 page / flip / 3D, SX-35
shape wipes), same commit, byte-for-byte except `Rolls.glsl` (the copyright sign written as `(c)`, ASCII rule).
`InvertedPageCurl.glsl` is **BSD 3-Clause** (Hewlett-Packard 2010, adapted by Sergey Kosarevsky): its full notice stays in
the file and in the COMP's `fx_trans_src` DAT (redistribution keeps the notice; no endorsement implied).**

| File | Type id | Author | Licence | What |
|---|---|---|---|---|
| `TvStatic.glsl` | `tvstatic` | Brandon Anzaldi | MIT | Cuts to full-screen TV static, then to the incoming image |
| `ColorPhase.glsl` | `colorphase` | gre | MIT | A crossfade in which each color channel changes at a different time |
| `BookFlip.glsl` | `bookflip` | hong | MIT | The outgoing image turns like a book page from right to left, revealing the incoming one |
| `InvertedPageCurl.glsl` | `pagecurl` | Hewlett-Packard | BSD 3 Clause | The outgoing image curls away like a page, revealing the incoming one |
| `Rolls.glsl` | `rolls` | Mark Craig | MIT | The outgoing image rolls away around a corner, revealing the incoming one |
| `HeartWipe.glsl` | `heart` | gre | MIT | A heart shape grows from the center to reveal the incoming image |
| `Pinwheel.glsl` | `pinwheel` | Mr Speaker | MIT | A spinning pinwheel reveals the incoming image |
| `LissajousTiles.glsl` | `lissajous` | Boundless | MIT | The image breaks into a grid of tiles that swirl along Lissajous curves, in a Scanimate style, and flip one by one to the incoming image before settling back |
| `GridFlip.glsl` | `gridflip` | TimDonselaar | MIT | The image splits into a grid of tiles that flip one by one to the incoming image |

Our own wave 3: `jigsaw` (FX7c 7C-29, clean-room from the Notch Jigsaw manual description: interlocking pieces with
an edge-hashed knob per inner edge, each piece flips A -> B at its own time; `fx_trans_logic.JIGSAW`, numpy mirror
`ref_jigsaw`).
