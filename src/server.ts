import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { TouchDesignerClient } from "./td-client.js";

type ToolPayload = Record<string, unknown>;

function asToolResult(payload: unknown) {
  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(payload, null, 2),
      },
    ],
  };
}

function asToolError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return {
    content: [{ type: "text" as const, text: message }],
    isError: true,
  };
}

function registerForwardedTool<T extends z.ZodRawShape>(
  server: McpServer,
  client: TouchDesignerClient,
  name: string,
  description: string,
  schema: T,
  action = name,
) {
  (server.registerTool as any)(
    name,
    {
      description,
      inputSchema: schema,
    },
    async (args: any): Promise<any> => {
      try {
        return asToolResult(
          await client.call(action, args as unknown as ToolPayload),
        );
      } catch (error) {
        return asToolError(error);
      }
    },
  );
}

export function createServer(client: TouchDesignerClient): McpServer {
  const server = new McpServer({
    name: "touchdesigner-mcp",
    version: "0.1.0",
  });

  registerForwardedTool(
    server,
    client,
    "td_ping",
    "检查 TouchDesigner 桥接是否在线。",
    {},
    "ping",
  );

  registerForwardedTool(
    server,
    client,
    "td_project_info",
    "读取当前 TouchDesigner 工程、版本、时间轴和桥接信息。",
    {},
    "project_info",
  );

  registerForwardedTool(
    server,
    client,
    "td_list_operators",
    "递归列出指定根节点下的 Operators，可按名称、路径、OP 类型或 family 过滤。",
    {
      root: z.string().default("/project1").describe("搜索根路径"),
      pattern: z.string().default("*").describe("名称或路径的通配符"),
      op_type: z.string().optional().describe("例如 null、text、constant"),
      family: z
        .string()
        .optional()
        .describe("例如 COMP、TOP、CHOP、SOP、DAT、MAT"),
      max_depth: z.number().int().min(0).max(20).default(4),
      limit: z.number().int().min(1).max(1000).default(200),
    },
    "list_operators",
  );

  registerForwardedTool(
    server,
    client,
    "td_operator_info",
    "读取一个 Operator 的类型、连接、位置、子节点和可选参数。",
    {
      path: z.string().describe("绝对 OP 路径"),
      include_parameters: z.boolean().default(false),
      parameter_limit: z.number().int().min(1).max(1000).default(200),
    },
    "operator_info",
  );

  registerForwardedTool(
    server,
    client,
    "td_get_parameters",
    "读取一个 Operator 的参数值、表达式、模式和只读状态。",
    {
      path: z.string(),
      names: z.array(z.string()).optional().describe("省略则返回全部参数"),
    },
    "get_parameters",
  );

  registerForwardedTool(
    server,
    client,
    "td_set_parameter",
    "设置 Operator 参数的常量值或 Python 表达式。",
    {
      path: z.string(),
      name: z.string().describe("参数脚本名，如 tx、resolutionw"),
      value: z.unknown(),
      mode: z.enum(["constant", "expression"]).default("constant"),
    },
    "set_parameter",
  );

  registerForwardedTool(
    server,
    client,
    "td_pulse_parameter",
    "触发 Pulse 类型参数，例如 reset、reload、save。",
    {
      path: z.string(),
      name: z.string(),
    },
    "pulse_parameter",
  );

  registerForwardedTool(
    server,
    client,
    "td_create_operator",
    "在父 COMP 内创建新的 Operator。",
    {
      parent: z.string().describe("父 COMP 路径"),
      op_type: z
        .string()
        .describe("TouchDesigner OP 类型，如 baseCOMP、constantCHOP、textDAT"),
      name: z.string(),
      node_x: z.number().optional(),
      node_y: z.number().optional(),
    },
    "create_operator",
  );

  registerForwardedTool(
    server,
    client,
    "td_connect_operators",
    "连接两个 Operator 的输出和输入连接器。",
    {
      source: z.string(),
      target: z.string(),
      source_output: z.number().int().min(0).default(0),
      target_input: z.number().int().min(0).default(0),
    },
    "connect_operators",
  );

  registerForwardedTool(
    server,
    client,
    "td_disconnect_input",
    "断开目标 Operator 的指定输入连接。",
    {
      target: z.string(),
      target_input: z.number().int().min(0).default(0),
    },
    "disconnect_input",
  );

  registerForwardedTool(
    server,
    client,
    "td_set_node_position",
    "设置 Operator 在 Network Editor 中的位置。",
    {
      path: z.string(),
      node_x: z.number(),
      node_y: z.number(),
    },
    "set_node_position",
  );

  registerForwardedTool(
    server,
    client,
    "td_get_dat_text",
    "读取 Text DAT 等 DAT 的文本内容。",
    {
      path: z.string(),
      max_chars: z.number().int().min(1).max(2_000_000).default(100_000),
    },
    "get_dat_text",
  );

  registerForwardedTool(
    server,
    client,
    "td_set_dat_text",
    "替换 Text DAT 等 DAT 的文本内容。",
    {
      path: z.string(),
      text: z.string(),
    },
    "set_dat_text",
  );

  registerForwardedTool(
    server,
    client,
    "td_destroy_operator",
    "删除 Operator。必须明确传入 confirm=true；不能删除根节点或桥接自身。",
    {
      path: z.string(),
      confirm: z.literal(true),
    },
    "destroy_operator",
  );

  registerForwardedTool(
    server,
    client,
    "td_save_project",
    "保存当前 TouchDesigner 工程；可选另存为指定 .toe 路径。",
    {
      path: z.string().optional(),
    },
    "save_project",
  );

  registerForwardedTool(
    server,
    client,
    "td_execute_python",
    "在 TouchDesigner 主环境执行 Python。TD 桥接的 Allow Python 默认关闭，只有显式开启后可用。",
    {
      code: z.string(),
    },
    "execute_python",
  );

  return server;
}
