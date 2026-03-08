---
document_type: plan
author: GPT-5 Codex
created: 2026-03-08
status: draft
related_docs:
  - docs/standards/doc-quality-standards.md
  - docs/standards/doc-organization.md
  - .agent/templates/prd.md
  - .agent/templates/plan.md
  - .agent/templates/task-readme.md
---

# Co-writers Frontmatter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为项目文档 frontmatter 增加可选 `co_writers` 字段，并同步更新受影响模板，避免后续协作时为保留多 Agent 署名而反复改写 `author`。

**Architecture:** 保持 `author` 为唯一主责作者，新增 `co_writers` 作为可选协作者列表，只扩展文档元数据规范，不改变现有文档类型或状态模型。实现分两层：先更新 `doc-quality-standards.md` 中的通用字段定义与示例，再同步 `.agent/templates/` 中需要 frontmatter 的模板。

**Tech Stack:** Markdown, YAML frontmatter, 项目文档标准

---

## Goal
- 为 frontmatter 增加一个稳定、可扩展的协作署名字段
- 明确 `author` 与 `co_writers` 的职责边界
- 让新模板默认支持多 Agent / 人类协作署名

## Non-goals
- 不回溯批量修正历史文档
- 不修改 `skills/` 下的 skill frontmatter 规范
- 不引入 `last_editor`、`contributors`、`reviewers` 等新元数据

## Context To Read
- `docs/standards/doc-quality-standards.md`
  现有 frontmatter 真源，需扩展通用字段与示例
- `docs/standards/doc-organization.md`
  检查是否有模板或 frontmatter 写法引用
- `.agent/templates/prd.md`
  用户已点名的模板入口
- `.agent/templates/plan.md`
  执行计划模板，通常也需要署名能力
- `.agent/templates/task-readme.md`
  任务入口文档模板，若保留 frontmatter，也应对齐
- 其他带 frontmatter 的 `.agent/templates/*.md`
  仅更新当前已使用统一 frontmatter 的模板，不扩展到纯占位旧模板

## Design Decision
- 字段名使用 `co_writers`
- 类型为 `array[string]`
- 可选字段，默认可省略
- 语义定义：
  - `author`：首位创建者或当前文档主责作者，保持单值、必填
  - `co_writers`：参与实质撰写且需要保留署名的协作者列表，可包含 AI 或人类身份
- 使用规则：
  - 更新文档时，如主责作者未变化，不应改写 `author`
  - 新协作者需要保留署名时，追加到 `co_writers`
  - 不允许把 `co_writers` 当作 `author` 的替代字段

## Files To Modify
- `docs/standards/doc-quality-standards.md`
- `.agent/templates/prd.md`
- `.agent/templates/plan.md`
- `.agent/templates/task-readme.md`
- 视内容需要再评估：
  - `.agent/templates/tech-spec.md`
  - `.agent/templates/test.md`
  - `.agent/templates/code.md`
  - `.agent/templates/audit.md`

## Tasks

### Task 1: 扩展文档标准真源

**Files:**
- Modify: `docs/standards/doc-quality-standards.md`

**Steps:**
1. 在通用字段表中新增 `co_writers` 行，标记为可选数组字段。
2. 在字段说明中定义 `author` 与 `co_writers` 的职责边界。
3. 在至少一个完整示例中加入 `co_writers` 用法。
4. 在检查清单或写作建议中补一句“新增协作者时优先追加 `co_writers`，不要无故改写 `author`”。

**Run:**
- `rg -n "co_writers|author" docs/standards/doc-quality-standards.md`

**Expected:**
- 标准文档同时定义 `author` 和可选 `co_writers`

### Task 2: 同步模板 frontmatter

**Files:**
- Modify: `.agent/templates/prd.md`
- Modify: `.agent/templates/plan.md`
- Modify: `.agent/templates/task-readme.md`
- Optional review: `.agent/templates/tech-spec.md`, `.agent/templates/test.md`, `.agent/templates/code.md`, `.agent/templates/audit.md`

**Steps:**
1. 找出当前已经使用 YAML frontmatter 的模板。
2. 为这些模板加入可选 `co_writers` 占位示例，格式保持一致。
3. 不为当前没有 frontmatter 的旧模板额外发明一整套新头部，除非本次也要正式纳入标准。

**Run:**
- `for f in .agent/templates/*.md; do echo '---' $f; sed -n '1,20p' "$f"; done`

**Expected:**
- 受支持模板都能示范 `author + co_writers`

### Task 3: 验证文档一致性

**Files:**
- Review: `docs/standards/doc-quality-standards.md`
- Review: `.agent/templates/*.md`

**Steps:**
1. 检查新增字段名称在所有修改文件中一致为 `co_writers`。
2. 检查没有出现单数 `co_writer`、`co-author` 或其他别名。
3. 检查模板中的示例作者身份与当前标准一致。

**Run:**
- `rg -n "co_writers|co_writer|co-author|coauthor" docs .agent/templates -g '*.md'`

**Expected:**
- 只有 `co_writers` 被使用

## Test Commands
- `rg -n "co_writers|author" docs/standards/doc-quality-standards.md .agent/templates -g '*.md'`
- `rg -n "co_writer|co-author|coauthor" docs .agent/templates -g '*.md'`

## Expected Result
- `doc-quality-standards.md` 正式支持可选 `co_writers`
- 相关模板默认展示 `author` 与可选 `co_writers` 的写法
- 后续多 Agent 协作时不需要为保留历史署名而改写 `author`

## Change Summary
- 预计修改 4-7 个 Markdown 文件
- 预计新增/修改 30-70 行
- 不涉及 Shell、测试代码或运行时逻辑
