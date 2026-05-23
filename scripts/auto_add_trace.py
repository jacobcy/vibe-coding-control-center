#!/usr/bin/env python3
"""自动给 Service 和 Client 层添加 trace 装饰器。

策略：
1. 在 common.py 添加 trace_method 装饰器（支持自动推断 class.method 名）
2. 扫描 services/ 和 clients/ 目录
3. 自动给所有公共方法添加装饰器

使用：
    uv run python scripts/auto_add_trace.py --dry-run  # 预览修改
    uv run python scripts/auto_add_trace.py            # 实际修改
"""

import argparse
import re
from pathlib import Path


def add_trace_decorator_to_file(file_path: Path, layer: str) -> list[str]:
    """给文件中的公共方法添加 trace 装饰器。

    Args:
        file_path: Python 文件路径
        layer: 层级名称（"service" 或 "client"）

    Returns:
        修改后的文件内容行列表
    """
    content = file_path.read_text()
    lines = content.split("\n")

    new_lines = []
    i = 0
    has_trace_import = False
    import_inserted = False

    # 根据 layer 决定类名后缀
    valid_suffixes = {
        "service": ["Service", "Usecase"],
        "client": ["Client"],
    }[layer]

    # 检查是否已有 import
    for line in lines:
        if "from vibe3.commands.common import" in line and "trace_method" in line:
            has_trace_import = True
            break

    while i < len(lines):
        line = lines[i]

        # 添加 import 语句（在第一个 from vibe3 之后）
        if not import_inserted and not has_trace_import and line.startswith("from vibe3"):
            new_lines.append(line)
            # 在下一个空行之前找合适的插入点
            j = i + 1
            while j < len(lines) and lines[j].startswith(("from ", "import ")):
                new_lines.append(lines[j])
                j += 1
            # 添加 trace_method import
            new_lines.append(
                "from vibe3.commands.common import trace_method"
            )
            new_lines.append("")
            i = j
            import_inserted = True
            continue

        # 检测类定义
        class_match = re.match(r'^class (\w+).*:', line)
        if class_match:
            class_name = class_match.group(1)

            # 只处理符合命名规范的类
            if not any(class_name.endswith(suffix) for suffix in valid_suffixes):
                new_lines.append(line)
                i += 1
                continue

            new_lines.append(line)
            i += 1

            # 在类方法中添加装饰器
            while i < len(lines):
                current_line = lines[i]

                # 检测公共方法定义（不以 _ 开头）
                method_match = re.match(r'^(\s*)def (\w+)\(', current_line)
                if method_match:
                    indent = method_match.group(1)
                    method_name = method_match.group(2)

                    # 跳过已有装饰器的方法
                    if i > 0 and '@' in lines[i - 1]:
                        new_lines.append(current_line)
                        i += 1
                        continue

                    # 跳过私有方法
                    if method_name.startswith('_'):
                        new_lines.append(current_line)
                        i += 1
                        continue

                    # 添加装饰器
                    trace_name = f"{class_name}.{method_name}"
                    new_lines.append(f'{indent}@trace_method("{trace_name}", layer="{layer}")')
                    new_lines.append(current_line)
                    i += 1
                    continue

                # 检测下一个类定义或文件结束
                if re.match(r'^class \w+', current_line) or i == len(lines) - 1:
                    break

                new_lines.append(current_line)
                i += 1

            continue

        new_lines.append(line)
        i += 1

    return new_lines


def main() -> None:
    parser = argparse.ArgumentParser(description="自动添加 trace 装饰器")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不修改文件")
    args = parser.parse_args()

    base_path = Path(__file__).parent.parent / "src" / "vibe3"

    # 定义需要处理的目录和层级
    targets = [
        (base_path / "services", "service"),
        (base_path / "clients", "client"),
    ]

    for target_dir, layer in targets:
        if not target_dir.exists():
            print(f"⚠️  目录不存在: {target_dir}")
            continue

        for py_file in target_dir.glob("*.py"):
            # 跳过 __init__.py 和 protocols.py
            if py_file.name in ["__init__.py", "protocols.py"]:
                continue

            print(f"处理: {py_file.relative_to(base_path)}")

            new_lines = add_trace_decorator_to_file(py_file, layer)
            new_content = "\n".join(new_lines)

            if args.dry_run:
                print("  [DRY RUN] 会修改此文件")
                # 显示差异（查找添加装饰器的行）
                old_lines = py_file.read_text().split("\n")
                for idx, (old, new) in enumerate(zip(old_lines, new_lines)):
                    if old != new and "@trace_method" in new:
                        # 显示装饰器及其后的方法定义
                        print(f"  - {old_lines[idx] if idx < len(old_lines) else ''}")
                        print(f"  + {new}")
                        if idx + 1 < len(new_lines):
                            print(f"  + {new_lines[idx + 1]}")
            else:
                py_file.write_text(new_content)
                print(f"  ✓ 已修改")


if __name__ == "__main__":
    main()
