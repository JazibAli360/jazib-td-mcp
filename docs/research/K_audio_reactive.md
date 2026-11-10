# K - Audio-reactive and music-synced visuals for PF26 (research, 16 Oct 2026)

Topic K of the TD research set. Research only: no TouchDesigner, Arena, Syphon or audio device was touched, nothing was
downloaded or installed, no generation. Guardrails: `BRIEF.md`. Builds on `td-port/audio_analysis/README.md`
(JZBA_AudioAnalysis, C++ engine) and does not repeat `A_td_2025_howto.md` section 5, `ops/CHOP.md` section 2,
`E_live_rig.md` section 5.4 (OSC, Link, tap tempo) or `C_pf26_fit.md` section 4.

Evidence labels: every claim has a URL; "snippet only" = I saw it in a search result but could not open the page;
**UNVERIFIED** = from memory, older builds, or an inference; "design" = my own arithmetic or proposal, not a source.
The session's web-search budget ran out part-way (about two thirds through), so a few planned lookups were not done;
they are listed under open questions.

## 0. Summary

1. **The analyzer is the right engine; what's missing is the feed and the look-side rules.** JZBA already gives
   kick/snare/hat/onset pulses, a beat-locked `phase`, bars, sections and drivers at about 75 us per cook. It has never
   been run on live input (its own README "Not verified"). The biggest PF26 risk is not the algorithm, it is **what
   audio reaches it** (section 2.2).
2. **Feed, ranked:** (1) a balanced post-fader stereo matrix/aux from FOH into a class-compliant interface; (2) plus 2 to 4
   group sends (drums, bass, vocal) if FOH agrees - these are the only *real* stems, zero latency, no ML; (3) ambient mic
   only as a last resort. Needs the FOH engineer's agreement in advance (sources in 2.2).
3. **Neural stem separation is not usable live in this setup.** The one low-latency research model (HS-TasNet, 23 ms,
   SDR 4.65) has no public code that I found; Demucs is archived and batch-oriented (ONNX card: 1.6 s latency on an M4 Pro
   CPU); the commercial real-time plug-in reports 245 ms. Pseudo-stems from the analyzer's band/flux detectors cost
   microseconds and already exist (2.5).
4. **Tempo/phase sync:** for live bands with unknown tempo, audio analysis is the only source that needs nobody's
   cooperation. Link, MIDI clock and LTC are good *if a band runs Ableton/backing tracks* (open question). Arena has native
   SMPTE input (clips without audio) and Pioneer sync (CDJ models only); it has **no audio BPM detection** per a 2020 staff
   statement (UNVERIFIED for 7.23.2). TD's Link CHOP is listen-only.
5. **Latency is a seating-distance question.** Sound travels 2.9 ms/m; the visual chain is probably 100 to 200 ms (design
   estimate, nothing measured). Picture-early is the more tolerable error (ITU numbers, 2.1). Measure with a phone in
   slow motion on the wall plus speaker; use `Lookahead` only for the predicted beat grid, never for kick/snare hits.
6. **Flash safety must be a hard governor on the TD output, not a property of the analyzer.** The analyzer's own
   minimum pulse spacing is 0.1 s (10/s), above the WCAG limit of 3 flashes/s. A whole-wall flash can never use the "small
   area" exception (the wall is about 53 degrees wide at 40 m). Spectrum-bar displays are also a stripe-pattern hazard (2.9).
7. **Avoiding "everything pulses to the kick":** give each look *one* primary reactive channel, drive motion from the
   continuous `phase`/`bar_phase` clock rather than from pulses, change *states* on `every4/8/16`, gate reaction depth by
   section (`breakdown/build/drop`), and fall back to free-running motion when `confidence` is low (2.7, 2.8).
8. **Recommended build order** is in section 4; nothing there is built, and several steps need the user's go-ahead.

## 1. Findings table

| # | Item | Verdict for PF26 | Cost / licence | Main evidence |
|---|---|---|---|---|
| K1 | FOH matrix/aux stereo line feed | **Do this** | Interface hardware (ask FOH); no licence | [ProSoundWeb aux vs matrix](https://www.prosoundweb.com/the-right-signal-deciding-on-an-aux-send-versus-a-matrix-to-send-to-video-on-corporate-gigs) (snippet only), [HeavyM line vs room mic](https://www.heavym.net/how-to-sync-visuals-with-music-audio-reactive-projection-mapping-made-simple/) (snippet only) |
| K2 | Group/channel sends = real stems (kick, drums, bass, vox) | **Do if FOH agrees** | Multi-channel interface; free | [LCD Soundsystem at Coachella, VDMX](https://vdmx.vidvox.net/blog/nev-bull-lcd-soundsystem-coachella): 64 audio + 12 drum-trigger channels |
| K3 | Ambient microphone | Last resort / rehearsal only | Mic; free | Same HeavyM line; PA level and crowd make it a poor feed (design) |
| K4 | TD `audiodeviceinCHOP` (CoreAudio) | Required path; test early | Free | [Audio Device In CHOP](https://docs.derivative.ca/Audio_Device_In_CHOP) (edited 24 Jun 2022): larger Buffer Length = more latency |
| K5 | JZBA_AudioAnalysis (C++ engine) as the analyzer | **Keep** | In-house | `td-port/audio_analysis/README.md` |
| K6 | BeatNet online beat/downbeat (CRNN + particle filter) | Not live; offline reference at most | CC-BY-4.0 code; needs madmom + PyAudio + PyTorch | [BeatNet repo](https://github.com/mjhydri/BeatNet), [paper](https://arxiv.org/abs/2108.03576) |
| K7 | Beat This! (ISMIR 2024), madmom | Offline reference only | Beat This! MIT; madmom code BSD but **models CC BY-NC-SA** | [Beat This!](https://github.com/CPJKU/beat_this), [madmom](https://github.com/CPJKU/madmom) |
| K8 | Neural stem separation live | **Skip** | HS-TasNet no code found; Demucs MIT, archived; PEEL STEMS 2 commercial | [HS-TasNet](https://arxiv.org/abs/2402.17701), [Demucs](https://github.com/facebookresearch/demucs), [ONNX card](https://huggingface.co/adowu/htdemucs-onnx), [PEEL STEMS 2](https://mixdownmag.com.au/news/zplane-cuts-stem-separation-latency-by-49-with-peel-stems-2/) |
| K9 | Ableton Link CHOP | Only if a band laptop runs Live | Free in TD; Link is GPLv2+/proprietary | [Link CHOP](https://docs.derivative.ca/Ableton_Link_CHOP), [forum](https://forum.derivative.ca/t/ableton-link-stop-start-sync-enable/219586), [Link repo](https://github.com/Ableton/link) |
| K10 | MIDI clock into TD (MIDI In CHOP) | Fallback if a band can send it | Free | [MIDI In CHOP](https://derivative.ca/UserGuide/MIDI_In_CHOP), [Mac bug thread](https://forum.derivative.ca/t/poor-midi-timing-behaviour-on-mac/145515) |
| K11 | LTC: TD `ltcinCHOP`, Arena SMPTE input | **Best for backing-track acts and timed reveals** | Free | [LTC In CHOP](https://docs.derivative.ca/LTC_In_CHOP), [Arena SMPTE](https://resolume.com/support/en/smpte) |
| K12 | Pioneer Pro DJ Link in Arena | Only if a DJ with CDJ-3000/2000NXS2 appears | Arena only | [Sync to Pioneer](https://resolume.com/support/en/sync-to-pioneer-dj-players) |
| K13 | OSC: TD to Arena (BPM/levels); console meters via OSC | Secondary; addresses must be learned | Free | `E_live_rig.md` 5.4; console OSC: UNVERIFIED |
| K14 | Arena built-in Audio FFT (3 bands, Gain/Fall) | Optional for Arena-native layers | Included | [Parameter animation](https://resolume.com/support/en/parameter-animation) |
| K15 | Envelope design (asymmetric follower, 1 Euro filter, Trigger CHOP, hysteresis) | **Apply** | Free | [1 Euro](https://gery.casiez.net/1euro/), [Trigger CHOP](https://docs.derivative.ca/Trigger_CHOP), musicdsp (2.6) |
| K16 | Flash governor on the TD output | **Build first** | Small GPU cost (design) | [WCAG 2.2 Understanding 2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html) |
| K17 | Latency calibration test | **Do at rehearsal** | A phone | ITU numbers via [TV Technology](https://www.tvtechnology.com/opinions/av-synchronization-how-bad-is-bad) |

## 2. Details

### 2.1 Where the milliseconds go (and why it matters for seating)

Facts:
- Speed of sound is 343 m/s at 20 C and about 349 m/s at 30 C ([Wikipedia](https://en.wikipedia.org/wiki/Speed_of_sound)).
  Karachi in October is warm, so use about 2.87 ms per metre: 20 m = 57 ms, 40 m = 115 ms, 60 m = 172 ms (design arithmetic).
- Audio-to-picture tolerance, ITU-R BT.1359-1 as tabulated by [TV Technology](https://www.tvtechnology.com/opinions/av-synchronization-how-bad-is-bad)
  (sign: plus = audio leads picture, inferred by the article's film example): detectable +45 / -125 ms, acceptable +90 / -185 ms. So **picture early
  is far more tolerable than sound early.** These are speech (newsreader) results; the [arXiv sports study](https://arxiv.org/pdf/2212.01686)
  notes the limits to that basis. Tolerance for music transients (a snare hit against a flash): UNVERIFIED, probably tighter.
- LED processor: Brompton data sheet figures (snippet only, [PDF](https://globaltrendpro.com/wp-content/uploads/2022/07/Brompton-SX40-Data-Sheet.pdf)
  returned 404 when opened): about 2 frames end to end, 1 frame in Ultra Low Latency, which needs source support. Which processor R02
  uses is a vendor question (`STAGE.md` RFI08 already asks for latency).
- Analyzer detection lag: `LATENCY_WINDOWS = 0.36` FFT windows of 2048 samples at 48 kHz = **15.4 ms** (constant in
  `td-port/audio_analysis/analyzer.py`, measured on synthetic kicks only).
- TD frame at 30 fps = 33.3 ms (`E_live_rig.md` fixes 30 fps). Syphon plus Arena composition: "probably 1 to 2 frames
  (unverified)" in `E_live_rig.md` 4.1; never measured.

Design estimate (not a measurement): interface buffer (a few ms, size not measured) + 15 ms + one TD frame + one to two
frames Syphon/Arena + about two frames LED = **roughly 100 to 200 ms** from console to light. The seat where picture and sound
line up is at d = L x c: 100 ms is about 35 m, 150 ms about 52 m, 200 ms about 70 m. Front rows see the wall *late*, the
back sees it *early*. Early is the forgiving side, so err toward a bit less compensation.

How to use it:
- **Beat grid:** the analyzer's `phase`/`beat` are a clock locked to the music, so `Lookahead` (seconds) can fire them
  early. Set it from the measured chain latency minus the acoustic delay at the target seat (FOH area is the natural target).
- **Hits (kick/snare/hat/onset) cannot be early.** They are detected after the sound; only decay shapes hide the lag.
  So never build a look whose impact depends on a kick landing *on* the picture frame.
- **Calibrate:** film the wall and a speaker (or a clap near the FOH mic) with a phone at 240 fps slow motion; step through
  frames; the difference between flash and clap, plus acoustic travel from the camera position, is the chain latency. Repeat
  at the FOH position at the real PA level. (Method is design; nothing in the sources prescribes it.)
- Arena's SMPTE input has a frame-based delay compensation that "a negative value can help restore lip sync on large stages"
  ([Arena SMPTE](https://resolume.com/support/en/smpte)); that is for timecoded clips, not TD.

### 2.2 Getting a clean audio feed at a festival

What the sources say:
- Practising engineers rank the ways to tap a mix: a mic splitter at the stage best, channel direct outs if pre-fader,
  inserts only if desperate; post-fader direct outs repeat every FOH move in your signal; and the venue/FOH must agree in
  advance ([Gearspace thread](https://gearspace.com/threads/live-sound-recording.178846/), snippet only; forum-grade).
- For video/stream feeds a console **matrix** takes a "mix of mixes" from subgroups/auxes/main, and an engineer reported a video crew asking for an aux independent
  of the house mix, while the engineer argued for a matrix off the main L/R; limiters near -1 dB protect the feed
  ([ProSoundWeb](https://www.prosoundweb.com/the-right-signal-deciding-on-an-aux-send-versus-a-matrix-to-send-to-video-on-corporate-gigs) and
  [Live Design](https://www.livedesignonline.com/gear/broadcast-audio-for-webcasting-while-also-mixing-foh), both snippet only: HTTP 403 when opened).
- A club-level recommendation: take the DJ mixer's booth/record out into a USB interface; a direct line feed beats a room
  mic ([HeavyM](https://www.heavym.net/how-to-sync-visuals-with-music-audio-reactive-projection-mapping-made-simple/), snippet only).
- Precedent for per-instrument feeds: LCD Soundsystem at Coachella 2016 gave VDMX **64 audio channels over MADI plus 12 drum-trigger
  channels**, run with no timecode, "set to run autonomously" on live triggers ([VDMX blog, 28 Apr 2016](https://vdmx.vidvox.net/blog/nev-bull-lcd-soundsystem-coachella)).
- Feed Me's rig ignored audio analysis for sync and used Max for Live OSC events from the performer's Live set
  ([CDM, 29 Aug 2012](https://cdm.link/playing-live-from-a-giant-toothy-monster-mouth-behind-the-scenes-with-feed-me/)).

Ranking for PF26:

| Rank | Feed | Why / catch |
|---|---|---|
| 1 | **Balanced stereo post-fader matrix (or aux) from FOH** into a class-compliant multi-input USB interface at 48 kHz | Clean, level-stable, follows the mix; ask for a limiter on the send. Catch: if audience/ambient mics are in the main mix the analyzer hears crowd cheers; ask for the matrix without them. |
| 2 | **2 to 4 group sends** (drums, bass, vocal; or kick and snare direct) alongside | True stems with zero latency; drives per-instrument looks with no ML. Pre-fader keeps visuals independent of FOH fader moves (but also reacts to muted channels); post-fader follows the mix. Ask the engineer; unknown which suits. |
| 3 | Ambient mic | Hears PA, crowd and the venue; its own level changes with the PA; only for rehearsal or a dead-feed emergency. |
| fallback | `audiofileinCHOP` of a track | Already the plan in `ops/CHOP.md` 2 if the device fails. |

Hardware notes:
- Mac side: `audiodeviceinCHOP` driver CoreAudio, `inputs` picks channels, `bufferlength` trades latency
  ([doc](https://docs.derivative.ca/Audio_Device_In_CHOP)). macOS asks for microphone permission, and a March 2026 forum post
  found no source despite permissions (`ops/CHOP.md` 2): test the exact interface on the show Mac early. The analyzer was only
  verified at 48 kHz (README "Not verified"), so set the interface to 48 kHz.
- A loopback driver such as [BlackHole](https://existential.audio/blackhole/) (2/16/64-channel, Apple Silicon build) is for passing audio between Mac apps
  (e.g. a backing-track player into TD); licence terms were not on the page: UNVERIFIED. Not needed for a hardware feed.
- Dante/AES/MADI inputs: UNVERIFIED (the Audinate page returned 403); ask FOH what the desk can output before buying anything.
- **Both machines**: `RUNTIME.md` plans a mirror machine; it needs the same feed (splitter or second interface path). Open question.
- Console OSC meter streams (some digital desks publish channel meters over OSC, which would allow per-channel "stems"
  with no audio cable): UNVERIFIED for this desk and not researched; it depends on what FOH brings.

### 2.3 Tempo and phase sync sources

What each can and cannot do (all TD-side facts are doc statements; none tested in 2025.31550):

**Ableton Link** - [TD Link CHOP](https://docs.derivative.ca/Ableton_Link_CHOP) (edited 24 Nov 2023): outputs ramp/pulse/sine/count/bar/beat/
sixteenths/phase/beats/tempo and status (`numpeers, linked, synced`). Tempo is output only; per a Derivative forum thread (Oct to Dec 2021) it ignores
start/stop from peers, cannot push tempo back, and is not tied to the playbar; use Info CHOP `ableton_is_playing`
([thread](https://forum.derivative.ca/t/ableton-link-stop-start-sync-enable/219586)). Link guarantees tempo, beat and phase
alignment (quantum), not independent timelines or simultaneous starts ([Link concepts](https://ableton.github.io/link/)); output
latency must be added by each implementer ([repo](https://github.com/Ableton/link)). Arena also has Link; while it is on, **BPM Resync and
Pause are disabled** ([Arena Link](https://resolume.com/support/en/link), v6 page). Needs the band's laptop on the same network and Link enabled: Wi-Fi robustness,
firewall, and Rosetta TD are UNVERIFIED. Link licence is GPLv2+ or proprietary (not our concern: we use TD's CHOP).

**MIDI clock** - 24 pulses per quarter note, bytes F8/FA/FB/FC ([Wikipedia](https://en.wikipedia.org/wiki/MIDI_beat_clock)). TD's MIDI In CHOP lists timer events with beat pulses, Start/Stop/Continue
(can drive the Timeline/Beat dialog) and Song Position Pointer ([doc](https://derivative.ca/UserGuide/MIDI_In_CHOP), no revision date). In 2020 tempo and notes
were unstable on a Mac with an external clock (build 2020.23680); staff said in Aug 2022 that M1 + TD 2022 "both the tempo and note triggers are coming in
stable now" ([forum](https://forum.derivative.ca/t/poor-midi-timing-behaviour-on-mac/145515)). The MIDI In CHOP shows one on/off per channel per frame; use
the MIDI Event DAT for fast note triggers. Behaviour in 2025.31550 under Rosetta: UNVERIFIED. Phase from MIDI clock is only as good as the transport; count 24 ticks per beat and low-pass the tempo over a bar.

**LTC (SMPTE audio)** - TD: Audio Device In CHOP into [LTC In CHOP](https://docs.derivative.ca/LTC_In_CHOP) (edited 5 Dec 2023): `inputrate`, discrete h/m/s/f
channels, total frames, up-sample to timeline FPS, debug channels. Arena: [SMPTE input](https://resolume.com/support/en/smpte) is Arena-only, uses an audio input,
frame rate must match the signal (a once-per-second playhead jump means the rate is wrong), clips are set to SMPTE 1/2, **not available on clips with an audio track**, trigger is not
sent over SMPTE, and speakers into the built-in mic do not work. Limit (any timecode system): the show is locked to its programmed tempo, so it cannot follow a live tempo change
([Feed Me interview](https://cdm.link/playing-live-from-a-giant-toothy-monster-mouth-behind-the-scenes-with-feed-me/)). For PF26 this is a **fit exactly where `CREATIVE.md` already says
"critical reveals and names are manual or timecoded"**: an act playing to backing tracks can send LTC from the playback laptop to the show Mac, and Arena can fire the right clip/cue; a band
playing freely cannot.

**Pioneer Pro DJ Link (Arena)** - [Sync to Pioneer](https://resolume.com/support/en/sync-to-pioneer-dj-players) (v7.12 page): Arena only, wired ethernet hub, up to 4 players, models CDJ-3000, CDJ-2000NXS2,
DJM-V10, DJM-V10-LF, DJM-900NXS2; it syncs the *video playhead to the track* (like SMPTE, only for clips without audio), and the page does not mention BPM. The PF26 running order
(`show.json`) is five solo artists with no DJ listed; relevant only if a DJ appears.

**Tap / analyzer BPM into Arena** - Arena's [BPM article](https://resolume.com/support/en/bpm) (v6 page) shows Tap, Resync, Nudge and no audio detection; a 2020 staff post says Resolume
does not detect BPM from audio (via search summary of [forum thread](https://www.resolume.com/forum/viewtopic.php?p=79144), UNVERIFIED for 7.23.2). Users have sent a beat
note over MIDI from an analyzer to Arena's Tap button ([same search summary](https://www.resolume.com/forum/viewtopic.php?p=79114)). If Arena's BPM-synced base effects are
wanted, the sequence is: JZBA `bpm`/`beat` to a MIDI note or OSC message to Arena Tap. The exact OSC/MIDI target must be learned in Arena (`E_live_rig.md` 5.4); no address is assumed here.
One tempo source of truth only: either the analyzer or Link, never both writing.

**Decision table**

| Situation | Primary sync | Backup |
|---|---|---|
| Band plays free, no laptop | Analyzer, `Live Band` preset, Follow Kicks, operator **Beat 1 Now** | Manual BPM per song + Beat 1 Now |
| Band plays to click, tempo constant per song | Analyzer with `Lock Tempo` and per-song BPM preset (from the setlist) | Tap |
| Band has an Ableton laptop on the network | Link CHOP for tempo/phase; analyzer as monitor | Analyzer |
| Backing tracks / playback laptop | LTC to Arena (timed reveals, base clips) and TD (`ltcinCHOP`); analyzer for texture | Manual cues |
| DJ on CDJs | Pro DJ Link in Arena (playhead); analyzer for TD texture | Analyzer |

### 2.4 Beat, onset, downbeat: other trackers vs the in-house analyzer

- **JZBA** (per its README): kick/snare/hat from log spectral flux with adaptive thresholds, tempo from autocorrelation with hysteresis,
  beat phase as a clock locked to kicks, per-slot downbeat vote. Offline on synthetic ground truth: kick F1 1.00, beats F >= 0.98, downbeat 0.97; in TD 2 the same audio gave
  kick F1 1.00 vs 0.25 for the palette `audioAnalysis`. Real tracks: steady BPM on only 3 of 6 test tracks; live input, other sample rates and long runs not verified. Cost 29 us per frame core (C++).
  This is where the risk is: **synthetic F1 does not predict live-band behaviour** (tempo drift, ghost notes, hat rolls, crowd).
- **BeatNet** ([paper](https://arxiv.org/abs/2108.03576), ISMIR 2021): causal CRNN + two particle filters for online beats, downbeats and meter; no latency figures on the page; repo is CC-BY-4.0,
  streaming mode uses PyAudio, depends on librosa and madmom, madmom 0.16.1 has problems with Python 3.10+ ([repo](https://github.com/mjhydri/BeatNet)); Mac support not stated. Running PyTorch + madmom in TD's
  Python under Rosetta is the opposite of the C++ approach that was chosen to save CPU. UNVERIFIED on this Mac; not recommended live.
- **Beat This!** ([repo](https://github.com/CPJKU/beat_this), ISMIR 2024, arXiv 2407.21658): MIT code and weights; offline CLI; no real-time claim; CUDA or CPU, MPS not mentioned. Useful only as an *offline reference annotator*.
- **madmom** ([repo](https://github.com/CPJKU/madmom)): code BSD, but "models and data files" are **CC BY-NC-SA 4.0**, commercial use needs permission from the author. Anything pulled in through madmom (BeatNet needs it) inherits that question for a paid festival.
- **Recommendation:** keep JZBA live. If the user wants more confidence, run Beat This! or BeatNet *offline* on a recording of each act's reference song to produce reference beat/downbeat times and score JZBA against them (a download/install: needs the user's go-ahead, not done).

### 2.5 Stem-separated reactivity: what is feasible in real time on this Mac

| Option | Latency / speed | Evidence |
|---|---|---|
| HS-TasNet (real-time Demucs-inspired) | 23 ms; SDR 4.65 (5.55 with extra data) on MUSDB | [arXiv 2402.17701](https://arxiv.org/abs/2402.17701); **no code repo on the page**; a commenter says it reaches about 20 ms while "Demucs and MDXNet add seconds" ([HN](https://news.ycombinator.com/item?id=47675446), anecdotal) |
| RT-STT (DTTNet-based, Nov 2025) | Not stated on the abstract page | [arXiv 2511.13146](https://arxiv.org/abs/2511.13146); no code link on the page |
| HT-Demucs (reference) | CPU time about 1.5 x track duration (README); ONNX export: 1.6 s latency, RTF 0.20 for a 7.8 s segment on an **M4 Pro CPU** (self-published card); CoreML provider claimed "typically >= 5x faster", no benchmark | [Demucs](https://github.com/facebookresearch/demucs) (MIT, **archived 1 Jan 2025**, "not maintained anymore"), [ONNX card](https://huggingface.co/adowu/htdemucs-onnx) (MIT). M1 Max numbers: none |
| PEEL STEMS 2 (zplane, AU/VST3/AAX) | 245 ms at 44.1 kHz on Apple Silicon (385 ms Intel), vendor claim, 10 Jul 2026 | [Mixdown](https://mixdownmag.com.au/news/zplane-cuts-stem-separation-latency-by-49-with-peel-stems-2/); how to host a plug-in inside TD: UNVERIFIED |
| DJ-software stems (Serato, VirtualDJ, djay...) | Real time inside those apps, more artefacts than offline | [DJ.Studio](https://dj.studio/blog/stem-separation-djs-methods-benchmarks) (vendor of an offline tool); not exposed to TD |

Reading: only HS-TasNet-class models reach hit-compatible latency and I found no code for it. Everything else is 0.25 s to seconds late, which is later than
the sound at any seat inside about 85 m, and it would also compete for the same GPU/CPU as the 7488x2880 renders. **Verdict: skip ML stems for PF26.**

What gives the same creative result:
1. **Real stems from the desk** (K2).
2. **The analyzer's detectors are already pseudo-stems:** `low/mid/high` bands (split at 150 / 4000 Hz by default), `kick` 35 to 130 Hz, `snare` body plus noise, `hat` 7 to 16 kHz, `centroid`, `flux`, `flatness`. A simple vocoder-style bank of
   band-pass filters plus envelope followers is the minimum-latency route a commenter recommends over FFT ([HN](https://news.ycombinator.com/item?id=47675446)); JZBA's FFT hop of 512 at 48 kHz is already 10.7 ms.
3. **Stems from playback**: if an act plays backing tracks from a laptop, ask for the stem outputs of that laptop (drums/bass/music) - again real stems.
4. A vocal-presence feature (open mic or not) from the vocal group send is a cleaner trigger for "singer is on" than any separation.

### 2.6 Envelope design, anti-jitter, calibration

Concepts with sources:
- A one-pole follower with separate attack and release coefficients, picked per sample by comparing the input to the current value
  ([musicdsp envelope detector](https://www.musicdsp.org/en/latest/Analysis/97-envelope-detector.html)). **Convention warning:** `a = exp(-1/(t*fs))` reaches 63% in time t; other snippets use `exp(ln(0.01)/(t*fs))` (100% to 1%), which is about
  4.6x faster for the same nominal setting ([snippet](https://www.musicdsp.org/en/latest/Analysis/136-envelope-follower-with-different-attack-and-release.html)). JZBA's `_ema_k(dt, tau)` is `1 - exp(-dt/tau)`: tau is the **63% time**.
- Defaults in JZBA: bands attack 5 ms / release 250 ms; pulses decay 150 ms; minimum kick spacing 0.1 s; drivers attack 10 ms / release 350 ms; auto gain over 8 s; peak memory 20 s so riser noise in a breakdown is not mistaken for hits.
- A hobby LED-visualiser thread supports long AGC release ("like 20 seconds" so gain does not rise in a breakdown) and "a simple EMA with smoothing gave the best results" ([HN](https://news.ycombinator.com/item?id=47675446), anecdotal).
- 1 Euro filter: low-pass whose cutoff rises with speed; `mincutoff` lower = less jitter, more lag; `beta` higher = less lag when moving fast; tune beta=0 first, then mincutoff, then beta
  ([Casiez et al., CHI 2012](https://gery.casiez.net/1euro/)). TD's Filter CHOP has `oneeuro` (`ops/CHOP.md`). **Use it for slow features** (`centroid`, `flatness`, `confidence`, `bpm`), not for hit pulses.
- Trigger CHOP: separate trigger/release thresholds, **Re-Trigger Delay**, **Min Trigger Length**, attack/decay/release shapes, Multi Trigger "Clamp at Peak Level" to stop stacking ([doc, edited 11 Dec 2025](https://docs.derivative.ca/Trigger_CHOP)).
- Audio Spectrum CHOP: FFT 2048 is a reasonable CPU trade; fewer output samples = fastest; "the CHOP uses the most recent samples" ([doc, edited 16 Nov 2021](https://docs.derivative.ca/Audio_Spectrum_CHOP)). JZBA does its own FFT, so this only matters for any extra display.

Design rules for PF26 (mine, not sourced; tune by eye on the wall preview):
1. **At 30 fps, an attack under 33 ms is a one-frame jump.** For anything that changes luminance, use an attack of at least 2 to 3 frames (66 to 100 ms) and a release of 200 to 600 ms; keep instant attacks only for non-luminance parameters (scale, offset, particle emission).
2. **Debounce with hysteresis**: arm at a high threshold, re-arm only below ~0.95 of the pulse (as td-port FX Trigger Level already does) and add a refractory time per accent (see 2.7 "cooldown").
3. **Separate two time scales per band**: a fast channel (hit) and a slow channel (energy, 1 to 4 s lag). Looks should usually be driven by the *slow* one; the fast one only decorates.
4. **Use phase, not pulses, for motion.** `phase`/`bar_phase` are 0 to 1 ramps locked to the grid; `sin(2*pi*phase)` or an eased ramp gives motion that is smooth, beat-locked, jitter-free and has no sudden luminance steps. A missed or doubled detection shifts a ramp instead of causing a glitch.
5. **Hold/quantise**: sample-and-hold (Hold CHOP) of a random or driver value on `beat`/`bar` gives variety without extra detection (JZBA `jump` and `zigzag` already do this).
6. **Confidence handoff**: when `confidence` is low or the gate is closed, cross-fade (over >= 1 s) to free-running LFO motion; never freeze and never go chaotic. Matches `RUNTIME.md` "reactive loss -> base loop keeps running".

### 2.7 How the JZBA outputs should drive looks

| Output | Drive this | Don't drive this |
|---|---|---|
| `phase`, `bar_phase`, `beat_num` | Continuous motion (rotation, sweeps, breathing as `sin`), accent patterns by beat number (big on 1, small on 3) | Anything needing exact sample timing |
| `drive_low` / `low` (slow) | Scale/breath, glow radius, feedback gain, camera push (attack >= 80 ms) | Full-field brightness |
| `kick` pulse | **Max one accent per bar**, or only on `beat_num == 1`; position/scale impulse; particle burst | Luminance of the whole wall |
| `snare` | Direction change, wipe, offset jump, texture swap | Full-field white flash |
| `hat`, `onset` | Fine grain, sparkle density, small-area particles | Anything large (hat rolls exceed 3/s; see 2.9) |
| `flux`, `flatness` | Turbulence/noise amount, feedback decay (noisy sections = more motion) | - |
| `centroid` | Palette position / hue within the PRISM palette (slow, 1 Euro filtered) | - |
| `every2/4/8/16`, `toggle*` | **State changes**: palette swap, camera angle, layer variant | Per-beat flicker |
| `breakdown` / `build` / `drop` | Global **reactivity depth** and pace: breakdown = depth x0.3, slower; build = rising density; drop = one big accent then a lock-out | Reveals or names |
| `confidence`, gate state | Cross-fade between beat-locked and free-running motion; fade the whole reactive layer out slowly if the feed dies | - |
| `spin_*`, `jump`, `zigzag` | Ready-made drivers: rotation speed, random targets with glide, ping-pong positions | - |
| `bpm` | Speed of free-running fallback LFOs (so the fallback still feels in time) | - |

Known gap (observation, not a change): pulses always "hit exactly 1" (README), so a ghost note and an accent look identical to the look. Kick velocity is used
internally for `kick_boost` but is not an output. If per-hit dynamics matter (rock acts), a `kick_vel` / `snare_vel` output would need adding to td-port; I have not touched it.

Rules already in the project: names, reveals and narrative cues are manual or timecoded (`CREATIVE.md`, `STAGE.md`); audio analysis only modulates texture; TALK = reactivity off (`E_live_rig.md` 5.4).

### 2.8 Avoiding "everything pulses to the kick"

Source quality is weak here: I found no article that addresses audience fatigue directly. What exists:
- Guides advise smoothing, scaling ranges and separating sources ([ossia](https://ossia.io/score-docs/examples/video/audioreactive.html)), assigning bass/mids/treble to different properties ([HyperFrames audio-reactive skill](https://skills.sh/heygen-com/hyperframes/audio-reactive), via search summary) and saving sharp changes for drops ([Ticket Fairy](https://www.ticketfairy.com/blog/vj-grammar-for-drum-bass-vs-deep-140-tailoring-visuals-for-bass-music-festivals/)).
- Practitioners in the [HN thread](https://news.ycombinator.com/item?id=47675446): "make it react too much, and it's chaos, and ... less, it's boring"; rare flashy effects with "durational and/or stochastic behavior"; raw bass amplitude is a poor "drop" detector (a bass-heavy verse matches the drop) - thresholding helped a little (r/vjing, anecdotal).
- Pro rigs mix reactivity with other sync: Gala 2024 audio drove "colour curves changes and video play head manipulation" on a base animation (`B_visual_techniques.md`); LCD Soundsystem used direct instrument triggers plus lighting-desk operator cues ([VDMX](https://vdmx.vidvox.net/blog/nev-bull-lcd-soundsystem-coachella)); Feed Me used performer events not audio ([CDM](https://cdm.link/playing-live-from-a-giant-toothy-monster-mouth-behind-the-scenes-with-feed-me/)).

Synthesis (design, labelled as such; test by eye):
1. **One primary reactive driver per look**, chosen so consecutive looks differ (look A: low -> scale; B: snare -> direction; C: centroid -> hue; D: hats -> grain; E: phase only, no audio). A per-look "reactivity budget" prevents all of them using the kick.
2. **Move on the grid, change on the phrase.** Continuous phase-locked motion; discrete changes on `every4/8/16`.
3. **Spatial spread across the nine faces** (20/10/10/10/30/10/10/10/20 ft): the kick drives a rotating subset or a left-right chase, not all faces at once; a hit that hits the whole wall is rationed to drops.
4. **Section-aware depth**: `breakdown` lowers reaction and slows motion, `build` ramps density, `drop` gives one accent then a lock-out of 4 s or more.
5. **Cooldown on accents** and **accent budget per minute** (e.g. big accents no more than once per 8 bars).
6. **Dynamic depth**: use `level`/`flux` to scale reaction so quiet verses move gently and choruses open up.
7. **Operator control**: one Reactivity master (0 to 1) per look and a global one, on the MIDImix; and an "Audio off" key that fades to the free-running state.
8. **Evening arc**: five acts from 5:30 PM to 12:00 AM (`show.json`): keep average reactivity depth low in the early sets, raise toward the headliner; the last set must not be the first to use everything.
9. **Genre fit**: Hasan Raheem/hip-hop and rock acts lean on snare and vocals, not four-on-the-floor kick. The preset menu (`Hip-Hop 70-115`, `Live Band`) matters more than any mapping detail (act genres beyond `show.json` tags: UNVERIFIED).

### 2.9 Audio-driven flash safety

Rules (W3C WCAG 2.2, [Understanding 2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html)):
- A **flash** = a pair of opposing changes in relative luminance (rise then fall, or fall then rise); a **general flash** = change of at least **10% of the maximum relative luminance (1.0)** where the darker state is **below 0.80**.
- **Red flash** = a pair of opposing transitions involving saturated red: R/(R+G+B) >= 0.8.
- Content passes if there are **no more than 3 general flashes and no more than 3 red flashes in any 1 s**, or if the concurrently flashing area is no more than **0.006 steradians within any 10 degree field** (25% of that field).
- Relative luminance: linearise sRGB (`((c+0.055)/1.055)^2.4`, or `/12.92` below 0.04045), then `0.2126R + 0.7152G + 0.0722B`.
- The document gives no algorithm for counting overlapping pairs in a long sequence; counting each adjacent opposing pair is "the natural reading" (the page's own wording: inference), which would count a pulse train as up to 2 flashes per pulse. **Which counting Ofcom/Harding tools use is UNVERIFIED**; the project rule in `concert-visuals-research/README.md` 4 (3 flashes/s over 25% of the screen, 9-frame spacing is fine) comes from ITC/Ofcom guidance and is stated differently.
- [Epilepsy Society](https://epilepsysociety.org.uk/about-epilepsy/epileptic-seizures/seizure-triggers/photosensitive-epilepsy): 3 to 30 Hz is the common trigger range, 16 to 25 Hz most likely; about 3% of people with epilepsy are photosensitive; light/dark stripe and check patterns are triggers, more so when moving or flashing; the HSE recommends strobes at no more than 4 Hz in clubs/public performances.

What this means for an audio-driven wall (arithmetic marked design):
1. **The "small area" exception does not apply to the wall.** The nine faces sum to 130 ft = 39.6 m (`CLAUDE.md`); at 40 m distance that spans about 53 degrees, far more than one 10 degree field. Whole-wall flashes must stay within the **3 per second** rule.
2. **Rhythm exceeds 3 per second easily:** 140 BPM kicks are 2.3/s, 174 BPM drum-and-bass kicks 2.9/s, an eighth-note hat 4.7/s, and rolls more. JZBA's minimum pulse spacing is 0.1 s (10/s), so the *analyzer cannot be the safety*; the limit has to sit at the output.
3. **What counts as a flash in sRGB:** from black a 10% relative-luminance step is an 8-bit grey of about **89/255** (linear 0.1 -> sRGB 0.349). From mid grey (124/255, linear 0.2) the step is to about 149/255. So luminance modulation depth on dark content can stay small and never be a flash (a modulation under that step on a dark base is safe by the definition), whereas "pulse to white from black" always is.
4. **Spectrum-bar / EQ displays** (`B_visual_techniques.md` #7) are high-contrast stripes that change; with more than five light/dark stripe pairs they fall under the pattern warning in `concert-visuals-research/README.md` 4. Use soft, low-contrast or non-striped renderings, or fewer, wider bars.
5. **Fades to black count.** A feed loss that cuts the reactive layer to black is itself a luminance step on a huge wall: fade out over >= 1 s.
6. **Arena composites on top.** A TD-side limiter only governs the TD layer's own swings; base clip luminance adds. Limit TD's contribution and test the composite in the viewer (`E_live_rig.md` test plan).

Proposed governor (design, not built; a TOP/CHOP chain at the very end before the Syphon Out):
- Tap the final TOP; reduce to a tiny resolution (e.g. 32x12), linearise, compute mean relative luminance per frame (TOP to CHOP, Math, Analyze) and also the saturated-red fraction.
- A small Script/Execute logic tracks the sequence of opposing swings of at least 10% over a rolling 1 s window. Aim at **at most 2 flashes in any second** (margin under 3, and below the ambiguous double counting for most content) and give a gain 0 to 1 that ramps the reactive layer's *luminance depth* down (not its motion) when the count nears the limit; recover slowly (seconds).
- Rate-limit big accents independent of audio: lock-out of at least 4 s after a "drop" accent, at most N big accents per minute.
- Log every engagement to a DAT so the rehearsal shows how often it fires.
- Test with a screen capture through a PEAT/Harding-type tool; the W3C page lists the Harding FPA site and Trace Center PEAT (no endorsement) and notes no tool is needed if flashing is at most 3 per second.
- Cost: a 32x12 readback each frame should be negligible next to the 21.6 MP render (UNVERIFIED; measure in the soak test).

### 2.10 Resolume's own audio features (when TD is not needed)

- Arena parameters can take FFT from the external audio device (Preferences > Audio), or from the composition/clip/layer/group audio: three bands (L/M/H) with adjustable in/out range, **Gain** and **Fall** (no attack control), and up/down/speed modes ([Parameter animation](https://resolume.com/support/en/parameter-animation), v7.23 tab present; text does not say which versions the features apply to).
- Audio input also serves SMPTE. A forum post quoting the manual describes an 18-band analyser (search summary, older).
- Use: subtle reactivity on Arena-native base looks without a TD layer; but two analyzers (Arena FFT + JZBA) give two different "truths", and the same interface opened by both apps (CoreAudio sharing) is UNVERIFIED. Preferred: JZBA is the one analyzer; send it to Arena over OSC if needed (`E_live_rig.md` 5.4).

## 3. What is not covered / not verifiable now

- Music-specific audio-visual asynchrony tolerance (drum hit vs flash), delay-tower feeds, Dante/AES inputs, console OSC meters, Audinate and ProSoundWeb pages: web budget exhausted or pages returned 403.
- Anything about live input into JZBA, the Link CHOP under Rosetta, MIDI clock stability in 2025.31550, Syphon + Arena latency, LED processor model: not measured.
- Real-time performance of any ML model on the M1 Max: no measurement exists in the sources (the only Apple figure is an M4 Pro CPU, self-published).

## 4. Ranked recommendations for PF26 (8 days to show)

1. **Settle the audio feed with FOH this week** (ask, don't buy yet): balanced post-fader stereo matrix without crowd mics, plus optionally drums/bass/vocal group sends, with a limiter on the send; plus a splitter path to the backup machine. Decide the interface only after FOH answers. *(Needs the user.)*
2. **Build the flash governor and the "reactivity master + kill" before any audio-reactive look** (2.9, 2.6 rule 6), and test it with a hard 140 to 175 BPM pulse source on the wall preview. Nothing audio-driven goes to Arena without it.
3. **Make looks follow the mapping table (2.7) and the one-driver-per-look rule (2.8)**, with phase-locked motion as the default and pulses as accents only; every look gets a confidence fallback.
4. **Per-song tempo presets from the setlist** (`show.json` setlists): BPM (if the band plays to a click), preset (`Live Band` / `Hip-Hop`), beats per bar; the operator uses `Beat 1 Now` at song starts. Ask each act about click/backing tracks (open question 1).
5. **Use LTC for reveals and timed cues when an act has backing tracks** (Arena SMPTE, native), and keep manual cues for everything else (matches `CREATIVE.md`).
6. **Latency calibration at the first on-site audio rehearsal** with a phone in slow motion (2.1); set `Lookahead` for the beat grid only; leave hits alone.
7. **Verify JZBA on live input before relying on it**: a 1 h soak with the real interface and a looped recording through the PA, logging `confidence`, `bpm` drift, gate state, `cpu_us`. (It is the stated unverified list in the analyzer README.) *(Needs the user's go-ahead for audio device use and Syphon.)*
8. **Skip ML stems and live BeatNet.** Optionally, offline reference-annotate each act's reference song with Beat This! (MIT) to score JZBA; needs a download approval.
9. **Link/MIDI clock only if a band laptop is on stage**; treat as optional and one-writer-only.

## 5. Open questions for the lead

1. Which acts run a click, backing tracks, or Ableton on stage (decides Link / MIDI clock / LTC / free tempo)? `RUNTIME.md` still has "live arrangements, BPMs and medleys" open.
2. Who is the FOH engineer/vendor, which desk, and can they give a matrix/aux feed plus group sends (and in what format: analog XLR, AES, Dante, MADI)?
3. Are crowd/audience mics in the main mix? Is the gate/auto-gain acceptable with them?
4. Does the backup machine need the same audio feed (splitter or second interface)?
5. Should audio-reactive TD be allowed on the nine-face wall at all in the opening sets, or only in later ones (evening arc)?
6. Who owns the final flash sign-off: us, the vendor, or the Arena operator? Is a PEAT/Harding check part of acceptance?
7. Are there delay-tower screens in R02 (the old site plan shows delay towers with screens) and do they take the same feed/latency?
8. Which LED processor and what processing latency (feeds the 100 to 200 ms estimate)?
9. May I run audio tests with the real interface (microphone permission, 1 h soak) and, separately, a Syphon latency measurement?
10. For any Beat This!/BeatNet offline scoring, may reference songs be used and the packages downloaded?

## 6. Sources

TouchDesigner / Derivative
- Ableton Link CHOP: https://docs.derivative.ca/Ableton_Link_CHOP (24 Nov 2023)
- Link start/stop thread: https://forum.derivative.ca/t/ableton-link-stop-start-sync-enable/219586 (Oct to Dec 2021)
- MIDI In CHOP: https://derivative.ca/UserGuide/MIDI_In_CHOP
- MIDI timing on Mac thread: https://forum.derivative.ca/t/poor-midi-timing-behaviour-on-mac/145515 (Aug 2020 to Aug 2022)
- LTC In CHOP: https://docs.derivative.ca/LTC_In_CHOP (5 Dec 2023)
- Audio Device In CHOP: https://docs.derivative.ca/Audio_Device_In_CHOP (24 Jun 2022)
- Audio Spectrum CHOP: https://docs.derivative.ca/Audio_Spectrum_CHOP (16 Nov 2021)
- Trigger CHOP: https://docs.derivative.ca/Trigger_CHOP (11 Dec 2025)

Resolume
- Parameter animation (audio FFT, SMPTE mention): https://resolume.com/support/en/parameter-animation
- SMPTE input: https://resolume.com/support/en/smpte
- Sync to Pioneer DJ players (v7.12): https://resolume.com/support/en/sync-to-pioneer-dj-players
- BPM (v6): https://resolume.com/support/en/bpm
- Link (v6): https://resolume.com/support/en/link
- Forum, BPM detection and MIDI tap (search summaries only): https://www.resolume.com/forum/viewtopic.php?p=79144 , https://www.resolume.com/forum/viewtopic.php?p=79114

Sync, tempo, beat tracking, stems
- Ableton Link concepts: https://ableton.github.io/link/ ; repo (GPLv2+/proprietary): https://github.com/Ableton/link
- MIDI beat clock: https://en.wikipedia.org/wiki/MIDI_beat_clock
- BeatNet: https://arxiv.org/abs/2108.03576 , https://github.com/mjhydri/BeatNet
- Beat This!: https://github.com/CPJKU/beat_this
- madmom: https://github.com/CPJKU/madmom
- HS-TasNet: https://arxiv.org/abs/2402.17701 ; RT-STT: https://arxiv.org/abs/2511.13146
- Demucs: https://github.com/facebookresearch/demucs ; ONNX export: https://huggingface.co/adowu/htdemucs-onnx
- PEEL STEMS 2: https://mixdownmag.com.au/news/zplane-cuts-stem-separation-latency-by-49-with-peel-stems-2/
- DJ stems: https://dj.studio/blog/stem-separation-djs-methods-benchmarks
- Envelope follower: https://www.musicdsp.org/en/latest/Analysis/97-envelope-detector.html , https://www.musicdsp.org/en/latest/Analysis/136-envelope-follower-with-different-attack-and-release.html
- 1 Euro filter: https://gery.casiez.net/1euro/ (Casiez, Roussel, Vogel, CHI 2012)

Practice and feeds
- LCD Soundsystem Coachella (VDMX, 28 Apr 2016): https://vdmx.vidvox.net/blog/nev-bull-lcd-soundsystem-coachella
- Feed Me interview (CDM, 29 Aug 2012): https://cdm.link/playing-live-from-a-giant-toothy-monster-mouth-behind-the-scenes-with-feed-me/
- HN thread on audio-reactive LEDs (anecdotal): https://news.ycombinator.com/item?id=47675446 (article: https://scottlawsonbc.com/post/audio-led , not opened)
- ossia audio-reactive tips: https://ossia.io/score-docs/examples/video/audioreactive.html
- HeavyM (snippet only, 403): https://www.heavym.net/how-to-sync-visuals-with-music-audio-reactive-projection-mapping-made-simple/
- ProSoundWeb aux vs matrix (snippet only, 403): https://www.prosoundweb.com/the-right-signal-deciding-on-an-aux-send-versus-a-matrix-to-send-to-video-on-corporate-gigs
- Live Design, broadcast/FOH (snippet only, 403): https://www.livedesignonline.com/gear/broadcast-audio-for-webcasting-while-also-mixing-foh
- Gearspace tapping FOH (snippet only): https://gearspace.com/threads/live-sound-recording.178846/
- Ticket Fairy VJ grammar (summary only): https://www.ticketfairy.com/blog/vj-grammar-for-drum-bass-vs-deep-140-tailoring-visuals-for-bass-music-festivals/
- HyperFrames audio-reactive skill (summary only): https://skills.sh/heygen-com/hyperframes/audio-reactive
- BlackHole: https://existential.audio/blackhole/

Latency and safety
- Speed of sound: https://en.wikipedia.org/wiki/Speed_of_sound
- AV sync thresholds (Hoffner, 14 May 2003): https://www.tvtechnology.com/opinions/av-synchronization-how-bad-is-bad ; sports study: https://arxiv.org/pdf/2212.01686
- Brompton SX40 data sheet (snippet only): https://globaltrendpro.com/wp-content/uploads/2022/07/Brompton-SX40-Data-Sheet.pdf
- WCAG 2.2 Understanding 2.3.1: https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html
- Epilepsy Society: https://epilepsysociety.org.uk/about-epilepsy/epileptic-seizures/seizure-triggers/photosensitive-epilepsy

Project files read
- `td-port/audio_analysis/README.md`, `td-port/audio_analysis/analyzer.py` (constants and `_frame`)
- `prismfest26-show/show.json` (running order), `RUNTIME.md`, `CREATIVE.md`, `STAGE.md`
- `concert-visuals-research/README.md` section 4
- `jazib-td-mcp/docs/research/` A, B, C, E, `ops/CHOP.md`
