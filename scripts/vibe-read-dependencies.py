#!/usr/bin/env python3
"""
vibe3 inspect dependencies - 读取并输出 dependencies.toml 配置

用于 Shell 脚本和 Skills 获取配置驱动的依赖列表。
"""

import sys
import tomllib
from pathlib import Path
from typing import Any


def load_dependencies() -> dict[str, Any]:
    """加载 dependencies.toml 配置文件"""
    # 优先从项目根目录查找
    config_paths = [
        Path.cwd() / "config" / "dependencies.toml",
        Path(__file__).parent.parent / "config" / "dependencies.toml",
    ]

    for config_path in config_paths:
        if config_path.exists():
            with open(config_path, "rb") as f:
                return tomllib.load(f)

    raise FileNotFoundError("dependencies.toml not found")


def format_shell_output(config: dict[str, Any]) -> str:
    """输出 Shell 脚本可解析的格式"""
    lines = []

    # Essential tools
    if "tools" in config and "essential" in config["tools"]:
        lines.append("# ESSENTIAL_TOOLS")
        for tool in config["tools"]["essential"]:
            lines.append(f"{tool['name']}|{tool['check']}|{tool['install']}|{tool['description']}")

    # Optional tools - 支持嵌套分组结构
    lines.append("# OPTIONAL_TOOLS")
    if "tools" in config:
        # 遍历所有可能的分组
        for group_name in ["productivity", "alternative_ai", "development", "remote"]:
            if group_name in config["tools"]:
                group = config["tools"][group_name]
                if isinstance(group, dict) and "tools" in group:
                    for tool in group["tools"]:
                        lines.append(f"{tool['name']}|{tool['check']}|{tool['install']}|{tool['description']}")

    # API Keys
    if "api_keys" in config:
        if "essential" in config["api_keys"]:
            lines.append("# ESSENTIAL_KEYS")
            for key in config["api_keys"]["essential"]:
                lines.append(f"{key['name']}|{key['env_var']}|{key['description']}|{key['get_from']}")

        if "optional" in config["api_keys"]:
            lines.append("# OPTIONAL_KEYS")
            for key in config["api_keys"]["optional"]:
                lines.append(f"{key['name']}|{key['env_var']}|{key['description']}|{key['get_from']}")

    return "\n".join(lines)


def format_json_output(config: dict[str, Any]) -> str:
    """输出 JSON 格式（供 skill 使用）"""
    import json
    return json.dumps(config, indent=2)


def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="读取 dependencies.toml 配置")
    parser.add_argument(
        "--format",
        choices=["shell", "json", "summary"],
        default="summary",
        help="输出格式：shell（脚本用）、json（skill用）、summary（人类可读）"
    )

    args = parser.parse_args()

    try:
        config = load_dependencies()

        if args.format == "shell":
            print(format_shell_output(config))
        elif args.format == "json":
            print(format_json_output(config))
        else:  # summary
            print("✓ Dependencies Configuration Summary")
            # 统计可选工具数量（从嵌套分组）
            optional_count = 0
            if "tools" in config:
                for group_name in ["productivity", "alternative_ai", "development", "remote"]:
                    if group_name in config["tools"]:
                        group = config["tools"][group_name]
                        if isinstance(group, dict) and "tools" in group:
                            optional_count += len(group["tools"])
            print(f"  Tools: {len(config.get('tools', {}).get('essential', []))} essential, {optional_count} optional")
            print(f"  Plugins: {len(config.get('plugins', {}).get('global', {}).get('plugins', []))} global, {len(config.get('plugins', {}).get('project', {}).get('plugins', []))} project")
            print(f"  Skills: {len(config.get('skills', {}).get('essential_skills', []))} essential, {len(config.get('skills', {}).get('support_skills', []))} support")
            print(f"  Workflows: {len(config.get('workflows', {}))} defined")
            print(f"  API Keys: {len(config.get('api_keys', {}).get('essential', []))} essential, {len(config.get('api_keys', {}).get('optional', []))} optional")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing config: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()