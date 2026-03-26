# Issue 257: 支持异步执行 plan/review/run 命令

## 问题背景

当前 `vibe3 plan` / `vibe3 review` / `vibe3 run` 都是**同步执行**，会阻塞用户操作：
- `pre-push hook` 中运行 review 会阻塞 push（等待 1-2 分钟）
- 执行失败时缺乏明确的状态反馈
- codeagent-wrapper 超时后只显示错误，无可观测性

## 解决方案

### Phase 1: 数据模型扩展 (FlowState)

添加执行状态字段：
```python
class FlowState(BaseModel):
    # 新增：异步执行状态
    planner_status: Literal["pending", "running", "done", "crashed"] | None = None
    executor_status: Literal["pending", "running", "done", "crashed"] | None = None
    reviewer_status: Literal["pending", "running", "done", "crashed"] | None = None

    # 执行元数据
    execution_pid: int | None = None
    execution_started_at: str | None = None
    execution_completed_at: str | None = None
```

### Phase 2: 异步执行服务

创建 `src/vibe3/services/async_execution_service.py`:
- `start_async_execution()` - 启动后台进程
- `check_execution_status()` - 检查进程状态
- `write_execution_result()` - 写入结果

### Phase 3: 命令层集成

为 plan/review/run 添加 `--async` 参数：
- 默认异步执行
- 使用 `--no-async` 同步执行

### Phase 4: Flow Show 展示

在 `flow show` 中展示执行状态

## 实现步骤

- [ ] Phase 1: 数据模型扩展
- [ ] Phase 2: 异步执行服务
- [ ] Phase 3: 命令层集成
- [ ] Phase 4: UI 展示
- [ ] Phase 5: 测试