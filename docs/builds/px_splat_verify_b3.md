# PX_pointfx on Gaussian splats: modules 16-30 (b3 verify lane, 27 Oct 2026, TD 2025.31550)

Read-only verification for px_requirements items 6 / 9 / 11. No builder edited; nothing brought home.

**Method.** Main's `/project1/lab/PX_pointfx` saved read-only to `output/transfer/PX_verify_b3.tox`, loaded into b3
`/project1/lab` (616 ops), un-parked. Scene = `px_checks.SPLAT_SCENE` (SmileyPinata.spz, Quality custom 228 287,
Render splats; side 478), one box effector E1 (tx 0.25, size 0.5). Every test: exec A = `set_stack([(module, values,
effs)])` + reset + pump 90 frames; exec B about 300 frames later = `_splat_measure` (source / update / look / srender
reads) + `out1.save` to `output/px_splat_b3_<module>.png`. The next test replaces the stack; the stack was emptied at
the end. The working-tree `builders/px_checks.py` (owner lane's uncommitted edits) supplied the helpers.

**Baseline (no modules):** splat 1, sw_render 2 (srender direct), look alpha mean 0.5344, size 1.0, srender alpha
(1/8 grid) 0.1311, rest scale median anisotropy 3.08 (max/min axis). Capture: `px_splat_b3_baseline.png`.

On every test below, `eng_info splat` = 1, `sw_render` = 2, 0 NaN, rot change 0.01 deg (no rotating module), and the
captures show real anisotropic splats (smooth ellipses, ground plate blobs unchanged), not dots. Sorts kept running
while centres moved (counter 74 -> 2044 over the run) and stopped for colour-only modules (1119 held).

| # | Module | Result | Numbers (vs baseline) | Capture |
|---|---|---|---|---|
| 16 | jitter (amp 0.03) | pass | disp mean 0.0288 / max 0.0514; image rgb diff 0.018; alpha unchanged | px_splat_b3_jitter.png |
| 17 | glitch (prob 0.5, block 0.1, offset 0.1) | pass | disp mean 0.0476 / max 0.148; blocks of splats offset as slabs | px_splat_b3_glitch.png |
| 18 | audio_displace | pass | beatkick 0.1 alone (no audio): uniform radial 0.0082 = beatkick x BEAT; with a fake audio CHOP (`Audiochop`, s0..s15 = k/15), band spec_id amp 0.1: disp mean 0.0500, max 0.1000 (= amp x 0.5 / amp x 1 exactly) | px_splat_b3_audio_displace.png, _audio_displace_spec.png |
| 19 | shockwave (beat, speed 0.6, width 0.08, amp 0.08) | pass | disp mean 0.020 / max 0.055; ring colour on splats: look rgb change 0.385 | px_splat_b3_shockwave.png |
| 20 | mask_region (E1) | pass | m0 max 1, mean 0.749 (79 % > 0.5); image unchanged alone (as designed); + colour_adjust maskin m0: rgb change 0.442, only the masked side recoloured | px_splat_b3_mask_region.png, _mask_region_consumer.png |
| 21 | mask_image (Ramp TOP into in_mask, screen, lum, thr 0.5) | pass | m0 mean 0.282 (29 % > 0.5); + colour_adjust maskin m0: right half of the screen recoloured (rgb change 0.127) | px_splat_b3_mask_image.png, _mask_image_consumer.png |
| 22 | mask_attr (height -0.1..0.2) | pass | m0 max 1, mean 0.568; + colour_adjust maskin m0: a height band recoloured (0.362) | px_splat_b3_mask_attr.png, _mask_attr_consumer.png |
| 23 | dissolve_noise | pass | progress 0.5: dissolve mean 0.043, look alpha 0.534 -> 0.512, size 0.970, srender alpha 0.131 -> 0.091; progress 0.8: dissolve 1.0, alpha 0, size 0.30 (peel/shrink), splats drift off as dust | px_splat_b3_dissolve_noise.png, _dissolve_noise_p08.png |
| 24 | dissolve_gradient (progress 0.5, range 0.8) | pass | dissolve mean 0.433, alpha 0.296, size 0.697, srender alpha 0.024; dissolved splats blow away as small splat dust | px_splat_b3_dissolve_gradient.png |
| 25 | dissolve_time | pass (see note) | Disrecover 0: dissolve 1.0, alpha 0 after ~5 s; Disrecover 3: dissolve mean 0.314, 29 % of splats at alpha < 0.1, speed mean 0.32 (release) | px_splat_b3_dissolve_time.png, _dissolve_time_recover.png |
| 26 | lifetime (life 0.5, fadeout 0.4) | pass | look alpha mean 0.534 -> 0.201, srender alpha 0.131 -> 0.109; no displacement | px_splat_b3_lifetime.png |
| 27 | density (0.3) | pass | alpha 0.534 -> 0.160 (= 0.3 x), size mean 0.300; kept splats render normally | px_splat_b3_density.png |
| 28 | colour_ramp (height -0.43..0.3) | pass | look rgb change 0.296, alpha unchanged; image = cyan-to-cream height ramp on the splats | px_splat_b3_colour_ramp.png |
| 29 | colour_adjust (exposure 1, hue 0.3) | pass | look rgb change 0.585, alpha unchanged; image hue-shifted | px_splat_b3_colour_adjust.png |
| 30 | velocity_streak | pass (needs a force) | alone / with jitter (kinematic): state v = 0, stretch 0 (nothing to streak); with curl (force) strength 3, gain 40: stretch mean 7.10, max 20 (= maxlen), speed mean 0.258; covariance stretched along v into long streaks | px_splat_b3_velocity_streak.png (curl + streak), _velocity_streak_driven.png (curl 1, gain 3: stretch 0.048) |

**Notes (no failures):**
* Masks (20-22) only write m0, so alone they leave the image as it was; the mask + colour_adjust captures show they
  act on splats.
* dissolve_time with the core `Disrecover` 0 (px_checks' scene default) ends fully dissolved after one cycle, because
  `dis = max(dis, d)` and nothing recovers it. That follows the core design, but a user who adds dissolve_time alone
  sees the scene vanish for good. **Suggestion for the owner:** document it in the module, or default Disrecover > 0
  when dissolve_time is in the stack.
* velocity_streak reads state velocity, which only force-mode modules (curl / wind / release / push force) create.
  Kinematic movers (jitter, glitch, wave...) give no streak.
* dissolve_noise progress 0.5 dissolved 4 % of this scene (X9 on the unit sphere: 44 %). Noise scale 2 on a small
  scene (pinata about 0.15 x 0.7 units) sits in one part of the noise field. Progress 0.8 dissolved all of it.
* Test-only ops made on b3 (`px_verify_ctl` Constant CHOP, `px_verify_mask` Ramp TOP) were removed afterwards.
  `Audiochop` and `Disrecover` were reset, the stack was emptied, and PX on b3 is parked again. The main TD was only
  touched for the one read-only `.save()`. Nothing named the sorter.
