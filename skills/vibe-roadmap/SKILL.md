---
name: vibe-roadmap
description: Use when the user wants project-level roadmap planning, version goals, backlog triage, or issue placement decisions, asks what the current or next version should contain, or mentions "vibe roadmap", "/vibe-roadmap", "/roadmap", "版本规划", "下一个版本做什么", or "这个 issue 放哪一版".
---

# /vibe-roadmap - 智能调度器

维护全景路线图，管理版本目标，对 task item 进行分类，决定规划窗口纳入什么。

**核心原则:** `/vibe-roadmap` 是规划层的 dispatch brain，负责调度决策；`uv run python src/vibe3/cli.py task` 负责 shell 层读写数据。

intake gate 约束：

- 不是所有 `repo issue` 都自动进入 GitHub Project。
- 只有经过 `vibe-roadmap` triage 的候选 `repo issue`，才应纳入 task item / GitHub Project。
- shell 层不负责智能 intake gate；是否纳入 Project 属于 skill / workflow 的规划判断。
- `vibe-roadmap` 消费的是 `repo issue intake 视图`，而不是本地长期 issue cache / registry。
- intake 视图应来自运行时查询与 task 列表对比。
- 若未来需要留痕，优先保存 triage 决策快照，而不是复制 issue 整池真源。

对象约束：

- `repo issue`: 需求来源
- `task item = GitHub Project item mirror`
- `task = execution record`
- `spec_standard/spec_ref` 是 task 侧扩展桥接字段，不是 GitHub Project 官方来源类型
- task bridge = 规划层 mirror 同步
- `task audit` = execution record 审计 / 修复
- OpenSpec 注册 = execution spec 来源桥接
- 任何规划判断都必须先读 shell 输出，再做编排

标准真源：

- 术语与默认动作语义以 `docs/standards/glossary.md`、`docs/standards/action-verbs.md` 为准。
- Skill 与 Shell 边界以 `docs/standards/v3/skill-standard.md`、`docs/standards/v3/command-standard.md`、`docs/standards/v3/python-capability-design.md` 为准。
- 触发时机与相邻 skill 分流以 `docs/standards/v3/skill-trigger-standard.md` 为准。
- task / flow / worktree 语义以 `docs/standards/v3/git-workflow-standard.md`、`docs/standards/v3/worktree-lifecycle-standard.md` 为准。

**Announce at start:** "我正在使用 /vibe-roadmap 技能来管理版本路线图。"

**命令自检:** 对 `uv run python src/vibe3/cli.py task` 的参数、子命令或 flag 有任何不确定时，先运行 `--help`。shell 命令是 agent 的工具入口，不是面向用户的命令教学清单。

## Trigger Examples

- `vibe roadmap`
- `/vibe-roadmap`
- `/roadmap`
- `版本规划`
- `下一个版本做什么`
- `管理许愿池`
- `版本目标`

## Hard Boundary

- 只负责规划层调度，不负责 `repo issue` 创建、task registry 修复或 runtime 修复
- 必须先运行 `uv run python src/vibe3/cli.py task` 相关 shell 命令
- 不得直接修改 `registry.json` 底层数据
- 必须通过 Shell API 写入数据
- 调度器无法判断优先级时，必须要求人类讨论
- 若涉及主 issue / sub-issue，只承接 skill/workflow 已做出的范围判断，不在 shell 层发明 parent/sub-issue 运行时逻辑

边界对照：

- `repo issue` intake、模板补全、查重：交给 `vibe-issue`
- `task <-> flow` 映射核对与修复：交给 `vibe-task`
- `task <-> flow` / worktree runtime 修复：交给 `vibe-check`
- OpenSpec / plan 到 `spec_standard/spec_ref` 的 execution spec 写回：交给 `vibe-task` 或 task 写入路径
- parent issue / sub-issue 的范围判断：交给 `vibe-issue` 等 skill/workflow；`vibe-roadmap` 只消费判断结果

## Workflow

### Step 1: 检查版本目标

先运行获取当前版本目标状态；必要时再补充文本输出：

```bash
uv run python src/vibe3/cli.py task list
uv run python src/vibe3/cli.py task show
```

获取：

- 当前版本目标是什么
- 有哪些 `repo issue` / task item 等待分类
- 各个分类下有多少 task item

### Step 2: 调度决策

根据当前状态做出决策：

**场景 A: 没有版本目标**

- 提示用户定义版本目标
- 展示许愿池中的 `repo issue` 供选择
- 要求人类讨论确定目标

**场景 B: 有版本目标但有新 `repo issue`**

- 对新的 `repo issue` / task item 进行分类：P0/当前版本/下一个版本/延期/拒绝
- 对候选 `repo issue` 做 intake gate 判断：纳入 / 不纳入 / 待讨论
- 按优先级排序
- 若该 issue 来自已有治理母题，先读取上游 skill/workflow 的范围判断：
  - 仍在原主 issue 范围内，可继续按 sub-issue 进入规划
  - 已超出原范围，要求拆成新的独立 issue，再决定归类

**场景 C: 版本结束**

- 确认下一版本目标
- 重新评估待分类 Issue

### Step 3: 输出状态

输出当前路线图状态：

```text
## 当前版本: v2.0

### P0 (紧急)
- #36: GitHub Projects 整合

### 当前版本
- #34: Issue 同步
- #35: save 自动关联

### 下一个版本
- 待定

### 延期
- 待讨论
```

### Step 4: 响应 vibe-new 调用

当 `/vibe-new` 触发时：

- 检查是否有版本目标
- 无目标 → 要求人类讨论确定
- 有目标 → 提示当前规划窗口有哪些 task item 可供继续拆成 task execution record
- 是否拆 task execution record、拆几个、绑定到哪个 flow，由上层 skill / agent 决定
- 不得把扩展层的 `spec_standard/spec_ref` 描述成 GitHub Project 官方来源类型

### Step 5: 同步到 GitHub Project

如需将 issue 链接到 GitHub Project：

```bash
uv run python src/vibe3/cli.py task bridge <issue_number>
```

## Roadmap 分类状态

| 状态       | 含义                     | 行为                                               |
| ---------- | ------------------------ | -------------------------------------------------- |
| P0         | 阻断性问题，需要立即处理 | 优先进入规划讨论，不直接等于 branch 当前任务       |
| 当前版本   | 明确纳入当前规划窗口     | 可被后续 skill 拆成 task，但不等于 branch 当前任务 |
| 下一个版本 | 有更优先的事项，但要做   | 本版本结束后自动成为下版本目标                     |
| 延期       | 待决定，暂时不做         | 等下次讨论                                         |
| 拒绝       | 不做                     | 关闭                                               |

## Failure Handling

如果 shell 命令失败：

- 直接展示 CLI 返回的阻塞原因
- 明确告诉用户当前无法进行路线图管理
- 不要自行 fallback 到直接修改 JSON

## Terminology Contract

- `版本目标`: 当前版本要完成的目标
- `许愿池`: GitHub `repo issues`（需求池）
- `repo issue`: 需求来源与讨论入口，不是 execution record
- `Task Item`: GitHub Project item，规划层工作单元
- `Task`: execution record，执行层最小单元
- `Flow`: task execution record 的运行时容器，通常由一个 worktree / branch 承载

## 命令映射说明

| 旧命令 (vibe2) | 新命令 (vibe3) |
|---------------|---------------|
| `vibe roadmap status` | `uv run python src/vibe3/cli.py task list` |
| `vibe roadmap list` | `uv run python src/vibe3/cli.py task list` |
| `vibe roadmap sync` | `uv run python src/vibe3/cli.py task bridge <issue>` |
| `vibe roadmap add` | `gh issue create` + `uv run python src/vibe3/cli.py flow bind` |
| `vibe roadmap audit` | `uv run python src/vibe3/cli.py check --all` |