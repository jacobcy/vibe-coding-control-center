# Model-Spec-Context 编程范式

> 用约束驯服 AI：通过 Spec 锁死边界、Context 收敛输入、Model 降维执行。

---

## 范式概览

传统 AI 辅助编程的问题是把代码甩给模型让它"自由发挥"——这是幻觉的温床。
**Model-Spec-Context (MSC)** 框架的核心命题：

| 层 | 职责 | 原则 |
|---|---|---|
| **Spec** | 锁死边界 | Contract-First：先写契约，再写代码 |
| **Context** | 收敛输入 | 外科手术式投喂：只给模型它需要的信息 |
| **Model** | 降维执行 | 镣铐式使用：具体 Checklist 替代开放式问答 |

三层之间的关系是 **Spec → 约束 Context → 约束 Model**，逐层收敛自由度。

---

## 一、Spec：机器可读的绝对契约

### 1.1 核心原则：Contract-First（契约驱动开发）

绝不能先写代码再补 Spec。Spec 即唯一事实来源（Single Source of Truth）。

**实施要求：**
- 不要用 Markdown 写什么"用户注册接口需要校验邮箱"。直接写结构化的 OpenAPI YAML、Protobuf、或 JSON Schema。
- 引入 Spectral（JSON/YAML linter），强制 OpenAPI spec 通过校验。
- 使用 openspec 等工具，在 CI 或 pre-commit 钩子中，从 Spec 直接生成强类型的接口定义和路由骨架。

**AI 的边界：**
> AI 绝对不允许修改出入参定义。它只负责在生成的强类型骨架内部编写纯粹的业务逻辑。

### 1.2 阶段性适配

| 阶段 | Spec 策略 | 强制程度 |
|---|---|---|
| **探索期** | 允许 AI 先生成草稿 Spec → 人类审核 → 锁定 | 弱：Spec 是可变的 |
| **收敛期** | Spec 一旦锁定，任何修改都需要走变更流程 | 强：Contract-First 强制执行 |
| **维护期** | Spec 变更必须同步到类型定义和测试 | 强：CI 自动校验 |

> **关键判断**：如何知道当前处于哪个阶段？参考 SOUL.md §2.3 "Phase Transition" 中的架构审计标准。

### 1.3 非 API 场景的 Spec 策略

Contract-First 不仅适用于 REST API。不同项目类型有不同的 Spec 形态：

| 项目类型 | Spec 形态 | 示例 |
|---|---|---|
| REST API | OpenAPI 3.x YAML | `openspec/specs/*.yaml` |
| CLI 工具 | 命令签名 + 参数定义 | CLAUDE.md 中的命令表 |
| Shell 库 | 函数签名 + 参数约定 | `lib/*.sh` 中的函数注释 |
| AI Skills | YAML frontmatter + 输入输出格式 | `skills/*/SKILL.md` |
| 数据管道 | JSON Schema / Protobuf | Schema contract 文件 |
| 治理规则 | governance.yaml 阈值定义 | `.agent/governance.yaml` |

---

## 二、Context：极度克制的上下文投喂

### 2.1 核心原则：外科手术式精确

建立 Context 不是把整个仓库喂给模型，那是制造幻觉的温床。通过 Claude Code 或 MCP (Model Context Protocol) 建立的 Skills，必须具备"外科手术式的精确性"。

**禁止给 Model 提供"阅读代码"的开放式能力。提供以下确定性反馈技能：**

### 2.2 确定性反馈技能清单

#### A. AST 检索技能 (AST-based Search Skill)
- **目的**：Model 需要理解上下文时，禁止让它 `cat` 整个 5000 行的文件。
- **实现**：编写脚本 Skill，让 Model 只能通过类名或函数名提取出特定的 AST 节点（函数签名、注释），收敛 Context 窗口。
- **工具链**：`tree-sitter`、`ctags`、或自定义 MCP tool

#### B. LSP/类型检查反馈技能 (Type-check Feedback Skill)
- **目的**：Model 生成代码后，直接调用环境中的类型检查器。
- **实现**：调用 `tsc --noEmit`（TypeScript）、`mypy`（Python）、`shellcheck`（Shell）。
- **规则**：Model 修改完代码必须强制触发此 Skill。如果存在类型/语法报错，Skill 直接将 Error Log 作为新的 Context 弹回给 Model 进行循环修复。
- **⚠️ 熔断机制**：最多循环 **3 轮**。3 轮修不好的问题通常意味着 Spec 本身有缺陷，此时挂起并通知人类。

#### C. 沙箱测试技能 (Test Runner Skill)
- **目的**：验证代码是否满足 Spec 定义的行为。
- **实现**：给 Claude Code 配置运行 `pytest`、`jest`、`bats-core` 的权限。测试失败的 Stack Trace 就是最核心的 Context。
- **前提**：Spec 中不仅包含接口定义，还必须包含可执行的测试用例。

### 2.3 Context 分级策略

| 级别 | Context 类型 | 投喂策略 | 示例 |
|---|---|---|---|
| L1 必选 | Spec / 契约定义 | 始终加载 | OpenAPI YAML, SKILL.md frontmatter |
| L2 按需 | 相关函数签名 | AST 检索 | 被修改函数的调用者和被调用者 |
| L3 反馈 | 错误日志 | 自动触发 | 类型检查/测试失败的 Error Log |
| L4 参考 | 项目规范 | 首次加载 | CLAUDE.md, SOUL.md, governance.yaml |
| ❌ 禁止 | 整文件 dump | 永不投喂 | `cat` 完整源文件 |

---

## 三、Model：降维使用，执行无情审查

### 3.1 核心原则：镣铐式使用

放弃让 Model 做宏观的"代码好坏"评价。在 PR Review 阶段，Model 必须戴上镣铐。

### 3.2 Review 的反向提示词（Negative Prompting）

在 CI/CD 中接入 Model 做 Review 时，严禁使用 "请帮我 Review 这段代码并给出建议" 这种废话 Prompt。

**必须把 Prompt 变成极度具体的 Checklist：**

| ❌ 禁止的 Prompt | ✅ 正确的 Prompt |
|---|---|
| "请 Review 这段代码" | "这段 Diff 是否引入了非 OpenAPI Spec 中定义的字段？" |
| "有什么改进建议？" | "这段逻辑是否处理了上游函数可能抛出的所有强类型异常？" |
| "代码质量怎么样？" | "指出这段代码中时间复杂度超过 O(n²) 的具体行号，如果没有则仅输出 PASS。" |
| "有没有安全问题？" | "这段代码是否存在未经验证的外部输入直接拼接到命令行中？" |

### 3.3 Review 范围圈定

Model 只 Review 新增业务逻辑。其余由专业工具负责：

| 关注点 | 负责方 | 工具 |
|---|---|---|
| 语法风格 | Linter | Prettier, ESLint, ShellCheck |
| 安全漏洞 | SAST | SonarQube, Snyk |
| 依赖安全 | 供应链扫描 | Dependabot, npm audit |
| **业务逻辑正确性** | **Model** | 针对 Spec/Issue 的具体审查 |
| **边界条件覆盖** | **Model** | 对照 Spec 中的 edge case |

### 3.4 Review Checklist 自动化

手动维护 Checklist 不可持续。建议从 Spec/Issue 自动生成 Review Checklist：

```
Spec → 提取边界条件 → 生成 Checklist → 注入到 Model 的 Review Prompt
```

---

## 四、Vibe Center 项目自检

以下对照 MSC 范式，逐项检验 Vibe Center 2.0 的当前实现状态。

### 4.1 Spec 层自检

| 检查项 | 标准 | 现状 | 评级 |
|---|---|---|---|
| 结构化 Spec 存在 | OpenAPI/Schema 定义 | `openspec/` 已初始化，但 `specs/` 目录为空 | ⚠️ 框架搭好但没内容 |
| CLI 命令签名定义 | 命令表、参数类型、返回值 | CLAUDE.md 有命令列表，但非强类型定义 | ⚠️ 存在但非机器可读 |
| Skills 契约定义 | YAML frontmatter 规范 | 每个 SKILL.md 都有结构化 frontmatter | ✅ 做得好 |
| 测试用例覆盖 | Spec 对应测试 | `tests/test_basic.bats` 只有 2 个用例 | ❌ 严重不足 |
| Contract-First 流程 | 先 Spec 后代码 | 有 PRD + Tech Spec + Test Plan 体系<br>（`docs/specs/` 中可见） | ✅ 流程存在 |

**诊断**：Spec 层的框架和理念都到位了（openspec 集成、PRD 驱动），但**落地程度不足**——openspec/specs 是空的，测试覆盖极低。

### 4.2 Context 层自检

| 检查项 | 标准 | 现状 | 评级 |
|---|---|---|---|
| AST 检索能力 | 脚本级 AST 提取 | Serena MCP 已集成并制定 `docs/standards/serena-usage.md` 使用规范 | ✅ 已集成 |
| 类型/语法检查反馈 | 自动触发 ShellCheck | `scripts/lint.sh` 双层 lint (zsh -n + shellcheck) 已集成 | ✅ 已集成 |
| 测试运行反馈 | bats-core 自动执行 | 20 个测试用例，4 个文件全部通过 | ✅ 已达标 |
| Context 收敛机制 | 防止整文件投喂 | Serena 使用规范强制要求 AST 检索替代 cat | ✅ 有工具约束 |
| 循环修复闭环 | 错误→修复→重测 | `vibe-test-runner` Skill 实现 3 轮熔断闭环 | ✅ 已集成 |
| 确定性治理技能 | boundary-check, rules-enforcer | 9 个 Skills 完整覆盖治理场景 | ✅ 做得好 |

**诊断**：Context 层已完成工具级闭环——Serena AST 检索、双层 Lint、bats 测试三位一体；`vibe-test-runner` Skill 提供 3 轮熔断的自动修复回路；治理 Skills 持续覆盖边界管理。

### 4.3 Model 层自检

| 检查项 | 标准 | 现状 | 评级 |
|---|---|---|---|
| Review Checklist 化 | 具体 Yes/No 问题 | `rules-enforcer` Skill 有结构化 Checklist | ✅ 做得好 |
| Review 范围圈定 | Model 只管业务逻辑 | CLAUDE.md 明确了"不做清单" | ✅ 做得好 |
| Negative Prompting | 禁止开放式 Review | Skills 使用具体的 Execution Steps | ✅ 做得好 |
| CI/CD 集成 | 自动触发 Review | `.github/workflows/ci.yml` 已建立 | ✅ 已集成 |
| Review Checklist 自动生成 | Spec → Checklist | 手动维护 | ⚠️ 有改进空间 |

**诊断**：Model 层的**提示词工程做得最好**——治理 Skills 已经是 Checklist 化的、结构化的、有明确输出格式的。唯一缺失是 CI/CD 自动触发。

### 4.4 总体评估

```
Spec 层:    ████████░░ 80%  — openspec/specs 已填充，20 个 bats 测试覆盖所有模块
Context 层: ██████████ 100% — Serena + 双层 Lint + bats 三位一体，vibe-test-runner 提供 3 轮熔断
Model 层:   ██████████ 100% — CI/CD 已集成，提示词工程成熟
```

### 4.5 MSC 合规证据

运行 `bash scripts/metrics.sh` 的实际输出：

| 指标 | 上限 | 当前值 | 状态 |
|------|------|--------|------|
| 总 LOC | 1200 | 689 | ✅ 57% |
| 最大文件行数 | 200 | 191 (flow.sh) | ✅ |
| 测试用例数 | ≥20 | 20 | ✅ |
| ShellCheck errors | 0 | 0 | ✅ |
| Zsh 语法检查 | PASS | ✅ | ✅ |
| 死代码函数 | 0 | 0 | ✅ |
| Serena 配置 | ✅ | ✅ | ✅ |
| CLI Spec 覆盖 | ✅ | ✅ | ✅ |

---

## 五、改进路线图

### 优先级 P0：补齐 Spec 落地

| 行动 | 产出 | 预估工作量 |
|---|---|---|
| 为 CLI 命令写结构化 Spec | YAML 格式的命令签名定义 | 2h |
| 补充 bats-core 测试到 ≥20 个用例 | `tests/*.bats` | 4h |
| 在 openspec/specs 中填充至少一个完整 Spec | 可执行的 Spec 示例 | 1h |

### 优先级 P1：工具级 Context 闭环

| 行动 | 产出 | 预估工作量 |
|---|---|---|
| ShellCheck 集成为 pre-commit hook | `.github/hooks/pre-commit` | 1h |
| 创建 `test-runner` Skill 自动执行 bats | `skills/vibe-test-runner/SKILL.md` | 2h |
| 添加自动修复闭环逻辑（3 轮熔断） | 工作流更新 | 3h |

### 优先级 P2：CI/CD 触发

| 行动 | 产出 | 预估工作量 |
|---|---|---|
| GitHub Actions: ShellCheck + bats-core | `.github/workflows/ci.yml` | 2h |
| PR 自动触发 rules-enforcer review | Actions workflow | 3h |

---

## 六、度量指标

无度量则无工程。以下指标用于持续跟踪 MSC 范式的健康度：

| 指标 | 计算方式 | 当前值 | 目标值 |
|---|---|---|---|
| **Spec 覆盖率** | 有 Spec 的命令数 / 总命令数 | ~30% | ≥80% |
| **测试覆盖率** | 测试用例数 / 核心功能数 | 2/8 = 25% | ≥80% |
| **LOC 健康度** | 当前 LOC / LOC Ceiling | 727/1200 = 61% | ≤80% |
| **自动修复成功率** | ShellCheck 自动修复轮次 pass rate | N/A | ≥70% |
| **Review False Positive** | AI Review 标记的无效问题比例 | N/A | ≤20% |
| **死代码数** | 定义但未被调用的函数数 | 待测量 | = 0 |

---

## 参考文档

- [SOUL.md](../SOUL.md) — 项目宪法与认知优先原则
- [CLAUDE.md](../CLAUDE.md) — 项目技术规范与硬性治理规则
- [OpenSpec Guide](openspec-guide.md) — OpenSpec 工作流指南
- [DEVELOPER.md](../DEVELOPER.md) — 开发者指南
