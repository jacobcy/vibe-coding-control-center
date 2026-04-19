---
name: vibe-skill-audit
description: Use when the user wants to create, update, review, or audit a repo-local Vibe skill under `skills/`, mentions "/vibe-skill-audit", "vibe-skill", "vibe skill", "创建 skill", "审查 skill", "skill 文案", or "自动匹配语义", or needs a Vibe-specific wrapper around `skill-creator` rather than a generic cross-project skill workflow.
---

# /vibe-skill-audit - Vibe Skill Governance

## Role

你负责 `skills/vibe-*` 的文案质量和语义一致性。

**核心职责**：

- 创建新的 `skills/vibe-*`
- 更新已有 skill 文案以对齐当前实现
- 审计 skill 与真源的对齐状态并立即修正问题
- 确保 skill 引用正确的标准、不绕过 Shell 边界

**硬约束**：发现漂移立即修正，不得只报警告；不直接执行 skill 流程。

## Permission Contract

Allowed:

- `skill.read/write`: 读取或创建/更新 `skills/vibe-*/SKILL.md`
- `skill.structure.write`: 创建 skill 目录结构
- `standards.read`: 读取 `docs/standards/**/*.md`
- `cli.read`: 读取 `src/vibe3/cli.py` 及相关命令实现
- `test.write`: 创建或更新 skill 相关测试
- `validation.execute`: 运行 `skill-creator` 验证脚本

Forbidden:

- `skill_runtime.execute`: 直接执行目标 skill 流程
- `shared_state.write`: 直接修改 `.git/vibe3/*.json` 或 `.git/vibe/*.json`
- `shell_boundary.bypass`: 在 skill 中发明绕过 Shell 命令的 workaround
- `terminology.redefine`: 重新定义已由 `glossary.md` 定义的术语
- `standard_override`: 用模糊描述覆盖真源定义
- `legacy_preserve`: 保留过时命令或旧职责描述作为主路径
- `drift_warning_only`: 发现漂移只报警告而不修正文案（真源不清晰时才允许保留警告）

## Architecture Contract

- **真源引用**：术语、命令行为、边界语义以 `docs/standards/` 为真源；skill 文案只引用不重新定义
- **Shell 边界**：涉及共享状态或外部系统时必须通过真实 `vibe3` 命令
- **命令对齐**：skill 中提到的所有 `vibe3` 命令必须与当前 CLI 实现一致
- **漂移修正优先**：发现不一致时默认直接更新 skill 文案

## Truth Sources

**真源**：

- **术语真源**：`docs/standards/glossary.md`
- **动作词真源**：`docs/standards/action-verbs.md`
- **命令真源**：`src/vibe3/cli.py` 及相关命令实现文件
- **标准真源**：`docs/standards/v3/*.md`（skill-standard, command-standard, python-capability-design）

**非真源**：skill 文案模糊描述、历史旧命令、其他仓库 skill、已废弃标准文件。

**冲突处理**：skill 文案与真源冲突时，以真源为准并立即修正。

## Core Rules

1. 先读真源，再判断 skill 状态
2. 先识别语义范围，再引用对应标准
3. **命令验证优先**：skill 中提到的命令必须通过 CLI 实现验证，不能仅凭文本假设存在
4. 每次创建/更新必须执行语义对齐循环
5. 发现漂移立即修正文案，不得只报警告
6. 不允许在 skill 中重新定义术语或边界语义
7. 如果需要停止，就 `exit()`
8. skill 审计完成后必须明确说明哪些检查已执行

## `exit()` 语义

`exit()` 是语义停止标记，表示停止本轮 skill 治理，不继续扩大分析范围或创建/更新文件。

## Stable Reads

**Skill 现场**：

```bash
ls -la skills/<skill-name>/
cat skills/<skill-name>/SKILL.md
python3 $HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/<skill-name>
```

**真源现场**：

```bash
cat docs/standards/glossary.md
cat docs/standards/v3/skill-standard.md
cat docs/standards/v3/command-standard.md
cat docs/standards/v3/python-capability-design.md
uv run python src/vibe3/cli.py --help
uv run python src/vibe3/cli.py <command> --help
```

**禁止**：直接执行 skill 流程、假设旧命令仍存在、真源不清晰时强行修正。
**允许**：发现漂移时直接编辑 skill 文案。

## Pseudo Functions

### `check_skill_scope()`

Inputs: target skill name, skill description, skill 文案提到的语义范围

Steps:

1. 识别 skill 涉及的语义范围（flow/task/handoff/worktree/shell/standards）
2. 对应语义范围找出应引用的真源文件
3. 检查真源文件是否存在且有效
4. 返回应引用的标准文件清单

Exit: skill 涉及的语义范围无法匹配到真源时，comment 缺失的真源类型后 `exit()`

### `check_command_alignment()`

Inputs: skill 文案中提到的所有 `vibe3` 命令, 当前 CLI 实现文件

Steps:

1. 提取 skill 文案中的所有命令名称和参数形状
2. 对每个命令执行 CLI help 验证：`uv run python src/vibe3/cli.py <command> --help`
3. 检查命令是否仍存在、参数形状是否一致、职责是否已迁移到其他命令
4. 返回命令对齐状态（Aligned / Drifted / Missing）

Exit: 命令不存在时立即修正删除引用或标注 `Capability Gap`；职责迁移时立即修正改用新命令

### `check_standard_citation()`

Inputs: skill 文案中提到的标准文件引用, 当前标准文件目录

Steps:

1. 提取 skill 文案中的所有标准文件引用
2. 对每个引用检查文件是否存在
3. 检查引用是否与语义范围匹配、是否遗漏必引用标准
4. 返回引用对齐状态

Exit: 引用不存在时立即修正删除或标注 `Drift Warning`；遗漏必引用标准时立即补充

### `check_shell_boundary()`

Inputs: skill 文案中的操作描述, Shell 边界标准

Steps:

1. 识别 skill 中涉及共享状态或外部系统的操作
2. 检查是否明确要求使用 `vibe3` 命令
3. 检查是否存在直接操作 `.git/vibe3` 或绕过 Shell 的描述
4. 检查是否存在"workaround"、"手动修改"等隐式绕过描述
5. 返回边界合规状态

Exit: 发现绕过 Shell 边界时立即修正改用真实命令；能力不存在时标注 `Capability Gap`

### `handle_create()`

When: 用户要求创建新的 `skills/vibe-*`

Allowed: `skill.write`, `skill.structure.write`, `standards.read`, `cli.read`, `validation.execute`

Forbidden: 创建不属于 `skills/` 的 skill、复制其他仓库 skill 作为模板、重新定义术语

Steps:

1. 确认 skill 名称符合 `skills/vibe-*` 命名规范，不与 `vibe-skills-manager` 范围重叠
2. 执行 `check_skill_scope()` 识别应引用的标准
3. 初始化 skill 结构：
   ```bash
   python3 $HOME/.codex/skills/.system/skill-creator/scripts/init_skill.py <skill-name> --path skills --resources scripts,references --interface display_name="..." --interface short_description="..." --interface default_prompt="Use $<skill-name> ..."
   ```
4. 替换模板文本为 Vibe-specific guidance：精确描述触发时机、明确 Shell 边界、引用应引用的标准、枚举所有 `vibe3` 命令并逐一验证
5. 添加必要的支持资源（优先一个 checklist/reference 文件）
6. 验证结构：`python3 $HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/<skill-name>`
7. skill 包含审计或确定性检查时添加自动化测试
8. `exit()`

### `handle_update()`

When: 用户要求更新已有的 `skills/vibe-*` 或审计发现漂移需要修正

Allowed: `skill.read/write`, `standards.read`, `cli.read`

Forbidden: 保留过时描述作为主路径、只报漂移警告而不修正、重新定义术语

Steps:

1. 读取目标 skill 文案
2. 执行 `check_command_alignment()`、`check_standard_citation()`、`check_shell_boundary()` 验证
3. 对发现的问题：命令漂移→立即修正改用新命令或标注 `Capability Gap`；引用缺失→立即补充；边界违规→立即修正；真源不清晰→保留 `Drift Warning` 并说明问题
4. 验证更新后的 skill 结构
5. 修正涉及命令或边界时更新相关测试
6. `exit()`

Hard rule: 发现漂移默认直接修正文案；真源不清晰时才允许保留 `Drift Warning`

### `handle_audit()`

When: 用户要求审计已有的 `skills/vibe-*` 或要求"固化流程"、"标准化流程"

Allowed: `skill.read`, `skill.write`（发现问题时立即修正）, `standards.read`, `cli.read`, `validation.execute`

Forbidden: 直接执行 skill 流程、真源清晰时保留漂移警告、只报告问题而不修正 Blocking/Missing Reference、凭虚构规范做事而不先读真源

Steps:

**前置强制步骤**（必须在任何检查前执行）：

1. **读取 skill-audit 自己需要的规范文件**（必须按顺序）：
   - ① `docs/standards/v3/skill-standard.md`（skill 结构与边界要求）
   - ② `docs/standards/glossary.md`（术语定义，用来审核其他 skill）
   - ③ `docs/standards/action-verbs.md`（动作词定义，用来审核其他 skill）

2. **理解仓库最新语义**（用于审核）：
   - 从 skill-standard.md 理解：对象模型边界、SKILL.md 最小规范、核心 skill 结构
   - 从 glossary.md 理解：flow/task/issue/worktree 等术语的正式定义和禁止混用
   - 从 action-verbs.md 理解：add/show/update/new/bind/check/done 等动作词的语义边界

**被审核 skill 检查步骤**：

3. **读取被审核 skill 文案**：`cat skills/<target>/SKILL.md`

4. **检查被审核 skill 的必读文档部分**：
   - 检查是否有"必读文档"部分
   - 检查必读文档是否不超过 3 个
   - 检查必读文档是否是业务相关的标准文件
   - 检查是否缺失了真正业务相关的标准文件

5. **读取被审核 skill 直接相关的标准文件**（不超过 3 个）：
   - 只读取"必读文档"部分列出的文件
   - 理解这些标准文件对被审核 skill 的业务意义

**核心检查步骤**：

6. **执行核心检查**：
   - `check_command_alignment()`：提取所有 `vibe3` 命令，逐一 CLI help 验证
   - `check_standard_citation()`：提取所有标准文件引用，检查存在性和必引用完整性
   - `check_shell_boundary()`：识别共享状态/外部系统操作，检查是否使用 `vibe3` 命令

7. **SKILL.md 最小规范检查**（基于 skill-standard.md 第 174-188 行）：
   - 检查是否有 Overview、When to Use、Execution Flow、Guardrails 部分
   - 检查 description 是否只定义触发条件，不摘要整个流程
   - 检查是否有必读文档部分，引用了必要的标准文件

8. **术语和动作词检查**（基于 glossary.md 和 action-verbs.md）：
   - 检查术语使用是否符合 glossary.md（例如不使用废弃术语"repo issue"）
   - 检查动作词语义是否符合 action-verbs.md（例如 `done` 是否超出边界）
   - 检查是否使用了未定义术语（例如 "Skill Governor"）

**虚构参数和执行流程检查**：

9. **虚构参数检查**（严重违规项）：
   - 检查硬编码用户名路径（如 `/Users/username/`）
   - 检查虚构命令名称或参数形状
   - 检查脚本路径是否使用 `$HOME` 或相对路径而非硬编码

10. **工具推荐和执行流程检查**：
    - Stable Reads 是否列出标准工具（ls, cat, python3, bash, git, uv）
    - 伪代码步骤是否清晰可执行，无含糊表述
    - Inputs / Steps / Exit 结构是否完整

**分类发现并立即修正**：

11. **分类发现**：
    - `Blocking`: 真源违规、对象模型重定义、术语混用、动作词边界超出、虚构参数（必须立即修正）
    - `Missing Reference`: 缺失标准引用、缺失必读文档部分（必须立即补充）
    - `Skill Structure Violation`: 缺失 Overview/When to Use/Execution Flow/Guardrails（必须补充）
    - `Capability Gap`: skill 需要的命令不存在（必须标注）
    - `Drift Warning`: 真源本身不清晰或需深入审查（说明原因，不强行修正）

12. **立即修正 Blocking、Missing Reference、Skill Structure Violation**：
    - Blocking 发现：立即修正 skill 文案（虚构参数、术语、对象模型重定义等）
    - Missing Reference 发现：立即补充标准引用，补充必读文档部分
    - Skill Structure Violation 发现：立即补充 Overview/When to Use/Execution Flow/Guardrails
    - Drift Warning：明确说明真源问题，不强行修正
    - 标注修正内容和位置

13. **验证修正结果**：
    - Blocking 修正：检查文件，确认虚构参数已删除、术语已修正、对象模型未重定义
    - Missing Reference 补充：检查标准引用，确认无遗漏
    - Skill Structure 补充：检查 Overview/When to Use/Execution Flow/Guardrails 是否完整
    - 具体检查：使用 grep 或 Read 工具验证修正位置

14. **清理冗余内容**：
    检查并精简以下冗余表述：
    - 重复表述：Role 职责列表与核心决策逻辑重复、Permission Contract 规则与 Forbidden 重复、Core Rules 条目重复
    - 过度详细的表格：质量评分表、预估效果表、输出说明的冗余描述
    - 与 Forbidden 重复的 Restrictions 内容
    - 重复的 Exit 详细说明（可合并到 Steps 中）
    - Stable Reads 禁止/允许的重复表述

    清理原则：
    - ✅ 保留核心流程（所有检查步骤和修正动作）
    - ✅ 保留关键新增（前置强制步骤、对象模型检查、术语检查）
    - ✅ 删除重复表述（职责列表、规则部分、重复条目）
    - ✅ 精简表格输出（删除过度详细的说明）
    - ✅ 合并相似内容（Exit 描述合并到 Steps、真源/非真源合并）
    - ✅ 精简 Restrictions（删除与 Forbidden 重复内容）

    清理后验证：
    - 确认文件行数合理（建议 < 400 行，核心 skill 建议 < 350 行）
    - 确认核心流程完整性（前置强制步骤、对象模型检查、术语检查）
    - 确认可读性提升（无冗余表述、步骤清晰）

15. **输出质量评分表**：
    | 维度 | 评分 | 说明 |
    |------|------|------|
    | 前置规范阅读 | ⭐ X/5 | 是否强制先读 skill-standard |
    | 必读文档检查 | ⭐ X/5 | 被审核 skill 是否要求先读规范 |
    | 术语使用 | ⭐ X/5 | 符合 glossary.md，无废弃术语 |
    | 动作词边界 | ⭐ X/5 | 符合 action-verbs.md，未超出语义 |
    | SKILL.md 结构 | ⭐ X/5 | Overview/When to Use/Flow/Guardrails 完整 |
    | 虚构参数检查 | ⭐ X/5 | 无虚构路径/用户名/命令 |
    | 工具推荐 | ⭐ X/5 | 工具明确可执行 |
    | 执行流程 | ⭐ X/5 | 步骤清晰无含糊 |
    | **冗余清理** | ⭐ X/5 | 无重复表述、表格精简、体积合理 |

    **总体评分**：⭐ X/5（加权平均）

    **评分硬规则**：
    - 未执行前置规范阅读评分不得高于 2/5
    - 被审核 skill 缺失必读文档部分评分不得高于 3/5
    - 对象模型重定义评分不得高于 2/5
    - 术语混用评分不得高于 3/5
    - 动作词边界超出评分不得高于 3/5
    - 虚构参数评分不得高于 3/5
    - 文件超过 400 行且存在冗余评分不得高于 3/5
    - 完全符合所有标准评分 5/5

16. **输出审计报告**：
    - 已执行检查清单（用 ✅ 标记）：前置规范阅读、被审核 skill 必读文档检查、对象模型边界检查、术语检查、动作词检查、SKILL.md 结构检查、命令对齐、标准引用、Shell 边界、虚构参数检查、工具推荐、执行流程检查、冗余清理
    - 所有发现及修正情况（发现位置、问题、违规类型、严重程度、修正方案）
    - 冗余清理情况：清理内容类型、清理位置、清理行数、清理后文件行数
    - 未修正警告的原因说明
    - 质量评分表和预估效果表

17. **验证所有修正和清理已完成**：
    - 确认 Blocking、Missing Reference、Skill Structure Violation 已修正
    - 确认冗余内容已清理（文件行数合理、无重复表述）
    - 确认评分达到 5/5
    - 确认无虚构参数残留
    - 确认无对象模型重定义
    - 确认术语和动作词符合真源

18. `exit()`

Hard rule:

- Blocking 发现必须立即修正，不得只报警告
- Missing Reference 发现必须立即补充，不得跳过
- 虚构参数（硬编码用户名/路径）是严重违规项，评分不得高于 3/5
- **文件超过 400 行且存在冗余内容时必须清理**，评分不得高于 3/5
- 审计完成后必须提供质量评分表和预估效果表（含文件体积对比）
- 必须验证修正和清理结果，确认无残留问题和冗余表述

## Output Contract

审计报告必须包含：

1. **已执行检查清单**（✅ 标记）：前置规范阅读（skill-audit 读 skill-standard/glossary/action-verbs）、被审核 skill 必读文档检查（不超过 3 个、业务相关、不包含 glossary/action-verbs）、对象模型边界检查、术语检查、动作词检查、SKILL.md 结构检查、命令对齐、标准引用、Shell 边界、虚构参数检查、工具推荐、执行流程检查、冗余清理

2. **发现分类**：
   - `Blocking`: 真源违规、对象模型重定义、术语混用、动作词边界超出、虚构参数、必读文档超过 3 个、必读文档包含 glossary/action-verbs（必须修正）
   - `Missing Reference`: 缺失标准引用、缺失必读文档部分、必读文档缺失业务相关标准（必须补充）
   - `Skill Structure Violation`: 缺失 Overview/When to Use/Execution Flow/Guardrails（必须补充）
   - `Capability Gap`: skill 需要的命令不存在（必须标注）
   - `Drift Warning`: 真源不清晰（说明原因，不强行修正）

   Blocking/Missing Reference/Skill Structure Violation 必须标注：发现位置（行号）、问题描述、违规类型、严重程度（HIGH/MEDIUM/LOW）、修正方案

3. **质量评分表**（十维度 ⭐ 1-5/5）：前置规范阅读（skill-audit 自己）、必读文档检查（不超过 3 个、业务相关）、对象模型边界、术语使用、动作词边界、SKILL.md 结构、虚构参数检查、工具推荐、执行流程、冗余清理

4. **冗余清理情况**：清理内容类型（重复表述/过度详细表格/重复 Restrictions）、清理位置（行号范围）、清理行数、清理后文件行数、清理效果评估

5. **修正情况和验证**：修正位置、修正内容、修正数量；验证无残留硬编码用户名/路径、必读文档不超过 3 个、必读文档是业务相关的标准文件、无冗余表述、无对象模型重定义、评分达到 5/5

6. **最终结论**：✅ 全部对齐（评分 5/5）、⚠️ 部分问题已修正达到标准、❌ 存在无法修正的真源问题（Drift Warning）

无发现时：明确说明已执行的检查清单，标注"全部对齐，评分 5/5"。

## Restrictions

- **不得凭虚构规范做事**：必须先读 skill-standard.md/glossary.md/action-verbs.md，了解仓库最新语义
- **不得要求被审核 skill 读 glossary.md 或 action-verbs.md**：这两个是 skill-audit 的审核工具，不是被审核 skill 的业务必读文档
- **不得在被审核 skill 必读文档超过 3 个时只报警告**：必须立即修正为不超过 3 个
- 不得在 skill 中重新定义术语或边界语义
- 不得保留过时命令或旧职责描述作为主路径
- 不得在 skill 中发明绕过 Shell 命令的 workaround
- 不得只报漂移警告而不修正文案（真源清晰时）
- **不得保留冗余表述**：重复职责列表、重复规则说明、过度详细的表格、与 Forbidden 重复的 Restrictions
- **不得跳过前置强制步骤**：必须先读真源规范，再检查被审核 skill 的必读文档部分（不超过 3 个、业务相关）
