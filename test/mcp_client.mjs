// Live test harness: spawns the MCP server over stdio (exactly as Claude Code would) and calls one tool.
// node test/mcp_client.mjs <tool> '<json args>'      (node test/mcp_client.mjs --list)
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const [name, raw = '{}'] = process.argv.slice(2);
const client = new Client({ name: 'jtd-test', version: '0' });
await client.connect(new StdioClientTransport({ command: process.execPath, args: [new URL('../src/server.js', import.meta.url).pathname] }));
if (name === '--list') {
  const { tools } = await client.listTools();
  console.log(tools.map((t) => t.name).join('\n'));
} else {
  const r = await client.callTool({ name, arguments: JSON.parse(raw) }, undefined, { timeout: 15 * 60 * 1000 });
  for (const c of r.content) {
    if (c.type === 'image') console.log(`[image ${c.mimeType}, ${Buffer.from(c.data, 'base64').length} bytes]`);
    else console.log(c.text);
  }
  if (r.isError) process.exitCode = 2;
}
await client.close();
