import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { createItemsServer } from "./server";

/** Connect a real MCP Client to the real server over a linked in-memory transport (same protocol, no process). */
export async function connectInMemory(): Promise<{ client: Client; close: () => Promise<void> }> {
  const server = createItemsServer();
  const client = new Client({ name: "genux-host", version: "1.0.0" }, { capabilities: {} });
  const [clientT, serverT] = InMemoryTransport.createLinkedPair();
  await Promise.all([server.connect(serverT), client.connect(clientT)]);
  return { client, close: async () => { await client.close(); await server.close(); } };
}
