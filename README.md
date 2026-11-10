# Jazib MCP for TouchDesigner

## About this repository

An MCP server that lets an AI assistant read and build a running **TouchDesigner** network: inspect and wire operators, edit GLSL, map MIDI controllers, import Shadertoy and ISF shaders, publish to Resolume over Syphon/NDI and OSC, and check the network for silent failures. I built it in October 2026 for my live-visuals work.

**How it was made:** with AI-assisted coding (Claude Code). I designed the tool set and the bridge, decided what each builder should do in a live show, tested it inside TouchDesigner and directed and reviewed the work; the AI wrote most of the lines. Development history is kept private; this is a clean public snapshot (project files, logs and scraped TouchDesigner docs removed). Third-party shaders keep the licence and credit in their headers; see `docs/research/L_shader_sources_licences.md`.

Muhammad Jazib Ali, creative technologist · [jazibali360.com](https://jazibali360.com)

---


Lets Claude read and build a running TouchDesigner network: list/inspect ops, set parameters, create and wire nodes,
edit DATs/GLSL, read errors, screenshot TOPs, capture TD's own windows (`td_window_capture`: network, panels, dialogs; needs Screen Recording), read numbers out of any op (`td_inspect`), look up ops/pars/docs offline (`td_help`), export/diff networks as text (`td_net_export`, `td_net_diff`), follow and read the user's selection (`td_focus`, `td_selection`), housekeeping report (`td_housekeeping`), send a TOP to Resolume Arena over Syphon/NDI and learn Arena's OSC addresses (`td_publish`, `td_publish_status`, `td_osc_learn`; built inactive), map MIDI controllers to any parameter with our own self-contained mapping COMP (`td_midi_build`, `td_midi_learn`, `td_midi_map`, `td_midi_unmap`, `td_midi_list`, `td_midi_bank`, `td_midi_save`, `td_midi_load`, `td_midi_status`, `td_midi_monitor`, `td_midi_simulate`, `td_midi_preset`: learn, banks, soft takeover, curves, smoothing, LED feedback; works without the MCP once built), silent-failure check (`td_health`), where an image went black (`td_trace`), call journal (`td_log`), read saved .toe/.tox with TD closed (`td_offline`), network text on save (`td_save_hook`, off by default), hex colours in `td_set_pars` (`#rrggbb[aa]`), mirror an inner op's pars onto its COMP (`td_custom_pars` mirror), About-page version stamp on `td_tox_save`, record a CHOP to a table/.csv (`td_record_chop`), modal dialogs never block `td_exec`, Shadertoy shaders as self-contained COMPs (`td_shadertoy`), ISF / VDMX shaders (multi-pass, persistent buffers, .vs) as self-contained COMPs (`td_isf`), a COMP's custom pars as OSC / OSCQuery (`td_osc_expose`, off by default), Blender-baked vertex animation textures played on their mesh at 60 fps (`td_vat_load`), Metavido volumetric clips decoded to colour / depth / world points + the recorded camera (`td_metavido`), an N-layer VJ mixer (`td_layer_mixer`) and a cooking guard (`td_cook_active`); every change is one TD undo step, add custom parameters, save .tox/.toe, run Python.

```
Claude --stdio--> src/server.js --HTTP+token--> src/bridge.js (127.0.0.1:9335)  <--WebSocket+token-- TD /jazib_mcp
```
TD dials out to the bridge; TD opens no port. Contract: `docs/PROTOCOL.md`.

## Setup (once)
1. `npm ci --ignore-scripts` (already done; deps pinned and audited in `AUDIT.md`).
2. Claude Code: `jazib-td` is registered in the bundle's `.mcp.json`. Restart Claude Code and check `/mcp`.
3. In TouchDesigner (2025.31550): open the Textport (Dialogs > Textport and DATs) and run
   ```python
   exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/td/install.py').read())
   ```
   That builds `/jazib_mcp` and saves `td/JazibTDMCP.tox`. In other projects, drag that `.tox` in instead.
   Or just open `projects/JazibTD_home.toe`: `/jazib_mcp` is saved in it and connects on its own (T-07).
   It reconnects on its own when the bridge starts; the first MCP tool call starts the bridge.

## Use
- From Claude: `td_guide` first, then `td_status`.
- From the shell: `node src/cli.js health`, `node src/cli.js status`, `node src/cli.js list '{"path":"/project1"}'`.
- One tool from the shell: `node test/mcp_client.mjs td_list '{"path":"/project1"}'`.
- Debug toolkit (any project, also ones Claude did not build; `docs/USING_TD.md` "Debugging any project"): `td_analyze`
  (X-ray + report under `output/debug/`), `td_analyze_file` (a closed .toe/.tox, no TD), `td_why` (what drives an op/par),
  `td_watch` (live recorder), `td_journal` (what the MCP did; opt-in before/after snapshots), `td_debug_panel` (on-screen
  panel in TD).

## Crash watchdog
`docs/WATCHDOG.md`: heartbeat .tox in the show project + `python3 tools/td_watchdog.py start --toe <show.toe>`.
What killed TD: `td_crash_report` (macOS .ips + `logs/td_faulthandler.log` + in-flight td_execs, matched against the
crash fingerprints `logs/crash_patterns.json` that td_exec's crash guard also uses; `docs/USING_TD.md`).

## Files
`src/` Node MCP + bridge · `td/` TD-side handlers, callbacks, installer, `midi_core.py` + `midi_runtime.py` (copied into the MIDI COMP) · `docs/` guide + protocol ·
`test/` offline tests (`npm test`) + live client · `output/` screenshots · `logs/exec.log` every td_exec · `logs/calls.jsonl` every bridge call (td_log).
