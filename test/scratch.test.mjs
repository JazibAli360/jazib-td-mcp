// Offline tests for the scratch TD route (T-83): td_exec target:'scratch' reaches only the scratch bridge and logs to
// logs/scratch/, never the main exec.log. No TouchDesigner: fake TDs on two private bridges.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import test, { after } from 'node:test';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import WebSocket from 'ws';

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'jtd-scratch-test-'));
const freePort = () => new Promise((r) => { const s = net.createServer().listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => r(p)); }); });
const MAIN = await freePort();
const SCR = await freePort();
const B2 = await freePort();
process.env.JTD_STATE_DIR = path.join(dir, 'state');
process.env.JTD_BRIDGE_PORT = String(MAIN);
process.env.JTD_SCRATCH_PORT = String(SCR); // never the real 9336
process.env.JTD_B2_PORT = String(B2); // never the real 9337
process.env.JTD_LOG_DIR = path.join(dir, 'logs');
process.env.JTD_OUTPUT_DIR = path.join(dir, 'output');
const B = await import('../src/bridge.js');
const S = await import('../src/scratch.js');
const TOKEN = B.token();
const mainBridge = await B.runBridge({ port: MAIN });
const scrBridge = await B.runBridge({ port: SCR });
const b2Bridge = await B.runBridge({ port: B2 });
const socks = new Set();
after(async () => { for (const s of socks) s.terminate(); await mainBridge.close(); await scrBridge.close(); await b2Bridge.close(); fs.rmSync(dir, { recursive: true, force: true }); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function fakeTD(port, name, scratch, instance) {
  const w = new WebSocket(`ws://127.0.0.1:${port}/`);
  socks.add(w);
  w.on('error', () => {});
  w.on('message', (data) => {
    const m = JSON.parse(String(data));
    if (m.type === 'ping') return;
    w.send(JSON.stringify({ id: m.id, ok: true, result: { from: name, cmd: m.cmd, code: m.args.code, frames: m.args.frames } }));
  });
  w.opened = new Promise((r) => w.on('open', () => { w.send(JSON.stringify({ type: 'hello', token: TOKEN, td: { pid: 1, scratch, ...(instance ? { instance } : {}) } })); r(); }));
  return w;
}
async function waitTD(port) {
  for (let i = 0; i < 50; i++) {
    const h = await B.bridgeHealth(port);
    if (h?.td) return;
    await sleep(40);
  }
  throw new Error('no td on ' + port);
}

test('checkScratchPort refuses the main port and bad ports', () => {
  assert.equal(S.checkScratchPort(9336, 9335), 9336);
  assert.throws(() => S.checkScratchPort(9335, 9335), /main bridge port/);
  assert.throws(() => S.checkScratchPort(0, 9335), /bad scratch port/);
  assert.equal(S.SCRATCH_PORT, SCR);
  assert.equal(S.SCRATCH_LOG_DIR, path.join(dir, 'logs', 'scratch'));
});

test('scratchCall: not connected -> how to start; a TD that says scratch:false is refused', async () => {
  const deps = { ensure: async () => {}, port: 7001, mainPort: 7000 };
  await assert.rejects(S.scratchCall('exec', {}, 1000, { ...deps, health: async () => ({ td: false }) }), /scratch_td\.py start/);
  await assert.rejects(S.scratchCall('exec', {}, 1000, { ...deps, health: async () => ({ td: true, tdInfo: { scratch: false } }) }), /not the scratch TD/);
  const got = await S.scratchCall('exec', { code: '1' }, 1000, { ...deps, health: async () => ({ td: true, tdInfo: { scratch: true } }), call: async (c, a, t, p) => ({ c, a, t, p }) });
  assert.deepEqual(got, { c: 'exec', a: { code: '1' }, t: 1000, p: 7001 });
});

test('td_exec target scratch goes to the scratch bridge only, logged under logs/scratch/', async () => {
  const m = fakeTD(MAIN, 'main', false);
  const s = fakeTD(SCR, 'scratch', true);
  await m.opened; await s.opened; await waitTD(MAIN); await waitTD(SCR);
  const client = new Client({ name: 'jtd-scratch', version: '0' });
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [new URL('../src/server.js', import.meta.url).pathname], env: { ...process.env }, stderr: 'ignore' }));
  try {
    const r1 = JSON.parse((await client.callTool({ name: 'td_exec', arguments: { code: 'probe()', frames: 3, target: 'scratch' } })).content[0].text);
    assert.deepEqual(r1, { from: 'scratch', cmd: 'exec', code: 'probe()', frames: 3 });
    const r2 = JSON.parse((await client.callTool({ name: 'td_exec', arguments: { code: '1+1' } })).content[0].text);
    assert.equal(r2.from, 'main');
    const rows = (f) => fs.readFileSync(f, 'utf8').trim().split('\n').map(JSON.parse);
    const scr = rows(path.join(dir, 'logs', 'scratch', 'exec.log'));
    assert.deepEqual(scr.map((r) => [r.phase, r.code]), [['start', 'probe()'], ['end', 'probe()']]);
    assert.equal(scr[0].target, 'scratch');
    const main = rows(path.join(dir, 'logs', 'exec.log'));
    assert.ok(main.every((r) => r.code === '1+1'), 'main exec.log never sees scratch code (watchdog T-77/T-78 signals)');
    assert.ok(fs.existsSync(path.join(dir, 'logs', 'scratch', 'calls.jsonl')));
    s.terminate(); await sleep(100);
    const down = await client.callTool({ name: 'td_exec', arguments: { code: '1', target: 'scratch' } });
    assert.ok(down.isError); assert.match(down.content[0].text, /scratch_td\.py start/);
  } finally { await client.close(); }
});

test('bridge log is per port (scratch keeps out of bridge.log)', () => {
  assert.match(B.logFor(9335), /bridge\.log$/);
  assert.match(B.logFor(9336), /bridge\.9336\.log$/);
});

test('identityProblem: each target accepts only its own TD (T-120)', () => {
  assert.equal(S.identityProblem('b2', { instance: 'b2', scratch: false }), null);
  assert.match(S.identityProblem('b2', { instance: 'b3' }), /b3 TD, not b2/);
  assert.match(S.identityProblem('b2', { scratch: false }), /no tdInfo.instance/);
  assert.equal(S.identityProblem('scratch', { scratch: true }), null);
  assert.match(S.identityProblem('scratch', { instance: 'b2', scratch: false }), /b2 TD/);
  assert.equal(S.identityProblem('main', { scratch: false }), null);
  assert.match(S.identityProblem('main', { instance: 'b2' }), /refusing/);
  assert.deepEqual(S.TARGETS, ['main', 'scratch', 'b2', 'b3', 'b4', 'b5']);
});

test('td_exec target b2 reaches only the b2 bridge; a TD claiming another identity is refused', async () => {
  const m = fakeTD(MAIN, 'main', false);
  const b = fakeTD(B2, 'b2', false, 'b2');
  await m.opened; await b.opened; await waitTD(MAIN); await waitTD(B2);
  const client = new Client({ name: 'jtd-b2', version: '0' });
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [new URL('../src/server.js', import.meta.url).pathname], env: { ...process.env }, stderr: 'ignore' }));
  try {
    const r = JSON.parse((await client.callTool({ name: 'td_exec', arguments: { code: 'b()', target: 'b2' } })).content[0].text);
    assert.equal(r.from, 'b2');
    const e = JSON.parse((await client.callTool({ name: 'td_errors', arguments: { path: '/project1', target: 'b2' } })).content[0].text);
    assert.deepEqual([e.from, e.cmd], ['b2', 'errors']);
    const rows = fs.readFileSync(path.join(dir, 'logs', 'b2', 'exec.log'), 'utf8').trim().split('\n').map(JSON.parse);
    assert.ok(rows.every((x) => x.code === 'b()') && rows[0].target === 'b2');
    b.terminate(); await sleep(100);
    const imp = fakeTD(B2, 'imposter', false, 'b3');
    await imp.opened; await waitTD(B2);
    const bad = await client.callTool({ name: 'td_exec', arguments: { code: '1', target: 'b2' } });
    assert.ok(bad.isError); assert.match(bad.content[0].text, /b3 TD, not b2/);
    imp.terminate();
  } finally { await client.close(); m.terminate(); }
});

test('bringHome: export in b2, load + check + park + save in main; refuses lane COMPs', async () => {
  const seen = [];
  const deps = {
    outDir: '/o', lanes: () => ({ '/project1/lab/Taken': { agent: 'fx lane' } }),
    sideExec: async (code) => { seen.push(['sideExec', code]); return { result: { file: '/o/transfer/ZZ_t.tox', bytes: 10, ops: 2 } }; },
    side: async (cmd) => { seen.push(['side', cmd]); return { saved: 'Build2.1.toe' }; },
    mainExec: async (code, frames) => { seen.push(['mainExec', frames]); return { result: code.includes('loadTox') ? { path: '/project1/lab/ZZ_t', ops: 2, replaced: null, notes: [] } : { ops: 2, staged: false, allowCooking: false } }; },
    main: async (cmd, args) => { seen.push(['main', cmd, args.frames]); return cmd === 'errors' ? { items: [] } : { saved: 'JazibTD_home.200.toe' }; },
  };
  const r = await S.bringHome({ comp: '/project1/lab/ZZ_t', from: 'b2' }, deps);
  assert.equal(r.main.path, '/project1/lab/ZZ_t');
  assert.deepEqual(r.check, { ops_equal: true, ops_side: 2, ops_main: 2, errors: [], warnings: 0 });
  assert.equal(r.main.allowCooking, false);
  assert.deepEqual(seen.map((x) => x.slice(0, 2)), [['sideExec', seen[0][1]], ['side', 'save_project'], ['mainExec', 0], ['main', 'errors'], ['mainExec', 1], ['main', 'save_project']]);
  assert.match(seen[0][1], /save_tox\(c, "\/o\/transfer\/ZZ_t\.tox"\)/);
  await assert.rejects(S.bringHome({ comp: '/project1/lab/Taken', from: 'b2' }, deps), /fx lane/);
  await assert.rejects(S.bringHome({ comp: '/project1/lab/Taken', from: 'b2', lane: 'other lane' }, deps), /fx lane/);
  const own = await S.bringHome({ comp: '/project1/lab/Taken', from: 'b2', lane: 'fx lane' }, deps).catch((e) => e);
  assert.ok(!(own instanceof Error && /registered by/.test(own.message)), 'own lane label passes the owner check');
  await assert.rejects(S.bringHome({ comp: '/project1/lab/X', from: 'main' }, deps), /one of b2, b3, b4, b5/);
  await assert.rejects(S.bringHome({ comp: 'X', from: 'b3' }, deps), /absolute/);
});

test('bringHome Python compiles (export, load, finish)', async () => {
  const { execFileSync } = await import('node:child_process');
  for (const code of [S.exportCode('/project1/lab/A', '/o/transfer/A.tox'), S.loadCode('/project1/lab', 'A', '/o/transfer/A.tox', 'b2'), S.finishCode('/project1/lab/A', true)]) {
    execFileSync('python3', ['-I', '-c', 'import sys; compile(sys.stdin.read(), "x", "exec")'], { input: code });
  }
});
