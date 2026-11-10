# Audit: everything Jazib MCP for TouchDesigner imports (16 Oct 2026)

Rule (user, 15 Oct): audit, pin, free licence, fully local, nothing phones home.

## Dependencies
The exact set already audited for `../jazib-gflow-mcp/AUDIT.md` (16 Oct 2026). The lockfile was copied from there
(only its own name/version header changed) and installed with `npm ci --ignore-scripts`, so every package and
sha512 matches that audit.

| Package | Version | Released | Licence |
|---|---|---|---|
| `@modelcontextprotocol/sdk` | 1.32.1 | 2026-10-05 | MIT |
| `ws` | 8.22.0 | 2026-09-26 | MIT |
| `zod` | 4.6.5 | 2026-09-13 | MIT |

`npm ci`: 0 vulnerabilities. Re-checked here: `grep -rlE 'posthog|sentry\.io' node_modules`: no hits.
The SDK's HTTP-transport deps are present but unused (stdio only).

TD side (`td/`): Python standard library + TouchDesigner's own `td` module only. Tests: stdlib `unittest`.

## Our own code
- `src/bridge.js` listens on 127.0.0.1 only. Both sides need the 48-hex token in
  `~/Library/Application Support/JazibTDMCP/token` (mode 600; never stored in the .tox). A request or upgrade with
  an `http:`/`https:`/`file:` Origin is refused, so a web page can't drive TD.
- TD opens no port: its WebSocket DAT connects out to the bridge.
- Nothing auto-updates. Nothing contacts any server; all traffic is loopback.
- `td_exec` is arbitrary Python inside TD by design (user's choice); every call is logged in `logs/exec.log`.

## Import: TD-Toxes by Aaron Myles Pereira (26 Oct 2026)
- Source: https://github.com/aaronmylespereira/TD-Toxes, commit `af4697dc9b61d7c29e1d3c4a13501dfe2c819ec8`.
- Licence: MIT, (c) 2024 Aaron Myles Pereira (`LICENSE` in the clone). Caveat: 8 of the 9 README effects are re-builds of other
  creators' free YouTube tutorials (no licence stated for those networks): study material, rebuild natively, don't ship the files.
- What it is: 11 `*_MYLES.tox` + README (the brief said 12), 0.7 to 5.4 KB each, saved on macOS 14.4/14.5 with build
  2023.11600 (feedback: 2023.11760), Apr to Jun 2024. Not a dependency: research material only.
- Checked: expanded each with `toeexpand` (TD 2's helper) in a scratch folder, one folder per tox; read every op file and DAT text;
  cross-checked every op type and non-custom par name against `docs/research/ops/INDEX_2025.31550.json`. Nothing was loaded into
  TouchDesigner, no `jazib-td` tool used, no code from the files run. Searched all text for imports, `os`/`subprocess`/socket/URL/
  `webbrowser`/`exec`/`eval`/`open`, GLSL, Script/Web/Network DATs, external `.tox`, absolute paths.
- Found: no GLSL, no network, no subprocess, no imports. Python is limited to CHOP Execute / Parameter Execute / Panel Execute
  callbacks that set a local op's bypass or button state, plus TD's own stock Palette `DocsHelper` extension (inside the embedded
  Palette `sharpen` and `feedbackEdge`; loaded from `op.TDResources`, opens the Derivative docs URL only if you press Help). Only URL
  string: `https://www.derivative.ca`. File access: Palette fallbacks read `app.samplesFolder` media (read-only, exist here);
  `randomVideoFile` lists and opens files from a user-set folder; it ships the author's own path
  (`/Users/aaronpereira/.../Adidas x Magnanimous/OUTPUT`, does not exist here). Dangling references to the author's project
  (`keyboardin1`, `null2`, `select1['ch1n76']`, stored input wires) only produce error flags. All op types exist in 2025.31550.
- Verdict: **safe to load, all 11**, into a scratch COMP (not the home rig), then `td_errors`; verification level is "read",
  nothing was run. Details, per-file table and adapt ranking: `docs/research/Y_td_toxes_myles.md`.
- Kept in git-ignored `research_src/TD-Toxes/` (not committed, not imported by anything).

## Adapted idea: Embody TDXN (26 Oct 2026)
| What | Source | Licence | How |
|---|---|---|---|
| Network-as-text export + diff (`td_net_export`, `td_net_diff`): non-default pars only, `=`/`~` prefixes with doubling escape, wires by name, custom pars by page, DAT text | `research_src/popular/github/Embody` (dylanroscover/Embody, `docs/tdxn/specification.md`) | MIT | Idea and conventions only; own code, own JSON-lines format (stdlib), attribution comments in `td/handlers.py` and `src/netdiff.js`. No Embody file copied or run. |

## Data, not code: ComfyUI partner-node class names (26 Oct 2026)
| What | Source | Licence | How |
|---|---|---|---|
| `PARTNER_NODES` in `td/comfy_client.py` (267 class names; the spend guard of `td_comfy_send`) | local ComfyUI v0.34.5 `~/ComfyUI-Installs/JZB1/ComfyUI/comfy_api_nodes/*.py`, every `node_id="..."` | GPL-3.0 (ComfyUI); names only | A list of identifiers read with grep; no code copied. The client is our own, written from ComfyUI's HTTP routes (server.py). TDComfyUI / ComfyUI-TD not used. Safety: stdlib threads, loopback HTTP only (other hosts refused, proxies bypassed), writes only under `output/comfy/` and ComfyUI's `input/jazib_td/` (via /upload/image). |
## Runtime use: TDAbleton palette (Derivative, ships in TD 2025.31550) (26 Oct 2026)
| What | Source | Licence | How |
|---|---|---|---|
| `td_tda load` loads `tdAbletonPackage.tox` (v2.6.3, author Ivan DelSol) from the TD app's palette; no code copied into this repo | `/Applications/TouchDesigner 2.app/.../Samples/Palette/TDAbleton/Live 11+/` (read with `toeexpand` in the scratchpad, 26 Oct) | part of TouchDesigner | Runs Derivative's TDAbletonExt in TD; its OSC In DAT `oscin_system` listens on UDP 58811 (Inport) once loaded; sends OSC only to 127.0.0.1:58888/51111 (we set Abletonaddress). Its Live-side Remote Script (not installed by us) binds 0.0.0.0:58888 and accepts `/shell/runCode`: so `load` needs `accept_risk`. We never press Install (it edits Live's `Library.cfg`), Update, Start or Auto-Start Live. |
## Adapted code: td-atlas (26 Oct 2026)
| What | Source | Licence | How |
|---|---|---|---|
| `td_health` (health_sample / health_probe / script_errors_recheck + verdict rules), `td_trace` (walk + marks), `td_save_hook` (sidecar name, atomic write, not-ours guard), call journal + redaction patterns, offline `.toe`/`.tox` readers (`.text` 27-byte prologue, `.parm` flag bits 0x10/0x200/0x200000, `.n` blocks, `.table`) | grigabyte/td-atlas `7cf8f57fa486ea5f8ef7259c07b0f68c72f714c5` (`research_src/community/files/75403/repo/`: `src/td_atlas/component/handler.py`, `bridge/health.py`, `bridge/trace.py`, `journal.py`, `project/formats.py`, docs) | MIT (lead: licences irrelevant for porting; source noted) | Logic adapted and rewritten into our layout (Python ASCII in td/handlers.py; Node src/health.js, src/journal.js, src/offline.js) with source comments. None of its code was run; no dependency added. `toeexpand` is TD's own binary (`/Applications/TouchDesigner 2.app/Contents/MacOS/toeexpand`), run only on a copy under output/offline/. |

## Adapted ideas, no code copied (27 Oct 2026)
| What | Source | Licence | How |
|---|---|---|---|
| hex colours, mirror pars, About stamp, record CHOP, dialog guard | dylanroscover/TDXComponents `1433c7b` (Hexler, Optimeister, Chop Recorder, About page) | GPL-3.0 | read only (research AM); our own code in td/handlers.py |
| `td_shadertoy` wrapper | SebastienGravel/ShaderToyTouchdesigner (idea) + Shadertoy's documented uniforms | none stated | own wrapper (research AN); shader licences are per shader (CC BY-NC-SA 3.0 default), kept on the COMP |
| `td_osc_expose` OSCToolset layout + OSCQuery JSON | eusebijucgla/OSCToolset (UE plugin source, address schema) + OSCQuery spec / OSC Query Server 62663 (idea) | GPL-3.0 / MIT | schema only (research AY); no remote-exec route; loopback defaults |
| `td_layer_mixer`, `td_cook_active` | black-pomeranian/VJ-System_Sample (allowCooking per source idea) | none stated | read only (research AU) |

## Import: third-party MCP servers into `mcp-vendor/` (26 Oct 2026, user: "sure add resolume mcp ... ableton live mcp ... yes on after effects and comfyui")
Audit and reasons: `docs/research/AH_relevant_mcps.md`. Registered in the bundle's `.mcp.json` (backup `.mcp.json.bak-20261026`). Gates: `mcp-vendor/README.md`.
| Server | Source / pin | Licence | Installed with | Verified | Telemetry | Notes |
|---|---|---|---|---|---|---|
| `resolume-723` | mackatwentytsuru/resolume-mcp-server `901cc9e1cf738d06089352d26a93b0babe43cb85` (v0.5.4 + fixes, 2026-10-19) | MIT | `npm ci --ignore-scripts && npm run build` (build runs its own `scripts/gen-tool-index.mjs`: local fs only, read first); sdk 1.29.0, zod 3.25.76 | handshake: 37 tools (stability=stable, 2 hidden); no tool called; with RESOLUME_CACHE off it contacts nothing at startup | none (grep hits = OSC "segment") | for Arena **7.23** (user's show build; author claims live test vs 7.23, unverified by us). Every call = user's go-ahead. `resolume_osc_send` sends any OSC path. |
| `resolume-arena` | Resolume's bundled server `/Applications/Resolume Arena/mcp/resolume_arena_mcp_server`, sha256 `aba9368fe7f9a837f0c029ddf813f490077eedb1b48fbce6d924d536478a9184` | proprietary (Resolume) | nothing to install | `--help` only (options: -v) | none found in strings (AH) | needs Arena **7.26+**; kept for later (FUTURE rule). Re-hash after any Arena update. |
| `aftereffects` | kumoproductions/mcp-aftereffects `73fea51220c9b2a8a5afbb95e50c37e0ad08e978` (v0.3.2, 2026-10-16) | MIT | `npm ci --ignore-scripts && npm run build`; sdk 1.32.1, zod 4.6.7 | handshake with AE_MCP_READONLY=1: 9 tools (2 withheld); AE not launched (no osascript until a tool call) | none | eval off; npm audit: body-parser/fast-uri advisories in SDK transitive deps (HTTP side; stdio only here). AE pref "Allow Scripts to Write Files..." = user's call. |
| `ableton-live` | wstierhout/ableton-live-mcp `55abd3a38a74c39f6f2fc0d1d90107d06ec5f952` (v1.8.1, 2026-09-16) | MIT | `uv sync --frozen`; `install` wrote only `~/Music/Ableton/User Library/Remote Scripts/AbletonMCP/__init__.py` (sha256 43c56bfe...0a3f56) | handshake: 108 tools (toolsets session,tracks,clips,devices); doctor: script installed + matches, not reachable until Live loads it | none (2 docstring words) | no read-only switch: set-changing tools wait for the user's OK. Socket 127.0.0.1:9877, no auth. Uninstall: `mcp-server-ableton-live uninstall`. |

## Blender + Blender MCP (26 Oct 2026, user: "blender integration is yes for now")
| What | Source / pin | Licence | Installed with | Verified | Telemetry | Notes |
|---|---|---|---|---|---|---|
| Blender app | Homebrew cask `blender` 5.2.2 (dmg sha256 `dc4125399b8bfefe283cc1624d6cfc7809d1cac20ace51072127eb371f31f210`, download.blender.org, 15 Sep 2026) | GPL | `HOMEBREW_NO_ANALYTICS=1 brew install --cask blender` | `Blender -b --python-expr` prints `5.2.2 LTS`; spctl (info only): notarized, Blender Foundation | Blender's own online access stays off by default | used headless by `td_import_blender` with `--factory-startup --disable-autoexec` |
| `blender` MCP (not registered yet) | Blender Lab `projects.blender.org/lab/blender_mcp` `dbbf836ad4b1025f14a2b3b504c43903f39e0b04` (2026-09-29) in `../mcp-vendor/blender-mcp-official/` | GPL-3.0-or-later | nothing yet: `requirements.lock.txt` (hashed, wheels only, deps <= 2026-10-19); install = the user's OK | all code read (add-on 9 files, server + 20 tools + helpers) | none (no HTTP client in the code) | add-on socket 127.0.0.1:9876, no auth; `execute_blender_code` = arbitrary Python (ask each time); stdio only. Details: `docs/research/BC_blender_td_scripts.md` s9. ahujasid/blender-mcp rejected (Supabase telemetry, cloud services). |

Our own Blender code: `tools/blender_export.py` (runs in Blender; reads the scene, writes only its `--out` folder and
`--save-blend`; no network), `tools/blender_td_logic.py` (stdlib math), `src/blender.js` (runs Blender with execFile,
fixed args, no shell).
