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

### 三层映射策略

1. **第一层：直接测试文件匹配**
   - 改动 `src/vibe3/<module>/<name>.py` → 运行 `tests/vibe3/<module>/test_<name>.py`
   - 优先级最高，必须运行

2. **第二层：DAG 导入分析**
   - 通过 import DAG 找出哪些测试间接引用了改动模块
   - 优先级中等，建议运行

3. **第三层：目录级回退**
   - 运行改动源文件对应的整个测试目录：`tests/vibe3/<module>/`
   - 优先级最低，覆盖面最广

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
