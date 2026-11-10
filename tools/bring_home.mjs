#!/usr/bin/env node
// td_bring_home from the command line (26 Oct 2026, user: "use more tds"): the same bringHome() as the MCP tool, for
// build TDs a running MCP server does not know yet (b4 / b5 until /mcp restarts it) and for lanes without MCP access.
//   node tools/bring_home.mjs --comp /project1/lab/MyComp --from b4 [--parent /project1/lab] [--no-park] [--lane "<label>"]
// --lane: the label your lane registered with tools/lane.py, to bring home your own registered COMP (T-138).
// Execs are logged like td_exec (main: logs/exec.log, side: logs/<from>/exec.log).
import fs from 'node:fs';
import path from 'node:path';
import { bridgeHealth, call as bridgeCall } from '../src/bridge.js';
import { CONFIG } from '../src/config.js';
import { BUILDS, bringHome, identityProblem, readLanes, SIDES, sideCall } from '../src/scratch.js';

const argv = process.argv.slice(2);
const opt = (k) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : undefined; };
const a = { comp: opt('--comp'), from: opt('--from'), parent: opt('--parent'), park: !argv.includes('--no-park'), force: argv.includes('--force'), lane: opt('--lane') };
if (!a.comp || !BUILDS.includes(a.from)) {
  console.error(`usage: node tools/bring_home.mjs --comp /project1/lab/X --from ${BUILDS.join('|')} [--parent P] [--no-park] [--lane "<your lane label>"]`);
  process.exit(2);
}

function execLog(row, dir) {
  fs.mkdirSync(dir, { recursive: true });
  fs.appendFileSync(path.join(dir, 'exec.log'), JSON.stringify({ time: new Date().toISOString(), pid: process.pid, client: 'bring_home.mjs', ...row }) + '\n');
}
const execVia = (viaCall, dir, target) => async (code, frames) => {
  execLog({ phase: 'start', code, ...(target !== 'main' ? { target } : {}) }, dir);
  try {
    const r = await viaCall('exec', { code, frames: frames || 0 }, 240000); // T-126
    execLog({ phase: 'end', code, ok: true }, dir);
    return r;
  } catch (e) { execLog({ phase: 'end', code, ok: false, error: String(e.message).slice(0, 300) }, dir); throw e; }
};

const h = await bridgeHealth();
if (!h?.td) { console.error('main TD not connected'); process.exit(2); }
const why = identityProblem('main', h.tdInfo);
if (why) { console.error(why); process.exit(2); }
const side = (c, x, t) => sideCall(a.from, c, x, t);
const main = (c, x, t) => bridgeCall(c, x, t);
try {
  const r = await bringHome(a, {
    sideExec: execVia(side, SIDES[a.from].logDir, a.from), side,
    mainExec: execVia(main, CONFIG.logDir, 'main'), main,
    lanes: () => readLanes(CONFIG.logDir), outDir: CONFIG.outputDir,
  });
  console.log(JSON.stringify(r, null, 1));
} catch (e) { console.error(String(e.message || e)); process.exit(1); }
