# BC - TD Scripts v1.4 (Artechs, derivative.ca asset 69030): Blender add-on for TouchDesigner (26 Oct 2026; TD 2025.31550, macOS, Rosetta)

Status: page read, **no code obtained** (downloads are Patreon-gated, Patreon returned 403 and was not bypassed). Everything about internals below is UNVERIFIED and marked as such. Saved: `research_src/tdscripts_blender_69030/` (page HTML + SOURCES.md).

## 1. What it is (page facts)
- Author Artechs (Patreon "factorysettings"), posted 18 Feb 2024, tags blender, tdscripts. Title says 1.4, text says check that .py and .tox both say 1.4.1. Later Patreon posts: 1.4.2 "official release", 1.4.3 (.py + .tox).
- Two parts: a **Blender add-on (.py)** and a **companion .tox**. Workflow per the page: drag the .tox into the TD network, install the add-on, press an export button in the add-on, then press the **"get" pulse** in the .tox.
- Features across versions: v1.0 (free) material converter + camera script; v1.1 camera/mesh; v1.2 animated camera export; v1.3 (VJ Union, Jul 2023) generates scripts that move Principled BSDF + image textures to PBR MAT, still and animated cameras, meshes to SOPs, UV map of chosen mesh, faster dense meshes; v1.4 TD camera -> Blender import, rearranged UI, beta multi-material mesh export. Later search snippet: animated meshes (object transform, armature/rig, shape keys).
- NOT on the page: TD build, OS, Blender version, licence, price, GitHub, Blender Extensions listing, forum thread. No GitHub repo found by search.

## 2. How it works (inferred, UNVERIFIED)
VJ Union v1.3 says the add-on **generates scripts** and the .tox "get" button **runs the script selected in Blender**, replacing copy/paste into Text DATs. So the exchange is almost certainly: Blender writes a Python script (via clipboard, a temp file, or localhost socket; the mechanism is not stated anywhere I could read) and the .tox executes it in TD, creating nodes (geometry as SOP/Script data, PBRMat, Camera COMP with keyframes as CHOP/DAT). It is a **script-generating copy, not a live link**; the author only "experiments" with TD->Blender using the same protocol. No FBX/USD/Alembic, no .tox generation, no lights, no projector/mapping features documented. Mesh via generated Python is likely slow/large for stage geometry compared with a file format.

## 3. TD side in 31550 (checked in the installed app's `tfs/Config/TDParameterHelp.json`, operator names exist)
`fbxCOMP`, `usdCOMP`, `alembicSOP`, `fileinSOP`, `fileinPOP`, `alembicPOP`, `cameraCOMP`, `lightCOMP`, `projectionTOP` all present. No `gltfCOMP`. (Existence only; behaviour not run.) So TD can ingest Blender exports natively without this add-on.

## 4. Audit
Cannot be done: no .py/.tox. Questions to answer before any use: socket bind address/port (must be 127.0.0.1), `exec`/`eval` of received text, `subprocess`, `pip`/network calls, telemetry, Patreon license check. Treat as arbitrary code execution inside both Blender and TD.
Blender install on this Mac: **none** (`ls /Applications | grep -i blender` empty). Blender MCP among peers: **none** (no mention in docs/research, `AH_relevant_mcps.md` does not list one by grep for "blender" beyond passing mentions).
Licence: unknown (Patreon-supported; v1.0 free). Mac/Windows: unknown (pure Python, likely both).

## 5. Verdict
Not adopted: paywalled, closed to inspection, script-injection design, nothing for stage mapping. Borrow only the idea (one "get" pulse) and the camera transfer concept.

## 6. How jazib-td should work with Blender (proposal, nothing built)
1. **td_import_blender(path, root_comp)**: user exports from Blender **FBX or USD** (stage mesh, cameras, optionally lights/empties named `PROJ_*`) plus a small **JSON sidecar** (name, type, position, rotation, sensor/lens, projector throw ratio, lens shift, resolution). Tool builds under a target COMP (e.g. LK_projection_room): `fbxCOMP`/`usdCOMP` for geometry, one Camera COMP per camera with FOV from lens+sensor, one Light COMP (spot) + Projection TOP / Camera for each `PROJ_*` with FOV = 2*atan(1/(2*throw)) (see AT_projector_coverage.md), units and Y-up/Z-up conversion checked by a unit cube test. Read-only on files, writes only inside that COMP, td_exec logged.
2. **Camera path baking**: Blender-side bake to FBX/Alembic animated camera; TD plays via the camera COMP in the FBX/USD COMP, or JSON keyframes to a CHOP.
3. **Pairing with a Blender MCP** (e.g. the community blender-mcp): only after audit via the AH_relevant_mcps gates; it would let an agent export the files in step 1. Its execute-python tool is full code execution, so the same go-ahead rule as Ableton/AE.
4. Stage source of truth is PF26 R02 geometry (nine faces); Blender export is for look/camera previs only, never overrides Resolume mapping.

## 7. Gated steps (need the user's OK)
- Installing Blender (not present) or any Blender MCP/add-on; paying for Patreon or downloading/auditing the add-on.
- Loading any .fbx/.usd/.tox into TD; building td_import_blender (build only on request).
- Any Resolume/Arena operation.

## Open questions
Is Blender wanted at all for PF26 (stage previs exists in the localhost 3D viewer)? Which exporter (FBX vs USD) do they prefer? Buy and audit 1.4.3, or build our own?

## 8. Built (26 Oct 2026, user: "blender integration is yes for now")
- **Blender installed:** `brew install --cask blender` (official cask, analytics off) -> `/Applications/Blender.app`
  **5.2.2 LTS** (hash d13f752e3b9c, built 2026-09-15; dmg Last-Modified 15 Sep = over 7 days old), CLI wrapper
  `/opt/homebrew/bin/blender`. Information only (house rule: no gating on it): `spctl` accepted, Notarized Developer ID,
  Stichting Blender Foundation (68UA947AUU). Headless check: `Blender -b --python-expr "import bpy;
  print(bpy.app.version_string)"` -> `5.2.2 LTS`.
- **Export:** `tools/blender_export.py` (runs in Blender) + `tools/blender_td_logic.py` (pure maths). USD export with
  `convert_orientation`, forward -Z, up Y, `convert_scene_units METERS`, cameras/lights left out of the USD (TD builds
  them from the sidecar). **Verified headless (Blender 5.2.2, pxr in Blender):** the tiny stage's USD has upAxis Y,
  metersPerUnit 1, deck bounds x +-4, y 0..1, z +-2 = the sidecar's td = (x, z, -y). Camera at Blender (0,-12,3) aimed at
  (0,0,1) -> TD t (0,3,12), rx -9.46 deg; projector (0,-8,4) -> t (0,4,8), rx -20.56 deg (both = atan of the drop).
- **TD side:** `td_import_blender` (src/blender.js plans, td/handlers.py `cmd_import_blender` builds). Tests:
  `test/test_blender_td.py` (logic, fixture, handler on a fake TD, Blender re-export when installed),
  `test/blender.test.mjs` (plan). Fixture: `test/fixtures/blender/tiny_stage.{blend,usdc,fbx,json}` made by
  `--make-test-scene` (8x4x1 m deck, 35 mm FOH camera with shift x 0.1, 40 deg projector spot with throw 1.5, 1920x1080).
- Not live-checked in TD yet. **Live-check list (scratch TD first, T-83):** (1) usdCOMP: does creating it import the
  default `$TT/USD/Pixar/shot_import.usda` before `file` is set; does `imp` re-import with importmethod full; does it
  honour metersPerUnit/upAxis (expected: data is already Y-up metres); children made, `td_errors` clean. (2) Render TOP
  `geometry geo` renders the USD COMP's children (else point it at `geo/*`). (3) Camera COMP fov / winx vs a Blender
  render of the same camera (overlay a still: edges must line up). (4) Light COMP cone: TD `coneangle` full angle like
  Blender `spot_size` (compare a spot pool on the deck). (5) Projector: ramp lands on the deck where Blender's spot is;
  `projangle` = horizontal FOV across the map. (6) `Camera` menu switches `render.par.camera`; Lightdimmer / Ambient /
  Resw / Resh drive the ops. (7) `td_perf`: COMP cook ms at 1920x1080 with other lab COMPs parked (60 fps rule; aim
  <= 3 ms). (8) Save rotation + `td_checkpoint` after the verified build.

- **Live-checked 26 Oct (T-104):** items 1-5 and 7-8 pass on 31550 (camera and projector within 2 px of Blender /
  analytic numbers, 60 fps); found: USD import makes smooth point normals (facetPOP unique fixes it), deck grey 0.30
  with no MAT. Item 6 (Camera menu / dimmer / ambient / Resw-Resh pars) set by expression, not exercised by a menu switch.

## 9. Blender MCP audit (26 Oct 2026)
| | ahujasid/blender-mcp (mcp-for-blender) | **Blender Lab official** (projects.blender.org/lab/blender_mcp) |
|---|---|---|
| Pin checked | `febcd90` (2026-10-24: under 7 days old) | **`dbbf836ad4b1025f14a2b3b504c43903f39e0b04` (2026-09-29)**, MCP 1.0.2, add-on 1.0.0 |
| Size | ~16k lines (addon.py 6.6k) | ~2.5k lines of code (+ bundled API/manual .rst docs) |
| Network | Supabase telemetry (`telemetry.py`, opt-out env), premium API (supabase function), Poly Haven, Sketchfab, Hyper3D/fal, Tencent Hunyuan, Meshy, Poly Pizza, PyPI/GitHub update checks | **none**: no urllib/requests/httpx/telemetry anywhere in `mcp/blmcp` or the add-on (grep + read) |
| In-Blender socket | `bind((host, port))` 9876 | `bind(("localhost", 9876))` AF_INET = 127.0.0.1 (pref `host` editable: keep `127.0.0.1`); null-byte JSON, 10 MiB cap, 10 s client timeout; **no auth** (any local process can run code; an HTTP request from a browser fails JSON parse) |
| Code exec | `exec(code, namespace)` | `exec(code, namespace)` for every tool (tools send `*_toolcode.py`); `execute_blender_code` = arbitrary LLM Python; `weak_sandbox.py` only blocks `sys.exit`, `wm.quit_blender`, factory/userpref resets ("not really a sandbox") |
| Other | consent prompt, trajectory upload | `*_for_cli` tools run `blender --background <file> --python-expr` (subprocess, `BLENDER_PATH`); render tools write to a given path; `--transport http` exists (127.0.0.1:8000, CORS *, DNS-rebinding guard off) -> **we run stdio only** |
| Licence | MIT | GPL-3.0-or-later |
| Verdict | not adopted (telemetry + cloud asset/AI services, 2 days old) | **adopted**; nothing to strip (no telemetry, no cloud features); add-on needs Blender's "Allow Online Access" (its own gate for the localhost socket) |
- Vendored: `../mcp-vendor/blender-mcp-official/` (git clone at the pin, no install scripts run). Deps resolved with
  `uv pip compile --exclude-newer 2026-10-19 --only-binary :all: --generate-hashes` -> `requirements.lock.txt`
  (mcp 1.30.0, docutils 0.23, pyyaml 6.0.3 + transitive, wheels only, hashes). **Install not done:** the venv install
  was refused by the session's permission classifier (code from outside); needs the user's OK. Add-on not installed
  in Blender (user step).
