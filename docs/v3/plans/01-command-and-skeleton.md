# 01. Command And Skeleton

目标：先把 `vibe3` 的实现骨架立起来，不碰旧 `lib/`，也不急着实现完整业务。

## 必读输入

- `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`
- `docs/plans/2026-03-13-vibe3-parallel-rebuild-plan.md`
- `docs/standards/v2/command-standard.md`
- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `STRUCTURE.md`

## 当前上下文

这一阶段不是在实现完整的 `v3` 业务，而是在建立一个不会继续污染 `2.x` 的新入口。

这里最容易走样的地方有两个：

- 一上来就把旧 `lib/` 逻辑搬过来，导致 `v3` 只是换目录的 `v2`
- 还没立起统一入口和错误/输出规则，就开始堆 `flow/task/pr` 业务分支

这一轮的正确目标是：先把“命令壳 + 目录壳 + Python 壳 + 测试壳”定稳。

这一轮只做这些事：

- 建立 `v3` 的目录骨架
- 明确 `bin/vibe3` 的命令分发入口
- 建立 `flow / task / pr / handoff` 四个域的最小空壳
- 建立 Python 侧最小 runtime 入口
- 固定统一输出 / 错误 / `--json` / `-y` 规则
- **新增**：建立 `vibe3 handoff auth` 和 `vibe3 handoff edit` 命令入口

这一轮不做：

- 真实 GitHub Project 写操作
- 真实 task / flow / pr 业务逻辑
- bump / changelog
- review comment 回贴
- handoff 自动刷新

**设计完整性说明**：

虽然本阶段只建立命令骨架，但完整的设计文档（`docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`）已包含"修正与撤销"命令集，用于错误恢复：

- `task unlink / update`
- `flow unbind / abort`
- `pr close`

这些命令将在后续阶段（02-04）逐步实现，本阶段只需确保命令分发入口能识别这些命令名即可（返回 "Not implemented in MVP" 提示）。

## 真源与边界

- 命令语义真源：`docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`
- 术语真源：`docs/standards/glossary.md`
- 旧实现目录 `lib/` / `tests/` 只可参考，不可直接复制整套心智
- 当前阶段不允许为了“跑起来”而把 `worktrees.json`、`roadmap.json` 重新拉回 `v3` 主链

## 建议交付物

- `bin/vibe3` 最小入口
- `lib3/common/` 下统一错误、输出、参数校验 helper
- `lib3/flow/`、`lib3/task/`、`lib3/pr/`、`lib3/handoff/` 的 help 与 dispatcher 空壳
- `scripts/python/v3/` 最小入口，例如统一 `main.py` 或分域命令入口
- `tests3/smoke/` 的最小 smoke contract

建议动到的文件：

- `bin/vibe3`
- `lib3/common/`
- `lib3/flow/`
- `lib3/task/`
- `lib3/pr/`
- `scripts/python/v3/`
- `tests3/smoke/`

## 验证证据 (历史记录，当前已失效)

以下证据来自上一轮失败执行，在战场清理后不再视为当前有效证据：

```text
 ✓ vibe3 --help should show usage
 ✓ vibe3 flow --help should show flow usage
 ✓ vibe3 task --help should show task usage
 ✓ vibe3 pr --help should show pr usage
 ✓ vibe3 with unknown domain should fail
 ✓ vibe3 flow with unknown command should fail with not implemented
 ✓ vibe3 flow smoke-python should call python core and return json
 ✓ vibe3 task unknown should fail with not implemented
 ✓ vibe3 pr unknown should fail with not implemented
```

手动验证：
- `bin/vibe3 flow smoke-python --arg1 val1` -> 返回正确 JSON
- `bin/vibe3 unknown` -> 报错 Unknown domain
- `bin/vibe3 flow` -> 返回 flow usage

## 当前状态（清理后）

- `01` 的目标和边界仍有效
- 上一轮“已收口”结论已失效
- 下一轮执行必须重新提交：
  - 当前实现路径
  - 当前 smoke test 结果
  - 当前 CLI 契约证据

状态：**待二次执行**。不得直接跳到 `02`，除非重新验证通过。

## 进入下一轮的条件

只有当下面四件事都成立，才能进入 `02`：

- 新入口存在
- 三个域的命令壳存在
- smoke tests 存在
- 输出/错误契约已被验证锁住

做完以后再进入 `02`。
