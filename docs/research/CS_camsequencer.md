# CS: CamSequencer / OpSequencer (Function Store) studied for a clean-room `CS_cam_sequencer` (28 Oct 2026)

Research only. No TouchDesigner was used, nothing was bought, no `.tox` was obtained or inspected, no login or paywall was
touched. Everything below comes from public pages, public YouTube videos (auto-captions + frame grabs) and our own repo.
Confidence tags: **[PAGE]** product / asset page text, **[VID]** seen or heard in a public video (timestamp given),
**[FRAME]** read from a video frame or the cover image, **[INFER]** our reasoning, **UNVERIFIED** = would need the product
itself (we will not get it). Build named for live claims: our target is TD 2025.31550 (the product's required build is **not
stated anywhere** public).

Local evidence (git-ignored): `media/research/camsequencer/` (captions, frames, `SOURCES.md`), `research_src/camseq/gumroad.html`.

## 1. Sources (all accessed 28 Oct 2026)

| # | Source | URL | Got |
|---|---|---|---|
| S1 | Gumroad product page "OpSequencer and CamSequencer component for TouchDesigner" (the URL as given and without `?layout=profile`; WebFetch only sees the `<title>`, the page is a JS app, so the public page data embedded in the served HTML was read with curl, no login) | https://functionstore.gumroad.com/l/camsequencer | description, parameter list, price, rating, cover, 2 videos |
| S2 | Gumroad seller profile (same method) | https://functionstore.gumroad.com/ | 5 products + prices |
| S3 | Derivative asset page "Easy Easing Between Camera Positions - CamSequencer" (function.store / Dan Molnar, posted 14 Feb 2022, 3,161 reads, 0 comments; tags camera, component, Interpolation, easing, curves, preset(s)) | https://derivative.ca/community-post/asset/easy-easing-between-camera-positions-camsequencer/65805 | same description, links, no file, no build |
| S4 | Derivative post "Tools you didn't know you needed" (CamSequencer/OpSequencer section) | https://derivative.ca/community-post/tools-you-didn%E2%80%99t-know-you-needed/72935 | "saves and blends camera presets using various easing curves, controlled by a slider; audioreactive"; OpSequencer "ideally a COMP with custom parameters", Spline Interpolation "fits a polynomial curve" |
| V1 | YouTube "Easy Easing Between Camera Positions in TouchDesigner - CamSequencer", Function Store, 14 Feb 2022, 5:33, 7,616 views | https://youtu.be/rdmt2F-oEtQ | captions + 720p frames |
| V2 | YouTube "CamSequencer update and OpSequencer release", Function Store, 19 Apr 2023, 4:19, 4,158 views, chapters Intro / Spline interpolation / Cam presets / Camera presets / OpSequencer | https://youtu.be/45XWxItESfg | captions + frames |
| V3 | YouTube "Custom Nvidia Flex setup + using OpSequencer preset system [Project Rundown]", Function Store, 23 Jan 2025, 26:46 (OpSequencer chapter 18:26) | https://youtu.be/K39_nhE0v0A | captions |
| V4 | YouTube "Audioreactive Particle Cloud (new)", elekktronaut (Bileam Tschepe), 10 Jul 2023, 16:24, 109k views; camSequencer chapter 7:00-9:58 | https://youtu.be/olhePB-r7I4 | captions + frames |
| V5 | YouTube "CamSequencer audioreactive with Raytk", PeriVJ, 19 Feb 2024, 0:32 | https://youtu.be/hDcvsGLX5cg | frames (music only, no speech) |
| V6 | YouTube "Camera Blending - Quick Tip 2", elekktronaut, 10 Apr 2022, 3:59 (built-in Camera Blend COMP; credits Function Store's video) | https://youtu.be/6Md4s5l07sY | captions |
| V7 | YouTube "Animating Camera Movement", elekktronaut, 2020, 25:02 (Animation COMP route) | https://youtu.be/qKkcYwiqT_g | chapters only used |
| F1 | Derivative forum "Smooth camera switch" (13-14 Jun 2024) | https://forum.derivative.ca/t/smooth-camera-switch/487041 | a buyer's verdict (section 4) |
| F2 | Derivative docs: Camera Blend COMP | https://derivative.ca/UserGuide/Camera_Blend_COMP | pars + modes |
| F3 | Derivative tutorial "Generative camera paths" | https://derivative.ca/community-post/tutorial/generative-camera-paths-touchdesigner-tutorial/66993 | DIY path route |
| F4 | Easing source the product credits | https://easings.net/ | the 30 curves |
| M1 | Unity Cinemachine 3.1 manual (blends, noise profiles, spline dolly) | https://docs.unity3d.com/Packages/com.unity.cinemachine@3.1/manual/ControllingAndCustomizingBlends.html , `.../CinemachineNoiseProfiles.html` , `.../CinemachineSplineDolly.html` | concepts |
| M2 | Unreal Engine docs: Camera Cut track, Camera Rig Rail, Camera Rig Crane | https://dev.epicgames.com/documentation/unreal-engine/cinematic-camera-cut-track-in-unreal-engine , https://docs.unrealengine.com/4.27/AnimatingObjects/Sequencer/Cameras/CameraRigRail | concepts |
| G1 | Maker's GitHub (repos listed via the public API: FNSTools MIT, TD-Launcher-Plus, TD_ParHoverMIDI_VSN1 ...). **CamSequencer is not in any public repo**; FNSTools README (TD 2025+, 80+ packages, 47 free / 24 Patreon-only) never names it | https://github.com/function-store | naming/style only |

Not reachable / skipped: Patreon posts (`patreon.com/posts/camsequencer-and-81712029`, `/80576530`, `/120635419`) return **403**,
not bypassed. Instagram (`@function.str`), X, Vimeo, Facebook: searched, **no CamSequencer post was findable without a login**,
so none is cited. Forum: one thread (F1) mentions it. The function.store site `functionstore.xyz` was not needed. A 2019 YouTube
video called "CamSequencer" (gjspneyjAU0) is a **Maya** tutorial, unrelated.

## 2. What the product is [PAGE][VID]

- Name: **"OpSequencer and CamSequencer component for TouchDesigner"** (Gumroad permalink `camsequencer`). Seller Function Store
  = Dan (Daniel) Molnar, Berlin. One `.tox` file ("summary: .tox file"). Also sold on Patreon (`patreon.com/function_store`).
- **Price: 2400 cents EUR = EUR 24** in the Gumroad page data (S1, fixed price, not pay-what-you-want; a search-engine snippet said
  "EUR 12+", presumably an older cached listing). Rating 5.0 from 9 reviews; seller 5.0 from 32 reviews, 5 products (S2):
  TDXMap Pro EUR 80, TDXMap Base EUR 40, OpSequencer+CamSequencer EUR 24, LayerSep EUR 22, ComplexFunction.store UV toolkit free.
- **Version and TD build requirement: not stated** on the Gumroad or Derivative pages. Original asset 14 Feb 2022 (S3), update +
  OpSequencer 19 Apr 2023 (V2), later "any to any" option (V3, Jan 2025). Included files: the single `.tox` (page lists none else);
  V1 says "there's even a readme" (inside the tox, 0:44).
- **CamSequencer** = "an extended version of the default Camera COMP" that "stores and recalls camera positions as presets, with an
  easing curve for the in-between values", so you get continuous animated camera movement "without the need of an Animation
  COMP". "Works best with a Look At object; it will sequence its transform parameters as well." Easing formulas from easings.net.
- **OpSequencer** (2023) = the same engine for **any one operator** ("not the full preset system, just a per-operator preset
  system", V2 0:20); CamSequencer now "under the hood is the OpSequencer" (V2 0:08). Custom easing lookup via a multi-sample CHOP
  input; alt-drag a Custom COMP onto OpSequencer adds all its custom pars; middle-click a par name in the header removes it [PAGE].
- **Parameters named on the page [PAGE]:** Init (clears the sequence, saves current position), Append, Replace, Insert (before the
  selected), Remove, **Ease Override** (On: the chosen curve is used between all presets; Off: the curve selected *when the preset
  was saved* eases **into** that preset), **Ease** (function), **Select** (a fader that switches between saved settings;
  "in-between numbers are the easing index"). Sequenced pars, camera **and** Look At: `tx ty tz rx ry rz sx sy sz px py pz`.
  Camera only: `projectionblend orthowidth fov focal aperture near far winx winy winsize winroll ipdshift`. (All of these exist on
  our 31550 `cameraCOMP`, checked in `ops/ops_COMP_2025.31550.json`.)
- **Screenshots / images:** the page has one cover (1920x1080, [FRAME], file `gumroad_cover.png`): left, a 5x6 grid of the **30
  easings.net curve thumbnails** (in/out/inOut x Sine, Quad, Cubic, Quart, Quint, Expo, Circ, Back, Elastic, Bounce), each a small
  white-to-blue/green curve on black with its name; right, a TD parameter dialog titled **Camera `camSequencer1`** with the page
  row Xform / Pre-Xform / View / Settings / Render / Extensions / Common and sub-tabs **Sequencer | Info**; rows: Append, Replace,
  Insert, Remove, Init (all Pulse buttons), Ease Override (Off), Ease (`InOutQuad` dropdown), Select (0, with slider), Length (1);
  bottom right, the component's square olive tile with a white lens/target icon and four corner brackets; big caption "EASY EASING
  BETWEEN CAMERA POSITIONS". No other screenshots on the page.

## 3. Videos, with a timestamped breakdown

Times are the video clock (YouTube captions, ~1-2 s granularity). "UI" = what the screen shows.

### V1 "Easy Easing Between Camera Positions in TouchDesigner - CamSequencer" (5:33, 14 Feb 2022)
Screen: full TD (network editor left, parameter dialog centre, Render viewer right) over a red/white cube, later a gold-and-red
instanced point-cube tunnel; presenter in a corner cam. Chapters: 2:14 "Change the Fov Angle", 2:43 "Replace a Selected Preset", 3:38
"Save the Easing Curve Tied to a Preset".
| Time | UI | Camera / feature |
|---|---|---|
| 0:00-0:40 | cube scene, dropdown of easings | "save camera settings in a preset list and interpolate between them with different easing curves"; four positions give "this very nice camera path"; there is a bounce curve; formulas from easings.net (browser shows the curve sheet) |
| 0:44-0:58 | - | readme inside; sold on Patreon, Gumroad also open |
| 1:03-1:36 | instanced geometry, palette sidebar | drag the **camSequencer from the user palette**; "a normal Camera COMP at heart": drag it onto the Render TOP, same parameters, **plus an extra Sequencer tab** |
| 1:50-2:07 | Select par expression turned off, viewer activated | animate-off while authoring; navigate the viewer to a first position, press **Init** (clears old presets) |
| 2:12-2:31 | viewer + Look At null | move elsewhere, **change FOV manually**, **move the Look At** (a Null connected to the camera); both are saved |
| 2:31-2:43 | | **Append** a second position; going between them uses the selected curve |
| 2:43-3:05 | | **Replace** the selected preset after re-posing |
| 3:05-3:25 | | **Insert** before a given preset; **Remove** a preset |
| 3:27-3:39 | | **Ease Override On**: one curve for all segments |
| 3:39-4:33 | Override Off | per-preset curves: go to preset 2, set `inOutCirc`, Replace; preset 3 with an out curve, Replace; **from preset 3 back to preset 1 an in/out bounce** (the wrap segment also has its own curve); re-enable the `absTime.seconds` expression on Select ([FRAME] shows an `absTime.seconds * 0.1`-style expression) to see a different easing per segment |
| 4:45-5:33 | | "hope this becomes your go-to default camera COMP"; other preset systems exist but this one is camera-specific and easy |

### V2 "CamSequencer update and OpSequencer release" (4:19, 19 Apr 2023)
Screen: TD with a Camera COMP `camSequencer1` (olive tile), an `OpSeq1` container, a bloom TOP over a field-of-grass video.
Parameter dialog now has pages **Seq | Presets | About** [FRAME 1:37]. Seq page rows (Camera: Append, Replace, Insert, Remove, Init,
**Override**, **Easing** `InOutSine`, **Spline Interpolation**, **Select**, **Length**, **Bind** (On)) [FRAME 0:38].
| Time | UI | Feature |
|---|---|---|
| 0:00-0:27 | | CamSequencer is now built on OpSequencer; "not the full preset system" |
| 0:27-1:29 | recorded positions on a cube, animated by an in/out sine on Select | **Spline Interpolation**: without it the camera visibly slows/changes at each recorded position "no matter which interpolation you select"; with it "very smooth and continuous and looping"; **drawback**: with some movements it "could behave unexpectedly", pick what looks best |
| 1:32-1:41 | **Presets** tab, **Open Cam Presets** / **Open Lookat Presets** pulses [FRAME 1:37] | opens a pop-up UI |
| 1:41-2:33 | pop-up table (`#`, `EASE`, one column per par) | edit any value, view, **reorder presets**, add new ones; **camera presets and look-at presets are separate tables and not linked** ("be careful when moving stuff, the preset will not move for the Look At") |
| 2:33-3:55 | `OpSeq1` container params (OP, Bind On, Reset) + same pop-up with `#`, `EASE` columns and a button row **Append / Replace / Insert / Remove / Init / BIND**, plus Override, Easing, Spline Interpolation, Select, Length [FRAME 2:55] | drag the bloom TOP onto the OP par, drag chosen pars into the header ("threshold" etc.), change values, Append, enable the Select expression, change easing and spline; works for any operator |
| 3:55-4:19 | | available on Patreon and Gumroad |

### V3 "Custom Nvidia Flex setup + OpSequencer preset system" (26:46, 23 Jan 2025), OpSequencer chapter 18:26-26:03
| Time | Feature |
|---|---|
| 19:13 | the system "works with a **CHOP input**" (other preset tools are timer-driven or MIDI/Python); use the Select slider |
| 19:53-20:23 | alt-drag a COMP onto the OP par adds all its custom pars; the initial preset is created automatically |
| 21:05-22:00 | change pars, **Append**, then **Select driven by `absTime.seconds`** morphs through the presets |
| 22:33-23:30 | "we spend most of the time between presets": a higher-order curve (**OutExpo**) lingers on the saved states; Override applies one curve to all |
| 23:47-24:25 | **Custom ease**: an S-curve CHOP as lookup gives a long hold then a sudden jump |
| 24:34-25:30 | **Unbind** to edit freely, then Append / insert-before-N / Replace, re-bind; with Bind the pars are owned by the sequencer |
| 25:32-25:59 | new **"any to any"** option: jump between any two presets instead of sequential order |
| 26:08 | the presets are stored in the project file |

### V4 elekktronaut, camSequencer chapter 7:00-9:58 (audio-reactive, with particlesGPU)
| Time | UI | Camera behaviour |
|---|---|---|
| 7:00-7:22 | `Cam` COMP node, camSequencer params | define camera spots by orbiting the viewer |
| 7:22-7:48 | | **"very important to have a null that defines the look-at point"**, put in Xform Look At: the camera "is more like a rotation" around it |
| 7:48-8:12 | | Append 3-4 spots; **spline interpolation** "makes it a lot smoother" |
| 8:14-8:50 | kick CHOP -> Count CHOP -> Null `cam` -> Select | kick advances Select: **hard cut** at each step |
| 8:50-9:05 | Lag CHOP, input lag only | **smooth transition** (lag in one direction) |
| 9:12-9:36 | Limit CHOP "zigzag" 0..3 | ping-pong across the 3 spots instead of jumping back |
| 9:41-10:30 | Math + Constant + Speed + Combine add | **constant slow rotation + kick as a push** |
Also in the rest of the video: kick scale, spectrum-driven scale (not camera).

### V5 PeriVJ "CamSequencer audioreactive with Raytk" (0:32, 19 Feb 2024)
No speech, music only. Eight frames at 4 s [FRAME]: a chrome head inside a rotating wireframe polyhedron, framing changes between
wide (object small), medium and an **extreme close-up of the face** with the background tone flipping between mid-grey and near
black; consistent with hard / fast framing changes on the beat (RayTK raymarched scene). Confidence low on mechanics.

### V6 / V7 (comparison only)
V6: the built-in **Camera Blend COMP** (inputs = cameras, Blend weights vs **Sequence** value, LFO on Sequence, then drag the
blend onto the Render TOP; fades translate / rotate / scale and fog, 1:26-3:35). V7: Animation COMP route (keyframed curves).

## 4. Public user feedback [F1]
A buyer (Jun 2024) wanted a camera switch from keyboard in any order: with CamSequencer the transition was "smoother but still
has that clunky effect"; a helper noted "it still **reads your presets in a sequence**", so jumping 1 to 4 sweeps through 2
and 3. The author later added **any-to-any** (V3). Lesson for us: Select is a **scalar index**; a jump needs its own blend, not
a sweep through the list.

## 5. Feature matrix

| Feature | Evidence | Conf. | Our build idea |
|---|---|---|---|
| Camera COMP that is the sequencer (same pars, drop on Render TOP) | S1/S3 text; V1 1:29 | high | Base COMP `CS_cam_sequencer` holding a Camera COMP `cam_out` (bound like `cam_rig_logic.apply_bind`); Render TOP Camera par points at `cam_out`. Reason: our rigs are position+target, not raw Euler |
| Store a shot from the current view (Init / Append) | S1; V1 2:01-2:31 | high | `Append` / `Replace` / `Insert` / `Remove` / `Init` pulses + `Capture` from any camera COMP / viewer camera (`Capsrc`) |
| Replace / Insert before selected / Remove | S1; V1 2:43-3:25 | high | same pulses on `Shot` (selected row) |
| Look At stored with the camera (separate table) | S1; V1 2:20; V2 1:41 | high | our shot row stores `target` (3 floats) in the same row: **never unlinked** (their stated pitfall, V2 2:17) |
| Sequenced pars: tx..sz, px..pz (+ look-at xform), projectionblend, orthowidth, fov, focal, aperture, near, far, win*, ipdshift | S1 | high | store pose (pos, target, roll) + `fov`; optional lens columns (`projblend`, `orthowidth`, `near`, `far`, `winx`, `winy`, `winroll`) interpolated when `Lens` toggle on |
| Select fader, fractional = easing index; Length | S1; V1; cover | high | `Select` float 0..N (wraps), `Shot` int, `Length` read-only; fraction = progress between shots |
| 30 easings (easings.net) | S1; cover thumbnails | high | menu of the 30 in/out/inOut curves + linear + smooth + smoother + `custom` (CHOP lookup); pure-python table (tested vs closed forms) |
| Ease Override on/off; curve saved per preset eases INTO it (incl. wrap segment) | S1; V1 3:27-4:33 | high | `Override` toggle; shot column `ease` |
| Spline interpolation (smooth, continuous, loopable; can overshoot) | V2 0:27-1:29; S4; V4 8:06 | high that it exists; **UNVERIFIED** algorithm (S4: "fits a polynomial curve") | centripetal Catmull-Rom through shot poses (closed when looping) with `Splinetension`; documented overshoot limited by centripetal + clamp. Not "polynomial fit" |
| Custom ease from a multi-sample CHOP | S1; V3 23:47 | high | `Customease` CHOP path, sampled by progress (one `lookup` per frame, ~free) |
| Any-to-any jump | V3 25:32; F1 | high | `Gotoshot` + `Anytoany` blend (fly A to B directly, `Trans` cut/ease/arc/spline); never sweeps through intermediates |
| Bind: sequencer drives the pars; Unbind to edit, Reset | V2 [FRAME]; V3 24:34 | high | `Active` toggle (off = camera free for hand/viewer editing, shots untouched) |
| Presets UI: pop-up table, reorder, edit values, add | V2 1:32-2:33 | high | a `shots` Table DAT shown in a viewer pane (also editable by MCP/Python): edit, reorder = row moves |
| OpSequencer: preset system for any op's pars | S1; V2; V3 | high | **Do not rebuild**: `ZC_control_surface` already binds any op's pars as knobs with Store / Recall / morph curves / randomise, and `TL_timeline` lanes animate any par. Our spec links to them (section 8) |
| alt-drag Custom COMP adds all custom pars; middle-click removes | S1 | high | ZC already has Bind selected / wildcards |
| Driving Select from audio (Count/Lag/Limit zigzag) | V4 8:14-9:36 | high | `Clock = AU beats` makes this built-in; `Trig*` pulses + `Lag` par; `Limit` = `Loopmode` pingpong |
| Constant rotation + kick push (sum of two drives) | V4 9:41 | high | `Orbitspeed` + `Beatkick` push on shake / dolly |
| Hard cut vs smooth blend | V4 8:50 | high | `Trans` column cut / ease / arc / spline |
| No beat quantisation, no shake, no look-at groups, no multi-camera, no timeline | absence in S1, S3, V1-V4 | medium (absence of mention) | our additions (sections 6-7) |
| Info / About pages, readme inside | V1 0:44; V2 [FRAME] | high | small `About` page text in the custom pars |
| `Bind` writes par values or expressions | - | UNVERIFIED | ours writes by one bound expression set (7 pars), see `cam_rig.md` |
| Whether Euler is interpolated raw (tx/rx/rz lerp, gimbal/wrap flips) | S1 lists raw pars | medium [INFER] | ours interpolates position/target/roll/fov and builds Euler at the end (round-trips every `rord`, tested in `cam_rig_logic`) |
| Locked / encrypted engine? | - | UNVERIFIED (their TDXMap engine is encrypted, see `AR_tdmap_midi.md`) | irrelevant for clean-room |

## 6. UI description (what the user of the original sees)

A Camera COMP in the palette-style olive tile. Params dialog: the stock Camera pages (Xform, Pre-Xform, View, Settings, Render,
Extensions, Common) **plus** a custom page **Seq** (2023: **Seq | Presets | About**; 2022: **Sequencer | Info**). Seq: a block of five
Pulse buttons (Append, Replace / Insert, Remove / Init), then Override (toggle) + Easing (dropdown), Spline Interpolation (toggle),
Select (slider, usually driven by an expression such as `absTime.seconds`-based or a CHOP) and Length (count of presets), and
Bind. Presets: two pulses open pop-up table editors for camera and look-at presets (rows `#`, `EASE`, a column per sequenced
par). OpSequencer adds an OP par (drop an operator), a pop-up with the same buttons plus **BIND**. Everything is par-driven; there
is no timeline strip, no gizmo, no thumbnail.

## 7. What we already have, and what is missing

Read: `builders/cam_rig_logic.py` (683 lines, 26 offline tests, live CR1-CR5 on b2 27 Oct), `docs/builds/cam_rig.md`, PX preset
`Crane director` (`builders/px_logic.py` ~L3122: `Cammode director`, `Camshots 'crane:8 orbit:8 dolly:4 path:8'`, `Camquant 4`,
`Camtrans cut`, with `velocity_streak` camera blur) and the PX Camera page (`Cammode` orbit / crane / dolly / path / follow /
director; `Camshots`, `Camdirmode` list / random, `Camquant`, `Camtrans` cut / ease / arc, `Camtdur`, `Camseed`, `Camroll`).

**Have (pure Python, tested, reusable as is):** `Pose` (pos, target, roll, fov horizontal), TD Euler for every `rord` with gimbal
fallback; rigs `orbit`, `crane` (heading / pitch / length), `dolly(a, b, u)`, `Path` (Catmull-Rom, arc-length table, look-ahead,
bank), `follow` (lag); `shake` (deterministic value noise, position + aim + roll, octaves); `blend(cut / ease / arc)`; 8 eases;
`Views` store (Table DAT `name px py pz tx ty tz roll fov`, `fly`); `Director` (shots with hold in beats, `list` / `random`,
`quant`, `min_hold` / `max_hold`, seeded, transition INTO a shot, beat clock, `cuts()`); `Memo` + `apply_bind` (7 Camera pars bound
to one pose per frame, 0.08 ms CPU measured); the audio side `AU_features` (`bpm`, `beat`, `beat_phase`, `beat_count`,
`beat_pulse`); the show side `TL_timeline` (lanes on any par, interp hold / linear / ease / bezier, Out `tl_beat tl_bar`),
`CQ_cuelist` (cue kinds `par` fades `op:par`, `zc_set`, `zc_recall`, `tl`), `ZC_control_surface` (any-par presets with morph);
zkit panel + `zk_essentials.json` Main tab / macros.

**Missing for a CamSequencer-class tool (and where it goes):**
1. A **standalone COMP** with its own params (decided "no CAM_rig COMP until a third consumer asks", `BUILD_PLAN_27OCT.md` row
   CAM_rig; PX and BL_splat_render are the first two; **this request is the third**).
2. **Authoring**: capture a shot from a live camera / viewer, Append / Replace / Insert / Remove / Init, reorder, per-shot ease,
   per-shot transition. (`Views` has store / remove only; no capture UI.)
3. **Select scrub** (fractional index over an ordered list, wrapping) and a **spline through stored poses** (the `Path` spline
   exists for points only, not poses with target / roll / fov).
4. **The full 30 easings** + custom CHOP lookup (we have 8).
5. **Any-to-any jump with its own blend** (director transitions only go into the next scheduled shot).
6. **Named shake profiles** (Cinemachine-style) and beat-linked shake; **target groups / framing** (fit a set of effectors, follow
   by name exists in PX only).
7. **Output contract**: a Camera COMP path + an Out CHOP of channels (today the pose is only bound to a camera's 7 pars).
8. **zkit panel + Main tab + presets** for the COMP, and a shot-list **generator** (coverage set from a target).
9. **Multi-camera**: nothing yet; the director already switches *poses* on one Camera COMP, which is the cheap way (one Render
   TOP); a second output camera is optional.

## 8. Comparable designs and how their concepts map

| Concept | TD today | Unity Cinemachine (M1) | Unreal Sequencer (M2) | Our spec |
|---|---|---|---|---|
| Shot = a camera with settings | Camera COMP; CamSequencer preset row | CinemachineCamera (priority) | Cine Camera Actor + Camera Cut track section | row in `shots` (pose + rig + hold + trans + ease + shake + tag) |
| Which shot is live, and how it blends | Camera Blend COMP (Blend weights or **Sequence**), CamSequencer Select | **Brain**: Default Blend + custom From/To blends matched by camera name; style cut / ease-in-out / linear / custom curve; timeline overlap overrides | Camera Cut track; blends by overlapping sections | per-shot `trans` + `tdur` (INTO the shot) and a `Defaultblend`; a small `blends` override table (from tag, to tag, kind, beats) |
| Dolly track | Camera `Path SOP` (Position, Orient along Path, Auto-Bank), generative paths (F3) | **Spline Dolly** (camera position along spline, Automatic Dolly fixed speed or nearest to target; rotation Default / Path / Follow Target) | **Camera Rig Rail** (Current Position on Rail 0..1) | `rig=path` shot (Catmull-Rom arc-length, exists) + `Pathpos` 0..1 |
| Crane / boom | none built in (our `crane`) | Orbital Follow | **Camera Rig Crane** (Crane Pitch, Yaw, Arm Length keyed) | `rig=crane` (exists: heading / pitch / length) |
| Look-at / aim | Camera Look At par (Null) | Rotation Composer / Hard Look At, Follow / Look At targets, **Target Group** | Look-at tracking, attach | `Targetmode`: stored per shot / fixed op / effector name / group average + radius for `Frame` |
| Noise / handheld | none | **Basic Multi Channel Perlin** + noise profile asset (per-axis layers: Hz, amplitude; rotation before position; wider lens = bigger amplitude; mix ~0.1-0.5 / 0.8-1.5 / 3-4 Hz) | camera shake assets | `Shakeprofile` menu (breath / handheld / walk / vehicle / quake / custom table) on top of `cam_rig_logic.shake` |
| Sequencing in time | Animation COMP, TL_timeline lanes | Timeline + Cinemachine track | **Sequencer** | internal playmodes + a TL lane on `Select` / `Shot` |
| Free-form variety | presets (ZC, TDMorph by Darien Brito, free, F1) | state-driven camera / clear shot | - | `Random` mode (no repeat, seeded, quantised) |

Also in TD itself: the built-in **Camera Blend COMP** (F2: modes Blend (first 4 inputs, Weight / Mask), Sequence (one input drives
the child position), Constrain; has Short Rotation quaternion blend for two inputs) and the Camera COMP's `lookat`, `pathsop`,
`bank`. We do not use Camera Blend: it blends **between existing Camera COMPs** (cost: one COMP per shot, no stored table), and
our poses are computed in Python at ~0.1 ms.

## 9. Open questions

1. Required TD build, `.tox` version number, whether the engine is locked: not public (we do not need them).
2. Exact spline algorithm and whether it closes the loop (V2 says "looping" with an in/out sine drive); whether easing is applied
   before or after the spline.
3. Whether the original interpolates Euler pars raw (gimbal / 360 wrap behaviour when a rotation crosses 180); not observable
   from the videos.
4. How Bind applies values (par write vs expression) and what happens to hand edits.
5. Price: page data says EUR 24; a search snippet said EUR 12+; take the page data.
6. Instagram / X / Vimeo demos: none findable without login (not pursued).
7. For us: what does the user want first, **authoring by capture in the TD viewer** or **a generated coverage list**? Proposal
   below ships both (small).
8. Which Render TOP / camera consumers must be preferred in the first test (BL_splat_render external camera and PX are the
   known two; PV_previz_stage and the PX Camera page can keep their built-in rigs).

## 10. Recommended clean-room spec: `CS_cam_sequencer`

Name: **`CS_cam_sequencer`** (prefix `CS_` is free in `docs/research` and the repo; check `lab` for clashes before the build;
the product's own names `camSequencer`, `OpSequencer` are not reused). Home `/project1/lab/CS_cam_sequencer`. Builder
`builders/cam_seq.py` (idempotent, T-70 safe, same shape as `zctl.py`), pure logic `builders/cam_seq_logic.py` (new, imports
nothing from TD; imports `cam_rig_logic` copied into the COMP as `cam_rig`), tests `test/test_cam_seq.py`, doc `docs/builds/cam_seq.md`.
**Lifts, not rewrites** `cam_rig_logic.py`; PX and BL_splat_render keep binding to the same module (no change to them).

### 10.1 Network (left to right, staged)
`Controls` (zkit panel + window) | `Data` (`shots` Table DAT, `blends` Table DAT, `cs_cfg`) | `Clock` (`clock` chooser:
internal / AU / TL / CHOP / manual -> `beats`, one Script CHOP or expression) | `Solve` (`cs_logic` + `cam_rig` Text DATs,
`solve` Script CHOP: one pose per frame via `Memo`, shake, framing) | `Output` (`cam_out` Camera COMP bound to the pose, `out_chans`
Out CHOP) | optional `Preview` (see 10.9). No GLSL, no TOPs in v1 (0 GPU).

### 10.2 Shots: how they are stored (Table DAT `shots`, survives in the .toe)
Columns = `Views.to_rows` prefix + shot fields, so a PX `cam_views` table can be pasted in:
`name px py pz tx ty tz roll fov | rig hold trans tdur ease shake target tag | a1..a4 (rig params as JSON in one `params` cell)`.
- `rig`: `view` (default: the stored pose) | `orbit` | `crane` | `dolly` | `path` | `follow` (as `cam_rig_logic.shot`).
- `hold` in beats (0 = use `Defaulthold`), `trans` = cut | ease | arc | spline (transition INTO this shot), `tdur` beats, `ease` =
  one of the 30 + linear | smooth | smoother | custom, `shake` = profile name or blank, `target` = blank | op name | effector name |
  group, `tag` = free word used by `blends` and by cues (`Gototag`).
- Optional lens columns `projblend orthowidth near far winx winy winroll` (only when `Lens` on).
- `blends` table (Cinemachine-style custom blends): `from_tag to_tag trans tdur ease` (first match wins, else the shot's own).
- Stored pose is **position + target + roll + horizontal fov** (same as `cam_rig_logic.Pose`), never raw Euler.

### 10.3 Pages and pars (custom pars, `Capital` + lowercase names, Float/Int/Menu/Toggle/Pulse)
- **Main** (zkit Main tab, 12 pars): `Active` (T), `Playmode` (manual | sequence | beat | random), `Shot` (Int, selected row),
  `Select` (Float 0..N, scrub, wraps), `Clockmode` (internal | au | tl | chop | manual), `Bpm` (Float, internal / fallback),
  `Quant` (beats, cut lands on a multiple), `Ease` (menu, 33 entries), `Trans` (cut | ease | arc | spline default for new
  shots), `Shakeprofile` (menu), `Shakeamount` (0..1), `Fov` (offset, deg).
- **Seq** (shot editing): pulses `Append`, `Replace`, `Insert`, `Remove`, `Init`, `Duplicate`, `Moveup`, `Movedown`, `Capture`
  (store the camera named in `Capsrc` = viewer / any Camera COMP path / `cam_out` itself), `Fromviewer`, `Gen coverage`
  (`Genshots`: wide / medium / close / low / high / top-down around `Target` with `Genradius`; vertical-aware), `Showtable`;
  `Length` (read-only), `Override` (T), `Defaulthold`, `Splineinterp` (T), `Splinetension`, `Loopmode` (loop | pingpong | once),
  `Anytoany` (T), `Gotoshot` (Int) + `Gotoblend` (cut | ease | arc), `Gototag` (Str).
- **Time**: `Playing`, `Rate` (-4..4), `Seek` (beats), `Beatsperbar`, `Tdur` (default transition beats), `Quant`, `Bpmsource` (beats | essentia), `Lag` (s, smoothing
  of Select when driven by a CHOP), `Customease` (CHOP path), `Easeoverride` (menu).
- **Look**: `Targetmode` (stored | op | effector | group), `Targetop`, `Targetnames`, `Lookdamp` (s), `Frame` (T: pull back so the
  group radius fits in the narrower frame angle; portrait uses the horizontal fov), `Framepad`, `Roll`.
- **Shake**: `Shakeprofile`, `Shakeamount`, `Shakepos` (units), `Shakerot` (deg), `Shakefreq`, `Shakeoct`, `Shakeseed`, `Shakebeat`
  (extra kick on beats, uses `AU_features.beat_pulse`), `Shakeperlens` (T: scale by fov).
- **Output**: `Resx` 1080, `Resy` 1920 (aspect for `viewproj`, Frame and the optional preview; **vertical default**), `Fovmode`
  (horizontal, the TD default), `Near`, `Far`, `Projection`, `Outcam` (read-only path of `cam_out`), `Outchop` channels (10.7).
- **Zkit** page from `zkit.build_controls` (+ macro knobs `Zkm1..`).
- **About**: one-line help, version, links to this doc.

### 10.4 Timeline / sequence playback
- `Playmode manual`: output = pose at `Select` (scrub / CHOP / expression / TL lane). Integer part = shot, fraction = progress; the
  segment from shot i to i+1 uses shot **i+1's** `trans` / `ease` (Override off) or the global `Ease` (Override on), as the original.
  `Loopmode loop` makes the segment N-1 -> 0 real (the original's bounce back to preset 1).
- `Playmode sequence`: auto-advance by each shot's `hold` (beats) on the beat clock; transition INTO the next starts at the cut
  (existing `Director` semantics: old shot keeps moving while the blend runs).
- `Playmode beat`: cut on the next multiple of `Quant` beats after a trigger (`Trignext`, CHOP edge) or every `Defaulthold`.
- `Playmode random`: seeded, never repeats (the existing `Director` random mode), `min_hold` / `max_hold`.
- **Timeline** = `TL_timeline` lane targeting `CS_cam_sequencer:Select` (ease / hold / bezier keys, markers) or `Gotoshot`; no
  second timeline UI is built (no bloat). `CQ_cuelist` row kind `par` (`CS:Gototag` with a fade, or `CS:Select`) and `zc_recall`
  for knob presets already work with any par.

### 10.5 Easing, blends, spline
- Easings: the 30 closed forms from F4 + linear + smooth (smoothstep) + smoother (existing `cam_rig_logic.ease`, extended; keep
  the 8 existing names working), `custom` = `Customease` CHOP sampled at progress (0..1, linear interp of the samples).
- Transition kinds: **cut** (instant), **ease** (straight line pos / target, eased), **arc** (existing `blend` arc: swing around the
  target, keeps framing), **spline** (centripetal Catmull-Rom over poses i-1..i+2, evaluated at the eased progress; closed when
  looping; overshoot guard = clamp distance to target to the min / max of the neighbours' by `Splinetension`; documented limit).
- **Any-to-any**: `Gotoshot` / `Gototag` starts a blend from the **current output pose** to the target shot (default `arc`, 1 beat)
  and then resumes the mode; never sweeps intermediates (fixes the forum complaint F1).
- Roll and fov interpolate linearly (fov in tan-space optional: `Fovtan`), lens columns linearly.

### 10.6 Shake and look-at
- Profiles as small tables of layers (Hz, amplitude) per rotation / position axis in the Cinemachine way (rotation first,
  position second; wide lens = bigger amplitude, `Shakeperlens`): `breath` (0.15-0.4 Hz, tiny), `handheld` (0.5, 1.2, 3.5 Hz),
  `walk` (1.8 Hz bob + sway), `vehicle` (6-12 Hz low amp + 0.4 Hz roll), `quake` (decaying bursts on `Shakebeat`), `custom`
  (a `shake_profiles` table). Computed by `cam_rig_logic.shake` per layer, deterministic by seed; applied after the blend, so
  noise never feeds the next shot.
- Targets: stored per shot (default), or an op / an effector by name (`/project1/effectors`, as PX `Camfollow`), or a group:
  centroid + bounding radius of the named effectors; `Lookdamp` smooths the target; `Frame` solves distance from the radius and
  the **narrower** frame angle (portrait: horizontal fov).

### 10.7 Triggers, clock, BPM
- Clock (`Clockmode`): `internal` = `absTime.seconds * Bpm / 60`; `au` = `AU_features` `beat_count + beat_phase` (live = 1; else
  falls back to internal; **exact channel use to be probed live**, UNVERIFIED); `tl` = `TL_timeline` `tl_beat`; `chop` = any In
  CHOP channel `beats`; `manual` = `Seek`. Read inside the expression (time dependency, T-113), as `cam_rig.md` does.
- Triggers: pulses `Trignext`, `Trigprev`, `Trigrandom`, `Trigcut` (cut to current `Shot` now); In CHOP channels `shot`, `select`,
  `next`, `prev`, `random`, `kick` (rising edge, with `Quant` landing on the grid); `jazib_midi` / ZC can write the same pars
  (no device code inside, like `zctl`); `CQ_cuelist` and `TL_timeline` drive pars as above. OSC: a TD OSC In CHOP feeds the
  In CHOP (no sockets in the COMP).
- Out CHOP `cs_out` (one sample): `cs_tx cs_ty cs_tz cs_rx cs_ry cs_rz cs_fov cs_roll cs_shot cs_select cs_progress cs_blend
  cs_cut` (1 on the frame a cut / blend starts) `cs_beats cs_bar cs_shake` `cs_dist` (camera-target distance).

### 10.8 Outputs and Render TOP hookup
- **`cam_out`** = a Camera COMP whose `tx ty tz rx ry rz fov` (+ `near far`, `lookat` unused, `projection` default perspective)
  are bound by `apply_bind` (one pose per frame, 7 pars). Any Render TOP, `BL_splat_render` (`Cammode external`), PX or a Camera
  Blend COMP input takes `/project1/lab/CS_cam_sequencer/cam_out` as its Camera. Output res defaults 1080 x 1920 for aspect.
- Multi-camera switching: for one scene, the director switches **poses** on this one camera (cheapest, no Camera Blend COMP).
  Optional `Outcams` (1..4): extra `cam_out2..` that follow another `Shot` / offset for split views; v2, only if asked.

### 10.9 zkit panel: Main tab essentials and macros (to add to `builders/zk_essentials.json`, validated by `test_zk_essentials.py`)
- `main` (8-16 names): `Active Playmode Shot Select Clockmode Bpm Quant Ease Trans Shakeprofile Shakeamount Fov`.
- Macros (2-4, each 2-5 drives, none driving a menu / toggle / pulse): `Zkm1` **Shake** (`Shakepos` 0 -> 0.03, `Shakerot` 0 -> 1.5,
  `Shakefreq` 0.3 -> 3.0); `Zkm2` **Pace** (`Defaulthold` 16 -> 2, `Tdur` default 4 -> 0.5); `Zkm3` **Smooth** (`Lag` 0 -> 1.5,
  `Splinetension` 0 -> 1, `Lookdamp` 0 -> 1); `Zkm4` **Lens** (`Fov` offset -15 -> +15, `Framepad` 0 -> 0.4).
- Optional (phase 2, not v1): a small top-down map TOP (shots as dots, path line, current camera) drawn by one single-pass GLSL
  at 270 x 480 for authoring; off by default, so 0 ms in the show.
- Panel: the standard `zkit.build_controls` (night theme, presets with hand morph, randomise, properties).

### 10.10 Presets (factory, as zkit presets + shot sets)
Shot sets (rows in `shots`, stored as JSON in a `shot_sets` table; recall = replace `shots`): **Four corners** (orbit view, 4 views
around a target), **Crane reveal** (low crane up + pull back, 2 shots), **Dolly + push** (rail a -> b then slow push-in),
**Doc handheld** (3 views + `handheld`), **Beat cuts** (6 views, `Quant 1`, cut), **Vertical LED arc** (slow `arc` between 4
views at vertical aspect, `breath`), **Kick push** (orbit + `Shakebeat`), plus the existing PX **Crane director** shot string
imported as a set. Knob presets: Calm / Standard / Aggressive (Zkm1-4 positions).

### 10.11 Budget, tests, build plan
- **Cost:** the solve is the `Memo` path measured at 0.08 ms CPU / 7 bound pars (`cam_rig.md` CR5); add the blend + shake
  ~0.05 ms, table reads only on change. No GPU. Target < 0.3 ms, project stays 60 fps; `allowCooking` off when `Active` off.
  `td_perf` + fps in the build report.
- **Offline tests** (`test/test_cam_seq.py`, pure): 30 easings vs closed forms (endpoints, monotone for non-elastic / back /
  bounce), Select maths (wrap, fraction, N = 1, N = 0), Append / Replace / Insert / Remove / reorder row semantics, per-shot
  ease INTO, override, spline passes through every key (error < 1e-9), centripetal no overshoot beyond a bound on a sharp
  corner, any-to-any starts at the current pose and ends at the target, quantised cuts land on multiples of `Quant`, group
  framing radius, vertical aspect framing, shake deterministic + zero at 0, JSON round-trip of `shots`.
- **Live checks (TD 2025.31550, one disposable COMP, the CR1 / CR2 harness reused):** CS1 pose = `pose_matrix` for 20 random shots
  x 6 `rord`; CS2 Render TOP 1080 x 1920 through `cam_out`: the target at the image centre +-1 px; CS3 Select 0..N sweep matches
  the logic within 1e-5; CS4 beat clock = AU 128 bpm test track, cuts only on bars; CS5 TL lane on `Select` and a CQ `par` cue both
  move the camera in the same frame; CS6 any-to-any with no intermediate shot visible (3 captures); CS7 Active off leaves the
  Camera free; CS8 cost.
- **Order and time (estimate ~5-6 h, lift not rewrite):** logic + tests 2 h (eases, select, spline, any-to-any, groups, profiles),
  builder + Seq / Main pages + table 1.5 h, zkit + essentials + presets 1 h, live checks + doc 1.5 h; one agent, one TD (b3-b5),
  main last. Gates: no installs, no Arena / REST / Syphon calls involved.

### 10.12 Clean-room statement
Used from the product: only its public description, parameter **names** and behaviour shown in public videos (to name our
equivalents and to match user expectations). Not used: any file, code, asset or screenshot of the product in the build; the
easing curves are the open easings.net formulas; spline, blends, shake and framing are standard maths from Cinemachine / Unreal
documentation and our own `cam_rig_logic`. Our par names differ (`Select`/`Length`/`Append` are generic English words and
common to any list; shot, blend and shake pars are ours).
