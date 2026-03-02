# Control Plane PLAN (Migration)

## 目标
将 V2 任务控制语义迁移到 V3 canonical 规范，保持兼容并消除命名混乱。

## 阶段任务
1. 对齐命令名：文档统一为 `task create` / `flow start`
2. 对齐状态机：统一五态状态机
3. 对齐字段：压缩为最小字段集合
4. 建立兼容映射：
   - `task add` -> `task create`（迁移期别名）
   - `vibe new` -> `flow start`（迁移期别名）
5. 输出迁移检查表（不改代码）

## 允许改动
仅 `v3/control-plane/*` 与 `v3/MASTER-PRD.md` 相关段落。

## 产出
- 命令映射表
- 字段映射表
- 状态迁移表
