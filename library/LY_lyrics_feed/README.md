# LY_lyrics_feed

> lyrics_feed: LY_lyrics_feed synced lyrics feed (26 Oct 2026, TD 2025.31550)

v0.1.1 - TD 2025.31550 - exported 2026-10-29 00:09:01 from `/project1/lab/LY_lyrics_feed`

`/project1/lab/LY_lyrics_feed`. Synced lyrics from local `.lrc` files (UTF-8, Urdu included), clocked by the
Spotify desktop app (osascript, background thread), a manual clock, or a CHOP. Spec/recipe:
`docs/research/AS_spotifybridge_lyrics.md` section 7 (local-only alternative; our own clean-room design). SpotifyBridge
(Derivative asset 74390, Patreon-only, no licence stated) was not obtained or used. No network, no credentials, no pip.

Out: `out1` TOP (1080x1920 preview: current line, next line, line progress bar), `out2` CHOP (`pos length playing
line_idx line_count line_progress next_in song_progress line_start line_changed has_lyrics source poll_ms resyncs`),
`out3` DAT (key/value: `cur next prev cur_rtl next_rtl idx count source status title artist track_id lrc_file
poll_state poll_error`). In: `in1` CHOP (optional clock: song seconds on channel `Chopchan`, else the first).
Inside: `cur_line` / `next_line` Text DATs, `lrc_table` (idx, time, line).

Build doc: `docs/builds/lyrics_feed.md`

## Inputs / outputs

- in `in1` (inCHOP)
- out `out1` (outTOP) 1080x1920
- out `out2` (outCHOP)
- out `out3` (outDAT)

## Custom parameters

### Source

| name | label | style | default | value |
|---|---|---|---|---|
| Source | Source | Menu | auto | auto |
| Folder | LRC folder | Folder | ~/Documents/StageLab_PrismFest/jazib-td-mcp/test/fixtures/lyrics | ~/Documents/StageLab_PrismFest/jazib-td-mcp/test/fixtures/lyrics |
| Lrcfile | Force .lrc (blank = match) | File |  |  |
| Offset | Offset s (+ = earlier) | Float | 0.0 | 0.0 |
| Pollhz | Spotify polls / s | Float | 4.0 | 4.0 |
| Drift | Resync above s | Float | 0.3 | 0.3 |
| Chopchan | CHOP channel (s) | Str | pos | pos |
| Rescan | Rescan folder | Pulse | False | False |
| Reload | Reload file | Pulse | False | False |

### Manual

| name | label | style | default | value |
|---|---|---|---|---|
| Play | Play | Toggle | True | True |
| Rate | Rate | Float | 1.0 | 1.0 |
| Loop | Loop | Toggle | True | True |
| Seekto | Seek to s | Float | 0.0 | 7.0 |
| Seek | Seek | Pulse | False | False |
| Restart | Restart | Pulse | False | False |

### Look

| name | label | style | default | value |
|---|---|---|---|---|
| Resw | Width | Int | 1080 | 1080 |
| Resh | Height | Int | 1920 | 1920 |
| Font | Font (Latin) | Str | Open Sans | Open Sans |
| Urdufont | Font (Urdu / RTL) | Str | Noto Nastaliq Urdu | Noto Nastaliq Urdu |
| Cursize | Line px | Float | 96.0 | 96.0 |
| Nextsize | Next line px | Float | 54.0 | 54.0 |
| Margin | Side margin px | Float | 80.0 | 80.0 |
| Gap | Line gap px | Float | 140.0 | 140.0 |
| Shownext | Show next line | Toggle | True | True |
| Showbar | Line progress bar | Toggle | True | True |
| Barh | Bar px | Float | 8.0 | 8.0 |
| Transparent | Transparent bg | Toggle | False | False |
| Textmethod | Textmethod | Menu | auto | auto |

### Colours

| name | label | style | default | value |
|---|---|---|---|---|
| Curcolourr | Line | RGBA | 1.0 | 1.0 |
| Curcolourg | Line | RGBA | 1.0 | 1.0 |
| Curcolourb | Line | RGBA | 1.0 | 1.0 |
| Nextcolourr | Next line | RGBA | 0.55 | 0.55 |
| Nextcolourg | Next line | RGBA | 0.55 | 0.55 |
| Nextcolourb | Next line | RGBA | 0.6 | 0.6 |
| Barcolourr | Bar | RGBA | 0.95 | 0.95 |
| Barcolourg | Bar | RGBA | 0.75 | 0.75 |
| Barcolourb | Bar | RGBA | 0.2 | 0.2 |
| Bgr | Background | RGBA | 0.0 | 0.0 |
| Bgg | Background | RGBA | 0.0 | 0.0 |
| Bgb | Background | RGBA | 0.0 | 0.0 |

### Zkit

| name | label | style | default | value |
|---|---|---|---|---|
| Opencontrols | Open controls | Pulse | False | False |
| Zktheme | Theme | Menu | night | night |
| Zkd | Knob size px | Int | 56 | 56 |
| Zkcols | Columns | Int | 8 | 8 |
| Zkrandamount | Random amount | Float | 0.5 | 0.5 |
| Zkrandomize | Randomize | Pulse | False | False |
| Zkshowall | Show deleted knobs | Pulse | False | False |
| Zkrebuild | Rebuild panel | Pulse | False | False |
| Zkmaxh | Max height px (0 = fit screen) | Int | 0 | 0 |
| Zkm1 | Size | Float | 0.0 | 0.43 |
| Zkm2 | Space | Float | 0.0 | 0.43 |

## Perf

cook 13.993 ms (CPU 13.993 / GPU 0.794) summed over the 7 ops that cooked in the last frame at export (30 frames after un-park, Out TOP force-cooked each frame; indicative)

## Files outside the repo / TD install (or missing)

- none

## Load

`td_library_load {"name": "LY_lyrics_feed", "parent": "/project1/lab"}` (lands parked)
