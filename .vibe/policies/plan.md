# Vibe Center Plan Conventions

> **Scope**: project scope — 追加到 user scope plan.policy 之后
> **用途**: vibe-center 项目专属的规划约定

## 跨项目占位测试

此文件验证 `.vibe/policies/plan.md` 的 project-scope 加载机制：
- 跨项目执行时，该文件不会被加载（仅当前 repo 的 `.vibe/` 生效）
- vibe-center 自身开发时，plan.policy 自动合并此文件到 prompt 末尾
- 加载由 `build_policy_section()` 的 append 语义统一处理，无需额外 provider 或 recipe 配置

TODO: 随项目演进，将 vibe-center 专属的规划约定补充到此文件。
