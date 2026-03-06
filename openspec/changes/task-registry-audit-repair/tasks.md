# Implementation Tasks: Task Registry Audit & Repair

## 1. Shell 层基础设施

- [x] 1.1 在 `lib/task.sh` 中新增 `_task_audit_branches()` 函数 - 核对 worktrees.json 的 null branch 字段
- [x] 1.2 在 `lib/task.sh` 中新增 `_task_fix_branches()` 函数 - 自动修复 null branch 字段
- [x] 1.3 在 `lib/task.sh` 中新增 `_task_check_branch_registration()` 函数 - 检查分支任务注册
- [x] 1.4 在 `lib/task.sh` 中新增 `_task_check_openspec_sync()` 函数 - 检查 OpenSpec 同步状态
<!-- DELETED: Violates architecture - Shell layer should not do PR analysis -->
<!-- DELETED: Moved to Skill layer -->
- [x] 1.7 在 `lib/task.sh` 中集成 `vibe_task_audit()` 主函数，编排三阶段核对

## 2. Shell 层命令接口

- [x] 2.1 扩展 `bin/vibe` 支持 `vibe task audit` 子命令
- [x] 2.2 实现 `vibe task audit --fix-branches` 参数处理
- [x] 2.3 实现 `vibe task audit --check-branches` 参数处理
- [x] 2.4 实现 `vibe task audit --check-openspec` 参数处理
<!-- DELETED: Violates architecture - Shell layer should not do PR analysis -->
- [x] 2.6 实现 `vibe task audit --all` 参数处理（运行所有检查）
- [x] 2.7 实现 `vibe task audit --dry-run` 参数处理（预览模式）
- [x] 2.8 更新 `lib/task_help.sh` 添加 audit 相关帮助文档

<!-- Architecture Refactoring: Removed vibe task sync -->
<!-- - vibe task sync deleted - Shell layer should not make smart decisions -->
<!-- - Enhanced --check-openspec to provide context data -->
<!-- - Added --check-plans to check docs/plans and docs/prds -->

- [x] 2.9 删除 vibe task sync 命令 - Shell 层不应做智能判断
- [x] 2.10 增强 --check-openspec 提供更多上下文数据（tasks.md 完成度）
- [x] 2.11 新增 --check-plans 参数 - 检查 docs/plans 和 docs/prds

## 3. Skill 层编排流程

- [ ] 3.1 更新 `skills/vibe-task/SKILL.md` 添加 audit 模式说明
- [ ] 3.2 在 SKILL.md 中实现 Step 0: 运行 `vibe task audit` 获取核对结果
- [ ] 3.3 在 SKILL.md 中实现结果解析和健康度评估
- [ ] 3.4 在 SKILL.md 中实现修复建议生成逻辑
- [ ] 3.5 在 SKILL.md 中实现用户交互流程（批量 vs 逐个确认）
- [ ] 3.6 在 SKILL.md 中实现修复执行和验证逻辑

## 4. 数据质量修复 (Phase 1 MVP)

- [x] 4.1 实现分支字段自动检测逻辑 - 从 git worktree list 获取实际分支
- [x] 4.2 实现备份机制 - 修复前创建 worktrees.json.backup
- [x] 4.3 实现修复逻辑 - 更新 null branch 字段
- [x] 4.4 实现修复验证 - 确认字段已正确更新
- [x] 4.5 实现回滚机制 - 验证失败时从备份恢复
- [x] 4.6 测试数据质量修复 - 创建 null branch worktree，运行修复，验证结果

## 5. 确定性核对 (Phase 2)

- [x] 5.1 实现分支名匹配逻辑 - 提取 YYYY-MM-DD-slug 模式
- [x] 5.2 实现 registry 查询 - 检查分支名对应的 task 是否已注册
- [x] 5.3 实现 OpenSpec changes 扫描 - 列出所有 changes 目录
- [x] 5.4 实现 OpenSpec → registry 对比 - 检查未同步的 changes
- [x] 5.5 实现结果分类输出 - 按问题类型分组显示
- [x] 5.6 测试分支核对 - 创建未注册分支，运行核对，验证检测（已注册分支测试通过）
- [x] 5.7 测试 OpenSpec 核对 - 创建新 change，运行核对，验证检测（基础功能测试通过，输出格式需优化）

## 6. Skill 层智能审计 (Phase 3)

- [ ] 6.1 在 SKILL.md 中实现 Audit 模式入口
- [ ] 6.2 在 SKILL.md 中调用 Shell 获取 PR 数据 (vibe flow review --json)
- [ ] 6.3 在 SKILL.md 中分析 PR 语义（调用 Subagent 分析描述、评论、commits）
- [ ] 6.4 在 SKILL.md 中检查 docs/plans、docs/prds 散落任务
- [ ] 6.5 在 SKILL.md 中生成智能任务创建/更新建议
- [ ] 6.6 在 SKILL.md 中实现用户交互（逐个确认 vs 批量确认）
- [ ] 6.7 在 SKILL.md 中调用 Shell 执行操作 (vibe task add/update)
- [ ] 6.8 测试 Skill 层审计流程 - 验证完整语义分析和用户交互

## 7. 批量修复功能

- [ ] 7.1 实现任务批量注册 - 从核对结果批量创建 task 记录
- [ ] 7.2 实现交互式确认 - 逐个询问用户是否注册
- [ ] 7.3 实现批量确认 - 一次性确认所有修复
- [ ] 7.4 实现修复日志 - 记录所有修复操作到 .agent/logs/repair.log
- [ ] 7.5 实现撤销功能 - 从备份恢复最近的修复
- [ ] 7.6 测试批量注册 - 创建多个未注册任务，运行修复，验证结果

## 8. 与 vibe check 集成

- [ ] 8.1 在 `lib/check.sh` 中添加 `--audit-tasks` 参数支持
- [ ] 8.2 在 `vibe_check()` 中集成任务核对作为可选步骤
- [ ] 8.3 实现条件触发 - 只在用户指定时运行任务核对
- [ ] 8.4 更新 `vibe check` 帮助文档说明新参数
- [ ] 8.5 测试集成 - 运行 `vibe check --audit-tasks` 验证完整流程

## 9. 增强任务概览

- [ ] 9.1 扩展 `vibe task list` 添加健康度检查
- [ ] 9.2 实现健康度指标计算 - 检查注册状态、worktree 绑定、branch 有效性
- [ ] 9.3 实现 `--healthy` 过滤 - 只显示健康的任务
- [ ] 9.4 实现 `--issues` 过滤 - 只显示有问题的任务
- [ ] 9.5 实现 `--unregistered` 过滤 - 显示未注册的 worktrees/branches/changes
- [ ] 9.6 扩展 JSON 输出添加 `health` 字段
- [ ] 9.7 更新 `skills/vibe-task/SKILL.md` 显示健康度信息
- [ ] 9.8 测试增强概览 - 创建各种健康状态的任务，验证显示正确

## 10. 错误处理和优雅降级

- [ ] 10.1 实现 gh CLI 不可用时的降级逻辑
- [ ] 10.2 实现 OpenSpec 目录不存在时的处理
- [ ] 10.3 实现 registry.json 写入失败的错误处理
- [ ] 10.4 实现网络错误重试机制（PR 查询）
- [ ] 10.5 实现冲突检测 - 任务已存在、分支已绑定等
- [ ] 10.6 测试降级场景 - 模拟各种错误，验证优雅处理

## 11. 测试与验证

- [ ] 11.1 测试数据质量修复完整流程 - 创建 null branch → 修复 → 验证
- [ ] 11.2 测试分支核对 - 未注册分支 → 检测 → 注册 → 验证
- [ ] 11.3 测试 OpenSpec 核对 - 新 change → 检测 → 同步 → 验证
- [ ] 11.4 测试 PR 检测 - 已合并 PR → 检测未注册任务 → 验证置信度
- [ ] 11.5 测试批量修复 - 多个问题 → 批量修复 → 验证所有问题已解决
- [ ] 11.6 测试撤销功能 - 修复 → 撤销 → 验证恢复到修复前状态
- [ ] 11.7 测试与 vibe check 集成 - 运行完整流程验证协作正常

## 12. 文档更新

- [ ] 12.1 更新 `skills/vibe-task/SKILL.md` 完整文档，说明 audit 和 repair 能力
- [ ] 12.2 更新项目 README 或相关文档，说明任务健康度检查新能力
- [ ] 12.3 创建使用指南 - 如何使用 `vibe task audit` 和修复流程
- [ ] 12.4 更新 CHANGELOG.md 记录本次功能增强
- [ ] 12.5 添加内联代码注释说明复杂逻辑
