# S - Trend scan 2024-2026: real-time and interactive concert visuals, plus South Asian visual culture (research, 16 Oct 2026)

Research only. Nothing was generated, built, installed or downloaded; TouchDesigner and Arena were not touched. Written for the
PRISMFEST'26 TD work (TD 2025.31550, builds at 1080x1920, TD live into Arena 7.23.2 via NDI/Syphon; acts: Nehaal Naseem,
Abdul Hannan, Hasan Raheem, Mustafa Zahid, Ali Zafar, per `prismfest26-show/show.json`).
It does not repeat `B_visual_techniques.md` §2 (RHCP, Calvin Harris Coachella 2023, Gala, Boomtown, Jade Cicada, EDC 2010, Rush, Amon Tobin)
or `concert-visuals-research/` (festival screen content, flash limits README §4). It adds newer items and goes into how each was made.

**How to read the evidence tags.** `[F]` = I fetched and read the page itself. `[S]` = only a web-search result summary, page not
fetched (treat as lead). `UNVERIFIED` = no usable source. Vendor case studies (Notch, disguise, Moment Factory, Xylobands) are
the vendor's own account. The web-search budget ran out part-way (200 calls shared by all agents), so some artist/tour questions were
not answered; they are listed as gaps, not guessed.

---

## 1. Summary

1. **Real-time is real, but the split is mixed everywhere I could verify.** The best-documented 2024-2026 show with a stated split is Phish at Sphere
   (Moment Factory): "longest-ever real-time content show", Unreal + Notch + pre-rendered, on disguise, 16K x 16K canvas [F: blooloop, newswire]. A Notch case study
   (search summary only, page not fetched) says the plan was 70/30 pre-rendered to real-time and rehearsals moved it to about 50/50 [S]. Pre-rendered
   loops for the same show were made in Notch, TouchDesigner, Houdini and Cinema 4D (Sila Sveta) [F: silasveta.com].
2. **Big pop tours stay mostly pre-rendered.** Billie Eilish's 2024 tour (Moment Factory + GMUNK) is explicitly pre-rendered, "glitchy and fluid", lo-fi,
   with live camera shots built into the content [F: momentfactory.com, toolofna.com]. For Beyonce, The Weeknd, Travis Scott I found **no** credit naming a real-time tool: UNVERIFIED.
3. **Where Notch/TD/Unreal are named at 2024-2026 festivals it is a "live instrument layered over a base"** model: Charli XCX and Arca at Coachella 2025, Dom Dolla at Coachella 2024,
   Cesare Cremonini stadium tour 2025, Junior H Coachella 2025 (Unreal + Notch on disguise). All [F].
4. **TouchDesigner is the glue, rarely the renderer of the hero image** in the credited big shows: control translation (Bad Bunny, 2019 [S]), Block testing (Harry Styles, Silent Partners [F]),
   lighting-data bridge (T2 Visuals, 2020 [F]), loop making (Sila Sveta, Phish [F]). Direct TD-as-show-system 2024-26 evidence is in Derivative's own posts:
   y=f(x) lab for Mysteryland 2024 mainstage and Carl Cox Evolution 2025 [F], PlexusPlay [F], Quayola *Solar* [F], *Astrum* in Riyadh [F].
5. **Look trend: lo-fi, analogue, intimate.** Fred again.. USB002 (phone-filmed moments on screens, red bulbs, blue torch covers) [F: NME]; Charli XCX (motion blur, low frame rate, double exposure, lens distortion, strobes) [F]; Billie (lo-fi, water/abyss) [F]; Harry Styles (vintage optical effects, "non-digital feel") [F].
6. **Audience as part of the image** is the other trend: LED wristbands (Coldplay India 2025 and Diljit Dosanjh tours), phone-torch keyrings (Fred again..), mobile voting/touch triggers (PlexusPlay) [F/S].
7. **South Asia: public technical credits are thin.** No verifiable credit for Notch/TD/Unreal at Coke Studio Pakistan, Lahooti Melo, or any Pakistani concert; Atif Aslam, Ali Zafar, Hasan Raheem, Young Stunners
   production coverage names no tools. What is documented: Lollapalooza India (Wolves, Notch, 21:9 centre + two vertical screens) [F], Coke Studio's hand-painted, colour-rich set language [F], Lolla India 2026 praise for on-screen lyric translation and criticism of sponsor-logo overload [F], and a 2026 Rolling Stone India piece on Indian "firsts" (360 stage, mesh holographic LED) [F].
8. 15 transferable ideas for PF26 in TD are in §5. Each is a proposal, not a fact.

---

## 2. Findings table

Real-time column: **RT** = stated real-time; **PRE** = stated pre-rendered; **MIX** = both stated; **?** = not stated in source I read.

| # | Item (year) | Who | RT? | Technique / tools named | Evidence |
|---|---|---|---|---|---|
| 1 | Phish, Sphere (Apr 2024) | Moment Factory (co-creative: Abigail Rosen Holmes); content also Sila Sveta, Myreze, Behaviour; Fuse integrator | MIX (RT central) | Unreal, Notch, pre-rendered, AI-assisted visuals, 360 capture, disguise, 16K x 16K, 14 hours content, 4 themed nights | [F] blooloop, newswire |
| 2 | Phish loops (Sila Sveta) | Sila Sveta | PRE | 60+ abstract loops in Notch, **TouchDesigner**, Houdini, C4D; drone-footage loops in Notch; tested on Unreal/Notch stage models; ~4 months | [F] silasveta.com |
| 3 | Anyma, The End of Genesys, Sphere (Dec 2024-2025) | Anyma (Matteo Milleri), Alessio De Vecchi, Woodblock | ? (sources disagree) | Unreal Engine; synced to beats "in real time" per one source; "pre-rendered CGI environments" per another | [F] heftig; ymcinema (low reliability, self-contradicting) |
| 4 | Billie Eilish, Hit Me Hard and Soft (2024-25) | Moment Factory; GMUNK Studio content | PRE | Lo-fi, glitchy/fluid, camera shots of performer inside content; LED floor, 8 towers, shape-shifting overhead screens | [F] momentfactory.com, toolofna.com |
| 5 | Charli XCX, Coachella 2025 | Cour Design; Notch designer Mike Kluge | RT (Notch "ran all of the actual show"; page does not say render mode explicitly) | Notch pre-viz of stage; analogue-camera effects | [F] notch.one |
| 6 | Arca, Coachella 2025 | Henrique Ghersi, Thomas Kother, Eddie Perez | RT | Notch Blocks in the Notch-for-Resolume plugin; MIDI on exposed params; automated cameras with live override; towers with live cameras ("bullet-time") | [F] notch.one |
| 7 | Dom Dolla + John Summit, Coachella 2024 | The Unlimited Dream Company; High Scream | RT (Notch) + pre-made | Notch Virtual Background puts the live camera feed into minimalist compositions; C4D, Unreal, After Effects | [F] notch.one |
| 8 | Junior H, Coachella 2025 main stage | Charly Camina; label Rancho Humilde | ? (not stated) | Whole set built in Unreal; Notch effects; disguise Designer Pro for simulation and pre-programming; EX3+ server; 4 weeks | [F] disguise.one |
| 9 | Cesare Cremonini stadium tour 2025 | NorthHouse | MIX | 65 m panoramic screen; Unreal previs; Notch run live ("100% live") with disguise keyframes + MIDI; pre-rendered sequences baked into Notch Blocks | [F] notch.one |
| 10 | Harry Styles, Love On Tour (2021-23) | Silent Partners Studio | RT (Notch Block) | **TouchDesigner used to test Notch Blocks**; one big Block for the whole show, one layer per look; lighting-console programmer drives Block params; network access to tweak in rehearsal | [F] notch.one |
| 11 | FKJ world tour (2022-24) | NorthHouse | RT + footage | Feedback loops from recorded footage, beat-driven Sound Modifier/Time Stretch, pixel-sort glitch, dither, Cloner; tools list includes TouchDesigner (role not stated) | [F] notch.one |
| 12 | Metallica M72 (2023-24) | Nocte Studio (Andrea Cuius) | Mostly pre-rendered in Notch | Pixel-map-matched 3D previs, NDI from After Effects into Notch, moving spotlights projecting a video layer | [F] notch.one (page undated; tour dates not on page) |
| 13 | Carl Cox Evolution (2025) and Mysteryland mainstage (2024) | y=f(x) lab (Roy and Tim Gerritsen) | RT | "Realtime software system" syncing visuals, lasers, lighting; Mysteryland: realtime visuals + custom mapping. TD not named on the studio page, but the talk was at the Derivative/MUTEK.JP **TouchDesigner Event Tokyo 22-23 Nov 2025** | [F] yfxlab.com, derivative.ca |
| 14 | PlexusPlay (2022-26) | Matt DiBiase | RT | TD + Ableton (TDAbletonSong), Art-Net LED suit, NDI to FOH lighting, mobile-vote (2023) and touch-sensor triggers for drops | [F] derivative.ca |
| 15 | Quayola, *Solar* (Toronto, Jan 2026 post) | Quayola; TD system by Murtas and De Vecchis | RT | TD maps Alembic-coordinates to 200 moving heads, sACN/Art-Net pan/tilt, Ableton OSC; custom Pan Tilt CHOP from Derivative | [F] derivative.ca |
| 16 | *Astrum*, NOOR Festival Riyadh (2025) | László Zsolt Bordos, programmer András László Nagy | RT | TD computes pan/tilt for 64 fixtures from a NASA star map, safety logic, 8 sACN universes, ran on an Apple M2 Air in testing | [F] derivative.ca |
| 17 | Tomorrowland Belgium (Jul 2025) | Organisers | n/a | Main stage destroyed by fire; replacement built in under 48 hours; parts of the LED wall from Metallica's touring rig; programme went ahead "almost unimpeded". Visual tools not stated | [F] Pollstar |
| 18 | Fred again.. USB002, Alexandra Palace (Feb 2026) | Boris Acket named for "immersive installation" | ? | Screens with phone-filmed moments, throbbing red bulbs, blue keyring torch covers; canopy; **no tool credits found** | [F] whynow, NME, Alexandra Palace blog |
| 19 | PLAVE (virtual K-pop band), Gocheok Sky Dome (Nov 2025) | VLAST | RT avatars | Performers backstage drive avatars live; ~37,000 over two nights (Seoulz, Jun 2026) | [F] seoulz.com |
| 20 | Lollapalooza India (2023, Notch case study) | Wolves (Joshua Dmello, Jash Reen) | ? | Notch; 21:9 centre screen + two vertical side screens; element-themed effects; Background Remover; iPad Pro touch control; Jackson Wang looks re-made in a one-hour changeover | [F] notch.one |
| 21 | Lollapalooza India (Jan 2026) | BookMyShow Live; visual language by Aaquib Wani | ? | "Cosmic connections" visual language, one story per stage; Fujii Kaze screen showed English translation of lyrics; sponsor logos "to the point of visual overload" | [F] rollingstoneindia.com, consequence.net |
| 22 | Indian "firsts" (2024-25) | Studio Majime (360 levitation stage, AP Dhillon 2024), Emergence (holographic mesh LED stage), Botlab (drone shows), Xylobands (Coldplay India 2025) | n/a | Mesh LED to cut weight; layered transparent mesh for a hologram look | [F] rollingstoneindia.com (8 Jan 2026) |
| 23 | Coke Studio Pakistan S14-S15 (2022, 2024) | Art director Hashim Ali (S14); directors incl. Kamal Khan, Awais Gohar (S15) | n/a (recorded) | Hand-painted backdrops by poster painters, saturated colour, Wes Anderson/Bhansali comparisons, built in ~2 days | [F] stirworld.com; [S] Wikipedia/Coca-Cola for S15 credits |

Not found despite searching (budget-limited): Beyonce Cowboy Carter (2025) tools/designer; The Weeknd After Hours Til Dawn tools; Travis Scott Circus Maximus
studio; Glastonbury 2024-25 content tools; Tomorrowland 2025 content tools; Treatment Studio 2024-26 specifics; Black Box (studio unclear), Hfour, ENESS, NONOTAK, Ouchhh, Zhestkov
2024-26 live-concert credits (see §4). All UNVERIFIED.

---

## 3. Per-item details (what was done, real-time or not, technique, links)

### 3.1 Sphere shows

**Phish, April 18-21 2024 (Moment Factory).** Four nights, each themed by a state of matter (solids, liquids, gas, plasma), 14 hours of content, 16K x 16K canvas on disguise,
Fuse Technical Group as integrator ("adding servers for real-time delivery") [F: https://blooloop.com/immersive/news/moment-factory-phish-sphere/].
Moment Factory calls it "the longest-ever real-time content show" on that canvas; show director Abigail Rosen Holmes ran it live from a command center [F: https://www.newswire.com/news/phish-live-at-sphere-moment-factory-harnesses-sphere-s-next-generation-22304019 ; the command-center line is from a search summary, [S]].
Split: planned 70/30 pre-rendered to real-time, moved in rehearsal to about 50/50, some visuals also drove lighting fixtures; this comes from Notch's case study as summarised by the search tool, and the case-study page returned 404 for me [S]
(https://notch.one/portfolio/phish-sphere-vegas). Sila Sveta's share: 60+ abstract render loops (Notch, TouchDesigner, Houdini, C4D), drone-footage loops of Cyprus processed in Notch, two Houdini/C4D narrative simulations; up to four hours per C4D frame, about one hour per Houdini frame; the page says the Sphere content was run in real time by the show director, i.e. loops were clips in the live show [F: https://www.silasveta.com/projects/phish-concert-sphere].
**Lesson for PF26:** real-time was used to *extend and improvise around* pre-rendered loops, which matches the DIRECTIONS §0 plan (TD live layer over a DXV3 base).

**Anyma, The End of Genesys (from 27 Dec 2024; ~130,000 attendees over the run).** Visuals credited to Anyma's team including Alessio De Vecchi and Woodblock studio, Unreal Engine, Dolby Atmos [F: https://www.heftig.com/virtual/anyma-at-the-sphere/].
A second article lists Unreal Engine 5 (Nanite/Lumen), Notch, TouchDesigner, disguise, C4D, Houdini and Stable Diffusion, but contradicts itself on real-time vs pre-rendered and names no studio, so treat as low reliability [F: https://ymcinema.com/2025/01/30/the-making-of-anymas-the-end-of-genesys-at-the-las-vegas-sphere-a-groundbreaking-fusion-of-music-and-technology/].
No source I found credits Zhestkov or Ouchhh for Anyma: UNVERIFIED.

**Dead & Company at Sphere (2024)**: ILM made "close to 20 minutes worth of content" (pre-rendered-style wording; mode not classified) [F: https://vfxvoice.com/vfx-in-live-performance-a-vast-visual-feast/]. The same VFX Voice piece (7 Jan 2025) quotes Digital Domain: "Most live performances are driven through Unreal for real-time content", and disguise: Notch renders natively inside Designer, can offload to an RX machine via RenderStream, and disguise "sees a lot of Unreal Engine usage" plus TouchDesigner and Unity integrations [F].

### 3.2 Tours

**Billie Eilish, Hit Me Hard and Soft (2024-25).** Moment Factory did creative direction, production design, content production, show direction; content is "pre-rendered visuals that alternate between glitchy and fluid"; lo-fi; themes water, infinity, abyss; camera shots of the performer are built into the content; LED floor, 8 towers, shape-shifting overhead screens [F: https://momentfactory.com/products/billie-eilish-hit-me-hard-and-soft-the-tour]. GMUNK Studio made content for "Over Now", "Wildflower", "Chihiro" and says explicitly the visuals are pre-rendered [F: https://toolofna.com/experience/talent/gmunk/billie-eilish-world-tour/].

**Cesare Cremonini 2025 stadium tour (NorthHouse).** 65 m panoramic screen, Unreal previs for camera placement, Notch as a live instrument with disguise keyframes and a MIDI controller driving Alembic animation, Cloner Effectors, blend modes and live grading; sequences rendered on a farm, composited, then built into Notch Blocks. Florian Lecoq: Notch gave "100% live" control [F: https://notch.one/madewithnotch/cesare-cremonini-2025]. Hybrid recipe: bake the heavy part, expose the look as parameters.

**Harry Styles Love On Tour (Silent Partners Studio).** Avoided realistic video; vivid palette; vintage film and classic optical effects, "non-digital feel". Heath Saunders used **TouchDesigner to test Notch Blocks**, built **one large Block for the whole show with each look on its own layer**, and set up a workflow so the D3 programmer could drive Block parameters from the lighting console; he could connect to the Block over the network for last-minute notes in rehearsal [F: https://www.notch.one/madewithnotch/harry-styles-love-on-tour]. Silent Partners' 2025 work found: Justin Timberlake Forget Tomorrow tour opening (3D, live action, VFX, AI-driven design) [S: https://www.appliedartsmag.com/winners/photography/justin-timberlake-forget-tomorrow-world-tour-opening-w4/?year=2025], no RT/TD statement.

**FKJ World Tour 2022-24 (NorthHouse).** Feedback loops from recorded footage for a "wispy tail", Notch Sound Modifier + Time Stretch tying clouds to beats, Pixel Sorting Glitch, Dither, Cloner for kaleidoscopes; tool list includes TouchDesigner (role not stated) [F: https://notch.one/madewithnotch/fkj-world-tour-22-24].

**Metallica M72 (Nocte Studio).** Most content pre-rendered in Notch; 3D previs UV-matched to the pixel map; NDI from After Effects into Notch for in-context preview; moving spotlights projecting a pre-sequenced layer plus an audio-reactive detail layer; two distinct visual sets for the two back-to-back nights per city, no setlist repeats [F: https://www.notch.one/madewithnotch/metallica-m72-world-tour]. Page has no date: tour years not verified from the page.

**Fred again.. USB002 (Oct 2025 - Feb 2026).** Alexandra Palace finale: four nights, "immersive installation by visual artist Boris Acket" [F: https://whynow.co.uk/read/fred-again-confirms-four-alexandra-palace-shows-for-february-2026]; screens showed phone-filmed everyday moments (rain on a car window) and a shaky live feed of him walking out; dangling red bulbs; blue rectangular keyring covers over phone torches made "a sea of blue" [F: https://www.nme.com/reviews/live/fred-again-alexandra-palace-london-live-review-3493997]; "canopy" over the crowd, no size [F: https://www.alexandrapalace.com/blog/february-26-a-landmark-month-for-music/]. **Correction to avoid:** the 48 m video wall and floating cube/LED pods at the same venue belong to *other* February shows (Fatboy Slim, Solomun), not Fred again.. (the search tool had merged them) [F: same Alexandra Palace page]. No tool credit found. A public Dropbox of USB002 creative files (visual stems, "slo-mo visualizers") exists [S: https://djmag.com/news/fred-again-shares-public-dropbox-folder-filled-usb002-creative-files; page returned 403, details from search summary].

### 3.3 Festivals

**Coachella 2025 (Weekend 1 and 2).**
- Charli XCX: Cour Design, Notch designer/video director Mike Kluge. Effects imitated analogue photography: motion blur, low frame rate, double exposure, lens distortion, strobes; tested on steadicam footage from earlier shows; Notch 3D previs of the stage; "restraint, intervened only at specific moments". Notch "ran all of the actual show" [F: https://www.notch.one/madewithnotch/charli-xcx-coachella-2025].
- Arca: a bullet-time idea for one song shaped the set ("modular towers, each embedded with live cameras"); cutting between camera feeds gave a cubist multi-angle view of Arca and her avatar; exported Notch Blocks sequenced in the Notch-for-Resolume plugin; MIDI on exposed parameters; automated camera sequences overridable live [F: https://www.notch.one/madewithnotch/arca-at-coachella-2025].
- Junior H main stage: whole set built in Unreal "with precise mapping", Notch effects, disguise Designer Pro for 3D simulation, EX3+ server, four weeks concept-to-rehearsal [F: https://www.disguise.one/kr/node/6706]. Render mode not stated.
**Coachella 2024, Dom Dolla + John Summit.** Notch Virtual Background places the artists' live camera feed into minimalist compositions (collage); visuals ramp from simplest to most complex "following the music's arc" [F: https://www.notch.one/madewithnotch/dom-dolla-john-summit-coachella24].

**Tomorrowland Belgium 2025.** The main stage burned before the first weekend; a replacement stage was built in under 48 hours with part of the LED wall from Metallica's touring rig; programme went on "almost unimpeded"; 400,000+ visitors, 16 stages, 850+ artists [F: https://news.pollstar.com/2025/07/29/from-ashes-to-anthem-tomorrowland-overcomes-main-stage-fire/]. The article gives no content or control details. A separate search summary (not fetched) says the original Orbyz stage was 50 m tall and 140 m wide and the replacement 8 m x 70 m [S]. **Reliability lesson:** when the physical stage changes at short notice, content must re-map fast (compare Jade Cicada, `B_visual_techniques.md` §2).

**Glastonbury 2024-25, Beyonce, The Weeknd, Travis Scott:** no usable technical sources found (see §2 note). Beyonce coverage in results describes content (LED text imagery, "film trailers" feel) with no tool credits [S: https://www.ebony.com/5-moments-beyonces-cowboy-carter-tour-family-fire-full-circle-moments/]. UNVERIFIED for tools.

### 3.4 K-pop

Only one source got through: Seoulz (25 Jun 2026) describes a four-layer stack (LED dome, XR/hybrid, synced lightsticks, avatars). PLAVE, a virtual band run by VLAST with backstage performers driving avatars in real time, drew about 37,000 over two nights at Gocheok Sky Dome in Nov 2025; Fanlight makes custom wireless LED lightsticks; BLACKPINK is cited for a physical + virtual-layer hybrid [F: https://www.seoulz.com/korea-concert-tech-2026/]. No tool credits for BLACKPINK, BTS, Seventeen or aespa tours found: UNVERIFIED. (Unreal's PLAVE case study returned 403: https://www.unrealengine.com/spotlights/introducing-plave-the-unreal-engine-powered-animated-korean-boy-band ; its content is known only from a search summary: venue replica in Unreal with virtual LED screens, reviewed in VR from audience seats [S].)

### 3.5 TouchDesigner-specific live evidence 2024-2026

- **y=f(x) lab** (Amsterdam): Mysteryland 2024 mainstage (realtime visuals, custom mapping system, end shows); Carl Cox Evolution 2025 (realtime software syncing visuals, lasers, lighting). Their talk "When Tools Become Instruments" at TouchDesigner Event Tokyo, 22-23 Nov 2025, covers "synchronizing lasers and visuals on Carl Cox's world tour" and "real-time visual tools for festivals" [F: https://www.yfxlab.com ; https://derivative.ca/community-post/touchdesigner-event-tokyo-2025/72796]. The studio page itself does not say TD.
- **PlexusPlay** (Matt DiBiase, post dated 24 Jun 2026): left C4D in 2020 to avoid render times; TD <-> Ableton both ways; TDAbletonSong COMP; Art-Net LED suit with video from TD (823-LED glasses); NDI to FOH lighting; audience voting via mobile web app (2023) and a Playtronica touch controller to trigger a drop; plans interactivity without smartphones because phones fail in large crowds [F: https://derivative.ca/community-post/euphoric-beats-interactive-feats-inside-plexusplay/74647].
- **Quayola, Solar** (post 27 Jan 2026): 200 moving heads follow a KUKA robot arm; shared 3D reference via Alembic from Maya; per-fixture local space; sACN/Art-Net; Ableton OSC straight into TD macros; calibration "a few minutes"; Derivative supplied a custom Pan Tilt CHOP [F: https://derivative.ca/community-post/tracing-sun-quayolas-solar-bentway/73804].
- **Astrum** (Riyadh, NOOR Festival 2025; post 24 Feb 2026): 64 fixtures, 757 celestial bodies tracked, blackouts on over-fast moves, grandMA verifies output, tested on an Apple M2 Air [F: https://derivative.ca/community-post/astrum-turning-riyadh%E2%80%99s-skyline-living-planetarium/73930].
- **Community tutorial** "Concert Visual Effects with TouchDesigner" (18 Nov 2025): MIDI-driven vs audio-driven animation; the Derivative post is a teaser, full text on interactiveimmersive.io (not retrievable by my fetcher) [F: https://derivative.ca/community-post/concert-visual-effects-touchdesigner/73330].
- Older but relevant control pattern: Bad Bunny X100pre (2019) used Resolume as the control surface with a custom TD app translating Resolume's OSC out to the Notch machine, and Notch Glitch effects over OSC [S: https://notch.one/portfolio/bad-bunny-x100-pre ; case study pages not fetched].
- NGHTMRE (T2 Visuals, 2020): TD + Resolume custom media server, TD translated grandMA2 lighting data into Notch [F: https://notch.one/madewithnotch/nghtmre ; https://www.tpimagazine.com/changing-hats-t2-visuals-tanner-thompson/]. Pandemic-era, included as the TD/lighting-data precedent.

### 3.6 Studios you asked about (what I could and could not verify)

| Studio | What I found | Verdict |
|---|---|---|
| Moment Factory | Phish at Sphere (RT + pre-rendered, Unreal/Notch); Billie Eilish tour (pre-rendered) | verified [F] |
| Silent Partners Studio | Harry Styles (Notch Block, TD for testing); JT tour opening 2025 | partly verified; no 2024-26 RT claim |
| Treatment Studio | Founded by Willie Williams and Sam Pattinson; Adele Munich visuals; no 2024-26 real-time claim | UNVERIFIED for RT [S: https://lightborne.com/ and search summary] |
| Sila Sveta | Phish loops; uses Notch, TD, Houdini, C4D | verified [F] |
| NorthHouse | FKJ 2022-24, Cremonini 2025 (Notch live over pre-rendered) | verified [F] |
| Nocte Studio | Metallica M72 content, Notch | verified [F]; undated |
| NONOTAK | Derivative lists them as part of the TD community (2024 post URL seen, not fetched); studio site lists projects with no description | no RT/2024-26 concert detail: UNVERIFIED [F: https://nonotak.com] |
| Ouchhh | Site describes data paintings/AI art; no named projects or tools on the page | UNVERIFIED [F: https://ouchhh.tv] |
| Zhestkov (Maxim Zhestkov) | Studio site lists art/commissions (Playscapes is a real-time artwork); **no Anyma credit found** | UNVERIFIED for concerts [F: https://zhestkov.studio/] |
| ENESS | RUFUS portable LED installation (2014, Red Bull); RUFUS DU SOL "LEDs illuminate in real time with notes on the synth" is from a search summary only | RT claim UNVERIFIED for 2024-26 [S] |
| Hfour, Black Box | Not reachable (hfour.com did not resolve); no usable result | UNVERIFIED |

---

## 4. South Asian and Pakistani concert visual culture

**Honest status:** English-language public coverage rarely credits visual crews or tools in Pakistan. I found no verifiable credit for TD, Notch or Unreal on a Pakistani festival or concert LED stage (agrees with `B_visual_techniques.md` §2 ending). What follows is the visual language *that is documented*, then gaps.

### 4.1 Documented visual language

1. **Hand-made, saturated, layered colour (Coke Studio Pakistan).** Art director Hashim Ali, S14 "Pasoori" and five other songs: each song gets its own set that reflects contemporary Pakistani culture; backdrops were hand-painted over about two days, one by an artist from a family of film and TV poster painters; palette is earthy walls against bright fabrics, with Ali saying colour is natural to Pakistani architecture and textiles and restraint was a Western design-school influence; critics compared it to Wes Anderson with Sanjay Leela Bhansali detail; Kangra miniature painting is named as a collaborative-process reference [F: https://www.stirworld.com/see-lifestyle-visual-design-for-a-world-without-borders]. Coke Studio S15 (Apr-Jul 2024) used a rotating set of directors, one a colourful set evoking inner Lahore [S: https://en.wikipedia.org/wiki/Coke_Studio_Pakistan_season_15].
2. **A visual language per stage and per set (Lollapalooza India 2026).** Festival-wide "cosmic connections" language designed with Aaquib Wani, each of four stages telling its own story; Zoya's visuals used motifs mirroring her musical arc; Fujii Kaze's screen showed English translations of his Japanese lyrics (praised as bridging language); Sammy Virji's visuals leaned into internet-culture irony [F: https://rollingstoneindia.com/lollapalooza-india-2026-review-linkin-park-playboi-carti-kehlani].
3. **Sponsor load is a real complaint.** A 2026 review says logos were "plastered across screens and stages to the point of visual overload" and sign-language interpreters stood where no screen helped them [F: https://concerts.consequence.net/articles/lollapalooza-india-2026-review-photos].
4. **Wolves at Lollapalooza India 2023:** centre 21:9 screen **plus two vertical screens** each side and a flow into the upstage wall; element-themed effects (wind trails for choreographed dance, fire post-filters for solo artists), teal-and-red keyed effects over Japanese-cyberpunk-style characters, iPad Pro touch control, Jackson Wang's looks rebuilt within "an hour of changeover time" [F: https://notch.one/madewithnotch/lollapalooza-india]. (Case study body gives no year; the 2023 date is from the LSI article [F: https://lsionline.com/ground-control-at-heart-of-lollapalooza-india].)
5. **Lighting-led festivals.** Lolla India 2023 ran four stages with 150-250 fixtures each and grandMA3 consoles, lighting plots submitted nearly four months ahead; the LSI piece does not mention video/LED content at all [F: lsionline link above]. So screens are one layer among several there.
6. **Crowd-as-canvas shows.** Coldplay India 2025 used RFID LED wristbands synced to the music [F: https://rollingstoneindia.com/concert-tech-ap-dhillon-stage-drone-show-alan-walker-karan-aujla]; Xylobands also claim 200,000+ fans wearing its bands across Diljit Dosanjh's Dil-Luminati (vendor claim; its page is dated 2016 so verify) [F: https://www.xylobands.com/blog/punjabi-wave-diljit-dosanjh-redefined-arena-spectacle].
7. **"First-of" stagecraft is the market signal:** AP Dhillon's 360-degree levitation stage (Studio Majime, mesh screens to save weight), Emergence's layered transparent mesh "holographic" stage, Botlab drone shows for Alan Walker, Arijit Singh, Karan Aujla; industry value passed INR 100 billion in 2024 (FICCI-EY, as quoted) [F: Rolling Stone India, 8 Jan 2026].

### 4.2 Pakistani acts: what is on record

- Atif Aslam, Dubai Global Village, Apr 2025: the venue's own press release praises "visual effects on the screens" [S]; Karachi, Aug 2025 Independence Day show at Governor House was halted for crowd behaviour (Dawn) [S: https://images.dawn.com/news/1193968]. No tool/visual credit.
- Young Stunners and Hasan Raheem, Dhaka "Carpe Diem: The Takeover" (Oct 2025): one reviewer said the only LED screen looped visuals of the performers; another called the night explosive with no visual detail [S: https://www.tbsnews.net/node/1263496 ; https://online91.thedailystar.net/entertainment/music/news/jalali-set-young-stunners-and-hasan-raheem-headline-memorable-evening]. Weak evidence of what *not* to do: a flat looped IMAG-like screen reads as thin.
- Lahooti Melo 2025 was in **Larkana** (15-16 Feb) [S: https://propakistani.pk/lens/heres-musical-lineup-for-lahooti-melo-2025-in-larkana/]; no visual detail found.
- A self-advertised Pakistani TD VJ (Fiverr, "mcirowave") claims shows for Atif Aslam, Asim Azhar, Hasan Raheem, Young Stunners, Farhan Saeed at ROX Lahore, Uraan Fest etc.: unconfirmed, see `B_visual_techniques.md` §2.
- NH7 Weekender 2024 (Pune, 14-15 Dec): identity was a 3D design language by Rahul Yadav; no stage-visual details [S: https://ianslive.in/nh7-weekender-to-be-held-in-pune-on-december-14-15--20241011125704 ; page not fetched]. Sunburn: no 2024-25 production details found.

### 4.3 What this suggests (inference, not fact)

Local audiences are used to colour-dense, craft-based, narrative sets (Coke Studio), crowd-participation light (wristbands, torches), and stage "spectacle firsts"; the complaints recorded are visual overload from sponsors and thin looped screens. For PRISM's brand rules, colour density must stay inside the orchid/pink/amber spectrum (DIRECTIONS §3), so the *craft/texture* and *lyric clarity* parts transfer more safely than the *multi-colour* part.

---

## 5. Fifteen concrete ideas for PF26 in TouchDesigner

Each is a proposal. All obey: build at 1080x1920 (`CLAUDE.md`), flash limits (`concert-visuals-research/README.md` §4: more than 3 flashes/s over 25% of screen is not allowed; no saturated-red flashing), names/words stay intact and are never produced by TD (`DIRECTIONS.md` §2), full-colour PRISM logo only, brand spectrum rules. Operator names are the ones listed in `ops/TOP.md`; check each against the ops dump before building. Cost: S/M/L = my guess at network size, not a measurement.

| # | Idea | Seen in | TD sketch | Act fit | Cost |
|---|---|---|---|---|---|
| 1 | **Pocket-footage diary strips.** Portrait clips of small everyday moments (rain, steam from chai, rickshaw lights, a hand on a rail), handheld, slightly overexposed, shown as slow vertical strips between songs. Only the team's own footage. | Fred again.. phone-filmed screens [NME] | Movie File In (stored clips, like `media/webcam/webcam_ref_5s.mp4`) -> Level (lifted blacks) -> Noise-driven Displace for handheld wobble -> Cross TOP between 3 slots; Switch on a slider. | Nehaal Naseem (The Soul) | S |
| 2 | **Analogue-damage master stack with one "damage" slider.** Motion blur, low frame rate, double exposure, lens distortion; strobe replaced by a capped-rate brightness step. | Charli XCX Coachella 2025 [Notch] | Cache TOP (hold every n-th frame for 8-12 fps look) -> Composite (add, delayed copy for double exposure) -> Lens Distort -> Feedback/Level. Strobe = Trigger/Limit CHOP with hard max 3 Hz, tested against README §4. | Ali Zafar (The Icon) as a flash-free "camera flash" accent; Mustafa Zahid | S-M |
| 3 | **Performer feed in glass frames** (IMAG treated as design). Duotone/palette-mapped camera feed inside portal shapes, never covering a name. | Dom Dolla Virtual Background [Notch]; Billie camera-in-content [Moment Factory] | NDI In or Video Device In (D_camera_mediapipe.md) -> person mask via the arm64 helper or Chroma Key -> Lookup (brand gradient) -> Composite into masked shapes. Stored clip fallback. | Hasan Raheem, Mustafa Zahid | M |
| 4 | **Bullet-time across the nine faces.** One feed, each face shows it delayed by n frames, producing a travelling "multi-angle" ripple from L1 to R1 on a key moment. | Arca's tower cameras, cubist cuts [Notch] | One Cache TOP; per-face Select with different `Cache Step`/index offsets; atlas assembled like `mapping.py`. Test at 1080x1920 per face crop first. | Mustafa Zahid (The Rockstar) | M |
| 5 | **One show Block.** A single TD COMP: one layer per look, every look reads shared custom pars (Intensity, Hue shift, Arc, Hold) so a panel, MIDI later, or OSC from Arena can drive it without rebuilding. | Harry Styles single Notch Block, params from console [Notch]; Bad Bunny OSC translation [S] | Matches `SHOW_PANEL.md`; add an OSC In DAT stub to receive Arena clip-trigger messages (needs verified OSC addresses; Arena operations need the user's go-ahead). | all | M |
| 6 | **Lyric-translation line.** A bottom-third text layer cued by the operator that shows a translated or transliterated line (Urdu with English, or the reverse) in time with the song. | Fujii Kaze translated lyrics, Lolla India 2026 [RS India] | Table DAT of lines + cue index -> Text TOP (Urdu shaping verified in A §2-5). **Only text supplied by the client/artist; no calligraphy from TD** (names-words rule). Permission and licensing for lyrics is an open question. | Hasan Raheem, Abdul Hannan | S |
| 7 | **Hand-painted poster theatre.** 3-5 flat cut-out layers from a hand-painted/poster-style source (the user's own or Flow output) with slow parallax, grain, paper shimmer, kept to the brand spectrum. | Coke Studio hand-painted backdrops, poster painters [Stirworld] | Layers as Movie File In with alpha -> Transform with Noise CHOP drift -> Displace by a low-res noise -> Composite; camera dolly via one Transform master. Cheap at 1080x1920. | Abdul Hannan (The Heartthrob), Nehaal Naseem | S |
| 8 | **Beam telemetry for lighting.** The on-screen "one beam" exports its x, y, angle as a CHOP so a lighting operator or console can follow it over sACN/OSC; screen and lights then move as one gesture. | Quayola *Solar* (shared 3D reference, sACN), *Astrum* (sACN, safety), y=f(x) lab Carl Cox [Derivative] | Beam position as 3 channels -> Null CHOP -> OSC Out/sACN (DMX Out CHOP). Needs the lighting designer's agreement and universes; do not output until the user says go. | Finale (Ali Zafar) | M |
| 9 | **Elastic holds.** A bed with no fixed end: a slider stretches time with a slow, non-repeating drift, so a 60 s bed can run through a long changeover or jam without a visible loop point. | Phish: Notch chosen so visuals could stretch with long jams [F: newswire/Notch summary] | Noise with `time` from a Speed CHOP (slider = speed) plus a slowly walking seed so no frame repeats; Feedback for body. Keep a pre-rendered loop of the same bed as the fallback. | the four changeovers (30/25/20/15 min) | S |
| 10 | **Complexity arc over a 60-minute set.** One `Arc` parameter ramps 0-1 across the set; every look reads it (particle count, layer count, motion speed), so the show goes from "simplest to most complex" without new content. | Dom Dolla set arc [Notch] | Timer CHOP or a slider; Math CHOP maps `Arc` to counts; also useful for the A03-style 5-minute countdown bed. | all five acts | S |
| 11 | **Glitch-to-fluid dial.** One slider crossfades two states of the same image: pixel-sort/dither glitch and smooth fluid displacement. | Billie "glitchy and fluid", lo-fi [Moment Factory]; FKJ pixel-sort + dither [Notch] | GLSL TOP for sort/dither (GLSL on macOS = Vulkan, A §2) vs Optical Flow + Displace feedback for fluid; Cross TOP. Check pixel-sort cost at 1080x1920 first. | Mustafa Zahid, Ali Zafar | M |
| 12 | **Phone-torch constellation.** If a crowd camera is allowed, bright phone lights become stars that connect by thin lines in the screen; the crowd draws the sky. No faces shown. | Fred again.. torch covers "sea of blue" [NME]; wristband shows in India [RS India]; D crowd ideas | Video In/NDI -> Luma Level + Threshold -> Blob Track (works on Mac per D §) -> POP/instancing points + line connections. Stored-clip fallback; needs a safe camera position. | Hasan Raheem (The Main Character) | M-L |
| 13 | **Kick-punch with a cap.** On kick envelopes: scale punch, RGB split, short shockwave ring, all rate-limited and brightness-capped. | General hip-hop/EDM convention; RGBSplit is the td-port pilot | Audio Device In -> Analyze -> Trigger CHOP -> Limit; drives Transform scale and the td-port RGB split; hard cap on repeats per second. Needs audio feed (E_live_rig). | Hasan Raheem, Abdul Hannan | S |
| 14 | **Logo-quiet sponsor bed.** A sponsor state whose motion lives in the background and leaves a fixed clean slot for the full-colour logo as supplied; no logo layers stacking. | Lolla India 2026 sponsor overload complaint [Consequence] | Bed generated in TD with a reserved mask area (Rectangle TOP) at the logo slot; logo comes from HyperFrames/Arena, not TD. | all (sponsor slots) | S |
| 15 | **One shader, five "phases".** A single base look whose parameters (frequency, threshold, feedback, grain) cross-map to five set identities, the way Phish gave each night a state of matter, so five acts share one tuned network. | Phish four nights x four states of matter [blooloop] | Preset table (Table DAT or Preset COMP) maps Phase -> custom par values; Cross or Lerp between presets with a Lag CHOP for smooth set-to-set change. Colours stay inside the PRISM spectrum rule. | each act gets a phase | M |

Not recommended: LED wristband and drone shows (hardware vendors, not TD work); real-time AI diffusion (the only Anyma AI claims come from a low-reliability article; and `T_realtime_ml.md` exists for that route).

---

## 6. Open questions for the lead

1. Do you want a Pakistani-specific visual-language review from a native source (a director from Coke Studio or a local VJ)? Public web text gave me little, and English-language Pakistani coverage of concert screens is almost silent on production.
2. Is a crowd-facing camera (ideas 3, 12) allowed at PF26, and where would it sit? If not, ideas 3 and 12 stay stored-clip only.
3. Do we have artists' permission and text for lyric lines (idea 6)? Which languages per act (Urdu script, Roman Urdu, English)?
4. Will the lighting designer accept beam telemetry over sACN/OSC (idea 8), and which universes are free?
5. Do you want me to retry the unfetchable primary sources when the search budget refills (Notch Phish case study returned 404, Bad Bunny case study not fetched, Unreal PLAVE returned 403)?
6. Which 3 of the 15 should be built first? My ranking by value per effort: 10 (Arc), 9 (elastic holds), 5 (Block), 7 (poster theatre), 2 (analogue damage).

---

## 7. Sources

Fetched `[F]` (read in this session):
- Notch Charli XCX Coachella 2025: https://www.notch.one/madewithnotch/charli-xcx-coachella-2025
- Notch Arca Coachella 2025: https://www.notch.one/madewithnotch/arca-at-coachella-2025
- Notch Dom Dolla + John Summit Coachella 2024: https://www.notch.one/madewithnotch/dom-dolla-john-summit-coachella24
- Notch Cesare Cremonini 2025: https://notch.one/madewithnotch/cesare-cremonini-2025
- Notch Harry Styles Love On Tour: https://www.notch.one/madewithnotch/harry-styles-love-on-tour
- Notch FKJ world tour: https://notch.one/madewithnotch/fkj-world-tour-22-24
- Notch Metallica M72: https://www.notch.one/madewithnotch/metallica-m72-world-tour
- Notch NGHTMRE: https://notch.one/madewithnotch/nghtmre
- Notch Lollapalooza India: https://notch.one/madewithnotch/lollapalooza-india
- disguise Junior H case study: https://www.disguise.one/kr/node/6706
- VFX Voice, 7 Jan 2025: https://vfxvoice.com/vfx-in-live-performance-a-vast-visual-feast/
- Moment Factory Billie Eilish: https://momentfactory.com/products/billie-eilish-hit-me-hard-and-soft-the-tour
- GMUNK Billie Eilish: https://toolofna.com/experience/talent/gmunk/billie-eilish-world-tour/
- Blooloop Phish: https://blooloop.com/immersive/news/moment-factory-phish-sphere/
- Newswire Phish: https://www.newswire.com/news/phish-live-at-sphere-moment-factory-harnesses-sphere-s-next-generation-22304019
- Sila Sveta Phish: https://www.silasveta.com/projects/phish-concert-sphere
- HEFT!G Anyma: https://www.heftig.com/virtual/anyma-at-the-sphere/
- YM Cinema Anyma (low reliability): https://ymcinema.com/2025/01/30/the-making-of-anymas-the-end-of-genesys-at-the-las-vegas-sphere-a-groundbreaking-fusion-of-music-and-technology/
- Pollstar Tomorrowland: https://news.pollstar.com/2025/07/29/from-ashes-to-anthem-tomorrowland-overcomes-main-stage-fire/
- NME Fred again..: https://www.nme.com/reviews/live/fred-again-alexandra-palace-london-live-review-3493997
- Why Now Fred again..: https://whynow.co.uk/read/fred-again-confirms-four-alexandra-palace-shows-for-february-2026
- Alexandra Palace blog: https://www.alexandrapalace.com/blog/february-26-a-landmark-month-for-music/
- y=f(x) lab: https://www.yfxlab.com
- Derivative Tokyo 2025: https://derivative.ca/community-post/touchdesigner-event-tokyo-2025/72796
- Derivative PlexusPlay: https://derivative.ca/community-post/euphoric-beats-interactive-feats-inside-plexusplay/74647
- Derivative Quayola Solar: https://derivative.ca/community-post/tracing-sun-quayolas-solar-bentway/73804
- Derivative Astrum: https://derivative.ca/community-post/astrum-turning-riyadh%E2%80%99s-skyline-living-planetarium/73930
- Derivative concert visuals post: https://derivative.ca/community-post/concert-visual-effects-touchdesigner/73330
- TPi T2 Visuals: https://www.tpimagazine.com/changing-hats-t2-visuals-tanner-thompson/
- Seoulz Korea concert tech: https://www.seoulz.com/korea-concert-tech-2026/
- Rolling Stone India Lolla 2026: https://rollingstoneindia.com/lollapalooza-india-2026-review-linkin-park-playboi-carti-kehlani
- Rolling Stone India concert tech (8 Jan 2026): https://rollingstoneindia.com/concert-tech-ap-dhillon-stage-drone-show-alan-walker-karan-aujla
- Consequence Lolla India 2026: https://concerts.consequence.net/articles/lollapalooza-india-2026-review-photos
- LSI Lollapalooza India lighting: https://lsionline.com/ground-control-at-heart-of-lollapalooza-india
- Stirworld Hashim Ali: https://www.stirworld.com/see-lifestyle-visual-design-for-a-world-without-borders
- Xylobands Dil-Luminati: https://www.xylobands.com/blog/punjabi-wave-diljit-dosanjh-redefined-arena-spectacle
- Studio sites: https://zhestkov.studio/ , https://ouchhh.tv , https://nonotak.com

Search summaries only `[S]` (leads, not read in full): Bad Bunny https://notch.one/portfolio/bad-bunny-x100-pre ; Phish Notch case study https://notch.one/portfolio/phish-sphere-vegas (404 on fetch) ; Silent Partners/JT https://www.appliedartsmag.com/winners/photography/justin-timberlake-forget-tomorrow-world-tour-opening-w4/?year=2025 ; Treatment https://lightborne.com/ ; Coke Studio S15 https://en.wikipedia.org/wiki/Coke_Studio_Pakistan_season_15 ; Lahooti Melo https://propakistani.pk/lens/heres-musical-lineup-for-lahooti-melo-2025-in-larkana/ ; Atif Aslam Karachi https://images.dawn.com/news/1193968 ; Dhaka reviews https://www.tbsnews.net/node/1263496 and https://online91.thedailystar.net/entertainment/music/news/jalali-set-young-stunners-and-hasan-raheem-headline-memorable-evening ; Fred again.. Dropbox https://djmag.com/news/fred-again-shares-public-dropbox-folder-filled-usb002-creative-files ; Unreal PLAVE https://www.unrealengine.com/spotlights/introducing-plave-the-unreal-engine-powered-animated-korean-boy-band ; Beyonce https://www.ebony.com/5-moments-beyonces-cowboy-carter-tour-family-fire-full-circle-moments/ ; NH7 https://ianslive.in/nh7-weekender-to-be-held-in-pune-on-december-14-15--20241011125704.

No reference images were saved (none needed; `refs/S/` not created).
