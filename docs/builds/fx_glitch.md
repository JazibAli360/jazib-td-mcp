# fx_glitch: FX_glitch rack + 15 modules (smear pilot first; live in main, 26-27 Oct 2026, TD 2025.31550)

`/project1/lab/FX_glitch`. The digital-breakage COMP from `docs/research/FX0_effects_backlog.md` (Phase 0 pilot). It
is kept lean on purpose (user rule 26 Oct: "dont bloat stuff just for modularity - it should make sense"): **no
codegen, no registry, no field/trigger/lib kit.** Those get built only when 2+ real modules need them. Module looks
come from `docs/research/FX1_destruction_datamosh_glitch.md` DG-05 / DG-06.

In: `in1` TOP. Out: `out1` TOP. Test picture: `test_clip` (the stored 5 s webcam clip, filled to 1080x1920; it cooks
only while selected). `Input` = auto (in1 once it is wired) / live / test.

## Build / rack edits (td_exec)
```python
ns = dict(globals()); exec(open('<repo>/builders/fx_glitch.py').read(), ns)
ns['build']('/project1/lab')                          # rack + the 'smear1' row on first build; idempotent
ns['add']('/project1/lab/FX_glitch', 'smear')          # smear2, wired last (order = max + 1), zkit panel + presets
ns['remove']('/project1/lab/FX_glitch', 'smear2')      # re-routes first, then safe_destroys its 3 ops
ns['rewire'](op('/project1/lab/FX_glitch'))            # after editing `order` in the slots table
```
`enabled` and `mix` in `slots` work live (expressions); `order`, add and remove go through the builder. `rewire`
changes only connectors that differ and returns how many it changed.
Offline tests (chain order, wires): `python3 -I -m unittest discover -s test -p 'test_fx_glitch.py'` (5).

## Network
| Stage | Ops |
|---|---|
| Rack | `slots` table: `name module enabled order mix` (the only rack state) |
| 1 Input | `in1`, `test_clip` -> `img_src` (Switch) |
| 2 Slots | per instance: `<name>` (module COMP) -> `<name>_mix` (Cross, dry/wet) -> `<name>_slot` (Switch: 0 bypass, 1 module, 2 mix) |
| 3 Out | `panic` (Switch: 0 = chain, 1 = `img_src`) -> `out1` |

A slot is only that Switch + Cross around one module COMP. Bypass (enabled 0 or mix 0) selects the slot's input, so the
module is not pulled (with the network pane elsewhere: pane viewers pull it, T-111 (5)). Mix 1 skips the Cross.
**Panic** (`Rack` page) is a toggle, so a MIDI button can latch it: on = `img_src` straight to `out1` in the same frame,
no slot cooks. No limiter, no flash/luminance caps (user rule).

## Module `smear` (`builders/fx_glitch_smear.py`)
Inside each instance: `in1` -> `stamp` (1x1 cook clock) / `fb` (Feedback) -> `prev_src` (Switch) -> `fx` (one
compute GLSL pass, shader in its docked `fx_compute`) -> `out1`, + zkit `controls` / `controls_window`.

| Par (page Smear) | What |
|---|---|
| Amount | 0 = exact passthrough (the shader writes texelFetch of the input, format useinput), 1 = full |
| Mode | Smear max (bright pixels drip, DG-05), Smear min (dark pixels drag), Stretch band (one band repeated along the axis, the classic pixel stretch), Feedback drag (displace-feedback smear, DG-06) |
| Angle | drag direction, deg; 0 = down, 90 = right |
| Length | px (smear: up to 24 bilinear taps; feedback: drag speed) |
| Threshold | luma a pixel needs before it smears (feedback: how much change keeps the trail) |
| Decay | falloff along the smear / feedback persistence |
| Wobble | per-2 px column jitter of the length (feedback: direction noise) |
| Bandpos, Bandwidth | Stretch band position and width along the axis (0..1) |
| Seed | wobble hash seed |

zkit presets (seeded once into `controls/zk_presets`, the user's own slots are kept): 1 drip, 2 shadow, 3 stretch,
4 mosh. Feedback history goes stale while a slot is bypassed or panicked: `stamp` (x = now, y = previous cook) tells
the shader, and a gap > 0.25 s restarts from the current frame (T-111 (1)), so you don't get an old frame popping in.

## Verified live (26 Oct, 31550; main TD, PX + physarum lanes also cooking)
- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).
- **Exact passthrough** (`img_src` vs `out1`, numpy max abs diff, clip paused, each read 4 frames after the change in
  a separate exec): Amount 0 -> 0; slot enabled 0 -> 0; mix 0 -> 0; Panic on (Amount 1, drip) -> 0. Control: drip on
  -> max 0.78, mean 0.056, 24 % of pixels changed.
- **Smear numbers** (1080x1920): smear max (drip) mean diff 0.057, 26 % changed, luma only rises (min delta 0);
  smear min mean 0.076, 33 % changed, luma only falls (max delta 0); stretch band (pos 0.45, width 0.08): rows
  931-1055 untouched (the band; expected 903-1056 minus wobble), every row below the band identical down the column
  (std 6e-7); feedback (mosh): mean diff 0.06, 76 % changed while running; first frames after re-enable = the input
  (no stale history), then the trail builds up.
- **Add / remove re-wire once:** `add` smear2 -> 7 wires changed (6 slot wires + panic in0), a second `rewire` -> 0;
  reorder (smear2 first) -> 7, again 0; `remove` smear2 -> 1 wire (panic back to smear1_slot), again 0; its ops gone.
- **Presets:** zkit Recall 1-4 set Mode/Angle/Length/... exactly as stored.
- **Cost** (out1 pulled per frame, sum cpu+gpu of the COMP's TOPs cooked that frame, test clip excluded; 120 frames):
  smear max 2.44 ms median (fx GPU 1.77; was 4.5 ms GPU at 64 taps, now capped at 24), feedback 0.98 ms, stretch 0.55
  ms. Test clip decode 1.5-3.4 ms (test content only). **Project 60.1 fps** (300 frames wall clock, median 16.55 ms,
  0 frames > 20 ms, cookRate 60 untouched), smear max running.
- `td_errors` clean, `td_layout` ok (the module's fb -> prev_src Feedback reference shows as one back wire, T-85 (6)),
  checkpoint `output/checkpoints/FX_glitch/FX_glitch_20261026-191844.tox`, project saved (.226), COMP parked.
- Captures: `output/project1_lab_FX_glitch_out1_2026-10-26T14-18-22-530Z.png` (drip), network
  `output/window_TouchDesigner_2025.31550_Users_vyro_Docu_2026-10-26T14-18-27-069Z.png`.

## Module `pixelsort` (`builders/fx_glitch_pixelsort.py`, DG-04, 26 Oct, 31550)
A true sort (FX6 recipe), not a smear. `in1` -> `sort` (compute, `local_size 1024`, 2048 line elements per workgroup in
`Chunk`-sized blocks, manual dispatch `dispatchsizex` = groups from the `geom` DAT) -> map (rgba32float: xy = the source
pixel that lands here, zw = own pixel) -> `fx` (gathers the picture through the map, Amount mix) -> `out_sel` (Amount 0
= in1, the sort does not cook) -> `out1`. Key = interval start (11 bits) | quantised sort key (10) | element index
(11): one prefix-max scan finds interval starts, ties never flicker. `Mask TOP` sits on the Inputs page.

Pars: Direction (rows / columns / Angle, rotated work frame, nearest back), Angle, Sortby (luma hue sat R G B),
Threshby (luma hue sat Mask TOP), Lower/Upper, Invert, Reverse, Random reverse (per span), Min span (an extra suffix
scan, only when > 1), Max span (splits spans), Random breaks, Chunk 128-2048 (max span length; 2048 = whole line),
Chunk jitter (rotates the chunk grid per line, wrap with >= 1 pad element so line ends never join), Thresh anim Hz /
depth (moves the window), Quality half (every 2nd line sorts; its neighbour follows the same permutation: unsorted
pixels stay exact), Seed. Presets: 1 asendorf (V, 0.25-0.8, whole columns), 2 comet (bright spans, reversed, max 360),
3 hue rainbow (rows by hue where saturated, jitter), 4 shards (Angle 30, random reverse/breaks, half), 5 breathe
(animated window).

Verified (main TD, other lanes cooking): vs a numpy reference of the same segmented sort, V/1024: 28 of 2.07 M pixels
differ (threshold rounding edges), on scratch H/512 + Min 10 + Max 100 + reverse + red key: 0 differ; Angle preset two
reads 5 frames apart identical (no tie flicker). Amount 0, slot enabled 0, mix 0, Panic: max diff 0. Cost (median per
frame, sum cpu+gpu): asendorf 2.13 ms (sort 1.32 GPU), shards Angle half 3.17 ms (sort 2.2; full = 5.0 on scratch, so
the preset uses half); first version (3 scans, per-line chunk padding) was 8 ms Angle. Project 59.9 fps (td_watch,
clip playing). Capture `output/project1_lab_FX_glitch_pixelsort1_out1_2026-10-26T14-34-05-072Z.png`.

## Module `chroma` (`builders/fx_glitch_chroma.py`, DG-10, 26 Oct, 31550)
One compute pass (`inputextenduv hold`). Split: RGB (R at +1, G at Green position, B at -1), Prism ghosts (two
hue-tinted luma ghosts added, gain + hue), Spectral (3-16 taps along a wavelength ramp, weights normalised per channel).
Mode: Offset (Distance px along Angle), Radial (lens dispersion from Centre, Falloff), Angle (channels rotated by
Rotate deg around Centre). Per-channel blur (Blur R/G/B px, <= 8 taps along the split), Line jitter (per Line size
band, re-rolled Jitter rate times/s), Audio gain x Inputs-page `Audiochop` / `Audiochan` (e.g. `AC_audio/out_ctl`,
`low`): distance x (1 + gain x level). Presets: 1 tear, 2 lens, 3 prism, 4 twist, 5 bass hit (audio).
Verified: RGB offset 12 px: R = input R shifted 12 px, B shifted -12, G unchanged (max error 0 each); Amount 0, slot
enabled 0, mix 0: diff 0; audio factor read 1.79 at low 0.198, gain 4 (1.0 with no CHOP / wrong channel). Cost: spectral
16 taps radial 0.73 ms, RGB angle with 3 x 40 px blur + jitter 0.67 ms; 60 fps outside other lanes' save stalls.
Capture `output/project1_lab_FX_glitch_chroma1_out1_2026-10-26T14-37-48-147Z.png` (lens, after the dct/bits slots).

## Module `block` (`builders/fx_glitch_block.py`, DG-07, 26 Oct, 31550)
One compute pass `fx` + 1x1 `stamp` (now / previous cook / last burst / beat count) + `fb` (Freeze only). Grid of
Blocksize cells, 2-level quadtree split by Irregular; each cell re-rolls Rate times/s (Jitter = per-cell rate/phase), is
hit by Chance, then picks a mode by weight: Smear (one column/row over the cell; Smeardir), Repeat (Tile px sub-block
tiled), Offset (cell shows a place up to Shiftmax px away; Snap = whole-cell moves = tile scramble), Colour (channel
swap + Cb/Cr DC drift, Colourerr), Freeze (previous output). Slice = chance a cell row runs on to the line end (slice
loss). Beat page: Beat (edge > 0.5, bind a CHOP/MIDI to it) or Bpm metronome -> burst: Burstchance on top of Chance,
decaying over Burstdecay s, every cell re-rolled. Presets: 1 tv loss, 2 green macro, 3 stuck decoder, 4 slice drop, 5
beat burst (Bpm 120; set 0 and bind Beat for the show).
Verified (main TD, clip paused): Amount 0 diff 0; tv loss 15.5 % px changed; green macro 24.9 % changed (Chance 0.25),
luma moves 0.078 where rgb moves 0.52 (chroma error); slice drop 46 of 120 cell rows run to the right edge (Slice 0.35);
beat burst 10.4 % (slices only) -> 66.6 % right after a Beat edge (Burstchance 0.7). Cost 1.48 ms median (fx GPU 1.0),
project 60.0 fps (300 frames, pane on FX_glitch).

## Module `dct` (`builders/fx_glitch_dct.py`, DG-08, 26 Oct, 31550)
ONE compute pass, `local_size 16x16` = one workgroup per 16x16 macroblock (FX6 1d, shared memory + barriers): RGB ->
YCbCr (JFIF), chroma 4:2:0 (2x2 average, one 8x8 block, bilinear back inside the macroblock) or 4:4:4, orthonormal
DCT-II on Blocksize 4 / 8 / 16, IJG luma/chroma tables x Quality (JPEG 1-100) x Crush (x Chromaq for chroma),
damage (Cutoff = zero high frequencies, Dcdrift = block colour walk, Corrupt / Corruptamp = AC sign flips + noise per
block), IDCT, RGB. Generation = previous output mixed into the encoder input (8-bit, like a re-save); Gridshift moves
the grid each Rate tick (manual dispatch = ceil(res/16)+1). Presets: 1 jpeg 30, 2 blocky 5, 3 chroma rot, 4 mpeg2 mud,
5 generational.
Verified: vs a numpy JPEG reference of the same codec (scratch, clip paused): max 0.5 level at block 8 4:4:4 and 4:2:0
and block 16; block 4 0.5 level except 0.0015 % of px (round() ties, <= 5.5 levels). Amount 0 diff 0. PSNR vs input
(main, after the other slots): jpeg 30 35.2 dB, blocky 5 23.0, generational q25 34.5 -> 32.0 dB with Generation 0.9
(stable after 3.5 s). Cost 1.32 ms median (fx GPU 0.85).

## Module `bits` (`builders/fx_glitch_bits.py`, DG-09, 26 Oct, 31550)
One uint compute pass: Floatbits (float mantissa crush) -> Depth (per channel Bits R/G/B, RGB565, RGB332, 1-bit, grey)
with Dither (Bayer 4/8, hash; Ditheramt, Ditherscale px), in gamma or Linear light -> Planemode keep/drop Plane ->
Op (XOR / AND / OR with Mask, Maskspread rotates the mask per channel, Maskwalk re-hashes it per Rate tick; NOT,
Rotate, Reverse) -> Fliprate random flips of bits >= Flipmin. Presets: 1 4-bit arcade, 2 gameboy 2-bit, 3 xor
psychedelia, 4 speckle corrupt, 5 plane slice.
Verified (scratch, vs integer numpy): XOR 170 exact, keep plane 6 exact, reverse exact, 4-bit arcade = 16 levels
(all values multiples of 17), flips 5.01 % per channel at Fliprate 0.05 and only bits 6-7 at Flipmin 6. Amount 0
diff 0 (main). Cost 0.60 ms median (fx GPU 0.14).

## Module `mosaic` (`builders/fx_glitch_mosaic.py`, DG-20, 26 Oct, 31550)
`stats` (compute: rgb + luma^2, rgba16float, padded to a multiple of 128 px so each mip texel is one grid cell, T-116)
-> `fx` (`inputfiltertype mipmap`, textureLod per candidate cell from Maxblock halving down to Minblock; first cell with
luma std dev <= Detail wins = quadtree) + `stamp` (rebuild clock). Fill mean / centre pixel, Edges darken. Decay page:
Decay (per-cell threshold noise, Decayrate Hz), Grow (threshold per second since the last rebuild), Rebuild (edge > 0.5;
also first cook, re-enable after > 1 s, Autorebuild s), Fall (share of Maxblock cells dropping under Gravity px/s2;
holes Black / Source / Transparent). Presets: 1 quadtree, 2 decay loop, 3 crumble, 4 big pixels, 5 shimmer.
Verified: cell colour vs numpy cell mean (Detail 0.5, 64 px): max 0.003 (0.16 before the 128 padding); Amount 0 diff 0;
quadtree preset: 51 % of the area in 64 px cells, 72 % >= 32, 87 % >= 16, 94 % >= 8, 100 % >= 4 (Minblock 4), PSNR
30.2 dB; crumble 20.5 % holes 0.6 s after a rebuild. Cost 0.89 ms median (fx 0.30 + stats 0.27 GPU).

All four on at once with the other lanes' chroma + mosh slots on and the pane on FX_glitch: 57.3 fps (300 frames,
14 > 20 ms); each alone held 60. They are left with slot enabled 0. Captures (network):
`output/fxg_block_net.png`, `output/fxg_dct_bits_net.png`, `output/fxg_mosaic_net.png`.

## Module `mosh` (`builders/fx_glitch_mosh.py`, DG-01 live datamosh, 26 Oct, 31550)
`src` (live in1 / offline `tools/mosh.py` clip / blend) -> `stamp` (3x1 in-place clock + I-frame triggers) -> `lum`
(luma at Estres, in place: r now, g previous cook) -> `mv` (8x8 SAD block match +-Range, one workgroup per block,
shared memory, FX6 3a; manual dispatch = block count; in place so Bloom can latch the field) -> `upd` (state S,
rgba16float, Feedback `sfb`: S(p) = S_prev(p + mv) + Residual (cur - cprev(p + mv)), Decay leak, block / global
refresh to cur) -> `fx` (mix in1 / S, View mosh / vectors / match error) -> `out_sel` (Amount 0 = in1, engine not pulled).
Pars: Mode mosh / bloom (latched MVs x Bloomgain, refresh re-latches) / hit (trigger: bloom for Holdtime, then an
I-frame); Gain, Minmag, Residual, Decay, Blockwarp (hard blocks -> fluid), Subpel; Refresh pulse, Holdauto, Randomrate
(/s), Period (s), Beatevery (+ Beatchop / Beatchan on the Source page: rising edges, every Nth), Blockrefresh
(per-block intra refresh / frame); Estres full / half (default, 16 px macroblocks) / quarter, Range (<= 16), Penalty.
Presets: 1 drag, 2 melt, 3 bloom, 4 hit, 5 blocks. Engine shared with `moshcut` (its only other user).
Verified (scratch first, then main): estimator = numpy brute-force SAD (+ penalty) on 40/40 random blocks of a moving
noise (uniform shift found on 99.5 % of blocks); after one clean motion step (separate execs) 760/760 sampled 16 px
blocks of S moved bit-exactly by the vector; bloom with a static source moved S 4 px per cook (100 % of pixels = S0
rolled by 36 px after 18 cooks); refresh S = cur (16F rounding 1.5e-4). Main: Amount 0 max diff 0, slot bypass 0;
mosh clip source, 150 frames after a refresh: 18.6 % of pixels drifted > 4/255, 19 % of blocks moving, max |mv| 11 px.
Cost 1.66 ms median (GPU 1.20, max 5.3) over 120 pulled frames; mv 0.34, upd 0.33, fx 0.17, cprev 0.11. Project
real rate ~43 cooks/s at the time with 5 other lanes' modules on (not a fair fps number; td_watch 59.8 absTime fps).
Readbacks re-cook in-place state ops (T-117): measure state in separate execs after a change.

## Module `moshcut` (`builders/fx_glitch_moshcut.py`, DG-02 A -> B mosh transition, 26 Oct, 31550)
A = in1, B = `b_test` (media/demo testsrc2 clip) or any TOP (Bsource / Btop), fitted to A. The mosh engine runs on B;
S starts as A's frame when Progress leaves 0 (or after any > 0.25 s gap), B's motion drags it, B's residual paints
B's edges, blocks refresh to B in Order (noise / top-down / bottom-up / radial from Centerx/y / luma) once Progress
passes Melt; Progress 1 = B exactly (`out_sel` 2), 0 = A exactly (`out_sel` 0, nothing cooks). Drive: Progress slider
(MIDI / cue) or Go pulse + Duration. Cutmode hard / soft (fluid, sub-pixel) / bloom (field latched after 2 cooks).
Presets: 1 drop cut, 2 slow melt, 3 radial, 4 bloom wipe. Verified: Progress 0 diff 0 vs A and 1 diff 0 vs B (scratch
and main); Progress 0.3 (< Melt): out vs A 0.063, vs B 0.47; 0.65: 49 % of 16 px blocks exactly B (expected 46 %);
Go + Duration 1 s ends on B. Cost 2.13 ms median at Progress 0.5 (p90 3.85, test clip excluded); the b_test mp4
decode is 8.4 ms per cook (test content only; use a real B source live). Both slots left enabled 0.

## Modules `timedisplace` / `timeshuffle` / `feedbackkill` (DG-13 / DG-12 / DG-21, 26 Oct, 31550)
Docs + live results: `fx_glitch_timedisplace.md`, `fx_glitch_timeshuffle.md`, `fx_glitch_feedbackkill.md`. The two
time modules share `builders/fx_time_ring.py` (Texture 3D ring -> Time Machine, compute map). Live fix T-122: the map
writes `m = 1 - (offset + 1) / Depth` (the Time Machine reads `(1 - m) * Depth - 1` slices); after it, offsets are
exact whole cooks. Amount 0 / bypass / mix 0 diff 0 for all three. Cost 1.09 / 0.94 / 0.80 ms median; all three on:
59.9 fps. Slots left enabled 0.

## Module `slash` (`builders/fx_glitch_slash.py`, DG-27 slash cuts / parted image, FX0 row 74)
`in1` -> `stamp` (1x1 in place: now, previous cook, last hit time, 2 x hit count + edge bit) -> `fx` (one compute pass,
`inputextenduv hold`) -> `out1`. Mirror: `builders/fx_glitch_slash_logic.py` (`reference`, `regions`, `cuts`,
`compare`; same lowbias32 hash). Tests: `test/test_fx_glitch_slash.py` (19, glslc of fx + stamp).

Up to 8 cuts (Count; shader loop max 8). Cut k parts its two sides by Gap px across and Slide px along the cut (Random
slide direction per cut flips the sign). Cuts apply one after another, so the shader inverts them exactly, last cut
first: a pixel comes from the + side at q - off when that point is on the + side, else from the - side at q + off,
else it is in the gap. Placement: Random (centre = Point + hash x Spread x frame, angle = Angle +- Anglejitter),
Radial (all through the Point, Angle + k x 180/Count), Parallel (spread across the frame along the normal). Jag =
piecewise-linear hashed offsets (Jagsize px segments) = a torn/jagged cut. Drive: Manual (Open 0..1) or Hit (Hit edge
> 0.5 from a CHOP/MIDI, or Auto every s): per cut Attack / Hold / Release (0 = stays open), Stagger s per cut; every hit
re-rolls the random cuts (count in the seed). Look: Back black / dimmed picture (Backdim) / transparent; edge Glow
(Glowwidth px, decays from the edge, scales with open) and Sparks (hashed dots in the gap, re-rolled 30x/s) in the Glow
colour (Glowr/g/b); Pointu/v. Parts moving in from outside the frame show Back.
Presets: 1 katana (one cut, Auto 2 s), 2 star split (4 radial), 3 blinds (6 parallel, dimmed back), 4 jagged tear
(5 random jagged, sparks), 5 manual part (2 vertical cuts, Open).
Cost estimate: <= 8 cuts x 2 side tests per pixel + 1 bilinear tap: ~0.3-0.6 ms at 1080x1920.

### LIVE CHECKS (slash)
1. Builds clean (`td_errors` none), `fx` + `stamp` compile.
2. Exact passthrough: Amount 0, slot enabled 0, mix 0 -> max diff **0** vs img_src (clip paused).
3. Parity (clip paused, Sparks 0, Glow 0): Drive manual, Open 1, Placement radial, Count 1, Angle 0, Anglejitter 0,
   Gap 20, Slide 8 (integer offsets) -> `compare(out1, reference(in1, pars, cnt=count))`: max <= 2/255; then preset
   4 jagged tear in manual (Open 1, Sparks 0) -> over-tol share < 0.5 % (bilinear + float32 edge pixels). Count from
   the stamp texel (w // 2, read-only exec).
4. Envelope: Drive hit, Auto 0, Hit 0 -> 1 -> picture parts within Attack, closes after Hold + Release (diff -> 0).
5. Presets 1-5 recall; cost per preset <= ~3 ms (target ~0.5); project fps.

### Verified live (slash: 26 Oct, 31550; b3 then main)
- b3 (rack built from the builder with only the new slots; clip paused on a real frame, img mean 0.466, T-157 (3)):
  Amount 0 / slot enabled 0 / mix 0 / Panic -> max diff **0**. Parity: radial, 1 cut, Angle 0, Gap 20, Slide 8 ->
  max **0.0** (bit-exact); 5 random jagged cuts (Jag 18) + glow -> 1 pixel of 2.07 M over 2/255, mean 0.001.
  Envelope (Drive hit, Auto 0): 0 % parted before the Hit edge, 94 % at +0.3 s, 0 % after Hold + Release.
- Presets 1-5 recall exactly (full state since 667072c); each parts the picture (75-99 % of pixels; jagged tear
  cycles open/closed with Auto 2 s). Cost (median per frame, own TOPs, In TOP excluded, 120 frames): katana 0.74,
  star split 0.91, blinds 1.05, jagged tear 1.30, manual part 0.87 ms. Capture
  `output/project1_lab_FX_glitch_slash1_out1_2026-10-26T18-43-13-113Z.png`.
- **Main** (JazibTD_home.466): added by builder as slot `slash1` (order 13, enabled 0); module parity again max 0.0;
  td_errors none; pars back to defaults; FX_glitch parked.

## Module `ghost` (`builders/fx_glitch_ghost.py`, FX4 D12 frame difference + plate subtract, FX0 row 77)
`in1` -> `stamp` (1x1: now, previous cook, last plate capture) -> `state` (ONE compute pass, 4 x rgba16float colour
buffers in place: b0 out, b1 previous frame, b2 trail rgb + mask, b3 plate; created with that layout before its first
cook, T-151 (2)) -> `out_sel` (Amount 0 = in1, the state does not cook) -> `out1`. Mirror:
`builders/fx_glitch_ghost_logic.py` (`step`, `f16`, `compare`). Tests: `test/test_fx_glitch_ghost.py` (14, glslc).

Mask = smoothstep(Threshold, Threshold + Softness, Gain x difference), difference = RGB max or luma, against the
previous frame (Ghost / Glow / Trails) or the plate (Plate). Modes: **Ghost** (only what moves; rest = Back),
**Glow** (Tint x Glowgain x decaying motion mask added), **Trails** (moving pixels leave copies decaying by Decay per
1/60 s over the Back), **Plate** (background subtract: the plate is grabbed on the first cook and on each Capture edge
> 0.5; what differs from it stays). View Mask = white-on-black mask (alpha 1) to feed another module's Mask TOP (e.g.
FX_destroy Masktop). A > 0.25 s gap between cooks restarts from the current frame (no stale flash); the plate is kept.
Presets: 1 ghost, 2 motion glow, 3 echo trails, 4 plate cutout (transparent back), 5 motion mask.
Cost estimate: one pass reading 3 and writing 4 16F buffers at 1080x1920: ~0.4-0.8 ms; memory 4 x 16.6 MB.

### LIVE CHECKS (ghost)
1. Builds clean; `state` has 4 colour buffers, readwrite, clearoutputs off.
2. Exact passthrough: Amount 0 / slot bypass / mix 0 -> **0**.
3. Static picture (clip paused), Mode ghost: out rgb = 0 everywhere (16F prev store noise < 5e-4 < Threshold).
4. Plate parity: Mode plate, clip paused at frame A, Capture edge; move the clip to frame B (separate exec), wait
   >= 4 frames; read in1 (B), the plate buffer (Render Select bufferindex 3, debug op removed in its own exec, T-119
   (5)) and out1 -> `step(B, {'prev': B, 'trail': 0, 'plate': plate})` out vs out1: max <= 2e-3 (16F).
5. Trails: clip playing, Mode trails, Decay 0.94: moving edges leave copies; pause -> trails fade (mean -> back).
6. Presets 1-5; cost <= ~3 ms; project fps.

### Verified live (ghost: 26 Oct, 31550; b3 then main)
- `state` built with 4 buffers / readwrite / clearoutputs off / rgba16float; td_errors none.
- Amount 0 / slot enabled 0 / mix 0 -> **0**. Static (clip paused), Mode ghost -> out rgb max **0.0** everywhere.
- Plate parity: plate captured at frame A (Capture edge), clip moved to frame B, plate read through a temporary
  Render Select (removed in its own exec): out1 vs `step(B, plate)` max **4.9e-4** (16F), 6.3 % of pixels kept.
- Trails (Decay 0.94, dimmed back): 1.3 % of pixels lit above the back while the clip plays (little motion in it);
  2.5 s after pausing: 0 % (fully decayed).
- Presets 1-5 set Mode / View / Diff / Threshold / Decay / Back as stored (full state, no inheritance: Decay back to 0.9
  after 3 -> 4). Cost 0.71-0.83 ms median per preset.
- **Main** (JazibTD_home.466): slot `ghost1` (order 14, enabled 0), td_errors none, state errors none.

`misc` (FX0 row 82 micro effects bank): `docs/builds/fx_glitch_misc.md` (live on b3 + main 26 Oct, slot `misc1`).

## Lane D extensions (27 Oct 2026, BUILD_PLAN_27OCT lane D; scratch first, then main by builder)
Rack: `_pars` now refreshes the names / labels of an existing Menu par (T-175: new entries reach old COMPs) and
`upgrade(c, name)` rebuilds an existing instance from its module file (new pars, shader text, panel knobs) and brings
its presets up to date (`preset_plan`: same-name rows replaced, free slots filled, user rows kept). Every touched
module's presets are full state now (page defaults + look; T-124 (1)). Live checks helper:
`builders/fx_glitch_checks.py` (`solo`, `pass_seq` / `pass_result`, `parity`, `presets`, `cost` / `cost_result`,
`fps`; changes and reads in separate scripts, T-74).

### smear mode `strips` (TC-25 pixel strips by coordinate remap)
Mode `Pixel strips` (menu index 4). The frame is cut into strips Stripwidth px wide across the drag direction (Angle,
0 = down), optionally bent by Curve px x sin(Curvefreq waves along the frame). Each strip (hash per strip index) gets a
segment length Length x (1 - Wobble x h1) and a phase h2 x Stripjitter (+ Speed px/s scroll); inside a segment every
pixel shows ONE source pixel (nearest, texelFetch): the segment start along the strip, and across it the strip's centre
line x Snap (1 = flat strips, 0 = stretched streaks). Decay < 1 fades back to the source along the segment, Threshold
gates by the sample's luma (bright-only strips), Density = share of strips on. Mirror: `fx_glitch_smear_logic.py`.
Presets 5 pixel strips, 6 liquid strips (curved, scrolling), 7 bright streaks. Est. 0.2-0.4 ms (one fetch per pixel).

LIVE CHECKS (strips): (1) compiles, td_errors none; (2) pass_seq: Amount 0 / enabled 0 / mix 0 / Panic -> max **0**;
(3) parity (clip paused, real frame: in_std > 0): Angle 0, Speed 0, Curve 0 -> `within` (2/255) >= 0.999; Curve 60 /
Angle 90 -> within >= 0.99 (float32 floor boundaries); (4) presets 1-7 full state (`presets`: no mismatches, after
`upgrade` too); (5) cost <= ~3 ms (target 0.4), project fps.

### smear modes `radial` and `maskedge` (DG-05 rest; lane D tail)
Radial stretch: the ring Bandpos..Bandpos + Bandwidth (shares of the half diagonal) around Centre x / y (Radial page)
is held, outside it each ray repeats the ring's outer pixel (Wobble jitters the band per 1/256 turn) = a radial
pixel stretch / burst. Mask edge stretch: pixels outside a Mask TOP (Radial page, luma > Threshold = inside; via
mask_sel into prev_src input 2, so the module keeps 3 GLSL inputs) take the first inside pixel up the drag direction
(<= 24 taps over Length), fading back over the run by 1 - Decay. Preset 8 radial burst. Mirror: smear_logic `radial`,
`maskedge` (Wobble 0: the column wobble is the old sin-hash). The 26 Oct "Not done" mask / radial stretch is closed.
LIVE CHECKS: parity radial (Wobble 0.6) and maskedge (Ramp TOP mask, Wobble 0) within (2/255) >= 0.99; presets 1-8.
Verified live (scratch, 27 Oct, 31550; `upgrade` of smear1: presets 1-7 replaced, 8 appended): radial within **0.9984**
(atan bucket edges, float32), maskedge with a vertical Ramp TOP mask within **1.0**; pass_seq **0 / 0 / 0 / 0**;
presets 1-8 full state; cost radial burst 0.48 / 1.05 ms, maskedge (200 px) 0.78 / 1.39 ms; project 59.93 fps.

### pixelsort Method `lite` (TC-24 masked pixel-stretch streaks)
Method menu (sort / lite). Lite does no sort: `lite` (compute, rgba32float, W x (H+1), row H texel 0 = cook clock)
reads its previous output through `lite_fb` (Feedback TOP): pixels inside the threshold window (Threshby / Lower /
Upper / Invert, Mask TOP too) seed the trail with their colour (alpha 1); every other pixel shows the previous trail
at p - dir x Litelength x (1 - Litejitter x h(column)) (+ Litenoise across, re-rolled per frame), bilinear, zero
outside the frame, x Litedecay per cook. A gap > 0.25 s since the last cook = fresh (no stale trail after bypass).
`lite_fx` composites: over (premultiplied), lighten, add, x Litegain, Amount mix. Direction rows = +x, columns = down,
Angle = (cos, sin); Reverse flips. out_sel: 0 in1 (Amount 0) / 1 sort / 2 lite, only the selected method cooks.
Mirror: `fx_glitch_pixelsort_logic.py` (`lite_step`, `lite_steady`, `reference`). Presets 6 lite drip, 7 lite wind
(lighten, noise), 8 lite shadows (dark window, Angle -60). Est. 0.3-0.6 ms.

LIVE CHECKS (lite): (1) compiles; lite_fb fresh on first cook; (2) pass_seq -> **0**; (3) steady-state parity (clip
paused >= 2 s, Litenoise 0, Litejitter 0, Litelength integer, columns): out1 vs `reference(in1, pars, iters=120)`
within (2/255) >= 0.99; (4) bypass 1 s then on: first read equals the seed-only frame (no stale trail); (5) presets
1-8 full state; (6) cost <= ~3 ms, project fps.

### chroma Split `time` (TC-26 RGB time split)
Split menu entry 4 `Time split`: each channel comes from its own frame, now / Delay / 2 x Delay cooks back (Order:
first letter = the channel taken now, second Delay ago, third 2 x Delay ago). Chain (only while Split = time and
Amount > 0, through Switches `t1_sel` / `t2_sel`, else in1): `ring` (Texture 3D, Depth = 2 x Delay + 1, Ringquality
full / half) + `stamp` (fx_time_ring's cook counter, its third user) -> `map1` / `map2` (1x1 offset maps, clamped to
the cooks the ring holds, T-122 encoding) -> `tm1` / `tm2` (Time Machine) -> fx (channel sources by `uG`; Mode /
Distance / blur still apply; Amount fades it in). VRAM full res: (2 x Delay + 1) x 8.3 MB (Delay 3 = 58 MB; half res
1/4). Presets 6 time split, 7 time smear (+ offset + blur), 8 ghost lens (radial, Delay 10, half ring). Mirror:
`fx_glitch_chroma_logic.py`.

LIVE CHECKS (time): (1) compiles (fx, stamp, map1/2), td_errors none; (2) pass_seq -> **0**; (3) cook-counter probe
(rgba32float in-place counter on every channel into the rack's in1, Input live, Distance 0, Delay 3, order rgb):
in - out per channel = **0 / 3 / 6** cooks on every pixel; order bgr -> 6 / 3 / 0; (4) restart: Amount 0 for 1 s,
back on -> offsets <= the stamp count right away (no stale frames); (5) Split rgb: the ring does not cook; (6)
presets 1-8 full state; (7) cost (ring + 2 tm + maps + fx) <= ~1 ms, project fps.

### mosaic Shape `hex` / `tri` / `square` (7C-33 cell mosaic with beat flips)
Shape menu (quad = the quadtree, default, unchanged). Cells page: Cellsize px (frame-centred lattice: hexagons from
two offset grids, equilateral triangles on the (1, 0) / (0.5, sqrt3/2) basis, squares), Cellfill centre pixel / cell
mean (stats mip at log2 Cellsize) / picture in the cell, Gap px + Gap colour, Edges darkens toward the gap. Beat =
the existing Rebuild edge / Autorebuild s (stamp: last rebuild time + count): per beat a Flip share of cells (hash of
cell id, beat count, Seed) flips over Fliptime s: Flip Y / Flip X (scale through 0, back side mirrored), Shrink (to 0
and back), Spin (half turn, clipped to the cell); the back side's hue turns by Recolour (YIQ). Mirror:
`fx_glitch_mosaic_logic.py` (centre / image fill exact; mean by look). Presets 6 hex flips, 7 tri shards (spin, image),
8 grid flip (squares, flip X, recolour). Est. 0.2-0.4 ms (+ stats 0.27 while wired).

LIVE CHECKS (cells): (1) compiles, td_errors none; (2) pass_seq -> **0**; (3) parity (clip paused, Flip 0) vs
`reference` for hex / tri / square, centre fill, Gap 2: within (2/255) >= 0.995 (float32 lattice boundaries); (4)
flip parity: Autorebuild 0, one Rebuild edge, read the stamp (last rebuild z, count w / 2, now x) with out1 in the
same read exec, reference(t = now, last = z, cnt) -> within >= 0.99; (5) presets 1-8 full state; (6) cost, fps.

### Module `databend` (DG-25 data-bending in 1D, FX0 row 73; lane D tail, `builders/fx_glitch_databend.py`)
The picture as a raw byte stream (R G B bytes per pixel, rows from the top like a file / columns / planar R..G..B),
through audio-style effects, written back: echo (Repeats taps Delay bytes apart x Feedback^n; a delay that wraps into
the next row = diagonal ghosts), delay, low-pass (exponential FIR, Cutoff, <= 32 Taps), high-pass (+128 centred),
crush (Bits), hold (sample-rate reduction), reverse (Chunk bytes), wah (cutoff swept Rate cycles / 10000 bytes,
Depth), reverb (4 comb taps at Delay x 1 / 1.37 / 1.71 / 2.13). Drift scrolls Delay (bytes/s). ONE compute pass:
every output byte gathers its taps (FIR forms, parallel), so the mirror `fx_glitch_databend_logic.py` is exact in
integer bytes. Presets 1 diagonal echo, 2 tape smear, 3 edge buzz, 4 reverse tape, 5 wah sweep, 6 planar reverb, 7
crushed hold, 8 drifting ghost. Est. 0.3-1.5 ms (32-tap filters the most).

LIVE CHECKS (databend): compiles; pass_seq -> **0**; parity (clip paused, Drift 0) for every effect within (1.5/255)
>= 0.999; presets full state; cost per preset <= ~3 ms (Taps 32 = the worst), fps.

Verified live (databend, scratch, 27 Oct 2026, 31550; rack from the builder, first frames at 270 x 480, T-193):
compiles; parity vs `fx_glitch_databend_logic` for all 9 effects (orders rows / columns / planar) within (1.5/255)
**1.0** (max 1 level); pass_seq **0 / 0 / 0 / 0**; presets 1-8 full state. First version gathered every filter tap
per byte (3 channels x 32 taps x a byte -> pixel lookup): tape smear 16.2 ms, wah 13.8 ms. Now the filters fetch
each stream pixel once and feed all three channels' taps from it (`lp3`; planar plane starts fall back to the exact
per-byte loop): parity unchanged (1.0), cost (median / p90) 0.85-2.18 / 1.35-5.14 ms per preset, Taps 32 columns
3.4 ms; Taps default 12, tape smear 16 taps. Project 59.95 fps.

### Verified live (lane D, scratch, 27 Oct 2026, 31550; rack built from the builder: smear1 + pixelsort1 only)
- **strips:** compiles, td_errors none. Parity vs `fx_glitch_smear_logic.reference` (clip paused, in std 0.227):
  straight strips (Angle 0, Stripwidth 6, Length 140, Wobble 0.6, Density 0.85) within 2/255 **0.999997** (6 px of
  2.07 M), 79 % of pixels changed; curved (Angle 90, Curve 60 x 2 waves, Snap 0, Threshold 0.3, Decay 0.6) **0.99989**.
  pass_seq Amount 0 / enabled 0 / mix 0 / Panic -> **0 / 0 / 0 / 0**. Presets 1-7 recall full state (0 mismatches),
  also after `upgrade` with a partial-state preset 1 and a missing slot 7 (replaced 1-6, appended 7). Cost (median /
  p90, own TOPs, In excluded, clip playing): pixel strips 0.62 / 1.26 ms, liquid strips 0.70 / 1.69, bright streaks
  0.64 / 1.65. Project **60.06 fps** (300 frames, cookRate 60 untouched).
- **pixelsort lite:** compiles. Steady-state parity at 270 x 480 (reference computed OUTSIDE TD from dumped .npy, T-181):
  columns / Length 10 / Decay 0.9 / over -> within **1.0** (max 0.0020); Angle -60 / Length 6.5 / jitter 0.5 / lighten
  x 1.3 -> **1.0**. Fresh restart after a 2 s bypass (pane off the rack): first read = the seed-only frame (k = 0
  exact; 240 cooks of stale trail would be within 0.64). pass_seq -> **0 / 0 / 0 / 0**. Presets 1-8 full state (0
  mismatches). Cost at 1080x1920: lite drip 0.98 / 1.99 ms, lite wind 0.96 / 4.06, lite shadows 1.02 / 1.78; true sort
  asendorf 3.40 / 5.73 (busy shared GPU; 2.13 in main 26 Oct).
- **chroma time split:** compiles (tm1 / tm2 show TD's "W-Offset" warning only before the ring's first cook). Cook-
  counter probe (270 x 480 rgba32float in-place counter, needs a time-dependent uniform or it cooks once): Delay 3
  rgb -> in - out = **0 / 3 / 6** on 129600 / 129600 pixels; Delay 5 bgr -> **10 / 5 / 0** on all pixels; Amount 0 for
  2 s then back: 4 frames later stamp z = 3 and the offsets read 3 / 3 / 0 (clamped, no stale frames). Split rgb
  (preset tear): ring cookAbsFrame frozen while fx cooks. pass_seq -> **0 / 0 / 0 / 0**; presets 1-8 full state.
  Cost: time split 1.43 / 2.38 ms (median / p90; ring + 2 Time Machines + maps + fx at 1080x1920), time smear 1.56 /
  3.49, ghost lens (half ring) 1.39 / 2.53, tear 0.60 / 1.37. Project 59.88 fps with time split on.
- **mosaic cells:** compiles. Parity at 1080x1920 (clip paused, Flip 0, Gap 2, Cellsize 48, centre fill) vs
  `fx_glitch_mosaic_logic.reference`: hex / tri / square all **max 0.0** (bit-exact), 87-91 % of pixels changed.
  Flip parity (Flip 0.5, Fliptime 3, image fill, Recolour 0.3, Edges 0.3, one Rebuild edge, stamp read with out1):
  Flip Y within **0.99998**, Spin **0.999998** (max 0.055 = hue-turn rounding). pass_seq -> **0 / 0 / 0 / 0**; presets
  1-8 full state. Cost: hex flips 1.23 / 2.14 ms (median / p90; fx + stats + stamp), tri shards 1.33 / 2.72, grid flip
  1.12 / 2.62, quadtree 1.09 / 1.75. Project 59.75 fps with hex flips on.
- **Main (JazibTD_home.644, 27 Oct):** FX_glitch (no other writes since the 22:22Z export) un-parked, then `upgrade`
  smear1 / pixelsort1 / chroma1 one per exec (3.5-3.7 s each; presets: old same-name rows replaced, new slots
  appended, no user rows), td_errors none, all 23 presets recall full state, pars back to defaults, every slot still
  enabled 0, re-parked (4330 ops), saved.
- **Main (JazibTD_home.676, 27 Oct):** mosaic1 / misc1 / timeshuffle1 `upgrade`d one per exec (3.0-3.3 s each;
  presets 1-5 replaced, 6-8 appended), td_errors none, presets full state, pars back to defaults, slots enabled 0,
  re-parked (4340 ops), saved. Same save: FX_retro `pixelart1` added by builder (enabled 0, 1775 ops).
- **Main (JazibTD_home.712, 27 Oct, lane D tail):** misc1 `upgrade`d (Lattice menu; preset 3 recalls Lattice classic),
  `databend1` added by builder (enabled 0); FX_retro `retroscreen1` added; errors none, presets full state, pars at
  defaults, re-parked (FX_glitch 4609 ops, FX_retro 2855), saved.
- **Main (JazibTD_home.716 / .726):** FX_retro `cycle1` + `halftone1` added by builder (.716, 3392 ops); FX_glitch
  smear1 `upgrade`d with radial / maskedge (.726, 4610 ops); errors none, presets full state, parked. Library
  re-exported: FX_glitch 0.3.0, FX_retro 0.6.0.
- With the network pane on the rack, a bypassed slot's module keeps cooking (pane viewer pulls it, T-111 (5)), so its
  trail never goes stale: the fresh-restart check needs the pane elsewhere.

## Module template (Phase 1 modules follow this)
One file per module: `builders/fx_glitch_<module>.py`. The rack finds it by name (`slots.module` = `<module>`), so
there is nothing to register. The file defines:

| Name | What |
|---|---|
| `MODULE` | the module name (`'smear'`) |
| `PAGES` | `[(page, [(Par, 'Float'/'Int'/'Menu'/'Toggle', default, {min, max, label, names, labels}), ...])]`; the rack adds them to the instance COMP. `Amount` first (0 = exact passthrough), `Seed` when the module is random. Slider ranges only, no clamps |
| `PANEL_PAGES` | pages the zkit panel shows |
| `PRESETS` | `[(slot, name, {Par: raw value})]`, 3-5 looks, menus as their index; seeded once into the zkit presets |
| `build(m, H)` | fills instance COMP `m` with `in1` (In TOP) -> ... -> `out1` (Out TOP), reads its pars as `parent().par.X`; `H` = rack helpers `mk(comp, cls, name)` (reuse-or-create), `expr(par, text)`, `sd(op)` (safe_destroy), `compute(m, name, text, ins, res=None, fmt)` (compute GLSL TOP + docked DAT, size = input 0 unless res), `uniforms(g, [(name, [x, y, z, w exprs])])`. Returns its stage plan `[{title, role, ops, body}]` for `layout_stages` |

Rules for modules: compute-mode GLSL for every pass (a rack is a multi-pass chain, T-46/T-47), output resolution =
input resolution, `format useinput` unless the module needs float state (then convert back for the out), Amount 0 =
bit-exact passthrough (check numpy diff 0), no limiter, <= ~3 ms at 1080x1920 with project 60 fps (per-module tap
or pass caps rather than a Quality framework until a module needs one). Masks / triggers / `DX_lib` snippets get
added to the rack only when a destruction module needs them and a second one will reuse them.

## Not done / open
- Mask-edge and radial stretch (DG-05): built in the lane D tail (smear modes radial / maskedge).
- No shared audio/trigger hook: `block` (Beat) and `mosaic` (Rebuild) take a float edge par each; bind a CHOP or MIDI
  to it. A shared `Hit` comes when a third module needs the same trigger.
- `block` Freeze and `dct` Generation reset after a > 0.25 s stall (like smear); `mosaic` rebuilds after > 1 s.
- Slots have no per-slot cook-ms readout. (Bypass with the pane on the rack no longer cooks the module: slot_gate.)
- Feedback restarts after any stall longer than 0.25 s (a heavy frame hitch resets the trail once).

- **Slot off = module not cooked, also with the pane on the rack** (27 Oct, T-201, RENDER_COST.md "Applied: slot_gate"): each module's `slot_gate` passes in1 when its slot is enabled 0 / mix 0; in main (FX_glitch + FX_analog, JazibTD_home.754).
