# Session ID Management and Resume Support

**Issue**: #249
**Created**: 2026-03-24
**Status**: Revised Plan

## Overview

实现 codeagent-wrapper 的 session ID 存储和 resume 功能，利用已有的数据库字段，避免重复传递完整 prompt，节省 token 成本。

## Background

当前 `codeagent-wrapper` 每次执行都会在输出中包含 session ID（格式：`SESSION_ID: <uuid>`），但 vibe3 没有存储和利用这个 session ID，导致每次都创建新 session 并传递完整 prompt。

数据库 schema 已经预留了 session_id 字段（v3 架构）：
- `planner_session_id` — plan 命令
- `executor_session_id` — run 命令
- `reviewer_session_id` — review 命令

## Goals

1. 正确解析并存储 session ID 到数据库
2. 实现 resume 模式，支持恢复之前的会话
3. 更新 plan/run/review 命令集成
4. 保持向后兼容，不影响现有流程

## Technical Design

### 1. Data Model Changes

#### 1.1 ReviewAgentResult 扩展

**File**: `src/vibe3/services/review_runner.py`

```python
@dataclass(frozen=True)
class ReviewAgentResult:
    """Result from running a review agent."""
    exit_code: int
    stdout: str
    stderr: str
    session_id: str | None = None  # NEW: Session ID from codeagent-wrapper
```

### 2. Core Logic Implementation

#### 2.1 Session ID Extraction

**File**: `src/vibe3/services/review_runner.py`

```python
import re

def extract_session_id(stdout: str) -> str | None:
    """Extract session ID from codeagent-wrapper output."""
    # Pattern to match UUID: SESSION_ID: 262f0fea-eacb-4223-b842-b5b5097f94e8
    match = re.search(r'SESSION_ID:\s*([a-f0-9-]{36})', stdout)
    return match.group(1) if match else None
```

#### 2.2 run_review_agent Modification

**File**: `src/vibe3/services/review_runner.py`

Update `run_review_agent` to handle `resume` command:

```python
def run_review_agent(
    prompt_file_content: str,
    options: ReviewAgentOptions,
    task: str | None = None,
    dry_run: bool = False,
    session_id: str | None = None,  # NEW parameter
) -> ReviewAgentResult:
    # ...
    if session_id:
        # Resume mode: codeagent-wrapper resume <session_id> <task>
        command.extend(["resume", session_id])
        command.append(task or "continue") # Default task if none provided
    else:
        # Normal mode with --prompt-file
        # ... existing logic ...
```

### 3. Database Storage

#### 3.1 record_handoff Modification

**File**: `src/vibe3/services/handoff_recorder.py`

Update `record_handoff` to accept and store `session_id`.

```python
def record_handoff(
    store: SQLiteClient,
    git_client: GitClient,
    handoff_type: str,
    ref: str,
    next_step: str | None,
    blocked_by: str | None,
    actor: str,
    session_id: str | None = None,  # NEW
) -> None:
    # ...
    if session_id:
        if handoff_type == "plan":
            update_kwargs["planner_session_id"] = session_id
        elif handoff_type == "report":
            update_kwargs["executor_session_id"] = session_id
        elif handoff_type == "audit":
            update_kwargs["reviewer_session_id"] = session_id
    # ...
```

#### 3.2 HandoffService Modification

**File**: `src/vibe3/services/handoff_service.py`

Update `record_plan`, `record_report`, `record_audit` to accept `session_id`.

### 4. Command Integration

#### 4.1 Local Recording Helpers

The following helper functions need to be updated to store `session_id` in `flow_state`:
- `record_plan_event` in `src/vibe3/commands/plan_helpers.py`
- `_record_run_event` in `src/vibe3/commands/run.py`
- `_record_review_event` in `src/vibe3/commands/review.py`

Example for `record_plan_event`:
```python
def record_plan_event(
    plan_content: str,
    options: ReviewAgentOptions,
    session_id: str | None = None,  # NEW
) -> Path | None:
    # ...
    store.update_flow_state(
        branch, 
        plan_ref=str(plan_file), 
        planner_actor=actor,
        planner_session_id=session_id  # NEW
    )
```

#### 4.2 Loading Session ID

Commands should attempt to load the existing `session_id` from `flow_state` before calling `run_review_agent`.

### 5. UI Improvements

**File**: `src/vibe3/commands/handoff.py`

Update `_render_agent_chain` to show session IDs (shortened) and add hints to `show` command.

## Implementation Steps

### Phase 1: Core Service Updates
- [ ] Update `ReviewAgentResult` in `src/vibe3/services/review_runner.py`
- [ ] Implement `extract_session_id` in `src/vibe3/services/review_runner.py`
- [ ] Update `run_review_agent` in `src/vibe3/services/review_runner.py` to support `resume`

### Phase 2: Storage Infrastructure
- [ ] Update `record_handoff` in `src/vibe3/services/handoff_recorder.py`
- [ ] Update `HandoffService` in `src/vibe3/services/handoff_service.py`

### Phase 3: Command Integration
- [ ] Update `plan` command and `record_plan_event`
- [ ] Update `run` command and `_record_run_event`
- [ ] Update `review` command and `_record_review_event`

### Phase 4: UI & Verification
- [ ] Update `vibe3 handoff show` to display session IDs and resume hints
- [ ] Add unit tests for extraction and resume logic
- [ ] Manual verification with `codeagent-wrapper`
