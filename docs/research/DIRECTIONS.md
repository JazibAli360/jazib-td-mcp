# DIRECTIONS — TD visuals for PRISMFEST'26 (lead's synthesis, 16 Oct 2026)

Compiled by the lead (Opus) from A (TD how-to, probed live), B (visual techniques + refs), C (PF26 fit) and
D (camera + MediaPipe, see `D_camera_mediapipe.md`). These are recommendations: **nothing is built until the user says
go** (build-only-what's-asked). Evidence for every line is in the A–D files they cite.

## 0. User decision (16 Oct, overrides the pre-render baseline below)
"ill probably use a ndi or syphon to bring stuff in resolume and keep controls in td — and yes its for 24 oct".
**TD runs live into Arena 7.23.2 (NDI or Syphon), controls in TD, for 24 Oct.** Offline ProRes renders stay as the
fallback/base-layer path. The live rig's research (real-time fps at wall size, Syphon vs NDI, controls, fail-safe,
rig + test plan) is `E_live_rig.md`. Starting Syphon/NDI or touching Arena still needs the user's go-ahead each time.
Answers: same Mac vs two machines **not decided** (E compares); controls **manual: on-screen TD panel + MIDI
controller** (sliders/buttons; Akai MPK Mini MK3 + Akai MIDImix), Arena→TD sync optional.

Decisions 16 Oct ~7:30 PM: **Arena 7.23.2** is the show host (this Mac's Arena.app reads 7.28.1: not for show
tests). **No MIDI hardware yet:** controls are TD sliders/buttons/constants on custom pars, MIDI mapped later.
**Crash watchdog: build.** **Build resolution: vertical 1080p, 1080x1920, for every TD look** (user, ~7:35 PM;
overrides the 7488x2880 build canvas below). Syphon is "just a node in td": no Syphon test now.

## 1. Settled facts (evidence in A §1–4, LEARNINGS T-09..T-17)
- Use **`TouchDesigner 2.app` (2025.31550, Pro licence)** only. No 1280 cap; max texture 16384; 7488x2880 and 9984x3840
  both cook. The native `TouchDesigner.app` is recorded as Non-Commercial: never for show renders.
- **Renders are offline** (`project.realTime = False`), **ProRes 422 HQ, 7488x2880, 30 fps** (TD renders 30 fps natively;
  "finished clips keep their source fps"). Realtime record at that size drops frames. TD has **no DXV**: the pipeline's
  existing DXV3 step stays. **Every render's frame count is checked with ffprobe** (a 71→69 gap was seen, cause unknown).
- Size: ~9–10 MB/frame ProRes at 7488x2880 → ~16–18 GB per minute (C §3, measured from existing masters).
- GLSL on macOS = Vulkan/MoltenVK (430 default, 460 selectable). POPs are in (97 classes). Urdu shapes in the Text TOP,
  but names/calligraphy still never come from TD (names-words rule).
- Face crops at 7488x2880 (verified live, A §6; matches `mapping.py`, C §2): L1 1152 · L2 L3 L4 576 · C 1728 ·
  R4 R3 R2 576 · R1 1152, all 2880 high. Build in plan space, assemble one atlas the same way as `mapping.py`
  (fold or authored returns per look); hard shapes stay inside one front face (L-32).

## 2. Where TD earns its place (C §1.3, §5)
Flow gives 8 s clips at 24 fps, loops that aren't clean, 3-clip walls that drift, no face-aware placement. TD gives exact
length, seamless loops, per-face timing, 30 fps, recolour by parameter, no credits. Ranked jobs (C §5):
1. **A03 countdown bed** (5 min, 9000 frames; C kept calm for the numerals).
2. **F05 portal bed + holds/TALK/B02 beds** (seamless 60–120 s).
3. **Wall-wide stings** F01/F03/F04/A04 and the open **F02 Facet Shatter**.
4. **E generic loop pack**, one family at a time, non-liquid first.
5. **G01 finale escalation + G02 bed.**
6. **Artist TAKEOVER hits**, after each act's world is approved.
7. Long DOORS variant (only if the D1 repeat shows).
8. **Live layer** (Arena layer 6): now the main path (§0); design per `E_live_rig.md`.
**Not TD:** names, logos, Urdu, "THANK YOU" (HyperFrames); countdown numerals (StageLab); info/emergency (plain posters);
painterly artist loops (Flow/Nano Banana).

## 3. Technique per job (B §4: the six that fit PRISM)
| Job | Technique (B) | Guard |
|---|---|---|
| A03, F05, holds, TALK | 6 gradient/tiling + grain; 2 soft spectrum beams | calm, 40–60 % brightness, 8 s+ cycles |
| F01, F03, A04 stings | 2 light beams / spectrum rays; 1 cheap-fake dispersion | soft light, not blades (hard graphics were denied) |
| F02 Facet Shatter | 3 triangle-facet instancing + POP shatter | one shard field per front face |
| E pack | 4 feedback + slit-scan; 6 tiling; POP particle weather | slit-scan/tiling = highest flash risk: check §4 limits |
| G01 finale, TAKEOVER | 1 dispersion (raymarched only for a hero moment), 2 beams | spectrum inside orchid → pink → amber, no rainbow (D4 rejected) |
| Numerals only | 5 kinetic type | never artist names |

## 4. Before the first look: Gate 0 (a test clip, not a PF26 look)
1. A 10 s, 300-frame test render, 7488x2880, 30 fps, ProRes 422 HQ, colour patches + a seamless-loop motion. Measure
   render time, confirm 300 frames with ffprobe, prove frame 301 = frame 1.
2. Colour round trip through `map_clip.py` (PIPELINE §5), then the existing DXV3 step.
3. Arena 7.23.2 decode of that DXV3 at 7488x2880: **an Arena operation, needs the user's go-ahead.**
Gate 0 measures render speed; until then no job gets a time estimate.

## 4b. Camera / MediaPipe (D, summary)
TD's own trackers (Body/Face Track, Optical Flow TOP, NVIDIA, Kinect, ZED) don't run on macOS. Routes that do: Blob
Track + OpenCV in TD (Farneback flow measured 42 ms/cook at 320x180 under Rosetta), the MediaPipe plugin
(torinmb v0.6.0, Web Render TOP, 188 MB, download needs the user's OK; Mac camera-permission issues are open), or
td-port's native arm64 camera_bridge (Apple Vision mask 33 ms, Depth Anything 67 ms, measured outside TD). Venue camera
plan (count, SDI/NDI, capture card) is still open in RUNTIME.md, so real-feed work waits; grades, masks, gesture logic
and fail-safes can be prototyped on the webcam or clips. IMAG on L1/R1 = 1152x2880 at 75%.

## 5. Rules that bind TD looks (C §3.4)
TD spends no credits, so the Flow video-credit gate doesn't apply. All the rest do: **3 different ideas per round, then
wait**; catalogue every look (`<ID> <Artist> · <STATE> · <idea> #n`, asset_where.py `--step video`, `viewer_add.py`);
show every result on the stage viewer; no repeat motifs; colourful logos; flash limits. TD clips have no still-approval
step: the clip is the first thing reviewed. Before the first `viewer_add`: a TD look-ID convention and the `E-*` entry
in `showplan.js` (C §3.1, open Q4).

## 6. MCP work this implies (proposed, not built)
- Typed **`td_record`**: offline render of a TOP to ProRes for N frames, realTime off/on around it, ffprobe frame check
  in the reply. The render recipe will keep repeating, so per CLAUDE.md it should become a tool.
- `td_screenshot` background option (alpha currently flattens over white, T-12).

## 7. Decisions for the user
1. ~~TD clips in the show?~~ Yes, live via NDI/Syphon (§0). Next: the rig + test plan in `E_live_rig.md`.
2. First job: A03 countdown bed (recommended) or another from §2?
3. Build `td_record` before Gate 0 (recommended: Gate 0 is its first use)?
4. ~~Live layer for 24 Oct?~~ Yes (§0). Camera work (D): in scope for 24 Oct? If yes: a supervised camera-permission
   test in TD 2 (you present), MediaPipe download OK or td-port helper first, and the venue camera plan.

## 8. UI Engine decision (lead, 16 Oct ~8:20 PM; evidence `I_ui_engine.md`)
**Skip UI Engine for the show panel.** It's a hand-copied library of themed widgets: no per-look auto-build from a
look COMP's custom pars (the user's "specific controls over each comp" rule, already working with Parameter COMPs in
`/project1/show/ui`), no documented binding/MIDI, proprietary licence (free, no redistribution), Patreon-gated, built on
2025.33070 (newer than our 31550), Mac support unstated, author warns of crashes with >2 modules. If the panel needs a
nicer performance look, upgrade with the shipped `autoUI.tox` / Basic Widgets bound through a Bind CHOP (T-44), free and
local. UI Engine stays an option only for decorative read-outs, and only after the user's download OK + AUDIT.md.
