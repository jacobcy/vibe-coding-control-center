# Plan C: Structure 扫描链路去重（Inspect Files vs Snapshot Build）

> For Agent: 目标是删除重复代码，不改变输出契约。

## Goal
收敛 `inspect files` 与 `snapshot build` 的重复结构扫描逻辑，降低维护成本和漂移风险。

## Scope
- 提取共享的 Python 文件扫描/过滤/结构采集流程
- 删除 command/service 两侧重复循环代码
- 保持现有 JSON 输出字段兼容

## Non-Goals
- 不变更 snapshot 存储格式
- 不改 review context schema

## Steps
1. 识别重复逻辑：遍历 `src/vibe3/**/*.py`、排除 `__pycache__`、调用 `analyze_python_file`。
2. 在 service 层建立单一扫描入口，command 与 snapshot 复用。
3. 删除原有重复循环代码，保持输出不变。
4. 回归 snapshot 与 inspect 相关测试。

## Files
- Modify: `src/vibe3/services/snapshot_service.py`
- Modify: `src/vibe3/commands/inspect.py`
- Modify: `src/vibe3/services/structure_service.py`（仅当需要新增复用入口）
- Test: `tests/vibe3/services/test_snapshot_service.py`
- Test: `tests/vibe3/services/test_structure_service.py`
- Test: `tests/vibe3/commands/test_inspect_commands.py`

## Acceptance
- 重复扫描逻辑收敛到一处。
- `snapshot build/show/diff` 与 `inspect files` 输出兼容。
- 净删代码（新增行数小于删除行数）。

## Verification
- `uv run pytest tests/vibe3/services/test_snapshot_service.py -q`
- `uv run pytest tests/vibe3/services/test_structure_service.py -q`
- `uv run pytest tests/vibe3/commands/test_inspect_commands.py -q`
