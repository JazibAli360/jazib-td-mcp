# T - Real-time ML / AI visuals on this Mac (research, 16 Oct 2026)

Agent T for the lead. Target machine: M1 Max 32-core GPU (64 GB per BRIEF), TD 2025.31550 = Intel build under Rosetta (Python 3.11 x86_64), vertical 1080x1920, TD -> Resolume Arena 7.23.2 over Syphon/NDI. Show: Sat 24 Oct 2026 (8 days).
Research only: nothing installed, downloaded, generated or run; TD, Arena, Syphon and the camera were not touched. Web search and fetch only.
Notation: **cited** = a URL is given; **local** = read from this repo; **UNVERIFIED** = snippet only, memory, vendor claim, or a gap I could not close. **No fps figure in this file was measured on this M1 Max** except where "local" says td-port measured it (and those were outside TD). Where I give an expectation for the M1 Max it is labelled as inference.
Limit hit: the shared web-search budget ran out mid-run (style-transfer fps, Apple Vision doc pages, RAFT/Apple-silicon fps stayed open). Apple developer doc pages returned only their titles to the fetch tool, so Vision API details are marked UNVERIFIED unless a WWDC/third-party page confirmed them.
Not repeated from `D_camera_mediapipe.md`: the MediaPipe web plugin, camera permission issue, Windows-only TD ops, Farneback recipe, OpenCV/Python inventory, TDLidar, CoreML Syphon Bridge basics, and the `jzb_camera_bridge` description. They are referenced as "D §n" and extended here.

---

## 1. Summary

1. **Real-time diffusion img2img on this Mac is possible but marginal, and not published for an M1 Max.** The only hard numbers are an M3 Ultra (60-core GPU): SD-Turbo 512x512 via PyTorch MPS 95.8 ms/frame (10.4 fps); Core ML UNet 53.2 ms; whole camera pipeline 13.8 fps; the smaller SDXS-512 reaches 22.7 fps; the same author's README lists an M4 Max (40-core) at **15.4 fps measured** and gives M1/M2/M3 Max a **12-18 fps estimate** ([paper](https://www.alphaxiv.org/abs/2605.16259.md), [repo](https://github.com/ochyai/streamdiffusion-mac)). Inference: an M1 Max is older and smaller than the M4 Max, so SDXS-512 there is likely at or below ~15 fps and SD-Turbo below ~14 fps. UNVERIFIED until someone runs it.
2. **It fights TD for the GPU.** Diffusion UNets run on the GPU (Neural Engine made the UNet 19% to 6.2x slower; parallel Core ML instances gave no gain because of Metal command-queue serialisation, same paper). TD's own render at 7488x2880 is GPU-bound ([E_live_rig.md](E_live_rig.md): heavy look 24.6 fps at 7488x2880). One machine cannot have both at full rate. Plan a budget or a second machine.
3. **DotSimulate StreamDiffusionTD does have a Mac path** (Apple Silicon "supported and builtin installation", Homebrew Python 3.11, "inference speeds are not as fast ... TensorRT is not supported on mac", 0.2.6 changelog; 0.2.99 adds a cloud backend and "better support for 5xxx and mac") but only as **search snippets of Patreon posts I could not open (403)**. Paid Patreon .tox, closed source, licence UNVERIFIED, never tested under Rosetta TD. Do not download (guardrail).
4. **The cheap, solid wins are not diffusion.** On this Mac, measured (outside TD, by td-port): Vision Fast person mask 33 ms round trip (~32/s), Depth Anything V2 Small 66.7 ms round trip (~15 maps/s), Vision faces 17-70 ms. Apple lists Depth Anything V2 Small F16 at **32.8 ms on an M1 Max** (Neural Engine) ([Apple model page](https://huggingface.co/apple/coreml-depth-anything-v2-small)), so there may be headroom vs. td-port's 53.9 ms compute (cause UNVERIFIED).
5. **Style transfer is the best "AI look" per millisecond:** Apple Create ML trains a video-optimised style network in "a few minutes" from one style image; the model is under 1 MB; Apple says up to 120 fps on an A13 and runs on the Neural Engine ([WWDC20 10642](https://developer.apple.com/wwdc20/10642)). No M1 Max fps found: UNVERIFIED, but it is the one candidate that leaves the GPU free and can be trained on PRISM art.
6. **Infeasible live here:** SDXL / SDXL-Lightning / FLUX class (SDXL-class UNet >200 ms on an M3 Ultra; mflux FLUX schnell 1024x1024 2-step ~55 s on an M1 Max), Real-ESRGAN upscaling (~1-1.3 s/frame on an M4), SAM 2 (prompt-driven, no Mac real-time number), RAFT (no Mac number; OpenCV flow is enough), pix2pix-turbo (3-4 fps).
7. **Architecture:** native arm64 helper (td-port pattern) is right; Rosetta TD must not host torch/onnx/mediapipe (D §3.2). Two transport choices: the existing socket (frames through TD Python, 15-30 maps/s measured outside TD, TD-side upload cost unmeasured) or Syphon in/out like the CoreML Syphon Bridge (zero-copy, "+2 ms overhead" claim). Syphon between an arm64 helper and Rosetta TD is **UNVERIFIED**.
8. **Licences:** SD-Turbo needs Stability's Community licence (free commercial under US$1M annual revenue, registration required); SDXS and SDXL-Lightning weights are OpenRAIL++; Depth Anything V2 **Small only** is Apache-2.0 (Base/Large/Giant are CC-BY-NC-4.0); SAM 2, MediaPipe, Real-ESRGAN, RAFT, TAESD, StreamDiffusion are permissive (table in §3).
9. **Flash/safety:** diffusion output flickers and can pulse; any ML layer needs a hard limiter (3 flashes/s rule, `concert-visuals-research/README.md` §4) and a fail-safe to the base loop (RUNTIME layer 6, D §0).
10. **Recommendation:** for the 24 Oct show put nothing diffusion-based on the critical path. Rank order in §5; the open decision for the lead is whether to spend a user-approved test slot on SDXS/SD-Turbo on this M1 Max (§7).

---

## 2. Findings table

fps column = what the cited source says, for the stated hardware. "M1 Max" in bold = the hardware that matters.

| # | Item | Mac / TD route | Numbers (hardware) | Licence (commercial) | Verdict |
|---|---|---|---|---|---|
| 1 | SD-Turbo img2img (StreamDiffusion-Mac / PyTorch MPS) | native Python venv, MPS | 95.8 ms, 10.4 fps at 512x512 (M3 Ultra) | Stability Community: free <US$1M revenue, register | Marginal; GPU-hungry |
| 2 | SD-Turbo Core ML UNet | native, Core ML CPU_AND_GPU | UNet 53.2 ms; pipeline 77.7 ms (12.9 fps), 13.8 fps 3-thread (M3 Ultra) | same | Marginal; best on M3 Ultra only |
| 3 | SDXS-512 Core ML | native, Core ML | UNet 24.4 ms; 22.7 fps (M3 Ultra); 15.4 fps (M4 Max); 12-18 fps est. for M1/M2/M3 Max (author's estimate) | OpenRAIL++ weights; repo Apache-2.0 | Best diffusion candidate; unmeasured on **M1 Max** |
| 4 | Tiny-SD / Small-SD Core ML | native | Tiny 31.3 ms UNet; "Fair" quality (M3 Ultra) | UNVERIFIED | Lower quality, no clear gain over SDXS |
| 5 | SDXL / SDXL-Lightning / SDXL-Turbo | any | SDXL-class >200 ms UNet even Core ML (M3 Ultra); Apple SDXL 46 s/image on an M1 Max | OpenRAIL++ (Lightning) | Infeasible live |
| 6 | FLUX / MLX diffusion (mflux) | MLX | FLUX.1 schnell 1024x1024 2 steps ~55 s on an M1 Max 64 GB (user-reported, mflux 0.4.0) | FLUX schnell Apache-2.0 UNVERIFIED | Infeasible live; offline only |
| 7 | pix2pix-turbo | native | 3.0 fps MPS; 4.0 fps Core ML UNet + MPS VAE (M3 Ultra) | UNVERIFIED | Infeasible |
| 8 | DotSimulate StreamDiffusionTD | .tox + external Python | no Mac fps published | closed, paid, UNVERIFIED | Experimental; user decision |
| 9 | Daydream (remote GPU) via StreamDiffusionTD | internet | forum: "extremely slow and expensive", not good for HD ~30 fps | UNVERIFIED | Venue-internet risk; skip |
| 10 | Create ML style transfer (video model) | native helper or Swift app, Core ML | Apple: up to 120 fps on A13; no M1 Max figure | your own model, trained on your own style image | Strong candidate; measure |
| 11 | Other Core ML style nets (AnimeGAN, fast-neural-style) | Core ML | no fps found | per-model (see repo list) | Candidate; licences per model |
| 12 | Depth Anything V2 Small Core ML | helper (exists) | **M1 Max 32.8 ms** Apple page; td-port 66.7 ms round trip, ~15/s (outside TD) | Apache-2.0 (Small only) | Feasible, already built |
| 13 | Video Depth Anything | PyTorch | A100 only: Small 7.5 ms FP16; no Mac figure | Small Apache-2.0 | No Mac path; skip |
| 14 | Person segmentation, Apple Vision | helper (exists) | Fast 33.3 ms, Balanced 33.4/50.2 ms round trip (outside TD) | OS framework | Feasible, already built |
| 15 | MediaPipe selfie / image segmenter | native Python or web | Pixel 6: 33.5 ms (selfie, CPU); no Mac fps | Apache-2.0 (framework), models UNVERIFIED | Redundant with Vision |
| 16 | SAM 2 / EdgeTAM | PyTorch/MLX/Core ML | Meta: Tiny 91.2 fps on A100; EdgeTAM 16 fps iPhone 15 Pro Max; sam3.cpp Metal ~1 fps (4-bit) | Apache-2.0 | Infeasible for automatic live masks |
| 17 | MediaPipe Pose/Hand (native venv, OSC) | native Python | M1 (not Max), pose, 640x360: CPU ~77 ms (~13 fps); GPU 14-25 ms (~40-70 fps) in 0.10.20, GPU silently CPU in 0.10.31, fixed in 0.10.32 | Apache-2.0 | Feasible; verify GPU delegate |
| 18 | Apple Vision hand / body pose | helper (extend) | none found | OS framework | Feasible in principle; UNVERIFIED speed |
| 19 | Optical flow RAFT-small | PyTorch | Jetson Orin 25-30 fps (glossary, rough); no Mac figure | BSD-3-Clause | Not worth it; use OpenCV (D §5.2) |
| 20 | Real-ESRGAN upscale | Core ML subprocess | ~1-1.3 s per 512->2048 frame on an M4 | BSD-3-Clause | Infeasible live |
| 21 | MetalFX spatial scaler / Anime4K GLSL | native Metal / TD GLSL | no numbers found | Anime4K MIT | Not ML; cheap spatial sharpen only |

---

## 3. Per-item details

### 3.1 Diffusion img2img on Apple silicon

**The one serious measurement set** (Ochiai, "Systematic Optimization of Real-Time Diffusion Model Inference on Apple M3 Ultra", arXiv May 2026; [alphaxiv summary](https://www.alphaxiv.org/abs/2605.16259.md); code [ochyai/streamdiffusion-mac](https://github.com/ochyai/streamdiffusion-mac), MIT). Hardware: M3 Ultra, 60-core GPU, 512 GB, macOS Sequoia, PyTorch 2.6 MPS, coremltools 9. MLX not evaluated.
- SD-Turbo, 1 step, PyTorch MPS: 256x256 79.5 ms (12.6 fps); 384x384 87.8 ms; 512x512 95.8 ms (10.4 fps). Cost barely moves with resolution (overhead-bound), so a portrait size is likely near these numbers; UNVERIFIED for 512x896.
- Core ML UNet 53.4 ms vs MPS 87.6 ms (-39%). Camera pipeline stages: preprocess 7.9, TAESD VAE encode 6.5, UNet 53.2, VAE decode 6.5, postprocess 2.4 ms = 77.7 ms (12.9 fps); 13.8 fps with a 3-thread capture/infer/display design.
- Dead ends the author measured (do not retry): INT8 and 6/4/2-bit palettisation = 0% speedup; Neural Engine UNet: ALL 63.6 ms (19% slower), CPU_AND_NE 329.4 ms (6.2x slower); Token Merging +10% time; attention slicing +40%; parallel Core ML instances no gain; torch.compile errors on MPS; SDXL-class UNet >200 ms even in Core ML.
- Smaller models: Small-SD 36.6 ms, Tiny-SD 31.3 ms UNet ("Fair" quality, fine detail degrades); **SDXS-512 (328M) 24.4 ms UNet, 44.1 ms per frame, 22.7 fps**, quality rated "Good" by the author (no numeric metric).
- Optical-flow frame skipping (warp every N frames): measured 17.4 fps, "jelly-like distortions" in large motion. A flow-warp interpolation of ML output could still be useful at stage scale, but this paper's version was not clean.
- Author's README fps table: M1/M2 ~5-8, Pro ~8-12, **M1/M2/M3 Max ~12-18 (estimates)**, M4 Max 15.4 (measured), M3 Ultra 22.7 (measured). Says "performance scales with GPU core count" ([repo](https://github.com/ochyai/streamdiffusion-mac)).
- Caveats from the summary: the paper's hardware description is internally inconsistent (192 cores vs 60 cores), and some table values differ between tables. Treat decimals loosely.

**Other Mac ports.** [patrickhartono/StreamDiffusion-Mac](https://github.com/patrickhartono/StreamDiffusion-Mac): a patched fork of StreamDiffusion (Apache-2.0), MPS, Apple Silicon and Intel, "only the img2img pipeline has been tested", SD-Turbo default, no fps published, browser demo. Original StreamDiffusion ([cumulo-autumn](https://github.com/cumulo-autumn/StreamDiffusion), Apache-2.0): SD-Turbo 93.9 fps img2img on an RTX 4090 / i9-13900K, Linux (so ~9x the M3 Ultra MPS number, which is the gap to remember). Diffusers note for SD-Turbo img2img: `num_inference_steps x strength` must be at least 1 ([model card](https://huggingface.co/stabilityai/sd-turbo)), so a light-touch restyle needs 2 steps, which doubles UNet cost.

**Core ML (non-Turbo) reference points on M1 Max:** SD 1.4 one image in 18 s with Core ML (step count not given, macOS 13.1 beta, [HF blog](https://huggingface.co/blog/diffusers-coreml)); Diffusers MPS 50 steps 30.81 s on an M1 Max 64 GB ([HF docs v0.3.0 via search snippet](https://huggingface.co/docs/diffusers/v0.3.0/optimization/mps), UNVERIFIED reading); Apple's own repo lists SD-XL 46 s on an M1 Max (0.46 it/s) per a search snippet of [apple/ml-stable-diffusion](https://github.com/apple/ml-stable-diffusion) (UNVERIFIED, page not opened). These are multi-step runs; they only show how far from real time full SD/SDXL is on this chip.

**MLX.** No MLX SD-Turbo or SDXS benchmark was found. The only MLX diffusion number: mflux FLUX.1 schnell 1024x1024, 2 steps, non-quantised: M1 Max 64 GB ~55 s, M3 Max ~20 s, M2 Ultra <15 s (README table, user-reported, [mflux 0.4.0](https://pypi.org/project/mflux/0.4.0), old version). Infeasible live.

**Quality for a stage.** At 512x512 (or ~384x680 portrait) the diffusion frame is upscaled ~2-3x to 1080x1920 and again to the LED canvas; TAESD's decoder is intentionally lossy ("trades a modest loss in quality for a substantial gain in speed", [TAESD](https://github.com/madebyollin/taesd), MIT) and SDXS-0.9 notes "TAESD may produce low-quality images in float16" ([model card](https://huggingface.co/IDKiro/sdxs-512-0.9)). Single-step distilled models give painterly, mushy detail with frame-to-frame shimmer. On big LED that reads as an organic texture, not as a sharp image. Faces and the PRISM wordmark/names must never go through it (names-intact rule). I found no side-by-side stage footage; judgement UNVERIFIED.

**Licences.**
- SD-Turbo: the model card says "For commercial use, please refer to https://stability.ai/license" ([HF](https://huggingface.co/stabilityai/sd-turbo)). Stability AI Community License (updated 5 Jul 2024): free commercial use below US$1,000,000 annual revenue (combined with affiliates), and you "must register" for commercial purposes; above that you request a licence ([stability.ai](https://stability.ai/community-license-agreement)). Which licence version applies to the SD-Turbo weights today is UNVERIFIED (the card does not reproduce a licence text). Revenue basis is for the lead/user to judge; I did not touch the MOU.
- SDXS-512-DreamShaper and SDXS-512-0.9: tagged `openrail++` on the model cards ([DreamShaper](https://huggingface.co/IDKiro/sdxs-512-dreamshaper), [0.9](https://huggingface.co/IDKiro/sdxs-512-0.9)); the code repo is Apache-2.0 ([IDKiro/sdxs](https://github.com/IDKiro/sdxs)). The author withheld the 1.0 releases "citing possible commercial and copyright risks" (0.9 card). 0.9 is distilled from SD-Turbo, so SD-Turbo's terms may flow through: UNVERIFIED legal reading. The Ochiai repo does not say which SDXS checkpoint it uses.
- SDXL-Lightning: openrail++ ([HF](https://huggingface.co/ByteDance/SDXL-Lightning)).
- TAESD: MIT. StreamDiffusion: Apache-2.0.

### 3.2 DotSimulate StreamDiffusionTD

- Distribution: Patreon .tox ("tox is distributed through DotSimulate's Patreon", workshop page says Patreon subscription required) ([search results; Derivative workshop listing](https://derivative.ca/workshop/ai-workshop-%E2%80%93-introduction-streamdiffusion-td-may-ai-%E5%B7%A5%E4%BD%9C%E5%9D%8A-streamdiffusion-td-%E5%85%A5%E9%96%80%E6%93%8D%E4%BD%9C-%E4%BA%94%E6%9C%88%E4%BB%BD%E5%A0%B4%E6%AC%A1)).
- Mac: search snippets of [0.1.9 "works on Mac"](https://www.patreon.com/posts/streamdiffusiont-103576412), [0.2.6 changelog](https://www.patreon.com/dotsimulate/posts/streamdiffusiont-122151622) ("MAC: (apple silicon) supported and builtin installation. Install python 3.11 using homebrew ... inference speeds are not as fast as with dedicated gpu and tensorrt is not supported on mac") and [0.2.99](https://www.patreon.com/dotsimulate/posts/streamdiffusiont-137019242) ("cloud backend and better support for 5xxx and mac"). All three pages returned 403 to me; **I read only the search snippets**. Older Derivative/third-party material says Windows + CUDA only ([tutorial list](https://derivative.ca/tags/streamdiffusion): none of the 8 posts mention Mac).
- Unknowns that matter here: whether it works inside the **Intel/Rosetta** TD 2025.31550 (the Mac install uses an external Python; an arm64 Homebrew Python started from a Rosetta process would stay native, by td-port's probe in the `camera_bridge` README, but that is for its own binary), how it hands frames back to TD, real fps on an M1 Max, and the plugin's licence/commercial terms. All UNVERIFIED. A Derivative forum poster calls the default Daydream route "extremely slow and expensive" and unsuitable for ~30 fps HD ([thread](https://forum.derivative.ca/t/stream-diffusion-sdxl-turbo/915335)); the Daydream cloud backend would also need venue internet.
- Daydream pricing/terms: I could not find them (daydream.live fetch returned an unrelated page; docs 404). UNVERIFIED.

### 3.3 Style transfer (Core ML)

- Apple ships **no** style-transfer model in its model gallery (list: FastViT, Depth Anything V2, DETR, DeepLabv3, YOLOv3, etc.; [Apple models](https://developer.apple.com/machine-learning/models/)).
- **Create ML Style Transfer** trains your own: one style image (>=512 px advised), content images, 400-500 iterations, "only a few minutes"; choose a **video** model for real time; model under 1 MB; "up to 120 frames per second" on an A13; two models ran on the Neural Engine with Metal blending in the demo ([WWDC20 10642](https://developer.apple.com/wwdc20/10642), [tutorial](https://iosdevie.substack.com/p/running-create-ml-style-transfer)). No Mac/M1 Max number found.
- Why it fits: tiny, per-frame (no flicker model needed beyond the video variant's design), runs on the Neural Engine so the GPU stays with TD, and the style can be a PRISM brand image (full-colour, per brand rules). Why it may disappoint: it is a 2016-style painterly filter; fidelity and resolution limits on 1080x1920 input are UNVERIFIED; Create ML training needs the Xcode/Create ML tool on the Mac (an install/approval question for the lead, not done here).
- Community models: [john-rocky/CoreML-Models](https://github.com/john-rocky/CoreML-Models) lists fast-neural-style and AnimeGAN variants (Hayao, Paprika, Face_Paint), MobileSAM, SAM2-Tiny, Real-ESRGAN, etc. Per-model licences vary (flags: UltraSharp CC-BY-NC-SA-4.0, FastSAM AGPL-3.0, RMBG1.4 and easyportrait "Creative Commons" variant not stated); no fps. The [CoreML Syphon Bridge](https://derivative.ca/community-post/tutorial/touchdesigner-coreml-syphon-bridge/74429) (D §3.3) bundles 16 models incl. style transfer and face parsing; flow documented as Syphon (IOSurface) -> CIImage -> Core ML -> Metal texture -> Syphon, "model speed + 2 ms overhead", macOS 14+, TD 2024+, licence and price not stated.

### 3.4 Depth

- Depth Anything V2 **Small** (24.8M params): Apache-2.0; Base/Large/Giant CC-BY-NC-4.0 ([repo](https://github.com/DepthAnything/Depth-Anything-V2)). Do not use Base/Large for the show. Apple's Core ML build: F16 49.8 MB, abs-rel error 0.0089, **32.80 ms on a MacBook Pro M1 Max** (24.58 ms M3 Max), Neural Engine the dominant unit ([Apple HF page](https://huggingface.co/apple/coreml-depth-anything-v2-small)). Apple's gallery repeats: M1 Max 33.48 ms (all units), 32.78 ms (GPU) ([Apple](https://developer.apple.com/machine-learning/models/)). The ANE detail from the HF page vs. the GPU line from the gallery is not reconciled (UNVERIFIED which unit wins).
- Local: the helper already serves it; round trip 66.7 ms median at a paced 60 fps loop (4 frames), helper compute 53.9 ms, ~15 maps/s (`td-port/camera_bridge/README.md`, outside TD). Quantised to 16.7 ms frames; the gap between 53.9 and Apple's 32.8 ms is unexplained (pre/post-processing and percentile computation are plausible, UNVERIFIED).
- Quality: depth maps are per-frame and flicker; larger Video Depth Anything has temporal consistency but is A100-benchmarked, no Mac path ([repo](https://github.com/DepthAnything/Video-Depth-Anything)): skip. Smooth the per-frame map in TD (Lag/Slope).
- Outdoor night/floodlights degrade monocular depth: UNVERIFIED.

### 3.5 Segmentation

- **Apple Vision person segmentation** (Fast/Balanced/Accurate) is already in the helper and measured (Fast 19.7 ms compute, 33.3 ms round trip; Balanced 25.3 ms compute; instance masks added; "a dense crowd keys as one blob and small far people are missed"; `td-port/camera_bridge/README.md` and D §0). Vision API availability/limits pages did not load; macOS-14 person-instance-mask availability is from memory: UNVERIFIED.
- **MediaPipe selfie segmenter**: 256x256 float16, 33.46 ms CPU / 35.15 ms GPU on a Pixel 6 ([MediaPipe docs](https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter)); model licence not on the page. Redundant with Vision on this Mac.
- **SAM 2**: Apache-2.0; A100 speeds Tiny 91.2 fps, Small 84.8 fps; docs cover CUDA/Linux ([facebookresearch/sam2](https://github.com/facebookresearch/sam2)). Apple publishes a Core ML SAM 2 BasePlus (float16, Apache-2.0) "for the SAM2 Studio demo app" with no latency numbers ([HF](https://huggingface.co/apple/coreml-sam2-baseplus)). SAM 2 needs a click/box prompt and a memory-attention tracker: ~1 fps for Tiny at 4-bit on Metal and ~0.4 s/frame for EdgeTAM in sam3.cpp (search snippet, [mimi3421/sam3.cpp](https://gitblind.noratr.app/mimi3421/sam3.cpp), UNVERIFIED); EdgeTAM claims 16 fps on iPhone 15 Pro Max, SAM 2 smallest ~1 fps there ([paper](https://huggingface.co/papers/2501.07256)) with no Mac package found. Not a live automatic-mask tool.

### 3.6 Pose, hands, faces

- **MediaPipe (native arm64 Python venv -> OSC -> TD)**: framework Apache-2.0 ([repo](https://github.com/google-ai-edge/mediapipe)); the Pose Landmarker task has lite/full/heavy bundles, 224/256 input, `num_poses` default 1 ([docs](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker)); no desktop latency table on the page. Real report on an **M1** (not Max), Pose Landmarker, 640x360 clip: mediapipe 0.10.20 GPU (Metal delegate) 14-25 ms/frame but with a memory leak; CPU ~77 ms; 0.10.31 silently used XNNPACK CPU even with GPU selected (~76-77 ms), fixed in 0.10.32 (closed 22 Jan 2026) ([issue 6216](https://github.com/google-ai-edge/mediapipe/issues/6216)). Per-frame ms are from the log; fps are my division (~13 CPU, ~40-70 GPU). Earlier M2 report: GPU mode failed with an unsupported image format ([issue 5568](https://github.com/google-ai-edge/mediapipe/issues/5568) via search snippet, UNVERIFIED). Rule: check the log line "Created TensorFlow Lite XNNPACK delegate for CPU" vs. a Metal delegate. D §3.3 already lists this route as untested; this adds the version trap. Current PyPI `mediapipe` 1.1.1 is arm64-only on macOS (D §3.2).
- **Apple Vision hand/body pose** in the helper: WWDC20 session 10653 introduced hand pose (21 points per hand) and body pose with multiple bodies; WWDC23 added a 3D body pose request with 17 joints ([WWDC20 notes](https://www.wwdcnotes.com/notes/wwdc20/10653/), [WWDC23 notes](https://wwdcnotes.com/notes/wwdc23/111241)). No speed number found. Same helper pattern as faces (kind 4); new request kinds would need helper code and a protocol bump (a build, so a lead decision).
- Faces: Vision faces 17-70 ms at 960x540, warm-up ~110-130 ms (local, outside TD).
- All of these need a camera or clean feed; the venue camera plan is open (D §0, §4).

### 3.7 Optical flow and upscaling

- **RAFT**: BSD-3-Clause ([princeton-vl/RAFT](https://github.com/princeton-vl/RAFT)); repo gives no speed claims; a glossary page gives RAFT 10-15 fps and RAFT-Small 25-30 fps on a Jetson Orin at 640x480 (rough, [claru.ai](https://claru.ai/glossary/raft)); NeuFlow v2 >20 fps at 512x384 on a Jetson Orin Nano ([paper](https://arxiv.org/abs/2408.10161)). **No Core ML / Apple silicon figure found.** TD's Optical Flow TOP is Windows/NVIDIA only and OpenCV Farneback/DIS already works in TD (D §3.4, §5.2: 42 ms/cook at 640x360). Verdict: no reason to bring a network in.
- **Real-ESRGAN Core ML**: Aristides.Lab TOX, subprocess + file exchange, 512x512 -> 2048x2048 in ~1-1.3 s per frame on an M4, "not meant for real-time video", TD stayed 60 fps ([post](https://derivative.ca/community-post/tutorial/coreml-upscaler/74428)). Licence of the TOX not stated; Real-ESRGAN itself BSD-3-Clause ([CoreML-Models](https://github.com/john-rocky/CoreML-Models)). Infeasible live; fine for stills/textures.
- Non-ML sharpening for a 512 px ML output: Lanczos/sharpen in TD GLSL, or Anime4K GLSL shaders (MIT, designed for real-time 1080p->4K anime playback, no numbers for Apple silicon; [repo](https://github.com/bloc97/Anime4K)). A macOS player project reports MetalFX spatial scaling is realtime on Apple silicon while its Core ML Real-ESRGAN path is export-only (single search snippet, UNVERIFIED). MetalFX needs native code, not TD.

---

## 4. Architecture for TD on this Mac

**Why a helper.** Rosetta TD's Python lacks torch/onnx/coremltools/mediapipe and PyPI only ships arm64 wheels for the newest mediapipe and onnxruntime (D §3.2). An arm64-only binary started from Rosetta TD stays native (td-port probe: universal binary reported `x86_64 translated=1` when spawned from TD's Python, arm64-only reported `arm64 translated=0`; `td-port/camera_bridge/README.md`). Apple: Rosetta translates a whole process and arm64 and x86_64 code cannot be mixed in one process ([Apple](https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment.md)).

**Transport options**

| Route | How | Cost / evidence | Risk |
|---|---|---|---|
| A. Unix socket (td-port protocol) | TD Python reads a small frame (Resolution TOP -> `numpyArray`), sends BGRA, helper replies mask/depth, Script TOP `copyNumpyArray` | outside TD with TD's own Python: depth 66.7 ms, Fast mask 33.3 ms, one request in flight, newest wins | **Nothing measured inside TD** (readback, upload, crashes); fine for masks/depth at 518x392 or smaller; too heavy for 512x512+ RGB diffusion return at 30 fps? UNVERIFIED |
| B. Syphon in -> helper -> Syphon out | TD Syphon Spout Out of a small frame, helper does Core ML, publishes result, TD Syphon Spout In | CoreML Syphon Bridge page: zero-copy IOSurface, "+2 ms overhead", round-robin 3 textures, "40+ FPS" depth with no hardware or resolution ([post](https://derivative.ca/community-post/tutorial/touchdesigner-coreml-syphon-bridge/74429)) | **Syphon between an arm64 process and Rosetta TD: UNVERIFIED**; Syphon is limited to 8-bit RGBA ([TD doc](https://docs.derivative.ca/Syphon_Spout_Out_TOP) per E_live_rig.md); never run between TD and Arena here (E_live_rig.md) |
| C. NDI loopback | same as B over NDI | E_live_rig compares Syphon/NDI for the Arena leg only | adds codec latency; skip unless B fails |
| D. Second machine | ML box sends results via NDI/OSC to the TD/Arena Mac | removes GPU contention | network at FOH (D §3.3), extra hardware: user's call |

**Budgets (arithmetic from cited numbers, not new measurements).** At 30 fps the frame is 33.3 ms (PF26 runs 30 fps, STAGE.md per E_live_rig.md). A result that takes 53.9 ms compute + 1-2 frame polling arrives ~66.7 ms later = **4 frames at 60 Hz** (td-port); it must be treated as a slowly updating mask/map and smoothed in TD, never as a frame-locked layer. A diffusion frame at the M3 Ultra's 77.7 ms (12.9 fps) means a ~3-frame-old picture at 30 fps plus Syphon; at 22.7 fps (44 ms) ~1.3 frames. For an M1 Max these are lower bounds (inference). For IMAG-style live camera restyle with lip-sync audio, diffusion latency would be visible; keep it off IMAG faces (names/faces rule + latency).

**GPU/ANE allocation.** Neural Engine: Depth Anything V2 Small, style transfer, Vision (Apple lists ANE dominant for depth). GPU: TD render, diffusion UNet. Parallel Core ML instances do not raise throughput (command-queue serialisation, [paper](https://www.alphaxiv.org/abs/2605.16259.md)). TD at 7488x2880 heavy look is GPU-bound at 24.6 fps (E_live_rig.md), so a diffusion helper at full rate would drop TD's cook rate; whether a 1080x1920 TD look plus SDXS at ~12 fps can share the GPU is **not measured**.

**Fail-safe.** One-in-flight, frame ids echoed, pass-through on missing helper, 2 s timeout (td-port design). ML layer must drop to the base loop when the helper dies (RUNTIME layer 6); helper lifetime follows TD's pid with idle exit (td-port). Add a TD-side flash/brightness limiter after any diffusion output.

**Offline alternative.** Same models can restyle clips offline into DXV3 masters via the normal pipeline (SYSTEM.md). That removes real-time constraints entirely; it is "generation" in the user's terms (not done here).

---

## 5. Ranked recommendations for PF26

Rank = value per risk, given 8 days and a one-machine rig. "Needs" = approval/build the lead must decide.

1. **Vision person mask (Fast) + depth from the existing helper.** Both exist, are measured outside TD, free, no model-licence problem (Depth Small Apache-2.0). Needs: the td-port camera_bridge gate in TD (unrun), a camera/clean feed. Look: silhouettes, depth fog, cut-outs (td-port `person_key`, `depth_fx`). Smooth results; treat as 15-30 Hz.
2. **Create ML video style transfer** as a new helper request kind or a small Core ML app: best "AI painting" look on the Neural Engine, one style image per look (PRISM art), sub-1 MB models. Needs: Create ML training on the Mac (user go-ahead), a Mac-side fps measurement (none exists), a transport (A or B). Quality is a filter look, not generative.
3. **Classic CV flow/background-subtraction in TD** (not ML; D §5): already verified, covers "motion-reactive" without a network.
4. **MediaPipe pose/hands via native venv -> OSC** (or Vision hand/body pose in the helper): only if the venue gives a clean camera feed; pin mediapipe >=0.10.32 and verify the Metal delegate in the log. Needs: venv install (user go-ahead).
5. **SDXS-512 (or SD-Turbo) Core ML img2img as an optional experimental layer**, small portrait size, 10-15 fps, on the same Mac or a second one. Needs: user-approved install and a bench on this M1 Max (§7); licence registration if SD-Turbo-derived; limiter; do not put on IMAG faces or names. Expected value: a differentiator look, not a dependable one.
6. **DotSimulate StreamDiffusionTD**: only if the lead wants the packaged route; subscription, closed, unverified under Rosetta TD. Prefer #5's open code if diffusion is wanted at all.
7. **Offline diffusion restyle of recorded TD loops** (not real time): lowest risk way to use diffusion for PF26; an Opus/lead call on whether it counts as generation under the user's video-first rules.

**Infeasible, with reasons**
- SDXL / SDXL-Lightning / SDXL-Turbo / FLUX live: SDXL-class UNet >200 ms on an M3 Ultra; FLUX schnell ~55 s per 1024x1024 on an M1 Max (mflux).
- pix2pix-turbo, kNN/CLIP retrieval synthesis, distilled tiny style nets: 3-4 fps, or poor quality per the M3 Ultra paper.
- SAM 2 / EdgeTAM automatic live masks: prompt-driven, no Mac real-time evidence.
- Real-ESRGAN real-time video upscaling: 1-1.3 s/frame on M4.
- RAFT on this Mac: no evidence of speed, no TD benefit over OpenCV.
- Cloud (Daydream): venue-internet dependency, reported slow/expensive, pricing unknown.
- Depth Anything Base/Large/Giant: CC-BY-NC-4.0 (non-commercial). Video Depth Anything: no Mac path.
- TD's Optical Flow, Body/Face Track, NVIDIA Background/Upscaler TOPs: unsupported on this OS (D §1.1).

---

## 6. Rules and risks that apply (from the repo)

- Never split/hide/chop names or words; keep faces/names out of any stylisation layer.
- Flash limit: no more than 3 flashes/second over 25% of screen; diffusion shimmer and brightness jumps count. Add a temporal limiter.
- Camera-based looks (masks, pose) depend on the unknown venue feed: prototype on FaceTime/recorded clip only (D §4).
- Syphon/NDI-to-Arena behaviour when a source disappears is undocumented (E_live_rig.md): the ML layer must degrade inside TD, not rely on Arena.
- td-port `camera_bridge` caveat stays: nothing in this file has run inside TD.

---

## 7. Open questions for the lead

1. Is a user-approved bench of SDXS-512 / SD-Turbo Core ML (`ochyai/streamdiffusion-mac`, MIT) on this M1 Max worth a slot? It needs a venv, model downloads (SD-Turbo / SDXS weights) and a Core ML conversion: all barred by this brief. It would settle item 1 of §1 with one number set.
2. If diffusion is used, which licence path: Stability Community registration (SD-Turbo and probably SDXS-0.9, which is distilled from it) vs. openrail++ weights; who confirms the revenue basis?
3. Create ML style transfer: approve installing/using Create ML to train a PRISM-style model, and measure fps on the M1 Max? (No M1 Max number exists; Apple's 120 fps is for an A13.)
4. Transport choice: extend the td-port socket (frames through TD Python, unmeasured in TD) or test Syphon from an arm64 helper into Rosetta TD (UNVERIFIED)? Either needs a user-approved Syphon test.
5. Should the helper gain hand/body-pose request kinds (Vision), or run MediaPipe in a native venv with OSC? Venue camera plan decides.
6. Is a second machine for ML (NDI/OSC to the TD Mac) acceptable at FOH, given GPU contention?
7. Is offline diffusion restyling of TD loops allowed under the video-first / generation rules, or must ML stay real-time-only?
8. Gaps I could not close (budget): Apple Vision pose/instance API availability, Create ML style-transfer fps on M-series, Daydream pricing/terms, DotSimulate's actual Mac requirements/licence, Syphon across architectures.

---

## 8. Sources

Diffusion on Apple silicon
- Ochiai, Systematic Optimization of Real-Time Diffusion Model Inference on Apple M3 Ultra (summary): https://www.alphaxiv.org/abs/2605.16259.md , https://www.alphaxiv.org/abs/2605.16259
- ochyai/streamdiffusion-mac (MIT): https://github.com/ochyai/streamdiffusion-mac
- patrickhartono/StreamDiffusion-Mac: https://github.com/patrickhartono/StreamDiffusion-Mac
- cumulo-autumn/StreamDiffusion (Apache-2.0, RTX 4090 table): https://github.com/cumulo-autumn/StreamDiffusion
- SD-Turbo model card: https://huggingface.co/stabilityai/sd-turbo ; Stability Community License (5 Jul 2024): https://stability.ai/community-license-agreement
- SDXS: https://github.com/IDKiro/sdxs , https://huggingface.co/IDKiro/sdxs-512-dreamshaper , https://huggingface.co/IDKiro/sdxs-512-0.9
- SDXL-Lightning: https://huggingface.co/ByteDance/SDXL-Lightning
- TAESD: https://github.com/madebyollin/taesd
- HF Core ML Stable Diffusion blog (M1 Max 18 s): https://huggingface.co/blog/diffusers-coreml ; Apple ml-stable-diffusion: https://github.com/apple/ml-stable-diffusion
- mflux 0.4.0 README table (M1 Max ~55 s): https://pypi.org/project/mflux/0.4.0
DotSimulate / TD
- StreamDiffusionTD 0.1.9 "works on Mac": https://www.patreon.com/posts/streamdiffusiont-103576412 ; 0.2.6: https://www.patreon.com/dotsimulate/posts/streamdiffusiont-122151622 ; 0.2.99: https://www.patreon.com/dotsimulate/posts/streamdiffusiont-137019242 (all read via search snippet only; 403)
- Derivative StreamDiffusion posts: https://derivative.ca/tags/streamdiffusion ; workshop listing (Patreon required): https://derivative.ca/workshop/ai-workshop-%E2%80%93-introduction-streamdiffusion-td-may-ai-%E5%B7%A5%E4%BD%9C%E5%9D%8A-streamdiffusion-td-%E5%85%A5%E9%96%80%E6%93%8D%E4%BD%9C-%E4%BA%94%E6%9C%88%E4%BB%BD%E5%A0%B4%E6%AC%A1
- Forum: https://forum.derivative.ca/t/stream-diffusion-sdxl-turbo/915335 ; motius remote plugin (MIT): https://github.com/motius/remote-stream-diffusion-td
- Aristides.Lab CoreML Syphon Bridge: https://derivative.ca/community-post/tutorial/touchdesigner-coreml-syphon-bridge/74429 ; CoreML Upscaler: https://derivative.ca/community-post/tutorial/coreml-upscaler/74428
Style transfer, models
- WWDC20 10642: https://developer.apple.com/wwdc20/10642 ; tutorial: https://iosdevie.substack.com/p/running-create-ml-style-transfer
- Apple Core ML models: https://developer.apple.com/machine-learning/models/ ; john-rocky/CoreML-Models: https://github.com/john-rocky/CoreML-Models
Depth, segmentation, pose
- Apple Depth Anything V2 Small Core ML: https://huggingface.co/apple/coreml-depth-anything-v2-small ; Depth-Anything-V2: https://github.com/DepthAnything/Depth-Anything-V2 ; Video Depth Anything: https://github.com/DepthAnything/Video-Depth-Anything
- SAM 2: https://github.com/facebookresearch/sam2 ; Apple Core ML SAM 2: https://huggingface.co/apple/coreml-sam2-baseplus ; EdgeTAM: https://huggingface.co/papers/2501.07256 ; sam3.cpp: https://gitblind.noratr.app/mimi3421/sam3.cpp
- MediaPipe: https://github.com/google-ai-edge/mediapipe ; Pose Landmarker: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker ; Image Segmenter: https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter ; Mac GPU issue: https://github.com/google-ai-edge/mediapipe/issues/6216 , https://github.com/google-ai-edge/mediapipe/issues/5568
- Vision pose (WWDC notes): https://www.wwdcnotes.com/notes/wwdc20/10653/ , https://wwdcnotes.com/notes/wwdc23/111241
Flow, upscaling, platform
- RAFT: https://github.com/princeton-vl/RAFT ; NeuFlow v2: https://arxiv.org/abs/2408.10161 ; glossary: https://claru.ai/glossary/raft
- Anime4K: https://github.com/bloc97/Anime4K
- Rosetta process rule: https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment.md
Local
- `td-port/camera_bridge/README.md`; `jazib-td-mcp/docs/research/D_camera_mediapipe.md`, `E_live_rig.md`, `BRIEF.md`.
