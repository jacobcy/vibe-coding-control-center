# Vibe Skills 规范标准 (SKILL_STANDARD.md)

所有技能必须遵循统一的 Vibe Skills 治理体系标准。

## 1. 文件结构
```
skills/<name>/
  SKILL.md          # 技能定义（必须）
  README.md         # 使用说明（可选）
  examples/         # 示例（可选）
```

## 2. SKILL.md Frontmatter 必须包含

在文件顶部的 YAML frontmatter 区域，必须提供以下元数据：

```yaml
---
name: <skill-name>
description: <one-line description>
category: process | guardian | audit
trigger: manual | auto | mixed
enforcement: hard | tiered | advisory
phase: exploration | convergence | both
---
```

## 3. 必须包含的章节

每个 `SKILL.md` 必须包含以下 Markdown 标题和内容：

- **System Role**: 技能人格和需要绝对遵守的硬规则
- **Overview**: 用一段话清晰描述该技能的核心目的
- **When to Use**: 触发条件列表（何时该用此技能）
- **Execution Steps**: 具体的执行步骤指南
- **Output Format**: 输出的格式模板（如合规报告模板）
- **What This Skill Does NOT Do**: 边界声明（明确不做的事情，防止范围蔓延）

## 4. Skills 清单与职责边界

### 4.1 核心 Skills

| Skill | 职责 | 使用命令 | 检查范围 |
|-------|------|---------|---------|
| **vibe-check** | 验证 memory 一致性 | `vibe check` | `.agent/` + `.git/` |
| **vibe-commit** | 生成 git commit | `git commit` | 本地代码 |
| **vibe-review-code** | 代码质量审查 | `vibe flow review` | PR 代码 |
| **vibe-review-docs** | 文档概念审查 | `vibe flow review` | 入口文件 + docs/ |
| **vibe-done** | 任务收口 | `vibe flow done` | Worktree 清理 |
| **vibe-save** | 保存会话上下文 | `vibe task update` | `.agent/context/` |
| **vibe-continue** | 恢复会话上下文 | Read tools | `.agent/context/` |
| **vibe-task** | 任务概览 | `vibe task list` | Registry |

### 4.2 流程 Skills

| Skill | 职责 | 触发时机 |
|-------|------|---------|
| **vibe-orchestrator** | Vibe Guard 总编排 | 开发任务入口 |
| **vibe-scope-gate** | 范围检查 | Gate 1 |
| **vibe-boundary-check** | 边界指标检查 | Gate 6 |
| **vibe-rules-enforcer** | 合规检查 | Gate 6 |
| **vibe-test-runner** | 自动测试 | Gate 4 |

### 4.3 Shell/Skill 职责划分原则

**Tier 1 (物理层 - Shell 命令)**:
- ✅ 执行具体操作（git, gh, jq, 读写文件）
- ✅ 修改数据结构（`.git/vibe/*.json`）
- ✅ 提供稳定的 API 接口

**Tier 2 (认知层 - Skills)**:
- ✅ 智能判断和交互编排
- ✅ 调用 Shell API 执行操作
- ✅ 提供流程控制和用户体验

**禁止越界**:
- ❌ Skills 不得直接修改 `.git/vibe/*.json`
- ❌ Skills 不得实现复杂的数据处理逻辑
- ❌ Skills 不得绕过 Shell API 直接操作数据

## 5. 标准 Shell 命令映射

Skills 必须使用以下标准命令，不得自行实现等价功能：

| 场景 | 命令 | 说明 |
|------|------|------|
| 检查 memory 一致性 | `vibe check` | 物理层审计 |
| 检查 PR 状态 | `vibe flow review` | PR 审计 |
| 查看当前分支 | `vibe flow status` | 当前任务状态 |
| 查看所有分支 | `vibe flow list` | 所有 worktree 状态 |
| 提交 PR | `vibe flow pr` | PR 提交 |
| 清理 worktree | `vibe flow done` | Worktree 清理 |
| 更新任务状态 | `vibe task update` | Registry 更新 |

