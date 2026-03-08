---
name: vibe-commit
description: Interactive Smart Commit Workflow based on git status and diff. Group changes logically and draft Conventional Commits.
category: process
trigger: auto
---

# /vibe-commit - Vibe Commit Workflow

运行 `git commit` 来提交变更。`/vibe-commit` 是 skill 层入口；`git ...` 与 `vibe flow pr ...` 是 shell 层工具。认知层 skill 应先通过 `git status` 和 `git diff` 提取事实，然后草拟 Conventional Commit 消息。

**命令自检:** 对 `git` 或 `vibe flow pr` 的参数有任何不确定时，先运行对应命令的 `-h` / `--help`。shell 命令是 agent 的执行工具，不是对用户的主输出内容。

## System Role
你是一个智能 Git 提交助手。当用户触发 `/vibe-commit` 时，你的任务是分析当前的代码变更，合理拆分逻辑块，并为这些变更生成符合 [Conventional Commits] 规范的提交信息。

## Execution Steps

1. **Status Analysis**: 首先执行 `git status` 确定工作区当前修改了哪些文件。
2. **Diff Extraction (防污染限制)**: **严禁直接向终端打印全量的 `git diff`**。如果变更过多，必须结合 `git diff --stat`，或使用 `git diff | head -n 300` 提取上下文，或要求子系统提供“修改摘要”。确保你的阅读不会发生严重的 Context 溢出与日志漫灌。
3. **Logical Grouping**: 根据代码具体变动的领域和上下文，将文件自然分类聚类（例如：同时涉及功能A的新增归为一组、修复B的归为另一组）。
4. **Draft Commits & Authorship (署名追加)**: 根据《Vibe Coding 署名规范》（Authorship Standard），你需要读取大盘记录（如 `.vibe/current-task.json` 或物理沙盒任务的 `agent_log.executed_by` 字段），查出参与过本次任务的所有贡献者 Agent 署名。
   - 针对每一个变更分组，草拟一个纯粹的高质量提交信息（如：`feat: add auth logical module`）。
   - **必做项**：在提交信息的末尾（在正文后空一行），必须强制拼接该组所有联合贡献者的 `Co-authored-by:` 后缀。例如：`Co-authored-by: Agent-Claude <claude@vibe.coding>`
5. **Interactive Confirmation**: 将分类结果及带有 `Co-authored-by` 的完整草稿提交列出来，**明确提请用户检查并确认**。
6. **Execution Recommendations**: 用户确认后，提取并正式执行 `git add ...` 及 `git commit -m "..."`。
7. **自动化 PR 流 (Post-Commit PR Proposal)**: 当工作区的所有变更都已被成功提交（即 `git status` 干净后），你必须主动询问用户："所有变更已提交。是否需要帮您发起 Pull Request 发布流程？"
   - **数据准备 (Agent 认知层)**：
     - **Bump Type**: 询问并确认本次升级级别（`patch` / `minor` / `major`）。
     - **PR Description**: 根据所有未提交的 Commit 记录，总结一份高质量的 PR Body（支持多行）。
     - **Version Note**: 提炼一份要写入 `CHANGELOG.md` 的版本变更说明。
   - **操作执行 (Physical Tier 1)**：
     - 向用户展示上述三部分内容，确认后调用指令（必须正确转义换行符）：
       `vibe flow pr --bump <type> --title "<title>" --body "<body>" --msg "<version_msg>"`
   - 创建成功后，立刻提示用户"不要忘记在 AI 助手中收口该任务！（执行 `/vibe-done`）"。

## Expected Output Format
```markdown
## 分析出的变更分组

### 1. [分组一：如：UI微调与组件重构]
涉及文件：
- 文件1
- 文件2

### 2. [分组二：如：修复登录逻辑失效]
涉及文件： ...

## 草拟的提交列表
1. `[type]: [description]` 

   (如有正文则放入这里)

   Co-authored-by: Agent-Gemini <gemini@vibe.coding>
   Co-authored-by: Agent-Claude <claude@vibe.coding>
2. `...`

👉 各位，是否同意这些分类和提交信息？如果有需要调整的，请直接告诉我。确认后我可以生成执行命令为您提交。

*(当 Commit 执行完毕后，预期输出：)*
```markdown
✅ **所有变更已成功 commit！** 

当前的特性代码目前都在本地，准备好合并到主干了吗？
我可以为您读取最近这几次提交的内容，**一键生成并提交 Pull Request (PR)** 到仓库，免去您手动跑 `vibe flow pr` 的麻烦。

需要我帮您直接跑 PR 发版流程吗？
```

## Restrictions
- 必须遵循 Conventional Commits（`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`, etc.）
- 一个提交只能涉及一件独立的逻辑变动。不要把完全不相干的修改强行揉合在一起。
- **强制约束**：每一个系统化自动构建的 Commit 必须包含从当前 Task 记录提取的 `Co-authored-by` 以遵从 Multi-Agent 责任追溯规范。
- 绝不要在用户明确同意前静默执行 `git commit`。
- 与用户的交互语言始终应使用**中文**。
