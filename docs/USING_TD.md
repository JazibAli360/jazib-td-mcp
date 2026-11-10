# Using TouchDesigner through Jazib MCP (td_guide)

## Before anything
1. `td_status`. If TD isn't connected: TD must be open with `/jazib_mcp` in the project (README, Setup 3). The user
   runs **2025.31550** (`/Applications/TouchDesigner 2.app`, Rosetta), not 2025.32820. Name the build in claims.
2. Read `LEARNINGS.md` (this MCP) and `../td-port/LEARNINGS.md` for TD facts. Ask TD rather than guess: one
   `td_exec` probe answers an API question faster than a build-and-crash cycle.

## Knowledge base
Before building show visuals: `docs/research/README.md` (task -> file index: TD 2025 how-to, techniques,
PF26 fit, camera/MediaPipe, DIRECTIONS). Live-confirmed facts: `LEARNINGS.md` (wins on conflict).

## Look it up before you set it
`td_help` answers op-type questions offline (TD not needed): `{op:"noiseTOP", page?|par?}` gives par names, menu
values, defaults and ranges; `{search:"blur"}` finds op types; `{par:"resolutionw"}` lists ops that have it; `docs:true`
adds the offline wiki summary. Use it before `td_create`/`td_set_pars` instead of a `td_exec` probe (does the type
exist, what is the menu name). Data = the 2025.31550 live dump + TD's shipped help.

## Making an effect: research first (user rule, 16 Oct 2026)
"Someone probably already made it." Before building any effect/look, search: the OP Snippets (479 example .tox) and Palette (278 .tox) inside the app
(`docs/research/ops/PLATFORM.md`; `toeexpand` reads a .tox as text), the TD Palette (shipped .tox),
Derivative community/forum + tutorials, GitHub .tox/GLSL, Shadertoy/ISF, `../td-port/` and `../stagelab/docs/specs/`.
Write the findings (link, licence, how it works) into `docs/research/` + a README row, then adapt the best one.
Imports: audited, free licence, pinned (AUDIT.md); downloading a .tox/plugin from the web needs the user's OK.

## Resolution (user rule, 16 Oct 2026)
Every TD look/build is **vertical 1080p: 1080x1920** (set it on generators / Render TOPs / GLSL TOPs; check with
td_info width/height). The 7488x2880 figures in docs/research are measurements, not the build size.

## Layout: always arranged (user rule, 16 Oct 2026)
Flow left to right, main chain (input 0) on one row, side inputs below, CHOP control band on top, docked DATs under
their op, a Null at each chain's end, a titled network box per module (`td_layout` annotate). td_create/connect/
disconnect/delete/tox_load re-flow the COMP; after a td_exec build call `td_layout` (flow, then check: ok must be true).
Spec + numbers: `docs/research/G_network_layout.md`.

## The user watches live (user rule, 26 Oct 2026)
Node viewers on and left on; never pile ops on one spot (or rebuild the same names over the same spot); the network
pane follows the COMP you work in. `td_create` and `td_exec` do this (exec reply `visible`); check with `td_layout check`, and look with `td_window_capture` (the network window, a panel window by title, or a
dialog: its window list shows popups TD opened, e.g. an overwrite prompt or "Missing Parent Shortcut").
`td_focus {path}` shows the user the op you mean or just changed (pane to its COMP, op selected + homed; `flash:true` adds a
0.5 s yellow tint, colour put back, opt-in since it touches the user's colours; UI only, no undo step). "This node" / "the selected one" = `td_selection` `this`
(current/selected op, never the mouse rollover); `this` null = several selected, ask which.

## Readable networks (user rule, 26 Oct 2026)
Every COMP must read at a glance for a human: `td_layout {mode:"stages", stages:[{ops, title, body, role, after?}]}`.
Default `arrange: mixed`: signal L->R inside a stage (branches on their own lanes T->B); stages that feed others sit to
their left; stages at the same depth stack top to bottom; `after` = dependency without a wire. Boxes (annotate mode:
title + note). Parameter references (render camera/geometry/lights, projection map, material) count as flow, like wires.
**The plan is stored on the COMP** (T-69): every later build (create/connect/exec...) re-applies it and places new
ops itself (wired -> its neighbour's stage; unwired panels/windows/their scripts -> `Controls`, on top of column 0;
anything else -> `Other`: give it a real stage). `check` fails on an op inside a box it is not in, an op in no box, or
boxes on each other; a build's `visible.layout` carries `placed` / `intruders`. `mode:"unstage"` drops the plan.
Then look with `td_window_capture`.

## 60 fps target (user rule, 26 Oct 2026)
The whole project must hold 60 fps (16.6 ms/frame). Per COMP aim <= 3 ms cook; check `td_perf` and the real fps
(`perform` fps CHOP / `project` stats) with everything else running; add `Quality`/resolution pars to heavy COMPs,
stop cooking what nobody uses (allowCooking, Switch instead of Cross, no always-cook), prefer single-pass/compute GLSL.

## Crash-safe building (T-70)
- Register your COMP for the job (T-95): `python3 tools/lane.py add <COMP> "<agent label>"` at the start,
  `python3 tools/lane.py remove <COMP>` at the end. After a crash the watchdog relaunches TD and `tools/td_recover.py`
  parks every lab COMP not listed there (and not touched by td_exec in the last 10 min). If TD disconnects, wait
  for "TD recovered" in `logs/recovery.log` (or the reconnect), re-check your COMP, re-enable it, continue.
- `absTime.frame` identical in two execs >= 1 s apart = TD's frame loop stopped while it still answers (T-95): report
  it with what you changed last; do not restart TD yourself.
- Destroying a panel (or ops inside it) that an open Window COMP or a network pane shows crashed TD (UI-thread SIGBUS).
  Use `safe_destroy(op)` in td_exec (td_delete does it): closes those windows, moves panes off, defers the destroy.
- Rebuild panels in place (update children) instead of destroying the container; close your own window first.
- At most 2 agents build live in one TD (user rule; up to 10 once stable). Never change cookRate live (T-64).
- **Scratch TD for risky code (T-83):** anything matching a known crash pattern (TOP reads right after a change,
  cookRate/realTime changes, destroy under windows, complex-script fonts, window COMPs) is tried on a disposable second
  TD first: `python3 tools/scratch_td.py start` (fresh `projects/scratch/Scratch.toe`, own bridge 9336, no autosave,
  no heartbeat), then `td_exec {code, target:'scratch'}` or `python3 tools/scratch_td.py run "<code>" --frames N`,
  then `stop`. Logs: `logs/scratch/`. The main TD's td_exec adds a note when code matches a pattern; the crash guard
  is only a note on the scratch TD. Never run a known crash pattern on the main TD.
- **Build TDs b2 / b3 (T-120; user 26 Oct: "you can even have 3 td builds live"):** up to 3 TDs build at once: main +
  `b2` (bridge 9337, `projects/build2/`) + `b3` (9338, `projects/build3/`). `python3 tools/scratch_td.py
  start|status|stop --name b2` (one start at a time; `run --name b2 "<code>"` works without the MCP). Unlike scratch
  they KEEP their project (newest `Build2[.N].toe` reopens; autosave 5 min; `stop` saves first), the crash guard stays
  on, logs go to `logs/b2/`, the watchdog ignores them. Build with the usual tools plus `target:'b2'`: `td_exec`,
  `td_create`, `td_set_pars`, `td_get_pars`, `td_connect`, `td_delete`, `td_list`, `td_info`, `td_inspect`,
  `td_errors`, `td_layout`, `td_screenshot`, `td_perf`, `td_health`, `td_net_export`, `td_tox_save/load`,
  `td_checkpoint` (-> `output/checkpoints_b2/`), `td_restore_checkpoint`, `td_save_project`, `td_library_export`.
  A target whose TD reports another identity (`tdInfo.instance`) or sits on the main port is refused. **Done =
  brought home:** `td_bring_home {comp:'/project1/lab/X', from:'b2', parent?:'/project1/lab', park?:true}` saves the
  COMP to `output/transfer/X.tox` + saves the b2 project, then in the main TD checkpoints + safe_destroys an existing
  X (its xy/colour/wires kept), loads the .tox as X, reads errors 3 frames later, re-applies the stage plan, parks it
  and saves the main .toe; reply `check {ops_equal, errors, warnings}`. It refuses a COMP another lane registered in
  `logs/active_lanes.json`. Then verify in main (un-park your own COMP, `td_inspect` in a later call). Main is still
  where the user looks: nothing lives only in a build TD. Each build TD costs GPU/RAM: stop it when your lane is done
  (leave it if another lane uses it).

## Crash guard + crash diagnostics (26 Oct 2026)
- **td_exec crash guard:** every td_exec is checked against the crash fingerprints in `logs/crash_patterns.json`
  (`td/crashdb.py`; seeded with T-64 cookRate set live, T-70 `.destroy()` while a Window COMP is open, T-74
  `numpyArray()` and T-76 `evalTextSize()` in the script that creates/changes TOPs). A match is refused with the
  pattern's LEARNINGS id, rule and way past it: `frames >= 2` for the readback patterns (read in a second td_exec),
  or the pattern's opt-out marker (`# allow-readback`, `# allow-cookrate`, `# allow-destroy`) when you are sure.
  T-70: use `safe_destroy(op)`, it is never refused. Code features are AST tokens (`call:numpyArray`,
  `assign:par.font*`, `kw:cook.force`, `assign:cookRate`), so comments and reads do not trigger. The guard sees only
  the td_exec text, not builder files it execs. The file is re-read on change (no td_reload).
- **faulthandler:** handlers enables Python's faulthandler on load (`all_threads=True`) into
  `logs/td_faulthandler.log`, one `=== jazib-td faulthandler session pid=.. build=.. project=.. ===` line per TD
  process. On SIGSEGV/SIGBUS it writes every Python thread's stack (a td_exec shows as `File "<jazib_mcp exec>", line
  N`), then TD's own crash handler runs as before. Check: `op('/jazib_mcp/handlers').module.faulthandler_status()`.
- **After a crash** (watchdog relaunched TD, or TD sits on its Fatal Error dialog): `td_crash_report` (TD not
  needed) = newest `~/Library/Logs/DiagnosticReports/TouchDesigner-*.ips` (signal, crashed thread's libs: `libGX <-
  libC_TOP <- Python` = a TOP Python call on the cook thread; `libUT/libUI/libOPUI` = UI drawing) + the faulthandler
  session of that pid + the td_execs in flight from `logs/exec.log` -> known pattern, or a PROPOSED pattern. The
  main session reviews it: LEARNINGS T-nn first, then the pattern into `logs/crash_patterns.json` (`status` "active",
  narrowed matcher). Proposals are never added automatically and never guard td_exec while `status` is "proposed".

## Lose nothing: pre-risk save + COMP checkpoints (26 Oct 2026, after crashes T-64/T-70/T-74/T-76; `td/safety.py`)
- **Pre-risk save is automatic.** Before a risky call the MCP saves the project in place first (next X.N.toe, like
  td_save_project): td_exec / td_create of an op type this project never had, a `.tox` or C++ plugin load, font /
  fontfile pars, a builder build (`builders/<x>.py`, `ns['build'](...)`), `safe_destroy` / `.destroy()`, td_delete of
  a COMP, a module reload (td_reload, `importlib`), a checkpoint restore, the typed builders (td_shadertoy,
  td_publish, td_midi_build, td_debug_panel ...). At most one save per 60 s counting EVERY save (autosave,
  td_save_project); skipped while realTime is off (offline render), in perform mode and before the first save. The
  reply says what happened: `pre_save {reasons, saved | skipped, ms}`. If TD then crashes, the newest save (what the
  watchdog reopens) is the state just before the risky call. `# no-presave` in exec code opts out (for a loop of
  small, known-safe destroys); `td_presave {on, min_s, check:{cmd, args}}` reads/sets it and dry-runs a call.
  Not the atlas td_save_hook: that one runs AFTER a save and writes the `.jtdnet` network text; with it on, every
  pre-risk save also leaves a diffable text, so the two stack.
- **Checkpoint every COMP that verifies.** At the end of a builder step, once td_errors is clean: `td_checkpoint
  {path, note:"<what this step added>"}`. It checks errors itself (force-cook, 2 frames) and refuses a broken COMP
  (`force:true` to keep one anyway), then writes `output/checkpoints/<comp>/<comp>_<stamp>.tox` + a `.json`
  (parent, xy, wires, cooking state, stage plan, build), keeping the newest 5. The COMP is not changed: no About
  stamp, never switched to externaltox. `list:true` shows what exists.
- **Restore** (a crash lost the COMP or a rebuild broke it): `td_restore_checkpoint {path, which:"latest"}` (or
  `"previous"`, an index, a stamp prefix). The current COMP is saved first to `pre_restore/` (lose nothing), the .tox
  loads into the same parent with cooking off, the old one goes through safe_destroy (T-70), the new one takes the
  name, place, wires, cooking state and stage plan, and its windows reopen 10 frames later. After a watchdog
  relaunch: if the COMP that was in flight has a checkpoint newer than the save TD reopened, restore it, then re-run
  only the builder steps after that checkpoint.

## Component library (27 Oct 2026; `td/library.py`, `library/`)
Finished, live-verified COMPs go into `library/<Name>/` for reuse in any project: `td_library_export {path}` (COMP
.tox + thumb.png + README.md + meta.json; `library/INDEX.md` + `index.json` regenerated), `td_library_list`,
`td_library_info {name}`, `td_library_load {name, parent, newname?}`.
- Export only a COMP nobody is building (it refuses one in `logs/active_lanes.json`). A parked COMP is un-parked for
  the thumbnail (Out TOP force-cooked 2 frames later, read 3+ frames after that, T-74) and parked again.
- `meta.json` `files` lists every file par and where it points (`repo` / `td_app` / `outside`, `exists`): an
  `outside` or missing file means the .tox will not work on another machine until that file is there.
- A .tox over 5 MB stays out of git (`library/.gitignore`); meta + sha256 stay, so re-export it on the new machine.
- A load lands parked with viewers on and its stage plan re-applied: turn it on (`allowCooking`) when you use it.

## Design note: lab COMPs as external .tox files? (26 Oct 2026, proposal only, nothing migrated)
Idea: each lab COMP (`/project1/lab/<X>`) gets `externaltox = projects/modules/<X>.tox`, `enableexternaltox` on, so
the .toe holds references and each COMP lives in its own file (research U 1.2; Ragan, Embody).
- **Pros:** the .toe gets small, so every save (autosave every 5 min, pre-risk saves) is quicker and hitches less
  [U: not measured]; one COMP can be reloaded from disk (`enableexternaltoxpulse`) without reopening the project; a
  COMP that crashes TD on load can be switched off (`enableexternaltox` off) and the rest of the lab still opens; two
  lanes write different files; per-COMP history (a small binary .tox per module, versionable); the same module drops
  into the show .toe.
- **Cons:** "faster project loads" is not a given: TD still loads every .tox at start (same content, more files)
  [U]; a COMP edited live is only on disk after `saveExternalTox` / `project.save(..., saveExternalToxs=True)`, so the
  plain in-place save (autosave, pre-risk save) would NOT keep its changes unless `savebackup` stays on (then the .toe
  is not smaller) - the opposite of "lose nothing"; unknown whether TD's CrashAutoSave writes changed external
  contents [U, needs a probe]; the watchdog's offline scan of the crash autosave (T-77, toeexpand) would no longer
  see a COMP's insides; nested externalisation asks a GUI question the MCP cannot see (research U 1.2), and modal
  prompts hang the bridge (T-37); relative path behaviour changed in 2023 builds; td_tox_save on a parent of an
  external COMP behaves differently.
- **Verdict for now:** keep the lab inside the .toe; checkpoints give per-COMP recovery without changing how the
  project loads or saves, and builders/*.py already rebuild most lab COMPs from text. Revisit for the show file freeze
  (Ragan's "only save toxes" workflow, `savebackup` on) after two live probes: (1) project load time with 5 lab COMPs
  external vs embedded on 31550; (2) does a CrashAutoSave keep unsaved edits of an external COMP.

## Self-contained effect COMPs (user rule, 26 Oct 2026)
Each effect COMP holds everything it needs: its custom parameters drive the internals (pause any panel: nothing
breaks), its Out TOP/CHOP carries the output only (no controls in it), and its own `controls` panel (autoUI,
`Pagescope` = slider page, `Pagetabs` off, `align verttb`, widget clones cut so the COMP stands alone) + a
`controls_window` opened by an `Opencontrols` pulse on the COMP. No shared lab-wide panel: one long panel cannot
be scrolled.

## Undo
Every command that changes the network (create, delete, rename, move, connect, disconnect, set_pars, dat_text,
custom_pars, tox_load, layout, exec, save_hook, the builders: publish, osc_learn, link, live_audio, tda_load,
import_ae_anim, comfy_build, midi_*, record_chop, shadertoy, osc_expose, layer_mixer, cook_active, debug_panel_build,
restore_checkpoint) is one TD undo step:
the user can Ctrl+Z any MCP call (T-54). Full list: `MUTATING` in td/handlers.py (PROTOCOL "Undo").

## Housekeeping
`td_housekeeping` (read-only, ~35 ms on the home project) before a save, a handoff or a show. It never deletes or turns
viewers off: orphans and leftovers are listed for the user to decide (spec: `docs/research/U_housekeeping_workspace.md`).
Tag an op `keep` to exempt it from orphan candidates.

## Numbers, not pictures
`td_inspect {path}` reads values back (read-only): CHOP channel min/max/mean/last, TOP per-RGBA stats (+ `sample:4`
grid, row 0 = top), DAT head rows, SOP/POP counts + bounds + attribute names, COMP children by family. Use it to check
"moving / not black / in range" before a screenshot; if a note says numpy failed, restart TD (T-48).
## Network as text (snapshot, compare)
`td_net_export {path, file:"snapshots/<name>"}` saves a COMP as deterministic JSON lines (one op per line: type,
non-default pars as value / `=expr` / `~bind`, wires by name, custom pars by page, DAT text) under `output/`; without
`file` the text comes back (cap ~60k chars). Before a risky change: export to a file; after: `td_net_diff {a: that file,
b: "/project1/comp"}` lists added/removed ops, changed pars ([before, after], null = default) and rewired inputs. Two
files diff with TD closed. Read-only; it is not a backup (no import yet): keep `td_tox_save` for that.

## TD + ComfyUI
`td_comfy_build {parent:"/project1"}` makes `/project1/comfy` (client DAT, workflow DAT, status/jobs tables, pump, result
Movie File In -> `out`). All HTTP runs in the client's background threads (stdlib urllib, loopback only, never on TD's
main thread); commands return at once. Chain: `td_comfy_status` (reachable? with Comfy Desktop closed it says so) ->
`td_comfy_send {comp, workflow: API-format JSON or file, inputs:{"6.text":"...","3.seed":42}, image_from:"/project1/look/out"}`
-> `td_comfy_result {comp}` until `done` (image in `<comp>/out`, files in `output/comfy/`) -> `td_comfy_free` to give
the GPU back. Export workflows with "Save (API Format)"; set `seed` yourself per job. **Partner/API nodes spend credits:
send refuses them; `confirm_spend:true` only with the user's go-ahead for that job.** Opening Comfy Desktop, model or
node downloads: the user's call. Comfy on this M1 is batch (seconds to minutes per image), not a live layer (research AL).
## TD + Resolume (Arena 7.23.2, research `docs/research/AI_td_resolume.md`)
Never write Arena's files (osc.xml, AdvancedOutput.xml, slices.xml, compositions); reading them is fine. Every Arena
call (resolume-723), every Syphon/NDI sender start and every OSC listener start = the user's go-ahead, each time.
- **Video out:** `td_publish {name, source:"/project1/look/out1", transport:"syphon"|"ndi"|"both", alpha?, res?}`
  builds `publish_<name>` **inactive** and tells you the sender to pick in Arena (Syphon `TD_<name>`; NDI
  `HOST (TD_<name>)`). With the user's OK: `td_publish {name, active:true}`; the user drags the source onto a clip in a
  scratch composition, then resolume-723: `get_composition`, `set_layer_blend_mode` Add, `trigger_clip`,
  `set_layer_opacity`/`set_layer_bypass` (the Arena-side kill). `td_publish {name}` (active defaults false) is the TD kill.
  `td_publish_status` lists every sender (active, size, cook, NDI skipped frames) and warns on duplicate names.
- **Alpha:** TD composites are premultiplied, Arena's clip Alpha Type defaults to Premultiplied: so the default
  (`alpha` premultiplied, `source_alpha` premultiplied) adds no step. Straight source: `source_alpha:"straight"`
  (Level premultiply). No alpha: `alpha:"none"` (GLSL, over black; use Add). Alpha claims stay "not checked in Arena"
  until the ramp test (AI T5). `td_screenshot` flattens alpha over white (T-12): judge alpha with `td_inspect`.
- **Sizes:** `res` adds a Fit TOP (fit best). Looks are 1080x1920 (user rule); 7488x2880 costs 86 MB/frame (AI).
- **OSC learn:** `td_osc_learn` (build, inactive) -> user turns on Arena Preferences > OSC Output (127.0.0.1:7001) ->
  `td_osc_learn {action:"start", seconds:60, arena_build:"7.23.2.51094"}` while the user wiggles faders / fires clips /
  changes BPM -> `output/osc_addresses_<build>.json`. The map is a starting point, not gospel: re-learn on any Arena
  change. **Port 7001 trade-off:** Arena has one OSC Output target; while TD listens there, resolume-723
  `osc_query`/`osc_subscribe` (they bind 7001) go quiet; `osc_send` (to 7000) still works. Stop learn before using them.
- **Clip bake (recipe, not a tool yet; FUTURE.md):** offline ProRes render with a frame check (T-11, T-29, T-30):
  1. a **fresh** Movie File Out per bake (T-30): `td_create {parent, type:"moviefileoutTOP", name:"bake_out",
     pars:{type:{menu:"movie"}, videocodec:{menu:"prores"}, file:"<abs>.mov"}}`, `td_connect` the look's out Null into
     it; for alpha pick a 4444 entry of `videocodectype` (read the menu with `td_get_pars` first).
  2. a docked Execute DAT, `frameend` on, that force-cooks it every frame while recording and stops at N (T-29):
     `def onFrameEnd(frame):` / `m = op('bake_out')` / `if m.par.record.eval():` / `m.cook(force=True)` /
     `n = me.fetch('n', 0) + 1; me.store('n', n)` / `if n >= N: m.par.record = False`.
  3. `td_exec`: remember `project.realTime`, set it False (big frames drop in realtime, T-11), `record = True`;
     when it stops, restore `realTime`.
  4. check: `ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of csv=p=0 <file>`
     must equal N (T-11 saw 69 of 71); premultiplied masters: assert rgb <= alpha on the out Null first.
  5. DXV3 is the Alley step (hyperframes H-36); Arena import is by hand on 7.23. Delete `bake_out` after.
## TD + Ableton (research AJ_td_ableton.md; Live is driven by the separate `ableton-live` MCP)
| Job | TD side (jazib-td) | Live side (ableton-live) |
|---|---|---|
| Tempo / phase | `td_link` (builds `link` COMP, Link off), then `td_link {enable:true}`; read `td_link_status` (`out`: beat bar bar_ramp tempo peers) | `set_ableton_link` true, `set_tempo`, `start_playback` / `stop_playback`, `tap_tempo`, `get_session_info` (tempo, Link state) |
| TDAbleton (song/tracks/clips/levels over OSC) | `td_tda {action:"check"}` (read-only), `load` only with `accept_risk:true` + the user's go-ahead (Live-side script listens on 0.0.0.0 with remote Python), `status` | `get_session_info`, `get_session_snapshot` (compare names: TDA dislikes duplicates and `#`) |
| Live audio into AC_audio | `td_live_audio {mode:"device", device:"BlackHole 2ch"}` builds the input inactive; `activate:true` only with the user's go-ahead (mic permission); `mode:"file"` goes back | route Live's output to the loopback device (Settings, GUI only); no device: `get_master_meters` / `get_track_meters` (a few Hz, for panels) |
| Cues / scenes | `td_exec` recipes until `td_cue_map` exists (AJ 3.5) | `fire_scene`, `fire_clip`, `stop_all_clips`, `jump_to_cue` |
Gates: installing the TDA Remote Script, any Max device, Control Surface rows, IAC buses, BlackHole, firewall changes =
the user's go-ahead each; never press TDA's Install/Update/Start (Install edits Live's `Library.cfg`); set-changing Live
calls on a disposable set only. Link start/stop follows only with Start Stop Sync on both sides (GUI in Live).
## TD + After Effects
Pairs with the read-only `aftereffects` MCP (AUDIT.md; AE open = the user's go-ahead; its write tools need write mode =
the user's go-ahead per session). Design + test plan: `docs/research/AK_td_aftereffects.md`.
- **AE motion -> TD:** `ae_project_export_json {outPath: <jazib-td-mcp>/output/ae/<name>.json}` (AE side, read-only), then
  `td_import_ae_anim {file, dry:true}` (counts + warnings, no TD), then without dry: COMP `ae_<comp>` with keys/text/markers
  tables and `out` CHOP (one sample per comp frame; units td = Transform TOP fractions, scale/opacity /100; units ae = raw).
  Warnings name what is not exact: expressions (bake with `ae_do comp.sample`), spatial paths (straight segments),
  parenting. Pick layers first with `ae_layer_info {detail:"summary"}`.
- **TD curves -> AE:** `td_export_ae_data {chop, file, format, frames?}` writes data footage under `output/ae_out/`; AE
  imports it in write mode (`project.import_file`, expression `footage(...)`). Read-only in TD.
- **TD look -> AE footage:** `td_render_for_ae {source, file, frames, fps}` = ProRes 4444 premultiplied with alpha (TD's own
  convention; AE: `footage.interpret alphaMode premultiplied`). Check `frames_ok` (ffprobe count) every time (T-11);
  match the timeline rate to fps or the content plays faster/slower (the reply says). Never write into AE's mailbox
  folder, prefs or .aep files.

## TD + Blender (26 Oct 2026; Blender 5.2.2 LTS, brew cask; design docs/research/BC_blender_td_scripts.md s6)
- **Blender scene -> TD:** `td_import_blender {blend, dry:true}` exports headless first (`tools/blender_export.py`: factory
  startup, autoexec off; writes `output/blender/<name>/<name>.usdc` + `<name>.json`), then without dry builds COMP
  `bl_<name>`: `geo` USD COMP (Y-up metres, import pulsed; `geo:'fbx'` for an FBX COMP), `cam_*` Camera COMPs (horz FOV
  from lens + sensor fit + render aspect; shift -> winx/winy; clip -> near/far), `light_*` Light COMPs, projectors =
  Blender lights with custom prop `projector` (image path, or true = ramp test image; `projector_throw`, `projector_res`,
  `projector_shift`) -> `map_*` TOP + projmap simplehorzfov, projangle = horizontal FOV from the throw, cone covers the
  image diagonal; `ambient`; `render` -> `out` through the `Camera` par. Controls on the Blender page. An existing
  export: `{usd | fbx, sidecar?}`. Maths: `tools/blender_td_logic.py` (td = (x, z, -y); cameras/lights keep their -Z
  look axis). Not modelled: projector lens shift (warns), watts are a dimmer heuristic, TD attenuation off, animation.
- **First live run on the scratch TD** (USD COMP import, Render TOP `geometry geo` and the `imp` pulse are unprobed),
  then the main TD with `td_perf` (60 fps rule; Resw/Resh lower the render). Live-check list: BC doc s8.
- **Driving Blender itself:** the `blender` MCP (official Blender Lab server, `../mcp-vendor/blender-mcp-official/`),
  once installed and enabled by the user. Its `execute_blender_code` runs any Python in Blender: ask each time.
## MIDI mapping (own system, research AR section 6; TDXMap not adopted)
`td_midi_build` makes `/project1/jazib_midi`, a self-contained COMP: it carries its own code (`midi_core` = value
logic from `td/midi_core.py`, `runtime` = TD I/O from `td/midi_runtime.py`) and plain tables, so it keeps working in a
saved .toe without the MCP. Rebuild after editing either file (mappings stay). Device = TD's MIDI Device Mapper entry
(Dialogs > MIDI Device Mapper, the user adds the controller once; `Device` menu on the COMP, `Refreshdevices` pulse).
- **Bind:** `td_midi_learn {target, par, wait_s:20}` then the user moves one control (hover mode: no target, the user
  hovers a parameter while moving the control; the COMP's `Learn` pulse does the same without the MCP). Smart learn
  picks absolute / relative encoder (2c, bin, sign) / button (toggle, momentary on Momentary pars, trigger on Pulse) /
  14-bit / pitch bend. Or explicit: `td_midi_map {mapping:{target, par, kind, channel, number, mode, curve, takeover}}`.
  min/max default to the par's normMin/normMax; channel 0 = any; re-learning a par replaces its binding.
- **Per mapping:** curve (linear, ease_in/out/in_out, log, exp, smoothstep, steps:N), invert, clamp, takeover
  (none, pickup = wait until the control meets the value, scale), smooth (seconds), feedback (LED ring / motor fader),
  step (relative). Banks: `Activebank` / `td_midi_bank`; bank 0 = always live.
- **Test without hardware:** `td_midi_simulate {kind:"cc", channel:1, number:7, value:127}` (or `events:[...]`) sends
  raw bytes into the same entry the MIDI In callback uses; check with `td_midi_monitor` and `td_inspect`/`td_get_pars`.
- **Files:** `td_midi_save {file:"show.json"}` -> `<project>/midi_maps/show.json`; `td_midi_load`. Controller templates:
  `td_midi_preset` (unbound slots; `generic_8x8` is an assumption, re-learn on the real controller).
- The editor (`Openeditor` pulse) is a scrolling list: click a cell to edit (label, bank, target.par, min, max, curve,
  mode, takeover, smooth, fb), `LRN` re-learns that row, `x` deletes it. Values are written with `par.val` only (never
  expressions); an exported par is skipped. Engine errors never raise in the callback: `td_midi_status` `last_error`.
- Not yet checked live on 31550 (built from TD's shipped offline help): MIDI In callback `bytes` format, the device
  table columns, MIDI Out CHOP send methods with a real port, List COMP `onEdit` timing, `ui.rolloverPar` during a MIDI cook.
## What TD stays quiet about (health, trace, journal, offline)
After building anything: `td_health {path}` (default /project1; ~1.5 s) samples twice and lists what `td_errors` cannot:
ops that change but nothing pulls (not running), never-cooked ops, outputs switched off, GLSL compile failures, script
tracebacks (`recheck:true` tells live from stale), slow cooks (stale cook times apart), fps / throttled window / paused
timeline, bypassed gain ops, feedback loops, Level TOPs making negative floats, absTime / unseeded random reads, file pars
naming missing files, NaN CHOPs. Bring TD to the front first (a background window throttles). An image is black or
wrong: `td_trace {path}` walks up its inputs and names the node where it was lost (`look_at`). What did I call / what
failed: `td_log` (`failures`, `summary`, `cmd`, `since`); every bridge call is in `logs/calls.jsonl`. A saved project
with TD closed: `td_offline {file}` (tree, `mode:"text"`, `query` grep in DAT code, `other` diff two files; works on a
copy). Git-diffable history: `td_save_hook {on:true, path}` writes `<project>.<root>.jtdnet` beside the .toe on save
(off by default; ask the user first, it adds a DAT to /jazib_mcp).

## Parameters, colours, mirrored pars, tox stamps (27 Oct 2026, research AM)
- **Hex colours:** `td_set_pars {path, pars:{color:"#00baff"}}` sets colorr/g/b (+ `alpha` with `#rrggbbaa`); works
  for `bgcolor` (+ bgalpha), custom RGB/RGBA groups (`Tint` -> Tintr..Tinta) and member names. value/255, written as
  is (no sRGB-to-linear). A Str par keeps the text.
- **Mirror pars (self-contained COMPs):** `td_custom_pars {path:comp, page:"Blur", mirror:{src:"blur1", pars:["size*"]}}`
  puts the inner op's built-in pars on the COMP and binds the inner ones to them, so the COMP's own pars drive it.
  Default: every page but Common; read-only and expression pars are skipped (listed with why; `replace_expr:true`
  takes them over); pulses relay through `mirror_pulse`. The inner op must live inside the COMP.
- **tox stamp:** `td_tox_save` writes an About page first (Version, Touchbuild, Saved). `bump:"patch"` before a
  release save; `version:"1.0.0"` to set; `stamp:false` to save untouched.

## Recording a CHOP (repeatable bakes)
`td_record_chop {chop, seconds:10}` (or `frames`) samples the CHOP once per frame into `<chop>_rec` (Table DAT:
frame, time, channels) and, with `file:"kick"`, `output/recordings/kick.csv`. `channels:"kick* snare"` filters. Frame
gaps (dropped frames in realTime) are reported; play it back with a DAT to CHOP. Freeze audio features or an OSC take
before an offline render so the render is repeatable.

## Timeline by data (TL_timeline phase 4, `docs/builds/timeline_phase4.md`)
`td_timeline_show` gives the whole show as JSON (settings, lanes + keys, markers, clips); `td_timeline_edit {ops}`
changes it (atomic batch, one undo step: add/move/delete keys, lanes, markers, clips, settings), `td_timeline_transport`
plays/seeks, `td_timeline_state {at}` reads values, `td_timeline_export` / `td_timeline_load` save and reload a show
(`output/timeline/`), `td_timeline_record` renders a take. Use musical times (`"8b"`, `"3.2.1"`, `"@Drop+2b"`) instead
of computing seconds. Inside TD the same API is promoted on the COMP: `op('TL_timeline').AddKey('level', '8b', 0.9)`.

## Shadertoy (research AN)
`td_shadertoy {code}` (the Image tab, or `file:` a .glsl/.frag) builds a self-contained COMP: GLSL TOP with every
Shadertoy uniform, `Channel0..3` pars for iChannel0..3, Play / Speed / Reset clock, Mouse pars for iMouse, Out TOP,
controls (Opencontrols). `compute:true` = compute shader (T-47: no tearing; use it for anything multi-pass or
heavy). Read `compile.ok` / `compile.errors` in the reply: line numbers are your own source lines. Not supported:
Buffer A-D (multi-pass: build one COMP per buffer and feed them with Channel pars), the Common tab (paste it above
mainImage), cubemaps, sound, keyboard. **Licence:** Shadertoy code defaults to CC BY-NC-SA 3.0; pass
`licence/author/url` (kept on the About page and in the source DAT).

## ISF shaders (td_isf; FX0 G-ISF)
`td_isf {file: 'media/demo/isf/Bad TV.fs', parent: '/project1/lab'}` imports an ISF filter/generator (VDMX / Vidvox;
the sibling `.vs` is picked up) as a self-contained COMP `isf_<stem>`: one GLSL TOP per ISF pass, Feedback TOPs for
PERSISTENT buffers, INPUTS as custom pars with the file's ranges/defaults (page ISF), image inputs as TOP pars on page
Images (the first falls back to the COMP's `in1`, so wire a source into the COMP; or `images: {inputImage: '/path'}`),
audio / audioFFT inputs as CHOP pars, zkit knob panel (Opencontrols; `panel:'plain'` = Parameter COMP). Reset clears
the persistent buffers. Read `compile.ok`; log line N / 0:N = your .fs line, 1:N = the .vs. Not supported:
vertex displacement (gl_Position in a .vs), cube maps, several outputs. All 327 Vidvox ISF-Files .fs translate and
compile with glslc offline (test/test_isf.py); live checks: docs/PROTOCOL.md `isf` + LEARNINGS. Vidvox ISF-Files are
MIT; other ISF files: pass `licence/author/url`.

## VAT: baked sims at 60 fps (td_vat_load; FX7c card 26)
`td_vat_load {demo: 'cloth'}` (or `{blend: 'x.blend', objects?, start?, end?, step?}` or `{json: 'vat/<name>/<name>.json'}`)
bakes in a headless Blender 5.2.2 (`tools/blender_vat.py`: factory startup, autoexec off; every visible mesh object,
evaluated with modifiers / sims, world space -> TD Y-up metres) into `output/vat/<name>/` and builds `vat_<name>`: the
rest mesh (`.obj`, uv w = point index) with a GLSL MAT that fetches each point's position (+ normal) per frame from a
32F EXR and lerps frames; out1 = render (orbit camera, 1080x1920), out2 = this frame's positions per point (32F, for
instancing / point effects). VAT page: Play, Speed (1 = bake fps), Loop (loop / once / pingpong), Interp, Scrub +
Frame (export audio or a timeline into Frame), Reset. Fixed topology only (cloth, soft body, shape keys, armatures,
deforms; not fluids / remesh: refused at bake). Cost is the mesh render, not the sim (demo cloth 2887 points: 1.9 ms
median incl. render). Max texture 8192 points wide (wraps into more rows per frame), 16384 rows. Houdini VAT files are
not read (Blender only, U6); layout in `tools/vat_logic.py`. Live check: frame k positions = the EXR to 1e-7 on b4.

## Metavido: recorded colour + depth + camera (td_metavido; FX7c card 27)
`td_metavido {}` (default the demo clip `media/demo/metavido/TaiwanStreet1-H264.mp4`, Keijiro's sample, Unlicense; or
`{file: '...mp4'}`) builds `mv_<stem>`: out1 colour (960x1080; Stencil on = people cut out by the recorded human
stencil, premultiplied), out2 depth in metres (960x540 32F), out3 world points (960x540 32F TD xyz per depth texel,
w = 1 when valid: instance from it or feed the pointcloud / PX colour+depth path with out1 + out2), `pose_out` CHOP
(tx ty tz rx ry rz [rotate order zxy] fov hfov near far shiftx shifty valid hash) and `cam`, the recording camera
(set the Render TOP camera to it to view the scene as recorded). Pars: Play, Speed, Scrub + Index, Stencil, Margin.
Live (b4, 31550): barcode bit-exact vs the reference on the same pixels, depth 1e-6 m (about 2 cm vs ffmpeg's own
YUV -> RGB), points = reference unprojection; TD index N = ffmpeg frame N - 1; the pose CHOP is one frame late
(nextframe download; the points TOP reads the barcode on the GPU, no lag). Cost: H.264 1080p decode ~5 ms GPU (the
clip, not the decoder: GLSL stages < 0.3 ms each, pose download ~0.9 ms CPU). Format notes: `tools/metavido_logic.py`.

## OSC out of any COMP (research AY)
`td_osc_expose {comp}` builds `<comp>_osc`: every custom par of the COMP as `/<comp>/<Par>` (tuplets = one message,
N args). Off until asked: `active:true` sends (127.0.0.1:9000, change-only, `rate_hz` cap), `receive:true` listens
(127.0.0.1:9001) and writes only the mapped pars (no command route), `oscquery:true` serves OSCQuery JSON (TCP, loopback
clients only) for TouchOSC / Chataigne / Vezer discovery; the JSON is always in the `oscquery` DAT. `layout:"osct"`
speaks OSCToolset's UE5 schema (`/OSCT/R/FLOAT/<comp>_<Par>`, ports 9999/9998). Each of send / receive / server is
network traffic: the user's go-ahead. Rebuildmap pulse after adding pars to the target.

## Layer mixer + cook guard (research AU)
`td_layer_mixer {layers:4, sources:[TOP or COMP paths]}` builds `mixer`: per layer Source / Opacity / Blend / Mute /
Solo (page Layer<n>), Master, Masterfx (put a master effect inside `fx_slot`), Out TOP `out1`. A layer at 0 is skipped
(no cook); with Cookguard, COMP sources no visible layer shows stop cooking (allowCooking off). Run it again to change
the source bank or the layer count. `td_cook_active {parent:"/project1/bank", active:["clip3"]}` is the same guard for
any set of COMPs (one live, the rest off).

## Webcam
Default source is the 5 s reference loop `media/webcam/webcam_ref_5s.mp4` (1920x1080, 30 fps). Open the live camera
only when the user asks or nothing else will do; set it inactive again after.

## When TD meets something new
Follow `docs/EVOLVING.md` (probe, LEARNINGS, upgrade the MCP, test, document, commit).

## Access
Full access (user, 16 Oct 2026): any op can be read, created, changed or deleted. Act like it's the user's show file:
- Look before you change: `td_info` / `td_get_pars` first.
- Before a big rebuild or a delete of something you didn't make: `td_checkpoint {path, verify:false}` (or `td_tox_save`
  the COMP to `output/backups/`). The project itself is pre-saved automatically before risky calls.
- `td_save_project` saves the user's .toe in place. Don't save unless asked or after a change the user wanted kept;
  saving as a new file is the safe default.
- Build new work inside its own COMP (e.g. `/project1/<thing>`), not loose in /project1.

## Building right
- Create → set pars → connect with explicit `inIndex` → `td_errors` on the COMP (frames ≥ 2) → `td_screenshot`
  the output TOP. Wiring is verified by `td_connect`; an error there is real, so stop and look.
- Multi-pass GLSL: use Compute mode (pixel-mode chains tear on this Mac, T-46/T-47).
- GLSL TOP: max 3 wired inputs, more via the `tops` par. Don't write `#version`. Use `sTD2DInputs[i]`, `vUV.st`,
  `uTDOutputInfo.res`, `TDOutputSwizzle()`. Compile errors come back from `td_errors`.
- Menus: `td_set_pars` with `{menu: "Name or Label"}`; a miss comes back as a warning, not a silent wrong value.
- Custom pars: names like `Centrex` (one capital, then lowercase/digits); labels hold the human name.
- Shader/script text is embedded in DATs; editing a file on disk changes nothing in TD until it is written in
  with `td_dat_text`.

## td_exec
Runs Python on TD's main thread with TD globals; returns stdout, stderr and the last expression's value. Every call
is logged in `logs/exec.log`. Use it for probes and one-offs; long loops freeze TD's UI while they run. When the
same exec keeps coming back, it should become a typed tool.
- **Dialog guard:** a modal box (`ui.messageBox`, `ui.chooseFile`, `ui.chooseFolder`) blocks TD's main thread, so the
  reply never comes. In td_exec they never open: messageBox returns 0 (first button), the choosers return None, and
  the reply lists them in `dialogs`. Pick answers with `dialogs: {messageBox: 1, chooseFile: "/abs/x.mov"}`. Code
  inside DAT modules / extensions that the exec calls still sees the real `ui` (e.g. a third-party "Remove?" pulse):
  don't pulse those from the MCP (research AM).

## When it goes wrong
- Timeout / no reply: TD may be busy, frozen or crashed. `pgrep -fl TouchDesigner`, look for
  `~/Desktop/CrashAutoSave.*.toe`. A crashed TD may show a macOS dialog Claude can't see. What killed it:
  `td_crash_report` (above, "Crash guard + crash diagnostics").
- Every bug: a `LEARNINGS.md` entry (T-nn) right away.

## Debugging any project (also ones you did not build)
- **What is this project?** `td_analyze {path:"/project1"}`: inventory, COMP tree, top-level flow (Mermaid), where
  Python runs (frame callbacks first), devices + ports, files (missing first), errors, heavy ops, dead-branch candidates,
  unresolved references. Report: `output/debug/<project>_<stamp>.md`. Huge project: it chunks itself (TD keeps running);
  page with `limit`/`offset`; `include:["packages"]` enters clones / palette packages. Closed file: `td_analyze_file
  {toe}` (no TD; never runs project code).
- **Why does this change / where does it come from?** `td_why {path, par?}`: tree of wires, expressions, binds, exports,
  reference pars, plus scripts that write it and Execute DATs watching it.
- **What is happening right now?** `td_watch {path, seconds:5}`: who cooks (cooks and estimated ms), which pars move,
  errors appearing / clearing, fps vs the cook rate. Leave the user's network alone while it runs (read-only).
- **What did I (or another lane) do?** `td_journal {since:"-30m"}` (filters agent / comp / tool / failures). For exact
  before/after networks turn the hook on first: `td_journal {snapshots:true}`, then `td_journal {diff:<snapshot id>}`;
  turn it off again when done (each mutating call costs two exports).
- **On screen for the user:** `td_debug_panel {scope:"/project1"}` builds `/project1/debug` (real-fps graph, top-10
  cook ops, 8 errors, 8 recent MCP actions; click a row = jump to the op). Since T-73 the view is spec tables -> Text
  TOPs (no List COMPs), redrawn only on change and never while the window is closed. Its cost: `op('/project1/debug/rt')
  .module.stats(op('/project1/debug'))` (tick ms ~0.4, `real_fps_2s` = real frame rate, wall clock between frame
  starts); measure with the window OPEN (T-72); `Active` off parks it.
- Findings are leads, not verdicts: "dead branch" and "unresolved" can be dynamic (scripts building paths). Confirm with
  `td_info` / `td_why` before changing anything you did not build.
