# AS - SpotifyBridge (real-time Spotify lyrics in TD) + local-only alternative (26 Oct 2026)

Research only. Nothing loaded into TD, nothing run, nothing installed, nobody signed in to. Files: `research_src/spotifybridge_74390/`
(`page.html` = the Derivative asset page, `patreon.html` = the Cloudflare "Just a moment" 403 stub, `lrclib_README.md` = LRCLIB server repo README,
`lrclib_api.json` = one public `/api/search?q=hello` response, no login, showing the field names).

## 1. What it is (from the asset page only)
- Derivative community asset 74390, posted 18 Apr 2026, ~685 views. Author "Lostfound" (Instagram merderbil). Built with Gemini, author says no prior Python.
  Inspired by an Instagram tool by sante.isaac. Version not stated (Patreon slug says "spotifybridge-v2").
- A `.tox` ("SpotifyBridge Container") that shows lyrics for whatever is playing on the user's Spotify account. Tabs: **Spotify Setup**, **Karaoke Control** (Lyric Status).
- OS: author says tested on a Windows PC and a MacBook, no problems. TD build: not stated. Licence: **not stated**.
- **Download is on Patreon only** (patreon.com/merderbil, post "spotifybridge-v2"). Cloudflare 403 for a plain fetch; not bypassed. **No GitHub, forum or video link exists.**
  So the .tox was NOT obtained, nothing could be inspected, and everything below about internals is inferred from the page text and marked UNVERIFIED.

## 2. How it works (page text + inference)
| Question | Answer |
|---|---|
| Now-playing / position | **Spotify Web API with OAuth** (Authorization Code flow): user creates an app in developer.spotify.com/dashboard, enables Web API, Redirect URI `http://127.0.0.1:8888/callback`, pastes Client ID + Client Secret, clicks "Authenticate with Spotify" (browser opens). Plays from any device ("a phone works"), so it polls the account's playback state (likely `GET /v1/me/player/currently-playing`, UNVERIFIED) - not AppleScript, no desktop helper. |
| Premium | Required by the page (and since 2025 Spotify dev-mode apps need the owner on Premium). New subscription may need hours. |
| Lyrics source | **LRCLIB** (lrclib.net, named on the page: "the lyrics database (LRCLIB) may not have them"). Not Spotify's internal lyrics endpoint, not Musixmatch. Synced LRC lines matched by track/artist/duration (UNVERIFIED which call). |
| Delivery to TD | Python inside the .tox (almost certainly `requests`/`urllib` or `spotipy` in a thread or `lfo1`-driven callback - page says the token renews "while the project is open and lfo1 is ticking", so a CHOP-triggered Python poll). No OSC/WebSocket. pip packages: UNVERIFIED. |
| Outputs | Only "Lyric Status" is documented. Channel/DAT names for current line, next line, progress: **UNVERIFIED**. |
| Credentials | Client ID/Secret typed into custom pars (so saved in the .toe/.tox as plain text unless cleared). OAuth token `.cache` file (spotipy-style name) stored **inside the project via VFS**; ~1 h expiry, auto-refresh; "Disconnect / Reset" deletes it. Middle-click the COMP to see it. |
| Ports | Needs a short-lived local HTTP listener on **127.0.0.1:8888** for the OAuth callback (inferred from the redirect URI). |

## 3. Official / ToS notes (not a blocker)
- Spotify Web API OAuth is the **official** route for now-playing/position. Fine for personal use; dev-mode apps are limited to allow-listed users.
- LRCLIB is a free community service (open server code, Rust/Axum/SQLite; public API, no key). Lyrics there are user-contributed and the copyright status of the texts is the contributors' problem: fine for a private rig, think twice before shipping/redistributing a lyrics cache or showing licensed lyrics publicly beyond what the venue/show already clears.
- Spotify's internal "lyrics" endpoint (the Musixmatch-backed one used by the app, via sp_dc cookie) is **not used here** and would be ToS-violating; do not use it.

## 4. Audit (what we could / could not verify)
| Check | Result |
|---|---|
| Network endpoints | Expected: accounts.spotify.com (auth/token), api.spotify.com, lrclib.net. **UNVERIFIED** - closed behind Patreon; could be more (e.g. telemetry). |
| Listening ports | 127.0.0.1:8888 during auth (expected). Others UNVERIFIED. |
| subprocess / eval / pip | UNVERIFIED. A Gemini-written .tox that runs browser-open and an HTTP server very likely uses `webbrowser`, `http.server`, and either bundled or pip-installed `spotipy`/`requests`. |
| Secrets | Client Secret in pars + token blob in VFS: **never save a project containing them to a shared location / repo**; reset before saving. |
| Licence | None stated -> treat as all rights reserved; cannot redistribute or vendor. |
| Gate to inspect | Patreon account/download = user's login: **needs the user**. After download: `toeexpand` into a subfolder, grep for `http`, `subprocess`, `eval`, `exec`, `pip`, `socket`, `os.system`; only then consider loading in a scratch project. |

## 5. Verdict
**Not adopted; file not obtained.** It solves a real need (now-playing + synced line) but: Patreon-gated, no licence, unauditable, needs Spotify Premium + developer app + OAuth secrets in the project, and only a Web-API poll (1 s-ish granularity needs interpolation anyway). For our per-track lyric designs we already own the timed lyrics, so the **local alternative (section 7) is better for the show**. SpotifyBridge is only worth it for a "play anything from the phone" VJ mode, and then only after the user fetches it and we audit.

## 6. Gated setup recipe (needs the user's OK + credentials) - if the user wants the real thing
1. User downloads the .tox from the Patreon post (their login) into a new folder; we `toeexpand` + grep per section 4. Stop on any surprise.
2. User OK to create a Spotify developer app (their Premium account), Redirect URI `http://127.0.0.1:8888/callback`; user types Client ID/Secret themselves (we never see/store them).
3. Scratch project (not the home .toe), load .tox, click Authenticate (browser, user logs in). Confirm Lyric Status, map its outputs to a `LK_typecore.Word` via a CHOP/DAT export or a tiny Execute DAT.
4. Before saving: Disconnect / Reset, blank the secret pars. Check with a TD/Rosetta test that the 8888 listener closes.
Cost: network = Spotify + LRCLIB only; every step is user-approved.

## 7. Local-only alternative (no Spotify API, no login, no network at show time)
Idea: Spotify desktop app reports state via AppleScript; lyrics come from local `.lrc` (or our own timed files); TD parses and drives a Text TOP / `LK_typecore.Word`.

**Now-playing (macOS, Spotify desktop app scriptable):**
```
osascript -e 'tell application "Spotify" to if player state is playing then (name of current track) & "|" & (artist of current track) & "|" & (player position) & "|" & (duration of current track) & "|" & (id of current track)'
```
`player position` = seconds (float), `duration` in ms, `id` = spotify:track:... URI. Sandbox note: TD needs macOS Automation permission for Spotify (prompt on first call - user OK). Rosetta TD can run `osascript`; use `subprocess.run([...], capture_output=True, timeout=1)` from a **thread** (`td.run`/threading) polling ~4 Hz, never in the cook thread. Interpolate between polls with `absTime` so lines switch on time (resync when |drift| > 0.3 s). Seek and pause handled by the polled position/state.

**Lyrics files:** `lyrics/<spotify_id or Artist - Title>.lrc` (`[mm:ss.xx]line`). Source: our own per-track timed lyric files (preferred, already one script per line, Urdu first) or LRCLIB downloaded **ahead of time** by the user/us into the folder (`GET https://lrclib.net/api/get?track_name=&artist_name=&duration=` -> `syncedLyrics`; fields seen live: id, trackName, artistName, albumName, duration (seconds), instrumental, plainLyrics, syncedLyrics). Offline at the show.

**TD ops (about 8):**
1. `Text DAT`/`Table DAT` `lrc_table` - parsed [time, line] rows (Python regex `\[(\d+):(\d+\.\d+)\](.*)`; sort by time; UTF-8 for Urdu).
2. `Script DAT` or `Execute DAT` `poll` - thread running osascript, writes to a `Storage` dict (track id, state, position, stamp).
3. `Constant`/`Script CHOP` `clock` - interpolated position = pos + (absTime.seconds - stamp) while playing; channels: `pos`, `playing`, `line_idx`, `line_progress` (0-1 between line start and next start), `next_in`.
4. `Table DAT` lookup (`lookup` DAT / Python bisect) -> `cur_line`, `next_line` Text DATs.
5. `Text TOP` bound to `cur_line` (Urdu: RTL shaping via a font + `text` par; check shaping in TD per Q_live_typography - HarfBuzz not in TD, pre-shape if needed) or `op('LK_typecore').par.Word = cur_line` from the line-change callback (CHOP Execute on `line_idx`).
6. Optional `Lag CHOP`/`Filter` on `line_progress` for animated in/out.
Track change: `poll` loads the matching `.lrc` into `lrc_table`; missing file -> blank + status DAT "no lyrics".

**Time to build:** ~1-2 h with the td_* tools in a scratch COMP; risks: Automation permission prompt, Urdu shaping in Text TOP, position jitter (1 Hz Spotify updates -> interpolate), Spotify not scriptable if only the web player is used. No port, no credentials, no pip. Needs the user's OK before building (Spotify automation prompt, then folder of lrc files).

## 8. Open questions for the user
1. Is "any song from my phone" needed, or only the show's known tracks (-> local alternative)?
2. OK to fetch the Patreon file yourself for an audit, or skip it?
3. LRC source for the show: our own timed files, or pre-fetch LRCLIB for the setlist?
4. OK for TD to call `osascript` (Automation permission for Spotify)?
