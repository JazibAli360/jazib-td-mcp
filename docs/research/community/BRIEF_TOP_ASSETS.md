# Brief: derivative.ca most-viewed ASSETS (5 Sonnet agents, 26 Oct 2026)

User: "5 agents on this too - https://derivative.ca/community?sort_by=views&type[]=24" (= community posts of type
Asset, sorted by views; 33 listing pages, `&page=0..32`, ~20 assets each).

**Follow `BRIEF.md` in this folder for manners, file rules, leak rule and the JSON line fields**, with these changes:
- Listing URL: `https://derivative.ca/community?sort_by=views&type%5B%5D=24&page=N` (your pages in your prompt).
- Add to each JSON line: `views_rank` (position in this sorted listing: page*20 + index + 1), `views` / `reads` and
  `comments` if the page shows them.
- **Go deeper than the general crawl**: these are the most-used shared tools. For every asset: what problem it solves,
  how it works (ops/Python/GLSL/C++ plugin), install steps, build/OS requirements, licence, price (free/paid/Patreon),
  dependencies, last update, and the author's other assets. For every file you download (BRIEF rules: free, no login,
  <= 50 MB; repos cloned depth 1 with commit): list its contents and, for `.tox`, run TD's `toeexpand` (inside
  `/Applications/TouchDesigner 2.app/Contents/`, find it) on a COPY in a fresh folder under
  `.../research_src/community/files/<postid>/expanded/` to read the network as text: op types, custom pars, any
  Python that runs on load / file / network / subprocess access (audit flags). **Never load anything into TD.**
  C++ plugins (.plugin/.bundle/.dylib/.dll): record only; don't download binaries.
- Other agents (slices 01-10) crawl the same site in page order; duplicates are fine, the lead merges by post id.
- Outputs: `~/Documents/StageLab_PrismFest/jazib-td-mcp/research_src/community/top_assets_<NN>.jsonl` and
  `~/Documents/StageLab_PrismFest/jazib-td-mcp/docs/research/community/top_assets_<NN>.md` (~150 lines:
  ranked table rank | title | author | views | free? | licence | build | Mac | what it is; deep notes on the top 15;
  downloaded files + audit flags; recurring authors; Windows/NVIDIA-only; skipped). Edit nothing else.
Reply with a 10-line summary.
