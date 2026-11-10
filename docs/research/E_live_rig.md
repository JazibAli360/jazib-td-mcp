# E - the live rig: TD -> Resolume Arena at the wall, controls in TD (research, 16 Oct 2026)

Agent E for the lead (Sonnet). Research only. User decision (16 Oct): TD runs live for PRISMFEST'26 on Sat 24 Oct, feeds
Arena via Syphon or NDI, the show controls stay in TD. Added by the lead during the run: **same Mac vs two machines is not
decided** (compare, recommend one), and controls are **an on-screen TD panel plus hand MIDI** (Akai MPK Mini MK3 + Akai
MIDImix). Nothing was started or opened: no Syphon/NDI out was created, no MIDI device opened, Arena not touched, TD project
not saved, `/jazib_mcp` untouched, all probe ops deleted (`/project1/_research_probe` gone).
Notation: **probed** = ran live in TD 2025.31550 (`TouchDesigner 2.app`, Rosetta, M1 Max, macOS 27.0); **doc** = URL cited;
**file** = read from disk; **unverified** = memory, forum anecdote or extrapolation. Paths are relative to the bundle root.

## Short answer
1. **TD can render at wall size in real time, within a budget.** One M1 Max, one TD, no output window, probed: a light GLSL
   look holds 60 fps at 3744x1440, 7488x2880 and 9984x3840; a heavy synthetic look (96 noise lookups per pixel) runs
   **59 fps at 3744x1440, 24.6 fps at 7488x2880, 13.6 fps at 9984x3840**. Cost is linear in pixels (about 1.9 ms per Mpx for
   that look, GPU-bound). A 6-op feedback loop at 7488x2880 holds 60 fps (8-bit) and 58 (16-bit float). A POP particle
   render at 7488x2880 holds 60 fps up to 2 M sprites of 24 px, falls to 38.6 fps at 4 M and 11.5 fps at 10 M. 8-bit vs
   16-bit made no measurable difference except in the feedback loop (2 fps). Table in section 1.
2. **Syphon is the simplest path on one Mac** (zero network, zero compression, 8-bit RGBA, same GPU); it has **never been
   run between TD (Rosetta) and Arena here**. NDI is the path for two machines (full-bandwidth about 0.3 to 0.7 Gbps at 30 fps
   for 7488x2880, my extrapolation; 10 GbE for comfort).
3. **Recommendation (section 4): one Mac, Syphon, full 7488x2880 atlas at 30 fps cook rate, with half-resolution
   (3744x1440, scaled up in Arena) as the fallback**; two machines over NDI only if a shared-GPU soak test with Arena
   playing the 7488x2880 DXV3 base fails. Reason that matters most: the MOU backup system must also carry the live layer,
   so a two-machine primary needs a four-machine rig (or a backup without the TD layer).
4. **Controls (section 5):** a TD panel (Slider/Button COMPs bound to custom parameters) plus MIDImix (8 faders = slot
   levels, master fader = output dimmer, knobs = per-slot params, buttons = enable/state select) and MPK Mini MK3 (pads =
   flash-limited hits and state jumps, knobs = fine params of the selected slot). Exact default CC/note numbers are only
   partly sourced; the rest must be learned once (opens the devices, needs a go-ahead).
5. **The one fail-safe fact nobody documents is what Arena shows when a Syphon/NDI source disappears** (last frame or black).
   It is unverified and decides the whole design of layer 6; test it first on Arena (section 7, step 5).
6. **TD 2 crashed during this research** (null dereference in the UI thread, section "Bugs hit"); 7 crash reports exist
   for 11 to 16 Oct. A live rig needs a watchdog and an independent Arena-side kill for the FX layer.

---

## 1. TD real-time cost at the wall size

### Method (probed, TD 2025.31550, M1 Max 32-core GPU, 64 GB, macOS 27.0)
- Network inside `/project1/_research_probe` (deleted at the end): GLSL TOP generator (custom 3 variants of one fBm
  "warped noise" shader, `#define REP n` repeats the pattern; REP1 = 12 value-noise lookups per pixel, REP4 = 48, REP8 = 96),
  a feedback loop, and a POP particle render. The shader is synthetic, **not a show look**: use the table as a cost scale.
- A frame pump (Execute DAT `onFrameStart`) force-cooks the final Null/Render TOP every frame and appends the
  `time.perf_counter()` delta between frame starts. Per test: warm-up 45 to 150 frames, then about 300 frames measured
  (5 s of wall clock, so ≥ 60 normal frames, T-05). **fps = frames TD actually cooked per wall second** (Null TOP
  `totalCooks` delta / wall seconds); median/p95/max frame interval reported. No output window, no Syphon/NDI.
- `td_perf` is not usable to separate CPU from GPU here: it reports `cookTime == cpuCookTime` and `gpuCookTime` = 0 on
  this Metal/Vulkan path (probed, every op). The GPU-bound evidence is below.
- **`absTime.frame` is wall-clock paced and must not be used as an fps readout:** during a 19 fps run it still advanced
  at 60 per second (186 abs frames while 73 frames were cooked). Count cooks instead (see Bugs hit).
- A second readout, `sync_ms` = time for a forced cook + `numpyArray()` of an 8x8 crop of the output, shows GPU backlog:
  3 to 10 ms when the GPU keeps up, 118 to 218 ms when it is saturated (the queue holds about 3 frames).
- Conditions: one TD instance (the stray blank second TD, pid 57140, was closed by the lead before the figures below),
  foreground vs background: one frontmost test (16.7 fps, REP8 7488x2880) ran during contamination, so it is inconclusive; light loads held 60 fps in the background. **The machine is shared:** idle GPU
  "Device Utilization" from other apps was 21 to 29 % (`ioreg -c IOAccelerator`, other agents' browsers, viewers) and ranged
  to 84 % mean / 99 % max while my tests ran. Earlier runs overlapped other agents' TD work (a Script TOP cooking at about
  3 s, then the lead's `cb_*` test) and read 19 to 31 fps for what is 24.6 or 59 fps clean; those were discarded. The
  figures below were taken after a clean baseline (64x64 constant: 60.02 fps, p95 19.4 ms, max 20.4 ms). The lead's `cb_*`
  nodes were present but idle. Treat the numbers as ±5 %, and as optimistic for a show machine that also runs Arena.

### Results (fps = cooked frames per second; "ms" = median frame interval; 60 = capped by the 60 Hz cook rate)
GLSL generator, 8-bit (rgba8fixed) unless stated (REP1 rows are single runs from the first pass, before the clean-baseline protocol; they sit at the 60 Hz cap, so read them as lower bounds):

| look | size | cook rate | fps | ms | note |
|---|---|---|---|---|---|
| REP1 (12 lookups/px) | 3744x1440 | 60 | **60.0** | 16.7 | max 18.5 ms |
| REP1 | 7488x2880 | 60 | **60.0** | 16.7 | max 16.8 ms, sync 6.5 ms |
| REP1 | 9984x3840 | 60 | **60.0** | 16.7 | max 17.0 ms, sync 9.7 ms |
| REP4 (48/px) | 7488x2880 | 60 | **47.3** | 21.0 | 16-bit float: 46.2 fps, 21.2 ms |
| REP4 | 7488x2880 | 30 | **30.0** | 33.6 | holds 30 with about no headroom |
| REP8 (96/px) | 3744x1440 | 60 | **59.0** | 17.0 | |
| REP8 | 7488x2880 | 60 | **24.4 / 24.7** (2 runs) | 40.5 | same at 30 Hz: 24.7 |
| REP8 | 9984x3840 | 60 | **14.2 / 13.1** (2 runs) | 70 to 77 | |

Feedback loop at 7488x2880 (Feedback -> Transform -> Level -> Composite(+moving Circle) -> Null; 6 wall-size TOPs):
**8-bit 60.0 fps** (max 17.5 ms), **16-bit float 57.8 fps** (median 16.7 ms, one 213 ms hitch in 300 frames). Trails verified
by pixel readout (max 0.06, mean 0.013). `sync_ms` 31 to 38 ms means the GPU is close to the 16.7 ms budget.

POP particle render at 7488x2880 (Point Generator POP -> Particle POP -> Select POP in a Geometry COMP with Point Sprite
MAT -> Camera -> Render TOP):

| particles (live) | sprite size | format | fps | ms |
|---|---|---|---|---|
| 300 k | 3 px | 8-bit | 60.0 | 16.7 |
| 2 M | 6 px | 8-bit | 60.0 | 16.7 |
| 2 M | 24 px | 8-bit / 16-bit float | 60.0 / 60.0 | 16.7 |
| 4 M | 24 px | 8-bit | **38.6** | 26.1 |
| 10 M | 40 px | 8-bit / 16-bit float | **11.5 / 11.5** | 85 to 87 |

### What the numbers say
- **GPU-bound, linear in pixels.** REP8: 17 ms at 5.4 Mpx, 40.5 ms at 21.6 Mpx, 70 to 77 ms at 38.3 Mpx = about 1.9 ms per Mpx
  once above the 16.7 ms cap, and about 0.24 ms per Mpx per REP unit. Rosetta (x86_64 TD) showed no CPU limit: the GPU work goes through
  Vulkan/MoltenVK to Metal; Python-heavy ops are the part Rosetta slows (td-port: Script CHOP about 2x slower, A section 2).
  I did not test a CPU-heavy network (Script TOP, many DATs), so "no CPU limit" holds only for GPU generators.
- **Budget rule for the wall:** at 7488x2880 a network has **about 16 ms (60 Hz) or 30 ms (30 Hz) of GPU** for everything; at
  3744x1440 it has the same time for 4x the work. PF26 runs 30 fps (STAGE.md), so cook rate 30 gives 2x headroom for the
  60 Hz-capable looks, and shared GPU with Arena eats into it.
- 8-bit vs 16-bit: no difference for the generator or particles (compute/fill-bound); 16-bit only cost 2 fps in the feedback loop.
  Syphon is 8-bit RGBA anyway (doc), so the Syphon feed should be 8-bit; keep 16-bit inside feedback if banding shows.
- **GPU memory** (probed `gpuMemory`): 86.3 MB per 8-bit and 172.5 MB per 16-bit-float wall-size TOP; the feedback net
  (6 TOPs, 16-bit) held about 1.0 GB, **the Render TOP alone 784.7 MB** at 7488x2880 8-bit (multisample/depth buffers).
  A network of a dozen wall-size TOPs plus a render is 2 to 3 GB; fine on 64 GB unified memory, but Arena shares it.
- **Not measured** (needs go-ahead or hardware): Syphon/NDI out cost, a presenting window (Window COMP / perform mode),
  Arena running at the same time, thermal behaviour over time, real show looks (this shader is synthetic), 9984x3840 for
  feedback/particles, CPU-heavy networks, MIDI/panel overhead. Per-op `td_perf` GPU times are not available on this build.

## 2. Syphon (Syphon Spout Out TOP -> Arena Syphon source)
- **TD side (doc, [Syphon Spout Out TOP](https://docs.derivative.ca/Syphon_Spout_Out_TOP), rev. 7 Sep 2023):** pars `active`,
  `sendername` plus the common TOP pars (Output Resolution incl. Custom, Pixel Format). Input 0 is the texture sent.
  "Syphon is limited to 8-bit RGBA." Same computer only (shared memory); for networks use Touch Out/In or NDI. **Max size: not
  stated.** Alpha handling when sending: not described (premultiplied vs straight unverified; matters for Arena's blend).
  Class `syphonspoutoutTOP` exists in 2025.31550 (probed `dir(td)`); not created.
- **TD ships Syphon.framework "5"** (file: `TouchDesigner 2.app/Contents/Frameworks/Syphon.framework`, headers
  `SyphonServer.h`, `SyphonOpenGLServer.h`, no Metal-server header listed). How TD publishes a Vulkan/Metal texture through
  it is not documented; the 2021 forum thread "Syphonspout not working on Mac?" (derivative forum, Monterey, staff: "not
  functional in the current experimental release") is old. Unverified on 2025.31550 + macOS 27; must be tested.
- **Max texture:** TD clamps textures at 16384 (probed, A section 3) and Metal's limit on Apple GPUs is 16384 (forum/Zed commit
  citation; not a Syphon statement). No Syphon/IOSurface size limit found. 7488x2880 and 9984x3840 are inside; **unverified end to
  end**. Frame size: 86.3 MB at 7488x2880 8-bit; at 30 fps that is 2.6 GB/s of IOSurface writes by TD and reads by Arena
  (5.2 GB/s at 60 fps), arithmetic, small against unified-memory bandwidth (Apple spec, unverified).
- **Arena side (doc, [Syphon & Spout](https://resolume.com/article/30), v7.22 tab):** "Syphon and Spout input are always
  enabled"; senders appear in the **Sources** tab and are dragged into a deck like any live input; Arena also publishes Syphon
  ("Arena" / "Composition", or "Screen n" from Advanced Output). The page names no resolution limit and no GPU requirement.
  A Resolume forum answer (Arena 5 era) asked whether both apps use the same GPU (they cannot share textures otherwise):
  one M1 Max has one GPU, so not an issue here (unverified).
- **Apple Silicon / Rosetta:** Arena has been a universal build since 7.11
  ([blog](https://www.resolume.com/blog/21445/resolume-7-11-apple-silicon-compatible-amp-delay-effects)); the `Arena` binary on
  disk contains both arm64 and x86_64 slices (file: `lipo`/`file`). TD 2 is x86_64 (Rosetta, probed `sysctl.proc_translated`
  = 1, A section 2). Syphon passes IOSurfaces by Mach/XPC messaging, which has no architecture dependency in principle; I found
  **no report either way** for a Rosetta server + native client. Unverified. A Resolume forum poster on an M1 Max reported VDMX Syphon sources appearing in Arena's
  source list (web-search summary, thread not fetched); not TD-specific.
- **Latency:** no measurement. Vendor text only: "almost no latency" between Syphon apps on one GPU
  ([ArKaos](https://pro.arkaos.com/node/99), marketing). Expect 1 to 2 frames from TD's cook plus Arena's compose (unverified).
- **Known issues:** itch.io comments claim Syphon "no longer works on macOS 15.1.1" for some apps (anecdotal, not TD/Arena).
  The PF26 viewer bridge reads Syphon rows bottom-up (L-54, `production/LEARNINGS.md`); that is the viewer's reader, so
  **Arena's orientation of a TD Syphon source is unverified** (test with a pattern that has a top).
- **Memory with both apps:** Arena's composition (7488x2880), decoded DXV clip textures and TD's 2 to 3 GB (section 1) all sit in
  the same 64 GB pool. Nothing measured for Arena (the 7488x2880 DXV3 playback test in PIPELINE section 8 is still pending).

## 3. NDI (NDI Out TOP -> Arena NDI source)
- **Versions (file):** TD 2 `Contents/Frameworks/libndi.dylib` = **NDI SDK 6.2.0.3** (build string "Jun 2 2025"); Arena's
  `/Applications/Resolume Arena/libndi.dylib` = **NDI SDK 6.1.1** ("Dec 20 2024"); both universal (arm64 + x86_64). Same major
  version; cross-version interop not tested (NDI 6.x is documented as compatible with earlier receivers, unverified).
- **TD side (doc, [NDI Out TOP](https://docs.derivative.ca/NDI_Out_TOP), rev. 28 Oct 2025):** `active`, `name`, `failovername`
  ("receivers switch to if this one fails", format `MACHINENAME (SourceName)`), `fps`, **`lowperformancebehavior` (Stall Main
  Thread or Skip Frames)**, `outputpixelformat` (8-bit fixed or 16-bit fixed), `includealpha` (off = alpha 1.0), `grouptable`,
  `audiochop`, `metadata`, `outputcolorspace`, `outputreferencewhite`. Page silent on SDK version, bandwidth and HX.
  **Set Skip Frames for the show** so a slow NDI encode cannot stall the TD main thread (and with it the panel/MIDI).
- **Arena side (doc, [NDI in Resolume](https://resolume.com/support/en/NDI_inputs_and_outputs), v7.22 tab):** inputs always
  enabled, appear in Sources; "at any resolution, including alpha"; a 60 fps 1080p stream "needs at least 150 Mbps"; NDI
  prefers Wi-Fi when both Wi-Fi and wired are up (macOS): **turn Wi-Fi off**; allow Arena under macOS Local Network privacy
  and the firewall; two machines need IPs in the same range; install NDI Tools on the receiver if sources stay at 0x0. Arena's
  own NDI output can drop bit depth/colour space/alpha to save bandwidth.
- **Bandwidth (doc: NDI [High Bandwidth SpeedHQ2](https://docs.ndi.video/all/getting-started/white-paper/bandwidth/ndi-high-bandwidth-based-on-speedhq2-8bit-4-2-2)
  and [SpeedHQ7 with alpha](https://docs.ndi.video/docs/white-paper/bandwidth/ndi-high-bandwidth-based-on-speedhq7-8bit-4-2-2-4)):**
  1080p60 about 132 Mbps (165 with alpha), 2160p60 about 250 Mbps (312 with alpha); intra-frame codec. **No source covers
  7488x2880 or 8K.** My extrapolation, pixel count only (21.6 Mpx = 2.6x 2160p): about **325 Mbps at 30 fps, 650 Mbps at 60 fps**
  from the 2160p figure; about 0.7 Gbps / 1.4 Gbps if the better 1080p bits-per-pixel is used (more pixels compress better,
  so the lower figure is likelier). With alpha about +25 %. **Unverified; measure with a test.**
  1 GbE (about 0.94 Gbps usable): 30 fps just fits with no margin, 60 fps does not. 10 GbE: comfortable.
  NDI HX (H.264/H.265, 5 to 85 Mbps) is not an option for a wall (forum, anecdotal: more delay and CPU; Arena can receive
  but not send HX).
- **Max resolution:** no stated cap in Resolume or TD docs; Arena 7.13.1 forum reports of some NDI sources staying black at
  odd sizes (1918x886) with no ceiling given (anecdotal). The viewer bridge already received Arena's own NDI at
  4538x1744 with rows padded to 4544 (L-55); 7488 and 2880 are multiples of 32, so no padding expected.
- **Same-machine loopback cost:** unmeasured. Mechanism: GPU -> CPU readback -> SpeedHQ encode (CPU) -> loopback -> decode (CPU)
  -> GPU upload for 86 MB frames. Worth measuring only if Syphon fails. Latency of NDI full: unmeasured (the PF26 viewer saw
  Arena's NDI at 27 to 28 fps, which is the viewer's reader, SYSTEM.md).
- **Alpha:** `includealpha` on (SpeedHQ7 variant, +25 % bandwidth). **Failover:** `failovername` lets a backup TD machine
  take over the same stream; whether Arena's NDI receiver honours failover is unverified.
- **Two-machine option (TD Mac -> Arena Mac, 10 GbE):** direct Mac-to-Mac cable (two 10 GbE adapters, no switch) is the
  simplest; static IPs in one /24, Wi-Fi off. Adds NDI encode CPU on the TD Mac and decode CPU on the Arena Mac, one
  to a few frames of delay (unverified), and hardware that is not in the bundle (a spend: the user's go-ahead).

## 4. Recommendation logic: one Mac or two, which texture, how Arena maps it

### 4.1 One Mac + Syphon vs two Macs + NDI
| | One Mac, Syphon | Two Macs, NDI over 10 GbE |
|---|---|---|
| Moving parts | 2 apps, 1 machine, no network | 2 apps, 2 machines, cable, NDI settings |
| Quality | 8-bit RGBA, lossless | SpeedHQ lossy, 8-bit (16-bit option) |
| GPU / thermal | shared M1 Max: TD (section 1) + Arena DXV3 7488x2880 + Advanced Output; **unmeasured together** | TD and Arena each get a whole GPU |
| Fault isolation | separate processes (TD crash does not kill Arena) but one power/thermal/OS | full |
| CPU | none extra | NDI encode + decode of 21.6 Mpx frames (unmeasured) |
| Latency | probably 1 to 2 frames (unverified) | NDI adds more (unverified) |
| Backup parity (MOU: mirrored machine switched at FOH, RUNTIME section 8) | backup = 1 identical Mac | backup needs the pair, so **4 Macs** (or a backup without the TD layer) |
| Cost / go-ahead | none | adapters or switch = a spend |
| Controls | USB MIDI + panel on the same Mac | MIDI on the TD Mac; Arena SAFETY deck on the Arena Mac, so the kill is on a different machine than the controls |

**Recommendation: one Mac with Syphon**, gated by two tests: (a) TD + Arena soak with Arena playing the 7488x2880 DXV3 base
(GPU, fps, temperature, 2 h), (b) the source-drop and kill tests (section 6). If (a) fails, the order of fixes is: half-resolution
TD (4x cheaper), cook rate 30, fewer slots, then two machines over NDI. Why not NDI first: lossy, unknown 7488-wide behaviour,
extra hardware, and doubled backup. The loopback NDI on one Mac has no advantage over Syphon except 16-bit/alpha options.

### 4.2 Which texture to send
Pixels per frame (8-bit): atlas 7488x2880 = 21.6 Mpx / 86.3 MB; front strip 5184x2880 = 14.9 Mpx; half 3744x1440 = 5.4 Mpx /
21.6 MB; per face C 1728x2880 = 5.0 Mpx.
1. **Full atlas 7488x2880 @ 30**, authored in TD in plan space and assembled like `mapping.py` (C section 2): the layer matches the
   composition 1:1, so Arena does no scaling and the Advanced Output slices (below) crop it directly. Use for light looks
   (REP1-class: 60 fps capable, so 2x headroom at 30). Section 1 shows REP4-class is the ceiling at 30 fps with no spare.
2. **Half atlas 3744x1440 @ 30 or 60, scaled 2x by Arena** when a look is heavy (REP8-class, particles over 4 M). 4x cheaper in
   TD, 4x less Syphon traffic. Fine for soft light, beams, gradients, grain (the TD jobs in DIRECTIONS section 3); hard edges and
   type soften (not TD jobs: names, logos, Urdu are HyperFrames). How Arena scales a smaller source into a layer
   (Autosize/Transform) was not verified: the manual pages I could fetch do not say; test.
3. **Per-zone feeds** (extra Syphon servers: C only 1728x2880, or L1/R1 wings) are cheaper still and could be placed by layer
   position in Arena, but each is another Syphon/NDI source, another test and another thing to fail. Use only for a zone effect
   (e.g. a hero particle field on C). A "front strip only" feed is not a contiguous block of the atlas (returns sit between L1..R1
   in atlas order), so it cannot be positioned in the atlas without slice routing: not recommended.
Frame rate: STAGE.md fixes 30 fps (user, 15 Oct); set TD `project.cookRate = 30` so TD, Syphon and the Arena composition share
one cadence (a 60 Hz sender into a 30 fps composition judders by frame repeat or drop: unverified in Arena).

### 4.3 How Arena maps a live source onto R02
Existing plan (`prismfest26-show/RUNTIME.md` section 8, `STAGE.md`): composition = full wall canvas **7488x2880**; **Advanced
Output = 9 slices cut from the final LED map**, routed to vendor outputs after RFI05; layer 6 FX = "TouchDesigner via Syphon + live
FX", "reactive loss -> base loop keeps running". No 9-slice PF26 preset file was found in `prismfest26-show/`; the StageLab repo
has Arena Advanced Output test XML (`.worktrees/*/tests/fixtures/arena_advanced_output_9col.xml`, `..._pf26_2screens.xml`,
written by Arena 7.23.2 revision 51094, composition 4537x1745) as format evidence only.
- A Syphon/NDI source in a layer is composited in **composition space** like any clip; Advanced Output slices then take their
  `InputRect` from the composition (doc: [Input Selection](https://resolume.com/support/en/input-selection), v6: any part of
  the composition, typed values, no size limits stated). So **a 7488x2880 TD atlas needs no separate mapping**: atlas x
  offsets (L1 0..1152, L2 1152..1728, ..., R1 6336..7488) must match the composition's slice rectangles. Orientation/flip to be
  verified with a pattern that has a top.
- Alternative (doc: [Slice Routing](https://resolume.com/support/en/slice-routing), v7.9): a layer or a whole screen can feed a
  slice directly instead of the composition. Caveat from the manual: it bypasses the composition (no blend modes, no composition
  effects; "straight alpha on top of the other slices"), and "don't use it as a quick way to position content". It could feed
  one TD source to a few slices only, but it also removes the base layer under it: not recommended for layer 6.

## 5. Controls in TD
Weighted to the user's decision: hand-operated panel + MIDI controllers, per look and per show state, crossfades, a kill.

### 5.1 Panel
- **Classic panel COMPs are creatable and have the pars needed (probed):** `sliderCOMP` (`slidertype`, `value0`/`value1`,
  `valuerange0l/h`, clamps), `buttonCOMP` (`buttontype` = momentary, toggledown/up, radio, exclusive...; `value0`),
  `fieldCOMP`, `containerCOMP`, `widgetCOMP` (probed: a container-like COMP, no widget-type menu), `windowCOMP`. The 2025 "Basic
  Widgets" (masterSlider, masterButton, buttonToggle, sliderHorz, ...) are documented
  ([Widgets](https://derivative.ca/UserGuide/Widgets)) as palette items under Derivative > UI, but **this install's Palette
  folder has no Widgets folder** (probed `os.listdir(app.paletteFolder)`: Generators, ImageFilters, Mapping, ..., Tools, UI, ...),
  so use Slider/Button COMPs or load the widgets from the Palette in the UI. Bindings of widgets to parameters are described only in
  tutorials ([I&I HQ](https://interactiveimmersive.io/blog/controlling-touchdesigner/bindings-with-matthew-ragan/), unverified
  here); parameter mode `BIND` exists in the MCP (`td_set_pars`).
- **Pattern:** one `/show` COMP with a **Controls** COMP holding custom pars (`Master`, `Slot1`..`Slot8`, `Speed1`.., `State`,
  `Safe`, `Kill`; one capital then lowercase, T-00e), the panel sliders/buttons bound to them, and MIDI writing to the same pars,
  so panel and hardware always show the same value. Panel and MIDI are two inputs to one parameter set.
- **Window:** a Window COMP showing the panel container on the control screen (probed pars: `winop`, `display`, `justifyh/v`,
  `size`, `borders`, `alwaysontop`, `vsyncmode`, `closeescape`, `performance`, `setperform`; doc
  [Window COMP](https://docs.derivative.ca/Window_COMP): "Bounds of all displays" on macOS needs Mission Control "Displays have
  separate Spaces" off). **Perform mode** (doc [Perform Mode](https://docs.derivative.ca/Perform_Mode)): F1 enters, Esc returns,
  renders only the Perform window's COMP and frees the Designer UI memory; Python `ui.performMode`. Probed project attributes
  for autostart: `project.performOnStart` (now False), `project.performWindowPath` (now '/perform'), `project.windowStartMode`.
  A separate output preview (a small Fit TOP of the atlas) on the panel is cheap; never show the full 7488x2880 in the UI.
- Show the panel on the control screen, never on the LED wall output (the wall output is the Syphon feed, not a window).

### 5.2 MIDI input (devices not opened)
- TD ops (probed class list): `midiinCHOP`, `midiinDAT`, `midieventDAT`, `midiinmapCHOP`, `midioutCHOP`. **MIDI In CHOP** (doc
  [MIDI In CHOP](https://docs.derivative.ca/MIDI_In_CHOP), rev. 28 Jul 2026): `Device ID`/`Device Table`, `MIDI Channels` 1 to 16,
  Control Change channels named `<Controller Name><0..127>`, note/velocity/pitch-wheel base names; the page does not describe a
  Learn feature or disconnect behaviour. **MIDI In Map CHOP** ([doc](https://docs.derivative.ca/MIDI_In_Map_CHOP), rev.
  2 Nov 2023): reads the mapping made in Dialogs > MIDI Device Mapper; channels `s1..` (sliders) and `b1..` (buttons); export methods
  to parameters; the page does not say how learning or storage work. Open question: do both controllers share one MIDI Device Mapper
  entry each (two devices -> two MIDI In CHOPs).
- **Recommendation:** MIDI In CHOP -> Select CHOP (explicit CC/note list) -> Lookup/Math -> custom pars through a small Python
  CHOP Execute or a parameter export, with the CC table held in a Table DAT, so the map is a readable file in the project and
  survives a device swap; use the Device Mapper only for the one-time learn. Add **pickup (takeover) mode**: the MIDImix knobs
  are not endless (270-degree pots, Akai: they "will not always be in sync"; the editor has "Send All" to resend positions), so after a
  state change a fader's physical position differs from the stored value; the parameter should not jump until the fader
  crosses the stored value.
- **Several apps can read one MIDI device through CoreMIDI** (general macOS knowledge, unverified for these two controllers), so Arena can bind its own SAFETY/kill buttons to the same controller or a second one (section 6).

### 5.3 The two controllers: defaults and a proposed map
Sources: [Spectrasonics MIDImix page](https://support.spectrasonics.net/manual/Omnisphere3HW/3/en/topic/setting-up-the-midimix),
[Akai: MIDImix editor](https://support.akaipro.com/en/support/solutions/articles/69000856691-akai-pro-midimix-using-the-editor-for-customisation),
[Spectrasonics MPK Mini mk3 page](https://support.spectrasonics.net/manual/Omnisphere3HW/3/en/topic/setting-up-the-mpk-mini-mk3),
[Akai MPK Mini mk3 FAQ](https://support.akaipro.com/en/support/solutions/articles/69000798861-akai-pro-mpk-mini-mk3-frequently-asked-questions).

**Akai MIDImix (24 knobs, 9 faders, 8 mute + 8 rec-arm, solo, bank L/R):**
- Faders (sourced, factory defaults): 1 to 8 = CC **19, 23, 27, 31, 49, 53, 57, 61**, master = CC **62**. Knob row 1 (sourced):
  CC **16, 20, 24, 28, 46, 50, 54, 58**. **Knob rows 2 and 3 are not on the sourced pages** (pattern from memory: row 2 = row 1 + 1,
  row 3 = row 1 + 2: **unverified**). Button numbers (mute, rec arm, solo, bank L/R): **not found**; Akai says buttons can send
  CC or note, buttons default type "not stated"; users report bank L/R only as notes.
- **No editor needed for the default map** (the Spectrasonics page uses the factory settings; the editor only changes CC/note
  and channel per control, saves `.midimix`, and "Send to Hardware"). The MIDI channel default is not stated (probably 1:
  unverified). The editor is needed only if a unit was customised.
- **Proposed map:** faders 1 to 8 = slot levels (post state-crossfade); **master fader = output dimmer** (final multiply; at 0 the
  output is black, works without any software state); knob row 1 = slot speed, row 2 = slot hue shift inside the PRISM palette,
  row 3 = slot density/scale (24 knobs = 8 slots x 3 params); mute buttons 1 to 8 = slot on/off (latched in TD; LED feedback via
  MIDI Out is unverified); rec-arm buttons 1 to 8 = **select** state 1 to 8 (not go); bank left/right = state page -/+; solo =
  SAFE HOLD (calm stable look; never BLACKOUT on a button next to ones used constantly).

**Akai MPK Mini MK3 (25 keys, 8 knobs, 2 banks x 8 pads, joystick):**
- Knobs K1 to K8 = CC **70 to 77** (sourced, with program "PGM: MPC" loaded; the editor restores them); pad 5/6 in CC mode = CC 20/21
  on bank A (sourced, a CC-mode detail). **Pad note numbers per bank, channel and joystick defaults: not found** (the manual PDF
  was not retrievable, 403). Joystick can be Pitch Bend (4 directions), Modulation 1 (one CC per axis, centre 64) or Modulation 2
  (two CCs per axis, centre 0) (Akai FAQ). 8 built-in programs via Prog Select + pads 1 to 8. The `CC` and `Prog Change` buttons switch
  the pads from notes to CC / program change: **keep pads in note mode and do not press them by accident.**
- **Proposed map:** pad bank A (red) = **one-shot hits**, each through a flash governor (see below); pad bank B (green) = state
  jump 1 to 8 (with the panel highlighting the target before GO); K1 to K8 = fine params of the slot selected on the panel
  (speed, hue, size, density, trail, intensity cap, ...); joystick X = nudge of the A/B crossfade, joystick Y = temporary
  intensity bump (springs back to centre = safe); keys: unused, or palette select; transpose keys must not trigger states.
- Learn the real numbers once with a MIDI In CHOP monitor (needs the user's go-ahead: opens the device).

### 5.4 OSC between TD and Arena (secondary)
- Arena 7 (doc [OSC](https://resolume.com/support/en/osc), v7.18 tab): enable in Preferences > OSC, default input port **7000**,
  every parameter has a fixed address (`/composition/layers/1/video/opacity 0.25`,
  `/composition/layers/2/clips/8/transport/position`), `"?"` polls a value, the OSC tab shows the last 200 messages, the full list
  "changes depending on how you have your composition set up" (Shortcuts > Edit OSC shows the real address). OSC output is
  per-preset and can go to Localhost/Broadcast/IP.
- **The bundle's map (`resolume7-fx-pipeline/CLAUDE.md`, "a starting point, not gospel", verify with `master.py learn`):**
  `/composition/dispatchclipfire layer col`, `/composition/layers/{l}/clips/{c}/connect 0|1`, `/composition/layers/{l}/opacity`,
  `/composition/master`, clip `video/hue|saturation|brightness`, `/composition/layers/{l}/bypass`. Note it uses
  `layers/{l}/opacity` while Resolume's own doc example is `layers/1/video/opacity`: another reason to re-learn. Tempo:
  `/composition/tempocontroller/tempo` appears in a Resolume 6 staff answer
  ([forum](https://www.resolume.com/forum/viewtopic.php?p=64064)); **column connect and crossfader addresses are unverified.**
- TD ops: `oscoutCHOP/DAT`, `oscinCHOP/DAT` (probed class names). Creating an OSC In opens a UDP port: not done.
  Practical use: **TD -> Arena** for the layer-6 opacity and a column/clip trigger on state changes (so the Arena-side FX layer
  fades with TD's state), **Arena -> TD** for the composition BPM or beat. All secondary to the hand controls.
- **BPM sync:** TD has `abletonlinkCHOP` (doc [Ableton Link CHOP](https://docs.derivative.ca/Ableton_Link_CHOP), rev. 24 Nov 2023:
  outputs ramp/pulse/sine/count/bar/beat/sixteenths, phase and tempo; **tempo is output only, no parameter to set it**). Arena has
  Link (doc [Link](https://resolume.com/support/en/link), v6: View > Show Ableton Link; while on, **BPM Resync and Pause are
  disabled**; Link peers are equal, a tempo change by any peer changes all). So TD and Arena can follow one Link session on the
  same Mac (forum: works with Live; Arena-to-Ableton on one computer, 7.2.1 era, anecdotal); tempo is then set from Arena (or the
  band's Ableton). Bands play live: BPMs and medleys are open (RUNTIME), so tap tempo in TD (`beatCHOP`, probed) is the plain
  fallback. Do not let beat analysis drive names/reveals (CREATIVE.md: audio only modulates texture; TALK = reactivity OFF).

### 5.5 Cue list / state machine and crossfades
- **States:** one row per PF26 state (RUNTIME section 2: DOORS, COUNTDOWN, HOST, INTRO, LIVE-STORY, LIVE-LOOP, TAKEOVER, TALK,
  OUTRO, CHANGEOVER, CLOSE, SAFE HOLD, BLACKOUT, EMERGENCY). The live layer participates in some (DOORS/CHANGEOVER/LIVE-LOOP/
  TAKEOVER/CLOSE); in HOST, TALK, BLACKOUT, EMERGENCY it is off (decide with the lead). A **Table DAT** `states`:
  `name, fade_s, slot1..slot8 weights, speed_cap, palette, reactive(0/1)`; a Python extension `GoState(name)` writes the target
  weights; one `Lag CHOP`/`Filter CHOP` (probed classes, separate up/down lag) smooths current -> target; the smoothed weights
  drive slot opacity in a Layer Mix/Composite TOP (probed `layermixTOP`, `compositeTOP`, `crossTOP`, `switchTOP`).
- **Do not pay for looks at weight 0:** TOPs cook while connected, regardless of opacity. Probed: `COMP.allowCooking` exists (read
  True on `/project1/geo1`); set it False on a slot COMP when its weight has been 0 for > 1 s and True at fade start. A Switch TOP
  also cooks only the selected input. Both are standard TD practice; the savings are unmeasured here.
- **Crossfade rule:** state change = weights glide over `fade_s` (suggest 2 to 8 s, 0.5 s for hits); the output dimmer and the
  hits sit after the crossfade. Palette changes by blending parameters, not by cutting.
- **Flash governor** (PF26 rules, `concert-visuals-research/README.md` section 4: flashes are not allowed when > 25 % of the
  screen flashes more than 3 times per second; leading edges ≥ 9 frames apart are fine): limit hit triggers to one per ≥ 9 frames
  (0.3 s at 30 fps), cap strobe-like looks by rate not by taste, and measure luma delta of the downscaled output with an Analyze/
  Math CHOP chain (design, unverified) to drop gain automatically. Saturated red flashes are the risky case.
- **Kill / safe, inside TD:** (1) master fader/`Master` par = final multiply; (2) `Safe` = state SAFE HOLD (low-motion stable
  slot only, sliders ignored); (3) `Kill` = output alpha 0 and `Active` off on the Syphon Out TOP (par `active`, doc) so the source
  disappears; an Arena-side kill is separate (section 6). Do not rely on a TD kill alone: if TD hangs, it does nothing.

## 6. Fail-safe
- **What Arena does when the Syphon/NDI source drops: not documented; not tested.** Resolume's pages say nothing. The only hint is
  an anecdote about a capture device in the Resolume forum (Arena froze the last frame, did not refresh after the signal came
  back, only restart fixed it; staff reply: "resolume detects input sources on startup"), **not Syphon, not Arena 7**. Possible
  outcomes to test: (a) clip goes black/transparent, (b) last frame stays, (c) clip flips to an empty source and recovers by name.
  Source disappearance, TD quit, TD hang (SIGSTOP), `Active` off and a slow cook are different events; test all four.
- **Design that is safe for both outcomes:** layer 6 FX **above** layer 1 BASE (RUNTIME section 8) with an **Add/Screen blend
  or luma key**, so a black or transparent TD frame shows BASE; and **an Arena-side kill for layer 6** (layer opacity or bypass on a
  dedicated MIDI button or a physical SAFETY-deck button, RUNTIME: SAFE HOLD, BLACKOUT, EMERGENCY have their own buttons, layer 8
  SAFETY deck top) that works with TD dead. A frozen last frame under Add stays visible, so the kill must be reachable in seconds.
  Alpha: Syphon is RGBA 8-bit and `includealpha` exists for NDI; the project memory says Resolume clips with alpha go premultiplied,
  so use Add (no alpha needed) unless a test shows straight alpha is read correctly.
- **TD crash recovery:** TD crashed once today (section "Bugs hit"); 7 `.ips` crash reports exist for 11 to 16 Oct
  (`~/Library/Logs/DiagnosticReports/TouchDesigner-2026-10-1*.ips`: 5 on 11 Oct, 1 on 12, 1 on 16), plus `~/Desktop/
  CrashAutoSave.NewProject.1.toe`. During development with the MCP, so not a show rate, but the rig must assume a crash.
  Measures: **`project.performOnStart` = True** and the project's perform window (probed attributes) so a relaunch lands in
  perform mode with the panel; a **watchdog outside TD** (launchd `KeepAlive` agent running `open -W`; generic macOS technique,
  [source](https://notes.alinpanaitiu.com/Restarting-macOS-apps-automatically-on-crash), not TD-specific) plus a **heartbeat** (TD
  sends an OSC/UDP ping each second; if it stops, the watchdog `kill -9`s TD so the Syphon server vanishes and relaunches).
  A hang does not exit the process, a launchd `KeepAlive` alone would miss it. Cold start to connected was about 30 s (T-07); the live
  layer would be dark for roughly 30 to 45 s per crash (shader compile on first cook adds to it): unverified; rehearse it. TD's own
  autosave is not a restore of live state, keep the show state in a Table DAT file.
  macOS may show a crash dialog (LEARNINGS T-00g: invisible to Claude); whether it blocks a launchd relaunch is untested.
- **Long run (6.5 h, 5:30 PM to midnight):** no thermal or memory-growth measurement exists. Do: 2 h soak at show load before
  Friday (log fps, TD memory via `ps`/Activity Monitor, GPU temp via iStat Menus, which is installed); power adapter, lid open,
  `caffeinate -dimsu`, no other apps (this dev Mac shows 21 to 29 % GPU idle from other apps, section 1), App Nap off for TD
  (unverified command: `defaults write <TD bundle id> NSAppSleepDisabled -bool YES`), Do Not Disturb, no software updates. TD kept
  cooking in the background at 60 fps for a light load in my runs; a lower figure was recorded in td-port (about 28 fps in the
  background, C section 4): re-test with the real network.
- **Backup parity (C section 4, RUNTIME section 8 "second machine runs a mirror of the composition, switched at FOH"):** the backup
  Mac needs the same TD project, same Arena composition, same MIDI map and the same Syphon name. The MIDI controllers can only be on
  one Mac (or split by CoreMIDI network session, unverified). Options: (1) backup TD sits on SAFE HOLD/last state fed by OSC
  state mirroring from the primary TD (`oscoutDAT` -> `oscinDAT`, design); (2) backup without TD layer (BASE only). Either way the
  hand state on the backup is "not the live state" at switch time: rehearse it. NDI Out has `failovername` for a hot-standby TD
  (two-machine option only).

## 7. Rig plan and test plan
### 7.1 Rig plan (recommended: one Mac)
- **Primary Mac (M1 Max, 64 GB):** TD 2 (Rosetta) `PF26_live.toe` in perform mode on the control screen: Controls COMP + panel +
  MIDI maps + `states` table + slot COMPs (each a wall-size or half-size TOP) -> mixer -> dimmer -> **Syphon Out TOP "PF26-TD",
  8-bit, 7488x2880 (or 3744x1440)**, `project.cookRate = 30`. Arena 7.23.2: composition 7488x2880, layer 6 FX holds the Syphon
  source in a deck column on the `00 SHOW` deck, blend Add, above BASE; Advanced Output = the 9 slices; SAFETY deck on layer 8 with
  the physical buttons, plus a dedicated button for layer-6 bypass.
- **Controls:** MIDImix + MPK Mini MK3 on USB into the TD Mac (hub with power), panel on the control screen, optional OSC TD -> Arena
  for the layer-6 fade.
- **Backup Mac:** identical, on SAFE HOLD or mirrored state, switched at FOH with Arena's mirror (rehearsed).
- **Fallback tiers:** half-resolution TD; fewer slots; TD layer off and BASE only (the pre-render path, DIRECTIONS section 0).

### 7.2 Test plan (ordered; "GA" = needs the user's go-ahead)
1. **TD-only cost with real looks** at 7488x2880 and 3744x1440, cook rate 30 and 60, 8/16-bit; repeat the section 1 method on each
   real slot network; build budget table (no go-ahead; TD only).
2. **TD soak, 2 h, no Syphon**, show-like network, log fps, memory, GPU temp (no go-ahead).
3. **Controller learn: GA** (opens the MIDI devices; MIDI In CHOP monitor): record real CC/note numbers of the MIDImix and MPK, the
   joystick mode, channels, button types; write the table DAT.
4. **Syphon Out -> PF26 viewer bridge: GA** (starts a Syphon server; the viewer's `live_bridge.py` is a receiver that does not touch
   Arena): check that TD publishes at all, size limit (3744x1440, 5184x2880, 7488x2880), orientation (L-54), alpha, fps, CPU/GPU
   cost of the server, `Active` toggle behaviour.
5. **Arena receives the Syphon source: GA** (Arena + Syphon, in a scratch composition, not the show file): source appears in Sources;
   resolution scaling into a 7488x2880 layer; orientation; alpha/blend; fps and judder at 30 vs 60 TD rate; **source-drop tests**
   (`Active` off; quit TD; `kill -9`; SIGSTOP hang; GPU-heavy hitch) and the recovery by name; layer-6 kill button; Rosetta server
   vs native client check.
6. **Shared-GPU soak: GA** (Arena): Arena plays the 7488x2880 DXV3 base (PIPELINE section 8 test, still pending) + 9-slice Advanced
   Output + TD live layer, 2 h, log fps of both, dropped frames, temperature, memory.
7. **Crash/watchdog rehearsal:** kill TD with the layer visible, time relaunch to live (perform mode on start), heartbeat watchdog
   kills a hung TD (GA: Arena visible).
8. **NDI loopback (only if Syphon fails): GA**: same measurements at 3744x1440 and 7488x2880 plus CPU and latency.
9. **Backup switch rehearsal, Fri 23 Oct (RUNTIME handover day): GA**: mirror switch with TD live, state mirroring.
10. **Two-machine NDI over 10 GbE (only if 5 or 6 fail): GA + spend** (adapters).

## Bugs hit
1. **TD crashed at 18:42:13 (local), 16 Oct, during this research.** Evidence: `~/Library/Logs/DiagnosticReports/
   TouchDesigner-2026-10-16-184213.ips`: `EXC_BAD_ACCESS / SIGSEGV, KERN_INVALID_ADDRESS at 0x0`, faulting thread is the main
   thread, frames in `libUT.dylib` then `libUI.dylib` and `libOPUI.dylib` (UI code), TD pid 12186 gone, MCP replied "TouchDesigner
   disconnected before replying". What was running: my `td_exec` had just (a) destroyed all children of `/project1/_research_probe`
   (an Execute DAT among them) and (b) created a Text DAT whose `tick()` rescheduled itself with `run(..., delayFrames=1)` each frame,
   then a second `td_exec` with `frames=120` was waiting. Another agent's Script TOP network (`_research_probe1`, a cook of about
   3 s) was running in the same TD. **Cause not established** (candidates: destroying an op the UI had open; the self-rescheduling
   `run` chain; the other network; unverified). Rule: in a shared TD do not self-schedule `run()` chains and do not destroy a
   COMP's children in the same call that creates new ones; use Execute DAT callbacks and delete once.
   **I relaunched TD** (one `open -a "TouchDesigner 2.app" .../projects/JazibTD_home.toe` at about 18:42:24, result pid 57376,
   reconnected 18:42:47 UTC+5 = T-07 behaviour). pid 57140 (blank, started 18:42:18, six seconds before my command, parent 1)
   was not started by me; another agent's command was waiting on `CrashAutoSave*` and a TD pid at that time. The lead closed it.
   Figures were taken after that (section 1).
2. **Execute DAT `onFrameEnd` stopped firing** after 214 calls (a counter stuck at 214 with the DAT still active; toggling
   `active` did not restart it); `onFrameStart` worked for the remaining tests. Cause not found. Rule: for a frame pump use
   `onFrameStart` and check the counter advances.
3. **`absTime.frame` is not an fps readout:** it follows wall-clock time; cooked-frame counts were 73 of 186 in 3.1 s.
   Rule: count cooks (`op.totalCooks` or a callback counter), never `absTime.frame` deltas, for fps.
4. **GLSL TOP `vec0name = 'uTime'` does not declare the uniform:** shader needs `uniform vec4 uTime;` and `uTime.x`; the error
   is only in the Info DAT ("`uTime` : undeclared identifier") and as a warning on the TOP (T-02). The first GLSL numbers
   (22 to 30 fps) came from the failing shader and were discarded. A.md section 6 recipe 2 omits the declaration.
5. **Shared-TD measurement contamination:** other agents' networks changed my fps by 2 to 3x (REP8 7488x2880: 19 to 31 fps
   contaminated vs 24.6 clean; half resolution looked slower than full). Rule: before any fps test, list `/project1` children, run
   the 64x64 baseline (expect 60.0 fps, max < 21 ms) and repeat twice; report the idle GPU load.
6. **`create(sliderCOMP, 'stest')` returned `stest1`** because a stale name collided; the first `td_delete` by the intended names
   reported them missing. Rule: use the path returned by `create`.
7. `td_perf` reports `gpuCookTime` 0 for every op on this build; no per-op GPU cost is available (workaround above).
8. WebFetch of Derivative docs returned 404 for `/MIDI_Device_Mapper`, `/Widget_Palette`, `/Dialogs_Menu`; the Akai MPK Mini mk3
   manual PDF (zzounds) returned 403, so pad notes could not be sourced.
9. **Version string mismatch seen on disk, not a TD fact:** `/Applications/Resolume Arena/Arena.app/Contents/Info.plist` (and the
   `.api9-2026-10-08` copy) read `CFBundleShortVersionString` 7.28.1 build 26535, while the bundle docs and Arena-written XML say
   7.23.2 revision 51094. Only the strings were read (no provenance checks, per the host-install rule). See Open questions.

## Open questions for the lead
1. **Which Arena is the show host?** Info.plist on disk says 7.28.1 (26535), the docs and the Arena-written fixtures say 7.23.2
   (51094). The Resolume docs I cite are v7.22-era pages; if the host is 7.28, check Syphon/NDI/Advanced Output notes against it.
2. Same Mac or two: I recommend one Mac + Syphon (section 4.1) gated by the soak test; do you want it as the primary plan, and may
   steps 4 to 6 (Syphon out, Arena scratch composition) run now?
3. May I (or another agent) open the MIDImix and MPK in a MIDI In CHOP once to learn the real CC/note numbers (opens the
   devices)? Knob rows 2/3 and all button numbers are unsourced.
4. Which PF26 states should the TD layer cover, and is TD allowed on TALK/HOST (reactivity OFF) at all? The state table needs
   that list (section 5.5).
5. Cook rate: 30 fps to match the composition (STAGE.md), or 60 for smoother TD motion? Is the Arena composition at 30 fps?
6. Layer-6 blend: Add (no alpha needed) or alpha (premultiplied rule in project memory)? The user's looks need to be luminous
   anyway.
7. Is a 4-Mac rig (two pairs) acceptable, or should the backup run without the TD layer? Is the show Mac a laptop (thermal) or a
   desktop?
8. Who runs the hand controls during the show: the user alone, or a second operator (a second controller, dual-MIDI)?
9. May the watchdog (launchd agent + heartbeat) be built for the show Mac, and is a crash dialog acceptable at FOH?
10. Do you want the lead-side TD probe lessons (items 2 to 5 of Bugs hit) as `T-nn` entries in `LEARNINGS.md`? I did not edit it
    (brief: write only the research file).
