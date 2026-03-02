# Process Plane Allowed Paths

## 当前阶段

V3 架构迁移阶段（文档优先）：只允许在 `v3/` 目录内修改；允许读取/拷贝 V2 内容用于迁移。

## 允许修改

- `v3/process-plane/*`
- `v3/MASTER-PRD.md`（仅接口与命名决策段）

## 禁止修改

- `config/aliases.sh`
- `config/aliases/*`
- `lib/task.sh`
- `lib/flow.sh`
- `skills/*`
- `.agent/workflows/*`
- `docs/*`（V2 文档保持不动）

## 跨层变更规则

若 provider 输出字段变化，必须先更新 `v3/MASTER-PRD.md` 的 Control <-> Process 契约。
