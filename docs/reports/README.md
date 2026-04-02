# Reports 目录

本目录保留历史报告样例和旧链接兼容说明，不再作为新的正式报告落点。

新的 Agent 报告应统一写入 `.agent/reports/`。

## 目录用途

| 目录 | 用途 | Git 追踪 |
|------|------|----------|
| `docs/reports/` | 历史报告样例 / 旧链接兼容 | ✅ 是 |
| `docs/plans/` | 历史计划样例 / 旧链接兼容 | ✅ 是 |
| `.agent/reports/` | Agent 生成的临时报告 | ❌ 否 |
| `.agent/plans/` | Agent 生成的临时计划 | ❌ 否 |
| `temp/` | 临时测试文件和脚本 | ❌ 否 |

## 文档类型示例

### docs/reports/（历史报告样例）

- 项目分析报告
- 技术调研报告
- 性能评估报告
- 代码审查总结
- 发布总结报告

### .agent/reports/（临时报告）

- Agent 自动生成的检查报告
- Rules 冲突检测报告
- 临时分析结果
- 调试报告

### temp/（临时文件）

- 测试脚本
- 调试输出
- 实验性代码
- 临时数据文件

## 参考规则

详见 [agent-document-lifecycle-standard.md](../standards/agent-document-lifecycle-standard.md)。

## 版本历史

| 日期 | 变更 |
|------|------|
| 2026-03-18 | 创建目录，定义用途 |
