# Research brief — making PF26 visuals in TouchDesigner through Jazib TD MCP (16 Oct 2026)

Set by the lead (Opus). Sonnet agents do the finding and compiling; the lead decides directions.
The user asked: "research what you need to do, how to do it in this version and all, look up visuals and all".

## Fixed facts (don't re-derive, don't contradict)
- TD build **2025.31550** (`/Applications/TouchDesigner 2.app`, runs under Rosetta) on an **Apple M1 Max, 32-core GPU,
  64 GB**, Metal. Driven through `jazib-td-mcp` (22 `td_*` tools; `td_guide` first). TD is open now on
  `jazib-td-mcp/projects/JazibTD_home.toe`, connected.
- Target: **PRISMFEST'26**, Sat 24 Oct 2026, Karachi. Stage = Vendor Package R02, nine faces
  20/10/10/10/30/10/10/10/20 ft, 9984x3840 native; PF26 production renders at **75% = 7488x2880**.
- Playback: **Resolume Arena 7.23.2** (final, no upgrade). Final clips go through `prismfest26-show/production/`
  (assets_where.py → viewer → Mastering → Final Assets; DXV3 masters). Read `production/SYSTEM.md` before claiming
  anything about the pipeline.
- Brand: `prism-brand/CLAUDE.md` + `brand.json`. Method: `concert-visuals-research/CLAUDE.md` Playbook.
- TD API facts already confirmed: `jazib-td-mcp/LEARNINGS.md`, `td-port/LEARNINGS.md`.

## Guardrails (all agents)
1. Research only. **No generation** (Flow, ImagineArt, anything that spends credits), **no builds for the show**, no
   Arena / REST / Syphon operations, no installs, no downloads of software/plugins/.tox from the web.
2. Write only inside `jazib-td-mcp/docs/research/` (your own file + `refs/<your-topic>/` for saved reference
   images; small images only, < 2 MB each, no video files over 20 MB, record source URL + author per file in
   `refs/<topic>/SOURCES.md`). Don't edit any other file in the bundle. Temp files go to the session scratchpad.
3. TD (only the agent told it may): read-only probes through `td_exec` / `td_list` / `td_info`. Anything created
   for a probe goes in `/project1/_research_probe` and is deleted at the end. **Never `td_save_project`**, never
   touch `/jazib_mcp`.
4. Every claim carries its source: a URL (with the doc page's version/date if shown) or "probed live in 2025.31550"
   with the exact expression. Mark anything from older builds or from memory as **unverified**. Don't invent
   numbers: no fps/perf figure without a measurement or a cited source.
5. Names the user's rules care about: never split/chop a name or word; full-colour PRISM logos only; flash limits per
   `concert-visuals-research/README.md` §4; info/emergency screens are plain posters (not TD work).
6. End with a short "Open questions for the lead" list. Pure facts and links, no sales talk.
