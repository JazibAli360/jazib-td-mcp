// The local bridge: one detached process on 127.0.0.1 that TouchDesigner dials out to (WebSocket, any path) and every
// Claude session's MCP server talks to (HTTP POST /ctl). Both sides present the secret token in
// ~/Library/Application Support/JazibTDMCP/token (TD in its hello, HTTP in x-jtd-token). Contract: docs/PROTOCOL.md.
import crypto from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { WebSocketServer } from 'ws';
import { CONFIG, ROOT } from './config.js';

export const TOKEN_FILE = path.join(CONFIG.stateDir, 'token');
// One log per port: the scratch TD's bridge (T-83, default 9336) keeps out of the main bridge.log.
export const logFor = (port) => path.join(CONFIG.stateDir, Number(port) === 9335 ? 'bridge.log' : `bridge.${port}.log`);
export const LOG = logFor(CONFIG.bridgePort);
const NOT_CONNECTED = 'TouchDesigner not connected: open TD and load /jazib_mcp (see README)';
// Web pages (and local HTML files) carry one of these origins; TD's WebSocket DAT sends none or its own.
const BAD_ORIGIN = /^(https?|file):/i;

export function token() {
  // TD may have created it first; 'wx' keeps a race from overwriting the other side's token.
  try { fs.writeFileSync(TOKEN_FILE, crypto.randomBytes(24).toString('hex'), { mode: 0o600, flag: 'wx' }); } catch (e) { if (e.code !== 'EEXIST') throw e; }
  return fs.readFileSync(TOKEN_FILE, 'utf8').trim();
}

function log(...a) { try { fs.appendFileSync(LOG, `${new Date().toISOString()} ${a.join(' ')}\n`); } catch {} }

// Resolves { port, close } once listening. port 0 = any free port (tests). helloMs / pingMs are for tests too.
export function runBridge({ port = CONFIG.bridgePort, token: TOKEN = token(), helloMs = 5000, pingMs = 20000 } = {}) {
  let td = null;
  let tdInfo = null;
  let seq = 0;
  const pending = new Map();

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    const send = (code, obj) => { res.writeHead(code, { 'content-type': 'application/json' }); res.end(JSON.stringify(obj)); };
    const origin = req.headers.origin;
    if (origin && BAD_ORIGIN.test(origin)) { log('refused http origin', origin); return send(403, { ok: false, error: 'origin' }); }
    if (req.headers['x-jtd-token'] !== TOKEN) return send(403, { ok: false, error: 'token' });
    if (url.pathname === '/health') return send(200, { ok: true, td: !!td, tdInfo, pid: process.pid });
    if (url.pathname === '/ctl' && req.method === 'POST') {
      let body = '';
      for await (const c of req) body += c;
      let cmd, args, timeoutMs;
      try { ({ cmd, args = {}, timeoutMs = 60000 } = JSON.parse(body)); } catch { return send(400, { ok: false, error: 'bad JSON body' }); }
      if (!cmd) return send(400, { ok: false, error: 'cmd missing' });
      if (!td) return send(503, { ok: false, error: NOT_CONNECTED });
      const id = ++seq;
      const m = await new Promise((resolve) => {
        const timer = setTimeout(() => { pending.delete(id); resolve({ ok: false, error: `TouchDesigner timeout after ${timeoutMs} ms on ${cmd}`, timeout: true }); }, timeoutMs);
        pending.set(id, (r) => { clearTimeout(timer); resolve(r); });
        td.send(JSON.stringify({ id, cmd, args }));
      });
      if (m.ok) return send(200, { ok: true, result: m.result });
      const out = { ok: false, error: m.error || 'unknown TouchDesigner error' };
      if (m.traceback) out.traceback = m.traceback;
      return send(m.timeout ? 504 : 200, out);
    }
    send(404, { ok: false, error: 'not found' });
  });

  const wss = new WebSocketServer({ noServer: true });
  server.on('upgrade', (req, sock, head) => {
    const origin = req.headers.origin;
    if (origin && BAD_ORIGIN.test(origin)) { log('refused upgrade origin', origin); sock.destroy(); return; }
    wss.handleUpgrade(req, sock, head, (w) => {
      let authed = false;
      const kill = setTimeout(() => { if (!authed) { log('no hello within', helloMs, 'ms'); w.close(); } }, helloMs);
      w.on('message', (data) => {
        let m;
        try { m = JSON.parse(String(data)); } catch { if (!authed) w.close(); return; }
        if (!authed) {
          if (m.type === 'hello' && m.token === TOKEN) {
            authed = true; clearTimeout(kill);
            if (td && td !== w) { log('newer TD hello replaces the old connection'); td.close(); }
            td = w; tdInfo = { ...(m.td || {}), since: new Date().toISOString() };
            log('TD connected', `origin=${origin || '(none)'}`, `path=${req.url}`, JSON.stringify(m.td || {}));
          } else { log('bad hello, closed'); w.close(); }
          return;
        }
        if (m.type === 'pong') return;
        if (m.type === 'log') { log(`TD ${m.level || 'info'}:`, m.msg); return; }
        const cb = pending.get(m.id);
        if (cb) { pending.delete(m.id); cb(m); }
      });
      w.on('error', (e) => log('TD socket error', e.message));
      w.on('close', () => {
        clearTimeout(kill);
        if (td !== w) return;
        td = null; tdInfo = null; log('TD disconnected');
        for (const [id, cb] of pending) { pending.delete(id); cb({ ok: false, error: 'TouchDesigner disconnected before replying' }); }
      });
    });
  });
  const ping = setInterval(() => { if (td) td.send(JSON.stringify({ type: 'ping' })); }, pingMs);

  return new Promise((resolve, reject) => {
    server.on('error', (e) => { log('bridge error', e.message); clearInterval(ping); reject(e); });
    server.listen(port, '127.0.0.1', () => {
      const p = server.address().port;
      log('bridge listening', p, 'pid', process.pid);
      resolve({
        port: p,
        close: () => new Promise((r) => { clearInterval(ping); for (const c of wss.clients) c.terminate(); server.closeAllConnections?.(); server.close(() => r()); }),
      });
    });
  });
}

// ---------- client side (used by the MCP server and the CLI) ----------
// port: another bridge (the scratch TD's, T-83); default the configured one.
export async function bridgeHealth(port = CONFIG.bridgePort) {
  try {
    const r = await fetch(`http://127.0.0.1:${port}/health`, { headers: { 'x-jtd-token': token() }, signal: AbortSignal.timeout(1500) });
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

export async function ensureBridge(port = CONFIG.bridgePort) {
  if (await bridgeHealth(port)) return;
  const out = fs.openSync(logFor(port), 'a');
  spawn(process.execPath, [path.join(ROOT, 'src', 'bridge.js'), 'serve'], { detached: true, stdio: ['ignore', out, out], env: { ...process.env, JTD_BRIDGE_PORT: String(port) } }).unref();
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 250));
    if (await bridgeHealth(port)) return;
  }
  throw new Error(`bridge did not start on 127.0.0.1:${port} (see ${logFor(port)})`);
}

// Throws Error(message [+ "\n" + traceback]); the traceback is also on err.traceback.
export async function call(cmd, args = {}, timeoutMs = 60000, port = CONFIG.bridgePort) {
  const r = await fetch(`http://127.0.0.1:${port}/ctl`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-jtd-token': token() },
    body: JSON.stringify({ cmd, args, timeoutMs }),
    signal: AbortSignal.timeout(timeoutMs + 5000),
  });
  const m = await r.json().catch(() => null);
  if (m && m.ok) return m.result;
  const e = new Error(((m && m.error) || `bridge returned HTTP ${r.status}`) + (m && m.traceback ? `\n${m.traceback}` : ''));
  if (m && m.traceback) e.traceback = m.traceback;
  e.status = r.status;
  throw e;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  if (process.argv[2] === 'serve') runBridge().catch(() => process.exit(1));
}
