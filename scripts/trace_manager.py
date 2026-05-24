#!/usr/bin/env python3
"""Trace Manager - 双向管理 services 层 @trace_method 装饰器。

使用：
    uv run python scripts/trace_manager.py --add --dry-run    # 预览插入
    uv run python scripts/trace_manager.py --add              # 执行插入
    uv run python scripts/trace_manager.py --remove --dry-run # 预览删除
    uv run python scripts/trace_manager.py --remove           # 执行删除
"""

import argparse
import re
from pathlib import Path

SERVICE_SUFFIXES = ["Service", "Usecase"]


def add_trace_decorator(lines: list[str]) -> list[str]:
    """给 services 层公共方法添加 trace 装饰器。"""
    new_lines = []
    i = 0
    has_trace_import = any(
        "from vibe3.observability.trace_method import trace_method" in line
        for line in lines
    )
    import_inserted = has_trace_import

    while i < len(lines):
        line = lines[i]

        if not import_inserted and line.startswith("from vibe3"):
            new_lines.append(line)
            j = i + 1
            while j < len(lines) and lines[j].startswith(("from ", "import ")):
                new_lines.append(lines[j])
                j += 1
            new_lines.append("from vibe3.observability.trace_method import trace_method")
            new_lines.append("")
            i = j
            import_inserted = True
            continue

        class_match = re.match(r'^class (\w+).*:', line)
        if class_match:
            class_name = class_match.group(1)

            if not any(class_name.endswith(suffix) for suffix in SERVICE_SUFFIXES):
                new_lines.append(line)
                i += 1
                continue

            new_lines.append(line)
            i += 1

            while i < len(lines):
                current_line = lines[i]
                method_match = re.match(r'^(\s*)def (\w+)\(', current_line)

                if method_match:
                    indent, method_name = method_match.groups()

                    if i > 0 and '@' in lines[i - 1]:
                        new_lines.append(current_line)
                        i += 1
                        continue

                    if method_name.startswith('_'):
                        new_lines.append(current_line)
                        i += 1
                        continue

                    trace_name = f"{class_name}.{method_name}"
                    new_lines.append(f'{indent}@trace_method("{trace_name}", layer="service")')
                    new_lines.append(current_line)
                    i += 1
                    continue

                if re.match(r'^class \w+', current_line) or i == len(lines) - 1:
                    break

                new_lines.append(current_line)
                i += 1
            continue

        new_lines.append(line)
        i += 1

    return new_lines


def remove_trace_decorator(lines: list[str]) -> list[str]:
    """移除文件中的 @trace_method 装饰器。"""
    return [
        line for line in lines
        if "from vibe3.observability.trace_method import trace_method" not in line
        and not re.match(r'^\s*@trace_method\(', line)
    ]


def process_file(file_path: Path, mode: str, dry_run: bool) -> bool:
    """处理单个文件，返回是否有修改。"""
    content = file_path.read_text()
    lines = content.split("\n")

    new_lines = add_trace_decorator(lines) if mode == "add" else remove_trace_decorator(lines)
    new_content = "\n".join(new_lines)

    if new_content == content:
        return False

    if dry_run:
        print(f"  [DRY RUN] 会修改: {file_path.name}")
        for idx, (old, new) in enumerate(zip(lines, new_lines)):
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
    parser = argparse.ArgumentParser(description="管理 services 层 @trace_method 装饰器")
    parser.add_argument("--add", action="store_true", help="插入装饰器")
    parser.add_argument("--remove", action="store_true", help="删除装饰器")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不修改文件")
    args = parser.parse_args()

    if not args.add and not args.remove:
        parser.error("必须指定 --add 或 --remove")
    if args.add and args.remove:
        parser.error("--add 和 --remove 不能同时使用")

    mode = "add" if args.add else "remove"
    base_path = Path(__file__).parent.parent / "src" / "vibe3"
    services_dir = base_path / "services"

    if not services_dir.exists():
        print(f"❌ 目录不存在: {services_dir}")
        return

    modified_count = 0
    for py_file in services_dir.glob("*.py"):
        if py_file.name in ["__init__.py", "protocols.py"]:
            continue

        if mode == "remove" and "@trace_method" not in py_file.read_text():
            continue

        print(f"处理: {py_file.relative_to(base_path)}")
        if process_file(py_file, mode, args.dry_run):
            modified_count += 1

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}共修改 {modified_count} 个文件")


if __name__ == "__main__":
    main()
