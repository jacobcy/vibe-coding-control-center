---
document_type: standard
title: Doc-Text Regression Test Governance Standard
status: active
scope: test-governance
authority:
  - doc-text-test-entry-criteria
  - doc-text-test-budget
  - doc-text-test-separation
author: Claude Sonnet 4.5
created: 2026-03-13
last_updated: 2026-03-14
related_docs:
  - docs/standards/glossary.md
  - docs/standards/v2/skill-standard.md
  - tests/README.md
---

# Doc-Text Regression Test Governance Standard

## 1. Scope

本文档定义文档文本回归测试的边界、准入标准、数量预算和治理规则。

本文档**不**定义行为测试、contract test 或集成测试的编写规范。

## 2. Definition

### 2.1 Doc-Text Regression Test

- **定义**: 通过文本匹配检查文档内容的测试，用于锁定关键语义和防止概念漂移。
- **特征**:
  - 使用 `rg`/`grep` 搜索文档中的特定文本
  - 断言特定短语或术语存在/不存在
  - 不测试 Shell 行为或命令输出
  - 主要锁定 `.md` 文件内容

### 2.2 Behavior Test

- **定义**: 测试 Shell 命令行为、输出格式、退出码、副作用等实际行为的测试。
- **特征**:
  - 调用 `vibe` 命令或 Shell 函数
  - 断言命令退出码、输出内容、文件变化
  - 测试业务逻辑和数据流

## 3. Separation Principle

**核心原则**: Doc-text tests 和 behavior tests 必须物理分离，不得混在同一文件。

**理由**:
1. 避免混淆 TDD 适用范围
2. 防止纯文案改动被误认为需要测试先行
3. 清晰表达测试意图和测试对象
4. 便于独立执行和治理

**强制要求**:
- Doc-text tests 只能放在 `tests/doc-text/` 目录
- Behavior tests 只能放在 `tests/` 下其他目录
- `tests/skills/test_skills.bats` 不得再添加文本匹配测试

## 4. Entry Criteria

### 4.1 允许新增 Doc-Text Test 的场景

新增 doc-text test 前必须满足以下**至少一项**:

1. **关键语义冻结**: 文档中的术语定义已被标记为稳定，不得随意改动
   - 例如: `glossary.md` 中的术语定义
   - 例如: `SOUL.md` 中的核心原则

2. **高风险承诺文本**: 文档中的特定措辞会直接影响 agent 行为
   - 例如: skill 文档中的 "Use when..." 触发条件
   - 例如: workflow 文档中的 "必须先..." 流程约束

3. **历史漂移问题**: 特定文案曾反复漂移并造成问题
   - 例如: 术语曾被错误替换或删除
   - 例如: 关键流程约束曾被意外移除

### 4.2 禁止新增 Doc-Text Test 的场景

以下场景**不得**添加 doc-text test:

1. **低风险润色**: 纯粹的措辞改进、语法修正、表达优化
   - 不应锁定具体措辞，只应锁定语义要点

2. **可被行为测试覆盖**: 如果 Shell 命令行为已经测试了该语义
   - 例如: 命令输出的帮助文本已通过行为测试验证

3. **重复断言**: 同一语义已在其他 doc-text test 中断言
   - 必须复用或合并现有测试

4. **非真源文档**: 在 plan、memo、archive 中复制的文本
   - 只锁定真源文档，不锁定派生内容

### 4.3 替代策略优先级

在考虑新增 doc-text test 前，必须先评估以下替代方案:

1. **优先级行为测试**: 如果可以编写行为测试，优先行为测试
2. **次优先单一真源**: 将语义集中到单一真源文档，减少需要锁定的位置
3. **最后才考虑文本断言**: 只有上述方案不可行时才添加 doc-text test

## 5. Budget and Limits

### 5.1 文件数量预算

- `tests/doc-text/` 目录下的测试文件数量上限: **10 个文件**
- 单个文件中的测试函数数量上限: **20 个测试**

### 5.2 新增测试检查清单

每次新增 doc-text test 时，必须在 commit message 或 PR 描述中填写:

```
Doc-Text Test Entry Checklist:
- [ ] 满足准入标准第 X 条
- [ ] 无法被行为测试替代
- [ ] 无法复用现有 doc-text test
- [ ] 未超出数量预算
```

### 5.3 整合策略

当测试数量接近上限时，必须优先整合而非扩容:

1. **合并同类测试**: 多个测试锁定相同文档的相近语义时，合并为一个测试
2. **抽象语义检查**: 从具体措辞检查改为语义模式检查（如正则表达式）
3. **删除过时测试**: 文档已删除或语义已变更的测试必须移除

## 6. Test Structure

### 6.1 文件命名约定

```
tests/doc-text/
  test_terminology_locks.bats    # 术语锁定测试
  test_workflow_constraints.bats # 流程约束文本测试
  test_skill_triggers.bats       # Skill 触发条件文本测试
  test_standard_semantics.bats   # 标准文档语义测试
```

### 6.2 测试函数命名约定

```bash
@test "doc-text: <document-path> locks <semantic-concept>" {
  # ...
}
```

示例:
```bash
@test "doc-text: glossary.md locks 'repo issue' term definition" {
  run rg -n "repo issue.*特指.*GitHub repository issue" "$REPO_ROOT/docs/standards/glossary.md"
  [ "$status" -eq 0 ]
}
```

### 6.3 测试内容约定

每个 doc-text test 必须包含注释说明:

```bash
# Reason: <为什么需要这个文本锁定>
# Entry Criterion: <满足第几条准入标准>
# Alternative Considered: <考虑过哪些替代方案>
@test "doc-text: ..." {
  # ...
}
```

## 7. Execution

### 7.1 独立执行入口

Doc-text tests 必须可独立执行:

```bash
# 执行所有 doc-text tests
bats tests/doc-text/

# 执行特定类别
bats tests/doc-text/test_terminology_locks.bats

# 排除 doc-text tests 执行其他测试
bats tests/ --filter '!^tests/doc-text/'
```

### 7.2 CI 集成

在 CI 中，doc-text tests 必须作为独立 job 或 stage:

```yaml
test-behavior:
  script: bats tests/ --filter '!^tests/doc-text/'

test-doc-text:
  script: bats tests/doc-text/
```

## 8. Maintenance

### 8.1 Quarterly Review

每季度必须审查所有 doc-text tests:

1. 验证测试仍然锁定有效语义
2. 检查是否有文档已删除或重构
3. 评估是否可以删除或整合测试
4. 确认未超出预算限制

### 8.2 Document Changes

当真源文档发生变更时:

1. **新增语义**: 评估是否需要新增 doc-text test（遵循准入标准）
2. **修改语义**: 更新对应的 doc-text test
3. **删除语义**: 删除对应的 doc-text test

## 9. Restrictions

- 不得为纯文案润色添加 doc-text test
- 不得在没有 entry criterion 的情况下添加 doc-text test
- 不得在 doc-text test 中调用 Shell 命令测试行为
- 不得绕过预算限制创建新的 doc-text test 文件
- 不得在 `tests/skills/test_skills.bats` 中继续添加文本匹配测试

## 10. Migration

现有 `tests/skills/test_skills.bats` 中的文本匹配测试必须迁移到 `tests/doc-text/`。

迁移步骤见实施计划文档。

## 11. Change Checklist

修改本标准或相关测试时，逐项确认:

- [ ] 是否明确了 doc-text test 和 behavior test 的边界？
- [ ] 是否定义了清晰的准入标准？
- [ ] 是否设置了数量预算和限制？
- [ ] 是否规定了独立执行入口？
- [ ] 是否建立了季度审查机制？
- [ ] 是否为现有测试制定了迁移路径？