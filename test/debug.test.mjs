// Offline tests for the debug toolkit (src/debug.js + its MCP tools). No TouchDesigner: a fake TD on an in-process
// bridge, a fake toeexpand, temp logs. Run: node --test test/debug.test.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import test, { after } from 'node:test';
import zlib from 'node:zlib';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import WebSocket from 'ws';

const REPO = path.resolve(new URL('..', import.meta.url).pathname);
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'jtd-dbg-'));
const freePort = () => new Promise((r) => { const s = net.createServer().listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => r(p)); }); });
const PORT = await freePort();
process.env.JTD_STATE_DIR = path.join(dir, 'state');
process.env.JTD_BRIDGE_PORT = String(PORT);
process.env.JTD_LOG_DIR = path.join(dir, 'logs');
process.env.JTD_OUTPUT_DIR = path.join(dir, 'output');

// fake toeexpand: writes <file>.dir with a tiny network, exits 1 like the real one on 2025.31550
const FAKE_EXPAND = path.join(dir, 'fake_toeexpand.mjs');
const textFile = (s) => { const b = Buffer.from(s); const h = Buffer.alloc(27); h.write('2\n*', 0, 'latin1'); h.writeUInt32BE(b.length, 23); return Buffer.concat([h, b]); };
fs.writeFileSync(FAKE_EXPAND, `#!${process.execPath}
import fs from 'node:fs'; import path from 'node:path';
const d = path.resolve(process.argv[2] + '.dir');
const w = (rel, data) => { fs.mkdirSync(path.dirname(path.join(d, rel)), { recursive: true }); fs.writeFileSync(path.join(d, rel), data); };
w('.build', 'version 099\\nbuild 2025.31550\\n');
w('project1.n', 'COMP:container\\nend\\n');
w('project1/noise1.n', 'TOP:noise\\nend\\n');
w('project1/level1.n', 'TOP:level\\ninputs\\n{\\n0 \\tnoise1\\n}\\nend\\n');
w('project1/out1.n', 'TOP:null\\nflags =  display on\\ninputs\\n{\\n0 \\tlevel1\\n}\\nend\\n');
w('project1/movie.n', 'TOP:moviefilein\\nend\\n');
w('project1/movie.parm', '?\\nfile 0 /nope/gone.mov\\n?\\n');
w('project1/osc.n', 'DAT:oscin\\nend\\n');
w('project1/osc.parm', '?\\nport 0 7001\\n?\\n');
w('project1/exec1.n', 'DAT:execute\\nend\\n');
w('project1/exec1.parm', '?\\nframestart 0 on\\n?\\n');
w('project1/exec1.text', Buffer.from(${JSON.stringify(textFile("def onFrameStart(frame):\n    op('noise1').par.seed = frame\n").toString('base64'))}, 'base64'));
console.log('expanded'); process.exit(1);
`, { mode: 0o755 });
process.env.JTD_TOEEXPAND = FAKE_EXPAND;

const B = await import('../src/bridge.js');
const D = await import('../src/debug.js');
const TOKEN = B.token();
const bridge = await B.runBridge({ port: PORT });
const sockets = new Set();
after(async () => { for (const s of sockets) s.terminate(); await bridge.close(); fs.rmSync(dir, { recursive: true, force: true }); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function fakeTD(handler) {
  const w = new WebSocket(`ws://127.0.0.1:${PORT}/`);
  sockets.add(w);
  w.on('error', () => {});
  w.on('message', async (data) => {
    const m = JSON.parse(String(data));
    if (m.type === 'ping') return w.send(JSON.stringify({ type: 'pong' }));
    try { w.send(JSON.stringify({ id: m.id, ok: true, result: await handler(m.cmd, m.args) })); } catch (e) { w.send(JSON.stringify({ id: m.id, ok: false, error: e.message })); }
  });
  w.opened = new Promise((r) => w.on('open', () => { w.send(JSON.stringify({ type: 'hello', token: TOKEN, td: { build: '2025.31550', project: 'fake.toe', pid: 1, protocol: 1 } })); r(); }));
  return w;
}
async function waitTD() { for (let i = 0; i < 50; i++) { const h = await B.bridgeHealth(); if (h?.td) return; await sleep(40); } throw new Error('td never connected'); }

// A small live-style summary like td/debug.py analyze() returns.
const SUMMARY = {
  source: 'live', root: '/project1', project: 'fake.toe', build: '2025.31550', ops: 4, total_ops: 4, ms: 3, frames: 1,
  inventory: { by_family: { TOP: 3, COMP: 1 }, by_type: { noiseTOP: 1 }, types: 3, comp_tree: { p: '/project1', t: 'containerCOMP', ops: 4, kids: [{ p: '/project1/fx', t: 'baseCOMP', ops: 2 }] }, packages: [{ p: '/project1/w', kind: 'clone of /sys/x', kids: 3 }] },
  graph: { edges_by_kind: { wire: 2, expr: 1 }, edges_total: 3, edges: [], top_level: { nodes: [{ p: '/project1/src', t: 'noiseTOP', ops: 1 }, { p: '/project1/fx', t: 'baseCOMP', ops: 2 }, { p: '/project1/out "q"', t: 'nullTOP', ops: 1 }], edges: [['/project1/src', '/project1/fx', 'wire', 1], ['/project1/fx', '/project1/out "q"', 'expr', 2]] } },
  expressions: { count: 1, items: [{ p: '/project1/fx/a', par: 'tx', expr: "op('b')['x']", refs: ['/project1/fx/b'] }] },
  binds: { count: 0, items: [] }, exports: { count: 0, items: [] }, unresolved_refs: { count: 1, items: [{ p: '/a', par: 'tx', ref: "op('gone')", tried: '/gone' }] },
  dat_refs: { count: 0, items: [] }, extensions: { count: 0, items: [] },
  python: { exec_dats: { count: 1, items: [{ p: '/project1/ex', t: 'executeDAT', active: true, triggers: ['framestart'], watches: null }] }, callbacks: { count: 0, items: [] }, script_ops: { count: 0, items: [] }, modules: { count: 0, items: [] }, where: { exec_dats: 1, exec_dats_active: 1, frame_callbacks: ['/project1/ex'], callback_dats: 0, script_ops: 0, extensions: 0 } },
  files: { count: 1, missing: 1, items: [{ p: '/project1/movie', par: 'file', path: '/nope.mov', exists: false }] },
  devices: { count: 1, items: [{ p: '/project1/osc', t: 'oscinDAT', kind: 'OSC in', active: false, settings: { port: 7001 } }] },
  health: { errors: { count: 1, items: [{ p: '/project1/movie', t: 'moviefileinTOP', msg: 'Failed to open | file\nline2' }] }, warnings: { count: 0, items: [] }, script_errors: { count: 0, items: [] }, cook_always: { count: 0, items: [] }, bypassed: { count: 0, items: [] }, locked: { count: 0, items: [] }, parked: { count: 0, items: [] }, exporting: { count: 0, items: [] }, display_flags: 1, render_flags: 0, viewers_on: 2, dead_branches: { count: 1, items: ['/project1/orphan'] }, heavy: [{ p: '/project1/src', t: 'noiseTOP', cpu_ms: 2, gpu_ms: 1, cooks: 9, stale: false }], gpu_memory_mb: [] },
};

test('reports: mermaid, dot, markdown, compact reply, files', () => {
  const m = D.mermaid(SUMMARY);
  assert.match(m, /^flowchart LR\n/);
  assert.match(m, /n0\["src<br\/>noiseTOP \(1\)"\]/);
  assert.match(m, /n0 -->\|wire 1\| n1/);
  assert.match(m, /n1 -.->\|ref 2\| n2/, 'non-wire kinds are dashed refs');
  assert.ok(!m.includes('"q"'), 'quotes in labels are escaped');
  assert.match(D.dot(SUMMARY), /"\/project1\/src" -> "\/project1\/fx" \[label="wire 1"\]/);
  const md = D.renderMarkdown(SUMMARY);
  for (const h of ['## Summary', '## Inventory', '### COMP tree', '## Top-level flow', '```mermaid', '## Where Python runs', '## Devices and ports', '## External files', '**MISSING**', '## Cook health', 'Failed to open \\| file line2', '/project1/orphan', '### Packages (listed, not entered']) assert.ok(md.includes(h), h);
  const files = D.writeReport(SUMMARY, path.join(dir, 'rep'), 'fake_project1', { now: new Date(Date.UTC(2026, 9, 26, 10, 0, 0)) });
  assert.equal(path.basename(files.md), 'fake_project1_2026-10-26T10-00-00Z.md');
  for (const f of Object.values(files)) assert.ok(fs.statSync(f).size > 20, f);
  const c = D.compactAnalysis(SUMMARY, files);
  assert.equal(c.health.errors, 1); assert.equal(c.files.missing, 1); assert.match(c.health.first_errors[0], /^\/project1\/movie: Failed to open/);
  assert.ok(JSON.stringify(c).length < 6000);
});

test('journal: exec.log pairing, calls.jsonl merge, filters, lines', () => {
  const ex = D.execEvents([
    { time: '2026-10-26T10:00:00.000Z', phase: 'start', code: "op('/project1/lab/a').par.x = 1", pid: 11 },
    { time: '2026-10-26T10:00:01.000Z', phase: 'start', code: 'boom', pid: 22, agent: 'lane-b' },
    { time: '2026-10-26T10:00:00.500Z', phase: 'end', code: "op('/project1/lab/a').par.x = 1", pid: 11, ok: true, result: '{"stdout":"","visible":{"new_ops":3,"pane":"/project1/lab","layout":[{"comp":"/project1/lab"}]}}' },
    { time: '2026-10-26T10:00:05.000Z', phase: 'start', code: 'never answered', pid: 11 },
    { time: '2026-10-26T10:00:02.000Z', phase: 'end', code: 'boom', pid: 22, ok: false, error: 'NameError: boom\ntb' },
  ]);
  assert.equal(ex.length, 3);
  assert.deepEqual([ex[0].ok, ex[0].ms, ex[0].new_ops, ex[0].pane], [true, 500, 3, '/project1/lab']);
  assert.deepEqual(ex[0].comps, ['/project1/lab/a', '/project1/lab']);
  assert.equal(ex[1].error, 'NameError: boom');
  assert.equal(ex[2].ok, null); assert.match(ex[2].error, /no reply/);
  const calls = D.callEvents([{ t: '2026-10-26T10:00:00.600Z', cmd: 'exec', ok: true, ms: 40 }, { t: '2026-10-26T10:00:03.000Z', cmd: 'create', ok: true, ms: 5, path: '/project1/lab', args: '{"type":"noiseTOP"}' }]);
  const all = D.mergeEvents(ex, calls, [{ t: '2026-10-26T10:00:03.010Z', id: 'snap1', tool: 'td_create', comp: '/project1/lab' }]);
  assert.deepEqual(all.map((e) => e.tool), ['td_exec', 'td_exec', 'td_create', 'td_exec'], 'the exec row from calls.jsonl is folded into exec.log');
  assert.equal(all[2].snapshot, 'snap1');
  const now = Date.parse('2026-10-26T10:10:00Z');
  assert.equal(D.filterEvents(all, { agent: 'lane-b' }).length, 1);
  assert.equal(D.filterEvents(all, { agent: '11' }).length, 2);
  assert.equal(D.filterEvents(all, { comp: '/project1/lab' }).length, 2);
  assert.equal(D.filterEvents(all, { failures: true }).length, 2);
  assert.equal(D.filterEvents(all, { since: '-9m', now }).length, 0);
  assert.equal(D.filterEvents(all, { since: '2026-10-26T10:00:02.500Z' }).length, 2);
  assert.match(D.journalLine(all[0]), /td_exec ok \(500ms \+3 ops pane \/project1\/lab pid 11\): op\('\/project1\/lab\/a'\)/);
  assert.match(D.journalLine(all[3]), / \?\? .*!! no reply/);
  assert.equal(D.sinceMs('-2h', now), now - 7200e3);
});

test('snapshots: off by default, before/after gz + index when on, diff, prune', async () => {
  const out = path.join(dir, 'snapout');
  const texts = ['{"format":"jtd-net","v":1,"root":"/p/a","build":"2025.31550","depth":2,"include_defaults":false,"dat_text":true,"xy":false}\n{"p":".","t":"noiseTOP","pars":{"seed":"1"}}\n{"end":true,"ops":1,"total":1,"truncated":false}\n'];
  texts.push(texts[0].replace('"seed":"1"', '"seed":"2"'));
  let n = 0;
  const calls = [];
  const fakeCall = async (cmd, args) => { calls.push([cmd, args]); return { text: texts[Math.min(n++, 1)], ops: 1, truncated: false }; };
  assert.equal(await D.withSnapshots('td_set_pars', { path: '/p/a' }, fakeCall, async () => 'ran', { cfg: {}, outDir: out }), 'ran');
  assert.equal(calls.length, 0, 'off: no extra calls');
  const r = await D.withSnapshots('td_set_pars', { path: '/p/a', pars: { seed: 2 } }, fakeCall, async () => 'ran', { cfg: { debugSnapshots: true }, outDir: out });
  assert.equal(r, 'ran');
  assert.deepEqual(calls.map((c) => [c[0], c[1].path, c[1].depth]), [['net_export', '/p/a', 2], ['net_export', '/p/a', 2]]);
  const sdir = path.join(out, 'debug', 'snapshots');
  const idx = fs.readFileSync(path.join(sdir, 'index.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  assert.equal(idx.length, 1); assert.equal(idx[0].tool, 'td_set_pars'); assert.equal(idx[0].comp, '/p/a');
  assert.equal(zlib.gunzipSync(fs.readFileSync(path.join(sdir, idx[0].before))).toString(), texts[0]);
  const d = D.snapshotDiff(sdir, idx[0].id.slice(0, 24));
  assert.deepEqual(d.counts, { added: 0, removed: 0, changed: 1, rewired: 0 });
  assert.deepEqual(d.changed[0].pars.seed, ['1', '2']);
  await assert.rejects(D.withSnapshots('td_set_pars', { path: '/p/a' }, fakeCall, async () => { throw new Error('td said no'); }, { cfg: { debugSnapshots: true }, outDir: out }), /td said no/);
  assert.equal(fs.readFileSync(path.join(sdir, 'index.jsonl'), 'utf8').trim().split('\n').length, 2, 'a failed call is still recorded');
  assert.equal(D.SNAP_TARGET.td_exec({ code: "op('/project1/lab/a').par.x=1\nop('/project1/lab/b')" }), '/project1/lab');
  assert.equal(D.SNAP_TARGET.td_exec({ code: "op('/project1/lab/a').cook()" }), '/project1/lab/a');
  assert.equal(D.SNAP_TARGET.td_delete({ paths: ['/project1/x'] }), '/project1');
  assert.equal(D.SNAP_TARGET.td_dat_text({ path: '/p/d' }), null, 'reading a DAT changes nothing');
  assert.equal(D.SNAP_TARGET.td_list, undefined, 'read-only tools take no snapshot');
  assert.ok(D.pruneSnapshots(sdir, 10) >= 1);
  assert.equal(fs.readdirSync(sdir).filter((f) => f.endsWith('.gz')).length, 0);
});

test('why text + watch compaction', () => {
  const t = { p: '/p/out', t: 'nullTOP', via: 'target', up: [{ p: '/p/lv', t: 'levelTOP', via: 'wire in0', up: [{ p: '/p/lfo', t: 'lfoCHOP', via: "expr opacity <- ['chan1']", more: true }] }, { p: '/p/gone', via: 'ref par top', missing: true }] };
  assert.deepEqual(D.whyLines(t), ['/p/out [nullTOP]', '  <- /p/lv [levelTOP]  via wire in0', "    <- /p/lfo [lfoCHOP]  via expr opacity <- ['chan1'] (depth limit)", '  <- /p/gone  via ref par top MISSING']);
  const w = D.compactWatch({ duration_s: 5, timeline: Array.from({ length: 200 }, (_, i) => ({ t: i / 40, fps: 60 })), par_changes_all: [1], top_cook: [] }, '/f.json');
  assert.ok(w.fps_timeline.length <= 40); assert.equal(w.timeline, undefined); assert.equal(w.par_changes_all, undefined); assert.equal(w.file, '/f.json');
});

test('expand + offline analysis through python3 td/debug.py (fake toeexpand, cache)', () => {
  const toe = path.join(dir, 'show.toe');
  fs.writeFileSync(toe, 'not really a toe');
  const cache = path.join(dir, 'cache');
  const x = D.expandCopy(toe, cache, FAKE_EXPAND);
  assert.equal(x.cached, false); assert.ok(fs.existsSync(path.join(x.dir, '.build')));
  assert.equal(D.expandCopy(toe, cache, FAKE_EXPAND).cached, true, 'same content: expanded once');
  assert.equal(fs.readFileSync(toe, 'utf8'), 'not really a toe', 'the original is untouched');
  const s = D.analyzeExpanded(x.dir, { path: '/project1' }, { root: REPO, file: toe, folder: dir });
  assert.equal(s.source, 'file'); assert.equal(s.build, '2025.31550'); assert.equal(s.root, '/project1');
  assert.equal(s.files.missing, 1); assert.equal(s.devices.items[0].kind, 'OSC in');
  assert.deepEqual(s.python.where.frame_callbacks, ['/project1/exec1']);
  assert.ok(s.graph.edges.some(([a, b, k]) => a === '/project1/noise1' && b === '/project1/exec1' && k === 'script'));
  assert.throws(() => D.resolveToe('x.txt', dir), /not a \.toe/);
  assert.throws(() => D.resolveToe('missing.toe', dir), /no such file/);
});

test('MCP tools: td_analyze / td_why / td_watch / td_debug_panel via fake TD; td_journal + td_analyze_file without TD; snapshot hook end to end', async () => {
  const net = (seed) => `{"format":"jtd-net","v":1,"root":"/project1/a","build":"2025.31550","depth":2,"include_defaults":false,"dat_text":true,"xy":false}\n{"p":".","t":"noiseTOP","pars":{"seed":"${seed}"}}\n{"end":true,"ops":1,"total":1,"truncated":false}\n`;
  let seed = 1;
  const got = [];
  const w = fakeTD((cmd, args) => {
    got.push(cmd);
    if (cmd === 'analyze') return { ...SUMMARY, gotArgs: args };
    if (cmd === 'why') return { path: args.path, tree: { p: args.path, t: 'nullTOP', via: 'target', up: [{ p: '/x', via: 'wire in0' }] }, nodes: 2 };
    if (cmd === 'watch') return { duration_s: 1, timeline: [{ t: 0, frame: 1 }, { t: 1, frame: 61, fps: 60 }], par_changes_all: [], top_cook: [], gotArgs: args };
    if (cmd === 'debug_panel_build') return { path: args.path, args };
    if (cmd === 'net_export') return { text: net(seed), ops: 1, truncated: false };
    if (cmd === 'set_pars') { seed = 2; return { set: ['seed'] }; }
    return {};
  });
  await w.opened; await waitTD();
  fs.mkdirSync(path.join(dir, 'logs'), { recursive: true });
  fs.writeFileSync(path.join(dir, 'logs', 'exec.log'), [
    { time: '2026-10-26T09:00:00.000Z', phase: 'start', code: "op('/project1/lab').create(noiseTOP)" },
    { time: '2026-10-26T09:00:00.100Z', phase: 'end', code: "op('/project1/lab').create(noiseTOP)", ok: true, result: '{"visible":{"new_ops":1}}' },
  ].map((r) => JSON.stringify(r)).join('\n') + '\n');
  const client = new Client({ name: 'jtd-dbg', version: '0' });
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [path.join(REPO, 'src', 'server.js')], env: { ...process.env }, stderr: 'ignore' }));
  const J = async (name, a) => { const r = await client.callTool({ name, arguments: a }); assert.ok(!r.isError, `${name}: ${r.content?.[0]?.text}`); return JSON.parse(r.content[0].text); };
  try {
    const an = await J('td_analyze', { path: '/project1', limit: 100, include: ['packages'] });
    assert.equal(an.health.errors, 1);
    assert.match(path.basename(an.files_written.md), /^fake_project1_.*\.md$/);
    assert.ok(fs.readFileSync(an.files_written.md, 'utf8').includes('```mermaid'));
    assert.ok((await client.callTool({ name: 'td_analyze', arguments: { include: ['everything'] } })).isError, 'include values are checked');
    const why = await J('td_why', { path: '/project1/out', par: 'opacity' });
    assert.equal(why.text, '/project1/out [nullTOP]\n  <- /x  via wire in0');
    const wa = await J('td_watch', { path: '/project1', seconds: 1 });
    assert.ok(fs.existsSync(wa.file)); assert.deepEqual(wa.fps_timeline, [[0, null], [1, 60]]);
    assert.deepEqual(await J('td_debug_panel', { scope: '/project1/lab' }), { args: { scope: '/project1/lab' } });
    // snapshot hook: on for every server through the flag file, then a td_set_pars is recorded and diffable
    assert.equal((await J('td_journal', { snapshots: true })).snapshots.on, true);
    await J('td_set_pars', { path: '/project1/a', pars: { seed: 2 } });
    const jr = await J('td_journal', { limit: 10 });
    const snapEv = jr.events.find((e) => e.snapshot);
    assert.ok(snapEv, JSON.stringify(jr.events));
    assert.equal(jr.events[0].tool, 'td_exec'); assert.equal(jr.events[0].new_ops, 1);
    const diff = await J('td_journal', { diff: snapEv.snapshot });
    assert.deepEqual(diff.changed[0].pars.seed, ['1', '2']);
    assert.equal((await J('td_journal', { snapshots: false })).snapshots.on, false);
    w.close(); await sleep(150);
    for (let i = 0; i < 50 && (await B.bridgeHealth())?.td; i++) await sleep(40);
    const fileRep = await J('td_analyze_file', { toe: path.join(dir, 'show.toe'), path: '/project1' });
    assert.equal(fileRep.source, 'file'); assert.equal(fileRep.files.missing, 1);
    assert.ok(fileRep.files_written.md.startsWith(path.join(dir, 'output', 'debug')));
    const off = await client.callTool({ name: 'td_analyze', arguments: {} });
    assert.ok(off.isError); assert.match(off.content[0].text, /not connected/);
    assert.ok((await J('td_journal', { failures: true })).total >= 0, 'journal works with TD disconnected');
  } finally { await client.close(); }
  assert.ok(got.includes('analyze') && got.includes('net_export'));
});
