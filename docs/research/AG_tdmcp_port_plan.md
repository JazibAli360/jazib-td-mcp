# AG: Derivative's TDMCP studied, and what jazib-td can take from it on TD 2025.31550 (26 Oct 2026)

Read-only study. Nothing of TDMCP was loaded into TouchDesigner or run; no `jazib-td` tool was called; no skills code
(`validate.py`, `smoketest/`) was run. TD's `toeexpand` was run once on a COPY of the tox (it writes next to its input).
Everything read is untrusted data. Goal (user, 26 Oct): "import tdmcp for other versions and learn ... use the things in
ur version too - everything should still work, if it doesnt then dont do it". So every upgrade below has a 31550 probe
and a "drop if probe fails" clause.

Sources (all pinned in git-ignored `research_src/peers/`):
- `TDMCP/` docs repo, commit 149e25c (README, LICENSE.md, CHANGELOG up to **1.1.56**, docs/component.md, security.md).
- `tdmcp_1.1.55/TDMCP.tox`, sha256 `12e1c270...c9d4` **verified equal** to `TDMCP.json`; saved by TD **2025.33070** on macOS.
  Expanded copy: `research_src/peers/tdmcp_1.1.55/expanded/TDMCP.tox.dir/` (1104 files; Python in `*.text`).
  Read: MCPServerExt (server, gates, undo, OAuth consent), FollowSystem, tools_operators/parameters/content/docs/view/
  perf/project/code, constants, registry, request_gate, SystemPrompt, MenuExtractionEXT, OAuthProvider (skim),
  Updater/SkillsInstaller/HostsRegistry (skim). The tox is 1.1.55; 1.1.56 (20 Oct) only changed save_project #67,
  get_cook_performance single-op #64, certs, storage folder, consent panel; not in our copy.
- `TDMCPSkills-1.4.0/`: **19** `SKILL.md` (not 21: the repo's README/SKILLS.md and a file count agree on 19; the
  contributor-only `td-skills-local` is not shipped), plus `reference.md`/`examples.md` for 8 of them.

Status key used everywhere: **LIVE** = confirmed on 31550 in our `LEARNINGS.md` (T-nn) · **DUMP** = in our live dump of
31550 (`docs/research/ops/`) · **DOC** = only in the app's offline help (a newer, also incomplete mirror: official
`Pane_Class` lacks `zoom`/`home`, yet T-54 saw them live) · **PROBE** = unknown, one-line probe in section 9 ·
**NEWER** = needs a build above 31550.

## 1. Summary
- TDMCP **cannot run here**: it requires TD **2025.33230+** (README), uses Web Server DAT `localaddress` (33060+), and the tox
  was saved by 33070. The second install on this Mac (32820, arm64) is also below the floor. We do not load it (user rule).
- Its architecture is the opposite of ours: server **inside** TD (Web Server DAT on port 13316, OAuth 2.1 + consent box).
  Ours: Node stdio MCP -> token bridge on 127.0.0.1:9335 <- TD dials out (WebSocket DAT, TD opens no port). Keep ours.
- We already have what AF ranked first: **undo blocks (T-54)**, **script errors (T-55)**, forced-cook errors with GLSL
  compile logs, layout engine, housekeeping, window capture, save backups, visible work. TDMCP has none of the last five.
- Biggest real gaps (all portable): **numeric readback** (`inspect_values`), **op/par help before creating** (`get_help`),
  **offline docs lookup** (`get_docs`), **sequence-par handling** (`set_parameters`), **one-call chain build**
  (`build_network`), **screenshot sizing + non-TOP viewer** (`view_operator`), **custom-par edit/delete/sort**,
  **DAT find-replace / rows / file sync**, **per-call follow + colour flash**, **MCP tool annotations** (client auto-approval).
- Two cheap wins nobody listed: Node-only items need no TD change (annotations, `instructions`, JSON-string argument
  coercion, `td_help`, `td_docs`, screenshot downscale via `sips`); and `run(delayFrames=)` in our `_schedule` uses the
  default `delayRef=me`, which may stall on a paused timeline (TDMCP 1.1.56 moved its deferred work to the UI clock).
- Licence: LICENSE.md section 6.1 allows copy/modify/incorporate **into MCP integrations for TouchDesigner with attribution**.
  This **supersedes AF's "ideas only"** (section 10 has the text). It is revocable and carries an indemnity (8.4b): plan =
  reimplement from the idea, copy verbatim only the docs parser and skill text, attribute both.
- Skills: 11 family skills are good reference (after name fixes: 19 op-like names flagged against the 31550 dump, 5 of them prose artefacts); the persona
  skills (td-general "Your Role", td-colab, td-working-mode) **conflict with CLAUDE.md** (full access, push to next step).
- Plan: U0 plus 15 ordered upgrades (section 8); 3 are Node-only, 4 more touch both sides. About 1-1.5 days wall-clock with 3 lanes.

## 2. Architecture
| | TDMCP 1.1.55 | jazib-td |
|---|---|---|
| Transport | MCP streamable HTTP, POST `/mcp` only (no SSE), JSON-RPC on TD's main thread; protocol 2025-11-25/2025-06-18 | MCP stdio -> HTTP+`x-jtd-token` -> bridge -> WebSocket (TD dials out) |
| Auth | OAuth 2.1 PKCE + dynamic client registration + modal "Allow full control" box; 24 h tokens; localhost bind (33060+), Origin gate, JSON content-type gate, 8 MB body cap, optional LAN+HTTPS | 48-hex token file (mode 600), hello token on WS, refuses any http/https/file Origin (stricter: TDMCP trusts loopback origins), no body cap (token checked first) |
| Tools | 26 broad tools with modes, registered by 9 text DATs into `TOOL_REGISTRY` | 25 narrower typed tools + `td_exec` |
| Async | request thread cannot wait, so captures return `job_id` + `waitTime` and the client polls | `Pending(frames)`: the reply is sent from a delayed `run()`, one MCP call, no polling (better) |
| Undo | every non-read-only tool in `ui.undo` block `MCP <tool> <path>`; swallows `endBlock` error (annotateCOMP creation tears blocks down) | `MUTATING` commands in block `jazib-td: <cmd>` (T-54), `endBlock` also swallowed |
| Feedback | FollowSystem: pan + select + colour flash per tool; `View` helper network for captures | `_show_new` after exec/create (viewers on, re-flow, pane to COMP) |
| Docs/help | `TDParameterHelp.json` + 33070 menu catalog + offline/web wiki | `docs/research/ops` dump + guide; no tool |
| Guidance | MCP `instructions` = SystemPrompt DAT, 19 skills installed per client | `td_guide` = `docs/USING_TD.md` |
Lessons from its security log worth keeping: consent can never be self-granted by the caller; a missing Content-Type made a
`no-cors` page able to call tools; oversized JSON blocks the main thread; names shown in dialogs are caller-controlled.

## 3. 31550 ledger of the TD APIs TDMCP uses
| API (where) | Status on 31550 | Evidence / note |
|---|---|---|
| `ui.undo.startBlock/endBlock/undoStack`, `undo()/redo()` | LIVE | T-54 |
| annotateCOMP creation kills open undo blocks | PROBE P2 | ours already swallows `endBlock` errors |
| `OP.errors()/warnings()`, `OP.scriptErrors()/clearScriptErrors()` | LIVE | T-55 (TDMCP does not read scriptErrors) |
| `ui.panes`, `PaneType.NETWORKEDITOR`, `pane.owner`, `pane.home()` | LIVE | `_show_new` (T-49, T-51) |
| `pane.x/.y/.zoom` read and **assign** (TDMCP pan) | PROBE P1 | T-54 saw `zoom`/`homeSelected` exist; assignment untested |
| `OP.current/.selected`, `COMP.selectedChildren/currentChild` | LIVE exist (T-54); set PROBE P1 | |
| `OP.color` get/set | LIVE | `ROLE_COLORS` in layout |
| `run(script, delayFrames=)` | LIVE T-04 | `delayRef=` kwarg: DOC (Td_Module) -> PROBE P7 |
| `OP.docked` | LIVE | layout/delete (T-28) |
| `COMP.copy(op, name=, includeDocked=)`, `OP.changeType(type)` | DOC | PROBE P6 |
| `cpuMemory, gpuMemory, totalCooks, cpuCookTime, gpuCookTime` | LIVE | T-53 |
| `childrenCPUCookTime, childrenCPUMemory(), cookedThisFrame` | DOC | PROBE P5 (`cookTime` is marked Deprecated in DOC; T-05 still reads it) |
| `Par.sequence`, `Sequence.numBlocks`, `Par.reset()`, `bindExpr`, `readOnly`, `enable`, `menuNames`, `isCustom` | DOC; `bindExpr` LIVE | PROBE P4 for sequences (we have **no** sequence code) |
| `Page.sort`, `Par.destroy()`, `startSection`, `appendHeader/OP/COMP/TOP/CHOP/SOP/DAT/MAT/Folder/XYZ/RGBA` | DOC; `appendFloat/Int/Toggle/Pulse/Menu/RGB/XY/File/Str` LIVE (T-04) | PROBE P8 |
| `TOP.saveByteArray('.png')` | DOC; `TOP.save(png)` LIVE | PROBE P3 |
| `TOP.numpyArray()`, `CHOP.numpyArray()`, `TOP.sample(x,y)` | DOC | hazards T-13 (zeros right after `cook(force)`), T-48 (numpy can fail a whole session) |
| `POP.numPoints()`, `pointAttributes`, `points(attr, startIndex=, count=, delayed=)` | DOC (Experimental-POP_Class) | TDMCP itself says "verified on 2025.32820" -> PROBE P9 |
| `opviewerTOP` + par `opviewer` | DUMP | T-54 probe saw it |
| `app.build` | LIVE | T-04 |
| `app.samplesFolder/configFolder/installFolder` | DOC | PROBE P10; on disk: `.../tfs/Samples`, `.../tfs/Config` |
| `project.saveBuild/cookRate/realTime/folder/name`, `project.save(path)` | LIVE | handlers use them |
| `TDParameterHelp.json` | on disk, 5.2 MB, 662 ops, **0 `menuNames`** | read-only check; has `glslcreatePOP`, which `dir(td)` lacks: help is not proof of existence |
| TDMCP `MenuValues` catalog | **stale** | extracted from 33070; its own `menuDataStale` warning would fire |
| Web Server DAT `localaddress`, `secure`, `certificate` | NEWER (33060+) / not needed | not used by us |
| `TDFunctions`, `TDStoreTools.StorageManager`, `op.TDTox`, `op.TDResources` | `TDResources` LIVE (T-52); rest PROBE P10 | skills depend on them |
Op names in the skills vs the 682-class dump: 175 of 194 op-like tokens exist (5 of the 19 misses are prose, e.g. `materialMAT`). Wrong spellings (use the dump): `videodevinTOP`->`videodeviceinTOP`,
`audiodevinCHOP`->`audiodeviceinCHOP`, `oscCHOP`->`oscinCHOP`, `hsvTOP`->`hsvadjustTOP`, `webClientDAT`->`webclientDAT`,
`audiobandCHOP`->`audiobandeqCHOP`, `topToCHOP`->`toptoCHOP`. Absent in 31550 (likely newer or typos): `resolveTOP`, `sourcePOP`,
`forcePOP` (we have `forceradialPOP`), `animationCHOP` (only `animationCOMP`), `curveSOP` (we have `curvePOP`), `wirePOP`,
`glslcreatePOP` (documented, not in `dir(td)`). Par and menu values spot-checked OK on 31550: `normalPOP.tang=alwayscompute`,
`glslPOP.outputaccess`, `cameraCOMP.projection=ortho`, `geometryCOMP.instancerottoorder`, `feedbackPOP/particlePOP` init/start/play pulses,
`annotateCOMP` `Titletext/Bodytext/Mode`, `textDAT.language` (default `input`); 216 of 276 backticked par-like tokens exist as pars
(the other 60 are menu values, tool names, sequence blocks beyond 0).

## 4. Tool map (TDMCP 26 tools -> ours)
Effort: S <= 1 h, M ~ 3 h, L ~ 1 day (one agent). "U-n" = upgrade in section 8.
| TDMCP tool | Ours | Gap | 31550 | Effort |
|---|---|---|---|---|
| `project_info` | `td_status` | panes, selected ops, current op, rollover, perform | LIVE/PROBE P1 | S (U12) |
| `list_operators` | `td_list` | nodeX/Y/size, connection counts, overlaps, annotations | LIVE | S (U12) |
| `search_operators` | `td_list` (family/type) | name glob | LIVE | S (U12) |
| `get_operator_info` | `td_info` | flags dict, extension signatures | LIVE + DOC | S (U10) |
| `get_connections` (graph=true) | `td_info` wiring only | topological order + cycle detection | LIVE | S (U10) |
| `get_help` | none | par names/types/menus by op type | DUMP + file | M (U2) |
| `get_docs` | none | Python API / concept pages offline | 2142 pages on disk | M (U3) |
| `get_parameters` | `td_get_pars` | glob pattern, batch, **search by value/expr**, sequence counts | LIVE/PROBE P4 | M (U6) |
| `set_parameters` | `td_set_pars` | **sequences**, reset, unbind, batch, readOnly/disabled report | PROBE P4 | M (U6) |
| `pulse_parameter` | `td_set_pars` (true pulses) | none | LIVE | - |
| `edit_custom_parameters` | `td_custom_pars` (add only, 9 styles) | edit/delete/sort/rename/delete page, 12 more styles, atomic pre-validation | PROBE P8 | M (U11) |
| `create_operator` | `td_create` | idempotent reuse + re-apply, type-mismatch error (ours raises on any clash) | LIVE | S (U9) |
| `build_network` | none (`td_exec`) | ops+wires in one call | LIVE create/connect | M (U9) |
| `wiring` | `td_connect`/`td_disconnect` | ours verifies the wire after; keep | LIVE | - |
| `edit_operator` | `td_rename`, `td_move` | flags, colour, copy_to, move_to (refuse wired), change_type | PROBE P6 | M (U10) |
| `reposition_operators` | `td_layout` + `td_move` | batch dict with docked following | LIVE | S (U10) |
| `delete_operator` | `td_delete` | confirm dialog: **do not port** (user: full access; TDMCP shipped auto-accept from 1.1.51) | - | - |
| `annotation` | `td_layout annotate` | edit existing box, `Bodytext`, colour | DUMP | S (U10) |
| `get_dat_content` | `td_dat_text` | table rows with offset/limit | LIVE | S (U12b) |
| `set_dat_content` | `td_dat_text` | rows, find-replace, file sync + containment check | PROBE P11 | M (U13) |
| `get_errors` | `td_errors` | ours is stronger (force cook, GLSL log, scriptErrors); take annotateCOMP-internals skip | LIVE | S (U4) |
| `inspect_values` | none (`td_info` counts only) | CHOP values/samples, TOP pixel + grid stats, DAT preview, SOP/POP data, CHOP recording | PROBE P3/P9 | L (U7) |
| `view_operator` | `td_screenshot` (TOP, native size) | size presets/aspect, non-TOP viewer, frame sequence, delay | PROBE P3/P13 | M (U8) |
| `get_cook_performance` | `td_perf` | `budgetPct`, memory, cook counts, sort, COMP aggregates | LIVE + PROBE P5 | S (U4) |
| `execute_code` | `td_exec` | ours is stronger (logged, visible, enums, frames) | LIVE | - |
| `save_project` | `td_save_project` | ours backs up conflicts (T-37); TDMCP #57/#67 are the same bug family | LIVE | - |
Ours with no TDMCP twin: `td_guide`, `td_window_capture`, `td_layout` (flow/check), `td_housekeeping`, `td_tox_save/load`, `td_reload`.

## 5. Feature deep-dives
### 5.1 Undo blocks (done; two refinements)
`_handle_tool_call` wraps every tool whose annotations are not `readOnlyHint` in `ui.undo.startBlock("MCP <tool> <path>")` ...
`finally: endBlock()` inside try/except, because creating an annotateCOMP ends all open blocks ("Cannot end non existent undo
operation"). Ours is the same shape (`undo_block`, T-54, live). Take: (a) put the target path in the block name so Edit > Undo
reads "jazib-td: create /project1/x"; (b) PROBE P2: after `layout annotate`, is the undo stack one entry or two? Delayed
(`frames`) commands already run their finish inside a block. No 31550 risk.
### 5.2 Network-editor follow + flash ("visible work v2")
TDMCP, after each tool: pick the target op (`path`, `to_path`, last created, `parent_path`), find a NETWORKEDITOR pane (reuse one
already on that COMP, else retarget the first), set `target.current=True; selected=True`, ease-out-cubic the pane `x/y` (and `zoom`
for home/reposition) over `Followtime` seconds with chained `run(delayFrames=1)`; `home()` then read the result to zoom out only
if reposition pushed ops off-screen. Flash: per category colour (inspect blue, edit amber, view violet, delete red, eval teal) by
interpolating `op.color` with smoothstep and restoring the exact original (rapid calls keep the first original; generation
counters cancel stale chains). Ours does only the post-exec re-flow + `pane.home`. Port as an **opt-in** layer (U14); it needs
pane `x/y/zoom` assignment (P1) and that colour writes add no undo entries (P12). Risks: it changes the user's selection and
op colours while they work; a TD save during a flash would persist a tinted colour (TDMCP restores on the last frame only).
Drop if P1 fails (keep `owner` + `home`).
### 5.3 Offline `get_docs`
Sources: `app.samplesFolder/Learn/OfflineHelp/https.docs.derivative.ca` (the macOS spelling; 1.1.53 fixed the case) or the live
wiki (5 s urllib calls on the main thread). A normalised index (`[a-z0-9]` only) maps `noiseTOP` -> `NoiseTOP_Class.htm`
(python) or `Noise_TOP.htm` (concept); exact names with `_`; fuzzy fallback. Class pages inline the whole inheritance
(~10K tokens), so the default shows only operator-specific members + the inheritance chain, `section=` drills (labels like
"Members (TOP Class)"), content is capped at 30,000 chars. Parser = stdlib regex (slice `mw-content-text`, balanced-div TOC
strip, headings -> sections, `<code>` -> backticks). On 31550: all 2142 pages are on disk and `NoiseTOP_Class`, `OP_Class`,
`Undo_Class`, `Td_Module` resolve. Two namespaces: official pages and `Experimental-*` (most POP pages, newer features). Warn
when only an Experimental page matches. The mirror is newer and incomplete, so answer "what does the API do" from it but
decide "does it exist on 31550" by probe. **Do it Node-side** (static files, works with TD disconnected or frozen); skip the web path.
### 5.4 Par/menu lookup before set (`get_help`)
TDMCP merges `TDParameterHelp.json` (label, summary, parType; **no menu names**) with its own `MenuValues` catalog (33070) and
warns when `app.build` differs. TD silently turns an unknown strict-Menu value into index 0, so `_menu_value_error` rejects it and
returns `details.valid_values`. Ours already matches menus by name or label and warns on a miss (live). Gap = looking up an op type
**before creating it**. Better data than TDMCP's: our dump `ops_*_2025.31550.json` has name, label, page, style, default, `menu`,
`menuLabels`, ranges for 507 ops; the other 175 classes (153 not creatable, 22 failed) get names/labels/summaries from
`TDParameterHelp.json` without menus. Filter machine-specific menus (`device`, `font`, `localaddress`, `targetaddress`) like TDMCP #25/#52.
Sequence pars: only block 0 exists in the dump; document `const0name` style and expand via section 5.8.
### 5.5 Capture and images
`view_operator`: TOP -> helper `resize_helper` -> `saveByteArray('.png')`; non-TOP -> `opviewerTOP` three frames later; preset =
pixel **budget** (tiny ~128x128, low ~640x360, high ~1280x720) reshaped to the source aspect, never upscaled, longest edge <= 2048 (#49);
`frames>1` = grid built by a **pixel-mode GLSL TOP + Feedback TOP** (the T-46 hazard on this Mac: avoid, or it can show stale
cells); `delay_frames` and `pre_pulses` fire triggers in the same tick; one capture at a time; inline base64 or a cached file.
`inspect_values(sample_grid=8)` is the cheap pixel check (needs `numpyArray`, so T-13/T-48 apply). Ours returns the full 1080x1920
PNG. Take: `sips -Z` downscale in Node (already used by `td_window_capture`), `opviewerTOP` for non-TOPs (P13), a frame **sequence** as
several image blocks (no GLSL grid), `delay_frames` via `Pending`.
### 5.6 Error and cook tracing
`get_errors`: `errors()` + `warnings()` for every child, skips anything inside an annotateCOMP (its cloned internals report false
errors), adds the `<name>_info` text when "Compile failed". `get_cook_performance`: `cookTime`, `cpuCookTime`, `gpuCookTime`, `budgetPct
= cookTime * rate / 10`, COMP `children*CookTime`, optional memory/cook counts, sorts, `top_n`. Ours already force-cooks (T-02), reads the
GLSL log, adds scriptErrors (T-55). Take: the annotateCOMP skip (ours `findChildren()` walks into boxes: false positives) and the perf fields.
### 5.7 One-call chain build (`build_network`)
Creates ops and wires them in one undo block; same-name same-type ops are **reused and their parameters re-applied** (retry converges);
a different-type clash is an `operator_type_mismatch`, and wires to refused names are not made; partial success reports
`failed_ops`, `failed`, `param_errors`, `success:false` and the MCP result gets `isError`. `auto_layout` = longest-path columns,
barycentre rows, 175x125 pitch. Ours: `plan_flow` is better (bands, docks, spine) and `td_create` raises on any clash. Take the API
shape and the convergence rule; keep our layout and wire verification; run `td_errors` on the COMP at the end. T-31 (crash after several
structural changes) is the reason to gate on a live 12-op stress test.
### 5.8 Sequences, resets, batches (`set_parameters`)
`const3name` on a 1-block constantCHOP auto-expands `sequence.numBlocks` (regex `prefix<N>suffix`, block 0 must exist); `{'reset':true}`,
`{'unbind':true}` (freeze value, clear expr/bind, force CONSTANT), batch `{opName:{par:val}}`, readOnly/disabled pars are skipped and reported.
We have none of the sequence code, and constantCHOP, glsl `vec`/`const`, mathmixPOP all need it.
### 5.9 Consent and security
Not ported: OAuth, consent box, `Yolomode`, mkcert/HTTPS, LAN scope, the rate gate (it exists because its server blocks the main thread; ours
returns after the bridge timeout). Worth copying as ideas: MCP **tool annotations** (`readOnlyHint` for reads so clients stop prompting;
SDK 1.32.1 supports `annotations`), MCP `instructions`, `_coerce_arguments` (clients double-serialise arrays/objects as JSON strings, our zod
would reject them), `isError` when a result says `success:false`, and the structured error contract `{error, details:{code, valid_values...}}`.
Overlap: TDMCP's `SystemPrompt` rules (null at chain ends, `optype_purpose` names, relative paths) overlap our guide.

## 6. What we do better (keep)
Dial-out transport + hello token; stricter Origin rule; save with conflict backup (T-37); forced-cook errors incl. GLSL log + scriptErrors; flow/check/annotate
layout engine and housekeeping report; `td_window_capture` (works while TD is frozen); logged, visible `td_exec` with TD enums; Pending replies in one call;
full 31550 knowledge base and live dump.

## 7. Skills (19 SKILL.md, 1.4.0)
Loaded into an agent, a skill is instructions. We copy them only as **reference docs** (never auto-installed), and leave the `td-` prefix to
TDMCP (our own Claude skills, if ever, would use `jtd-`). Checks below are against the dump, LEARNINGS and the offline docs.
| Skill | Teaches | Conflicts / 31550 problems | Adopt |
|---|---|---|---|
| td-general | role, workflow, skill map, naming, paths, tool prefs, gotchas, token frugality | **"Your Role" = thinking partner, resist auto-building, ask before build** contradicts CLAUDE.md ("push to the next step", full access). Absolute paths banned in pars (we use absolute for tools: fine). "Never absTime.seconds" is advice, not a defect | Sections only: naming, paths, gotchas, token frugality. Not the role |
| td-colab | collaboration persona | Direct conflict (above) | No |
| td-working-mode | agent blind to layout; route to code-on-disk + verify | Premise outdated here (we have flow layout + `td_window_capture`); code-on-disk mechanic is good if P11 passes | Mechanic only |
| td-build-planning | scout, plan, positions, 6 phases, pitfalls | Position maths (175/125/210) conflicts with our `td_layout` flow (gaps 95/60); pitfalls are gold: in*/out* before wiring, `connectorder`, pbr needs env light, partial-build orphans, camera far clip | Pitfalls + phases |
| td-review-network | PASS/WARN/FAIL checklist, trace upstream | Uses `get_errors`/`inspect_values`/`view_operator` names; fine otherwise | Yes, short form in USING_TD |
| td-network-cleanup | alignment, annotations, padding 25/60 | Uses `reposition_operators`; "never networkbox mode" (ours uses annotateCOMP: fine); **Bodytext** for explanation, we only set Titletext | Bodytext rule only |
| td-node-layout | 175x125 pitch, Y up, DAT sandwich, annotation maths | Differs from G_network_layout / `plan_flow`; do not change our numbers without the user | Compare, no change |
| td-performance-check | operators over Python, selective cooking, time without overflow | None found | Yes (reference) |
| td-top-family | TOP sources/chains, formats, pitfalls | `videodevinTOP`, `hsvTOP`, `resolveTOP` wrong or absent; "Alpha-blended render corrupts alpha" matches our T-12 | Yes + name fixes |
| td-chop-family | CHOP chains, patterns, pitfalls | `audiodevinCHOP`, `oscCHOP`, `animationCHOP`, `audiobandCHOP` wrong/absent | Yes + name fixes |
| td-pop-family | POP lifecycle, glslPOP, attributes, pitfalls | POPs were younger on 31550 (T-35: Feedback POP macOS crash fixed after 31550; Mac has no Ray POP); `sourcePOP`, `glslcreatePOP` absent; many pitfalls are about later builds | Yes with a "verify live first" banner |
| td-sop-family | SOP ops | **"Always prefer POPs over SOPs"** is wrong as a rule for 31550/Mac (T-35); `curveSOP` absent | Op list only |
| td-mat-family | MAT types, pbr env light, pointsprite, glslMAT | `wirePOP` typo; sample `CloudyOcean_2Kx1K_8bit.tif` exists in our `Samples/Map` | Yes |
| td-glsl-shaders | GLSL TOP/MAT/POP API, uniforms, docked DATs | **Multi-pass `npasses`/feedback recipe conflicts with T-46/T-47** (use compute mode on this Mac). "Prefer glslmultiTOP": both have identical pars here; its tearing is unprobed. Vulkan notes agree with T-10 | Yes with an override banner |
| td-dat-family | callbacks, execute-DAT source pars, sync to file | "Edit on disk, TD live-reloads" contradicts our USING_TD ("editing a file changes nothing") unless `syncfile` is on: PROBE P11 | Yes after P11 |
| td-comp-architecture | shortcuts, in/out ops, custom pars, clones | None; custom-par naming = T-00e | Yes |
| td-python-extension | ext0object, promotion, StorageManager, scriptTOP | `findChildren(type=textDAT)` without `maxDepth=1` crawls into annotateCOMPs (our handlers use `findChildren()`); needs P10 | Yes |
| td-geometry-instancing | instancing pars, POP direct feeds | Cross-check with T-15 (`instanceop` vs `instancepop`=pivot); pars exist in DUMP | Yes |
| td-lister-ui | Lister/TreeLister recipe (19 colDefine rows) | `op.TDTox` PROBE P10; Palette `UI/lister.tox` exists; our panel uses Basic Widgets (T-52) | Yes (reference) |
Adoption plan: copy tier "Yes" to `docs/research/tdmcp_skills/<skill>/` with the section 10 header, a "31550 check" banner listing the fixes above, and
one index row in `docs/research/README.md`; hand-merge tier "sections only" into `docs/USING_TD.md`; skip the rest. Not before the user answers Q1. Do not run
`validate.py`; its provider-term filter (no "Claude", no `.claude/`) is a useful idea for our own skill checks only.

## 8. Port plan (ordered; lanes: N = `src/` Node, H = `td/handlers.py`, D = docs)
Always: ASCII-only in `td/` (T-00a); `node --check src/server.js && npm test` before every commit (T-56); `td_reload` after handlers edits; one structural change
per live call + `td_errors` (T-31); LEARNINGS entry for every surprise; commit each verified step. Tests = `npm test` (Node 13 + Python 59) plus the live call named.
| U | Upgrade | Side | Probe first | Test | Drop if probe fails |
|---|---|---|---|---|---|
| U0 | NOTICE + licence record (section 10); reference copies only after Q1 | D | none | review | - |
| U1 | MCP tool `annotations` per class (read-only / mutating / destructive), server `instructions` (short guide), JSON-string argument coercion, `isError` when a result has `success:false` | N | SDK 1.32.1 accepts both (checked in `mcp.d.ts`/`index.d.ts`) | offline test: tools/list shows hints; coercion unit test | n/a |
| U2 | `td_help`: op type -> pars/labels/styles/defaults/menus from the dump + `TDParameterHelp.json` summaries; family listing; near-name suggestions; session-menu filter | N | file present and loads (checked: 5,239,153 bytes, 662 ops) | node test on `noiseTOP.type`, an unknown op, a non-dumped op | n/a (offline) |
| U3 | `td_docs`: offline wiki lookup (resolver + section drill + 30k cap + Experimental flag); no web path | N | none needed: dir has 2142 pages; `NoiseTOP_Class.htm`, `Undo_Class.htm` exist (checked read-only) | fixture pages + node test; live `td_docs noiseTOP` | n/a |
| U4 | `td_errors`: skip annotateCOMP internals; `td_perf`: `budgetPct`, memory, `totalCooks`, sort, `top` | H | P5 (COMP aggregates) | fake-op unit tests; live on `/project1` | aggregates only |
| U5 | Error contract: `code` + `details` in replies; invalid strict-menu value returns `valid_values`; block name carries the path | H | P2 | unit tests | path in block name only |
| U6 | `td_set_pars`: sequence auto-expand + `sequences`, `reset`, `unbind`, batch over several ops, skipped readOnly/disabled report; `td_get_pars`: glob, search by value/expr, sequence counts | H+N | P4 | unit + live on a scratch constantCHOP (`const0name`..`const3name`) | sequences part |
| U7 | `td_inspect`: CHOP channels/samples, TOP sample + NxN grid stats, DAT preview, SOP counts, POP attributes, CHOP record via per-frame sampling (no View helper) | H+N | P3 (numpy now), P9 (POP) | unit on fakes; live per family; numpy read one frame after cook (T-13); `import numpy` guard (T-48) | POP part / numpy-free fallbacks |
| U8 | `td_screenshot` v2: `maxSize` via `sips`, non-TOP through `opviewerTOP`, `frames`/`step` as several images, `delay` | N+H | P3, P13 | node test for resize; live TOP + CHOP + COMP | non-TOP viewer |
| U9 | `td_build`: ops[] + wires[] in one undo block, reuse-and-converge, mismatch error, wire verification, `_arrange`, auto `td_errors` | H+N | live 12-op stress on a scratch COMP (T-31) | unit + live | if a 12-op build stalls TD: keep `td_exec` |
| U10 | `td_edit` flags/colour/copy/move/retype (move refuses wired), `td_move` batch with docked following, `td_layout annotate` edit + Bodytext, `td_info` flags + extension signatures + graph order | H | P6 | unit + live | copy/move/retype |
| U11 | `td_custom_pars` v2: edit/delete/sort/rename/delete page, 12 more styles, validate-all-first | H | P8 | unit + live | missing append types |
| U12 | `td_status` panes/selection/current/rollover; `td_list` geometry + overlaps + name glob; `td_dat_text` rows paging | H | P1 | unit + live | selection part |
| U13 | `td_dat_text` find-replace and file sync (`file_content`, explicit `file_path`, containment check #26, set `language`) | H | P11 | unit + live edit-on-disk | file sync |
| U14 | Follow + flash (opt-in): target pan/select, category colour flash, exact restore | H | P1, P12 | fake-pane unit; live visual check with `td_window_capture` | all, keep `owner`+`home` |
| U15 | Robust timing: `run(..., delayRef=op.TDResources)` in `_schedule` and follow chains, so a paused timeline cannot stall replies | H | P7 | unit; live with timeline stopped then restored | revert |
Lanes after U0-U1: N (U2, U3, U8 resize) | H-a (U4, U5, U15, U6) | H-b (U10, U11, U12, U13, U9) | D (reference copies). U7 and U14 last (largest, most
live risk). Estimate: serial ~4 days; 3 lanes ~1-1.5 days. H-a and H-b touch one file: merge by function, never edit `handlers.py` from two agents at once.

## 9. Probe sheet (td_exec one-liners; run only with the user's go-ahead; scratch names are unique per T-20; all clean up after themselves)
- P1 panes: `p=[x for x in ui.panes if x.type==PaneType.NETWORKEDITOR][0]; a=(p.x,p.y); p.x=a[0]+1; ok=(p.x!=a[0]); p.x=a[0]; (ok,p.zoom,hasattr(p,'home'),hasattr(p,'homeSelected'),op('/project1').selectedChildren)`
- P2 undo vs annotate: `u=ui.undo; u.startBlock('probe'); a=op('/project1').create(annotateCOMP,'_probe_ann'); a.destroy(); n=len(u.undoStack); u.endBlock()` (expect an exception text or `n`; read it, do not guess)
- P3 byte array: `len(op('<any TOP>').saveByteArray('.png'))` and `op('<TOP>').sample(x=0.5,y=0.5)`
- P4 sequences: `c=op('/project1').create(constantCHOP,'_probe_seq'); s=c.par.const0name.sequence; n0=s.numBlocks; s.numBlocks=4; r=(n0,s.numBlocks,hasattr(c.par,'const3name')); c.destroy(); r`
- P5 aggregates: `c=op('/project1'); (c.childrenCPUCookTime,c.childrenGPUCookTime,c.childrenCPUMemory(),c.childrenGPUMemory(),c.totalCooks,c.cookedThisFrame)`
- P6 copy/retype: `p=op('/project1'); a=p.create(nullTOP,'_probe_a'); b=p.copy(a,name='_probe_b'); c=b.changeType(selectTOP); r=(c.OPType,); a.destroy(); c.destroy(); r`
- P7 delayRef and pause: `r=run('1',delayFrames=1,delayRef=op.TDResources); type(r).__name__`; then pause test with restore: `root.time.play=False` (frames=0), next call `td_exec code='"alive"' frames=2` (a timeout means a paused timeline stalls Pending), finally `root.time.play=True`
- P8 custom pars: `c=op('/project1').create(baseCOMP,'_probe_cp'); pg=c.appendCustomPage('P'); pg.appendHeader('Hd'); pg.appendOP('Opx'); f=pg.appendFloat('Val')[0]; f.startSection=True; pg.sort('Val','Hd'); f.destroy(); r=[x.name for x in pg.pars]; c.destroy(); r`
- P9 POP data: `n=op('<any POP>'); (n.numPoints(),[a.name for a in n.pointAttributes],n.points('P',startIndex=0,count=2))`
- P10 modules and paths: `import os,TDFunctions as TDF,TDStoreTools; (app.samplesFolder,app.configFolder,os.path.isdir(os.path.join(app.samplesFolder,'Learn','OfflineHelp','https.docs.derivative.ca')),hasattr(TDF,'createProperty'),hasattr(TDStoreTools,'StorageManager'),hasattr(op,'TDTox'))`
- P11 file sync: `d=op('/project1').create(textDAT,'_probe_sync'); r=(hasattr(d.par,'syncfile'),hasattr(d.par,'file'),d.par.language.eval()); d.destroy(); r`; then write a file, set `file`+`syncfile`, edit the file on disk, read `d.text` two frames later (also: does GLSL recompile).
- P12 colour flash: `o=op('/project1'); c=tuple(o.color); n0=len(ui.undo.undoStack); o.color=(0.9,0.6,0.1); r=(tuple(o.color),len(ui.undo.undoStack)-n0); o.color=c; r`
- P13 viewer for non-TOP: `v=op('/project1').create(opviewerTOP,'_probe_pv'); v.par.opviewer=op('<any CHOP>'); v.cook(force=True); r=(v.width,v.height); v.destroy(); r` (then save bytes one frame later)

## 10. Licence and attribution (decision needed: Q1)
Both repos' LICENSE.md = "Shared Use License" + "TDMCP Tool Terms of Use" (rev. 14 Apr 2026); the Terms prevail. Section 6.1 grants a revocable, royalty-free licence to "use,
copy, modify, and incorporate the TDMCP Tool, in whole or in part, into your MCP integrations for TouchDesigner", provided "appropriate attribution to Derivative Inc. as the original
author" is included in any Derivative Works. Also in force: Shared Use (keep the notice and conditions; no use of Derivative's name to endorse; use only with TD and as a TD licensee: we hold
Pro, T-09); 4.2 Anthropic-use limits (no standalone image/video/audio generation service, ads, financial transfers, extracting the AI service's memory; none applies to jazib-td); 5.1 node
names, parameter values and errors may reach the AI provider (same as today); **8.4(b) indemnity** for Derivative Works we distribute; 9.2 on termination delete copies.
Text for `NOTICE-TDMCP.md` (repo root): the two LICENSE.md texts verbatim, then: "Portions of jazib-td-mcp are adapted from TDMCP (c) Derivative Inc.,
https://github.com/TouchDesigner/TDMCP (docs commit 149e25c; release 1.1.55, TDMCP.tox sha256 12e1c270171cd35f3b91377ee9c4e833ff42d4e6fa298b9269ed24d5f321c9d4) and TDMCPSkills 1.4.0, under TDMCP Tool Terms
section 6.1. Modified. Derivative Inc. does not endorse jazib-td-mcp." plus a table: file / function / what changed.
Per-file header for adapted code or text: `Adapted from TDMCP (c) Derivative Inc. (tools_docs: html parser) under TDMCP Tool Terms 6.1; modified by Jazib <date>: <summary>. See NOTICE-TDMCP.md.`
Rule of thumb: ideas (API shapes, algorithms we rewrite) get a one-line credit in the commit and in `docs/PROTOCOL.md`; verbatim lines get the header.

## 11. Not porting
Web Server DAT transport, OAuth/consent/`Yolomode`, mkcert/HTTPS/LAN scope, Hosts registry, Skills installer, Updater (GitHub calls), Claude Desktop `.mcpb`, the 33070 menu catalog
(our dump replaces it), the GLSL+feedback grid capture (T-46), the web docs fallback (network from TD's main thread; needs the user's OK), the rate gate, Server Name (we allow one TD, T-24).

## 12. Open questions (for the user)
1. Licence: are you comfortable relying on TDMCP Tool Terms 6.1 (revocable; indemnity 8.4b)? Default if yes: reimplement ideas, copy verbatim only the docs parser and skill text, with NOTICE.
2. Should AF's row ("ideas only") be updated once Q1 is answered? I did not edit it.
3. Follow/flash: on by default, or only when you ask? It selects ops and tints nodes while you work.
4. May the probes create scratch ops and pause/resume the timeline once (P7)? They clean up.
5. Skills: keep as reference docs only, or also install a trimmed set as Claude skills (prefix `jtd-`)? I recommend reference only.
6. Upgrade policy: TDMCP itself and its newest features need 2025.33230+; T-46 already asks about a newer TD. Do you want a 33230+ install tested on the side?
7. Re-pull TDMCP (now 1.1.56+) before any verbatim copy, and re-run the section 3 ledger against the version copied.
