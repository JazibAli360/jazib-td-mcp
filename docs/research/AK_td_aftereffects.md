# AK - jazib-td <-> Adobe After Effects 2026 (26 Oct 2026, research only)

Brief: `INTEGRATION_BRIEF.md`. Nothing was run: no TD call, no AE launch, no MCP tool call, nothing installed. Read: the pinned
`mcp-vendor/mcp-aftereffects` source (v0.3.2, `73fea51`), `AH`, `A`, `X`, `E`, `C`, `ops/*` dump, `LEARNINGS` T-11/T-29/T-30.
Tags: **[V]** read in the pinned source or a doc page this session; **[S]** web source (URL in Sources); **[D]** class/par in
`docs/research/ops/` (class-only = in the 682-class list, skipped in the par dump because it opens a device/socket); **[U]**
unverified, needs the test plan. Build behind TD claims: 2025.31550 (macOS, Rosetta). AE = 2026 (v26.x), `aftereffects` MCP is
`AE_MCP_READONLY=1`.

## 1. Summary
1. **No live AE <-> TD bridge exists that we can rely on.** Real options: NDI out of AE (Mercury Transmit, official NDI Tools
   plugin, Win+Mac) into TD's NDI In TOP, preview-grade only [S]; AESyphon (Tobias Ebsen, $20, 2014-era, Intel/Catalina notes)
   [S, U on AE 2026]. Everything that matters is **file hand-off** (ProRes 4444 / PNG / EXR sequence) plus **data hand-off** (JSON).
2. **AE -> TD data is already solved on the AE side and needs no write access:** `ae_project_export_json {outPath}` is allowed in
   read-only mode [V `blockedInReadOnly:false`], writes to disk (not into the model's context), and carries comps, layers,
   transforms, keyframes (time, value, interp, bezier ease speed/influence), text documents, markers, expressions (as strings),
   effects, shape contents [V `jsx/export.jsx`, `helpers.jsx`]. Gaps [V]: **no spatial tangents** (curved Position paths),
   expression results are not evaluated, keyframes of non-exported property types are lost.
3. **Missing TD piece = an importer.** Proposed `td_import_ae_anim` (typed tool): AE JSON (or Lottie JSON) -> long-form `keys`
   Table DAT + baked per-frame channels (Table DAT -> DAT to CHOP) + text/marker tables; exact AE bezier math (section 3.3).
4. **TD -> AE without eval exists and is safe:** (a) files (`project.import_file`, `footage.replace` + `footage.reload`);
   (b) `ae_project_import_json {inPath, dryRun}` with a TD-generated schema-v2 doc; (c) CSV/TSV/JSON as AE *data footage* read by
   expressions (`footage("x.csv").dataValue`, AE's data-driven animation [S/U-exact-syntax]); (d) `keyframe.apply`/`set_batch`
   (small curves, data passes through model context). All need **write mode** (`AE_MCP_READONLY` off = the user's go-ahead).
   **Never write into AE's mailbox dir**: `dispatcher.jsx` runs any request found there with no policy check = arbitrary code in AE [V `src/config.ts`].
5. **Alpha/colour is the real risk, not transport.** Straight vs premultiplied, AE working space vs TD working space, 29.97 vs 30
   fps, duplicate loop frame. Section 3.1/3.2 gives the rules and a numeric round-trip test (AE `ae_render_frame` sRGB PNG vs `td_inspect`).
6. **Proposed upgrades:** `td_import_ae_anim`, `td_export_ae_data`, `td_render_for_ae` (a general offline recorder, T-29/T-30,
   shared with Resolume/HAP), recipes for NDI In and Lottie via Web Render TOP. Offline tests first, live steps ordered in section 5.

## 2. Existing (what already exists for TD <-> AE)
### 2.1 AE side (the `aftereffects` MCP, read-only) [V]
9 tools visible: `ae_project_info`, `ae_comp_info`, `ae_layer_info {compNameOrId, layerIndex: n|[n]|"all", detail: summary|full}`,
`ae_version_info`, `ae_context`, `ae_project_export_json {outPath?, pretty?}`, `ae_render_frame {time|times, outPath, contactSheet?,
analyze?}`, `ae_catalog`, `ae_do`. Withheld in read-only: `ae_save_project`, `ae_project_import_json`. Transport = file mailbox under
`os.tmpdir()/mcp-aftereffects/runtime` + `osascript`; no port, no network. Needs AE Preferences > Scripting & Expressions >
"Allow Scripts to Write Files and Access Network" ON and macOS Automation permission (user's call, AUDIT).
Read-only `ae_do` operations that matter to TD (readOnly:true in source): `comp.info`, `layer.info`, **`comp.sample`** (post-expression
values of chosen properties at a list of times, many layers/comps in one call), `property.get/list`, `item.list`, `item.usages`,
`marker.list`, `project.get_settings` (workingSpace, bit depth), `render.get_settings`, `render.list_templates`, `render.status`,
`footage.list_missing`, `font.*` (list/missing/used), `text.measure`, `effect.list_on_layer`, `egp.list_controllers`, `batch.run`
(read-only children only), `render.frame` (PNG). **Not available read-only:** `render.add_to_queue/start/set_output/queue_in_ame`
(any movie/sequence render from AE), `project.import_file`, `footage.*`, `keyframe.*`, `expression.set`, `eval.run` (also needs `AE_MCP_ENABLE_EVAL=1`, off).
`ae_render_frame` converts color-managed projects to display sRGB itself; raw `render.frame` writes working-space values that look dark [V description].
### 2.2 TD side
- File I/O [D]: `moviefileinTOP` (pars `file, playmode locked|specify|sequential|timecodeop, index+indexunit, interp,
  premultrgbbyalpha off|on|automatic, inputcolorspace automatic|srgb|...|acescg|passthrough, trim/tstart/tend, textendleft/right
  hold|cycle|mirror|black|zero, loopcrossfade, imageindexing zero|filename, prereadframes, format`); `moviefileoutTOP` (`type movie|image|
  imagesequence|stopframemovie, videocodec ... hap|prores|..., videocodectype, imagefiletype tiff|jpeg|bmp|exr|png|dds, outputcolorspace,
  limitlength/length/lengthunit, fps, record, pause, addframe, videopixelformat yuv420|yuv422, format`). Codec facts (probed, `A` s4):
  ProRes 422 HQ..4444 XQ with **yuva4444 12-bit alpha**, Hap/Hap Q/Hap R (alpha), Animation (rle), Cineform, NotchLC; **no DXV**;
  Movie File In reads mov/mp4/Hap Q+alpha/Cineform/NotchLC/EXR/DDS/image sequences [D/V doc].
- Data [D]: `tableDAT` (`file, write, syncfile`), `jsonDAT` (`filter` JSONPath, `outputformat table`), `dattoCHOP` (`output single|chanperrow|
  chanpercol|chanpervalue`), `choptoDAT`, `fileinCHOP`/`fileoutCHOP`/`recordCHOP`, `lookupCHOP` (`interp, left/right`), `scriptCHOP`,
  `keyframeCHOP` (`animation` COMP, `rate`, `left/right hold|slope|cycle|mirror|default`), `animationCOMP` (`channels` DAT, `playmode`,
  `tleft/tright`), `timelineCHOP`, `timecodeCHOP`, `chopexecuteDAT`. Class-only [D]: `ndiinTOP/ndioutTOP`, `syphonspoutinTOP/outTOP`,
  `webrenderTOP`, `oscinCHOP/oscoutCHOP`, `oscinDAT/oscoutDAT`, `websocketDAT`, `webclientDAT/webserverDAT`, `tcpipDAT`, `udpinDAT`, `touchin/outTOP`.
- Palette/Samples inside the app [V ls]: no AE, Lottie or Bodymovin component. `Samples/Chan/default.chan` + File In CHOP show TD reads `.chan`
  (Houdini/Nuke-style per-frame channel files); `Palette/Tools` has `SVG.tox` (static vector, not an AE bridge). **TDAbleton exists, nothing for AE.**
### 2.3 Community / third party
- **Lottie:** forum "Lottie for TouchDesigner?" (31 likes, 2021): staff answer = run it inside a Web Render TOP with a page + websocket/TCP
  for control; asker planned a Lottie tox, **no tox was posted in the thread** [V `research_src/popular/forum_hot/topics/223940.json`]. No
  Lottie GitHub project for TD found (two searches) [S/U]. lottie-web is MIT (Airbnb) [S]; dotLottie web player (ThorVG, canvas) is the newer player [S].
- **NDI for After Effects** (NDI Tools plugin): AE Preferences > Video Preview > Mercury Transmit > NDI; frames go out while the timeline plays/scrubs;
  Win and Mac; AE source name "Adobe After Effects"; alpha and exact AE version support not stated [S docs.ndi.video]. Lower preview resolution = lower-res NDI [S third-party note].
- **AESyphon** (Tobias Ebsen): AE as Syphon server for live preview; free trial, $20 full (needs paid for > XGA); reported to freeze unless AE is the active app (Catalina); 2014-era; current AE 2026/Apple-silicon status unknown [S, U].
- **Keyframe text format:** AE's clipboard "Adobe After Effects 8.0/9.0 Keyframe Data" (tab table, frames/units per second); npm `ae-keyframes` 0.0.1 parses it [S]. No built-in export; our JSON export replaces it.
- **Hap/ProRes from AE:** ProRes via AE's QuickTime output (Mac) [U for 2026 exact menu]; **Hap needs a plugin**: disguise `hap-encoder-adobe-cc` (free; 1.2.0 mentions native AE support Mac+Win; Apple silicon unconfirmed by a Sept 2025 post) or AfterCodecs (paid; last listed AE 2024) [S]. Hap is therefore optional; ProRes 4444 / PNG / EXR are the default hand-off.
- **AEJuice** (preset/pack panel): a library for authoring inside AE; no TD or live link known; not researched further [U].
- Peers: none of the 8 peer TD MCPs in `AF` has an AE bridge.

## 3. Patterns
### 3.1 File hand-off AE -> TD (the default)
| Need | AE output module | TD Movie File In | Notes |
|---|---|---|---|
| Overlay with alpha | QuickTime ProRes 4444, Channels RGB+Alpha, **Color: Premultiplied (Matted)** | `playmode locked` (or `specify`), `premultrgbbyalpha off` [U] | TD TOP chain is premultiplied (Over/Composite expect it). If the file is Straight, set `premultrgbbyalpha on`. `automatic`'s rule is undocumented [V doc: option listed, not explained] so **test, don't trust**. Rule of the repo: clips going on to Resolume are premultiplied (memory `overlay-alpha-premultiplied`, `C` s3). |
| No-surprise frames | PNG sequence `name_[#####].png` (RGB+A, 8/16-bit) or EXR sequence | `imageindexing filename`, file = first frame | Frame-exact, no codec; heavy on disk. Sequence name pattern in `file` is [U]; test. |
| Colour-managed AE project | Output Module > Color: convert to sRGB (or Rec.709) for 8-bit delivery; EXR keeps linear | `inputcolorspace automatic` reads metadata, else assumes sRGB [V doc] | AE `workingSpace = None` (default) files are display-referred sRGB-like: leave TD at sRGB. ACEScg/linear project: render EXR (linear) and set TD `inputcolorspace` to match, or convert in the Output Module. Verify numerically (s5 step 5). |
| Small/loopable | Hap / Hap Q Alpha via plugin | same node, hardware decode | Plugin gate (section 2.3). |
Rules: render the **work area at the comp's native fps**; TD project rate = file rate (Movie Out `fps`, T-30 shows 60 fps default clips); AE 29.97 vs 30 is the classic mismatch (read `ae_comp_info.frameRate`; conform in TD with `speed`/`index` only after checking). `ae_render_frame {times: [...], contactSheet:true, analyze:true}` is the read-only way to **preview a cut** before anyone renders it.
### 3.2 Frame-exact loops
Loop of N frames: AE comp duration N/fps, **last rendered frame must be frame N-1 and frame N must equal frame 0 by design** (no duplicated end frame). TD playback: `playmode specify`, `index = absTime.frame % N` with `indexunit frames`, `interp off`, `textendleft/right cycle`; or `locked` with the timeline range = N (A s4 "frame-exact loops"). Crossfade loops (`loopcrossfade`) are the fallback only (`C` s3 L-36). Check with ffprobe `nb_frames` == N (T-11: 71 asked -> 69 written).
### 3.3 AE keyframes -> TD curves (data pattern)
Source: `ae_project_export_json`. Per property: `keyframes[] = {time s, value, inInterp/outInterp (AE enum ints; rely on the names), inInterpName/outInterpName (linear|bezier|hold), inEase/outEase [{speed, influence}] (bezier keys only, one entry per eased dimension)}`; `value` as array (position `[x,y]`, color `[r,g,b]` 0-1), text as `{__kind:"TextDocument", text, fontSize, fillColor, justification, tracking,...}`, markers `{__kind:"MarkerValue", comment,...}` [V `helpers.jsx`, `fixtures/simple.json`].
**Exact AE bezier (1-D, key A to key B, dt = tB - tA, dv = vB - vA):** `P0 = (tA, vA)`, `P1 = (tA + oA*dt, vA + sOutA*oA*dt)`, `P2 = (tB - iB*dt, vB - sInB*iB*dt)`, `P3 = (tB, vB)` with `oA = outInfluence_A/100`, `iB = inInfluence_B/100`, `s = speed` in units/second. Evaluate by solving `x(u) = t` (monotonic) then `y(u)`. Linear = bezier with 33.33 % and speed dv/dt; hold = out interp name `hold` (value stays until the next key). This is the same normalisation as Lottie (`o.y = o.x*speed*dt/dv`) [S Lottie spec as in lottie-ios list, U on detail]; test numerically against `comp.sample`.
Special cases: (a) **Position/Anchor/3D spatial properties** have ONE ease (speed along the path) plus spatial tangents that the export does **not** include [V `serializeProperty` vs `snapshotKeys`] -> exact reconstruction needs `comp.sample` at frame times, otherwise treat as straight segments and warn; separated X/Y Position are 1-D and exact. (b) Scale/color/etc. non-spatial multi-D: one ease per dimension. (c) `expression` strings are exported un-evaluated; `wiggle`, `loopOut`, `time*k` need TD equivalents (Noise CHOP, Keyframe CHOP `left/right cycle`, `absTime`): list them in the import report, never eval them. (d) Time Remap, layer `startTime/inPoint/outPoint/stretch`, parenting (`parentIndex`) are in the export; parenting must be rebuilt as a transform chain.
**Unit map to a 1080x1920 TD build:** AE px origin top-left, y down; Transform TOP `tunit fraction`, origin centre, y up: `tx = x/w - ax`, `ty = ay - y/h` (include anchor); scale % -> ratio /100; opacity 0-100 -> 0-1; rotation sign and 3D camera zoom (`fov = 2*atan(0.5*w/zoom)`) are [U] until tested; times s -> frames `t*fps`. TD build is vertical 1080x1920 by rule while an AE comp may be 1920x1080: the importer keeps AE pixel units in the `keys` table and exposes `width/height` so the consumer chooses (never silently rescale).
**TD representation (recommended):** bake once at import into a Table DAT (rows = frames, cols = `Layer.Prop.dim`) -> `dattoCHOP` (`output chanpercol`, `firstcolumn ignored`, rate = comp fps) -> Null CHOP `ae_out`; keep `keys` (long form: `layer, matchName, dim, t, value, inI, outI, inSpd, inInf, outSpd, outInf`) beside it for audit; `text` table (`layer, t, string, font, size, fill, just`) for step-wise text via `Lookup CHOP`/index `hold`; `markers` table -> Timer/Event cues (marker comments are free-form cue names). `Animation COMP` (editable curves in TD's editor) is a **later, probe-gated option**: its internal key-table layout is [U] (create one on a scratch COMP, dump `children`/DAT text, then decide; fall back to the baked table, which is exact and cannot break on an internal format).
### 3.4 Lottie / bodymovin JSON -> TD
Two routes. **(R1) Same importer:** Lottie JSON `{fr, ip, op, w, h, layers:[{ks:{p,s,r,o,a}, ip, op, st, parent}]}` with keyframes `{t frames, s, e?, i:{x,y}, o:{x,y}, h?}`; bezier handles are already normalised, so Lottie is a *simpler* input than AE and fits the same `keys`/baked schema (transforms, opacity, text-less). Vector shape layers need a renderer, so R1 = motion data only. **(R2) Visual:** Web Render TOP [D class-only] on a local HTML page with lottie-web or dotLottie, controlled from TD over `websocketDAT` or Web Render's JS call interface [S forum 223940; call API U]; gives the pixels incl. vector shapes, loses frame-exact control and costs CPU readback; library vendor = download needs the user's OK + `AUDIT.md` pin (MIT, >= 7 days, `--ignore-scripts`). To *produce* Lottie from AE needs the Bodymovin/LottieFiles panel (UI plugin, cannot be driven by this MCP); `ae_project_export_json` already gives richer data with no plugin, so Lottie import is for third-party Lottie files (LottieFiles library), not for our AE projects.
### 3.5 TD -> AE
| Path | Mechanism | MCP ops (write mode) | Latency / failure modes |
|---|---|---|---|
| Footage | TD records ProRes 4444/PNG/EXR (`td_render_for_ae`) | `project.import_file {path, sequence?}`, `footage.interpret {alphaMode: premultiplied|straight, conformFrameRate}`, `layer.create_footage`, later **`footage.replace`/`footage.reload`** after TD overwrites the file | File lock while TD is writing (T-29: file unreadable until record stops); `footage.reload` is the "live-ish" update; AE Cache needs purge (`project.purge`). |
| Animation data (small) | none (data via model context) | `keyframe.apply {keys:[{time,value,interp,inInfluence,outInfluence,inSpeed,outSpeed}]}` / `keyframe.set_batch {times, values}` | Good for <= ~100 keys; bezier fit from TD curves is lossy. |
| Animation data (large) | TD writes an AE schema-v2 doc to `output/ae_out/*.json` | **`ae_project_import_json {inPath, dryRun:true}` then real** (appends unless `clearFirst`; validator `validate.ts`; supports keyframes with `inEase/outEase`, `expression`, TextLayer, CameraLayer) | Path-based so it never enters the model's context; builds a NEW comp/folder: never `clearFirst` on the user's project. |
| Data-driven | TD writes CSV/TSV/JSON | `project.import_file` (data file) + `expression.set` `footage("td.csv").dataValue([c,r])`, `footage.reload` | Expression engine only reads imported data; no eval; exact `dataValue` syntax [U], AE supports CSV/TSV/JSON "data-driven animation" [S: Adobe help, not fetched]. Best for audio-analysis curves from TD feeding AE typography. |
| Live preview | AE -> TD only (NDI) | none (user turns on Mercury Transmit) | TD -> AE live does not exist (no NDI in to AE comp; Syphon-in to AE: none known). |
**Forbidden shortcuts:** TD writing request files into the AE mailbox; `eval.run` (off, and read-only wins); `command.execute` (drives arbitrary menu commands even with eval off [V policy.ts]); TD opening a socket to AE (the MCP is stdio; AE has no listening port).
### 3.6 Combined sessions (which tool does what)
AE look-dev -> `ae_render_frame {times, contactSheet}` (user sees it) -> user renders ProRes 4444 (or Claude does in write mode) -> `td_create moviefileinTOP` -> `td_inspect` alpha/mean check -> composite with TD generative layer -> `td_render_for_ae` back -> `footage.replace`. Data: `ae_project_export_json` -> `td_import_ae_anim` -> TD audio-react or tempo (Ableton Link, `K`) drives the baked channels as modulation. Hap path for Resolume: out of scope here (see the Resolume file).

## 4. Proposed jazib-td upgrades
Rules respected: one structural change per call, always arrange (`td_layout flow` + check), viewers on, build-gated features noted in `FUTURE.md`, never write AE config/project files (TD writes only under `output/ae_out/`; AE writes only through the MCP's own ops).
| # | Name / args | Side | Builds / does in TD | Pairs with AE tools |
|---|---|---|---|---|
| 1 | **`td_import_ae_anim {file, format:"auto"|"ae"|"lottie", comp?, layers?, props?, mode:"baked"|"keys"|"both", rate?, parent?, name?, dry?}`** | `src/` validates (abs path, `.json`, size cap ~25 MB, under `output/` or user path), `td/handlers.py` `cmd_import_ae_anim` (pure Python bezier solver, no numpy dependency, T-48) | One COMP `ae_<comp>` (own undo block T-54): `meta`, `layers`, `keys`, `text`, `markers` Table DATs, baked table -> `dattoCHOP` -> `ae_out` Null CHOP, report DAT of warnings (expressions, spatial paths needing sampling, unsupported property types). `dry:true` returns counts + warnings only. | `ae_project_export_json {outPath: .../output/ae/<name>.json}`, `ae_layer_info {detail:"summary"}` to choose layers, `ae_do comp.sample` to bake the flagged properties |
| 2 | **`td_export_ae_data {source: chop|dat path, file, format:"csv"|"tsv"|"json"|"ae_doc", comp?:{name,w,h,fps}, simplify?: tolerance}`** | `td/handlers.py` (reads CHOP samples/ DAT cells; writes under `output/ae_out/`, ASCII-safe names) | Nothing structural; optional RDP key reduction to cap key count; `ae_doc` writes a schema-v2 doc (null/text layers + keyframes) | `ae_project_import_json {inPath, dryRun}`, or `project.import_file` + `expression.set` data-driven |
| 3 | **`td_render_for_ae {top, file?, frames, fps, codec:"prores4444"|"prores422hq"|"hapq"|"png"|"exr", alpha:"premultiplied"|"straight"|"none", loop?:true, resolution?}`** (generic offline recorder; Resolume/ComfyUI files may ask for the same: dedupe at lead level) | `td/handlers.py` recipe, `src/` runs ffprobe after (frames, pix_fmt, size) and returns a pass/fail | Recipe from T-29/T-30: **fresh** Movie File Out (never switch codec on an existing one), `videocodec prores` + `videocodectype 4444` + 12-bit alpha pixel format [D/A], `outputcolorspace srgb`; docked Execute DAT `onFrameEnd` force-cooks it; `project.realTime=False` for the take, restored after (even on error); `limitlength` in frames = N, record starts on frame 0 of the loop; straight vs premultiplied by an explicit Unpremult step before out (a Level/GLSL op; no `unpremultTOP` in the dump [D]). Verifies `nb_frames == N`. | `project.import_file`, `footage.interpret {alphaMode}`, `ae_render_frame` for the AE-side look |
| 4 | Recipe (no tool): **AE live preview** | `td_exec` | `ndiinTOP` (class-only [D]; create probe first, user opens AE Mercury Transmit), source "Adobe After Effects", then Null TOP; 1 NDI feed, Rosetta/libndi arch is [U] | `ae_version_info`, `ae_context` to confirm AE state |
| 5 | Recipe: **Lottie by Web Render TOP** | `td_exec` | `webrenderTOP` -> local `file://` HTML, lottie-web vendored in `media/` after audit | none |
| 6 | Doc: `td_guide` paragraph + `LEARNINGS` rows when tests run | docs | "AE hand-off" 8 lines: premultiplied rule, no mailbox writes, loop frame rule | - |
Cost/benefit: #1 and #3 are the useful ones (animation reuse; any TD look into AE/Resolume); #2 is cheap once #1 exists; #4/#5 recipes only.
Gate notes for `FUTURE.md`: Animation COMP key-table writer (probe-gated, any build), `kumo` v0.3.x write-mode tools once the user opens write mode, Hap-from-AE plugin once chosen. No newer-build TD feature is required by this plan.

## 5. Test plan
**Offline (no TD, no AE) - `npm test` additions:**
1. `fixtures/simple.json` (in the vendor repo) + a hand-made 3-key bezier doc -> Python bezier solver: endpoints exact, midpoint equals a numpy-free reference cubic; linear (33.33 %) matches dv/dt; hold gives steps. Pure unit test of `td/handlers.py` helpers (no `td` module, like `plan_flow`).
2. Lottie sample (hand-written, 2 layers) -> same `keys` schema; schema validator rejects non-ASCII file names (T-00a) and sizes above the cap.
3. `td_export_ae_data` -> doc passes the vendor's `validateAeProjectDoc` (run `node` against `mcp-vendor/.../dist/validate.js` with `dryRun`-equivalent; no AE).
**Live, in order:**
| # | Step | Mode | Expected |
|---|---|---|---|
| 1 | `td_status`; probe `animationCOMP` internals on a scratch COMP (`_probe_ae`), dump child DATs; probe `ndiinTOP`, `webrenderTOP` creation | TD-only | Layout of Animation COMP key tables (decides option in 3.3); NDI/Web Render create or give an OS error (T-18 style). |
| 2 | Hand-made AE JSON -> `td_import_ae_anim` (dry, then real) | TD-only | COMP built left-to-right, `td_layout check ok`, `td_errors` empty, `td_inspect ae_out` min/max match the keys, viewers on. |
| 3 | Colour/alpha chart: a TD-generated test clip (known RGB + alpha ramps) -> `td_render_for_ae` ProRes 4444 straight and premultiplied -> ffprobe -> read back in a fresh Movie File In, `premultrgbbyalpha` off/on/automatic | TD-only | Table: which combination returns original pixels (`td_inspect sample:4`); settles `automatic`. |
| 4 | `ae_version_info`, `ae_context`, `ae_project_info` (AE open on a scratch project) | **APP** (AE open; macOS Automation prompt; user's go-ahead for the first call) | Version 26.x, capabilities list, project name. Nothing changed. |
| 5 | `ae_project_export_json {outPath}` on a small test project; `ae_do comp.sample` at 5 frame times for one eased layer and one expression layer | **APP**, read-only | JSON file written; `comp.sample` values vs the TD solver within 1e-3 (non-spatial) - this validates the bezier math and shows whether spatial paths need sampling. |
| 6 | Round trip render: user (or write-mode Claude) renders a ProRes 4444 clip from AE (premultiplied) and a PNG sequence of the same comp; `ae_render_frame` sRGB PNG at frame k; TD Movie File In both; `td_inspect` grids | **APP** (user renders, or write mode with go-ahead) | Frame k pixels equal within 1-2/255 (8-bit); alpha edge halo absent; sequence frame count == movie frame count == N. |
| 7 | Loop: N-frame AE comp -> TD `specify` index loop for 10 cycles | TD-only after 6 | No hitch frame at the wrap (`td_inspect` frame diff at 0 and N-1 small, consistent with the design). |
| 8 | TD -> AE: `td_render_for_ae` clip, then write mode: `project.import_file`, `footage.interpret premultiplied`, `layer.create_footage` into a test comp, `ae_render_frame`; then overwrite file + `footage.reload` | **APP, write mode** (user's go-ahead; `AE_MCP_READONLY` off for this session only) | AE shows the clip with correct alpha; reload picks up the new take. |
| 9 | `ae_project_import_json {inPath, dryRun:true}` then real into a NEW test project | **APP, write mode** | Plan lists comps/layers/keys; real run adds a folder, `clearFirst` stays false. |
| 10 | NDI: user enables Mercury Transmit, TD `ndiinTOP` | **APP** (+ NDI Tools installed) | TD receives preview while the timeline plays; measure latency/fps; document alpha behaviour. |
| 11 | Lottie R2 (only if wanted, after audit and OK) | TD-only | Web Render TOP shows the animation; frame-seek control works over websocket. |
Every bug found -> `LEARNINGS.md` T-nn at once (rule 'bugs go in LEARNINGS').

## 6. Gates
- AE is the user's licence; MCP stays `AE_MCP_READONLY=1`, eval off. Write mode (render queue, import, keyframe/expression writes, `ae_project_import_json`, `ae_save_project`) = the user's go-ahead per session; use a copy of the project, never the show's .aep (README of the MCP advises a backup). Project data (layer names, expressions, file paths) goes to the model: say so before reading real projects (NDA).
- AE Preference "Allow Scripts to Write Files and Access Network" and the macOS Automation permission are the user's call (AUDIT). `instance.start`/`install-agent` (writes an AE Startup script) = not used.
- Never write into AE's mailbox; never write AE preferences (`pref.set`, `command.execute`); never overwrite an `.aep` from TD.
- No download without the user's OK: NDI Tools (installer), Hap plugin (disguise/AfterCodecs), Bodymovin/LottieFiles panel, lottie-web: each gets an `AUDIT.md` row (pin, licence, >= 7 days, `--ignore-scripts`, telemetry grep) first.
- Resolume rule carried over: anything Resolume receives from this chain is checked in Arena's blend (premultiplied) and needs the user's go-ahead for every Arena call.
- Claims carry levels: nothing in this file is verified live; steps 1-11 earn it.

## 7. Sources
- Pinned vendor source read: `mcp-vendor/mcp-aftereffects/{README.md,docs/TOOLS.md,src/policy.ts,src/config.ts,src/tools/{project-export,project-import,layer-info,render-frame,do}.ts,src/operations/{inspect,sample,keyframe,render,footage,project}.ts,jsx/{export,helpers,import}.jsx,fixtures/simple.json}`; `jazib-td-mcp/AUDIT.md` (import row), `AH_relevant_mcps.md` s3.
- Dump/docs here: `ops/ops_{TOP,CHOP,DAT,COMP}_2025.31550.json`, `A_td_2025_howto.md` s4, `X_tutorials_workflow_output.md` R12, `E_live_rig.md`, `C_pf26_fit.md` s3, `LEARNINGS.md` T-11/T-29/T-30/T-48/T-54.
- NDI for After Effects: https://docs.ndi.video/all/using-ndi/ndi-tools/plugins/ndi-for-after-effects
- AESyphon: https://lesterbanks.com/?p=27638 , https://cdm.link/syphon-in-your-after-effects-lets-you-map-while-you-animate/ , https://community.troikatronix.com/topic/5716/syphon-for-after-effects
- TD Movie File In TOP: https://docs.derivative.ca/Movie_File_In_TOP (premultiply/colour-space/extend/indexing wording)
- Lottie in TD thread: https://forum.derivative.ca/t/223940 (local copy `research_src/popular/forum_hot/topics/223940.json`); lottie-web https://github.com/airbnb/lottie-web ; dotLottie https://github.com/LottieFiles/dotlottie-web
- Hap from AE: https://github.com/disguise-one/hap-encoder-adobe-cc/releases , https://aescripts.com/aftercodecs/ , https://community.adobe.com/t5/after-effects-discussions/hap-codec/m-p/14148391
- ProRes 4444 alpha straight/premult mismatches (other apps): https://community.adobe.com/questions-729/exporting-premultiplied-alpha-from-premiere-1419383 , https://forum.boinx.com/t/alpha-channel-in-mimolive-layout-not-what-it-is-in-preview/17477
- AE keyframe clipboard format: https://www.npmjs.com/package/ae-keyframes , https://community.adobe.com/questions-529/export-keyframe-data-to-txt-file-29435

## 8. Open questions (for the user)
1. Will AE ever render from Claude (write mode: render queue, import) or does the user always render by hand? Decides whether `td_render_for_ae` + `footage.replace` is a closed loop or a manual hand-off.
2. Which direction matters first: AE motion -> TD (importer #1), or TD looks -> AE for compositing (#3)? Suggest #3 first (cheap, reuses T-29/T-30) then #1.
3. Alpha convention for AE deliverables: premultiplied everywhere (matches Resolume rule)? Confirm, then step 3/6 settle TD's `premultrgbbyalpha`.
4. Install NDI Tools (audited) for live AE preview, or skip live and use `ae_render_frame` + files only?
5. Is Hap from AE wanted (plugin download + audit), or is ProRes -> DXV3 via the existing pipeline enough (TD cannot write DXV)?
6. Are the user's AE projects colour-managed (ACEScg/linear) or "None"? Decides sRGB vs EXR hand-off.
7. OK to let `td_import_ae_anim` write only under `output/ae/` and `output/ae_out/` (git-ignored) and nowhere in AE's folders?
