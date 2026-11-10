# BQ: Show control in TouchDesigner: timecode (LTC / MTC), cue lists, multi-machine sync (research, 26 Oct 2026)

Research only. Nothing was loaded into TD, no `jazib-td` tool was called, nothing installed or run, no sign-in, no bypass. Downloaded into
`research_src/BQ_show_control_timecode/`: one YouTube auto-caption file (`tut154.en.vtt` + `tut154.txt`, text only). The community repos
(62701, 62689, 62526, 66050) were already on disk from the community slice (`research_src/community/files/<id>/`) and were read as text.
Target build: TD 2025.31550, macOS M1 Max, Rosetta (x86_64 Python 3.11). Tags: **[D]** op/par confirmed in our `ops/` dump,
**[V]** read on a doc page or in a file named here, **[S]** secondary/forum, **[U]** unverified, needs a live test.
Clean-room rule holds: we study behaviour, we copy no code (GPL assets are prior art only; licences noted, irrelevant for research).

## 0. Findings in 12 lines
1. TD 31550 already has the whole timecode toolbox as ops **[D]**: `timecodeCHOP`, `ltcinCHOP`, `ltcoutCHOP`, `timerCHOP` (`timecontrol`
   lock/sequential/chop/**timecode**), `timelineCHOP` (`usetimecode`), `abletonlinkCHOP`, `touchinCHOP`/`touchoutCHOP`, `syncoutCHOP`
   (+ Sync In, Pro only), `artnetDAT`, `oscinDAT`, `midiinCHOP`/`midiinDAT`. `ltcin/ltcout` sit in the dump's `skipped_not_created`
   list (audio-device ops), so their pars are **[V] doc only** until a live probe.
2. **There is no MTC reader.** Docs list Start/Stop/Continue + Song Position + timer events for MIDI In CHOP but not quarter-frame
   (F1) messages **[V]**; MIDI In DAT has a `bytes` column (raw bytes) **[V]**, which is the way in. We write the MTC assembler
   ourselves (pure Python, section 4.2). Mac MIDI devices missing on 31550 is T-34 (plug in before TD starts).
3. **No TD op chases the project timeline from LTC/MTC by itself.** Forum thread (Ableton + TD sync, 211409): LTC In worked, nobody
   drove the Timeline COMP; the working pattern is "total seconds channel -> Movie File In index / our own clock" **[S]**.
   So: our cue COMP owns its clock and *follows* timecode (offset + freewheel on loss), it does not write `project.frame`.
4. `timecodeCHOP` (new in 2023.11290) is the arithmetic/format hub: modes locked-to-timeline / index / string / h-m-s-f pars /
   sequential / timecode object / CHOP channels / OP reference; auto drop-frame for fractional rates (29.97 standard, general method
   otherwise); `smpte` flag off allows negative and >24 h **[V]**. Python object `tdu.Timecode`; `.timecode` members on Movie File In,
   Audio File In, LTC In/Out, Timer, Timeline, Sync, DMX In, Clock, MIDI In **[V]**.
5. Multi-machine: three TD-native routes. **Sync Out/In CHOP** (frame-lock within one frame, Pro only, multicast 224.0.0.1, one slow
   client slows everyone, Info CHOP `sync_incompletes`) **[V]**; **Touch Out/In CHOP** (TCP streaming or UDP/multicast messaging,
   queue pars, "Use Synced Ports" single pipe port 10500, no Pro mention) **[V]**; **OSC timecode** to a second instance (Derivative's own
   tutorial 154 video does exactly this) **[V caption]**. Plus Ableton Link for beat phase only.
6. **Arena 7.23 side**: Arena locks a clip's playhead to **SMPTE LTC from a line input** (Preferences > Audio > SMPTE input + frame rate;
   Timeline dropdown on the clip = SMPTE 1/2; offset + frame delay; clips with audio cannot use SMPTE; two inputs) and **does not
   trigger from LTC** (staff, several threads) **[V + S]**. Playing LTC through the speakers into the mic "does not work" **[V]**.
   Triggering = OSC (`/composition/...`, port 7000, `?` queries) or REST (8080) **[V AI]**; MIT Companion module is a map of actions
   (trigger column, next/prev column, connect clip, tempo tap/resync) **[V]**. Every Arena call still needs the user's go-ahead.
7. **Cue-list assets** (ranked, section 1): CuryCue (netzzy, CC BY-NC, QLab-style, Python + SQLite, GO / linked cues / show-mode lock) >
   Sourcerer 62526 (MIT, follow actions + pending queue) > Custom Cuelist Sequencer 73521 (26 KB, per-cue time + fade, 4 drive modes)
   > LTC Timecode Cue List 62701 (GPL-3, named timecode ranges on a Timer CHOP) > Multi-Layer Timeline 62689 (GPL-3, cues = media/tox/
   TCP/custom types) > RegieKI (shared cue list over websockets).
8. **None of them has the full triple we want**: GO / STANDBY(arm) / PANIC-less *operator-decides* transport + timecode chase + cue
   fades through our preset kit + an append-only show log. That is the gap `CQ_cuelist` fills.
9. Our own parts to reuse (no copying of third-party code needed): `TL_timeline` (`Seek`, `Play`, `Rate`, `Loop`, `Inpoint/Outpoint`,
   `markers` Table DAT `time,name`, `tl_out` CHOP with `tl_time`, `Clockmode` realtime/frame, T-64 rule), `ZC_control_surface`
   (`Recall(pid, morphtime)`, `MorphTo(end, morphtime)`, `Store`, presets JSON `{knob: value}`), td_link (Link CHOP, listen-only).
10. LTC/MTC/Link/Art-Net timecode are **inputs we only listen to**; generating LTC (`ltcoutCHOP`) is optional and gated because it is
    audio that must never reach the Mac speakers (user rule) and must not be built on the default output.
11. Most "sync" bugs on Mac will be Local Network permission (Link, multicast), device-before-launch (MIDI, T-34) and Rosetta audio
    latency; all three are measurable and listed as live checks (section 5).
12. Build two COMPs: **`CQ_cuelist`** (main, 7-8 h) and **`TC_timecode`** (input hub, 3-4 h; can be built first or inside CQ as a
    sub-network). Details in sections 3 and 4. Estimated total 11-12 h with 2 builder lanes (logic+tests / network+UI) after a 1-item pilot.

## 1. Landscape (ranked)
Rank = fit to "cue list with GO/fades + timecode + our kit". Mac/31550 status is from files/docs only; nothing was run.

| # | Item | Link | What it is | Licence | Mac / 31550 | Use for us |
|---|---|---|---|---|---|---|
| 1 | **TD built-ins** (Timecode, LTC In/Out, Timer, Timeline, Sync In/Out, Touch In/Out, Link, MIDI In, OSC, Art-Net) | docs.derivative.ca: [Timecode](https://docs.derivative.ca/Timecode), [Timecode CHOP](https://docs.derivative.ca/Timecode_CHOP), [LTC In](https://docs.derivative.ca/LTC_In_CHOP), [LTC Out](https://docs.derivative.ca/LTC_Out_CHOP), [Sync Out](https://docs.derivative.ca/Sync_Out_CHOP), [Touch In](https://docs.derivative.ca/Touch_In_CHOP), [Link](https://docs.derivative.ca/Ableton_Link_CHOP) | native | commercial TD (Sync Out = Pro; this Mac runs Pro per AI) | ops exist **[D]**; LTC/Sync/Touch not instantiated (device/port ops) **[U]** | the foundation |
| 2 | **CuryCue** (netzzy, 42 stars, 79 commits) | [github](https://github.com/netzzy/curycue) | cue list modelled on QLab/lighting consoles: cues store only *changed* params (tracking, rest inherited), Show/Edit/Fixture modes (Ctrl+E), Go button, linked cues (`\|\|` column: next fires when the longest fade ends), DirectOnly (`D`), content presets with active fade, Python + SQLite (schema versioned, `*.before_migrate_*.db` backup), optional Engine Room (heavy preset in an isolated TouchEngine process) | **CC BY-NC 4.0** (`License.md`; non-commercial, attribution) | requirements/Mac not stated in README **[U]**; Python + SQLite so likely fine | best prior art for tracking cues + GO + linked cues; do not port code, copy the *ideas* |
| 3 | **Sourcerer** 62526 (matthewwachter) | [post](https://derivative.ca/community-post/asset/62526), repo on disk | media bin + source switcher: transitions, follow actions (Play Next, Go to Index/Name, "Done On"), **pending queue** state machine (queue vs interrupt), callbacks, preset import/export, safety lock; updated 2026-09-22 for 32280 | MIT | pure Python extension, 496 ops, saved 33070 **[S]**; load test would need a newer build, not 31550 **[U]** | best source for the follow-action + queue semantics |
| 4 | **Custom Cuelist Sequencer** 73521 (GabPelland, 10 Dec 2025, v1.0.0, 26 KB, 412 reads) | [post](https://derivative.ca/community-post/asset/custom-cuelist-sequencer/73521) | "Master Operator" COMP is the preset; each cue = Time + FadeIn + Note; modes: locked to timeline / local timer / frame input / manual index; mirrors outTOP/CHOP/SOP/POP/DAT; Reload pulse | not stated | build not stated **[U]** | confirms the minimal model: cue = (time, fade, note); we go beyond |
| 5 | **LTC Timecode Cue List** 62701 (TimFranklin, 2020, v1.08) | [post](https://derivative.ca/community-post/asset/ltc-timecode-cue-list/62701) | named timecode *ranges* (start, end, loop) played by a Timer CHOP with segments, outputs LTC audio; transport buttons (click = 10 s, ctrl = 1 s, ctrl+shift = 5 s); typing shortcuts (`1h30` = 01:30:00:00, `0100` = 00:00:01:00); save/load cue lists as .py files; "TOD" cue = time of day (warns of drift); 1.07/1.08 efficient readout (cached digits, 3D texture + one GLSL) | GPL-3.0 | tagged Mac icon fix in 1.03 **[V]**; built for 2020 builds | the only free LTC *generator* + cue list; read for UX (time entry shorthand), not code |
| 6 | **Multi-Layer Timeline (TD-MTL)** 62689 (TimFranklin + Brian Alexander) | [post](https://derivative.ca/community-post/asset/62689) | timeline whose cues have *types* (Media, Tox, TCP/IP, custom); the timeline only outputs timing + cue info, examples fire them; 3D canvas + render-picking UI | GPL-3.0 | old; heavy tox set (27 files) | cue-type idea (our cues have a *kind* column) |
| 7 | **UESequencerSync** 66050 (L05) | [repo](https://github.com/L05/UESequencerSync) | Unreal sequencer frame/start/end/fps/name over OSC -> a TD time COMP | MIT | pure OSC receive **[V]** | pattern for "external sequencer drives our clock" |
| 8 | **RegieKI** | [repo](https://github.com/RegieKI/regieki-av) | AV patches; session manager + websocket router; shared cue list for light and sound | LICENSE.md, type not stated | n/a | websocket cue-broadcast idea |
| 9 | Derivative tutorial 154 (Jack DiLaura, [xbUwV8v7XHY](https://www.youtube.com/watch?v=xbUwV8v7XHY), 40 min) | [post 69333](https://derivative.ca/community-post/tutorial/look-new-timecode-tools-touchdesigner/69333) | Timecode CHOP modes; Timer CHOP driving two TD instances' Movie File Ins; OSC timecode to instance 2 ("not necessarily the recommended way", says the narrator); `timeline CHOP usetimecode` to convert to frames/seconds | n/a | Mac: second instance needs a terminal launch **[V caption]** | reference for the OSC sync pattern |
| 10 | Forum: Ableton + TD timeline sync 211409; Unreal Sequencer Sync 252498; timecode.tox 652 | [211409](https://forum.derivative.ca/t/ableton-td-time-line-sync/211409) | LTC via loopback + LTC In worked; tempo changes break LTC; start/end locator method within ~2 frames over 10 000 frames; jitter fixed with ~12 sample lag/offset | n/a | n/a | why a chase needs lag + freewheel |
| 11 | Resolume Arena SMPTE | [manual](https://www.resolume.com/support/en/smpte) | LTC in from a line input; per-clip SMPTE 1/2; offset + delay; no audio-clips; **no triggering** | commercial | forum: playhead drift with long uptime (2023, no fix found) **[S]** | the Arena sync contract |
| 12 | Resolume OSC page / Companion module | [OSC](https://www.resolume.com/support/en/osc), [module](https://github.com/bitfocus/companion-module-resolume-arena) | `/composition/layers/N/clips/M/...`, `?` query, `+ - * a` prefixes, Shortcuts > Edit OSC shows any address; module = REST 8080 + OSC 7000 with 7001 listener; actions column/clip/next/prev/tempo | MIT (module) | page covers 7.18; 7.23 addresses must be learned (AI T7) | cue "kinds" for Arena (dry-run only) |
| 13 | glama `touch-designer-mcp` (lucasmaher-hash) tool pages `sync_timecode`, `manage_cue`, `create_stage_dashboard` | [sync_timecode](https://glama.ai/mcp/servers/lucasmaher-hash/touch-designer-mcp/tools/sync_timecode) | third-party MCP descriptions: MTC via MIDI In -> Null -> Execute DAT writes `project.frame`; "paused TD will not advance"; cue store with morph crossfades quantised to beats/bars; panic button | n/a | tool text only, not run | feature checklist for our MCP tools (we do **not** write `project.frame`) |
| 14 | Art-Net DAT page | `docs.derivative.ca/Artnet_DAT` returned 404; Art-Net's ArtTimeCode packet (opcode 0x9700) is not documented for the TD op **[U]** | - | - | treat Art-Net timecode as a gated idea (receive the raw UDP via `udpinDAT` and parse, section 4.2) |

Not found: any free .tox that decodes **MTC**; any free GO/standby cue stack for TD with timecode chase; any asset that writes the Timeline COMP from LTC.
Searched: derivative.ca tags/timecode (only 62701), forum tag `timeline`, GitHub. YouTube: one tutorial captioned, no 429.

## 2. How it works in TD (what the specs rely on)

### 2.1 Time models
- The **Timeline COMP** counts frames at the project rate (`absTime.frame`); cooking is frame-driven; a paused TD does not advance. We never write
  `project.cookRate` live (T-64) and never use the project timeline as the show clock: each COMP keeps its own clock (TL_timeline rule).
- **Timecode** is HH:MM:SS:FF with a frame rate (24/25/30/29.97 DF/48/50/60). `timecodeCHOP` converts both ways and reports a `Drop Frame` and `FPS`
  channel; `tdu.Timecode` is the Python object **[V]**. We keep *seconds (float)* as the internal unit and convert at the edges, so drop-frame
  is a formatting concern (section 4.2 has the exact maths and its tests).
- **LTC** = SMPTE as a biphase-mark audio signal; LTC In CHOP decodes from an Audio Device In CHOP; pars `inputrate` (24-30), `discrete`
  (frame/second/minute/hour channels), `totalframes`, `totalsec`, `upsample`, `userfields`, `debugchans` (`quantized, bits, ones_count, decode_count`)
  **[V]**. Not documented: sample rate requirements, drop-frame flag handling, latency, Mac behaviour. So `decode_count` rising ~ fps/s and the
  `totalsec` channel are the live health checks.
- **MTC** = 8 quarter-frame MIDI messages (`F1 nn`) per 2 frames + full-frame SysEx at locate. Not exposed as channels by TD **[V absence]**.
- **Link** = beat/phase/tempo for a LAN (`abletonlinkCHOP`, listen-only, Local Network permission, startstopsync) - used for *musical* cues
  (`at bar 17`), not for film timecode.

### 2.2 Cue-list mechanics (QLab/console model, the part every asset reinvents)
- A **cue** = number/name, trigger (manual GO, follow, timecode `at`, bar `at`, OSC), pre-wait, fade time, curve, action(s), note.
- **GO** fires the *standby* cue and advances standby to the next. **Standby** (armed) is the cue the next GO fires; it is editable and
  jumpable (like QLab's playhead). **Follow** cues chain: *auto-follow* (start when previous starts + delay), *auto-continue* after the fade
  (CuryCue's `||` is the latter). **Pending queue** (Sourcerer): a GO during a fade either queues or interrupts - a per-COMP choice.
- **Tracking vs cue-only** (CuryCue `D`): tracking cues store only changed parameters and inherit; cue-only (`DirectOnly`) fire exactly what
  they store. For us a cue stores a *preset id* (ZC preset JSON) or an explicit `target:value` list; tracking = resolve the full state by
  replaying earlier cues (pure function, section 4.3).
- **Fades** are time-based interpolation to the target values with a curve (linear/ease/smooth/cut); ZC `MorphTo(end, morphtime)` already does
  that for knob values. Other targets (TL transport, OSC sends, Arena) use "kinds" with their own executor.
- Operator decides: no safety limits and no warnings in the COMPs (user rule). Show mode is a *lock the operator chooses* (like CuryCue's),
  default off, never blocking.
- **Show log**: append-only CSV (`time_wall, tc, cue, event, detail`) + in-COMP Table DAT ring (last 500). Events: `go, standby, fire, done,
  skip, chase_lock, chase_lost, jump, edit, panic`.

### 2.3 Multi-machine sync in TD (pick by need)
| Need | Use | Notes |
|---|---|---|
| Frame-locked render of one show over N machines | `syncoutCHOP` / Sync In (Pro) | server runs ahead, everyone waits; keep one refresh rate; one bad client slows all |
| Stream channels/values between instances (timecode, cue state) | `touchoutCHOP` -> `touchinCHOP` | TCP streaming or UDP messaging; `Use Synced Ports` (port 10500) keeps channels in the same frame; watch `queue_*` Info channels |
| Loose "same moment" cues over any network | **OSC** timecode + cue id messages (`oscoutDAT` -> `oscinDAT`), a heartbeat at 10 Hz | no Pro, works with Arena/QLab/lighting; the receiver freewheels |
| Beat phase across apps | Ableton Link | tempo/phase only; start/stop only with startstopsync both sides |
| Wall-clock start | agree on a start time-of-day (TOD cue in 62701; "may drift" says its README) | only for loose installs |
Always carry **cue state**, not only time, so a late joiner can resolve the same state (replay-to-time, section 4.3).

### 2.4 Arena 7.23 interplay (planning only, all Arena calls gated)
Cue kinds `arena_osc` and `arena_rest`: build the message, show it in the log, send only when `Arenasend` is on (default off = dry), and refuse addresses not in
`osc_addresses_<build>.json` learned with `td_osc_learn` (AI T7). Arena follows LTC separately through its own SMPTE input (clip timeline dropdown);
TD cannot trigger it, so a chain is: TD cue -> OSC column/clip connect -> clip with SMPTE timeline plays against LTC. LTC must come from a real line
path (second audio interface or a loopback device the user chooses), never the speakers/mic path.

## 3. CLEAN-ROOM BUILD SPEC A: `CQ_cuelist` (the main build)

COMP path `/project1/lab/CQ_cuelist`. Self-contained effect-style COMP: custom pars drive internals, Out ops carry output only, own controls panel and
`controls_window` opened by an `Opencontrols` pulse (same pattern as TL_timeline `OPEN` callback). Pure logic in `builders/cuelist_logic.py` (no `td` import,
copied into the COMP's `cq_logic` Text DAT), builder `builders/cuelist.py` (`build(parent_path)`, idempotent, keeps user table data), tests
`test/test_cuelist.py`, doc `docs/builds/cuelist.md`. Never saves the project (main session autosaves, T-71; the builder writes the .tox via `td_tox_save`
only when the main session asks).

### 3.1 Custom parameters (names: one capital then lowercase)
| Page | Pars |
|---|---|
| `Transport` | `Go` (pulse), `Goback` (pulse), `Standbyprev` / `Standbynext` (pulses), `Gotocue` (str, name or number), `Stop` (pulse: ends running fades, keeps state), `Pause` (toggle), `Resume`, `Reset` (pulse: standby = first cue), `Rate` (float 0..4, default 1: fade-time speed, 0 holds), `Queuemode` (menu queue / interrupt / ignore, default queue) |
| `Clock` | `Clocksrc` (menu internal / timeline / tc_chop / ltc / mtc / osc / link / manual), `Tcrate` (menu 24, 25, 29.97 DF, 30, 50, 60; default 25), `Tcoffset` (str `HH:MM:SS:FF`), `Chase` (toggle), `Chaselag` (float s, default 0), `Freewheel` (float s, default 2: keep running this long after the source stops), `Lockwindow` (float frames, default 3), `Jumpthreshold` (float s, default 1.0: bigger step = locate, not a play), `Linkquantum` (int bars, default 1) |
| `Cues` | `Cuetable` (DAT ref, default internal `cues`), `Tracking` (toggle, default on), `Autofollow` (toggle), `Defaultfade` (float s, default 0), `Defaultcurve` (menu cut / linear / ease / smooth), `Presetkit` (COMP ref -> `ZC_control_surface`), `Timeline` (COMP ref -> `TL_timeline`) |
| `Targets` | `Allowtl` / `Allowzc` / `Allowosc` / `Allowarena` (toggles; the last two default off), `Oscdest` (str host), `Oscport` (int, default 7000), `Arenasend` (toggle, default off = dry run, log only), `Oscmap` (DAT ref to learned addresses) |
| `Log` | `Logfile` (str, default `logs/cq_<yyyymmdd>.csv` relative to project), `Logon` (toggle, default on), `Logmax` (int, ring size 500), `Clearlog` (pulse) |
| `Status` (read-only) | `Standby`, `Running` (name of the live cue), `Fadepct`, `Tc` (string), `Clockstate` (free / locked / freewheel / lost), `Lastevent`, `Lasterror` |
| `Panel` | `Opencontrols` (pulse), `Showmode` (toggle lock for edits, default off), `Compact` (toggle) |
Menu pars are `Menu`, not StrMenu (T-62); `Cuetable`/`Oscmap` as DAT pars. No clamps that stop the operator (no safety limits).

### 3.2 In / Out
- `In1` (In CHOP): optional external clock channels (any of: `seconds`, or `hour,minute,second,frame`, or `beat`); read when `Clocksrc` needs a CHOP.
- `In2` (In DAT): optional message log feed (OSC In DAT rows / MIDI In DAT rows) for `osc` / `mtc` sources.
- `Out1` (Out CHOP, **output only**): `cq_time` (s), `cq_cue` (index), `cq_fade` (0..1), `cq_running`, `cq_standby`, `cq_locked` (0/1), `cq_go` (1-frame pulse on each GO), `cq_chase_err` (s), plus
  `cq_v_<n>` for up to 16 numeric cue values (cue column `out1..out16`), so a look can read cue values as plain CHOP data.
- `Out2` (Out DAT): the resolved *current state* table (`target, value`).
Nothing else goes through the Outs (no controls, no preview).

### 3.3 Cue table `cues` (Table DAT) and state tables
`cues` columns: `id, num, name, trigger, at, pre, fade, curve, kind, target, value, follow, delay, note, enabled, color`
- `trigger`: `manual | follow | tc | bar | osc`; `at`: `HH:MM:SS:FF` (tc), `bar.beat` (bar), osc address (osc).
- `kind`: `zc_recall` (target = preset id, value = morph s) / `zc_set` (target `Knob3`, value) / `tl` (target `Seek|Play|Rate|Goto marker`, value) / `par` (target `op:par`, value) / `osc` (target address, value list) / `arena_osc` / `arena_rest` / `note` (log only) / `group` (rows with same `num` fire together).
- State tables (internal Table DATs): `runtime` (key/value: standby id, running ids, fade t0/t1, clock state), `log` (ring), `resolved` (tracking result), `sources` (what each clock source reports now).

### 3.4 Network, stage by stage (`td_layout mode:"stages"`, stages left to right)
1. **Clock in**: `tc_hub` (a sub-COMP or the `TC_timecode` COMP from spec B, `Clocksrc` selects) -> `clk_null` (CHOP: `seconds, locked, source_ok, jitter`).
   Internal clock = Python in the `tick` Execute DAT (frame start), `time.perf_counter` dt - never the Timeline COMP.
2. **Chase / state machine** (`cq_engine` Script/Text DAT module `cq_logic`): `chase_step()`, `jump_or_play()`, `trigger_due()`; writes `runtime`.
3. **Cue store**: `cues` Table DAT + `cue_parse` (validated dict list; bad rows flagged in `Lasterror`, never raise).
4. **Executors** (one small DAT each, each wrapped in try/except, each honouring its `Allow*` toggle): `ex_zc` (calls `ZC.Recall(pid, morphtime)`/`MorphTo`), `ex_tl` (writes `TL.par.Seek/Play`; jump to marker row), `ex_par` (sets a par; fades float pars via `fade_tick`), `ex_osc` (`oscoutDAT.sendOSC`, dry unless `Arenasend`/`Allowosc`).
5. **Fade runner**: `fade_tick` Execute DAT (frame start) advances all active fades (list in `runtime`); curve lookup in pure logic; `Rate` scales dt.
6. **Out**: `out_chop` Script CHOP -> `Out1`; `out_state` -> `Out2`.
7. **Log**: `logger` DAT: ring append + CSV append every event (open/append/close each write, flush on `panic`/`stop`); `Clearlog` clears the ring only (the CSV is never truncated).
8. **Controls**: autoUI `controls` (Pagescope Transport, Clock, Cues, Targets, Log, Pagetabs off, align verttb) + a **cue-list panel** (container with a list of rows: number, name, trigger, `at`, fade, state colour; standby row highlighted, running row with a fade bar; big **GO** button, **STANDBY** up/down, **BACK**, **STOP**, **PAUSE**, the timecode readout, clock-state dot (free/locked/freewheel/lost), source name). The row painter is one GLSL TOP in compute mode (T-46) or Text TOPs per visible row (max 24 rows, scrolling by wheel); `list_input` Panel Execute handles click = standby, double-click = fire, drag = reorder.
9. `controls_window` Window COMP (1280x720, not full screen), `Opencontrols` pulse opens it.
Role colours, titled stage boxes, left-to-right, `td_layout flow` after build.

### 3.5 Behaviour (the rules the logic encodes)
- **GO**: fires standby cue `S`; standby becomes the next *enabled* cue after `S`; with `Autofollow`, cues with `trigger=follow` start when their predecessor starts (+`delay`) and cues with `follow=continue` start when the predecessor's longest fade ends. GO while fading: `Queuemode` queue -> GO is remembered and fires when the current fade completes (single slot, last wins); interrupt -> new fades start from the *current* values (no jump); ignore -> logged only.
- **Goto / Standbyprev/next**: only move standby (no fire). `Gotocue` accepts name or number; unknown = `Lasterror`, nothing moves.
- **Timecode triggers**: with a locked clock, a `trigger=tc` cue fires once when `clock_time` crosses `at + Tcoffset` going forward (edge-detected with the previous tick time; jumps over `Jumpthreshold` do **not** fire the skipped cues - they *resolve state* instead, see below).
- **Locate (jump)**: backward or > `Jumpthreshold` forward step = locate: pure `resolve_state(cues, t)` computes the tracked state at `t` and `ExecState` applies it without fades, running cues are cancelled, standby = first cue after `t`. This is how late joiners and rewinds land on the right look.
- **Chase**: `Clocksrc` ltc/mtc/tc_chop/osc: `err = source - own_clock`; lock when |err| < `Lockwindow` frames for 5 consecutive ticks; while locked the own clock *slaves* with a one-pole correction (`own += err * 0.5` per tick, clamped so it never runs backward unless the source did); lose lock: `Clockstate = freewheel` and the clock keeps running at the last observed speed for `Freewheel` seconds, then `lost` and it holds (logged `chase_lost`). No automatic stop, no alarm; the operator reads the dot.
- **Fades**: value(t) = a + (b-a) * curve(u), u = elapsed/(fade/Rate). `cut` = u>=0 -> 1. `zc_recall` hands the morph to ZC (single morph at a time there; a second recall retargets from current - ZC's own rule).
- **Panic-less**: `Stop` freezes fades where they are; `Reset` returns standby; there is no auto "blackout". The operator can add a `blackout` preset cue.
- **Show mode** (operator toggle): edits to the table and panel drag are ignored; GO / standby / jump work; every refused edit is logged `edit_refused`.

### 3.6 Pure-logic sketches (`cuelist_logic.py`, unit-testable)
```python
def parse_tc(s, fps, df=False):             # 'HH:MM:SS:FF' or 'HH:MM:SS;FF' or shorthand '1h30', '0100' -> seconds (float)
    ...
def tc_to_frames(h, m, s, f, fps_nom, df):  # nominal fps_nom = 30 for 29.97
    total = (h*3600 + m*60 + s) * fps_nom + f
    if df:                                   # drop 2 frames each minute except every 10th (29.97); 4 at 59.94
        drop = 2 if fps_nom == 30 else 4
        mins = h*60 + m
        total -= drop * (mins - mins // 10)
    return total
def frames_to_tc(n, fps_nom, df):
    if df:
        drop = 2 if fps_nom == 30 else 4
        per10 = fps_nom*600 - drop*9         # 17982 at 29.97
        d, r = divmod(n, per10)
        n += 9*drop*d + (drop*((r - drop) // (fps_nom*60 - drop)) if r > drop else 0)
    f = n % fps_nom; s = (n // fps_nom) % 60; m = (n // (fps_nom*60)) % 60; h = n // (fps_nom*3600)
    return h, m, s, f
def seconds_of_frames(n, fps_nom, df):       # real time: 29.97 => n * 1001 / 30000
    return n * 1001.0 / (fps_nom * 1000.0) if df else n / float(fps_nom)

def crossed(prev_t, t, at, eps=1e-9):        # edge detector for tc triggers; forward play only
    return prev_t < at - eps <= t - eps and (t - prev_t) < JUMP

def resolve_state(cues, t, tracking=True):   # dict target -> value, replay cues with trigger tc/bar and at <= t, in order
    state = {}
    for c in sorted(due_cues(cues, t), key=order_key):
        if tracking or c['direct']: state.update(c['values'])
        else: state = dict(c['values'])
    return state

def curve(u, name):                          # cut/linear/ease/smooth
    u = 0.0 if u < 0 else 1.0 if u > 1 else u
    return {'cut': 1.0 if u > 0 else 0.0, 'linear': u, 'ease': u*u*(3-2*u), 'smooth': u*u*u*(u*(6*u-15)+10)}[name]

class Chase:                                  # lock logic, no td
    def step(self, own, src, src_ok, dt): ...  # returns (own', state, err)
class Engine:                                 # GO/standby/queue state machine
    def go(self, now): ...  def tick(self, now): ...  # returns a list of Actions (kind, target, value, fade, curve)
```
Verify the drop-frame functions against the official tables: 00:01:00;02 is frame 1800 at 29.97 DF; 00:10:00;00 is frame 17982; one hour DF = 107892 frames (3600.0 s * 29.97 = 107892).

### 3.7 Offline tests (`test/test_cuelist.py`, pytest, no TD)
1. `parse_tc` shorthands (`1h30`, `0100`, `100000`, `01h30m`, bad strings -> None), 25/30/29.97 DF; tc <-> frames round trip for every frame in the first 3 h at 29.97 DF (10 800 s * 30 = 324 000 frames: exhaustive); `00:00:59;29 + 1 = 00:01:00;02`; 10th minute does not drop; seconds conversion 107892 frames = 3600.0 s.
2. Engine: GO order, GO at the last cue (no wrap unless `Loop`), standby skip of disabled cues, queue/interrupt/ignore under GO during fade, follow chain timing (delay, continue after longest fade), group rows fire together, `Gotocue` unknown name no-op.
3. Timecode trigger: edge detection once per crossing, none on jump, jump resolves state exactly = replay (property test with random cue tables), rewinds, `Tcoffset`.
4. Fades: curve monotone, endpoints exact, `Rate` 0 holds, interrupt starts from the current value, retarget mid-fade has no jump.
5. Chase: lock after 5 good ticks, freewheel duration, lost, resume re-lock, backward step = locate, jitter of +-1 frame never unlocks, speed estimate.
6. Log: ring cap, CSV append-only (never truncated), event schema, `Clearlog` leaves the CSV.
7. Parsers: cue table with ragged rows, duplicate nums, empty table; all bad rows reported, none raise.
8. Tracking vs direct cue semantics (CuryCue idea) on a 6-cue fixture.

### 3.8 Live verification numbers (after build; the user's go-ahead for the live step; TD session reserved for builders)
- Build: `td_errors` empty; layout check ok; no overlapping boxes (T-69); `td_perf` of the COMP idle < 0.2 ms/cook, firing a GO < 2 ms.
- 10-cue fixture: 4 `zc_recall` (use 3 stored ZC presets), 2 `tl` (Seek to marker, Play), 2 `par` fades (0 -> 1 over 2 s), 1 `osc` to loopback 127.0.0.1 (counted with an OSC In DAT; dry unless `Allowosc`), 1 `note`.
- GO latency: GO pulse to first applied value <= 2 frames (33 ms at 60 fps) measured on `cq_go` vs target par change.
- Fade: a 2 s fade has |t_end - 2.0| < 1 frame; value at 1.0 s = 0.5 +- 0.01 with `linear`; no value written after done.
- Timecode: internal source ("tc_chop") with 100 timed cues: 100 of 100 fire once, each within +1 frame of `at` (log timestamps minus `at` <= 1/60 s + tick), none twice; locate to 00:00:30:00 resolves the same state as having played to it (all targets equal).
- Chase from a TD-made `timecodeCHOP` (sequential mode) through `In1`: lock within 1 s; stop source -> `freewheel` for `Freewheel` s -> `lost`; restart -> re-lock.
- Show log: CSV rows == events; file survives a TD restart (append).
- Panel: `td_screenshot` of `controls_window` for the readability check (24 rows, standby highlight, GO visible from 3 m at 1280x720).
- Idle perf target: panel redraw only on change; 500 log rows no growth in cook time.

### 3.9 Mac / 31550 caveats
- Python `time.perf_counter` ticks at frame rate; with a 60 Hz cook the clock quantises to 16.7 ms - fine for cues, so triggers are edge-detected, not equality-tested.
- Single-pass or compute-mode GLSL only for the panel (T-46); no multi-pass chain.
- CSV write per event is a main-thread file open: fine for < 20 events/s; bulk fades log start/end only (not per tick).
- No `.destroy()` of panels while windows are open (T-70); rebuild closes `controls_window` first.
- Window opens only through the pulse; never full screen.

## 4. CLEAN-ROOM BUILD SPEC B: `TC_timecode` (timecode in/out hub; builder lane 2)

COMP path `/project1/lab/TC_timecode`. One COMP that turns any timecode source into a single clock (`seconds`, `locked`, `source_ok`, `jitter`) and, optionally, generates timecode. It can be used alone (display, log, sync a TL_timeline) or as the `tc_hub` inside CQ.
Pure logic in `builders/timecode_logic.py` (+ tests `test/test_timecode.py`): LTC bit decoder, MTC assembler, OSC time parser, drop-frame maths (shared with `cuelist_logic`, kept in one module and copied), jitter statistics.

### 4.1 Pars
`Source` (menu internal / timecode_chop / ltc / mtc / osc / link / manual), `Tcrate` (24, 25, 29.97 DF, 30, 50, 60), `Offset` (str TC), `Manualtc` (str, for `manual`), `Run` (toggle for `internal`), `Rate` (speed multiplier for internal),
`Ltcdevice` (str: Audio Device In device name or `none`; **default none = never opens an input**; the operator picks a line-in/aggregate device; default input = the mic, so it is not chosen for them), `Ltcchannel` (int 1..N),
`Midiport` (str substring of a MIDI input name, e.g. `IAC`, `Network`), `Oscport` (int, default 9000), `Oscaddr` (str, default `/tc`), `Oscformat` (menu string / seconds / frames / hmsf), `Linksync` (toggle -> `abletonlinkCHOP.enable`), `Linkquantum` (int),
`Outltc` (toggle, default off), `Outltcdevice` (str, default none; **never the default speakers**), `Outmtc` (toggle, default off), `Outmtcport` (str), `Outosc` (toggle), `Oscdest`, `Oscoutport`, `Oscrateout` (Hz, default 10), `Opencontrols` (pulse), read-outs `Tc`, `Locked`, `Jitterms`, `Dropped`, `Lastsource`.

### 4.2 Stages
1. **Sources** (all optional, built inactive): `ltc_in` = `audiodeviceinCHOP` -> `select` (channel) -> `ltcinCHOP` (`inputrate` = Tcrate, `discrete`, `totalsec`, `debugchans`) - **inactive until `Ltcdevice` is set**; `mtc_in` = `midiinDAT` (device by name, `bytes` column on) + `mtc_parse` DAT callbacks assembling quarter frames; `osc_in` = `oscinDAT` (port `Oscport`, address filter `Oscaddr`) + parser; `tc_chop` = reference to an existing `timecodeCHOP` or `timerCHOP` (`timecontrol` = timecode); `link` = `abletonlinkCHOP` (enable off) -> `beats` -> seconds at the stored BPM; `internal` = Python clock; `manual` = string -> seconds.
2. **Select + normalise**: `src_sel` Script CHOP picks the source, converts to seconds (float), applies `Offset`, stamps `source_ok` (a fresh-sample test: last update < 3 frames old, or 0.25 s for LTC/MTC).
3. **Quality**: `jitter` = std of (arrival gaps - expected gap); `dropped` = count of frames missed (LTC `decode_count` stalled, MTC piece out of order); 120-sample ring.
4. **Outputs**: Out CHOP `tc_out` (`seconds, frames, hour, minute, second, frame, locked, source_ok, jitter_ms, dropped, df`); Out DAT `tc_text` one row (`01:02:03:04`, or `;` for DF).
5. **Generators (all off, gated)**: `ltcoutCHOP` -> `audiodeviceoutCHOP` only on the device named in `Outltcdevice`; MTC out: `midioutCHOP`-style quarter-frame messages scheduled each tick (Rosetta timing must be measured before promising); OSC out: `oscoutDAT.sendOSC(Oscaddr, string)` at `Oscrateout` Hz.
6. **Controls**: autoUI + a small readout panel (big timecode, source dot, jitter number, a 10 s sparkline of err); window via `Opencontrols`.

### 4.3 LTC / MTC logic sketches (pure Python, no td)
```python
SYNC = 0b0011111111111101                      # LTC bits 64..79
def ltc_decode_bits(bits):                     # 80 list[int] -> (h, m, s, f, df, user) or None
    word = sum(b << i for i, b in enumerate(bits[64:80]))      # sync word, bit 64 = LSB of the 16 (check: 0x3FFD on read order)
    if word != 0xBFFC and word != SYNC:  return None           # exact bit order is a live/offline-test item (U)
    d = lambda lo, n: sum(bits[lo + i] << i for i in range(n))
    f = d(0, 4) + 10 * d(8, 2); s = d(16, 4) + 10 * d(24, 3)
    m = d(32, 4) + 10 * d(40, 3); h = d(48, 4) + 10 * d(56, 2)
    return h, m, s, f, bool(bits[10]), (d(4, 4), d(12, 4), d(20, 4), d(28, 4), d(36, 4), d(44, 4), d(52, 4), d(60, 4))
def biphase_decode(edge_intervals, nominal_half):   # intervals between zero crossings -> bits: long = 0, two short = 1
    ...
MTC_FIELDS = ('f_lo', 'f_hi', 's_lo', 's_hi', 'm_lo', 'm_hi', 'h_lo', 'h_hi')
class MtcAssembler:                             # feed(data_byte) for each F1 nn
    def feed(self, nn, now):
        piece, val = nn >> 4, nn & 0xF
        if piece != (self.last + 1) % 8 and self.last is not None: self.dropped += 1; self.reset()
        self.p[piece] = val; self.last = piece
        if piece == 7:                          # complete: value is 2 frames old -> add 2
            f = self.p[0] | self.p[1] << 4; s = self.p[2] | self.p[3] << 4
            m = self.p[4] | self.p[5] << 4; h = self.p[6] | (self.p[7] & 1) << 4
            rate = (self.p[7] >> 1) & 3         # 0 = 24, 1 = 25, 2 = 29.97 DF, 3 = 30
            return add_frames(h, m, s, f, 2, rate)
def mtc_full_frame(msg):                        # F0 7F 7F 01 01 hr mn sc fr F7 -> locate (rate in hr bits 5-6)
    ...
```
(LTC: the biphase decoder is the only piece TD already does for us via `ltcinCHOP`; we keep a pure-Python decoder only as the offline *oracle* so tests can encode a frame with a numpy biphase generator and check `ltc_decode_bits`. The 0x3FFD bit order is verified in tests with a generated waveform before any live LTC is wired.)

### 4.4 Offline tests (`test/test_timecode.py`)
LTC: encode 2 h at 25 fps and 29.97 DF into a numpy waveform, add noise/gain/DC offset/polarity flip, decode bits -> TC equals input for every frame; 40% speed and reverse produce the right sign; MTC: assembler for all four rates, +2 frame compensation, dropped piece recovers in 1 frame, full-frame SysEx locate; OSC parser formats (string, seconds, frames, hmsf); jitter stats on synthetic arrival times; `Offset` arithmetic across midnight; drop-frame shared tests with `cuelist_logic`.

### 4.5 Live verification
- Internal -> `tc_out`: `seconds` advances 1.000 s per s +- 0.2% over 60 s; `Rate 2` doubles it.
- `timecodeCHOP` (sequential, 25 fps) as source: locked in 1 s; `jitter_ms` < 1 ms.
- OSC loopback (self-send at 10 Hz): jitter < 5 ms, `source_ok` drops to 0 within 0.5 s after the sender stops.
- MTC: IAC/Network MIDI port with a **disposable** sender (no Live set needed; a test script on the MCP side sends quarter frames 4 per frame at 25 fps): TD sees all 8 pieces, `dropped` 0 over 60 s; macOS MIDI visibility per T-34 (port exists before TD starts).
- LTC: `ltcoutCHOP` -> `audiodeviceoutCHOP` **on an aggregate/loopback device the user names** into `ltcinCHOP`, never the speakers: `decode_count` rate = Tcrate, `totalsec` error < 1 frame over 5 min. User go-ahead and device choice first.
- Link: with a second Link peer only (user-gated) `numpeers` 1, beat phase offset recorded.
- `td_perf` < 0.3 ms idle; `td_errors` empty; layout check ok.

### 4.6 Mac caveats
Audio Device In default = the MacBook mic (do not use for LTC; the mic rule). Aggregate/loopback devices are a user decision (BlackHole is GPL/commercial; not installed). Link and multicast need macOS Local Network permission (AJ T2). Rosetta: audio latency unmeasured; the `Chaselag` par compensates and is calibrated by eye/scope against a visible flash. Sync Out needs Pro and the same refresh rate on all machines; untested on this Mac.

## 5. Integration with `TL_timeline` and the `ZC_control_surface` kit
| Link | How |
|---|---|
| CQ -> TL | `ex_tl` writes `TL.par.Seek`, `Play`, `Rate`; `Goto marker` reads TL's `markers` Table DAT (`time,name`, parsed with `timeline_logic.parse_markers`). **Cues can be generated from markers**: `Importmarkers` pulse creates one `tc`/`tl` cue per marker (name = marker name, `at` = marker time as TC). |
| TL -> CQ | `Clocksrc = timeline`: reads `TL.op('tl_out')['tl_time']` as the clock source (frames step 1/Fps when TL is in `Clockmode frame`, so stepped renders give deterministic cue firing). Never writes `project.frame` / `cookRate` (T-64). |
| CQ -> ZC | `ex_zc` calls `Recall(pid, morphtime)` (existing method), `MorphTo(end, morphtime)` for explicit value sets, `Store()` for a "store current as cue" button (writes a new preset then a cue row pointing at it). Preset JSON stays `{knob: value}` as in `zctl_logic.preset_dumps`. |
| ZC -> CQ | ZC knobs are targets; a cue that sets `Knob7` with a fade uses ZC's `Morph` so a knob the operator touches mid-fade drops out of that fade (ZC rule: touched knob is never fought). |
| Look COMPs | any effect COMP's custom pars are `par` targets (`op:par`); the cue kind `par` resolves the path relative to the CQ COMP or absolute. |
| TC hub | `TC_timecode.tc_out` feeds CQ `In1` (CHOP) or CQ builds its own `tc_hub` copy. |
Shared helper module: `builders/timecode_logic.py` holds the drop-frame maths so CQ and TC use the same tested code (copied into each COMP's Text DAT).

## 6. MCP tool ideas (build-gated, small)
| Tool | What | Gate |
|---|---|---|
| `td_cue` {comp, action: go / goback / standby / goto / stop / reset / list / state} | thin wrapper that pulses the CQ pars and reads `runtime` | none (TD-only); outbound kinds stay `Allow*` off |
| `td_cue_edit` {comp, op: add / update / delete / move / import_markers / import_csv / export_csv} | edits the `cues` table with the logic's validator; returns parse errors; works through `td_dat_text` underneath | refused in `Showmode` unless `force` |
| `td_timecode` {comp, action: status / set_source / set_rate / manual} | builds `TC_timecode` inactive, reads Info numbers, sets source | LTC/MIDI devices need the user's pick |
| `td_show_log` {comp, tail, since} | tail the CSV/ring and summarise | none |
| `td_tc_calc` {from, to, fps, df} | pure offline TC <-> frames <-> seconds converter (no TD) | none |
| `td_cue_dry_run` {comp, from_tc, to_tc} | simulate the cue list over a time range offline (pure logic) and return the event list; no TD call | none |
| `td_ltc_wav` {fps, df, start, minutes, path} | write a test LTC .wav with the pure encoder for offline checks or for Arena's SMPTE test | file output only; does not play it |
Typed tools are added only when the COMPs exist and the same job keeps coming up (EVOLVING.md); `td_exec` covers the rest.

## 7. Gated items for `docs/FUTURE.md`
| Item | Build gate | Status | Needs |
|---|---|---|---|
| LTC In from a real line input into `TC_timecode` | 31550 (device ops) | idea only; build inactive | user picks the audio device (never the mic/speakers default); live probe of `ltcinCHOP` pars (not in the dump: `skipped_not_created`) |
| LTC Out `ltcoutCHOP` + `audiodeviceoutCHOP` | 31550 | gated | user names a non-speaker device (aggregate/loopback); never default out |
| MTC out (quarter-frame sender) | 31550 | idea only | timing test on Rosetta; IAC/Network MIDI port |
| ArtTimeCode (Art-Net opcode 0x9700) receive via `udpinDAT` | 31550 | idea only | doc page 404; verify packet layout against the Art-Net spec before coding |
| Sync Out / Sync In multi-machine frame lock | 31550 Pro | idea only | second machine, same refresh rate; user's go-ahead |
| Touch Out/In timecode + cue-state mirror | 31550 | idea only | second machine or second instance; `Use Synced Ports` test |
| Timeline COMP chased from external timecode (write `project.frame`) | any | **not planned** (T-64 rule); the COMP-owned clock is the design | revisit only if the user asks |
| Arena cue kinds (`arena_osc`, `arena_rest`) live | Arena 7.23.2 | dry-run only | learned `osc_addresses_<build>.json` (td_osc_learn), the user's go-ahead per send session |
| Arena SMPTE clip test (TD LTC out -> Arena SMPTE 1) | Arena 7.23.2 | gated | line path + user go-ahead; Arena clips with audio cannot use SMPTE |
| Link-driven bar/beat cue triggers | 31550 | idea only | AJ T3/T4 Link tests first |
| CuryCue-style tracking edit view (diff vs previous cue) | any | idea | after CQ v1 |
| Engine-room idea: heavy look in isolated TouchEngine process | 31550 | idea only | not planned |
| CQ websocket cue broadcast to other machines (RegieKI idea) | 31550 | idea only | second machine |
| Time-of-day cue (62701 "TOD") | any | idea only | known to drift; use only with a re-sync pulse |

## 8. Builder hand-off
Order: (1) `cuelist_logic.py` + `timecode_logic.py` + tests green (pure Python, ~2 h, parallel lane 1); (2) `TC_timecode` network with internal/timecode_chop/osc/manual sources only, inactive device sources (~2 h, lane 2); (3) `CQ_cuelist` network + executors + log (~3 h); (4) cue-list panel + window (~2 h); (5) live verification 3.8 + 4.5 (~1.5 h, one TD at a time). Pilot first: one cue of each kind with one fade before the table UI. Docs: `docs/builds/cuelist.md`, LEARNINGS rows for every bug, FUTURE rows from section 7, README row. The builder never saves the project (the main session autosaves every 10 min and after verified builds, T-71) but writes the COMP to `td_tox_save` only on request.

## 9. Sources (fetched 26 Oct 2026)
docs.derivative.ca: Timecode, Timecode CHOP, LTC In CHOP, LTC Out CHOP, Sync Out CHOP, Touch In CHOP, Ableton Link CHOP, MIDI In DAT (Art-Net DAT: 404);
derivative.ca posts 62701, 62689, 62526 (on disk), 66050 (on disk), 73521, 69083, 69333, tag timecode; forum.derivative.ca 211409 (Ableton + TD sync);
github.com/netzzy/curycue (README, License.md), github.com/RegieKI/regieki-av, github.com/bitfocus/companion-module-resolume-arena;
resolume.com/support/en/smpte and /osc; Resolume forum threads via search (SMPTE trigger vs sync, drift) [S]; YouTube xbUwV8v7XHY auto-captions (`research_src/BQ_show_control_timecode/tut154.txt`);
glama.ai `touch-designer-mcp` tool pages (third-party descriptions, not run); our notes `AI_td_resolume.md`, `AJ_td_ableton.md`, `BD_rudiment_timeline.md`, `BE_rudiment_zerror.md`, `ops/CHOP.md`, `ops_CHOP_2025.31550.json`, LEARNINGS T-34 / T-46 / T-47 / T-62 / T-64 / T-69 / T-70 / T-71, `docs/builds/timeline_phases.md`, `builders/timeline*.py`, `builders/zctl*.py`.

## 10. Open questions for the user
1. Is there a real line-level LTC source at the venue (DJ/stage rig), or is timecode only an internal/OSC convenience? (decides whether `TC_timecode` LTC is built at all)
2. Which audio device may TD use for LTC in/out (aggregate/loopback), given the Mac-speakers-default rule?
3. Should CQ's `arena_*` kinds ever send for real, or stay log-only until a learned OSC map exists?
4. Is a second machine part of the plan (Sync/Touch/OSC tests), or single-machine only?
