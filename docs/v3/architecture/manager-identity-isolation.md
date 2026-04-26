# Manager Identity & Token Isolation Design

## 1. Background

In the current implementation, the Manager Agent sharing the same `GITHUB_TOKEN` with human users leads to identity confusion. The Manager cannot distinguish between its own previous comments and new human instructions, which can cause logic loops and "ghost" transitions (e.g., an issue moving back and forth between states because the Manager misinterprets its own progress report as a new command).

## 2. Design Principles

### 2.1 Architectural Philosophy

- **Leverage Existing V2/V3 Structure**:
  - V2 (Shell): Infrastructure layer - `vibe keys` for key management, `vibe doctor` for validation
  - V3 (Python): Business logic layer - roles, execution, orchestration

- **Minimal Changes, Maximum Compatibility**:
  - Preserve backward compatibility: existing `GitHubClient()` calls continue to work
  - Optional injection: role-specific tokens are opt-in, not mandatory
  - Progressive enhancement: start with manager role, extend to other roles incrementally

- **Fail-Fast at Runtime**:
  - Doctor checks token permissions during environment validation
  - Role execution fails fast when token is invalid or missing
  - No startup blocking: server starts even if optional tokens are missing

### 2.2 Extensibility Goals

This architecture supports future extensions:
- Different roles using different GitHub accounts (manager, governance, supervisor)
- Role-specific permission isolation
- Gradual migration from shared token to isolated tokens
- Zero breaking changes to existing functionality

## 3. Implementation Phases

### Phase 1: Infrastructure Foundation (V2 Layer)

**Objective**: Establish key management infrastructure with permission validation.

#### Step 1.1: Key Registration

**File**: `config/keys.template.env`
```bash
# Add new entry
VIBE_MANAGER_GITHUB_TOKEN=
```

This follows the existing V2 key management pattern.

#### Step 1.2: Doctor Permission Check

**File**: `lib/doctor.sh`

Add a new check function:

```bash
check_manager_token() {
    print_check "Manager Token (VIBE_MANAGER_GITHUB_TOKEN)"

    if [ -z "$VIBE_MANAGER_GITHUB_TOKEN" ]; then
        print_fail "Not configured"
        print_fix "Run: vibe keys set VIBE_MANAGER_GITHUB_TOKEN"
        return 1
    fi

    # Validate token permissions
    local username
    username=$(GH_TOKEN="$VIBE_MANAGER_GITHUB_TOKEN" gh api user -q '.login' 2>/dev/null)

    if [ $? -ne 0 ]; then
        print_fail "Token validation failed (invalid or insufficient permissions)"
        return 1
    fi

    # Cross-check with settings.yaml bot_username
    local expected_username
    expected_username=$(grep "bot_username:" config/settings.yaml | awk '{print $2}' 2>/dev/null)

    if [ -n "$expected_username" ] && [ "$username" != "$expected_username" ]; then
        print_fail "Identity mismatch (expected: $expected_username, got: $username)"
        return 1
    fi

    print_ok "Configured (user: $username)"
    return 0
}
```

**Integration**: Add this check to `vibe_doctor()` function when `--full` flag is used.

**Rationale**:
- ✅ Follows V2 responsibility: infrastructure validation
- ✅ Checks token permissions (not just existence)
- ✅ Provides actionable error messages

---

### Phase 2: GitHubClient Token Injection (V3 Layer)

**Objective**: Enable optional token injection while preserving backward compatibility.

#### Step 2.1: GitHubClient Optional Token Parameter

**File**: `src/vibe3/clients/github_client_base.py`

```python
import os
import subprocess
from typing import Any

from loguru import logger

from vibe3.exceptions import GitHubError, UserError


class GitHubClientBase:
    """Base class for GitHub client operations."""

    def __init__(self, token: str | None = None):
        """
        Initialize GitHub client with optional token override.

        Args:
            token: Optional explicit token. If None, uses GH_TOKEN from environment.
                   This preserves backward compatibility: existing GitHubClient() calls
                   continue to use global GH_TOKEN.

        Design:
            - Backward compatible: GitHubClient() works as before
            - Opt-in injection: GitHubClient(token="...") for role-specific tokens
            - Fallback chain: explicit token → GH_TOKEN → GITHUB_TOKEN
        """
        self._explicit_token = token

    def _get_effective_token(self) -> str | None:
        """Get the effective token following fallback chain."""
        if self._explicit_token is not None:
            return self._explicit_token
        return os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")

    def _run_gh(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        """Run gh CLI with token injection.

        All gh commands should use this method instead of direct subprocess.run(["gh", ...]).
        This ensures the explicit token (if provided) is injected into GH_TOKEN environment variable.
        """
        env = os.environ.copy()
        token = self._get_effective_token()
        if token:
            env["GH_TOKEN"] = token

        return subprocess.run(["gh"] + args, env=env, **kwargs)

    def check_auth(self) -> bool:
        """Check if authenticated to GitHub."""
        try:
            result = self._run_gh(["auth", "status"], capture_output=True, text=True)
            return result.returncode == 0
        except Exception:
            logger.bind(external="github", operation="check_auth").error(
                "Failed to check auth"
            )
            return False

    def get_current_user(self) -> str:
        """Get current authenticated user login name."""
        try:
            result = self._run_gh(
                ["api", "user", "-q", ".login"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = (e.stderr or str(e)).strip()
            raise GitHubError(
                status_code=e.returncode,
                message=f"Failed to get current GitHub user: {error_msg}",
            ) from e

    # ... rest of existing methods remain unchanged, but should use self._run_gh() ...
```

**Migration Note**:
- Existing `GitHubClient()` calls continue to work (backward compatible)
- All methods using `subprocess.run(["gh", ...])` should migrate to `self._run_gh([...])`
- This is a **non-breaking change**: no existing call sites need modification

**Backward Compatibility Verification**:
```python
# Existing code - continues to work
client = GitHubClient()
user = client.get_current_user()  # Uses global GH_TOKEN

# New code - role-specific token
client = GitHubClient(token="ghp_manager_token")
user = client.get_current_user()  # Uses manager-specific token
```

---

### Phase 3: Configuration Extension (V3 Layer)

**Objective**: Define role-specific token configuration with future extensibility.

#### Step 3.1: Role Identity Configuration

**File**: `src/vibe3/models/orchestra_config.py`

```python
class AssigneeDispatchConfig(BaseModel):
    """Configuration for assignee-based manager dispatch."""

    enabled: bool = True
    use_worktree: bool = True
    agent: str | None = None
    backend: str | None = None
    model: str | None = None
    timeout_seconds: int = Field(default=3600, ge=60)
    prompt_template: str = Field(default="orchestra.assignee_dispatch.manager")
    supervisor_file: str | None = Field(default="supervisor/manager.md")
    include_supervisor_content: bool = Field(default=True)

    # NEW: Role-specific token configuration
    token_env: str | None = Field(
        default="VIBE_MANAGER_GITHUB_TOKEN",
        description=(
            "Environment variable name for manager-specific GitHub token. "
            "If None or token not set, falls back to global GH_TOKEN. "
            "This enables role isolation: manager can use a dedicated bot account."
        ),
    )
```

**Extensibility Pattern**:
```python
# Future extension: other roles can follow the same pattern

class GovernanceConfig(BaseModel):
    """Configuration for periodic governance scan service."""

    enabled: bool = True
    # ... existing fields ...

    # Future: governance-specific token
    token_env: str | None = Field(
        default="VIBE_GOVERNANCE_GITHUB_TOKEN",
        description="Environment variable name for governance-specific GitHub token",
    )


class SupervisorHandoffConfig(BaseModel):
    """Configuration for supervisor handoff issue consumption."""

    enabled: bool = True
    # ... existing fields ...

    # Future: supervisor-specific token
    token_env: str | None = Field(
        default="VIBE_SUPERVISOR_GITHUB_TOKEN",
        description="Environment variable name for supervisor-specific GitHub token",
    )
```

---

### Phase 4: Role-Level Token Injection (V3 Layer)

**Objective**: Inject role-specific token during role construction.

#### Step 4.1: Manager Request Builder

**File**: `src/vibe3/roles/manager.py`

```python
import os
from pathlib import Path
from typing import Any

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo
from vibe3.execution.contracts import ExecutionRequest

def build_manager_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    *,
    registry: SessionRegistryService | None = None,
    repo_path: Path | None = None,
    actor: str = "orchestra:manager",
) -> ExecutionRequest | None:
    """Build the manager execution request with optional token injection.

    Design:
        - Role isolation: manager can use dedicated token
        - Backward compatible: falls back to global GH_TOKEN if token_env not configured
        - Fail-fast: missing optional token logs warning but doesn't block execution
    """
    # ... existing flow creation logic ...

    # Prepare environment variables
    env = dict(os.environ)

    # Inject manager-specific token (if configured)
    if config.assignee_dispatch.token_env:
        manager_token = os.getenv(config.assignee_dispatch.token_env)
        if manager_token:
            env["GH_TOKEN"] = manager_token
            logger.bind(domain="manager", issue_number=issue.number).info(
                f"Using manager-specific token from {config.assignee_dispatch.token_env}"
            )
        else:
            logger.bind(domain="manager", issue_number=issue.number).debug(
                f"Manager token not configured ({config.assignee_dispatch.token_env}), "
                "using global GH_TOKEN"
            )

    # Build request with enhanced environment
    request = build_issue_async_cli_request(
        role="manager",
        issue=issue,
        target_branch=flow_branch,
        command_args=["internal", "manager", str(issue.number), "--no-async"],
        actor=actor,
        execution_name=get_manager_session_name(issue.number),
        refs=refs,
        env=env,  # Injected environment with role-specific token
        worktree_requirement=MANAGER_ROLE.worktree,
        repo_path=repo_path,
    )

    return request
```

#### Step 4.2: Manager Execution with Dedicated Client

**File**: `src/vibe3/commands/internal.py`

```python
import os
from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestra_config import OrchestraConfig

def internal_manager_dispatch(
    issue_number: int,
    config: OrchestraConfig,
) -> None:
    """Manager dispatch with role-specific GitHub client.

    This creates a GitHubClient instance with manager-specific token,
    ensuring role isolation at the client level.
    """
    # Resolve manager-specific token
    manager_token: str | None = None
    if config.assignee_dispatch.token_env:
        manager_token = os.getenv(config.assignee_dispatch.token_env)

    # Create manager-dedicated client
    github = GitHubClient(token=manager_token) if manager_token else GitHubClient()

    # Execute manager logic with isolated client
    # ... existing manager execution logic ...
```

**Rationale**:
- ✅ Role isolation: manager uses dedicated token at client level
- ✅ Backward compatible: falls back to global token gracefully
- ✅ Consistent with existing architecture: token injection via environment variables

---

### Phase 5: Prompt-Level Identity Filtering (V3 Layer)

**Objective**: Prevent self-referential loops through prompt-level logic.

#### Step 5.1: Manager Prompt Enhancement

**File**: `supervisor/manager.md`

```markdown
## Identity Isolation Rules

When reading issue comments for "Human Instructions":

### Self-Identity Detection

1. **Get Your Own Username**:
   ```python
   import os
   from vibe3.models.orchestra_config import OrchestraConfig

   # Try environment variable first (injected during role construction)
   bot_username = os.getenv("VIBE3_BOT_USERNAME")

   # Fallback to config
   if not bot_username:
       config = OrchestraConfig()  # Load from settings.yaml
       bot_username = config.bot_username
   ```

2. **Comment Filtering Logic**:
   ```python
   def filter_human_instructions(comments: list[Comment], bot_username: str) -> list[Comment]:
       """
       Filter out bot's own comments and automated reports.

       Rules:
           - Skip comments where author == bot_username
           - Skip comments containing [manager] marker
           - NEVER interpret your own status reports as new commands
       """
       return [
           c for c in comments
           if c.author != bot_username and "[manager]" not in c.body
       ]
   ```

### Example Scenario

Given these comments:
1. `author="human"`, body="Please implement feature X"
2. `author="vibe-manager-bot"`, body="[manager] Moving to plan phase"
3. `author="human"`, body="Also add tests"

Filtered human instructions:
- Comment 1: "Please implement feature X"
- Comment 3: "Also add tests"

Comment 2 is ignored (bot's own report).
```

#### Step 5.2: Environment Variable Injection

**File**: `src/vibe3/roles/manager.py`

```python
def build_manager_request(...) -> ExecutionRequest | None:
    # ... existing logic ...

    env = dict(os.environ)

    # Inject bot_username for identity detection
    if config.bot_username:
        env["VIBE3_BOT_USERNAME"] = config.bot_username

    # Inject manager-specific token
    if config.assignee_dispatch.token_env:
        manager_token = os.getenv(config.assignee_dispatch.token_env)
        if manager_token:
            env["GH_TOKEN"] = manager_token

    # ... rest of request building ...
```

---

### Phase 6: UI Enhancement (Optional)

**Objective**: Improve CLI output to distinguish human vs. bot actions.

#### Step 6.1: Task Show Refactoring

**File**: `src/vibe3/ui/task_ui.py`

```python
from rich.panel import Panel
from rich.console import Console

def render_task_comments(
    comments: list[Comment],
    bot_username: str | None,
) -> Panel:
    """
    Render comments with separated sections.

    Sections:
        1. Human Instructions (expanded, max 3 visible)
        2. Bot Reports (collapsed by default)
    """
    if not bot_username:
        # No bot identity configured, show all comments uniformly
        return _render_all_comments(comments)

    # Separate human and bot comments
    human_comments = [c for c in comments if c.author != bot_username]
    bot_comments = [c for c in comments if c.author == bot_username]

    console = Console()

    # Render human instructions
    human_content = ""
    for c in human_comments[:3]:  # Show max 3 recent
        human_content += f"[bold]{c.author}[/] ({c.timestamp}):\n{c.body}\n\n"
    if len(human_comments) > 3:
        human_content += f"[dim]... and {len(human_comments) - 3} older instructions[/]"

    # Render bot reports (collapsed)
    bot_content = ""
    if bot_comments:
        latest = bot_comments[-1]
        bot_content = f"\n\n[dim]Bot Reports ({len(bot_comments)} total)[/]\n"
        bot_content += f"[dim]Latest: {latest.timestamp}[/]"

    return Panel(human_content + bot_content, title="Issue Timeline")
```

---

## 4. Migration Path

### Phase 1: Foundation (Immediate)
- [x] Add `VIBE_MANAGER_GITHUB_TOKEN` to `config/keys.template.env`
- [x] Implement `check_manager_token()` in `lib/doctor.sh`
- [x] Test doctor check with valid and invalid tokens

### Phase 2: Client Enhancement (Next)
- [ ] Add optional `token` parameter to `GitHubClientBase.__init__()`
- [ ] Migrate all `subprocess.run(["gh", ...])` to `self._run_gh([...])`
- [ ] Verify backward compatibility: all existing `GitHubClient()` calls work

### Phase 3: Configuration (Parallel)
- [ ] Add `token_env` field to `AssigneeDispatchConfig`
- [ ] Update `config/settings.yaml` documentation
- [ ] Test with and without token configuration

### Phase 4: Role Isolation (Core)
- [ ] Implement token injection in `build_manager_request()`
- [ ] Implement dedicated client in `internal_manager_dispatch()`
- [ ] Test manager execution with isolated token

### Phase 5: Prompt Logic (Essential)
- [ ] Add identity filtering rules to `supervisor/manager.md`
- [ ] Inject `VIBE3_BOT_USERNAME` in role builder
- [ ] Test comment filtering with bot's own comments

### Phase 6: UI Polish (Optional)
- [ ] Implement `render_task_comments()` with bot filtering
- [ ] Update `vibe task show` to use new renderer
- [ ] Test with mixed human/bot comments

---

## 5. Testing Strategy

### Unit Tests

**File**: `tests/vibe3/test_github_client.py`

```python
import os
import pytest
from vibe3.clients.github_client import GitHubClient

def test_client_backward_compatible():
    """Existing GitHubClient() calls should work without modification."""
    os.environ["GH_TOKEN"] = "global_token"
    client = GitHubClient()  # No parameters
    assert client._get_effective_token() == "global_token"

def test_client_token_override():
    """Explicit token should override environment variable."""
    os.environ["GH_TOKEN"] = "global_token"
    client = GitHubClient(token="role_specific_token")
    assert client._get_effective_token() == "role_specific_token"

def test_client_fallback_chain():
    """Should fallback to GITHUB_TOKEN if GH_TOKEN missing."""
    os.environ.pop("GH_TOKEN", None)
    os.environ["GITHUB_TOKEN"] = "legacy_token"
    client = GitHubClient()
    assert client._get_effective_token() == "legacy_token"
```

**File**: `tests/vibe3/test_manager_request.py`

```python
import os
import pytest
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.roles.manager import build_manager_request

def test_manager_request_injects_token(monkeypatch):
    """Manager request should inject role-specific token into env."""
    config = OrchestraConfig(
        assignee_dispatch=AssigneeDispatchConfig(
            token_env="VIBE_MANAGER_GITHUB_TOKEN"
        )
    )
    monkeypatch.setenv("VIBE_MANAGER_GITHUB_TOKEN", "manager_token")

    request = build_manager_request(config, mock_issue())
    assert request.env["GH_TOKEN"] == "manager_token"

def test_manager_request_fallback_to_global_token():
    """Should use global GH_TOKEN if manager token not configured."""
    config = OrchestraConfig(
        assignee_dispatch=AssigneeDispatchConfig(token_env=None)
    )
    os.environ["GH_TOKEN"] = "global_token"

    request = build_manager_request(config, mock_issue())
    assert request.env["GH_TOKEN"] == "global_token"
```

### Integration Tests

**File**: `tests/vibe3/test_role_isolation.py`

```python
def test_manager_uses_isolated_client():
    """Manager should create GitHubClient with isolated token."""
    # Setup: configure manager token
    # Execute: internal_manager_dispatch()
    # Verify: GitHub calls use manager bot account
    # Teardown: clean up test issue
```

---

## 6. Expected Outcomes

### Immediate Benefits
- **Zero Self-Loops**: Manager filters own comments, never misinterprets reports as commands
- **Backward Compatibility**: All existing code continues to work without modification
- **Progressive Enhancement**: Start with manager, extend to other roles incrementally

### Long-Term Benefits
- **Role Isolation**: Each role can use dedicated bot account
- **Permission Separation**: Manager, governance, supervisor can have different permissions
- **Audit Clarity**: GitHub timeline clearly distinguishes human vs. bot actions
- **Improved UX**: CLI users see high-signal human instructions without bot noise

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Token not configured before manager execution | Doctor check warns during environment validation; execution fails fast with clear error message |
| Token belongs to wrong account | Doctor cross-checks `bot_username` in config; manager filters comments using username |
| Breaking existing GitHubClient() calls | Backward compatibility verified by tests; no parameters required |
| Performance overhead from token injection | Minimal: one `os.getenv()` call per role construction |
| User confusion about which token to use | Clear documentation: `vibe keys set VIBE_MANAGER_GITHUB_TOKEN` |

---

## 8. Future Extensions

### Multi-Role Token Isolation

```yaml
# config/settings.yaml
orchestra:
  assignee_dispatch:
    token_env: "VIBE_MANAGER_GITHUB_TOKEN"

  governance:
    token_env: "VIBE_GOVERNANCE_GITHUB_TOKEN"

  supervisor_handoff:
    token_env: "VIBE_SUPERVISOR_GITHUB_TOKEN"
```

### Token Permission Templates

```bash
# Different token types with different permissions
VIBE_MANAGER_GITHUB_TOKEN_READONLY  # Read-only access
VIBE_MANAGER_GITHUB_TOKEN_WRITE     # Write access for comments/labels
VIBE_MANAGER_GITHUB_TOKEN_ADMIN     # Full access for critical operations
```

### Role-Specific Rate Limiting

```python
# Each role has independent rate limit
manager_client = GitHubClient(token=manager_token, rate_limit=1000/hour)
governance_client = GitHubClient(token=governance_token, rate_limit=100/hour)
```

---

## 9. Summary

### Key Design Decisions

1. **Minimal Changes**: Optional token parameter in `GitHubClient`, backward compatible
2. **Role-Level Injection**: Token injection happens in role builders, not coordinator
3. **V2/V3 Separation**: V2 handles key management, V3 handles business logic
4. **Fail-Fast at Runtime**: Doctor validates permissions, execution fails fast if token invalid
5. **Future-Proof**: Architecture supports multi-role token isolation

### Implementation Philosophy

```
Leverage Existing V2/V3 Architecture
  ├── V2 (Shell): Infrastructure
  │   ├── vibe keys: key management
  │   └── vibe doctor: permission validation
  │
  └── V3 (Python): Business Logic
      ├── GitHubClient: optional token (backward compatible)
      ├── OrchestraConfig: role-specific token_env
      ├── Role Builders: inject token into environment
      └── Prompt Layer: filter self-referential comments
```

### Next Steps

1. **Implement Phase 1**: Doctor check for manager token
2. **Implement Phase 2**: GitHubClient optional token parameter
3. **Implement Phase 3-5**: Configuration and role injection
4. **Test thoroughly**: Verify backward compatibility and isolation
5. **Document migration**: Provide clear user guide

This architecture provides a solid foundation for role isolation while preserving existing investments and enabling future extensions.
