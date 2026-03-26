# Vibe3 Flow Task Issue Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 统一 `vibe3 flow` / `task` / `pr` / `plan` 的 task 语义，让 flow 直接围绕 GitHub issue 建立 task、related、dependency 与 spec ref 链路。

**Architecture:** 保持现有 command -> service -> client 分层，只收敛语义与编排。`flow create --task` / `flow blocked --task` / `flow bind` 统一接收 issue 引用，服务层负责本地 flow state、GitHub Project bridge、issue label 与 dependency 关系，plan context builder 负责把 issue 标题和 description 注入 plan agent。

**Tech Stack:** Typer, Pydantic, SQLiteClient, GitHub gh CLI, GitHub Projects v2 GraphQL, pytest

---

## Scope

- `flow create --task <issue-ref>` 把 issue 绑定为当前 flow 的 task
- `flow create --spec <spec-ref>` 作为唯一主语义
- task issue 自动加 `vibe-task` label，并确保进入 GitHub Project
- `flow blocked --task <issue-ref>` 把 issue 绑定为 dependency，并确保有 `vibe-task` label
- `flow bind <issue-ref>` 支持 `--role task|related|dependency`
- `flow show` 与 `pr` 在当前 flow 无 task 时给出 bind 建议
- `flow done` 在当前 flow 无 task 且未显式 `--yes` 时阻止关闭
- `spec_ref` 若是 issue，引入 `#id:<title>` 展示格式，并把 issue body 传给 plan agent

## Non-Goals

- 不改 GitHub Project 字段模型
- 不引入新的顶层命令
- 不重做现有 handoff / review / orchestra 流程

## Implementation Notes

- `--task` 统一解释为 GitHub issue 引用，支持 `123`、`#123`、issue URL
- `flow create` 的 spec 参数命名以 `--spec` 为准，避免 `--file` 无法表达“文件或 issue spec 引用”的问题
- 现有 `FlowService.bind_task()` 需要从“宽松 task_ref”语义收敛为“issue_ref -> issue_number”
- `flow bind` 是补绑入口，也承担追加 `related` / `dependency` 的能力
- `task link` 保留，但 `flow bind` 要成为 flow 视角下的等价入口
- `spec_ref` 需要区分“文件路径 spec”和“issue-based spec”

### Task 1: 收敛 CLI 语义与帮助文案

**Files:**
- Modify: `src/vibe3/commands/flow.py`
- Modify: `src/vibe3/commands/flow_lifecycle.py`
- Modify: `src/vibe3/commands/task.py`
- Test: `tests/vibe3/commands/test_task_management_commands.py`

**Step 1: 写失败测试**

在 `tests/vibe3/commands/test_task_management_commands.py` 增加以下覆盖：
- `flow create --task 219` 调用新的 issue 绑定路径，而不是旧的任意 task ID 绑定
- `flow create --spec docs/spec.md` 继续工作
- 若保留兼容，`flow create --file docs/spec.md` 输出 deprecated 提示并映射到 `--spec`
- `flow blocked --task 218` 帮助文案出现 `--task`，不再只暴露 `--by`
- `flow bind 220 --role task`
- `flow bind 219 --role related`
- `flow bind 218 --role dependency`
- `flow show` / `pr show` / `pr create` 的无 task 提示文案

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/commands/test_task_management_commands.py -q`
Expected: FAIL，帮助文案和 mock 调用与现状不一致

**Step 3: 写最小命令层改动**

在 `src/vibe3/commands/flow.py`：
- 将 `create(..., task=...)` 的帮助文案改为 `Task issue reference`
- 将 spec 参数命名保持为 `--spec`
- 若需要兼容历史调用，为 `--file` 增加 deprecated alias，并统一映射到 `spec`
- 新增 issue ref 解析复用点，优先复用 `parse_issue_ref()`，必要时提取公共工具
- 改造 `flow bind`：
  - 位置参数改名为 `issue`
  - 增加 `--role task|related|dependency`
  - `task` 走 task 绑定路径
  - `related/dependency` 走 `TaskService.link_issue()`

在 `src/vibe3/commands/flow_lifecycle.py`：
- `flow blocked` 保留 `--by` 兼容入口
- 新增 `--task` 作为推荐入口，语义等价于 dependency issue
- 明确禁止同时使用 `--by` 与 `--task`

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/vibe3/commands/test_task_management_commands.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/flow.py src/vibe3/commands/flow_lifecycle.py src/vibe3/commands/task.py tests/vibe3/commands/test_task_management_commands.py
git commit -m "feat: align flow CLI with issue-based task semantics"
```

### Task 2: 收敛服务层 task 绑定与 role 绑定

**Files:**
- Modify: `src/vibe3/services/flow_query_mixin.py`
- Modify: `src/vibe3/services/task_service.py`
- Modify: `src/vibe3/services/flow_lifecycle.py`
- Test: `tests/vibe3/services/test_flow_binding.py`
- Test: `tests/vibe3/services/test_task_linking.py`
- Test: `tests/vibe3/services/test_flow_lifecycle.py`

**Step 1: 写失败测试**

新增覆盖：
- `bind_task()` 接收 `#123`、URL、纯数字，统一解析成 issue number
- `flow bind --role task` 会设置 `task_issue_number`
- `flow bind --role related|dependency` 只写 issue_link，不覆盖 task
- `flow blocked --task 218` 会新增 dependency link
- 已有相同 role 绑定时保持幂等，不重复污染事件或至少不破坏状态

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/services/test_flow_binding.py tests/vibe3/services/test_task_linking.py tests/vibe3/services/test_flow_lifecycle.py -q`
Expected: FAIL

**Step 3: 写最小实现**

在 `src/vibe3/services/flow_query_mixin.py`：
- 提取 issue ref 解析逻辑，避免 `digits only` 的宽松实现误吞字符串
- `bind_task()` 只处理 issue 绑定，不再使用 “task ID format” 命名
- 绑定 task 后仍触发 auto project link

在 `src/vibe3/services/task_service.py`：
- 为 `link_issue()` 增加 task / related / dependency 的明确事件语义
- 若 role 是 `task`，保证本地 `task_issue_number` 与 issue link 一致

在 `src/vibe3/services/flow_lifecycle.py`：
- `block_flow(..., blocked_by_issue=...)` 继续复用 dependency link 路径
- 当由 `--task` 进入时，输出与日志文案统一为 dependency task

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/vibe3/services/test_flow_binding.py tests/vibe3/services/test_task_linking.py tests/vibe3/services/test_flow_lifecycle.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/services/flow_query_mixin.py src/vibe3/services/task_service.py src/vibe3/services/flow_lifecycle.py tests/vibe3/services/test_flow_binding.py tests/vibe3/services/test_task_linking.py tests/vibe3/services/test_flow_lifecycle.py
git commit -m "feat: align flow service bindings with issue roles"
```

### Task 3: 把 task issue 和 dependency issue 接到 GitHub label 与 Project

**Files:**
- Modify: `src/vibe3/services/task_bridge_mutation.py`
- Modify: `src/vibe3/services/task_bridge_mixin.py`
- Modify: `src/vibe3/services/label_service.py`
- Create: `src/vibe3/services/task_label_service.py`
- Test: `tests/vibe3/services/test_task_bridge_mutation.py`
- Test: `tests/vibe3/services/test_task_label_service.py`

**Step 1: 写失败测试**

新增覆盖：
- task issue 绑定后会给 issue 加 `vibe-task` label
- dependency issue 绑定后也会给 issue 加 `vibe-task` label
- issue 已在 project 中时不会重复 add
- issue 不在 project 中时会 add 并记录 item
- label 添加失败时不会破坏本地 flow state，但会返回可见 warning

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/services/test_task_bridge_mutation.py tests/vibe3/services/test_task_label_service.py -q`
Expected: FAIL

**Step 3: 写最小实现**

新增 `src/vibe3/services/task_label_service.py`：
- 封装 `ensure_vibe_task_label(issue_number)` 与必要的幂等逻辑
- 复用 `gh issue edit --add-label`

在 `src/vibe3/services/task_bridge_mutation.py`：
- `auto_link_issue_to_project()` 之前或之后调用 `ensure_vibe_task_label()`
- task 与 dependency 共用同一条 label/project side effect
- related issue 不自动进 project，除非后续另有需求

在 `src/vibe3/services/task_bridge_mixin.py`：
- 将“issue 绑定为 task/dependency 时自动加入项目”的注释与返回语义同步更新

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/vibe3/services/test_task_bridge_mutation.py tests/vibe3/services/test_task_label_service.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/services/task_bridge_mutation.py src/vibe3/services/task_bridge_mixin.py src/vibe3/services/label_service.py src/vibe3/services/task_label_service.py tests/vibe3/services/test_task_bridge_mutation.py tests/vibe3/services/test_task_label_service.py
git commit -m "feat: auto label and project-link issue-backed tasks"
```

### Task 4: 在 flow show 和 pr 命令中增加缺失 task 的引导

**Files:**
- Modify: `src/vibe3/commands/flow.py`
- Modify: `src/vibe3/commands/pr_create.py`
- Modify: `src/vibe3/commands/pr_query.py`
- Modify: `src/vibe3/ui/flow_ui.py`
- Modify: `src/vibe3/ui/pr_ui.py`
- Test: `tests/vibe3/commands/test_flow_show.py`
- Test: `tests/vibe3/commands/test_pr_create.py`
- Test: `tests/vibe3/commands/test_pr_show.py`

**Step 1: 写失败测试**

新增覆盖：
- `flow show` 当前 flow 没有 task 时，输出建议：`vibe3 flow bind <issue> --role task`
- `pr create` 当前 flow 没有 task 时，先显示提醒但不阻止创建
- `pr show` 当前 flow 没有 task 且当前分支无 PR 时，错误提示包含 bind 建议

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/commands/test_flow_show.py tests/vibe3/commands/test_pr_create.py tests/vibe3/commands/test_pr_show.py -q`
Expected: FAIL

**Step 3: 写最小实现**

- 命令层读取当前 flow state 的 `task_issue_number`
- 无 task 时只补充提示，不改变 exit code 设计，除了已有失败分支
- UI 层文案统一，不在多个命令里复制拼接逻辑

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/vibe3/commands/test_flow_show.py tests/vibe3/commands/test_pr_create.py tests/vibe3/commands/test_pr_show.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/flow.py src/vibe3/commands/pr_create.py src/vibe3/commands/pr_query.py src/vibe3/ui/flow_ui.py src/vibe3/ui/pr_ui.py tests/vibe3/commands/test_flow_show.py tests/vibe3/commands/test_pr_create.py tests/vibe3/commands/test_pr_show.py
git commit -m "feat: guide users to bind task before flow and pr actions"
```

### Task 5: 在 flow done 增加“无 task 需要 --yes”保护

**Files:**
- Modify: `src/vibe3/commands/flow_lifecycle.py`
- Modify: `src/vibe3/services/flow_lifecycle.py`
- Test: `tests/vibe3/services/test_flow_lifecycle.py`
- Test: `tests/vibe3/commands/test_flow_done.py`

**Step 1: 写失败测试**

新增覆盖：
- 当前 flow 没有 `task_issue_number` 时，`flow done` 默认失败
- 当前 flow 没有 task 且加 `--yes` 时允许继续
- 当前 flow 有 task 时保持现有 done 行为
- 指定 `--branch` 关闭其他 flow 时同样执行这条检查

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/services/test_flow_lifecycle.py tests/vibe3/commands/test_flow_done.py -q`
Expected: FAIL

**Step 3: 写最小实现**

- 在 command 层先查询 flow state 并做人类可读提示
- 或在 service 层抛出明确 `UserError` 风格异常，由 command 负责转成 `--yes` 提示
- 错误文案固定为：
  - 当前 flow 未绑定 task issue
  - 先执行 `vibe3 flow bind <issue> --role task`
  - 若确认强制关闭，使用 `vibe3 flow done --yes`

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/vibe3/services/test_flow_lifecycle.py tests/vibe3/commands/test_flow_done.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/commands/flow_lifecycle.py src/vibe3/services/flow_lifecycle.py tests/vibe3/services/test_flow_lifecycle.py tests/vibe3/commands/test_flow_done.py
git commit -m "feat: require explicit force when closing taskless flow"
```

### Task 6: 让 spec ref 支持 issue 形态并把 description 注入 plan agent

**Files:**
- Modify: `src/vibe3/services/flow_query_mixin.py`
- Modify: `src/vibe3/services/plan_context_builder.py`
- Modify: `src/vibe3/commands/plan.py`
- Modify: `src/vibe3/clients/github_issues_ops.py`
- Create: `src/vibe3/services/spec_ref_service.py`
- Test: `tests/vibe3/services/test_spec_ref_service.py`
- Test: `tests/vibe3/services/test_plan_context_builder.py`
- Test: `tests/vibe3/commands/test_plan.py`

**Step 1: 写失败测试**

新增覆盖：
- `flow bind --role task` 后，如果用户将 spec ref 指向 issue，展示值为 `#123:Title`
- `build_plan_context()` 在 task / issue-spec 场景下会包含：
  - issue 编号
  - issue 标题
  - issue description
- issue body 为空、issue 不存在、网络失败时的降级行为

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/vibe3/services/test_spec_ref_service.py tests/vibe3/services/test_plan_context_builder.py tests/vibe3/commands/test_plan.py -q`
Expected: FAIL

**Step 3: 写最小实现**

新增 `src/vibe3/services/spec_ref_service.py`：
- 识别 spec ref 是文件路径还是 issue 引用
- issue 引用格式化为 `#id:<title>`
- 返回用于展示与用于 prompt 的两个视图

在 `src/vibe3/services/plan_context_builder.py`：
- 为 task scope 增加可选 issue context section
- issue 可获取时，把 title/body 注入 `Planning Task` 或新增 `Issue Context` section
- body 为空时不输出空段落

在 `src/vibe3/commands/plan.py`：
- 若当前 flow 的 spec_ref 指向 issue，优先读取该 issue 内容
- 若当前 flow 有 task issue，也读取 task issue title/body 作为补充上下文
- 失败时降级，不阻塞 `plan` 主流程

在 `src/vibe3/clients/github_issues_ops.py`：
- 如有必要补充获取字段，保持只读、幂等接口

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/vibe3/services/test_spec_ref_service.py tests/vibe3/services/test_plan_context_builder.py tests/vibe3/commands/test_plan.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/vibe3/services/flow_query_mixin.py src/vibe3/services/plan_context_builder.py src/vibe3/commands/plan.py src/vibe3/clients/github_issues_ops.py src/vibe3/services/spec_ref_service.py tests/vibe3/services/test_spec_ref_service.py tests/vibe3/services/test_plan_context_builder.py tests/vibe3/commands/test_plan.py
git commit -m "feat: support issue-backed spec refs in planning context"
```

### Task 7: 更新文档与回归验证

**Files:**
- Modify: `docs/standards/vibe3-user-guide.md`
- Modify: `docs/references/flow-dependency.md`
- Modify: `CLAUDE.md`
- Test: `tests/vibe3/commands/test_task_management_commands.py`
- Test: `tests/vibe3/services/test_flow_binding.py`
- Test: `tests/vibe3/services/test_flow_lifecycle.py`
- Test: `tests/vibe3/commands/test_plan.py`

**Step 1: 更新文档**

同步以下内容：
- `flow create --task` 现在是 task issue 绑定，不是任意 task ID
- `flow blocked --task` 是 dependency issue 入口
- `flow bind` 是补绑 / 追加 role 的统一入口
- `flow done` 无 task 需要 `--yes`
- `spec ref` 支持 issue 形态与 plan agent description 注入

**Step 2: 跑目标测试集**

Run: `uv run pytest tests/vibe3/commands/test_task_management_commands.py tests/vibe3/services/test_flow_binding.py tests/vibe3/services/test_task_linking.py tests/vibe3/services/test_flow_lifecycle.py tests/vibe3/commands/test_plan.py -q`
Expected: PASS

**Step 3: 跑质量检查**

Run: `uv run ruff check src/vibe3 tests/vibe3`
Expected: PASS

**Step 4: 跑类型检查**

Run: `uv run mypy src/vibe3`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/standards/vibe3-user-guide.md docs/references/flow-dependency.md CLAUDE.md
git commit -m "docs: update vibe3 flow and task issue workflow"
```

## Risks

- 现有 `flow bind` 测试和帮助文案明显还是旧语义，重命名后会牵动较多 snapshot/assertion
- `project_item_id` 当前是按 flow 存储，不是按 issue-role 存储；dependency 自动进 project 时要确认是否允许多个 dependency 共用单个 flow 级 bridge 字段
- `spec_ref` 现有字段是单字符串，若同时支持文件和 issue，需要避免让 UI 和 PR metadata 变得含混
- `vibe-task` label 与现有 `state/*` label 体系并存时，要保证不会互相覆盖

## Decisions To Confirm During Implementation

1. dependency issue 自动进 GitHub Project 时，是否允许覆盖 flow 当前的 `project_item_id`
2. 若 flow 已绑定 task issue，再次 `flow bind <other> --role task` 是覆盖还是报错
3. `spec_ref` 是否允许同时保留原始 issue URL 与展示格式化值

## Recommended Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6
7. Task 7
