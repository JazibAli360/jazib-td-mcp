# fx_glitch module `timeshuffle` (frame shuffle / per-block time offset, DG-12) - offline prep, 26 Oct 2026

Status: **live on the main TD (26 Oct, 31550), slot `timeshuffle1` (enabled 0).** Map encoding corrected live (T-122). Everything marked **LIVE CHECK** needs TD 2025.31550. Rack + template:
`docs/builds/fx_glitch.md`. Same native ring as `timedisplace` (`builders/fx_time_ring.py`, FX6 probe 4b); the only
GLSL is the map pass, which gives every block a whole-cook time offset.

Files: `builders/fx_glitch_timeshuffle.py`, `builders/fx_time_ring.py`, `builders/fx_time_logic.py` (`ts_offsets`,
`ts_block_offset`, `perm` = the shader in Python, exact uint32 hash), `test/test_fx_glitch_timeshuffle.py` (19 tests,
glslc compile against TD stubs).

## Network
As `timedisplace` without `map_sel`: `in1` -> `ring` (Texture 3D) ; `stamp` ; `map` (full input res, rgba32float)
-> `tmachine` -> `out_sw` (Amount 0 = in1) -> `out1`. Map grey `m = 1 - k/(Depth-1)`, k whole cooks, clamped to
`[0, min(Depth-1, stamp.z)]` (no stale slices after a restart).

| Par | What |
|---|---|
| Amount | x Chance (0 = exact passthrough) |
| Depth, Quality | ring slices (VRAM as timedisplace: 32 = 265 MB full), full / half res |
| Mode | random (delay 0..Length-1 per block, redrawn Rate times a second), permute (plays the previous Length frames shuffled; needs Depth >= 2*Length), reverse (each chunk backwards; Depth >= 2*Length-1), hold (stutter: first frame of each chunk), luma (bright blocks lag), wave (delay from the block's place along Angle; Repeat, Phase scroll) |
| Length | frames per chunk / max delay |
| Blocksize, Shape | px; squares, rows (full-width strips), columns |
| Chance | share of blocks affected (redrawn per epoch / chunk) |
| Rate | Hz of the random / luma / wave draws and the grid jumps (0 = frozen draw) |
| Perblock | each block starts its chunk at its own phase (staggered stutter / reverse / permute) |
| Gridshift | block grid jumps by up to this x Blocksize per Rate tick |
| Angle, Repeat, Phase, Invert | wave direction (0 = bottom now), count, scroll; Invert flips luma / wave |
| Seed | hash seed |

Presets: 1 temporal blocks, 2 stutter strips, 3 rewind, 4 shuffle deck, 5 time stairs.

## Build
```python
ns = dict(globals()); exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_glitch.py').read(), ns)
ns['add']('/project1/lab/FX_glitch', 'timeshuffle')       # -> timeshuffle1
```
Scratch TD first (T-83), lane.py add/remove, park at the end (as timedisplace).

## LIVE CHECKS (~15 min; frame-code probe + read snippet: `docs/builds/fx_glitch_timedisplace.md`)
1. **Builds clean:** `td_errors` none; `map` compiles (`findMSB`, uint loops).
2. **Exact passthrough:** Amount 0 / enabled 0 / mix 0 / Panic -> max diff **0** (clip paused).
3. **Random fingerprint** (probe, Mode random, Rate **0**, Seed 1, Blocksize 64, squares, Length 16, Chance 1,
   Depth 32, full; wait > 1 s): decode the offset at each block centre (x = 32 + 64 i, y = 32 + 64 j, from the
   bottom). Expected from `ts_offsets`: bottom row of blocks i = 0..7: **5, 13, 3, 7, 9, 1, 14, 10**; first column
   j = 1..4: **14, 13, 14, 12**; 510 blocks (17 x 30), mean offset over pixels **7.81**. Pass: >= 99 % of blocks equal
   (whole frames; a frame drop can make one read +1). Every pixel of a block equal (`np.ptp` per block 0).
4. **Whole-cook exactness:** offsets are whole cooks, so out codes are exact frame codes: decoded offsets equal the
   reference (check 3) with no +-1 scatter inside a block. If any block reads between two frames, the float map vs Time Machine
   interpolation is not exact: note it (fix = Sampling Units index / map rounding).
5. **Hold** (preset 2 with Perblock off, rows 24 px, Length 8): every pixel the same offset in [0, 7]; reads 0.5 s
   apart differ. Perblock on: per strip offsets differ, all in [0, 7].
6. **Reverse** (preset 3, Length 12, Depth 32): whole frame one offset, an even number in [0, 22]. **Permute**
   (preset 4 without Perblock, Length 8): one offset in [1, 15] across the frame (reference sequence for n =
   104..111 shows frames 102, 97, 100, 101, 99, 98, 103, 96: a shuffled previous chunk).
7. **Restart:** Amount 0 for 1 s, back to 1: offsets <= stamp z at once (no stale blocks).
8. **Wave** (preset 5): rows step up the picture, offsets 0 at the bottom to 29 at the top (Length 30), scrolling
   with Phase 0.2.
9. **Cost:** ring + tmachine + map <= **0.6 ms** (map full res: one hash per pixel, ~0.1 ms); project 60 fps.
10. Presets 1-5 recall; captures; `td_checkpoint`, save, park, results here + T-entry.

## Not done / open
- Beat-synced chunks (a `Hit` / bar pulse) wait for the rack's trigger hook (fx_glitch.md "Not done").
- Ping-pong mode left out (hold + reverse cover it with Perblock); add if asked.

## Verified live (26 Oct, 31550; scratch first, then main; T-122)
- Builds clean (`map` compiles). Exact passthrough: Amount 0, enabled 0, mix 0 -> max diff 0.
- **Random fingerprint (check 3) after the T-122 map fix, 16f cook counter:** bottom row 5, 13, 3, 7, 9, 1, 14, 10;
  first column 14, 13, 14, 12; mean 7.81; 100 % of pixels equal the map's whole-cook offset, ptp 0 inside every block
  (whole frames, no blend). Before the fix every block read k-1.
- Cost (preset 1 temporal blocks, 120 pulled cooks): 0.94 ms median (tmachine 0.23, map 0.21, stamp 0.13, ring 0.10).
- Not run live: checks 5-8 (hold / reverse / permute / wave sequences), presets 2-5 by eye.

## Mode `cadence` (TC-31 frame-cadence editor; lane D, 27 Oct 2026)
Mode menu entry 7. Cadence page: `Cadence` menu = a BANK pattern (stutter `p6 h6 r6 v6`, strobe `p3 b1 p2 w1 h4 b1`,
rhythm `p4 h8 r4 v4`, reel `p8 r8 r8 b2`, blink `p5 b1`, rewind `p12 v12`) or Custom = the `Pattern` text: steps
`p` play, `h` hold (the step's first frame), `r` repeat the previous step's frames, `v` reverse, `b` fill colour
(Fillr/g/b), `w` white, each + a length in cooks (no number = Length). Up to 16 steps loop over the stamp's cook count
(so a restart starts the pattern at step 1, offsets clamped to the ring as every mode). Blocks: Blocksize / Shape,
Perblock staggers the phase per block, Chance (x Amount) picks blocks per cycle; whole frame = Blocksize 512 squares.
The `cadence` Text DAT parses the pattern for the map uniforms (uP0-3 codes, uL0-3 lengths, uQ total / steps); the
map's alpha marks fill frames (1 keep, 0 fill, 0.5 white) and `cad` (compute after tmachine) paints them; out_sw
index 2 only in cadence mode. No limiter on fill / white frames (operator decides; user rule). Mirror:
`fx_time_logic.cadence_offset` / `cadence_frames`. Presets 6 stutter cut, 7 strobe edit, 8 rhythm strips (Perblock,
Chance 0.7); presets 1-5 are full state now (Quality, Rate, Cadence, fill pars added to `_Z`).

LIVE CHECKS (cadence): (1) compiles (map, cad); (2) pass_seq -> **0**; (3) cook-counter probe, Cadence custom
`p4 h4 r4 b1 v3`, whole frame: 16 consecutive dumps (one per frame, scheduled runs) decode to the `cadence_frames`
sequence (play, hold, repeat, fill, reverse) up to the frame phase; fill frame = Fill colour exactly; (4) Time
Machine ignores the map alpha (keep frames unchanged vs random mode at the same offsets); (5) presets 1-8 full state;
(6) cost <= ~1.2 ms (+ cad 0.1), fps.

### Verified live (cadence: lane D, scratch, 27 Oct 2026, 31550; rack from the builder)
- Compiles (map, cad), td_errors none. Cook-counter probe (270 x 480 rgba32float) into the rack, Pattern `p4 h4 r4 b1
  v3`, Blocksize 512, Chance 1, Fill R 0.25: 40 scheduled dumps (one per frame) covering all 16 pattern phases:
  **40 / 40** frames = `cadence_frames` (play, hold on the step's first cook, repeat of the previous 4, the fill
  frame exactly (0.25, 0, 0), reverse 2 i back); keep frames show whole cooks, so the Time Machine ignores the map's
  alpha. pass_seq -> **0 / 0 / 0 / 0**; presets 1-8 full state. Cost (median / p90): stutter cut 1.03 / 1.69 ms,
  strobe edit 1.07 / 1.82, rhythm strips 1.11 / 1.84, temporal blocks 0.89 / 2.09. Project 59.99 fps (strobe edit).
