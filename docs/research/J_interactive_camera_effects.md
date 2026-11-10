# J - Interactive body/camera-driven effects for PRISMFEST'26 in TouchDesigner (research, 16 Oct 2026)

Agent J for the lead. Build **2025.31550** (`TouchDesigner 2.app`, x86_64 under Rosetta), M1 Max 64 GB, Arena 7.23.2 host, TD builds at **1080x1920**.
Research only: nothing installed, downloaded (software), generated or built; TouchDesigner and Arena were not touched. The only local reads were the
in-build offline help (`TouchDesigner 2.app/Contents/Resources/tfs/Samples/Learn/OfflineHelp/https.docs.derivative.ca/*.htm`, = this build) and td-port READMEs.
No reference images saved (so no `refs/J/`).

**Goes deeper than, does not repeat:** `D_camera_mediapipe.md` (camera inputs, permission blocker, plugin internals, Farneback 42 ms probe, recipes R1-R6),
`B_visual_techniques.md` (technique catalogue), `E_live_rig.md` (rig, fail-safe). Read D §0, §3, §4 first; this file adds the *looks*, *who did them*, a per-technique
chain/latency/robustness/cost verdict, and the PF26 ranking.

Notation: **doc** = URL read this session; **in-build doc** = offline help of 2025.31550; **td-port** = README in `td-port/` (measured *outside* TD unless stated);
**UNVERIFIED** = memory, search-result summary I could not open, vendor/author claim, or my own reasoning with no venue evidence.
**Search limit:** the session's WebSearch budget ran out part-way (200 calls shared by all agents). Everything after that was WebFetch of known URLs. Items I could not open are marked.

---

## 1. Summary

1. **The cheapest, safest camera-driven things need no ML at all**: grade/duotone/halftone/edge/RGB-split/frame-delay on the camera picture, echo/trails via Cache TOP, slit-scan via Texture 3D + Time Machine TOP, and motion-energy from frame differences. They survive strobes/haze better because they never need to *recognise* a person, and they are the only family that adds one frame of latency instead of 2-4.
2. **Real tours do exactly this and name it "IMAG effects"**: Coldplay MOTS 2022 (prismatic trails, motion-generated particles, reverse-playback capture of band and audience), Rammstein 2019 (masking, Motion Datamosh, frame delays), Pierce the Veil 2025 (HLSL halftone, grunge, Virtual Background), Benee 2020 (bodies made of particle systems), Lil Baby at Made in America 2021 (background removal, fire/lightning on the artist), Olivia Dean 2026 (per-song LUT/colour grade). **All were Notch on Disguise/Windows RTX servers**, not TouchDesigner (see §5, links). TD can reproduce the looks; nobody in these sources documents TD doing it on a tour (one search-summary says an Avenged Sevenfold TD show did, UNVERIFIED, page blocked).
3. **Person mask is the key enabler for the premium looks** (spectrum through the artist, host cut-out, mask echo, particles that hug the body). On this Mac the viable route is a **native arm64 helper** (td-port `jzb_camera_bridge`: Apple Vision mask, 33 ms median round trip outside TD) or the MediaPipe plugin (Chromium, camera-permission risk). Both are untested inside TD.
4. **NVIDIA-only TD ops (Body Track, Face Track, NVIDIA Background, Optical Flow TOP) do not exist on this Mac** (D §1.1, probed). Every body look below uses another route.
5. **Apple Vision exposes more than the bridge uses**: body pose (macOS 11+), hand pose (macOS 11+), 3D body pose (macOS 14+), optical flow (macOS 11+), person instance masks (macOS 14+) per Apple's JSON docs. The bridge currently does depth, person mask, faces. Adding pose/hand/optical-flow requests is a bridge extension, not a new tool.
6. **Latency is the show-critical number nobody has measured in the venue chain.** EBU R37 (2007) allows sound-before-picture 40 ms and sound-after-picture 60 ms for TV. ML looks arrive 2-4 frames late (td-port); a TD/Syphon/Arena hop adds more. So: **no ML on the lip-sync path**; ML looks are decorative overlays that may lag.
7. **Robustness under strobe/LED wash/haze is unevidenced for every ML model** (all vendor numbers are phone or lab). Frame-difference/optical-flow looks are *actively fooled* by strobes (whole-frame luminance change), so they need td-port's "Steady" compensation and a flash limiter. Treat as UNVERIFIED until the real feed is seen.
8. **Flash rule bites hardest on echo, slit-scan, datamosh and mask wobble** (>3 flashes/s over >25% of the screen is out; `concert-visuals-research/README.md` §4 via D). Every item below ends in a rate limiter + fail-safe Switch (D §4.2).
9. **Venue camera plan is still open** (D §0), so IMAG/crowd looks can only be proven on the Mac webcam or a clip until the feed exists. Everything in the top 10 has a stage where it can be built and tested with a recorded clip.
10. **Top 10 for PF26 in §6**: (1) IMAG stylise stack, (2) person-mask spectrum fill / host cut-out, (3) echo + prismatic trails, (4) slit-scan time smear, (5) motion-reactive smear/glow, (6) mask-driven particles, (7) depth fog/grade, (8) face-aware crop + brackets, (9) hand-gesture cue, (10) pose-driven ribbons.

---

## 2. Findings table

Cost class: **L** = TOP/GLSL only, no CPU readback, no model; **M** = GPU-heavy or CPU readback (Script TOP/OpenCV) or VRAM-heavy history; **H** = needs an ML model in a helper/Chromium plus readback and upload. Latency column = *extra* frames beyond the camera, from cited figures only; "-" = no figure exists. Robustness = my judgement (no venue evidence), marked H/M/L = survives strobe/LED wash/haze.

| ID | Technique (look) | Prior art | TD op chain (short) | Mac route | Added latency | Robust | Cost | PF26 rank |
|---|---|---|---|---|---|---|---|---|
| J1 | **IMAG stylise stack** (duotone, halftone, edge/neon, RGB split, grunge, frame-delay) | Pierce the Veil 2025, Rammstein 2019, Coldplay 2022, Olivia Dean 2026 | In -> Crop/Fit 2:5 -> Level/Lookup -> GLSL halftone/Edge -> Composite -> Switch -> Null -> Syphon | none needed | 0 extra ML; TD/Syphon hop only (not measured) | H | L | **1** |
| J2 | **Person-mask spectrum fill / cut-out / host over collage** | Lil Baby MIA 2021, Pierce the Veil 2025 (Notch Virtual Background) | Camera -> bridge mask (Script TOP) -> Blur -> Matte/Multiply with PRISM gradient -> Over | Vision helper or MediaPipe plugin | 2 frames if picture is synced to mask (td-port); mask 33 ms median round trip | M | H | **2** |
| J3 | **Echo / ghost trails / prismatic trails / reverse-playback capture** | Coldplay MOTS 2022; Rammstein frame delays | Camera (or J2 mask) -> Cache TOP -> N Cache Select -> tint -> Composite/Add | none (full-frame) or J2 | 0-1 | H (full-frame), M (masked) | L-M (VRAM) | **3** |
| J4 | **Slit-scan / time displacement on live camera** | Trumbull 1968+ (film); interactive catalogue 1988-2009 (Levin page); Lake Heckaman GLSL 2026; official lesson | Camera -> Texture 3D TOP -> Time Machine TOP (2nd input = ramp/noise/mask) | none | 0-1 (+ history is a time smear by design) | H | M (VRAM) | **4** |
| J5 | **Motion-reactive smear / sparks / streaks / flow colour** | Memo Akten Body Paint 2009; Coldplay "motion-generated particles" | td-port `flow_fx` GLSL block matching; or OpenCV Farneback/DIS Script TOP | no NVIDIA; GLSL or CPU | Farneback probe: 42.5 ms median per cook (D R2) | L (strobe fools it) | M | **5** |
| J6 | **Mask-driven particles ("body made of particles", particles hugging the artist)** | Benee 2020 (Notch); Derivative job post 2024 (a request) | J2 mask -> TOP to POP / particlesGpu -> Render | mask route as J2; POPs in build | as J2 | M | H | **6** |
| J7 | **Depth fog / grade / key / displacement / point cloud** | Torin Blankensmith Depth Anything plugin + tutorial (Oct 2025) | camera -> bridge depth -> fog/grade/key GLSL; or Displace/instance | Core ML helper or Torin plugin | td-port: 66.7 ms median round trip (~4 frames at 60 fps) | L-M | H | **7** |
| J8 | **Face-aware crop and brackets** | td-port Tracker; MediaPipe 478 landmarks / 52 blendshapes | camera -> bridge faces / MediaPipe -> Crop/Fit + frame corners | helper or plugin | 17-70 ms per detection at 960x540 (td-port) | M | M-H | **8** |
| J9 | **Hand-gesture cue** (open palm = flare) | Kat Zhang, 80.lv Oct 2024 (hand-driven particles, MediaPipe plugin) | plugin hand CHOP -> Logic -> Trigger (rate limit) -> Switch/OSC | MediaPipe plugin or Vision hand pose | HandLandmarker 12-17 ms on a Pixel 6 (not Mac) | L | M | **9** |
| J10 | **Pose ribbons / light beams from wrists, stick-figure** | Torin YOLO pose plugin (Oct 2025); MediaPipe pose 33 landmarks | pose CHOP -> Trail/Instance/Line -> Composite | plugin / Vision body pose / 3D (macOS 14) | - | L | H | **10** |
| J11 | **Optical-flow fluid / dye** | touchFluid (MIT); Aurelian Ionus TOP fluid 2025; Dobryakov WebGL (MIT); Kurt Kaminski "Melange" | flow field -> TOP fluid feedback loop (advect, pressure, dye) | GLSL/TOPs, flow from J5 | - | L | M-H | not ranked (see §3) |
| J12 | **Mirror / kaleidoscope of camera or mask** | classic; td-port `kaleido`; Text Rain-style mirrored video (Utterback/Achituv) | Flip/Transform -> Tile -> Composite | none | 0 | H | L | folded into J1/J3 |
| J13 | **Live datamosh / glitch on IMAG** | Rammstein 2019 (Notch Motion Datamosh node) | flow field + Feedback + Displace | GLSL or OpenCV flow | - | M | M | not ranked (flash risk, §3) |
| J14 | **Crowd energy level -> glow/pulse** | td-port `crowd_energy` | frame diff (Steady) -> level CHOP -> look | none | 1 frame (td-port) | L (strobe) | L | needs a crowd cam; conditional |
| J15 | **Phone depth/pose sensor as camera** | TDLidar (Aristides Lintzeris, 2 May 2026) | NDI In + OSC In | iPhone, Wi-Fi | author claims 30-80 ms | M | M | excluded (§3) |

---

## 3. Per-item details

### J1 - IMAG stylise stack (no ML)

**Look.** The artist stays recognisable; the *picture* is branded: duotone Plum/Orchid, halftone dots, neon edge, spectrum RGB split on drops, a constant grunge overlay, frame-delay stutter.
**Who.** FRAY Studio on Pierce the Veil 2025: "Custom HLSL shaders evoked halftone print effects", a homemade grunge overlay across the show, Notch 1.0, nearly all real-time ([notch.one](https://www.notch.one/madewithnotch/pierce-the-veil-world-tour-2025)). Rammstein 2019 (Woodroffe Bassett; Tim Hornung video/Notch programmer): colour grade per song to match lighting, distortion/noise, strobes and frame delays, Motion Datamosh ([notch.one](https://www.notch.one/madewithnotch/rammstein-european-tour-2019)). Olivia Dean 2026 (FRAY Studio + 1826 Studio): live camera feeds graded with custom LUTs and Notch per song, on Disguise GX 3 ([ISP Audio](https://www.isp-audio.com/en/installation-case-studies/audiovisual-installation/13332-olivia-dean-s-tour-replaces-imag-screens-with-a-real-time-projection-system), 29 Jun 2026). A touring practitioner source recommends pre-rendering heavy looks and keeping only light real-time treatments such as IMAG effects live, because of frame-rate and stability risk at big shows (search-result summary of [Interactive & Immersive HQ](https://interactiveimmersive.io/blog/deployment/creating-dj-visuals-with-touchdesigner/); page text not retrievable, UNVERIFIED wording).
**TD chain.** `Video Device In / NDI In / Syphon Spout In` -> `Crop`/`Fit` to 2:5 -> `Level`/`Lookup` (brand ramp) -> `GLSL TOP` (halftone, Sobel edge) -> `Transform`/`Channel Mix` (RGB offset) -> `Composite` (grain, corner frame) -> `Switch TOP` (clean fallback) -> `Null` -> `Syphon Spout Out`. D recipe R1 has the same chain; this adds halftone/edge/frame-delay (`Cache TOP` with negative Output Index = delay, in-build `Cache_TOP.htm`).
**Mac constraints.** None. Pure TOPs.
**Latency.** No ML. The unmeasured part is TD + Syphon + Arena. Rule from D: keep IMAG itself a plain camera layer in Arena (layers 3-4) and use TD for an *optional* look layer; or do duotone/RGB split in Arena where the same effect exists.
**Robustness.** High: nothing depends on image content. Colour flicker from LED backgrounds is the camera's problem (D §4.2).
**Cost.** L. **Licence.** Own code.
**Caution.** The Notting Hill Carnival account (published 2 Sep 2024) is the only first-hand TD-vs-Resolume failure I found: TD alone, production team on Resolume, "misalignment between the different setups led to distorted visuals", TD could not run live, MP4 backups loaded the next day ([Substack](https://oliviaema.substack.com/p/producing-digital-art-for-notting)). Lesson matches E: test the exact canvas/aspect through Arena before the day.

### J2 - Person mask: spectrum through the artist, cut-out, host over collage

**Look.** The performer filled with the PRISM spectrum gradient, or isolated over a collage/plain field; brand duotone outside; neon rim. Maps to `prism-brand`, "IMAG background removal" (branded-look-ideas B4), host cut-out (ref 123) from D §4.1.
**Who.** Lil Baby, Made in America 2021: T2 Visuals (Tanner Thompson, Notch operator; Ivan Ceron, video programmer) used Notch's new real-time background removal "developed in collaboration with NVIDIA" for fire/lightning/electric glow on the artist, on a custom RTX Titan server feeding Resolume ([notch.one](https://www.notch.one/madewithnotch/lil-baby-at-made-in-america-festival-2021/)). Pierce the Veil 2025 used Notch Virtual Background to "foreground the band members during special moments" ([notch.one](https://www.notch.one/madewithnotch/pierce-the-veil-world-tour-2025)). Rammstein masked around the IMAG to affect every image ([notch.one](https://www.notch.one/madewithnotch/rammstein-european-tour-2019)).
**TD chain.** (a) td-port `person_key` (6 looks: cut-out, silhouette, neon rim, echo, per-person colour, shadow; Smoothing/Grow/Softness; Sync Picture), fed by the bridge. (b) MediaPipe plugin `Detectsegments`: native masks 256x256 (Selfie, Multiclass), 256x144 (Landscape), `seg_data` Script TOP, WebSocket ([README](https://github.com/torinmb/mediapipe-touchdesigner)). Then `Resolution TOP` -> `Blur` -> `Matte`/`Multiply` with a gradient TOP -> `Over`. D recipe R3.
**Mac route facts.**
- Apple `VNGeneratePersonSegmentationRequest`: macOS 12+ ([Apple JSON](https://developer.apple.com/tutorials/data/documentation/vision/vngeneratepersonsegmentationrequest.json)); quality levels fast/balanced/accurate and "one combined mask" are from memory (UNVERIFIED). `VNGeneratePersonInstanceMaskRequest`: macOS 14+ ([Apple JSON](https://developer.apple.com/tutorials/data/documentation/vision/vngeneratepersoninstancemaskrequest.json)); "max four people" UNVERIFIED.
- td-port numbers (outside TD): Fast mask 33.3 ms median round trip, compute 19.7 ms, ~32/s; Balanced 33.4/50.2 ms. Their own caveat: keys people at medium/close range, "a dense crowd keys as one blob and small far people are missed".
- MediaPipe SelfieSegmenter 256x256: 33.46 ms CPU / 35.15 ms GPU **on a Pixel 6** ([Google](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter)) - a phone figure, not Mac. Plugin input limited to 720p; `totalInToOutDelay` "at least 3 frames" in 2022.33910 ([README](https://github.com/torinmb/mediapipe-touchdesigner)); plugin README says use "MultiCam" model for the most accurate webcam cutout.
- NVIDIA Background TOP: not supported here (D). Notch Virtual Background is NVIDIA-linked; Mac availability UNVERIFIED and Notch is not a TD route.
**Latency.** Mask arrives late; "Sync Picture" delays the picture to match (td-port: a frame or two). That delays the picture it covers, so use J2 on a *decorative duplicate* of the camera, not the IMAG layer people lip-read.
**Robustness.** Medium at best. Backlight, saturated LED wash and haze are not what these models were trained on (D §4.2, UNVERIFIED for this venue). A wobbling mask edge is a flash source: smooth it (PersonKey has controls) and rate-limit.
**Cost.** H (helper + readback + upload; none of it measured inside TD). **Licence.** Plugin MIT; Depth/segmentation models in the bridge: Apple Vision is OS; Depth Anything V2 Small Core ML is Apache-2.0.

### J3 - Echo, ghost trails, prismatic trails, reverse-playback capture

**Look.** The performer leaves 2-6 delayed, tinted copies (prismatic ghosts); or a bright trail; or a short "replay" that runs backwards.
**Who.** Coldplay MOTS 2022 (FRAY Studio Notch design, Leo Flint video designer): "prismatic trails" on Paradise and A Sky Full of Stars; "live recording capture with reverse playback of the band and audience" on The Scientist ([notch.one](https://www.notch.one/madewithnotch/coldplay-music-of-the-spheres-tour-2022/)). Rammstein: strobes and frame delays ([notch.one](https://www.notch.one/madewithnotch/rammstein-european-tour-2019)).
**TD chain.** `Cache TOP` (stores images in GPU memory; "acts as a delay if you set Output Index to negative numbers and leave Active On"; Cache Size, Replace, Pre-Fill; in-build `Cache_TOP.htm`) -> several `Cache Select TOP` at offsets (e.g. 4, 8, 12 frames) -> `Level`/tint each (Plum, Orchid, Amber) -> `Add`/`Composite`. Reverse capture = Active pulse then animate Output Index backwards. For person-only echo use J2 mask (PersonKey Person Echo layer exists in td-port, not run in TD). td-port also has `echo` (`JZBT_Echo.tox`) and `motion_trail` as prior art in the repo.
**Mac.** None. **Memory (arithmetic, not measured):** RGBA8 1080x1920 = 7.91 MiB/frame, so 120 frames = 0.93 GiB; at 1152x2880 (IMAG face size at 75%) 12.66 MiB/frame, 120 frames = 1.48 GiB. RGBA16F doubles this.
**Latency.** 0-1 frame for the live copy; echoes are late by design.
**Robustness.** High full-frame (works on any image). Flash risk: bright echoes pulsing at beat rate on a big LED; cap pulse rate, keep trails soft (user: "soft light not blades", DIRECTIONS §3).
**Cost.** L-M. **Licence.** Own.

### J4 - Slit-scan / time displacement on live camera

**Look.** Time becomes space: the performer's motion smears into streaks, a wave sweeps across the picture (offset by a ramp), or bends by a noise field. On the portrait IMAG faces it reads as the PRISM "double-exposure with motion blur" poster feel (B §4).
**Who/history.**
- Douglas Trumbull's Stargate (2001) from the 19th-century strip-photography idea ([Red Shark News](https://www.redsharknews.com/douglas-trumbull-and-how-slit-scan-changed-sfx)).
- Interactive/live versions 1988-2009 in Golan Levin's slit-scan catalogue, edited to 2015: Bill Spinhoven *Time Stretcher* (1988-94), Toshio Iwai *Another Time, Another Space* (1993), Daniel Rozin *Time Scan Mirror* (2004), HC Gilje *Bufferzone/Elevator* (2004, **live slit-scan of dancers in theatre**), Glen Murphy *Robot Mirror* (2005, brightness as time-displacement map) ([flong.com](https://www.flong.com/archive/texts/lists/slit_scan/index.html)).
- TD: official lesson "Slit Scan using the Time Machine TOP" ([Derivative Learn](https://learn.derivative.ca/courses/200-intermediate/lessons/202-tops-intermediate/topic/slit-scan-using-the-time-machine-top/): Texture 3D + Time Machine, no parameters or cost given); Lake Heckaman's real-time GLSL slit-scan, posted 22 Feb 2026 by elburz ([Derivative](https://derivative.ca/community-post/tutorial/glsl-slit-scan-effect-touchdesigner/74007); resolution/frames/licence not stated). A paid 20-minute webcam course exists (Jack DiLaura, $147, via search summary, UNVERIFIED).
**TD chain (doc-confirmed).** `Texture 3D TOP` (history of N frames) -> `Time Machine TOP` input 1; **input 2 sets the per-pixel time offset** (black = oldest layer, white = newest; Black Offset / White Offset with units index/frames/seconds/fraction) (in-build `Time_Machine_TOP.htm`). Input 2 can be a horizontal ramp (classic slit-scan), a `Noise` TOP (organic), an animated ramp (sweeping wave) or a person mask (artist in present time, background smeared: J2+J4). Alternatively `Cache TOP` + `GLSL` sampling an array. td-port already has `slit_scan` (`JZBT_SlitScan.tox`) and `slit_volume` (time-block, 512 MiB cap) - not run in TD.
**Mac.** None. VRAM: same arithmetic as J3. A Glama-MCP tool doc claims 1080p RGBA16 costs depth x 32 MB (600 deep = ~5 GB); my arithmetic gives 1080x1920 RGBA16F = 15.8 MiB/frame, so their figure refers to a different size - treat as UNVERIFIED and measure.
**Latency.** Live pixel is current; the effect is deliberately time-smeared.
**Robustness.** High for the image process; the *look* is the risk: B §4 flags slit-scan and tiling as highest flash risk when offset textures move fast. Keep offsets slow (seconds), avoid hard-edged black/white ramps.
**Cost.** M (VRAM). **Licence.** Official lesson free; community GLSL licence not stated.

### J5 - Motion-reactive looks from optical flow (smear, sparks, streaks, flow colour)

**Look.** Whatever moves (singer, dancers, flag) drags, sparks or glows in direction colours; still areas stay clean.
**Who.** Memo Akten, *Body Paint* (2009): infrared camera, custom openFrameworks/OpenCV software, "movement creates paint", detects movement rather than people, scales from 4 x 2.25 m to 50 x 5 m ([memo.tv](https://www.memo.tv/works/body-paint/)). Coldplay: "motion-generated particles" on Biutyful ([notch.one](https://www.notch.one/madewithnotch/coldplay-music-of-the-spheres-tour-2022/)). Kurt Kaminski, *Melange* (UCSB MAT): 2D fluid driven by depth camera + optical flow in TD (search summary, UNVERIFIED). An Interactive & Immersive HQ tutorial feeds an optical flow into a `particlesGpu` COMP's second input using "any regular camera feed" (search summary of [GPU particles tutorial](https://interactiveimmersive.io/blog/touchdesigner-lessons/touchdesigner-gpu-particles/); page text not retrievable, UNVERIFIED).
**TD chain / routes on this Mac.**
- **No NVIDIA Optical Flow TOP here** (D). A forum summary says TD's own optical flow uses NVIDIA's SDK and OpenCV is the non-NVIDIA alternative (search summary, UNVERIFIED).
- (a) td-port `flow_fx`: GPU block matching on a quarter-size grey copy; motion resolution in integer steps of 4 source px per frame in 32 px blocks, so slow/small motion may not register; "Steady" removes camera pan and whole-frame light changes (td-port README). Not run in TD.
- (b) OpenCV in a Script TOP: Farneback measured 42.5 ms median, p95 109 ms per cook at 320x180 flow from 640x360 input under Rosetta with other work running (D R2, probed). `cv2.optflow` (DIS) exists in TD's OpenCV 4.11 (D §3.2, probed); DIS authors claim "300 Hz up to 600 Hz on a single CPU core" (Kroeger et al., [arXiv 1603.03590](https://arxiv.org/abs/1603.03590), 2016, their hardware/resolution) - unmeasured here, worth one probe (it would turn a 42 ms cook into a few ms if it carries over; UNVERIFIED).
- (c) Apple `VNGenerateOpticalFlowRequest`, macOS 11+ ([Apple JSON](https://developer.apple.com/tutorials/data/documentation/vision/vngenerateopticalflowrequest.json)) in the native helper: not in the bridge today; speed unmeasured.
**Latency.** td-port: level one frame late. **Robustness.** Low-medium for strobes: a strobe changes every pixel's luminance and appears as motion. That is why `crowd_energy`/`flow_fx` have "Steady" and Floor/Gain calibration. Haze scatters and lowers flow quality (UNVERIFIED).
**Cost.** M. **Licence.** Own / OpenCV Apache-2.0 (OpenCV licence not re-checked this session).

### J6 - Mask-driven particles ("body made of particles")

**Look.** Thousands of points on and around the silhouette, flowing with motion; the performer becomes a particle figure while the real person fades.
**Who.** Benee's NZ tour, Oct 2020: IMAG ranging "from basic colour grading to bodies made up of particle systems" built in Notch by Ryan Sheppard for Ben Dalgleish (Human Person), layered live via grandMA2 ([notch.one](https://www.notch.one/madewithnotch/utterly-seamless-imag-effects-for-live-concerts-utterly-seamless-imag-effects-for-live-concerts/); the page that URL returns is the Benee case). TD-side: a 2024 Derivative job post asks for particles that "cling to a human silhouette and flow around movement" using MediaPipe in a dark room with MadMapper output (a request, not a delivered work) ([derivative.ca](https://derivative.ca/job-post/interactive-touchdesigner-dance-performance/69298)). Kat Zhang's MediaPipe-plugin hand-controlled particles (80.lv, 21 Oct 2024) are the nearest TD-performance-adjacent example ([80.lv](https://80.lv/articles/awesome-sci-fi-inspired-gestural-experiments-with-touchdesigner/)).
**TD chain.** J2 mask -> (a) POP route: Jack DiLaura's tutorial builds a POP network from a TOP texture into particles with colour attributes (posted 29 Jan 2026, [Derivative](https://derivative.ca/community-post/tutorial/touchdesigner-3d-particles-2d-textures/73861); it shows TOP *patterns*, not live video - live-camera use is unconfirmed); POPs are in this build (97 classes, `ops/POP.md`). (b) `particlesGpu` palette with a TOP source: Derivative lists webcam and Kinect as sources (search summary, UNVERIFIED). Emit where mask > threshold (sample the mask at spawn), add a flow-field force from J5 so particles follow motion, Render TOP over transparent.
**Mac.** POPs are GPU ops on Metal/Vulkan; max-particle count and cost not measured (`ops/POP.md` for what is known).
**Latency/robustness/cost.** As J2 plus render cost; H.

### J7 - Depth: fog, grade, key, displacement, point cloud

**Look.** Haze that thickens behind the artist; near/far colour grade; depth-keyed cut; the artist lifted off the background as relief or point cloud.
**Who.** Torin Blankensmith: Depth Anything V2 and YOLO plugins (post 2 Oct 2025; "works on Mac and PC", licence/price not stated, [derivative.ca](https://derivative.ca/community-post/yolo-depth-anything-plugins-real-time-tracking-depth-without-extra-hardware/72940)) and a tutorial (10 Oct 2025) building instanced visuals with trails, occlusion, depth exports, Josef Pelz's PCR point-cloud renderer and Prismatic's SSDR (optional Patreon add-ons) ([derivative.ca](https://derivative.ca/community-post/tutorial/depth-anything-touchdesigner-plugin-tutorial/73018)). Obscura-style depth camera work is out of scope (no sensor).
**Mac.** Core ML Depth Anything V2 Small F16 on Apple's own page: 32.80 ms on MacBook Pro M1 Max (macOS 15.0, Neural Engine dominant), 24.58 ms on M3 Max; Apache-2.0; 24.8M parameters; input size for the latency test not stated ([Hugging Face apple/coreml-depth-anything-v2-small](https://huggingface.co/apple/coreml-depth-anything-v2-small)). td-port measured **66.7 ms median round trip** (compute 53.9 ms) through its helper outside TD. Both are relative (not metric) depth from one camera.
**TD chain.** td-port `depth_fx` (Fog / Grade / Key, Smoothing, Randomness) or the Torin plugin; for displacement: `Displace`/GLSL MAT on a `Grid` SOP/POP, or td-port `video_relief` (luma -> height, no ML).
**Robustness.** Single-image depth under LED wash/haze is unevidenced; temporal flicker needs smoothing (td-port has it); night-outdoor shots with a dark sky have little to estimate - UNVERIFIED.
**Latency.** ~4 frames at 60 fps (td-port). **Cost.** H. Decorative only.

### J8 - Face-aware crop and brackets

**Look.** The 2:5 IMAG crop re-centres on the face (headroom), thin PRISM triangle corners/brackets follow the face.
**Who/route.** td-port `tracker` (bridge kind 4 faces: 17-70 ms per detection at 960x540; "finds faces, does not recognise anyone"). MediaPipe Face Landmarker: 478 3D landmarks, 52 blendshape scores, optional facial transformation matrix, smoothing only when `num_faces`=1 ([Google](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker)); no latency given on the page.
**TD chain.** faces CHOP/DAT -> `Lag CHOP` (smooth) -> `Crop`/`Transform` (virtual camera move) + `Composite` frame. Smooth hard: a jittering crop is a flash/nausea source.
**Cautions.** Auto-reframing the *real* IMAG changes what the audience sees of the artist: it is a camera-director decision (D §4.2 lip-sync/lower-third rules apply). Brackets must not cover names/logos. Audience-face walls are the production's call (td-port Tracker).
**Cost.** M-H.

### J9 - Hand gestures as cues

**Look.** The artist (or host) raises an open palm and a flare/sting fires; fingers control particle speed (Kat Zhang). **Route.** Plugin Hand tracking tox (landmarks + gestures, MIT); Google HandLandmarker: 21 keypoints, default `num_hands`=1, 12.27 ms GPU / 17.12 ms CPU on a Pixel 6, trained on ~30K real-world images plus synthetic ([Google](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker)). Apple Vision hand pose, macOS 11+ ([Apple JSON](https://developer.apple.com/tutorials/data/documentation/vision/vndetecthumanhandposerequest.json)).
**TD chain.** D recipe R4 (`Logic` -> `Trigger` with min interval 0.33 s -> Switch/OSC); add stable-for-N-frames hold. **Needs** a medium/close camera that sees hands; the IMAG artist cam is the only plausible source. **Robustness.** Gloves, microphones, microphone-in-hand and stage haze will hide hands (UNVERIFIED). False fire during a show is worse than no gesture: recommend operator-confirm (button) rather than autonomous trigger.

### J10 - Pose ribbons, beams, stick figures

**Look.** Glowing ribbons from wrists/ankles, beams between joints, a spectrum skeleton, hit flares on a jump. **Route.** MediaPipe Pose Landmarker: 33 3D landmarks, `num_poses` default 1, lite/full/heavy bundles, optional segmentation mask, no latency given ([Google](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker)); Torin's YOLO plugin adds multi-person pose and Nano face (Oct 2025, runtime not stated); Apple Vision body pose macOS 11+, 3D body pose macOS 14+ ([Apple JSON](https://developer.apple.com/tutorials/data/documentation/vision/vndetecthumanbodyposerequest.json), [3D](https://developer.apple.com/tutorials/data/documentation/vision/vndetecthumanbodypose3drequest.json)). **TD chain.** pose CHOP -> `Trail CHOP` -> `CHOP to`/instanced geometry or `Line` -> `Composite`. **Needs** full-body shots; stage costumes, other performers and lighting changes break tracking (UNVERIFIED). Lowest priority: most failure modes, least PRISM-brand fit.

### J11 - Optical-flow fluid / dye (not ranked)

touchFluid (kamindustries): lightweight 2D semi-Lagrangian solver, vorticity, temperature, buoyancy, obstacles; .toe + .tox; **MIT**; TD version and Mac not stated ([GitHub](https://github.com/kamindustries/touchFluid)). Aurelian Ionus' TOP-only fluid translated from Bruno Imbrizi's, posted 6 Mar 2025, optical flow taken from the palette component (NVIDIA-linked on this Mac, D), no licence/version/perf stated ([Derivative](https://derivative.ca/community-post/asset/fluid-simulation-tops/71458)). Dobryakov WebGL Fluid Simulation, MIT ([GitHub](https://github.com/PavelDoGreat/WebGL-Fluid-Simulation)). **Why not ranked:** it needs J5's flow, adds a per-frame multi-pass solver at the same time as the ML helpers, reads as "liquid" (the user already restricts liquid looks: DIRECTIONS §2 "non-liquid first"), and a fluid that reacts to strobes is a flash risk. Keep as a later extra.

### J12 / J13 - Mirror, kaleidoscope, datamosh (folded / not ranked)

Mirrored-video interaction is old: *Text Rain* (Romy Achituv and Camille Utterback; first shown 1999 per the page's earliest listed date) shows a mirrored black-and-white video of the viewer with falling letters that land on anything "darker than a certain threshold" ([camilleutterback.com](https://www.camilleutterback.com/projects/text-rain/)); Rafael Lozano-Hemmer's *Body Movies* (2001; Linz 2002) shows portraits only inside passers-by's shadows ([Canadian Art](https://canadianart.ca/features/rafael-lozano-hemmer-body-movies/)). The shadow/threshold idea (the silhouette *is* the interface) is what J2 + particles generalise. Kaleidoscope on the camera is one `Tile`/`Flip` chain (td-port `kaleido`), folded into J1. Live datamosh (Rammstein's Motion Datamosh node) needs flow + feedback and produces hard, flashing blocks; not recommended for PF26 because of the flash rule (and datamosh tutorials exist on Interactive & Immersive HQ, a "Part #3" page title was all I could open).

### J14 - Crowd energy

td-port `crowd_energy`: movement only, 0..1 `level` CHOP, one frame late, calibrate with Floor/Gain; no detection. **Blocker:** no document names a crowd camera (D §0). Conditional: if the organiser provides one, it is the cheapest crowd-reactive item. Strobe/haze will inflate the level; Steady and a Floor set during a lighting-heavy rehearsal are mandatory.

### J15 - Phone as depth/pose sensor (excluded)

TDLidar (Aristides Lintzeris, 2 May 2026): iPhone TrueDepth/LiDAR to NDI + OSC (body, face blendshapes, hands); the author's own claim 50-80 ms on Wi-Fi 5, ~30 ms on Wi-Fi 6, no test method ([Derivative](https://derivative.ca/community-post/tdlidar-%E2%80%94-turn-your-iphone-realtime-depth-tracking-and-audio-sensor-touchdesigner)). Excluded: Wi-Fi/NDI multicast at an outdoor FOH, a phone mounted for a stage, short sensor range, unaudited app (D §3.3). IR cameras/depth sensors (Body Paint used an infrared camera) are the traditional stage answer for strobe immunity; no sensor is in the plan. A practitioner tip that IR tracking suffers from reflective floors and visible stage light was only in a search summary I could not confirm: UNVERIFIED.

---

## 4. Cross-cutting

### 4.1 Which route on this Mac (summary; detail in D §3)
| Route | Gives | Stops you | Measured |
|---|---|---|---|
| No-ML TOP/GLSL | J1, J3, J4, J5(a), J12, J14 | nothing | td-port: not run in TD |
| OpenCV in Script TOP (TD Python, x86_64, cv2 4.11) | flow (Farneback, DIS), blobs, MOG2 | Rosetta CPU, 2x slower Python (D) | Farneback 42.5 ms/cook |
| Native arm64 helper (`jzb_camera_bridge`) | mask, depth, faces; pose/hand/flow possible via Apple Vision | socket + Script TOP upload not proven in TD | mask 33 ms, depth 67 ms, faces 17-70 ms (outside TD) |
| MediaPipe plugin (Chromium Web Render TOP) | mask, hands, pose, face, objects | camera opened by the page: permission/Rosetta unknown; heavier than native (HKU page: "a lot heavier") | none on this Mac |
| iPhone sensor | depth/pose/hand OSC | Wi-Fi, unaudited | author claim only |

### 4.2 Latency budget (arithmetic, not a measurement)
One frame = 16.7 ms at 60 fps, 33.3 ms at 30 fps (the show runs 30 fps, D). EBU R37 (2007, TV): sound before picture 40 ms, after 60 ms ([EBU R37 PDF](https://tech.ebu.ch/docs/r/r037.pdf)); live-venue tolerance and where the PA delay sits is a venue fact I have no source for (UNVERIFIED). Known contributors: mask Sync Picture +1-2 frames (td-port); depth/mask results ~2-4 frames at 60 fps (td-port); MediaPipe plugin >= 3 frames (README, 2022 build); Syphon/NDI hop, capture card, Arena, LED processor: **not measured anywhere in the bundle** (E measured fps, not latency). Rule: IMAG = plain camera layer; every J2/J6/J7/J8 look sits on a duplicate that may lag.

### 4.3 Robustness in the venue (outdoor, night, floodlights, haze, LED wash, strobes)
No source tests any model in this condition. Reasoned risks (UNVERIFIED): backlight and saturated colour wash lower mask/landmark quality; haze lowers contrast for depth and flow; strobes and LED video backgrounds look like global motion to flow/energy looks; camera auto-exposure/flicker is upstream (RUNTIME "test moire and camera flicker"). Mitigations that are in the design already: td-port Steady, Smoothing/Grow/Softness, pass-through when the helper is missing; add: Switch TOP watchdog by result age, rate limiter at the flash rule, and a "freeze last good mask for N seconds" instead of dropping to full picture (a mask that blinks out is a flash). Test with the real feed on the Fri 23 Oct commissioning day (RUNTIME timeline, D §0).

### 4.4 Rules that bind
Names stay whole and uncovered (no face bracket, particle or echo over a name/logo); full-colour PRISM logo only; flash limit; TALK state = IMAG on, low motion, nothing flashing (so J3-J5 off in TALK); TAKEOVER = IMAG off, so camera looks there only as a *secondary* source; Arena operations (Syphon/NDI, layer tests) need the user's go-ahead; premultiplied alpha for anything with a mask going to Arena (memory: overlay-alpha-premultiplied) - verify in Arena's blend.

---

## 5. Ranked recommendations for PF26 (top 10)

Order = value for PRISM x readiness x robustness x lip-sync safety. "Prototype now" = can be built on the Mac webcam or a clip before the venue feed.

| # | Look | Why this rank | Prototype now | Needs from the user / venue |
|---|---|---|---|---|
| 1 | **J1 IMAG stylise stack** (duotone + halftone + frame corner + RGB split on drops) | no ML, no model risk, same family real tours use; branded IMAG is already in the idea bank (#16-17) | yes | camera feed, Arena layer-6 test (go-ahead); decide Arena-grade vs TD-grade |
| 2 | **J2 Person-mask spectrum fill / host cut-out** | strongest "PRISM through the artist" hero; PersonKey exists | yes (webcam permission test or clip) | bridge-in-TD proof; permission test; privacy OK for artist-only |
| 3 | **J3 Echo + prismatic trails** (full-frame first, masked second) | Coldplay-style, cheap, robust; works without ML | yes | flash-rate cap |
| 4 | **J4 Slit-scan time smear** (ramp/noise offsets, slow) | official ops, td-port `slit_scan` exists; matches double-exposure poster feel | yes | flash/tiling review (B §4) |
| 5 | **J5 Motion-reactive smear/sparks** on the artist cam | `flow_fx` designed; no ML; reads as energy | yes (webcam clip) | strobe test; benchmark DIS vs Farneback vs block matching |
| 6 | **J6 Mask-driven particles** | Benee-type "bodies of particles"; high wow for TAKEOVER-like moments | after #2 | POP budget at stage size; TAKEOVER state rules |
| 7 | **J7 Depth fog/grade** | brand-fog look behind artist; needs helper only | after #2 | night-scene depth quality unknown |
| 8 | **J8 Face-aware crop + brackets** | useful for 2:5 framing; low drama | yes | camera director agreement; no audience faces unless production says so |
| 9 | **J9 Hand-gesture cue** | novelty; operator can do the same with a button | yes (pipeline) | camera that sees hands; confirm-by-operator |
| 10 | **J10 Pose ribbons** | most fragile; only for wide dancer shots | yes | full-body feed |
Not in top 10: J11 fluid (liquid + flash + cost), J13 datamosh (flash), J14 crowd energy (no crowd cam; promote if one appears, would rank ~5), J15 phone sensor (excluded).

**Suggested build order (within the "3 ideas then wait" rule):** round 1 = J1, J3, J4 (no ML, safe, all prototype-able), round 2 = J2 once the bridge/permission gates pass, round 3 = J5/J6.

## 6. Measurements worth doing before 24 Oct (each is small, none done)
1. Camera-permission test of Video Device In in TD 2 (D Q1) and whether the bridge round trip works from TD's Script TOP (texture exchange + upload cost) - gates J2/J6/J7/J8.
2. Cache TOP + Time Machine VRAM and cook time at 1080x1920 and 1152x2880 for 60/120 frames (my arithmetic above is not a measurement).
3. DIS (`cv2.optflow`) vs Farneback vs td-port block matching, ms per cook at 320x180 under Rosetta (single probe).
4. Syphon/NDI hop latency with an on-screen frame counter (the only way to get a real chain number).
5. Mask quality/jitter on a recorded night-concert clip with strobes (any public clip; reviewing only), and the strobe response of Steady-compensated flow.

---

## Open questions for the lead
1. Is the camera look an **overlay on a duplicate of IMAG** (my recommendation) or does the user want TD on the actual IMAG layers L1/R1? The second puts ML latency on the lip-sync path.
2. Should camera looks also run on the **centre/wall faces** (e.g. the artist's silhouette across the 30 ft C face) or stay on L1/R1 only? That changes canvas size and the "huge LED" scale of mask artefacts.
3. Go-ahead for: (a) the supervised camera-permission test, (b) a bridge-in-TD test (the bridge binary exists per td-port), (c) the MediaPipe plugin download? Or bridge first?
4. Extend the bridge with Apple Vision **optical flow, body pose, hand pose** (all macOS 11+ per Apple docs)? That keeps all ML in one native process and avoids Chromium; it is a build task for another agent.
5. Will a **crowd camera** exist? If not, J14 stays parked.
6. Is **audience silhouette/face** processing allowed at all (td-port Tracker: the production's call)? J2/J6 as drafted only target the artist/host.
7. Who owns the **flash/strobe review** for echo/slit-scan looks - does the user want a numeric limiter in every camera look (3 events/s, 25% area) by default?
8. Notch-style Virtual Background looks were all done on Windows/NVIDIA servers; if the quality of an Apple Vision mask on real concert footage is not good enough, is a second machine (Windows/RTX with TD's NVIDIA Background TOP) acceptable, or is "no mask on the day" the fallback?

---

## Sources
Prior art on tours (read this session):
- Lil Baby, Made in America 2021 (T2 Visuals): https://www.notch.one/madewithnotch/lil-baby-at-made-in-america-festival-2021/
- Benee NZ tour 2020 (Human Person): https://www.notch.one/madewithnotch/utterly-seamless-imag-effects-for-live-concerts-utterly-seamless-imag-effects-for-live-concerts/
- Rammstein European Tour 2019: https://www.notch.one/madewithnotch/rammstein-european-tour-2019
- Coldplay Music of the Spheres 2022: https://www.notch.one/madewithnotch/coldplay-music-of-the-spheres-tour-2022/
- Pierce the Veil World Tour 2025 (FRAY Studio): https://www.notch.one/madewithnotch/pierce-the-veil-world-tour-2025
- Linkin Park (All Of It Now; Notch 1.0, CDJ data): https://allofitnow.com/work/linkin-park/
- Olivia Dean tour, 29 Jun 2026: https://www.isp-audio.com/en/installation-case-studies/audiovisual-installation/13332-olivia-dean-s-tour-replaces-imag-screens-with-a-real-time-projection-system
- Notting Hill Carnival TD/Resolume mismatch, 2 Sep 2024: https://oliviaema.substack.com/p/producing-digital-art-for-notting
- DJ visuals / IMAG hybrid advice (search summary only): https://interactiveimmersive.io/blog/deployment/creating-dj-visuals-with-touchdesigner/

Artists and history:
- Memo Akten, Body Paint (2009): https://www.memo.tv/works/body-paint/
- Golan Levin, slit-scan catalogue (page edited 26 Feb 2015): https://www.flong.com/archive/texts/lists/slit_scan/index.html
- Trumbull / Stargate: https://www.redsharknews.com/douglas-trumbull-and-how-slit-scan-changed-sfx
- Text Rain (Utterback, Achituv): https://www.camilleutterback.com/projects/text-rain/
- Body Movies (Lozano-Hemmer): https://canadianart.ca/features/rafael-lozano-hemmer-body-movies/
- Kat Zhang gestural particles, 80.lv 21 Oct 2024: https://80.lv/articles/awesome-sci-fi-inspired-gestural-experiments-with-touchdesigner/
- Derivative job post, dancer-hugging particles (Apr 2024): https://derivative.ca/job-post/interactive-touchdesigner-dance-performance/69298

TouchDesigner and community:
- In-build docs: `Time_Machine_TOP.htm`, `Cache_TOP.htm` in `TouchDesigner 2.app/Contents/Resources/tfs/Samples/Learn/OfflineHelp/https.docs.derivative.ca/` (build 2025.31550)
- Official slit-scan lesson: https://learn.derivative.ca/courses/200-intermediate/lessons/202-tops-intermediate/topic/slit-scan-using-the-time-machine-top/
- Lake Heckaman GLSL slit-scan (elburz, 22 Feb 2026): https://derivative.ca/community-post/tutorial/glsl-slit-scan-effect-touchdesigner/74007
- POP particles from textures (Jack DiLaura, 29 Jan 2026): https://derivative.ca/community-post/tutorial/touchdesigner-3d-particles-2d-textures/73861
- GPU particles + optical flow (search summary only): https://interactiveimmersive.io/blog/touchdesigner-lessons/touchdesigner-gpu-particles/
- Torin Blankensmith YOLO + Depth Anything plugins (2 Oct 2025): https://derivative.ca/community-post/yolo-depth-anything-plugins-real-time-tracking-depth-without-extra-hardware/72940
- Depth Anything tutorial (10 Oct 2025): https://derivative.ca/community-post/tutorial/depth-anything-touchdesigner-plugin-tutorial/73018
- MediaPipe TD plugin README (MIT): https://github.com/torinmb/mediapipe-touchdesigner
- HKU note on plugin weight: https://bookstack.hku.nl/books/touchdesigner/page/mediapipe-for-bodytracking-in-td-no-kinect-needed/export/markdown
- touchFluid (MIT): https://github.com/kamindustries/touchFluid
- TOP fluid (Aurelian Ionus, 6 Mar 2025): https://derivative.ca/community-post/asset/fluid-simulation-tops/71458
- Dobryakov WebGL fluid (MIT): https://github.com/PavelDoGreat/WebGL-Fluid-Simulation
- TDLidar (2 May 2026): https://derivative.ca/community-post/tdlidar-%E2%80%94-turn-your-iphone-realtime-depth-tracking-and-audio-sensor-touchdesigner

Models and platform:
- Apple Vision JSON docs (platform availability): https://developer.apple.com/tutorials/data/documentation/vision/vngeneratepersonsegmentationrequest.json , .../vngeneratepersoninstancemaskrequest.json , .../vndetecthumanbodyposerequest.json , .../vndetecthumanbodypose3drequest.json , .../vndetecthumanhandposerequest.json , .../vngenerateopticalflowrequest.json
- Core ML Depth Anything V2 Small (Apple, Apache-2.0): https://huggingface.co/apple/coreml-depth-anything-v2-small
- MediaPipe Image Segmenter: https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter
- MediaPipe Pose Landmarker: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
- MediaPipe Hand Landmarker: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker
- MediaPipe Face Landmarker: https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker
- DIS optical flow (Kroeger et al., 2016): https://arxiv.org/abs/1603.03590
- EBU R37 (2007), A/V relative timing in TV: https://tech.ebu.ch/docs/r/r037.pdf

Local (read, not copied): `td-port/INVENTORY.md`, `td-port/{camera_bridge,person_key,depth_fx,tracker,flow_fx,crowd_energy,slit_volume,video_relief}/README.md`, `jazib-td-mcp/docs/research/{BRIEF,README,DIRECTIONS,B_visual_techniques,D_camera_mediapipe}.md`.

Items I tried and could not open (so not relied on): Sydney Sousa's UT thesis (Avenged Sevenfold TD IMAG case, HTTP 403), Interactive & Immersive HQ GPU-particles and DJ-visuals pages (truncated), Apple developer HTML pages (JS; used the JSON endpoints instead). Search budget exhausted before: ITU-R BT.1359 thresholds, crowd-camera visual precedents, haze/strobe robustness of segmentation models.
