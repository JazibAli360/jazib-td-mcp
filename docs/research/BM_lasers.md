# BM - Lasers (ILDA) from TouchDesigner: landscape, how it works, clean-room build spec

Researched 26 Oct 2026 (offline research lane: web, GitHub, docs.derivative.ca, the app's own offline help and OP Snippets;
TD NOT touched, no `jazib-td` tool called, nothing downloaded was run). Build target TD 2025.31550 (`/Applications/TouchDesigner 2.app`,
x86_64 / Rosetta), macOS Apple Silicon. General-purpose TD; PRISM/PF26 not a factor (the old "laser rays denied" look rule in
O/P/B files is a PF26 aesthetic rule, irrelevant here).
Local evidence (read-only): `research_src/BM_lasers/` = `snippet/` (Derivative's own `laserCHOP.tox` OP Snippet, `toeexpand`ed, text only),
`ilda/` (ILDA IDTF14 rev 011 PDF + text pulled with stdlib zlib, no PDF tool), `yt/` (one auto-caption transcript).

## 0. Top findings (read this first)

1. **TD 31550 already has the whole laser stack, on macOS.** `laserCHOP` (path generator: blanking, corner hold, step size),
   `laserdeviceCHOP` (sends to EtherDream / Helios / ShowNET), `etherdreamDAT` (device list), `pangolinCHOP` (Windows only).
   Proof it is not Windows-only for the first two: the app ships `libLaserCHOP.dylib` + `libHeliosLaserDAC.dylib` (+ libusb) in
   `Contents/Frameworks` for BOTH apps: `TouchDesigner.app` (arm64) and `TouchDesigner 2.app` (x86_64, our build). Operator pages
   state no platform limit except Pangolin ("only supported under Microsoft Windows"). Still UNVERIFIED live (nobody has created the ops on this
   Mac; earlier dump `docs/research/ops/` skipped them): step 1 of the live check.
2. **Our value-add is NOT re-implementing the DAC drivers.** It is: (a) one self-contained COMP that turns any source (SOP, POP, CHOP,
   TOP-trace, text, audio scope) into clean laser paths with sane defaults and its own controls; (b) a **hardware-free test bench**
   (physics-based beam preview, fake DACs on loopback, ILDA round trip); (c) the adapters TD lacks: **LaserCube** (UDP, protocol
   public + MIT reference), **ILDA .ild export/record**, and an optional own draw-order optimiser the native op does not have.
3. **TD 2025.30000 rewrote the Laser CHOP** (with LaserAnimation Sollinger): corner vs guide points (`LasCorner`), per-point hold
   (`LasCornerHoldAdd` / `...LookupFactor`), internal generation at 192000 Hz then resampled to `outputrate`, direct POP input, `starthold`
   removed. Old files need Step Size / Blanking Step Size retuned. Laser Device CHOP got Helios SDK 11 (IDN adapter, 16-bit + 4 user
   channels on "extended frames").
4. **No draw-order optimisation in the native op** (it blanks between shapes in input order). Path ordering is the biggest free win for
   galvo throughput (open-source reference: `lasy`, MIT, implements Abderyim et al.). That is the heart of our spec.
5. Community assets are mostly **Windows-era, TD 099/2018-2022, unlicensed or donationware**: useful as prior art only. Nothing adopted.
6. **Scanner physics is the real constraint, not software** (galvo bandwidth: sharp corners need dwell, blank/colour timing mismatch
   makes tails, kpps rating is a guideline at a given angle). Documented in section 3; we build NO limiter (operator decides),
   only visible read-outs.

## 1. Landscape (ranked)

Licence column: "n/s" = not stated. User rule: licences are irrelevant for research; noted anyway.

| # | Tool / asset / repo | What | Platform / 31550 | Licence | Verdict |
|---|---|---|---|---|---|
| 1 | **Laser CHOP** (`laserCHOP`, built in) https://docs.derivative.ca/Laser_CHOP | SOP/POP/CHOP -> sample stream (x,y,r,g,b[,i]) with blanking, corner hold, step size; ILDA-style point generation | in 31550, dylib present on Mac (arm64 + x86_64) | TD licence | **Use as the engine** (mode "Native") |
| 2 | **Laser Device CHOP** (`laserdeviceCHOP`) https://docs.derivative.ca/Laser_Device_CHOP | sends samples to `etherdream` / `helios` / `shownet`; queue time, X/Y/RGB/intensity scale; replaces EtherDream CHOP + Helios DAC CHOP (2023) | in 31550; Helios via libusb dylib in app | TD licence | **Use for those DACs** |
| 3 | EtherDream DAT https://docs.derivative.ca/EtherDream_DAT | lists DACs found by UDP broadcast (Poll Devices + callbacks) | in 31550 | TD | use for discovery |
| 4 | **OP Snippet `laserCHOP.tox`** (in the app: `.../OPSnippets/Snippets/CHOP/laserCHOP.tox`) | Derivative's examples: 3D object, audio, chop, text, dashed lines, open shapes, **`laserPreview`** (draw-the-path sim) and a trace-an-image chain (Movie In -> res -> blur -> level -> lookup(steps) -> Trace SOP -> Laser CHOP) | in app; expanded and read | TD | **best prior art**; copy ideas |
| 5 | Pangolin CHOP (`pangolinCHOP`) https://docs.derivative.ca/Pangolin_CHOP | sends SOP/CHOP/POP to Pangolin Beyond (zones, rate mode, vector frame, enable/disable/blackout pulses) | **Windows only** (docs); Beyond must run; NC licence = Beyond demo only | TD | gated (FUTURE) |
| 6 | TouchDesigner and Lasers (Daniel Dalfovo, 20 Dec 2020, asset 63736) https://derivative.ca/community-post/asset/touchdesigner-and-lasers/63736 + repo https://github.com/danieldalfovo/Laser-Control (53 stars) | 3 YouTube parts (setup, Laser CHOP, many lasers over AVB); `Laser.toe`, `pathCreator.tox`; Copy SOP stamping, coloring-by-TOP component | built for the OLD Laser CHOP era; needs LA-Toolbox + RME/MOTU AVB hardware; macOS has AVB built in (docs) | none (README: "free to use") | prior art only; transcript gives practical rules (section 2) |
| 7 | More about Lasers and TouchDesigner (Elburz / Interactive & Immersive HQ, 21 Mar 2025, asset 71583) | teaser; full article on interactiveimmersive.io (not fetched past teaser) | n/a | n/s | skip |
| 8 | Laser Cube Ethernet/LAN/WiFi script (NairoDorian, Sep 2021, asset 65251) https://github.com/NairoDorian/Laser-Cube-TouchDesigner (32 stars) | Python DAT script + TDAsyncIO inside `TD_LASER_CUBE_WIFI_LAN(_2022).toe`; params cube IP, rate (default 30000, 34500 suggested), intensity, scale, ON/OFF; 2 cubes in parallel 10+ h | TD 2022-era; untested here | none in repo | **not loaded**; we write our own from the public protocol |
| 9 | Wickedlasers `Laser_OS_TouchDesigner` https://github.com/Wickedlasers/Laser_OS_TouchDesigner (40 stars, 2021) + `colinstokes/Laser-OS_cross-platform` (2025-09, "macOS Intel + Apple Silicon") | C++ CHOP plugin for LaserCube/LaserDock via Laser OS | Windows (orig), macOS in the fork; unsigned binary plugin: audit first | n/s | gated (needs plugin audit, user OK) |
| 10 | `tgreiser/etherdream-touch-designer` https://github.com/tgreiser/etherdream-touch-designer (123 stars, MIT, 2023); `Ferrous256/etherdream-touchdesigner` (MIT 2016); `tgreiser/helios-touchdesigner` (MIT 2017) | old DAT/Script-CHOP drivers + "#LaserHack 101" PDF; README rules: set queue time as low as possible without flicker, open UDP 7654 inbound, **Mac may need manual IP config**, rating e.g. 30K pps @ 8 deg | superseded by Laser Device CHOP | MIT | prior art for troubleshooting notes |
| 11 | `tgreiser/laser-juice` https://github.com/tgreiser/laser-juice (44 stars, GPL-3.0, 2020, donationware) | TD abstract-ILDA generator, space bar = stop, calibration (scale freq) | TD 099, Windows (Laser OS) | GPL-3.0 | prior art |
| 12 | `stith/eostre-spirits` https://github.com/stith/eostre-spirits (MIT, 2025-03) | webcam blob track (OpenCV) -> 3x3 grid warp (lens + galvo-space correction) -> shapes on points -> laser | TD patch, any DAC | MIT | good pattern for the optional `Warp` stage |
| 13 | `TonilK/TD_099_CitpCaex` https://github.com/TonilK/TD_099_CitpCaex | CITP/CAEX (UDP+TCP) laser feed into Capture visualiser | 2018 build, beta | n/s | gated idea (visualiser export) |
| 14 | `nannou-org/lasercube` https://github.com/nannou-org/lasercube (MIT; `SPECIFICATION.md`) | **public LaserCube UDP spec** (reverse engineered): ports 45456/45457/45458, commands, point packing | Rust, protocol only | MIT | **our protocol source** |
| 15 | Ether Dream protocol https://ether-dream.com/protocol.html | TCP 7765 control, UDP broadcast 1/s, 18-byte points | protocol only | open hardware | reference + fake server in tests |
| 16 | Helios DAC SDK https://github.com/Grix/helios_dac (131 stars, MIT text in `sdk/cpp/LICENSE.md`; hardware licence forbids selling units; GitHub says NOASSERTION) | USB VID 0x1209 PID 0xE500, 12-bit xy, max 4095 pts/frame (8192 over IDN), pps 7..65535 (100000 IDN), mgmt port 7355; `libusb` binaries incl. Mac | Mac supported by SDK | MIT (sdk) | reference |
| 17 | `lasy` https://github.com/nannou-org/lasy (MIT) | path optimisation lib: graph optimisation, draw-order, blanking delays, sharp-angle delays (Abderyim et al., *Accurate and Efficient Drawing Method for Laser Projection*, https://art-science.org/journal/v7n4/v7n4pp155/artsci-v7n4pp155.pdf) | Rust | MIT | algorithm reference for our optimiser |
| 18 | Halabi and Chiba, vector-oriented laser drawing (https://iwate-u.repo.nii.ac.jp/record/9737/files/dis-v30i3p97-106.pdf) | constant beam intensity, blanking timing from a delay test pattern, corner dwell by angle to avoid overshoot/ringing | paper | n/a | basis for dwell + delay-calibration |
| 19 | ILDA IDTF14 rev 011 https://www.ilda.com/resources/StandardsDocs/ILDA_IDTF14_rev011.pdf ; IDN-Stream rev 002 (Jul 2025) https://ilda.com/resources/StandardsDocs/ILDA-IDN-Stream-rev002.pdf | file format + network stream standards | standards | free PDFs | IDTF read and verified; IDN-Stream not read (gated) |
| 20 | LA.laserchop (LaserAnimation Sollinger, paid, mentioned on the Laser CHOP page); AVB2ILDA box | extended commercial path; 24-bit AVB output, masking, geometric correction, per-colour delay | n/a | paid | not needed |
| 21 | Liberation Laser (https://docs.liberationlaser.com) | free/paid laser software (DAC list: LaserCube USB + network from 0.7.3) | n/a | n/s | use only as a hardware cross-check |
| 22 | Rust `td-rs` fork with Lasercube CHOP (`thatmarcel/touchdesigner-plugins`, from `AN_awesome_touchdesigner.md`) | compiled CHOP plugin | Rosetta needs x86_64 build | n/s | gated (arch + audit) |

Verified negative: no laser POP exists in 31550 (only POP *inputs* to Laser CHOP and Pangolin CHOP); `scanCHOP` is deprecated (use Laser CHOP);
`etherdreamCHOP` and `heliosdacCHOP` are deprecated into Laser Device CHOP; no LaserCube or IDN type in the Laser Device menu (Helios SDK 11 can
send IDN, exposed as Helios devices only: "Helios can also send to all IDN devices, including the Helios OpenIDN adapter" per the Lasers page).

## 2. How it works in TD

### 2.1 The 5 documented pathways (https://docs.derivative.ca/Lasers, rev 36904, 4 Nov 2025)
1 EtherDream (Ethernet + ILDA cable) -> Laser Device CHOP. 2 Helios (USB; also all IDN devices incl. OpenIDN over Ethernet) -> Laser Device CHOP.
3 ShowNET (Ethernet, on-board DAC) -> Laser Device CHOP. 4 LaserAnimation Sollinger AVB: Laser CHOP -> **Audio Device Out CHOP** (MOTU, RME, USB2AVB, macOS
built-in AVB; AVB2ILDA adds 24-bit, masking, colour delay, geometry). 5 Pangolin Beyond: any source -> Pangolin CHOP (Windows).

### 2.2 Data contract (Laser CHOP / Laser Device CHOP channels)
`x`,`y` in [-1,1]; `r`,`g`,`b` in [0,1]; `i` [0,1]; `user1..user4` optional (EtherDream has no user3/4). Blank = r=g=b=0 (or all three colour scales 0).
Frame Start Pulse (`startpulse`) inserts a sample with all colours -1. Info CHOP: `sample_rate`, `num_channels`, etc.

### 2.3 Laser CHOP: what each parameter does (docs verbatim names)
- Inputs by path pars, not wires: `source` (sop/chop/pop) + `sop`/`chop`/`pop`. CHOP input needs `x`,`y`; optional `z`,`r`,`g`,`b`,`id` (same id = one shape; no `id` = every point separate), `lascorner`, `lascornerholdadd`, `lascornerholdlookupfactor`. Other channels pass through as colours (blanked with the beam). SOP: points grouped by primitive; POP: `P` + `Color`.
- `outputrate` (default 48000; 60 fps -> 800 points/frame), `swap`, `xscale`, `yscale`, `rotate`, `camera` (to view a SOP), `updatemethod` (`alldrawn` default / `everyframe`; Every Frame avoids flicker when a picture needs more than one frame), `startpulse`, `debugchan` (-1 pulse, 0 colour, 1 corner hold, 2 start hold, 3 pre-blank on, 4 post-blank on, 5 blanking, 6 pre-blank off, 7 post-blank off).
- Scanning: `stepsize` (max x,y change per sample while drawing), `bstepsize` (while blanked), `mincornerhold` (shallow angles; 180 deg gives the minimum), `maxcornerhold` (sharp, 0 deg gives the max), `cornerholdchop` (custom curve), `closedoverlap` (ms).
- Colour: `redscale` `greenscale` `bluescale`, `preblankon` / `postblankon` / `preblankoff` / `postblankoff` (ms), `colordelay` (ms), `interpcolors`, `brightnesscurvechop` (soft edge of closed shapes). `starthold` removed in 2025.30000.
- Corner repeat formula: `NumRepeatPoints = HoldAdd + HoldLookupFactor * H` with H from the angle and min/max hold. Guide points are emitted once; corner points are repeated (this is how a sharp corner stays sharp without wasting points on curves).
- Since 2025.30000 points are generated at 192000 and resampled to `outputrate`.

### 2.4 Laser Device CHOP pars
`active`, `type` (etherdream/helios/shownet), `device` (menu for Helios/ShowNET), `scan` (pulse; close active Helios first), `netaddress`, `port` (EtherDream), `localaddress` (NIC choice), `queuetime` + `queueunits` (samples/frames/seconds), `xscale` `yscale` `redscale` `greenscale` `bluescale` `intensityscale`. Info CHOP reports whether a Helios supports extended frames.

### 2.5 Practical rules from the Laser CHOP tutorial (Dalfovo part 2 transcript, `research_src/BM_lasers/yt/`; spoken, not measured)
A laser is ONE moving point. Step size = point density along a segment (fewer points = dimmer, faster). Vertex hold = how long it stays on a corner (mirrors cannot turn sharply; too long wastes points, too short rounds corners). Blanking: raise the pre-blanking delay; keep Blanking Step Size high to save points; "each laser has its own characteristics: there is no rule", tune by eye with the trail preview. Their laser: 96 kpps.

### 2.6 Why the Derivative snippet matters (read-only expand, `snippet/laserCHOP.tox.dir/`)
`example1/laserPreview` = `laserIn` In CHOP -> Math (map to 0..1) -> Limit SOP (one for the coloured path, one for the output geo) -> two geo COMPs rendered by a Render TOP with a **Line MAT** (width 3, points drawn, point alpha 0.066), plus a Z-offset `pattern1` (length 800, phasestep 0.25) so the path trail shows the beam travelling in "ladders" (corner holds). Examples chop/audio/text/3dObj feed `laser1` with `timeslice on`, `mincornerhold` = `maxcornerhold` = 0.1. `example2` = trace chain (res -> blur -> level -> lookup of stripe ramp -> Trace SOP -> SOP to/CHOP to). Their readme: work at low resolution, blur away detail lasers cannot show, tune stepsize with points displayed.

### 2.7 Protocols we may speak ourselves (all public)
- **ILDA IDTF14 rev 011 (read in the PDF)**: file = sequence of 32-byte headers + records, big endian. Header: bytes 1-4 "ILDA", 5-7 zero, 8 format code, 9-16 name, 17-24 company, 25-26 number of records, 27-28 frame number (from 0), 29-30 total frames, 31 projector number, 32 zero. Formats: 0 = 3D + index colour (8 B: x y z status index), 1 = 2D + index (6 B), 2 = palette (3 B RGB x 2..256), **4 = 3D true colour (10 B: x y z status B G R)**, **5 = 2D true colour (8 B: x(2) y(2) status B G R)**, format 3 never approved. x,y,z signed int16 (left/bottom -32768, right/top +32767); status bit 7 = last point, bit 6 = blanking (1 = laser off; RGB SHOULD be treated as zero when set). Null header (0 records) ends the file. Files are point-oriented (already galvo samples, "NOT raw vector information").
- **Ether Dream** (https://ether-dream.com/protocol.html): TCP 7765; DAC broadcasts status/ID UDP once per second (laser-juice README says open inbound UDP 7654); one host at a time. Commands: `p` prepare, `b` begin (u16 low_water unused + u32 rate), `q` queue rate change, `d` data (u16 n + n * 18 B point `<HhhHHHHHH` control,x,y,r,g,b,i,u1,u2; control bit 15 = change rate), `s` stop, `c` clear e-stop, `?` ping, 0x00/0xFF/any unknown = e-stop. Reply = response byte (`a` ACK, `F` full, `I` invalid, `!` stop condition) + echoed command + 20 B status `<BBBBHHHHHII` (protocol, light engine 0 ready/1 warmup/2 cooldown/3 estop, playback 0 idle/1 prepared/2 playing, source, 3 flag words, buffer_fullness, point_rate, point_count). Order: prepare -> data -> begin; pace with `buffer_fullness`. Byte-order text in the spec contradicts itself: verify on the wire (our fake server fixes one choice; the real device decides).
- **LaserCube** (nannou spec, MIT): UDP; ports 45456 alive, 45457 cmd, 45458 data; broadcast 255.255.255.255 reaches all. `0x77` GET_FULL_INFO (64 B reply: fw, output flag, DAC rate u32 LE at 10, max rate at 14, rx buffer free u16 at 19, rx size u16 at 21, battery, temp, connection type, serial, IP, model), `0x78 n` buffer-size-in-data-reply, `0x80 n` SET_OUTPUT, `0x8a` free sample count (u16 LE at offset 2), `0xa9 00 msg frame` + points, each point 5 x u16 LE (x,y,r,g,b), 12-bit, centre 0x800; **<=140 points per datagram** (1404 B < MTU); buffer about 6000 pts, wait when free < about 5000. No SET-RATE command in this spec: DAC rate is device state (read it, pace to it). Send commands twice (idempotent). Safety timeouts / e-stop are listed as implementation duties by the spec.
- **Helios**: USB bulk (VID 0x1209 PID 0xE500, EP 0x02 out / 0x81 in), `HeliosPoint` x,y uint12, r,g,b,i uint8; extended: uint16 x y r g b i + user1..4; max 4095 pts/frame, pps 7..65535 (IDN: 8192, 100000); flags START_IMMEDIATELY / SINGLE_MODE / DONT_BLOCK. We do NOT reimplement (Laser Device CHOP wraps SDK 11).
- **IDN** (ILDA Digital Network, UDP; Stream rev 002 Jul 2025, IDN-Hello for discovery): not read. Gated.

## 3. Scanner physics (documentation only; NO limits are built)

Facts that decide whether a path looks right. Numbers marked (est) are typical starting points from general knowledge, not measured here: calibrate with the test pattern.
- Mirrors have finite bandwidth: the beam lags the commanded x,y by a roughly constant time (about 100-300 us (est) at small angles) while the colour switches instantly. Result: tails/bright dots at ends of lines. Fix = **colour delay** (shift colour relative to xy) + **pre/post blanking delays** + per-corner **dwell**.
- kpps rating is "points per second at a given optical angle" (hobby scanners 20-30 kpps @ 8 deg, pro 40-60+ kpps @ 8 deg; larger angle = lower reliable rate): a guideline; complex shapes near the angle limit may need lower pps (tgreiser README).
- Points per frame = pps / fps (30000 / 30 = 1000; 48000 / 60 = 800). If the path needs more points than one frame holds, the image takes N frames to draw and flickers (Laser CHOP `updatemethod everyframe` vs `alldrawn` chooses the behaviour). Persistence of vision wants the whole image redrawn at about 25-30+ Hz, more for bright flicker-free (est).
- Corner dwell vs angle: sharp corner needs more samples; straight lines none (matches Laser CHOP min/max hold). Overshoot/ringing is the cost of too few (Halabi/Chiba).
- Beam brightness on screen is proportional to dwell: many points at one place = a bright dot (corners, path starts); long fast strokes are dim. Constant intensity needs even point spacing (step size).
- Open hardware controls (interlock key, shutter, DIP switches, e-stop) are the operator's. TD docs and community assets each carry a safety paragraph; ours appears once in the COMP's readMe text and the doc, nowhere as a software block.

## 4. Clean-room build spec A: `LP_laser_path` (Base COMP, path generator + preview + test bench)

BUILT LIVE v1 (26 Oct 2026, TD 2025.31550): builders/laser_path.py; results in docs/builds/laser_path.md, facts in LEARNINGS T-85

COMP path: **`/project1/lab/LP_laser_path`**. Builder module `builders/laser_path.py`, pure logic `builders/laser_path_logic.py` (ASCII, no `td` import), tests `test/test_laser_path.py`. Idempotent build like `builders/db_meter.py` (T-67 no functions in op storage, T-70 safe destroy, controls panel + `controls_window` opened by `Opencontrols`).
Own code and own design; Derivative's snippet and the public specs above are the references.

### 4.1 Interface (self-contained; Out ops = output only)
- Inputs: `in1` In SOP (shapes), `in2` In CHOP (xy[ rgb id lascorner]), `in3` In TOP (image to trace / luma), `in4` In POP (`inPOP`/`outPOP` exist in the 31550 index; wire it, or use the `Pop` path par since the Laser CHOP itself takes a POP by path). `Source` menu picks one: SOP, CHOP, POP, TOP-trace, Text, Audio scope (L/R as x/y), Test pattern.
- Outputs: `out1` Out CHOP **`laser`**: the final sample stream (`x y r g b i` + `flag` debug), sample rate = `Pps`. `out2` Out TOP **`preview`** (beam simulation picture, `Previewres` square, default 1080x1080... build resolution rule says 1080x1920 for looks; this is a tool picture: `Previewres` default 1080 x 1080, documented). `out3` Out DAT **`stats`** (table: points_total, points_draw, points_blank, frames_per_image, shapes, corners, blank_travel, est_flicker_hz, overflow).
- Custom pars (names one capital then lowercase/digits):
  - Page `Source`: `Source`, `Sop`, `Chop`, `Pop`, `Text`, `Font`, `Tracelevel`, `Traceblur`, `Tracesteps`, `Audiochop`, `Pattern` (circle, square, triangle, star, ILDA-ish test grid, dashed, text, spiral), `Count`, `Size`.
  - Page `Path`: `Engine` (Native / Own), `Pps` (default 30000; no maximum enforced), `Fps` (read-out follows project, editable), `Stepsize`, `Bstepsize`, `Minhold`, `Maxhold`, `Holdadd`, `Closedoverlap`, `Order` (None / Nearest / TwoOpt), `Startpoint` (menu: nearest to centre / first), `Preblankon`, `Postblankon`, `Preblankoff`, `Postblankoff`, `Colordelay`, `Interpcolors`, `Overflow` (menu: draw over several frames / thin the steps / drop the farthest shapes; operator picks, none is "safe").
  - Page `Shape`: `Scalex`, `Scaley`, `Rotate`, `Offsetx`, `Offsety`, `Flipx`, `Flipy`, `Swap`, `Warp` (toggle) + `Warptable` DAT (3x3 grid, eostre-style, TD-side calibration), `Rgb` (colour), `Intensity`, `Gain`.
  - Page `Drive` (control options, none is a limiter): `Intensitysrc` (Manual / BPM LFO / Audio / CHOP), `Bpm`, `Beatdiv`, `Audioch` (path to an audio CHOP), `Audioamt`, `Blackout` (toggle), `Hold` (freeze last image), `Strobe` (Manual / BPM / audio gate) as plain on/off modulations.
  - Page `Preview`: `Galvobw` (Hz, default 6000 (est)), `Galvozeta` (0.7), `Persist` (ms half life, 60), `Glow` (blur px), `Spotgain`, `Showlag` (toggle), `Showblank` (toggle, draws the blanked travel dim), `Bg`.
  - Page `Controls`: pulse `Opencontrols`; pulse `Savesnap` (writes a path+pars snapshot, 4.7).
- Audio rule: the COMP never touches the audio output (Mac speakers stay the default); `Audioch` is an external reference only; mic never routed to speakers.

### 4.2 Engine "Native" (default): wraps the built-in op
`source` stage builds a CHOP with `x y r g b id lascorner` (SOP via `soptoCHOP` per primitive id, POP via `poptoCHOP`, TOP via Trace SOP chain from the snippet, text via Text SOP/Font SOP, audio scope via Math), then **`laserCHOP`** (`outputrate` = `Pps`, `stepsize`, `bstepsize`, holds, blank delays from the COMP pars via expressions). If `Order` != None, a Script CHOP "order" (4.3 stage 3 logic) reorders shapes BEFORE the Laser CHOP (ids renumbered in draw order). Native is the production default because Derivative tunes it with LaserAnimation Sollinger.

### 4.3 Engine "Own": stage-by-stage (Script CHOP + numpy, all logic in `laser_path_logic.py`)
1. **Polylines** (`build_shapes(table)`): input is a flat table `x,y,r,g,b,id,corner` -> list of shapes: points (N,2), colours (N,3), closed flag (first == last within eps or `closed` attr), per-vertex corner flags (default: corner where turning angle > `cornertol`, e.g. 25 deg (est); everything else guide).
2. **Transform** (`apply_xform`): rotate, scale, offset, flip, swap, optional 3x3 warp (bilinear grid in normalised space), x,y clipped to the int16 range only at export, never by value limits.
3. **Order** (`order_shapes`): greedy nearest endpoint with reversal of open shapes and best-vertex rotation of closed shapes, then bounded 2-opt on the shape sequence (budget `Orderms`, default 3 ms, deterministic). Objective = total blanked travel. (lasy / Abderyim "draw order".)
4. **Resample** (`resample_edge`): points along each edge so no sample step exceeds `Stepsize` (draw) / `Bstepsize` (blank); guide points emitted once, corner points get dwell: `repeat = holdadd + round(factor * H)`, `H = lerp(maxhold, minhold, angle/180)` (angle = interior angle at the vertex, 180 = straight, 0 = reversal); closed shapes add `closedoverlap` ms of overlap.
5. **Blank** (`insert_blanks`): between shape A and B: `postblankoff`-style sequence as in Laser CHOP: pre-blank-on dwell at A end (colour still on), colour off + post-blank-on dwell, blanked travel at `Bstepsize`, pre-blank-off dwell at B start (dark), colour on + post-blank-off dwell. All ms -> samples = `round(ms * Pps / 1000)`.
6. **Colour delay** (`delay_colour`): colours shifted `Colordelay` ms relative to xy.
7. **Budget** (`frame_budget`): points per frame = `Pps / Fps`; if total > budget -> `Overflow` policy (documented, operator-chosen, no clamp of values): `stats.overflow` = total / budget; frames_per_image = ceil.
8. **Output**: x,y in [-1,1] float, r,g,b in [0,1], `i`, `flag` (0 colour, 1 corner hold, 3..7 blank phases = same codes as Laser CHOP `debugchan`, so Native and Own compare channel-by-channel).
Why have "Own": hardware-free tests on the exact numbers; ILDA export; LaserCube adapter needs the stream anyway; and an A/B against Native to see what Derivative's tuning does (a diff table of point counts/blank counts in `stats`).

### 4.4 Preview / glow simulator (no hardware) - "what the beam would draw"
Stages (single-pass GLSL or stock ops only, T-46: no multi-pass GLSL chain):
1. **Galvo model** (`galvo_filter(x, y, pps, bw, zeta)`, pure numpy, in the logic module, run in a Script CHOP): 2nd-order low-pass per axis, `omega = 2*pi*Galvobw`, bilinear-discretised at the sample rate. With `Showlag` on the preview is drawn from filtered xy while colour is the unfiltered, delayed stream: tails, rounded corners and overshoot appear exactly when the settings are wrong. With it off, the ideal path.
2. **Dwell brightness**: per sample weight `w = 1 / (eps + speed)` normalised (speed = |delta xy| per sample) so corner holds glow, long strokes are dim (physical: same energy per time, spread over more screen).
3. **Render**: Script CHOP exposes N samples -> Geo COMP with `Copy`-style instancing (instance positions from CHOP, a soft round sprite, colour = rgb * w * `Spotgain`) -> Render TOP, additive blend, `Previewres`. The snippet's Line MAT approach (lines between consecutive samples, width 3, point alpha 0.066) is the cheap fallback; instancing is the physically better one (dwell = pile of sprites).
4. **Persistence**: Feedback TOP + Level (decay from `Persist` half life and the real frame time) + Add. Optional **Blur TOP** for `Glow` (one pass).
5. **Frame-time ghost**: when the image needs N frames to draw, the preview accumulates only the samples of the current frame (so flicker is visible).
Optional later: haze/volumetric fan (fake: radial-blur post), ILDA test-pattern view.

### 4.5 Test patterns / calibration pattern
`Pattern` menu produces deterministic shapes in the logic module (no TD): circle, square, triangle, star, dashed lines, spiral, 3x3 grid of dots, text outline, **delay calibration pattern** (a bright dot sweeping a square at known step size, for tuning colour delay / blanking by eye - the Halabi/Chiba idea). The 8-degree and kpps numbers are the operator's.

### 4.6 Offline-testable logic (`builders/laser_path_logic.py`, pytest, no TD)
Functions + assertions:
- `corner_angle(p0,p1,p2)`: straight = 180, right angle = 90, reversal = 0; `hold_count(angle, minh, maxh, add, factor)` at 180 -> min, 0 -> max, 90 -> mid, monotone.
- `resample_edge(a, b, step)`: number of segments `ceil(dist/step)`, every step <= `step`, endpoints exact, no duplicate vertex between consecutive edges.
- `order_shapes`: result is a permutation; blank travel never longer than input order; on a fixed random seed of 50 scattered segments at least 20% shorter (property test); deterministic; closed shape rotation picks the vertex nearest the previous endpoint.
- `insert_blanks` counts equal the ms->samples formula, flag channel matches 3,4,5,6,7 phases in order.
- `delay_colour`: output colour at i equals input colour at i - d; xy unchanged.
- `frame_budget`: 30000 pps / 30 fps = 1000; 48000/60 = 800; overflow ratio.
- `galvo_filter`: unit step response overshoot for zeta 0.7 about 4.6% (closed form), DC gain 1, stable for omega * dt up to Nyquist; impulse area equals the sum.
- `to_ilda_f5(points, ...)` / `from_ilda(bytes)` **round trip** within 1/32768; header bytes exact (the 32-byte layout above), big-endian, null header at end, status 0x80 on the last point and 0x40 on blanked points, BGR order in records.
- `etherdream_pack_points`, `etherdream_parse_status` (struct sizes 18 and 20 asserted), `lasercube_pack(points, msg, frame)` (<=140 per datagram, header `a9 00 mm ff`, little-endian 12-bit centred 0x800, clamp to 0..4095 on export only), `lasercube_parse_info` against a built 64-byte buffer from the spec.
- Fake DACs for tests in `test/fake_dacs.py` (loopback only): `FakeEtherDream` (TCP, implements the state machine: prepare/data/begin, buffer drain at the point rate, NAK-Full, underflow flag), `FakeLaserCube` (UDP 3 ports on 127.0.0.1 high ports, free-buffer replies). Tests assert the host never overruns the buffer and recovers from a dropped datagram.

### 4.7 Persistence of work (user, 26 Oct: "save your projects always so you don't lose progress, learnings or node setups")
For every builder lane on this spec:
- After each green stage: `td_save_project` (user asked for it, overrides the "don't save unless asked" default in USING_TD.md for this task), plus `td_tox_save` of the COMP to `output/backups/LP_laser_path_<stage>.tox`, plus `td_net_export` JSON snapshot in `snapshots/`.
- Builder source stays in `builders/` (re-runnable, so a lost .toe is rebuildable); `Savesnap` pulse in the COMP writes the current pars + shape tables to `output/laser/<name>.json`.
- Each new live fact or bug goes to `LEARNINGS.md` (T-nn) at once; the build notes and the verification numbers to this file's section 7 or a short addendum.

### 4.8 Controls panel / UI rules
`controls` panel (autoUI from the custom pages, `Pagescope` = Source,Path,Shape,Drive,Preview; widget clones cut so the COMP stands alone) + `controls_window` opened by `Opencontrols`; the Out ops carry no controls. Roles/colours per house rule (input blue, shaping orange, preview green, controls on top of column 0). Layout through `td_layout` flow, check ok. Viewers on; network pane on the COMP while building.

### 4.9 Live verification (TD 2025.31550; name the build in the note; no hardware)
1. Create `laserCHOP` + `laserdeviceCHOP` + `etherdreamDAT` on a scratch COMP (expect no "not supported on this operating system", T-18 style probe). If unsupported on this Mac, Native engine is marked `available:false` and Own engine is the default; record in LEARNINGS.
2. `Pattern=square`, `Pps=48000`, `Fps=60`: `laser` has `sample_rate` 48000 and **800** samples per frame (timeslice off: length 800 at 1 frame); stats.points_total = 800 +- blank padding rules; `debugchan` shows phases 1,3-7 present.
3. Corner count: square has 4 corners; hold_count at 90 deg with min=max=0.1 (snippet default) equals what Native emits (compare flag channel counts Native vs Own for the same pars: expect equality of corner dwell counts and blank counts within +-2 samples; larger gap = a documented difference, not a failure).
4. Draw order: scatter 50 short segments (Pattern=dashed Count=50): `stats.blank_travel` with `Order=TwoOpt` at least 20% below `Order=None`.
5. Preview: `Showlag=0` renders a crisp square (`td_inspect out2` non-black; mean luminance of the 4 corner pixels above the mean of edge midpoints = dwell brightness); `Showlag=1`, `Galvobw=1500`, `Colordelay=0` shows rounded corners and tails (corner overshoot pixels outside the square bbox > 0); raising `Colordelay` shrinks tails (pixel count outside bbox falls monotonically).
6. Fake DAC: with the adapter COMP (section 5) against the pytest fake on loopback: Laser Device CHOP type=etherdream `netaddress` 127.0.0.1 `port` 7765 with the fake started by the builder from a terminal (our own code, user's go-ahead for each run since it opens a local port; no hardware).
7. Audio/BPM drive: `Intensitysrc=BPM` at 120 BPM: `i` channel toggles at 2 Hz (+-1 frame); no sound is routed anywhere.
8. Webcam trace test: stored clip `media/webcam/webcam_ref_5s.mp4` -> `In3` -> Trace chain: `stats.shapes` > 0, `points_total` stable across the loop (+- 15%); live camera only on request.
9. `td_errors` clean after every build; `td_perf`: targets below.

### 4.10 Perf targets and Mac caveats
- Own engine on a 1000-point frame at 60 fps: whole Script CHOP cook < 1 ms (numpy vectorised; 2-opt bounded by `Orderms`); order of 300 shapes inside the 3 ms budget. Native op cook (td_perf) recorded as a number, no target set before measuring.
- Preview 1080x1080: one Render TOP + Feedback + Blur, < 2 ms GPU on M1 Max; keep single-pass GLSL / stock ops (T-46: Vulkan/MoltenVK multi-pass GLSL can tear; compute-mode GLSL is clean, T-47).
- Rosetta: all python is x86_64 3.11 with numpy 2.1.2 and cv2 4.11 (no pip allowed); no mediapipe/onnxruntime needed here. Sockets work from TD Python; threads allowed but never from `td_exec` blocking calls.
- macOS network: Ether Dream needs Ethernet with a link-local/manual IP (laser-juice: "MacOS may require manual IP configuration"); LaserCube in server mode lives at 192.168.1.1 (NairoDorian README) and wants the Mac on that subnet; allow UDP 7654 (EtherDream discovery) in the firewall; `localaddress` par on the Laser Device CHOP picks the NIC. TD under Rosetta cannot load arm64 plugin dylibs (and vice versa): any C++ plugin must be x86_64 (T-18 neighbour; the Rust `td-rs` plugin row).
- USB Helios: libusb dylib in the app; macOS may prompt for USB access; only one process can hold the device.

## 5. Clean-room build spec B: `LO_laser_out` (Base COMP, output adapters; build after A)

COMP path: **`/project1/lab/LO_laser_out`**. Builder `builders/laser_out.py`, logic `builders/laser_out_logic.py` (pack/parse/flow control as pure code; same file as A's wire functions or imported by copy: nothing shared across repos, one copy inside jazib-td-mcp). Takes the `laser` CHOP of A (or any CHOP with `x y r g b [i]`).
- Inputs: `in1` In CHOP. Outputs: `out1` Out CHOP `sent` (what actually left, after scales), `out2` Out DAT `status` (device table: type, address, connected, buffer free/full, dac rate, underflows, packets/s, last error).
- Pars: `Target` (None / TD Laser Device / LaserCube UDP / ILDA record / Fake loopback / Pangolin(gated off on Mac)), `Active` (toggle; default OFF, operator turns on), `Devtype` (etherdream/helios/shownet, forwarded to `laserdeviceCHOP.type`), `Address`, `Cmdport`, `Dataport`, `Queuetime`, `Queueunits`, `Scalex`, `Scaley`, `Redscale`, `Greenscale`, `Bluescale`, `Intscale`, `Rate` (pps pacing for UDP targets, default = device rate read from info), `Blackout` (pulse + toggle: zero colours, keep mirrors alive), `Disarm` (pulse: stop sending and `SET_OUTPUT 0` / EtherDream stop), `Recordfile`, `Record` (toggle), `Recordframes`, `Opencontrols`.
- Stage "TD device": `laserdeviceCHOP` (pars bound to the COMP pars) with the `scan` pulse for Helios. Nothing else added; `etherdreamDAT` for discovery with a callback filling `status`.
- Stage "LaserCube" (clean-room from the nannou/MIT spec, section 2.7): UDP out DAT (`udpoutDAT`, one for cmd, one for data) + UDP in DAT per port for replies; Execute DAT per-frame pacer in Python (pure `laser_out_logic`): discovery by broadcast 0x77 to 45457; on connect send 0x78 01 then 0x80 01 (twice each); every tick compute `free` from the last 0xa9 reply, send chunks of <=140 points while `free` > threshold (default 5000 headroom rule from the spec, a pacing rule not a safety rule); sequence numbers wrap at 255; coordinates: x,y -> int((v*0.5+0.5)*4095) clamped to the 12-bit field only for packing; `Disarm` sends 0x80 00 x2 and stops the pacer. 2-device version = two instances (no shared state).
- Stage "ILDA record": ring buffer of N frames written as format 5 `.ild` into `output/laser/` (header per frame, null header at end), plus a reader for playback tests. Gate: file writes only into `output/laser/`.
- Stage "Fake loopback": same code path as LaserCube/EtherDream but pointed at the pytest fake on 127.0.0.1 (builder runs it in a terminal, never auto-started).
- Controls panel + window as in 4.8. Safety plumbing = operator controls only (Active, Blackout, Disarm); no value caps, no warnings dialogs.
- Offline tests: all pack/parse/flow control in section 4.6; additional: pacer never sends when `free` < chunk size; reconnect after silent device (timeout par `Timeout` default 2 s, resend 0x77).
- Live checks: Fake LaserCube: packets/s about `Rate/140`, no buffer overrun over 5 minutes; Fake EtherDream: status `buffer_fullness` stays between low-water and capacity, `underflow` flag 0; EtherDream real device only with the user present (hardware).
- Perf: adapters < 0.5 ms per frame; sockets non-blocking; no thread left running after `Active` off (check `threading.enumerate()` in td_exec).

## 6. MCP tool ideas (typed; add per docs/EVOLVING.md when a lane needs them)
- `td_laser_probe` (read-only): creates `laserCHOP`, `laserdeviceCHOP`, `etherdreamDAT` in a scratch COMP, returns {created, par names, build, errors}, then removes them. Answers "supported on this Mac?" in one call.
- `td_laser_path {comp, pattern, pps, fps}`: runs the Own engine on a pattern and returns the stats table + a PNG of the preview (no device).
- `td_laser_export_ilda {comp, frames, file}` writes `.ild` under `output/laser/` and returns point counts + checksum; `td_laser_import_ilda {file}` loads frames into a Table DAT / CHOP for preview.
- `td_laser_devices` (read-only): runs the `etherdreamDAT` poll and the Helios `scan` flag logic and returns a device list; never sets `active`.
- `td_laser_fake {kind, port}`: starts/stops the loopback fake DAC process by exact PID (never pkill) - only on the user's request.
- Docs: add a "Lasers" paragraph to `docs/USING_TD.md` (pathways table + Mac network notes) after the first live pass.

## 7. Gated items for `docs/FUTURE.md` (each blocked on a decision or hardware; none touched)
| Item | Gate |
|---|---|
| Real EtherDream / Helios / LaserCube / ShowNET output | hardware present + operator present; no automatic start; hardware interlock is the operator's |
| Pangolin Beyond via `pangolinCHOP` | Windows only (docs); Beyond license; not on this Mac |
| LaserAnimation Sollinger AVB path (Laser CHOP -> Audio Device Out CHOP -> AVB2ILDA) | AVB interface + AVB2ILDA hardware; macOS built-in AVB per docs; must never share the default speaker route |
| IDN-Stream / IDN-Hello adapter (UDP, OpenIDN) | read IDN-Stream rev 002 + IDN-Hello specs first; hardware or software IDN receiver |
| `Wickedlasers/Laser_OS_TouchDesigner` or `colinstokes/Laser-OS_cross-platform` C++ plugin | arch x86_64 build needed (Rosetta TD), audit (AUDIT.md), user OK for a binary plugin |
| CITP/CAEX laser feed to Capture visualiser (TonilK) | Capture installed; spec read; beta component |
| LaserCube SET-RATE / settings commands | not in the public spec; read `crates/lasercube-core` source + device behaviour |
| Own `Warp` calibration with a camera (eostre-spirits idea) | needs the laser in the room; camera mounted at the laser |
| ILDA IDTF "Format 4/5 + palette" import of third-party `.ild` | user supplies files; audit parser against malformed headers |
| `LA.laserchop` (paid) | purchase decision |
| Laser POP (none exists in 31550) | watch release notes for a native laser POP; gate on `app.build` + operator presence |

## 8. Open questions
1. Do `laserCHOP` / `laserdeviceCHOP` / `etherdreamDAT` create and cook on this Mac under Rosetta? (Probe is step 1 of the live check; dylibs for x86_64 are present.)
2. Does Laser Device CHOP list a Helios plugged into the M1 Max through Rosetta + libusb (x86_64 libusb is bundled)? Hardware needed.
3. Which engine should be the default after the A/B of Native vs Own? (Native is the working assumption.)
4. EtherDream wire byte order (the protocol text contradicts itself): decide from a real device; the fake server must follow whatever the real one does.
5. LaserCube real DAC rate and buffer behaviour on newer firmware (spec is reverse engineered, 6000-point buffer, ~5000 threshold are community numbers).
6. Preview defaults `Galvobw` 6000 Hz and corner tolerance 25 deg are estimates: tune against a real scanner or published galvo datasheets.

## 9. Builder job description (one paragraph)
Build `/project1/lab/LP_laser_path` first (spec A, section 4): a self-contained Base COMP that converts SOP/CHOP/POP/TOP-trace/text/audio sources into a laser sample stream (`x y r g b i flag`, Out CHOP `laser`) through either the built-in `laserCHOP` (default, after a probe proves it creates on this Mac) or our own numpy engine (order, resample, corner dwell, blanking, colour delay, frame budget) whose logic lives in `builders/laser_path_logic.py` with pytest tests written FIRST and green; add the galvo-lag + dwell-brightness + persistence preview (Out TOP `preview`) and a stats DAT, a fully custom-par-driven interface with its own controls panel and `controls_window` (`Opencontrols` pulse), Drive options for manual / BPM / audio intensity (no limits, no warnings), a test-pattern generator and the stored-clip trace test (`media/webcam/webcam_ref_5s.mp4`). Then build `/project1/lab/LO_laser_out` (spec B, section 5): Laser Device CHOP wrapper, clean-room LaserCube UDP adapter from the public spec, ILDA format-5 recorder, all verified against loopback fakes in `test/fake_dacs.py` (no hardware, `Active` default off). Follow house rules: idempotent builder (T-67, T-70), `td_layout` flow then check ok, `td_errors` after each stage, single-pass or compute GLSL only (T-46), never route anything to audio output, and **save as you go**: `td_save_project` + `td_tox_save` to `output/backups/` + `td_net_export` after every green stage, every bug or live fact to `LEARNINGS.md` at once. Report live numbers (section 4.9) with the TD build named; ~8 h for A, ~5 h for B (estimates).

## Sources (fetched 26 Oct 2026)
docs.derivative.ca: Lasers, Laser_CHOP, Laser_Device_CHOP, EtherDream_DAT, Pangolin_CHOP; the app's offline help (Release_Notes 2023 "Laser Control", 2025 "Laser Upgrades"; Experimental) and OP Snippet `laserCHOP.tox` (expanded in `research_src/BM_lasers/snippet/`); derivative.ca community assets 63736, 65251, 71583; https://bookstack.hku.nl/books/showlaser/page/laser-in-touchdesigner-ilda ; https://github.com/Grix/helios_dac (HeliosDac.h); https://ether-dream.com/protocol.html ; https://github.com/nannou-org/lasercube (SPECIFICATION.md) ; https://github.com/nannou-org/lasy ; https://github.com/tgreiser/etherdream-touch-designer ; https://github.com/tgreiser/laser-juice ; https://github.com/danieldalfovo/Laser-Control ; https://github.com/NairoDorian/Laser-Cube-TouchDesigner ; https://github.com/Wickedlasers/Laser_OS_TouchDesigner ; https://github.com/colinstokes/Laser-OS_cross-platform ; https://github.com/stith/eostre-spirits ; https://github.com/TonilK/TD_099_CitpCaex ; ILDA IDTF14 rev 011 PDF; YouTube aNerC7KIFXo auto-captions (Dalfovo part 2).
