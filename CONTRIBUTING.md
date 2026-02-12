# Contributing

感谢你对 Vibe Coding Control Center 的贡献。

## 基本原则

- 请先阅读 `SOUL.md` 与 `CLAUDE.md`，遵循项目规则与工作流。
- 保持最小改动范围，避免无关重构。
- 变更需要有清晰的动机与说明，便于 review。

## 分支管理与保护

为了维护 `main` 分支的稳定性，我们实施了严格的分支保护规则（Rulesets）。
详细配置请参阅 [Branch Protection Rules](docs/governance/BRANCH_PROTECTION.md)。

- **禁止直接提交到 main**：所有变更必须通过 PR 合并。
- **强制代码审查**：所有 PR 必须经过至少一次 Review。
- **自动化检查**：必须通过所有测试与静态分析。

## 提交流程

1. 新建分支（避免直接在 main/master 上操作）。
2. 进行修改并自测（如有测试脚本请执行）。
3. 更新相关文档（README / docs / 变更说明）。
4. 提交前检查 `git status`，确保变更范围清晰。

## 代码与脚本规范

- 以可读性为先，保持一致的命名与日志风格。
- 关键路径使用已有的验证与安全函数（详见 `lib/utils.sh`）。
- 避免修改用户本地或系统级配置。

## 文档规范

- 中文为主，必要时可补充英文说明。
- 示例命令保持可执行性与一致性。

谢谢！
