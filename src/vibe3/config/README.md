# Config

配置加载与 schema 验证层，从 YAML 文件加载配置并通过 Pydantic 验证。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| settings.py | 474 | 主配置 schema（VibeConfig、AIConfig、QualityConfig 等） |
| loader.py | 467 | YAML 加载逻辑、配置文件解析、环境变量覆盖 |
| convention_resolver.py | 279 | 约定解析器（ConventionResolver、get_convention） |
| __init__.py | 242 | 公共 API 导出（lazy import） |
| agent_preset.py | 242 | Agent 预设解析（resolve_repo_agent_preset、read_models_json） |
| env_override.py | 230 | 环境变量覆盖规则（OVERRIDE_RULES） |
| timeline_comment_policy.py | 179 | 时间线评论策略（TimelineCommentPolicy） |
| profile_convention.py | 148 | Profile 约定（ProfileConvention、LabelsConvention） |
| profile_config.py | 118 | Profile 配置（ProfileConfig） |
| settings_pr.py | 87 | PR 评分配置（PRScoringConfig） |
| cli_overrides.py | 75 | CLI 角色覆盖（RoleCliOverrides、build_role_cli_overrides） |
| get.py | 74 | 配置值查询 CLI（get_config 快捷函数） |
| role_policy.py | 69 | 角色输出契约（RoleOutputContract、get_role_section） |
| manager_config.py | 61 | Manager 配置辅助（get_manager_usernames、get_handoff_state_label） |
| utils.py | 59 | 配置工具函数 |
| config_loader.py | 58 | 按角色加载配置（load_config_for_role） |
| settings_check_cleanup.py | 42 | Check cleanup 配置 |
| orchestra_config.py | 34 | Orchestra 配置 re-export（OrchestraConfig、PeriodicCheckConfig、QueueRefreshConfig） |
| orchestra_settings.py | 22 | Orchestra 配置辅助（load_orchestra_config） |
| role_gates.py | 11 | 角色 gate 常量（MANAGER_GATE_CONFIG、PLANNER_GATE_CONFIG 等） |
| branch_convention.py | 9 | Branch 约定 re-export（BranchConvention） |

截至 2026-06，总计 21 文件，约 2980 行代码。

## 架构说明

Config 模块采用分层配置架构，将配置分为根配置和子配置域。

### 配置层次结构

```
VibeConfig (根配置)
├── ai: AIConfig
│   └── agent_prompt: AgentPromptConfig
├── code_paths: CodePathsConfig
│   └── exclude: list[str]
├── code_limits: CodeLimitsConfig
│   ├── single_file_loc: int (default: 500)
│   └── total_file_loc: int (default: 3000)
├── test_paths: TestPathsConfig
│   └── test_dirs: list[str]
├── review_scope: ReviewScopeConfig
│   └── max_files: int
├── quality: QualityConfig
│   └── merge_gate: MergeGateConfig
│       ├── tests: str
│       ├── mypy: str
│       └── ruff: str
├── pr_scoring: PRScoringConfig
│   ├── high_risk_file_patterns: list[str]
│   ├── critical_paths: list[str]
│   └── penalty_thresholds: dict
├── flow: FlowConfig
│   └── auto_merge_label: str
└── plan: PlanConfig
    └── max_files: int
```

### 加载流程

```
config/settings.yaml
       ↓
   loader.py (load_config, load_config_with_env_override)
       ↓
   settings.py (VibeConfig 验证)
       ↓
   get.py (get_config 缓存)
```

### 约定解析

```
vibe.profile.yaml (或 VIBE_PROFILE 环境变量)
       ↓
   convention_resolver.py (ConventionResolver, diagnose_profile)
       ↓
   profile_convention.py (ProfileConvention, LabelsConvention)
       ↓
   profile_config.py (ProfileConfig)
```

### 设计原则

- **单一职责**: `loader.py` 只负责加载，`settings.py` 只定义 schema
- **类型安全**: 所有配置通过 Pydantic BaseModel 验证
- **懒加载**: 配置在首次访问时加载，后续通过 `get_config()` 缓存
- **分离关注点**: PR scoring、timeline comment 等子配置独立文件
- **约定优于配置**: 通过 `ConventionResolver` 支持 profile-based 约定
- **环境变量覆盖**: 通过 `env_override.py` 支持环境变量覆盖配置

## 公共 API

`__init__.py` 导出以下 63 个符号：

### 配置模型（Config Classes）

- **VibeConfig**: 根配置模型
- **AIConfig**: AI 配置模型
- **AgentPromptConfig**: Agent prompt 配置
- **CodePathsConfig**: 代码路径配置
- **CodeLimitsConfig**: 代码限制配置
- **TestPathsConfig**: 测试路径配置
- **ReviewScopeConfig**: Review 范围配置
- **QualityConfig**: 质量配置
- **MergeGateConfig**: Merge gate 配置
- **PRScoringConfig**: PR 评分配置
- **PlanConfig**: Plan 配置
- **FlowConfig**: Flow 配置
- **RunConfig**: Run 配置
- **PathsConfig**: 路径配置
- **SingleFileLocConfig**: 单文件行数配置
- **TotalFileLocConfig**: 总行数配置
- **OrchestraConfig**: Orchestra 配置（re-export）
- **PeriodicCheckConfig**: Periodic check 配置（re-export）
- **QueueRefreshConfig**: Queue refresh 配置（re-export）

### 约定与 Profile

- **ConventionResolver**: 约定解析器
- **ProfileConvention**: Profile 约定模型
- **ProfileConfig**: Profile 配置模型
- **LabelsConvention**: Labels 约定模型
- **BranchConvention**: Branch 约定模型

### 角色相关

- **RoleOutputContract**: 角色输出契约
- **RoleCliOverrides**: CLI 角色覆盖
- **ROLE_CONFIG_SECTIONS**: 角色配置段映射

### 策略配置

- **TimelineCommentPolicy**: 时间线评论策略
- **DEFAULT_COMMENT_POLICY**: 默认评论策略

### Gate 配置

- **MANAGER_GATE_CONFIG**: Manager gate 配置
- **PLANNER_GATE_CONFIG**: Planner gate 配置
- **REVIEWER_GATE_CONFIG**: Reviewer gate 配置
- **SUPERVISOR_IDENTIFY_GATE_CONFIG**: Supervisor identify gate 配置
- **SUPERVISOR_APPLY_GATE_CONFIG**: Supervisor apply gate 配置
- **EXECUTOR_GATE_CONFIG**: Executor gate 配置
- **GOVERNANCE_GATE_CONFIG**: Governance gate 配置

### 环境覆盖

- **OVERRIDE_RULES**: 环境变量覆盖规则

### 配置加载函数

- **get_config**: 获取全局配置实例（带缓存）
- **load_config**: 从文件加载配置
- **reload_config**: 强制重新加载配置
- **load_config_with_env_override**: 加载配置并应用环境变量覆盖
- **load_runtime_config**: 加载运行时配置
- **load_keys_env_fallback**: 加载密钥（环境变量 fallback）
- **load_orchestra_config**: 加载 Orchestra 配置
- **load_config_for_role**: 按角色加载配置

### 配置查询函数

- **get_convention**: 获取当前约定
- **get_resolver**: 获取约定解析器实例
- **diagnose_profile**: 诊断 profile 配置
- **get_commands_root**: 获取 commands 根目录
- **get_source_root**: 获取 source 根目录
- **get_role_output_contract**: 获取角色输出契约
- **get_role_section**: 获取角色配置段
- **get_handoff_state_label**: 获取 handoff state label
- **get_manager_usernames**: 获取 manager 用户名列表

### Agent 预设函数

- **resolve_repo_agent_preset**: 解析 repo agent preset
- **resolve_repo_agent_preset_name**: 解析 repo agent preset 名称
- **resolve_effective_agent_options**: 解析有效 agent 选项
- **read_models_json**: 读取 models.json
- **repo_models_json_path**: 获取 repo models.json 路径
- **has_agent_env_override**: 检查是否有 agent 环境变量覆盖
- **find_missing_backend_commands**: 查找缺失的 backend 命令

### CLI 辅助

- **build_role_cli_overrides**: 构建 role CLI 覆盖

## 内部依赖

```
config/
├── loader.py → settings.py (VibeConfig)
├── settings.py → settings_pr.py (PRScoringConfig)
├── settings.py → models.orchestra_config (OrchestraConfig)
├── orchestra_config.py → models.orchestra_config (re-export)
├── orchestra_settings.py → settings.py (VibeConfig)
├── orchestra_settings.py → models.orchestra_config (OrchestraConfig)
├── convention_resolver.py → profile_convention.py (ProfileConvention)
├── convention_resolver.py → profile_config.py (ProfileConfig)
├── agent_preset.py → models.adapter_manifest (AdapterManifest)
├── config_loader.py → loader.py (load_config)
├── get.py → loader.py (load_config)
└── role_policy.py → models (部分模型引用)
```

**循环依赖检查**: ✅ 无循环依赖

**跨模块依赖**:
- `settings.py`, `orchestra_config.py`, `orchestra_settings.py` 依赖 `models.orchestra_config`（OrchestraConfig 在 models 层定义并在 config 层 re-export）
- `agent_preset.py` 依赖 `models.adapter_manifest`

## 外部依赖

- **models/**: OrchestraConfig, AdapterManifest 等模型
- **exceptions/**: ConfigError

## 被依赖

- ~106 个文件引用，覆盖 agents/analysis/commands/domain/environment/execution/orchestra/roles/runtime/server/services 等几乎所有模块

## 架构演变说明

### 配置加载历史

**早期设计**：配置分散在多个入口点，缺乏统一的加载逻辑

**当前设计**：
1. `loader.py` 统一加载逻辑
2. `settings.py` 定义所有 schema
3. `get.py` 提供全局访问入口
4. `convention_resolver.py` 支持约定解析

### 约定系统

**设计目标**：支持多 profile 配置（vibe-center、github-flow 等）

**实现方式**：
1. 通过 `VIBE_PROFILE` 环境变量或 `vibe.profile.yaml` 指定 profile
2. `ConventionResolver` 解析 profile 并加载对应约定
3. 约定包括 labels、branch naming、adapter 配置等

### Agent 预设系统

**设计目标**：支持多种 agent backend（codeagent、claude-api 等）

**实现方式**：
1. `config/v3/models.json` 定义 agent presets
2. `agent_preset.py` 解析 preset 并验证 backend 命令可用性
3. 支持环境变量覆盖（`CLAUDE_CODE_MODEL` 等）

## 设计原则

- **Pydantic BaseModel**: 所有配置通过 Pydantic 验证，提供类型安全
- **YAML 格式**: 配置文件使用 YAML 格式，易于阅读和编辑
- **环境变量支持**: 敏感信息（密钥）通过环境变量注入
- **约定优于配置**: 通过 profile 系统支持多场景配置
- **单一数据源**: 配置从单一文件加载，避免配置分散
- **懒加载**: 配置在首次访问时加载，减少启动开销
