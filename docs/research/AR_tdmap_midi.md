# AR: TDMap / TDXMap MIDI mapping tool (function.store, asset 74906) read for jazib-td (26 Oct 2026)

Research only. Nothing was loaded into TouchDesigner, no code run. Tags: [PAGE] derivative.ca asset 74906, [DOCS] the vendor docs
site, [TOX] text read from `toeexpand` of the downloaded free .tox, [REPO] the author's open predecessor repo, UNVERIFIED = needs a probe.
Page: https://derivative.ca/community-post/asset/tdmap-smoothest-midi-mapping-workflow-tool-any-controller/74906 (posted 27 Jun 2026,
author function.store = Daniel (Dan) Molnar, Berlin). The product has since been renamed **TDXMap**: tdmap.functionstore.xyz
308-redirects to https://tdxmap.functionstore.tools (docs `/docs/`, licence `/license/`, browser demo `/demo/`). Video: https://youtu.be/rD7GHs_x0CI
(not fetched). Patreon post https://www.patreon.com/posts/160393153 returned 403 (not bypassed). Author's repos: github.com/function-store.

Local: `research_src/tdmap_74906/TDXMap.tox` (935 KB, free trial build from the vendor's R2 link, no login), `x/` (toeexpand output, 296 files),
`hover_vsn1/` (shallow clone of TD_ParHoverMIDI_VSN1, .git removed, 38 MB). Nothing else downloaded.

## 1. What it is [PAGE][DOCS]
One `.tox` dropped at `/` (one instance per project, "Externalize" once so updates work) that replaces per-control CHOP wiring for MIDI.
A web UI (button in TD's top-right or Alt+Shift+D, Cmd on macOS) shows a grid editor per controller. Features listed:
- Multiple devices, each its own grid; banks (swap whole mapping sets); factory layouts (APC40 MkII, Akai MIDI Mix, Arturia MiniLab Mk II,
  Launch Control family, Midi Fighter Twister, Traktor F1, Intech Grid, OXI E16).
- **MIDI learn**: global Learn, per-slot LRN, "Smart Learn" (classifies knob / fader / relative encoder / button from the first moves),
  "Learn All CC" for a whole controller, PAR learn (hover a TD parameter, move a knob).
- Binding by typing op path + par name, or drag a parameter (or a whole operator/COMP, which bulk-fills empty slots) onto a slot card or the button.
  Retargeting of renamed/moved COMPs (`RetargetBanks`).
- Per assignment: Min, Max, Default, Clamp. Relative encoders, 14-bit (native path needs TD 2025.32460+), velocity, push-encoders, hover mode.
- **Feedback**: per-slot MIDI Out to LED rings, motor faders, button state (toggle/momentary/level); `SendAllFeedback`; `onValueChange` callback can replace/suppress it.
- **Pro only**: smoothing, **pickup (soft takeover)**, easing curves, function/slot/modify modes, math between controls.
- Presets: factory layouts inside the .tox; user library as exportable JSON; "global config" bundles (Save/Load/SetDefault). Mappings live in a separate
  `TDMap_Config` COMP so updates keep them. Prefs in `tdmap-prefs.json`.
- Script mode per slot: Python with CHOP-Execute-style callbacks (`onOffToOn`, `whileOn`...), plus a `TDMap_callbacks` Text DAT with lifecycle
  events (`onReady`, `onValueChange`, `onParLearn`, `onBankChange`, `onConfigSave`...).
- Public Python API on `op.TDXMap` (calls queue and run at frame end): `AssignSlot(par, device, row, col, bank, is_push)`, `Learn(active)`, `CreateDevice`,
  `CreateBank`, `SelectBank`, `SendAllFeedback`, `SaveGlobalConfig/LoadGlobalConfig/SetDefaultGlobalConfig`, `RetargetBanks`, `SetOwnerComp`.

## 2. How the binding works
- [DOCS] Routing uses TD's own MIDI device table: it "edits the same `/local/midi/device` table that TouchDesigner uses". Raw 7-bit values come from a
  MIDI In DAT, 14-bit from a 14-bit CHOP. So devices are the same ones set up in the MIDI Device Mapper.
- The actual par write is inside the locked engine. Whether it is a `par.val` set from a callback, a CHOP export, or an expression is **UNVERIFIED**.
  Evidence for "Python set on events": the Python API/callbacks, the `Controller undo` option (groups parameter changes into one undo step), pickup
  (an expression/export could not do that), and the "pink button while waiting" state. Not a bind expression per control, since there is no per-control wiring.
- [TOX] The free .tox is a shell: `TDXMap/TDXMap_MID.enc` (889 KB) is an **encrypted, locked engine** COMP. Readable only: `TDMapPubExt` (thin facade that
  forwards `@exposed` calls to `PubRunner.Enqueue`, serialises args to a "wire format the locked engine expects... literal eval"), `public_enqueue`,
  `PubRunnerExt`, `ExtUtils` (CustomParHelper, extStubser, logger, keyboard callbacks, FNS_About), `InjectExt`, `vc_data` table. No mapping DAT is exposed.
- Ops: base/container COMPs, DAT executes, par execs, extensions via `CustomParHelper` (his own helper, same code in his other tools). Web UI served locally:
  custom par `Port` default **16669** [TOX], "Open in browser" does `ui.viewFile('http://localhost:<Port>')`. The server code is in the encrypted part (UNVERIFIED how).
  Port 9642 websocket is for the Intech VSN1 editor link only.
- Build: .tox saved in **2023.12120, on Windows 10** (`.build`: build 2023.12120, osname Windows, 20 Aug 2026; internal version.build 109, 14 Jun 2026).
  Needs 2023.12120+; native 14-bit needs 2025.32460+, older builds "legacy per-channel pipeline". So 31550 runs the **legacy 14-bit path** (7-bit unaffected).
  Mac: the page and docs state no OS support at all; docs mention Cmd shortcuts for macOS, and the author's other tools say cross-platform. Not verified on
  Apple Silicon / Rosetta. Binary content is pure Python/TD (no native plugin visible), so Mac loading is plausible, UNVERIFIED.

## 3. Licence, price, audit
- **Proprietary** ("TDXMap is proprietary software"). Free: 14-day full-Pro trial (no sign-in to start, but validates online at startup and ~hourly using
  a machine identifier; mappings kept afterwards). Paid: Patreon membership (OAuth browser sign-in once per computer) or one-time Gumroad key (up to 3-5
  computers, lifetime updates; licence page says 3, home page says 5). Base = core mapping, banks, hardware bank sync, button scripts. Pro adds smoothing,
  pickup, easing, function/slot/modify modes. **Prices are not on any page we could read** (Patreon 403). Once activated it runs offline; live checks only at update install.
  Source "may be provided to subscribers/purchasers" for own modification, no redistribution.
- Audit of what is readable [TOX]: no `subprocess`, `os.system`, `socket`, `urlopen`, pip, or third-party imports in the 70 visible text DATs
  (only TD builtins, `functools`, his helpers); `ui.viewFile` to open docs/localhost. LICENSE text inside is MIT but only for the PubRunner wrapper.
  **The locked, encrypted engine cannot be audited**: it does the licence call, the web server on a local port, and file I/O (configs, prefs).
  The "Externalize" step also writes a .tox into the user palette folder and the updater downloads and replaces it (network, self-modifying). Under our
  audit rule (every import audited, local and free, nothing phones home) it fails: closed, trial phones home, paid.
- [REPO] `hover_vsn1/` (GPLv3, free, Dan Molnar, predecessor "Par Hover Control for VSN1"): relative-encoder MIDI to the hovered/slotted parameter,
  Svelte web components, Python extensions (`scripts/HoveredMidiRelative`, `scripts/IntechGridComm` which uses a websocket DAT to the Grid Editor on 9642, and
  an auto-updater from GitHub). Readable reference for relative-encoder stepping and slot/bank logic. Tied to the VSN1 and TD's hover pane; not a general
  learn/map tool. Not run.

## 4. TD built-in MIDI tools (for comparison)
- **MIDI In CHOP**: raw channel/note/controller numbers as channels (`ch1ctrl7`...), no logical layer; remap by editing the CHOP.
- **MIDI Device Mapper dialog** (the `/local/midi/device` Table DAT, saved in user prefs, not in the .toe): names a device, assigns logical sliders `s1..sN` and
  buttons `b1..bN` to physical controls (it has a learn button), plus MIDI out. https://derivative.ca/UserGuide/MIDI_Mapper_Dialog (fetch timed out; content from
  the MIDI In Map page).
- **MIDI In Map CHOP**: outputs the logical `sN`/`bN` channels from a device table; params `device`, `id`, `sliders`, `buttons`, `bvelocity`, `squeue`; Common page
  Export can write channels to pars (DAT Table by Index/Name, Channel Name as Path:Parameter). Hardware-independent.
- **MIDI In DAT** (event callbacks `onControl`, `onNote`), **MIDI Out CHOP/DAT** (LED feedback by writing CC/notes yourself), **MIDI Event DAT/CHOP** for timed events.
- No bundled palette MIDI component exists in this app (`Palette` search finds only `abletonMIDI.tox` under TDAbleton, which is Live-specific). No learn-to-parameter,
  no soft takeover, no curves, no bank system built in: all of that is what TDMap sells.

## 5. Verdict for us
- **Do not adopt TDXMap.** Closed encrypted engine (cannot meet our audit), trial phones home, paid for the features we want (pickup, curves), Windows-built,
  Mac/Rosetta unverified, 14-bit on the legacy path in 31550, a local web server and a self-updater. Also no listed way for an agent to drive it except its Python API
  (usable, but it would still be a black box).
- Our need is small: sliders (custom pars on each effect COMP, e.g. LK_projection_room 'Room' page) driven later by a few controllers. Build it ourselves on TD's own
  device table + MIDI In DAT; ~150 lines of Python in one COMP, all plain data. Borrow only ideas (Smart Learn classification, bank, pickup, min/max/clamp,
  RetargetBanks, "global config" bundle).
- If the user later wants a polished hardware grid UI, re-check TDXMap Base (price unknown, ask) on a scratch project, after audit of whatever source is supplied.

## 6. Recipe: a `td_midi_map`-style MCP tool (own implementation)
Principle: mapping = a Table DAT (plain rows); runtime = one MIDI In DAT callback + one Python extension; the MCP tool only edits the table and toggles learn.
No bind expressions per parameter (they cannot do pickup/curves and are hard to list/undo).

**Structure** (`/jazib_midi` baseC, network laid out per td-human-readable rule):
`midiin1` (MIDI In DAT, device from the Device Mapper or `par.device`), `map` (Table DAT), `state` (Table DAT, live: last value, picked_up flag), `ext` (Text DAT, extension
`MidiMap`), `cb` (DAT Execute / the MIDI In DAT's own callbacks DAT), optional `midiout1` (MIDI Out DAT) for LED feedback.

**map table columns**: `id, device, channel, kind(cc|note|pb), number, target (op path), par (name or tuple name), min, max, curve(lin|exp|log|ease|step), invert(0/1),
mode(abs|rel), takeover(pickup|jump|scale), clamp, feedback(0/1), enabled, label`. One row per binding; save with the project (`table.save` to
`jazib-td-mcp/projects/midi_maps/<name>.json` via export to JSON; keep the Table DAT's text in the .toe too).

**MCP tools** (thin, all go through `td_exec` of `op('/jazib_midi').ext.MidiMap.<fn>`; keep logged):
- `td_midi_learn_start(target, par, min?, max?, curve?)` sets `learn={target,par,...}`; the next incoming CC/note (the MIDI In DAT `onControl`/`onNote`) creates the row
  (`kind,channel,number` from the message), clears learn, returns the row. Add a timeout. Smart-learn classification: if the first 3 values differ by one step each
  with wrap or 63/65 centred values, set `mode=rel`; if only 0/127 values, note/`step`.
- `td_midi_unlearn(id)`, `td_midi_list()`, `td_midi_set(id, {min,max,curve,takeover,invert,enabled})`, `td_midi_save(name)`/`td_midi_load(name)`,
  `td_midi_monitor(n)` (last n raw events, for debugging without hardware), `td_midi_simulate(kind,channel,number,value)` (calls the same handler, so tests run without a controller).

**Value path** (in the callback, per message): `x = value/127` (or 14-bit: `(msb*128+lsb)/16383`; if the 2025.32460 native path is wanted, gate on `app.build`);
`x = curve(x)` (`lin: x; exp: x**2.2; log: x**(1/2.2); ease: x*x*(3-2*x)`); `y = min + x*(max-min)`; clamp; for menu/toggle pars use `round`/threshold; for tuple pars write each member;
write with `getattr(op(target).par, par).val = y` (never `.expr`, keep Resolume/other exports untouched). Rel mode: `delta = (value-64)*step`, add to the current par value, clamp.
Use `par.normMin/normMax` as default min/max when row min/max empty, so a slider gets its natural range.

**Soft takeover**: store per row `picked` bool. When the par changes by other means (slider, preset load, bank switch) set `picked=False`. In `pickup` mode ignore
incoming values until the controller value crosses the par's current normalised value (|x - cur| < 0.02, or sign change vs the last message), then set `picked=True`.
`scale` mode: remap the remaining travel so controller and par meet at an end. `jump`: write immediately. Needs `ParameterExecute` on mapped pars (or a 10 Hz poll
of the `map` rows) to detect external edits; poll is simpler and cheap for < 100 rows.

**Feedback**: if `feedback=1`, on any par change (same poll) send the CC back through `midiout1` with the inverse curve, so LED rings/motor faders follow; skip
the echo for the value we just wrote (compare with a `last_sent` column).

**Banks** (later): add `bank` column and `active_bank` par; rows of other banks are ignored and set `picked=False` on switch. Presets = load another JSON.

**Safety/audit**: no network, no subprocess, no eval of table text (parse numbers, look up par names with `getattr` after checking `op(target)` exists and is a custom or
built-in par), nothing written outside the project's midi_maps folder. Device selection stays in TD's Device Mapper (user action, once). Never write to Arena.

**Test plan (no hardware)**: `td_midi_simulate` against a scratch COMP with a Float par 0-1 and a Float par 0-255: lin/exp/ease endpoints, invert, clamp, pickup crossing, tuple par,
learn timeout, unlearn, save/load round trip. Real hardware test only when the user has a controller connected (target: a Rosetta TD note: MIDI via CoreMIDI works in TD; UNVERIFIED on 31550).

## 7. Open questions
- TDXMap price and whether it runs under Rosetta on 31550 (only a scratch-project trial would tell; needs the user's go-ahead; trial phones home).
- Does the vendor offer source to Base buyers (licence page says "may")? If so the audit could be redone.
- Which controller will the user use? That decides rel vs abs, 14-bit, and LED feedback needs.
