# review_tour — Lab review window (v1)

COMP `/project1/review_tour`, TD 2025.31550. Builder `builders/review_tour.py` (`build(panel=True, open_window=None)`,
idempotent, T-70 safe), pure logic `builders/review_tour_logic.py` (copied into `tour_logic`), runtime
`builders/review_tour_rt.py` (copied into `tour_rt`), offline tests `test/test_review_tour.py` (14).

```python
ns = dict(globals()); exec(open('<repo>/builders/review_tour.py').read(), ns); ns['build']()
op('/project1/review_tour').par.Opentour.pulse()        # window 'Lab review'
```

## What it is
- **List** (left, 380x800): every child COMP of `/project1/lab` (annotate boxes left out), grouped and ordered like the
  lab's stage boxes (the lab's stored `jz_stages` plan); COMPs no box lists go under OTHER. `*` = cooking now,
  `(no out)` = no Out TOP. Spec tables -> 5 Text TOPs (Menlo, fixed 18 px line slots, rewritten only on change) over a
  blue highlight bar; scrolls around the selection when the lab outgrows the panel.
- **Big view** (right, 450x800): Select TOP of the shown COMP's Out TOP (`handlers._source_top`) -> Fit best -> title
  bar (name, n/N, group, cooking/parked, controls hint). Click the title bar (or Enter / `c`, or the `controls` knob)
  = the shown COMP's `Opencontrols` pulse (or its `controls_window`).
- **zkit knobs** under them (page Tour): prev, next, comp # (Index), controls, rescan lab, close tour.
  Keys while the tour has focus (Keyboard In, `panels` = the tour panels): left/up/`[` prev, right/down/`]`/space
  next, Enter/`c` controls, Esc close. Click a row = show it.
- **Cook guard** (page Setup: `Cookguard`, `Protectlanes`): the window opening starts a session that records which lab
  COMPs were already cooking (`rt_session.before`). Showing a COMP wakes it if parked (the tour then owns it); moving
  on parks what the tour woke; closing the window (X, Closetour, Esc) parks the rest. Never parked: a COMP cooking
  before the tour, a live lane's COMP (`logs/active_lanes.json`), top-level COMPs. While closed `view_src` is empty,
  so nothing is pulled.
- Pars: Tour = Prev, Next, Index, Openctl, Rescan, Closetour + read-only Shown, Cooking, Tourstatus; Setup =
  Opentour, Lab, Cookguard, Protectlanes; Zkit page from zkit (Opencontrols opens the same window).
- The tour itself is not parked: a parked COMP's Parameter Execute does not fire (T-100), so Opentour would do
  nothing. Closed it costs 0 cooks (120 frames measured) plus one tiny frame-start Python call.

## Live verification (26 Oct 2026, TD 2025.31550, other lanes building)
- Scratch TD first (T-83; fake lab of 6 COMPs): open, steps, key/click, close, rebuild with the window open: no crash,
  session kept, `before` COMP never parked.
- Main: 33 lab COMPs listed in 8 groups; `td_errors` clean; `td_layout check` ok (33 ops, 0 overlaps/intruders).
- **5 steps (Next x5 from BO_particles), cooking set after each** (the lab had GN_reaction_diffusion + AU_features
  cooking from other lanes): {BN_fluid2d}, {BN_cloth}, {BL_splat_render}, {BL_cloud_morph}, {LK_projection_room}, each
  plus exactly those two; each step parked the previous one; one on_pulse + one Index change per step (traced).
- **fps with the window open** (TP_test_pattern shown, wall clock between frame starts, 301 frames): 60.1 fps,
  median 16.7-17.1 ms. Tour cost per frame: view chain only (src 0.15, fit 0.07, comp 0.06, out 0.02 ms CPU+GPU); list
  and title Text TOPs 0 cooks between changes.
- **Rebuild with the window open (T-70):** window closed by the builder, rebuilt, reopened 5 frames later; no crash;
  session re-started cleanly (shown COMP parked on close, woken on reopen).
- Close: TP_test_pattern parked, lab back to its pre-tour set, view_src empty, 0 tour cooks in 120 frames.
- Capture: session scratchpad `review_tour_main.png`. Checkpoint `output/checkpoints/review_tour/`; saved
  JazibTD_home.208.

## Notes / next
- Real keystrokes were not sent (they would type into the user's TD); `key()` was fed key events like zkit's tests.
- Scratch run: the Index stepped 1-2 extra times twice while the window sat under the pointer (likely wheel/click on
  the comp # knob in the visible window); on main the trace showed exactly one change per step.
- Ideas: per-COMP cook ms in the list, a "solo" mode that parks everything except the shown COMP (needs the user's
  OK: it would park other people's work), thumbnails.
