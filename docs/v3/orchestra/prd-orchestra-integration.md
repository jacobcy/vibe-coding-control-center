---
document_type: prd
title: "Orchestra 调度器设计 PRD"
version: v2
author: "Kiro"
created: "2026-03-16"
last_updated: "2026-03-24"
related_docs:
  - docs/v3/orchestra/README.md
  - CLAUDE.md
  - src/vibe3/models/orchestration.py
  - src/vibe3/services/label_service.py
status: active
---

# Orchestra 调度器设计 PRD

## 0. 背景与定位

**Orchestra** 是 Vibe Center v3 的调度器子系统，负责从任务板（GitHub Issues）拉取任务并自动分发给 Agent 执行。

### 0.1 当前实现状态

**PR #236 已实现状态机核心**：

| 组件 | 文件 | 状态 |
|------|------|------|
| 状态枚举 | `src/vibe3/models/orchestration.py` | ✅ 已实现 |
| 状态迁移规则 | `src/vibe3/models/orchestration.py` | ✅ 已实现 |
| LabelService API | `src/vibe3/services/label_service.py` | ✅ 已实现 |
| GitHub Actions | `.github/workflows/issue-state-sync.yml` | ✅ 已实现 |

**状态迁移图**：

```
ready → claimed → in-progress → review → merge-ready → done
                    ↓
               blocked / handoff
```

### 0.2 设计策略调整

**v1 设计**（已废弃）：复杂的 daemon + reconciliation loop
**v2 设计**（当前）：简化的 `vibe3 serve` 服务

**关键变化**：
1. **状态机已就绪** - `LabelService` 提供 Python API
2. **简化架构** - 先实现核心调度，后续再考虑主控 agent
3. **增量开发** - 基于现有 plan/run/review 命令

### 0.3 v2 设计目标

| 目标 | 说明 |
|------|------|
| 监听标签变化 | `vibe3 serve` 后台服务 |
| 触发对应命令 | 状态变化 → 调用 plan/run/review |
| 记录执行过程 | 写入 handoff.db |
| 可观测性 | `vibe3 flow status` 显示状态 |

## 1. 架构设计

### 1.1 核心组件

```
+-------------------------------------------------------------+
|                     vibe3 serve                             |
|  +-----------+    +-----------+    +-----------+            |
|  |  Poller   |--->|  Router   |--->| Dispatcher|            |
|  | (每 60s)  |    | (状态判断) |    | (执行命令) |            |
|  +-----------+    +-----------+    +-----------+            |
|        |                |                |                  |
|        v                v                v                  |
|  +-----------+    +-----------+    +-----------+            |
|  | GitHub API|    |LabelService|    | Commands  |            |
|  | (gh issue)|    | (状态机)    |    |plan/run/  |            |
|  |           |    |            |    | review    |            |
|  +-----------+    +-----------+    +-----------+            |
+-------------------------------------------------------------+
                              |
                              v
                    +-----------------+
                    |   handoff.db    |
                    |  (执行记录)      |
                    +-----------------+
```

### 1.2 状态触发映射

| GitHub Label | 状态变化 | 触发命令 | 说明 |
|--------------|----------|----------|------|
| `state/ready` → `state/claimed` | READY → CLAIMED | `vibe3 plan task <issue>` | 开始规划 |
| `state/claimed` → `state/in-progress` | CLAIMED → IN_PROGRESS | `vibe3 run execute` | 开始执行 |
| `state/in-progress` → `state/review` | IN_PROGRESS → REVIEW | `vibe3 review pr <pr_number>` | 开始审核 |
| `state/review` → `state/merge-ready` | REVIEW → MERGE_READY | - | 等待合并 |
| `state/merge-ready` → `state/done` | MERGE_READY → DONE | - | 完成 |
| 任意 → `state/blocked` | → BLOCKED | - | 阻塞中 |
| 任意 → `state/handoff` | → HANDOFF | - | 交接中 |

### 1.3 文件结构

```
src/vibe3/orchestra/
├── __init__.py
├── serve.py          # vibe3 serve 命令
├── poller.py         # GitHub 标签轮询
├── router.py         # 状态变化路由
├── dispatcher.py     # 命令调度执行
└── config.py         # Orchestra 配置
```

## 2. 核心实现

### 2.1 `vibe3 serve` 命令

```python
# src/vibe3/orchestra/serve.py

@app.command()
def start(
    interval: int = 60,
    repo: str | None = None,
    dry_run: bool = False,
) -> None:
    """Start Orchestra daemon to monitor GitHub labels.
    
    Args:
        interval: Polling interval in seconds (default: 60)
        repo: GitHub repo (default: current repo)
        dry_run: Only log actions, don't execute
    """
    config = OrchestraConfig.from_settings()
    if interval != 60:
        config.polling_interval = interval
    if repo is not None:
        config.repo = repo
    if dry_run:
        config.dry_run = dry_run
    
    poller = Poller(config)
    poller.start()
```

### 2.2 Poller 实现

```python
# src/vibe3/orchestra/poller.py

class Poller:
    def __init__(self, config: OrchestraConfig):
        self.config = config
        self.router = Router()
        self.dispatcher = Dispatcher(config)
    
    async def start(self) -> None:
        """Start async polling loop."""
        while self._running:
            await self._tick_async()
            await asyncio.sleep(self.config.polling_interval)
    
    async def _tick_async(self) -> None:
        """Single polling iteration."""
        issues = self._fetch_issues()
        for issue in issues:
            await self._process_issue_async(issue)
```

### 2.3 Dispatcher 实现

```python
# src/vibe3/orchestra/dispatcher.py

class Dispatcher:
    def _build_command(self, trigger: Trigger) -> list[str] | None:
        """Build command list from trigger with flow orchestration."""
        cmd = ["uv", "run", "python", "-m", "vibe3", trigger.command]
        cmd.extend(trigger.args)
        
        if trigger.command == "plan":
            # vibe3 plan task <issue_number>
            cmd.append(str(trigger.issue.number))
        elif trigger.command == "review":
            # vibe3 review pr <pr_number>
            pr_number = self._get_pr_for_issue(trigger.issue.number)
            if pr_number:
                cmd.append(str(pr_number))
            else:
                return None  # Cannot review without PR
        
        return cmd
```

## 3. 使用场景

### 3.1 典型工作流

```bash
# 1. 启动 serve 服务
vibe3 serve start --interval 60

# 2. 人类创建 issue 并添加标签
gh issue create --title "feat: add new feature" --body "..."
gh issue edit 42 --add-label "state/ready"

# 3. serve 自动检测到 ready → claimed 状态变化，触发:
#    → vibe3 plan task 42
#    → 创建 plan-{timestamp}.md

# 4. 人类查看 plan 后，添加 in-progress 标签
gh issue edit 42 --add-label "state/in-progress"

# 5. serve 自动检测到 claimed → in-progress
#    → vibe3 run execute
#    → 开始执行代码

# 6. 执行完成后，添加 review 标签
gh issue edit 42 --add-label "state/review"

# 7. serve 自动触发 review
#    → vibe3 review pr 123

# 8. review 通过后，人类 merge PR
#    → GitHub Actions 自动设置 done
```

### 3.2 手动模式共存

```bash
# serve 服务与手动命令可以共存

# 手动执行（不依赖 serve）
vibe3 plan task 42
vibe3 run execute --file plan.md
vibe3 review pr 123

# serve 会在后台监控标签变化
# 不会干扰手动操作
```

## 4. 配置

### 4.1 settings.yaml 扩展

```yaml
orchestra:
  enabled: true
  polling_interval: 60
  repo: "jacobcy/vibe-coding-control-center"
  max_concurrent_flows: 3
  
  master_agent:
    enabled: true
    agent: "master-controller"
    timeout_seconds: 300
```

## 5. 实现计划

### Phase 1: 核心调度（本周）

| 任务 | 文件 | 优先级 |
|------|------|--------|
| serve 命令 | `orchestra/serve.py` | P0 |
| Poller 实现 | `orchestra/poller.py` | P0 |
| Router 实现 | `orchestra/router.py` | P0 |
| Dispatcher 实现 | `orchestra/dispatcher.py` | P0 |
| 配置支持 | `orchestra/config.py` | P1 |

### Phase 2: 集成测试（下周）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 单元测试 | 每个组件的测试 | P0 |
| 集成测试 | 端到端流程测试 | P0 |
| 文档更新 | README 和 PRD | P1 |

### Phase 3: 主控 Agent（后续）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| Agent 编排 | 多 agent 协调 | P2 |
| 错误恢复 | 崩溃恢复机制 | P2 |
| 监控面板 | 状态可视化 | P3 |

## 6. 风险与约束

### 6.1 风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| GitHub API 限流 | 轮询失败 | 限制轮询间隔 >= 30s |
| 并发执行 | 资源竞争 | 限制 max_concurrent_flows |
| 进程崩溃 | 孤儿任务 | PID 文件 + 健康检查 |

### 6.2 约束

- **轮询间隔**：不低于 30 秒（GitHub API 限流）
- **并发限制**：最多 3 个并发 flow
- **幂等性**：相同状态变化不重复执行
- **可观测性**：所有操作写入 handoff.db

## 7. 验收标准

- [ ] `vibe3 serve start` 命令可以启动后台服务
- [ ] 检测到 `state/ready` → `state/claimed` 标签变化时触发 `vibe3 plan task <issue>`
- [ ] 检测到 `state/claimed` → `state/in-progress` 标签变化时触发 `vibe3 run execute`
- [ ] 检测到 `state/in-progress` → `state/review` 标签变化时触发 `vibe3 review pr <pr_number>`
- [ ] 所有执行记录写入 handoff.db
- [ ] `vibe3 flow status` 显示当前状态
- [ ] 单元测试覆盖率 >= 80%

## 8. 后续规划

### 8.1 Phase 3: 主控 Agent

**目标**：实现智能编排，而非简单状态触发

**功能**：
- 分析 issue 复杂度，决定是否需要拆分
- 监控执行进度，自动处理异常
- 协调多个 agent 并行工作
- 生成执行报告

**实现方式**：
- 使用 LLM 作为主控 agent
- 基于 handoff.db 的历史数据学习
- 提供可配置的编排策略

### 8.2 长期目标

- **多项目支持**：一个 serve 监控多个 repo
- **Linear 集成**：支持 Linear 作为 tracker
- **可视化面板**：Web UI 展示状态
- **机器学习**：预测执行时间，优化调度