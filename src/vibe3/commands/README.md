# Commands

`src/vibe3/commands/` 是 Typer CLI 的参数解析与展示层。业务事实由
`analysis/`、`services/` 和 `clients/` 提供，command renderer 不重新分析或补猜数据。

## 主要命令组

- `flow*`、`task.py`：flow/task 生命周期与状态。
- `handoff*`：共享 handoff 的读写与渲染。
- `pr*`：PR 查询、创建、生命周期和质量门禁。
- `plan.py`、`run.py`、`review.py`：agent 执行入口。
- `status*`、`scan.py`、`check*`：运行时状态与治理检查。
- `internal.py`、`mcp.py`、`ask.py`：内部 bootstrap、MCP 与知识查询。

## Inspect 证据接口

公共子命令只有：

```bash
vibe3 inspect base [<base>] --json
vibe3 inspect files <file.py> --json
vibe3 inspect symbols <file.py>:<symbol> --json
```

- `inspect.py` 注册命令组及单文件 `files`。
- `inspect_base.py` 与 `inspect_base_helpers.py` 展示精确 Git change partitions、
  Review Kernel 命中和最低 review depth。
- `inspect_symbols.py` 展示 provider 返回且经范围校验的正向引用证据。

Inspect 不预测运行时影响、不输出风险分数、不判断 dead code，也不提供 snapshot、
PR/commit 分析或 DAG 扩散。

## 依赖规则

- command 只做参数解析、调用 use case/analysis 和渲染 model。
- 共享选项放在 `command_options.py`，跨命令 helper 必须保持薄层。
- Git、GitHub、SQLite 等外部访问通过 `clients/`。
- 禁止在 renderer 中创建第二套业务真源。
