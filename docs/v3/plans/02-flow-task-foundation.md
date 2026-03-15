# 02. Flow Task Foundation

目标：先把 `flow` 和 `task` 的主链打通，让 `v3` 能表达：

`repo issue -> task issue -> flow(branch)`

## ⚠️ 实现规范（强制）

**必须遵守**: [docs/v3/implementation-spec-phase2.md](../implementation-spec-phase2.md)

该文档定义了：
- ✅ 必须使用的技术栈（typer, rich, pydantic, loguru）
- ✅ 强制的目录结构
- ✅ 严格的分层职责
- ✅ 类型注解要求
- ✅ 测试要求
- ✅ 代码量限制

**违反规范将导致验收失败，不予合并。**

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

**文件结构**（必须符合 [实现规范](../implementation-spec-phase2.md)）:

```
scripts/python/vibe3/
├── cli.py                    # Typer 入口
├── commands/
│   ├── flow.py              # flow 命令调度
│   └── task.py              # task 命令调度
├── services/
│   ├── flow_service.py      # Flow 业务逻辑
│   └── task_service.py      # Task 业务逻辑
├── clients/
│   ├── git_client.py        # Git 操作封装
│   ├── github_client.py     # GitHub API 封装
│   └── store_client.py      # SQLite 封装
├── models/
│   ├── flow.py              # Flow Pydantic 模型
│   └── task.py              # Task Pydantic 模型
└── ui/
    └── console.py           # Rich 输出
```

**命令列表**:
- `vibe3 flow new` - 创建新 flow
- `vibe3 flow show` - 展示 flow 详情
- `vibe3 flow status` - 列出所有 flow
- `vibe3 flow bind` - 绑定 issue
- `vibe3 task add` - 添加 task
- `vibe3 task show` - 展示 task 详情

**测试要求**:
- 单元测试: `tests/unit/`
- 契约测试: `tests3/flow/`, `tests3/task/`

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

## 验收标准

**代码质量检查**（强制）:
- [ ] `mypy scripts/python/vibe3` - 类型检查通过
- [ ] `ruff check scripts/python/vibe3` - Lint 通过
- [ ] `black --check scripts/python/vibe3` - 格式检查通过
- [ ] 每个文件代码量符合规范
- [ ] 所有公共函数有类型注解

**功能验证**:
- [ ] `vibe3 flow new <name>` - 创建成功
- [ ] `vibe3 flow show` - 展示正确
- [ ] `vibe3 flow status` - 列表正确
- [ ] `vibe3 task add --repo-issue <id>` - 添加成功
- [ ] dirty workspace 检查有效

**测试验证**:
- [ ] 单元测试覆盖率 > 80%
- [ ] 契约测试全部通过

**文档更新**:
- [ ] README 包含使用说明
- [ ] 每个命令有 help 文档

**不通过条件**:
- ❌ 违反 [实现规范](../implementation-spec-phase2.md)
- ❌ 缺少类型注解
- ❌ 使用了禁止的依赖
- ❌ 测试不充分

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
