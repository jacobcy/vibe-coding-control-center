# Process Plane PLAN (Migration)

## 目标
建立 provider 可替换路由架构，并把 Supervisor 六层作为流程平面内部标准。

## 阶段任务
1. 定义 provider 枚举与 `provider_ref` 规范
2. 定义路由策略输入（任务类型/风险/人工策略/资源）
3. 定义降级路径（provider 不可用 -> manual）
4. 定义 Supervisor 六层与外部 provider 的映射（仅流程平面内部）
5. 输出 provider adapter 模板（文档）

## 允许改动
仅 `v3/process-plane/*` 与 `v3/MASTER-PRD.md` 相关段落。

## 产出
- provider 接入清单
- 路由策略矩阵
- 降级与升级策略说明
