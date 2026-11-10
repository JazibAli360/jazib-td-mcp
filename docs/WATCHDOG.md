# Crash watchdog (show use)

TD can't rescue itself (a crash freezes it on a modal Fatal Error dialog; a hang just stops cooking), so:

1. **Heartbeat in the show project:** drag `td/JazibWatchdogHB.tox` into the project root (or run
   `exec(open('<repo>/td/watchdog_hb_install.py').read(), globals())`), then **save the project** (`td_save_project`
   is safe to call onto an existing name since T-37). It writes `~/Library/Application Support/JazibTDMCP/heartbeat.json`
   about once a second (pid, frame, fps, project, build).
2. **Watchdog outside TD:** `python3 tools/td_watchdog.py start --toe <show.toe>` (stdlib only).
   - no TD -> launch the show .toe (never a CrashAutoSave)
   - heartbeat stale > `--stale` from a TD that has beaten before -> kill only when ALSO (T-78/T-95): no MCP sign of
     life within `--stale` (exec.log reply, or `heartbeat_mcp.json`, which handlers.py writes from the WebSocket
     callbacks, so it keeps going when the frame loop stops), AND hang evidence (a crash dialog window: TD's own
     "Fatal Error"/CrashAutoSave alert or a UserNotificationCenter/ReportCrash alert naming TouchDesigner, or process
     state U/Z/T) or everything silent past `--hard-stale` (default 3 x stale). Otherwise warn. Window titles need
     Screen Recording permission for the terminal running the watchdog; without it only state + hard-stale apply.
   - frame heartbeat stale but TD answering = "frames stopped" (T-95): warning; `status` shows `frames_frozen_s`
   - after a relaunch, on the new TD's first heartbeat: `tools/td_recover.py --pid <pid>` once (wait for the bridge,
     td_reload, park lab COMPs except `logs/active_lanes.json`, td_autosave 5 min, td_save_project; writes
     `logs/recovery.log` + a "TD recovered" line, also as event `recovered` in watchdog.log). `--no-recover` turns it off.
   - a TD that never beats (no heartbeat COMP) -> warning notification only, never killed
   - more than 3 restarts in 300 s -> 30 s backoff between launches + notification
   - `pause` before quitting TD on purpose (watch only); `resume` after. `status`, `stop`.
3. Log: `logs/watchdog.log` (JSON lines) and `logs/watchdog.log.out`.

Measured (16 Oct, M1 Max, home project): crash -> relaunch at once -> heartbeat back after ~19 s -> MCP reconnected.
One TD at a time (T-24): with two TDs the watchdog keeps the one that beats and kills the other, **except the scratch
TD** (T-83, `tools/scratch_td.py`): pids recorded in `scratch_td.json` (state dir), or any TD that appears while that file
says "launching" (120 s), are never counted, managed or killed, and a heartbeat whose project is not the `--toe`
project (or sits under `projects/scratch/`) is ignored. Relaunches use `open -n` so a running scratch TD is never
handed the show file. Exec timeouts / disconnects in exec.log no longer count as "TD answered" (the T-78 guard kept
a hung TD alive at 16:20-16:31 on 26 Oct because the lanes' timed-out probes re-armed it).
Not done: auto-start at login (a LaunchAgent) and perform mode on relaunch; ask the user before adding either.

After a relaunch (T-94): the reopened save is at most the pre-risk save made just before the risky call (or the
5-min autosave). For the COMP that was in flight, `td_checkpoint {path, list:true}`: when its newest checkpoint is
newer than the reopened save, `td_restore_checkpoint {path}` and re-run only the builder steps after it.
