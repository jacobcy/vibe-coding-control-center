# Verdict 命令设计文档

> **设计原则**：底层只做观测和链条维护，决策逻辑在 agent prompt 中

## 核心理念

**协作工具，而非决策系统**：
- ✅ 提供 `vibe3 handoff verdict` 命令，让 agent 显式记录判断结果
- ✅ 提供 `vibe3 handoff show` 展示完整链条和最终判定
- ✅ 底层只负责记录、存储、展示
- ❌ 底层不做判断逻辑（除了 no-op gate）

**职责分离**：
- **工具层**：记录、存储、展示、观测
- **Agent 层**：阅读 verdict、理解上下文、做出决策

---

## 一、命令设计

### 1.1 `vibe3 handoff verdict` - 写入 verdict

```bash
vibe3 handoff verdict <verdict> [options]

Arguments:
  verdict              PASS | MAJOR | BLOCK | UNKNOWN

Options:
  --reason TEXT        Verdict 理由（可选）
  --issues TEXT        问题清单（可选，自由文本）

Examples:
  # Reviewer 给出裁决
  vibe3 handoff verdict MAJOR --reason "缩进错误和缺少文档"

  # Manager 补救
  vibe3 handoff verdict MAJOR --reason "补救：发现实际问题"
```

**实现要点**：
- 写入 handoff 的 Updates 部分
- 同时更新 flow state 的 `latest_verdict` 字段（用于快速查询）
- 不做任何判断或验证

---

### 1.2 `vibe3 handoff show` - 展示完整链条

**输出格式**：

```markdown
# Handoff: task/issue-304

## Latest Verdict
verdict: MAJOR
actor: manager
timestamp: 2026-04-22T08:00:00Z
reason: 补救：Reviewer 输出格式错误，但发现实际问题

## Updates Timeline

### 2026-04-22T08:00:00+08:00 | manager | verdict
verdict: MAJOR
reason: 补救：Reviewer 输出格式错误，但发现实际问题

### 2026-04-21T23:50:04+08:00 | claude/claude-sonnet-4-6 | audit
verdict: UNKNOWN
reference: docs/reports/task-issue-304-audit-auto-*.md

### 2026-04-21T23:45:26+08:00 | manager | note
[manager] Implementation audit complete...

...
```

**关键点**：
- **顶部显示最新 verdict**：方便快速查看
- **完整 timeline**：展示所有更新记录
- **不做解读**：只展示原始数据

---

### 1.3 `vibe3 flow show` - 展示整条线

**输出格式**：

```markdown
# Flow: task/issue-304

## Timeline

2026-04-19 21:22  manager   claimed issue
2026-04-19 22:43  planner   created plan
2026-04-21 05:22  manager   updated plan
2026-04-21 10:56  executor  completed execution
2026-04-21 23:50  reviewer  audit (verdict: UNKNOWN)
2026-04-22 08:00  manager   verdict (MAJOR)

## Current State

- Branch: task/issue-304
- Status: in-progress
- Latest Verdict: MAJOR
```

**关键点**：
- **Timeline 视图**：整条线的流程概览
- **Current State**：当前状态快照
- **不做决策**：只展示事实

---

## 二、数据模型

### 2.1 VerdictRecord

```python
# models/verdict.py
from datetime import datetime
from pydantic import BaseModel
from typing import Literal

class VerdictRecord(BaseModel):
    """Verdict 记录"""

    verdict: Literal["PASS", "MAJOR", "BLOCK", "UNKNOWN"]
    actor: str              # 例如 "claude/claude-sonnet-4-6"
    role: str               # 例如 "reviewer" | "manager"
    timestamp: datetime
    reason: str | None = None
    issues: str | None = None   # 自由文本，不做结构化要求

    # 关联信息
    flow_branch: str
```

### 2.2 存储位置

**Handoff Updates**：

```markdown
### 2026-04-22T08:00:00+08:00 | manager | verdict
verdict: MAJOR
reason: 补救：Reviewer 输出格式错误，但发现实际问题
```

**Flow State**：

```json
{
  "branch": "task/issue-304",
  "latest_verdict": {
    "verdict": "MAJOR",
    "actor": "manager",
    "timestamp": "2026-04-22T08:00:00Z",
    "reason": "补救：Reviewer 输出格式错误，但发现实际问题"
  }
}
```

---

## 三、实现架构

### 3.1 命令层

**文件**：`src/vibe3/commands/handoff.py`

```python
@app.command("verdict")
def verdict_command(
    verdict: Annotated[
        Literal["PASS", "MAJOR", "BLOCK", "UNKNOWN"],
        typer.Argument(),
    ],
    reason: Annotated[str | None, typer.Option()] = None,
    issues: Annotated[str | None, typer.Option()] = None,
    branch: Annotated[str | None, typer.Argument()] = None,
) -> None:
    """Write verdict to handoff and flow state."""
    from vibe3.services.verdict_service import VerdictService

    service = VerdictService()
    service.write_verdict(
        verdict=verdict,
        reason=reason,
        issues=issues,
        branch=branch,
    )

    typer.echo(f"Verdict written: {verdict}")
```

### 3.2 服务层

**文件**：`src/vibe3/services/verdict_service.py`

```python
class VerdictService:
    """Verdict 记录服务（只做记录，不做判断）"""

    def write_verdict(
        self,
        verdict: str,
        reason: str | None,
        issues: str | None,
        branch: str | None,
    ) -> None:
        """写入 verdict 到 handoff 和 flow state"""

        # 1. 解析 branch
        target_branch = branch or self.git_client.get_current_branch()

        # 2. 构建记录
        record = VerdictRecord(
            verdict=verdict,
            actor=self._get_current_actor(),
            role=self._get_current_role(),
            timestamp=datetime.now(UTC),
            reason=reason,
            issues=issues,
            flow_branch=target_branch,
        )

        # 3. 写入 handoff
        self.handoff_service.append_update(
            branch=target_branch,
            kind="verdict",
            message=record.to_handoff_markdown(),
        )

        # 4. 更新 flow state（快速查询用）
        self.flow_service.update_latest_verdict(target_branch, record)

    def get_latest_verdict(self, branch: str) -> VerdictRecord | None:
        """获取最新 verdict（只查询，不判断）"""

        # 从 flow state 读取（快速路径）
        return self.flow_service.get_latest_verdict(branch)
```

### 3.3 展示层

**文件**：`src/vibe3/ui/handoff_ui.py`

```python
def render_handoff_show(handoff: HandoffData) -> None:
    """渲染 handoff show 输出"""

    # 1. 顶部显示最新 verdict
    if handoff.latest_verdict:
        console.print("\n[bold]## Latest Verdict[/]")
        console.print(f"verdict: {handoff.latest_verdict.verdict}")
        console.print(f"actor: {handoff.latest_verdict.actor}")
        console.print(f"timestamp: {handoff.latest_verdict.timestamp}")
        if handoff.latest_verdict.reason:
            console.print(f"reason: {handoff.latest_verdict.reason}")

    # 2. 完整 timeline
    console.print("\n[bold]## Updates Timeline[/]")
    for update in handoff.updates:
        render_update(update)
```

---

## 四、Agent Prompt 集成

### 4.1 Reviewer Prompt

**文件**：`.agent/policies/review.md`

**新增输出契约**：

```markdown
## 输出要求

完成审查后，必须执行：

vibe3 handoff verdict <VERDICT> --reason "<理由>"

VERDICT 选择：
- PASS: 无问题，可合并
- MAJOR: 需修复后合并
- BLOCK: 严重问题，阻塞合并
- UNKNOWN: 无法判断

示例：
vibe3 handoff verdict MAJOR --reason "发现缩进错误和缺少文档"
```

**关键点**：
- ✅ 在 prompt 中明确要求
- ✅ 不在底层强制检查
- ❌ 如果 reviewer 不遵守，由 manager 补救

---

### 4.2 Manager Prompt

**文件**：`supervisor/manager.md`

**UNKNOWN 处理逻辑**（在 prompt 中）：

```markdown
### `handle_handoff()` - 处理 audit_ref

读取 handoff：
```bash
vibe3 handoff show <branch>
```

检查 `latest_verdict`：
- 如果 verdict 是 PASS：进入 merge-ready
- 如果 verdict 是 MAJOR/BLOCK：保持 in-progress，写修复指令
- 如果 verdict 是 UNKNOWN 或缺失：
  - 阅读 audit_ref 内容
  - 自行判断是否"实质通过"
  - 执行补救：
    ```bash
    vibe3 handoff verdict MAJOR --reason "补救：发现实际问题"
    ```
  - 按补救后的 verdict 处理
```

**关键点**：
- ✅ Manager 在 prompt 中阅读和理解 verdict
- ✅ Manager 有补救工具（命令）
- ✅ 决策逻辑在 prompt，不在代码

---

### 4.3 Executor Prompt

**文件**：`.agent/policies/run.md`

**任务类型判断**（在 prompt 中）：

```markdown
## 任务类型判断

启动时执行：
```bash
vibe3 handoff show <branch>
```

查看 `latest_verdict`：
- 如果 verdict 是 MAJOR 或 BLOCK：
  - 你在修复已有代码
  - 重点阅读 handoff 中的 reason 和 issues
  - 不要重新执行 plan

- 如果 verdict 是 PASS 或 UNKNOWN 或无：
  - 你在执行 plan
  - 重点阅读 plan_ref 和 spec_ref
```

**关键点**：
- ✅ Executor 在 prompt 中判断任务类型
- ✅ 不在底层判断并路由
- ✅ 底层只提供数据

---

## 五、No-Op Gate 观测

### 5.1 观测逻辑

**文件**：`src/vibe3/execution/gates.py`

```python
def check_progress_gate(flow_branch: str) -> bool:
    """检查是否有进展（观测，不判断）"""

    # 读取最新 verdict
    verdict = verdict_service.get_latest_verdict(flow_branch)

    # 只观测，不判断
    # 返回事实：是否有 verdict 记录
    return verdict is not None
```

**关键点**：
- ✅ 只观测是否有记录
- ✅ 不判断 verdict 值是否合理
- ✅ No-op gate 基于"是否有进展"，不是"进展是否正确"

---

## 六、使用流程

### 6.1 正常流程

```
1. Reviewer 分析代码
2. Reviewer 执行：vibe3 handoff verdict MAJOR --reason "..."
3. Manager 读取：vibe3 handoff show
4. Manager 看到 verdict: MAJOR
5. Manager 写修复指令到 handoff
6. Executor 读取：vibe3 handoff show
7. Executor 看到 verdict: MAJOR → 执行修复
```

### 6.2 补救流程

```
1. Reviewer 输出格式错误（无 verdict 命令）
2. Manager 读取：vibe3 handoff show
3. Manager 发现 latest_verdict 缺失或 UNKNOWN
4. Manager 阅读 audit_ref 内容
5. Manager 判断：发现实际问题
6. Manager 补救：vibe3 handoff verdict MAJOR --reason "补救：..."
7. Executor 读取：vibe3 handoff show
8. Executor 看到补救后的 verdict → 执行修复
```

---

## 七、关键设计决策

### 7.1 为什么不在底层判断？

**问题**：如果底层判断 verdict，就变成强制流程。

**回答**：
- ✅ 底层只提供工具和数据
- ✅ Agent 在 prompt 中做决策
- ✅ 保持协作标准的灵活性

### 7.2 为什么允许 Manager 补救？

**问题**：如果 Reviewer 不遵守，怎么处理？

**回答**：
- ✅ Manager 是 Issue Owner，有权纠正
- ✅ 补救是显式操作（命令 + reason）
- ✅ 所有操作都记录在 timeline 中

### 7.3 为什么保留 UNKNOWN？

**问题**：UNKNOWN 有什么用？

**回答**：
- ✅ Reviewer 可能真的无法判断
- ✅ Manager 需要知道这个状态
- ✅ 可以选择补救或进入 blocked

---

## 八、迁移策略

### Phase 1：实现命令（立即）

**文件**：
- `src/vibe3/commands/handoff.py` - 添加 verdict 子命令
- `src/vibe3/services/verdict_service.py` - 写入和查询服务
- `src/vibe3/ui/handoff_ui.py` - 展示逻辑

**用途**：Manager 补救用

---

### Phase 2：更新 Prompt（短期）

**文件**：
- `.agent/policies/review.md` - 要求使用命令
- `supervisor/manager.md` - 补救流程
- `.agent/policies/run.md` - 任务类型判断

**用途**：所有 agent 使用命令

---

### Phase 3：清理旧逻辑（长期）

**移除**：
- `src/vibe3/agents/review_parser.py` 中的 VERDICT 解析逻辑
- 任何在代码中判断 verdict 的逻辑

**保留**：
- No-op gate 的观测逻辑
- 命令和服务

---

## 九、总结

**核心原则**：
- 工具层：记录、存储、展示、观测
- Agent 层：阅读、理解、决策

**关键命令**：
- `vibe3 handoff verdict` - 写入 verdict
- `vibe3 handoff show` - 展示完整链条（顶部显示最新 verdict）
- `vibe3 flow show` - 展示整条 timeline

**底层职责**：
- ✅ 提供工具
- ✅ 维护链条
- ✅ 观测进展（no-op gate）
- ❌ 不做判断

**Agent 职责**：
- ✅ 使用工具
- ✅ 阅读数据
- ✅ 做出决策
- ✅ 补救错误
