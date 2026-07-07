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
- **Gate 优先于提示**：凡是多阶段流程、subagent 协作、handoff、审批、验证等关键行为，优先固化到 backlog task、metadata、状态检查或结果裁决 gate；不得只靠 prompt 里的“必须/禁止”维持约束
- **减少解释空间**：skill 文案、执行模板、reference 样例之间不得出现可被 agent 合理化绕开的语句；一旦发现“先干活后解释”空间，默认视为 Blocking 并立即修正
- **分阶段授权**：涉及握手/验证/审批的 subagent 流程，spawn 初始 prompt 必须只包含当前阶段允许动作；正式工作必须通过第二条消息、第二个 task 或后续 phase 单独激活
- **握手必须有时序**：涉及 lead/subagent 握手时，优先使用 `lead_ready -> agent_ready -> send_task` 的单向时序；不得把握手写成双方同时各自宣布 ready 的并发语义
- **Lead 最小权限**：如果流程设计要求 subagent 先完成背景调研或专项审查，team-lead 不得在 backlog / 握手前执行原本属于 subagent 的预调查动作；显式 PR 编号入口下，`gh pr view/diff`、`git diff/log/show` 这类上下文采集默认属于 agent，不属于 lead
- **fresh spawn / 复用分离**：首次 spawn 的 agent 与已完成上一轮任务的复用 teammate 必须使用不同语义；不得把“待命/等待新 PR”指令混入 fresh spawn 的握手后路径
- **backlog gate 可判定**：关键握手/激活流程不仅要有 `handshake_status`，还应有 `expected_next_action`、`task_activation_allowed`、`activation_state` 之类可判定字段，避免 lead 口头宣布状态却没有 metadata 证据
- **伪代码符号约定**：使用伪代码的 skill 必须包含 Pseudocode Convention 节，明确定义 `@function()`（伪代码函数）、`ToolName()`（真实 Tool）、`$ cmd`（Shell 命令）、`{variable}`（占位符）的视觉区分规则；不得出现 agent 无法判断是伪代码还是真实命令的模糊写法

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
9. 涉及 subagent / workflow 的 skill，必须检查是否存在可判定的 gate，而不是只有 prompt 约束
10. 涉及 handshake / verify / approve 的 agent prompt，必须检查“前置阶段是否纯净”：只要在握手阶段混入任何正式工作内容，直接判 Blocking
11. 涉及 team-lead + subagent 分工的 skill，必须检查 lead 是否被误授予“预调查”权限；如果显式 PR 入口要求 lead 先 `gh pr view/diff`，直接判 Blocking
12. 涉及 fresh spawn + reuse 两种模式的 skill，必须检查两者是否显式分离；如果刚握手成功的 fresh spawn agent 被允许进入 idle/待命语义，直接判 Blocking
13. 涉及双向握手的 skill，必须检查是否存在明确时序；如果 lead 和 agent 可以同时各说一次“已就绪”而没有 `lead_ready -> agent_ready` 顺序，直接判 Blocking
14. 涉及 backlog task gate 的 skill，必须检查 metadata 是否足以判定”下一步只允许什么”；如果只有自然语言约束，没有 `expected_next_action` / `task_activation_allowed` 之类字段，默认视为脆弱设计
15. 涉及伪代码的 skill，必须检查是否定义了 Pseudocode Convention 节；若伪代码函数与真实 Tool 调用无法视觉区分（如 `stop()` vs `TeamCreate()`），直接判 Blocking

## `exit()` 语义

`exit()` 是语义停止标记，表示停止本轮 skill 治理，不继续扩大分析范围或创建/更新文件。

## Stable Reads

**Skill 现场**：

```bash
ls -la skills/<skill-name>/
cat skills/<skill-name>/SKILL.md
uv run python $HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/<skill-name>
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

### `check_pseudocode_convention()`

Inputs: skill 文案（全部 SKILL.md 内容）

Steps:

1. 判断 skill 是否包含伪代码（检查是否存在缩进伪代码块、`Phase_N()` 定义、`// comment` 注释等伪代码特征）
2. 若无伪代码特征 → 跳过本检查，返回 N/A
3. 若有伪代码，检查是否定义了 **Pseudocode Convention** 节：
   - 未定义 → 判 `Blocking`，必须补充
4. Pseudocode Convention 节必须明确以下视觉区分规则：
   - `@function()` 前缀用于伪代码函数（本文件定义的元指令）
   - `ToolName()` 首字母大写无前缀用于真实的 Claude Code Tool
   - `$ cmd` 前缀用于伪代码块中的 Shell 命令
   - `{variable}` 用于占位符
   - `` ```bash `` 代码块用于可直接执行的 Shell 脚本
5. 检查实际使用是否与约定一致：
   - 伪代码函数是否统一使用 `@` 前缀（`@stop` / `@handshake` 等）
   - 真实 Tool 调用是否无前缀（`TeamCreate` / `SendMessage` 等）
   - 脚本调用是否区分了 `$ cmd`（伪代码内）vs `` ```bash ``（独立执行）
   - 是否存在 `function_name()` 无前缀的模糊写法（agent 无法判断是伪代码还是真实 Tool）
6. 检查是否存在违反显式停止条件的模糊模式：
   - `handle errors appropriately` → 应改为 `if exit ≠ 0: @stop("原因")`
   - `wait for completion` → 应改为 `@wait_for_report(...)` 或 `if timeout: @stop(...)`
   - `use script.sh` 或 `check file.md` → 应明确是执行还是读取参考
7. 返回伪代码约定状态（Aligned / Blocking / N/A）

Exit: 伪代码约定缺失或实际使用不一致 → 判 `Blocking`，立即修正；模糊命令引用 → 标注具体行号并修正

### `handle_create()`

When: 用户要求创建新的 `skills/vibe-*`

Allowed: `skill.write`, `skill.structure.write`, `standards.read`, `cli.read`, `validation.execute`

Forbidden: 创建不属于 `skills/` 的 skill、复制其他仓库 skill 作为模板、重新定义术语

Steps:

1. 确认 skill 名称符合 `skills/vibe-*` 命名规范，不与 `vibe-skills-manager` 范围重叠
2. 执行 `check_skill_scope()` 识别应引用的标准
3. 初始化 skill 结构：
   ```bash
   uv run python $HOME/.codex/skills/.system/skill-creator/scripts/init_skill.py <skill-name> --path skills --resources scripts,references --interface display_name="..." --interface short_description="..." --interface default_prompt="Use $<skill-name> ..."
   ```
4. 替换模板文本为 Vibe-specific guidance：精确描述触发时机、明确 Shell 边界、引用应引用的标准、枚举所有 `vibe3` 命令并逐一验证
5. 添加必要的支持资源（优先一个 checklist/reference 文件）
6. 验证结构：`uv run python $HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/<skill-name>`
7. skill 包含审计或确定性检查时添加自动化测试
8. `exit()`

### `handle_update()`

When: 用户要求更新已有的 `skills/vibe-*` 或审计发现漂移需要修正

Allowed: `skill.read/write`, `standards.read`, `cli.read`

Forbidden: 保留过时描述作为主路径、只报漂移警告而不修正、重新定义术语

Steps:

1. 读取目标 skill 文案
2. 执行 `check_command_alignment()`、`check_standard_citation()`、`check_shell_boundary()`、`check_pseudocode_convention()` 验证
3. 如目标 skill 含 subagent / workflow / backlog task：额外检查关键约束是否已固化为 backlog task、metadata、状态检查、结果过滤等 gate；若只有 prompt 约束、缺少 gate、或存在可被误读的执行顺序，视为 Blocking
4. 如目标 skill 含 handshake / verify / approve：额外检查 spawn 初始 prompt 是否只包含当前阶段允许动作；若在 handshake 阶段混入任何正式工作（如 gh pr view/diff、读取 diff、开始审查、开始调研），视为 Blocking
5. 如目标 skill 含显式 PR / MR / diff 入口：额外检查 lead 是否在 spawn / backlog / 握手之前被要求执行 `gh pr view/diff`、`git diff/log/show` 等预调查；若是，视为 Blocking，必须改成“lead 先建 task + 发起握手，context/reviewer agent 成为首个接触 diff 的主体”
6. 如目标 skill 同时描述 fresh spawn 与 reuse：额外检查握手成功后的下一步是否唯一；若 fresh spawn agent 在未收到当前任务前被允许“保持空闲/等待新 PR”，视为 Blocking
7. 如目标 skill 含双向握手：额外检查 team-lead 与 agent 是否使用有序消息（如 `lead_ready` / `agent_ready`）；若双方都可在未收到对方确认前自行宣布 ready，视为 Blocking
8. 如目标 skill 依赖 backlog task gate：额外检查 metadata 是否记录 `expected_next_action`、`task_activation_allowed`、`activation_state` 等状态字段；若只写“收到 ready 后再做 X”但没有可判定 metadata，视为 Blocking 或至少 High-Risk Drift
9. 对发现的问题：命令漂移→立即修正改用新命令或标注 `Capability Gap`；引用缺失→立即补充；边界违规→立即修正；真源不清晰→保留 `Drift Warning` 并说明问题；prompt-only workflow → 补 gate、补测试、删歧义描述；handshake 混工 → 拆成“初始 prompt 只握手 + 第二条消息激活正式任务”；lead 预调查 → 收回 lead 权限并改成 agent 首次接触上下文；fresh spawn / reuse 混语义 → 强制补“握手成功后立即激活正式任务”规则；并发握手 → 改成 `lead_ready -> agent_ready -> send_task`；backlog 弱 gate → 补 metadata 状态字段
10. 验证更新后的 skill 结构
11. 修正涉及命令、边界或 gate 时更新相关测试
12. `exit()`

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
   - `check_pseudocode_convention()`：若 skill 含伪代码，检查 Pseudocode Convention 节是否存在、视觉区分规则是否完整、实际使用是否一致

7. **SKILL.md 最小规范检查**（基于 skill-standard.md 第 174-188 行）：
   - 检查是否有 Overview、When to Use、Execution Flow、Guardrails 部分
   - 检查 description 是否只定义触发条件，不摘要整个流程
   - 检查是否有必读文档部分，引用了必要的标准文件

8. **术语和动作词检查**（基于 glossary.md 和 action-verbs.md）：
   - 检查术语使用是否符合 glossary.md（例如不使用废弃术语"GitHub issue"的别称）
   - 检查动作词语义是否符合 action-verbs.md（例如 `done` 是否超出边界）
   - 检查是否使用了未定义术语（例如 "Skill Governor"）

**虚构参数、执行流程与 gate 检查**：

9. **虚构参数检查**（严重违规项）：
   - 检查硬编码用户名路径（如 `/Users/username/`）
   - 检查虚构命令名称或参数形状
   - 检查脚本路径是否使用 `$HOME` 或相对路径而非硬编码

10. **工具推荐和执行流程检查**：
    - Stable Reads 是否列出标准工具（ls, cat, bash, git, uv）
    - 伪代码步骤是否清晰可执行，无含糊表述
    - Inputs / Steps / Exit 结构是否完整
    - 若 skill 使用伪代码，检查 Pseudocode Convention 节：`@` 伪代码函数 / `ToolName()` 真实 Tool / `$ cmd` Shell 命令 / `{variable}` 占位符 是否均已定义且实际使用一致
    - 检查伪代码块中是否存在 `function_name()` 无前缀写法（agent 无法判断是伪代码还是真实 Tool）
    - 检查脚本引用是否区分了"执行"（`$ script.sh`）vs "读取参考"（`Read reference: ...`），禁止出现 `use script.sh` / `check file.md` 等模糊指令
    - 若 skill 涉及 subagent / workflow / backlog task：检查是否把关键行为固化为 backlog task、metadata、状态检查、结果过滤等 gate
    - 检查是否存在“写了必须先验证/先握手，但执行模板先开始工作”的顺序漏洞
    - 检查 reference 样例、执行模板、agent 文案之间是否互相打架，给 agent 留下“我以为 prompt 已经正式放行”的解释空间
    - 检查 handshake 阶段是否纯净：spawn 初始 prompt 中不得混入任何正式工作内容；正式任务必须在握手成功后通过第二条消息、第二个 task 或后续 phase 单独激活
    - 检查 lead 是否被误授予预调查权限：显式 PR 编号入口下，不得要求 lead 在 backlog / 握手前执行 `gh pr view/diff` 或 `git diff/log/show`
    - 检查 fresh spawn / reuse 是否混淆：刚完成握手的 fresh spawn agent 不得被允许进入“保持空闲/等待新 PR”语义；待命只属于已完成上一轮任务的复用 teammate
    - 检查握手是否有明确时序：lead 必须先发 `lead_ready`，agent 再回 `agent_ready`；不得保留双方同时各说一次“已就绪”的解释空间
    - 检查 backlog metadata 是否足够硬：是否明确记录 `expected_next_action`、`task_activation_allowed`、`activation_state`，并用它们限制 task 激活时机

**分类发现并立即修正**：

11. **分类发现**：
    - `Blocking`: 真源违规、对象模型重定义、术语混用、动作词边界超出、虚构参数、prompt-only gate、执行顺序自相矛盾、handshake 阶段混入正式工作、lead 预调查、fresh spawn / reuse 混淆、并发握手、弱 backlog gate、可被 agent 合理化绕开的描述（必须立即修正）
    - `Missing Reference`: 缺失标准引用、缺失必读文档部分（必须立即补充）
    - `Skill Structure Violation`: 缺失 Overview/When to Use/Execution Flow/Guardrails（必须补充）
    - `Capability Gap`: skill 需要的命令不存在（必须标注）
    - `Drift Warning`: 真源本身不清晰或需深入审查（说明原因，不强行修正）

12. **立即修正 Blocking、Missing Reference、Skill Structure Violation**：
    - Blocking 发现：立即修正 skill 文案（虚构参数、术语、对象模型重定义、prompt-only workflow、顺序漏洞、handshake 混工、lead 预调查、fresh spawn / reuse 混淆、并发握手、弱 backlog gate 等）
    - Missing Reference 发现：立即补充标准引用，补充必读文档部分
    - Skill Structure Violation 发现：立即补充 Overview/When to Use/Execution Flow/Guardrails
    - prompt-only workflow：优先把关键行为固化到 backlog task / metadata / 状态 gate / 结果裁决 gate，并删除会暗示“可先执行后解释”的描述
    - handshake 混工：将 spawn 初始 prompt 收敛为“只含当前阶段允许动作”，把正式工作拆到握手成功后的第二条消息、第二个 task 或后续 phase
    - lead 预调查：将首个接触 PR / diff 的动作改派给 context/reviewer agent；lead 只保留 backlog、握手、状态更新、结果裁决和写回权限
    - fresh spawn / reuse 混淆：明确“fresh spawn ready 后立即激活当前任务”，将“保持空闲/等待新 PR”限制到上一轮任务已完成的复用 teammate
    - 并发握手：显式补 `lead_ready -> agent_ready -> send_task` 时序，禁止双方在未收到对方消息前各自宣布 ready
    - 弱 backlog gate：补 `expected_next_action`、`task_activation_allowed`、`activation_state` 等 metadata，并让关键动作以它们为前置条件
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
    | 伪代码约定 | ⭐ X/5 | Pseudocode Convention 完整、视觉区分一致 |
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
    - **使用伪代码但缺少 Pseudocode Convention 节评分不得高于 3/5**
    - 完全符合所有标准评分 5/5

16. **输出审计报告**：
    - 已执行检查清单（用 ✅ 标记）：前置规范阅读、被审核 skill 必读文档检查、对象模型边界检查、术语检查、动作词检查、SKILL.md 结构检查、命令对齐、标准引用、Shell 边界、伪代码约定检查、虚构参数检查、工具推荐、执行流程检查、冗余清理
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
    - 确认伪代码约定（如适用）：Pseudocode Convention 节存在、`@`/`$`/`{var}` 前缀一致、无模糊命令引用

18. `exit()`

Hard rule:

- Blocking 发现必须立即修正，不得只报警告
- Missing Reference 发现必须立即补充，不得跳过
- 虚构参数（硬编码用户名/路径）是严重违规项，评分不得高于 3/5
- **文件超过 400 行且存在冗余内容时必须清理**，评分不得高于 3/5
- **涉及 subagent / workflow 的 skill，如关键约束只存在于 prompt 而未落到 gate，必须判为 Blocking 并立即修正**
- **涉及 handshake / verify / approve 的 skill，如 spawn 初始 prompt 混入正式工作，必须判为 Blocking 并立即修正**
- **使用伪代码但缺少 Pseudocode Convention 节，或伪代码函数与真实 Tool 无法视觉区分，必须判为 Blocking 并立即修正**
- 审计完成后必须提供质量评分表和预估效果表（含文件体积对比）
- 必须验证修正和清理结果，确认无残留问题和冗余表述

## Output Contract

审计报告必须包含：

1. **已执行检查清单**（✅ 标记）：前置规范阅读（skill-audit 读 skill-standard/glossary/action-verbs）、被审核 skill 必读文档检查（不超过 3 个、业务相关、不包含 glossary/action-verbs）、对象模型边界检查、术语检查、动作词检查、SKILL.md 结构检查、命令对齐、标准引用、Shell 边界、伪代码约定检查、虚构参数检查、工具推荐、执行流程检查、冗余清理

2. **发现分类**：
   - `Blocking`: 真源违规、对象模型重定义、术语混用、动作词边界超出、虚构参数、必读文档超过 3 个、必读文档包含 glossary/action-verbs、prompt-only gate、执行顺序自相矛盾、handshake 阶段混入正式工作、reference/template/agent 文案互相冲突、**伪代码缺少 Pseudocode Convention 节、伪代码函数与真实 Tool 无法视觉区分**（必须修正）
   - `Missing Reference`: 缺失标准引用、缺失必读文档部分、必读文档缺失业务相关标准（必须补充）
   - `Skill Structure Violation`: 缺失 Overview/When to Use/Execution Flow/Guardrails（必须补充）
   - `Capability Gap`: skill 需要的命令不存在（必须标注）
   - `Drift Warning`: 真源不清晰（说明原因，不强行修正）

   Blocking/Missing Reference/Skill Structure Violation 必须标注：发现位置（行号）、问题描述、违规类型、严重程度（HIGH/MEDIUM/LOW）、修正方案

3. **质量评分表**（十一维度 ⭐ 1-5/5）：前置规范阅读（skill-audit 自己）、必读文档检查（不超过 3 个、业务相关）、对象模型边界、术语使用、动作词边界、SKILL.md 结构、伪代码约定、虚构参数检查、工具推荐、执行流程、冗余清理

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
- **不得把关键流程约束只写在 prompt 里**：涉及握手、验证、审批、subagent 协作时，必须尽量固化到 backlog task、metadata、状态检查或结果裁决 gate
- **不得保留给 agent 自行解释的缝**：如果 skill 同时出现“先验证/先握手”和“直接开始工作/无需等待”的描述，必须立即删除歧义并补 gate
- **不得在 handshake 阶段混入正式工作**：spawn 初始 prompt 只能包含当前阶段允许动作；正式调研、正式审查、读取 diff、gh pr view/diff 等必须在握手成功后单独激活
- **不得保留冗余表述**：重复职责列表、重复规则说明、过度详细的表格、与 Forbidden 重复的 Restrictions
- **不得跳过前置强制步骤**：必须先读真源规范，再检查被审核 skill 的必读文档部分（不超过 3 个、业务相关）
