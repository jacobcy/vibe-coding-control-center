---
document_type: quick-reference
title: Vibe 3.0 - 命令参数快速参考
status: active
author: Claude Sonnet 4.6
created: 2026-03-17
last_updated: 2026-03-17
related_docs:
  - docs/v3/infrastructure/07-command-standards.md
---

# 命令参数快速参考

> **完整标准**: [07-command-standards.md](07-command-standards.md)

---

## 核心参数集

所有 `vibe` 命令必须支持以下参数：

| 参数 | 短选项 | 长选项 | 用途 | 示例 |
|------|--------|--------|------|------|
| 追踪 | - | `--trace` | 运行时调用链路追踪 | `vibe review pr 42 --trace` |
| 详细 | `-v` | `--verbose` | 详细输出（DEBUG 日志） | `vibe inspect metrics -v` |
| JSON | - | `--json` | JSON 格式输出 | `vibe inspect pr 42 --json` |
| 确认 | `-y` | `--yes` | 自动确认交互 | `vibe clean --yes` |
| 帮助 | `-h` | `--help` | 显示帮助 | `vibe review --help` |

---

## 快速验证

验证命令是否符合标准：

```python
import inspect
from vibe3.commands.example import example_command

sig = inspect.signature(example_command)
params = sig.parameters

# 检查核心参数
assert "trace" in params
assert "verbose" in params
assert "json_output" in params
assert "yes" in params

# 检查默认值
assert all(params[p].default == False for p in ["trace", "verbose", "json_output", "yes"])
```

---

**完整标准**: [07-command-standards.md](07-command-standards.md)