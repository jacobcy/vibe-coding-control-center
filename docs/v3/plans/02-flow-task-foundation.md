# 02. Flow Task Foundation

目标：先把 `flow` 和 `task` 的主链打通，让 `v3` 能表达：

`repo issue -> task issue -> flow(branch)`

## 必读输入

- `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`
- `docs/standards/glossary.md`
- `docs/standards/v2/command-standard.md`
- `docs/standards/git-workflow-standard.md`
- `docs/standards/v2/handoff-governance-standard.md`
- `docs/v3/01-command-and-skeleton.md`

## 当前上下文

这一阶段是 `v3` 的第一段真实业务实现。

目标不是做“完整 task 系统”，而是把执行主链立住，让人和 agent 能在本地和远端之间看清：

- 一条线当前真正对接的是哪个 task issue

这一轮新增 Handoff 同步逻辑：
- **`vibe handoff auth`**：实现执行者身份注册（planner/executor/reviewer）
- **JSON 同步**：实现从 `.agent/handoff/{branch}/*.json` 到 SQLite 的定时或指令触发式同步

这一轮只做这些事：

- `task add --repo-issue`
- `task link`
- `task show`
- `task list`
- `task update`
- `flow new`
- `flow bind --issue`
- `flow bind task <repo-issue>`
- `flow switch`
- `flow show`
- `flow status`
- `flow freeze --by`

**修正与撤销命令（本阶段可暂缓实现）**：

以下命令已在设计文档中定义（见 `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md` "修正与撤销" 章节），用于错误恢复和状态修正：

- `task unlink --repo-issue <id>`：解除 task 与参考 issue 的关联
- `flow unbind task`：解除 flow 与主 task 的绑定
- `flow unbind --issue <id>`：解除 flow 与特定参考 issue 的绑定
- `flow abort`：废弃当前 flow，删除 branch 和 draft PR

这些命令虽然属于 flow/task 域，但可以在后续阶段实现，不影响主链路的打通。

这一轮重点：

- 一个 flow 可绑定多个 `repo issue`
- 一个 flow 只能绑定一个 `task issue`
- `task` / `pr` group 先从 `task issue` 主字段开始
- `flow show` / `flow status` 先把链路看清
- stash / dirty workspace 规则先落地

## 真源与边界

- `repo issue` / `task issue` 编号直接用 GitHub 编号
- `flow` 只以 branch 为身份锚点
- `worktree` 只是物理目录，不承担 flow 身份
- 本地只允许最小 handoff store，不允许新建“本地 task 数据库心智”
- `task issue` group 从主字段开始，但只作为后续 `pr` 默认策略来源，不要在这一轮实现发布逻辑
- `vibe check` 需要参与这一轮，负责验证本地责任链和远端真源是否一致

## 建议交付物

- `task add --repo-issue`
- `task link`
- `task show`
- `task list`
- `task update`
- `flow new`
- `flow bind --issue`
- `flow bind task <repo-issue>`
- `flow switch`
- `flow show`
- `flow status`
- `flow freeze --by`
- **`handoff auth`**：身份注册逻辑
- **Handoff Sync**：JSON 文件编辑后的入库同步逻辑
- `vibe check`
- 对应的 `tests3/flow/*` 和 `tests3/task/*`

## 验证证据 (历史记录，当前已失效)

以下证据来自上一轮失败执行，在战场清理后不再视为当前有效证据：

```text
 ✓ vibe3 task add and list
 ✓ vibe3 flow new and bind
 ✓ vibe3 flow status shows active flow
 ✓ vibe3 flow new blocks on dirty workspace
 ✓ vibe3 flow freeze
```

手动验证：
- `bin/vibe3 task add "Test" --repo-issue 123` -> 成功
- `bin/vibe3 flow bind task 123` -> 成功
- `bin/vibe3 flow show` -> 成功展示链路
- `bin/vibe3 flow freeze --by "#blocker"` -> 状态变为 blocked

## 当前状态（清理后）

- `02` 的目标和边界仍有效
- 上一轮“已收口”结论已失效
- 下一轮执行必须重新提交：
  - flow/task 主链证据
  - 绑定规则证据
  - `vibe check` 对齐证据
  - dirty workspace 保护证据

状态：**待二次执行**。不得直接跳到 `03`，除非重新验证通过。

## 进入下一轮的条件

只有当“flow/task 主链已可见、输出模型已稳定、核心绑定规则已测试锁定”后，才能进入 `03`。

建议动到的文件：

- `lib3/flow/`
- `lib3/task/`
- `scripts/python/v3/flow/`
- `scripts/python/v3/task/`
- `tests3/flow/`
- `tests3/task/`

做完以后再进入 `03`。
