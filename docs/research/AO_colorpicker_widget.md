# AO - ColorPicker UI widget (Artechs / "Factory Settings"), 26 Oct 2026

Status: **PARTIAL. The file could not be downloaded, so nothing was inspected.** Every claim about internals is UNVERIFIED.
Nothing was opened or run in TD. `research_src/colorpicker_63881/` is empty on purpose.

## What was established (cited)
- Derivative asset page `https://derivative.ca/community-post/asset/colorpicker-ui-widget-v13/63881`: "ColorPicker UI Widget (v1.3)",
  author Artechs, posted 10 Feb 2021, tags colorpicker/widget/color. Modelled on the Serif Affinity Designer picker.
  The page has **no tox/toe link**, no build, no licence, no OS note, no forum/GitHub link. Its only resource is a YouTube video
  (`youtu.be/trejboUyp-o`) that "contains the explanation and download link".
- Direct `curl` of the page returns 403 (AWS load balancer blocks non-browser clients). A browser-UA retry was refused by the
  permission classifier as bot-check circumvention, so it was not done. WebFetch of the page text works.
- The YouTube description could not be read (WebFetch returned only page chrome).
- Same author is "Factory Settings" on Patreon. v1.3 post (`patreon.com/posts/colorpicker-for-47031212`): file `COLORPICKER_TOX_v1.3.tox`,
  floating mode for containers, up to 8 stored colours. Patreon returns 403 to WebFetch (login/anti-bot).
  Later: v1.4 public release, v1.5.x with an "assign mode" (supporter-first, later public; one search snippet says v1.5.2 `FS_COLORPICKER_v1.5.2.tox`
  is public), v1.5.4 on 23 Dec 2025 (`derivative.ca/community-post/asset/colorpicker-v154-update/73603`, "Download TOX here" ->
  `patreon.com/posts/colorpicker-1-5-146422129`, adds a panebar shortcut). All downloads are on Patreon; a free YouTube/Patreon
  "Free download" video also exists (`youtube.com/watch?v=pFR8yXXlOA8`). No GitHub repo exists. Licence: never stated anywhere found.
- Not found anywhere: op types, extensions, custom pars, binding method, build saved with, Mac status, network/eval use.

## How it probably binds (UNVERIFIED, inferred from the "assign mode" feature name and typical widgets)
Most likely it exposes colour as custom pars / a CHOP-DAT output on the widget COMP, and the 1.5 "assign mode" lets the user pick a
target par to drive. Whether it handles an RGB tuplet or 3 float pars is unknown. Do not rely on it.

## Audit checklist for when the file is in hand (user must supply it, e.g. download in a browser)
1. `toeexpand` into a subfolder; read only text files. 2. grep for `op.`, `exec`, `eval`, `subprocess`, `os.system`, `webbrowser`,
`urllib`, `requests`, `socket`, `importlib`, `tdu.`, `project.folder`, Web Client/Server/Execute DATs, `onStart`, `onCreate`.
3. Record build (`build` in the .toe/.tox header, `.n` files), op types, extension classes, custom page/par names, and whether
the output is par-bind, CHOP, or a Python callback that writes `parent().par[...]`.

## Recipe to drop a colour widget into an autoUI panel container (applies to any widget COMP, incl. this one once audited)
Based on T-68: build the panel with autoUI on the **slider page only** (`Pagescope` = slider page, `Pagetabs=False`); colours stay on a
`Colours` page that autoUI never sees. Then add the widget as a sibling inside the panel container:
- Put widget COMP in the container; `alignorder` = index after the last slider section (e.g. container `verttb`, widget `alignorder = N`).
- `hmode = Fill` (`hmode='fill'`), `vmode = Fixed`, `h` = ~220-260 px for a SV box + hue bar (widget's own min size to confirm),
  `w` driven by fill; `align = verttb` on the container; check with a window capture (td_screenshot).
- Binding without trusting the widget internals: on the effect COMP, read the widget's colour output with a Parameter/Execute-free
  expression on the three float pars, e.g. `Colourr` `=op('colorpicker1/out_rgb')['r']` (bind expression, mode EXPRESSION), same for g, b;
  or a CHOP Execute-free route via a Select CHOP -> Parameter bind. Prefer expressions (no Python callbacks, no scripts).
- Do not use an RGB custom par for this: three Float pars (`Colourr/g/b`) bind cleanly and avoid the autoUI `KeyError 'RGBA 3'`.

## Risks
Download only via Patreon (account-gated, possibly paid for newest); licence unknown (free-to-use claim only on a video); builds
unknown (2021 file vs 31550); may include on-load scripts; assign-mode likely uses Python writes to other COMPs; Mac/Rosetta untested.

## Verdict
**Not adopted; cannot be audited yet.** Lower-risk path that needs no third-party file: for each colour, three Float custom pars
(r,g,b) on a `Colours` page, shown with basicWidgets sliders/rgb-style Slider2D + one Container Panel built by hand (sliders bound
by expression), plus an on-screen Constant TOP swatch. Revisit this widget only if the user drops the .tox into
`research_src/colorpicker_63881/` (from a browser; no login scraping), then run the audit checklist above.
