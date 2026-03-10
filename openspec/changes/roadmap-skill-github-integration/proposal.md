## Why

当前项目缺少"智能调度器"能力，无法将 GitHub Issue（许愿池）转化为有计划的版本目标。具体问题：

1. **没有版本目标**：vibe task list 只有任务基础功能，没有调度能力
2. **Issue 无处安放**：Issue 作为需求池很好（不污染代码），但没有分类机制
3. **版本规划缺失**：不知道 v2 做到什么程度、v3 做什么，没有 changelog 自动生成能力

## What Changes

1. **新增智能调度器 (vibe-roadmap)**
   - 创建 `skills/vibe-roadmap/SKILL.md`
   - 注册到 `skills/vibe-skills-manager/registry.json`
   - 维护版本目标和 Issue 分类状态机

2. **重新定义 Issue 分类**
   - P0 (紧急)：阻断性问题，需要立即处理，不受版本约束
   - 当前版本：明确纳入本版本，按优先级分配
   - 下一个版本：有更优先事项，但要做，本版本结束后自动成为下版本目标
   - 延期：待决定，暂时不做
   - 拒绝：不做

3. **调度器触发机制**
   - 每次 `/vibe-new` 发动时，在任务编排器之前先调用调度器
   - 用户指定具体任务 → 直接交给编排器
   - 用户未指定 → 调度器分配优先任务

4. **版本周期管理**
   - 版本结束时：确认下一版本目标 → 决定未分类 Issue 的归属
   - Changelog 自动生成：大功能 +0.1，小功能 +0.01

5. **GitHub 整合**
   - 支持 `--provider github` 从 Issue 拉取许愿池

## Capabilities

### New Capabilities

- `roadmap-skill`: 智能调度器，维护版本目标和 Issue 分类
- `github-sync`: GitHub Issues 与本地 Task 的同步适配器
- `roadmap-data-model`: Issue 分类状态机数据定义

### Modified Capabilities

- `cli-commands`: 新增 `vibe roadmap` 命令族和 `vibe task sync --provider` 参数
- `vibe-new`: 在任务编排前先调用调度器

## Impact

- **新增文件**: `skills/vibe-roadmap/SKILL.md`
- **修改文件**: `skills/vibe-skills-manager/registry.json`, `lib/task_actions.sh`, `lib/task_help.sh`, `.agent/skills/vibe-new/SKILL.md`
- **测试文件**: `tests/test_task_sync_github.bats`, `tests/test_roadmap_scheduler.bats`
- **数据**: `registry.json` 扩展 Issue 分类字段
