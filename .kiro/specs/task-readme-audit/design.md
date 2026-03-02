# Task README Status Field Audit & Cleanup - Bugfix Design

## Overview

本 bugfix 解决 Task README 文件中的状态字段冲突问题。当前系统存在双头真源：frontmatter 的 `status` 字段与正文的 `**状态**:` 字段同时存在且可能不一致，违反单一真源原则（Single Source of Truth）。

根据 2026-03-02 审计结果，发现 6 个文件存在此问题：
- 2 个高优先级冲突文件（frontmatter 与正文状态值完全不同）
- 4 个中优先级冗余文件（状态值一致但存在重复维护负担）

修复策略：确立 frontmatter `status` 字段为唯一真源，将正文中的独立状态字段替换为指引文本或完全删除，消除冗余和冲突。

## Glossary

- **Bug_Condition (C)**: Task README 文件同时包含 frontmatter `status` 字段和正文 `**状态**:` 字段
- **Property (P)**: Task README 文件仅使用 frontmatter `status` 作为唯一真源，正文使用指引文本或不显示状态
- **Preservation**: 保持 frontmatter 其他元数据字段、正文非状态内容、Gate 进展表格不变
- **Frontmatter Status**: YAML frontmatter 中的 `status:` 字段，使用标准枚举值（`todo`, `in_progress`, `completed`, `archived` 等）
- **正文状态字段**: 正文中的 `- **状态**: xxx` 行，可能与 frontmatter 冲突或冗余
- **指引文本**: 替代独立状态值的文本，如 `见 frontmatter \`status\` 字段（唯一真源）`
- **Gate 状态表格**: 显示各个 gate（scope/spec/plan/test/code/audit）进展的表格，这些是独立检查点状态，不属于任务整体状态

## Bug Details

### Fault Condition

当 Task README 文件同时包含 frontmatter `status` 字段和正文 `**状态**:` 字段时，系统产生双头真源问题。这导致：
1. 状态信息可能冲突（frontmatter 显示 `completed`，正文显示 `In Progress`）
2. 维护负担增加（需要同步更新两处）
3. 信息过时风险（开发者更新一处但忘记另一处）

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type TaskREADMEFile
  OUTPUT: boolean
  
  RETURN input.hasFrontmatterStatus()
         AND input.hasBodyStatusField()
         AND input.bodyStatusField.pattern MATCHES "- \*\*状态\*\*: .+"
END FUNCTION
```

### Examples

- **高优先级冲突 1**: `docs/tasks/2026-03-02-cross-worktree-task-registry/README.md`
  - Frontmatter: `status: "completed"`
  - 正文: `- **状态**: In Progress`
  - 问题: 状态值完全矛盾，无法确定任务真实状态

- **高优先级冲突 2**: `docs/tasks/2026-03-01-session-lifecycle/README.md`
  - Frontmatter: `status: "completed"`
  - 正文: `- **状态**: In Progress`
  - 问题: 状态值完全矛盾，无法确定任务真实状态

- **中优先级冗余 1**: `docs/tasks/2026-03-02-rotate-alignment/README.md`
  - Frontmatter: `status: "planning"`
  - 正文: `- **状态**: 见 frontmatter \`status\` 字段（唯一真源）`
  - 问题: 虽然已使用指引文本，但格式需要统一（当前已修复为正确格式）

- **中优先级冗余 2**: `docs/tasks/2026-03-02-command-slash-alignment/README.md`
  - Frontmatter: `status: "todo"`
  - 正文: `- **状态**: Todo`
  - 问题: 状态值一致但存在冗余，增加维护负担

- **边缘情况**: 已归档任务（archived）
  - 多个 archived 任务的 frontmatter 和正文状态一致
  - 虽然不冲突，但仍需清理冗余以统一标准

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Frontmatter 其他元数据字段（`task_id`, `title`, `author`, `created`, `last_updated`, `gates` 等）必须保持不变
- 正文非状态相关内容（概述、文档导航、关键约束、非目标等）必须保持不变
- Gate 进展表格（显示 scope/spec/plan/test/code/audit 各个 gate 的状态）必须保持不变，因为这些是独立检查点状态
- Frontmatter `status` 字段的标准枚举值（`todo`, `in_progress`, `completed`, `archived` 等）必须继续使用

**Scope:**
所有不涉及正文 `- **状态**: xxx` 行的内容都应完全不受影响。这包括：
- Frontmatter 的所有字段（除了验证 `status` 字段存在）
- 正文的标题、段落、列表、代码块、链接等
- Gate 进展表格的所有行
- 文档导航部分的所有链接

## Hypothesized Root Cause

基于审计结果和文件内容分析，最可能的根本原因是：

1. **历史遗留问题**: 早期 Task README 模板可能同时包含 frontmatter 和正文状态字段，导致新建任务时自动生成两个字段

2. **维护不同步**: 开发者在任务进展过程中更新了 frontmatter `status` 字段（如从 `in_progress` 改为 `completed`），但忘记同步更新正文的 `**状态**:` 字段

3. **缺乏明确规范**: 系统没有明确文档规定 frontmatter `status` 是唯一真源，导致开发者不清楚应该维护哪个字段

4. **模板不一致**: 不同时期创建的任务可能使用了不同版本的模板，有些包含正文状态字段，有些不包含（如 `2026-02-28-vibe-skills/README.md` 就没有正文状态字段）

## Correctness Properties

Property 1: Fault Condition - 消除状态字段冲突和冗余

_For any_ Task README 文件，如果该文件包含 frontmatter `status` 字段和正文 `**状态**:` 字段，修复后的文件 SHALL 将正文状态字段替换为指引文本 `见 frontmatter \`status\` 字段（唯一真源）` 或完全删除该行，确保 frontmatter `status` 成为唯一真源。

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation - 保持非状态内容不变

_For any_ Task README 文件中不属于正文 `**状态**:` 字段的内容（frontmatter 其他字段、正文其他内容、Gate 进展表格），修复后的文件 SHALL 保持这些内容完全不变，确保只修改状态字段相关内容。

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

假设根本原因分析正确，需要对以下文件进行修复：

**Phase A: 高优先级冲突文件（必须修复）**

**File 1**: `docs/tasks/2026-03-02-cross-worktree-task-registry/README.md`

**Current State**:
- Frontmatter: `status: "completed"`
- 正文: `- **状态**: In Progress`

**Specific Changes**:
1. **定位正文状态字段**: 找到 `## 当前状态` 部分下的 `- **状态**: In Progress` 行
2. **替换为指引文本**: 将该行替换为 `- **状态**: 见 frontmatter \`status\` 字段（唯一真源）`
3. **验证 frontmatter**: 确认 frontmatter `status: "completed"` 字段存在且正确

**File 2**: `docs/tasks/2026-03-01-session-lifecycle/README.md`

**Current State**:
- Frontmatter: `status: "completed"`
- 正文: `- **状态**: In Progress`

**Specific Changes**:
1. **定位正文状态字段**: 找到 `## 当前状态` 部分下的 `- **状态**: In Progress` 行
2. **替换为指引文本**: 将该行替换为 `- **状态**: 见 frontmatter \`status\` 字段（唯一真源）`
3. **验证 frontmatter**: 确认 frontmatter `status: "completed"` 字段存在且正确

**Phase B: 中优先级冗余文件（建议修复）**

**File 3**: `docs/tasks/2026-03-02-command-slash-alignment/README.md`

**Current State**:
- Frontmatter: `status: "todo"`
- 正文: `- **状态**: Todo`

**Specific Changes**:
1. **定位正文状态字段**: 找到 `## 当前状态` 部分下的 `- **状态**: Todo` 行
2. **替换为指引文本**: 将该行替换为 `- **状态**: 见 frontmatter \`status\` 字段（唯一真源）`

**File 4-6**: Archived 任务文件
- `docs/tasks/2026-02-26-agent-dev-refactor/README.md`
- `docs/tasks/2026-02-25-vibe-v2-final/README.md`
- `docs/tasks/2026-02-21-save-command/README.md`
- `docs/tasks/2026-02-26-vibe-engine/README.md`
- `docs/tasks/2026-02-21-vibe-architecture/README.md`

**Specific Changes** (统一处理):
1. **定位正文状态字段**: 找到 `## 当前状态` 部分下的 `- **状态**: Archived` 行
2. **替换为指引文本**: 将该行替换为 `- **状态**: 见 frontmatter \`status\` 字段（唯一真源）`

**Note**: `docs/tasks/2026-03-02-rotate-alignment/README.md` 已经使用正确的指引文本格式，无需修改。

### Implementation Pattern

所有修复遵循统一模式：
```markdown
## 当前状态
- **层级**: [保持不变]
- **状态**: 见 frontmatter `status` 字段（唯一真源）
- **最后更新**: [保持不变]
```

## Testing Strategy

### Validation Approach

测试策略采用两阶段方法：首先在未修复代码上运行探索性测试以确认 bug 存在，然后验证修复后的文件符合预期行为并保持其他内容不变。

### Exploratory Fault Condition Checking

**Goal**: 在实施修复之前，通过测试确认 bug 的存在。验证根本原因分析是否正确。如果测试结果与假设不符，需要重新分析。

**Test Plan**: 编写脚本扫描所有 Task README 文件，检测同时包含 frontmatter `status` 字段和正文 `**状态**:` 字段的文件，并报告冲突和冗余情况。在未修复的代码上运行此脚本，观察失败模式。

**Test Cases**:
1. **冲突检测测试**: 扫描所有文件，找出 frontmatter 和正文状态值不一致的文件（预期找到 2 个高优先级冲突文件）
2. **冗余检测测试**: 扫描所有文件，找出同时包含两个状态字段的文件（预期找到所有 6+ 个文件）
3. **模式匹配测试**: 验证正则表达式 `- \*\*状态\*\*: .+` 能正确匹配正文状态字段（预期在未修复代码上成功匹配）
4. **边缘情况测试**: 检查已经使用指引文本的文件（如 `rotate-alignment`），确认其格式正确（预期通过）

**Expected Counterexamples**:
- `cross-worktree-task-registry/README.md`: frontmatter=`completed`, 正文=`In Progress` (冲突)
- `session-lifecycle/README.md`: frontmatter=`completed`, 正文=`In Progress` (冲突)
- `command-slash-alignment/README.md`: frontmatter=`todo`, 正文=`Todo` (冗余)
- 多个 archived 任务: frontmatter=`archived`, 正文=`Archived` (冗余)

可能的根本原因：历史模板包含正文状态字段，维护时未同步更新，缺乏明确规范。

### Fix Checking

**Goal**: 验证对于所有存在 bug 条件的输入（同时包含两个状态字段的文件），修复后的文件产生预期行为（正文使用指引文本或删除状态字段）。

**Pseudocode:**
```
FOR ALL file WHERE isBugCondition(file) DO
  fixedFile := applyFix(file)
  ASSERT NOT fixedFile.hasConflictingStatus()
  ASSERT fixedFile.bodyStatusField == "见 frontmatter `status` 字段（唯一真源）"
     OR NOT fixedFile.hasBodyStatusField()
  ASSERT fixedFile.frontmatterStatus IS VALID_ENUM
END FOR
```

### Preservation Checking

**Goal**: 验证对于所有不属于正文状态字段的内容，修复后的文件产生与原始文件相同的结果。

**Pseudocode:**
```
FOR ALL file WHERE isBugCondition(file) DO
  originalFile := readFile(file)
  fixedFile := applyFix(file)
  
  ASSERT fixedFile.frontmatter (except status) == originalFile.frontmatter (except status)
  ASSERT fixedFile.frontmatterStatus == originalFile.frontmatterStatus
  ASSERT fixedFile.bodyContentExceptStatus == originalFile.bodyContentExceptStatus
  ASSERT fixedFile.gateProgressTable == originalFile.gateProgressTable
END FOR
```

**Testing Approach**: 使用 property-based testing 进行 preservation checking，因为：
- 自动生成多个测试用例覆盖所有受影响文件
- 捕获手动单元测试可能遗漏的边缘情况
- 提供强保证：所有非状态字段内容在修复后保持不变

**Test Plan**: 首先在未修复代码上观察各文件的 frontmatter 和正文内容，然后编写 property-based 测试捕获这些行为，确保修复后保持不变。

**Test Cases**:
1. **Frontmatter 保持测试**: 验证修复后 frontmatter 的所有字段（除了验证 `status` 存在）与原文件完全一致
2. **正文内容保持测试**: 验证修复后正文的标题、段落、列表（除了状态行）、代码块、链接等与原文件完全一致
3. **Gate 表格保持测试**: 验证修复后 Gate 进展表格的所有行与原文件完全一致
4. **文档导航保持测试**: 验证修复后文档导航部分的所有链接与原文件完全一致

### Unit Tests

- 测试正则表达式能正确匹配正文状态字段模式 `- \*\*状态\*\*: .+`
- 测试指引文本替换逻辑对各种状态值（`In Progress`, `Todo`, `Archived` 等）都能正确工作
- 测试边缘情况：文件没有 `## 当前状态` 部分、状态字段在不同位置、状态字段有额外空格等
- 测试 frontmatter 解析能正确提取 `status` 字段值

### Property-Based Tests

- 生成随机 Task README 文件结构，验证修复逻辑只修改正文状态字段，不影响其他内容
- 生成随机 frontmatter 配置，验证修复后 frontmatter 保持不变（除了验证 `status` 存在）
- 生成随机正文内容组合，验证修复后非状态内容完全保持不变
- 测试多个文件批量修复场景，验证每个文件独立修复且互不影响

### Integration Tests

- 测试完整修复流程：扫描 → 检测冲突/冗余 → 应用修复 → 验证结果
- 测试修复后的文件能被现有工具正确解析（如 YAML parser、Markdown parser）
- 测试修复后的文件在 Git 中的 diff 只包含预期的状态字段变更
- 测试修复后的文件符合 Task README 格式规范（如果存在规范文档）
