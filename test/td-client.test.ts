import assert from "node:assert/strict";
import { createServer } from "node:http";
import test from "node:test";
import {
  TouchDesignerClient,
  TouchDesignerError,
} from "../src/td-client.js";

test("向 TD 桥接发送 action、args 和 token", async () => {
  let receivedBody = "";
  let receivedToken = "";

  const server = createServer((request, response) => {
    receivedToken = String(request.headers["x-td-mcp-token"] ?? "");
    request.setEncoding("utf8");
    request.on("data", (chunk) => {
      receivedBody += chunk;
    });
    request.on("end", () => {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ ok: true, result: { pong: true } }));
    });
  });

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  assert(address && typeof address === "object");

  try {
    const client = new TouchDesignerClient({
      url: `http://127.0.0.1:${address.port}/api`,
      token: "test-token",
    });
    const result = await client.call("ping", { value: 1 });

    assert.deepEqual(result, { pong: true });
    assert.equal(receivedToken, "test-token");
    assert.deepEqual(JSON.parse(receivedBody), {
      action: "ping",
      args: { value: 1 },
    });
  } finally {
    server.close();
  }
});

test("将 TD 业务错误转换为 TouchDesignerError", async () => {
  const fakeFetch: typeof fetch = async () =>
    new Response(JSON.stringify({ ok: false, error: "节点不存在" }), {
      status: 404,
      headers: { "content-type": "application/json" },
    });

  const client = new TouchDesignerClient({
    url: "http://127.0.0.1:9980/api",
    token: "test",
    fetchImpl: fakeFetch,
  });

  await assert.rejects(
    client.call("operator_info", { path: "/missing" }),
    (error: unknown) =>
      error instanceof TouchDesignerError &&
      error.message === "节点不存在" &&
      error.status === 404,
  );
});
