# Roadmap 标签管理工作流程

**维护者**: Vibe Team
**最后更新**: 2026-03-30
**状态**: Active
**文档类型**: 工作流程

---

## 1. 目标

本文档定义**如何使用 GitHub issue labels 管理项目 roadmap** 的工作流程。

**本文档回答的问题**:
- 如何用标签做版本规划？（工作流程）
- 如何为新 issue 分配标签？（操作步骤）
- 如何管理版本生命周期？（版本开始/进行中/结束）
- 如何进行脏数据清洗和标准化？（第一层审查）
- 如何将 issue 转化为 vibe-task？（与 orchestra 的边界）

**本文档不回答的问题**:
- 有哪些标签？→ 见 [github-labels-reference.md](github-labels-reference.md)
- 标签的语义是什么？→ 见 [github-labels-standard.md](github-labels-standard.md)
- 具体命令怎么用？→ 见 [vibe3-user-guide.md](vibe3-user-guide.md)

---

## 2. 核心原则

### 2.1 GitHub-as-truth

所有 roadmap 管理通过 GitHub issue labels 触发，不在本地实现数据存储。

- 标签是 roadmap 管理的唯一真源
- 本地只保留最小索引，不存储 roadmap 状态
- 所有规划决策基于 GitHub 标签状态

### 2.2 Label 触发机制

- **优先级管理**: 通过 `priority/*` 标签控制
- **版本规划**: 通过 `roadmap/*` 标签控制
- **Milestone 分配**: 通过 GitHub Milestone 功能控制
- **执行状态**: 通过 `state/*` 标签控制（由执行层管理）

### 2.3 标签层级关系

```
roadmap/* (何时做)
    ↓
priority/* (多紧急)
    ↓
type/* (做什么)
    ↓
state/* (当前状态)
```

---

## 3. Roadmap 管理工作流程

### 3.1 新 Issue 处理流程

当有新 issue 创建时，按照以下流程处理：

#### Step 1: 评估类型

确定 issue 的类型，添加 `type/*` 标签：

```bash
# 功能开发
gh issue edit <issue_number> --add-label "type/feature"

# Bug 修复
gh issue edit <issue_number> --add-label "type/fix"

# 文档更新
gh issue edit <issue_number> --add-label "type/docs"
```

**决策标准**:
- 新增功能 → `type/feature`
- 修复问题 → `type/fix`
- 代码重构 → `type/refactor`
- 文档更新 → `type/docs`
- 测试相关 → `type/test`
- 构建/配置 → `type/chore`

#### Step 2: 评估优先级

根据紧急程度添加 `priority/*` 标签：

```bash
# 高优先级 - 核心功能、关键 bug 修复
gh issue edit <issue_number> --add-label "priority/high"

# 中优先级 - 重要但非紧急的功能
gh issue edit <issue_number> --add-label "priority/medium"

# 低优先级 - 优化、改进等非关键任务
gh issue edit <issue_number> --add-label "priority/low"
```

**决策标准**:
- 影响核心功能、阻断性问题 → `priority/high`
- 重要功能改进、非阻断性 bug → `priority/medium`
- 优化、文档完善、代码清理 → `priority/low`

#### Step 3: 确定规划窗口

根据版本目标添加 `roadmap/*` 标签：

```bash
# 当前迭代必须完成
gh issue edit <issue_number> --add-label "roadmap/p0"

# 下个迭代优先完成
gh issue edit <issue_number> --add-label "roadmap/p1"

# 有容量时完成
gh issue edit <issue_number> --add-label "roadmap/p2"

# 需要讨论设计
gh issue edit <issue_number> --add-label "roadmap/rfc"
```

**决策标准**:
- 阻断性问题、当前版本核心功能 → `roadmap/p0`
- 下个版本规划的功能 → `roadmap/p1`
- 改进项、有容量时做 → `roadmap/p2`
- 待确认、需要讨论 → `roadmap/next`
- 长期规划 → `roadmap/future`
- 需要设计讨论 → `roadmap/rfc`

#### Step 4: 分配 Milestone

将 issue 分配到适当的 Milestone：

```bash
# 分配到具体版本
gh issue edit <issue_number> --milestone "Phase 1: 基础设施"
```

**决策标准**:
- 根据版本目标选择 Milestone
- 一个 issue 只能有一个 Milestone
- Milestone 与 `roadmap/*` 标签配合使用

#### Step 5: 转化为 vibe-task

将有效 issue 转化为 vibe-task：

```bash
# 添加 vibe-task 标签
gh issue edit <issue_number> --add-label "vibe-task"

# 绑定到 Flow（如果需要开始执行）
uv run python src/vibe3/cli.py flow bind <issue_number>
```

**注意**：转化为 vibe-task 后，编排职责将移交给 Orchestra，由 Orchestra 决定 flow 完成几个 task，还是一个 flow 只完成一个 task 的一部分。

### 3.2 版本管理流程

#### 版本开始

1. **创建 Milestone**
   ```bash
   # 在 GitHub 上创建新 Milestone
   # 或使用 GitHub CLI
   gh api repos/{owner}/{repo}/milestones -f title="Phase X: 版本名称" -f state="open"
   ```

2. **为相关 issues 添加标签**
   ```bash
   # 为核心功能添加 roadmap/p0
   gh issue edit 123 --add-label "roadmap/p0"
   
   # 为重要功能添加 roadmap/p1
   gh issue edit 124 --add-label "roadmap/p1"
   ```

3. **分配 Milestone**
   ```bash
   gh issue edit 123 --milestone "Phase X: 版本名称"
   gh issue edit 124 --milestone "Phase X: 版本名称"
   ```

#### 版本进行中

1. **定期检查标签状态**
   ```bash
   # 查看当前迭代必须完成的 issues
   gh issue list -l "roadmap/p0"
   
   # 查看高优先级 issues
   gh issue list -l "priority/high"
   ```

2. **根据进展调整优先级和规划**
   ```bash
   # 如果 issue 进展缓慢，降低优先级
   gh issue edit 123 --remove-label "roadmap/p0" --add-label "roadmap/p1"
   
   # 如果 issue 变成阻断性问题，提高优先级
   gh issue edit 124 --remove-label "roadmap/p1" --add-label "roadmap/p0"
   ```

3. **更新 issue 状态**
   ```bash
   # 开始执行
   gh issue edit 123 --add-label "state/in-progress"
   
   # 被阻塞
   gh issue edit 123 --add-label "state/blocked"
   ```

#### 版本结束

1. **更新 issues 状态**
   ```bash
   # 标记已完成的 issues
   gh issue edit 123 --add-label "state/done"
   
   # 关闭 issue
   gh issue close 123
   ```

2. **将未完成的 issues 移至下一版本**
   ```bash
   # 更新 roadmap 标签
   gh issue edit 124 --remove-label "roadmap/p0" --add-label "roadmap/p1"
   
   # 更新 milestone
   gh issue edit 124 --milestone "Phase X+1: 下一版本"
   ```

3. **关闭 Milestone**
   ```bash
   gh api repos/{owner}/{repo}/milestones/{milestone_number} -f state="closed"
   ```

---

## 4. 标签使用规范

### 4.1 Priority 标签使用

| 优先级 | 使用场景 | 示例 |
|--------|----------|------|
| `priority/high` | 核心功能、关键 bug 修复、阻断性问题 | 支付功能失效、系统崩溃 |
| `priority/medium` | 重要但非紧急的功能 | 性能优化、用户体验改进 |
| `priority/low` | 优化、改进等非关键任务 | 代码清理、文档完善 |

### 4.2 Roadmap 标签使用

| 标签 | 使用场景 | 决策标准 |
|------|----------|----------|
| `roadmap/p0` | 当前迭代必须完成 | 阻断性问题、核心功能 |
| `roadmap/p1` | 下个迭代优先完成 | 重要功能、已规划的功能 |
| `roadmap/p2` | 有容量时完成 | 一般功能、改进项 |
| `roadmap/next` | 下个迭代规划中 | 待确认的功能 |
| `roadmap/future` | 未来考虑 | 长期规划、想法阶段 |
| `roadmap/rfc` | RFC/设计阶段 | 需要讨论设计的功能 |

### 4.3 标签组合原则

- 一个 issue 应该同时有 `type/*` 和 `priority/*` 标签
- `roadmap/p0` 通常配合 `priority/high` 使用
- `roadmap/rfc` 可以没有 `priority/*` 标签
- 执行中的 issue 应该有 `vibe-task` 和 `state/*` 标签

---

## 5. 查询与筛选

### 5.1 按优先级查询

```bash
# 查看高优先级 issues
gh issue list -l "priority/high"

# 查看中优先级 issues
gh issue list -l "priority/medium"

# 查看低优先级 issues
gh issue list -l "priority/low"
```

### 5.2 按规划状态查询

```bash
# 查看当前迭代必须完成的 issues
gh issue list -l "roadmap/p0"

# 查看下个迭代优先完成的 issues
gh issue list -l "roadmap/p1"

# 查看有容量时完成的 issues
gh issue list -l "roadmap/p2"
```

### 5.3 组合查询

```bash
# 查看高优先级且当前迭代必须完成的 issues
gh issue list -l "priority/high" -l "roadmap/p0"

# 查看功能开发类型的 issues
gh issue list -l "type/feature"

# 查看特定 milestone 的 issues
gh issue list --milestone "Phase 1: 基础设施"
```

### 5.4 查看 Milestone 进度

```bash
# 查看特定 milestone 的 issues
gh issue list --milestone "Phase 1: 基础设施"

# 查看 task show 中的 milestone 信息
uv run python src/vibe3/cli.py task show <branch>
```

---

## 6. 决策流程

### 6.1 优先级决策

当无法确定优先级时，考虑以下因素：

1. **业务影响**: 影响多少用户？影响核心功能吗？
2. **技术风险**: 有技术债务风险吗？会影响系统稳定性吗？
3. **依赖关系**: 是否阻塞其他工作？
4. **时间敏感性**: 有截止日期吗？

### 6.2 规划窗口决策

当无法确定规划窗口时，考虑以下因素：

1. **版本目标**: 是否符合当前版本目标？
2. **资源容量**: 团队有容量完成吗？
3. **依赖关系**: 依赖其他 issue 吗？被其他 issue 依赖吗？
4. **风险**: 风险高吗？需要更多时间评估吗？

### 6.3 需要人类讨论的情况

以下情况需要人类讨论确定：

- 优先级冲突（多个 `priority/high` issue）
- 版本目标不明确
- 技术方案需要评估
- 资源分配需要协调

---

## 7. 自动化规则

### 7.1 标签自动添加

当 issue 被绑定到 flow 时，自动添加 `vibe-task` 标签：

```bash
uv run python src/vibe3/cli.py flow bind <issue_number>
# 自动添加 vibe-task 标签
```

### 7.2 状态自动更新

当 issue 状态变化时，自动更新 `state/*` 标签：

- 开始执行 → `state/in-progress`
- 被阻塞 → `state/blocked`
- 完成 → `state/done`

### 7.3 Milestone 自动同步

当 issue 被分配到 Milestone 时，自动同步到 GitHub Project。

---

## 8. 最佳实践

### 8.1 定期审查

- **每周**: 审查 `roadmap/p0` issues，确保按计划推进
- **每月**: 审查 `roadmap/p1` 和 `roadmap/p2` issues，调整优先级
- **每季度**: 审查 `roadmap/future` issues，评估是否纳入规划

### 8.2 标签维护

- 保持标签的准确性和时效性
- 及时更新已完成 issues 的状态
- 定期清理过时标签

### 8.3 沟通协作

- 在 issue 中说明标签变更的原因
- 使用 handoff 记录标签变更的上下文
- 与团队成员共享 roadmap 状态

---

## 9. 故障处理

### 9.1 标签冲突

当发现标签冲突时：

1. 检查 issue 的实际状态
2. 移除错误的标签
3. 添加正确的标签
4. 记录变更原因

### 9.2 状态不一致

当发现本地状态与 GitHub 标签不一致时：

1. 以 GitHub 标签为准
2. 更新本地状态
3. 检查同步机制

### 9.3 查询失败

当查询命令失败时：

1. 检查网络连接
2. 验证 GitHub CLI 配置
3. 使用备选查询方式

---

## 10. 参考文档

- [github-labels-reference.md](github-labels-reference.md) - 标签速查手册（有哪些标签）
- [github-labels-standard.md](github-labels-standard.md) - 标签语义和真源标准
- [vibe3-state-sync-standard.md](vibe3-state-sync-standard.md) - 状态同步标准
- [issue-standard.md](issue-standard.md) - Issue 标准
- [vibe3-user-guide.md](vibe3-user-guide.md) - 用户操作手册
