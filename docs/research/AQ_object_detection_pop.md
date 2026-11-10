# AQ - Object Detection POP (Tyrell, asset 74954), 26 Oct 2026

Status: **PAID, Windows + NVIDIA only, needs TD 2025.32820+. Not usable on our Mac / 31550. Nothing downloaded, nothing inspected.**
`research_src/objdetect_pop_74954/` is empty on purpose (no free file exists; the download needs a shop login and a paid licence).

## What it is (cited)
- Derivative asset page `https://derivative.ca/community-post/asset/object-detection-pop/74954` (WebFetch worked, no 403): author **Tyrell**
  (design studio, Brussels), posted 6 Jul 2026, tag C++, 0 comments. A **native C++ Custom Operator** (a POP) that runs
  **transformer-based detection models** fully on the GPU. Input: any TOP. Output: **one POP point per detection**.
- Model family and COCO class list are **not named** on the page (shop page: five ONNX models nano/small/medium/base/large, "COCO labels" file in the zip;
  family e.g. RT-DETR/D-FINE is UNVERIFIED). Class filter parameter built in.
- Output attributes (page): `P` (bbox centre, for instancing), bbox min/max (normalised x1 y1 x2 y2), centre + size, score, class ID,
  and from a built-in **SORT tracker**: track ID, track age, velocity. No CHOP or DAT output stated (get them with POP to CHOP / POP to DAT).
- Performance claims: sub-ms to a few ms per frame, zero-copy GPU, FP16/FP32, TensorRT engine pre-bake (first cook otherwise 30-90 s). Not measured by us.
- Shop `https://tdplugins.shop/product/objdetectpop` (v1.0.3, 646 MB zip): **paid per machine**: Non-commercial EUR 10 (1 machine), Indie EUR 35 (1 machine,
  freelance ok), Studio EUR 250 (5 machines). Zip = plugin DLL, 5 ONNX models, engine builder, `tdlicense-manager.exe`, COCO labels, example .toe, LICENSE.pdf,
  THIRD_PARTY_LICENSES.txt. Requirements: **Windows 10/11 x64, TouchDesigner 2025.32820+**, CUDA/TensorRT (NVIDIA).
  Docs `tdplugins.shop/docs/objdetectpop` (landing only readable; Installation / Parameters / TensorRT / Point Attributes / License FAQ sub-pages 404 or not fetched).
- YouTube video `C4n1vDWB3gY`: WebFetch returned page chrome only; nothing learned. No GitHub, no forum thread linked.

## Audit (what can be said without the file)
- Native DLL = arbitrary code in the TD process; cannot be audited by reading. Closed source. Licence: commercial EULA, per-machine activation by
  `tdlicense-manager.exe` (**network use during activation UNVERIFIED**). No Python, pip, eval or subprocess is stated, but also not checkable.
- Not a .tox: it is a Custom Operator DLL, so `toeexpand` does not apply; the example .toe is inside the paid zip, not obtained.

## Verdict for TD 2025.31550, macOS Apple Silicon (Rosetta)
- **Not feasible.** Three independent blockers: (1) Windows x64 DLL, no macOS build; (2) CUDA/TensorRT = NVIDIA only (we have Vulkan/MoltenVK on Apple GPU);
  (3) needs build 2025.32820+ and we are on 31550 (final decision: no upgrade is planned for the show). Not installed, no install recipe.
- Gated recipe if the user ever gets a Windows/NVIDIA machine: user buys a licence (spend = their go-ahead), downloads the zip in a browser, extracts it into a
  new dir, we read LICENSE.pdf + THIRD_PARTY_LICENSES.txt, check tdlicense-manager traffic, copy the DLL into TD's Plugins folder, bake the TensorRT engine
  (30-90 s), then POP out -> `td_exec` read of `P`, `score`, `classid`, `trackid`. Every step needs the user's OK.

## Comparison with TDYolo (see `AN_awesome_touchdesigner.md` row 5) and our webcam rule
| | Object Detection POP | TDYolo |
|---|---|---|
| Licence/cost | paid, closed, per machine | MIT, free |
| Platform | Windows + NVIDIA only | Win + macOS (Metal), TD 2023.12000+ |
| Engine | C++ plugin, CUDA/TensorRT | headless browser (WebGPU/ONNX) in Web Render TOP |
| Output | POP points + SORT tracking (instancing-ready) | table DATs (report, summary) + overlay TOPs |
| Needs network | licence activation (unverified) | internet to bootstrap runtime |
| 31550 / Mac | no | candidate, WebGPU on Rosetta still a PROBE |
- Take from it as **ideas only**: output contract of one point per detection with `P`, bbox, score, classid, trackid, trackage, velocity; a SORT-style tracker
  for stable IDs. If TDYolo is ever adopted, a small Script POP/DAT-to-POP shim could present its report DAT in this same attribute layout (so looks that
  instance on detections are portable to the paid plugin later). Idea only, not built.
- Webcam rule: any detection test uses the stored clip `media/webcam/webcam_ref_5s.mp4` (Movie File In), live camera only when the user asks.

## FUTURE.md-style note
Row added to `docs/FUTURE.md`: Object Detection POP, needs 2025.32820+ and Windows/NVIDIA, status idea only.
