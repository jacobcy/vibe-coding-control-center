# Vibe-Center Review Conventions

> **Scope**: project scope — 追加到 user scope review.policy 之后
> **用途**: vibe-center 项目专属的审查约定

## 三层架构跨层检查

审查时检查 plan scope 是否覆盖所有相关层：
- `src/vibe3/services/`、`src/vibe3/ui/`、`src/vibe3/commands/`
- `tests/`、`docs/`
- 详见 `common.rules@project` 的「跨层一致性检查」

## 包级导入验证

审查涉及模块重组、re-export 修改、符号移动的 PR 时，验证包级导入无循环依赖。
详见 `plan.policy@project` 的「包级导入验证」。

## 模块化边界检查

- 所有跨模块导入必须通过公开 API（`__init__.py` 重导出）
- 不该有的深层导入（如 `from vibe3.roles.manager import X` 而非 `from vibe3.roles import X`）
- 新增导出必须更新 `__all__` 和 `_LAZY_IMPORTS`
