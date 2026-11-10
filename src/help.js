// td_help (26 Oct 2026): offline op-type / parameter / docs lookup, no TD needed. Sources, all local and read-only:
//  - our live dump docs/research/ops/INDEX_<build>.json + ops_<FAMILY>_<build>.json (pars, pages, defaults, menus, ranges);
//  - TD's shipped parameter help (<app>/Contents/Resources/tfs/Config/TDParameterHelp.json: op label + summary, par help);
//  - TD's shipped offline wiki (<app>/.../Samples/Learn/OfflineHelp/https.docs.derivative.ca/*.htm: the Summary section).
// Idea from TDMCP get_docs / describe_op_type and 8beeeaaat's touchdesigner-mcp (research AF, Top 10 #6); written here.
// Pure functions take a db built by buildDb(); loadDb() reads the files once and caches them in memory.
import fs from 'node:fs';
import path from 'node:path';
import { ROOT } from './config.js';

export const BUILD = '2025.31550';
export const FAMILIES = ['TOP', 'CHOP', 'SOP', 'DAT', 'COMP', 'MAT', 'POP'];
const TD_APP = process.env.JTD_TD_APP || '/Applications/TouchDesigner 2.app';
const PAR_HELP = path.join(TD_APP, 'Contents/Resources/tfs/Config/TDParameterHelp.json');
const DOCS_DIR = path.join(TD_APP, 'Contents/Resources/tfs/Samples/Learn/OfflineHelp/https.docs.derivative.ca');
const OPS_DIR = path.join(ROOT, 'docs', 'research', 'ops');
const MENU_CAP = 40;
const FULL_LIST_CAP = 80; // more pars than this and no page/par filter: pages give names only

export const norm = (s) => String(s || '').toLowerCase().replace(/[\s_-]+/g, '');
export const clip = (s, n) => { const t = String(s || '').replace(/\s+/g, ' ').trim(); return t.length > n ? t.slice(0, n - 1) + '…' : t; };

// index: INDEX_<build>.json; dumps: {FAMILY: ops_<FAMILY>.json}; paramHelp: TDParameterHelp.json or null; docsFiles:
// list of .htm basenames in the offline wiki or null.
export function buildDb({ index = {}, dumps = {}, paramHelp = null, docsFiles = null, docsDir = null } = {}) {
  const ops = new Map(); // norm(type) -> record
  const put = (type, family, extra) => {
    const k = norm(type);
    const r = ops.get(k) || { type, family, label: null, summary: null, in: null, out: null, pars: null, help: null, status: 'help_only' };
    Object.assign(r, extra);
    ops.set(k, r);
    return r;
  };
  for (const fam of FAMILIES) {
    const d = dumps[fam];
    if (!d) continue;
    for (const o of d.dumped || []) put(o.type, fam, { in: o.inputs, out: o.outputs, pars: o.pars || [], status: 'dumped' });
    for (const t of d.skipped_not_created || []) put(t, fam, { status: 'not_created' });
    for (const f of d.failed || []) put(f.type, fam, { status: 'failed', failed: clip(f.error, 160) });
  }
  if (paramHelp && paramHelp.help) {
    for (const [famKey, group] of Object.entries(paramHelp.help)) {
      const fam = famKey.replace(/s$/, '');
      for (const [type, h] of Object.entries(group || {})) {
        const r = ops.get(norm(type));
        const extra = { label: h.label || null, summary: h.summary || null, help: h.parameters || {} };
        if (r) Object.assign(r, extra); else put(type, fam, extra);
      }
    }
  }
  const docs = new Map(); // norm(basename) -> file, e.g. noisetop -> Noise_TOP.htm
  for (const f of docsFiles || []) {
    if (!/\.htm$/i.test(f) || /^Palette-/.test(f) || /_Class\.htm$/i.test(f)) continue;
    const exp = /^Experimental-/.test(f);
    const k = norm(f.replace(/^Experimental-/, '').replace(/\.htm$/i, ''));
    if (!exp || !docs.has(k)) docs.set(k, f); // the release page wins over its Experimental- copy
  }
  return { ops, index, docs, docsDir, hasHelp: !!paramHelp, hasDocs: !!docsFiles };
}

export function resolveOp(db, q) {
  const k = norm(q);
  if (db.ops.has(k)) return db.ops.get(k);
  for (const r of db.ops.values()) if (r.label && norm(r.label + r.family) === k) return r;
  return null;
}

function parEntry(p, help, withHelp) {
  const e = { name: p.name, label: p.label };
  if (p.style) e.style = p.style;
  if (p.default !== undefined && p.default !== null && p.default !== '') e.default = p.default;
  if (p.menu) {
    e.menu = p.menu.slice(0, MENU_CAP);
    const labels = (p.menuLabels || []).slice(0, MENU_CAP);
    if (labels.length && labels.some((l, i) => l !== e.menu[i])) e.menuLabels = labels;
    if (p.menu.length > MENU_CAP) e.menuMore = p.menu.length - MENU_CAP;
  } else if (p.normMin !== undefined && !(p.normMin === 0 && p.normMax === 1) && ['Float', 'Int', 'XYZW', 'XY', 'XYZ', 'UV', 'UVW', 'WH', null, undefined].includes(p.style)) {
    e.range = [p.normMin, p.normMax];
  }
  if (p.clampMin) e.min = p.min;
  if (p.clampMax) e.max = p.max;
  if (withHelp) { const h = help && (help[p.name] || help[p.tuplet]); if (h && h.summary) e.help = clip(h.summary, 220); }
  return e;
}

// {op, page?, par?, docs?} -> one op type in detail.
export function opHelp(db, q, { page, par, docs = false } = {}) {
  const r = resolveOp(db, q);
  if (!r) return { error: `unknown op type ${JSON.stringify(q)} (types look like noiseTOP, baseCOMP)`, did_you_mean: suggest(db, q) };
  const out = { op: r.type, family: r.family, build: BUILD };
  if (r.label) out.label = r.label;
  if (r.summary) out.summary = clip(r.summary, 400);
  if (r.status !== 'dumped') {
    out.note = r.status === 'not_created' ? `not in the live ${BUILD} dump: TD could not create it on this machine (hardware/licence op)`
      : r.status === 'failed' ? `not in the live ${BUILD} dump: probe failed (${r.failed})`
        : `only in TD's shipped help, not in the live ${BUILD} dump`;
  } else { out.inputs = r.in; out.outputs = r.out; }
  const filtered = !!(page || par);
  let list;
  if (r.pars) list = r.pars.filter((p) => p.page);
  else if (r.help) list = Object.entries(r.help).map(([name, h]) => ({ name, label: h.label, style: h.parType, page: '(help only, page unknown)' }));
  else list = [];
  const pagesAll = [...new Set(list.map((p) => p.page))];
  if (page) {
    const want = norm(page);
    list = list.filter((p) => norm(p.page) === want);
    if (!list.length) { out.error = `no page ${JSON.stringify(page)}`; out.pages = pagesAll; return out; }
  }
  if (par) {
    const want = norm(par);
    const exact = list.filter((p) => norm(p.name) === want || norm(p.tuplet) === want);
    list = exact.length ? exact : list.filter((p) => norm(p.name).includes(want) || norm(p.label).includes(want));
    if (!list.length) { out.error = `no par like ${JSON.stringify(par)} on ${r.type}`; out.pages = pagesAll; return out; }
  }
  out.count = list.length;
  const namesOnly = !filtered && list.length > FULL_LIST_CAP;
  const groups = new Map();
  for (const p of list) {
    if (!groups.has(p.page)) groups.set(p.page, []);
    groups.get(p.page).push(namesOnly ? p.name : parEntry(p, r.help, filtered));
  }
  out.pages = [...groups].map(([name, pars]) => ({ page: name, count: pars.length, pars }));
  if (namesOnly) out.hint = `${list.length} pars: names only; pass page (or par) for labels, defaults, menus and help text`;
  else if (!filtered && r.help) out.hint = 'pass page or par for each par\'s help text';
  if (docs) out.docs = docsFor(db, r);
  return out;
}

// Close type names for a miss: substring hits first, then the smallest edit distance.
export function lev(a, b) {
  const d = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    let prev = d[0]; d[0] = i;
    for (let j = 1; j <= b.length; j++) { const t = d[j]; d[j] = Math.min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1)); prev = t; }
  }
  return d[b.length];
}
export function suggest(db, q, n = 6) {
  const hits = search(db, q, { limit: n }).ops.map((o) => o.type);
  if (hits.length >= n) return hits;
  const k = norm(q);
  const ranked = [...db.ops.values()].map((r) => [r.type, lev(k, norm(r.type))]).filter(([t, d]) => d <= Math.max(2, Math.floor(k.length / 3)) && !hits.includes(t));
  ranked.sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0]));
  return [...hits, ...ranked.slice(0, n - hits.length).map(([t]) => t)];
}

// Summary section of the op's offline wiki article, as plain text.
export function docsFor(db, r) {
  if (!db.hasDocs) return { note: `offline help not found (${DOCS_DIR})` };
  const file = db.docs.get(norm(r.type)) || (r.label && db.docs.get(norm(r.label + r.family)));
  if (!file) return { note: `no offline article for ${r.type}` };
  const full = path.join(db.docsDir, file);
  try {
    const summary = htmlSummary(fs.readFileSync(full, 'utf8'), 1500);
    return summary ? { file: full, summary } : { file: full, note: 'the offline article has no summary text; see the file' };
  } catch (e) { return { file: full, note: `could not read: ${e.message}` }; }
}

const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', '#39': "'" };
export const decode = (s) => s.replace(/&(#x[0-9a-f]+|#\d+|\w+);/gi, (m, e) => {
  if (e[0] === '#') { const n = e[1].toLowerCase() === 'x' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10); return Number.isFinite(n) ? String.fromCodePoint(n) : m; }
  return ENT[e.toLowerCase()] ?? m;
});

export function htmlSummary(html, cap = 1500) {
  let i = html.indexOf('id="Summary"');
  let body;
  if (i >= 0) {
    body = html.slice(i);
    const ends = [body.indexOf('<h2', 1), body.indexOf('id="toc"')].filter((x) => x > 0);
    if (ends.length) body = body.slice(0, Math.min(...ends));
  } else {
    i = html.indexOf('mw-parser-output');
    body = i >= 0 ? html.slice(i) : html;
  }
  const paras = [];
  for (const m of body.matchAll(/<p>([\s\S]*?)<\/p>/g)) {
    if (/PythonIcon/.test(m[1])) continue;
    const t = decode(m[1].replace(/<[^>]+>/g, '')).replace(/\s+/g, ' ').trim();
    if (t) paras.push(t);
    if (i < 0 || html.indexOf('id="Summary"') < 0) break; // no Summary section: first paragraph only
  }
  const s = paras.join('\n\n');
  return s.length > cap ? s.slice(0, cap - 1) + '…' : s;
}

// {search} -> op types whose type/label (then summary) contain the words, best first.
export function search(db, q, { family, limit = 20 } = {}) {
  const words = String(q || '').toLowerCase().split(/\s+/).filter(Boolean).map(norm).filter(Boolean);
  const hits = [];
  for (const r of db.ops.values()) {
    if (family && r.family !== family) continue;
    const t = norm(r.type), l = norm(r.label), s = norm(r.summary);
    let score = 0, all = true;
    for (const w of words) {
      let ws = 0;
      if (t === w || l === w || t === w + norm(r.family)) ws = 100;
      else if (t.startsWith(w) || l.startsWith(w)) ws = 80;
      else if (t.includes(w) || l.includes(w)) ws = 60;
      else if (s.includes(w)) ws = 20;
      if (!ws) { all = false; break; }
      score += ws;
    }
    if (all && words.length) hits.push({ r, score: score - (r.status === 'dumped' ? 0 : 5) });
  }
  hits.sort((a, b) => b.score - a.score || a.r.type.localeCompare(b.r.type));
  const ops = hits.slice(0, limit).map(({ r }) => {
    const o = { type: r.type, family: r.family };
    if (r.label) o.label = r.label;
    if (r.summary) o.summary = clip(r.summary, 100);
    if (r.status !== 'dumped') o.dumped = false;
    return o;
  });
  return { search: q, count: hits.length, ops, ...(hits.length > limit ? { truncated: true } : {}) };
}

// {par} -> which op types have a parameter with that name.
export function parLookup(db, name, { family, limit = 60 } = {}) {
  const want = norm(name);
  const byFam = {};
  let count = 0, sample = null;
  const similar = new Map();
  for (const r of db.ops.values()) {
    if (family && r.family !== family) continue;
    const pars = r.pars ? r.pars : r.help ? Object.entries(r.help).map(([n, h]) => ({ name: n, label: h.label, style: h.parType })) : [];
    let hit = null;
    for (const p of pars) {
      const n = norm(p.name);
      if (n === want) { hit = p; break; }
      if (n.includes(want) || (want.length > 3 && norm(p.label).includes(want))) similar.set(p.name, (similar.get(p.name) || 0) + 1);
    }
    if (!hit) continue;
    count++;
    if (!sample && r.pars) sample = { op: r.type, ...parEntry(hit, r.help, true), page: hit.page };
    (byFam[r.family] ||= []).push(r.type);
  }
  const out = { par: name, count };
  if (sample) out.sample = sample;
  let left = limit;
  out.families = {};
  for (const fam of FAMILIES) {
    const list = byFam[fam];
    if (!list) continue;
    list.sort();
    out.families[fam] = { count: list.length, ops: list.slice(0, Math.max(left, 0)) };
    left -= list.length;
  }
  if (left < 0) out.truncated = true;
  if (!count) out.similar = [...similar].sort((a, b) => b[1] - a[1]).slice(0, 20).map(([n, c]) => `${n} (${c})`);
  return out;
}

// Reads the local files once; later calls return the cached db.
let CACHE = null;
export function loadDb() {
  if (CACHE) return CACHE;
  const read = (f) => JSON.parse(fs.readFileSync(f, 'utf8'));
  const idx = path.join(OPS_DIR, `INDEX_${BUILD}.json`);
  const index = fs.existsSync(idx) ? read(idx) : {};
  const dumps = {};
  for (const fam of FAMILIES) { const f = path.join(OPS_DIR, `ops_${fam}_${BUILD}.json`); if (fs.existsSync(f)) dumps[fam] = read(f); }
  let paramHelp = null, docsFiles = null;
  try { paramHelp = read(PAR_HELP); } catch { /* TD app missing: dump only */ }
  try { docsFiles = fs.readdirSync(DOCS_DIR); } catch { /* no offline wiki: docs part skipped */ }
  CACHE = buildDb({ index, dumps, paramHelp, docsFiles, docsDir: DOCS_DIR });
  return CACHE;
}

// The td_help tool body.
export function help(a = {}) {
  const db = loadDb();
  if (!db.ops.size) return { error: `no op data: docs/research/ops/*_${BUILD}.json and ${PAR_HELP} both missing` };
  const fam = a.family;
  if (a.op) return opHelp(db, a.op, { page: a.page, par: a.par, docs: a.docs });
  if (a.search) return search(db, a.search, { family: fam, limit: a.limit || 20 });
  if (a.par) return parLookup(db, a.par, { family: fam, limit: a.limit || 60 });
  return { usage: 'td_help {op:"noiseTOP", page?, par?, docs?} | {search:"blur", family?} | {par:"resolutionw", family?}', sources: { dump: BUILD, param_help: db.hasHelp, offline_docs: db.hasDocs }, op_types: db.ops.size };
}
