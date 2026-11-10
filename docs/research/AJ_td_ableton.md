# AJ - TouchDesigner <-> Ableton Live 12 Suite (26 Oct 2026)

Research agent AJ for `INTEGRATION_BRIEF.md`. Research only: no TD, no Live, no MCP call, nothing installed. What was done: read the TDAbleton
palette `.tox` files (expanded with `toeexpand` into the session scratchpad, not loaded), read the Remote Script and Max devices TD ships under
`tfs/Samples/TDAbleton/`, read the vendored `mcp-vendor/ableton-live-mcp` source, `docs/research/ops/ops_CHOP_2025.31550.json`, and fetched
docs.derivative.ca (TDAbleton, Ableton Link CHOP). Tags: [V] verified from a source I read (file or doc page), [S] source/doc statement or secondary,
[U] unverified design or guess, [D] op/par confirmed in `docs/research/ops/`, [FS] file seen on this Mac. Target: TD 2025.31550 (Rosetta, Mac), Live 12.4.3
[FS: `Info.plist` CFBundleShortVersionString], `ableton-live` MCP v1.8.1 (handshake 108 tools with `ABLETON_TOOLSETS=session,tracks,clips,devices`; full server 156).

## 1. Summary

1. **TDAbleton ships inside TD** and is real: palette `Palette/TDAbleton/Live 11+/` (12 `.tox`, package version **2.6.3**, saved by TD 2025.31376 on
   Windows [V `.build`]) plus the Live-side files in `tfs/Samples/TDAbleton/Live 11+/TouchDesigner/` (Remote Script `TDA.py`, 8 `.amxd` Max devices, a demo
   Live set) [FS]. Doc page says "Live 11.1.5 and up, TD 2021.20k+" and never says "12"; the changelog (2.5, 2.5.2) names Live 12 fixes ("Main track" rename,
   adding Max devices on Live 12), so Live 12 is intended but **not tested here** [V/U].
2. **It does not collide with AbletonMCP on ports or file names**: AbletonMCP = TCP 127.0.0.1:9877 in folder `Remote Scripts/AbletonMCP/`; TDA = UDP
   58888 (Live receives), 58811 (TD receives), 51111 (Max devices) in `Remote Scripts/TouchDesigner/` [V]. Both are `ControlSurface` subclasses that each need their
   **own Control Surface row** (Input/Output None); Live has 6 rows [S]. Same-process interplay (two scripts on Live's main thread) is [U].
3. **Two blockers to decide before TDAbleton is ever installed** (section 6): (a) TDA's OSC server binds **0.0.0.0** and exposes `/shell/runCode`,
   `/shell/consoleLine` (Python `exec`/`InteractiveConsole` inside Live) and `eval()`s a field of `/tda/command addDevice` [V `TDA.py` lines 197-215, 376-404, `Shell.py`]
   - this undoes the "loopback only, no arbitrary-code path" reason `wstierhout` was chosen (AH); (b) TDA's **Install** button also edits Live's `Library.cfg`
   [V `TDAbletonExt` `doInstallTDAbleton`], which breaks "never write the other app's config files". Recommended path: manual copy of one folder only, firewall the ports,
   user's go-ahead (section 6).
4. **Tempo/phase: Ableton Link CHOP is the lowest-risk first step**: built into TD, no Live-side install, `enable` default **off** [D], outputs ramp/pulse/sine/count/bar/
   beat/sixteenths/tempo/beats/phase + status `numpeers linked waiting synced` [D][V doc]. TD is a listener (no tempo-set par); set the tempo from Live with MCP
   `set_tempo`, toggle Link with `set_ableton_link` and TD follows.
5. **Audio into TD on this Mac needs a loopback device that is not installed** (only built-in mic/speakers + a `ParrotAudioPlugin.driver` in HAL [FS]). Options ranked in
   section 3.3: zero-install first (TDA_Level RMS per chain, and MCP `get_track_meters` polling), then BlackHole (GPL-3.0, install gate) or Aggregate/Multi-Output device.
   TDA_Level gives **volume only, no spectrum** [V help text]; band splits come from the shipped `TDA_Audio_Analyzer.adg` rack (chains Low/Mid/High) [V].
6. **Cue/scene both ways** is covered by TDA components (`abletonSong` Firescene/Stopallclips/Cuepointtojumpto/Tempo/Play/Stop, `abletonClipSlot` Fireclip,
   callbacks DATs) and by MCP (`fire_scene`, `fire_clip`, `stop_all_clips`, `jump_to_cue`, `start_playback`); a no-install fallback is MIDI over the macOS IAC Driver.
7. **Proposed**: `td_link` (typed, TD-only), `td_tda` (health/loader; `check` is read-only, `load` waits for the user), `td_live_audio` (AC_audio source), plus
   `td_exec` recipes first. Tool pairs in section 4.

## 2. What exists (TD <-> Live)

| # | Item | What it does | Mac / 2025.31550 / licence | Tag |
|---|---|---|---|---|
| 1 | **TDAbleton** (Derivative palette, author Ivan DelSol) | Live Set <-> TD over OSC/UDP: song, tracks, clip slots, racks, device params, MIDI notes/CC, levels, time data, mapper. Components: `tdAbletonPackage` (holds `tdAbleton` master + all comps), `abletonSong`, `abletonTrack`, `abletonClipSlot`, `abletonChain`, `abletonRack`, `abletonDeviceParameters`, `abletonParameter`, `abletonMapper`, `abletonMIDI`, `abletonLevel`, `abletonValueListener` | Palette is in the app [FS]; Mac supported (docs list a Mac file-limit note); part of TD, Max devices are Derivative's, licence text not on the doc page | V |
| 2 | TDA Remote Script `TouchDesigner/` (`TDA.py`, `OSC3.py`, `Listeners.py`, `Shell.py`, `songInfoStructure.py`) | Control Surface class `TDA`; OSC server `0.0.0.0:58888`; client defaults `127.0.0.1:58811` | Python 3 branch (`OSC3`) for Live 11+/12 [V] | V |
| 3 | TDA Max devices | `TDA_Master` (on Main track; ports, time data), `TDA_MIDI` / `TDA_MIDI_MPE` (notes/CC/bend out of a track), `TDA_Level` (RMS of its chain), `TDA_Mapper` (any param, incl. non-automatable), `TDA_Ignore` / `TDA_Ignore_MIDI(_MPE)` (hide parts of big sets), rack OSC devices | Needs Max for Live: Live 12 Suite bundles Max (`App-Resources/Max/Max.app` [FS]) | V |
| 4 | Install button on the `tdAbleton` COMP (Utilities page) | `shutil.copytree` of the shipped `TouchDesigner/` folder into `<User Library>/Remote Scripts/`, then **edits `Library.cfg`** to add a "TouchDesigner" User Folder | See section 6 gate | V |
| 5 | Demo | `Demo Project/TDAbletonDemo.toe` + `TDADemo Live Set/TDADemo Set.als` and `TDA Project/` presets | In app [FS] | FS |
| 6 | **Ableton Link CHOP** `abletonlinkCHOP` | Joins a Link session; outputs tempo/beat/bar/phase; no tempo-set par | In dump: pars `active, enable(False), startstopsync, signature1/2, callbacks, status, ramp, pulse, sine, count, countramp, bar, beat, sixteenths, rampbar, rampbeat, tempo, beats, phase` [D]; Info CHOP channels `ableton_is_playing, ableton_tempo, ableton_clock_diff, ableton_time_behind_link, ableton_lost_time` [V doc]; doc warns Link "doesn't work with all sound drivers" (DirectX example); no macOS notes | D/V |
| 7 | Beat CHOP / Timeline | Local clock; `updateglobal`, `bpm`; Link does not drive `/local/time` by itself [S W R6] | `beatCHOP` [D] | D |
| 8 | MIDI In CHOP / MIDI In DAT / MIDI Event DAT | Notes, CC, clock bytes (start/stop/continue, SPP) from any CoreMIDI port incl. macOS **IAC Driver** | CoreMIDI built in, no install [S] | S |
| 9 | Audio Device In CHOP | CoreAudio input incl. loopback devices; macOS mic-permission prompt | Not created yet; prompt behaviour for `TouchDesigner 2.app` unconfirmed (`ops/CHOP.md`) | D |
| 10 | OSC In CHOP/DAT, OSC Out | For custom M4L/Max or AbletonOSC-style senders | UDP ports; creating OSC In opens a port (not done) | D |
| 11 | Community | Top-5 TDAbleton components (elburz, Mar 2023), TDAbleton 2.0 (Ivan, Aug 2022), PlexusPlay (TD <-> Live both ways, `abletonSong`, Jun 2026), DJ Shadow Shadowsphere (Live MIDI -> OSC -> TD) | `W`, `S`, `AB` rows | S |
| 12 | `ideoforms/AbletonOSC`, ableton-js, Bitwig/other | Alternative OSC Remote Scripts (MIT, ports 11000/11001) | not audited here; would be a third Control Surface row; **not needed** since AbletonMCP exists | U |
| 13 | **AbletonMCP** (`mcp-vendor/ableton-live-mcp`, v1.8.1) | The Live-side control we already have: TCP 9877 loopback, no code-exec path | Installed script `~/Music/Ableton/User Library/Remote Scripts/AbletonMCP` [FS]; `ABLETON_PORT` / `ABLETON_MCP_PORT` env override [V] | V |

TDAbleton parameter surfaces I read (cparm lists, all [V]): `abletonSong` Tempo, Play, Stop, Loop*, Timedata, Scenetofire/Firescene, Stopallclips, Cuepointtojumpto/Jump,
Tempotap, Nudgeup/down, Signature, Cliptriggerquantization, Recordmode, Backtoarranger, Addtdamasterdevice, Callbackdat; `abletonTrack` Track, Mute, Solo, Volume, Panning,
Arm, Crossfader, Includeclipdata/Includeaclipdata/Includeaudiodata, Currentclip, Enablecallbacks, Callbackdat; `abletonClipSlot` Slot, Fireclip, Stopclip, Midicliptimerange;
`abletonLevel` Track, Device, Mix (apply track mixer or raw), Leveldataonly; `abletonMIDI` Lastnotedata, Defaultnoterange, Enablecallbacks, MPE add.
Doc caveats [V doc]: duplicate track/device names confuse it (auto-rename option), names with `#` break, output meters only update while visible in Live's UI (Live Object Model bug),
big sets slow loading and can overload OSC on Macs (`sudo launchctl limit maxfiles 128000 524288` is the doc's Mac fix: a system change, user's call), Auto Sync can echo changes
both ways, every TD parameter change creates a Live undo step.

### 2.1 Conflicts with AbletonMCP (Control Surface slots and ports)

| Resource | AbletonMCP | TDAbleton | Conflict? |
|---|---|---|---|
| Control Surface row | one row = `AbletonMCP`, Input/Output None | one row = `TouchDesigner`, Input/Output None | No, but they need **two** rows; keep hardware rows untouched (MIDI controllers stay owned by TD, AH) |
| Folder | `Remote Scripts/AbletonMCP/` | `Remote Scripts/TouchDesigner/` | No |
| Ports | TCP 9877, 127.0.0.1 | UDP 58888 (Live, `0.0.0.0`), 58811 (TD), 51111 (Max devices) | No overlap; none overlap Resolume's usual OSC ports either (7000/7001 [S], not checked) |
| Live main thread | schedules JSON commands, Live API calls | `schedule_message` loops, listeners on song/tracks, song dump at connect | Possible stalls during TDA song dump while MCP calls run; sequence them: connect TDA, wait for dump, then use MCP [U] |
| State echo | MCP writes to the set | TDA Auto Sync writes back to the set | Intended: TD sees MCP edits; but loops possible if TD also writes the same par; use `Listenonly` on the `tdAbleton` COMP when TD should only read [V par] |
| Security posture | loopback, typed commands | network-wide, remote Python | **Yes** (section 6) |

## 3. Patterns (signal flow, op chains, failure modes)

### 3.1 Tempo and phase from Live into TD (Link)
Chain: Live `set_ableton_link(true)` -> `abletonlinkCHOP` (`enable` 1, outputs bar/beat/sixteenths/tempo/phase/ramp/status) -> `selectCHOP` or direct -> Null CHOP `n_link`; `infoCHOP`
`op`=link1 -> Null `n_link_info` (channels `ableton_is_playing`, `ableton_tempo`, `ableton_clock_diff`). Optional: `chopexecuteDAT` on `tempo` `valuechange` ->
`op('/local/time').tempo = round(val, 2)` behind custom toggle `Drivetempo` (default off) so `beatCHOP` (`updateglobal` on, one only) and `AC_audio` `beat`/`bar_ramp` follow Live [U, per W R6 + open question 2].
- Same Mac works in principle: Link peers on one host discover each other (Link uses UDP multicast discovery [S, ableton.github.io/link]). Under Rosetta, and with the macOS "Local Network"
  permission, it is **[U] until step T3** of the test plan. Failure modes: `numpeers` 0 (Link off in Live: Live 12 puts Link in Settings > Link, Tempo & MIDI; firewall; local-network permission), `waiting` stuck,
  Link ignores start/stop unless **Start Stop Sync** is on in Live *and* TD (`startstopsync`) [D][S], tempo cannot be pushed from TD (use Live), phase jumps when a peer joins mid-bar (quantum = bar; do not
  retrigger looks on a phase jump), Link needs a running audio engine in Live (Live stopped but audio engine on is fine).
- Latency: Link phase is for the system clock; the audio output latency of Live is not compensated in TD (Link repo: each implementer adds output latency [S]). A visual offset of a few tens of ms is
  expected; give the look a `Latencyms` offset on `n_link` and calibrate by eye/scope (T4).

### 3.2 MIDI clock and notes from Live (no install, no M4L)
macOS Audio MIDI Setup > Window > Show MIDI Studio > IAC Driver > "Device is online" (system component; no download) [S]. Live Settings > Tempo & MIDI: on the IAC output row switch **Sync** on (clock) and
**Track** on (notes); a MIDI track's output "MIDI To" = IAC Driver (MCP `set_track_routing` field `output_routing_type`, display name from `get_track_routing`; the Settings toggle itself is GUI-only).
TD: `midiinCHOP` (device "IAC Driver Bus 1") -> events; clock start/stop/continue and 24 ppq timer events can drive the Timeline per the MIDI In doc [S]; `midiinDAT`/`midieventDAT` for note-based
cues. Failure modes: clock drift/jitter (low-pass tempo over a bar, as K 2.3), IAC bus shared with other apps, hardware controller rows must not be reused.
Use this when Link is unreliable on the venue network (Link is LAN multicast; IAC is local only).

### 3.3 Audio from Live into TD (ranked)
| Rank | Route | Gives | Install? | Latency / failure modes |
|---|---|---|---|---|
| A | `TDA_Level` per chain + `abletonLevel` | RMS volume per track/return/Main (pre-fader or Mix), over OSC; **no spectrum** | TDA install + a Max device in the set | OSC rate follows Live's UI-thread meter update; meters update only when visible in Live [V doc] |
| A2 | `TDA_Audio_Analyzer.adg` rack (Low/Mid/High chains [V]) with `TDA_Level` per band | Three band RMS values, good for `low/mid/high/level` | same as A | band edges are the rack's EQ; match them to `AC_audio` (120 Hz / ~1.2 kHz / 6 kHz) or accept different edges |
| A3 | MCP `get_track_meters` / `get_master_meters` polling | L/R 0..1 post-fader, per track, no install | none | each poll = TCP round trip through Live's main thread; fine for a status panel (a few Hz), not for beat reactivity |
| B | **BlackHole** (2ch/16ch) as Live's output, TD `audiodeviceinCHOP` driver CoreAudio | real audio, full `AC_audio` analysis chain (kick/snare/hat/spectrum) | **Install gate**: GPL-3.0 (commercial licence for non-GPL use [S]); `brew install blackhole-2ch` needs admin and a CoreAudio restart/reboot | user hears nothing unless a **Multi-Output Device** (BlackHole + speakers, drift correction on the speakers) or an Aggregate is created in Audio MIDI Setup; Live and TD must use the same sample rate (44.1/48 k) or crackle; TD mic-permission prompt for `TouchDesigner 2.app` [U]; buffer 256 samples ~ 6 ms each side [U] |
| C | Aggregate Device (built-in output + BlackHole) | monitoring plus capture in one device | same as B | Live prefers one device; aggregates add drift unless clock source set to the real interface |
| D | Loopback (Rogue Amoeba) | named virtual devices per source | paid, not audited | not evaluated |
| E | File hand-off: MCP `record_section` (WAV, no export dialog) -> `audiofileinCHOP` | offline looks from a recorded section | none | not live; good for tests and for pre-rendered visuals with the right song |
| F | Own M4L sender (`udpsend` of band energies) | custom analysis | write a `.amxd`: user decision | not built; only if A2 is too coarse |

Recommendation: A3 now (no install, shows meters in TD), A/A2 when TDAbleton is accepted, B when the user wants kick/snare reactivity from Live. The user's earlier decision (td-port 12 Oct: external 0-1
values over TD mic analysis) stays the default for PF26 shows; Live audio is for rehearsal, tests, and installations.

### 3.4 Into `AC_audio` (AC_audio_reactive_designs.md section 2)
`AC_audio` has `Source` menu 0 file, 1 device. Add **2 = live-link** (does not replace analysis): (1) `Source` 1 device with route B/C feeds the same `switchCHOP` -> `n_mono` -> low/mid/high/kick/snare/hat/spectrum
unchanged. (2) For routes A/A2, a second CHOP `ac_tda` provides `low mid high level` directly (rename `abletonLevel` channels, `lagCHOP` as in AC) and bypasses the analysis, so spectrum TOPs (`out_spec`) are
unavailable and looks that need them fall back to the file source. (3) Tempo: `beat`/`bar_ramp` from `n_link` instead of the typed `Bpm` (the AC table says "no live BPM here"; Link is the way to have one when Live is the source).
Depth/flash governor rules from AC/K apply unchanged: reactivity master `Depth`, `kick_lum` retrigger 0.5 s.

### 3.5 Cue and scene triggering both ways
| Direction | No-install route | TDAbleton route | MCP route |
|---|---|---|---|
| TD -> Live | MIDI Out CHOP to IAC; a Live MIDI-mapped clip/scene key (user maps in Live, GUI) | `abletonSong.Firescene` (name or index), `abletonClipSlot.Fireclip`, `Stopallclips`, `Cuepointtojumpto`, `Play`, `Stop`, `Tempo` | `fire_scene`, `fire_clip`, `stop_clip`, `stop_all_clips`, `jump_to_cue`/`jump_to_locator`, `start_playback`, `set_tempo` (from Claude only, not from a running show) |
| Live -> TD | a MIDI "cue track": one note per scene played by a clip in each scene; `midiinCHOP` -> `tableDAT` cue map -> look switch | `abletonSong` callbacks (scene triggered; `last_started_scene` is a best guess, doc), `abletonTrack`/`abletonClipSlot` callbacks DAT when a clip starts/plays (clip names usable as look IDs) | `get_session_snapshot`, `get_clip_info` (poll, not event) |
A cue map is a TD `tableDAT`: scene/clip name -> look COMP + crossfade seconds; names must be unique and contain no `#` (TDA limit). Safe-hold: if the connection or Link drops, looks keep
free-running (AC "Depth 0 fades to free-running within 1 s"). Never let a Live cue change whole-frame brightness; the flash governor (K) sits after it.

## 4. Proposed jazib-td upgrades

Order: `td_exec` recipe -> typed tool when reused. Every builder: one structural change per call, `td_layout flow` after, viewers on, network pane on the COMP, `td_errors` after. Handlers go in `td/handlers.py`
(pure functions + `COMMANDS` entry) with a thin tool in `src/`. Gate on `app.build` with `build_gate` where noted; nothing here needs a build newer than 31550 (Link CHOP and TDA exist in the dump / app).

| Tool | Args | Side | Builds in TD | Pairs with `ableton-live` tools |
|---|---|---|---|---|
| **`td_link`** (TD-only, safe) | `parent='/project1'`, `name='link'`, `enable=false` (build first, enable on request), `signature=[4,4]`, `outputs=['ramp','bar','beat','sixteenths','tempo','beats','phase']`, `startstopsync=false`, `drive_tempo=false`, `latency_ms=0` | `td/handlers.py` `cmd_link` + `src` tool | Base COMP `link` with `abletonlinkCHOP` -> Null `n_link`; `infoCHOP`(op=link) -> Null `n_link_info`; optional `chopexecuteDAT` `tempo_follow` behind custom toggle `Drivetempo`; custom pars page `Link` (`Enable`, `Latencyms`, `Drivetempo`); returns channel table and `numpeers/linked/synced` so Claude can confirm; arranged | `set_ableton_link(true)`, `set_tempo`, `get_session_info` (tempo/Link state), `start_playback`/`stop_playback`, `tap_tempo` |
| **`td_tda`** `action=check` (read-only) | none | `td/handlers.py` | reads the installed state without writing: shipped folder exists in `app`'s `tfs`; `~/Music/Ableton/User Library/Remote Scripts/TouchDesigner` present? same for `AbletonMCP`; versions (`tdAbleton` `Version` par, `TDA.py` `DEFAULT_*_PORT`); `listen 58888/58811/51111` via `lsof` (read only); `0.0.0.0` bind warning; Live process running; returns a go/no-go list | `doctor --json` (CLI, not an MCP tool), `get_session_info` |
| `td_tda` `action=load` | `parent`, `components=['song','track','level']`, `address='127.0.0.1'`, `listenonly=true`, `autosync=false` | handlers | `tdAbletonPackage.tox` from `app.samplesFolder`/Palette via `comp.loadTox`, sets `Abletonaddress 127.0.0.1`, `Listenonly` on, `Connect` after the user's go-ahead; adds the chosen comps; `Showconnectingdialog` off, `Suppresspopupdialogs` on so no modal blocks the MCP; never presses Install | `get_session_info`, `get_track_info`, `get_session_snapshot` to compare names (duplicate-name check) |
| `td_tda` `action=status` | none | handlers | `tdAbleton` `Connected`, song name, track names, duplicate-name list, last OSC age | `get_session_snapshot` |
| **`td_live_audio`** | `source='meters'|'tda_level'|'device'`, `device`, `rate`, `into='AC_audio'` | handlers + docs | `meters`: Script CHOP/Timer poll is NOT used (MCP is not callable from TD); instead a `tableDAT` that `td_exec` fills (documented hand-off). `tda_level`: renames `abletonLevel` channels to `low/mid/high/level`. `device`: `audiodeviceinCHOP` (CoreAudio, device menu by name, 2 ch) -> `AC_audio` switch input; first call asks for the mic-permission prompt (APP gate) | `get_master_meters`, `get_track_meters`, `get_return_tracks`; for B: `get_track_routing`/`set_track_routing` (not for Main output device: Settings is GUI-only) |
| `td_cue_map` (later, shared with Resolume) | `rows=[{key, look, fade}]`, `source='tda'|'midi'|'osc'` | handlers | `tableDAT` + `chopexecuteDAT`/callbacks that switch looks; arranged | `fire_scene`, `fire_clip`, `create_scene`, `set_scene_name`, `get_session_snapshot` (names) |

Recipes before typing (`td_exec`): R-A `link` (above, 6 ops); R-B IAC MIDI in (`midiinCHOP` device pick by name containing "IAC", `midiinDAT`); R-C `tda_probe` (`op('/project1/tdAbleton').par.Connect`, `.SongInfo` keys).
Rules: `td_tda load` must not press `Install`/`Updateabletoncomps`/`Start`/`Autostartlive` (they write or launch Live); `Abletonaddress` stays `127.0.0.1`; the TDA COMP is stored as an external `.tox` in `projects/` if kept.
Docs to update with it: `docs/USING_TD.md` (Link recipe, IAC recipe), `AC_audio_reactive_designs.md` (Source 2), `FUTURE.md` (none), `AUDIT.md` row for TDAbleton Remote Script if installed.

## 5. Test plan

**Offline (now, nothing opens)**: (1) `npm test` additions: `plan_link` pure function (pars/outputs/names, `enable` default false, naming rules), `td_tda check` path logic with fake directory trees, build-gate note; (2) `test_handlers.py`:
Link CHOP par names against `ops_CHOP_2025.31550.json` (all exist), TDA par names against the expanded `tdAbleton.cparm` copy; (3) static check that `td_tda load` never touches `Install/Updateabletoncomps/Start/Autostartlive`.

**Live steps, in order**
| Step | Mark | Action | Expect |
|---|---|---|---|
| T1 | TD-only | `td_link` build with `enable=0` in a scratch COMP; `td_errors`, `td_layout flow`, `td_screenshot` | no errors; ops arranged; channels listed (`numpeers` 0) |
| T2 | TD-only | `td_exec` probe: `op('link/link1').par.enable = 1` alone | `numpeers` 0, `linked`? note if Rosetta prompts a Local Network permission; record in LEARNINGS |
| T3 | APP, user go-ahead | Live open with a **disposable set**; MCP `set_ableton_link(true)` then `get_session_info` | TD `numpeers` 1, `synced` 1 within a few seconds; `ableton_tempo` = Live tempo |
| T4 | APP | MCP `set_tempo(100)`, `start_playback`; read `n_link` for 20 s with `td_inspect` | tempo 100, `beat` pulses at 1.67 Hz, bar every 4 beats; compare phase to Live by eye; note offset ms (Latencyms) |
| T5 | APP | Live `stop_playback`; read `ableton_is_playing`; toggle Start Stop Sync (GUI) on both | `is_playing` 0 only with sync on; record result (forum 2021 says ignored) |
| T6 | APP | `td_tda check` (read-only); then user decides on TDAbleton (section 6) | list of ports, folders, bind warnings |
| T7 | APP + install gate | (After approval) manual copy of `TouchDesigner/` folder; firewall rule; add Control Surface row `TouchDesigner` in Live (user, GUI); open `TDADemo Set.als` copy; `td_tda load`; Connect | `Connected` 1, SongInfo tracks match MCP `get_session_snapshot` names |
| T8 | APP | `abletonSong.Firescene` from TD; MCP `get_session_snapshot`; then MCP `fire_scene` and read the callback | both directions fire; record latency (frames) |
| T9 | APP | `abletonLevel` on Main with a looping test clip vs MCP `get_master_meters` | same order of magnitude; meters stop updating if Live window hidden (doc) |
| T10 | APP + install gate | BlackHole route B (only if user approves): Multi-Output device, TD `audiodeviceinCHOP`, mic prompt | non-zero samples in `n_stereo`; `kick` count per bar plausible on a 4-on-the-floor clip |
Each APP step needs Live open and a go-ahead; never touch the user's real set (copy `.als`, `save_set` only on the copy).

## 6. Gates (stay as set by AH and `mcp-vendor/README.md`)
- Installing the TDA Remote Script, adding any Max device to a set, enabling a Control Surface row, creating an IAC bus, installing BlackHole/any HAL driver, `launchctl limit maxfiles`, and any firewall change: **user's go-ahead each**.
- **Security decision for the user (TDA)**: the script listens on all interfaces and accepts remote Python (`runCode`, `consoleLine`), so on a venue/home LAN anybody can run code inside Live. Options: (1) skip TDAbleton and use Link + IAC + MCP (no network exposure);
  (2) install it only with a macOS firewall block of inbound 58888/51111 (or a `pf` loopback-only rule) and keep it off at shows; (3) the user edits a copy of `TDA.py` to bind `127.0.0.1` (we do not patch their files, and a repo change would leave the upstream audit). Not decided; do not install before the user chooses.
- **Install button writes `Library.cfg`**: forbidden for us; the manual route copies only `.../Remote Scripts/TouchDesigner/` from `tfs/Samples/TDAbleton/Live 11+/` and skips the browser User Folder (devices are added by TDA itself from that folder, e.g. `TDA_Master.amxd` to `SONG.master_track` [V]).
- Set-changing MCP tools and anything that edits the set (adding `TDA_Master`) = disposable set first; `save_set` only on the copy. TD never writes `.als` or Live preference files.
- Host-install rule (CLAUDE.md): Live is not code-sign checked; this file makes no provenance gate.

## 7. Sources
- Files [FS]: `/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/Palette/TDAbleton/Live 11+/*.tox` (expanded copy in scratchpad `tda/`: `tdAbleton.cparm` ports and Version 2.6.3, `changes.text` 2.4 to 2.6.3, `TDAbletonExt` install code);
  `.../tfs/Samples/TDAbleton/Live 11+/TouchDesigner/{TDA.py,Shell.py,OSC3.py,*.amxd}`, `Demo Project/`; `jazib-td-mcp/docs/research/ops/ops_CHOP_2025.31550.json` (abletonlinkCHOP, beatCHOP, midiinCHOP, audiodeviceinCHOP);
  `mcp-vendor/ableton-live-mcp/ableton_live_mcp/{remote_script/__init__.py,connection.py,tools/session.py,tools/tracks.py,tools/_groups.py}`; `.mcp.json` (`ABLETON_TOOLSETS`); `AUDIT.md` (108-tool handshake).
- Web (fetched 26 Oct 2026): https://docs.derivative.ca/TDAbleton ; https://docs.derivative.ca/Ableton_Link_CHOP ; https://github.com/ExistentialAudio/BlackHole (GPL-3.0, commercial licence otherwise); https://ableton.github.io/link/ (concepts, via K).
- In-repo: `K_audio_reactive.md` 2.3, `W_tutorials_control_audio_python.md` R6, `E_live_rig.md` BPM sync, `AC_audio_reactive_designs.md` section 2, `N_community_components.md` row 46, `AH_relevant_mcps.md` section 2, `ops/CHOP.md`.

## 8. Open questions
1. Does Live 12.4.3 load TDA 2.6.3 cleanly (no Python errors in Live's `Log.txt`), including `TDA_Master` on the Main track? Needs T7.
2. Does TD 2 (Rosetta) join a Link session with Live on the same Mac, and does macOS ask for Local Network permission? T2/T3.
3. Does `abletonlinkCHOP` ever set `/local/time` tempo itself? (W open question 2); the recipe assumes not.
4. Security choice for TDAbleton (section 6): skip, firewall, or loopback-bind a copy? Which does the user want?
5. Is Live part of the PF26 plan or only a test/installation tool? (If only a controller host, stop at Link + IAC; do not install TDA or BlackHole.)
6. Will the user install BlackHole (GPL-3.0) or prefer a hardware interface loopback? Mic-permission behaviour of `TouchDesigner 2.app` for Audio Device In is unconfirmed.
7. Can the AbletonMCP and TDA scripts run together under load (song dump while MCP commands)? Test T7/T8.
8. Does Live 12.4's Settings expose a Start/Stop Sync toggle and does TD's `startstopsync` follow it? T5.
