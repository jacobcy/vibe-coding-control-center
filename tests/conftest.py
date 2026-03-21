"""Configure Python path for tests."""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add src to path for imports
scripts_python = Path(__file__).parent.parent / "scripts" / "python"
if str(scripts_python) not in sys.path:
    sys.path.insert(0, str(scripts_python))


# ============================================================
# Flow Service Fixtures
# ============================================================


@pytest.fixture
def flow_state_data():
    """Sample flow state data for testing."""
    return {
        "branch": "test-branch",
        "flow_slug": "test-flow",
        "flow_status": "active",
        "task_issue_number": None,
        "pr_number": None,
        "spec_ref": None,
        "plan_ref": None,
        "report_ref": None,
        "audit_ref": None,
        "planner_actor": None,
        "planner_session_id": None,
        "executor_actor": None,
        "executor_session_id": None,
        "reviewer_actor": None,
        "reviewer_session_id": None,
        "latest_actor": "test-actor",
        "blocked_by": None,
        "next_step": None,
        "updated_at": "2026-03-16T00:00:00",
    }


@pytest.fixture
def mock_store(flow_state_data):
    """Mock Vibe3Store with pre-configured responses."""
    store = Mock()
    store.get_flow_state.return_value = flow_state_data
    store.get_active_flows.return_value = []
    return store


@pytest.fixture
def mock_store_with_task(flow_state_data):
    """Mock store with a task issue already bound."""
    flow_state_data["task_issue_number"] = 101
    store = Mock()
    store.get_flow_state.return_value = flow_state_data
    return store


# ============================================================
# Task Service Fixtures
# ============================================================


@pytest.fixture
def issue_link_data():
    """Sample issue link data for testing."""
    return {
        "branch": "test-branch",
        "issue_number": 101,
        "issue_role": "repo",
        "created_at": "2026-03-16T00:00:00",
    }


@pytest.fixture
def mock_store_for_task(issue_link_data):
    """Mock store configured for task service tests."""
    store = Mock()
    store.get_issue_links.return_value = [issue_link_data]
    return store
