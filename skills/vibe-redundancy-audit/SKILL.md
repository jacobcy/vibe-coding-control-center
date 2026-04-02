---
name: vibe-redundancy-audit
description: Use when the user wants to find suspicious redundant business logic, repeated implementation patterns, stale compatibility paths, or low-quality code that should be reviewed for consolidation, reuse, or retirement. Do not use for automatic cleanup or direct code deletion.
---

# Vibe Redundancy Audit

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

**核心职责**: 发现可疑的冗余业务逻辑、重复实现模式、迁移后残留路径和低质代码信号，并输出人工复核所需的报告与建议文档。

语义边界：

- 本 skill 只做只读审查，不自动清理代码，不直接删除逻辑，不直接修改共享状态。
- 本 skill 关注的是“业务语义冗余”和“分层职责重复”，不是单纯做文本去重。
- 本 skill 输出的是 `可疑点`、`证据`、`建议`，不是自动下结论”这段代码必须删除”。
- 本 skill **必须**将审查结果写入 handoff，确保下游 agent 可追溯。
- 若用户要直接评审某次代码改动的正确性或回归风险，优先使用 `vibe-review-code`。

## 目标

本 skill 的目标不是机械地找死代码，而是尽可能提升代码质量，持续发现并暴露以下问题：

- 重构后新旧路径并存，但旧逻辑没有及时回收
- command / usecase / service / client 之间职责漂移，形成重复编排
- 相似业务判断在多个模块重复实现，而没有沉淀成共享能力
- 兼容分支、历史 alias、临时 fallback 长期滞留，演变成隐性业务逻辑
- 局部看都合理，但整体让代码库持续膨胀、复用下降、认知负担上升
- **过度设计**：为了解决一个简单问题引入了不必要的抽象层、状态机、标志位或中间件。特征是"为了 X 而 Y，但 Y 本身比 X 更复杂"。发现后只标记，由人类确认是否简化

## 核心原则

1. **认知优先，证据先于结论**
   - 任何“冗余”“过时”“重复”的判断都必须建立在结构、调用面、改动范围和职责边界的组合证据上。
2. **关注业务语义冗余，不只看文本相似**
   - 重点识别重复的业务判断、编排顺序、错误翻译、兼容语义和边界处理。
3. **分层边界是主要审查坐标**
   - 优先检查 command、usecase、service、client 是否重复承担 orchestration 或业务决策。
4. **对迁移残留保持高敏感**
   - 只要出现“新能力已引入，但旧路径仍保留大部分业务逻辑”，就应列为高价值可疑点。
5. **复用优先于继续复制**
   - 当相似模式已经稳定存在，优先提出“是否应提炼共享能力”，而不是只报“代码相似”。
6. **兼容入口默认可疑，但不默认错误**
   - alias、deprecated 命令、fallback 分支需要重点复核，但必须保留人工确认环节。
7. **没有验证证据，不得声称确认冗余**
   - 本 skill 只能提出嫌疑点，不能把可疑点伪装成已确认问题。

## 项目特有的方法

本 skill 体现的是 Vibe 项目自己的冗余逻辑审查方法，不是通用 dead code 教程。

本项目的理想结构是：

- command 层暴露能力，不承载过多业务编排
- usecase 层收敛命令侧 orchestration
- service / client 层保持单能力组件
- 相似能力优先沉淀为共享实现，而不是在多个入口平行复制

因此，本 skill 的审查重点是：

- `thin commands` 是否真的变薄，而不是只“多加一层”
- 新 usecase 引入后，旧 command 业务逻辑是否仍大量残留
- 共享能力是否真正被复用，还是只复制出第二份实现
- 兼容路径是否仍有现实保留价值，还是已经演变为历史包袱

## 内建分析能力

本 skill 必须优先使用仓库真源里的 V3 CLI 能力做证据收集，默认使用兼容写法：

```bash
uv run python src/vibe3/cli.py <subcommand>
```

重点使用以下能力：

- `vibe3 inspect base --json`
  - 识别当前分支相对 base 的核心改动面、公开入口触达范围和 changed symbols。
- `vibe3 inspect commit <sha> --json`
  - 识别某次提交引入的结构波及面和关键符号变化。
- `vibe3 inspect files <file> --json`
  - 识别文件形状：LOC、函数数、导入关系、是否存在“迁移后仍很重”的模块。
- `vibe3 inspect symbols <file>:<symbol> --json`
  - 验证具体符号的真实调用面，确认兼容入口、helper、旧路径是否仍被实际引用。
- `vibe3 snapshot show <file> --json`
  - 补充文件级结构信息，用于说明模块复杂度和函数分布。

补充说明：

- `inspect files` / `snapshot show` 适合发现“形状异常”和“分层仍过厚”的嫌疑点。
- `inspect symbols` 更适合作为二次验证器，而不是唯一发现器。
- `inspect base` / `inspect commit` 用来回答“这次重构是否同时新增新路径但未回收旧路径”。

## 触发时机

- 用户要求检查重复模式、冗余业务逻辑、历史残留、过时兼容逻辑
- 用户担心某次拆分或重构“越拆越大”，想确认旧实现是否没删干净
- 用户想找出适合提炼共享能力的低质重复实现
- 用户要产出“可疑点报告”或“建议文档”，但明确不自动清理

## 审查流程

1. 先用 `inspect base` 或 `inspect commit` 锁定本次改动范围与重点文件。
2. 对重点文件运行 `inspect files` 或 `structure show`，识别以下信号：
   - 文件仍然过胖
   - 子命令/函数数量仍过多
   - 新旧层并存
   - 依赖面异常扩大
3. 对可疑函数、兼容入口、helper、新 usecase 入口运行 `inspect symbols`，确认调用面。
4. 结合分层边界判断问题类型：
   - 迁移后残留
   - 重复编排
   - 可疑兼容逻辑
   - 共享能力缺失
   - 疑似无人使用的业务逻辑
5. **发现即止：3 个可疑点后立即写报告**
   - 发现 3 个疑似问题后，停止搜索，立即输出报告并写 handoff。
   - 不要为了"找全"而无限搜索——本 skill 的价值在于快速暴露问题，不是穷举。未覆盖的区域留待下一轮审查。
6. 输出可疑点报告，并在需要时生成建议文档。
7. **Handoff 记录（强制）**：审查完成后，**必须**使用标准 handoff 命令记录结果：
   ```bash
   # a. 将完整报告写入 .agent/reports/ 目录

   # b. 记录审计事件
   vibe3 handoff audit "<报告文件路径>" \
     --next-step "下一步建议" \
     --actor "<actor标识>"

   # c. 用 handoff append 记录关键发现和下一步
   vibe3 handoff append "发现摘要: ..." --actor "<actor标识>" --kind finding
   vibe3 handoff append "下一步: ..." --actor "<actor标识>" --kind next
   ```
   **不得跳过此步骤**。handoff 是下游 agent（如 spec agent、执行 agent）获取审查结果的唯一标准通道。

可疑点分类说明见 `references/suspicion-signals.md`。

## 输出契约

输出必须分成三个层次：

### 1. 可疑点报告

每个可疑点必须包含：

- `location`
- `suspicion_type`
- `why_flagged`
- `evidence`
- `manual_check`

### 2. 建议文档

当用户要求落文档时，生成一份建议文档，归纳：

- 哪些地方适合合并为共享能力
- 哪些旧路径应评估退役
- 哪些兼容逻辑需要补保留理由
- 哪些模块说明分层已经开始漂移

建议文档是审查建议，不是清理执行单。

### 3. Handoff 记录（强制，不可跳过）

审查完成后，**必须**使用标准 handoff 命令将结果写入 handoff：

```bash
# 记录审计事件（引用报告文件）
vibe3 handoff audit "<报告路径>" --next-step "..." --actor "<actor标识>"

# 记录关键发现
vibe3 handoff append "发现摘要: ..." --actor "<actor标识>" --kind finding

# 记录下一步建议
vibe3 handoff append "下一步: ..." --actor "<actor标识>" --kind next

# 记录阻塞项（如有）
vibe3 handoff append "阻塞: ..." --actor "<actor标识>" --kind blocker
```

完整报告存入 `.agent/reports/` 目录。不写 handoff 的审查结果视为未完成。

## 严格禁止

- 不自动删除代码
- 不自动修改实现
- 不直接改 `.git/vibe*` 或其他共享状态真源
- 不把“可疑点”描述成“已确认冗余”
- 不因为 `inspect symbols` 显示 0 引用就直接下结论，必须结合 CLI 入口、兼容性和分层语义人工判断
