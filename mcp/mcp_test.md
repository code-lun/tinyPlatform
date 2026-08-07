测试目标

  验证 MCP 服务器能否通过 stdio 协议，将后端 API
  的工具（sys_check.sh、get_time.sh）暴露给外部客户端调用。

  测试方法

  编写测试客户端 mcp/test_client.py，通过 mcp.client.stdio.stdio_client 启动 mcp/server.py 子进程，建立
  JSONRPC 通信，依次调用 list_tools 和 call_tool 验证完整链路：

  测试客户端 ──(stdio)──▶ MCP 服务器 ──(HTTP)──▶ FastAPI 后端 ──(subprocess)──▶ Shell 脚本

  ---
  遇到的问题及解决

  1. 变量名拼写错误

  server.py 第21行定义了 EST_TIMEOUT，但第30行和第96行引用的是 REQUEST_TIMEOUT，后者未定义，会导致
  NameError。

  → 将 EST_TIMEOUT 改为 REQUEST_TIMEOUT。

  ---
  2. MCP SDK 主版本升级导致 API 完全不兼容

  项目 requirements.txt 写的是 mcp>=1.0.0，但实际安装到了 mcp 2.0.0。v1 → v2 的 API 是破坏性变更：

  ┌──────────────┬─────────────────────────┬────────────────────────────────────────────────────────┐
  │     项目     │    MCP 1.x（旧代码）    │                   MCP 2.0（新 API）                    │
  ├──────────────┼─────────────────────────┼────────────────────────────────────────────────────────┤
  │ 导入 Server  │ from mcp.server import  │ from mcp.server.lowlevel import Server                 │
  │              │ Server                  │                                                        │
  ├──────────────┼─────────────────────────┼────────────────────────────────────────────────────────┤
  │ 注册         │ @mcp.list_tools()       │ server.add_request_handler("tools/list",               │
  │ list_tools   │ 装饰器                  │ PaginatedRequestParams, handler)                       │
  ├──────────────┼─────────────────────────┼────────────────────────────────────────────────────────┤
  │ 注册         │ @mcp.call_tool() 装饰器 │ server.add_request_handler("tools/call",               │
  │ call_tool    │                         │ CallToolRequestParams, handler)                        │
  ├──────────────┼─────────────────────────┼────────────────────────────────────────────────────────┤
  │ Tool 字段    │ inputSchema（驼峰）     │ input_schema（蛇形）                                   │
  └──────────────┴─────────────────────────┴────────────────────────────────────────────────────────┘

  → 重写 server.py，将装饰器模式改为 add_request_handler() 显式注册。

  ---
  3. Handler 函数签名不对

  MCP 2.0 的 handler 签名为 (ctx, params) —— 第一个参数是 RequestContext。旧代码只写了 (params)
  一个参数，调用时报错 takes 1 positional argument but 2 were given。

  → 给 handle_list_tools 和 handle_call_tool 都加上 ctx 参数。

  ---
  4. print() 污染 MCP 通信通道

  server.py 中的 print() 输出到了 stdout，而 MCP 的 stdio 传输正是通过 stdout 传递 JSONRPC
  消息。日志混杂在 JSON 中导致客户端解析失败：Invalid JSON: expected value at line 1 column 2（它读到了
  [MCP] 服务器启动... 这段中文）。

  → 将所有 print() 改为 print(..., file=sys.stderr, flush=True)，确保日志走 stderr，stdout 只留给
  JSONRPC 协议消息。

  ---
  5. 依赖冲突（附带问题）

  安装 mcp 时依赖树将 starlette 从 0.38 升级到 1.4，而旧版 fastapi 0.115.0 要求
  starlette<0.39，导致后端启动报 Router.__init__() got an unexpected keyword argument 'on_startup'。

  → 升级 fastapi 到 0.141.1（兼容 starlette 1.x）。

  ---
  最终测试结果

  === 工具列表 ===
    get_time: 获取当前系统时间，包含日期时间、毫秒时间戳和时区信息
    sys_check: 系统资源巡检，检查 CPU、内存、磁盘、网络等资源使用情况

  === 调用 sys_check ===
  {"status": "success", "code": 0, "data": {"cpu_usage": 32.3, "mem_usage": 71.05, "disk_usage": 16}}

  === 调用 get_time ===
  {"status": "success", "code": 0, "data": {"datetime": "2026-08-06 11:06:35", "timezone": "CST"}}

  三条 MCP 协议操作全部成功，scripts/ → backend/ → mcp/ → 客户端 全链路打通。