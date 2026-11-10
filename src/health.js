// td_health: what TouchDesigner stays quiet about. Two health_sample calls an interval apart (td/handlers.py), a cook
// probe for ops that did not cook, optional script-error recheck, then the verdict here (pure analyze(), tested
// offline). Rules and wording adapted from td-atlas by grigabyte (https://github.com/grigabyte/td-atlas, commit
// 7cf8f57, src/td_atlas/bridge/health.py, docs/health.md; their measurements on 2025.32460). Own additions:
// missing-files, nan-chops.

export const SLOW_COOK_MS = 8;
export const MAX_INTERVAL = 10;
export const PROBE_GAP_MS = 200;
const SHOW = 8;
const GAIN_TYPES = new Set(['levelTOP', 'mathTOP', 'hsvadjustTOP', 'mathCHOP', 'mathPOP']);
const OUTPUT_TYPES = {
  audiodeviceoutCHOP: 'audio output', moviefileoutTOP: 'movie recording', midioutCHOP: 'MIDI output', oscoutCHOP: 'OSC output',
  dmxoutCHOP: 'DMX output', serialDAT: 'serial output', touchoutTOP: 'Touch Out', ndioutTOP: 'NDI output',
  videodeviceoutTOP: 'video output', syphonspoutoutTOP: 'Syphon/Spout output',
};
const SEV = { error: 0, warning: 1, note: 2 };

const firstLine = (s) => String(s || '').split('\n').map((l) => l.trim()).find(Boolean) || '';
const clipLine = (s, n = 110) => (s.length > n ? `${s.slice(0, n)}...` : s);
// The exception line of a kept traceback (skip "Traceback" and File lines).
export function scriptExcerpt(text) {
  const lines = String(text || '').split('\n').map((l) => l.trim()).filter(Boolean);
  for (const l of lines) {
    if (l.includes('Traceback') || l.startsWith('File ')) continue;
    if (/(Error|Exception|Interrupt|Exit)$/.test(l.split(':', 1)[0].trim())) return clipLine(l);
  }
  return clipLine(lines[0] || '');
}

function finding(sev, kind, message, paths = []) {
  const f = { sev, kind, msg: message };
  if (paths.length) { f.count = paths.length; f.paths = paths.slice(0, SHOW); if (paths.length > SHOW) f.more = paths.length - SHOW; }
  return f;
}

// first: counts_only sample; second: full sample; probe: second health_probe answer (or null = could not run, or
// undefined = not needed); verdicts: script_errors_recheck read (or null/undefined); opts {interval, asked, path}.
export function analyze(first, second, { probe, verdicts, interval = 1, asked, path = second?.path } = {}) {
  const F = [];
  const frames = (second.frame ?? 0) - (first.frame ?? 0);
  const elapsed = Math.max(interval, 1e-6);
  const paused = second.playing === false;
  const stalled = frames < 5 || paused;
  const fpsTarget = second.rate || 0;
  const fps = Math.round((frames / elapsed) * 10) / 10;
  const before = first.counts || {};
  const nodes = second.nodes || [];
  let cooking = 0;
  const dormant = []; const slow = []; const stale = []; const loops = []; const through = []; const bypassed = [];
  const negAdd = []; const negOnly = []; const errored = []; const warned = []; const inactive = []; const shaders = [];
  const history = []; const clamped = [];
  if (asked !== undefined && asked !== interval) F.push(finding('note', 'interval-clamped', `interval ${asked}s changed to ${interval}s (0..${MAX_INTERVAL})`));
  if (second.truncated) F.push(finding('warning', 'walk-truncated', `only ${second.scanned} ops under ${path} sampled (limit ${second.limit}); at least ${second.notScanned} more not looked at. Run on a sub-COMP for the rest`));
  for (const n of nodes) {
    if (n.compile) shaders.push(`${n.path} (${n.compile})`);
    if (n.history) history.push(`${n.path} (${n.type})`);
    if (n.family === 'COMP') continue;
    const prev = before[n.path];
    const delta = typeof prev === 'number' && typeof n.cooks === 'number' ? n.cooks - prev : null;
    if (stalled || delta === null || delta > 0) cooking++; else dormant.push(n.path);
    if ((n.cookTime || 0) >= SLOW_COOK_MS) {
      const cost = `${n.path} (${Math.round(n.cookTime)} ms`;
      const last = n.cookAbsFrame;
      if (typeof last !== 'number') slow.push(`${cost})`);
      else if (frames <= 0 || paused) slow.push(`${cost}, last cooked at abs frame ${Math.round(last)})`);
      else if (last >= (first.frame ?? 0) - 1) slow.push(`${cost}, cooked during this check)`);
      else stale.push(`${cost}, last cooked ${Math.round(second.frame - last)} frames ago)`);
    }
    if (n.feedback && !n.feedback.reset) loops.push(`${n.path} (target ${n.feedback.target || 'none'})`);
    if (n.bypass && GAIN_TYPES.has(n.type)) through.push(`${n.path} (${n.type})`); else if (n.bypass) bypassed.push(n.path);
    if (n.negativeFloat) {
      const r = n.negativeFloat;
      const head = `${n.path} (${[r.format, ...Object.entries(r.settings || {}).map(([k, v]) => `${k} ${v}`)].join(', ')}`;
      if (r.adds?.length) negAdd.push(`${head}, added in ${r.adds.join(', ')})`); else negOnly.push(`${head})`);
    }
    if (n.errors) errored.push(n.path);
    if (n.warnings) {
      warned.push(`${n.path} (${clipLine(firstLine(n.warnings).replace(/^Warning: /, ''))})`);
      if (/resolution limited/i.test(n.warnings)) clamped.push(n.path);
    }
    if (OUTPUT_TYPES[n.type] && n.active === false) inactive.push(`${n.path} (${OUTPUT_TYPES[n.type]})`);
  }
  if (clamped.length) F.push(finding('error', 'resolution-clamped', 'resolution silently reduced by the licence: output smaller than asked', clamped));
  if (errored.length) F.push(finding('error', 'node-errors', 'ops reporting an error (messages: td_errors)', errored));
  if (shaders.length) F.push(finding('error', 'shader-compile', 'GLSL shader did not compile (TD files it as a warning): the op outputs a checkerboard or black', shaders));
  if (inactive.length) F.push(finding('error', 'output-off', 'output ops switched off: they produce nothing and report no error', inactive));
  // script errors
  const scripted = second.scriptErrors || {};
  const sp = Object.keys(scripted).sort();
  if (sp.length && verdicts) {
    const live = []; const unknown = []; const st = [];
    for (const p of sp) {
      const v = verdicts[p]?.verdict || 'live';
      const line = `${p} (${scriptExcerpt(scripted[p])})`;
      if (v === 'stale') st.push(`${line}, not raised again across ${verdicts[p].cooks || 0} cook(s)`);
      else if (v === 'unknown') unknown.push(line); else live.push(line);
    }
    if (live.length) F.push(finding('error', 'script-errors', `tracebacks still raised (cleared, back within ${PROBE_GAP_MS} ms); td_errors does not list script errors as errors`, live));
    if (unknown.length) F.push(finding('warning', 'script-errors', 'tracebacks kept from some time; nothing that runs the code cooked during the check, so live or fixed is unknown (text left in place)', unknown));
    if (st.length) F.push(finding('note', 'script-errors-stale', 'old tracebacks: cleared, the code ran again without raising, so fixed since (cleared for good)', st));
  } else if (sp.length) {
    F.push(finding('error', 'script-errors', 'ops with a traceback from a script or callback (TD keeps old ones: recheck:true tells live from stale)', sp.map((p) => `${p} (${scriptExcerpt(scripted[p])})`)));
  } else if (second.scriptErrorsRaw) {
    F.push(finding('error', 'script-errors', `a script raised somewhere under ${path}, owner not found: ${scriptExcerpt(second.scriptErrorsRaw)}`));
  }
  // cooking
  if (dormant.length) {
    if (probe === null || probe === undefined) {
      F.push(finding('warning', 'not-cooking', `ops did not cook in ${frames} frames and could not be probed: static (normal) or pulled by nothing is unknown`, dormant));
    } else {
      if (probe.cooked?.length) F.push(finding('warning', 'not-pulled', `change from frame to frame but nothing views, displays or records them, so they are not running (none cooked in ${frames} frames; asked twice ${PROBE_GAP_MS} ms apart, each had something new). To keep one live: view it, feed an output, or a Cache/Null with always cook`, probe.cooked));
      if (probe.unprobed?.length) F.push(finding('note', 'not-cooking-unprobed', "did not cook and were not asked (probe's cook budget ran out): static or unpulled is unknown", probe.unprobed));
      if (probe.never?.length) F.push(finding('note', 'never-cooked', 'never cooked since created: nothing asked for their output (not asked here: a first cook can be expensive)', probe.never));
      if (probe.skipped?.length) F.push(finding('note', 'quiet-outputs', `outputs that did not cook in ${frames} frames (not asked: a cook could write or send); one switched off is under output-off`, probe.skipped));
      if (probe.quiet?.length) F.push(finding('note', 'static', 'did not cook because nothing changed (normal for fixed settings, DATs, materials)', probe.quiet));
    }
  }
  if (paused) F.push(finding('note', 'paused', 'timeline paused: the frame clock stands still, so which ops cook cannot be judged until it plays'));
  else if (stalled) F.push(finding('warning', 'stalled', `only ${frames} frame(s) in ${elapsed}s: TD throttles when its window is in the background; bring it to the front before judging performance`));
  else if (fpsTarget && fps < fpsTarget * 0.6) F.push(finding('warning', 'slow', `running at ${fps} fps against ${fpsTarget}`));
  if (slow.length) F.push(finding('warning', 'expensive', `ops over ${SLOW_COOK_MS} ms per cook (a 60 fps frame is 16.7 ms)${frames <= 0 || paused ? '; clock frozen: last measured times, not the current frame' : ''}`, slow));
  if (stale.length) F.push(finding('note', 'expensive-stale', `cook time over ${SLOW_COOK_MS} ms from a cook before this check: not what holds the frame rate`, stale));
  if (bypassed.length) F.push(finding('warning', 'bypassed', 'ops bypassed', bypassed));
  if (through.length) F.push(finding('warning', 'bypass-passes-through', 'gain ops bypassed: bypass passes the input through at full strength, it does not switch the layer off (set the level to 0 or disconnect)', through));
  if (loops.length) F.push(finding('note', 'feedback-loops', 'feedback loops: cook(force=True) does not advance them, so frames made by forced cooks carry a stale trail; play the timeline instead', loops));
  if (negAdd.length) F.push(finding('warning', 'negative-float', 'Level TOPs that output negative floats (float format, no clamp, contrast > 1 / inlow > 0 / outlow < 0) into an Add below, which darkens it. Fix: Post page clamp, clamplow2 0', negAdd));
  if (negOnly.length) F.push(finding('note', 'negative-float', 'Level TOPs that can output negative floats (no Add found within 4 ops downstream). Post page clamp with clamplow2 0 removes them', negOnly));
  if (history.length) F.push(finding('note', 'history', 'ops carrying state frame to frame (they have a reset pulse): a frame reached by jumping the timeline or forcing cooks is not the playback frame; reset them before a take', history));
  const reads = second.clockReads || [];
  if (reads.length) {
    const c = second.clockReadsCount || reads.length;
    F.push(finding('warning', 'nondeterministic', `${c} read(s) of absTime, time.time() or an unseeded random: frames do not reproduce between runs (absTime does not follow the timeline). Use me.time.seconds/frame and seed generators${c > reads.length ? ` (${c - reads.length} more not listed)` : ''}`, reads.map(([p, where, call]) => (where === 'text' ? `${p} uses ${call}` : `${p} ${where} = ${call}`))));
  }
  const scan = second.scan || {};
  const short = [['pars', 'parameters'], ['scripts', 'scripts'], ['nan', 'CHOPs (NaN scan)']].filter(([k]) => Array.isArray(scan[k]) && scan[k][0] < scan[k][1]);
  if (short.length) F.push(finding('note', 'scan-budget', `time budget ran out: checked ${short.map(([k, w]) => `${scan[k][0]} of ${scan[k][1]} ${w}`).join(', ')}. Run on a sub-COMP for the rest`));
  const miss = second.missingFiles || [];
  if (miss.length) F.push(finding('warning', 'missing-files', `file pars naming files that do not exist${second.missingFilesCount > miss.length ? ` (${second.missingFilesCount - miss.length} more)` : ''}: the op loads nothing or keeps an old image`, miss.map(([p, par, v]) => `${p} ${par} = ${v}`)));
  const nan = second.nanChops || [];
  if (nan.length) F.push(finding('warning', 'nan-chops', 'CHOPs holding NaN/Inf samples: anything they drive goes undefined (black, jumps)', nan.map(([p, bad, all]) => `${p} (${bad} of ${all})`)));
  if (warned.length) F.push(finding('note', 'node-warnings', 'ops reporting a warning', warned));
  if (second.realTime === false) F.push(finding('note', 'non-realtime', 'Realtime is off: every frame is rendered, none dropped to keep up'));
  for (const n of second.notes || []) F.push(finding('note', 'unread', n));
  F.sort((a, b) => SEV[a.sev] - SEV[b.sev]);
  const counts = { error: 0, warning: 0, note: 0 };
  for (const f of F) counts[f.sev]++;
  return {
    path, build: second.build, ok: counts.error === 0, counts,
    fps: { target: fpsTarget, actual: fps, frames, seconds: elapsed, playing: second.playing },
    ops: nodes.length, cooking,
    findings: F,
    ...(F.length ? {} : { verdict: 'nothing wrong found' }),
    _dormant: dormant,
  };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// The whole check: call(cmd, args, timeoutMs) is the bridge call. Returns analyze()'s report.
export async function runHealth(call, { path = '/project1', interval = 1, recheck = false } = {}, wait = sleep) {
  const asked = interval;
  const iv = Math.max(0, Math.min(Number(interval) || 0, MAX_INTERVAL));
  const first = await call('health_sample', { path, counts_only: true }, 30000);
  await wait(iv * 1000);
  const second = await call('health_sample', { path }, 60000);
  const pre = analyze(first, second, { interval: iv, path });
  let probe;
  if (pre._dormant.length) {
    try {
      await call('health_probe', { paths: pre._dormant }, 30000);
      await wait(PROBE_GAP_MS);
      probe = await call('health_probe', { paths: pre._dormant }, 30000);
    } catch { probe = null; }
  }
  let verdicts;
  const scripted = Object.keys(second.scriptErrors || {});
  if (recheck && scripted.length) {
    let state;
    try {
      const c = await call('script_errors_recheck', { step: 'clear', paths: scripted }, 30000);
      if (c && c.available === false) second.notes = [...(second.notes || []), `recheck: ${c.note}`];
      else {
        state = c.state;
        await wait(PROBE_GAP_MS);
        verdicts = (await call('script_errors_recheck', { step: 'read', state }, 30000)).verdicts;
      }
    } catch {
      verdicts = null;
      if (state) { try { await call('script_errors_recheck', { step: 'restore', state }, 30000); } catch {} }
    }
  }
  const rep = analyze(first, second, { probe, verdicts, interval: iv, asked: asked === undefined ? undefined : Number(asked), path });
  delete rep._dormant;
  return rep;
}
