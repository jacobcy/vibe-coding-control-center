# Spec: 优化 vibe-manager Skill 与相关执行流程

## 背景与问题陈述

本次 session 中，manager 角色执行出现了以下根本性错误：

**错误 1：manager 直接写了代码**
- manager 应该只派发 agent 去做代码工作，自己只做编排和监控
- SKILL.md 明确写了："manager 不亲自写代码"
- 实际执行中 manager 绕过了这条规则，直接修改了源文件

**错误 2：flow 没有 task binding 就开始执行**
- `vibe3 flow show` 显示 `task: not bound`
- 没有执行 `vibe3 flow bind <issue> --role task`
- 执行链路没有合法的入口

**错误 3：`vibe3 run --skill --async` 产生了多个 aborted 记录**
- flow timeline 中有 3 条 `run_aborted`：`Plan file not found: nonexistent.md`
- manager 对此没有观察到也没有处理
- async 模式下 skill 执行的错误路径有 bug

**错误 4：manager 没有维持观察循环**
- manager 发起了 async agent 后，没有定期检查 `vibe3 flow show`
- 直接进入了代码修改工作，打破了 manager 的职责边界

---

## 目标

本 spec 定义需要改进的三个方向：

1. **vibe-manager SKILL.md**：补充具体的可执行步骤，防止角色越界
2. **`vibe3 run --async --skill` 执行路径**：修复 "nonexistent.md" bug
3. **manager 观察协议**：定义 manager 如何非阻塞地监控 agent 进度

---

## 改进方向 1：vibe-manager SKILL.md 补充

### 当前缺陷

SKILL.md 描述了 manager 的"主链"（6个步骤），但缺少：

- **Phase 0 缺失**：没有说明"必须先完成 flow + task binding 再派发 agent"
- **agent 派发步骤缺失**：SKILL.md 没有说如何调用 `vibe3 run --skill --async`
- **观察循环缺失**：没有说明 manager 应该怎么检查 agent 是否完成
- **发现代码问题时的处理规则**：没有说明 manager 只能发 issue，不能亲自修代码

### 需要新增的内容

**Phase 0: 确认执行入口合法性（前置检查）**

```
manager 在任何 agent 派发之前必须完成：
1. vibe3 flow show                    # 确认 flow 状态
2. vibe3 task show                    # 确认 task 状态
3. 如果 task not bound → vibe3 flow bind <issue> --role task
4. 确认 flow + task + spec 三者对齐
只有通过 Phase 0，才能进入 agent 派发。
```

**Phase 1: agent 派发协议**

```
manager 的派发动作：
- 写 prompt → vibe3 run "instructions" --async
- 用现有 skill → vibe3 run --skill <name> --async
- 用 plan 文件 → vibe3 run --plan <file> --async

派发后立即记录：
- 派发了什么 agent
- 预期产出是什么
- 检查时间点是什么
```

**Phase 2: 观察循环（非阻塞）**

```
manager 不等待 agent 完成，而是定期轮询：
  vibe3 flow show      # 检查 run_started / run_aborted / run_done
  vibe3 handoff show   # 检查 handoff 状态

轮询间隔：每次观察后可以处理其他事情（发 issue、看报告），
但不能自己去实现代码。
```

**明确禁止补充**

```
新增禁止项：
- manager 不得在观察到 agent 结果前自行实现代码
- manager 不得在 flow task not bound 的情况下派发 agent
- manager 发现代码问题 → 发 issue，不是自己改
```

---

## 改进方向 2：修复 `vibe3 run --skill --async` 的 bug

### 问题描述

当执行 `vibe3 run --skill vibe-redundancy-audit --async` 时，
flow timeline 出现多条：
```
run_aborted  reason: Plan file not found: nonexistent.md
```

### 根因分析（需要确认）

`build_async_command()` 正确生成了 `--skill` 参数：
```python
cmd = ["uv", "run", "python", "src/vibe3/cli.py", "run", "--no-async", "--skill", skill]
```

但 `AsyncExecutionService.start_async_execution()` 在记录 run 事件时，
可能从 flow.plan_ref 读取了一个不存在的文件路径。

需要确认：
- `AsyncExecutionService` 是否错误地用 `plan_ref` 覆盖了 `skill` 入口
- run_aborted 事件的触发位置是否在 async 子进程还是在父进程记录阶段

### 需要做的修复

- [ ] 定位 "nonexistent.md" 的来源（在 AsyncExecutionService 或 FlowService 中）
- [ ] 修复：当 `--skill` 被指定时，不应读取 flow.plan_ref
- [ ] 确保 async skill 执行成功后，flow timeline 有正确的 run_done 记录
- [ ] 添加测试：`vibe3 run --skill X --async` 不产生虚假的 run_aborted

---

## 改进方向 3：manager 观察协议文档

### 当前缺陷

没有文档说明：
- manager 在 async agent 运行中应该做什么
- manager 如何判断 agent 完成（通过 flow show / handoff show）
- manager 在 agent 失败时如何响应

### 需要新增

在 SKILL.md 或单独的 `docs/standards/v3/manager-observation-protocol.md` 中说明：

```
agent 派发后，manager 的等待模式：
1. 不阻塞（不用 wait=true 的进程等待）
2. 定期检查：vibe3 flow show 看 run_started/run_done/run_aborted
3. 如果 run_aborted → 分析原因 → 重新派发或发 issue
4. 如果 run_done → 读 handoff show → 决定下一步

manager 永远不应该因为 agent 在跑就去做代码工作。
```

---

## 实现任务

按优先级排序：

| 优先级 | 任务 | 负责方 |
|--------|------|--------|
| P0 | 修复 async skill 执行的 "nonexistent.md" bug | agent（代码修复） |
| P1 | 更新 vibe-manager SKILL.md 补充 Phase 0 + 派发协议 + 观察循环 | agent（文档修改） |
| P2 | 更新 vibe-manager SKILL.md 补充明确禁止项 | agent（文档修改） |
| P3 | 新建 manager-observation-protocol.md | agent（文档） |

---

## 验收标准

1. `vibe3 run --skill <name> --async` 不再产生 "nonexistent.md" aborted 记录
2. vibe-manager SKILL.md 中有明确的 Phase 0 前置检查步骤
3. vibe-manager SKILL.md 中有明确的 agent 派发命令示例
4. vibe-manager SKILL.md 中有明确禁止 manager 亲自写代码的条款
5. 下次使用 vibe-manager 时，manager 能正确：绑定 task → 派发 agent → 观察 → 发 issue

