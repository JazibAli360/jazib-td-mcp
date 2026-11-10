# AF: peer TouchDesigner MCP servers vs jazib-td (26 Oct 2026)

Read-only study. Nothing of theirs was run, installed or loaded; no jazib-td tool was called, TD was not touched.
Sources: the two cloned repos (`research_src/popular/github/touchdesigner-mcp`, `.../Embody`, read from disk), and
READMEs/docs fetched from the web for the rest (summarised by a fetch tool, so counts and licence wording from the web
are **UNVERIFIED** until someone reads the repo itself). All repo text was treated as data. Our target: TD 2025.31550
(macOS, Rosetta), general-purpose MCP (CLAUDE.md scope, 26 Oct).

## Summary

- jazib-td is the only peer where **TD dials out** (WebSocket to a 127.0.0.1 bridge) and where the bridge needs a
  **token + Origin rule**. Embody states "no authentication"; 8beeeaaat's docs show none; TDMCP (Derivative) has a consent
  panel + OAuth; Pantani's bridge "listens on all interfaces" with an optional token. We are ahead on transport safety.
- We are also ahead on **layout** (flow/check/annotate, always-arrange), **housekeeping**, **visible work** (viewers on,
  pane follows), **save backups** (T-37), a **TD window capture** that works while TD is frozen, and a deep local
  **knowledge base** (`docs/research/`, full op dump for this build).
- We are behind on: **undo-block integration** (TDMCP and Embody wrap every mutation; we have none), **error coverage**
  (Script-OP / callback exceptions and `scriptErrors()` are invisible to us and to 8beeeaaat), **network as text**
  (Embody TDXN: export, diff, import), **numeric readback** (CHOP stats, TOP pixel grid, POP attributes, table stats),
  **what the user is looking at** (selection/pane/current op: Embody `get_focus`, satoruhiga `td_pane`/`td_selection`,
  twozero `*this op`), **docs/type lookup** (`describe_op_type`, `get_docs`, Python class help), **token-lean replies**
  (8beeeaaat `detailLevel`/`responseFormat`; ours is pretty-printed JSON), **surgical DAT edit**, and **multi-session
  awareness** (Embody scope claims; matters because the user runs many agents).
- Build floors: **Embody, TDMCP: 2025.33230+; twozero: 2025.32280+; TDPilot: 2025.30000+ baseline; 8beeeaaat: "latest",
  no floor stated.** We are on 31550, so we cannot run Embody or TDMCP at all; everything below is ideas to
  re-implement, probed on 31550 first (EVOLVING.md step 2).
- Licences: 8beeeaaat, Embody, satoruhiga, bottobot, Pantani, TDPilot are **MIT** (code may be adapted with the
  copyright notice kept). Derivative's TDMCP is a **custom "Shared Use" licence**: ideas only. twozero: closed `.tox`,
  no licence shown: ideas only.
- The ranked top 10 upgrades are below the gap table; the first three (undo blocks, 3-surface errors, network export+diff)
  are the best value for the least risk.

## Our baseline (what the comparison is against)

25 tools (`src/server.js`): `td_guide`, `td_status`, `td_window_capture` (Node-side), `td_list`, `td_info`, `td_get_pars`,
`td_set_pars`, `td_create`, `td_delete`, `td_rename`, `td_move`, `td_connect`, `td_disconnect`, `td_layout`,
`td_dat_text`, `td_errors`, `td_screenshot`, `td_custom_pars` (add only), `td_tox_save`, `td_tox_load`,
`td_save_project`, `td_perf`, `td_housekeeping`, `td_exec`, `td_reload`. Protocol v1 (`docs/PROTOCOL.md`): JSON over a
WebSocket TD opened to the bridge; `frames` replies for errors/screenshot/exec; 1627 lines in `td/handlers.py`; offline
tests (`npm test`, `test_handlers.py`) plus a live client. Replies are `JSON.stringify(o, null, 1)`. No undo blocks, no
`scriptErrors()`, no selection/focus read, no docs lookup, no numeric CHOP/TOP/POP readback, `td_screenshot` takes only
`path` (full-size PNG inline).

## Peer 1: 8beeeaaat/touchdesigner-mcp (602 stars, MIT, v2.1.0, pushed 12 Oct 2026)

- **Architecture:** Node MCP server (stdio, or streamable HTTP with Host/Origin checks) -> HTTP to a **WebServer DAT**
  inside `mcp_webserver_base.tox` (default port 9981) -> Python `api_controller` / `api_service`. TD **opens a port**.
  OpenAPI schema -> generated client (orval), so both sides share a typed contract. Docker image, MCP bundle for Claude
  Desktop, npm package, Codex and Claude Code **plugin marketplace** entries.
- **Tools (14):** `create_td_node`, `delete_td_node`, `get_td_nodes` (filter, pattern), `get_td_node_parameters`,
  `update_td_node_parameters`, `get_td_node_errors`, `get_td_info`, `get_top_image`, `execute_python_script`,
  `exec_node_method`, `get_td_classes`, `get_td_class_details`, `get_td_module_help`, `describe_td_tools`.
  **Prompts (3):** search node, node connection, check node errors. No resources.
- **Notable:** (1) **response shaping**: every tool takes `detailLevel` (minimal|summary|detailed) and `responseFormat`
  (json|yaml|markdown), plus `limit`: token-optimised presenters. (2) **Errors and warnings** with a careful report:
  warnings included (missing files, dangling refs and shader failures are warnings), multi-line message grouping,
  an explicit "no errors is not healthy" rule, and honesty fields saying what could not be read. Their debug skill also
  states what they cannot see: **Script OP / Execute DAT callback exceptions land on neither stream**. (3)
  `get_top_image` is a Python script over the exec channel: base64 JPEG, optional downscale through a temporary
  resolutionTOP destroyed in `finally`. (4) **Python API introspection** tools (`help()` of td modules). (5) **Version
  handshake**: component `mcpApiVersion` vs `minApiVersion` / `expectedApiVersion` table (ok / warn / stop). (6)
  **Claude Code plugin with 8 skills** (setup, launch, debug, perf, snapshot, fundamentals, overview, python-api) and a
  **PostToolUse hook** that injects "verify this mutation" after create/update/delete/exec. The `launch` skill opens the
  `.tox` as a document (`open -a TouchDesigner x.tox`) so TD starts with the component loaded, also on macOS. (7) A pure
  `node_layout.py` (grid placement, no `import td`) unit-tested outside TD. (8) Tests: vitest unit + integration + e2e
  for stdio/HTTP, pytest for the TD-side parsers; CI plugin-sync checks.
- **TD build / OS:** "latest recommended"; Node 22.18+/24/26. macOS and Windows both handled in skills.
- **Weak spots vs us:** no auth beyond localhost; WebServer DAT port open in TD; no layout flow/check, no
  housekeeping, no undo, no focus read, no network export.
- **Licence:** MIT (c) 2025 sadao komaki. Code can be adapted with notice.

## Peer 2: dylanroscover/Embody (209 stars, MIT, v6.2.76, pushed 25 Oct 2026)

- **Architecture:** a big `.tox` (Embody + **Envoy**) holding an MCP server **inside TD**: worker thread runs the MCP SDK
  2.x server (uvicorn, streamable HTTP, `127.0.0.1:9870`), a main-thread `_onRefresh` queue executes every TD call
  (Event+Queue handoff). A Python **STDIO bridge** (`envoy-bridge.py`) turns stdio into HTTP and adds meta-tools that work
  while TD is down (`get_td_status`, `launch_td`, `restart_td`, `list_dialogs`, `dismiss_dialog`, `switch_instance`).
  A **liveness watchdog** revives the socket after `project.save()` / reinit. Host/Origin validation, **no
  authentication** (stated). Optional **Convoy** = LAN relay between machines (18 `convoy_*` tools). Per-project `.venv`.
- **Tools:** docs list ~46 TD tools + 24 bridge/convoy tools ("70"). Groups: operator management (`create_op`,
  `create_extension`, `delete_op`, `copy_op`, `rename_op`, `get_op`, `query_network`, `find_children` with tags/text/comment
  filters, `cook_op`); parameters (`set_parameter`, `get_parameter` with **parameter search** by glob/substring over a
  subtree); DAT (`get_dat_content` text|table|**stats**, `set_dat_content` with **wipe guardrail**, `edit_dat_content`
  = surgical old/new string); **data readback** (`get_chop_data` min/max/mean/std per channel, `get_pop_data`);
  flags (`get/set_op_flags`); layout (`get_network_layout`, `set_op_position`, `layout_children`); annotations (4);
  connections (`connect_ops`, `disconnect_op`, `get_connections`, COMP connectors); performance
  (`get_op_performance`, `get_project_performance` incl. FPS, dropped frames, GPU temp; `run_soak_test` as a background
  **job**); `execute_python` (auto-lints raw `create()` left at 0,0 and **threading misuse**: thread target calling
  `run()`); diagnostics (`get_op_errors` over **three surfaces**: cook errors, `OP.scriptErrors` tracebacks tagged
  `kind: script`, GLSL `shaderErrors`; `exec_op_method`; `describe_op_type`; `get_docs`; `get_guidance`; **`get_focus`**);
  TDXN (`read_tdxn`, `export_network`, `import_network`, `diff_tdxn`); capture (`capture_op`, `capture_top`);
  multi-session (`get_sessions`, `claim_scope`, `release_scope`, `announce_task`, `update_task`, `preflight_landing`);
  logs/tests/jobs (`get_logs`, `run_tests` background, `get_job_status`); `batch_operations`.
- **Notable:** (1) **Every mutating call is wrapped in `ui.undo.startBlock` / `endBlock`** (one undo step per batch;
  stale-flag self-heal after 60 s; `endBlock` can raise after an annotateCOMP creation tears blocks down, so it is
  guarded). (2) **TDXN**: network as YAML, non-default parameters only, `=expr` / `~bind` prefixes, type defaults hoisted,
  connections by name, DAT text as block scalars; round-trips; claimed ~20-90x fewer tokens than per-op reads (their
  claim, unmeasured here). `diff_tdxn` compares live network to the on-disk file. (3) **`get_focus`**: current pane
  network, selected ops, current op, rollover. (4) **`capture_op`** renders non-TOP families through a transient OP
  Viewer TOP; `capture_top` returns a file path (inline base64 off by default, JPEG q80, 640 px) and a `sample_grid`
  NxN RGBA readback. (5) Protection of its own host COMP from `destroy`/`reload`. (6) Compact replies by default,
  opt-in `details`. (7) Docs site, `.claude/rules` + skills served by `get_guidance`, unit tests that run inside TD.
- **TD build / OS:** **2025.33230+**, Windows and macOS (macOS path partly "unverified at time of writing" in the
  provisioning doc). No Rosetta statement.
- **Weak spots vs us:** no token; TD opens a port; save blocks the main thread 15 s+ and restarts the server (their note:
  not for shows); heavier install (wizard, venv, auto-updater); a floor above ours.
- **Licence:** MIT (c) The Experiential Company, LLC. Adaptable with notice.

## Peer 3: satoruhiga/claude-touchdesigner (128 stars, MIT, 11 commits, Feb 2026)

- **Architecture:** Claude Code **plugin** + `toe/TouchDesignerAPI.tox` that starts an MCP server inside TD; Node MCP
  client connects to TD on **port 44444** (`TDAPI_PORT`). TD 2025+, Node, Claude Code.
- **Tools (4):** `td_execute` (Python), `td_pane` (current network editor state), `td_selection` (selected ops),
  `td_operators` (list at a path). One skill `td-guide`: families, layout patterns, Geometry COMP instancing, rendering
  setup, GLSL for TOP/MAT/POP, feedback loops.
- **Notable:** the only one besides Embody/twozero built around **what the user has selected / is looking at**.
  Minimal surface, everything else via Python. No errors tool, no screenshots listed.
- **Licence:** MIT. OS unstated (port instructions for macOS/Linux/Windows).

## Peer 4: TouchDesigner/TDMCP (Derivative, official, public beta, 62 stars, Oct 2026)

- **Architecture:** `TDMCP.tox`, MCP server **inside TD**, streamable HTTP on `127.0.0.1:13316/mcp`; Claude Desktop via a
  `.mcpb` extension. **Consent panel** on first connection ("Allow full control"), authentication on by default
  (OAuth tokens in `~/Library/Application Support/Derivative/TDMCP` on macOS, so macOS is a supported path), localhost
  only by default, optional HTTPS, rate limiting (slow threshold 5 s, cooldown 1 s), **node following** (the network
  editor follows/highlights nodes the agent touches), "ask before delete" with an auto-accept option, no telemetry.
  Skills live in a separate repo (`TDMCPSkills`) and are installed per client from the tox.
- **Tools (26, from `docs/component.md`; args not listed there):** `project_info`, `list_operators`, `search_operators`,
  `get_operator_info`, `get_connections` (also a COMP's full signal flow), `get_help` (parameter names, types, menu
  values per op type), `get_docs` (Python API + operator articles; docs source auto/web/local), `get_parameters`,
  `set_parameters`, `pulse_parameter`, `edit_custom_parameters` (add, edit, sort, rename, delete), `create_operator`,
  **`build_network`** (create + wire several operators in one call), `wiring`, `edit_operator` (rename, copy, move,
  retype, flags, colour), `reposition_operators`, `delete_operator`, `annotation`, `get_dat_content`,
  `set_dat_content` (optionally synced to a file), `get_errors`, **`inspect_values`** (channels, pixels, points, cells),
  `view_operator`, `get_cook_performance`, `execute_code`, `save_project`. **All non-read-only tools run in an undo
  block.**
- **TD build / OS:** **2025.33230+**; macOS state folder is documented.
- **Licence:** custom **"Shared Use License"** (Derivative owns the software; use/modify only together with TouchDesigner
  and under Derivative's TD licence; redistribution of modified versions must keep notices; no using Derivative's name to
  endorse derived products; the separate "TDMCP Tool Terms" add attribution to Derivative for derivative works, restrict
  some AI-provider uses, and prevail on conflict). Summary from a fetch tool, **UNVERIFIED**. We read README and docs
  only; **no code copied or planned**. Ideas (undo block, build_network, inspect_values, node following) are generic and
  also appear in MIT peers.

## Peers 5-8: found, lighter notes

- **bottobot/touchdesigner-mcp-server** (80 stars, MIT, v3.0.0): a **docs-only** stdio MCP, no live TD link (the web
  server/WebSocket bridge is "temporarily shelved"). 21 tools: operator reference (661 ops), 14 tutorials, 214 Python
  classes, version system, GLSL patterns, workflow transitions, network templates. Its data is for generic builds
  (2025.32820 + older); **our `docs/research/ops/INDEX_2025.31550.json` is a live dump of our own build and is better**.
  MIT: its tutorial/GLSL JSON could be mined if audited (AUDIT.md rules).
- **Pantani/tdmcp** (55 stars, MIT, Aug 2026): Node server + bridge inside TD on port 9980, **508 tools** in layers
  (artist-level generators such as `create_audio_reactive`, `create_feedback_network`, `create_particle_system`;
  building blocks such as `create_control_panel`, `animate_parameter`, `create_external_io`; atomic CRUD), recipe gallery,
  a create -> verify -> preview thumbnail loop, auto left-to-right layout, optional Ollama RAG. Security note: bridge
  "listens on all interfaces", token/exec-off by env var only. Interesting as a design pole (many high-level tools)
  that we should **not** copy: it multiplies tool count and prompt cost; our rule is typed tools only when a td_exec
  recipe repeats (EVOLVING.md).
- **dreamrec/TDPilot** (16 stars, MIT, v2.4.x, Mac install script): **114 tools**: "brain" planning against 659 operator
  cards, **transactions** (preflight, snapshot, rollback, diff/restore), parameter bounds, technique memory
  (learn/save/recall/replay recipes), vision/stream capture, knowledge store. HTTP 9981 + WS 9982; TD 2025.30000+;
  Python 3.10+. Worth watching for **snapshot / restore** and **recipe memory** ideas; much heavier than we need.
- **twozero** (`twozero-team/twozero-td-mcp`, 28 stars, no licence shown): closed `twozero.tox` plugin, MCP at
  `localhost:40404`, TD **2025.32280+**, handles multiple open TD instances, "safe mode" (plan before change), `*here`
  and `*this op` triggers (current network / selection), project error ranking, structure compare, performance
  analysis. Ideas only; the tool list is not public in the README. Others seen in the search (benoitliard/touch-mcp,
  29 tools over WebSocket, no licence; johnsabath, no licence; several small MIT ones) were not read.

## Gap table

H/M/L = value for us as a general-purpose MCP on 31550/macOS. Effort: S under half a day, M about a day, L multi-day.
"Licence-safe" = the closest peer implementation is MIT (adapt with notice) or the idea is generic; **idea** = re-implement
from scratch.

| Feature | Who has it | Ours | Value | Effort | Licence-safe to adapt |
|---|---|---|---|---|---|
| Undo block around every mutation | TDMCP, Embody | no | H | S | idea (generic API `ui.undo`); Embody MIT |
| Errors: Script-OP / callback tracebacks (`scriptErrors()`) | Embody | no | H | S | Embody MIT |
| Errors: honesty fields ("could not read X", "empty is not healthy") | 8beeeaaat | partial (GLSL log only) | M | S | 8beeeaaat MIT |
| Network as YAML/text export | Embody (TDXN) | no | H | M | Embody MIT |
| Network diff vs saved snapshot | Embody (`diff_tdxn`), TDPilot snapshots | no | H | M | Embody MIT |
| Network import from text (round trip) | Embody | no (tox only) | M | L | Embody MIT |
| What the user has selected / is viewing | Embody `get_focus`, satoruhiga, twozero | no (pane only used to move it) | H | S | satoruhiga/Embody MIT |
| Numeric readback: CHOP stats, TOP pixel grid, POP attrs, table stats | Embody, TDMCP `inspect_values` | no (screenshot only) | H | M | Embody MIT |
| Op-type describe (pars/menus before creation) | Embody, TDMCP `get_help` | offline INDEX json, no tool | H | S | idea; own data |
| Python API / module help | 8beeeaaat, Embody, bottobot | no (td_exec `help()`) | M | S | 8beeeaaat MIT |
| Docs lookup (official wiki) | TDMCP `get_docs`, Embody `get_docs`, bottobot | docs/research only | M | M | idea (wiki fetch needs user OK) |
| Token-lean replies (detail level, format, limit) | 8beeeaaat | no (pretty JSON) | M-H | S | 8beeeaaat MIT |
| Surgical DAT edit (old/new) + wipe guard | Embody | no (`td_dat_text` whole) | M | S | Embody MIT |
| DAT table read + stats | Embody | text only | M | S | Embody MIT |
| Parameter search across a subtree | Embody | no | M | S | Embody MIT |
| Find by tag / text / comment | Embody | list by family/type only | M | S | Embody MIT |
| Op flags get/set (bypass, lock, viewer, display) | Embody, TDMCP | no (td_exec) | M | S | MIT |
| Custom par edit / rename / delete / sort | TDMCP | add only | M | S | idea |
| Copy op, retype op | Embody, TDMCP | no | L-M | S | idea |
| Batch build (several ops in one call) | TDMCP, Embody | no, and T-31 says one structural change per call | M | M | idea |
| Screenshot: downscale, JPEG, file-only, non-TOP via viewer | Embody, 8beeeaaat | PNG full-size inline, TOP only | M | S | Embody MIT |
| TD window capture while frozen | Embody (dialogs), ours | **yes** | - | - | n/a |
| Dialog list / dismiss | Embody | window list only | L | M | Embody MIT |
| Layout flow / check / annotate | ours (peers have grid or `layout_children`) | **yes** | - | - | n/a |
| Housekeeping report | none | **yes** | - | - | n/a |
| Project perf (FPS, dropped frames, GPU mem), soak job | Embody | per-op cook times only | M | M | Embody MIT |
| Background jobs (long tasks, status poll) | Embody | no | L-M | M | Embody MIT |
| Multi-session awareness (claims, task ledger) | Embody | no (T-24: one TD) | M | M | Embody MIT |
| Auth: token + origin rule, TD opens no port | ours (TDMCP: consent + OAuth) | **yes** | - | - | n/a |
| Consent / ask-before-delete / read-only mode | TDMCP | no (full access by user choice) | L-M | S | idea |
| Exec lint (threading `run()`, 0,0 piles) | Embody | piles handled by visible pass; no threading lint | L-M | S | Embody MIT |
| Protect own host COMP | Embody | `_protected` | - | - | n/a |
| Version handshake (API compat table) | 8beeeaaat | `protocol:1` in hello, no table | L | S | MIT |
| Launch TD with the tox / restart | 8beeeaaat skill, Embody bridge | watchdog + home .toe | L | S | MIT |
| MCP prompts and skills | 8beeeaaat (3 prompts, 8 skills), TDMCPSkills | one `td_guide` doc | M | S | MIT |
| PostToolUse "verify" hook | 8beeeaaat | rule in USING_TD only | M | S | MIT |
| Snapshot / restore / rollback | TDPilot | tox_save by hand | M | M | TDPilot MIT |
| Recipes / technique memory | Pantani, TDPilot | docs/research | L | L | MIT; deliberately skip |
| Tests | 8beeeaaat (vitest + e2e + pytest), Embody (in TD) | offline + live client | - | - | n/a |

## Top 10 upgrades (ranked)

Each: tool, args, side, TD-build note. "Probe first" = one `td_exec` on 31550 before building (EVOLVING.md step 2).

1. **Undo blocks around every mutating command** (H, S). Side: `td/handlers.py` `dispatch`. For cmds in a set
   {set_pars, create, delete, rename, move, connect, disconnect, dat_text(set), custom_pars, tox_load, layout(flow),
   exec} call `ui.undo.startBlock('jtd <cmd>')` before and `ui.undo.endBlock()` in `finally`, with the Embody guards:
   a stale-flag reclaim after 60 s and a swallowed `endBlock` error (annotateCOMP creation tears blocks down). `exec`
   with `frames>0` runs later: no block. New optional arg on `exec`: `undo:false`. Reply gains `undo:true`. Result: the
   user presses Ctrl+Z in TD to revert any agent step (strong fit with "full access" and the user watching live). Probe
   first: `ui.undo.startBlock` exists and works on 31550 (the API is old, but unverified here). Test: pure helper for the
   guard in `test_handlers.py`. Caveat: does not cover file writes (tox_save, save_project).

2. **Errors on all three surfaces + honesty fields** (H, S). Side: `cmd_errors` in `handlers.py`, doc in PROTOCOL.
   Add per item `kind: cook|script|shader`, read `o.scriptErrors()` (Python tracebacks from Script OPs, Execute DAT
   callbacks, expressions) next to `errors()` / `warnings()`; keep the GLSL info-DAT log as `shader`. Reply gains
   `unread:[paths]` (an op whose stream raised), `scanned:n`, and a one-line `note` when the list is empty
   ("empty is not proof the op cooked"). Same args. Also log script errors into `housekeeping`. Probe first:
   `OP.scriptErrors()` signature and that it returns text on 31550 (Embody calls it as `child.scriptErrors()`).
   This closes a known blind spot: an exception in a callback shows nowhere in today's `td_errors`.

3. **Network as text: `td_net_export` and `td_net_diff`** (H, M). Side: new cmd `net_export` in `handlers.py` (reads
   structure) + Node-side diff/snapshot store in `src/` (`output/snapshots/<name>.txt`). Args: `td_net_export
   {path, depth=1, dat_text=true, max_dat_chars=2000, save?:"name"}` returns compact YAML: per op `type`, `xy`, non-default
   pars only, `=expr` / `~bind` prefixes, wires as `[srcName, ...]` by input index with `null` gaps, tags, flags, DAT
   text as block scalars; custom pars grouped by page. `td_net_diff {path, against:"name"|file}` compares a live export to
   a saved one and lists added/removed/changed ops and pars (diff in Node, no TD round trip for the compare). Reuses
   `cmd_info` / `par_obj` / `par_differs`. Use: show Claude a whole COMP in one cheap read, compare attempts, checkpoint
   before a rebuild (replaces some `td_tox_save` backups). Phase 2 only if wanted: `td_net_import` (rebuild ops from
   text, through the same create/set/connect code so T-00c and layout still apply). No newer-build dependency
   (everything is classic OP API), but TDXN fidelity (locked content, clones) is Embody's to solve: skip cloned and
   locked ops with a note.

4. **`td_inspect` numeric readback** (H, M). Side: new cmd `inspect` in `handlers.py`; tool in `server.js`. Args:
   `{path, channels?:glob, samples?:0, grid?:0, attrs?:glob, max_rows?:20}` by family. CHOP: per channel min/max/mean/
   std/first/last (cap 32 channels; samples adds head/tail). TOP: `grid=N` (2..32) returns an NxN RGBA array and mean/min/
   max over the full texture (`numpyArray()` per image; T-48 says numpy may be broken in a session, so fall back to
   `sample()` or report). DAT table: row/col counts, per-column min/max/mean or distinct counts, head/tail rows. POP/SOP:
   point count and attribute metadata (reading values is a GPU->CPU readback: flag `values:true` opt-in, capped).
   Answers "is it actually moving / not black / in range" without a screenshot. Probe first: POP attribute API on 31550
   (POPs are new; `docs/research/ops/POP.md`).

5. **`td_focus`: what the user is looking at** (H, S). Side: new cmd `focus` in `handlers.py` (we already walk
   `ui.panes` in `_show_new`). Returns `{pane_path, pane_type, selected:[paths], current, rollover, viewer_flag_ops?}`
   (`pane.owner`, `owner.selectedChildren`, `owner.currentChild`, `ui.rolloverOp`). Rule for `USING_TD`: "this node"
   means the selected/current op, not the rollover. Optional later: a "node following" mode like TDMCP (pane follows and
   highlights touched nodes) which our visible-work pass already half does (T-49). Probe first: `ui.rolloverOp` and
   `selectedChildren` names on 31550.

6. **`td_help`: type, class and docs lookup** (H-M, S then M). Side: Node (`server.js` reads
   `docs/research/ops/INDEX_2025.31550.json`) for `{op_type, pattern?, page?, menus?}` giving parameter names, labels,
   styles, defaults and menu values for an op **type** before creating it (no TD needed; we already own the dump); plus a
   `help` cmd in `handlers.py` for `{class|module, member?}` using `inspect`/`help()` on `td` classes (as 8beeeaaat's
   `get_td_class_details` / `get_td_module_help`). Phase 2: `docs` lookup of the official wiki, only with the user's OK
   to fetch (EVOLVING rule on downloads), cached under `docs/research/refs/`. Replaces many `td_exec` probe round
   trips and the T-26/T-36 "does the op exist" check becomes a tool.

7. **DAT: surgical edit and table mode** (M, S). Side: `cmd_dat_text` + schema in `server.js`. New tool `td_dat_edit
   {path, old, new, replace_all=false}` (fails unless `old` is unique, like the Edit tool; returns a short context
   snippet and the compile/error state after a frame), `td_dat_text` gains `format:"text|table|stats"` and
   `confirm_wipe` (refuse empty `text` on a non-empty DAT unless confirmed). GLSL and Script DAT iteration shrinks
   from "resend the whole shader" to a few lines; the T-02 compile log can ride in the reply.

8. **Token-lean replies** (M-H, S). Side: `src/server.js` `text()` helper + per-handler options. Today every reply is
   `JSON.stringify(o, null, 1)`. Change the default to compact JSON (no indentation), add optional `detail:
   "min|summary|full"` and `limit` on `td_list`, `td_info`, `td_get_pars`, `td_errors`, and a `format:"json|yaml|md"` for
   list-like replies (tables in markdown are cheaper for lists of ops). Keep `td_info` default as non-default pars only
   (already). Measure before and after on a 50-op COMP and note the numbers in LEARNINGS (our rule: claims need evidence).

9. **Multi-session scope claims** (M, M). Side: `src/bridge.js` (it is the one shared process: every Claude session's
   `server.js` talks to it) + two tools. `td_claim {scope:"/project1/foo", ttl_s=300, note}`, `td_release {scope}`,
   `td_sessions {}`; the bridge records the claimant id (a per-`server.js` uuid sent in `/ctl`) and refuses mutating cmds
   from another session under a claimed prefix with a clear message (`td_exec` is exempt but logs a warning). Cooperative,
   expiring leases like Embody's `claim_scope`. Needs a short live test with two sessions. No TD-side change.

10. **Screenshot v2** (M, S). Side: `src/server.js` `td_screenshot` + `cmd_screenshot`. Args: add `maxSize` (default 1280;
    downscale in TD through a temporary resolution TOP destroyed in `finally`, or in Node with `sips -Z`, which
    `td_window_capture` already uses), `format:"png|jpg"`, `inline:true|false` (false = file path only, Claude can
    Read it), and for non-TOP ops a viewer-based capture (an OP Viewer TOP created in a scratch COMP, rendered a few
    frames, destroyed: Embody's `capture_op`). Cuts the image tokens of every verify step. Probe first: OP Viewer TOP
    renders non-TOP families on 31550 (viewer compute may differ on the Vulkan build).

Also-ran (not in the top 10, with reason): `td_build` batch create+wire (conflicts with T-31 one structural change per
call; revisit after #1 gives one-step undo); project FPS / dropped-frame monitor + soak job (M, good for PF26 shows,
needs a background-job mechanism: do after #9); read-only "show mode" env (`JTD_READONLY=1` rejecting mutating cmds)
and ask-before-delete (user chose full access; offer, don't impose); exec lint for threads calling `run()` (cheap, add
with #1); MCP `prompts` + a verify reminder hook for debug/perf/snapshot workflows (S, M; a Claude Code settings change,
needs the user); flags/find/par-search/custom-par edit tools (S each, bundle as "TDMCP parity" later); dialog
list/dismiss (our window capture already shows dialogs); snapshot/restore (covered by #3 + tox_save); recipe memory and
generator tools like Pantani's (skip by design).

## Newer-build notes

- Floors of the peers: Embody/TDMCP 2025.33230, twozero 2025.32280, TDPilot 2025.30000 baseline (2025.33070 supported;
  they bind the Web Server DAT to loopback by default on that build, i.e. older builds did not). We are on 31550 and
  `EVOLVING.md` says switching the target build waits for the user. Anything that reads a TD API added after 31550 (some `OP.scriptErrors` variants, POP readbacks,
  `ui.*` helpers Embody calls) must be probed on 31550 and degrade to a `note`, never crash the command.
- Only #6 phase 2 and #3 phase 2 depend on anything beyond the 31550 OP API; #1, #2, #4, #5 are probe-then-ship.
- T-46/T-47 (GLSL pixel-mode tearing) and T-48 (numpy) affect #4 and #10 captures: always capture from the real output
  path, and treat numpy failure as an `unread` item.

## Licences

| Project | Licence | Our use |
|---|---|---|
| 8beeeaaat/touchdesigner-mcp | MIT (c) 2025 sadao komaki (LICENSE file read) | Adapt with copyright notice in the file header and AUDIT.md row |
| dylanroscover/Embody | MIT (c) 2020-present The Experiential Company, LLC (LICENSE read) | Same; their TD-side code needs 33230+ APIs, so re-implement against 31550 and cite |
| satoruhiga/claude-touchdesigner | MIT (web summary, UNVERIFIED) | Same |
| bottobot, Pantani/tdmcp, TDPilot | MIT (GitHub metadata) | Same; data from bottobot must be audited |
| TouchDesigner/TDMCP (Derivative) | Custom "Shared Use License" + Tool Terms (summary UNVERIFIED) | **Ideas only**: no code, no skills text. Not clone-and-copy; do not use the Derivative name |
| twozero | none shown, closed `.tox` | Ideas only |
| benoitliard, johnsabath | none listed | Ideas only (not read) |

Rule for anything we do adapt: put source file + licence + commit in `AUDIT.md` first (CLAUDE.md dependency rule),
keep the notice in the file header, prefer re-writing the small functions against our own handlers.

## Open questions

1. Does `ui.undo.startBlock` / `endBlock` nest and behave inside our `dispatch` on 31550, and what happens when a command
   creates an annotateCOMP (Embody says it tears blocks down)? One probe settles it.
2. Does `OP.scriptErrors()` exist and return text on 31550, and does it include Execute DAT callback exceptions?
3. Does the OP Viewer TOP render CHOP/DAT/COMP on this Rosetta/Vulkan build (needed for non-TOP capture)?
4. Token numbers: how much do the peers' claims (TDXN 20-90x, detail levels) really save on our own COMPs? Measure
   `td_info` + `td_get_pars` over a 50-op COMP vs an export before committing to phase 2 of #3.
5. User call: do you want ask-before-delete or a read-only show mode, given full access was your choice (16 Oct)?
6. User call: may an agent fetch the official TD wiki for `td_help` phase 2 (a download needing your OK)?
7. Should one of Embody's `.claude/rules` / skills texts be reviewed for ideas on `td_guide` structure (MIT, readable
   offline in the clone), or do you prefer to keep `USING_TD.md` as the single guide?
8. Re-check periodically: Derivative's TDMCP is in public beta; its tool list and licence may change, and a future
   switch of our target build would reopen it as a possible host-side alternative.
