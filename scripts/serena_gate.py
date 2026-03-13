#!/usr/bin/env python3
import json
import os
import sys
from datetime import UTC, datetime

from serena.agent import SerenaAgent

FUNCTION_KIND = 12


def unique_strings(values):
    seen = set()
    result = []
    for value in values:
        if isinstance(value, str) and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def extract_function_names(payload):
    names = []

    def walk(node):
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
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return unique_strings(names)


def count_references(payload):
    if isinstance(payload, list):
        return len(payload)

    count = 0

    def walk(node):
        nonlocal count
        if isinstance(node, dict):
            if isinstance(node.get("name_path"), str):
                count += 1
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return count


def main():
    files = json.loads(os.environ["SERENA_TARGET_FILES_JSON"])
    report_file = os.environ["SERENA_REPORT_FILE"]
    project_name = os.environ["SERENA_PROJECT_NAME"]
    base_ref = os.environ["SERENA_BASE_REF"]
    project_root = os.environ.get("SERENA_PROJECT_ROOT", ".")

    report = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": project_name,
        "base_ref": base_ref,
        "health_check": {"status": "ok", "log": ""},
        "files": [],
    }

    try:
        agent = SerenaAgent(project=project_root)
        overview_tool = agent.get_tool_by_name("get_symbols_overview")
        references_tool = agent.get_tool_by_name("find_referencing_symbols")
        for relative_file in files:
            try:
                overview_raw = agent.execute_task(lambda rel=relative_file: overview_tool.apply(relative_path=rel))
                overview = json.loads(overview_raw)
            except Exception as exc:
                report["files"].append(
                    {
                        "file": relative_file,
                        "status": "error",
                        "error": f"get_symbols_overview_failed: {exc}",
                        "symbols": [],
                    }
                )
                continue

            symbols = []
            for function_name in extract_function_names(overview):
                try:
                    refs_raw = agent.execute_task(
                        lambda fn=function_name, rel=relative_file: references_tool.apply(name_path=fn, relative_path=rel)
                    )
                    refs = json.loads(refs_raw)
                    symbols.append({"name": function_name, "status": "ok", "references": count_references(refs)})
                except Exception as exc:
                    symbols.append({"name": function_name, "status": "error", "references": 0, "error": str(exc)})
            report["files"].append({"file": relative_file, "status": "ok", "symbols": symbols})
    except Exception as exc:
        report["health_check"] = {"status": "error", "log": str(exc)}

    file_errors = sum(1 for item in report["files"] if item.get("status") != "ok")
    symbol_errors = sum(
        1
        for item in report["files"]
        for symbol in item.get("symbols", [])
        if symbol.get("status") != "ok"
    )
    report["summary"] = {
        "files": len(report["files"]),
        "file_errors": file_errors,
        "symbol_errors": symbol_errors,
    }

    with open(report_file, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=True, indent=2)
        handle.write("\n")

    print(json.dumps(report, ensure_ascii=True))

    if report["health_check"]["status"] != "ok":
        return 5
    if file_errors > 0 or symbol_errors > 0:
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
