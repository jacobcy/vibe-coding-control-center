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
last_updated: 2026-06-02
related_docs:
  - docs/standards/glossary.md
  - v3/skill-standard.md
  - tests/README.md
---

# Doc-Text Regression Test Governance Standard (V3)

## 1. Scope

本文档定义文档文本回归测试的边界、准入标准、数量预算和治理规则。

本文档**不**定义行为测试、Contract Test 或集成测试的编写规范。

## 2. Definition

### 2.1 Doc-Text Regression Test

- **定义**: 通过文本匹配检查文档内容的测试，用于锁定关键语义和防止概念漂移。
- **特征**:
  - 使用 Python/pytest 配合 `grep` 或正则表达式搜索文档
  - 断言特定短语或术语存在/不存在
  - 不测试代码行为或命令输出
  - 主要锁定 `.md` 文件内容

### 2.2 Behavior Test

- **定义**: 测试系统命令行为、输出格式、状态变更、副作用等实际行为的测试。
- **特征**:
  - 调用 `vibe3` 命令、API 或内部服务
  - 断言状态码、输出内容、数据库变化
  - 测试业务逻辑和数据流

## 3. Separation Principle

**核心原则**: Doc-text tests 和 Behavior tests 必须物理分离，不得混在同一文件。

**理由**:
1. 避免混淆 TDD 适用范围
2. 防止纯文案改动被误认为需要测试先行
3. 清晰表达测试意图和测试对象
4. 便于独立执行和治理

**强制要求**:
- Doc-text tests 只能放在 `tests/vibe3/doc-text/` (或 V2 的 `tests/doc-text/`) 目录
- Behavior tests 只能放在 `tests/vibe3/` 下功能对应的目录
- 现有的行为测试文件中禁止包含纯文本匹配断言

## 4. Entry Criteria

### 4.1 允许新增 Doc-Text Test 的场景

新增 doc-text test 前必须满足以下**至少一项**:

1. **关键语义冻结**: 文档中的术语定义已被标记为稳定，不得随意改动
   - 例如: `glossary.md` 中的术语定义
   - 例如: `SOUL.md` 中的核心原则

2. **高风险承诺文本**: 文档中的特定措辞会直接影响 Agent 行为
   - 例如: Skill 文档中的 "Use when..." 触发条件
   - 例如: Workflow 文档中的 "必须先..." 流程约束

3. **历史漂移问题**: 特定文案曾反复漂移并造成问题
   - 例如: 术语曾被错误替换或删除
   - 例如: 关键流程约束曾被意外移除

### 4.2 禁止新增 Doc-Text Test 的场景

以下场景**不得**添加 doc-text test:

1. **低风险润色**: 纯粹的措辞改进、语法修正、表达优化
   - 不应锁定具体措辞，只应锁定语义要点

2. **可被行为测试覆盖**: 如果系统行为已经测试了该语义
   - 例如: 命令输出的帮助文本已通过行为测试验证

3. **重复断言**: 同一语义已在其他 doc-text test 中断言
   - 必须复用或合并现有测试

4. **非真源文档**: 在 plan、memo、archive 中复制的文本
   - 只锁定真源文档，不锁定派生内容

## 5. Budget and Limits

### 5.1 文件数量预算

- `tests/vibe3/doc-text/` 目录下的测试文件数量上限: **10 个文件**
- 单个文件中的测试函数数量上限: **20 个测试**

### 5.2 新增测试检查清单

每次新增 doc-text test 时，必须在 Commit Message 或 PR 描述中填写:

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
tests/vibe3/doc-text/
  test_terminology_locks.py    # 术语锁定测试
  test_workflow_constraints.py # 流程约束文本测试
  test_skill_triggers.py       # Skill 触发条件文本测试
  test_standard_semantics.py   # 标准文档语义测试
```

### 6.2 测试函数命名约定

```python
def test_doc_text_document_path_locks_semantic_concept():
    # ...
```

示例:
```python
def test_doc_text_glossary_locks_github_issue_term():
    content = read_doc("docs/standards/glossary.md")
    assert "GitHub issue" in content
    assert "GitHub repository issue" in content
```

### 6.3 测试内容约定

每个 doc-text test 必须包含注释说明:

```python
# Reason: <为什么需要这个文本锁定>
# Entry Criterion: <满足第几条准入标准>
# Alternative Considered: <考虑过哪些替代方案>
def test_doc_text_...():
    # ...
```

## 7. Execution

### 7.1 独立执行入口

Doc-text tests 必须可独立执行:

```bash
# 执行所有 V3 doc-text tests
uv run pytest tests/vibe3/doc-text/

# 执行特定类别
uv run pytest tests/vibe3/doc-text/test_terminology_locks.py
```

### 7.2 CI 集成

在 CI 中，doc-text tests 必须作为独立 Job 或 Stage:

```yaml
test-behavior:
  script: uv run pytest tests/vibe3/ --ignore=tests/vibe3/doc-text/

test-doc-text:
  script: uv run pytest tests/vibe3/doc-text/
```

## 8. Maintenance

### 8.1 Cron Supervisor Review

治理机制从“季度审查”迁移至 **Cron Supervisor** 模式:

1. **自动化探测**: 由 `vibe-audit` 或专门的治理 Agent 定期扫描文档变更。
2. **漂移预警**: 当检测到锁定的文档发生变更但测试未更新时，自动创建治理 Issue。
3. **预算审计**: 定期统计测试数量，超出预算时触发合并/删除任务。

### 8.2 Document Changes

当真源文档发生变更时:

1. **新增语义**: 评估是否需要新增 doc-text test（遵循准入标准）
2. **修改语义**: 更新对应的 doc-text test
3. **删除语义**: 删除对应的 doc-text test

## 9. Restrictions

- 不得为纯文案润色添加 doc-text test
- 不得在没有 entry criterion 的情况下添加 doc-text test
- 不得在 doc-text test 中直接调用复杂的业务逻辑
- 不得绕过预算限制创建新的 doc-text test 文件

## 10. Migration

现有 V2 `tests/doc-text/*.bats` 中的测试应逐步迁移到 V3 Python 实现，或在保持 V2 时确保遵循相同的准入与预算规则。

## 11. Change Checklist

修改本标准或相关测试时，逐项确认:

- [ ] 是否明确了 doc-text test 和 behavior test 的边界？
- [ ] 是否定义了清晰的准入标准？
- [ ] 是否设置了数量预算和限制？
- [ ] 是否规定了独立执行入口？
- [ ] 是否对接了 Cron Supervisor 机制？
