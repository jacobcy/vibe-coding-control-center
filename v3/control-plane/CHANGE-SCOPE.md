# Control Plane Allowed Paths

## 当前阶段

V3 架构迁移阶段（文档优先）：只允许在 `v3/` 目录内修改；允许读取/拷贝 V2 内容用于迁移。

## 允许修改

- `v3/control-plane/*`
- `v3/MASTER-PRD.md`（仅接口与命名决策段）

## 禁止修改

- `config/aliases.sh`
- `config/aliases/*`
- `skills/*`（除非跨层协议评审通过）
- `bin/*`
- `lib/*`
- `tests/*`
- `docs/*`（V2 文档保持不动）

## 跨层变更规则

如需新增字段影响 Execution/Process，必须先更新 `v3/MASTER-PRD.md` 接口契约章节。
