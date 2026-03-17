"""Serena client for symbol-level code analysis."""

import json
import sys
from pathlib import Path
from typing import Union

from loguru import logger

# Add lib to path for Vibe3Store
lib_path = Path(__file__).parent.parent.parent.parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))


class SerenaClientError(Exception):
    """Serena client error."""

    pass


FUNCTION_KIND = 12


def extract_function_names(payload: dict[str, Union[str, int, list]]) -> list[str]:
    """Extract function names from Serena symbol overview.

    Args:
        payload: Serena symbol overview payload

    Returns:
        List of unique function names
    """
    names: list[str] = []

    def walk(node: dict[str, Union[str, int, list]] | list) -> None:
        if isinstance(node, dict):
            if node.get("kind") == FUNCTION_KIND:
                name = node.get("name_path") or node.get("name")
                if isinstance(name, str):
                    names.append(name)
            functions = node.get("Function")
            if isinstance(functions, list):
                for item in functions:
                    if isinstance(item, str):
                        names.append(item)
                    elif isinstance(item, dict):
                        nested_name = item.get("name_path") or item.get("name")
                        if isinstance(nested_name, str):
                            names.append(nested_name)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)

    # Unique preserving order
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def count_references(payload: dict[str, Union[str, int, list]]) -> int:
    """Count references in Serena reference payload.

    Args:
        payload: Serena reference payload

    Returns:
        Number of references
    """
    if isinstance(payload, list):
        return len(payload)

    count = 0

    def walk(node: dict[str, Union[str, int, list]] | list) -> None:
        nonlocal count
        if isinstance(node, dict):
            if isinstance(node.get("name_path"), str):
                count += 1
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return count


class SerenaClient:
    """Client for Serena agent operations."""

    def __init__(self, project_root: str = ".") -> None:
        """Initialize Serena client.

        Args:
            project_root: Project root directory
        """
        self.project_root = project_root
        self._agent = None
        logger.debug("Serena client initialized", project_root=project_root)

    def _get_agent(self):  # type: ignore[no-untyped-def]
        """Get or create Serena agent.

        Returns:
            Serena agent instance

        Raises:
            SerenaClientError: If agent creation fails
        """
        if self._agent is None:
            try:
                from serena.agent import SerenaAgent  # type: ignore[import-not-found]

                self._agent = SerenaAgent(project=self.project_root)
                logger.debug("Serena agent created")
            except Exception as e:
                logger.exception("Failed to create Serena agent")
                raise SerenaClientError(f"Failed to create Serena agent: {e}") from e
        return self._agent

    def get_symbols_overview(
        self, relative_file: str
    ) -> dict[str, Union[str, int, list]]:
        """Get symbols overview for a file.

        Args:
            relative_file: Relative file path

        Returns:
            Symbol overview dict

        Raises:
            SerenaClientError: If operation fails
        """
        try:
            agent = self._get_agent()
            tool = agent.get_tool_by_name("get_symbols_overview")
            result = agent.execute_task(lambda: tool.apply(relative_path=relative_file))
            return json.loads(result)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(
                "Failed to get symbols overview",
                file=relative_file,
                error=str(e),
            )
            raise SerenaClientError(f"get_symbols_overview failed: {e}") from e

    def find_references(
        self, name_path: str, relative_file: str
    ) -> dict[str, Union[str, int, list]]:
        """Find references to a symbol.

        Args:
            name_path: Symbol name path
            relative_file: Relative file path

        Returns:
            References dict

        Raises:
            SerenaClientError: If operation fails
        """
        try:
            agent = self._get_agent()
            tool = agent.get_tool_by_name("find_referencing_symbols")
            result = agent.execute_task(
                lambda: tool.apply(name_path=name_path, relative_path=relative_file)
            )
            return json.loads(result)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(
                "Failed to find references",
                symbol=name_path,
                file=relative_file,
                error=str(e),
            )
            raise SerenaClientError(f"find_referencing_symbols failed: {e}") from e
