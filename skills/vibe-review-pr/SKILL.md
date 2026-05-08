---
name: vibe-review-pr
description: |
  Use only in Claude Code environments with Agent Teams enabled when the user wants
  a comprehensive PR review using the multi-agent team workflow.
---

# Vibe PR Review Skill

`vibe-review-pr` 是 **Claude Code Agent Teams 专用入口**。本文件定义生命周期、执行步骤、phase 契约、审查质量标准与硬边界。消息样例与恢复细节在 `references/`。

非 Claude team 环境（含 Codex）一律分流：docs-only PR → `vibe-review-docs`；其他 → `vibe-review-code`。

## When to Use

仅在以下条件**全部**满足时使用：

- host 为 Claude Code
- `TMUX` 已设置
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- 工具面提供 TeamCreate / Agent / SendMessage / teammate-message

任一缺失 → 立即停止，按文件范围回退到单 agent 审查。

## Must Read

启动前读取：

1. `.claude/team-templates/pr-review-team.yaml`
2. `.claude/agents/pr-*.md`
3. `docs/references/team-guide.md`

需要消息样例或恢复路径时再读 `references/execution-reference.md` / `references/recovery-playbook.md`。

## Session Lifecycle（强制理解，issue #742 反复踩坑）

> **核心误解**：把 Team 当成"PR-级"对象。事实上 Team 是"会话级"对象。

```
环境检查 → TeamCreate（一次） → PR #A → continue → PR #B → ... → end → TeamDelete（一次）
```

| 规则 | 原因 | 易犯错误 |
|------|------|---------|
| 一个会话一个 Team | TeamCreate / TeamDelete 是高代价操作；teammates 状态不应跨 PR 重置 | 每审完一个 PR 就 TeamDelete，下一个又重建 |
| 一个 Team 多个 PR | spawn agent 比 SendMessage 慢 10-100 倍且占资源 | 每个 PR 都重新 spawn `code-analyst` |
| 切换 PR 用 SendMessage | agent 已就绪，只需告诉它"换审 PR #B" | 关闭旧 agent，spawn 新 agent |
| TeamDelete 仅在用户 end | 用户没说结束就保留状态 | 看到"询问是否继续"以为是 TeamDelete 触发点 |

Team 名称固定为 `pr-review-team`（**不要**用 `pr-review-713` 这种 PR-编号命名，会强化错误心智模型）。

## Execution Flow

| Step | 动作 | 关键约束 |
|------|------|---------|
| 1 | 环境检查 | 缺工具 → 立即回退，禁止模拟 |
| 2 | 选执行模式 | `auto-fix / comment-only / auto-decide / ask-each` |
| 3 | PR 选择/排序 | 优先 `state/merge-ready`、改动小、`base==main` |
| 4 | 检查已有审查 | 有人类 / agent 评论时询问是否重审 |
| 5 | 加载 template | 读 `.claude/team-templates/pr-review-team.yaml` |
| 6 | 创建或复用 Team | 已存在且健康 → 复用；不存在 → TeamCreate；状态异常 → 停止由人类处理 |
| 7 | 判断 PR 类型 | 多维判断（见下） |
| 8 | 执行审查 | Phase 1 → 2 → 3 → 4，**严格串行** |
| 9 | 询问继续 | continue → 回 Step 3，**复用** Team；end → Step 10 |
| 10 | TeamDelete | 仅当 Step 9 选 end，整会话最多一次 |

### Step 7: PR 分类（多维判断，禁止简化）

> **常见错误**：看到"文档改动"就归类 `simple`。这是错的。

`simple` 必须**同时**满足全部 4 项：

- ✅ **单文件**改动
- ✅ 改动 **< 30 行**
- ✅ 仅文档 / 注释 / 字符串 / 重命名
- ✅ 无 `security/*` 标签

任一不满足 → 不是 simple。

| 类型 | 触发 | 处理 |
|------|------|------|
| `simple` | 上述 4 项**全**满足 | 仅 Phase 1（team-lead 调用 `vibe-review-docs` 或 `vibe-review-code`） |
| `security` | 涉及认证 / 授权 / 数据 / 凭据 / 输入验证 | Phase 1+2，**必须**含 `security-reviewer` |
| `refactor` | ≥ 5 文件 **或** 大规模重构 | Phase 1+2 |
| `standard` | 不属于上述 | Phase 1+2 |

**反例**（issue #742 真实踩坑）：PR #713 改 6 文件、+11/-10、含 `manager.py` 代码改动 + 文档 → 错误归类 `simple` → 实际应按 `standard` 处理。**只要包含代码改动或多文件，就不是 simple。**

## Phase Contracts

| Phase | 强制要求 | 易错点 |
|-------|---------|-------|
| 1 背景调研 | 必须**先于** Phase 2 完成；产出 `phase_1_output` 并回传 team-lead | 只打印到终端、未保存为变量、未通过 SendMessage 回传 |
| 2 专项审查 | 多 agent **同一响应**内并行 spawn；spawn 后**立即** SendMessage 把 `phase_1_output` 广播给每个 | **与 Phase 1 并行启动**（issue #742 真实踩坑）；忘发背景导致盲审 |
| 2.5 Codex验证（可选） | **触发条件**：安全PR、大型PR（>500行）、冲突仲裁；**执行时机**：Phase 2完成后收集所有报告；通过 `codex:rescue` skill 调用 | 与 Phase 2 并行执行；未收集完整 Phase 2 报告就调用 |
| 3 综合判断 | 检查 `required - received` 缺失；冲突必须仲裁；缺失只能标"审查不完整"；如有 Phase 2.5 报告作为补充材料 | 替缺失 agent 脑补 / 用错误 teammate-message 内容继续 |
| 4 写回 | 模式决定路径；仅 `auto-fix` 可 spawn `pr-fix-executor`；范围外问题转 follow-up issue | 把范围外技术债塞进当前 PR comment |

> **没有 Phase 5**。完成 Phase 4 直接回 Step 9。teammates 的 idle / pane / inbox 由运行时管理，**skill 不感知不操作**。如果你正在思考"清理 inbox"或"保留状态"，停下——这不是你的工作。

详细消息样例见 `references/execution-reference.md`。

## Review Quality Standards（强制，写回前自查）

> **针对 PR #737 暴露的 8 类审查质量问题。每条都有真实踩坑反例。任一条不满足必须先修正再写回 comment。**

### 1. 禁虚假精度评分

LLM 拟合不出小数点评分，强行打分就是幻觉。

- ❌ "代码质量评分：89.75 / 100 (A-)"
- ❌ "架构符合性：A (90)、错误处理：B+ (85)、测试覆盖：A (95)"
- ✅ "APPROVE（已解决 3 项技术债，遗留 2 项次要问题转 follow-up）"

### 2. 强制规则引用

凡是判定为"违规 / 技术债 / 应修复"的条目，必须**引用具体规则来源**。

- ❌ "异常类型不一致（ValueError 应改为 SystemError）"——没有规则依据
- ✅ "`ValueError` 不在 `CLAUDE.md` HARD RULE 13 规定的 `SystemError / UserError / BatchError` 体系内"

合法引用源：`CLAUDE.md` 第 N 条 / `.claude/rules/coding-standards.md § X` / `.claude/rules/python-standards.md` / `docs/standards/error-handling.md` 等。

### 3. 验证再断言（数字基于本 PR 实际 diff）

- ❌ 在不修改 PRService 的 PR 中报告 "PRService at 394/400 maintained"——本 PR 不改它
- ❌ "函数大小超标（68 行，接近 100 行上限）"——project 标准是 < 100 建议，68 行**未超标**
- ✅ "`get_numstat()` 函数体 65 行（含 docstring），Client/Utils 层建议上限 100，未超标"

### 4. 禁滑动靶点（论证只针对本 PR 改动）

- ❌ 本 PR 函数不直接调用 subprocess，却写"无 shell 注入风险：使用 subprocess.run 列表形式"——这是替既有代码做声明
- ✅ "本 PR 新增的 `get_numstat()` 不直接调用 subprocess，通过注入的 `run` callable 委托；底层 `_run` 安全性属于既有代码，不在本次审查范围"

### 5. 禁无关指标

不要把与本 PR 无关的项目级指标作为"verification result"列出。

- ❌ 本 PR 不改 PRService，却列 "PRService at 394/400 maintained" 作为验证结果
- ✅ 仅列**本 PR 改动文件**的真实数据（行数、覆盖率、增删比）

### 6. 强制识别真实重构机会

`code-analyst` 必须做**结构性扫描**，不能只跑样板检查。重点找：重复代码段、冗余防御（discriminated union 之后又做 isinstance）、已有规则在新代码中的违反点。

- ❌ 在 PR #737 中遗漏 BRANCH 与 PR 分支的 `merge_base + 三点 diff` 重复
- ✅ 明确指出"BRANCH 和 PR 两条分支共享同一 `merge_base + 三点 diff` 模式，可提取私有 helper 减少 6 行重复"

### 7. 测试评估看性质而非数量

- ❌ "9 个测试 → 测试覆盖 A (95)"
- ✅ "9 个 MagicMock 单元测试，覆盖 4 种 ChangeSource + 4 种错误分支，但缺乏与真实 GitClient._run 的集成契约测试"

必须区分：单元（mock） / 集成（真实依赖）、happy path / 错误分支。

### 8. comment 格式（写回前最后一道关）

**必须包含**：决策一行（APPROVE / NEEDS_CHANGES / REJECT） / 已解决技术债（带 diff 引用） / 遗留问题（每条带规则引用） / follow-up issue 链接 / 审查依据（引用了哪些规则文档）。

**禁止包含**：

- ❌ 百分制 / 字母评分（除非用户明确要求）
- ❌ "Phase 1 / Phase 2 / Phase 3" 内部流程标题作叙事结构（这是 skill 的执行结构，不是审查报告的叙事结构）
- ❌ 已解决与未解决问题混在一起

## Hard Rules

### Team / Session

- TeamCreate 整会话最多一次；TeamDelete 最多一次（任务结束时）
- 已存在的健康 Team 必须复用，禁止重复 TeamCreate
- 切换 PR 用 SendMessage，禁止重新 spawn agent
- **TeamDelete 合法场景**：
  - ✅ 任务完成时（Step 10）
  - ✅ 状态不一致时先尝试清理（Step 6）
- **清理优先级**：TeamDelete → rm -rf fallback → 退出重建会话
- 当前会话若无法安全复用现有 Team，唯一合法恢复是退出并重建会话

### Phase 流程

- Phase 1 / Phase 2 严格**串行**，禁止并行 spawn
- Phase 2 spawn 后必须 SendMessage 发 `phase_1_output`，禁止盲审
- 仅 `refactor / security / standard` 走双阶段；`simple` 只做 Phase 1

### 状态操作

- 不手工编辑 `~/.claude/projects/.../*.jsonl`
- 不手工 `rm -rf ~/.claude/teams/`
- 不手工 `tmux kill-pane`
- 不发送 teammate shutdown 指令

### 诚信

- teammate-message PR 编号不匹配时必须如实标注，并说明正确报告来源（session 文件路径）
- 缺失报告必须标"审查不完整"，禁止脑补缺失 agent 的同意 / 反对
- 拒绝"已合并 / CI 通过 / 无漏洞"这类无证据声明（按 yaml `anti_hallucination` 提供证据）

## Recovery

按 `references/recovery-playbook.md` 处理，不在主流程临场发明 workaround：

- TeamCreate 与 Agent spawn 状态不一致
- 已有 Team 但需确认是否可复用
- TeamDelete 后 UI 残留
- 部分审查 agent 超时 / 缺失
- 背景报告未送达
- teammate-message PR 编号路由错误（Claude Code 已知 bug #40166 / #39651）

## File Map

| 文件 | 职责 |
|------|------|
| `SKILL.md` | 生命周期、phase 契约、质量标准、硬边界 |
| `references/execution-reference.md` | 消息样例与等待策略 |
| `references/recovery-playbook.md` | 故障恢复路径 |
| `.claude/team-templates/pr-review-team.yaml` | 团队配置真源 |
| `.claude/agents/pr-*.md` | teammate 项目特定职责 |
| `docs/references/team-guide.md` | Team 功能通用背景 |

## Usage

```
/vibe-review-pr 604
```
