# GitHub Issue 和 PR 标签规范

> **文档定位**：定义 Vibe Center 项目的 GitHub Issue 和 PR 标签体系
> **适用范围**：所有 GitHub Issue 和 Pull Request
> **维护者**：Vibe Team

---

## 标签体系设计原则

1. **语义清晰**：标签名称和颜色应一目了然
2. **分类明确**：不同类型的标签使用不同前缀
3. **自动应用**：尽可能通过工具自动应用标签
4. **最小集合**：避免标签过多导致混乱

---

## 标签分类

### 1. 类型标签 (Type Labels)

**用途**：标识 Issue 或 PR 的主要类型

| 标签名称 | 颜色 | 描述 | 示例场景 |
|---------|------|------|---------|
| `type/feature` | `#a2eeef` | 新功能开发 | 添加新的 CLI 命令 |
| `type/fix` | `#d73a4a` | Bug 修复 | 修复命令行参数解析错误 |
| `type/refactor` | `#fbca04` | 代码重构 | 重构 Logger 层统一规范 |
| `type/docs` | `#0075ca` | 文档更新 | 更新 README、添加 API 文档 |
| `type/test` | `#0e8a16` | 测试相关 | 添加单元测试、修复测试 |
| `type/chore` | `#fef2c0` | 杂项改动 | 更新依赖、修改构建脚本 |

**自动应用规则**：
- PR 标题包含 `feat:` → 自动添加 `type/feature`
- PR 标题包含 `fix:` → 自动添加 `type/fix`
- PR 标题包含 `refactor:` → 自动添加 `type/refactor`
- PR 标题包含 `docs:` → 自动添加 `type/docs`
- PR 标题包含 `test:` → 自动添加 `type/test`
- PR 标题包含 `chore:` → 自动添加 `type/chore`

---

### 2. 优先级标签 (Priority Labels)

**用途**：标识工作优先级

| 标签名称 | 颜色 | 描述 | 使用场景 |
|---------|------|------|---------|
| `priority/high` | `#b60205` | 高优先级 | 阻塞发布、严重 Bug |
| `priority/medium` | `#fbca04` | 中等优先级 | 常规功能开发 |
| `priority/low` | `#c5def5` | 低优先级 | 优化、改进项 |

**应用规则**：
- 由 Issue 创建者或 Reviewer 手动添加
- 默认为 `priority/medium`

---

### 3. 范围标签 (Scope Labels)

**用途**：标识改动影响的技术范围

| 标签名称 | 颜色 | 描述 | 涵盖范围 |
|---------|------|------|---------|
| `scope/shell` | `#1d76db` | Shell 层改动 | bin/vibe、lib/*.sh |
| `scope/skill` | `#5319e7` | Skill 层改动 | skills/**、.agent/workflows/** |
| `scope/supervisor` | `#d93f0b` | Supervisor 层改动 | .agent/rules/**、.agent/context/** |
| `scope/infrastructure` | `#0e8a16` | 基础设施改动 | CI/CD、hooks、scripts |
| `scope/documentation` | `#0075ca` | 文档改动 | docs/**、README、CLAUDE.md |
| `scope/python` | `#fbca04` | Python 代码改动 | src/vibe3/**/*.py |
| `scope/shell-script` | `#c5def5` | Shell 脚本改动 | lib/**/*.sh、scripts/**/*.sh |

**自动应用规则**：
- 文件路径匹配 `src/vibe3/**/*.py` → 自动添加 `scope/python`
- 文件路径匹配 `lib/**/*.sh` → 自动添加 `scope/shell-script`
- 文件路径匹配 `docs/**` → 自动添加 `scope/documentation`

---

### 4. 状态标签 (Status Labels)

**用途**：标识 Issue 或 PR 的当前状态

| 标签名称 | 颜色 | 描述 | 使用场景 |
|---------|------|------|---------|
| `status/blocked` | `#b60205` | 被阻塞 | 依赖未完成、等待外部输入 |
| `status/in-progress` | `#fbca04` | 进行中 | 正在开发中 |
| `status/ready-for-review` | `#0e8a16` | 待审核 | PR 已创建，等待 Review |
| `status/wip` | `#c5def5` | 工作进行中 | Work In Progress |

**应用规则**：
- Issue 被分配时 → 自动添加 `status/in-progress`
- PR 创建后 → 自动添加 `status/ready-for-review`
- 发现阻塞时 → 手动添加 `status/blocked`

---

### 5. 组件标签 (Component Labels)

**用途**：标识改动的具体组件或模块

| 标签名称 | 颜色 | 描述 | 涵盖模块 |
|---------|------|------|---------|
| `component/cli` | `#1d76db` | CLI 入口 | src/vibe3/cli.py |
| `component/flow` | `#5319e7` | Flow 管理 | src/vibe3/commands/flow.py、services/flow_service.py |
| `component/pr` | `#d93f0b` | PR 管理 | src/vibe3/commands/pr.py、services/pr_service.py |
| `component/task` | `#0e8a16` | Task 管理 | src/vibe3/commands/task.py、services/task_service.py |
| `component/logger` | `#fbca04` | Logger 模块 | src/vibe3/observability/** |
| `component/client` | `#c5def5` | Client 封装 | src/vibe3/clients/** |
| `component/config` | `#fef2c0` | 配置管理 | src/vibe3/config/** |

**自动应用规则**：
- 根据文件路径自动匹配并添加对应组件标签

---

### 6. 特殊标签 (Special Labels)

**用途**：特殊分类或标记

| 标签名称 | 颜色 | 描述 | 使用场景 |
|---------|------|------|---------|
| `vibe-task` | `#0E8A16` | Vibe 任务追踪 | 由 `/vibe-new` 创建的 Issue |
| `good first issue` | `#7057ff` | 适合新手 | 适合首次贡献者 |
| `help wanted` | `#008672` | 需要帮助 | 需要社区贡献 |
| `breaking-change` | `#b60205` | 破坏性变更 | 不兼容旧版本的改动 |

---

## 标签使用流程

### Issue 创建流程

1. **创建 Issue 时**：
   - 添加至少一个 **类型标签** (`type/*`)
   - 添加一个 **优先级标签** (`priority/*`)
   - 根据需要添加 **范围标签** (`scope/*`)
   - 根据需要添加 **组件标签** (`component/*`)

2. **Issue 被分配时**：
   - 添加 `status/in-progress`

3. **Issue 被阻塞时**：
   - 添加 `status/blocked`，并在评论中说明阻塞原因

### PR 创建流程

1. **创建 PR 时**（在 vibe-commit skill 中自动完成）：
   - 根据 PR 标题自动添加 **类型标签**
   - 根据文件改动自动添加 **范围标签** 和 **组件标签**
   - 添加 `status/ready-for-review`

2. **PR Review 中**：
   - 如需要修改，添加 `status/wip`
   - 修改完成后，添加 `status/ready-for-review`

3. **PR Merge 后**：
   - 移除所有状态标签
   - 保留类型、范围、组件标签用于分类

---

## 标签命名约定

### 前缀约定

- `type/` - 类型标签
- `priority/` - 优先级标签
- `scope/` - 范围标签
- `status/` - 状态标签
- `component/` - 组件标签

### 颜色约定

- **红色系** (`#d73a4a`, `#b60205`) - 高优先级、严重问题、破坏性变更
- **黄色系** (`#fbca04`, `#fef2c0`) - 中等优先级、进行中
- **绿色系** (`#0e8a16`, `#008672`) - 低优先级、已完成、正面状态
- **蓝色系** (`#0075ca`, `#1d76db`, `#c5def5`) - 功能、文档、Shell 层
- **紫色系** (`#5319e7`, `#7057ff`) - Skill 层、新手友好
- **橙色系** (`#d93f0b`) - Supervisor 层、紧急组件

---

## 标签自动化

### GitHub Actions 自动打标签

创建 `.github/workflows/label.yml`：

```yaml
name: Auto Label
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  label:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/labeler@v4
        with:
          repo-token: "${{ secrets.GITHUB_TOKEN }}"
```

### 配置文件 `.github/labeler.yml`

```yaml
# 类型标签
type/feature:
  - head_branch: ['^feat/', '^feature/']

type/fix:
  - head_branch: ['^fix/', '^bugfix/']

type/refactor:
  - head_branch: ['^refactor/']

type/docs:
  - head_branch: ['^docs/', '^documentation/']

type/test:
  - head_branch: ['^test/', '^testing/']

# 范围标签
scope/python:
  - 'src/vibe3/**/*.py'

scope/shell-script:
  - 'lib/**/*.sh'
  - 'scripts/**/*.sh'

scope/documentation:
  - 'docs/**'
  - '**/*.md'
  - 'LICENSE'

scope/infrastructure:
  - '.github/**'
  - '.pre-commit-config.yaml'
  - 'scripts/hooks/**'

# 组件标签
component/cli:
  - 'src/vibe3/cli.py'
  - 'src/vibe3/commands/*.py'

component/flow:
  - 'src/vibe3/commands/flow.py'
  - 'src/vibe3/services/flow_service.py'

component/pr:
  - 'src/vibe3/commands/pr.py'
  - 'src/vibe3/services/pr_service.py'

component/logger:
  - 'src/vibe3/observability/**'

component/client:
  - 'src/vibe3/clients/**'
```

---

## 最佳实践

### ✅ 推荐

1. **每个 Issue/PR 至少有一个类型标签**
2. **优先级标签帮助排定工作顺序**
3. **范围标签帮助快速定位改动影响**
4. **状态标签帮助跟踪工作进度**
5. **使用前缀分类，保持标签体系清晰**

### ❌ 避免

1. **不要创建过多标签** - 保持精简
2. **不要滥用高优先级标签** - 仅用于真正紧急的事项
3. **不要忽略标签** - 标签是项目管理的重要工具
4. **不要创建重复标签** - 如已有 `bug`，不要再创建 `type/bug`

---

## 标签维护

### 定期审查

- **每月**：审查是否有不再使用的标签
- **每季度**：评估标签体系是否需要调整
- **按需**：新增组件或模块时，考虑添加对应标签

### 标签废弃流程

1. 在标签描述中标记为 `[DEPRECATED]`
2. 通知团队成员不再使用该标签
3. 迁移现有 Issue/PR 到新标签
4. 确认无遗漏后删除标签

---

## 参考资料

- [GitHub Labels Best Practices](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels)
- [Conventional Commits](https://www.conventionalcommits.org/)
- `docs/standards/v2/git-workflow-standard.md`
- `skills/vibe-commit/SKILL.md`

---

**维护者**: Vibe Team
**最后更新**: 2026-03-17