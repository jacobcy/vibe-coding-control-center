# Client Lifecycle Management Standards

## Purpose

This document establishes standards for managing the lifecycle of `GitClient` and `GitHubClient` instances in the vibe3 codebase, ensuring clean architecture boundaries and proper dependency injection patterns.

## Core Principles

### Layered Architecture

The vibe3 system follows a three-layer architecture:

1. **Clients Layer** (`src/vibe3/clients/`): External system interfaces (Git, GitHub)
2. **Services Layer** (`src/vibe3/services/`): Business logic orchestration
3. **App Boundary Layer** (`src/vibe3/server/`, commands): Request handling and app lifecycle

### Instance Creation Scopes

The following scopes determine where and how client instances should be created:

| Scope | Location | Lifetime | Pattern |
|-------|----------|----------|---------|
| **App-level** | `server/registry.py` | Single app run | Create once, inject into multiple services |
| **Request-level** | Service constructors | Single request/command | Constructor injection with fallback |
| **Local** | Function/method bodies | Single function call | Direct construction for one-off operations |

## Allowed Patterns

### ✅ Services Layer: Constructor Injection with Fallback

Services should accept optional client parameters and fallback to default construction:

```python
class MyService:
    def __init__(
        self,
        git_client: GitClient | None = None,
        github_client: GitHubClient | None = None,
    ):
        self.git_client = git_client or GitClient()
        self.github_client = github_client or GitHubClient()
```

**Why this works**:
- Allows test injection via mock clients
- Maintains backward compatibility with existing callers
- Each service instance controls its own client lifetime
- No hidden global state

**Example**: `check_service.py:64-65`

### ✅ App Boundary Layer: Instance Sharing

At app startup, create shared instances and inject them into multiple services:

```python
# server/registry.py
shared_github = GitHubClient()
service_a = ServiceA(github_client=shared_github)
service_b = ServiceB(github_client=shared_github)
```

**Why this works**:
- Cache instances that are expensive to create
- Scope limited to single app lifecycle (e.g., one request in serverless)
- Explicit sharing, not hidden singleton
- Easy to trace injection path

**Example**: `server/registry.py:64`

### ✅ Local Scope: Direct Construction

For one-off operations that don't need sharing:

```python
def some_function():
    git = GitClient()
    return git.get_current_branch()
```

**Why this works**:
- Clear lifetime boundaries (function scope)
- No cross-contamination between calls
- Simple and direct

## Prohibited Patterns

### ❌ Clients Layer: Global Singleton Factories

**Do not use `@lru_cache` to create global client instances in the Clients layer**:

```python
# ❌ WRONG: Clients layer global singleton
@lru_cache
def get_git_client() -> GitClient:
    return GitClient()
```

**Why this violates architecture**:
- **Crosses layer boundaries**: Clients layer should not manage instance lifecycle
- **Worktree boundary violation**: Shared `.git` common dir across worktrees can cause cache collision
- **Hidden global state**: Difficult to test, difficult to reason about
- **Cache semantics unclear**: Should cache key be repo path? Current directory? Git common dir?

### ❌ Services Layer: Hidden Global State

Services should not maintain module-level client caches:

```python
# ❌ WRONG: Module-level singleton
_GIT_CLIENT: GitClient | None = None

def get_git_client() -> GitClient:
    global _GIT_CLIENT
    if _GIT_CLIENT is None:
        _GIT_CLIENT = GitClient()
    return _GIT_CLIENT
```

**Why this violates architecture**:
- Hidden dependency (not visible in constructor)
- Difficult to reset between tests
- Lifetime unclear (module load? first call?)

## Special Cases

### Instance-Level Caching

**Allowed**: Instance-level caches that are scoped to a single client instance:

```python
class GitClient:
    def __init__(self):
        self._pr_diff_cache: dict[str, str] = {}
```

**Why this is acceptable** (`git_client.py:119`):
- Cache lifetime bound to instance lifetime
- No hidden global state (cache is instance attribute)
- Each instance has its own cache
- Caller controls lifetime via injection or direct construction

**Distinction from prohibited patterns**:
- ✅ Instance-level: `self._cache` (lifetime = instance lifetime)
- ❌ Module-level: `_GLOBAL_CACHE` (lifetime = process lifetime)
- ❌ Factory-level: `@lru_cache get_client()` (lifetime = process lifetime)

## Migration Path

### Current State

- ~20 services already support constructor injection (e.g., `check_service.py`)
- ~40 call sites still use direct construction (acceptable, not a target for mass migration)
- No global singleton factories exist in the codebase (PR #690 was closed unmerged)

### Target State

- All **critical services** support constructor injection
- Documentation establishes clear standards
- Tests verify injection paths work correctly

### Gradual Migration Strategy

1. **Fix critical services**: Ensure services used by multiple callers support injection
2. **Add tests**: Verify injection paths work for DI-supported services
3. **Incremental improvement**: When modifying a service/command, add injection support if missing
4. **No mass migration**: Do not attempt to change all 40+ call sites in one PR

**Rationale**: Gradual migration reduces risk and allows testing patterns in production before broader adoption.

## Testing Guidelines

### Unit Tests

Services with constructor injection should be tested with mock clients:

```python
def test_service_with_mock():
    mock_git = Mock(spec=GitClient)
    mock_git.get_current_branch.return_value = "main"

    service = MyService(git_client=mock_git)
    result = service.get_branch_info()

    mock_git.get_current_branch.assert_called_once()
```

### Integration Tests

When testing full workflows, use real clients or shared fixtures:

```python
@pytest.fixture
def shared_github_client():
    return GitHubClient()

def test_full_workflow(shared_github_client):
    service = MyService(github_client=shared_github_client)
    # ... integration test logic
```

## Historical Context

### Why PR #690 Was Closed

PR #690 attempted to introduce `@lru_cache` factory functions in the Clients layer. This approach was rejected because:

1. **Architecture violation**: Clients should not manage their own lifecycle
2. **Worktree complexity**: Multiple worktrees share `.git` common dir, making cache key selection ambiguous
3. **Testing difficulty**: Global singletons are harder to mock and reset between tests
4. **Cache invalidation**: No clear strategy for when to invalidate cached instances

The correct solution is constructor injection at the Services layer, with optional sharing at the App boundary layer.

## Acceptance Criteria

For code changes involving client lifecycle:

- [ ] No `@lru_cache` in Clients layer for client instances
- [ ] Services use constructor injection with fallback (`client or Client()`)
- [ ] App boundary explicitly manages shared instances
- [ ] Tests verify both injection and fallback paths
- [ ] Documentation updated if patterns change

## References

- Issue #704: Refactor GitClient/GitHubClient with dependency injection
- Issue #690: Original factory singleton approach (closed unmerged)
- `check_service.py`: Example of correct DI pattern
- `server/registry.py:64`: Example of app-level sharing
