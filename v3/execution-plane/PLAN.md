# Execution Plane PLAN (Migration)

## 目标
把 V2 aliases 的执行能力以 V3 契约方式固化，支持 human/openclaw 双执行者。

## 阶段任务
1. 能力盘点：worktree/tmux/recover 命令矩阵
2. 命名对齐：worktree/session 统一命名规则
3. 回写对齐：统一 `resolved_*` 字段
4. 错误语义统一：创建失败、恢复失败、冲突处理
5. 生成 OpenClaw skill 接入草案（文档）

## 允许改动
仅 `v3/execution-plane/*` 与 `v3/MASTER-PRD.md` 相关段落。

## 产出
- 命令矩阵
- 回写 schema
- 恢复流程模板
