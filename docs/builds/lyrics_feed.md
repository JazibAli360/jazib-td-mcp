# lyrics_feed: LY_lyrics_feed synced lyrics feed (26 Oct 2026, TD 2025.31550)

`/project1/lab/LY_lyrics_feed`. Synced lyrics from local `.lrc` files (UTF-8, Urdu included), clocked by the
Spotify desktop app (osascript, background thread), a manual clock, or a CHOP. Spec/recipe:
`docs/research/AS_spotifybridge_lyrics.md` section 7 (local-only alternative; our own clean-room design). SpotifyBridge
(Derivative asset 74390, Patreon-only, no licence stated) was not obtained or used. No network, no credentials, no pip.

Out: `out1` TOP (1080x1920 preview: current line, next line, line progress bar), `out2` CHOP (`pos length playing
line_idx line_count line_progress next_in song_progress line_start line_changed has_lyrics source poll_ms resyncs`),
`out3` DAT (key/value: `cur next prev cur_rtl next_rtl idx count source status title artist track_id lrc_file
poll_state poll_error`). In: `in1` CHOP (optional clock: song seconds on channel `Chopchan`, else the first).
Inside: `cur_line` / `next_line` Text DATs, `lrc_table` (idx, time, line).

## Build
```python
ns = dict(globals()); exec(open('<repo>/builders/lyrics_feed.py').read(), ns); ns['build']('/project1/lab')
```
Idempotent, T-70 safe (closes its own controls_window, zkit panel refreshed in place, `_sd` = safe_destroy, never moves
the pane). Logic: `builders/lyrics_feed_logic.py` (copied into `ly_logic`), 23 offline tests:
`python3 -I -m unittest discover -s test -p 'test_lyrics_feed.py'`. Test lyrics: `test/fixtures/lyrics/` (our own
lines, English + Urdu + Roman Urdu, a two-stamp chorus, enhanced word stamps, `[length:]`).

## Parameters (zkit panel: Source, Manual, Look, Colours; pulse `Opencontrols`)
| Page | Pars |
|---|---|
| Source | Source (auto = Spotify when it reports a track, else CHOP when wired, else manual / spotify / manual / chop), Folder (`.lrc` folder, default the test folder), Lrcfile (force one file; blank = match the track, or the first file in manual/chop), Offset s (+ = lines earlier), Pollhz, Drift (resync above s), Chopchan, Rescan, Reload |
| Manual | Play, Rate (any value; negative runs back), Loop, Seekto + Seek, Restart |
| Look | Resw/Resh, Font (Latin), Urdufont, Textmethod (auto = bitmap for RTL lines), Cursize, Nextsize, Margin, Gap, Shownext, Showbar, Barh, Transparent |
| Colours | Curcolour, Nextcolour, Barcolour, Bg |

Track -> file match (first hit wins): `<spotify id>.lrc`, `Artist - Title.lrc` (loose: case, punctuation,
"(feat ..)", " - Remastered" dropped), first artist only, title only, `[ar:]`/`[ti:]` tags inside the files. A missing
file triggers one folder rescan on that track change; status says "no lyrics for ...".

## How it works
- `poller` (Text DAT module): a daemon thread runs `/usr/bin/osascript` (`if application "Spotify" is running` first,
  so it never launches Spotify) at Pollhz, parses with the logic module's plain functions, stores the reply under a
  lock. It touches no TD op. The engine's `ensure()` every cook is a heartbeat; 3 s without one (COMP parked or deleted,
  Source manual) and the thread ends. First call waits up to 60 s for macOS's one-time Automation prompt.
- `engine` (Script CHOP, force-cooked each frame by `ly_tick`): picks the clock, interpolates Spotify between polls
  (stamp = osascript mid-point; resync on track change, play/pause or |drift| > Drift), looks up the line (bisect),
  writes channels every frame and the DATs only when something changed.
- Preview (perf 28 Oct, T-228): per line slot a fixed Latin Text TOP (`txt_cur` / `txt_next`) and a fixed Urdu one
  (`txt_cur_ur` / `txt_next_ur`, Urdufont + bitmap + right-to-left) feed a Switch (`sel_cur` / `sel_next`, index =
  cur_rtl / next_rtl). A Text TOP never changes font at a line change (a bitmap face nobody holds reloads at ~130-430
  ms). The poller spawns osascript with `close_fds=False` (posix_spawn; fork stalled TD ~120 ms per poll). b3: 60 fps,
  max frame 17.5-18.8 ms over 30 s with line changes; out1 bit-exact vs the old build (10 states incl. wrapped Urdu).
- State: plain dicts in a process-wide registry module keyed by the COMP path (not op storage, T-67), because TD
  rebuilds a DAT's `.module` when it is re-cooked.

## Verified live (26 Oct, 31550)
- Manual: Seek 5.6 -> line 2 (Urdu), line_progress 0.0286 (= 0.1/3.5), next_in 3.4, cur_rtl 1, txt_cur font Noto
  Nastaliq Urdu + righttoleft, next line Open Sans. Rate 2 for 2.133 s: pos 9.867 (expected 9.865), line 3.
- CHOP clock (constant 26.6 s into the engine, then removed): source 2, Urdu chorus line; Offset 0.5 -> pos 27.1,
  line 8, progress 0.1714 (= 0.6/3.5).
- Bar: 394 px at progress 0.4286 of 920 px (x 80..474).
- Spotify: thread runs, osascript started; **the macOS Automation prompt was showing (UserNotificationCenter window)
  and waits for the user**, so every call timed out (60 s). Not yet verified: a real now-playing reply, interpolation
  against the real app, the track -> file match on a real track.
- Cost: engine 0.19 ms CPU/frame, preview overs ~0.5 ms GPU (cook-time readout), Text TOPs cook on line change only.
  Project fps with another agent's lane running: 49.5 / 48.75 with the COMP on vs 50.0 parked (no measurable cost).
- td_errors clean, layout check ok (no intruders / unboxed / box overlaps).

## Open
- User: answer the Automation prompt ("TouchDesigner wants to control Spotify" -> OK); then check a playing track.
  If it was denied: System Settings > Privacy & Security > Automation > TouchDesigner > Spotify.
- Urdu lines need a native reader's check (rendering judged by eye).
