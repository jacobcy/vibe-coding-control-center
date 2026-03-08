---
name: vibe-issue
description: 智能 Issue 创建工作流：包括模板校验、查重、Roadmap 检查与智能评论补充。
category: workflow
trigger: manual
phase: both
---

# /vibe-issue - 智能 Issue 助手

该技能负责引导用户创建高质量的 GitHub Issue，并确保其与项目路线图同步。

## 核心原则
- **不重造轮子**：直接调用 `gh` CLI 和 `vibe roadmap` 命令。
- **治理先行**：创建前必先查重，必先匹配模板。
- **自动对齐**：自动将 Issue 映射为 Roadmap Item。

## 使用逻辑

### Step 1: 确定意图与模板
- 用户通过 `/vibe-issue create "<标题>"` 触发。
- Skill 扫描 `.github/ISSUE_TEMPLATE/*.md`。
- 如果没有指定模板，主动询问用户是 Bug 还是 Feature。
- 获取对应模板的 fields。

### Step 2: 智能查重 (Semantic Check)
- 运行 `gh issue list --search "<标题>" --state all --json number,title,state`。
- 分析搜索结果：
  - **高相似度**：展示重复 Issue，建议用户在原 Issue 下评论或合并。
  - **低相似度**：继续创建流程。

### Step 3: Roadmap 检查
- 运行 `vibe roadmap list` 检查是否有类似的心愿。
- 如果 Issue 标题与某个 Roadmap Item 匹配，自动记录其 ID。

### Step 4: 填充与润饰
- 引导用户补充模板中缺失的关键信息。
- 基于 AI 建议合适的 Labels (例如 `bug`, `enhancement`, `vibe-task`)。

### Step 5: 提交与收口
- 执行 `gh issue create --title "<标题>" --body "<润色后的内容>" --label "<labels>"`。
- 创建成功后，如果它不在 Roadmap 中，询问用户或自动执行 `vibe roadmap sync`。
- 输出成功提示及 Issue 链接。

## Failure Handling
- 若 `gh` 未登录：提示用户进行授权。
- 若没有模板文件：使用内置的基础 markdown 结构。
