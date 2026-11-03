import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createItemsServer } from "./server";

// Run with: pnpm mcp:stdio — for any desktop MCP host (see docs/labs/mcp-apps.md).
const server = createItemsServer();
await server.connect(new StdioServerTransport());
console.error("genux-items MCP server running on stdio");
