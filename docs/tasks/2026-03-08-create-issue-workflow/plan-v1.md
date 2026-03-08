---
document_type: plan
author: Antigravity
created: 2026-03-08
status: draft
related_docs:
  - docs/tasks/2026-03-08-create-issue-workflow/prd-v1.md
---

# Plan: Vibe Issue Workflow (Pure Skill implementation)

## 1. 目标
通过纯 Skill 编排，实现 `vibe-issue` 构建流，直接调用 `gh` 和 `vibe roadmap` 原子命令。

## 2. 任务分解

### Phase 1: 基础环境与规范检查
- [x] **Task 1.1 (Bugfix)**: 修正 `bin/vibe` help 输出，补全 `roadmap` 命令说明。
- [x] **Task 1.2**: 确认 `gh` CLI 工具状态及权限。
- [x] **Task 1.3**: 在 `.github/ISSUE_TEMPLATE/` 补充缺失的 Issue 模板文件。

### Phase 2: Skill 定义 (`skills/vibe-issue/SKILL.md`)
- [x] **Task 2.1**: 定义技能主逻辑：
  - **引导**：匹配 Issue 模板。
  - **查重**：直接执行 `gh issue list --search "..."`。
  - **对齐**：通过 `vibe roadmap list` 检查已存在的心愿。
  - **决策**：根据查重结果，建议用户“创建新项”、“合并到旧项”或“仅添加评论”。

### Phase 3: 工作流集成
- [x] **Task 3.1**: 创建 `.agent/workflows/vibe-issue.md`。
  - 将 `/vibe-issue` 路由到该技能。

## 3. 验证方案
- [ ] 运行 `bin/vibe help`，确认 `roadmap` 出现在列表中。
- [ ] 模拟输入“我想加一个暗黑模式”，确认 Skill 能够通过 `gh` 找到相关的 existing issues (如果有)。
- [ ] 最终成功产出一个关联了 Roadmap Item ID 的真实 GitHub Issue（或模拟输出 `gh` 命令内容）。

## 4. 非目标
- ❌ 不修改 `lib/*.sh` 增加新逻辑。
- ❌ 不在 `bin/vibe` 增加新子命令（除了 help 修复）。
