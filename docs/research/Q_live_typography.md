# Q: live kinetic typography and text-driven effects in TouchDesigner (EN + Urdu), research for PF26

Research only, 16 Oct 2026. Build in scope: **TouchDesigner 2025.31550** (Pro, macOS, Rosetta, M1 Max), vertical 1080x1920, output to Resolume Arena 7.23.2.
Nothing was built, generated, downloaded or installed, and no TD/app was touched. Every claim has a URL, a pointer to an existing file in this folder
(those files hold the live probes), or is marked **UNVERIFIED**. Where a result below is "own reasoning", it says so.
Not repeated here: the Text TOP Urdu probe (`A_td_2025_howto.md` §5, images `refs/A_td_howto/urdu_*.png`), the HyperFrames/HarfBuzz Urdu
pipeline (`hyperframes/LEARNINGS.md` U-01..U-07, H-20; `hyperframes/RESEARCH.md`), op/par tables (`ops/TOP.md`, `ops/SOP_MAT.md`, `ops/POP.md`).

**House rules that shape every recommendation here** (BRIEF.md §5, hyperframes CLAUDE.md rule 7, `names-words-intact`): a name or word is animated as one unit and is never
split, scrambled, partially shown or covered at rest; Urdu calligraphy comes only from the client's intact file; fonts set Urdu *text* but never stand in for calligraphy;
every Urdu line is proofed by a native reader (hyperframes U-06); no recolour/glow on the logo.

---

## 1. Summary

1. **Shaping is the Urdu risk in TD, and there are four independent engines in this build, each with different evidence.** Text TOP: Urdu joins and runs right-to-left (probed live, `A_td_2025_howto.md` §5; docs never state it). Text COMP / Geo Text COMP / Text TOP "Scalable": these use the **Slug library 7.2** in this build ([release notes](https://docs.derivative.ca/Release_Notes): "Upgraded to slugLibrary 7.2"); Slug's own manual (v7.5) documents right-to-left and bidirectional layout, but I found **no statement of Arabic contextual joining**, so Nastaliq in the Text COMP is **UNVERIFIED** and needs a probe. Text SOP: Urdu shaping untested. Web Render TOP (Chromium/CEF 132, bundled): runs the same Chrome text path the HyperFrames library already proved for Urdu; transparency on macOS is documented only as a parameter (see §4.1).
2. **For names the cheapest robust path is: one whole-word raster (Text TOP, or a pre-rendered HyperFrames/PNG with alpha), then do all the "kinetic" work as image processing on that raster** (displace, light sweep, normal-map relief, SDF outline/glow, mask-reveal, feedback). It never touches glyphs, so the whole-word rule and the joining problem both disappear. Per-glyph engines (instancing, POP-per-letter, atlases) are the high-risk class for Urdu and for the rules.
3. **Supplied calligraphy (client PNG/SVG)** can be animated without breaking it by treating it as an opaque alpha plate: moving light/specular sweep, normal-map relief lighting, slow scale/parallax, glow breathing, whole-word fade/blur-in, directional wipe with padded bounds (hyperframes U-03). Not safe: Trace SOP re-vectorising (changes the art), per-stroke draw-on (needs centre-lines the client file does not have), recolouring (**ask**), blur/displacement strong enough to hurt legibility.
4. **Text POP (new POP with extrude, glyph attributes) is not in 2025.31550**; it appears in the release notes at build 2025.32460 ([release notes](https://docs.derivative.ca/Release_Notes)) and the live class list here has no `textPOP` (`A_td_2025_howto.md` §2). 3D text in this build = Text SOP (closed polygons) + Hole SOP + Extrude SOP, with a **known macOS coarse-curve bug** (`ops/SOP_MAT.md` gotcha 3), or Geo Text COMP (flat Slug quads, lit by a MAT), or 2.5D relief from a raster.
5. **Particle text is a hard-rule problem, not a TD problem.** Any "particles assemble into the name" intro shows partial lettering (against U-00). Rule-safe versions: particles that live *around* an always-whole solid name (sparks off the edge, dust, light motes), or a dissolve **out** after the full name has been held. Ask the lead before any assemble/scatter.
6. **Text masks revealing video** (video inside the name) is the most TD-native, cheapest and strongest-looking item: Text TOP -> Matte/Multiply/Inside with the clip. The legibility risk is dark video inside thin Nastaliq strokes (covered-by-darkness); fix with luma floor + outline + solid backing layer.
7. **Text from audio** = audio values drive *properties of the whole word* (scale, glow, displace amplitude), not letters. Do not apply tracking (letter-spacing) to Urdu: W3C says it breaks cursive joins ([CSS Text 3 §7.2.1](https://www.w3.org/TR/css-text-3/)). Show rule: names and reveals are manual or timecoded, never audio-only (CREATIVE.md "Reactivity" as quoted in `C_pf26_fit.md`). Live speech-to-text (Whisper components) uses a cloud API: conflicts with the local/free policy and Urdu accuracy is unknown, so not recommended.
8. **Fonts:** Noto Nastaliq Urdu, Gulzar, Noto Naskh/Sans Arabic, Lalezar, Reem Kufi, Aref Ruqaa Ink are SIL OFL 1.1 and already audited in `hyperframes/studio/assets/fonts/`. **Awami Nastaliq is OFL but Graphite-only (no OpenType path): avoid in TD.** **Jameel Noori Nastaleeq: licence not confirmed and a provenance concern was reported: do not use.**
9. **Far-away readability:** minimum legible height is easy to meet (arithmetic in §4.12); the real problem is **Nastaliq's hairline strokes and tall overhang** on narrow 10 ft faces (576 px wide at 75%). Needs a solid, bold weight (Noto Nastaliq VF wght up to 700), a single thin outline (hyperframes U-07), and vertical room (U-03).
10. **Biggest unknowns to probe before building** (list in §7): Urdu in Text COMP/Geo Text COMP (Slug), Urdu in Text SOP, Web Render TOP transparency + frame rate on this Mac, tracking/weight control on Urdu, variable-font axis (weight) support in Text TOP.

---

## 2. Findings table

Status: V = verified live in this build (see cited file); D = documented (URL) not run; U = UNVERIFIED.

| # | Item | Look | TD route (31550) | Urdu | Rule risk | Far-read | Status |
|---|---|---|---|---|---|---|---|
| 1 | Name as text | Solid bold name, anything done to it after | Text TOP (`dispmethod=scalable`, Slug) -> TOP chain | Joins + RTL OK in Noto Nastaliq/Geeza Pro (V) | none | high if bold | V (Urdu), D (Slug) |
| 2 | Urdu via Chromium | Any HTML/GSAP text anim, real shaping | Web Render TOP (CEF 132) loads a page; `transparent` par | Same engine as HyperFrames (hyperframes U-05) | low | high | par exists (V, `ops/TOP.md`); alpha on Mac **U** |
| 3 | Pre-rendered overlay | Finished motion with alpha, TD adds light/FX | Movie File In (ProRes 4444 / Hap Q alpha / PNG seq) | HyperFrames already shapes it | none | high | D (`ops/TOP.md` 2.6) |
| 4 | Supplied calligraphy | Gold brush name, shimmer / relief light / wipe | Movie File In (PNG alpha) or SVG COMP (webSvg) | n/a, client file | **high if altered** | medium (thin) | D |
| 5 | Kinetic EN names | Whole-word slide/scale/displace/echo | Text TOP + Transform/Displace/Feedback/Cache | n/a | low | high | D (tutorials) |
| 6 | Per-letter instancing | Letters tumble and settle | Geo Text COMP spec-DAT blocks / Text SOP instancing | **breaks joins if split** (hyperframes U-01) | **violates rule** w/o OK | n/a | D, not recommended |
| 7 | Lyric-style lines | Timed lines, whole-line transitions | Table/Text DAT cue list -> Text TOP/COMP `text` | proof each line (U-06) | rights (own note, §4.4) | high | D |
| 8 | SDF / outline / glow | Clean outline, inner glow, bevel look | Text TOP -> GLSL TOP (JFA) or Level/Blur/Edge chain | fine, bitmap-based | none | **best fix for thin strokes** | D (technique), U (TD build) |
| 9 | Particle text | Name dissolves to/forms from points | Text TOP -> TOP to POP -> Particle POP -> Render | fine (bitmap) | **assemble = partial name** | medium | D (texture->POP tutorial) |
| 10 | 3D extruded text | Chrome/gold slab letters | Text SOP(closed) -> Hole -> Extrude -> PBR MAT -> Render | **Text SOP shaping untested** | low (one mesh per word) | high | D; macOS LOD bug |
| 11 | 2.5D relief | Embossed/lit plate from any raster | Normal Map / Emboss TOP + GLSL light | fine | none | high | D |
| 12 | Video inside name | Footage visible through letters | Text TOP matte -> Matte/Multiply/Inside with clip | fine | covered-by-dark risk | high with outline | D |
| 13 | Text from camera | (a) video-in-name, (b) ASCII-style mosaic | (a) as 12; (b) Tile/Lookup + glyph atlas | n/a | mosaic is background only | low | D (low-quality sources) |
| 14 | Text from audio | Word pulses/glows/warps with music | Audio Spectrum/Analyze CHOP -> pars of 1, 5, 8 | no tracking on Urdu | names manual/timecoded | high | D; house `JZBA_AudioAnalysis` |

---

## 3. What motion is safe for a name (derived from the rules, applies to §4)

Own synthesis from `hyperframes/CLAUDE.md` rule 7, U-00..U-03 and BRIEF §5 (not a new rule):

- **Allowed on a whole-word raster:** translate/scale/rotate of the whole word; opacity; blur-in; word-level mask wipe with padded bounds; light/specular sweeps; glow; relief lighting; displacement with amplitude small enough that every letter stays recognisable; echo/trails behind (never over) the word.
- **Needs the lead's OK:** any per-letter or per-glyph motion; assemble-from-particles; scramble/decode; slicing ("Sliced Type" style) that offsets parts of the word; video-in-letters (the clip changes what is visible inside the shape, see §4.8).
- **Never:** splitting Urdu into per-letter elements (cuts joining context so letters take isolated forms: hyperframes U-01); applying tracking to Urdu ([W3C](https://www.w3.org/TR/css-text-3/): "Notice this breaks cursive joins!", "Authors should avoid applying letter-spacing to cursive scripts"); drawing a font in place of the client's calligraphy.

---

## 4. Per-item details

### 4.1 Urdu in TD: the shaping engines (look, build, gotchas)

| Engine | What the docs say | What we know here | Verdict |
|---|---|---|---|
| **Text TOP** | Unicode supported; `Reading Direction` LTR/RTL; `Break Language` is "a hint"; page never mentions Arabic/shaping ([Text TOP](https://docs.derivative.ca/Text_TOP)). Uses an older Unicode line-break library (Derivative staff, [forum](https://forum.derivative.ca/t/texttop-other-break-languages/641191)); break-language menu has no Urdu (dump). Display Method `Scalable` uses Slug ([Text TOP](https://docs.derivative.ca/Text_TOP), [Slug](https://docs.derivative.ca/Slug)). | **Probed: joined forms, RTL word order, Noto Nastaliq Urdu + Geeza Pro** (`A_td_2025_howto.md` §5). Judged by eye on the agent's own string, not by a reader. | Use for Urdu *text* lines after a native-reader check. |
| **Text COMP / Geo Text COMP** | Slug-based GPU text; RTL option; "Bidirectional layout is also supported when LTR characters are detected when using RTL mode"; font list shows Geeza Pro and Noto Nastaliq Urdu but "does not describe Arabic shaping or joining" ([Text COMP](https://docs.derivative.ca/Text_COMP), [Geo Text COMP](https://docs.derivative.ca/Geo_Text_COMP)). Formatting codes (colour, `grad`, `track`, `skew`, `stretch`) inline per word ([Text Formatting Codes](https://docs.derivative.ca/Text_Formatting_Codes)). | Slug 7.2 in this build ([release notes](https://docs.derivative.ca/Release_Notes)). Slug manual v7.5 documents `kLayoutRightToLeft` and `kLayoutBidirectional` ([search summary of sluglibrary.com/SlugManual.pdf](https://sluglibrary.com/SlugManual.pdf); I could not read the PDF text directly). Slug's site lists kerning, ligature replacement, combining-mark placement ([sluglibrary.com](https://sluglibrary.com/)) but **not Arabic joining**. | **UNVERIFIED for Urdu.** Probe before use. Great for Latin names (resolution independent). |
| **Text SOP** | Unicode; `Reading Direction`; "Language" hint using the Unicode language abbreviations, where `ur` Urdu, `ar`, `fa` exist ([abbreviations](https://docs.derivative.ca/Text_TOP/SOP_Unicode_Language_Abbreviations)); closed polygons for Extrude ([Text SOP](https://docs.derivative.ca/Text_SOP)). | Dump here has `breaklang` (no Urdu entry) and `readingdirection`; no shaping test (`ops/SOP_MAT.md` row `textSOP`). | **UNVERIFIED for Urdu.** |
| **Text POP** | CPU-heavy; outputs `CpIndex`, `GlyphIndex`, `GlyphId`; "one glyph can represent multiple code points" (hints at a shaping layer, not stated) ([Text POP](https://docs.derivative.ca/Text_POP)). | **Not in 31550.** Added in 2025.32460 ([release notes](https://docs.derivative.ca/Release_Notes)); fixes on macOS in 2025.32820 (font file input) and Text TOP Stroke mode on macOS in 2025.32820. | Out of scope unless TD is upgraded (lead decision). |
| **Web Render TOP** (Chromium/CEF) | Renders pages in separate CEF processes; `Transparent Background` option; Info DAT reports `cef`/`chromium` versions; macOS not discussed ([Web Render TOP](https://docs.derivative.ca/Web_Render_TOP)). Local files via `file://`. | CEF 132.3.1.0 helpers bundled; pars `transparent`, `maxrenderrate` default 30, `dpiscale` default 2.0 (`ops/TOP.md` row `webrenderTOP`, `D_camera_mediapipe.md`). HyperFrames relies on Chrome's HarfBuzz for Urdu (`hyperframes/RESEARCH.md`). Could not fetch Blink's shaper docs (search budget used up): "Chromium shapes with HarfBuzz" rests on that local note. | Real shaping engine. **UNVERIFIED on this Mac:** actual alpha, 1080x1920 frame rate, transparent-background behaviour, GSAP playing in real time (HyperFrames pages are seek-driven; a live page needs its timeline played, not seeked). |
| **Pre-rendered (HyperFrames)** | Library renders 1920x1080 ProRes 4444 alpha at 30 fps, premultiplied step for Arena (`hyperframes/CLAUDE.md` rule 5). | Already built and shaping Urdu. Not vertical 1080x1920 and not live. | Safest for finished name cards; TD only post-processes. |

**Known gotchas (Urdu specific):**
- **Tall overhang:** Nastaliq tails/dots reach far outside the advance box; a mask or Text TOP frame that is too tight chops them (hyperframes U-03; `A_td_2025_howto.md` §5). Allow ~0.55em x 0.4em padding (hyperframes number) and Nastaliq line-height about 2.0.
- **Narrow word spaces** in Nastaliq: words run together from far away; add word spacing (hyperframes U-07: `word-spacing: 0.3em`). In TD that is a space-padded string or separate text blocks per *word* (a word-level layout, not a letter split). Do **not** use `trackingx` (see §3).
- **Language tag:** `ur` switches Urdu digit forms in fonts that have `locl` (hyperframes U-02). Text TOP has no Urdu break language (dump), so digit forms by locale in TD are **UNVERIFIED**; avoid digits in Persian-designed faces until checked.
- **Unicode through DATs:** a 2020-era forum thread reports the DAT class not handling Unicode; workaround was storing escapes and pushing through a script to the `text` par ([forum](https://forum.derivative.ca/t/unicode-on-dats/7802)). Docs now state Unicode is fully supported in DATs and Python ([Text COMP](https://docs.derivative.ca/Text_COMP)). **UNVERIFIED in 31550 for Urdu:** test a Table DAT -> `text` expression round trip.
- **Arabic through the UE TouchEngine plugin showed "?"** in a forum report; Derivative said text was fine inside the Engine COMP ([forum](https://forum.derivative.ca/t/touch-engine-plugin-for-ue4-arabic-text-in-dats/211467)). Relevant only if text is ever sent between apps (OSC/Syphon labels): keep Urdu as images when crossing apps.
- **Variable fonts:** Noto Nastaliq Urdu VF has wght 400-700 (hyperframes AUDIT §4). The Text TOP/COMP expose `typeface` (Regular/Italic/Bold/Bold Italic) but **no variation-axis parameter** in the dump; whether a variable font's weight axis is reachable from TD is **UNVERIFIED** (my search found nothing). In a Web Render page, CSS `font-variation-settings` would animate weight.

### 4.2 Animating a supplied calligraphy image/vector without breaking it

Source rule: Urdu calligraphy comes only from PRISM's intact file (hyperframes rule 7; `prism-brand/CLAUDE.md`). The feed uses gold Urdu brush calligraphy over artist names (`hyperframes/RESEARCH.md`). I have not seen the client file, so format is unknown.

**Load paths in this build**
- **Raster (PNG/TIFF with alpha, or ProRes 4444 / Hap Q alpha clip):** Movie File In TOP (`ops/TOP.md` 2.6). Pixel-exact; no re-interpretation. Export it at least at the size it will appear on the face (10 ft face = 576 px wide at 75%, 1152 / 1728 px for 20 / 30 ft: `C_pf26_fit.md` §2) plus 2x headroom for slow zooms.
- **Vector (SVG):** SVG COMP (formerly webSvg) renders through the Web Render TOP, in its own thread; changes show "1 to 2 frames later"; animating needs Cook Always; no stroke-animation features documented ([SVG COMP](https://docs.derivative.ca/SVG_COMP) rev. page text via fetch). The old SVG TOP is deprecated and does not work (`ops/TOP.md` row `svgTOP`). Cost/benefit: crisp at any scale, but a CEF process per SVG and a lag; I would rasterise once at final size instead, **unless** the client sends only vector (then ask for a high-res PNG too).
- **Do not auto-trace** (Trace SOP, [docs](https://docs.derivative.ca/Trace_SOP)) the client's art to get geometry: it threshold-traces a raster into polygons, with smoothing/resample options, so it produces an *approximation*, not the file. UNVERIFIED whether the client would accept that as "their calligraphy"; ask.

**Safe motion recipes (all keep the plate whole; ops exist per `ops/TOP.md`; chains are my design, UNVERIFIED as builds):**

| Effect | Chain | Notes |
|---|---|---|
| **Light sweep / gold glint** | plate alpha -> Ramp or Noise TOP (moving) -> Multiply by plate alpha -> Add over plate | The glint lives inside the existing pixels, so nothing is added outside the shape |
| **Relief lighting (chrome/gold emboss)** | plate alpha -> Blur -> Normal Map TOP (`heightmap`, `zscale`) -> GLSL TOP light + env-map ramp, or Emboss TOP | Same look family as HyperFrames "chrome, glass and gold" (direction B). Blur the alpha first or the normal map shows jaggies |
| **Breathing glow** | plate -> Blur/Bloom -> Add behind, level driven by LFO/audio | Glow must not eat the thin strokes: keep it behind the plate (Under), not over |
| **Slow push / parallax / float** | Transform TOP on whole plate; optional second displaced copy as a shadow | uniform scale only (logo-style discipline) |
| **Reveal (word wipe, fade, blur-in)** | Ramp TOP threshold as a matte (Matte TOP / Multiply), direction following reading order (right to left; Nastaliq slopes down-left) | Pad the matte so tails are not clipped (U-03). A wipe shows a partial word for its duration: **confirm it is acceptable**; fade or blur-in never shows a partial word |
| **Ink-bleed reveal** | Noise TOP -> Threshold TOP animated -> matte | Same partial-word caveat |
| **Subtle living distortion** | Displace TOP with low-frequency noise at tiny `displaceweight` | Keep amplitude below stroke thickness or counters/dots shift off their letters |

**Not safe / not possible:**
- **Stroke draw-on.** The standard technique is `stroke-dashoffset` on a *centre-line path* ([general SVG technique](https://www.svgator.com/blog/how-to-create-svg-text-animations/), via search summary). Brush calligraphy is almost always a filled outline, which has no centre-line to draw; no TD-documented stroke animation exists in the SVG COMP. Can only be faked by a directional wipe.
- **Per-stroke or per-letter particles** from the plate: breaks the whole-word rule.
- **Recolour:** the gold is part of the client's file and brand look (`prism-brand/CLAUDE.md` logo rules are for logos; for calligraphy this is a lead decision).

**Alpha path to Arena:** RGBA through Syphon is 8-bit (`A_td_2025_howto.md` §4); clips with alpha for Arena go out *premultiplied* (project memory, `E_live_rig.md` lines ~353). Text TOP has `premultrgbbyalpha`; Level/Over math on glowing edges is where straight-vs-premult mistakes show (hyperframes H-34, H-18). Test with Arena's blend.

### 4.3 Kinetic English artist names (whole word)

**Look:** big solid name sliding/scaling in, settling with a light sweep, trailing echoes, audio-pulsed glow; no letter motion.

**Existing community references (watch only, nothing downloaded):**
- Derivative community "Text TOP Pro Tricks" (elburz): layout and sizing tricks ([post](https://derivative.ca/community-post/touchdesigner-text-top-pro-tricks/63063), full text at [interactiveimmersive.io](https://interactiveimmersive.io/blog/touchdesigner-lessons/touchdesigner-text-top-pro-tricks/); I could not read the body).
- "Sliced Type" (threedashes, 2020): noise + masks + Displace TOP, audio-driven ([post](https://derivative.ca/community-post/tutorial/sliced-type/62992)). **Slices the word** -> needs OK under the rules.
- "Touching Typography" Cases 1-3 (Artechs, 2020): noise grid, cache grid, stair cube; field-inspired ([Case 1](https://derivative.ca/community-post/tutorial/touching-typography-case-1-noise-grid-part-1-2/62979), [Case 2](https://derivative.ca/community-post/tutorial/touching-typography-case-2-cache-grid/63534), [Case 3](https://derivative.ca/community-post/tutorial/touching-typography-case-3-stair-cube/63592)). Mostly pre-baked-style whole-text-as-texture moves.
- "Kinetic Typography in TouchDesigner" (Artechs, Dec 2019): "sentence instancing" ([Part 1](https://derivative.ca/community-post/tutorial/kinetic-typography-touchdesigner-part-1-fundament/62255)); per-glyph, and **Part 4 exists because "texture instancing is not supported" for non-Kepler GPUs and Mac** ([Part 4](https://derivative.ca/community-post/tutorial/kinetic-typography-touchdesigner-part-4-non-kepler-mac-osx-workaround/62711), 2020). Treat 2019/2020 instancing tutorials as Mac-risky. Geo Text COMP docs also note instance textures are limited to **128 on macOS** vs 16384 on Windows ([Geo Text COMP](https://docs.derivative.ca/Geo_Text_COMP)).
- "Characters Animation" asset (Fred Tretout / anodin, Mar 2024): intro/stay/outro with Geo Text COMP, decode FX for monospace; licence and TD version not stated ([asset](https://derivative.ca/community-post/asset/characters-animation/69211)). Per-character; decode intro breaks the rules for names.
- "Audio-reactive text tracing and instancing" (audiodevout, 9 Oct 2025): uses the "AudioAnalysis tool" ([tutorial](https://derivative.ca/community-post/tutorial/audioreactive-text-tracing-and-instancing-touchdesigner-tutorial/73009)). Recent; per-letter granularity not stated.

**TD build (own design, UNVERIFIED):**
`Text TOP (word, big, scalable) -> Transform TOP (position/scale from a Timer or Spring/Lag CHOP) -> Displace TOP (low-freq Noise) -> Composite with Feedback TOP echo (behind) -> Level/Bloom -> Null`. Echo uses `Feedback TOP` recipe 1 in `A_td_2025_howto.md` §6 (verified loop). 16-bit float for long trails (`ops/TOP.md`).

**Readability:** solid, bold weight, one outline (see §4.5). Latin: use the brand faces in `hyperframes/studio/assets/fonts/` (Montserrat, Josefin Sans, OFL-checked there).

### 4.4 Lyrics-style / cue-driven text

**Look:** whole lines appear/replace on cue, one line per face, large.

**Build:** Table/Text DAT as the cue list (time, text); Python (Execute DAT or a Timer CHOP callback) sets the Text COMP/Text TOP `text`. Pattern is in `ops/DAT.md` and `H_control_panel.md`. Transition per line: Level/opacity crossfade of the *whole line*. Show timing must follow the PF26 rule that reveals are manual or timecoded (`C_pf26_fit.md`, CREATIVE.md "Reactivity").
- **Timed transcript from audio:** DotSimulate's OpenAIAudio TOX produces a segmented table with start/end times ([Patreon post](https://www.patreon.com/posts/92826648)) and Torin Blankensmith's Whisper/ChatGPT components exist ([tutorial](https://derivative.ca/community-post/tutorial/text-speech-elevenlabs-plugin-touchdesigner-whisper-chatgpt-and-mediapipe)): both rely on **OpenAI's cloud API** (per the posts), which breaks the local/free/no-account policy (`hyperframes/AUDIT.md` rule 1), and Urdu recognition accuracy is **UNVERIFIED**. Recommended instead: pre-written line lists from the real setlists (`prismfest26-show/show.json`).
- **Rights (own note, no source):** reproducing lyrics on screen may need rights clearance; "lyrics-style" can mean the *style* with the client's own words. Ask.
- **Urdu lines:** native-reader proof (U-06); word spacing (U-07); fit with `fontautosize` (not tracking).

### 4.5 SDF, outline, glow (the far-readability tool)

**Why:** a single clean outline and an inner/outer glow are the main way to keep thin Nastaliq and gold type readable from far on any background (`overlay-readability-rules`; hyperframes U-07: a Latin-weight outline turned Nastaliq into a "scalloped, doubled shadow"; use one thin outline).

**Options in 31550:**
1. **Text TOP stroke mode:** `dispmethod=stroke` + `strokewidth` gives outline only ([Text TOP](https://docs.derivative.ca/Text_TOP)); composite over a fill Text TOP with the same settings. Cheapest; note a macOS fix for Stroke mode landed in 2025.32820, i.e. after this build ([release notes](https://docs.derivative.ca/Release_Notes)): **Stroke on macOS in 31550 is UNVERIFIED**.
2. **Raster dilate:** word alpha -> Blur -> Level/Threshold (gamma/threshold) -> subtract the original = outline ring. Pure TOPs, no readback. (own technique, UNVERIFIED)
3. **Jump Flood SDF (GLSL TOP):** seeds -> init -> log2(max(w,h)) halving passes -> distance -> outline/glow/bevel from the distance value. Algorithm and use for silhouettes, outlines and glow described in the three.js forum demo ([discourse.threejs.org](https://discourse.threejs.org/t/demo-realtime-sdf-effects-with-the-jump-flood-algorithm/88012)); a TD structure (seeds -> `jfa_init` -> K halving passes -> colour pass -> null, K from log2(max(w,h))) appears in a third-party MCP tool listing ([create_jfa_voronoi](https://glama.ai/mcp/servers/lucasmaher-hash/touch-designer-mcp/tools/create_jfa_voronoi), low trust, structure only). At 1080x1920 that is about 11 passes (arithmetic: log2(1920) = 10.9). GLSL TOP works on this Mac (Vulkan/MoltenVK; `A_td_2025_howto.md` §2).
4. **Atlas MSDF (msdf-atlas-gen):** MIT, selects glyphs by **glyph index** (`-glyphset`) and supports `-varfont` ([repo](https://github.com/Chlumsky/msdf-atlas-gen)), so a pre-shaped Urdu run (HarfBuzz glyph IDs) is possible. But needs a CMake/vcpkg build or a Windows binary (install gate), emits **per-glyph quads**, and the repo says nothing on Arabic shaping. For whole words a single raster -> JFA is simpler and rule-safe. **Not recommended.**
- Pre-shaped glyph outlines as vector: HarfBuzz 13.0.0 added an experimental `hb-vector` API/CLI that writes glyph outlines to **SVG only** ([release 13.0.0](https://github.com/harfbuzz/harfbuzz/releases/tag/13.0.0)); `uharfbuzz` (Apache-2.0) binds HarfBuzz to Python ([repo](https://github.com/harfbuzz/uharfbuzz)); HyperFrames already does this in-page (U-05). Use only if a vector word asset is needed offline; install needs the user's go-ahead.
- Courses (paid, FYI): Matthew Ragan "SDFs 101" 4 h, $147 ([page](https://pro.interactiveimmersive.io/?p=32371)); the page does not mention text.

### 4.6 Particle text

**Look:** points that carry the name's colour; sparks, dust and glints around a solid name; or a dissolve out after the hold.

**Build in 31550 (own design, UNVERIFIED as a chain; pieces verified):**
- `Text TOP -> TOP to POP (toptoPOP exists, probed in A) -> Particle POP / Noise POP / forces -> Render TOP (Point Sprite MAT)`. The Particle POP chain was verified in `A_td_2025_howto.md` §6 / T-15; texture-to-particles is Jack DiLaura's tutorial, Jan 2026 ([post](https://derivative.ca/community-post/tutorial/touchdesigner-3d-particles-2d-textures/73861): TOP patterns -> POP network that converts the texture to 3D geometry, generates particles, applies colour). Derivative/SudoMagic's POP lessons (May 2026) cover attributes, noise, feedback, colour sampling and particles but **no text or logo forming lesson** ([lessons](https://derivative.ca/community-post/new-pops-lessons-learnderivativeca/74561)).
- Alternative start: `Text SOP (closed polys) -> Resample -> SOP to POP`; points sit on outlines, not fill; Mac LOD bug applies (`ops/SOP_MAT.md` gotcha 3).
- POP caveats on this Mac: POP-to-SOP readback stalls; keep it on the GPU (`ops/SOP_MAT.md` gotcha 9).

**Rule-safe variants:** (a) always-whole solid name + particle sparks/motes drawn *under or beside* it; (b) the name held whole, then dissolves out as the very last move (ask); (c) particles *form* the name: **partial lettering for the duration -> needs explicit OK.**

**Urdu:** bitmap-based, so joining is already baked in; but thin strokes give few points (more per area needed) and dots/marks can drift off their letters: keep particle displacement small while the word is read.

### 4.7 3D extruded text

| Route | Build | Result | Problems |
|---|---|---|---|
| **A. Text SOP -> Hole -> Extrude -> MAT -> Render** | Text SOP `output=closedpolys` (triangles extrude each triangle: [Extrude SOP](https://docs.derivative.ca/Extrude_SOP)), Hole SOP for counters ([Hole SOP](https://docs.derivative.ca/Hole_SOP); the page does not describe the glyph use, taken from [Text SOP](https://docs.derivative.ca/Text_SOP)), Extrude SOP bevel via cross-section input, Depth Scale, `cusp` angle; PBR/Phong MAT, env map | True 3D slab, bevel, metal | **macOS ignores Level of Detail** (forum via `ops/SOP_MAT.md` gotcha 3: ~277 pts vs ~1280 on Windows); **Urdu shaping in Text SOP untested**; thin Nastaliq strokes get fragile when extruded. Dump has `extrude`/`extrudedepth` on the Text SOP that docs lack. Keep one mesh per word. |
| **B. Geo Text COMP** | Slug quads in a 3D scene, any MAT, `facecam` (new in 31550), lights apply | Flat but lit, crisp at any size | No extrusion ([Geo Text COMP](https://docs.derivative.ca/Geo_Text_COMP)); glyphs are semi-transparent rectangles needing draw-order care; Urdu **UNVERIFIED** |
| **C. 2.5D relief from raster** | §4.2 relief chain, optional POP/grid displacement by the blurred alpha | Fake chrome slab; works for the *client's calligraphy plate* | Silhouette stays flat; very cheap |
| **D. Text POP with `extrude`** | Not in this build ([Text POP](https://docs.derivative.ca/Text_POP), added 2025.32460) | Native GPU-pipeline extruded text with `Connectivity` triangles/line strips and Bridge Holes | Needs a TD upgrade decision |
| **E. Pre-render** | HyperFrames H-20 (HarfBuzz -> `glyphToPath` -> Three.js `ExtrudeGeometry`, clipping-plane reveals, selective bloom H-21) -> ProRes 4444 alpha -> Movie File In | Direction-B chrome/glass/gold already working | Not live, 1920x1080; vertical variants need new comps |

Recommendation: **E for hero names, C for the calligraphy plate, A only for Latin names** until the Text SOP is probed for Urdu and the LOD bug is looked at on the wall (§7).

### 4.8 Text masks revealing video

**Look:** the name is a window into footage (webcam clip, approved PF26 loops, abstract renders); whole name always present, footage moves inside.

**Build:** `Text TOP (white on black, Slug scalable, giant) -> Matte TOP or Multiply TOP / Inside TOP with the clip`; the Derivative fundamentals lesson on mattes and masks ([Mattes & Masks](https://learn.derivative.ca/courses/100-fundamentals/lessons/102-tops-working-with-images/topic/mattes-masks/)) uses Composite and Multiply; `matteTOP` takes a channel of In3 as matte (`ops/TOP.md`), `insideTOP` shows In1 only where In2 has alpha. Add: outline ring (§4.5) in a solid colour, a solid dark/gold backing plate under the clip with Level floor so the interior never goes fully dark, and brightness clamp on the clip inside the letters.

**Rule check:** the name is whole and uncovered *as a shape*; it stays readable only if clip luma inside is bounded. The risk is the name "disappearing" in dark footage = effectively hidden. Treat the outline + floor as mandatory, and ask the lead to confirm this style at all.

**Urdu:** counters and dots are small; footage inside thin Nastaliq strokes is unreadable. Prefer bold weights (Noto Nastaliq VF at 700) or the client plate's fill area; use footage mainly as *texture inside gold*, not full-colour imagery.

**Reveal of the video itself** (text as a mask that grows) is a hidden-name risk: the mask must start at the full name, never smaller.

### 4.9 Text from camera

(a) **Video inside the name**: §4.8. For the webcam use the stored 5 s clip `media/webcam/webcam_ref_5s.mp4` (house rule) rather than the live camera; live camera routes and permissions: `D_camera_mediapipe.md`.
(b) **ASCII/character-mosaic of the camera:** tutorials exist as videos only ("webcam ASCII" listings, [aggregated](https://interactiveimmersive.io/touchdesigner-operators-tops/), thin content). Method (own sketch, UNVERIFIED): downscale camera -> Level -> map brightness to cell index via Lookup/Tile against a glyph-ramp texture rendered from a Text TOP. Mosaic characters are background texture; the name must sit whole on top. Urdu glyph ramps would be isolated letters: **do not use Arabic-script characters as mosaic cells** (isolated forms look like broken words).
(c) **Silhouette-filled name:** a person-mask (Blob Track / MediaPipe plugin in a Web Render TOP) as matte over the clip inside the name: same §4.8 rules; vision routes in `D_camera_mediapipe.md`.

### 4.10 Text from audio

- **Properties, not letters:** map Audio Spectrum / Analyze / Envelope CHOP values (`ops/CHOP.md`; house component `JZBA_AudioAnalysis`, td-port LEARNINGS, Script CHOP ~2x slower under Rosetta per `A_td_2025_howto.md` §5) to word-level scale, glow, displacement amplitude, or hue shift. Lag/Spring CHOP smoothing keeps it legible.
- **Tracking:** audio-driven letter-spacing is a classic move for Latin; for Urdu it breaks joins ([CSS Text 3 §7.2.1](https://www.w3.org/TR/css-text-3/)). Use `stretch`/`scale`, not tracking. Whether the Text COMP `{#stretch()}` formatting code elongates Nastaliq glyphs properly (rather than just scaling) is **UNVERIFIED**.
- **Variable weight breathing** (wght axis on Noto Nastaliq Urdu VF) would be a legible audio effect but depends on axis control (§4.1): **UNVERIFIED** in TD; available in a Web Render page via CSS.
- **Control rule:** `C_pf26_fit.md` quotes CREATIVE.md: critical reveals and names are manual or timecoded, never audio analysis alone; fall back to a static look when audio drops.

### 4.11 Font licences (all rendered output is fine under OFL; keep licence texts with the fonts)

| Font | Licence | Evidence | Note |
|---|---|---|---|
| Noto Nastaliq Urdu (VF, wght 400-700) | SIL OFL 1.1, Google | [fontsource](https://fontsource.org/fonts/noto-nastaliq-urdu/about); local `hyperframes/studio/assets/fonts/noto-nastaliq-urdu/OFL.txt` | Tall; very large line-height; 1,138 glyphs, 9 OT features per fontsource |
| Gulzar | OFL 1.1 | [googlefonts/gulzar](https://github.com/googlefonts/gulzar) ("typographic, rather than calligraphic feel") | Cleaner, more "typographic" Nastaliq |
| Noto Naskh Arabic, Noto Sans Arabic, Lalezar, Reem Kufi, Aref Ruqaa Ink | OFL 1.1 | `hyperframes/AUDIT.md` §4 (from google/fonts commit, licence text beside files) | Naskh/Sans better at distance than Nastaliq; Aref Ruqaa Ink is COLR v1 (hyperframes U-04); in TD, colour-font support in Text TOP is **UNVERIFIED** |
| Awami Nastaliq (SIL) | OFL, **Graphite-only, no OpenType rendering** ([CTAN awami](https://ctan.org/pkg/awami); [Wikipedia](https://en.wikipedia.org/wiki/Awami_Nastaliq)) | | **Do not use** in TD/Chromium/CoreText (no Graphite): would show unshaped; TD Graphite support **UNVERIFIED** and unlikely |
| Jameel Noori Nastaleeq | **Not confirmed** | Search found no licence text; one Wikimedia commenter says its ligatures derive from a proprietary font ([Phabricator T62685](https://phabricator.wikimedia.org/T62685), single opinion) | **Do not use** without the vendor licence |
| Nafees Nastaleeq (CRULP) | Permissive (reproduce/distribute, keep notice, rename modified) per [CLE PDF](https://www.cle.org.pk/Downloads/localization/fonts/NafeesNastaleeq/Nafees_Nastaleeq_v1.01.pdf) snippet | Full text not read | Candidate only if a different Nastaliq look is wanted; not audited |
| Akira Expanded (PRISM campaign face) | Demo licence | `hyperframes/AUDIT.md` §4 | Not imported |

TD side: `fontfile` takes a `.ttf`; `font` menu lists system fonts and does include Noto Nastaliq Urdu and Geeza Pro on this Mac (`A_td_2025_howto.md` §5). Fonts must also be present when the .toe moves machines (Text COMP: unseen fonts cause a first-use delay while intermediate files are created: [Text COMP](https://docs.derivative.ca/Text_COMP)): ship via `fontfile`.

### 4.12 Readability from far away (large, solid, outlined)

- Rules of thumb disagree, so size for the farthest viewer: Daktronics 1 in of text height per 25 ft of distance ([source](https://www.daktronics.com/en-us/support/kb/000030569)); ActivU distance(ft)/14 inches ([PDF](https://activu.com/uploads/Optimal-Font-Size.pdf)); Extron 10 arc-minutes minimum, 15-20 recommended ([Extron](https://azwebdev.extron.com/article/videowallfontsize)); one source says large, bold, high-contrast type, thin intricate fonts are hard to read ([smartled](https://smartled.yolasite.com/how-to-choose.php)).
- Arithmetic only (no measured stage data): 15-20 arc-minutes at 100 ft is about 5-7 in of letter height (tan(15') ~ 0.0044 x 1200 in = 5.2 in; tan(20') ~ 0.0058 x 1200 = 7 in), i.e. about 25-35 px at 57.6 px/ft (PF26 75% render, `C_pf26_fit.md` §2). So *size* is not the limit; names will be far larger.
- **The limit is stroke thickness and width.** Nastaliq hairlines and dots at final pixel size: aim for the thinnest stroke well over 2-3 px at 75% (own suggestion, UNVERIFIED; check on the LED pitch once known). A 10 ft face is only 576 px wide x 2880 tall at 75% (`C_pf26_fit.md` §2): a long Nastaliq name fits only at small size on one 10 ft face, so choose the 20 ft (1152 px) or 30 ft (1728 px) face for Urdu names, or ask whether rotating the word 90 degrees along the tall face is acceptable (**decision for the lead**; the name must stay on one face and whole).
- Treatments, in order: bold weight (Noto Nastaliq VF 700); solid fill; single thin outline in the contrasting brand colour (hyperframes U-07: `outlineEm: 0.045` worked for Nastaliq); dark or light backing glow behind, not over; word-spacing 0.3em; keep brightness change slow (flash limits: `concert-visuals-research/README.md` §4 and hyperframes rule 8).
- Contrast evidence images and numbers for overlays: `hyperframes/docs/proof/contrast-2026-10-16/README.md` (referenced from LEARNINGS U-07; not re-read here).

---

## 5. Ranked recommendations

1. **Make the whole-word raster the unit** (Text TOP for Latin, Web-Render or pre-rendered HyperFrames for Urdu names) and put all kinetic work on it (§4.3, 4.5, 4.8, 4.10). Highest value, lowest rule risk, least Urdu risk.
2. **Calligraphy plate toolkit** (§4.2): light sweep + relief + breathing glow + push + fade/wipe, as one reusable TD component fed by a PNG with alpha. Needs the client's file format and a decision on wipe/recolour.
3. **Outline + SDF glow component** (§4.5): Level/Blur dilate first, JFA later if the Stroke mode or dilate looks bad. This is what makes Nastaliq readable from far.
4. **Video-in-name component** (§4.8): strongest "TD-native" typography look; mandatory outline + luma floor.
5. **Probe session** (§7) before any other Urdu work in Text COMP / Text SOP / Web Render; one afternoon, throwaway ops in `_research_probe`.
6. **Hero 3D names via HyperFrames pre-render** (§4.7 E), live TD only for post-FX and mixing.
7. **Particle text, rule-safe variants only** (§4.6 a, b).
8. **Per-letter instancing, glyph atlases, MSDF, Whisper captions: do not build** unless the lead explicitly asks (rule, Mac instancing limits, installs, cloud).

---

## 6. Gaps in the evidence

- No source states Arabic/Urdu joining for Slug (Text COMP, Geo Text COMP, Text TOP Scalable).
- No source on whether Text TOP/SOP uses macOS CoreText or another engine; the TOP's break library is "older Unicode-based" per staff; shaping engine is not documented.
- Web search budget ran out mid-session (limit shared by every agent), so some intended checks were not done: Chromium/Blink HarfBuzz citation, extra reference footage for LED typography, Web Render TOP on macOS threads.
- Slug manual PDF text could not be read (compressed fonts); the bidirectional flags come from a search summary of v7.5.
- No festival-stage typography reference (LED name reveals) was collected from the web; use `concert-visuals-research/` references for look direction.

## 7. Probe plan (when a TD session is allowed; throwaway ops in `/project1/_research_probe`, delete after)

1. Text COMP and Geo Text COMP with a short Urdu test string in Noto Nastaliq Urdu, Reading Direction RTL: joined or isolated? (screenshot vs Text TOP). Same for Text TOP `dispmethod=scalable` vs `polygon` vs `bitmap`.
2. Text SOP with the same string (triangles and closedpolys): joined? counters kept after Hole + Extrude? point count vs LOD (macOS bug).
3. Text TOP `trackingx` != 0 on Urdu: gaps between joined letters? Same for the `{#track()}`/`{#stretch()}` codes in Text COMP.
4. Text TOP `fontfile` with `NotoNastaliqUrdu-VF.ttf` and Typeface Bold: does the wght axis apply? Any way to set it?
5. Text TOP stroke mode on macOS in 31550 (fix listed in 2025.32820): outline quality and `strokewidth`.
6. Web Render TOP: local HTML with transparent body + Urdu word (Noto Nastaliq) -> alpha preserved? `maxrenderrate`, achieved `updates_per_second` at 1080x1920, premult state; can a GSAP timeline play live?
7. Table DAT with Urdu string -> Text TOP `text` expression round-trip.
8. Mask-reveal chain with the stored webcam clip: Level floor/outline.

## 8. Open questions for the lead

1. **Client calligraphy file:** what format (PNG/PDF/SVG/AI), resolution, colour (gold baked in?) and does PRISM have one per artist or a generic style? Is recolour or a lit-metal treatment allowed?
2. **Is a word wipe/ink-bleed reveal acceptable** (partial word on screen for ~1 s), or only fades/blur-ins that keep the whole word present?
3. **Video-in-name and particle-dissolve:** do they count as "covered/hidden" under the rule? Which are allowed?
4. **Which face carries an Urdu name?** 10 ft faces are 576 px wide at 75%; rotate 90 degrees allowed, or restrict Urdu names to 20/30 ft faces?
5. **Text POP / newer TD builds:** is a TD upgrade ever allowed (Arena 7.23.2 is final, TD not stated)? 2025.32460 adds Text POP with extrude; 2025.32820 fixes Text TOP Stroke and Text POP font input on macOS.
6. **Lyrics:** are on-screen lyric lines wanted at all (rights), and who writes/proofs the Urdu lines?
7. **Web Render TOP route:** acceptable to rely on a Chromium page inside TD for Urdu text, given the 30 fps default and Mac alpha uncertainty, versus pre-rendering in HyperFrames?
8. **Installs** needed only if wanted: `uharfbuzz` (pre-shaped outlines), msdf-atlas-gen. Recommended: neither.
9. **LED pixel pitch / viewing distance** to set stroke minimums.

## 9. Sources

TouchDesigner docs (fetched 16 Oct 2026):
- Text TOP https://docs.derivative.ca/Text_TOP · Text SOP https://docs.derivative.ca/Text_SOP · Text COMP https://docs.derivative.ca/Text_COMP · Geo Text COMP https://docs.derivative.ca/Geo_Text_COMP · Text POP https://docs.derivative.ca/Text_POP
- Slug Library https://docs.derivative.ca/Slug (rev. 26 Sep 2023) · https://derivative.ca/UserGuide/Slug_Library
- Text Formatting Codes https://docs.derivative.ca/Text_Formatting_Codes · Language abbreviations https://docs.derivative.ca/Text_TOP/SOP_Unicode_Language_Abbreviations
- Release notes (2025.31550 = Oct 30 2025; Text POP 2025.32460; macOS fixes 2025.32820) https://docs.derivative.ca/Release_Notes
- Web Render TOP https://docs.derivative.ca/Web_Render_TOP · SVG COMP https://docs.derivative.ca/SVG_COMP
- Extrude SOP https://docs.derivative.ca/Extrude_SOP · Hole SOP https://docs.derivative.ca/Hole_SOP · Trace SOP https://docs.derivative.ca/Trace_SOP
- Mattes & Masks lesson https://learn.derivative.ca/courses/100-fundamentals/lessons/102-tops-working-with-images/topic/mattes-masks/
- POP lessons (May 2026) https://derivative.ca/community-post/new-pops-lessons-learnderivativeca/74561
- Forum: break languages https://forum.derivative.ca/t/texttop-other-break-languages/641191 · Unicode DATs https://forum.derivative.ca/t/unicode-on-dats/7802 · UE plugin Arabic https://forum.derivative.ca/t/touch-engine-plugin-for-ue4-arabic-text-in-dats/211467

Community tutorials/assets:
- https://derivative.ca/community-post/tutorial/kinetic-typography-touchdesigner-part-1-fundament/62255 · .../part-4-non-kepler-mac-osx-workaround/62711
- https://derivative.ca/community-post/tutorial/sliced-type/62992 · https://derivative.ca/community-post/touchdesigner-text-top-pro-tricks/63063 · https://interactiveimmersive.io/blog/touchdesigner-lessons/touchdesigner-text-top-pro-tricks/
- https://derivative.ca/community-post/tutorial/touching-typography-case-1-noise-grid-part-1-2/62979 · .../case-2-cache-grid/63534 · .../case-3-stair-cube/63592
- https://derivative.ca/community-post/asset/characters-animation/69211 · https://derivative.ca/community-post/tutorial/audioreactive-text-tracing-and-instancing-touchdesigner-tutorial/73009
- https://derivative.ca/community-post/tutorial/touchdesigner-3d-particles-2d-textures/73861 · https://derivative.ca/tags/text
- Whisper in TD: https://www.patreon.com/posts/92826648 · https://derivative.ca/community-post/tutorial/text-speech-elevenlabs-plugin-touchdesigner-whisper-chatgpt-and-mediapipe
- SDFs 101 (paid) https://pro.interactiveimmersive.io/?p=32371 · JFA demo https://discourse.threejs.org/t/demo-realtime-sdf-effects-with-the-jump-flood-algorithm/88012 · TD JFA tool listing (low trust) https://glama.ai/mcp/servers/lucasmaher-hash/touch-designer-mcp/tools/create_jfa_voronoi

Engines, standards, fonts:
- Slug: https://sluglibrary.com/ · https://sluglibrary.com/SlugManual.pdf (v7.5, not readable here)
- W3C CSS Text 3 §7.2.1 cursive scripts https://www.w3.org/TR/css-text-3/
- HarfBuzz 13.0.0 hb-vector https://github.com/harfbuzz/harfbuzz/releases/tag/13.0.0 · uharfbuzz https://github.com/harfbuzz/uharfbuzz · msdf-atlas-gen https://github.com/Chlumsky/msdf-atlas-gen
- Fonts: https://fontsource.org/fonts/noto-nastaliq-urdu/about · https://github.com/googlefonts/gulzar · https://ctan.org/pkg/awami · https://en.wikipedia.org/wiki/Awami_Nastaliq · https://phabricator.wikimedia.org/T62685 · https://www.cle.org.pk/Downloads/localization/fonts/NafeesNastaleeq/Nafees_Nastaleeq_v1.01.pdf
- Legibility: https://www.daktronics.com/en-us/support/kb/000030569 · https://activu.com/uploads/Optimal-Font-Size.pdf · https://azwebdev.extron.com/article/videowallfontsize · https://smartled.yolasite.com/how-to-choose.php
- SVG draw-on technique (general) https://www.svgator.com/blog/how-to-create-svg-text-animations/

Local files relied on: `A_td_2025_howto.md` §2/4/5/6, `ops/TOP.md`, `ops/SOP_MAT.md`, `ops/POP.md`, `C_pf26_fit.md` §2, `D_camera_mediapipe.md`, `E_live_rig.md`, `hyperframes/CLAUDE.md`, `hyperframes/LEARNINGS.md` (U-00..U-07, H-18, H-20, H-21, H-34), `hyperframes/RESEARCH.md`, `hyperframes/AUDIT.md` §4.
