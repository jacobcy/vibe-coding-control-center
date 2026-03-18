"""Inspection data models.

This module provides data models for code inspection output,
supporting hierarchical call tree visualization.

Reference: docs/v3/design/trace-inspect-output-format.md
"""

from typing import Any

import yaml
from pydantic import BaseModel, Field


class CallNode(BaseModel):
    """A node in the call tree.

    Attributes:
        name: Function/method name
        line: Line number in the source file
        calls: List of child call nodes
    """

    name: str = Field(..., description="Function/method name")
    line: int = Field(..., description="Line number")
    calls: list["CallNode"] = Field(
        default_factory=list, description="Child call nodes"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary recursively.

        Returns:
            Dictionary representation with nested calls
        """
        return {
            "name": self.name,
            "line": self.line,
            "calls": [call.to_dict() for call in self.calls] if self.calls else [],
        }


class CommandInspection(BaseModel):
    """Command inspection model with hierarchical call tree.

    Attributes:
        command: Command name (e.g., "pr show")
        file: Source file path
        call_depth: Maximum call depth
        call_tree: Root-level call nodes
    """

    command: str = Field(..., description="Command name")
    file: str = Field(..., description="Source file path")
    call_depth: int = Field(..., description="Maximum call depth")
    call_tree: list[CallNode] = Field(
        default_factory=list, description="Call tree nodes"
    )

    def to_yaml(self) -> str:
        """Convert to YAML string.

        Returns:
            YAML formatted string with hierarchical structure

        Example:
            >>> inspection = CommandInspection(...)
            >>> print(inspection.to_yaml())
            command: pr show
            file: src/vibe3/commands/pr.py
            call_depth: 16
            call_tree:
              - caller: show
                line: 84
                calls:
                  - name: app.command
                    line: 84
        """
        data = {
            "command": self.command,
            "file": self.file,
            "call_depth": self.call_depth,
            "call_tree": [node.to_dict() for node in self.call_tree],
        }
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON formatted string

        Example:
            >>> inspection = CommandInspection(...)
            >>> print(inspection.to_json())
            {"command": "pr show", "file": "...", "call_tree": [...]}
        """
        return self.model_dump_json(indent=2)

    def to_tree(self) -> str:
        """Convert to ASCII tree format.

        Returns:
            ASCII tree string with hierarchy visualization

        Example:
            >>> inspection = CommandInspection(...)
            >>> print(inspection.to_tree())
            pr show (src/vibe3/commands/pr.py:84)
            ├─ app.command (L84)
            ├─ setup_logging (L95)
            └─ PRService (L103)
               └─ service.get_pr (L104)
        """
        first_line = self.call_tree[0].line if self.call_tree else 0
        lines = [f"{self.command} ({self.file}:{first_line})"]
        self._build_tree(lines, self.call_tree, "")
        return "\n".join(lines)

    def _build_tree(self, lines: list[str], nodes: list[CallNode], prefix: str) -> None:
        """Build tree lines recursively.

        Args:
            lines: Output lines list
            nodes: Current level nodes
            prefix: Current prefix string
        """
        for i, node in enumerate(nodes):
            is_last = i == len(nodes) - 1
            connector = "└─ " if is_last else "├─ "
            lines.append(f"{prefix}{connector}{node.name} (L{node.line})")

            if node.calls:
                new_prefix = prefix + ("    " if is_last else "│   ")
                self._build_tree(lines, node.calls, new_prefix)

    def to_mermaid(self) -> str:
        """Convert to Mermaid flowchart code.

        Returns:
            Mermaid flowchart code string

        Example:
            >>> inspection = CommandInspection(...)
            >>> print(inspection.to_mermaid())
            ```mermaid
            graph TD
                A[show:84] --> B[app.command:84]
                A --> C[setup_logging:95]
            ```
        """
        lines = ["graph TD"]
        self._build_mermaid(lines, self.call_tree, "A")
        return "```mermaid\n" + "\n".join(lines) + "\n```"

    def _build_mermaid(
        self, lines: list[str], nodes: list[CallNode], parent_id: str
    ) -> None:
        """Build Mermaid graph lines recursively.

        Args:
            lines: Output lines list
            nodes: Current level nodes
            parent_id: Parent node ID
        """
        for i, node in enumerate(nodes):
            node_id = f"{parent_id}{i}"
            label = f"{node.name}:{node.line}"
            lines.append(f'    {node_id}["{label}"]')
            lines.append(f"    {parent_id} --> {node_id}")

            if node.calls:
                self._build_mermaid(lines, node.calls, node_id)
