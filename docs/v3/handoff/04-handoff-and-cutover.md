---
document_type: plan
title: Phase 04 - Handoff Command & Store
status: draft
author: GPT-5 Codex
created: 2026-03-15
last_updated: 2026-03-21
related_docs:
  - docs/v3/handoff/v3-rewrite-plan.md
  - docs/standards/v3/handoff-store-standard.md
  - docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/infrastructure/03-coding-standards.md
  - docs/v3/infrastructure/04-test-standards.md
---

# Phase 04: Handoff Command & Store

**Goal**: 实现 `vibe handoff` 命令与 JSON 文件编辑机制，建立基于 SQLite + JSON 文件的 handoff 体系，并降级 `.agent/context/task.md` 为 workflow 辅助索引。

## 1. 架构约束

见 [01-command-and-skeleton.md](01-command-and-skeleton.md) §通用架构约束

本阶段额外固定以下约束：

- `handoff command + handoff store` 是 v3 多 agent 共同维护的交接真源
- `issue -> pr` 是唯一标准交付链
- `.agent/context/task.md` 不再承担 v3 正式 handoff 语义
- 若 handoff 与 `issue / PR / git` 现场冲突，必须修正 handoff

## 2. Pre-requisites (Executor Entry)

- [ ] Phase 02 的 flow/task 责任链已经可写入 handoff store
- [ ] Phase 03 的 `issue -> pr` 主链已经可运行
- [ ] `pre-push` 本地 review report 已能落到 `.agent/reports/`
- [ ] review report 中的 `SESSION_ID` 已可作为可提取线索使用

## 3. 目录结构

```text
.agent/handoff/
├── task-feature-xyz/
│   ├── plan.json
│   ├── report.json
│   └── audit.json
└── task-another-feature/
    ├── plan.json
    ├── report.json
    └── audit.json
```

**路径规则**：
- `{branch-safe-name}`：将 branch 名称中的 `/` 替换为 `-`
- 示例：`task/vibe3-parallel-rebuild` → `task-vibe3-parallel-rebuild`

## 4. 技术要求（分层实现）

### 4.1 数据库扩展

**新增表**: `handoff_items`

```sql
CREATE TABLE handoff_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  branch TEXT NOT NULL,
  handoff_type TEXT NOT NULL,  -- 'plan', 'report', 'audit'
  sequence_number INTEGER NOT NULL,
  actor TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(branch, handoff_type, sequence_number)
);

CREATE INDEX idx_handoff_branch_type ON handoff_items(branch, handoff_type);
```

### 4.2 JSON 文件格式

**文件路径**: `.agent/handoff/{branch-safe-name}/plan.json`

**格式**:
```json
{
  “flow_slug”: “vibe3-parallel-rebuild”,
  “branch”: “task/vibe3-parallel-rebuild”,
  “handoff_type”: “plan”,
  “items”: [
    {
      “sequence_number”: 1,
      “actor”: “claude/sonnet-4.5”,
      “content”: “完成了数据模型的初步设计”
    },
    {
      “sequence_number”: 2,
      “actor”: “codex/gpt-5.4”,
      “content”: “实现了 SQLite handoff store”
    }
  ]
}
```

### 4.3 Service Layer

**文件**: `src/vibe3/services/handoff_service.py`

提供方法：
- `get_handoff(branch, handoff_type)` - 从 SQLite 读取 handoff
- `sync_from_json(branch, handoff_type, json_path)` - 从 JSON 同步到 SQLite
- `sync_to_json(branch, handoff_type, json_path)` - 从 SQLite 同步到 JSON
- `add_handoff_item(branch, handoff_type, content, actor)` - 添加新条目
- `update_handoff_item(branch, handoff_type, sequence_number, content)` - 更新条目
- `delete_handoff_item(branch, handoff_type, sequence_number)` - 删除条目

**同步逻辑**：
1. 比较 JSON 文件和 SQLite 的 `updated_at` 时间戳
2. 以最新时间戳为准
3. 记录同步事件到 `flow_events` 表

### 4.4 Command Layer

**文件**: `src/vibe3/commands/handoff.py`

提供命令：
- `vibe3 handoff edit plan` - 编辑 plan handoff（打开 JSON 文件）
- `vibe3 handoff edit report` - 编辑 report handoff
- `vibe3 handoff edit audit` - 编辑 audit handoff
- `vibe3 handoff show plan` - 显示 plan handoff
- `vibe3 handoff show report` - 显示 report handoff
- `vibe3 handoff show audit` - 显示 audit handoff

**edit 命令流程**：
1. 检查 JSON 文件是否存在，不存在则创建
2. 如果 SQLite 有数据但 JSON 不存在，先同步到 JSON
3. 使用 `$EDITOR` 打开 JSON 文件
4. 等待编辑器关闭
5. 解析 JSON 文件并同步到 SQLite
6. 记录 `handoff_edited` 事件到 `flow_events`

**show 命令流程**：
1. 从 SQLite 读取 handoff items
2. 使用 rich 格式化输出
3. 支持 `--json` 参数输出 JSON 格式

## 5. 成功标准（验收标准）

### 5.1 功能验收

- [ ] `vibe3 handoff edit plan` 打开 JSON 文件编辑器
- [ ] 编辑 JSON 文件后，SQLite 自动同步
- [ ] `vibe3 handoff show plan` 显示 handoff 内容
- [ ] `vibe3 handoff show plan --json` 输出 JSON 格式
- [ ] 新增条目自动分配 `sequence_number`
- [ ] 删除条目后 `sequence_number` 不回收
- [ ] 所有变更记录到 `flow_events` 表

### 5.2 数据库验收

- [ ] `handoff_items` 表正确记录所有条目
- [ ] 唯一约束 `(branch, handoff_type, sequence_number)` 生效
- [ ] 删除条目后编号保留，不回收

### 5.3 代码质量验收

- [ ] `mypy --strict` 检查通过（无类型错误）
- [ ] Service 层文件 < 300 行
- [ ] Command 层文件 < 100 行
- [ ] 不使用 `print()`，使用 `logger` 或 `rich`

### 5.4 测试验收

- [ ] `HandoffService` 单元测试通过（100% 成功率）
- [ ] JSON ↔ SQLite 同步测试通过
- [ ] 错误处理测试通过（JSON 格式错误、文件不存在等）

**测试标准**: 见 [04-test-standards.md](../infrastructure/04-test-standards.md)

## 10. Development Notes

## 6. Development Notes

### 6.1 JSON 编辑流程

**参考**: [2026-03-13-vibe3-parallel-rebuild-design.md](../../plans/2026-03-13-vibe3-parallel-rebuild-design.md) § "Handoff Command Design"

**编辑规则**：

1. **添加新记录**：
   - 在 `items` 数组末尾添加新对象
   - **不要填写 `sequence_number`**（系统自动分配）
   - **不要填写 `actor`**（系统自动从当前注册身份读取）
   - **不要填写 `created_at` 和 `updated_at`**（系统自动生成）
   - 只需要填写 `content` 字段

2. **修改记录**：
   - 直接修改对应记录的 `content` 字段
   - **不要修改 `sequence_number`、`actor`、`created_at`**
   - 系统会自动更新 `updated_at`

3. **删除记录**：
   - 从 `items` 数组中移除对应的对象
   - 删除后 `sequence_number` 不回收，保持历史可追溯性

**同步规则**：
- 系统会比较 JSON 文件和数据库的内容
- 自动检测新增、修改、删除的记录
- 自动分配 `sequence_number`（新增记录）
- 自动更新 `updated_at`（修改记录）
- 自动记录所有变更到 `flow_events` 表

### 6.2 Service 层实现模式

**参考**: Phase 02 中的 `flow_service.py` 实现

**推荐结构**：
```python
# services/handoff_service.py
from pathlib import Path
from typing import Protocol
import json

class HandoffServiceProtocol(Protocol):
    def get_handoff(self, branch: str, handoff_type: str) -> dict:
        ...

    def sync_from_json(self, branch: str, handoff_type: str, json_path: Path) -> None:
        ...

class HandoffService:
    def __init__(self, store: Vibe3Store):
        self.store = store

    def get_handoff(self, branch: str, handoff_type: str) -> dict:
        items = self.store.get_handoff_items(branch, handoff_type)
        return {
            "branch": branch,
            "handoff_type": handoff_type,
            "items": items
        }
```

### 6.3 Command 层实现模式

**参考**: Phase 02 中的 `flow.py` 实现

**edit 命令**：
```python
# commands/handoff.py
import typer
import subprocess
from pathlib import Path

@app.command()
def edit(handoff_type: str):
    """Edit handoff JSON file"""
    branch = get_current_branch()
    json_path = get_handoff_json_path(branch, handoff_type)

    # 如果 SQLite 有数据但 JSON 不存在，先同步
    if not json_path.exists():
        service.sync_to_json(branch, handoff_type, json_path)

    # 打开编辑器
    editor = os.getenv("EDITOR", "vim")
    subprocess.run([editor, str(json_path)])

    # 编辑完成后同步回 SQLite
    service.sync_from_json(branch, handoff_type, json_path)
```

### 6.4 `task.md` 降级说明

`.agent/context/task.md` 在 v3 阶段降级为 workflow 辅助索引：

**允许记录**：
- 当前 workflow 的 task list
- 每个 task 运行过程中的 findings
- follow-up issue 是否已发
- 当前阶段的最终结论

**不允许记录**：
- 可替代 handoff store 的正式责任链
- 与 `issue / PR / git` 冲突的阶段事实

## 7. Handoff for Executor 05

- [ ] 确保 `vibe3 handoff edit plan` 能正确打开 JSON 文件
- [ ] 确保 JSON 编辑后能正确同步到 SQLite
- [ ] 确保 `vibe3 handoff show plan` 能正确显示内容
- [ ] 确保所有变更记录到 `flow_events` 表
- [ ] 更新 `.agent/context/task.md` 说明其降级角色
