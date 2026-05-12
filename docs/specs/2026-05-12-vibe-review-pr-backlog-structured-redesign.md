# Vibe-Review-PR Backlog 结构化重构

## 问题

刚完成的唤醒协议单源化重构解决了参数/流程/引用的三层解耦，但 Backlog task 的 description 存在更深层的结构问题：

1. **Phase 编号不一致**：SKILL.md Backlog 用 Phase 1-5，YAML 用 phase_1/2/2.5/3/4，Phase 3 在两边指向完全不同的阶段
2. **Phase 3-5 的 description 过于简短**：各只有 1 句话，team-lead 执行时缺乏操作指引
3. **缺少输入/输出/门禁契约**：team-lead 不知道每个阶段需要什么上游产出、应该交付什么、进入下一阶段的条件是什么
4. **fix-executor 握手硬编码重复**：YAML `wait_fix_ready` 硬编码了 3 次重试，未引用 centralized handshake_protocol

## 设计目标

- **Backlog task 标准化**：每个 Phase 的 description 统一为 `【输入】/【输出】/【步骤】/【门禁】` 四段结构
- **Phase 编号统一**：YAML phase_2.5→phase_3, phase_3→phase_4, phase_4→phase_5
- **消除最后一处重复**：fix-executor 唤醒逻辑引用 handshake_protocol
- **步骤可执行**：每条步骤都是具体动作，不是描述性语句；引用协议而非重复逻辑

## 方案

### Backlog description 标准化模板

```yaml
description: |
  【输入】
  - <上游产出1>
  - <上游产出2>

  【输出】
  - <本阶段交付物>

  【步骤】
  1. <具体动作>（引用协议/工具）
  2. ...

  【门禁】
  - <进入下一阶段前必须为真的布尔条件>
```

### 五阶段契约

#### Phase 1: 背景调研

```
【输入】PR 编号
【输出】phase_1_output（结构化背景报告，保存到 task metadata）
【步骤】
1. team-lead 自身 ToolSearch
2. spawn context-researcher，仅握手 prompt
3. 按 handshake_agent("context-researcher") 执行握手（含 3 次唤醒）
4. 收到 agent_ready 后，SendMessage 下发正式调研任务（含 PR 编号）
5. 等待 teammate-message 获取背景报告
6. TaskUpdate 保存 phase_1_output 到 metadata，标记 status="completed"
【门禁】
- handshake_status.context-researcher == "ready"
- phase_1_output 非空且包含 PR 概述/改动范围/关联 issue/风险评估
```

#### Phase 2: 专家评审

```
【输入】phase_1_output（从 Phase 1 task metadata 获取）
【输出】code-analyst / architect-reviewer / security-reviewer 的审查报告
【步骤】
1. TaskGet Phase 1 → 提取 phase_1_output，确认 context-researcher handshake_status == "ready"
2. 依次对每个 agent（code-analyst → architect → security）：
   a. spawn agent，仅握手 prompt，run_in_background=true
   b. 按 handshake_agent(agent_name) 执行握手（含 3 次唤醒）
   c. 收到 agent_ready 后，SendMessage 下发正式任务（含 phase_1_output）
   d. 派发后不得 idle，立即继续下一个 agent
3. 等待所有已握手 agent 的 task-notification（status=completed）
4. 收集全部报告
【门禁】
- 至少 1 个 agent handshake_status == "ready" 且返回了有效报告
- 未握手 agent 的报告标记为无效，不计入
```

#### Phase 3: Codex 复查

```
【输入】Phase 2 全部审查报告
【输出】codex 验证报告（或 skip 标记及原因）
【步骤】
1. 收集 Phase 2 所有报告
2. 校验各报告基础数据（文件数/行数/涉及模块）是否与 PR 实际 diff 一致
3. 失真报告标注"报告作废"
4. 判断触发条件（安全PR / diff>500行 / 报告冲突 / 报告缺失）
5. 满足且报告质量合格 → codex:rescue（仅传结构化报告，禁止传 diff）
6. 不满足或全部报告不合格 → 记录 skip 原因
【门禁】
- 已做出"启用 codex"或"跳过 codex"的明确决定（不可跳过此判断）
- 如启用 codex：codex 报告已收到并保存
- 此阶段不涉及 agent 握手
```

#### Phase 4: 综合判断

```
【输入】Phase 2 可用报告（剔除作废） + Phase 3 codex 报告（如有）
【输出】最终决策（APPROVE / NEEDS_CHANGES / REJECT）+ 结构化审查报告
【步骤】
1. 收集 Phase 2 可用报告，剔除 Phase 3 标记为作废的
2. 收集 Phase 3 codex 报告（如有）
3. 仲裁不同报告间的冲突，记录仲裁理由
4. 生成最终决策
5. 按 output_format 格式化审查报告（禁虚假评分、禁无关指标、强制规则引用）
6. 缺失 agent 报告标注"审查不完整"，不脑补结论
【门禁】
- 最终决策已做出
- 审查报告已按 Review Quality Standards 自查通过
- 禁止使用已作废的报告做结论
```

#### Phase 5: 写回 + 修复

```
【输入】Phase 4 最终决策和审查报告
【输出】PR comment + follow-up issues + 可选修复 commit
【步骤】
1. 判断执行模式（auto-fix / comment-only / auto-decide / ask-each）
2. 写 PR comment（必须包含：决策/已解决/遗留/规则引用）
3. 如 auto-fix 模式：
   a. spawn fix-executor，仅握手 prompt
   b. 按 handshake_agent("fix-executor") 执行握手（含 3 次唤醒）
   c. 收到 agent_ready 后，SendMessage 下发修复任务（含审查报告）
   d. 等待修复完成并验证
4. 范围外问题创建 follow-up issues（先搜索去重）
5. 禁止把阻塞问题转 follow-up
【门禁】
- PR comment 已通过 gh pr comment 发布
- 范围外问题已创建 follow-up issue 或确认无需创建
```

### YAML 改动

**Phase 编号重排**：
- `phase_2.5` → `phase_3`（Codex第三方验证 → Codex复查）
- `phase_3` → `phase_4`（综合判断与改进 → 综合判断）
- `phase_4` → `phase_5`（写回与改进 → 写回+修复）

**fix-executor 握手去重**：`wait_fix_ready` 步骤改为：
```yaml
- step: wait_fix_ready
  action: |
    等待 fix-executor 回复"【agent_ready】已就绪"，按 handshake_protocol 执行
    （见 SKILL.md §握手与唤醒协议规范）。
    未收到 → 按 handshake_agent() 重试/blocked 逻辑处理。
    收到 → 立即进入 send_fix_task。
```
删除当前硬编码的 3 次 30 秒重试伪代码。

### 效果

| 指标 | 改前 | 改后 |
|------|------|------|
| Phase 编号一致性 | SKILL.md≠YAML（2.5 vs 3 错位） | 完全一致（1-5） |
| Phase 3-5 description 长度 | 各 1 句话 | 各含输入/输出/步骤/门禁 4 段 |
| 握手逻辑硬编码 | YAML wait_fix_ready 重复 3 次重试 | 全部引用 handshake_protocol |
| Backlog 格式 | 自然语言叙述 | 统一四段模板 |

## 不变的部分

- 唤醒协议单源结构不变（wakeup_policy + handshake_agent + handle_agent_idle）
- Phase Contracts 表不变
- Review Quality Standards 不变
- Hard Rules 不变
- Session Lifecycle 不变
- Recovery 流程不变
- 握手机制行为语义不变

## 关联文件

- `skills/vibe-review-pr/SKILL.md` §Step 6.5 Backlog Setup — Phase 1-5 TaskCreate description 重写
- `.claude/team-templates/pr-review-team.yaml` — phase 编号重排 + wait_fix_ready 去重
