# CQ_cuelist — cue list + timecode show control (v1)

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

Spec: `docs/research/BQ_show_control_timecode.md` §3 (clean-room). COMP `/project1/lab/CQ_cuelist`, TD 2025.31550.
Builder `builders/cuelist.py` (`build(parent_path, panel=True, reset_cues=False)`, idempotent, keeps the cue table),
pure logic `builders/cuelist_logic.py` (copied into `cq_logic`), TD runtime in the generated `cq_rt` Text DAT,
offline tests `test/test_cuelist.py`.

```python
ns = dict(globals()); exec(open('<repo>/builders/cuelist.py').read(), ns); ns['build']('/project1/lab')
```

## What v1 does
- **Transport:** `Go`, `Goback`, `Standbyprev/next`, `Gotocue` (name or number; unknown = `Lasterror`, nothing moves),
  `Stop` (freezes fades), `Pause` (holds fades), `Reset`, `Rate` (fade speed, 0 holds), `Queuemode` queue / interrupt
  (new fade starts from the current value) / ignore.
- **Cues** (`cues` table, columns as in the spec): rows with the same `num` fire together; disabled rows skipped;
  `trigger` manual / follow (`delay`, `follow=continue` = after the longest fade) / tc (`at` HH:MM:SS:FF, `12.5s`,
  `1h30`, ...). Kinds: `par` (`op:par`, faded), `zc_set` (knob on `Presetkit`, faded), `zc_recall` (`Recall(pid,
  morph)`), `tl` (`Seek`/`Play`/`Rate`/pulse pars, `Goto` = marker), `osc` / `arena_osc` (dry log unless `Allowosc`;
  Arena also needs `Allowarena` + `Arenasend`), `arena_rest` (dry only), `note`. Bad rows are listed in `Lasterror`,
  never raise.
- **Clock:** `internal` (perf_counter, `Clockplay`, `Locate` + `Dolocate`), `manual` (`Manualtc`), `tc_chop`
  (`Tcchop` or In1: `seconds`/`total_seconds` or `hour,minute,second,frame` at `Tcrate`; `Chase` lock after 5 ticks
  within `Lockwindow` frames, `freewheel` for `Freewheel` s, then `lost`; backward / > `Jumpthreshold` = locate).
- **Timecode triggers** edge-detected once per forward crossing; a jump or rewind **locates**: tracked state at t
  (`resolve_state`) applied without fades, standby = next cue after t.
- **Log:** every event to the CSV (`Logfile`, relative to the project folder, append only) + a ring (`Logmax`); the
  `log` table shows the last 24.
- **Out1** CHOP `cq_time cq_cue cq_fade cq_running cq_standby cq_locked cq_go cq_chase_err`; **Out2** DAT resolved
  state. Controls: zkit panel (Transport/Clock/Cues/Targets/Log), `Opencontrols`.

## Not in v1 (next)
Cue-list panel (rows, standby highlight, big GO), Show mode, `cq_v_<n>` value channels, ltc/mtc/osc/link/timeline
clock sources (TC_timecode hub, spec B), bar/osc triggers, Arena REST sends, one-DAT-per-executor split.

## Live verification (26 Oct 2026, TD 2025.31550, Rosetta; 4 other lanes building at the same time)
- Build: `td_errors` empty, layout ok (0 overlaps, 0 back wires, stage boxes). Offline: 20 tests pass.
- **GO latency:** `Go` par pulse -> first applied value in the same frame (go_frame == apply_frame); GO call 1.0 ms.
- **Fade** 0 -> 1 over 2 s linear: done at 2.017 s after GO (first frame after 2.0), value at 1.0 s = 0.4999,
  no writes after the end. (Fix found here: a fade started mid-frame counts only the time since its start.)
- **Timecode:** 100 tc cues (00:00:01:00 .. 00:00:09:xx, 2-3 frames apart), internal clock: 100 of 100 fired once,
  median 7.6 ms after `at`, p90 30 ms; 7 were 64-476 ms late: 5 from one ~0.5 s TD frame stall
  while other lanes built (all cues crossed in that tick fired once, none skipped), 2 from shorter stalls. Rewind to 0 + locate to the end = the played state
  (all targets equal), standby = after the last due cue.
- **Chase** (TC CHOP = Speed CHOP `seconds`): freewheel 0.16 s after the source stopped, `lost` at 2.16 s
  (Freewheel 2 s), restart (2 s behind = locate) re-locked in 0.13 s; locked error <= 9.4 ms.
- **Cost:** tick 0.12 ms idle (median, p95 0.13; was 0.38 before the per-frame cue-table text compare was replaced by
  the `cues_watch` DAT Execute), 0.43 ms with 2 fades running. Project: 48.6 fps real (median frame 16.6 ms, p95
  31 ms) with 4 other lab COMPs building live; CQ's share is ~0.1 ms.
- Show log CSV: `projects/logs/cq_<yyyymmdd>.csv` (git-ignored), append only.
- Panel capture: `output/project1_lab_CQ_cuelist_controls_zk_out_2026-10-26T11-19-13-863Z.png` (zkit autoUI).
