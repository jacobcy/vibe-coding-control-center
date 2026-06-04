# 治理闭环机制说明

**维护者**: Vibe Team
**创建时间**: 2026-05-26
**状态**: Active

---

## 概述

Governance 分为两层，加上上层的 roadmap 审查，共三层。每层有独立的标签实现闭环，防止重复处理。

**三层架构、标签语义和角色分工详见 [supervisor/roadmap-common.md](../../supervisor/roadmap-common.md)**。

---

## 完整业务循环

### Issue 生命周期

```
Issue 创建（无 assignee，无标签）
  |
  v
[intake 扫描]
  |- 有 orchestra-scanned? -> 跳过
  |- 有 assignee? -> 跳过（已在 pool）
  |- 无标签、无 assignee -> 三级审查
       |- 接受 -> 分配 assignee --> 流入 pool（无 scanned 标签）
       |- 跳过 -> 打 orchestra-scanned --> 不再看
              |
              v（如果接受了）
[pool 扫描]
  |- 无 assignee? -> 跳过（不在 pool）
  |- 有 orchestra-governed? -> 跳过
  |- 有 assignee、无 governed -> 决策
       |- roadmap/rfc -> 不进 ready，等人类决策（标签是信号，非执行门禁）
       |- roadmap/epic -> 不进 ready，需拆分
       |- state/ready -> 可执行
       |- 建议关闭
       打完标签后 -> 打 orchestra-governed --> 不再看
              |
              v
[vibe-roadmap 审查]
  |- 有 roadmap-reviewed? -> 跳过
  |- 无 -> 审查 governance 决策
       写 [roadmap decision] -> 打 roadmap-reviewed -> 写 memory.md
```

### ADR 决策耐久化

架构级 rfc 决策不应止步于评论。当决策满足 ADR 结晶条件时（跨任务/跨模块、有真实权衡、期望长期有效），应结晶为 `docs/decisions/` 下的 ADR 文件，确保决策理由在 PR/issue 关闭后仍可追溯。

生成路径：`roadmap/rfc` → 人类决策 → 结晶为 ADR → 更新 standards。
消费路径：读 standards（现状）→ 溯 ADR（为什么）→ 溯 RFC issue（原始问题）。

### 两层 governance 的扫描边界

| | roadmap-intake | assignee-pool |
|---|---|---|
| **扫描范围** | broader repo（无 assignee） | assignee pool（有 assignee） |
| **跳过条件** | 有 assignee / 有 `orchestra-scanned` / 有 `orchestra-governed`（防御） | 无 assignee 或 有 `orchestra-governed` |
| **打标签** | 只对跳过的打 `orchestra-scanned` | 对所有决策完的打 `orchestra-governed` |
| **不打的含义** | 接受 -> assignee 是信号 -> 流入 pool | 无——所有决策完都打 |
| **过滤例外** | 无 | `roadmap/epic` 收口检查独立扫描所有 epic，不受 governed 过滤 |

---

## roadmap/rfc 语义与 Level 0 闭环

### roadmap/rfc 是人类规划信号，不是执行门禁

自动执行的真正门禁是 **manager assignee + `state/ready`**：orchestra 派发队列恒定 `require_manager_assignee=True`（见 `src/vibe3/orchestra/queue_operations.py`），并要求 state 进入 ready。`roadmap/rfc` 本身**不被派发队列消费**，它是给人类规划层和治理 scan 过滤用的可见性信号，语义为"需要人类设计决策"。

推论：一个 issue 只要没有 manager assignee + ready，就不会被自动执行，无论是否带 `roadmap/rfc`。因此对**人类 assignee** 的 issue 而言，`roadmap/rfc` 不充当门禁，但仍作为"需设计讨论"的可查询规划信号保留其价值。

### Level 0 闭环：intake 直接打 roadmap/rfc

`.claude/` / `.codex/` 目录改动（Level 0）是**机械可判定**的硬阻塞，自动化无法修改这些目录。intake 在 skip 该类 issue 时，除打 `orchestra-scanned` 外，**直接打 `roadmap/rfc`**——这是 intake 唯一允许设置 `roadmap/*` 的机械例外（非 intake 自称 decider，而是路由一个确定性硬阻塞）。

闭环路径（不经过 pool，因为 Level 0 issue 无 assignee，pool 只扫 has-assignee）：

```
intake 检测 Level 0 -> 打 orchestra-scanned + roadmap/rfc（无 assignee）
   -> task status Rule 1（roadmap/rfc「始终展示」，不管 assignee）
   -> /vibe-task surface 给人类
   -> 人类决策（分配 assignee / 移除 roadmap/rfc / 关闭）
```

**为什么必须由 intake 打**：[task-status-filtering.md](../v3/orchestra/task-status-filtering.md) 的 Rule 4 会把"无 state + 无 assignee"的 issue 隐藏（SKIP）。若 intake 只写 suggest 而不打 `roadmap/rfc`，Level 0 issue 会落入 Rule 4 被永久隐藏；pool 又只扫 has-assignee，永远看不到它。只有 intake 直接打 `roadmap/rfc` 命中 Rule 1 才能让它可见、被 vibe-task 捡起。`roadmap/rfc` 的后续清理由 vibe-roadmap（Layer 3，两个群体都可见）或人类（经 vibe-task）负责；**pool 不清理 `roadmap/rfc`**——pool 只清理自己域内的 `orchestra-governed`。

---

## 缓存机制

### .agent/context/memory.md

**用途**：vibe-roadmap 每次分析后的结果缓存，下次运行时快速定位锚点

**git 状态**：不纳入 git 追踪（.gitignore），本地缓存专用

**写入时机**：vibe-roadmap Step 4 完成后

**读取时机**：vibe-roadmap 启动时（可选，快速定位上次决策锚点）

---

## 闭环检查清单

### Layer 1: roadmap-intake

- [x] 扫描前过滤：跳过有 `orchestra-scanned`、`orchestra-governed`（防御）或有 assignee 的 issue
- [x] 接受（分配 assignee）：不设 scanned 标签，自然流入 pool
- [x] 跳过（不接受）：打 `orchestra-scanned` 标签
- [x] Level 0（`.claude/`/`.codex/`）skip：除 `orchestra-scanned` 外**直接打 `roadmap/rfc`**（机械例外），让 task-status Rule 1 始终展示、vibe-task 可捡起
- [x] Stop Point Checklist 区分接受/跳过两种情况

### Layer 2: assignee-pool

- [x] 扫描前过滤：跳过无 assignee 或有 `orchestra-governed` 的 issue
- [x] 决策完成（rfc/epic/ready/close）：打 `orchestra-governed` 标签
- [x] 去重规则检查 `orchestra-governed` 标签
- [x] Stop Point Checklist 要求打 governed 标签

### Layer 3: vibe-roadmap

- [x] Step 0 过滤：跳过有 `roadmap-reviewed` 标签的 issue
- [x] 审查完成：写 `[roadmap decision]` + 打 `roadmap-reviewed` 标签
- [x] 结果写入 memory.md 缓存
- [x] **推翻 intake skip 时**：移除 `orchestra-scanned` + 分配 assignee + 打 `roadmap-reviewed`（明示规则见 [`skills/vibe-roadmap/SKILL.md`](../../skills/vibe-roadmap/SKILL.md) Step 0 第 5 步）

---

## 异常兜底机制

三层闭环并不能覆盖所有情况，**`vibe3 task status` 命令充当异常监控兜底**。
详细规则见 [task-status-filtering.md](../v3/orchestra/task-status-filtering.md) 的 Rule 5/7。

### 兜底覆盖的场景

| 场景 | 标签状态 | task status 显示 | 应对 |
|------|---------|-----------------|------|
| pool 决策 rfc，人类移除 `roadmap/rfc` 后未触发 pool 重新评估 | 有 assignee + 无 state + 有 `orchestra-governed` + 无 `roadmap/rfc` | **State Missing anomaly**（Rule 7） | 人类按提示介入：手动移除 `orchestra-governed` 让 pool 重评，或直接补 `state/ready` |
| pool 建议 close 但 issue 仍 OPEN（只写 suggest 未关闭） | 有 assignee + 无 state + 有 `orchestra-governed` | **State Missing anomaly**（Rule 7） | 人类决定真关闭，或修正决策 |
| pool 真的关闭了 issue | issue closed | 不显示（CLOSED 不在 orchestrated_issues） | 等用户重新发 issue |
| intake 接受但 pool 尚未扫描 | 有 manager assignee + 无 state + 无 `orchestra-governed` | **Waiting Governance**（Rule 5） | 等下次 pool scan 自然消化 |

### 兜底设计原则

- 三层 agent 负责**正常路径闭环**（打标签、写决策）
- `task status` 异常区负责**反常路径监控**（标签漂移、决策半完成）
- 不要求 agent 主动捕获所有边缘 case；让 status dashboard 充当人类视野的一部分

---

## 验证方法

```bash
# 验证 intake 层：被跳过的 issue 应有 orchestra-scanned
gh issue view <N> --json labels --jq '.labels | map(.name)'

# 验证 pool 层：被决策的 issue 应有 orchestra-governed
gh issue view <N> --json labels --jq '.labels | map(.name)'

# 验证 roadmap 层：被审查的 issue 应有 roadmap-reviewed
gh issue view <N> --json labels --jq '.labels | map(.name)'
```

---

## 相关文档

- **写入侧（本文档）**：定义谁/何时打什么标签，三层 agent 的闭环责任
- **[supervisor/roadmap-common.md](../../supervisor/roadmap-common.md)**：三层架构、标签语义和三级审查框架的公共定义
- **[docs/v3/orchestra/task-status-filtering.md](../v3/orchestra/task-status-filtering.md)**：定义 `vibe3 task status` 的 UI 展示过滤规则（读取侧）
- **[docs/standards/github-labels-reference.md](../standards/github-labels-reference.md)**：标签参考手册
- **[supervisor/governance/roadmap-intake.md](../../supervisor/governance/roadmap-intake.md)**：intake 角色 prompt
- **[supervisor/governance/assignee-pool.md](../../supervisor/governance/assignee-pool.md)**：pool 角色 prompt
- **[skills/vibe-roadmap/SKILL.md](../../skills/vibe-roadmap/SKILL.md)**：roadmap 审查 skill

---

**维护者**: Vibe Team
**最后更新**: 2026-05-28
