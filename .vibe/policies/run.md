# Vibe-Center Run Conventions

> **Scope**: project scope — 追加到 user scope run.policy 之后
> **用途**: vibe-center 项目专属的执行约定

## 测试范围选择

### 使用 pre_push_test_selector 工具

```bash
# 列出改动的源文件，通过 test selector 获取相关测试
git diff --name-only HEAD~1 HEAD -- src/vibe3/ | \
  uv run python src/vibe3/analysis/pre_push_test_selector.py
```

### 三层映射策略

1. **第一层：直接测试文件匹配** — `src/vibe3/<module>/<name>.py` → `tests/vibe3/<module>/test_<name>.py`，优先级最高
2. **第二层：DAG 导入分析** — 通过 import DAG 找出间接引用改动模块的测试
3. **第三层：目录级回退** — 运行源文件对应的整个测试目录 `tests/vibe3/<module>/`

范围过大时，本地只运行第一层+第二层，全量交 CI。

### 测试失败处理

测试失败需明确记录失败项和 reproduction 命令，不得冒称"所有测试通过"。

## 三层架构跨层验证

命名/术语变更实现完成后：
- `rg '<old_name>'` 搜索所有层（`src/vibe3/services/`、`src/vibe3/ui/`、`src/vibe3/commands/`、`tests/`、`docs/`）
- 确认无遗漏旧引用，如有遗漏立即修复或记录 finding
- 详见 `common.rules@project` 的「跨层一致性检查」

## CI-like 环境验证

涉及 subprocess、git 操作、文件路径假设的测试，声称完成前验证：
- `GITHUB_ACTIONS=true uv run pytest tests/vibe3/<path>` — CI 环境模拟
- `VIBE_CI_SIMULATE=1 bash scripts/hooks/pre-push.sh` — pre-push 模拟
- 详见 `common.rules@project` 的「CI 环境模拟验证」

## 框架行为验证（Typer/Click）

verification report 涉及框架行为时，必须基于代码实际运行行为验证：
- `count=True` 默认值（0 vs 1）
- `ctx.meta` 继承链路（`main_callback` → 子命令）
- 验证方式：代码追踪全链路 或 本地实际运行观察

## Commit 与 Push 验证

声称完成前 `git status` 必须 clean；禁止声称完成但未提交。
