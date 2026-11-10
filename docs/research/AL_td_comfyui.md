# AL - TouchDesigner <-> ComfyUI (Comfy Desktop) integration (research, 26 Oct 2026)

Brief: `INTEGRATION_BRIEF.md`. Research only: no TD call, no app launch, no MCP tool call, nothing installed or downloaded. Comfy Desktop was **not running** (no `:8188` listener, no process). Read-only reads of Comfy Desktop's own config/log files, the local ComfyUI 0.34.5 source (`~/ComfyUI-Installs/JZB1/ComfyUI/`), the vendored `mcp-vendor/comfy-mcp/src` (v0.10.0), TD's offline help and our dumps, plus a few web fetches.
Tags: [V] read/seen at the URL or file named; [S] search snippet or secondary source; [U] unverified / needs the live test; [D] op or par confirmed in `ops/` dumps; [L] read from the local ComfyUI source (this install, v0.34.5).
TD = 2025.31550 (Rosetta x86_64, Python 3.11). Machine = M1 Max 64 GB (`Total VRAM 65536 MB ... Device: mps`, [V] comfyui.log). Real-time ML numbers: `T_realtime_ml.md`.

---

## 1. Summary

1. **Comfy Desktop's port is 8188 (default), confirmed from its own logs.** All 6 launch logs (Sep 5 - Oct 13) say `To see the GUI go to: http://127.0.0.1:8188` [V]. `settings.json` and `installations.json` hold no port field; the install has `portConflict: "auto"` (so it moves to another port if 8188 is busy, e.g. by a second Comfy) and `launchArgs: "--enable-manager"` (no `--listen`: loopback only) [V]. Confirm at runtime (`lsof -nP -iTCP:8188 -sTCP:LISTEN` or the `comfyui` MCP `server_info`), never assume.
2. **Install facts.** Instance `JZB1`, ComfyUI **v0.34.5**, Python 3.13.12, torch 2.12.1, `mac-mps`; I/O dirs `~/ComfyUI-Shared/{input,output,models}`; custom nodes: `ComfyUI-Sharp`, `ComfyUI-GaussianPack`, ComfyUI-Manager (`--enable-manager`) [V]. **`models/checkpoints` and `diffusion_models` are empty** [V]: no SD/SDXL/Flux weights are installed, so nothing diffusion-based can run until a model is downloaded (an install gate, user's go-ahead). What *has* run: SHARP (single image -> Gaussian-splat `.ply`), `Total inference time: 14.99s (14.99s per image)` on this machine [V log]; outputs `sharp_*.ply` in `~/ComfyUI-Shared/output`; saved workflows `SHARP - Mac image to splat.json`, `sharp-image-to-splat.json` [V].
3. **The integration is plain HTTP + one websocket on loopback.** `POST /prompt`, `GET /history/{id}`, `GET /view`, `POST /upload/image` (multipart), `GET /ws?clientId=` [L]. TD needs no plugin on its side; the only hard constraint is that **TD's Web Client DAT cannot send multipart** (its `uploadFile` is "only valid with a PUT"), so uploads go through a worker thread (Python `urllib`) or by writing the frame into `~/ComfyUI-Shared/input` (see 3.3).
4. **Recommended shape: a recipe-built `comfy` COMP, then typed tools.** First `td_exec` recipes build `/project1/comfy` (Script TOP out, Text DAT workflow, Web Client DAT or thread worker, Table DAT of jobs). When it has been used 3+ times, promote to `td_comfy_build / td_comfy_send / td_comfy_result / td_comfy_cancel` (section 4). The `comfyui` MCP (official comfy-mcp) is the **other-side driver**: `validate_workflow`, `run_workflow`, `job`, `fetch_outputs`, `upload_file`, `system_stats`, `free_memory`, `search_models`, `download_model`.
5. **Real-time vs batch on this M1 Max: batch.** Published best case for diffusion on Apple silicon is SDXS-512 ~12-18 fps *estimated* for M1/M2/M3 Max, SD-Turbo 512 ~10 fps on an M3 Ultra, and it fights TD for the same GPU (`T_realtime_ml.md` 1-2, 3.1). ComfyUI's per-job overhead (HTTP queue, model load, VAE, PNG round trip) is on top. Treat Comfy as **a few seconds to minutes per frame/clip** (stills, textures, splats, restyled loops) feeding TD and the PF26 pipeline offline, not a live layer. StreamDiffusionTD local mode is Windows + NVIDIA only (`X` row 39).
6. **Existing TD <-> Comfy tools** (section 2): TDComfyUI (olegchomp, 284 stars, workflow JSON in a Text DAT, needs Acly's tooling nodes), ComfyUI-TD + ComfyUI2TD.tox (JiSenHua, 168 stars, AGPL-3.0, Windows paths in docs), ComfyTD (dotsimulate, Mac unstated), `comfyui-NDI`. None states macOS or build 31550 support; all three TD-side `.tox` would be audit-then-try, never trust.
7. **The one-line gap that matters:** **Comfy Desktop's workspace is not a comfy-cli workspace.** comfy-mcp's lifecycle tools (`launch_comfyui`, `stop_comfyui`, `restart_comfyui`, `get_logs`, `update_comfyui`, `install_node`) act on whichever workspace comfy-cli targets, not on `~/ComfyUI-Installs/JZB1`. Use only the HTTP-side tools with Desktop; start/stop Comfy Desktop by hand; read its log from `~/ComfyUI-Installs/JZB1/logs/comfyui.log` ([U] whether `comfy which` finds the Desktop install at all: first live check).
8. **Safe ordering** (section 6): TD-only offline tests -> user opens Comfy Desktop -> `server_info` -> a free local workflow (SHARP, already installed) -> only then diffusion (needs a model download = gate) -> partner/credit nodes last, each with a cap.

---

## 2. Existing TD <-> ComfyUI pieces

| Item | What it is / how it talks | Mac + 31550 | Licence | Verdict |
|---|---|---|---|---|
| **TDComfyUI** (olegchomp), github.com/olegchomp/TDComfyUI, 284 stars, 14 forks, 24 commits [V fetch] | `.tox` front end for the ComfyUI API. Workflow (API format) in a Text DAT -> InDAT; pars generated from the workflow; "Generate" button; callbacks `onConnected/onDisconnected/onGenerated/onParameterCreated`. Image **in** via Acly `ETN_LoadImageBase64` (TOP set on a par), image **out** via Acly `Send Image (WebSocket)`; example `TouchDesigner_img2img.json` | OS and TD build not stated on the page; needs only a reachable ComfyUI [V]. Mac [U] | none stated | Best template to copy the *pattern* from (read the .tox as text via toeexpand; do not load unaudited) |
| **Acly/comfyui-tooling-nodes** [V fetch] | Custom nodes: Load Image (Base64), Load Mask (Base64), Send Image (WebSocket) (binary msg = two big-endian ints 1 and 2, then PNG bytes; then an `executed` JSON). Pure Python | No OS specifics [V]; should work on MPS [U] | **GPL-3.0** | Needed by TDComfyUI; install into Comfy = an install gate |
| **ComfyUI-TD + ComfyUI2TD.tox** (JiSenHua), 168 stars, 164 commits, AGPL-3.0 [V fetch; stars in our scrape `research_src/popular/github.jsonl` rank 26] | Comfy-side nodes `ImagetoTD`, `ImagetoTD(JPEG)`, `LoadTDImage` (TD TOP -> Comfy), `VideotoTD`, `AudiotoTD`, 3D to point cloud, `3DGStoTD` (Gaussian splat PLY; needs ComfyUI-Sharp and tox v5.3.x+). WebSocket stream; `broadcast` option | Docs show Windows paths; macOS not mentioned [V] | AGPL-3.0 | **Interesting match for this install** (ComfyUI-Sharp is already here and `sharp_*.ply` exists) but unaudited and Windows-biased; candidate for a user-approved test |
| **ComfyTD** (dotsimulate) | Component to drive ComfyUI workflows from TD, link pars and inputs (Derivative tutorial, Marco, 22 Sep 2025) [V page; body only in a YouTube video] | Mac not stated anywhere I could read (`X` row 40) [U] | Patreon-style, closed [U] | Skip (do not download); read its docs only |
| **StreamDiffusionTD** (dotsimulate) | TD <-> StreamDiffusion; **local mode Windows + NVIDIA only; Mac = Daydream cloud only** (`X` row 39) | no | closed | Not Comfy; mentioned because it is the "real-time" tool and does not apply |
| **comfyui-NDI** (ningxiaoxiao) [S search] | Comfy nodes pulling/sending frames over NDI (`pip install ndi-python`, NDI Tools) | Mac [U] | [U] | Real-time-ish route Comfy <-> TD NDI In/Out; extra install, [U] |
| Spout/Syphon nodes: Jovimetrix `SPOUT WRITER` (Windows), `decadetw-spout-syphon-im-vj`, `MKRShift Syphon Sender` [S] | GPU texture share | Syphon on Mac [U], not verified | [U] | Hint only; Syphon between an arm64 process and Rosetta TD is itself [U] (`T` 4) |
| TD built-ins [D] | `webclientDAT` (HTTP; `request(url, method, header, data, pars, ..., uploadFile, timeout)`; callbacks `onConnect/onDisconnect/onResponse(dat, statusCode, headerDict, data)`), `websocketDAT` (live-confirmed T-04; pars `active reset netaddress port timeout callbacks clamp maxlines`), `webserverDAT`, `moviefileinTOP`, `scriptTOP` (`copyNumpyArray`, `loadByteArray(ext, bytes)`), `TOP.save/saveByteArray/numpyArray`, ThreadManager (`op.TDResources.ThreadManager`, palette `threadManagerClient.tox`, default 4 workers) | all present in 31550 [V offline help] | Derivative | The whole integration can be built from these |

The user's folder `~/Documents/Comfyui REal time ` exists and is **empty** (seen 26 Oct); no earlier work to reuse there.

---

## 3. Patterns

### 3.1 The ComfyUI HTTP / websocket API (read from the local source, v0.34.5)

| Call | Facts |
|---|---|
| `POST /prompt` | Body `{"prompt": <API-format graph>, "client_id": "<uuid>", "prompt_id": "<uuid, optional>", "extra_data": {...}, "partial_execution_targets": [...]}`. Reply `{"prompt_id", "number", "node_errors"}`; invalid graph = HTTP 400 `{"error", "node_errors"}`. A client-chosen `prompt_id` must be a lowercase hyphenated UUID, which lets TD know the job id before the reply [L server.py 1072-1134] |
| `GET /history/{prompt_id}` | `{}` while queued/running, `{<id>: {"outputs": {node: {"images": [{"filename","subfolder","type"}]}}, "status": ...}}` when done. Cheap poll target [L 1059] |
| `GET /api/jobs/{id}` , `GET /api/jobs` | Per-job state incl. queued/running/finished (newer API) ; `POST /api/jobs/{id}/cancel` [L 821-989] |
| `GET /view?filename=&subfolder=&type=output` | Returns the file (PNG etc.). `type` = input/output/temp. Path traversal rejected [L 516]. `&preview=` makes a downscaled copy |
| `POST /upload/image` | **multipart/form-data**, field `image` (file), optional `type` (default input), `subfolder`, `overwrite=true`; reply `{"name","subfolder","type"}`; without overwrite a name clash becomes `name (1).png` unless the hash matches [L 400-470]. `LoadImage` then takes `name` (or `subfolder/name`) |
| `POST /interrupt`, `POST /queue` (`{"delete":[ids]}` / clear), `GET /queue`, `POST /free` (`unload_models`, `free_memory`), `GET /system_stats`, `GET /object_info[/{class}]`, `GET /models/{folder}` | as named [L] |
| `GET /ws?clientId=<uuid>` | First message `status` (queue info + `sid`). Then per job: `execution_start`, `execution_cached`, `executing {node}`, `progress {value,max,node,prompt_id}`, `executed {node, output}`, `execution_success`, `execution_error`, `execution_interrupted`; the older "done" signal is `executing` with `node: null` [L main.py 405/471, execution.py]. **Events go only to the client whose `client_id` was sent with the prompt** (`send_sync(..., server.client_id)`), so TD must use the same uuid on `/ws` and `/prompt`. Binary frames = 4-byte event type (1 PREVIEW_IMAGE, 2 UNENCODED, 3 TEXT, 4 PREVIEW_WITH_METADATA) + 4-byte format + image bytes (latent previews, `SaveImageWebsocket` in `custom_nodes/websocket_image_save.py`) [L protocol.py] |
| Security | `origin_only_middleware`: rejects cross-site browser requests and Host/Origin mismatches on loopback; **it only checks when an `Origin` header is present, and TD's websocket DAT sends none (T-04)**, so TD and `urllib` pass. No auth: keep `--listen` off |

### 3.2 How TD calls it, without ever blocking the main thread

TD rules that bind this (all [V] in repo docs): never touch OPs/pars from a thread (`PLATFORM.md` 112, `Experimental-Thread_Manager`); Web Client DAT responses arrive in `onResponse` on the main thread; the `numpyArray()` of a just-force-cooked TOP can be zeros (T-13); two force-cooks in one frame feed identical frames (T-21).

| Route | Op chain / code | Good for | Limits |
|---|---|---|---|
| **A. Web Client DAT (async, built in)** | `webclientDAT` `url=http://127.0.0.1:8188/prompt`, `reqmethod=POST`, header table (`Content-Type application/json`), data from the Text DAT; or `me.request(url, 'POST', header={...}, data=json_text, timeout=5000)` returns a connection id; result in `onResponse(dat, statusCode, headerDict, data)` | `POST /prompt`, `GET /history`, `GET /queue`, `GET /system_stats`, `POST /interrupt`: all JSON. The network I/O is off the main thread (the DAT's own job) | **no multipart** (`uploadFile` = raw PUT only [D]); binary bodies in `onResponse` as `bytes`: [U] whether PNG bytes arrive intact (the DAT is documented as outputting text), so images are fetched another way |
| **B. Python in a ThreadManager task** | `op.TDResources.ThreadManager.TDTask(target=fn, args=(...), SuccessHook=..., ExceptHook=...)`; `fn` uses stdlib `urllib.request` / `http.client` (always present; `requests` is in the bundled-package list but only cv2/numpy were checked live, T-19) with **plain data only**, no `op()` inside; results come back through `SuccessHook` (main thread) | multipart upload, `GET /view` bytes, polling loops, the PNG encode | Never read `par.x` inside `fn`: pass values in. A hung request holds a worker (default 4): always pass `timeout=` |
| **C. WebSocket DAT** | `websocketDAT` `netaddress=127.0.0.1`, `port=8188`, callback `onReceiveText(dat,rowIndex,message)` parses `progress / executing / execution_success` into a Table/Constant CHOP | push progress (no polling) | TD requests path `/` (T-04); ComfyUI needs `/ws?clientId=...` [L]. **[U] whether the DAT accepts a path/query in `netaddress`** (first thing to probe). If not: poll (A). Binary frames land in `onReceiveBinary` [D] |
| **D. Web Server DAT (inverse)** | Comfy pushes to TD: a Comfy-side node `POST`s a result to `http://127.0.0.1:<port>/`; `onHTTPRequest` reads it | event-driven results from a custom Comfy node | needs a custom Comfy node and a TD listening port (opens a port: gate) |
| **E. Script DAT / `td_exec` one-shot** | `td_exec` runs `urllib` directly: **blocks TD's main thread for the call** | quick manual probes with a 3 s timeout only | Never in a loop or per frame; T-22 shows frame counts stretch under blocking |

Recommended default: **A + B + polling**, C as an upgrade after the probe. Poll cadence 4-10 Hz is plenty (Comfy jobs take seconds).

### 3.3 TD TOP -> Comfy: send a frame, run, load the result

```
[any TOP] -> resolutionTOP (e.g. 512x896, vertical) -> nullTOP "comfy_in"
   |  main thread, once per request:  data = op('comfy_in').saveByteArray('.png')     # in memory, no disk  [D PLATFORM 87/386]
   |  ThreadManager task:
   |     1. POST /upload/image  (multipart: image=data, name="td_<jobid>.png", overwrite=true)  ->  {"name": ...}
   |     2. fill the workflow template: LoadImage.inputs.image = name; KSampler.inputs.seed = N; prompt text ...
   |     3. POST /prompt  {"prompt": graph, "client_id": CID, "prompt_id": JID}
   |     4. poll GET /history/JID until non-empty (timeout 120 s); read outputs[node].images[i]
   |     5. GET /view?filename=&subfolder=&type=output  -> bytes
   |  SuccessHook (main thread): scriptTOP.loadByteArray('.png', bytes)  OR  write file + moviefileinTOP.par.file; reload
[scriptTOP "comfy_out"] -> nullTOP -> (look / Syphon out)
```

Variants: (a) **file hand-off** (no upload): `saveByteArray` -> write to `~/ComfyUI-Shared/input/td_<id>.png`, `LoadImage` takes the filename. Simpler, no multipart, but writes into the other app's folder (the brief forbids writing the other app's *config*; an input image is data, still ask the user once) and Comfy's file watcher/asset registry may index it. (b) **Output by disk**: read `~/ComfyUI-Shared/output/<file>` straight into a Movie File In (`file` par, reload pulse): no `/view` call needed because the output dir is shared on this machine. (c) **MCP-staged**: the `comfyui` MCP `upload_file(paths=[abs png])` (HTTP `/upload`) after TD saved the PNG with `td_exec` `op(...).save(path)`; keeps TD out of the HTTP business entirely.

Cost notes [U, measure at first live test]: `saveByteArray('.png')` of 1080x1920 is a CPU encode on the main thread (likely tens to ~100+ ms); downscale first, or use `.jpg`; `TOP.save(file, asynchronous=True)` exists [D PLATFORM 87]. Comfy `LoadImage` reads RGB(+mask from alpha). Result sizes: SD-class models output 512-1024 px; upscale on the GPU in TD (Resolution TOP) to 1080x1920, never the LED canvas (names/faces stay out of any Comfy restyle, `T` 3.1).

### 3.4 Workflow JSON templating (API format)

- **Export** from the Comfy UI with "Save (API Format)" (Dev mode on, as TDComfyUI says); the **API format** is `{ "<node_id>": {"class_type": "KSampler", "inputs": {"seed": 5, "model": ["4", 0], ...}} }`. Links are `[node_id, output_index]`; literals are values. The UI-format workflow (`SHARP - Mac image to splat.json`, with `nodes`/`links`) is a different file: `POST /prompt` rejects it; comfy-mcp `run_workflow` accepts both ("API-format or UI export") [V README].
- **Template store in TD**: Text DAT `workflow_api` (file-synced, `syncfile`) + Table DAT `slots` (`slot, node, input, type, value, source`), e.g. `positive | 6 | text | str | par:Prompt`, `seed | 3 | seed | int | par:Seed`, `init | 10 | image | file | upload:comfy_in`. Templating = `json.loads(text)` then `graph[node]['inputs'][input] = value` in the worker; never string-replace JSON.
- **Slots**: comfy-mcp's `list_workflow_slots / set_workflow_slot / vary_workflow` use addresses like `6.text` on *frontend-format* templates, matching the slot-table idea; same address syntax (`<node>.<input>`) in TD keeps both sides compatible.
- **Seed rule**: set `seed` per job (`control_after_generate` does not run through the API); log the seed in the job table so a look can be reproduced.
- **Custom pars on the COMP** (`td_custom_pars` exists): `Host`, `Port` (8188), `Clientid` (uuid, read-only), `Workflow` (DAT), `Status`, `Progress`, `Promptid`, `Submit` (pulse), `Cancel` (pulse), `Timeout`.

### 3.5 Real-time vs batch on this M1 Max

- Comfy runs on `mps` with 64 GB unified memory (`Set vram state to: SHARED`) [V log], i.e. **TD and Comfy share one GPU and one memory pool**. A 1080x1920 TD look at 30 fps plus a diffusion step = contention (`T` 2). Run Comfy while TD is idle, paused, or on a light look, and call `free_memory` (MCP) afterwards.
- Measured here: only SHARP, 14.99 s per image [V log]. For diffusion there is no local number (no checkpoint installed). Use `T_realtime_ml.md`'s inference ranges only as bounds: SD-Turbo/SDXS single-step *may* give ~1-2 s per 512 frame on MPS in Comfy, SDXL-class tens of seconds [U].
- Fits Comfy: still plates and textures for looks, restyled keyframes, img2img of a TD render, depth/normal/segment maps as nodes, image -> splat (`ComfyUI-Sharp`), upscaling stills, batch variations (`vary_workflow`). Does not fit: per-frame live restyle of IMAG/camera, anything lip-sync critical.
- Offline loop pipeline: TD renders 5-30 s source -> frame batch -> Comfy img2img with fixed seed + low denoise -> frames back -> `moviefileout` / ffmpeg to the PF26 master path (`C_pf26_fit.md` 3). Flicker control is the user's creative question; Comfy does not give temporal consistency by default [U].
- **Rules that still bind** (user memory): flat screen-content only, no stage mockups; full-colour PRISM logo; names/words never altered by a generator; research before generating; approved looks go to the PF26 viewer through the existing flow, not straight from Comfy.

### 3.6 Return paths other than PNG

| Result | Route in TD | Status |
|---|---|---|
| PNG/JPG still | `/view` bytes -> Script TOP `loadByteArray`, or Movie File In on the output file | works by design |
| Video (VideoHelperSuite / `SaveVideo`) | Movie File In on `~/ComfyUI-Shared/output/*.mp4` after `/history` shows it | [U] codec: H.264 plays; Hap/ProRes need an ffmpeg step |
| Gaussian splat `.ply` (SHARP) | Is a PLY reader available? **[U]** TD 31550 POP/SOP import of PLY not probed (`PointClouds/` samples dir exists in the app; check in a TD-only test) | Candidate showpiece; test with the existing `sharp_*.ply` |
| Latent previews | websocket binary frames (route C) | [U] |
| Audio / 3D | via ComfyUI-TD nodes | not planned |

---

## 4. Proposed jazib-td upgrades

Rules honoured: one structural change per call, always arrange, viewers on, nothing written to Comfy's config files, newer-build features gated. Stage 1 = `td_exec` recipes (no new code); Stage 2 = typed tools after 3 real uses (CLAUDE.md "when the same job keeps coming up, add a typed tool").

### 4.1 Stage 1: recipe (a `td_exec` per step, `td_layout flow` after each)

1. `td_create` `baseCOMP` `/project1/comfy` (label "ComfyUI bridge"). 2. Inside: `textDAT workflow_api` (file-synced), `tableDAT slots`, `tableDAT jobs` (`job, promptid, state, progress, started, seed, outputs`), `scriptTOP comfy_out` (+ callbacks DAT), `moviefileinTOP comfy_file`, `nullTOP out`, `webclientDAT http`, optional `websocketDAT ws`, `textDAT ext` (extension: `Submit()`, `Poll()`, `Cancel()`, `OnDone()`), custom pars from 3.4. 3. `td_custom_pars` for the page. 4. `td_errors` and `td_layout check`.
Safe to build and test with **no Comfy running**: every request fails with a connection error that the DAT reports (the failure path is part of the test, section 5).

### 4.2 Stage 2: typed tools (names proposed)

| Tool | Args | Side | What it does in TD | Pairs with `comfyui` MCP |
|---|---|---|---|---|
| `td_comfy_build` | `{parent="/project1", name="comfy", host="127.0.0.1", port=8188, workflow_file?, res=[512,896]}` | `td/handlers.py` `comfy_build` (+ `src/server.js` schema) | Builds the COMP of 4.1 (one structural change; arranged; viewers on). Port default 8188, overridable because `portConflict: auto` | `server_info` first (is it up, which workspace); `system_stats` (VRAM/RAM) |
| `td_comfy_status` | `{comp}` | handlers (read-only) | GET `/system_stats`, `/queue`, `/object_info` class count via the worker; reports `reachable`, `version`, `queue`, `argv`. Never raises when Comfy is closed (returns `reachable:false` + the hint "open Comfy Desktop") | `server_info`, `system_stats`, `which` |
| `td_comfy_send` | `{comp, workflow:"<dat path\|file>", set?:{"6.text":"...", "3.seed":42}, image?:{top:"/project1/x/out", slot:"10.image"}, wait=false, timeout_s=120, confirm_spend=false}` | handlers (worker thread) + `src` | `saveByteArray` once on the main thread, thread: upload, apply slots, `POST /prompt` with client `prompt_id`; returns `{promptid, queued_at}` at once. **Refuses graphs containing partner-API node classes unless the user said go** (`confirm_spend`; list from `/object_info` / class-name prefix, [U] rule) | `validate_workflow` on the same file first; `list_workflow_slots`; `run_workflow` is the MCP-only alternative that never touches TD |
| `td_comfy_result` | `{comp, promptid?, load=true}` | handlers | `/history` state; on done fetch `/view` (thread) and load into `comfy_out` (Script TOP) or `comfy_file`; returns `{state, progress, outputs:[{file, w, h}], top:"/project1/comfy/out"}` and a `td_screenshot` hint | `job(action="status"/"wait"/"error")` on the same `prompt_id` (it is the same server); `fetch_outputs(prompt_id, out_dir)` to also copy to disk |
| `td_comfy_cancel` | `{comp, promptid?}` | handlers | `POST /interrupt {prompt_id}` and `/queue {delete:[id]}` | `job(action="cancel")` |
| `td_comfy_free` (optional) | `{comp}` | handlers | `POST /free {unload_models:true,free_memory:true}` | `free_memory` |

Notes: all HTTP is in `td/handlers.py` workers (stdlib only; no new dependency, so no AUDIT row); `src/` only declares schemas and adds the spend guard text; PROTOCOL.md gets one row per command. A TD-side `comfy` COMP built by recipe stays the source of truth, so a tool can be dropped without breaking saved projects. Gate on `app.build`: none needed (all ops exist in 31550 [D]).

### 4.3 Which `comfyui` MCP tools to use for what (official comfy-mcp 0.10.0, 39 tools [V README])

- **Use with Comfy Desktop (HTTP only):** `server_info`, `system_stats`, `free_memory`, `validate_workflow`, `run_workflow` (free local graphs; `confirm_spend=False` default fails closed on partner nodes), `job`, `fetch_outputs`, `upload_file`, `nodes` / `workflow_deps` (what the live install has), `search_models`, `list_workflow_slots / set_workflow_slot / vary_workflow`, `search_templates / get_template / fetch_template`.
- **Do not use against Desktop:** `launch_comfyui`, `stop_comfyui`, `restart_comfyui`, `get_logs`, `update_comfyui`, `switch_comfyui_version`, `install_node`, `download_model`, `download`: they act on comfy-cli's workspace [V README], not `~/ComfyUI-Installs/JZB1`, and `install_node`/`download_model` change installs (user's go-ahead anyway). Read the Desktop log as a file.
- **Spend:** `partner_generate`, `list_partner_models`, `partner_model_schema`, `emit_partner_workflow`, `run_template` with partner nodes, `auth_login`: credits, per-job approval with a cap, same as Flow's `max_credits`. `COMFY_API_KEY` is not set in `.mcp.json`; keep it that way unless the user wants it.
- **Typical chain (one Claude session):** `td_comfy_status` -> MCP `server_info` -> MCP `validate_workflow` (template file TD wrote) -> `td_comfy_send` -> MCP `job(wait)` or `td_comfy_result` -> `td_inspect`/`td_screenshot` of `comfy_out` -> look goes into the PF26 flow by `assets_where.py`. Reverse chain: MCP `run_workflow` for a batch, `fetch_outputs` to a folder, TD Movie File In reads the folder.

---

## 5. Test plan

### 5.1 Offline (no TD, no app)
- `test/test_handlers.py`: the workflow templating function (slot table -> graph edit; unknown slot = error naming it; array links `[id, i]` untouched), client `prompt_id` is a lowercase UUID, spend guard (graph with a partner `class_type` -> refused without `confirm_spend`), multipart builder produces a body `aiohttp` accepts (parse with `email`/`cgi` in the test).
- A fake ComfyUI in the test: a ~60-line `http.server` on an ephemeral port serving `/prompt`, `/history/{id}` (empty twice, then outputs), `/view`, `/upload/image`, `/system_stats`, and a 400 case with `node_errors`; handlers run against it from Python with no TD (same style as `test_watchdog.py`).
- `npm test` for the schemas (src side), plus PROTOCOL.md rows.

### 5.2 TD-only (safe; Comfy closed)
1. Build `/project1/comfy` by recipe (4.1); `td_errors`, `td_layout check`; viewers on. Expect: no errors, network reads left to right.
2. Click Submit with Comfy closed. Expect `reachable:false`, a status string, no frozen UI (measure `td_perf` and fps before/after; the request must not stall frames: if it does, the call is on the main thread, fix per T-22).
3. Point the COMP at the **fake server of 5.1** (it can run as a separate Python process the user lets me start) and run the full cycle with a test PNG: upload, prompt, poll, view, load. Expect the Script TOP shows the returned image; time each stage with `absTime`.
4. Probes: (i) does `saveByteArray('.png')` of 512x896 and 1080x1920 return bytes and how long (ms)? (ii) does `webclientDAT.onResponse` deliver binary intact? (iii) does `websocketDAT.netaddress` accept `127.0.0.1/ws?clientId=...`? (iv) is `requests` importable in TD's Python? (v) can a PLY load (POP/SOP) at all? Record to LEARNINGS (T-nn).

### 5.3 APP (needs Comfy Desktop open; the user's go-ahead for each; no credits)
1. User opens Comfy Desktop (instance JZB1). `lsof -nP -iTCP:8188 -sTCP:LISTEN` and MCP `server_info`; expect `127.0.0.1:8188` ComfyUI 0.34.5, device `mps`. If `server_info` shows a different workspace or none: note it (open question 3) and rely on the HTTP tools.
2. `system_stats`: expect `vram_total` ~64 GB shared. `nodes` (or `/object_info`): expect SHARP nodes present.
3. **Free local workflow first:** run the user's existing `sharp-image-to-splat.json` (UI format) with the existing input image `sharp-sample-beach.jpg` through MCP `run_workflow`; expect a new `sharp_*.ply` after ~15 s (matches the logged 14.99 s). Then the same from TD: `td_comfy_send` with a TOP as the image. No download, no credits.
4. If the user wants diffusion: they pick one small checkpoint (SD-Turbo / SDXS class per `T`); `search_models` then `download_model` is an install gate; then a 512x512 img2img from a TD frame; time it, watch TD fps during the run, call `free_memory`.
5. Failure drills: kill Comfy mid-job (expect `execution_*` absent, poll times out -> state `timeout`, no hung worker); cancel (`/interrupt`); invalid graph (HTTP 400 `node_errors` shown in the jobs table).
6. Partner nodes: not tested unless the user asks, with a credit cap per job.

---

## 6. Gates

- Opening/closing Comfy Desktop, any model or custom-node download, `install_node`, `comfy-cli` installs, Manager changes: user's go-ahead (install gates; `mcp-vendor/README.md`).
- Credits: partner models, partner-API nodes, Comfy Cloud (`inst-1788645883930` "Comfy Cloud" exists as an installation entry): per-job approval with a cap. Never set `COMFY_API_KEY` ourselves.
- Do not write Comfy Desktop's files (`settings.json`, `installations.json`, `extra_model_paths` yaml, `user/`); the only allowed writes are images handed over via `/upload/image` or (once approved) `~/ComfyUI-Shared/input`.
- Telemetry: Comfy Desktop `settings.json` has `telemetryEnabled: true` and there is a PostHog id file in its folder [V]. That is the app's own behaviour, outside our MCP; comfy-cli telemetry must stay off via env (`COMFY_NO_TELEMETRY=1`, `DO_NOT_TRACK=1`), per AH. Raise with the user; changing the Desktop setting is theirs.
- Licences: comfy-mcp AGPL-3.0-or-later OR commercial (local private use fine, do not redistribute), Acly tooling nodes GPL-3.0, ComfyUI-TD AGPL-3.0: audit before any install, note in AUDIT.md; none is a dependency of jazib-td in the stdlib design.
- Opening ports: the Web Server DAT route (3.2 D) listens on a TD port: not used in the base design.
- PF26 rules (flat visuals, names intact, approved flow) bind any Comfy output used for the show.

## 7. Sources

Local [V]: `~/Library/Application Support/Comfy Desktop/{settings.json, installations.json, last-session.json, ops-flags.json, instance-model-paths/*.yaml, window-state.json}`; `~/ComfyUI-Installs/JZB1/{manifest.json, logs/comfyui*.log, ComfyUI/server.py, execution.py, main.py, protocol.py, script_examples/websockets_api_example.py, custom_nodes/websocket_image_save.py, user/default/workflows/}`; `~/ComfyUI-Shared/{input,output,models}`; `mcp-vendor/comfy-mcp/src/README.md` and `src/comfy_mcp/*.py` (v0.10.0, venv has comfy-cli 1.22.0); `/Applications/TouchDesigner 2.app/.../Learn/OfflineHelp/https.docs.derivative.ca/{Web_Client_DAT, WebclientDAT_Class, Experimental-Thread_Manager}.htm`; `docs/research/{T_realtime_ml, X_tutorials_workflow_output (rows 39-41), AH_relevant_mcps (5), ops/PLATFORM, ops/DAT, ops/TOP}.md`; `LEARNINGS.md` T-04, T-13, T-19, T-21, T-22.
Web [V fetched]: https://github.com/olegchomp/TDComfyUI ; https://github.com/JiSenHua/ComfyUI-TD ; https://github.com/Acly/comfyui-tooling-nodes ; https://derivative.ca/community-post/tutorial/comfyui-workflows-touchdesigner/72860 (ComfyTD announcement only). [S]: https://www.comfyonline.app/comfyui-nodes/comfyui-NDI ; https://runcomfy.com/comfyui-nodes/Jovimetrix/SPOUT-WRITER--JOV--- ; https://www.comfyonline.app/comfyui-nodes/ComfyUI-decadetw-spout-syphon-im-vj ; https://comfy.icu/node/MKRSyphonSenderPlan ; https://interactiveimmersive.io/blog/artificial-intelligence/integrating-comfyui-with-touchdesigner/ (body truncated on fetch).

## 8. Open questions

1. Does the user want Comfy used for PF26 offline looks (img2img of TD renders, keyframes), for the splat (SHARP) idea, or only as an experiment? That decides Stage 1 vs Stage 2 and whether a checkpoint download is worth asking.
2. Which checkpoint(s), if any, may be downloaded (disk, licence: SD-Turbo = Stability Community licence, `T` 3.1)?
3. Does comfy-cli (`comfy which`) see the Desktop install at all, and does `server_info` report Desktop's workspace? If not, lifecycle tools stay unused (as planned). Check at the first live step.
4. Can the WebSocket DAT take a path/query (`/ws?clientId=`)? If not, polling is final.
5. Should we test ComfyUI-TD / ComfyUI2TD.tox (AGPL, Windows-biased) for the splat route, after an audit? Or build our own minimal return path (this file) first (recommended)?
6. `telemetryEnabled: true` in Comfy Desktop: does the user want it turned off (their setting, not ours)?
7. Is a PLY loadable in TD 31550 (POP/SOP) so SHARP results can be shown? Probe in 5.2.
8. Should `td_comfy_send` hard-refuse partner nodes, or ask once per job like Flow? (Proposed: refuse unless `confirm_spend` and a cap.)
