// Offline tests: no TouchDesigner. A fake TD (ws client) plays the /jazib_mcp side. Run: node --test test/offline.test.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import test, { after } from 'node:test';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import WebSocket from 'ws';

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'jtd-test-'));
const freePort = () => new Promise((r) => { const s = net.createServer().listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => r(p)); }); });
const PORT = await freePort();
process.env.JTD_STATE_DIR = path.join(dir, 'state');
process.env.JTD_BRIDGE_PORT = String(PORT);
process.env.JTD_LOG_DIR = path.join(dir, 'logs');
process.env.JTD_OUTPUT_DIR = path.join(dir, 'output');
process.env.JTD_DIAG_DIR = new URL('./fixtures/crash', import.meta.url).pathname; // td_crash_report reads fixture .ips
const B = await import('../src/bridge.js');
const { CONFIG } = await import('../src/config.js');
const TOKEN = B.token();
const bridge = await B.runBridge({ port: PORT });
const base = `http://127.0.0.1:${PORT}`;
const H = { 'x-jtd-token': TOKEN };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const sockets = new Set();
after(async () => { for (const s of sockets) s.terminate(); await bridge.close(); fs.rmSync(dir, { recursive: true, force: true }); });

// Fake TD: connects, sends hello, answers requests with handler(cmd, args) (throw → ok:false with traceback;
// undefined → no reply).
function fakeTD({ port = PORT, token = TOKEN, hello = true, handler = () => ({}) } = {}) {
  const w = new WebSocket(`ws://127.0.0.1:${port}/`);
  sockets.add(w);
  w.closed = new Promise((r) => w.on('close', r));
  w.on('error', () => {});
  w.on('message', async (data) => {
    const m = JSON.parse(String(data));
    if (m.type === 'ping') return w.send(JSON.stringify({ type: 'pong' }));
    try {
      const result = await handler(m.cmd, m.args);
      if (result !== undefined) w.send(JSON.stringify({ id: m.id, ok: true, result }));
    } catch (e) { w.send(JSON.stringify({ id: m.id, ok: false, error: e.message, traceback: `Traceback (most recent call last):\n  ${m.cmd}\n${e.message}` })); }
  });
  w.opened = new Promise((r, j) => { w.on('open', () => { if (hello) w.send(JSON.stringify({ type: 'hello', token, td: { build: '2025.31550', project: 'fake.toe', pid: 1, protocol: 1 } })); r(); }); w.on('error', j); });
  return w;
}
const health = async () => (await fetch(`${base}/health`, { headers: H })).json();
async function waitTD(want = true) { for (let i = 0; i < 50; i++) { if ((await health()).td === want) return; await sleep(40); } throw new Error(`td never ${want}`); }
const ctl = (body) => fetch(`${base}/ctl`, { method: 'POST', headers: { ...H, 'content-type': 'application/json' }, body: JSON.stringify(body) });

test('state, logs and port come from the overrides, never the real ones', () => {
  assert.equal(CONFIG.stateDir, path.join(dir, 'state'));
  assert.equal(CONFIG.logDir, path.join(dir, 'logs'));
  assert.notEqual(CONFIG.bridgePort, 9335);
});

test('token file: 48 lowercase hex, mode 600', () => {
  assert.match(TOKEN, /^[0-9a-f]{48}$/);
  assert.equal(fs.statSync(B.TOKEN_FILE).mode & 0o777, 0o600);
  assert.equal(B.token(), TOKEN, 'stable once created');
});

test('/health and /ctl refuse a missing or wrong token', async () => {
  for (const headers of [{}, { 'x-jtd-token': 'f'.repeat(48) }]) {
    assert.equal((await fetch(`${base}/health`, { headers })).status, 403);
    assert.equal((await fetch(`${base}/ctl`, { method: 'POST', headers, body: '{"cmd":"status"}' })).status, 403);
  }
  assert.equal((await fetch(`${base}/health`, { headers: H })).status, 200);
});

test('web origins refused on HTTP even with the token', async () => {
  for (const origin of ['http://evil.example', 'https://evil.example', 'file://']) {
    assert.equal((await fetch(`${base}/health`, { headers: { ...H, origin } })).status, 403, origin);
  }
  assert.equal((await fetch(`${base}/health`, { headers: { ...H, origin: 'touchdesigner' } })).status, 200, 'other origins allowed');
});

test('web origins refused on upgrade; no origin accepted on any path', async () => {
  for (const origin of ['http://evil.example', 'https://evil.example', 'file://']) {
    const w = new WebSocket(`ws://127.0.0.1:${PORT}/`, { origin });
    await assert.rejects(new Promise((r, j) => { w.on('open', r); w.on('error', j); }), undefined, origin);
  }
  const w = new WebSocket(`ws://127.0.0.1:${PORT}/any/path`);
  sockets.add(w);
  await new Promise((r, j) => { w.on('open', r); w.on('error', j); });
  w.close();
});

test('a bad hello token is closed and never becomes TD', async () => {
  const w = fakeTD({ token: '0'.repeat(48) });
  await w.opened;
  await w.closed;
  assert.equal((await health()).td, false);
});

test('no hello within the timeout closes the socket', async () => {
  const b2 = await B.runBridge({ port: 0, helloMs: 200 });
  try {
    const w = fakeTD({ port: b2.port, hello: false });
    await w.opened;
    const t0 = Date.now();
    await w.closed;
    assert.ok(Date.now() - t0 < 2000);
  } finally { await b2.close(); }
});

test('503 when TD is not connected', async () => {
  const r = await ctl({ cmd: 'status' });
  assert.equal(r.status, 503);
  const m = await r.json();
  assert.equal(m.ok, false);
  assert.match(m.error, /TouchDesigner not connected/);
  await assert.rejects(B.call('status'), /TouchDesigner not connected/);
});

test('round trip: ok result, and error with traceback (HTTP and call())', async () => {
  const w = fakeTD({ handler: (cmd, args) => { if (cmd === 'boom') throw new Error('td.tdError: bad par'); return { cmd, args }; } });
  await w.opened; await waitTD();
  try {
    const h = await health();
    assert.equal(h.tdInfo.build, '2025.31550');
    assert.ok(h.tdInfo.since);
    assert.deepEqual(await B.call('list', { path: '/' }), { cmd: 'list', args: { path: '/' } });
    const m = await (await ctl({ cmd: 'boom', args: {} })).json();
    assert.equal(m.ok, false);
    assert.equal(m.error, 'td.tdError: bad par');
    assert.match(m.traceback, /^Traceback/);
    await assert.rejects(B.call('boom'), (e) => /bad par\nTraceback/.test(e.message) && /Traceback/.test(e.traceback));
  } finally { w.close(); await w.closed; await waitTD(false); }
});

test('ctl timeout when TD never replies', async () => {
  const w = fakeTD({ handler: () => undefined });
  await w.opened; await waitTD();
  try {
    const r = await ctl({ cmd: 'hang', timeoutMs: 200 });
    assert.equal(r.status, 504);
    assert.match((await r.json()).error, /timeout after 200 ms on hang/);
  } finally { w.close(); await w.closed; await waitTD(false); }
});

test('TD log messages go to bridge.log', async () => {
  const w = fakeTD();
  await w.opened; await waitTD();
  w.send(JSON.stringify({ type: 'log', level: 'warn', msg: 'hello from fake TD' }));
  await sleep(100);
  w.close(); await w.closed; await waitTD(false);
  const log = fs.readFileSync(B.LOG, 'utf8');
  assert.match(log, /TD warn: hello from fake TD/);
  assert.match(log, /origin=\(none\)/);
});

test('a second hello replaces the first connection', async () => {
  const a = fakeTD({ handler: () => 'A' });
  await a.opened; await waitTD();
  const b = fakeTD({ handler: () => 'B' });
  await b.opened;
  await a.closed;
  await waitTD();
  try { assert.equal(await B.call('who'), 'B'); } finally { b.close(); await b.closed; await waitTD(false); }
});

// ---------------------------------------------------------------- MCP server over stdio
const NET_H = '{"format":"jtd-net","v":1,"root":"/r/look","type":"baseCOMP","build":"2025.31550","depth":99,"include_defaults":false,"dat_text":true,"xy":false}';
const NET_A = [NET_H, '{"p":".","t":"baseCOMP"}', '{"p":"level1","t":"levelTOP","in":[["noise1",0]],"pars":{"opacity":0.5}}', '{"end":true,"ops":2,"total":2,"truncated":false}', ''].join('\n');
const NET_B = [NET_H, '{"p":".","t":"baseCOMP"}', '{"p":"blur1","t":"blurTOP","in":[["noise1",0]]}', '{"p":"level1","t":"levelTOP","in":[["blur1",0]],"pars":{"gamma":"=me.digits"}}', '{"end":true,"ops":3,"total":3,"truncated":false}', ''].join('\n');
const AE_FIXTURE = new URL('./fixtures/ae_export_eased.json', import.meta.url).pathname;
const PNG = Buffer.from('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8ffff3f0005fe02fea7d6a4b00000000049454e44ae426082', 'hex');

test('server: all td_* tools registered; td_exec logged; td_screenshot returns an image', async () => {
  const w = fakeTD({ handler: (cmd, args) => {
    if (cmd === 'exec') { if (args.code === 'raise') throw new Error('NameError: x'); if (args.dialogs) return { gotArgs: args }; return { stdout: '', stderr: '', result: 42 }; }
    if (cmd === 'screenshot') { fs.writeFileSync(args.file, PNG); return { file: args.file, width: 1, height: 1 }; }
    if (cmd === 'status') return { build: '2025.31550', fps: 60 };
    if (cmd === 'comfy_send' || cmd === 'comfy_result') return { gotArgs: args };
    if (cmd === 'net_export') return { text: NET_B, ops: 3, total: 3, chars: NET_B.length, truncated: false, notes: [], gotArgs: args };
    if (cmd === 'publish' || cmd === 'osc_learn' || cmd === 'publish_status') return { cmd, gotArgs: args };
    if (cmd.startsWith('tda_') || cmd === 'link' || cmd === 'live_audio') return { cmd, args };
    if (cmd === 'import_ae_anim' || cmd === 'export_ae_data') return { got: args };
    if (cmd.startsWith('midi_')) return { cmd, args };
    if (cmd === 'health_sample') return args.counts_only ? { frame: 100, playing: true, rate: 60, counts: { '/p/n': 5 } } : { frame: 160, playing: true, rate: 60, path: '/p', build: '2025.31550', nodes: [{ path: '/p/n', type: 'noiseTOP', family: 'TOP', cooks: 5, cookTime: 1 }], scriptErrors: {}, notes: [] };
    if (cmd === 'health_probe') return { cooked: ['/p/n'], quiet: [], never: [], skipped: [], missing: [], unprobed: [] };
    if (['checkpoint', 'restore_checkpoint', 'presave'].includes(cmd)) return { cmd, gotArgs: args };
    if (cmd.startsWith('timeline_')) return { cmd, gotArgs: args, frames_asked: 3 };
    if (cmd.startsWith('library_')) return { cmd, gotArgs: args };
    if (['record_chop', 'shadertoy', 'isf', 'osc_expose', 'layer_mixer', 'cook_active', 'tox_save', 'custom_pars', 'set_pars'].includes(cmd)) return { cmd, gotArgs: args };
    return {};
  } });
  await w.opened; await waitTD();
  const client = new Client({ name: 'jtd-offline', version: '0' });
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [new URL('../src/server.js', import.meta.url).pathname], env: { ...process.env }, stderr: 'ignore' }));
  try {
    const names = (await client.listTools()).tools.map((t) => t.name).sort();
    const want = ['td_guide', 'td_status', 'td_list', 'td_info', 'td_get_pars', 'td_set_pars', 'td_create', 'td_delete', 'td_rename', 'td_move', 'td_connect', 'td_disconnect', 'td_dat_text', 'td_errors', 'td_screenshot', 'td_custom_pars', 'td_tox_save', 'td_tox_load', 'td_save_project', 'td_perf', 'td_exec', 'td_reload', 'td_layout', 'td_housekeeping', 'td_window_capture', 'td_help', 'td_focus', 'td_selection', 'td_inspect', 'td_net_export', 'td_net_diff', 'td_comfy_build', 'td_comfy_status', 'td_comfy_send', 'td_comfy_result', 'td_comfy_cancel', 'td_comfy_free', 'td_publish', 'td_publish_status', 'td_osc_learn', 'td_link', 'td_link_status', 'td_tda', 'td_live_audio', 'td_import_ae_anim', 'td_import_blender', 'td_export_ae_data', 'td_render_for_ae', 'td_midi_build', 'td_midi_status', 'td_midi_learn', 'td_midi_map', 'td_midi_unmap', 'td_midi_list', 'td_midi_bank', 'td_midi_save', 'td_midi_load', 'td_midi_monitor', 'td_midi_simulate', 'td_midi_preset', 'td_health', 'td_trace', 'td_save_hook', 'td_log', 'td_offline', 'td_record_chop', 'td_shadertoy', 'td_osc_expose', 'td_layer_mixer', 'td_cook_active', 'td_autosave', 'td_bring_home', 'td_isf'];
    want.push('td_analyze', 'td_analyze_file', 'td_why', 'td_watch', 'td_journal', 'td_debug_panel'); // src/debug.js
    want.push('td_crash_report'); // src/crash.js
    want.push('td_checkpoint', 'td_restore_checkpoint', 'td_presave'); // lose nothing (td/safety.py)
    want.push('td_timeline_state', 'td_timeline_show', 'td_timeline_edit', 'td_timeline_transport', 'td_timeline_export', 'td_timeline_load', 'td_timeline_record'); // src/timeline.js
    want.push('td_library_export', 'td_library_list', 'td_library_info', 'td_library_load'); // src/library.js
    want.push('td_vat_load', 'td_metavido'); // src/vat.js, src/metavido.js (lane T)
    assert.deepEqual(names, [...want].sort());

    const crep = JSON.parse((await client.callTool({ name: 'td_crash_report', arguments: { ips: 'TouchDesigner-2026-10-26-150020.ips' } })).content[0].text);
    assert.deepEqual(crep.known.by_stack, ['T-74-readback-after-change', 'T-76-textsize-after-create']);
    assert.equal(crep.crash.pid, 4242);
    assert.ok((await client.callTool({ name: 'td_crash_report', arguments: { ips: 'x.txt' } })).isError);

    const st = JSON.parse((await client.callTool({ name: 'td_status', arguments: {} })).content[0].text);
    assert.equal(st.td_connected, true); assert.equal(st.fps, 60);

    const ok = await client.callTool({ name: 'td_exec', arguments: { code: '1+41' } });
    assert.ok(!ok.isError); assert.equal(JSON.parse(ok.content[0].text).result, 42);
    const bad = await client.callTool({ name: 'td_exec', arguments: { code: 'raise' } });
    assert.ok(bad.isError); assert.match(bad.content[0].text, /NameError: x\nTraceback/);
    const rows = fs.readFileSync(path.join(dir, 'logs', 'exec.log'), 'utf8').trim().split('\n').map(JSON.parse);
    assert.deepEqual(rows.map((r) => [r.phase, r.code, r.ok]), [['start', '1+41', undefined], ['end', '1+41', true], ['start', 'raise', undefined], ['end', 'raise', false]]);
    assert.ok(rows.every((r) => !Number.isNaN(Date.parse(r.time))));
    assert.match(rows[3].error, /NameError/);

    const dg = JSON.parse((await client.callTool({ name: 'td_exec', arguments: { code: 'ui.messageBox("a", "b")', dialogs: { messageBox: 1, chooseFile: null } } })).content[0].text);
    assert.deepEqual(dg.gotArgs.dialogs, { messageBox: 1, chooseFile: null }, 'dialog answers reach TD');
    assert.ok((await client.callTool({ name: 'td_exec', arguments: { code: '1', dialogs: { messageBox: -1 } } })).isError);

    const shot = await client.callTool({ name: 'td_screenshot', arguments: { path: '/project1/out1' } });
    assert.ok(!shot.isError, shot.content?.[0]?.text);
    assert.equal(shot.content[0].type, 'image'); assert.equal(shot.content[0].mimeType, 'image/png');
    assert.deepEqual(Buffer.from(shot.content[0].data, 'base64'), PNG);
    const meta = JSON.parse(shot.content[1].text);
    assert.match(path.basename(meta.file), /^project1_out1_.*\.png$/);
    assert.equal(path.dirname(meta.file), path.join(dir, 'output'));

    const ex = JSON.parse((await client.callTool({ name: 'td_net_export', arguments: { path: '/r/look', file: 'snap/look_after' } })).content[0].text);
    assert.equal(ex.file, path.join(dir, 'output', 'snap', 'look_after.jtdnet')); assert.equal(fs.readFileSync(ex.file, 'utf8'), NET_B);
    const esc = await client.callTool({ name: 'td_net_export', arguments: { path: '/r/look', file: '/etc/x' } });
    assert.ok(esc.isError); assert.match(esc.content[0].text, /must be under/);
    const inline = await client.callTool({ name: 'td_net_export', arguments: { path: '/r/look' } });
    assert.equal(inline.content[0].text, NET_B);
    fs.writeFileSync(path.join(dir, 'output', 'before.jtdnet'), NET_A);
    const live = JSON.parse((await client.callTool({ name: 'td_net_diff', arguments: { a: 'before', b: '/r/look' } })).content[0].text);
    assert.equal(live.b_from, 'live /r/look'); assert.deepEqual(live.counts, { added: 1, removed: 0, changed: 1, rewired: 1 });

    const cs = JSON.parse((await client.callTool({ name: 'td_comfy_send', arguments: { comp: '/project1/comfy', workflow: 'wf/api.json', inputs: { '6.text': 'x' } } })).content[0].text);
    assert.equal(cs.gotArgs.workflow, path.resolve(new URL('../..', import.meta.url).pathname, 'wf/api.json'), 'relative workflow -> bundle root');
    assert.equal(cs.gotArgs.out_dir, path.join(dir, 'output', 'comfy')); assert.equal(cs.gotArgs.inputs['6.text'], 'x');
    const cj = JSON.parse((await client.callTool({ name: 'td_comfy_send', arguments: { comp: '/c', workflow: '{"1":{}}' } })).content[0].text);
    assert.equal(cj.gotArgs.workflow, '{"1":{}}', 'inline JSON passes through');
    const cr = JSON.parse((await client.callTool({ name: 'td_comfy_result', arguments: { comp: '/c' } })).content[0].text);
    assert.equal(cr.gotArgs.out_dir, path.join(dir, 'output', 'comfy'));
    const pub = JSON.parse((await client.callTool({ name: 'td_publish', arguments: { name: 'look1', source: '/project1/look1/out1', transport: 'both', res: [1080, 1920] } })).content[0].text);
    assert.deepEqual(pub, { cmd: 'publish', gotArgs: { name: 'look1', source: '/project1/look1/out1', transport: 'both', res: [1080, 1920] } }, 'no active sent = TD default inactive');
    const badName = await client.callTool({ name: 'td_publish', arguments: { name: 'bad name', source: '/a' } });
    assert.ok(badName.isError, 'publish name checked by the schema');
    const badRes = await client.callTool({ name: 'td_publish', arguments: { name: 'x', source: '/a', res: [8, 99999] } });
    assert.ok(badRes.isError, 'res range checked by the schema');
    const lb = JSON.parse((await client.callTool({ name: 'td_osc_learn', arguments: {} })).content[0].text);
    assert.equal(lb.gotArgs.file, undefined, 'build exports nothing');
    const ls = JSON.parse((await client.callTool({ name: 'td_osc_learn', arguments: { action: 'stop', arena_build: '7.23.2 (51094)' } })).content[0].text);
    assert.equal(ls.gotArgs.file, path.join(dir, 'output', 'osc_addresses_7.23.2_51094.json'));
    const lt = JSON.parse((await client.callTool({ name: 'td_osc_learn', arguments: { action: 'start', seconds: 5 } })).content[0].text);
    assert.equal(lt.gotArgs.file, path.join(dir, 'output', 'osc_addresses_arena.json'), 'start with seconds exports at the end');
    const lo = JSON.parse((await client.callTool({ name: 'td_osc_learn', arguments: { action: 'start' } })).content[0].text);
    assert.equal(lo.gotArgs.file, undefined);
    const tda = async (a) => JSON.parse((await client.callTool({ name: 'td_tda', arguments: a })).content[0].text);
    assert.deepEqual(await tda({ action: 'check', path: '/x', accept_risk: true }), { cmd: 'tda_check', args: {} });
    assert.deepEqual(await tda({ action: 'load', accept_risk: true, path: '/x' }), { cmd: 'tda_load', args: { accept_risk: true } });
    assert.deepEqual(await tda({ action: 'status', path: '/p/tda', connect: true }), { cmd: 'tda_status', args: { path: '/p/tda' } });
    assert.ok((await client.callTool({ name: 'td_tda', arguments: { action: 'install' } })).isError, 'no install action');
    const lk = JSON.parse((await client.callTool({ name: 'td_link', arguments: { enable: false } })).content[0].text);
    assert.deepEqual(lk, { cmd: 'link', args: { enable: false } });
    const la = JSON.parse((await client.callTool({ name: 'td_live_audio', arguments: { mode: 'device' } })).content[0].text);
    assert.deepEqual(la, { cmd: 'live_audio', args: { mode: 'device' } });
    // TD + After Effects tools: the parse happens here, TD gets tables; files only under output/ae_out/
    const imp = JSON.parse((await client.callTool({ name: 'td_import_ae_anim', arguments: { file: AE_FIXTURE } })).content[0].text);
    assert.equal(imp.got.parent, '/project1'); assert.equal(imp.got.name, 'ae_title_card');
    assert.equal(imp.got.baked.length, 61); assert.equal(imp.got.baked[0][0], 'title_opacity');
    assert.equal(imp.got.text.length, 3); assert.equal(imp.got.markers.length, 4); assert.ok(imp.warnings.length >= 3);
    const exd = JSON.parse((await client.callTool({ name: 'td_export_ae_data', arguments: { chop: '/p/out', file: 'curves/a', format: 'csv', frames: 10 } })).content[0].text);
    assert.equal(exd.got.file, path.join(dir, 'output', 'ae_out', 'curves', 'a.csv')); assert.equal(exd.got.frames, 10);
    for (const f of ['/etc/x.mov', '../../x.mov', 'b\u00e9.mov', 'x.mp4']) {
      const r = await client.callTool({ name: 'td_render_for_ae', arguments: { source: '/p/noise1', file: f, frames: 30 } });
      assert.ok(r.isError, f); assert.match(r.content[0].text, /must be under|ASCII|must end with/);
    }

    // 27 Oct upgrades: hex / mirror / stamp pass through; record file under output/recordings; shadertoy file read Node-side
    const up = async (name, a) => { const r = await client.callTool({ name, arguments: a }); if (r.isError) return { error: r.content[0].text }; return JSON.parse(r.content[0].text); };
    assert.deepEqual((await up('td_set_pars', { path: '/p/c', pars: { color: '#00baff' } })).gotArgs.pars, { color: '#00baff' });
    assert.deepEqual((await up('td_custom_pars', { path: '/p/fx', page: 'Blur', mirror: { src: 'blur1', pars: ['size*'] } })).gotArgs.mirror, { src: 'blur1', pars: ['size*'] });
    assert.match((await up('td_custom_pars', { path: '/p/fx', page: 'X', mirror: { nope: 1 } })).error, /src/);
    const tx = await up('td_tox_save', { path: '/p/fx', file: '/tmp/fx.tox', bump: 'minor' });
    assert.deepEqual(tx.gotArgs, { path: '/p/fx', file: '/tmp/fx.tox', bump: 'minor' });
    assert.ok((await up('td_tox_save', { path: '/p/fx', file: '/tmp/fx.tox', bump: 'huge' })).error);
    const rc = await up('td_record_chop', { chop: '/p/audio', seconds: 2, file: 'kick', channels: 'kick*' });
    assert.equal(rc.gotArgs.file, path.join(dir, 'output', 'recordings', 'kick.csv')); assert.equal(rc.gotArgs.seconds, 2);
    for (const a of [{ chop: '/p/a' }, { chop: '/p/a', seconds: 1, frames: 3 }, { chop: '/p/a', frames: 3, file: '../../x.csv' }, { chop: '/p/a', frames: 3, file: 'x.txt' }]) {
      assert.ok((await up('td_record_chop', a)).error, JSON.stringify(a));
    }
    const glslFile = path.join(dir, 'st.frag');
    fs.writeFileSync(glslFile, 'void mainImage(out vec4 c, in vec2 p) { c = vec4(1.0); }');
    const sty = await up('td_shadertoy', { file: glslFile, compute: true, licence: 'MIT' });
    assert.match(sty.gotArgs.code, /mainImage/); assert.equal(sty.gotArgs.file, undefined); assert.equal(sty.gotArgs.compute, true);
    assert.ok((await up('td_shadertoy', {})).error, 'code or file');
    assert.ok((await up('td_shadertoy', { code: 'x', file: glslFile })).error, 'not both');
    assert.ok((await up('td_shadertoy', { file: path.join(dir, 'x.png') })).error, 'extension');
    const isfFile = path.join(dir, 'My Fx.fs');
    fs.writeFileSync(isfFile, '/*{}*/ void main() { gl_FragColor = vec4(1.0); }');
    const isf1 = await up('td_isf', { file: isfFile, panel: 'plain' });
    assert.match(isf1.gotArgs.code, /gl_FragColor/); assert.equal(isf1.gotArgs.source_name, 'My Fx.fs'); assert.equal(isf1.gotArgs.base_dir, dir);
    assert.equal(isf1.gotArgs.vs, undefined, 'no sibling .vs'); assert.equal(isf1.gotArgs.file, undefined); assert.equal(isf1.gotArgs.panel, 'plain');
    fs.writeFileSync(path.join(dir, 'My Fx.vs'), 'void main() { isf_vertShaderInit(); }');
    assert.match((await up('td_isf', { file: isfFile })).gotArgs.vs, /isf_vertShaderInit/, 'sibling .vs read');
    assert.ok((await up('td_isf', {})).error, 'code or file');
    assert.ok((await up('td_isf', { code: 'x', vs_file: isfFile })).error, 'vs_file needs file');
    assert.ok((await up('td_isf', { file: path.join(dir, 'x.png') })).error, 'extension');
    assert.ok((await up('td_isf', { code: 'x', panel: 'fancy' })).error, 'panel enum');
    assert.deepEqual((await up('td_osc_expose', { comp: '/p/look', layout: 'osct', oscquery: true })).gotArgs, { comp: '/p/look', layout: 'osct', oscquery: true });
    assert.ok((await up('td_osc_expose', { comp: '/p/look', layout: 'udp' })).error);
    assert.deepEqual((await up('td_layer_mixer', { layers: 5, sources: ['/p/a'], blend: 'screen' })).gotArgs, { layers: 5, sources: ['/p/a'], blend: 'screen' });
    assert.ok((await up('td_layer_mixer', { layers: 17 })).error); assert.ok((await up('td_layer_mixer', { blend: 'burn' })).error);
    const ck = await up('td_checkpoint', { path: '/p/lab/FX', note: 'after build', list: true });
    assert.deepEqual(ck.gotArgs, { path: '/p/lab/FX', note: 'after build', list_only: true, root: path.join(dir, 'output', 'checkpoints') }, 'checkpoints under output/checkpoints');
    assert.equal((await up('td_checkpoint', { path: '/p/lab/FX' })).gotArgs.list_only, undefined);
    assert.ok((await up('td_checkpoint', { path: '/p/lab/FX', frames: 1 })).error, 'verify needs >= 2 frames');
    const rs = await up('td_restore_checkpoint', { path: '/p/lab/FX', which: 1 });
    assert.deepEqual(rs.gotArgs, { path: '/p/lab/FX', which: 1, root: path.join(dir, 'output', 'checkpoints') });
    assert.ok((await up('td_presave', { min_s: 5 })).error, 'min_s >= 10');
    assert.deepEqual((await up('td_presave', { check: { cmd: 'exec', args: { code: 'x' } } })).gotArgs, { check: { cmd: 'exec', args: { code: 'x' } } });
    assert.deepEqual((await up('td_cook_active', { parent: '/p/bank', active: ['clip2'] })).gotArgs, { parent: '/p/bank', active: ['clip2'] });
    // component library: root = <repo>/library; names checked
    const lib1 = await up('td_library_load', { name: 'GN_x', parent: '/p/lab/_libtest', newname: 'c1' });
    assert.deepEqual({ ...lib1.gotArgs, root: undefined }, { name: 'GN_x', parent: '/p/lab/_libtest', newname: 'c1', root: undefined });
    assert.ok(lib1.gotArgs.root.endsWith(`${path.sep}library`));
    assert.ok((await up('td_library_load', { name: 'bad name', parent: '/p' })).error);
    assert.ok((await up('td_library_export', { path: '/p/lab/X', frames: 2 })).error, 'frames >= 5');
    // TL_timeline agent API: ops/times pass through; files only under output/timeline/
    const ops = [{ op: 'add_key', lane: 'level', t: '8b', v: 0.9 }, { op: 'add_marker', t: '3.1.1', name: 'Verse' }];
    assert.deepEqual((await up('td_timeline_edit', { ops, dry: true })).gotArgs, { ops, dry: true });
    assert.ok((await up('td_timeline_edit', { ops: [{ op: 'explode' }] })).error, 'op names checked');
    assert.ok((await up('td_timeline_edit', { ops: [] })).error, 'at least one op');
    assert.deepEqual((await up('td_timeline_transport', { action: 'seek', t: '@Drop' })).gotArgs, { action: 'seek', t: '@Drop' });
    assert.ok((await up('td_timeline_transport', { rate: 9 })).error);
    assert.deepEqual((await up('td_timeline_state', { at: [1, '2b'] })).gotArgs, { at: [1, '2b'] });
    const tle = await up('td_timeline_export', { what: 'lanes_csv', fps: 60 });
    assert.equal(tle.gotArgs.file, path.join(dir, 'output', 'timeline', 'exports', 'TL_timeline_lanes_csv.csv'));
    assert.ok((await up('td_timeline_export', { file: '../../../x.json' })).error);
    assert.ok((await up('td_timeline_export', { what: 'show', file: 'x.csv' })).error);
    fs.mkdirSync(path.join(dir, 'output', 'timeline', 'shows'), { recursive: true });
    fs.writeFileSync(path.join(dir, 'output', 'timeline', 'shows', 'gig.json'), JSON.stringify({ format: 'tl-show', v: 1, markers: [[1, 'A']] }));
    assert.deepEqual((await up('td_timeline_load', { file: 'gig', mode: 'merge' })).gotArgs, { mode: 'merge', show: { format: 'tl-show', v: 1, markers: [[1, 'A']] } });
    assert.ok((await up('td_timeline_load', {})).error, 'show or file');
    assert.ok((await up('td_timeline_record', { file: 'take1.mp4' })).error, '.mov only');
    const TLJ = await import('../src/timeline.js');
    assert.equal(TLJ.tlFile(path.join(dir, 'output'), 'renders', 'take1', '.mov'), path.join(dir, 'output', 'timeline', 'renders', 'take1.mov'));
    assert.throws(() => TLJ.tlFile(path.join(dir, 'output'), 'renders', '/etc/take1.mov', '.mov'), /must be under/);

    // MIDI mapping tools: args pass through; schema checks kinds, ranges and .json files
    const midi = async (name, a) => JSON.parse((await client.callTool({ name, arguments: a })).content[0].text);
    assert.deepEqual(await midi('td_midi_simulate', { kind: 'cc', channel: 1, number: 7, value: 127 }), { cmd: 'midi_simulate', args: { kind: 'cc', channel: 1, number: 7, value: 127 } });
    assert.deepEqual(await midi('td_midi_map', { mapping: { target: '/project1/look', par: 'Gain', number: 7, takeover: 'pickup' } }), { cmd: 'midi_map', args: { mapping: { target: '/project1/look', par: 'Gain', number: 7, takeover: 'pickup' } } });
    assert.deepEqual(await midi('td_midi_learn', { target: '/p/x', par: 'Gain', wait_s: 2 }), { cmd: 'midi_learn', args: { target: '/p/x', par: 'Gain', wait_s: 2 } });
    assert.deepEqual(await midi('td_midi_save', { file: 'show.json' }), { cmd: 'midi_save', args: { file: 'show.json' } });
    for (const [name, a] of [['td_midi_simulate', { kind: 'sysex' }], ['td_midi_simulate', { channel: 17 }], ['td_midi_map', { mapping: { mode: 'spin' } }], ['td_midi_save', { file: 'x.txt' }], ['td_midi_bank', { bank: 0 }]]) {
      assert.ok((await client.callTool({ name, arguments: a })).isError, `${name} ${JSON.stringify(a)} refused by the schema`);
    }

    const hl = JSON.parse((await client.callTool({ name: 'td_health', arguments: { path: '/p', interval: 0 } })).content[0].text);
    assert.equal(hl.findings.find((f) => f.kind === 'not-pulled')?.paths[0], '/p/n', 'td_health: sample, probe, verdict');

    w.close(); await w.closed; await waitTD(false);
    const dry = JSON.parse((await client.callTool({ name: 'td_import_ae_anim', arguments: { file: AE_FIXTURE, dry: true, units: 'ae' } })).content[0].text);
    assert.equal(dry.dry, true); assert.equal(dry.channels, 8); assert.equal(dry.units, 'ae'); assert.equal(dry.comp.frames, 60);
    const lg = JSON.parse((await client.callTool({ name: 'td_log', arguments: { failures: true } })).content[0].text);
    assert.ok(lg.rows.some((r) => r.cmd === 'exec' && r.code === 'raise' && /NameError/.test(r.error)), 'journal keeps failures, works offline');
    const sm = JSON.parse((await client.callTool({ name: 'td_log', arguments: { summary: true } })).content[0].text);
    assert.ok(sm.by_cmd.health_sample.calls === 2 && sm.by_cmd.health_probe.calls === 2);
    const ofl = await client.callTool({ name: 'td_offline', arguments: { file: '/nope/x.toe' } });
    assert.ok(ofl.isError); assert.match(ofl.content[0].text, /no such file/);
    const hp = JSON.parse((await client.callTool({ name: 'td_help', arguments: { op: 'noiseTOP', par: 'resolutionw' } })).content[0].text);
    assert.equal(hp.family, 'TOP'); assert.equal(hp.pages[0].pars[0].name, 'resolutionw', 'td_help works with TD disconnected');
    const offDiff = JSON.parse((await client.callTool({ name: 'td_net_diff', arguments: { a: 'before', b: 'snap/look_after' } })).content[0].text);
    assert.deepEqual(offDiff.added, ['blur1'], 'two files diff without TD');
    const offLive = await client.callTool({ name: 'td_net_diff', arguments: { a: 'before', b: '/r/look' } });
    assert.ok(offLive.isError); assert.match(offLive.content[0].text, /not connected/);
    const off = JSON.parse((await client.callTool({ name: 'td_status', arguments: {} })).content[0].text);
    assert.equal(off.td_connected, false); assert.match(off.how_to_connect, /jazib_mcp/);
    const nope = await client.callTool({ name: 'td_list', arguments: {} });
    assert.ok(nope.isError); assert.match(nope.content[0].text, /not connected/);
  } finally { await client.close(); }
});

test('netdiff: parse, added/removed/changed/rewired, warnings', async () => {
  const { diffNet, parseNet, looksLikeNetText } = await import('../src/netdiff.js');
  assert.equal(parseNet(NET_A).ops.size, 2);
  assert.throws(() => parseNet('{"x":1}'), /jtd-net/);
  assert.throws(() => parseNet('nope'), /not JSON/);
  assert.equal(diffNet(NET_A, NET_A).same, true);
  const d = diffNet(NET_A, NET_B);
  assert.equal(d.same, false);
  assert.deepEqual(d.added, ['blur1']); assert.deepEqual(d.removed, []); assert.deepEqual(d.rewired, ['level1']);
  assert.deepEqual(d.changed, [{ p: 'level1', in: [[['noise1', 0]], [['blur1', 0]]], pars: { opacity: [0.5, null], gamma: [null, '=me.digits'] } }]);
  const r = diffNet(NET_B, NET_A);
  assert.deepEqual(r.removed, ['blur1']);
  const cpA = NET_A.replace('"t":"baseCOMP"', '"t":"baseCOMP","cp":{"Controls":{"Speed":{"style":"Float","v":1}}}');
  const cpB = NET_A.replace('"t":"baseCOMP"', '"t":"baseCOMP","cp":{"Controls":{"Speed":{"style":"Float","v":2}}}');
  assert.deepEqual(diffNet(cpA, cpB).changed[0].cp, { 'Controls/Speed': [{ style: 'Float', v: 1 }, { style: 'Float', v: 2 }] });
  const other = NET_A.replace('"include_defaults":false', '"include_defaults":true').replace('"truncated":false', '"truncated":true');
  assert.equal(diffNet(NET_A, other).warnings.length, 2);
  assert.equal(diffNet(NET_A, NET_B, { max: 0 }).truncated, true);
  assert.ok(looksLikeNetText(NET_A)); assert.ok(!looksLikeNetText('/project1/x')); assert.ok(!looksLikeNetText('snap/a'));
});

test('pickWindow: main TD window by default, title match, dialogs, none', async () => {
  const { pickWindow } = await import('../src/windows.js');
  const wins = [{ id: 1, title: '', w: 2056, h: 39 }, { id: 2, title: 'PF26 Show Panel', w: 600, h: 928 },
    { id: 3, title: 'TouchDesigner 2025.31550: /x/home.toe', w: 2056, h: 1291 }, { id: 4, title: 'Missing Parent Shortcut', w: 260, h: 134 }];
  assert.equal(pickWindow(wins).id, 3);
  assert.equal(pickWindow(wins, 'show panel').id, 2);
  assert.equal(pickWindow(wins, 'Missing').id, 4);
  assert.equal(pickWindow(wins, 'nope'), null);
  assert.equal(pickWindow([]), null);
});

// ---------------------------------------------------------------- td_help (src/help.js), pure functions on fixtures
test('td_help: op detail, page/par filters, search, par lookup, misses', async () => {
  const H = await import('../src/help.js');
  const par = (name, page, extra = {}) => ({ name, label: name.toUpperCase(), page, style: 'Float', default: 0, tuplet: name, normMin: 0, normMax: 1, clampMin: false, clampMax: false, min: 0, max: 1, ...extra });
  const db = H.buildDb({
    dumps: {
      TOP: { dumped: [
        { type: 'noiseTOP', inputs: 2, outputs: 1, pars: [par('pageindex', null), par('type', 'Noise', { style: 'Menu', default: 'simplex3d', menu: ['perlin2d', 'simplex3d'], menuLabels: ['Perlin 2D', 'Simplex 3D'] }),
          par('period', 'Noise', { normMax: 2, clampMin: true }), par('resolutionw', 'Common', { style: 'Int', default: 256 })] },
        { type: 'blurTOP', inputs: 1, outputs: 1, pars: [par('size', 'Blur'), par('resolutionw', 'Common')] }],
      skipped_not_created: ['kinectTOP'], failed: [{ type: 'svgTOP', error: 'Invalid number' }] },
      CHOP: { dumped: [{ type: 'lfoCHOP', inputs: 3, outputs: 1, pars: [par('frequency', 'LFO', { menu: Array.from({ length: 50 }, (_, i) => `m${i}`), menuLabels: Array.from({ length: 50 }, (_, i) => `m${i}`) })] }] },
    },
    paramHelp: { help: { TOPs: { noiseTOP: { label: 'Noise', summary: 'The Noise TOP generates noise.', parameters: { period: { label: 'Period', summary: 'Peak  separation.', parType: 'Float' } } },
      kinectTOP: { label: 'Kinect', summary: 'Kinect camera.', parameters: { active: { label: 'Active', parType: 'Toggle', summary: '' } } },
      lumablurTOP: { label: 'Luma Blur', summary: 'Blurs by luminance.', parameters: {} } } } },
  });
  const n = H.opHelp(db, 'Noise TOP');
  assert.equal(n.op, 'noiseTOP'); assert.equal(n.label, 'Noise'); assert.equal(n.inputs, 2); assert.equal(n.count, 3, 'page-less pageindex dropped');
  assert.deepEqual(n.pages.map((p) => p.page), ['Noise', 'Common']);
  const [type, period] = n.pages[0].pars;
  assert.deepEqual(type.menu, ['perlin2d', 'simplex3d']); assert.deepEqual(type.menuLabels, ['Perlin 2D', 'Simplex 3D']);
  assert.deepEqual(period.range, [0, 2]); assert.equal(period.min, 0); assert.equal(period.max, undefined); assert.equal(period.help, undefined, 'no help text unfiltered');
  const f = H.opHelp(db, 'noisetop', { page: 'noise', par: 'period' });
  assert.equal(f.count, 1); assert.equal(f.pages[0].pars[0].help, 'Peak separation.');
  assert.match(H.opHelp(db, 'noiseTOP', { page: 'Nope' }).error, /no page/);
  assert.equal(H.opHelp(db, 'noiseTOP', { par: 'resolution' }).pages[0].pars[0].name, 'resolutionw', 'par substring');
  assert.deepEqual(H.opHelp(db, 'nosieTOP').did_you_mean, ['noiseTOP']);
  const lfo = H.opHelp(db, 'lfoCHOP').pages[0].pars[0];
  assert.equal(lfo.menu.length, 40); assert.equal(lfo.menuMore, 10); assert.equal(lfo.menuLabels, undefined, 'labels equal names: omitted');
  const k = H.opHelp(db, 'kinectTOP');
  assert.match(k.note, /could not create/); assert.equal(k.pages[0].pars[0].style, 'Toggle');
  assert.match(H.opHelp(db, 'svgTOP').note, /probe failed/);
  const s = H.search(db, 'blur');
  assert.deepEqual(s.ops.map((o) => o.type), ['blurTOP', 'lumablurTOP']); assert.equal(s.count, 2);
  assert.deepEqual(H.search(db, 'noise', { family: 'CHOP' }).ops, []);
  assert.equal(H.search(db, 'generates').ops[0].type, 'noiseTOP', 'summary match');
  const p = H.parLookup(db, 'resolutionw');
  assert.equal(p.count, 2); assert.deepEqual(p.families.TOP.ops, ['blurTOP', 'noiseTOP']);
  assert.equal(H.parLookup(db, 'resolutionw', { limit: 1 }).truncated, true);
  assert.deepEqual(H.parLookup(db, 'resol').similar, ['resolutionw (2)']);
  assert.equal(H.lev('nosie', 'noise'), 2);
});

test('td_help: offline wiki summary text, entities, Python icon line skipped', async () => {
  const H = await import('../src/help.js');
  const html = '<h2><span id="Summary">Summary</span></h2>\n<p>The Noise <span class="t">TOP</span> makes &amp; mixes&#39;s.\n</p><p>Second   para.</p><p><a href="/File:PythonIcon.png"><img></a>x_Class</p><div id="toc"><p>not this</p></div>';
  assert.equal(H.htmlSummary(html), "The Noise TOP makes & mixes's.\n\nSecond para.");
  assert.equal(H.htmlSummary(html, 10), 'The Noise…');
  assert.equal(H.htmlSummary('<div class="mw-parser-output"><p>First.</p><p>Second.</p></div>'), 'First.');
  const db = H.buildDb({ dumps: { TOP: { dumped: [{ type: 'noiseTOP', pars: [] }] } }, docsFiles: ['Experimental-Noise_TOP.htm', 'Noise_TOP.htm', 'NoiseTOP_Class.htm'], docsDir: '/nowhere' });
  assert.equal(db.docs.get('noisetop'), 'Noise_TOP.htm', 'release page wins over Experimental-');
  assert.match(H.docsFor(H.buildDb({}), { type: 'noiseTOP' }).note, /offline help not found/);
});

test('td_help: the real 2025.31550 dump loads and answers', async () => {
  const H = await import('../src/help.js');
  const r = H.help({ op: 'noiseTOP', page: 'Noise' });
  assert.equal(r.family, 'TOP'); assert.ok(r.pages[0].pars.some((p) => p.name === 'type' && p.menu.includes('simplex3d')));
  assert.ok(H.help({ par: 'resolutionw' }).families.TOP.count > 50);
  assert.ok(H.help({ search: 'blur' }).ops.some((o) => o.type === 'blurTOP'));
  assert.ok(JSON.stringify(H.help({ op: 'containerCOMP' })).length < 20000, 'big COMPs stay compact');
  assert.equal(H.loadDb(), H.loadDb(), 'cached');
});

test('ae: AE temporal bezier is exact (endpoints, symmetric ease midpoint, reference cubic), linear, hold', async () => {
  const A = await import('../src/ae.js');
  const k = (t, v, out, inn, oE, iE) => ({ t, v, out, in: inn, outEase: oE, inEase: iE });
  const ease = { speed: 0, influence: 33.333333 };
  const keys = [k(0, 0, 'bezier', 'bezier', ease, ease), k(1, 100, 'bezier', 'bezier', ease, ease)];
  assert.equal(A.evalKeys(keys, 0), 0); assert.equal(A.evalKeys(keys, 1), 100); assert.equal(A.evalKeys(keys, 2), 100);
  assert.ok(Math.abs(A.evalKeys(keys, 0.5) - 50) < 1e-9, 'easy ease is symmetric');
  assert.ok(A.evalKeys(keys, 0.1) < 10 && A.evalKeys(keys, 0.9) > 90, 'eased: slow start/end');
  // reference: dense u sweep of the same control points, then linear interpolation in x
  const strong = [k(0, 10, 'bezier', 'bezier', { speed: 50, influence: 80 }, null), k(2, 30, 'bezier', 'bezier', null, { speed: -5, influence: 20 })];
  const P = [[0, 10], [0 + 0.8 * 2, 10 + 50 * 0.8 * 2], [2 - 0.2 * 2, 30 - -5 * 0.2 * 2], [2, 30]];
  const bz = (i, u) => { const m = 1 - u; return m * m * m * P[0][i] + 3 * m * m * u * P[1][i] + 3 * m * u * u * P[2][i] + u * u * u * P[3][i]; };
  for (const t of [0.25, 0.7, 1.3, 1.9]) {
    let ref = null;
    for (let j = 0; j < 200000; j++) { const u0 = j / 200000, u1 = (j + 1) / 200000; const x0 = bz(0, u0), x1 = bz(0, u1); if (x0 <= t && t <= x1) { const f = (t - x0) / (x1 - x0); ref = bz(1, u0) + f * (bz(1, u1) - bz(1, u0)); break; } }
    assert.ok(Math.abs(A.evalKeys(strong, t) - ref) < 1e-4, `t=${t}: ${A.evalKeys(strong, t)} vs ${ref}`);
  }
  const lin = [k(0, 0, 'linear', 'linear'), k(4, 8, 'linear', 'linear')];
  assert.ok(Math.abs(A.evalKeys(lin, 1) - 2) < 1e-9, 'linear = dv/dt');
  const hold = [k(0, 1, 'hold', 'hold'), k(1, 5, 'hold', 'hold')];
  assert.equal(A.evalKeys(hold, 0.99), 1); assert.equal(A.evalKeys(hold, 1), 5);
});

test('ae: parse the export fixture (tables, unit map, warnings, caps) and ffprobe output', async () => {
  const A = await import('../src/ae.js');
  const doc = JSON.parse(fs.readFileSync(AE_FIXTURE, 'utf8'));
  const r = A.parseAeExport(doc);
  assert.deepEqual(r.comp, { name: 'Title Card', width: 1080, height: 1920, fps: 30, start: 0, duration: 2, frames: 60 });
  assert.deepEqual(r.channels, ['title_opacity', 'title_position_x', 'title_position_y', 'title_scale_x', 'title_scale_y', 'title_scale_z', 'flash_opacity', 'flash_glow_intensity']);
  const col = (n) => r.baked[0].indexOf(n);
  assert.equal(r.baked[1 + 15][col('title_opacity')], 0.5, 'opacity /100, eased midpoint');
  assert.equal(r.baked[1][col('title_position_y')], Number((0.5 - 1460 / 1920).toFixed(6)), 'y down -> y up fraction');
  assert.equal(r.baked[1][col('title_position_x')], 0, 'centre = 0');
  assert.equal(r.baked[1 + 29][col('flash_opacity')], 0); assert.equal(r.baked[1 + 30][col('flash_opacity')], 1, 'hold steps on the key');
  assert.deepEqual(r.text.slice(1).map((x) => x[2]), ['HELLO', 'PRISM FEST'], 'tab inside text cleaned');
  assert.deepEqual(r.markers.slice(1).map((x) => x[2]), ['drop', 'out', 'hit']);
  assert.equal(r.keys.length - 1, 2 + 4 + 6 + 3 + 2);
  for (const w of [/spatial/, /expression not evaluated/, /parented/, /without ease/]) assert.ok(r.warnings.some((x) => w.test(x)), String(w));
  const raw = A.parseAeExport(doc, { units: 'ae', rate: 10 });
  assert.equal(raw.comp.frames, 20); assert.equal(raw.baked[1][raw.baked[0].indexOf('title_position_y')], 1460);
  assert.throws(() => A.parseAeExport(doc, { comp: 'nope' }), /no comp named/);
  assert.throws(() => A.parseAeExport({ items: [] }), /no CompItem/);
  assert.throws(() => A.parseAeExport({}), /not an ae_project_export_json/);
  assert.throws(() => A.parseAeExport(doc, { rate: 240 * 5000 }), /bake too large/);
  assert.equal(A.chanName('Glow / Intensity 2'), 'glow_intensity_2');
  const fp = A.parseFfprobe(JSON.stringify({ streams: [{ codec_name: 'prores', codec_tag_string: 'ap4h', pix_fmt: 'yuva444p12le', width: 1080, height: 1920, r_frame_rate: '30/1', nb_read_frames: '30' }] }));
  assert.deepEqual(fp, { frames: 30, codec: 'prores', tag: 'ap4h', pix_fmt: 'yuva444p12le', width: 1080, height: 1920, fps: 30 });
  assert.equal(A.parseFfprobe('{"streams":[]}'), null);
});

// ---------------------------------------------------------------- td-atlas port: journal, health, offline (pure)
test('journal: rows, redaction, rotation, read/summary, MUTATING parity with handlers.py', async () => {
  const J = await import('../src/journal.js');
  const tok = 'a'.repeat(48);
  const row = JSON.parse(J.journalRow({ cmd: 'exec', args: { code: `api_key = "abc123"\nx = '${tok}'\nsk-${'Z'.repeat(20)}` }, ok: false, ms: 12.345, error: 'NameError: x\ntb', token: tok }));
  assert.equal(row.ok, false); assert.equal(row.ms, 12.3); assert.equal(row.error, 'NameError: x');
  assert.ok(!row.code.includes('abc123') && !row.code.includes(tok) && !row.code.includes('ZZZZ'), row.code);
  const ro = JSON.parse(J.journalRow({ cmd: 'info', args: { path: '/a', allPars: true }, ok: true, ms: 1 }));
  assert.equal(ro.path, '/a'); assert.equal(ro.args, undefined, 'read-only calls keep only the path');
  const set = JSON.parse(J.journalRow({ cmd: 'set_pars', args: { path: '/a', pars: { tx: 0.5 } }, ok: true, ms: 1 }));
  assert.match(set.args, /"tx":0.5/);
  assert.equal(J.callPath({ paths: ['/a', '/b'] }), '/a (+1)');
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'jtd-j-'));
  for (let i = 0; i < 30; i++) J.appendJournal(d, J.journalRow({ cmd: i % 3 ? 'list' : 'create', args: { parent: '/p' }, ok: i % 5 !== 0, ms: i, error: 'ValueError: no operator', now: new Date(Date.UTC(2026, 9, 26, 10, i)) }), 1000);
  assert.ok(fs.existsSync(path.join(d, 'calls.1.jsonl')), 'rotated'); assert.ok(fs.statSync(path.join(d, 'calls.jsonl')).size <= 1000);
  const all = J.readJournal(d, { limit: 500 });
  assert.ok(all.total > 5 && all.total < 30, 'oldest dropped');
  const f = J.readJournal(d, { failures: true });
  assert.ok(f.rows.every((r) => !r.ok));
  const s2 = J.readJournal(d, { summary: true, cmd: 'create' });
  assert.ok(Object.keys(s2.by_cmd).every((k) => k === 'create')); assert.equal(s2.slowest[0].ms >= s2.slowest[1].ms, true);
  assert.equal(J.readJournal(d, { since: '2026-10-26T10:28:00Z' }).total, 2);
  const py = fs.readFileSync(new URL('../td/handlers.py', import.meta.url), 'utf8');
  const m = /MUTATING = frozenset\(\(([\s\S]*?)\)\)/.exec(py);
  assert.deepEqual([...m[1].matchAll(/'(\w+)'/g)].map((x) => x[1]).sort(), [...J.MUTATING_CMDS].sort());
  fs.rmSync(d, { recursive: true, force: true });
});

test('health: analyze findings, paused/stalled, stale cook times, probe kinds, recheck verdicts', async () => {
  const H = await import('../src/health.js');
  const first = { frame: 1000, playing: true, rate: 60, counts: { '/p/a': 3, '/p/b': 7, '/p/lv': 2, '/p/mov': 0, '/p/fb': 9, '/p/old': 1 } };
  const second = {
    frame: 1060, playing: true, rate: 60, path: '/p', build: '2025.31550', realTime: true,
    nodes: [
      { path: '/p/a', type: 'noiseTOP', family: 'TOP', cooks: 3, cookTime: 0.2 },
      { path: '/p/b', type: 'levelTOP', family: 'TOP', cooks: 9, cookTime: 12, cookAbsFrame: 1059, bypass: true, negativeFloat: { format: 'rgba16float', settings: { contrast: 2 }, adds: ['/p/add1'] } },
      { path: '/p/old', type: 'moviefileinTOP', family: 'TOP', cooks: 1, cookTime: 44, cookAbsFrame: 353 },
      { path: '/p/mov', type: 'moviefileoutTOP', family: 'TOP', cooks: 0, cookTime: 0, active: false },
      { path: '/p/fb', type: 'feedbackTOP', family: 'TOP', cooks: 10, cookTime: 0.1, feedback: { target: '/p/b', reset: false }, history: true },
      { path: '/p/g', type: 'glslTOP', family: 'TOP', cooks: 4, cookTime: 0.1, compile: "ERROR: /p/g_pixel:2: 'x' : undeclared identifier", warnings: 'Warning: The GLSL Shader has compile errors' },
    ],
    scriptErrors: { '/p/cb': 'Error: Traceback (most recent call last):\n  File "x", line 1\nNameError: name \'q\' is not defined (/p/cb)' },
    clockReads: [['/p/a', 'tz', 'absTime.seconds']], clockReadsCount: 1, missingFiles: [['/p/old', 'file', 'clips/gone.mov']], nanChops: [['/p/c', 3, 10]],
    scan: { pars: [5, 9], scripts: [1, 1], nan: [1, 1] }, notes: [],
  };
  const r = H.analyze(first, second, { probe: { cooked: ['/p/a'], quiet: [], never: [], skipped: ['/p/mov'], unprobed: [] }, interval: 1 });
  const kinds = Object.fromEntries(r.findings.map((f) => [f.kind + ':' + f.sev, f]));
  for (const k of ['shader-compile:error', 'output-off:error', 'script-errors:error', 'not-pulled:warning', 'quiet-outputs:note', 'expensive:warning', 'expensive-stale:note', 'bypass-passes-through:warning', 'feedback-loops:note', 'negative-float:warning', 'history:note', 'nondeterministic:warning', 'missing-files:warning', 'nan-chops:warning', 'scan-budget:note', 'node-warnings:note']) assert.ok(kinds[k], `missing ${k}: ${Object.keys(kinds)}`);
  assert.equal(r.ok, false); assert.equal(r.fps.actual, 60); assert.equal(r.findings[0].sev, 'error');
  assert.match(kinds['expensive-stale:note'].paths[0], /\/p\/old .*707 frames ago/);
  assert.match(kinds['script-errors:error'].paths[0], /NameError: name 'q'/);
  assert.ok(!r.findings.some((f) => f.kind === 'bypassed'), 'gain op only under bypass-passes-through');
  const paused = H.analyze({ ...first, frame: 1060 }, { ...second, playing: false }, { interval: 1 });
  assert.ok(paused.findings.some((f) => f.kind === 'paused')); assert.ok(!paused.findings.some((f) => f.kind.startsWith('not-')));
  assert.match(paused.findings.find((f) => f.kind === 'expensive').msg, /clock frozen/);
  const stalled = H.analyze({ ...first, frame: 1058 }, second, { interval: 1 });
  assert.ok(stalled.findings.some((f) => f.kind === 'stalled'));
  const unprobed = H.analyze(first, second, { probe: null, interval: 1 });
  assert.ok(unprobed.findings.some((f) => f.kind === 'not-cooking'));
  const rc = H.analyze(first, second, { verdicts: { '/p/cb': { verdict: 'stale', cooks: 4 } }, interval: 1 });
  assert.ok(rc.findings.some((f) => f.kind === 'script-errors-stale') && !rc.findings.some((f) => f.kind === 'script-errors'));
  const clean = H.analyze({ frame: 0, playing: true, rate: 60, counts: { '/q/n': 1 } }, { frame: 60, playing: true, rate: 60, nodes: [{ path: '/q/n', type: 'noiseTOP', family: 'TOP', cooks: 61, cookTime: 0.1 }] }, { interval: 1 });
  assert.equal(clean.verdict, 'nothing wrong found'); assert.equal(clean.ok, true);
  // runHealth orchestration with a fake call: interval clamped, probe twice, recheck clear+read
  const calls = [];
  const fake = async (cmd, args) => { calls.push(cmd + (args.step ? ':' + args.step : '')); if (cmd === 'health_sample') return args.counts_only ? first : structuredClone(second); if (cmd === 'health_probe') return { cooked: [], quiet: args.paths, never: [], skipped: [], unprobed: [] }; if (args.step === 'clear') return { state: { '/p/cb': {} } }; return { verdicts: { '/p/cb': { verdict: 'live' } } }; };
  const waits = [];
  const rep = await H.runHealth(fake, { path: '/p', interval: 30, recheck: true }, async (ms) => waits.push(ms));
  assert.deepEqual(calls, ['health_sample', 'health_sample', 'health_probe', 'health_probe', 'script_errors_recheck:clear', 'script_errors_recheck:read']);
  assert.deepEqual(waits, [10000, 200, 200]);
  assert.ok(rep.findings.some((f) => f.kind === 'interval-clamped')); assert.equal(rep._dormant, undefined);
  assert.equal(H.scriptExcerpt('Error: Traceback (most recent call last):\n File "a"\nKeyError: 3 (/x)'), 'KeyError: 3 (/x)');
});

test('offline: payload/table/node/parm readers, records, tree, grep, diff, moves (synthetic expand)', async () => {
  const O = await import('../src/offline.js');
  const payload = (txt) => { const b = Buffer.from(txt); const h = Buffer.alloc(27); h.write('2\n*', 0); h.writeUInt32BE(b.length, 23); return Buffer.concat([h, b]); };
  assert.equal(O.readPayload(payload('a\nb')), 'a\nb'); assert.equal(O.readPayload(Buffer.from('nope')), null);
  const cells = ['x', 'y', '1', '2'];
  const tb = Buffer.concat([Buffer.from('1\n*'), Buffer.from([0, 0, 0, 1, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 0]), ...cells.map((c) => { const h = Buffer.alloc(8); h.writeUInt32BE(1, 0); h.writeUInt32BE(c.length, 4); return Buffer.concat([h, Buffer.from(c)]); })]);
  assert.deepEqual(O.readTable(tb), [['x', 'y'], ['1', '2']]);
  const n = O.readNode('TOP:level\ncomment "hi \\"there\\""\ntags 0 2 TDSubComp TDPub\ntile 475 -525 130 90\nflags =  picked on viewer 1 bypass on parlanguage 0\ninputs\n{\n0 \tnoise1\n2 \tramp1\n}\ncolor 0.5 0.35 0.05\nend\n');
  assert.deepEqual([n.family, n.type, n.inputs, n.tile, n.flags.bypass, n.comment, n.tags], ['TOP', 'level', [[0, 'noise1'], [2, 'ramp1']], [475, -525, 130, 90], 'on', 'hi "there"', ['TDSubComp', 'TDPub']]);
  const p = O.readParms('?\nopacity 0 0.5\ntitle 16 "PF26 Show Panel" me\nalignorder 16 0 "20000 - me.nodeY"\ncolorr 515 1 parent.Checker.par.Color1r\nfile 0 movies/a b.mov\nodd 2097152 1 1\n?\n');
  assert.deepEqual(O.parCode(p.opacity), '0.5'); assert.equal(O.parCode(p.title), '=me'); assert.equal(O.parCode(p.alignorder), '=20000 - me.nodeY');
  assert.equal(p.colorr.bind, 'parent.Checker.par.Color1r'); assert.equal(p.colorr.value, '1'); assert.equal(p.colorr.expr, undefined); assert.equal(O.parCode(p.colorr), '~parent.Checker.par.Color1r');
  assert.equal(p.file.value, 'movies/a b.mov'); assert.equal(p.odd.raw, '1');
  assert.deepEqual(O.readCustomParms('?\npages 2 "Jazib MCP" Look\n772804880 Handlersfile "Handlers File" 1 1\n?\n'), { pages: ['Jazib MCP', 'Look'], names: ['Handlersfile'] });
  // a fake expanded tree, twice (b = a with one par changed, one op added, one moved)
  const mk = (root, { tx = '0', extra = false, x = 200 } = {}) => {
    const w = (f, c) => { fs.mkdirSync(path.dirname(path.join(root, f)), { recursive: true }); fs.writeFileSync(path.join(root, f), c); };
    w('.build', 'version 099\nbuild 2025.31550\n');
    w('project1.n', 'COMP:container\ntile 0 0 100 100\nend\n');
    w('project1/noise1.n', `TOP:noise\ntile ${x} 0 130 90\nend\n`);
    w('project1/noise1.parm', `?\ntx 0 ${tx}\n?\n`);
    w('project1/level1.n', 'TOP:level\ntile 400 0 130 90\ninputs\n{\n0 \tnoise1\n}\nend\n');
    w('project1/script1.n', 'DAT:text\ntile 0 -200 130 90\nend\n');
    fs.writeFileSync(path.join(root, 'project1/script1.text'), payload('def onCook(scriptOp):\n    v = absTime.seconds\n'));
    if (extra) w('project1/blur1.n', 'TOP:blur\ntile 600 0 130 90\nend\n');
  };
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'jtd-off-'));
  mk(path.join(d, 'a')); mk(path.join(d, 'b'), { tx: '0.5', extra: true, x: 250 });
  const ra = O.readExpanded(path.join(d, 'a'), { root: '/project1' });
  assert.deepEqual(ra.map((r) => r.p), ['.', 'level1', 'noise1', 'script1']);
  assert.deepEqual(ra[1].in, [['noise1', 0]]); assert.equal(ra[2].pars.tx, '0'); assert.match(ra[3].text, /absTime/);
  assert.deepEqual(O.readExpanded(path.join(d, 'a'), { root: '/project1', depth: 0 }).map((r) => r.p), ['.']);
  assert.equal(O.readExpanded(path.join(d, 'a')).length, 4, 'no root = whole file');
  const tree = O.treeLines(ra);
  assert.match(tree.lines[1], /^level1 levelTOP <- noise1$/);
  const g = O.grepExpanded(path.join(d, 'a'), ra, 'abstime', { want: '/project1' });
  assert.deepEqual(g.hits, [{ p: 'script1', line: 2, text: 'v = absTime.seconds' }]);
  const rb = O.readExpanded(path.join(d, 'b'), { root: '/project1' });
  const { diffNet } = await import('../src/netdiff.js');
  const opt = { root: '/project1', depth: 99 };
  const dd = diffNet(O.netText(ra, { file: 'a.toe', build: O.readBuild(path.join(d, 'a')), ...opt }), O.netText(rb, { file: 'b.toe', build: {}, ...opt }));
  assert.deepEqual(dd.added, ['blur1']); assert.deepEqual(dd.changed, [{ p: 'noise1', pars: { tx: ['0', '0.5'] } }]);
  assert.deepEqual(O.moves(ra, rb), ['noise1']);
  assert.throws(() => O.resolveProjectFile('x.txt', d), /not a .toe/);
  fs.rmSync(d, { recursive: true, force: true });
});

test('offline: real toeexpand on a copy of td/JazibTDMCP.tox (skipped without TD installed)', { skip: !fs.existsSync('/Applications/TouchDesigner 2.app/Contents/MacOS/toeexpand') }, async () => {
  const O = await import('../src/offline.js');
  const tox = new URL('../td/JazibTDMCP.tox', import.meta.url).pathname;
  const before = fs.readFileSync(tox);
  const cache = fs.mkdtempSync(path.join(os.tmpdir(), 'jtd-tx-'));
  const r = O.offline({ file: tox }, { base: '/', cacheRoot: cache });
  assert.ok(r.ops >= 5); assert.ok(r.lines.some((l) => /^\/jazib_mcp\/ws websocketDAT/.test(l)), r.lines.join('\n'));
  const g = O.offline({ file: tox, query: 'def on_text' }, { base: '/', cacheRoot: cache });
  assert.ok(g.hits.some((h) => h.p === '/jazib_mcp/handlers'));
  assert.equal(O.offline({ file: tox }, { base: '/', cacheRoot: cache }).cache, r.cache, 'same content -> cached expand');
  const dd = O.offline({ file: tox, other: tox }, { base: '/', cacheRoot: cache });
  assert.equal(dd.same, true);
  assert.deepEqual(fs.readFileSync(tox), before, 'original untouched');
  assert.ok(!fs.existsSync(`${tox}.dir`) && !fs.existsSync(`${tox}.toc`), 'nothing written beside the original');
  fs.rmSync(cache, { recursive: true, force: true });
});
