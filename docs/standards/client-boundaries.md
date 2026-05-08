# GitHub Client Boundary Guidelines

## When to Use Client Wrapper vs Direct gh/git

### Use GitHub Client Wrapper When:

1. **Response normalization is needed**
   - Transforming gh CLI output to domain models (e.g., `get_pr` → `PRResponse`)
   - Deriving computed fields (e.g., `is_ready`, `ci_passed`)
   - Normalizing error types (e.g., network errors vs user errors)

2. **Error handling requires domain knowledge**
   - Converting CLI errors to domain exceptions
   - Providing user-friendly error messages with context
   - Handling retry logic with domain-specific policies

3. **Testing benefits outweigh indirection cost**
   - Protocol seams enable mock injection
   - Complex logic needs unit testing without GitHub dependency
   - Multiple implementations may exist (e.g., REST API vs CLI)

4. **Operations require orchestration**
   - Multi-step operations (e.g., `create_pr` with body repair)
   - Operations with pre/post-conditions (e.g., `close_pr` with comment)
   - Cross-resource coordination

### Use Direct gh/git CLI When:

1. **Simple pass-through with no normalization**
   - Direct command execution with minimal processing
   - No response transformation beyond basic parsing
   - Logging is the only added value

2. **Prototyping or one-off commands**
   - Exploratory code that may not survive
   - Quick scripts that don't need testing
   - Debug/inspection commands

3. **Performance-critical paths with known behavior**
   - Hot paths where wrapper overhead matters
   - Commands called in tight loops
   - Batch operations with proven patterns

## Narrow Port Pattern

### Overview

Instead of a single broad `GitHubClientProtocol` with 20+ methods, define narrow ports for specific use cases:

```python
# Bad: Broad protocol
class GitHubClientProtocol(Protocol):
    def get_pr(...): ...
    def create_pr(...): ...
    def view_issue(...): ...
    def close_issue(...): ...
    # ... 16 more methods

# Good: Narrow ports
class PRReadPort(Protocol):
    def get_pr(...): ...
    def list_prs_for_branch(...): ...

class PRWritePort(Protocol):
    def create_pr(...): ...
    def update_pr(...): ...

# Composite for backward compatibility
class GitHubClientProtocol(PRReadPort, PRWritePort, ..., Protocol):
    pass
```

### Benefits

1. **Clear dependencies**: Services declare exactly what they need
2. **Easier mocking**: Tests only mock relevant methods
3. **Decoupling**: Implementation changes don't ripple through codebase
4. **Self-documenting**: Port names reveal intent (e.g., `PRReadPort`)

### When to Define a Narrow Port

1. **A service uses a cohesive subset of methods**
   - Group related operations (e.g., PR read operations)
   - Service depends on 3-7 methods from a larger protocol

2. **Multiple implementations may exist**
   - Different backends (CLI vs REST API)
   - Test fakes vs production implementations

3. **Testing isolation is valuable**
   - Complex service logic needs unit testing
   - Integration tests are slow/expensive

### Implementation Pattern

```python
# protocols.py
class PRReadPort(Protocol):
    def get_pr(self, pr_number: int | None = None, branch: str | None = None) -> PRResponse | None: ...
    def list_prs_for_branch(self, branch: str, *, state: str | None = None) -> list[PRResponse]: ...
    def list_all_prs(self, state: str = "open", limit: int = 100) -> list[PRResponse]: ...

# Backward compatibility
class GitHubClientProtocol(PRReadPort, PRWritePort, ..., Protocol):
    """Composite protocol combining all narrow ports."""
    pass

# service.py
class MyService:
    def __init__(self, pr_reader: PRReadPort) -> None:
        self.pr_reader = pr_reader
    
    def do_something(self) -> None:
        pr = self.pr_reader.get_pr(123)  # Only uses PRReadPort
```

## Current Client Structure

After refactoring (Issue #406):

- `github_pr_read_ops.py` (256 LOC) — PR query operations
- `github_pr_write_ops.py` (279 LOC) — PR mutation operations  
- `github_review_ops.py` (128 LOC) — PR review/diff operations
- `github_issues_ops.py` (236 LOC) — Issue query operations
- `github_issue_admin_ops.py` — Issue admin operations
- `github_comment_ops.py` — Comment operations

All files under 400 LOC limit, enabling maintainable, focused modules.
