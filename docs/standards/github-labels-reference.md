# GitHub 标签速查手册

**维护者**: Vibe Team
**最后更新**: 2026-06-03
**状态**: Active
**文档类型**: 参考手册

---

## 1. 目标

本文档是 GitHub 标签的**快速参考手册**，提供所有可用标签的清单和使用速查。

**注意**:
- 本文档只回答"**有哪些标签**"和"**基本用法**"
- 标签的语义定义、真源规则、使用场景见 [github-labels-standard.md](github-labels-standard.md)
- 如何使用标签管理 roadmap 见 [roadmap-label-management.md](roadmap-label-management.md)

---

## 2. 标签清单

### 2.1 分类标签

#### 类型标签 (type/*)

| 标签名称 | 描述 | 示例命令 |
|---------|------|----------|
| `type/feature` | 新功能 | `gh issue edit 123 --add-label "type/feature"` |
| `type/fix` | Bug 修复 | `gh issue edit 123 --add-label "type/fix"` |
| `type/refactor` | 重构 | `gh issue edit 123 --add-label "type/refactor"` |
| `type/docs` | 文档 | `gh issue edit 123 --add-label "type/docs"` |
| `type/test` | 测试 | `gh issue edit 123 --add-label "type/test"` |
| `type/chore` | 杂项 | `gh issue edit 123 --add-label "type/chore"` |
| `type/task` | 综合型任务 | `gh issue edit 123 --add-label "type/task"` |
| `type/perf` | 性能优化 | `gh issue edit 123 --add-label "type/perf"` |

#### 优先级标签 (priority/*)

| 标签名称 | 描述 | 示例命令 |
|---------|------|----------|
| `priority/critical` | 紧急阻断性问题 | `gh issue edit 123 --add-label "priority/critical"` |
| `priority/high` | 高优先级 | `gh issue edit 123 --add-label "priority/high"` |
| `priority/medium` | 中优先级 | `gh issue edit 123 --add-label "priority/medium"` |
| `priority/low` | 低优先级 | `gh issue edit 123 --add-label "priority/low"` |
| `priority/0` ~ `priority/9` | 数值优先级（推荐） | `gh issue edit 123 --add-label "priority/7"` |

**说明**：
- 数值优先级（`priority/0-9`）为推荐格式，更精确
- Legacy 文本优先级（`priority/critical/high/medium/low`）保持兼容
- 数值越大优先级越高

#### 范围标签 (scope/*)

| 标签名称 | 描述 | 示例命令 |
|---------|------|----------|
| `scope/python` | Python 改动 | `gh issue edit 123 --add-label "scope/python"` |
| `scope/shell` | Shell 改动 | `gh issue edit 123 --add-label "scope/shell"` |
| `scope/documentation` | 文档改动 | `gh issue edit 123 --add-label "scope/documentation"` |
| `scope/infrastructure` | 基础设施 | `gh issue edit 123 --add-label "scope/infrastructure"` |
| `scope/skill` | Skill 改动 | `gh issue edit 123 --add-label "scope/skill"` |
| `scope/supervisor` | agent/workflow/rules 改动 | `gh issue edit 123 --add-label "scope/supervisor"` |

#### 组件标签 (component/*)

| 标签名称 | 描述 | 示例命令 |
|---------|------|----------|
| `component/cli` | CLI 入口 | `gh issue edit 123 --add-label "component/cli"` |
| `component/flow` | Flow 相关 | `gh issue edit 123 --add-label "component/flow"` |
| `component/task` | Task 相关 | `gh issue edit 123 --add-label "component/task"` |
| `component/pr` | PR 相关 | `gh issue edit 123 --add-label "component/pr"` |
| `component/client` | Client 层 | `gh issue edit 123 --add-label "component/client"` |
| `component/config` | 配置层 | `gh issue edit 123 --add-label "component/config"` |
| `component/orchestra` | Orchestra 模块 | `gh issue edit 123 --add-label "component/orchestra"` |

### 2.2 特殊用途标签

| 标签名称 | 描述 | 使用场景 |
|---------|------|----------|
| `orchestra-scanned` | intake 层已审查，不纳入 | roadmap-intake 跳过 issue 时打标签，下次扫描自动跳过 |
| `orchestra-governed` | assignee-pool 层已决策 | assignee-pool 决策完成后打标签，下次扫描自动跳过 |
| `roadmap-reviewed` | 已通过 roadmap decider 审查 | roadmap 写完 `[roadmap decision]` 后打标签，Step 0 自动跳过 |
| `orchestra` | [Legacy] Orchestra 治理标记 | 已拆分为 `orchestra-scanned` 和 `orchestra-governed`，保留兼容 |
| `supervisor` | Supervisor-governed orchestration issue | 标记需要 Supervisor 治理的编排问题 |
| `tech-debt` | Technical debt tracking | 追踪技术债务和需要优化的代码 |
| `improvement` | Non-urgent improvements | 非紧急的改进和增强项 |

**说明**：
- `orchestra` 标签已拆分为 `orchestra-scanned`（intake 层跳过标记）和 `orchestra-governed`（pool 层决策标记）
- `roadmap-reviewed` 与 `[roadmap decision]` 评论配合，实现治理闭环
- 三层标签各自闭环：intake 看 scanned，pool 看 governed，roadmap 看 reviewed
- 可以与 `type/*`、`scope/*` 等标签组合使用

**迁移说明**：
- 现有 `orchestra` 标签逐步替换
- 迁移期间，`orchestra` 作为兼容标签保留

### 2.3 路线图标签 (roadmap/*)

| 标签名称 | 描述 | 示例命令 |
|---------|------|----------|
| `roadmap/p0` | 当前迭代必须完成 | `gh issue edit 123 --add-label "roadmap/p0"` |
| `roadmap/p1` | 下个迭代优先完成 | `gh issue edit 123 --add-label "roadmap/p1"` |
| `roadmap/p2` | 有容量时完成 | `gh issue edit 123 --add-label "roadmap/p2"` |
| `roadmap/next` | 下个迭代规划中 | `gh issue edit 123 --add-label "roadmap/next"` |
| `roadmap/future` | 未来考虑 | `gh issue edit 123 --add-label "roadmap/future"` |
| `roadmap/rfc` | RFC/设计阶段（agent 无法判断目标/拆分形态） | `gh issue edit 123 --add-label "roadmap/rfc"` |
| `roadmap/epic` | Epic 主 issue（有 Sub-issues，主 issue 作为治理容器） | `gh issue edit 123 --add-label "roadmap/epic"` |

**说明**：
- `roadmap-reviewed` 是审查层闭环标签，虽不以 `roadmap/` 为前缀，但与 roadmap 审查流程紧密配合。定义见 §2.2 特殊用途标签
- `roadmap-reviewed` 标签在 `[roadmap decision]` 评论后自动添加
- 用于实现治理闭环，避免 Step 0 重复扫描已决策的 issues

### 2.4 关系镜像标签

| 标签名称 | 描述 | 示例命令 |
|---------|------|----------|
| `vibe-task` | 执行项镜像标签 | 自动镜像，不建议手动维护 |

**说明 (Truth Source)**：
- `vibe-task` 是 `vibe3 flow bind` 成功的**自动镜像（副作用）**。
- **非真源**：它不是 Governance 或执行引擎判定的真源。真源位于本地 SQLite `flow_issue_links`。
- **可视化用途**：仅用于 GitHub 视角（如 Projects 视图）过滤和识别已绑定的任务。

### 2.5 编排状态标签 (state/*)

| 标签名称 | 含义 | 示例命令 |
|---------|------|----------|
| `state/ready` | 可认领 | 通常由自动化镜像，不建议手工维护 |
| `state/claimed` | 已认领，待进入执行 | 通常由自动化镜像，不建议手工维护 |
| `state/in-progress` | 执行中 | 通常由自动化镜像，不建议手工维护 |
| `state/blocked` | 阻塞中 | 通常由自动化镜像，不建议手工维护 |
| `state/failed` | 执行失败（serve 层警告，非 flow 状态） | 通常由自动化镜像，不建议手工维护 |
| `state/handoff` | 待交接 | 通常由自动化镜像，不建议手工维护 |
| `state/review` | 待 review | 通常由自动化镜像，不建议手工维护 |
| `state/merge-ready` | 已满足合并条件 | 通常由自动化镜像，不建议手工维护 |
| `state/done` | 已完成 | 通常由自动化镜像，不建议手工维护 |

**说明 (State Mirroring)**：
- `state/*` 标签是执行状态的**可选镜像**。
- **真源分离**：`assignee issue` 的真实执行状态优先以本地 SQLite `flow_state` 表与 orchestration scene 为准。
- **自动同步**：由 `vibe3` 在状态迁移时自动更新 GitHub 标签。

### 2.6 触发器标签 (trigger/*)

| 标签名称 | 描述 | 使用场景 |
|---------|------|----------|
| `trigger/ai-review` | 触发 AI PR 审查流程 | 开发者完成 PR 后手动添加，触发自动审查 |

**说明**：
- Trigger 标签是**一次性触发器**，由开发者手动添加
- Workflow 完成后会自动移除 trigger 标签
- 用于触发自动化流程，不作为长期状态标记

**使用流程**：
1. 开发者完成 PR，添加 `trigger/ai-review` 标签
2. 触发 `ai-pr-review.yml` workflow
3. Workflow 发送 AI 审查请求（`@codex review` 或 `@copilot review`）
4. Workflow 自动移除 `trigger/ai-review` 标签
5. 后续再次添加标签时，workflow 会检查 PR comments 防止重复请求

**防重复机制**：
- Workflow 检查 PR comments 是否已有 `@codex review`
- 已发送过审查请求的 PR 不会重复触发

---

## 3. 常用查询速查

### 3.1 按标签查询

```bash
# 查看高优先级 issues
gh issue list -l "priority/high"

# 查看当前迭代必须完成的 issues
gh issue list -l "roadmap/p0"

# 查看执行中的 issues
gh issue list -l "state/in-progress"

# 组合查询：高优先级且当前迭代必须完成
gh issue list -l "priority/high" -l "roadmap/p0"

# 查看功能开发类型的 issues
gh issue list -l "type/feature"
```

### 3.2 管理标签

```bash
# 添加单个标签
gh issue edit 123 --add-label "priority/high"

# 添加多个标签
gh issue edit 123 --add-label "priority/high" --add-label "roadmap/p0"

# 移除标签
gh issue edit 123 --remove-label "priority/low"

# 查看 issue 的标签
gh issue view 123
```

### 3.3 Milestone 管理

```bash
# 分配 milestone
gh issue edit 123 --milestone "Phase 1: 基础设施"

# 查看特定 milestone 的 issues
gh issue list --milestone "Phase 1: 基础设施"
```

### 3.4 标签同步

**自动同步标准标签**：

```bash
# 同步所有标准标签到 repo（幂等，不删除现有标签）
./scripts/sync-labels.sh
```

**脚本特性**：
- ✅ **幂等性**：可以重复运行，不会重复创建
- ✅ **非破坏性**：只创建/更新标签，从不删除
- ✅ **自动更新**：更新已存在标签的描述和颜色
- ✅ **保留默认**：保留 GitHub 默认标签（bug、documentation、enhancement、question）

---

## 4. 标签组合速查表

| 场景 | 推荐标签组合 |
|------|-------------|
| 高优先级功能开发 | `type/feature` + `priority/9` + `roadmap/p0` |
| 中优先级 bug 修复 | `type/fix` + `priority/5` + `roadmap/p1` |
| 低优先级文档更新 | `type/docs` + `priority/3` + `roadmap/p2` |
| agent 无法判断目标/拆分形态 | `type/feature` + `roadmap/rfc` |
| Epic 主 issue | `roadmap/epic` + `type/feature`（主 issue 保持治理容器，执行进入 sub-issue） |
| 性能优化 | `type/perf` + `priority/7` + `roadmap/p0` |
| 技术债务清理 | `tech-debt` + `priority/5` + `roadmap/p1` |
| 编排系统改进 | `component/orchestra` + `type/feature` + `roadmap/p1` |
| Supervisor 治理问题 | `supervisor` + `priority/7` + `roadmap/p0` |
| 非紧急改进 | `improvement` + `priority/3` + `roadmap/p2` |
| 完成 PR 需要AI审查 | `trigger/ai-review`（手动添加，workflow自动移除） |
| 正在执行的任务 | `vibe-task`（flow bind 自动镜像）+ `state/in-progress`（可选） |
| 被阻塞的任务 | `vibe-task`（flow bind 自动镜像）+ `state/blocked`（可选） |
| 待 review 的任务 | `vibe-task`（flow bind 自动镜像）+ `state/review`（可选） |
| 已完成的任务 | `vibe-task`（flow bind 自动镜像）+ `state/done`（可选） |

---

## 5. 参考文档

- [github-labels-standard.md](github-labels-standard.md) - 标签语义和真源标准
- [roadmap-label-management.md](roadmap-label-management.md) - 如何使用标签管理 roadmap
- [v3/command-standard.md](v3/command-standard.md) - 命令与状态同步标准
- [issue-standard.md](issue-standard.md) - Issue 标准
