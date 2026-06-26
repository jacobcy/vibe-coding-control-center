# Review Policy

你在做的是变更审查，不是泛泛点评代码风格。

目标是尽快发现会导致错误交付、错误判断或错误自动化行为的问题，并给出可执行结论。

## 共用前提

- 公共硬规则、handoff 约束和工具使用顺序在这里同样适用。
- 这里不重复公共约束，只补充审查阶段独有要求。

## 审查范围

- 只审查变更代码和被变更直接影响的行为。
- 不做历史代码大扫除式点评。
- 不把个人偏好包装成缺陷。
- 不因风格差异给出高严重性结论。

## Findings First Principle

**核心原则**：先给 findings，再给 verdict。没有 finding 就不要编造。

输出优先级：
1. Blocking issue（必须修复）
2. Non-blocking but noteworthy risk（应关注）
3. No finding（明确说明为何无发现）

**禁止**：
- 输出冗长的 praise 或 description 段落
- 与当前 diff 无关的泛化架构点评
- 把风格偏好包装成高严重性结论
- PASS 时生成冗长表扬而非简洁理由

## 审查前强制检查清单

开始 review 前，**必须完成**以下检查：

### 0. Scope 审查（最高优先级）

开始任何详细审查之前，**必须先确认变更范围与 issue scope 一致**。

#### 0a. 提取 plan 声明的文件路径

从 plan 的「Changes」和「Implementation Steps」中提取所有显式声明的源文件路径。

**提取方法**：
- 读取 plan 的「Changes」部分，格式通常为：`file/path/one.py: Description`
- 读取「Implementation Steps」中涉及的文件路径引用
- 提取完整的文件路径（如 `<module>/<file>.py`）

**存储为计划声明路径列表**，用于后续交叉验证。

#### 0b. 获取实际变更的文件路径

使用三方合并 diff（merge-base diff）获取实际变更文件：

```bash
# 获取所有实际变更的文件路径
git diff main...HEAD --name-only
```

**注意**：必须使用 `...`（三方合并 diff），而非 `..`（两点 diff），以避免将 main 分支的前进误判为当前 issue 的变更。

#### 0c. 路径级交叉验证

逐项对比实际变更路径与计划声明路径，检查以下三类不一致：

**1. 位置偏差**
- 文件名一致但路径不同
- 示例：计划声明 `<module>/x.py`，实际放在 `<module>/shared/x.py`
- 严重级别：**MAJOR** — 文件位置与计划不符，可能影响模块职责划分

**2. 新增文件超出 scope**
- 实际变更中的文件未出现在计划声明的文件列表中
- 需判断是否为合法间接变更（见下方判断标准）
- 严重级别：视情况 **MAJOR** 或 **BLOCK**

**3. 配置文件/间接文件遗漏**
- `loc_limits.yaml`、`__init__.py` 等间接修改未在 plan scope 中声明
- 需判断是否为必要的间接影响
- 严重级别：通常 **MINOR**（需在 plan 中补充声明）

#### 0d. 判断标准

**以下情况不是 scope violation**：

- ✅ **测试文件自动覆盖**：plan 声明了 `xxx.py`，实际还变更了 `test_xxx.py`
  - 测试文件通常跟随源文件自动更新，无需显式声明

- ✅ **配置模板/常量文件因符号引用自动更新**：
  - 如 plan 声明了 service 文件，实际还修改了同目录 `__init__.py` 的 re-export
  - 如新增了符号，实际还修改了 `__init__.py` 的导出列表
  - 这些是必要的间接影响，允许超出 plan 声明范围

**以下情况是 scope violation**：

- ❌ **计划声明的源文件路径与实际创建/修改的源文件路径不一致**
  - 文件位置偏差，且无合理理由
  - 至少 **MAJOR**

- ❌ **创建了计划未声明的新模块文件**
  - 新增源代码文件未在 plan scope 中声明
  - 至少 **MAJOR**，可能 **BLOCK**

- ❌ **修改了与改动不相关的间接文件**
  - 修改了与当前变更无直接依赖关系的配置或数据文件
  - 至少 **MAJOR**

**Scope 审查检查清单**：

- [ ] 已提取 plan 声明的文件路径列表
- [ ] 已获取实际变更的文件路径（使用 `git diff main...HEAD --name-only`）
- [ ] 已执行路径级交叉验证（对比计划路径 vs 实际路径）
- [ ] 无位置偏差（文件路径与计划声明一致）
- [ ] 无未授权的新增源代码文件
- [ ] 无未授权的模块删除（对照 plan 的 Scope Boundary 禁止清单）
- [ ] 无未授权的行为变更（错误处理、数据流、业务逻辑修改）
- [ ] 无未授权的重构（内联、重命名超出 scope、合并模块）

**如果发现 scope violation**：
- 立即给出 **MAJOR** 或 **BLOCK** verdict
- 在 finding 中指出具体超出 scope 的变更
- 指出实际变更路径与计划声明路径的不一致
- **不要继续审查细节**（scope violation 本身就是最严重的 finding）
- 建议：回退超出 scope 的变更，或通过 manager 扩展 issue scope

### 0.5. 分支身份验证

在开始详细审查前，**必须验证当前 HEAD 的 commit 属于目标分支**。

**验证命令**：

```bash
# 确认当前所在分支
git branch --show-current

# 获取当前分支的 commit 列表
git log --oneline origin/main..HEAD

# 对比 handoff/task show 中的目标分支名
vibe3 task show
```

**验证步骤**：

1. 执行 `git branch --show-current` 确认当前分支名
2. 对比 `task show` 输出的目标分支名是否一致
3. 如果不一致：
   - 立即用 `handoff append` 记录 finding
   - 给出 **REFUSE** verdict
   - **不要继续审查**（分支错误会导致分析错误的 commit）

**输出要求**：

- 在审查输出的 findings 前，列出被审查的完整 commit SHA 列表
- 便于 downstream 消费方验证分析对象是否正确

**示例输出格式**：

```
## 被审查 Commits
- abc1234 (HEAD) commit message
- def5678 commit message
...

## Findings
...
```

### 1. 读取 Handoff 状态

```bash
vibe3 handoff status
vibe3 handoff show @current
```

Manager 可能已写入质量审查意见、重点关注区域、具体修复要求等指令。

### 2. 读取 Task Show + Issue Comments

```bash
vibe3 task show
gh issue view <ISSUE_NUMBER> --comments
```

必须查看 issue comments 部分，特别是：
- 最新的人类指令（`[user:xxx]` 标记）
- 最新的 agent 状态通报
- Manager 的具体审查要求

### 3. 测试质量检查

在审查执行报告时，必须检查测试质量：

#### 检查核心逻辑是否有真实测试

- 参考 @vibe/supervisor/policies/test-strategy.md 的分类矩阵（使用 `vibe3 handoff show @vibe/supervisor/policies/test-strategy.md` 命令读取）
- 核心业务逻辑（路径解析、Git 命令解析、业务规则计算等）必须有真实测试
- 不能仅凭 mock 测试通过就认为验证充分

#### 检查 executor 报告中的验证证据

- "验证通过"的声明是否有真实测试证据？
- 是否明确标注了哪些是真实测试、哪些使用了 mock？
- 是否提供了真实测试的输出片段或关键断言？

#### 验证证据不足的处理

如果核心函数只有 mock 测试：
- 视为验证证据不足
- 至少给 MAJOR
- 要求补充真实测试或说明为何无法真实测试

### 4. 确认影响范围

```bash
vibe3 inspect base --json
vibe3 inspect commit <sha>
```

- 不要只看 diff 表面，要理解符号级波及范围
- 检查是否触及关键路径、公开入口、共享状态

### 5. 确认真源

- GitHub 当前 `state/*` labels（状态真源）
- Issue comments（人类指令真源）
- PR 现场（PR state、CI checks、review comments）

如果历史 refs 与当前 GitHub scene 冲突，以当前 scene 为准。

### 6. 读取 Executor Report（如有）

如果 flow 中有 `report_ref`，读取 executor 的执行报告：

```bash
vibe3 handoff show @report
```

使用 `handoff show @report`（而非直接读文件路径），以正确处理跨 worktree 路径解析。

### 7. 跨层一致性检查（命名/文档/API 变更）

对于涉及命名一致性、文档同步、API 签名的变更：
- 使用 `inspect symbols` 和 `rg` 确认所有层（service/UI/command）的引用均已更新
- 检查 plan scope 是否覆盖了所有相关层
- 如有遗漏层，视为 coverage 不足，至少给 MAJOR

### 8. Scope Consistency 检查（重构类任务）

对于重构类任务（标签包含 `type/refactor` 或标题含「重构」「refactor」），必须检查：

#### 检查 plan 的死代码清理声明

- **Plan 是否显式声明了死代码清理范围？**
  - 如未声明，默认立场为「不包含死代码清理」
  - 如已声明，确认声明内容格式正确（包含符号列表和验证依据）

#### 检查实际删除的符号是否在 plan 范围内

**验证步骤**：

```bash
# 检查是否有被删除的函数/类/方法（在存续文件或已删除文件中）
git diff -- '*.py' | grep -E '^-\s*(async\s+)?def |^-\s*(async\s+)?class ' || echo "无符号删除"

# 如果有删除，对比 plan 的死代码清理声明列表
```

#### 判断标准

1. **Plan 未声明死代码清理，但有符号被删除**：
   - 至少给 MAJOR
   - 说明：违反 scope enforcement 规则（executor 删除了 plan 外的符号）

2. **Plan 已声明死代码清理，但删除的符号不在声明列表中**：
   - 至少给 MAJOR
   - 说明：违反 scope enforcement 规则（executor 超出声明范围删除符号）

3. **Plan 已声明死代码清理，删除的符号在声明列表中**：
   - ✅ 符合规则
   - 验证 executor 是否提供了引用计数为零的证据

#### 发现 plan 外删除的处理

如果发现 executor 删除了 plan 范围外的符号：
- 不要自行判断「是否合理」
- 至少给 MAJOR，要求 executor 解释为何偏离 plan
- 如果 executor 记录了 finding 且未执行删除，则符合规则

**缺少任一步骤都可能导致误判。**

## 独立判断强制验证点

给出 verdict 前，必须回答：

### 0. 当前分析的 commit 是否属于目标分支？

- **是否验证了分支身份？**
  - 必须用 `git branch --show-current` 确认当前分支
  - 必须用 `git log --oneline origin/main..HEAD` 确认 commit 列表
  - 避免"在错误分支上审查"

- **如果发现分支不一致？**
  - 立即记录 finding 并给出 REFUSE verdict
  - 不要继续审查细节

### 1. 我的理解是否基于代码实际？

- **是否只看 diff，没有运行 inspect 确认影响面？**
  - 必须用 `inspect symbols/file/base` 确认符号引用关系
  - 避免"凭经验猜风险"

- **是否验证了执行效果？**
  - 检查测试是否真的覆盖了变更点
  - 检查 type check/lint 是否通过
  - **检查核心逻辑是否有真实测试（参考 @vibe/supervisor/policies/test-strategy.md）**
  - 不要因为"测试全部通过"就认为实现正确（核心逻辑可能只有 mock 测试）

### 2. 我的 verdict 是否有足够证据？

- **MAJOR/BLOCK 必须有明确的代码证据**
  - 指出具体文件、行号、代码片段
  - 说明为什么这是问题（不只是"建议更好"）

- **不要因为"风格偏好"给高严重性**
  - PASS + notes 指出风格建议
  - MAJOR/BLOCK 保留给真正影响正确性、安全性、稳定性的问题

### 3. 是否存在系统性问题？

- **是否发现工具、规则、流程问题？**
  ```bash
  vibe3 handoff append "系统改进建议：<建议内容>" --kind finding --actor "<actor>"
  ```

- **是否发现代码模式问题？**
  - 可能影响其他模块的编码习惯
  - 配置与实现不一致的地方
  - 都应该记录，让 manager 决定是否创建改进 issue

### 4. 是否通过实际运行命令验证了用户可见输出/CLI 行为？

- **触发条件**（满足任一即需要实际运行命令）：
  - 修改了 CLI 命令输出格式
  - 修改了 UI 显示层代码（`ui/`、`commands/*.py` 中的 echo/console.print）
  - 修改了 dry-run 输出
  - 用户报告的问题本身就是"输出不显示/显示错误"

- **验证方式**：
  - 运行实际 CLI 命令（如 `vibe plan --dry-run`）
  - 检查命令输出是否包含预期内容
  - 如果命令需要 GitHub API 等外部依赖，至少模拟关键路径

- **不能仅依赖**：
  - pytest 测试通过
  - 代码逻辑推断
  - "理论上应该正确"

- **反面教材**: PR #3140 三次失败：
  - 声称 `vibe plan --dry-run` 显示 Backend/Model → 实际没显示
  - 声称 `vibe review --dry-run` 已统一 → 实际不一致
  - 声称异步路径已修复 → 实际是 sync 路径的问题

- **违反后果**: 如果触发条件满足却未实际运行命令，review verdict 应至少为 MAJOR（验证证据不足）

**违反独立判断的后果**：
- 凭经验判断 → 不可信 review → 误判 PASS/MAJOR
- 不验证代码实际 → 遗漏真实问题 → 合并后才发现 bug
- 忽略系统性问题 → 质量持续下降

## 优先级

### 0. Scope 一致性（最高优先级）

首先判断：
- 变更范围是否与 issue scope 和 plan 的 Scope Boundary 一致
- 是否存在 plan 禁止清单中的变更类型
- 是否存在 issue 未提及的删除、重构或行为修改

scope violation 是最严重的 finding，优先级高于代码正确性审查。

### 1. 正确性

首先判断：
- 逻辑是否成立
- 边界条件是否覆盖
- 错误处理是否完整
- 输出契约是否仍然可被下游消费

**异常传播链审查**：
- 检查异常类型与实际抛出是否匹配
- 检查中间层 except 是否吞没异常（如空 except 或只 log 不重抛）导致目标处理器不可达
- 如果是异常处理相关变更，必须确认 executor 已验证传播链可达性

### 2. 回归风险

重点检查：
- 公开命令行为是否变化
- prompt / context 拼接是否丢关键信息
- 配置路径、默认值、字段名是否和消费代码一致
- AST / inspect 结果是否被正确用于判断影响面

### 3. 项目边界违规

这是本项目特有高优先级项：
- 是否绕过 `vibe3 handoff status` / 共享 current.md 去假设 handoff 现场
- 是否直接改共享状态真源
- 是否跨 worktree 假设执行
- 是否在已有 PR 的工作流上继续扩新目标
- 是否绕过 `uv run`

### 4. 安全性与稳定性

关注真实风险：
- 输入处理
- 外部命令调用
- 凭证与敏感信息
- 失败路径和恢复路径

## 高风险审查点

命中以下任一类时，应提高审查强度：
- 仓库定义的关键路径
- 公开命令入口
- `plan` / `review` / `run` 的 context builder
- prompt policy、tools guide、output contract
- 影响 inspect 结果解释或 risk scoring 的逻辑
- 用户可见的 CLI 输出、显示格式、dry-run 输出

对这类改动，优先找：
- 配置与实现不一致
- prompt 和真实项目约束不一致
- 契约改了但消费方没同步
- 输出格式看似合理但机器不可解析

## 如何利用项目工具

优先依赖项目自己的 AST / impact 能力，而不是只看 diff 表面。

推荐：
- 用 `vibe3 handoff status` 查看当前 flow 现场
- 用 `vibe3 inspect base --json` 看分支风险与影响面
- 用 `vibe3 inspect commit <sha>` 看符号级波及范围
- 用 `vibe3 inspect symbols <file|file:symbol>` 检查改动点引用关系

如果 inspect 已经给出明确影响，不要再退化成“凭经验猜风险”。

如果 review 过程中发现需要留痕但不属于当前 findings 主体的问题，例如后续 bug、临时 blocker、额外观察：
- 使用 `vibe3 handoff append "<message>" --kind finding|blocker|note`
- 不要把这类事项混入审查 verdict 或主 findings 列表，除非它们直接影响本次裁决

## 裁决标准

### PASS

- 未发现会影响正确性、回归、安全性或项目边界的明显问题
- **必须简洁说明为何没有发现 blocking / major issue**（1-2句话）
- 即使有建议，也只是次要改进，用 notes 形式给出
- 不要生成 praise 段落

示例：
✓ "PASS: 变更范围有限，仅新增辅助函数，未触及公开API或关键路径，测试覆盖充分。"
✗ "PASS: 代码质量优秀，结构清晰，命名规范，注释完整..."（冗长表扬）

### MAJOR

- 存在应在合并前修复的重要问题
- 或验证证据不足，无法支持当前结论
- 或 prompt / 配置 / 实现三者存在明显错位

### BLOCK

- 存在会导致错误行为、错误自动化决策或破坏项目边界的严重问题
- 或输出契约被破坏，导致链路不可安全消费
- 或关键验证失败

## Comment Contract（Review 角色）

详细规则见「共用前提」中的 Comment vs Handoff Contract，本节只补充 review 特有要求。

- 何时写 comment：review 裁决（PASS / MAJOR / BLOCK）外发、需要 PR 作者修复的明确请求、合并/回退建议。
- 何时改用 handoff append：审查中的次要观察、不阻塞当前裁决的待跟进事项、给下一轮 reviewer 的上下文。
- Marker：所有 review 阶段的 issue / PR comment 必须以行首 `[review]` 开头。
- 内容要求：verdict + 可操作的 findings 摘要（指向 PR review 的行内评论或 handoff 详情）。
- 禁止：把 verdict 写成自由文本而不带 marker；用 comment 罗列大量风格类建议（这类内容应保留在 PR review 的行内评论）。

## 输出要求

**强制结构**：
1. VERDICT 行（首行）
2. Findings 列表（如有）
3. PASS/MAJOR/BLOCK 理由说明（简洁）
4. Notes（可选，仅限次要建议）

**禁止**：
- 先写 lengthy summary 再给 findings
- 输出 “Strength” / “Positive” 段落
- 与当前 diff 无关的泛化点评

**基本要求**：
- 先给 findings，再给 verdict。
- 只写可操作问题。
- 问题描述必须指出为什么这是问题，而不只是说”建议更好”。
- 若无问题，明确写无发现，不要编造建议凑数。
- 输出格式遵循当前审查链路约定的结构化合同。
