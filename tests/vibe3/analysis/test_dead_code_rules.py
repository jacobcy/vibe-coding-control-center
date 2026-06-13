"""Tests for dead code detection rules."""

import tempfile
from pathlib import Path

import pytest

from vibe3.analysis.dead_code_rules import (
    classify_confidence,
    get_router_functions,
    is_dead_code,
    is_private,
    should_exclude,
)


class TestShouldExclude:
    """Test exclusion patterns."""

    @pytest.mark.parametrize(
        "func_name,expected",
        [
            pytest.param("test_something", True, id="test_function"),
            pytest.param("test_", True, id="test_prefix"),
            pytest.param("setup", True, id="setup"),
            pytest.param("teardown", True, id="teardown"),
            pytest.param("setup_module", True, id="setup_module"),
            pytest.param("teardown_class", True, id="teardown_class"),
            pytest.param("__init__", True, id="init"),
            pytest.param("__str__", True, id="str"),
            pytest.param("__repr__", True, id="repr"),
        ],
    )
    def test_should_exclude(self, func_name: str, expected: bool):
        """Test functions that should be excluded."""
        assert should_exclude(func_name) is expected

    @pytest.mark.parametrize(
        "func_name",
        [
            pytest.param("process_data", id="process_data"),
            pytest.param("calculate_total", id="calculate_total"),
        ],
    )
    def test_should_not_exclude(self, func_name: str):
        """Test normal functions that should NOT be excluded."""
        assert should_exclude(func_name) is False


class TestIsPrivate:
    """Test private function detection."""

    @pytest.mark.parametrize(
        "func_name,expected",
        [
            pytest.param("_helper", True, id="single_underscore"),
            pytest.param("__private", True, id="double_underscore"),
            pytest.param("public", False, id="public"),
            pytest.param("test_something", False, id="test_function"),
        ],
    )
    def test_is_private(self, func_name: str, expected: bool):
        """Test private function detection."""
        assert is_private(func_name) is expected


class TestClassifyConfidence:
    """Test confidence classification."""

    @pytest.mark.parametrize(
        "func_name,ref_count,is_cli_command,expected",
        [
            pytest.param("some_command", 0, True, "excluded", id="cli_command"),
            pytest.param("test_something", 0, False, "excluded", id="test_function"),
            pytest.param("used_func", 1, False, "excluded", id="has_references"),
        ],
    )
    def test_classify_confidence_excluded(
        self, func_name: str, ref_count: int, is_cli_command: bool, expected: str
    ):
        """Test functions that should be excluded."""
        result = classify_confidence(func_name, ref_count, is_cli_command)
        assert result == expected

    @pytest.mark.parametrize(
        "func_name,ref_count,expected",
        [
            pytest.param("unused_func", 0, "high", id="normal_zero_refs"),
            pytest.param("_private_unused", 0, "medium", id="private_zero_refs"),
        ],
    )
    def test_classify_confidence_levels(
        self, func_name: str, ref_count: int, expected: str
    ):
        """Test confidence levels for unused functions."""
        result = classify_confidence(func_name, ref_count)
        assert result == expected


class TestIsDeadCode:
    """Test dead code detection."""

    @pytest.mark.parametrize(
        "func_name,ref_count,is_cli_command,expected_is_dead,reason_contains",
        [
            pytest.param(
                "some_command", 0, True, False, "CLI command", id="cli_command"
            ),
            pytest.param(
                "test_something",
                0,
                False,
                False,
                "Excluded pattern",
                id="test_function",
            ),
            pytest.param(
                "used_func", 1, False, False, "1 references", id="has_references"
            ),
        ],
    )
    def test_is_not_dead(
        self,
        func_name: str,
        ref_count: int,
        is_cli_command: bool,
        expected_is_dead: bool,
        reason_contains: str,
    ):
        """Test functions that should not be flagged as dead."""
        is_dead, reason = is_dead_code(func_name, ref_count, is_cli_command)
        assert is_dead is expected_is_dead
        assert reason_contains in reason

    @pytest.mark.parametrize(
        "func_name,ref_count,expected_confidence",
        [
            pytest.param("unused_func", 0, "high confidence", id="normal_zero_refs"),
            pytest.param(
                "_private_unused", 0, "medium confidence", id="private_zero_refs"
            ),
        ],
    )
    def test_is_dead(self, func_name: str, ref_count: int, expected_confidence: str):
        """Test functions that should be flagged as dead."""
        is_dead, reason = is_dead_code(func_name, ref_count)
        assert is_dead is True
        assert expected_confidence in reason


class TestGetRouterFunctions:
    """Test FastAPI router decorator detection."""

    def test_detects_router_post(self):
        """Test @router.post decorator detection."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
from fastapi import APIRouter

router = APIRouter()

@router.post("/events")
async def publish_event(request: dict) -> dict:
    return {"status": "ok"}
""")
            f.flush()
            file_path = f.name

        result = get_router_functions(file_path)
        assert "publish_event" in result
        Path(file_path).unlink()

    def test_detects_router_get(self):
        """Test @router.get decorator detection."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
from fastapi import APIRouter

router = APIRouter()

@router.get("/events")
async def list_events() -> list:
    return []
""")
            f.flush()
            file_path = f.name

        result = get_router_functions(file_path)
        assert "list_events" in result
        Path(file_path).unlink()

    def test_detects_app_post(self):
        """Test @app.post decorator detection."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
from fastapi import FastAPI

app = FastAPI()

@app.post("/webhook")
async def handle_webhook(request: dict) -> dict:
    return {"status": "ok"}
""")
            f.flush()
            file_path = f.name

        result = get_router_functions(file_path)
        assert "handle_webhook" in result
        Path(file_path).unlink()

    def test_no_decorator(self):
        """Test function without router decorator."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
async def regular_function() -> str:
    return "hello"
""")
            f.flush()
            file_path = f.name

        result = get_router_functions(file_path)
        assert result == set()
        Path(file_path).unlink()

    def test_classify_excludes_router_endpoint(self):
        """Test that classify_confidence excludes router endpoints."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
from fastapi import APIRouter

router = APIRouter()

@router.post("/events")
async def publish_event(request: dict) -> dict:
    return {"status": "ok"}
""")
            f.flush()
            file_path = f.name

        router_funcs = get_router_functions(file_path)
        confidence = classify_confidence("publish_event", 0, False, router_funcs)
        assert confidence == "excluded"
        Path(file_path).unlink()
