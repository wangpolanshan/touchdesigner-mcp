# TouchDesigner MCP

通过标准 MCP Server 控制正在运行的 TouchDesigner。TD 端使用可拖入的 `.tox` 组件提供本地 HTTP 桥接，MCP Server 通过 `stdio` 对外暴露工具。

## 内容

- `outputs/TD_MCP_Bridge.tox`：TouchDesigner 组件，拖入 TD 即可使用。
- `src/`：标准 MCP Server 源码。
- `touchdesigner/install_td_mcp.py`：开发/重建 `.tox` 用的 TD 安装脚本。

## 使用 TouchDesigner 组件

1. 打开目标 `.toe`。
2. 将 `outputs/TD_MCP_Bridge.tox` 拖入 TouchDesigner 网络编辑区。
3. 选中 `TD_MCP_Bridge` 组件。
4. 在 `MCP` 参数页设置：
   - `端口`：默认 `9980`
   - `访问令牌`：请自行设置，不要公开
   - `服务开关`：打开后启动 Web Server DAT
5. 连接地址通常是：

```text
http://127.0.0.1:9980/api
```

## 安装 Node.js 依赖

要求 Node.js 20 或更高版本：

```powershell
npm install
npm run build
```

## MCP Client 配置示例

把 `<项目目录>` 替换为你本机 clone 后的目录，把 `<访问令牌>` 替换为 TD 组件 MCP 参数页里的访问令牌。

```json
{
  "mcpServers": {
    "touchdesigner": {
      "command": "node",
      "args": [
        "<项目目录>/dist/index.js"
      ],
      "env": {
        "TD_MCP_URL": "http://127.0.0.1:9980/api",
        "TD_MCP_TOKEN": "<访问令牌>",
        "TD_MCP_TIMEOUT_MS": "10000"
      }
    }
  }
}
```

## 可用能力

- `td_ping`
- `td_project_info`
- `td_list_operators`
- `td_operator_info`
- `td_get_parameters`
- `td_set_parameter`
- `td_pulse_parameter`
- `td_create_operator`
- `td_connect_operators`
- `td_disconnect_input`
- `td_set_node_position`
- `td_get_dat_text`
- `td_set_dat_text`
- `td_destroy_operator`
- `td_save_project`
- `td_execute_python`

## 安全说明

- 不要提交 `.env` 或真实访问令牌。
- 默认只建议绑定本机 `127.0.0.1` 使用，不要把端口暴露到公网。
- `td_execute_python` 默认关闭；确有需要时，在 TD 组件的 MCP 参数页手动开启 `允许任意 Python`。
- `td_destroy_operator` 需要显式传入 `confirm=true`，并且桥接组件与工程根节点受保护。

## 验证

```powershell
npm test
```
