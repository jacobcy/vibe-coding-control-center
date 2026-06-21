# Vibe-Center Plan Conventions

> **Scope**: project scope — 追加到 user scope plan.policy 之后
> **用途**: vibe-center 项目专属的规划约定

## 包级导入验证（循环依赖检测）

涉及以下改动时，必须在 plan 阶段测试包级导入：
- 新增/修改 `__init__.py` 中的 re-export
- 新增/修改模块间的交叉导入
- 移动或重命名符号
- 重组模块结构

验证命令模板：
```bash
# 直接子模块导入（验证子模块自身无循环依赖）
uv run python -c "from vibe3.<module>.<submodule> import <Symbol>"

# 包级导入（验证 __init__.py 重导出链无循环依赖）
uv run python -c "from vibe3.<module> import <Symbol>"
```

失败处理：直接导入通过而包级导入失败是循环依赖的典型信号，必须在 plan 阶段记录为 finding 并标记为阻塞条件。

## 基础设施代码参考模式

编写涉及 subprocess、文件操作、环境变量的代码时，必须检查现有模式：
- subprocess 解释器选择：使用 `sys.executable`（参考 `tests/vibe3/test_cli_bootstrap.py:38`、`tests/vibe3/test_modularity/test_module_independence.py:37`）
- 优先复用 `tests/` 中的现有 monkeypatch/mock 模式

示例搜索命令：
```bash
rg 'subprocess\.run\(' tests/ -A 5
rg '"python"' tests/
```

## 环境变量语义验证示例（TMUX 参考案例）

```bash
# 验证 TMUX 环境变量语义
echo $TMUX
# 输出: /private/tmp/tmux-501/default,4658,123
# 结论: TMUX env var 是 socket path，不是 session name

# 获取实际 session name
tmux display-message -p '#{session_name}'
# 输出: vibe3-executor-issue-42
# 结论: 需要用 tmux display-message 获取 session name
```

## 测试范围路径约定

默认测试目录结构：
- 单元测试：`tests/vibe3/test_<module>/`
- 集成测试：`tests/vibe3/integration/`
- 模块化测试：`tests/vibe3/test_modularity/`

## ADR 约束

规划前必须查看 `docs/decisions/INDEX.md` 和相关 accepted ADR，确认计划不违反任何当前有效 ADR。
