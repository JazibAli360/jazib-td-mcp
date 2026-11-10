# M: audience / crowd interaction on concert screens (what exists, how it is wired, what fits PRISMFEST'26 Karachi)

Research agent M, Fri 16 Oct 2026. Research only: TD not touched, nothing built, nothing generated, nothing installed or downloaded, no Arena/Syphon/REST operation.
Web access: `WebFetch` pages were read in full where the source column says **fetched**. The session's web-search budget ran out part-way
through, so some leads rest on **search-result summaries only** (marked **snippet**) and some leads were never followed (listed in "Open questions").
Anything from memory or not backed by a URL is marked **UNVERIFIED**. Arithmetic done here is marked as such. No performance number appears without a source.
Fixed facts (TD 2025.31550, 1080x1920 build, Syphon/NDI into Arena 7.23.2, Karachi 24 Oct) come from `BRIEF.md` / `DIRECTIONS.md` and are not re-derived.
Camera/crowd-cam/MediaPipe ground is already in `D_camera_mediapipe.md` (R2 motion energy, R4 gesture triggers, privacy line 217); this file goes deeper on the *interaction* side and does not repeat it.

---

## 1. Summary (read this first)

1. **The proven, big-scale crowd interactions are not phone-network interactions.** LED wristbands (Xylobands RF; PixMob IR) and noise meters tied to a real microphone have run at tens of thousands of people for years. Phone-driven web interactions exist but their only hard scale numbers are small (2,913 players in a QR game; 6,000 app downloads per college game) and the best-documented phone light show (CUE) deliberately avoids Wi-Fi and cellular by sending cues as ultrasound.
2. **Cellular congestion is real, measured and gets worse on uplink.** A 2026 measurement paper at a 77,622-seat stadium found a cellular "uplink gap" on game day: P90 time-to-first-byte 5,983 ms on congested 5G NSA, 46% of image uploads failing on cellular, while the venue's ~900-AP Wi-Fi had a 3.9% page-load failure rate. A Karachi open-air festival will have far less purpose-built capacity than that stadium (**UNVERIFIED**: no source found on the venue's network). Treat every phone-dependent feature as a *bonus layer* that can vanish without the show noticing.
3. **Pakistan adds a second failure mode: government-ordered mobile-data suspensions** (Karachi Muharram precedent; 2026 Islamabad/Rawalpindi and 2025 Balochistan reports). Nothing found says 24 Oct 2026 is affected; it is an organiser/security question.
4. **Free-text from the crowd is the expensive part.** Hashtag/open walls get hijacked; Roman Urdu has no standard spelling; Google/Jigsaw's Perspective API is announced to stop after 31 Dec 2026 and nothing found shows Urdu support; X reads cost $0.005 per post and X reaches only ~2.88M ad-audience in Pakistan. **Fixed-choice inputs need no moderation at all.**
5. **Privacy:** the Coldplay/Astronomer kiss-cam incident (16 Jul 2025, Gillette Stadium) is the live example of a crowd cam backfiring. Pakistan has no comprehensive data-protection law in force per secondary sources (conflicting). Keep crowd-cam FX to movement/brightness levels, no face display, no recording.
6. **Architecture rule for phone input:** TD sits behind venue NAT, phones are on cellular, so TD must dial *out* (WebSocket DAT / SocketIO DAT / Web Client DAT polling) to a small cloud relay. Web Server DAT is for the operator panel on the LAN, not the public (Basic auth only, "security is the complete responsibility of the user").
7. **Top picks for PF26 (section 7):** (1) microphone "make some noise" meter, (2) crowd-cam motion/phone-light energy with no faces, (3) organiser-sourced RF wristbands (decision this week or never), (4) QR tap-vote with fixed bilingual choices, (5) operator-approved bilingual shout-outs, then ultrasonic phone light show (post-PF26), opt-in dance cam, and "skip: hashtag wall".
8. Timeline: today is 16 Oct, programming day is Fri 23 Oct (`show.json` calendar via C §1.1): **7 days**. Anything that needs a vendor quote, import or an app store listing is already marginal.

---

## 2. Findings table (who did it, how, scale, evidence)

| # | Idea | Who / where | Mechanism | Scale / numbers | Source | Status |
|---|---|---|---|---|---|---|
| 1 | RF LED wristbands, whole audience | Coldplay (Mylo Xyloto 2011/12 onward; A Head Full of Dreams incl. Glastonbury 2016; Music of the Spheres, compostable white-only, returned for reuse) | One RF transmitter + laptop, bands receive and execute together; DMX from the lighting console into the RF transmitter; seating-block segmentation | MotS tour: 86% average return in year one, Seoul 99% (Apr 2025); Xylobands claim 10,000+ events, 50+ countries (own site) | [Xylobands technical blog](https://xylobands.com/blog/technical-look-led-wristband-technology), [Wikipedia: Xyloband](https://en.wikipedia.org/wiki/Xyloband), [Korea Times](https://www.koreatimes.co.kr/amp/southkorea/society/20250425/seoul-tops-coldplays-led-wristband-return-rate-in-world-tour) | fetched |
| 2 | IR LED wristbands / "human video screen" | PixMob: Arcade Fire Coachella 2011 (1,250+ glowing balls), Super Bowl XLVIII 2014 (about 80,000 video ski hats), Milan Cortina 2026 (65,000+ with wristbands) | IR transmitters around the venue; in "VIDEO" mode each receiver decodes the signal according to its position; also DMX/Art-Net into the lighting desk | PixMob says 10,000+ events, 8 Super Bowls | [Wikipedia: PixMob](https://en.wikipedia.org/wiki/PixMob), [TPI](https://www.tpimagazine.com/pixmob-reflects-on-two-decades-of-shapeshifting-innovation/), [Architect magazine snippet](https://www.architectmagazine.com/technology/products/when-the-audience-becomes-the-concert-lighting_o) | fetched (Wikipedia, TPI); IR/DMX/16 transmitters/100 m only from a search snippet |
| 3 | Hybrid wristband control | Xylobands: RF for sync, DMX for art, IR for zones; segment by seat block, sweeps, audio-cue triggers | see row 1 | "tens of thousands of new mobile pixels" at Coldplay | [Xylobands: Crowd as canvas](https://xylobands.com/blog/crowd-as-canvas-festival-production-new-era) | fetched; marketing text |
| 4 | Phone light show over **ultrasound** (no Wi-Fi/cellular) | CUE Audio (founded 2017; 800+ events/yr, mostly sports; tours: Lynyrd Skynyrd, Jeremy Camp; AGT); earlier Wham City Lights (2012-13) and Dan Deacon app (25 Sep 2012) | Stage speakers play a patented "acoustic modem" signal; phone mic decodes it; screen/torch effects | CUE: participation 20% to 60% in the best shows (vendor); UNC case: 6k downloads and 10k opens per game vs 21k attendance goal; Wham City Lights: 40,000 at one CMA Music Festival (search summary of Technical.ly) | [Pollstar 2023](https://news.pollstar.com/2023/07/21/lighting-industry-takes-cues-from-fans-production-quarterly/), [Hypebot: Dan Deacon](https://www.hypebot.com/fans-become-the-light-show-with-dan-deacons-live-concert-mobile-app/), [Technical.ly (snippet)](https://technical.ly/?p=88437) | Pollstar, Hypebot fetched; CUE band 17.5-19.5 kHz and Wham City 40,000 from **snippet** |
| 5 | QR code on the screen turns phones into controllers | St. Louis Blues "Blue Notes Racing": fans scan QR on the jumbotron, tap to speed a Zamboni on the screen | Second-screen web app on AWS, thousands of simultaneous requests | pilot: 2,913 players, 2,040 offer clicks (about 70%, their figure) | [Paradowski case](https://paradowski.com/work/st-louis-blues) | fetched; date not stated |
| 6 | QR check-in and encore voting | SET.Live (launched in coverage 20 Sep 2022) | QR -> show page: vote encore song, contests, merch | no usage numbers | [Hypebot](https://www.hypebot.com/hypebot/2022/09/setlive-free-app-helps-artists-connect-with-fans-at-live-shows.html) | fetched |
| 7 | Inaudible-audio triggers for phone voting + light show at music events | UntapTV with AEG (China, 2012) | audio watermark in the PA feed | users opened app about 10 times on average | [Mobile Marketing Magazine (snippet)](https://mobilemarketingmagazine.com/aeg-and-untaptv-deliver-live-mobile-experience-at-music-events/) | **snippet** (page 403) |
| 8 | Stadium noise meter on the scoreboard | Kansas City Chiefs (Guinness outdoor stadium noise record, 2014: 142.2 dB per one source; 137.5 dB per another) with Larson Davis Class 1 meters | Calibrated meter -> wireless/network -> graphics computer -> scoreboard, sample rate set by the graphics operator | Larson Davis argues "fake" meters hurt trust | [Larson Davis](https://larsondavis.com/applications/environmentalnoisemonitoring/stadiumnoisemonitoring), [PopSci](https://www.popsci.com/science/jell-o-crowd-volume/) | Larson Davis fetched; dB figures conflict, see section 6.3 |
| 9 | Live audience camera on the show screens | Radiohead 2025 tour: 20+ live cameras (band and audience), whole show in Notch, no pre-rendered content, Disguise GX 3; Imagine Dragons Mercury Tour 2022 live camera effects on IMAG | Cameras into media server, effects in Notch | 20 performances, 5 cities | [Disguise case study (26 Mar 2026)](https://www.disguise.one/en/insights/case-study/radioheads-record-breaking-tour-put-visuals-round-disguise-and-notch) | Radiohead fetched; Imagine Dragons **snippet** |
| 10 | Camera/Kinect-tracked crowd drives visuals | Nuits Sonores (Lyon): LED pyramid, six Kinects tracked people walking over it, OpenFrameworks; Glastonbury "Pi" tent: tracked silhouettes + particles | depth cameras over a small zone | small zone, not a mass crowd | [Creative Applications (403 on fetch)](https://www.creativeapplications.net/?p=36107) | **snippet** only; treat as "this exists", not as method evidence |
| 11 | Kiss cam | Coldplay, Gillette Stadium, Foxborough MA, 16 Jul 2025 (likely date; article says "Wednesday night", published 19 Jul) | Venue crowd cam on the jumbotron | Astronomer CEO resigned within days; fake apology statement circulated | [Yahoo News](https://www.yahoo.com/news/tech-firm-ceo-resigns-amid-221454031.html) | fetched; the article has no statement on privacy/consent |
| 12 | Social/tweet walls | Many conferences; danah boyd at Web 2.0 Expo NY (Nov 2009): Twitter wall behind her, she could not see it, left upset | Hashtag aggregator -> screen | hijacking and spam "not uncommon" (agency blog) | [Raph Koster on boyd](https://www.raphkoster.com/2009/11/25/danah-boyds-talk-about-streams-becomes-object-lesson/), [Converia](https://www.converia.de/en/blog/tweet-it-to-the-wall/), [Crowdpurr](https://www.crowdpurr.com/blog/5-social-media-wall-pitfalls-to-avoid) | fetched (Converia, Crowdpurr); Koster **snippet** |
| 13 | Open public vote hijacked | NERC "Name our ship" (2016): "Boaty McBoatface" 124,109 votes; name not used, ship became RRS David Attenborough | web poll | 7,000+ names submitted, site outages from traffic | [CNN](https://amp.cnn.com/cnn/2016/04/18/world/boaty-mcboatface-wins-vote), [Time](https://tollbit.time.com/4266219/boaty-mcboatface-naming-vote/) | **snippet** (summary of search results) |
| 14 | Phone-voted visuals in a classical concert (research) | Open Symphony (QMUL): audience votes mood of projected animation, client/server | web app | paper page returned empty on fetch | [QMUL record](https://qmro.qmul.ac.uk/xmlui/handle/123456789/12500) | **snippet**; no data extracted |

---

## 3. Per-item details

### 3.1 LED wristbands (rows 1-3)

- **Two radio families.** RF: one laptop-fed transmitter reaches every band in range, passes through bodies and clothing, bands act on the same packet at the same moment; the RF transmitter can take DMX from the lighting console; IR: small transmitters, line-of-sight, good for zones or "trigger as people pass" ([Xylobands tech blog](https://xylobands.com/blog/technical-look-led-wristband-technology)). Wikipedia lists a handheld controller range of 250 m and a laptop-based transmitter up to 300 m ([Xyloband](https://en.wikipedia.org/wiki/Xyloband)). PixMob IR: commands go to transmitters that emit IR; each receiver feeds a tiny 8-bit processor that lights RGB LEDs; in video mode each receiver decodes the signal for its position in the audience ([Wikipedia: PixMob](https://en.wikipedia.org/wiki/PixMob)).
- **Third family, Bluetooth** (phone app linked to seat number, most expensive, most pre-production) per [Wristband Resources](https://www.wristband.com/blogs/news/how-led-wristbands-work-at-concerts); that page is written by a seller of admission wristbands (not LED), so its numbers are unverified.
- **Network independence is the point for Karachi:** control is radio/IR from a transmitter at FOH. No phone, no cellular, no Wi-Fi.
- **Reuse:** MotS bands are compostable, white-only, collected, sterilised, recharged (86% returned in year one; Jakarta disputed: claim 52%, Coldplay said 77%, 80,000 distributed per the claimant, not official: search summary). PixMob recycling since 2018, 2 million bands refurbished in 2024 ([PixMob story](https://pixmob.com/stories/closing-the-loop-on-event-waste)). A one-off festival in Karachi should assume *no return* and a per-person cost.
- **Cost:** no official per-band price found. Wristband Resources says "$5 to $10 per person" (vendor of non-LED bands; **unverified**). Generic Indian marketplace listings were reported at about INR 60-165 per piece for sound-reactive/multicolour silicone bands (search snippet, [IndiaMART](https://m.indiamart.com/impcat/led-wristband.html), page 403), which are **not** synced RF bands. Wikipedia notes a "wrongly reported" EUR 490,000 per concert figure for Xylobands, i.e. no usable number.
- **Lead time/availability in Pakistan:** no source found. **UNVERIFIED.** For a 24 Oct show a quote, shipping and customs are the risk, not the control side.
- **TD link:** TD does not drive RF bands directly. Cleanest TD role: send a level or cue (MIDI/OSC/DMX) to whoever runs the wristband transmitter, or follow the same cue list. `dmxoutCHOP` exists in the dump (Art-Net, sACN, FTDI; `ops/CHOP.md` row `dmxoutCHOP`, class-level only, not run). Whether the transmitter takes Art-Net or only wired DMX is an open vendor question.
- **Safety:** wristband strobes add to the venue's total flashing; the flash limits in `concert-visuals-research/README.md` §4 are written for screens (3 flashes/s over more than 25% of the field). Applying a similar cap to wristband effects is a sensible rule, **not a sourced requirement**.

### 3.2 Ultrasonic / audio-triggered phone shows (rows 4 and 7)

- **How:** the PA plays an inaudible modem tone; each phone's microphone decodes cues; no network needed. CUE calls it an "acoustic modem" (patented); Pollstar: "needs no WiFi or mobile service", works "over long distances with low latency", designed by CUE about 95% of the time, webpage access "not yet available and would depend on Apple opening that capability", **app installation is a barrier in touring** ([Pollstar](https://news.pollstar.com/2023/07/21/lighting-industry-takes-cues-from-fans-production-quarterly/)).
- **Band 17.5-19.5 kHz** is from a search-result summary of CUE's FAQ (**snippet**); the FAQ URL now redirects to connectwithcue.com. A phone microphone and a loud outdoor PA with a Nastaliq-era audience of mixed Android hardware is an unknown: **UNVERIFIED**.
- **Dan Deacon app (25 Sep 2012):** free iOS/Android app, phones synchronised by "sonic prompts", works "without using WiFi or data" ([Hypebot](https://www.hypebot.com/fans-become-the-light-show-with-dan-deacons-live-concert-mobile-app/)).
- **Fit for PF26:** the only phone interaction that survives a dead network, but it needs an app people install beforehand and a vendor; not realistic by 24 Oct. Park as a post-PF26 R&D line.
- **Browser-only version:** MDN: `getUserMedia` works only on HTTPS/localhost and always shows a permission prompt ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)). A web page listening for ultrasound is therefore possible in principle but nobody found has shown it at scale; **UNVERIFIED**, and CUE says iOS web access is not available (quote above).

### 3.3 Phone -> web -> TD (rows 5-6 and the architecture)

**Why a relay.** Phones on cellular cannot reach a Mac behind venue NAT. Derivative's remote-control tutorial exposes TD with `ngrok http 9980`: the free subdomain changes every restart, the client URL is hard-coded, and "any connected client can send events" because the code authenticates nobody ([Interactive & Immersive](https://interactiveimmersive.io/blog/controlling-touchdesigner/control-your-touchdesigner-installation-remotely/)). That is a demo pattern, not a show pattern.

**Recommended shape (design inference, nothing built):**

```
phone (QR -> tiny bilingual page, fixed buttons)
   |  HTTPS POST /vote {choice: "A"}   (one small request per tap; no accounts)
   v
cloud relay (Cloudflare Worker + Durable Object, or any small VPS)
   - validates choice against a whitelist, rate-limits, keeps counters
   - exposes GET /tally -> {"A":123,"B":87,...,"t":1729...}   (cached, tiny)
   ^
   |  TD dials OUT every 1-2 s  (Web Client DAT)  or holds a socket (WebSocket DAT / SocketIO DAT)
TD (venue LAN, no inbound port)
   webclientDAT -> jsonDAT -> tableDAT/CHOP -> clamp -> Null CHOP -> look parameters
   heartbeat age > N s -> Switch TOP to the default look (nothing on screen depends on the crowd)
```

- **TD side ops (all exist as classes in the build dump; none run for this purpose):** `webclientDAT`, `jsonDAT`, `websocketDAT` (live-confirmed as a client, T-04), `socketioDAT` (socket.io C++ client v3.1.0, works with v3/v4 servers, server events must be listed in input 2, `emit` supported, no ack callbacks, `delay` par = reconnect ms) ([SocketIO DAT](https://derivative.ca/UserGuide/SocketIO_DAT), `ops/DAT.md` rows), `mqttclientDAT` (ws/wss capable), `oscinDAT`/`oscinCHOP` for a LAN helper. **Polling `GET /tally` is the most failure-tolerant** (each poll is independent; last good value is held). WebSocket DAT docs say nothing on reconnect or keepalive ([WebSocket DAT](https://derivative.ca/UserGuide/WebSocket_DAT)), so a persistent socket needs a TD-side watchdog; SocketIO DAT has an explicit reconnect delay.
- **Web Server DAT:** serves HTTP and WebSockets, no stated max connections, no threading note, TLS pars exist, Basic auth only, "security is the complete responsibility of the user", page edited 4 Jun 2026 ([Web Server DAT](https://docs.derivative.ca/Web_Server_DAT)). Use it only for an operator control/approval page on the venue LAN. macOS firewall prompts are unverified (`ops/DAT.md`).
- **OSC In CHOP** is UDP only; useful for a local helper (e.g. a Python vision process or the relay's LAN agent) with `Queued`, `Maximum Queue`, and Info CHOP queue channels ([OSC In CHOP](https://docs.derivative.ca/OSC_In_CHOP)). Do not put OSC on the public internet.
- **Open-source template exists:** MultiplayerServer_TD (Derivative community, 8 Jun 2026): Node/Express + Socket.io, input batching, SQLite, Docker; no tested player count or latency stated ([page](https://derivative.ca/community-post/asset/multiplayerservertd-multiplayer-game-touchdesigner/74760)). Not downloaded (guardrail); useful only as a pattern to read later.
- **Relay cost/limits (Cloudflare Durable Objects, fetched):** Free plan allows SQLite-backed objects, 100,000 requests/day and 13,000 GB-s/day; incoming WebSocket messages billed 20:1; batching every 50-100 ms recommended; "thousands of clients per instance", no hard maximum given; deploying a new version disconnects every socket ([pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/), [WebSocket best practices](https://developers.cloudflare.com/durable-objects/best-practices/websockets/)). Whether a Pakistani audience reaches Cloudflare edge reliably is **UNVERIFIED**.
- **Per-IP rate limiting is dubious:** mobile carriers commonly NAT many users behind one IP (general knowledge, **UNVERIFIED for Pakistani carriers**); prefer per-device token + global caps.

**Scale of participation (honest numbers):** St. Louis Blues QR game: 2,913 players ([Paradowski](https://paradowski.com/work/st-louis-blues)). CUE (app-based, ultrasound): best shows 20-60% of the stadium; UNC college: 6k downloads and 10k opens per game against a 21k attendance goal (arithmetic: about 29% downloads). No source found measures *web-only QR* participation at a music festival; for PF26 assume a small fraction (a planning guess, **UNVERIFIED**) and design the visual so 200 votes and 2,000 votes look equally intentional (normalised bars, not absolute counts).

**Page design for bad networks (design inference):** one inline HTML file well under 50 KB, no external fonts/frameworks/analytics, big bilingual buttons (Urdu and English on every button, `dir="rtl"` for Urdu text), system fonts only (Nastaliq availability on stock Android: **UNVERIFIED**, test on a few phones), optimistic UI (button turns "sent" at once, retry in background), works if the POST is slow, no camera or microphone prompt. A QR code on the LED wall must be large: rule-of-thumb scan distance is roughly 10x the code width (general rule; the source page I tried returned 404, **UNVERIFIED**).

### 3.4 Networks at crowd scale (what actually fails)

- **Cell capacity is the limit, not signal bars:** operators bring cells on wheels (COWs) for chosen events; "you can double or triple the capacity, but you can't increase it a thousand times" (Guardian, via [PressReader](https://www.pressreader.com/usa/the-guardian-usa/20230826/282218015348150), **snippet**, page 403 on fetch).
- **Measured at a stadium** ([arXiv 2607.16008](https://arxiv.org/abs/2607.16008), Notre Dame Stadium, 77,622 seats, ~900 outdoor Wi-Fi APs, up to 129 PCIs per operator through a small-cell DAS; abstract fetched): cellular is excellent when empty, but game-day crowds strain **uplink** and latency ("uplink gap"); under 5G NSA congestion web TTFB 5,983 ms at P90, 46% image-upload failure on cellular; low-band n5 median BLER 70% during browsing, 36.6% page-load failure; Wi-Fi had 3.9% page-load failure and 2.1x image-upload latency degradation vs empty. The measured apps were web browsing, WhatsApp and Instagram upload, i.e. close to a vote page. Lesson: a tiny POST can still time out; design for retries and seconds of lag.
- **Dense Wi-Fi is a big build:** vendor guidance 1 AP per 50-100 seats under-seat or 150-200 overhead; Purple's worked example of 65,000 seats needs ~1,419 bowl APs and 10-100 Gbps backhaul ([Purple.ai](https://www.purple.ai/en-us/guides/high-density-wifi-design-stadium-and-arena-best-practices), vendor figures, internal inconsistency noted by the fetch). A one-night open-air festival will not have this; do not plan on venue Wi-Fi for the crowd. Arithmetic example only: even 3,000 simultaneous Wi-Fi users at 55 devices/AP (that page's rated capacity) would need about 55 APs.
- **Pakistan context:** PTA/Opensignal Q2 2026: average 4G download 18.9 Mbps, Karachi 12.19-18.27 Mbps across operators ([TechJuice](https://www.techjuice.pk/?p=255538)); Ookla median mobile download 24.32 Mbps (Pakistan, to Aug 2025) ([DataReportal 2026](https://datareportal.com/reports/digital-2026-pakistan)). Speed is fine; *shared capacity under a crowd* is the unknown.
- **Government suspensions:** Karachi Muharram suspensions (Sindh asked for mobile services off 10 am-10 pm on eight Muharram, year not shown in the snippet: [ARY snippet](https://bk.arynews.tv/?p=251706), 503 on fetch); Balochistan data suspended to 31 Aug 2025; Islamabad/Rawalpindi suspension reported 2026 by one outlet only ([Digital Rights Monitor](https://digitalrightsmonitor.pk/pakistan-mobile-services-suspended-in-islamabad-rawalpindi/), **single source**). No source says anything about 24 Oct 2026 in Karachi. **UNVERIFIED either way.**
- **Reach by platform in Pakistan (ad-reach, late 2025, not active users):** TikTok 79.9M (18+), Facebook 52.9M, YouTube 54.3M, Snapchat 41.1M, Instagram 22.4M, X 2.88M ([DataReportal](https://datareportal.com/reports/digital-2026-pakistan)). WhatsApp and smartphone shares are not in that page; a marketing blog says 100M+ WhatsApp users with no source (**UNVERIFIED**). Implication: a hashtag wall that depends on X is nearly pointless; a QR to a plain web page does not depend on any platform.

### 3.5 Crowd microphone "make some noise" meters (row 8)

- **What was done:** calibrated Class 1 meters (Larson Davis, up to 143 dB) near the crowd, data streamed to the scoreboard graphics operator, who chooses refresh rate and how to display; used to prompt louder/quieter play and for sponsored displays. The vendor stresses real measurements over "fake meters" ([Larson Davis](https://larsondavis.com/applications/environmentalnoisemonitoring/stadiumnoisemonitoring)).
- **For a festival with a big PA the hard problem is bleed:** a microphone near the crowd mostly hears the PA. No source found addresses this. Mitigations (design inference, **UNVERIFIED**): use the audience/ambience mics the broadcast or recording engineer already has, high-pass/gate, and show *relative* movement above a baseline captured during a quiet moment, not an absolute dB figure. Never label it dB unless a calibrated meter is used.
- **TD chain (classes exist; nothing run):** `audiodeviceinCHOP` -> `audiospectrumCHOP` or filter -> `analyzeCHOP` (rmspower) -> `mathCHOP` (range) -> `lagCHOP`/`filterCHOP` (fast attack, slow release) -> baseline subtraction -> `nullCHOP` -> params; peak hold with `timerCHOP`/`triggerCHOP`. Per `ops/CHOP.md` the macOS microphone permission prompt for Audio Device In is untested here, and `A_td_2025_howto.md` §ADR notes td-port chose external 0-1 audio values over TD mic analysis on 12 Oct. Decide: keep that external-values route and feed the crowd level in the same way.
- **Latency:** local audio buffer only (no network). Audio Device In buffer length trades latency (`ops/CHOP.md`). No figure is claimed here.

### 3.6 Crowd camera, motion energy, kiss/dance cams (rows 9-11)

- **Already covered:** D §R2 (Farneback motion energy, 0..1 CHOP), `td-port/crowd_energy`, face/person FX, privacy line. **Optical Flow TOP is not usable on this Mac** (Windows/NVIDIA, D line 65). `blobtrackTOP` creates on Mac (D line 63).
- **New here, "sea of lights" detection:** in a dark crowd, phone torches are bright points: `lumalevelTOP`/`thresholdTOP` -> `blobtrackTOP` or `analyzeTOP`/`toptoCHOP` count -> level. This would drive F06 *Crowd Pulse ident* ("sea of lights", `C_pf26_fit.md` row F06 d1/d2) from reality. Never tried; stage lighting and LED wash may saturate the sensor (**UNVERIFIED**).
- **Pro tours do show the crowd:** Radiohead 2025 used 20+ cameras including audience shots, all in Notch, and RUNTIME-style fail-safes (state-driven, no timecode) ([Disguise](https://www.disguise.one/en/insights/case-study/radioheads-record-breaking-tour-put-visuals-round-disguise-and-notch)). The camera plan for PF26 is still open (D line 21).
- **Kiss cam:** see row 11. Facts from the article: the screen caught a married CEO and a colleague, Chris Martin joked "Either they're having an affair or they're just very shy", viral identification, resignation. The article itself has no privacy comment. A fake apology that criticised Coldplay for showing audience on screen circulated and the company said it was not genuine (LBC via search summary). Lesson: *identifiable individuals on a giant screen + a caption from the stage* is the risk, not the camera.
- **Pakistan privacy/legal:** a 2026 legal guide says no comprehensive enacted data-protection law as of May 2026; another says the bill is still in Parliament; PECA 2016, amended Jan 2025, is a criminal statute, not a privacy framework (search-result summaries of secondary legal sites: [Commoner Law](https://commoner-law.com/pakistan/data-privacy-digital-rights/data-privacy-without-pdp-act), [Chambers 2026](https://practiceguides.chambers.com/practice-guides/data-protection-privacy-2026/pakistan)). **Check with the organiser's counsel; I found nothing on filming consent at private events.** Cultural sensitivity of couples on screen in Karachi: judgement call, **UNVERIFIED**.

### 3.7 Text walls, SMS walls, moderation (rows 12-13)

- **Documented failure modes:** hashtag hijacking, profanity from real attendees, negativity, outside influence ([Crowdpurr](https://www.crowdpurr.com/blog/5-social-media-wall-pitfalls-to-avoid)); the wall behind the speaker that the speaker cannot see ([Converia](https://www.converia.de/en/blog/tweet-it-to-the-wall/)). Both are vendor/agency blogs with a commercial interest; the boyd incident is first-person blog evidence, relayed by [Fortune](https://fortune.com/2009/11/21/what-wowed-the-crowd-at-web-2-0-expo) and Koster.
- **Open polls get taken over** (Boaty McBoatface, row 13). So any free-text or open-choice input is a moderation job.
- **Platform feeds are poor and costly:** X API pay-per-use is $0.005 per Post read, capped at 3M reads per month; no free reading tier on that page ([X API pricing](https://docs.x.com/x-api/getting-started/pricing)). Instagram Basic Display API: all requests error since 4 Dec 2024; replacement requires Professional accounts and is a different API ([Meta, via search](https://developers.secure.facebook.com/docs/instagram-basic-display-api)). With X at 2.88M ad-audience in Pakistan, hashtag walls are a poor fit.
- **Language moderation:** Roman Urdu has no standard spelling, which defeats keyword lists; research shows trained classifiers on RU datasets (RUHSOLD 10,012 tweets; RU-OLD 15,000 tweets; accuracy figures vary 93%-99% by dataset and are not comparable) ([RU-OLD record](https://repository.cuilahore.edu.pk/handle/123456789/1758), [EMNLP 2020](https://preview.aclanthology.org/setup/2020.emnlp-main.197), [MDPI 2025 benchmark](https://www.mdpi.com/1999-4893/18/7/396)). **Perspective API: "will no longer be in service after 2026", active until 31 Dec 2026** ([perspectiveapi.com](https://perspectiveapi.com/)); the page does not show Urdu support. A hosted LLM classifier could be an assistant, but I have no evidence on its Urdu/Roman Urdu accuracy: **UNVERIFIED**. Conclusion: human approval is the only gate.
- **Operator workflow (design inference):** submissions land in a relay queue; an operator panel (TD custom pars/Web Server DAT on LAN, or a plain admin page) shows Urdu/English text; operator taps approve; TD displays the single approved line with a minimum on-screen time; a global "hold" kills the layer. Text shown *whole*, never truncated (names/words intact rule): cap input length at submission and auto-fit rather than clip. Urdu shapes in the Text TOP (A §2); names of artists are never TD-generated (DIRECTIONS §2).
- **Sensitive content in Pakistan** (political, religious, sectarian, defamatory text) is a legal as well as taste risk; the organiser must name who approves. PECA (criminal statute) is the relevant law per the same legal guides above; scope **UNVERIFIED**.

### 3.8 TD-side summary of the op chains

| Interaction | Input path | TD chain (class names exist in `ops/INDEX_2025.31550.json`; none run) | Fail-safe |
|---|---|---|---|
| Noise meter | audio interface line from audience mic | `audiodeviceinCHOP` -> `analyzeCHOP` -> `mathCHOP` -> `lagCHOP` -> baseline -> `nullCHOP` -> look | level < threshold shows the idle look; mic lost -> hold last then fade |
| Crowd-cam energy | NDI/Syphon/capture of organiser crowd feed | D R2 (Script TOP Farneback, verified synthetic) or luma threshold + `blobtrackTOP` -> `toptoCHOP` -> `lagCHOP` | `switchTOP` to a clean base; watchdog on frame age (D "Fail-safe") |
| QR vote | cloud tally | `webclientDAT` (poll) -> `jsonDAT` -> `tableDAT` -> `selectCHOP`/`mathCHOP` normalise -> `nullCHOP` | tally age > N s or failed polls -> default; values clamped, only whitelisted options |
| Shout-outs | cloud queue -> operator approval | as above + `textTOP` (Urdu shaping per A §2) with auto-fit | hold toggle; EMERGENCY/SAFE HOLD kills the layer |
| Wristband cue | TD or lighting desk -> RF transmitter | `dmxoutCHOP` (Art-Net/sACN) or MIDI/OSC cue to the desk | wristbands default to off/steady; vendor-defined |

---

## 4. Latency, scale limits, reliability (consolidated)

- **Phone -> screen is seconds, not frames.** From the stadium paper: P90 TTFB 5.98 s under congestion; Wi-Fi uplink latency 2.1x worse than empty. Design visuals as *aggregates that drift* (bar fills, mood colour, hold-for-N-seconds), never twitch games.
- **No latency figures exist for the DATs themselves in the docs** (Web Server DAT, WebSocket DAT, SocketIO DAT pages carry none; OSC In CHOP only describes its queue). Any figure must be measured in a later authorised session.
- **Acoustic/RF/IR links are the low-latency, high-count options** (vendor claims only; no measured latency in the sources).
- **Participation caps** are unknown for web-only; app-based best cases are 20-60% (CUE, vendor). Wristbands reach 100% of the people given one (hand-out logistics are the limit).
- **Moderation and legal exposure scale with free text**, not with headcount.

## 5. Cost (what the sources support)

| Item | Cost evidence | Source |
|---|---|---|
| Relay (votes/tally) | Cloudflare Workers Free: 100k requests/day, incoming WebSocket messages 20:1; paid $0.15 per million requests after 1M/month | [Cloudflare pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/) |
| X reads | $0.005 per Post, 3M/month cap | [X](https://docs.x.com/x-api/getting-started/pricing) |
| LED wristbands | "$5 to $10 per person" (non-LED seller, unverified); no PixMob/Xylobands quote public | [Wristband Resources](https://www.wristband.com/blogs/news/how-led-wristbands-work-at-concerts) |
| Calibrated noise meter | no price found; not needed if the meter is relative | n/a |
| Moderation | human operator time; Perspective API ends 31 Dec 2026 | [perspectiveapi.com](https://perspectiveapi.com/) |
| Venue Wi-Fi for thousands | vendor example: >1,000 APs for 65,000 seats, 100 Gbps uplink; out of reach for this show (inference) | [Purple.ai](https://www.purple.ai/en-us/guides/high-density-wifi-design-stadium-and-arena-best-practices) |

## 6. What really worked vs gimmicks (evidence-weighted)

### 6.1 Worked (multi-year, large-scale, documented)
- **Wristbands:** Coldplay used them from 2011 to the current tour (return rates 86%-99% show fans keep playing along); PixMob 8 Super Bowls and Milan Cortina 2026 (65,000+); Xylobands' own text: "The technology should never be a gimmick" ([Xylobands](https://xylobands.com/blog/crowd-as-canvas-festival-production-new-era)).
- **Real noise meters** in sport (Chiefs); the vendor itself says fake ones damage trust.
- **Ultrasonic phone light shows** in sport (800+ events/yr, vendor claim), because they do not depend on the network.
- **Live crowd shots** on the screens (Radiohead 2025; IMAG tradition).

### 6.2 Gimmick-prone or fragile
- **Hashtag/tweet walls** (hijack, speaker blind to wall, tiny platform reach in Pakistan).
- **Open public votes** (Boaty McBoatface; Mountain Dew "Dub the Dew" went to offensive suggestions per a search summary).
- **Apps that must be installed** for a touring show (CUE: install is a barrier).
- **Phone games that need many round trips** over a congested uplink (stadium paper).
- **Kiss cam** as a surprise gag when the people shown have not agreed.
- **Fake meters** (Larson Davis argument) - if a number looks fixed or scripted the crowd stops believing it.

### 6.3 Figures that disagree (noted, not resolved)
Chiefs record: 142.2 dB in the search summary vs 137.5 dB in the title of an article linked from Larson Davis's page (not the page body). Do not quote a figure without opening the Guinness entry.

---

## 7. Ranked recommendations for PF26 (Karachi, 24 Oct, Urdu/English, unreliable mobile data)

Ranking = value for the show x feasibility in 7 days x robustness to a dead network x moderation/privacy cost. All are *proposals*: nothing is built until the user says go (build-only-what's-asked). Placement keys to RUNTIME states: pilot in a **changeover** (30/25/20/15 min beds + sponsor slates), never in TALK ("nothing flashing") or EMERGENCY/SAFE HOLD; F06 Crowd Pulse ident (10 s) and G01 finale are the natural payoffs.

| Rank | Idea | Why it ranks here | Network need | Moderation | Privacy | Needs from others | Effort to 24 Oct |
|---|---|---|---|---|---|---|---|
| **1** | **Mic "make some noise" meter** (relative, never labelled dB), drives a bar/pulse on a changeover bed and a finale build | Real, proven in sport; no phones, no network, no moderation, no privacy; one signal feeds many looks | none | none | none (no recording) | a clean audience/ambience mic line to the Mac interface; permission prompt test (untested here) | small; Chain in 3.5; decide external-values vs TD mic first |
| **2** | **Crowd-cam motion energy + torch-count** (no faces, no recording) to drive F06 Crowd Pulse | Reuses D R2 and `crowd_energy`; real crowd drives the ident; fits "sea of lights" look already in the plan | none (organiser's camera feed over NDI/SDI) | none | low: levels only; ask for a filming notice anyway | **a crowd camera and a feed to the Mac: not in any document** (D line 21, 41) | medium; blocked on RFI08 camera plan |
| **3** | **RF LED wristbands** (Coldplay-style), operated by the lighting side with TD sending cues | The only high-impact interaction that works with no phones at all | none (RF/IR from FOH) | none | none | organiser budget, vendor with stock in Karachi, hand-out plan, transmitter position, DMX/Art-Net input question; **go/no-go by about 18 Oct** or drop | build effort small, procurement is the whole risk |
| **4** | **QR tap-vote with fixed bilingual choices** (e.g. pick the colour/mood of the Crowd Pulse or the next changeover bed from 3-4 pre-approved looks) | Needs no moderation; the visual is built from approved looks; hold-last-value fail-safe | cellular or venue Wi-Fi; designed to fail soft | none (whitelisted options) | collects nothing: no names, no numbers, no analytics | a cloud relay account, a QR on the wall, sponsor/organiser OK; user rule: viewer review of every look before it can be chosen | medium; pilot in Changeover 1 |
| **5** | **Operator-approved shout-outs** (one line, EN or UR, fits-whole, sponsor-slate adjacent) | Audience sees themselves on the wall, but only with a human gate; Urdu shaping available in Text TOP | same as 4 | **human approval of every line**; global hold | stores only the text; no ids | an operator seat with Urdu literacy; written rules posted on the QR page; organiser decides what is forbidden | medium-high; only if 4 works in rehearsal |
| **6** | **Ultrasonic phone light show** (CUE-type) | Network-independent and proven in sport | none | none | microphone permission on phones | vendor app/SDK, audience installs app, PA ultrasound reproduction untested: **not feasible by 24 Oct** | post-PF26 R&D |
| **7** | **Opt-in "dance cam"** on a marked volunteer zone, framed by the host | Fun when consent is explicit; avoids the kiss-cam trap | none | none | consent by signage + host invitation; no captions about people; no recording | organiser camera, host script, a zone | low tech, high care; skip unless the organiser asks |
| **8** | **Hashtag/social wall** | Included only to say **skip**: platform reach, API cost, hijack risk | internet + platform APIs | heavy | posts are public data but shown on a huge screen | n/a | skip |

Per-rank notes the lead may need:
- **#1/#2 dependency:** both reduce to "give TD one number between 0 and 1 and a safe default". They use the same watchdog/Switch scaffolding D already specifies, so they share build time.
- **#3 is a decision, not a TD job.** If it goes ahead, TD's part is a cue/level sender; the rest is vendor and logistics. If no quote by the decision date, drop it.
- **#4 flash rule:** a vote result must never raise flash rate; clamp output to the approved looks and the 3 flashes/s / 25% limits (`concert-visuals-research/README.md` §4).
- **All phone-dependent items (#4, #5): defaults must look intentional with zero votes**, and the audience should never be told a result is "live" unless it is.
- **Emergency:** the interactive layer is a Switch TOP branch killed by SAFE HOLD/EMERGENCY states; layer 6 in Arena already is "reactive loss -> base loop keeps running" (D line 32).

## 8. Open questions for the lead

1. **Is the user willing to have any audience interaction at all** (RUNTIME and MOU list "live camera FX" only), and who at PRISM approves content shown from the crowd? (Privacy and moderation both hinge on this.)
2. **Crowd audio:** can the audio engineer give a clean audience/ambience mic or a stereo FOH tap, and is it OK to use the macOS microphone permission with TD (untested; `ops/CHOP.md`)? Or keep td-port's "external 0-1 values" decision and feed the level from outside TD?
3. **Crowd camera:** does the organiser plan any crowd shots, and can a clean feed reach this Mac? (RFI08 is open.) Is a venue filming notice already planned (td-port says it is the production's call)?
4. **Wristbands:** does PRISM or RONIN have budget, and is there a supplier in Karachi with stock? Who runs the transmitter (lighting desk or us)? Does it accept Art-Net or only wired DMX? Go/no-go date?
5. **Network:** what does the venue (DHA Sports Club / Moin Khan Academy per RUNTIME) have: Wi-Fi at all, carriers' event capacity (COW) arranged? Is a mobile-data suspension possible on 24 Oct? Who can tell us?
6. **Sponsor angle:** RONIN is title sponsor; would sponsor-linked QR content be wanted (and approved) on the wall? Not decided; do not raise MOU scope/fee (memory: MOU parked).
7. **Languages:** Urdu script only, Roman Urdu, English? Which Urdu font renders on a representative set of cheap Android phones (Nastaliq fallback)? Not tested.
8. **Moderator:** who is the human approver and can they read Roman Urdu? Is a banned-topics list available from the organiser?
9. **Where to pilot:** Changeover 1 (6:30-7:00 PM, smaller crowd) is the proposed first slot; needs the user's go-ahead and a rehearsal at the venue network.
10. **Sources not followed (search budget):** Open Symphony results and latency; CUE FAQ ultrasound band confirmation; Nuits Sonores/Glastonbury Pi detail; Karachi event network reports; Perspective-like Urdu moderation APIs; WhatsApp usage in Pakistan from a primary source; QR scanning distance rule; a measured participation rate for web-only QR voting at music festivals (none found).

---

## 9. Sources (all URLs used; "fetched" = page read via the fetch tool; "snippet" = only a search-result summary)

TouchDesigner (Derivative):
- Web Server DAT, https://docs.derivative.ca/Web_Server_DAT (edited 4 Jun 2026) - fetched
- WebSocket DAT, https://derivative.ca/UserGuide/WebSocket_DAT - fetched
- SocketIO DAT, https://derivative.ca/UserGuide/SocketIO_DAT - fetched
- OSC In CHOP, https://docs.derivative.ca/OSC_In_CHOP - fetched
- MultiplayerServer_TD community asset (Vasily, 8 Jun 2026), https://derivative.ca/community-post/asset/multiplayerservertd-multiplayer-game-touchdesigner/74760 - fetched
- Interactive & Immersive, remote control with ngrok, https://interactiveimmersive.io/blog/controlling-touchdesigner/control-your-touchdesigner-installation-remotely/ - fetched
- Local: `ops/DAT.md`, `ops/CHOP.md`, `A_td_2025_howto.md`, `D_camera_mediapipe.md`, `C_pf26_fit.md`, `DIRECTIONS.md`, `ops/INDEX_2025.31550.json`, `../../LEARNINGS.md` T-04; `prismfest26-show/RUNTIME.md`, `SHOW.md`; `concert-visuals-research/README.md` §4.

Wristbands:
- Xylobands technical blog, https://xylobands.com/blog/technical-look-led-wristband-technology - fetched
- Xylobands, Crowd as canvas, https://xylobands.com/blog/crowd-as-canvas-festival-production-new-era - fetched
- Wikipedia: Xyloband, https://en.wikipedia.org/wiki/Xyloband - fetched
- Wikipedia: PixMob, https://en.wikipedia.org/wiki/PixMob - fetched
- TPI Magazine, PixMob two decades, https://www.tpimagazine.com/pixmob-reflects-on-two-decades-of-shapeshifting-innovation/ - fetched
- PixMob, closing the loop on event waste (22 Apr 2025), https://pixmob.com/stories/closing-the-loop-on-event-waste - fetched
- Korea Times, Seoul wristband return rate (25 Apr 2025), https://www.koreatimes.co.kr/amp/southkorea/society/20250425/seoul-tops-coldplays-led-wristband-return-rate-in-world-tour - fetched
- Wristband Resources, how LED wristbands work, https://www.wristband.com/blogs/news/how-led-wristbands-work-at-concerts - fetched (seller of non-LED bands)
- Architect magazine, https://www.architectmagazine.com/technology/products/when-the-audience-becomes-the-concert-lighting_o - snippet (403)
- CTV Montreal, PixMob at the Super Bowl (11 Feb 2024), https://www.ctvnews.ca/montreal/article/montreal-company-lights-up-the-crowd-at-the-super-bowl/ - fetched (teaser only)
- IndiaMART LED wristband listing, https://m.indiamart.com/impcat/led-wristband.html - snippet (403)

Phone / audio-triggered / QR:
- Pollstar, Lighting industry takes cues from fans (21 Jul 2023), https://news.pollstar.com/2023/07/21/lighting-industry-takes-cues-from-fans-production-quarterly/ - fetched
- Hypebot, Dan Deacon app (25 Sep 2012), https://www.hypebot.com/fans-become-the-light-show-with-dan-deacons-live-concert-mobile-app/ - fetched
- Technical.ly, Wham City Lights, https://technical.ly/?p=88437 and https://technical.ly/baltimore/2013/08/30/wham-city-lights-one-year-old/ - snippet (403)
- Mobile Marketing Magazine, UntapTV + AEG, https://mobilemarketingmagazine.com/aeg-and-untaptv-deliver-live-mobile-experience-at-music-events/ - snippet (403)
- Paradowski, St. Louis Blues QR game, https://paradowski.com/work/st-louis-blues - fetched
- Hypebot, SET.Live (20 Sep 2022), https://www.hypebot.com/hypebot/2022/09/setlive-free-app-helps-artists-connect-with-fans-at-live-shows.html - fetched
- QMUL Open Symphony, https://qmro.qmul.ac.uk/xmlui/handle/123456789/12500 - snippet (empty on fetch)
- CUE Audio (redirects), https://cueaudio.com/frequently-asked-questions/light-show - snippet
- MDN getUserMedia, https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia - fetched

Noise meters / camera / tours:
- Larson Davis, stadium noise monitoring, https://larsondavis.com/applications/environmentalnoisemonitoring/stadiumnoisemonitoring - fetched
- PopSci, Giant Jell-O, https://www.popsci.com/science/jell-o-crowd-volume/ - snippet
- Disguise, Radiohead tour case study (26 Mar 2026), https://www.disguise.one/en/insights/case-study/radioheads-record-breaking-tour-put-visuals-round-disguise-and-notch - fetched
- Creative Applications (Nuits Sonores / Glastonbury Pi, 403), https://www.creativeapplications.net/?p=36107 - snippet
- Yahoo News, kiss-cam resignation (19 Jul 2025), https://www.yahoo.com/news/tech-firm-ceo-resigns-amid-221454031.html - fetched
- LBC, fake statement, https://www.lbc.co.uk/news/entertainment/ceos-fake-statement-kisscam-coldplay-gig/ - snippet

Networks / Pakistan:
- arXiv 2607.16008, App-based performance in dense stadium deployments (Notre Dame), https://arxiv.org/abs/2607.16008 - fetched (abstract)
- Guardian via PressReader, https://www.pressreader.com/usa/the-guardian-usa/20230826/282218015348150 - snippet (403)
- Purple.ai, high-density Wi-Fi design, https://www.purple.ai/en-us/guides/high-density-wifi-design-stadium-and-arena-best-practices - fetched (vendor)
- DataReportal Digital 2026 Pakistan, https://datareportal.com/reports/digital-2026-pakistan - fetched
- TechJuice, PTA Q2 2026 (Opensignal), https://www.techjuice.pk/?p=255538 - fetched
- Digital Rights Monitor, https://digitalrightsmonitor.pk/pakistan-mobile-services-suspended-in-islamabad-rawalpindi/ - snippet
- Internet Society Pulse, Balochistan Aug 2025, https://pulse.internetsociety.org/en/shutdowns/internet-suspended-in-balochistan-pakistan-august-2025/ - snippet
- ARY News, Karachi Muharram suspension, https://bk.arynews.tv/?p=251706 - snippet (503)
- Commoner Law, https://commoner-law.com/pakistan/data-privacy-digital-rights/data-privacy-without-pdp-act ; Chambers 2026, https://practiceguides.chambers.com/practice-guides/data-protection-privacy-2026/pakistan - snippets

Walls, polls, moderation:
- Crowdpurr, https://www.crowdpurr.com/blog/5-social-media-wall-pitfalls-to-avoid - fetched
- Converia, https://www.converia.de/en/blog/tweet-it-to-the-wall/ - fetched
- Raph Koster on danah boyd, https://www.raphkoster.com/2009/11/25/danah-boyds-talk-about-streams-becomes-object-lesson/ ; Fortune, https://fortune.com/2009/11/21/what-wowed-the-crowd-at-web-2-0-expo - snippets
- CNN Boaty McBoatface, https://amp.cnn.com/cnn/2016/04/18/world/boaty-mcboatface-wins-vote ; Time, https://tollbit.time.com/4266219/boaty-mcboatface-naming-vote/ - snippets
- X API pricing, https://docs.x.com/x-api/getting-started/pricing - fetched
- Meta, Instagram Basic Display API, https://developers.secure.facebook.com/docs/instagram-basic-display-api - snippet (the Facebook-docs URL I fetched had no deprecation text)
- Perspective API, https://perspectiveapi.com/ - fetched (sunset notice; no Urdu statement)
- Roman Urdu offence detection: https://repository.cuilahore.edu.pk/handle/123456789/1758 ; https://preview.aclanthology.org/setup/2020.emnlp-main.197 ; https://www.mdpi.com/1999-4893/18/7/396 - snippets
- Cloudflare Durable Objects pricing, https://developers.cloudflare.com/durable-objects/platform/pricing/ ; WebSocket best practices, https://developers.cloudflare.com/durable-objects/best-practices/websockets/ - fetched

No images were saved (nothing needed), so there is no `refs/M/`.
