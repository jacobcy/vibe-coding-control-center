# Manager

`manager/` 现在只保留 manager 角色自身的最小业务壳，不再拥有独立执行框架。

统一主线已经变成：

- runtime/server: 注册角色服务并触发 polling
- domain: 把事件翻译成 manager request
- execution: 处理 flow scene / worktree / lifecycle / capacity / launch / completion gate
- environment: 提供 worktree 与 session 原语

## 当前仅保留的 manager 职责

- `manager_run_service.py`
  - `internal manager` 同步入口
  - 调用 execution 主线后回收同步执行结果
- `prompts.py`
  - manager prompt / recipe / command 渲染

## 已迁出的职责

- flow scene orchestration → `execution/flow_dispatch.py`
- session naming → `environment/session_naming.py`
- manager async dispatch request → `execution/role_services.py`
- completion gate → `execution/gates.py`
- manager executor shell → 已删除
- worktree 启动控制 → `execution + environment`

## 迁移目标

后续继续收敛后，`manager/` 应进一步退化为：

- manager prompt 业务规则
- 一个很薄的同步 CLI 壳

当同类角色都迁完后，`manager/` 目录本身也应可被移除或并入更通用模块。
