// td_crash_report (26 Oct 2026, after crashes T-64/T-70/T-74/T-76): what killed TouchDesigner, read from files only,
// so it works with TD dead, hung or relaunched. The work is td/crashdb.py (pure Python, same file TD loads for the
// td_exec crash guard): newest ~/Library/Logs/DiagnosticReports/TouchDesigner-*.ips (crashed thread libs, signal),
// logs/td_faulthandler.log (Python stacks of every thread, written by handlers.install_faulthandler) and the td_execs
// in flight in logs/exec.log -> summary + known patterns + a PROPOSED new pattern (never added automatically).
import { execFileSync } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';

export const PYTHON = process.env.JTD_PYTHON || 'python3';
export const diagDir = () => process.env.JTD_DIAG_DIR || path.join(os.homedir(), 'Library', 'Logs', 'DiagnosticReports');

export function crashArgs(a, { root, logDir, diag = diagDir() }) {
  const args = ['-I', path.join(root, 'td', 'crashdb.py'), 'report', '--diag-dir', diag,
    '--exec-log', path.join(logDir, 'exec.log'), '--fh-log', path.join(logDir, 'td_faulthandler.log'),
    '--patterns', path.join(root, 'logs', 'crash_patterns.json'),
    '--window', String(a.window_s ?? 120), '--tail', String(a.tail ?? 60)];
  if (a.ips) {
    if (!/\.ips$/i.test(a.ips)) throw new Error(`ips must be a .ips crash report: ${a.ips}`);
    args.push('--ips', path.isAbsolute(a.ips) ? a.ips : path.join(diag, a.ips));
  }
  return args;
}

export function crashReport(a = {}, opts) {
  let out;
  try {
    out = execFileSync(opts.python || PYTHON, crashArgs(a, opts), { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, timeout: 60000, stdio: ['ignore', 'pipe', 'pipe'] });
  } catch (e) { throw new Error(`td/crashdb.py failed: ${String(e.stderr || e.message).trim().split('\n').slice(-3).join(' ').slice(0, 400)}`); }
  return JSON.parse(out);
}

export function registerCrash({ server, text, fail, z, CONFIG, ROOT }) {
  server.registerTool('td_crash_report', { description: 'After a TouchDesigner crash or hang (TD not needed; read-only): parses the newest ~/Library/Logs/DiagnosticReports/TouchDesigner-*.ips (or ips: a file name there / absolute path): signal, crashed thread, its library chain (libGX <- libC_TOP <- Python = a TOP Python call; libUT/libUI/libOPUI = UI drawing); the faulthandler log logs/td_faulthandler.log (Python stack of every thread at the fault, the session of that pid); the td_execs in flight from logs/exec.log (never ended or ended with a bridge timeout/disconnect, around the crash; the crash time falls back to TD\'s last reply when the report was written much later, i.e. TD hung on its crash dialog). Matches them against logs/crash_patterns.json (by stack and by code) -> verdict, and for an unknown crash a PROPOSED pattern entry (status "proposed": the main session reviews it, writes LEARNINGS, then adds it; td_exec\'s crash guard reads the file on its next call).',
    inputSchema: { ips: z.string().optional().describe('a .ips file name in DiagnosticReports or an absolute path (default: newest TouchDesigner-*.ips)'),
      window_s: z.number().int().min(10).max(7200).optional().describe('seconds before the crash to look for in-flight execs (default 120)'),
      tail: z.number().int().min(5).max(500).optional().describe('faulthandler lines to return (default 60)') } }, async (a) => {
    try { return text(crashReport(a || {}, { root: ROOT, logDir: CONFIG.logDir })); } catch (e) { return fail(e); }
  });
}
