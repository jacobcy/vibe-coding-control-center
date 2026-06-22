# Vibe-Center Run Conventions

> **Scope**: project scope — 追加到 user scope run.policy 之后
> **用途**: vibe-center 项目专属的执行约定

## 测试范围选择

### 使用 pre_push_test_selector 工具

项目提供了 `vibe3.analysis.pre_push_test_selector.select_pre_push_tests` 用于映射源文件到相关测试：

```bash
# 列出改动的源文件，通过 test selector 获取相关测试
git diff --name-only HEAD~1 HEAD -- src/vibe3/ | \
  uv run python src/vibe3/analysis/pre_push_test_selector.py
```

### 三层映射策略 (强制)

执行验证时，executor **必须**使用 `pre_push_test_selector` 工具解析出完整测试集（含所有三层），并运行解析结果中的所有测试文件。不得仅运行 plan 中明确提到的测试，也不得仅运行第一层映射结果。

1. **第一层：直接测试文件匹配**
   - 改动 `src/vibe3/<module>/<name>.py` → 运行 `tests/vibe3/<module>/test_<name>.py`
   - 优先级最高，**必须运行**

2. **第二层：DAG 导入分析**
   - 通过 import DAG 找出哪些测试间接引用了改动模块
   - 优先级中等，**必须运行**（除非 test selector 未解析出任何 DAG 目标）

3. **第三层：目录级回退**
   - 运行改动源文件对应的整个测试目录：`tests/vibe3/<module>/`
   - 优先级最低，**必须运行**（除非 test selector 在上层已全覆盖或返回 skip 模式）

### 执行模板

```bash
# 1. 获取当前分支相对 merge-base 的改动文件列表
CHANGED=$(git diff --name-only origin/main...HEAD -- src/vibe3/)

# 2. 通过 test selector 解析完整测试集（含 DAG 分析和目录回退）
SELECTION=$(echo "$CHANGED" | uv run python src/vibe3/analysis/pre_push_test_selector.py)
TARGETS=$(echo "$SELECTION" | uv run python -c "import sys,json; print(' '.join(json.load(sys.stdin)['tests']))")
MODE=$(echo "$SELECTION" | uv run python -c "import sys,json; print(json.load(sys.stdin)['mode'])")

# 3. 根据 mode 决定本地执行策略
if [ "$MODE" = "skip" ]; then
    echo "Selector returned skip mode — tests covered by CI"
else
    uv run pytest $TARGETS
fi
```

### 验证自检（声称 tests=PASS 前必须完成）

1. **确认已运行完整 selector 输出**：
   - 记录 `pre_push_test_selector` 的 `mode` 和 `tests` 列表
   - 确认 pytest 命令覆盖了列表中的所有测试文件

2. **确认非 skip 模式下无遗漏**：
   - 如果 mode 为 `incremental` 或 `smoke`，确认所有 `tests` 项都已执行
   - 如果 mode 为 `skip`，在执行报告中明确说明原因和 CI 覆盖策略

3. **如果发现测试失败**：
   - 在执行报告中明确记录哪些测试失败
   - 不得冒称 "所有测试通过"
   - 提供失败测试的 reproduction 命令

### 范围过大处理

如果测试范围 resolve 到 `tests/vibe3` 全量：
- 本地只运行直接对应的测试目录（第一层和第二层）
- 全量测试交由 CI 覆盖
- 不要在本地盲目运行全量测试，避免超时

## CI-like 环境验证

对于涉及 subprocess、git 操作、文件路径假设的测试，声称完成前必须验证：

1. **Subprocess 测试**：验证工作目录无关性、环境变量独立性、git 路径独立性
2. **Git 操作测试**：验证 bare repository 和不同 branch topology 下的行为
3. **文件路径测试**：验证相对路径在 CI 根目录和 worktree 中都能工作

验证命令：
```bash
GITHUB_ACTIONS=true uv run pytest tests/vibe3/path/to/test.py
VIBE_CI_SIMULATE=1 bash scripts/hooks/pre-push.sh
uv run pytest tests/vibe3/integration/test_ci_parity.py -v
```

## Framework 行为验证（Typer/Click）

verification report 涉及框架行为时，必须基于代码实际运行行为验证，而非假设参数默认值语义。

关键机制追踪：`count=True` 默认值、`ctx.meta` 继承链路（`main_callback` → 子命令）、继承 guard 条件。

禁止仅凭参数默认值或单一函数签名判断行为（忽略 `ctx.meta` 覆盖、callback/inheritance 链路）。
