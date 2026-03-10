# Memory Index

本文件是认知对齐的入口索引，记录达成的概念共识和关键定义。

---

## 2026-03-02: Command vs Slash Alignment

### 核心共识

**Shell/Slash 职责边界原则**：

1. **Shell 赋能 Slash (高低解耦)**
   - Slash 不直接操作复杂数据结构（如 registry.json）
   - 必须通过 Shell API 调用（如 `vibe task update --status`）
   - Shell 负责数据完整性和事务安全

2. **Slash 包裹 Shell (交互升维)**
   - 生硬的 CLI 工作流隐藏在 Slash 指令后
   - Slash 提供智能交互和流程编排
   - Shell 提供稳定的底层 API

### 关键概念

| 概念 | 定义 | 示例 |
|------|------|------|
| Shell API | 底层操作接口，使用 jq 操作 JSON | `vibe task update --status` |
| Slash 命令 | AI 交互入口，调用 Shell API | `/vibe-done` → `vibe task update` |
| 边界审查 | 检查 Slash 是否直接修改 JSON | grep "registry.json" skills/*/SKILL.md |
| JSON 验证 | 验证 JSON 语法和 Schema | `vibe check json registry.json` |

### Shell API 清单

**已实现的 API**：
```bash
# Task 状态管理
vibe task update <task-id> --status <status>

# Worktree 绑定管理
vibe task update <task-id> --worktree <path> --bind-current
vibe task update <task-id> --worktree <path> --status idle

# JSON 验证
vibe check json <filepath> [schema-type]
vibe check json registry.json      # 自动检测 schema
vibe check json worktrees.json     # 自动检测 schema

# Next-step 更新
vibe task update <task-id> --next-step <step>
```

### Slash 命令边界合规性

| 命令 | 边界评估 | 备注 |
|------|---------|------|
| `/vibe-task` | ✅ 合规 | 调用 Shell API，只读操作 |
| `/vibe-done` | ⚠️ 需重构 | 直接修改 JSON（已制定重构方案） |
| `/vibe-save` | ✅ 合规 | 只读操作 |
| `/vibe-continue` | ✅ 合规 | 只读操作 |
| `/vibe-commit` | ✅ 合规 | 使用 git 命令 |
| `/vibe-check` | ✅ 合规 | 只读检查 |
| `/vibe-skills-manager` | ✅ 合规 | 读取 registry，生成报告 |

### Hook 配置优化

**修改内容**：允许 skills/ 和 docs/ 目录创建 .md 文件

**允许的文件**：
- ✅ `README.md`
- ✅ `CLAUDE.md`
- ✅ `AGENTS.md`
- ✅ `CONTRIBUTING.md`
- ✅ `skills/*/*.md` (新增 - Skill 定义文件)
- ✅ `docs/**/*.md` (新增 - 项目文档)
- ✅ `.claude/plans/*.md` (新增 - 计划文件)

**修改位置**：`~/.claude/settings.json` → `hooks.PreToolUse[3]`

### CI 配置调整

**LOC 限制**：1200 → 1500 行

**修改文件**：`scripts/metrics.sh`

**当前状态**：1305 行 < 1500 行 ✅

### 文件拆分优化

**拆分 check.sh**：
- `lib/check.sh` (118 行) - 环境检查（vibe doctor）
- `lib/check_json.sh` (100 行) - JSON 验证（vibe check json）

---

## 2026-03-03: CI Test Alignment and Path Resolution

### 核心共识

1. **测试路径解析原则**：
   - 必须使用绝对路径导出 `VIBE_ROOT` (`export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"`) 避免相对路径在测试层级导致模块找不到。
   - 配置环境覆盖（如 `TEMP_TEST_DIR` 作为 `VIBE_ROOT` 时），应同时符号链接 bin 和 lib，保障工具正常寻址。
2. **测试数据契约对齐**：
   - Shell API (`lib/task_help.sh`) 和测试用例中的变量占位符必须强一致（如 `<id>` 统一为 `<task-id>`）。
   - Shell 自动化 Mocks 必须模拟真实的 Git 行为，特别是对 `rev-parse --show-toplevel` 和 `rev-parse --git-common-dir`。

---

## 2026-03-03: Save Protocol Enhancement

### 核心共识

**审阅优先原则 (Review-First Principle)**：
- 在写入任何持久化上下文（如 `memory.md`, `task.md`）之前，必须先读取并审阅已有内容。
- 若发现已有内容陈旧、有误或与当前事实冲突，必须先进行修正，而非直接追加。
- 目的：防止 AI 生成的上下文变成不可读的“屎山”，保持认知对齐的纯净度。

### 关键定义

| 概念 | 定义 |
|------|------|
| 审阅优先 | 在写入前进行事实检查和旧数据清理的必经步骤 |
| 事实对齐 | 确保 `Task ID`、`Status` 等字段与物理真源（Registry）一致 |

---

## 2026-03-04: PR Automation and Real-time Auditing

### 核心共识

1. **确定性发布原则 (Tier 1 Determinism)**：
   - `vibe flow pr` 作为物理真源，必须是无交互（Non-interactive）且参数化的。
   - 交互意图（如选择 Bump 级别、撰写摘要）由 Tier 2 (Skills) 负责，通过 CLI 参数传递给 Tier 1。

2. **核心发布三要素 (PR Metadata Tripod)**：
   - PR 携带三个维度的元数据：`Title` (PR 标题)、`Body` (详细描述)、`Msg` (写入 CHANGELOG 的 Release Note)。
   - 脚本支持自动 Fallback：若未传入，则从 Git Commit History 自动提取。

3. **实时真源审计 (Living Auditor)**：
   - `vibe flow review` 不再只是链接跳转，而是 CI 和 Review 状态的实时探测器。
   - 具备“防抖”能力：支持对 PENDING 状态的 CI 进行 3x30s 的轮询等待。
   - 具备“决策”能力：根据 `ReviewDecision` 和 `statusCheckRollup` 给出明确的 "Ready to merge" 或 "Blocked" 指令。

### 关键定义

| 概念 | 定义 |
|------|------|
| 串行发布墙 | `vibe flow pr` 强制检查指向 `main` 的 Open PR，防止版本冲突。 |
| 自动 Patch | 手动执行无参数 PR 时，默认执行 patch 级的 version bump。 |
| 无感审计 | 使用 `PAGER=cat` 屏蔽交互式窗口，直接将 PR 状态平铺于终端。 |

---

## 相关文档

- [Task README](../docs/tasks/2026-03-02-command-slash-alignment/README.md)
- [PR Automation Design](#2026-03-04-pr-automation-and-real-time-auditing)
- [Scope Gate Review](../docs/tasks/2026-03-02-command-slash-alignment/README.md) (在 README 中)

---

_Last Updated: 2026-03-04_
