# BK - DMX / Art-Net / sACN lighting control from TouchDesigner + clean-room build spec (`BK_dmx_out`)

Researched 26 Oct 2026, offline research only: nothing loaded into TD, no jazib-td tool called, no code from the web run, no pip, no logins.
Target: TD 2025.31550 (macOS M1 Max, TD under Rosetta, x86_64 Python 3.11 with numpy 2.1.2 / cv2 4.11). Vulkan/MoltenVK: multi-pass GLSL can tear, compute-mode is clean (T-46).
General-purpose TD (PRISM/PF26 not relevant). Licences are irrelevant for research; they are noted only.

Evidence tags: **[docs]** = docs.derivative.ca page fetched today; **[forum]** = forum.derivative.ca thread fetched today; **[web]** = other page fetched/search result;
**[mem]** = my protocol knowledge, not re-verified today; **[idx]** = our `ops/INDEX_2025.31550.json` / `ops/*.md`; **[spec]** = our design, unverified in TD. UNVERIFIED = do not claim without a live probe.

## 0. Findings in one screen

1. **31550 has both families.** CHOP route (`dmxoutCHOP`, `dmxinCHOP`) and the newer POP route (`dmxfixturePOP` -> `dmxoutPOP`, plus `dmxmapDAT`, `artnetDAT`) [idx, docs]. Our op dump could not create the POPs (`skipped_not_created`), so POP par names below come from docs only and are UNVERIFIED on this build.
2. **Primary route for us = CHOP, Packet Per Channel, one 512-sample channel per universe + routing table.** Documented, simplest to test, per-universe `netaddress` for unicast to many nodes [docs]. POP route is a gated v2 (needs a live probe; a 32280 latency thread exists, section 3.3).
3. **Known build facts that matter here:** ArtDmx `sequence` was always 0 in every build up to and including 2025.32050 (regression since 2023.12230), so on 31550 it is 0 (= "sequencing off", valid but some receivers dislike it); 32280 fixed it but a user saw a packet-rate drop there [forum]. Do not upgrade TD for this (no-upgrade stance); a Python sender (v2) is the clean fix if a receiver needs sequence numbers.
4. **Broadcast does not scale:** with ~2,400 packets/frame Derivative staff told the user to switch to unicast (socket struggled, ArtSync timeouts) [forum]. Default for the COMP = unicast; broadcast is an option, no warning shown (user rule: operator decides).
5. **DMX512 refresh ceiling 44 Hz** is stated on every DMX op page [docs]; many LED controllers take more, so `Rate` is a free number, no clamp.
6. **Pixel mapping recipe that pros use:** pixel positions (SOP/CSV) -> UV table -> Remap TOP samples the content -> RGB values -> shuffle to R,G,B,R,G,B -> 510 samples (170 pixels) per universe channel -> DMX Out [forum 2022, YouTube Dean Cheesman/Derivative 2024]. We copy the recipe, not any file.
7. **Fixture data:** Open Fixture Library (MIT, JSON, fine channels via `fineChannelAliases`) is the best offline-importable source; GDTF (ZIP + XML, DIN SPEC 15800, ~3000 files on GDTF Share) is the pro standard [web]. Clean-room importers for both go in the patch helper; the TD DMX Fixture POP profile is parametric (`dmxchan` blocks), not a file format [docs].
8. **Moving heads:** `Pan Tilt CHOP` exists (inputs tx,ty,tz per rig, reset/clamp pars, anti-flip) but its axis convention is not documented [docs]; we write our own tested aim maths and cross-check the Pan Tilt CHOP live.
9. **No hardware needed:** TD can talk to itself over loopback (Out -> 127.0.0.1 -> In CHOP) and a stdlib Python sniffer can read the packets on a custom port; Wireshark filters `artnet`, `dmx`, `dmx_chan` [docs].
10. **Mac caveats:** macOS Sequoia/Tahoe "Local Network" privacy gates LAN UDP (broadcast/multicast) per app, intermittent multicast failures are reported, and the multicast entitlement does not help on macOS [web: TN3179 + Apple forums]. Loopback is the safe offline test. Enttec USB Pro on Mac needs `sudo kextunload -b com.apple.driver.AppleUSBFTDI` [docs] = a system change, gated.

## 1. Landscape (ranked)

### 1.1 Built into 31550 (ranked by usefulness to us)
| Rank | Op | What | Status here | Source |
|---|---|---|---|---|
| 1 | `dmxoutCHOP` | Art-Net, sACN, KiNET, Enttec serial/USB Pro/Mk2. Format `packetpersample` (each CHOP channel = one DMX slot, 512 channels = a universe) or `packetperchan` (each channel = one universe of up to 512 samples). Pars: `active interface format rate net subnet universe multicast netaddress localaddress localport customport netport sendartsync artsynctimeout cid source priority routingtable` (+ serial/KiNET). Routing Table (docked Table DAT; columns net, subnet, universe, netaddress, all optional; Packet Per Channel only). sACN universe index 1 is first available. | network ok on Mac; USB needs the kext command | [docs] |
| 2 | `dmxinCHOP` | Art-Net / sACN / KiNET / Enttec in. Format `packetpersample` (Timesliced), `packetperchan` (Latest), `packetperchanall` (All). Filter Table (`filterdat`: net, subnet, universe, optional srcaddress/destaddress, `id`), `queuesize`, `rate` (resample), `startcodes` (sACN), `multicast`, channel name prefixes. **No custom port par is listed -> listens on the standard port.** | fine; our loopback receiver | [docs] |
| 3 | `artnetDAT` | `poll` pulse lists Art-Net nodes; `columns`, `callbacks`. Listing only. | ok | [docs] |
| 4 | `dmxfixturePOP` | Each primitive = a fixture; universes built from Net/Subnet/Universe/Channel + `changap`, `quantizeuni` (off / fixture / component), routing table or per-primitive attributes `DMXFixtureNet/Subnet/Universe/Channel/NetAddress/Gap`. DMX profile = numbered `dmxchan` blocks: `name`, `valuetype` point/primitive, `valuesource` constant/attribute, `numcomps`, `value(r,g,b,a)`, `attr`, `valueres` b8/b16/b24/b32, `normalized`, `merge`, `interleavebytes`. Names may not contain spaces (2025.30000 notes) [idx]. | not created by our dump -> par names UNVERIFIED on 31550 | [docs][idx] |
| 5 | `dmxoutPOP` | Merges fixture POPs (inputs or `fixture0pop` refs) and sends: `active interface rate` + the same network pars as the CHOP + `usemultipliers`/`multiplier0dmxchannels`/`multiplier0value` (0-1 per named channel, `*` = all). Unicast advised for many universes. | UNVERIFIED on 31550 | [docs] |
| 6 | `dmxmapDAT` | Table of universes/channels/values from a Fixture/Out POP; filters; `excludeunused`; shows merge conflicts. | n/a to CHOP route | [docs] |
| 7 | `panTiltCHOP` | Aims platforms at targets. Input 0 channels `tx ty tz` (relative target position, or full transform set); input 1 optional `pan tilt` reset values; pars `reset resetvals1/2 clamppan panrangemin/max clamptilt tiltrangemin/max`; minimises flipping. Output channel names and axes NOT documented. | probe live | [docs] |

### 1.2 Community / third party (all read-only, none loaded)
| Item | What | Licence | Mac / 31550 | Use for us |
|---|---|---|---|---|
| Derivative tutorial "Pixel Mapping to DMX LEDs and Lights using TouchDesigner" (Dean Cheesman, 12 Jun 2024, derivative.ca/community-post/tutorial/pixel-mapping-dmx-leds-and-lights-using-touchdesigner/69617; video YiW8FohVSgk) | Auto-subtitles read: SOP/OBJ/SVG geometry -> SOP to CHOP -> UV image (R=u, G=v, 50x1) -> **Remap TOP** samples source -> convert to CHOP, shuffle to RGB RGB RGB -> DMX Out; instancing previz of the output. | none stated | method is op-level, platform independent | the pixel-map stage (section 3.3 stage 2). Transcript saved: `research_src/BK_dmx_artnet_sacn/yt/YiW8FohVSgk.en.srt` |
| Forum "Pixel Mapping Import DMX Patch from File" (samaa/Peeet, Jun 2022, forum.derivative.ca/t/267129) | ~90 sACN universes from one HD canvas, CSV with XYZ + universe + address; DATto SOP, SOPto CHOP, TOPto CHOP, 510 samples (170 px) per universe channel, **lock the CHOP** so geometry stops cooking, content rarely needs more than 720p, hundreds of universes feasible; ordering via routing table | forum | any | patch-table design, universe packing, perf expectation |
| Forum "DMX POP is experiencing latency TD2025.32280" (snaut/eric.b, Jan-Feb 2026, /t/936654) | 400k-LED volumetric; broadcast with 2,432 packets/frame stalled (1 fps after re-plug), fix = unicast per IP with `DMXFixtureNetAddress`, `DMXFixtureUniverse` per column, Connectivity POP, build 32331 fixed a crash | forum | build 32280+ | proof that unicast + per-node address is the scaling path |
| Forum "Artnet problems build 2025.32280" (Barts.art/eric.b, Jan-Feb 2026, /t/931899) | see finding 3; also **DAT to CHOP "First Row is" must be Ignored** or a header column eats one of the 32 channels (31 sent) | forum | both builds | rule for any table->CHOP step we build |
| Forum "DMX IN \| sACN issue" (/t/869380) and older (/t/269648) | working sACN In: Timesliced, Net 0, Subnet 0, chosen universe, start code 0, multicast on, **Local Address = the adapter**; multicast join failures on some Windows builds; unicast works but some makers do not implement it | forum | adapter choice matters on Mac too | `Localip` par, unicast default |
| TouchLED-DMX (github.com/yastefan/TouchLED-DMX) | Mapper (TOP onto SOP points), DMX_Universe (sACN), Visualizer, Static_Channels (dimmer/shutter/pan/tilt/zoom), RGBtoCMYK; 15 stars, 16 commits | GPL-3.0 | TD version/platform not stated | idea source (SOP points = pixels, static-channel panel); not downloaded |
| HKU bookstack "touchdesigner tox for various fixtures" (bookstack.hku.nl) | per-fixture-layout .tox files (5/6/7-channel PARs, 14/16-ch moving heads), `dmx_out_Artnet_2023.tox` with Merge for several fixtures, tip: pad to full 512 channels if a node ignores short frames, WLED preset | not stated | any | confirms the "fixture Base + Merge + universe pad" pattern from AD section 2.11 |
| GeoPix (EnviralDesign) | LED/DMX pixel map + previz in TD | MIT | Windows `.bat` (N file) | skip |
| Artio (theexperiential) | pixel-map generator tox | GPL-3 | Windows (AB file) | skip |
| twozero ZERROR DMX surface (BE) | Art-Net-input-only DMX fader surface | licence per machine | account-gated | idea only |
| Open Fixture Library (github.com/OpenLightingProject/open-fixture-library) | JSON fixtures per manufacturer; schemas in `schemas/`; export plugins; one JSON has `availableChannels` with `fineChannelAliases` (e.g. "Pan fine"), `modes[].channels` (names, `null` = unused), `physical`, capabilities with `angleStart/angleEnd` (example read: Robe ROBIN Viva CMY, Pan 0-540 deg, Tilt 270 deg, 32-ch "Standard 16 bit" mode, 26-ch "Reduced 8 bit") | code MIT (fixture data licence UNVERIFIED) | pure JSON | patch-helper import source |
| GDTF / GDTF Share (gdtf-share.com, spec 1.2 = DIN SPEC 15800:2022) | ZIP with `description.xml` + glTF/3DS geometry + PNG gobos; ~3000 files on the share | share terms UNVERIFIED | pure ZIP/XML | v2 importer (channels only, ignore geometry) |
| Python libs (reference only, not to be installed): `sacn` 1.11.0 (Feb 2025, MIT, sender/receiver, multicast+unicast, per-address priority); `pyartnet` 2.0 (Nov 2025, GPL-3.0+, asyncio, ArtNet/sACN/KiNet) | | | | read their packet code for cross-checking our own encoder |
| Test tools: **sACNView** (docsteer, Apache-2.0, viewer+sender, builds for Linux/Mac/Win; arm64 build not confirmed), **ArtNetView** (free Mac App Store, Art-Net only), **QLC+** (Art-Net+sACN in/out on macOS [web], fixture editor), Dmxhub (free macOS router), VELOR (paid) | all need install/download = user's go-ahead; none needed for the offline plan | | | the stdlib sniffer replaces them |
| Protocol docs (not downloaded): Art-Net 4 spec (Artistic Licence), ANSI E1.31-2018 (sACN) | secondary sources used: Wikipedia Art-Net, hexdocs `art_net`, OLA docs, go-sacn | | | field layouts, section 2 |

### 1.3 Not found / gaps (honest)
- No 2025 tutorial for the **POP** fixture workflow was found; the only POP evidence is docs + the 32280 forum thread.
- Release-note text for DMX fixes between 31550 and today was not read (only forum statements).
- No source for a TD sACN `universe` <-> `net/subnet/universe` formula; guess in section 2.3, to be proven by loopback.
- No arm64 confirmation for sACNView/ArtNetView.

## 2. How it works in TD (practical)

### 2.1 Protocol cheat sheet [mem unless tagged]
| | Art-Net (UDP 6454) | sACN / E1.31 (UDP 5568) |
|---|---|---|
| Addressing | 15-bit Port-Address = Net(7) . SubNet(4) . Universe(4); flat = net*256 + subnet*16 + universe | universe 1-63999 (0 reserved [docs]) |
| Delivery | unicast, directed broadcast, or limited broadcast 255.255.255.255 [docs]; Art-Net 4 advises unicast for big rigs | multicast 239.255.<hi>.<lo> of the universe (or unicast); join needs the right NIC |
| ArtDmx header (18 B) | "Art-Net\0", opcode 0x5000 (LE), version 0,14, sequence (0 = off), physical, SubUni (low byte), Net, length (hi,lo; even, 2-512), data | root layer + framing (source name 64 B, priority 0-200 default 100, sequence, options, universe) + DMP; 638 B total for 512 slots |
| Other opcodes | ArtPoll 0x2000, ArtPollReply 0x2100, ArtSync 0x5200 (TD: `sendartsync`) | sync packets, universe discovery (not needed) |
| Packet size on wire (512 slots) | 530 B payload | 638 B payload |
| Rate | DMX frame = ~22.7 ms -> 44 Hz ceiling on DMX512 wires [docs]; Ethernet nodes often take 60 | same; senders also keep-alive ~1 s when idle |
| TD sequence | **0 always on 31550** [forum] | per op (UNVERIFIED) |

Bandwidth estimate [spec]: 170 universes x 40 Hz x (530 + 42 B IP/UDP/Eth) = ~31 Mbit/s: fine on wired gigabit, not for Wi-Fi.

### 2.2 DMX Out CHOP, the way we use it
- **Packet Per Channel**, `rate` = send rate, one CHOP channel per universe, 512 samples (float 0-255; the op rounds - rounding behaviour UNVERIFIED, we hand it integers).
- **Routing table** (docked Table DAT): header `net subnet universe netaddress`, one row per channel in channel order. We generate it from the patch (one row per used universe) so per-node unicast works with a single DMX Out.
- Without a table: given address goes to channel 1, the rest are consecutive universes [docs].
- Unicast: `netaddress` = node IP (or per-row). Broadcast default 255.255.255.255 [docs]. `localaddress` picks the adapter.
- **Pad every universe to 512 samples** (also HKU tip) so all nodes see full frames.
- Header-row trap: DAT to CHOP `First Row is` = Ignored [forum].

### 2.3 Universe numbers
Our patch uses one **flat universe index** `U` (Art-Net: 0-based flat Port-Address; sACN: 1-based). Helper `port_address(U) -> (net, subnet, universe) = (U>>8 & 127, U>>4 & 15, U & 15)`. TD's `universe` par is 0-15 only [docs], so anything above 15 must go through net/subnet or the routing table. Whether TD turns net/subnet/universe into the sACN universe as `net*256+subnet*16+universe` is UNVERIFIED -> first live check (section 4, test L2).

### 2.4 DMX In CHOP
Use `packetperchan` (Latest) for a stable one-channel-per-universe view; set `multicast` off for unicast loopback. Channel names are built from the net/subnet/universe name prefixes (`netname`, `subnetname`, `universename`); exact resulting channel names UNVERIFIED -> read them in the first probe. It listens on the standard port (no custom port par).

### 2.5 DMX POPs (v2 route)
Fixture POP: points/primitives -> universes (`autolayout` + `quantizeuni`), Out POP merges and sends; multipliers per channel name give a free master/blackout per attribute. It scales better when fixtures are geometry (copy a line strip 400 times), but: par names UNVERIFIED on 31550, a 32280 latency thread, and the dump could not create them. Plan: probe once (create, read pars, delete) in a later live session, then decide.

### 2.6 Pixel mapping from a TOP (what works)
Points (u,v) -> `Remap TOP` (nearest, extend = hold) over the content TOP -> small float image (N x 1) -> CPU (`TOP.numpyArray(delayed=True)` UNVERIFIED on Rosetta/Vulkan, fallback `TOP to CHOP` with delayed download) -> scale/gamma/order in numpy -> scatter into the universe buffer. Only N pixels are read back, never the whole canvas. Latency +1-2 frames (acceptable; section 4 measures it).

### 2.7 Fixture profiles and OFL / GDTF
- Internal profile `jzfix` (JSON, section 3.4) is channel-list based: offset, name, attr, bits (8/16), kind, default, angle range.
- **OFL -> jzfix**: for each mode, walk `channels`; resolve a name through `availableChannels` or `fineChannelAliases` to (coarse, fine) pairs; type Pan/Tilt/Intensity/ColorIntensity (Red, Green, Blue, White, Amber, UV, Cyan...) -> `kind` and `attr`; `null` -> reserved slot; capture `angleStart/angleEnd` -> `range`; skip wheels/matrix channels beyond "raw value" in v1.
- **GDTF -> jzfix** (v2): unzip, read `description.xml` -> `DMXModes/DMXMode/DMXChannels/DMXChannel` (Offset "1,2" = coarse,fine), `LogicalChannel@Attribute` (Pan, Tilt, Dimmer, ColorAdd_R...), ignore geometry. Field names from the GDTF 1.2 spec - UNVERIFIED until the spec page is read.

### 2.8 Moving heads from 3D targets
Pan/tilt are 540/270 deg typical, sent 16-bit (coarse = high byte, fine = low byte, value = angle/range * 65535) [web + mem]. We compute angles from a world target, a world position and an orientation; own maths (section 3.5) is unit-testable; the Pan Tilt CHOP is the live cross-check.

### 2.9 Testing without hardware
1. Loopback inside TD: Out -> 127.0.0.1:6454 -> In CHOP, compare sample by sample.
2. Out with `customport` 16454 -> 127.0.0.1 -> stdlib sniffer (our own `tools/dmx_sniff.py`, run with `python3 -I`, binds a UDP socket, parses ArtDmx/E1.31, prints header fields and counts).
3. Pure-Python round trip tests of the encoder/decoder and every mapping function (pytest, no TD).
4. Optional later (user's go-ahead for install/net): sACNView / Wireshark on LAN.

## 3. CLEAN-ROOM BUILD SPEC: `BK_dmx_out` (one COMP, with the patch helper built in)

COMP path suggestion: **`/project1/lab/BK_dmx_out`**. Builder: `builders/dmx_out.py` (idempotent `build(parent)` like `db_meter.py`: ops reused by name, keeps custom par values and the panel), logic in `builders/dmx_logic.py` (pure Python + numpy, no `td` import), tests `test/test_dmx.py`, sniffer `tools/dmx_sniff.py`. ASCII only. No Python functions in op storage (T-67). No `.destroy()` of anything a window shows (T-70, use the safe-destroy pattern of the other builders). Stage boxes with `td_layout stages` (T-66/T-69). Own idea, own code; nothing copied from any file listed above.

### 3.1 Interface
- Inputs: `in1` In TOP (content for pixel mapping, optional), `in2` In CHOP (fixture values, channels named `<fixture>.<attr>`, 0-1; pan/tilt in degrees if the attr ends with `_deg`; optional), `in3` In CHOP (level/BPM modulation source, e.g. a CHOP carrying an audio level; optional).
- Outputs (output only): `out1` Out TOP (universe monitor heat-map, default 1024x768), `out2` Out CHOP (`stats`: `packets_s`, `universes`, `slots_used`, `frame`, `compose_ms`, `loopdiff`, `seq`), `out3` Out CHOP (`universes`: the composed buffer, one channel `u<flat>` x 512 samples, for external viewers/recorders).
- The COMP never touches audio output (default out = Mac speakers, never mic->speaker); in3 is a read-only CHOP.

### 3.2 Custom parameters (page, name; names = one capital then lowercase/digits)
- **Output**: `Active` toggle; `Protocol` menu artnet/sacn; `Targetmode` menu unicast / broadcast / multicast (multicast only for sACN); `Targetip` str (default 127.0.0.1 so a fresh COMP is harmless-by-default, not a safety limit; broadcast uses 255.255.255.255); `Localip` str (blank = OS choice); `Rate` float 40 (no clamp); `Firstuniv` int (flat index of the first universe, 0 Art-Net / 1 sACN); `Priority` int 100; `Sourcename` str "BK_dmx_out"; `Sendsync` toggle; `Syncms` int 20; `Netport` int 0 (0 = default port; else custom port, used for sniffer tests); `Loopback` toggle (forces Targetip 127.0.0.1 and starts the in-COMP DMX In check); `Sender` menu tddmx / python (python = v2, greyed in v1).
- **Mapping**: `Pixelsrc` TOP ref (blank = in1); `Pixelblur` float 0 (px, Blur TOP before sampling); `Colororder` menu rgb/rbg/grb/gbr/brg/bgr/rgbw/grbw; `Whitemode` menu none / extract-min / zero-w; `Gamma` float 1.0 (2.2 for typical strips); `Pixperuniv` int 170 (4-ch pixels: 128); `Spanuniv` toggle (pixel may straddle universes = continuous channels); `Pixelscale` float 255 (full-scale value); `Interp` menu nearest / bilinear. **`Popsrc`** POP ref (27 Oct, TC-38, lane T): set = pixel i takes point i's `Color` (POP to CHOP `popchop`, nextframe; Switch `pixin` picks it over the sampled TOP); live on b4 (31550): 5 points -> u0 bytes 26 51 77 / 255 0 0 / 0 255 0 / 0 0 255 / 128 64 191 (Active off, nothing sent).
- **Master**: `Master` float 1 (slider 0-1, field accepts any), `Blackout` toggle, `Blackoutmode` menu intensity / all, `Freeze` toggle (hold last frame), `Masterfrom` menu manual / bpm / audio / bpm-x-audio, `Bpm` float 120, `Beatshape` menu pulse/saw/sine/square, `Beatdepth` float 1, `Audioamt` float 1, `Tapbpm` pulse.
- **Test**: `Pattern` menu live / zero / full / ramp / channelid / chase / rgbcycle / walkpixel / fixtureid / strobe; `Patternmix` menu replace / add / max; `Level` float 1; `Speed` float 1 (Hz, or beat divisions when `Masterfrom` is bpm); `Solofixture` str; `Solochan` int; `Univfilter` str (pattern of flat universes to send, blank = all).
- **Monitor**: `Monfirst` int, `Moncount` int (universes shown), `Moncell` int 6 (px per slot), `Monmode` menu heat / grey / nonzero.
- **Patch** (helper, section 3.6): `Addfixture` pulse, `Profile` menu (from profiles), `Mode` menu, `Count` int, `Fixname` str, `Univ` int, `Addr` int, `Autonext` toggle, `Quantize` menu off / fixture, `Gap` int, `Checkpatch` pulse, `Importfile` file (OFL .json / CSV), `Importpulse` pulse, `Clearpatch` pulse (confirms nothing - operator decides).
- **Controls**: `Opencontrols` pulse (opens `controls_window`), `Bypass`, `Resetdefaults` pulse.
- Read-only status pars on Output: `Universes`, `Slotsused`, `Packetsrate`, `Mapok`.
- No built-in limits or warnings: no max-brightness cap, no strobe-rate limiter, no "broadcast" or "high rate" prompts. Values are clamped to 0-255 and rounded only because DMX slots are bytes.

### 3.3 Internal network (L-to-R stages, titled boxes, role colours, comments)
1. **"Inputs"**: `in1` (In TOP), `in2`, `in3` (In CHOP), Table DATs: `patch` (fixtures), `profiles_json` (Text DAT, jzfix list), `pixels` (pixel map), `routing` (generated), `settings` (Parameter Execute for rebuilds).
2. **"Pixel sample"**: `pixels` (cols `id u v univ addr group`, u,v in 0-1) -> `uvtable` (DAT to CHOP, First Row = Ignored, channels u v) -> CHOP to TOP `uvmap` (N x 1, 32-bit float RG) -> `remap` (Remap TOP, in1 = content, in2 = uvmap, nearest, extend hold) -> optional `blur` before the remap -> `pixelout` Null TOP. Rebuild `uvmap` only when `pixels` changes (lock/skip, forum tip).
3. **"Compose"** (Script CHOP `compose`, cook = one call to `dmx_logic.compose(plan, state)`): steps in order (a) zero buffer (U x 512 uint8) (b) fixtures: apply in2 values through profiles (c) pixels: `pixelout.numpyArray(delayed=True)` -> order/white/gamma/scale -> scatter by slot index (d) pattern per `Patternmix` (e) master/blackout/freeze, applied only to slots whose `kind` is intensity (pan/tilt untouched unless `Blackoutmode=all`) (f) universe filter (g) round + clip. Output channels `u<flat>` x 512 samples (float 0-255) via `scriptOp.copyNumpyArray` (UNVERIFIED; fallback `appendChan` + `vals`). The `plan` (index arrays from tables) is rebuilt only by a DAT Execute when a table or relevant par changes.
4. **"Master source"**: BPM LFO (Pattern CHOP / Wave or Python phase from `absTime`) by `Beatshape`; audio from `in3` via Analyze CHOP (RMS) + Lag; mix per `Masterfrom`; result `master_eff` read by `compose`.
5. **"Send"**: `routing` (Table DAT: `net subnet universe netaddress` per used universe, generated by `plan`) docked to `dmxout` (DMX Out CHOP: `interface` from `Protocol`, `format packetperchan`, `rate`, `customport/netport`, `multicast`, `localaddress`, `priority`, `source`, `sendartsync`, `artsynctimeout`, `active`). Pars bound by expressions to the COMP's custom pars (T-62: do not set StrMenu pars as strict menus).
6. **"Loopback check"**: `dmxin` (DMX In CHOP, `packetperchan`, `active` = `Loopback`) -> Math (subtract) with `compose` -> Analyze (max abs) -> `loopdiff`. Active only while `Loopback`.
7. **"Monitor"**: `compose` -> CHOP to TOP `u2top` (512 x U, 32f, r = v/255) -> **one compute-mode GLSL TOP** `mon` (T-46: never chain passes) -> `out1`. Tiles of 32 x 16 slots per universe.
8. **"Stats / Outputs"**: Info CHOPs of `dmxout`/`compose` + `chopexec`-free Script CHOP for `stats` -> `out2`; `out3` = Null of `compose`.
9. **"Panel"**: `controls_panel` Container (sections made with the same helpers as the other builders), `controls_window` Window COMP opened by `Opencontrols` pulse; panel = Output, Master (big Blackout + Master slider), Test pattern pad, Monitor TOP view, patch table viewer. Panel widgets only reference custom pars.

GLSL monitor sketch (compute mode; Mac/MoltenVK safe):
```glsl
// BK monitor: one compute pass. In0 = universe values (x = slot 0..511, y = universe row).
uniform int uTilesX;    // tiles per row
uniform int uCell;      // px per slot
uniform int uFirst;     // first universe row shown
uniform int uCount;     // universes shown
uniform int uMode;      // 0 heat, 1 grey, 2 nonzero
layout (local_size_x = 8, local_size_y = 8) in;
vec3 heat(float v){ return vec3(clamp(v*3.,0.,1.), clamp(v*3.-1.,0.,1.), clamp(v*3.-2.,0.,1.)); }
void main(){
  ivec2 p = ivec2(gl_GlobalInvocationID.xy);
  ivec2 tile = ivec2(32,16) * uCell + ivec2(4);          // 4 px gutter
  ivec2 t = p / tile, l = p % tile;
  int u = t.y * uTilesX + t.x;
  vec4 c = vec4(0.04,0.04,0.05,1.);
  if (u < uCount && l.x < 32*uCell && l.y < 16*uCell) {
    ivec2 cell = l / uCell;
    float v = texelFetch(sTD2DInputs[0], ivec2(cell.y*32 + cell.x, uFirst + u), 0).r;
    c.rgb = (uMode==1) ? vec3(v) : (uMode==2 ? vec3(v>0.?1.:0.2*0.) : heat(v));
  }
  imageStore(mTDComputeOutputs[0], p, TDOutputSwizzle(c));
}
```
(uniform names and `sTD2DInputs`/`mTDComputeOutputs` follow T-46/T-68 practice; vectors set through the GLSL TOP vector sequence.)

### 3.4 Data formats
- `patch` table: `name profile mode univ addr count gapslots node kind` (`node` = IP for per-node unicast, blank = Targetip; `kind` fixture/pixelstrip).
- `pixels` table: `id u v univ addr group` (generated by helper from layouts: strip, grid with serpentine, ring, CSV import with xyz normalised).
- `profiles_json`: list of `{id, name, maker, source, modes:[{name, channels:[{off, name, attr, bits, kind, default, min, max, range_deg}]}], pan_range, tilt_range}`, `kind` in intensity / colour / position / other, `attr` in dimmer, red, green, blue, white, amber, uv, pan, tilt, speed, shutter, raw. Built-ins: `generic_dimmer_1ch`, `generic_rgb_3ch`, `generic_rgbw_4ch`, `generic_rgbaw_uv_6ch`, `generic_mh_16bit_16ch`.
- `routing` table generated: sorted unique flat universes of the plan.

### 3.5 Python logic (`dmx_logic.py`), pure and offline-testable
```python
import math, numpy as np

def port_address(u):             # flat Art-Net Port-Address -> (net, subnet, universe)
    return (u >> 8) & 0x7F, (u >> 4) & 0xF, u & 0xF

def split16(v01):                # 0..1 -> (coarse, fine)
    n = int(round(min(max(v01, 0.0), 1.0) * 65535)); return n >> 8, n & 255

def place(buf, univ0, addr, data):   # buf: (U,512) uint8, addr 1-based, may spill into next universe
    flat = (univ0 * 512) + (addr - 1); view = buf.reshape(-1)
    view[flat:flat + len(data)] = data

def layout_pixels(n, per_univ=170, univ0=0, addr0=1, chans=3, span=False):   # -> list of (univ, addr)
    ...

def pixel_slots(rgb01, order='rgb', white='none', gamma=1.0, scale=255):     # (N,3)->(N,k) uint8
    ...

def aim(pos, target, rot_deg, pan_range=540., tilt_range=270., pan_zero=0.5, tilt_off=0.,
        pan_dir=1, tilt_dir=1, prev_pan=None):
    # local vector l = R^-1 (target - pos); pan = atan2(l.x, -l.z); theta = atan2(hypot(l.x, l.z), l.y)
    # candidate A (pan, theta), B (pan+180, -theta); pick the one inside mechanical range closest to prev_pan
    ...

def beam_dir(pan_deg, theta_deg):     # forward kinematics for tests: cos(t)*up + sin(t)*(sin p, 0, -cos p)
    ...

def encode_artdmx(seq, univ, data): ...      # 18-byte header + data, length even
def encode_sacn(seq, univ, data, prio=100, name='bk', cid=b'...'): ...
def parse_artdmx(pkt) / parse_sacn(pkt): ...
def ofl_to_profile(d): ...                   # section 2.7
def auto_address(fixtures, quantize): ...    # next free address, conflict list
def check_patch(patch, profiles): ...        # overlaps, universe spills, unknown profile/mode
def pattern(kind, t, n_univ, params): ...    # returns (U,512) uint8
```
Tilt convention: `theta` is the polar angle from the fixture's up axis (0 = straight up the mount axis); DMX angle = `tilt_dir * theta + tilt_off`, divided by `tilt_range`. Defaults are a starting point; calibration = enter one measured pan/tilt for a known target and the helper solves `pan_zero`/`tilt_off`. Hanging fixture = roll 180 deg in `rot_deg`.

### 3.6 Fixture patch helper (inside the COMP, `Patch` extension + panel tab)
- `Addfixture`: appends `Count` fixtures of `Profile/Mode` at `Univ/Addr` (or next free when `Autonext`), `Quantize=fixture` pushes a fixture to the next universe if it would straddle (max 512 slots), `Gap` extra slots between fixtures (same idea as the POP `changap`, our own implementation).
- `Checkpatch`: lists overlaps (same slot twice), straddles, unknown profile, empty universe holes; writes a `patch_report` Text DAT. Reports only; it never blocks sending.
- `Importfile`: OFL .json -> new profile; CSV -> pixel map (columns x,y[,z],univ,addr or just x,y with auto layout).
- Pixel layout generators: `strip(n)`, `grid(w,h,serpentine)`, `ring(n)`, `csv(...)`, all return both `pixels` and `patch` rows.
- Works from a dropped OFL file in `research_src` style directories; no network needed.

### 3.7 Offline tests (pytest, `test/test_dmx.py`, no TD)
`port_address` round trip for U in 0..32767; `split16` edges (0, 1, 0.5, monotonic); `place` spill across universes; `layout_pixels` 170/univ and spanning, count of universes for 28,900 px = 170; `pixel_slots` per order + gamma 1/2.2 + `extract-min` white (w = min, others reduced); `aim` + `beam_dir` round trip on 10,000 random targets (error < 1e-6 rad, result inside range or flagged), flip solution near the zenith, hysteresis (no 360 deg jump between neighbouring frames), hanging fixture; encoder/parser round trip for ArtDmx and sACN (field offsets: ArtDmx data at byte 18, length even, universe split), `ofl_to_profile` on a saved sample JSON (16-bit pairs, `null`); `auto_address`/`check_patch` cases; pattern shapes and determinism; master only on intensity slots.

### 3.8 Live verification (31550; numbers to hit; nothing needs hardware)
| Id | Test | Pass |
|---|---|---|
| L1 | Art-Net loopback, 4 universes, `channelid` pattern, Out -> 127.0.0.1:6454 -> DMX In CHOP | `loopdiff` = 0 for 10 s; In channel names recorded |
| L2 | sACN loopback, flat universe 1..4 | In sees same data; observed sACN universe numbers vs `net/subnet/universe` pars recorded (settles 2.3) |
| L3 | Sniffer: Out `Netport` 16454, Art-Net | header OK; **sequence = 0** on 31550 recorded; length 512; packets/s per universe = `Rate` +-2% over 10 s |
| L4 | Sniffer on sACN | priority = `Priority`, source name, CID stable, packet size 638 |
| L5 | Pixel map 50-pixel ring, content = webcam_ref_5s.mp4 (media/webcam/) | slots equal the content pixel at each (u,v) +-2 LSB with `Gamma` 1, `Interp` nearest; solid red -> 255/0/0 per pixel; latency <= 2 frames (impulse test) |
| L6 | 28,900 px grid (170 universes) | compose < 4 ms/frame avg, fps stays 60 with `Rate` 40, packets/s = 170 x 40 = 6800 +-2%, no TD errors |
| L7 | 16-bit moving head: target (0,0,-5), head at (0,3,0), then orbit | coarse/fine equal `dmx_logic.aim` within 1 LSB; fit against Pan Tilt CHOP output within 0.5 deg after a constant sign/offset fit |
| L8 | Blackout / Freeze / Master from BPM 120 pulse | intensity slots follow, pan/tilt unchanged unless `all` |
| L9 | Monitor TOP | compute shader draws 170 tiles, no tearing over 2 min (T-46) |
| L10 | Broadcast / LAN | only after the user allows real network sends; macOS Local Network permission for TD checked first |
| L11 | Persistence | rebuild with the builder on a fresh `lab` gives identical ops/pars (idempotent), `.tox` saved from the COMP loads back |

### 3.9 Performance targets and Mac caveats
- Compose < 4 ms avg / < 8 ms p99 at 170 universes (87k slots) in numpy; TD fps 60 with panel closed, >= 55 with monitor open.
- Memory: monitor TOP 512 x 170 f32 = 350 kB; fine.
- Sustained rate: 6,800 packets/s on loopback and wired LAN; document that Wi-Fi is unsuitable.
- Mac: choose `Localip` explicitly when several adapters exist; Local Network permission (Settings > Privacy & Security > Local Network) per app, may need the app re-added; multicast intermittently flaky on Sequoia/Tahoe, prefer unicast; Enttec USB Pro needs the kext unload (gated); loopback tests do not need any permission (UNVERIFIED but expected).
- Build-specific: no sequence number on 31550 (L3 records it); do not use 32280's sequence fix as a reason to upgrade.
- Any table->CHOP step uses `First Row is = Ignored`.

### 3.10 Persistence and housekeeping (user: "save ur projects always so u dont loose ur progress or learnings or node setups")
- The builder script (`builders/dmx_out.py`) is the node setup of record (idempotent rebuild) and `dmx_logic.py` + tests hold the logic: both live in files, not only in the .toe.
- The builder agent never saves the project (T-71: the main session saves after each verified build; the handlers autosave runs every 10 min). The builder reports "ready to save" and the COMP path; main session then runs `td_save_project` and `td_tox_save` of the COMP to `projects/`/`output/` per the other builders' convention.
- Every bug hit during the build gets a LEARNINGS entry (T-nn) at once; facts proven in L1-L11 go into this file's section 5 (open questions closed) in the same session.

## 4. Build order and estimate (about 8-9 h for v1)
1. `dmx_logic.py` + `test_dmx.py` + `tools/dmx_sniff.py` (offline, 2.5 h). 2. Builder skeleton: Output + Test + Master + `compose` + `dmxout` + `routing` (2 h) -> L1-L4. 3. Pixel stage + helpers (1.5 h) -> L5-L6. 4. Fixtures/profiles/aim (1.5 h) -> L7-L8. 5. Monitor + stats + panel/window (1 h) -> L9. 6. Docs/LEARNINGS/README and save handoff (0.5 h). Parallel lanes: steps 1 and the GLSL monitor can be done in separate lanes; live TD work stays one lane.

## 5. Open questions (for the first live probe, not for the user)
- **Answered live 26 Oct (31550, LEARNINGS T-82):** DMX In names under packetperchan = `net0subnet0uni<N>`; Art-Net and sACN sequence = 0 on 31550; sACN packet 638 bytes, CID constant ("TouchDesigner"), routing `universe` column = sACN universe; routing table needs a `channel` column; DMX Out `rate` overshoots (paced by `pacer`, Rate 10-60 -> 10.0-59.7 pkt/s); DMX In does not receive sACN unicast loopback (sACN checked with the sniffer); TOP to CHOP of a multi-row image = r0 g0 b0 a0 r1 ...; 170-channel x 512 Script CHOP write = 0.6 ms with per-channel copyNumpyArray. L6 at 170 universes: 44-50 fps on this Mac (not yet 60).
- Exact DMX In channel names under `packetperchan`; whether `dmxout` rounds or truncates floats.
- sACN universe mapping from `net/subnet/universe` (2.3). Whether `sequence` increments for sACN.
- `TOP.numpyArray(delayed=True)` and `scriptOp.copyNumpyArray` on Rosetta/Vulkan; cost of a 170-channel x 512 Script CHOP.
- Info CHOP/DAT fields on `dmxout` for packet rate (forum quotes `packet_rate`; our page lists only common channels).
- DMX Out POP / Fixture POP par names on 31550 (v2).
- Pan Tilt CHOP axis/units and output channel names.

## 6. MCP tool ideas (for `src/`, later; none built now)
- `td_dmx_build` {parent, panel}: runs the idempotent builder (like the other builder tools), returns path + the L-check list.
- `td_dmx_patch` {action add/list/check/clear/import_ofl/import_csv, ...}: edits `patch`/`profiles_json`, returns conflicts; offline mode works on a CSV file without TD.
- `td_dmx_test` {suite loopback_artnet|loopback_sacn|sniffer|pixel|aim}: runs L1-L9, returns diffs and pass/fail numbers.
- `td_dmx_sniff` {start/stop/last} wrapping the stdlib sniffer (exact PID stop only, no pkill).
- `td_dmx_aim` {pos, target, rot, ranges}: offline pan/tilt/DMX bytes; useful for calibration.
- `td_artnet_poll`: pulses `artnetDAT.poll` and returns the node table (read-only network traffic; user go-ahead on a real LAN).
- Doc tools: `profile_search` over a local OFL checkout.

## 7. Gated items for `docs/FUTURE.md`
| Item | Gate |
|---|---|
| Real LAN sends (broadcast/unicast/multicast) to fixtures or nodes | user's go-ahead per session; Local Network permission check |
| Enttec USB Pro / serial DMX on Mac | needs `sudo kextunload -b com.apple.driver.AppleUSBFTDI` (system change) and hardware |
| DMX Fixture/Out POP route | one live probe of par names; re-check latency report; Mac status |
| Python socket sender (`Sender=python`): real sequence numbers, ArtSync control, exact pacing | v2, after L3 shows the 31550 behaviour |
| GDTF import (channels only), GDTF geometry previz | read GDTF 1.2 spec first; share terms UNVERIFIED |
| OFL bulk checkout of fixtures | download of a repo = user's OK; data licence check |
| RDM, ArtTimeCode, Art-Net 4 discovery in the panel, sACN universe discovery/sync | none yet |
| Previz of fixtures (beams, pixel wall) tied to `BI_rudiment_previz_stage` | after v1 |
| Newer-build features: 32280's ArtDmx sequence fix, POP latency fixes (32331) | keep as gated on build number; no upgrade (user stance) |
| sACNView / Wireshark / QLC+ installs for LAN checks | installs need the user's go-ahead |

## 8. Builder job description (hand to the builder agent)
Build `BK_dmx_out` at `/project1/lab/BK_dmx_out`: a self-contained Base COMP that turns patch tables, an optional pixel-content TOP, optional fixture-value CHOP and test patterns into Art-Net or sACN output. Start offline: write `builders/dmx_logic.py` (port addresses, 16-bit split, slot placement, pixel layout and colour order/gamma/white, aim maths with a forward-kinematics round-trip, ArtDmx/sACN encode+parse, OFL import, patch check, test patterns), `test/test_dmx.py` with the cases in 3.7, and `tools/dmx_sniff.py` (stdlib UDP, run with `python3 -I`, parses and counts packets on a given port). Then write `builders/dmx_out.py` (idempotent like `db_meter.py`; stage boxes via `td_layout stages`; safe-destroy rules T-70; ASCII only): custom pars of 3.2, internal stages of 3.3 with one Script CHOP `compose` producing one 512-sample channel per universe, one `dmxout` (Packet Per Channel + generated routing table), one compute-mode GLSL monitor TOP (no multi-pass, T-46), a loopback DMX In check, Out TOP/CHOPs as outputs only, `Opencontrols` pulse opening `controls_window`, no limiters or warnings anywhere, no audio output. Verify with L1-L9 in 3.8 using only loopback and the sniffer (webcam tests on `media/webcam/webcam_ref_5s.mp4`), record every measured number and every UNVERIFIED item that became fact in this file (section 5) and in LEARNINGS, and do not save the project (main session saves, T-71); report the COMP path, the pars list and the pass/fail table.

## 9. Sources
Docs (fetched 26 Oct 2026): docs.derivative.ca/DMX_Out_CHOP, /DMX_In_CHOP, /DMX_Out_POP, /DMX_Fixture_POP, /DMX_Map_DAT, /Art-Net_DAT, /Art-Net, /Pan_Tilt_CHOP.
Forum: forum.derivative.ca/t/artnet-problems-build-2025-32280/931899; /t/dmx-pop-is-experiencing-latency-td2025-32280/936654; /t/pixel-mapping-import-dmx-patch-from-file/267129; /t/dmx-in-sacn-issue/869380; /t/pixel-mapping-to-dmx-leds-and-lights-using-touchdesigner-2024-06-12/870844; derivative.ca/community-post/tutorial/pixel-mapping-dmx-leds-and-lights-using-touchdesigner/69617; YouTube YiW8FohVSgk (auto subtitles, `yt-dlp --skip-download`, one request, no 429).
Other: github.com/yastefan/TouchLED-DMX; github.com/OpenLightingProject/open-fixture-library (+ fixtures/robe/robin-viva-cmy.json read via raw URL); open-fixture-library.org/about; gdtf-share.com/help/developers/gdtf_1_2; bookstack.hku.nl (TD fixture tox pages); github.com/docsteer/sACNView; pypi.org/project/sacn, /pyartnet; Wikipedia Art-Net; hexdocs.pm/art_net; docs.openlighting.org (ola::acn); Apple TN3179 and developer forum threads 757824, 765285, 782922; controlbooth thread on free macOS DMX tools.
Local: `research_src/BK_dmx_artnet_sacn/yt/YiW8FohVSgk.en.srt` (text only). Our notes: A, AB (row 26), AD (2.11), AE (P9), BE, N, `ops/POP.md`, `ops/CHOP.md`, `ops/DAT.md`, `ops/PLATFORM.md`; LEARNINGS T-18, T-46, T-62, T-66-T-71.
