# save-command

## Summary
/save 和 /continue 命令实现跨会话的工作流连续性：/save 保存状态，/continue 恢复状态。

## Key Decisions
- **命名: `/save`** - 描述动作（保存上下文），而非告别
- **命名: `/continue`** - 描述动作（继续任务），与 `/save` 形成闭环
- **主题式组织** - 比日期式更利于检索
- **分节更新策略** - 只替换有变化的部分，保留已有内容
- **任务 ID 格式**: `<topic>-YYYYMMDD-NNN` - 可读性和可追溯性，用于关联主题
- **与 /learn 独立** - `/save` 保存项目上下文，`/learn` 提取全局模式
- **迭代式实现策略** - Skill (轻量级) → Hooks (提醒) → Plugin (完整) (2026-02-21)
- **自我验证** - 用 `/save` 来验证 `/save` 的实现 (2026-02-21)
- **Hook 文件位置**: `.claude/hooks/` 目录 (2026-02-21)
- **/continue 不自动执行** - 只加载上下文，让用户确认后才开始 (2026-02-21)
- **Skill description 语言**: 必须用英文，包含明确触发条件 (如 "Use when user says /save") (2026-02-21)
- **Skill 注册方式**: `.claude-plugin/plugin.json` + `~/.claude/skills/` 符号链接 (2026-02-21)

## Problems & Solutions
### Skill vs Plugin 选择
- **Issue**: 如何确定 `/save` 的实现方式？
- **Solution**: 采用迭代策略 - 先实现轻量级 Skill (纯 LLM 逻辑)，再添加 Hooks (自动提醒)，最终包装为 Plugin

### 现有 memory.md 兼容性
- **Issue**: 如何处理现有的 memory.md 结构？
- **Solution**: 扩展现有结构，新增 Topic Index 表格，保持 Key Decisions、Execution Log 等现有部分

### Hook 会话隔离
- **Issue**: 多个并行会话如何避免计数器冲突？
- **Solution**: 使用 `${PPID}` 作为计数器文件后缀，每个会话进程有独立的计数文件

### 跨会话工作流连续性
- **Issue**: 如何在新会话中自动恢复上次的工作状态？
- **Solution**: /continue 技能读取 task.md 和 memory/<topic>.md，通过任务 ID 前缀关联主题，恢复完整上下文

### Skills 不被 Claude Code 识别
- **Issue**: 自定义的 /save 和 /continue skills 无法被 Claude Code 识别
- **Solution**:
  1. 将 description 改为英文，包含明确的触发条件
  2. 创建 `.claude-plugin/plugin.json` 注册 skills 目录
  3. 在 `~/.claude/skills/` 创建符号链接 (vibe-save, vibe-continue)
  4. 确保 SKILL.md 文件名和目录结构符合规范

## Related Tasks
- [x] save-20260221-001: 实现 /save Skill 核心逻辑 ✅
- [x] save-20260221-002: 创建 memory/ 目录结构 ✅
- [x] save-20260221-003: 扩展 memory.md 索引 ✅
- [x] save-20260221-004: 实现 Stop Hook 提醒机制 (P1) ✅
- [x] save-20260221-007: 实现 /continue 技能 ✅
- [x] save-20260221-008: 修复 Skill 格式使其被 Claude Code 识别 ✅
- [ ] save-20260221-005: 与 /learn 集成 (P2) → 迁移到 context-20260221-004
- [ ] save-20260221-006: 将项目包装成 Plugin → 待定

> 注：save-command 主题已合并到 context-commands，后续任务使用 context- 前缀。

## References
- 设计文档: [docs/plans/2026-02-21-save-command-design.md](docs/plans/2026-02-21-save-command-design.md)
- /save Skill: [.agent/skills/save/SKILL.md](.agent/skills/save/SKILL.md)
- /continue Skill: [.agent/skills/continue/SKILL.md](.agent/skills/continue/SKILL.md)
- Hooks 配置: [.claude/hooks/hooks.json](.claude/hooks/hooks.json)

---
Created: 2026-02-21
Last Updated: 2026-02-21
Sessions: 5
