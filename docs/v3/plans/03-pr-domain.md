---
document_type: plan
title: Phase 03 - PR Domain (GitHub Integration)
status: draft
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-16
related_docs:
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
  - docs/v3/plans/v3-rewrite-plan.md
  - docs/v3/implementation/02-architecture.md
  - docs/v3/implementation/03-coding-standards.md
  - docs/v3/implementation/04-test-standards.md
---

# Phase 03: PR Domain (GitHub Integration)

**Goal**: Implement Pull Request automation logic and GitHub API integration.

## 1. Context Anchor (Optional)
If you require more than technical scope, refer to the [Vibe 3.0 Master Plan](v3-rewrite-plan.md).

## 2. Pre-requisites (Executor Entry)
- [ ] `Vibe3Store` can successfully write/read handoff records from SQLite.
- [ ] Environment variables for GitHub API (or `gh` CLI auth) are verified.
- [ ] Phase 02 Flow/Task domain commands are functional.

**重要澄清**：
- SQLite 存储 handoff 记录（执行过程、规范、署名、追责）
- PR 数据通过 `gh` CLI 实时读取，不做本地缓存
- Task 状态通过 `gh project item` 实时读取，不做本地镜像

## 3. Architecture Constraints (引用)

**必须遵守**：
- [02-architecture.md](../implementation/02-architecture.md) - 分层架构与职责
- [03-coding-standards.md](../implementation/03-coding-standards.md) - 技术栈与依赖管理
- [04-test-standards.md](../implementation/04-test-standards.md) - 测试标准与约束

**关键约束**：
- `clients/github_client.py` 必须提供 Protocol 接口，支持 Mock 测试
- `commands/pr.py` 必须 < 100 行，禁止包含业务逻辑
- `services/pr_service.py` 必须 < 300 行，禁止包含 UI 逻辑
- 测试文件必须遵循测试标准（Services 测试 < 150 行，Clients 测试 < 100 行）

## 4. Interaction Requirements

**GitHub 调用标准**: 见 [github-remote-call-standard.md](../../standards/v3/github-remote-call-standard.md)

- **Metadata Injection**: Automatically inject Task ID, Flow Slug, and Group ID into the PR Description.
- **State Feedback**: Fetch PR status (draft, open, merged) and reflect it in `flow status --json`.
- **API Helper**: Use `gh` CLI for all GH interactions (wraps `gh` CLI).

## 2. Technical Requirements

- **PR Draft Logic**: Create PR as draft by default.
- **Versioning**: Implement the "group-based bump" logic where the highest priority change in the group determines the next version (patch/minor/major).
- **PR Readiness**: Move PR from draft to ready once local validation passes.

## 3. Success Criteria (Technical)

- [ ] `vibe3 pr draft` successfully creates a GitHub PR and returns the URL.
- [ ] PR description contains strictly formatted metadata: `Task: #123`, `Flow: <slug>`.
- [ ] `vibe3 pr ready` triggers the correct version bump calculation (logged to STDOUT).
- [ ] Log file confirms "API call successful" for each PR state transition.

## 5. Development Notes (基于 Phase 02 经验)

### 5.1 Client Layer Design Pattern
**参考**: `scripts/python/vibe3/clients/git_client.py`

**经验教训**：
- ✅ Client 层只封装外部系统调用，不包含业务逻辑
- ✅ 所有方法必须返回标准类型（dict, list, primitive），不返回 ORM 对象
- ✅ 使用 Protocol 定义接口，便于测试 Mock
- ❌ 避免：在 Client 层直接使用 subprocess，应封装为方法

**推荐结构**：
```python
# clients/github_client.py
from typing import Protocol

class GitHubClientProtocol(Protocol):
    def create_pr(self, title: str, body: str, draft: bool) -> dict:
        ...

class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("GITHUB_TOKEN")

    def create_pr(self, title: str, body: str, draft: bool) -> dict:
        # 使用 gh CLI 或 PyGithub
        ...
```

### 5.2 PR Metadata 格式规范
**参考**: [2026-03-13-vibe3-parallel-rebuild-design.md](../../plans/2026-03-13-vibe3-parallel-rebuild-design.md) § "Why Draft PR Matters"

**PR Description 模板**：
```markdown
## Task
- Task Issue: #123
- Spec Ref: docs/plans/example.md

## Flow
- Flow: feature-xyz
- Branch: task/feature-xyz

## Issues
- Closes #123
- Related #124, #125

## Agent
- Planner: claude/sonnet-4.5
- Executor: codex/gpt-5.4
```

### 5.3 Version Bump 逻辑
**参考**: [2026-03-13-vibe3-parallel-rebuild-design.md](../../plans/2026-03-13-vibe3-parallel-rebuild-design.md) § "Task / PR Grouping"

**分组规则**：
- `feature`: 默认 bump minor version (0.1.0 → 0.2.0)
- `bug`: 默认 bump patch version (0.1.0 → 0.1.1)
- `docs`/`chore`: 默认不 bump，需显式 `--bump`

**实现位置**：在 `services/pr_service.py` 中实现，不在 Command 层

### 5.4 Error Handling 模式
**参考**: Phase 02 中的 `flow.py` 实现

**推荐模式**：
```python
# commands/pr.py
try:
    pr = service.create_draft_pr(...)
    render_pr_created(pr)
except Exception as e:
    render_error(f"Failed to create PR: {e}")
    raise typer.Exit(1)
```

**禁止**：
- ❌ 直接使用 `print(f"[red]Error: {e}")`
- ❌ 在 Service 层包含 UI 逻辑（rich 颜色标注）

### 5.5 Testing Strategy
**参考**: [04-test-standards.md](../implementation/04-test-standards.md)

**必须测试**：
- GitHub API 调用（使用 Mock）
- Version bump 逻辑（不同 group 的计算）
- PR metadata 生成（格式验证）
- Error handling（网络错误、权限错误）

**测试隔离**：
- 使用 `GitHubClientProtocol` Mock GitHub API
- 不依赖真实 GitHub 仓库

**测试约束**：
- 测试文件 < 100 行（Clients 层），< 180 行（Services 层）
- 单个测试函数 < 40 行（Clients 层），< 50 行（Services 层）
- 测试覆盖率 >= 80%（Services 层），>= 70%（Clients 层）
- 使用 pytest fixtures 减少重复 mock setup

## 6. Handoff for Executor 04
- [ ] Ensure `vibe3 pr draft` returns a URL (real or mock) that can be read by the Handoff sync logic.
