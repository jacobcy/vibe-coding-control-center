---
document_type: plan
title: Phase 04 - Handoff & Cutover
status: draft
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-16
related_docs:
  - docs/v3/plans/v3-rewrite-plan.md
  - docs/v3/implementation/02-architecture.md
  - docs/v3/implementation/03-coding-standards.md
  - docs/v3/implementation/04-test-standards.md
---

# Phase 04: Handoff & Cutover

**Goal**: Implement synchronization between the local SQLite database and Markdown handoff files, then transition the primary entry point to `vibe3`.

## 1. Context Anchor (Optional)
If you require more than technical scope, refer to the [Vibe 3.0 Master Plan](v3-rewrite-plan.md).

## 2. Pre-requisites (Executor Entry)
- [ ] `docs/v3/handoff.md` template exists.
- [ ] `vibe3 flow status --json` returns a non-empty list of active flows.
- [ ] Phase 03 PR commands are functional.

## 3. Architecture Constraints (引用)

**必须遵守**：
- [02-architecture.md](../implementation/02-architecture.md) - 分层架构与职责
- [03-coding-standards.md](../implementation/03-coding-standards.md) - 编码标准
- [04-test-standards.md](../implementation/04-test-standards.md) - 测试标准
- [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md) - Handoff 数据结构

**关键约束**：
- Handoff 同步逻辑放在 `services/handoff_service.py` (< 300 行)
- Markdown 解析逻辑放在 `clients/markdown_client.py` (< 200 行)
- 禁止在 Command 层直接操作文件系统
- 测试文件 < 150 行（Services 层），< 100 行（Clients 层）

## 4. Handoff Logic

- **Two-Way Sync**: Ensure `vibe3 handoff sync` can push SQLite state to Markdown markers and vice versa.
- **Marker Format**: Use standard HTML/Markdown comment markers (e.g., `<!-- VIBE_STATE_START -->`) to identify injectable regions.
- **Schema Validation**: Verify that the handoff Markdown matches the required structured data schema for the next Agent.

## 2. Technical Cutover

- **Entry Proxy**: Modify `bin/vibe` to check for a configuration flag (or file presence) to decide whether to run `vibe2` (legacy) or `vibe3`.
- **Delegation**: Ensure `vibe3` can transparently handle commands that were previously handled by `vibe2`, providing a compatibility layer if necessary.

## 3. Success Criteria (Technical)

- [ ] `vibe3 handoff sync` updates `docs/v3/handoff.md` without overwriting unrelated text.
- [ ] Run a comparison tool that confirms 100% data parity between `handoff.db` and the Markdown file.
- [ ] Executing `bin/vibe flow status` successfully triggers the `vibe3` path.
- [ ] `vibe3 handoff edit` opens the correct file with the specified editor.

## 5. Development Notes (基于 Phase 02 经验)

### 5.1 Markdown 标记格式
**参考**: [2026-03-13-vibe3-parallel-rebuild-design.md](../../plans/2026-03-13-vibe3-parallel-rebuild-design.md) § "Handoff Identity And Authorship"

**标记格式**：
```markdown
<!-- VIBE_STATE_START -->
## Flow State
- Flow: feature-xyz
- Branch: task/feature-xyz
- Task Issue: #123
- Status: active

## Handoff Items
[1] [claude/sonnet-4.5] 完成了设计初稿
[2] [codex/gpt-5.4] 实现了核心逻辑
<!-- VIBE_STATE_END -->
```

**解析规则**：
- 使用正则表达式提取 `<!-- VIBE_STATE_START -->` 和 `<!-- VIBE_STATE_END -->` 之间的内容
- 不修改标记外的任何文本
- 保持原有缩进和格式

### 5.2 双向同步逻辑
**参考**: SQLite `flow_state` 表结构

**SQLite → Markdown**：
1. 读取 `flow_state` 表当前记录
2. 读取 `flow_events` 表事件历史
3. 渲染为 Markdown 格式
4. 替换标记区域内容

**Markdown → SQLite**：
1. 解析 Markdown 标记区域
2. 提取结构化字段
3. 更新 `flow_state` 表
4. 添加 `handoff_synced` 事件到 `flow_events` 表

**冲突处理**：
- 以 SQLite 为准（最新 `updated_at` 时间戳）
- 记录同步事件到 `flow_events` 表

### 5.3 Entry Point 切换逻辑
**参考**: [2026-03-13-vibe3-parallel-rebuild-design.md](../../plans/2026-03-13-vibe3-parallel-rebuild-design.md) § "Command Strategy"

**`bin/vibe` 实现模式**：
```bash
#!/bin/bash
# 检查切换标志
if [ -f ".git/vibe3_enabled" ]; then
    exec python3 scripts/python/vibe3/cli.py "$@"
else
    # 调用旧实现
    exec bash lib/vibe_main.sh "$@"
fi
```

**切换流程**：
1. 初期：默认使用 vibe2，需要显式启用 vibe3
2. 稳定期：默认使用 vibe3，提供 `--vibe2` 回退选项
3. 最终：移除 vibe2 入口

### 5.4 UI 分离原则
**经验教训**（来自 flow.py 重构）：
- ✅ Command 层只负责参数解析和调用 Service
- ✅ UI 渲染逻辑全部放在 `ui/` 目录
- ❌ 避免：在 Command 层直接使用 `print()` 或 Rich Table

**示例**：
```python
# ❌ 错误：Command 层包含 UI 逻辑
print(f"[green]✓ Flow created:[/] {flow.flow_slug}")

# ✅ 正确：委托给 UI 层
render_flow_created(flow)
```

### 5.5 Testing Strategy
**参考**: [04-test-standards.md](../implementation/04-test-standards.md)

**必须测试**：
- Markdown 标记区域解析（正则表达式验证）
- 双向同步逻辑（SQLite ↔ Markdown）
- Entry point 切换逻辑（bash 脚本）
- 不覆盖标记外文本（保留用户笔记）

**测试数据**：
- 创建包含标记的测试 Markdown 文件
- 使用内存 SQLite 数据库
- 验证同步后数据一致性

**测试约束**：
- 测试文件 < 180 行（Services 层），< 100 行（Clients 层）
- 测试覆盖率 >= 80%（Services 层），>= 70%（Clients 层）
- 使用 Mock 隔离文件系统操作
- 使用 pytest fixtures 减少重复代码

### 5.6 兼容性处理
**参考**: [2026-03-13-vibe3-parallel-rebuild-design.md](../../plans/2026-03-13-vibe3-parallel-rebuild-design.md) § "Migration Principles"

**兼容层设计**：
- 提供 `vibe2` 别名，指向旧实现
- 新命令（如 `vibe3 handoff`）不提供兼容层
- 记录所有兼容性警告到日志

## 6. Handoff for Executor 05
- [ ] Verify `bin/vibe` successfully delegates to the new implementation.
- [ ] Ensure all `lib3/` modules are correctly linked.
