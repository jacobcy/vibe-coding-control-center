# Roadmap List Color Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `vibe roadmap list` 的分组标题增加与 `vibe flow list` 风格一致的状态颜色，同时保持非 TTY 文本输出不变。

**Architecture:** 继续在 `lib/roadmap_query.sh` 内集中处理 roadmap 文本渲染。新增一个“分组标题着色” helper，复用现有 roadmap 配色语义，只作用于 `list` 的组标题层，不改变数据查询或 JSON 输出。

**Tech Stack:** Zsh CLI、`jq`、Bats。

---

### Task 1: 先补分组标题着色测试

**Files:**
- Modify: `tests/test_roadmap.bats`

**Step 1: 写一个交互态颜色测试**

- 追加一个测试，直接 source `lib/roadmap.sh`，并重载 `_vibe_roadmap_supports_color` 让其返回成功。
- 调用 `vibe_roadmap list`，断言输出包含 ANSI 转义和状态标题文本，例如 `P0 (1)`。

**Step 2: 跑定向测试确认先失败**

Run:

```bash
bats tests/test_roadmap.bats --filter 'roadmap list text output'
```

Expected:
- 新颜色断言失败
- 现有非 TTY 文本断言仍通过

**Step 3: 提交前不 commit，继续实现**

---

### Task 2: 实现 roadmap list 分组标题着色

**Files:**
- Modify: `lib/roadmap_query.sh`

**Step 1: 增加分组标题渲染 helper**

- 新增 helper，输入 `status` 和 `count`
- 在支持颜色时输出带颜色的 `Label (count)`
- 在非 TTY 时输出纯文本 `Label (count)`

**Step 2: 在 `_vibe_roadmap_list` 中替换组标题输出**

- 把当前 `printf '%s (%s)\n' ...` 替换为新的 helper
- 保持组顺序、空行、item 行文本完全不变

**Step 3: 避免重复配色逻辑**

- 优先复用 `_vibe_roadmap_format`
- 若需要状态到颜色前缀的映射，提炼为独立 helper，不复制 `flow list` 代码

---

### Task 3: 验证回归

**Files:**
- Verify: `tests/test_roadmap.bats`
- Verify: `lib/roadmap_query.sh`

**Step 1: 跑 roadmap 测试**

Run:

```bash
bats tests/test_roadmap.bats
```

Expected:
- 全部测试通过

**Step 2: 运行真实命令做人工检查**

Run:

```bash
bin/vibe roadmap list
```

Expected:
- 当前终端下分组标题显示颜色
- 文本结构与现在一致

---

### Task 4: 单独提交这个逻辑变更

**Files:**
- Stage only:
  - `lib/roadmap_query.sh`
  - `tests/test_roadmap.bats`
  - `docs/plans/2026-03-09-roadmap-list-color-design.md`
  - `docs/plans/2026-03-09-roadmap-list-color-plan.md`

**Step 1: 检查暂存范围**

Run:

```bash
git status --short
```

Expected:
- 只暂存本次 roadmap list 颜色相关文件

**Step 2: 提交**

Run:

```bash
git commit -m "feat(roadmap): colorize list group headings"
```

Expected:
- 生成单一逻辑提交
