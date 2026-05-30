"""Shared fixtures for exception tests."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from vibe3.clients import SQLiteClient
from vibe3.services.error_tracking_service import ErrorTrackingService


@pytest.fixture(autouse=True)
def reset_error_tracking() -> Iterator[None]:
    """Reset ErrorTrackingService singleton between tests to prevent state leakage."""
    yield
    ErrorTrackingService.clear_instance()


@pytest.fixture
def temp_store(tmp_path: Path) -> SQLiteClient:
    """Create a temporary SQLiteClient for testing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    from vibe3.clients import init_schema

    init_schema(conn)
    conn.close()
    return SQLiteClient(db_path=str(db_path))
