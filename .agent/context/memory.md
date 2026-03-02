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
| `/vibe-skills` | ✅ 合规 | 读取 registry，生成报告 |

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

## 相关文档

- [Task README](../docs/tasks/2026-03-02-command-slash-alignment/README.md)
- [Plan v1](../docs/tasks/2026-03-02-command-slash-alignment/plan-v1.md)
- [Scope Gate Review](../docs/tasks/2026-03-02-command-slash-alignment/README.md) (在 README 中)

---

_Last Updated: 2026-03-02_
