# EVOLVING — how this MCP keeps up (user rule, 16 Oct 2026)

User: "always upgrade mcp if u encounter a new thing that u dont know — have documentation and workflow for
encountering future advances of td or bugs or instances or requests". The MCP is never "done": every new thing
met in TD ends in a better tool, a test and a doc line, in the same session.

## The loop (every time)
1. **Notice:** something unknown (an op, a par, a behaviour, an error, a crash, a request no tool covers).
2. **Ask TD, don't guess:** one `td_exec` probe; check `docs/research/ops/INDEX_<build>.json` and LEARNINGS first.
3. **Log at once:** `LEARNINGS.md` T-nn (evidence, cause, rule, TD build). Bugs before anything else.
4. **Decide the upgrade** (the smallest that stops it happening again):
   - wrong/unsafe behaviour of a tool → fix `td/handlers.py` (+ `src/server.js` if the shape changes);
   - a `td_exec` recipe used twice → a typed tool;
   - a TD fact agents need → `docs/USING_TD.md` (td_guide) or the right `docs/research/` file + its README row;
   - a user rule → memory + `CLAUDE.md` + `USING_TD.md`.
5. **Test:** offline test for the pure part (`test/test_handlers.py`, `test/offline.test.mjs`), `npm test`, then a
   live call via `node test/mcp_client.mjs` (after `td_reload` for handler edits).
6. **Document:** `docs/PROTOCOL.md` for command changes, README tool list, STATUS.md top, this file's log below.
7. **Commit** the verified change. A new tool reaches a running Claude session only after it restarts its MCP
   (say so to the user); `td_reload` covers handler-only changes.

## By trigger
| Trigger | Do |
|---|---|
| **New TD build** (Derivative release, or a different app/version opened) | Name the build in every claim. Walk `docs/FUTURE.md` (features stored for newer builds): probe, enable, test. Run `tools/op_dump.py` for all 7 families into `docs/research/ops/` (new `_<build>` files), diff the INDEX against the last one (new/removed ops, par changes), write `docs/research/ops/CHANGES_<old>_<new>.md`, rerun the live matrix (STATUS) and `npm test`; update the target build in CLAUDE.md only after the user says to switch. |
| **Bug / crash** | T-nn entry first. Crash: `pgrep -fl TouchDesigner`, newest `~/Library/Logs/DiagnosticReports/TouchDesigner-*.ips` (read the crashed thread), the CrashAutoSave path from the dialog; never reopen a CrashAutoSave as the working file. Reproduce in a scratch COMP if safe; fix or guard the tool; add a test. |
| **New TD instance / project** | One TD at a time (T-24). `td_status` names project + pid. A project without `/jazib_mcp`: drag `td/JazibTDMCP.tox` in or open `projects/JazibTD_home.toe`. |
| **New request the tools don't cover** | Research first (someone probably made it: palette, community, GitHub, Shadertoy, td-port), record it, then build: as td_exec first, then a typed tool once it repeats. |
| **New device / input** (camera, MIDI, NDI, Syphon) | Only with the user's OK for anything that opens a device or a network; record the live facts (menus, sizes, latency) in LEARNINGS + the research file. Webcam: use `media/webcam/webcam_ref_5s.mp4` unless the user asks for live. |

## Log of upgrades
- 16 Oct 2026: `td_layout` (flow/check/annotate) + always-arrange on create/connect/disconnect/delete/tox_load;
  `td_create after`; op dump tool; webcam reference clip.
- 16 Oct 2026: crash watchdog (`tools/td_watchdog.py`, `td/JazibWatchdogHB.tox`, docs/WATCHDOG.md); save_project
  backs up conflicting files first (T-37).
- 26 Oct 2026: td_exec shows what it built (viewers on, re-flow, pane follows; T-49); td_create viewer on; T-46 workaround = compute mode (T-47).
- 26 Oct 2026: td_exec visibility pass only touches the shallowest new ops (T-50); exec namespace gets TDDefinitions enums (T-51); show panel on Basic Widgets (T-52); TD window capture works.
- 26 Oct 2026: `td_window_capture` (Node side, screencapture of a TD window by CGWindowID via JXA; works with TD frozen).
- 26 Oct 2026: `td_housekeeping` read-only report (U spec section A; tidy mode waits for the user's scope).
- 26 Oct 2026: every mutating command is one TD undo step (T-54; idea from TDMCP/Embody, research AF).
- 26 Oct 2026: newer-build features are kept behind build/API gates + `docs/FUTURE.md` (user rule), never dropped.
- 26 Oct 2026: `td_help` offline op-type / par / docs lookup (Node side, src/help.js; dump + TD's shipped param help and offline wiki; research AF #6).
- 26 Oct 2026: `td_focus` (pane + select + home + opt-in 0.5 s flash, colour always restored) and `td_selection` (what the user
  points at; `this`); `_show_new` uses the same pane helper (AF #5; idea TDMCP node following, Embody get_focus).
- 26 Oct 2026: `td_inspect` numeric readback by family (research AF #4; idea from Embody/8beeeaaat/TDMCP, no code copied); numpy failure (T-48) degrades to TOP.sample + note.
- 26 Oct 2026: TD -> Resolume: `td_publish` (Syphon/NDI sender COMP, built inactive, alpha prep, Arena pick names),
  `td_publish_status` (read-only), `td_osc_learn` (OSC In logger -> `output/osc_addresses_<build>.json`); clip bake kept
  as a USING_TD recipe + FUTURE row (research AI "Proposed upgrades"; idea of learn from resolume7-fx-pipeline, rewritten).
- 26 Oct 2026: `td_net_export` + `td_net_diff`: network as JSON-lines text, snapshot and diff (AF #3; idea from Embody TDXN, MIT; diff Node-side in src/netdiff.js).
- 26 Oct 2026: `td_comfy_build/status/send/result/cancel/free`: TD-side ComfyUI client (research AL 4.2): `td/comfy_client.py` in a Text DAT, stdlib threads + Execute DAT pump, loopback only, partner-node spend guard. Own code from ComfyUI's HTTP API; no peer code.
- 26 Oct 2026: TD + Ableton (research AJ section 4): `td_link` / `td_link_status` (Ableton Link CHOP, off unless asked), `td_tda` check/load/status
  (TDAbleton palette; load needs accept_risk, Listen Only, 127.0.0.1, never Install / Library.cfg), `td_live_audio` (AC_audio file | device source,
  device inactive unless activate). Pairs with the `ableton-live` MCP in USING_TD "TD + Ableton". Live checks pending (lead).
- 26 Oct 2026: TD + After Effects (research AK): `td_import_ae_anim` (AE JSON parsed + baked Node-side, src/ae.js, exact AE
  temporal bezier), `td_export_ae_data`, `td_render_for_ae` on the shared `offline_render` recorder (T-11/T-29/T-30);
  Pending replies can chain (a finish may return a Pending). Live checks pending (lead).
- 26 Oct 2026: td_layout mode stages (mixed L->R + T->B storyboard, titled note boxes, boxes follow ops: T-66); new-COMP insides flowed (T-65); audio defaults (speaker out, default device in).
- 26 Oct 2026: td-atlas port (grigabyte/td-atlas `7cf8f57`, MIT): `td_health` (silent-failure check, two samples + cook probe, verdict in src/health.js), `td_trace` (where a TOP chain lost its image), `td_log` (call journal `logs/calls.jsonl`, every bridge call), `td_offline` (saved .toe/.tox via toeexpand on a copy), `td_save_hook` (network text beside the .toe on save, default off).
- 27 Oct 2026: MCP upgrades (research AM, AN, AY, AU; ideas ported, no code copied): `td_set_pars` hex colours,
  `td_custom_pars` mirror mode, `td_tox_save` About stamp, `td_record_chop`, td_exec dialog guard, `td_shadertoy`,
  `td_osc_expose` (+ OSCQuery, OSCToolset layout), `td_layer_mixer` + `td_cook_active`. Offline tests only
  (test/test_upgrades.py: pure helpers + a fuller fake TD for the builders); live checks pending (lead).
