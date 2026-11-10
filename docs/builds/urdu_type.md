# urdu_type (BJ build spec A): status 26 Oct 2026, TD 2025.31550 - LIVE-VERIFIED via the pre-shaped atlas route (commit 9eb3bc7: 150 s scratch soak, then main; earlier Text TOP route crashed TD, T-76/T-79)

- Quiet-machine numbers: docs/builds/PERF_QUIET_27OCT.md (27 Oct, other TDs closed; load still ~40-60).

Spec: `docs/research/BJ_urdu_arabic_text_shaping.md` section 5 (clean-room). Path: `/project1/lab/BJ_urdu_type`.

## Files
| File | What | State |
|---|---|---|
| `builders/urdu_type_logic.py` | pure logic: bidi-lite (UAX #9 W/N/I rules per word), L2 reorder, tokenize, font roles, layout (wrap, align, anchor, line pitch), ranks, anim (7 modes), progress (manual/seconds/bpm/audio + in2), **pixel-free measuring**: font file lookup (file-name guess, then a header-only name-table index, ~50 ms once), hhea metrics, `hb-shape --show-extents` batch (one process per font), ink box per word relative to the tile centre, estimate fallback (no shaper / `.notdef`), tile size | offline-verified |
| `test/test_urdu_type.py` | 28 tests: levels = fribidi on 32 lines x 3 directions, layout invariants, anim golden table, hb-shape oracles 1617/2515/3605/3393 + negative control, **pixel-free measure = the live pre-crash numbers** (urdu at 160 px: advance 233.3 = evalTextSize width, line box 400 = evalTextSize height, ink 214 x 150 below centre), batch order/fallback, and a guard that no builder/runtime source calls `.numpyArray(` / `.evalTextSize(` / `.sample(` | 28/28 pass |
| `builders/urdu_type_rt.py` | TD runtime (Text DAT `urdu_rt`): coalesced rebuild/relayout; `rebuild()` sets Text TOP **pars only** (font, file, typeface, reading direction, size, resolution, text) and never calls a TOP method | not run |
| `builders/urdu_type.py` | builder, `build(..., upto=1..4)` in steps: 1 tiles (rgba8) + tables + scheduled rebuild, 2 + one compute place pass (`Showboxes` draws the measured ink boxes, to check the offline measure by eye), 3 + half-res blurs + one compute compose + out + par watchers + pre-created `controls/zk_measure`, 4 + zkit controls + stage layout | not run |

## Live run order (each its own td_exec, >= 2 frames apart; one lane only while it runs)
```python
g = dict(globals()); exec(open('<repo>/builders/urdu_type.py').read(), g); g['build']('/project1/lab', upto=1)
# then upto=2, upto=3, then upto=4 (zkit) in a later call, so zk_measure has existed + cooked for >= 2 frames
```
Then: td_errors, `words` table (src = hb for Urdu, adv/lineh as in the tests), `Showboxes` on + window capture (boxes
must hug the ink: that checks the "Text TOP centres the advance box + hhea line box" assumption without readback),
td_layout check, td_perf + td_watch 5 s with the rest parked, save, park.

## Crashes
- 26 Oct 14:53 (first build): stack Python -> libC_TOP -> libGX -> OSX_CrashHandler; that build created 24 a8fixed
  tiles and called `evalTextSize` + `cook(force)` + `numpyArray` on them in one exec. Taken as T-74 (readback).
- **26 Oct 15:12 (this rebuild's scratch probe, crash 4):** the probe made a fresh Text TOP in a new COMP, set
  font/size pars and called **`evalTextSize()` only** (no numpyArray, no cook) in the same script. Same stack
  (`sample` of pid 37620: cook thread, libC_DAT -> Python exec -> cfunction_call -> libC_TOP -> libGX ->
  OSX_CrashHandler::abortHandler / sigwait), td_exec timed out at 60 s, CrashAutoSave.JazibTD_home.93.toe written
  15:12. So `evalTextSize` on a Text TOP that was just created / re-fonted reaches the GPU layer too and is not a
  safe replacement for readback (T-74 recommends it). zkit's `build_controls` does the same pattern (creates
  `zk_measure`, then `Rebuild()` -> `evalTextSize` in one script): it has worked before, but it is the same hazard.

## Left to do
TD restart (user), then the live run order above.
