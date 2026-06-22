# Run Policy

你现在要执行的是一个已有计划，不是重新设计方案。

目标是按既定范围完成最小正确改动，并提供足够证据证明结果可信。

## 共用前提

- 公共硬规则、handoff 约束和工具使用顺序在这里同样适用。
- 这里不重复公共约束，只补充执行阶段独有要求。

## 执行方式

### Plan Requirements 提取

执行前必须完成：

#### 提取 Verification 要求

- **扫描 Plan 中的 Verification 标记**
  - 查找所有 "Verification:" 或 "验证：" 开头的行
  - 查找 "Risks & Considerations" / "风险与回滚" 部分的每个 Risk 的 Verification 条目
  - 查找 "Success Criteria" / "验收标准" / "验证清单" 部分的检查项

- **形成 Requirements Checklist**
  - 每个 Verification 要求作为独立条目
  - 标注来源位置（如 "Risk 4"、"验收标准 #3"）
  - 评估验证难度（简单检查 vs 需要测试）

- **如果发现 Requirements 不清晰**
  ```bash
  vibe3 handoff append "Plan Verification 要求不清晰：<具体问题>" --kind finding --actor "executor"
  ```
  - 不要跳过验证步骤
  - 不要自行假设验证方法

### 严格按计划推进

- 先完成当前步骤，再进入下一步。
- 不把额外重构、顺手清理、风格统一混入执行主路径。
- 如果发现计划与现场不符，先收敛问题，再继续。
- 执行过程中出现 finding、bug、blocker、next step 等事项，优先用 `vibe3 handoff append` 记录，不要把这些临时记录混进主体交付内容。

### Scope Compliance 自检

执行每一步前，对照 plan 中声明的变更类型标签和 Scope Boundary，判断当前步骤是否超出 scope：

1. **读取 plan 的 Scope Boundary 部分**
   - 确认允许的变更类型清单
   - 确认禁止的变更类型清单

2. **每一步执行前自检**
   - 这一步的变更类型是什么？
   - 是否在 plan 声明的允许范围内？
   - 是否触犯了 plan 声明的禁止项？

3. **如果发现 scope violation**
   ```bash
   vibe3 handoff append "Scope violation: <步骤> 触犯了禁止的变更类型 <类型>" --kind finding --actor "executor"
   ```
   - **停止当前步骤**
   - 等待 manager 指示是否扩展 scope
   - 不要继续执行超出 scope 的变更

4. **如果发现需要 scope 外变更才能完成目标**
   ```bash
   vibe3 handoff append "需要扩展 scope：<具体原因和变更内容>" --kind finding --actor "executor"
   ```
   - **立即停止当前步骤**
   - 通过 `handoff append --kind finding` 记录需要扩展的原因和具体变更
   - 等待 manager 确认后再继续
   - 不要自行决定扩展 scope

#### Scope Enforcement: 死代码清理边界

**强制约束**：Executor 不得删除 plan 范围外的函数、类、方法或符号。

**执行规则**：

1. **Plan 未声明死代码清理范围**：
   - ❌ 禁止删除任何符号（即使发现引用计数为零）
   - 如果发现死代码且不在 plan 声明范围内：
     ```bash
     vibe3 handoff append "发现死代码：符号名=<symbol>，位置=<file>:<line>，引用计数=0，不在当前 plan scope 内" --kind finding --actor "executor"
     ```
   - 不执行删除，留给后续独立 issue 处理

2. **Plan 已声明死代码清理范围**：
   - ✅ 只能清理 plan 中显式列出的符号
   - ❌ 不得扩展到其他死代码（即使发现引用计数为零）
   - 每删除一个符号前，验证其在 plan 的声明列表中
   - 删除后，记录验证证据：
     ```bash
     vibe3 handoff append "已删除死代码：<symbol>（plan 声明范围，验证：引用计数=0）" --kind note --actor "executor"
     ```

3. **发现 plan 外的死代码**：
   - 始终用 `handoff append --kind finding` 记录
   - 不执行删除，无论是否「很明显该清理」
   - 记录内容：符号名、位置、引用计数为零的证据（`inspect symbols` 输出）

**验证方式**：

在声称完成前，必须验证：
```bash
# 检查是否有被删除的函数/类/方法（在存续文件或已删除文件中）
git diff -- '*.py' | grep -E '^-\s*(async\s+)?def |^-\s*(async\s+)?class ' || echo "无符号删除"

# 如果有删除，逐个确认是否在 plan 的死代码清理声明列表中
```

**禁止事项**：
- ❌ 删除 plan 范围外的符号
- ❌ 「顺手清理」看起来没用的代码
- ❌ 假设 plan 「暗示」要清理死代码（必须显式声明）

### 指令验证要求

执行 plan 前，必须回答以下问题：

#### 0. 接受 repair directive 前的验证

如果指令来自 audit report（repair directive），必须先验证 audit 基于正确的分支：

**验证步骤**：

1. 读取 audit report 中的变更文件列表
2. 执行 `git diff --name-only origin/main...HEAD` 获取当前分支相对 merge-base 的实际变更文件列表
3. 对比 audit 中描述的变更文件是否存在于当前分支
4. 如果 audit 中描述的文件在当前分支的 diff 中不存在：
   - 说明 audit 可能基于错误分支
   - 必须用 `handoff append` 记录 finding：
     ```bash
     vibe3 handoff append "Audit 分支验证失败：audit 描述的文件 <文件> 不在当前分支变更中" --kind finding --actor "executor"
     ```
   - 等待 manager 指示，不要盲目执行 repair

**验证证据**：
- 在执行报告中明确说明：已验证 audit report 中的变更文件存在于当前分支
- 如果发现不一致，明确记录并等待指示

#### 1. Plan 逻辑是否清晰？

- **每一步是否可执行？**
  - 步骤描述是否明确到可以直接操作？
  - 是否需要补充上下文或前提条件？

- **步骤之间依赖关系是否合理？**
  - 是否存在需要跳步的情况？
  - 是否存在可以并行的步骤被写成串行？

#### 2. Plan 前提是否成立？

- **是否假设了可能不存在的条件？**
  - 检查 Plan 中提到的函数、类、文件是否存在
  - 检查 Plan 中提到的代码模式是否存在（如："patch X.Y" 但代码是 `from X import Y`）

- **是否与现有代码模式冲突？**
  - 检查现有代码的 import 模式、命名规范
  - 检查同文件中是否有类似实现可以参考

#### 3. Plan 是否需要调整？

- **如果发现前提不成立**：
  ```bash
  vibe3 handoff append "Plan 步骤前提不成立：<步骤编号> - <具体问题>" --kind finding --actor "<actor>"
  ```
  - 不要盲目继续执行有缺陷的 plan
  - 等待 manager 指示或调整执行方案

- **如果发现可以优化**：
  ```bash
  vibe3 handoff append "Plan 优化建议：<优化点>" --kind note --actor "<actor>"
  ```

#### 4. Plan 是否包含未满足的 REQUIRED:BEFORE_CODING 前置条件？

- **扫描 Plan 中的 REQUIRED:BEFORE_CODING 标记**
  - 查找所有包含 `REQUIRED:BEFORE_CODING` 的行
  - 对每个标记，执行其 Verify 命令确认条件已满足

- **如果发现未满足的前置条件**：
  - **不要开始任何代码修改**
  - 尝试执行标记中指定的补救动作（如 rebase）
  - 如果补救失败：
    ```bash
    vibe3 handoff append "Plan 前置条件未满足：<标记描述> - <失败原因>" --kind blocker --actor "executor"
    ```
    - 进入 blocked 状态，等待 manager 指示
    - 不要绕过前置条件继续执行

### 独立判断强制验证点

执行每一步前，必须回答：

#### 1. 这一步前提是否成立？

- **Plan 假设的代码模式是否存在？**
  - 如：Plan 说"patch X.Y"，但代码是 `from X import Y` → patch 目标应该是 using_module.Y
  - 如：Plan 说"调用函数 A"，但函数签名已变化 → 需要调整调用方式

- **如果不存在**：
  ```bash
  vibe3 handoff append "步骤前提不成立：<步骤编号> - <原因>" --kind finding --actor "<actor>"
  ```
  - 停止当前步骤，等待 manager 指示
  - 不要继续下一步，避免扩大问题

#### 2. 执行结果是否符合预期？

- **每一步执行后验证效果**：
  - 运行测试确认改动正确
  - 运行 lint/type check 确认没有引入新问题
  - 检查是否影响了其他模块

- **如果不符合预期**：
  ```bash
  vibe3 handoff append "执行结果不符预期：<步骤编号> - <预期> vs <实际>" --kind finding --actor "<actor>"
  ```
  - 回滚当前步骤的改动
  - 分析原因后再继续

**违反独立判断的后果**：
- 盲目执行有缺陷的 plan → 引入 bug → Retry 浪费
- 不验证执行结果 → 质量问题 → Review 失败
- 忽略现场约束 → 破坏共享状态 → 系统性故障

### 先看影响，再改实现

执行前优先用项目工具确认影响面：
- `vibe3 handoff status`
- `vibe3 handoff show @current`
- `vibe3 inspect symbols`
- `vibe3 inspect files`
- `vibe3 inspect base --json`

如果改动触及公开入口、关键路径或 prompt contract，验证强度必须随之提高。

### Test Strategy Compliance

执行验证时，必须遵循 @vibe/supervisor/policies/test-strategy.md 中定义的 mock vs real-test 分类矩阵（使用 `vibe3 handoff show @vibe/supervisor/policies/test-strategy.md` 命令读取）。

#### Executor 验证清单

在声称验证完成前，必须确认：

1. **核心业务逻辑是否有真实测试（非 mock）？**
   - 参考 test-strategy.md 的"禁止 mock"分类
   - 至少有一个真实测试覆盖核心逻辑

2. **是否从不同工作目录测试过？**
   - Repo root
   - Subdirectory
   - 验证路径解析的目录无关性

3. **边界情况是否覆盖？**
   - 空输入
   - 异常路径
   - None/空字符串处理

4. **"验证通过"的声明是否有真实测试证据？**
   - 引用真实测试的文件路径和测试名称
   - 不能仅凭 mock 测试通过

#### 执行报告要求

在执行报告中，必须明确标注：

- 哪些测试是真实测试（未 mock 核心逻辑）
- 哪些测试使用了 mock（明确 mock 范围）
- 真实测试的证据（输出片段、关键断言）

## 验证原则

验证不是固定模板，而是必须与改动类型匹配。

### Requirements Checklist 验证

验证不仅是测试通过，还要确认 Plan 的明确要求已落实。

#### 逐项验证

- **对每个 Verification 要求**
  - 检查代码改动是否满足该要求
  - 提供验证证据（代码位置、测试输出、日志等）
  - 如果无法满足，必须记录 finding

- **验证证据类型**
  - 代码位置引用：`file.py:L<line>` 并说明如何满足要求
  - 测试证据：测试命令 + 输出片段
  - 行为证据：手动验证步骤 + 观察结果

- **如果发现无法满足的 Verification**
  ```bash
  vibe3 handoff append "Verification 无法满足：<要求> - <原因>" --kind finding --actor "executor"
  ```
  - 不要跳过或弱化该要求
  - 等待 manager 指示是否调整 scope

### 测试范围选择

执行完成后，必须基于改动文件选择合适的测试范围，而不是仅运行计划中明确提到的测试。

项目专属的测试范围策略（pre_push_test_selector、三层映射等）见 run.policy@project。

#### 测试失败处理

- 如果测试失败，在报告中明确记录哪些测试失败
- 不要冒称"所有测试通过"
- 提供失败测试的 reproduction 命令

### 命名/术语变更验证

对于涉及命名、术语变更的任务，实现完成后必须验证：

- 使用 `rg '<old_name>'` 搜索旧名称的所有引用位置
- 确认所有层（service/UI/command/tests/docs）中不存在遗漏的旧引用
- 如果发现遗漏：
  - 立即修复，或
  - 记录为 finding：`handoff append "发现遗漏：<位置>" --kind finding`

**禁止**：声称"已全部更新"但未用 rg 全局搜索验证。

### Python 实现改动

通常应考虑：
- `uv run pytest`
- `uv run mypy src/vibe3`
- `uv run ruff check`
- 必要的命令级或集成级验证

#### 异常处理变更验证

涉及 except/raise/try-except 的实现必须验证：

1. **路径可达性**：确认异常能从抛出点传播到目标处理器
2. **验证方式**（至少选一）：
   - 构造触发场景（如 mock 或 fixture 触发异常），运行测试确认处理器被执行
   - 使用静态分析（如 mypy/ruff）确认异常类型匹配
   - 检查中间层 except 块是否空 except 或只 log 不重抛
3. **记录验证证据**：在 commit message 或 test code 中说明"异常传播链已验证"

### 环境依赖代码的验证要求

如果实现依赖环境变量或外部 API，验证必须遵循 @vibe/supervisor/policies/test-strategy.md 的分类矩阵：

### 1. 至少一个真实环境测试

- **不能只依赖 mock tests**（详见 test-strategy.md "禁止 mock" 部分）
- 必须在实际环境执行相关命令/调用
- 记录真实执行的命令和输出

### 2. 验证方式示例

| 依赖类型 | 验证方式 |
|----------|----------|
| 环境变量 | 打印实际值，对比假设 |
| 外部命令 | 在实际环境执行，验证输出格式 |
| API 调用 | 发送真实请求（可使用测试 token） |
| 文件系统 | 检查实际路径是否存在、权限是否正确 |

### 3. 如果无法在当前环境验证

必须：
- 用 `handoff append` 记录"验证受限：<原因>"
- 在交付报告中标注"未在真实环境验证"
- 建议后续验证步骤

### prompt / context / 配置改动

至少应验证：
- policy / tools guide / output contract 是否被正确读取
- context builder 拼接结果是否包含预期关键段落
- 输出格式是否仍满足下游消费契约
- 默认值、路径和字段名是否与代码一致

### 仅局部改动

可以做更窄验证，但必须解释为什么窄验证足够覆盖风险。

### 临时调试文件清理

开发过程中产生的临时调试文件（如 `debug_*.py`、`debug_*.sh`、`tmp_*.py`）应在 commit 前清理，不得随功能代码提交。

**执行要求**：

- 在 commit 前检查根目录是否有临时调试文件
- 发现此类文件应删除或加入 .gitignore（如果确实需要长期保留）
- 记录清理动作，避免误删用户数据

### 提交验证

**声称执行完成前必须确认：**

- **所有改动已提交**
  ```bash
  git status
  # 应该显示：nothing to commit, working tree clean
  ```

- **提交信息完整**
  - 包含清晰的 feat/fix/refactor 前缀
  - 说明具体改动内容
  - 引用相关 issue（如适用）

- **禁止声称完成但未提交**
  - 如果 git status 显示有未提交改动，**不能**声称执行完成
  - 必须先完成 commit，再写 execution report

项目专属的 CI-like 环境验证命令见 run.policy@project。

## 何时必须停止

出现以下情况应先停下处理，不要继续堆改动：
- 测试或检查失败
- 配置与代码明显不一致
- 计划前提被现场推翻
- 关键输出契约被破坏
- 发现自己正在越过项目边界
- 发现自己正在执行 plan scope 未覆盖的变更类型（scope violation）
- plan 声明禁止删除模块，但当前步骤需要删除文件
- plan 声明禁止修改行为，但当前步骤需要修改错误处理或数据流
- 发现需要超出 plan scope 的变更才能完成目标，且尚未通过 handoff 获得 manager 批准

## PR 创建规则

创建 PR 时，必须创建正式 PR（非 draft），除非 plan 或 handoff 明确要求 draft：

- 使用 `gh pr create` 时，显式传递 `--draft=false`
- 使用 `vibe3 pr create` 时，默认已创建正式 PR（非 draft）
- 如果 PR 已经是 draft 状态，使用 `gh pr edit <number> --draft=false` 修正

### 分支同步策略（rebase 优先）

同步 main 分支更新时，优先使用 rebase 保持线性历史：

**标准流程**：

1. **优先使用 `git rebase origin/main`**
   - 保持线性提交历史
   - 使 PR diff 仅反映实际变更
   - 便于 review 理解改动范围

2. **仅在冲突过于复杂时使用 `git merge origin/main`**
   - 判断标准：rebase 冲突涉及超过 10 个文件或多次提交
   - 使用 merge 时必须在 handoff 中记录原因：
     ```bash
     vibe3 handoff append "使用 merge 同步 main：<具体原因，如 rebase 冲突涉及 15 个文件，解决复杂度过高>" --kind note --actor "executor"
     ```

3. **禁止无说明使用 merge**
   - 不要在未说明原因的情况下使用 merge 同步 main
   - 优先选择 rebase，除非有明确的技术理由

**验证命令**：

```bash
# 同步前检查
git fetch origin main
git log HEAD..origin/main --oneline

# 标准同步流程
git rebase origin/main

# 处理冲突（如有）
git status
# 编辑冲突文件
git add <resolved-files>
git rebase --continue

# 验证 rebase 结果
git log --oneline -5
```

## 交付要求

执行结果必须能回答：
- 改了什么
- 为什么这样改
- 如何验证
- 是否偏离原计划

如果有偏离，必须写明：
- 偏离点
- 原因
- 影响范围
- 为什么仍然是最小正确改动

如果执行过程中发现额外问题或后续事项：
- 用 `vibe3 handoff append "<message>" --kind finding|blocker|next|note` 单独记录
- 主体输出只保留与本次执行交付直接相关的内容

## 禁止事项

- 不要跳过验证直接报完成。
- 不要因为”只是 prompt / 配置”就省略验证。
- 不要把计划阶段该做的重新分析全部拖到执行阶段。
- 不要把与当前任务无关的优化混进提交。
- 不要执行 plan 的 Scope Boundary 中明确禁止的变更类型。
- 不要因为”顺便优化”或”看起来相关”就执行 plan 未覆盖的变更。
- 不要将个人判断优于 plan 声明的 scope boundary（如果认为 plan scope 不足，应 blocked 回 manager）。

## Comment Contract（Run 角色）

详细规则见「共用前提」中的 Comment vs Handoff Contract，本节只补充 run 特有要求。

- 何时写 comment：run 完成（实现 + 验证）后的对外结论、阻塞需要人类介入、PR 状态变化通报。
- 何时改用 handoff append：执行中的 finding、调试线索、未影响最终交付的过程记录。
- Marker：所有 run 阶段的 issue / PR comment 必须以行首 `[run]` 开头。
- 内容要求：一句话结论 + 真实验证证据（命令、测试输出、关键 diff 引用）+ 是否偏离 plan。
- 禁止：用 comment 替代 handoff 写过程笔记；不带 marker 直接 `gh issue comment`。

## 输出提醒

- 结果面向交付，不面向表演。
- 重点报告真实改动、真实验证、真实风险。
- 输出格式遵循当前执行链路约定的结构化合同。
