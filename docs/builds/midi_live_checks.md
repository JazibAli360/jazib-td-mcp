# MIDI mapper live checks (26 Oct 2026, TD 2025.31550, no MIDI hardware)

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60) (MIDI_mapper).

COMP: `/project1/lab/MIDI_mapper` (built with `H.cmd_midi_build`, handlers loaded in TD; the `td_midi_*` MCP tools
are not registered in the running server yet). No MIDI device and no MIDI ports on this Mac
(`/local/midi/midi_inputs` and `midi_outputs` empty), so the simulate path (raw bytes into `runtime.on_receive`) is
the test. Left parked (`allowCooking False`), 0 mappings, scratch target + probes removed.

## Items

| Item | Result |
|---|---|
| MIDI In DAT callback signature | **Confirmed + fixed.** 31550 template: `onReceiveMIDI(dat, rowIndex, message, channel, index, value, input, byteData)`; ours named the last arg `bytes`. `MIDI_CB` (handlers.py) now uses `byteData` (positional and keyword calls tested offline); the live `midi_cb` DAT text was updated from the file (no reload). |
| type of the bytes arg | Template annotation `byteData: bytes`; `decode_bytes` takes bytes/bytearray/list/hex. **A real message was not received** (no device): unverified live. |
| MIDI In DAT cooking when unviewed | **Confirmed:** with the tick's forced cook off, `midi_in` cooked 0 times in 68 frames (viewer on, pane on the COMP, no device); with `tick` on: 67 cooks / 66 frames, 0.03-0.07 ms. Whether a real message dirties an unviewed DAT is unverified; the forced cook stays. Warning "Could not open the MIDI interface" while no device exists (expected). |
| /local/midi/device | **Confirmed:** tableDAT, header `id indevice outdevice definition channel`, no device rows. `devices()` / `device_menu()` read `id` + `indevice`: match. Device menu falls back to `1 (no device in the MIDI Device Mapper)`. |
| Device / id par type | **Confirmed:** MIDI In DAT and MIDI Out CHOP `id` = **Str** par (`device` = DAT par `/local/midi/device`); our `Device` custom par = Menu, the expression `int(parent().par.Device.eval() or 1)` gives '1'. |
| MIDI Out CHOP send methods | **Confirmed present:** sendControl(ch, index, value), sendNoteOn(ch, index, value), sendNoteOff, sendPitchBend(ch, value 0..16384), sendPolyKeyPressure(ch, index, value), sendChannelPressure(ch, value), send(*bytes), sendExclusive, ... **Bug fixed:** with no device every send* raises `tdError('Cannot communicate with the MIDI device.')` (also with destination `file`); `runtime.send` let it escape, so a relative/toggle mapping's LED echo aborted the rest of the event (other mappings, event log) and `poll` errored every 10 Hz. Now each send is guarded; one `last_error` per new error ("feedback not sent: ..."). |
| raw value scaling | Pars set at build and read back: `onebased False`, `controlnorm off`, `notenorm off`, `controlformat 7bit`, `cookalways True`. Per TD's docstrings this means raw 0..127 (pitch bend 0..16384). `feedback_messages`: cc 0/0.5/1 -> 0/64/127; cc14 0.5 -> MSB 64 + LSB(n+32) 0, 1 -> 127/127; pitch bend 0.5 -> 8192, 1 -> 16383; note on -> 127. Bytes on the wire: unverified (no device). |
| ui.rolloverPar (hover learn) | **Present** (also rolloverOp, rolloverPage, rolloverPanel, rolloverParGroup); `None` when the mouse is not over a par. Hover learn with no par under the mouse stays `listening` with note "no parameter under the mouse". A real hover was not done (it would need the user's mouse). |
| Parameter Execute signature | **Confirmed:** 31550 template `onValueChange(par, prev)`, `onValuesChanged(changes)`, `onPulse(par)`, `onExpressionChange/onExportChange(par, val, prev)`, `onEnableChange`, `onModeChange`. Ours (`onPulse(par)`, `onValueChange(par, *args)`) match. Live: `Learn` pulse stopped a listening learn; `Activebank` 1 -> 2 wrote `active_bank` 2 to config. |
| List COMP editor callbacks | **Confirmed:** template has onInitCell/Row/Col/Table, onRollover, onSelect, onRadio, onFocus, `onEdit(comp, row, col, val)`; no onHoverGetAccept/onDropGetAccept (ours are unused extras). `attribs.editable` = int (clicks to edit) exists. `onSelect` is "called every frame from press to release" and its `start`/`end` are annotated `Coords`, so `if end:` may hold every frame: **fixed in the runtime** with a 0.5 s per-cell debounce (a held press on `del` could have deleted the following rows too). onEdit timing with a real typed edit: unverified (needs the mouse/keyboard). |
| reset refresh | **Confirmed:** `refresh_editor` sets rows/cols + pulses `reset`; the list showed the 9 mappings, then the empty hint after unmapping. |
| Window COMP pars | **Confirmed:** winop, title, size (automatic/fill/custom/exclusive), winw, winh, winopen, winclose; `Openeditor` opened `editor_window` (captured). |
| Text COMP pars | **Confirmed:** text, alignx, fontsize, font, fontsizeunits, fontcolorr/g/b, x/y/w/h. |
| menu writes via menuIndex | **Confirmed:** CC 127 -> Shape `d` (menuIndex 3), CC 50 -> `b` (1). |
| Pulse via .pulse() | **Confirmed:** note on -> write True -> the target's Parameter Execute counted 1 fire (it runs at the end of the frame); note off writes False, no pulse. |
| td_errors + layout | Only the expected "Could not open the MIDI interface" warning on `midi_in`; `td_layout check` ok (no intruders / unboxed / box overlaps). |
| Bug: event/binding headers | **Fixed:** a new Table DAT on 31550 holds one blank cell, so the build's `numRows == 0` check never wrote the events header (monitor rows came back keyed `''`). `runtime.ensure_header` (called by `init_config` at every build and by `_log_event`) puts the header on top and drops blank rows; the test fake now starts tables with one blank cell like TD. |
| Stray `midi_in_callbacks` | A new MIDI In DAT makes its own callbacks DAT; ours is `midi_cb`. Removed live; handlers.py build removes it (offline, not reloaded). |

## Simulate round trip (scratch Float/Int/Menu/Toggle/Pulse pars in `_test_target` inside the COMP)
- Absolute CC7 -> Gain (0..10): 127 -> 10, 64 -> 5.039, 0 -> 0; channel 2 -> no match.
- Relative encoder (relative_2c, CC10 -> Int Count 0..4, default step 1/127): 1 tick no change, 38 ticks +1 (1 -> 2),
  25 ticks back (-> 1), one message of +5 ticks -> 2 (accumulator keeps sub-step motion). On Int pars one detent is
  1/127 of the range: a step of 1/span may suit encoders better (not changed: a design choice).
- 14-bit (cc14 #1 -> Fine 0..1): 8192 -> bytes `b0 01 40`, `b0 21 00` -> 0.50003; 16383 -> 1.0.
- Pickup takeover (CC12 -> Pick, set to 5.0 outside): 10 and 60 blocked ("m7: waiting for pickup"), 66 crosses
  0.5 -> 5.197, then 90 -> 7.087.
- Banks: CC20 in bank 1 -> Gain (m8) only; Activebank 2 -> CC20 -> Pick (m9) only, CC7 (bank 1) ignored;
  `cmd_midi_bank` lists banks [1, 2].
- Toggle (note 60): on -> True, note off -> no change, on -> False. Pulse (note 61): fired once.
- Feedback: the relative and toggle writes queued `cc 1 10 64` and `note 1 60 127`; sends raised (no device) ->
  writes kept, `last_error` "feedback not sent: tdError: Cannot communicate with the MIDI device.".
- Learn (par mode) on Fine: 5 CCs on ch3 #40 -> after the 0.5 s window `done`, "cc ch3 #40 (absolute)"; it replaced
  the existing mapping of that par (m3), by design of `learn_finish`.
- Cost: `on_frame` 0.055 ms (Python), `tick` 0.032 ms, `midi_in` forced cook 0.03-0.04 ms; project 59.5 fps.

## Editor look (zerror night palette, cheap)
`runtime.editor_init_table/row/cell` (copied into the COMP; handlers' list callbacks call them when present):
night background, black header row with surface-blue names, zebra rows, Open Sans 12, `LRN` orange, `x` red, label
left-justified, target right-justified (the op.par end stays visible), widths 970 px so all 14 columns fit.
Live via an updated `list_cb` text. Capture: session scratchpad `midi_editor2.png`.

## Needs td_reload later (handlers.py edited + tested offline, NOT reloaded)
- `MIDI_CB`: last arg `byteData`.
- `MIDI_LIST_CB`: routes onInitTable/Row/Cell to the runtime's editor_init_* (falls back to the old look).
- `_midi_build_ops`: removes the auto-made `midi_in_callbacks` DAT.
The live COMP already has the first two texts (set from the file); a rebuild before the reload would put the old
`midi_cb` / `list_cb` texts back.
