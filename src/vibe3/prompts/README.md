# Prompts

Prompt 模板组装层，加载模板、解析变量、记录 provenance，并从配置文件
读取角色 prompt 的装配顺序。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 1 | 模块初始化 |
| provider_registry.py | 34 | Provider 注册中心，变量解析分发 |
| exceptions.py | 56 | 模块专用异常定义 |
| models.py | 73 | PromptRecipe, PromptRenderResult 等数据模型 |
| context_builder.py | 93 | 运行时上下文构建，配置注入 |
| assembler.py | 113 | PromptAssembler 主拼装器，模板变量替换 |
| builtin_providers.py | 130 | 内置变量 provider（git/code/config 来源） |
| template_loader.py | 154 | 模板文件加载，YAML 解析 |
| manifest.py | 170 | 装配表加载、variant 解析、section 渲染 |
| validation.py | 232 | 模板校验，变量检查 |

截至 2026-05，总计约 1056 行。

## 职责

- 加载文本模板（config/prompts/prompts.yaml）
- 加载装配表（config/prompts/prompt-recipes.yaml）
- 注册和解析变量 provider（code/git/config 来源）
- 组装最终 prompt（变量替换 + 段落拼接）
- 记录变量 provenance（用于审计追踪）
- 支持通过命令 dry-run 查看运行时 prompt

## 关键组件

### assembler.py
**PromptAssembler** 是核心拼装器，负责：
1. 加载模板文件
2. 解析变量引用（`{{variable}}` 语法）
3. 调用 ProviderRegistry 解析变量值
4. 执行变量替换并记录 provenance
5. 返回 PromptRenderResult（含最终文本和变量来源追踪）

### provider_registry.py
**ProviderRegistry** 是变量解析中心：
1. 维护 variable name → provider function 映射
2. 支持动态注册 provider
3. 变量解析时按优先级查找 provider
4. 提供变量缺失时的错误信息

### manifest.py
负责装配表的加载和解析：
1. 从 `config/prompt-recipes.yaml` 加载配方
2. 解析 variant（如 `plan.default` vs `plan.detailed`）
3. 按 section 顺序渲染段落
4. 支持条件性包含段落

### builtin_providers.py
提供内置变量解析器：
- `git_*`: Git 相关变量（branch, commit, status）
- `code_*`: 代码分析变量
- `config_*`: 配置文件变量
- `env_*`: 环境变量

## 配置关系

`config/prompts/prompts.yaml` 保留实际 prompt 文本、模板和说明。
`config/prompts/prompt-recipes.yaml` 回答”某个 prompt variant 使用哪些 section、什么顺序”。
当前 `run.*` / `plan.*` / `review.*` 均由 recipe 驱动。

## 依赖关系

```
prompts/
├── assembler.py → builtin_providers, exceptions, models, provider_registry, template_loader
├── builtin_providers.py → exceptions, models, provider_registry
├── context_builder.py → assembler, models, provider_registry
├── validation.py → assembler, models, provider_registry, template_loader
└── 其他模块：无内部依赖（exceptions, models, provider_registry, template_loader, manifest）
```

**外部依赖**:
- loguru: 日志记录
- pydantic: 数据模型
- yaml: 配置文件解析
- vibe3.exceptions: VibeError 基类
- vibe3.services.flow_service: Git common dir 解析（builtin_providers，条件导入）

**被依赖**:
- **agents/**: prompt 构建（plan_prompt, run_prompt, review_prompt）
- **execution/**: PromptManifest (governance_sync_runner), collect_dry_run_provenance (governance_sync_runner), resolve_governance_material (governance_sync_runner), PromptAssembler (job_executor)
- **manager/**: manager prompts
- **commands/**: dry-run 命令
- **domain/**: collect_dry_run_provenance, resolve_governance_material
- **roles/**: section builders

## 公开 APIs

| 符号 | 类型 | 消费位置 |
|------|------|---------|
| **Core** | | |
| PromptAssembler | 核心拼装器 | agents/, execution/, commands/ |
| PromptContextBuilder | 上下文构建器 | agents/, commands/ |
| make_context_builder | 工厂函数 | agents/, commands/ |
| **Manifest** | | |
| PromptManifest | 配方加载器 | execution/, commands/ |
| PromptProvider | 提供者定义 | commands/ |
| PromptRecipeDefinition | 配方定义 | commands/ |
| PromptRecipeVariant | 变体定义 | commands/ |
| **Models** | | |
| PromptRecipe | 数据模型 | commands/ |
| PromptRenderResult | 渲染结果 | agents/, commands/ |
| PromptVariableSource | 变量来源 | commands/ |
| PromptRenderProvenance | 来源追踪 | execution/, domain/ |
| PromptVariableProvenance | 变量来源追踪 | commands/ |
| PromptSectionSpec | 段落规格 | commands/ |
| PromptMaterialSpec | 材料规格 | commands/ |
| PromptRecipeKind | 配方类型 | commands/ |
| VariableSourceKind | 来源类型 | commands/ |
| AnomalyFlags | 异常标记 | commands/ |
| MaterialEntry | 材料条目 | commands/ |
| PolicyEntry | 策略条目 | commands/ |
| LoadedPromptRecipeDefinition | 加载后配方 | commands/ |
| PromptRecipeVariantSpec | 变体规格 | commands/ |
| SectionSourceProvenance | 段落来源 | commands/ |
| **Provider** | | |
| ProviderRegistry | 注册中心 | agents/, commands/ |
| **Validation** | | |
| PromptValidationService | 校验服务 | commands/ |
| PromptValidationResult | 校验结果 | commands/ |
| ValidationIssue | 校验问题 | commands/ |
| **Exceptions** | | |
| PromptAssemblyError | 组装异常 | agents/, commands/ |
| MissingVariableError | 变量缺失 | agents/, commands/ |
| ProviderNotFoundError | 提供者未找到 | commands/ |
| TemplateNotFoundError | 模板未找到 | commands/ |
| ContextBuilderError | 构建器异常 | commands/ |
| **Template helpers** | | |
| DEFAULT_PROMPTS_PATH | 默认路径 | commands/ |
| load_prompt_templates | 加载模板 | commands/ |
| resolve_prompt_template | 解析模板 | agents/, commands/ |
| resolve_prompts_path | 解析路径 | commands/ |
| resolve_source | 解析来源 | commands/ |
| **Section builders** | | |
| build_policy_section | 策略段落 | agents/, roles/ |
| build_tools_guide_section | 工具指南段落 | agents/, roles/ |
| build_common_rules_section | 通用规则段落 | agents/, roles/ |
| build_project_common_rules_section | 项目通用规则 | agents/, roles/ |
| build_project_policy_section | 项目策略段落 | agents/, roles/ |
| resolve_common_rules_path | 解析规则路径 | agents/, roles/ |
| discover_project_scope_overlays | 发现覆盖层 | agents/, roles/ |
| **Provenance** | | |
| collect_dry_run_provenance | 收集来源 | execution/, domain/, commands/ |
| **Governance Material** | | |
| load_governance_material_catalog | 加载材料目录 | execution/, domain/ |
| resolve_governance_material | 解析材料 | execution/, domain/ |
| build_governance_execution_name | 构建执行名称 | execution/ |

## execution 层接口

execution 层通过以下接口使用 prompts 模块：

- **execution/governance_sync_runner**: 导入 `PromptManifest`, `collect_dry_run_provenance`, `resolve_governance_material`
- **execution/job_executor**: 导入 `PromptAssembler`

prompts 模块为 execution 层提供 prompt 上下文装配能力，是 agent 执行的下游依赖。

## 三层协作关系

```
runtime (事件循环驱动)
  └─ HeartbeatServer.on_tick()
       ├─ domain.OrchestrationFacade.on_tick() → 发布 domain events
       │    └─ execution.ExecutionCoordinator → 调度 agent 执行
       │         └─ agents.CodeagentBackend.run(prompt)
       │              └─ prompts.PromptAssembler.assemble() → 装配 prompt 上下文
       └─ runtime.execute_periodic_check() → 一致性检查 & 资源清理
```

prompts 模块处于三层架构的最底层：
- **上层消费者**: agents 层通过 prompts 构建 plan/run/review prompt
- **核心职责**: 加载模板、解析变量、装配上下文、追踪来源
- **执行支持**: 为 agent 执行提供最终的要发送给 LLM 的 prompt 文本
