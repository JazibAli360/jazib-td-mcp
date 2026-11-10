// Side TDs (26 Oct 2026), started by tools/scratch_td.py: the disposable scratch TD (T-83, port 9336) and the build
// TDs b2 / b3 (T-120, ports 9337 / 9338; they keep and autosave their own projects). Each /jazib_mcp dials its own
// bridge, so a side TD never touches the main session's bridge, exec.log or calls.jsonl (the watchdog reads those for
// the main TD: T-77, T-78); its calls are logged under logs/<name>/. td_* tools with target:'scratch'|'b2'|'b3' land
// here; td_bring_home copies a COMP built in b2/b3 into the main TD (everything ends in the main .toe).
import fs from 'node:fs';
import path from 'node:path';
import { bridgeHealth, call as bridgeCall, ensureBridge } from './bridge.js';
import { CONFIG } from './config.js';

export const SCRATCH_PORT = Number(process.env.JTD_SCRATCH_PORT || 9336);
export const SCRATCH_LOG_DIR = path.join(CONFIG.logDir, 'scratch');
export const SCRATCH_DOWN = `scratch TD not connected on 127.0.0.1:${SCRATCH_PORT}: start it with "python3 tools/scratch_td.py start" (status: "python3 tools/scratch_td.py status"); stop it with "stop" when done.`;
export const SIDES = {
  scratch: { port: SCRATCH_PORT, logDir: SCRATCH_LOG_DIR },
  b2: { port: Number(process.env.JTD_B2_PORT || 9337), logDir: path.join(CONFIG.logDir, 'b2') },
  b3: { port: Number(process.env.JTD_B3_PORT || 9338), logDir: path.join(CONFIG.logDir, 'b3') },
  b4: { port: Number(process.env.JTD_B4_PORT || 9339), logDir: path.join(CONFIG.logDir, 'b4') }, // user 26 Oct: "use more tds"
  b5: { port: Number(process.env.JTD_B5_PORT || 9340), logDir: path.join(CONFIG.logDir, 'b5') },
};
export const BUILDS = Object.keys(SIDES).filter((n) => n !== 'scratch');
export const TARGETS = ['main', ...Object.keys(SIDES)];
const downMsg = (name, port) => (name === 'scratch' ? SCRATCH_DOWN
  : `${name} TD not connected on 127.0.0.1:${port}: start it with "python3 tools/scratch_td.py start --name ${name}" (status / stop: same with --name ${name}).`);

// Pure: refuse a side port that is the main bridge's (a side call must never reach the main TD).
export function checkScratchPort(scratchPort = SCRATCH_PORT, mainPort = CONFIG.bridgePort, name = 'scratch') {
  if (!Number.isInteger(scratchPort) || scratchPort <= 0) throw new Error(`bad ${name} port ${scratchPort}`);
  if (scratchPort === mainPort) throw new Error(`${name} port ${scratchPort} is the main bridge port: set ${name === 'scratch' ? 'JTD_SCRATCH_PORT' : `JTD_${name.toUpperCase()}_PORT`} to another port`);
  return scratchPort;
}

// Pure: why the TD that answered on a target's port is not that target (null = it is). tdInfo comes from its hello:
// scratch (T-83) = not scratch:false and instance absent or 'scratch'; b2/b3 = instance equal to the name; main =
// not a side TD (no scratch:true, instance absent or 'main').
export function identityProblem(name, tdInfo) {
  const ti = tdInfo || {};
  if (name === 'main') return ti.scratch === true || (ti.instance && ti.instance !== 'main') ? `the TD on the main port says it is ${ti.instance || 'scratch'}; refusing` : null;
  if (name === 'scratch') {
    if (ti.instance && ti.instance !== 'scratch') return `says it is the ${ti.instance} TD, not the scratch TD; refusing`;
    return ti.scratch === false ? 'says it is not the scratch TD (tdInfo.scratch false); refusing' : null;
  }
  return ti.instance === name ? null : `says it is ${ti.instance ? `the ${ti.instance} TD` : 'not a build TD (no tdInfo.instance)'}, not ${name}; refusing`;
}

// One bridge call to a side TD. deps are for tests.
export async function sideCall(name, cmd, args = {}, timeoutMs = 60000, deps = {}) {
  if (!SIDES[name]) throw new Error(`unknown target ${name} (one of ${TARGETS.join(', ')})`);
  const { health = bridgeHealth, ensure = ensureBridge, call = bridgeCall, port = SIDES[name].port, mainPort = CONFIG.bridgePort } = deps;
  checkScratchPort(port, mainPort, name);
  await ensure(port);
  const h = await health(port);
  if (!h?.td) throw new Error(downMsg(name, port));
  const why = identityProblem(name, h.tdInfo);
  if (why) throw new Error(`the TD on port ${port} ${why}`);
  return call(cmd, args, timeoutMs, port);
}
export const scratchCall = (cmd, args, timeoutMs, deps) => sideCall('scratch', cmd, args, timeoutMs, deps);

// ------------------------------------------------------------------ td_bring_home (T-120)
const NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
const PATH_RE = /^\/[A-Za-z0-9_/]*$/;
const py = (s) => JSON.stringify(String(s)); // ASCII-only inputs (checked): a JSON string is a Python literal

// Pure: the Python run in the build TD: save the COMP as .tox (td/safety.py save_tox: temp name + os.replace,
// externaltox put back), count its ops.
export function exportCode(comp, file) {
  return [
    'H = op("/jazib_mcp/handlers").module',
    `c = op(${py(comp)})`,
    `if c is None or not c.isCOMP: raise ValueError(${py(comp + ' is not a COMP in this TD')})`,
    'import os',
    `os.makedirs(os.path.dirname(${py(file)}), exist_ok=True)`,
    `notes = H._safety().save_tox(c, ${py(file)})`,
    `{"file": ${py(file)}, "bytes": os.path.getsize(${py(file)}), "ops": len(c.findChildren()), "type": c.OPType, "notes": notes}`,
  ].join('\n');
}

// Pure: the Python run in the main TD: checkpoint + safe_destroy (T-70) a COMP of that name, loadTox the new one
// (cooking on for the check), keep the old one's xy / colour / comment / wires, else arrange the parent.
export function loadCode(parent, name, file, from) {
  return [
    'H = op("/jazib_mcp/handlers").module',
    'S = H._safety()',
    `par_ = op(${py(parent)})`,
    `if par_ is None or not par_.isCOMP: raise ValueError(${py(parent + ' is not a COMP in the main TD')})`,
    `old = par_.op(${py(name)})`,
    'r = {"replaced": None, "checkpoint": None, "released": None, "notes": []}',
    'state = None',
    'if old is not None:',
    `    if not old.isCOMP: raise ValueError(${py(parent + '/' + name + ' exists and is not a COMP')})`,
    `    r["checkpoint"] = S.write_checkpoint(old, None, S.CKPT_KEEP, ${py(`before td_bring_home from ${from}`)})["file"]`,
    '    state = S.comp_state(old)',
    '    r["replaced"] = old.path',
    `new = par_.loadTox(${py(file)})`,
    'new.allowCooking = False',
    `new.name = ${py(name + '_incoming')} + str(int(new.id))`,
    'if old is not None:',
    '    r["released"] = H.safe_destroy(old)',
    `new.name = ${py(name)}`,
    'if state:',
    '    new.nodeX, new.nodeY = int(state["xy"][0]), int(state["xy"][1])',
    '    if state.get("color"): new.color = tuple(state["color"])',
    '    if state.get("comment"): new.comment = state["comment"]',
    '    S._rewire(new, state.get("inputs"), state.get("outputs"), r["notes"])',
    'else:',
    '    r["layout"] = H._arrange(par_, True)',
    'new.allowCooking = True',
    'r.update(path=new.path, ops=len(new.findChildren()))',
    'r',
  ].join('\n');
}

// Pure: after >= 3 frames: re-apply the stage plan, park (allowCooking off) unless park is false.
export function finishCode(p, park) {
  return [
    'H = op("/jazib_mcp/handlers").module',
    `c = op(${py(p)})`,
    `if c is None: raise ValueError(${py(p + ' is gone')})`,
    'r = {"ops": len(c.findChildren()), "staged": bool(H._stage_plan(c))}',
    'if r["staged"]: r["layout"] = H.restage(c)',
    ...(park ? ['c.allowCooking = False'] : []),
    'r["allowCooking"] = bool(c.allowCooking)',
    'r',
  ].join('\n');
}

// Pure: is this COMP (main-TD path) registered by a live lane (logs/active_lanes.json, T-95)?
export function laneOwner(lanes, p) {
  const v = lanes && typeof lanes === 'object' ? lanes[p] : null;
  return v ? (v.agent || 'a lane') : null;
}

// td_bring_home: export COMP from a build TD, load it into the main TD, check, park, save both projects.
// deps: sideExec(code, frames), side(cmd, args, t), mainExec(code, frames), main(cmd, args, t), lanes(), outDir.
export async function bringHome(a, deps) {
  const from = a.from;
  if (!BUILDS.includes(from)) throw new Error(`from must be one of ${BUILDS.join(', ')}, not ${from}`);
  const comp = String(a.comp || '').replace(/\/+$/, '');
  if (!PATH_RE.test(comp) || !comp.includes('/', 1)) throw new Error(`comp must be an absolute ASCII path in the ${from} TD, e.g. /project1/lab/MyComp: ${a.comp}`);
  const name = comp.split('/').pop();
  if (!NAME_RE.test(name)) throw new Error(`bad COMP name ${name}`);
  const parent = String(a.parent || '/project1/lab').replace(/\/+$/, '');
  if (!PATH_RE.test(parent)) throw new Error(`parent must be an absolute ASCII path: ${a.parent}`);
  const dest = `${parent}/${name}`;
  if (dest.startsWith('/jazib_mcp')) throw new Error('refusing /jazib_mcp');
  const owner = laneOwner(deps.lanes(), dest);
  // a lane bringing home its OWN COMP names its registration label (T-138: owners were refused and --force is a bypass)
  if (owner && !a.force && a.lane !== owner) throw new Error(`${dest} is registered by ${owner} (logs/active_lanes.json): not replacing another lane's COMP (your own: pass lane:"${owner}")`);
  const file = path.join(path.resolve(deps.outDir), 'transfer', `${name}.tox`);
  if (/[^\x20-\x7e]/.test(file)) throw new Error(`transfer path must be ASCII: ${file}`);
  const res = (r) => (r && typeof r === 'object' && 'result' in r ? r.result : r);

  const exported = res(await deps.sideExec(exportCode(comp, file), 0));
  if (!exported || exported.file !== file) throw new Error(`export from ${from} failed: ${JSON.stringify(exported).slice(0, 300)}`);
  const sideSaved = await deps.side('save_project', {}, 60000).catch((e) => ({ error: e.message }));
  const loaded = res(await deps.mainExec(loadCode(parent, name, file, from), 0));
  if (!loaded || loaded.path !== dest) throw new Error(`load into the main TD failed: ${JSON.stringify(loaded).slice(0, 300)}`);
  const errs = await deps.main('errors', { path: dest, frames: 3 }, 60000);
  const fin = res(await deps.mainExec(finishCode(dest, a.park !== false), 1));
  const mainSaved = await deps.main('save_project', {}, 60000);
  const items = (errs && errs.items) || [];
  return {
    from, exported: { comp, file, bytes: exported.bytes, ops: exported.ops },
    main: { path: dest, replaced: loaded.replaced, checkpoint: loaded.checkpoint, released: loaded.released, ops: loaded.ops, layout: fin.layout || loaded.layout, staged: fin.staged, allowCooking: fin.allowCooking, ...(loaded.notes?.length ? { notes: loaded.notes } : {}) },
    check: { ops_equal: loaded.ops === exported.ops, ops_side: exported.ops, ops_main: loaded.ops, errors: items.filter((x) => x.errors).slice(0, 20), warnings: items.filter((x) => !x.errors && x.warnings).length },
    saved: { side: sideSaved, main: mainSaved },
  };
}

export function readLanes(logDir = CONFIG.logDir) {
  try { return JSON.parse(fs.readFileSync(path.join(logDir, 'active_lanes.json'), 'utf8')); } catch { return {}; }
}
