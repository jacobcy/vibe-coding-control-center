"""Minimal Serena client for validated definition/reference evidence."""

from __future__ import annotations

import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Any

from loguru import logger

from vibe3.exceptions import SerenaError


class SerenaClient:
    """Narrow wrapper around the two Serena tools inspect symbols needs."""

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = project_root
        self._agent: Any = None

    def _get_agent(self) -> Any:
        if self._agent is None:
            try:
                from serena.agent import SerenaAgent  # type: ignore[import-untyped]

                self._agent = SerenaAgent(project=self.project_root)
            except Exception as exc:
                raise SerenaError("create agent", str(exc)) from exc
        return self._agent

    def _execute(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute one Serena tool without contaminating structured stdout."""
        try:
            agent = self._get_agent()
            tool = agent.get_tool_by_name(tool_name)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                result = agent.execute_task(lambda: tool.apply(**kwargs))
            return json.loads(result)
        except Exception as exc:
            logger.bind(
                external="serena",
                operation=tool_name,
                error=str(exc),
            ).error("Serena tool failed")
            raise SerenaError(tool_name, str(exc)) from exc

    def find_symbol(self, name_path: str, relative_file: str) -> Any:
        """Find a symbol definition constrained to one source file."""
        return self._execute(
            "find_symbol",
            name_path_pattern=name_path,
            relative_path=relative_file,
            include_body=False,
        )

    def find_references(self, name_path: str, relative_file: str) -> Any:
        """Find static referencing symbols for an exact definition identity."""
        return self._execute(
            "find_referencing_symbols",
            name_path=name_path,
            relative_path=relative_file,
        )
