export interface TouchDesignerClientOptions {
  url: string;
  token: string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}

export interface TdBridgeResponse<T = unknown> {
  ok: boolean;
  result?: T;
  error?: string;
}

export class TouchDesignerError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "TouchDesignerError";
  }
}

export class TouchDesignerClient {
  private readonly url: string;
  private readonly token: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor(options: TouchDesignerClientOptions) {
    this.url = options.url;
    this.token = options.token;
    this.timeoutMs = options.timeoutMs ?? 10_000;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  async call<T = unknown>(
    action: string,
    args: Record<string, unknown> = {},
  ): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await this.fetchImpl(this.url, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-td-mcp-token": this.token,
        },
        body: JSON.stringify({ action, args }),
        signal: controller.signal,
      });

      const text = await response.text();
      let payload: TdBridgeResponse<T>;
      try {
        payload = JSON.parse(text) as TdBridgeResponse<T>;
      } catch {
        throw new TouchDesignerError(
          `TouchDesigner 返回了无效 JSON：${text.slice(0, 300)}`,
          response.status,
        );
      }

      if (!response.ok || !payload.ok) {
        throw new TouchDesignerError(
          payload.error ?? `TouchDesigner HTTP ${response.status}`,
          response.status,
        );
      }

      return payload.result as T;
    } catch (error) {
      if (error instanceof TouchDesignerError) {
        throw error;
      }
      if (error instanceof Error && error.name === "AbortError") {
        throw new TouchDesignerError(
          `连接 TouchDesigner 超时（${this.timeoutMs}ms）：${this.url}`,
        );
      }
      const message = error instanceof Error ? error.message : String(error);
      throw new TouchDesignerError(
        `无法连接 TouchDesigner：${message}。请确认 TD 已打开且 td_mcp_bridge 正在运行。`,
      );
    } finally {
      clearTimeout(timer);
    }
  }
}
