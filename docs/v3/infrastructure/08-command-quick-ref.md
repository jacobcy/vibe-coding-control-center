---
document_type: quick-reference
title: Vibe 3.0 - 命令参数快速参考
status: active
author: Claude Sonnet 4.6
created: 2026-03-17
last_updated: 2026-03-18
related_docs:
  - docs/v3/infrastructure/07-command-standards.md
---

# 命令参数快速参考

> **完整标准**: [07-command-standards.md](07-command-standards.md)

---

## 三层参数结构

```
全局层     vibe3 -v/-vv [COMMAND]
命令组层   vibe3 flow/inspect/review/... [-h]
子命令层   vibe3 flow new NAME [--trace] [--json] [-y]
```

---

## 全局层参数（`vibe3`）

| 参数 | 说明 |
|------|------|
| `-v` | INFO 日志 |
| `-vv` | DEBUG 日志 |
| `-h` / `--help` | 显示帮助 |
| （无参数） | 显示帮助 |

```bash
vibe3 -v flow list
vibe3 -vv inspect pr 42
vibe3 -h
vibe3 help
```

---

## 子命令层参数（所有叶子命令）

| 参数 | 短选项 | 用途 |
|------|--------|------|
| `--trace` | - | 调用链路追踪 + DEBUG（比 `-vv` 更重量级） |
| `--json` | - | JSON 格式输出到 stdout |
| `--yes` | `-y` | 自动确认（破坏性操作） |
| `--help` | `-h` | 显示帮助 |

```bash
vibe3 inspect pr 42 --trace
vibe3 inspect pr 42 --json | jq '.score'
vibe3 inspect pr 42 --trace --json
vibe3 review pr 42 --help
vibe3 flow new my-feature -h
```

---

## `-v` vs `--trace` 对比

| | `-v` / `-vv` | `--trace` |
|---|---|---|
| 作用域 | 全局 | 子命令 |
| 日志级别 | INFO / DEBUG | DEBUG |
| 调用链追踪 | ❌ | ✅ |
| 性能开销 | 低 | 高 |
| 典型用途 | agent 日常调用 | 深度排查 |

---

## 常用命令示例

```bash
# 查看帮助（任意层级）
vibe3 -h
vibe3 flow -h
vibe3 inspect pr -h

# 分析 PR
vibe3 inspect pr 42
vibe3 inspect pr 42 --json
vibe3 inspect pr 42 --trace

# 代码审核
vibe3 review pr 42
vibe3 review pr 42 --publish
vibe3 -v review pr 42          # INFO 日志 + 审核

# 查看流程
vibe3 flow list
vibe3 flow status
vibe3 -vv flow new my-feature  # DEBUG 日志 + 创建
```

---

**完整标准**: [07-command-standards.md](07-command-standards.md)
