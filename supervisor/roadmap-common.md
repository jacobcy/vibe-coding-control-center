# Roadmap 治理闭环共享定义

**维护者**: Vibe Team  
**创建时间**: 2026-05-27  
**状态**: Active  

---

> 本文件是三层治理架构的权威定义源。所有治理材料应引用此文件，而非重复定义。

---

## 三层架构与角色分工

```
broader repo --> Layer 1: roadmap-intake (入口层)
                    扫描范围: 无 assignee 的 issue
                    过滤: 无 orchestra-scanned
                    接受 -> 分配 assignee -> 流入 Layer 2
                    跳过 -> 打 orchestra-scanned -> 不再看
                          |
                          v
                 Layer 2: assignee-pool (池内决策层)
                    扫描范围: 有 assignee 的 issue
                    过滤: 无 orchestra-governed
                    决策(rfc/epic/ready) -> 打 orchestra-governed -> 不再看
                          |
                          v
                 Layer 3: vibe-roadmap (上层审查层)
                    扫描范围: 所有 [governance suggest] 评论
                    过滤: 无 roadmap-reviewed
                    审查 -> 打 roadmap-reviewed -> 写入 memory.md
```

| 角色 | 文件 | Marker | 职责 | 标签 |
|------|------|--------|------|------|
| **roadmap-intake** | supervisor/governance/roadmap-intake.md | `[governance suggest]` | 入口观察者：扫描 broader repo，决定是否纳入 pool | 跳过时打 `orchestra-scanned` |
| **assignee-pool** | supervisor/governance/assignee-pool.md | `[governance suggest]` | 池内决策者：对 pool 中 issue 做 rfc/epic/ready 决策 | 决策后打 `orchestra-governed` |
| **vibe-roadmap** | skills/vibe-roadmap/SKILL.md | `[roadmap decision]` | 上层审查者：审查 governance 决策，纠正和补全 | 审查后打 `roadmap-reviewed` |

---

## 三标签定义与语义

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
intake 扫描 -> 跳过有 orchestra-scanned 的 issue
intake 扫描 -> 跳过有 assignee 的 issue（已在 pool 中）
```

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

## 各层过滤逻辑

### Layer 1: roadmap-intake

**扫描前过滤（强制）**：
- 跳过有 `orchestra-scanned` 标签的 issue（已审查过，不重复扫描）
- 跳过有 assignee 的 issue（已在 pool 中，由 assignee-pool 负责）

**处理动作**：
- 接受（分配 assignee）：不设 scanned 标签，自然流入 pool
- 跳过（不接受）：打 `orchestra-scanned` 标签

---

### Layer 2: assignee-pool

**扫描前过滤（强制）**：
- 跳过无 assignee 的 issue（不在 pool 中，由 roadmap-intake 负责）
- 跳过有 `orchestra-governed` 标签的 issue（pool 已决策过，不重复检查）

**处理动作**：
- 决策完成（rfc/epic/ready/close）：打 `orchestra-governed` 标签

---

### Layer 3: vibe-roadmap

**Step 0 过滤（强制）**：
- 跳过有 `roadmap-reviewed` 标签的 issue（已审查过）
- 跳过有 `roadmap/rfc` 标签的 issue（等待人类决策）

**处理动作**：
- 审查完成：写 `[roadmap decision]` + 打 `roadmap-reviewed` 标签（decision 不是 rfc 时）
- 结果写入 memory.md 缓存

---

## 三层决策范围边界

| 层级 | 决策范围 | 输出 | 边界 |
|------|----------|------|------|
| **Layer 1: roadmap-intake** | 只决定 accept（分配 assignee）或 skip（打 scanned） | `[governance suggest]` 建议纳入或跳过，附带原因 | intake 不自称 decider；跳过原因写在 suggest 中，由 pool 或 roadmap 做进一步决策 |
| **Layer 2: assignee-pool** | `roadmap/*`(rfc/epic/p0/p1/p2)、`priority/*`、close（明确冲突/重复）、`roadmap/rfc`（不确定）、resume（明确可恢复）、split（清晰分界） | `[governance suggest]` 决策建议 + `orchestra-governed` 标签 | pool 是 assignee pool 内的决策 OWNER |
| **Layer 3: vibe-roadmap** | 审查 `roadmap/rfc`、`state/blocked`、未 reviewed 的 issue；可覆盖 pool 的决策（rfc → continue、epic → split 等） | `[roadmap decision]` 决策结论 + `roadmap-reviewed` 标签 + memory.md 缓存 | roadmap 是上层审查纠正者，拥有最终决策权 |

**关键原则**：
- intake 不设 `roadmap/*`、`priority/*` 标签（属于 pool 层决策范围）
- pool 决策完成后一律打 `orchestra-governed`，不管结论是什么
- roadmap 审查完成后打 `roadmap-reviewed`（decision 不是 rfc 时），结果写入 memory.md

---

## Comment Marker 规范

### 角色与 Marker 映射

| 角色 | Marker | 性质 | 适用场景 |
|------|--------|------|----------|
| roadmap-intake / assignee-pool（observer） | `[governance suggest]` | 观察者意见，无强制力 | 入口观察、池内决策建议 |
| vibe-roadmap（decider） | `[roadmap decision]` | 决策者结论，覆盖 governance 建议 | 上层审查、纠正、最终决策 |

### 强制规则

1. **Marker 必须在行首**：所有 agent 写出的 issue / PR comment 必须以角色 marker 开头（行首，方括号包裹），前面只允许空白字符
2. **Marker 与正文分隔**：marker 与正文之间至少一个空格或换行
3. **禁止混用**：
   - vibe-roadmap **禁止**写 `[governance suggest]`
   - roadmap-intake / assignee-pool **禁止**写 `[roadmap decision]`
4. **缺失 marker 的后果**：会被人类指令解析器误读为人类指令

### 合规示例

```
[governance suggest] Intake: assigned to @vibe-manager-agent (manager-pool); scope=bugfix.
[governance suggest] Skipped: scope unclear, needs pool or roadmap review before automation.
[governance suggest] 入池评估：评估依据=重构范围明确，已设置 roadmap/p2 + priority/5 + state/ready.
[governance auto-recover] 已自动恢复 state：检测到 blocked 原因是 state unchanged，但 authoritative ref 已存在。
[roadmap decision] split epic into #42, #43, #44; reason: scope exceeds single-iteration threshold.
[roadmap decision] continue #78; reason: bounded enough for manager to plan inside one issue.
[roadmap decision] close #99; reason: dependency removed in #123, API deprecated.
[roadmap decision] hold #55 until #56 completes; reason: dependency graph constraint.
[roadmap decision] rfc #77; reason: cannot determine split shape without architecture input.
```

### 不合规示例

```
✗ "Manager: moving to in-progress"        # 无 marker，会被识别为人类
✗ "请尽快合并 [manager]"                  # marker 不在行首
✗ "评论里嵌入 [run] 字样作引用"           # 装饰性使用，会触发 agent 过滤
✗ [governance suggest] vibe-roadmap 写的  # vibe-roadmap 禁止使用此 marker
✗ [roadmap decision] intake 写的          # intake 禁止使用此 marker
```

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

**维护者**: Vibe Team  
**最后更新**: 2026-05-27
