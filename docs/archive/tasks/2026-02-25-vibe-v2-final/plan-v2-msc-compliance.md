# MSC (Model-Spec-Context) 合规达标计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 使 Vibe Center 2.0 通过 MSC 范式的全部自检项，成为可以指导其他项目的合格样板工程。

**Architecture:** 分四个阶段推进——P0 修复违规，P1 补齐 Spec 落地（最大短板），P2 建立工具级 Context 闭环（Serena + ShellCheck + bats 三位一体），P3 接入 CI/CD 触发和度量。每个阶段独立可验证。

**Tech Stack:** zsh, bats-core, shellcheck, Serena MCP (LSP/AST), GitHub Actions

**当前基线：**
- Shell LOC: 727/1200 (61%) ✅
- 测试用例: 2 个 ❌
- flow.sh: 208 行（超 200 行上限）⚠️
- openspec/specs/: 空 ❌
- ShellCheck 集成: 已安装未集成 ⚠️
- Serena: 已配置 `.serena/project.yml`（bash），未强制使用 ⚠️
- `zsh -n` 语法检查: 全部通过 ✅（但未自动化）
- CI/CD: 无 ❌

**已有工具盘点（"枪已备好"）：**
| 工具 | 状态 | 用途 |
|---|---|---|
| Serena MCP | `.serena/project.yml` 已配置 bash LSP | AST 符号检索、引用查找、死代码检测 |
| ShellCheck v0.11.0 | `/opt/homebrew/bin/shellcheck` 已安装 | Shell 代码质量 lint |
| `zsh -n` | 系统自带 | Zsh 语法验证 |
| bats-core | 已安装，有 2 个基础测试 | Shell 单元测试 |
| OpenSpec | `openspec/` 目录已初始化 | 结构化变更管理 |

**不做的事：**
- 不重构核心业务逻辑
- 不增加新 CLI 功能
- 不改变已有 Skills 的提示词内容
- 不引入新的外部依赖

---

## Phase 0: 修复违规项 (HARD RULES Compliance)

> 优先处理，因为项目自己的 HARD RULES 有一条正在被违反。

### Task 0.1: 修复 flow.sh 超过 200 行上限

**Files:**
- Modify: `lib/flow.sh` (208 → ≤200 行)

**Step 1: 测量当前状态**

Run: `wc -l lib/flow.sh`
Expected: `208 lib/flow.sh` (或 `209 lib/flow.sh`)

**Step 2: 精简 flow.sh 至 ≤200 行**

策略：删除空行、合并短行、精简注释。不改变逻辑。目标压到 195 行左右给后续留余量。

具体可压缩点：
- `_flow_start` 中的 PRD heredoc（~10 行）可压缩为 1 行 `printf`
- `_flow_pr` 中的 body 拼接（~5 行）可合并
- dispatcher 中的 help 文本（~7 行）可压缩格式

**Step 3: 验证**

Run: `wc -l lib/flow.sh`
Expected: ≤200

Run: `bin/vibe flow help`
Expected: 正常输出帮助文本

Run: `bats tests/test_basic.bats`
Expected: 2 tests, 0 failures

**Step 4: Commit**

```bash
git add lib/flow.sh
git commit -m "fix: slim flow.sh to comply with 200-line file limit"
```

---

## Phase 1: Spec 层达标 (Contract-First)

### Task 1.1: 为 CLI 命令创建结构化 Spec

**Files:**
- Create: `openspec/specs/cli-commands.yaml`

**Step 1: 编写 CLI 命令 Spec**

从 `bin/vibe` 和 CLAUDE.md 提取所有命令签名，写入 YAML 格式的结构化定义。
包含：命令名、子命令、参数（名称、类型、是否必须）、返回值、示例。

覆盖以下命令：
- `vibe check`
- `vibe flow <start|review|pr|done|status|sync>`
- `vibe keys <list|set|get|init>`
- `vibe tool`
- `vibe clean`

**Step 2: 验证 Spec 格式可读**

Run: `cat openspec/specs/cli-commands.yaml | head -30`
Expected: 格式良好的 YAML

**Step 3: Commit**

```bash
git add openspec/specs/cli-commands.yaml
git commit -m "docs: add structured CLI command spec"
```

### Task 1.2: 补充 bats-core 测试至 ≥20 个用例

**Files:**
- Modify: `tests/test_basic.bats` (保留已有的 2 个，重命名为 test_vibe.bats)
- Create: `tests/test_flow.bats`
- Create: `tests/test_keys.bats`
- Create: `tests/test_utils.bats`

**Step 1: 扩展基础测试 (test_vibe.bats)**

新增用例覆盖 `bin/vibe` dispatcher：
- `vibe help` 输出包含 "Usage"
- `vibe check` 返回 0
- `vibe` 无参数时返回帮助信息
- 无效子命令返回错误
- `VIBE_ROOT` 环境变量正确设置

**Step 2: 创建 flow 测试 (test_flow.bats)**

新增用例覆盖 `lib/flow.sh`：
- `vibe flow help` 输出子命令列表
- `vibe flow start` 无参数时报错
- `vibe flow status` 在非 worktree 中报错
- `_detect_feature` 从目录名提取 feature
- `_detect_agent` 从目录名提取 agent

**Step 3: 创建 keys 测试 (test_keys.bats)**

新增用例覆盖 `lib/keys.sh`：
- `vibe keys help` 输出子命令列表
- `vibe keys list` 返回 0（无论是否有 keys.env）
- `vibe keys init` 创建 keys.env（用 temp 目录隔离）

**Step 4: 创建 utils 测试 (test_utils.bats)**

新增用例覆盖 `lib/utils.sh`：
- `log_info` 输出包含 "ℹ" 或 "INFO"
- `log_error` 输出包含 "✗" 或 "ERROR"
- `log_success` 输出包含 "✓"
- `vibe_has` 检测已有命令返回 0
- `vibe_has` 检测不存在命令返回 1

**Step 5: 运行全部测试**

Run: `bats tests/`
Expected: ≥20 tests, 0 failures

**Step 6: Commit**

```bash
git add tests/
git commit -m "test: expand bats test suite to ≥20 cases covering all modules"
```

---

## Phase 2: Context 层达标 (Tool-level Feedback Loop)

> 核心思路：把已有的三把枪（Serena、ShellCheck、bats）串成自动化闭环。

### Task 2.1: 双层语法检查集成 (zsh -n + ShellCheck)

**Files:**
- Create: `.shellcheckrc`
- Create: `scripts/hooks/lint.sh`

**Step 1: 创建 ShellCheck 配置**

创建 `.shellcheckrc`，针对 Zsh 项目做合理适配：

```ini
# .shellcheckrc
# Zsh-specific: disable false positives for Zsh parameter expansion flags
# SC2296: ${(%):-%x} and ${(C)var} are valid Zsh syntax
disable=SC2296
# SC2034: Variables in sourced files may appear unused but are used by sourcer
disable=SC2034
# SC1091: Cannot follow sourced files (cross-file sourcing is by design)
disable=SC1091
```

**Step 2: 创建双层 lint 脚本**

`scripts/hooks/lint.sh` 执行两层检查：
1. **Layer 1: `zsh -n`** — Zsh 原生语法验证（严格，0 容忍）
2. **Layer 2: `shellcheck -s bash`** — 代码质量 lint（error 级别 0 容忍，warning 允许但报告）

```bash
#!/usr/bin/env bash
# scripts/hooks/lint.sh — Dual-layer shell lint: zsh -n (syntax) + shellcheck (quality)
set -e

echo "=== Layer 1: Zsh Syntax Check (zsh -n) ==="
errors=0
for f in lib/*.sh bin/vibe; do
  if zsh -n "$f" 2>&1; then
    echo "  ✅ $f"
  else
    echo "  ❌ $f"
    errors=$((errors + 1))
  fi
done
[[ $errors -gt 0 ]] && { echo "FAIL: $errors files have syntax errors"; exit 1; }
echo "  All files passed syntax check."

echo ""
echo "=== Layer 2: ShellCheck Lint ==="
shellcheck -s bash -S error lib/*.sh bin/vibe
echo "  All files passed ShellCheck (error level)."

echo ""
echo "=== Layer 2b: ShellCheck Warnings (informational) ==="
shellcheck -s bash -S warning lib/*.sh bin/vibe || true
echo ""
echo "✅ Lint complete. 0 errors."
```

**Step 3: 运行 lint**

Run: `bash scripts/hooks/lint.sh`
Expected: 0 errors（warnings 作为信息输出但不阻塞）

**Step 4: 修复 ShellCheck 发现的 error 级别问题**

已知 error：
- `lib/config.sh:7` — SC2296 (Zsh `${(%):-%x}`) → 已通过 `.shellcheckrc` 排除
- `lib/flow.sh:39` — SC2296 (Zsh `${(C)agent}`) → 已通过 `.shellcheckrc` 排除

如仍有其他 error，逐个修复。

**Step 5: 验证修复后测试仍通过**

Run: `bats tests/`
Expected: 所有测试通过

**Step 6: Commit**

```bash
git add .shellcheckrc scripts/hooks/lint.sh
git commit -m "chore: integrate dual-layer lint (zsh -n + shellcheck)"
```

### Task 2.2: Serena AST 检索集成

> 把已配置的 Serena 从"护身符"变成"实战武器"。

**Files:**
- Modify: `.serena/project.yml` (更新 project_name 和 initial_prompt)
- Create: `docs/standards/serena-usage.md`

**Step 1: 更新 Serena 项目配置**

修改 `.serena/project.yml`：
- `project_name` 从 `codex` 改为 `vibe-center`（当前配置是错的）
- 添加 `initial_prompt` 指导 Serena 的行为约束

```yaml
project_name: "vibe-center"

languages:
- bash

initial_prompt: |
  This is a Zsh CLI project with strict governance rules.
  HARD RULES:
  - Total LOC (lib/ + bin/) must be ≤ 1200
  - Any single .sh file must be ≤ 200 lines
  - Zero dead code: every function must have ≥1 caller
  - Do NOT add features not approved in SOUL.md
  Before modifying any function, use find_referencing_symbols to check callers.
  After modification, run: zsh -n <file> && bats tests/
```

**Step 2: 编写 Serena 使用规范文档**

创建 `docs/standards/serena-usage.md`，定义 Agent 在什么场景下必须使用 Serena 的哪个工具：

```markdown
# Serena AST 检索使用规范

## 强制使用场景

| 场景 | 必须使用的 Serena 工具 | 目的 |
|---|---|---|
| 修改任何函数前 | `find_referencing_symbols` | 确认影响范围，防止断裂 |
| 删除任何函数前 | `find_referencing_symbols` | 确认调用者为 0，确认是死代码 |
| 新增函数后 | `get_symbols_overview` | 确认不超过 functions_per_file 上限 |
| 理解代码上下文 | `find_symbol` + `get_symbols_overview` | 替代 cat 整文件 |
| PR Review 死代码检查 | `find_referencing_symbols` 对所有函数 | 确认 Zero Dead Code |

## 禁止行为
- ❌ 禁止用 `read_file` 读取整个文件来"理解上下文"
- ❌ 禁止在不查引用的情况下删除函数
- ❌ 禁止在不查引用的情况下修改函数签名
```

**Step 3: 验证 Serena 配置生效**

如果 Serena MCP server 已运行，可以测试：
- `find_symbol("vibe_flow")` → 应返回 `lib/flow.sh` 中的定义
- `get_symbols_overview("lib/flow.sh")` → 应返回 7 个函数

**Step 4: Commit**

```bash
git add .serena/project.yml docs/standards/serena-usage.md
git commit -m "chore: activate serena AST integration with usage standards"
```

### Task 2.3: 创建 Context 闭环 Skill (test-runner)

**Files:**
- Create: `skills/vibe-test-runner/SKILL.md`

**Step 1: 编写 Skill**

创建一个 Skill，指导 AI agent 在修改代码后自动执行三把枪的检查闭环：

```yaml
---
name: vibe-test-runner
description: 代码修改后自动执行三层验证（Serena 影响分析 + Lint + 测试），失败时循环修复（最多 3 轮）
category: quality
trigger: auto
enforcement: hard
phase: convergence
---
```

Skill 内容定义三层验证步骤：

**Layer 1: Serena 影响分析（修改前）**
- 修改任何函数前，必须通过 Serena `find_referencing_symbols` 确认调用者
- 如果有调用者且修改了签名，必须同步更新所有调用者

**Layer 2: 语法 + Lint 检查（修改后）**
- `zsh -n <modified_file>` — 语法验证
- `shellcheck -s bash <modified_file>` — 质量验证
- 如有 error，自动修复并重跑（计入循环次数）

**Layer 3: 测试验证（修复后）**
- `bats tests/` — 全量测试
- 如有失败，分析 Stack Trace 并修复（计入循环次数）

**熔断机制：**
- Layer 2 + Layer 3 共享 3 轮最大循环次数
- 3 轮修不好 → 输出诊断报告 → 挂起通知人类
- 诊断报告格式：哪个 Layer 失败、失败了多少次、最后一次的 error log

**Step 2: 验证 Skill 格式**

确认 SKILL.md 包含：System Role, Overview, When to Use, Execution Steps (三层), Output Format, What This Skill Does NOT Do。

**Step 3: Commit**

```bash
git add skills/vibe-test-runner/
git commit -m "feat: add vibe-test-runner skill with serena + lint + test triple loop"
```

---

## Phase 3: CI/CD + 度量 (Automation & Metrics)

### Task 3.1: GitHub Actions CI Pipeline

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: 编写 CI workflow**

触发条件：push to any branch, PR to main
Job steps：
1. checkout
2. install bats-core (`brew install bats-core` or apt)
3. install shellcheck
4. run `bash scripts/hooks/lint.sh` (双层 lint)
5. run `bats tests/` (Unit tests)
6. run LOC check: `find lib/ bin/ -name '*.sh' -o -name 'vibe' | xargs wc -l` 并验证 ≤ 1200
7. run 单文件上限检查: 验证所有文件 ≤ 200 行

**Step 2: 推送并验证 CI**

Run: `git push`
Expected: GitHub Actions 显示绿色 ✅

**Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add shellcheck + bats + loc-ceiling pipeline"
```

### Task 3.2: 度量仪表盘 (Metrics Dashboard)

**Files:**
- Create: `scripts/tools/metrics.sh`

**Step 1: 编写度量脚本**

输出以下指标：
- Shell LOC / LOC Ceiling (1200)
- 最大文件行数 / 单文件上限 (200)
- 测试用例数
- ShellCheck error 数
- `zsh -n` 语法检查结果
- 死代码函数数（defined but never called，通过 grep 交叉比对）
- Serena 配置状态（project.yml 存在且 project_name 正确）

输出格式：Markdown 表格，可直接嵌入 PR description 或 review 报告。

```
## 📊 MSC 健康度仪表盘

| 指标 | 上限 | 当前值 | 状态 |
|------|------|--------|------|
| 总 LOC | 1200 | 727 | ✅ 61% |
| 最大文件行数 | 200 | 195 | ✅ |
| 测试用例数 | ≥20 | 22 | ✅ |
| ShellCheck errors | 0 | 0 | ✅ |
| Zsh 语法检查 | PASS | PASS | ✅ |
| 死代码函数 | 0 | 0 | ✅ |
| Serena 配置 | ✅ | ✅ | ✅ |
| CLI Spec 覆盖 | ✅ | ✅ | ✅ |
```

**Step 2: 运行并验证**

Run: `bash scripts/tools/metrics.sh`
Expected: Markdown 表格输出，所有指标在健康范围内

**Step 3: Commit**

```bash
git add scripts/tools/metrics.sh
git commit -m "chore: add MSC health metrics dashboard"
```

### Task 3.3: 更新 model-spec-context.md 最终自检

**Files:**
- Modify: `docs/model-spec-context.md` (第四章 "Vibe Center 项目自检")

**Step 1: 更新自检评级**

将 Context 层自检中的以下项从 ❌ 更新为 ✅：
- AST 检索能力 → ✅ Serena 已集成并制定使用规范
- 类型/语法检查反馈 → ✅ 双层 lint (zsh -n + shellcheck) 已集成
- 循环修复闭环 → ✅ vibe-test-runner Skill 实现 3 轮熔断

**Step 2: 运行 metrics.sh 贴结果作为证据**

Run: `bash scripts/tools/metrics.sh`
贴输出到文档中作为实际数据支撑。

**Step 3: Commit**

```bash
git add docs/model-spec-context.md
git commit -m "docs: update MSC self-audit to reflect compliance status"
```

---

## 验收标准 (Definition of Done)

当以下全部条件满足时，视为 MSC 合规达标：

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | 所有文件 ≤ 200 行 | `scripts/tools/metrics.sh` |
| 2 | 总 LOC ≤ 1200 | `scripts/tools/metrics.sh` |
| 3 | CLI Spec 存在且覆盖所有命令 | `cat openspec/specs/cli-commands.yaml` |
| 4 | 测试用例 ≥ 20 个且全部通过 | `bats tests/` |
| 5 | `zsh -n` 全部 PASS | `bash scripts/hooks/lint.sh` |
| 6 | ShellCheck 0 error | `bash scripts/hooks/lint.sh` |
| 7 | Serena 配置正确且有使用规范 | `.serena/project.yml` + `docs/standards/serena-usage.md` |
| 8 | test-runner Skill 包含三层验证 + 3 轮熔断 | `cat skills/vibe-test-runner/SKILL.md` |
| 9 | CI Pipeline 绿色 | GitHub Actions |
| 10 | 度量脚本可用且全绿 | `bash scripts/tools/metrics.sh` |
| 11 | 死代码 = 0 | `scripts/tools/metrics.sh` |
| 12 | docs/model-spec-context.md 自检全绿 | 人工确认 |

## 变更汇总

| 类型 | 文件 | 预估行数 |
|---|---|---|
| 修改 | `lib/flow.sh` | -13 行 |
| 修改 | `.serena/project.yml` | ~5 行改动 |
| 修改 | `docs/model-spec-context.md` | ~20 行更新 |
| 新增 | `openspec/specs/cli-commands.yaml` | ~80 行 |
| 新增 | `tests/test_vibe.bats` | ~30 行 |
| 新增 | `tests/test_flow.bats` | ~30 行 |
| 新增 | `tests/test_keys.bats` | ~30 行 |
| 新增 | `tests/test_utils.bats` | ~30 行 |
| 新增 | `.shellcheckrc` | ~5 行 |
| 新增 | `scripts/hooks/lint.sh` | ~25 行 |
| 新增 | `scripts/tools/metrics.sh` | ~60 行 |
| 新增 | `skills/vibe-test-runner/SKILL.md` | ~70 行 |
| 新增 | `docs/standards/serena-usage.md` | ~40 行 |
| 新增 | `.github/workflows/ci.yml` | ~45 行 |
| **总计** | **14 文件** | **~450 行新增，~13 行删除，~25 行修改** |
