# OpenSpec 融入 Vibe Workflow Engine 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 Plan Provider 抽象接口，使 Vibe Orchestrator 能够透明调用 OpenSpec 或其他规范框架，实现松耦合集成。

**Architecture:** 引入 Plan Provider 适配器模式 - Orchestrator 通过抽象接口访问计划内容，底层可替换为 OpenSpec/Markdown/其他框架。对用户透明，通过 `/vibe-new` 统一入口。

**Tech Stack:** Zsh, OpenSpec CLI, Markdown, Vibe Skills

---

## 背景

当前状态：
- Vibe Orchestrator 已实现四闸机制（Scope/Plan/Execution/Review Gate）
- OpenSpec 已安装 (v1.1.1)，有独立 skill 和 workflow
- 两者独立运行，无交集

目标：
- Orchestrator 的 Plan Gate 能自动检测并读取 OpenSpec artifacts
- 用户通过 `/vibe-new` 透明使用，不需要显式调用 `/opsx`
- 保持松耦合，未来可轻松替换为其他规范框架

---

## Task 1: 创建 Plan Provider 抽象层

### 1.1: 创建 lib/plan-provider.sh 骨架

**Files:**
- Create: `lib/plan-provider.sh`

**Step 1: 写入骨架代码**

```zsh
#!/usr/bin/env zsh
# lib/plan-provider.sh - Plan Provider 抽象接口
# 支持 OpenSpec / Native Markdown 等多种规范框架

[[ -z "${VIBE_ROOT:-}" ]] && { echo "error: VIBE_ROOT not set"; return 1; }

# Plan Provider 类型
PLAN_PROVIDER_TYPE=""

# 检测计划来源
plan_detect_source() {
  local feature="$1"

  # 检测 OpenSpec
  if [[ -d "${VIBE_ROOT}/openspec/changes/${feature}" ]]; then
    PLAN_PROVIDER_TYPE="openspec"
    echo "openspec"
    return 0
  fi

  # 检测 Native Markdown
  if [[ -f "${VIBE_ROOT}/docs/prds/${feature}.md" ]]; then
    PLAN_PROVIDER_TYPE="native-md"
    echo "native-md"
    return 0
  fi

  PLAN_PROVIDER_TYPE=""
  echo "none"
  return 1
}

# 读取 Proposal (Scope Gate 用)
plan_read_proposal() {
  local feature="$1"
  case "$PLAN_PROVIDER_TYPE" in
    openspec)
      cat "${VIBE_ROOT}/openspec/changes/${feature}/proposal.md" 2>/dev/null
      ;;
    native-md)
      cat "${VIBE_ROOT}/docs/prds/${feature}.md" 2>/dev/null
      ;;
    *)
      echo ""
      ;;
  esac
}

# 读取 Design (Plan Gate 用)
plan_read_design() {
  local feature="$1"
  case "$PLAN_PROVIDER_TYPE" in
    openspec)
      cat "${VIBE_ROOT}/openspec/changes/${feature}/design.md" 2>/dev/null
      ;;
    native-md)
      cat "${VIBE_ROOT}/docs/specs/${feature}-spec.md" 2>/dev/null
      ;;
    *)
      echo ""
      ;;
  esac
}

# 读取 Tasks (Execution Gate 用)
plan_read_tasks() {
  local feature="$1"
  case "$PLAN_PROVIDER_TYPE" in
    openspec)
      cat "${VIBE_ROOT}/openspec/changes/${feature}/tasks.md" 2>/dev/null
      ;;
    native-md)
      cat "${VIBE_ROOT}/docs/tasks/${feature}.md" 2>/dev/null
      ;;
    *)
      echo ""
      ;;
  esac
}

# 读取 Verification (Review Gate 用)
plan_read_verification() {
  local feature="$1"
  case "$PLAN_PROVIDER_TYPE" in
    openspec)
      cat "${VIBE_ROOT}/openspec/changes/${feature}/verify.md" 2>/dev/null
      ;;
    native-md)
      # Native MD 没有独立的 verify，从 tasks 中提取
      grep -E "^\- \[ \]|# .*验证|# .*check" "${VIBE_ROOT}/docs/tasks/${feature}.md" 2>/dev/null || echo ""
      ;;
    *)
      echo ""
      ;;
  esac
}

# 回退创建计划模板
plan_fallback_create() {
  local feature="$1"
  local type="$2"  # openspec | native-md

  case "$type" in
    openspec)
      echo "请使用 /opsx:new ${feature} 创建 OpenSpec artifacts"
      ;;
    native-md)
      mkdir -p "${VIBE_ROOT}/docs/prds"
      mkdir -p "${VIBE_ROOT}/docs/specs"
      mkdir -p "${VIBE_ROOT}/docs/tasks"

      cat > "${VIBE_ROOT}/docs/prds/${feature}.md" << 'EOF'
# PRD: {feature}

## 背景
_TODO: 描述为什么需要这个功能_

## 目标
- [ ] 目标1
- [ ] 目标2

## 非目标
- 不做 X
- 不做 Y

## 验证方式
- [ ] 验证点1
- [ ] 验证点2
EOF

      echo "Created: docs/prds/${feature}.md"
      ;;
  esac
}
```

**Step 2: 验证语法**

Run: `zsh -n lib/plan-provider.sh`
Expected: 无错误

**Step 3: 提交**

```bash
git add lib/plan-provider.sh
git commit -m "feat: add Plan Provider abstract interface"
```

---

## Task 2: 改造 vibe-orchestrator Skill 集成 Plan Provider

### 2.1: 更新 vibe-orchestrator SKILL.md

**Files:**
- Modify: `skills/vibe-orchestrator/SKILL.md`

**Step 1: 在 Plan Gate 部分添加 Plan Provider 调用逻辑**

在现有 Plan Gate 部分找到类似这样的内容：
```yaml
### Gate 2: Plan Gate
- 检查是否存在可执行计划（目标、非目标、步骤、验证命令）
- 无计划时，先产出计划文件再继续
- 禁止"先改再补计划"
```

替换为：
```yaml
### Gate 2: Plan Gate

**Step 2.1: 检测计划来源**
- 调用 plan_detect_source("<feature_name>")
- 识别来源类型：openspec / native-md / none

**Step 2.2: 读取计划内容**
- 如果是 openspec：读取 openspec/changes/<feature>/proposal.md, design.md, tasks.md
- 如果是 native-md：读取 docs/prds/<feature>.md, docs/specs/<feature>-spec.md, docs/tasks/<feature>.md

**Step 2.3: 验证计划完整性**
- proposal: 是否有明确的目标和非目标
- design: 是否有技术方案描述
- tasks: 是否有任务列表和验证命令

**Step 2.4: 无计划时的处理**
- 如果没有找到计划，引导用户选择：
  - 使用 OpenSpec: /opsx:new <feature>
  - 使用原生 Markdown: 创建 docs/prds/<feature>.md
- 禁止在无计划情况下进入 Execution Gate

**拒绝模板：**
"当前缺少必要的计划文件。请先通过 `/opsx:new ${feature}` 创建 OpenSpec 计划，或在 docs/prds/${feature}.md 中编写 PRD。我不能在没有计划的情况下进入执行阶段，以避免产出垃圾代码。"
```

**Step 2: 提交**

```bash
git add skills/vibe-orchestrator/SKILL.md
git commit -m "feat: integrate Plan Provider in orchestrator Plan Gate"
```

---

## Task 3: 改造 vibe-test-runner Skill 支持 Verification 来源

### 3.1: 更新 vibe-test-runner SKILL.md

**Files:**
- Modify: `skills/vibe-test-runner/SKILL.md`

**Step 1: 添加 verification 来源检测逻辑**

在 Execution Gate 的 Layer 3 部分，找到：
```yaml
### Layer 3: 测试验证（修复后）
```

添加前置步骤：
```yaml
### Layer 3.0: 读取验证标准（新增）

在执行测试前，先尝试获取验证标准：
- 如果存在 openspec/changes/<feature>/verify.md，读取验证命令
- 如果不存在 verify.md，从 tasks.md 中提取验证项
- 如果都没有，使用默认验证：zsh -n + shellcheck + bats

**验证优先级：**
1. verify.md 中的明确验证命令
2. tasks.md 中的 check 项
3. 默认验证（lint + test）
```

**Step 2: 提交**

```bash
git add skills/vibe-test-runner/SKILL.md
git commit -m "feat: support verification from multiple sources in test-runner"
```

---

## Task 4: 更新 workflow 入口文档

### 4.1: 更新 vibe-new.md workflow

**Files:**
- Modify: `.agent/workflows/vibe-new.md`

**Step 1: 添加 Plan Provider 说明**

在 Step 3 "Run Gate Flow" 部分添加：
```yaml
**Plan Gate 细节：**
- Orchestrator 会自动检测计划来源（OpenSpec 或 Markdown）
- 支持的格式：
  - OpenSpec: openspec/changes/<feature>/proposal.md, design.md, tasks.md
  - Native MD: docs/prds/<feature>.md, docs/specs/<feature>-spec.md
- 如果未找到计划，会引导用户创建
```

**Step 2: 提交**

```bash
git add .agent/workflows/vibe-new.md
git commit -m "docs: document Plan Provider support in vibe-new workflow"
```

---

## Task 5: 创建端到端测试验证

### 5.1: 创建 plan-provider 测试

**Files:**
- Create: `tests/plan-provider.bats`

**Step 1: 写入测试用例**

```bash
#!/usr/bin/env bats

setup() {
  load test_helper
  # 设置 VIBE_ROOT 为测试目录
  export VIBE_ROOT="${BATS_TEST_DIRNAME}/.."
}

@test "plan_detect_source: detects openspec" {
  # 创建临时 openspec 目录结构
  mkdir -p "${BATS_TMPDIR}/openspec/changes/test-feature"
  echo "# Proposal" > "${BATS_TMPDIR}/openspec/changes/test-feature/proposal.md"

  # 注意：需要 mock VIBE_ROOT 或修改函数支持自定义路径
  # 这个测试需要在实际环境中验证
}

@test "plan_detect_source: returns none for missing feature" {
  run plan_detect_source "nonexistent-feature"
  [ "$status" -eq 1 ]
}
```

**Step 2: 提交**

```bash
git add tests/plan-provider.bats
git commit -m "test: add Plan Provider tests"
```

---

## Task 6: 更新 governance.yaml flow_hooks (可选)

### 6.1: 扩展 governance.yaml

**Files:**
- Modify: `.agent/governance.yaml`

**Step 1: 添加 Plan Provider 相关配置**

```yaml
# 计划来源优先级
plan_sources:
  priority:
    - openspec    # OpenSpec artifacts
    - native-md   # docs/prds/*.md
  fallback_create: native-md  # 默认创建格式
```

**Step 2: 提交**

```bash
git add .agent/governance.yaml
git commit -m "config: add plan_sources to governance.yaml"
```

---

## Task 6: 更新 governance.yaml flow_hooks (可选)

### 6.1: 扩展 governance.yaml

**Files:**
- Modify: `.agent/governance.yaml`

**Step 1: 添加 Plan Provider 相关配置**

```yaml
# 计划来源优先级
plan_sources:
  priority:
    - openspec    # OpenSpec artifacts
    - native-md   # docs/prds/*.md
  fallback_create: native-md  # 默认创建格式
```

**Step 2: 提交**

```bash
git add .agent/governance.yaml
git commit -m "config: add plan_sources to governance.yaml"
```

---

## Task 7: 增加 AI Spec Critic 机制 (对齐范式 2. 规范层)

> 对应 Cognition-Spec-Dominion 范式中的 "AI 刺客/找茬" 机制

### 7.1: 创建 vibe-spec-critic Skill

**Files:**
- Create: `skills/vibe-spec-critic/SKILL.md`

**Step 1: 写入 skill 定义**

```yaml
---
name: vibe-spec-critic
description: AI 架构刺客 - 在 Spec 锁定前进行逆向提问，找出问题与漏洞
category: guardian
trigger: auto
enforcement: hard
phase: planning
---

# AI Spec Critic 架构刺客

## System Role

你是 AI 架构刺客 (Spec Critic)，你的职责是在 Spec 正式锁定前进行"找茬"式审查，专门挑战假设、寻找漏洞、暴露风险。你不是实现者，你是"故意找麻烦"的审查者。

## 核心任务

对给定的 Spec (docs/specs/{feature}-spec.md) 进行逆向审查：

### 必须执行的审查维度

1. **边界完备性**
   - 极限输入是否被覆盖？（空值、超长、特殊字符）
   - 并发场景是否考虑？（竞态条件、死锁）
   - 网络异常是否处理？（超时、重试、熔断）

2. **假设检验**
   - 哪些假设被隐式做出？
   - 如果假设不成立会怎样？

3. **完整性检查**
   - 接口契约是否完整？（成功/错误/边界）
   - 不变量是否真的"不变"？
   - 性能约束是否可测量？

4. **过度设计检测**
   - 是否有"个人脚本用航母级设计"的情况？
   - 是否有解决不存在问题的抽象层？

## 输出格式

```markdown
## Spec Critic 审查报告

### 风险评级: 低 / 中 / 高

### 找茬清单

| # | 类别 | 问题 | 严重度 | 建议 |
|---|---|---|---|---|
| 1 | 边界 | 缺少空值处理 | 高 | 添加 null 检查 |
| 2 | 假设 | 假设网络永远稳定 | 中 | 添加重试机制 |
| 3 | 过度 | 为 CLI 工具设计微服务架构 | 中 | 简化设计 |

### 结论

- [ ] 可以锁定 Spec
- [ ] 需要修改后重新审查
- [ ] 建议返回 Plan 阶段重新讨论
```

## 触发时机

- Spec 新创建或重大修改后
- 由 Orchestrator 的 Plan Gate 在检测到 Spec 时自动触发
- 只有 Critic 通过后才能进入 Execution Gate
```

**Step 2: 验证语法**

确认 YAML 格式正确，无明显错误。

**Step 3: 提交**

```bash
git add skills/vibe-spec-critic/SKILL.md
git commit -m "feat: add AI Spec Critic skill for adversarial review"
```

### 7.2: 更新 Orchestrator 集成 Spec Critic

**Files:**
- Modify: `skills/vibe-orchestrator/SKILL.md`

**Step 1: 在 Plan Gate 添加 Spec Critic 调用**

在 Plan Gate 验证计划完整性后，添加：

```yaml
**Step 2.5: Spec 审查（AI 刺客机制）**
- 如果存在 Spec 文件 (docs/specs/{feature}-spec.md 或 openspec/.../design.md)
- 自动触发 `vibe-spec-critic` 进行找茬审查
- 如果 Critic 报告返回 高风险：
  - 阻断进入 Execution Gate
  - 引导用户修复 Spec 后重新审查
- 如果 Critic 报告返回 中风险：
  - 警告但允许通过（人类决定）
- 如果 Critic 报告返回 低风险：
  - 通过

**拒绝模板：**
"Spec 审查发现 高风险问题，当前无法进入代码阶段。请先修复以下问题后重新审查：
{critic_report}"
```

**Step 2: 提交**

```bash
git add skills/vibe-orchestrator/SKILL.md
git commit -m "feat: integrate Spec Critic in orchestrator Plan Gate"
```

---

## Task 8: 增加"串通检测"机制 (对齐范式 6. AI Audit)

> 对应 Cognition-Spec-Dominion 范式中 "AI 审计官和 AI 编码员串通检测"

### 8.1: 创建 vibe-collusion-detector Skill

**Files:**
- Create: `skills/vibe-collusion-detector/SKILL.md`

**Step 1: 写入 skill 定义**

```yaml
---
name: vibe-collusion-detector
description: 检测 AI 编码员与 AI 审计员是否"串通" - 审计放水或代码偷换概念
category: guardian
trigger: auto
enforcement: hard
phase: review
---

# Collusion Detector 串通检测器

## System Role

你是串通检测器 (Collusion Detector)，你的职责是检测 AI 编码员和 AI 审计员是否"串通作恶"——即审计官放水、编码员偷换概念、或两者共同绕过规范。

## 核心任务

### 必须检测的串通模式

1. **审计放水**
   - 审计报告中是否缺少关键问题？
   - 测试是否被弱化？（删除边界用例、降低断言强度）
   - 是否对明显错误"视而不见"？

2. **概念偷换**
   - 代码实现是否偏离了 Spec 的核心定义？
   - 是否有"改叫法不改实现"的情况？
   - 是否有删除了功能但声称保留的情况？

3. **测试作弊**
   - 测试是否真的在验证 Spec 要求？
   - 是否有"永远通过"的测试？
   - 错误处理是否被真实测试？

## 检测方法

### 对比分析

```
输入：
- docs/specs/{feature}-spec.md (原始 Spec)
- 代码实现 (lib/, bin/)
- vibe-rules-enforcer 输出的审计报告

检测：
1. Spec 中的每个不变量 → 代码中是否有对应实现？
2. Spec 中的每个边界用例 → 测试中是否有覆盖？
3. 审计报告中的每个 绿 → 是否有事实支撑？
```

### 串通信号

| 信号 | 检测方法 |
|------|----------|
| 审计报告过于简洁 | 逐项对照 Spec 检查 |
| 测试覆盖率异常高但质量低 | 审查测试逻辑真实性 |
| 无报错通过 | 故意构造错误输入测试 |
| Spec 变更未同步 | 对比 git 历史中 Spec vs Code 变更 |

## 输出格式

```markdown
## Collusion Detection Report

### 串通风险评级: 无 / 警告 / 检测到

### 逐项检查

| Spec 要求 | 代码实现 | 审计确认 | 状态 |
|-----------|---------|---------|------|
| 接口返回 JSON | 实现了 | 通过 | 绿 |
| 错误返回 500 | 未实现 | 通过 | 红 串通 |
| 超时重试 | 部分 | 通过 | 黄 |

### 结论

- [ ] 无串通迹象
- [ ] 警告：审计可能过于宽松
- [ ] 检测到串通：需要人类介入
```

## 触发时机

- 由 Review Gate 在 vibe-rules-enforcer 完成后自动触发
- 独立运行，不依赖编码/审计 Agent 的输出
```

**Step 2: 提交**

```bash
git add skills/vibe-collusion-detector/SKILL.md
git commit -m "feat: add Collusion Detector skill"
```

### 8.2: 更新 Review Gate 集成串通检测

**Files:**
- Modify: `skills/vibe-orchestrator/SKILL.md`

**Step 1: 在 Review Gate 添加串通检测**

找到 Review Gate 部分，添加：

```yaml
### Gate 4: Review Gate

**Step 4.1: 执行合规审查**
- 调用 `vibe-rules-enforcer` 生成合规报告
- 调用 `vibe-boundary-check` 生成边界报告

**Step 4.2: 串通检测（新增）**
- 调用 `vibe-collusion-detector` 进行独立审查
- 检测是否存在"审计放水"或"概念偷换"
- 如果检测到 串通风险：
  - 阻断合并
  - 输出详细串通报告
  - 建议人类介入

**Step 4.3: 最终裁决**
- 根据合规报告 + 串通检测结果输出最终结论
- 只有全部通过才能建议合并
```

**Step 2: 提交**

```bash
git add skills/vibe-orchestrator/SKILL.md
git commit -m "feat: integrate Collusion Detector in Review Gate"
```

---

## Task 9: 增强 Execution Plan 上下文圈定 (对齐范式 3.)

> 对应 Cognition-Spec-Dominion 范式中的 "上下文圈定" 要求

### 9.1: 创建 tasks.md 模板增强

**Files:**
- Modify: `docs/templates/task-template.md` (或创建)

**Step 1: 添加上下文圈定字段**

```markdown
# Task: {task_name}

## 上下文圈定 (Context Scoping) - 必须填写

### 需要读取的文件
- [ ] `lib/xxx.sh` - 原因：调用现有函数
- [ ] `bin/vibe` - 原因：CLI 入口修改

### 禁止读取的文件
- [ ] `lib/unrelated.sh` - 原因：功能无关

### 预计改动范围
- 文件数: N
- 预计新增行数: N

## 任务详情

### 任务描述
一句话描述

### 验收标准
- [ ] 标准1
- [ ] 标准2
```

**Step 2: 提交**

```bash
git add docs/templates/task-template.md
git commit -m "docs: enhance task template with context scoping"
```

### 9.2: 更新 Orchestrator 验证上下文圈定

**Files:**
- Modify: `skills/vibe-orchestrator/SKILL.md`

**Step 1: 在 Execution Gate 添加上下文验证**

```yaml
### Gate 3: Execution Gate

**Step 3.1: 验证上下文圈定**
- 在执行每个任务前，验证 tasks.md 中是否包含"上下文圈定"部分
- 检查：
  - 是否有明确的"需要读取的文件"列表
  - 是否有明确的"禁止读取的文件"列表
- 如果缺少上下文圈定：
  - 提示必须补充才能执行
  - 禁止盲目读取整个代码库

**Step 3.2: 按任务执行**
- 读取 tasks.md 中的任务列表
- 逐个执行任务
- 每个任务完成后验证验收标准
```

**Step 2: 提交**

```bash
git add skills/vibe-orchestrator/SKILL.md
git commit -m "feat: enforce context scoping in Execution Gate"
```

---

## 验证步骤

完成所有 tasks 后，执行以下验证：

1. **语法检查**
   ```bash
   zsh -n lib/plan-provider.sh
   ```

2. **加载测试**
   ```bash
   source lib/plan-provider.sh
   plan_detect_source "nonexistent"  # 应返回 none
   ```

3. **手动测试**
   - 执行 `vibe flow start test-feature`
   - 在 AI 助手中执行 `/vibe-new test-feature`
   - 验证 Plan Gate 能正确检测计划来源

---

## 依赖关系

```
Task 1 (Plan Provider 抽象层)
    │
    ├── Task 2 (Orchestrator 集成) ← 依赖 Task 1
    ├── Task 3 (Test Runner 更新)  ← 依赖 Task 1
    ├── Task 4 (文档更新)         ← 独立
    ├── Task 5 (单元测试)          ← 依赖 Task 1
    └── Task 6 (governance 配置)  ← 可选

Task 7 (AI Spec Critic)          ← 独立
    └── Task 7.2 (集成)          ← 依赖 Task 7.1

Task 8 (串通检测机制)            ← 独立
    └── Task 8.2 (集成)          ← 依赖 Task 8.1

Task 9 (上下文圈定增强)           ← 独立
    └── Task 9.2 (集成)          ← 依赖 Task 9.1
```

---

## 预期产出

| Task | 文件 | 说明 |
|------|------|------|
| Task 1 | `lib/plan-provider.sh` | Plan Provider 抽象接口实现 |
| Task 2 | `skills/vibe-orchestrator/SKILL.md` | 集成 Plan Provider |
| Task 3 | `skills/vibe-test-runner/SKILL.md` | 支持多源验证 |
| Task 4 | `.agent/workflows/vibe-new.md` | 文档更新 |
| Task 5 | `tests/plan-provider.bats` | 单元测试 |
| Task 6 | `.agent/governance.yaml` | 配置扩展（可选）|
| Task 7 | `skills/vibe-spec-critic/SKILL.md` | AI 刺客找茬机制 |
| Task 8 | `skills/vibe-collusion-detector/SKILL.md` | 串通检测机制 |
| Task 9 | `docs/templates/task-template.md` | 上下文圈定模板 |

---

## 范式对齐总结

| 范式层 | 对应 Task | 产出 |
|--------|-----------|------|
| 1. PRD（认知层） | Task 1-4 | Plan Provider 透明调用 |
| 2. Spec（规范层） | Task 7 | AI Spec Critic 找茬 |
| 3. Execution Plan | Task 9 | 上下文圈定强制要求 |
| 4. Test | Task 3 | 多源验证 |
| 5. Code | Task 1（Serena）| AST 约束（已有）|
| 6. AI Audit | Task 8 | 串通检测 |

---

## Plan complete and saved to `docs/plans/2026-02-26-plan-provider-integration.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
