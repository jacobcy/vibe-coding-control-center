#!/usr/bin/env python3
"""Trace Manager - 双向管理不同模块的 @trace_method 装饰器。

使用：
    uv run python scripts/trace_manager.py --add --module services --dry-run
    uv run python scripts/trace_manager.py --add --module clients
    uv run python scripts/trace_manager.py --add --module all
    uv run python scripts/trace_manager.py --remove --module services
"""

import argparse
import re
from pathlib import Path
from typing import Sequence, TypedDict


class LayerConfig(TypedDict):
    dir: str
    suffixes: list[str]
    layer_name: str


LAYER_CONFIG: dict[str, LayerConfig] = {
    "services": {
        "dir": "services",
        "suffixes": ["Service", "Usecase"],
        "layer_name": "service",
    },
    "clients": {
        "dir": "clients",
        "suffixes": ["Client", "Repo", "Ops"],
        "layer_name": "client",
    },
    "agents": {
        "dir": "agents",
        "suffixes": ["Agent", "Runner", "Executor"],
        "layer_name": "agent",
    },
    "analysis": {
        "dir": "analysis",
        "suffixes": ["Analyzer", "Service"],
        "layer_name": "analysis",
    },
    "orchestra": {
        "dir": "orchestra",
        "suffixes": ["Manager", "Service", "Scheduler"],
        "layer_name": "orchestra",
    },
    "execution": {
        "dir": "execution",
        "suffixes": ["Executor", "Runner", "Handler"],
        "layer_name": "execution",
    },
    "adapters": {
        "dir": "adapters",
        "suffixes": ["Adapter", "Wrapper"],
        "layer_name": "adapter",
    },
    "environment": {
        "dir": "environment",
        "suffixes": ["Manager", "Service"],
        "layer_name": "environment",
    },
    "prompts": {
        "dir": "prompts",
        "suffixes": ["Service"],
        "layer_name": "prompts",
    },
    "domain": {
        "dir": "domain",
        "suffixes": ["Service", "Gate"],
        "layer_name": "domain",
    },
    "runtime": {
        "dir": "runtime",
        "suffixes": ["Executor", "Manager"],
        "layer_name": "runtime",
    },
}


def _has_target_class(lines: list[str], suffixes: Sequence[str]) -> bool:
    """文件中是否存在 suffix 匹配的 class？"""
    for line in lines:
        match = re.match(r"^class (\w+).*:", line)
        if match and any(match.group(1).endswith(s) for s in suffixes):
            return True
    return False


def _find_import_insert_index(lines: list[str]) -> int:
    """返回应在哪一行之前插入新的 module-level import。

    扫描所有顶层（无缩进）import 语句，找到最后一个的结束行。
    支持多行 import（带括号）。这样可以跳过 ``if TYPE_CHECKING:`` 块
    内的缩进 import，避免插入位置错位或漏插。
    """
    last_after = -1
    i = 0
    while i < len(lines):
        line = lines[i]
        is_top_level = bool(line) and not line[0].isspace()
        if is_top_level and (line.startswith("from ") or line.startswith("import ")):
            paren_count = line.count("(") - line.count(")")
            j = i + 1
            while j < len(lines) and paren_count > 0:
                paren_count += lines[j].count("(") - lines[j].count(")")
                j += 1
            last_after = j
            i = j
        else:
            i += 1
    return last_after


def add_trace_decorator(
    lines: list[str], layer_name: str, suffixes: list[str]
) -> list[str]:
    """给匹配 suffix 的 class 公共方法添加 trace 装饰器。

    无匹配 class 的文件直接返回原内容，避免插入 dead import。
    支持 ``@staticmethod`` / ``@classmethod`` — trace 装饰器插在它们之下。
    """
    if not _has_target_class(lines, suffixes):
        return lines

    has_trace_import = any(
        "from vibe3.observability.trace_method import trace_method" in line
        for line in lines
    )

    if has_trace_import:
        working = list(lines)
    else:
        insert_at = _find_import_insert_index(lines)
        if insert_at < 0:
            insert_at = 0
        working = (
            list(lines[:insert_at])
            + ["from vibe3.observability.trace_method import trace_method"]
            + list(lines[insert_at:])
        )

    new_lines: list[str] = []
    i = 0
    while i < len(working):
        line = working[i]
        class_match = re.match(r"^class (\w+).*:", line)
        if class_match:
            class_name = class_match.group(1)

            if not any(class_name.endswith(suffix) for suffix in suffixes):
                new_lines.append(line)
                i += 1
                continue

            new_lines.append(line)
            i += 1

            while i < len(working):
                current_line = working[i]
                method_match = re.match(r"^(\s*)def (\w+)\(", current_line)

                if method_match:
                    indent, method_name = method_match.groups()

                    if method_name.startswith("_"):
                        new_lines.append(current_line)
                        i += 1
                        continue

                    # Scan all preceding decorators (e.g. @staticmethod) for
                    # an existing @trace_method to avoid double-wrapping.
                    k = len(new_lines) - 1
                    already_traced = False
                    while k >= 0 and new_lines[k].strip().startswith("@"):
                        if "@trace_method" in new_lines[k]:
                            already_traced = True
                            break
                        k -= 1
                    if already_traced:
                        new_lines.append(current_line)
                        i += 1
                        continue

                    trace_name = f"{class_name}.{method_name}"
                    new_lines.append(
                        f'{indent}@trace_method("{trace_name}", layer="{layer_name}")'
                    )
                    new_lines.append(current_line)
                    i += 1
                    continue

                if re.match(r"^class \w+", current_line) or i == len(working) - 1:
                    break

                new_lines.append(current_line)
                i += 1
            continue

        new_lines.append(line)
        i += 1

    return new_lines


def remove_trace_decorator(lines: list[str]) -> list[str]:
    """移除文件中的 @trace_method 装饰器（支持多行）。"""
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if "from vibe3.observability.trace_method import trace_method" in line:
            i += 1
            continue

        if re.match(r"^\s*@trace_method\(", line):
            paren_count = line.count("(") - line.count(")")
            i += 1
            while i < len(lines) and paren_count > 0:
                paren_count += lines[i].count("(") - lines[i].count(")")
                i += 1
            continue

        new_lines.append(line)
        i += 1

    return new_lines


def process_file(
    file_path: Path, mode: str, dry_run: bool, layer_name: str, suffixes: list[str]
) -> bool:
    """处理单个文件，返回是否有修改。"""
    content = file_path.read_text()
    lines = content.split("\n")

    new_lines = (
        add_trace_decorator(lines, layer_name, suffixes)
        if mode == "add"
        else remove_trace_decorator(lines)
    )
    new_content = "\n".join(new_lines)

    if new_content == content:
        return False

    if dry_run:
        print(f"  [DRY RUN] 会修改: {file_path.name}")
        for old, new in zip(lines, new_lines):
            if old != new:
                if mode == "add" and "@trace_method" in new:
                    print(f"    + {new}")
                elif mode == "remove" and "@trace_method" in old:
                    print(f"    - {old}")
    else:
        file_path.write_text(new_content)
        print(f"  ✓ 已修改: {file_path.name}")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="管理不同模块的 @trace_method 装饰器")
    parser.add_argument("--add", action="store_true", help="插入装饰器")
    parser.add_argument("--remove", action="store_true", help="删除装饰器")
    parser.add_argument(
        "--module",
        choices=list(LAYER_CONFIG.keys()) + ["all"],
        default="services",
        help=f"目标模块: {', '.join(LAYER_CONFIG.keys())}, 或 all (默认: services)",
    )
    parser.add_argument("--dry-run", action="store_true", help="只预览，不修改文件")
    args = parser.parse_args()

    if not args.add and not args.remove:
        parser.error("必须指定 --add 或 --remove")
    if args.add and args.remove:
        parser.error("--add 和 --remove 不能同时使用")

    mode = "add" if args.add else "remove"
    base_path = Path(__file__).parent.parent / "src" / "vibe3"

    modules = list(LAYER_CONFIG.keys()) if args.module == "all" else [args.module]

    total_modified = 0
    for module in modules:
        config = LAYER_CONFIG[module]
        target_dir = base_path / config["dir"]

        if not target_dir.exists():
            print(f"❌ 目录不存在: {target_dir}")
            continue

        print(f"\n处理模块: {module} ({config['dir']}/)")
        modified_count = 0
        for py_file in target_dir.glob("*.py"):
            if py_file.name in ["__init__.py", "protocols.py"]:
                continue

            if mode == "remove" and "trace_method" not in py_file.read_text():
                continue

            if process_file(
                py_file, mode, args.dry_run, config["layer_name"], config["suffixes"]
            ):
                modified_count += 1

        print(f"  {'[DRY RUN] ' if args.dry_run else ''}修改 {modified_count} 个文件")
        total_modified += modified_count

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}总计修改 {total_modified} 个文件")


if __name__ == "__main__":
    main()
