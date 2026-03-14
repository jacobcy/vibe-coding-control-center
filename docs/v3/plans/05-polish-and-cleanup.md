# 05. Polish And Cleanup

目标：在 3.0 核心能力上线并稳定运行后，进行收尾工作，清理战场。

## 必读输入

- `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`
- `docs/v3/plans/04-handoff-and-cutover.md`

## 这一轮只做这些事：

- **归档 2.x 遗留代码**：
  - 将 `lib/` 移动到 `lib2/` 或进行深度清理
  - 将 `tests/` 移动到 `tests2/`
  - 更新所有相关引用
- **性能优化**：
  - 优化 SQLite 查询性能
  - 优化 GitHub CLI / GraphQL 调用，减少延迟
- **文档与教程**：
  - 更新项目根目录的 `README.md`，正式声明 3.0 为默认版本
  - 编写 `docs/v3/onboarding.md` 指导新 agent 或人类如何使用新链
  - 更新 `AGENTS.md`，将 3.0 主链设为默认 Protocol
- **异常链路补全**：
  - 补齐所有“待实现”的修正与撤销命令（`pr close`, `flow abort` 等）

## 真源与边界

- 3.0 已成为唯一推荐路径
- 旧路径不再维护新功能
- 文档与代码库状态保持一致

## 建议交付物

- 清理后的目录结构
- 性能评估报告
- 完整的 3.0 使用文档
- 所有子命令的完整闭环实现

## 验证证据

- `vibe` 命令全路径测试通过
- `lib/` 目录已成功迁移或归档
- 文档已同步更新

## 最终收口

至此，Vibe 3.0 并行重建工作全部完成。
