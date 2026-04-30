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
- 如何为 issue 绑定执行入口？（flow bind 的语义）

**本文档不回答的问题**:
- 有哪些标签？→ 见 [github-labels-reference.md](github-labels-reference.md)
- 标签的语义是什么？→ 见 [github-labels-standard.md](github-labels-standard.md)
- 具体命令怎么用？→ 见 [v3/command-standard.md](v3/command-standard.md)

---

## 2. 核心原则

### 2.1 GitHub-as-truth

所有 roadmap 管理通过 GitHub issue labels 触发，不在本地实现数据存储。

- 标签是 roadmap 管理的唯一真源
- 本地只保留最小索引，不存储 roadmap 状态
- 所有规划决策基于 GitHub 标签状态

### 2.2 Label 触发机制

- **优先级管理**: 通过 `priority/*` 标签控制
  - **Numeric priority (推荐)**: `priority/0` ~ `priority/9`（数值越大优先级越高）
  - **Legacy priority (兼容)**: `priority/critical`, `priority/high`, `priority/medium`, `priority/low`
  - 默认优先级为 `priority/0`（无标签时）
- **版本规划**: 通过 `roadmap/*` 标签控制
- **Milestone 分配**: 通过 GitHub Milestone 功能控制
- **执行状态**: 通过 `state/*` 标签控制（由执行层管理）

### 2.3 队列排序规则

Orchestra 的 ready queue 使用三级排序（从高到低）：

1. **Milestone** (大桶): 版本号小的优先（v0.1 > v0.3）
2. **Roadmap** (版本内排序): roadmap/p0 > roadmap/p1 > roadmap/p2
3. **Priority** (细粒度排序): priority/9 > priority/8 > ... > priority/0

**示例**：
- v0.1 的 roadmap/p0 + priority/9 会优先于 v0.1 的 roadmap/p1 + priority/5
- v0.1 的所有 issues 会优先于 v0.3 的所有 issues

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

**推荐使用 Numeric Priority (0-9)**:

```bash
# 最高优先级 - 紧急阻断性问题
gh issue edit <issue_number> --add-label "priority/9"

# 高优先级 - 核心功能、关键 bug 修复
gh issue edit <issue_number> --add-label "priority/7"

# 中等优先级 - 重要但非紧急的功能
gh issue edit <issue_number> --add-label "priority/5"

# 低优先级 - 优化、改进等非关键任务
gh issue edit <issue_number> --add-label "priority/3"

# 最低优先级 - 默认值
# 不添加标签即默认为 priority/0
```

**Legacy Priority (兼容支持)**:

```bash
# 紧急阻断性问题 - 等同于 priority/9
gh issue edit <issue_number> --add-label "priority/critical"

# 高优先级 - 核心功能、关键 bug 修复，等同于 priority/7
gh issue edit <issue_number> --add-label "priority/high"

# 中优先级 - 重要但非紧急的功能，等同于 priority/5
gh issue edit <issue_number> --add-label "priority/medium"

# 低优先级 - 优化、改进等非关键任务，等同于 priority/3
gh issue edit <issue_number> --add-label "priority/low"
```

**优先级映射表**:

| Legacy 标签 | 映射到 Numeric | 说明 |
|-------------|---------------|------|
| `priority/critical` | `priority/9` | 紧急阻断性问题、系统崩溃 |
| `priority/high` | `priority/7` | 核心功能、关键 bug 修复 |
| `priority/medium` | `priority/5` | 重要但非紧急的功能 |
| `priority/low` | `priority/3` | 优化、改进等非关键任务 |

**决策标准**:
- 9: 紧急阻断性问题、系统崩溃、核心功能失效
- 7-8: 核心功能、关键 bug 修复、影响大量用户的问题
- 5-6: 重要功能改进、非阻断性 bug
- 3-4: 优化、文档完善、代码清理
- 1-2: 低优先级改进、nice-to-have
- 0: 默认优先级（未设置标签时）

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

#### Step 5: 绑定执行入口

将 issue 绑定到 flow，正式进入 **Manager 主开发链**：

```bash
# 绑定到 Flow（开始执行）
uv run python src/vibe3/cli.py flow bind <issue_number>
# 自动镜像 vibe-task 标签（副作用，不作为真源）
```

**注意**：
- `flow bind` 是 issue 进入执行现场的正式绑定入口。
- `vibe-task` 与 `state/*` 标签是由绑定和执行状态自动镜像的副作用，**不建议作为手工主入口**。
- 一旦绑定，issue 进入 manager 主执行闭环，由 Manager/Plan/Run/Review 推进。

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
   # 开始执行：优先通过 flow bind / manager 主链推进
   uv run python src/vibe3/cli.py flow bind 123

    # 如需查看运行状态，优先检查 flow 状态
    uv run python src/vibe3/cli.py flow show task/issue-123
   ```

#### 版本结束

1. **更新 issues 状态**
   ```bash
   # PR 合并或确认终态后关闭 issue
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

**Numeric Priority (推荐)**:

| 优先级 | 使用场景 | 示例 |
|--------|----------|------|
| `priority/9` | 紧急阻断性问题、系统崩溃、核心功能失效 | 支付功能失效、数据库损坏 |
| `priority/8` | 极高优先级、重要功能阻断 | 关键 API 失效 |
| `priority/7` | 核心功能、关键 bug 修复、影响大量用户 | 登录失败、性能严重下降 |
| `priority/6` | 重要功能改进、影响部分用户 | 功能缺失、用户体验问题 |
| `priority/5` | 重要但非紧急的功能 | 性能优化、用户体验改进 |
| `priority/4` | 一般功能改进 | 功能增强、小改进 |
| `priority/3` | 一般功能、改进项 | 代码清理、小优化 |
| `priority/2` | 低优先级改进 | 次要改进 |
| `priority/1` | 最低优先级改进 | nice-to-have |
| `priority/0` | 默认优先级（无标签） | - |

**Legacy Priority (兼容支持)**:

| 优先级 | 使用场景 | 映射到 Numeric |
|--------|----------|---------------|
| `priority/critical` | 紧急阻断性问题 | `priority/9` |
| `priority/high` | 核心功能、关键 bug 修复 | `priority/7` |
| `priority/medium` | 重要但非紧急的功能 | `priority/5` |
| `priority/low` | 优化、改进等非关键任务 | `priority/3` |

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
- flow 绑定的 issue 会自动镜像 `vibe-task` 标签；执行状态以 flow 状态为准

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

# 查看当前 flow 中的 milestone 信息
uv run python src/vibe3/cli.py flow show --branch <branch>
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

当 assignee issue 的 flow 状态变化时，可自动镜像 `state/*` 标签：

- 开始执行 → `state/in-progress`
- 被阻塞 → `state/blocked`
- 完成 → `state/done`

### 7.3 Milestone 自动同步

当 issue 被分配到 Milestone 时，自动同步到 GitHub Project。

---

## 8. 特殊用途标签

### 8.1 治理与编排标签

除了常规的 roadmap、priority、type 标签，项目还使用以下特殊用途标签：

#### supervisor 标签

**用途**：标记需要 Supervisor 治理的编排问题

**使用场景**：
- Supervisor 层的架构决策
- 治理流程改进
- Policy/rules 变更
- 编排系统的治理级问题

**示例**：
```bash
# 标记 Supervisor 治理问题
gh issue edit 123 --add-label "supervisor" --add-label "priority/7" --add-label "roadmap/p0"
```

#### orchestra 标签

**用途**：标记 Orchestra 谘度和自动化相关 issue

**使用场景**：
- Orchestra 谘度逻辑改进
- 分诊和 dispatch 机制
- Queue ordering 优化
- 自动化流程改进

**示例**：
```bash
# 标记 Orchestra 谘度问题
gh issue edit 124 --add-label "orchestra" --add-label "type/feature" --add-label "roadmap/p1"
```

#### tech-debt 标签

**用途**：追踪技术债务和需要优化的代码

**使用场景**：
- 代码重构需求
- 架构优化
- 依赖更新
- 代码质量问题

**示例**：
```bash
# 标记技术债务
gh issue edit 125 --add-label "tech-debt" --add-label "priority/5" --add-label "roadmap/p1"
```

#### improvement 标签

**用途**：标记非紧急的改进和增强项

**使用场景**：
- 用户体验改进
- 边缘 case 处理
- 小功能增强
- 非阻断性改进

**示例**：
```bash
# 标记非紧急改进
gh issue edit 126 --add-label "improvement" --add-label "priority/3" --add-label "roadmap/p2"
```

### 8.2 触发器标签 (trigger/*)

**用途**：触发自动化工作流

**与常规标签的区别**：
- 常规标签：长期状态标记，手动添加/移除
- 触发器标签：一次性触发器，workflow 自动移除

#### trigger/ai-review 标签

**用途**：触发 AI PR 审查流程

**使用场景**：
- 开发者完成 PR 后手动添加
- 触发 Codex/Copilot 自动审查
- Workflow 完成后自动移除

**工作流程**：
1. 开发者添加 `trigger/ai-review` 标签
2. 触发 `.github/workflows/ai-pr-review.yml`
3. Workflow 发送审查请求（`@codex review` 或 `@copilot review`）
4. Workflow 移除 `trigger/ai-review`
5. Workflow 检查 PR comments 防止重复请求（无需额外标签）

**示例**：
```bash
# 完成 PR 后触发 AI 审查
gh pr edit <pr_number> --add-label "trigger/ai-review"
# Workflow 会自动移除此标签
```

**防重复机制**：
- Workflow 直接检查 PR comments 是否已有 `@codex review`
- 不需要额外的辅助标签
- 利用 GitHub 现有数据（comments）而非创建新标签

### 8.3 与常规标签的关系

**组合使用原则**：
- 特殊用途标签可以与 `type/*`、`scope/*`、`roadmap/*`、`priority/*` 组合
- `supervisor` 和 `orchestra` 通常配合 `roadmap/p0` 或 `roadmap/p1`
- `tech-debt` 和 `improvement` 通常配合 `roadmap/p1` 或 `roadmap/p2`

**标签层级**：
```
特殊用途标签 (治理维度)
    ↓
roadmap/* (何时做)
    ↓
priority/* (多紧急)
    ↓
type/* (做什么)
    ↓
scope/* (影响范围)
```

---

## 9. 最佳实践

### 9.1 定期审查

- **每周**: 审查 `roadmap/p0` issues，确保按计划推进
- **每月**: 审查 `roadmap/p1` 和 `roadmap/p2` issues，调整优先级
- **每季度**: 审查 `roadmap/future` issues，评估是否纳入规划
- **定期**: 审查 `tech-debt` 和 `improvement` issues，评估是否需要提升优先级

### 9.2 标签维护

- 保持标签的准确性和时效性
- 及时更新已完成 issues 的状态
- 定期清理过时标签
- 检查特殊用途标签（`supervisor`、`orchestra`、`tech-debt`、`improvement`）是否准确

### 9.3 沟通协作

- 在 issue 中说明标签变更的原因
- 使用 handoff 记录标签变更的上下文
- 与团队成员共享 roadmap 状态
- 特殊用途标签的变更需要团队讨论

---

## 10. 故障处理

### 10.1 标签冲突

当发现标签冲突时：

1. 检查 issue 的实际状态
2. 移除错误的标签
3. 添加正确的标签
4. 记录变更原因

### 10.2 状态不一致

当发现本地状态与 GitHub 标签不一致时：

1. 以 GitHub 标签为准
2. 更新本地状态
3. 检查同步机制

### 10.3 查询失败

当查询命令失败时：

1. 检查网络连接
2. 验证 GitHub CLI 配置
3. 使用备选查询方式

### 10.4 特殊用途标签误用

当发现特殊用途标签误用时：

1. 确认 issue 的实际性质
2. 移除不合适的特殊标签（`supervisor`、`orchestra` 等）
3. 添加合适的 `type/*` 和 `scope/*` 标签
4. 在 issue comment 中说明变更原因

---

## 11. 参考文档

- [github-labels-reference.md](github-labels-reference.md) - 标签速查手册（有哪些标签）
- [github-labels-standard.md](github-labels-standard.md) - 标签语义和真源标准
- [v3/command-standard.md](v3/command-standard.md) - 共享状态命令与状态同步标准
- [issue-standard.md](issue-standard.md) - Issue 标准
- [../../AGENTS.md](../../AGENTS.md) - 项目导览与操作手册
