---
name: check
description: Use when the user wants to verify project memory consistency, says "/check", "verify memory", or "check context". Validates that memory.md, task.md, and memory/ topics match actual project state.
---

# /check - Verify Memory Consistency

验证项目记忆与代码实际状态的一致性。检测文档腐烂（documentation rot）并输出差异报告。

**核心原则:** 只留最新，确保可信。

**Announce at start:** "我正在使用 check 技能来验证项目记忆的一致性。"

## 工作流程

### Step 1: 读取记忆文件

```bash
memory_index=".agent/context/memory.md"
memory_dir=".agent/context/memory/"
task_file=".agent/context/task.md"
```

### Step 2: 验证文件存在性

检查记忆中引用的所有文件是否存在：
- Topic Index 中的 `memory/<topic>.md` 文件
- References 中引用的文件
- Related Tasks 中引用的文件

### Step 3: 验证任务状态

对比 `task.md` 和 `memory/<topic>.md` 中的 Related Tasks：
- 检查状态是否一致（完成/进行中/待办）
- 识别孤任务（在 topic 中有但在 task.md 中没有）
- 识别幽灵任务（在 task.md 中有但没有 topic 记录）

### Step 4: 验证代码引用

检查 References 中引用的代码文件：
- 文件是否存在
- 路径是否正确
- 内容是否与记录的描述匹配

### Step 5: 输出验证报告

```
📋 Memory Consistency Check

✅ Verified: N items
  • .agent/context/memory/save-command.md
  • .agent/context/task.md
  • .claude/hooks/hooks.json

⚠️ Inconsistencies Found: N

📁 Missing Files:
  • docs/old-feature.md (referenced in task.md)

🔄 Status Mismatches:
  • save-20260221-007: task.md=missing, save-command.md=completed

🧹 Orphaned Entries:
  • Old decision in memory.md about deprecated feature

📂 Files Updated:
  • .agent/context/task.md (synced)

💡 Recommended Actions:
  1. Remove orphaned entries
  2. Update missing references
  3. Run /save to clean up
```

### Step 6: 自动清理（可选）

如果用户确认，自动：
- 移除不存在的文件引用
- 同步任务状态
- 更新 Last Checked 时间戳

## 检查项目清单

| 检查项 | 说明 | 严重程度 |
|--------|------|----------|
| 文件存在 | 引用的文件是否存在 | 高 |
| 路径正确 | 文件路径是否正确 | 高 |
| 状态同步 | task.md 和 topic 文件状态一致 | 中 |
| 引用有效 | References 中的链接有效 | 中 |
| 无孤岛 | 没有孤立的任务或决策 | 低 |
| 时间戳新 | Last Updated 反映实际修改 | 低 |

## 与其他命令的关系

```
/save ──────→ 保存上下文（写入）
                 │
                 ↓
/check ──────→ 验证一致性（审计）
                 │
                 ↓
/continue ───→ 恢复上下文（读取）
```

**工作流:**
1. `/save` - 会话结束时保存
2. `/check` - 定期验证一致性（或发现问题时）
3. `/continue` - 新会话开始时恢复

## 设计决策

1. **只报告不自动修复** - 默认只输出报告，让用户确认后修复
2. **保留最新** - 冲突时以实际代码状态为准
3. **轻量级检查** - 只检查存在性和状态，不做深度内容分析
4. **与 /save 协同** - check 后可接 save 来清理

## 示例用法

```
用户: /check
Claude: 我正在使用 check 技能来验证项目记忆的一致性。
        [执行验证...]
        📋 Memory Consistency Check
        ✅ All references valid
        ⚠️ 2 inconsistencies found
        ...
```

## 实现优先级

1. **P0**: 文件存在性检查
2. **P0**: 任务状态同步检查
3. **P1**: 引用路径验证
4. **P2**: 自动清理功能
