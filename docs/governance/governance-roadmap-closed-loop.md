# 治理闭环机制说明

**维护者**: Vibe Team  
**创建时间**: 2026-05-26  
**状态**: Active  

---

## 概述

Governance 分为两层，加上上层的 roadmap 审查，共三层。每层有独立的标签实现闭环，防止重复处理。

---

## 三层架构

```
broader repo --> Layer 1: roadmap-intake (入口层)
                    扫描范围: 无 assignee 的 issue
                    过滤: 无 orchestra-scanned（自闭环）
                          + 无 orchestra-governed（防御：pool 已决策的不该回头）
                    接受 -> 分配 assignee -> 流入 Layer 2
                    跳过 -> 打 orchestra-scanned -> 不再看
                          |
                          v
                 Layer 2: assignee-pool (池内决策层)
                    扫描范围: 有 assignee 的 issue
                    过滤: 无 orchestra-governed
                    例外: roadmap/epic 收口检查每次独立扫描，不受 governed 过滤
                    决策(close/split/rfc/epic/ready/resume) -> 打 orchestra-governed -> 不再看
                          |
                          v
                 Layer 3: vibe-roadmap (上层审查/纠偏层)
                    扫描范围: 所有 [governance suggest] 评论
                    过滤: 无 roadmap-reviewed 且无 roadmap/rfc
                    审查 -> 打 roadmap-reviewed -> 写入 memory.md
```

---

## 角色分工

| 角色 | 文件 | Marker | 职责 | 标签 |
|------|------|--------|------|------|
| **roadmap-intake** | supervisor/governance/roadmap-intake.md | `[governance suggest]` | 入口观察者：扫描 broader repo，决定是否纳入 pool | 跳过时打 `orchestra-scanned` |
| **assignee-pool** | supervisor/governance/assignee-pool.md | `[governance suggest]` | 池内决策者：对 pool 中 issue 做 rfc/epic/ready 决策 | 决策后打 `orchestra-governed` |
| **vibe-roadmap** | skills/vibe-roadmap/SKILL.md | `[roadmap decision]` | 上层审查者：审查 governance 决策，纠正和补全 | 审查后打 `roadmap-reviewed` |

---

## 三标签详解

### 1. orchestra-scanned（入口层闭环）

**谁打**：roadmap-intake  
**何时打**：审查后**决定不接受**（不分配 assignee）时  
**不打的情况**：接受并分配 assignee 时——assignee 本身就是信号，issue 自然流入 assignee-pool  

**语义**："已审查，不纳入"  

**命令**：
```bash
gh issue edit <issue-number> --add-label "orchestra-scanned"
```

**颜色**：FF9933（橙色）

**过滤逻辑**：
```
intake 扫描 -> 跳过有 orchestra-scanned 的 issue（自闭环）
intake 扫描 -> 跳过有 orchestra-governed 的 issue（防御性过滤）
intake 扫描 -> 跳过有 assignee 的 issue（已在 pool 中）
```

**防御性过滤说明**：
代码 `build_broader_repo_entries` 同时过滤 `orchestra-scanned` 和 `orchestra-governed`。
原因：broader repo 默认查询无 assignee 的 issue，但如果一个 issue 曾被 pool 决策（带 `orchestra-governed`）后 assignee 被移除，或 pool 决策 `close`/`rfc` 后 issue 仍 OPEN 但无 assignee，
不该让 intake 再次评估它——它已经过更上层的决策了。

---

### 2. orchestra-governed（池内层闭环）

**谁打**：assignee-pool  
**何时打**：完成决策后（不管结论是 rfc、epic、ready、建议关闭）  

**语义**："已决策，不再重复检查"  

**命令**：
```bash
gh issue edit <issue-number> --add-label "orchestra-governed"
```

**颜色**：9933FF（蓝紫色）

**过滤逻辑**：
```
pool 扫描 -> 跳过有 orchestra-governed 的 issue
pool 扫描 -> 跳过无 assignee 的 issue（不在 pool 中，由 intake 负责）
```

---

### 3. roadmap-reviewed（审查层闭环）

**谁打**：vibe-roadmap  
**何时打**：写完 `[roadmap decision]` 评论后，**但 decision 不是 `rfc` 时**  
**不打的情况**：decision 是 `rfc` 时——rfc 表示需要人类决策，未完成决策闭环  

**语义**："已审查，下次 Step 0 跳过"  

**与 `roadmap/rfc` 的互斥规则**：
- `roadmap/rfc` 和 `roadmap-reviewed` **不能共存**
- 带 `roadmap/rfc` 的 issue 表示"未完成决策"，不应打 `roadmap-reviewed`
- 人类移除 `roadmap/rfc` 后，下次 roadmap 扫描会重新捡起该 issue，完成审查后打 `roadmap-reviewed`

**命令**：
```bash
gh issue edit <issue-number> --add-label "roadmap-reviewed"
```

**过滤逻辑**：
```
Step 0 搜索 -> 过滤掉有 roadmap-reviewed 的 issue
Step 0 搜索 -> 过滤掉有 roadmap/rfc 的 issue（等待人类决策）
```

**颜色**：CC99FF（淡紫色）

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
       |- roadmap/rfc -> 跳过执行，等人类决策
       |- roadmap/epic -> 跳过执行，需拆分
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

### 两层 governance 的扫描边界

| | roadmap-intake | assignee-pool |
|---|---|---|
| **扫描范围** | broader repo（无 assignee） | assignee pool（有 assignee） |
| **跳过条件** | 有 assignee / 有 `orchestra-scanned` / 有 `orchestra-governed`（防御） | 无 assignee 或 有 `orchestra-governed` |
| **打标签** | 只对跳过的打 `orchestra-scanned` | 对所有决策完的打 `orchestra-governed` |
| **不打的含义** | 接受 -> assignee 是信号 -> 流入 pool | 无——所有决策完都打 |
| **过滤例外** | 无 | `roadmap/epic` 收口检查独立扫描所有 epic，不受 governed 过滤 |

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
- **[docs/v3/orchestra/task-status-filtering.md](../v3/orchestra/task-status-filtering.md)**：定义 `vibe3 task status` 的 UI 展示过滤规则（读取侧）
- **[docs/standards/github-labels-reference.md](../standards/github-labels-reference.md)**：标签参考手册
- **[supervisor/governance/roadmap-intake.md](../../supervisor/governance/roadmap-intake.md)**：intake 角色 prompt
- **[supervisor/governance/assignee-pool.md](../../supervisor/governance/assignee-pool.md)**：pool 角色 prompt
- **[skills/vibe-roadmap/SKILL.md](../../skills/vibe-roadmap/SKILL.md)**：roadmap 审查 skill

---

**维护者**: Vibe Team  
**最后更新**: 2026-05-28
