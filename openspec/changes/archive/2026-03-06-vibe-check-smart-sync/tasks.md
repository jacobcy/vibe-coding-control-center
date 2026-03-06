## 1. 命令族扩展

- [x] 1.1 扩展 `lib/flow.sh` 中的 `_flow_list` 函数，新增 `--pr` 参数支持
- [x] 1.2 扩展 `lib/flow.sh` 中的 `_flow_list` 函数，新增 `--keywords` 参数支持
- [x] 1.3 增强 `lib/flow.sh` 中的 `_flow_review` 函数，新增 `--json` 输出支持
- [x] 1.4 更新 `lib/flow_help.sh` 帮助文档，说明新增参数

## 2. Shell 层检查流程

- [x] 2.1 在 `lib/check.sh` 中新增 `_check_gh_available()` 函数，检查 gh 可用性
- [x] 2.2 在 `lib/check.sh` 中新增 `_get_merged_prs()` 函数，查询已合并 PR 列表
- [x] 2.3 在 `lib/check.sh` 中新增 `_get_in_progress_tasks()` 函数，获取进行中的任务
- [x] 2.4 在 `lib/check.sh` 中新增 `_check_pr_merged_status()` 函数，检查任务关联 PR 是否已合并
- [x] 2.5 在 `lib/check.sh` 中集成 Phase 2 检查流程到主 `vibe_check()` 函数

## 3. Skill 层智能分析

- [x] 3.1 更新 `skills/vibe-check/SKILL.md` 的 Step 0，调用 Shell 层获取 PR 数据
- [x] 3.2 在 `skills/vibe-check/SKILL.md` 中新增 Subagent 调用逻辑（Step 2）
- [x] 3.3 在 `skills/vibe-check/SKILL.md` 中实现置信度分级处理（Step 3）
- [x] 3.4 在 `skills/vibe-check/SKILL.md` 中实现用户交互流程（Step 4）
- [x] 3.5 在 `skills/vibe-check/SKILL.md` 中实现深度代码分析选项（可选）

## 4. 测试与验证

- [x] 4.1 测试单任务场景：创建测试任务、提交 PR、合并 PR、运行 `vibe check` 验证建议
  - ✅ 已验证：使用现有任务 (2026-03-05-bug-fix) 和已合并 PR (#38)
  - ✅ `vibe check` 成功检测到 merged PR 并建议运行 /vibe-check
  - 🐛 修复了 bug：jq 查询使用 `worktree_path` 改为 `worktree_name`
  - ⚠️  发现数据质量问题：worktrees.json 中许多 worktree 的 branch 字段为 null
- [ ] 4.2 测试多任务场景：创建包含多个任务的 worktree、合并 PR、验证智能分析
- [x] 4.3 测试无 PR 场景：创建任务但不创建 PR、运行 `vibe check` 验证跳过 PR 检查
  - ✅ 已验证：当前任务 2026-03-05-roadmap-skill 无 PR，vibe check 正确跳过检测
- [x] 4.4 测试 gh 不可用场景：卸载或禁用 gh、运行 `vibe check` 验证优雅降级
  - ✅ 已验证：模拟 gh 不可用 (PATH=/usr/bin)，正确显示警告并跳过 PR 检查
- [ ] 4.5 测试用户确认流程：验证高/中/低置信度的处理和用户交互

## 5. 文档更新

- [x] 5.1 更新 `README.md` 或相关文档，说明 `vibe check` 的新能力
- [x] 5.2 更新 `CHANGELOG.md`，记录本次功能增强
