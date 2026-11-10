# R. Making interactive TD visuals show-safe in a Resolume-led show (research agent R, 16 Oct 2026)

Research only, for the lead (Opus). Nothing was started, opened, installed or downloaded. TouchDesigner, Resolume, MIDI devices and
`/jazib_mcp` were not touched. Only read-only local commands were run (`system_profiler`, `pmset -g`, `notifyutil -g`, `file`,
`PlistBuddy`, `ps`); results are tagged **probed locally**. Scratch dir deleted at the end.

**Notation.** **doc** = vendor page fetched (URL given). **forum** = a Derivative forum thread I fetched (username + date given).
**snippet** = only a web-search result summary, the page itself was not readable (Resolume forum returned HTTP 403 to every fetch).
**probed locally** = read-only command on this Mac, 16 Oct 2026. **proposal** = my design, not a sourced fact. **UNVERIFIED** =
memory, inference or a single anecdote. Facts already in `E_live_rig.md`, `H_control_panel.md`, `ops/CHOP.md`, `../WATCHDOG.md` are
referenced as "E §n" etc., not repeated.

**Limits of this research.** The shared web-search budget ran out part-way; the second half used direct fetches of docs and of the
Derivative forum's own search. No Resolume forum thread could be read (403), so Resolume-forum claims are snippets. No reddit access.
No measurement of Syphon latency, Arena source-drop behaviour or thermal behaviour exists anywhere I could find: those stay test items.

---

## 0. Summary

1. **The decisive unknown is still what Arena shows when the TD Syphon sender stops** (E §6). Resolume forum snippets point at two bad
   outcomes: a frozen last frame that needs an Arena restart (capture device, older Arena) and clips turning red OFFLINE until restart
   (NDI, Arena 7.21.3, Apple Silicon). Design for both: a kill that works with TD dead, and a re-trigger step in the recovery runbook.
2. **A frozen frame is worse than black under an Add blend** (it stays on the wall). The current watchdog (stale > 8 s) leaves up to
   ~8 s of frozen TD layer on the wall. Cheap fix (proposal): the watchdog also sends one OSC packet to Arena to drop layer 6 opacity to 0
   the moment the heartbeat goes stale (address pattern is documented, section R5).
3. **One MIDI press should fire two independent kills** (proposal): TD soft kill + Arena hard kill, both from the same MPK pad. Arena can
   read the same device; use Resolume's "Any Device" input so the detection-order swap documented by Resolume cannot break it (R10, R12).
4. **TD on macOS has an active Vulkan-device-error problem** on Apple Silicon in 2025 builds, including this exact build 2025.31550
   (forum, 1 Nov 2025, no fix posted). Staff say fixes are in 2025.32460 and later. Triggers seen: bad GLSL saved, two scenes cooking
   during a scene change, one long GPU job beyond the macOS GPU timeout, POP combinations. Rule: freeze the project, no live edits, no
   MCP `td_exec` during the show, and stress-test every look (R9).
5. **Perform mode cooks only what feeds the outputs.** A cue script that works in edit mode can silently stop in perform mode (forum,
   Xavier). Every test in the checklist must be run in perform mode, started the way the show will start (R6).
6. **Frame budget: crossfades cost the sum of both looks.** From E's numbers a REP4-class look uses ~21 ms of a 33.3 ms frame at
   7488x2880; two of them during a crossfade is ~42 ms, so the crossfade drops frames even though each look alone holds 30 fps (R7).
7. **This Mac is a 16-inch MacBook Pro M1 Max** (`MacBookPro18,2`, probed locally), so Apple's **High Power Mode** exists on it (16-inch
   M1 Max only). Thermal pressure is readable with no root: `notifyutil -g com.apple.system.thermalpressurelevel` (0 now). No sustained
   TD+Arena thermal data exists; a full 6.5 h soak with logging is the only way to know (R8).
8. **Syphon has no frame queue**; TD staff say a shared texture without a queue shows frames twice or skips some, NDI keeps a queue
   (forum, malcolm, 2022; said about Spout, Syphon is grouped with it, so for Syphon this is UNVERIFIED). Expect occasional duplicate or
   skipped frames when TD and Arena run free clocks; test with a moving-bar counter pattern, set Arena's composition frame rate to fixed (R1).
9. **TD cannot be an FFGL in Arena on a Mac** today: the only TD-as-FFGL host found is a community plugin, Windows/Spout only (forum,
   June 2024). The FFGL route on a Mac is our own `JZB_*` plugins for looks that are one shader plus parameters (R1).
10. **Installed-builds fact for the lead:** a native arm64 `TouchDesigner.app` 2025.32820 sits next to the Intel `TouchDesigner 2.app`
    2025.31550 (probed locally). td-port's LEARNINGS records 32820 as Non-Commercial and that the user chose TD 2; the release notes show
    macOS fixes (NDI Out startup crash, silent quit) arrive in 32460/32820. No action proposed, flagged as open question 3.

---

## 1. Findings table

| ID | Topic | Finding | Status | Source |
|---|---|---|---|---|
| R1 | Transport | Syphon is 8-bit RGBA only; no queue between processes, frames can repeat or skip; NDI queues and has a frame-sync that drops/duplicates to re-clock | doc + forum (Syphon part UNVERIFIED) | S11, S19, S51 |
| R1 | Latency | No published Syphon latency figure found anywhere; must be measured | gap | search, see R1 |
| R1 | Colour | TD default working colour space is PASS_THROUGH: values leave "as-is"; Syphon/NDI behaviour not documented | doc | S12 |
| R1 | TD as FFGL | Only a community FFGL host for TouchEngine, Windows + Spout; macOS needs a Metal-sharing port | forum | S42 |
| R1 | Arena frame rate | 7.23.0 fixed "smoother playback when frame rate is fixed in the composition settings" | doc | S48 |
| R2 | Cueing | Arena can emit OSC per control and answers `?` reads, so TD can re-sync from Arena after a relaunch | doc | S44 |
| R2 | Pattern in use | Resolume sends OSC to TD to pick numbered .tox, A/B Engine COMPs so one loads while the other blends | forum | S35 |
| R3 | Lost source | Capture input froze on last frame until restart (old Arena); NDI inputs OFFLINE until restart (7.21.3 Apple Silicon); Max Syphon server restart showed no content | snippets | S50 |
| R3 | Lost source | Arena NDI clip shows red Offline mark at 0x0 when unreachable | doc | S46 |
| R4 | Fallback | Plan B/C as pre-exported MP4 in Resolume saved a TD-based show on day 2 | blog | S59 |
| R4 | In-TD failover | Switch TOP + cook-count watchdog is an in-process pattern; cannot survive TD death | pattern (3rd party tool) | S61 |
| R4 | Camera | Video Device In `connected` = 1 does not mean valid input | doc | S17 |
| R4 | Audio | Audio Device In has "Error if Missing"; reconnect behaviour not documented | doc | S16 |
| R5 | Hang vs dialog | On 2025.33070 (Windows) TD parks its main thread in the fatal-error handler, no dialog in perform mode, process stays alive; a watchdog must kill it | forum | S31 |
| R5 | Hang vs dialog | Mac Vulkan fatal: dialog "TouchDesigner has encountered an error and must close"; autosaves not written on that crash | forum | S26, S30 |
| R5 | Display missing | 2025.30000 added a warning when the perform display does not exist | doc | S10 |
| R6 | Perform mode | Only the Window COMP set as perform window renders; nodes cook only if they feed outputs | doc + forum | S1, S23 |
| R6 | Sleep | Window COMP has "Prevent Display Sleep" (added 2025.30000); playback stops during system sleep | doc | S2, S10 |
| R6 | Frame rate | Display refresh sets TD fps: a 25 Hz display setting gave 25 fps; VSync caused fluctuating fps on macOS (2020) | forum | S37, S38 |
| R6 | Esc | Esc leaves perform mode; "Close on Escape Key" off needs Shift-Esc | doc | S1, S2 |
| R7 | Budget | 30 fps = ~33 ms, 60 fps = ~16 ms; Performance Monitor "Frame Trigger" finds the first frame over budget | doc | S7 |
| R7 | Metrics | Perform CHOP: `droppedframes`, `cook`, `msec`, `gpumemused`, `cpumemused`; `gputemp` is NVIDIA only | doc | S8 |
| R7 | GPU timeout | macOS kills a single GPU job over the OS timeout (Vulkan device error); no setting to raise it | forum | S28 |
| R7 | Contention | Scene change in Resolume dropped frames more when TD was not the focused app; OS favours the focused process | forum | S20 |
| R8 | Thermal | Thermal pressure, not temperature, is the right measure; `notifyutil -g com.apple.system.thermalpressurelevel` needs no root | blog + probed | S56, S57 |
| R8 | High Power Mode | 16-inch M1 Max only; fans run faster; louder | Apple KB via blog | S55 |
| R8 | Restarts | Staff: restart weekly, avoid timers that count forever; 24/7 setups schedule restarts but that can hide leaks | forum | S24, S25 |
| R8 | Degradation | Movie File In cook time rose 0.2 ms to 4 ms after many file swaps; restart fixed | forum | S36 |
| R9 | Vulkan errors | 2025.31550 on M4 Max: recurring Vulkan device errors across projects | forum | S27 |
| R9 | Vulkan errors | Scene changes with two scenes cooking triggered errors in a scenechanger VJ rig (M4, 2025.32050) | forum | S26 |
| R9 | GLSL | Saving erroneous GLSL on macOS can crash TD (M1 Max, 2022.33910) | forum | S29 |
| R9 | POPs | Copy POP to Ray POP reproduces a Vulkan fatal error on MacBooks (Oct 2026, build 2025.33230) | forum | S30 |
| R10 | Controllers | MIDImix: every control has editable CC/note + channel; presets live on the device; MPK Mini: 8 onboard presets, CC mode and Prog-Change mode change what pads send | doc | S52, S53 |
| R10 | Resolume MIDI | Device identity assigned by detection order, "shortcuts will be swapped" if it changes; "Any Device" input exists | doc | S45 |
| R10 | Takeover | Ableton defines None / Pick-Up / Value Scaling | doc | S60 |
| R10 | TD MIDI | MIDI In CHOP restores saved values on load (jump risk); MIDI In DAT logs one row per event with a callback per row; `onDeviceChange` exists | doc | S13, S14, S15 |
| R10 | TD MIDI bug | MIDI In DAT pointing at a missing device cost ~15 fps (Windows 11, fixed in later 2025 build) | forum | S34 |
| R11 | State | Project autosave is not a live-state restore; MIDI In values are saved in the .toe | doc + forum | S13, S26 |
| R12 | Kill | Resolume "Piano" mode = on only while held; Range/Value modes exist for fixed levels | doc | S45 |

---

## 2. Per-item details (practice, source, how to apply here)

### R1. Transport and source type: Syphon vs NDI vs FFGL, latency and colour

**Practice.** Same Mac: Syphon. Frame delivery has no queue, so duplicates and skips can occur; NDI buys a queue and re-clocking at the
price of compression and latency. For the show the question is not "which is faster" but "which failure is visible on a wall".

- **Frame pacing.** TD staff (malcolm, 5 and 7 Nov 2022, S19): "Spout has no queueing between processes", a single shared texture is
  written and read at unpredictable times so frames are "sometimes shown twice and sometimes skipped"; NDI keeps a queue. He also said
  Spout and Syphon behave the same regardless of the application. That thread is about Spout on Windows with OBS and gives no
  measurements; for Syphon on macOS this is **UNVERIFIED**, but it is the only staff statement. NDI's own SDK page (S51) says sender and
  receiver clocks are "extremely unlikely to share the exact same clock rate" and its frame-sync drops or duplicates frames to re-clock,
  so NDI is not jitter-free either.
- **Latency.** I found no measured Syphon latency (searched; only vendor wording, already quoted in E §2). Method (proposal): TD draws a
  moving bar plus a binary frame counter; Arena shows the Syphon clip in the composition; film the TD control display and the Arena
  output monitor together with a phone at 240 fps (or record both) and read the counter difference in frames. Same rig also counts
  duplicated or skipped counter values (the pacing question above). Arena's own Syphon output "Composition" (S47) could be read back by
  the PF26 viewer bridge for a numeric version (needs the user's go-ahead: Syphon/Arena operation).
- **Rates.** Set TD `project.cookRate = 30` (E §4.2) and make the Window COMP V-Sync Mode "FPS is Half Monitor Rate" so a 60 Hz control
  display paces a 30 fps cook (S2: "Half-rate modes suit running a 30fps file on a 60Hz display"). Set Arena's composition frame rate to a
  fixed value: Arena 7.23.0 fixed "smoother video playback when frame rate is fixed in the composition settings" (#22712, S48). A Resolume
  moderator snippet says the composition rate is a maximum that can dip under load (S50, p=72152 snippet).
- **Colour.** TD 2025 default is PASS_THROUGH: colours are "output to displays and files as-is" (S12). Syphon is 8-bit RGBA (S11).
  Nothing documents any conversion in the Syphon path, so TD and Arena most likely exchange raw values (UNVERIFIED). Test with a chart:
  grey ramp plus the PRISM brand colours (`prism-brand/brand.json`) sent through TD to Arena, compare numeric values at Arena's
  Composition output; check alpha edges for premultiplied halos (project memory: Resolume clips with alpha go out premultiplied).
- **TD as FFGL.** Community plugin FFGLTouchEngine (djevo1, forum 21 and 27 Jun 2024, S42) loads .tox in Resolume, but uses Spout, so
  Windows only; the author said macOS would need platform macros and Metal texture sharing. Not usable here. UNVERIFIED whether a Mac port
  appeared after June 2024. What does work on this Mac is Arena-native FFGL: the StageLab `JZB_*` plugins run inside Arena with no IPC
  and no second process to crash (a Resolume forum snippet confirms an FFGL plugin on a clip, layer or composition receives that level's
  texture, S50). Trade-off (inference): a faulty FFGL crashes Arena itself, a faulty TD does not.

**Apply here.** (1) Keep Syphon on one Mac as in E §4. (2) Add the frame-counter, latency and colour-chart patterns to E §7.2 step 4/5.
(3) Any TD look that is just a single GLSL shader plus parameters is a candidate for a `JZB_*` FFGL port, which removes it from the
TD-crash risk entirely; bake the rest. (4) Keep NDI as the documented fallback only.

### R2. Cueing interactive effects inside a Resolume-led show

**Practice.** Decide who owns the cue. Documented building blocks exist for "Arena leads, TD follows":
- Arena OSC input is off by default, enabled in Preferences > OSC, default port 7000; addresses such as
  `/composition/layers/1/video/opacity` (float); clip-playhead address `/composition/layers/2/clips/8/transport/position` (S44).
- Arena OSC **output**: enable per control (right-click), wildcards for "All Layers/Clips"; the "Output All OSC Messages" preset floods
  quickly; `?` sent to an address makes Arena reply with the current value; the Preferences fold-out shows the last 200 messages (S44).
  Clip-connect and layer-bypass addresses are not given on that page: learn them from Shortcuts > Edit OSC (UNVERIFIED addresses).
- In use by others: "Resolume sends OSC to TouchDesigner to switch files", numbered .tox 1 to 40, two Engine COMPs as an A/B deck so one
  blends while the other loads (Chemtrails, forum 4 Mar 2024, S35). That thread also records a TouchEngine GPU resource leak fixed in
  2023.11600, so "switch many times in a set" is a known stress pattern.

**Apply here (proposal).** E §5 puts the controls in TD. A hybrid that keeps this: Arena owns the **show state** (SHOW-deck columns,
BASE loops, SAFETY deck, layer-6 on/off), TD owns **fine parameters**. Each interactive look is a layer-6 placeholder clip; connecting
it sends OSC that selects the TD slot. After any TD relaunch TD reads the current layer-6 clip from Arena with `?` and lands in the right
look, so Arena and TD cannot disagree on "which look". Needs the user's decision (open question 1) and an Arena OSC test (go-ahead).

### R3. What happens when the source disappears; designing for both outcomes

**Practice / evidence.** Arena 7.23.2 behaviour is untested (E §6). Evidence is all indirect:
- Resolume forum snippet: a capture device turned off or swapped left Arena on the last frame, reconnect from the thumbnail did not
  help, only restarting Arena did (p=37005; older Arena; the thread returned 403) (S50).
- Resolume forum snippet: Arena 7.21.3 on macOS Sonoma, Apple Silicon: NDI inputs randomly OFFLINE mid-show, restart sometimes enough,
  sometimes a reboot; NDI Monitor still saw the signal; staff reply only suggested removing virtual devices and VLANs (p=99053) (S50).
- Resolume doc (S46): NDI clips show a red Offline mark at 0x0 when sender and receiver are on different IP ranges (a network case).
- Cycling '74 snippet: a restarted Max Syphon patch was seen by the client but showed nothing (S50). Resolume forum snippet: a Syphon
  source with empty alpha looks invisible (S50).
- TD side: build 2025.33230 notes "Fixed extra `_1` sender name being registered" for the Syphon Spout Out TOP (S10). On 2025.31550 a
  relaunch might therefore publish `PF26-TD_1` while a stale `PF26-TD` clip exists in Arena (UNVERIFIED how that bug appears).

**Apply here.** The source-drop matrix of E §7.2 step 5 stays the first Arena test. Add: (a) after each TD relaunch read the sender
name in Arena's Sources tab and compare with the clip's source; (b) record whether the clip recovers without re-triggering; (c) record
whether the wall shows last frame, black or offline art under the real blend (Add); (d) the recovery runbook (section 5) always includes
"re-trigger the layer-6 clip" until the test proves it is unnecessary.

### R4. Fallbacks when TD, camera or audio fails

Tiers (proposal, extends E §6 and §7.1):
1. **T0** TD live on layer 6.
2. **T1** TD degraded: cheap look or half-resolution (E §4.2), set from the panel or automatically (R7).
3. **T2** layer 6 hidden by Arena, BASE DXV loop runs (MOU: "reactive loss -> base loop keeps running", E §4.3).
4. **T3 baked backup of each interactive look.** Record each look from TD during rehearsal (Movie File Out) as DXV masters in the normal
   PF26 pipeline and place them in the same SHOW-deck column on a BAKED layer. The operator swaps live for baked with one press. Source
   for the idea: Olivia Ema, Notting Hill Carnival (2 Sep 2024, S59): "Always have a Plan B and C"; MP4 exports of her TD work loaded into
   Resolume carried day 2 after day 1 failed because her TD canvas did not match the production team's Resolume setup. Needs the
   user's rule check: PF26 clips obey the 75% / DXV3 / viewer-verdict pipeline (`production/SYSTEM.md`).
5. **T4** backup Mac at FOH (E §6).

In-TD failover (Switch TOP between live and a fallback file, tripped when the primary's cook count stalls, auto-return after a healthy
period; one community MCP tool implements it, S61) only catches a look that stalls inside a living TD. It cannot help when the process
dies or hangs, which is the Arena-side tiers' job. Low priority.

**Sensors fail soft (proposal).** Every reactive input feeds a `confidence` 0..1 that crossfades the reactive term toward an autonomous
slow motion over 1 to 2 s, so no look goes dark or freezes because a sensor vanished.
- Camera: Video Device In exposes `connected` (0/1) and `connection_changes`, but "connected" "does not necessarily mean there is valid
  input" (S17). Add a staleness check (frame difference or a counter that stops changing) and treat "connected but stale" as lost. Stored
  5 s clip fallback is already the td-port rule (project memory).
- Audio: Audio Device In has "Error if Missing" and its page documents no reconnect (S16). Silence between songs is normal, so a silent
  input cannot be told from a dead one; the reactive term must therefore be able to idle gracefully on either, and device presence is
  checked separately. Buffer Length trades latency for stability (S16).
- MIDI: see R10.

### R5. Watchdog extensions (beyond `../WATCHDOG.md`)

Evidence that the existing design matches reality:
- Windows 2025.33070: TD "stops cooking permanently", main thread parked in the fatal-error handler, **no dialog in perform mode, no
  event log entry, process stays alive**; "a watchdog must kill it" (Titus Riemersma, forum; staff varad asked for a spindump and an
  upgrade to 2025.33230) (S31).
- Mac: Vulkan fatal appears as a notification "The Vulkan Device has returned a fatal error code ... TouchDesigner has encountered an error
  and must close"; autosaves are not written on that crash (Luca_Scl, 28 Jan 2026, build 2025.32280) (S26, S30).
- Operators in the wild do the same: kill a hung TD and let a watchdog relaunch (forum listing "FIXED: TD hanging at 100%", excerpt only,
  S32); boot script + process manager + "Start in Perform Mode" for installations (harveymoon, 11 Mar 2019, S33).

Proposals:
1. **Watchdog hides the TD layer in Arena on stale heartbeat** (OSC to Arena, `/composition/layers/<N>/video/opacity 0`, documented
   in S44; stdlib UDP, a few lines) and restores it only on the operator's REJOIN. This turns the 8 s frozen-frame window into the time
   it takes the stale check to fire. Needs the user's go-ahead (Arena operation) and Arena's OSC test.
2. **Tune the stale threshold only with data.** Lower than 8 s risks false kills during heavy hitches; the 2 h soak should log the
   longest heartbeat gap (UNVERIFIED how the heartbeat COMP is driven; check it is not blocked by a heavy cook).
3. **Relaunch into perform mode** (listed as "not done" in WATCHDOG.md): Window Placement Dialog "Start in Perform Mode" (S3) or
   `project.performOnStart` (S4: defined only as "perform on start state"). Needs the user's go-ahead. Rehearse relaunch with the control
   display unplugged: 2025.30000 added a warning when the perform display is missing (S10); older builds crashed in that case (forum
   listing "Crash on startup in perform mode when ... perform window does not exist", S43).
4. **Crash loop policy:** WATCHDOG backs off after 3 restarts in 300 s. Add: after the backoff the TD layer stays hidden in Arena and the
   notification says so, rather than a flapping layer coming back every 30 s.
5. **State survives a crash only if written outside TD** (R11): autosave is not a restore.
6. **Cold start is slow:** 19 s to heartbeat measured (WATCHDOG.md), plus shader compile on first cook (E §6, UNVERIFIED). Pre-warm every look once at startup (cook each slot with the output blanked) so the first live use does not hitch; measure the hitch with Perform CHOP `droppedframes` (S8).

### R6. Perform mode as a show mode

**Practice.**
- Perform mode renders only the Window COMP set as perform window (S1). Start flag: Window Placement Dialog "Start in Perform Mode"
  and "Main Perform" column (S3). F1 enters, Esc leaves if the cursor is over the window, Shift-Esc always (S1, S2).
- **Test in perform mode.** Wieger (forum, premiere-this-Friday thread, S23): a foot-pedal cue counter worked in edit mode, in perform mode
  the cue froze playback. Pixelux's explanation: TD cooks a node only when needed; edit mode has many open viewers that force cooks;
  perform mode cooks only what feeds the outputs. Fix: Null CHOP with cook type Always after the cue logic. TD's Cook page (S5): `*Out`
  operators cook every frame (so the Syphon/NDI Out is safe, by name; UNVERIFIED for Syphon Spout Out specifically), Render TOP and
  `*In` operators cook whenever asked. **Everything else the show depends on (state writer, flash limiter, MIDI-to-par logic,
  heartbeat) must feed an output or be forced.**
- Window COMP pars to set (S2): Borders off, Always on Top, Cursor Visible = Never (on the output window), Close on Escape Key off,
  V-Sync Mode (see R1), Draw Window off if the window only paces a Syphon-only output (the page says it stops drawing; effect on pacing
  UNVERIFIED), **Prevent Display Sleep** (`blocksleep`, new in 2025.30000, S10).
- **Refresh rate sets fps.** Forum (S38): M1 MacBook Pro 2021 on Ventura, TD ran 25 fps because an external display's HiDPI mode offered
  only 25 Hz; switching to a 60 Hz mode restored 60. Forum (S37): on macOS Catalina 2020 fluctuating fps was fixed by turning VSync off.
  Check the control display's actual refresh and test V-Sync modes with the real network.
- **Focus.** malcolm (S20): when resources are tight "the OS divides constrained resources among processes"; the unfocused app drops
  more. Windows+NVIDIA reports also exist of TD freezing when its window overlaps Arena's (S21, S22, VRR / driver related, staff: "window
  update failure ... likely a driver bug"): not a Mac report, but keep TD's panel and Arena's output windows on separate displays and
  not overlapping. Test Arena's output fps with TD focused and with Arena focused (td-port saw TD at ~28 fps in the background,
  E §6).
- **Dialogs.** A Mac Pro M3 build 2023.11760 arm64 restarted the whole system when the Window Placement Dialog's perform tab was opened
  then the designer tab clicked (HadisFard, 8 Jul 2024, S41; no fix posted). Configure placement once, save, then never open that dialog
  on the show Mac.
- **Sleep.** TD keeps cooking during background macOS wakes; the lid-closed case was unresolved (S39). Keep the lid open (E §6).

### R7. Frame-drop budgeting

**Practice (docs).**
- Budget: 30 fps is ~33 ms/frame, 60 fps ~16 ms (S7). Performance Monitor: set **Frame Trigger (ms)** to the budget, Analyze reports the
  first frame over it, sort by Adjusted Length; CPU contention can give misleading cook times (S7).
- Perform CHOP channels: `fps`, `msec`, `cook` (0 = skipped), `droppedframes`, `cookrate`, `gpumemused`, `totalgpumem`, `cpumemused`;
  `gputemp` works only on NVIDIA, so no GPU temperature here (S8). Log them to a Trail/Record CHOP for the soak (S6 suggests Perform CHOP
  into Trail).
- Bottleneck test: drop the render resolution to 64x64; if it speeds up it is the GPU (S6). Hog CHOP burns CPU to simulate a slower
  machine (S9; CPU only, so it does not model Arena's GPU share).
- `project.realTime` True means frames may be skipped to hold cookRate; False processes all frames (S4). Show mode wants True.

**Numbers from E reused.** REP4-class look at 7488x2880: 47.3 fps at 60 Hz means ~21 ms of GPU per frame, 63 % of a 33.3 ms frame.
REP8: 40.5 ms (over budget alone). ~1.9 ms per Mpx for the heavy look (E §1).

**Proposals.**
1. **Budget rule (rule of thumb, UNVERIFIED as a standard, my number):** measure each look *while Arena plays the 7488x2880 base*; a look
   alone must use at most ~60 % of the frame budget (20 ms at 30 fps), p95 not average; keep the margin for Arena's share, the panel and
   thermal drift. Log the real figure per look in a table next to the look list.
2. **Crossfades add.** Both looks cook during a crossfade (H §3.2). 2 x 21 ms = ~42 ms > 33.3 ms (derived arithmetic, assumes additive
   GPU time and no Arena load). Options: hard cut with a one-frame dip; crossfade only a heavy look with a light one; shorten the
   overlap; render both at half-res during the fade then switch back. Forum evidence that scene transitions are where Mac rigs break:
   charlieihle (6 Feb 2026, M4 Pro, 2025.32050, scenechanger VJ rig): Vulkan errors "during scene transitions, when two scenes may be
   cooking at once" (S26). And Resolume side: frames dropped on scene switching when TD was unfocused (S20).
3. **One long GPU job kills the device.** malcolm (25 May 2026, S28): a Blur TOP on a 5906x4169 image with big filter settings crashed
   with a Vulkan error because the job exceeded "the gpu-timeout limit of the OS", with no macOS equivalent of the Windows timeout
   setting. The macOS timeout value is not documented (UNVERIFIED). At wall size avoid single heavy passes (large blur, deep ray/loop
   shaders): split into tiles or run at half-res. Test each look at 7488x2880 for Vulkan errors, not just fps.
4. **Adaptive resolution governor (proposal):** watch `msec`/`droppedframes` (S8); if the 1 s median exceeds the budget step the look's
   internal resolution down one level (1.0, 0.75, 0.5) with hysteresis, then upscale to the constant Syphon size so Arena never sees a
   size change. Use per-look Resolution TOPs driven by a parameter: the *Global Resolution Multiplier* is an application preference
   (Edit > Preferences > TOPs, `ops/TOP.md`), not a project setting, so it cannot be used for this and it can silently halve a wall
   render if left on another value: check it on the show Mac and on the backup.
5. **Memory:** 86.3 MB per 8-bit wall TOP, Render TOP alone ~785 MB (E §1). Movie File In cook time grew 0.2 ms to 4 ms after many
   file swaps on a long run (REM_Visuals, June 2025, S36): load media once, avoid per-cue file swapping.

### R8. GPU, power and thermal over 6.5 hours on a laptop

**Facts.**
- This Mac: `MacBookPro18,2`, Apple M1 Max, 10 cores, 64 GB, macOS 27.0 build 26A428 (probed locally). That identifier is the
  16-inch 2021 M1 Max (my knowledge, UNVERIFIED against Apple's list). Current `pmset -g`: `powermode 0`, `sleep 0` (held by caffeinate
  processes and this tool), `displaysleep 60`, `powernap 1`, `hibernatemode 3`, `womp 1`. Thermal pressure level now 0 (probed locally).
- High Power Mode (Apple KB quoted by 512pixels, S55): "allows the fans to run at higher speeds", "additional cooling capacity may
  allow the system to deliver higher performance in very intensive workloads", louder fans, usable on or off power; **exclusive to the
  16-inch M1 Max** (not 14-inch, not 16-inch M1 Pro). Where it is set under macOS 27 is UNVERIFIED (earlier macOS: System Settings >
  Battery > Energy Mode).
- What to measure: temperature is a poor guide, thermal pressure is the indicator chip vendors recommend (Eclectic Light, S56).
  `notifyutil -g com.apple.system.thermalpressurelevel`: 0 nominal, 1 moderate, 2 heavy, 3 trapping, 4 sleeping (blog, from
  `OSThermalNotification.h`; the author never reached 3/4; S57); `sudo powermetrics -s thermal` needs root; `ProcessInfo.thermalState`
  has only four coarse levels and stayed at "fair" while powermetrics went moderate/heavy (S57). Throttling looked like CPU at 100 % with
  watts falling (S57). `pmset -g thermlog` returned nothing useful for that author (S57); `pmset -g therm` here says no warning recorded.
- Forum: laptops throttle and desktops are suggested for week-long runs (S43 listing "GPU cards and VRAM"); a Windows laptop paused its
  TD timeline when too hot to touch (S40); staff suspected thermal throttling in a slow-down-over-time report (S36).
- Sleep tools (ss64, S58): `caffeinate -d` display, `-i` idle, `-m` disk, `-s` system (AC only), `-u` user activity, `-t` timeout, `-w`
  PID; `pmset -a sleep 0|displaysleep 0|disksleep 0|powernap 0`. Changing these is a system setting: user's go-ahead.
- App Nap: Apple's behaviour is hidden-app throttling; I found no TD-specific App Nap report and E's `defaults write ... NSAppSleepDisabled`
  remains UNVERIFIED. TD's own Prevent Display Sleep and an unobscured perform window are the documented levers.
- Restarts: Derivative staff `ben` (13 Oct 2023, S24): restart "at least weekly", avoid timers that count indefinitely, test before
  committing. JetXS (15 Jun 2022, S25): 24/7 productions often schedule a restart (PM2 etc.) but that "might hide the leak".

**Apply here (proposal).**
1. Show Mac on AC with the original adapter, lid open on a stand with free airflow, High Power Mode on (if it is the 16-inch), no other
   apps; run TD and Arena fresh at ~4:30 PM, not mid-show (fresh start is the only restart that fits a 6.5 h show).
2. **Logger for every soak (local, free):** every 10 s append `date, thermalpressurelevel` (notifyutil), TD Perform CHOP row (fps, msec,
   droppedframes, gpumemused, cpumemused), `ps` RSS of TD and Arena. iStat Menus is installed (E §6) for fan and power watching.
3. **Full 6.5 h dress soak** at least once (Fri 23 Oct) with the real looks cycling on a timer, Arena playing the 7488x2880 base and the
   9-slice output, controls untouched; plus a 15 min "hot moment" test with the heaviest look + crossfades. E's 2 h soak is the minimum.
4. Venue ambient and stage heat are the unknown: log thermal pressure at soundcheck.
5. Pass criteria (proposal): thermal pressure never above 1 for more than a few minutes; zero Vulkan errors; `droppedframes` per look
   under an agreed count; RSS growth flat over hours.

### R9. TD 2025.31550 on macOS: instability inventory and rules

Forum evidence (all fetched):
- **This build**: "Vulkan device error MacOS 15.6.1, Commercial build 2025.31550", M4 Max, regular errors across projects (overthoughtarts,
  1 Nov 2025; staff Guillaume.L asked for crash files; no fix posted) (S27).
- **Recurring Vulkan Device Error & Crashing** (Feb 2025 to Aug 2026, many posters, M2 Max to M5 Max, S26): errors about hourly on an M4;
  dialog says errors are logged in Console but are not; autosaves not written on crash; staff ben (31 Mar 2026) asked M4 Pro/Max users
  to test macOS 26.4 and build 2025.32460, "numerous fixes"; charlieihle: no crash since updating (14 May 2026), unconfirmed fix.
- **Saving broken GLSL** can crash with a Vulkan error: "Vulkan is much more sensible to errors and can lead to driver crashes, bringing
  down TouchDesigner" (JetXS, 5 Sep 2023, M1 Max 64 GB, S29).
- **Heavy GPU work**: Blur TOP over the OS GPU timeout (S28); Copy POP into Ray POP gives a fatal error on MacBooks (Oct 2026, S30).
- Release notes after 31550: 32460 "Fixed issue which caused TouchDesigner to silently quit on macOS sometimes" (Touch Out CHOP);
  32820 "Attempt to fix crash that can occur when starting up an NDI Out TOP on macOS"; 33230 Syphon Spout Out sender-name fix (S10).

Rules (proposal): (1) show project frozen, `td_save_project` only at known-good points; (2) **MCP bridge idle during the show**: no
`td_exec`, no GLSL or network edits (a bad GLSL save is a documented crash path); (3) every look stress-tested at 7488x2880 for Vulkan
errors, with transitions; (4) avoid POP combinations reported to fail on Macs unless tested (Ray POP, large Copy POP chains); (5) keep
a known-good .toe copy plus the baked tier (R4); (6) put the Vulkan-crash count into the soak pass criteria; (7) log every crash
report path (`~/Library/Logs/DiagnosticReports/TouchDesigner-*.ips`, E "Bugs hit") and add a LEARNINGS entry per bug (project rule).

### R10. MIDI for a one-person operator

**What is documented.**
- **Controller internals.** MIDImix: each control's CC/note number and channel is editable; buttons can send CC or note; presets are
  files on the computer or stored on the unit, and "Sending a Preset will overwrite that Preset number on your MIDImix" (S52). Send All is
  not covered by Akai's editor article. MPK Mini MK3: 8 onboard presets (Prog Select + pad 1..8), CC mode and Prog Change mode change what
  pads send, Full Level, joystick modes, bus-powered, class-compliant, "some users report success with a powered USB hub" (S53). Pad note
  defaults per bank were not found in any fetched source (E bug 8 same).
- **TD side.** MIDI In CHOP restores last values from the .toe, so controls "may be in a different position" and values jump when moved
  (S13). MIDI In DAT logs one row per MIDI event and runs its Callbacks DAT "once for each row added", default 100 lines (S14). Execute
  DAT `onDeviceChange()` runs "each time devices are connected or disconnected, such as MIDI devices, cameras, or joysticks" (S15).
  2025.33070 added capture of MIDI events faster than the timeline rate to the MIDI In CHOP (S10), which implies 2025.31550's CHOP samples
  at the timeline rate (inference). A MIDI In DAT pointing at a missing device cost ~15 fps (Windows 11, 2025 builds, fixed in a later
  2025 build) (S34).
- **Resolume side.** Shortcut modes Toggle / Piano (on while held) / Range / Value; CC modes Absolute / Button / Relative / Fake Relative;
  targets By Position / This Clip,Layer / Selected; Input and Output (LED feedback) configured per device; **device identity is assigned by
  detection order, "the shortcuts will be swapped" if it changes**; "Any Device" input treats all devices as equal (S45).
- **Takeover (Ableton manual, S60):** None = value applies at once; Pick-Up = "no effect until it reaches the value of its destination
  parameter"; Value Scaling = "smooth value transitions".

**Apply here (proposal).**
1. **One owner per control.** TD owns both controllers (E §5). Arena gets no shortcuts from these two devices except the one dual-fire
   kill (R12), set to "Any Device" on a note number that exists only on one pad.
2. **Triggers through MIDI In DAT callbacks, levels through the CHOP.** A pad tap shorter than a 33 ms frame can be missed by a CHOP
   sampled at the timeline rate on this build (inference, test it: tap-test with the shortest tap and count); the DAT records every event.
3. **Takeover:** Pick-Up on the master dimmer and any fader (a surprise jump on the master is a safety event); Value Scaling on per-look
   knobs so that changing look does not leave dead zones. H §3.7 has the TD mechanism.
4. **Layout for one pair of hands (design opinion):** bank 0 "always": master fader, KILL, SAFE/HOLD, look select, REJOIN; bank per look:
   8 knobs max, labels mirrored on the panel; fine parameters on screen only; no shift layers beyond one. Print a paper overlay for each.
5. **Controller self-check panel:** the Table DAT map from the learn step (E §7.2 step 3) plus a lamp per control that turns green once
   seen after power-up; an "unexpected message type" lamp catches an MPK left in CC/Prog-Change mode or on a different preset.
   Lock the MPK preset and MIDImix preset, record both with the editors, store the files in the project, and re-check after any power cycle.
6. **Hot-plug rehearsal:** unplug and replug each controller and the hub with the show running; use `onDeviceChange` to re-resolve the
   device and re-arm pickup; also launch with the controllers unplugged (no MIDI In DAT left pointing at an absent device).
7. **Power and cable:** both controllers on one powered hub with strain relief, hub on the same UPS or clean outlet (E §7.1).

### R11. Preset and state recall

Build on H §3.4 to §3.6 and add the crash-safety side:
- TD does not restore live state after a crash (autosaves not written on Vulkan fatal, S26/S30), and MIDI In values saved in the .toe
  can disagree with the physical faders (S13).
- Proposal: a small writer (Execute DAT, debounced to ~1 s after any change) writes `state.json` (look id, per-look parameter values,
  master, flags, schema version, timestamp) with write-to-temp-then-rename so a crash mid-write cannot corrupt it; keep the last 3
  versions. On start: load, **come up dark** (master 0, TD layer hidden by Arena), arm Pick-Up on all controls, show "READY" with the
  restored look, and only fade in on the operator's REJOIN. This avoids a relaunched TD blasting a stale loud state onto the wall.
- Presets: snapshot in the same schema by look ("A", "B", "last good"); recall always goes through the existing smoothing (H §3.4) and
  respects the flash limiter (H §3.6).
- Pre-warm A/B slots as in the Chemtrails Engine COMP deck (S35): the incoming look is already cooked (and compiled) before the fade.
- State in a Table DAT file on disk is also what E §6 recommends (TD autosave is not a restore of live state).

### R12. Interaction kill switches

Tiers (proposal), each independent of the one before it:
1. **Soft (TD):** `Interact` gate forces every reactive/camera/audio term to neutral through a 0.5 to 2 s ramp, stops emitters, holds
   the look. Back out with the same button.
2. **Dim (TD):** master to 0 with a ramp (H §3.3).
3. **Hard (Arena):** layer-6 opacity 0 / bypass on a MIDI button or SAFETY-deck button, works with TD dead (E §6).
4. **Watchdog-triggered Hard:** stale heartbeat sends the Arena opacity-0 OSC (R5).
5. **Baked swap (R4):** hands the slot to a pre-rendered clip.
6. **FOH backup Mac / LED processor blackout** (MOU, out of TD's hands).

**Dual-fire pad (proposal):** MPK pad N sends one note. TD maps it to the soft kill, Arena maps it (Any Device, Resolume "Piano"-style
momentary or Toggle) to layer-6 bypass. Both apps get the same message from the OS (CoreMIDI multi-client is general macOS knowledge,
UNVERIFIED for these two devices; test). If TD is dead, Arena still kills. Piano mode ("on for as long as you hold ... turn off when you
release", S45) makes a dead-man style momentary hide possible. Never put the Hard kill on the same detection-order-dependent device
identity (S45).

### R13. What experienced programmers say (digest, with the speaker and date)

- "Always have a Plan B and C." Olivia Ema, TD visuals at Notting Hill Carnival, 2 Sep 2024 (S59). Her failure was a mismatch between her
  TD output and the Resolume setup of the production team; the MP4s were the save.
- "Restart at least weekly ... avoid timers that count indefinitely"; test the setup before committing. Derivative staff ben, 13 Oct
  2023 (S24).
- "Production 24/7 setups often schedule a reboot ... Restarts can hide a leak." JetXS, 15 Jun 2022 (S25).
- "TouchDesigner will cook a node only when it needs to"; edit-mode viewers hide missing cooks in perform mode. Pixelux/Xavier (S23).
- "Spout has no queueing between processes ... frames sometimes shown twice and sometimes skipped; NDI keeps a queue." malcolm, 5 Nov
  2022 (S19).
- "The workflow is feasible and many people use it. Success depends on the system having enough resources for both applications'
  combined workloads." malcolm, 28 Dec 2023 (S20).
- "Vulkan is much more sensible to errors and can lead to driver crashes, bringing down TouchDesigner." JetXS, 5 Sep 2023 (S29).
- "The operation is taking too long for the GPU to complete in the gpu-timeout limit of the OS ... no macOS equivalent." malcolm, 25 May
  2026 (S28).
- Derivative's own "When disaster strikes" lesson only says plan recovery and that TD "will try to save a file at the last moment"
  (S66); Stefan Kraus's 2020 workshop on frame drops, crashes and jittery playback for stage shows was closed Zoom with a paid course,
  content not readable (S65). Nothing on hot-standby TD from Derivative; their lighting-and-live-shows page says nothing about
  redundancy (S67).
- On Resolume's side the forum was unreadable (403); only the release notes show Arena 7.23.2 stability items (S48). Arena is final at
  7.23.2 so later fixes (7.27 Autopilot, 7.28 crash fixes, S68) do not apply.

---

## 3. Ranked recommendations

Rank = value for show safety per unit of effort. "GA" = needs the user's go-ahead (Arena / Syphon / OSC / system setting / install).

1. **Run the Arena source-drop matrix first (GA)** and extend it with the R1/R3 additions: sender name after relaunch, red OFFLINE vs
   frozen, recovery without re-trigger, SIGSTOP hang, Add-blend visibility. Everything below depends on its result.
2. **Dual-fire KILL pad + watchdog-to-Arena OSC hide (GA).** Closes the frozen-frame hazard; both tiny.
3. **BAKED tier for every interactive look** (Movie File Out during rehearsal -> normal PF26 pipeline -> SHOW deck) and a one-press swap.
4. **Frame-budget table per look, measured with Arena playing the base**, crossfade cost rule, adaptive-resolution governor, no
   single heavy wall-size pass. Fold into E §7.2 step 1.
5. **TD stability posture on macOS:** frozen project, bridge idle in show, stress/transition test for Vulkan errors, known-good copy.
6. **Perform-mode rehearsal:** logic forced to cook, Window COMP pars, Start in Perform Mode via watchdog relaunch (GA), missing-display
   and focus tests.
7. **Full 6.5 h soak with logging** (thermal pressure + Perform CHOP + RSS), High Power Mode on, power settings reviewed (GA for settings).
8. **MIDI robustness:** DAT callbacks for triggers, onDeviceChange rehearsal, locked controller presets, self-check panel, Resolume
   "Any Device" for the one shared control.
9. **State file + dark-start + REJOIN** so a relaunched TD never surprises the wall.
10. **Sensor confidence/fail-soft** for camera and audio.
11. **Decide on a TD build change** only if the lead wants it: 32820/33230 carry macOS fixes (NDI Out, silent quit, Syphon sender name), but
    changing builds restarts every level of verification; the user chose TD 2 (Pro licence, Intel build). Keep as an explicit decision.
12. **Port single-shader looks to `JZB_*` FFGL** where possible (long term; removes IPC risk for those looks).

---

## 4. Pre-show checklist (proposal; tick only with the named evidence)

**A. Weeks to T-3 days (no wall, no Arena unless GA)**
- [ ] Each look: fps, p95 `msec`, `droppedframes` at 7488x2880 / chosen size, cook rate 30, with another app playing video; row in table.
- [ ] Each look: 10 min at max parameter ranges and all transitions in perform mode; zero Vulkan errors; log kept.
- [ ] Perform-mode start from cold (watchdog relaunch) lands on dark READY; state restored from `state.json`; Global Resolution
      Multiplier = 1 checked on show and backup Mac.
- [ ] MIDI learn table complete for both controllers; presets locked and saved to files; self-check lamps all green; hot-plug test passed;
      launch with controllers unplugged passed.
- [ ] Reactive inputs: unplug camera / audio interface mid-look: look idles gracefully; replug recovers or stays idle.
- [ ] BAKED clip exists, is approved by the user's verdict flow, and is in the SHOW deck for each interactive look.
- [ ] Colour chart and counter pattern sent TD -> Arena (GA): colours numerically match, no premultiply halo, latency in frames noted,
      duplicate/skipped counter count noted at 30 fps.

**B. T-2 / T-1 (Fri 23 Oct, rehearsal day, GA)**
- [ ] Source-drop matrix in the real show Arena file: sender quit, `kill -9`, SIGSTOP, `Active` off; record wall result and recovery.
- [ ] Watchdog: kill TD with layer visible: Arena hides within the target time; relaunch to READY time recorded; REJOIN works; crash
      loop behaviour verified (3 kills in 5 min).
- [ ] Dual-fire pad: with TD running, with TD frozen (SIGSTOP), with TD dead: wall result each time.
- [ ] 6.5 h soak at show settings with logger; thermal pressure, fps, RSS curves saved; pass criteria met.
- [ ] Backup Mac mirror switch rehearsed (E §6, §7.2 step 9): same project, same MIDI map, same sender name, same Arena composition.
- [ ] Operator drill: 5 failures read out loud (TD freeze, TD crash, controller loss, audio loss, thermal warning), operator does the
      runbook without help.

**C. Show day, before doors (5:30 PM)**
- [ ] Fresh cold start of TD and Arena (~4:30 PM); no other apps; Focus/Do Not Disturb on; auto-updates off; Wi-Fi/Bluetooth policy per
      E §3 (NDI off Wi-Fi); AC adapter, High Power Mode, lid open, stand, spare adapter, spare USB cables and hub.
- [ ] `caffeinate -dimsu` (or the settings change) running; Prevent Display Sleep on in the Window COMP.
- [ ] Logger running; thermal pressure 0 at idle; sender name in Arena = clip source; first live look pre-warmed.
- [ ] Controller lamps green; master at 0 on start; paper overlays on; kill pad tested with TD live (one tap, release).
- [ ] Known-good .toe and baked clips on the show Mac and backup Mac; crash-report folder noted.

**D. During the show (operator rules)**
- No edits in TD, no MCP calls, no GLSL changes; do not open Window Placement; do not drag the TD window onto Arena's display.
- Check the thermal lamp and `droppedframes` lamp between acts; if thermal pressure >= 2: drop to half-res look or baked tier.
- Crossfade only between pairs measured OK in section A.

**E. Failure runbook (one line each; proposal)**
- Wall frozen on TD layer: press KILL (Arena hard) -> BASE continues -> note time -> wait for watchdog READY -> REJOIN, re-trigger the
  layer-6 clip if Arena shows OFFLINE/black.
- Controller dead: use the panel; replug; self-check lamps.
- Audio/camera dead: nothing to do (look idles); fix between acts.
- Thermal >= 2 or repeated dropped frames: half-res look, then baked tier, then BASE only.
- TD crash loop (3 in 5 min): stay on BASE + baked; leave the TD layer hidden; fix after the show.
- Arena itself problem: SAFETY deck / FOH backup Mac (MOU).

---

## 5. Open questions for the lead

1. **Who owns the cue: TD (E decision) or Arena with TD following over OSC (R2)?** The hybrid proposal keeps "controls in TD" for
   parameters but makes Arena the show-state master and gives TD a way to re-sync after a relaunch. Your call.
2. **May the watchdog send an OSC packet to Arena (layer-6 opacity 0 on stale heartbeat), and may I (or another agent) test OSC in/out
   with a scratch Arena composition?** Needs Arena + OSC go-ahead. Also needed for the source-drop matrix, Syphon latency and colour chart.
3. **TD build:** `TouchDesigner.app` 2025.32820 (arm64 native) is installed next to `TouchDesigner 2.app` 2025.31550 (Intel, Rosetta).
   td-port's LEARNINGS says 32820 is Non-Commercial and you chose TD 2. 32460/32820/33230 carry macOS fixes (silent quit, NDI Out startup
   crash, Syphon sender name). Does the Pro licence run on a newer build, and do you want that evaluated, or is 31550 frozen for the show?
4. **Arena version:** E's open question stands (Info.plist 7.28.1 vs documented 7.23.2). Source-drop behaviour may differ by version.
5. **Is the show Mac this 16-inch M1 Max (`MacBookPro18,2`) and is the backup identical?** High Power Mode and thermal budget depend on it.
6. **May the show Mac's power settings change (High Power Mode, sleep, caffeinate, Focus) and may the watchdog relaunch into perform
   mode (LaunchAgent / "Start in Perform Mode")?** Both are system-level changes.
7. **BAKED tier:** OK to record each interactive look as a DXV master through the PF26 pipeline as a safety clip? It needs the verdict
   flow and the 75% / DXV3 rules (`production/SYSTEM.md`).
8. **Composition frame rate in Arena (30 fixed?) and TD cook rate 30 vs 60** (E open question 5): decides the judder test.
9. **Full 6.5 h soak slot** on Friday 23 Oct, and venue ambient/airflow on the day: who measures?
10. **MIDI:** may the two controllers also be read by Arena for the single dual-fire kill pad, or do you want a separate third device?

---

## 6. Sources

Docs (TouchDesigner, fetched 16 Oct 2026)
- S1 https://docs.derivative.ca/Perform_Mode
- S2 https://docs.derivative.ca/Window_COMP
- S3 https://docs.derivative.ca/Window_Placement_Dialog
- S4 https://docs.derivative.ca/Project_Class
- S5 https://docs.derivative.ca/Cook
- S6 https://docs.derivative.ca/Optimize
- S7 https://docs.derivative.ca/Performance_Monitor_Dialog
- S8 https://docs.derivative.ca/Perform_CHOP
- S9 https://docs.derivative.ca/Hog_CHOP
- S10 https://docs.derivative.ca/Release_Notes (2025.30000 to 2025.33230 sections; page read to character 200000 of 217262)
- S11 https://docs.derivative.ca/Syphon_Spout_Out_TOP
- S12 https://docs.derivative.ca/Working_Color_Space
- S13 https://docs.derivative.ca/MIDI_In_CHOP
- S14 https://docs.derivative.ca/MIDI_In_DAT
- S15 https://docs.derivative.ca/Execute_DAT
- S16 https://docs.derivative.ca/Audio_Device_In_CHOP
- S17 https://docs.derivative.ca/Video_Device_In_TOP
- S18 https://derivative.ca/download (latest official macOS build listed 2025.33230, 1 Sep 2026)

Derivative forum (fetched)
- S19 https://forum.derivative.ca/t/spout-vs-ndi-vs-other-options-for-same-machine-video-send/297315
- S20 https://forum.derivative.ca/t/frame-drops-and-gpu-usage-dip-when-switching-scenes-in-resolume-via-spout-from-touchdesigner/413014
- S21 https://forum.derivative.ca/t/fixed-td-freezes-when-overlapping-with-resolume-arena/607666
- S22 https://forum.derivative.ca/t/touchdesinger-crashing-when-resolume-is-selected-as-main-application/642468
- S23 https://forum.derivative.ca/t/help-needed-premiere-this-friday/11001
- S24 https://forum.derivative.ca/t/mac-studio-users/384730
- S25 https://forum.derivative.ca/t/vulkan-device-error-when-running-project-24-7/269560
- S26 https://forum.derivative.ca/t/recurring-vulkan-device-error-crashing/612349
- S27 https://forum.derivative.ca/t/vulkan-device-error-macos-15-6-1-commercial-build-2025-31550/830675
- S28 https://forum.derivative.ca/t/vulkan-device-error-while-working-with-blur-top/991446
- S29 https://forum.derivative.ca/t/glsl-vulcan-device-errors-on-macos/371363
- S30 https://forum.derivative.ca/t/multiple-errors-warnings-application-crashing-and-not-enough-gpu-storage-and-gpu-resources/1018605
- S31 https://forum.derivative.ca/t/fatal-process-suspended-in-crash-handler-after-an-unhandled-c-stl-exception-inside-a-cook-on-the-main-thread-when-a-cplusplus-chops-output-is-rebuilt-getchannelname-setstring-one-cook-after-its-first-connect-cook-order-dependent/1015965
- S32 https://forum.derivative.ca/t/fixed-td-hanging-at-100/557990 (search-listing excerpt only, not opened)
- S33 https://forum.derivative.ca/t/default-perform-mode/11773
- S34 https://forum.derivative.ca/t/missing-midi-devices-and-uncooking-bug/978939
- S35 https://forum.derivative.ca/t/fixed-engine-comp-crashing-when-switching-between-tox-files/439222
- S36 https://forum.derivative.ca/t/media-playback-performance-issues/711206
- S37 https://forum.derivative.ca/t/dropping-fps-td/146570
- S38 https://forum.derivative.ca/t/resolved-mac-os-ventura-td-running-at-15-fps/295149
- S39 https://forum.derivative.ca/t/touchdesigner-cooking-while-mac-sleeps/419776
- S40 https://forum.derivative.ca/t/timeline-pauses-on-its-own/10835
- S41 https://forum.derivative.ca/t/crash-on-window-placement-dialog/497179
- S42 https://forum.derivative.ca/t/resolume-ffgl-host-for-touchengine/490220
- S43 Forum search listings (titles/excerpts only): https://forum.derivative.ca/search.json?q=resolume , ...?q=watchdog , ...?q=perform%20mode%20crash , ...?q=thermal%20throttling , ...?q=vulkan%20macOS , ...?q=syphon%20mac

Resolume
- S44 https://resolume.com/support/en/osc
- S45 https://resolume.com/support/en/midi-shortcuts
- S46 https://resolume.com/support/en/NDI_inputs_and_outputs
- S47 https://resolume.com/support/en/syphonspout
- S48 https://resolume.com/blog/30807 (7.23.0 to 7.23.2 fix lists)
- S49 https://resolume.com/support/en/tech-specs (macOS recommended: Sonoma, M2 Max, 16 GB; no memory/Rosetta detail)
- S50 Resolume forum, search-result summaries only (fetch gave 403): https://resolume.com/forum/viewtopic.php?p=37005 ,
  ?p=99053 , ?p=71858 , ?p=72152 , ?p=86362 , ?p=77556 ; Cycling '74: https://cycling74.com/forums/topic/text-heads-up-display-to-syphon
- S68 https://resolume.com/blog/34561 (7.27 notes; later versions, not applicable to 7.23.2)

Other
- S51 https://docs.ndi.video/all/developing-with-ndi/advanced-sdk/ndi-sdk-review/video-formats/frame-synchronization.md
- S52 https://support.akaipro.com/en/support/solutions/articles/69000856691-akai-pro-midimix-using-the-editor-for-customisation
- S53 https://support.akaipro.com/en/support/solutions/articles/69000798861-akai-pro-mpk-mini-mk3-frequently-asked-questions
- S55 https://512pixels.net/2021/11/kbase-article-of-the-week-use-high-power-mode-on-your-16-inch-macbook-pro-with-m1-max/ (quotes Apple KB; Apple page not opened)
- S56 https://eclecticlight.co/2024/02/23/apple-silicon-2-power-and-thermal-glory/
- S57 https://stanislas.blog/2025/12/macos-thermal-throttling-app/ (single blog source; verify `notifyutil` on this Mac: returned 0)
- S58 https://ss64.com/mac/caffeinate.html , https://ss64.com/mac/pmset.html
- S59 https://oliviaema.substack.com/p/producing-digital-art-for-notting
- S60 https://www.ableton.com/en/live-manual/12/midi-and-key-remote-control/
- S61 https://glama.ai/mcp/servers/lucasmaher-hash/touch-designer-mcp/tools/create_show_failover (third-party tool listing; pattern only)
- S62 https://github.com/Syphon/Syphon-Framework (file listing shows SyphonMetalServer.m; README says nothing else)
- S64 Probed locally 16 Oct 2026: `system_profiler SPHardwareDataType`, `sw_vers`, `pmset -g`, `pmset -g therm`, `notifyutil -g com.apple.system.thermalpressurelevel`,
  `file /Applications/TouchDesigner*.app/Contents/MacOS/TouchDesigner`, `PlistBuddy` on both TouchDesigner Info.plist files
- S65 https://derivative.ca/workshop/sequence-shows-and-installations-touchdesigner/63128 (Stefan Kraus, 27 Aug 2020)
- S66 https://learn.derivative.ca/courses/100-fundamentals/lessons/108-resources/topic/when-disaster-strikes/
- S67 https://derivative.ca/feature/lighting-and-live-shows
