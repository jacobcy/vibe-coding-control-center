# 治理闭环机制说明

**维护者**: Vibe Team  
**创建时间**: 2026-05-26  
**状态**: Active  

---

## 概述

本文档说明 Governance Observer → Roadmap Decider 的完整闭环机制，包括缓存和标签的工作方式。

---

## 角色分工

| 角色 | 文件 | Marker | 职责 | 标签 |
|------|------|--------|------|------|
| **Governance Observer** | supervisor/governance/roadmap-intake.md<br>supervisor/governance/assignee-pool.md | `[governance suggest]` | 观察者：扫描 issues，写建议，不入池 | 打 `orchestra-scanned` |
| **Roadmap Decider** | skills/vibe-roadmap/SKILL.md | `[roadmap decision]` | 决策者：消化建议，做决策，分配 assignee | 打 `roadmap-reviewed` |

---

## 完整闭环流程

```mermaid
graph TB
    Start[ Governance Scan 启动 ] --> CheckLabel{Issue 有 orchestra-scanned?}
    CheckLabel -->|Yes| Skip[跳过该 issue]
    CheckLabel -->|No| Scan[扫描 issue]
    
    Scan --> WriteSuggest[写 governance suggest 评论]
    WriteSuggest --> TagScanned[打 orchestra-scanned 标签]
    TagScanned --> StopObserver[Observer 停止]
    
    StopObserver --> UserTrigger[用户运行 /vibe-roadmap]
    UserTrigger --> Step0[Step 0: 搜索未处理的 suggest]
    
    Step0 --> FilterLabel{过滤已决策 issues}
    FilterLabel -->|有 roadmap-reviewed| SkipDecision[跳过]
    FilterLabel -->|无 roadmap-reviewed| ProcessSuggest[处理 suggest]
    
    ProcessSuggest --> WriteDecision[写 roadmap decision 评论]
    WriteDecision --> TagReviewed[打 roadmap-reviewed 标签]
    TagReviewed --> UpdateCache[更新 memory.md 缓存]
    UpdateCache | StopDecider[Decider 停止]
    
    StopDecider --> NextRun[下次运行]
    NextRun --> FilterLabel
    
    style TagScanned fill:#ff9933
    style TagReviewed fill:#cc99ff
    style WriteSuggest fill:#e1f5fe
    style WriteDecision fill:#f3e5f5
```

---

## 标签机制详解

### 1. orchestra-scanned 标签

**打标签时机**：Governance Observer 完成 issue 扫描后立即打标签

**执行位置**：
- `supervisor/governance/roadmap-intake.md` § "治理闭环标签"
- `supervisor/governance/assignee-pool.md` § "orchestra-scanned 标签要求"

**命令**：
```bash
gh issue edit <issue-number> --add-label "orchestra-scanned"
```

**作用**：
- 标记"已通过 governance observer 审查"
- 下次 governance 扫描自动跳过
- 实现 governance 层的闭环

**颜色**：FF9933（橙色）

---

### 2. roadmap-reviewed 标签

**打标签时机**：Roadmap Decider 写完 `[roadmap decision]` 评论后立即打标签

**执行位置**：
- `skills/vibe-roadmap/SKILL.md` § Step X (Intake 判断)
- `skills/vibe-roadmap/SKILL.md` § Comment Marker Contract

**命令**：
```bash
gh issue edit <issue-number> --add-label "roadmap-reviewed"
```

**作用**：
- 标记"已通过 roadmap decider 决策"
- 下次 Step 0 自动跳过已决策 issues
- 实现 roadmap 层的闭环

**颜色**：CC99FF（淡紫色）

---

## 缓存机制详解

### .agent/context/memory.md

**用途**：存储 `/vibe-roadmap` 每次分析结果

**内容结构**：
```markdown
# Roadmap Analysis Cache

## 2026-05-26 Analysis

### Step 0: 消化未处理的 Governance Suggest
- 上次决策锚点
- 已处理的 suggest 清单
- 按优先级分组

### Step 1-3: 新 Issues Intake
- 通过三级审查的 issues
- 已分配的标签和 assignee

### Step 4: 输出路线图状态
- P0/P1/P2/RFC 分类

### 下次运行指引
- 上次决策锚点时间
- 需要处理的 issues 范围
```

**读取时机**：`/vibe-roadmap` 启动时（可选，用于快速定位锚点）

**写入时机**：Step 4 完成后

**git 状态**：不纳入 git 追踪（.gitignore），本地缓存专用

---

## 闭环检查清单

### ✅ Governance Observer 侧

**roadmap-intake.md**：
- ✅ 有"治理闭环标签"章节（§ 末尾）
- ✅ 明确说明打 `orchestra-scanned` 标签
- ✅ 提供命令示例：`gh issue edit <issue-number> --add-label "orchestra-scanned"`

**assignee-pool.md**：
- ✅ 有"orchestra-scanned 标签要求"章节（§ 380）
- ✅ 明确要求：发布评论后**必须**立即添加标签
- ✅ 更新去重规则：检查 `orchestra-scanned` 标签

**执行顺序检查**：
```
扫描 issue → 写 [governance suggest] 评论 → 打 orchestra-scanned 标签 → 停止
```

**问题**：❌ 需要确认 agent 是否**真的执行**打标签动作（文档有说明，但实际执行可能遗漏）

---

### ✅ Roadmap Decider 侧

**vibe-roadmap/SKILL.md**：
- ✅ Step 0 有搜索逻辑（§ 290-313）
- ✅ Step 0 有标签过滤逻辑（`select(.labels | map(.name) | index("roadmap-reviewed") | not)`）
- ✅ Step X 有打标签动作（§ 447, 465, 479）
- ✅ Comment Marker Contract 有打标签说明（§ 338-340）

**执行顺序检查**：
```
Step 0 搜索 → 过滤已决策 → 处理 suggest → 写 [roadmap decision] 评论 → 打 roadmap-reviewed 标签 → 更新缓存
```

**问题**：⚠️ Step 0 的搜索逻辑有**两种方式**（标签过滤 vs 时间戳比对），需要明确优先级

---

### ✅ 已改进的地方

#### 1. Governance Observer 执行验证

**问题**：文档有说明，但不确定 agent 是否真的执行打标签

**解决方案**：已在 `supervisor/governance/` 中添加明确的 Stop Point Checklist：

```markdown
## Stop Point Checklist（强制）

完成以下动作后才能停止：
- [ ] 写完 [governance suggest] 评论
- [ ] 打上 orchestra-scanned 标签
- [ ] 确认标签已添加（可选：gh issue view 验证）

**缺少标签的后果**：下次扫描会重复处理同一 issue，造成资源浪费
```

**修改文件**：
- ✅ `supervisor/governance/assignee-pool.md`
- ✅ `supervisor/governance/roadmap-intake.md`

#### 2. Step 0 搜索逻辑明确化

**问题**：当前有两种方式，需要明确优先级

**当前文档**：
```bash
# 方式 A: 使用标签过滤（推荐）
gh search issues '[governance suggest]' --match comments \
  | select(.labels | map(.name) | index("roadmap-reviewed") | not)

# 方式 B: 时间戳比对（fallback）
```

**建议**：明确标注执行顺序
```markdown
**优先级**：
1. **方式 A（标签过滤）**：优先使用，效率高
2. **方式 B（时间戳比对）**：仅用于验证或 fallback
```

#### 3. 缓存读取时机不明确

**问题**：memory.md 文档没说明何时读取

**建议**：在 Step 0 增加说明
```markdown
**可选前置步骤**：读取 `.agent/context/memory.md` 快速定位上次决策锚点
```

---

## 验证方法

### 1. 验证 orchestra-scanned 标签

**Governance Observer 运行后**：
```bash
# 检查最近处理的 issue 是否有 orchestra-scanned 标签
gh issue view <issue-number> --json labels --jq '.labels | map(.name)'
```

**预期**：应该包含 `orchestra-scanned`

---

### 2. 验证 roadmap-reviewed 标签

**Roadmap Decider 运行后**：
```bash
# 检查已决策的 issue 是否有 roadmap-reviewed 标签
gh issue view <issue-number> --json labels --jq '.labels | map(.name)'
```

**预期**：应该包含 `roadmap-reviewed`

---

### 3. 验证 Step 0 过滤逻辑

**下次运行 `/vibe-roadmap`**：
```bash
# Step 0 应该不包含已决策的 issues
# 可以在输出中检查是否有 "跳过已决策 issue" 的日志
```

---

## 完整示例

### Governance Observer 流程

```bash
# 1. 扫描 issue
gh issue view 123 --json title,body,labels,comments

# 2. 写评论
gh issue comment 123 --body "[governance suggest] Intake: ..."

# 3. 打标签（关键！）
gh issue edit 123 --add-label "orchestra-scanned"

# 4. 停止
```

---

### Roadmap Decider 流程

```bash
# Step 0: 搜索未处理的 suggest
gh search issues '[governance suggest]' --match comments --limit 50 \
  --json number,labels,title \
  --jq '.[] | select(.labels | map(.name) | index("roadmap-reviewed") | not)'

# Step 1-3: 处理 suggest
# 写决策评论
gh issue comment 123 --body "[roadmap decision] assign to vibe-manager-agent"

# 打标签（关键！）
gh issue edit 123 --add-label "roadmap-reviewed"

# Step 4: 更新缓存
echo "## $(date +%Y-%m-%d) Analysis\n..." >> .agent/context/memory.md
```

---

## 总结

**闭环机制**：
1. ✅ Governance Observer 打 `orchestra-scanned` → 避免重复扫描
2. ✅ Roadmap Decider 打 `roadmap-reviewed` → 避免重复决策
3. ✅ memory.md 缓存 → 快速定位锚点

**待改进**：
1. ⚠️ 需要验证 agent 是否真的执行打标签动作
2. ⚠️ Step 0 搜索逻辑需要明确优先级
3. ⚠️ 缓存读取时机需要明确说明

**建议下一步**：
1. 运行一次 governance scan，验证是否打标签
2. 运行一次 `/vibe-roadmap`，验证 Step 0 是否过滤已决策 issues
3. 更新文档明确执行顺序和检查点

---

**维护者**: Vibe Team  
**最后更新**: 2026-05-26
