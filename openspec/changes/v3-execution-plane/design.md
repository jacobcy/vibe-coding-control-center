## Context

**背景**：V2 架构中，控制平面（`vibe flow`）直接调用 worktree/tmux 操作，导致职责混乱和会话管理问题。V3 架构将执行职责明确分离为独立平面。

**当前状态**：
- `config/aliases/` 已有基础的 worktree 和 tmux 命令
- 命名约定不统一（如 `wtnew`, `wtdone` 等命名不一致）
- 缺乏标准化的会话恢复机制
- 无执行结果回写契约

**约束**：
- 必须复用 V2 aliases 核心逻辑，不重写执行理念
- 遵守 CLAUDE.md HARD RULES（LOC 限制、拒绝过度工程化）
- 兼容现有开发者工作流

**相关方**：
- 开发者（Human Mode 用户）
- OpenClaw Agent（自动调用执行平面）
- Control Plane（消费执行结果）

## Goals / Non-Goals

**Goals：**
1. 建立统一的 worktree/tmux 命名规范（`wt-<owner>-<task-slug>` / `<agent>-<task-slug>`）
2. 实现标准化的执行结果回写契约（JSON 格式）
3. 支持双模式执行（Human + OpenClaw）
4. 提供会话恢复能力（< 30 秒恢复现场）
5. 自动处理命名冲突（追加短后缀）

**Non-Goals：**
1. 不定义任务生命周期状态机（由 control plane 负责）
2. 不实现 provider 路由逻辑（由 process plane 负责）
3. 不创建新的测试框架（使用现有 bats）
4. 不实现复杂缓存或持久化机制（保持简单）

## Decisions

### Decision 1: 命名规范统一

**选择**：采用 `wt-<owner>-<task-slug>` 和 `<agent>-<task-slug>` 格式

**理由**：
- 明确所有权（owner/agent），便于多 agent 并行场景
- task-slug 保持可读性，避免哈希混淆
- 冲突时追加短后缀（如 `-a1b2`），而非报错中断

**备选方案**：
- ❌ 使用哈希 ID：可读性差，难以人工识别
- ❌ 使用时间戳：不直观，无法快速定位

### Decision 2: 执行结果回写机制

**选择**：使用 JSON 文件作为回写媒介（`.agent/execution-results/<task_id>.json`）

**理由**：
- 简单可靠，无需数据库依赖
- 人类可读，便于调试
- 符合 CLAUDE.md "零死代码" 原则（避免复杂持久化）

**备选方案**：
- ❌ 环境变量：无法持久化，会话丢失后不可恢复
- ❌ SQLite：过度工程化，违反 LOC 限制

**回写字段**：
```json
{
  "task_id": "abc123",
  "resolved_worktree": "wt-claude-add-user-auth",
  "resolved_session": "claude-add-user-auth",
  "executor": "human",  // or "openclaw"
  "timestamp": "2026-03-03T06:30:00Z"
}
```

### Decision 3: 双模式实现策略

**选择**：Human Mode 和 OpenClaw Mode 调用同一命令面，通过环境变量区分执行者

**理由**：
- 避免代码重复（符合 CLAUDE.md "拒绝过度工程化"）
- 单一真实来源（Single Source of Truth）
- 易于测试和维护

**实现**：
```bash
# Human Mode
wtnew add-user-auth

# OpenClaw Mode (通过 skill 封装)
EXECUTOR=openclaw wtnew add-user-auth
```

### Decision 4: 会话恢复机制

**选择**：基于 task/worktree/session hint 查找并恢复

**理由**：
- 利用现有 git worktree 和 tmux 能力
- 无需额外状态管理系统
- 符合 "简单优先" 原则

**恢复流程**：
1. 根据 task_id 查找 `.agent/execution-results/<task_id>.json`
2. 读取 `resolved_worktree` 和 `resolved_session`
3. 切换到 worktree 并 attach tmux session
4. 若 session 丢失，提供重建提示

### Decision 5: 冲突处理策略

**选择**：自动追加 4 字符短后缀（基于时间戳哈希）

**理由**：
- 避免人工干预，保持流程顺畅
- 后缀足够短，不影响可读性
- 冲突概率极低（4 字符 = 1.6M 组合）

**示例**：
```
wt-claude-add-user-auth      # 原始名称
wt-claude-add-user-auth-a1b2 # 冲突后
```

## Risks / Trade-offs

### Risk 1: JSON 文件损坏或丢失
→ **缓解**：
- 回写前验证 JSON 格式
- 提供恢复命令（基于 worktree/session 重建）
- 定期备份 `.agent/execution-results/` 目录

### Risk 2: 命名冲突在极端情况下仍可能发生
→ **缓解**：
- 4 字符后缀足够应对 99.9% 场景
- 若仍冲突，报错并提示人工介入
- 记录冲突日志供后续分析

### Risk 3: tmux session 丢失导致无法恢复
→ **缓解**：
- 提供 `wtrecover` 命令重建 session
- worktree 仍然存在，仅 session 丢失
- 记录 session 创建参数便于重建

### Risk 4: 双模式调用可能引入不一致
→ **缓解**：
- 统一测试覆盖两种模式
- Code Review 重点检查执行路径一致性
- 使用相同的环境变量读取逻辑

### Trade-off 1: JSON 文件 vs 数据库
- **优点**：简单、无依赖、人类可读
- **缺点**：无事务保证、查询能力有限
- **决策**：对于当前规模（< 100 并发任务），JSON 文件足够

### Trade-off 2: 自动后缀 vs 人工干预
- **优点**：流程顺畅，无阻塞
- **缺点**：名称可能变长
- **决策**：可接受，后缀仅 4 字符

## Migration Plan

### 阶段 1: 基础能力增强（Week 1）
1. 增强 `config/aliases/worktree.sh`：
   - 添加命名规范校验
   - 实现冲突检测和自动后缀
2. 增强 `config/aliases/tmux.sh`：
   - 添加 session 命名规范
   - 实现会话恢复命令
3. 创建 `config/aliases/execution-contract.sh`：
   - 实现 JSON 回写逻辑
   - 提供读取和查询接口

### 阶段 2: OpenClaw Skill 封装（Week 2）
1. 创建 `skills/execution-plane/SKILL.md`
2. 封装 worktree/tmux 操作为可调用技能
3. 设置 `EXECUTOR=openclaw` 环境变量

### 阶段 3: 集成测试（Week 3）
1. 测试 Human Mode 完整流程
2. 测试 OpenClaw Mode 完整流程
3. 测试会话恢复能力（< 30 秒）
4. 测试命名冲突处理

### 阶段 4: 文档和迁移（Week 4）
1. 更新 CLAUDE.md 添加 execution plane 说明
2. 更新 `.agent/rules/` 添加执行平面规则
3. 提供迁移指南（从 V2 aliases 迁移）

### 回滚策略
- 保留 V2 aliases 命令作为备份
- 新命令失败时可快速切回旧命令
- JSON 文件损坏时可手动删除重建

## Open Questions

1. **Q**: 是否需要统一 `wtrm` 与 tmux 清理的联动策略？
   - **建议**：暂不联动，保持命令职责单一。可在后续迭代中添加 `wtcleanup` 联动命令。

2. **Q**: OpenClaw 自动重试次数默认值多少合适？
   - **建议**：默认 3 次，可通过环境变量 `OPENCLAW_RETRY_COUNT` 覆盖。

3. **Q**: JSON 文件是否需要定期清理？
   - **建议**：提供 `wtclean-results` 命令清理已完成任务的 JSON 文件（archived 状态）。

4. **Q**: 是否需要支持跨 worktree 共享执行结果？
   - **建议**：当前设计已支持，JSON 文件存储在 `.agent/execution-results/`，所有 worktree 可访问。
