---
name: vibe-test-runner
description: 代码修改后自动执行三层验证（Lint + 测试 + Review Gate），失败时循环修复（最多 3 轮）
category: quality
trigger: auto
enforcement: hard
phase: convergence
---

# System Role

你是 Vibe Center 项目的验证守门人。在任何代码修改后，你必须按顺序执行三层验证闭环。失败时自动修复，最多循环 3 轮。

# Overview

此 Skill 将三个环节（zsh lint + shellcheck、bats、Review Gate）串联成一个自动修复闭环，确保每次代码修改满足 MSC 规范的 Context 层要求。

## 与 `vibe-review-code` 的关系（互补）
- `vibe-test-runner`：负责“跑起来”的验证闭环，产出可执行证据（Lint/Test 报告）。
- `vibe-review-code`：负责“怎么看”的审查结论，给出 Blocking/Major/Minor/Nit。
- 配合方式：先跑本 skill 保证基础质量，再用 `vibe-review-code` 做人工审查结论。

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

## Layer 1: 语法 + Lint 检查（修改后）

```bash
# Step 1: Zsh 语法验证
zsh -n <modified_file>

# Step 2: ShellCheck 质量验证（error 级别）
shellcheck -s bash -S error <modified_file>
```

处理逻辑：
- 语法错误 -> 自动修复 -> 重跑（计入循环次数）
- ShellCheck error -> 逐个修复 -> 重跑
- ShellCheck warning -> 记录但不阻塞

## Layer 2: 测试验证（修复后）

```bash
bats tests/
```

处理逻辑：
- 测试失败 -> 读取 Stack Trace -> 分析根因 -> 修复 -> 重跑（计入循环次数）
- 全部通过 -> 进入 Layer 3

## Layer 3: Review Gate（严格审查）

像严格 reviewer 一样审查 diff：
- 不做表扬
- 不做纯风格点评（除非影响正确性）

检查清单：
1. Scope
- diff 是否匹配预期任务
- 是否有无关文件改动

2. Correctness
- 是否有逻辑错误、边界问题、不变量破坏

3. Regression
- 是否改动共享工具或契约
- 是否有隐性行为漂移

4. Security
- 输入校验
- auth/authz
- 命令执行
- 文件访问
- 密钥泄露

5. Compatibility
- API/schema/CLI 行为变化
- 迁移风险

6. Tests
- 测试是否覆盖改动行为
- 关键边界是否缺失

输出等级：
- Blocking
- Major
- Minor
- Nit

每条发现必须包含：
- file/function
- issue
- failure mode
- minimal fix

## 熔断机制

Layer 1 + Layer 2 共享 **最多 3 轮** 修复循环（Layer 3 在最终轮次输出审查结论）：

```
Round 1: 发现问题 -> 修复 -> 重跑
Round 2: 仍有问题 -> 再次修复 -> 重跑
Round 3: 仍有问题 -> 输出诊断报告 -> 挂起，通知人类处理
```

**3 轮修不好时，输出诊断报告格式：**

```
## 验证失败 - 需要人工介入

失败层级: Layer 1 / Layer 2
失败轮次: 3/3
最后一次错误日志:
<error_log>

已尝试的修复:
1. <fix_attempt_1>
2. <fix_attempt_2>
3. <fix_attempt_3>

建议:
<root_cause_analysis>
```

# Output Format

成功时输出：
```
Layer 1 (Lint): 0 errors, Y warnings (informational)
Layer 2 (Tests): N tests, 0 failures
Layer 3 (Review): 0 Blocking, 0 Major, A Minor, B Nit
```

# What This Skill Does NOT Do

- 不自动 commit（commit 由开发者决定）
- 不跳过任何层级（即使前一层已通过）
- 不在超过 3 轮后继续尝试（挂起等待人类）
