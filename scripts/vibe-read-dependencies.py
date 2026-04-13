#!/usr/bin/env python3
"""
vibe3 inspect dependencies - 读取并输出 dependencies.toml 配置

用于 Shell 脚本（vibe doctor / vibe keys）获取配置驱动的依赖列表。
"""

import sys
import tomllib
from pathlib import Path
from typing import Any


def load_dependencies() -> dict[str, Any]:
    """加载 dependencies.toml 配置文件"""
    # 优先从项目根目录查找，fallback 到脚本相对路径
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
    """输出 Shell 脚本可解析的格式（固定段名）"""
    lines = []

    # REQUIRED_TOOLS
    lines.append("# REQUIRED_TOOLS")
    if "tools" in config and "required" in config["tools"]:
        for tool in config["tools"]["required"]:
            lines.append(f"{tool['name']}|{tool['check']}|{tool['install']}|{tool['description']}")

    # OPTIONAL_TOOLS
    lines.append("# OPTIONAL_TOOLS")
    if "tools" in config and "optional" in config["tools"]:
        for tool in config["tools"]["optional"]:
            lines.append(f"{tool['name']}|{tool['check']}|{tool['install']}|{tool['description']}")

    # REQUIRED_PLUGINS
    lines.append("# REQUIRED_PLUGINS")
    if "plugins" in config and "required" in config["plugins"]:
        for plugin in config["plugins"]["required"]:
            scope = plugin.get("scope", "")
            lines.append(f"{plugin['name']}|{scope}|{plugin['description']}")

    # RECOMMENDED_PLUGINS
    lines.append("# RECOMMENDED_PLUGINS")
    if "plugins" in config and "recommended" in config["plugins"]:
        for plugin in config["plugins"]["recommended"]:
            scope = plugin.get("scope", "")
            lines.append(f"{plugin['name']}|{scope}|{plugin['description']}")

    # OPTIONAL_PLUGINS
    lines.append("# OPTIONAL_PLUGINS")
    if "plugins" in config and "optional" in config["plugins"]:
        for plugin in config["plugins"]["optional"]:
            scope = plugin.get("scope", "")
            lines.append(f"{plugin['name']}|{scope}|{plugin['description']}")

    # REQUIRED_KEYS
    lines.append("# REQUIRED_KEYS")
    if "keys" in config and "required" in config["keys"]:
        for key in config["keys"]["required"]:
            note = key.get("note", "")
            used_by = ",".join(key.get("used_by", []))
            resolution = ",".join(key.get("resolution", []))
            activation = key.get("activation", "always")
            lines.append(
                f"{key['name']}|{key['env_var']}|{key['description']}|{key['get_from']}|{note}|{used_by}|{resolution}|{activation}"
            )

    # OPTIONAL_KEYS
    lines.append("# OPTIONAL_KEYS")
    if "keys" in config and "optional" in config["keys"]:
        for key in config["keys"]["optional"]:
            note = key.get("note", "")
            used_by = ",".join(key.get("used_by", []))
            resolution = ",".join(key.get("resolution", []))
            activation = key.get("activation", "any_used")
            lines.append(
                f"{key['name']}|{key['env_var']}|{key['description']}|{key['get_from']}|{note}|{used_by}|{resolution}|{activation}"
            )

    return "\n".join(lines)


def format_summary_output(config: dict[str, Any]) -> str:
    """输出统计摘要（工具、插件和密钥数量）"""
    lines = []

    # Tools统计
    if "tools" in config:
        required_count = len(config["tools"].get("required", []))
        optional_count = len(config["tools"].get("optional", []))
        lines.append(f"Tools: {required_count} required, {optional_count} optional")

    # Keys统计
    if "keys" in config:
        required_count = len(config["keys"].get("required", []))
        optional_count = len(config["keys"].get("optional", []))
        lines.append(f"Keys: {required_count} required, {optional_count} optional")

    # Plugins统计
    if "plugins" in config:
        required_count = len(config["plugins"].get("required", []))
        recommended_count = len(config["plugins"].get("recommended", []))
        optional_count = len(config["plugins"].get("optional", []))
        lines.append(
            f"Plugins: {required_count} required, {recommended_count} recommended, {optional_count} optional"
        )

    return "\n".join(lines)


def format_summary_output(config: dict[str, Any]) -> str:
    """输出统计摘要（工具和密钥数量）"""
    lines = []

    # Tools统计
    if "tools" in config:
        required_count = len(config["tools"].get("required", []))
        optional_count = len(config["tools"].get("optional", []))
        lines.append(f"Tools: {required_count} required, {optional_count} optional")

    # Keys统计
    if "keys" in config:
        required_count = len(config["keys"].get("required", []))
        optional_count = len(config["keys"].get("optional", []))
        lines.append(f"Keys: {required_count} required, {optional_count} optional")

    return "\n".join(lines)


def format_json_output(config: dict[str, Any]) -> str:
    """输出 JSON 格式（供调试使用）"""
    import json
    return json.dumps(config, indent=2)


def main():
    """主入口"""
    import argparse

    parser = argparse.ArgumentParser(description="读取 dependencies.toml 配置")
    parser.add_argument(
        "--format",
        choices=["shell", "json", "summary"],
        default="shell",
        help="输出格式：shell（脚本用）、json（调试用）、summary（统计摘要）",
    )

    args = parser.parse_args()

    try:
        config = load_dependencies()

        if args.format == "shell":
            print(format_shell_output(config))
        elif args.format == "summary":
            print(format_summary_output(config))
        else:  # json
            print(format_json_output(config))

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing config: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
