# Doc-Text Regression Tests

本目录包含文档文本回归测试，用于锁定关键语义和防止概念漂移。

## 定义

Doc-text regression tests 通过文本匹配检查文档内容，不测试 Shell 行为。

## 与 Behavior Tests 的区别

- **Doc-text tests**: 检查文档中的文本是否存在、是否符合预期模式
- **Behavior tests**: 测试命令行为、输出、退出码、副作用

## 何时添加测试

**必须满足准入标准**（见 `docs/standards/doc-text-test-governance.md`）:

1. 关键语义冻结（如术语定义）
2. 高风险承诺文本（如 agent 触发条件）
3. 历史漂移问题

## 何时不添加测试

- 低风险润色
- 可被行为测试覆盖
- 重复断言
- 非真源文档

## 运行测试

```bash
# 执行所有 doc-text tests
bats tests/doc-text/

# 执行特定文件
bats tests/doc-text/test_terminology_locks.bats
```

## 预算限制

- 文件数量上限: 10 个文件
- 单文件测试数量上限: 20 个测试
- 超出前必须优先整合而非扩容

## 检查清单

添加新测试前必须填写:

```
Doc-Text Test Entry Checklist:
- [ ] 满足准入标准第 X 条
- [ ] 无法被行为测试替代
- [ ] 无法复用现有 doc-text test
- [ ] 未超出数量预算
```

## 参见

- [Doc-Text Test Governance Standard](../../docs/standards/doc-text-test-governance.md)
- [Issue #134](https://github.com/jacobcy/vibe-coding-control-center/issues/134)
