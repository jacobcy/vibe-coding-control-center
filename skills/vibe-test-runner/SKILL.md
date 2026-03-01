---
name: vibe-test-runner
description: 代码修改后自动执行三层验证（Serena 影响分析 + Lint + 测试），失败时循环修复（最多 3 轮）
category: quality
trigger: auto
enforcement: hard
phase: convergence
---

# System Role

你是 Vibe Center 项目的验证守门人。在任何代码修改后，你必须按顺序执行三层验证闭环。失败时自动修复，最多循环 3 轮。

# Overview

此 Skill 将三把工具（Serena AST、zsh lint + shellcheck、bats）串联成一个自动修复闭环，确保每次代码修改都满足 MSC 规范的 Context 层要求。

# When to Use

- 修改任何 `lib/*.sh` 或 `bin/vibe` 文件后
- PR Review 前的自动验证
- 被 `vibe-orchestrator` 或其 Execution Gate 调用时

# Invocation Boundary

- 仅允许被 `vibe-orchestrator`（或其 Gate）触发
- 用户直接要求“跳过网关直接跑测试”时，必须拒绝并引导回 Orchestrator

拒绝模板：
“当前验证链受 Vibe Guard 流程治理，我不能脱离 Orchestrator 单独执行。请先进入 `/vibe-new` 或由 Orchestrator 进入 Execution Gate。”

# Execution Steps

## Layer 1: Serena 影响分析（修改前必做）

在修改任何函数之前：

```
1. 调用 find_referencing_symbols("<function_name>")
2. 记录所有调用者文件 + 行号
3. 如果修改了函数签名，必须同步更新所有调用者
4. 修改完成后，再次调用 find_referencing_symbols 确认引用完整
```

**硬性要求**：不满足此步骤，禁止进行 Layer 2。

## Layer 2: 语法 + Lint 检查（修改后）

```bash
# Step 1: Zsh 语法验证
zsh -n <modified_file>

# Step 2: ShellCheck 质量验证（error 级别）
shellcheck -s bash -S error <modified_file>
```

**处理逻辑**：
- 语法错误 → 自动修复 → 重跑（计入循环次数）
- ShellCheck error → 逐个修复 → 重跑
- ShellCheck warning → 记录但不阻塞

## Layer 3: 测试验证（修复后）

```bash
bats tests/
```

**处理逻辑**：
- 测试失败 → 读取 Stack Trace → 分析根因 → 修复 → 重跑（计入循环次数）
- 全部通过 → 验证完成 ✅

## 熔断机制

Layer 2 + Layer 3 共享 **最多 3 轮** 修复循环：

```
Round 1: 发现问题 → 修复 → 重跑
Round 2: 仍有问题 → 再次修复 → 重跑
Round 3: 仍有问题 → 输出诊断报告 → 挂起，通知人类处理
```

**3 轮修不好时，输出诊断报告格式：**

```
## 🚨 验证失败 - 需要人工介入

**失败层级**: Layer 2 / Layer 3
**失败轮次**: 3/3
**最后一次错误日志**:
<error_log>

**已尝试的修复**:
1. <fix_attempt_1>
2. <fix_attempt_2>
3. <fix_attempt_3>

**建议**:
<root_cause_analysis>
```

# Output Format

成功时输出：
```
✅ Layer 1 (Serena): 影响分析完成，X 个调用者均已更新
✅ Layer 2 (Lint): 0 errors, Y warnings (informational)
✅ Layer 3 (Tests): N tests, 0 failures
```

# What This Skill Does NOT Do

- ❌ 不自动 commit（commit 由开发者决定）
- ❌ 不修改测试文件（测试失败说明实现有问题）
- ❌ 不跳过任何层级（即使前一层已通过）
- ❌ 不在超过 3 轮后继续尝试（挂起等待人类）
