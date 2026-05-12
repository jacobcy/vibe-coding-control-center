# Vibe PR Review Skill - 开发文档

## 版本历史

- **v2026-05-12**: 修复 Phase 0 Backlog 约束、Phase 2 agent idle 处理、Phase 5 执行模式说明
- **v2026-04-27**: 基于 PR #842 稳定版本重组（执行顺序组织）

---

## 改进摘要

**本次改进解决的核心问题**：

1. **Phase 0 Backlog 约束缺失** → 现在强制创建所有 Phase 1-5 的 Backlog task，防止流程跳过
2. **agent idle 处理缺失** → 现在收到 idle 通知后自动检查并重新握手，无需用户干预
3. **Phase 5 执行模式说明缺失** → 现在明确说明 ask-each / auto-decide / auto-fix / comment-only 四种模式的区别和适用场景

**关键设计决策**：

- **混合 Backlog 创建策略**：Phase 0 创建骨架 task，各 Phase 结束时补充详细 metadata
- **全自动化 agent idle 处理**：无需用户干预，自动检测、诊断、重新握手
- **渐进式执行模式**：从最安全的 ask-each 到高效的 auto-fix，用户可根据风险偏好选择

---

## 技术实现说明

详细实现规范见：
- **SKILL.md** - Agent执行主文档
- **references/backlog-task-templates.yaml** - Phase 1-5 TaskCreate 模板
- **references/execution-modes.md** - 执行模式详细说明
- **references/execution-reference.md** - 消息样例与约束机制
- **references/recovery-playbook.md** - 异常恢复流程
