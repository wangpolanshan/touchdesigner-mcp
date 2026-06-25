#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createServer } from "./server.js";
import { TouchDesignerClient } from "./td-client.js";

function parsePositiveInteger(value: string | undefined, fallback: number) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

const url = process.env.TD_MCP_URL ?? "http://127.0.0.1:9980/api";
const token = process.env.TD_MCP_TOKEN ?? "";
const timeoutMs = parsePositiveInteger(process.env.TD_MCP_TIMEOUT_MS, 10_000);

if (!token) {
  console.error(
    "警告：未设置 TD_MCP_TOKEN。TouchDesigner 桥接默认要求安装脚本生成的令牌。",
  );
}

const client = new TouchDesignerClient({ url, token, timeoutMs });
const server = createServer(client);
const transport = new StdioServerTransport();

process.on("SIGINT", async () => {
  await server.close();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  await server.close();
  process.exit(0);
});

try {
  await server.connect(transport);
} catch (error) {
  console.error("TouchDesigner MCP 启动失败：", error);
  process.exit(1);
}
