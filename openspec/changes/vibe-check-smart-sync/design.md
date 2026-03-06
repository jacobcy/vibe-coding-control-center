## Context

当前 `vibe check` 是静态检查工具，只能验证文件存在性和状态一致性。任务状态更新完全依赖人工判断，导致状态容易过期。

本设计引入智能状态同步能力，通过检测外部事件（PR merged）和 AI 分析来自动建议状态更新。核心原则是**渐进式智能**：从确定性操作到启发式判断，保持用户决策权。

**架构分层**：
- **Tier 1 (Shell)**: 确定性操作，数据收集，简单匹配
- **Tier 2 (Skill)**: 智能判断，Subagent 分析，交互编排
- **Tier 3 (Supervisor)**: 未涉及

**约束**：
- 不新增本地数据存储（遵循单一真源原则）
- 复用现有 `gh` 命令和缓存机制
- 保持向后兼容，不破坏现有行为

## Goals / Non-Goals

**Goals:**
1. 实现 PR merged 检测，自动建议任务状态更新
2. 支持多任务场景的智能分析（Subagent 分析 PR 内容）
3. 提供用户友好的确认流程，保留人工决策权
4. 扩展 `vibe flow` 命令族以支持 PR 数据查询

**Non-Goals:**
- Issue closed 检测（依赖 roadmap.json，不在本次范围）
- 深度代码质量分析（由 vibe-review-code 负责）
- 自动修正状态无需确认（必须用户确认）
- 本地 PR 缓存或同步机制（使用 gh 实时查询）

## Decisions

### D1: 多任务场景的判断策略

**Alternatives considered:**
- A: 标记 worktree 所有任务为完成 - 过于激进
- B: 只标记 main task - 可能遗漏子任务
- C: Subagent 分析 PR 内容，智能判断 - 灵活且准确

**Chosen:** C - 利用 AI 能力分析 PR 描述、评论、commits，匹配每个任务的目标

**实现方式：**
1. Shell 层收集 PR 数据（通过 `vibe flow review --json`）
2. Skill 层调用 Subagent (Explore agent)
3. Subagent 输出每个任务的完成度和置信度
4. 根据置信度分级处理

### D2: 置信度分级处理

**分级策略：**
- **高置信度 (> 0.8)**: AI 直接决定，记录建议
- **中置信度 (0.5-0.8)**: 询问用户选择：
  1. 深度分析代码变更
  2. 手动选择是否完成
  3. 跳过此任务
- **低置信度 (< 0.5)**: 跳过，不做建议

**置信度计算（Subagent 负责）：**
- PR 描述明确提到任务 → 高置信度
- 评论中有讨论但未明确 → 中置信度
- PR 内容未提及 → 低置信度

### D3: 数据查询策略

**Alternatives considered:**
- A: 本地同步 PR 记录到 `pr_cache.json`
- B: 实时查询 `gh` 命令

**Chosen:** B - 实时查询 gh

**理由：**
- 符合单一真源原则（GitHub API 是真源）
- 不需要维护同步逻辑
- gh 已有缓存机制
- API 限流充足（5000 requests/hour）
- 系统简单，避免过度工程化

**依赖检查：**
```bash
vibe_has gh || {
  log_warn "gh not found, skipping PR status check"
  return 0
}
```

### D4: 命令扩展设计

**vibe flow list 扩展：**
```bash
# 现有行为
vibe flow list                    # 列出所有 worktree

# 新增参数
vibe flow list --pr               # 最近 10 个有 PR 的分支
vibe flow list --keywords <text>  # 按关键字查找分支
```

**vibe flow review 增强：**
```bash
# 现有行为：显示 PR 状态
vibe flow review <branch>

# 新增 JSON 输出
vibe flow review <branch> --json  # 返回结构化 PR 数据
```

**实现原则：**
- 扩展现有命令，不新增顶层命令
- 保持向后兼容
- 使用 `--json` 标志支持程序化调用

### D5: 检查流程设计

**Phase 1: 静态检查（已实现）**
- Registry 与 OpenSpec 同步
- completed → archived 自动流转
- 僵尸分支检测
- 分支-任务一致性

**Phase 2: Git 状态检查（新增）**
```bash
# 获取所有 in_progress 任务
in_progress_tasks=$(jq '.tasks[] | select(.status=="in_progress")')

# 对每个任务：
for task in $in_progress_tasks; do
  branch=$(get_branch_from_task $task)

  # 查询 PR 状态
  pr_info=$(gh pr view $branch --json number,state,mergedAt 2>/dev/null)

  # 检查是否 merged
  if [[ $(echo $pr_info | jq -r '.state') == "MERGED" ]]; then
    # 传递给 Skill 层分析
    uncertain_tasks+=($task)
  fi
done
```

**Phase 3: 智能分析（Skill 层）**
1. 收集 PR 数据：描述、评论、commits
2. 调用 Subagent 分析每个任务
3. 返回带置信度的建议列表

**Phase 4: 用户确认并执行**
```
显示建议 → 用户确认 → 执行 vibe task update --status completed
```

## Risks / Trade-offs

### Risk 1: gh 不可用或未认证
**风险**: 用户未安装 gh 或未配置认证
**缓解**:
```bash
if ! vibe_has gh; then
  log_warn "gh not found, skipping PR check"
  return 0  # 优雅降级，继续其他检查
fi
```

### Risk 2: 网络问题或 API 限流
**风险**: 无法访问 GitHub API
**缓解**:
- 捕获错误，优雅降级
- API 限流 5000/hour 足够日常使用
- 显示友好的错误提示

### Risk 3: Subagent 分析不准确
**风险**: AI 判断错误导致错误的状态更新
**缓解**:
- 高置信度阈值设置保守（> 0.8）
- 中置信度必须用户确认
- 最终执行前用户确认所有建议

### Risk 4: 多任务场景误判
**风险**: worktree 包含多个任务，AI 无法准确判断
**缓解**:
- 提供详细的 PR 数据给 Subagent
- 用户可选择手动选择
- 不强制自动更新

### Trade-off: 查询延迟 vs 数据新鲜度
**权衡**: 实时查询 gh 有网络延迟，但保证数据最新
**选择**: 优先数据新鲜度，延迟在可接受范围内（~1秒）

## Migration Plan

**Phase 1: 扩展命令族**
1. 实现 `vibe flow list --pr`
2. 实现 `vibe flow list --keywords`
3. 增强 `vibe flow review --json`
4. 更新帮助文档

**Phase 2: 实现检查流程**
1. 在 `lib/check.sh` 新增 Phase 2 检查
2. 实现 PR merged 检测逻辑
3. 收集 uncertain tasks 传递给 Skill 层

**Phase 3: 升级 Skill 层**
1. 更新 `skills/vibe-check/SKILL.md`
2. 实现 Subagent 调用逻辑
3. 实现置信度分级处理
4. 实现用户交互流程

**Phase 4: 测试与验证**
1. 单任务场景测试
2. 多任务场景测试
3. 无 PR 场景测试
4. gh 不可用场景测试

**Rollback Strategy:**
- 所有修改兼容现有行为
- 新增功能通过参数控制，不影响现有命令
- 可通过跳过 Phase 2/3 检查来回退

## Open Questions

1. **Issue closed 检测是否需要独立实现？**
   - 依赖 roadmap.json 的实现
   - 可能放在后续的 roadmap-skill 中

2. **是否需要支持其他 Git 托管平台（如 GitLab）？**
   - 当前只支持 GitHub（通过 gh）
   - 可以在 Skill 层抽象接口

3. **深度代码分析的触发条件？**
   - 当前设计：用户选择
   - 是否需要自动触发（如置信度在某个范围）？

4. **是否需要记录检查历史？**
   - 方便追溯状态变更原因
   - 可能需要新增日志文件