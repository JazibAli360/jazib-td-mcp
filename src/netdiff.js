// Network-as-text diff (td_net_diff). Pure functions over the JSON-lines export of td/handlers.py cmd_net_export
// (format jtd-net v1, docs/PROTOCOL.md). Idea from Embody's TDXN diff (dylanroscover/Embody, MIT); own code.

const canon = (v) => {
  if (Array.isArray(v)) return `[${v.map(canon).join(',')}]`;
  if (v && typeof v === 'object') return `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${canon(v[k])}`).join(',')}}`;
  return JSON.stringify(v === undefined ? null : v);
};
const same = (a, b) => canon(a) === canon(b);

// Text -> {header, ops: Map(p -> record), end}. Throws on anything that is not a jtd-net export.
export function parseNet(text) {
  const lines = String(text).split('\n').map((l) => l.trim()).filter(Boolean);
  if (!lines.length) throw new Error('empty network export');
  const recs = lines.map((l, i) => { try { return JSON.parse(l); } catch (e) { throw new Error(`network export line ${i + 1} is not JSON: ${e.message}`); } });
  const header = recs[0];
  if (!header || header.format !== 'jtd-net') throw new Error('not a jtd-net export (first line must have "format":"jtd-net"; make one with td_net_export)');
  const ops = new Map();
  let end = null;
  for (const r of recs.slice(1)) {
    if (r && r.end) { end = r; continue; }
    if (!r || typeof r.p !== 'string') throw new Error('network export record without "p"');
    ops.set(r.p, r);
  }
  return { header, ops, end };
}

// Per-name diff of two flat objects: {name: [a, b]} with null for absent (= default for pars).
function diffMap(a = {}, b = {}) {
  const out = {};
  for (const k of [...new Set([...Object.keys(a), ...Object.keys(b)])].sort()) {
    if (!same(a[k], b[k])) out[k] = [a[k] === undefined ? null : a[k], b[k] === undefined ? null : b[k]];
  }
  return out;
}
const flatCustom = (cp = {}) => Object.fromEntries(Object.entries(cp).flatMap(([page, pars]) => Object.entries(pars).map(([n, d]) => [`${page}/${n}`, d])));

// One op's changes, or null when equal.
export function diffOp(a, b) {
  const ch = {};
  for (const k of [...new Set([...Object.keys(a), ...Object.keys(b)])].sort()) {
    if (k === 'p' || same(a[k], b[k])) continue;
    if (k === 'pars') ch.pars = diffMap(a.pars, b.pars);
    else if (k === 'cp') ch.cp = diffMap(flatCustom(a.cp), flatCustom(b.cp));
    else ch[k] = [a[k] === undefined ? null : a[k], b[k] === undefined ? null : b[k]];
  }
  return Object.keys(ch).length ? ch : null;
}

// a, b: export texts or parsed exports. Lists added / removed ops, changed ones (pars, custom pars, rewired inputs,
// anything else) and warnings when the two exports are not comparable like for like. max caps each list.
export function diffNet(a, b, { max = 200 } = {}) {
  const A = typeof a === 'string' ? parseNet(a) : a;
  const B = typeof b === 'string' ? parseNet(b) : b;
  const added = [...B.ops.keys()].filter((p) => !A.ops.has(p)).sort();
  const removed = [...A.ops.keys()].filter((p) => !B.ops.has(p)).sort();
  const changed = [];
  const rewired = [];
  for (const p of [...A.ops.keys()].filter((k) => B.ops.has(k)).sort()) {
    const d = diffOp(A.ops.get(p), B.ops.get(p));
    if (!d) continue;
    changed.push({ p, ...d });
    if (d.in || d.cin) rewired.push(p);
  }
  const warnings = [];
  for (const k of ['include_defaults', 'dat_text', 'xy', 'depth']) {
    if (!same(A.header[k], B.header[k])) warnings.push(`exports differ in ${k} (${A.header[k]} vs ${B.header[k]}): some differences may only be that`);
  }
  if (A.header.build !== B.header.build) warnings.push(`different TD builds (${A.header.build} vs ${B.header.build}): par defaults may differ`);
  if (A.end?.truncated || B.end?.truncated || !A.end || !B.end) warnings.push('an export is truncated or has no end line: ops past the cut show as added/removed');
  const cap = (l) => l.slice(0, max);
  const truncated = [added, removed, changed].some((l) => l.length > max);
  return {
    same: !added.length && !removed.length && !changed.length,
    counts: { added: added.length, removed: removed.length, changed: changed.length, rewired: rewired.length },
    a: { root: A.header.root, build: A.header.build, ops: A.ops.size },
    b: { root: B.header.root, build: B.header.build, ops: B.ops.size },
    added: cap(added), removed: cap(removed), rewired: cap(rewired), changed: cap(changed),
    ...(truncated ? { truncated: true, max } : {}),
    ...(warnings.length ? { warnings } : {}),
  };
}

// Is this argument export text (vs a file path or a TD path)?
export const looksLikeNetText = (s) => typeof s === 'string' && (s.includes('\n') || s.trimStart().startsWith('{'));
