# Phase 3 Implementation Spec (Draft)

**状态**: 建议补充到 `docs/v3/plans/03-pr-domain.md`
**作者**: Claude Sonnet 4.6
**时间**: 2026-03-16

---

## ⚠️ 实现规范（强制）

**必须遵守**:
- [docs/v3/implementation/02-architecture.md](../implementation/02-architecture.md)
- [docs/v3/implementation/03-coding-standards.md](../implementation/03-coding-standards.md)
- [.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md)

该文档定义了：
- ✅ 必须使用的技术栈（typer, rich, pydantic, loguru）
- ✅ 强制的目录结构
- ✅ 严格的分层职责
- ✅ 类型注解要求
- ✅ 测试要求
- ✅ 代码量限制

**违反规范将导致验收失败，不予合并。**

---

## 命令详细设计

### 1. `vibe3 pr draft`

**职责**: 创建 draft PR 并注入 metadata

**参数**:
```python
def draft(
    task_issue: int | None = None,      # Task issue number
    spec_ref: str | None = None,         # Plan 文档路径
    base_branch: str = "main",           # Base branch
    title: str | None = None,            # PR title (auto from commit if None)
) -> None:
    """Create draft PR with metadata injection."""
```

**Metadata Injection** (强制):
```
## Vibe Metadata
- Task: #123
- Flow: feature-xyz
- Spec: docs/plans/example.md
- Agent: Claude Sonnet 4.6
```

**实现层要求**:
- CLI (cli.py): 参数定义，调用 command
- Command (commands/pr.py): 参数验证，调用 service
- Service (services/pr_service.py): 业务逻辑
- Client (clients/github_client.py): GitHub API 调用

**错误处理**:
- 未在 git repo 中 → `GitError`
- GitHub API 失败 → `GitHubAPIError`
- 缺少必要参数 → `ValidationError`

---

### 2. `vibe3 pr show`

**职责**: 显示 PR 详情和绑定信息

**参数**:
```python
def show(
    pr_number: int | None = None,  # PR number (auto from current branch if None)
    json_output: bool = False,     # JSON 格式输出
) -> None:
    """Show PR details and metadata."""
```

**输出内容**:
- PR 基本信息 (title, state, author)
- 绑定的 Task issue
- 绑定的 Spec ref
- Flow 信息
- Review 状态

---

### 3. `vibe3 pr review`

**职责**: 本地审查 + 回贴 PR

**参数**:
```python
def review(
    local: bool = True,           # 本地审查模式
    post: bool = False,           # 是否回贴到 PR
    agent: str = "codex",         # 审查 agent
) -> None:
    """Run local review and optionally post to PR."""
```

**审查内容**:
- 代码质量检查
- 架构一致性检查
- 测试覆盖率检查
- 文档完整性检查

---

### 4. `vibe3 pr ready`

**职责**: Publish gate 检查 + version bump 策略

**参数**:
```python
def ready(
    bump: str | None = None,      # "patch" | "minor" | "major" (auto if None)
    changelog: bool = True,       # 是否生成 changelog
) -> None:
    """Mark PR ready for review with version bump strategy."""
```

**Publish Gate 检查**:
- [ ] 所有测试通过
- [ ] 代码覆盖率 >= 80%
- [ ] 文档已更新
- [ ] 无 `TODO` 或 `print()` 残留

**Version Bump 策略** (Group 驱动):
| Group | 默认 Bump | 逻辑 |
|-------|----------|------|
| feature | minor | 新功能 |
| bug | patch | 修复 bug |
| docs | none | 文档变更 |
| chore | none | 杂项 |

---

### 5. `vibe3 pr merge`

**职责**: Merge PR + 状态收口

**参数**:
```python
def merge(
    squash: bool = False,         # 是否 squash merge
    delete_branch: bool = True,   # 是否删除分支
) -> None:
    """Merge PR and update task status."""
```

**状态收口**:
- 更新 GitHub Project task 状态为 `completed`（通过 `gh project item edit`）
- 记录 handoff 信息到 SQLite（merge 证据、agent 署名、追责记录）
- 关闭 task issue (如果配置了自动关闭，通过 `gh issue close`)

---

## 文件结构要求

### 必须创建的文件

```
scripts/python/vibe3/
├── commands/
│   └── pr.py                  # PR 命令层 (< 100 行)
├── services/
│   └── pr_service.py          # PR 业务逻辑 (< 300 行)
├── clients/
│   └── github_client.py       # GitHub API 封装
├── models/
│   └── pr.py                  # PR 数据模型
└── ui/
    └── pr_display.py          # PR 展示逻辑
```

### 代码量限制

| 层级 | 文件最大行数 | 函数最大行数 |
|------|------------|------------|
| CLI (cli.py) | < 50 行 | < 20 行 |
| Commands | < 100 行 | < 50 行 |
| Services | < 300 行 | < 100 行 |
| Clients | 无限制 | < 150 行 |

---

## 测试要求

### 测试文件结构

```
tests3/pr/
├── test_pr_draft.py           # pr draft 测试
├── test_pr_show.py            # pr show 测试
├── test_pr_review.py          # pr review 测试
├── test_pr_ready.py           # pr ready 测试
└── test_pr_merge.py           # pr merge 测试
```

### 测试覆盖率

- **最低要求**: 80% 代码覆盖率
- **核心路径**: 100% 覆盖
- **错误场景**: 必须测试

### 测试内容

1. **契约测试** (Contract Tests)
   - 验证命令参数和输出格式
   - 验证 metadata 注入格式

2. **集成测试** (Integration Tests)
   - 使用 mock GitHub API
   - 验证完整流程

3. **错误处理测试**
   - 测试所有错误场景
   - 验证错误消息清晰

---

## GitHub Client 要求

### 必须实现的 Protocol

```python
from typing import Protocol

class GitHubClientProtocol(Protocol):
    def create_pr(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = True,
    ) -> str:
        """Create PR and return URL."""
        ...

    def get_pr(self, pr_number: int) -> dict:
        """Get PR details."""
        ...

    def update_pr(self, pr_number: int, **updates) -> None:
        """Update PR."""
        ...

    def create_review(self, pr_number: int, body: str) -> None:
        """Create PR review."""
        ...

    def merge_pr(self, pr_number: int, squash: bool = False) -> None:
        """Merge PR."""
        ...
```

### 实现要求

- 使用 `gh` CLI 作为底层实现
- 所有方法必须有类型注解
- 所有错误必须转换为自定义异常
- 必须支持 mock 用于测试

---

## 依赖注入

### 使用 Protocol 进行依赖注入

```python
from typing import Protocol

class PRService:
    def __init__(
        self,
        github_client: GitHubClientProtocol,
        git_client: GitClientProtocol,
        store: Vibe3StoreProtocol,
    ) -> None:
        self.github = github_client
        self.git = git_client
        self.store = store
```

### 测试时注入 Mock

```python
def test_pr_draft():
    mock_github = MockGitHubClient()
    mock_git = MockGitClient()
    mock_store = MockVibe3Store()

    service = PRService(mock_github, mock_git, mock_store)
    # 测试...
```

---

## 验收标准

Phase 3 被认为成功完成，当且仅当：

- [ ] 所有 5 个命令实现完成
- [ ] 所有测试通过 (单元测试 + 集成测试)
- [ ] 代码覆盖率 >= 80%
- [ ] mypy --strict 检查通过
- [ ] 无 `TODO` 或 `print()` 残留
- [ ] 所有文件符合行数限制
- [ ] 文档完整 (命令 help + README 更新)
- [ ] 错误处理完善
- [ ] Metadata 注入格式正确
- [ ] Version bump 策略正确实现

---

## 参考文档

- [docs/v3/implementation/02-architecture.md](../implementation/02-architecture.md) - 架构设计
- [docs/v3/implementation/03-coding-standards.md](../implementation/03-coding-standards.md) - 编码标准
- [docs/v3/implementation/05-logging.md](../implementation/05-logging.md) - 日志规范
- [docs/v3/implementation/06-error-handling.md](../implementation/06-error-handling.md) - 异常处理
- [.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md) - Python 标准

---

**维护者**: Vibe Team
**最后更新**: 2026-03-16