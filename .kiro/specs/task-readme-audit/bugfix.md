# Bugfix Requirements Document

## Introduction

Task README 文件中存在状态字段冲突问题，导致任务状态信息混淆和维护困难。具体表现为：frontmatter 中的 `status` 字段与正文中的 `**状态**:` 字段存在语义冲突，造成双头真源问题。这违反了单一真源原则（Single Source of Truth），影响了任务状态的可靠性和可维护性。

根据 2026-03-02 的审计结果，发现多个 Task README 文件存在此问题，其中部分文件的两个状态字段完全不一致（如 frontmatter 显示 `completed` 而正文显示 `In Progress`），导致状态信息严重混淆。

本 bugfix 的目标是修复这些冲突，确保 frontmatter `status` 字段成为唯一真源，并清理或重定向正文中的冗余状态字段。

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN Task README 文件的 frontmatter `status` 字段值为 `completed` 且正文 `**状态**:` 字段值为 `In Progress` THEN 系统存在状态信息冲突，无法确定任务的真实状态

1.2 WHEN Task README 文件同时包含 frontmatter `status` 字段和正文 `**状态**:` 字段且两者值不同 THEN 系统产生双头真源问题，违反单一真源原则

1.3 WHEN 开发者更新 frontmatter `status` 字段但未同步更新正文 `**状态**:` 字段 THEN 系统产生状态不一致，导致信息过时和混淆

1.4 WHEN 正文中存在独立的 `**状态**:` 字段且其值与 frontmatter 重复 THEN 系统存在冗余信息，增加维护负担和出错风险

### Expected Behavior (Correct)

2.1 WHEN Task README 文件需要表达任务状态 THEN 系统 SHALL 仅使用 frontmatter `status` 字段作为唯一真源

2.2 WHEN Task README 文件的正文需要引用任务状态 THEN 系统 SHALL 使用指引文本（如"见 frontmatter `status` 字段"）而非独立的状态值

2.3 WHEN 开发者更新任务状态 THEN 系统 SHALL 仅需更新 frontmatter `status` 字段，无需同步更新其他位置

2.4 WHEN 存在历史遗留的正文状态字段 THEN 系统 SHALL 将其替换为指引文本或完全删除，消除冗余

### Unchanged Behavior (Regression Prevention)

3.1 WHEN Task README 文件的 frontmatter 包含其他元数据字段（如 `task_id`, `title`, `author`, `gates` 等）THEN 系统 SHALL CONTINUE TO 保持这些字段不变

3.2 WHEN Task README 文件的正文包含非状态相关的内容（如概述、文档导航、关键约束等）THEN 系统 SHALL CONTINUE TO 保持这些内容不变

3.3 WHEN Task README 文件已经没有正文状态字段（如 `2026-02-28-vibe-skills/README.md`）THEN 系统 SHALL CONTINUE TO 保持其干净状态不变

3.4 WHEN Task README 文件的 frontmatter `status` 字段使用标准状态枚举值（`todo`, `in_progress`, `completed`, `archived` 等）THEN 系统 SHALL CONTINUE TO 使用这些标准值

3.5 WHEN Task README 文件的 Gate 进展表格显示各个 gate 的状态 THEN 系统 SHALL CONTINUE TO 保持 gate 状态表格不变，因为这些是独立的检查点状态而非任务整体状态
