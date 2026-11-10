# AH: other MCP servers worth adding to the TD / AV workstation (26 Oct 2026)

Research + audit only. **Nothing was installed or run**; no server started; `.mcp.json` untouched; no `jazib-td` /
`jazib-gflow` tool called. Candidate repos were shallow-cloned into a scratch folder and read (files, deps, lockfiles,
grep for network / telemetry / exec); the Resolume binary on disk was only inspected (`strings`, `unzip -p manifest.json`,
`shasum`), never executed. All repo text was treated as data. Audit rules: free licence, pin >= 7 days old (today
2026-10-26, so commit date <= 2026-10-19), no telemetry / phoning home, local-only by default, deps listed, what it can
execute. Format follows `jazib-td-mcp/AUDIT.md`. Facts marked **UNVERIFIED** came from a fetched web page or a README only.

## Summary

- **Best find: Resolume ships its own official Arena MCP server inside the Arena install.** On this Mac:
  `/Applications/Resolume Arena/mcp/resolume_arena_mcp_server` (+ `.mcpb`), a signed-by-Resolume Rust stdio binary
  (rmcp 1.2.0, universal arm64+x86_64), REST-only, proprietary licence, no telemetry/analytics strings in the binary.
  Nothing to download. **Recommend**, with every Arena operation behind the user's go-ahead (see Gates).
- **Version conflict to resolve first:** `CLAUDE.md` says Arena is 7.23.2 (51094) and final, but
  `/Applications/Resolume Arena/Arena.app` reports `CFBundleShortVersionString` **7.28.1**, build 26535 (same for the
  `Resolume Arena.api9-2026-10-08` copy and Wire). Resolume's docs say the MCP needs **7.26+**. If the app really is 7.28.1 the
  bundled MCP works; if the user wants to stay on 7.23.2 it does not. The lead should ask the user which is true (Q1).
- **Ableton Live 12 Suite is installed** (`/Applications/Ableton Live 12 Suite.app`, prefs for 12.4.3). Best-audited Live MCP:
  `wstierhout/ableton-live-mcp` v1.8.1 (MIT, PyPI + MCP Registry, `uv.lock`, no telemetry, "no arbitrary-code path", loopback
  socket). **Recommend**, but it needs a Remote Script copied into Ableton's User Library (user's go-ahead).
- **Not recommended:** `ahujasid/ableton-mcp` and `ahujasid/mcp-for-blender` (both ship Supabase telemetry; anonymous tier is
  **on by default**); `drohi-r/resolume-mcp` (209 tools, overwrites `AdvancedOutput.xml`/`slices.xml`, breaks "Resolume is never
  overwritten"); ffmpeg MCPs (Claude Code + Bash + ffmpeg already do it); Unreal/Unity/Blender (none installed).
- **Maybe:** After Effects (`kumoproductions/mcp-aftereffects` v0.3.2, AE 2026 is installed, 2 runtime deps, read-only mode,
  eval off by default); ComfyUI (`joenorton/comfyui-mcp-server` v1.1.1 or `Comfy-Org/comfy-mcp` v0.10.0); community Resolume
  `mackatwentytsuru/resolume-mcp-server` (only if OSC read/subscribe is wanted; live-tested on 7.23); Peekaboo (capture only).
- **Gaps with no good candidate:** generic **OSC** (only `daanrongen/osc-mcp`, 0 stars, needs `bun`) and **MIDI** (none
  usable). Cheapest answer: `td_exec` inside TD (OSC In/Out DAT, MIDI In CHOP, already documented in `ops/CHOP.md`) or a
  ~80-line in-house `jazib-osc` MCP. No MadMapper / Millumin / Notch / Syphon MCP exists (searched GitHub, MCP Registry, web).
- Other TouchDesigner MCPs were already compared in `AF_peer_td_mcps.md`; nothing new beats `jazib-td` (list below).

## How this was searched

GitHub `gh api search/repositories` (about 45 queries: touchdesigner, resolume, ableton, osc, midi, blender, comfyui,
unreal, unity, obs, ffmpeg, qlab, madmapper, millumin, notch, after effects, figma, shadertoy, glsl, max, dmx, companion,
stream deck, syphon, vj, coremidi); the official MCP Registry API (`registry.modelcontextprotocol.io/v0.1/servers?search=`,
17 keywords; no Resolume, MadMapper, Notch, QLab or Syphon entries); `punkpeye/awesome-mcp-servers` and `modelcontextprotocol/registry`
exist (not mined line by line); web search for Glama / Smithery / mcp.so Resolume (no listing found); Resolume's own support
pages. Installed apps were taken from `/Applications` to judge relevance.

## Installed on this Mac (relevance filter)

Present: Ableton Live 12 Suite, Resolume Arena (+Wire, Alley), TouchDesigner (x2), After Effects 2026, Premiere, Media Encoder,
Photoshop, Illustrator, DaVinci Resolve, Figma, OBS, Comfy Desktop, Vezer, Node v26.5.0, Python 3.13, `uv`, `npm`, `gh`.
Absent: Blender, Unreal, Unity, QLab, MadMapper, Millumin, Notch, `bun`/`bunx`, `comfy` (comfy-cli), `pipx`.
`~/Documents/Max 9` exists but no Max.app in `/Applications`.

## Candidates table

Stars/dates from GitHub on 2026-10-26. "Verdict": R = recommend, M = maybe, N = no.

| # | Candidate | Stars | Last push / release | Licence | Runtime | Connects via | Tools | Executes | Telemetry | Mac | Paid? | V |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Resolume official Arena MCP** (bundled, v7.28.1 per manifest) | n/a | built 2026-10-06 | proprietary (Resolume) | Rust binary, stdio | Arena REST (web server) | ~20 grouped tools (`clip`, `effect`, `layer`, `group`, `column`, `deck`, `composition`, `parameter`, `transport`, `crossfader`, `monitor`, `diagnose`, `autopilot`, `file`, `catalog`, `style`, `technique`, `status`) | no shell, no code eval seen; edits composition | none found in strings | universal | no (bundled) | **R** |
| 2 | mackatwentytsuru/resolume-mcp-server | 4 | 2026-10-19 / v0.5.4 (not on npm) | MIT | TS, Node 20+ | Arena REST + OSC in/out | 39 | OSC send = any path; `confirm:true` on destructive | none | yes | no | M |
| 3 | drohi-r/resolume-mcp | 13 | 2026-10-12 / no release | Apache-2.0 | Python 3.12, uv | REST + WS + OSC; **edits Arena prefs XML** | 209 | writes `AdvancedOutput.xml`, `slices.xml` (backup + `confirm_destructive`) | none found | yes | no | N |
| 4 | Tortillaguy / sandraschi / Ayesy / jbrick2070 / DjSantech resolume-mcp | 0-7 | stale or new, one-person | MIT / none | mixed | REST | 10-44 | not read | not read | | | N |
| 5 | **wstierhout/ableton-live-mcp** | 60 | 2026-10-23 / v1.8.1 (2026-09-16) | MIT | Python 3.10+, uv, PyPI | Remote Script in Live, TCP 127.0.0.1:9877 | 156 typed | no arbitrary-code path (README + grep) | none found | yes | no | **R** |
| 6 | ahujasid/ableton-mcp | 3247 | 2026-09-22 / v1.4.5 | MIT | Python, `supabase` dep | Remote Script TCP 9877 | ~30 | `import`-capable commands per its own comment | **anonymous telemetry ON by default** + opt-in dataset upload to Supabase | yes | no | N |
| 7 | bschoepke/ableton-live-mcp | 234 | 2026-10-06 / v0.1.1 | MIT | Python, no deps | Remote Script + Max for Live device | many | **`eval`/`exec` of caller code in Live** by design | none found | yes | no | N |
| 8 | xiaolaa2/ableton-copilot-mcp, nozomi-koborinai/ableton-osc-mcp (Go, AbletonOSC), Pantani/ableton-mind, ntworm (Windows) | 9-93 | | MIT | TS / Go / Python | ableton-js / AbletonOSC | | not read | not read | | | N |
| 9 | **kumoproductions/mcp-aftereffects** | 137 | 2026-10-23 / v0.3.2 (2026-10-16) | MIT | TS, Node 24+ (have v26.5) | file IPC + `osascript` into AE | 11 grouped | ExtendScript **eval off by default** (`AE_MCP_ENABLE_EVAL`) | none found | yes (AE 2024-26) | no | M |
| 10 | joenorton/comfyui-mcp-server | 410 | 2026-02-17 / v1.1.1 | Apache-2.0 | Python, `requests`, `Pillow`, `mcp` | own HTTP MCP on 127.0.0.1:9000 -> ComfyUI :8188 | ~20 | runs workflows you name | none (a "telemetry" log line is a local log) | yes | no | M |
| 11 | Comfy-Org/comfy-mcp | 304 | 2026-10-22 / v0.10.0 (2026-08-10, PyPI) | **AGPL-3.0-or-later OR commercial** | Python 3.10+, needs `comfy-cli` | shells out to `comfy --where local` | 40 | subprocess `comfy`; **partner models spend credits** | comfy-cli telemetry unless `COMFY_NO_TELEMETRY`/`comfy tracking disable` | yes | partner credits only | M |
| 12 | artokun/comfyui-mcp | 863 | 2026-10-25 / v0.52.206 | MIT | TS, 338 lock pkgs, optional Claude/OpenAI/AWS/Azure/cloudflared | HTTP/WS + sidebar agent | 100+ | installs nodes/models, RunPod, tunnels | not found in src | yes | optional clouds | N |
| 13 | daanrongen/osc-mcp (generic OSC) | 0 | 2026-04-20 / 1.1.4 | MIT (field only, no LICENSE file) | TS built **for bun**, `effect`, `osc` | UDP, 127.0.0.1 default | 4 (`send`, `send_bundle`, `listen`, `status`) | sends any OSC | none | needs `bun` | no | M |
| 14 | noodledostuff/osc-mcp-server, sandraschi/osc-mcp, darkwings/OSC_MCP | 0-3 | 2025-08 / 2026-10 | MIT / Apache | TS (SDK 0.4) / FastMCP+FastAPI | UDP / HTTP | | | | | | N |
| 15 | MIDI MCPs (tubone24 file writer, teemow Go rig, ugufru C++ CoreMIDI, mcp-koii ...) | 0-57 | | MIT / BSD | | | | | | | | N (none usable) |
| 16 | OBS: sbroenne/mcp-server-obs (C#), xDarkzx/OBS_MCP (Py, Apache, 148 tools), ironystock/agentic-obs (Go) | 13-39 | 2026-04..10 | MIT / Apache | | obs-websocket v5 | 100+ | start/stop stream & record | not read | OBS.app present | no | N (no streaming workflow stated) |
| 17 | ffmpeg: kajisho5/ffmpeg-skill (2902 stars, **created 2026-09-03**, v2.17.1 on 10-25, 10+ releases/week), KyaniteLabs/kinocut (222, 205 tools, torch/whisper extras), misbahsy/video-audio-mcp (stale) | | | MIT / Apache | Py stdlib / Py | local ffmpeg | 42 / 205 | runs ffmpeg | none found | yes | no | N |
| 18 | Blender: ahujasid/mcp-for-blender (32k stars, telemetry), official Blender Lab MCP (projects.blender.org/lab/blender_mcp, add-on 1.0.3, Blender 5.1+) | | | MIT / not stated | Py | add-on socket | | **exec LLM Python in Blender, no guards** | ahujasid: opt-out env | | | N (Blender not installed) |
| 19 | Unreal (ChiR24/Unreal_mcp, 980) / Unity (CoplayDev/unity-mcp, 15k) | | | MIT | | editor plugin | | editor scripting | | | | N (not installed, not in workflow) |
| 20 | Figma: GLips/Figma-Context-MCP v0.13.2 (16k, MIT); official remote `com.figma.mcp/mcp` (Figma-hosted) | | | MIT / n/a | TS | Figma REST (token) / hosted | | read-only design data | calls api.figma.com | Figma.app present | token | N (not motion work) |
| 21 | Peekaboo `openclaw/Peekaboo` v4.9.3 (5389 stars, `@steipete/peekaboo`) | 5389 | 2026-10-24 | MIT | Swift CLI + Node launcher | local, ScreenCaptureKit + Accessibility | ~30 | **clicks, types, scripts any Mac app** | Chrome DevTools sub-MCP telemetry patched off; rest not audited | macOS 15+ | no | M (capture only) |
| 22 | QLab (MarcheKEN, magichao326), Lightkey, QLC+, ETC Eos, grandMA, Companion, Stream Deck | 0-54 | | | | OSC / WS | | | | | | N (apps not present) |
| 23 | Shadertoy: wilsonchenghy/ShaderToy-MCP | 50 | 2025-05-07 | MIT | Py | Shadertoy API | | | | | | N (stale; Shadertoy licences are NC, see `L_shader_sources_licences.md`) |
| 24 | Max/MSP: tiianhk/MaxMSP-MCP-Server | 285 | 2026-05-12 | MIT | Py + Max patch | UDP | | patches | | no Max.app found | | N |
| 25 | MadMapper, Millumin, Notch, Syphon, NDI | - | - | - | - | - | - | - | - | - | - | none exist |

Already compared elsewhere (`AF_peer_td_mcps.md`, not re-audited): 8beeeaaat/touchdesigner-mcp (602), dylanroscover/Embody (209),
satoruhiga/claude-touchdesigner (128), Derivative TouchDesigner/TDMCP (62, custom licence), bottobot/touchdesigner-mcp-server (80,
docs server), Pantani/tdmcp (55), twozero-team/twozero-td-mcp (28, closed), dreamrec/TDPilot (16), plus newly seen and not read:
johnsabath/touchdesigner-mcp (16, Python, runs inside TD on :9988, TD 2024+), familienak-tech/Touchdesigner---MCP-server (12),
sarveshsea/touchdesigner-ai-brain (10), PyPI `touchdesigner-mcp` (19 tools, Web Server DAT :9980). None adds what `jazib-td` lacks
beyond the ideas already ranked in AF.

## Per-recommended audit

### 1. Resolume official Arena MCP server (bundled)

- **What:** `/Applications/Resolume Arena/mcp/resolume_arena_mcp_server` (13,850,896 bytes) and `.mcpb` (12,966,472). Manifest
  (read with `unzip -p`): name "Resolume Arena MCP Server", version 7.28.1, author Resolume, `license: "proprietary"`,
  `privacy_policies: resolume.com/privacy`, "Requires Resolume Arena 7.26+", command = the binary over stdio, platforms darwin + win32.
- **Hashes (this install, mtime 2026-10-06):** binary `aba9368fe7f9a837f0c029ddf813f490077eedb1b48fbce6d924d536478a9184`;
  `.mcpb` `e00b74d6ccbd539887d4ccff3594193cb035c77769c1e8468dab2feba21d6469`. Pin = these hashes; re-hash after any Arena update.
  The user's rule: the installed Arena is the user's own working install, so no signature / provenance checks were made.
- **Static read of the binary (`strings`, `otool -L`):** Rust, `rmcp-1.2.0`, `common_rust/net-client` http/rest modules (GET/POST/PUT/PATCH/DELETE),
  links only Security, CoreFoundation, libiconv, libSystem. No posthog / sentry / mixpanel / analytics / telemetry strings, no
  external `http(s)://` URLs other than XMP namespace strings. Destructive actions carry an argument literally named
  `are_you_absolutely_sure_user_confirmed` ("ONLY set true after the user has explicitly confirmed in chat") on composition, layer and group.
- **Tools** (type names in the binary): clip (open / set_transport / find / copy / swap / merge, with effects + parameters + auto-trigger),
  effect, layer, group, column, deck, composition, parameter (set incl. animation phase sources), transport (play/pause/stop/bpm/resync),
  crossfader, transition, transform, color_code, autopilot, file (browse / info), monitor (snapshot / filmstrip / motion / diff, jpg or png),
  diagnose (playback, bypass, effects, codecs, resolution, audio), catalog, style, technique, status (`instructions`).
- **Limits (Resolume's page):** REST only; no Advanced Output slices/screens, no keyboard/MIDI/DMX/OSC mappings, no cue points, presets,
  envelopes, dashboard dials, recording. Only clips and files in the current deck. "Mostly for building and modifying a composition,
  not live performance." Also Wire MCP (nodes, ISF shaders): out of scope, Wire is dropped (ADR-008).
- **Executes:** edits the open composition and can load files by path; no shell. It can call `clip:open` with a file path, so it can load
  media from disk into Arena (a write inside Arena, not on disk).
- **Config unknown (UNVERIFIED):** host/port/web-server settings and any flags were not found in strings and the binary was not run
  (`--help` exists). Needs Arena's web server on (Preferences > Web Server). Lead: read Resolume's page
  `resolume.com/support/en/mcp-servers` and, with the user's OK, run `--help` once.
- **Verdict: recommend** (after Q1). **Pin:** the two hashes above. **Install:** nothing to download. `.mcp.json` entry (lead adds):
  `"resolume-arena": {"command": "/Applications/Resolume Arena/mcp/resolume_arena_mcp_server"}` plus whatever env the docs name.
  Do **not** add it to any allow-list: every call asks the user.

### 2. wstierhout/ableton-live-mcp (Ableton Live 12)

- **Repo:** https://github.com/wstierhout/ableton-live-mcp, MIT, 60 stars, created 2026-07-11, 5 open issues, `SECURITY.md`, CI (ruff, pytest, py_compile
  of the Remote Script), PyPI trusted-publish. Also in the official MCP Registry as `io.github.wstierhout/ableton-live-mcp`.
- **Pin:** tag **v1.8.1**, commit `55abd3a38a74c39f6f2fc0d1d90107d06ec5f952` (committed 2026-09-16, PyPI upload 2026-09-17, 39 days old).
  PyPI name `mcp-server-ableton-live==1.8.1`. Use the repo + `uv.lock` (49 locked packages incl. `av`, `cryptography`, `mcp`), not floating `uvx`.
- **Connects:** MCP server (stdio) -> TCP `127.0.0.1:9877` -> Remote Script inside Live. The socket has **no authentication**; any local process can
  drive Live while the script is loaded (stated in `SECURITY.md`; bind overridable by `ABLETON_MCP_HOST`, leave unset).
- **Tools:** 156 typed tools (session/transport, tracks/mixer, clips + MIDI notes, devices + parameters, arrangement, generators, batch, audio
  analysis, offline `.als` parse, recipes). `ABLETON_TOOLSETS=session,tracks,clips,devices` trims the list.
- **Executes:** README: "Every action is a specific tool with validated arguments; there is no arbitrary-code path". Grep confirms no `eval`/`exec`;
  one `subprocess.run` runs its own `_audio_decode.py` (PyAV) with a 60 s timeout on a user-given audio path. Writes only through
  the installer (`install`/`uninstall`, with recovery copy) and a WAV record-section tool. Destructive edits exist (delete track, replace notes): "save before a big session".
- **Telemetry:** none found (grep for posthog / sentry / telemetry / analytics / mixpanel / supabase). Network: Live socket only (loopback).
- **Mac:** yes. Live 12 supported. **Paid:** no.
- **Fit:** the user's Akai MIDImix / MPK Mini feed TD directly; this MCP is for building/reading Live sets (stems, tempo, scenes) that drive PF26 audio. It does not replace TD's MIDI In CHOP.
- **Install plan (do not run now):**
  ```
  git clone https://github.com/wstierhout/ableton-live-mcp.git <dest>/ableton-live-mcp
  git -C <dest>/ableton-live-mcp checkout 55abd3a38a74c39f6f2fc0d1d90107d06ec5f952
  cd <dest>/ableton-live-mcp && uv sync --frozen
  # later, with the user's OK (copies a Remote Script into Ableton's User Library, keeps a recovery copy):
  uv run --frozen mcp-server-ableton-live install
  uv run --frozen mcp-server-ableton-live doctor --json
  ```
  `.mcp.json`: `{"command":"uv","args":["run","--frozen","--directory","<dest>/ableton-live-mcp","mcp-server-ableton-live"],"env":{"ABLETON_TOOLSETS":"session,tracks,clips,devices"}}`.
  Then in Live: Preferences > Link/Tempo/MIDI > Control Surface = the new script (UI step for the user). Start read-only.
- **Verdict: recommend.**

### 3. kumoproductions/mcp-aftereffects (After Effects 2026)

- https://github.com/kumoproductions/mcp-aftereffects, MIT, 137 stars, created 2026-08-08, v0.3.2 published 2026-10-16 (10 days), npm `@kumoproductions/mcp-aftereffects` 0.3.2
  (integrity `sha512-Fr0n6+xvP0auDANSD7j+f5XIiKjKwkDT/1wWI2KdX8z/w7r4xX53LgvC/q8spcvwkj08hxuj2P8cUcEKqPrYxg==`). Commit `73fea51220c9b2a8a5afbb95e50c37e0ad08e978`.
- **Deps:** runtime only `@modelcontextprotocol/sdk ^1.32.1` (same major as ours, 1.32.1 already audited) and `zod ^4.6.7`; 227 lock entries are dev tooling. Node 24+ needed (have v26.5).
- **Connects:** file-based IPC: writes a script, launches it in the running AE through `osascript` (macOS) and reads the result. No port, no network code found.
- **Tools:** 11 grouped (Inspect, Document, Render, Operations): read project/comps/layers, edit layers/keyframes/effects/masks/text/shapes/expressions, save, backup/restore, render frames.
- **Executes:** AE edits by structured operations. Raw ExtendScript/eval is **off** unless `AE_MCP_ENABLE_EVAL=1` (README warns it can affect the whole computer). `AE_MCP_READONLY=1` blocks edits; `AE_MCP_ALLOW_CATEGORIES` limits operation types.
  `execFile` is used for `osascript` dialogs and AE launch only.
- **Needs:** AE Preferences > Scripting & Expressions > "Allow Scripts to Write Files and Access Network" ON (a global AE setting; the user's call).
  README warns project data (layer names, expressions, footage paths) goes to the model.
- **Telemetry:** none found. **Paid:** no (AE licence is the user's).
- **Install plan:**
  ```
  git clone https://github.com/kumoproductions/mcp-aftereffects.git <dest>/mcp-aftereffects
  git -C <dest>/mcp-aftereffects checkout 73fea51220c9b2a8a5afbb95e50c37e0ad08e978
  cd <dest>/mcp-aftereffects && npm ci --ignore-scripts && npm run build    # prepare=lefthook install is skipped by --ignore-scripts
  ```
  `.mcp.json`: `{"command":"node","args":["<dest>/mcp-aftereffects/dist/index.js"],"env":{"AE_MCP_READONLY":"1"}}` (drop READONLY only when the user starts AE work).
- **Verdict: maybe** (recommend only when the user starts AE motion work; the PF26 plan is TD / HyperFrames / Resolume).

### 4. mackatwentytsuru/resolume-mcp-server (community Resolume)

- https://github.com/mackatwentytsuru/resolume-mcp-server, MIT, 4 stars, single author, created 2026-04-27. **Not on npm** (README says so); build from source.
  Pin `901cc9e1cf738d06089352d26a93b0babe43cb85` (2026-10-19, exactly 7 days; code equals v0.5.4 plus post-tag review fixes; the last two commits are docs/author only).
- **Why it is the only community Resolume one worth a look:** curated 39 tools, Zod on every input, `confirm:true` on `clear_clip` / `clear_layer` / `wipe_composition` / `remove_effect`,
  `RESOLUME_TOOLS_STABILITY` filter, `config.ts` refuses non-private hosts (RFC1918 / loopback / Tailscale only) and cloud-metadata addresses, **claims live test against Arena 7.23**
  (this matches the user's stated build; UNVERIFIED by us). Unique extras: `resolume_osc_query` (wildcard reads), `resolume_osc_subscribe` (playhead push), `resolume_get_clip_thumbnail`.
- **Risks:** `resolume_osc_send` can send any OSC path to Arena; `scripts/setup-hooks.mjs` runs `git config` on `npm install` (use `--ignore-scripts`); dev deps (vitest, msw, tsc) pull 238 lock entries, runtime only SDK + zod.
  No fs writes found in `src/` outside tests. Sockets: REST to Arena, `node:dgram` to OSC ports 7000/7001 on loopback.
- **Install plan:**
  ```
  git clone https://github.com/mackatwentytsuru/resolume-mcp-server.git <dest>/resolume-mcp-server
  git -C <dest>/resolume-mcp-server checkout 901cc9e1cf738d06089352d26a93b0babe43cb85
  cd <dest>/resolume-mcp-server && npm ci --ignore-scripts && npm run build
  ```
  `.mcp.json`: `node <dest>/resolume-mcp-server/build/index.js`, env `RESOLUME_HOST=127.0.0.1`, `RESOLUME_PORT=8080`, `RESOLUME_TOOLS_STABILITY=stable`; leave `RESOLUME_CACHE` unset (it binds the OSC OUT port).
- **Verdict: maybe.** Redundant if the official bundled server works (item 1); keep as the fallback or when OSC reads are needed. It does not fix the "OSC addresses must be re-verified per build" rule in `CLAUDE.md`.

### 5. ComfyUI (pick one, only if the user wants Comfy driven by an agent)

- **joenorton/comfyui-mcp-server** v1.1.1, commit `e0101b2312f30501664dabe4a74c1283c4268eb8` (2026-02-17, 252 days old, so stale but stable), Apache-2.0, 410 stars.
  `pip install -r requirements.txt` (requests, mcp, Pillow, pytest) in a venv; run `python server.py` yourself; MCP at `http://127.0.0.1:9000/mcp` (streamable HTTP, so needs a running
  process, unlike stdio). Talks to ComfyUI on `:8188` (Comfy Desktop uses its own port; set `COMFYUI_URL` and `set_comfyui_output_root`). Tools: generate_image / generate_song / run_workflow / list_models / view_image / publish_asset /
  get_job / cancel_job. No telemetry (the grep hit is a local log line). **Verdict: maybe.**
- **Comfy-Org/comfy-mcp** v0.10.0, commit `92f4ee1953e7f2ecf71016a5f4a43fc7a69676c8` (2026-08-10), PyPI `comfy-mcp==0.10.0`, official, 40 tools, stdio. Cons: **AGPL-3.0-or-later or commercial** (fine for private local use; do not redistribute),
  needs `pip install "comfy-cli>=1.14.0"` (absent here), comfy-cli telemetry must be turned off (`COMFY_NO_TELEMETRY=1`, `DO_NOT_TRACK=1`, `comfy tracking disable`), `partner_generate` and partner-API nodes **spend Comfy credits**
  (user's go-ahead per job, as with Flow). **Verdict: maybe.**
- `artokun/comfyui-mcp`: **no** (338 locked packages, optional AWS/Azure/RunPod/cloudflared tunnels, auto-installs nodes/models, a whole agent panel).
- Note `T_realtime_ml.md`: real-time diffusion on this Mac is limited; Comfy here is for stills/short clips, not the live rig.

### 6. Peekaboo (read-only screen capture of Arena / Ableton / AE)

- https://github.com/openclaw/Peekaboo, MIT, 5389 stars, npm `@steipete/peekaboo` (CLI + `peekaboo mcp`), macOS 15+, Node 22+. v4.9.3 = commit `dcb8570efad33c9992241203aff71cc78c1ea376` (2026-10-14).
  Releases ship every 1-3 days (so pin is old enough but moves fast); 2587 files, Swift, not auditable in this pass.
- **It can click, type, press chords and set values in any Mac app.** That is far above what is needed. `td_window_capture` already covers TD; Claude Code can read screenshots. Only worth it for captures of Arena / Ableton windows.
  If added: `Screen Recording` permission only, never `Accessibility`, and a project-level permission rule that denies the `click`, `type`, `press`, `set_value`, `action`, `scroll` tools.
- **Verdict: maybe (capture only).** Install not given; decide after Q4.

## Not recommended, with the reason (evidence)

- **ahujasid/ableton-mcp** (3247 stars): `MCP_Server/telemetry.py` header: "Anonymous tier ... On by default; opt out with `ABLETON_MCP_DISABLE_TELEMETRY`", `supabase` is a hard dependency, a dataset-recording tier uploads prompts / MIDI / names to Supabase when a consent is granted, and its Remote Script comment says the socket "takes unauthenticated commands that import" code. Violates "nothing phones home" by default.
- **ahujasid/mcp-for-blender** (32k): telemetry opt-in for content but a "minimal anonymous usage record" unless `DISABLE_TELEMETRY=true`; `addon.py` has `exec(code, namespace)`; Blender is not installed. If Blender comes later, prefer the official Blender Lab MCP (page warns it "will execute LLM generated code in Blender without any guards").
- **bschoepke/ableton-live-mcp**: `bridge.py` has `eval(params["expr"])` / `exec(params["code"])` inside Live by design; also M4L device builder. No telemetry, but arbitrary code is an unnecessary risk next to wstierhout.
- **drohi-r/resolume-mcp**: Apache-2.0, 209 tools, `uv.lock` 39 packages, no telemetry, `RESOLUME_ALLOWED_HOSTS` allow-list, 20 destructive ops gated. Rejected because it **writes** Arena's `AdvancedOutput.xml` / `slices.xml` (atomic + backup, `restore_advanced_output_preferences`), `pyproject` calls it "Private", no release, and a 209-tool surface is exactly what the other server's author warns against. `CLAUDE.md`: "Resolume is never overwritten or assumed".
- **ffmpeg MCPs:** `ffmpeg-skill` is a 2-month-old repo releasing daily (v2.17.1 on 10-25, 12+ releases in 3 days), so any pin >= 7 days is mid-churn; `kinocut` has 205 tools and torch / whisper / demucs extras. Claude Code's Bash + the user's ffmpeg + HyperFrames already render and probe; "Build only what's asked".
- **OBS:** OBS.app is installed, but no streaming job is on the plan; all candidates have under 40 stars and are one-person projects.
- **Unreal / Unity / Blender / QLab / Lightkey / Eos / grandMA / Companion / Stream Deck / Max:** the apps are not installed (Max.app absent) or not in the PF26 plan.
- **Shadertoy MCP:** stale since 2025-05; fetches Shadertoy content whose licences are mostly non-commercial.
- **Figma / GLips:** needs a Figma API token and calls api.figma.com; not motion work here.

## Install plan (order, nothing run yet)

1. Resolve Q1 (Arena version). Then add `resolume-arena` (item 1): one `.mcp.json` entry, no download. First call: `status` / `instructions`, read-only.
2. Create one vendor folder (suggest `<bundle>/jazib-td-mcp/research_src/mcps/` is git-ignored research; for runnable MCPs prefer a new `mcp-vendor/` next to `jazib-gflow-mcp/`, lead's choice) and clone + checkout + lockfile install for wstierhout (item 2).
   Record sha512 / lock hashes in `jazib-td-mcp/AUDIT.md` in the usual format (a new "Import: ..." section per MCP).
3. Ask the user for the Live Remote Script step (needs a UI choice in Live). Then `doctor`.
4. Only on request: AE (item 3, `AE_MCP_READONLY=1`), ComfyUI (item 5), community Resolume (item 4).
5. After each add: restart MCP servers, list tools, call one read-only tool, write a T-nn LEARNINGS entry for anything surprising.
6. OSC and MIDI: do not import. Either use `td_exec` with an OSC Out DAT / MIDI Out CHOP (TD side, already documented) or build `jazib-osc` in the house style (Node, `dgram`, loopback only, port allow-list excluding Arena's 7000 unless the user OKs).

## Gates (user's approvals)

- **Resolume (any of the three servers):** Arena / REST / OSC operations need the user's go-ahead **each time** (`CLAUDE.md`). Do not put these tools in a Claude Code allow rule. Read-only calls (`status`, `catalog`, `composition get`, `monitor`) are still Arena REST traffic: ask once per session at least, and say what will be called.
  Never call `confirm`-style destructive args on the user's behalf; never edit `AdvancedOutput.xml` / `slices.xml`. Output/LED mapping files stay StageLab-descriptive only.
- **Ableton:** installing the Remote Script, enabling it in Live, and any set-changing tool wait for the user's OK. Work in a disposable set first. MIDI controllers stay owned by TD (MIDI In CHOP) so Live's control-surface slot is not double-mapped.
- **After Effects:** the global "Allow Scripts to Write Files and Access Network" preference, and any non-read-only run, need the user's OK; `AE_MCP_ENABLE_EVAL` stays off.
- **ComfyUI / any paid service:** partner models, Comfy Cloud, credits = per-job approval with a cap, same as Flow's `max_credits`.
- **Installs:** every `uv sync`, `npm ci`, `pip install`, and clone into the bundle needs the go-ahead (CLAUDE.md "installs ... need the user's go-ahead").
- **Peekaboo:** Screen Recording permission is a macOS prompt the user must grant; Accessibility must not be.
- **Rule for all:** `--ignore-scripts` / `--frozen` installs, loopback only, no env that points at a non-loopback host, no auto-update, MCP env holds no tokens.

## Open questions for the user / lead

1. **Which Arena is installed?** Bundle says 7.23.2 (51094) final; the app says 7.28.1 (26535) (and `mcp/` ships inside it). Is 7.28.1 right, or is this a different build / the 7.23.2 copy lives elsewhere? The bundled MCP needs 7.26+.
2. Does the bundled Resolume MCP need web-server settings (host/port) that we should set explicitly? Not found in the binary's strings; read Resolume's page or run `--help` once (with OK).
3. Is Ableton Live part of the PF26 plan (stems / playback) or only a controller host? If not, skip item 2.
4. Does the user want an agent to *see* Arena/Ableton windows (Peekaboo, capture only) or is `td_window_capture` + manual screenshots enough?
5. Does the user want ComfyUI driven by an agent at all, and which port does Comfy Desktop use here (not checked)?
6. Build `jazib-osc` in-house, or keep OSC inside TD's `td_exec`? (Recommended: TD side first; build `jazib-osc` only if a non-TD OSC target appears.)
7. Where should third-party MCP code live (a new `mcp-vendor/` directory vs git-ignored `research_src/`)? Runnable code should not live in a git-ignored research folder.

## Notes for the lead on method

- Pins use full commit SHAs; tags are not trusted (tags can move). Dates are commit dates from GitHub, not the web page.
- Counts of tools come from the README / manifests and one grep (`@mcp.tool` = 209 for drohi-r); not re-derived live.
- Everything about runtime behaviour (ports, prompts, how Live loads the Remote Script) is **UNVERIFIED** until a one-item live pilot per MCP with the user's go-ahead.
- Clones used for the audit are in the session scratchpad only (`.../scratchpad/s/clones/`), not in the bundle.
