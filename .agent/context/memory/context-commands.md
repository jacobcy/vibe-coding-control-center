# context-commands

## Summary
上下文管理命令体系，实现跨会话的工作流连续性：`/save` 保存状态，`/continue` 恢复状态，`/check` 验证一致性。

## Key Decisions
- **命令命名**: 动词形式，简短好记 (`/save`, `/continue`, `/check`)
- **职责分离**: 保存/恢复/验证三个独立职责
- **避免冲突**: 不与 Claude Code 内置命令重叠
- **技能注册**: 通过 `.claude-plugin/plugin.json` + `~/.claude/skills/` 符号链接
- **只留最新**: `/check` 发现不一致时以实际代码状态为准

## Commands

### /save
- **用途**: 会话结束时保存上下文
- **存储**: `.agent/context/memory/<topic>.md`, `.agent/context/task.md`
- **触发**: 手动 `/save` + Stop Hook 提醒 (>8 轮)

### /continue
- **用途**: 新会话开始时恢复上下文
- **读取**: `.agent/context/task.md`, `.agent/context/memory.md`, `.agent/context/memory/<topic>.md`
- **触发**: 手动 `/continue`

### /check
- **用途**: 验证记忆与代码一致性
- **检查**: 文件存在性、任务状态同步、引用有效性
- **触发**: 手动 `/check` 或发现问题时

## Workflow

```
/save ──────→ 保存上下文（写入）
                 │
                 ↓
/check ──────→ 验证一致性（审计）
                 │
                 ↓
/continue ───→ 恢复上下文（读取）
```

## Related Tasks
- [x] context-20260221-001: 实现 /save 技能 ✅
- [x] context-20260221-002: 实现 /continue 技能 ✅
- [x] context-20260221-003: 实现 /check 技能 ✅
- [ ] context-20260221-004: 与 /learn 集成

## References
- /save Skill: [.agent/skills/save/SKILL.md](.agent/skills/save/SKILL.md)
- /continue Skill: [.agent/skills/continue/SKILL.md](.agent/skills/continue/SKILL.md)
- /check Skill: [.agent/skills/check/SKILL.md](.agent/skills/check/SKILL.md)
- Plugin 配置: [.claude-plugin/plugin.json](.claude-plugin/plugin.json)

---
Created: 2026-02-21
Last Updated: 2026-02-22
Sessions: 2
