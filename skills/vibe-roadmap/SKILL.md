---
name: vibe-roadmap
description: Use when the user wants project-level roadmap planning, version goals, backlog triage, or issue placement decisions, asks what the current or next version should contain, or mentions "vibe roadmap", "/vibe-roadmap", "/roadmap", "版本规划", "下一个版本做什么", or "这个 issue 放哪一版".
---

# /vibe-roadmap - 版本规划助手

维护版本路线图，管理 milestone、roadmap 桶和规划层优先级元数据，决定哪些 issue 进入哪个版本窗口。

**核心原则:** `/vibe-roadmap` 是版本规划层，不是 runtime 调度器。它负责给 issue 设定规划元数据，供后续治理与执行参考；shell 层只负责暴露现场事实。

**新增核心原则:** 所有 roadmap 管理通过 GitHub issue labels 触发，不在本地实现数据存储，遵循 GitHub-as-truth 原则。

**核心职责:**

- **审查纠正 governance 决策**：审查 pool 层的 `roadmap/rfc`、`state/blocked` 决策，可覆盖纠正
- **确认未 reviewed 的 issue**：所有无 `roadmap-reviewed` 标签的 issue 都需要审查
- **治理漏网检查**：检测有 assignee 但缺 state 标签的 issue（隐含 rfc）、state/done 但未自动关闭的 issue
- 判断 issue 属于哪个版本窗口或是否暂缓
- 判断 issue 属于哪个版本窗口或是否暂缓
- 为有效 issue 设定规划层 metadata：milestone、`roadmap/*`、必要时的 `priority/[0-9]`
- 管理版本目标与版本窗口边界
- 输出规划层候选集，供后续执行 skill 使用
- **审查完打 `roadmap-reviewed` 标签，结果写入 memory.md**

intake gate 约束：

- 不是所有 `GitHub issue` 都自动进入 GitHub Project。
- 只有经过 `vibe-roadmap` triage 的候选 `GitHub issue`，才应纳入 roadmap 规划。
- `vibe-roadmap` 消费的是 GitHub issue intake 视图，而不是本地长期 issue cache / registry。
- intake 视图应来自运行时查询与 flow/status 总览对比。
- 若未来需要留痕，优先保存 triage 决策快照，而不是复制 issue 整池真源。

对象约束：

- `GitHub issue`: 需求来源
- `vibe-roadmap` 只处理规划元数据，不负责 execution record
- 任何规划判断都必须先读 GitHub 与 shell 输出，再做编排

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`
> 标签定义参考见 `docs/standards/github-labels-reference.md`
> Roadmap 管理指南见 `docs/standards/roadmap-label-management.md`

**Announce at start:** "我正在使用 /vibe-roadmap 技能来管理版本路线图。"

**命令自检:** 对 `vibe3 task status`、`gh issue list`、`gh issue edit` 等参数、子命令或 flag 有任何不确定时，先运行 `--help`。shell 命令是 agent 的工具入口，不是面向用户的命令教学清单。

## Command Pitfalls

### `gh issue list --json comments` 行为差异

**问题**: 不同 `gh` 版本中，`gh issue list --json comments` 的 `comments` 字段行为不一致：
- 某些版本：返回 comment 对象数组，可用 `.[].comments[].body` 提取内容
- 其他版本：返回整数（评论数），上述 jq 表达式会失败

**推荐模式**:
```bash
# 1. 用 gh issue list 获取 issue 编号/标题（不含评论内容）
gh issue list --json number,title --limit 50

# 2. 需要评论内容时，对每个 issue 单独调用 gh issue view
gh issue view <number> --json comments --jq '.comments[].body'
```

**示例**: 本文件的 Step 0 已采用此模式（见下方"方式 B"），避免依赖 `list --json comments` 的版本特定行为。

## Trigger Examples

- `vibe roadmap`
- `/vibe-roadmap`
- `/roadmap`
- `版本规划`
- `下一个版本做什么`
- `管理许愿池`
- `版本目标`
- `issue 标签管理`
- `设置 issue 优先级`
- `分配 milestone`

## Hard Boundary

- 只负责规划层调度，不负责 `GitHub issue` 创建、flow 注册修复或 runtime 修复
- 必须先运行 `vibe3 task status` / `gh issue list` 等命令理解当前版本与候选池
- 不得直接修改 `.git/vibe3/handoff.db` 底层数据
- 远端写操作优先通过 `gh` / GitHub 原生命令完成
- 只有涉及本地 flow 绑定时才使用 `vibe3 flow bind`
- 调度器无法判断优先级时，必须要求人类讨论
- 若涉及主 issue / sub-issue，vibe-roadmap 可以作为 decider 决定拆分或不拆分；只有无法判断拆分形态时才标记 `roadmap/rfc`
- 所有 roadmap 管理通过 GitHub issue labels 触发，不在本地实现数据存储
- 不负责根据当前 active / ready / blocked 现场判断”现在下一个该做谁”；这是 `vibe-orchestra` 的职责

## 配置读取

Roadmap skill 必须读取以下配置：

**Manager Usernames 配置**：
- 文件：`config/v3/settings.yaml`
- 字段：`manager_usernames`
- 用途：确定自动分配的目标 assignee

读取方式：
```bash
# 查看配置（未来可使用 vibe3 config show）
cat config/v3/settings.yaml | grep manager_usernames

# 或使用 Python 加载并获取第一个 manager bot 名称
uv run python -c "
import yaml
from pathlib import Path
config_path = Path('config/v3/settings.yaml')
config = yaml.safe_load(open(config_path)) if config_path.exists() else {}
usernames = config.get('orchestra', {}).get('manager_usernames', ['vibe-manager-agent'])
print(usernames[0] if usernames else 'vibe-manager-agent')
"
```

默认行为：
- 若配置文件不存在或字段缺失，使用默认值 `["vibe-manager-agent"]`（本机 `~/.vibe/settings.yaml` 可覆盖）
- 只使用配置中的第一个 manager username

边界对照：

- `GitHub issue` intake、模板补全、查重：交给 `vibe-issue`
- `task <-> flow` 映射核对与修复：交给 `vibe-task`
- `task <-> flow` / worktree runtime 修复：交给 `vibe-check`
- 基于当前运行现场寻找下一个值得处理的 issue：交给 `vibe-orchestra`
- parent issue / sub-issue 的范围判断：`vibe-issue` 可在 intake 时创建结构，`vibe-roadmap` 可在规划时决定拆分或继续单 issue

## Intake Gate 机制

**三级审查框架详见 [supervisor/roadmap-common.md](../../supervisor/roadmap-common.md#三级审查框架)**。

### 决策逻辑（决策矩阵）

vibe-roadmap 作为 decider，对 governance observer 层的输出执行**强制决策**，不再只写建议。scope 过大时优先自己判断是否拆分；拆分不会改变主 issue 的治理真源，只是把独立执行环节显式化。

| governance observer 输出 | vibe-roadmap decision | 执行动作 |
|---|---|---|
| `[governance suggest] needs split` | `[roadmap decision] split` 或 `[roadmap decision] continue` | 能拆就拆；判断单 issue 足够清晰则继续规划 |
| `[governance suggest] Recommend Close` | `[roadmap decision] close` | 写 comment 说明关闭理由；建议人类关闭（不自动关闭） |
| `[governance suggest] Skipped (needs human)` | `[roadmap decision] rfc` 或 `[roadmap decision] continue` | 只有无法判断目标或拆分形态时标记 `roadmap/rfc`；能判断则继续 |
| `[governance suggest] waiting on #X` | `[roadmap decision] hold until #X` 或调整 milestone | 校验依赖图无循环 → 写 decision |

**决策原则**：
- 每个 suggest 必须产生一个对应的 decision
- decision 优先于 suggest（decider 覆盖 observer）
- 无法判断 scope、目标或拆分形态时，标记为 `[roadmap decision] rfc` 并添加 `roadmap/rfc`

## Assignee 自动分配

### 配置来源

Manager assignee 配置位于：
- **配置文件**：`config/v3/settings.yaml`
- **配置字段**：`manager_usernames`
- **默认值**：`["vibe-manager-agent"]`

### 分配规则（强制）

**自动化路径**：
- 通过三级审查 → 分配给 `{manager_bot}`（从 `config.manager_usernames[0]` 解析）
- 利用 manager dispatch 机制 → 自动触发执行

**使用规则**：
- ✅ 必须使用配置中的 manager_usernames
- ✅ 默认使用配置中 `manager_usernames[0]`
- ❌ 禁止使用人类用户名（如 jacobcy、alice）
- ❌ 禁止使用示例中的 placeholder（如 @alice）

### 触发机制

1. Issue 通过三级审查
2. Roadmap skill 分配 assignee（两步骤）：
   - 读取配置获取 manager bot 名称：`uv run python -c "..."`
   - 执行分配：`gh issue edit <number> --assignee <manager_bot_name>`
3. Manager dispatch 检测到 issue 分配给 manager_usernames
4. Manager 自动启动执行链

### 人机协作路径

**要求人类讨论**（decider 无法判断）：
- 目标、架构方向或拆分形态无法由 roadmap decider 判断 → 写 comment 说明原因
- 不分配 assignee
- 标记为 `roadmap/rfc`

**建议关闭**（Level 2/3 不通过）：
- 写 comment 说明关闭原因
- 建议人类关闭 issue

## 人机协作边界

### 明确分工

**Automation Path（自动路径）**：
- Roadmap skill + manager dispatch
- 三级审查通过 → 自动分配 assignee → manager 启动
- 无需人类干预

**Human-Machine Collaboration Path（人机协作路径）**：
- Roadmap skill + human decision gate
- 只有 decider 无法判断目标或拆分形态时才进入 `roadmap/rfc`
- 人类明确方向后再回到 roadmap / manager 自动路径

### 决策逻辑

**优先自动化**（通过三级审查）：
- bug fix：问题明确 + 架构相关 + 未过时
- small feature：方案明确 + 范围小
- refactor：范围明确 + 边界清晰

**要求人类讨论**（decider 无法判断）：
- issue 目标不明确
- 需要架构/产品方向决策
- 范围过大且 decider 无法判断如何拆分

**建议关闭**（Level 2/3 不通过）：
- 依赖已移除
- API 已废弃
- 重复已关闭 issue

### 不要误判为需要人类讨论的情况

- 同一目标下有 2-3 个局部实现路径，但 issue 本身已说明要修什么、验收看什么
- manager 可以先读代码再决定采用哪种小范围实现
- 描述里列了若干候选方案，但这些方案不会改变系统边界，只影响落地细节

## Comment Contract

vibe-roadmap 作为治理-决策双轨中的**决策者**，使用独立的 `[roadmap decision]` marker，与 observer 层的 `[governance suggest]` 严格区分：

- 第一行行首必须是 `[roadmap decision]`（前面只允许空白字符）
- vibe-roadmap **禁止**写 `[governance suggest]` 评论（marker 必须区分 observer / decider）
- 缺失 marker 或使用错误 marker 会被人类指令解析器误读为人类指令
- 详细 marker contract 见下方「Comment Marker Contract」章节

合规示例：
```
[roadmap decision] split epic into #42, #43, #44; reason: scope exceeds single-iteration threshold.
[roadmap decision] continue #78; reason: bounded enough for manager to plan inside one issue.
[roadmap decision] close #99; reason: dependency removed in #123, API deprecated.
[roadmap decision] hold #55 until #56 completes; reason: dependency graph constraint.
[roadmap decision] rfc #77; reason: cannot determine split shape without architecture input.
```

## 基于 Label 的 Roadmap 管理

### 核心标签类型

根据 `docs/standards/github-labels-reference.md`，roadmap 管理主要使用以下标签：

#### Priority 标签 (priority/\*)

| 标签名称         | 描述       | 使用场景                        |
| ---------------- | ---------- | ------------------------------- |
| `priority/[0-9]` | 细粒度顺位 | 同一 roadmap 桶内的前后顺序提示 |

补充说明：

- 新规划建议优先使用 `priority/[0-9]`，默认 `0`，数字越大越靠前。
- legacy `priority/high|medium|low|critical` 仅作为兼容读取输入，不建议作为新规划主路径。

#### Roadmap 状态标签 (roadmap/\*)

| 标签名称         | 描述             | 使用场景           |
| ---------------- | ---------------- | ------------------ |
| `roadmap/p0`     | 当前迭代必须完成 | 阻断性问题         |
| `roadmap/p1`     | 下个迭代优先完成 | 重要功能           |
| `roadmap/p2`     | 有容量时完成     | 一般功能           |
| `roadmap/next`   | 下个迭代规划中   | 待确认的功能       |
| `roadmap/future` | 未来考虑         | 长期规划           |
| `roadmap/rfc`    | RFC/设计阶段     | agent 无法判断目标、架构方向或拆分形态 |

#### 治理闭环标签

**三层标签语义和闭环流程详见 [supervisor/roadmap-common.md](../../supervisor/roadmap-common.md#三标签语义)**。

### Milestone 管理

- Milestone 用于标识版本目标，如 "Phase 1: 基础设施"、"Phase 2: 核心功能" 等
- 每个 issue 可以分配一个 Milestone，表示其所属的版本
- Milestone 与 roadmap 状态标签配合使用

## Workflow

### Step 0: 消化未处理的 governance suggest

> 命令行为注意事项见 [Command Pitfalls](#command-pitfalls)。

每次 `/vibe-roadmap` 被触发，**必做的第一步**：

1. **找到上次决策锚点**：
   ```bash
   # 搜索最近的 [roadmap decision] 评论（跨 issue）
   # 注意：gh search 默认全局搜索，需要加 repo 限定
   REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
   gh search issues "repo:$REPO [roadmap decision]" --match comments --limit 20 --json number,updatedAt --jq 'sort_by(.updatedAt) | reverse | .[0] | {number, updatedAt}'
   ```
   若无历史 `[roadmap decision]` 评论（首次运行），锚点设为 7 天前。

2. **列出锚点之后所有未消化的 `[governance suggest]`（过滤已决策）**：
   ```bash
   # 方式 A: 使用标签过滤（推荐）
   # 搜索带 [governance suggest] 但没有 roadmap-reviewed 标签的 issues
   # 同时排除带 roadmap/rfc 的 issue（rfc 表示需要人类决策，未完成决策）
   REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
   gh search issues "repo:$REPO [governance suggest]" --match comments --limit 50 --json number,labels,title \
     --jq '.[] | select(.labels | map(.name) | index("roadmap-reviewed") | not) | select(.labels | map(.name) | index("roadmap/rfc") | not) | {number, title, has_suggest: true}'
   
   # 方式 B: 时间戳比对（fallback）
   # 若 issue 有 roadmap-reviewed 标签但标签添加时间早于最新 suggest → 仍需处理
   anchor_time=$(date -d '7 days ago' +%Y-%m-%dT%H:%M:%SZ)
   gh search issues '[governance suggest]' --match comments --limit 50 --json number --jq '.[].number' \
     | while read num; do
         last_decision=$(gh issue view $num --json comments --jq '.comments | map(select(.body | startswith("[roadmap decision]"))) | sort_by(.createdAt) | .[-1].createdAt // "1970-01-01"')
         if [[ "$last_decision" < "$anchor_time" ]]; then
           echo "#$num needs new decision"
         fi
       done
   ```
   
   **优先使用方式 A（标签过滤）**，效率更高；方式 B 仅用于验证或 fallback。

3. **按 issue × suggest 类型分组展示**：
   - 格式：`#N: [governance suggest] <type> — <summary>`
   - 类型：`needs split` / `Recommend Close` / `Skipped (needs human)` / `waiting on #X`
   - 时间权重：
     - 7 天内的 suggest → 高优先级
     - 30 天内的 → 正常优先级
     - 30 天外的 → 低优先级（可能已过时）

4. **决策优先级**：
   - 先处理 `[governance suggest] needs split`（拆分或继续，产出最大）
   - 再处理 `[governance suggest] Recommend Close`（清积压）
   - 再处理 `[governance suggest] waiting on #X`（依赖校验）
   - 最后处理 `[governance suggest] Skipped (needs human)`（判断是 `rfc` 还是可继续）

5. **闭环要求**：处理完每个 suggest 后必须：
   - 写 `[roadmap decision]` 评论关闭闭环
   - 如果 decision 不是 `rfc`：**打 `roadmap-reviewed` 标签**：
     ```bash
     gh issue edit <number> --add-label "roadmap-reviewed"
     ```
   - 如果 decision 是 `rfc`：**不打 `roadmap-reviewed`**，保留 `roadmap/rfc` 标签等待人类决策。人类移除 `roadmap/rfc` 后，下次 roadmap 扫描会重新捡起该 issue。

6. **推翻 intake skip 决策的特殊处理**（明示）：

   当审查的 `[governance suggest]` 来自 **roadmap-intake** 层的 skip 决策（issue 带 `orchestra-scanned` 标签且无 assignee），如果你决定**纳入**该 issue（与 intake 的 skip 决定相反），**必须显式执行三步**：

   ```bash
   # 1. 移除 intake 的跳过标记，让该 issue 不再被 intake 自动跳过
   gh issue edit <number> --remove-label "orchestra-scanned"

   # 2. 分配 manager assignee，让 issue 进入 assignee-pool 流转
   gh issue edit <number> --add-assignee <manager_bot_name>

   # 3. 写决策评论并打 roadmap-reviewed
   gh issue comment <number> --body "[roadmap decision] override intake skip: ... <理由>"
   gh issue edit <number> --add-label "roadmap-reviewed"
   ```

   **为什么必须移除 `orchestra-scanned`**：
   - intake 扫描会跳过有 `orchestra-scanned` 的 issue（[`build_broader_repo_entries`](../../src/vibe3/roles/governance_utils.py) 的过滤逻辑）
   - 不移除标签，下次 intake 仍会自动跳过，决策推翻不生效
   - assignee 是流入 pool 的信号；分配 assignee 后 pool 会接手

### Step 0.5: 治理漏网检查

Step 0 处理完 governance suggest 后，检查两类"漏网" issue：

**类型 A：有 assignee 但缺 state 标签（隐含 rfc）**

这些 issue 通过了 intake（有 assignee）但 pool 还没处理（无 state 标签），等于卡在两层之间。

```bash
# 搜索有 assignee 但无 state/* 标签的 open issues
gh issue list --assignee vibe-manager-agent --limit 50 --json number,title,labels \
  --jq '.[] | select(.state == "OPEN") | select([.labels[].name] | map(select(startswith("state/"))) | length == 0) | {number, title}'
```

对每个漏网 issue 判断：
- **应执行**（范围明确、有 priority、有 roadmap）→ 补 `state/ready`
- **应关闭**（过时、冲突、不适用、无价值）→ 写 `[roadmap decision] close` + 打 `roadmap-reviewed`

**类型 B：state/done 但 issue 仍 OPEN（系统未自动关闭）**

```bash
# 搜索 state/done 但 issue 仍 open
gh issue list --label "state/done" --limit 30 --json number,title,labels \
  --jq '.[] | select(.state == "OPEN") | {number, title}'
```

对每个漏网 issue：
1. 检查是否有关联 PR 且已 merged：
   ```bash
   gh pr list --search "issue:<number>" --state merged --json number,state,mergedAt
   ```
2. **代码实际验证（强制）**：不是只看 PR 状态。必须检查代码实际：
   - PR merged → 检查目标文件/模块是否确实包含了 issue 要求的改动
   - 无 PR → 检查代码库中是否已经以其他方式完成了改动（`git log --grep`、`inspect files`）
   ```bash
   git log --oneline -10 --all --grep="<issue 关键词>"
   uv run python src/vibe3/cli.py inspect files <相关路径>
   ```
3. **完成了**（代码实际包含改动）→ 关闭 issue，comment 说明关闭原因和代码证据
4. **没完成**（代码中无对应改动）→ 关闭当前 issue（已过时或范围不清）+ 创建新 issue（范围更明确，引用原 issue）

**关键原则**：roadmap 处理的都是"悬浮状态"——issue 标签和代码实际脱节。不能用形式审查（看标签、看 PR 状态）代替实质判断（看代码）。必须确认改动是否真实存在于代码库中。

处理完所有漏网 issue 后，打 `roadmap-reviewed`，写入 memory.md 缓存。

---

### Step 1: 检查版本目标

先运行获取当前版本目标状态；必要时再补充文本输出：

```bash
# 查看当前 flow / issue 总览
vibe3 task status

# 查看开放的 issues
gh issue list

# 查看带有特定标签的 issues
gh issue list -l "priority/5"
gh issue list -l "roadmap/p0"
```

获取：

- 当前版本目标是什么
- 有哪些 `GitHub issue` 等待分类
- 各版本窗口下有多少候选 issue
- 现有 issues 的 milestone / roadmap / priority 分布

### Step 2: 版本规划决策

根据当前状态做出决策：

**场景 A: 没有版本目标**

- 提示用户定义版本目标
- 展示许愿池中的 `GitHub issue` 供选择
- 要求人类讨论确定目标

**场景 B: 有版本目标但有新 `GitHub issue`**

- 对新的 `GitHub issue` 进行分类：
- **Epic 检查**（结构分流）：
  - 如果 issue 有 `roadmap/epic` 标签且 body 包含 `## Sub-issues` section：
    - 将主 issue 视为治理容器，优先规划未完成 sub-issues
    - 如果所有 sub-issues 已完成，写 closure/summary decision
    - 如果 sub-issues 不完整，补齐或调整拆分；不要把 epic 本身当成失败状态
- 1.  分配适当的 Milestone
- 2.  添加 roadmap 状态标签（`roadmap/p0`、`roadmap/p1`、`roadmap/p2` 等）
- 3.  必要时补 `priority/[0-9]` 作为同一 roadmap 桶内的细粒度顺位提示
- 对候选 `GitHub issue` 做 intake gate 判断：纳入 / 不纳入 / 待讨论
- 输出版本窗口内的候选集合，但不根据当前 runtime 现场判断“现在该做谁”
- 若该 issue 来自已有治理母题，先读取上游 skill/workflow 的范围判断：
  - 仍在原主 issue 范围内，可继续按 sub-issue 进入规划
  - 已超出原范围，要求拆成新的独立 issue，再决定归类

**场景 C: 版本结束**

- 确认下一版本目标
- 重新评估待分类 Issue
- 更新 roadmap 状态标签

### Step 2.5: Scope 拆分决策

在版本规划决策过程中，roadmap decider 必须在三种结果里选择一个：拆分、继续单 issue、或标记 `roadmap/rfc`。拆分本身不是破坏性动作：主 issue 保持为治理容器，sub-issues 只是独立执行环节。

**Epic 候选识别条件**（满足任一即触发）：
- Issue body 中已有 `## Sub-issues` section（人工预标注）
- Scope estimate 超阈值（涉及 3+ 模块、预估 >1 迭代窗口）
- 已被 `[governance suggest] needs split` 标记

**拆分动作**：
1. 主 issue 加 `roadmap/epic` 标签：
   ```bash
   gh issue edit <epic-number> --add-label "roadmap/epic"
   ```
2. 主 issue 通常不分配 `vibe-manager-agent` assignee；由具体 sub-issues 进入 manager pool
3. 调用 `/vibe-issue` 创建 sub-issues（每个 sub-issue body 中包含 `## Parent issue\n- #<epic-number>`）
4. 在主 issue body 中追加或更新 `## Sub-issues` 清单：
   ```markdown
   ## Sub-issues
   - [ ] #<sub1> — <简短描述>
   - [ ] #<sub2> — <简短描述>
   ```
   注：格式与 `skills/vibe-issue/SKILL.md` 标准对齐
5. 在 sub-issues 之间用 `## Dependencies` 建立顺序（见依赖图编排章节）
6. 写 `[roadmap decision]` comment：
   ```bash
   gh issue comment <epic-number> --body "[roadmap decision] split epic into #<sub1>, #<sub2>, #<sub3>; reason: <拆分理由>"
   ```

**阈值参考**：
- 涉及 1 个模块、≤200 LOC → single issue，不拆分
- 涉及 2 个模块、200-500 LOC → 视耦合度决定
- 涉及 3+ 模块、>500 LOC → 优先拆分；如果无法判断拆分边界，标记 `roadmap/rfc`

### Step X: Intake 判断（新增）

**场景 A: 适合自动化推进**
- 检查：运行三级审查（Level 1/2/3）
- 决策：通过全部三级审查
- 执行动作：
  1. 分配 assignee（两步骤）：
     - 读取配置：`uv run python -c "..."`
     - 执行分配：`gh issue edit <number> --add-assignee <manager_bot_name>`
  2. 写 intake comment：
     ```bash
     gh issue comment <number> --body "[roadmap decision] assign to @{manager_bot} (manager-pool); scope=bugfix."
     # scope 可选值：bugfix, feature, refactor
     ```
  3. **打 `roadmap-reviewed` 标签**（标记已决策）：
     ```bash
     gh issue edit <number> --add-label "roadmap-reviewed"
     ```

**场景 B: 需要人类讨论**
- 检查：目标不明确、架构方向需要人类判断，或 scope 过大但无法判断拆分形态
- 决策：标记 RFC
- 执行动作：
  1. 写 comment 说明原因：
     ```bash
     gh issue comment <number> --body "[roadmap decision] rfc: needs human scope confirmation before automation. Reason: <具体原因>."
     ```
  2. 不分配 assignee
  3. 标记为待讨论：
     ```bash
     gh issue edit <number> --add-label "roadmap/rfc"
     ```
  4. **不打 `roadmap-reviewed`**：rfc 表示未完成决策，只有人类移除 `roadmap/rfc` 后，下次 roadmap 才会重新审查并打 `roadmap-reviewed`。

**场景 C: 建议关闭**
- 检查：Level 2 或 Level 3 不通过（依赖已移除、API 已废弃、重复）
- 决策：建议人类关闭
- 执行动作：
  1. 写 comment 说明关闭原因：
     ```bash
     gh issue comment <number> --body "[roadmap decision] close: dependency removed in #<PR>, API deprecated, duplicate of #<issue>."
     ```
  2. 建议人类关闭 issue（不自动关闭）
  3. **打 `roadmap-reviewed` 标签**（标记已决策）：
     ```bash
     gh issue edit <number> --add-label "roadmap-reviewed"
     ```

### Step 3: 应用标签和 Milestone

使用 GitHub CLI 为 issues 添加标签和 Milestone：

```bash
# 分配 Milestone
gh issue edit <issue_number> --milestone "Phase 1: 基础设施"

# 添加 roadmap 状态标签
gh issue edit <issue_number> --add-label "roadmap/p0"

# 添加细粒度 priority 标签
gh issue edit <issue_number> --add-label "priority/5"

# 同时添加多个标签
gh issue edit <issue_number> --milestone "Phase 1: 基础设施" --add-label "roadmap/p0" --add-label "priority/5"
```

详细操作指南见 `docs/standards/roadmap-label-management.md`。

### 依赖图编排

milestone 分配时必须校验依赖图：

**真源读取**：
- 读取 issue body 中的 `## Dependencies` section（主真源，远端可读）
- 读取本地 SQLite `flow_issue_links` 表（`issue_role='dependency'`）（补充真源，执行现场）
- 注：`flow_issue_links` 是本地数据库表，不是 GitHub 功能

**校验规则**：
1. **无循环检测**：从当前 issue 出发 DFS 遍历 `## Dependencies`，确认无环
2. **倒序分配**：被依赖的 issue **必须**进入更早或同一 milestone
   - 不允许被依赖 issue 进入更晚 milestone
   - 若违反，调整被依赖 issue 的 milestone 到较早窗口
3. **同 milestone 优先级**：同一 milestone 内，被依赖的 issue 应给更高 `priority/[0-9]`

**操作示例**：
```bash
# 校验 #42 的依赖 #40 是否在更早 milestone
gh issue view 40 --json milestone,labels

# 若 #40 milestone 晚于 #42，调整 #40
gh issue edit 40 --milestone "<earlier-milestone>"

# 同 milestone 内提高被依赖 issue 优先级
gh issue edit 40 --add-label "priority/8"
```

**冲突处理**：
- 若依赖图检测到循环 → 写 `[roadmap decision] cycle detected: #A → #B → #A; requires human resolution`
- 若被依赖 issue 已 closed → 写 `[roadmap decision] dependency #X is closed; unblocking #Y`

### Step 4: 输出状态

输出当前路线图状态：

```text
## 当前版本: Phase 1: 基础设施

### P0 (紧急)
- #36: GitHub Projects 整合 [priority/8, roadmap/p0]

### 当前版本
- #34: Issue 同步 [priority/5, roadmap/p1]
- #35: save 自动关联 [priority/5, roadmap/p1]

### 下一个版本
- #37: 智能调度 [priority/3, roadmap/p2]

### 延期
- #38: 性能优化 [priority/0, roadmap/future]
```

### Step 5: 响应 vibe-new 调用

当 `/vibe-new` 触发时：

- 检查是否有版本目标
- 无目标 → 要求人类讨论确定
- 有目标 → 提示当前规划窗口有哪些候选 issue 可继续进入执行现场
- 是否此刻就开始处理、在多个候选里当前先做哪个，由 `vibe-orchestra` 或人类结合 runtime 现场决定

### Step 6: 落地规划结果

规划层远端写操作优先直接使用 GitHub / `gh`：

```bash
gh issue edit <issue_number> --add-label "roadmap/p0"
gh issue edit <issue_number> --milestone "Phase 1: 基础设施"
```

如需把某个 issue 进入当前执行现场，再交给 `/vibe-new` 或 `vibe3 flow bind` 处理本地绑定。

## Label 触发机制

所有 roadmap 管理操作通过 GitHub issue labels 触发：

1. **版本规划**: 通过 `milestone` 与 `roadmap/*` 控制
2. **同桶细粒度顺位**: 必要时通过 `priority/[0-9]` 控制
3. **Milestone 分配**: 通过 GitHub Milestone 功能控制
4. **执行状态**: 通过 `state/*` 标签控制（由执行层管理，非 roadmap 职责）

Agent 应通过以下方式使用标签触发机制：

- 定期扫描带有特定标签的 issues
- 为新 issues 分配适当的规划标签
- 当版本窗口变化时更新 milestone / roadmap / priority 元数据
- 不在这里根据当前 active / ready 现场做即时抢占排序

详细触发机制见 `docs/standards/roadmap-label-management.md`。

## Milestone 显示

`vibe3 flow show` 命令会显示当前 flow 绑定 issue 的 Milestone 信息：

- 从 GitHub API 获取 Milestone 数据
- 显示 Milestone 标题、进度和相关 issues
- 提供 Milestone 上下文用于规划决策

## Failure Handling

如果 shell 命令失败：

- 直接展示 CLI 返回的阻塞原因
- 明确告诉用户当前无法进行路线图管理
- 不要自行 fallback 到直接修改数据库

## Comment Marker Contract

**Comment Marker 规范和格式详见 [supervisor/roadmap-common.md](../../supervisor/roadmap-common.md#comment-marker-contract)**。

## Reference Documents

- [docs/standards/github-labels-reference.md](../../docs/standards/github-labels-reference.md) - 完整的标签定义参考
- [docs/standards/roadmap-label-management.md](../../docs/standards/roadmap-label-management.md) - 详细的 roadmap 标签管理指南
- [docs/standards/v3/command-standard.md](../../docs/standards/v3/command-standard.md) - V3 命令标准
- [docs/standards/issue-standard.md](../../docs/standards/issue-standard.md) - Issue 标准

## Terminology Contract

- `版本目标`: 当前版本要完成的目标
- `许愿池`: GitHub issues（需求池）
- `GitHub issue`: 需求来源与讨论入口，不是 execution record
- `Task`: 执行层最小单元，不属于 roadmap 直接管理范围
- `Flow`: task 的运行时容器，不属于 roadmap 直接管理范围
- `priority label`: 细粒度顺位标签，如 `priority/5`
- `roadmap label`: 路线图状态标签，如 `roadmap/p0`
- `Milestone`: 版本目标标识，如 "Phase 1: 基础设施"
