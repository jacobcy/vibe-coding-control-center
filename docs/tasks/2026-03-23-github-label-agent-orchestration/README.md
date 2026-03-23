# GitHub Label 状态机实施

**创建时间**: 2026-03-23
**状态**: In Progress
**分支**: `feature/github-label-agent-orchestration`

---

## 目标

实现 GitHub Label 状态机核心，为 flow/agent 命令组提供标签支持。

---

## 标签分类

### 静态标签（分类用）

由 `labeler.yml` 自动添加，不参与状态机：

- `type/*` - 工作类型
- `scope/*` - 改动范围
- `priority/*` - 优先级
- `component/*` - 组件

### 动态标签（状态机）

由 `LabelService` 管理，反映 flow/agent 状态：

- `state/ready` → `state/claimed` → `state/in-progress` → `state/review` → `state/done`
- 旁路：`state/blocked`, `state/handoff`

---

## 文档导航

| 层级 | 文档 | 状态 |
|------|------|------|
| 标准 | [github-labels-standard.md](../../standards/github-labels-standard.md) | ✅ 已存在 |
| **Spec** | [spec-v1-label-state-machine.md](./spec-v1-label-state-machine.md) | ✅ 本任务 |

---

## 实施范围

### 本次实现

- `IssueState` 枚举
- `StateTransition` 模型
- `LabelService` Python API
- GitHub Actions workflow（PR 合并自动设置 done）

### 后续实现（不在本次）

- flow 命令组集成
- agent 命令组集成
- Handoff 联动

---

## 文件清单

| 文件 | 操作 |
|------|------|
| `src/vibe3/models/orchestration.py` | 新建 |
| `src/vibe3/services/label_service.py` | 新建 |
| `src/vibe3/exceptions/orchestration.py` | 新建 |
| `.github/workflows/issue-state-sync.yml` | 新建 |

---

## 进度日志

| 日期 | 事件 |
|------|------|
| 2026-03-23 | 创建分支 `feature/github-label-agent-orchestration` |
| 2026-03-23 | 完成 Spec v1（精简范围） |