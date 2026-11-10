// Dev CLI: `node src/cli.js <cmd> '<json args>'` sends one raw bridge command to TD and prints the JSON result.
// `node src/cli.js health` prints bridge health; `node src/cli.js token` prints the token file path (never the token).
import { bridgeHealth, call, ensureBridge, TOKEN_FILE } from './bridge.js';

const [cmd, a = '{}'] = process.argv.slice(2);
if (!cmd) { console.log('usage: node src/cli.js <cmd> [json-args] | health | token'); process.exit(1); }
if (cmd === 'token') { console.log(TOKEN_FILE); process.exit(0); }
await ensureBridge();
if (cmd === 'health') { console.log(JSON.stringify(await bridgeHealth(), null, 1)); process.exit(0); }
try {
  console.log(JSON.stringify(await call(cmd, JSON.parse(a), 180000), null, 1));
} catch (e) { console.error(e.message); process.exit(2); }
