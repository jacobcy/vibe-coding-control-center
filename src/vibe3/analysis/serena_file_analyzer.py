"""File analysis functions for Serena service."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from loguru import logger

from vibe3.clients.serena_client import (
    count_references,
    extract_function_names,
)
from vibe3.exceptions import SerenaError


def analyze_file(
    relative_file: str,
    client: Any,
    is_cli_file_func: Any,
) -> dict:
    """Analyze symbols in a file.

    Args:
        relative_file: Relative file path
        client: Serena client instance
        is_cli_file_func: Function to check if file is CLI module

    Returns:
        File analysis dict with symbols and references

    Raises:
        SerenaError: If analysis fails
    """
    logger.bind(
        domain="serena",
        action="analyze_file",
        file=relative_file,
    ).info("Analyzing file")

    try:
        overview = client.get_symbols_overview(relative_file)
        symbols = []
        # Check if this is a CLI file
        is_cli_file = is_cli_file_func(relative_file)

        for func_name in extract_function_names(overview):
            # Fail-fast: 立即抛出异常，不允许部分失败
            refs = client.find_references(func_name, relative_file)
            ref_count = count_references(refs)

            # Determine symbol type
            symbol_type = (
                "cli_command" if is_cli_file and ref_count == 0 else "function"
            )

            symbols.append(
                {
                    "name": func_name,
                    "type": symbol_type,
                    "references": ref_count,
                }
            )

        logger.bind(
            file=relative_file,
            symbol_count=len(symbols),
        ).success("File analyzed")

        return {
            "file": relative_file,
            "symbols": symbols,
        }

    except SerenaError:
        # 立即向上抛出，不允许静默
        raise
    except Exception as e:
        # 其他异常包装为 SerenaError
        raise SerenaError(f"analyze_file({relative_file})", str(e)) from e


def analyze_files(files: list[str], client: Any, is_cli_file_func: Any) -> dict:
    """Analyze multiple files.

    Args:
        files: List of relative file paths
        client: Serena client instance
        is_cli_file_func: Function to check if file is CLI module

    Returns:
        Analysis report dict

    Raises:
        SerenaError: If any file analysis fails
    """
    logger.bind(
        domain="serena",
        action="analyze_files",
        file_count=len(files),
    ).info("Analyzing files")

    # Filter out files that don't exist
    existing_files = []
    skipped_files = []
    for file_path in files:
        if Path(file_path).exists():
            existing_files.append(file_path)
        else:
            skipped_files.append(file_path)

    if skipped_files:
        logger.bind(
            domain="serena",
            action="analyze_files",
            skipped_count=len(skipped_files),
            skipped_files=skipped_files,
        ).warning(
            f"Skipping {len(skipped_files)} files that no longer exist in repository"
        )

    report: dict[str, str | dict | list[dict] | list[str]] = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "health_check": {"status": "ok", "log": ""},
        "files": [],  # type: ignore[dict-item]
        "skipped_files": skipped_files,
    }

    for file in existing_files:
        # Fail-fast: 如果任何文件分析失败，立即抛出
        result = analyze_file(file, client, is_cli_file_func)
        cast(list[dict[str, Any]], report["files"]).append(result)

    # Summary
    files_list = cast(list[dict[str, Any]], report["files"])
    total_symbols = sum(
        len(f.get("symbols", [])) for f in files_list if isinstance(f, dict)
    )
    report["summary"] = {
        "files": len(report["files"]),
        "total_symbols": total_symbols,
        "skipped_files": len(skipped_files),
    }

    logger.bind(
        total_files=len(existing_files),
        total_symbols=total_symbols,
        skipped_files=len(skipped_files),
    ).success("Files analyzed")

    return report
