# Spec: GitHub Label 状态机

**版本**: v1
**状态**: Draft
**创建时间**: 2026-03-23
**依赖**: `docs/standards/github-labels-standard.md`

---

## 1. 目标

实现 GitHub Label 状态机核心：
1. 定义 `state/*` 动态标签的状态迁移规则
2. 实现 `LabelService` Python API
3. 定义消费接口（供 flow/agent 命令组调用）
4. 定义 GitHub Actions workflow 自动化

---

## 2. 标签分类

### 2.1 静态标签（分类用）

由 `labeler.yml` 自动添加，不参与状态机：

| 前缀 | 用途 | 示例 |
|------|------|------|
| `type/*` | 工作类型 | `type/feature`, `type/fix` |
| `scope/*` | 改动范围 | `scope/python`, `scope/shell` |
| `priority/*` | 优先级 | `priority/high`, `priority/low` |
| `component/*` | 组件 | `component/cli`, `component/flow` |

### 2.2 动态标签（状态机）

由 `LabelService` 管理，反映 flow/agent 状态：

| 标签 | 含义 | 触发场景 |
|------|------|----------|
| `state/ready` | 可认领 | issue 创建，flow 绑定 |
| `state/claimed` | 已认领 | agent plan |
| `state/in-progress` | 执行中 | agent run |
| `state/blocked` | 阻塞中 | flow blocked |
| `state/handoff` | 待交接 | agent 退出 |
| `state/review` | 待审核 | agent review / PR 创建 |
| `state/merge-ready` | 可合并 | review 通过 |
| `state/done` | 已完成 | PR 合并 / flow done |

---

## 3. 状态迁移规则

### 3.1 迁移表

```
ready ──────► claimed ──────► in-progress ──────► review ──────► merge-ready ──────► done
                 │                 │                 │
                 │                 ▼                 │
                 │            blocked                │
                 │                 │                 │
                 │                 ▼                 │
                 │            handoff ◄──────────────┘
                 │                 │
                 └─────────────────┘
```

### 3.2 允许的迁移

```python
ALLOWED_TRANSITIONS: set[tuple[IssueState, IssueState]] = {
    # 主链
    (IssueState.READY, IssueState.CLAIMED),
    (IssueState.CLAIMED, IssueState.IN_PROGRESS),
    (IssueState.IN_PROGRESS, IssueState.REVIEW),
    (IssueState.REVIEW, IssueState.MERGE_READY),
    (IssueState.MERGE_READY, IssueState.DONE),
    
    # 旁路
    (IssueState.IN_PROGRESS, IssueState.BLOCKED),
    (IssueState.BLOCKED, IssueState.IN_PROGRESS),
    (IssueState.IN_PROGRESS, IssueState.HANDOFF),
    (IssueState.HANDOFF, IssueState.IN_PROGRESS),
    (IssueState.REVIEW, IssueState.IN_PROGRESS),
}
```

### 3.3 非法迁移

以下迁移需要 `force=True`：

```python
FORBIDDEN_TRANSITIONS: set[tuple[IssueState, IssueState]] = {
    (IssueState.READY, IssueState.DONE),
    (IssueState.CLAIMED, IssueState.DONE),
    (IssueState.BLOCKED, IssueState.DONE),
    (IssueState.HANDOFF, IssueState.DONE),
}
```

---

## 4. LabelService API

### 4.1 数据模型

```python
# src/vibe3/models/orchestration.py

from enum import Enum
from datetime import datetime
from pydantic import BaseModel

class IssueState(str, Enum):
    """编排状态枚举，映射到 GitHub label: state/{value}"""
    READY = "ready"
    CLAIMED = "claimed"
    IN_PROGRESS = "in-progress"
    BLOCKED = "blocked"
    HANDOFF = "handoff"
    REVIEW = "review"
    MERGE_READY = "merge-ready"
    DONE = "done"
    
    def to_label(self) -> str:
        """转换为 GitHub label 名称"""
        return f"state/{self.value}"
    
    @classmethod
    def from_label(cls, label: str) -> "IssueState | None":
        """从 GitHub label 解析状态"""
        if label.startswith("state/"):
            try:
                return cls(label[6:])
            except ValueError:
                pass
        return None


class StateTransition(BaseModel):
    """状态迁移记录"""
    issue_number: int
    from_state: IssueState | None
    to_state: IssueState
    actor: str
    timestamp: datetime
    forced: bool = False
```

### 4.2 服务接口

```python
# src/vibe3/services/label_service.py

from typing import Protocol

class LabelService:
    """GitHub state/* 标签操作服务。
    
    这是状态机核心，提供 Python API 供其他服务调用。
    不暴露 CLI 命令。
    """
    
    def get_state(self, issue_number: int) -> IssueState | None:
        """获取 issue 当前的编排状态。
        
        Returns:
            IssueState: 当前状态
            None: 未找到 state/* 标签
        """
    
    def transition(
        self,
        issue_number: int,
        to_state: IssueState,
        actor: str,
        force: bool = False,
    ) -> StateTransition:
        """执行状态迁移。
        
        Args:
            issue_number: GitHub issue 编号
            to_state: 目标状态
            actor: 执行者标识（如 "flow:blocked", "agent:run"）
            force: 跳过迁移规则校验
        
        Returns:
            StateTransition: 迁移记录
        
        Raises:
            InvalidTransitionError: 非法迁移且未 force
        """
    
    def set_state(self, issue_number: int, state: IssueState) -> None:
        """直接设置状态（内部方法，原子替换 state/* 标签）"""
    
    def _get_all_state_labels(self, issue_number: int) -> list[str]:
        """获取 issue 所有 state/* 标签"""
    
    def _add_label(self, issue_number: int, label: str) -> None:
        """[内部] 添加标签"""
    
    def _remove_label(self, issue_number: int, label: str) -> None:
        """[内部] 移除标签"""
```

---

## 5. 消费接口

### 5.1 flow 命令组消费

```python
# flow 命令组调用示例（后续实现）

# flow new --issue 123
# → 创建 flow，绑定 issue
# → label_service.transition(123, IssueState.READY, "flow:new")

# flow blocked --reason "等待依赖"
# → 标记阻塞
# → label_service.transition(issue, IssueState.BLOCKED, "flow:blocked")

# flow done
# → 完成 flow
# → label_service.transition(issue, IssueState.DONE, "flow:done")
```

### 5.2 agent 命令组消费

```python
# agent 命令组调用示例（后续实现）

# vibe3 plan --issue 123
# → agent 认领任务
# → label_service.transition(123, IssueState.CLAIMED, "agent:plan")

# vibe3 run
# → agent 开始执行
# → label_service.transition(issue, IssueState.IN_PROGRESS, "agent:run")

# vibe3 review
# → agent 提交审核
# → label_service.transition(issue, IssueState.REVIEW, "agent:review")

# vibe3 handoff
# → agent 交接
# → label_service.transition(issue, IssueState.HANDOFF, "agent:handoff")
```

### 5.3 GitHub Actions 消费

```yaml
# .github/workflows/issue-state-sync.yml
# PR 合并时自动设置 done

on:
  pull_request:
    types: [closed]

jobs:
  sync:
    if: github.event.pull_request.merged == true
    steps:
      - name: Set issue done
        run: |
          # 解析 PR body 中的 closes #xxx
          # 调用 gh issue edit 添加 state/done，移除其他 state/*
```

---

## 6. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/vibe3/models/orchestration.py` | 新建 | IssueState, StateTransition |
| `src/vibe3/services/label_service.py` | 新建 | LabelService |
| `src/vibe3/exceptions/orchestration.py` | 新建 | InvalidTransitionError |
| `.github/workflows/issue-state-sync.yml` | 新建 | PR 合并自动设置 done |

---

## 7. 不在本次范围

- ❌ CLI 命令（flow/agent 命令组后续实现）
- ❌ FlowService 修改
- ❌ Handoff 联动
- ❌ 调度功能
- ❌ 静态标签操作（type/*, scope/* 等）

---

## 8. 验收标准

- [ ] `IssueState` 枚举定义完成
- [ ] `StateTransition` 模型定义完成
- [ ] `LabelService.get_state()` 实现完成
- [ ] `LabelService.transition()` 实现完成
- [ ] 状态迁移规则正确执行
- [ ] 非法迁移被拒绝（除非 force）
- [ ] 单元测试覆盖率 > 80%
- [ ] 文档更新