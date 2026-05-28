# Vibe-Review-PR 唤醒协议单源化重构

## 问题

b0ea872 引入的 3 次唤醒机制在 SKILL.md 和 YAML 中共散布 8+ 处，修改一个参数需要动 7-8 个位置。历史上同一逻辑至少重写了 4 次，导致：

- 维护成本高：改 `max_attempts` 从 3 到 5 需改 8 处
- 一致性风险：多处手工重复容易漂移
- 文件臃肿：YAML 中 3 个 verify 步骤各有 ~15 行几乎相同的伪代码

## 设计目标

- **单源真源**：`max_attempts` / `timeout` 只在一处定义
- **流程集中**：握手/唤醒伪代码只写一次，在 SKILL.md 中集中描述
- **YAML 精简化**：每个 verify 步骤从伪代码块变为一行引用

## 方案

### 三层单源结构

```
Backlog metadata (参数定义)
  └─ wakeup_policy: {max_attempts: 3, timeout: 30s}
       │
       ▼
SKILL.md "握手与唤醒协议规范" (流程定义)
  └─ handshake_agent() / handle_agent_idle() 伪代码（各一份）
  └─ 参数读取自 metadata.wakeup_policy
       │
       ▼
YAML Phase 2 execution (执行引用)
  └─ verify_X_handshake: 按握手协议规范执行（agent=X）
  └─ check_agent_pane_status: 按 idle 检查协议执行
```

### SKILL.md 改动

**新增 "握手与唤醒协议规范" 章节**（约 60 行，替代当前分散在多处的定义）：

```markdown
## 握手与唤醒协议规范

参数定义见 Backlog metadata `wakeup_policy`。

### handshake_agent(agent_name)

1. SendMessage(to=agent_name, lead_ready)
2. 等 agent_ready (timeout=wakeup_policy.timeout)
3. 未收到 & attempts < max_attempts → 重试（告知第 N 次唤醒）
4. 未收到 & attempts >= max_attempts → blocked
5. 收到 → ready，重置计数器

### handle_agent_idle_after_task(agent_name)

1. 检查 inbox 送达
2. check pane: InputValidationError → 重新握手
3. check pane: Bash/Read → 执行中
4. check pane: ❯ → 正常 idle
```

**Backlog metadata** 中新增 `wakeup_policy`：

```yaml
wakeup_policy:
  max_attempts: 3
  timeout: 30s
```

**删除**当前散布的：
- 伪代码 `def handshake_agent()` (line ~107-136)
- Backlog metadata 中散落的 `wakeup_attempts` / `max_wakeup_attempts` 重复定义
- Phase 2 TaskCreate metadata 中的重复 `wakeup_attempts` 块

### YAML 改动

**Phase 2 新增 `handshake_protocol` 字段**（phase 头部，定义一次）：

```yaml
phase_2:
  handshake_protocol: |
    逐个 agent 握手+派发，具体流程见 SKILL.md §握手与唤醒协议规范。
    约束：派发完一个 agent 后不得 idle，必须继续下一个；全部完成前 team-lead 不得 idle。
```

**verify 步骤精简**（3 个 agent 各从 ~20 行伪代码变为 ~5 行引用）：

改前（以 code-analyst 为例）：
```yaml
- step: verify_code_analyst_handshake
  action: |
    等待 code-analyst 回复"【agent_ready】已就绪"。
    **3 次唤醒机制**：
    if not received_agent_ready("code-analyst", timeout=30s):
      wakeup_attempts.code-analyst += 1
      if wakeup_attempts.code-analyst < max_wakeup_attempts:
        SendMessage(to="code-analyst", message="【lead_ready】... (第 {wakeup_attempts.code-analyst} 次唤醒)")
        return "retry"
      else:
        handshake_status.code-analyst = "blocked"
        ...
    ...
```

改后：
```yaml
- step: verify_code_analyst_handshake
  action: |
    对 code-analyst 执行 handshake_agent("code-analyst")。
    成功 → 进入 send_code_analyst_task。
    失败 → 标记 blocked，继续处理下一个 agent。
    派发后不得 idle，必须继续处理下一个 agent。
```

**check_agent_pane_status** 同样精简，引用 `handle_agent_idle()` 而非内嵌伪代码。

### 效果

| 指标 | 改前 | 改后 |
|------|------|------|
| YAML 行数 | ~910 | ~820 |
| 唤醒逻辑定义次数 | 8+ | 3（参数1 + 流程1 + 引用1） |
| 改 max_attempts 需改动 | 8 处 | 1 处 |
| verify 步骤代码重复 | 3 份 ~15 行伪代码 | 3 份 ~5 行引用 |

## 不变的部分

- Phase 0 双向握手协议不变
- Session Lifecycle 不变
- Phase Contracts 表格不变
- 所有 agent 定义不变
- 执行模式不变
- 唤醒机制的行为语义不变

## 关联文件

- `skills/vibe-team-review/SKILL.md` — 新增协议规范章节，精简 Backlog metadata
- `.claude/team-templates/pr-review-team.yaml` — Phase 2 新增 handshake_protocol，精简 verify 步骤
