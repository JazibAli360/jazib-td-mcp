# TL_timeline phase 4: agent-ready API (prepared offline 26 Oct 2026, TD 2025.31550 target; NOT yet run live)

Plan: `docs/builds/timeline_phases.md` (phase 4). COMP: `/project1/lab/TL_timeline`. Phases 1-2 unchanged; phase 4 is
added by the same `build()` call (`api=True`, the default). Local AI audio tools (beat/onset lanes, BPM estimate) are
the other half of phase 4 and are NOT in this prep.

## Status
- **Offline: done.** 35 tests (`test/test_timeline_api.py`): pure logic (times, every op, atomic/non-atomic, tables
  round trip, changed-table diff, show load/merge, exports, record plan, transport plan), the generated `TimelineExt`
  text run against fake ops (writes only changed tables, dry/atomic write nothing, lane tables created/destroyed,
  Load, Transport/State, Export to file, RecordPrepare/Arm/Finish), the record clock in `tl_actions.tick` (0 step in
  the arming frame, then 1/cookRate per TD frame), `build_api` extension pars, handlers routing + the record Pending
  chain (transport restored on success and on error). With phases 1-2: `python3 -I -m unittest discover -s test -p
  'test_timeline*.py'` -> 94 OK. Node: 7 `td_timeline_*` tools registered, schemas + file rules tested
  (`test/offline.test.mjs`).
- **Live: not run.** See LIVE CHECKs below.

## Build (live lane, one exec, then td_errors + td_layout check)
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/timeline.py').read(), ns)
ns['build']('/project1/lab')                 # clips=True, api=True are the defaults
```
Then `td_reload` (handlers.py has the new `timeline_*` commands) and restart the MCP server (new `td_timeline_*` tools).

## Files
| File | What |
|---|---|
| `builders/timeline_api_logic.py` | pure logic (copied into `tl_api_logic`): show doc <-> tables, time strings, 17 edit ops, apply_ops (atomic), load/merge, exports, record + transport plans |
| `builders/timeline_ext.py` | `EXT_TEXT` = the `TimelineExt` class (Text DAT `TimelineExt`), `build_api(comp)`: ext0object/ext0name/ext0promote + initializeExtensions (same pattern as zctl, live-proven there) |
| `builders/timeline.py` | `build(..., api=True)` execs timeline_ext.py; every `lane_*` table joins the Data stage; `tl_actions.tick` honours storage `tl_rec` (record clock) |
| `td/handlers.py` | commands `timeline_state/show/edit/load/transport/export/record` (section "TL_timeline agent API"); `offline_render(..., on_start=)` hook |
| `src/timeline.js` | MCP tools `td_timeline_*` (registerTimeline in server.js); files only under `output/timeline/{exports,shows,renders}/` |
| `test/test_timeline_api.py` | 35 offline tests |

## API (TimelineExt, promoted: `op('TL_timeline').AddKey(...)`)
- Reads: `Show(parts)` (tl-show v1 JSON), `State(at)` (transport + lane values + lane_status + clips on screen; `at` =
  lane values at times, pure maths), `Sample(t)`.
- Edits (all through `Edit(ops, atomic=True, dry=False)`): `AddKey MoveKey DeleteKey SetKeys AddLane SetLane BindLane
  DeleteLane AddMarker MoveMarker DeleteMarker AddClip SetClip MoveClip TrimClip DeleteClip Set(**settings)`,
  `Load(show, mode='replace'|'merge', dry)`. Reply `{ok, written, changed (tables), removed (lane tables), settings,
  results [{i, op, ok, ...|error, warnings?}], applied, summary}`.
- Transport: `Transport(action, **kw)`, `Play Pause Stop Seek(t|frame) Step(n)`; reply = State + `set`.
- Export: `Export(what='show'|'lanes_csv'|'markers_json'|'markers_csv', file, start, end, fps, lanes)`.
- Record: `RecordPrepare(start, end, fps, source)` -> plan; `RecordArm()` (offline_render on_start); `RecordFinish()`.
- Times everywhere: seconds, `"90f"`, `"8b"`, `"2bar"`, `"3.2.1"` (bar.beat.16th), `"00:00:04:15"`, `"01:04.5"`,
  `"@Marker"`, `"@Marker+2b"`.
- Edit ops: `add_key move_key delete_key set_keys add_lane set_lane delete_lane move_lane add_marker move_marker
  delete_marker add_clip set_clip move_clip trim_clip delete_clip set` (fields: `docs/PROTOCOL.md` "Timeline API").
  Marker names are unique (they are time anchors). Lane names `[A-Za-z_][A-Za-z0-9_]*` (they name `lane_<name>`).
- Only changed tables are rewritten (lanes, lane_<name>, markers, clips), settings pars only when changed (Length
  first). New lane tables get viewer on and join the Data stage box (`jz_stages` + `restage`); deleted ones go through
  `safe_destroy`. timeline_edit / timeline_load are one undo step each (MUTATING).

## Record clock
`RecordPrepare` parks the transport (Play off, Rate 1, Loop off, In/Out = take, Seek = start; old values in storage
`tl_rec.saved`). `offline_render` turns Record on and calls `RecordArm` (Play on, `tl_rec.armed`, `arm_frame =
absTime.frame`). `tl_actions.tick` then uses dt = 0 in the arming frame and dt = 1/cookRate after it (not wall time:
realTime is off for the take), so TL time follows the TD timeline the Movie File Out writes by (T-64: cooks = frames x
cookRate / fps). `RecordFinish` (end of the Pending chain, also on error) restores the transport and unstores
`tl_rec`.

## LIVE CHECKs (do in order; record numbers here; every bug -> LEARNINGS T-nn)
Rules: register the lane (`tools/lane.py add`), park other lab COMPs except recently touched ones, un-park only
TL_timeline; never change cookRate (T-64); never numpyArray() a TOP in the exec that changed it (T-74).
1. **Build**: td_errors clean; td_layout check ok; `tl_api_logic` + `TimelineExt` in the Data box; extension
   initialised (`op('/project1/lab/TL_timeline').ext.TimelineExt` not None, promoted `AddKey` callable on the COMP);
   rebuild with the controls window open: no crash (T-70), user tables kept.
2. **td_reload + MCP restart**: the 7 `td_timeline_*` tools listed; `td_timeline_state` replies (t, timecode, lane
   values equal `lanes_eval` channels at the same t within 1e-6).
3. **Edit round trip**: `td_timeline_edit` add_key `{lane:'level', t:'3b', v:0.9}` -> `lane_level` gains the row,
   ruler view redraws once (`view_data` 1 cook), `demo_level` follows while playing; `dry:true` changes nothing;
   an atomic batch with one bad op changes nothing (table text identical). Ctrl+Z undoes one edit as one step.
4. **Lanes**: add_lane with an absolute target (`/project1/lab/TL_timeline/demo_noise.ty`) -> `lane_<name>` created,
   viewer on, inside the Data box, `lane_status` ok; delete_lane -> table gone via safe_destroy, no errors, box refit.
5. **Clips**: add_clip / move_clip / trim_clip / delete_clip -> `clips` rows updated, `tl_clips` picks them up
   (clip_status, Clipactive), strip redraws; trim_clip out edge stops at the source end (media json).
6. **Transport**: play / pause / seek `@Drop` / step -3 / next_marker / prev_key; rate 2, loop off, in/out via
   transport; `td_timeline_state` agrees with `Timecode`/`Barbeat`/`Marker` pars.
7. **Show doc**: `td_timeline_export` show -> `td_timeline_load` the same file (replace) -> `changed` empty, nothing
   rewritten; merge a doc with one new lane + one replaced marker; a doc with a bad lane name changes nothing.
8. **Exports**: lanes_csv at 30 fps for 0..16 s = 480 rows, values equal `td_timeline_state at` for 3 sample times;
   markers_json / markers_csv frames + SMPTE right.
9. **Record**: `td_timeline_record {file:'take1', start:2, end:4, fps:30}` -> ffprobe 60 frames, frames_ok; first
   frame = the live `Seek 2.0` picture of program, last = `Seek 4 - 1/30` (per-RGBA means within 1/255; ramp clip
   gives a grey per frame); transport restored (Play/Seek/Loop/In/Out as before); `tl_rec` gone; realTime back on.
   Watch for: off-by-one frame at the start (arming order of run() vs frame start: fix by moving `arm_frame` logic),
   black/stale clip frames with realTime off (players load async?), project timeline paused = Movie File Out may
   write nothing (offline_render notes it).
10. **Perf**: idle td_perf of TL_timeline unchanged vs phase 2 (the ext adds no per-frame work; tick adds one storage
    fetch); a 200-op edit batch under ~50 ms; 60 fps playing with the window open.

## Not in this prep
Local AI audio tools (onset/beat lane, beat -> markers, BPM autocorrelation), audio track (phase 3), a typed
`td_timeline_build` (the builder runs through td_exec as in phases 1-2).
