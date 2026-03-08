---
name: vibe-check
description: Use when the user wants to verify project memory consistency, says "/vibe-check", "verify memory", or "check context". Validates that memory.md, task.md, and memory/ topics match actual project state. Now with intelligent task status sync based on PR merged events.
---

# /vibe-check - Intelligent Status Sync & Memory Consistency

智能任务状态同步 + 项目记忆一致性验证。检测外部事件（PR merged）并自动建议状态更新，同时验证文档腐烂（documentation rot）。

**核心职责**:
1. **智能状态同步**: 检测 PR merged 事件，分析任务完成度，提示用户确认后修正状态
2. **内存一致性检查**: 确保 `.agent/` 和 `.git/` 目录的一致性，task 记录和 memory 文件与实际代码状态对齐

**核心原则:** 渐进式智能，保留人工决策权，只留最新，确保可信。

**Announce at start:** "我正在使用 /vibe-check 技能来执行智能状态同步和内存一致性验证。"

**命令边界:** `/vibe-check` 是 skill 层入口；`vibe check`、`vibe flow review` 是 shell 层工具。只要 shell 参数、子命令或 flag 有任何不确定，先运行对应命令的 `-h` / `--help`。这些 shell 命令是 agent 的工具入口，不是面向用户的命令教学清单。

## 工作流程

### Step 0: Shell-Level Audit (Phase 1 - 静态检查)

 ```bash
 vibe check
 ```

运行 `vibe check` 进行全面的 Registry、任务归档以及物理真源审计。解释其审计结果。

**Phase 1 包括**:
- Registry 与 OpenSpec 同步
- completed → archived 自动流转
- 僵尸分支检测
- 散落文档检测
- 分支-任务一致性检查

### Step 1: PR Merged Detection (Phase 2 - Git 状态检查)

如果 Shell 层检测到有任务的 PR 已合并，继续智能分析流程。

**获取 PR 数据**:
```bash
# 获取任务关联的 PR 详细信息
vibe flow review <branch> --json
```

返回数据包括：
- PR number, title, body
- Comments and reviews
- Commits
- State and mergedAt

### Step 2: Subagent Analysis (Phase 3 - 智能分析)

**使用 Agent tool，启动 subagent_type="Explore"**

**任务**: 分析 PR 是否完成了所有绑定的 tasks

**输入数据**:
- PR 数据（number, title, body, comments, reviews, commits）
- Branch 绑定的 task 列表（每个 task 的 title/description）

**分析方法**:
1. 仔细阅读 PR 描述，理解 PR 实际完成了什么
2. 阅读评论和 review，获取更多上下文
3. 对比每个 task 的目标
4. 给出判断

**输出格式（JSON）**:
```json
{
  "results": [
    {
      "task_id": "xxx",
      "completed": true/false,
      "confidence": 0.0-1.0,
      "reason": "基于 ... 判断"
    }
  ]
}
```

**置信度分级**:
- confidence > 0.8: 高置信度，AI 可直接决定
- 0.5 <= confidence <= 0.8: 中置信度，需要用户确认
- confidence < 0.5: 低置信度，跳过

### Step 3: Confidence-Based Processing (置信度分级处理)

根据 Subagent 返回的置信度进行分级处理：

**高置信度 (> 0.8)**:
```
✅ 确定完成的任务：
  • 2026-03-05-add-login (置信度: 0.92)
    原因：PR 描述明确提到完成了 feature-a
```
→ 自动记录建议，等待用户最终确认

**中置信度 (0.5-0.8)**:
```
⚠️ 需要确认的任务：
  • 2026-03-04-feature-b (置信度: 0.65)
    原因：评论中有讨论，但未明确完成
```
→ 询问用户选择处理方式

**低置信度 (< 0.5)**:
```
⏭️ 跳过的任务：
  • 2026-03-04-feature-c (置信度: 0.32)
    原因：PR 内容未提及
```
→ 不做建议，跳过

### Step 4: User Interaction (用户交互流程)

**显示建议列表**:
```
💡 建议操作：
✅ 标记以下任务为已完成：
  1. 2026-03-04-feature-a
  2. 2026-03-04-feature-b

是否执行？[Y/n]
```

**中置信度任务的处理选项**:
```
⚠️ 无法确定以下任务是否完成：
  1. 2026-03-04-feature-b (中置信度)

请选择处理方式：
1. 深度分析代码变更
2. 手动选择是否完成
3. 跳过这些任务

选择 [1-3]:
```

**选项 1: 深度代码分析（可选）**:
- 调用 subagent_type="Explore"
- 输入：task 的功能需求 + PR 的代码变更
- 分析：代码是否实现了 task 的功能需求
- 输出：完成度评估

**选项 2: 手动选择**:
- 显示任务列表
- 让用户手动勾选完成的任务

**选项 3: 跳过**:
- 不处理这些任务
- 继续到最终确认

### Step 5: Execute Status Updates (执行状态更新)

用户确认后，调用 Shell API 更新状态：

```bash
for task_id in tasks_to_update; do
  vibe task update "$task_id" --status completed
done
```

### Step 6: Memory Consistency Check (内存一致性检查)

完成智能状态同步后，继续执行原有的内存一致性检查：

```bash
memory_index=".agent/context/memory.md"
memory_dir=".agent/context/memory/"
task_file=".agent/context/task.md"
```

**验证内容**:
- 文件存在性检查
- 任务状态一致性
- 代码引用有效性
- 项目治理状态

### Step 7: Final Report (最终报告)

```
📋 Vibe Check 完整报告

## 智能状态同步
✅ 已更新：2 个任务
  • 2026-03-04-feature-a
  • 2026-03-04-feature-b

## 静态检查
✅ Registry 与 OpenSpec 已同步
✅ 3 个任务已归档
⚠️  发现 2 个僵尸分支

## 内存一致性
✅ 所有引用有效
⚠️  2 个不一致性

💡 推荐操作：
  1. 清理僵尸分支
  2. 修复内存不一致
  3. 运行 /vibe-save 清理
```

## 检查项目清单

| 检查项 | 说明 | 严重程度 | 阶段 |
|--------|------|----------|------|
| PR merged 检测 | 检测已合并 PR 关联的任务 | 高 | Phase 2 |
| 智能完成度分析 | AI 分析任务是否完成 | 高 | Phase 3 |
| 幽灵分支 | 无关联任务的长期存活分支 | 高 | Phase 1 |
| 文档散落 | 任务文档遗留在 docs/plans | 高 | Phase 1 |
| 文件存在 | 引用的文件是否存在 | 高 | Phase 1 |
| 状态同步 | task.md 和 topic 文件状态一致 | 中 | Phase 1 |
| 引用有效 | References 中的链接有效 | 中 | Phase 1 |

## 优雅降级

**gh CLI 不可用时**:
```
⚠️  gh CLI not found or not authenticated
跳过 PR 状态检查，继续静态检查...
```
- 自动跳过 Phase 2 和 Phase 3
- 继续执行 Phase 1 的静态检查
- 不影响其他功能

**网络错误时**:
```
⚠️  Network error during PR query
继续其他检查...
```
- 捕获错误，优雅降级
- 继续执行其他检查
- 显示友好的错误提示

## 与其他命令的关系

```
/vibe-save ─→ 保存上下文（写入）
                 │
                 ↓
/vibe-check ─→ 智能状态同步 + 验证一致性（审计）
                 │
                 ↓
/review ─────→ 物理与逻辑深度审计（Codex）
                 │
                 ↓
/vibe-continue → 恢复上下文（读取）
```

**工作流**:
1. `/vibe-save` - 会话结束时保存
2. `/vibe-check` - 定期智能同步 + 验证一致性
3. `/vibe-continue` - 新会话开始时恢复

## 设计决策

1. **渐进式智能** - 从确定性到启发式，逐层递进
2. **保留人工决策权** - AI 辅助，但最终决策在人
3. **优雅降级** - gh 不可用时仍能做静态检查
4. **实时查询 gh** - 不同步本地 PR 记录，符合单一真源原则
5. **置信度分级** - 高/中/低置信度差异化处理
6. **用户确认** - 状态更新前必须用户确认

## 示例用法

```
用户: /vibe-check
Claude: 我正在使用 /vibe-check 技能来执行智能状态同步和内存一致性验证。

        ## Phase 1: 静态检查
        ✅ Registry 与 OpenSpec 已同步
        ✅ 3 个任务已归档
        ⚠️  发现 2 个僵尸分支

        ## Phase 2: Git 状态检查
        🔍 发现 1 个已合并的 PR：
          • PR #42: "feat: implement multi-feature"
            Branch: claude/multi-feature
            Merged: 2026-03-05

        ## Phase 3: 智能分析
        🤖 调用 AI 分析 PR 内容...

        分析结果：
        ✅ 高置信度（AI 决定）：
          • 2026-03-04-feature-a (置信度: 0.92)
            原因：PR 描述明确提到完成了 feature-a

        ⚠️  中置信度（需要确认）：
          • 2026-03-04-feature-b (置信度: 0.65)
            原因：评论中有讨论，但未明确完成

        💡 建议操作：
        ✅ 标记 "2026-03-04-feature-a" 为已完成

        ⚠️  无法确定 "2026-03-04-feature-b" 是否完成
        请选择处理方式：
        1. 深度分析代码变更
        2. 手动选择是否完成
        3. 跳过此任务

        选择 [1-3]: 1

        🤖 深度分析代码变更...

        深度分析结果：
        Task: 2026-03-04-feature-b
        需求: 添加用户认证功能

        代码变更分析：
        • 新增文件: auth/login.py (✅ 实现)
        • 新增文件: tests/test_auth.py (✅ 测试)
        • 修改文件: config.py (✅ 配置)

        结论：已完成 (置信度: 0.88)

        💡 最终建议：
        ✅ 标记以下任务为已完成：
          1. 2026-03-04-feature-a
          2. 2026-03-04-feature-b

        是否执行？[Y/n] y

        ✅ 已更新 2 个任务状态

        ## Phase 4: 内存一致性检查
        ✅ 所有引用有效
        ⚠️  2 个不一致性
        ...
```

## 实现优先级

1. **P0**: PR merged 检测
2. **P0**: Subagent 智能分析
3. **P0**: 用户确认流程
4. **P1**: 深度代码分析（可选）
5. **P1**: 优雅降级处理
6. **P2**: 内存一致性检查增强
