// Settings. Overrides come from `config.json` next to package.json (optional) and JTD_* environment variables.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// Relative .tox / project paths resolve against the bundle root (the folder holding every project).
export const BUNDLE = path.resolve(ROOT, '..');
const STATE = process.env.JTD_STATE_DIR || path.join(os.homedir(), 'Library/Application Support/JazibTDMCP');

const defaults = {
  stateDir: STATE,
  outputDir: path.join(ROOT, 'output'),
  logDir: path.join(ROOT, 'logs'),
  bridgePort: 9335,
};

function load() {
  let file = {};
  const p = path.join(ROOT, 'config.json');
  if (fs.existsSync(p)) file = JSON.parse(fs.readFileSync(p, 'utf8'));
  const cfg = { ...defaults, ...file };
  if (process.env.JTD_STATE_DIR) cfg.stateDir = process.env.JTD_STATE_DIR;
  if (process.env.JTD_BRIDGE_PORT) cfg.bridgePort = Number(process.env.JTD_BRIDGE_PORT);
  if (process.env.JTD_OUTPUT_DIR) cfg.outputDir = process.env.JTD_OUTPUT_DIR;
  if (process.env.JTD_LOG_DIR) cfg.logDir = process.env.JTD_LOG_DIR;
  fs.mkdirSync(cfg.stateDir, { recursive: true });
  return cfg;
}

export const CONFIG = load();
