# FX6 - Phase 1 probes on the scratch TD (TD 2025.31550, 26 Oct 2026)

What the FX0 Phase 1 modules (`mosh`, `pixelsort`, `dct` + `bits`, `timedisplace`, `shatter`) need to know before
anyone builds them. Each probe was checked against numpy, and each cost was measured on the **scratch TD only**
(T-83, `/project1/fx6`, now removed). The main TD was not touched. Only the five probes the Phase 1 modules need were
run. Blur preshrink and OCIO `.cube` are FX0 Phase 0 items for later phases and are not covered here.

**Method.** Every probe is a Compute-mode GLSL TOP (T-47) at 1080x1920 unless stated. Each one was force-cooked once
per frame by a `run(delayFrames=1)` chain for 120-150 frames. The first 10 frames were dropped, and the table gives
the median `gpuCookTime` (max in brackets). Correctness was checked by a `numpyArray(delayed=False)` read in a later
exec (T-74). Two sessions ran: scratch pid 45327, which crashed afterwards (see below), and pid 15821 after the
restart. Other lanes (PX, debug panel, physarum) used the same scratch TD at the time, so expect +-0.5 to 1 ms noise.
Where the two sessions differ, both values are given. "fps" is the scratch TD's real rate (wall clock between frame
starts) while that probe ran.

## Results

| # | Probe | Result | GPU ms @1080x1920 (median, [max]) | Pass |
|---|---|---|---|---|
| 1a | `shared float sk[512]` + `barrier()` bitonic sort, `local_size_x = 512`, rows in 512-px chunks | identical to `np.sort` per chunk (max error 0, 0 bad segments) | 1.08-1.50 [2.9-4.2] | PASS |
| 1b | the same with `local_size_x = 1024` (1024-px chunks) | identical to `np.sort` (error 0) | 1.51-2.38 [4.1-5.2] | PASS |
| 1c | whole column 1920 px: `local_size 1x1024`, `shared vec4 sk[2048]`, 2 elements per thread, manual dispatch 1080x1x1 | keys identical to `np.sort` (r error 0); (r,g) pairs are the same multiset per column; 140 g mismatches all sit on the 159 tied keys (bitonic is not stable) | 1.56-1.65 [4.1] | PASS |
| 1d | DCT 8x8: `local_size 8x8`, one workgroup per block, `shared float b[8][8], t[8][8]`, 4 barriers, separable DCT-II + IDCT, 1 channel | coefficients vs numpy max error 1.9e-6; round trip 4.8e-7 | 0.47-0.80 [1.8-3.3] | PASS |
| 2 | `uint` ops in compute: `bitfieldExtract/Insert/Reverse`, `bitCount`, `findMSB/LSB`, `^ & << >>`, `floatBitsToUint` / `uintBitsToFloat`, 2 colour buffers | all 8 channels identical to the Python integer reference (error 0) | crush pass (mantissa mask + 8-bit plane XOR + hash) 0.24-0.26 [0.6-1.0] | PASS |
| 3a | block match 8x8 SAD, full search +-8 (289 candidates). **Shared version**: workgroup per block (8x8 threads), 24x24 search window + block in shared memory, 64-thread min-reduction | known shift (3,-5) recovered as MV (-3,+5) on 100% of inner blocks, SAD 0, at both sizes | **1080x1920: 1.04-2.74** [3.4-9.0]; **540x960: 0.27-0.66** [1.0-3.1] | PASS |
| 3b | the same search, naive (one thread per block, all taps from textures) | same MVs | 1080x1920: **21.6** [42.7] (scratch fell to 18.7 fps); 540x960: 6.7-7.2 [13-14.5] | FAIL (cost) |
| 4a | `timemachineTOP` fed by a **Cache TOP** (cachesize 32) | **error: "Input texture must be a 3D or a 2D Array"**. A Cache TOP outputs one 2D frame (depth 1). | - | FAIL (by design) |
| 4b | `texture3dTOP` (cachesize 32) -> `timemachineTOP` (vertical ramp map, `blackoffset -31`, `samplemode depthoffset`) | offset is linear in the map (white 0, black = oldest slice) and interpolated between slices (241 distinct row values); 32 slices = 32 **cooks**, so under dropped frames the oldest row reads -41 absTime frames, not -31 | tex3d 0.12-0.15 [1.3-1.5] + time machine 0.21 [0.7-2.4]; real fps 57.8-60 | PASS |
| 5a | shard state: 3 colour buffers `rgba32float`, `outputaccess readwrite`, `clearoutputs off`, `TDImageLoadOutput` / `TDImageStoreOutput` in place, 64x16 = 1024 shards; buffers 1-2 read through `renderselectTOP` `bufferindex` | after 100 cooks every texel = 100 steps exactly; position accumulation error 7e-6; constants 16777215, 0.1234567, -3e30, 1e-30 bit-exact | **0.07-0.12** [0.8-0.9] | PASS |
| 5b | the same state shader at 1080x1920 x 3 buffers (per-pixel state) | no errors | 0.59-0.61 [1.0-1.7] | PASS |

Reference costs from the same runs: Noise TOP source 1080x1920 0.3-1.9 ms; a 1-tap shift compute pass 0.02-0.14 ms.

## What each Phase 1 module should do

- **`pixelsort` (DG-04).** Use one compute pass with shared-memory bitonic and `barrier()`. This works on 31550/MoltenVK
  up to `local_size 1024`, and 2 elements per thread give 2048-element lines. Default to rows in 512-px chunks (~1.1-1.5
  ms). A full 1920-px column is 1.6 ms, which fits the 3 ms budget. The segmented sort goes into the key in the same
  pass (interval id in the high bits). Bitonic is not stable, so pack the pixel index into the low bits of the key, or
  tied pixels shuffle from frame to frame (flicker). No multi-pass chain is needed. Add a `Quality` half option only if
  the combined rack check needs it.
- **`dct` (DG-08).** Use one pass, `local_size 8x8`, one workgroup per block, shared 8x8 arrays (as in the probe). One
  channel is 0.5-0.8 ms. For YCbCr, run luma at full res and chroma at half (4:2:0 is what JPEG does anyway), and
  measure the 3-channel cost at build time. Quantise and coefficient damage go between the forward and inverse
  transforms in the same shader.
- **`bits` (DG-09).** Every uint op it needs works and is exact. It is a one-pass shader of about 0.25 ms. It does not
  need the DCT pass or any shared library: one small shader of its own.
- **`mosh` (DG-01).** The block-match estimator must be the shared-memory workgroup-per-block version. The naive form
  costs 21 ms at full res and is never usable. Default the estimator to 540x960 with 8x8 blocks and +-8 search
  (0.3-0.7 ms; 8x8 at half res = 16x16 at full, the codec macroblock), with Full as an option (1-2.7 ms). Output is one
  texel per block (`rgba32float`: mv.xy, SAD). The update/advect pass (state rgba16f) was not probed; it is one
  ordinary per-pixel pass. Larger ranges should go coarse-to-fine, not to a wider full search: the cost grows with the
  candidate count.
- **`timedisplace` (DG-13).** Use native `texture3dTOP` -> `timemachineTOP` with the map on input 2. There is no GLSL
  and no Cache TOP: the time machine refuses a Cache TOP. It costs ~0.35 ms. VRAM is the real cost: 32 slices of
  1080x1920 rgba16f = ~530 MB, so `Depth` = `cachesize` and `Quality` half (1/4 of the VRAM) are the only
  heavyweight pars. Depth is counted in cooks, not seconds, so it stretches when frames drop. The same 3D ring serves
  `timeshuffle` later. Do not build a shared ring now (no-bloat rule).
- **`shatter` (DG-15).** Shard state lives in **one** compute TOP with 3 `rgba32float` colour buffers (pos/vel,
  rot/angvel, life/seed/...). Set `outputaccess readwrite` and `clearoutputs off`, update in place with
  `TDImageLoadOutput`, and use a Reset uniform for the initial state. No Feedback TOP is needed. 1024 shards cost
  ~0.1 ms, so the budget goes to the render/instancing pass, which was not probed here. The draw side reads buffers 1-2
  through Render Select TOP `bufferindex`.

None of these results calls for a shared `DX_lib`. The only thing the modules have in common is "compute pass, custom
resolution, auto dispatch", and the builders already do that (`builders/cloth.py` `_compute`).

## Crash during the probes (T-110)

The scratch TD (pid 45327) segfaulted at 18:57:59 PKT. The faulthandler logged "Fatal Python error: Segmentation
fault", and the faulting thread had no Python frame. No .ips was written: the TD sat on its crash dialog until
`scratch_td.py stop` ended it. In that same second, this lane's exec had just finished plain `.destroy()` calls on 3
ops in `/project1/fx6` (an Execute DAT with frame callbacks, a Text DAT, and a Noise TOP with its viewer on) while the
network pane showed that COMP. This is likely the T-70 pattern (UI thread drawing destroyed ops), but it is not proven
without symbols. Other lanes' scratch execs (PX build, debug panel, physarum probe) timed out with it. After the
restart all probes were rebuilt and every removal went through `safe_destroy`, with no further crash. Rule: on the
scratch TD too, remove ops with `safe_destroy` (it is in td_exec's namespace), never with a bare `.destroy()`.
