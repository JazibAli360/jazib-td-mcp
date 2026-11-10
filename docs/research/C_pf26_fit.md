# C: where TouchDesigner content fits PRISMFEST'26 and its production pipeline

Research agent C, Fri 16 Oct 2026 (~7:30 PM). Research only: no TD touched, nothing generated, no PF26 script that
writes was run (`assets_where.py` was NOT run, because for a show asset it creates the `To Review/` folder, line 30 of
the script; `viewer_audit.py` was run, it is read-only). Paths are relative to `StageLab_PrismFest/` unless noted.
Facts from the repo carry the file. Anything from memory or older builds is marked **unverified**. No fps or
performance figure appears without a measurement; the file-size figures below are measured from the existing masters.

---

## 1. The show's needs, and what is covered

### 1.1 Running order and states (`prismfest26-show/show.json` running_order, `RUNTIME.md` §2, §4)

Sat 24 Oct 2026, 5:30 PM to 12:00 AM, Karachi. Programming day Fri 23 Oct; MOU library date 19 Oct, final specs 21 Oct,
organiser build 22 Oct (`show.json` calendar).

| Time | Block |
|---|---|
| doors (TBC) to 5:23 PM | DOORS (A01/A02) |
| 5:23 to 5:25 PM | HOST welcome (B01/B02, host Ahmed Godil) |
| 5:25 to 5:30 PM | COUNTDOWN (A03) into the show-open sting (A04) |
| 5:30 to 6:30 PM | 1 Nehaal Naseem (NN) |
| 6:30 to 7:00 PM | Changeover 1, 30 min, tease AH (F08) |
| 7:00 to 8:00 PM | 2 Abdul Hannan (AH) |
| 8:00 to 8:25 PM | Changeover 2, 25 min, tease HR (F09) |
| 8:25 to 9:25 PM | 3 Hasan Raheem (HR) |
| 9:25 to 9:45 PM | Changeover 3, 20 min, tease MZ (F10) |
| 9:45 to 10:45 PM | 4 Mustafa Zahid (MZ) |
| 10:45 to 11:00 PM | Changeover 4, 15 min, tease AZ (F11) |
| 11:00 PM to 12:00 AM | 5 Ali Zafar (AZ) |
| 12:00 AM on | CLOSE (G01 finale, G02 end card) then BLACKOUT |

14 states (RUNTIME §2): DOORS, COUNTDOWN, HOST, INTRO, LIVE-STORY, LIVE-LOOP, TAKEOVER, TALK, OUTRO, CHANGEOVER,
CLOSE, SAFE HOLD, BLACKOUT, EMERGENCY. 87 assets in the build list (RUNTIME §6). Per-state lengths that matter for TD:
A01 10 min seamless, A02 5 min seamless, A03 5 min, A04 10 to 12 s, B02 2 min seamless, C-x-3 TALK 2 min seamless,
C-x-4 TAKEOVER 15 to 20 s plus loop tail, E loops 16/32-bar seamless, F01 to F04 stings 6 to 12 s, F05 bed 60 s seamless,
F06 10 s, F08 to F11 teases 60 s, G01 30 to 60 s, G02 hold.

### 1.2 The coverage picture (assets index `production/assets/index.json`, generated 16 Oct 6:08 PM; verdicts through viewer seq 331)

**The big finding: the production so far is stills. Video is almost nonexistent and nothing is in `Final Assets/`.**
`find "production/assets/Final Assets" -type f` returns nothing. The only clips anywhere in the pipeline are four ProRes
masters in `Mastering/` waiting for DXV3: `D1_light-leak-video-v02.mov` (A01, 6 s), and NN's three
`C-NN-1v4a2m / v4b1m / v4b2m` motion plates (13 s, 8 s, 13 s). All four are 7488x2880, ProRes 422 10-bit, 24 fps
(probed with ffprobe). The AZ poster clips are in Changes/Denied.

Approved stills per house/safety asset (from index.json, `status == approved`; none has a video):

| Asset | State | Approved looks (stills) | Open / weak |
|---|---|---|---|
| A01/A02 | DOORS | D1 light leak v02, clip in Mastering (DXV3 not made); 3 other D1 clips denied | needs 10 min / 5 min; a 6 s clip would repeat about 100 times |
| A03 | COUNTDOWN bed | A03 "Gathering light" | video todo (STATES.md); 5 min cannot come from an 8 s Veo clip |
| A04 | show-open sting | A04a curtain of light, A04b spectrum sunrise (keep both) | video todo |
| B02 | HOST bed | B02c1 ajrak haze, B02d1 velvet dusk | video todo; 5 variants denied before |
| F01 | sting Prism Bloom | F01c1, c2, d1, d2 | video todo |
| F02 | sting Facet Shatter | **none** (7 denied) | **no look at all** (STATUS open item 11) |
| F03 | sting Light-Slice Wipe | F03b "light rush" | video todo |
| F04 | sting Signal Reset | F04c1, c2 (truck-art glitch) | stepping at depth steps was the early objection (STATES.md 15 Oct) |
| F05 | PRISM Portal bed (60 s seamless) | D3 portals | video todo; hard shapes, so L-32/L-38 apply |
| F06 | Crowd Pulse ident | F06d1, d2 (sea of lights) | video todo |
| F07/H02 | clean hold, micro-motion | H02a1 haze drift | static H01 already in Mastering |
| F08 to F11 | teases (60 s) | F08, F09, F10, F11d1/d2/e1/e2 | video todo (STATUS item 13) |
| G01 | finale (30 to 60 s) | G01c2, d1, d2 | video todo; user note "works if u can make it loop" |
| G02 | end card bed | G02 | video todo |
| H01, H03 to H05 | safe/emergency | approved static cards (H01 in Mastering) | static; not TD (info/emergency are plain posters, BRIEF guardrail 5) |

Artist rows (index.json counts; STATUS "Where it stands"):

| Row | State |
|---|---|
| NN | L-NN: 49 approved / 25 denied stills (30 picks); S01a-4, S02a-2, C-NN-4a-2 (TAKEOVER), C-NN-5a-3 (OUTRO) approved stills; three C-NN-1 poster clips in Mastering; **TALK C-NN-3 denied twice, open** |
| AH | L-AH: 8 approved / 4 changes / 5 denied (needs about 20); C-AH-1 posters 3 approved; S03/S04, TALK, TAKEOVER, OUTRO not started |
| HR, MZ | findings and directions written, **nothing generated** (STATUS) |
| AZ | only the C-AZ-1 posters (changes/denied); loops, stories, TALK, TAKEOVER, OUTRO not started |
| E | generic loop pack, 24 loops, **not started** (no look exists) |

Whole-night shortage: 12 stories (S01 to S12), 100 plus artist loops (all stills), 24 E loops, 5 TALK, 5 TAKEOVER, 5
OUTRO, 5 posters, every house bed/sting as video. Each video job needs the user's go-ahead plus `max_credits`
(PIPELINE §4; the Jazib MCP read 10 credits for a `veo-fast` 8 s clip, `PIPELINE.md` §4 Credits line), and a full-wall
state is 3 tall clips (about 30 credits). Mapped files go through `mapping.py` / `assemble_wall.py` with ×1.6 to ×2.7
upscale from Flow's 1080p ceiling (PIPELINE §1, §4b).

### 1.3 Where procedural TD content would actually help

What Flow does badly in this repo's own evidence (so TD has a real argument):

- **Length.** Flow clips are 8 s (+7 s per extend). The plan needs 60 s to 10 min beds (RUNTIME §6).
- **Clean loops.** Veo start=end "builds up and folds back" (L-84), "start+end is not a clean loop" (L-36). Measured wrap jumps 3 to 5x a normal step.
- **Three-clip walls drift** apart mid-clip and need row-by-row light matching (L-37, L-39).
- **Face-aware placement.** Prompts cannot place shapes ("% heights are ignored", L-78); L-32 wants one hard shape per panel inside the 22.2 / 33.3 / 66.7 / 77.8 % edges.
- **Resolution.** Flow exports 1080p; the wall is 7488x2880 (×2.7 on the front strip, soft; PIPELINE §2).
- **Frame rate.** Veo is 24 fps; the show composition is 30 fps (show.json playback.fps = 30, user 15 Oct). A TD render can be 30 fps natively.
- **Exact brand colour and recolour.** Prompts carry hex values only approximately; the E pack is explicitly "recolourable" (RUNTIME §6).
- **Cost.** Every video job needs a go-ahead and credits; a TD render spends none.

What TD does badly (honest limits from the same files):

- The user rejected "generic abstract CGI" (prism-v1, L-02) and stopped the procedural batch-1 stills (PHASES.md "Batch 1 parked"; `production/kit.py` is "look-dev scaffolding only", README.md).
- The approved house looks are "soft, glowing, organic light" (D1, D3, A03, F01, H01, G02, teases); denied ones are "hard/graphic (shards, blades, neon rings, laser rays, caustic net, chroma band)" (STATES.md 15 Oct "Read of the audit"). Painterly textures (ajrak, jharoka, silk, curtains) are Nano Banana strengths.
- "Liquid Spectrum family was rejected (D4: 'i dont like these')" and no caustics/liquid chrome for NN and AH (`assets/_shared/show-visuals/research/AS_directions.md` §2 row 14). "Brand-colour spectrum looks" are therefore risky; no literal rainbow (PIPELINE §3 Banned; L-16).
- Names, words, Urdu, logos: HyperFrames owns these (`hyperframes/INVENTORY.md` O1 to O19, 30 finals premultiplied and confirmed in Arena 16 Oct). The countdown numerals are a StageLab plugin (INVENTORY: "O11 countdown → StageLab plugin"). **Not a TD job.**
- Info and emergency screens are plain posters (BRIEF guardrail 5; memory `info-posters-plain`).

Where the two lists meet (procedural, soft light, time-critical, face-aware, long): countdown build, long seamless beds,
sweeps and stings across the five fronts, calm low-motion beds (TALK/HOST/hold), the generic E loops, the finale
escalation, and a live audio layer. Details in §5.

---

## 2. R02 geometry (`prismfest26-show/show.json` stage.faces; `STAGE.md`; `production/mapping.py`)

Stage: 9 faces, all 50 ft high, 76.8 px/ft native, 9984x3840 native (130 x 50 ft unfolded). **PF26 renders at 75%:
7488x2880** (Profile A, user 14 Oct; "never native", `CLAUDE.md` in prismfest26-show). Order left to right
`L1 L2 L3 L4 C R4 R3 R2 R1`. Pixel rectangles are top-left origin, half-open, y = 0, no gutters.

| Face | Role | W ft | 75% px (W x H) | Atlas x0 | x1 (excl.) | Native px |
|---|---|---|---|---|---|---|
| L1 | outer front | 20 | 1152 x 2880 | 0 | 1152 | 1536 x 3840 |
| L2 | outer return | 10 | 576 x 2880 | 1152 | 1728 | 768 x 3840 |
| L3 | inner front | 10 | 576 x 2880 | 1728 | 2304 | 768 x 3840 |
| L4 | inner return | 10 | 576 x 2880 | 2304 | 2880 | 768 x 3840 |
| **C** | centre front | 30 | 1728 x 2880 | 2880 | 4608 | 2304 x 3840 |
| R4 | inner return | 10 | 576 x 2880 | 4608 | 5184 | 768 x 3840 |
| R3 | inner front | 10 | 576 x 2880 | 5184 | 5760 | 768 x 3840 |
| R2 | outer return | 10 | 576 x 2880 | 5760 | 6336 | 768 x 3840 |
| R1 | outer front | 20 | 1152 x 2880 | 6336 | 7488 | 1536 x 3840 |

Sum check: 1152+576+576+576+1728+576+576+576+1152 = 7488. The five FRONT faces (L1 L3 C R3 R1) form a 90 x 50 ft
picture, **5184 x 2880 (1.8:1)**, almost 16:9; the four RETURNS turn 90 degrees inward and are almost invisible from the centre
crowd (L-23, PIPELINE §7b).

**Seams.** Atlas edges at x = 1152, 1728, 2304, 2880, 4608, 5184, 5760, 6336. In the 5184-wide front strip the face
edges sit at x = 1152, 1728, 3456, 4032 = **22.2 / 33.3 / 66.7 / 77.8 %** of the width (STATES.md layout rule; BRIEF
in `assets/_shared/show-visuals/BRIEF.md`). Depth steps happen where fronts meet through a return: hard straight lines
kink there (L-29), hard-edged shapes must stay inside one front face (L-32), soft light may cross.

**Safe area** (STAGE.md): 10 % inset per edge; nothing critical across a 90-degree corner. At 75% that is (derived,
10 % of the face size; show.json gives the native values 154/1382 and 77/691/231/2073 x 384/3456): L1/R1 x 115 to 1037,
10 ft faces x 58 to 518, C x 173 to 1555, all faces y 288 to 2592. **Type on C lives at 15 to 75 % of the height**
(y 432 to 2160) because of the FOH canopy and raised hands (L-70, provisional).

**Zones** (`RUNTIME.md` §3, `STAGE.md` "Screen roles"; the research's Signage/Show/Wings model is
`concert-visuals-research/README.md` §7): C = Show/hero (names, story focus); L1/R1 = Wings (2:5 portrait IMAG with the
camera crop, covered by IMAG most of the night, so loops put interest in L3 / C / R3 = 22 to 78 %, BRIEF "The states per act");
L3/R3 + four returns = atmosphere (colour, light, depth; nothing critical). TAKEOVER is one image on all nine faces
with IMAG off.

**How the existing pipeline maps a 16:9 image (`production/mapping.py` LAYOUT, `fold()`).** Front strip = cover-fit to
5184x2880; each front face takes its slice by plan position; each return is `fold(front, bx, w)` where bx is the corner
column in front-strip coordinates (L2 bx=1152, L4 bx=1728, R4 bx=3456, R2 bx=4032, w=576): the return's first column
continues the face on its left, its last column meets the face on its right, smoothstep-crossfaded across the depth
(L-38: extruded bars were "stretching looks bad"). Caution in L-38: fold ghosts neighbours onto the return for hard-shape looks.

**Recommended TD layout (proposal, not tested):** build once a **plan-space "front strip" comp at 5184x2880** (x in feet
= -45 to +45, face edges as constants) and add a final stage that assembles the **7488x2880 atlas** exactly as `mapping.py`
does (copy the LAYOUT table and the fold formula so TD output and the viewer's audience-view simulation agree), with a
per-look switch for "returns authored" (explicit colour/light on L2/L4/R4/R2) versus "returns folded". Output is ONE
7488x2880 canvas per state, matching the decided "one clip per state" (PIPELINE §2). Per-face renders (C 1728x2880, L1/R1
1152x2880, strips 576x2880) are only needed for IMAG frames or alpha overlays; both are better handled by HyperFrames or
Arena. The shortcut of rendering a plain 16:9 and running `map_clip.py` works but loses the TD advantage (it re-crops 1:1.8
to 16:9 and Lanczos-scales to 1920x1080 first; `map_clip.py` refuses non-16:9 sources unless `--fit`).

Not recorded anywhere in the repo: a TD texture of 7488x2880 has never been created or timed
(grep for 7488/9984 in `td-port/` and `jazib-td-mcp/` docs: no hits). **Open for the lead.**

---

## 3. Delivery path for a TD-made clip

### 3.1 Which step it enters

Source: `prismfest26-show/production/SYSTEM.md` §1, `PIPELINE.md` §5 to §7, `assets/README.md`, `CLAUDE.md` (prismfest26-show).

A TD clip skips Flow, the 1K still and the 3-clip assembly. It enters at the **video** step, already at 7488x2880:

1. **Where:** `python3 production/assets_where.py <ASSET> --step video` prints the row's `To Review/Video` folder (and creates
   it). Write there. (Not run by me.)
2. **Names:** every file starts with the look's viewer ID followed by `_`, `.` or `-`. Existing habit for clip looks:
   `<still ID>v<N>` + `m` (`C-NN-1v4b1m`); house looks are `F01c1`, `F02c1` style. For a TD look I suggest `<ASSET>t<n>`
   (for example `A03t1`, `F05t1`) or the pack pattern `L-AH-33-1`, `E-xx-01` (**convention suggestion, unverified**).
   Master `<ID>_7488x2880_prores.mov`; review MP4 for the viewer; frame grab/start frame as `--orig`
   (viewer_add: "Always pass it"). Extra files (preview, recipe `.toe/.tox`, frame grabs) share the prefix and the sorter files
   them in `Work/` as `<ID>__<name>`.
3. **Catalogue:** `mockup/viewer_add.py <ID> "<ID> <Artist full name or PRISM house> · <STATE> · <idea> #n" <review mp4>
   --orig <frame> --group "…" --note "…"`. A clip is `video` by itself. The look's ID must resolve to a show asset in
   `mockup/viewer/app/showplan.js` ASSETS (memory `catalog-every-look`). **Gotcha:** `patterns()` in `viewer/app/catalog.js`
   (line 9) gives asset "E" only the exact ID `E` (no trailing digit, so no `E*` wildcard), so E-pack looks need an
   `E: { looks: ["E-*"] }` entry in showplan.js first (lead/viewer edit, not mine).
4. **Verdict:** the user decides in the PF26 Show Suite app; agents read with `viewer_audit.py` (`--since-seq 331`), never write.
5. **Master:** after approval, ProRes 422 HQ master recorded with `viewer_add.py <ID> --master <ProRes>` ("To master" step).
   Existing masters use `prores_ks -profile:v 3 -vendor apl0 yuv422p10le`, tagged bt709 / tv range
   (`map_clip.py` lines 121 to 123).
6. **DXV3:** Resolume Alley (installed `/Applications/Resolume Alley`), saved NEXT TO the ProRes in
   `Mastering/<row>/Video/` as `<ID>_…_dxv3.mov` BEFORE Mark final (it becomes the look's file). Alley has a hidden
   command-line mode (hyperframes `LEARNINGS.md` H-36, per its STATUS).
7. **Mark final** (the user) moves the DXV3 to `Final Assets/<row>/Video/`, what the user hand-imports into Resolume.

Never copy a file into a second folder; never move files by hand; the sorter runs by itself after verdicts.

### 3.2 Format rules a TD render must meet

| Item | Rule | Source |
|---|---|---|
| Raster | 7488x2880 only; never native 9984x3840 | prismfest26-show `CLAUDE.md` Rules; PHASES rule 1 |
| fps | show composition 30 fps. Finished clips KEEP their source fps (don't pass `--fps`; user 16 Oct ~5 PM "Keep source fps"). A TD render at 30 fps is native, no 24-to-30 conform. Loops need an integer frame count | `show.json` playback; PIPELINE §5.4 |
| Codec | master ProRes 422 HQ (4444 for alpha); playback DXV3 (DXV3 with alpha for overlays) | RUNTIME §7, PIPELINE §5 |
| Colour | Rec.709, tagged bt709, tv range; explicit BT.709 matrix on encode | PIPELINE §5; `show.json` colour "Rec.709" (status: proposed, RFI08) |
| Alpha | if a TD clip carries alpha it must be premultiplied and checked with Arena's blend | memory `overlay-alpha-premultiplied`; hyperframes H-34 |
| Length / loop | per RUNTIME §6 table; seamless loops built by design, not by crossfade (crossfade is the fallback, `loop_clip.py`, L-36); wall brightness/colour joins are not an issue in one render (no L-37) | RUNTIME §6 |
| Names | none baked in; overlays carry names (names whole, `names-words-intact`) | PIPELINE §2 |
| Logos | full-colour PRISM only, as supplied, never recoloured/glowed; logo is an overlay | memory `colorful-logos`; `prism-brand/CLAUDE.md` Hard rules |
| Brand | plum base `#3B132F` (official) / `#19041E` (campaign), orchid `#CA47E9`, pink `#FF447F`, gold `#FFB903` (gold is the only type accent); no full-white fields | `prism-brand/CLAUDE.md`; README §7 ref 05 |
| Flashing | screen content: at most 3 flashes/s over more than 25 % of the screen, no saturated-red flashing, no more than 5 high-contrast stripe pairs, no moire-prone fine patterns. (CREATIVE.md 15 Oct: full strobes are approved for the LIGHTING; screen content still avoids long full-frame red/white flashing.) TALK states: no flashing at all, nothing faster than about 8 s per cycle, 40 to 60 % brightness | `concert-visuals-research/README.md` §4 and §5; `host-states.md` rules 1 to 3 |
| Banding | grain: the wall assembly adds one grain layer (sigma 2.0 at half res, L-39) because Flow video is smoother than stills; a procedural render of smooth dark plum gradients will band on DXV3. DXV block compression behaviour is **unverified (from memory)**: test | LEARNINGS L-39 |
| Size | measured ProRes HQ at this raster: D1 1.449 GB / 144 frames = 10.1 MB per frame; C-NN-1v4a2m 2.833 GB / 312 frames = 9.1 MB per frame. At 30 fps: 60 s = 1800 frames is about 16 to 18 GB; 5 min (9000 frames) about 82 to 91 GB; 10 min about 163 to 181 GB. Disk free 1.2 TB (df). DXV3 size and 7488x2880 DXV3 playback in Arena 7.23.2 are **not yet tested** (STATUS open item 14, PIPELINE §8) | measured |

### 3.3 TD-side facts that gate this (not my topic, flagged)

- **Licence:** Non-Commercial TD is limited to 1280x1280 images; Commercial and Pro have no cap
  (<https://derivative.ca/UserGuide/TouchDesigner_Non-Commercial>, via web search summary, current page not opened). The
  installed `TouchDesigner.app` is recorded as Non-Commercial; the licence of `TouchDesigner 2.app` (2025.31550, the one
  in use) is **not recorded anywhere in the repo** (`td-port/LEARNINGS.md` line 89 only says the other app is NC). If 2.app is
  NC, a 7488x2880 render is impossible without a licence (a spend: needs the user).
- **Movie File Out TOP** on macOS lists ProRes, Hap, H.264; DXV is not listed; H.264/H.265/AV1 encoding needs Commercial or
  Pro (<https://docs.derivative.ca/Movie_File_Out_TOP>, revision oldid 38341, last edited 16 July 2026). So a TD render is
  ProRes (or Hap) or an image sequence, then ffmpeg/Alley. Whether ProRes writes at 7488x2880 under Rosetta is **unverified**.
- Existing TD facts: TD 2 is the Intel build under Rosetta and crashed about 9 times during the port tests (`td-port/LEARNINGS.md` "TD 2 crashes"); in the background it cooked at about 28 fps instead of 60 (line 262).

### 3.4 Do the user's rules bind a TD render? (source quoted)

| Rule | Source | Applies to TD? |
|---|---|---|
| "Make **only 3** results per round, put them on the stage, then **stop and wait for the user's verdict**" ("always only just make 3 than push to stage view and wait for my verdict"; "three different ideas x1") | memory `three-then-wait.md`; PIPELINE §3; prismfest26-show CLAUDE.md "Per round: 3 different ideas × 1 … then wait" | **Yes in spirit.** Written for generation, but the stated reason (verdicts change what comes next, bulk is wasted) applies to renders too. Recommend 3 TD looks per round, 3 different ideas, then wait. |
| "Write generation prompts one by one … never in bulk"; "dont tell me the prompt - generate and show on the stage" | memory `prompts-one-by-one.md` | No prompt exists for TD, but the analogue holds: one look recipe at a time, shown as a result, not as a plan. Don't build a bulk set of recipes. |
| "every look tied to a show asset and named `<ID> <Artist full name> · <STATE> · <idea> #n`" | memory `catalog-every-look.md` | **Yes**, plus the showplan.js entry (E gotcha above). |
| "once a motif is approved … never re-make the same idea in a new colour or angle" ("ur recreating same stuff again and again") | memory `no-repeat-motifs.md` | **Yes, and sharply:** a parametric TD network invites recolour-and-resubmit. Per-act loops must be new subjects. The E pack is the one place the plan explicitly wants a recolourable family (RUNTIME §6), but still one idea per round. |
| "every generated result (stills AND clips), including ones I think failed, goes into the viewer; my doubts go in --note" | memory `always-show-before-asking.md` | **Yes.** Every TD render, even ones I doubt, goes into the viewer first. |
| "Approved goes forward"; "an approved clip always wins" | memory `approved-goes-forward.md` | Yes for the board logic. |
| "Names and words stay whole"; "full-colour logos" | `names-words-intact.md`, `colorful-logos.md` | Yes; sidestepped by keeping text and logos out of TD renders (overlays). |
| 75 % (7488x2880) only; video-first; "ideally nothing will be a static png" | `pf26-production-rules.md`; PHASES rules 1, 2 | **Yes** to 7488x2880. Video-first suits TD. |
| "Every video job needs the user's go-ahead (16 Oct): read Flow's credit quote, ask with the figure, then pass `max_credits`"; "a scoped 'generate without approval' never covers video spend" | prismfest26-show CLAUDE.md "Rules"; PIPELINE §4; `pf26-production-rules.md` | **The credit gate itself does not apply (a TD render spends no credits).** The text is about Flow's credits. But three things still need the user: (1) the PHASES rule that the user "approves every still's art style before it goes to video" has no still stage for TD, so the clip itself is the first thing reviewed; (2) any licence purchase/install (CLAUDE.md "Installs … still need the user's go-ahead"); (3) any Arena / Syphon operation (same sentence) . Nothing in the docs says TD renders may be started without asking either; I recommend asking once, as one line, before the first TD look ("build only what's asked", memory `build-only-what-asked.md`). |
| "One phase at a time" (PHASES): current phase 4 (artist packs) and the C·1 posters; house motion was Phase 3 (17 to 18 Oct) | PHASES.md | A house bed (A03, F05) is a Phase 3 asset; a gate needs the user. |
| "Research stays in the folder"; temp emptied | `research-stays-in-folder.md` | Yes: TD recipes and renders go into the asset folder, not temp. |
| "Bugs go in LEARNINGS" | `bugs-go-in-learnings.md`; production/LEARNINGS.md | Yes; a TD finding about PF26 gets an `L-87+` entry. |
| MOU / fee | memory `mou-parked.md` | Not raised here. |

---

## 4. Live TD versus pre-rendered clips in Arena

What the docs say:

- `RUNTIME.md` §1: "Resolume at FOH with TouchDesigner and camera inputs; DXV3, 30 fps". §8 layer 6 **FX: "TouchDesigner via Syphon + live FX"**, with "reactive loss → base loop keeps running"; layer 1 BASE holds the full-wall loops/beds, layers 3 and 4 IMAG-L/R camera. SAFETY (layer 8) is a separate deck on dedicated MIDI buttons.
- `STAGE.md`: "TouchDesigner via an inter-app route"; commissioning order ends "recovery (camera loss → artwork; reactive loss → stable loop; timecode loss → hold)".
- `CREATIVE.md` "Reactivity": kick/sub → scale, depth, breathing; snare → cuts; highs → particles; critical reveals and names are manual or timecoded, never audio analysis alone; when reactive input drops, fall back to a stable loop. `STAGE.md`: "audio analysis only modulates texture".
- `host-states.md`: in TALK, reactivity is OFF.
- MOU scope (`SHOW.md`): live playback through "Resolume or TouchDesigner", on-screen live FX and live camera FX are in Jazib's scope; he also supplies "a redundant backup playback system". RUNTIME §8: "a second machine runs a mirror of the composition, switched at FOH. Test the switch on Friday."
- `show.json` playback.app: "Resolume (+TouchDesigner)".

What has been tested (SYSTEM.md §3, §6; LEARNINGS L-54 to L-58; STATUS 16 Oct): the viewer's live bridge reads Syphon and NDI.
Syphon from a *local test server* ran 26.7 fps, 33 ms; **"Syphon from Resolume itself not yet"**; NDI of Arena's composition
(4538x1744) plays at 27 to 28 fps; NDI latency not measured. That is the viewer pulling from Arena, not Arena pulling TD.
Nothing in the repo measures TD to Arena (Syphon) at any size, or Arena DXV3 playback at 7488x2880.

Risk view (my assessment, evidence marked):

1. **Pre-rendered is the show's baseline and the only mirror-safe path.** A clip file is identical on the primary and the backup machine; a live TD layer exists only where TD runs. If the backup is switched in, a live TD layer is gone unless TD runs there too (the docs only say the mirror is "of the composition"). Treat TD live as garnish, never as a state's only content.
2. **TD stability.** TD 2 is Intel-under-Rosetta, crashed repeatedly in the port work (td-port LEARNINGS "TD 2 crashes", cause for the rebuild crash still "unexplained"); a crashed TD pops a macOS dialog. A live layer needs a crash-safe fallback = Arena layer 6 showing nothing and BASE continuing (the docs' own "reactive loss → base loop keeps running"). Test: kill TD with the layer visible.
3. **Background cooking.** td-port measured about 28 fps instead of 60 when TD was in the background. If TD sits behind Arena on the FOH Mac, it may under-cook. Unmeasured for this use.
4. **GPU contention** on one laptop (Arena at 7488x2880 DXV3 plus TD plus cameras): unmeasured; the Arena 7488x2880 DXV3 playback test (PIPELINE §8) has not been done.
5. **Syphon between a Rosetta process and Arena:** not tested; Arena's Syphon source behaviour in 7.23.2 and frame orientation (L-54: Syphon frames read bottom-up in the viewer's bridge; that is the viewer's reader, not Arena) are **unverified**. Any Arena/Syphon test needs the user's go-ahead (CLAUDE.md).
6. **Audio input** to TD (FOH feed, device, latency) is not defined anywhere; td-port open question "Which audio device for SPECTRUM-03?" is still unanswered.
7. **Content rules for live:** must obey the same flash limits; live code can't be pre-checked frame by frame the way a render can.

Conclusion for planning: do the render-to-clip work first (no live risk, no credits, mirror-safe). A live TD layer is a late, optional extra, to be tested on Friday 23 Oct with the backup machine, default OFF.

What exists in `td-port/` (a separate project; nothing shared or imported, just noting): 33 effects ported from the StageLab FFGL set;
**18 of 33 have passed in TD 2 (2025.31550) as of 2026-10-16** (stutter, shatter, ascii, spectrum, slice_ripple, slice_spread,
slice_tile, slice_tiler, slice_trim, beam_fx, camera_slice_reveal, slice_chase, slice_color, slice_id, slice_life, hit_slice,
slit_volume, slice_delay), 19 saved `.tox` in the inventory (RGBSplit pilot, Echo, Halftone, Glitch, Hit, Color Warp, etc.);
the rest including all camera effects (person_key, depth_fx, tracker, crowd_energy, flow_fx), light_shafts, ink_flow,
prism_glass, elastic_lens, video_relief and logo_build were not yet run in TD (td-port `STATUS.md`). These are **effects that
process an input** (and slice-aware tools), not content generators, and none was built for 7488x2880.

---

## 5. Ranked TD jobs for the 8 days left (proposals; today Fri 16 Oct, show Sat 24 Oct)

Ranking logic: value to the night, can't be done well with Flow, soft-light genre (what the user approves), buildable and
reviewable in the viewer, mirror-safe (pre-rendered). Each is one asset family, 3-per-round, no repeats.

| # | Job | State / row | Why TD rather than Flow | Deliverable spec |
|---|---|---|---|---|
| 1 | **Countdown build bed** | A03 COUNTDOWN (house). Pairs with A04a/A04b stings and the StageLab/HyperFrames numerals | 5 min is impossible from 8 s clips (+7 s extends, L-84 drift). A deterministic timeline lands on an exact frame; "light gathers toward C, C kept dark for numerals" (STATES.md A03; approved still exists) is a face-aware layout | 7488x2880, 30 fps, 300.0 s = 9000 frames, ProRes 422 HQ (about 82 to 91 GB, measured rate), DXV3 for Arena. Ends on the frame where A04 starts (match palette/brightness). C's middle band (15 to 75 %) calm, no numerals/text, no flashes. Single render, one look per round |
| 2 | **PRISM Portal bed + holds** | F05 (D3 portals, approved), F07/H02 hold, C·3 TALK beds (NN denied twice, user answer pending), B02 host bed | Seamless 60 s to 120 s loops, designed to loop; hard shapes placed inside one front face each (L-32), authored returns (avoid fold ghosting, L-38); calm low-motion by design (8 s+ cycles, 40 to 60 % brightness) | 7488x2880, 30 fps; F05 60 s = 1800 frames (about 16 to 18 GB ProRes), TALK/B02 120 s = 3600 frames. Exact loop (frame N+1 = frame 1). Tint per act via palette parameter (NN indigo/amber, AH lilac/cyan, HR navy/teal/magenta/lime, MZ charcoal/ember/silver, AZ violet/gold/midnight: `showplan.js` ARTISTS). No repeating a denied B02/TALK motif |
| 3 | **Wall-wide stings** | F01 Prism Bloom (4 approved stills), F03 Light-Slice Wipe (F03b), F04 Signal Reset (F04c), A04a/A04b show-open, and the open **F02 Facet Shatter** (no look) | Per-face timing across the five fronts (a "slice" per front is literally the geometry), one render so no L-37 drift, exact length; Flow can't place a blade per face. Risk: hard graphics were denied (blades, shards, neon rings), so keep to soft glow and let F03 be light, not blades | 7488x2880, 30 fps, 6 to 12 s (180 to 360 frames), start and end on plum so they butt into beds. Option: wipe as an alpha/luma-matte layer over BASE, premultiplied alpha (DXV3 with alpha). Flash-limit check done in-render. 3 ideas then wait |
| 4 | **E generic loop pack, one family at a time** | E (24 loops = 8 families x slow/med/high; none exists). Start with the families that are not liquid: Particle Weather, Organic Pulse, Open-Sky Release (AS_directions §2: Liquid Spectrum rejected) | Recolourable and tempo-locked by design: one network, palette per act, three energies; seamless on a bar grid; unlimited length; no credits. 32 bars at 120 BPM is 64 s = 1920 frames (arithmetic; real BPMs are an open organiser item, STATUS 19) | 7488x2880, 30 fps, 16/32-bar loops, 20 to 64 s; interest in L3 / C / R3 (22 to 78 %), L1/R1 calm because IMAG covers them (BRIEF). Needs the `E-*` entry in showplan.js (see §3.1) |
| 5 | **Finale escalation + end bed** | G01 CLOSE finale (G01c2, d1, d2 approved stills), G02 end card bed | 30 to 60 s one-shot build to the biggest moment then settle into G02 (warm plum/gold, C clear for "THANK YOU KARACHI." from HyperFrames O13); Veo's 8 s can't hold an escalation; flash profile controllable and checkable. Spectrum stays inside orchid to pink to amber, no rainbow | 7488x2880, 30 fps, G01 30 to 60 s (900 to 1800 frames), G02 loop 60 s. Brightest hit of the night but under §4 limits; the last frame equals G02's first |
| 6 | **Artist TAKEOVER hits** (one image across all nine faces, IMAG off) | C·4 for AZ (headliner), then MZ/HR/AH; NN's C-NN-4a-2 still is approved | Wall-wide energy build with an exact 15 to 20 s curve plus loop tail, lands on the drop; the only state that uses all nine faces as one canvas | 7488x2880, 30 fps, 15 to 20 s plus loop tail; act palette; red only as glow (AS_directions MZ ember row); needs the act's world approved first (no motif repeat) |
| 7 | **Long beds that repeat today** | A01/A02 DOORS: D1 is 6 s, needs 10 min / 5 min | A long-period (for example 120 s) drift in the same grade as D1 instead of a 6 s loop repeating about 100 times | Only if the user finds the repeat visible; D1 is approved and mastering. Same spec as job 2. Lowest priority |
| 8 | **Live layer on Arena layer 6** (audio-reactive glow/particles, optional camera FX on L1/R1 IMAG) | any LIVE state; default OFF; TALK = off | The one thing Flow can never do. Highest risk (§4) and needs Arena/Syphon go-ahead, an audio feed, and the backup system's parity | Syphon out at half the wall at most (size unmeasured: test); base loop beneath must stand alone; kill key; tested Friday 23 Oct. Do last, or not at all |

Not TD jobs: names, kickers, "THANK YOU", host card, logos, Urdu (HyperFrames, 30 finals exist); countdown numerals
(StageLab plugin); info/emergency posters (plain posters); painterly artist loops and story key frames (Nano Banana is the
user's accepted genre); IMAG frames C·2 (HyperFrames O6 name tag).

Suggested order inside the week (approximate; PHASES.md windows): job 1 and job 2 first (Phase 3 house motion, 17 to 18 Oct,
and both are long-form gaps with no Flow answer), then job 3 and 5, then job 4 as the 19 to 21 Oct loop-library window
opens; job 6 after each act's world is approved. One cheap first step before any build: confirm the TD licence and a
7488x2880 ProRes write (see Open questions).

---

## Open questions for the lead

1. **TD licence of `TouchDesigner 2.app` (2025.31550):** Commercial/Pro or Non-Commercial? NC caps images at 1280x1280, so a 7488x2880 render would be impossible; a licence is a spend and needs the user. Nothing in the repo records it.
2. **Can TD 2.app create and record a 7488x2880 texture at all** (memory, Movie File Out ProRes under Rosetta, offline-render speed)? Nobody has tried; no number exists. A throwaway probe (agent A/B's remit?) answers it before any job is promised.
3. **Does the user want TD-made clips in the show at all?** The docs frame TD as a live FX layer (RUNTIME §8 layer 6) and the old stance is "organiser-supplied content". Ask once, in one line, per `build-only-what-asked`. This also decides whether the 3-per-round rule is applied to renders (I recommend yes).
4. **Look IDs and showplan.js:** approve a TD naming convention (`<ASSET>t<n>`?) and add `E: looks: ["E-*"]` (the pack E ID pattern gap) before the first `viewer_add`.
5. **Review MP4 format for the viewer:** existing viewer clips are H.264 3744x1440 (probed in `viewer/media/`); `map_clip.py` writes a 2000x770 preview. Which should a TD look pass as SRC? And H.264 encoding in TD needs Commercial/Pro; otherwise ffmpeg from the ProRes.
6. **DXV3 banding and 7488x2880 DXV3 decode in Arena 7.23.2** are untested (STATUS item 14). A TD clip would be the natural first test file; needs the user's go-ahead for any Arena operation.
7. **Colour pipeline:** TD's working space to Rec.709 tv-range tagged ProRes. Who verifies the encode matches `map_clip.py`'s round-trip (a test colour round-trips exactly, PIPELINE §5)? Suggest a colour-patch test clip through the same path.
8. **Real tempos / song BPMs** (STATUS item 19) decide whether E loops lock to bars or to seconds; until then use seconds-based loops (60 s / 64 s).
9. **Live layer:** does the backup machine also run TD? What audio feed reaches the FOH Mac? These decide if job 8 exists.
10. **Spectrum risk:** the user rejected Liquid Spectrum (D4) and Spectrum Glass is still "keep/drop" (STATUS item 18). Should "brand-colour spectrum looks" be offered only as soft light inside the orchid to pink to amber range?
