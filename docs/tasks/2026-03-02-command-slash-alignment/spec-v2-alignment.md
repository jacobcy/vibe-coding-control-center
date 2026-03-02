---
task_id: "2026-03-02-command-slash-alignment"
document_type: technical_spec
title: "Slash vs Shell Command Alignment Spec"
author: "Antigravity Agent"
created: "2026-03-02"
last_updated: "2026-03-02"
status: draft
---

# Slash vs Shell Command Alignment Spec

## 1. 存储架构 (Storage Architecture)

- **持久化层**: 所有核心任务元数据（`registry.json`, `worktrees.json`）存储于 `$(_git_common_dir)/vibe/` 目录下。
- **共享数据**: 使用 `.git/vibe/shared/` 目录存放跨 worktree 共享的任务执行信息（如执行日志、中间过程），确保不污染当前代码工作区。
- **当前上下文**: 仅在当前工作区的 `.vibe/` 目录下存放指向共享数据的符号链接或轻量级 ID 引用。

## 2. 命令映射矩阵 (Command Mapping Matrix)

### 2.1 任务管理 (`/vibe-task` <-> `vibe task`)
| Slash 命令 | 映射 Shell 命令 | 职责 |
|------------|-----------------|------|
| `/vibe-task add` | `vibe task add` | 创建并上架新任务 |
| `/vibe-task list` | `vibe task list` | 查阅当前全局任务大盘（含动态 OpenSpec） |
| `/vibe-task sync` | `vibe task update --sync` | 主动从 OpenSpec 桥接并注册任务 |

### 2.2 流程生命周期 (`Flow/Vibe Guard`)
| Slash 命令 | 职责 | 实现逻辑 |
|------------|------|----------|
| `/vibe-new` | 入口与编排 | 1. 检查或创建 Registry 任务；2. 创建新 Worktree；3. 设置当前 Context；4. 从 `.git/vibe/shared/` 读取历史 |
| `/vibe-save` | 状态快照 | 强制记录当前 Flow 状态，保存对话线，圈定任务上下文 |
| `/vibe-continue` | 断点续传 | 检查 Registry 状态，恢复环境钩子，继续未完成的任务层级 |
| `/vibe-commit` | 提交产出 | 运行测试，生成 PR，准备 Audit Gate 数据 |
| `/vibe-done` | 归档收尾 | 1. 标记任务为 completed；2. 冻结代码；3. 销毁本地与远端分支；4. 清理 Worktree |

### 2.3 审计与检查 (`/vibe-check` <-> `vibe doctor/check`)
| Slash 命令 | 职责 | 操作行为 |
|------------|------|----------|
| `/vibe-check` | 全面审计 | 1. 检查 Registry 与 OpenSpec 的状态一致性；2. 将已完成的任务文件移入 `archive`；3. 删除远端无用僵尸分支；4. 任务健康度审计 |

## 3. 实现准则 (Implementation Rules)

1.  **拒绝过度工程化**: 只有 Shell 命令不支持的逻辑（如 AI 编排、对话存储）才允许在 Slash 层实现。
2.  **数据隔离**: 工作区 `.vibe/` 内禁止写入大型 JSON 数据，只保留会话引用。
3.  **原子化交互**: Slash 命令应包裹 Shell 调用，一个 Slash 动作对应一个或多个原子 Shell 原子命令。
4.  **远程同步**: `done` 和 `check` 必须通过 Shell 调用 `git push --delete` 来确保云端一致性。
