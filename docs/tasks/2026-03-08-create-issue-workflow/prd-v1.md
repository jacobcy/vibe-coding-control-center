---
task_id: 2026-03-08-create-issue-workflow
document_type: task-prd
title: Vibe Issue Workflow Skill - PRD
author: Antigravity
created: 2026-03-08
status: draft
related_docs:
  - docs/tasks/2026-03-08-create-issue-workflow/plan-v1.md
  - SOUL.md
  - CLAUDE.md
---

# PRD: Vibe Issue Workflow Skill

## 1. 业务背景
Vibe Center 旨在作为 AI 开发者的控制中心。GitHub Issue 是需求的主要来源。目前项目虽然有 `vibe-roadmap` 技能，但缺乏一个专门用于“创建和预旋 Issue”的工作流技能。这个技能将确保新提出的需求（Issue）符合规范、不重复、且能正确映射到路线图中。

## 2. 核心目标
创建一个新的 Vibe Skill `vibe-issue`，用于自动化和智能化地处理 Issue 的创建。

## 3. 功能需求

### 3.1 模板校验 (Template Validation)
- 当用户想要创建 Issue 时，技能应识别用户的意图。
- 引导用户填充必要的信息，确保符合 `.github/ISSUE_TEMPLATE/` 中的定义（Bug report, Feature request 等）。
- 校验缺失的关键项并提示补充。

### 3.2 Roadmap 检查 & 智能关联
- 自动检查当前 Issue 与 `Roadmap` 的关系。
- 若 Issue 描述的需求已存在于 Roadmap 中，建议关联。
- 若不存在，建议作为新的 Roadmap Item 加入“许愿池”。

### 3.3 智能查重 & 合并 (Duplicate Detection & Merging)
- 使用智能搜索（基于标题和描述）检索现有的 Open Issues。
- 给出查重置信度。
- 若发现高度重复，建议关闭并重定向到现有 Issue，或者提出合并建议。

### 3.4 评论补偿 & 智能润饰 (Comment Supplement)
- 基于提供的信息，自动建议 Labels。
- 建议 Assignees 或 Milestone。
- 若信息不足，AI 自动生成第一条评论提出具体问题，引导用户/后续 Agent 补充。

## 4. 实现策略
- **Pure Skill Implementation**：该功能完全实现在 Skill 层。
- **直接调度原子工具**：
  - 使用 `gh` CLI 处理所有 GitHub 原生操作（查重、创建、评论）。
  - 使用 `bin/vibe roadmap` 处理所有路线图映射操作。
- **无需新增 Shell 命令**：不修改 `bin/vibe` 或 `lib/`（除了修复已发现的 help 文档 Bug）。

## 5. 验收标准
- [ ] 能够通过 `/vibe-issue create` 启动引导。
- [ ] 能够检测到重复的 Issue 并给出警告。
- [ ] 自动关联 Roadmap Items。
- [ ] 基于模板输出结构化的 Issue 内容。
