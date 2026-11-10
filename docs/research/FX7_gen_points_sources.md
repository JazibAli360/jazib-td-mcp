# FX7: GEN_points sources and verified maths (26 Oct 2026, offline research, nothing run in TD)

Feeds the generator COMP `GEN_points` (additive point looks): modules density2d, attractor3d, streamlines, form,
flame, lsystem, graph, sparkle. Web + repo reading + numpy checks run here (our own scripts, not in TD). Tags: [V2]
read in 2+ sources, [V1] one source, [NUM] checked by our own numpy run (RK4, 3 seeds, 400 time units), [MEM] from
memory or UNVERIFIED. Licence rule (user): licence is irrelevant for STUDY, but note the source; maths is free, GPL
code is not copied.

## 1. Summary

- **density2d / flame / attractor3d share one engine:** N independent particle states in an rgba32f compute GLSL TOP
  (T-46/T-47 form), deposit as 1-px additive points into a 32F Render TOP (the GN_physarum path, T-112: exact sums, no
  atomics), then a log-density tonemap GLSL TOP. Only the per-point update shader and the camera differ. No POP loop,
  so the F11 crash class is avoided.
- **density2d:** Clifford, de Jong, Svensson, Bedhead, Fractal Dream: 14 + 10 + 4 + 5 + 4 parameter sets below, all
  checked chaotic (Lyapunov > 0) and bounded. Bounds are analytic for Clifford/de Jong/Svensson/Fractal Dream; Bedhead
  needs a percentile box (it reached +-10).
- **attractor3d:** 11 ODE systems with parameters, a safe dt (RK2 midpoint is enough for most), centre and extent in
  section 3.2. Three traps found: Thomas coexisting attractors + an invariant diagonal, Rabinovich-Fabrikant is not
  globally bounded (needs warm seeds + respawn guard), Halvorsen a=1.89 appears on one non-academic page only.
- **flame:** Draves variations 0-17 written out (cross-checked: paper-derived Wikipedia, blog and flam3 source),
  colour index c = (c + ci)/2, log-density + gamma + vibrancy tonemap, Electric Sheep morph = interpolate genomes
  after rotating the affine part. flam3 is GPL: maths only.
- **streamlines:** divergence-free analytic curl field (sum of sines) or Noise POP `NoiseCurl` (O F5); Hobbs'
  flow-field rules (short curves = fur, long = fluid, continuous angle noise = no crossing). **form:** Trapcode Form
  feature map (section 3.5) onto Grid POP + glslPOP/Noise POP. **lsystem:** 8 rule sets verified by running them;
  `lsystemSOP` exists in 31550 (256-char rules, 30 generations); L-System POP (Alaghast) needs 2025.33070+. **graph:**
  Fruchterman-Reingold, brute-force N <= ~2-4k on the GPU, edges by Proximity POP or a link table. **sparkle:** own
  clean-room star sprite.

## 2. Sources

- Paul Bourke, Clifford attractors | https://paulbourke.net/fractals/clifford/ | not stated (c) Bourke | equation, 7
  sets, histogram method
- Paul Bourke, Peter de Jong | https://paulbourke.net/fractals/peterdejong/ | not stated | equation, 9 sets, Svensson
  variant + "one ring"
- Paul Bourke, bad hair day 2D map | https://paulbourke.net/fractals/2dmap/ | not stated | 14-parameter general map,
  14 sets (not used)
- Bourke Sprott / Chen-Lee pages | https://paulbourke.net/fractals/sprotta , /chenlee | not stated | credit only;
  equations are images (unread)
- HoloViz "Visualizing Attractors" | https://examples.holoviz.org/gallery/attractors/attractors.html | BSD-3 [MEM] |
  Bedhead + Fractal Dream maps, sets
- dynamicmath strange attractors | https://www.dynamicmath.xyz/strange-attractors/ | not stated | 12 ODEs + parameters
  (the page the Derivative tutorial links)
- Derivative "Tutorial 06 Strange attractors (POPs)", ETCH-01, 16 Aug 2025 |
  https://derivative.ca/community-post/tutorial/touchdesigner-tutorial-06-strange-attractors-pops/72620 | none stated
  | POP math route; page has no equations, links dynamicmath + Function Store tools
- Attraktors Creator (free lite) / Designer (Patreon), JiveFaury |
  https://derivative.ca/community-post/attractors-designer-v07-tutorial-1-interface-and-features/66287 | not stated /
  proprietary | prior art only, pos/vel textures (repo: community/top_assets_04.md rows 315, 404)
- Reddit "Moving sands", 10 M attractor particles in POPs | repo popular/reddit.md #16 | Patreon | scale proof only
- Wikipedia: Thomas attractor, Rossler, Rabinovich-Fabrikant, L-system, Fractal flame, Force-directed drawing |
  en.wikipedia.org | CC BY-SA (text); equations are facts | equations, bifurcation values, rule sets
- Draves & Reckase, "The Fractal Flame Algorithm" (2003/08) | https://flam3.com/flame_draves.pdf (23 MB, not parsed) |
  paper, free to read | algorithm; formulas taken via flam3 source + Wikipedia
- flam3 `variations.c`, `rect.c` | https://github.com/scottdraves/flam3 | **GPL-3+** (Debian copyright) | MATHS ONLY,
  no code copied
- Electric Sheep | https://en.wikipedia.org/wiki/Electric_Sheep | client GPL | morph idea only
- Fractorium wiki (Flame tab) | git.speice.io mirror of fractorium Data/Wiki/FlameTab.htm | GPL-3 [MEM] | meaning of
  gamma threshold, vibrancy, highlight power
- Tyler Hobbs, "Flow Fields" | https://www.tylerxhobbs.com/words/flow-fields | none stated | rules of thumb (ideas)
- Bridson, Hourihan, Nordenstam, "Curl-noise for procedural fluid flow", SIGGRAPH 2007 |
  https://www.cs.ubc.ca/~rbridson/docs/bridson-siggraph2007-curlnoise.pdf | paper | curl of a potential; PDF not
  parsed, formula from memory
- Fruchterman & Reingold 1991 | https://www.reingold.co/force-directed.pdf | paper | f_a = d^2/k, f_r = k^2/d
- Maxon/Red Giant Trapcode Form help | https://help.maxon.net/rg/en-us/Content/html/Cat_Form.html | proprietary |
  feature NAMES only (39 topics)
- Nuke Glint node doc | https://learn.foundry.com/nuke/Content/reference_guide/draw_nodes/glint.html | proprietary |
  controls (ray count, length, threshold)
- Alaghast L-System POP / Voronoi POP | https://github.com/Alaghast/L-System-POP | "proprietary freeware" | not
  usable: needs 2025.33070+ (N_community)
- prismatic, "Procedural Plants with L-Systems" (Feb 2022, L System SOP + tox) | derivative.ca community post | not
  stated | prior art
- Prior art searched, not found | Shadertoy Clifford / flame density, TD flame / force-graph / Clifford tox | none
  found (search returned nothing)

## 3. Maths per module

### 3.1 density2d (2D maps, iterate (x,y) -> (x',y'), accumulate hits, display log-density)
Maps ([V2] Bourke + HoloViz unless noted; bounds are exact bounds of the map):
- Clifford: x' = sin(a y) + c cos(a x); y' = sin(b x) + d cos(b y). |x| <= 1+|c|, |y| <= 1+|d|.
- de Jong: x' = sin(a y) - cos(b x); y' = sin(c x) - cos(d y). |x|,|y| <= 2.
- Svensson (Bourke, HoloViz): x' = d sin(a x) - sin(b y); y' = c cos(a x) + cos(b y). |x| <= |d|+1, |y| <= |c|+1.
- Fractal Dream [V1 HoloViz]: x' = sin(b y) + c sin(b x); y' = sin(a x) + d sin(a y). |x| <= 1+|c|, |y| <= 1+|d|.
- Bedhead [V1 HoloViz; also Bourke "bad hair day" family]: x' = y sin(x y / b) + cos(a x - y); y' = x + sin(y)/b. Not
  bounded analytically (seen +-10): box from percentiles. Guard b near 0. Start (1,1).
Parameter sets (a,b,c,d), [NUM]: Lyapunov (log per iteration, 20000 its) is > 0 for all of them (0.12 to 1.5); occ =
fraction of a 256^2 grid (0.05-99.95 percent box) hit by 2.4 M points, a 'how filled' hint:
- Clifford (Bourke #1-#7): (-1.4,1.6,1.0,0.7) L.29 occ.52 | (1.6,-0.6,-1.2,1.6) L.17 .19 | (1.7,1.7,0.6,1.2) L.35 .57
  | (1.5,-1.8,1.6,0.9) L.45 .83 | (-1.7,1.3,-0.1,-1.2) L.20 .30 | (-1.7,1.8,-1.9,-0.4) L.62 .50 |
  (-1.8,-2.0,-0.5,-0.9) L.36 .80. HoloViz extras: (-1.9,-1.9,-1.9,-1.0) .81 | (0.75,1.34,-1.93,1.0) .41 |
  (-1.32,-1.65,0.74,1.81) .66 | (-1.3,-1.3,-1.8,-1.9) .83 | (1.7,0.7,1.4,2.0) .50 | (0.77,1.99,-1.31,-1.45) .52 |
  (1.1,-1.32,-1.03,1.54) .42.
- de Jong (Bourke): (1.641,1.902,0.316,1.525) .23 | (0.970,-1.899,1.381,-1.506) .34 | (1.4,-2.3,2.4,-2.1) .73 |
  (2.01,-2.53,1.61,-0.33) .43 | (-2.7,-0.09,-0.86,-2.2) .29 | (-0.827,-1.637,1.659,-0.943) .24 |
  (-2.24,0.43,-0.65,-2.43) .12 | (-2,-2,-1.2,2) .61 | (-0.709,1.638,0.452,1.740) .48 | HoloViz
  (-1.244,-1.251,-1.815,-1.908) .59.
- Svensson: "one ring" (1.40,1.56,1.40,-6.56) (Bourke, Johnny Svensson; x spans +-7.56, wide thin ring, L 1.5, occ
  .77) | (-1.78,1.29,-0.09,-1.18) .25 | (1.5,-1.8,1.6,0.9) .84 | (-0.91,-1.29,-1.97,-1.56) .34.
- Fractal Dream (a,b,c,d), start (0.1,0.1): (-2.8276,1.2813,1.9655,0.597) .80 | (-1.9956,-1.4528,-2.6206,0.8517) .83 |
  (-0.966918,2.879879,0.765145,0.744728) .34 | (-1.1554,-2.3419,-1.9799,2.1828) .93.
- Bedhead (a,b): (0.06,0.98) .45 [box +-6] | (-0.81,-0.92) .32 | (-0.64,0.76) .42 [+-9] | (-0.67,0.83) .37 |
  (0.64,0.76) .59 [+-10] (HoloViz default).
Good fits for a "lace/smoke" look: low occ (.12-.3) sets; "dust" look: occ > .7. Start at (0.1,0.1), discard 20-100
iterations, seed N points near the start with tiny jitter (they separate in ~20 iterations, Lyapunov > .15).
Display (Bourke: histogram, colour in a second step; log scaling is general practice): H = hit count per pixel,
`v = ln(1 + e*H) / ln(1 + e*Href)`, `out = palette(pow(v, 1/gamma))`, Href = a running max (Lag) or a fixed par.
2 M points on 1080x1920 give ~1 hit per pixel on a filled map: use the section 4 deposit (physarum path).

### 3.2 attractor3d (ODEs; [NUM] = our RK4 runs, 3 seeds x 400 time units)
Equations (source: dynamicmath [V1]; second source in brackets). Units: dx/dt etc.
- Lorenz: x'=s(y-x); y'=x(r-z)-y; z'=xy-bz. s=10 r=28 b=8/3 [V2 dynamicmath, standard; matches repo slice_08 note].
- Thomas: x'=sin y - b x; y'=sin z - b y; z'=sin x - b z [V2 Wikipedia]. b=0.19 calm; 0.208186 = onset of chaos
  (Wikipedia).
- Aizawa (dynamicmath calls it "Langford (a.k.a. Aizawa)"): x'=(z-b)x-d y; y'=d x+(z-b)y; z'=c+a z-z^3/3-(x^2+y^2)(1+e
  z)+f z x^3. a=.95 b=.7 c=.6 d=3.5 e=.25 f=.1 [V1].
- Halvorsen: x'=-a x-4y-4z-y^2; y'=-a y-4z-4x-z^2; z'=-a z-4x-4y-x^2 [V2 form: UMN/arXiv use it with a=1.4;
  dynamicmath a=1.89, which only a non-academic gallery repeats]. Cyclic symmetry, 120 deg about (1,1,1).
- Dadras: x'=y-a x+b y z; y'=c y-x z+z; z'=d x y-e z. a=3 b=2.7 c=1.7 d=2 e=9 [V2 dynamicmath + arXiv 2606.24824
  (h=e)].
- Chen (1999, ORIGINAL): x'=a(y-x); y'=(c-a)x-x z+c y; z'=x y-b z. a=35 b=3 c=28 [MEM, NUM chaotic L+2.0].
- Chen-Lee: x'=a x-y z; y'=b y+x z; z'=c z+x y/3. a=5 b=-10 c=-0.38 [V1 dynamicmath]. **dynamicmath labels this
  "Chen"; it is the Chen-Lee system (Chan & Lee 2004, Bourke credit); the `attractors` package lists Chen and Chen-Lee
  separately.**
- Rossler: x'=-(y+z); y'=x+a y; z'=b+z(x-c). a=.2 b=.2 c=5.7 [V2 Wikipedia]; (0.1,0.1,14) is also standard.
- Sprott: x'=y+a x y+x z; y'=1-b x^2+y z; z'=x-x^2-y^2. a=2.07 b=1.79 [V2 dynamicmath + arXiv 2604.11929/MathWorks, IC
  (0.63,0.47,-0.54)]. Lyapunov only +0.005..0.023 in our run: weakly chaotic or quasi-periodic, UNVERIFIED.
- Rabinovich-Fabrikant: x'=y(z-1+x^2)+g x; y'=x(3z+1-x^2)+g y; z'=-2z(al+x y) [V2]. Pairs: al=.14 g=.10 (dynamicmath;
  **Wikipedia says stable limit cycle**), al=.98 g=.1 (chaotic per Wikipedia citing Danca & Romera), al=1.1 g=.87 IC
  (-1,0,.5) (Wikipedia main example, corr. dim 2.19).
- Three-Scroll unified: x'=a(y-x)+d x z; y'=b x-x z+f y; z'=c z+x y-e x^2. a=32.48 b=45.84 c=1.18 d=.13 e=.57 f=14.7
  [V1].
- Wang-Sun four-wing: x'=a x+y z; y'=b x+c y-x z; z'=-z-x y. a=.2 b=.01 c=-.4 [V1].
- Lorenz-83: x'=-a x-y^2-z^2+a f; y'=-y+x y-b x z+g; z'=-z+b x y+x z. a=.95 b=7.91 f=4.83 g=4.66 [V1].
Numbers ([NUM]; "RK2" = midpoint gave the same extents at that dt; centre = mean; half = max |p - centre| per axis;
rmax = max distance from centre, use 1/rmax as the unit-size scale):

| system | seed IC | dt RK4 / RK2 | centre | half-extent xyz | rmax | note |
|---|---|---|---|---|---|---|
| Lorenz | (1,1,1) | .01 / .01 | (0,0,23.6) | 19.4, 26.6, 23.2 | 33.5 | L+0.91 |
| Thomas b=.19 | (.1,0,0) | .1 / .1 | (0,0,0) | 4.1 | 4.6 | L+.04; b=.17 -> 4.33 |
| Thomas b=.208186 | (.1,0,0) | .1 / .1 | (1.9,1.9,1.9) | 3.0 | 4.0 | **mirror pair**: seed (-1,.5,.2) -> (-1.9,..) |
| Aizawa | (.1,0,0) | .02 / .02 | (0,0,.70) | 1.5, 1.5, 1.1 | 1.5 | z in [-.37,1.85] |
| Halvorsen a=1.89 | (-1.48,-1.51,2.04) | .01 / .01 | (-2.64,..) same 3 | 9.5 each | 12.8 | [-12.1,6.3]; L+.02 weak |
| Halvorsen a=1.4 | same | .01 | (-3.09,..) | box [-13.3,6.4] | 13.2 | L+.59 (stronger chaos) |
| Dadras | (1.1,2.1,-2) | .005 / .005 | (.94,-.20,.32) | 17.8, 11.2, 14.1 | 22.9 | L+.42; stiff, dt .01 distorts |
| Chen 35/3/28 | (-3,2,20) | .005 / .005 | (0,0,23.8) | 26.4, 30.7, 27.4 | 40.8 | L+2.0 |
| Chen-Lee | (1,1,1) | .01 / .01 | (0,0,8.2) | 21.6, 18.7, 10.6 | 25.6 | L+.43 |
| Rossler | (1,1,1) | .05 / .05 | (.17,-.85,.86) | 11.2, 9.9, 21.9 | 22.8 | z in [0,22.8] |
| Sprott | (.63,.47,-.54) | .01 | (.64,0,0) | 1.1, 1.1, 1.0 | 1.2 | weak L |
| RF .14/.10 | (-1,0,.5) | .005 | (-.66,.05,.50) | 1.8, 2.5, 1.0 | 2.8 | bounded only near this IC |
| Three-Scroll | (-.29,-.28,.28) | .001 / .002 | (0,0,123.7) | 101, 160, 116 | 168 | very fast, dt must be tiny |
| Wang-Sun | (.3,-.4,-.1) | .05 | (0,.06,0) | 3.2, 3.0, 2.7 | 4.2 | L+.12 |
| Lorenz-83 | (1,1,1) | .01 | (1.15,-.06,.5) | 2.7, 3.4, 3.2 | 4.3 | L+.016 |

Traps ([NUM]): (1) Thomas x=y=z is an invariant line (IC (1,1,1) sits still at 2.58 for every b): never seed on a
symmetric grid; at b=.208 two mirrored attractors coexist, so seed both signs or the look is lopsided; b=.19 is the
origin-centred one. (2) Rabinovich-Fabrikant is not globally bounded: 29/60, 54/60, 39/60 random ICs in [-1,1]^3
escaped (|p| > 50) for the three pairs above, and 400 particles at +-0.1 of an IC blew up too: seed from a warmed-up
orbit and add `|p| > R or NaN -> respawn` (FX5 G03 already asks for this guard). (3) Stiff systems (Dadras,
Three-Scroll, Chen): use substeps, not a bigger dt; time speed par = dt x substeps per frame. (4) The repo's slice_08
note 'Lorenz 10 20 3/8' is wrong: rho = 28 (dynamicmath, Wikipedia-standard).

### 3.3 flame (Draves & Reckase; chaos game on N parallel points)
- Point (x,y,c), c in [0,1] a palette index. Each iteration pick xform i with probability w_i, apply `F_i(x,y) = P_i(
  sum_j v_ij V_j(A_i (x,y)) )` (A_i, P_i affine, v_ij weights [V2 blog + Wikipedia]), then `c = (c + c_i)/2` [V2
  Wikipedia + paper]. A final xform is applied for plotting only, not fed back [MEM]. Discard the first ~15-20
  iterations of a fresh point [MEM: paper 20, flam3 15]. Plot (x,y) with colour palette(c) additively.
- Variations (r = sqrt(x^2+y^2), th = atan2(x, y) with x FIRST, phi = atan2(y, x)) [V2 flam3 source + Draves paper via
  blog/Wikipedia for V0-2, 13, 17; w = weight; (a..f) = coefficients of the xform's affine A]: V0 linear (x, y) | V1
  sinusoidal (sin x, sin y) | V2 spherical (x, y)/(r^2) | V3 swirl (x sin r^2 - y cos r^2, x cos r^2 + y sin r^2) | V4
  horseshoe ((x-y)(x+y), 2xy)/r | V5 polar (th/pi, r-1) | V6 handkerchief r (sin(th+r), cos(th-r)) | V7 heart r (sin(r
  th), -cos(r th)) | V8 disc (th/pi)(sin(pi r), cos(pi r)) | V9 spiral (cos th + sin r, sin th - cos r)/r | V10
  hyperbolic (sin th / r, r cos th) | V11 diamond (sin th cos r, cos th sin r) | V12 ex: p0 = sin(th+r)^3, p1 =
  cos(th-r)^3, r (p0+p1, p0-p1) | V13 julia sqrt(r) (cos(th/2 + W), sin(th/2 + W)), W = 0 or pi, 50 percent each | V14
  bent: x' = 2x if x < 0, y' = y/2 if y < 0, else unchanged | V15 waves (x + b sin(y/c^2), y + e sin(x/f^2)) | V16
  fisheye 2/(r+1) (y, x) | V17 popcorn (x + c sin(tan 3y), y + f sin(tan 3x)). flam3 adds a small epsilon to divisors
  (r^2 + eps). Dependent variations (15, 17) use the xform's coefficients. V24 PDJ (sin(p1 y) - cos(p2 x), sin(p3 x) -
  cos(p4 y)) [V1 blog] is de Jong inside a flame.
- Display (Wikipedia: alpha = ln(count)/ln(max), colour x alpha^(1/gamma), gamma > 1; flam3 `rect.c`, summarised not
  copied): per bucket with density A3 (A_rgb accumulated colour): `L = k1 ln(1 + k2 A3) / A3`, `A' = L A`; normalised
  D = A3'/P; `alpha = D^(1/gamma)` (flam3 adds a linear ramp below a "gamma threshold", exact curve UNVERIFIED);
  vibrancy v mixes the two colour paths: `rgb_out = v * rgb' * alpha / D + (1 - v) * 256 * (rgb'/P)^(1/gamma)`;
  background adds `(1 - alpha) B` (or divide by alpha for a transparent output). Vibrancy 1 = saturated, 0 = washes
  toward white (Fractorium wiki). Sample genome values in flam3 `test.flam3`: brightness 4, gamma 4, vibrancy 1. Our
  port: tonemap GLSL TOP with `exposure` (= k1), `k2` as density scale, `gamma`, `vibrancy`, `highlight` (optional).
- Electric Sheep morph: flam3 README "sequence" = each flame rotates its xforms 360 deg ("fractal rotation"), then
  transitions smoothly to the next genome; so animate by rotating the affine part (A_i columns) at a steady speed and
  linearly interpolating weights, coefficients and palette between two table rows. Padding of unequal xform counts and
  the loop/edge seam: UNVERIFIED (docs not read).
- 4 M points x several iterations per frame is the budget question, see section 4 (deposit 3.8 ms per 1 M points).

### 3.4 streamlines (curl-noise flow field agents)
- Stream function psi(x,y,t); `v = (dpsi/dy, -dpsi/dx)` is exactly divergence-free [V2 Bridson 2007 idea, derivation
  trivial: v_x,x + v_y,y = psi_yx - psi_xy = 0]. 3D: v = curl of a vector potential (3 noise fields, offset seeds).
- Cheap analytic psi, no noise op: psi = sum_k a_k sin(k_k . p + w_k t + ph_k), k = 3-8 waves, |k| log-spaced: dpsi is
  a sum of cosines, exact, GLSL-cheap. Or Noise POP `NoiseCurl` (float3) / `NoiseCurl2` (float2) (O F5, translate 4D =
  time).
- Agents: p += v dt; age; respawn at random when age > life or outside the frame. Draw: Trail POP strips (POP.md 4.2)
  or a feedback decay. Hobbs rules [V1]: grid spacing ~0.5 percent of width, step 0.1-0.5 percent; short curves (fur,
  rough) when colour varies a lot, long curves (fluid, leading lines) for subtle palettes; continuous angle distortion
  keeps curves from crossing, quantised angles (multiples of pi/10 or pi/4) or per-row random angles give
  rocky/chaotic looks; min spacing by collision test (skip: costs, use circle-packed starts instead).

### 3.5 form (Trapcode Form look, features from the Maxon help TOC, 39 topics)
Form groups [V1, Maxon help TOC]: Base Form (String, 3D Model/OBJ; Box-Grid, Sphere etc. from memory, not in the TOC
page), Particle (type, glow, streaklet, texture, rotation), Shading (shadowlet), Layer Maps, Audio React, Disperse and
Twist, Fluid, Fractal Field, Spherical Field, Kaleidospace, Transform, Visibility, Rendering (motion blur). Our maths:
- Base grid P0 (Grid POP / sphere / file POP). Layer map: sample a TOP at uv(P0): `P = P0 + n * (luma - .5) * amp`,
  colour and size from the map. Fractal field: `d = sum_o g^o noise3(f l^o P0 + flow * t + offs)`, o = 0..octaves-1,
  then `P += d * disp`. Spherical field: `P += normalize(P - c) * s * falloff(|P - c|/R)` (push), falloff =
  smoothstep.
- Disperse: `P += disp * (hash3(id) - .5)`; Twist: rotate P about an axis by `ang = twist * dot(P - c, axis)`. Audio
  react: band level -> amp / disp / size through a 2 s Lag (FX5 notes the same clamp).
- FX4 G-FORM already scopes this as a PX source preset pack; in GEN_points it is the same GLSL MAT deposit reading P0
  + a small uniform set, no state texture needed (P0 is analytic from the grid index).

### 3.6 lsystem (rules verified by running them, numpy turtle; Wikipedia rule sets [V1], Hilbert/Gosper [MEM] then run)
Turtle: F/G/A/B draw (Hilbert A,B do NOT draw), + turn left, - turn right, [ push, ] pop, X/other = no draw.
- Koch: F -> F+F-F-F+F, 90 deg, axiom F (n=3: 125 segs).
- Sierpinski arrowhead: A -> B-A-B, B -> A+B+A, 60 deg, axiom A (n=6: 729 segs, 730 distinct points = a path, ok).
- Sierpinski triangle: axiom F-G-G, F -> F-G+F+G-F, G -> GG, 120 deg.
- Dragon: F -> F+G, G -> F-G, 90 deg, axiom F (n=10: 1024 segs).
- Hilbert (draw F only; A -> +BF-AFA-FB+, B -> -AF+BFB+FA-, 90 deg, axiom A): n=4 gives 255 = 4^4-1 segs, 256 distinct
  points on a 16 x 16 grid: space-filling confirmed.
- Gosper (A,B both draw): A -> A-B--B+A++AA+B-, B -> +A-BB--B-A++A+B, 60 deg: n=3 -> 343 = 7^3 segs.
- Fractal plant: axiom -X, X -> F+[[X]-X]-F[-FX]+X, F -> FF, 25 deg (n=5: 1488 segs, 6264 chars). Binary tree: 1 ->
  11, 0 -> 1[0]0 (45 deg, Wikipedia) or the symmetric 0 -> 1[+0]-0 (n=6: 256 segs).
- TD: `lsystemSOP` exists in 31550 (skeleton|tube, <= 30 generations, rules <= 256 chars; SOP_MAT.md) and SOP->POP via
  `soptoPOP`; or Python rewrite + turtle once per rule change (FX5 G05 plan, 1-5 ms for <= 200k segs), segments to a
  table or POP and drawn as lines/points. Growth: clip by segment order; sway: noise offset by depth.

### 3.7 graph (force-directed constellation)
Fruchterman-Reingold [V2 Wikipedia/Boost/graph-tool]: attractive f_a = d^2/k on edges, repulsive f_r = k^2/d on all
pairs, `k = C sqrt(area/n)` (C ~ 1), displacement clamped by a temperature that cools each step. N^2 repulsion is fine
to ~1000 nodes in a few ms on a CPU; on the GPU brute force 2-4 k nodes is 4-16 M pairs (cheap on M1 Max, UNVERIFIED
here). Edge sources: distance threshold (Proximity POP, POP.md R5 recipe) or a link table. Neighbor POP inside a
feedback loop is unproven (O F4, F11); pairwise brute force in one glslPOP/compute pass avoids it. Draw edges with
distance fade, nodes as sparkle sprites.

### 3.8 sparkle (own clean-room design, no source found)
- Twinkle: `b_i(t) = pow(.5 + .5 sin(2pi (f_i t) + ph_i), p)`, p 6-24 (sharper = rarer glints), f_i, ph_i = hash(id).
- Star sprite on a quad (not a 1-px point): `q = rot(a_i) * (uv - .5)`; `core = exp(-|q|^2 / s0^2)`; `spike =
  exp(-|q.x| / w) * exp(-|q.y| / h)` with w >> h; 4-point = spike(q) + spike(q.yx), 8-point adds a 45 deg copy at .5
  gain; `rgb += tint_i * (core + g * spike) * b_i`, additive. Nuke Glint's controls (ray count, length, threshold) map
  1:1: ray count, `w`, brightness threshold on the source TOP luma for "glint where it is bright".
- Variants: colour from a ramp by hash; size by depth; trails off. Cost = quad count x fill; stays small for <= 50 k
  stars.

## 4. How this repo already draws points

- **GN_physarum (T-112, builders/physarum.py ~line 449, builders/glsl/ph_deposit_vertex.glsl):** a Grid POP
  (`surftype` points, side x side) is exposed to a Geometry COMP by a Select POP (`pop` = '../pts'); a GLSL MAT
  (`dep_mat`) reads the state texture with `sampler0top` and writes `gl_Position` from `texelFetch`, `gl_PointSize =
  1.0`; `blending` on with `srcblend/destblend/srcblenda/destblenda = one`, depth test and write off; Render TOP
  rgba32float, aa1. **Read the position with `TDPos()` (`TDPos().xy + 0.5` = grid uv); raw `P` rendered garbage (4 px
  of 0.7).** Result: 262144 points, sum 262144, per-cell max diff 0 vs numpy add.at. Unused slots go to clip space
  (2,2,0,1).
- **Cost (same note):** the Render TOP CPU side is the floor (Rosetta): deposit 2.2 ms at 262 k (GPU 0.6), 3.8 ms at 1
  M; whole COMP 4.4 / 6.4 ms (8.0 ms with a 1080x1920 trail). FX5's "1 M points ~ 2 ms" for G03 and "2 M ~ 2-3 ms" for
  G04 were design guesses, now low: budget 4 ms per 1 M points and ~8 ms for 2 M, UNVERIFIED for these shaders.
- **State:** compute-mode GLSL TOP is clean (T-47: 441/441 at 1080x1920 16F, 340/340 at 256^2 32F:
  `TDImageStoreOutput(0, ivec3(gl_GlobalInvocationID), c)`, `local_size 8x8`, custom resolution par); pixel-mode
  multi-pass tears (T-46, 0/328). State carried with a Feedback TOP whose `top` is the end Null (O F10: `npasses` for
  substeps; later inputs stay constant per pass). In-place read-write of own output across frames: untested (BO V2).
  1-pixel-high 32F strips are fine as data containers (tutorials/slice_08).
- **BO_particles (builders/particles.py, docs/builds/particles.md, BO_particle_sims.md 4):** engine B = compute TOP
  state + instanced GLSL MAT render (`TDInstanceID()` -> texelFetch); the POP engine A is not built. Instancing from a
  POP: Geometry COMP `instanceop`, NOT `instancepop` (that is the pivot) (T-15). T-15 proved only the minimal chain
  Point Generator POP -> Particle POP -> Select POP, Point Sprite MAT, Render TOP.
- **PX_pointfx (BR, docs/builds/px.md):** additive glow needs no sort; instanced quads with a soft-disc/splat/streak
  GLSL MAT; DOF as per-point CoC size; log/exposure grade in post. Reuse for sparkle and form.
- **POP loop rule (O F11):** Feedback POP + Null target crashed on macOS (32260, hotfix 32280); keep loops in a
  scratch COMP, no viewers inside, never `progressiveUnload` a Particle POP container. Hence the recommended
  state-texture engine.
- **Ops that exist in 31550 (POP.md dump):** linePOP, trailPOP, proximityPOP, neighborPOP, copyPOP, skinPOP, glslPOP /
  glsladvancedPOP / glslcopyPOP (outputs uninitialised unless `initoutputattrs`), noisePOP (`NoiseCurl`). Not present:
  Triangulate, Voronoi, Text, L-System POPs; `lsystemSOP` is present. Palette has `particlesGpu` (compute particles).
- **Analyze/stats chains update only while pulled (T-112 item 6):** a log-tonemap max-count normaliser needs a pulled
  Analyze TOP, or use a fixed exposure par; auto-exposure = slow Lag of the pulled max.

## 5. Open / unverified

- Draves paper PDF (23 MB) and Bridson PDF not parsed (tools returned binary/too large); flame formulas rest on flam3
  source + Wikipedia + a blog, curl-noise on derivation. Warm-up count (15 vs 20), final-xform semantics, the flam3
  gamma-threshold ramp, the Electric Sheep loop/edge seam and padding rule: UNVERIFIED.
- Bourke's Sprott and Chen-Lee equations are images (unread); Sprott's a=2.07 b=1.79 system is [V2] (arXiv +
  MathWorks) but only weakly chaotic here; Chen-Lee [V1]; Wang-Sun, Three-Scroll, Lorenz-83, Aizawa, Halvorsen a=1.89
  [V1].
- Rabinovich-Fabrikant: dynamicmath's al=.14 g=.10 vs Wikipedia "stable limit cycle"; our Lyapunov estimate +.03 is
  inconclusive. Treat as a decorative orbit, not a proof of chaos. al=1.1 g=.87 not reproduced in a stable form by our
  RK4.
- Chaos claims use a two-trajectory Lyapunov estimate (60-300 time units); weak values (< .05) are not proof.
- Trapcode Form: base-form names beyond String and OBJ are from memory; Form's exact fractal-field formula is
  proprietary, section 3.5 is our equivalent, not a copy.
- No Shadertoy example for Clifford/flame density found (search returned none); no TD flame / force-graph / Clifford
  tox found: all of those modules start from the maths here.
- Perf and GPU feasibility (4 M points per frame, 2-4 k node brute force, `npasses` substeps) unmeasured: use the E
  method (frame pump, count cooks) before promising a number; one-item pilot first (Clifford, one state pass).
- HoloViz licence (BSD-3) and Fractorium (GPL-3) from memory; no code from either is needed.

