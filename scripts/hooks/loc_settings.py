"""Shared LOC settings parser for hook scripts.

Uses only the Python standard library so hook scripts can run before uv sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocException:
    path: str
    limit: int
    reason: str = ""


@dataclass(frozen=True)
class LocSettings:
    single_file_default: int
    single_file_max: int
    total_v2_shell: int
    total_v3_python: int
    warning_threshold_percent: int
    last_reviewed: str
    code_paths_v2_shell: tuple[str, ...]
    code_paths_v3_python: tuple[str, ...]
    scripts_paths_v2_shell: tuple[str, ...]
    scripts_paths_v3_python: tuple[str, ...]
    test_paths_v2_shell: tuple[str, ...]
    test_paths_v3_python: tuple[str, ...]
    exceptions: tuple[LocException, ...]


def _normalize_value(raw: str) -> str:
    value = raw.split("#", 1)[0].strip()
    if not value:
        return ""
    if value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_settings(path: Path) -> tuple[dict[str, str], dict[str, list[str]], dict[str, list[dict[str, str]]]]:
    scalars: dict[str, str] = {}
    string_lists: dict[str, list[str]] = {}
    object_lists: dict[str, list[dict[str, str]]] = {}
    stack: list[tuple[int, str]] = []
    current_object_path: str | None = None
    current_object_indent = -1

    for raw_line in path.read_text().splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if current_object_path is not None and indent <= current_object_indent:
            current_object_path = None
            current_object_indent = -1

        content = _normalize_value(raw_line.strip())
        if not content:
            continue

        if content.startswith("- "):
            item = content[2:].strip()
            list_path = ".".join(part for _, part in stack)
            if ":" in item:
                key, raw_value = item.split(":", 1)
                obj = {key.strip(): _normalize_value(raw_value)}
                object_lists.setdefault(list_path, []).append(obj)
                current_object_path = list_path
                current_object_indent = indent
            else:
                string_lists.setdefault(list_path, []).append(_normalize_value(item))
            continue

        if ":" not in content:
            continue

        key, raw_value = content.split(":", 1)
        key = key.strip()
        value = _normalize_value(raw_value)

        if value:
            if current_object_path and indent > current_object_indent:
                object_lists[current_object_path][-1][key] = value
                continue

            path_key = ".".join([part for _, part in stack] + [key])
            scalars[path_key] = value
            continue

        stack.append((indent, key))

    return scalars, string_lists, object_lists


def load_loc_settings(config_path: str | None = None) -> LocSettings:
    # Try new path first, then fallback to old path
    if config_path is None:
        new_path = Path("config/v3/loc_limits.yaml")
        old_path = Path("config/loc_limits.yaml")
        if new_path.exists():
            config_path = str(new_path)
        elif old_path.exists():
            config_path = str(old_path)
        else:
            config_path = "config/v3/loc_limits.yaml"  # Default to new path
    scalars, string_lists, object_lists = _parse_settings(Path(config_path))
    exceptions = tuple(
        LocException(
            path=item["path"],
            limit=int(item["limit"]),
            reason=item.get("reason", ""),
        )
        for item in object_lists.get("code_limits.single_file_loc.exceptions", [])
        if item.get("path") and item.get("limit")
    )
    seen_paths: set[str] = set()
    for entry in exceptions:
        if entry.path in seen_paths:
            raise ValueError(f"Duplicate LOC exception path: {entry.path}")
        seen_paths.add(entry.path)
    return LocSettings(
        single_file_default=int(scalars.get("code_limits.single_file_loc.default", "300")),
        single_file_max=int(scalars.get("code_limits.single_file_loc.max", "400")),
        total_v2_shell=int(scalars.get("code_limits.total_file_loc.v2_shell", "4000")),
        total_v3_python=int(scalars.get("code_limits.total_file_loc.v3_python", "32000")),
        warning_threshold_percent=int(scalars.get("code_limits.total_file_loc.warning_threshold_percent", "90")),
        last_reviewed=scalars.get("code_limits.total_file_loc.last_reviewed", ""),
        code_paths_v2_shell=tuple(string_lists.get("code_limits.code_paths.v2_shell", [])),
        code_paths_v3_python=tuple(string_lists.get("code_limits.code_paths.v3_python", [])),
        scripts_paths_v2_shell=tuple(string_lists.get("code_limits.scripts_paths.v2_shell", [])),
        scripts_paths_v3_python=tuple(string_lists.get("code_limits.scripts_paths.v3_python", [])),
        test_paths_v2_shell=tuple(string_lists.get("code_limits.test_paths.v2_shell", [])),
        test_paths_v3_python=tuple(string_lists.get("code_limits.test_paths.v3_python", [])),
        exceptions=exceptions,
    )


def find_exception(exceptions: tuple[LocException, ...], relative_path: str) -> LocException | None:
    for entry in exceptions:
        if entry.path == relative_path:
            return entry
    return None


def is_in_warning_zone(current_loc: int, limit: int, warning_threshold_percent: int) -> bool:
    """Check if current LOC is in warning zone (between threshold and limit)."""
    warning_threshold = limit * warning_threshold_percent / 100
    return warning_threshold <= current_loc < limit


def iter_files(
    paths: tuple[str, ...],
    *,
    suffixes: tuple[str, ...],
    test_only: bool = False,
    recursive: bool = True,
) -> list[Path]:
    collected: dict[str, Path] = {}
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            iterator = path.rglob("*") if recursive else path.glob("*")
            for file_path in iterator:
                if not file_path.is_file():
                    continue
                if suffixes and file_path.suffix not in suffixes:
                    continue
                if test_only and not file_path.name.startswith("test_"):
                    continue
                if "__pycache__" in file_path.parts:
                    continue
                collected[file_path.as_posix()] = file_path
            continue

        if not path.is_file():
            continue
        if suffixes and path.suffix and path.suffix not in suffixes:
            continue
        if test_only and not path.name.startswith("test_"):
            continue
        collected[path.as_posix()] = path

    return [collected[key] for key in sorted(collected)]
